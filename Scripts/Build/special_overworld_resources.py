"""Plan terrain resources from z3ed's saved native special-overworld export.

The packing algorithm is retained from lyra_resident_graphics.py@60605572986c,
with a page-keyed terrain input replacing the old sidecar document dependency.
This module does not allocate ROM storage or activate runtime consumers.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
import struct
import sys

import lyra_native_loaders as native

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Generate'))
import sheet_codec
import sheet_overrides
import sheet_table

SOURCE_SCHEMA = 'yaze.special-overworld-native-source.v1'
PLAN_SCHEMA = 'special_overworld.terrain_resources.v1'
EXPERIMENTAL_SOURCE_SCHEMA = 'yaze.special-overworld-native-source.experimental-v2'
EXPERIMENTAL_PLAN_SCHEMA = 'special_overworld.terrain_resources.experimental-v2'
PAGE_TILE16_RUNTIME_REQUIREMENTS = (
    'page_qualified_collision_source_words',
    'page_qualified_entrance_character_comparison',
    'mutable_and_fixed_tile_id_semantics_and_closure',
    'page_context_for_overlay_transition_and_refresh_readers',
)
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
                          allow_nan=False, ensure_ascii=False).encode('utf-8')
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


def _graphics_sources(value, graphics_root):
    """Authenticate the export's complete selected global-source binding."""
    if 'graphics_source' not in value:
        return {}
    _require(graphics_root is not None, 'GRAPHICS_ROOT_REQUIRED')
    provenance = value['graphics_source']
    _require(type(provenance) is dict, 'GRAPHICS_SOURCE_INVALID')
    root = Path(graphics_root).resolve(strict=True)
    ordinary_name = 'Data/graphics/source_sprite_sheets.json'
    d4_name = 'Data/graphics/d4_zora_sprite_sheets.json'
    spec_name = provenance.get('spec')
    _require(spec_name in (ordinary_name, d4_name), 'GRAPHICS_SPEC_MISMATCH')
    spec_path = root / spec_name
    _require(spec_path.resolve(strict=True) == spec_path, 'GRAPHICS_SPEC_PATH_INVALID')
    _require(provenance.get('spec_sha1') == hashlib.sha1(spec_path.read_bytes()).hexdigest(),
             'GRAPHICS_SPEC_MISMATCH')
    spec = sheet_overrides.read_spec(spec_path)
    globals_ = [entry for entry in spec['sheets'] if 'global_sheet' in entry]
    names = {entry['flag'] for entry in globals_ if entry.get('flag')}
    names.update(('ENABLE_SOURCE_SPRITE_SHEETS', 'ENABLE_D4_ZORA_REDESIGN'))
    defines, define_files = {}, {}
    for relative in ('Util/macros.asm', 'Config/module_flags.asm', 'Config/feature_flags.asm'):
        path = root / relative
        if not path.exists():
            continue
        _require(path.resolve(strict=True).is_relative_to(root), 'GRAPHICS_DEFINE_PATH_INVALID')
        raw = path.read_bytes()
        define_files[relative] = _sha(raw)
        for line in raw.decode('utf-8').splitlines():
            match = re.match(r'^\s*!([A-Za-z0-9_]+)(.*)$', line.split(';', 1)[0])
            if not match or match[1] not in names:
                continue
            rest = match[2].strip()
            _require(rest.startswith('='), 'GRAPHICS_FLAG_ASSIGNMENT_INVALID')
            literal = rest[1:].strip()
            # Match the source adapter: decimal or $hex, at most eight digits;
            # later include-file assignments replace earlier values.
            valid = re.fullmatch(r'(?:[0-9]{1,8}|\$[0-9a-fA-F]{1,8})', literal)
            defines[match[1]] = (int(literal[1:], 16) if literal.startswith('$')
                                else int(literal)) if valid else None
    _require(all(name in defines and defines[name] is not None for name in names),
             'GRAPHICS_FLAG_UNRESOLVED')
    _require(defines['ENABLE_SOURCE_SPRITE_SHEETS'] == 1,
             'GRAPHICS_SOURCE_FEATURE_DISABLED')
    d4_selected = defines['ENABLE_D4_ZORA_REDESIGN'] != 0
    _require(spec_name == (d4_name if d4_selected else ordinary_name),
             'GRAPHICS_SPEC_SELECTION_MISMATCH')
    ordinary_sha1 = None
    if d4_selected:
        ordinary_path = root / ordinary_name
        _require(ordinary_path.resolve(strict=True) == ordinary_path,
                 'GRAPHICS_SPEC_PATH_INVALID')
        ordinary = sheet_overrides.read_spec(ordinary_path)
        _require(spec['sheets'][:len(ordinary['sheets'])] == ordinary['sheets'],
                 'GRAPHICS_D4_STANDARD_PREFIX_MISMATCH')
        ordinary_sha1 = hashlib.sha1(ordinary_path.read_bytes()).hexdigest()
    selected = {sheet_overrides.number(entry['global_sheet']): entry
                for entry in globals_ if not entry.get('flag')}
    for entry in globals_:
        if entry.get('flag') and defines[entry['flag']] != 0:
            selected[sheet_overrides.number(entry['global_sheet'])] = entry
    authenticated, expected = {}, []
    for sheet, entry in sorted(selected.items()):
        path = spec_path.parent / entry['source']
        # read_spec checks both lexical traversal and symlink containment.
        _require(path.suffix == '.txt', 'GRAPHICS_SOURCE_FORMAT_UNSUPPORTED')
        grid = sheet_codec.text_to_grid(path.read_text())
        raw = sheet_codec.grid_to_sheet(grid)
        _require(_sha(raw) == entry['decoded_sha256'], 'GRAPHICS_SOURCE_HASH_MISMATCH')
        flat = bytes(pixel for row in grid for pixel in row)
        row = dict(sheet_id=sheet, source=entry['source'], flag=entry.get('flag'),
                   decoded_sheet_sha256=_sha(flat))
        expected.append(row)
        source_record = dict(spec=spec_name,
            spec_sha1=provenance['spec_sha1'], source=entry['source'],
            flag=entry.get('flag'), define_files_sha256=define_files)
        if ordinary_sha1 is not None:
            source_record['ordinary_spec_sha1'] = ordinary_sha1
        authenticated[sheet] = (raw, grid, source_record)
    _require(set(provenance) == {'spec', 'spec_sha1', 'sheets'}
             and provenance.get('sheets') == expected, 'GRAPHICS_SOURCE_ROWS_MISMATCH')
    return authenticated


