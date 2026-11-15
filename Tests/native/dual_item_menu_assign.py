#!/usr/bin/env python3
"""Native proof: bind Y and X by pressing Y and X on the Items page.

Needs a ROM built with ENABLE_DUAL_ITEM_BINDING_PROTOTYPE=1. Launches its own
private headless Mesen2-OOS (never oos-rc-play) from the gameplay baseline.

Declared fixture writes (unearned inventory, not acquisition proof):
Bow level 2 + 30 arrows, Boomerang level 1, Hookshot level 1, $0202=Boomerang,
and a clean binding start (saved version/Y/X = 0, volatile latch = 0).
No binding value is written by the test: every binding comes from menu input.

Scenario (all real controller input):
1. START opens the Items page on Boomerang. X binds X=Boomerang.
2. LEFT moves the cursor to Bow; the Y item does not change (no equip on move).
   Y binds Y=Bow. The menu buffer holds green Y corners and blue X corners.
3. X on Bottle (Y-only item) is refused: saved X stays Boomerang. Hookshot
   is latchable since the dispatch slice, so it no longer serves as the refusal.
4. X on Boomerang again clears X; X again binds it back.
5. START closes the menu: $0202=Bow, saved bindings [1, 1, 2].
6. In gameplay Y fires an arrow and X throws the boomerang without the map.
7. Reopen, move to Boomerang, press A: the menu closes and $0202 stays Bow
   (A never binds).
8. Same item on both buttons: Y on Boomerang shows green left and blue right corners.

--codex (ROM built with hud_layout_codex): one corner per button instead of
four (Y = green top-left, X = blue bottom-right), so the marker counts differ.
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
MENU = 0x7E0200
Y_ITEM = 0x7E0202
CURSOR, LOGICAL, BUTTON_ACTION, BUTTON, MENU_Y = 0x7E02B3, 0x7E02B4, 0x7E02B5, 0x7E02B6, 0x7E02B7
SAVED_VERSION, SAVED_Y, SAVED_X = 0x7EF3B9, 0x7EF3BA, 0x7EF3BB
BOW, BOOMERANG, HOOKSHOT, ARROWS = 0x7EF340, 0x7EF341, 0x7EF342, 0x7EF377
BOTTLE1 = 0x7EF35C  # menu ID 6, Y-only
ANCILLA = 0x7E0C4A
ARROW_ID, BOOMERANG_ID = 0x09, 0x05
MAP_MODULE = 0x0E
MENU_BUF, MENU_BUF_LEN = 0x7E1000, 0x800
Y_MARKER, X_MARKER = 0x3C60, 0x2C60  # corner glyph $060; flips add $4000/$8000
ITEMS_PAGE = 0x04


class MenuAssignTest(deku.DekuStickRuntimeTest):
    def __init__(self, rom, app, work, codex=False):
        super().__init__(rom, app, work)
        self.codex = codex
        self.log: list[dict] = []
        self.checks: dict[str, bool] = {}

    def snap(self, label):
        s = dict(label=label, module=self.r(MODULE), sub=self.r(SUBMODULE), menu=self.r(MENU),
                 y_item=self.r(Y_ITEM), menu_y=self.r(MENU_Y), cursor=self.r(CURSOR),
                 button=self.r(BUTTON),
                 saved=[self.r(SAVED_VERSION), self.r(SAVED_Y), self.r(SAVED_X)],
                 ancilla=[self.r(ANCILLA + i) for i in range(5)])
        self.log.append(s)
        print(f"    {label}: {json.dumps({k: v for k, v in s.items() if k != 'label'})}")
        return s

    def check(self, name, ok):
        self.checks[name] = bool(ok)
        print(f"    [{'PASS' if ok else 'FAIL'}] {name}")

    def wait_for(self, pred, timeout=4.0):
        end = time.time() + timeout
        while time.time() < end:
            if pred():
                return True
            time.sleep(0.02)
        return False

    def has(self, ident):
        return any(self.r(ANCILLA + i) == ident for i in range(5))

    def markers(self):
        buf = self.b.read_block(MENU_BUF, MENU_BUF_LEN)
        words = [buf[i] | (buf[i + 1] << 8) for i in range(0, len(buf) - 1, 2)]
        ys = [0x1000 + 2 * i for i, w in enumerate(words) if w & 0x3FFF == Y_MARKER]
        xs = [0x1000 + 2 * i for i, w in enumerate(words) if w & 0x3FFF == X_MARKER]
        return ys, xs

    def open_menu(self):
        self.press("START", frames=6)
        ok = self.wait_for(lambda: self.r(MENU) == ITEMS_PAGE, 4.0)
        time.sleep(0.4)
        return ok

    def close_menu(self, button="START"):
        self.press(button, frames=6)
        return self.wait_play(6.0)

    def move_to(self, item, direction, tries=24):
        for _ in range(tries):
            if self.r(Y_ITEM) == item:
                return True
            self.press(direction, frames=4)
            time.sleep(0.15)
        return self.r(Y_ITEM) == item

    def tap(self, button):
        self.press(button, frames=4)
        time.sleep(0.35)

    def scenario(self):
        # Declared fixture: inventory and a clean binding start only.
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(BOOMERANG, 1); self.w(HOOKSHOT, 1)
        self.w(BOTTLE1, 2)
        self.w(Y_ITEM, 2)
        self.w(SAVED_VERSION, 0); self.w(SAVED_Y, 0); self.w(SAVED_X, 0)
        for a in (CURSOR, LOGICAL, BUTTON_ACTION, BUTTON):
            self.w(a, 0)
        time.sleep(0.2)
        self.snap("fixture")

        # 1. Open on Boomerang, X binds X.
        self.check("menu_opened", self.open_menu())
        s = self.snap("menu_open")
        self.check("open_on_boomerang", s["y_item"] == 2 and s["menu_y"] == 2)
        self.tap("X")
        s = self.snap("X_on_boomerang")
        self.check("X_bound_boomerang", s["saved"][0] == 1 and s["saved"][2] == 2 and s["menu"] == ITEMS_PAGE)

        # 2. Move to Bow: no equip on move. Y binds Y.
        self.check("cursor_reached_bow", self.move_to(1, "LEFT"))
        s = self.snap("cursor_on_bow")
        self.check("move_does_not_equip", s["menu_y"] == 2)
        self.tap("Y")
        s = self.snap("Y_on_bow")
        self.check("Y_bound_bow", s["menu_y"] == 1 and s["menu"] == ITEMS_PAGE)
        ys, xs = self.markers()
        print(f"    markers Y={[hex(a) for a in ys]} X={[hex(a) for a in xs]}")
        # Bow and Boomerang are neighbors: they share one corner column, X shows there.
        if self.codex:  # one corner each: Y on Bow (cursor cell), X on Boomerang
            self.check("Y_green_corners_X_blue_corners", len(ys) == 1 and len(xs) == 1)
        else:
            self.check("Y_green_corners_X_blue_corners", len(ys) == 2 and len(xs) == 4)
        self.take_screenshot("01_markers_Y_bow_X_boomerang")

        # 3. X on Bottle (Y-only) is refused.
        self.check("cursor_reached_bottle", self.move_to(6, "RIGHT"))
        self.tap("X")
        s = self.snap("X_on_bottle")
        self.check("X_refused_unsupported", s["saved"][2] == 2 and s["menu"] == ITEMS_PAGE)

        # 4. X on Boomerang again clears X, then binds again.
        self.check("cursor_reached_boomerang", self.move_to(2, "LEFT"))
        self.tap("X")
        s = self.snap("X_again_clears")
        ys, xs = self.markers()
        self.check("X_cleared_no_X_marker", s["saved"][2] == 0 and len(xs) == 0
                   and len(ys) == (1 if self.codex else 4))
        self.take_screenshot("02_X_cleared")
        self.tap("X")
        s = self.snap("X_rebound")
        self.check("X_rebound_boomerang", s["saved"][2] == 2)

        # 5. Close: the Y item returns to $0202.
        self.check("menu_closed_start", self.close_menu("START"))
        # Gameplay mirrors $0202 into saved Y on the next idle frame.
        mirrored = self.wait_for(lambda: self.r(SAVED_Y) == 1, 2.0)
        s = self.snap("closed")
        self.check("closed_state", mirrored and s["y_item"] == 1 and s["saved"] == [1, 1, 2])
        self.take_screenshot("03_hud_after_close")

        # 6. Gameplay use of both buttons.
        self.press("Y", frames=4)
        self.check("Y_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.wait_for(lambda: self.r(BUTTON) == 0 and not self.has(ARROW_ID), 6.0)
        self.press("X", frames=4)
        thrown = self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5)
        s = self.snap("gameplay_X")
        self.check("X_throws_boomerang_no_map", thrown and s["module"] != MAP_MODULE)
        self.check("gameplay_saved", s["y_item"] == 1 and s["saved"] == [1, 1, 2])
        self.take_screenshot("04_boomerang_from_X")
        self.wait_for(lambda: self.r(BUTTON) == 0 and not self.has(BOOMERANG_ID), 6.0)

        # 7. A never binds.
        self.check("menu_reopened", self.open_menu())
        self.check("cursor_reached_boomerang_2", self.move_to(2, "RIGHT"))
        self.check("menu_closed_A", self.close_menu("A"))
        time.sleep(0.4)
        s = self.snap("closed_with_A")
        self.check("A_does_not_bind", s["y_item"] == 1 and s["saved"] == [1, 1, 2])

        # 8. One item on both buttons: both markers side by side.
        self.check("menu_reopened_2", self.open_menu())
        self.check("cursor_reached_boomerang_3", self.move_to(2, "RIGHT"))
        self.tap("Y")
        ys, xs = self.markers()
        s = self.snap("Y_and_X_on_boomerang")
        print(f"    markers Y={[hex(a) for a in ys]} X={[hex(a) for a in xs]}")
        if self.codex:  # same cell: Y top-left $1108+X, X bottom-right $11CE+X
            self.check("both_markers_side_by_side",
                       s["menu_y"] == 2 and len(ys) == 1 and len(xs) == 1 and xs[0] == ys[0] + 0xC6)
        else:
            self.check("both_markers_side_by_side",
                       s["menu_y"] == 2 and len(ys) == 2 and len(xs) == 2 and min(xs) == min(ys) + 6)
        self.take_screenshot("05_both_markers_one_item")
        self.check("menu_closed_end", self.close_menu("START"))
        s = self.snap("end")
        self.check("end_Y_boomerang", s["y_item"] == 2)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=deku.APP_DEFAULT)
    ap.add_argument("--codex", action="store_true", help="ROM built with hud_layout_codex")
    args = ap.parse_args()
    t = MenuAssignTest(args.rom, args.app, args.work, codex=args.codex)
    result = {"rom": str(args.rom), "status": "ERROR"}
    try:
        t.launch()
        t.boot_file2()
        t.scenario()
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
