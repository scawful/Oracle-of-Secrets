"""Native special-overworld data lowering, shared by initial import and Build.

The filename retains the searchable Lyra alias. These are format operations for
the shared special overworld, not region membership or an alternate publisher.
Table and actor lowering is for one-time import only. Ordinary Build must read
the saved directory and emit reader constants without regenerating its payload.

The current-mode family layout and actor packing come from retained606; the
historical pilot, sidecar publisher and admission framework are not dependencies.
"""
from __future__ import annotations

from dataclasses import dataclass
import argparse
from pathlib import Path
import struct
import sys
import zlib

import native_overworld_authoring_metadata as authoring_metadata


FIRST_TAIL_MAP = 0xA0
MAP_CAPACITY = 0xC0
DIRECTORY_PC = 0x147000
DIRECTORY_SIZE = 1024
MAGIC = b'OOSOW192'
TABLE_BASE = 0x468000
BINDINGS_BASE = 0x46B180
CODE_BASE = 0x46C000
CODE_LIMIT = 0x470000
ACTORS_BASE = 0x4C8000
# Selected source reservations for initial native appearance import. Generic
# directory codecs still require caller-supplied entries; these constants do
# not write, expand or activate a ROM. Bank47 belongs to graphics sheets DF-FE.
APPEARANCE_FLAGS_BASE = 0x4D8000
APPEARANCE_PALETTES_BASE = 0x4D8100
AUTHORING_METADATA_BASE = 0x4DD000
RESIDENT_DATA_PC = 0x270000
RESIDENT_DATA_CAPACITY = 0x10000

# Existing dictionaries in the selected Oracle engine. Initial import reuses
# these owned bodies; arbitrary relocation needs a separately bound reader ABI.
CURRENT_DICTIONARIES = {400: 0x3D8000, 401: 0x038000, 402: 0x048000,
                        403: 0x3E8000, 404: 0x3F8000}
TILE16_LONG_READERS = (
    (0x008865, 0), (0x0EDE4F, 0), (0x0EDEE9, 0),
    (0x1BBC2D, 2), (0x1BBC4C, 0), (0x1BBCC2, 4), (0x1BBCCB, 6),
    (0x1BBEF6, 0), (0x1BBF23, 0), (0x1BC041, 0),
    (0x1BC9B3, 0), (0x1BC9BA, 2), (0x1BC9C1, 4), (0x1BC9C8, 6),
    (0x1BCA40, 0), (0x1BCA47, 2), (0x1BCA4E, 4), (0x1BCA55, 6),
    (0x02F457, 0), (0x02F45E, 2), (0x02F467, 4), (0x02F46E, 6),
    (0x02F51F, 0), (0x02F526, 4), (0x02F52F, 2), (0x02F536, 6),
)
TILE32_LONG_READERS = tuple(
    (401 + quadrant, operand + quadrant * 0x40, offset)
    for quadrant in range(4)
    for operand, offset in ((0x02F6AC, 0), (0x02F6B3, 1), (0x02F6BA, 2),
                            (0x02F6C1, 3), (0x02F6C8, 4), (0x02F6DA, 5)))
TILE16_WORD_READERS = ((0x02FE1C, 0), (0x02FE23, 4),
                       (0x02FE2C, 2), (0x02FE33, 6))
TILE16_BANK_READERS = (0x02FD28, 0x02FD39)

