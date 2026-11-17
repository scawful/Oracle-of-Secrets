import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from generate_room_state_table import ROOM_COUNT, build_table, render  # noqa: E402


class RoomStateTableTests(unittest.TestCase):
    def test_empty_is_all_zero(self):
        table = build_table({"schema_version": 1, "rooms": []})
        self.assertEqual(table, bytes(ROOM_COUNT))
        self.assertEqual(render(table).count("db "), ROOM_COUNT // 16 + (ROOM_COUNT % 16 > 0))

    def test_modes_and_tags(self):
        table = build_table({"schema_version": 1, "rooms": [
            {"room": "0x0CF", "mode": "code_owned"},
            {"room": 0x127, "mode": "shutters_stay_open", "clear_tags": ["AE", "AF"]},
        ]})
        self.assertEqual(table[0x0CF], 0x01)
        self.assertEqual(table[0x127], 0x32)

    def test_rejects_bad_entries(self):
        bad = [
            [{"room": "0x128", "mode": "none"}],
            [{"room": "0x10", "mode": "none"}, {"room": 16, "mode": "none"}],
            [{"room": "0x10", "mode": "sticky"}],
            [{"room": "0x10", "mode": "code_owned", "clear_tags": ["AE"]}],
            [{"room": "0x10", "mode": "shutters_stay_open", "clear_tags": ["AD"]}],
        ]
        for rooms in bad:
            with self.assertRaises(ValueError):
                build_table({"schema_version": 1, "rooms": rooms})


if __name__ == "__main__":
    unittest.main()
