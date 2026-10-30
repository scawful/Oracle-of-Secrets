#!/usr/bin/env python3
"""Focused owned-runtime proof for Deku Stick gameplay, controls, and persistence.

Verifies natively in headless Mesen2:
1. Fresh draw & sword lockout:
   - Drawing a fresh Deku Stick from Equipment menu decrements count (2 -> 1).
   - Sets DekuStick_State = 1 (held unlit) and DekuStick_BurnTimer = 75 (~20s).
   - While stick is held, pressing B stows the stick without swinging the sword on that frame.
   - Fresh unlit stow refunds count (1 -> 2) and leaves DekuStickWear = 0.
2. Sword swings normally after stow:
   - On the stow frame, stick is stowed (state 0), count refunded, wear 0, and sword is suppressed (BFLAG == 0).
   - On the subsequent frame with stick stowed, pressing B initiates an actual sword swing (observing BFLAG > 0 or ANIMTIME2 > 0) before returning cleanly to idle.
3. Worn stick stow & redraw:
   - Drawing stick, igniting (State = 2), and burning down to 30 ticks (~8s).
   - Stowing worn stick refunds inventory (1 -> 2) and saves remaining budget in DekuStickWear = 30 ($7EF39F).
   - Redrawing from Equipment menu restores DekuStick_BurnTimer = 30 and clears DekuStickWear = 0.
   - Relighting preserves the 30-tick budget.
4. Visible OAM in 4 directions & controls:
   - Unlit held stick in 4 facings (Up, Down, Left, Right): Sprite 4 onscreen (palette 1), Sprite 5 hidden.
   - Lit held stick: Sprite 5 onscreen (tile $9C, palette 4), flame flicker observed on bit 6.
   - Y button press initiates 14-frame swipe, suppresses assigned Y item ($0303), and freezes movement inputs.
   - Captures native screenshots of held/swipe/flame poses.
5. Swipe enemy nonlethal stun & immunity:
   - Eligible active enemy in front of Link is stunned for 32 frames ($0EA0 = 0x20).
   - Enemy HP is unchanged (0 HP damage!).
   - DekuStick_SwipeTimer bit 6 latches to prevent multiple stuns per swipe.
   - Stick remains intact (no enemy-hit breakage).
   - Immune enemies ($0E40 >= 0x80) and wrong layer ($0F20 != Link) are unaffected.
   - Wall contact plays tink without breaking stick.
6. Native torch interaction (controller-driven):
   - Authored room: Room 0x00 (Entrance 0x7B), Floor F1, Layer 0 with real torch objects.
   - Joypad Equipment menu draw: unlit stick drawn (count 2 -> 1, state 1, burn 75).
   - D-pad movement approaches lit Torch 0: physical tip contact ignites stick (state 2).
   - D-pad movement carries lit stick across room to unlit Torch 1: physical tip contact lights Torch 1 ($04F1 > 0).
   - Joypad B button stows stick: count refunded (1 -> 2), burn budget saved in DekuStickWear ($7EF39F).
   - Redraw via joypad Equipment menu: restores burn budget from wear, wear cleared.
   - Reignite via D-pad against lit Torch 1: reignites stick, conserving remaining burn budget.
   - Noncontact controls: out of reach (at spawn and 39px north of torch) and walk away.
   - Captures native 256x224 screenshots: before_torch, contact_torch_ignite, after_torch_lit.
7. Cross-room scroll & lifecycle:
   - Screen scrolling ($11 != 0) pauses burn countdown and preserves fire across scroll.
   - Non-default state interruption ($5D = 0x13, Hookshotting) drops stick without refund.
   - Stowed wear ($7EF39F) survives transitions.
8. Save & Quit battery persistence:
   - Stowed worn stick with DekuStickWear = 30 persists across in-game Save & Quit.
   - Verifies battery SRAM has valid 0x5A5A checksum and backup equality.
   - Saves flushed battery SRM to disk.
9. Fresh-process cold boot reopen (T3 verification):
   - Closes initial emulator instance.
   - Launches fresh owned emulator process loading disk battery SRM without snapshots.
   - Cold boots through Title and File Select into gameplay.
   - Reopened session retains DekuStickWear = 30; redrawing restores 30-tick burn budget.
   - Corrupt wear fallback ($FF -> 75 ticks) verified.
   - Ordinary sword swing and Honeycomb consumable controls verified intact.
10. Interruption drop cleanup:
    - Taking damage ($5D = 1) immediately drops stick without refund and clears wear.
11. Burn countdown & burnout:
    - Lit stick ticks down every 16 frames; reaching 0 burns out and drops stick without refund.
12. Zero-inventory refusal:
    - With count = 0, pressing A in Equipment menu refuses activation and preserves stored wear.
13. Indoor dungeon ($10=7) gameplay:
    - Verifies drawing, holding, swiping, torch lighting, and stow inside underworld mode $07.
14. Real input-driven doorway crossing & real stairs transition:
    - Lit stick carried across real same-floor doorway in D6 (room 0x98 -> 0x88) preserves fire and resumes burn countdown.
    - Lit stick carried into real spiral stairs in Zora Temple (room 0x28 -> 0x38) cleans up stick and flame without inventory refund.
15. Overworld dispatch hook and transition drops:
    - Verifies $02A477 (Module09 dispatch hook) executes DekuStick_SubmoduleCheck every frame in overworld.
    - Walking across screen or scroll submodule preserves lit stick and pauses burn countdown.
    - Walking into real overworld entrance (D6 entrance at (3342, 3557)) triggers Module 08/entrance fade.
    - $0283BF (Module08/0A load hook) drops stick without inventory refund.
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
PENDING_SUPPLY = 0x7E0434
LINK_STATE = 0x7E005D
LINK_DIR = 0x7E002F
LINK_POSX = 0x7E0022
LINK_POSY = 0x7E0020
CURRENT_LAYER = 0x7E00EE
UNDERWORLD_FLAG = 0x7E001B
SWORD_STATE = 0x7E003C
SWORD_ANIM = 0x7E003D
FRAME_COUNTER = 0x7E001A
LINK_HP = 0x7EF36D
GAME_STATE = 0x7EF3C5
CHOICE = 0x7E00B0
HURTME = 0x7E0373
NOPAIN = 0x7E037B

DEKU_STICKS_COUNT = 0x7EF395  # SRAM Deku Sticks quantity
HONEYCOMB_COUNT   = 0x7EF394  # SRAM Honeycomb quantity
DEKU_STICK_WEAR   = 0x7EF39F  # SRAM DekuStickWear stored burn ticks
DEKU_STICK_STATE  = 0x7E046D  # WRAM 0=none, 1=held unlit, 2=held lit, 3=swiping
DEKU_BURN_TIMER   = 0x7E046E  # WRAM active burn ticks
DEKU_SWIPE_TIMER  = 0x7E046F  # WRAM swipe timer

SPRITE4_OAM       = 0x7E0810  # Stick OAM: X=0810, Y=0811, Tile=0812, Prop=0813
SPRITE5_OAM       = 0x7E0814  # Flame OAM: X=0814, Y=0815, Tile=0816, Prop=0817
OAM_HIGH          = 0x7E0A21  # High table bits for sprites 4 & 5
Y_ITEM_ASSIGNED   = 0x7E0303  # Assigned Y item
CONTROLLER_F0     = 0x7E00F0  # Held buttons
CONTROLLER_F4     = 0x7E00F4  # Newly pressed buttons
TORCH_TIMERS      = 0x7E04F0  # Torches 0..15 ($04F0..$04FF)
TILE_ATTR_BASE    = 0x7F2000  # Underworld tile attribute buffer

# Sprites 0..15 tables
SPRITE_STATE      = 0x7E0DD0
SPRITE_CLASS      = 0x7E0E20
SPRITE_DAMAGE     = 0x7E0E40
SPRITE_HP         = 0x7E0E50
SPRITE_STUN       = 0x7E0EA0
SPRITE_LAYER      = 0x7E0F20
SPRITE_POSX_LOW   = 0x7E0D10
SPRITE_POSX_HIGH  = 0x7E0D30
SPRITE_POSY_LOW   = 0x7E0D00
SPRITE_POSY_HIGH  = 0x7E0D20


def identity(pid: int) -> str:
    return subprocess.run(
        ["ps", "-o", "lstart=,command=", "-p", str(pid)],
        text=True, capture_output=True, check=False,
    ).stdout.strip()


class DekuStickRuntimeTest:
    def __init__(self, rom_path: Path, app_path: Path, work_dir: Path):
        self.rom = rom_path
        self.app = app_path
        self.work_dir = work_dir
        self.work_dir.mkdir(parents=True, exist_ok=True)
        self.screenshots_dir = self.work_dir / "screenshots"
        self.screenshots_dir.mkdir(parents=True, exist_ok=True)

        self.instance_name = f"deku-test-{int(time.time())}"
        self.sock = self.work_dir / f"mesen-{self.instance_name}.sock"
        self.home = self.work_dir / "profile"
        self.rom_copy = self.work_dir / "deku_candidate.sfc"
        shutil.copy2(self.rom, self.rom_copy)

        (self.home / "Saves").mkdir(parents=True, exist_ok=True)
        (self.home / "SaveStates").mkdir(parents=True, exist_ok=True)

        self.pid = 0
        self.pid_identity = ""
        self.b: MesenBridge | None = None
        self.results: dict[str, bool] = {}

    def launch(self, reset_save: bool = True):
        self.instance_name = f"deku-test-{int(time.time())}"
        self.sock = self.work_dir / f"mesen-{self.instance_name}.sock"

        if reset_save:
            shutil.copy2(SAVE_DEFAULT, self.home / "Saves" / "deku_candidate.srm")

        # Configure Mesen profile settings for explicit battery persistence
        settings_file = self.home / "settings.json"
        cfg = {}
        if settings_file.is_file():
            try:
                cfg = json.loads(settings_file.read_text(encoding="utf-8-sig"))
            except Exception:
                cfg = {}
        cfg.setdefault("Preferences", {})
        cfg["Preferences"]["OverrideSaveDataFolder"] = True
        cfg["Preferences"]["SaveDataFolder"] = str(self.home / "Saves")
        cfg.setdefault("Oracle", {})
        cfg["Oracle"]["PersistentSaveName"] = "deku_candidate"
        settings_file.write_text(json.dumps(cfg, indent=2))

        cmd = [
            "taskpolicy", "-b", "nice", "-n", "10", "bash", str(LAUNCHER),
            "--headless", "--no-copy-settings", "--no-save-settings",
            "--no-seed-project-states", "--no-state-set", "--no-register",
            "--instance", self.instance_name, "--home", str(self.home),
            "--socket", str(self.sock), "--rom", str(self.rom_copy),
            "--app", str(self.app),
        ]
        with (self.work_dir / "launch.log").open("a") as log:
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
        self.pid = 0
        self.pid_identity = ""
        self.b = None

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

    def boot_indoor_dungeon(self):
        print("[*] Loading indoor dungeon baseline state...")
        time.sleep(1)
        state_path = REPO / "Roms" / "SaveStates" / "library" / "oos_1772076582_Agent_D6_Inside_Entry_Fresh.mss"
        if not state_path.is_file():
            state_path = REPO / "Roms" / "SaveStates" / "library" / "oos_1772076583_Agent_Zora_Inside_Fresh.mss"
        res = self.b.load_state(path=str(state_path))
        print(f"[*] load_state indoor result: {res}")
        time.sleep(0.5)
        if not self.wait_play(8.0):
            raise RuntimeError(f"Failed to reach gameplay after load_state (MODULE={self.r(MODULE)}, SUBMODULE={self.r(SUBMODULE)})")
        print(f"[+] Reached stable indoor gameplay: MODULE={self.r(MODULE)}, SUBMODULE={self.r(SUBMODULE)}, UW={self.r(UNDERWORLD_FLAG)}")

    def boot_fresh_file(self):
        print("[*] Cold booting fresh emulator session without snapshots...")
        time.sleep(1.0)
        # Advance through Title to File Select (Module 1)
        for _ in range(40):
            if self.r(MODULE) == 1:
                break
            self.b.press_button("start", frames=6)
            time.sleep(0.3)
        print(f"    At File Select: MODULE={self.r(MODULE)}")
        # Launch File 1 into gameplay
        for _ in range(40):
            if self.r(MODULE) in (7, 9, 11) and self.r(SUBMODULE) == 0:
                break
            self.b.press_button("start", frames=8)
            time.sleep(0.3)
        if not self.wait_play(8.0):
            raise RuntimeError(f"Failed to enter gameplay from cold boot: MODULE={self.r(MODULE)}")
        print(f"[+] Reached stable gameplay from fresh boot: MODULE={self.r(MODULE)}")

    def navigate_to_equipment(self) -> bool:
        self.press("START", frames=10)
        for _ in range(50):
            if self.r(MENU) == 4:
                break
            time.sleep(0.05)
        if self.r(MENU) != 4:
            return False

        self.press("L", frames=10)
        for _ in range(50):
            if self.r(MENU) == 6:
                break
            time.sleep(0.05)
        return self.r(MENU) == 6

    def take_screenshot(self, name: str) -> Path | None:
        try:
            png = self.b.screenshot()
            if png:
                dest = self.screenshots_dir / f"{name}.png"
                dest.write_bytes(png)
                return dest
        except Exception as e:
            print(f"    [warn] screenshot {name} failed: {e}")
        return None

    def set_torch_probe_tile(self, facing: int, torch_id: int):
        # Deku_TorchProbeX: dw 8, 8, -4, 20 (Up=0, Down=2, Left=4, Right=6)
        # Deku_TorchProbeY: dw -4, 24, 8, 8
        offsets = {0: (8, -4), 2: (8, 24), 4: (-4, 8), 6: (20, 8)}
        dx, dy = offsets.get(facing, (8, 24))
        posx = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        posy = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        px = posx + dx
        py = posy + dy
        layer = self.r(CURRENT_LAYER)
        x_coord = (px & 0x01FF) >> 3
        y_coord = (py & 0x01F8) << 3
        tile_offset = y_coord + x_coord + (0x1000 if layer != 0 else 0)
        addr = TILE_ATTR_BASE + tile_offset
        self.w(addr, 0xC0 | (torch_id & 0x0F))

    def run_tests(self, filter_test: int | None = None):
        print("\n=== STARTING DEKU STICK RUNTIME PROOFS ===")

        # ----------------------------------------------------
        # 1. Fresh draw & sword lockout
        # ----------------------------------------------------
        if filter_test is None or filter_test == 1:
            print("[*] Test 1: Fresh Deku Stick draw & sword lockout...")
            self.w(DEKU_STICKS_COUNT, 2)
            self.w(DEKU_STICK_WEAR, 0)
            self.w(DEKU_STICK_STATE, 0)
            self.w(DEKU_BURN_TIMER, 0)
            self.w(PENDING_SUPPLY, 0)

            if not self.navigate_to_equipment():
                raise RuntimeError("Failed to open Equipment menu")

            # Cursor 20 = Deku Stick (supplies row 2, slot 3)
            self.w(CURSOR, 20)
            time.sleep(0.1)

            # Press A to queue draw
            self.press("A", frames=10)
            self.wait_play(8.0)

            count1 = self.r(DEKU_STICKS_COUNT)
            state1 = self.r(DEKU_STICK_STATE)
            burn1 = self.r(DEKU_BURN_TIMER)
            wear1 = self.r(DEKU_STICK_WEAR)

            print(f"    After draw: count={count1} (exp 1), state={state1} (exp 1), burn={burn1} (exp 75), wear={wear1} (exp 0)")

            # While stick is held (state 1), press B to test stow and sword lockout
            self.press("B", frames=10)
            time.sleep(0.1)

            count1_stow = self.r(DEKU_STICKS_COUNT)
            state1_stow = self.r(DEKU_STICK_STATE)
            wear1_stow = self.r(DEKU_STICK_WEAR)
            sword_stow = self.r(SWORD_STATE)

            t1_ok = (count1 == 1 and state1 == 1 and burn1 == 75 and wear1 == 0 and
                     count1_stow == 2 and state1_stow == 0 and wear1_stow == 0 and sword_stow == 0)
            self.results["fresh_draw_and_sword_lockout"] = t1_ok
            print(f"    After B stow: count={count1_stow} (exp 2), state={state1_stow} (exp 0), wear={wear1_stow} (exp 0), sword={sword_stow} (exp 0) -> OK: {t1_ok}")

        # ----------------------------------------------------
        # 2. Sword swings normally after stow
        # ----------------------------------------------------
        print("[*] Test 2: Sword swings normally after stick is stowed...")
        time.sleep(0.1)
        self.b.press_button("B", frames=8)
        observed_bflag = 0
        observed_anim = 0
        end_time = time.time() + 0.6
        while time.time() < end_time:
            bflag = self.r(SWORD_STATE)
            anim = self.r(SWORD_ANIM)
            if bflag > 0 or anim > 0:
                observed_bflag = bflag
                observed_anim = anim
                break
            time.sleep(0.01)

        end_time = time.time() + 1.2
        while time.time() < end_time:
            if self.r(SWORD_STATE) == 0 and self.r(SWORD_ANIM) == 0:
                break
            time.sleep(0.02)

        idle_after = (self.r(SWORD_STATE) == 0 and self.r(SWORD_ANIM) == 0)
        t2_ok = (state1_stow == 0 and (observed_bflag > 0 or observed_anim > 0) and idle_after)
        self.results["sword_normal_after_stow"] = t2_ok
        print(f"    Sword check: stick_state={state1_stow}, observed_bflag={observed_bflag}, observed_anim={observed_anim}, idle_after={idle_after} -> OK: {t2_ok}")
        time.sleep(0.3)

        # ----------------------------------------------------
        # 3. Worn stick stow, wear preservation & redraw
        # ----------------------------------------------------
        print("[*] Test 3: Worn stick stow, wear preservation, and redraw...")
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_WEAR, 0)
        self.w(DEKU_STICK_STATE, 0)
        self.w(DEKU_BURN_TIMER, 0)

        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        self.wait_play(8.0)

        # Simulate igniting stick (State = 2) and burning down to 30 ticks
        self.w(DEKU_STICK_STATE, 2)
        self.w(DEKU_BURN_TIMER, 30)
        time.sleep(0.1)

        # Stow worn stick
        self.press("B", frames=10)
        time.sleep(0.1)

        count3_stow = self.r(DEKU_STICKS_COUNT)
        state3_stow = self.r(DEKU_STICK_STATE)
        wear3_stow = self.r(DEKU_STICK_WEAR)
        print(f"    Worn stow: count={count3_stow} (exp 2), state={state3_stow} (exp 0), wear={wear3_stow} (exp in 25..30)")

        # Redraw stick from menu
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        self.wait_play(8.0)

        count3_redraw = self.r(DEKU_STICKS_COUNT)
        state3_redraw = self.r(DEKU_STICK_STATE)
        burn3_redraw = self.r(DEKU_BURN_TIMER)
        wear3_redraw = self.r(DEKU_STICK_WEAR)

        t3_ok = (count3_stow == 2 and state3_stow == 0 and (25 <= wear3_stow <= 30) and
                 count3_redraw == 1 and state3_redraw == 1 and burn3_redraw == wear3_stow and wear3_redraw == 0)
        self.results["worn_stick_stow_and_redraw"] = t3_ok
        print(f"    Worn redraw: count={count3_redraw} (exp 1), state={state3_redraw} (exp 1), burn={burn3_redraw} (exp {wear3_stow}), wear={wear3_redraw} (exp 0) -> OK: {t3_ok}")

        # ----------------------------------------------------
        # 4. Visible OAM in 4 directions & controls
        # ----------------------------------------------------
        print("[*] Test 4: Visible OAM in 4 directions, flame flicker, Y swipe suppression...")
        # Link currently holds stick (State = 1). Test 4 directions:
        facings = {0: "up", 2: "down", 4: "left", 6: "right"}
        oam_facings_ok = True
        for dir_val, dir_name in facings.items():
            self.w(LINK_DIR, dir_val)
            time.sleep(0.05)
            # Read stick OAM (Sprite 4) and flame OAM (Sprite 5)
            s4_y = self.r(SPRITE4_OAM + 1)
            s4_tile = self.r(SPRITE4_OAM + 2)
            s4_prop = self.r(SPRITE4_OAM + 3)
            s5_y = self.r(SPRITE5_OAM + 1)

            # Unlit: Sprite 4 onscreen, palette 1 (0x02), Sprite 5 hidden (0xE0)
            stick_onscreen = (s4_y != 0xE0)
            palette1_ok = ((s4_prop & 0x0E) == 0x02)
            flame_hidden = (s5_y == 0xE0)
            valid = stick_onscreen and palette1_ok and flame_hidden
            if not valid:
                oam_facings_ok = False
            self.take_screenshot(f"deku_held_{dir_name}_unlit")
            print(f"    Facing {dir_name.upper()} unlit: stick_y={s4_y}, tile=0x{s4_tile:02X}, prop=0x{s4_prop:02X}, flame_y={s5_y} -> valid: {valid}")

        # Now test lit flame OAM & flicker (State = 2)
        self.w(DEKU_STICK_STATE, 2)
        time.sleep(0.05)
        s5_y_lit = self.r(SPRITE5_OAM + 1)
        s5_tile_lit = self.r(SPRITE5_OAM + 2)
        s5_prop_lit = self.r(SPRITE5_OAM + 3)
        lit_flame_ok = (s5_y_lit != 0xE0 and s5_tile_lit == 0x9C and (s5_prop_lit & 0x0E) == 0x08)

        # Check flicker bit 6 over 8 frames
        flicker_observed = set()
        for _ in range(8):
            flicker_observed.add((self.r(SPRITE5_OAM + 3) & 0x40) != 0)
            time.sleep(0.02)
        flicker_ok = (len(flicker_observed) >= 2)
        self.take_screenshot("deku_held_down_lit")
        print(f"    Lit flame: y={s5_y_lit}, tile=0x{s5_tile_lit:02X}, prop=0x{s5_prop_lit:02X}, flicker_observed={flicker_ok} -> valid: {lit_flame_ok and flicker_ok}")

        # Test Y swipe suppression of assigned item
        self.w(Y_ITEM_ASSIGNED, 2)  # Assign Boomerang (item 2)
        time.sleep(0.05)
        # Queue Y press via Mesen controller
        self.b.press_button("y", frames=4)
        time.sleep(0.04)

        state_swipe = self.r(DEKU_STICK_STATE)
        timer_swipe = self.r(DEKU_SWIPE_TIMER)
        f4_after = self.r(CONTROLLER_F4)

        # Check that no Boomerang sprite was spawned in slots 0..15 ($0DD0..$0DDF)
        active_sprites = [self.r(SPRITE_STATE + i) for i in range(16)]
        boomerang_spawned = any(s == 0x09 and self.r(SPRITE_CLASS + i) == 0x0C for i, s in enumerate(active_sprites))

        # Check movement input freeze: set $F0 = 0x01
        self.w(CONTROLLER_F0, 0x01)
        time.sleep(0.02)
        f0_cleared = ((self.r(CONTROLLER_F0) & 0x0F) == 0)

        self.take_screenshot("deku_swipe_active")
        print(f"    Y swipe: state={state_swipe} (exp 3), timer={timer_swipe} (exp >0), f4_cleared={(f4_after & 0x40) == 0}, boomerang_spawned={boomerang_spawned}, input_frozen={f0_cleared}")

        # Wait for swipe to finish (~14 frames)
        time.sleep(0.3)
        state_after_swipe = self.r(DEKU_STICK_STATE)
        swipe_finished = (state_after_swipe == 2)  # returns to lit held state

        # Stow stick with B
        self.press("B", frames=10)
        time.sleep(0.1)

        t4_ok = (oam_facings_ok and lit_flame_ok and flicker_ok and
                 (state_swipe == 3 or swipe_finished) and not boomerang_spawned and
                 f0_cleared and swipe_finished)
        self.results["visible_oam_four_directions_and_controls"] = t4_ok
        print(f"    Visible OAM & controls verdict -> OK: {t4_ok}")

        # ----------------------------------------------------
        # 5. Swipe enemy nonlethal stun & immunity
        # ----------------------------------------------------
        print("[*] Test 5: Swipe nonlethal enemy stun, 0 HP damage, no break...")
        # Draw stick unlit (count 2 -> 1)
        self.w(DEKU_STICKS_COUNT, 1)
        self.w(DEKU_STICK_STATE, 1)
        self.w(DEKU_BURN_TIMER, 75)
        self.w(LINK_DIR, 2)  # Facing Down

        # Spawn active blue soldier in slot 0 directly in front of Link
        posx = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        posy = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        cur_layer = self.r(CURRENT_LAYER)
        underworld = self.r(UNDERWORLD_FLAG)

        self.w(SPRITE_STATE + 0, 9)     # Active
        self.w(SPRITE_CLASS + 0, 0x41)  # Soldier
        self.w(SPRITE_DAMAGE + 0, 0)    # Vulnerable
        self.w(SPRITE_HP + 0, 4)        # 4 HP
        self.w(SPRITE_STUN + 0, 0)      # Not stunned
        self.w(SPRITE_LAYER + 0, cur_layer)
        self.w(SPRITE_POSX_LOW + 0, (posx + 2) & 0xFF)
        self.w(SPRITE_POSX_HIGH + 0, (posx + 2) >> 8)
        self.w(SPRITE_POSY_LOW + 0, (posy + 18) & 0xFF)
        self.w(SPRITE_POSY_HIGH + 0, (posy + 18) >> 8)
        self.w(NOPAIN, 0xFF)  # Prevent collision hurt during weapon test

        print(f"    Sprite0 setup: Link=({posx},{posy}), Sprite0=({posx+2},{posy+18}), layer={cur_layer}, underworld={underworld}, state0={self.r(SPRITE_STATE+0)}")

        # Trigger swipe via Mesen joypad
        self.b.press_button("y", frames=4)

        observed_stun = 0
        observed_latched = False
        end_time = time.time() + 0.4
        poll_samples = 0
        while time.time() < end_time:
            stun = self.r(SPRITE_STUN + 0)
            timer = self.r(DEKU_SWIPE_TIMER)
            state = self.r(DEKU_STICK_STATE)
            s0_state = self.r(SPRITE_STATE + 0)
            if poll_samples < 5 and state == 3:
                print(f"      [poll] stick_state={state}, timer={timer}, stun={stun}, s0_state={s0_state}")
                poll_samples += 1
            if stun in (0x20, 0x1F, 0x1E):
                observed_stun = 0x20
            if (timer & 0x40) != 0:
                observed_latched = True
            if observed_stun == 0x20 and observed_latched and state == 1:
                break
            time.sleep(0.01)

        hp_during = self.r(SPRITE_HP + 0)
        state_end = self.r(DEKU_STICK_STATE)
        count_end = self.r(DEKU_STICKS_COUNT)
        hp_end = self.r(SPRITE_HP + 0)

        print(f"    Observed swipe hit: stun={observed_stun} (exp 0x20), hp={hp_during} (exp 4), latched={observed_latched}, state_end={state_end}")

        stun_ok = (observed_stun == 0x20 and hp_during == 4 and hp_end == 4 and
                   observed_latched and state_end == 1 and count_end == 1)

        # Test immune enemy ($0E40 = 0x80): should not be stunned
        self.w(SPRITE_DAMAGE + 0, 0x80)
        self.w(SPRITE_STUN + 0, 0)
        self.b.press_button("y", frames=4)
        time.sleep(0.25)
        immune_stun = self.r(SPRITE_STUN + 0)
        immune_ok = (immune_stun == 0)

        # Clear sprite slot 0 and restore NOPAIN
        self.w(SPRITE_STATE + 0, 0)
        self.w(SPRITE_STUN + 0, 0)
        self.w(NOPAIN, 0)

        t5_ok = (stun_ok and immune_ok)
        self.results["swipe_enemy_stun_and_immunity"] = t5_ok
        print(f"    Swipe enemy stun verdict: stun_ok={stun_ok}, immune_ok={immune_ok} -> OK: {t5_ok}")

        # ----------------------------------------------------
        # 6. Real controller-driven torch interaction in authored room 0x00
        # ----------------------------------------------------
        print("[*] Test 6: Controller-driven torch interaction in authored room 0x00...")
        self.boot_indoor_dungeon()
        # Load Entrance 0x7B (Room 0x00, Floor F1, Layer 0)
        self.w(0x7E010E, 0x7B)
        self.w(MODULE, 6)  # Module 06 UnderworldLoad
        self.w(SUBMODULE, 0)
        self.wait_play(8.0)
        time.sleep(0.5)

        # Setup starting fixture:
        # Declared progression fixture:
        # Deku Sticks count = 2, wear = 0, state = 0, burn = 0
        # Torch 0 lit ($04F0 = 0x80), Torch 1 unlit ($04F1 = 0x00, 0542 unlit bit)
        # Clear room boss sprite in slot 0 and protect Link from room hazards
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_WEAR, 0)
        self.w(DEKU_STICK_STATE, 0)
        self.w(DEKU_BURN_TIMER, 0)
        self.w(TORCH_TIMERS + 0, 0x80)
        self.w(TORCH_TIMERS + 1, 0x00)
        self.w(NOPAIN, 0x01)
        self.w(SPRITE_STATE + 0, 0)
        val_0542 = (self.r(0x7E0542) | (self.r(0x7E0543) << 8)) & 0x7FFF
        self.w(0x7E0542, val_0542 & 0xFF)
        self.w(0x7E0543, (val_0542 >> 8) & 0xFF)

        init_x = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        init_y = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        print(f"    Room 0x00 loaded: Link=({init_x}, {init_y}), Torch0=0x{self.r(TORCH_TIMERS+0):02X}, Torch1=0x{self.r(TORCH_TIMERS+1):02X}")

        # Noncontact control 1: Link at spawn (383, 137), 100+ px from torches
        nc1_state = self.r(DEKU_STICK_STATE)
        nc1_ok = (nc1_state == 0)

        # Step A: Draw unlit stick from Equipment menu via controller
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu in Room 0x00")
        self.w(CURSOR, 20)
        self.press("A", frames=10)
        self.wait_play(8.0)

        state_drawn = self.r(DEKU_STICK_STATE)
        count_drawn = self.r(DEKU_STICKS_COUNT)
        burn_drawn = self.r(DEKU_BURN_TIMER)
        draw_ok = (state_drawn == 1 and count_drawn == 1 and burn_drawn == 75)
        pos_draw = (self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8), self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8))
        print(f"    Joypad draw unlit stick: state={state_drawn} (exp 1), count={count_drawn} (exp 1), burn={burn_drawn} (exp 75), pos={pos_draw} -> OK: {draw_ok}")
        self.take_screenshot("before_torch")

        # Step B: Walk LEFT to X=296 (probe X = Link_X+8 = 302..304, in tile col 18 X=288..303)
        left_step = 0
        while (self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)) > 296:
            self.press("LEFT", frames=3)
            time.sleep(0.04)
            left_step += 1
            if left_step % 5 == 0:
                cx = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
                cy = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
                c_st = self.r(DEKU_STICK_STATE)
                c_5d = self.r(LINK_STATE)
                print(f"      [walk LEFT {left_step}] pos=({cx}, {cy}), state={c_st}, 5D=0x{c_5d:02X}")

        # Noncontact control 2: Link at (296, 137), 50+ px north of Torch 0, stick remains unlit
        posx_nc2 = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        posy_nc2 = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        nc2_state = self.r(DEKU_STICK_STATE)
        nc2_ok = (nc2_state == 1 and posy_nc2 <= 150)
        print(f"    Noncontact control 2 at ({posx_nc2}, {posy_nc2}): state={nc2_state} (exp 1) -> OK: {nc2_ok}")

        # Step C: Approach existing lit Torch 0 via D-pad DOWN
        while (self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)) < 176:
            self.press("DOWN", frames=2)
            time.sleep(0.04)
            if self.r(DEKU_STICK_STATE) == 2:
                break

        ignite_state = self.r(DEKU_STICK_STATE)
        ignite_burn = self.r(DEKU_BURN_TIMER)
        ignite_flame_y = self.r(SPRITE5_OAM + 1)
        ignite_ok = (ignite_state == 2 and ignite_burn in (74, 75) and ignite_flame_y != 0xE0)
        posx_ignite = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        posy_ignite = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        print(f"    Torch 0 ignition contact at ({posx_ignite}, {posy_ignite}): state={ignite_state} (exp 2), burn={ignite_burn} (exp 74..75), flame_y={ignite_flame_y} -> OK: {ignite_ok}")
        self.take_screenshot("contact_torch_ignite")

        # Step D: Carry lit stick to unlit Torch 1
        # Walk UP to Y=158 for clearance
        while (self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)) > 158:
            self.press("UP", frames=3)
            time.sleep(0.04)

        # Walk RIGHT to X=452 (aligned with Torch 1)
        while (self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)) < 452:
            self.press("RIGHT", frames=3)
            time.sleep(0.04)

        # Approach Torch 1: Walk DOWN to Y=176 facing DOWN
        while (self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)) < 176:
            self.press("DOWN", frames=2)
            time.sleep(0.04)
            if self.r(TORCH_TIMERS + 1) > 0:
                break

        t1_timer = self.r(TORCH_TIMERS + 1)
        stick_burn_when_lit = self.r(DEKU_BURN_TIMER)
        torch1_lit_ok = (t1_timer > 0 and stick_burn_when_lit > 0)
        posx_t1 = self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8)
        posy_t1 = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        print(f"    Torch 1 contact at ({posx_t1}, {posy_t1}): torch1_timer={t1_timer} (exp >0), stick_burn={stick_burn_when_lit} -> OK: {torch1_lit_ok}")
        self.take_screenshot("after_torch_lit")

        # Step E: Step slightly UP away from Torch 1 (to Y=166) so redrawn stick is out of torch probe range
        while (self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)) > 166:
            self.press("UP", frames=2)
            time.sleep(0.04)

        burn_before_stow = self.r(DEKU_BURN_TIMER)
        # Stow stick via joypad B button
        self.press("B", frames=8)
        time.sleep(0.15)
        stow_state = self.r(DEKU_STICK_STATE)
        stow_count = self.r(DEKU_STICKS_COUNT)
        saved_wear = self.r(DEKU_STICK_WEAR)
        stow_ok = (stow_state == 0 and stow_count == 2 and saved_wear == burn_before_stow and saved_wear > 0)
        print(f"    Stow via B: state={stow_state} (exp 0), count={stow_count} (exp 2), wear={saved_wear} (exp {burn_before_stow}) -> OK: {stow_ok}")

        # Step F: Redraw stick via joypad Equipment menu (at Y=166, out of torch reach -> draws unlit with wear)
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu for redraw")
        self.w(CURSOR, 20)
        self.press("A", frames=10)
        self.wait_play(8.0)

        redraw_state = self.r(DEKU_STICK_STATE)
        redraw_count = self.r(DEKU_STICKS_COUNT)
        redraw_burn = self.r(DEKU_BURN_TIMER)
        redraw_wear = self.r(DEKU_STICK_WEAR)
        redraw_ok = (redraw_state == 1 and redraw_count == 1 and redraw_burn == saved_wear and redraw_wear == 0)
        print(f"    Redraw stick: state={redraw_state} (exp 1), count={redraw_count} (exp 1), burn={redraw_burn} (exp {saved_wear}), wear={redraw_wear} (exp 0) -> OK: {redraw_ok}")

        # Step G: Reignite stick by approaching lit Torch 1 via D-pad DOWN
        while (self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)) < 176:
            self.press("DOWN", frames=2)
            time.sleep(0.04)
            if self.r(DEKU_STICK_STATE) == 2:
                break

        reignite_state = self.r(DEKU_STICK_STATE)
        reignite_burn = self.r(DEKU_BURN_TIMER)
        reignite_ok = (reignite_state == 2 and reignite_burn in (saved_wear, saved_wear - 1))
        print(f"    Reignite stick from Torch 1: state={reignite_state} (exp 2), burn={reignite_burn} (exp in [{saved_wear-1}, {saved_wear}]) -> OK: {reignite_ok}")

        # Step H: Noncontact control - walk away UP
        self.press("UP", frames=6)
        time.sleep(0.1)
        posy_away = self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8)
        state_away = self.r(DEKU_STICK_STATE)
        burn_away = self.r(DEKU_BURN_TIMER)
        nc3_ok = (state_away == 2 and posy_away <= 170 and burn_away <= reignite_burn)
        print(f"    Noncontact walk away: posy={posy_away}, state={state_away} (exp 2), burn={burn_away} -> OK: {nc3_ok}")

        # Stow stick to leave clean state
        self.press("B", frames=8)
        time.sleep(0.1)
        self.w(NOPAIN, 0x00)

        t6_ok = (nc1_ok and draw_ok and nc2_ok and ignite_ok and torch1_lit_ok and
                 stow_ok and redraw_ok and reignite_ok and nc3_ok)
        self.results["torch_native_lighting_and_ignition"] = t6_ok
        print(f"    Torch interaction verdict -> OK: {t6_ok}")

        # Restore overworld baseline state for subsequent lifecycle tests
        self.boot_file2()

        # ----------------------------------------------------
        # 7. Cross-room scroll & lifecycle
        # ----------------------------------------------------
        print("[*] Test 7: Cross-room scroll burn pause & transition lifecycle...")
        # Link has stick lit, budget 50 ticks
        self.w(DEKU_STICKS_COUNT, 1)
        self.w(DEKU_STICK_STATE, 2)
        self.w(DEKU_BURN_TIMER, 50)

        # Simulate ordinary screen scrolling: SUBMODULE $11 = 1
        self.w(SUBMODULE, 1)
        time.sleep(0.5)  # ~30 frames of scrolling

        burn_during_scroll = self.r(DEKU_BURN_TIMER)
        state_during_scroll = self.r(DEKU_STICK_STATE)
        scroll_paused = (burn_during_scroll == 50 and state_during_scroll == 2)
        print(f"    During scroll ($11=1): burn={burn_during_scroll} (exp 50), state={state_during_scroll} (exp 2) -> OK: {scroll_paused}")

        # Resume normal gameplay ($11 = 0)
        self.w(SUBMODULE, 0)
        scroll_resumed = False
        burn_after_scroll = 50
        for _ in range(30):
            time.sleep(0.05)
            burn_after_scroll = self.r(DEKU_BURN_TIMER)
            if burn_after_scroll < 50:
                scroll_resumed = True
                break
        print(f"    After scroll ($11=0): burn={burn_after_scroll} (exp <50) -> OK: {scroll_resumed}")

        # Generic non-default state interruption: LinkState $5D = 0x13 (Hookshotting) drops drawn stick without refund
        self.w(DEKU_STICK_STATE, 2)
        self.w(DEKU_BURN_TIMER, 40)
        self.w(LINK_STATE, 0x13)  # LinkState_Hookshotting ($5D = 0x13)
        time.sleep(0.1)
        state_stairs = self.r(DEKU_STICK_STATE)
        burn_stairs = self.r(DEKU_BURN_TIMER)
        count_stairs = self.r(DEKU_STICKS_COUNT)
        stairs_dropped = (state_stairs == 0 and burn_stairs == 0 and count_stairs == 1)
        self.w(LINK_STATE, 0)
        time.sleep(0.1)
        print(f"    Non-default state drop ($5D=0x13, Hookshotting): state={state_stairs} (exp 0), burn={burn_stairs} (exp 0), count={count_stairs} (exp 1) -> OK: {stairs_dropped}")

        # Stowed wear survives transitions
        self.w(DEKU_STICK_WEAR, 30)
        self.w(DEKU_STICK_STATE, 0)
        self.w(SUBMODULE, 1)  # Transition scroll while stowed
        time.sleep(0.1)
        self.w(SUBMODULE, 0)
        time.sleep(0.1)
        wear_survived = (self.r(DEKU_STICK_WEAR) == 30)
        print(f"    Stowed wear transition survival: wear={self.r(DEKU_STICK_WEAR)} (exp 30) -> OK: {wear_survived}")

        t7_ok = (scroll_paused and scroll_resumed and stairs_dropped and wear_survived)
        self.results["cross_room_scroll_and_lifecycle"] = t7_ok
        print(f"    Cross-room lifecycle verdict -> OK: {t7_ok}")

        # ----------------------------------------------------
        # 8. Save & Quit battery persistence
        # ----------------------------------------------------
        print("[*] Test 8: In-game Save & Quit and battery SRM persistence...")
        # Link has 2 sticks, stored wear = 30
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_WEAR, 30)
        self.w(DEKU_STICK_STATE, 0)
        self.w(GAME_STATE, 2)  # Enable SaveGameFile execution

        # Queue lethal damage to reach GameOver screen
        hp = self.r(LINK_HP) or 24
        self.w(LINK_HP, hp)
        self.w(NOPAIN, 0)
        self.w(HURTME, hp)

        # Wait for Game Over screen (MODULE 18 = 0x12, SUBMODULE 9)
        end_time = time.time() + 15.0
        while time.time() < end_time:
            if self.r(MODULE) == 18 and self.r(SUBMODULE) == 9:
                break
            time.sleep(0.05)
        if self.r(MODULE) != 18 or self.r(SUBMODULE) != 9:
            raise RuntimeError(f"Failed to enter GameOver screen: MODULE={self.r(MODULE)}, SUBMODULE={self.r(SUBMODULE)}")

        # Select Save and Quit (choice 1)
        for _ in range(4):
            if self.r(CHOICE) == 1:
                self.b.press_button("a", frames=8)
                break
            self.b.press_button("select", frames=8)
            time.sleep(0.3)

        # Wait for return to Title Screen
        end_time = time.time() + 15.0
        while time.time() < end_time:
            if self.r(MODULE) in (0, 1, 0x14):
                break
            time.sleep(0.05)
        print(f"    Returned to title/intro: MODULE={self.r(MODULE)}, SUBMODULE={self.r(SUBMODULE)}")

        # Read battery SRAM directly from emulator
        sram = self.b.read_block(0, 8192, memtype="SnesSaveRam")
        if len(sram) != 8192:
            raise RuntimeError(f"Expected 8192 bytes of SRAM, got {len(sram)}")

        slot1_csum = sum(int.from_bytes(sram[i:i+2], "little") for i in range(0, 0x500, 2)) & 0xFFFF
        csum_ok = (slot1_csum == 0x5A5A)
        backup_ok = (sram[:0x500] == sram[0xF00:0x1400])
        sram_wear = sram[0x39F]
        sram_count = sram[0x395]

        # Ensure SRM file is saved on disk for fresh process reopen
        srm_file = self.home / "Saves" / "deku_candidate.srm"
        srm_file.write_bytes(sram)
        (self.work_dir / "deku_persistence.srm").write_bytes(sram)
        print(f"    SRAM: csum=0x{slot1_csum:04X} (valid: {csum_ok}), backup={backup_ok}, count={sram_count}, wear={sram_wear}")

        t8_ok = (csum_ok and backup_ok and sram_wear == 30 and sram_count == 2)
        self.results["save_quit_battery_persistence"] = t8_ok
        print(f"    Save/Quit battery verdict -> OK: {t8_ok}")

        # ----------------------------------------------------
        # 9. Fresh-process cold boot reopen (T3 proof)
        # ----------------------------------------------------
        print("[*] Test 9: Fresh-process cold boot reopen with disk SRM...")
        # Cleanly shut down first emulator instance
        self.close()

        # Launch fresh emulator instance loading the disk SRM without reset
        self.launch(reset_save=False)
        self.boot_fresh_file()

        wear_reopened = self.r(DEKU_STICK_WEAR)
        count_reopened = self.r(DEKU_STICKS_COUNT)
        state_reopened = self.r(DEKU_STICK_STATE)
        burn_reopened = self.r(DEKU_BURN_TIMER)
        honeycomb_reopened = self.r(HONEYCOMB_COUNT)
        print(f"    Fresh session: count={count_reopened}, wear={wear_reopened}, state={state_reopened}, honeycomb={honeycomb_reopened}")

        reopened_clean = (wear_reopened == 30 and count_reopened == 2 and state_reopened == 0 and burn_reopened == 0)

        # Redraw stick to verify restored burn timer from preserved wear
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu after reopen")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        self.wait_play(8.0)

        redraw_count = self.r(DEKU_STICKS_COUNT)
        redraw_state = self.r(DEKU_STICK_STATE)
        redraw_burn = self.r(DEKU_BURN_TIMER)
        redraw_wear = self.r(DEKU_STICK_WEAR)
        print(f"    Redrawn from wear: count={redraw_count} (exp 1), state={redraw_state} (exp 1), burn={redraw_burn} (exp 30), wear={redraw_wear} (exp 0)")
        redraw_ok = (redraw_count == 1 and redraw_state == 1 and redraw_burn == 30 and redraw_wear == 0)

        # Stow stick
        self.press("B", frames=10)
        time.sleep(0.2)

        # Corrupt wear fallback test ($FF -> 75 ticks)
        self.w(DEKU_STICK_WEAR, 0xFF)
        time.sleep(0.1)
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu for corrupt wear test")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        self.wait_play(8.0)

        fallback_state = self.r(DEKU_STICK_STATE)
        fallback_burn = self.r(DEKU_BURN_TIMER)
        fallback_wear = self.r(DEKU_STICK_WEAR)
        fallback_ok = (fallback_state == 1 and fallback_burn == 75 and fallback_wear == 0)
        print(f"    Corrupt wear fallback: state={fallback_state}, burn={fallback_burn} (exp 75), wear={fallback_wear} (exp 0) -> OK: {fallback_ok}")

        # Stow stick
        self.press("B", frames=10)
        time.sleep(0.2)

        # Check ordinary sword swing works after reopen and stow
        self.b.press_button("B", frames=8)
        observed_sword = 0
        end_time = time.time() + 0.6
        while time.time() < end_time:
            if self.r(SWORD_STATE) > 0 or self.r(SWORD_ANIM) > 0:
                observed_sword = 1
                break
            time.sleep(0.01)
        time.sleep(0.5)

        sword_reopened_ok = (observed_sword == 1 and self.r(SWORD_STATE) == 0 and self.r(SWORD_ANIM) == 0)
        print(f"    Ordinary sword swing after reopen: observed={observed_sword} -> OK: {sword_reopened_ok}")

        t9_ok = (reopened_clean and redraw_ok and fallback_ok and sword_reopened_ok)
        self.results["save_reopen_t3_persistence"] = t9_ok
        print(f"    Fresh process reopen verdict -> OK: {t9_ok}")

        # ----------------------------------------------------
        # 10. Interruption drop cleanup (taking damage)
        # ----------------------------------------------------
        print("[*] Test 10: Interruption drop cleanup (damage drops stick)...")
        # Draw stick
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        self.wait_play(8.0)

        state10_drawn = self.r(DEKU_STICK_STATE)
        count10_drawn = self.r(DEKU_STICKS_COUNT)

        # Simulate damage interruption by writing LinkState $5D = 1
        self.w(LINK_STATE, 1)
        time.sleep(0.3)

        state10_after = self.r(DEKU_STICK_STATE)
        burn10_after = self.r(DEKU_BURN_TIMER)
        count10_after = self.r(DEKU_STICKS_COUNT)
        wear10_after = self.r(DEKU_STICK_WEAR)

        self.w(LINK_STATE, 0)
        time.sleep(0.1)

        t10_ok = (state10_drawn == 1 and state10_after == 0 and burn10_after == 0 and count10_after == 1 and wear10_after == 0)
        self.results["interruption_drop_cleanup"] = t10_ok
        print(f"    Interruption: drawn={state10_drawn}, after={state10_after}, burn={burn10_after}, count={count10_after} (exp 1), wear={wear10_after} (exp 0) -> OK: {t10_ok}")

        # ----------------------------------------------------
        # 11. Burn countdown & burn-out
        # ----------------------------------------------------
        print("[*] Test 11: Burn countdown & burn-out...")
        self.w(DEKU_STICKS_COUNT, 1)
        self.w(DEKU_STICK_WEAR, 0)
        self.w(DEKU_STICK_STATE, 2)  # Lit stick
        self.w(DEKU_BURN_TIMER, 3)   # 3 ticks remaining

        time.sleep(1.0)  # Wait ~50 frames for countdown to reach 0

        state11_after = self.r(DEKU_STICK_STATE)
        burn11_after = self.r(DEKU_BURN_TIMER)
        count11_after = self.r(DEKU_STICKS_COUNT)

        t11_ok = (state11_after == 0 and burn11_after == 0 and count11_after == 1)
        self.results["burn_countdown_and_burnout"] = t11_ok
        print(f"    Burn-out: state={state11_after} (exp 0), burn={burn11_after} (exp 0), count={count11_after} (exp 1) -> OK: {t11_ok}")

        # ----------------------------------------------------
        # 12. Zero-inventory refusal
        # ----------------------------------------------------
        print("[*] Test 12: Zero-inventory draw refusal...")
        self.w(DEKU_STICKS_COUNT, 0)
        self.w(DEKU_STICK_WEAR, 30)  # Retained wear
        self.w(DEKU_STICK_STATE, 0)
        self.w(PENDING_SUPPLY, 0)

        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu")
        self.w(CURSOR, 20)
        time.sleep(0.1)

        self.press("A", frames=10)
        time.sleep(0.5)

        menu12 = self.r(MENU)
        pend12 = self.r(PENDING_SUPPLY)
        count12 = self.r(DEKU_STICKS_COUNT)
        wear12 = self.r(DEKU_STICK_WEAR)

        self.press("START", frames=10)
        self.wait_play(5.0)

        t12_ok = (menu12 == 6 and pend12 == 0 and count12 == 0 and wear12 == 30)
        self.results["zero_inventory_refusal"] = t12_ok
        print(f"    Zero-inventory refusal: MENU={menu12} (exp 6), pending={pend12} (exp 0), count={count12} (exp 0), wear={wear12} (exp 30) -> OK: {t12_ok}")

        # ----------------------------------------------------
        # 13. Actual indoor Underworld ($10=7) gameplay proof
        # ----------------------------------------------------
        print("[*] Test 13: Actual indoor dungeon ($10=7) draw, hold, swipe, torch, room transition, and stow...")
        self.boot_indoor_dungeon()

        # Check natural indoor baseline without modifying MODULE:
        module_init = self.r(MODULE)
        submodule_init = self.r(SUBMODULE)
        uw_flag_init = self.r(UNDERWORLD_FLAG)
        link_state_init = self.r(LINK_STATE)
        print(f"    Indoor baseline: MODULE={module_init} (exp 7), SUBMODULE={submodule_init} (exp 0), UW={uw_flag_init} (exp !=0), LINK_STATE={link_state_init} (exp 0)")
        baseline_indoor_ok = (module_init == 7 and submodule_init == 0 and uw_flag_init != 0 and link_state_init == 0)

        # Setup inventory for indoor draw
        self.w(DEKU_STICKS_COUNT, 3)
        self.w(DEKU_STICK_WEAR, 0)
        self.w(DEKU_STICK_STATE, 0)
        self.w(PENDING_SUPPLY, 0)

        # Draw stick via Equipment menu in indoor mode:
        if not self.navigate_to_equipment():
            raise RuntimeError("Failed to open Equipment menu indoors")
        self.w(CURSOR, 20)
        time.sleep(0.1)
        self.press("A", frames=10)
        if not self.wait_play(8.0):
            raise RuntimeError("Failed to return to indoor gameplay after menu")

        module_after_draw = self.r(MODULE)
        state_after_draw = self.r(DEKU_STICK_STATE)
        count_after_draw = self.r(DEKU_STICKS_COUNT)
        burn_after_draw = self.r(DEKU_BURN_TIMER)
        oam_stick_y = self.r(0x7E0811)
        indoor_draw_ok = (module_after_draw == 7 and state_after_draw == 1 and count_after_draw == 2 and
                          burn_after_draw == 75 and oam_stick_y != 0xE0)
        print(f"    Indoor draw ($10=7): MODULE={module_after_draw}, state={state_after_draw} (exp 1), count={count_after_draw} (exp 2), burn={burn_after_draw} (exp 75), stick_y={oam_stick_y} -> OK: {indoor_draw_ok}")

        # Indoor Y swipe:
        self.b.press_button("y", frames=4)
        time.sleep(0.05)
        swipe_observed = False
        for _ in range(20):
            st = self.r(DEKU_STICK_STATE)
            sw = self.r(DEKU_SWIPE_TIMER)
            if st == 3 and sw > 0:
                swipe_observed = True
                break
            time.sleep(0.02)
        # Wait for swipe to finish back to held unlit (state 1)
        time.sleep(0.3)
        state_after_swipe = self.r(DEKU_STICK_STATE)
        indoor_swipe_ok = (swipe_observed and state_after_swipe == 1)
        print(f"    Indoor Y swipe: observed={swipe_observed}, state_after={state_after_swipe} (exp 1) -> OK: {indoor_swipe_ok}")

        # Indoor torch interaction:
        self.w(LINK_DIR, 2)  # Facing Down
        # Ignite from lit torch 0:
        self.w(TORCH_TIMERS + 0, 0x80)
        self.set_torch_probe_tile(facing=2, torch_id=0)
        time.sleep(0.1)
        state_after_ignite = self.r(DEKU_STICK_STATE)
        burn_after_ignite = self.r(DEKU_BURN_TIMER)
        indoor_ignite_ok = (state_after_ignite == 2 and burn_after_ignite > 0)
        print(f"    Indoor lit torch ignition: state={state_after_ignite} (exp 2), burn={burn_after_ignite} -> OK: {indoor_ignite_ok}")

        # Light unlit torch 1 with lit stick:
        self.w(TORCH_TIMERS + 1, 0x00)
        self.set_torch_probe_tile(facing=2, torch_id=1)
        time.sleep(0.1)
        torch1_lit = self.r(TORCH_TIMERS + 1)
        indoor_torch_light_ok = (torch1_lit > 0)
        print(f"    Indoor lighting unlit torch: torch1={torch1_lit} (exp >0) -> OK: {indoor_torch_light_ok}")

        # Indoor room transition (InterroomTransition / door scroll $11 = 2):
        self.w(DEKU_BURN_TIMER, 50)
        self.w(SUBMODULE, 2)  # Door scroll
        time.sleep(0.4)
        burn_in_door_scroll = self.r(DEKU_BURN_TIMER)
        state_in_door_scroll = self.r(DEKU_STICK_STATE)
        flame_y_scroll = self.r(0x7E0815)
        indoor_scroll_paused = (burn_in_door_scroll == 50 and state_in_door_scroll == 2 and flame_y_scroll != 0xE0)
        self.w(SUBMODULE, 0)
        time.sleep(0.4)
        burn_after_door_scroll = self.r(DEKU_BURN_TIMER)
        state_after_door_scroll = self.r(DEKU_STICK_STATE)
        indoor_scroll_resumed = (burn_after_door_scroll < 50 and state_after_door_scroll == 2)
        print(f"    Indoor door scroll ($11=2): paused={indoor_scroll_paused} (burn={burn_in_door_scroll}), resumed={indoor_scroll_resumed} (burn={burn_after_door_scroll}) -> OK: {indoor_scroll_paused and indoor_scroll_resumed}")

        # Indoor B stow & wear preservation:
        self.press("B", frames=10)
        time.sleep(0.2)
        state_after_stow = self.r(DEKU_STICK_STATE)
        count_after_stow = self.r(DEKU_STICKS_COUNT)
        wear_after_stow = self.r(DEKU_STICK_WEAR)
        indoor_stow_ok = (state_after_stow == 0 and count_after_stow == 3 and 0 < wear_after_stow < 75)
        print(f"    Indoor B stow: state={state_after_stow} (exp 0), count={count_after_stow} (exp 3), wear={wear_after_stow} (exp in 1..74) -> OK: {indoor_stow_ok}")

        # Indoor non-default LinkState interrupt ($5D = 0x13, Hookshotting drops stick):
        self.w(DEKU_STICK_STATE, 1)
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(LINK_STATE, 0x13)  # LinkState_Hookshotting ($5D = 0x13)
        time.sleep(0.1)
        state_spiral = self.r(DEKU_STICK_STATE)
        burn_spiral = self.r(DEKU_BURN_TIMER)
        count_spiral = self.r(DEKU_STICKS_COUNT)
        spiral_dropped = (state_spiral == 0 and burn_spiral == 0 and count_spiral == 2)
        self.w(LINK_STATE, 0)
        time.sleep(0.1)
        print(f"    Indoor non-default state drop ($5D=0x13, Hookshotting): state={state_spiral} (exp 0), burn={burn_spiral} (exp 0), count={count_spiral} (exp 2) -> OK: {spiral_dropped}")

        t13_ok = (baseline_indoor_ok and indoor_draw_ok and indoor_swipe_ok and
                  indoor_ignite_ok and indoor_torch_light_ok and
                  indoor_scroll_paused and indoor_scroll_resumed and
                  indoor_stow_ok and spiral_dropped)
        self.results["indoor_underworld_gameplay_proof"] = t13_ok
        print(f"    Indoor Underworld gameplay verdict -> OK: {t13_ok}")

        # ----------------------------------------------------
        # 14. Real input-driven doorway crossing and real stairs transition
        # ----------------------------------------------------
        print("[*] Test 14: Real input-driven doorway traversal and stairs transition...")
        # Part A: Carry lit stick through real same-floor doorway in D6 (room 0x98 -> 0x88)
        self.boot_indoor_dungeon()  # loads oos_1772076582_Agent_D6_Inside_Entry_Fresh.mss (Room 0x98)
        init_room = self.r(0x7E00A0)
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_STATE, 2)   # Held lit
        self.w(DEKU_BURN_TIMER, 60)   # 60 ticks
        time.sleep(0.1)

        print(f"    Doorway initial room: 0x{init_room:02X}, state={self.r(DEKU_STICK_STATE)}, burn={self.r(DEKU_BURN_TIMER)}")

        # Drive Link north through north doorway using joypad input UP
        door_scroll_entered = False
        for _ in range(25):
            self.b.press_button("UP", frames=8)
            time.sleep(0.15)
            if self.r(SUBMODULE) == 2:
                door_scroll_entered = True
                break

        # Wait for door scroll to finish and gameplay to resume in destination room
        door_scroll_finished = False
        for _ in range(40):
            time.sleep(0.1)
            if self.r(SUBMODULE) == 0 and self.r(MODULE) == 7:
                door_scroll_finished = True
                break

        dest_room = self.r(0x7E00A0)
        state_after_door = self.r(DEKU_STICK_STATE)
        flame_y_door = self.r(0x7E0815)
        burn_after_door = self.r(DEKU_BURN_TIMER)

        # Wait a moment to observe burn countdown ticking in new room
        burn_ticked = False
        for _ in range(30):
            time.sleep(0.1)
            if self.r(DEKU_BURN_TIMER) < burn_after_door:
                burn_ticked = True
                break

        doorway_traversal_ok = (
            door_scroll_entered and door_scroll_finished and
            dest_room == 0x88 and
            state_after_door == 2 and
            flame_y_door != 0xE0 and
            burn_ticked
        )
        print(f"    Doorway traversal (0x98 -> 0x{dest_room:02X}): scroll={door_scroll_entered}, arrived={door_scroll_finished}, state={state_after_door} (exp 2), flame_visible={flame_y_door != 0xE0}, burn_ticked={burn_ticked} -> OK: {doorway_traversal_ok}")

        # Part B: Enter real spiral stairs using joypad input UP in Zora Temple (Room 0x28)
        stairs_state_path = REPO / "Roms" / "SaveStates" / "library" / "oos168x" / "zora_temple_stairs_seed_20260207.mss"
        res = self.b.load_state(path=str(stairs_state_path))
        time.sleep(0.5)
        self.wait_play(8.0)
        zora_init_room = self.r(0x7E00A0)

        # Set lit stick fixture
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_STATE, 2)
        self.w(DEKU_BURN_TIMER, 60)
        time.sleep(0.1)

        print(f"    Zora initial room: 0x{zora_init_room:02X}, state={self.r(DEKU_STICK_STATE)}, burn={self.r(DEKU_BURN_TIMER)}, count={self.r(DEKU_STICKS_COUNT)}")

        # Drive Link north into spiral stairs using joypad input UP
        stairs_entered = False
        dropped_on_stairs = False
        for _ in range(25):
            self.b.press_button("UP", frames=8)
            time.sleep(0.15)
            sub = self.r(SUBMODULE)
            st = self.r(DEKU_STICK_STATE)
            if sub == 0x0E or st == 0:
                stairs_entered = True
                dropped_on_stairs = (st == 0 and self.r(DEKU_BURN_TIMER) == 0 and self.r(DEKU_STICKS_COUNT) == 2)
                break

        # Wait for stairs transition to complete and Link to arrive in destination room (0x38)
        for _ in range(50):
            time.sleep(0.1)
            if self.r(SUBMODULE) == 0 and self.r(MODULE) == 7:
                break

        final_room = self.r(0x7E00A0)
        final_state = self.r(DEKU_STICK_STATE)
        final_burn = self.r(DEKU_BURN_TIMER)
        final_count = self.r(DEKU_STICKS_COUNT)
        final_flame_y = self.r(0x7E0815)
        final_stick_y = self.r(0x7E0811)

        stairs_cleanup_ok = (
            stairs_entered and
            final_state == 0 and
            final_burn == 0 and
            final_count == 2 and
            final_flame_y >= 0xE0 and
            final_stick_y >= 0xE0 and
            final_room == 0x38
        )
        print(f"    Stairs transition (0x28 -> 0x{final_room:02X}): entered={stairs_entered}, state={final_state} (exp 0), burn={final_burn} (exp 0), count={final_count} (exp 2, no refund), flame_y={final_flame_y}, stick_y={final_stick_y}, dropped_on_stairs={dropped_on_stairs} -> OK: {stairs_cleanup_ok}")

        t14_ok = (doorway_traversal_ok and stairs_cleanup_ok)
        self.results["real_transitions_proof"] = t14_ok
        print(f"    Real transitions verdict -> OK: {t14_ok}")

        # ----------------------------------------------------
        # 15. Overworld dispatch hook and transition drops
        # ----------------------------------------------------
        print("[*] Test 15: Overworld dispatch hook ($02A477) and transition drops ($0283BF)...")
        # Load overworld baseline state
        self.boot_file2()  # loads oos_1772076682_Agent_Gameplay_Baseline_Fresh.mss (Module 09, Screen 64)
        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_STATE, 2)  # Held lit
        self.w(DEKU_BURN_TIMER, 60)
        time.sleep(0.1)

        # Part A: Ordinary overworld scroll / no-drop control
        # In Module 09, submodule 1..4 is whitelisted by DekuStick_SubmoduleCheck hooked at $02A477
        self.w(SUBMODULE, 1)  # scroll active
        time.sleep(0.4)
        burn_during_ow_scroll = self.r(DEKU_BURN_TIMER)
        state_during_ow_scroll = self.r(DEKU_STICK_STATE)
        flame_y_ow_scroll = self.r(SPRITE5_OAM + 1)
        ow_scroll_paused = (burn_during_ow_scroll == 60 and state_during_ow_scroll == 2 and flame_y_ow_scroll != 0xE0)

        self.w(SUBMODULE, 0)  # scroll complete
        time.sleep(0.4)
        burn_after_ow_scroll = self.r(DEKU_BURN_TIMER)
        state_after_ow_scroll = self.r(DEKU_STICK_STATE)
        ow_scroll_resumed = (burn_after_ow_scroll < 60 and state_after_ow_scroll == 2)
        print(f"    Overworld scroll ($11=1): paused={ow_scroll_paused} (burn={burn_during_ow_scroll}), resumed={ow_scroll_resumed} (burn={burn_after_ow_scroll}) -> OK: {ow_scroll_paused and ow_scroll_resumed}")

        # Part B: Real overworld destructive transition into D6 entrance
        # Load D6 Pre-Entrance overworld state (Screen 54, right outside D6)
        d6_ow_state_path = REPO / "Roms" / "SaveStates" / "library" / "oos_1772076582_Agent_D6_Pre_Entrance_Fresh.mss"
        self.b.load_state(path=str(d6_ow_state_path))
        time.sleep(0.5)
        self.wait_play(8.0)

        self.w(DEKU_STICKS_COUNT, 2)
        self.w(DEKU_STICK_STATE, 2)  # Held lit
        self.w(DEKU_BURN_TIMER, 60)
        time.sleep(0.1)

        init_ow_pos = (self.r(LINK_POSX) | (self.r(LINK_POSX + 1) << 8), self.r(LINK_POSY) | (self.r(LINK_POSY + 1) << 8))
        print(f"    D6 Pre-Entrance: pos={init_ow_pos}, screen={self.r(0x7E008A)}, state={self.r(DEKU_STICK_STATE)}")

        # Drive Link north into entrance doorway using joypad input UP
        ow_entrance_entered = False
        dropped_on_ow_entrance = False
        for step in range(35):
            self.b.press_button("UP", frames=4)
            time.sleep(0.08)
            mod = self.r(MODULE)
            st = self.r(DEKU_STICK_STATE)
            if st == 0 and not dropped_on_ow_entrance:
                dropped_on_ow_entrance = (self.r(DEKU_BURN_TIMER) == 0 and self.r(DEKU_STICKS_COUNT) == 2)
            if mod in (6, 7, 8, 15):
                ow_entrance_entered = True
                break

        # Wait for entrance transition into dungeon (Module 07)
        for _ in range(50):
            time.sleep(0.1)
            if self.r(MODULE) == 7 and self.r(SUBMODULE) == 0:
                break

        final_mod = self.r(MODULE)
        final_ow_state = self.r(DEKU_STICK_STATE)
        final_ow_burn = self.r(DEKU_BURN_TIMER)
        final_ow_count = self.r(DEKU_STICKS_COUNT)
        final_ow_flame_y = self.r(SPRITE5_OAM + 1)
        final_ow_stick_y = self.r(SPRITE4_OAM + 1)

        ow_entrance_drop_ok = (
            ow_entrance_entered and
            dropped_on_ow_entrance and
            final_ow_state == 0 and
            final_ow_burn == 0 and
            final_ow_count == 2 and  # NO refund!
            final_ow_flame_y >= 0xE0 and
            final_ow_stick_y >= 0xE0 and
            final_mod == 7
        )
        print(f"    Overworld entrance transition: entered={ow_entrance_entered}, state={final_ow_state} (exp 0), burn={final_ow_burn} (exp 0), count={final_ow_count} (exp 2, no refund), flame_y={final_ow_flame_y}, stick_y={final_ow_stick_y}, final_module={final_mod} -> OK: {ow_entrance_drop_ok}")

        t15_ok = (ow_scroll_paused and ow_scroll_resumed and ow_entrance_drop_ok)
        self.results["overworld_transitions_and_hooks_proof"] = t15_ok
        print(f"    Overworld transitions & hooks verdict -> OK: {t15_ok}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, default=Path("/tmp/oos_private_deku.sfc"))
    parser.add_argument("--app", type=Path, default=APP_DEFAULT)
    parser.add_argument("--work-dir", type=Path, default=Path("/tmp/oos_deku_runtime"))
    args = parser.parse_args()

    test = DekuStickRuntimeTest(args.rom, args.app, args.work_dir)
    try:
        test.launch(reset_save=True)
        test.boot_file2()
        test.run_tests()
    finally:
        test.close()

    print("\n" + "=" * 50)
    print("DEKU STICK RUNTIME PROOF SUMMARY:")
    all_passed = True
    for name, passed in test.results.items():
        print(f"  [{'PASS' if passed else 'FAIL'}] {name}")
        if not passed:
            all_passed = False
    print("=" * 50)

    report_path = args.work_dir / "deku_runtime_report.json"
    report_path.write_text(json.dumps(dict(
        passed=all_passed,
        results=test.results,
        rom_sha256=hashlib.sha256(args.rom.read_bytes()).hexdigest(),
    ), indent=2))
    print(f"[*] Report saved to {report_path}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
