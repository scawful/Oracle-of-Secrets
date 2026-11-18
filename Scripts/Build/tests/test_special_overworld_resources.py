"""Synthetic native-source compiler controls; no production allocation proof."""
import copy
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import special_overworld_resources as R

SPEC = importlib.util.spec_from_file_location(
    'native_resource_fixture', Path(__file__).with_name('test_lyra_native_loaders.py'))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class SavedNativeTerrainResourcesTest(unittest.TestCase):
    def setUp(self):
        self.fixture = F.Revision4AppearanceDirectoryTest()
        self.fixture.setUp()
        image = self.fixture.image
        records = {entry_id: R.native.pc(address) for entry_id, address, _ in self.fixture.entries}
        image[self.fixture.flags_pc:self.fixture.flags_pc + 192] = bytes(192)
        image[self.fixture.colors_pc:self.fixture.colors_pc + 64 * 256] = bytes(64 * 256)
        for page in range(128, 192):
            image[records[7] + page] = page
            image[records[4] + page] = 1
        for page, color in zip((0xB0, 0xB1, 0xB8, 0xB9), (0, 0x1234, 0x2345, 0x3456)):
            image[records[7] + page] = 0xB0
            image[records[30] + page] = 1
            image[self.fixture.flags_pc + page] = 3
            struct.pack_into('<H', image, self.fixture.colors_pc + (page - 128) * 256 + 82, color)
        # Every definition uses char0 in palette bank2. The graphics stream is
        # real LC-LZ2 literal data decoded through the retained sheet codec.
        for tile in range(4096):
            struct.pack_into('<4H', image, records[400] + tile * 8, *([2 << 10] * 4))
        raw = R.sheet_codec.grid_to_sheet([[1] * 128 for _ in range(32)])
        compressed = bytearray()
        for chunk in (raw[:1024], raw[1024:]):
            size = len(chunk) - 1
            compressed.extend((0xE0 | (size >> 8), size & 255))
            compressed.extend(chunk)
        compressed.append(255)
        image[0x280000:0x280000 + len(compressed)] = compressed
        for sheet in (0, 1):
            for table, value in zip((R.sheet_table.TBL_BANK, R.sheet_table.TBL_HIGH,
                                     R.sheet_table.TBL_LOW), (0x50, 0x80, 0)):
                image[R.native.pc(table) + sheet] = value
        self.source = self.fixture.installed()
        self.exported = self.make_export(self.source)

    @staticmethod
    def seal(value):
        return dict(native_source=value, native_source_sha256=R._sha(R._json_bytes(value)))

    def make_export(self, source):
        capacity, _, entries = R.native.read_native_directory(source)
        read, _ = R._source_sheets(source)
        decoded = read(0)[0]
        animated = read(1)[0]
        pages, areas = [], {}
        for page in range(128, capacity):
            def row(entry_id, width=1, index=page):
                at = R.native.pc(entries[entry_id][0]) + index * width
                return source[at:at + width]
            flags = row(410)[0]
            words = list(struct.unpack('<128H', row(411, 256, page - 128)))
            palette = words + [0] * 128
            states = []
            for state in range(3):
                slots = []
                for slot in range(16):
                    pixels = bytes((v + (0x88 if slot in (0, 3, 4, 5) else 0)) & 255
                                   for v in decoded)
                    if slot == 7:
                        pixels = animated[:0x800] + pixels[0x800:]
                    slots.append(dict(slot=slot, sheet_id=0,
                        decoded_sheet_sha256=R._sha(decoded),
                        resolved_slot_sha256=R._sha(pixels), empty=slot >= 8))
                states.append(dict(state=state, slots=slots,
                    palette=dict(words=list(palette), uint16le_sha256=R._sha(struct.pack('<256H', *palette))),
                    animation=dict(sheet_id=1, decoded_sheet_sha256=R._sha(animated))))
            parent, size = row(7)[0], row(30)[0]
            profile = dict(background_color=int.from_bytes(row(1, 2), 'little'),
                main_palette=row(2)[0], palette_set=row(31)[0], area_graphics=row(27)[0],
                graphics_sheets=list(row(6, 8)), animated_sheet=row(4)[0],
                subscreen_overlay=int.from_bytes(row(5, 2), 'little'),
                mosaic=[bool(row(3)[0] & (8 >> bit)) for bit in range(4)],
                appearance_flags=flags, background_palette_words=words)
            pages.append(dict(map_id=page, parent_map_id=parent, role=row(29)[0],
                              source_profile=profile, tiles=[0] * 1024, resolved_states=states))
            area = areas.setdefault(parent, dict(parent_map_id=parent,
                size=('small', 'large', 'wide', 'tall')[size], maps=[], resident_required=False))
            area['maps'].append(page)
            area['resident_required'] |= bool(flags)
        address, count = entries[400]
        value = dict(schema=R.SOURCE_SCHEMA, resolution_scope='resident_gameplay_areas',
            source_rom_sha256=R._sha(source),
            source_byte_count=len(source), directory_revision=4,
            materialized_map_count=capacity, first_special_map=128,
            special_map_count=capacity - 128, rom_address_overrides={},
            directory_sha256=R._sha(source[R.native.DIRECTORY_PC:R.native.DIRECTORY_PC + 1024]),
            tile16_dictionary=dict(snes_address=address, pc_address=R.native.pc(address),
                count=count, stride=8, sha256=R._sha(source[R.native.pc(address):R.native.pc(address) + count * 8])),
            pages=pages, gameplay_areas=[areas[key] for key in sorted(areas)])
        return self.seal(value)

    def test_native_large_area_packs_physical_page_colors_without_sidecar(self):
        before = hashlib.sha256(self.source).hexdigest()
        result = R.plan_saved_native_terrain(self.source, self.exported)
        # Captured from the pre-source-context compiler at HEAD, not recomputed
        # from the new implementation: no-context serialized output stays exact.
        self.assertEqual(result['plan_sha256'],
            '2ef00caabbb191f825bfa247614b6444716e5c1519c47f77b52b430ba5b9b570')
        self.assertEqual(len(result['areas']), 1)
        area = result['areas'][0]
        self.assertEqual(area['maps'], [0xB0, 0xB1, 0xB8, 0xB9])
        self.assertTrue(result['terrain_plan_ready'])
        self.assertEqual(area['witness']['source_colors_sha256'],
                         area['witness']['reconstructed_colors_sha256'])
        self.assertGreater(area['witness']['pixel_comparisons'], 0)
        self.assertFalse(result['ordinary_build_ready'])
        self.assertFalse(result['allocation_granted'])
        self.assertEqual(result, R.plan_saved_native_terrain(self.source, self.exported))
        self.assertEqual(hashlib.sha256(self.source).hexdigest(), before)

    def sky_overlay_export(self, selected=0x94, host=0x87):
        image = bytearray(self.source)
        _, _, entries = R.native.read_native_directory(self.source)
        image[R.native.pc(entries[410][0]) + host] = 1
        struct.pack_into('<H', image, R.native.pc(entries[5][0]) + host * 2,
                         selected)
        legacy = {name: (address, width) for name, address, _, _, width
                  in R.native.CURRENT_TABLE_SPECS}
        address, width = legacy['overlay']
        struct.pack_into('<H', image, R.native.pc(address) + host * width,
                         selected)
        for overlay in (0x94, 0x9F):
            for name, family in (('map32_high', 20), ('map32_low', 21)):
                address, width = legacy[name]
                old = R.native.pc(address) + overlay * width
                current = R.native.pc(entries[family][0]) + overlay * width
                image[old:old + width] = image[current:current + width]
        self.fixture.image = image
        self.source = self.fixture.installed()
        value = self.make_export(self.source)['native_source']
        for page in value['pages']:
            if page['map_id'] in (0x94, 0x9F):
                page['tiles'] = [3 if page['map_id'] == 0x94 else 4] * 1024
        return self.seal(value)

    def test_sky_host_reserves_cloud_rain_and_mutable_rows_without_changing_source(self):
        for selected in (0x94, 0xFF):
            with self.subTest(selected=selected):
                exported = self.sky_overlay_export(selected)
                original = self.source
                plan = R.plan_saved_native_terrain(self.source, exported)
                host = next(area for area in plan['areas'] if area['maps'] == [0x87])
                rows = {row['tile16_id'] for row in host['remaps']}
                self.assertEqual(rows, {0, 0xDA4, 0xDA6, 0xE54})
                overlay_rows = {(r['overlay_map_id'], r['tile16_id']) for r in host['overlay_remaps']}
                self.assertEqual(overlay_rows, {(0x9F, 4)} |
                                 ({(0x94, 3)} if selected == 0x94 else set()))
                self.assertTrue(host['terrain_plan_ready'])
                self.assertFalse(plan['full_residency_ready'])
                self.assertEqual(self.source, original)

    def test_overlay_same_word_uses_explicit_source_chr_and_palette(self):
        area = dict(parent_map_id=0x87, maps=[0x87], size='small')
        word = (2 << 10) | 64
        definitions = struct.pack('<4H', *([word] * 4)) * 4096
        host_palette = [0] * 256
        donor_palette = [0] * 256
        host_palette[33] = 0x001F
        donor_palette[33:35] = [0x03E0, 0x7C00]
        assets = {
            (0x87, 0): dict(palette={'words': host_palette},
                           slots=[{'sheet_id': 0}] * 8),
            (0x94, 0): dict(palette={'words': donor_palette},
                           slots=[{'sheet_id': 1}] * 8),
        }
        def sheet(index):
            pixels = bytes([1] * 64) if index == 0 else bytes([1, 2] * 32)
            return b'', [pixels] * 64
        args = (area, {0x87: [0]}, assets, definitions, sheet)
        overlays = {0x87: {0x94: {0}}}
        old = R._plan_area(*args, overlay_tiles=overlays)
        same = R._plan_area(*args, overlay_tiles=overlays,
                            overlay_asset_contexts={(0x87, 0x94): 0x87})
        self.assertEqual(old, same)
        different = R._plan_area(*args, overlay_tiles=overlays,
                                 overlay_asset_contexts={(0x87, 0x94): 0x94})
        self.assertTrue(different['terrain_plan_ready'])
        self.assertEqual(old['static_pattern_count'], 1)
        self.assertEqual(different['static_pattern_count'], 2)
        self.assertEqual(different['animated_pattern_count'], 0)
        self.assertEqual(len(different['remaps']), 4)
        self.assertEqual(len(different['overlay_remaps']), 4)
        self.assertNotEqual(different['remaps'][0]['target_word'],
                            different['overlay_remaps'][0]['target_word'])
        self.assertEqual(different['overlay_remaps'][0]['asset_source_map_id'], 0x94)
        self.assertEqual(different['witness']['pixel_comparisons'], 512)
        self.assertEqual(different['witness']['source_colors_sha256'],
                         different['witness']['reconstructed_colors_sha256'])
        self.assertNotEqual(old['witness']['source_colors_sha256'],
                            different['witness']['source_colors_sha256'])

    def test_explicit_nonresident_donor_requires_resolved_states(self):
        exported = self.sky_overlay_export(host=0x8C)
        self.assertFalse(next(a for a in exported['native_source']['gameplay_areas']
                              if a['parent_map_id'] == 0x95)['resident_required'])
        contexts = {(0x8C, 0x94): 0x95}
        result = R.plan_saved_native_terrain(self.source, exported,
                                             overlay_asset_contexts=contexts)
        host = next(a for a in result['areas'] if a['maps'] == [0x8C])
        self.assertEqual({r['asset_source_map_id'] for r in host['overlay_remaps']
                          if r['overlay_map_id'] == 0x94}, {0x95})
        self.assertFalse(any(a['maps'] == [0x95] for a in result['areas']))
        missing = copy.deepcopy(exported['native_source'])
        next(p for p in missing['pages'] if p['map_id'] == 0x95)['resolved_states'] = []
        with self.assertRaisesRegex(ValueError, 'NATIVE_PHASES_INVALID'):
            R.plan_saved_native_terrain(self.source, self.seal(missing),
                                        overlay_asset_contexts=contexts)

    def test_public_overlay_context_uses_authenticated_different_donor(self):
        exported = self.sky_overlay_export()
        before = self.source
        baseline = R.plan_saved_native_terrain(self.source, exported)
        # B1's real synthetic ROM palette already differs at the used entry.
        # The public path validates/reconstructs that palette from the export.
        selected = R.plan_saved_native_terrain(
            self.source, exported, overlay_asset_contexts={(0x87, 0x94): 0xB1})
        host = next(a for a in selected['areas'] if a['maps'] == [0x87])
        old = next(a for a in baseline['areas'] if a['maps'] == [0x87])
        self.assertTrue(selected['terrain_plan_ready'])
        self.assertEqual(old['static_pattern_count'], 1)
        self.assertEqual(host['static_pattern_count'], 2)
        cloud = [r for r in host['overlay_remaps'] if r['overlay_map_id'] == 0x94]
        rain = [r for r in host['overlay_remaps'] if r['overlay_map_id'] == 0x9F]
        self.assertEqual(len(cloud), 4)
        self.assertEqual({r['asset_source_map_id'] for r in cloud}, {0xB1})
        self.assertTrue(all('asset_source_map_id' not in r for r in rain))
        self.assertNotEqual(cloud[0]['target_word'], rain[0]['target_word'])
        self.assertNotEqual(host['witness']['source_colors_sha256'],
                            old['witness']['source_colors_sha256'])
        self.assertEqual(host['witness']['source_colors_sha256'],
                         host['witness']['reconstructed_colors_sha256'])
        self.assertEqual(self.source, before)
        self.assertFalse(selected['ordinary_build_ready'])

    def test_overlay_context_requires_actual_bound_pair_and_source(self):
        exported = self.sky_overlay_export()
        for contexts in ([], {(0x87, 0x94): 0x77}, {(0x88, 0x94): 0x87},
                         {(0x87, None): 0x87}, {(0x87, 0x94): True}):
            with self.subTest(contexts=contexts):
                with self.assertRaisesRegex(ValueError, 'OVERLAY_ASSET_CONTEXT_'):
                    R.plan_saved_native_terrain(self.source, exported,
                                               overlay_asset_contexts=contexts)
        baseline = R.plan_saved_native_terrain(self.source, exported)
        self.assertEqual(baseline, R.plan_saved_native_terrain(
            self.source, exported, overlay_asset_contexts={(0x87, 0x94): 0x87}))

    def test_sky_host_refuses_legacy_selection_or_pointer_disagreement(self):
        exported = self.sky_overlay_export()
        legacy = {name: (address, width) for name, address, _, _, width
                  in R.native.CURRENT_TABLE_SPECS}
        for name, page, reason in (('overlay', 0x87, 'SELECTION'),
                                   ('map32_high', 0x94, 'POINTER'),
                                   ('map32_low', 0x9F, 'POINTER')):
            with self.subTest(name=name, page=page):
                image = bytearray(self.source)
                address, width = legacy[name]
                image[R.native.pc(address) + page * width] ^= 1
                changed = bytes(image)
                value = copy.deepcopy(exported['native_source'])
                value['source_rom_sha256'] = R._sha(changed)
                with self.assertRaisesRegex(ValueError, 'SKY_OVERLAY_' + reason + '_MISMATCH'):
                    R.plan_saved_native_terrain(changed, self.seal(value))

    def test_overlay862_is_separate_from_bridge862_and_blank_entire_timeline(self):
        read, _ = R._source_sheets(self.source)
        blank = bytes(64)
        opaque = bytes([1] * 64)
        # Frame0 alone would miss the deliberate third-frame color below.
        sheets = {0: (bytes(4096), [opaque] * 64),
                  1: (bytes(4096), [blank] * 64),
                  2: (bytes(4096), [blank] * 64)}
        sheets[2][1][3] = opaque
        palette = list(range(256))
        assets = {(0x8D, 0): dict(palette=dict(words=palette),
            slots=[dict(sheet_id=0) for _ in range(8)], animation=dict(sheet_id=2))}
        area = dict(parent_map_id=0x8D, size='small', maps=[0x8D])
        definitions = bytes(4096 * 8)
        pages = {(0x8D, 0x862): (0x0800,) * 4,
                 (0x94, 0x862): (0x1DC2,) * 4,
                 (0x9F, 0x862): (0x1DC3,) * 4}
        packed = R._plan_area(area, {0x8D: [0x862]}, assets, definitions,
            sheets.__getitem__, page_definitions=pages,
            overlay_tiles={0x8D: {0x94: {0x862}, 0x9F: {0x862}}})
        self.assertEqual(packed['refusals'], [])
        self.assertEqual(packed['witness']['source_colors_sha256'],
                         packed['witness']['reconstructed_colors_sha256'])
        fg = packed['remaps'][0]['target_word']
        cloud = packed['overlay_remaps'][0]['target_word']
        rain = packed['overlay_remaps'][4]['target_word']
        self.assertNotEqual(fg, cloud)
        self.assertNotEqual(cloud, rain, 'different animated timelines must not alias')
        for frame in packed['animation']['frame_payloads']:
            raw = bytes.fromhex(frame['payload_hex'])
            offset = ((cloud & 1023) - 448) * 32
            self.assertEqual(raw[offset:offset + 32], bytes(32))
        self.assertEqual(packed['remaps'][0]['source_word'], 0x0800)
        self.assertEqual(packed['overlay_remaps'][0]['source_word'], 0x1DC2)

    def bound_global(self):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        root = Path(folder.name)
        spec_path = root / 'Data/graphics/source_sprite_sheets.json'
        spec_path.parent.mkdir(parents=True)
        (root / 'Util').mkdir()
        (root / 'Config').mkdir()
        (root / 'Util/macros.asm').write_text('!ENABLE_TEST_SKY = 0\n'
            '!ENABLE_SOURCE_SPRITE_SHEETS = 1\n!ENABLE_D4_ZORA_REDESIGN = 0\n')
        (root / 'Config/module_flags.asm').write_text('')
        (root / 'Config/feature_flags.asm').write_text('!ENABLE_TEST_SKY = $01\n')
        grid = [[2] * 128 for _ in range(32)]
        raw = R.sheet_codec.grid_to_sheet(grid)
        (spec_path.parent / 'sky.txt').write_text(R.sheet_codec.grid_to_text(grid))
        base_grid = [[1] * 128 for _ in range(32)]
        (spec_path.parent / 'base.txt').write_text(R.sheet_codec.grid_to_text(base_grid))
        spec = dict(schema_version=2, start='0x40D000', capacity=12288,
            encoding='lz2', sheets=[dict(global_sheet='0xEB', source='base.txt',
                decoded_sha256=R._sha(R.sheet_codec.grid_to_sheet(base_grid)), why='fallback'),
                dict(global_sheet='0xEB', source='sky.txt',
                flag='ENABLE_TEST_SKY', decoded_sha256=R._sha(raw), why='test')])
        spec_path.write_text(json.dumps(spec))
        value = copy.deepcopy(self.exported['native_source'])
        flat = bytes([2] * 4096)
        for page in value['pages']:
            for state in page['resolved_states']:
                state['slots'][0].update(sheet_id=0xEB,
                    decoded_sheet_sha256=R._sha(flat),
                    resolved_slot_sha256=R._sha(bytes([0x8A] * 4096)))
        value['graphics_source'] = dict(spec='Data/graphics/source_sprite_sheets.json',
            spec_sha1=hashlib.sha1(spec_path.read_bytes()).hexdigest(), sheets=[dict(
                sheet_id=0xEB, source='sky.txt', flag='ENABLE_TEST_SKY',
                decoded_sheet_sha256=R._sha(flat))])
        return root, value, raw

    def sky_source_contract_fixture(self):
        root, value, _ = self.bound_global()
        with (root / 'Util/macros.asm').open('a') as out:
            out.write('!ENABLE_SKY_OVERLAY_SOURCE_PROFILE = 1\n')
        value['directory_revision'] = 5
        pages = {p['map_id']: p for p in value['pages']}
        for host in R.SKY_RESIDENT_HOSTS:
            pages[host]['source_profile']['subscreen_overlay'] = 0x94
            value['gameplay_areas'].append(dict(maps=[host], resident_required=True))
        pages[0x94]['source_profile']['appearance_flags'] = 3
        pages[0x94]['resolved_states'] = [dict(state=i) for i in range(3)]
        return root, value

    def test_source_overlay_flag_absent_off_and_precedence_preserve_default(self):
        root, value, _ = self.bound_global()
        self.assertIsNone(R.selected_sky_overlay_contexts(value, None))
        self.assertIsNone(R.selected_sky_overlay_contexts(value, root))
        with (root / 'Util/macros.asm').open('a') as out:
            out.write('!ENABLE_SKY_OVERLAY_SOURCE_PROFILE = 1\n')
        with (root / 'Config/feature_flags.asm').open('a') as out:
            out.write('!ENABLE_SKY_OVERLAY_SOURCE_PROFILE = 0\n')
        self.assertIsNone(R.selected_sky_overlay_contexts(value, root))

    def test_source_overlay_flag_on_selects_only_saved_calm_page(self):
        root, value = self.sky_source_contract_fixture()
        expected = {(h, 0x94): 0x94 for h in R.SKY_RESIDENT_HOSTS}
        self.assertEqual(R.selected_sky_overlay_contexts(value, root), expected)
        self.assertNotIn((0x87, 0x9F), expected)
        self.assertNotIn((0x8B, 0x94), expected)

    def test_source_overlay_flag_refuses_wrong_host_unresolved_and_bad_auth(self):
        root, value = self.sky_source_contract_fixture()
        for change, reason in (('host', 'HOST_SELECTION'), ('states', 'PROFILE_UNRESOLVED'),
                               ('revision', 'BINDING_REQUIRED'), ('hash', 'SPEC_MISMATCH')):
            with self.subTest(change=change):
                bad = copy.deepcopy(value)
                if change == 'host':
                    next(p for p in bad['pages'] if p['map_id'] == 0x8C)['source_profile']['subscreen_overlay'] = 0x95
                elif change == 'states':
                    next(p for p in bad['pages'] if p['map_id'] == 0x94)['resolved_states'] = []
                elif change == 'revision':
                    bad['directory_revision'] = 4
                else:
                    bad['graphics_source']['spec_sha1'] = '0' * 40
                with self.assertRaisesRegex(ValueError, reason):
                    R.selected_sky_overlay_contexts(bad, root)

    def test_source_overlay_flag_rejects_nonliteral_conditional_and_nonboolean(self):
        root, value = self.sky_source_contract_fixture()
        for assignment in ('?= 1', '= thing', '= 2', '= -1'):
            with self.subTest(assignment=assignment):
                (root / 'Config/feature_flags.asm').write_text(
                    '!ENABLE_TEST_SKY = 1\n!ENABLE_SKY_OVERLAY_SOURCE_PROFILE ' + assignment + '\n')
                with self.assertRaisesRegex(ValueError, 'SKY_SOURCE_FLAG_'):
                    R.selected_sky_overlay_contexts(value, root)

    def test_bound_eb_source_authenticates_both_digest_representations(self):
        root, value, raw = self.bound_global()
        result = R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)
        row, = [s for s in result['decoded_sheets'] if s['sheet_id'] == 0xEB]
        self.assertEqual(row['decoded_3bpp_sha256'], R._sha(raw))
        self.assertEqual(row['decoded_indexed8_sha256'], R._sha(bytes([2] * 4096)))
        self.assertEqual(row['source_provenance']['source'], 'sky.txt')
        self.assertNotIn('pointer_snes', row)
        self.assertEqual(result, R.plan_saved_native_terrain(
            self.source, self.seal(value), graphics_root=root))
        # A context is inert for old exports: preserve their exact plan bytes.
        self.assertEqual(R._json_bytes(R.plan_saved_native_terrain(self.source, self.exported)),
            R._json_bytes(R.plan_saved_native_terrain(
                self.source, self.exported, graphics_root=root)))

    def test_graphics_provenance_needs_context_and_complete_authentic_rows(self):
        root, original, raw = self.bound_global()
        with self.assertRaisesRegex(ValueError, 'GRAPHICS_ROOT_REQUIRED'):
            R.plan_saved_native_terrain(self.source, self.seal(original))
        mutations = [
            lambda p: p.__setitem__('spec_sha1', '0' * 40),
            lambda p: p.__setitem__('spec', 'elsewhere.json'),
            lambda p: p['sheets'][0].__setitem__('source', 'forged.txt'),
            lambda p: p['sheets'][0].__setitem__('flag', None),
            lambda p: p['sheets'][0].__setitem__('sheet_id', 0xEC),
            lambda p: p['sheets'][0].__setitem__('decoded_sheet_sha256', R._sha(raw)),
            lambda p: p.__setitem__('sheets', []),
            lambda p: p['sheets'].append(copy.deepcopy(p['sheets'][0])),
        ]
        for mutate in mutations:
            value = copy.deepcopy(original)
            mutate(value['graphics_source'])
            with self.subTest(provenance=value['graphics_source']):
                with self.assertRaisesRegex(ValueError, 'GRAPHICS_(SPEC|SOURCE_ROWS)_MISMATCH'):
                    R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_stale_artwork_and_disabled_missing_nonliteral_flags_refuse(self):
        root, value, _ = self.bound_global()
        flags = root / 'Config/feature_flags.asm'
        for text in ('!ENABLE_TEST_SKY = 0\n', '!ENABLE_TEST_SKY = other\n',
                     '!ENABLE_TEST_SKY ?= 1\n'):
            flags.write_text(text)
            with self.subTest(flags=text):
                with self.assertRaisesRegex(ValueError, 'GRAPHICS_(SOURCE_ROWS|FLAG)'):
                    R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)
        flags.write_text('')
        (root / 'Util/macros.asm').write_text('')
        with self.assertRaisesRegex(ValueError, 'FLAG_UNRESOLVED'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)
        (root / 'Util/macros.asm').write_text(
            '!ENABLE_SOURCE_SPRITE_SHEETS = 1\n!ENABLE_D4_ZORA_REDESIGN = 0\n')
        flags.write_text('!ENABLE_TEST_SKY = 1\n')
        (root / 'Data/graphics/sky.txt').write_text(R.sheet_codec.grid_to_text([[3] * 128 for _ in range(32)]))
        with self.assertRaisesRegex(ValueError, 'SOURCE_HASH_MISMATCH'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_source_symlink_cannot_escape_spec_directory(self):
        root, value, _ = self.bound_global()
        path = root / 'Data/graphics/sky.txt'
        outside = root / 'outside.txt'
        outside.write_bytes(path.read_bytes())
        path.unlink()
        path.symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'escapes through a symlink'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_enclosing_source_and_d4_flags_are_explicit_admission_guards(self):
        root, value, _ = self.bound_global()
        flags = root / 'Config/module_flags.asm'
        for text, message in (
            ('!ENABLE_SOURCE_SPRITE_SHEETS = 0\n', 'SOURCE_FEATURE_DISABLED'),
            ('!ENABLE_SOURCE_SPRITE_SHEETS = 2\n', 'SOURCE_FEATURE_DISABLED'),
            ('!ENABLE_D4_ZORA_REDESIGN = 1\n', 'SPEC_SELECTION_MISMATCH'),
            ('!ENABLE_D4_ZORA_REDESIGN = expression\n', 'FLAG_UNRESOLVED')):
            flags.write_text(text)
            with self.subTest(flags=text):
                with self.assertRaisesRegex(ValueError, message):
                    R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

        flags.write_text('')
        macros = root / 'Util/macros.asm'
        for missing in ('ENABLE_SOURCE_SPRITE_SHEETS', 'ENABLE_D4_ZORA_REDESIGN'):
            macros.write_text('!ENABLE_TEST_SKY = 0\n' + ''.join(
                f'!{name} = {number}\n' for name, number in
                (('ENABLE_SOURCE_SPRITE_SHEETS', 1), ('ENABLE_D4_ZORA_REDESIGN', 0))
                if name != missing))
            with self.subTest(missing=missing):
                with self.assertRaisesRegex(ValueError, 'FLAG_UNRESOLVED'):
                    R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_d4_source_selection_prefix_and_sha_are_authenticated(self):
        root, value, _ = self.bound_global()
        ordinary_path = root / 'Data/graphics/source_sprite_sheets.json'
        d4_path = ordinary_path.with_name('d4_zora_sprite_sheets.json')
        d4 = json.loads(ordinary_path.read_text())
        grid = [[3] * 128 for _ in range(32)]
        raw = R.sheet_codec.grid_to_sheet(grid)
        (d4_path.parent / 'd4.txt').write_text(R.sheet_codec.grid_to_text(grid))
        d4['sheets'].append(dict(global_sheet='0xEC', source='d4.txt',
            decoded_sha256=R._sha(raw), why='D4 addition'))
        d4_path.write_text(json.dumps(d4))
        flags = root / 'Config/module_flags.asm'
        flags.write_text('!ENABLE_D4_ZORA_REDESIGN = 2\n')
        provenance = value['graphics_source']
        provenance.update(spec='Data/graphics/d4_zora_sprite_sheets.json',
            spec_sha1=hashlib.sha1(d4_path.read_bytes()).hexdigest())
        provenance['sheets'].append(dict(sheet_id=0xEC, source='d4.txt', flag=None,
            decoded_sheet_sha256=R._sha(bytes([3] * 4096))))
        for page in value['pages']:
            for state in page['resolved_states']:
                state['slots'][1].update(sheet_id=0xEC,
                    decoded_sheet_sha256=R._sha(bytes([3] * 4096)),
                    resolved_slot_sha256=R._sha(bytes([3] * 4096)))
        result = R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)
        row, = [s for s in result['decoded_sheets'] if s['sheet_id'] == 0xEC]
        self.assertEqual(row['decoded_3bpp_sha256'], R._sha(raw))
        self.assertEqual(row['source_provenance']['ordinary_spec_sha1'],
                         hashlib.sha1(ordinary_path.read_bytes()).hexdigest())
        flags.write_text('!ENABLE_D4_ZORA_REDESIGN = 0\n')
        with self.assertRaisesRegex(ValueError, 'SPEC_SELECTION_MISMATCH'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)
        flags.write_text('!ENABLE_D4_ZORA_REDESIGN = 1\n')
        stale = copy.deepcopy(value)
        stale['graphics_source']['spec_sha1'] = '0' * 40
        with self.assertRaisesRegex(ValueError, 'GRAPHICS_SPEC_MISMATCH'):
            R.plan_saved_native_terrain(self.source, self.seal(stale), graphics_root=root)
        d4['sheets'][0]['why'] = 'changed standard prefix'
        d4_path.write_text(json.dumps(d4))
        provenance['spec_sha1'] = hashlib.sha1(d4_path.read_bytes()).hexdigest()
        with self.assertRaisesRegex(ValueError, 'D4_STANDARD_PREFIX_MISMATCH'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_canonical_spec_cannot_be_an_internal_symlink_alias(self):
        root, value, _ = self.bound_global()
        path = root / 'Data/graphics/source_sprite_sheets.json'
        alias = path.with_name('alias.json')
        path.rename(alias)
        path.symlink_to(alias.name)
        with self.assertRaisesRegex(ValueError, 'GRAPHICS_SPEC_PATH_INVALID'):
            R.plan_saved_native_terrain(self.source, self.seal(value), graphics_root=root)

    def test_fixed_aux_palette_context_preserves_resident_color_plan(self):
        value = copy.deepcopy(self.exported['native_source'])
        value['rom_address_overrides'] = dict(
            overworld_aux_palette_extension_pc=0x22F900,
            overworld_aux_palette_extension_count=32,
            overworld_aux_palette_extension_abi=1)
        baseline = R.plan_saved_native_terrain(self.source, self.exported)
        result = R.plan_saved_native_terrain(self.source, self.seal(value))
        self.assertEqual(result['source_rom_sha256'], baseline['source_rom_sha256'])
        self.assertEqual(result['areas'], baseline['areas'])
        self.assertEqual(result['decoded_sheets'], baseline['decoded_sheets'])
        self.assertNotEqual(result['native_source_sha256'],
                            baseline['native_source_sha256'])

    def test_aux_context_rejects_partial_foreign_and_wrong_typed_contracts(self):
        valid = dict(overworld_aux_palette_extension_pc=0x22F900,
                     overworld_aux_palette_extension_count=32,
                     overworld_aux_palette_extension_abi=1)
        bad = [None, [], {'overworld_gfx_ptr1': 42},
               {**valid, 'overworld_gfx_ptr1': 42}]
        for key in valid:
            bad.append({k: v for k, v in valid.items() if k != key})
            for replacement in (True, False, str(valid[key]), float(valid[key]),
                                -1, 0, valid[key] + 1):
                bad.append({**valid, key: replacement})
        for overrides in bad:
            with self.subTest(overrides=overrides):
                value = copy.deepcopy(self.exported['native_source'])
                value['rom_address_overrides'] = overrides
                with self.assertRaisesRegex(ValueError, 'OVERRIDES_UNSUPPORTED'):
                    R._native_source(self.source, self.seal(value))

    def test_aux_context_requires_complete_fixed_table_extent(self):
        overrides = dict(overworld_aux_palette_extension_pc=0x22F900,
                         overworld_aux_palette_extension_count=32,
                         overworld_aux_palette_extension_abi=1)
        end = 0x22F900 + 32 * 21 * 2
        with self.assertRaisesRegex(ValueError, 'AUX_PALETTE_EXTENSION_TRUNCATED'):
            R._validate_address_overrides(bytes(end - 1), overrides)
        R._validate_address_overrides(bytes(end), overrides)
        R._validate_address_overrides(b'', {})

    def test_export_identity_raw_profile_and_topology_cannot_be_substituted(self):
        for change, message in (
            (lambda v: v.__setitem__('source_rom_sha256', '0' * 64), 'SOURCE_MISMATCH'),
            (lambda v: v.__setitem__('rom_address_overrides', {'overworld_gfx_ptr1': 42}), 'OVERRIDES_UNSUPPORTED'),
            (lambda v: v['pages'][0]['source_profile'].__setitem__('main_palette', 9), 'PROFILE_MISMATCH'),
            (lambda v: v['pages'][0].__setitem__('parent_map_id', 0xB0), 'AREA_MISMATCH'),
            (lambda v: v['pages'][0]['tiles'].__setitem__(0, 4096), 'TILE16_MAP_INVALID')):
            with self.subTest(message=message):
                value = copy.deepcopy(self.exported['native_source'])
                change(value)
                with self.assertRaisesRegex(ValueError, message):
                    R.plan_saved_native_terrain(self.source, self.seal(value))
        changed = copy.deepcopy(self.exported)
        changed['native_source']['pages'][0]['tiles'][0] = 1
        with self.assertRaisesRegex(ValueError, 'EXPORT_HASH_MISMATCH'):
            R.plan_saved_native_terrain(self.source, changed)

    def test_resolved_bytes_and_phase_variation_are_checked_before_packing(self):
        for target, field, message in (
            ('slot', 'decoded_sheet_sha256', 'SHEET_HASH_MISMATCH'),
            ('slot', 'resolved_slot_sha256', 'RESOLVED_SLOT_HASH_MISMATCH'),
            ('animation', 'decoded_sheet_sha256', 'ANIMATION_HASH_MISMATCH')):
            with self.subTest(field=field, target=target):
                value = copy.deepcopy(self.exported['native_source'])
                state = value['pages'][0xB1 - 128]['resolved_states'][0]
                row = state['slots'][0] if target == 'slot' else state['animation']
                row[field] = '0' * 64
                with self.assertRaisesRegex(ValueError, message):
                    R.plan_saved_native_terrain(self.source, self.seal(value))
        value = copy.deepcopy(self.exported['native_source'])
        for state in value['pages'][0xB1 - 128]['resolved_states']:
            palette = state['palette']
            palette['words'][41] ^= 1
            palette['uint16le_sha256'] = R._sha(struct.pack('<256H', *palette['words']))
        with self.assertRaisesRegex(ValueError, 'BG128_SOURCE_MISMATCH'):
            R.plan_saved_native_terrain(self.source, self.seal(value))
        self.fixture.image[self.fixture.flags_pc + 0xB1] = 1
        source = self.fixture.installed()
        value = self.make_export(source)['native_source']
        palette = value['pages'][0xB1 - 128]['resolved_states'][2]['palette']
        palette['words'][41] ^= 1
        palette['uint16le_sha256'] = R._sha(struct.pack('<256H', *palette['words']))
        with self.assertRaisesRegex(ValueError, 'BG_PHASE_VARIATION_UNSUPPORTED'):
            R.plan_saved_native_terrain(source, self.seal(value))

    def test_source_zero_in_biased_bg_is_opaque_and_empty_slot_stays_transparent(self):
        image = self.fixture.image
        # A compressed all-zero source sheet: source0 becomes index8 in a
        # present biased BG slot; a genuinely empty slot has no bias.
        image[0x280000:0x280005] = bytes((0xE7, 0xFF, 0, 0xE5, 0xFF))
        image[0x280005:0x280007] = bytes((0, 0xFF))
        source = self.fixture.installed()
        exported = self.make_export(source)
        opaque = R.plan_saved_native_terrain(source, exported)['areas'][0]
        self.assertTrue(any(bytes.fromhex(opaque['static_chr']['payload_hex'])))
        value = copy.deepcopy(exported['native_source'])
        for page in value['pages']:
            for state in page['resolved_states']:
                state['slots'][0]['empty'] = True
                state['slots'][0]['resolved_slot_sha256'] = R._sha(bytes(0x1000))
        transparent = R.plan_saved_native_terrain(source, self.seal(value))['areas'][0]
        self.assertEqual(set(bytes.fromhex(transparent['static_chr']['payload_hex'])), {0})
        self.assertNotEqual(opaque['witness']['source_colors_sha256'],
                            transparent['witness']['source_colors_sha256'])

class ExperimentalPageTile16ResourcesTest(unittest.TestCase):
    """Synthetic revision5 wire bytes; no encoder/allocation/runtime authority."""
    def setUp(self):
        self.fixture = SavedNativeTerrainResourcesTest()
        self.fixture.setUp()
        self.rows = [(0xB0, 0, (0xE800, 0x4801, 0x8802, 0x2803)),
                     (0xB1, 0, (0x2804, 0x8805, 0x4806, 0xE807))]
        self.address = 0x518000  # Synthetic only; not a production reservation.
        self.source, self.exported = self.install(self.rows)

    @staticmethod
    def reseal(image):
        """Wire fixture builder independent of the producer revision5 reader."""
        import zlib
        at = R.native.DIRECTORY_PC
        count, = struct.unpack_from('<H', image, at + 18)
        for index in range(count):
            row = at + 32 + index * 16
            _, _, address, rows, stride, _ = struct.unpack_from('<HHIHHI', image, row)
            start = R.native.pc(address)
            struct.pack_into('<I', image, row + 12,
                             zlib.crc32(image[start:start + rows * stride]))
        struct.pack_into('<I', image, at + 28, 0)
        struct.pack_into('<I', image, at + 28,
                         zlib.crc32(image[at:at + R.native.DIRECTORY_SIZE]))
        return bytes(image)

    def install(self, rows, count=4, *, authoring=False, capacity=192):
        image = bytearray(self.fixture.source)
        at = R.native.DIRECTORY_PC
        entries = 58 if authoring else 57
        struct.pack_into('<6HBBH', image, at + 8, 5, 32, 32 + entries * 16,
                         capacity, capacity, entries, 0x4C,
                         0x7C if authoring else 0x5C, capacity * 2)
        for index in range(56):
            record = at + 32 + index * 16
            key, = struct.unpack_from('<H', image, record)
            if key <= 39 or key == 410:
                struct.pack_into('<H', image, record + 8, capacity)
        index = 56
        if authoring:
            raw = R.native.authoring_metadata.encode(
                dict(next_placement_id=1, placements=[]), capacity)
            start = R.native.pc(R.native.AUTHORING_METADATA_BASE)
            image[start:start + len(raw)] = raw
            struct.pack_into('<HHIHHI', image, at + 32 + index * 16,
                412, 9, R.native.AUTHORING_METADATA_BASE, 256, 32, 0)
            index += 1
        raw = b''.join(struct.pack('<6H', page, tile, *words)
                       for page, tile, words in rows) + b'\xFF' * ((count - len(rows)) * 12)
        start = R.native.pc(self.address)
        image[start:start + len(raw)] = raw
        struct.pack_into('<HHIHHI', image, at + 32 + index * 16,
                         413, 10, self.address, count, 12, 0)
        source = self.reseal(image)
        value = copy.deepcopy(self.fixture.exported['native_source'])
        value.update(schema=R.EXPERIMENTAL_SOURCE_SCHEMA, runtime_supported=False,
            directory_revision=5, source_rom_sha256=R._sha(source),
            directory_sha256=R._sha(source[at:at + R.native.DIRECTORY_SIZE]),
            page_tile16_definitions=dict(table_id=413, snes_address=self.address,
                pc_address=start, count=count, stride=12, sha256=R._sha(raw),
                rows=[dict(map_id=page, tile_id=tile, words=list(words))
                      for page, tile, words in rows]))
        for page in value['pages']:
            page['tiles'] = [0, 1] * 512
        overrides = {page for page, _, _ in rows}
        for area in value['gameplay_areas']:
            area['resident_required'] |= bool(overrides.intersection(area['maps']))
        return source, self.fixture.seal(value)

    def plan(self, source=None, exported=None):
        return R.plan_saved_native_terrain(
            self.source if source is None else source,
            self.exported if exported is None else exported,
            experimental_page_tile16=True)

    def test_effective_page_words_global_fallback_and_attribute_preservation(self):
        before = self.source
        result = self.plan()
        self.assertEqual(result['schema'], R.EXPERIMENTAL_PLAN_SCHEMA)
        self.assertTrue(result['terrain_plan_ready'])
        self.assertFalse(result['runtime_supported'])
        self.assertFalse(result['ordinary_build_ready'])
        area = result['areas'][0]
        remaps = {(row['map_id'], row['tile16_id'], row['quadrant']): row
                  for row in area['remaps']}
        for page, tile, words in self.rows:
            for quadrant, word in enumerate(words):
                row = remaps[page, tile, quadrant]
                self.assertEqual(row['source_word'], word)
                self.assertEqual(row['target_word'] & 0xE000, word & 0xE000)
                self.assertEqual(remaps[page, 1, quadrant]['source_word'], 0x800)
        self.assertEqual(remaps[0xB8, 0, 0]['source_word'], 0x800)
        self.assertEqual(area['witness']['source_colors_sha256'],
                         area['witness']['reconstructed_colors_sha256'])
        self.assertEqual(self.source, before)

    def test_zero_appearance_page_still_requires_resources(self):
        rows = [(0x82, 0, (0x4800,) * 4), *self.rows]
        source, exported = self.install(rows)
        area = next(a for a in self.plan(source, exported)['areas'] if a['maps'] == [0x82])
        self.assertTrue(area['terrain_plan_ready'])
        self.assertEqual(area['remaps'][0]['source_word'], 0x4800)

    def test_default_admission_and_runtime_lowering_remain_refused(self):
        import special_overworld_native_build as build
        import special_overworld_resident_abi as resident
        for operation in (
                lambda: R.native.read_native_directory(self.source),
                lambda: R.native.reader_constants(self.source),
                lambda: R.plan_saved_native_terrain(self.source, self.exported),
                lambda: build.prepare_revision4_compilation(self.source, self.exported,
                    data_pc=R.native.RESIDENT_DATA_PC, capacity=R.native.RESIDENT_DATA_CAPACITY,
                    preimage=bytes(R.native.RESIDENT_DATA_CAPACITY)),
                lambda: resident.plan_native_resident_abi(self.plan(), tile16_count=4096)):
            with self.subTest(operation=operation), self.assertRaises(ValueError):
                operation()

    def test_export_extent_hash_rows_schema_and_stale_source_refused(self):
        for field, replacement in [('table_id', 412), ('pc_address', 0),
                ('snes_address', self.address + 12), ('count', 3), ('stride', 8),
                ('sha256', '0' * 64), ('rows', []), ('unknown', 1)]:
            value = copy.deepcopy(self.exported['native_source'])
            value['page_tile16_definitions'][field] = replacement
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'PAGE_TILE16_SOURCE_MISMATCH'):
                self.plan(exported=self.fixture.seal(value))
        for schema in (R.SOURCE_SCHEMA, 'unknown.experimental-v3'):
            value = copy.deepcopy(self.exported['native_source'])
            value['schema'] = schema
            with self.assertRaisesRegex(ValueError, 'SOURCE_MISMATCH'):
                self.plan(exported=self.fixture.seal(value))
        value = copy.deepcopy(self.exported['native_source'])
        value['page_tile16_definitions']['rows'][0]['words'][0] = 0
        with self.assertRaisesRegex(ValueError, 'PAGE_TILE16_SOURCE_MISMATCH'):
            self.plan(exported=self.fixture.seal(value))
        value = copy.deepcopy(self.exported['native_source'])
        value['runtime_supported'] = True
        with self.assertRaisesRegex(ValueError, 'RUNTIME_ADMISSION'):
            self.plan(exported=self.fixture.seal(value))
        changed = bytearray(self.source)
        struct.pack_into('<H', changed, R.native.pc(self.address) + 4, 0x800)
        changed = self.reseal(changed)
        with self.assertRaisesRegex(ValueError, 'SOURCE_MISMATCH'):
            self.plan(source=changed)
        value = copy.deepcopy(self.exported['native_source'])
        value['source_rom_sha256'] = R._sha(changed)
        value['directory_sha256'] = R._sha(changed[R.native.DIRECTORY_PC:R.native.DIRECTORY_PC + 1024])
        with self.assertRaisesRegex(ValueError, 'PAGE_TILE16_SOURCE_MISMATCH'):
            self.plan(source=changed, exported=self.fixture.seal(value))

    def test_resealed_malformed_rows_and_wire_contract_refused(self):
        start = R.native.pc(self.address)
        cases = [lambda image: struct.pack_into('<H', image, start, 127),
                 lambda image: struct.pack_into('<H', image, start, 192),
                 lambda image: struct.pack_into('<H', image, start + 2, 4096),
                 lambda image: image.__setitem__(slice(start + 12, start + 24), image[start:start + 12]),
                 lambda image: image.__setitem__(slice(start, start + 12), b'\xFF' * 12),
                 lambda image: struct.pack_into('<H', image, start + 24, 0xB2),
                 lambda image: struct.pack_into('<H', image, R.native.DIRECTORY_PC + 8, 6),
                 lambda image: struct.pack_into('<H', image, R.native.DIRECTORY_PC + 32 + 56 * 16 + 10, 8),
                 lambda image: struct.pack_into('<I', image, R.native.DIRECTORY_PC + 32 + 56 * 16 + 4, 0x51FFF0)]
        for index, mutate in enumerate(cases):
            image = bytearray(self.source)
            mutate(image)
            with self.subTest(case=index), self.assertRaises(ValueError):
                R.native.read_native_directory(self.reseal(image), experimental_page_tile16=True)
        image = bytearray(self.source)
        image[start + 4] ^= 1
        with self.assertRaisesRegex(ValueError, 'CRC'):
            R.native.read_native_directory(bytes(image), experimental_page_tile16=True)

    def test_variable_extent_both_capacities_and_optional_authoring(self):
        rows = [(0x8D, 0xFFF, (0xFFFF, 0x8000, 0x4000, 0x2000))]
        for capacity in (160, 192):
            for count in (1, 2730):
                for authoring in (False, True):
                    with self.subTest(capacity=capacity, count=count, authoring=authoring):
                        source, _ = self.install(rows, count=count, capacity=capacity, authoring=authoring)
                        actual, _, entries = R.native.read_native_directory(source, experimental_page_tile16=True)
                        self.assertEqual(actual, capacity)
                        self.assertEqual(entries[413], (self.address, count))
                        self.assertEqual(412 in entries, authoring)
                        start = R.native.pc(self.address)
                        decoded = R.native.decode_page_tile16(source[start:start + count * 12], capacity)
                        self.assertEqual(decoded, {(rows[0][0], rows[0][1]): rows[0][2]})
                        global_start = R.native.pc(entries[400][0])
                        definitions = source[global_start:global_start + 4096 * 8]
                        self.assertEqual(R.native.effective_tile16_words(definitions, decoded, 0x8D, 0xFFF), rows[0][2])

    def test_legacy_v1_output_is_exact_even_with_opt_in(self):
        regular = R.plan_saved_native_terrain(self.fixture.source, self.fixture.exported)
        admitted = R.plan_saved_native_terrain(self.fixture.source, self.fixture.exported,
                                              experimental_page_tile16=True)
        self.assertEqual(regular, admitted)
        self.assertEqual(regular['plan_sha256'],
                         '2ef00caabbb191f825bfa247614b6444716e5c1519c47f77b52b430ba5b9b570')


