#!/usr/bin/env python3
"""Attach-only Portal near-warp boundary qualification; caller owns the process.

Use a paused normal House0104 or ordinary overworld reached by controller.
Explicit sprite/cache fixtures never write Link, live camera, module, CPU, ROM,
SRAM, health or invulnerability. Draw probes use the real native Long/Draw and
PrepOamCoord; queued probes use the actual Long/Main/handler JSR/RTS. Candidate
refusals must have zero protected writes. The final accepted candidate stops at
Main RTS after full coordinate/cache writes; native recovery/hop completion and
ordinary placement/route/save acceptance remain separate. Baseline stops before
its first unsafe warp write and never resumes. No fixture launches/stops Mesen.
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
    raise RuntimeError("Reviewed Portal counterpart utilities differ")
_spec = importlib.util.spec_from_file_location("portal_warp_protocol", CP_PATH)
cp = importlib.util.module_from_spec(_spec); _spec.loader.exec_module(cp)
util = cp.util
require, sha, number, raw, symbol, data = cp.require, cp.sha, cp.number, cp.raw, cp.symbol, cp.data
SPRITES, SIZE = cp.SPRITES, cp.SIZE
# CacheCameraProperties owns these fields; the six-byte hole C1A0..A5 is not touched.
CACHE_WORDS = ((0xE2, 0x180), (0xE8, 0x182), (0x20, 0x184), (0x22, 0x186),
               (0x600, 0x188), (0x604, 0x18A), (0x608, 0x18C), (0x60C, 0x18E),
               (0x610, 0x190), (0x612, 0x192), (0x614, 0x194), (0x616, 0x196),
               (0x618, 0x198), (0x61C, 0x19A), (0xA6, 0x19C), (0xA9, 0x19E))
CACHE_BYTES = ((0x2F, 0x1A6), (0xEE, 0x1A7), (0x476, 0x1A8), (0x6C, 0x1A9), (0xA4, 0x1AA))
CACHE_CODE = bytes.fromhex("c220a5e28f80c17ea5e88f82c17ea5208f84c17ea5228f86c17ead00068f88c17ead04068f8ac17ead08068f8cc17ead0c068f8ec17ead10068f90c17ead12068f92c17ead14068f94c17ead16068f96c17ead18068f98c17ead1c068f9ac17ea5a68f9cc17ea5a98f9ec17ee220a52f8fa6c17ea5ee8fa7c17ead76048fa8c17ea56c8fa9c17ea5a48faac17e6b")
PROTECTED = dict(cp.PROTECTED, cached_player_camera=(0x7EC180, 43), scroll=(0x7E00E0, 12),
                 quadrant=(0x7E00A6, 5), layer=(0x7E00EE, 1), recovery_stage=(0x7E00B0, 1),
                 camera_more=(0x7E0618, 8))
FIXTURE_CACHE = {0x7EC000 + offset + i for _, offset in CACHE_WORDS for i in (0, 1)}
FIXTURE_CACHE |= {0x7EC000 + offset for _, offset in CACHE_BYTES}
FIXTURE_SPRITES = {0x7E0000 + table + slot for table in
                   (0xDD0, 0xE20, 0xE30, 0xD80, 0xD90, 0xE00, 0xEE0, 0xD10, 0xD30, 0xD00, 0xD20, 0xF20)
                   for slot in (0, 14)} | {0x7E0DD0 + slot for slot in range(16)}


def allowed_write(address):
    return address in FIXTURE_SPRITES or address in FIXTURE_CACHE or address in (0x7E0632, 0x7E0633)


def target_case(name, x, y, sx, sy, layer):
    """Choose actual-world adversarial inputs; no fixed House/page assumptions."""
    if name == "cross-x": return x ^ 0x100, y, layer
    if name == "cross-y": return x, y ^ 0x100, layer
    if name == "offscreen-x":
        candidates = [v for v in range(x & 0xFF00, (x & 0xFF00) + 256) if ((v - sx) & 0xFFFF) > 0xF0]
        return min(candidates, key=lambda v: abs(v - x)), y, layer
    if name == "offscreen-y":
        candidates = [v for v in range(y & 0xFF00, (y & 0xFF00) + 256) if ((v - sy) & 0xFFFF) > 0xD0]
        return x, min(candidates, key=lambda v: abs(v - y)), layer
    if name == "other-layer": return x, y, layer ^ 1
    require(name == "near", "Unknown context fixture")
    candidates = [(x + dx, y + dy) for dx, dy in ((16, 16), (-16, 16), (16, -16), (-16, -16))]
    candidates = [(a, b) for a, b in candidates if 0 <= a <= 65535 and 0 <= b <= 65535
                  and a >> 8 == x >> 8 and b >> 8 == y >> 8
                  and ((a - sx) & 65535) <= 0xF0 and ((b - sy) & 65535) <= 0xD0]
    require(candidates, "No nonzero near target fits admitted current camera/page")
    return *candidates[0], layer


def check_context_return(entry, returned, accepted):
    require(number(returned["sp"]) == number(entry["sp"]) + 2
            and all(number(entry[k]) == number(returned[k]) for k in ("x", "y", "dbr", "d"))
            and number(entry["p"]) & 0xFE == number(returned["p"]) & 0xFE
            and bool(number(returned["p"]) & 1) == accepted,
            "Context guard short-return SP/carry/P/register ABI differs")


def describe(image, text, expect):
    p = cp.describe(image, text, "candidate")  # Both controls already have identity guards.
    require((p["transport_guard"] is not None) == (expect == "candidate"), "Wrong warp-context code profile")
    require(raw(image, 0x01FF28, len(CACHE_CODE)) == CACHE_CODE, "Native complete current-cache capture differs")
    require(raw(image, p["draw"], 4) == bytes.fromhex("2216E406"), "Draw does not call real PrepOamCoord")
    p.update(expect=expect, draw_return=p["long"] + 6, prep_oam_return=p["draw"] + 4,
             allocator=0x06F864, native_cache=0x01FF28)
    return p


def fixture_class(portal):
    class WarpFixture(cp.fixture_class(portal)):
        def write(self, address, value, reason):
            require(allowed_write(address) and self.paused() and 0 <= value <= 255,
                    "Forbidden/unpaused warp fixture write: " + hex(address))
            row = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(row)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            row["readback"] = self.b.read_memory(address)
            require(row["readback"] == value, "Fixture readback differs")

        def capture(self, name):
            r = super().capture(name)
            r["protected"] = {k: self.block(a, n).hex() for k, (a, n) in PROTECTED.items()}
            r["live_xy"] = [self.b.read_memory16(0x7E0022), self.b.read_memory16(0x7E0020)]
            r["cached_sprite_xy"] = self.block(0x7E0FD8, 4).hex()
            return r

        def position(self, slot, x, y, layer):
            for table, value in ((0xD10, x & 255), (0xD30, x >> 8), (0xD00, y & 255),
                                 (0xD20, y >> 8), (0xF20, layer)):
                self.write(0x7E0000 + table + slot, value, "disclosed split-coordinate/layer sprite input")

        def initialize(self):
            expected = 7 if self.a.world == "dungeon" else 9
            require((self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011)) == (expected, 0)
                    and self.b.read_memory(0x7E001B) == (self.a.world == "dungeon"), "Caller must provide actual normal world context")
            if self.a.world == "dungeon": require(self.b.read_memory16(0x7E00A0) == 0x104, "Dungeon fixture is cold House0104 only")
            require(self.b.read_memory(0x7E00B0) == 0, "Recovery stage must be neutral before fixtures")
            self.home = (self.b.read_memory16(0x7E0022), self.b.read_memory16(0x7E0020), self.b.read_memory(0x7E00EE))
            for slot in range(16): self.write(0x7E0DD0 + slot, 0, "disable actors before native Portal Prep")
            for table, value in ((0xE20, 3), (0xE30, 2), (0xD80, 1), (0xD90, 0), (0xE00, 0x40), (0xEE0, 0x40)):
                self.write(0x7E0000 + table, value, "source native-Prep fixture")
            self.position(0, *self.home)
            self.write(0x7E0DD0, 8, "execute real native state08 Portal Prep")
            row = dict(entry=self.run_to({self.code["prep"]}), returned=self.run_to({self.code["prep_return"]}))
            require(number(row["entry"]["x"]) == 0 and self.b.read_memory(0x7E0DD0) == 9, "Native Prep did not select/activate source0")
            self.run_to({util.SHIM_RETURN}); self.result["native_initialization"] = row

        def draw_case(self, offscreen):
            self.reset_idle()
            sx, sy = self.b.read_memory16(0x7E00E2), self.b.read_memory16(0x7E00E8)
            self.position(0, (sx + 512) & 65535 if offscreen else self.home[0], self.home[1], self.home[2])
            row = dict(name="draw-512-away" if offscreen else "draw-near", passed=False,
                       long_cpu=self.run_to({self.code["long"]}), entry_cpu=self.run_to({self.code["draw"]}))
            self.result["cases"].append(row)
            row["input"] = self.capture(row["name"] + "-before")
            require(self.b.read_memory16(0x7E0FD8) == ((sx + 512) & 65535 if offscreen else self.home[0]),
                    "Native cached sprite X does not match pre-frame fixture")
            row["prep_return_cpu"] = self.run_to({self.code["prep_oam_return"]})
            require(bool(number(row["prep_return_cpu"]["p"]) & 1) == offscreen, "Native PrepOamCoord carry differs")
            stop = self.run_to({self.code["allocator"], self.code["draw_return"]})
            allocated = number(stop["pc"]) == self.code["allocator"]
            require(allocated == (not offscreen or self.a.expect == "baseline"), "Offscreen Draw allocation admission differs")
            if allocated: stop = self.run_to({self.code["draw_return"]})
            require(number(stop["sp"]) == number(row["entry_cpu"]["sp"]) + 2
                    and number(stop["x"]) == 0 and number(stop["dbr"]) == self.code["long"] >> 16, "Draw short return ABI differs")
            row.update(allocated=allocated, return_cpu=stop, after=self.capture(row["name"] + "-after"), passed=True)
            require(row["input"]["protected"] == row["after"]["protected"], "Draw changed protected transport context")
            self.position(0, *self.home)  # Restore sprite only, while still paused before Main.

        def case(self, name):
            self.check_owner(); self.reset_idle(); self.position(0, *self.home)
            caller = self.run_to({self.code["call"]}); entry = self.run_to({self.code["main"]})
            action = (3 if self.a.color == "blue" else 4) + (2 if self.a.world == "overworld" else 0)
            idle = 1 if self.a.color == "blue" else 2
            x, y, layer = self.home
            tx, ty, tl = target_case(name, x, y, self.b.read_memory16(0x7E00E2), self.b.read_memory16(0x7E00E8), layer)
            for slot, subtype in ((0, 2 if idle == 1 else 1), (14, 1 if idle == 1 else 2)):
                for table, value in ((0xE20, 3), (0xE30, subtype), (0xDD0, 9)):
                    self.write(0x7E0000 + table + slot, value, "live opposite-color queued-warp identity input")
            self.position(14, tx, ty, tl)
            if name in ("cross-x", "cross-y"):
                # Both sprites share the wrong page: a sprite-to-sprite compare
                # would pass. Actual Link must be the source of truth.
                self.position(0, tx, ty, layer)
            self.write(0x7E0D80, action, "queued handler input at actual Main entry")
            self.write(0x7E0632, 0 if idle == 1 else 14, "blue cached handle")
            self.write(0x7E0633, 14 if idle == 1 else 0, "orange cached handle")
            if name == "near" and self.a.world == "dungeon":
                for address in sorted(FIXTURE_CACHE):
                    self.write(address, self.b.read_memory(address) ^ 0x80, "poison only native cache-owned fields; accepted warp must refresh all37 bytes")
            before = self.block(SPRITES, SIZE)
            row = dict(name=name, passed=False, color=self.a.color, world=self.a.world, target=[tx, ty, tl],
                       caller_cpu=caller, entry_cpu=entry, input=self.capture(name + "-before"))
            self.result["cases"].append(row)
            expected_cache = bytearray.fromhex(row["input"]["protected"]["cached_player_camera"])
            for source, offset in CACHE_WORDS: expected_cache[offset - 0x180:offset - 0x180 + 2] = self.block(0x7E0000 + source, 2)
            for source, offset in CACHE_BYTES: expected_cache[offset - 0x180] = self.b.read_memory(0x7E0000 + source)
            native_cache = bytes(expected_cache)
            expected_cache[4:8] = ty.to_bytes(2, "little") + tx.to_bytes(2, "little")
            watches = {}
            for key, (address, length) in {**PROTECTED, "target_timer": (0x7E0EEE, 1)}.items():
                ident = number(data(self.b.mem_watch_add(address, length, 512))["watch_id"])
                self.watches.add(ident); watches[key] = ident
            path = self.code["queued"][action]
            row["handler_cpu"] = self.run_to({path["entry"]})
            if self.a.expect == "baseline":
                row["effect_cpu"] = self.run_to({path["first_effect"]}); self.terminal = True
                row["unsafe_context_admitted_before_first_write"] = True
                row["after"] = self.capture(name + "-terminal")
                require(row["input"]["protected"] == row["after"]["protected"], "Baseline terminal stop advanced through a warp effect")
            else:
                row["context_cpu"] = self.run_to({self.code["transport_guard"]})
                row["context_return_cpu"] = self.run_to({path["context_return"]})
                a, b = row["context_cpu"], row["context_return_cpu"]
                check_context_return(a, b, name == "near")
                if name == "near" and self.a.world == "dungeon":
                    row["cache_entry_cpu"] = self.run_to({self.code["native_cache"]})
                    row["cache_return_cpu"] = self.run_to({path["first_effect"] + 4})
                    a, b = row["cache_entry_cpu"], row["cache_return_cpu"]
                    require(number(a["y"]) == number(b["y"]) == 14
                            and all(number(a[k]) == number(b[k]) for k in ("x", "dbr", "d"))
                            and number(b["sp"]) == number(a["sp"]) + 3
                            and number(b["p"]) & 0x30 == 0x30,
                            "Native full-cache capture changed validated target Y or its long-call ABI")
                row["return_cpu"] = self.run_to({self.code["return_pc"]})
                returned = row["return_cpu"]
                require(all(number(returned[k]) == number(caller[k]) for k in ("sp", "x", "dbr", "d"))
                        and number(returned["p"]) & 0x30 == 0x30, "Actual Main RTS ABI differs")
                row["after"] = self.capture(name + "-after")
                wanted = dict(row["input"]["protected"])
                expected_sprite = bytearray(before); expected_sprite[0xD80 - 0xB00] = idle
                if name == "near":
                    expected_sprite[0xEEE - 0xB00] = 0x40
                    if self.a.world == "dungeon":
                        wanted["cached_player_camera"] = expected_cache.hex(); wanted["module"] = "0714"
                    else:
                        wanted["player_xy"] = (ty.to_bytes(2, "little") + tx.to_bytes(2, "little")).hex()
                        wanted["movement"] = "01"
                    self.terminal = True  # No native recovery/hop frames in this boundary test.
                require(row["after"]["protected"] == wanted and self.block(SPRITES, SIZE) == expected_sprite,
                        "Queued warp changed unexpected context/sprite bytes or failed full-coordinate writes")
            row["protected_write_provenance"] = {k: data(self.b.mem_blame(watch_id=w)) for k, w in watches.items()}
            if name != "near":
                require(all(not t["writes"] for t in row["protected_write_provenance"].values()),
                        "Refused/terminal warp wrote a protected field even if byte value stayed equal")
            else:
                writes = row["protected_write_provenance"]
                changed_keys = {"cached_player_camera", "module", "recovery_stage", "target_timer"} if self.a.world == "dungeon" else {"player_xy", "movement", "target_timer"}
                require(all(not t["writes"] for k, t in writes.items() if k not in changed_keys),
                        "Accepted warp wrote a protected field outside its narrow contract")
                effect = path["first_effect"] if self.a.world == "dungeon" else path["first_effect"] - 3
                def exact(key, wanted):
                    observed = writes[key]["writes"]
                    require(len(observed) == len(wanted)
                            and all((number(w["addr"]), number(w["pc"]), number(w["value"]), number(w["size"])) == (*e, 1)
                                    for w, e in zip(observed, wanted)), "Unexpected native writer/size/value/order for " + key)
                exact("target_timer", [(0x7E0EEE, effect + (34 if self.a.world == "dungeon" else 22), 0x40)])
                if self.a.world == "dungeon":
                    exact("module", [(0x7E0011, effect + 41, 0x14)])
                    exact("recovery_stage", [(0x7E00B0, effect + 37, 0)])
                    cache_writes = []
                    pcs = (0xFF2C, 0xFF32, 0xFF38, 0xFF3E, 0xFF45, 0xFF4C, 0xFF53, 0xFF5A,
                           0xFF61, 0xFF68, 0xFF6F, 0xFF76, 0xFF7D, 0xFF84, 0xFF8A, 0xFF90)
                    for (_, off), pc in zip(CACHE_WORDS, pcs):
                        cache_writes += [(0x7EC000 + off + i, 0x010000 + pc, native_cache[off - 0x180 + i]) for i in (0, 1)]
                    for (_, off), pc in zip(CACHE_BYTES, (0xFF98, 0xFF9E, 0xFFA5, 0xFFAB, 0xFFB1)):
                        cache_writes.append((0x7EC000 + off, 0x010000 + pc, native_cache[off - 0x180]))
                    cache_writes += [(0x7EC184 + i, effect + 7 + i * 7, v) for i, v in enumerate(expected_cache[4:8])]
                    exact("cached_player_camera", cache_writes)
                else:
                    exact("player_xy", [(0x7E0020 + i, effect + 3 + i * 5, v)
                                         for i, v in enumerate(ty.to_bytes(2, "little") + tx.to_bytes(2, "little"))])
                    exact("movement", [(0x7E005D, effect + 27, 1)])
            for watch in watches.values(): self.remove_watch(watch)
            row["passed"] = True
    return WarpFixture


def main():
    p = argparse.ArgumentParser(description=__doc__)
    for n in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"): p.add_argument("--" + n, required=True)
    for n in ("status-file", "owned-rom", "symbols", "client-root", "owner-file", "output", "support-file"):
        p.add_argument("--" + n, type=Path, required=True)
    p.add_argument("--pid", type=int, required=True)
    p.add_argument("--world", choices=("dungeon", "overworld"), required=True)
    p.add_argument("--color", choices=("blue", "orange"), required=True)
    p.add_argument("--expect", choices=("baseline", "candidate"), required=True)
    p.add_argument("--execute-fixtures", action="store_true")
    a = p.parse_args(); require(a.execute_fixtures and a.pid > 0, "Explicit private fixture authorization required")
    image, symbols = a.owned_rom.read_bytes(), a.symbols.read_bytes()
    require(sha(image) == a.rom_sha256 and hashlib.sha1(image).hexdigest() == a.rom_sha1
            and sha(symbols) == a.symbols_sha256, "ROM/symbol identities differ")
    code = describe(image, symbols.decode(), a.expect); portal = util.load_support(a.support_file)
    a.output.mkdir(parents=True, exist_ok=False); sys.path.insert(0, str(a.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    f = fixture_class(portal)(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0), code)
    f.result.update(schema="portal-warp-context-boundary-v1", inputs=vars(a), code=code,
                    driver_sha256=sha(Path(__file__).read_bytes()), counterpart_sha256=CP_SHA,
                    claim="Explicit sprite/cache fixtures: Draw carry and queued near-warp boundary; no completed warp, placement, route or save acceptance")
    owned = False; saved = sram = None
    try:
        f.check_owner(); require(f.paused(), "Caller must pause owned CPU")
        require(not f.b.list_breakpoints() and not data(f.b.mem_watch_list())["watches"], "Existing probes; refuse shared session")
        owned = True; f.input("")
        saved = f.block(0x7EF000, SIZE); sram = bytes(f.b.read_block(0, 8192, "SnesSaveRam"))
        require(len(sram) == 8192, "Short native SRAM capture")
        (a.output / "before-saved-wram.bin").write_bytes(saved); (a.output / "before-native-sram.bin").write_bytes(sram)
        f.initialize(); f.draw_case(False); f.draw_case(True)
        for name in (("cross-x",) if a.expect == "baseline" else ("cross-x", "cross-y", "offscreen-x", "offscreen-y", "other-layer", "near")):
            f.case(name)
        require(f.terminal and all(row["passed"] for row in f.result["cases"]), "Incomplete terminal matrix")
        f.result["runtime_checks_passed"] = True
    except BaseException as error:
        f.result["error"] = repr(error)
        if owned:
            try: f.ensure_paused(); f.result["failure"] = f.capture("failure")
            except BaseException as e: f.result["failure_capture_error"] = repr(e)
    finally:
        if owned:
            for action in (lambda: f.input(""), f.ensure_paused):
                try: require(action() is not False, "Owned release/pause rejected")
                except BaseException as e: f.result["cleanup_errors"].append(repr(e))
            for remove, ids in ((f.remove, f.breakpoints), (f.remove_watch, f.watches)):
                for ident in list(ids):
                    try: remove(ident)
                    except BaseException as e: f.result["cleanup_errors"].append(repr(e))
            try:
                f.ensure_paused()
                for slot in range(16): f.write(0x7E0DD0 + slot, 0, "paused actor cleanup; caller must stop without resuming")
                f.result["final"] = f.capture("final")
                f.result["saved_wram_deltas"] = util.saved_wram_deltas(saved, f.block(0x7EF000, SIZE))
                f.result["native_sram_preserved"] = util.verify_native_sram(sram, bytes(f.b.read_block(0, 8192, "SnesSaveRam")))
            except BaseException as e: f.result["cleanup_errors"].append(repr(e))
        for path, pin in ((a.owned_rom, a.rom_sha256), (a.symbols, a.symbols_sha256), (CP_PATH, CP_SHA),
                          (a.support_file, cp.SUPPORT_SHA), (cp.UTIL_PATH, cp.UTIL_SHA)):
            try: require(sha(path.read_bytes()) == pin, "Input changed: " + str(path))
            except BaseException as e: f.result["cleanup_errors"].append(repr(e))
        f.result["terminal_no_resume"] = f.terminal
        f.result["passed"] = bool(f.result.get("runtime_checks_passed") and f.result.get("native_sram_preserved") and not f.result["cleanup_errors"])
        (a.output / "RESULT.json").write_text(json.dumps(f.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=f.result["passed"], result=str(a.output / "RESULT.json"))))
    return 0 if f.result["passed"] else 1

if __name__ == "__main__": raise SystemExit(main())
