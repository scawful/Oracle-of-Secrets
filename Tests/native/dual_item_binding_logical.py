#!/usr/bin/env python3
"""Native proof: logical-cell items on X (Portal, Goldstar, Bombchu, Switch Hook).

Dual-item binding and the 2-item HUD layout are default-on. Launches
its own private headless Mesen2-OOS (never oos-rc-play). Companion to
dual_item_binding_states.py.

X and Y may now share an action routine: the routine's variant read goes
through ItemBindings_EffectiveItem, so each button fires its own item.

Declared fixture writes (unearned inventory/bindings, not acquisition proof):
Bow 2 + 30 arrows, Hookshot 1, Goldstar 1, Portal Rod 1, Switch Hook 1,
Bombchu 1 + 10 ammo, 10 bombs, full magic, and the binding bytes.

Cases (real controller input after each fixture):
1. goldstar_x: Y = Hookshot, X = Goldstar. X launches with the Goldstar
   latch (2); Y then launches with the Hookshot latch (1).
2. bombchu_x: Y = Bombs, X = Bombchu. X sends a Bombchu (slot set, ammo
   debited, bombs kept); Y then places a normal bomb.
3. bombs_x: Y = Bombchu, X = Bombs. X places a normal bomb (bombs debited,
   Bombchu ammo kept, no Bombchu slot).
4. portal_x: Y = Bow, X = Portal Rod. X spawns a portal sprite (type $03,
   state 9); Y then fires an arrow.
5. switch_hook_x: Y = Bow, X = Switch Hook. X launches a hook shot with the
   Switch Hook snapshot active ($07F8 = $A5) and the Hookshot latch.
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

Y_ITEM, BUTTON = base.Y_ITEM, base.BUTTON
CURSOR, LOGICAL, BUTTON_ACTION = base.CURSOR, base.LOGICAL, base.BUTTON_ACTION
SAVED_VERSION, SAVED_Y, SAVED_X = base.SAVED_VERSION, base.SAVED_Y, base.SAVED_X
BOW, ARROWS = base.BOW, base.ARROWS
HOOKSHOT, BOMBS, MAGIC = 0x7EF342, 0x7EF343, 0x7EF36E
PORTAL_OWNED, GOLDSTAR_OWNED, BOMBCHU_OWNED, SWITCH_HOOK_OWNED = 0x7EF3A6, 0x7EF3A9, 0x7EF3AD, 0x7EF3AE
BOMBCHU_AMMO, BOMBCHU_SLOT = 0x7EF3B0, 0x7E07F1
GOLDSTAR_LATCH = 0x7E1E79          # GoldstarOrHookshot: 1 hookshot, 2 goldstar
SWITCH_HOOK_ACTIVE, SWITCH_HOOK_TAG = 0x7E07F8, 0xA5
SPR_STATE, SPR_KIND = 0x7E0DD0, 0x7E0E20
ARROW_ID, BOMB_ID, HOOK_ANC = 0x09, 0x07, 0x1F
ID_BOW, ID_HOOKSHOT, ID_BOMBS = 1, 3, 4
ID_PORTAL, ID_GOLDSTAR, ID_BOMBCHU, ID_SWITCH_HOOK = 0x19, 0x1A, 0x1C, 0x1D


class LogicalTest(base.DualItemBindingTest):
    def inventory(self):
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(HOOKSHOT, 1); self.w(BOMBS, 10)
        self.w(MAGIC, 0x80)
        for a in (PORTAL_OWNED, GOLDSTAR_OWNED, BOMBCHU_OWNED, SWITCH_HOOK_OWNED):
            self.w(a, 1)
        self.w(BOMBCHU_AMMO, 10)

    def bindings(self, y_item, x_item):
        self.inventory()
        self.w(Y_ITEM, y_item)
        self.w(SAVED_VERSION, 1); self.w(SAVED_Y, y_item); self.w(SAVED_X, x_item)
        for a in (LOGICAL, BUTTON_ACTION, BUTTON):
            self.w(a, 0)
        self.w(CURSOR, y_item)
        time.sleep(0.4)          # let the HUD redraw the X box

    def portals(self):
        return sum(self.r(SPR_STATE + i) == 9 and self.r(SPR_KIND + i) == 3 for i in range(16))

    def settle(self, timeout=8.0):
        self.wait_for(lambda: self.r(BUTTON) == 0 and self.r(BOMBCHU_SLOT) == 0 and
                      not any(self.r(base.ANCILLA + i) in (ARROW_ID, BOMB_ID, HOOK_ANC) for i in range(5)),
                      timeout)
        time.sleep(0.3)

    # 1 ---------------------------------------------------------------
    def goldstar_x(self):
        self.bindings(ID_HOOKSHOT, ID_GOLDSTAR)
        self.take_screenshot("20_goldstar_x_hud")
        self.b.press_button("x", frames=4, detach_debugger=False)
        ok = self.wait_for(lambda: self.has(HOOK_ANC) and self.r(GOLDSTAR_LATCH) == 2, 1.5)
        self.snap("goldstar_after_X")
        self.check("goldstar_X_launches_goldstar", ok)
        self.settle()
        self.b.press_button("y", frames=4, detach_debugger=False)
        ok = self.wait_for(lambda: self.has(HOOK_ANC) and self.r(GOLDSTAR_LATCH) == 1, 1.5)
        s = self.snap("goldstar_after_Y")
        self.check("goldstar_Y_launches_hookshot", ok and s["y_item"] == ID_HOOKSHOT)
        self.settle()

    # 2 ---------------------------------------------------------------
    def bombchu_x(self):
        self.bindings(ID_BOMBS, ID_BOMBCHU)
        self.take_screenshot("21_bombchu_x_hud")
        bombs, ammo = self.r(BOMBS), self.r(BOMBCHU_AMMO)
        self.b.press_button("x", frames=4, detach_debugger=False)
        sent = self.wait_for(lambda: self.r(BOMBCHU_SLOT) != 0, 1.5)
        self.snap("bombchu_after_X")
        self.check("bombchu_X_sends_bombchu",
                   sent and self.r(BOMBCHU_AMMO) == ammo - 1 and self.r(BOMBS) == bombs)
        self.settle()
        bombs, ammo = self.r(BOMBS), self.r(BOMBCHU_AMMO)
        self.b.press_button("y", frames=4, detach_debugger=False)
        placed = self.wait_for(lambda: self.r(BOMBS) == bombs - 1, 1.5)
        self.snap("bombchu_after_Y")
        self.check("bombchu_Y_places_bomb",
                   placed and self.r(BOMBCHU_AMMO) == ammo and self.r(BOMBCHU_SLOT) == 0)
        self.settle()

    # 3 ---------------------------------------------------------------
    def bombs_x(self):
        self.bindings(ID_BOMBCHU, ID_BOMBS)
        self.take_screenshot("22_bombs_x_hud")
        bombs, ammo = self.r(BOMBS), self.r(BOMBCHU_AMMO)
        self.b.press_button("x", frames=4, detach_debugger=False)
        placed = self.wait_for(lambda: self.r(BOMBS) == bombs - 1, 1.5)
        s = self.snap("bombs_after_X")
        self.check("bombs_X_places_bomb",
                   placed and self.has(BOMB_ID) and self.r(BOMBCHU_AMMO) == ammo
                   and self.r(BOMBCHU_SLOT) == 0 and s["y_item"] == ID_BOMBCHU)
        self.settle()

    # 4 ---------------------------------------------------------------
    def portal_x(self):
        self.bindings(ID_BOW, ID_PORTAL)
        self.take_screenshot("23_portal_x_hud")
        before = self.portals()
        self.b.press_button("x", frames=4, detach_debugger=False)
        ok = self.wait_for(lambda: self.portals() > before, 2.0)
        self.snap("portal_after_X")
        self.check("portal_X_spawns_portal", ok)
        self.settle()
        self.b.press_button("y", frames=4, detach_debugger=False)
        self.check("portal_Y_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.settle()

    # 5 ---------------------------------------------------------------
    def switch_hook_x(self):
        self.bindings(ID_BOW, ID_SWITCH_HOOK)
        self.take_screenshot("24_switch_hook_x_hud")
        self.b.press_button("x", frames=4, detach_debugger=False)
        ok = self.wait_for(lambda: self.has(HOOK_ANC) and self.r(SWITCH_HOOK_ACTIVE) == SWITCH_HOOK_TAG
                           and self.r(GOLDSTAR_LATCH) == 1, 1.5)
        self.snap("switch_hook_after_X")
        self.check("switch_hook_X_launches", ok)
        self.settle()
        self.check("switch_hook_X_released", self.r(BUTTON) == 0)
        self.b.press_button("y", frames=4, detach_debugger=False)
        self.check("switch_hook_Y_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.settle()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=deku.APP_DEFAULT)
    args = ap.parse_args()
    t = LogicalTest(args.rom, args.app, args.work)
    result = {"rom": str(args.rom), "status": "ERROR"}
    try:
        t.launch()
        t.boot_file2()
        for case in (t.goldstar_x, t.bombchu_x, t.bombs_x, t.portal_x, t.switch_hook_x):
            print(f"  case {case.__name__}")
            case()
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
