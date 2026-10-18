#!/usr/bin/env python3
"""Attach-only Bombchu supply, native pickup and optional persistence check.

Declared fixtures: ownership, Bombchu counts 1/18, regular bombs 0, and one
originally inactive pickup sprite. State 08 runs native sprite initialization;
controller movement collects it. No Link XY, CPU, story, ROM, direct SRAM or
save-state writes. --save-reopen intentionally saves this private game through
Save/Quit, resets it and reopens file 1. Actor fields restore before saving.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time
from types import SimpleNamespace

sys.dont_write_bytecode = True
import bombchu_world_sprite as art

native, prototype = art.native, art.prototype
OWNED, AMMO, BOMBS, PENDING = 0x7EF3AD, prototype.BOMBCHU_AMMO, prototype.BOMBS, 0x7EF375
# Same native initialization destinations as garo_combat_fixture.TABLES.
TABLES = (0x0B58, 0x0B89, 0x0BA0, 0x0BB0, 0x0BC0, 0x0BE0,
          0x0C9A, 0x0CAA, 0x0CBA, 0x0CD2, 0x0CE2,
          *range(0x0D00, 0x0F51, 0x10), 0x0F60, 0x0F70, 0x0F80, 0x0F90, 0x1CC0)
LONG_TABLES = (0x7FF9C2, 0x7FFA1C, 0x7FFA2C, 0x7FFA3C, 0x7FFA4C)


def describe():
    return dict(native_executed=False, room="0104", fixture="Inventory plus one inactive native pickup sprite slot",
                checks=["Bombchu casts with one supply and zero bombs; zero-supply recast rejected",
                        "DD pack grants five, caps at 20, uses 16x16 mouse art; regular bombs unchanged",
                        "DC/DE and unowned DD retain normal bomb refills",
                        "HUD and selected footer show 00/20; optional native save/reset/reopen retains 20"],
                limitations="Controlled pickup placement; no enemy drop-frequency or route claim")


class SupplyFlow(art.BombchuArtFlow):
    slot = None
    saved_slot = None

    def write(self, address, value, reason):
        native.require(value in {OWNED: (0, 1), AMMO: (1, 18), BOMBS: (0,)}.get(address, ()),
                       "Write outside declared supply fixture")
        self.record(address, value, reason)

    def record(self, address, value, reason):
        self.check_owner(); native.require(self.paused(), "Fixture write requires pause")
        row = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(row)
        native.require(self.b.write_memory(address, value) and self.r(address) == value, "Fixture write/readback failed")

    def actor_write(self, table, value):
        address = 0x7E0000 + table + self.slot
        native.require(address in self.saved_slot, "Write outside owned actor slot")
        self.record(address, value, "Declared native pickup placement")

    def remove_actor(self):
        if self.slot is None: return
        self.actor_write(0x0DD0, 0)
        for address, value in self.saved_slot.items():
            if address != 0x7E0DD0 + self.slot:
                self.record(address, value, "Restore originally inactive pickup slot")
        self.result["fixture_cleanup"].append(dict(slot=self.slot, restored=True))
        self.slot, self.saved_slot = None, None

    def pickup(self, kind, side, expected_chus, expected_bombs):
        self.ready()
        native.require(self.r(0x7E0010) == 7 and self.r(0x7E001B) == 1
                       and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104,
                       "Pickup fixture requires hut104")
        native.require(self.slot is None and self.r(PENDING) == 0 and not self.ancilla(7), "Pickup requires quiet inventory")
        x, y = (int.from_bytes(self.block(a, 2), "little") for a in (0x7E0022, 0x7E0020))
        target_x = x + side * 24
        native.require(0x0940 <= x <= 0x09B0 and 0x0928 <= target_x <= 0x09C8 and 0x2170 <= y <= 0x21B0,
                       f"Link outside hut pickup corridor: {x},{y}")
        free = [s for s in range(15, -1, -1) if self.r(0x7E0DD0 + s) == 0]
        native.require(bool(free), "No unused pickup slot")
        self.slot = free[0]
        self.saved_slot = {a: self.r(a) for a in
            [0x7E0000 + t + self.slot for t in TABLES] + [t + self.slot for t in LONG_TABLES]}
        for table in TABLES:
            if table != 0x0DD0: self.actor_write(table, 0)
        for table, value in ((0x0E20, kind), (0x0D10, target_x & 255), (0x0D30, target_x >> 8),
                             (0x0D00, y & 255), (0x0D20, y >> 8), (0x0F20, self.r(0x7E00EE)),
                             (0x0BC0, 255), (0x0DD0, 8)):
            self.actor_write(table, value)
        self.advance("", 1)
        self.check("Native pickup prep", self.r(0x7E0DD0 + self.slot), 9)
        self.actor_write(0x0B58, 255)  # Same finite lifetime as a native enemy drop.
        self.advance("", 4)
        custom = kind == 0xDD and self.r(OWNED) == 1
        if custom:
            objects = self.oam(0x2E)
            native.require(len(objects) == 1 and objects[0]["large"] and objects[0]["props"] & 0xCF == 4,
                           f"Pack must use page0 palette2 idle 16x16 mouse: {objects}")
            offset = native.pc_offset(self.symbol("BombchuWorldGfx"))
            self.check("Idle pack VRAM matches up frame0", self.tile_bytes((0x2E, 0x2F, 0x3E, 0x3F)).hex(),
                       self.rom[offset:offset + 128].hex())
            self.shot(f"pack-before-collection-{expected_chus}")
        start = [self.r(AMMO), self.r(BOMBS)]
        for _ in range(32):
            if self.r(0x7E0DD0 + self.slot) == 0: break
            self.advance("Right" if side > 0 else "Left", 1)
        self.advance("", 2)
        self.check(f"{kind:02X} controller contact collects", self.r(0x7E0DD0 + self.slot), 0)
        self.until(lambda: self.r(PENDING) == 0, "Native pending bomb refill did not settle", 100)
        self.check(f"{kind:02X} resulting supplies", [self.r(AMMO), self.r(BOMBS)], [expected_chus, expected_bombs])
        self.result.setdefault("pickups", []).append(dict(type=f"{kind:02X}", owned=self.r(OWNED),
            custom=custom, position=[target_x, y], before=start, after=[self.r(AMMO), self.r(BOMBS)]))
        self.remove_actor()

    def count_ui(self, count):
        self.advance("", 4)
        self.check(f"HUD count {count:02d}", [int.from_bytes(self.block(a, 2), "little")
                   for a in (0x7EC7B0, 0x7EC7B2)], [0x2490 | count // 10, 0x2490 | count % 10])
        self.tap("Start"); self.wait_screen("items"); self.pick(0x1C)
        self.check("Selected Bombchu label/count", self.text(9, 26, 14), f"   BOMBCHU  {count:02d}")
        offset = native.pc_offset(self.symbol("TimeLabels")) + count * 4
        self.check("Footer count uses native digit table", self.block(0x7E16AA, 4).hex(), self.rom[offset:offset + 4].hex())
        self.shot(f"supply-count-{count:02d}")
        self.tap("Start"); self.wait_screen("gameplay"); self.ready()

    def save_reopen(self):
        self.check("Save begins with earned capped supply", self.r(AMMO), 20)
        self.tap("Select", 90)
        for _ in range(4):
            if self.r(0x7E1CE8) == 1: break
            self.tap("Down", 15)
        self.check("Controller selects Save and Quit", self.r(0x7E1CE8), 1)
        self.tap("A", 180)
        for _ in range(30):
            if (self.r(0x7E0010), self.r(0x7E0011)) == (0, 8): break
            self.advance("", 60)
        self.check("Native Save/Quit reaches title", [self.r(0x7E0010), self.r(0x7E0011)], [0, 8])
        saved = bytes(self.b.read_block(0, 8192, "SnesSaveRam"))
        native.require(len(saved) == 8192, "Short native SRAM read")
        (self.a.output / "native-save.srm").write_bytes(saved)
        self.check_owner(); native.require(self.b.reset(), "Private reset rejected"); self.b.pause()
        until = time.monotonic() + 5
        while not self.paused() and time.monotonic() < until: time.sleep(.01)
        native.require(self.paused(), "Reset pause did not settle")
        self.advance("", 120)
        for _ in range(60):
            if (self.r(0x7E0010), self.r(0x7E0011)) == (0, 8): break
            self.advance("", 60)
        self.check("Reset reaches title", [self.r(0x7E0010), self.r(0x7E0011)], [0, 8])
        self.tap("Start", 120)
        self.until(lambda: (self.r(0x7E0010), self.r(0x7E0011)) == (1, 5), "File select not ready", 400)
        self.tap("Start", 180); self.wait_screen("gameplay"); self.ready()
        self.check("Native reopen preserves Bombchu ownership/count", [self.r(OWNED), self.r(AMMO)], [1, 20])
        for message in (0x038, 0x15B, 0x15C):
            self.check(f"Reopen tutorial pointer {message:03X}",
                       int.from_bytes(self.block(0x7F71C0 + message * 3, 3), "little"),
                       self.symbol(f"MinishTutorial_{message:03X}"))
        self.shot("supply-fresh-reopen")

    def run(self):
        self.result["scope"] = describe(); self.result["scope"].update(native_executed=True, save_reopen=self.a.save_reopen)
        self.ready()
        native.require(self.r(0x7E02B2) == 0 and self.r(prototype.menu.HP) >= 24
                       and not self.ancilla(7) and self.r(PENDING) == 0, "Need human Link, three hearts and quiet inventory")
        self.write(OWNED, 1, "Declared Bombchu ownership")
        self.write(AMMO, 1, "Last Bombchu fixture"); self.write(BOMBS, 0, "No regular bombs fixture")
        self.equip(0x1C); self.tap("Right", 1); self.tap("Y", 1)
        self.until(lambda: self.r(0x7E07F1) != 0, "One Bombchu with zero regular bombs did not cast", 24)
        self.check("Cast debits only Bombchu supply", [self.r(AMMO), self.r(BOMBS)], [0, 0])
        self.until(lambda: not self.ancilla(7), "Last Bombchu did not finish", 320); self.ready()
        self.tap("Y", 1); self.advance("", 12)
        self.check("Zero supply refuses a second cast", [self.r(AMMO), self.r(BOMBS), self.r(0x7E07F1), len(self.ancilla(7))], [0, 0, 0, 0])
        self.count_ui(0)
        self.pickup(0xDD, 1, 5, 0)
        self.write(AMMO, 18, "Near-cap Bombchu fixture")
        self.pickup(0xDD, -1, 20, 0); self.count_ui(20)
        self.pickup(0xDC, 1, 20, 1); self.pickup(0xDE, -1, 20, 9)
        self.write(OWNED, 0, "Unowned DD control")
        self.write(BOMBS, 0, "Uncapped ordinary-bomb baseline for unowned DD")
        self.pickup(0xDD, 1, 20, 4)
        self.write(OWNED, 1, "Restore owned Bombchu fixture")
        if self.a.save_reopen: self.save_reopen()
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true"); parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--save-reopen", action="store_true")
    parser.add_argument("--session", type=Path); parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.describe: print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output, "Need explicit fixtures, session and output")
    values = json.loads(args.session.read_text())
    for key in ("status_file", "owner_file", "owned_rom", "symbols", "client_root"): values[key] = Path(values[key])
    values.update(output=args.output, save_reopen=args.save_reopen); a = SimpleNamespace(**values)
    native.require(a.socket.startswith("/tmp/mesen2-bombchu-crawl-") and a.owner.startswith("codex-bombchu-crawl-")
                   and "oos-rc-play" not in str(values), "Need task-owned private Bombchu session")
    native.require(native.digest(a.owned_rom.read_bytes()) == a.rom_sha256
                   and native.digest(a.symbols.read_bytes()) == a.symbols_sha256, "Artifact hash mismatch")
    a.rom_sha1 = native.digest(a.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(a.pid)], text=True)
    native.require("--headless" in command and str(a.owned_rom) in command, "PID is not the private ROM process")
    args.output.mkdir(parents=True, exist_ok=False); sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = SupplyFlow(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0)); flow.result["inputs"] = values
    admitted = False
    try:
        flow.check_owner(); native.require(flow.paused() and not flow.b.list_breakpoints(), "Need pause without breakpoints")
        admitted = True; flow.run()
    except Exception as error: flow.result["error"] = repr(error)
    finally:
        if admitted:
            try: flow.check_owner(); flow.input(""); flow.remove_actor()
            except Exception as error: flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
