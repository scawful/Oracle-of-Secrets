#!/usr/bin/env python3
"""Compile room-scoped graphics packages without modifying a ROM.

Usage: room_graphics.py PROFILE --base-rom BASE --out-dir NEW_DIRECTORY
       room_graphics.py PROFILE --base-rom BASE --out-dir DIRECTORY --check

See compile_profile for the strict version-1 contract. Output contains 3bpp/LZ2
sheets, CGRAM row payloads and CustomObjectHandler-compatible patterns. The
bundle records intended scope; it does NOT install loaders, allocate ROM/VRAM,
change collision, bind object IDs, or attach door states to redraw routines.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

import lz2
import sheet_codec
import sheet_table


def require(condition, message):
    if not condition:
        raise ValueError(message)


def fields(value, names):
    require(type(value) is dict and set(value) == set(names.split()),
            'missing or unsupported fields: ' + names)


def integer(value, low, high):
    require(type(value) in (int, str), 'expected integer or 0x-prefixed integer')
    if isinstance(value, str):
        require(re.fullmatch(r'0x[0-9a-fA-F]+', value), 'expected hexadecimal integer')
        value = int(value, 16)
    require(low <= value <= high, f'integer outside {low}..{high}: {value}')
    return value


def identifier(value):
    require(isinstance(value, str) and re.fullmatch(r'[a-z][a-z0-9_]{0,47}', value),
            'identifier must be lowercase ASCII, at most 48 characters')
    return value


def digest(data):
    return hashlib.sha256(data).hexdigest()


def array(value, low, high):
    require(type(value) is list and low <= len(value) <= high,
            f'expected array with {low}..{high} entries')
    return value


def unique_pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key: ' + key)
        result[key] = value
    return result


def load_json(path):
    raw = Path(path).read_bytes()
    require(len(raw) <= 1024 * 1024, 'profile exceeds 1 MiB')
    return json.loads(raw, object_pairs_hook=unique_pairs)


def tile_word(cell):
    """null skips an existing tile; a word explicitly carries palette/flip bits."""
    if cell is None:
        return 0
    value = integer(cell, 0, 0xFFFF)
    require(value != 0, 'word zero skips drawing; use null explicitly')
    require(2 <= (value >> 10 & 7) <= 7, 'BG tile references HUD palette row 0/1')
    require(value & 0x3FF < 0x200, 'pattern references outside eight BG sheet slots')
    return value


def pattern_grid(rows):
    array(rows, 1, 64)
    width = len(array(rows[0], 1, 31))
    require(all(type(row) is list and len(row) == width for row in rows),
            'pattern must be rectangular, at most 31 tiles wide')
    result = [[tile_word(cell) for cell in row] for row in rows]
    require(any(word for row in result for word in row), 'empty pattern')
    return result


def encode_pattern(grid):
    """Native row header: byte stride $80 from row START, low 5 bits count.

    The existing handler decrements before testing count; zero is not a valid
    row length. Zero tile words skip writes (not transparent erasure).
    """
    out = bytearray()
    for row in grid:
        require(1 <= len(row) <= 31, 'native row count must be 1..31')
        out += struct.pack('<H', 0x8000 | len(row))
        for word in row:
            out += struct.pack('<H', word)
    return bytes(out) + b'\0\0'


def decode_pattern(data):
    """Strictly decode existing native streams into (x, y, word) writes.

    Accepts non-$80 jumps used by existing hand-authored objects. Rejects
    ambiguous counts, odd jumps, out-of-buffer writes and trailing bytes.
    """
    cursor = position = 0
    writes = []
    while cursor + 2 <= len(data):
        header, = struct.unpack_from('<H', data, cursor)
        cursor += 2
        if header == 0:
            require(cursor == len(data), 'data after pattern terminator')
            return writes
        count, jump = header & 31, header >> 8
        require(count and header & 0xE0 == 0, 'invalid native count bits')
        require(jump % 2 == 0, 'odd native byte stride')
        require(cursor + count * 2 <= len(data), 'truncated native pattern')
        for index in range(count):
            address = position + index * 2
            require(0 <= address < 0x2000, 'native pattern exceeds tilemap')
            word, = struct.unpack_from('<H', data, cursor)
            cursor += 2
            if word:
                writes.append((address % 128 // 2, address // 128, word))
        position += jump
    raise ValueError('missing pattern terminator')


def source_file(root, value):
    require(isinstance(value, str) and value, 'source path must be nonempty')
    relative = Path(value)
    require(not relative.is_absolute() and '..' not in relative.parts,
            'source must stay inside profile directory')
    path = (root / relative).resolve()
    require(path.is_relative_to(root.resolve()), 'source escapes via symlink')
    require(path.is_file(), 'source file missing: ' + value)
    return path


def rom_context(rom, room, entrance):
    """Resolve Oracle's relocated entrance and native header/group tables."""
    def word(offset):
        return struct.unpack_from('<H', rom, offset)[0]

    def address(value):
        require(value & 0x8000 and (value >> 16 & 0x7F) < 0x7E,
                'invalid LoROM context pointer')
        return sheet_table.pc(value)

    require(word(0x78000 + entrance * 2) == room,
            'entrance does not lead to declared room in Oracle base')
    main = rom[0x79600 + entrance]
    require(main < 37, 'entrance main blockset outside table')
    headers = address(int.from_bytes(rom[0xB5DD:0xB5E0], 'little'))
    header = address(rom[0xB5E7] << 16 | word(headers + room * 2))
    secondary = rom[header + 2]
    require(secondary < 24, 'room collision group outside audited 24-entry table')
    groups = address(word(0x6237))
    bg = list(rom[groups + main * 8:groups + main * 8 + 8])
    require(len(bg) == 8, 'truncated main graphics group')
    for slot in range(3, 7):
        override = rom[0x5D97 + secondary * 4 + slot - 3]
        if override:
            bg[slot] = override
    return main, secondary, bg


