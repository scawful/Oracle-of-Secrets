"""Synthetic native-source compiler controls; no production allocation proof."""
import copy
import hashlib
import importlib.util
import json
from pathlib import Path
import struct
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


if __name__ == '__main__':
    unittest.main()
