"""Contract and tilemap-geometry tests for the Menu v5 Map & Spoils page (QUEUE320 polish).

Covers:
1. Tilemap footprints on the Map & Spoils page: 8x8 Mini-Map (rows 11..18, cols 6..13),
   2-line word-wrapped Area Name (rows 11..12, cols 15..26), MAP icon (15,15) + hoverable
   Dungeon icons (ChestKey 15,18; BigKey 15,21; Treasure 15,24), zero static A:MAP / A:USE,
   row 19 horizontal wood divider (cols 6..25), 6 Spoils icons on row 21 (cols 6,9,13,17,21,24),
   4x4 C4 cursors across all 10 cells, menu_frame interior bounds, and $1692 footer.
2. MenuMap_Move_Long 2D navigation (top row skipping unowned dungeon icons + bottom row),
   X-button Map shortcut anywhere on Map & Spoils, Spoils Detail/Use Popup contracts.
"""

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MENU = (ROOT / "Menu" / "menu.asm").read_text(encoding="utf-8")
MAP_TRAVEL = (ROOT / "Menu" / "menu_map_travel.asm").read_text(encoding="utf-8")
CURSOR_FLOW = (ROOT / "Menu" / "menu_cursor_flow.asm").read_text(encoding="utf-8")
V5_EXT = (ROOT / "Menu" / "menu_v5_ext.asm").read_text(encoding="utf-8")
DRAW = (ROOT / "Menu" / "menu_draw.asm").read_text(encoding="utf-8")
FRAME = (ROOT / "Menu" / "tilemaps" / "menu_frame.tilemap").read_bytes()

PANEL_BLANK = 0x3417


def menu_offset(y: int, x: int) -> int:
    return y * 64 + x * 2


