"""A saved-source partition retains native3 without granting them to Lyra."""
import copy
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_allocation as R
import lyra_project_tile32 as T
import lyra_project_prepare as Q
import lyra_project_admission as A

WORKING = Path('/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-Working/oracle-working.sfc')


class NativePartitionTest(unittest.TestCase):
    def setUp(self):
        self.claim, self.ledger_hash = R.reservation_claim()
        self.partition = self.claim['current_saved_native_tile32_partition']

    def request(self, count, source_hash):
        return dict(source_rom_sha256=source_hash, terrain_sha256='fixture', candidate_maps=[0xA1],
                    render_directory=[], missing_definitions=[[i] * 4 for i in range(count)], consumer_receipt={})

    def test_partition_activates_only_for_exact_named_saved_source(self):
        self.assertEqual(T.native_partition(self.claim, self.partition['source_rom_sha256']), self.partition)
        self.assertIsNone(T.native_partition(self.claim, 'a' * 64))
        self.assertIsNone(T.native_partition({}, self.partition['source_rom_sha256']))

    def test_partition_cannot_be_repinned_or_widened_by_changing_ledger(self):
        for key, value in (('source_rom_sha256', 'a' * 64), ('scope', 'production'),
                           ('production_admission', True), ('native_tile32_ids', [0x453C, 0x453D, 0x453E, 0x453F]),
                           ('original_quadrants', [0] * 4), ('native_references', []), ('native_definitions', [])):
            claim = copy.deepcopy(self.claim)
            claim['current_saved_native_tile32_partition'][key] = value
            with self.subTest(key=key), self.assertRaises(ValueError):
                T.native_partition(claim, self.partition['source_rom_sha256'])

    def test_generic_joint_assignment_excludes_native3_and_refuses126(self):
        request = self.request(125, self.partition['source_rom_sha256'])
        assigned = T._assignments([request], self.claim['tile32_candidate_reservation'], self.claim)
        self.assertEqual([r['tile32_id'] for r in assigned], list(range(0x44C0, 0x453D)))
        with self.assertRaisesRegex(ValueError, '126 definitions exceed 125'):
            T._assignments([self.request(126, request['source_rom_sha256'])],
                           self.claim['tile32_candidate_reservation'], self.claim)

    def test_historical_joint_assignment_keeps_original128_id_policy(self):
        assigned = T._assignments([self.request(128, 'historical_source')],
                                  self.claim['tile32_candidate_reservation'], self.claim)
        self.assertEqual([r['tile32_id'] for r in assigned], list(range(0x44C0, 0x4540)))

    def test_current_assignment_has10_tail_ids_after_frozen115(self):
        frozen = tuple((0x44C0 + i, (i + 1,) * 4) for i in range(115))
        with (mock.patch.object(Q.T32, 'ownership', return_value={'retained_native_ids': [0x453D, 0x453E, 0x453F]}),
              mock.patch.object(Q.A, 'read_tile32', return_value=(0,) * 4),
              mock.patch.object(Q.C, '_missing', return_value=[(i,) * 4 for i in range(1000, 1010)])):
            assignment = Q.current_assignment(b'fixture', b'terrain', object(), frozen, R.LEDGER)
            self.assertEqual([r['tile32_id'] for r in assignment['assignments']][-10:], list(range(0x4533, 0x453D)))
            with mock.patch.object(Q.C, '_missing', return_value=[(i,) * 4 for i in range(1000, 1011)]):
                with self.assertRaisesRegex(ValueError, '11 new definitions exceed 10'):
                    Q.current_assignment(b'fixture', b'terrain', object(), frozen, R.LEDGER)


@unittest.skipUnless(WORKING.exists(), 'Exact private saved Working source unavailable in CI')
class ActualSavedPartitionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source = WORKING.read_bytes()
        cls.claim, _ = R.reservation_claim()
        cls.partition = cls.claim['current_saved_native_tile32_partition']
        if R.sha(cls.source) != cls.partition['source_rom_sha256']:
            raise unittest.SkipTest('Working project has a newer saved source')

    def test_all160_consumers_and125_lyra_ids_are_exact(self):
        receipt = T.ownership(self.source, self.claim)
        self.assertEqual(receipt['native_maps'], 160)
        self.assertEqual(receipt['retained_native_references'], self.partition['native_references'])
        self.assertEqual(receipt['lyra_assignable_ids'], list(range(0x44C0, 0x453D)))
        self.assertEqual(Q.resource_report(self.source, R.LEDGER), [])

    def test_any_editor_save_change_expires_named_partition(self):
        source = bytearray(self.source)
        source[0x11111] ^= 1
        with self.assertRaisesRegex(ValueError, 'packed Tile32 preimage differs'):
            T.ownership(bytes(source), self.claim)

    def test_normalization_still_protects_neighbor453c_packed_bytes(self):
        source = bytearray(self.source)
        source[A.TILE32_BASES[0] + 0x453C // 4 * 6] ^= 1
        # Isolate packed-byte validation from the stronger whole-ROM hash gate.
        with mock.patch.object(T, 'native_partition', return_value=self.partition):
            with self.assertRaisesRegex(ValueError, 'packed Tile32 preimage differs'):
                T.ownership(bytes(source), self.claim)


if __name__ == '__main__':
    unittest.main()
