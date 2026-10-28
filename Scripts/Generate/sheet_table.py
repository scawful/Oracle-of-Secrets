#!/usr/bin/env python3
"""Read-only survey of the ALTTP graphics sheet pointer tables and packing.

Usage: sheet_table.py <rom> [--vanilla <rom>] [--base <rom>] [--json out.json]

Global sheet g (0..222) pointer = bank[$00:CF80+g], high[$00:D05F+g], low[$00:D13E+g].
Sprite sheet s = global s+$73 (Decompress_sprite_arbitrary $00:E772 reads $CFF3/$D0D2/$D1B1,Y).
Global 115-126 (sprite $00-$0B) are stored uncompressed (0x600 bytes, read raw).
"""
import sys, json, hashlib, argparse
import lz2

def pc(a): return ((a >> 16) & 0x7f) * 0x8000 + (a & 0x7fff)

def decomp(rom, addr):
    """Vanilla LC-LZ2 (Decompress $00:E79E). Returns (data, compressed_len)."""
    return lz2.decompress(rom, pc(addr))

TBL_BANK, TBL_HIGH, TBL_LOW = 0x00CF80, 0x00D05F, 0x00D13E
N = 223

# Relocated arrays (Core/gfx_sheet_table.asm): bank $23, $100 rows each.
NEW_BANK, NEW_HIGH, NEW_LOW = 0x23FD00, 0x23FE00, 0x23FF00

def relocated(rom):
    """True when Decompress_sprite_arbitrary ($00:E772) is a JSL to the helper."""
    return rom[pc(0x00E772)] == 0x22

def table_operands(rom):
    # $00:E772 LDA.w $CFF3,Y ; $00:E777 LDA.w $D0D2,Y ; $00:E77C LDA.w $D1B1,Y
    out = {}
    if relocated(rom):
        return out
    for name, a in (('bank', 0x00E772), ('high', 0x00E777), ('low', 0x00E77C)):
        i = pc(a); out[name] = (rom[i], rom[i+1] | (rom[i+2] << 8))
    return out

def ptr(rom, g):
    bank, high, low = (NEW_BANK, NEW_HIGH, NEW_LOW) if relocated(rom) else (TBL_BANK, TBL_HIGH, TBL_LOW)
    return (rom[pc(bank)+g] << 16) | (rom[pc(high)+g] << 8) | rom[pc(low)+g]

def survey(rom):
    rows = []
    # $FF remains the default sentinel. Expanded background rows are 3bpp;
    # only the seven named legacy ranges use the native 2bpp loader.
    for g in range(0xFF if relocated(rom) else N):
        a = ptr(rom, g)
        unc = 115 <= g <= 126
        two = g in (113, 114) or 218 <= g < N
        if unc:
            data, clen = bytes(rom[pc(a):pc(a)+0x600]), 0x600
        else:
            try: data, clen = decomp(rom, a)
            except Exception as e: data, clen = b'', -1
        rows.append(dict(g=g, spr=(g-0x73 if g >= 0x73 else None), ptr=a, pcaddr=pc(a), clen=clen,
                         dlen=len(data), uncompressed=unc, bpp=2 if two else 3,
                         sha=hashlib.sha1(data).hexdigest()[:12], data=data))
    # packing: gap to next distinct start address (by PC order)
    order = sorted(rows, key=lambda r: r['pcaddr'])
    for i, r in enumerate(order):
        nxt = next((o['pcaddr'] for o in order[i+1:] if o['pcaddr'] > r['pcaddr']), None)
        r['gap'] = (nxt - r['pcaddr']) if nxt is not None else None
        r['slack'] = (r['gap'] - r['clen']) if (nxt is not None and r['clen'] >= 0) else None
    return rows


# Explicit-layout ownership audit. Unlike survey(), failures are retained and
# fail the preflight; an unreadable stream cannot be treated as unused space.
def stream_extents(rom, layout):
    tables, count = ((TBL_BANK, TBL_HIGH, TBL_LOW), N) if layout == 'base' else ((NEW_BANK, NEW_HIGH, NEW_LOW), 256)
    rows, errors = [], []
    for g in range(count):
        try:
            pointer = sum(rom[pc(t)+g] << shift for t, shift in zip(tables, (16, 8, 0)))
            if pointer & 0xFFFF < 0x8000 or pointer >> 16 & 0x7F >= 0x7E:
                raise ValueError('unmapped LoROM pointer')
            start = pc(pointer)
            raw = 0x73 <= g <= 0x7E
            if raw:
                data = rom[start:start+0x600]
                if len(data) != 0x600: raise ValueError('truncated raw sheet')
                consumed = 0x600
            else:
                data, consumed = lz2.decompress(rom, start)
            expected = 0x800 if g in (0x71, 0x72, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE) else 0x600
            if len(data) != expected:
                raise ValueError(f'decoded length {len(data)} != {expected}')
            rows.append(dict(id=g, pointer=pointer, start_pc=start,
                             end_pc=start+consumed, encoding='raw' if raw else 'lc-lz2',
                             decoded_size=len(data), decoded_sha256=hashlib.sha256(data).hexdigest(),
                             consumed_sha256=hashlib.sha256(rom[start:start+consumed]).hexdigest()))
        except (ValueError, IndexError) as exc:
            errors.append(dict(id=g, error=str(exc)))
    groups = {}
    for r in rows:
        groups.setdefault((r['start_pc'], r['end_pc']), []).append(r['id'])
    aliases = [dict(start_pc=a, end_pc=b, ids=ids) for (a,b),ids in sorted(groups.items()) if len(ids)>1]
    # Distinct starts whose consumed bytes overlap are also aliases/overlaps;
    # equal-start aliases above alone would miss a pointer into another stream.
    overlaps = []
    unique = sorted(groups)
    for i, (a,b) in enumerate(unique):
        for c,d in unique[i+1:]:
            if c >= b: break
            overlaps.append(dict(left_ids=groups[a,b], right_ids=groups[c,d],
                                 start_pc=c, end_pc=min(b,d)))
    return dict(layout=layout, sha256=hashlib.sha256(rom).hexdigest(),
                size=len(rom), rows=rows, aliases=aliases,
                overlapping_streams=overlaps, errors=errors)

