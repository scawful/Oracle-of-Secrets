"""Independent synthetic placements expose false passes in room-wide audits."""
from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "validate_minecart_starts.py"
spec = importlib.util.spec_from_file_location("validate_minecart_starts", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


def start(room=0x88, x=0x1160, y=0x10D0):
    return {"room": room, "x": x, "y": y}


def placement(track=3, layer=0, **kwargs):
    return {**start(**kwargs), "subtype": track, "layer": layer, "record_index": 0}


class InitialPlacementTests(unittest.TestCase):
    def setUp(self):
        self.starts = [start(0, 0, 0) for _ in range(32)]
        self.starts[3] = start()
        self.stops = {0x88: {26 * 64 + 44: 0xBA}}

    def audit(self, placements, tracks=(3,)):
        return validator.check_starts(self.starts, placements, self.stops, list(tracks))

    def codes(self, result):
        return [issue["code"] for issue in result["issues"]]

    def test_matching_start_and_stop_pass(self):
        self.assertEqual(self.audit([placement()])["status"], "pass")

    def test_track3_return_stops_do_not_replace_initial_match(self):
        returns = [placement(room=0x87, x=0x0E70, y=y) for y in (0x10D0, 0x1110)]
        self.assertIn("missing_initial_placement", self.codes(self.audit(returns)))
        result = self.audit(returns + [placement()])
        self.assertEqual(result["status"], "pass")
        self.assertEqual(result["tracks"][0]["initial_match_count"], 1)
        self.assertEqual(len(result["tracks"][0]["placements"]), 3)

    def test_other_subtype_on_same_stop_is_not_a_match(self):
        self.assertIn("missing_initial_placement", self.codes(self.audit([placement(track=1)])))

    def test_same_subtype_wrong_coordinate_is_not_a_match(self):
        self.assertIn("missing_initial_placement", self.codes(self.audit([placement(y=0x10D8)])))

    def test_initial_match_without_stop_fails(self):
        self.stops[0x88] = {26 * 64 + 44: 0xB0}
        self.assertEqual(self.codes(self.audit([placement()])), ["initial_point_not_on_stop"])

    def test_duplicate_nonzero_start_tuple_fails(self):
        self.starts[1] = start()
        result = self.audit([placement(), placement(track=1)], tracks=(1, 3))
        self.assertEqual(self.codes(result), ["duplicate_start_tuple"])
        self.assertEqual(result["issues"][0]["tracks"], [1, 3])

    def test_unselected_duplicate_does_not_fail_selected_track(self):
        self.starts[1] = start()
        self.assertEqual(self.audit([placement()])["status"], "pass")

    def test_disabled_zero_rooms_are_not_duplicate_starts(self):
        result = self.audit([], tracks=(0, 1))
        self.assertEqual(result["status"], "pass")
        self.assertEqual([r["status"] for r in result["tracks"]], ["disabled", "disabled"])

    def test_multiple_same_id_initial_records_fail(self):
        self.assertIn("multiple_initial_placements", self.codes(self.audit([placement(), placement()])))

    def test_stop_is_checked_on_placement_layer(self):
        self.assertIn("initial_point_not_on_stop", self.codes(self.audit([placement(layer=1)])))
        self.stops[0x88][0x1000 + 26 * 64 + 44] = 0xBA
        self.assertEqual(self.audit([placement(layer=1)])["status"], "pass")

    def test_invalid_room_or_coordinates_do_not_wrap_into_stop(self):
        self.starts[3] = start(x=0x1360)
        self.assertIn("invalid_start_coordinates", self.codes(self.audit([])))
        self.starts[3] = start(room=0x128)
        self.assertIn("invalid_start_room", self.codes(self.audit([])))


class CompiledInputTests(unittest.TestCase):
    def fixture(self):
        data = bytearray(0x8000)
        lines = ["[labels]"]
        for i, (field, symbol) in enumerate(validator.TABLE_SYMBOLS.items()):
            offset = i * 64
            lines.append(f"00:{0x8000 + offset:04X} {symbol}")
            for track in range(32):
                value = {"room": 0x88, "x": 0x1160, "y": 0x10D0}[field]
                data[offset + track * 2:offset + track * 2 + 2] = value.to_bytes(2, "little")
        return bytes(data), "\n".join(lines)

    def test_reads_all_32_compiled_entries(self):
        starts, addresses = validator.read_start_tables(*self.fixture())
        self.assertEqual(len(starts), 32)
        self.assertEqual(starts[31], start())
        self.assertEqual(addresses["x"]["snes_address"], "0x008040")

    def test_missing_or_malformed_wla_labels_fail(self):
        data, symbols = self.fixture()
        for invalid in (symbols.replace("[labels]", "[other]"), symbols + "\nnot-a-label"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                validator.read_start_tables(data, invalid)

    def test_duplicate_label_fails(self):
        data, symbols = self.fixture()
        with self.assertRaisesRegex(ValueError, "Duplicate WLA"):
            validator.read_start_tables(data, symbols + "\n" + symbols.splitlines()[1])

    def test_truncated_rom_and_non_rom_address_fail(self):
        data, symbols = self.fixture()
        for rom, sym in ((data[:100], symbols), (data, symbols.replace("00:8000", "7E:8000")),
                         (data, symbols.replace("00:8000", "00:FFF0"))):
            with self.subTest(sym=sym), self.assertRaises(ValueError):
                validator.read_start_tables(rom, sym)

    def test_track_selection(self):
        self.assertEqual(validator.parse_tracks("0-2,0x3,3"), [0, 1, 2, 3])
        self.assertEqual(len(validator.parse_tracks("all")), 32)
        for raw in ("", "32", "4-1", "-1", "1-2-3"):
            with self.subTest(raw=raw), self.assertRaises(argparse.ArgumentTypeError):
                validator.parse_tracks(raw)


if __name__ == "__main__":
    unittest.main()
