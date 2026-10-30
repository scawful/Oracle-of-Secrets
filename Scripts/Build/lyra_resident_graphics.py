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

from lyra_project_terrain import TerrainDocument, has_native_resource_history, validated_gameplay_areas

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Generate'))
import sheet_codec
import sheet_table

KIND = 'lyra.resident_graphics_source_plan.v1'
NATIVE_KIND = 'lyra.resident_atlas_native_abi.v1'
NATIVE_ABI_VERSION = 1
NATIVE_DIRECTORY_STRIDE = 8
NATIVE_BLOCK_SHIFT = 5
NATIVE_BLOCK_DIRECTORY_BYTES = 128
NATIVE_ANIMATION_DIRECTORY_STRIDE = 11
FIRST, END = 0xA0, 0xC0
STATIC_SLOTS = tuple(range(448)) + tuple(range(480, 512))
ANIMATED_SLOTS = tuple(range(448, 480))
CONDITIONAL_KIND = 'lyra.conditional_tile16_demands.v1'
CONDITIONAL_POLICY_KIND = 'lyra.conditional_tile16_source_policy.v1'
CONDITIONAL_SOURCE_FILES = (
    'Items/all_items.asm', 'Items/ice_rod.asm', 'Overworld/entrances.asm',
    'Overworld/area_tilesets.asm', 'Overworld/custom_gfx.asm',
    'Config/feature_flags.asm', 'Config/module_flags.asm', 'Util/macros.asm',
)
# These are saved-source predicates, not the compiled consumer's new hooks.
# Bind their complete bytes before deriving replacements from native IDs.
CONDITIONAL_NATIVE_PREIMAGES = {
    0x1BBDF4: 'c93400f045c97100f040c93500f03bc90d01f036c90f01f031c9e100f02cc9e200f027c9da00f022c9f800f01dc90e01f018',
    0x1BBE3E: 'ad7a0329ff00c90100d0f2',
    0x1BBE58: 'a0c90d805d',
    0x1BBEAF: 'a0c70dc92a07d003a0c80d',
    0x1BBFE3: 'a0c70dc93600f01da0c80dc92a07f015a0ca0dc90f02f00dc93902f008c90101d022a0c60d',
    0x1BBE26: 'c97e03f032a00200c93600f05aa00400c92a07f052',
    0x1BBE5D: 'ad7a0329ff00c90100d0034c1abf',
    0x1BBE88: 'a0c50d802d',
    0x1BBDD1: 'c91b02d013e220a9118d2e01c2202267dd0ea9cb0d4cc3be',
    0x1BBFAC: 'a00000c96d03f02cc8c96e03f026c8c97403f020c8c97503f01aa00000c93b02f012c8c93c02f00cc8c93d02f006c93e02d004c84c9fc0',
    0x1BC081: 'bf00207ea00000c92602f012c8c92702f00cc8c92802f006c92902d0b7c8',
    0x1BBEDF: '0a0a8506a5002908004a4a0406a50229010005060aaabf0080bd29ff01aabf59940e',
    0x1BC027: '0a0a8506a5022908004a4a0406a5004a4a4a29010005060aaabf0080bd29ff01aa688500688502bf59940ee2316b',
    0x008864: 'bf0080bd850629ff01aabf59940e',
    0x1BBF22: 'bf0080bd29ff01aabf59940e',
    0x1BBBF4: 'c231a520',
    0x088A5D: '9de403a8',
    0x0E95DC: '515757',
}
CONDITIONAL_UNCLOSED = (
    'hidden_items_bomb_doors_and_event_recipe', 'ice_rod_direct_dma_adapter',
    'overlay_and_shared_bg_resources', 'active_obj_follower_ancilla_resources',
    'external_scroll_coexistence', 'pyramid_029E6A',
)
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


def conditional_document_identity(document):
    """Shared exact saved-document value identity; no runtime state is inferred."""
    value = dict(profile=document.profile, maps=document.maps,
        properties=document.properties, authoring=document.authoring,
        gameplay_areas=document.gameplay_areas)
    if has_native_resource_history(document):
        value['next_native_resource_id'] = document.next_native_resource_id
    return _sha(_json_bytes(value))


