#!/usr/bin/env python3
"""Attach-only native proof of the compiled Somaria socket-door room tag.

The caller owns launch, the heavy lock, a paused private headless House 0x104
session and process disposal. This fixture never launches or stops Mesen, loads
or saves states, resets, changes PC or registers, runs Lua, or writes ROM. It
refuses a candidate whose tag $24 entry (RoomTag_Holes2, $01CC89) is not
JML $2CFD00, or whose pinned dispatcher/handler/return bytes or symbols differ,
before touching the runtime.

Each case spends one natural frame: Underworld_HandleRoomTags ($01C2FD), the
declared tag fixture AE=$24/AF=$00, the tag hook $01CC89 on its real JSR stack,
injected switch/ancilla fields, the compiled handler $2CFD00, the pre-RTS
boundary $01CC5A and the post-RTS boundary $01C310. Injected fields and handler
outputs are restored at $01C310, tags at $01C31B, before any other frame code
runs. Owned WRAM write/read breakpoints watch the handler window.

Scope: compiled handler with synthetic tag, switch and cube state. It is not a
naturally cast cane, real pressure plate or door traversal acceptance.
--describe is source-only; runtime needs explicit --execute-fixtures.
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
sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_rod_spawn_return as native  # noqa: E402

require, number, digest, pc_offset = native.require, native.number, native.digest, native.pc_offset

DISPATCH = 0x01C2FD
TAG_SLOT0_RETURN = 0x01C310
DISPATCH_END = 0x01C31B
HOOK = 0x01CC89
HANDLER = 0x2CFD00
TAG_RETURN = 0x01CC5A
CALLER_RETURN_STACK = bytes.fromhex("C88702")        # JSL $01C2FD at $0287C5
HOOK_STACK = bytes.fromhex("0FC3") + CALLER_RETURN_STACK
SLOT1_RETURN_LOW = 0x1A                              # JSR (.vectors,X) at $01C318

HANDLER_BYTES = bytes.fromhex(
    "e230a51bf03aad4606f0352c08033030adf403d02ba204bd4a0cc92cd01fbd9403d01a"
    "bdc503d015bd8003d010bddb03c904d009bd9e02f00ec9fff00aca10d7c230a201008005"
    "c230a20000ec6804f0188e68049c8e069c9006e230e000d005a9258d2f01a9058511e230"
    "5c5acc01")
HOOK_JML = bytes.fromhex("5c00fd2c")
UNHOOKED_HOLES2 = bytes.fromhex("c23020cc")
PINNED = (
    (0x01C2FD, "adc704d019e2302029c3640ea5ae0aaafc7dc2a901850ea5af0aaafc7dc29cc7046b",
     "Underworld_HandleRoomTags through RTL"),
    (0x01C2C5, "89cc", "tag $24 vector -> RoomTag_Holes2 $01CC89"),
    (0x01C27D, "28c3", "tag $00 vector -> RoomTag_Nothing $01C328"),
    (0x01C328, "60", "RoomTag_Nothing RTS"),
    (0x01CC5A, "60", "RoomTag_Return RTS"),
    (0x0287C1, "a511d01c22fdc201a511d014", "Module07_Underworld $11 gates and JSL"),
    (HANDLER, HANDLER_BYTES.hex(), "RoomTag_SomariaSocketDoor compiled body"),
)
STX_DOOR = HANDLER + 0x51
LDA_SOMBTN = HANDLER + 0x06

LOW_WRAM = 0x2000
WRAM_END = 0x1FFFF
TAGS = (0x00AE, 0x00AF)
GLOBALS = (0x0646, 0x0308, 0x03F4, 0x0642)
SLOT_FIELDS = (0x0C4A, 0x0394, 0x03C5, 0x0380, 0x03DB, 0x029E)
OUTPUTS = (0x0468, 0x0469, 0x068E, 0x068F, 0x0690, 0x0691, 0x012F, 0x0011)
ADMITTED = frozenset(TAGS + GLOBALS + SLOT_FIELDS + OUTPUTS)
QUALIFYING = {0x0C4A: 0x2C, 0x0394: 0x00, 0x03C5: 0x00, 0x0380: 0x00, 0x03DB: 0x04, 0x029E: 0x00}
SENTINELS = {0x068E: 0xA5, 0x068F: 0x5A, 0x0690: 0x3C, 0x0691: 0xC3}
EXPECTED = {
    "open": {0x0468: 0, 0x0469: 0, 0x068E: 0, 0x068F: 0, 0x0690: 0, 0x0691: 0,
             0x012F: 0x25, 0x0011: 0x05},
    "close": {0x0468: 1, 0x0469: 0, 0x068E: 0, 0x068F: 0, 0x0690: 0, 0x0691: 0,
              0x0011: 0x05},
    "none": {},
}
READ_WATCH = (
    (0x0020, 0x0023, "Link coordinates"),
    (0x004D, 0x004D, "Link auxiliary state"),
    (0x02E4, 0x02E4, "Link control lock"),
    (0x0466, 0x0467, "push-block switch latch"),
    (0x0478, 0x0479, "push-block count"),
    (0x0500, 0x055F, "push-block table"),
    (0x0642, 0x0642, "ordinary/Stone switch signal"),
    (0xF340, 0xF3FF, "inventory and progress mirror"),
    (0x12000, 0x13FFF, "Link floor collision map"),
)


def case(name, door, expect, globals_=None, slot=None, controls=False):
    values = {0x0646: 0x01, 0x0308: 0x00, 0x03F4: 0x00, 0x0642: 0x00}
    values.update(globals_ or {})
    fields = dict(QUALIFYING)
    fields.update(slot or {})
    return {"name": name, "door": door, "expect": expect, "globals": values,
            "slot0": fields, "controls": controls}


CASES = (
    case("open-closed-door", 1, "open", controls=True),
    case("unchanged-open", 0, "none"),
    case("stale-0646-closes", 0, "close", slot={0x0C4A: 0x00}),
    case("unchanged-closed", 1, "none", globals_={0x0646: 0x00}, slot={0x0C4A: 0x00}),
    case("altitude-ff-opens", 1, "open", slot={0x029E: 0xFF}),
    case("reject-lifted", 0, "close", slot={0x0380: 0x03}),
    case("reject-airborne", 0, "close", slot={0x029E: 0x10}),
    case("reject-fizzled", 0, "close", slot={0x0C4A: 0x2D}),
    case("reject-spawn-delay", 0, "close", slot={0x0394: 0x03}),
    case("reject-bouncing", 0, "close", slot={0x03C5: 0x01}),
    case("reject-three-probes", 0, "close", slot={0x03DB: 0x03}),
    case("reject-link-carrying", 0, "close", globals_={0x0308: 0x80}),
    case("reject-transit-lines", 0, "close", globals_={0x03F4: 0x02}),
    case("reject-0642-stone-link", 0, "close", globals_={0x0646: 0x00, 0x0642: 0x01},
         slot={0x0C4A: 0x00}),
)


def case_writes(row):
    """Ordered (address, value) fixture writes made at the tag hook pause."""
    writes = [(0x0468, row["door"]), (0x0469, 0x00)]
    writes += sorted(SENTINELS.items()) + [(0x012F, 0x00)]
    writes += list(row["globals"].items())
    writes += [(table, row["slot0"][table]) for table in SLOT_FIELDS]
    return writes


def write_watch(allowed):
    """WRAM ranges (inclusive) covering every byte the handler may not write."""
    ranges, start = [], 0
    for address in sorted(allowed):
        if address > start:
            ranges.append((start, address - 1, "write"))
        start = address + 1
    if start <= WRAM_END:
        ranges.append((start, WRAM_END, "write"))
    return ranges


def symbol(text, name):
    found = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?" + re.escape(name) + r"\s*$",
                       text, re.MULTILINE)
    values = {int(bank + offset, 16) for bank, offset in found}
    require(len(values) == 1, "Missing or ambiguous symbol " + name)
    return values.pop()


def validate_candidate(rom, symbols):
    """Offline identity of the wired candidate; raises before any runtime access."""
    def raw(address, length):
        offset = pc_offset(address)
        require(offset + length <= len(rom), f"ROM too short for {address:06X}")
        return rom[offset:offset + length]

    require(symbol(symbols, "RoomTag_SomariaSocketDoor") == HANDLER,
            "Handler symbol is not RoomTag_SomariaSocketDoor at $2CFD00")
    require(symbol(symbols, "RoomTag_Return") == TAG_RETURN, "RoomTag_Return symbol is not $01CC5A")
    hook = raw(HOOK, 4)
    require(hook != UNHOOKED_HOLES2, "Unhooked candidate: $01CC89 is still vanilla RoomTag_Holes2")
    require(hook == HOOK_JML, f"Wrong tag $24 hook at $01CC89: {hook.hex()} (need JML $2CFD00)")
    for address, expected, label in PINNED:
        require(raw(address, len(expected) // 2).hex() == expected, f"Pinned bytes differ: {label}")
    return {"hook": "01CC89 JML 2CFD00", "handler": f"{HANDLER:06X}", "handler_size": len(HANDLER_BYTES),
            "pinned": [label for _, _, label in PINNED]}


def describe():
    return {
        "claim": "native compiled RoomTag_SomariaSocketDoor with synthetic tag, switch and cube state",
        "not_claimed": ["naturally cast Cane of Somaria", "real pressure plate probe",
                        "door traversal, shutter animation or room geometry", "GetEssenceCount"],
        "boundaries": {"dispatcher": "01C2FD", "tag_hook": "01CC89", "handler": "2CFD00",
                       "pre_rts": "01CC5A", "post_rts": "01C310", "dispatcher_end": "01C31B"},
        "expected_stacks": {"dispatcher_sp+1..3": CALLER_RETURN_STACK.hex(),
                            "tag_hook_sp+1..5": HOOK_STACK.hex()},
        "fixture_points": {"01C2FD": "write AE=24 AF=00 (original values recorded)",
                           "01CC89": "write declared door/sentinel/SFX/global/slot0 fields",
                           "01C310": "restore injected fields and handler outputs; low WRAM must equal tag-hook snapshot",
                           "01C31B": "restore AE/AF; only $0E and the slot1 JSR stack byte may differ"},
        "admitted_wram": sorted(f"{a:04X}" for a in ADMITTED),
        "read_watch": [(f"{lo:05X}", f"{hi:05X}", label) for lo, hi, label in READ_WATCH],
        "write_watch": "all WRAM except the case's expected output bytes; full WRAM for unchanged cases",
        "breakpoint_control": "first case: read of $0646 and write of $0468 must each stop inside the handler",
        "cases": [{"name": row["name"], "expect": row["expect"],
                   "writes": {f"{a:04X}": v for a, v in case_writes(row)},
                   "expected_handler_writes": {f"{a:04X}": v for a, v in EXPECTED[row["expect"]].items()}}
                  for row in CASES],
        "pinned_bytes": [(f"{a:06X}", b, label) for a, b, label in PINNED] + [("01CC89", HOOK_JML.hex(), "hook")],
        "native_executed": False,
    }


class SomariaDoorFixture(native.Fixture):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 300
        self.dirty = {}
        self.result.update(claim=describe()["claim"], breakpoint_log=[], restores=[])

    def check_owner(self):
        info = super().check_owner()
        status = json.loads(self.a.status_file.read_text())
        if status.get("romHash"):
            require(str(status["romHash"]).lower() == self.a.rom_sha1.lower(), "Status ROM hash mismatch")
        return info

    def rd(self, address):
        reply = self.b.send_command("READ", {"addr": f"0x{0x7E0000 | address:06X}"})
        require(reply.get("success"), f"READ {address:04X} rejected")
        return int(str(reply.get("data")).replace('"', "").replace("0x", ""), 16) & 0xFF

    def low(self):
        return self.block(0x7E0000, LOW_WRAM)

    def stack(self, sp, count):
        return self.block(0x7E0000 + sp + 1, count)

    def frame(self):
        reply = self.b.send_command("STATE")
        require(reply.get("success"), "STATE rejected")
        data = reply.get("data", {})
        return (json.loads(data) if isinstance(data, str) else data).get("frame")

    def write(self, address, value, reason, at=None):
        require(address in ADMITTED and 0 <= value <= 255, f"Forbidden fixture write: {address:04X}")
        require(self.paused(), "Fixture write requires a paused CPU")
        pc = number(self.cpu()["pc"])
        require(at is None or pc == at, f"Fixture write at {pc:06X}, admitted only at {at:06X}")
        before = self.rd(address)
        self.dirty.setdefault(address, before)
        entry = {"address": f"{address:04X}", "before": before, "value": value,
                 "reason": reason, "pc": f"{pc:06X}"}
        self.result["writes"].append(entry)
        require(self.b.write_memory(0x7E0000 | address, value), "Fixture write rejected")
        entry["readback"] = self.rd(address)
        require(entry["readback"] == value, f"Fixture readback mismatch: {address:04X}")

    def restore(self, addresses, reason, at=None):
        for address in reversed([a for a in self.dirty if a in addresses]):
            original = self.dirty[address]
            current = self.rd(address)
            if current == original:
                self.result["restores"].append({"address": f"{address:04X}", "value": original,
                                                "reason": reason, "skipped": "already original"})
            else:
                self.write(address, original, reason, at)
            del self.dirty[address]

    def add_bp(self, address, kind="exec", end=None, memtype="SnesMemory"):
        ident = self.b.add_breakpoint(address, bptype=kind, end_address=end, memtype=memtype)
        require(isinstance(ident, int) and ident >= 0, "Could not install owned breakpoint")
        self.breakpoints.add(ident)
        self.result["breakpoint_log"].append({"id": ident, "addr": f"{address:06X}", "kind": kind,
                                              "end": None if end is None else f"{end:06X}",
                                              "memtype": memtype})
        return ident

    def run_until(self, targets, watches=(), accept=None):
        """Resume to an exec target; any other stop (watch hit) is returned for checking."""
        self.check_owner()
        require(self.paused(), "Resume requires a paused CPU")
        state = self.cpu()
        start = number(state["pc"])
        if start in targets:
            return state
        ids = []
        try:
            ids += [self.add_bp(target) for target in targets]
            ids += [self.add_bp(lo, kind, hi, "wram") for lo, hi, kind in watches]
            require(self.b.resume(), "Native resume rejected")
            until = min(self.deadline, time.monotonic() + 5)
            while time.monotonic() < until:
                if self.paused():
                    state = self.cpu()
                    pc = number(state["pc"])
                    if pc != start and self.paused():
                        break
                time.sleep(0.005)
            else:
                self.b.pause()
                raise RuntimeError(f"Stop timeout: expected {[f'{t:06X}' for t in targets]}, CPU {self.cpu()}")
        finally:
            for ident in ids:
                if ident in self.breakpoints:
                    self.remove(ident)
        admitted = pc in targets or (accept is not None and accept[0] <= pc <= accept[1])
        require(admitted, f"Unexpected stop at {pc:06X} (owned watch hit or foreign stop): {state}")
        return state

    def same_cpu(self, a, b, keys, label):
        differ = [k for k in keys if number(a[k]) != number(b[k])]
        require(not differ, f"{label}: CPU {differ} differ ({a} vs {b})")

    def snapshot(self, row, phase, data):
        path = self.a.output / f"{row['name']}-{phase}.bin"
        path.write_bytes(data)
        row["snapshots"][phase] = path.name

    def run_case(self, spec):
        row = {"name": spec["name"], "expect": spec["expect"], "passed": False, "snapshots": {}}
        self.result["cases"].append(row)
        for _ in range(3):
            dispatch = self.run_until({DISPATCH})
            if self.rd(0x04C7) == 0:
                break
            self.run_until({DISPATCH_END})
        else:
            raise RuntimeError("Room tags stayed suppressed ($04C7) for three frames")
        row["frame"], row["dispatch_cpu"] = self.frame(), dispatch
        sp0 = number(dispatch["sp"])
        row["dispatch_stack"] = self.stack(sp0, 3).hex()
        require(self.stack(sp0, 3) == CALLER_RETURN_STACK, "Dispatcher not entered from Module07 JSL $0287C5")
        require((self.rd(0x10), self.rd(0x11)) == (7, 0) and self.b.read_memory16(0x7E00A0) == 0x104
                and self.rd(0x1B) != 0, "Fixture requires indoor House 0104 module 07/00")
        row["tags_before"] = [self.rd(a) for a in TAGS]
        self.write(0x00AE, 0x24, "tag fixture: slot0 Somaria socket door", DISPATCH)
        self.write(0x00AF, 0x00, "tag fixture: slot1 RoomTag_Nothing", DISPATCH)

        hook = self.run_until({HOOK})
        sp = number(hook["sp"])
        row.update(hook_cpu=hook, hook_stack=self.stack(sp, 5).hex())
        require(sp == sp0 - 2 and self.stack(sp, 5) == HOOK_STACK,
                "Tag hook is not on the dispatcher's slot0 JSR stack (return $01C310)")
        require(number(hook["p"]) & 0x30 == 0x30 and number(hook["d"]) == 0
                and (number(hook["dbr"]) & 0x7F) < 0x40, "Tag hook ABI is not M8/X8/D0 with low-WRAM DBR")
        require(self.rd(0x11) == 0 and self.rd(0x0E) == 0, "Tag hook without $11=00/$0E=00 cadence")
        require(all(self.rd(0x0C4A + s) != 0x2C for s in range(5)), "A real Somaria block occupies slots 0-4")
        hook_snap = self.low()
        self.snapshot(row, "hook", hook_snap)
        for address in OUTPUTS:
            self.dirty.setdefault(address, hook_snap[address])
        writes = case_writes(spec)
        for address, value in writes:
            self.write(address, value, f"{spec['name']} fixture", HOOK)

        entry = self.run_until({HANDLER})
        row["entry_cpu"], row["entry_stack"] = entry, self.stack(sp, 5).hex()
        self.same_cpu(hook, entry, ("a", "x", "y", "sp", "d", "dbr", "p"), "JML to handler")
        entry_snap = self.low()
        self.snapshot(row, "entry", entry_snap)
        injected = bytearray(hook_snap)
        for address, value in writes:
            injected[address] = value
        row["injection_diff"] = native_diff(hook_snap, entry_snap)
        require(entry_snap == bytes(injected), "Handler entry WRAM differs from hook snapshot plus fixtures")

        expected = EXPECTED[spec["expect"]]
        watches = write_watch(expected) + [(lo, hi, "read") for lo, hi, _ in READ_WATCH]
        row["watches"] = [(f"{lo:05X}", f"{hi:05X}", kind) for lo, hi, kind in watches]
        if spec["controls"]:
            row["control_read_0646"] = self.run_until({TAG_RETURN}, watches + [(0x0646, 0x0646, "read")],
                                                      accept=(LDA_SOMBTN, LDA_SOMBTN + 3))
            require(number(row["control_read_0646"]["pc"]) != TAG_RETURN, "Read breakpoint control did not fire")
            control = [w for w in watches if w[2] == "read"] + write_watch(set(expected) - {0x0468, 0x0469})
            row["control_write_0468"] = self.run_until({TAG_RETURN}, control, accept=(STX_DOOR, STX_DOOR + 3))
            require(number(row["control_write_0468"]["pc"]) != TAG_RETURN, "Write breakpoint control did not fire")
        pre = self.run_until({TAG_RETURN}, watches)
        row["pre_rts_cpu"], row["pre_rts_stack"] = pre, self.stack(number(pre["sp"]), 5).hex()
        require(number(pre["p"]) & 0x30 == 0x30, "Handler exit is not M8/X8")
        self.same_cpu(entry, pre, ("y", "sp", "d", "dbr"), "Handler preserved state")
        require(row["pre_rts_stack"] == row["entry_stack"], "Handler changed its JSR/JSL stack bytes")
        pre_snap = self.low()
        self.snapshot(row, "pre-rts", pre_snap)
        wanted = bytearray(entry_snap)
        for address, value in expected.items():
            wanted[address] = value
        row["handler_diff"] = native_diff(entry_snap, pre_snap)
        row["scratch_preserved"] = (pre_snap[:0x10] == entry_snap[:0x10]
                                    and all(pre_snap[a] == entry_snap[a] for a in TAGS))
        require(pre_snap == bytes(wanted), f"Handler WRAM result differs from {spec['expect']} expectation")
        require(row["scratch_preserved"], "Handler changed scratch $00-$0F or tag bytes")

        post = self.run_until({TAG_SLOT0_RETURN})
        row["post_rts_cpu"] = post
        require(number(post["sp"]) == number(pre["sp"]) + 2, "Actual RTS did not pop the slot0 JSR return")
        self.same_cpu(pre, post, ("y", "d", "dbr"), "RTS")
        post_snap = self.low()
        self.snapshot(row, "post-rts", post_snap)
        require(post_snap == pre_snap, "RTS boundary changed WRAM")

        self.restore(set(self.dirty) - set(TAGS), "restore injected fields and handler outputs", TAG_SLOT0_RETURN)
        restored = self.low()
        self.snapshot(row, "restored", restored)
        row["restore_diff"] = native_diff(hook_snap, restored)
        require(restored == hook_snap, "Restored low WRAM differs from natural tag-hook snapshot")

        end = self.run_until({DISPATCH_END})
        row["dispatch_end_cpu"] = end
        require(number(end["sp"]) == number(post["sp"]), "Slot1 RoomTag_Nothing unbalanced the stack")
        self.restore(set(TAGS), "restore room tags", DISPATCH_END)
        final = self.low()
        self.snapshot(row, "dispatch-end", final)
        settled = bytearray(hook_snap)
        settled[0x0E], settled[sp + 1] = 0x01, SLOT1_RETURN_LOW
        for address, value in zip(TAGS, row["tags_before"]):
            settled[address] = value
        row["end_diff"] = native_diff(hook_snap, final)
        require(final == bytes(settled), "Dispatcher end WRAM differs beyond $0E, slot1 return and restored tags")
        require(not self.dirty, "Fixture bytes remain dirty after case")
        row["passed"] = True

    def cleanup(self):
        errors = self.result["cleanup_errors"]
        try:
            self.check_owner()
        except BaseException as error:
            errors.append("Ownership check refused cleanup: " + repr(error))
            return
        for step in (self.b.pause, lambda: self.input("")):
            try:
                require(step() is not False, "Owned cleanup action rejected")
            except BaseException as error:
                errors.append(repr(error))
        for ident in list(self.breakpoints):
            try:
                self.remove(ident)
            except BaseException as error:
                errors.append(repr(error))
        try:
            if self.dirty:
                self.result["fixture_cleanup"].append({"dirty": {f"{a:04X}": v for a, v in self.dirty.items()}})
                self.restore(set(self.dirty), "failure-path restore of admitted fixture bytes")
        except BaseException as error:
            errors.append(repr(error))
        try:
            listed = self.b.send_command("BREAKPOINT", {"action": "list"})
            require(listed.get("success"), "Breakpoint list rejected during cleanup")
            remaining = (listed.get("data") or {}).get("breakpoints", [])
            require(not remaining, f"Breakpoints remain after owned cleanup: {remaining}")
        except BaseException as error:
            errors.append(repr(error))


def native_diff(before, after):
    return [{"addr": f"{i:04X}", "before": b, "after": a}
            for i, (b, a) in enumerate(zip(before, after)) if a != b]


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--describe", action="store_true", help="print the source-only plan and exit")
    parser.add_argument("--validate-candidate", action="store_true",
                        help="offline ROM/symbol identity check only; no socket")
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"):
        parser.add_argument("--" + name)
    for name in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--execute-fixtures", action="store_true")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.describe:
        print(json.dumps(describe(), indent=2))
        return 0
    if args.validate_candidate:
        require(args.owned_rom and args.symbols, "--validate-candidate needs --owned-rom and --symbols")
        try:
            report = {"candidate_ok": True, **validate_candidate(args.owned_rom.read_bytes(),
                                                                 args.symbols.read_text())}
        except RuntimeError as error:
            report = {"candidate_ok": False, "error": str(error)}
        print(json.dumps(report, indent=2))
        return 0 if report["candidate_ok"] else 2
    require(args.execute_fixtures, "Use --describe, --validate-candidate or explicitly --execute-fixtures")
    identity = ("socket", "rom_sha256", "symbols_sha256", "owner", "owned_rom", "symbols",
                "client_root", "status_file", "owner_file", "output", "pid")
    require(all(getattr(args, name) for name in identity) and args.pid > 0,
            "Missing explicit private-session identity")
    require(args.socket.startswith("/tmp/mesen2-") and "oos-rc-play" not in " ".join(map(str, vars(args).values())),
            "Only a task-owned private socket is admitted")
    rom, symbols = args.owned_rom.read_bytes(), args.symbols.read_bytes()
    require(digest(rom) == args.rom_sha256.lower(), "Private ROM SHA256 mismatch")
    require(digest(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 mismatch")
    rom_sha1 = digest(rom, "sha1")
    if args.rom_sha1:
        require(rom_sha1 == args.rom_sha1.lower(), "Private ROM SHA1 mismatch")
    code = validate_candidate(rom, symbols.decode())
    args.rom_sha1 = rom_sha1
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    require("--headless" in command and str(args.owned_rom) in command,
            "PID is not the explicit headless private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = SomariaDoorFixture(args, bridge)
    fixture.result.update(inputs={k: str(v) for k, v in vars(args).items()}, code=code,
                          source_sha256=digest(Path(__file__).read_bytes()))
    admitted = False
    try:
        fixture.check_owner()
        require(fixture.paused(), "Caller must provide a paused private session")
        listed = bridge.send_command("BREAKPOINT", {"action": "list"})
        require(listed.get("success") and not (listed.get("data") or {}).get("breakpoints"),
                "Existing breakpoints or unreadable list: refuse shared debug session")
        admitted = True
        fixture.input("")
        for spec in CASES:
            fixture.run_case(spec)
        fixture.result["runtime_checks_passed"] = True
    except BaseException as error:
        fixture.result["error"] = repr(error)
        if admitted:
            try:
                bridge.pause()
                fixture.result["failure_cpu"] = fixture.cpu()
                (args.output / "failure-low-wram.bin").write_bytes(fixture.low())
            except BaseException as capture_error:
                fixture.result["failure_capture_error"] = repr(capture_error)
    finally:
        if admitted:
            fixture.cleanup()
        for path, expected, label in ((args.owned_rom, args.rom_sha256, "ROM"),
                                      (args.symbols, args.symbols_sha256, "Symbols")):
            if digest(path.read_bytes()) != expected.lower():
                fixture.result["cleanup_errors"].append(f"{label} file changed")
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed")
                                        and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": fixture.result["passed"], "result": str(args.output / "RESULT.json")}))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
