#!/usr/bin/env python3
"""Attach-only Portal dismissal identity qualification in cold House0104.

Twenty explicit count/selector/handle cases run through native state08 Prep,
Long/Main/StateHandler and the actual dismissal JSR/RTS. Cached handles, actor
identity and the two in-window out-of-range canaries are disclosed fixtures.
They are restored before the remaining StateHandler/Reject code can run.
Caller owns launch/cold boot/positive process cleanup. No CPU/register/PC writes,
direct calls, savestates, module/player-health/invulnerability or save writes.
This is a routine identity/count/ABI test, not natural placement or lifetime.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
COUNTERPART_SHA = "e744f35c34b00ee8f725c0f792c801564b7172fbc11b699a1ac80e45558c6513"
COUNTERPART_PATH = Path(__file__).with_name("portal_counterpart.py")
if hashlib.sha256(COUNTERPART_PATH.read_bytes()).hexdigest() != COUNTERPART_SHA:
    raise RuntimeError("Qualified Portal counterpart utilities differ")
_spec = importlib.util.spec_from_file_location("dismissal_counterpart_protocol", COUNTERPART_PATH)
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)
util = cp.util
require, sha, number, raw, symbol, data = cp.require, cp.sha, cp.number, cp.raw, cp.symbol, cp.data
SPRITES, SIZE = cp.SPRITES, cp.SIZE
CANARIES = (0x7E0DE0, 0x7E0ECF)
STATE_ADDRESSES = (0x7E0DD0, 0x7E0DDE, 0x7E0DDF, *CANARIES)
INVALIDS = ("dead", "reused-type", "wrong-color", "inactive08", "out-of-range10", "out-of-rangeFF", "self")


def allowed_write(address):
    return (cp.allowed_write(address) or address in (0x7E06FE, 0x7E0FA6, *CANARIES)
            or address - 0x7E000F in (0xE20, 0xE30))


def matrix():
    cases = [dict(name=f"count{count}-selector{selector}", count=count, selector=selector, target=None, status="valid")
             for count in (0, 1) for selector in (0, 1)]
    cases += [dict(name=f"count2-validpair-selector{selector}", count=2, selector=selector, target=None, status="valid")
              for selector in (0, 1)]
    cases += [dict(name=f"{color}-{status}", count=2, selector=1 if color == "blue" else 0,
                   target=color, status=status) for color in ("blue", "orange") for status in INVALIDS]
    return cases


def inputs(case):
    blue, orange = dict(index=14, state=9, kind=3, subtype=2), dict(index=15, state=9, kind=3, subtype=1)
    source_subtype = 0
    if case["target"]:
        target = blue if case["target"] == "blue" else orange
        status = case["status"]
        if status == "dead": target["state"] = 0
        elif status == "reused-type": target["kind"] = 0xD5
        elif status == "wrong-color": target["subtype"] = 3 - target["subtype"]
        elif status == "inactive08": target["state"] = 8
        elif status == "out-of-range10": target["index"] = 0x10
        elif status == "out-of-rangeFF": target["index"] = 0xFF
        elif status == "self":
            target["index"] = 0
            source_subtype = target["subtype"]  # Explicitly forge role so the self guard is necessary.
        else: raise RuntimeError("Unknown invalid handle input")
    return dict(blue=blue, orange=orange, source_subtype=source_subtype)


def expected(case, expect):
    require(expect in ("baseline", "candidate"), "Unknown expected profile")
    values = inputs(case)
    if case["count"] < 2:
        return dict(counter=case["count"] + 1, state_writes=[], counter_values=[case["count"] + 1], a=case["count"], carry=False)
    writes = []
    for color in (("blue", "orange") if case["selector"] else ("orange",)):
        target = values[color]
        valid = (target["index"] < 16 and target["index"] != 0 and target["kind"] == 3
                 and target["subtype"] == (2 if color == "blue" else 1) and target["state"] == 9)
        if expect == "baseline" or valid:
            writes.append(dict(color=color, address=0x7E0DD0 + target["index"], value=0))
    return dict(counter=0 if case["selector"] else 1, state_writes=writes,
                counter_values=[1, 0] if case["selector"] else [1], a=values["orange"]["index"], carry=True)


def describe(image: bytes, text: str, expect: str) -> dict:
    """File-only guards bind native dispatch and both exact dismissal implementations."""
    # Both profiles already contain the qualified counterpart fix.
    plan = cp.describe(image, text, "candidate")
    start = symbol(text, "CheckForDismissPortal")
    orange = symbol(text, "CheckForDismissPortal_DespawnOrange")
    low = symbol(text, "CheckForDismissPortal_return")
    handler = symbol(text, "StateHandler")
    require(raw(image, handler, 6) == b"\x20" + (start & 65535).to_bytes(2, "little")
            + b"\x20" + (symbol(text, "RejectOnTileCollision") & 65535).to_bytes(2, "little"),
            "StateHandler does not call exact dismissal then Reject code")
    prefix = bytes.fromhex("ADFE06C902") + bytes([0x90, low - (start + 7)]) + bytes.fromhex("AFA60F7E")
    prefix += bytes([0xF0, orange - (start + len(prefix) + 2)])
    code = bytearray(prefix)
    states, counters = {}, {}
    for color, index, subtype in (("blue", 0x632, 2), ("orange", 0x633, 1)):
        if color == "orange": require(start + len(code) == orange, "Orange dismissal entry differs")
        code += b"\xda\xad" + index.to_bytes(2, "little")
        if expect == "candidate":
            keep = symbol(text, "CheckForDismissPortal_keep_" + color + "_slot")
            def branch(op):
                at = start + len(code)
                require(0 <= keep - (at + 2) < 128, "Guard branch does not remain short/forward")
                code.extend(bytes([op, keep - (at + 2)]))
            code += bytes.fromhex("C910"); branch(0xB0)
            code += bytes.fromhex("C301"); branch(0xF0)
            code += bytes.fromhex("AABD200EC903"); branch(0xD0)
            code += bytes.fromhex("BD300EC9") + bytes([subtype]); branch(0xD0)
            code += bytes.fromhex("BDD00DC909"); branch(0xD0)
        else:
            require(expect == "baseline", "Unknown expected profile")
            code += b"\xaa"
        states[color] = start + len(code)
        code += bytes.fromhex("9ED00D")
        counters[color] = start + len(code)
        code += bytes.fromhex("CEFE06")
        if expect == "candidate" and color == "orange": code += bytes.fromhex("AD3306")
        code += b"\xfa"
    if expect == "candidate": code += b"\x38"
    code += b"\x60"
    require(start + len(code) == low, "Low-count branch entry differs")
    code += bytes.fromhex("EEFE0660")
    require(raw(image, start, len(code)) == code, "Dismissal guard, state/counter writers or legacy A/C return bytes differ")
    plan.update(expect=expect, dismissal=start, dismissal_call=handler, dismissal_return=handler + 3,
                state_writers=states, counter_writers=counters, increment_writer=low, dismissal_bytes=code.hex(), case_count=20)
    return plan


def fixture_class(portal):
    class DismissalFixture(cp.fixture_class(portal)):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge, code)
            self.saved_canaries = None

        def write(self, address, value, reason):
            require(allowed_write(address), "Forbidden Portal dismissal fixture write: " + hex(address))
            require(0 <= value <= 255 and self.paused(), "Fixture byte write requires paused CPU")
            entry = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(entry)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            entry["readback"] = self.b.read_memory(address)
            require(entry["readback"] == value, "Fixture write readback differs")

        def capture(self, name):
            result = super().capture(name)
            blob = self.block(SPRITES, SIZE)
            result.update(blue14={k: blob[t - 0xB00 + 14] for k, t in cp.FIELDS.items()},
                          orange15={k: blob[t - 0xB00 + 15] for k, t in cp.FIELDS.items()},
                          canaries={f"{a:06X}": self.b.read_memory(a) for a in CANARIES})
            return result

        def reset_idle(self):
            super().reset_idle()
            self.write(0x7E0DDF, 0, "deactivate orange15 before permitting any further native frame")
            self.write(0x7E0DD0, 9, "restore controlled source after possible baseline self deletion")
            if self.saved_canaries is not None:
                for address, value in self.saved_canaries.items():
                    self.write(address, value, "restore exact out-of-range canary before native continuation")

        def initialize(self):
            self.saved_canaries = {a: self.b.read_memory(a) for a in CANARIES}
            super().initialize()

        def case(self, case_input):
            self.check_owner()
            self.reset_idle()
            long_caller = self.run_to({self.code["call"]})
            main_entry = self.run_to({self.code["main"]})
            main_stack = self.block(0x7E0000 + number(main_entry["sp"]) + 1, 2)
            require(number(long_caller["x"]) == 0 and number(main_entry["sp"]) == number(long_caller["sp"]) - 2
                    and main_stack == ((self.code["return_pc"] - 1) & 65535).to_bytes(2, "little"), "Actual Long/Main JSR stack differs")
            values = inputs(case_input)
            for table, value in ((0xD80, 0), (0xE30, values["source_subtype"]), (0xD90, 0), (0xE00, 0x40), (0xEE0, 0x40)):
                self.write(0x7E0000 + table, value, "new source StateHandler role/action/timer input at actual Main boundary")
            for color, slot in (("blue", 14), ("orange", 15)):
                target = values[color]
                for table, value in ((0xE20, target["kind"]), (0xE30, target["subtype"]), (0xDD0, target["state"])):
                    self.write(0x7E0000 + table + slot, value, "explicit cached-handle actor identity fixture")
            for address, value in ((0x7E0632, values["blue"]["index"]), (0x7E0633, values["orange"]["index"]),
                                   (0x7E06FE, case_input["count"]), (0x7E0FA6, case_input["selector"]),
                                   (CANARIES[0], 0xA5), (CANARIES[1], 0x5A)):
                self.write(address, value, "disclosed cached index/count/selector or in-window OOB canary input")
            caller = self.run_to({self.code["dismissal_call"]})
            require(number(caller["x"]) == 0 and number(caller["dbr"]) == self.code["long"] >> 16
                    and number(caller["d"]) == 0 and number(caller["p"]) & 0x30 == 0x30, "Dismissal caller X/DBR/DP/MX differs")
            before = self.block(SPRITES, SIZE)
            record = dict(**case_input, passed=False, expected=expected(case_input, self.a.expect), values=values,
                          long_caller_cpu=long_caller, main_entry_cpu=main_entry, main_short_stack=main_stack.hex(),
                          caller_cpu=caller, input=self.capture(case_input["name"] + "-before"))
            self.result["cases"].append(record)
            watches = {a: self.watch(a) for a in (*STATE_ADDRESSES, 0x7E06FE)}
            record["entry_cpu"] = self.run_to({self.code["dismissal"]})
            entry = record["entry_cpu"]
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 2)
            record["short_return_stack"] = stack.hex()
            require(number(entry["sp"]) == number(caller["sp"]) - 2
                    and stack == ((self.code["dismissal_return"] - 1) & 65535).to_bytes(2, "little"), "Actual dismissal JSR stack differs")
            record["return_cpu"] = self.run_to({self.code["dismissal_return"]})
            returned, wanted = record["return_cpu"], record["expected"]
            require(all(number(returned[k]) == number(caller[k]) for k in ("sp", "x", "y", "dbr", "d"))
                    and number(returned["p"]) & 0x30 == number(caller["p"]) & 0x30, "Dismissal RTS corrupted SP/X/Y/DBR/DP/MX")
            require(number(returned["a"]) & 255 == wanted["a"]
                    and number(returned["a"]) & 0xFF00 == number(caller["a"]) & 0xFF00
                    and bool(number(returned["p"]) & 1) == wanted["carry"], "Legacy dismissal A/carry return changed")
            record["after"] = self.capture(case_input["name"] + "-after")
            after = self.block(SPRITES, SIZE)
            expected_blob = bytearray(before)
            for write in wanted["state_writes"]: expected_blob[write["address"] - SPRITES] = 0
            require(after == expected_blob, "Dismissal altered an unexpected sprite byte or failed its state-identity contract")
            record["changed_sprite_addresses"] = [f"{SPRITES+i:06X}" for i, (a, b) in enumerate(zip(before, after)) if a != b]
            protected = dict(record["input"]["protected"])
            protected["counter"] = bytes([wanted["counter"]]).hex()
            require(record["after"]["protected"] == protected, "Dismissal changed protected context/indices or counter contract")
            traces = {a: data(self.b.mem_blame(watch_id=watches[a])) for a in watches}
            record["write_provenance"] = {f"{a:06X}": trace for a, trace in traces.items()}
            observed = sorted((w for a in STATE_ADDRESSES for w in traces[a]["writes"]), key=lambda w: number(w["cycle"]))
            require(len(observed) == len(wanted["state_writes"]), "Unexpected state clear count")
            for write, desired in zip(observed, wanted["state_writes"]):
                require(number(write["addr"]) == desired["address"] and number(write["value"]) == 0
                        and number(write["pc"]) == self.code["state_writers"][desired["color"]]
                        and number(write["size"]) == 1, "Missing unique native dismissal state writer")
            counter_writes = traces[0x7E06FE]["writes"]
            writers = ([self.code["increment_writer"]] if case_input["count"] < 2 else
                       [self.code["counter_writers"][c] for c in (("blue", "orange") if case_input["selector"] else ("orange",))])
            require([number(w["value"]) for w in counter_writes] == wanted["counter_values"]
                    and [number(w["pc"]) for w in counter_writes] == writers
                    and all(number(w["size"]) == 1 for w in counter_writes), "Legacy counter writer/count behavior changed")
            for watch in watches.values(): self.remove_watch(watch)
            # Restore every dangerous fixture before the CPU can enter Reject or a later frame.
            self.reset_idle()
            record["restored_before_continuation"] = self.capture(case_input["name"] + "-restored")
            require(all(self.b.read_memory(a) == v for a, v in self.saved_canaries.items())
                    and self.b.read_memory(0x7E0DD0) == 9
                    and self.b.read_memory(0x7E0DDE) == self.b.read_memory(0x7E0DDF) == 0, "Unsafe actors/canaries before native continuation")
            record["main_return_cpu"] = self.run_to({self.code["return_pc"]})
            require(all(number(record["main_return_cpu"][k]) == number(long_caller[k]) for k in ("sp", "x", "dbr", "d"))
                    and number(record["main_return_cpu"]["p"]) & 0x30 == 0x30, "Remaining native Main RTS ABI differs")
            self.reset_idle()
            record["passed"] = True

    return DismissalFixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"):
        parser.add_argument("--" + name, required=True)
    for name in ("status-file", "owned-rom", "symbols", "client-root", "owner-file", "output", "support-file"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--pid", type=int, required=True)
    parser.add_argument("--expect", choices=("baseline", "candidate"), required=True)
    parser.add_argument("--execute-fixtures", action="store_true")
    args = parser.parse_args()
    require(args.execute_fixtures and args.pid > 0, "Explicit owned fixture authorization required")
    image, symbols = args.owned_rom.read_bytes(), args.symbols.read_bytes()
    require(sha(image) == args.rom_sha256.lower() and hashlib.sha1(image).hexdigest() == args.rom_sha1.lower(), "Owned ROM hashes differ")
    require(sha(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 differs")
    code = describe(image, symbols.decode(), args.expect)
    portal = util.load_support(args.support_file)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    fixture = fixture_class(portal)(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0), code)
    bridge = fixture.b
    fixture.result.update(schema="portal-dismissal-identity-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=cp.SUPPORT_SHA,
                          counterpart_sha256=COUNTERPART_SHA, protocol_utilities_sha256=cp.UTIL_SHA,
                          claim="House native Prep/Main/StateHandler dismissal fixtures; identity/count/A-C/ABI only, no natural placement/lifetime/route/save acceptance")
    owned, saved_before, sram_before = False, None, None
    try:
        fixture.check_owner()
        require(fixture.paused(), "Caller must supply paused owned CPU")
        require(not bridge.list_breakpoints() and not data(bridge.mem_watch_list())["watches"], "Existing debug probes; refuse shared session")
        owned = True
        fixture.input("")
        saved_before = fixture.block(0x7EF000, SIZE)
        sram_before = bytes(bridge.read_block(0, 8192, "SnesSaveRam"))
        require(len(sram_before) == 8192, "Short native SRAM capture")
        (args.output / "before-saved-wram.bin").write_bytes(saved_before)
        (args.output / "before-native-sram.bin").write_bytes(sram_before)
        fixture.initialize()
        for case in matrix(): fixture.case(case)
        require(len(fixture.result["cases"]) == 20 and all(c["passed"] for c in fixture.result["cases"]), "Incomplete twenty-case matrix")
        fixture.result["runtime_checks_passed"] = True
    except BaseException as error:
        fixture.result["error"] = repr(error)
        if owned:
            try:
                fixture.ensure_paused()
                fixture.result["failure"] = fixture.capture("failure")
            except BaseException as capture_error:
                fixture.result["failure_capture_error"] = repr(capture_error)
    finally:
        if owned:
            for action in (lambda: fixture.input(""), fixture.ensure_paused):
                try: require(action() is not False, "Owned pause/release rejected")
                except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
            for remove, collection in ((fixture.remove, fixture.breakpoints), (fixture.remove_watch, fixture.watches)):
                for ident in list(collection):
                    try: remove(ident)
                    except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
            try:
                fixture.ensure_paused()
                fixture.reset_idle()
                for slot in range(16): fixture.write(0x7E0DD0 + slot, 0, "paused actor cleanup before caller disposes process")
                fixture.result["final"] = fixture.capture("final")
                fixture.result["saved_wram_deltas"] = util.saved_wram_deltas(saved_before, fixture.block(0x7EF000, SIZE))
                fixture.result["native_sram_preserved"] = util.verify_native_sram(sram_before, bytes(bridge.read_block(0, 8192, "SnesSaveRam")))
            except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
        for path, pin in ((args.owned_rom, args.rom_sha256), (args.symbols, args.symbols_sha256),
                          (args.support_file, cp.SUPPORT_SHA), (COUNTERPART_PATH, COUNTERPART_SHA), (cp.UTIL_PATH, cp.UTIL_SHA)):
            try: require(sha(path.read_bytes()) == pin.lower(), "Input changed: " + str(path))
            except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed") and fixture.result.get("native_sram_preserved") and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=fixture.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
