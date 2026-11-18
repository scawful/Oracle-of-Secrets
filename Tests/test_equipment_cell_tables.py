"""Equipment cell order is data: these tables must agree with each other.

A reorder edits Menu_Equipment_Pos (draw position) and Menu_Equipment_Columns
(cursor column). Horizontal moves step slot+-1 inside a band (.starts/.ends),
so each band's slots must run left to right. Gfx and Names stay slot-indexed.
This test fails when one table is edited alone.
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "Menu" / "menu_equipment.asm").read_text()
SLOTS = 29
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
        self.starts = [int(v) for v in table(".starts", "db")]
        self.ends = [int(v) for v in table(".ends", "db")]

    def test_lengths(self):
        for name in ("pos", "rows", "cols"):
            self.assertEqual(len(getattr(self, name)), SLOTS, name)
        self.assertEqual(len(self.starts), BANDS)
        self.assertEqual(len(self.ends), BANDS)
        self.assertEqual(len(table("Menu_Equipment_Gfx:", "dw")), SLOTS)

    def test_columns_match_draw_positions(self):
        # DrawMenuItem is relative to absolute (4,4); the cursor column is absolute.
        for slot, ((_, col), cursor_col) in enumerate(zip(self.pos, self.cols)):
            self.assertEqual(col + 4, cursor_col, f"slot {slot}")

    def test_rows_match_band_ranges(self):
        for band, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            for slot in range(lo, hi):
                self.assertEqual(self.rows[slot], band, f"slot {slot}")
        self.assertEqual(self.ends[-1], SLOTS)

    def test_bands_run_left_to_right(self):
        # Menu_Equipment_Move steps slot+-1 and turns the page at .starts/.ends.
        self.assertIn("CMP.w .ends,X : BCS .turn", SRC)
        self.assertIn("CMP.w .starts,X : BEQ .turn", SRC)
        for band, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            cols = [self.cols[s] for s in range(lo, hi)]
            self.assertEqual(cols, sorted(set(cols)), f"band {band}")
            rows = {self.pos[s][0] for s in range(lo, hi)}
            self.assertEqual(len(rows), 1, f"band {band} on one tile row")

    def test_gear_row(self):
        lo, hi = self.starts[4], self.ends[4]
        gear = list(range(lo, hi))
        self.assertEqual(gear, [24, 25, 26, 27, 28])  # story, heavy, green/blue/red tunic
        self.assertEqual([self.cols[s] for s in gear], [6, 10, 15, 19, 23])

    def test_cursor_boxes_fit_between_rows(self):
        # The full cursor uses the tile row above and below each icon (2x2):
        # visible bands (GEAR, masks, rings) need two empty rows between icons.
        visible = [self.pos[s][0] for s in (24, 0, 6)]
        self.assertEqual(visible, sorted(visible))
        for a, b in zip(visible, visible[1:]):
            self.assertGreaterEqual(b - a, 4)
        self.assertGreaterEqual(visible[0], 4)  # title row 2 (menu_offset) stays clear


if __name__ == "__main__":
    unittest.main()
