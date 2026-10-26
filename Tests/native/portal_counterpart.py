#!/usr/bin/env python3
"""Attach-only Portal counterpart boundary qualification in cold House0104.

Caller owns launch, cold boot and positive process cleanup. Explicit sprite and
cached-index fixtures exercise native state08 Prep, Long JSR/Main/RTS, twelve
overlaps and (candidate only) four cancelled queued entries. The final case
stops BEFORE the first warp effect (legacy STA or guarded native cache call)
and NEVER resumes. This
qualifies counterpart admission/cancellation, not a completed warp, portal
lifetime, natural placement, route, prize or save. No CPU/register/PC writes,
direct calls, savestates, module, player-health or invulnerability writes.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import sys

sys.dont_write_bytecode = True
UTIL_SHA = "e8491c9f188901dee5e990ff0f44e1c93190253a151022dae1befd091f83f8d4"
SUPPORT_SHA = "bac027161d84ff12cc56a3a987f52545800da173c37044b22a5cae35ded6ce0f"
UTIL_PATH = Path(__file__).with_name("manhandla_phase_death.py")
if hashlib.sha256(UTIL_PATH.read_bytes()).hexdigest() != UTIL_SHA:
    raise RuntimeError("Qualified Manhandla protocol utilities differ")
_spec = importlib.util.spec_from_file_location("portal_counterpart_protocol", UTIL_PATH)
util = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(util)
require, sha, number, raw, symbol, data = util.require, util.sha, util.number, util.raw, util.symbol, util.data
SPRITES, SIZE = 0x7E0B00, 0x500
STATUSES = ("valid", "default-index0", "dead", "reused-type", "wrong-color", "out-of-range")
FIELDS = {"state": 0xDD0, "kind": 0xE20, "subtype": 0xE30, "action": 0xD80,
          "frame": 0xD90, "timer_b": 0xE00, "timer_d": 0xEE0}
SOURCE_TABLES = {0xE20, 0xE30, 0xD80, 0xD90, 0xE00, 0xD00, 0xD10, 0xD20, 0xD30, 0xF20, 0xEE0}
TARGET_TABLES = {0xE20, 0xE30, 0xD00, 0xD10, 0xD20, 0xD30, 0xF20}
PROTECTED = {"player_xy": (0x7E0020, 4), "module": (0x7E0010, 2),
             "movement": (0x7E005D, 1), "camera": (0x7E0600, 24),
             "cached_player_camera": (0x7EC180, 24), "portal_xy": (0x7E06F8, 4),
             "indices": (0x7E0632, 2), "counter": (0x7E06FE, 1), "selector": (0x7E0FA6, 1)}


def allowed_write(address):
    return (0x7E0DD0 <= address < 0x7E0DE0 or address in (0x7E0632, 0x7E0633)
            or address - 0x7E0000 in SOURCE_TABLES
            or address - 0x7E000E in TARGET_TABLES)


def matrix(expect):
    require(expect in ("baseline", "candidate"), "Unknown expected profile")
    result = [(f"{color}-overlap-{status}", "overlap", color, status, None)
              for color in ("blue", "orange") for status in STATUSES]
    if expect == "candidate":
        result += [(f"queued-{color}-{world}-dead", "queued", color, "dead", action)
                   for color, world, action in (("blue", "dungeon", 3), ("orange", "dungeon", 4),
                                               ("blue", "overworld", 5), ("orange", "overworld", 6))]
    result.append(("terminal-blue-dungeon-" + ("dead" if expect == "baseline" else "valid"),
                   "terminal", "blue", "dead" if expect == "baseline" else "valid", 3))
    return result


def expected_action(expect, mode, color, status):
    idle = 1 if color == "blue" else 2
    if mode == "queued":
        return idle
    return (3 if color == "blue" else 4) if expect == "baseline" or status == "valid" else idle


def target_fixture(color, status):
    require(status in STATUSES, "Unknown counterpart fixture")
    opposite = 1 if color == "blue" else 2
    return dict(index=0 if status == "default-index0" else 255 if status == "out-of-range" else 14,
                state=0 if status == "dead" else 9, kind=0xD5 if status == "reused-type" else 3,
                subtype=(2 if color == "blue" else 1) if status == "wrong-color" else opposite)


def describe(image: bytes, text: str, expect: str) -> dict:
    """File-only native dispatch, helper bounds and all four original-effect guards."""
    require(expect in ("baseline", "candidate"), "Unknown expected code profile")
    names = {"long": "Sprite_Portal_Long", "prep": "Sprite_Portal_Prep", "main": "Sprite_Portal_Main",
             "draw": "Sprite_Portal_Draw", "return_pc": "Sprite_Portal_Long_SpriteIsNotActive",
             "blue": "BluePortal", "orange": "OrangePortal"}
    plan = {key: symbol(text, name) for key, name in names.items()}
    wrapper = symbol(text, "Sprite_PrepExp_Long")
    require(raw(image, util.SHIM, 5) == b"\x22" + wrapper.to_bytes(3, "little") + b"\x60",
            "Native Prep JSL/RTS shim differs")
    require(raw(image, 0x06864D, 10) == bytes.fromhex("2218B80DFED00DBD200E")
            and raw(image, 0x06865B + 6, 2) == (util.SHIM & 65535).to_bytes(2, "little")
            and raw(image, symbol(text, "NewSprPrepRoutinesLong") + 9, 3) == plan["prep"].to_bytes(3, "little"),
            "Native state08 dispatch does not select Portal Prep")
    require(raw(image, 0x069283 + 6, 2) == bytes.fromhex("F8FF")
            and raw(image, 0x06FFF8, 5) == bytes.fromhex("2200803060")
            and raw(image, symbol(text, "NewSprRoutinesLong") + 9, 3) == plan["long"].to_bytes(3, "little"),
            "Native state09 dispatch does not select Portal Long")
    long_bytes = (bytes.fromhex("8B4BAB20") + (plan["draw"] & 65535).to_bytes(2, "little")
                  + bytes.fromhex("22008031900320") + (plan["main"] & 65535).to_bytes(2, "little") + bytes.fromhex("AB6B"))
    require(raw(image, plan["long"], len(long_bytes)) == long_bytes
            and plan["return_pc"] == plan["long"] + 15, "Native Long/Main short-call ABI differs")
    prep_bytes = raw(image, plan["prep"], 26)
    require(prep_bytes[:4] == bytes.fromhex("8B4BABA9") and prep_bytes[4] in (0, 0x80)
            and prep_bytes[5:] == bytes.fromhex("9DAA0CBD600F29C09D600F9E6B0BA9FF9DA00BAB6B"),
            "Native Portal Prep must have exact legacy00 or persistent80 properties")
    transport = "Portal_CheckWarpContext" in text
    context = symbol(text, "Portal_CheckWarpContext") if transport else None
    if transport:
        # Exact no-RAM-write guard. P is restored before returned C; X/Y/DB/DP
        # remain untouched. High bytes compare actual Link, not the other sprite.
        guard = bytearray.fromhex("08")
        branches = []
        def branch(op):
            branches.append(len(guard)); guard.extend(bytes([op, 0]))
        for code in ("B9300DC523", "B9200DC521", "B9200FC5EE"):
            guard.extend(bytes.fromhex(code)); branch(0xD0)
        guard.extend(bytes.fromhex("B9200DEBB9000DC22038E5E8C9D100")); branch(0xB0)
        guard.extend(bytes.fromhex("E220B9300DEBB9100DC22038E5E2C9F100")); branch(0xB0)
        guard.extend(bytes.fromhex("283860"))
        invalid = len(guard); guard.extend(bytes.fromhex("281860"))
        for at in branches: guard[at + 1] = invalid - (at + 2)
        require(raw(image, context, len(guard)) == guard, "Exact bounded full-coordinate warp guard differs")
        require(raw(image, plan["draw"], 11) == bytes.fromhex("2216E4069001602264F806"),
                "Portal draw must return on native PrepOamCoord carry before allocation")
    helper = symbol(text, "Portal_CheckCounterpart") if expect == "candidate" else None
    if helper is not None:
        require(raw(image, helper, 50) == bytes.fromhex(
            "BD300EC902F00BC901D025AC3206A9028005AC3306A901C010B015D9300ED010B9200EC903D009B9D00DC909D00238601860"),
            "Counterpart helper identity/bounds/type/state/opposite-color checks differ")
    queued = {}
    for action, name in ((3, "BluePortal_WarpDungeon"), (4, "OrangePortal_WarpDungeon"),
                         (5, "BluePortal_WarpOverworld"), (6, "OrangePortal_WarpOverworld")):
        entry = symbol(text, name)
        idle = 1 if action in (3, 5) else 2
        prefix = b""
        if helper is not None:
            prefix = b"\x20" + (helper & 65535).to_bytes(2, "little") + bytes([0xB0, 6, 0xA9, idle]) + bytes.fromhex("9D800D60")
            require(raw(image, entry, 11) == prefix
                    and symbol(text, name + "_valid_counterpart") == entry + 11,
                    "Queued counterpart guard or idle cancellation differs")
        original = entry + len(prefix)
        if transport:
            require(helper is not None, "Context guard requires identity admission first")
            context_prefix = b"\x20" + (context & 65535).to_bytes(2, "little")
            context_prefix += bytes([0xB0, 6, 0xA9, idle]) + bytes.fromhex("9D800D60")
            require(raw(image, original, len(context_prefix)) == context_prefix
                    and symbol(text, name + "_valid_context") == original + len(context_prefix),
                    "Queued context guard or idle cancellation differs")
            original += len(context_prefix)
            if action < 5:
                effects = bytes.fromhex("2228FF01B9000D8F84C17EB9200D8F85C17EB9100D8F86C17EB9300D8F87C17EA94099E00E64B0A9148511")
            else:
                effects = bytes.fromhex("B9000D8520B9200D8521B9100D8522B9300D8523A94099E00EA901855D")
            effects += bytes([0xA9, idle]) + bytes.fromhex("9D800D60")
            require(raw(image, original, len(effects)) == effects,
                    "Exact full-coordinate/current-context warp effects differ")
            first_effect = original if action < 5 else original + 3
            effect_guard = bytes.fromhex("2228FF01") if action < 5 else bytes.fromhex("8520")
        else:
            load = bytes.fromhex("AF84C17E") if action < 5 else bytes.fromhex("ADFA06" if action == 5 else "ADF806")
            require(raw(image, original, len(load) + 2) == load + bytes.fromhex("8520"),
                    "First original warp effect differs")
            first_effect, effect_guard = original + len(load), bytes.fromhex("8520")
        queued[action] = dict(entry=entry, helper_return=entry + 3 if helper else None,
                              idle_writer=entry + 7 if helper else None, first_effect=first_effect,
                              effect_guard=effect_guard.hex(), context_entry=context,
                              context_return=entry + 14 if transport else None,
                              context_idle_writer=entry + 18 if transport else None)
    dispatch = (bytes.fromhex("BD800D22818700") + b"".join(
        (address & 65535).to_bytes(2, "little") for address in
        (symbol(text, "StateHandler"), plan["blue"], plan["orange"], *(queued[a]["entry"] for a in (3, 4, 5, 6)))))
    require(raw(image, plan["main"], len(dispatch)) == dispatch, "Main action dispatch table differs")
    overlaps = {}
    for color, action, first in (("blue", 3, 0), ("orange", 4, 2)):
        start = plan[color]
        no_overlap = symbol(text, ("BluePortal" if color == "blue" else "OrangePortal") + "_NoOverlap")
        prefix = bytes.fromhex("BD900DC9") + bytes([first]) + bytes.fromhex("B005A9") + bytes([first])
        prefix += bytes.fromhex("9D900DBD000ED015BD900D1A9D900DC9") + bytes([first + 2])
        prefix += bytes.fromhex("9005A9") + bytes([first]) + bytes.fromhex("9D900DA9089D000EA511C92AD002641118BDE00E")
        prefix += bytes([0xD0, no_overlap - (start + len(prefix) + 2)])
        helper_return = None
        if helper is not None:
            prefix += b"\x20" + (helper & 65535).to_bytes(2, "little")
            helper_return = start + len(prefix)
            prefix += bytes([0x90, no_overlap - (start + len(prefix) + 2)])
        suffix = bytes.fromhex("22F7823122EA830622E68306900A18A51BF006A9") + bytes([action])
        suffix += bytes.fromhex("9D800D60A9") + bytes([action + 2]) + bytes.fromhex("9D800D60")
        require(raw(image, start, len(prefix + suffix)) == prefix + suffix, "Overlap animation/timer/guard/hitbox/action bytes differ")
        overlaps[color] = dict(entry=start, helper_return=helper_return, action_writer=no_overlap - 3)
    plan.update(expect=expect, helper=helper, call=plan["long"] + 12, prep_return=wrapper + 7,
                overlaps=overlaps, queued=queued, transport_guard=context, prep_caa=prep_bytes[4],
                case_count=len(matrix(expect)))
    return plan


def fixture_class(portal):
    class CounterpartFixture(util.fixture_class(portal)):
        def __init__(self, args, bridge, code):
            super().__init__(args, bridge, code)
            self.terminal = False

        def run_to(self, addresses):
            require(not self.terminal, "Terminal original-effect stop must never resume")
            return super().run_to(addresses)

        def write(self, address, value, reason):
            require(allowed_write(address), "Forbidden Portal counterpart fixture write: " + hex(address))
            require(0 <= value <= 255 and self.paused(), "Fixture byte write requires paused CPU")
            entry = dict(address=f"{address:06X}", before=self.b.read_memory(address), value=value, reason=reason)
            self.result["writes"].append(entry)
            require(self.b.write_memory(address, value), "Fixture write rejected")
            entry["readback"] = self.b.read_memory(address)
            require(entry["readback"] == value, "Fixture write readback differs")

        def capture(self, name):
            require(self.paused(), "Capture requires settled pause")
            sprites, saved = self.block(SPRITES, SIZE), self.block(0x7EF000, SIZE)
            sram = bytes(self.b.read_block(0, 8192, "SnesSaveRam"))
            require(len(sram) == 8192, "Short native SRAM capture")
            for suffix, blob in (("sprites", sprites), ("saved-wram", saved), ("native-sram", sram)):
                (self.a.output / f"{name}-{suffix}.bin").write_bytes(blob)
            return dict(cpu=self.cpu(), frame=number(self.b.get_rom_info()["frameCount"]),
                        source={k: sprites[t - 0xB00] for k, t in FIELDS.items()},
                        target={k: sprites[t - 0xB00 + 14] for k, t in FIELDS.items()},
                        protected={k: self.block(a, n).hex() for k, (a, n) in PROTECTED.items()},
                        room=self.b.read_memory16(0x7E00A0), hp=self.b.read_memory(0x7EF36D),
                        sprites_sha256=sha(sprites), saved_wram_sha256=sha(saved), native_sram_sha256=sha(sram))

        def reset_idle(self):
            self.write(0x7E0DDE, 0, "deactivate target14 before any later frame; its Main must not change cached indices")
            self.write(0x7E0D80, 1, "restore source idle before any later frame; never execute a queued warp")
            self.write(0x7E0E30, 2, "restore source blue identity before any later frame")
            self.write(0x7E0EE0, 0x40, "suppress overlap between isolated Main boundaries")

        def initialize(self):
            require((self.b.read_memory(0x7E0010), self.b.read_memory(0x7E0011), self.b.read_memory16(0x7E00A0))
                    == (7, 0, 0x104), "Caller must supply paused cold House0104")
            for slot in range(16):
                self.write(0x7E0DD0 + slot, 0, "disable actors before native state08 Portal Prep")
            x, y = self.b.read_memory16(0x7E0022), self.b.read_memory16(0x7E0020)
            for table, value in ((0xE20, 3), (0xE30, 2), (0xD80, 1), (0xD90, 0), (0xE00, 0x40),
                                 (0xEE0, 0x40), (0xD10, x & 255), (0xD30, x >> 8),
                                 (0xD00, y & 255), (0xD20, y >> 8), (0xF20, self.b.read_memory(0x7E00EE))):
                self.write(0x7E0000 + table, value, "source Portal native-Prep role/location/layer fixture on Link")
            self.write(0x7E0DD0, 8, "execute actual native state08 loader and Portal Prep")
            init = dict(shim_cpu=self.run_to({util.SHIM}), prep_cpu=self.run_to({self.code["prep"]}))
            require(number(init["prep_cpu"]["x"]) == 0, "Native Prep selected another slot")
            init["prep_return_cpu"] = self.run_to({self.code["prep_return"]})
            init["snapshot"] = self.capture("native-prep")
            require(init["snapshot"]["source"]["state"] == 9 and init["snapshot"]["source"]["kind"] == 3,
                    "Native state08 did not activate source Portal")
            init["shim_return_cpu"] = self.run_to({util.SHIM_RETURN})
            self.result["native_initialization"] = init

        def case(self, name, mode, color, status, action):
            self.check_owner()
            self.reset_idle()
            caller = self.run_to({self.code["call"]})
            require(number(caller["x"]) == 0 and number(caller["dbr"]) == self.code["long"] >> 16
                    and number(caller["d"]) == 0 and number(caller["p"]) & 0x30 == 0x30,
                    "Actual Portal Long caller X/DBR/DP/MX differs")
            entry = self.run_to({self.code["main"]})
            stack = self.block(0x7E0000 + number(entry["sp"]) + 1, 2)
            require(number(entry["sp"]) == number(caller["sp"]) - 2
                    and stack == ((self.code["return_pc"] - 1) & 65535).to_bytes(2, "little"),
                    "Native Main JSR short return stack differs")
            idle = 1 if color == "blue" else 2
            target = target_fixture(color, status)
            for table, value in ((0xE30, 2 if color == "blue" else 1), (0xD80, action or idle),
                                 (0xD90, 0 if color == "blue" else 2), (0xE00, 0x40), (0xEE0, 0)):
                self.write(0x7E0000 + table, value, "isolated Main role/action and nonanimating overlap input")
            for table, value in ((0xE20, target["kind"]), (0xE30, target["subtype"]), (0xDD0, target["state"])):
                self.write(0x7E000E + table, value, "explicit target14 identity fixture; target cannot run before this Main returns")
            self.write(0x7E0632, target["index"] if color == "orange" else 0, "explicit blue cached index")
            self.write(0x7E0633, target["index"] if color == "blue" else 0, "explicit orange cached index")
            if mode == "terminal" and self.code["transport_guard"] is not None:
                # A valid same-context target is required to reach the first
                # effect, which is now the native cache capture (not a write).
                x, y = self.b.read_memory16(0x7E0022), self.b.read_memory16(0x7E0020)
                for table, value in ((0xD10, x & 255), (0xD30, x >> 8),
                                     (0xD00, y & 255), (0xD20, y >> 8),
                                     (0xF20, self.b.read_memory(0x7E00EE))):
                    self.write(0x7E000E + table, value, "terminal target14 uses actual Link full coordinates/current layer")
            before = self.block(SPRITES, SIZE)
            case = dict(name=name, mode=mode, color=color, status=status, passed=False,
                        caller_cpu=caller, entry_cpu=entry, short_return_stack=stack.hex(),
                        target_fixture=target, input=self.capture(name + "-before"))
            self.result["cases"].append(case)
            require(case["input"]["protected"]["module"] == "0700" and self.b.read_memory(0x7E001B) == 1,
                    "Case must begin in normal indoor context")
            watch = self.watch(0x7E0D80)
            path = self.code["overlaps"][color] if mode == "overlap" else self.code["queued"][action]
            case["handler_cpu"] = self.run_to({path["entry"]})
            if self.code["helper"] is not None:
                case["helper_cpu"] = self.run_to({self.code["helper"]})
                case["helper_return_cpu"] = self.run_to({path["helper_return"]})
                carry = bool(number(case["helper_return_cpu"]["p"]) & 1)
                require(carry == (status == "valid"), "Actual helper carry disagrees with counterpart contract")
            if mode == "terminal":
                case["effect_cpu"] = self.run_to({path["first_effect"]})
                self.terminal = True
                effect_guard = bytes.fromhex(path["effect_guard"])
                require(raw(self.a.owned_rom.read_bytes(), number(case["effect_cpu"]["pc"]), len(effect_guard)) == effect_guard,
                        "Terminal stop is not before the first guarded warp effect")
                case["original_effect_executed"] = False
            else:
                case["return_cpu"] = self.run_to({self.code["return_pc"]})
                returned = case["return_cpu"]
                require(all(number(returned[k]) == number(caller[k]) for k in ("sp", "x", "dbr", "d"))
                        and number(returned["p"]) & 0x30 == number(caller["p"]) & 0x30,
                        "Native Main RTS corrupted SP/X/DBR/DP/MX")
            case["after"] = self.capture(name + "-after")
            after = self.block(SPRITES, SIZE)
            expected = action if mode == "terminal" else expected_action(self.a.expect, mode, color, status)
            require(case["after"]["source"]["action"] == expected, "Native action differs from independent expected admission/cancellation")
            require(case["input"]["protected"] == case["after"]["protected"], "Portal boundary changed player/cache/camera/indices/context")
            changed = [SPRITES + i for i, (a, b) in enumerate(zip(before, after)) if a != b]
            case["changed_sprite_addresses"] = [f"{a:06X}" for a in changed]
            require(all(a == 0x7E0D80 for a in changed), "Main changed another slot or unexpected sprite field")
            case["action_write_provenance"] = data(self.b.mem_blame(watch_id=watch))
            writes = case["action_write_provenance"]["writes"]
            should_write = mode == "queued" or (mode == "overlap" and (self.a.expect == "baseline" or status == "valid"))
            if should_write:
                writer = path["idle_writer"] if mode == "queued" else path["action_writer"]
                require(len(writes) == 1 and number(writes[0]["pc"]) == writer
                        and number(writes[0]["value"]) == expected and number(writes[0]["size"]) == 1,
                        "Missing unique actual native action writer")
            else:
                require(not writes, "Rejected overlap or terminal prefix unexpectedly wrote action")
            self.remove_watch(watch)
            case["passed"] = True
            # No resume follows this reset until the next case's explicit boundary.
            self.reset_idle()
            return case

    return CounterpartFixture


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
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    fixture = fixture_class(portal)(args, bridge, code)
    fixture.result.update(schema="portal-counterpart-boundary-v1", inputs=vars(args), code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()), support_sha256=SUPPORT_SHA,
                          protocol_utilities_sha256=UTIL_SHA,
                          claim="House native Prep/Main fixtures: counterpart overlap/cancel boundary and one terminal prefix; no completed warp/lifetime/route/save acceptance")
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
        for item in matrix(args.expect):
            fixture.case(*item)
        require(fixture.terminal and len(fixture.result["cases"]) == code["case_count"]
                and all(c["passed"] for c in fixture.result["cases"]), "Incomplete terminal-bounded matrix")
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
            for remove, collection in ((fixture.remove, fixture.breakpoints), (fixture.remove_watch, fixture.watches)):
                for ident in list(collection):
                    try:
                        remove(ident)
                    except BaseException as error:
                        fixture.result["cleanup_errors"].append(repr(error))
            try:
                fixture.ensure_paused()
                for slot in range(16):
                    fixture.write(0x7E0DD0 + slot, 0, "paused actor cleanup; caller must dispose process without resuming")
                fixture.result["final"] = fixture.capture("final")
                fixture.result["terminal_stop_no_resume"] = fixture.terminal
                fixture.result["saved_wram_deltas"] = util.saved_wram_deltas(saved_before, fixture.block(0x7EF000, SIZE))
                fixture.result["native_sram_preserved"] = util.verify_native_sram(sram_before, bytes(bridge.read_block(0, 8192, "SnesSaveRam")))
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        for path, pin in ((args.owned_rom, args.rom_sha256), (args.symbols, args.symbols_sha256),
                          (args.support_file, SUPPORT_SHA), (UTIL_PATH, UTIL_SHA)):
            try:
                require(sha(path.read_bytes()) == pin.lower(), "Input changed: " + str(path))
            except BaseException as error:
                fixture.result["cleanup_errors"].append(repr(error))
        fixture.result["passed"] = bool(fixture.result.get("runtime_checks_passed") and fixture.result.get("native_sram_preserved")
                                       and fixture.result.get("terminal_stop_no_resume") and not fixture.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(fixture.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=fixture.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if fixture.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
