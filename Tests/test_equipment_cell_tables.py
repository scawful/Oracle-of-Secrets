"""Equipment cell order is data: these tables must agree with each other.

A reorder edits Menu_Equipment_Pos (draw position), Menu_Equipment_Columns
(cursor column), and the .next/.prev ring of Menu_Equipment_Move. Gfx and
Names stay slot-indexed. This test fails when one table is edited alone.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "Menu" / "menu_equipment.asm").read_text()
SLOTS = 27
BANDS = 5  # masks, rings, songs, supplies, GEAR


def table(label, kind):
    """Values of the db/dw lines after `label` until the next label."""
    start = SRC.index(label + "\n") + len(label) + 1
    out = []
    for line in SRC[start:].splitlines():
        line = line.split(";")[0].strip()
        if not line:
            continue
        if not line.startswith(kind + " "):
            break
        out.extend(v.strip() for v in re.split(r",(?![^(]*\))", line[len(kind) + 1:]))
    return out


def offsets(values):
    pos = []
    for v in values:
        m = re.fullmatch(r"menu_offset\((\d+),(\d+)\)", v)
        assert m, v
        pos.append((int(m.group(1)), int(m.group(2))))
    return pos


class EquipmentCellTables(unittest.TestCase):
    def setUp(self):
        self.pos = offsets(table("Menu_Equipment_Pos:", "dw"))
        self.rows = [int(v) for v in table("Menu_Equipment_Rows:", "db")]
        self.cols = [int(v) for v in table("Menu_Equipment_Columns:", "db")]
        self.next = [int(v) for v in table(".next", "db")]
        self.prev = [int(v) for v in table(".prev", "db")]
        self.starts = [int(v) for v in table(".starts", "db")]
        self.ends = [int(v) for v in table(".ends", "db")]

    def test_lengths(self):
        for name in ("pos", "rows", "cols", "next", "prev"):
            self.assertEqual(len(getattr(self, name)), SLOTS, name)
        self.assertEqual(len(self.starts), BANDS)
        self.assertEqual(len(self.ends), BANDS)
        self.assertEqual(len(table("Menu_Equipment_Gfx:", "dw")), 24)

    def test_columns_match_draw_positions(self):
        # DrawMenuItem is relative to absolute (4,4); the cursor column is absolute.
        for slot, ((_, col), cursor_col) in enumerate(zip(self.pos, self.cols)):
            self.assertEqual(col + 4, cursor_col, f"slot {slot}")

    def test_rows_match_band_ranges(self):
        for band, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            for slot in range(lo, hi):
                self.assertEqual(self.rows[slot], band, f"slot {slot}")
        self.assertEqual(self.ends[-1], SLOTS)

    def test_next_prev_walk_columns_left_to_right(self):
        for band, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            if band == 4:
                continue  # GEAR steps slot+1 (see test_gear_row)
            band_slots = set(range(lo, hi))
            by_col = sorted(band_slots, key=lambda s: self.cols[s])
            for a, b in zip(by_col, by_col[1:]):
                self.assertEqual(self.next[a], b, f"next of slot {a}")
                self.assertEqual(self.prev[b], a, f"prev of slot {b}")
            # Edge checks in Menu_Equipment_Move compare columns 7 and $17.
            self.assertEqual(self.cols[by_col[0]], 7, f"band {band} first column")
            self.assertEqual(self.cols[by_col[-1]], 0x17, f"band {band} last column")

    def test_gear_row(self):
        lo, hi = self.starts[4], self.ends[4]
        gear = list(range(lo, hi))
        self.assertEqual(gear, [24, 25, 26])
        # Right moves INX until slot $1A; left uses .prev and the column-7 edge.
        self.assertEqual([self.cols[s] for s in gear], sorted(self.cols[s] for s in gear))
        self.assertEqual(self.cols[gear[0]], 7)
        self.assertIn("CPX.b #$1A : BEQ .turn", SRC)
        for a, b in zip(gear, gear[1:]):
            self.assertEqual(self.prev[b], a)


if __name__ == "__main__":
    unittest.main()
