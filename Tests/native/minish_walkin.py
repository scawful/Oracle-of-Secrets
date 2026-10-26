#!/usr/bin/env python3
"""Attach-only Minish walk-in fixture; caller owns headless launch/cleanup.

Temporarily replaces a 12x9 collision patch around the existing hut position
with tile64 and adds a six-column floor strip on its right. Restores all cells
in finally. No XY, CPU, actor, progression, SRAM, save-state or ROM writes.
--gbc also fixtures mask6/state17/gfx3B after leaving the portal, then restores
those three original bytes. Separate --passage mode uses adjacent64/65 columns:
human blocked, controller shrink, Minish crossing.
No normal-route or Loom tiny-house claim; no Y or R input is sent.
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
import quest_collectibles as menu

native = menu.native
MASK, STATE, GFX = 0x7E02B2, 0x7E005D, 0x7E00BC


def describe():
    return dict(native_executed=False, fixtures="Restored 18x9 collision patch at $7F2000; optional restored GBC mask/state/gfx",
                checks=["D-pad-held contact shrinks without Y", "Idle and movement on portal retain Minish",
                        "Menu roundtrip does not rearm", "Leaving and reentering grows; optional GBC contact shrinks"],
                passage="Separate --passage: human65 barrier,64 shrink,Minish65 crossing; no form writes",
                limitations="Collision fixture in hut104; no route, tiny-house entrance or save/reopen qualification")


class MinishFlow(menu.QuestFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 600

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

    def sample(self, label):
        row = dict(label=label, xy=[int.from_bytes(self.block(a, 2), "little") for a in (0x7E0022, 0x7E0020)],
                   mask=self.r(MASK), state=self.r(STATE), gfx=self.r(GFX), latch=self.r(0x7E07EC),
                   inputs={f"{a:02X}": self.r(0x7E0000 + a) for a in (0xF0, 0xF2, 0xF4, 0xF6)},
                   requested_buttons=self.result["frame_advances"][-1]["buttons"] if self.result["frame_advances"] else None)
        self.result.setdefault("trace", []).append(row)
        return row

    def patch(self):
        native.require((self.r(0x7E0010), self.r(0x7E0011), self.r(0x7E00EE)) == (7, 0, 0)
                       and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104,
                       "Need stable hut104 on collision layer0")
        row = self.sample("start")
        c, r = ((v & 0x1FF) // 8 for v in row["xy"])
        native.require(6 <= c <= 51 and 3 <= r <= 58, "Current position cannot fit bounded collision fixture")
        self.edge = (row["xy"][0] & ~0x1FF) + (c + 6) * 8
        self.barrier = (row["xy"][0] & ~0x1FF) + (c + 2) * 8
        self.cells = {0x7F2000 + y * 64 + c - 6: self.block(0x7F2000 + y * 64 + c - 6, 18)
                      for y in range(r - 3, r + 6)}
        self.patch_value = bytes([0x64] * 2 + [0] * 6 + [0x65] * 2 + [0] * 8 if self.a.passage else [0x64] * 12 + [0] * 6)
        self.write_rows(self.patch_value, "Declared portal/passage collision fixture")

    def write_rows(self, value, reason):
        for address in self.cells:
            previous = self.block(address, 18)
            self.check_owner(); native.require(self.paused(), "Collision fixture requires paused CPU")
            self.result["writes"].append(dict(address=f"{address:06X}", before=previous.hex(), value=value.hex(), reason=reason))
            native.require(self.b.write_block(address, value) and self.block(address, 18) == value, "Collision patch rejected")

    def walk_form(self, button, expected, frames=12):
        for _ in range(frames // 2):
            self.advance(button, 2)
            if self.sample(button)["mask"] == expected:
                self.advance("", 2)
                self.check("Contact form survives following frames", self.r(MASK), expected)
                return
        raise RuntimeError(f"Held {button} did not reach form{expected} within {frames} frames")

    def leave(self):
        for _ in range(40):
            if self.sample("leave")["xy"][0] >= self.edge + 16:
                break
            self.advance("Right", 4)
            self.check("Moving within portal does not toggle", self.r(MASK), 5)
        native.require(self.sample("outside")["xy"][0] >= self.edge + 16, "Could not leave portal by controller")
        self.advance("", 8)
        self.check("Four eligible absent frames rearm", self.r(0x7E07EC) & 0x80, 0)

    def run(self):
        self.result["scope"] = describe(); self.result["scope"]["native_executed"] = True
        self.result["mode"] = "passage" if self.a.passage else "portal"
        passage_scope = self.result["scope"].pop("passage")
        if self.a.passage:
            self.result["scope"]["checks"] = [passage_scope]
            self.result["scope"]["fixtures"] = "Restored18x9 collision patch only; no form writes"
        self.ready()
        native.require(self.r(MASK) == 0 and self.r(0x7EF3C5) != 0, "Need ordinary Link and active progression")
        self.patch()
        if self.a.passage:
            self.passage(); self.result["runtime_checks_passed"] = True
            return
        self.walk_form("Right", 5)
        self.ready(); self.advance("", 72)
        self.check("Lingering does not auto-grow", self.r(MASK), 5)
        self.advance("Right", 6); self.advance("Left", 6)
        self.check("Movement within portal does not rearm", self.r(MASK), 5)
        self.tap("Start"); self.wait_screen("items")
        self.advance("", 12)
        self.tap("Start"); self.wait_screen("gameplay")
        self.advance("", 12)
        self.check("Menu roundtrip retains form", self.r(MASK), 5)
        self.check("Menu roundtrip retains visit latch", bool(self.r(0x7E07EC) & 0x80), True)
        self.shot("minish-lingering-after-menu")
        self.leave()
        self.walk_form("Left", 0, 80)
        self.ready(); self.advance("", 20)
        self.check("Reentry grows and stays grown", self.r(MASK), 0)
        self.shot("minish-grown-after-reentry")
        if self.a.gbc:
            for _ in range(40):
                if self.sample("gbc-exit")["xy"][0] >= self.edge + 16: break
                self.advance("Right", 4)
            native.require(self.sample("gbc-outside")["xy"][0] >= self.edge + 16, "GBC setup must be off portal")
            self.advance("", 8)
            self.gbc_restore = {a: self.r(a) for a in (MASK, STATE, GFX)}
            for address, value in {MASK: 6, STATE: 0x17, GFX: 0x3B}.items():
                self.check_owner(); native.require(self.paused(), "GBC fixture requires paused CPU")
                self.result["writes"].append(dict(address=f"{address:06X}", before=self.gbc_restore[address], value=value, reason="Declared GBC form fixture"))
                native.require(self.b.write_memory(address, value) and self.r(address) == value, "GBC fixture rejected")
            self.walk_form("Left", 5, 80)
            self.shot("gbc-walk-in-shrink")
        self.result["runtime_checks_passed"] = True

    def passage(self):
        self.advance("Right", 24)
        stopped = self.sample("human-at65")["xy"][0]
        native.require(stopped < self.barrier, "Human crossed65 barrier")
        self.advance("Right", 8)
        self.check("Human remains blocked by65", self.sample("human-still-blocked")["xy"][0], stopped)
        self.check("Barrier attempt retains human form", self.r(MASK), 0)
        self.shot("human-blocked-by65")
        self.walk_form("Left", 5, 80)
        self.check("Transformation cloud freezes input", self.r(0x7E02E1), 1)
        stopped = self.sample("poof-before-reverse")["xy"][0]
        self.advance("Right", 8)
        self.check("Poof cancels the previous walking velocity", self.sample("poof-after-reverse")["xy"][0], stopped)
        self.check("Poof preserves portal visit", bool(self.r(0x7E07EC) & 0x80), True)
        for _ in range(40):
            if self.sample("minish-cross65")["xy"][0] >= self.barrier + 18: break
            self.advance("Right", 4)
            self.check("Passage movement retains Minish", self.r(MASK), 5)
        native.require(self.sample("past65")["xy"][0] >= self.barrier + 18, "Minish did not cross the same65 barrier")
        self.shot("minish-past65-barrier")

    def restore(self):
        self.check_owner(); self.input("")
        native.require(self.paused(), "Fixture restoration requires pause")
        native.require(self.r(0x7E0010) in (7, 0x0E) and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104,
                       "Room changed; collision restoration withheld")
        for address, value in getattr(self, "cells", {}).items():
            native.require(self.b.write_block(address, value) and self.block(address, len(value)) == value, "Collision restore failed")
            self.result["fixture_cleanup"].append(dict(address=f"{address:06X}", restored=value.hex()))
        for address, value in getattr(self, "gbc_restore", {}).items():
            native.require(self.b.write_memory(address, value) and self.r(address) == value, "GBC restore failed")
            self.result["fixture_cleanup"].append(dict(address=f"{address:06X}", restored=value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("describe", "execute-fixtures", "gbc", "passage"):
        parser.add_argument("--" + flag, action="store_true")
    for flag in ("session", "output"):
        parser.add_argument("--" + flag, type=Path)
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output, "Need --execute-fixtures, --session and --output")
    native.require(not (args.gbc and args.passage), "--passage is a separate run from --gbc")
    values = json.loads(args.session.read_text())
    for key in ("status_file", "owner_file", "owned_rom", "symbols", "client_root"):
        values[key] = Path(values[key])
    values.update(output=args.output, gbc=args.gbc, passage=args.passage)
    a = SimpleNamespace(**values)
    native.require(a.socket.startswith(("/tmp/mesen2-minish-", "/tmp/mesen2-cursor-minish-", "/tmp/mesen2-bombchu-world-"))
                   and a.owner.startswith(("codex-minish-", "cursor-minish-", "codex-bombchu-world-")) and "oos-rc-play" not in str(values), "Need task-owned private session")
    native.require(native.digest(a.owned_rom.read_bytes()) == a.rom_sha256 and native.digest(a.symbols.read_bytes()) == a.symbols_sha256, "Artifact hash mismatch")
    a.rom_sha1 = native.digest(a.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(a.pid)], text=True)
    native.require("--headless" in command and str(a.owned_rom) in command, "PID is not the private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = MinishFlow(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = values
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused session without breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.restore()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