# name, native SNES table, native row count, native first map, row stride.
# Compact special tables have structural zero prefixes in the expanded copy;
# their original readers continue to own the existing native maps.
CURRENT_TABLE_SPECS = (
    ('bg_color', 0x288000, 160, 0, 2),
    ('main_palette', 0x288160, 160, 0, 1),
    ('mosaic', 0x288200, 160, 0, 1),
    ('animated', 0x2882A0, 160, 0, 1),
    ('overlay', 0x288340, 160, 0, 2),
    ('gfx', 0x288480, 160, 0, 8),
    ('parent', 0x288998, 160, 0, 1),
    ('ByScreen1', 0x288A38, 160, 0, 2),
    ('ByScreen2', 0x288B78, 160, 0, 2),
    ('ByScreen3', 0x288CB8, 160, 0, 2),
    ('ByScreen4', 0x288DF8, 160, 0, 2),
    ('transition_y', 0x288F38, 160, 0, 2),
    ('transition_x', 0x289078, 160, 0, 2),
    ('scroll_north', 0x2891B8, 160, 0, 2),
    ('scroll_west', 0x2892F8, 160, 0, 2),
    ('sprite_phase0', 0x289438, 160, 0, 2),
    ('sprite_phase1', 0x289578, 160, 0, 2),
    ('sprite_phase2', 0x2896B8, 160, 0, 2),
    ('sign_text', 0x2897F8, 160, 0, 2),
    ('map32_high', 0x02F94D, 160, 0, 3),
    ('map32_low', 0x02FB2D, 160, 0, 3),
    ('bomb_doors', 0x02A644, 160, 0, 2),
    ('hidden_items', 0x02A784, 160, 0, 2),
    ('special_sprite_gfx', 0x02E6E1, 32, 128, 1),
    ('special_sprite_palettes', 0x02E701, 32, 128, 1),
    ('area_gfx', 0x00FC9C, 160, 0, 1),
    ('special_entry_gfx', 0x02E821, 32, 128, 1),
    ('music_dark_special', 0x02C403, 96, 64, 1),
    ('area_size', 0x02F88D, 160, 0, 1),
    ('palette_set', 0x09C635, 160, 0, 1),
) + tuple((f'music_phase{i}', 0x02C303 + i * 0x40, 64, 0, 1)
          for i in range(4)) + (
    ('special_sprite_gfx_phase1', 0x02E6E1, 32, 128, 1),
    ('special_sprite_palettes_phase1', 0x02E701, 32, 128, 1),
    ('special_sprite_palettes_phase2', 0x02E701, 32, 128, 1),
    ('special_sprite_gfx_phase2', 0x02E6E1, 32, 128, 1),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def pc(snes):
    require(type(snes) is int and 0 <= snes <= 0xFFFFFF
            and snes & 0x8000 and snes >> 16 not in (0x7E, 0x7F),
            'Expected a mapped LoROM address')
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)


@dataclass(frozen=True)
class Family:
    id: int
    name: str
    legacy_snes: int
    legacy_rows: int
    legacy_first: int
    stride: int
    snes: int


def current_table_layout(table_base):
    """Return the retained full192-row ABI plus appended role metadata.

    This does not allocate the supplied address. The caller owns the selected
    source/ledger composition. A160 conversion needs its own runtime producer.
    """
    pc(table_base)
    result, cursor = [], table_base
    for index, (name, old, rows, first, stride) in enumerate(CURRENT_TABLE_SPECS):
        # ID29 is metadata; retained physical family order stays unchanged.
        entry_id = index + 1 if index < 28 else index + 2
        result.append(Family(entry_id, name, old, rows, first, stride, cursor))
        cursor += MAP_CAPACITY * stride
    result.append(Family(29, 'role', 0, 0, 0, 1, cursor))
    cursor += MAP_CAPACITY
    require((table_base & 0xFFFF) + cursor - table_base <= 0x10000,
            'Native tables cross a LoROM bank')
    return tuple(result)


def initial_appearance_entries(capacity):
    """Return the selected410/411 extents, without allocating or writing."""
    require(type(capacity) is int and capacity in (160, 192),
            'Expected160 or192 materialized maps')
    return ((410, APPEARANCE_FLAGS_BASE, capacity),
            (411, APPEARANCE_PALETTES_BASE, 64))


