#!/usr/bin/env python3
"""Native proof: dual-item binding in more game states, plus old-save reload.

Needs a ROM built with ENABLE_DUAL_ITEM_BINDING_PROTOTYPE=1 (and, for the
HUD screenshots, ENABLE_HUD_LAYOUT_CODEX=1). Launches its own private headless
Mesen2-OOS (never oos-rc-play). Companion to dual_item_binding.py (overworld,
Game Over save/reopen) and dual_item_menu_assign.py (menu assignment).

Declared fixture writes (unearned inventory/bindings, not acquisition proof):
Bow 2 + 30 arrows, Boomerang 1, Hookshot 1, Bottle 1 = empty, Bombchu owned +
10 bombs, the saved/volatile binding bytes, and the message ID/module bytes
that open a text box in the dialogue case.

Cases (real controller input after each fixture):
1. dungeon: Y fires an arrow, X throws the boomerang, no dungeon map.
2. dialogue: with a forced text box (module $0E), Y and X start nothing; the
   fixture restores play, then X throws the boomerang.
3. bottle_y: Y = Bottle (Y-only item). X still throws the boomerang and
   $0202 stays the bottle.
4. bombchu_conflict: Y = Bombchu, X = Bombs (same bomb routine). X places a
   normal bomb (the routine reads ItemBindings_EffectiveItem); Bombchu ammo
   is kept.
5. old_save: saved bindings version 0 (a save from before the feature) with
   Hookshot on Y. Gameplay hydrates version 1 with Y = Hookshot; X = Bow is
   then assigned. Game Over Save & Quit, fresh process, cold boot: Y is still
   Hookshot (not Bow, the first owned item), X fires an arrow.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("dual_item_binding", HERE / "dual_item_binding.py")
base = importlib.util.module_from_spec(spec)
spec.loader.exec_module(base)
deku = base.deku

MODULE, SUBMODULE = base.MODULE, base.SUBMODULE
Y_ITEM, BUTTON = base.Y_ITEM, base.BUTTON
CURSOR, LOGICAL, BUTTON_ACTION = base.CURSOR, base.LOGICAL, base.BUTTON_ACTION
SAVED_VERSION, SAVED_Y, SAVED_X = base.SAVED_VERSION, base.SAVED_Y, base.SAVED_X
BOW, BOOMERANG, ARROWS = base.BOW, base.BOOMERANG, base.ARROWS
HOOKSHOT, BOMBS, BOTTLE1, BOMBCHU_OWNED = 0x7EF342, 0x7EF343, 0x7EF35C, 0x7EF3AD
ARROW_ID, BOOMERANG_ID, BOMB_ID, HOOKSHOT_ANC = 0x09, 0x05, 0x07, 0x1F
MSG_ID, MSG_SAVED_MODULE = 0x7E1CF0, 0x7E010C
ID_BOW, ID_BOOMERANG, ID_HOOKSHOT, ID_BOMBS, ID_BOTTLE1, ID_BOMBCHU = 1, 2, 3, 4, 6, 0x1C
DUNGEON_MAP_MODULE = 0x0E


class StatesTest(base.DualItemBindingTest):
    def inventory(self):
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(BOOMERANG, 1); self.w(HOOKSHOT, 1)
        self.w(BOTTLE1, 2); self.w(BOMBCHU_OWNED, 1); self.w(BOMBS, 10)

    def bindings(self, y_item, version, saved_y, saved_x, hydrated=True):
        self.inventory()
        self.w(Y_ITEM, y_item)
        self.w(SAVED_VERSION, version); self.w(SAVED_Y, saved_y); self.w(SAVED_X, saved_x)
        for a in (LOGICAL, BUTTON_ACTION, BUTTON):
            self.w(a, 0)
        # Cursor 0 = not yet hydrated this session (what AdapterReset leaves).
        self.w(CURSOR, y_item if hydrated else 0)
        time.sleep(0.25)

    def ancilla_count(self, ident):
        return sum(self.r(base.ANCILLA + i) == ident for i in range(5))

    def settle(self):
        self.idle()
        for i in range(5):  # drop leftovers so later "has" checks start clean
            if self.r(base.ANCILLA + i) in (ARROW_ID, BOOMERANG_ID, BOMB_ID, HOOKSHOT_ANC):
                self.wait_for(lambda: self.r(base.ANCILLA + i) == 0, 4.0)

    # 1 ---------------------------------------------------------------
    def dungeon(self):
        self.boot_indoor_dungeon()
        self.bindings(ID_BOW, 1, ID_BOW, ID_BOOMERANG)
        self.snap("dungeon_fixture")
        self.b.press_button("y", frames=4, detach_debugger=False)
        self.check("dungeon_Y_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.settle()
        self.b.press_button("x", frames=4, detach_debugger=False)
        thrown = self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5)
        s = self.snap("dungeon_after_X")
        self.check("dungeon_X_throws_boomerang", thrown)
        self.check("dungeon_X_no_map", s["module"] != DUNGEON_MAP_MODULE)
        self.check("dungeon_Y_kept", s["y_item"] == ID_BOW)
        self.take_screenshot("10_dungeon_X")
        self.settle()

    # 2 ---------------------------------------------------------------
    def dialogue(self):
        self.boot_file2()
        self.bindings(ID_BOW, 1, ID_BOW, ID_BOOMERANG)
        play_module = self.r(MODULE)
        self.w(MSG_ID, 0x20); self.w(MSG_ID + 1, 0x00)
        self.w(MSG_SAVED_MODULE, play_module)
        self.w(SUBMODULE, 0x02); self.w(MODULE, 0x0E)
        opened = self.wait_for(lambda: self.r(MODULE) == 0x0E and self.r(SUBMODULE) == 0x02, 2.0)
        time.sleep(1.0)
        self.take_screenshot("11_dialogue_open")
        for key in ("x", "y"):
            self.b.press_button(key, frames=4, detach_debugger=False)
            time.sleep(0.2)
        s = self.snap("dialogue_after_XY")
        self.check("dialogue_opened", opened)
        self.check("dialogue_XY_start_nothing",
                   s["button"] == 0 and not self.has(ARROW_ID) and not self.has(BOOMERANG_ID)
                   and s["y_item"] == ID_BOW and s["saved"] == [1, ID_BOW, ID_BOOMERANG])
        # The forced text box has no real message context and A does not close
        # it. Restore play as a fixture step, then X must route again.
        self.w(SUBMODULE, 0x00); self.w(MODULE, play_module)
        restored = self.wait_play(4.0)
        self.check("dialogue_fixture_restored_play", restored)
        time.sleep(0.3)
        self.b.press_button("x", frames=4, detach_debugger=False)
        self.check("dialogue_after_X_throws",
                   self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5))
        self.snap("dialogue_after_close_X")
        self.settle()

    # 3 ---------------------------------------------------------------
    def bottle_y(self):
        self.boot_file2()
        # Not hydrated: the first Route call must hydrate from a Y-only item.
        self.bindings(ID_BOTTLE1, 1, ID_BOW, ID_BOOMERANG, hydrated=False)
        self.snap("bottle_fixture")
        self.b.press_button("x", frames=4, detach_debugger=False)
        thrown = self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5)
        s = self.snap("bottle_after_X")
        self.check("bottle_Y_X_throws_boomerang", thrown and s["module"] != base.MAP_MODULE)
        self.check("bottle_Y_kept", s["y_item"] == ID_BOTTLE1 and s["saved"][1] == ID_BOTTLE1)
        self.take_screenshot("12_bottle_Y_boomerang_X")
        self.settle()

    # 4 ---------------------------------------------------------------
    def bombchu_conflict(self):
        self.boot_file2()
        self.bindings(ID_BOMBCHU, 1, ID_BOMBCHU, ID_BOMBS)
        bombs = self.r(BOMBS)
        self.b.press_button("x", frames=4, detach_debugger=False)
        time.sleep(0.5)
        s = self.snap("bombchu_after_X")
        self.check("bombchu_X_places_bomb",
                   self.ancilla_count(BOMB_ID) >= 1 and self.r(BOMBS) == bombs - 1
                   and s["y_item"] == ID_BOMBCHU)
        self.take_screenshot("13_bombchu_Y_bombs_X")
        # Return to a plain state for the next case.
        self.bindings(ID_BOW, 1, ID_BOW, ID_BOOMERANG)

    # 5 ---------------------------------------------------------------
    def old_save(self):
        self.boot_file2()
        self.bindings(ID_HOOKSHOT, 0, 0, 0, hydrated=False)
        hydrated = self.wait_for(lambda: self.r(SAVED_VERSION) == 1, 2.0)
        s = self.snap("old_save_hydrated")
        self.check("old_save_hydrates_v1_Y_hookshot",
                   hydrated and s["saved"][:2] == [1, ID_HOOKSHOT] and s["y_item"] == ID_HOOKSHOT)
        self.w(SAVED_X, ID_BOW)       # fixture: X = Bow, the first owned item
        time.sleep(0.2)
        self.b.press_button("x", frames=4, detach_debugger=False)
        self.check("old_save_X_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.settle()

        # Game Over -> Save & Quit (same path as dual_item_binding.py).
        self.w(0x7EF3C5, max(self.r(0x7EF3C5), 2))
        hp = self.r(0x7EF36D) or 24
        self.w(0x7EF36D, hp); self.w(0x7E037B, 0); self.w(0x7E0373, hp)
        if not self.wait_for(lambda: self.r(MODULE) == 18 and self.r(SUBMODULE) == 9, 15.0):
            raise RuntimeError("Game Over screen not reached")
        self.take_screenshot("14_game_over")
        for _ in range(6):
            if self.r(deku.CHOICE) == 1:
                self.b.press_button("a", frames=8, detach_debugger=False)
                break
            self.b.press_button("select", frames=8, detach_debugger=False)
            time.sleep(0.3)
        self.wait_for(lambda: self.r(MODULE) in (0, 1, 0x14), 15.0)
        sram = self.b.read_block(0, 8192, memtype="SnesSaveRam")
        csum = sum(int.from_bytes(sram[i:i + 2], "little") for i in range(0, 0x500, 2)) & 0xFFFF
        saved = list(sram[0x3B9:0x3BC])
        print(f"    SRAM checksum=0x{csum:04X} bindings={saved}")
        self.check("old_save_sram_checksum", csum == 0x5A5A)
        self.check("old_save_sram_bindings", saved == [1, ID_HOOKSHOT, ID_BOW])
        (self.home / "Saves" / "deku_candidate.srm").write_bytes(sram)
        (self.work_dir / "old_save.srm").write_bytes(sram)

        self.close()
        self.launch(reset_save=False)
        self.boot_fresh_file()
        time.sleep(0.5)
        s = self.snap("old_save_reopened")
        self.check("reopen_Y_still_hookshot", s["y_item"] == ID_HOOKSHOT)
        self.check("reopen_saved_bindings", s["saved"] == [1, ID_HOOKSHOT, ID_BOW])
        self.take_screenshot("15_reopened_hud")
        self.w(ARROWS, 30)
        self.b.press_button("x", frames=4, detach_debugger=False)
        self.check("reopen_X_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.settle()
        self.b.press_button("y", frames=4, detach_debugger=False)
        self.check("reopen_Y_fires_hookshot", self.wait_for(lambda: self.has(HOOKSHOT_ANC), 1.5))
        self.snap("old_save_reopened_Y")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=deku.APP_DEFAULT)
    args = ap.parse_args()
    t = StatesTest(args.rom, args.app, args.work)
    result = {"rom": str(args.rom), "status": "ERROR"}
    try:
        t.launch()
        t.dungeon()
        t.dialogue()
        t.bottle_y()
        t.bombchu_conflict()
        t.old_save()
        result["status"] = "PASS" if t.checks and all(t.checks.values()) else "FAIL"
    except Exception as e:  # recorded, still non-zero
        result["error"] = repr(e)
    finally:
        t.close()
        result.update(checks=t.checks, log=t.log)
        (args.work / "RESULT.json").write_text(json.dumps(result, indent=2) + "\n")
        print(json.dumps({"status": result["status"], "failed": [k for k, v in t.checks.items() if not v],
                          "error": result.get("error")}))
    sys.exit(0 if result["status"] == "PASS" else 1)


if __name__ == "__main__":
    main()
