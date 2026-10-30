"""Derive unallocated resident terrain resources from a bound native inspection.

This is data planning for the existing current-save publisher. It never writes
a ROM, assigns storage, clears appearance blockers or qualifies native loading.
"""
from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
import re
import struct
import sys

from lyra_project_terrain import TerrainDocument, validated_gameplay_areas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Generate'))
import sheet_codec
import sheet_table

KIND = 'lyra.resident_graphics_source_plan.v1'
FIRST, END = 0xA0, 0xC0
STATIC_SLOTS = tuple(range(448)) + tuple(range(480, 512))
ANIMATED_SLOTS = tuple(range(448, 480))
UNKNOWNS = (
    'mutable_event_tile_closure', 'overlay_and_shared_bg_resources',
    'active_obj_follower_ancilla_resources', 'external_scroll_coexistence',
    'owned_allocation_and_transfer_budget', 'native_remap_palette_animation_consumers',
    'native_tint_refresh_and_departure_restore',
)


def _require(value, reason):
    if not value:
        raise ValueError('RESIDENT_GRAPHICS_' + reason)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json_bytes(value):
    try:
        return json.dumps(value, sort_keys=True, separators=(',', ':'),
                          allow_nan=False).encode('utf-8')
    except (TypeError, ValueError) as error:
        raise ValueError('RESIDENT_GRAPHICS_PROVENANCE_INVALID') from error


def _digest(value):
    return type(value) is str and re.fullmatch('[0-9a-f]{64}', value) is not None


def _payload(raw, **details):
    return dict(byte_count=len(raw), payload_hex=raw.hex(), sha256=_sha(raw), **details)