def initial_authoring_entry(capacity):
    """Return the selected412 extent; caller supplies its validated payload."""
    require(type(capacity) is int and capacity in (160, 192),
            'Expected160 or192 materialized maps')
    return 412, AUTHORING_METADATA_BASE, 256


def _row_bytes(value, stride, name):
    if stride == 8:
        require(type(value) in (bytes, list, tuple) and len(value) == 8
                and all(type(v) is int and 0 <= v <= 255 for v in value),
                f'Invalid explicit {name} row')
        return bytes(value)
    require(type(value) is int and 0 <= value < 1 << (stride * 8),
            f'Invalid explicit {name} row')
    return value.to_bytes(stride, 'little')


def _validate_tail_areas(rows):
    for map_id, row in rows.items():
        parent, size = row['parent'], row['area_size']
        require(type(parent) is int and FIRST_TAIL_MAP <= parent < MAP_CAPACITY
                and type(size) is int and 0 <= size <= 3,
                f'Invalid explicit parent/size for map {map_id:02X}')
        width, height = (2 if size in (1, 2) else 1), (2 if size in (1, 3) else 1)
        require(parent % 8 + width <= 8 and parent + (height - 1) * 8 + width <= MAP_CAPACITY,
                f'Area footprint leaves tail storage for map {map_id:02X}')
        children = {parent + y * 8 + x for y in range(height) for x in range(width)}
        require(map_id in children and all(rows[child]['parent'] == parent
                and rows[child]['area_size'] == size for child in children),
                f'Inconsistent explicit area footprint for map {map_id:02X}')


def lower_tables(source, tail_rows, *, table_base, legacy_roles):
    """Lower every explicit tail row once, preserving native table payload.

    Returned bytes are an import candidate, not a complete ROM or runtime proof.
    Unknown roles may be explicitly FF; absent gameplay grouping is an error.
    """
    require(type(source) is bytes and 0x200000 <= len(source) <= 0x400000,
            'Expected a complete headerless saved ROM')
    require(read_native_directory(source) is None,
            'Existing expanded data must not be regenerated by initial import')
    layout = current_table_layout(table_base)
    names = {family.name for family in layout}
    require(type(tail_rows) is dict and all(type(k) is int for k in tail_rows)
            and set(tail_rows) == set(range(FIRST_TAIL_MAP, MAP_CAPACITY)),
            'Initial import requires all32 explicit tail maps')
    require(all(type(row) is dict and set(row) == names for row in tail_rows.values()),
            'Each tail map requires every explicit table family and role')
    require(type(legacy_roles) in (bytes, list, tuple) and len(legacy_roles) == FIRST_TAIL_MAP
            and all(type(v) is int and (0 <= v <= 3 or v == 255) for v in legacy_roles),
            'Expected160 explicit preserved roles or unspecified FF values')
    _validate_tail_areas(tail_rows)
    tables = {}
    for family in layout:
        payload = bytearray(MAP_CAPACITY * family.stride)
        if family.name == 'role':
            payload[:FIRST_TAIL_MAP] = bytes(legacy_roles)
        else:
            start, length = pc(family.legacy_snes), family.legacy_rows * family.stride
            require(start + length <= len(source), 'Truncated native table')
            first = family.legacy_first * family.stride
            payload[first:first + length] = source[start:start + length]
            if family.name.startswith('music_phase'):
                other = pc(0x02C403)
                payload[0x40:FIRST_TAIL_MAP] = source[other:other + 0x60]
        for map_id, row in tail_rows.items():
            value = row[family.name]
            if family.name == 'role':
                require(type(value) is int and (0 <= value <= 3 or value == 255),
                        'Invalid explicit tail role')
            if family.name.startswith('map32_'):
                pc(value)
            start = map_id * family.stride
            payload[start:start + family.stride] = _row_bytes(value, family.stride, family.name)
        tables[family.id] = bytes(payload)
    return tables