def _conditional_definitions(source, document):
    count = document.profile.get('tile_count')
    _require(type(count) is int and 0 < count <= 4096 and len(source) >= 0x868,
             'CONDITIONAL_DEFINITIONS_INVALID')
    pointer = int.from_bytes(source[0x865:0x868], 'little')
    _require(pointer & 0xFFFF >= 0x8000 and (pointer >> 16) & 0x7F < 0x7E,
             'CONDITIONAL_DEFINITION_POINTER_INVALID')
    at = sheet_table.pc(pointer)
    raw = source[at:at + count * 8]
    _require(len(raw) == count * 8
             and _sha(raw) == document.profile.get('tile16_definition_fingerprint'),
             'CONDITIONAL_DEFINITION_HASH_MISMATCH')
    return pointer, raw


def _conditional_source_policy(source, document, inspection, policy):
    keys = {'kind', 'source_epoch', 'selected_features', 'source_files',
            'native_preimages', 'tail_recipe', 'save_identity', 'area_tilesets'}
    _require(type(policy) is dict and set(policy) == keys
             and policy['kind'] == CONDITIONAL_POLICY_KIND
             and type(policy['source_epoch']) is str
             and re.fullmatch('[0-9a-f]{40}', policy['source_epoch']), 'CONDITIONAL_POLICY_INVALID')
    features = policy['selected_features']
    _require(type(features) is dict and set(features) == {'ice_rod', 'area_tilesets'}
             and all(type(value) is bool for value in features.values()), 'CONDITIONAL_FEATURES_INVALID')
    _require(not features['area_tilesets'] and policy['area_tilesets'] is None,
             'CONDITIONAL_AREA_TYPES_UNQUALIFIED')
    rows = policy['source_files']
    _require(type(rows) is list, 'CONDITIONAL_SOURCE_FILES_UNBOUND')
    files = {}
    for row in rows:
        _require(type(row) is dict and set(row) == {'path', 'sha256', 'source_utf8'},
                 'CONDITIONAL_SOURCE_FILE_INVALID')
        path, text = row['path'], row['source_utf8']
        _require(type(path) is str and path and not Path(path).is_absolute()
                 and '..' not in Path(path).parts and '\0' not in path and path not in files
                 and type(text) is str and _sha(text.encode('utf-8')) == row['sha256'],
                 'CONDITIONAL_SOURCE_FILE_MISMATCH')
        files[path] = '\n'.join(line.split(';', 1)[0] for line in text.splitlines())
    _require(set(CONDITIONAL_SOURCE_FILES) <= set(files), 'CONDITIONAL_SOURCE_FILES_UNBOUND')

    def flag(name, *paths):
        values = [match[1].strip() for path in paths for match in re.finditer(
            r'^\s*!' + name + r'\s*=\s*([^\n]+)$', files[path], re.M)]
        _require(values and all(value in ('0', '1') for value in values),
                 'CONDITIONAL_FEATURE_SOURCE_UNBOUND: ' + name)
        return int(values[-1])

    _require(features['ice_rod'] == (flag('DISABLE_ITEMS', 'Util/macros.asm',
                 'Config/module_flags.asm') == 0)
             and features['area_tilesets'] == bool(flag('ENABLE_OW_AREA_TILESETS',
                 'Util/macros.asm', 'Config/feature_flags.asm')),
             'CONDITIONAL_FEATURE_SOURCE_MISMATCH')
    _require(re.search(r'^\s*incsrc\s+"Items/ice_rod\.asm"\s*$',
                       files['Items/all_items.asm'], re.M), 'CONDITIONAL_ICE_SOURCE_UNBOUND')
    ice = re.sub(r'\s+', '', files['Items/ice_rod.asm']).upper()
    for snippet in ('LDA$03E8:CMP#$08', 'LDA$03E8:CMP#$03',
                    'LDA#$00B7:STA$7E2000,X', 'ORG$0E95DCASL$5757'):
        _require(snippet in ice, 'CONDITIONAL_ICE_SOURCE_UNSUPPORTED')
    door = re.sub(r'\s+', '', files['Overworld/entrances.asm']).upper()
    door_predicate = ('LDA.B$2F:AND.W#$00FF:BNE.NOT_FACING_UP'
        'LDA.LMAP16DEFINITIONS+2,XAND.W#$41FF:CMP.W#$00E9:BEQ.OPEN_DOOR'
        'CMP.W#$0149:BEQ.LEFT_SIDE_CASTLE_DOORCMP.W#$0169:BEQ.LEFT_SIDE_CASTLE_DOOR'
        'TYXLDA.L$7E2002,XASL#3TAXLDA.LMAP16DEFINITIONS+0,X'
        'AND.W#$41FF:CMP.W#$4149:BEQ.RIGHT_SIDE_CASTLE_DOOR'
        'CMP.W#$4169:BEQ.RIGHT_SIDE_CASTLE_DOORCMP.W#$40E9:BNE.CHECK_DOOR_TYPE'
        'DEYDEY.OPEN_DOORTYXLDA.W#$0DA4:JSLOVERWORLD_DRAWMAP16_PERSIST'
        'LDA.W#$0DA6:STA.L$7E2002,XLDY.W#$0002JSLOVERWORLD_DRAWMAP16_ANYWHERE')
    _require(door_predicate in door, 'CONDITIONAL_DOOR_SOURCE_UNSUPPORTED')
    preimages = {}
    _require(type(policy['native_preimages']) is list, 'CONDITIONAL_NATIVE_PREIMAGES_UNBOUND')
    for row in policy['native_preimages']:
        _require(type(row) is dict and set(row) == {'snes', 'payload_hex', 'sha256'}
                 and type(row['snes']) is int and row['snes'] & 0xFFFF >= 0x8000
                 and type(row['payload_hex']) is str
                 and re.fullmatch(r'(?:[0-9a-f]{2})+', row['payload_hex'])
                 and row['snes'] not in preimages, 'CONDITIONAL_NATIVE_PREIMAGE_INVALID')
        raw = bytes.fromhex(row['payload_hex'])
        at = sheet_table.pc(row['snes'])
        _require(_sha(raw) == row['sha256'] and source[at:at+len(raw)] == raw,
                 'CONDITIONAL_NATIVE_PREIMAGE_MISMATCH')
        preimages[row['snes']] = raw
    for at, expected in CONDITIONAL_NATIVE_PREIMAGES.items():
        _require(preimages.get(at) == bytes.fromhex(expected),
                 'CONDITIONAL_NATIVE_PREDICATE_UNSUPPORTED: ' + f'{at:06X}')
    native = preimages.get(0x0E9459)
    _require(native is not None and len(native) == 512, 'CONDITIONAL_NATIVE_TYPES_UNBOUND')
    effective = bytearray(native)
    patches = []
    if features['ice_rod']:
        index = 0x0E95DC - 0x0E9459
        _require(effective[index:index+3] == bytes.fromhex('515757'),
                 'CONDITIONAL_ICE_TYPE_PREIMAGE_MISMATCH')
        effective[index:index+3] = bytes.fromhex('0e5757')
        patches.append(dict(source_path='Items/ice_rod.asm', snes=0x0E95DC,
                            before_hex='515757', after_hex='0e5757'))
    recipe = policy['tail_recipe']
    _require(type(recipe) is dict and set(recipe) == {'binding', 'payload_hex'}
             and type(recipe['binding']) is dict
             and set(recipe['binding']) == {'path', 'sha256'}
             and type(recipe['binding']['path']) is str and recipe['binding']['path']
             and type(recipe['payload_hex']) is str
             and re.fullmatch(r'(?:[0-9a-f]{2})+', recipe['payload_hex']),
             'CONDITIONAL_RECIPE_UNBOUND')
    raw = bytes.fromhex(recipe['payload_hex'])
    _require(_sha(raw) == recipe['binding']['sha256'], 'CONDITIONAL_RECIPE_MISMATCH')
    def unique(pairs):
        result = {}
        for key, value in pairs:
            _require(key not in result, 'CONDITIONAL_RECIPE_DUPLICATE')
            result[key] = value
        return result
    try:
        recipe_rows = json.loads(raw, object_pairs_hook=unique)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError('RESIDENT_GRAPHICS_CONDITIONAL_RECIPE_INVALID') from error
    _require(type(recipe_rows) is dict and set(recipe_rows) == {f'{page:02X}' for page in range(FIRST, END)}
             and all(type(row) is dict for row in recipe_rows.values()), 'CONDITIONAL_RECIPE_INCOMPLETE')
    identity = policy['save_identity']
    _require(type(identity) is dict and set(identity) == {'transfer_id', 'generation', 'operation_id',
        'source_rom_sha256', 'terrain_sha256', 'inspection_sha256', 'document_sha256'}
        and _digest(identity['transfer_id']) and type(identity['generation']) is int
        and 0 < identity['generation'] <= 0xFFFFFFFFFFFFFFFF
        and type(identity['operation_id']) is str and identity['operation_id']
        and type(inspection) is dict and identity['source_rom_sha256'] == _sha(source)
        and inspection.get('source_rom_sha256') == identity['source_rom_sha256']
        and _digest(identity['terrain_sha256'])
        and inspection.get('terrain_sha256') == identity['terrain_sha256']
        and identity['inspection_sha256'] == _sha(_json_bytes(inspection))
        and identity['document_sha256'] == conditional_document_identity(document),
        'CONDITIONAL_SAVE_IDENTITY_MISMATCH')
    return bytes(effective), dict(snes=0x0E9459, byte_count=512,
        source_sha256=_sha(native), effective_sha256=_sha(effective), patches=patches)


