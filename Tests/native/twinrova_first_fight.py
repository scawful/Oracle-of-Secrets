#!/usr/bin/env python3
"""Attach-only Twinrova first-fight initialization regression.

The caller supplies a paused, private cold House 0104 process and owns launch,
reservation and positive process cleanup. This test discloses an entrance34
reload, a DB->AC engine fall, native state08 actor inputs and follower history
fixtures. It never sets CPU registers/PC, directly calls game code, loads a
state, writes Link health/reward grants, or saves. Saved room-flag/follower inputs
are logged and restored. Each independent case supplies TimerD=0 because the
native loader retains that AI timer; arbitrary stale AI timers are not tested.
Dirty dead-slot properties
are diagnostic inputs, not a claim that an ordinary route creates those bytes.

Six cases: ordinary Prep, maiden suppression, healthy follower spawn, dirty CE
follower spawn, dirty non-CE follower spawn, defeated Prep. Baseline PASS means
the old stale-property behavior was characterized. Candidate PASS requires
native property writes plus shared startup, actual long-call return and AI
survival. Ordinary B acknowledgments may close the native opening dialogue.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True
SUPPORT_SHA = "bac027161d84ff12cc56a3a987f52545800da173c37044b22a5cae35ded6ce0f"
SPRITES, SIZE = 0x7E0B00, 0x500
CALL, RETURN, SPAWN, SPAWN_RTL = 0x09A21D, 0x09A221, 0x1DA03C, 0x1DA080
SHIM, SHIM_RETURN, LOADER = 0x068EB9, 0x068EBD, 0x0DB818
FIELDS = {"hp": 0x0E50, "bump": 0x0CD2, "hitbox": 0x0F60, "oam": 0x0E40,
          "deflection": 0x0CAA, "gfx": 0x0E60, "palette": 0x0F50,
          "tile_interaction": 0x0B6B, "prize": 0x0BE0}
EXPECTED = dict(zip(FIELDS, (0x5A, 4, 0x83, 6, 0x80, 0x10, 0, 2, 0)))
DIRTY = dict(zip(FIELDS, (1, 0x0F, 0, 0x1F, 0x42, 0x40, 0x0E, 1, 0x80)))
COMMON = bytes.fromhex(
    "A95A9D500EA9809DAA0CA9049DD20CBD600E29BF9D600E"
    "A90F9D500DA90F9D500DA9108508A9108509A9609D100E"
    "A9019DB00DA9029DE00DA9049DB00EA9079DC00D9C690B")
PREP_PREFIX = bytes.fromhex("AD030410049ED00D6B8B4BABAFCCF37EC906D0039ED00D")
SPAWN_SUFFIX = bytes.fromhex(
    "A200A9099DD00DA9CE9D200EA5009D100DA5019D300DA50238E9109D000D"
    "A5039D200DA9C09D100EA9009DC00DA9029DE00D9DA00B"
    "AD030409208D03049C690B6B")
ENTRANCE_WRITES = ((0x7E010E, 0x34), (0x7E010F, 0), (0x7E010A, 1),
                   (0x7E04AA, 0), (0x7E001B, 1), (0x7E0011, 0),
                   (0x7E00B0, 0), (0x7E0010, 5))


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def pc(address):
    require(address & 0x8000, "Expected LoROM ROM address")
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def raw(image, address, size):
    result = image[pc(address):pc(address) + size]
    require(len(result) == size, "ROM guard extends outside image")
    return result


def symbol(text, name):
    matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?"
                         + re.escape(name) + r"\s*$", text, re.MULTILINE)
    values = {int(a + b, 16) for a, b in matches}
    require(len(values) == 1, "Missing or ambiguous symbol: " + name)
    return values.pop()


def data(reply):
    require(reply.get("success"), "Native command rejected: " + str(reply))
    value = reply.get("data", {})
    return json.loads(value) if isinstance(value, str) else value


def load_support(path):
    require(sha(path.read_bytes()) == SUPPORT_SHA, "Portal support source hash differs")
    spec = importlib.util.spec_from_file_location("twinrova_portal_support", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def describe(image: bytes, text: str, expect: str) -> dict:
    """File-only admission. Expected rows come from guarded ROM/source contracts."""
    require(expect in ("baseline", "candidate"), "Unknown expected code profile")
    prep = symbol(text, "Sprite_Twinrova_Prep")
    graphics = symbol(text, "ApplyTwinrovaGraphics")
    wrapper = symbol(text, "Sprite_PrepExp_Long")
    dispatch = symbol(text, "NewSprPrepTable")
    table = symbol(text, "NewSprPrepRoutinesLong")
    require(raw(image, CALL, 4) == b"\x22" + SPAWN.to_bytes(3, "little"),
            "Actual follower caller JSL differs")
    require(raw(image, SPAWN + 4, len(SPAWN_SUFFIX)) == SPAWN_SUFFIX
            and SPAWN + 4 + len(SPAWN_SUFFIX) - 1 == SPAWN_RTL,
            "Fixed spawn coordinates/state/flags/manual overrides/RTL differ")
    require(raw(image, prep, len(PREP_PREFIX)) == PREP_PREFIX,
            "Defeated guard or maiden suppression prefix differs")
    require(raw(image, SHIM, 5) == b"\x22" + wrapper.to_bytes(3, "little") + b"\x60",
            "Native Prep JSL/RTS shim differs")
    require(raw(image, wrapper, 9) == b"\x8b\x4b\xab\x22" + dispatch.to_bytes(3, "little") + b"\xab\x6b",
            "Native custom Prep wrapper differs")
    require(raw(image, 0x06865B + 0xCE * 2, 2) == (SHIM & 0xFFFF).to_bytes(2, "little")
            and raw(image, table + 0xCE * 3, 3) == prep.to_bytes(3, "little"),
            "Native state08 does not dispatch CE to the pinned custom Prep")
    require(raw(image, 0x06864D, 10) == bytes.fromhex("2218B80DFED00DBD200E"),
            "Native property-load/state09/dispatch prefix differs")
    require(raw(image, LOADER, 17) == bytes.fromhex("2271B80D5A8B4BABBC200EB980B09D400E"),
            "Native reset/type/OAM loader prefix differs")
    require(raw(image, 0x0DB829, 6) == bytes.fromhex("2200EC3AEAEA")
            and raw(image, 0x3AEC00, 6) == bytes.fromhex("B973B19D500E"),
            "Native balance health loader differs")
    rows = {"oam": (0x0DB080, 6), "hp": (0x0DB173, 0),
            "hitbox": (0x0DB44C, 0x83), "prize": (0x0DB632, 0),
            "deflection": (0x0DB725, 0x40), "bump": (0x0DB266, 0),
            "tile_interaction": (0x0DB53F, 2), "gfx": (0x0DB359, 0x10)}
    for name, (address, value) in rows.items():
        require(raw(image, address + 0xCE, 1) == bytes([value]),
                "Native CE property row differs: " + name)
    for address, pattern in ((0x0DB82F, "B94CB49D600F"), (0x0DB835, "B932B69DE00B"),
                             (0x0DB83B, "B925B79DAA0C"), (0x0DB841, "B966B29DD20C"),
                             (0x0DB847, "B93FB59D6B0B"),
                             (0x0DB860, "BC200EB959B39D600E290F9D500F")):
        require(raw(image, address, len(bytes.fromhex(pattern))) == bytes.fromhex(pattern),
                "Native table writer differs at " + hex(address))
    result = dict(expect=expect, prep=prep, main=symbol(text, "Sprite_Twinrova_Main"),
                  graphics=graphics, wrapper=wrapper, prep_return=wrapper + 7,
                  call=CALL, return_pc=RETURN, spawn=SPAWN, spawn_rtl=SPAWN_RTL,
                  native_rows={k: dict(table=a, value=v) for k, (a, v) in rows.items()})
    if expect == "baseline":
        require(raw(image, SPAWN, 4) == b"\x22" + graphics.to_bytes(3, "little"),
                "Baseline spawn does not directly call graphics")
        init = prep + len(PREP_PREFIX)
        require(raw(image, init, len(COMMON) + 2) == COMMON + b"\xab\x6b",
                "Baseline inline startup differs")
        result.update(initialize=init, first_fight_helper=None)
    else:
        init = symbol(text, "Twinrova_Initialize")
        helper = symbol(text, "Twinrova_FirstFightPrep")
        require(raw(image, SPAWN, 4) == b"\x22" + helper.to_bytes(3, "little"),
                "Candidate fixed hook does not call FirstFightPrep")
        require(raw(image, prep + len(PREP_PREFIX), 5) == b"\x20" + (init & 0xFFFF).to_bytes(2, "little") + b"\xab\x6b",
                "Candidate normal Prep does not reuse shared startup")
        require(raw(image, init, len(COMMON) + 1) == COMMON + b"\x60",
                "Candidate shared startup differs")
        expected = (bytes.fromhex("8B4BABDAA200A9CE9D200E2218B80D20")
                    + (init & 0xFFFF).to_bytes(2, "little")
                    + b"\xfa\xab\x5c" + graphics.to_bytes(3, "little"))
        require(raw(image, helper, len(expected)) == expected,
                "Candidate must select slot0/typeCE BEFORE native loader, preserve X/DBR and tailcall graphics")
        result.update(initialize=init, first_fight_helper=helper)
    result["health_store"] = result["initialize"] + 2
    return result


def properties(sprite_bytes):
    require(len(sprite_bytes) == SIZE, "Incomplete sprite capture")
    return {name: sprite_bytes[address - 0x0B00] for name, address in FIELDS.items()}


def fixture_class(portal):
    class TwinrovaFixture(portal.Fixture):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge)
            self.deadline = time.monotonic() + 240
            self.code, self.watches = code, set()

        def check_owner(self):
            require(time.monotonic() < self.deadline, "240-second fixture deadline exceeded")
            record = json.loads(self.a.owner_file.read_text())
            require(record.get("owner") == self.a.owner and record.get("active") is True,
                    "Private caller ownership is not active")
            return super().check_owner()

        def ensure_paused(self):
            if self.paused():
                return
            require(self.b.pause(), "Owned pause rejected")
            until = time.monotonic() + 3
            while time.monotonic() < until:
                if self.paused():
                    return
                time.sleep(0.01)
            raise RuntimeError("Owned pause did not settle")

        def write(self, address, value, reason):
            fixed = {a for a, _ in ENTRANCE_WRITES} | {
                0x7E00A0, 0x7E00A1, 0x7E00A2, 0x7E00A3, 0x7E0020, 0x7E0021,
                0x7E0022, 0x7E0023, 0x7EF159, 0x7EF3CC, 0x7E0403,
                0x7FE0D8, 0x7FE0D9, 0x7E0EE0}
            tables = set(FIELDS.values()) | {0x0DD0, 0x0E20, 0x0D00, 0x0D10,
                                             0x0D20, 0x0D30, 0x0F20}
            allowed = address in fixed or 0x7E1A00 <= address < 0x7E1A64 or any(
                0x7E0000 + t <= address < 0x7E0010 + t for t in tables)
            require(allowed, "Forbidden fixture write: " + hex(address))
            require(0 <= value <= 255 and self.paused(), "Fixture write requires a paused CPU and byte value")
            entry = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(entry)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            entry["readback"] = self.b.read_memory(address)
            require(entry["readback"] == value, "Fixture readback differs")

        def word(self, address, value, reason):
            self.write(address, value & 255, reason)
            self.write(address + 1, value >> 8, reason)

        def watch(self, address):
            ident = number(data(self.b.mem_watch_add(address, 1, 128))["watch_id"])
            self.watches.add(ident)
            return ident

        def remove_watch(self, ident):
            reply = self.b.mem_watch_remove(ident)
            require(reply.get("success"), "Native watch removal rejected: " + str(reply))
            self.watches.remove(ident)

        def capture(self, name):
            require(self.paused(), "Capture requires paused CPU")
            sprites = self.block(SPRITES, SIZE)
            saved = self.block(0x7EF000, SIZE)
            sram = bytes(self.b.read_block(0, 8192, "SnesSaveRam"))
            require(len(sram) == 8192, "Short native SRAM capture")
            for suffix, blob in (("sprites", sprites), ("saved-wram", saved), ("native-sram", sram)):
                (self.a.output / f"{name}-{suffix}.bin").write_bytes(blob)
            return dict(cpu=self.cpu(), frame=number(self.b.get_rom_info()["frameCount"]),
                        module=self.b.read_memory(0x7E0010), submodule=self.b.read_memory(0x7E0011),
                        room=self.b.read_memory16(0x7E00A0), follower=self.b.read_memory(0x7EF3CC),
                        room_flags=self.b.read_memory(0x7E0403), properties=properties(sprites),
                        state=self.b.read_memory(0x7E0DD0), kind=self.b.read_memory(0x7E0E20),
                        action=self.b.read_memory(0x7E0D80), timer_c=self.b.read_memory(0x7E0E10),
                        timer_d=self.b.read_memory(0x7E0EE0),
                        x=self.b.read_memory16(0x7E0022), y=self.b.read_memory16(0x7E0020),
                        sprite_x=self.b.read_memory(0x7E0D10) + 256 * self.b.read_memory(0x7E0D30),
                        sprite_y=self.b.read_memory(0x7E0D00) + 256 * self.b.read_memory(0x7E0D20),
                        player_hp=self.b.read_memory(0x7EF36D),
                        sprites_sha256=sha(sprites), saved_wram_sha256=sha(saved), native_sram_sha256=sha(sram))

        def frame(self, count, buttons=""):
            self.check_owner()
            require(self.paused(), "FRAME requires settled pause")
            self.input(buttons)
            before = number(self.b.get_rom_info()["frameCount"])
            require(self.b.send_command("FRAME", {"count": str(count)}).get("success"), "FRAME rejected")
            until = min(self.deadline, time.monotonic() + 10)
            while time.monotonic() < until:
                now = number(self.b.get_rom_info()["frameCount"])
                if now >= before + count and self.paused():
                    require(now <= before + count + 1, "Unexpected FRAME overshoot")
                    self.input("")
                    self.result["frame_advances"].append(dict(buttons=buttons, requested=count, before=before, after=now))
                    return
                time.sleep(0.01)
            raise RuntimeError("Native FRAME did not complete")

        def acknowledge(self):
            # Native opening message123 is a real AI effect. Never write module/text/health to dismiss it.
            for _ in range(90):
                module = self.b.read_memory(0x7E0010)
                if module != 0x0E:
                    require(module == 7, "Unexpected module during ordinary dialogue acknowledgment")
                    return
                self.frame(2, "B")
                self.frame(2)
            raise RuntimeError("Opening dialogue did not close with ordinary B input")

        def settle_room(self, room):
            seen = []
            for _ in range(90):
                state = (self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011),
                         self.b.read_memory16(0x7E00A0))
                if not seen or list(state) != seen[-1]:
                    seen.append(list(state))
                if state == (7, 0, room):
                    return seen
                if state[0] == 0x0E:
                    self.acknowledge()
                    continue
                self.frame(4)
            raise RuntimeError("Engine room fixture did not settle: " + str(seen))

        def history(self, trigger=False):
            y, x = (0x155C, 0x1978) if trigger else (0x1C00, 0x1600)
            for i in range(20):
                for base, value in ((0x1A00, y & 255), (0x1A14, y >> 8),
                                    (0x1A28, x & 255), (0x1A3C, x >> 8), (0x1A50, 0)):
                    self.write(0x7E0000 + base + i, value, "explicit follower history trigger" if trigger else "keep maiden outside trigger while native Prep runs")

        def enter_room(self):
            require((self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011),
                     self.b.read_memory16(0x7E00A0)) == (7, 0, 0x104), "Caller must provide cold House0104")
            self.write(0x7EF3CC, 6, "maiden fixture before entrance34")
            self.history()
            for address, value in ENTRANCE_WRITES:
                self.write(address, value, "exact entrance34 engine reload fixture")
            self.result["entrance34_sequence"] = self.settle_room(0xDB)
            self.frame(60)
            self.acknowledge()
            self.result["before_fall"] = self.capture("before-fall")
            require((self.result["before_fall"]["module"], self.result["before_fall"]["submodule"],
                     self.result["before_fall"]["room"]) == (7, 0, 0xDB),
                    "Entrance34 must finish dialogue in native roomDB before fall inputs")
            for address, value in ((0x7E00A2, 0xDB), (0x7E00A3, 0), (0x7E00A0, 0xAC),
                                   (0x7E00A1, 0), (0x7E00B0, 0), (0x7EF159, 0),
                                   (0x7FE0D8, 0), (0x7FE0D9, 0)):
                self.write(address, value, "DB->AC engine fall fixture and clear AC saved/death flags")
            self.word(0x7E0022, 0x1680, "old-room fall X: in-room0080")
            self.word(0x7E0020, 0x1BC0, "old-room fall Y: in-room01C0")
            self.write(0x7E0011, 7, "enter native indoor fall reload submodule")
            self.result["fall_sequence"] = self.settle_room(0xAC)
            self.frame(60)
            self.acknowledge()
            self.result["arrival"] = self.capture("arrival")
            require((self.result["arrival"]["module"], self.result["arrival"]["submodule"],
                     self.result["arrival"]["room"]) == (7, 0, 0xAC),
                    "Native roomAC must finish dialogue before initialization cases")
            require(self.b.read_memory(0x7E0E20) == 0xCE and self.b.read_memory(0x7E0DD0) == 0,
                    "Native AC room-list CE did not suppress itself with maiden present")
            require(self.b.read_memory(0x7E0403) & 0x80 == 0, "AC defeated flag unexpectedly set")

        def native_prep(self, name, follower, defeated=False):
            self.check_owner()
            self.history()
            for i in range(16):
                self.write(0x7E0DD0 + i, 0, "disable other actors before native initialization fixture")
            self.write(0x7EF3CC, follower, "native Prep follower input")
            self.write(0x7E0403, 0x80 if defeated else 0, "native Prep defeated-bit control")
            self.write(0x7E0EE0, 0, "independent-case TimerD input; native loader retains this AI timer")
            self.write(0x7E0E20, 0xCE, "native state08 CE input")
            for table, value in ((0x0D10, 0x78), (0x0D30, 0x19), (0x0D00, 0x3C),
                                 (0x0D20, 0x15), (0x0F20, 0)):
                self.write(0x7E0000 + table, value, "native initialization actor location/layer")
            self.write(0x7E0DD0, 8, "native state08 property loader and custom Prep dispatch")
            trace = dict(shim_cpu=self.run_to({SHIM}))
            require(number(trace["shim_cpu"]["x"]) == 0, "Native state08 selected another slot")
            trace["prep_cpu"] = self.run_to({self.code["prep"]})
            entry = trace["prep_cpu"]
            require(number(entry["x"]) == 0 and number(entry["d"]) == 0 and number(entry["p"]) & 0x30 == 0x30,
                    "Unexpected native Prep X/DP/MX ABI")
            trace["return_cpu"] = self.run_to({self.code["prep_return"]})
            require(number(trace["return_cpu"]["sp"]) == number(entry["sp"]) + 3
                    and number(trace["return_cpu"]["dbr"]) == number(entry["dbr"]),
                    "Prep long return corrupted stack or DBR")
            trace["snapshot"] = self.capture(name + "-prep-return")
            require(trace["snapshot"]["timer_d"] == 0, "Independent-case TimerD input changed before Prep return")
            expect = dict(EXPECTED)
            if defeated:
                expect.update(hp=0, bump=0, deflection=0x40)
            require(trace["snapshot"]["properties"] == expect, "Native Prep properties differ")
            require(trace["snapshot"]["state"] == (0 if follower == 6 or defeated else 9),
                    "Maiden/defeated/ordinary native Prep state differs")
            trace["shim_return_cpu"] = self.run_to({SHIM_RETURN})
            require(number(trace["shim_return_cpu"]["sp"]) == number(trace["shim_cpu"]["sp"]),
                    "Native state08 dispatch did not restore complete caller stack")
            return trace

        def ai(self, case, name, expected_hp, require_progress=True):
            start = self.capture(name + "-ai-start")
            samples = []
            for i in range(2):
                self.acknowledge()
                self.frame(30)
                self.acknowledge()
                sample = self.capture(name + f"-ai-{(i + 1) * 30}")
                samples.append(sample)
                require(sample["state"] == 9 and sample["kind"] == 0xCE and sample["properties"]["hp"] == expected_hp,
                        "Twinrova died/despawned or lost initialized HP during native AI")
                require(sample["player_hp"] > 0 and sample["room"] == 0xAC and sample["module"] == 7,
                        "Player died or left the admitted encounter during AI observation")
            case["ai"] = dict(start=start, samples=samples, requested_neutral_frames=60)
            if require_progress:
                require(len({s["action"] for s in [start] + samples}) > 1
                        or any(s["timer_c"] != start["timer_c"] for s in samples),
                        "Frame advancement alone did not prove native AI progression")

        def prep_control(self, name, follower, defeated=False, survival=False):
            case = dict(name=name, passed=False)
            self.result["cases"].append(case)
            case["native_prep"] = self.native_prep(name, follower, defeated)
            if survival:
                self.ai(case, name, 0x5A)
            case["passed"] = True

        def spawn_case(self, name, dirty=False, non_ce=False):
            case = dict(name=name, passed=False, dirty_properties=dirty, prior_non_ce=non_ce)
            self.result["cases"].append(case)
            case["suppressed_native_prep"] = self.native_prep(name, 6)
            if dirty:
                for key, table in FIELDS.items():
                    self.write(0x7E0000 + table, DIRTY[key], "dead slot0 stale-property diagnostic input")
            if non_ce:
                self.write(0x7E0E20, 3, "dead slot0 prior non-CE type: native loader must select CE first")
            require(self.b.read_memory(0x7E0DD0) == 0, "Dirty input must remain a dead slot")
            case["before_trigger"] = self.capture(name + "-before-trigger")
            watches = {key: self.watch(0x7E0000 + address) for key, address in FIELDS.items()}
            self.history(trigger=True)
            case["caller_cpu"] = self.run_to({CALL})
            before_call = self.block(SPRITES, SIZE)
            (self.a.output / f"{name}-caller-sprites.bin").write_bytes(before_call)
            caller = case["caller_cpu"]
            require(number(caller["d"]) == 0 and number(caller["p"]) & 0x30 == 0x30,
                    "Actual follower caller DP/MX ABI differs")
            scratch = self.block(0x7E0000, 4)
            case["follower_xy_cache"] = scratch.hex()
            case["spawn_cpu"] = self.run_to({SPAWN})
            entry = case["spawn_cpu"]
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 3)
            case["long_return_stack"] = stack.hex()
            require(number(entry["sp"]) == number(caller["sp"]) - 3 and stack == bytes.fromhex("20A209"),
                    "Actual follower JSL stack differs")
            if self.a.expect == "candidate":
                case["helper_cpu"] = self.run_to({self.code["first_fight_helper"]})
                case["loader_cpu"] = self.run_to({LOADER})
                require(number(case["loader_cpu"]["x"]) == 0 and self.b.read_memory(0x7E0E20) == 0xCE,
                        "First-fight loader did not receive slot0/typeCE")
                case["initialize_cpu"] = self.run_to({self.code["initialize"]})
                require(self.b.read_memory(0x7E0E50) == 0, "Native CE health table load was bypassed")
            case["spawn_rtl_cpu"] = self.run_to({SPAWN_RTL})
            case["immediate"] = self.capture(name + "-spawn-rtl")
            observed = case["immediate"]["properties"]
            after_call = self.block(SPRITES, SIZE)
            guarded_tables = set(FIELDS.values()) | {0x0DD0, 0x0E20, 0x0D00, 0x0D10,
                                                     0x0D20, 0x0D30, 0x0D80, 0x0E10}
            require(all(before_call[t - 0x0B00 + 1:t - 0x0B00 + 16]
                        == after_call[t - 0x0B00 + 1:t - 0x0B00 + 16] for t in guarded_tables),
                    "First-fight spawn changed a guarded field in another sprite slot")
            case["other_15_slot_fields_preserved"] = True
            expected = DIRTY if dirty and self.a.expect == "baseline" else EXPECTED
            require(observed == expected, "Immediate first-fight properties differ from selected profile")
            case["matches_intended_properties"] = observed == EXPECTED
            require(self.block(0x7E0000, 4) == scratch, "Spawn helper corrupted follower position cache")
            expected_x = int.from_bytes(scratch[:2], "little")
            expected_y = (scratch[2] - 0x10) % 256 + scratch[3] * 256
            require((case["immediate"]["sprite_x"], case["immediate"]["sprite_y"]) == (expected_x, expected_y),
                    "Native spawn did not use the actual follower position cache")
            require((case["immediate"]["state"], case["immediate"]["kind"], case["immediate"]["follower"]) == (9, 0xCE, 0)
                    and self.b.read_memory(0x7E0BA0) == 2 and self.b.read_memory(0x7E0DC0) == 0
                    and self.b.read_memory(0x7E0E10) == 0xC0 and self.b.read_memory(0x7E0403) & 0x20,
                    "Native follower dismissal/spawn/manual overrides/room flag differ")
            case["write_provenance"] = {key: data(self.b.mem_blame(watch_id=ident)) for key, ident in watches.items()}
            if self.a.expect == "candidate":
                writers = {"hp": self.code["health_store"], "bump": self.code["initialize"] + 12,
                           "deflection": self.code["initialize"] + 7, "oam": 0x0DB826,
                           "hitbox": 0x0DB832, "prize": 0x0DB838, "gfx": 0x0DB866,
                           "palette": 0x0DB86B, "tile_interaction": 0x0DB84A}
                for key, address in writers.items():
                    trace = case["write_provenance"][key]["writes"]
                    actual = [w for w in trace if number(w["pc"]) == address and number(w["addr"]) == 0x7E0000 + FIELDS[key]]
                    require(len(actual) == 1 and number(actual[0]["value"]) == EXPECTED[key]
                            and number(actual[0]["size"]) == 1, "Missing unique native initialization writer: " + key)
            else:
                require(all(not trace["writes"] for trace in case["write_provenance"].values()),
                        "Baseline unexpectedly repaired a stale property")
            for ident in watches.values():
                self.remove_watch(ident)
            case["return_cpu"] = self.run_to({RETURN})
            returned = case["return_cpu"]
            require(number(returned["sp"]) == number(caller["sp"])
                    and number(returned["dbr"]) == number(caller["dbr"])
                    and number(returned["y"]) == number(caller["y"])
                    and number(returned["d"]) == number(caller["d"])
                    and number(returned["p"]) & 0x30 == number(caller["p"]) & 0x30,
                    "Spawn RTL corrupted caller SP/DBR/Y/DP/MX ABI")
            case["first_main_cpu"] = self.run_to({self.code["main"]})
            require(number(case["first_main_cpu"]["x"]) == 0,
                    "Native Main did not execute for initialized slot0")
            self.ai(case, name, expected["hp"], require_progress=not (dirty and self.a.expect == "baseline"))
            case["passed"] = True

    return TwinrovaFixture


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
    require(args.execute_fixtures and args.pid > 0, "Explicit owned diagnostic fixture authorization required")
    image, symbols = args.owned_rom.read_bytes(), args.symbols.read_bytes()
    require(sha(image) == args.rom_sha256.lower(), "Owned ROM SHA256 differs")
    require(hashlib.sha1(image).hexdigest() == args.rom_sha1.lower(), "Owned ROM SHA1 differs")
    require(sha(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 differs")
    code = describe(image, symbols.decode(), args.expect)
    portal = load_support(args.support_file)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = fixture_class(portal)(args, bridge, code)
    fixture.result.update(schema="twinrova-first-fight-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=SUPPORT_SHA,
                          claim="native initialization plus bounded AI with explicit room/slot/follower fixtures; no ordinary route/defeat/save proof")
    owned = False
    saved_before = sram_before = None
    try:
        fixture.check_owner()
        require(fixture.paused(), "Caller must supply paused owned CPU")
        require(not bridge.list_breakpoints(), "Existing breakpoints; refuse shared debug session")
        require(not data(bridge.mem_watch_list())["watches"], "Existing memory watches; refuse shared debug session")
        owned = True
        fixture.input("")
        saved_before = fixture.block(0x7EF000, SIZE)
        sram_before = bytes(bridge.read_block(0, 8192, "SnesSaveRam"))
        require(len(sram_before) == 8192, "Short native SRAM capture")
        (args.output / "before-saved-wram.bin").write_bytes(saved_before)
        (args.output / "before-native-sram.bin").write_bytes(sram_before)
        fixture.enter_room()
        fixture.prep_control("ordinary-prep", 0, survival=True)
        fixture.prep_control("maiden-present-prep", 6)
        fixture.spawn_case("healthy-prior-ce")
        fixture.spawn_case("dirty-prior-ce", dirty=True)
        fixture.spawn_case("dirty-prior-non-ce", dirty=True, non_ce=True)
        fixture.prep_control("defeated-prep", 0, defeated=True)
        require(len(fixture.result["cases"]) == 6 and all(c["passed"] for c in fixture.result["cases"]),
                "Incomplete six-case initialization matrix")
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
                try:
                    require(action() is not False, "Owned pause/release rejected")
                except BaseException as error:
                    fixture.result["cleanup_errors"].append(repr(error))
            for ident in list(fixture.breakpoints):
                try:
                    fixture.remove(ident)
                except BaseException as error:
                    fixture.result["cleanup_errors"].append(repr(error))
            for ident in list(fixture.watches):
                try:
                    fixture.remove_watch(ident)
                except BaseException as error:
                    fixture.result["cleanup_errors"].append(repr(error))
            try:
                fixture.ensure_paused()
                for slot in range(16):
                    fixture.write(0x7E0DD0 + slot, 0, "remove diagnostic actors before caller disposes private process")
                if saved_before is not None:
                    for address in (0x7EF159, 0x7EF3CC):
                        fixture.write(address, saved_before[address - 0x7EF000], "restore explicit saved-WRAM fixture input; never save")
                fixture.result["final"] = fixture.capture("final")
                after = fixture.block(0x7EF000, SIZE)
                fixture.result["saved_wram_changed_offsets"] = [i for i, (a, b) in enumerate(zip(saved_before, after)) if a != b]
                require(bytes(bridge.read_block(0, 8192, "SnesSaveRam")) == sram_before, "Diagnostic test changed native SRAM")
                fixture.result["native_sram_preserved"] = True
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        for path, pin in ((args.owned_rom, args.rom_sha256), (args.symbols, args.symbols_sha256),
                          (args.support_file, SUPPORT_SHA)):
            try:
                require(sha(path.read_bytes()) == pin.lower(), "Input changed: " + str(path))
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed")
                                       and fixture.result.get("native_sram_preserved")
                                       and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=fixture.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