def lower_actor_lists(streams, *, data_snes, capacity):
    """Pack actual headerless lists for all32 maps and all three phases.

    Parent aggregation belongs to the authored-data importer, before this seam.
    No missing stream becomes an empty list and no native bank09 data changes.
    """
    pc(data_snes)
    require(type(capacity) is int and capacity > 0
            and (data_snes & 0xFFFF) + capacity <= 0x10000,
            'Actor storage requires one explicit mapped bank extent')
    expected = {(map_id, phase) for map_id in range(FIRST_TAIL_MAP, MAP_CAPACITY)
                for phase in range(3)}
    require(type(streams) is dict and set(streams) == expected
            and all(type(k) is tuple and all(type(v) is int for v in k) for k in streams),
            'Expected every tail map and actor phase explicitly')
    payload, offsets, pointers = bytearray(), {}, {}
    for key in sorted(expected):
        raw = streams[key]
        require(type(raw) is bytes and raw and raw[-1] == 0xFF
                and len(raw) % 3 == 1 and len(raw) <= 128 * 3 + 1
                and all(raw[i] != 0xFF for i in range(0, len(raw) - 1, 3)),
                'Actor lists require at most128 complete triples and a final terminator')
        if raw not in offsets:
            require(len(payload) + len(raw) <= capacity,
                    'Actor lists exceed the selected storage extent')
            offsets[raw] = len(payload)
            payload.extend(raw)
        pointers[key] = (data_snes + offsets[raw]) & 0xFFFF
    return bytes(payload), pointers


def entry_spec(entry_id, capacity, revision=3):
    require(revision in (3, 4), 'Unsupported native source revision')
    strides = (2, 1, 1, 1, 2, 8, 1, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 2, 3,
               3, 2, 2, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1, 1)
    if 1 <= entry_id <= 39:
        return 1, capacity, strides[entry_id - 1]
    if entry_id == 100:
        return 2, None, 1
    if 200 <= entry_id <= 202:
        return 3, (0x7E70, 0x411F, 0x8000)[entry_id - 200], 1
    if 210 <= entry_id <= 213:
        return 3, 0x8000, 1
    if entry_id == 300:
        return 5, None, 1
    if entry_id == 301:
        return 6, None, 16
    if entry_id == 400:
        return 7, 4096, 8
    if 401 <= entry_id <= 404:
        return 7, 4432, 6
    if revision == 4 and entry_id == 410:
        return 8, capacity, 1
    if revision == 4 and entry_id == 411:
        return 8, 64, 256
    if revision == 4 and entry_id == 412:
        return 9, 256, 32
    raise ValueError('Unknown native directory entry')


def encode_revision3_directory(image, entries, *, tail_actor_bank, capacity=MAP_CAPACITY):
    """Encode the revision3 directory over an already materialized candidate.

    Each entry is (id, SNES address, count). This checks storage structure and
    CRCs only; the existing Yaze inspector must validate readers/decoded data
    before an import candidate can be used for normal editing or runtime.
    """
    return _encode_native_directory(image, entries, tail_actor_bank=tail_actor_bank,
                                    capacity=capacity, revision=3)


def encode_revision4_directory(image, entries, *, tail_actor_bank, capacity=MAP_CAPACITY):
    """Seal authored page appearance, without granting runtime resources.

    The caller supplies already owned, materialized payload extents. This
    function neither selects free space nor activates a runtime consumer.
    """
    return _encode_native_directory(image, entries, tail_actor_bank=tail_actor_bank,
                                    capacity=capacity, revision=4)


