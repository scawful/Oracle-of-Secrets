"""Lower packed special-overworld terrain to resident lookup and upload data.

Retains the606 native ABI algorithms, generalized to materialized special maps
and sparse area selection. This module performs no I/O or ROM allocation.
Lyra symbol names remain aliases for the retained assembly consumers.
"""
from __future__ import annotations

import copy
import re
import struct

from special_overworld_resources import (
    ANIMATED_SLOTS, PLAN_SCHEMA, STATIC_SLOTS,
    _digest, _json_bytes, _payload, _require, _sha,
)

NATIVE_KIND = 'special_overworld.resident_abi.v1'
NATIVE_ABI_VERSION = 1
NATIVE_DIRECTORY_STRIDE = 8
NATIVE_ANIMATION_DIRECTORY_STRIDE = 11
NATIVE_PALETTE_DIRECTORY_STRIDE = 3
NATIVE_PALETTE_DIRECTORY_LABEL = 'SpecialOverworldPaletteDirectory'
NATIVE_BLOCK_SHIFT = 5
NATIVE_BLOCK_DIRECTORY_BYTES = 128
FIRST = 0x80
TRANSFER_CONSTANTS = {
    'ABIVersion': 1, 'HeaderSize': 22, 'NormalCount': 0, 'NormalPtr': 2,
    'CacheMask': 4, 'TransitionMode': 5, 'TransitionStart': 6, 'TransitionEnd': 8,
    'TransitionSource': 10, 'StagingCount': 13, 'StagingPtr': 15,
    'LateFirst': 17, 'LateEnd': 18, 'LateSource': 19,
    'NormalRecordSize': 7, 'StagingRecordSize': 8,
    'ModeNone': 0, 'ModeRange': 1, 'ModeStart': 2, 'ModeNative': 3,
}


def _checked_areas(areas, end):
    _require(type(areas) is list and len(areas) <= end - FIRST,
             'NATIVE_AREAS_INVALID')
    seen = set()
    for area in areas:
        _require(type(area) is dict and type(area.get('parent_map_id')) is int
                 and type(area.get('maps')) is list and area['maps']
                 and area.get('size') in ('small', 'large', 'wide', 'tall'),
                 'NATIVE_AREAS_INVALID')
        parent = area['parent_map_id']
        width, height = dict(small=(1, 1), large=(2, 2), wide=(2, 1), tall=(1, 2))[area['size']]
        maps = area['maps']
        _require(FIRST <= parent < end and parent % 8 + width <= 8
                 and maps == [parent + y * 8 + x for y in range(height) for x in range(width)]
                 and all(type(page) is int and FIRST <= page < end and page not in seen for page in maps),
                 'NATIVE_AREA_FOOTPRINT_INVALID')
        seen.update(maps)
    return seen

def _native_blob(raw, label, role):
    return dict(label=label, role=role, **_payload(raw))


def _native_static_runs(tile_count):
    """Describe the exact resident prefix in the existing native sheet buffers."""
    _require(type(tile_count) is int and 0 <= tile_count <= len(STATIC_SLOTS),
             'NATIVE_STATIC_EXTENT_INVALID')
    runs = []
    native_bases = (0x7F2000, 0x7F2800, 0x7F3000, 0x7F0000,
                    0x7F0800, 0x7F1000, 0x7F1800, 0x7F3800)
    for index, slot in enumerate(STATIC_SLOTS[:tile_count]):
        sheet, tile_in_sheet = divmod(slot, 64)
        record = dict(source_offset=index * 32, byte_count=32,
                      vram_word_address=0x2000 + slot * 16,
                      wram_address=native_bases[sheet] + tile_in_sheet * 32,
                      native_sheet=sheet)
        previous = runs[-1] if runs else None
        if previous is not None and previous['native_sheet'] == sheet and all(
                previous[key] + previous['byte_count'] // divisor == record[key]
                for key, divisor in (('source_offset', 1), ('vram_word_address', 2),
                                     ('wram_address', 1))):
            previous['byte_count'] += 32
        else:
            runs.append(record)
    return runs


