"""Focused terrain-delta manifest validation against pinned handoff inputs."""
import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HANDOFF = Path('/Users/scawful/.context/projects/oracle-of-secrets/scratchpad/handoffs')
sys.path.insert(0, str(ROOT / 'Scripts/Build'))

import lyra_project_allocation as R
import lyra_project_delta as D

WISDOM = HANDOFF / 'wisdom_dry_route_2026-10-21/compiler-input/wisdom-r01.terrain-delta.json'
WISDOM_SHA = '90d8faa335b0bf0ccb028b69f4b5b493227097508832d6c9a4f5a5a69d5e35fa'
POWER = HANDOFF / 'power_region_route_2026-10-21/compiler-input/power-r03.terrain-delta.json'
POWER_SHA = 'a794a382348ab8a0cff2fd33f7706788e6a8136dca5bd6d5024277cc9a4b833a'
JOINT = HANDOFF / 'lyra_native_w02_2026-10-21/tile32-slice/actual-final/JOINT_ASSIGNMENT.json'
JOINT_SHA = '24ca5f6c8deefcf2b937b2e7da1d2969a7c422b2a7f25a3907460558d109e34c'
LEDGER_SHA = 'e782d3ef159a6f2506538c86bf94a0f11761620569ae1c617f2e72729e8e2ba3'
# This frozen baseline belongs to the released C1 ledger, not the new tail-state
# ownership context. Never redirect the allocator's default ledger globally.
HISTORICAL_LEDGER = Path('/Users/scawful/.cursor/worktrees/oracle-of-secrets/'
    'lyra-delta-intake-20261021/Config/allocation_ownership.json')


def _load(path: Path, digest: str) -> dict:
    return D.load_manifest(path, expected_sha256=digest)


@unittest.skipUnless(all(p.exists() for p in (WISDOM, POWER, JOINT, HISTORICAL_LEDGER)),
                     'Exact historical manifest/assignment inputs are unavailable in CI')
