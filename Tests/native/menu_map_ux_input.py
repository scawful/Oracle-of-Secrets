#!/usr/bin/env python3
"""Native proof: unified Menu and Map button routing across all pages and maps.

Verifies in private headless Mesen2-OOS:
1. Items page: A binds Y without closing; Y binds Y without closing; X binds/clears X;
   B closes the menu with the A-bound Y item persisted.
2. Equipment page: A equips (ring toggle) without closing; B closes cleanly.
3. Quest page: A never closes (both with no songs and when selecting a song);
   B closes cleanly.
4. Map page: B closes directly; A on [MAP] opens Overworld Map.
5. Overworld Map (from Map page AND direct gameplay X):
   - Zoomed IN ($7E0636 != 0): A stays on map; X zooms out; B exits immediately
     and reopens the Map page cleanly when Pending == 3 (no double-close).
   - Zoomed OUT ($7E0636 == 0): A stays on map; B exits immediately.
6. Dungeon Map (clean Module 05 dungeon load, both direct X AND Map page):
   - A stays on Dungeon Map; B exits immediately (reopening Map page when Pending == 3).
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("deku_proof", HERE / "deku_stick_runtime_proof.py")
deku = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deku)

MODULE, SUBMODULE = 0x7E0010, 0x7E0011
UNDERWORLD_FLAG = 0x7E001B
MENU, Y_ITEM, BLINK = 0x7E0200, 0x7E0202, 0x7E0207
CURSOR2, H_SCROLL = 0x7E020B, 0x7E1E71
LAST_PAGE, ITEMS_CURSOR = 0x7E02BF, 0x7E02BE
MENU_Y, PENDING = 0x7E02B7, 0x7E1EFF
WORLD_ZOOM = 0x7E0636
SAVED_VERSION, SAVED_Y, SAVED_X = 0x7EF3B9, 0x7EF3BA, 0x7EF3BB
BOW, BOOMERANG, HOOKSHOT, ARROWS = 0x7EF340, 0x7EF341, 0x7EF342, 0x7EF377
DEKU_MASK, OCARINA, SONGS_FLAGS = 0x7EF349, 0x7EF34C, 0x7EF3D8
FOUNDRINGS, MAGICRINGS, RING_SLOT1 = 0x7EF3A1, 0x7EF3A2, 0x7EF3A3
SWORD, SHIELD, ARMOR = 0x7EF359, 0x7EF35A, 0x7EF35B
DNG_MAP1, DNG_MAP2, TINGLE_MAPS = 0x7EF368, 0x7EF369, 0x7EF396
CURRENT_SONG, SAVED_SONG = 0x7E030F, 0x7EF3AB

ITEMS_PAGE = 0x04
RIGHT_PAGE = 0x06
WORLD_MAP_SUB = 0x07
DUNGEON_MAP_SUB = 0x03


class MenuMapUxInputTest(deku.DekuStickRuntimeTest):
    def __init__(self, rom: Path, app: Path, work: Path):
        super().__init__(rom, app, work)
        self.checks: dict[str, bool] = {}
        self.log: list[dict] = []

    def check(self, name: str, ok: bool) -> None:
        self.checks[name] = bool(ok)
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")

    def wait_for(self, pred, timeout: float = 5.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.02)
        return False

    def snap(self, label: str) -> dict:
        s = dict(
            label=label,
            module=self.r(MODULE),
            sub=self.r(SUBMODULE),
            menu=self.r(MENU),
            hscroll=self.r(H_SCROLL),
            last_page=self.r(LAST_PAGE),
            y_item=self.r(Y_ITEM),
            menu_y=self.r(MENU_Y),
            cursor2=self.r(CURSOR2),
            pending=self.r(PENDING),
            zoom=self.r(WORLD_ZOOM),
            ring1=self.r(RING_SLOT1),
            song=self.r(CURRENT_SONG),
            saved=[self.r(SAVED_VERSION), self.r(SAVED_Y), self.r(SAVED_X)],
        )
        self.log.append(s)
        print(f"    {label}: {json.dumps({k: v for k, v in s.items() if k != 'label'})}")
        return s

    def open_pause(self, page_state: int = ITEMS_PAGE, hscroll: int = 0x00) -> bool:
        self.press("START", frames=6)
        ok = self.wait_for(
            lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == 0x01
            and self.r(MENU) == page_state and self.r(H_SCROLL) == hscroll,
            4.0,
        )
        time.sleep(0.35)
        return ok

    def turn_page(self, button: str, target_hscroll: int) -> bool:
        self.press(button, frames=6)
        ok = self.wait_for(
            lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == 0x01
            and self.r(MENU) == RIGHT_PAGE and self.r(H_SCROLL) == target_hscroll,
            4.0,
        )
        time.sleep(0.35)
        return ok

    def close_pause_b(self) -> bool:
        self.press("B", frames=6)
        return self.wait_play(5.0)

    def tap(self, button: str, delay: float = 0.35) -> None:
        self.press(button, frames=5)
        time.sleep(delay)

    def run_all(self) -> None:
        # Clean overworld fixture
        self.boot_file2()
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(BOOMERANG, 1); self.w(HOOKSHOT, 1)
        self.w(DEKU_MASK, 1); self.w(SWORD, 2); self.w(SHIELD, 2); self.w(ARMOR, 1)
        self.w(FOUNDRINGS, 0x3F); self.w(MAGICRINGS, 0x3F); self.w(RING_SLOT1, 0)
        self.w(OCARINA, 0); self.w(SONGS_FLAGS, 0); self.w(CURRENT_SONG, 0); self.w(SAVED_SONG, 0)
        self.w(LAST_PAGE, 0); self.w(ITEMS_CURSOR, 1)
        self.w(Y_ITEM, 1)
        self.w(SAVED_VERSION, 1); self.w(SAVED_Y, 1); self.w(SAVED_X, 0)
        time.sleep(0.25)

        # 1. ITEMS PAGE: A binds Y, Y binds Y, X binds X, B closes cleanly.
        self.check("items_opened", self.open_pause(ITEMS_PAGE, 0x00))
        self.tap("RIGHT")  # cursor -> Boomerang (2)
        self.tap("A")
        s = self.snap("items_A_binds")
        self.check("items_A_binds_Y_no_close", s["menu"] == ITEMS_PAGE and s["y_item"] == 2 and s["menu_y"] == 2)
        self.tap("RIGHT")  # cursor -> Hookshot (3)
        self.tap("Y")
        s = self.snap("items_Y_binds")
        self.check("items_Y_binds_Y_no_close", s["menu"] == ITEMS_PAGE and s["y_item"] == 3 and s["menu_y"] == 3)
        self.tap("LEFT")   # cursor -> Boomerang (2)
        self.tap("X")
        s = self.snap("items_X_binds")
        self.check("items_X_binds_X_no_close", s["menu"] == ITEMS_PAGE and s["saved"][2] == 2)
        self.check("items_B_closes", self.close_pause_b())
        s = self.snap("items_after_B_close")
        self.check("items_B_persisted_Y_and_X", s["y_item"] == 3 and s["saved"] == [1, 3, 2])

        # 2. EQUIPMENT PAGE: A toggles/equips without closing, B closes cleanly.
        self.check("reopen_items_for_equip", self.open_pause(ITEMS_PAGE, 0x00))
        self.check("turn_right_to_equip", self.turn_page("R", 0x20))
        self.tap("DOWN")   # Init starts at slot 0 (Deku Mask); 1 DOWN -> slot 6 (Ring 1)
        self.tap("A")
        s = self.snap("equip_A_press")
        self.check("equip_A_equips_ring_no_close",
                   s["menu"] == RIGHT_PAGE and s["hscroll"] == 0x20 and s["cursor2"] == 6 and s["ring1"] == 2)
        self.check("equip_B_closes", self.close_pause_b())

        # 3. QUEST PAGE: A never closes (no songs AND with learned songs), B closes.
        self.check("reopen_equip", self.open_pause(RIGHT_PAGE, 0x20))
        self.check("turn_right_to_quest", self.turn_page("R", 0x00))
        self.tap("A")
        s = self.snap("quest_no_songs_A")
        self.check("quest_no_songs_A_stays_open", s["menu"] == RIGHT_PAGE and s["hscroll"] == 0x00)
        self.check("quest_B_closes_no_songs", self.close_pause_b())

        # Enable Ocarina + songs, reopen Quest (MenuFlow_LastPage == $00)
        self.w(OCARINA, 5); self.w(SONGS_FLAGS, 0x22)
        self.check("reopen_quest_with_songs", self.open_pause(RIGHT_PAGE, 0x00))
        self.tap("A")
        s = self.snap("quest_song_A")
        self.check("quest_song_A_binds_no_close",
                   s["menu"] == RIGHT_PAGE and s["hscroll"] == 0x00 and s["song"] != 0)
        self.check("quest_B_closes_with_songs", self.close_pause_b())

        # Restore Y=Bow, X cleared for Map tests.
        self.w(SAVED_X, 0)
        self.w(Y_ITEM, 1)
        self.w(0x7E02B3, 0); self.w(0x7E02B4, 0); self.w(0x7E02B5, 0); self.w(0x7E02B6, 0)

        # 4. MAP PAGE & OVERWORLD MAP:
        #    (a) B closes Map page directly.
        self.check("reopen_quest_to_map", self.open_pause(RIGHT_PAGE, 0x00))
        self.check("turn_right_to_map", self.turn_page("R", 0x40))
        self.check("map_page_B_closes", self.close_pause_b())

        #    (b) Reopen Map page (LastPage=$40), press A on [MAP] -> Overworld Map (zoomed IN).
        self.check("reopen_map_page", self.open_pause(RIGHT_PAGE, 0x40))
        self.tap("A", delay=0.1)
        self.check("world_map_opened_from_menu",
                   self.wait_for(lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == WORLD_MAP_SUB, 4.0))
        time.sleep(0.5)
        s = self.snap("world_map_zoomed_in")
        self.check("world_map_starts_zoomed_in", s["zoom"] != 0)
        #    A while zoomed in stays open
        self.tap("A")
        s = self.snap("world_map_A_zoomed_in")
        self.check("world_map_A_ignored_zoomed_in", s["module"] == 0x0E and s["sub"] == WORLD_MAP_SUB)
        #    X zooms out (to $0636 == 0)
        self.tap("X", delay=0.5)
        s = self.snap("world_map_zoomed_out")
        self.check("world_map_X_zooms_out", s["module"] == 0x0E and s["sub"] == WORLD_MAP_SUB and s["zoom"] == 0)
        #    A while zoomed out STILL stays open
        self.tap("A")
        s = self.snap("world_map_A_zoomed_out")
        self.check("world_map_A_ignored_zoomed_out", s["module"] == 0x0E and s["sub"] == WORLD_MAP_SUB)
        #    B while zoomed out exits AND Pending==3 cleanly reopens Map page without double-closing
        self.tap("B", delay=0.1)
        reopened = self.wait_for(lambda: self.r(MENU) == RIGHT_PAGE and self.r(H_SCROLL) == 0x40, 5.0)
        time.sleep(0.4)
        s = self.snap("map_page_after_B_from_world_map")
        self.check("world_map_B_reopens_map_page_no_double_close",
                   reopened and s["menu"] == RIGHT_PAGE and s["hscroll"] == 0x40)
        self.check("map_page_close_after_reopen", self.close_pause_b())

        #    (c) Direct Overworld X opens zoomed IN ($0636 != 0), B exits immediately to Overworld!
        self.tap("X", delay=0.1)
        self.check("direct_X_opens_world_map",
                   self.wait_for(lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == WORLD_MAP_SUB, 4.0))
        time.sleep(0.5)
        self.tap("B", delay=0.1)
        self.check("world_map_B_exits_while_zoomed_in", self.wait_play(5.0))
        s = self.snap("overworld_after_zoomed_in_B")
        self.check("returned_to_overworld_play", s["module"] == 0x09 and s["sub"] == 0x00)

        # 5. DUNGEON MAP: clean Module 05 dungeon load.
        self.boot_clean_dungeon(entrance_id=0x27, area_id=0x36)
        self.w(DNG_MAP1, 0xFF); self.w(DNG_MAP2, 0xFF); self.w(TINGLE_MAPS, 0xFF)
        self.w(SAVED_X, 0); self.w(SAVED_Y, 1); self.w(Y_ITEM, 1)
        self.w(0x7E02B3, 0); self.w(0x7E02B4, 0); self.w(0x7E02B5, 0); self.w(0x7E02B6, 0)
        self.w(LAST_PAGE, 0)
        time.sleep(0.25)

        #    (a) Direct X opens Dungeon Map -> A ignored, B exits to Dungeon play ($07).
        self.tap("X", delay=0.1)
        self.check("direct_X_opens_dungeon_map",
                   self.wait_for(lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == DUNGEON_MAP_SUB and self.r(MENU) == 3, 5.0))
        time.sleep(0.25)
        self.tap("A")
        s = self.snap("dungeon_map_A")
        self.check("dungeon_map_A_ignored", s["module"] == 0x0E and s["sub"] == DUNGEON_MAP_SUB)
        self.tap("B", delay=0.1)
        self.check("dungeon_map_B_exits", self.wait_play(5.0))
        s = self.snap("dungeon_play_after_B")
        self.check("returned_to_dungeon_play", s["module"] == 0x07 and s["sub"] == 0x00 and self.r(UNDERWORLD_FLAG) == 1)

        #    (b) Map page -> A on [MAP] opens Dungeon Map -> B reopens Map page cleanly!
        self.check("dungeon_open_items", self.open_pause(ITEMS_PAGE, 0x00))
        self.check("dungeon_turn_to_map", self.turn_page("L", 0x40))
        self.tap("A", delay=0.1)
        self.check("dungeon_map_opened_from_menu",
                   self.wait_for(lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == DUNGEON_MAP_SUB and self.r(MENU) == 3, 5.0))
        time.sleep(0.25)
        self.tap("A")
        s = self.snap("dungeon_map_from_menu_A")
        self.check("dungeon_map_from_menu_A_ignored", s["module"] == 0x0E and s["sub"] == DUNGEON_MAP_SUB)
        self.tap("B", delay=0.1)
        dng_reopened = self.wait_for(
            lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == 0x01
            and self.r(MENU) == RIGHT_PAGE and self.r(H_SCROLL) == 0x40,
            5.0,
        )
        time.sleep(0.4)
        s = self.snap("dungeon_map_page_after_B")
        self.check("dungeon_map_B_reopens_map_page_no_double_close",
                   dng_reopened and s["sub"] == 0x01 and s["menu"] == RIGHT_PAGE
                   and s["hscroll"] == 0x40 and s["pending"] == 0)
        self.check("dungeon_map_page_B_closes", self.close_pause_b())


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=deku.APP_DEFAULT)
    args = ap.parse_args()
    args.work.mkdir(parents=True, exist_ok=True)
    t = MenuMapUxInputTest(args.rom, args.app, args.work)
    result = {"rom": str(args.rom), "status": "ERROR"}
    try:
        t.launch()
        t.run_all()
        result["status"] = "PASS" if t.checks and all(t.checks.values()) else "FAIL"
    except Exception as exc:
        result["error"] = repr(exc)
    finally:
        t.close()
        result.update(checks=t.checks, log=t.log)
        (args.work / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        failed = [k for k, v in t.checks.items() if not v]
        print(json.dumps({"status": result["status"], "failed": failed, "error": result.get("error")}))
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