def _verified_payload(value):
    _require(type(value) is dict and type(value.get('payload_hex')) is str,
             'NATIVE_PAYLOAD_INVALID')
    try:
        raw = bytes.fromhex(value['payload_hex'])
    except ValueError as error:
        raise ValueError('RESIDENT_GRAPHICS_NATIVE_PAYLOAD_INVALID') from error
    _require(type(value.get('byte_count')) is int and len(raw) == value['byte_count']
             and value.get('sha256') == _sha(raw), 'NATIVE_PAYLOAD_MISMATCH')
    return raw


def plan_native_resident_abi(resident_plan, *, tile16_count):
    """Lower authenticated terrain data to relocatable, unselected native ABI.

    Each physical page has a 128-byte block directory followed by 32-byte
    leaves. A nonzero block/row index is one-based; row zero means that the
    terrain census did not qualify this Tile16. It does not prove resource
    closure. Target word zero is valid. Areas share resources, never page keys.
    """
    _require(type(resident_plan) is dict and resident_plan.get('schema') == PLAN_SCHEMA
             and resident_plan.get('terrain_plan_ready') is True,
             'NATIVE_TERRAIN_PLAN_REQUIRED')
    _require(type(tile16_count) is int and 0 < tile16_count <= 4096,
             'NATIVE_TILE16_COUNT_INVALID')
    supplied = resident_plan.get('plan_sha256')
    _require(_digest(supplied) and supplied == _sha(_json_bytes(
        {key: value for key, value in resident_plan.items() if key != 'plan_sha256'})),
        'NATIVE_SOURCE_PLAN_MISMATCH')
    _require(all(resident_plan.get(key) is False for key in (
        'full_residency_ready', 'allocation_granted', 'ordinary_build_ready')), 'NATIVE_SOURCE_AUTHORITY_INVALID')
    end = resident_plan.get('materialized_map_count')
    _require(type(end) is int and end in (160, 192), 'NATIVE_MAP_CAPACITY_INVALID')
    source_areas = resident_plan.get('areas')
    _checked_areas(source_areas, end)
    pages, areas, blobs, unique = [], [], [], {}

    def blob(raw, label, role):
        # Role separation keeps a resource from aliasing executable lookup data.
        key = (role, raw)
        if key not in unique:
            unique[key] = label
            blobs.append(_native_blob(raw, label, role))
        return unique[key]

    for area_index, area in enumerate(sorted(source_areas, key=lambda row: row['parent_map_id'])):
        parent = area['parent_map_id']
        _require(area.get('terrain_plan_ready') is True and area.get('refusals') == []
                 and type(area.get('remaps')) is list, 'NATIVE_AREA_UNQUALIFIED')
        prefix = f'LyraResidentArea_{parent:02X}'
        static = _verified_payload(area.get('static_chr'))
        palette = _verified_payload(area.get('palette'))
        animation = area.get('animation')
        _require(type(animation) is dict and animation.get('frame_count') == 3
                 and type(animation.get('frame_payloads')) is list
                 and len(animation['frame_payloads']) == 3, 'NATIVE_ANIMATION_INVALID')
        frames = [_verified_payload(value) for value in animation['frame_payloads']]
        slots = area.get('static_slots')
        animated_slots = animation.get('slots')
        _require(type(slots) is list and slots == list(STATIC_SLOTS[:len(slots)])
                 and len(slots) <= len(STATIC_SLOTS) and len(static) == len(slots) * 32
                 and type(animated_slots) is list
                 and animated_slots == list(ANIMATED_SLOTS[:len(animated_slots)])
                 and len(animated_slots) <= 32
                 and all(len(raw) == len(animated_slots) * 32 for raw in frames)
                 and len(palette) == 256, 'NATIVE_RESOURCE_EXTENT_INVALID')
        palette_words = area['palette'].get('words')
        _require(type(palette_words) is list and len(palette_words) == 128
                 and all(type(word) is int and 0 <= word <= 0x7FFF for word in palette_words)
                 and palette == struct.pack('<128H', *palette_words),
                 'NATIVE_PALETTE_INVALID')
        static_label = blob(static, prefix + '_Static', 'static_chr') if static else None
        palette_label = blob(palette, prefix + '_Palette', 'palette')
        frame_labels = [blob(raw, prefix + f'_Frame{index}', 'animation') if raw else None
                        for index, raw in enumerate(frames)]
        runs = _native_static_runs(len(slots))
        areas.append(dict(area_index=area_index, parent_map_id=parent, size=area['size'],
            maps=list(area['maps']), static_label=static_label, static_runs=runs,
            palette_label=palette_label, palette_byte_count=256,
            palette_consumer='ProjectBGPalette native reference/effective/tint lifecycle',
            animation_labels=frame_labels, animation_byte_count=len(frames[0]),
            animation_wram=[0x7EA680, 0x7EAA80, 0x7EAE80],
            animation_vram_word_address=0x3C00, native_animation_upload_byte_count=0x400))
        page_rows = {page: {} for page in area['maps']}
        for remap in area['remaps']:
            _require(type(remap) is dict and set(remap) == {
                'map_id', 'tile16_id', 'quadrant', 'source_word', 'target_word'},
                'NATIVE_REMAP_INVALID')
            page, tile, quadrant = (remap[name] for name in ('map_id', 'tile16_id', 'quadrant'))
            _require(type(page) is int and page in page_rows
                     and type(tile) is int and 0 <= tile < tile16_count
                     and type(quadrant) is int and 0 <= quadrant < 4
                     and all(type(remap[name]) is int and 0 <= remap[name] <= 0xFFFF
                             for name in ('source_word', 'target_word')), 'NATIVE_REMAP_INVALID')
            quadrants = page_rows[page].setdefault(tile, {})
            _require(quadrant not in quadrants, 'NATIVE_REMAP_DUPLICATE')
            quadrants[quadrant] = remap['target_word']
        for page, rows in sorted(page_rows.items()):
            _require(0 < len(rows) and all(set(values) == set(range(4))
                     for values in rows.values()), 'NATIVE_ROWS_OR_QUADRANTS_INVALID')
            _require(len(rows) <= 255, 'NATIVE_ROW_CAPACITY_EXCEEDED')
            directory, leaves, words = bytearray(128), bytearray(), bytearray(8)
            leaf_rows = {}
            for row_index, (tile, quadrants) in enumerate(sorted(rows.items()), 1):
                block, offset = divmod(tile, 32)
                leaf_rows.setdefault(block, bytearray(32))[offset] = row_index
                words.extend(struct.pack('<4H', *(quadrants[q] for q in range(4))))
            for block_index, (block, raw) in enumerate(sorted(leaf_rows.items()), 1):
                directory[block] = block_index
                leaves.extend(raw)
            index = bytes(directory + leaves)
            index_label = blob(index, f'LyraResidentPageIndex_{page:02X}', 'page_index')
            words_label = blob(bytes(words), f'LyraResidentPageWords_{page:02X}', 'page_words')
            pages.append(dict(map_id=page, area_index=area_index, row_count=len(rows),
                block_count=len(leaf_rows), index_label=index_label, words_label=words_label,
                index_alias=f'LyraResidentPageIndex_{page:02X}',
                words_alias=f'LyraResidentPageWords_{page:02X}', tile16_ids=sorted(rows)))
    pages.sort(key=lambda row: row['map_id'])
    counts = {role: sum(row['byte_count'] for row in blobs if row['role'] == role)
              for role in ('page_index', 'page_words', 'static_chr', 'animation', 'palette')}
    counts['page_directory'] = (end - FIRST) * NATIVE_DIRECTORY_STRIDE
    counts['animation_directory'] = (end - FIRST) * NATIVE_ANIMATION_DIRECTORY_STRIDE
    result = dict(kind=NATIVE_KIND, abi_version=NATIVE_ABI_VERSION,
        source_plan_sha256=supplied, materialized_map_count=end, tile16_count=tile16_count,
        directory_label='LyraResidentPageDirectory', directory_stride=NATIVE_DIRECTORY_STRIDE,
        animation_directory_label='LyraResidentAnimationDirectory',
        animation_directory_stride=NATIVE_ANIMATION_DIRECTORY_STRIDE,
        block_shift=NATIVE_BLOCK_SHIFT, block_directory_bytes=NATIVE_BLOCK_DIRECTORY_BYTES,
        first_map=FIRST, end_map=end, row_limit=255, pages=pages, areas=areas, blobs=blobs,
        byte_counts=counts, unaligned_byte_count=sum(counts.values()),
        consumer_status=dict(page_word_lookup='source_abi_only',
            main_chr_staging_implemented=False, palette_lifecycle_implemented=False,
            animation_lifecycle_implemented=False, resource_closure_verified=False),
        unknowns=copy.deepcopy(resident_plan['unknowns']),
        missing_row_semantics='unqualified native fallback; resource closure remains unknown',
        selected=False, allocation_granted=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, compiled_consumers_verified=False)
    result['abi_sha256'] = _sha(_json_bytes(result))
    return result


