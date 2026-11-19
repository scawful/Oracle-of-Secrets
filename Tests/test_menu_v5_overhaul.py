"""QUEUE320 Menu v5 UX & Layout Overhaul contract and simulation tests.

Verifies:
1. Items Page Option A 4x6 grid, logical ID preservation, col 21 wood divider,
   zero overlap with menu_frame borders, static button prompt removal.
2. Gust Jar (S1/P1), Blue Hookshot (H3), Brown/Tan Fishing Rod (F2) Menu & HUD
   icon word parity, clean SwordGFX without level digits, HUD X|Y wood divider,
   and in-game Fishing Rod 4bpp brown/tan sprite + Bank 0D OAM palette hook.
3. Cursor C4 layering & full-size 4x4 Quest Songs cursor.
4. X-button HUD icon cache invalidation (RebuildHUD, X-item upgrade, Epona mount/dismount).
5. Heavy Sword label (BROKEN BLADE / GORONBLADE) & Select Context Help Popup.
6. Special Overworld $80-$BF area names & 8x8 Mini-Map terrain tables.
"""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
MENU = (ROOT / "Menu" / "menu.asm").read_text(encoding="utf-8")
DRAW = (ROOT / "Menu" / "menu_draw.asm").read_text(encoding="utf-8")
SELECT = (ROOT / "Menu" / "menu_select_item.asm").read_text(encoding="utf-8")
TEXT = (ROOT / "Menu" / "menu_text.asm").read_text(encoding="utf-8")
GFX = (ROOT / "Menu" / "menu_gfx_table.asm").read_text(encoding="utf-8")
HUD = (ROOT / "Menu" / "menu_hud.asm").read_text(encoding="utf-8")
HUD_CACHE = (ROOT / "Menu" / "menu_hud_cache.asm").read_text(encoding="utf-8")
HUD_CODEX = (ROOT / "Menu" / "menu_hud_codex.asm").read_text(encoding="utf-8")
BINDINGS = (ROOT / "Menu" / "menu_item_bindings.asm").read_text(encoding="utf-8")
V5_EXT = (ROOT / "Menu" / "menu_v5_ext.asm").read_text(encoding="utf-8")
CURSOR_FLOW = (ROOT / "Menu" / "menu_cursor_flow.asm").read_text(encoding="utf-8")
SWORDS = (ROOT / "Menu" / "menu_sword_slots.asm").read_text(encoding="utf-8")
PAGE3 = (ROOT / "Menu" / "menu_page3.asm").read_text(encoding="utf-8")
MAP_TRAVEL = (ROOT / "Menu" / "menu_map_travel.asm").read_text(encoding="utf-8")
FISHING_ASM = (ROOT / "Items" / "fishing_rod.asm").read_text(encoding="utf-8")
FISHING_BIN = (ROOT / "Items" / "gfx" / "fishingrod.bin").read_bytes()
FRAME = (ROOT / "Menu" / "tilemaps" / "menu_frame.tilemap").read_bytes()

PANEL_BLANK = 0x3417


