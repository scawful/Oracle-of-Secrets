#!/usr/bin/env python3
"""Attach-only native Portal placement transaction fixtures in cold House0104.

Twelve count/color/tile cases use native state08 Prep, Long/Main/StateHandler,
and the real dungeon Sprite_GetTileAttr lookup. One disclosed plane-A collision
cell is restored before any later frame. Old pair identities/count/selector are
explicit paused fixtures. Caller owns launch/cold boot/positive cleanup. No
CPU/register/PC, module, camera, player-health, invulnerability or save writes.
This is placement validation, not an actual rod cast, warp, route or save test.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
sys.dont_write_bytecode = True
CP_SHA = "d523cde1519e9c888edb8c35bd74b0af5bbdb97047a07dc03e3fda6b557458c2"
CP_PATH = Path(__file__).with_name("portal_counterpart.py")
if hashlib.sha256(CP_PATH.read_bytes()).hexdigest() != CP_SHA:
    raise RuntimeError("Qualified Portal counterpart source differs")
_spec = importlib.util.spec_from_file_location("placement_portal_protocol", CP_PATH)
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)
util = cp.util
require, sha, number, raw, symbol, data = cp.require, cp.sha, cp.number, cp.raw, cp.symbol, cp.data
SPRITES, SIZE = cp.SPRITES, cp.SIZE
CELL = 0x7F2BEF  # Canonical cold House X0978/Y2178, masked 64x64 plane-A lookup.
PUBLICATION = (0x7E0307, 0x7E0632, 0x7E0633, 0x7E06F8, 0x7E06F9, 0x7E06FA, 0x7E06FB)
TILE_HELPER = bytes.fromhex("8b4bab2086e8ab6bbd200fc901c23064059005a900108505a51b29ff00f025a50229ff014a4a4a8504a50029f8010a0a0a186504186505daaabf00207ffae2308da50f60")
DISMISS = bytes.fromhex("adfe06c902905dafa60f7ef029daad3206c910b01dc301f019aabd200ec903d011bd300ec902d00abdd00dc909d0039ed00dcefe06fadaad3306c910b01dc301f019aabd200ec903d011bd300ec901d00abdd00dc909d0039ed00dcefe06ad3306fa3860eefe0660")
TAIL = bytes.fromhex("afa60f7ed020a9018d07038a8d3306bd000d8dfa06bd100d8dfb06a9019d300ea9029d800d60a9028d07038a8d3206bd000d8df806bd100d8df906a9029d300ea9019d800d60")
REJECT = bytes.fromhex("bd000d29f88500bd200d8501bd100d29f88502bd300d8503a900227be806ada50f18c900f011c948f00da93c8d2e01a9009dd00dcefe0660")

def matrix():
    return ([dict(name=f"reject01-count{n}-selector{s}", attr=1, count=n, selector=s)
             for n in (0, 1, 2) for s in (0, 1)]
            + [dict(name=f"accept00-count{n}-selector{s}", attr=0, count=n, selector=s)
               for n in (0, 2) for s in (0, 1)]
            + [dict(name=f"accept48-count1-selector{s}", attr=0x48, count=1, selector=s) for s in (0, 1)])

def model(case, expect):
    require(expect in ("baseline", "candidate"), "Unknown expected profile")
    accepted = case["attr"] in (0, 0x48)
    publish = accepted or expect == "baseline"
    counter = case["count"]
    counter_values, clears = [], []
    if publish:
        if counter < 2:
            counter += 1; counter_values.append(counter)
        else:
            for slot in ((14, 15) if case["selector"] else (15,)):
                clears.append(slot); counter -= 1; counter_values.append(counter)
        if not accepted:
            counter = (counter - 1) & 255; counter_values.append(counter)
    return dict(accepted=accepted, publish=publish, counter=counter,
                counter_values=counter_values, clears=clears, state=9 if accepted else 0,
                action=(1 if case["selector"] else 2) if publish else 0,
                subtype=(2 if case["selector"] else 1) if publish else 0)

def lookup_cell(x, y):
    return 0x7F2000 + ((y & 0x1F8) << 3) + ((x & 0x1FF) >> 3)

def allowed_write(address):
    return (cp.allowed_write(address) or address in (0x7E06FE, 0x7E0FA6, CELL)
            or address - 0x7E000F in (0xE20, 0xE30))

def describe(image: bytes, text: str, expect: str) -> dict:
    require(expect in ("baseline", "candidate"), "Unknown expected profile")
    p = cp.describe(image, text, "candidate")  # Both profiles contain the fixed counterpart helper.
    handler, reject, dismissal = (symbol(text, n) for n in ("StateHandler", "RejectOnTileCollision", "CheckForDismissPortal"))
    jsr = lambda addr: b"\x20" + (addr & 65535).to_bytes(2, "little")
    head = (jsr(dismissal) + jsr(reject) if expect == "baseline" else
            jsr(reject) + bytes.fromhex("BDD00DF0") + bytes([len(TAIL) + 2]) + jsr(dismissal))
    require(raw(image, handler, len(head + TAIL)) == head + TAIL
            and p["blue"] == handler + len(head + TAIL), "Exact StateHandler validation/publication order differs")
    reject_bytes = REJECT if expect == "baseline" else REJECT[:-4] + b"\x60"
    # Candidate removal of DEC shortens each of the two acceptance branches by 3.
    if expect == "candidate":
        reject_bytes = bytearray(reject_bytes); reject_bytes[37] -= 3; reject_bytes[41] -= 3; reject_bytes = bytes(reject_bytes)
    require(raw(image, reject, len(reject_bytes)) == reject_bytes, "Exact tile rejection/native effect bytes differ")
    require(raw(image, dismissal, len(DISMISS)) == DISMISS, "Legacy identity-guarded dismissal bytes differ")
    require(raw(image, 0x06E87B, len(TILE_HELPER)) == TILE_HELPER, "Actual native plane-A tile helper differs")
    publication_writers = {a:handler + (head+TAIL).index(b"\x8d" + (a & 65535).to_bytes(2,"little")) for a in PUBLICATION if a != 0x7E0307}
    color_writers = [handler+(head+TAIL).index(bytes.fromhex("8D0703")),handler+(head+TAIL).rindex(bytes.fromhex("8D0703"))]
    p.update(expect=expect, handler=handler, reject=reject, dismissal=dismissal,
             publication_writers=publication_writers, color_writers=color_writers,
             reject_call=handler if expect == "candidate" else handler + 3,
             reject_return=handler + 3 if expect == "candidate" else handler + 6,
             attr_call=reject + 26, attr_return=reject + 30,
             reject_state_writer=reject + 49, reject_counter_writer=reject + 52 if expect == "baseline" else None,
             state_writers=[dismissal + DISMISS.index(bytes.fromhex("9ED00D")), dismissal + DISMISS.rindex(bytes.fromhex("9ED00D"))],
             counter_writers=[dismissal + DISMISS.index(bytes.fromhex("CEFE06")), dismissal + DISMISS.rindex(bytes.fromhex("CEFE06"))],
             increment_writer=dismissal + len(DISMISS) - 4, case_count=12)
    return p

def fixture_class(portal):
    class PlacementFixture(cp.fixture_class(portal)):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge, code)
            self.tile_original = None

        def write(self, address, value, reason):
            require(allowed_write(address) and self.paused() and 0 <= value <= 255,
                    "Forbidden or unpaused placement fixture write: " + hex(address))
            row = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(row)
            require(self.b.write_memory(address, value), "Fixture write failed")
            row["readback"] = self.b.read_memory(address)
            require(row["readback"] == value, "Fixture write/readback failed")

        def restore_cell(self):
            if self.tile_original is not None:
                self.write(CELL, self.tile_original, "restore exact collision cell before any later frame")

        def source_xy(self):
            return (self.b.read_memory(0x7E0D10) | self.b.read_memory(0x7E0D30) << 8,
                    self.b.read_memory(0x7E0D00) | self.b.read_memory(0x7E0D20) << 8)

        def reset_idle(self):
            self.restore_cell()
            super().reset_idle()
            self.write(0x7E0DDF, 0, "deactivate old orange before any later native frame")
            self.write(0x7E0DD0, 9, "restore controlled source after rejected placement")

        def initialize(self):
            self.tile_original = self.b.read_memory(CELL)
            super().initialize()
            require(lookup_cell(*self.source_xy()) == CELL,
                    "Canonical source no longer samples the admitted plane-A cell")

        def capture(self, name):
            r = super().capture(name)
            r["protected"]["scroll_registers"] = self.block(0x7E00E0, 12).hex()
            r.update(pair_states=self.block(0x7E0DDE, 2).hex(), attr=self.b.read_memory(0x7E0FA5),
                     sound=self.b.read_memory(0x7E012E), color=self.b.read_memory(0x7E0307),
                     collision_cell=self.block(CELL, 2).hex(), scratch=self.block(0x7E0000, 6).hex())
            return r

        def case(self, c):
            self.check_owner(); self.reset_idle()
            caller = self.run_to({self.code["call"]}); entry = self.run_to({self.code["main"]})
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 2)
            require(number(caller["x"]) == 0 and number(entry["sp"]) == number(caller["sp"]) - 2
                    and number(caller["dbr"]) == self.code["long"] >> 16
                    and number(caller["d"]) == 0 and number(caller["p"]) & 0x30 == 0x30
                    and stack == ((self.code["return_pc"] - 1) & 65535).to_bytes(2, "little"), "Actual Long/Main short stack differs")
            for table, value in ((0xD80, 0), (0xE30, 0), (0xD90, 0), (0xE00, 0x40), (0xEE0, 0x40)):
                self.write(0x7E0000 + table, value, "pending source action/role/timer fixture at actual Main")
            for slot, subtype in ((14, 2), (15, 1)):
                for table, value in ((0xE20, 3), (0xE30, subtype), (0xDD0, 9 if c["count"] >= (1 if slot == 14 else 2) else 0)):
                    self.write(0x7E0000 + table + slot, value, "explicit prior live pair fixture; no other actor executes")
            for address, value in ((0x7E0632, 14), (0x7E0633, 15), (0x7E06FE, c["count"]), (0x7E0FA6, c["selector"]), (CELL, c["attr"])):
                self.write(address, value, "disclosed pair handle/count/selector or single sampled collision cell")
            state = self.run_to({self.code["handler"]})
            before = self.block(SPRITES, SIZE); wanted = model(c, self.a.expect)
            row = dict(**c, expected=wanted, passed=False, caller_cpu=caller, main_entry_cpu=entry,
                       main_short_stack=stack.hex(), handler_cpu=state, input=self.capture(c["name"] + "-before"))
            self.result["cases"].append(row)
            watches = {a:self.watch(a) for a in (0x7E0DD0, 0x7E0DDE, 0x7E0DDF, 0x7E06FE, 0x7E0FA5, *PUBLICATION)}
            row["reject_call_cpu"] = self.run_to({self.code["reject_call"]}) if self.code["reject_call"] != self.code["handler"] else state
            row["reject_entry_cpu"] = self.run_to({self.code["reject"]})
            row["tile_call_cpu"] = self.run_to({self.code["attr_call"]})
            x,y = self.source_xy()
            require(lookup_cell(x,y) == CELL and self.block(0x7E0000,4) == (y & 0xFFF8).to_bytes(2,"little") + (x & 0xFFF8).to_bytes(2,"little"), "Actual Reject masked coordinates differ")
            row["lookup"] = dict(x=x,y=y,address=f"{CELL:06X}",raw=self.block(CELL,2).hex(),scratch=self.block(0x7E0000,4).hex())
            row["tile_entry_cpu"] = self.run_to({0x06E87B})
            row["tile_return_cpu"] = self.run_to({self.code["attr_return"]})
            row["reject_return_cpu"] = self.run_to({self.code["reject_return"]})
            rc,rr = row["reject_call_cpu"],row["reject_return_cpu"]
            require(all(number(rc[k]) == number(rr[k]) for k in ("sp","x","dbr","d")) and number(rr["p"]) & 0x30 == 0x30, "Reject RTS ABI differs")
            row["main_return_cpu"] = self.run_to({self.code["return_pc"]})
            ret = row["main_return_cpu"]
            require(all(number(ret[k]) == number(caller[k]) for k in ("sp","x","dbr","d")) and number(ret["p"]) & 0x30 == 0x30, "Main return ABI differs")
            row["after"] = self.capture(c["name"] + "-after"); after = self.block(SPRITES,SIZE)
            row["provenance"] = {f"{a:06X}":data(self.b.mem_blame(watch_id=w)) for a,w in watches.items()}
            require(row["after"]["frame"] == row["input"]["frame"], "Native transaction escaped its single-frame collision fixture")
            expected = bytearray(before)
            for table,value in ((0xDD0,wanted["state"]),(0xD80,wanted["action"]),(0xE30,wanted["subtype"]),(0xFA5,c["attr"])):
                expected[table-0xB00] = value
            for slot in wanted["clears"]:expected[0xDD0-0xB00+slot]=0
            require(after == expected, "Unexpected sprite/global byte change or wrong placement result")
            protected = dict(row["input"]["protected"]);protected["counter"] = bytes([wanted["counter"]]).hex()
            if wanted["publish"]:
                indices = bytearray.fromhex(protected["indices"]);indices[0 if c["selector"] else 1]=0;protected["indices"]=indices.hex()
                xy = bytearray.fromhex(protected["portal_xy"]);offset=0 if c["selector"] else 2;xy[offset:offset+2]=bytes([y&255,x&255]);protected["portal_xy"]=xy.hex()
            require(row["after"]["protected"] == protected, "Placement changed protected context or wrong counter/index/coordinate publication")
            require(row["after"]["attr"] == c["attr"] and row["after"]["collision_cell"] == row["input"]["collision_cell"], "Native tile lookup/cell changed unexpectedly")
            require(row["after"]["color"] == (2 if c["selector"] else 1) if wanted["publish"] else row["after"]["color"] == row["input"]["color"], "Rejected placement published color or accepted color differs")
            if not wanted["accepted"]:require(row["after"]["sound"] == 0x3C, "Rejected placement did not emit native error sound")
            else:require(row["after"]["sound"] == row["input"]["sound"], "Accepted placement changed rejection sound")
            publication = sorted((w for a in PUBLICATION for w in row["provenance"][f"{a:06X}"]["writes"]), key=lambda w:number(w["cycle"]))
            selected = 0x7E0632 if c["selector"] else 0x7E0633
            xybase = 0x7E06F8 if c["selector"] else 0x7E06FA
            pub_expected = ([(0x7E0307, 2 if c["selector"] else 1, self.code["color_writers"][c["selector"]]),
                             (selected, 0, self.code["publication_writers"][selected]),
                             (xybase, y & 255, self.code["publication_writers"][xybase]),
                             (xybase+1, x & 255, self.code["publication_writers"][xybase+1])] if wanted["publish"] else [])
            require([(number(w["addr"]),number(w["value"]),number(w["pc"])) for w in publication] == pub_expected
                    and all(number(w["size"]) == 1 for w in publication), "Unexpected or missing portal publication writer")
            attr = row["provenance"]["7E0FA5"]["writes"]
            require(len(attr)==1 and number(attr[0]["pc"])==0x06E8BB and number(attr[0]["value"])==c["attr"] and number(attr[0]["size"])==1, "Missing unique native collision attr writer")
            cw = row["provenance"]["7E06FE"]["writes"]
            require([number(t["value"]) for t in cw] == wanted["counter_values"], "Unexpected placement counter writer values")
            writers=[]
            if wanted["publish"]:
                writers=([self.code["increment_writer"]] if c["count"]<2 else [self.code["counter_writers"][i] for i in ((0,1) if c["selector"] else (1,))])
                if not wanted["accepted"]:writers.append(self.code["reject_counter_writer"])
            require([number(t["pc"]) for t in cw] == writers and all(number(t["size"])==1 for t in cw), "Unexpected placement counter writer provenance")
            state_writes = sorted((w for a in ("7E0DD0", "7E0DDE", "7E0DDF") for w in row["provenance"][a]["writes"]), key=lambda w:number(w["cycle"]))
            desired = [(0x7E0DD0 + slot, self.code["state_writers"][0 if slot == 14 else 1]) for slot in wanted["clears"]]
            rejected = [(0x7E0DD0, self.code["reject_state_writer"])] if not wanted["accepted"] else []
            desired = rejected + desired if self.a.expect == "candidate" else desired + rejected
            require([(number(w["addr"]), number(w["pc"])) for w in state_writes] == desired
                    and all(number(w["value"]) == 0 and number(w["size"]) == 1 for w in state_writes), "Unexpected source/pair state writer provenance")
            for watch in watches.values():self.remove_watch(watch)
            self.reset_idle();row["restored"] = self.capture(c["name"] + "-restored")
            require(self.b.read_memory(CELL)==self.tile_original and self.block(0x7E0DDE,2)==bytes(2), "Unsafe collision/actor fixture before later frame")
            require(row["restored"]["frame"] == row["after"]["frame"], "Collision fixture survived into a later frame")
            row["passed"] = True
    return PlacementFixture

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
    fixture.result.update(schema="portal-placement-validation-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=cp.SUPPORT_SHA,
                          counterpart_sha256=CP_SHA, protocol_utilities_sha256=cp.UTIL_SHA,
                          claim="Native Prep/Main/StateHandler and real plane-A tile lookup; explicit pair/count/selector/single-cell fixtures, no natural cast/warp/route/save acceptance")
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
        require(len(fixture.result["cases"]) == 12 and all(c["passed"] for c in fixture.result["cases"]), "Incomplete twelve-case matrix")
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
                          (args.support_file, cp.SUPPORT_SHA), (CP_PATH, CP_SHA), (cp.UTIL_PATH, cp.UTIL_SHA)):
            try: require(sha(path.read_bytes()) == pin.lower(), "Input changed: " + str(path))
            except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed") and fixture.result.get("native_sram_preserved") and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=fixture.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
