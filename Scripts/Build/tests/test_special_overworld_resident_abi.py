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


if __name__ == '__main__':
    unittest.main()
