#!/usr/bin/env python3
"""Verify assembled joint palette directory bytes against the bound spec.

Asar read*() only sees the input ROM, so emitted directory/record bytes are
proved here: compare a JOINT_PALETTE_DIRECTORY_ENABLED=0 ROM with the =1 ROM
from the same input. Every changed byte must be one of the four 7-byte readers
or the granted arena, and each must equal the spec-derived bytes exactly.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'Scripts/Generate'))
import joint_palette_directory as jp  # noqa: E402

NATIVE_READERS = {0x1BEECE: 'main', 0x1BEEF2: 'aux', 0x1BEF16: 'aux'}
LEGACY = {'main': bytes.fromhex('bf3bec1b69c8e6'), 'aux': bytes.fromhex('bf13ec1b696ce8')}


def pc(snes):
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)


def reader(directory):
    return bytes([0xBF, directory & 0xFF, directory >> 8 & 0xFF, directory >> 16]) + b'\xEA' * 3


def symbol(path, name):
    for line in Path(path).read_text(errors='replace').splitlines():
        match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line.strip())
        if match and match[3] == name:
            return int(match[1], 16) << 16 | int(match[2], 16)
    raise ValueError(f'{name} missing from {path}')


def expected_arena(spec_path):
    _, records, _, _ = jp.read_spec(spec_path)
    main_words, aux_words = jp.directory_words(records)
    slots = {f'{jp.label(k, i)}&$FFFF': a for (k, i), a in jp.SLOTS.items()}
    words = [slots[w] & 0xFFFF if w in slots else int(w[1:], 16) for w in main_words + aux_words]
    expected = {jp.MAIN_DIR + 2 * n + b: w >> 8 * b & 0xFF for n, w in enumerate(words) for b in range(2)}
    for r in records:
        if r['mode'] == 'emit':
            expected.update({r['address'] + n: v for n, v in enumerate(r['data'])})
    return expected, records


def verify(off, on, zs_reader, spec_path):
    errors = []
    require = lambda ok, message: ok or errors.append(message)
    require(len(off) == len(on), 'ROM sizes differ')
    expected, records = expected_arena(spec_path)
    sites = dict(NATIVE_READERS)
    sites[zs_reader] = 'main'
    for site, kind in sorted(sites.items()):
        at = pc(site)
        require(off[at:at + 7] == LEGACY[kind], f'${site:06X} flag-off bytes are not the legacy {kind} reader')
        directory = jp.MAIN_DIR if kind == 'main' else jp.AUX_DIR
        require(on[at:at + 7] == reader(directory), f'${site:06X} flag-on bytes are not LDA.l ${directory:06X},X : NOP #3')
        expected.update({site + n: v for n, v in enumerate(reader(directory))})
    for snes, value in expected.items():
        require(on[pc(snes)] == value, f'${snes:06X} = {on[pc(snes)]:02X}, expected {value:02X}')
    for r in records:
        if r['mode'] == 'input':
            at = pc(r['address'])
            require(on[at:at + len(r['data'])] == r['data'], f'input record ${r["address"]:06X} differs')
    allowed = {pc(s) for s in expected}
    # Full Asar builds recompute the LoROM checksum. Admit only the actual
    # checksum/complement pair, and prove both power-of-two ROM sums first.
    header = slice(0x7FDC, 0x7FE0)
    if off[header] != on[header]:
        for name, image in (('off', off), ('on', on)):
            power_of_two = len(image) >= 0x8000 and len(image) & (len(image)-1) == 0
            inverse = int.from_bytes(image[0x7FDC:0x7FDE], 'little')
            checksum = int.from_bytes(image[0x7FDE:0x7FE0], 'little')
            require(power_of_two and inverse ^ checksum == 0xFFFF
                    and sum(image) & 0xFFFF == checksum,
                    f'{name} ROM checksum/complement is invalid or has an unsupported mirrored size')
        allowed.update(range(header.start, header.stop))
    changed = [n for n in range(min(len(off), len(on))) if off[n] != on[n]]
    stray = [n for n in changed if n not in allowed]
    require(not stray, f'{len(stray)} changed bytes outside readers/arena, first PC ${stray[0]:06X}' if stray else '')
    for n in range(pc(jp.ARENA_START), pc(jp.ARENA_END)):
        snes = 0x1B8000 | n & 0x7FFF
        if snes not in expected and not any(r['mode'] == 'input' and 0 <= snes - r['address'] < len(r['data'])
                                            for r in records):
            require(on[n] == 0xFF, f'unbound arena byte ${snes:06X} is not $FF')
    return [e for e in errors if e], len(changed)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--off', type=Path, required=True, help='ROM assembled with the flag off')
    ap.add_argument('--on', type=Path, required=True, help='ROM assembled with the flag on')
    ap.add_argument('--on-symbols', type=Path, required=True, help='WLA symbols for the flag-on ROM')
    ap.add_argument('--spec', type=Path, default=ROOT / jp.SPEC)
    args = ap.parse_args()
    zs_reader = symbol(args.on_symbols, 'JointPalette_ZSMainReader')
    errors, changed = verify(args.off.read_bytes(), args.on.read_bytes(), zs_reader, args.spec)
    print(json.dumps(dict(ok=not errors, zs_reader=f'${zs_reader:06X}', changed_bytes=changed, errors=errors), indent=2))
    return 1 if errors else 0


if __name__ == '__main__':
    sys.exit(main())