def _encode_native_directory(image, entries, *, tail_actor_bank, capacity, revision):
    require(revision in (3, 4), 'Unsupported native source revision')
    require(type(image) is bytes and 0x200000 <= len(image) <= 0x400000,
            'Expected a complete headerless candidate image')
    require(type(capacity) is int and capacity in (160, 192)
            and type(tail_actor_bank) is int and 0 <= tail_actor_bank <= 255
            and tail_actor_bank not in (0x7E, 0x7F), 'Invalid native capacity or actor bank')
    expected = set(range(1, 40)) | {100, 200, 201, 202, 210, 211, 212, 213,
                                 300, 301, 400, 401, 402, 403, 404}
    if revision == 4:
        expected |= {410, 411}
    authoring = revision == 4 and any(row[0] == 412 for row in entries)
    if authoring:
        expected.add(412)
    require(len(entries) == len(expected) and {row[0] for row in entries} == expected,
            f'Expected exactly{len(expected)} unique native directory entries')
    directory = bytearray(DIRECTORY_SIZE)
    directory[:8] = MAGIC
    struct.pack_into('<6HBBHII', directory, 8, revision, 32, 32 + 16 * len(entries),
                     capacity, capacity, len(entries), tail_actor_bank,
                     0x0C if revision == 3 else (0x3C if authoring else 0x1C),
                     2 * capacity, len(image), 0)
    spans = [(DIRECTORY_PC, DIRECTORY_PC + DIRECTORY_SIZE)]
    for index, (entry_id, address, count) in enumerate(sorted(entries)):
        require(type(entry_id) is int, 'Directory IDs must be integers')
        kind, fixed_count, stride = entry_spec(entry_id, capacity, revision)
        require(type(count) is int and 0 < count <= 65535
                and (fixed_count is None or count == fixed_count), 'Invalid directory count')
        start, length = pc(address), count * stride
        require((address & 0xFFFF) + length <= 0x10000 and start + length <= len(image),
                'Directory entry leaves its mapped bank or candidate image')
        require(all(start >= end or start + length <= begin for begin, end in spans),
                'Native directory entries overlap')
        if 200 <= entry_id <= 202:
            require(start == (0x58000, 0x60000, 0x130000)[entry_id - 200],
                    'Original terrain pool moved')
        if 210 <= entry_id <= 213:
            require(address & 0xFFFF == 0x8000, 'Writable terrain pool must begin at bank8000')
        if entry_id == 100:
            require(address >> 16 == tail_actor_bank, 'Actor directory bank mismatch')
        if entry_id == 410:
            flags = image[start:start + length]
            require(not any(flags[:128])
                    and all(value in (0, 1, 3) for value in flags),
                    'Invalid native physical-page appearance flags')
        if entry_id == 411:
            require(all(word <= 0x7FFF for word in struct.unpack('<8192H', image[start:start + length])),
                    'Invalid native BGR555 appearance color')
        if entry_id == 412:
            authoring_metadata.decode(image[start:start + length], capacity)
        spans.append((start, start + length))
        struct.pack_into('<HHIHHI', directory, 32 + index * 16, entry_id, kind,
                         address, count, stride, zlib.crc32(image[start:start + length]))
    struct.pack_into('<I', directory, 0x1C, zlib.crc32(directory))
    return bytes(directory)