def derive_conditional_demands(source, document, inspection, *, source_policy):
    """Derive a closed subset of potential mutations, never runtime admission.

    The wrapper authenticates source epoch/files, Save IDs and recipe identity.
    This pure layer rechecks their value hashes, exact native predicates, every
    quadrant's effective char type, and the source door's actual target offsets.
    """
    _require(type(source) is bytes and isinstance(document, TerrainDocument), 'CONDITIONAL_INPUT_INVALID')
    _require(not has_native_resource_history(document),
             'NATIVE_RESOURCES_UNBOUND: schema9 resources require a typed source-bound binder')
    areas = validated_gameplay_areas(document.gameplay_areas)
    _require({page for area in areas for page in area['maps']} == set(range(FIRST, END))
             and len(document.maps) == 32 and all(type(tiles) is tuple and len(tiles) == 1024
                 for tiles in document.maps), 'CONDITIONAL_PAGES_INCOMPLETE')
    pointer, definitions = _conditional_definitions(source, document)
    types, type_source = _conditional_source_policy(source, document, inspection, source_policy)
    targets = {}

    def words(tile):
        _require(type(tile) is int and 0 <= tile < len(definitions)//8, 'CONDITIONAL_TILE16_INVALID')
        return list(struct.unpack_from('<4H', definitions, tile*8))

    def add(page, target, family, trigger):
        key = (page, target)
        row = targets.setdefault(key, dict(map_id=page, tile16_id=target,
            source_words=words(target), already_authored=target in document.maps[page-FIRST],
            families=set(), triggers={}))
        row['families'].add(family)
        row['triggers'][_json_bytes(trigger)] = trigger

    dig = {0x34, 0x71, 0x35, 0x10D, 0x10F, 0xE1, 0xE2, 0xDA, 0xF8, 0x10E}
    objects = {0x36: 0xDC7, 0x72A: 0xDC8, 0x20F: 0xDCA, 0x239: 0xDCA, 0x101: 0xDC6}
    unsupported = {0x37E: 'grass', 0x21B: 'peg', **dict.fromkeys(
        (0x36D, 0x36E, 0x374, 0x375, 0x23B, 0x23C, 0x23D, 0x23E,
         0x226, 0x227, 0x228, 0x229), 'large_rock')}
    for page in range(FIRST, END):
        for cell, tile in enumerate(document.maps[page-FIRST]):
            original = words(tile)
            quadrants = [types[word & 0x1FF] for word in original]
            _require(tile not in unsupported, 'CONDITIONAL_UNSUPPORTED_FAMILY: '
                     + f'{unsupported.get(tile)}:{page:02X}:{cell}:{tile:04X}')
            trigger = dict(map_id=page, cell_index=cell, source_tile16_id=tile,
                           source_words=original, quadrant_types=quadrants)
            if tile in dig:
                add(page, 0xDC9, 'dig', dict(trigger, action='037A.low==1'))
            if tile in objects:
                add(page, objects[tile], 'bush' if tile in (0x36, 0x72A) else 'small_object', trigger)
            if source_policy['selected_features']['ice_rod'] and any(value in (3, 8) for value in quadrants):
                add(page, 0xB7, 'ice_rod_water', dict(trigger,
                    eligible_quadrants=[q for q, value in enumerate(quadrants) if value in (3, 8)]))

    for area in sorted(areas, key=lambda row: row['parent_map_id']):
        mask = {'small': 0, 'wide': 1, 'tall': 8, 'large': 9}[area['size']]
        def cell_at(raw):
            _require(0 <= raw < 0x2000 and raw % 2 == 0, 'CONDITIONAL_DOOR_TARGET_OUT_OF_DOMAIN')
            quadrant = (((raw & 0x1000) >> 12) * 8 + ((raw & 0x40) >> 6)) & mask
            page = area['parent_map_id'] + quadrant
            cell = ((raw >> 7) & 31)*32 + ((raw >> 1) & 31)
            return page, cell, document.maps[page-FIRST][cell]
        for raw in range(0, 0x2000, 2):
            query_quadrant = ((raw & 0x1000) >> 9) | ((raw & 0x40) >> 6)
            if query_quadrant & ~mask:
                continue
            page, cell, tile = cell_at(raw)
            original = words(tile)
            predicate = original[1] & 0x41FF
            if predicate == 0xE9:
                left, branch = raw, 'current_q1_00E9'
            elif predicate in (0x149, 0x169) or raw+2 >= 0x2000:
                continue
            else:
                neighbor_page, neighbor_cell, neighbor_tile = cell_at(raw+2)
                if words(neighbor_tile)[0] & 0x41FF != 0x40E9:
                    continue
                left, branch = raw-2, 'neighbor_q0_40E9'
            for offset, target in ((left, 0xDA4), (left+2, 0xDA6)):
                target_page, target_cell, _ = cell_at(offset)
                evidence = dict(map_id=page, cell_index=cell, source_tile16_id=tile,
                    source_words=original, native_raw_offset=raw, branch=branch,
                    target_raw_offset=offset, target_cell_index=target_cell)
                if branch == 'neighbor_q0_40E9':
                    evidence['neighbor'] = dict(map_id=neighbor_page, cell_index=neighbor_cell,
                        source_tile16_id=neighbor_tile, source_words=words(neighbor_tile))
                add(target_page, target, 'wooden_door', evidence)
    rows = []
    for _, row in sorted(targets.items()):
        rows.append(dict(row, families=sorted(row['families']),
                         triggers=[value for _, value in sorted(row['triggers'].items())]))
    result = dict(kind=CONDITIONAL_KIND, scope='saved_terrain_direct_trigger_subset',
        source_policy=copy.deepcopy(source_policy),
        source_policy_sha256=_sha(_json_bytes(source_policy)),
        source_binding=dict(source_rom_sha256=_sha(source),
            terrain_sha256=source_policy['save_identity']['terrain_sha256'],
            inspection_sha256=_sha(_json_bytes(inspection)),
            document_sha256=conditional_document_identity(document),
            tile16_definition_snes=pointer, tile16_definition_sha256=_sha(definitions)),
        native_type_source=type_source, rows=rows,
        additional_rows=[dict(map_id=row['map_id'], tile16_id=row['tile16_id'])
                         for row in rows if not row['already_authored']],
        unclosed_families=list(CONDITIONAL_UNCLOSED), known_conditional_demands_ready=True,
        full_residency_ready=False, appearance_coherent=False, allocation_granted=False,
        publication_authorized=False, ordinary_build_ready=False, runtime_admission=False,
        compiled_consumers_verified=False, resource_closure_verified=False,
        rom_written=False, selected=False)
    result['witness_sha256'] = _sha(_json_bytes(result))
    return result


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


def _plan_area(area, document, assets, definitions, read_sheet, conditional_tiles=None):
    demands, references, claims = {}, [], {}
    for map_id in area['maps']:
        data = assets[map_id, 0]
        palette = data['palette']['words']
        tiles = set(document.maps[map_id - FIRST])
        if conditional_tiles is not None:
            tiles.update(conditional_tiles.get(map_id, ()))
        for tile in sorted(tiles):
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


def plan_resident_graphics(source, document, inspection, *, terrain_sha256, provenance,
                           conditional_demands=None):
    """Return deterministic ungranted DATA; native/shared-resource readiness stays false."""
    _require(not has_native_resource_history(document),
             'NATIVE_RESOURCES_UNBOUND: schema9 resources require a typed source-bound binder')
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
    conditional_tiles = None
    if conditional_demands is not None:
        _require(type(conditional_demands) is dict
                 and type(conditional_demands.get('source_policy')) is dict,
                 'CONDITIONAL_WITNESS_UNBOUND')
        expected = derive_conditional_demands(source, document, inspection,
            source_policy=conditional_demands['source_policy'])
        _require(conditional_demands == expected, 'CONDITIONAL_WITNESS_MISMATCH')
        _require(expected['source_binding']['terrain_sha256'] == terrain_sha256,
                 'CONDITIONAL_TERRAIN_MISMATCH')
        conditional_tiles = {}
        for row in expected['rows']:
            conditional_tiles.setdefault(row['map_id'], set()).add(row['tile16_id'])
    read_sheet, sheets = _source_sheets(source)
    assets = _inspection_rows(source, document, inspection, terrain_sha256, read_sheet)
    planned = [_plan_area(area, document, assets, definitions, read_sheet, conditional_tiles)
               for area in sorted(areas, key=lambda row: row['parent_map_id'])]
    plan = dict(kind=KIND, scope='terrain_resource_data_only',
        source_binding=dict(source_rom_sha256=_sha(source), source_byte_count=len(source),
            terrain_sha256=terrain_sha256, inspection_sha256=_sha(_json_bytes(inspection)),
            document_sha256=conditional_document_identity(document),
            tile16_definition_snes=pointer, tile16_definition_sha256=_sha(definitions)),
        provenance=copy.deepcopy(provenance), provenance_sha256=_sha(_json_bytes(provenance)),
        terrain_plan_ready=all(area['terrain_plan_ready'] for area in planned),
        full_residency_ready=False, appearance_coherent=False,
        allocation_granted=False, publication_authorized=False,
        ordinary_build_ready=False, runtime_admission=False, compiled_consumers_verified=False,
        static_namespace=list(STATIC_SLOTS), animated_namespace=list(ANIMATED_SLOTS),
        unknowns=list(UNKNOWNS), areas=planned,
        decoded_sheets=[sheets[sheet] for sheet in sorted(sheets)])
    if conditional_demands is not None:
        plan['scope'] = 'terrain_and_known_conditional_resource_data_only'
        plan['conditional_demands'] = copy.deepcopy(expected)
    plan['plan_sha256'] = _sha(_json_bytes(plan))
    return plan


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
    _require(type(resident_plan) is dict and resident_plan.get('kind') == KIND
             and resident_plan.get('terrain_plan_ready') is True,
             'NATIVE_TERRAIN_PLAN_REQUIRED')
    _require(type(tile16_count) is int and 0 < tile16_count <= 4096,
             'NATIVE_TILE16_COUNT_INVALID')
    supplied = resident_plan.get('plan_sha256')
    _require(_digest(supplied) and supplied == _sha(_json_bytes(
        {key: value for key, value in resident_plan.items() if key != 'plan_sha256'})),
        'NATIVE_SOURCE_PLAN_MISMATCH')
    _require(all(resident_plan.get(key) is False for key in (
        'full_residency_ready', 'appearance_coherent', 'allocation_granted',
        'publication_authorized', 'ordinary_build_ready', 'runtime_admission',
        'compiled_consumers_verified')), 'NATIVE_SOURCE_AUTHORITY_INVALID')
    source_areas = resident_plan.get('areas')
    _require(type(source_areas) is list and 0 < len(source_areas) <= 32,
             'NATIVE_AREAS_INVALID')
    try:
        layout = validated_gameplay_areas(tuple(dict(parent_map_id=area['parent_map_id'],
            size=area['size'], maps=area['maps']) for area in source_areas))
    except (KeyError, TypeError, ValueError) as error:
        raise ValueError('RESIDENT_GRAPHICS_NATIVE_AREAS_INVALID') from error
    _require({page for area in layout for page in area['maps']} == set(range(FIRST, END)),
             'NATIVE_PAGES_INCOMPLETE')
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
        areas.append(dict(area_index=area_index, parent_map_id=parent,
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
    counts['page_directory'] = (END - FIRST) * NATIVE_DIRECTORY_STRIDE
    counts['animation_directory'] = (END - FIRST) * NATIVE_ANIMATION_DIRECTORY_STRIDE
    result = dict(kind=NATIVE_KIND, abi_version=NATIVE_ABI_VERSION,
        source_plan_sha256=supplied, tile16_count=tile16_count,
        directory_label='LyraResidentPageDirectory', directory_stride=NATIVE_DIRECTORY_STRIDE,
        animation_directory_label='LyraResidentAnimationDirectory',
        animation_directory_stride=NATIVE_ANIMATION_DIRECTORY_STRIDE,
        block_shift=NATIVE_BLOCK_SHIFT, block_directory_bytes=NATIVE_BLOCK_DIRECTORY_BYTES,
        first_map=FIRST, end_map=END, row_limit=255, pages=pages, areas=areas, blobs=blobs,
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
    _require(native_plan.get('directory_stride') == 8
             and native_plan.get('block_shift') == 5
             and native_plan.get('block_directory_bytes') == 128
             and native_plan.get('directory_label') == 'LyraResidentPageDirectory'
             and native_plan.get('animation_directory_label') == 'LyraResidentAnimationDirectory'
             and native_plan.get('animation_directory_stride') == NATIVE_ANIMATION_DIRECTORY_STRIDE
             and native_plan.get('first_map') == FIRST and native_plan.get('end_map') == END
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
                 and label not in by_label and row.get('role') in (
                     'page_index', 'page_words', 'static_chr', 'animation', 'palette'),
                 'NATIVE_BLOBS_INVALID')
        by_label[label] = _verified_payload(row)
        _require(0 < len(by_label[label]) <= 0x8000, 'NATIVE_BLOB_BANK_CAPACITY')
    pages = native_plan.get('pages')
    areas = native_plan.get('areas')
    _require(type(pages) is list and [row.get('map_id') for row in pages] == list(range(FIRST, END))
             and type(areas) is list and 0 < len(areas) <= 32,
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
    expected_counts['page_directory'] = 256
    expected_counts['animation_directory'] = (END - FIRST) * NATIVE_ANIMATION_DIRECTORY_STRIDE
    _require(native_plan.get('byte_counts') == expected_counts
             and native_plan.get('unaligned_byte_count') == sum(expected_counts.values()),
             'NATIVE_BYTE_COUNT_INVALID')
    return by_label


def emit_native_resident_abi(native_plan, *, data_pc, capacity, preimage,
                             binary_path='binaries/resident-atlas.bin'):
    """Emit bytes/source for an explicit caller-owned ROM interval, without I/O.

    This mechanically places each blob inside one LoROM bank. It accepts no
    default address and makes no claim that the interval or runtime is granted.
    The owning publisher must authenticate and rederive the complete plan.
    """
    by_label = validate_native_resident_abi(native_plan)
    _require(type(data_pc) is int and type(capacity) is int
             and 0 <= data_pc < data_pc + capacity <= 0x400000
             and type(preimage) is bytes and len(preimage) == capacity,
             'NATIVE_ORIGIN_PREIMAGE_REQUIRED')
    _require(type(binary_path) is str and re.fullmatch(r'binaries/[A-Za-z0-9_-]+\.bin', binary_path),
             'NATIVE_BINARY_PATH_INVALID')
    cursor, binary, placements = data_pc, bytearray(), []

    def snes(pc):
        return 0x800000 | ((pc // 0x8000) << 16) | 0x8000 | (pc % 0x8000)

    def place(label, raw, role):
        nonlocal cursor
        if cursor % 0x8000 + len(raw) > 0x8000:
            cursor = (cursor // 0x8000 + 1) * 0x8000
        _require(cursor + len(raw) <= data_pc + capacity, 'NATIVE_ALLOCATION_CAPACITY')
        record = dict(label=label, role=role, pc=[cursor, cursor + len(raw)],
            snes=snes(cursor), byte_count=len(raw), sha256=_sha(raw),
            binary_offset=len(binary), preimage_sha256=_sha(
                preimage[cursor-data_pc:cursor-data_pc+len(raw)]))
        placements.append(record)
        binary.extend(raw)
        cursor += len(raw)
        return record

    directory = place(native_plan['directory_label'], bytes(256), 'page_directory')
    animation_directory = place(native_plan['animation_directory_label'],
        bytes((END - FIRST) * NATIVE_ANIMATION_DIRECTORY_STRIDE), 'animation_directory')
    for blob in native_plan['blobs']:
        place(blob['label'], by_label[blob['label']], blob['role'])
    addresses = {row['label']: row['snes'] for row in placements}
    directory_raw = b''.join(addresses[page['index_label']].to_bytes(3, 'little')
        + addresses[page['words_label']].to_bytes(3, 'little')
        + bytes((page['area_index'], page['row_count'])) for page in native_plan['pages'])
    binary[:256] = directory_raw
    directory['sha256'] = _sha(directory_raw)
    animation_raw = bytearray()
    for page in native_plan['pages']:
        area = native_plan['areas'][page['area_index']]
        animation_raw.extend(b''.join((addresses[label] if label else 0).to_bytes(3, 'little')
                                     for label in area['animation_labels']))
        animation_raw.extend(area['animation_byte_count'].to_bytes(2, 'little'))
    offset = animation_directory['binary_offset']
    binary[offset:offset + len(animation_raw)] = animation_raw
    animation_directory['sha256'] = _sha(animation_raw)
    lines = ['; Generated resident ABI v1; unselected terrain census only.', 'pushpc']
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
                lines.append(f'{alias} = {label}')
    lines += ['pullpc', '']
    constants = (f'!LYRA_CURRENT_RESIDENT_ABI_VERSION = {NATIVE_ABI_VERSION}\n'
        + f'!LYRA_CURRENT_RESIDENT_TILE16_COUNT = {native_plan["tile16_count"]}\n'
        + f'!LYRA_CURRENT_RESIDENT_DIRECTORY = ${directory["snes"]:06X}\n')
    constants += (f'!LYRA_CURRENT_RESIDENT_ANIMATION_DIRECTORY = ${animation_directory["snes"]:06X}\n')
    return dict(kind='lyra.resident_atlas_native_emission.v1',
        abi_sha256=native_plan['abi_sha256'], data_pc=[data_pc, data_pc + capacity],
        preimage_sha256=_sha(preimage), used_pc_end=cursor,
        used_extent_bytes=cursor-data_pc, bank_padding_bytes=cursor-data_pc-len(binary),
        binary_path=binary_path, payload_hex=bytes(binary).hex(), payload_sha256=_sha(binary),
        placements=placements, animation_directory_byte_count=len(animation_raw),
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
        preimage=preimage, binary_path=emission.get('binary_path'))
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