def vram_sheet(raw, main, slot):
    """Match LoadBackgroundGraphics / Do3To4{High,Low}16Bit.

    Runtime slot counts backward, so high-half destination blocks are 0..3
    for main groups < $20, otherwise {0,3,4,5}. Zero remains transparent.
    """
    require(len(raw) == 0x600, 'need one 64-tile 3bpp sheet')
    high = slot < 4 if main < 0x20 else slot in (0, 3, 4, 5)
    out = bytearray(0x800)
    for tile in range(64):
        src, dst = tile * 24, tile * 32
        out[dst:dst+16] = raw[src:src+16]
        for row in range(8):
            p0, p1, p2 = raw[src+row*2], raw[src+row*2+1], raw[src+16+row]
            out[dst+16+row*2] = p2
            out[dst+17+row*2] = p0 | p1 | p2 if high else 0
    return bytes(out), 'high' if high else 'low'


def compile_profile(profile_path, base_rom):
    """Compile strict, context-pinned assets; all output is returned in memory.

    Version 1 keys: schema_version, id, base_sha256, context, palette_rows,
    sheets, patterns. Context names room/entrance, main/room blocksets and
    eight BG sheets. Pattern words use native V/H/priority/palette/tile bits.
    Every state has the same footprint and an explicit collision policy.
    No runtime or Yaze configuration is emitted automatically.
    """
    path = Path(profile_path)
    spec = load_json(path)
    fields(spec, 'schema_version id base_sha256 context palette_rows sheets patterns')
    require(type(spec['schema_version']) is int and spec['schema_version'] == 1,
            'unsupported room graphics schema')
    profile_id = identifier(spec['id'])
    rom = Path(base_rom).read_bytes()
    require(len(rom) >= 0x80000 and len(rom) % 0x8000 == 0,
            'need an unheadered editable LoROM image')
    require(spec['base_sha256'] == digest(rom), 'base ROM fingerprint changed')
    ctx = spec['context']
    fields(ctx, 'room entrance main_blockset room_blockset bg_sheets')
    room = integer(ctx['room'], 0, 0x127)
    entrance = integer(ctx['entrance'], 0, 0x84)
    main = integer(ctx['main_blockset'], 0, 36)
    # Oracle collision-offset table has 24 entries. Larger editor group counts
    # do not establish collision support; the v1 contract preserves this group.
    secondary = integer(ctx['room_blockset'], 0, 23)
    bg = [integer(v, 0, 0x70) for v in array(ctx['bg_sheets'], 8, 8)]
    actual = rom_context(rom, room, entrance)
    require(actual[0] == main, 'entrance main blockset differs')
    require(actual[1] == secondary, 'room header blockset differs')
    require(actual[2] == bg, 'resolved background sheet slots differ')
    files, palette_meta, sheet_meta, pattern_meta = {}, [], [], []
    seen = set()
    for palette in array(spec['palette_rows'], 0, 6):
        fields(palette, 'row colors')
        row = integer(palette['row'], 2, 7)
        require(row not in seen, 'duplicate palette row')
        seen.add(row)
        colors = [integer(c, 0, 0x7FFF) for c in array(palette['colors'], 15, 15)]
        name = f'palettes/row_{row}.bin'
        files[name] = struct.pack('<15H', *colors)
        palette_meta.append(dict(row=row, first_color=1, file=name))
    if seen == set(range(2, 8)):
        files['palettes/dungeon_main.bin'] = b''.join(
            files[f'palettes/row_{row}.bin'] for row in range(2, 8))
    seen = set()
    inputs = {path.resolve(), Path(base_rom).resolve()}
    for sheet in array(spec['sheets'], 0, 8):
        fields(sheet, 'slot source base_sha256')
        slot = integer(sheet['slot'], 0, 7)
        require(slot not in seen, 'duplicate BG slot')
        seen.add(slot)
        pointer = sheet_table.ptr(rom, bg[slot])
        require(pointer & 0x8000 and (pointer >> 16 & 0x7F) < 0x7E,
                'invalid background graphics pointer')
        original, _ = sheet_table.decomp(rom, pointer)
        require(len(original) == 0x600 and digest(original) == sheet['base_sha256'],
                'decoded base background sheet changed')
        source = source_file(path.parent, sheet['source'])
        inputs.add(source)
        require(source.suffix in ('.txt', '.png'), 'sheet source must be .txt or indexed .png')
        grid = (sheet_codec.png_to_grid(source) if source.suffix == '.png'
                else sheet_codec.text_to_grid(source.read_text()))
        raw = sheet_codec.grid_to_sheet(grid)
        compressed = lz2.compress(raw)
        require(lz2.decompress(compressed, max_output=0x600) == (raw, len(compressed)),
                'sheet compression roundtrip failed')
        name = f'sheets/slot_{slot}'
        files[name + '.3bpp'] = raw
        files[name + '.lz2'] = compressed
        files[name + '.vram4bpp'], conversion = vram_sheet(raw, main, slot)
        sheet_meta.append(dict(slot=slot, base_sheet=bg[slot], first_tile=slot*64,
                               source_sha256=digest(source.read_bytes()),
                               raw=name+'.3bpp', compressed=name+'.lz2',
                               vram=name+'.vram4bpp', palette_half=conversion,
                               identity=(raw == original)))
    seen = set()
    for pattern in array(spec['patterns'], 1, 128):
        fields(pattern, 'id kind collision states')
        name = identifier(pattern['id'])
        require(name not in seen, 'duplicate pattern id')
        seen.add(name)
        require(pattern['kind'] in ('object', 'door_frame'), 'unknown pattern kind')
        require(pattern['collision'] in ('preserve_existing', 'requires_overlay'),
                'explicit collision policy required')
        states, state_names, dimensions = [], set(), None
        for state in array(pattern['states'], 1, 32):
            fields(state, 'name rows')
            state_name = identifier(state['name'])
            require(state_name not in state_names, 'duplicate state name')
            state_names.add(state_name)
            grid = pattern_grid(state['rows'])
            extent = (len(grid[0]), len(grid))
            require(dimensions in (None, extent), 'states must share a footprint')
            dimensions = extent
            data = encode_pattern(grid)
            expected = [(x,y,w) for y,row in enumerate(grid) for x,w in enumerate(row) if w]
            require(decode_pattern(data) == expected, 'native pattern roundtrip differs')
            file = f'patterns/{name}/{state_name}.bin'
            files[file] = data
            states.append(dict(name=state_name, file=file))
        pattern_meta.append(dict(id=name, kind=pattern['kind'],
                                 collision=pattern['collision'], width=dimensions[0],
                                 height=dimensions[1], states=states,
                                 runtime_binding_required=True))
    metadata = dict(schema_version=1, id=profile_id, base_sha256=digest(rom),
                    profile_sha256=digest(path.read_bytes()),
                    context=dict(room=room, entrance=entrance, main_blockset=main,
                                 room_blockset=secondary, bg_sheets=bg),
                    stage='compiled_assets_unbound', runtime_installed=False,
                    palette_dependencies=['BG rows 2..7 share one room palette',
                                          'first seven dungeon colors also feed OBJ environment half-row',
                                          'native high/low expansion depends on main blockset and destination slot',
                                          'palette animation consumers must be checked before runtime binding'],
                    palette_rows=palette_meta, sheets=sheet_meta, patterns=pattern_meta,
                    files={n:dict(bytes=len(d), sha256=digest(d)) for n,d in files.items()})
    files['bundle.json'] = (json.dumps(metadata, indent=2) + '\n').encode()
    return files, inputs


