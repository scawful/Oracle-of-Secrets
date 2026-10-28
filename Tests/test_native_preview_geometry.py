"""Native drawing origins: camera position and rendered map must agree."""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'Scripts/Build'))
from checkpoint_registry import _native_tilemap_origin


class NativePreviewGeometryTest(unittest.TestCase):
    def test_ferry_second_half_keeps_its_physical_column(self):
        # Build09 Ferry43: camera648,3344; parent30 starts0,3072.
        # The native 64-column buffer needs row17/column40, not column8.
        origin = _native_tilemap_origin(648, 3344, 0, 3072, 1024, 512)
        self.assertEqual(origin, 0x08D0)
        self.assertEqual(divmod(origin, 128), (17, 80))
        old = ((3344 & 0x1F0) << 3) | ((648 & 0x1F0) >> 3)
        self.assertEqual(old, 0x0890)
        self.assertEqual((origin-old)//2*16, 512)

    def test_existing_small_sky_and_a0_origins_stay_identical(self):
        for sx, sy, area_x, area_y, expected in (
                (0x0E18, 0x00A0, 0x0E00, 0x0000, 0x0502),
                (0x0088, 0x08D0, 0x0000, 0x0800, 0x0690)):
            with self.subTest(expected=expected):
                self.assertEqual(_native_tilemap_origin(sx, sy, area_x, area_y,
                                                       512, 512), expected)

    def test_native_goron_control_cache_stays_identical(self):
        self.assertEqual(_native_tilemap_origin(0x0CA8, 0x0DD8, 0x0C00,
                                               0x0C00, 1024, 1024), 0x0E94)

    def test_tall_area_keeps_its_second_half_row(self):
        origin = _native_tilemap_origin(0x0688, 0x0A10, 0x0600, 0x0800,
                                       512, 1024)
        self.assertEqual(divmod(origin, 128), (33, 16))

    def test_area_translation_does_not_move_its_buffer_origin(self):
        for width, height in ((512, 512), (1024, 512),
                              (512, 1024), (1024, 1024)):
            for dx, dy in ((0, 0), (0x200, 0), (0, 0x600), (0xA00, 0xC00)):
                with self.subTest(size=(width, height), shift=(dx, dy)):
                    self.assertEqual(
                        _native_tilemap_origin(0x288+dx, 0x210+dy,
                                               dx, dy, width, height),
                        _native_tilemap_origin(0x288, 0x210, 0, 0, width, height))


if __name__ == '__main__':
    unittest.main()
