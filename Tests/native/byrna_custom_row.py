#!/usr/bin/env python3
"""Attach-only controller check of Byrna and the custom item row.

The caller owns the private paused headless Mesen process and cleanup. Inventory
and magic are declared WRAM fixtures; no position, health, story, cursor, CPU,
ROM, save-state or SRAM writes. The scenario does not prove item acquisition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
import quest_collectibles as menu

native = menu.native
BYRNA, RODS, PORTAL, GOLDSTAR = 0x7EF3AC, 0x7EF351, 0x7EF3A6, 0x7EF3A9
INVENTORY = tuple(0x7EF300 + value for value in
                  (0x40, 0x41, 0x42, 0x43, 0x44, 0x5C, 0x4B, 0x4A, 0x45,
                   0x46, 0x53, 0x5D, 0x4C, 0x4E, 0x50, 0x51, 0x4D, 0x5E,
                   0x5F, 0xA6, 0xA9, 0xAC, 0xAD, 0xAE))
ALLOWED = set(INVENTORY) | {menu.MAGIC, 0x7EF349, 0x7EF3A8}
PROTECTED = (0x7EF3A3, 0x7EF3A8, 0x7EF3C5, 0x7EF3C6, 0x7EF3D6,
             0x7EF3D7, 0x7EF3D8, 0x7EF374, 0x7EF37A, 0x7EF410)
CASES = (
    ("fishing-only", {RODS: 1}, (0x10,)),
    ("upgraded-rods", {RODS: 2}, (0x10, 0x19)),
    ("byrna-only", {BYRNA: 1}, (0x1B,)),
    ("invalid-byrna", {BYRNA: 255}, ()),
    ("custom-row", {BYRNA: 1, RODS: 2, GOLDSTAR: 1, 0x7EF350: 1,
                     0x7EF35F: 3}, (0x0F, 0x1B, 0x19, 0x10, 0x1A, 0x18)),
)


def describe():
    return dict(cases=[dict(name=n, writes={f"{a:06X}": v for a, v in writes.items()},
                            selectable=list(items)) for n, writes, items in CASES],
                native_executed=False, acquisition_tested=False,
                behavior=["Physical D-pad routing with stable item IDs",
                          "Byrna beside Somaria; Portal/Fishing first two bottom cells, Goldstar fifth",
                          "Declared empty inventory also clears Bombchu/Switch Hook ownership",
                          "Byrna HUD, no-magic refusal, spark activation and magic drain",
                          "Second Y and switching to each rod terminate the shield",
                          "Declared Deku ownership/binding: R transform stops shield without changing Y selection",
                          "Fishing cast/retract and Portal Y-action selection"])


class ByrnaFlow(menu.QuestFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.result["scope"] = describe()

    def write(self, address, value, reason):
        self.check_owner()
        native.require(address in ALLOWED and 0 <= value <= 255 and self.paused(),
                       "Fixture outside paused inventory/magic contract")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Fixture readback differs")

    def pick(self, item):
        native.require(self.screen() == "items", "Need Items screen")
        for _ in range(24):
            if self.r(0x7E0202) == item:
                return
            self.tap("Right")
        raise RuntimeError(f"Item {item:02X} is unreachable")

    def sparks(self):
        return [slot for slot in range(5) if self.r(0x7E0C4A + slot) == 0x31]

    def until(self, predicate, label, frames=100):
        for _ in range(frames // 2):
            if predicate():
                return
            self.advance("", 2)
        raise RuntimeError(label)

    def activate(self):
        self.tap("Start"); self.wait_screen("items")
        self.pick(0x1B)
        self.tap("Start"); self.wait_screen("gameplay")
        self.write(menu.MAGIC, 0x80, "Disposable full-magic Byrna fixture")
        self.tap("Y")
        self.until(lambda: bool(self.sparks()), "Byrna spark did not activate")
        self.advance("", 2)
        self.check("Byrna active shield flag", self.r(0x7E037B), 1)

    def run(self):
        native.require(self.screen() == "gameplay" and self.r(0x7E0011) == 0,
                       "Need stable private gameplay")
        native.require(not self.r(0x7E02B2) and not self.r(0x7E0055),
                       "Need ordinary Link, without a mask form")
        native.require(not self.sparks() and not self.r(0x7F5BA2), "An item is already active")
        protected = {str(a): self.r(a) for a in PROTECTED}
        for name, values, selectable in CASES:
            for address in INVENTORY:
                self.write(address, values.get(address, 0), name)
            self.tap("Start"); self.wait_screen("items")
            if not selectable:
                self.check(name + " has no selected item", self.r(0x7E0202), 0)
                self.tap("Right")
                self.check(name + " ignores empty navigation", self.r(0x7E0202), 0)
            else:
                self.pick(selectable[0])
                seen = []
                for _ in selectable:
                    seen.append(self.r(0x7E0202)); self.tap("Right")
                self.check(name + " visible order", seen, list(selectable))
                self.check(name + " wraps", self.r(0x7E0202), selectable[0])
            if name == "custom-row":
                self.icon("Byrna beside Somaria", 17, 17, "ByrnaGFX")
                self.icon("Portal bottom first", 7, 20, "PortalRodGFX")
                self.icon("Fishing bottom second", 10, 20, "FishingRodGFX")
                self.icon("Goldstar bottom fifth", 20, 20, "HookGFX", 2)
                self.pick(0x0F); self.tap("Down")
                self.check("Somaria downward fallback skips unowned new items to Goldstar", self.r(0x7E0202), 0x1A)
                self.tap("Up")
                self.check("Goldstar upward fallback skips empty Feather/Bottle3 to Portal", self.r(0x7E0202), 0x19)
                self.pick(0x1B); self.tap("Down")
                self.check("Byrna downward fallback skips unowned Bombchu to Goldstar", self.r(0x7E0202), 0x1A)
                self.tap("Left")
                self.check("Left skips unowned Bombchu/Switch Hook to Fishing", self.r(0x7E0202), 0x10)
                self.pick(0x1B)
                self.check("Byrna label", self.text(9, 26, 14).strip(), "BYRNA")
                self.shot("custom-row")
            self.tap("Start"); self.wait_screen("gameplay")
            self.check(name + " preserves unrelated progress",
                       {str(a): self.r(a) for a in PROTECTED}, protected)

        self.check("Byrna uses existing action", self.r(0x7E0303), 0x0D)
        hud = [int.from_bytes(self.block(a, 2), "little")
               for a in (0x7EC776, 0x7EC778, 0x7EC7B6, 0x7EC7B8)]
        self.check("Byrna HUD", hud, [0x2CDC, 0x2CDD, 0x2CEC, 0x2CED])
        self.write(menu.MAGIC, 0, "No-magic refusal")
        self.tap("Y", 30)
        self.check("No magic creates no shield", self.sparks(), [])
        self.check("No-magic use releases animation", self.r(0x7E037A) & 8, 0)
        self.check("Vanilla no-magic message", int.from_bytes(self.block(0x7E1CF0, 2), "little"), 0x007B)
        for _ in range(12):
            if self.screen() == "gameplay":
                break
            self.tap("B", 20)
        self.wait_screen("gameplay")
        self.activate()
        before = self.r(menu.MAGIC)
        self.advance("", 60)
        native.require(self.r(menu.MAGIC) < before, "Byrna did not drain magic")
        self.tap("Y"); self.until(lambda: not self.sparks(), "Second Y did not dismiss Byrna")
        self.check("Dismissal clears shield", self.r(0x7E037B), 0)
        for item in (0x10, 0x19):
            self.activate()
            self.tap("Start"); self.wait_screen("items"); self.pick(item)
            self.tap("Start"); self.wait_screen("gameplay")
            self.until(lambda: not self.sparks(), "Rod switch retained Byrna shield", 16)
            self.check("Rod switch clears shield flag", self.r(0x7E037B), 0)
            self.check("Rod retains shared action", self.r(0x7E0303), 0x0D)
            if item == 0x10:
                self.tap("Y")
                self.until(lambda: self.r(0x7F5BA2) == 1, "Fishing did not cast")
                self.tap("Y")
                self.until(lambda: self.r(0x7F5BA2) == 0, "Fishing did not retract")
        self.check("Rod upgrade retained", self.r(RODS), 2)
        self.check("Byrna remains independently owned", self.r(BYRNA), 1)
        old_deku, old_binding = self.r(0x7EF349), self.r(0x7EF3A8)
        self.write(0x7EF349, 1, "Disposable Deku mask ownership for shared-action guard")
        self.write(0x7EF3A8, 1, "Disposable R binding for shield-to-mask transition")
        self.activate()
        self.until(lambda: self.r(0x7E037A) == 0 and not (self.r(0x7E003A) & 0x40),
                   "Byrna windup did not finish")
        self.tap("R")
        self.until(lambda: self.r(0x7E02B2) == 1 and not self.sparks(),
                   "R-bound mask retained Byrna shield")
        self.check("Mask keeps Byrna Y selection", self.r(0x7E0202), 0x1B)
        self.check("Mask clears shield flag", self.r(0x7E037B), 0)
        native.require(self.r(0x7E0303) != 0x0D, "Mask did not route its effective action")
        self.until(lambda: self.r(0x7E005D) == 0, "Mask transform did not finish", 200)
        self.tap("R")
        self.until(lambda: self.r(0x7E02B2) in (0, 6) and self.r(0x7E005D) == 0,
                   "R did not return to Link", 200)
        self.write(0x7EF349, old_deku, "Restore declared mask fixture")
        self.write(0x7EF3A8, old_binding, "Restore declared binding fixture")
        self.check("Final unrelated progress", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
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
    native.require(args.socket.startswith("/tmp/mesen2-byrna-") and "oos-rc-play" not in str(args),
                   "Only task-owned Byrna socket admitted")
    native.require(native.digest(args.owned_rom.read_bytes()) == args.rom_sha256, "Private ROM hash differs")
    native.require(native.digest(args.symbols.read_bytes()) == args.symbols_sha256, "Symbols hash differs")
    args.rom_sha1 = native.digest(args.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    native.require("--headless" in command and str(args.owned_rom) in command,
                   "PID is not the explicit headless private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = ByrnaFlow(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
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
