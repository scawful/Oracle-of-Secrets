"""Atlas domain/geometry contract, without ROM or project writes."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as current
import lyra_world_map as W
from test_lyra_project_terrain import fixture, parse


def source():
    data = fixture()
    for i, row in enumerate(data['maps']):
        row['tiles16'] = [[i * 32 + y] * 32 for y in range(32)]
    document = parse(data)
    return document, current.native_checkpoint_boundaries(document)


class LyraWorldMapTest(unittest.TestCase):
    def test_all_legacy_atlas_palette_prize_and_marker_routes_stay_native(self):
        atlas = W.plan(*source())
        for area in range(0xA0):
            with self.subTest(area=area):
                route = atlas.runtime_selection(area)
                expected = 'dark' if 0x40 <= area < 0x80 else 'light'
                self.assertEqual((route.atlas, route.prizes), (expected, expected))
                self.assertEqual(route.marker, 'native_live' if area < 0x80 else 'native_cached')

    def test_a0_through_bf_select_lyra_and_refuse_unbound_runtime(self):
        atlas = W.plan(*source())
        for area in range(0xA0, 0xC0):
            with self.subTest(area=area):
                self.assertEqual(atlas.select(area).atlas, 'lyra')
                self.assertEqual(atlas.select(area).domain, 'special')
                self.assertIsNone(atlas.select(area).prizes)
                with self.assertRaisesRegex(ValueError, 'LYRA_WORLD_MAP_ASSETS_UNBOUND'):
                    atlas.runtime_selection(area)

    def test_configured_template_ids_and_entire_storage_span_preserved(self):
        document, boundary = source()
        atlas = W.plan(document, boundary)
        expected = boundary['named_overlay_templates']
        self.assertEqual([i for i, r in enumerate(atlas.routes) if r.role == 'overlay_template'], expected)
        self.assertEqual(atlas.report()['protected_overlay_templates'], expected)
        for area in range(boundary['protected_legacy_storage_span'][0],
                          boundary['protected_legacy_storage_span'][1] + 1):
            self.assertEqual(atlas.select(area).atlas, 'light')
            self.assertEqual(atlas.select(area).marker, 'native_cached')

    def test_invalid_and_unadmitted_maps_never_alias_light_or_lyra(self):
        atlas = W.plan(*source())
        for area in (-1, 0xC0, 0xC1, 0xFF, 0x100, True, 160.0, 'A0'):
            with self.subTest(area=area), self.assertRaisesRegex(ValueError, 'DOMAIN_UNADMITTED'):
                atlas.select(area)

    def test_lattice_uses_real_order_and_all_four_extreme_cells(self):
        document, boundary = source()
        atlas = W.plan(document, boundary)
        grid = struct.unpack('<32768H', atlas.tile16_grid)
        for area in range(32):
            map_y, map_x = divmod(area, 8)
            for y in range(32):
                start = (map_y * 32 + y) * 256 + map_x * 32
                self.assertEqual(grid[start:start + 32], document.maps[area][y * 32:y * 32 + 32])
        self.assertEqual((grid[0], grid[255], grid[-256], grid[-1]), (0, 224, 799, 1023))

    def test_lattice_is_deterministic_and_does_not_mutate_document_or_boundaries(self):
        document, boundary = source()
        before = copy.deepcopy((document, boundary))
        atlas = W.plan(document, boundary)
        self.assertEqual(W.plan(document, boundary), atlas)
        self.assertEqual((document, boundary), before)
        report = atlas.report()
        self.assertFalse(report['lattice']['artwork'])
        self.assertEqual(report['runtime_selected_maps'], [0xA0, 0xA1])
        self.assertIsNone(report['marker']['native_projection'])
        self.assertIsNone(report['required_assets']['addresses'])
        for flag in ('atlas_art_bound', 'marker_projection_bound', 'allocation_granted',
                     'runtime_admission', 'rom_written'):
            self.assertIs(report[flag], False)

    def test_changed_document_or_rebound_roles_refuse_a_cached_boundary(self):
        document, boundary = source()
        changed = list(document.maps)
        changed[0] = (1,) + changed[0][1:]
        with self.assertRaisesRegex(ValueError, 'BOUNDARY_STALE'):
            W.plan(replace(document, maps=tuple(changed)), boundary)
        for key, value in (('named_overlay_templates', [0x93]),
                           ('protected_legacy_storage_span', [0x93, 0x9E]),
                           ('allowed_tail_maps', [0xA0, 0xBF])):
            candidate = copy.deepcopy(boundary)
            candidate[key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'BOUNDARY_STALE'):
                W.plan(document, candidate)

    def test_document_markers_cover_rectangular_grid_without_native_coordinate_masking(self):
        atlas = W.plan(*source())
        self.assertEqual(atlas.document_marker(0xA0, 0, 0), (0, 0))
        self.assertEqual(atlas.document_marker(0xA1, 0, 0), (512, 0))
        self.assertEqual(atlas.document_marker(0xA8, 0, 0), (0, 512))
        self.assertEqual(atlas.document_marker(0xBF, 511, 511), (4095, 2047))
        for args in ((0x98, 0, 0), (0xA0, 512, 0), (0xA0, 0, -1),
                     (0xA0, 256, 2304), (0xBF, True, 0)):
            with self.subTest(args=args), self.assertRaises(ValueError):
                atlas.document_marker(*args)

    def test_cli_uses_verified_transfer_and_existing_atomic_output_writer(self):
        atlas = W.plan(*source())
        binding = dict(generation=4, operation_id='op', transfer_id='id')
        with tempfile.TemporaryDirectory() as temp:
            destination = Path(temp).resolve() / 'map'
            with patch.object(W, 'from_transfer', return_value=(atlas, binding, [])) as verified:
                self.assertEqual(W.main(['--request', temp + '/request.json', '--project', temp + '/project.yaze',
                    '--base-rom', temp + '/source.sfc', '--output', str(destination)]), 0)
                verified.assert_called_once()
            report = json.loads((destination / 'WORLD_MAP_PLAN.json').read_bytes())
            self.assertEqual((destination / 'lyra.tile16.bin').read_bytes(), atlas.tile16_grid)
            self.assertEqual(report['saved_source'], binding)
            with patch.object(W, 'from_transfer') as verified:
                self.assertEqual(W.main(['--request', 'r', '--project', 'p', '--base-rom', 'b',
                    '--output', str(destination)]), 1)
                verified.assert_not_called()


if __name__ == '__main__':
    unittest.main()