def ownership_preflight(base, candidate, symbols):
    """Read actual consumed stream extents; no allocation or current build grant."""
    import re
    names = {}
    for line in symbols.splitlines():
        m = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (GfxSheet_[A-Za-z_]+)', line.strip())
        if m: names[m[3]] = (int(m[1],16)<<16) | int(m[2],16)
    issues = []
    for name, address in (('GfxSheet_Helpers',0x23FC00), ('GfxSheet_Bank',NEW_BANK),
                          ('GfxSheet_High',NEW_HIGH), ('GfxSheet_Low',NEW_LOW)):
        if names.get(name) != address: issues.append('symbol mismatch: '+name)
    empty = names.get('GfxSheet_EmptyStream')
    if empty is None or not 0x23FC00 <= empty < 0x23FD00:
        issues.append('empty stream symbol missing/outside helper interval')
    reports = [stream_extents(base,'base'), stream_extents(candidate,'candidate')]
    start, end = 0x11FC00, 0x120000
    for report in reports:
        report['intersections'] = []
        for row in report['rows']:
            if row['start_pc'] < end and row['end_pc'] > start:
                intended = (report['layout']=='candidate' and empty is not None
                            and row['id']>=0xDF and row['pointer']==empty
                            and row['start_pc']==pc(empty) and row['end_pc']<=0x11FD00
                            and row['decoded_size']==0x600
                            and candidate[row['start_pc']:row['end_pc']]==bytes.fromhex('e7ff00e5ff00ff'))
                report['intersections'].append(dict(**row, intended= intended))
                if not intended: issues.append(f"unexpected {report['layout']} stream {row['id']:02X} overlaps top 1KiB")
        if report['errors']: issues.append(report['layout']+' has undecodable/invalid streams')
    candidate_rows = {r['id']:r for r in reports[1]['rows']}
    for g in range(0xDF,0x100):
        row=candidate_rows.get(g)
        if row is None or row['pointer']!=empty: issues.append(f'new row {g:02X} is not the intended empty stream')
    return dict(schema_version=1, verdict='HOLD' if issues else 'STREAM_PREFLIGHT_PASS',
                allocation_granted=False, current_base_build=False,
                generic_yaze_new_id_writer_contract='PENDING', issues=issues,
                protected_interval_pc=[start,end],
                intended_consumers=[dict(owner='GfxSheet helpers/empty stream',start_pc=start,end_pc=0x11FD00),
                                    dict(owner='bank array',start_pc=0x11FD00,end_pc=0x11FE00),
                                    dict(owner='high array',start_pc=0x11FE00,end_pc=0x11FF00),
                                    dict(owner='low array',start_pc=0x11FF00,end_pc=end)],
                empty_stream_pointer=empty, reports=reports)


