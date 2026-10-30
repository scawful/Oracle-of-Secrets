"""Schema5 authored area shapes; no inferred grouping or runtime admission."""
import copy
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_terrain as T
from test_lyra_project_terrain import fixture, profile


def area(parent, size, maps):
    return dict(parent_map_id=parent, size=size, maps=maps)


def schema5(areas=None):
    data = fixture()
    data['schema_version'] = 5
    data['gameplay_areas'] = [area(0xA1, 'large', [0xA1, 0xA2, 0xA9, 0xAA])] if areas is None else areas
    return data


def parse(data, *, bindings=None, drafts=True):
    return T.parse_terrain_document(json.dumps(data), profile(),
        expected_asset_bindings=bindings, allow_authoring_drafts=drafts)


class GameplayAreasTest(unittest.TestCase):
    def test_all_four_sizes_allow_unaligned_parents_and_grid_edges(self):
        cases = ((0xBF, 'small', (0xBF,)),
                 (0xB8, 'wide', (0xB8, 0xB9)),
                 (0xA7, 'tall', (0xA7, 0xAF)),
                 (0xA1, 'large', (0xA1, 0xA2, 0xA9, 0xAA)))
        for parent, size, expected in cases:
            with self.subTest(parent=parent, size=size):
                self.assertEqual(T.gameplay_area_footprint(parent, size), expected)
                entry = area(parent, size, list(expected))
                self.assertEqual(parse(schema5([entry])).gameplay_areas, (entry,))

    def test_partial_reordered_areas_and_maps_preserve_authored_area_order(self):
        entries = [area(0xBF, 'small', [0xBF]),
                   area(0xA1, 'large', [0xA1, 0xA2, 0xA9, 0xAA]),
                   area(0xB4, 'wide', [0xB4, 0xB5]), area(0xA7, 'tall', [0xA7, 0xAF])]
        data = schema5(entries)
        data['maps'].reverse()  # Saved map records remain independently keyed.
        original = copy.deepcopy(data)
        document = parse(data)
        self.assertEqual(document.gameplay_areas, tuple(entries))
        self.assertEqual(T.validated_gameplay_areas(document.gameplay_areas), tuple(entries))
        self.assertEqual(document.maps[0][2], 1)
        self.assertEqual(document.maps[31][2], 32)
        self.assertEqual(data, original)
        document.gameplay_areas[1]['maps'][0] = 0xA0
        self.assertEqual(data, original)
        data['gameplay_areas'][0]['maps'][0] = 0xBE
        self.assertEqual(document.gameplay_areas[0]['maps'], [0xBF])

    def test_all32_single_map_areas_are_valid_without_sorting(self):
        entries = [area(parent, 'small', [parent]) for parent in reversed(range(0xA0, 0xC0))]
        self.assertEqual(parse(schema5(entries)).gameplay_areas, tuple(entries))

    def test_schema5_with_and_without_bg_preserves_all_existing_metadata(self):
        original = schema5()
        auth = original['maps'][1]['authoring']
        auth['sprites'] = [dict(id=1, x=31, y=0, sprite_id=255, state=2)]
        auth['doors'] = [dict(id=2, x=5, y=6, entrance_id=0x0B)]
        auth['exits'] = [dict(id=3, x=7, y=8, room_id=0x83, exit_row=None)]
        original['flight_points'] = [dict(id=4, map_id=0xA1, x=0, y=31,
                                           name='Explicit flight', runtime_slot=None)]
        original['edge_connections'] = [dict(id=5, map_a=0xA1, map_b=0xA9,
                                            passage=dict(first_tile=2, last_tile=5))]
        for has_bg in (False, True):
            data = copy.deepcopy(original)
            bindings = None
            if has_bg:
                last = data['maps'][31]['authoring']
                last['properties']['background_palette'] = list(range(127)) + [0x7FFF]
                last['asset_bindings'] = ['a'*64, 'b'*64, 'c'*64]
                bindings = {0xBF: tuple(last['asset_bindings'])}
            before = copy.deepcopy(data)
            document = parse(data, bindings=bindings)
            with self.subTest(background_palette=has_bg):
                self.assertEqual(document.authoring, tuple(entry['authoring'] for entry in data['maps']))
                self.assertEqual(document.properties, tuple(entry['authoring']['properties'] for entry in data['maps']))
                self.assertEqual(document.flight_points, tuple(data['flight_points']))
                self.assertEqual(document.edge_connections, tuple(data['edge_connections']))
                self.assertEqual(document.gameplay_areas, tuple(data['gameplay_areas']))
                self.assertEqual(data, before)

    def test_schema5_default_runtime_refuses_active_gameplay_areas(self):
        with self.assertRaisesRegex(ValueError, 'Unsupported runtime metadata: gameplay_areas'):
            parse(schema5(), drafts=False)

    def test_legacy_schema_shapes_bg_rule_and_positional_constructor_remain(self):
        legacy = fixture()
        document = parse(legacy, drafts=False)
        self.assertEqual(document.gameplay_areas, ())
        positional = T.TerrainDocument(document.profile, document.maps, document.properties,
            document.edge_connections, document.authoring, document.flight_points)
        self.assertEqual(positional, document)
        for version in (3, 4):
            data = fixture()
            data['schema_version'] = version
            if version == 4:
                auth = data['maps'][31]['authoring']
                auth['properties']['background_palette'] = [0x1234]*128
                auth['asset_bindings'] = ['a'*64]*3
            bindings = {0xBF: ('a'*64,)*3} if version == 4 else None
            self.assertEqual(parse(data, bindings=bindings).gameplay_areas, ())
            data['gameplay_areas'] = []
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'header keys'):
                parse(data, bindings=bindings)
        data = fixture()
        data['schema_version'] = 4
        with self.assertRaisesRegex(ValueError, 'schema 4 requires'):
            parse(data)
        for version in (1, 2):
            data = fixture()
            data['schema_version'] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'Expected Yaze Lyra schema'):
                parse(data)

    def test_area_array_shape_count_keys_parent_and_size_are_strict(self):
        valid = area(0xA0, 'small', [0xA0])
        bad_values = (None, {}, 'areas', [], [valid]*33)
        for value in bad_values:
            data = schema5()
            data['gameplay_areas'] = value
            with self.subTest(value=value), self.assertRaises(ValueError):
                parse(data)
        for changed in ({'parent_map_id': True}, {'parent_map_id': 160.0},
                        {'parent_map_id': 0x9F}, {'parent_map_id': 0xC0},
                        {'size': 'Small'}, {'size': 'large '}, {'size': 0}, {'size': None},
                        {'maps': None}, {'maps': [True]}, {'maps': [160.0]},
                        {'maps': [0x9F]}, {'maps': [0xC0]}, {'maps': []}, {'extra': 1}):
            entry = dict(valid, **changed)
            with self.subTest(changed=changed), self.assertRaises(ValueError):
                parse(schema5([entry]))
        for key in valid:
            entry = dict(valid)
            del entry[key]
            with self.subTest(missing=key), self.assertRaisesRegex(ValueError, 'gameplay area keys'):
                parse(schema5([entry]))

    def test_exact_footprint_order_bounds_duplicates_and_overlap_are_required(self):
        malformed = ([area(0xA7, 'wide', [0xA7, 0xA8])],
                     [area(0xB8, 'tall', [0xB8, 0xC0])],
                     [area(0xBF, 'large', [0xBF, 0xC0, 0xC7, 0xC8])],
                     [area(0xA1, 'large', [0xA1, 0xA9, 0xA2, 0xAA])],
                     [area(0xA0, 'wide', [0xA1, 0xA0])],
                     [area(0xA0, 'wide', [0xA0, 0xA0])],
                     [area(0xA0, 'small', [0xA0, 0xA1])],
                     [area(0xA0, 'small', [0xA1])],
                     [area(0xA0, 'small', [0xA0])]*2,
                     [area(0xA0, 'wide', [0xA0, 0xA1]), area(0xA1, 'small', [0xA1])])
        for entries in malformed:
            with self.subTest(entries=entries), self.assertRaises(ValueError):
                parse(schema5(entries))
        for size in ('wide', 'tall', 'large'):
            with self.subTest(size=size), self.assertRaisesRegex(ValueError, 'leaves A0-BF grid'):
                T.gameplay_area_footprint(0xBF, size)

    def test_schema5_preserves_unknown_field_entity_bg_and_asset_refusals(self):
        for mutate in (
                lambda data: data.update(extra=True),
                lambda data: data['maps'][0].update(extra=True),
                lambda data: data['maps'][0]['authoring']['sprites'].append(
                    dict(id=1, x=0, y=0, sprite_id=True, state=0)),
                lambda data: data['maps'][0]['authoring']['properties'].update(background_palette=[True]*128),
                lambda data: data['maps'][0]['authoring'].update(asset_bindings=['a'*64]*3)):
            data = schema5()
            mutate(data)
            with self.assertRaises(ValueError):
                parse(data)
        raw = json.dumps(schema5())
        raw = raw[:-1] + ', "gameplay_areas": []}'
        with self.assertRaisesRegex(ValueError, 'Duplicate JSON keys'):
            T.parse_terrain_document(raw, profile(), allow_authoring_drafts=True)


if __name__ == '__main__':
    unittest.main()
