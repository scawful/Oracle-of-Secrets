"""Lower one reviewed Sky/ferry packet inside the current-save assembler.

The canonical transfer policy binds the packet. This module checks its typed
grants, saved generation and input bytes; it never patches a saved/output ROM.
Palette records retain their existing source producer. Map grids retain Yaze.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_prepare as Q

KIND = 'lyra.joint_art_packet.v1'
SKY_IDS = set(range(0x895, 0x8F3)) | set(range(0x96B, 0x98C)) | set(range(0xF89, 0xFC0))
FERRY_IDS = set(range(0xFE0, 0x1000)) | set(range(0x798, 0x7AE)) | {0x6C7}
PRESENTATION = {0x04C665: '0d', 0x04C6BC: '0f', 0x075538: '101606ff',
                0x075540: '141505ff', 0x1401E7: '06', 0x1408B8: 'df3be0e1e2e3e459'}
SHEET_SPANS = ((0x40E5DB, 0x40E9F0), (0x40E9F0, 0x40EDB9),
               (0x40EDB9, 0x40F0F0), (0x40F0F0, 0x40F3DB),
               (0x40F3DB, 0x40F497), (0x40F497, 0x40F7C5),
               (0x40F7C5, 0x40F982))
AREA_CODE = (0xE2E000, 0xE2E200)
AREA_DATA = (0xE2E200, 0xE2ED79)  # 89 type bytes + 89 * 32 raw CHR bytes
DOCK_RESOURCE = '3fd640ea5f71e4301983dc4944b355f6d8582ea14797605688e5adaf37ffc3b4'


def require_source_profile(profile):
    defines = profile['selected_source']['defines']
    R.require(all(defines.get(name) == 1 for name in (
        'ENABLE_EXPANDED_GRAPHICS_TABLE', 'ENABLE_SOURCE_SPRITE_SHEETS', 'ENABLE_OW_AREA_TILESETS')),
        'JOINT_ART_SOURCE_FEATURES_UNBOUND')


def _keys(value, keys, label):
    R.require(type(value) is dict and set(value) == set(keys), 'Malformed joint art ' + label)


def _hex(value):
    R.require(type(value) is str and value and len(value) % 2 == 0
              and all(c in '0123456789abcdef' for c in value), 'Invalid joint art bytes')
    return bytes.fromhex(value)


def prepare(binding, request, source, *, occupied=()):
    """Return assembler inputs and exact readback rows, without writing files."""
    import lyra_current_transfer as current
    packet = current._json(Q.read_bound(binding))
    _keys(packet, {'kind', 'source_rom_sha256', 'generation', 'operation_id', 'transfer_id',
                   'writes', 'sheets', 'ferry'}, 'packet')
    R.require(packet['kind'] == KIND and packet['source_rom_sha256'] == R.sha(source)
              and type(packet['generation']) is int
              and packet['generation'] == request['live']['generation']
              and packet['operation_id'] == request['live']['operation_id']
              and packet['transfer_id'] == request['transfer_id'], 'JOINT_ART_SAVED_GENERATION_STALE')
    expanded = A.expanded_rom(source)
    atlas = A.pc(int.from_bytes(source[0x865:0x868], 'little'))
    writes, seen = [], set()
    ids = {'sky_tile16': set(), 'ferry_tile16': set()}
    selectors = set()

    def write(at, raw, old):
        R.require(type(at) is int and 0 <= at < at + len(raw) <= len(expanded)
                  and len(raw) == len(old), 'JOINT_ART_WRITE_EXTENT_INVALID')
        span = (at, at + len(raw))
        R.require(not any(span[0] < b and a < span[1] for a, b in [*occupied, *seen]),
                  'JOINT_ART_WRITE_OVERLAP')
        R.require(expanded[at:span[1]] == old, 'JOINT_ART_PREIMAGE_MISMATCH: ' + hex(at))
        seen.add(span)
        writes.append(dict(pc=list(span), payload_hex=raw.hex(), preimage_hex=old.hex()))

    R.require(type(packet['writes']) is list, 'Malformed joint art writes')
    for row in packet['writes']:
        _keys(row, {'role', 'pc', 'preimage_hex', 'payload_hex'}, 'write')
        at = row['pc']; raw = _hex(row['payload_hex']); old = _hex(row['preimage_hex'])
        R.require(type(at) is int, 'Invalid joint art PC address')
        if row['role'] in ids:
            tile, remainder = divmod(at - atlas, 8)
            allowed = SKY_IDS if row['role'] == 'sky_tile16' else FERRY_IDS
            R.require(remainder == 0 and len(raw) == 8 and tile in allowed
                      and tile not in ids[row['role']], 'JOINT_ART_TILE16_OUTSIDE_GRANT')
            ids[row['role']].add(tile)
        else:
            R.require(row['role'] == 'presentation' and at in PRESENTATION
                      and raw.hex() == PRESENTATION[at] and at not in selectors,
                      'JOINT_ART_PRESENTATION_OUTSIDE_GRANT')
            selectors.add(at)
        write(at, raw, old)
    R.require(ids == {'sky_tile16': SKY_IDS, 'ferry_tile16': FERRY_IDS}
              and selectors == set(PRESENTATION), 'JOINT_ART_INCOMPLETE_DEFINITIONS_OR_SELECTORS')

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Generate'))
    import lz2
    R.require(type(packet['sheets']) is list and len(packet['sheets']) == len(SHEET_SPANS),
              'JOINT_ART_SHEETS_INCOMPLETE')
    source_root = Path(__file__).resolve().parents[2]
    inputs = [binding, *[Q.bound(source_root / name) for name in (
        'Data/graphics/joint_palette_directory.json',
        'Core/Generated/joint_palette/directory.asm',
        'Overworld/joint_palette_readers.asm',
        'Scripts/Generate/joint_palette_directory.py',
        'Scripts/Validate/verify_joint_palette_directory.py')]]
    for sheet, (lo, hi), row in zip(range(0xDF, 0xE6), SHEET_SPANS, packet['sheets']):
        _keys(row, {'global_sheet', 'stream', 'decoded_sha256', 'preimage_hex'}, 'sheet')
        R.require(type(row['global_sheet']) is int and row['global_sheet'] == sheet,
                  'JOINT_ART_SHEET_OUTSIDE_GRANT')
        stream = Q.read_bound(row['stream']); decoded, used = lz2.decompress(stream, max_output=0x600)
        R.require(len(stream) == hi - lo and used == len(stream) and len(decoded) == 0x600
                  and R.sha(decoded) == row['decoded_sha256'], 'JOINT_ART_SHEET_PAYLOAD_INVALID')
        write(A.pc(lo), stream, _hex(row['preimage_hex']))
        # The source-owned expanded table first copies native rows, then its
        # four existing sprite overrides. New rows are emitted after both.
        pointer = lo | 0x800000
        for table, byte in ((0x23FD00, pointer >> 16), (0x23FE00, pointer >> 8 & 255),
                            (0x23FF00, pointer & 255)):
            at = A.pc(table + sheet)
            write(at, bytes([byte]), expanded[at:at+1])
        inputs.append(row['stream'])

    ferry = packet['ferry']
    _keys(ferry, {'graphics', 'types', 'native_types_sha256'}, 'ferry')
    graphics, types = Q.read_bound(ferry['graphics']), Q.read_bound(ferry['types'])
    R.require(len(graphics) == 0xB20 and len(types) == 89 and set(types) <= {0, 2, 8},
              'JOINT_ART_FERRY_PAYLOAD_INVALID')
    at = A.pc(0x0E9459)
    R.require(R.sha(source[at:at+512]) == ferry['native_types_sha256'], 'JOINT_ART_NATIVE_TYPES_CHANGED')
    # Fixed same-bank data origin; the source module bounds its code and
    # descriptors before this data, including all four DMA spans.
    raw = types + graphics
    at = A.pc(AREA_DATA[0])
    R.require(len(raw) == AREA_DATA[1] - AREA_DATA[0], 'JOINT_ART_FERRY_DATA_EXTENT_INVALID')
    write(at, raw, expanded[at:at+len(raw)])
    inputs += [ferry['graphics'], ferry['types']]
    binary = bytearray(); lines = ['; Reviewed joint art; saved map grids are not rewritten.', 'pushpc']
    for row in writes:
        raw = bytes.fromhex(row['payload_hex'])
        lines += [f'org ${A.snes(row["pc"][0]):06X}',
                  f'incbin "binaries/joint-art.bin":${len(binary):X}..${len(binary)+len(raw):X}']
        binary.extend(raw)
    lines += ['namespace Oracle', f'FerryArea30Types = ${AREA_DATA[0]:06X}',
              f'FerryArea30TypesEnd = ${AREA_DATA[0]+89:06X}',
              f'FerryArea30Bitmap = ${AREA_DATA[0]+89:06X}',
              f'FerryArea30BitmapEnd = ${AREA_DATA[1]:06X}', 'namespace off', 'pullpc', '']
    constants = ('!JOINT_PALETTE_DIRECTORY_ENABLED = 1\n!LYRA_AREA_TILESETS_BOUND = 1\n'
                 '!LYRA_AREA_FERRY_BOUND = 1\n!LYRA_AREA_TILESETS_ORIGIN = $E2E000\n'
                 '!LYRA_AREA_TILESETS_END = $E30000\n')
    plan = dict(kind=KIND, binding=binding, inputs=inputs, writes=writes,
                source_rom_sha256=R.sha(source), area_code_snes=list(AREA_CODE),
                area_data_snes=list(AREA_DATA), unselected_maps=[0xB6],
                native_gameplay_verified=False)
    return plan, constants, '\n'.join(lines).encode(), bytes(binary)


def verify(plan, compiled, symbols, source_root):
    """Check art/data and source-produced palette bytes in the assembled ROM."""
    import lyra_native_loaders as native
    labels = native._labels(symbols)
    text = symbols.decode() if isinstance(symbols, bytes) else symbols
    import re
    for line in text.splitlines():
        m = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?(\w+)', line)
        if m:
            labels[m[3]] = int(m[1]+m[2], 16)
    for row in plan['writes']:
        a, b = row['pc']
        R.require(compiled[a:b].hex() == row['payload_hex'], 'JOINT_ART_COMPILED_PAYLOAD_MISMATCH')
    for row in plan['inputs']:
        Q.read_bound(row)
    R.require(all(labels.get(name) == address for name, address in (
        ('GfxSheet_Helpers', 0x23FC00), ('GfxSheet_Bank', 0x23FD00),
        ('GfxSheet_High', 0x23FE00), ('GfxSheet_Low', 0x23FF00))),
        'JOINT_ART_EXPANDED_SHEET_READERS_MISSING')
    for site, name, size, bank_store in (
        (0x00D53B, 'GfxSheet_GetPtr_Spr', 17, True),
        (0x00E2D8, 'GfxSheet_GetPtr_Default', 15, False),
        (0x00E462, 'GfxSheet_GetPtr_Spr', 17, True),
        (0x00E6BA, 'GfxSheet_GetPtr_Spr', 15, False),
        (0x00E72E, 'GfxSheet_GetPtr_Spr', 15, False),
        (0x00E772, 'GfxSheet_GetPtr_SprCA', 15, False),
        (0x00E78F, 'GfxSheet_GetPtr_BgCA', 15, False)):
        target = labels.get(name, 0)
        R.require(0x23FC00 <= target < 0x23FD00, 'JOINT_ART_EXPANDED_SHEET_HELPER_INVALID')
        raw = b'\x22' + target.to_bytes(3, 'little')
        if bank_store:
            raw += bytes.fromhex('a5028505')
        raw += b'\xea' * (size - len(raw))
        R.require(compiled[A.pc(site):A.pc(site)+size] == raw,
                  'JOINT_ART_EXPANDED_SHEET_READER_MISMATCH')
    R.require(labels.get('AreaTileset_CodeStart') == AREA_CODE[0]
              and AREA_CODE[0] < labels.get('AreaTileset_CodeEnd', 0) <= AREA_CODE[1]
              and labels.get('FerryArea30Types') == AREA_DATA[0]
              and labels.get('FerryArea30Bitmap') == AREA_DATA[0]+89
              and labels.get('FerryArea30BitmapEnd') == AREA_DATA[1], 'JOINT_ART_AREA_SYMBOLS_INVALID')
    dock = labels.get('SharedGraphicsResource_' + DOCK_RESOURCE, 0)
    R.require(dock and R.sha(compiled[A.pc(dock):A.pc(dock)+0x800]) == DOCK_RESOURCE,
              'JOINT_ART_DOCK_RESOURCE_MISMATCH')
    transfers = ((0x2C00, 0x2000, labels['BoatBitmap']),
                 (0x2C00, 0x0800, dock),
                 (0x3000, 0x0B20, labels['FerryArea30Bitmap']),
                 (0x5000, 0x2000, labels['AdditionalBitmap']))
    descriptors = b''.join(vram.to_bytes(2, 'little') + size.to_bytes(2, 'little')
                           + address.to_bytes(3, 'little') for vram, size, address in transfers) + b'\xff\xff'
    at = A.pc(labels['AreaTileset_FerrySheets'])
    R.require(compiled[at:at+len(descriptors)] == descriptors, 'JOINT_ART_DOCK_DMA_MISMATCH')
    sys.path.insert(0, str(Path(source_root) / 'Scripts/Validate'))
    import verify_joint_palette_directory as palette
    expected, records = palette.expected_arena(Path(source_root) / 'Data/graphics/joint_palette_directory.json')
    for address, value in expected.items():
        R.require(compiled[A.pc(address)] == value, 'JOINT_ART_PALETTE_PAYLOAD_MISMATCH')
    for row in records:
        at = A.pc(row['address'])
        R.require(compiled[at:at+len(row['data'])] == row['data'], 'JOINT_ART_PALETTE_RECORD_MISMATCH')
    for address, kind in {**palette.NATIVE_READERS, labels['JointPalette_ZSMainReader']: 'main'}.items():
        raw = palette.reader(palette.jp.MAIN_DIR if kind == 'main' else palette.jp.AUX_DIR)
        R.require(compiled[A.pc(address):A.pc(address)+7] == raw, 'JOINT_ART_PALETTE_READER_MISMATCH')
    for address in (0x00886E, 0x1BBEFD, 0x1BBF2A, 0x1BC04E):
        R.require(compiled[A.pc(address):A.pc(address)+4] == bytes.fromhex('bf00d07f'),
                  'JOINT_ART_COLLISION_READER_MISMATCH')
    return dict(art_writes_verified=len(plan['writes']), palette_readers_verified=4,
                collision_readers_verified=4, expanded_sheet_readers_verified=7,
                ferry_dock_bytes_verified=0x800, ferry_dma_descriptors_verified=4,
                unselected_maps=plan['unselected_maps'],
                native_gameplay_verified=False)
