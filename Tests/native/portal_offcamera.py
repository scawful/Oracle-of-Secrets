#!/usr/bin/env python3
"""Attach-only Portal off-camera persistence qualification in cold House0104.

Actual Y/allocator/FirePortal and native state08 Prep supply the two CAA values.
State-only occupancy, rod/magic, idle role/timer and sprite-position inputs are
explicit fixtures. Both paths run on-screen, X=screenX-128, then return. Two
paused predicate controls verify global freeze/submodule gates before bit7.
Those controls are not actual dialogue/transition acceptance. Caller owns cold
boot/launch/positive cleanup. No CPU/PC/register, camera, player-health,
invulnerability, save or savestate writes; the fixture never writes CAA.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
COUNTERPART_SHA = "05f61d02f82ea98b51eb01791a0bd3df375adbbc70efebb770d760223eb2ec10"
COUNTERPART_PATH = Path(__file__).with_name("portal_counterpart.py")
if hashlib.sha256(COUNTERPART_PATH.read_bytes()).hexdigest() != COUNTERPART_SHA:
    raise RuntimeError("Qualified Portal counterpart utilities differ")
_spec = importlib.util.spec_from_file_location("offcamera_counterpart_protocol", COUNTERPART_PATH)
cp = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cp)
util = cp.util
require, sha, number, raw, symbol, data = cp.require, cp.sha, cp.number, cp.raw, cp.symbol, cp.data
SPRITES, SIZE = cp.SPRITES, cp.SIZE
CALL, FIRE_RETURN = 0x07A52B, 0x07A52F
GATES = (0x7E0FC1, 0x7E0011)
EQUIPMENT = {0x7EF351: 2, 0x7EF3A6: 1, 0x7E0202: 0x19, 0x7E0303: 0x0D,
             0x7E0304: 0x0D, 0x7EF36E: 0x80, 0x7E06FE: 0, 0x7E0FA6: 0}
CASE_NAMES = ("dynamic-onscreen", "dynamic-offcamera", "dynamic-return",
              "prep-onscreen", "prep-offcamera", "prep-return", "prep-freeze-gate", "prep-submodule-gate")


def allowed_write(address):
    return (0x7E0DD0 <= address < 0x7E0DE0 or address in (0x7E0632, 0x7E0633)
            or address - 0x7E0000 in cp.SOURCE_TABLES or address in EQUIPMENT or address in GATES)


def expected_caa(expect, path):
    require(expect in ("baseline", "candidate") and path in ("dynamic", "prep"), "Unknown initialization profile")
    return (0x40 if path == "dynamic" else 0) | (0x80 if expect == "candidate" else 0)


def outcome(expect, path, offscreen, gate=None, already_dead=False):
    if already_dead:
        return dict(state=0, main=False)
    if expect == "baseline" and path == "dynamic" and offscreen:
        return dict(state=0, main=False)
    return dict(state=9, main=not gate and not (offscreen and expect == "baseline"))


def verify_oam_region_b(before, after, trace):
    """Only the observed native Region-B two-byte allocation is admissible."""
    require(len(before) == len(after) == SIZE, "Incomplete OAM counter capture")
    offset = 0xFE2 - 0xB00
    old = int.from_bytes(before[offset:offset + 2], "little")
    new = int.from_bytes(after[offset:offset + 2], "little")
    writes = trace["writes"]
    if not writes:
        require(old == new, "OAM Region-B counter changed without a native writer")
    else:
        require(len(writes) == 2, "Native OAM word store requires exactly two byte bus events")
        low, high = writes
        require(all(number(write["pc"]) == 0x0DBB41 and number(write["size"]) == 1
                    and number(write["opcode"]) == 0x99 for write in writes)
                and number(low["addr"]) == 0x7E0FE2 and number(high["addr"]) == 0x7E0FE3
                and number(low["value"]) == new & 255 and number(high["value"]) == new >> 8
                and number(low["sp"]) == number(high["sp"])
                and number(high["cycle"]) == number(low["cycle"]) + 1
                and before[0xE40 - 0xB00] & 0x1F == 1 and new == old + 8 and new < 0x0201,
                "Unexpected OAM Region-B writer/value/size/allocation delta")
    return dict(before=old, after=new, native_allocations=len(writes) // 2)


def describe(image: bytes, text: str, expect: str) -> dict:
    """Strict actual producer/gate guards; no ROM-copy normalization."""
    require(expect in ("baseline", "candidate"), "Unknown expected profile")
    prep = symbol(text, "Sprite_Portal_Prep")
    prep_bytes = bytes.fromhex("8B4BABA9") + bytes([0x80 if expect == "candidate" else 0])
    prep_bytes += bytes.fromhex("9DAA0CBD600F29C09D600F9E6B0BA9FF9DA00BAB6B")
    require(raw(image, prep, len(prep_bytes)) == prep_bytes, "Actual complete Portal Prep bytes differ")
    fire, finish = symbol(text, "LinkItem_FirePortal"), symbol(text, "LinkItem_FirePortal_finish")
    require(raw(image, CALL, 4) == b"\x22" + fire.to_bytes(3, "little")
            and raw(image, fire, 9) == bytes.fromhex("A903225DF61D10016B"), "Actual Y/JSL/allocator/RTL prefix differs")
    finish_bytes = bytes.fromhex("BB9E600D9E700D")
    if expect == "candidate": finish_bytes += bytes.fromhex("BDAA0C09809DAA0C")
    finish_bytes += bytes.fromhex("A9FF9DA00BFAAF0FA507853D642E9C00039C0103A9010C01036B")
    require(raw(image, finish, len(finish_bytes)) == finish_bytes, "Actual dynamic producer or final A/P return bytes differ")
    require(raw(image, 0x0DB728, 1) == b"\x40" and raw(image, 0x0DB83B, 6) == bytes.fromhex("B925B79DAA0C"),
            "Native Portal property table or CAA loader writer differs")
    active = symbol(text, "Sprite_CheckActive")
    require(raw(image, active, 30) == bytes.fromhex("BDD00DC909D013ADC10FD00EA511D00ABDAA0C3007BD000FF002186B386B"),
            "Global state/freeze/submodule gates no longer precede bit7/pause gate")
    require(raw(image, 0x06E485, 16) == bytes.fromhex("FE000FBDAA0C300422F8F10968683880")
            and raw(image, 0x09F1F8, 14) == bytes.fromhex("BDAA0C2940D004A51BD0479ED00D"), "Native OAM culling/kill guard differs")
    require(raw(image, 0x1DF6A1, 6) == bytes.fromhex("DABB2218B80D")
            and raw(image, 0x1DF6CD, 2) == bytes.fromhex("986B"), "Actual dynamic property load/allocator return differs")
    require(raw(image, 0x0DBB41, 3) == bytes.fromhex("99E00F")
            and raw(image, 0x0DBA84, 4) == bytes.fromhex("A002800E")
            and raw(image, 0x0DBAA0, 2) == bytes.fromhex("0102"), "Native Region-B OAM writer/selector/limit differs")
    # Actual image is admitted directly; cp accepts only exact00/80 Prep.
    plan = cp.describe(image, text, "candidate")
    plan.update(expect=expect, fire=fire, finish=finish, actual_prep_bytes=prep_bytes.hex(),
                actual_finish_bytes=finish_bytes.hex(), active=active, active_call=plan["long"] + 6,
                active_return=plan["long"] + 10, prep_caa_writer=prep + 5,
                dynamic_caa_writer=finish + 12 if expect == "candidate" else None,
                property_caa_writer=0x0DB83E, allocator_return=0x1DF6CE, case_count=8)
    return plan


def fixture_class(portal):
    class OffcameraFixture(cp.fixture_class(portal)):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge, code)
            self.path = "dynamic"
            self.gate_originals = None
            self.home = None

        def write(self, address, value, reason):
            require(allowed_write(address), "Forbidden off-camera fixture write: " + hex(address))
            require(0 <= value <= 255 and self.paused(), "Fixture byte write requires paused CPU")
            item = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(item)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            item["readback"] = self.b.read_memory(address)
            require(item["readback"] == value, "Fixture write readback differs")

        def capture(self, name):
            snap = super().capture(name)
            snap["protected"]["scroll_registers"] = self.block(0x7E00E0, 12).hex()
            snap["source"].update(caa=self.b.read_memory(0x7E0CAA), pause=self.b.read_memory(0x7E0F00),
                                  bulletproof=self.b.read_memory(0x7E0BA0), hitbox=self.b.read_memory(0x7E0F60),
                                  x=self.b.read_memory(0x7E0D10) | self.b.read_memory(0x7E0D30) << 8,
                                  y=self.b.read_memory(0x7E0D00) | self.b.read_memory(0x7E0D20) << 8)
            snap["freeze"] = self.b.read_memory(GATES[0])
            return snap

        def restore_gates(self):
            if self.gate_originals is not None:
                for address, value in self.gate_originals.items():
                    self.write(address, value, "restore paused predicate input before any later branch/frame continuation")

        def neutral_frames(self, count):
            require(self.gate_originals is not None and all(self.b.read_memory(a) == v for a, v in self.gate_originals.items()),
                    "Gate predicate fixture must be restored before FRAME")
            return super().neutral_frames(count)

        def position(self, x, y):
            for table, value in ((0xD10, x & 255), (0xD30, x >> 8), (0xD00, y & 255), (0xD20, y >> 8)):
                self.write(0x7E0000 + table, value, "disclosed source-only screen-boundary/return position fixture")

        def isolate_idle(self):
            for slot in range(1, 16): self.write(0x7E0DD0 + slot, 0, "remove occupancy actors before any sprite frame")
            for table, value in ((0xE30, 2), (0xD80, 1), (0xD90, 0), (0xE00, 0x40), (0xEE0, 0x40)):
                self.write(0x7E0000 + table, value, "idle blue role/timer fixture; initialization proof does not claim natural placement")
            self.home = ((self.b.read_memory16(0x7E0022) + 0x30) & 65535,
                         (self.b.read_memory16(0x7E0020) - 0x10) & 65535)
            self.position(*self.home)

        def verify_producer(self, trace, path):
            writes = trace["writes"]
            expected = [(self.code["property_caa_writer"], 0x40, 1)]
            writer = self.code["prep_caa_writer"] if path == "prep" else self.code["dynamic_caa_writer"]
            if writer is not None: expected.append((writer, expected_caa(self.a.expect, path), 1))
            require([(number(w["pc"]), number(w["value"]), number(w["size"])) for w in writes] == expected
                    and all(number(w["addr"]) == 0x7E0CAA for w in writes),
                    "Actual unique ordered CAA initialization producers differ")

        def dynamic_spawn(self):
            require((self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011), self.b.read_memory16(0x7E00A0))
                    == (7, 0, 0x104), "Caller must supply cold House0104")
            self.gate_originals = {a: self.b.read_memory(a) for a in GATES}
            require(not any(self.gate_originals.values()), "Caller must supply unfrozen normal submodule")
            for address, value in EQUIPMENT.items(): self.write(address, value, "explicit Portal Rod/equip/magic/count/selector fixture")
            for slot in range(16): self.write(0x7E0DD0 + slot, 0, "remove actors before the actual controller Y boundary")
            watch = self.watch(0x7E0CAA)
            self.input("Y")
            record = dict(caller_cpu=self.run_to({CALL}))
            self.input("")
            # Install occupancy only after Link actually reaches its JSL: no
            # artificial occupied slot can execute before allocation/cleanup.
            for slot in range(1, 16): self.write(0x7E0DD0 + slot, 9, "paused actual-Y JSL occupancy forces allocator free slot0")
            record["occupancy_at_call"] = self.capture("dynamic-y-call-occupancy")
            require(self.block(0x7E0DD0, 16) == bytes([0] + [9] * 15), "Occupancy differs at actual Y JSL")
            record["fire_entry_cpu"] = self.run_to({self.code["fire"]})
            entry = record["fire_entry_cpu"]
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 3)
            record["long_return_stack"] = stack.hex()
            require(number(entry["sp"]) == number(record["caller_cpu"]["sp"]) - 3 and stack == bytes.fromhex("2EA507")
                    and number(entry["dbr"]) == 7 and number(entry["d"]) == 0 and number(entry["p"]) & 0x30 == 0x30,
                    "Actual Y FirePortal JSL ABI differs")
            record["allocator_return_cpu"] = self.run_to({self.code["allocator_return"]})
            require(number(record["allocator_return_cpu"]["y"]) == 0, "Native allocator did not select free slot0")
            record["finish_cpu"] = self.run_to({self.code["finish"]})
            record["return_cpu"] = self.run_to({FIRE_RETURN})
            returned, caller = record["return_cpu"], record["caller_cpu"]
            require(all(number(returned[k]) == number(caller[k]) for k in ("sp", "x", "dbr", "d"))
                    and number(returned["p"]) & 0x30 == 0x30 and number(returned["a"]) & 255 == 1,
                    "Actual successful FirePortal RTL/final A ABI differs")
            record["producer"] = data(self.b.mem_blame(watch_id=watch))
            self.verify_producer(record["producer"], "dynamic")
            self.remove_watch(watch)
            record["actual_spawn"] = self.capture("dynamic-native-spawn")
            require(record["actual_spawn"]["source"]["state"] == 9 and record["actual_spawn"]["source"]["kind"] == 3,
                    "Actual Y did not initialize an active Portal")
            self.result["dynamic_initialization"] = record
            self.isolate_idle()

        def native_prep(self):
            for slot in range(16): self.write(0x7E0DD0 + slot, 0, "remove dynamic trial actors before independent native Prep")
            self.neutral_frames(90)
            require(self.b.read_memory(0x7E003A) & 0x40 == 0 and self.b.read_memory(0x7E0300) == 0, "Native Y animation did not settle")
            watch = self.watch(0x7E0CAA)
            super().initialize()
            trace = data(self.b.mem_blame(watch_id=watch))
            self.verify_producer(trace, "prep")
            self.remove_watch(watch)
            self.result["native_initialization"]["caa_producer"] = trace
            self.path = "prep"
            self.isolate_idle()

        def observe(self, name, *, offscreen=False, gate=None):
            self.check_owner()
            wanted = outcome(self.a.expect, self.path, offscreen, gate,
                             already_dead=self.b.read_memory(0x7E0DD0) == 0)
            record = dict(name=name, path=self.path, offscreen=offscreen, gate=gate, expected=wanted, passed=False)
            self.result["cases"].append(record)
            if wanted["state"] == 0 and self.b.read_memory(0x7E0DD0) == 0:
                record["input"] = self.capture(name + "-before")
                self.neutral_frames(2)
                record["after"] = self.capture(name + "-after")
                require(record["after"]["source"]["state"] == 0
                        and record["after"]["source"]["caa"] == expected_caa(self.a.expect, self.path)
                        and record["after"]["protected"] == record["input"]["protected"],
                        "Deleted baseline Portal return changed state/CAA/protected context")
                record["expected_dead_no_dispatch"] = True
                record["passed"] = True
                return
            record["long_entry_cpu"] = self.run_to({self.code["long"]})
            before = self.block(SPRITES, SIZE)
            record["input"] = self.capture(name + "-before")
            state_watch = self.watch(0x7E0DD0)
            oam_watch = number(data(self.b.mem_watch_add(0x7E0FE2, 2, 128))["watch_id"])
            self.watches.add(oam_watch)
            record["active_call_cpu"] = self.run_to({self.code["active_call"]})
            caller = record["active_call_cpu"]
            if gate:
                self.write(GATES[0] if gate == "freeze" else GATES[1], 1, "paused CheckActive predicate input; not actual text/transition")
                record["gate_input"] = self.capture(name + "-gate")
            record["check_entry_cpu"] = self.run_to({self.code["active"]})
            record["check_return_cpu"] = self.run_to({self.code["active_return"]})
            checked = record["check_return_cpu"]
            require(all(number(checked[k]) == number(caller[k]) for k in ("sp", "x", "y", "dbr", "d"))
                    and number(checked["p"]) & 0x30 == 0x30 and bool(number(checked["p"]) & 1) == wanted["main"],
                    "Actual CheckActive return ABI/carry differs")
            # Restore predicate inputs at the JSL return, before even its caller's branch.
            self.restore_gates()
            require(all(self.b.read_memory(a) == v for a, v in self.gate_originals.items()),
                    "Predicate bytes were not restored at CheckActive return")
            record["gates_restored_cpu"] = self.cpu()
            reached = self.run_to({self.code["main"], self.code["return_pc"]})
            record["first_boundary_cpu"] = reached
            require((number(reached["pc"]) == self.code["main"]) == wanted["main"], "Native Main admission differs")
            if wanted["main"]:
                stack = self.block(0x7E0000 + number(reached["sp"]) + 1, 2)
                record["main_short_stack"] = stack.hex()
                require(number(reached["sp"]) == number(caller["sp"]) - 2
                        and stack == ((self.code["return_pc"] - 1) & 65535).to_bytes(2, "little"), "Native Main JSR short stack differs")
                reached = self.run_to({self.code["return_pc"]})
            record["return_cpu"] = reached
            require(all(number(reached[k]) == number(caller[k]) for k in ("sp", "x", "dbr", "d"))
                    and number(reached["p"]) & 0x30 == 0x30, "Native Long/Main boundary ABI differs")
            record["after"] = self.capture(name + "-after")
            after = self.block(SPRITES, SIZE)
            require(record["after"]["source"]["state"] == wanted["state"]
                    and record["after"]["source"]["caa"] == expected_caa(self.a.expect, self.path), "Native persistence/CAA result differs")
            require(record["input"]["protected"] == record["after"]["protected"], "Native Portal trial changed player/camera/cache/context")
            allowed = {0x7E0BC0, 0x7E0DD0, 0x7E0D90, 0x7E0E00, 0x7E0F00, 0x7E0FA8, 0x7E0FA9}
            changes = [SPRITES + i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            record["changed_sprite_addresses"] = [f"{a:06X}" for a in changes]
            record["state_write_provenance"] = data(self.b.mem_blame(watch_id=state_watch))
            record["oam_region_b_write_provenance"] = data(self.b.mem_blame(watch_id=oam_watch))
            record["oam_region_b"] = verify_oam_region_b(before, after, record["oam_region_b_write_provenance"])
            require(set(changes) - {0x7E0FE2, 0x7E0FE3} <= allowed,
                    "Portal trial changed another actor or unexpected sprite/global byte")
            writes = record["state_write_provenance"]["writes"]
            if wanted["state"] == 0:
                require(len(writes) == 1 and number(writes[0]["pc"]) == 0x09F203
                        and number(writes[0]["value"]) == 0, "Missing actual native offcamera kill writer")
            else: require(not writes, "Live Portal unexpectedly had a state writer")
            self.remove_watch(state_watch)
            self.remove_watch(oam_watch)
            if offscreen:
                require(record["after"]["source"]["pause"] != 0, "Off-camera fixture did not exercise native culling")
                self.neutral_frames(60)
                record["after60"] = self.capture(name + "-after60")
                require(record["after60"]["source"]["state"] == wanted["state"]
                        and record["after60"]["source"]["caa"] == expected_caa(self.a.expect, self.path), "Portal state/CAA did not survive the requested sixty native frames")
                require(record["after60"]["protected"] == record["after"]["protected"],
                        "Protected player/camera/cache/context drifted during the sixty-frame off-camera hold")
                require(record["after60"]["source"]["pause"] != 0,
                        "Sixty-frame hold no longer has the native off-camera pause flag")
                require(self.block(0x7E0DD0, 16) == bytes([wanted["state"]] + [0] * 15),
                        "Another actor became active during the isolated off-camera hold")
            record["passed"] = True

        def path_cases(self):
            self.observe(self.path + "-onscreen")
            self.position((self.b.read_memory16(0x7E00E2) - 0x80) & 65535, self.home[1])
            self.observe(self.path + "-offcamera", offscreen=True)
            self.position(*self.home)
            self.observe(self.path + "-return")

    return OffcameraFixture


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
    fixture.result.update(schema="portal-offcamera-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=cp.SUPPORT_SHA,
                          counterpart_sha256=COUNTERPART_SHA, protocol_utilities_sha256=cp.UTIL_SHA,
                          claim="Actual Y/native Prep producer and disclosed actor/position/idle/gate fixtures; offcamera dispatch only, no natural placement, dialogue, transition, warp, route or save acceptance")
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
        fixture.dynamic_spawn(); fixture.path_cases()
        fixture.native_prep(); fixture.path_cases()
        fixture.observe("prep-freeze-gate", gate="freeze")
        fixture.observe("prep-submodule-gate", gate="submodule")
        require([c["name"] for c in fixture.result["cases"]] == list(CASE_NAMES)
                and all(c["passed"] for c in fixture.result["cases"]), "Incomplete eight-case matrix")
        fixture.result["runtime_checks_passed"] = True
    except BaseException as error:
        fixture.result["error"] = repr(error)
        if owned:
            try:
                fixture.ensure_paused(); fixture.result["failure"] = fixture.capture("failure")
            except BaseException as capture_error: fixture.result["failure_capture_error"] = repr(capture_error)
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
                fixture.ensure_paused(); fixture.restore_gates()
                if fixture.home is not None: fixture.position(*fixture.home)
                for slot in range(16): fixture.write(0x7E0DD0 + slot, 0, "paused diagnostic actor cleanup before caller disposes process")
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