class MenuV5OverhaulTest(unittest.TestCase):
    def test_items_page_option_a_grid_and_logical_ids_preserved(self):
        # Exact Option A 4x6 grid (Gust Jar $1D at Row 3 Col 5, Portal Rod $19 at Row 4 Col 5)
        m = re.search(r"Menu_CustomGridItems:\s*\n((?:\s*db [^\n]+\n)+)", SELECT)
        self.assertIsNotNone(m)
        grid = [int(x.lstrip("$"), 16) for x in re.findall(r"\$[0-9A-Fa-f]{2}", m.group(1))]
        expected = [
            0x01, 0x02, 0x03, 0x04, 0x1C, 0x06,
            0x07, 0x05, 0x09, 0x0A, 0x1A, 0x0C,
            0x08, 0x0E, 0x0F, 0x1B, 0x1D, 0x12,
            0x0D, 0x11, 0x0B, 0x10, 0x19, 0x18,
        ]
        self.assertEqual(grid, expected)

        # Parse Menu_ItemCursorPositions (30 entries for logical IDs $01..$1E)
        cm = re.search(r"Menu_ItemCursorPositions:\s*\n(.*?)Menu_ItemCursorPositions_End:", SELECT, re.S)
        self.assertIsNotNone(cm)
        pos_offsets: list[int] = []
        for raw in cm.group(1).splitlines():
            code = raw.split(";", 1)[0].strip()
            if not code.startswith("dw "):
                continue
            expr = code[3:].strip()
            mo = re.fullmatch(r"menu_offset\((\d+),(\d+)\)", expr)
            if mo:
                pos_offsets.append(int(mo.group(1)) * 64 + int(mo.group(2)) * 2)
            else:
                ar = re.fullmatch(r"\((\d+)\*64\)\+\((\d+)\*2\)", expr)
                self.assertIsNotNone(ar, f"Unexpected cursor expression: {expr}")
                pos_offsets.append(int(ar.group(1)) * 64 + int(ar.group(2)) * 2)
        self.assertEqual(len(pos_offsets), 30)

        # Verify every active grid cell maps to exact Option A (rows [11,14,17,20], cols [6,9,12,15,18,24])
        # and that its 4x4 C4 cursor stays strictly inside panel and never touches col 21 divider.
        frame = [int.from_bytes(FRAME[i:i + 2], "little") for i in range(0, len(FRAME), 2)]
        divider_cells = {(r, 21) for r in range(11, 23)}
        expected_rows = [11, 14, 17, 20]
        expected_cols = [6, 9, 12, 15, 18, 24]
        for idx, item_id in enumerate(expected):
            r_idx, c_idx = divmod(idx, 6)
            off = pos_offsets[item_id - 1]
            # Cursor TL = $1108 + off => abs (r - 1, c - 1)
            tl_r, tl_c = divmod((0x108 + off) // 2, 32)
            self.assertEqual((tl_r + 1, tl_c + 1), (expected_rows[r_idx], expected_cols[c_idx]),
                             f"Logical ID ${item_id:02X} cursor mismatch")
            box = {(tl_r + dr, tl_c + dc) for dr in range(4) for dc in range(4)}
            self.assertFalse(box & divider_cells, f"Logical ID ${item_id:02X} cursor hits col 21 divider")
            for br, bc in box:
                self.assertEqual(frame[br * 32 + bc], PANEL_BLANK, f"Logical ID ${item_id:02X} leaves panel at {(br, bc)}")

        # Gust Jar label + SwitchHook alias preserved; static button prompt removed
        self.assertIn("Menu_GustJarLabel:\nMenu_SwitchHookLabel:\n  dw \"___GUST_JAR___\"", TEXT)
        self.assertNotIn("JSR Menu_DrawButtonPrompt", MENU)
        self.assertIn("JSR Menu_DrawItemsDivider", MENU)

    def test_icons_recolors_sword_digits_and_hud_divider(self):
        # Gust Jar S1/P1
        self.assertIn("GustJarGFX:\nSwitchHookGFX:\n  dw $28F2,$2930,$357E,$357F", GFX)
        self.assertIn("dw $28F2,$2930,$357E,$357F ; Gust Jar (S1/P1)", HUD)
        # Hookshot H3 blue/white (Goldstar untouched)
        self.assertIn("dw $2CF5, $2CF6, $2CC0, $2CF5 ; Hookshot", GFX)
        self.assertIn("dw $2C17, $3531, $2D40, $3541 ; Ball & Chain", GFX)
        self.assertIn("dw $2CF5, $2CF6, $2CC0, $2CF5 ; Hookshot", HUD)
        # Fishing Rod F2 brown/tan (Portal Rod untouched)
        self.assertIn("dw $2082, $2883, $208B, $288C ; Fishing Rod", GFX)
        self.assertIn("dw $2082, $2883, $208B, $288C ; Fishing Rod", HUD)
        self.assertIn("dw $2CF0, $24F1, $30EC, $E4F0 ; Portal Rod", HUD)
        # SwordGFX level digits removed
        for old_digit in ("$2D26", "$2D48", "$2D39"):
            self.assertNotIn(old_digit, GFX)
        self.assertEqual(GFX.count("$EC8A"), 3)
        # HUD X|Y brown wood divider at col 26 rows 1-2
        self.assertIn("dw $201B, $344B, $344B, $344B, $344B, $20DE, $20AA, $20AA, $214F, $20AA, $20AA, $20DF", HUD)
        self.assertIn("dw $A00B, $A00C, $A00C, $A00C, $A00C, $20EE, $20AA, $20AA, $214F, $20AA, $20AA, $20EF", HUD)

    def test_ingame_fishing_rod_sprite_brown_wood_and_oam_hook(self):
        # Check Bank 0D hook in Items/fishing_rod.asm
        self.assertIn("org $0DA6AA ; @hook module=Items name=FishingRod_WeaponOamPalette", FISHING_ASM)
        self.assertIn("LDA.l $7F5BA2 : BNE .fishing", FISHING_ASM)
        self.assertIn("LDA.b #$04 : STA.b $0F", FISHING_ASM)  # Byrna/Portal stays blue pal 2
        self.assertIn("LDA.b #$0E : STA.b $0F", FISHING_ASM)  # Fishing rod uses Link pal 7 (brown/tan)
        # Check 4bpp pixel indices in Items/gfx/fishingrod.bin: {0, 5 outline, 6 tan, 14 brown wood}
        self.assertEqual(len(FISHING_BIN), 448)
        used = set()
        for ti in range(len(FISHING_BIN) // 32):
            tile = FISHING_BIN[ti * 32:(ti + 1) * 32]
            for y in range(8):
                p0, p1 = tile[y * 2], tile[y * 2 + 1]
                p2, p3 = tile[16 + y * 2], tile[16 + y * 2 + 1]
                for x in range(8):
                    c = (((p0 >> (7 - x)) & 1) | (((p1 >> (7 - x)) & 1) << 1)
                         | (((p2 >> (7 - x)) & 1) << 2) | (((p3 >> (7 - x)) & 1) << 3))
                    used.add(c)
        self.assertEqual(used, {0, 5, 6, 14})

    def test_hud_x_cache_invalidation_and_epona_mounted_bow(self):
        # HudCache guards: RebuildHUD tile0 check, ownership/level byte, follower, gameplay $16 upload
        self.assertIn("HudCache_CodexTile0 = $7EC9D3", HUD_CACHE)
        self.assertIn("HudCache_CodexOwn   = $7EC9D5", HUD_CACHE)
        self.assertIn("HudCache_CodexFoll  = $7EC9D6", HUD_CACHE)
        self.assertIn("LDA.l $7EC770 : CMP.l HudCache_CodexTile0 : BNE .draw_codex_m8", HUD_CACHE)
        self.assertIn("LDA.l $7EF3CC : CMP.l HudCache_CodexFoll : BNE .draw_codex", HUD_CACHE)
        self.assertIn("LDA $01,S : CMP.l HudCache_CodexOwn : BNE .draw_codex", HUD_CACHE)
        self.assertIn("LDA.l $7EC770 : STA.l HudCache_CodexTile0", HUD_CACHE)
        self.assertIn("LDA.b $10 : CMP.b #$0E : BEQ .codex_done", HUD_CACHE)
        # HUD_CodexCells mounted horse Bow allowance (no follower)
        self.assertIn("CMP.w #$0009 : BNE .empty", HUD_CODEX)
        self.assertIn("LDA.l $7EF3CC : AND.w #$00FF : BNE .empty", HUD_CODEX)
        self.assertIn("LDA.l ItemBindingSavedX : AND.w #$00FF : CMP.w #$0001 : BEQ .form_ok", HUD_CODEX)

    def test_heavy_sword_labels_and_select_help_popup(self):
        self.assertIn('dw "_BROKEN_BLADE_"', SWORDS)
        self.assertIn('dw "__GORONBLADE__"', SWORDS)
        self.assertIn("LDA.l SwordSlotFlags : AND.b #!SwordSlot_HeavyReforged : BNE .heavy_reforged", SWORDS)
        # Select Help Popup wired on all 4 pages + state $09 handler
        self.assertIn("!MENU_STATE_HELP_POPUP          = $09", MENU)
        self.assertIn("dw Menu_HelpPopup", MENU)
        self.assertIn("LDA.b #!MENU_STATE_HELP_POPUP : STA.w $0200", PAGE3)
        self.assertGreaterEqual(PAGE3.count("JSL MenuHelp_Draw_Long"), 2)
        # Verify every help line is exactly 18 chars and all 4 pages exist
        lines = re.findall(r'dw "([A-Z.:_]{18})"', V5_EXT)
        self.assertEqual(len(lines), 24, "Expected 4 pages x 6 lines x 18 tiles in MenuHelp_Draw_Long")

    def test_quest_songs_full_4x4_cursor_and_special_ow_names_and_minimap(self):
        # QuestSongs_DrawCursor upgraded to full 4x4 C4 frame/L-brackets
        self.assertIn("JSL Menu_C4_DrawEquipBox_Long", CURSOR_FLOW)
        self.assertIn("JSL Menu_C4_DrawEquipCursor_Long", CURSOR_FLOW)
        self.assertNotIn("STA.w $1106,X", CURSOR_FLOW)
        # Map & Spoils title has clean spaces (no slash) and calls Special OW area names
        self.assertIn('dw "_MAP_SPOILS_"', MAP_TRAVEL)
        self.assertIn("JSL MenuMap_SpecialAreaName_Long", MAP_TRAVEL)
        # Special OW $80-$BF index table has exactly 64 entries referencing valid names (0..16)
        im = re.search(r"\.map_index\s*\n((?:\s*db [^\n]+\n)+)", V5_EXT)
        self.assertIsNotNone(im)
        indices = [int(v) for v in re.findall(r"\b\d+\b", re.sub(r";[^\n]*", "", im.group(1)))]
        self.assertEqual(len(indices), 64)
        self.assertTrue(all(0 <= v <= 16 for v in indices))
        # Mini-Map terrain has exactly 3 worlds x 64 cells = 192 entries (values 0..5)
        tm = re.search(r"\.terrain\s*\n(.*?)\n\}", V5_EXT, re.S)
        self.assertIsNotNone(tm)
        tvals = [int(v) for v in re.findall(r"\b\d+\b", re.sub(r";[^\n]*", "", tm.group(1)))]
        self.assertEqual(len(tvals), 192)
        self.assertTrue(all(0 <= v <= 5 for v in tvals))


if __name__ == "__main__":
    unittest.main()