def publish(out, files, inputs, check=False):
    """Only create a new directory; never overwrite an existing asset package."""
    out = Path(out)
    require(not out.is_symlink(), 'output directory cannot be a symlink')
    require(not out.resolve().name.lower().endswith(('.sfc', '.smc')),
            'output must be a directory, not a ROM path')
    require(all(out.resolve() != p and out.resolve() not in p.parents for p in inputs),
            'output aliases or contains an input')
    if check:
        require(out.is_dir(), 'output package missing')
        present = {p.relative_to(out).as_posix() for p in out.rglob('*') if p.is_file()}
        require(present == set(files), 'output file set differs')
        for name, data in files.items():
            p = out / name
            require(not p.is_symlink() and p.read_bytes() == data, 'stale output: ' + name)
        return
    require(not out.exists(), 'output already exists; use a new directory or --check')
    out.mkdir(parents=True, exist_ok=False)
    for name, data in files.items():
        destination = out / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open('xb') as stream:
            stream.write(data)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('profile', type=Path)
    parser.add_argument('--base-rom', type=Path, required=True)
    parser.add_argument('--out-dir', type=Path, required=True)
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args(argv)
    try:
        files, inputs = compile_profile(args.profile, args.base_rom)
        publish(args.out_dir, files, inputs, args.check)
    except (OSError, ValueError, KeyError, IndexError, struct.error) as error:
        print(f'room graphics: {error}', file=sys.stderr)
        return 1
    print(f'{"Checked" if args.check else "Compiled"} {len(files)} files: {args.out_dir}; runtime binding pending')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