def _four_bpp(pixels):
    """Encode one native-order 8x8 indexed tile, preserving index0."""
    _require(len(pixels) == 64 and all(0 <= value < 16 for value in pixels),
             'PIXEL_INDEX_INVALID')
    raw = bytearray(32)
    for y in range(8):
        for x in range(8):
            value, bit = pixels[y * 8 + x], 1 << (7 - x)
            for plane in range(4):
                if value & (1 << plane):
                    raw[(plane // 2) * 16 + y * 2 + plane % 2] |= bit
    return bytes(raw)


def _color_bytes(colors):
    return b''.join(b'\x00\x00\x00' if value is None else
                    b'\x01' + struct.pack('<H', value) for value in colors)


def _source_sheets(source):
    cache, records = {}, {}

    def read(sheet):
        _require(type(sheet) is int and 0 <= sheet < 255, 'SHEET_SELECTOR_INVALID')
        if sheet not in cache:
            try:
                pointer = sheet_table.ptr(source, sheet)
                _require(pointer & 0xFFFF >= 0x8000
                         and (pointer >> 16) & 0x7F < 0x7E, 'SHEET_POINTER_INVALID')
                start = sheet_table.pc(pointer)
                if 0x73 <= sheet <= 0x7E:
                    raw, consumed = source[start:start + 0x600], 0x600
                else:
                    raw, consumed = sheet_table.decomp(source, pointer)
                _require(len(raw) == 0x600 and start + consumed <= len(source),
                         'SHEET_BYTES_INVALID')
                grid = sheet_codec.sheet_to_grid(raw)
            except (IndexError, ValueError) as error:
                raise ValueError(f'RESIDENT_GRAPHICS_SHEET_DECODE_FAILED: {sheet:02X}') from error
            flat = bytes(value for row in grid for value in row)
            tiles = tuple(bytes(grid[t // 16 * 8 + y][t % 16 * 8 + x]
                                for y in range(8) for x in range(8)) for t in range(64))
            cache[sheet] = (flat, tiles)
            records[sheet] = dict(sheet_id=sheet, pointer_snes=pointer,
                stream_byte_count=consumed, stream_sha256=_sha(source[start:start + consumed]),
                decoded_3bpp_sha256=_sha(raw), decoded_indexed8_sha256=_sha(flat))
        return cache[sheet]

    return read, records


def _inspection_rows(source, document, inspection, terrain_sha256, read_sheet):
    _require(type(inspection) is dict
             and inspection.get('source_rom_sha256') == _sha(source), 'SOURCE_MISMATCH')
    _require(_digest(terrain_sha256) and inspection.get('terrain_sha256') == terrain_sha256,
             'TERRAIN_MISMATCH')
    _require(inspection.get('profile') == document.profile, 'PROFILE_MISMATCH')
    _require(type(inspection.get('asset_binding_mismatches')) is int
             and inspection['asset_binding_mismatches'] == 0
             and inspection.get('map_count') == 32
             and inspection.get('donor_map') == 0x3A
             and inspection.get('inspection_only') is True
             and inspection.get('native_resolution_schema') == 'yaze.lyra-native-resolution.v1',
             'INSPECTION_UNBOUND')
    supplied = inspection.get('map_assets')
    _require(type(supplied) is list and len(supplied) == 96, 'INSPECTION_ROWS_INVALID')
    rows = {}
    for row in supplied:
        _require(type(row) is dict and type(row.get('map_id')) is int
                 and FIRST <= row['map_id'] < END and type(row.get('state')) is int
                 and 0 <= row['state'] < 3, 'INSPECTION_ROW_INVALID')
        key = (row['map_id'], row['state'])
        _require(key not in rows, 'INSPECTION_ROW_DUPLICATE')
        map_id, state = key
        prop = document.properties[map_id - FIRST]
        assets = row.get('native_assets')
        _require(type(assets) is dict and assets.get('schema') == 'yaze.lyra-native-resolution.v1'
                 and assets.get('inspection_only') is True
                 and assets.get('resolution_mode') == 'native-only'
                 and assets.get('state') == state and assets.get('resolver_seed_map') == 0x3A,
                 'ASSET_RESOLUTION_UNBOUND')
        expected = document.authoring[map_id - FIRST]['asset_bindings'][state]
        binding = row.get('current_binding')
        _require(_digest(binding) and row.get('binding_changed') is False
                 and row.get('stored_binding') == expected
                 and (not expected or binding == expected)
                 and row.get('native_base_binding') == binding
                 and assets.get('native_base_binding') == binding, 'ASSET_BINDING_MISMATCH')
        saved = assets.get('saved_properties')
        fields = ('graphics_sheets', 'main_palette', 'palette_set', 'animated_sheet',
                  'sprite_graphics', 'sprite_palettes')
        _require(type(saved) is dict and all(saved.get(name) == prop[name] for name in fields)
                 and saved.get('background_palette') == prop.get('background_palette'),
                 'SAVED_PROPERTIES_MISMATCH')
        palette = assets.get('palette')
        words = palette.get('words') if type(palette) is dict else None
        _require(type(words) is list and len(words) == 256
                 and all(type(value) is int and 0 <= value <= 0x7FFF for value in words)
                 and row.get('palette_words') == words, 'PALETTE_WORDS_INVALID')
        raw_palette = struct.pack('<256H', *words)
        _require(palette.get('uint16le_sha256') == _sha(raw_palette), 'PALETTE_HASH_MISMATCH')
        override = prop.get('background_palette')
        _require(palette.get('background_override_words') == override
                 and (override is None or words[:128] == override), 'BG128_MISMATCH')
        animation = assets.get('animation')
        selector = animation.get('sheet_id') if type(animation) is dict else None
        _require(type(selector) is int and 1 <= selector < 255, 'ANIMATION_SELECTOR_INVALID')
        _require(1 <= prop['animated_sheet'] < 255
                 and all(type(sheet) is int and 0 <= sheet < 255
                         for sheet in prop['graphics_sheets']), 'SELECTOR_RESOLUTION_UNSUPPORTED')
        _require(selector == prop['animated_sheet'], 'ANIMATION_SELECTOR_MISMATCH')
        animated, _ = read_sheet(selector)
        _require(animation.get('decoded_sheet_sha256') == _sha(animated), 'ANIMATION_HASH_MISMATCH')
        read_sheet(selector - 1)
        slots = assets.get('slots')
        _require(type(slots) is list and len(slots) == 16
                 and [slot.get('slot') for slot in slots if type(slot) is dict] == list(range(16)),
                 'SLOT_ROWS_INVALID')
        for index, slot in enumerate(slots):
            sheet = slot.get('sheet_id')
            if index < 8:
                _require(sheet == prop['graphics_sheets'][index], 'SHEET_SELECTOR_MISMATCH')
            if sheet is None:
                resolved = bytes(0x1000)
            else:
                decoded, _ = read_sheet(sheet)
                _require(slot.get('decoded_sheet_sha256') == _sha(decoded), 'SHEET_HASH_MISMATCH')
                bias = 0x88 if index in (0, 3, 4, 5) else 0
                resolved = bytes((value + bias) & 255 for value in decoded)
            if index == 7:
                resolved = animated[:0x800] + resolved[0x800:]
            if 'resolved_slot_sha256' in slot:
                _require(slot['resolved_slot_sha256'] == _sha(resolved), 'RESOLVED_SLOT_HASH_MISMATCH')
        rows[key] = assets
    _require(set(rows) == {(map_id, state) for map_id in range(FIRST, END) for state in range(3)},
             'INSPECTION_ROWS_INCOMPLETE')
    for map_id in range(FIRST, END):
        first = rows[map_id, 0]
        for state in (1, 2):
            other = rows[map_id, state]
            _require(first['palette']['words'][:128] == other['palette']['words'][:128]
                     and all((left.get('sheet_id'), left.get('decoded_sheet_sha256'),
                              left.get('resolved_slot_sha256')) ==
                             (right.get('sheet_id'), right.get('decoded_sheet_sha256'),
                              right.get('resolved_slot_sha256'))
                             for left, right in zip(first['slots'][:8], other['slots'][:8]))
                     and first['animation']['sheet_id'] == other['animation']['sheet_id'],
                     f'BG_PHASE_VARIATION_UNSUPPORTED: {map_id:02X}')
    return rows


def _plan_area(area, document, assets, definitions, read_sheet):
    demands, references, claims = {}, [], {}
    for map_id in area['maps']:
        data = assets[map_id, 0]
        palette = data['palette']['words']
        for tile in sorted(set(document.maps[map_id - FIRST])):
            for quadrant, word in enumerate(struct.unpack_from('<4H', definitions, tile * 8)):
                references.append((map_id, tile, quadrant, word))
                key = (map_id, word)
                if key in demands:
                    continue
                char, bank = word & 1023, (word >> 10) & 7
                slot, index = divmod(char, 64)
                _require(slot < 8, 'TERRAIN_OBJ_REFERENCE_UNSUPPORTED')
                animated = 448 <= char < 480
                if animated:
                    selector = data['animation']['sheet_id']
                    before = read_sheet(selector - 1)[1]
                    current = read_sheet(selector)[1]
                    frames = (before[index], before[32 + index], current[index])
                else:
                    sheet = data['slots'][slot]['sheet_id']
                    frames = (bytes(64) if sheet is None else read_sheet(sheet)[1][index],)
                high = slot in (0, 3, 4, 5) and not animated
                indices = tuple(bytes(0 if value == 0 else value | 8 if high else value
                                      for value in frame) for frame in frames)
                colors = tuple(tuple(None if value == 0 else palette[bank * 16 + value]
                                     for value in frame) for frame in indices)
                for frame in indices:
                    for value in frame:
                        if value:
                            claims.setdefault(bank * 16 + value, set()).add(palette[bank * 16 + value])
                demands[key] = dict(animated=animated, colors=colors,
                    color_set=frozenset(value for frame in colors for value in frame if value is not None))
    sets = sorted({row['color_set'] for row in demands.values()},
                  key=lambda values: (-len(values), tuple(sorted(values))))
    bins, assignment, refused = [], {}, []
    for colors in sets:
        choices = [(len(colors - existing), index) for index, existing in enumerate(bins)
                   if len(existing | colors) <= 15]
        if choices:
            _, index = min(choices)
            bins[index].update(colors)
        elif len(bins) < 6 and len(colors) <= 15:
            index = len(bins)
            bins.append(set(colors))
        else:
            refused.append('TERRAIN_PALETTE_PACKING_UNKNOWN')
            break
        assignment[colors] = index
    base_palette = assets[area['parent_map_id'], 0]['palette']['words'][:128]
    if any(assets[map_id, 0]['palette']['words'][:32] != base_palette[:32]
           for map_id in area['maps']):
        refused.append('HUD_PALETTE_CONFLICT')
    result = dict(parent_map_id=area['parent_map_id'], size=area['size'], maps=list(area['maps']),
        terrain_plan_ready=False, full_residency_ready=False,
        full_residency_status='UNKNOWN_RESOURCE_CLOSURE', unknowns=list(UNKNOWNS),
        refusals=refused, palette_row_color_counts=[len(values) for values in bins],
        conflicting_original_cgram_entries=[dict(entry=index, colors=sorted(values))
            for index, values in sorted(claims.items()) if len(values) > 1],
        remaps=[], static_slots=[], static_chr=None, animation=None, palette=None, witness=None)
    if refused:
        result['status'] = 'TERRAIN_PACKING_UNQUALIFIED'
        return result
    palettes = [sorted(values) for values in bins]
    encoded = {}
    for key, demand in demands.items():
        row = assignment[demand['color_set']]
        lookup = {value: index + 1 for index, value in enumerate(palettes[row])}
        pixels = tuple(bytes(0 if value is None else lookup[value] for value in frame)
                       for frame in demand['colors'])
        encoded[key] = (row + 2, tuple(_four_bpp(frame) for frame in pixels), pixels)
    static = sorted({frames[0] for key, (_, frames, _) in encoded.items() if not demands[key]['animated']})
    animated = sorted({frames for key, (_, frames, _) in encoded.items() if demands[key]['animated']})
    if len(static) > len(STATIC_SLOTS):
        refused.append('STATIC_NAMESPACE_EXHAUSTED')
    if len(animated) > len(ANIMATED_SLOTS):
        refused.append('ANIMATION_NAMESPACE_EXHAUSTED')
    result.update(static_pattern_count=len(static), animated_pattern_count=len(animated))
    if refused:
        result['status'] = 'TERRAIN_PACKING_UNQUALIFIED'
        return result
    static_ids = {pattern: STATIC_SLOTS[index] for index, pattern in enumerate(static)}
    animated_ids = {pattern: ANIMATED_SLOTS[index] for index, pattern in enumerate(animated)}
    source_colors, reconstructed = hashlib.sha256(), hashlib.sha256()
    comparisons = 0
    for map_id, tile, quadrant, word in references:
        key = (map_id, word)
        bank, patterns, pixels = encoded[key]
        char = animated_ids[patterns] if demands[key]['animated'] else static_ids[patterns[0]]
        target_word = (word & 0xE000) | (bank << 10) | char
        result['remaps'].append(dict(map_id=map_id, tile16_id=tile, quadrant=quadrant,
                                    source_word=word, target_word=target_word))
        for original, frame in zip(demands[key]['colors'], pixels):
            restored = tuple(None if value == 0 else palettes[bank - 2][value - 1] for value in frame)
            _require(original == restored, 'COLOR_RECONSTRUCTION_FAILED')
            source_colors.update(_color_bytes(original))
            reconstructed.update(_color_bytes(restored))
            comparisons += len(frame)
    words = list(base_palette)
    for index, colors in enumerate(palettes, 2):
        words[index * 16:index * 16 + 16] = [base_palette[index * 16], *colors,
                                            *([0] * (15 - len(colors)))]
    result.update(status='TERRAIN_ONLY_CONSTRUCTIVE_FIT', terrain_plan_ready=True,
        static_slots=list(STATIC_SLOTS[:len(static)]),
        static_chr=_payload(b''.join(static), tile_count=len(static), format='snes4bpp'),
        animation=dict(slots=list(ANIMATED_SLOTS[:len(animated)]), frame_count=3,
            frame_payloads=[_payload(b''.join(pattern[frame] for pattern in animated),
                                    tile_count=len(animated), format='snes4bpp') for frame in range(3)]),
        palette=dict(words=words, **_payload(struct.pack('<128H', *words),
                                           format='bgr555_uint16le', hypothetical_rows=list(range(2, 8)))),
        witness=dict(pixel_comparisons=comparisons, source_colors_sha256=source_colors.hexdigest(),
                     reconstructed_colors_sha256=reconstructed.hexdigest(),
                     transparency='native index0 preserved; opaque black is a distinct color'))
    return result


def plan_resident_graphics(source, document, inspection, *, terrain_sha256, provenance):
    """Return deterministic ungranted DATA; native/shared-resource readiness stays false."""
    _require(type(source) is bytes and 0 < len(source) <= 0x400000
             and len(source) % 0x8000 == 0, 'SOURCE_INVALID')
    _require(isinstance(document, TerrainDocument)
             and type(document.maps) is tuple and len(document.maps) == 32
             and type(document.properties) is tuple and len(document.properties) == 32
             and type(document.authoring) is tuple and len(document.authoring) == 32
             and type(document.profile) is dict,
             'DOCUMENT_INVALID')
    count = document.profile.get('tile_count')
    _require(type(count) is int and 0 < count <= 4096
             and _digest(document.profile.get('tile16_definition_fingerprint')),
             'DEFINITION_COUNT_INVALID')
    _require(all(type(prop) is dict and all(name in prop for name in
                 ('graphics_sheets', 'animated_sheet', 'main_palette', 'palette_set',
                  'sprite_graphics', 'sprite_palettes'))
                 and type(prop['graphics_sheets']) is list and len(prop['graphics_sheets']) == 8
                 and type(prop['animated_sheet']) is int for prop in document.properties)
             and all(type(row) is dict and type(row.get('asset_bindings')) in (list, tuple)
                     and len(row['asset_bindings']) == 3 for row in document.authoring),
             'DOCUMENT_PROPERTIES_INVALID')
    _require(type(provenance) is dict and bool(provenance), 'PROVENANCE_INVALID')
    _json_bytes(provenance)
    try:
        areas = validated_gameplay_areas(document.gameplay_areas)
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('RESIDENT_GRAPHICS_GAMEPLAY_AREAS_INVALID') from error
    _require({map_id for area in areas for map_id in area['maps']} == set(range(FIRST, END)),
             'GAMEPLAY_AREAS_INCOMPLETE')
    _require(all(type(tiles) is tuple and len(tiles) == 1024
                 and all(type(tile) is int and 0 <= tile < count for tile in tiles)
                 for tiles in document.maps), 'TILE16_MAP_INVALID')
    _require(len(source) >= 0x868, 'DEFINITION_POINTER_MISSING')
    pointer = int.from_bytes(source[0x865:0x868], 'little')
    _require(pointer & 0xFFFF >= 0x8000 and (pointer >> 16) & 0x7F < 0x7E,
             'DEFINITION_POINTER_INVALID')
    start = sheet_table.pc(pointer)
    definitions = source[start:start + count * 8]
    _require(len(definitions) == count * 8
             and _sha(definitions) == document.profile['tile16_definition_fingerprint'],
             'DEFINITION_HASH_MISMATCH')
    read_sheet, sheets = _source_sheets(source)
    assets = _inspection_rows(source, document, inspection, terrain_sha256, read_sheet)
    planned = [_plan_area(area, document, assets, definitions, read_sheet)
               for area in sorted(areas, key=lambda row: row['parent_map_id'])]
    plan = dict(kind=KIND, scope='terrain_resource_data_only',
        source_binding=dict(source_rom_sha256=_sha(source), source_byte_count=len(source),
            terrain_sha256=terrain_sha256, inspection_sha256=_sha(_json_bytes(inspection)),
            document_sha256=_sha(_json_bytes(dict(profile=document.profile,
                maps=document.maps, properties=document.properties, authoring=document.authoring,
                gameplay_areas=document.gameplay_areas))),
            tile16_definition_snes=pointer, tile16_definition_sha256=_sha(definitions)),
        provenance=copy.deepcopy(provenance), provenance_sha256=_sha(_json_bytes(provenance)),
        terrain_plan_ready=all(area['terrain_plan_ready'] for area in planned),
        full_residency_ready=False, appearance_coherent=False,
        allocation_granted=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, compiled_consumers_verified=False,
        static_namespace=list(STATIC_SLOTS), animated_namespace=list(ANIMATED_SLOTS),
        unknowns=list(UNKNOWNS), areas=planned,
        decoded_sheets=[sheets[sheet] for sheet in sorted(sheets)])
    plan['plan_sha256'] = _sha(_json_bytes(plan))
    return plan
