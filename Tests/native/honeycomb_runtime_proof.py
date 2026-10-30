#!/usr/bin/env python3
"""Focused owned-runtime proof for Honeycomb Nimbus bee-swarm, bottle bees, and Windmill Guy multiplexing.

Verifies natively in headless Mesen2:
1. Windmill Guy preservation:
   - Windmill Guy ($0E20=$B2, $0D80=0, $0EB0=0) executes NPC routine ($309119 -> Race Game Lady / dialogue),
     setting SprMiscC=1, without executing bee AI or despawning.
2. Ordinary bottle bee release:
   - Releasing an Ordinary Bee ($07) from Bottle 1 empties the bottle to $02.
   - Spawned bee routes as PlayerBee ($0D80=1), but retains Ordinary Bee subtype ($0EB0=0).
   - Windmill Guy in slot 0 remains untouched.
3. Good Bee bottle release:
   - Releasing a Good Bee ($08) from Bottle 1 empties the bottle to $02.
   - Spawned bee routes as PlayerBee ($0D80=1), and sets Good Bee subtype ($0EB0=1).
   - Windmill Guy in slot 0 remains untouched.
4. Swarm activation in presence of Windmill Guy:
   - Honeycomb activation in Windmill Guy's presence is accepted (Windmill Guy is not treated as a bee).
   - Menu queues deferred action, scrolls up and returns to gameplay.
   - Exactly 3 Good Bees spawn ($0E20=$B2, $0D80=1, $0EB0=1).
   - Inventory decrements: exactly 1 Honeycomb spent ($7EF393: 2 -> 1).
   - Windmill Guy remains untouched while swarm spawns alongside him.
5. Attacking bees:
   - Bees acquire enemy target in room and damage/destroy enemy.
6. Active swarm refusal:
   - While bees are active, Honeycomb activation is refused.
   - Menu remains open (no scroll-up/exit), pending remains 0, inventory count preserved.
7. Slot pressure refusal:
   - When fewer than 3 sprite slots are free (< 3 free slots), Honeycomb activation is refused.
   - Menu remains open, pending remains 0, inventory count preserved.
8. Bottle preservation:
   - Bottles are untouched during Honeycomb usage.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "Scripts" / "Mesen2"))
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402

LAUNCHER = REPO / "Scripts" / "Mesen2" / "mesen2_launch_instance.sh"
APP_DEFAULT = Path("/Applications/Mesen2 OOS.app")
SAVE_DEFAULT = REPO / "Roms" / "SaveStates" / "oos168x" / "oos168x.srm"

MODULE, SUBMODULE = 0x7E0010, 0x7E0011
MENU, CURSOR, PAGE = 0x7E0200, 0x7E020B, 0x7E1E71
HONEYCOMB_COUNT = 0x7EF393
PENDING_SUPPLY = 0x7E0434
BOTTLE_1 = 0x7EF35C
BOTTLE_INDEX = 0x7EF34F
EQUIPPED_Y = 0x7E0202

SPR_STATUS = 0x7E0DD0
SPR_ACTION = 0x7E0D80   # $0D80,X (route identity: 0=Windmill Guy, 1=active bee)
SPR_ID = 0x7E0E20
SPR_GOODBEE = 0x7E0EB0  # $0EB0,X (Good Bee subtype: 0=Ordinary Bee, 1=Good Bee)
SPR_MISCC = 0x7E0DE0    # $0DE0,X
SPR_HITBOX = 0x7E0E40
SPR_HEALTH = 0x7E0E50
SPR_YL = 0x7E0D00
SPR_YH = 0x7E0D20
SPR_XL = 0x7E0D10
SPR_XH = 0x7E0D30
SPR_FLOOR = 0x7E0F20
SPR_FLAGS4 = 0x7E0CAA   # persist bit $80


def identity(pid: int) -> str:
    return subprocess.run(
        ["ps", "-o", "lstart=,command=", "-p", str(pid)],
        text=True, capture_output=True, check=False,
    ).stdout.strip()


class HoneycombRuntimeTest:
    def __init__(self, rom_path: Path, app_path: Path, work_dir: Path):
        self.rom = rom_path
        self.app = app_path
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)

        self.instance_name = f"honeycomb-test-{int(time.time())}"
        self.sock = self.work_dir / f"mesen-{self.instance_name}.sock"
        self.home = self.work_dir / "profile"
        self.rom_copy = self.work_dir / "honeycomb_candidate.sfc"
        shutil.copy2(self.rom, self.rom_copy)

        (self.home / "Saves").mkdir(parents=True, exist_ok=True)
        shutil.copy2(SAVE_DEFAULT, self.home / "Saves" / "honeycomb_candidate.srm")

        self.pid = 0
        self.pid_identity = ""
        self.b: MesenBridge | None = None
        self.results: dict[str, bool] = {}

    def launch(self):
        cmd = [
            "taskpolicy", "-b", "nice", "-n", "10", "bash", str(LAUNCHER),
            "--headless", "--no-copy-settings", "--no-save-settings",
            "--no-seed-project-states", "--no-state-set", "--no-register",
            "--instance", self.instance_name, "--home", str(self.home),
            "--socket", str(self.sock), "--rom", str(self.rom_copy),
            "--app", str(self.app),
        ]
        with (self.work_dir / "launch.log").open("w") as log:
            subprocess.run(cmd, cwd=REPO, stdout=log, stderr=log, check=True, timeout=30)

        for _ in range(80):
            if self.sock.exists():
                break
            time.sleep(0.25)
        if not self.sock.exists():
            raise RuntimeError(f"Socket {self.sock} did not appear")

        pids = subprocess.run(["lsof", "-t", str(self.sock)], text=True, capture_output=True).stdout.split()
        owned = [int(p) for p in pids if p.isdigit() and str(self.rom_copy) in identity(int(p))]
        if len(owned) != 1:
            raise RuntimeError(f"Cannot identify owned emulator PID: {pids}")
        self.pid = owned[0]
        self.pid_identity = identity(self.pid)
        self.b = MesenBridge(str(self.sock))
        print(f"[*] Attached to emulator PID {self.pid} on {self.sock}")

    def close(self):
        if self.pid and identity(self.pid) == self.pid_identity:
            os.kill(self.pid, signal.SIGTERM)
            for _ in range(50):
                if identity(self.pid) != self.pid_identity:
                    print(f"[*] Emulator PID {self.pid} exited cleanly")
                    break
                time.sleep(0.1)
        if self.sock.exists():
            self.sock.unlink(missing_ok=True)

    def r(self, addr: int) -> int:
        return self.b.read_memory(addr)

    def w(self, addr: int, val: int):
        self.b.write_memory(addr, val)

    def press(self, button: str, frames: int = 10):
        if not self.b.press_button(button, frames=frames):
            raise RuntimeError(f"press failed: {button}")
        time.sleep((frames + 8) / 60)

    def wait_play(self, timeout: float = 10.0) -> bool:
        end = time.time() + timeout
        while time.time() < end:
            if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                time.sleep(0.3)
                if self.r(MODULE) in (7, 9) and self.r(SUBMODULE) == 0:
                    return True
            time.sleep(0.1)
        return False

    def boot_file2(self):
        print("[*] Loading gameplay baseline state...")
        time.sleep(2)
        state_path = REPO / "Roms" / "SaveStates" / "library" / "oos_1772076682_Agent_Gameplay_Baseline_Fresh.mss"
        if not state_path.is_file():
            state_path = REPO / "Roms" / "SaveStates" / "oos168x" / "oos168x_1.mss"
        res = self.b.load_state(path=str(state_path))
        print(f"[*] load_state result: {res}")
        time.sleep(0.5)
        if not self.wait_play(8.0):
            raise RuntimeError(f"Failed to reach gameplay after load_state (MODULE={self.r(MODULE)}, SUBMODULE={self.r(SUBMODULE)})")
        print(f"[+] Reached stable gameplay: MODULE={self.r(MODULE)}")

    def navigate_to_equipment(self) -> bool:
        """Opens menu and navigates cleanly to the Equipment page (menu state 6)."""
        self.press("START", frames=10)
        # Wait for menu state 4 (Item screen active)
        for _ in range(50):
            if self.r(MENU) == 4:
                break
            time.sleep(0.05)
        if self.r(MENU) != 4:
            return False

        # Switch to Equipment page
        self.press("L", frames=10)
        # Wait for menu state 6 (Equipment screen active)
        for _ in range(50):
            if self.r(MENU) == 6:
                break
            time.sleep(0.05)
        return self.r(MENU) == 6

    def run_tests(self):
        # Fixture setup
        self.w(HONEYCOMB_COUNT, 2)
        self.w(PENDING_SUPPLY, 0)
        self.w(BOTTLE_1, 2)  # Bottle 1 is empty bottle ($02)

        link_y = self.r(0x7E0020) | (self.r(0x7E0021) << 8)
        link_x = self.r(0x7E0022) | (self.r(0x7E0023) << 8)
        floor = self.r(0x7E00EE)

        # Clear sprite slots 0..15
        for s in range(16):
            self.w(SPR_STATUS + s, 0)
            self.w(SPR_ID + s, 0)
            self.w(SPR_ACTION + s, 0)
            self.w(SPR_GOODBEE + s, 0)

        # ----------------------------------------------------
        # 1. Windmill Guy preservation test
        # ----------------------------------------------------
        print("[*] Test 1: Windmill Guy NPC execution & preservation...")
        # Slot 0: Windmill Guy ($B2, state 9, $0D80=0, $0EB0=0) positioned near Link with persist flag
        self.w(SPR_ID + 0, 0xB2)
        self.w(SPR_STATUS + 0, 9)
        self.w(SPR_ACTION + 0, 0)
        self.w(SPR_GOODBEE + 0, 0)
        self.w(SPR_MISCC + 0, 0)
        self.w(SPR_YL + 0, link_y & 0xFF)
        self.w(SPR_YH + 0, (link_y >> 8) & 0xFF)
        self.w(SPR_XL + 0, (link_x + 32) & 0xFF)
        self.w(SPR_XH + 0, ((link_x + 32) >> 8) & 0xFF)
        self.w(SPR_FLOOR + 0, floor)
        self.w(SPR_FLAGS4 + 0, 0x80)

        # Let frames run naturally so Windmill Guy executes Sprite_WindmillGuy_Long
        time.sleep(0.6)

        # Windmill Guy should have executed Sprite_WindmillGuy_Long -> set SprMiscC=1, action=0, goodbee=0
        status0 = self.r(SPR_STATUS + 0)
        id0 = self.r(SPR_ID + 0)
        action0 = self.r(SPR_ACTION + 0)
        goodbee0 = self.r(SPR_GOODBEE + 0)
        miscc0 = self.r(SPR_MISCC + 0)
        t1_ok = (status0 == 9 and id0 == 0xB2 and action0 == 0 and goodbee0 == 0 and miscc0 == 1)
        self.results["windmill_guy_preserved"] = t1_ok
        print(f"    Windmill Guy status={status0}, id=0x{id0:02X}, action={action0}, goodbee={goodbee0}, miscc={miscc0} -> OK: {t1_ok}")

        # ----------------------------------------------------
        # 2. Ordinary bottled bee release test
        # ----------------------------------------------------
        print("[*] Test 2: Ordinary bottle bee release (subtype 0 preserved)...")
        # Put Ordinary Bee ($07) into Bottle 1 and equip as Y item
        self.w(BOTTLE_1, 0x07)
        self.w(BOTTLE_INDEX, 1)
        self.w(EQUIPPED_Y, 6)   # Bottle 1 slot
        time.sleep(0.1)

        # Press Y to release Ordinary Bee
        self.press("Y", frames=10)
        time.sleep(0.8)

        bottle_after_ord = self.r(BOTTLE_1)
        ord_bee_slot = None
        ord_bee_action = None
        ord_bee_subtype = None
        for s in range(1, 16):
            if self.r(SPR_STATUS + s) != 0 and self.r(SPR_ID + s) == 0xB2:
                ord_bee_slot = s
                ord_bee_action = self.r(SPR_ACTION + s)
                ord_bee_subtype = self.r(SPR_GOODBEE + s)
                break

        wmg_alive_ord = (self.r(SPR_STATUS + 0) == 9 and self.r(SPR_ID + 0) == 0xB2 and self.r(SPR_ACTION + 0) == 0 and self.r(SPR_GOODBEE + 0) == 0)
        t2_ok = (bottle_after_ord == 2 and ord_bee_slot is not None and ord_bee_action == 1 and ord_bee_subtype == 0 and wmg_alive_ord)
        self.results["ordinary_bottle_bee_release"] = t2_ok
        print(f"    Ordinary bee release: bottle={bottle_after_ord} (expected 2), bee slot={ord_bee_slot}, action={ord_bee_action} (expected 1), subtype={ord_bee_subtype} (expected 0), WMG={wmg_alive_ord} -> OK: {t2_ok}")

        # Clear released bee from slot
        if ord_bee_slot is not None:
            self.w(SPR_STATUS + ord_bee_slot, 0)

        # ----------------------------------------------------
        # 3. Good Bee bottle release test
        # ----------------------------------------------------
        print("[*] Test 3: Good Bee bottle release (subtype 1 preserved)...")
        # Put Good Bee ($08) into Bottle 1 and equip as Y item
        self.w(BOTTLE_1, 0x08)
        self.w(BOTTLE_INDEX, 1)
        self.w(EQUIPPED_Y, 6)
        time.sleep(0.1)

        # Press Y to release Good Bee
        self.press("Y", frames=10)
        time.sleep(0.8)

        bottle_after_good = self.r(BOTTLE_1)
        good_bee_slot = None
        good_bee_action = None
        good_bee_subtype = None
        for s in range(1, 16):
            if self.r(SPR_STATUS + s) != 0 and self.r(SPR_ID + s) == 0xB2:
                good_bee_slot = s
                good_bee_action = self.r(SPR_ACTION + s)
                good_bee_subtype = self.r(SPR_GOODBEE + s)
                break

        wmg_alive_good = (self.r(SPR_STATUS + 0) == 9 and self.r(SPR_ID + 0) == 0xB2 and self.r(SPR_ACTION + 0) == 0 and self.r(SPR_GOODBEE + 0) == 0)
        t3_ok = (bottle_after_good == 2 and good_bee_slot is not None and good_bee_action == 1 and good_bee_subtype == 1 and wmg_alive_good)
        self.results["good_bottle_bee_release"] = t3_ok
        print(f"    Good bee release: bottle={bottle_after_good} (expected 2), bee slot={good_bee_slot}, action={good_bee_action} (expected 1), subtype={good_bee_subtype} (expected 1), WMG={wmg_alive_good} -> OK: {t3_ok}")

        # Clear released bee from slot
        if good_bee_slot is not None:
            self.w(SPR_STATUS + good_bee_slot, 0)

        # ----------------------------------------------------
        # 4. Swarm activation in presence of Windmill Guy
        # ----------------------------------------------------
        print("[*] Test 4: Honeycomb activation in presence of Windmill Guy...")
        # Link has 2 Honeycombs
        self.w(HONEYCOMB_COUNT, 2)
        self.w(PENDING_SUPPLY, 0)

        if not self.navigate_to_equipment():
            raise RuntimeError(f"Failed to navigate to Equipment screen (MENU={self.r(MENU)})")

        # Select Honeycomb (cursor 19)
        self.w(CURSOR, 19)
        time.sleep(0.1)

        # Press A on Honeycomb: queues exit action and scrolls menu up
        self.press("A", frames=10)

        # Wait for menu to scroll up and return to stable gameplay
        if not self.wait_play(8.0):
            print(f"    [!] Warning: menu did not return to gameplay (MODULE={self.r(MODULE)})")

        # Verify exit action deployed:
        # Exactly 1 Honeycomb spent: 2 -> 1
        count_after = self.r(HONEYCOMB_COUNT)
        # Windmill Guy still alive in slot 0
        wmg_alive = (self.r(SPR_STATUS + 0) == 9 and self.r(SPR_ID + 0) == 0xB2 and self.r(SPR_ACTION + 0) == 0 and self.r(SPR_GOODBEE + 0) == 0)

        # Count spawned bees ($B2 with action 1 and Good Bee subtype 1)
        bee_slots = []
        for s in range(1, 16):
            if self.r(SPR_STATUS + s) != 0 and self.r(SPR_ID + s) == 0xB2 and self.r(SPR_ACTION + s) == 1 and self.r(SPR_GOODBEE + s) == 1:
                bee_slots.append(s)

        t4_ok = (count_after == 1 and wmg_alive and len(bee_slots) == 3)
        self.results["swarm_deployed_with_wmg"] = t4_ok
        print(f"    Honeycomb count={count_after} (expected 1), WMG alive={wmg_alive}, bee_slots={bee_slots} -> OK: {t4_ok}")

        # ----------------------------------------------------
        # 5. Attacking bees: target acquisition & damage
        # ----------------------------------------------------
        print("[*] Test 5: Attacking bees damage enemy target...")
        target_slot = 5
        self.w(SPR_ID + target_slot, 0x05)    # Octorok
        self.w(SPR_STATUS + target_slot, 9)
        self.w(SPR_HITBOX + target_slot, 0)   # Harmful enemy
        self.w(SPR_HEALTH + target_slot, 16)  # 16 HP
        self.w(SPR_YL + target_slot, (link_y + 16) & 0xFF)
        self.w(SPR_YH + target_slot, ((link_y + 16) >> 8) & 0xFF)
        self.w(SPR_XL + target_slot, (link_x + 8) & 0xFF)
        self.w(SPR_XH + target_slot, ((link_x + 8) >> 8) & 0xFF)
        self.w(SPR_FLOOR + target_slot, floor)
        self.w(SPR_FLAGS4 + target_slot, 0x80)

        initial_hp = self.r(SPR_HEALTH + target_slot)
        # Let bees attack
        damaged = False
        for _ in range(25):
            time.sleep(0.1)
            hp = self.r(SPR_HEALTH + target_slot)
            st = self.r(SPR_STATUS + target_slot)
            if hp < initial_hp or st != 9:
                damaged = True
                break

        final_hp = self.r(SPR_HEALTH + target_slot)
        final_status = self.r(SPR_STATUS + target_slot)
        self.results["bees_attack_target"] = damaged
        print(f"    Target enemy initial_hp={initial_hp}, final_hp={final_hp}, status={final_status} -> Damaged: {damaged}")

        # ----------------------------------------------------
        # 6. Active swarm refusal
        # ----------------------------------------------------
        print("[*] Test 6: Active swarm refusal preserves inventory...")
        # Give Link 1 Honeycomb to test repeated consumption
        self.w(HONEYCOMB_COUNT, 1)

        # While bees are actively buzzing, open menu to Equipment
        if not self.navigate_to_equipment():
            raise RuntimeError(f"Failed to navigate to Equipment screen (MENU={self.r(MENU)})")

        self.w(CURSOR, 19)
        time.sleep(0.1)

        # Press A: should be REFUSED because bees are currently active!
        self.press("A", frames=10)
        time.sleep(0.5)

        # Verify refused: menu did NOT scroll up (remains at state 6), pending is 0, count is 1
        menu_state = self.r(MENU)
        pending_after = self.r(PENDING_SUPPLY)
        count_pres = self.r(HONEYCOMB_COUNT)

        t6_ok = (menu_state == 6 and pending_after == 0 and count_pres == 1)
        self.results["active_swarm_refused"] = t6_ok
        print(f"    Active swarm refusal: MENU={menu_state} (expected 6), pending={pending_after}, count={count_pres} -> OK: {t6_ok}")

        # Close menu
        self.press("START", frames=10)
        self.wait_play(5.0)

        # ----------------------------------------------------
        # 7. Slot pressure refusal
        # ----------------------------------------------------
        print("[*] Test 7: Slot pressure refusal (<3 free slots)...")
        # Despawn all existing sprites except slot 0
        for s in range(16):
            self.w(SPR_STATUS + s, 0)

        # Fill 15 slots (slots 0..14) so at most 1-2 slots remain free
        for s in range(15):
            self.w(SPR_STATUS + s, 9)
            self.w(SPR_ID + s, 0x05)
            self.w(SPR_ACTION + s, 0)
            self.w(SPR_GOODBEE + s, 0)
            self.w(SPR_YL + s, (link_y + 30) & 0xFF)
            self.w(SPR_YH + s, ((link_y + 30) >> 8) & 0xFF)
            self.w(SPR_XL + s, (link_x + 30) & 0xFF)
            self.w(SPR_XH + s, ((link_x + 30) >> 8) & 0xFF)
            self.w(SPR_FLOOR + s, floor)
            self.w(SPR_FLAGS4 + s, 0x80)

        self.w(HONEYCOMB_COUNT, 1)
        self.w(PENDING_SUPPLY, 0)

        # Open menu -> Equipment
        if not self.navigate_to_equipment():
            raise RuntimeError(f"Failed to navigate to Equipment screen (MENU={self.r(MENU)})")

        self.w(CURSOR, 19)
        time.sleep(0.1)

        # Press A: should be REFUSED because only 1-2 slots are free (< 3)
        self.press("A", frames=10)
        time.sleep(0.5)

        menu_slot = self.r(MENU)
        pend_slot = self.r(PENDING_SUPPLY)
        count_slot = self.r(HONEYCOMB_COUNT)

        t7_ok = (menu_slot == 6 and pend_slot == 0 and count_slot == 1)
        self.results["slot_pressure_refused"] = t7_ok
        print(f"    Slot pressure refusal: MENU={menu_slot} (expected 6), pending={pend_slot}, count={count_slot} -> OK: {t7_ok}")

        # Close menu
        self.press("START", frames=10)
        self.wait_play(5.0)

        # ----------------------------------------------------
        # 8. Bottle preservation
        # ----------------------------------------------------
        print("[*] Test 8: Bottle inventory preservation...")
        b1_val = self.r(BOTTLE_1)
        t8_ok = (b1_val == 2)  # Remained empty bottle ($02)
        self.results["bottle_preserved"] = t8_ok
        print(f"    Bottle 1 contents = 0x{b1_val:02X} (expected 0x02) -> OK: {t8_ok}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("/tmp/oos_private_honeycomb.sfc"))
    parser.add_argument("--app", type=Path, default=APP_DEFAULT)
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/oos_honeycomb_runtime"))
    args = parser.parse_args()

    test = HoneycombRuntimeTest(args.rom, args.app, args.work_dir)
    try:
        test.launch()
        test.boot_file2()
        test.run_tests()
    finally:
        test.close()

    print("\n" + "=" * 50)
    print("HONEYCOMB RUNTIME PROOF SUMMARY:")
    all_passed = True
    for name, passed in test.results.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            all_passed = False
    print("=" * 50)

    report_path = args.work_dir / "honeycomb_runtime_report.json"
    report_path.write_text(json.dumps(dict(
        passed=all_passed,
        results=test.results,
        rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest(),
    ), indent=2))
    print(f"[*] Report saved to {report_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
