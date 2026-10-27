"""Authored gameplay-area source metadata; no storage, ROM or runtime writer."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_admission as A
import lyra_project_terrain as T
from test_lyra_project_terrain import fixture, profile


def document(areas=None):
    data = fixture()
    if areas is not None:
        data['schema_version'] = 5
        data['gameplay_areas'] = copy.deepcopy(areas)
    return T.parse_terrain_document(json.dumps(data), profile(),
                                    allow_authoring_drafts=True)


def area(parent, size):
    return dict(parent_map_id=parent, size=size,
                maps=list(T.gameplay_area_footprint(parent, size)))


class GameplayAreaPlanTest(unittest.TestCase):
    def test_legacy_default_remains_unassigned_without_inferred_rows(self):
        parsed = document()
        constructed = T.TerrainDocument(parsed.profile, parsed.maps,
                                        parsed.properties)
        for source in (parsed, constructed):
            plan = A.gameplay_area_plan(source)
            self.assertEqual(plan, dict(kind='lyra.gameplay_area_source_plan.v1',
                status='UNASSIGNED', complete=False, areas=[], assignments=[],
                render_footprints=[], unassigned_maps=list(range(0xA0, 0xC0)),
                allocation_granted=False, publication_authorized=False,
                runtime_admission=False))

    def test_four_sizes_use_native_codes_and_exact_quadrants_for_every_member(self):
        cases = (
            (0xBF, 'small', 0, [0xBF] * 4),
            (0xA1, 'wide', 2, [0xA1, 0xA2, 0xA1, 0xA2]),
            (0xA9, 'tall', 3, [0xA9, 0xA9, 0xB1, 0xB1]),
            (0xA1, 'large', 1, [0xA1, 0xA2, 0xA9, 0xAA]),
        )
        for parent, size, code, quadrants in cases:
            with self.subTest(parent=parent, size=size):
                authored = area(parent, size)
                source = document([authored])
                plan = A.gameplay_area_plan(source)
                self.assertEqual(plan['status'], 'PARTIAL')
                self.assertIs(plan['complete'], False)
                self.assertEqual(plan['areas'], [authored])
                self.assertEqual(plan['assignments'], [dict(map_id=map_id,
                    parent_map_id=parent, size=size, area_size_code=code)
                    for map_id in authored['maps']])
                self.assertEqual(plan['render_footprints'], [dict(map_id=map_id,
                    quadrant_maps=quadrants) for map_id in authored['maps']])
                self.assertEqual(plan['unassigned_maps'], [m for m in range(0xA0, 0xC0)
                    if m not in authored['maps']])

    def test_partial_authored_order_is_retained_without_rows_for_unassigned_maps(self):
        authored = [area(0xB0, 'wide'), area(0xA1, 'large')]
        source = document(authored)
        plan = A.gameplay_area_plan(source)
        self.assertEqual(plan['areas'], authored)
        self.assertEqual([row['map_id'] for row in plan['assignments']],
                         [0xB0, 0xB1, 0xA1, 0xA2, 0xA9, 0xAA])
        self.assertEqual([row['map_id'] for row in plan['render_footprints']],
                         [0xB0, 0xB1, 0xA1, 0xA2, 0xA9, 0xAA])
        self.assertEqual(plan['unassigned_maps'], [m for m in range(0xA0, 0xC0)
                         if m not in {0xB0, 0xB1, 0xA1, 0xA2, 0xA9, 0xAA}])
        self.assertEqual(len(plan['assignments']) + len(plan['unassigned_maps']), 32)

    def test_explicit_full_coverage_is_assigned_for_large_or_small_areas(self):
        choices = (
            [area(parent, 'large') for parent in
             (0xA0, 0xA2, 0xA4, 0xA6, 0xB0, 0xB2, 0xB4, 0xB6)],
            [area(parent, 'small') for parent in range(0xA0, 0xC0)],
        )
        for authored in choices:
            with self.subTest(areas=len(authored)):
                plan = A.gameplay_area_plan(document(authored))
                self.assertEqual(plan['status'], 'ASSIGNED')
                self.assertIs(plan['complete'], True)
                self.assertEqual(plan['unassigned_maps'], [])
                self.assertEqual(len(plan['assignments']), 32)
                self.assertEqual({r['map_id'] for r in plan['assignments']},
                                 set(range(0xA0, 0xC0)))
                self.assertEqual(plan['areas'], authored)

    def test_plan_and_member_quad_arrays_do_not_alias_saved_model(self):
        source = document([area(0xA1, 'large')])
        before = copy.deepcopy(source)
        plan = A.gameplay_area_plan(source)
        plan['areas'][0]['maps'].reverse()
        plan['render_footprints'][0]['quadrant_maps'][0] = 0xBF
        self.assertEqual(source, before)
        self.assertEqual(plan['render_footprints'][1]['quadrant_maps'],
                         [0xA1, 0xA2, 0xA9, 0xAA])
        self.assertEqual(A.gameplay_area_plan(source)['areas'],
                         list(source.gameplay_areas))

    def test_shared_validator_and_footprint_helpers_are_the_authority(self):
        source = document([area(0xA9, 'large')])
        with mock.patch.object(A, 'validated_gameplay_areas',
                               wraps=T.validated_gameplay_areas) as validate:
            with mock.patch.object(A, 'gameplay_area_footprint',
                                   wraps=T.gameplay_area_footprint) as footprint:
                A.gameplay_area_plan(source)
        validate.assert_called_once_with(source.gameplay_areas)
        footprint.assert_called_once_with(0xA9, 'large')
        with mock.patch.object(A, 'validated_gameplay_areas',
                               side_effect=ValueError('shared validator refusal')):
            with self.assertRaisesRegex(ValueError, 'shared validator refusal'):
                A.gameplay_area_plan(source)

    def test_invalid_manually_constructed_models_fail_closed(self):
        source = document()
        malformed = (
            None, False, {}, [], ('large',),
            (dict(parent_map_id=True, size='small', maps=[0xA0]),),
            (dict(parent_map_id=0xA1, size='LARGE', maps=[0xA1, 0xA2, 0xA9, 0xAA]),),
            (dict(parent_map_id=0xA7, size='wide', maps=[0xA7, 0xA8]),),
            (dict(parent_map_id=0xB8, size='tall', maps=[0xB8, 0xC0]),),
            (dict(parent_map_id=0xA1, size='large', maps=[0xA1, 0xA9, 0xA2, 0xAA]),),
            (dict(parent_map_id=0xA1, size='small', maps=[True]),),
            (area(0xA1, 'large'), area(0xA2, 'small')),
        )
        for value in malformed:
            with self.subTest(value=value), self.assertRaises(ValueError):
                A.gameplay_area_plan(replace(source, gameplay_areas=value))
        for value in (None, SimpleNamespace(gameplay_areas=())):
            with self.subTest(document=value), self.assertRaisesRegex(
                    ValueError, 'parsed TerrainDocument'):
                A.gameplay_area_plan(value)

    def test_metadata_planning_never_dispatches_writers_or_grants_authority(self):
        source = document([area(0xA9, 'large')])
        refusal = AssertionError('No writer or native verifier is part of this plan')
        with (mock.patch.object(Path, 'write_bytes', side_effect=refusal),
              mock.patch.object(Path, 'write_text', side_effect=refusal),
              mock.patch.object(A, 'relocated_table_payloads', side_effect=refusal),
              mock.patch.object(A, 'native_verify', side_effect=refusal),
              mock.patch.object(T, 'compile_terrain', side_effect=refusal)):
            plan = A.gameplay_area_plan(source)
        for key in ('allocation_granted', 'publication_authorized', 'runtime_admission'):
            self.assertIs(plan[key], False)
        self.assertNotIn('storage', plan)
        self.assertNotIn('writes', plan)
        self.assertEqual(json.loads(json.dumps(plan)), plan)

    def test_historical_table_publishers_refuse_areas_before_reading_any_payload(self):
        source = document([area(0xA1, 'large')])
        for publisher in (A.relocated_table_payloads, A.relocated_table_plan):
            with self.subTest(publisher=publisher.__name__), self.assertRaisesRegex(
                    ValueError, 'no authored gameplay area consumer'):
                publisher(b'', source, object(), ())

    def test_legacy_tables_and_render_dependency_behavior_stay_unchanged(self):
        source = bytes(0x400000)
        compiled = SimpleNamespace(maps=[])
        self.assertEqual(A.relocated_table_payloads(source, document(), compiled, ()),
                         A.relocated_table_payloads(source, None, compiled, ()))
        directory, closure = A.render_dependency_plan([0xA1, 0xBF])
        self.assertEqual(directory, {0xA1: (0xA1, 0xA2, 0xA9, 0xAA),
                                     0xBF: (0xBF, 0xBF, 0xBF, 0xBF)})
        self.assertEqual(closure, (0xA1, 0xA2, 0xA9, 0xAA, 0xBF))


if __name__ == '__main__':
    unittest.main()