class LyraTerrainDeltaTest(unittest.TestCase):
    def test_immutable_w02_assignment_and_ledger_hashes(self):
        self.assertEqual(R.sha(JOINT.read_bytes()), JOINT_SHA)
        self.assertEqual(R.sha(HISTORICAL_LEDGER.read_bytes()), LEDGER_SHA)

    def test_wisdom_manifest_normalizes_and_reconstructs(self):
        manifest = _load(WISDOM, WISDOM_SHA)
        normalized = D.normalize_manifest(manifest, manifest_sha256=WISDOM_SHA)
        self.assertEqual(normalized.kind, D.NORMALIZED_KIND)
        self.assertTrue(normalized.compiler_target_input)
        self.assertIsNone(normalized.w02_reference_only)
        cells = sum(len(m['tile16_changes']) for m in normalized.maps)
        blocks = sum(len(m['tile32_content_changes']) for m in normalized.maps)
        self.assertEqual((cells, blocks), (157, 41))
        self.assertEqual(len(normalized.new_content_relative_to_source_used_quads), 3)
        self.assertTrue(all(r['production_slot'] is None and r['relocation_required']
                            for r in normalized.content_requests))
        fixture_roles = [r for r in normalized.content_requests if r['role'] == 'fixture_evidence_only']
        self.assertEqual(len(fixture_roles), 3)
        self.assertTrue(all(r['fixture_candidate_slot'] in (17727, 17726, 17725) for r in fixture_roles))
        source_path = Path(manifest['inputs']['source_rom']['path'])
        target_path = Path(manifest['inputs']['candidate_fixture_rom']['path'])
        source = source_path.read_bytes()
        target = target_path.read_bytes()
        self.assertEqual(R.sha(source), manifest['inputs']['source_rom']['sha256'])
        self.assertEqual(R.sha(target), manifest['inputs']['candidate_fixture_rom']['sha256'])
        map_ids = tuple(m['map_id'] for m in manifest['maps'])
        grids = D.native_grids_from_rom(source, map_ids)
        rebuilt = D.reconstruct(manifest, grids)
        for mid in map_ids:
            self.assertEqual(rebuilt[mid], D.native_map_grid(target, mid))
        neutral = copy.deepcopy(manifest)
        neutral.pop('fixture_evidence_only')
        self.assertEqual(D.reconstruct(neutral, grids), rebuilt)

    def test_power_compiler_maps_and_provenance_separation(self):
        manifest = _load(POWER, POWER_SHA)
        normalized = D.normalize_manifest(manifest, manifest_sha256=POWER_SHA)
        self.assertEqual(len(normalized.maps), 1)
        self.assertEqual(normalized.maps[0]['map_id'], 55)
        self.assertEqual(len(normalized.maps[0]['tile16_changes']), 21)
        self.assertEqual(len(normalized.maps[0]['tile32_content_changes']), 8)
        self.assertEqual(len(normalized.new_content_relative_to_source_used_quads), 0)
        provenance = normalized.lyra_source_provenance
        self.assertIsNotNone(provenance)
        self.assertFalse(provenance['compiler_target_input'])
        self.assertEqual(len(provenance['map_summaries']), 4)
        self.assertEqual({row['map_id'] for row in provenance['map_summaries']}, {176, 177, 184, 185})
        prov_cells = sum(row['tile16_change_count'] for row in provenance['map_summaries'])
        prov_blocks = sum(row['tile32_block_change_count'] for row in provenance['map_summaries'])
        self.assertEqual((prov_cells, prov_blocks), (149, 51))
        reference = normalized.w02_reference_only
        self.assertFalse(reference['duplicate_or_replace_input'])
        self.assertEqual(reference['joint_assignment']['sha256'], JOINT_SHA)
        source = Path(manifest['inputs']['source_rom']['path']).read_bytes()
        target = Path(manifest['inputs']['candidate_fixture_rom']['path']).read_bytes()
        rebuilt = D.reconstruct(manifest, D.native_grids_from_rom(source, (55,)))
        self.assertEqual(rebuilt[55], D.native_map_grid(target, 55))
        lyra = manifest['lyra_source_provenance']
        sidecar_source = Path(lyra['source_sidecar']['path']).read_bytes()
        sidecar_target = Path(lyra['target_sidecar']['path']).read_bytes()
        self.assertEqual(R.sha(sidecar_source), lyra['source_sidecar']['sha256'])
        self.assertEqual(R.sha(sidecar_target), lyra['target_sidecar']['sha256'])

    def test_stale_tile16_preimage_refused(self):
        manifest = _load(WISDOM, WISDOM_SHA)
        source = Path(manifest['inputs']['source_rom']['path']).read_bytes()
        grids = D.native_grids_from_rom(source, (144, 152))
        stale = copy.deepcopy(manifest)
        stale['maps'][0]['tile16_delta'][0][2] ^= 1
        with self.assertRaisesRegex(ValueError, 'Stale tile16 preimage'):
            D.reconstruct(stale, grids)

    def test_reordered_quartet_refused(self):
        manifest = _load(WISDOM, WISDOM_SHA)
        source = Path(manifest['inputs']['source_rom']['path']).read_bytes()
        grids = D.native_grids_from_rom(source, (144, 152))
        reordered = copy.deepcopy(manifest)
        key = manifest['new_content_relative_to_source_used_quads'][0]
        entry = reordered['quad_library'][key]
        entry['tile16'] = list(reversed(entry['tile16']))
        with self.assertRaisesRegex(ValueError, 'content_sha256 differs'):
            D.validate_manifest(reordered)
        reordered = copy.deepcopy(manifest)
        reordered['quad_library'][key]['tile16'] = list(reversed(reordered['quad_library'][key]['tile16']))
        reordered['quad_library'][key]['content_sha256'] = D.content_sha256(
            reordered['quad_library'][key]['tile16'])
        with self.assertRaisesRegex(ValueError, 'does not match tile16 order'):
            D.validate_manifest(reordered)
        reordered = copy.deepcopy(manifest)
        reordered['quad_library'][key]['tile16'] = list(reversed(reordered['quad_library'][key]['tile16']))
        with self.assertRaisesRegex(ValueError, 'tile32|tile16 and tile32'):
            D.reconstruct(reordered, grids)

    def test_manifest_structure_guards_from_root_review(self):
        manifest = copy.deepcopy(_load(WISDOM, WISDOM_SHA))
        duplicate = copy.deepcopy(manifest)
        duplicate['maps'].append(copy.deepcopy(duplicate['maps'][0]))
        with self.assertRaisesRegex(ValueError, 'Duplicate Compiler map_id'):
            D.normalize_manifest(duplicate, manifest_sha256=WISDOM_SHA)
        wrong_id = copy.deepcopy(manifest)
        wrong_id['maps'][0]['map_id'] = 192
        with self.assertRaisesRegex(ValueError, 'outside supported range'):
            D.normalize_manifest(wrong_id, manifest_sha256=WISDOM_SHA)
        swapped_encoding = copy.deepcopy(manifest)
        swapped_encoding['encoding']['tile16_delta_row'] = [
            'y_tile16', 'x_tile16', 'source_tile16', 'target_tile16']
        with self.assertRaisesRegex(ValueError, 'tile16_delta_row field order'):
            D.normalize_manifest(swapped_encoding, manifest_sha256=WISDOM_SHA)

    def test_fixture_allocation_use_refused(self):
        normalized = D.normalize_manifest(_load(WISDOM, WISDOM_SHA), manifest_sha256=WISDOM_SHA).to_dict()
        normalized['content_requests'][0]['production_slot'] = 17727
        with self.assertRaisesRegex(ValueError, 'production_slot'):
            D.refuse_fixture_allocation_use(normalized)
        normalized = D.normalize_manifest(_load(POWER, POWER_SHA), manifest_sha256=POWER_SHA).to_dict()
        normalized['fixture_witness_streams'][0]['production_pc'] = 0x2D7C00
        with self.assertRaisesRegex(ValueError, 'Fixture stream PC'):
            D.refuse_fixture_allocation_use(normalized)


if __name__ == '__main__':
    unittest.main()
