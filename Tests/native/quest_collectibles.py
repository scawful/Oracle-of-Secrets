#!/usr/bin/env python3
"""One attach-only Equipment/Quest flow; caller owns headless launch and cleanup.

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
SUPPLY_NAMES = ("BANANA", "PINEAPPLE", "ROCK MEAT", "SEASHELL", "HONEYCOMB", "DEKU STICK")
HP, MAXHP, MAGIC = 0x7EF36D, 0x7EF36C, 0x7EF36E
CURSOR, MENU, PAGE = 0x7E020B, 0x7E0200, 0x7E0731
PROTECTED = (0x7E0202, 0x7E0303, 0x7E0304, 0x7EF3A3, 0x7EF3A4, 0x7EF3A5,
             0x7EF3A8, 0x7EF3AB, 0x7EF3C5, 0x7EF3D6, 0x7EF3C6, 0x7EF3D7,
             0x7EF3D8, 0x7EF37A, 0x7EF374, 0x7EF410, 0x7E04C6)
ALLOWED = set(COUNTS) | {HP, MAXHP, MAGIC, 0x7EF340, 0x7EF344, 0x7EF34E,
                         0x7EF354, 0x7EF355, 0x7EF356, 0x7EF357,
                         0x7EF359, 0x7EF35A, 0x7EF35B}


def describe():
    return {
        "flow": ["Start, L: Equipment without Powder; all six supply slots including zero selectable",
                 "Full singular names and counts 0/59/60/99/100/255 in the 14-character footer; contextual A:USE",
                 "Y cannot consume; A food success, last-item retention, full/empty/three no-op refusals",
                 "R/L loop Items/Quest/Equipment; Quest gear, green Tunic=0, held Sword=FF and Pearl",
                 "Equipment Start and informational Quest A close; Y/mask/ring selections retained"],
        "fixtures": "Only ALLOWED inventory/HP/magic bytes, recorded with readback; caller supplies existing Y/mask/ring selections.",
        "counts": list(BOUNDARIES), "cursor": "7E020B, supply slots15..20", "native_executed": False,
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

    def text(self, x, y, count):
        # Existing menu glyphs; underscore and interior-fill tiles are spaces.
        chars = {0x2550 + i: chr(65 + i) for i in range(26)}
        chars.update({0x2570 + i: str(i) for i in range(10)})
        chars.update({0x256A: ".", 0x256B: ":", 0x20F5: " ", 0x2417: " ", 0x3417: " "})
        return "".join(chars.get(word, "?") for word in self.words(x, y, count))

    def supply_footer(self, slot):
        count = self.r(COUNTS[slot])
        self.check("full supply name/count footer", self.text(9, 26, 14),
                   f"{SUPPLY_NAMES[slot]:<10}{count:3d} ")
        cue = "A:USE" if slot in (0, 1, 4) and count > 0 else "     "
        self.check("contextual supply action", self.text(20, 21, 5), cue)

    def select(self, slot):
        native.require(self.screen() == "equipment" and 0 <= slot < 6, "Need Equipment supply slot")
        # Reach the supply row by ordinary vertical navigation; do not test or
        # change the existing mask/ring/song actions on the way.
        for _ in range(4):
            if 15 <= self.r(CURSOR) <= 20:
                break
            self.tap("Up")
        native.require(15 <= self.r(CURSOR) <= 20, "Supply row was not reachable")
        for _ in range(6):
            if self.r(CURSOR) == slot + 15:
                break
            self.tap("Right")
        self.check("selected supply slot", self.r(CURSOR), slot + 15)

    def use(self, label, slot, count, hp, magic, result_count, result_hp, result_magic):
        self.select(slot)
        for address, value in ((COUNTS[slot], count), (HP, hp), (MAGIC, magic)):
            self.write(address, value, label)
        counts = [self.r(a) for a in COUNTS]
        self.advance("", 2)
        self.supply_footer(slot)
        self.tap("A")
        self.check(label + " stays on Equipment", self.screen(), "equipment")
        self.check(label + " restores supply cursor", self.r(CURSOR), slot + 15)
        counts[slot] = result_count
        self.check(label + " counts", [self.r(a) for a in COUNTS], counts)
        self.check(label + " HP/magic", [self.r(HP), self.r(MAGIC)], [result_hp, result_magic])
        self.supply_footer(slot)

    def run(self):
        self.check("start in gameplay", self.screen(), "gameplay")
        native.require(self.r(0x7E0010) in (7, 9) and self.r(0x7E0011) == 0, "Need stable gameplay, not title/transition")
        for address, value in {0x7EF340: 1, 0x7EF344: 0, 0x7EF34E: 1, MAXHP: 80, HP: 40, MAGIC: 64,
                               0x7EF354: 2, 0x7EF355: 1, 0x7EF356: 1,
                               0x7EF357: 1, 0x7EF359: 4, 0x7EF35A: 3, 0x7EF35B: 0}.items():
            self.write(address, value, "Declared inventory: no Powder, Book, Quest gear, green tunic")
        for address, value in zip(COUNTS, BOUNDARIES):
            self.write(address, value, "Six count-domain boundaries, selected in Equipment footer")
        self.tap("Start"); self.wait_screen("items")
        protected = {str(a): self.r(a) for a in PROTECTED}
        self.result["protected_before"] = protected
        self.tap("L"); self.wait_screen("equipment")
        self.check("Powder absent", self.r(0x7EF344), 0)
        for slot in range(6):
            self.select(slot)
            self.supply_footer(slot)
        self.tap("Right"); self.check("Supply row wraps through empty Banana", self.r(CURSOR), 15)
        self.icon("Empty Banana remains visible", 7, 22, "BananaGFX")
        self.tap("Left"); self.check("Supply row wraps left", self.r(CURSOR), 20)
        self.select(1)
        self.shot("equipment-pineapple-name-count-action")

        self.select(0)
        self.write(COUNTS[0], 1, "One Banana makes Y-versus-A and last-item behavior observable")
        self.advance("", 2)
        before_y = [self.r(a) for a in (*COUNTS, HP, MAGIC, CURSOR)]
        self.tap("Y")
        self.check("Y does not consume or move supply cursor", [self.r(a) for a in (*COUNTS, HP, MAGIC, CURSOR)], before_y)
        self.check("Y preserves equipped selections", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.use("Last Banana heal", 0, 1, 40, 64, 0, 56, 64)
        self.use("Pineapple refill", 1, 2, 56, 64, 1, 56, 128)
        self.use("Honeycomb cap", 4, 2, 76, 128, 1, 80, 128)
        self.use("Full health", 0, 2, 80, 128, 2, 80, 128)
        self.use("Full magic", 1, 2, 80, 128, 2, 80, 128)
        self.use("Empty Banana", 0, 0, 40, 64, 0, 40, 64)
        for slot, label in ((2, "Rock Meat info"), (3, "Seashell info"), (5, "Deku Stick info")):
            self.use(label, slot, 5, 40, 64, 5, 40, 64)
        counts = [self.r(a) for a in COUNTS]
        self.check("Supply actions preserve equipped selections", {str(a): self.r(a) for a in PROTECTED}, protected)

        self.tap("R"); self.wait_screen("items")
        self.tap("R"); self.wait_screen("quest")
        for name, x, y, table, variant in (
                ("Glove", 18, 13, "PowerGloveGFX", 2), ("Boots", 21, 13, "PegasusBootsGFX", 1),
                ("Flippers", 24, 13, "FlippersGFX", 1), ("Sword", 18, 17, "SwordGFX", 4),
                ("Shield", 21, 17, "ShieldGFX", 3), ("Green Tunic", 24, 17, "TunicGFX", 1)):
            self.icon(name, x, y, table, variant)
        self.icon("Moon Pearl", 19, 21, "MoonPearlGFX")
        self.check("Quest GEAR label", self.text(19, 12, 4), "GEAR")
        self.check("Old PEARL label area is blank", self.text(20, 20, 5), "     ")
        hearts = self.r(0x7EF36B)
        heart_tiles = [0x24AD if hearts else 0x2484, 0x64AD if hearts == 3 else 0x6484,
                       0x24AE if hearts >= 2 else 0x2485, 0x6485]
        self.check("Heart icon beside Pearl", self.words(23, 21, 2) + self.words(23, 22, 2), heart_tiles)
        self.check("Heart count below pair", self.text(22, 23, 3), f"{hearts:3d}")
        self.check("Old heart icon area is blank", self.text(24, 9, 2) + self.text(24, 10, 2), "    ")
        self.check("Old heart count area is blank", self.text(24, 11, 3), "   ")
        for x, bit in ((8, 0x04), (12, 0x20)):
            tile = 0x3534 if self.r(0x7EF37A) & bit else 0x3134
            self.check(f"Bottom essence at ({x},20)", self.words(x, 20, 2) + self.words(x, 21, 2),
                       [tile, tile + 1, tile + 0x10, tile + 0x11])
        native.require(self.text(6, 9, 8) != "LOCATION", "Quest still has redundant LOCATION label")
        for x in (6, 8):
            native.require(self.text(x, 21, 7) != "DUNGEON", "Quest still has redundant DUNGEON label")
        footer = self.text(9, 26, 14)
        native.require(footer[:7].strip() and footer[7:9] == "  " and re.fullmatch(r"[0-9]{2}:[0-9]{2}", footer[9:]),
                       "Quest footer must contain seven name cells, two blanks and HH:MM")
        self.result["quest_name_clock_footer"] = footer
        self.shot("quest-gear-green-tunic-name-clock")

        self.write(0x7EF359, 255, "Smith-held sword sentinel, display must be bounded")
        # Quest is informational; leave and re-enter to invoke its real redraw.
        self.tap("R"); self.wait_screen("equipment")
        self.tap("L"); self.wait_screen("quest")
        self.icon("Held sword is unavailable", 18, 17, "NothingGFX")
        self.tap("X")
        if self.a.journal == "deferred":
            self.check("Journal remains deferred", self.screen(), "quest")
        else:
            self.wait_screen("menu-0E")
            self.tap("A"); self.wait_screen("quest")
        self.check("Journal retains counts", [self.r(a) for a in COUNTS], counts)
        self.tap("L"); self.wait_screen("items")
        self.tap("L"); self.wait_screen("equipment")
        self.check("Page cycle retains counts", [self.r(a) for a in COUNTS], counts)
        self.check("Page cycle retains selections/story", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.tap("Start"); self.wait_screen("gameplay")
        self.check("Equipment Start retains selections/story", {str(a): self.r(a) for a in PROTECTED}, protected)
        self.tap("Start"); self.wait_screen("items")
        self.tap("R"); self.wait_screen("quest")
        self.tap("A"); self.wait_screen("gameplay")
        self.check("Informational Quest A retains counts", [self.r(a) for a in COUNTS], counts)
        self.check("Informational Quest A retains selections/story", {str(a): self.r(a) for a in PROTECTED}, protected)
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