def _source_sheets(source, authenticated=None):
    cache, records = {}, {}
    authenticated = authenticated or {}

    def read(sheet):
        _require(type(sheet) is int and 0 <= sheet < 255, 'SHEET_SELECTOR_INVALID')
        if sheet not in cache:
            if sheet in authenticated:
                raw, grid, provenance = authenticated[sheet]
                records[sheet] = dict(sheet_id=sheet, source_provenance=provenance,
                    decoded_3bpp_sha256=_sha(raw),
                    decoded_indexed8_sha256=_sha(bytes(v for row in grid for v in row)))
            else:
                return read_rom(sheet)
            return cache_grid(sheet, grid)
        return cache[sheet]

    def cache_grid(sheet, grid):
        flat = bytes(value for row in grid for value in row)
        tiles = tuple(bytes(grid[t // 16 * 8 + y][t % 16 * 8 + x]
                            for y in range(8) for x in range(8)) for t in range(64))
        cache[sheet] = (flat, tiles)
        return cache[sheet]

    def read_rom(sheet):
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
        records[sheet] = dict(sheet_id=sheet, pointer_snes=pointer,
            stream_byte_count=consumed, stream_sha256=_sha(source[start:start + consumed]),
            decoded_3bpp_sha256=_sha(raw),
            decoded_indexed8_sha256=_sha(bytes(v for row in grid for v in row)))
        return cache_grid(sheet, grid)

    return read, records


def _plan_area(area, page_tiles, assets, definitions, read_sheet, conditional_tiles=None,
               page_definitions=None):
    demands, references, claims = {}, [], {}
    for map_id in area['maps']:
        data = assets[map_id, 0]
        palette = data['palette']['words']
        tiles = set(page_tiles[map_id])
        if conditional_tiles is not None:
            tiles.update(conditional_tiles.get(map_id, ()))
        for tile in sorted(tiles):
            words = native.effective_tile16_words(
                definitions, page_definitions or {}, map_id, tile)
            for quadrant, word in enumerate(words):
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
                # The normal loader biases every pixel in these BG sheets,
                # including source index0: it becomes opaque palette index8.
                # An absent slot stays transparent because no bias is applied.
                present = animated or data['slots'][slot]['sheet_id'] is not None
                indices = tuple(bytes(value | 8 if high and present else value
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


def _validate_address_overrides(source, overrides):
    """Admit only Oracle's existing fixed aux-palette ABI, not relocations."""
    _require(type(overrides) is dict, 'ADDRESS_OVERRIDES_UNSUPPORTED')
    if not overrides:
        return
    # Overworld/aux_palette_extension.asm owns SNES45F900..45FE3F.
    # These describe palette loading; sheet pointers still come from the ROM.
    expected = dict(overworld_aux_palette_extension_pc=0x22F900,
                    overworld_aux_palette_extension_count=32,
                    overworld_aux_palette_extension_abi=1)
    _require(overrides.keys() == expected.keys()
             and all(type(value) is int for value in overrides.values())
             and overrides == expected, 'ADDRESS_OVERRIDES_UNSUPPORTED')
    _require(0x22F900 + 32 * 21 * 2 <= len(source),
             'AUX_PALETTE_EXTENSION_TRUNCATED')


def _native_source(source, exported, *, experimental_page_tile16=False):
    """Check a fresh z3ed export against its saved native ROM, without writes."""
    _require(type(source) is bytes and 0x200000 <= len(source) <= 0x400000,
             'SOURCE_INVALID')
    installed = native.read_native_directory(
        source, experimental_page_tile16=experimental_page_tile16)
    _require(installed is not None, 'NATIVE_DIRECTORY_REQUIRED')
    capacity, _, entries = installed
    revision = struct.unpack_from('<H', source, native.DIRECTORY_PC + 8)[0]
    _require(type(exported) is dict and type(exported.get('native_source')) is dict,
             'NATIVE_EXPORT_REQUIRED')
    value = exported['native_source']
    _require(exported.get('native_source_sha256') == _sha(_json_bytes(value)),
             'NATIVE_EXPORT_HASH_MISMATCH')
    schema = EXPERIMENTAL_SOURCE_SCHEMA if revision == 5 else SOURCE_SCHEMA
    _require(value.get('schema') == schema
             and value.get('resolution_scope') == 'resident_gameplay_areas'
             and value.get('source_rom_sha256') == _sha(source)
             and value.get('source_byte_count') == len(source)
             and value.get('directory_revision') == revision
             and value.get('materialized_map_count') == capacity
             and value.get('first_special_map') == 128
             and value.get('special_map_count') == capacity - 128
             and value.get('directory_sha256') == _sha(source[
                 native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE]),
             'NATIVE_EXPORT_SOURCE_MISMATCH')
    # Palette-only ABI metadata does not relocate the ROM's sheet pointers.
    _validate_address_overrides(source, value.get('rom_address_overrides'))
    address, count = entries[400]
    definitions = source[native.pc(address):native.pc(address) + count * 8]
    _require(value.get('tile16_dictionary') == dict(snes_address=address,
        pc_address=native.pc(address), count=count, stride=8, sha256=_sha(definitions)),
        'DEFINITION_HASH_MISMATCH')
    page_definitions = {}
    if revision == 5:
        _require(value.get('runtime_supported') is False,
                 'PAGE_TILE16_RUNTIME_ADMISSION_UNSUPPORTED')
        address, rows = entries[413]
        start = native.pc(address)
        raw = source[start:start + rows * 12]
        page_definitions = native.decode_page_tile16(raw, capacity)
        expected = dict(table_id=413, pc_address=start, snes_address=address,
            count=rows, stride=12, sha256=_sha(raw),
            rows=[dict(map_id=page, tile_id=tile, words=list(words))
                  for (page, tile), words in page_definitions.items()])
        # Compare the complete extent and semantic rows to the CRC-checked ROM,
        # including JSON types. Rehashing a stale/tampered export cannot admit it.
        _require(_json_bytes(value.get('page_tile16_definitions')) == _json_bytes(expected),
                 'PAGE_TILE16_SOURCE_MISMATCH')
    else:
        _require('page_tile16_definitions' not in value,
                 'PAGE_TILE16_REVISION_MISMATCH')
    override_pages = {page for page, _ in page_definitions}
    pages = value.get('pages')
    _require(type(pages) is list and len(pages) == capacity - 128
             and [p.get('map_id') for p in pages if type(p) is dict]
                 == list(range(128, capacity)), 'NATIVE_PAGES_INCOMPLETE')

    def row(entry_id, map_id):
        address, _ = entries[entry_id]
        _, _, width = native.entry_spec(entry_id, capacity, revision)
        start = native.pc(address) + map_id * width
        return source[start:start + width]

    areas, tiles = {}, {}
    for page in pages:
        map_id = page['map_id']
        parent, = row(7, map_id)
        size, = row(30, map_id)
        role, = row(29, map_id)
        _require(128 <= parent < capacity and size in (0, 1, 2, 3)
                 and page.get('parent_map_id') == parent and page.get('role') == role,
                 'NATIVE_AREA_MISMATCH')
        profile = page.get('source_profile')
        _require(type(profile) is dict, 'NATIVE_PROFILE_INVALID')
        flags = row(410, map_id)[0] if revision >= 4 else 0
        expected = dict(background_color=int.from_bytes(row(1, map_id), 'little'),
            main_palette=row(2, map_id)[0], palette_set=row(31, map_id)[0],
            area_graphics=row(27, map_id)[0], graphics_sheets=list(row(6, map_id)),
            animated_sheet=row(4, map_id)[0],
            subscreen_overlay=int.from_bytes(row(5, map_id), 'little'),
            mosaic=[bool(row(3, map_id)[0] & (8 >> bit)) for bit in range(4)],
            appearance_flags=flags, background_palette_words=None)
        if revision >= 4:
            expected['background_palette_words'] = list(struct.unpack('<128H', row(411, map_id - 128)))
        _require(profile == expected, 'NATIVE_PROFILE_MISMATCH')
        grid = page.get('tiles')
        _require(type(grid) is list and len(grid) == 1024
                 and all(type(tile) is int and 0 <= tile < count for tile in grid),
                 'TILE16_MAP_INVALID')
        tiles[map_id] = grid
        area = areas.setdefault(parent, dict(parent_map_id=parent,
            size=('small', 'large', 'wide', 'tall')[size], maps=[], resident_required=False))
        _require(area['size'] == ('small', 'large', 'wide', 'tall')[size],
                 'NATIVE_AREA_MISMATCH')
        area['maps'].append(map_id)
        area['resident_required'] |= flags != 0 or map_id in override_pages
    areas = [areas[key] for key in sorted(areas)]
    for area in areas:
        width, height = dict(small=(1, 1), large=(2, 2), wide=(2, 1), tall=(1, 2))[area['size']]
        parent = area['parent_map_id']
        _require(parent % 8 + width <= 8
                 and area['maps'] == [parent + y * 8 + x for y in range(height) for x in range(width)],
                 'NATIVE_AREA_FOOTPRINT_INVALID')
    _require(value.get('gameplay_areas') == areas, 'NATIVE_AREAS_MISMATCH')
    return value, definitions, tiles, areas, page_definitions


def _sky_overlay_closure(source, value, tiles, areas, *, experimental_page_tile16=False):
    """Bind the tower host's BG1 demands to the actual legacy overlay loader.

    Map87 and overlays9C/9F remain below the native readers' A0 threshold.
    An export of their directory rows alone does not prove the running loader
    selects the same picture. Refuse disagreement before packing resources.
    """
    if not any(0x87 in area['maps'] and area['resident_required'] for area in areas):
        return {}
    profile = next(page['source_profile'] for page in value['pages']
                   if page['map_id'] == 0x87)
    selected = profile['subscreen_overlay']
    _require(selected in (0x9C, 0xFF), 'SKY_OVERLAY_UNSUPPORTED')
    tables = {name: (address, width) for name, address, _, _, width
              in native.CURRENT_TABLE_SPECS}
    address, width = tables['overlay']
    start = native.pc(address) + 0x87 * width
    _require(int.from_bytes(source[start:start + width], 'little') == selected,
             'SKY_OVERLAY_SELECTION_MISMATCH')
    _, _, entries = native.read_native_directory(
        source, experimental_page_tile16=experimental_page_tile16)
    # Storms overrides even an absent ordinary overlay with9F.
    overlays = (0x9C, 0x9F) if selected == 0x9C else (0x9F,)
    for overlay in overlays:
        for name, family in (('map32_high', 20), ('map32_low', 21)):
            address, width = tables[name]
            legacy = native.pc(address) + overlay * width
            current = native.pc(entries[family][0]) + overlay * width
            _require(source[legacy:legacy + width] == source[current:current + width],
                     'SKY_OVERLAY_POINTER_MISMATCH')
    # Reserve the existing door-open/rock-ground results conservatively; this
    # is not proof that every possible mutable writer has been closed.
    return {0x87: set().union(*(tiles[overlay] for overlay in overlays),
                              (0xDA4, 0xDA6, 0xE54))}


def plan_saved_native_terrain(source, exported, *, graphics_root=None,
                              experimental_page_tile16=False):
    """Reuse the retained packer with saved-ROM pages, never a terrain sidecar.

    The caller must obtain the export by running z3ed on this exact saved ROM.
    The exporter validates/decompresses terrain; this adapter rechecks native
    profiles, topology and ROM-resolved BG bytes before consuming its tile grid.
    A source-bound export additionally requires its explicit graphics checkout;
    its selected globals are authenticated against the canonical producer spec.
    """
    value, definitions, tiles, areas, page_definitions = _native_source(
        source, exported, experimental_page_tile16=experimental_page_tile16)
    try:
        authenticated = _graphics_sources(value, graphics_root)
    except (OSError, TypeError, KeyError) as error:
        raise ValueError('RESIDENT_GRAPHICS_SOURCE_UNAVAILABLE') from error
    read_sheet, sheets = _source_sheets(source, authenticated)
    assets = {}
    required = {page for area in areas if area['resident_required'] for page in area['maps']}
    for page in value['pages']:
        if page['map_id'] not in required:
            continue
        states = page.get('resolved_states')
        _require(type(states) is list and len(states) == 3
                 and [s.get('state') for s in states if type(s) is dict] == [0, 1, 2],
                 'NATIVE_PHASES_INVALID')
        for state in states:
            palette = state.get('palette')
            words = palette.get('words') if type(palette) is dict else None
            _require(type(words) is list and len(words) == 256
                     and all(type(word) is int and 0 <= word <= 0x7FFF for word in words)
                     and palette.get('uint16le_sha256') == _sha(struct.pack('<256H', *words)),
                     'PALETTE_HASH_MISMATCH')
            if page['source_profile']['appearance_flags'] & 2:
                _require(words[:128] == page['source_profile']['background_palette_words'],
                         'BG128_SOURCE_MISMATCH')
            animation = state.get('animation')
            selector = animation.get('sheet_id') if type(animation) is dict else None
            _require(type(selector) is int and 1 <= selector < 255,
                     'ANIMATION_SELECTOR_INVALID')
            animated, _ = read_sheet(selector)
            read_sheet(selector - 1)
            _require(animation.get('decoded_sheet_sha256') == _sha(animated),
                     'ANIMATION_HASH_MISMATCH')
            slots = state.get('slots')
            _require(type(slots) is list and len(slots) == 16
                     and [s.get('slot') for s in slots if type(s) is dict] == list(range(16)),
                     'SLOT_ROWS_INVALID')
            bg_slots = []
            for index, slot in enumerate(slots[:8]):
                sheet = slot.get('sheet_id')
                empty = slot.get('empty')
                _require(type(empty) is bool and type(sheet) is int
                         and (not empty or sheet == 0), 'SLOT_SOURCE_INVALID')
                decoded, _ = read_sheet(sheet)
                _require(slot.get('decoded_sheet_sha256') == _sha(decoded),
                         'SHEET_HASH_MISMATCH')
                bias = 0x88 if index in (0, 3, 4, 5) else 0
                resolved = bytes(0x1000) if empty else bytes((v + bias) & 255 for v in decoded)
                if index == 7:
                    resolved = animated[:0x800] + resolved[0x800:]
                _require(slot.get('resolved_slot_sha256') == _sha(resolved),
                         'RESOLVED_SLOT_HASH_MISMATCH')
                bg_slots.append(dict(sheet_id=None if empty else sheet,
                    decoded_sheet_sha256=slot['decoded_sheet_sha256'],
                    resolved_slot_sha256=slot['resolved_slot_sha256']))
            assets[page['map_id'], state['state']] = dict(
                palette=palette, slots=bg_slots, animation=animation)
        baseline = assets[page['map_id'], 0]
        for phase in (1, 2):
            other = assets[page['map_id'], phase]
            _require(baseline['palette']['words'][:128] == other['palette']['words'][:128]
                     and baseline['slots'] == other['slots']
                     and baseline['animation'] == other['animation'],
                     'BG_PHASE_VARIATION_UNSUPPORTED')
    conditional_tiles = _sky_overlay_closure(
        source, value, tiles, areas, experimental_page_tile16=experimental_page_tile16)
    _require(all(0 <= tile < len(definitions) // 8
                 for values in conditional_tiles.values() for tile in values),
             'SKY_OVERLAY_TILE_INVALID')
    planned = [_plan_area(area, tiles, assets, definitions, read_sheet,
                          conditional_tiles=conditional_tiles, page_definitions=page_definitions)
               for area in areas if area['resident_required']]
    result = dict(schema=PLAN_SCHEMA, source_rom_sha256=_sha(source),
        materialized_map_count=value['materialized_map_count'],
        native_source_sha256=exported['native_source_sha256'],
        tile16_definition_sha256=_sha(definitions), areas=planned,
        terrain_plan_ready=all(area['terrain_plan_ready'] for area in planned),
        full_residency_ready=False, allocation_granted=False,
        ordinary_build_ready=False, unknowns=list(UNKNOWNS),
        decoded_sheets=[sheets[key] for key in sorted(sheets)])
    if value['directory_revision'] == 5:
        # Existing resident ABI accepts only PLAN_SCHEMA. A visual fit here
        # must not be passed to its runtime lowering/publication path.
        result.update(schema=EXPERIMENTAL_PLAN_SCHEMA, runtime_supported=False,
            page_tile16_definitions_sha256=value['page_tile16_definitions']['sha256'],
            runtime_requirements=list(PAGE_TILE16_RUNTIME_REQUIREMENTS))
    result['plan_sha256'] = _sha(_json_bytes(result))
    return result
