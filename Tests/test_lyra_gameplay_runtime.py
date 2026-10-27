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
from test_lyra_gameplay_area_plan import document as parsed_document


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

    def test_composer_accepts_lowered_transitions_and_refuses_stale_small_area_constants(self):
        rows = X.A.gameplay_transition_rows(self.f.source, self.f.document)
        for area, values in rows.items():
            self.f.rows[area].update(values)
        self.f.table_plan = self.f.tables()
        self.assertEqual(json.loads(self.f.compose()['prepare.json'])['gameplay_area_plan']['status'], 'ASSIGNED')
        # An independently well-formed table plan still cannot substitute a
        # small-area left delta for the saved large area's right-hand row.
        self.f.rows[0xA2]['ByScreen2'] = 0x40
        with self.assertRaisesRegex(ValueError, 'GAMEPLAY_TRANSITIONS_MISMATCH'):
            self.f.compose(table_plan=self.f.tables())


class GameplayTransitionRowsTest(unittest.TestCase):
    def rows(self, *specs, source=None):
        selected = [dict(parent_map_id=p, size=s, maps=list(T.gameplay_area_footprint(p, s))) for p, s in specs]
        occupied = {m for area in selected for m in area['maps']}
        selected += [dict(parent_map_id=m, size='small', maps=[m])
                     for m in range(0xA0, 0xC0) if m not in occupied]
        return X.A.gameplay_transition_rows(bytes(0x200000) if source is None else source,
                                            parsed_document(selected))

    def test_parent_camera_and_all_native_size_codes(self):
        rows = self.rows((0xA1, 'large'), (0xA4, 'wide'), (0xB0, 'tall'))
        for member in (0xA1, 0xA2, 0xA9, 0xAA):
            self.assertEqual({k: rows[member][k] for k in ('parent', 'area_size', 'transition_y', 'transition_x',
                                                        'scroll_north', 'scroll_west')},
                dict(parent=0xA1, area_size=1, transition_y=0x800, transition_x=0x200,
                     scroll_north=0x720, scroll_west=0x100))
        self.assertEqual((rows[0xA4]['area_size'], rows[0xB0]['area_size'], rows[0xBF]['area_size']), (2, 3, 0))
        self.assertEqual([rows[m]['ByScreen1'] for m in (0xA1, 0xA2, 0xA9, 0xAA)], [0x60, 0x60, 0x1060, 0x1060])
        self.assertEqual([rows[m]['ByScreen2'] for m in (0xA1, 0xA2, 0xA9, 0xAA)], [0x80, 0x80, 0x1080, 0x1080])
        self.assertEqual([rows[m]['ByScreen3'] for m in (0xA1, 0xA2, 0xA9, 0xAA)], [0x1800, 0x1840, 0x1800, 0x1840])
        self.assertEqual([rows[m]['ByScreen4'] for m in (0xA1, 0xA2, 0xA9, 0xAA)], [0x2000, 0x2040, 0x2000, 0x2040])
        self.assertEqual(rows[0xAB]['ByScreen1'], 0xF060)
        self.assertEqual(rows[0xA8]['ByScreen2'], 0xF040)
        self.assertEqual(rows[0xB2]['ByScreen3'], 0x17C0)

    def test_aligned_and_staggered_horizontal_neighbors(self):
        rows = self.rows((0xA0, 'large'), (0xA2, 'large'))
        self.assertEqual(rows[0xA9]['ByScreen2'], 0x80)
        self.assertEqual(rows[0xAA]['ByScreen1'], 0x60)
        rows = self.rows((0xA0, 'large'), (0xAA, 'large'))
        self.assertEqual(rows[0xAA]['ByScreen1'], 0xF060)
        rows = self.rows((0xA1, 'tall'), (0xA2, 'large'))
        self.assertEqual(rows[0xA9]['ByScreen2'], 0x40)
        self.assertEqual(rows[0xAA]['ByScreen1'], 0x60)

    def test_aligned_and_staggered_vertical_neighbors_match_maintained_bytes(self):
        rows = self.rows((0xA0, 'wide'), (0xA8, 'wide'))
        self.assertEqual(rows[0xA1]['ByScreen4'], 0x1000)
        self.assertEqual(rows[0xA9]['ByScreen3'], 0x1800)
        rows = self.rows((0xA0, 'wide'), (0xA9, 'wide'))
        self.assertEqual(rows[0xA9]['ByScreen3'], 0x07C0)
        rows = self.rows((0xA1, 'large'), (0xB0, 'large'))
        self.assertEqual(rows[0xB0]['ByScreen3'], 0x1800)
        self.assertEqual(rows[0xB1]['ByScreen3'], 0x1840)
        self.assertEqual(rows[0xA9]['ByScreen4'], 0x1FC0)

    def test_native_special_seam_is_read_without_modifying_native_rows_or_wrapping_columns(self):
        source = bytearray(0x200000)
        for m in (0x98, 0x99):
            source[X.A.pc(0x02F88D)+m] = 2
            source[X.A.pc(0x288998)+m] = 0x98
        before = bytes(source)
        rows = self.rows(source=before)
        self.assertEqual(rows[0xA1]['ByScreen3'], 0x17C0)
        self.assertEqual(bytes(source), before)
        self.assertEqual(rows[0xA0]['ByScreen1'], 0x60)
        self.assertEqual(set(rows), set(range(0xA0, 0xC0)))


if __name__ == '__main__':
    unittest.main()
