#!/usr/bin/env python3
"""One attach-only Quest controller flow; caller owns headless launch and cleanup.

Inventory/HP/magic are declared private-session fixtures. No cursor, module,
position, CPU, story, SRAM, save-state or ROM writes. Reuses the existing native
fixture ownership/ROM protocol. --describe is file-only; runtime needs explicit
--execute-fixtures and an already-paused private gameplay session.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import sys
import time

sys.dont_write_bytecode = True
import portal_rod_spawn_return as native

COUNTS = (0x7EF38B, 0x7EF38D, 0x7EF38F, 0x7EF391, 0x7EF393, 0x7EF395)
BOUNDARIES = (0, 59, 60, 99, 100, 255)
COUNT_CELLS = ((20, 14), (24, 14), (20, 17), (24, 17), (20, 20), (24, 20))
HP, MAXHP, MAGIC = 0x7EF36D, 0x7EF36C, 0x7EF36E
CURSOR, MENU, PAGE = 0x7E020C, 0x7E0200, 0x7E0731
PROTECTED = (0x7E0202, 0x7E0303, 0x7E0304, 0x7EF3A3, 0x7EF3A4, 0x7EF3A5,
             0x7EF3A8, 0x7EF3AB, 0x7EF3C5, 0x7EF3D6, 0x7EF3C6, 0x7EF3D7,
             0x7EF3D8, 0x7EF37A, 0x7EF374, 0x7EF410, 0x7E04C6)
ALLOWED = set(COUNTS) | {HP, MAXHP, MAGIC, 0x7EF340, 0x7EF344, 0x7EF34E,
                         0x7EF354, 0x7EF355, 0x7EF356, 0x7EF357,
                         0x7EF359, 0x7EF35A, 0x7EF35B}


def describe():
    return {
        "flow": ["Start, R: Quest without Powder; six count boundaries in one screen",
                 "D-pad visits all six cells and wraps both axes; empty cells selectable",
                 "Banana/Pineapple/Honeycomb success; full/empty/three no-op refusals",
                 "X honors Journal build policy; R/R/R and L/L/L loop all pages",
                 "Moved gear, green Tunic=0, held Sword=FF; Start closes; selections retained"],
        "fixtures": "Only ALLOWED inventory/HP/magic bytes, recorded with readback; caller supplies existing Y/mask/ring selections.",
        "counts": list(BOUNDARIES), "cursor": "7E020C", "native_executed": False,
    }


class QuestFlow(native.Fixture):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 180
        self.result.update(checks=[], screenshots=[], scope=describe())
        self.rom = args.owned_rom.read_bytes()
        self.symbols = args.symbols.read_text()

    def r(self, address):
        return self.b.read_memory(address) & 255

    def check(self, label, actual, expected):
        self.result["checks"].append(dict(name=label, actual=actual, expected=expected, passed=actual == expected))
        native.require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def write(self, address, value, reason):
        self.check_owner()
        native.require(address in ALLOWED and 0 <= value <= 255 and self.paused(), "Fixture outside paused inventory contract")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.r(address)
        native.require(entry["readback"] == value, "Fixture readback differs")

    def advance(self, buttons="", count=2):
        self.check_owner()
        native.require(self.paused(), "Controller FRAME requires paused CPU")
        self.input(buttons)
        before = native.number(self.b.get_rom_info()["frameCount"])
        native.require(self.b.send_command("FRAME", {"count": str(count)}).get("success"), "FRAME rejected")
        until = min(self.deadline, time.monotonic() + 5)
        while time.monotonic() < until:
            after = native.number(self.b.get_rom_info()["frameCount"])
            if after >= before + count and self.paused():
                native.require(after <= before + count + 1, "FRAME overshoot")
                self.result["frame_advances"].append(dict(buttons=buttons, count=count, before=before, after=after))
                return
            time.sleep(.01)
        raise RuntimeError("Controller FRAME timeout")

    def tap(self, button, settle=3):
        self.advance("", 2)
        self.advance(button, 2)
        self.advance("", settle)

    def screen(self):
        if self.r(0x7E0010) != 0x0E:
            return "gameplay"
        if self.r(MENU) == 4:
            return "items"
        if self.r(MENU) == 6:
            return "equipment" if self.r(PAGE) else "quest"
        return f"menu-{self.r(MENU):02X}"

    def wait_screen(self, expected):
        for _ in range(60):
            if self.screen() == expected:
                self.advance("", 2)
                self.check("screen", self.screen(), expected)
                if expected == "gameplay":
                    native.require(self.r(0x7E0010) in (7, 9) and self.r(0x7E0011) == 0,
                                   "Menu did not return to stable gameplay")
                return
            self.advance("", 4)
        raise RuntimeError(f"Timed out awaiting {expected}; got {self.screen()}")

    def shot(self, name):
        data = self.b.screenshot()
        native.require(bool(data), "Missing screenshot")
        path = self.a.output / (name + ".png")
        path.write_bytes(data)
        (self.a.output / (name + ".tilemap.bin")).write_bytes(self.block(0x7E1000, 0x800))
        self.result["screenshots"].append(str(path))

    def words(self, x, y, count):
        blob = self.block(0x7E1000 + (y * 32 + x) * 2, count * 2)
        return [int.from_bytes(blob[i:i + 2], "little") for i in range(0, len(blob), 2)]

    def symbol(self, name):
        matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?" + re.escape(name) + r"\s*$", self.symbols, re.M)
        values = {int(a + b, 16) for a, b in matches}
        native.require(len(values) == 1, "Missing/ambiguous symbol " + name)
        return values.pop()

    def icon(self, name, x, y, table, variant=1):
        pos = native.pc_offset(self.symbol(table)) + (variant - 1) * 8
        expected = [int.from_bytes(self.rom[i:i + 2], "little") for i in range(pos, pos + 8, 2)]
        self.check(name, self.words(x, y, 2) + self.words(x, y + 1, 2), expected)

    def select(self, slot):
        native.require(self.screen() == "quest" and self.r(CURSOR) < 6, "Invalid Quest cursor")
        for _ in range(3):
            if self.r(CURSOR) // 2 == slot // 2:
                break
            self.tap("Down")
        if self.r(CURSOR) % 2 != slot % 2:
            self.tap("Right")
        self.check("selected slot", self.r(CURSOR), slot)

    def use(self, label, slot, count, hp, magic, result_count, result_hp, result_magic):
        self.select(slot)
        for address, value in ((COUNTS[slot], count), (HP, hp), (MAGIC, magic)):
            self.write(address, value, label)
        counts = [self.r(a) for a in COUNTS]
        self.tap("A")
        self.check(label + " stays on Quest", self.screen(), "quest")
        counts[slot] = result_count
        self.check(label + " counts", [self.r(a) for a in COUNTS], counts)
        self.check(label + " HP/magic", [self.r(HP), self.r(MAGIC)], [result_hp, result_magic])

    def run(self):
        self.check("start in gameplay", self.screen(), "gameplay")
        native.require(self.r(0x7E0010) in (7, 9) and self.r(0x7E0011) == 0, "Need stable gameplay, not title/transition")
        for address, value in {0x7EF340: 1, 0x7EF344: 0, 0x7EF34E: 1, MAXHP: 80,
                               0x7EF354: 2, 0x7EF355: 1, 0x7EF356: 1,
                               0x7EF357: 1, 0x7EF359: 4, 0x7EF35A: 3, 0x7EF35B: 0}.items():
            self.write(address, value, "Declared inventory: no Powder, Book, moved gear, green tunic")
        for address, value in zip(COUNTS, BOUNDARIES):
            self.write(address, value, "Six count-domain boundaries in one Quest screen")
        self.tap("Start"); self.wait_screen("items")
        protected = {str(a): self.r(a) for a in PROTECTED}
        self.result["protected_before"] = protected
        self.tap("R"); self.wait_screen("quest")
        self.check("Powder absent", self.r(0x7EF344), 0)
        self.check("Quest entry cursor", self.r(CURSOR), 0)
        self.shot("quest-count-boundaries")
        for value, (x, y) in zip(BOUNDARIES, COUNT_CELLS):
            expected = [0x2417 if c == " " else 0x2570 + int(c) for c in f"{value:3d}"]
            self.check(f"decimal {value}", self.words(x, y, 3), expected)
        for button, slot in [("Right", 1), ("Down", 3), ("Down", 5), ("Left", 4),
                             ("Up", 2), ("Up", 0), ("Up", 4), ("Down", 0), ("Left", 1), ("Right", 0)]:
            self.tap(button); self.check("grid " + button, self.r(CURSOR), slot)
        self.use("Banana heal", 0, 2, 40, 64, 1, 56, 64)
        self.use("Pineapple refill", 1, 2, 56, 64, 1, 56, 128)
        self.use("Honeycomb cap", 4, 2, 76, 128, 1, 80, 128)
        self.use("Full health", 0, 2, 80, 128, 2, 80, 128)
        self.use("Full magic", 1, 2, 80, 128, 2, 80, 128)
        self.use("Empty Banana", 0, 0, 40, 64, 0, 40, 64)
        for slot, label in ((2, "Rock Meat info"), (3, "Seashell info"), (5, "Deku Stick info")):
            self.use(label, slot, 5, 40, 64, 5, 40, 64)
        cursor = self.r(CURSOR)
        counts = [self.r(a) for a in COUNTS]
        self.tap("X")
        if self.a.journal == "deferred":
            self.check("Journal remains deferred", self.screen(), "quest")
        else:
            self.wait_screen("menu-0E")
            self.tap("A"); self.wait_screen("quest")
        self.check("Journal retains cursor", self.r(CURSOR), cursor)
        self.check("Journal retains counts", [self.r(a) for a in COUNTS], counts)
        self.tap("R"); self.wait_screen("equipment")
        for name, x, table, variant in (("Sword", 17, "SwordGFX", 4), ("Shield", 20, "ShieldGFX", 3),
                                        ("Green Tunic", 23, "TunicGFX", 1)):
            self.icon(name, x, 22, table, variant)
        self.icon("Moon Pearl", 23, 18, "MoonPearlGFX")
        self.shot("equipment-moved-gear-green-tunic")
        self.write(0x7EF359, 255, "Smith-held sword sentinel, display must be bounded")
        self.advance("", 3)
        self.icon("Held sword is unavailable", 17, 22, "NothingGFX")
        self.shot("equipment-held-sword")
        for button, target in [("R", "items"), ("R", "quest"), ("L", "items"),
                               ("L", "equipment"), ("L", "quest")]:
            self.tap(button); self.wait_screen(target)
        self.check("Page changes retain counts", [self.r(a) for a in COUNTS], counts)
        self.check("Selections/story after menu navigation", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.tap("Start"); self.wait_screen("gameplay")
        self.check("Selections/story after Start", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    for key in ("socket", "rom-sha256", "symbols-sha256", "owner"):
        parser.add_argument("--" + key)
    for key in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output"):
        parser.add_argument("--" + key, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--journal", choices=("deferred", "enabled"), default="deferred")
    parser.add_argument("--execute-fixtures", action="store_true")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures, "Use --describe or explicitly --execute-fixtures")
    native.require(all(getattr(args, name) for name in ("socket", "rom_sha256", "symbols_sha256", "owner", "owned_rom", "symbols", "client_root", "status_file", "owner_file", "output", "pid")), "Missing explicit private-session identity")
    native.require(args.socket.startswith("/tmp/mesen2-quest-") and "oos-rc-play" not in str(args), "Only task-owned quest socket admitted")
    native.require(native.digest(args.owned_rom.read_bytes()) == args.rom_sha256, "Private ROM hash differs")
    native.require(native.digest(args.symbols.read_bytes()) == args.symbols_sha256, "Symbols hash differs")
    args.rom_sha1 = native.digest(args.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    native.require("--headless" in command and str(args.owned_rom) in command, "PID is not the explicit headless private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = QuestFlow(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = vars(args)
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused private session with no breakpoints")
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