class SkyCloudOverlayConstantTest(unittest.TestCase):
    def test_asm_constant_matches_build_constant(self):
        asm = (Path(__file__).resolve().parents[3] / 'Overworld' / 'ZSCustomOverworld.asm').read_text()
        found = re.findall(r'^!SKY_CLOUD_OVERLAY = \$([0-9A-Fa-f]+)\s*$', asm, re.M)
        # Flag-on branch first, flag-off fallback ($9C, the pre-move ID) second.
        self.assertEqual([int(v, 16) for v in found], [R.SKY_CLOUD_OVERLAY, 0x9C])
        self.assertNotEqual(R.SKY_CLOUD_OVERLAY, 0x9C)  # $9C is reserved for the Fortress


class TreeHouseCanopyOverlayByteTest(unittest.TestCase):
    """Ensure Tree House exit room $0181 loads tree canopy $9E at $02:AF9C (PC 0x012F9C) even when Sky flags are off."""

    TREE_HOUSE_OVERLAY_SNES = 0x02AF9C
    TREE_HOUSE_OVERLAY_PC = 0x012F9C
    TREE_HOUSE_CANOPY_ID = 0x9E
    TREE_HOUSE_BRANCH_BYTES = bytes.fromhex('A29E00A5A0C98101F0F1')
    ASSEMBLER = shutil.which('asar')

    def _zs_text(self):
        return (Path(__file__).resolve().parents[3] / 'Overworld' / 'ZSCustomOverworld.asm').read_text()

    def _assert_rom_branch(self, image: bytes, context: str):
        if len(image) % 0x8000 == 0x200:
            image = image[0x200:]
        self.assertEqual(R.native.pc(self.TREE_HOUSE_OVERLAY_SNES), self.TREE_HOUSE_OVERLAY_PC)
        self.assertEqual(
            image[self.TREE_HOUSE_OVERLAY_PC],
            self.TREE_HOUSE_CANOPY_ID,
            f'{context}: expected PC 0x012F9C ($02:AF9C) == 0x9E, got 0x{image[self.TREE_HOUSE_OVERLAY_PC]:02X}',
        )
        self.assertEqual(
            image[self.TREE_HOUSE_OVERLAY_PC - 1:self.TREE_HOUSE_OVERLAY_PC + 9],
            self.TREE_HOUSE_BRANCH_BYTES,
            f'{context}: unexpected instruction sequence around PC 0x012F9B..0x012FA4',
        )

    def test_source_tree_house_branch_unconditionally_loads_canopy(self):
        zs = self._zs_text()
        fn_start = zs.index('org $02AF58 ; $012F58')
        fn_end = zs.index('assert pc() <= $02B0D2 ; $0130D2', fn_start)
        body = zs[fn_start:fn_end]
        depth = 0
        pending_ldx = None
        matched_0181 = None
        for raw_line in body.splitlines():
            stripped = raw_line.split(';', 1)[0].strip()
            if not stripped:
                continue
            if re.match(r'^if\b', stripped):
                depth += 1
                continue
            if re.match(r'^endif\b', stripped):
                depth -= 1
                self.assertGreaterEqual(depth, 0)
                continue
            ldx_match = re.match(r'^LDX\.w\s+#\$([0-9A-Fa-f]{4})$', stripped)
            if ldx_match:
                pending_ldx = (int(ldx_match.group(1), 16), depth)
                continue
            if re.match(r'^LDA\.b\s+\$A0\s*:\s*CMP\.w\s+#\$0181\s*:\s*BEQ\s+\.loadOverlayShortcut$', stripped):
                matched_0181 = (pending_ldx, depth)
                break
        self.assertIsNotNone(matched_0181, 'Missing $0181 shortcut branch in Overworld_ReloadSubscreenOverlay_Interupt')
        (ldx_info, cmp_depth) = matched_0181
        self.assertIsNotNone(ldx_info, 'Missing LDX.w immediate before CMP.w #$0181')
        ldx_val, ldx_depth = ldx_info
        self.assertEqual(ldx_depth, 0, 'Tree House $0181 LDX.w must be unconditional (active when flag-off)')
        self.assertEqual(cmp_depth, 0, 'Tree House $0181 CMP/BEQ must be unconditional (active when flag-off)')
        self.assertEqual(ldx_val, self.TREE_HOUSE_CANOPY_ID)

    @unittest.skipUnless(ASSEMBLER, 'Asar required for compiled Overworld_ReloadSubscreenOverlay_Interupt check')
    def test_flag_off_assembled_pc_012f9c_is_9e(self):
        zs = self._zs_text()
        const_marker = 'if !ENABLE_SKY_OVERLAY_SOURCE_PROFILE == 1\n!SKY_CLOUD_OVERLAY'
        const_block = ''
        if const_marker in zs:
            const_start = zs.index(const_marker)
            const_end = zs.index('endif\n', const_start) + len('endif\n')
            const_block = zs[const_start:const_end]
        fn_start = zs.index('org $02AF58 ; $012F58')
        fn_end = zs.index('assert pc() <= $02B0D2 ; $0130D2', fn_start) + len('assert pc() <= $02B0D2 ; $0130D2')
        fn_block = zs[fn_start:fn_end]

        for sky_flag, lyra_fix in ((0, 1), (0, 0), (1, 1)):
            with self.subTest(sky_flag=sky_flag, lyra_fix=lyra_fix), tempfile.TemporaryDirectory() as tmp:
                tmp_dir = Path(tmp)
                rom_path = tmp_dir / 'probe.sfc'
                asm_path = tmp_dir / 'probe.asm'
                rom_path.write_bytes(b'\x00' * 0x200000)
                asm_path.write_text(
                    'lorom\n'
                    f'!ENABLE_SKY_OVERLAY_SOURCE_PROFILE = {sky_flag}\n'
                    f'!ENABLE_LYRA_OVERLAY_FIX = {lyra_fix}\n'
                    '!ENABLE_PART0_STORM = 1\n'
                    'Oracle_LyraOverlay_UseTablePath = $348000\n'
                    'Oracle_Part0Storm_CarryClearIfStorm = $348010\n'
                    'ReadOverlayArray = $288000\n'
                    'Pool_EnableRainMireEvent = $288010\n'
                    'Pool_EnableBeginningRain = $288020\n'
                    'LoadSubscreenOverlay = $02B0D2\n'
                    f'{const_block}\n'
                    f'{fn_block}\n'
                )
                proc = subprocess.run(
                    [self.ASSEMBLER, '--no-title-check', '--fix-checksum=off', str(asm_path), str(rom_path)],
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
                self._assert_rom_branch(rom_path.read_bytes(), f'assembled(sky_flag={sky_flag}, lyra_fix={lyra_fix})')

    @unittest.skipUnless(os.environ.get('OOS_TEST_ROM'), 'Set OOS_TEST_ROM to a built oos168x.sfc')
    def test_built_rom_pc_012f9c_is_9e(self):
        rom_path = Path(os.environ['OOS_TEST_ROM'])
        self._assert_rom_branch(rom_path.read_bytes(), f'built_rom({rom_path.name})')


if __name__ == '__main__':
    unittest.main()