def ownership_cli(args):
    """One fresh output inode per attempt; never reopen/truncate a named input."""
    import os
    import uuid
    from datetime import datetime, timezone
    from pathlib import Path

    attempt = dict(id=uuid.uuid4().hex, started_utc=datetime.now(timezone.utc).isoformat())
    inputs = dict(base=args.rom, candidate=args.ownership_candidate, symbols=args.ownership_symbols)
    output = Path(args.ownership_json)
    result = dict(schema_version=1, verdict='HOLD', allocation_granted=False,
                  current_base_build=False, generic_yaze_new_id_writer_contract='PENDING',
                  attempt=attempt, inputs=inputs, output=str(output), issues=[])
    # Reject aliases before reserving an inode or reading any input content.
    # samefile covers hardlinks; resolve covers symlinked parent directories.
    try:
        absolute = os.path.abspath(output)
        resolved = output.resolve()
        for name in inputs.values():
            path = Path(name)
            if absolute == os.path.abspath(path) or resolved == path.resolve():
                raise ValueError('ownership output aliases an input')
            if output.exists() and path.exists() and output.samefile(path):
                raise ValueError('ownership output aliases an input inode')
        if os.path.lexists(output):
            raise ValueError('ownership output already exists; choose a fresh attempt path')
        # Use the resolved parent, no final symlink following, and exclusive
        # creation. If a path appears after validation, O_EXCL refuses it.
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, 'O_NOFOLLOW', 0)
        fd = os.open(resolved, flags, 0o600)
    except (OSError, ValueError, RuntimeError) as exc:
        result['issues'] = [f'output identity/reservation refused: {type(exc).__name__}: {str(exc)[:512]}']
        result['output_reserved'] = False
        # No safe artifact path exists. Emit an attempt-bound refusal on stderr,
        # preserving any existing input/evidence file byte for byte.
        print(json.dumps(result), file=sys.stderr)
        return 1

    result['output_reserved'] = True
    stage = 'base input'
    try:
        rom = Path(args.rom).read_bytes()
        stage = 'candidate input'
        candidate = Path(args.ownership_candidate).read_bytes()
        stage = 'symbols input'
        symbol_bytes = Path(args.ownership_symbols).read_bytes()
        symbols = symbol_bytes.decode('utf-8')
        stage = 'preflight parsing'
        measured = ownership_preflight(rom, candidate, symbols)
        result.update(measured)
        result['inputs']['symbols_sha256'] = hashlib.sha256(symbol_bytes).hexdigest()
        if hashlib.sha256(rom).hexdigest() != args.expected_base_sha256:
            result['issues'].append('base SHA256 mismatch')
            result['verdict'] = 'HOLD'
    except (OSError, UnicodeError, ValueError, IndexError, TypeError) as exc:
        result['verdict'] = 'HOLD'
        result['issues'] = [f'{stage}: {type(exc).__name__}: {str(exc)[:512]}']
    result['attempt']['finished_utc'] = datetime.now(timezone.utc).isoformat()
    # Write only through the exclusively reserved descriptor, never reopen the
    # output path after reads. Read/decode failures become this attempt's HOLD.
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as out:
            json.dump(result, out, indent=2)
            out.write('\n')
            out.flush()
            os.fsync(out.fileno())
    except OSError as exc:
        result['verdict'] = 'HOLD'
        result['issues'] = [f'output write: {type(exc).__name__}: {str(exc)[:512]}']
        print(json.dumps(result), file=sys.stderr)
        return 1
    print(result['verdict'], json.dumps(result['issues']))
    return 1 if result['issues'] else 0

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--ownership-candidate'); ap.add_argument('--ownership-symbols')
    ap.add_argument('--expected-base-sha256'); ap.add_argument('--ownership-json')
    ap.add_argument('rom'); ap.add_argument('--vanilla'); ap.add_argument('--base')
    ap.add_argument('--json'); ap.add_argument('--sheets', help='comma hex sprite sheet ids to print')
    a = ap.parse_args()
    if a.ownership_candidate:
        if not (a.ownership_symbols and a.ownership_json and a.expected_base_sha256):
            ap.error('ownership preflight requires symbols, expected base SHA256 and output JSON')
        return ownership_cli(a)
    rom = open(a.rom, 'rb').read()
    print('table operands', {k: (hex(v[0]), hex(v[1])) for k, v in table_operands(rom).items()})
    rows = survey(rom)
    van = survey(open(a.vanilla, 'rb').read()) if a.vanilla else None
    base = survey(open(a.base, 'rb').read()) if a.base else None
    for r in rows:
        if van:
            prior = van[r['g']] if r['g'] < len(van) else None
            r['ptr_eq_vanilla'] = prior['ptr'] == r['ptr'] if prior else None
            r['data_eq_vanilla'] = prior['data'] == r['data'] if prior else None
            r['vanilla_clen'] = prior['clen'] if prior else None
        if base:
            prior = base[r['g']] if r['g'] < len(base) else None
            r['ptr_eq_base'] = prior['ptr'] == r['ptr'] if prior else None
            r['data_eq_base'] = prior['data'] == r['data'] if prior else None
    spr = [r for r in rows if r['g'] >= 0x73]
    sel = [int(x, 16) for x in a.sheets.split(',')] if a.sheets else None
    print(f"{'spr':>4} {'glob':>4} {'ptr':>8} {'clen':>5} {'gap':>5} {'slack':>5} {'dlen':>5} van base")
    for r in spr:
        if sel and r['spr'] not in sel: continue
        print(f"${r['spr']:02X}  {r['g']:4d} ${r['ptr']:06X} {r['clen']:5d} {str(r['gap']):>5} {str(r['slack']):>5} {r['dlen']:5d} "
              f"{'' if not van else ('P' if r['ptr_eq_vanilla'] else 'p')+('D' if r['data_eq_vanilla'] else 'd')} "
              f"{'' if not base else ('P' if r['ptr_eq_base'] else 'p')+('D' if r['data_eq_base'] else 'd')}")
    if a.json:
        json.dump([{k: v for k, v in r.items() if k != 'data'} for r in rows], open(a.json, 'w'), indent=1)

if __name__ == '__main__':
    sys.exit(main())