def read_native_directory(image):
    """Read and CRC-check installed storage without lowering authored payload.

    Semantic terrain/parent/actor validation remains the editor inspector's
    responsibility. This is the Build seam, not a second editor admission API.
    Absent descriptors retain the ordinary160 build. Attributed older or broken
    descriptors fail instead of being mistaken for ordinary native storage.
    """
    raw = image[DIRECTORY_PC:DIRECTORY_PC + DIRECTORY_SIZE]
    if len(raw) < DIRECTORY_SIZE:
        require(not raw.startswith(b'OOSOW'), 'Truncated special-overworld directory')
        return None
    fingerprint = ((raw[8:14], raw[18:20]) in (
        (b'\x03\x00\x20\x00\x80\x03', b'\x36\x00'),
        (b'\x04\x00\x20\x00\xA0\x03', b'\x38\x00'),
        (b'\x04\x00\x20\x00\xB0\x03', b'\x39\x00')))
    if not raw.startswith(b'OOSOW') and not fingerprint:
        return None
    require(raw[:8] == MAGIC and struct.unpack_from('<H', raw, 8)[0] in (3, 4),
            'Ordinary Build requires the installed revision3 or revision4 special-overworld format')
    revision, header_size, used_size, capacity, materialized, count, bank, flags, stride, size, _ = (
        struct.unpack_from('<6HBBHII', raw, 8))
    authoring = revision == 4 and flags & 0x20 != 0
    expected_count, expected_flags = ((54, 0x0C) if revision == 3 else
                                      (57, 0x3C) if authoring else (56, 0x1C))
    require(header_size == 32 and used_size == 32 + expected_count * 16 and count == expected_count
            and materialized == capacity and flags == expected_flags and stride == 2 * capacity
            and size == len(image), 'Invalid installed native directory header')
    entries = []
    for index in range(count):
        entry_id, kind, address, rows, width, crc = struct.unpack_from('<HHIHHI', raw, 32 + index * 16)
        expected_kind, _, expected_width = entry_spec(entry_id, capacity, revision)
        require(kind == expected_kind and width == expected_width, 'Installed directory ABI differs')
        entries.append((entry_id, address, rows))
    # Re-encoding checks every span/CRC, unique ID, reserved byte and header CRC.
    expected = _encode_native_directory(image, entries, tail_actor_bank=bank,
                                        capacity=capacity, revision=revision)
    # Directory record order is not an ABI; normalize only the record order.
    normalized = bytearray(raw)
    normalized[32:used_size] = b''.join(sorted(
        (raw[start:start + 16] for start in range(32, used_size, 16)),
        key=lambda record: struct.unpack_from('<H', record)[0]))
    normalized[28:32] = bytes(4)
    original_crc, = struct.unpack_from('<I', raw, 28)
    original = bytearray(raw)
    original[28:32] = bytes(4)
    require(zlib.crc32(original) == original_crc, 'Installed directory CRC differs')
    struct.pack_into('<I', normalized, 28, zlib.crc32(normalized))
    require(bytes(normalized) == expected, 'Installed directory payload CRC or padding differs')
    require(image[0x140145] == 3 and image[0x1423FF] != 0xEA,
            'Native special overworld conflicts with the installed ZS layout')
    return capacity, bank, {entry_id: (address, rows) for entry_id, address, rows in entries}


def read_revision3_directory(image):
    """Compatibility entry point for callers requiring the revision3 ABI."""
    result = read_native_directory(image)
    require(result is None or struct.unpack_from('<H', image, DIRECTORY_PC + 8)[0] == 3,
            'This caller requires the installed revision3 special-overworld format')
    return result


def require_native_runtime_resources(image):
    # Revision4 stores editable source intent. The retained revision3 renderer
    # does not implement physical-page profiles/full BG128; never publish it as
    # a current runnable build while that compiler/consumer is unavailable.
    require(struct.unpack_from('<H', image, DIRECTORY_PC + 8)[0] == 3,
            'Native per-page appearance requires resident resource compilation; '
            'this Build cannot publish revision4 source as runnable output')


def verify_dictionary_readers(image, entries):
    """Bind the first producer to all56 existing dictionary operand sites.

    Locations below are operand addresses, with their opcode immediately
    before them. Compare mapped addresses so legitimate FastROM aliases work.
    The four active custom entrance reads use the emitted Map16 constant.
    """
    for entry_id, expected in CURRENT_DICTIONARIES.items():
        require(pc(entries[entry_id][0]) == pc(expected),
                f'Native dictionary ID{entry_id} differs from this engine profile')
    readers = tuple((400, address, offset) for address, offset in TILE16_LONG_READERS)
    for entry_id, address, offset in readers + TILE32_LONG_READERS:
        at = pc(address)
        require(at + 3 <= len(image) and image[at - 1] == 0xBF,
                f'Native dictionary reader opcode changed at {address:06X}')
        actual = int.from_bytes(image[at:at + 3], 'little')
        require(pc(actual) == pc(entries[entry_id][0] + offset),
                f'Native dictionary reader operand disagrees at {address:06X}')
    target = entries[400][0]
    for address in TILE16_BANK_READERS:
        at = pc(address)
        require(at < len(image) and image[at - 1] == 0xA9
                and pc((image[at] << 16) | 0x8000) == pc(target),
                f'Native Tile16 bank reader disagrees at {address:06X}')
    for address, offset in TILE16_WORD_READERS:
        at = pc(address)
        require(at + 2 <= len(image) and image[at - 1] == 0xB9
                and int.from_bytes(image[at:at + 2], 'little')
                == ((target + offset) & 0xFFFF),
                f'Native Tile16 word reader disagrees at {address:06X}')


