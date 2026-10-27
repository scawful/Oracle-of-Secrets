"""Current saved-area consumers with real compiler and bound host transfers.

The external native verifier remains the existing host fixture. These tests
exercise maintained parsing, generation binding, byte lowering and readback;
they do not claim 65816/native gameplay or assign storage to actor lists.
"""
import copy
import json
import unittest
from unittest import mock

from test_lyra_current_composer_binding import ComposerFixture
import test_lyra_current_transfer as transfer_fixtures
from test_lyra_project_admission import observation
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_project_terrain as T


def areas():
    result = [dict(parent_map_id=p, size=s, maps=list(T.gameplay_area_footprint(p, s)))
              for p, s in ((0xA1, 'large'), (0xA4, 'wide'), (0xB0, 'tall'))]
    occupied = {m for area in result for m in area['maps']}
    return result + [dict(parent_map_id=m, size='small', maps=[m])
                     for m in range(0xA0, 0xC0) if m not in occupied]


class GameplayRuntimeTest(unittest.TestCase):
    def setUp(self):
        prepare = transfer_fixtures.CurrentSaveTransferTest.prepare
        def seed(case, **kwargs):
            data = json.loads(case.terrain.read_bytes())
            for m in (0xA1, 0xA2, 0xA9, 0xAA, 0xA4, 0xA5, 0xB0, 0xB8):
                data['maps'][m-0xA0]['authoring']['sprites'] = [dict(
                    id=m, x=31, y=31, sprite_id=m-0xA0, state=0)]
            case.terrain.write_bytes(X.P.encoded(data))
            case.inputs['terrain'] = X.Q.bound(case.terrain)
            case.save['artifacts'] = case.artifacts(case.inputs)
            case.receipt.write_bytes(X.P.encoded(case.save))
            case.proof.clear()
            case.proof.update(observation(case.rom.read_bytes(), data)[1])
            case.proof['terrain_sha256'] = X.R.sha(case.terrain.read_bytes())
            return prepare(case, **kwargs)
        with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest, 'prepare', seed):
            self.f = ComposerFixture(self, gameplay_areas=areas())

    def test_full32_compiler_uses_all_four_authored_sizes_preserving_native160(self):
        directory, closure = X.A.render_dependency_plan(X.V.FULL_MAPS, document=self.f.document)
        self.assertEqual(closure, tuple(X.V.FULL_MAPS))
        expected = {0xA0: (0xA0,)*4, 0xA1: (0xA1, 0xA2, 0xA9, 0xAA),
                    0xA4: (0xA4, 0xA5, 0xA4, 0xA5), 0xB0: (0xB0, 0xB0, 0xB8, 0xB8)}
        for area in areas():
            for member in area['maps']:
                self.assertEqual(directory[member], expected.get(area['parent_map_id'], (member,)*4))
        case = self.f.contract_fixture
        plan, payload = X.V.compile_native_plan(self.f.source, self.f.document,
            case.allocation(), directory, spare_tile32_ids=(13993, 13994, 13995),
            current_source_profile=self.f.profile)
        self.assertEqual(len(payload), 32*518)
        self.assertEqual((plan['native_maps_preserved'], plan['native_planes_preserved']), (160, 320))
        self.assertEqual(plan['render_directory'], [dict(map_id=m, quadrant_maps=list(directory[m]))
                                                   for m in X.V.FULL_MAPS])
        self.assertFalse(plan['runtime_admission'])
        self.assertFalse(case.case.candidate.exists())
        changed = copy.deepcopy(directory)
        changed[0xA2] = T.quadrant_map_plan(0xA2)
        with self.assertRaisesRegex(ValueError, 'GAMEPLAY_AREAS_RENDER_MISMATCH'):
            X.V.compile_native_plan(self.f.source, self.f.document, case.allocation(), changed,
                                    current_source_profile=self.f.profile)

    def test_parent_actor_lists_offset_once_and_preserve_source_placement_provenance(self):
        plan = L.plan_current_actor_streams(self.f.source, self.f.document,
                                           current_source_profile=self.f.profile)
        rows = {(row['map_id'], row['state']): row for row in plan['streams']}
        vectors = {0xA1: '1f1f011f3f023f1f093f3f0aff',
                   0xA4: '1f1f041f3f05ff', 0xB0: '1f1f103f1f18ff'}
        for area in areas():
            parent = area['parent_map_id']
            for member in area['maps']:
                row = rows[member, 0]
                self.assertEqual(row['payload_hex'], vectors.get(parent, 'ff'))
                self.assertEqual(row['parent_map_id'], parent)
                self.assertEqual(row['source_maps'], area['maps'])
                self.assertEqual(row['placement_maps'], area['maps'] if parent in vectors else [])
                self.assertEqual(row['placement_ids'], area['maps'] if parent in vectors else [])
                self.assertEqual(rows[member, 1]['payload_hex'], 'ff')
                self.assertEqual(rows[member, 2]['payload_hex'], 'ff')
        self.assertEqual(plan['demand']['placements'], 8)
        self.assertIsNone(plan['storage'])
        self.assertIsNone(plan['pointers'])

    def test_unassigned_or_cross_area_render_inputs_refuse_without_inferred_layout(self):
        from dataclasses import replace
        partial = replace(self.f.document, gameplay_areas=(areas()[0],))
        with self.assertRaisesRegex(ValueError, 'GAMEPLAY_AREAS_UNASSIGNED'):
            X.A.render_dependency_plan(X.V.FULL_MAPS, document=partial)
        directory, closure = X.A.render_dependency_plan([0xA2], document=partial)
        self.assertEqual(directory, {0xA2: (0xA1, 0xA2, 0xA9, 0xAA)})
        self.assertEqual(closure, (0xA1, 0xA2, 0xA9, 0xAA))
        with self.assertRaisesRegex(ValueError, 'Render footprint'):
            X.A.render_dependency_plan([0xA2], [dict(map_id=0xA2, quadrant_maps=[0xA2]*4)],
                                       document=partial)


if __name__ == '__main__':
    unittest.main()
