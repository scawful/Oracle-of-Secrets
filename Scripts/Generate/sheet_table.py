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
    for g in range(N):
        a = ptr(rom, g)
        unc = 115 <= g <= 126
        two = g in (113, 114) or g >= 218
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

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('rom'); ap.add_argument('--vanilla'); ap.add_argument('--base')
    ap.add_argument('--json'); ap.add_argument('--sheets', help='comma hex sprite sheet ids to print')
    a = ap.parse_args()
    rom = open(a.rom, 'rb').read()
    print('table operands', {k: (hex(v[0]), hex(v[1])) for k, v in table_operands(rom).items()})
    rows = survey(rom)
    van = survey(open(a.vanilla, 'rb').read()) if a.vanilla else None
    base = survey(open(a.base, 'rb').read()) if a.base else None
    for r in rows:
        if van: r['ptr_eq_vanilla'] = van[r['g']]['ptr'] == r['ptr']; r['data_eq_vanilla'] = van[r['g']]['data'] == r['data']; r['vanilla_clen'] = van[r['g']]['clen']
        if base: r['ptr_eq_base'] = base[r['g']]['ptr'] == r['ptr']; r['data_eq_base'] = base[r['g']]['data'] == r['data']
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
    main()