def reader_constants(image):
    """Emit constants only: never org/db/incbin or a saved data body.

    The retained runtime is192 only. Legacy160 needs no conversion and a
    revision3/160 image is refused until a corresponding engine is implemented.
    """
    installed = read_native_directory(image)
    if installed is None:
        return '; Ordinary160-map source path.\n!SPECIAL_OVERWORLD_NATIVE = 0\n'
    require_native_runtime_resources(image)
    capacity, bank, entries = installed
    require(capacity == MAP_CAPACITY, 'Retained native readers require192 materialized maps')
    require(all(entries[family.id][0] == family.snes
                for family in current_table_layout(TABLE_BASE))
            and entries[300][0] == CODE_BASE and entries[300][1] <= CODE_LIMIT - CODE_BASE
            and entries[301][0] == BINDINGS_BASE
            and entries[301][1] * 16 <= CODE_BASE - BINDINGS_BASE
            and entries[100][0] == ACTORS_BASE and entries[100][1] <= 0x8000
            and all(entries[210 + i] == (((0x48 + i) << 16) | 0x8000, 0x8000)
                    for i in range(4)),
            'Installed native layout differs from this engine\'s selected ROM reservations')
    verify_dictionary_readers(image, entries)
    lines = ['; Generated from the saved ROM; contains no authored data.',
             '!SPECIAL_OVERWORLD_NATIVE = 1', '!LYRA_CURRENT_MODE = 1',
             f'!SPECIAL_OVERWORLD_DIRECTORY_CRC = ${struct.unpack_from("<I", image, DIRECTORY_PC + 28)[0]:08X}',
             '!LYRA_CURRENT_FIRST = $00A0', '!LYRA_CURRENT_END = $00C0',
             '!LYRA_CURRENT_PARENT_COUNT = $00C0',
             '!LYRA_CURRENT_ACTORS_ENABLED = 1', '!LYRA_CURRENT_ACTORS_BOUND = 1',
             f'!LYRA_CURRENT_MAP16_DEFINITIONS = ${CURRENT_DICTIONARIES[400]:06X}',
             '!LYRA_CURRENT_EVENTS_ENABLED = 1', '!LYRA_CURRENT_EVENTS_BOUND = 1',
             '!LYRA_CURRENT_EVENT_BASE = $7EF4C0',
             '!LYRA_CURRENT_EVENT_VERSION = $7EF4E0', '!LYRA_CURRENT_EVENT_MARKER = $A1',
             f'!LYRA_CURRENT_ACTOR_BANK = ${bank:02X}']
    for family in current_table_layout(TABLE_BASE):
        if family.id != 29:
            lines.append(f'!LYRA_CURRENT_TABLE_{family.name} = ${entries[family.id][0]:06X}')
    code, code_bytes = entries[300]
    require((code & 0xFFFF) + code_bytes <= 0x10000, 'Reader code leaves its bank')
    lines += [f'!LYRA_CURRENT_CODE_BASE = ${code:06X}',
              f'!LYRA_CURRENT_CODE_END = ${code + code_bytes:06X}']
    return '\n'.join(lines) + '\n'


