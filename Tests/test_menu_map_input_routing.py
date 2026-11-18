"""Unit/contract checks for unified Menu and Map button routing."""
from __future__ import annotations

from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCROLL = ROOT / "Menu" / "menu_scroll.asm"
BINDINGS = ROOT / "Menu" / "menu_item_bindings.asm"
PAGE3 = ROOT / "Menu" / "menu_page3.asm"
QUEST = ROOT / "Menu" / "menu_quest.asm"
MAP_TRAVEL = ROOT / "Menu" / "menu_map_travel.asm"
MENU = ROOT / "Menu" / "menu.asm"


def _routine_body(path: Path, name: str) -> str:
    text = path.read_text(encoding="utf-8")
    m = re.search(rf"^{name}:\s*\n\{{\n(.*?)^\}}", text, re.M | re.S)
    if not m:
        raise AssertionError(f"{name} not found in {path.name}")
    lines = []
    for raw in m.group(1).splitlines():
        code = raw.split(";", 1)[0].strip()
        if code:
            lines.append(code)
    return "\n".join(lines)


class TestMenuMapInputRoutingContracts(unittest.TestCase):
    def test_items_page_bindings_accept_a_and_y_and_never_close_on_a(self):
        hscroll = _routine_body(SCROLL, "Menu_CheckHScroll")
        self.assertIn("BIT.b #$90 : BNE .leave_menu", hscroll)
        self.assertNotIn("BIT.b #$80", hscroll, "A must never close the pause menu")

        bindings = _routine_body(BINDINGS, "Menu_Bindings_Input")
        self.assertIn("LDA.b $F4 : BIT.b #$40 : BNE .bind_y", bindings)
        self.assertIn("LDA.b $F6 : BIT.b #$80 : BEQ .no_y", bindings)
        self.assertIn("LDA.b #$80 : TRB.b $F6", bindings)

    def test_equipment_quest_and_map_pages_close_on_b_or_start_never_a(self):
        quest = _routine_body(QUEST, "Menu_QuestScreen")
        self.assertIn("LDA.b $F4 : BIT.b #$90 : BEQ .no_start", quest)
        self.assertNotIn("BIT.b #$80", quest, "A must never close Quest")

        map_screen = _routine_body(MAP_TRAVEL, "MenuMapTravel_Screen")
        self.assertIn("LDA.b $F4 : BIT.b #$90 : BEQ .no_start", map_screen)

        p3_item = _routine_body(PAGE3, "Menu_Page3_ItemScreen")
        self.assertIn("BIT.b #$90 : BEQ .ring_turn", p3_item)
        self.assertNotIn("A closes the menu first", PAGE3.read_text(encoding="utf-8"))

        p3_stats = _routine_body(PAGE3, "Menu_Page3_StatsScreen")
        self.assertIn("BIT.b #$90 : BNE .ring_no_lr", p3_stats)
        self.assertIn("BIT.b #$90 : BNE .quest_input", p3_stats)
        self.assertIn("BIT.b #$90 : BNE .quest", p3_stats)
        self.assertIn("BIT.b #$90 : BEQ .no_start", p3_stats)

    def test_submenus_allow_b_return(self):
        journal = _routine_body(MENU, "Menu_Journal")
        self.assertIn("LDA.b $F4 : BIT.b #$80 : BNE .return_pressed", journal)
        self.assertIn("LDA.b $F4 : BIT.b #$10 : BNE .close_menu", journal)

        sub = _routine_body(MENU, "Submenu_Return")
        self.assertIn("LDA.b $F4 : BIT.b #$80 : BNE .return", sub)
        self.assertIn("LDA.b $F4 : BIT.b #$10 : BEQ +", sub)

    def test_world_and_dungeon_map_exit_logic(self):
        """Simulate Menu_WorldMapCheckExit and Menu_DungeonMapCheckExit semantics."""
        txt = MAP_TRAVEL.read_text(encoding="utf-8")
        self.assertIn("org $0ABAFB", txt)
        self.assertIn("org $0ABB00", txt)
        self.assertIn("org $0AE95E", txt)

        def eval_world_map(f4: int, f6: int, zoom_state: int) -> bool:
            if f4 & 0x90:
                return True
            if zoom_state != 0:
                return False
            return bool(f6 & 0x40)

        def eval_dungeon_map(f4: int, f6: int) -> bool:
            if f4 & 0x90:
                return True
            return bool(f6 & 0x40)

        # World map: B ($80) / Start ($10) exit both zoomed in and zoomed out;
        # A ($80 on $F6) never exits; X ($40 on $F6) exits only when zoomed out.
        for zoom in (0, 1, 0x81):
            self.assertTrue(eval_world_map(0x80, 0x00, zoom), f"B should exit zoom={zoom}")
            self.assertTrue(eval_world_map(0x10, 0x00, zoom), f"Start should exit zoom={zoom}")
            self.assertFalse(eval_world_map(0x00, 0x80, zoom), f"A must not exit zoom={zoom}")
        self.assertFalse(eval_world_map(0x00, 0x40, 1))
        self.assertTrue(eval_world_map(0x00, 0x40, 0))

        # Dungeon map: B/Start/X exit; A never exits.
        self.assertTrue(eval_dungeon_map(0x80, 0x00))
        self.assertTrue(eval_dungeon_map(0x10, 0x00))
        self.assertTrue(eval_dungeon_map(0x00, 0x40))
        self.assertFalse(eval_dungeon_map(0x00, 0x80))


if __name__ == "__main__":
    unittest.main()
