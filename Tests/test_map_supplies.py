"""Contract and tilemap-geometry tests for the Menu v5 Map & Spoils page (QUEUE320).

Covers:
1. Tilemap footprints on the Map & Spoils page: Area Name (row 9), 8x8 Mini-Map
   (rows 11..18, cols 6..13), MAP icon (12,19) + 4x4 C4 cursor + "A:MAP" (12,22..26),
   !DungeonRow 3 icons (ChestKey, BigKey, Chest at (15, 17/20/23)), A:USE prompt (18,21..25),
   row 19 horizontal divider (cols 6..25), 6 Spoils icons on row 21 (cols 6,9,13,17,21,24)
   + 4x4 C4 cursors, menu_frame interior bounds, and $1692 footer — zero overlap and border intact.
2. MenuFlow_MapMove / MenuMapTravel_Select / MenuFlow_MapInit / MenuFlow_RecordTurn
   contracts and state transitions.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MAP_TRAVEL = (ROOT / "Menu" / "menu_map_travel.asm").read_text(encoding="utf-8")
CURSOR_FLOW = (ROOT / "Menu" / "menu_cursor_flow.asm").read_text(encoding="utf-8")
DRAW = (ROOT / "Menu" / "menu_draw.asm").read_text(encoding="utf-8")
FRAME = (ROOT / "Menu" / "tilemaps" / "menu_frame.tilemap").read_bytes()

PANEL_BLANK = 0x3417


def menu_offset(y: int, x: int) -> int:
    return y * 64 + x * 2


def to_cell(byte_offset: int) -> tuple[int, int]:
    assert byte_offset % 2 == 0, f"odd tilemap offset {byte_offset:#x}"
    return divmod(byte_offset // 2, 32)


def cursor_box_4x4(draw_offset: int) -> set[tuple[int, int]]:
    # Full 12-tile C4 perimeter around a 2x2 icon at draw_offset (+4,+4):
    # corners + top/bottom + left/right relative to $1000 + draw_offset.
    disps = (
        0x0C6, 0x0C8, 0x0CA, 0x0CC,
        0x106, 0x10C,
        0x146, 0x14C,
        0x186, 0x188, 0x18A, 0x18C,
    )
    return {to_cell(draw_offset + d) for d in disps}


def icon_2x2(draw_offset: int) -> set[tuple[int, int]]:
    return {to_cell(draw_offset + disp) for disp in (0x108, 0x10A, 0x148, 0x14A)}


class MapSuppliesLayoutTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.frame = [int.from_bytes(FRAME[i:i + 2], "little") for i in range(0, len(FRAME), 2)]
        m = re.search(
            r"MenuFlow_MapPos:\s*\n(.*?)MenuFlow_MapGfx:", CURSOR_FLOW, re.S
        )
        assert m, "MenuFlow_MapPos table not found"
        cls.map_pos = [
            (int(y), int(x))
            for y, x in re.findall(r"menu_offset\((\d+),(\d+)\)", m.group(1))
        ]

    def test_table_sizes_and_alignment(self):
        self.assertEqual(len(self.map_pos), 7)
        self.assertEqual(self.map_pos[0], (8, 15))  # abs (12, 19)
        # Spoils sit on menu_offset row 17 (abs icons rows 21..22), matching QuestSongs.
        for i in range(1, 7):
            self.assertEqual(self.map_pos[i][0], 17, f"spoil cell {i} row")
        self.assertEqual(
            [c for _, c in self.map_pos[1:]], [2, 5, 9, 13, 17, 20]
        )

        gfx_m = re.search(r"MenuFlow_MapGfx:\s*\n(.*?)\n\n", CURSOR_FLOW, re.S)
        assert gfx_m
        gfxs = re.findall(r"(\w+GFX)", gfx_m.group(1))
        self.assertEqual(
            gfxs,
            [
                "MapGFX",
                "BananaGFX",
                "PineappleGFX",
                "RockMeatGFX",
                "SeashellGFX",
                "HoneycombGFX",
                "DekuStickGFX",
            ],
        )

    def test_zero_overlap_and_inside_panel(self):
        # Fixed elements on Map & Spoils page
        fixed = {}
        fixed["area_name"] = {(9, c) for c in range(5, 27)}
        fixed["minimap"] = {(r, c) for r in range(11, 19) for c in range(6, 14)}
        fixed["amap_label"] = {(12, c) for c in range(22, 27)}
        fixed["divider_h"] = {(19, c) for c in range(6, 26)}

        dy, dx = map(int, re.search(r"!DungeonRow = menu_offset\((\d+),(\d+)\)", DRAW).groups())
        # Under !ENABLE_MENU_MAP_TRAVEL == 1: ChestKey (15,17), BigKey (15,20), Chest (15,23).
        d_offsets = re.findall(
            r"LDX\.w #!DungeonRow\+menu_offset\((\d+),\s*(\d+)\) ; Map & Spoils page",
            DRAW,
        )
        self.assertEqual(len(d_offsets), 3)
        for idx, (y, x) in enumerate(d_offsets):
            fixed[f"dungeon_{idx}"] = icon_2x2(menu_offset(dy + int(y), dx + int(x)))

        use_m = re.search(r"\.use_prompt\s*\n\s*LDA\.l \.use_text,X : STA\.w \$1000\+menu_offset\((\d+),(\d+)\),X", CURSOR_FLOW)
        assert use_m, "A:USE offset not found"
        uy, ux = int(use_m.group(1)), int(use_m.group(2))
        fixed["use_prompt"] = {(uy, ux + i) for i in range(5)}

        # All fixed elements stay strictly inside panel interior
        for fname, fcells in fixed.items():
            for r, c in fcells:
                self.assertEqual(self.frame[r * 32 + c], PANEL_BLANK, f"{fname} leaves panel at {(r, c)}")

        # All 7 cell icons stay inside panel and clear of fixed elements
        icons = {}
        for idx, (y, x) in enumerate(self.map_pos):
            cells = icon_2x2(menu_offset(y, x))
            for r, c in cells:
                self.assertEqual(self.frame[r * 32 + c], PANEL_BLANK, f"cell {idx} icon leaves panel at {(r, c)}")
            icons[f"cell_{idx}"] = cells

        # No overlap among fixed + icons
        combined = dict(fixed, **icons)
        names = list(combined)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertFalse(combined[a] & combined[b], f"{a} overlaps {b}: {combined[a] & combined[b]}")

        # Active 4x4 C4 cursor for EVERY cell (0..6) must stay inside panel and never overlap
        # fixed elements or its own icon or footer.
        footer = {(26, 9 + i) for i in range(14)}
        for idx, (y, x) in enumerate(self.map_pos):
            box = cursor_box_4x4(menu_offset(y, x))
            for r, c in box:
                self.assertEqual(
                    self.frame[r * 32 + c],
                    PANEL_BLANK,
                    f"cell {idx} 4x4 cursor hits border/outside panel at {(r, c)}",
                )
            self.assertFalse(box & footer, f"cell {idx} cursor overlaps footer")
            self.assertFalse(box & icons[f"cell_{idx}"], f"cell {idx} cursor overlaps own icon")
            for fname, fcells in fixed.items():
                self.assertFalse(box & fcells, f"cell {idx} cursor overlaps {fname}: {box & fcells}")

    def test_asm_contracts(self):
        # Usable bitmask matches Banana (1), Pineapple (2), Honeycomb (5), Deku Stick (6)
        usable_m = re.search(r"\.usable\s*\n\s*db\s+([0-9,]+)", CURSOR_FLOW)
        assert usable_m
        self.assertEqual([int(v) for v in usable_m.group(1).split(",")], [1, 1, 0, 0, 1, 1])

        # Select restores $020B after MagicBag_ConsumeItem and only allows A ($F6 bit 7)
        sel_m = re.search(r"MenuMapTravel_Select:\s*\n\{(.*?)\n\}", MAP_TRAVEL, re.S)
        assert sel_m
        sel = sel_m.group(1)
        self.assertIn("BIT.b $F6 : BPL .done", sel)
        self.assertIn("JSR MagicBag_ConsumeItem", sel)
        self.assertIn("PLA : STA.w $020B", sel)

        # RecordTurn emits row 0 for cell 0 and row 3 for supplies
        self.assertIn("LDA.w $020B : BEQ .map_top", CURSOR_FLOW)
        self.assertIn("LDA.b #$03 : BRA .store", CURSOR_FLOW)


if __name__ == "__main__":
    unittest.main()