def to_cell(byte_offset: int) -> tuple[int, int]:
    assert byte_offset % 2 == 0, f"odd tilemap offset {byte_offset:#x}"
    return divmod(byte_offset // 2, 32)


def cursor_box_4x4(draw_offset: int) -> set[tuple[int, int]]:
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
        # 10 hoverable cells: 0=Map, 1..6=Spoils, 7=ChestKey, 8=BigKey, 9=Treasure
        self.assertEqual(len(self.map_pos), 10)
        self.assertEqual(self.map_pos[0], (11, 11))   # abs (15, 15)
        self.assertEqual(self.map_pos[7], (11, 14))   # abs (15, 18)
        self.assertEqual(self.map_pos[8], (11, 17))   # abs (15, 21)
        self.assertEqual(self.map_pos[9], (11, 20))   # abs (15, 24)
        for i in range(1, 7):
            self.assertEqual(self.map_pos[i][0], 17, f"spoil cell {i} row")
        self.assertEqual(
            [c for _, c in self.map_pos[1:7]], [2, 5, 9, 13, 17, 20]
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

    def test_zero_overlap_no_static_prompts_and_inside_panel(self):
        # Static A:MAP and A:USE prompts are completely gone from Map & Spoils.
        self.assertNotIn('dw "A:MAP"', CURSOR_FLOW)
        self.assertNotIn('dw "A:USE"', CURSOR_FLOW)
        self.assertNotIn('dw "A:MAP"', V5_EXT)
        self.assertNotIn('dw "A:USE"', V5_EXT)

        fixed = {
            "area_name": {(r, c) for r in (11, 12) for c in range(15, 27)},
            "minimap": {(r, c) for r in range(11, 19) for c in range(6, 14)},
            "divider_h": {(19, c) for c in range(6, 26)},
        }

        dy, dx = map(int, re.search(r"!DungeonRow = menu_offset\((\d+),(\d+)\)", DRAW).groups())
        d_offsets = re.findall(
            r"LDX\.w #!DungeonRow\+menu_offset\((\d+),\s*(\d+)\) ; Map & Spoils page",
            DRAW,
        )
        self.assertEqual(len(d_offsets), 3)
        d_abs = sorted((dy + int(y), dx + int(x)) for y, x in d_offsets)
        self.assertEqual(d_abs, [self.map_pos[7], self.map_pos[8], self.map_pos[9]])

        # All fixed elements stay strictly inside panel interior.
        for fname, fcells in fixed.items():
            for r, c in fcells:
                self.assertEqual(self.frame[r * 32 + c], PANEL_BLANK, f"{fname} leaves panel at {(r, c)}")

        # All 10 icon cells stay inside panel and clear of fixed elements & each other.
        icons = {}
        for idx, (y, x) in enumerate(self.map_pos):
            cells = icon_2x2(menu_offset(y, x))
            for r, c in cells:
                self.assertEqual(self.frame[r * 32 + c], PANEL_BLANK, f"cell {idx} icon leaves panel at {(r, c)}")
            icons[f"cell_{idx}"] = cells

        combined = dict(fixed, **icons)
        names = list(combined)
        for i, a in enumerate(names):
            for b in names[i + 1:]:
                self.assertFalse(combined[a] & combined[b], f"{a} overlaps {b}: {combined[a] & combined[b]}")

        # Active 4x4 C4 cursor for EVERY cell (0..9) must stay inside panel, clear fixed elements,
        # clear footer, and never overwrite any cell's 2x2 icon!
        footer = {(26, 9 + i) for i in range(14)}
        all_icons = set().union(*icons.values())
        for idx, (y, x) in enumerate(self.map_pos):
            box = cursor_box_4x4(menu_offset(y, x))
            for r, c in box:
                self.assertEqual(
                    self.frame[r * 32 + c],
                    PANEL_BLANK,
                    f"cell {idx} 4x4 cursor hits border/outside panel at {(r, c)}",
                )
            self.assertFalse(box & footer, f"cell {idx} cursor overlaps footer")
            self.assertFalse(box & all_icons, f"cell {idx} cursor overlaps an icon: {box & all_icons}")
            for fname, fcells in fixed.items():
                self.assertFalse(box & fcells, f"cell {idx} cursor overlaps {fname}: {box & fcells}")

    def test_asm_contracts_x_shortcut_hover_footers_and_spoil_popup(self):
        # Usable bitmask matches Banana (0), Pineapple (1), Honeycomb (4), Deku Stick (5).
        usable_m = re.search(r"MenuSpoil_IsUsable_Long:.*?\.usable\s*\n\s*db\s+([0-9,\s]+)", V5_EXT, re.S)
        assert usable_m
        self.assertEqual([int(v.strip()) for v in usable_m.group(1).split(",")], [1, 1, 0, 0, 1, 1])

        # X shortcut anywhere on Map & Spoils routes through MenuMapTravel_CanMap.
        scr_m = re.search(r"MenuMapTravel_Screen:\s*\n\{(.*?)\n\}", MAP_TRAVEL, re.S)
        assert scr_m
        scr = scr_m.group(1)
        self.assertIn("LDA.b $F6 : BIT.b #$40 : BEQ .no_x_map", scr)
        self.assertIn("JSR MenuMapTravel_CanMap : BCC .x_map_err", scr)

        # Select opens !MENU_STATE_SPOIL_POPUP on owned spoil (A only, Y never acts).
        sel_m = re.search(r"MenuMapTravel_Select:\s*\n\{(.*?)\n\}", MAP_TRAVEL, re.S)
        assert sel_m
        sel = sel_m.group(1)
        self.assertIn("BIT.b $F6 : BPL .done", sel)
        self.assertIn("LDA.b #!MENU_STATE_SPOIL_POPUP : STA.w $0200", sel)
        self.assertIn("JSL MenuSpoil_DrawPopup_Long", sel)

        # Menu_SpoilPopup calls MagicBag_ConsumeItem and restores $020B, supporting B cancel & Start close.
        pop_m = re.search(r"Menu_SpoilPopup:\s*\n\{(.*?)\n\}", MENU, re.S)
        assert pop_m
        pop = pop_m.group(1)
        self.assertIn("JSL MenuSpoil_IsUsable_Long : BCC .stay", pop)
        self.assertIn("JSR MagicBag_ConsumeItem", pop)
        self.assertIn("PLA : STA.w $020B", pop)
        self.assertIn("LDA.b #!MENU_STATE_STATS_SCREEN : STA.w $0200", pop)

        # Footer labels for Map + Dungeon icons are all 14 tiles wide.
        for lbl in ("__WORLD_MAP___", "_DUNGEON_MAP__", "__CHEST_KEY___", "___BOSS_KEY___", "___TREASURE___"):
            self.assertEqual(len(lbl), 14)
            self.assertIn(f'dw "{lbl}"', V5_EXT)

        # RecordTurn treats 0 and 7..9 as top row (ordinal 0), 1..6 as bottom row (ordinal 3).
        self.assertIn("CMP.b #$07 : BCS .map_top", CURSOR_FLOW)
        self.assertIn("LDA.b #$03 : BRA .store", CURSOR_FLOW)

    def test_2d_navigation_model(self):
        """Model MenuMap_Move_Long 2D navigation for outdoors and dungeon subsets."""
        top_cells = [0, 7, 8, 9]
        top_cols = [15, 18, 21, 24]
        bot_cols = [6, 9, 13, 17, 21, 24]

        def step(cur: int, direction: str, owned_dng: set[int]):
            owned = {0, 1, 2, 3, 4, 5, 6} | owned_dng
            if direction in ("U", "D"):
                if cur == 0:
                    return 3, None
                if cur >= 7:
                    return cur - 3, None
                src = bot_cols[cur - 1]
                best_d, best_c = 255, 0
                for tc, col in zip(top_cells, top_cols):
                    if tc in owned:
                        d = abs(col - src)
                        if d < best_d:
                            best_d, best_c = d, tc
                return best_c, None
            if 1 <= cur <= 6:
                if direction == "R":
                    return (cur, "R") if cur == 6 else (cur + 1, None)
                return (cur, "L") if cur == 1 else (cur - 1, None)
            idx = 0 if cur == 0 else cur - 6
            delta = 1 if direction == "R" else -1
            while True:
                idx += delta
                if idx < 0:
                    return cur, "L"
                if idx >= 4:
                    return cur, "R"
                if top_cells[idx] in owned:
                    return top_cells[idx], None

        # Outdoors: no dungeon icons owned -> Map L/R turns pages, Down->3, any spoil Up->0.
        self.assertEqual(step(0, "R", set()), (0, "R"))
        self.assertEqual(step(0, "L", set()), (0, "L"))
        self.assertEqual(step(0, "D", set()), (3, None))
        for s in range(1, 7):
            self.assertEqual(step(s, "U", set()), (0, None))

        # Indoors with ChestKey (7) + Treasure (9) only (BigKey 8 skipped cleanly!):
        self.assertEqual(step(0, "R", {7, 9}), (7, None))
        self.assertEqual(step(7, "R", {7, 9}), (9, None))
        self.assertEqual(step(9, "R", {7, 9}), (9, "R"))
        self.assertEqual(step(9, "L", {7, 9}), (7, None))
        self.assertEqual(step(7, "L", {7, 9}), (0, None))
        self.assertEqual(step(0, "L", {7, 9}), (0, "L"))
        self.assertEqual(step(7, "D", {7, 9}), (4, None))
        self.assertEqual(step(9, "D", {7, 9}), (6, None))
        self.assertEqual(step(5, "U", {7, 9}), (7, None))  # col 21: |18-21|=3 vs |24-21|=3, tie favors left
        self.assertEqual(step(6, "U", {7, 9}), (9, None))

        # Indoors with all 3 dungeon icons owned:
        self.assertEqual(step(4, "U", {7, 8, 9}), (7, None))
        self.assertEqual(step(5, "U", {7, 8, 9}), (8, None))
        self.assertEqual(step(6, "U", {7, 8, 9}), (9, None))
        self.assertEqual(step(8, "D", {7, 8, 9}), (5, None))


if __name__ == "__main__":
    unittest.main()
