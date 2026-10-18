#!/usr/bin/env python3
"""Attach-only first native check of the new items; never starts an emulator.

Only declared private-session inventory/magic WRAM bytes are fixture writes.
All selection, mask binding, transformation and item use use controller input.
No CPU, position, story, room, SRAM, save-state or ROM writes are made.
This scenario does not establish acquisition, Garo contact/counter damage, or
successful Switch Hook exchange; those need a separate world fixture.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
# Staging this script in AFS avoids changing inputs while the combined ROM builds.
# After copying to Tests/native this argument is optional.
if "--support-root" in sys.argv:
    sys.path.insert(0, sys.argv[sys.argv.index("--support-root") + 1])
import quest_collectibles as menu

native = menu.native
NEW_OWNERSHIP = (0x7EF3AC, 0x7EF3AD, 0x7EF3AE, 0x7EF3AF)
BOMBS, HOOK, SWORD = 0x7EF343, 0x7EF342, 0x7EF359
ALLOWED = set(NEW_OWNERSHIP) | {BOMBS, HOOK, SWORD, menu.MAGIC}
PROTECTED = (0x7EF3A3, 0x7EF3A4, 0x7EF3A5, 0x7EF3C5, 0x7EF3C6,
             0x7EF3D6, 0x7EF3D7, 0x7EF3D8, 0x7EF374, 0x7EF37A, 0x7EF410)
BOTTOM = (0x19, 0x10, 0x1D, 0x1C, 0x1A, 0x18)
NAMES = {0x1B: ("BYRNA", "ByrnaGFX"),
         0x1C: ("BOMBCHU", "BombchuGFX"),
         0x1D: ("SWITCH HOOK", "SwitchHookGFX")}


def describe():
    return dict(native_executed=False, acquisition_tested=False,
                fixture_addresses=[f"{a:06X}" for a in sorted(ALLOWED)],
                menu_bottom_order=[f"{item:02X}" for item in BOTTOM],
                checks=["Owned bottom-row order, new item labels/icons/HUD",
                        "Equipment sixth mask: bind, R transform, Y guard, R remove",
                        "Bombchu: Y cast, forward movement, one ammo debit, explosion",
                        "Normal bomb control: one ammo debit and ordinary bomb lifetime",
                        "Switch Hook miss: visible chain, retract, no drag, released controls"],
                followups=["Garo timed enemy-contact parry and counter damage",
                           "Switch Hook accepted/rejected D5 world fixture and ordinary pull control"])


class NewItemsFlow(menu.QuestFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 600
        self.result["scope"] = describe()

    def write(self, address, value, reason):
        self.check_owner()
        native.require(address in ALLOWED and 0 <= value <= 255 and self.paused(),
                       "Fixture outside paused inventory/magic contract")
        if address in NEW_OWNERSHIP:
            native.require(value == 1, "New-item fixture only grants exact ownership value 1")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Fixture readback differs")

    def until(self, predicate, label, frames=160):
        for _ in range((frames + 1) // 2):
            if predicate():
                return
            self.advance("", 2)
        native.require(predicate(), label)

    def ready(self):
        self.until(lambda: self.screen() == "gameplay" and self.r(0x7E0011) == 0
                   and self.r(0x7E005D) == 0 and self.r(0x7E037A) == 0
                   and not (self.r(0x7E003A) & 0xC0), "Link did not regain item control", 220)

    def ancilla(self, kind):
        return [i for i in range(5) if self.r(0x7E0C4A + i) == kind]

    def position(self, slot):
        return (self.r(0x7E0C04 + slot) | self.r(0x7E0C18 + slot) << 8,
                self.r(0x7E0BFA + slot) | self.r(0x7E0C0E + slot) << 8)

    def pick(self, item):
        native.require(self.screen() == "items", "Need Items screen")
        for _ in range(24):
            if self.r(0x7E0202) == item:
                return
            self.tap("Right")
        raise RuntimeError(f"Item {item:02X} is unreachable")

    def equip(self, item):
        self.ready()
        self.tap("Start"); self.wait_screen("items")
        self.pick(item)
        self.tap("Start"); self.wait_screen("gameplay")
        self.ready()

    def icon_words(self, table, variant=1):
        position = native.pc_offset(self.symbol(table)) + (variant - 1) * 8
        return [int.from_bytes(self.rom[i:i + 2], "little")
                for i in range(position, position + 8, 2)]

    def hud(self, label, table):
        words = [int.from_bytes(self.block(address, 2), "little")
                 for address in (0x7EC776, 0x7EC778, 0x7EC7B6, 0x7EC7B8)]
        self.check(label, words, self.icon_words(table))

    def menu_checks(self):
        self.tap("Start"); self.wait_screen("items")
        self.pick(0x1D)
        start, seen = 0x1D, []
        for _ in range(24):
            seen.append(self.r(0x7E0202))
            self.tap("Right")
            if self.r(0x7E0202) == start:
                break
        self.check("Physical navigation wraps", self.r(0x7E0202), start)
        owned_bottom = [item for item in BOTTOM if item in seen]
        pivot = owned_bottom.index(start)
        self.check("Bottom-row order among existing owned cells",
                   [item for item in seen if item in BOTTOM],
                   owned_bottom[pivot:] + owned_bottom[:pivot])
        self.result["owned_physical_order"] = [f"{item:02X}" for item in seen]
        self.icon("Switch Hook directly below Hookshot", 13, 20, "SwitchHookGFX")
        self.icon("Bombchu directly below Bombs", 17, 20, "BombchuGFX")
        self.icon("Byrna beside Somaria", 17, 17, "ByrnaGFX")
        if 0x1A in seen:
            self.icon("Goldstar fifth bottom cell", 20, 20, "HookGFX", 2)
        self.shot("new-items-menu")
        for item, (name, table) in NAMES.items():
            self.pick(item)
            self.check(name + " footer", self.text(9, 26, 14).strip(), name)
            self.tap("Start"); self.wait_screen("gameplay")
            self.hud(name + " HUD", table)
            self.tap("Start"); self.wait_screen("items")
        self.pick(0x1D)
        self.tap("L"); self.wait_screen("equipment")
        for _ in range(4):
            if self.r(menu.CURSOR) < 6:
                break
            self.tap("Up")
        native.require(self.r(menu.CURSOR) < 6, "Could not reach mask row")
        for _ in range(6):
            if self.r(menu.CURSOR) == 5:
                break
            self.tap("Right")
        self.check("Garo sixth Equipment mask", self.r(menu.CURSOR), 5)
        self.icon("Garo mask icon", 23, 10, "GaroMaskGFX")
        self.check("Garo label", self.text(9, 26, 14).strip(), "GARO MASTER")
        self.tap("A")
        self.check("Controller binds Garo", self.r(0x7EF3A8), 6)
        self.shot("garo-equipment")
        self.tap("Start"); self.wait_screen("gameplay")

    def mask_checks(self):
        self.ready()
        self.check("Garo binding retains normal item", self.r(0x7E0202), 0x1D)
        self.tap("R")
        self.until(lambda: self.r(0x7E02B2) == 8 and self.r(0x7E005D) == 0,
                   "R did not activate Garo", 220)
        self.advance("", 4)
        self.check("Garo retains Switch Hook selection", self.r(0x7E0202), 0x1D)
        self.check("Garo suppresses normal Y action", self.r(0x7E0303), 0)
        self.hud("Garo HUD", "GaroMaskGFX")
        self.tap("Y", 1)
        native.require(self.r(0x7E07EE) > 0, "Y did not open Garo's guard window")
        self.check("Garo Y does not cast selected chain", self.ancilla(0x1F), [])
        self.shot("garo-guard")
        self.advance("", 40)
        self.check("Garo guard expires", self.r(0x7E07EE), 0)
        self.tap("R")
        self.until(lambda: self.r(0x7E02B2) in (0, 6) and self.r(0x7E005D) == 0,
                   "R did not remove Garo", 220)
        self.ready()
        self.check("Unmask retains normal item", self.r(0x7E0202), 0x1D)
        self.check("Unmask restores chain action", self.r(0x7E0303), 0x0E)
        self.hud("Unmasked Switch Hook HUD", "SwitchHookGFX")

    def bombchu_checks(self):
        self.equip(0x1C)
        self.tap(self.a.launch_direction, 2)
        self.ready()
        before = self.r(BOMBS)
        self.tap("Y", 1)
        self.until(lambda: self.r(0x7E07F1) != 0, "Bombchu did not allocate a native bomb", 24)
        slot = self.r(0x7E07F1) - 1
        native.require(slot in (0, 1), "Bombchu used a non-bomb ancilla slot")
        self.check("Bombchu debits one bomb", self.r(BOMBS), before - 1)
        self.check("Bombchu uses native bomb", self.r(0x7E0C4A + slot), 7)
        self.check("Bombchu signature", self.r(0x7E03EA + slot), 0xBC)
        origin = self.position(slot)
        direction = self.r(0x7E07F2)
        trace, explosion, moved = [], False, False
        self.shot("bombchu-flight")
        for _ in range(100):
            kind, phase = self.r(0x7E0C4A + slot), self.r(0x7E0C5E + slot)
            point = self.position(slot)
            trace.append(dict(kind=kind, phase=phase, position=point,
                              active=self.r(0x7E07F1), ammo=self.r(BOMBS)))
            if kind != 7:
                break
            explosion |= phase > 0
            if phase == 0:
                dx = ((point[0] - origin[0] + 0x8000) & 0xFFFF) - 0x8000
                dy = ((point[1] - origin[1] + 0x8000) & 0xFFFF) - 0x8000
                forward = (-dy, dy, -dx, dx)[direction]
                moved |= forward >= 2
            self.advance("", 2)
        self.result["bombchu_trace"] = trace
        self.check("Bombchu moves forward", moved, True)
        self.check("Bombchu enters native explosion", explosion, True)
        self.check("Bombchu finishes native lifetime", self.r(0x7E0C4A + slot), 0)
        self.check("Bombchu clears ownership latch", self.r(0x7E07F1), 0)
        self.check("Bombchu lifetime costs one bomb", self.r(BOMBS), before - 1)

    def normal_bomb_control(self):
        self.equip(0x04)
        before = self.r(BOMBS)
        self.tap("Y", 1)
        self.until(lambda: bool(self.ancilla(7)), "Normal bomb did not spawn", 24)
        self.check("Normal bomb debits one bomb", self.r(BOMBS), before - 1)
        self.check("Normal bomb has no Bombchu owner", self.r(0x7E07F1), 0)
        for slot in self.ancilla(7):
            native.require(self.r(0x7E03EA + slot) != 0xBC, "Ordinary bomb acquired Bombchu signature")
        # Ordinary controller movement, not a position fixture; leave the bomb.
        self.advance(self.a.launch_direction, 18)
        self.advance("", 2)
        self.until(lambda: not self.ancilla(7), "Normal bomb did not finish", 240)
        self.check("Normal bomb lifetime costs one bomb", self.r(BOMBS), before - 1)
        self.ready()

    def switch_miss(self):
        self.equip(0x1D)
        self.tap(self.a.launch_direction, 2)
        self.ready()
        before = self.block(0x7E0020, 4)
        self.tap("Y", 1)
        self.until(lambda: bool(self.ancilla(0x1F)), "Switch Hook did not cast", 24)
        self.check("Switch Hook owns its flight", self.r(0x7E07F8), 0xA5)
        self.check("Switch Hook uses ordinary chain rendering", self.r(0x7E005D), 0x13)
        self.shot("switch-hook-flight")
        trace = []
        for _ in range(100):
            slots = self.ancilla(0x1F)
            trace.append(dict(slots=slots, drag=self.r(0x7E037E),
                              active=self.r(0x7E07F8), state=self.r(0x7E005D)))
            native.require(not self.r(0x7E037E), "Switch Hook miss started vanilla wall dragging")
            if not slots:
                break
            self.advance("", 2)
        self.result["switch_miss_trace"] = trace
        self.check("Miss retracts its chain", self.ancilla(0x1F), [])
        self.ready()
        self.check("Miss clears shot latch", self.r(0x7E07F8), 0)
        self.check("Miss does not teleport or pull Link", self.block(0x7E0020, 4).hex(), before.hex())
        self.shot("new-items-finished")

    def run(self):
        native.require(self.screen() == "gameplay" and self.r(0x7E0010) in (7, 9)
                       and self.r(0x7E0011) == 0, "Need stable private gameplay")
        native.require(self.r(0x7E02B2) in (0, 6) and not self.r(0x7E0055),
                       "Need ordinary Link without a cape/mask")
        native.require(not self.ancilla(7) and not self.ancilla(0x1F), "Existing bomb or chain active")
        native.require(self.r(menu.HP) >= 16, "Private save needs at least two hearts for damage-on bomb control")
        protected = {str(address): self.r(address) for address in PROTECTED}
        for address in NEW_OWNERSHIP:
            self.write(address, 1, "Explicit prototype ownership fixture")
        self.write(BOMBS, 9, "Shared ordinary bomb ammunition fixture")
        self.write(HOOK, 1, "Ordinary Hookshot control ownership")
        if not 1 <= self.r(SWORD) <= 4:
            self.write(SWORD, 1, "Ordinary sword needed by Garo counter prototype")
        self.write(menu.MAGIC, 128, "Private full magic fixture")
        self.menu_checks()
        self.mask_checks()
        self.bombchu_checks()
        self.normal_bomb_control()
        self.switch_miss()
        self.check("Story/ring/progression bytes remain unchanged",
                   {str(address): self.r(address) for address in PROTECTED}, protected)
        self.check("All four new ownership bytes persist", [self.r(a) for a in NEW_OWNERSHIP], [1] * 4)
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--support-root", type=Path, default=Path(__file__).parent)
    parser.add_argument("--launch-direction", choices=("Up", "Down", "Left", "Right"), default="Right")
    for key in ("socket", "rom-sha256", "symbols-sha256", "owner"):
        parser.add_argument("--" + key)
    for key in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output"):
        parser.add_argument("--" + key, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--execute-fixtures", action="store_true")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures, "Use --describe or explicitly --execute-fixtures")
    required = ("socket", "rom_sha256", "symbols_sha256", "owner", "owned_rom", "symbols",
                "client_root", "status_file", "owner_file", "output", "pid")
    native.require(all(getattr(args, name) for name in required), "Missing explicit private-session identity")
    native.require(args.socket.startswith("/tmp/mesen2-new-items-")
                   and args.owner.startswith("codex-new-items-") and "oos-rc-play" not in str(args),
                   "Only task-owned new-items session admitted")
    native.require(native.digest(args.owned_rom.read_bytes()) == args.rom_sha256, "Private ROM hash differs")
    native.require(native.digest(args.symbols.read_bytes()) == args.symbols_sha256, "Symbols hash differs")
    args.rom_sha1 = native.digest(args.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    native.require("--headless" in command and str(args.owned_rom) in command,
                   "PID is not the explicit headless private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = NewItemsFlow(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = vars(args)
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(),
                       "Need paused private session with no breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.check_owner(); flow.input(""); flow.b.pause()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
