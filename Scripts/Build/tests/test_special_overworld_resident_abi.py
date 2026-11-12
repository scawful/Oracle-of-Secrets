"""Native resident byte-format checks, without ROM allocation or activation."""
import copy
import importlib.util
from pathlib import Path
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import special_overworld_resources as R
import special_overworld_resident_abi as A

SPEC = importlib.util.spec_from_file_location(
    'resident_resource_fixture', Path(__file__).with_name('test_special_overworld_resources.py'))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class ResidentAbiTest(unittest.TestCase):
    def plan(self, capacity=192):
        fixture = F.SavedNativeTerrainResourcesTest()
        fixture.setUp()
        if capacity == 160:
            image = fixture.fixture.image
            records = {entry: R.native.pc(address) for entry, address, _ in fixture.fixture.entries}
            image[fixture.fixture.flags_pc:fixture.fixture.flags_pc + 192] = bytes(192)
            for page in range(128, 192):
                image[records[7] + page] = page
                image[records[30] + page] = 0
            for page in (0x90, 0x91, 0x98, 0x99):
                image[records[7] + page] = 0x90
                image[records[30] + page] = 1
                image[fixture.fixture.flags_pc + page] = 3
            image[R.native.DIRECTORY_PC:R.native.DIRECTORY_PC + 1024] = fixture.fixture.encode(160)
            source = bytes(image)
            exported = fixture.make_export(source)
        else:
            source, exported = fixture.source, fixture.exported
        return R.plan_saved_native_terrain(source, exported)

    @staticmethod
    def reseal(value, key):
        value[key] = R._sha(R._json_bytes({k: v for k, v in value.items() if k != key}))
        return value

    def test_both_capacities_keep_physical_page_lookup_and_sparse_fallback(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity):
                plan = self.plan(capacity)
                abi = A.plan_native_resident_abi(plan, tile16_count=4096)
                blobs = A.validate_native_resident_abi(abi)
                self.assertEqual((abi['first_map'], abi['end_map']), (128, capacity))
                self.assertEqual(abi['byte_counts']['page_directory'], (capacity - 128) * 8)
                self.assertEqual(len(abi['pages']), 4)
                self.assertEqual(len(abi['areas']), 1)
                emitted = A.emit_native_resident_abi(
                    abi, data_pc=0x300000, capacity=0x10000, preimage=bytes(0x10000))
                payload = bytes.fromhex(emitted['payload_hex'])
                placements = {row['label']: row for row in emitted['placements']}
                page_directory = placements[abi['directory_label']]
                animation_directory = placements[abi['animation_directory_label']]
                selected = {page['map_id']: page for page in abi['pages']}
                remaps = {(r['map_id'], r['tile16_id'], r['quadrant']): r['target_word']
                          for area in plan['areas'] for r in area['remaps']}
                for page in range(128, capacity):
                    at = page_directory['binary_offset'] + (page - 128) * 8
                    raw = payload[at:at + 8]
                    animated_at = animation_directory['binary_offset'] + (page - 128) * 11
                    if page not in selected:
                        self.assertEqual(raw, bytes(8))
                        self.assertEqual(payload[animated_at:animated_at + 11], bytes(11))
                        continue
                    item = selected[page]
                    self.assertEqual(int.from_bytes(raw[:3], 'little'), placements[item['index_label']]['snes'])
                    self.assertEqual(int.from_bytes(raw[3:6], 'little'), placements[item['words_label']]['snes'])
                    self.assertEqual((raw[6], raw[7]), (item['area_index'], item['row_count']))
                    index, words = blobs[item['index_label']], blobs[item['words_label']]
                    for tile in item['tile16_ids']:
                        block = index[tile >> 5]
                        row = index[128 + (block - 1) * 32 + (tile & 31)]
                        for quadrant in range(4):
                            self.assertEqual(struct.unpack_from('<H', words, row * 8 + quadrant * 2)[0],
                                             remaps[page, tile, quadrant])
                self.assertFalse(emitted['allocation_granted'])
                self.assertFalse(emitted['ordinary_build_ready'])
                self.assertEqual(abi, A.plan_native_resident_abi(plan, tile16_count=4096))

    def test_byte_zero_target_is_valid_and_missing_row_is_distinct(self):
        plan = self.plan()
        for area in plan['areas']:
            for remap in area['remaps']:
                remap['target_word'] = 0
        self.reseal(plan, 'plan_sha256')
        abi = A.plan_native_resident_abi(plan, tile16_count=4096)
        blobs = A.validate_native_resident_abi(abi)
        for page in abi['pages']:
            index, words = blobs[page['index_label']], blobs[page['words_label']]
            self.assertEqual(set(words), {0})
            tile = page['tile16_ids'][0]
            block = index[tile >> 5]
            self.assertNotEqual(index[128 + (block - 1) * 32 + (tile & 31)], 0)

    def test_own_preimage_bank_boundaries_and_bridge_rederivation(self):
        abi = A.plan_native_resident_abi(self.plan(), tile16_count=4096)
        preimage = bytes(0x10000)
        emitted = A.emit_native_resident_abi(
            abi, data_pc=0x307FF0, capacity=len(preimage), preimage=preimage)
        for row in emitted['placements']:
            self.assertEqual(row['pc'][0] // 0x8000, (row['pc'][1] - 1) // 0x8000)
        bridge = A.resident_runtime_inputs(abi, emitted, preimage=preimage)
        self.assertEqual(len(bridge['parents']), 4)
        self.assertFalse(bridge['runtime_admission'])
        changed = copy.deepcopy(emitted)
        changed['placements'][0]['snes'] += 1
        with self.assertRaisesRegex(ValueError, 'EMISSION_MISMATCH'):
            A.resident_runtime_inputs(abi, changed, preimage=preimage)
        with self.assertRaisesRegex(ValueError, 'ALLOCATION_CAPACITY'):
            A.emit_native_resident_abi(abi, data_pc=0x300000, capacity=8, preimage=bytes(8))
        with self.assertRaisesRegex(ValueError, 'PREIMAGE_REQUIRED'):
            A.emit_native_resident_abi(abi, data_pc=0x300000, capacity=100, preimage=bytes(99))

    def test_transfer_table_relocates_around_another_owners_reservation(self):
        abi = A.plan_native_resident_abi(self.plan(), tile16_count=4096)
        preimage = bytes(0x10000)
        initial = A.emit_native_resident_abi(
            abi, data_pc=0x300000, capacity=len(preimage), preimage=preimage)
        old_table = next(row for row in initial['placements']
                         if row['role'] == 'graphics_transfer_tables')
        first = old_table['pc'][0]
        hole = (first, first + 0x100)
        emitted = A.emit_native_resident_abi(
            abi, data_pc=0x300000, capacity=len(preimage), preimage=preimage,
            excluded_pc_spans=(hole,))
        for row in emitted['placements']:
            self.assertTrue(row['pc'][1] <= hole[0] or row['pc'][0] >= hole[1])
            self.assertEqual(row['pc'][0] // 0x8000, (row['pc'][1]-1) // 0x8000)
        table = next(row for row in emitted['placements']
                     if row['role'] == 'graphics_transfer_tables')
        self.assertGreaterEqual(table['pc'][0], hole[1])
        first_area = abi['areas'][0]
        # The table's own 16-bit profile pointers must use the relocated
        # address, not the cursor from before the excluded reservation.
        self.assertEqual(emitted['transfer_profile_snes'][str(first_area['parent_map_id'])],
                         table['snes'] + abi['end_map'] * 2)
        A.resident_runtime_inputs(abi, emitted, preimage=preimage)
        self.assertEqual(emitted['excluded_extent_bytes'], 0x100)
        self.assertGreaterEqual(emitted['bank_padding_bytes'], 0)

    def test_excluded_reservations_are_validated_and_rederived(self):
        abi = A.plan_native_resident_abi(self.plan(), tile16_count=4096)
        preimage = bytes(0x10000)
        arguments = dict(data_pc=0x300000, capacity=len(preimage), preimage=preimage)
        for spans in (((0x2FFFF0, 0x300100),), ((0x300100, 0x300100),),
                      ((0x300200, 0x300400), (0x300300, 0x300500)),
                      ((0x300200, 0x300300), (0x300000, 0x300100))):
            with self.subTest(spans=spans), self.assertRaisesRegex(
                    ValueError, 'EXCLUDED_SPANS_INVALID'):
                A.emit_native_resident_abi(abi, **arguments, excluded_pc_spans=spans)
        with self.assertRaisesRegex(ValueError, 'ALLOCATION_CAPACITY'):
            A.emit_native_resident_abi(abi, **arguments,
                                       excluded_pc_spans=((0x300000, 0x310000),))
        emitted = A.emit_native_resident_abi(abi, **arguments,
                                            excluded_pc_spans=((0x300000, 0x300100),))
        changed = copy.deepcopy(emitted)
        changed['excluded_pc_spans'] = []
        with self.assertRaisesRegex(ValueError, 'EMISSION_MISMATCH'):
            A.resident_runtime_inputs(abi, changed, preimage=preimage)

    def test_changed_lookup_bytes_overlapping_areas_and_source_hash_refuse(self):
        plan = self.plan()
        changed = copy.deepcopy(plan)
        changed['areas'][0]['maps'].append(0xB0)
        self.reseal(changed, 'plan_sha256')
        with self.assertRaisesRegex(ValueError, 'FOOTPRINT_INVALID'):
            A.plan_native_resident_abi(changed, tile16_count=4096)
        changed = copy.deepcopy(plan)
        changed['areas'][0]['remaps'][0]['target_word'] ^= 1
        with self.assertRaisesRegex(ValueError, 'SOURCE_PLAN_MISMATCH'):
            A.plan_native_resident_abi(changed, tile16_count=4096)
        abi = A.plan_native_resident_abi(plan, tile16_count=4096)
        row = next(row for row in abi['blobs'] if row['role'] == 'page_index')
        raw = bytearray.fromhex(row['payload_hex'])
        raw[0] = 255
        row.update(payload_hex=raw.hex(), sha256=R._sha(raw))
        self.reseal(abi, 'abi_sha256')
        with self.assertRaisesRegex(ValueError, 'BLOCK_INDEX_INVALID'):
            A.validate_native_resident_abi(abi)

    def test_resource_roles_directory_names_and_aliases_cannot_be_substituted(self):
        original = A.plan_native_resident_abi(self.plan(), tile16_count=4096)
        for substitute in ('role', 'directory', 'animation_directory', 'alias'):
            with self.subTest(substitute=substitute):
                abi = copy.deepcopy(original)
                page = abi['pages'][0]
                blob = next(row for row in abi['blobs'] if row['label'] == page['words_label'])
                if substitute == 'role':
                    blob['role'] = 'animation'
                    abi['byte_counts']['page_words'] -= blob['byte_count']
                    abi['byte_counts']['animation'] += blob['byte_count']
                elif substitute == 'alias':
                    page['words_alias'] = 'LyraResidentInjectedAlias'
                else:
                    label = abi['directory_label' if substitute == 'directory' else 'animation_directory_label']
                    previous = blob['label']
                    blob['label'] = label
                    for item in abi['pages']:
                        if item['words_label'] == previous:
                            item['words_label'] = label
                self.reseal(abi, 'abi_sha256')
                with self.assertRaisesRegex(ValueError, 'PAGE_EXTENT_INVALID|BLOBS_INVALID'):
                    A.validate_native_resident_abi(abi)

    def test_shared_graphics_table_matches_retained_twenty_two_byte_abi(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity):
                abi = A.plan_native_resident_abi(self.plan(capacity), tile16_count=4096)
                emitted = A.emit_native_resident_abi(abi, data_pc=0x307FF0,
                    capacity=0x10000, preimage=bytes(0x10000))
                rows = {row['label']: row for row in emitted['placements']}
                table = rows['SharedGraphicsParentProfiles']
                payload = bytes.fromhex(emitted['payload_hex'])
                raw = payload[table['binary_offset']:table['binary_offset'] + table['byte_count']]
                pointer = emitted['transfer_table_snes']
                self.assertEqual(pointer, table['snes'])
                area = abi['areas'][0]
                runs = area['static_runs']
                selected = {page['map_id'] for page in abi['pages']}
                profile_word = (pointer + capacity * 2) & 65535
                for page in range(capacity):
                    self.assertEqual(struct.unpack_from('<H', raw, page * 2)[0],
                                     profile_word if page in selected else 0)
                header = raw[capacity * 2:capacity * 2 + 22]
                normal_count, normal_word, mask, mode = struct.unpack_from('<HHBB', header)
                staging_count, staging_word = struct.unpack_from('<HH', header, 13)
                self.assertEqual((normal_count, staging_count), (len(runs), len(runs)))
                self.assertEqual((mask, mode), (sum(1 << r['native_sheet'] for r in runs), 3))
                self.assertEqual(header[6:13] + header[17:22], bytes(12))
                for index, run in enumerate(runs):
                    offset = normal_word - (pointer & 65535) + index * 7
                    source = rows[area['static_label']]['snes'] + run['source_offset']
                    self.assertEqual(int.from_bytes(raw[offset:offset + 3], 'little'), source)
                    self.assertEqual(struct.unpack_from('<HH', raw, offset + 3),
                                     (run['vram_word_address'], run['byte_count']))
                    offset = staging_word - (pointer & 65535) + index * 8
                    self.assertEqual(int.from_bytes(raw[offset:offset + 3], 'little'), source)
                    self.assertEqual(int.from_bytes(raw[offset + 3:offset + 6], 'little'), run['wram_address'])
                    self.assertEqual(struct.unpack_from('<H', raw, offset + 6)[0], run['byte_count'])
                self.assertEqual(len(raw), capacity * 2 + 22 + len(runs) * 15)
                self.assertEqual(table['pc'][0] // 0x8000, (table['pc'][1] - 1) // 0x8000)
                self.assertIn(f'!GfxRT_Bank = ${pointer >> 16:04X}', emitted['constants_asm'])
                self.assertFalse(emitted['runtime_admission'])

    def test_palette_directory_uses_sparse_physical_pages_and_existing_blobs(self):
        for capacity in (160, 192):
            with self.subTest(capacity=capacity):
                abi = A.plan_native_resident_abi(self.plan(capacity), tile16_count=4096)
                before = copy.deepcopy(abi)
                preimage = bytes(0x10000)
                emitted = A.emit_native_resident_abi(abi, data_pc=0x307FF0,
                    capacity=len(preimage), preimage=preimage)
                self.assertEqual(abi, before)
                rows = {row['label']: row for row in emitted['placements']}
                directory = rows['SpecialOverworldPaletteDirectory']
                payload = bytes.fromhex(emitted['payload_hex'])
                raw = payload[directory['binary_offset']:
                              directory['binary_offset'] + directory['byte_count']]
                self.assertEqual(len(raw), (capacity - 128) * 3)
                self.assertEqual(emitted['palette_directory_snes'], directory['snes'])
                self.assertEqual(emitted['palette_directory_stride'], 3)
                self.assertEqual(emitted['palette_directory_byte_count'], len(raw))
                selected = {page['map_id']: page for page in abi['pages']}
                palette_addresses = set()
                for page in range(128, capacity):
                    at = (page - 128) * 3
                    pointer = int.from_bytes(raw[at:at + 3], 'little')
                    if page not in selected:
                        self.assertEqual(pointer, 0)
                        continue
                    area = abi['areas'][selected[page]['area_index']]
                    row = rows[area['palette_label']]
                    self.assertEqual(pointer, row['snes'])
                    palette_addresses.add(pointer)
                    self.assertEqual(row['role'], 'palette')
                    self.assertEqual(row['byte_count'], 256)
                    self.assertEqual(payload[row['binary_offset']:row['binary_offset'] + 256],
                                     bytes.fromhex(next(b['payload_hex'] for b in abi['blobs']
                                                       if b['label'] == area['palette_label'])))
                # Every member of this large gameplay area shares its one
                # existing packed palette body; no child palette is invented.
                self.assertEqual(len(palette_addresses), 1)
                self.assertEqual(directory['pc'][0] // 0x8000,
                                 (directory['pc'][1] - 1) // 0x8000)
                self.assertIn(f'!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY = ${directory["snes"]:06X}',
                              emitted['constants_asm'])
                self.assertIn('!SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE = 3', emitted['constants_asm'])
                changed = copy.deepcopy(emitted)
                changed['palette_directory_snes'] += 1
                with self.assertRaisesRegex(ValueError, 'EMISSION_MISMATCH'):
                    A.resident_runtime_inputs(abi, changed, preimage=preimage)
                self.assertFalse(emitted['runtime_admission'])


if __name__ == '__main__':
    unittest.main()
