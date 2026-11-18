#!/usr/bin/env python3
"""Focused native proof for the dual-item binding prototype (Bow on Y, Boomerang on X).

Dual-item binding is default-on. Launches its own
private headless Mesen2-OOS (never oos-rc-play) from the gameplay baseline state.

Declared fixture writes (unearned inventory/bindings, not acquisition proof):
Bow level 2 + 30 arrows, Boomerang level 1, $0202=Bow, saved bindings
version 1 / Y=Bow / X=Boomerang, volatile latch cleared.

Scenario (all real controller input):
1. Y fires an arrow; latch Button=1 while busy, then clears.
2. X throws the boomerang without pausing; no field map opens; $0202 stays Bow.
3. Y while the boomerang is in flight is rejected: latch stays X, no arrow,
   $0202/saved bindings unchanged.
4. After the boomerang returns, Y fires an arrow again (switch without pause).
5. Control: with saved X cleared, X opens the native field map.
6. Save & Quit via Game Over, check SRAM bytes $3B9-$3BB and checksum, then a
   fresh process cold-boots the .srm and the bindings route again.
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
Y_ITEM, ACTION, ACTION_LATCH = 0x7E0202, 0x7E0303, 0x7E0304
MASK = 0x7E02B2
CURSOR, LOGICAL, BUTTON_ACTION, BUTTON = 0x7E02B3, 0x7E02B4, 0x7E02B5, 0x7E02B6
SAVED_VERSION, SAVED_Y, SAVED_X = 0x7EF3B9, 0x7EF3BA, 0x7EF3BB
BOW, BOOMERANG, ARROWS = 0x7EF340, 0x7EF341, 0x7EF377
ANCILLA = 0x7E0C4A
ARROW_ID, BOOMERANG_ID = 0x09, 0x05
MAP_MODULE = 0x0E


class DualItemBindingTest(deku.DekuStickRuntimeTest):
    def __init__(self, rom, app, work):
        super().__init__(rom, app, work)
        self.log: list[dict] = []
        self.checks: dict[str, bool] = {}

    def snap(self, label):
        s = dict(label=label, module=self.r(MODULE), sub=self.r(SUBMODULE),
                 y_item=self.r(Y_ITEM), action=self.r(ACTION), latch=self.r(ACTION_LATCH),
                 mask=self.r(MASK), cursor=self.r(CURSOR), logical=self.r(LOGICAL),
                 button_action=self.r(BUTTON_ACTION), button=self.r(BUTTON),
                 saved=[self.r(SAVED_VERSION), self.r(SAVED_Y), self.r(SAVED_X)],
                 ancilla=[self.r(ANCILLA + i) for i in range(5)],
                 arrows=self.r(ARROWS), link_state=self.r(0x7E005D))
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

    def idle(self):
        return self.wait_for(lambda: self.r(BUTTON) == 0 and
                             not any(self.r(ANCILLA + i) in (ARROW_ID, BOOMERANG_ID) for i in range(5)),
                             timeout=6.0)

    def fixture(self, x_item=2):
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(BOOMERANG, 1)
        self.w(Y_ITEM, 1)
        self.w(SAVED_VERSION, 1); self.w(SAVED_Y, 1); self.w(SAVED_X, x_item)
        for a in (CURSOR, LOGICAL, BUTTON_ACTION, BUTTON):
            self.w(a, 0)
        time.sleep(0.2)

    def has(self, ident):
        return any(self.r(ANCILLA + i) == ident for i in range(5))

    def scenario(self):
        self.fixture()
        base = self.snap("fixture")
        self.check("base_form", base["mask"] in (0, 6))

        # 1. Y -> arrow
        self.b.press_button("y", frames=4, detach_debugger=False)
        seen_y = self.wait_for(lambda: self.r(BUTTON) == 1, 1.0)
        s = self.snap("after_Y")
        self.check("Y_latched_bow", seen_y and s["button_action"] in (0, 3))
        self.check("Y_fired_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.check("Y_latch_released", self.idle())
        self.take_screenshot("01_bow_on_Y")

        # 2. X -> boomerang, no map
        self.b.press_button("x", frames=4, detach_debugger=False)
        seen_x = self.wait_for(lambda: self.r(BUTTON) == 2, 1.0)
        thrown = self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5)
        s = self.snap("after_X")
        self.check("X_latched_boomerang", seen_x and thrown)
        self.check("X_no_field_map", s["module"] != MAP_MODULE)
        self.check("X_kept_Y_equipment", s["y_item"] == 1 and s["saved"] == [1, 1, 2])
        self.take_screenshot("02_boomerang_on_X")

        # 3. Y during boomerang flight -> rejected
        arrows_before = self.r(ARROWS)
        self.b.press_button("y", frames=4, detach_debugger=False)
        time.sleep(0.15)
        s = self.snap("Y_during_boomerang")
        rejected = (s["button"] == 2 and not self.has(ARROW_ID) and self.r(ARROWS) == arrows_before
                    and s["y_item"] == 1 and s["saved"] == [1, 1, 2])
        self.check("conflict_Y_rejected_state_kept", rejected)
        self.check("X_latch_released", self.idle())

        # 4. Y again after return
        self.b.press_button("y", frames=4, detach_debugger=False)
        self.check("Y_after_X_fires_arrow", self.wait_for(lambda: self.has(ARROW_ID), 1.5))
        self.idle()
        self.snap("after_switch_back")

        # 5. Control: X unassigned -> native map
        self.w(SAVED_X, 0)
        time.sleep(0.1)
        self.b.press_button("x", frames=4, detach_debugger=False)
        opened = self.wait_for(lambda: self.r(MODULE) == MAP_MODULE, 3.0)
        self.snap("control_X_unassigned")
        self.check("control_X_opens_map", opened)
        self.take_screenshot("03_control_map")
        if opened:
            time.sleep(1.5)
            for key in ("x", "x", "b", "start", "a"):
                self.b.press_button(key, frames=6, detach_debugger=False)
                if self.wait_play(4.0):
                    break
            self.check("control_map_closed", self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0)
        self.w(SAVED_X, 2)
        time.sleep(0.2)

    def save_reopen(self):
        self.w(0x7EF3C5, max(self.r(0x7EF3C5), 2))
        hp = self.r(0x7EF36D) or 24
        print(f"    pre-gameover module={self.r(MODULE)} sub={self.r(SUBMODULE)} hp={hp}")
        self.w(0x7EF36D, hp); self.w(0x7E037B, 0); self.w(0x7E0373, hp)
        if not self.wait_for(lambda: self.r(MODULE) == 18 and self.r(SUBMODULE) == 9, 15.0):
            raise RuntimeError("Game Over screen not reached")
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
        print(f"    SRAM slot1 checksum=0x{csum:04X} bindings={saved}")
        self.check("sram_checksum_valid", csum == 0x5A5A)
        self.check("sram_backup_matches", sram[:0x500] == sram[0xF00:0x1400])
        self.check("sram_bindings_saved", saved == [1, 1, 2])
        (self.home / "Saves" / "deku_candidate.srm").write_bytes(sram)
        (self.work_dir / "dual_binding.srm").write_bytes(sram)

        self.close()
        self.launch(reset_save=False)
        self.boot_fresh_file()
        s = self.snap("reopened")
        self.check("reopen_bindings_loaded", s["saved"] == [1, 1, 2] and s["button"] == 0)
        self.w(BOW, 2); self.w(ARROWS, 30); self.w(BOOMERANG, 1); self.w(Y_ITEM, 1)
        time.sleep(0.2)
        self.b.press_button("x", frames=4, detach_debugger=False)
        ok = self.wait_for(lambda: self.has(BOOMERANG_ID), 1.5)
        s = self.snap("reopened_X")
        self.check("reopen_X_throws_boomerang_no_map", ok and s["module"] != MAP_MODULE)
        self.take_screenshot("04_reopened_X")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--work", type=Path, required=True)
    ap.add_argument("--app", type=Path, default=deku.APP_DEFAULT)
    args = ap.parse_args()
    t = DualItemBindingTest(args.rom, args.app, args.work)
    result = {"rom": str(args.rom), "status": "ERROR"}
    try:
        t.launch()
        t.boot_file2()
        t.scenario()
        t.save_reopen()
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
