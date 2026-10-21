"""Source ownership is required before actual-byte candidate allocation."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_admission as A
import lyra_project_allocation as R


def actual_input():
    source = bytearray(0x400000)
    source[A.pc(A.EMPTY_ACTORS)] = 255
    source[A.pc(A.EMPTY_HIDDEN_ITEMS):A.pc(A.EMPTY_HIDDEN_ITEMS) + 2] = b'\xff\xff'
    return bytes(source)


class LyraSourceAllocationTest(unittest.TestCase):
    def test_fresh_zero_preimages_require_source_claim_and_validate_exactly(self):
        source = actual_input()
        manifest = R.derive_allocation(source)
        allocation = A.parse_allocation(manifest, source)
        A.verify_allocation(source, allocation, manifest['reservation'])
        self.assertEqual(manifest, R.derive_allocation(source))
        self.assertEqual(manifest['source_rom_sha256'], R.sha(source))
        self.assertEqual(manifest['stream_ranges'], [[0x3D4000, 0x3D4818]])
        self.assertEqual(manifest['admission']['production_maps'], [])
        self.assertEqual(manifest['owned_tile32_ids'], [])
        self.assertTrue(all(r['fill'] == 0 for r in manifest['reservation']['regions']))
        # Historical FF assumptions cannot admit this real zero-filled source.
        with self.assertRaisesRegex(ValueError, 'occupied'):
            A.verify_allocation(source, allocation)

    def test_rebinding_only_the_old_outer_hash_cannot_reuse_a_reservation(self):
        source = actual_input()
        manifest = R.derive_allocation(source)
        changed = bytearray(source)
        changed[0x10000] = 1  # Outside all three extents.
        manifest['source_rom_sha256'] = R.sha(changed)
        allocation = A.parse_allocation(manifest, bytes(changed))
        with self.assertRaisesRegex(ValueError, 'stale or forged'):
            A.verify_allocation(bytes(changed), allocation, manifest['reservation'])

    def test_occupied_owned_range_and_changed_source_ledger_refuse(self):
        source = actual_input()
        changed = bytearray(source)
        changed[0x3D4001] = 0x21
        with self.assertRaisesRegex(ValueError, 'occupied'):
            R.derive_allocation(bytes(changed))
        manifest = R.derive_allocation(source)
        allocation = A.parse_allocation(manifest, source)
        ledger = json.loads(R.LEDGER.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ledger.json'
            ledger['description'] += ' changed source identity'
            path.write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError, 'stale or forged'):
                R.verify_reservation(source, allocation, manifest['reservation'], ledger_path=path)
            ledger['rom_candidate_reservations'] = []
            path.write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError, 'No unique source-declared'):
                R.derive_allocation(source, ledger_path=path)

    def test_foreign_streams_or_tile32_grant_cannot_hide_behind_valid_preimages(self):
        source = actual_input()
        manifest = R.derive_allocation(source)
        for field, value in (('stream_ranges', [[0x3D4000, 0x3E0000]]), ('owned_tile32_ids', [10])):
            altered = copy.deepcopy(manifest)
            altered[field] = value
            allocation = A.parse_allocation(altered, source)
            with self.assertRaisesRegex(ValueError, 'differs from the source-declared'):
                A.verify_allocation(source, allocation, altered['reservation'])

    def test_native_empty_list_checks_still_run_for_new_reservation(self):
        source = bytearray(actual_input())
        source[A.pc(A.EMPTY_ACTORS)] = 0
        source = bytes(source)
        manifest = R.derive_allocation(source)
        with self.assertRaisesRegex(ValueError, 'empty actor'):
            A.verify_allocation(source, A.parse_allocation(manifest, source), manifest['reservation'])

    def test_another_rom_owner_blocks_derivation_even_when_bytes_are_zero(self):
        source = actual_input()
        ledger = json.loads(R.LEDGER.read_text())
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'ledger.json'
            ledger['claims'].append(dict(id='future-other-owner', space='pc_rom', base=0x144010, size=4))
            path.write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError, 'conflicts with ROM owner'):
                R.derive_allocation(source, ledger_path=path)
            ledger['claims'].pop()
            ledger['allocation_available'] = True
            path.write_text(json.dumps(ledger))
            with self.assertRaisesRegex(ValueError, 'general free-space'):
                R.derive_allocation(source, ledger_path=path)


if __name__ == '__main__':
    unittest.main()
