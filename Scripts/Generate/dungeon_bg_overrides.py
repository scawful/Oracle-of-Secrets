#!/usr/bin/env python3
"""Generate audited 3bpp dungeon BG sheet overrides without writing the editable ROM."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

import lz2
import sheet_codec
from sheet_overrides import number, require, write_outputs
from sheet_table import N, NEW_BANK, NEW_HIGH, NEW_LOW, TBL_BANK, TBL_HIGH, TBL_LOW, decomp, pc, ptr

START, CAPACITY = 0x5D8000, 0x2000
SPEC = Path('Data/graphics/dungeon_bg_sheets.json')
OUTPUT = Path('Core/Generated/dungeon_bg_sheets')
# $07/$1F/$22 are the original audited sheets. $1C is house slot 6 (low
# palette half): the timber kettle's four glyphs live on its blank tiles
# $30-$33 so palette 3 uses the silver/gold half instead of slot 3's dark half.
SHEETS = (0x07, 0x1F, 0x22, 0x1C)


def _decode_3bpp_sheet(rom: bytes, global_id: int) -> tuple[bytes, int]:
    pointer = ptr(rom, global_id)
    require(pointer & 0x8000 and ((pointer >> 16) & 0x7F) < 0x7E,
            f'invalid BG sheet ${global_id:02X} pointer')
    raw, _ = decomp(rom, pointer)
    require(len(raw) == 0x600, f'BG sheet ${global_id:02X} must decode to exactly 1536 bytes')
    return raw, pointer


def _parse_rows(rows: list[str], width: int, height: int, context: str) -> list[list[int]]:
    require(isinstance(rows, list) and len(rows) == height,
            f'{context}: expected {height} pixel rows')
    out = []
    for row in rows:
        require(isinstance(row, str) and len(row) == width and all(c in '.01234567' for c in row),
                f'{context}: row must be {width} chars of . or 0-7')
        out.append([0 if c == '.' else int(c) for c in row])
    return out


def _read_grid_16x16(path: Path, context: str) -> list[list[int]]:
    lines = [ln for ln in path.read_text().splitlines() if ln and not ln.startswith('#')]
    return _parse_rows(lines, 16, 16, context)


def _tile_slice(grid: list[list[int]], tile: int) -> list[list[int]]:
    tx, ty = (tile % 16) * 8, (tile // 16) * 8
    return [grid[ty + y][tx:tx + 8] for y in range(8)]


def _set_tile(grid: list[list[int]], tile: int, block: list[list[int]]) -> None:
    tx, ty = (tile % 16) * 8, (tile // 16) * 8
    for y in range(8):
        grid[ty + y][tx:tx + 8] = block[y]


def read_spec(path: Path) -> dict:
    path = Path(path)
    spec = json.loads(path.read_text())
    require(type(spec) is dict and set(spec) == {
        'schema_version', 'start', 'capacity', 'sheets', 'patches'
    }, 'invalid dungeon BG sheet spec keys')
    require(spec['schema_version'] == 1, 'unsupported dungeon BG sheet schema')
    require((number(spec['start']), number(spec['capacity'])) == (START, CAPACITY),
            'only audited $5D:8000-$5D:9FFF is supported')
    require(type(spec['sheets']) is list and len(spec['sheets']) == len(SHEETS),
            'expected exactly four audited BG sheets')
    seen_sheets = set()
    for entry in spec['sheets']:
        require(type(entry) is dict and set(entry) == {'global_sheet', 'base_sha256'},
                'invalid BG sheet entry')
        gid = number(entry['global_sheet'])
        require(gid in SHEETS and gid not in seen_sheets, 'unsupported or duplicate BG sheet')
        seen_sheets.add(gid)
        require(isinstance(entry['base_sha256'], str)
                and re.fullmatch('[0-9a-f]{64}', entry['base_sha256']),
                'base_sha256 must be a full lowercase SHA256')
    require(seen_sheets == set(SHEETS), 'spec must cover sheets 0x07, 0x1F, 0x22, 0x1C')
    require(type(spec['patches']) is list and spec['patches'], 'patches list required')

    allocated: set[tuple[int, int]] = set()
    seen_names: set[str] = set()
    for patch in spec['patches']:
        require(type(patch) is dict and 'name' in patch and 'kind' in patch and 'sheet' in patch,
                'invalid patch entry')
        name = patch['name']
        require(isinstance(name, str) and name and name not in seen_names, f'duplicate or empty patch name: {name!r}')
        seen_names.add(name)
        gid = number(patch['sheet'])
        require(gid in seen_sheets, f'{name}: sheet ${gid:02X} not declared in sheets')
        kind = patch['kind']
        if kind == 'grid_16x16':
            require(set(patch) == {'name', 'kind', 'sheet', 'source', 'tiles', 'require_blank'},
                    f'{name}: invalid grid_16x16 fields')
            src = Path(patch['source'])
            require(not src.is_absolute() and '..' not in src.parts,
                    f'{name}: source must stay inside spec directory')
            require((path.parent / src).resolve().is_relative_to(path.parent.resolve()),
                    f'{name}: source escapes through symlink')
            require(isinstance(patch['tiles'], list) and len(patch['tiles']) == 4,
                    f'{name}: expected 4 TL/TR/BL/BR tile indices')
            for val in patch['tiles']:
                tile = number(val)
                require(0 <= tile < 64 and (gid, tile) not in allocated,
                        f'{name}: invalid or duplicate tile ${tile:02X}')
                allocated.add((gid, tile))
        elif kind == 'base_tile_copy':
            require(set(patch) == {
                'name', 'kind', 'sheet', 'source_sheet', 'source_base_sha256',
                'source_tiles', 'tiles', 'require_blank'
            }, f'{name}: invalid base_tile_copy fields')
            src_gid = number(patch['source_sheet'])
            require(0 <= src_gid < N, f'{name}: source_sheet out of range')
            require(isinstance(patch['source_base_sha256'], str)
                    and re.fullmatch('[0-9a-f]{64}', patch['source_base_sha256']),
                    f'{name}: invalid source_base_sha256')
            require(isinstance(patch['source_tiles'], list)
                    and isinstance(patch['tiles'], list)
                    and len(patch['source_tiles']) == len(patch['tiles'])
                    and len(patch['tiles']) > 0,
                    f'{name}: source_tiles and tiles must match non-empty length')
            for val in patch['source_tiles']:
                require(0 <= number(val) < 64, f'{name}: invalid source tile')
            for val in patch['tiles']:
                tile = number(val)
                require(0 <= tile < 64 and (gid, tile) not in allocated,
                        f'{name}: invalid or duplicate tile ${tile:02X}')
                allocated.add((gid, tile))
        elif kind == 'tile_8x8':
            require(set(patch) == {'name', 'kind', 'sheet', 'tile', 'expected_rows', 'rows'},
                    f'{name}: invalid tile_8x8 fields')
            tile = number(patch['tile'])
            require(0 <= tile < 64 and (gid, tile) not in allocated,
                    f'{name}: invalid or duplicate tile ${tile:02X}')
            allocated.add((gid, tile))
            _parse_rows(patch['expected_rows'], 8, 8, f'{name}.expected_rows')
            _parse_rows(patch['rows'], 8, 8, f'{name}.rows')
        else:
            raise ValueError(f'{name}: unsupported patch kind {kind!r}')
    return spec


def validate_reservation(root: Path, rom: bytes) -> None:
    """Ensure bank $5D allocation is unoccupied and unowned by other reachable ASM."""
    begin, end = pc(START), pc(START) + CAPACITY
    require(end <= len(rom) and not any(rom[begin:end]),
            'dungeon BG allocation $5D:8000-$5D:9FFF is occupied in editable base')
    from generate_hack_manifest import ORG_BANK_RE, collect_reachable_asm_sources
    for source in collect_reachable_asm_sources(root):
        if source.is_relative_to((root / OUTPUT).resolve()):
            continue
        for line in source.read_text().splitlines():
            match = ORG_BANK_RE.match(line.split(';', 1)[0])
            if match:
                address = int(match[1], 16) & 0x7FFFFF
                require(address >> 16 != 0x5D,
                        'another reachable source owns bank $5D: ' + str(source))


def build(spec_path: Path, base_rom: Path, root: Path | None = None) -> tuple[dict, list[dict]]:
    spec_path = Path(spec_path)
    spec = read_spec(spec_path)
    rom = Path(base_rom).read_bytes()
    require(len(rom) >= 0x300000 and len(rom) % 0x8000 == 0,
            'need unheadered expanded LoROM image')
    if root is not None:
        validate_reservation(Path(root).resolve(), rom)

    bases: dict[int, bytes] = {}
    pointers: dict[int, int] = {}
    grids: dict[int, list[list[int]]] = {}
    for entry in spec['sheets']:
        gid = number(entry['global_sheet'])
        raw, pointer = _decode_3bpp_sheet(rom, gid)
        digest = hashlib.sha256(raw).hexdigest()
        require(digest == entry['base_sha256'],
                f'sheet ${gid:02X}: base sheet changed ({digest}); re-audit before overriding')
        bases[gid] = raw
        pointers[gid] = pointer
        grids[gid] = sheet_codec.sheet_to_grid(raw)

    for patch in spec['patches']:
        name = patch['name']
        gid = number(patch['sheet'])
        grid = grids[gid]
        base_raw = bases[gid]
        kind = patch['kind']
        if kind == 'grid_16x16':
            full = _read_grid_16x16(spec_path.parent / patch['source'], name)
            quads = [
                [row[:8] for row in full[:8]],
                [row[8:] for row in full[:8]],
                [row[:8] for row in full[8:]],
                [row[8:] for row in full[8:]],
            ]
            for val, quad in zip(patch['tiles'], quads):
                tile = number(val)
                if patch['require_blank']:
                    require(base_raw[tile * 24:(tile + 1) * 24] == bytes(24),
                            f'{name}: target tile ${gid:02X}:${tile:02X} is not blank in base')
                _set_tile(grid, tile, quad)
        elif kind == 'base_tile_copy':
            src_gid = number(patch['source_sheet'])
            src_raw, _ = _decode_3bpp_sheet(rom, src_gid)
            src_sha = hashlib.sha256(src_raw).hexdigest()
            require(src_sha == patch['source_base_sha256'],
                    f'{name}: source sheet ${src_gid:02X} changed ({src_sha})')
            src_grid = sheet_codec.sheet_to_grid(src_raw)
            for s_val, d_val in zip(patch['source_tiles'], patch['tiles']):
                s_tile, d_tile = number(s_val), number(d_val)
                if patch['require_blank']:
                    require(base_raw[d_tile * 24:(d_tile + 1) * 24] == bytes(24),
                            f'{name}: target tile ${gid:02X}:${d_tile:02X} is not blank in base')
                _set_tile(grid, d_tile, _tile_slice(src_grid, s_tile))
        elif kind == 'tile_8x8':
            tile = number(patch['tile'])
            expected = _parse_rows(patch['expected_rows'], 8, 8, f'{name}.expected_rows')
            actual = _tile_slice(grid, tile)
            require(actual == expected,
                    f'{name}: base tile ${gid:02X}:${tile:02X} pixels do not match audited baseline')
            _set_tile(grid, tile, _parse_rows(patch['rows'], 8, 8, f'{name}.rows'))

    out: list[dict] = []
    address = START
    for gid in SHEETS:
        raw = sheet_codec.grid_to_sheet(grids[gid])
        stream = lz2.compress(raw)
        require(lz2.decompress(stream, max_output=0x600) == (raw, len(stream)),
                f'compressed BG sheet ${gid:02X} round trip differs')
        require(address + len(stream) <= START + CAPACITY,
                'dungeon BG allocation $5D:8000-$5D:9FFF is full')
        out.append(dict(
            g=gid,
            raw=raw,
            stream=stream,
            snes=address,
            base_pointer=pointers[gid],
            base_sha256=hashlib.sha256(bases[gid]).hexdigest(),
        ))
        address += len(stream)
    return spec, out


def generated_files(items: list[dict]) -> dict[Path, bytes]:
    lines = [
        '; GENERATED by Scripts/Generate/dungeon_bg_overrides.py. Do not edit.',
        '; Four audited 3bpp dungeon BG sheets ($07, $1F, $22, $1C) in bank $5D.',
        'pushpc',
        f'org ${START:06X}',
    ]
    for item in items:
        lines.append(f'DungeonBgSheet_{item["g"]:02X}: incbin "sheets/bg{item["g"]:02X}.bin"')
    lines.append(
        f'assert pc() <= ${START + CAPACITY:06X}, "Dungeon BG sheets exceeded 8 KiB bank $5D slot"'
    )
    lines += [
        'if not(defined("GfxSheet_TableDone"))',
        '  error "bg_sheet_overrides.asm must follow Core/gfx_sheet_table.asm"',
        'endif',
    ]
    for item in items:
        address, old = item['snes'] | 0x800000, item['base_pointer']
        lines.append(f'; Global BG sheet ${item["g"]:02X}; decoded base SHA256 {item["base_sha256"]}')
        for table, new, shift in ((TBL_BANK, NEW_BANK, 16), (TBL_HIGH, NEW_HIGH, 8), (TBL_LOW, NEW_LOW, 0)):
            entry, row = table + item['g'], new + item['g']
            lines += [
                f'assert read1(${entry:06X}) == ${(old >> shift) & 255:02X}, "Dungeon BG sheet base pointer changed"',
                f'org ${row:06X} ; @hook module=Dungeons kind=data protected_size=1',
                f'  db ${(address >> shift) & 255:02X}',
                f'assert pc() == ${row + 1:06X}',
            ]
    files = {Path('sheets') / f'bg{i["g"]:02X}.bin': i['stream'] for i in items}
    files[Path('bg_sheet_overrides.asm')] = ('\n'.join(lines + ['pullpc', ''])).encode()
    return files


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('spec', type=Path, nargs='?')
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument('--base-rom', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    root = args.root.resolve()
    try:
        spec_path = args.spec or root / SPEC
        spec, items = build(spec_path, args.base_rom, root)
        files, out = generated_files(items), args.out_dir or root / OUTPUT
        stale = [
            str(name)
            for name, data in files.items()
            if not (out / name).is_file() or (out / name).read_bytes() != data
        ]
        if args.check:
            require(not stale, 'stale generated dungeon BG sheets: ' + ', '.join(stale))
        else:
            sources = [args.base_rom, spec_path] + [
                spec_path.parent / p['source']
                for p in spec['patches']
                if 'source' in p
            ]
            write_outputs(out, files, sources)
        print(json.dumps(dict(
            checked=args.check,
            sheets=[dict(
                global_sheet=f'{i["g"]:02X}',
                bytes=len(i['stream']),
                decoded_sha256=hashlib.sha256(i['raw']).hexdigest(),
            ) for i in items],
        )))
        return 0
    except (OSError, ValueError, KeyError, TypeError, IndexError) as error:
        print('Dungeon BG sheets: ' + str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
