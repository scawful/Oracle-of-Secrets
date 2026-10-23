#!/usr/bin/env python3
"""Attach-only Phase A proof of the compiled tag-$37 cart shutter hook.

The caller owns launch, the heavy lane and a paused private House $104 session.
Four synthetic flag/shutter cases run through the real room-tag JSR dispatcher.
No PC/register writes, reset, state load/save, ROM writes or process launch occur.
Injected WRAM and handler outputs are restored before normal frame code resumes.
This does not qualify boarding, shutter animation, traversal or reclose behavior.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import somaria_socket_door as dispatch  # noqa: E402

require, number, digest = dispatch.require, dispatch.number, dispatch.digest
DISPATCH, POST_RTS, DISPATCH_END = 0x01C2FD, 0x01C310, 0x01C31B
HOOK, TAG_RETURN = 0x01CC14, 0x01CC5A
TAGS = (0xAE, 0xAF)
OUTPUTS = (0x0468, 0x0469, 0x068E, 0x068F, 0x0690, 0x0691, 0x012F, 0x0011)
ADMITTED = frozenset(TAGS + (0x35, 0x36) + OUTPUTS)
UNHOOKED = bytes.fromhex("a90c8006")
HANDLER_BYTES = bytes.fromhex(
    "ad3500f020c230a20000ec6804f0149c68049c8e069c9006e230a91b8d2f01a9058511"
    "e2305c5acc01")
PINNED = (
    (DISPATCH, "adc704d019e2302029c3640ea5ae0aaafc7dc2a901850ea5af0aaafc7dc29cc7046b",
     "room-tag dispatcher"),
    (0x01C2EB, "14cc", "tag $37 vector"),
    (0x01C2E5, "08cc", "neighbor crumble tag $34 vector"),
    (0x01C2E9, "10cc", "neighbor Minish tag $36 vector"),
    (0x01C27D, "28c3", "tag $00 vector"),
    (0x01C328, "60", "RoomTag_Nothing RTS"),
    (TAG_RETURN, "60", "RoomTag_Return RTS"),
    (0x0287C1, "a511d01c22fdc201a511d014", "normal module-07 tag caller"),
)
OPEN = {0x0468: 0, 0x0469: 0, 0x068E: 0, 0x068F: 0, 0x0690: 0, 0x0691: 0,
        0x012F: 0x1B, 0x0011: 0x05}
CASES = (
    {"name": "unmounted-closed", "mounted": 0, "door": 1, "open": False},
    {"name": "mounted-closed-opens", "mounted": 1, "door": 1, "open": True},
    {"name": "mounted-already-open", "mounted": 1, "door": 0, "open": False},
    {"name": "unmounted-already-open", "mounted": 0, "door": 0, "open": False},
)


def validate_candidate(rom, symbols):
    """Resolve the handler, then bind the compiled hook and body before attach."""
    handler = dispatch.symbol(symbols, "RoomTag_ShutterDoorRequiresCart")
    require(0 <= handler <= 0xFFFFFF and handler & 0x8000
            and (handler >> 16) & 0x7F not in (0x7E, 0x7F),
            "Cart shutter handler is not a LoROM code address")
    require(dispatch.symbol(symbols, "RoomTag_Return") == TAG_RETURN,
            "RoomTag_Return symbol is not $01CC5A")

    def raw(address, size):
        offset = dispatch.pc_offset(address)
        require(offset + size <= len(rom), f"ROM too short for {address:06X}")
        return rom[offset:offset + size]

    hook = raw(HOOK, 4)
    require(hook != UNHOOKED, "Unhooked candidate: tag $37 remains vanilla Holes6")
    require(hook == b"\x5c" + handler.to_bytes(3, "little"),
            "Tag $37 hook is not JML to the resolved cart shutter handler")
    for address, expected, label in PINNED:
        require(raw(address, len(expected) // 2).hex() == expected,
                "Pinned bytes differ: " + label)
    require(raw(handler, len(HANDLER_BYTES)) == HANDLER_BYTES,
            "Compiled cart shutter body differs from the source contract")
    return {"hook": f"{HOOK:06X}", "handler": f"{handler:06X}",
            "handler_size": len(HANDLER_BYTES), "handler_sha256": digest(HANDLER_BYTES),
            "return": f"{TAG_RETURN:06X}", "pinned": [p[2] for p in PINNED]}


def case_writes(spec):
    return {0x35: spec["mounted"], 0x36: 0xA5, 0x0468: spec["door"], 0x0469: 0,
            0x068E: 0xA5, 0x068F: 0x5A, 0x0690: 0x3C, 0x0691: 0xC3,
            0x012F: 0, 0x0011: 0}


def watches(expected):
    # The handler may read only the byte flag and (when mounted) shutter word.
    # Reading adjacent $36 would expose an accidental M16 flag read.
    read = [(lo, hi, "read") for lo, hi, _ in dispatch.write_watch({0x35, 0x0468, 0x0469})]
    return dispatch.write_watch(expected) + read


def describe():
    return {"claim": "compiled cart shutter hook with synthetic flag/door state on its natural JSR stack",
            "not_claimed": ["controller boarding", "shutter animation/collision", "traversal/reclose",
                            "room or save persistence"],
            "boundaries": {"dispatcher": f"{DISPATCH:06X}", "hook": f"{HOOK:06X}",
                           "handler": "resolved RoomTag_ShutterDoorRequiresCart symbol",
                           "pre_rts": f"{TAG_RETURN:06X}", "post_rts": f"{POST_RTS:06X}"},
            "cases": [{**s, "writes": {f"{a:04X}": v for a, v in case_writes(s).items()},
                       "expected_handler_writes": {f"{a:04X}": v for a, v in (OPEN if s["open"] else {}).items()}}
                      for s in CASES],
            "native_executed": False}


class CartShutterFixture(dispatch.SomariaDoorFixture):
    """Reuse attach/ownership, breakpoint, snapshot and cleanup mechanics only."""
    def __init__(self, args, bridge, code):
        super().__init__(args, bridge)
        self.handler = int(code["handler"], 16)
        self.result["claim"] = describe()["claim"]

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
        require(entry["readback"] == value, "Fixture readback mismatch")

    def run_case(self, spec):
        row = {"name": spec["name"], "passed": False, "snapshots": {}}
        self.result["cases"].append(row)
        for _ in range(3):
            start = self.run_until({DISPATCH})
            if self.rd(0x04C7) == 0:
                break
            self.run_until({DISPATCH_END})
        else:
            raise RuntimeError("Room tags stayed suppressed for three frames")
        sp0 = number(start["sp"])
        row.update(frame=self.frame(), dispatch_cpu=start, dispatch_stack=self.stack(sp0, 3).hex())
        require(self.stack(sp0, 3) == dispatch.CALLER_RETURN_STACK,
                "Dispatcher not entered from normal module-07 JSL")
        require((self.rd(0x10), self.rd(0x11)) == (7, 0)
                and self.b.read_memory16(0x7E00A0) == 0x104 and self.rd(0x1B) != 0,
                "Fixture requires indoor House 0104 module 07/00")
        require(self.rd(0x35) == 0, "Refuse a naturally mounted session")
        row["tags_before"] = [self.rd(a) for a in TAGS]
        self.write(0xAE, 0x37, "tag fixture: cart shutter slot0", DISPATCH)
        self.write(0xAF, 0, "tag fixture: RoomTag_Nothing slot1", DISPATCH)
        hook = self.run_until({HOOK})
        sp = number(hook["sp"])
        row.update(hook_cpu=hook, hook_stack=self.stack(sp, 5).hex())
        require(sp == sp0 - 2 and self.stack(sp, 5) == dispatch.HOOK_STACK,
                "Cart hook is not on the natural slot0 JSR stack")
        require(number(hook["p"]) & 0x30 == 0x30 and number(hook["d"]) == 0
                and (number(hook["dbr"]) & 0x7F) < 0x40,
                "Tag hook ABI is not M8/X8/D0 with low-WRAM DBR")
        require(self.rd(0x11) == 0 and self.rd(0x0E) == 0, "Wrong tag cadence")
        before = self.low()
        self.snapshot(row, "hook", before)
        for a in OUTPUTS:
            self.dirty.setdefault(a, before[a])
        writes = case_writes(spec)
        for a, value in writes.items():
            self.write(a, value, spec["name"] + " fixture", HOOK)
        entry = self.run_until({self.handler})
        row["entry_cpu"] = entry
        self.same_cpu(hook, entry, ("a", "x", "y", "sp", "d", "dbr", "p"), "JML entry")
        injected = bytearray(before)
        for a, value in writes.items():
            injected[a] = value
        require(self.low() == bytes(injected), "Unexpected WRAM before handler")
        expected = OPEN if spec["open"] else {}
        watch = watches(expected)
        if spec["open"]:
            # CPX is after the initial LDA; its read stop cannot be confused
            # with the still-paused handler-entry execution breakpoint.
            row["control_read_shutter"] = self.run_until(
                {TAG_RETURN}, watch + [(0x0468, 0x0469, "read")],
                accept=(self.handler + 10, self.handler + 13))
            require(number(row["control_read_shutter"]["pc"]) != TAG_RETURN,
                    "Read breakpoint control did not fire")
            write_control = watches(set(expected) - {0x0468, 0x0469})
            row["control_write_shutter"] = self.run_until(
                {TAG_RETURN}, write_control, accept=(self.handler + 15, self.handler + 18))
            require(number(row["control_write_shutter"]["pc"]) != TAG_RETURN,
                    "Write breakpoint control did not fire")
        pre = self.run_until({TAG_RETURN}, watch)
        row["pre_rts_cpu"] = pre
        require(number(pre["p"]) & 0x30 == 0x30, "Handler exit is not M8/X8")
        self.same_cpu(entry, pre, ("y", "sp", "d", "dbr"), "Handler preserved state")
        require(self.stack(number(pre["sp"]), 5) == dispatch.HOOK_STACK,
                "Handler changed the natural return stack")
        wanted = bytearray(injected)
        for a, value in expected.items():
            wanted[a] = value
        actual = self.low()
        self.snapshot(row, "pre-rts", actual)
        row["handler_diff"] = dispatch.native_diff(injected, actual)
        require(actual == bytes(wanted), "Handler changed WRAM beyond exact case outputs")
        post = self.run_until({POST_RTS})
        row["post_rts_cpu"] = post
        require(number(post["sp"]) == sp + 2, "RTS did not consume the tag JSR return")
        self.same_cpu(pre, post, ("y", "d", "dbr"), "RTS")
        require(self.low() == actual, "RTS changed WRAM")
        self.restore(set(self.dirty) - set(TAGS), "restore inputs and hook outputs", POST_RTS)
        require(self.low() == before, "WRAM did not restore before normal frame code")
        end = self.run_until({DISPATCH_END})
        row["dispatch_end_cpu"] = end
        require(number(end["sp"]) == number(post["sp"]), "Slot1 changed stack depth")
        self.restore(set(TAGS), "restore original tags", DISPATCH_END)
        final = self.low()
        settled = bytearray(before)
        settled[0x0E], settled[sp + 1] = 1, dispatch.SLOT1_RETURN_LOW
        for a, value in zip(TAGS, row["tags_before"]):
            settled[a] = value
        require(final == bytes(settled), "Dispatcher changed unexpected WRAM")
        require(not self.dirty, "Fixture bytes remain dirty")
        self.snapshot(row, "restored-dispatch-end", final)
        row["passed"] = True


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("describe", "validate-candidate", "execute-fixtures"):
        p.add_argument("--" + name, action="store_true")
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"):
        p.add_argument("--" + name)
    for name in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--pid", type=int)
    return p.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    if args.describe:
        print(json.dumps(describe(), indent=2))
        return 0
    if args.validate_candidate:
        require(args.owned_rom and args.symbols, "Candidate validation needs ROM and symbols")
        try:
            result = {"candidate_ok": True, **validate_candidate(args.owned_rom.read_bytes(), args.symbols.read_text())}
        except RuntimeError as error:
            result = {"candidate_ok": False, "error": str(error)}
        print(json.dumps(result, indent=2))
        return 0 if result["candidate_ok"] else 2
    require(args.execute_fixtures, "Use --describe, --validate-candidate or --execute-fixtures")
    fields = ("socket", "rom_sha256", "symbols_sha256", "owner", "owned_rom", "symbols",
              "client_root", "status_file", "owner_file", "output", "pid")
    require(all(getattr(args, k) for k in fields) and args.pid > 0, "Missing private-session identity")
    require(args.socket.startswith("/tmp/mesen2-")
            and "oos-rc-play" not in " ".join(map(str, vars(args).values())), "Refuse non-private session")
    rom, symbols = args.owned_rom.read_bytes(), args.symbols.read_bytes()
    require(digest(rom) == args.rom_sha256.lower(), "Private ROM SHA256 mismatch")
    require(digest(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 mismatch")
    sha1 = digest(rom, "sha1")
    require(not args.rom_sha1 or sha1 == args.rom_sha1.lower(), "Private ROM SHA1 mismatch")
    code = validate_candidate(rom, symbols.decode())
    args.rom_sha1 = sha1
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    require("--headless" in command and str(args.owned_rom) in command, "PID is not the private headless ROM")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = CartShutterFixture(args, bridge, code)
    fixture.result.update(inputs={k: str(v) for k, v in vars(args).items()}, code=code,
                          source_sha256=digest(Path(__file__).read_bytes()))
    admitted = False
    try:
        fixture.check_owner()
        require(fixture.paused(), "Caller must supply a paused private session")
        listed = bridge.send_command("BREAKPOINT", {"action": "list"})
        require(listed.get("success") and not (listed.get("data") or {}).get("breakpoints"),
                "Existing breakpoints: refuse shared debug session")
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
            try:
                require(digest(path.read_bytes()) == expected.lower(), label + " file changed")
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed")
                                        and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": fixture.result["passed"], "result": str(args.output / "RESULT.json")}))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