def verify_saved_payload(source, compiled):
    """Refuse assembly that replaces any installed ROM-owned payload.

    Reader code/bindings are also immutable for this initial integration. A
    future intentional reader update must reseal and revalidate them explicitly.
    """
    installed = read_native_directory(source)
    if installed is None:
        require(read_native_directory(compiled) is None,
                'Normal Build cannot install an unrequested native directory')
        return
    require_native_runtime_resources(source)
    require(len(source) == len(compiled), 'Native Build changed the saved image extent')
    require(source[DIRECTORY_PC:DIRECTORY_PC + DIRECTORY_SIZE]
            == compiled[DIRECTORY_PC:DIRECTORY_PC + DIRECTORY_SIZE],
            'Build replaced the saved native directory')
    capacity, _, entries = installed
    verify_dictionary_readers(source, entries)
    for entry_id, (address, count) in entries.items():
        _, _, stride = entry_spec(entry_id, capacity)
        start, length = pc(address), count * stride
        require(source[start:start + length] == compiled[start:start + length],
                f'Build replaced saved native payload ID{entry_id}')
    for entry_id, start in ((20, 0x1794D), (21, 0x17B2D)):
        address, _ = entries[entry_id]
        authoritative = source[pc(address):pc(address) + FIRST_TAIL_MAP * 3]
        require(source[start:start + len(authoritative)] == authoritative,
                'Saved native pointer mirrors disagree')
        require(compiled[start:start + len(authoritative)] == authoritative,
                'Build replaced saved native pointer mirrors')
    # Existing maps still use the original native property/actor slots. The
    # directory copies alone are not proof that an edited prefix survives
    # assembly. Keep every native family at its exact saved bytes as well.
    for name, address, rows, _, stride in CURRENT_TABLE_SPECS:
        if name in ('map32_high', 'map32_low'):
            continue  # Their authoritative copied-prefix equality is above.
        start, length = pc(address), rows * stride
        require(source[start:start + length] == compiled[start:start + length],
                f'Build replaced saved native prefix {name}')
    # Binding records are unchanged, so each installed call must still match.
    address, count = entries[301]
    for index in range(count):
        start = pc(address) + index * 16
        site, target, table_id, kind, reserved = struct.unpack_from('<IIHBB', source, start)
        instruction = source[start + 12:start + 16]
        require(table_id in range(1, 40) and table_id != 29 and 1 <= kind <= 5
                and reserved == 0 and instruction[0] in (0x22, 0x5C)
                and int.from_bytes(instruction[1:], 'little') == target,
                'Saved native reader binding is invalid')
        code, length = entries[300]
        require(pc(code) <= pc(target) < pc(code) + length
                and (site & 0xFFFF) + 4 <= 0x10000,
                'Saved native reader target or site leaves its bound extent')
        site_pc = pc(site)
        require(source[site_pc:site_pc + 4] == instruction
                and compiled[site_pc:site_pc + 4] == instruction,
                'Build changed an installed native reader call')
    read_revision3_directory(compiled)
    verify_dictionary_readers(compiled, entries)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom', required=True, type=Path)
    modes = parser.add_mutually_exclusive_group(required=True)
    modes.add_argument('--constants', type=Path)
    modes.add_argument('--compiled', type=Path)
    args = parser.parse_args(argv)
    try:
        source = args.rom.read_bytes()
        if args.constants is not None:
            text = reader_constants(source)
            require(args.constants.resolve() != args.rom.resolve()
                    and not (args.constants.exists() and args.constants.samefile(args.rom)),
                    'Constants must not overwrite the ROM')
            args.constants.parent.mkdir(parents=True, exist_ok=True)
            args.constants.write_text(text)
        else:
            verify_saved_payload(source, args.compiled.read_bytes())
    except (ValueError, OSError) as error:
        print(f'Native special overworld: {error}', file=sys.stderr)
        return 1
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
