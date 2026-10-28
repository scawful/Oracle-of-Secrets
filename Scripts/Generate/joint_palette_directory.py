#!/usr/bin/env python3
"""Generate the joint Sky/ferry overworld palette directory without writing a ROM.

The root grant reserves [$1BB6A8,$1BB800): a 7-word main directory, a 25-word
aux directory and fixed record slots main06 and aux20..aux24. Directory words
are bank-$1B record addresses consumed by the four readers in
Overworld/joint_palette_readers.asm. Each granted record is either emitted by
this source ("emit"), already present in the input ROM ("input") or parked.
Asar read*() sees the input ROM only, so input checks never prove emitted data;
emitted data is proved by labels, extents and post-assembly verification.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

SPEC = Path('Data/graphics/joint_palette_directory.json')
OUTPUT = Path('Core/Generated/joint_palette/directory.asm')
FLAG = 'JOINT_PALETTE_DIRECTORY_ENABLED'

ARENA_START, ARENA_END = 0x1BB6A8, 0x1BB800
MAIN_DIR, MAIN_COUNT = 0x1BB6A8, 7
AUX_DIR, AUX_COUNT = 0x1BB6B6, 25
MAIN_BASE, MAIN_SIZE, MAIN_LEGACY = 0x1BE6C8, 70, 6
AUX_BASE, AUX_SIZE, AUX_LEGACY = 0x1BE86C, 42, 20
MAIN_OFFSETS, AUX_OFFSETS = 0x1BEC3B, 0x1BEC13
SET_TABLE, SET_ROWS = 0x0ED504, 0x1F
AREA_SETS = 0x09C635
MAIN_TABLE, MAIN_TABLE_ROWS = 0x288160, 0xA0
SLOTS = {('main', 6): 0x1BB6E8, ('aux', 20): 0x1BB72E, ('aux', 21): 0x1BB758,
         ('aux', 22): 0x1BB782, ('aux', 23): 0x1BB7AC, ('aux', 24): 0x1BB7D6}
SIZES = {'main': MAIN_SIZE, 'aux': AUX_SIZE}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def number(value):
    require(type(value) in (int, str), 'expected an integer or hexadecimal string')
    return int(value, 0) if isinstance(value, str) else value


def single_line(value, name):
    require(isinstance(value, str) and value and '\n' not in value and '\r' not in value,
            f'{name} must be a single non-empty line')


def read_spec(path):
    raw = Path(path).read_bytes()
    spec = json.loads(raw)
    require(type(spec) is dict and set(spec) == {'schema_version', 'arena', 'records', 'parked'},
            'invalid joint palette spec keys')
    require(spec['schema_version'] == 1, 'unsupported joint palette schema')
    arena = spec['arena']
    require(type(arena) is dict and set(arena) == {'start', 'end'}, 'invalid arena keys')
    require((number(arena['start']), number(arena['end'])) == (ARENA_START, ARENA_END),
            'only the granted [$1BB6A8,$1BB800) arena is supported')
    require(type(spec['records']) is list and type(spec['parked']) is list, 'records and parked must be lists')
    seen = {}
    records = []
    for entry in spec['records']:
        require(type(entry) is dict and set(entry) == {'kind', 'id', 'address', 'mode', 'bgr555_hex', 'source',
                                                       'source_sha256', 'why'}, 'invalid record keys')
        key = (entry['kind'], number(entry['id']))
        require(key in SLOTS, f'{key} is not a granted record slot')
        require(key not in seen, f'duplicate record {key}')
        require(number(entry['address']) == SLOTS[key], f'{key} must use its granted address')
        require(entry['mode'] in ('emit', 'input'), 'mode must be emit or input')
        require(isinstance(entry['bgr555_hex'], str) and re.fullmatch('(?:[0-9a-f]{2})+', entry['bgr555_hex']),
                'bgr555_hex must be lowercase hexadecimal bytes')
        data = bytes.fromhex(entry['bgr555_hex'])
        require(len(data) == SIZES[entry['kind']], f'{key} must be {SIZES[entry["kind"]]} bytes')
        require(all(int.from_bytes(data[i:i + 2], 'little') < 0x8000 for i in range(0, len(data), 2)),
                f'{key} contains a non-BGR555 word')
        require(isinstance(entry['source_sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['source_sha256']),
                'source_sha256 must be a full lowercase SHA256')
        single_line(entry['source'], 'source')
        single_line(entry['why'], 'why')
        seen[key] = 'record'
        records.append(dict(kind=key[0], id=key[1], address=SLOTS[key], mode=entry['mode'], data=data,
                            why=entry['why']))
    for entry in spec['parked']:
        require(type(entry) is dict and set(entry) == {'kind', 'id', 'address', 'why'}, 'invalid parked keys')
        key = (entry['kind'], number(entry['id']))
        require(key in SLOTS and key not in seen, f'parked {key} is not a free granted slot')
        require(number(entry['address']) == SLOTS[key], f'parked {key} must use its granted address')
        single_line(entry['why'], 'why')
        seen[key] = 'parked'
    require(set(seen) == set(SLOTS), 'every granted slot must be a record or parked')
    return spec, records, sorted(k for k, v in seen.items() if v == 'parked'), hashlib.sha256(raw).hexdigest()


def label(kind, ident):
    return f'JointPalette_{kind.capitalize()}{ident:02d}'


def directory_words(records):
    """Every directory word: legacy record or granted slot. Parked ids stay unreachable (checked)."""
    main = [f'${MAIN_BASE + MAIN_SIZE * i & 0xFFFF:04X}' for i in range(MAIN_LEGACY)]
    aux = [f'${AUX_BASE + AUX_SIZE * i & 0xFFFF:04X}' for i in range(AUX_LEGACY)]
    present = {(r['kind'], r['id']) for r in records}
    for kind, words, count in (('main', main, MAIN_COUNT), ('aux', aux, AUX_COUNT)):
        for ident in range(len(words), count):
            key = (kind, ident)
            words.append(f'{label(kind, ident)}&$FFFF' if key in present else f'${SLOTS[key] & 0xFFFF:04X}')
    return main, aux


def reachable_expr(expr, legacy, ids, keep_marker):
    """Allowed: legacy ids, bound records and (set table only) the BMI keep-previous marker."""
    terms = ([f'{expr} >= $80'] if keep_marker else []) + [f'{expr} < {legacy}']
    return ' || '.join(terms + [f'{expr} == {i}' for i in sorted(ids)])


def asm_text(records, parked, spec_sha):
    main_words, aux_words = directory_words(records)
    main_ok = {r['id'] for r in records if r['kind'] == 'main'}
    aux_ok = {r['id'] for r in records if r['kind'] == 'aux'}
    emitted = [r for r in records if r['mode'] == 'emit']
    out = [
        f'; Generated by Scripts/Generate/joint_palette_directory.py from {SPEC.as_posix()}',
        f'; (sha256 {spec_sha}). Do not edit.',
        '; Joint Sky/ferry palette directory in the granted arena [$1BB6A8,$1BB800).',
        '; read*() sees the INPUT ROM: these checks pin preimages, never emitted bytes.',
        '; Arithmetic is parenthesized: the build uses Asar left-to-right math.',
        f'assert !{FLAG} == 1',
        'JointPalette_ArenaBase = $1BB6A8',
        '',
        '; Input ROM: legacy offset tables match the literal legacy directory words.',
        '!i = 0',
        f'while !i < {MAIN_LEGACY}',
        f'  assert read2(${MAIN_OFFSETS:06X}+(2*!i)) == ({MAIN_SIZE}*!i), "Legacy main palette offsets changed"',
        '  !i #= !i+1',
        'endwhile',
        '!i = 0',
        f'while !i < {AUX_LEGACY}',
        f'  assert read2(${AUX_OFFSETS:06X}+(2*!i)) == ({AUX_SIZE}*!i), "Legacy aux palette offsets changed"',
        '  !i #= !i+1',
        'endwhile',
        '',
        '; Input ROM: native area palette sets 00-9F stay inside the checked set rows.',
        '!i = 0',
        f'while !i < ${MAIN_TABLE_ROWS:02X}',
        f'  assert read1(${AREA_SETS:06X}+!i) < ${SET_ROWS:02X}, "Area palette set is outside the checked set table"',
        '  !i #= !i+1',
        'endwhile',
        '; Input ROM: every aux id the set table can store has a directory record.',
        '!i = 0',
        f'while !i < ${SET_ROWS:02X}',
        f'  assert {reachable_expr(f"read1(${SET_TABLE:06X}+(4*!i))", AUX_LEGACY, aux_ok, True)}, "Set table aux1 reaches a missing palette record"',
        f'  assert {reachable_expr(f"read1(${SET_TABLE:06X}+(4*!i)+1)", AUX_LEGACY, aux_ok, True)}, "Set table aux2 reaches a missing palette record"',
        '  !i #= !i+1',
        'endwhile',
        '; Input ROM: native area main palettes 00-9F. Lyra project areas bind theirs in the Lyra data.',
        '!i = 0',
        f'while !i < ${MAIN_TABLE_ROWS:02X}',
        f'  assert {reachable_expr(f"read1(${MAIN_TABLE:06X}+!i)", MAIN_LEGACY, main_ok, False)}, "Area main palette reaches a missing record"',
        '  !i #= !i+1',
        'endwhile',
        '',
        '; Input ROM: directories and emitted/parked slots are unused; input records match.',
        '!i = 0',
        f'while !i < ${SLOTS[("main", 6)] - ARENA_START:02X}',
        f'  assert read1(${ARENA_START:06X}+!i) == $FF, "Palette directory arena is not free in the input ROM"',
        '  !i #= !i+1',
        'endwhile',
    ]
    for r in records:
        if r['mode'] == 'input':
            for i in range(0, len(r['data']), 2):
                out.append(f'assert read2(${r["address"] + i:06X}) == ${int.from_bytes(r["data"][i:i + 2], "little"):04X}, '
                           f'"Input {label(r["kind"], r["id"])} differs from the bound record"')
    free = [(SLOTS[key], SIZES[key[0]]) for key in parked] + [(r['address'], SIZES[r['kind']]) for r in emitted]
    for start, size in sorted(free):
        out += ['!i = 0', f'while !i < {size}',
                f'  assert read1(${start:06X}+!i) == $FF, "Palette record slot ${start:06X} is not free in the input ROM"',
                '  !i #= !i+1', 'endwhile']
    out += ['', 'pushpc',
            f'org ${MAIN_DIR:06X} ; @hook module=Overworld kind=data name=JointPaletteDirectory '
            f'protected_size={2 * (MAIN_COUNT + AUX_COUNT)}',
            'JointPalette_MainDirectory:',
            '  dw ' + ', '.join(main_words), 'JointPalette_MainDirectoryEnd:',
            'JointPalette_AuxDirectory:']
    for i in range(0, AUX_COUNT, 8):
        out.append('  dw ' + ', '.join(aux_words[i:i + 8]))
    out.append('JointPalette_AuxDirectoryEnd:')
    for r in sorted(records, key=lambda r: r['address']):
        name = label(r['kind'], r['id'])
        if r['mode'] == 'emit':
            out += [f'org ${r["address"]:06X} ; @hook module=Overworld kind=data name={name.replace("_", "")} '
                    f'protected_size={SIZES[r["kind"]]}', f'{name}:  ; {r["why"]}']
            words = [f'${int.from_bytes(r["data"][i:i + 2], "little"):04X}' for i in range(0, len(r['data']), 2)]
            for i in range(0, len(words), 7):
                out.append('  dw ' + ', '.join(words[i:i + 7]))
            out.append(f'{name}_End:')
        else:
            out += [f'{name} = ${r["address"]:06X}  ; input ROM record: {r["why"]}',
                    f'{name}_End = ${r["address"] + SIZES[r["kind"]]:06X}']
    out += ['pullpc', '',
            f'assert JointPalette_MainDirectory == ${MAIN_DIR:06X}',
            f'assert JointPalette_MainDirectoryEnd == ${MAIN_DIR + 2 * MAIN_COUNT:06X}',
            f'assert JointPalette_AuxDirectory == ${AUX_DIR:06X}',
            f'assert JointPalette_AuxDirectoryEnd == ${AUX_DIR + 2 * AUX_COUNT:06X}']
    for r in sorted(records, key=lambda r: r['address']):
        name = label(r['kind'], r['id'])
        out += [f'assert {name} == ${r["address"]:06X}',
                f'assert {name}_End == ${r["address"] + SIZES[r["kind"]]:06X}']
    return '\n'.join(out) + '\n'


def build(spec_path):
    _, records, parked, spec_sha = read_spec(spec_path)
    return asm_text(records, parked, spec_sha)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--root', type=Path, default=Path('.'))
    ap.add_argument('--check', action='store_true', help='fail if the tracked output is stale')
    args = ap.parse_args()
    text = build(args.root / SPEC)
    target = args.root / OUTPUT
    if args.check:
        if not target.exists() or target.read_text() != text:
            print(f'{OUTPUT} is stale; rerun {Path(__file__).name}', file=sys.stderr)
            return 1
        return 0
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(text)
    print(f'wrote {OUTPUT} ({hashlib.sha256(text.encode()).hexdigest()})')
    return 0


if __name__ == '__main__':
    sys.exit(main())
