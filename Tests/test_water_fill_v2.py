"""Water-fill format boundaries and saved editor-zone Build preservation."""

import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "generate_water_fill_table", ROOT / "Scripts/Generate/generate_water_fill_table.py"
)
water = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(water)


class WaterFillV2Test(unittest.TestCase):
    def test_full_pools_fit_word_counts(self):
        zones = {0x25: list(range(594)), 0x27: list(range(296))}
        offsets = water.build_layout(zones, {0x25: 2, 0x27: 1}, 2)
        self.assertEqual(offsets, {0x25: 9, 0x27: 1199})
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "table.asm"
            water.write_asm(path, Path("fixture.sfc"), 0xF5, zones,
                            {0x25: 2, 0x27: 1}, offsets, 2)
            text = path.read_text()
        self.assertIn("db $82", text)
        self.assertIn("dw $0252 ; mask=$02", text)
        self.assertIn("dw $0128 ; mask=$01", text)
        self.assertIn("assert !ENABLE_WATER_FILL_V2 == 1", text)

    def test_legacy_layout_stays_byte_counted(self):
        self.assertEqual(water.build_layout({0x25: [0, 4095]}, {0x25: 2}),
                         {0x25: 5})
        with self.assertRaisesRegex(ValueError, "format v1 max"):
            water.build_layout({0x25: list(range(256))}, {0x25: 2})

    def test_v2_keeps_region_and_grid_bounds(self):
        with self.assertRaisesRegex(ValueError, "reserved bank"):
            water.build_layout({0x25: list(range(4096))}, {0x25: 2}, 2)
        with self.assertRaisesRegex(ValueError, "collision bounds"):
            water.build_layout({0x25: [4096]}, {0x25: 2}, 2)

    def make_saved_table(self, count=594):
        data = bytearray(0x200000)
        start = 0x12E000
        data[start:start + 5] = bytes([0x81, 0x25, 2, 5, 0])
        struct.pack_into("<H", data, start + 5, count)
        for i in range(count):
            struct.pack_into("<H", data, start + 7 + 2 * i, i)
        return data

    def test_saved_editor_zones_survive_generation_without_markers(self):
        data = self.make_saved_table()
        self.assertEqual(water.collect_marker_offsets(data, 255, 0xF5), {})
        zones, masks = water.read_saved_v2_table(data)
        self.assertEqual(zones, {0x25: list(range(594))})
        self.assertEqual(masks, {0x25: 2})
        self.assertEqual(water.build_layout(zones, masks, 2), {0x25: 5})

    def test_normal_generator_preserves_saved_editor_table(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "saved.sfc"
            output = Path(tmp) / "water.asm"
            rom.write_bytes(self.make_saved_table())
            with patch("sys.argv", ["generate_water_fill_table.py", "--rom", str(rom),
                                    "--out-asm", str(output), "--format-version", "2"]):
                self.assertEqual(water.main(), 0)
            text = output.read_text()
        self.assertIn("db $81", text)
        self.assertIn("dw $0252 ; mask=$02", text)

    def test_legacy_generator_refuses_to_downgrade_saved_v2(self):
        with tempfile.TemporaryDirectory() as tmp:
            rom = Path(tmp) / "saved.sfc"
            output = Path(tmp) / "water.asm"
            rom.write_bytes(self.make_saved_table())
            with patch("sys.argv", ["generate_water_fill_table.py", "--rom", str(rom),
                                    "--out-asm", str(output)]):
                with self.assertRaisesRegex(ValueError, "ENABLE_WATER_FILL_V2"):
                    water.main()
            self.assertFalse(output.exists())

    def test_saved_empty_differs_from_no_editor_table(self):
        data = bytearray(0x200000)
        self.assertIsNone(water.read_saved_v2_table(data))
        data[0x12E000] = 0x80
        self.assertEqual(water.read_saved_v2_table(data), ({}, {}))

    def test_saved_omission_and_empty_set_do_not_regenerate_marker_room(self):
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as tmp:
                data = self.make_saved_table()
                # A real custom-collision stream still authors room $27's F5
                # marker, but the saved v2 set omits that room.
                entry = 0x128090 + 0x27 * 3
                data[entry:entry + 3] = bytes([0x50, 0x84, 0x25])
                data[0x128450:0x128459] = bytes(
                    [0, 0, 1, 1, 0xF5, 0xF0, 0xF0, 0xFF, 0xFF])
                self.assertEqual(water.collect_marker_offsets(data, 255, 0xF5),
                                 {0x27: [0]})
                if empty:
                    data[0x12E000:0x130000] = bytes([0x80]) + bytes(0x1FFF)
                rom, output = Path(tmp) / "saved.sfc", Path(tmp) / "water.asm"
                rom.write_bytes(data)
                with patch("sys.argv", ["generate_water_fill_table.py", "--rom", str(rom),
                                        "--out-asm", str(output), "--format-version", "2"]):
                    self.assertEqual(water.main(), 0)
                text = output.read_text()
                self.assertNotIn("WaterFillData_Room27", text)
                if empty:
                    self.assertIn("db $80", text)
                    self.assertNotIn("WaterFillData_Room25", text)
                else:
                    self.assertIn("WaterFillData_Room25", text)

    def test_saved_bad_word_count_refuses(self):
        data = self.make_saved_table()
        struct.pack_into("<H", data, 0x12E005, 0xFFFF)
        with self.assertRaisesRegex(ValueError, "grid or reserved"):
            water.read_saved_v2_table(data)

    def test_saved_count_cannot_cross_region_end(self):
        data = self.make_saved_table()
        struct.pack_into("<H", data, 0x12E003, 0x1FFF)
        with self.assertRaisesRegex(ValueError, "region end"):
            water.read_saved_v2_table(data)


if __name__ == "__main__":
    unittest.main()