def validate_native_resident_abi(native_plan):
    """Check independently consumable lookup bytes and their semantic page rows."""
    _require(type(native_plan) is dict and native_plan.get('kind') == NATIVE_KIND
             and native_plan.get('abi_version') == NATIVE_ABI_VERSION
             and native_plan.get('abi_sha256') == _sha(_json_bytes({
                 key: value for key, value in native_plan.items() if key != 'abi_sha256'})),
             'NATIVE_ABI_MISMATCH')
    end = native_plan.get('materialized_map_count')
    _require(type(end) is int and end in (160, 192), 'NATIVE_MAP_CAPACITY_INVALID')
    _require(native_plan.get('directory_stride') == 8
             and native_plan.get('block_shift') == 5
             and native_plan.get('block_directory_bytes') == 128
             and native_plan.get('directory_label') == 'LyraResidentPageDirectory'
             and native_plan.get('animation_directory_label') == 'LyraResidentAnimationDirectory'
             and native_plan.get('animation_directory_stride') == NATIVE_ANIMATION_DIRECTORY_STRIDE
             and native_plan.get('first_map') == FIRST and native_plan.get('end_map') == end
             and type(native_plan.get('tile16_count')) is int
             and 0 < native_plan['tile16_count'] <= 4096
             and all(native_plan.get(key) is False for key in (
                 'selected', 'allocation_granted', 'publication_authorized',
                 'ordinary_build_ready', 'runtime_admission', 'compiled_consumers_verified'))
             and native_plan.get('consumer_status') == dict(page_word_lookup='source_abi_only',
                 main_chr_staging_implemented=False, palette_lifecycle_implemented=False,
                 animation_lifecycle_implemented=False, resource_closure_verified=False),
             'NATIVE_ABI_CONTRACT_INVALID')
    blobs = native_plan.get('blobs')
    _require(type(blobs) is list and all(type(row) is dict for row in blobs),
             'NATIVE_BLOBS_INVALID')
    by_label = {}
    for row in blobs:
        label = row.get('label')
        _require(type(label) is str and re.fullmatch(r'LyraResident[A-Za-z0-9_]+', label)
                 and label not in (native_plan['directory_label'], native_plan['animation_directory_label'])
                 and label not in by_label and row.get('role') in (
                     'page_index', 'page_words', 'static_chr', 'animation', 'palette'),
                 'NATIVE_BLOBS_INVALID')
        by_label[label] = _verified_payload(row)
        _require(0 < len(by_label[label]) <= 0x8000, 'NATIVE_BLOB_BANK_CAPACITY')
    pages = native_plan.get('pages')
    areas = native_plan.get('areas')
    _require(type(pages) is list and all(type(row) is dict for row in pages)
             and type(areas) is list, 'NATIVE_PAGES_INCOMPLETE')
    selected = _checked_areas([dict(parent_map_id=area.get('parent_map_id'),
        maps=area.get('maps'), size=area.get('size')) for area in areas], end)
    _require([row.get('map_id') for row in pages] == sorted(selected),
             'NATIVE_PAGES_INCOMPLETE')
    by_role = {row['label']: row['role'] for row in blobs}
    for area_index, area in enumerate(areas):
        _require(area.get('area_index') == area_index
                 and type(area.get('maps')) is list and area['maps']
                 and area.get('parent_map_id') == area['maps'][0]
                 and by_role.get(area.get('palette_label')) == 'palette'
                 and len(by_label[area['palette_label']]) == 256
                 and area.get('palette_byte_count') == 256
                 and (area.get('static_label') is None or
                      by_role.get(area['static_label']) == 'static_chr')
                 and type(area.get('animation_labels')) is list
                 and len(area['animation_labels']) == 3
                 and type(area.get('animation_byte_count')) is int
                 and 0 <= area['animation_byte_count'] <= 1024
                 and all((label is None and area['animation_byte_count'] == 0) or
                         (by_role.get(label) == 'animation'
                          and len(by_label[label]) == area['animation_byte_count'])
                         for label in area['animation_labels']), 'NATIVE_AREA_EXTENT_INVALID')
        static = by_label[area['static_label']] if area['static_label'] is not None else b''
        _require(len(static) % 32 == 0
                 and area.get('static_runs') == _native_static_runs(len(static) // 32)
                 and area.get('animation_wram') == [0x7EA680, 0x7EAA80, 0x7EAE80]
                 and area.get('animation_vram_word_address') == 0x3C00
                 and area.get('native_animation_upload_byte_count') == 0x400
                 and area['animation_byte_count'] % 32 == 0
                 and all(word <= 0x7FFF for word in struct.unpack('<128H', by_label[area['palette_label']])),
                 'NATIVE_RESOURCE_LAYOUT_INVALID')
    for page in pages:
        index, words = (by_label.get(page.get(key)) for key in ('index_label', 'words_label'))
        count, blocks, area = (page.get(key) for key in ('row_count', 'block_count', 'area_index'))
        _require(type(count) is int and 0 < count <= 255
                 and type(blocks) is int and 0 < blocks <= 128
                 and type(area) is int and 0 <= area < len(areas)
                 and page['map_id'] in areas[area]['maps']
                 and by_role.get(page.get('index_label')) == 'page_index'
                 and by_role.get(page.get('words_label')) == 'page_words'
                 and page.get('index_alias') == f"LyraResidentPageIndex_{page['map_id']:02X}"
                 and page.get('words_alias') == f"LyraResidentPageWords_{page['map_id']:02X}"
                 and index is not None and len(index) == 128 + blocks * 32
                 and words is not None and len(words) == (count + 1) * 8
                 and words[:8] == bytes(8), 'NATIVE_PAGE_EXTENT_INVALID')
        _require(sorted(value for value in index[:128] if value) == list(range(1, blocks + 1)),
                 'NATIVE_BLOCK_INDEX_INVALID')
        observed = {}
        for tile in range(4096):
            block = index[tile >> 5]
            row = index[128 + (block - 1) * 32 + (tile & 31)] if block else 0
            if row:
                _require(tile < native_plan['tile16_count'] and row <= count
                         and row not in observed, 'NATIVE_ROW_INDEX_INVALID')
                observed[row] = tile
        _require(sorted(observed) == list(range(1, count + 1))
                 and [observed[row] for row in range(1, count + 1)] == page.get('tile16_ids'),
                 'NATIVE_ROW_INDEX_INVALID')
    expected_counts = {role: sum(row['byte_count'] for row in blobs if row['role'] == role)
                       for role in ('page_index', 'page_words', 'static_chr', 'animation', 'palette')}
    expected_counts['page_directory'] = (end - FIRST) * NATIVE_DIRECTORY_STRIDE
    expected_counts['animation_directory'] = (end - FIRST) * NATIVE_ANIMATION_DIRECTORY_STRIDE
    _require(native_plan.get('byte_counts') == expected_counts
             and native_plan.get('unaligned_byte_count') == sum(expected_counts.values()),
             'NATIVE_BYTE_COUNT_INVALID')
    return by_label


def _transfer_tables(native_plan, addresses, origin):
    """Retained SharedGraphics22B ABI, with same-bank absolute word pointers.

    Uses only the already validated static runs and assigned resource origins.
    This is derived data; it does not enable uploads, cache mutation or hooks.
    """
    parent_count = native_plan['end_map']
    raw = bytearray(parent_count * 2)
    profiles = {}
    by_area = {}
    for area in native_plan['areas']:
        runs = area['static_runs']
        start = len(raw)
        normal = start + 22
        staging = normal + len(runs) * 7
        size = 22 + len(runs) * 15
        _require((origin & 0xFFFF) + start + size <= 0x10000,
                 'TRANSFER_TABLE_BANK_CROSSING')
        address = origin + start
        profiles[area['parent_map_id']] = address
        by_area[area['area_index']] = address
        mask = sum(1 << run['native_sheet'] for run in runs)
        header = bytearray(22)
        struct.pack_into('<HHBB', header, 0, len(runs),
            (origin + normal) & 0xFFFF if runs else 0, mask, 3)
        struct.pack_into('<HH', header, 13, len(runs),
            (origin + staging) & 0xFFFF if runs else 0)
        raw.extend(header)
        sources = []
        for run in runs:
            source = addresses[area['static_label']] + run['source_offset']
            _require((source & 0xFFFF) + run['byte_count'] <= 0x10000,
                     'TRANSFER_RESOURCE_BANK_CROSSING')
            sources.append(source)
            raw.extend(source.to_bytes(3, 'little'))
            raw.extend(struct.pack('<HH', run['vram_word_address'], run['byte_count']))
        for run, source in zip(runs, sources):
            raw.extend(source.to_bytes(3, 'little'))
            raw.extend(run['wram_address'].to_bytes(3, 'little'))
            raw.extend(struct.pack('<H', run['byte_count']))
    for page in native_plan['pages']:
        struct.pack_into('<H', raw, page['map_id'] * 2,
                         by_area[page['area_index']] & 0xFFFF)
    return bytes(raw), profiles


def emit_native_resident_abi(native_plan, *, data_pc, capacity, preimage,
                             binary_path='binaries/resident-atlas.bin',
                             excluded_pc_spans=()):
    """Emit bytes/source for an explicit caller-owned ROM interval, without I/O.

    This mechanically places each blob inside one LoROM bank. It accepts no
    default address and makes no claim that the interval or runtime is granted.
    The owning publisher must authenticate and rederive the complete plan.
    """
    by_label = validate_native_resident_abi(native_plan)
    end = native_plan['end_map']
    page_count = end - FIRST
    _require(type(data_pc) is int and type(capacity) is int
             and 0 <= data_pc < data_pc + capacity <= 0x400000
             and type(preimage) is bytes and len(preimage) == capacity,
             'NATIVE_ORIGIN_PREIMAGE_REQUIRED')
    _require(type(binary_path) is str and re.fullmatch(r'binaries/[A-Za-z0-9_-]+\.bin', binary_path),
             'NATIVE_BINARY_PATH_INVALID')
    _require(type(excluded_pc_spans) in (list, tuple),
             'NATIVE_EXCLUDED_SPANS_INVALID')
    exclusions = []
    for span in excluded_pc_spans:
        _require(type(span) in (list, tuple) and len(span) == 2
                 and all(type(value) is int for value in span)
                 and data_pc <= span[0] < span[1] <= data_pc + capacity
                 and (not exclusions or exclusions[-1][1] <= span[0]),
                 'NATIVE_EXCLUDED_SPANS_INVALID')
        exclusions.append(tuple(span))
    cursor, binary, placements = data_pc, bytearray(), []

    def snes(pc):
        return 0x800000 | ((pc // 0x8000) << 16) | 0x8000 | (pc % 0x8000)

    def next_pc(size):
        _require(size <= 0x8000, 'NATIVE_ALLOCATION_BANK_CAPACITY')
        at = cursor
        while True:
            if at % 0x8000 + size > 0x8000:
                at = (at // 0x8000 + 1) * 0x8000
            blocked = next((end for first, end in exclusions
                            if at < end and at + size > first), None)
            if blocked is None:
                break
            at = blocked
        _require(at + size <= data_pc + capacity, 'NATIVE_ALLOCATION_CAPACITY')
        return at

    def place(label, raw, role):
        nonlocal cursor
        cursor = next_pc(len(raw))
        record = dict(label=label, role=role, pc=[cursor, cursor + len(raw)],
            snes=snes(cursor), byte_count=len(raw), sha256=_sha(raw),
            binary_offset=len(binary), preimage_sha256=_sha(
                preimage[cursor-data_pc:cursor-data_pc+len(raw)]))
        placements.append(record)
        binary.extend(raw)
        cursor += len(raw)
        return record

    directory = place(native_plan['directory_label'], bytes(page_count * NATIVE_DIRECTORY_STRIDE), 'page_directory')
    animation_directory = place(native_plan['animation_directory_label'],
        bytes(page_count * NATIVE_ANIMATION_DIRECTORY_STRIDE), 'animation_directory')
    for blob in native_plan['blobs']:
        place(blob['label'], by_label[blob['label']], blob['role'])
    addresses = {row['label']: row['snes'] for row in placements}
    transfer_size = (end * 2 + sum(22 + len(area['static_runs']) * 15
                                  for area in native_plan['areas']))
    transfer_pc = next_pc(transfer_size)
    transfer_raw, transfer_profiles = _transfer_tables(native_plan, addresses, snes(transfer_pc))
    _require(not any(row['label'] == 'SharedGraphicsParentProfiles' for row in placements),
             'TRANSFER_LABEL_COLLISION')
    transfer = place('SharedGraphicsParentProfiles', transfer_raw, 'graphics_transfer_tables')
    # Physical special-page keys, not gameplay parent indices. Existing palette
    # blobs already deduplicate equal area palettes; zero means native fallback.
    palette_raw = bytearray(page_count * NATIVE_PALETTE_DIRECTORY_STRIDE)
    for page in native_plan['pages']:
        area = native_plan['areas'][page['area_index']]
        source = addresses[area['palette_label']]
        _require((source & 0xFFFF) + area['palette_byte_count'] <= 0x10000,
                 'PALETTE_RESOURCE_BANK_CROSSING')
        at = (page['map_id'] - FIRST) * NATIVE_PALETTE_DIRECTORY_STRIDE
        palette_raw[at:at + NATIVE_PALETTE_DIRECTORY_STRIDE] = source.to_bytes(3, 'little')
    # The label cannot alias authenticated blobs (whose names start LyraResident)
    # or the canonical page aliases. The same emitter owns its bytes/preimage.
    _require(not any(row['label'] == NATIVE_PALETTE_DIRECTORY_LABEL for row in placements),
             'PALETTE_DIRECTORY_LABEL_COLLISION')
    palette_directory = place(NATIVE_PALETTE_DIRECTORY_LABEL, bytes(palette_raw), 'palette_directory')
    directory_raw = bytearray(page_count * NATIVE_DIRECTORY_STRIDE)
    animation_raw = bytearray(page_count * NATIVE_ANIMATION_DIRECTORY_STRIDE)
    for page in native_plan['pages']:
        index = page['map_id'] - FIRST
        record = (addresses[page['index_label']].to_bytes(3, 'little')
                  + addresses[page['words_label']].to_bytes(3, 'little')
                  + bytes((page['area_index'], page['row_count'])))
        at = index * NATIVE_DIRECTORY_STRIDE
        directory_raw[at:at + NATIVE_DIRECTORY_STRIDE] = record
        area = native_plan['areas'][page['area_index']]
        record = (b''.join((addresses[label] if label else 0).to_bytes(3, 'little')
                          for label in area['animation_labels'])
                  + area['animation_byte_count'].to_bytes(2, 'little'))
        at = index * NATIVE_ANIMATION_DIRECTORY_STRIDE
        animation_raw[at:at + NATIVE_ANIMATION_DIRECTORY_STRIDE] = record
    binary[:len(directory_raw)] = directory_raw
    directory['sha256'] = _sha(directory_raw)
    offset = animation_directory['binary_offset']
    binary[offset:offset + len(animation_raw)] = animation_raw
    animation_directory['sha256'] = _sha(animation_raw)
    lines = ['; Generated special-overworld resident ABI; unselected terrain census only.', 'pushpc']
    for row in placements:
        start, size = row['binary_offset'], row['byte_count']
        lines += [f'org ${row["snes"]:06X}', row['label'] + ':',
                  f'incbin "{binary_path}":${start:X}..${start+size:X}',
                  f'{row["label"]}_End:',
                  f'assert {row["label"]}>>16 == ({row["label"]}_End-1)>>16']
    for page in native_plan['pages']:
        for alias, label in ((page['index_alias'], page['index_label']),
                             (page['words_alias'], page['words_label'])):
            if alias != label:
                lines.append(f'{alias} = ${addresses[label]:06X}')
    lines += ['pullpc', '']
    constants = (f'!SPECIAL_OVERWORLD_RESIDENT_FIRST = ${FIRST:04X}\n'
        + f'!SPECIAL_OVERWORLD_RESIDENT_END = ${end:04X}\n'
        + f'!LYRA_CURRENT_RESIDENT_ABI_VERSION = {NATIVE_ABI_VERSION}\n'
        + f'!LYRA_CURRENT_RESIDENT_TILE16_COUNT = {native_plan["tile16_count"]}\n'
        + f'!LYRA_CURRENT_RESIDENT_DIRECTORY = ${directory["snes"]:06X}\n')
    constants += (f'!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY = ${animation_directory["snes"]:06X}\n')
    constants += ''.join(f'!GfxRT_{key} = ${value:04X}\n' for key, value in dict(
        TRANSFER_CONSTANTS, Bank=transfer['snes'] >> 16, ParentCount=end).items())
    constants += f'!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY = ${transfer["snes"]:06X}\n'
    constants += f'!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY = ${palette_directory["snes"]:06X}\n'
    constants += f'!SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE = {NATIVE_PALETTE_DIRECTORY_STRIDE}\n'
    excluded_bytes = sum(max(0, min(end, cursor) - first)
                         for first, end in exclusions if first < cursor)
    return dict(kind='lyra.resident_atlas_native_emission.v1',
        abi_sha256=native_plan['abi_sha256'], data_pc=[data_pc, data_pc + capacity],
        excluded_pc_spans=[list(span) for span in exclusions],
        preimage_sha256=_sha(preimage), used_pc_end=cursor,
        used_extent_bytes=cursor-data_pc,
        bank_padding_bytes=cursor-data_pc-len(binary)-excluded_bytes,
        excluded_extent_bytes=excluded_bytes,
        binary_path=binary_path, payload_hex=bytes(binary).hex(), payload_sha256=_sha(binary),
        placements=placements, animation_directory_byte_count=len(animation_raw),
        palette_directory_snes=palette_directory['snes'],
        palette_directory_byte_count=len(palette_raw),
        palette_directory_stride=NATIVE_PALETTE_DIRECTORY_STRIDE,
        transfer_table_snes=transfer['snes'], transfer_table_byte_count=len(transfer_raw),
        transfer_profile_snes={str(parent): address for parent, address in transfer_profiles.items()},
        runtime_data_asm='\n'.join(lines), constants_asm=constants,
        selected=False, allocation_granted=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False)


def resident_bg128_rows(native_plan):
    """Return derived BG inputs for every physical page, never saved properties."""
    payloads = validate_native_resident_abi(native_plan)
    return [dict(map_id=page['map_id'], properties=dict(background_palette=list(
        struct.unpack('<128H', payloads[native_plan['areas'][page['area_index']]['palette_label']]))))
        for page in native_plan['pages']]


def resident_runtime_inputs(native_plan, emission, *, preimage):
    """Bridge verified resident placements to the existing SharedGraphics ABI.

    The resident emitter remains the sole payload writer. Its complete output
    is rederived before any external address is used; neither this bridge nor
    its fixed22B upload profiles grants allocation or activation authority.
    """
    _require(type(emission) is dict
             and emission.get('kind') == 'lyra.resident_atlas_native_emission.v1'
             and type(emission.get('data_pc')) is list and len(emission['data_pc']) == 2
             and all(type(value) is int for value in emission['data_pc']),
             'NATIVE_EMISSION_INVALID')
    first, end = emission['data_pc']
    expected = emit_native_resident_abi(native_plan, data_pc=first, capacity=end-first,
        preimage=preimage, binary_path=emission.get('binary_path'),
        excluded_pc_spans=emission.get('excluded_pc_spans', ()))
    _require(expected == emission, 'NATIVE_EMISSION_MISMATCH')
    placements = {row['label']: row for row in expected['placements']}
    resources, profiles, parents = {}, {}, {}
    for area in native_plan['areas']:
        profile_id = f"resident_{area['parent_map_id']:02X}"
        resource_id = area['static_label']
        if resource_id is not None:
            row = placements[resource_id]
            resources[resource_id] = {key: row[key] for key in (
                'label', 'snes', 'byte_count', 'sha256')}
        normal, staging = [], []
        for run in area['static_runs']:
            transfer = dict(resource_id=resource_id, **{key: run[key] for key in (
                'source_offset', 'vram_word_address', 'byte_count')})
            normal.append(transfer)
            staging.append(dict(transfer, wram_address=run['wram_address']))
        slots = [run['native_sheet'] for run in area['static_runs']]
        profiles[profile_id] = dict(runtime_enabled=True, normal=normal, staging=staging,
            transition=dict(mode='native_staging', source_bank=0x7F),
            cache_slots=slots, cache_slot_mask=sum(1 << slot for slot in slots), late=None)
        for page in native_plan['pages']:
            if page['area_index'] == area['area_index']:
                parents[str(page['map_id'])] = dict(profile_id=profile_id, runtime_enabled=True)
    return dict(kind='lyra.resident_shared_graphics_bridge.v1',
        abi_sha256=native_plan['abi_sha256'], payload_sha256=expected['payload_sha256'],
        resources=resources, profiles=profiles, parents=parents,
        selected=False, allocation_granted=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False)
