#!/usr/bin/env python3
"""Attach-only native regression for Portal Rod's sprite-allocation return.

The caller owns cold boot, the resource reservation and process cleanup. Supply
an already paused, private House 0x104 session and explicitly authorize fixture
writes. This test never launches/stops Mesen, loads a state, or sets CPU/Link
position/health. Every rod/magic/sprite fixture write is recorded and read back.

The primary assertion runs from the actual Y-button JSL through the allocator to
the immediate return boundary. RTS and RTL builds are both admitted; RTS must
fail with the retained wrong-bank PC and one remaining return-bank stack byte.
Fixture actors are removed before advancing native animation frames. Recovery
and the separate positive control install fresh occupancy fixtures, leaving one
slot free; they do not test portal placement/lifetime after the helper returns.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import time


CALL = 0x07A52B
RETURN = 0x07A52F
SPRITES = 0x7E0B00
SPRITE_SIZE = 0x500


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def digest(data, algorithm="sha256"):
    return hashlib.new(algorithm, data).hexdigest()


def pc_offset(address):
    require(address & 0x8000, f"Not a LoROM ROM address: {address:06X}")
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def helper_address(symbols):
    matches = re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+"
        r"(?:Oracle_)?LinkItem_FirePortal\s*$", symbols, re.MULTILINE)
    addresses = {int(bank + offset, 16) for bank, offset in matches}
    require(len(addresses) == 1, "Missing or ambiguous LinkItem_FirePortal symbol")
    return addresses.pop()


def validate_code(rom, helper):
    def raw(address, length):
        offset = pc_offset(address)
        return rom[offset:offset + length]
    require(raw(CALL, 4) == b"\x22" + helper.to_bytes(3, "little"),
            "Portal Rod caller JSL does not match the pinned helper symbol")
    require(raw(helper, 8) == bytes.fromhex("A903225DF61D1001"),
            "Unexpected allocator prefix/negative branch ABI")
    require(raw(helper + 8, 1) in (b"\x60", b"\x6b"),
            "Failure return is neither baseline RTS nor candidate RTL")
    require(raw(0x1DF65D, 14) == bytes.fromhex("A00F48B9D00DF0068810F868986B"),
            "Unexpected full-slot allocator read-only failure path")
    return {"helper": f"{helper:06X}", "failure_opcode": raw(helper + 8, 1).hex(),
            "caller": f"{CALL:06X}", "return": f"{RETURN:06X}"}


class Fixture:
    def __init__(self, args, bridge):
        self.a, self.b = args, bridge
        self.breakpoints = set()
        self.result = {"passed": False, "cases": [], "writes": [], "frame_advances": [],
                       "fixture_cleanup": [], "cleanup_errors": []}
        self.deadline = time.monotonic() + 120

    def check_owner(self):
        require(time.monotonic() < self.deadline, "120-second fixture deadline exceeded")
        text = self.a.owner_file.read_text()
        try:
            owner = json.loads(text)["owner"]
        except (ValueError, KeyError, TypeError):
            owner = next((line.split("=", 1)[1] for line in text.splitlines()
                          if line.startswith("owner=")), None)
        require(owner == self.a.owner, "Resource owner changed")
        status = json.loads(self.a.status_file.read_text())
        require(number(status["pid"]) == self.a.pid, "Status PID does not match owned PID")
        require(status["socketPath"] == self.a.socket, "Status socket does not match explicit socket")
        os.kill(self.a.pid, 0)
        info = self.b.get_rom_info()
        require(str(info.get("sha1", "")).lower() == self.a.rom_sha1.lower(),
                "Loaded ROM SHA1 mismatch")
        return info

    def paused(self):
        reply = self.b.send_command("STATE")
        require(reply.get("success"), "Cannot read native pause state")
        state = reply.get("data", {})
        if isinstance(state, str):
            state = json.loads(state)
        require("paused" in state, "Native pause state is unknown")
        return state["paused"] is True

    def block(self, address, size):
        data = self.b.read_block(address, size)
        require(len(data) == size, f"Short read at {address:06X}")
        return bytes(data)

    def cpu(self):
        state = self.b.get_cpu_state()
        require(state and "pc" in state and "sp" in state, "Missing CPU state")
        return state

    def write(self, address, value, reason):
        # Deliberately closed fixture whitelist: rod/equip/magic and sprite RAM.
        allowed = {0x7EF351, 0x7EF3A6, 0x7E0202, 0x7E0303,
                   0x7E0304, 0x7EF36E, 0x7E06FE, 0x7E0FA6}
        sprite_tables = {0x0DD0, 0x0E20, 0x0D00, 0x0D10, 0x0D20, 0x0D30,
                         0x0D40, 0x0D50, 0x0D80, 0x0E30, 0x0EE0, 0x0CAA}
        allowed_sprite = any(0x7E0000 + table <= address < 0x7E0010 + table
                             for table in sprite_tables)
        require(address in allowed or allowed_sprite, f"Forbidden fixture write: {address:06X}")
        require(self.paused(), "Fixture write requires a paused CPU")
        before = self.b.read_memory(address)
        entry = {"address": f"{address:06X}", "before": before,
                 "value": value, "reason": reason}
        self.result["writes"].append(entry)
        require(self.b.write_memory(address, value), "Fixture write rejected")
        entry["readback"] = self.b.read_memory(address)
        require(entry["readback"] == value, f"Fixture readback mismatch: {address:06X}")

    def input(self, buttons):
        reply = self.b.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"})
        require(reply.get("success"), "Native controller INPUT rejected")

    def add(self, address):
        ident = self.b.add_breakpoint(address)
        require(isinstance(ident, int) and ident >= 0, "Could not install owned breakpoint")
        self.breakpoints.add(ident)
        return ident

    def remove(self, ident):
        require(self.b.remove_breakpoint(ident), "Could not remove owned breakpoint")
        self.breakpoints.remove(ident)

    def wait_pc(self, addresses):
        until = min(self.deadline, time.monotonic() + 5)
        while time.monotonic() < until:
            state = self.cpu()
            if number(state["pc"]) in addresses and self.paused():
                return state
            time.sleep(0.01)
        self.b.pause()
        raise RuntimeError(f"Breakpoint timeout: expected {sorted(addresses)}, CPU {self.cpu()}")

    def run_to(self, addresses):
        ids = [self.add(address) for address in addresses]
        require(self.b.resume(), "Native resume rejected")
        try:
            return self.wait_pc(addresses)
        finally:
            for ident in ids:
                self.remove(ident)

    def neutral_frames(self, count):
        self.check_owner()
        require(self.paused(), "Neutral frame advance requires paused CPU")
        self.input("")
        before = number(self.b.get_rom_info()["frameCount"])
        reply = self.b.send_command("FRAME", {"count": str(count)})
        require(reply.get("success"), "FRAME rejected")
        until = min(self.deadline, time.monotonic() + 5)
        while time.monotonic() < until:
            now = number(self.b.get_rom_info()["frameCount"])
            if now >= before + count and self.paused():
                require(now <= before + count + 1, "Unexpected frame overshoot")
                self.result["frame_advances"].append({"buttons": "", "requested": count,
                                                      "before": before, "after": now})
                return
            time.sleep(0.01)
        raise RuntimeError("Neutral FRAME timeout")

    def prepare(self, free_slot=None):
        require(self.b.read_memory(0x7E0010) == 7 and self.b.read_memory(0x7E0011) == 0,
                "Fixture requires normal indoor module 07/00")
        require(self.b.read_memory16(0x7E00A0) == 0x104, "Fixture requires cold House 0104")
        require(self.b.read_memory(0x7E006C) == 0, "Doorway state blocks ordinary Y cast")
        for address, value in ((0x7EF351, 2), (0x7EF3A6, 1), (0x7E0202, 0x19),
                               (0x7E0303, 0x0D), (0x7E0304, 0x0D),
                               (0x7EF36E, 0x80), (0x7E06FE, 0), (0x7E0FA6, 0)):
            self.write(address, value, "equip Portal Rod and magic fixture")
        x = (self.b.read_memory16(0x7E0022) + 0x30) & 0xFFFF
        y = (self.b.read_memory16(0x7E0020) - 0x10) & 0xFFFF
        for slot in range(16):
            self.write(0x7E0DD0 + slot, 0, "pause sprite while preparing occupancy")
            fields = {0x0E20: 3, 0x0D10: x & 255, 0x0D30: x >> 8,
                      0x0D00: y & 255, 0x0D20: y >> 8,
                      0x0D40: 0, 0x0D50: 0, 0x0D80: 1,
                      0x0E30: 2, 0x0EE0: 0x40, 0x0CAA: 0x40}
            for table, value in fields.items():
                self.write(0x7E0000 + table + slot, value, "controlled occupancy actor")
            self.write(0x7E0DD0 + slot, 9, "occupy sprite slot")
        if free_slot is not None:
            self.write(0x7E0DD0 + free_slot, 0, "release one allocator slot")

    def cast(self, name, helper, failure):
        self.check_owner()
        case = {"name": name, "expected_failure": failure, "passed": False}
        self.result["cases"].append(case)
        ident = self.add(CALL)
        self.input("Y")
        require(self.b.resume(), "Y-cast resume rejected")
        try:
            case["caller_cpu"] = self.wait_pc({CALL})
        finally:
            self.remove(ident)
        self.input("")
        before = self.block(SPRITES, SPRITE_SIZE)
        case["selectors_before"] = {f"{address:06X}": self.b.read_memory(address)
                                    for address in (0x7E0FA6, 0x7E06FE)}
        (self.a.output / f"{name}-before-sprites.bin").write_bytes(before)
        states = self.block(0x7E0DD0, 16)
        require(states == (bytes([9] * 16) if failure else bytes([9] * 15 + [0])),
                "Occupancy changed before the actual native JSL")
        caller_sp = number(case["caller_cpu"]["sp"])
        case["helper_cpu"] = self.run_to({helper})
        entry_sp = number(case["helper_cpu"]["sp"])
        stack = self.block(0x7E0000 + entry_sp + 1, 3)
        case["long_return_stack"] = stack.hex()
        require(entry_sp == caller_sp - 3 and stack == bytes.fromhex("2EA507"),
                "Actual JSL did not push the expected three-byte banked return")
        require(number(case["helper_cpu"]["d"]) == 0, "Unexpected direct page ABI")
        require(number(case["helper_cpu"]["p"]) & 0x30 == 0x30
                and number(case["helper_cpu"]["dbr"]) == 7,
                "Expected native M8/X8/DBR07 Portal Rod ABI")
        if failure:
            case["negative_cpu"] = self.run_to({helper + 8})
            require(number(case["negative_cpu"]["y"]) & 255 == 255
                    and number(case["negative_cpu"]["a"]) & 255 == 255
                    and number(case["negative_cpu"]["p"]) & 0x80,
                    "Allocator did not report the native negative sentinel")
        wrong_bank = (helper & 0xFF0000) | (RETURN & 0xFFFF)
        case["return_cpu"] = self.run_to({RETURN, wrong_bank})
        after = self.block(SPRITES, SPRITE_SIZE)
        case["selectors_after"] = {f"{address:06X}": self.b.read_memory(address)
                                   for address in (0x7E0FA6, 0x7E06FE)}
        (self.a.output / f"{name}-after-sprites.bin").write_bytes(after)
        case["sprite_changed_offsets"] = [i for i, (a, b) in enumerate(zip(before, after)) if a != b]
        # Save these before asserting, so the baseline wrong-bank failure is useful evidence.
        case["return_pc_ok"] = number(case["return_cpu"]["pc"]) == RETURN
        case["return_sp_ok"] = number(case["return_cpu"]["sp"]) == caller_sp
        require(case["return_pc_ok"] and case["return_sp_ok"],
                "Allocation return corrupted long-call bank/stack (RTS instead of RTL)")
        if failure:
            require(before == after, "Failed allocation changed sprite/indexed RAM")
            require(case["selectors_before"] == case["selectors_after"],
                    "Failed allocation changed Portal selectors")
        else:
            for table in (0x0DD0, 0x0E20, 0x0D00, 0x0D10, 0x0D20, 0x0D30):
                offset = table - 0x0B00
                require(before[offset:offset + 15] == after[offset:offset + 15],
                        f"Successful allocation changed another actor table {table:04X}")
            require(self.b.read_memory(0x7E0DD0 + 15) == 9
                    and self.b.read_memory(0x7E0E20 + 15) == 3
                    and self.b.read_memory(0x7E0BA0 + 15) == 255,
                    "Released slot did not receive the native Portal spawn")
        case["passed"] = True

    def clear_fixture_and_settle(self):
        self.result["fixture_cleanup"].append({"reason": "remove controlled actors before native animation frames"})
        for slot in range(16):
            self.write(0x7E0DD0 + slot, 0, "fixture cleanup, separate from allocation proof")
        self.neutral_frames(90)
        require(self.b.read_memory(0x7E003A) & 0x40 == 0
                and self.b.read_memory(0x7E0300) == 0,
                "Native Y animation did not finish after fixture cleanup")


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"):
        parser.add_argument("--" + name, required=True)
    for name in ("status-file", "owned-rom", "symbols", "client-root", "owner-file", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    parser.add_argument("--pid", required=True, type=int)
    parser.add_argument("--execute-fixtures", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    require(args.execute_fixtures, "Fixture writes require --execute-fixtures")
    require(args.pid > 0, "An explicit positive owned PID is required")
    rom = args.owned_rom.read_bytes()
    symbols = args.symbols.read_bytes()
    require(digest(rom) == args.rom_sha256.lower(), "Private ROM SHA256 mismatch")
    require(digest(rom, "sha1") == args.rom_sha1.lower(), "Private ROM SHA1 mismatch")
    require(digest(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 mismatch")
    helper = helper_address(symbols.decode())
    code = validate_code(rom, helper)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = Fixture(args, bridge)
    fixture.result.update({"inputs": vars(args) | {"code": code},
                           "source_sha256": digest(Path(__file__).read_bytes()),
                           "claim": "native allocation return/spawn only; controlled fixture actors"})
    owned = False
    try:
        fixture.check_owner()
        require(fixture.paused(), "Caller must provide a paused private session")
        require(not bridge.list_breakpoints(), "Existing breakpoints: refuse shared debug session")
        owned = True
        fixture.neutral_frames(2)
        fixture.prepare()
        fixture.cast("full16-failure", helper, failure=True)
        fixture.clear_fixture_and_settle()
        fixture.prepare(free_slot=15)
        fixture.cast("post-failure-released-slot-recovery", helper, failure=False)
        fixture.clear_fixture_and_settle()
        fixture.prepare(free_slot=15)
        fixture.cast("fresh15-positive-control", helper, failure=False)
        fixture.result["runtime_checks_passed"] = True
    except BaseException as error:
        fixture.result["error"] = repr(error)
        if owned:
            try:
                bridge.pause()
                fixture.result["failure_cpu"] = fixture.cpu()
                (args.output / "failure-sprites.bin").write_bytes(fixture.block(SPRITES, SPRITE_SIZE))
            except BaseException as capture_error:
                fixture.result["failure_capture_error"] = repr(capture_error)
    finally:
        if owned:
            for action in (lambda: fixture.input(""), bridge.pause):
                try:
                    require(action() is not False, "Owned cleanup action rejected")
                except BaseException as error:
                    fixture.result["cleanup_errors"].append(repr(error))
            for ident in list(fixture.breakpoints):
                try:
                    fixture.remove(ident)
                except BaseException as error:
                    fixture.result["cleanup_errors"].append(repr(error))
        try:
            require(digest(args.owned_rom.read_bytes()) == args.rom_sha256.lower(), "Private ROM changed")
            require(digest(args.symbols.read_bytes()) == args.symbols_sha256.lower(), "Symbols changed")
        except BaseException as error:
            fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed")
                                        and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": fixture.result["passed"], "result": str(args.output / "RESULT.json")}))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
