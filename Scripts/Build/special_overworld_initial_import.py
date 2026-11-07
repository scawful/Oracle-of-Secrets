"""Complete initial special-overworld composition for the selected Oracle engine.

Reuse the native table, actor, authoring and directory codecs. This operation
prepares a complete editable image; it neither adopts a project nor claims a
runnable build. The normal saved-native Build remains the runtime producer.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import struct

import lyra_native_loaders as native


IMAGE_SIZE = 0x400000
QUADRANT_CAPACITY = 4432
SIZES = {'small': 0, 'large': 1, 'wide': 2, 'tall': 3}
FOOTPRINTS = {'small': (0,), 'large': (0, 1, 8, 9),
              'wide': (0, 1), 'tall': (0, 8)}
ORIGINAL_POOLS = ((0x58000, 0x5FE70), (0x60000, 0x6411F),
                  (0x130000, 0x138000))


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _integer(value, low, high, name):
    native.require(type(value) is int and low <= value <= high,
                   f'Invalid initial import {name}')
    return value


def _bytes(values, name):
    native.require(type(values) is list and all(type(v) is int and 0 <= v <= 255
                                              for v in values),
                   f'Invalid initial import {name} bytes')
    return bytes(values)


def _areas(rows):
    native.require(type(rows) is list and 1 <= len(rows) <= 32,
                   'Initial import requires explicit gameplay areas')
    result = {}
    for row in rows:
        parent = _integer(row['parent_map_id'], 160, 191, 'area parent')
        size = row['size']
        native.require(size in SIZES, 'Invalid initial import area size')
        members = row['maps']
        native.require(type(members) is list and all(type(v) is int for v in members)
                       and members == [parent + v for v in FOOTPRINTS[size]],
                       'Initial import area footprint differs')
        native.require(size not in ('large', 'wide') or parent % 8 < 7,
                       'Initial import area wraps a map row')
        for member in members:
            native.require(160 <= member < 192 and member not in result,
                           'Initial import areas overlap or leave the tail')
            result[member] = (parent, size)
    native.require(set(result) == set(range(160, 192)),
                   'Initial import must assign all32 tail maps exactly once')
    return result


def _authenticate(source, terrain_raw, areas_raw, plan, inspection):
    native.require(type(source) is bytes and 0x200000 <= len(source) <= IMAGE_SIZE,
                   'Initial import needs a headerless source ROM')
    native.require(native.read_native_directory(source) is None,
                   'Initial import refuses an already native source')
    native.require(plan['schema'] == 'yaze.special-overworld-terrain-import.v1'
                   and plan['capacity'] == 192 and plan['complete_image'] is False,
                   'Unsupported initial terrain plan')
    native.require(sha(source) == plan['source_rom_sha256']
                   == inspection['source_rom_sha256'], 'Initial import source identity differs')
    native.require(sha(terrain_raw) == plan['source_terrain_sha256']
                   == inspection['terrain_sha256'], 'Initial import terrain identity differs')
    native.require(sha(areas_raw) == plan['gameplay_areas_sha256'],
                   'Initial import gameplay-area identity differs')
    areas = json.loads(areas_raw)
    native.require(areas == plan['gameplay_areas'], 'Initial import gameplay areas differ')
    assignments = _areas(areas)
    document = json.loads(terrain_raw)
    native.require(not document.get('edge_connections') and not document.get('flight_points'),
                   'Initial import cannot discard authored edge connections or flight points')
    native.require(not document.get('gameplay_areas')
                   or document['gameplay_areas'] == areas,
                   'Saved document and supplied gameplay areas differ')
    dictionary = native.pc(native.CURRENT_DICTIONARIES[400])
    native.require(document['profile']['tile_count'] == 4096
                   and document['profile']['tile16_definition_fingerprint']
                   == sha(source[dictionary:dictionary + 4096 * 8]),
                   'Initial import Tile16 source fingerprint differs')
    rows = document['maps']
    native.require(type(rows) is list and len(rows) == 32
                   and [row['map_id'] for row in rows] == list(range(160, 192)),
                   'Initial import needs the32 saved tail maps in document order')
    native.require(inspection['map_count'] == 32
                   and inspection['asset_binding_mismatches'] == 0,
                   'Initial import asset bindings differ')
    native.require(len(plan['geometry']) == 192, 'Initial import geometry is incomplete')
    for member, (parent, size) in assignments.items():
        geometry = plan['geometry'][member]
        native.require(geometry['parent'] == parent and geometry['size'] == size
                       and len(geometry['words']) == 8
                       and all(type(v) is int and 0 <= v <= 65535
                               for v in geometry['words']),
                       'Initial import terrain and gameplay geometry disagree')
    assets = {}
    for row in inspection['map_assets']:
        value = row['native_assets']
        key = (row['map_id'], value['state'])
        native.require(key not in assets and row['state'] == key[1]
                       and value['schema'] == 'yaze.lyra-native-resolution.v1'
                       and row['binding_changed'] is False
                       and row['current_binding'] == value['native_base_binding'],
                       'Initial import asset projection is stale or duplicated')
        assets[key] = value
    native.require(set(assets) == {(m, phase) for m in range(160, 192) for phase in range(3)},
                   'Initial import needs96 explicit map/state asset projections')
    seed = _integer(inspection['donor_map'], 0, 159, 'resolver seed')
    native.require(all(value['resolver_seed_map'] == seed for value in assets.values()),
                   'Initial import resolver seed differs')
    baseline = source.ljust(IMAGE_SIZE, b'\0')
    native.require(sha(baseline) == plan['initial_image_sha256'],
                   'Initial import planner baseline differs')
    return document, assets, baseline, seed


def _terrain(image, baseline, plan):
    families = {f.id: f for f in native.current_table_layout(native.TABLE_BASE)}
    native.require(plan['high_table_pc'] == native.pc(families[20].snes)
                   and plan['low_table_pc'] == native.pc(families[21].snes)
                   and plan['stream_start'] == native.pc(0x488000)
                   and plan['stream_end'] == native.pc(0x4C8000)
                   and plan['native_prefix'] == dict(high_table_pc=0x1794D,
                                                    low_table_pc=0x17B2D, map_count=160),
                   'Initial terrain plan leaves selected engine reservations')
    allowed = ((plan['high_table_pc'], plan['high_table_pc'] + 192 * 3),
               (plan['low_table_pc'], plan['low_table_pc'] + 192 * 3),
               (0x1794D, 0x1794D + 160 * 3), (0x17B2D, 0x17B2D + 160 * 3),
               (plan['stream_start'], plan['stream_end']))
    spans = []
    for write in plan['terrain_writes']:
        at = _integer(write['pc'], 0, IMAGE_SIZE - 1, 'terrain offset')
        before, after = (_bytes(write[k], 'terrain ' + k) for k in ('before', 'after'))
        end = at + len(after)
        native.require(before and len(before) == len(after)
                       and any(a <= at < end <= b for a, b in allowed),
                       'Initial terrain write leaves owned storage')
        native.require(all(at >= b or end <= a for a, b in spans),
                       'Initial terrain writes overlap')
        native.require(baseline[at:end] == before, 'Initial terrain preimage differs')
        image[at:end] = after
        spans.append((at, end))
    for table_id, legacy in ((20, 0x1794D), (21, 0x17B2D)):
        at = native.pc(families[table_id].snes)
        native.require(image[at:at + 160 * 3] == image[legacy:legacy + 160 * 3],
                       'Initial canonical and original160 pointers disagree')
    definitions = _integer(plan['dictionary_definition_count'], 4,
                           QUADRANT_CAPACITY * 4, 'dictionary definition count')
    native.require(definitions % 4 == 0 and len(plan['quadrant_bytes']) == 4,
                   'Initial import requires four complete dictionary quadrants')
    for quadrant, values in enumerate(plan['quadrant_bytes']):
        payload = _bytes(values, 'dictionary quadrant')
        native.require(len(payload) == definitions // 4 * 6,
                       'Initial dictionary quadrant extent differs')
        at = native.pc(native.CURRENT_DICTIONARIES[401 + quadrant])
        image[at:at + QUADRANT_CAPACITY * 6] = payload.ljust(QUADRANT_CAPACITY * 6, b'\0')


def _sprite_palette(source, maps, assets, seed, choices, map_id, phase):
    groups = 0x75580
    selected = _integer(assets[map_id, phase]['effective_sprite_palette'], 0, 255,
                        'sprite palette selector')
    pair = source[groups + selected * 2:groups + selected * 2 + 2]
    if 255 not in pair:
        return selected
    native.require(maps[map_id]['authoring']['properties']['sprite_palettes'][phase] < 0,
                   'Initial import cannot reinterpret an explicit sprite palette')
    native.require(seed > 0, 'Inherited sprite palette needs a preceding resolver page')
    previous = source[0x7B41 + seed - 1]
    previous_pair = source[groups + previous * 2:groups + previous * 2 + 2]
    resolved = bytes((previous_pair[i] if previous_pair[i] != 255 else 0)
                     if value == 255 else value for i, value in enumerate(pair))
    candidates = sorted({previous} | {v['effective_sprite_palette'] for v in assets.values()})
    matches = [value for value in candidates if source[groups + value * 2:
                                                       groups + value * 2 + 2] == resolved]
    native.require(matches, 'No existing concrete palette preserves inherited sprite colors')
    selected = matches[0]
    choices.append(dict(map_id=map_id, phase=phase, native_selector=selected,
                        resolved_pair=list(resolved)))
    return selected


def _tables(source, image, document, assets, seed, plan):
    maps = {row['map_id']: row for row in document['maps']}
    geometry = {m: dict(parent=plan['geometry'][m]['parent'],
                        area_size=SIZES[plan['geometry'][m]['size']]) for m in maps}
    authored = {m: {key: maps[m]['authoring'][key] for key in ('sprites', 'doors', 'exits')}
                for m in maps}
    streams, metadata = native.lower_authored_actor_lists(authored, geometry)
    actors, pointers = native.lower_actor_lists(streams, data_snes=native.ACTORS_BASE,
                                               capacity=0x8000)
    layout = native.current_table_layout(native.TABLE_BASE)
    defaults = {}
    for family in layout:
        if family.name == 'role':
            defaults[family.name] = 0
            continue
        row = seed if family.legacy_first == 0 else 0
        at = native.pc(family.legacy_snes) + row * family.stride
        raw = source[at:at + family.stride]
        defaults[family.name] = list(raw) if family.stride == 8 else int.from_bytes(raw, 'little')
    hidden = next(f for f in layout if f.name == 'hidden_items')
    empty = None
    for m in range(160):
        at = native.pc(hidden.legacy_snes) + m * 2
        pointer = int.from_bytes(source[at:at + 2], 'little')
        if pointer >= 0x8000 and source[native.pc(0x9B0000 | pointer):
                                      native.pc(0x9B0000 | pointer) + 2] == b'\xff\xff':
            empty = pointer
            break
    native.require(empty is not None, 'No existing empty native hidden-item list')
    flags, palettes, rows, choices = bytearray(192), bytearray(64 * 256), {}, []
    for m, saved in maps.items():
        properties, geometry = saved['authoring']['properties'], plan['geometry'][m]
        row = dict(defaults)
        row.update(parent=geometry['parent'], area_size=SIZES[geometry['size']], role=0,
                   main_palette=properties['main_palette'], animated=properties['animated_sheet'],
                   gfx=list(properties['graphics_sheets']), sign_text=properties['message_id'],
                   palette_set=properties['palette_set'], hidden_items=empty, bomb_doors=0)
        row['special_entry_gfx'] = row['area_gfx']
        row['bg_color'] = assets[m, 0]['palette']['words'][0]
        for table_id, value in zip(range(8, 16), geometry['words']):
            row[next(f.name for f in layout if f.id == table_id)] = value
        for phase in range(3):
            row[f'sprite_phase{phase}'] = pointers[m, phase]
            row[('special_sprite_gfx', 'special_sprite_gfx_phase1',
                 'special_sprite_gfx_phase2')[phase]] = assets[m, phase]['effective_sprite_graphics']
            row[('special_sprite_palettes', 'special_sprite_palettes_phase1',
                 'special_sprite_palettes_phase2')[phase]] = _sprite_palette(
                     source, maps, assets, seed, choices, m, phase)
        for phase in range(4):
            row[f'music_phase{phase}'] = properties['music'][phase]
        row['music_dark_special'] = properties['music'][0]
        for table_id, name in ((20, 'high'), (21, 'low')):
            at = plan[f'{name}_table_pc'] + m * 3
            row[f'map32_{name}'] = int.from_bytes(image[at:at + 3], 'little')
        flags[m] = 1 | (2 if 'background_palette' in properties else 0)
        if 'background_palette' in properties:
            colors = properties['background_palette']
            native.require(len(colors) == 128 and all(type(v) is int and 0 <= v <= 0x7FFF
                                                      for v in colors),
                           'Invalid initial background palette')
            struct.pack_into('<128H', palettes, (m - 128) * 256, *colors)
        rows[m] = row
    lowered = native.lower_tables(source, rows, table_base=native.TABLE_BASE,
                                   legacy_roles=[255] * 160)
    for table_id, name in ((20, 'high'), (21, 'low')):
        at = plan[f'{name}_table_pc']
        lowered[table_id] = bytes(image[at:at + 192 * 3])
    for family in layout:
        at = native.pc(family.snes)
        image[at:at + len(lowered[family.id])] = lowered[family.id]
    for address, payload in ((native.ACTORS_BASE, actors),
                             (native.APPEARANCE_FLAGS_BASE, flags),
                             (native.APPEARANCE_PALETTES_BASE, palettes),
                             (native.AUTHORING_METADATA_BASE, metadata)):
        at = native.pc(address)
        image[at:at + len(payload)] = payload
    entries = [(f.id, f.snes, 192) for f in layout]
    entries += [(100, native.ACTORS_BASE, len(actors)), (200, 0x0B8000, 0x7E70),
                (201, 0x0C8000, 0x411F), (202, 0x268000, 0x8000)]
    entries += [(210 + i, (0x48 + i) << 16 | 0x8000, 0x8000) for i in range(4)]
    entries += [(400, native.CURRENT_DICTIONARIES[400], 4096)]
    entries += [(401 + i, native.CURRENT_DICTIONARIES[401 + i], QUADRANT_CAPACITY)
                for i in range(4)]
    entries += list(native.initial_appearance_entries(192)) + [native.initial_authoring_entry(192)]
    return entries, dict(actor_payload_sha256=sha(actors), metadata_sha256=sha(metadata),
                         explicit_sprite_palette_choices=choices, empty_hidden_pointer=empty)


def prepare_initial_import(source, terrain_raw, areas_raw, plan, inspection, bootstrap):
    """Return a complete editable image and evidence; never write caller inputs."""
    try:
        document, assets, baseline, seed = _authenticate(source, terrain_raw, areas_raw,
                                                        plan, inspection)
        native.require(bootstrap['source_rom_sha256'] == sha(source)
                       and bootstrap['padded_source_sha256'] == sha(baseline)
                       and bootstrap['complete_image'] is False,
                       'Initial bootstrap source identity differs')
        image = bytearray(baseline)
        _terrain(image, baseline, plan)
        entries, detail = _tables(source, image, document, assets, seed, plan)
        spans = []
        for patch in bootstrap['patches']:
            at = _integer(patch['pc'], 0, IMAGE_SIZE - 1, 'bootstrap offset')
            before, after = (bytes.fromhex(patch[k]) for k in ('before_hex', 'after_hex'))
            end = at + len(after)
            native.require(before and len(before) == len(after) and end <= IMAGE_SIZE
                           and all(at >= b or end <= a for a, b in spans),
                           'Initial bootstrap patch extent differs or overlaps')
            native.require(image[at:end] == before, 'Initial bootstrap preimage differs')
            image[at:end] = after
            spans.append((at, end))
        for key, table_id in (('directory300', 300), ('directory301', 301)):
            row = bootstrap[key]
            at = native.pc(row['snes'])
            count = row['count']
            stride = 1 if table_id == 300 else 16
            native.require(sha(image[at:at + count * stride]) == row['sha256'],
                           'Initial bootstrap payload identity differs')
            entries.append((table_id, row['snes'], count))
        native.verify_dictionary_readers(bytes(image), {key: (address, count)
                                                       for key, address, count in entries})
        directory = native.encode_revision4_directory(bytes(image), entries,
                                                       tail_actor_bank=native.ACTORS_BASE >> 16)
        image[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE] = directory
        native.require(native.read_native_directory(bytes(image))[0] == 192,
                       'Complete initial image directory did not validate')
        native.require(all(image[a:b] == baseline[a:b] for a, b in ORIGINAL_POOLS),
                       'Initial import changed original terrain stream pools')
        dictionary = native.pc(native.CURRENT_DICTIONARIES[400])
        native.require(image[dictionary:dictionary + 4096 * 8]
                       == baseline[dictionary:dictionary + 4096 * 8],
                       'Initial import changed original Tile16 definitions')
        return bytes(image), dict(source_rom_sha256=sha(source),
            source_terrain_sha256=sha(terrain_raw), gameplay_areas_sha256=sha(areas_raw),
            image_sha256=sha(image), byte_count=len(image), capacity=192,
            gameplay_area_count=len(plan['gameplay_areas']), descriptor_revision=4,
            native_payload_count=len(entries), appearance_activation_ready=False,
            original_geometry_preserved=True,
            original_stream_pools_preserved=True, complete_image=True,
            runtime_qualified=False, adopted=False, **detail)
    except (KeyError, TypeError, IndexError, struct.error) as error:
        raise ValueError(f'Malformed initial import input: {error}') from error


def initialize_dormant_appearance(image, exported):
    """Seed Customize colors from the actual model, preserving active palettes."""
    native.require(type(image) is bytes and exported['source_rom_sha256'] == sha(image),
                   'Initial appearance projection source differs')
    installed = native.read_native_directory(image)
    native.require(installed is not None and installed[0] == 192,
                   'Initial appearance needs the complete native192 image')
    entries = installed[2]
    pages = exported['pages']
    native.require(len(pages) == 64 and {p['map_id'] for p in pages} == set(range(128, 192)),
                   'Initial appearance projection must cover all64 special screens')
    flags_at = native.pc(entries[410][0])
    palette_at = native.pc(entries[411][0])
    output, initialized = bytearray(image), []
    for page in pages:
        map_id = _integer(page['map_id'], 128, 191, 'appearance map')
        if image[flags_at + map_id] == 3:
            continue  # Explicit saved custom colors remain byte exact.
        words = page.get('background_palette_words')
        native.require(type(words) is list and len(words) == 128
                       and all(type(v) is int and 0 <= v <= 0x7FFF for v in words),
                       'Invalid initial appearance projection colors')
        at = palette_at + (map_id - 128) * 256
        output[at:at + 256] = struct.pack('<128H', *words[:128])
        initialized.append(map_id)
    rows = [(key, address, count) for key, (address, count) in entries.items()]
    directory = native.encode_revision4_directory(bytes(output), rows, tail_actor_bank=installed[1])
    output[native.DIRECTORY_PC:native.DIRECTORY_PC + native.DIRECTORY_SIZE] = directory
    native.read_native_directory(bytes(output))
    return bytes(output), dict(appearance_activation_ready=True,
        dormant_appearance_maps=sorted(initialized),
        appearance_projection_source_sha256=sha(image))
