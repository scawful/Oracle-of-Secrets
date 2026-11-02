#!/usr/bin/env python3
"""Generate narrowly allocated 2bpp HUD icons without writing the editable ROM."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import lz2
from sheet_overrides import require, number, write_outputs
from sheet_table import N, TBL_BANK, TBL_HIGH, TBL_LOW, decomp, pc, ptr

START, CAPACITY = 0x438000, 0x2000
SPEC = Path('Data/graphics/menu_icons.json')
OUTPUT = Path('Core/Generated/menu_icons')
SHEETS = (0x69, 0x6A, 0x6B)
BLANK = 0x07F
TILES = frozenset((0x00D, 0x00E, 0x00F, 0x025, 0x07B, 0x08F,
                   0x0AC, 0x0AF, 0x0F2, 0x130, 0x17E, 0x17F))


def tile_location(tile):
    """Normal HUD loader orders sprite sheets 6A, 6B, 69 at VRAM $7000.w."""
    require(0 <= tile < 0x180, 'tile is outside the normal HUD sheets')
    return (0x6A, 0x6B, 0x69)[tile // 0x80], (tile % 0x80) * 16


def read_spec(path):
    path = Path(path)
    spec = json.loads(path.read_text())
    require(type(spec) is dict and set(spec) == {
        'schema_version', 'start', 'capacity', 'canonical_blank_tile', 'sheets', 'icons'
    }, 'invalid menu icon spec keys')
    require(spec['schema_version'] == 1, 'unsupported menu icon schema')
    require((number(spec['start']), number(spec['capacity'])) == (START, CAPACITY),
            'only audited $43:8000-$43:9FFF is supported')
    require(number(spec['canonical_blank_tile']) == BLANK, 'canonical blank must remain $07F')
    require(type(spec['sheets']) is list and len(spec['sheets']) == 3, 'exactly three HUD sheets required')
    seen = set()
    for entry in spec['sheets']:
        require(type(entry) is dict and set(entry) == {'sprite_sheet', 'base_sha256'}, 'invalid HUD sheet entry')
        sheet = number(entry['sprite_sheet'])
        require(sheet in SHEETS and sheet not in seen, 'unsupported or duplicate HUD sheet')
        seen.add(sheet)
        require(isinstance(entry['base_sha256'], str) and re.fullmatch('[0-9a-f]{64}', entry['base_sha256']),
                'base_sha256 must be a full lowercase SHA256')
    require(type(spec['icons']) is list and len(spec['icons']) == 3, 'exactly three prototype icons required')
    names, allocated = set(), set()
    for entry in spec['icons']:
        require(type(entry) is dict and set(entry) == {'name', 'source', 'tiles', 'palette'}, 'invalid icon entry')
        require(entry['name'] in ('garo_mask', 'bombchu', 'switch_hook') and entry['name'] not in names,
                'unsupported or duplicate icon name')
        names.add(entry['name'])
        require(type(entry['tiles']) is list and len(entry['tiles']) == 4, 'icon must have TL/TR/BL/BR tiles')
        for value in entry['tiles']:
            tile = number(value)
            require(tile != BLANK, 'canonical blank tile cannot be allocated')
            require(tile in TILES and tile not in allocated, 'tile is unapproved or already allocated')
            allocated.add(tile)
        require(0 <= number(entry['palette']) < 8, 'invalid BG3 palette')
        source = Path(entry['source'])
        require(not source.is_absolute() and '..' not in source.parts, 'icon source must stay inside spec directory')
        require((path.parent/source).resolve().is_relative_to(path.parent.resolve()), 'icon source escapes through symlink')
    require(allocated == TILES, 'icon allocation must use the twelve audited tiles exactly')
    return spec


def validate_reservation(root, rom):
    """Check editable bytes, reachable writers, and all existing stream extents."""
    begin, end = pc(START), pc(START) + CAPACITY
    require(not any(rom[begin:end]), 'menu icon allocation is occupied in editable base')
    from generate_hack_manifest import collect_reachable_asm_sources, ORG_BANK_RE
    for source in collect_reachable_asm_sources(root):
        if source.is_relative_to((root/OUTPUT).resolve()):
            continue
        for line in source.read_text().splitlines():
            match = ORG_BANK_RE.match(line.split(';', 1)[0])
            if match:
                address = int(match[1], 16) & 0x7FFFFF
                require(address >> 16 != 0x43, 'another reachable source owns bank $43: '+str(source))
    for global_id in range(N):
        address = ptr(rom, global_id)
        require(address & 0x8000 and (address >> 16 & 0x7F) < 0x7E, 'invalid graphics pointer')
        position = pc(address)
        if 115 <= global_id <= 126:
            length = 0x600
            require(position+length <= len(rom), 'truncated raw graphics sheet')
        else:
            _, length = decomp(rom, address)
        require(not (position < end and begin < position+length), 'existing graphics stream overlaps menu icon allocation')


def build(spec_path, base_rom, root=None):
    spec_path = Path(spec_path)
    spec = read_spec(spec_path)
    rom = Path(base_rom).read_bytes()
    require(len(rom) >= 0x8000 and len(rom) % 0x8000 == 0, 'need unheadered editable LoROM image')
    if root is not None:
        validate_reservation(Path(root).resolve(), rom)
    bases, pointers = {}, {}
    for entry in spec['sheets']:
        sheet = number(entry['sprite_sheet'])
        pointer = ptr(rom, sheet+0x73)
        require(pointer & 0x8000 and (pointer >> 16 & 0x7F) < 0x7E, 'invalid HUD sheet pointer')
        raw, _ = decomp(rom, pointer)
        require(len(raw) == 0x800, 'HUD sheet must decode to exactly 2048 bytes')
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == entry['base_sha256'], f'sheet ${sheet:02X}: base sheet changed ({digest}); re-audit before overriding')
        bases[sheet], pointers[sheet] = raw, pointer
    modified = {sheet: bytearray(raw) for sheet, raw in bases.items()}
    for icon in spec['icons']:
        pixels = (spec_path.parent/icon['source']).read_bytes()
        require(len(pixels) == 64, f'{icon["name"]}: icon must be 64 bytes of SNES 2bpp TL/TR/BL/BR')
        require(any(pixels), f'{icon["name"]}: icon is entirely transparent')
        for quadrant, value in enumerate(icon['tiles']):
            tile = number(value)
            sheet, offset = tile_location(tile)
            require(bases[sheet][offset:offset+16] == bytes(16), f'tile ${tile:03X} is not empty in editable base')
            modified[sheet][offset:offset+16] = pixels[quadrant*16:(quadrant+1)*16]
    sheet, offset = tile_location(BLANK)
    require(modified[sheet][offset:offset+16] == bases[sheet][offset:offset+16] == bytes(16),
            'canonical blank pixels changed or are not transparent')
    out, address = [], START
    for sheet in SHEETS:
        raw = bytes(modified[sheet])
        stream = lz2.compress(raw)
        require(lz2.decompress(stream, max_output=0x800) == (raw, len(stream)), 'compressed HUD round trip differs')
        require(address+len(stream) <= START+CAPACITY, 'menu icon allocation is full')
        out.append(dict(s=sheet, g=sheet+0x73, raw=raw, stream=stream, snes=address,
                        base_pointer=pointers[sheet], base_sha256=hashlib.sha256(bases[sheet]).hexdigest()))
        address += len(stream)
    return spec, out


def generated_files(items):
    lines = ['; GENERATED by Scripts/Generate/menu_icon_overrides.py. Do not edit.',
             '; Three complete 2bpp HUD sheets; only the twelve approved icon tiles differ.',
             '; Canonical transparent tile $07F is preserved.', 'pushpc', 'org $438000']
    for item in items:
        lines.append(f'MenuIconSheet_{item["s"]:02X}: incbin "sheets/spr{item["s"]:02X}.bin"')
    lines.append('assert pc() <= $43A000, "Menu icon sheets exceeded their 8 KiB allocation"')
    for item in items:
        address, old = item['snes'] | 0x800000, item['base_pointer']
        lines += [f'; Sheet ${item["s"]:02X}; decoded base SHA256 {item["base_sha256"]}']
        for table, shift in ((TBL_BANK, 16), (TBL_HIGH, 8), (TBL_LOW, 0)):
            entry = table+item['g']
            lines += [f'assert read1(${entry:06X}) == ${(old >> shift)&255:02X}, "HUD sheet base pointer changed"',
                      f'org ${entry:06X} ; @hook module=Menu kind=data protected_size=1',
                      f'  db ${(address >> shift)&255:02X}',
                      f'assert pc() == ${entry+1:06X}']
    files = {Path('sheets')/f'spr{i["s"]:02X}.bin': i['stream'] for i in items}
    files[Path('menu_icon_overrides.asm')] = ('\n'.join(lines+['pullpc', ''])).encode()
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, nargs='?')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--base-rom', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        spec_path = args.spec or root/SPEC
        spec, items = build(spec_path, args.base_rom, root)
        files, out = generated_files(items), args.out_dir or root/OUTPUT
        stale = [str(name) for name, data in files.items() if not (out/name).is_file() or (out/name).read_bytes() != data]
        if args.check:
            require(not stale, 'stale generated menu icon sheets: '+', '.join(stale))
        else:
            write_outputs(out, files, [args.base_rom, spec_path]+[spec_path.parent/i['source'] for i in spec['icons']])
        print(json.dumps(dict(checked=args.check, sheets=[dict(sprite_sheet=f'{i["s"]:02X}',
                         bytes=len(i['stream']), decoded_sha256=hashlib.sha256(i['raw']).hexdigest()) for i in items])))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print('Menu icon sheets: '+str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
