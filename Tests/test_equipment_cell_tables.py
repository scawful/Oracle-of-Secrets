"""Equipment cell order is data (Menu v5 E2 layout): these tables must agree.

E2 places 3 visual rows inside the unchanged menu_frame interior:
  Row 0 (Gear, row 10):       Story(24), Heavy(25) | Green(26), Blue(27), Red(28)
  Row 1 (Mid,  row 15):       Deku(0), Zora(1), Wolf(2) | Power(6), Armor(7), Heart(8)
  Row 2 (Bot,  row 19):       Bunny(3), Stone(4), Garo(5) | Light(9), Blast(10), Steadfast(11)
Horizontal moves step through Menu_Equipment_VisualOrder inside each visual row
(.starts/.ends) and turn the page at the row edge. Gfx, Pos, Columns, Rows, and
Names stay slot-indexed (0..28).
"""
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = (ROOT / "Menu" / "menu_equipment.asm").read_text()
SLOTS = 29
VISUAL_ROWS = 3


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
        self.vorder = [int(v) for v in table("Menu_Equipment_VisualOrder:", "db")]
        self.starts = [int(v) for v in table(".starts", "db")]
        self.ends = [int(v) for v in table(".ends", "db")]

    def test_lengths(self):
        for name in ("pos", "rows", "cols"):
            self.assertEqual(len(getattr(self, name)), SLOTS, name)
        self.assertEqual(len(self.starts), VISUAL_ROWS)
        self.assertEqual(len(self.ends), VISUAL_ROWS)
        self.assertEqual(len(self.vorder), 17)
        self.assertEqual(self.ends[-1], len(self.vorder))
        self.assertEqual(len(table("Menu_Equipment_Gfx:", "dw")), SLOTS)

    def test_columns_match_draw_positions(self):
        # DrawMenuItem is relative to absolute (4,4); the cursor column is absolute.
        for slot, ((_, col), cursor_col) in enumerate(zip(self.pos, self.cols)):
            self.assertEqual(col + 4, cursor_col, f"slot {slot}")

    def test_rows_match_visual_order_ranges(self):
        seen = set()
        for vrow, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            for idx in range(lo, hi):
                slot = self.vorder[idx]
                self.assertNotIn(slot, seen, f"duplicate slot {slot} in VisualOrder")
                seen.add(slot)
                self.assertEqual(self.rows[slot], vrow, f"slot {slot}")
        # All 6 masks (0..5), all 6 rings (6..11), and all 5 gear slots (24..28) are navigable.
        self.assertEqual(seen, set(range(0, 12)) | set(range(24, 29)))

    def test_visual_rows_run_left_to_right(self):
        self.assertIn("INY : CPY.b $09 : BCS .turn", SRC)
        self.assertIn("TYA : CMP.w .starts,X : BEQ .turn", SRC)
        for vrow, (lo, hi) in enumerate(zip(self.starts, self.ends)):
            slots = self.vorder[lo:hi]
            cols = [self.cols[s] for s in slots]
            self.assertEqual(cols, sorted(set(cols)), f"visual row {vrow}")
            rows = {self.pos[s][0] for s in slots}
            self.assertEqual(len(rows), 1, f"visual row {vrow} on one tile row")

    def test_e2_gear_masks_and_rings_coordinates(self):
        # Row 0 Gear: Story(24)@(10,7), Heavy(25)@(10,11) | Green(26)@(10,17), Blue(27)@(10,20), Red(28)@(10,23)
        gear = self.vorder[self.starts[0]:self.ends[0]]
        self.assertEqual(gear, [24, 25, 26, 27, 28])
        self.assertEqual([(self.pos[s][0] + 4, self.cols[s]) for s in gear],
                         [(10, 7), (10, 11), (10, 17), (10, 20), (10, 23)])
        # Row 1 Mid: 3 Masks (6,9,12) | 3 Rings (18,21,24) at abs row 15
        mid = self.vorder[self.starts[1]:self.ends[1]]
        self.assertEqual(mid, [0, 1, 2, 6, 7, 8])
        self.assertEqual([(self.pos[s][0] + 4, self.cols[s]) for s in mid],
                         [(15, 6), (15, 9), (15, 12), (15, 18), (15, 21), (15, 24)])
        # Row 2 Bot: 3 Masks (6,9,12) | 3 Rings (18,21,24) at abs row 19
        bot = self.vorder[self.starts[2]:self.ends[2]]
        self.assertEqual(bot, [3, 4, 5, 9, 10, 11])
        self.assertEqual([(self.pos[s][0] + 4, self.cols[s]) for s in bot],
                         [(19, 6), (19, 9), (19, 12), (19, 18), (19, 21), (19, 24)])

    def test_cursor_boxes_fit_between_rows_and_clear_dividers(self):
        # Absolute icon rows: 10 (box 9..12), 15 (box 14..17), 19 (box 18..21).
        # Row 13 is the horizontal wood divider; internal vertical divider removed in polish pass.
        self.assertIn("LDA.w #$217A", SRC)
        self.assertNotIn("LDA.w #$214F", SRC)
        row_ys = [self.pos[self.vorder[lo]][0] + 4 for lo in self.starts]
        self.assertEqual(row_ys, [10, 15, 19])
        for slot in self.vorder:
            r = self.pos[slot][0] + 4
            c = self.cols[slot]
            box_rows = range(r - 1, r + 3)
            box_cols = range(c - 1, c + 3)
            self.assertNotIn(13, box_rows, f"slot {slot} cursor hits row 13 divider")
            self.assertNotIn(15, box_cols, f"slot {slot} cursor crosses center gutter col 15")
            self.assertGreaterEqual(min(box_rows), 9)
            self.assertLessEqual(max(box_rows), 22)
            self.assertGreaterEqual(min(box_cols), 5)
            self.assertLessEqual(max(box_cols), 26)


if __name__ == "__main__":
    unittest.main()
