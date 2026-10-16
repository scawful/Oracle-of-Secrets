#!/usr/bin/env python3
"""Attach-only Manhandla phase/death routine qualification in cold House0104.

Caller owns launch, reservation and positive process cleanup. This test supplies
one state08 type88/body plus explicit dead-head, subtype, phase and boss-HP
inputs. Native Intro allocates the heads, then native Emerge/Flower reuses a
head slot. Actual Long JSR/checker/RTS boundaries qualify nine cases. Only the
final candidate case continues into native Main09/state04. No CPU/PC writes,
direct game calls, savestates, player-health/invulnerability writes or saves.
This is not a natural D1 encounter, head-kill, prize, route or save test.
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
SPRITES, SIZE, BODY = 0x7E0B00, 0x500, 0
SHIM, SHIM_RETURN = 0x068EB9, 0x068EBD
TABLES = {"state": 0x0DD0, "kind": 0x0E20, "subtype": 0x0E30,
          "phase": 0x0E90, "action": 0x0D80, "hp": 0x0E50,
          "timer_a": 0x0DF0, "oam": 0x0E40}
INPUT_TABLES = set(TABLES.values()) | {0x0D00, 0x0D10, 0x0D20, 0x0D30, 0x0F20}
CASE_NAMES = ("phase0-live-heads", "phase0-dead-heads", "phase2-hp4-live-flower",
              "protected-phase3-hp2", "nonbody-head1-hp2", "nonbody-flower8-hp2",
              "nonbody-blastA-hp2", "phase2-hp3-live-flower", "phase2-hp2-live-flower")


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def pc(address):
    require(address & 0x8000, "Expected LoROM ROM address")
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def raw(image, address, size):
    value = image[pc(address):pc(address) + size]
    require(len(value) == size, "ROM guard extends outside image")
    return value


def symbol(text, name):
    values = {int(a + b, 16) for a, b in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?" + re.escape(name) + r"\s*$",
        text, re.MULTILINE)}
    require(len(values) == 1, "Missing or ambiguous symbol: " + name)
    return values.pop()


def data(reply):
    require(reply.get("success"), "Native command rejected: " + str(reply))
    value = reply.get("data", {})
    return json.loads(value) if isinstance(value, str) else value


def load_support(path):
    require(sha(path.read_bytes()) == SUPPORT_SHA, "Portal support source hash differs")
    spec = importlib.util.spec_from_file_location("manhandla_portal_support", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def relative_target(image, address):
    distance = raw(image, address + 1, 1)[0]
    return address + 2 + (distance if distance < 128 else distance - 256)


def unique_store(image, start, end, prefix, target):
    code = raw(image, start, end - start)
    pattern = bytes.fromhex(prefix) + b"\x9d" + target.to_bytes(2, "little")
    require(code.count(pattern) == 1, "Missing or ambiguous checker writer: " + hex(target))
    return start + code.index(pattern) + len(bytes.fromhex(prefix))


def describe(image: bytes, text: str, expect: str) -> dict:
    """File-only guards for actual native dispatch and independently defined outcomes."""
    require(expect in ("baseline", "candidate"), "Unknown expected code profile")
    names = {"long": "Sprite_Manhandla_Long", "checker": "Sprite_Manhandla_CheckForNextPhaseOrDeath",
             "prep": "Sprite_Manhandla_Prep", "main": "Sprite_Manhandla_Main", "intro": "Manhandla_Intro",
             "emerge": "BigChuchu_Emerge", "flower": "Flower_Flicker", "dead": "BigChuchu_Dead",
             "not_dead": "Sprite_Manhandla_CheckForNextPhaseOrDeath_not_dead",
             "join": "Sprite_Manhandla_CheckForNextPhaseOrDeath_offspring3_dead",
             "phase2": "Sprite_Manhandla_CheckForNextPhaseOrDeath_phase2",
             "phase2_return": "Sprite_Manhandla_CheckForNextPhaseOrDeath_phase2_not_dead",
             "main_return": "Sprite_Manhandla_Long_SpriteIsNotActive"}
    plan = {key: symbol(text, name) for key, name in names.items()}
    wrapper = symbol(text, "Sprite_PrepExp_Long")
    require(raw(image, SHIM, 5) == b"\x22" + wrapper.to_bytes(3, "little") + b"\x60",
            "Native Prep JSL/RTS shim differs")
    require(raw(image, 0x06864D, 10) == bytes.fromhex("2218B80DFED00DBD200E"),
            "Native state08 property-load/state09 prefix differs")
    require(raw(image, 0x06865B + 0x88 * 2, 2) == (SHIM & 0xFFFF).to_bytes(2, "little")
            and raw(image, symbol(text, "NewSprPrepRoutinesLong") + 0x88 * 3, 3) == plan["prep"].to_bytes(3, "little"),
            "Native state08 does not select the exact Manhandla Prep")
    require(raw(image, 0x069283 + 0x88 * 2, 2) == bytes.fromhex("F8FF")
            and raw(image, 0x06FFF8, 5) == bytes.fromhex("2200803060")
            and raw(image, symbol(text, "NewSprRoutinesLong") + 0x88 * 3, 3) == plan["long"].to_bytes(3, "little"),
            "Native normal-state dispatch does not select exact Manhandla Long")
    require(raw(image, plan["long"] + 11, 6) == b"\x8b\x4b\xab\x20" + (plan["checker"] & 0xFFFF).to_bytes(2, "little"),
            "Actual Long PHB/PHK/PLB/JSR checker ABI differs")
    require(raw(image, plan["main_return"], 2) == bytes.fromhex("AB6B"), "Long exit ABI differs")
    head_start = plan["checker"]
    if expect == "candidate":
        require(raw(image, head_start, 4) == bytes.fromhex("BD300ED0")
                and relative_target(image, head_start + 3) == plan["not_dead"],
                "Candidate subtype guard does not refuse nonbody actors")
        require(raw(image, head_start + 5, 4) == bytes.fromhex("BD900ED0")
                and relative_target(image, head_start + 8) == plan["join"],
                "Candidate phase bypass must land at speed07 join")
        head_start += 10
    else:
        require(raw(image, head_start, 3) == bytes.fromhex("AD4107"), "Baseline head gate prefix differs")
    # Identical head gates, existing speed writes, phase transition and low-HP death body.
    gates = b""
    for index, speed in ((0x741, 5), (0x742, 6), (0x743, 7)):
        gates += b"\xad" + index.to_bytes(2, "little") + bytes.fromhex("A8B9D00DF0034C")
        gates += (plan["not_dead"] & 0xFFFF).to_bytes(2, "little") + bytes([0xA9, speed]) + bytes.fromhex("8D3600")
    require(raw(image, head_start, len(gates)) == gates, "Legacy head-state gates or speed setup differ")
    transition = bytes.fromhex("BD900ED01FA9019D900EA9409DF00DA9409D500EA9089D400EA9079D800DA90A8D360060")
    require(raw(image, plan["join"], 5) == bytes.fromhex("A9078D3600")
            and raw(image, plan["join"] + 5, len(transition)) == transition,
            "Existing phase0 transition fields/speed differ")
    death = bytes.fromhex("BD900EC903F020BD500EC904B019A9509DF00DA9099D800DA9138D2C01A9049D900EA90A8D360060")
    require(raw(image, plan["phase2"], len(death)) == death, "Existing protected-phase/HP threshold/death fields differ")
    require(raw(image, plan["dead"], 13) == bytes.fromhex("A9FF9DC00BA9049DD00D9E500E"),
            "Actual Main09 death-state writer differs")
    plan["phase_writers"] = {"phase": unique_store(image, plan["join"], plan["phase2"], "A901", 0xE90),
                             "action": unique_store(image, plan["join"], plan["phase2"], "A907", 0xD80)}
    plan["death_writers"] = {"phase": unique_store(image, plan["phase2"], plan["phase2_return"] + 1, "A904", 0xE90),
                             "action": unique_store(image, plan["phase2"], plan["phase2_return"] + 1, "A909", 0xD80)}
    producers = {}
    for key, name, cache in (("left", "SpawnLeftManhandlaHead", 0x741),
                             ("right", "SpawnRightManhandlaHead", 0x742),
                             ("center", "SpawnCenterMandhandlaHead", 0x743)):
        address = symbol(text, name)
        require(raw(image, address, 7) == bytes.fromhex("A988225DF61D30")
                and raw(image, address + 8, 4) == b"\x98\x8d" + cache.to_bytes(2, "little"),
                "Head producer allocator/cache writer differs: " + key)
        producers[key] = dict(entry=address, cache=cache, store=address + 9)
    flower = raw(image, plan["flower"], plan["emerge"] - plan["flower"])
    pattern = bytes.fromhex("988D4307")
    require(flower.count(pattern) == 1 and bytes.fromhex("A988225DF61D30") in flower,
            "Native Flower allocator/cache identity differs")
    plan.update(expect=expect, call=plan["long"] + 14, return_pc=plan["long"] + 17,
                prep_return=wrapper + 7, producers=producers,
                flower_store=plan["flower"] + flower.index(pattern) + 1,
                final_state_store=plan["dead"] + 7)
    return plan


def expected_result(expect, subtype, phase, hp, heads_alive):
    """Expected control flow comes from the proposed contract, not observed native bytes."""
    if subtype and expect == "candidate":
        return "unchanged"
    if heads_alive and (expect == "baseline" or phase == 0):
        return "unchanged"
    if phase == 0:
        return "emerge"
    if phase != 3 and hp < 4:
        return "death"
    return "alive"


def saved_wram_deltas(before, after):
    require(len(before) == len(after) == SIZE, "Incomplete saved-WRAM preservation capture")
    return [dict(address=f"{0x7EF000 + i:06X}", before=a, after=b)
            for i, (a, b) in enumerate(zip(before, after)) if a != b]


def verify_native_sram(before, after):
    require(len(before) == len(after) == 8192, "Incomplete native SRAM preservation capture")
    require(before == after, "Routine fixture changed native SRAM")
    return True


def fixture_class(portal):
    class ManhandlaFixture(portal.Fixture):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge)
            self.deadline = time.monotonic() + 240
            self.code, self.watches = code, set()
            self.safe_phase, self.safe_action, self.safe_hp = 0, 6, 0x80

        def check_owner(self):
            require(time.monotonic() < self.deadline, "240-second fixture deadline exceeded")
            owner = json.loads(self.a.owner_file.read_text())
            require(owner.get("owner") == self.a.owner and owner.get("active") is True, "Private caller ownership is not active")
            return super().check_owner()

        def add(self, address):
            # All custom heads/flowers use this Long. Native expression filtering keeps the body boundary exact.
            ident = self.b.add_breakpoint(address, condition="x == 0")
            require(isinstance(ident, int) and ident >= 0, "Could not install owned body breakpoint")
            self.breakpoints.add(ident)
            return ident

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
            allowed = address == 0x7E0036 or any(0x7E0000 + t <= address < 0x7E0010 + t for t in INPUT_TABLES)
            require(allowed, "Forbidden fixture write: " + hex(address))
            require(0 <= value <= 255 and self.paused(), "Fixture write requires paused CPU and byte value")
            record = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(record)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            record["readback"] = self.b.read_memory(address)
            require(record["readback"] == value, "Fixture readback differs")

        def watch(self, address):
            ident = number(data(self.b.mem_watch_add(address, 1, 128))["watch_id"])
            self.watches.add(ident)
            return ident

        def remove_watch(self, ident):
            reply = self.b.mem_watch_remove(ident)
            require(reply.get("success"), "Native watch removal rejected: " + str(reply))
            self.watches.remove(ident)

        def capture(self, name):
            require(self.paused(), "Capture requires settled pause")
            sprites, saved = self.block(SPRITES, SIZE), self.block(0x7EF000, SIZE)
            sram = bytes(self.b.read_block(0, 8192, "SnesSaveRam"))
            require(len(sram) == 8192, "Short native SRAM capture")
            for suffix, blob in (("sprites", sprites), ("saved-wram", saved), ("native-sram", sram)):
                (self.a.output / f"{name}-{suffix}.bin").write_bytes(blob)
            return dict(cpu=self.cpu(), frame=number(self.b.get_rom_info()["frameCount"]),
                        body={k: sprites[t - 0xB00] for k, t in TABLES.items()},
                        offspring=list(self.block(0x7E0741, 3)), speed=self.b.read_memory(0x7E0036),
                        music=self.b.read_memory(0x7E012C), hp=self.b.read_memory(0x7EF36D),
                        module=self.b.read_memory(0x7E0010), room=self.b.read_memory16(0x7E00A0),
                        sprites_sha256=sha(sprites), saved_wram_sha256=sha(saved), native_sram_sha256=sha(sram))

        def restore_body(self):
            for table, value in ((0xE30, 0), (0xE90, self.safe_phase), (0xD80, self.safe_action),
                                 (0xE50, self.safe_hp), (0xDD0, 9)):
                self.write(0x7E0000 + table, value, "restore controlled body before permitting native Main between routine cases")
            self.write(0x7E0036, 7 if self.safe_phase else 4, "restore native phase speed before Main")

        def initialize(self):
            require((self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011),
                     self.b.read_memory16(0x7E00A0)) == (7, 0, 0x104), "Caller must provide cold House0104")
            require(not self.b.read_memory(0x7E0403) & 0x80, "House defeated flag blocks native Prep")
            for slot in range(16):
                self.write(0x7E0DD0 + slot, 0, "disable actors before controlled native state08 body")
            x = (self.b.read_memory16(0x7E0022) + 0x60) & 0xFFFF
            y = (self.b.read_memory16(0x7E0020) - 0x50) & 0xFFFF
            for table, value in ((0xE20, 0x88), (0xE30, 0), (0xD10, x & 255), (0xD30, x >> 8),
                                 (0xD00, y & 255), (0xD20, y >> 8), (0xF20, 0)):
                self.write(0x7E0000 + table, value, "native body type/subtype/location/layer input")
            self.write(0x7E0DD0, 8, "execute native state08 property loader and Manhandla Prep")
            init = dict(shim_cpu=self.run_to({SHIM}), prep_cpu=self.run_to({self.code["prep"]}))
            require(number(init["prep_cpu"]["x"]) == 0, "Native Prep selected another slot")
            init["prep_return_cpu"] = self.run_to({self.code["prep_return"]})
            init["snapshot"] = self.capture("native-prep")
            require(init["snapshot"]["body"]["hp"] == 0x80 and init["snapshot"]["body"]["state"] == 9,
                    "Native body Prep did not initialize active HP80")
            init["shim_return_cpu"] = self.run_to({SHIM_RETURN})
            watches = {k: self.watch(0x7E0000 + p["cache"]) for k, p in self.code["producers"].items()}
            init["first_long_cpu"] = self.run_to({self.code["call"]})
            init["intro_cpu"] = self.run_to({self.code["intro"]})
            init["main_return_cpu"] = self.run_to({self.code["main_return"]})
            init["after_intro"] = self.capture("native-intro")
            heads = init["after_intro"]["offspring"]
            require(heads == [15, 14, 13], "Native Intro did not allocate the expected fresh head slots")
            for key, slot, subtype in zip(("left", "right", "center"), heads, (3, 2, 1)):
                require(self.b.read_memory(0x7E0DD0 + slot) == 9 and self.b.read_memory(0x7E0E20 + slot) == 0x88
                        and self.b.read_memory(0x7E0E30 + slot) == subtype, "Native Intro head identity differs")
                trace = data(self.b.mem_blame(watch_id=watches[key]))
                init.setdefault("head_write_provenance", {})[key] = trace
                writes = [w for w in trace["writes"] if number(w["pc"]) == self.code["producers"][key]["store"]]
                require(len(writes) == 1 and number(writes[0]["value"]) == slot, "Missing actual native Intro head cache writer")
            for ident in watches.values():
                self.remove_watch(ident)
            require(init["after_intro"]["body"]["action"] == 6, "Native Intro did not reach body action6")
            self.result["native_initialization"] = init
            return heads

        def routine_case(self, name, subtype, phase, hp, *, heads_alive, final=False, clear_heads=()):
            self.check_owner()
            self.restore_body()
            caller = self.run_to({self.code["call"]})
            require(number(caller["x"]) == 0 and number(caller["dbr"]) == self.code["long"] >> 16
                    and number(caller["d"]) == 0 and number(caller["p"]) & 0x30 == 0x30,
                    "Actual Long caller X/DBR/DP/MX ABI differs")
            # Keep the real heads allocated until this exact boundary: an intervening
            # body Main can spawn beams into any slot freed earlier.
            for slot in clear_heads:
                self.write(0x7E0DD0 + slot, 0, "explicit head-death fixture at checker JSR; not earned head kills")
            require(not clear_heads or all(self.b.read_memory(0x7E0DD0 + slot) == 0 for slot in clear_heads),
                    "Controlled head slots were not dead at the actual checker boundary")
            for table, value in ((0xE30, subtype), (0xE90, phase), (0xE50, hp), (0xD80, 6 if phase == 0 else 4)):
                self.write(0x7E0000 + table, value, "checker subtype/phase/HP/action diagnostic input")
            self.write(0x7E0036, 0x55, "speed preservation canary at actual checker JSR")
            before = self.block(SPRITES, SIZE)
            case = dict(name=name, passed=False, caller_cpu=caller, input=self.capture(name + "-before"),
                        expected=expected_result(self.a.expect, subtype, phase, hp, heads_alive),
                        cleared_heads_at_call=list(clear_heads))
            self.result["cases"].append(case)
            watched = {k: self.watch(0x7E0000 + TABLES[k]) for k in ("phase", "action")}
            case["entry_cpu"] = self.run_to({self.code["checker"]})
            entry = case["entry_cpu"]
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 2)
            case["short_return_stack"] = stack.hex()
            require(number(entry["sp"]) == number(caller["sp"]) - 2
                    and stack == ((self.code["return_pc"] - 1) & 0xFFFF).to_bytes(2, "little"),
                    "Actual native JSR did not push the exact two-byte short return")
            case["return_cpu"] = self.run_to({self.code["return_pc"]})
            returned = case["return_cpu"]
            require(all(number(returned[k]) == number(caller[k]) for k in ("sp", "x", "dbr", "d"))
                    and number(returned["p"]) & 0x30 == number(caller["p"]) & 0x30,
                    "Checker RTS corrupted caller SP/X/DBR/DP/MX ABI")
            case["after"] = self.capture(name + "-after")
            after = self.block(SPRITES, SIZE)
            expected = dict(case["input"]["body"])
            speed = 0x55
            outcome = case["expected"]
            if outcome == "emerge":
                expected.update(phase=1, timer_a=0x40, hp=0x40, oam=8, action=7)
                speed = 0x0A
            elif outcome == "death":
                expected.update(phase=4, timer_a=0x50, action=9)
                speed = 0x0A
            elif outcome == "alive":
                speed = 7
            require(case["after"]["body"] == expected and case["after"]["speed"] == speed,
                    "Native checker output or phase speed differs from independent expected result")
            if outcome == "death":
                require(case["after"]["music"] == 0x13, "Native death music writer did not execute")
            else:
                require(case["after"]["music"] == case["input"]["music"], "Nondeath checker changed music")
            allowed = {0xE90, 0xDF0, 0xE50, 0xE40, 0xD80} if outcome in ("emerge", "death") else set()
            changes = [SPRITES + i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            case["changed_sprite_addresses"] = [f"{a:06X}" for a in changes]
            require(all(a - 0x7E0000 in allowed for a in changes), "Checker changed another slot or an unexpected sprite field")
            case["write_provenance"] = {k: data(self.b.mem_blame(watch_id=v)) for k, v in watched.items()}
            for key, trace in case["write_provenance"].items():
                writes = trace["writes"]
                if outcome in ("emerge", "death"):
                    writer = self.code["phase_writers" if outcome == "emerge" else "death_writers"][key]
                    require(len(writes) == 1 and number(writes[0]["pc"]) == writer
                            and number(writes[0]["value"]) == expected[key] and number(writes[0]["size"]) == 1,
                            "Missing unique actual phase/action transition writer")
                else:
                    require(not writes, "Nontransition checker unexpectedly wrote phase/action")
            for ident in watched.values():
                self.remove_watch(ident)
            if final and outcome == "death":
                case["dead_main_cpu"] = self.run_to({self.code["dead"]})
                state_watch = self.watch(0x7E0DD0)
                case["dead_main_return_cpu"] = self.run_to({self.code["main_return"]})
                case["native_death"] = self.capture(name + "-native-death")
                trace = data(self.b.mem_blame(watch_id=state_watch))
                case["native_death_state_writes"] = trace
                require(case["native_death"]["body"]["state"] == 4 and case["native_death"]["body"]["hp"] == 0,
                        "Native Main09 did not enter explosion state04 with HP0")
                require(any(number(w["pc"]) == self.code["final_state_store"] and number(w["value"]) == 4
                            for w in trace["writes"]), "Missing actual Main09 state04 writer")
                self.remove_watch(state_watch)
            case["passed"] = True
            return case

        def flower_producer(self):
            # Continue the actual phase0 all-heads-dead output; neither action7 nor timer40 is forced here.
            output = dict(emerge_cpu=self.run_to({self.code["emerge"]}))
            output["at_emerge"] = self.capture("native-emerge")
            require(output["at_emerge"]["body"]["phase"] == 1 and output["at_emerge"]["body"]["action"] == 7,
                    "Native all-heads-dead output did not execute Emerge")
            watch = self.watch(0x7E0743)
            output["flower_cpu"] = self.run_to({self.code["flower"]})
            output["flower_store_cpu"] = self.run_to({self.code["flower_store"]})
            require(number(output["flower_store_cpu"]["y"]) == 15 and number(output["flower_store_cpu"]["a"]) & 255 == 15,
                    "Native Flower allocator did not reuse freed head slot15")
            output["return_cpu"] = self.run_to({self.code["main_return"]})
            output["after_flower"] = self.capture("native-flower-alias")
            require(output["after_flower"]["offspring"] == [15, 14, 15]
                    and output["after_flower"]["body"]["phase"] == 2
                    and output["after_flower"]["body"]["action"] == 4,
                    "Native producer did not create the actual head/flower cache alias")
            require(self.b.read_memory(0x7E0DD0 + 15) == 9 and self.b.read_memory(0x7E0E20 + 15) == 0x88
                    and self.b.read_memory(0x7E0E30 + 15) == 8, "Reused slot15 is not the live native subtype8 flower")
            output["cache_write_provenance"] = data(self.b.mem_blame(watch_id=watch))
            require(any(number(w["pc"]) == self.code["flower_store"] and number(w["value"]) == 15
                        for w in output["cache_write_provenance"]["writes"]), "Missing native Flower cache writer")
            self.remove_watch(watch)
            self.result["native_flower_producer"] = output
            self.safe_phase, self.safe_action, self.safe_hp = 2, 4, 0x40

    return ManhandlaFixture


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
    require(sha(image) == args.rom_sha256.lower() and hashlib.sha1(image).hexdigest() == args.rom_sha1.lower(),
            "Owned ROM hash differs")
    require(sha(symbols) == args.symbols_sha256.lower(), "Symbols SHA256 differs")
    code = describe(image, symbols.decode(), args.expect)
    portal = load_support(args.support_file)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = fixture_class(portal)(args, bridge, code)
    fixture.result.update(schema="manhandla-phase-death-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=SUPPORT_SHA,
                          claim="House native state08/Intro/Emerge/Flower plus explicit head-death/role/phase/bossHP inputs; routine ABI only, no ordinary D1 route/prize/save acceptance")
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
        heads = fixture.initialize()
        fixture.routine_case(CASE_NAMES[0], 0, 0, 0x80, heads_alive=True)
        fixture.routine_case(CASE_NAMES[1], 0, 0, 0x80, heads_alive=False, clear_heads=heads)
        fixture.flower_producer()
        for name, subtype, phase, hp in ((CASE_NAMES[2], 0, 2, 4), (CASE_NAMES[3], 0, 3, 2),
                                         (CASE_NAMES[4], 1, 2, 2), (CASE_NAMES[5], 8, 2, 2),
                                         (CASE_NAMES[6], 0xA, 2, 2), (CASE_NAMES[7], 0, 2, 3),
                                         (CASE_NAMES[8], 0, 2, 2)):
            require(bridge.read_memory(0x7E0DD0 + 15) == 9 and bridge.read_memory(0x7E0E30 + 15) == 8,
                    "Live flower identity was lost before the alias matrix")
            fixture.routine_case(name, subtype, phase, hp, heads_alive=True, final=name == CASE_NAMES[-1])
        require([c["name"] for c in fixture.result["cases"]] == list(CASE_NAMES)
                and all(c["passed"] for c in fixture.result["cases"]), "Incomplete nine-case matrix")
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
                fixture.result["final"] = fixture.capture("final")
                after_saved = fixture.block(0x7EF000, SIZE)
                fixture.result["saved_wram_deltas"] = saved_wram_deltas(saved_before, after_saved)
                fixture.result["saved_wram_changed_offsets"] = [i for i, (a, b) in enumerate(zip(saved_before, after_saved)) if a != b]
                fixture.result["native_sram_preserved"] = verify_native_sram(
                    sram_before, bytes(bridge.read_block(0, 8192, "SnesSaveRam")))
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
