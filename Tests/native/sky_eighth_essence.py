#!/usr/bin/env python3
"""Sky (D8) eighth-essence award, observed natively from admitted room $0096.

run(active, output_path, case='sky') takes the caller's admitted, paused,
normal-gameplay session (module 07/00, indoors, real room header) and writes
a JSON receipt to output_path. `active` provides .b (MesenBridge),
.step(frames, buttons=''), .session.pause(), optional .snap(label) and
.job/.socket/.pid. The caller owns launch, entrance redirect, identity,
stopping, save/quit and fresh load; verify_reopened() is a read-only check
for that fresh load. Fixture writes (paused, logged, read back): Crystals,
$0403 |= $80 and room tag $AE/$AF. They model the boss-defeat trigger only;
this is not boss completion proof. No CPU/PC/ROM, ancilla, ceremony, HP,
magic or position writes. Stdlib only; --describe works offline.
Native contract: Dungeons/sky_d8_award.asm; usdasm 01C709 (tag 25), 05A51D,
098BC1 (falling prize), 08CA8C (Ancilla29), 08CBF2 (3E), 08F76B (collision).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time

sys.dont_write_bytecode = True

MODULE, INDOORS, AREA, ROOM, DUNGEON = 0x7E0010, 0x7E001B, 0x7E008A, 0x7E00A0, 0x7E040C
CAMERA_X, CAMERA_Y = 0x7E00E2, 0x7E00E8
LINK_Y, LINK_STATE, RECOIL, HOOKSHOT = 0x7E0020, 0x7E005D, 0x7E004D, 0x7E037E
TAGS, ROOM_FLAGS, PRIZE_TIMER = 0x7E00AE, 0x7E0403, 0x7E04C2
ANC_TYPE, ANC_YL, ANC_YH, ANC_XL, ANC_XH, ANC_ITEM = 0x7E0C4A, 0x7E0BFA, 0x7E0C0E, 0x7E0C04, 0x7E0C18, 0x7E0C5E
CRYSTALS, MAP_ICON, FOLLOWER, WORLD, HP = 0x7EF37A, 0x7EF3C7, 0x7EF3CC, 0x7EF3CA, 0x7EF36D
WATCHES = {"crystals": (CRYSTALS, 1, 16), "follower": (FOLLOWER, 8, 64), "map_icon": (MAP_ICON, 1, 16)}
FIXTURE_ADDRESSES = (CRYSTALS, ROOM_FLAGS, TAGS, TAGS + 1)
SKY_ROOM, HEART_TAG, FALLING, RISING, SKY_BIT, PRE_AWARD = 0x0096, 0x25, 0x29, 0x3E, 0x80, 0x7F
STORE_PC, STORE_BYTES, COLLECTOR_HOOK = 0x08CC48, bytes.fromhex("8f7af37e"), 0x08CC3B
COLLISION_CALL = (0x08CB15, bytes.fromhex("a002206bf7"))   # LDY.b #$02 : JSR Ancilla_CheckLinkCollision
COLLISION_TABLES = (0x08F72F, bytes.fromhex(               # offset_y, offset_x, height, width, link_y, link_x
    "00000800080008000000" "00000800080008000000" "1400140008001c000e00"
    "14000300080018000e00" "0c000c000c000c000c00" "0800080008000c000800"))
MAIDEN_FOLLOWER_PCS, PRIZE_CHECKS, FALL_OFFSET = (0x1ECD9D, 0x1ECDA9), 0x02A1A4, 0x78
EXIT_MODE, EXIT_AREA, VICTORY_MODULE, CRYSTAL_SUB = (0x09, 0x00), 0x7A, 0x16, (0x07, 0x18)
STEP, SPAWN_STEPS, WALK_STEPS, STALL_STEPS, SETTLE = 2, 30, 240, 12, 16
CEREMONY_FRAMES, CONTROL_FRAMES, FRAME_BUDGET, DEADLINE_SECONDS = 2400, 60, 3600, 300
CASES = ("sky", "owned", "legacy-owned")


def describe():
    return {
        "fixture": "sky_eighth_essence", "cases": CASES, "native_executed": False,
        "callable": "run(active, output_path, case='sky'); verify_reopened(active, output_path, run()['expected_reopen'])",
        "fixture_writes": {"7EF37A": "sky 7F, owned FF, legacy-owned RoomTagPrizeChecks[040C/2]",
                           "7E0403": "OR 80", "7E00AF/7E00AE": "00 / 25 RoomTag_GetHeartForPrize"},
        "sky": "tag 25 -> ancilla 29 (slot 0-4, camera+78) -> D-pad walk to the ROM-read Ancilla_CheckLinkCollision Y=2 "
               "box -> 3E -> Crystals writes exactly [(08CC48, FF)] -> 07/18 -> 16 -> 09/00 indoors 0 area 7A; "
               "7EF3CC-D3 block and MapIcon unchanged, no 1ECD9D/1ECDA9 maiden write",
        "controls": "owned / legacy-owned: tag deleted, no 29/3E, no Crystals write, room and 07/00 kept",
        "caps": {"walk_frames": WALK_STEPS * STEP, "ceremony_frames": CEREMONY_FRAMES,
                 "frame_budget": FRAME_BUDGET, "deadline_seconds": DEADLINE_SECONDS},
    }


class Failure(RuntimeError):
    pass


def require(ok, message):
    if not ok:
        raise Failure(message)


def number(value):
    require(not isinstance(value, bool), f"Boolean where a number was expected: {value!r}")
    return value if isinstance(value, int) else int(str(value), 0)


def payload(reply, what):
    require(isinstance(reply, dict) and reply.get("success"), f"{what} failed: {reply!r}")
    data = reply.get("data")
    if isinstance(data, str):
        try:
            data = json.loads(data)
        except ValueError as error:
            raise Failure(f"{what} returned unparsable data {data!r}") from error
    require(isinstance(data, dict), f"{what} returned non-object data {data!r}")
    return data


class SkyEighth:
    def __init__(self, active, output_path, case):
        self.active, self.output, self.case = active, Path(output_path), case
        self.deadline, self.frames, self.watches = time.monotonic() + DEADLINE_SECONDS, 0, {}
        self.result = {"fixture": "sky_eighth_essence", "case": case, "passed": False,
                       "session": {k: str(getattr(active, k, None)) for k in ("job", "socket", "pid")},
                       "checks": [], "fixture_writes": [], "modules": [], "path": [], "snaps": [],
                       "review": [], "cleanup_errors": []}

    @property
    def b(self):
        return self.active.b

    def rb(self, address, length):
        data = bytes(self.b.read_block(address, length))
        require(len(data) == length, f"READBLOCK {address:06X}+{length} returned {len(data)} bytes")
        return data

    def r(self, address):
        return self.rb(address, 1)[0]

    def w16(self, address):
        return int.from_bytes(self.rb(address, 2), "little")

    def link(self):
        y = self.rb(LINK_Y, 4)
        return [y[2] | y[3] << 8, y[0] | y[1] << 8]

    def mode(self):
        return list(self.rb(MODULE, 2))

    def types(self):
        return list(self.rb(ANC_TYPE, 10))

    def ancilla(self, i):
        return dict(slot=i, type=self.r(ANC_TYPE + i), item=self.r(ANC_ITEM + i),
                    x=self.r(ANC_XL + i) | self.r(ANC_XH + i) << 8, y=self.r(ANC_YL + i) | self.r(ANC_YH + i) << 8)

    def paused(self):
        state = payload(self.b.send_command("STATE"), "STATE")
        require("paused" in state, "Native pause state is unknown")
        return bool(state["paused"])

    def neutral(self):
        reply = self.b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
        require(isinstance(reply, dict) and reply.get("success"), "Neutral INPUT rejected")

    def check(self, label, actual, expected):
        self.result["checks"].append(dict(name=label, actual=actual, expected=expected, passed=actual == expected))
        require(actual == expected, f"{label}: {actual!r} != {expected!r}")

    def snap(self, label):
        if callable(getattr(self.active, "snap", None)):
            self.result["snaps"].append(dict(label=label, frame=self.frames, data=self.active.snap(label)))

    def step(self, frames, buttons=""):
        require(time.monotonic() < self.deadline, "Fixture deadline exceeded")
        require(self.frames + frames <= FRAME_BUDGET, "Fixture frame budget exceeded")
        self.active.step(frames, buttons)
        self.frames += frames

    def fixture(self, address, value, reason):
        require(address in FIXTURE_ADDRESSES and self.paused(), "Fixture write outside paused contract")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["fixture_writes"].append(entry)
        require(self.b.write_memory(address, value), f"Fixture write {address:06X} rejected")
        entry["readback"] = self.r(address)
        require(entry["readback"] == value, f"Fixture readback {address:06X} differs")

    def watch_add(self, name):
        address, size, depth = WATCHES[name]
        data = payload(self.b.mem_watch_add(address, size=size, depth=depth), f"MEM_WATCH_WRITES add {name}")
        require("watch_id" in data, f"MEM_WATCH_WRITES add has no watch_id: {data!r}")
        self.watches[name] = number(data["watch_id"])
        require(number(data.get("addr", -1)) == address, f"Watch {name} address differs: {data!r}")
        require(number(data.get("depth", -1)) == depth, f"Watch {name} depth differs: {data!r}")

    def blame(self, name):
        address, size, depth = WATCHES[name]
        data = payload(self.b.mem_blame(watch_id=self.watches[name]), f"MEM_BLAME {name}")
        raw = data.get("writes")
        require(isinstance(raw, list), f"MEM_BLAME {name} has no writes list: {data!r}")
        self.result.setdefault("writes", {})[name] = raw
        require(number(data.get("count", len(raw))) == len(raw), f"MEM_BLAME {name} count differs")
        require(len(raw) < depth, f"{name} watch log saturated at depth {depth}")
        writes = []
        for entry in raw:
            require(isinstance(entry, dict), f"Malformed write record {entry!r}")
            write = dict(pc=number(entry["pc"]), addr=number(entry["addr"]), value=number(entry["value"]),
                         cycle=entry.get("cycle"))
            require(address <= write["addr"] < address + size, f"Write outside {name} watch: {entry!r}")
            writes.append(write)
        self.result["writes"][name] = [dict(w, pc=f"{w['pc']:06X}", addr=f"{w['addr']:06X}") for w in writes]
        return writes

    def symbol(self, name):
        path = Path(str(getattr(self.active, "job", ""))) / "candidatex.sym"
        if not path.is_file():
            return None
        found = {int(bank + addr, 16) for bank, addr in re.findall(
            rf"^([0-9A-Fa-f]{{2}}):([0-9A-Fa-f]{{4}})\s+(?:Oracle_)?{name}\s*$", path.read_text(errors="replace"), re.M)}
        require(len(found) <= 1, f"Ambiguous symbol {name}")
        return found.pop() if found else None

    def guard_code(self):
        hook = self.rb(COLLECTOR_HOOK, 4)
        target, symbol = int.from_bytes(hook[1:], "little"), self.symbol("SkyD8_CrystalCollector")
        self.result["code"] = dict(collector_jml=f"{target:06X}",
                                   collector_symbol=None if symbol is None else f"{symbol:06X}")
        self.check("08CC48 retained STA.l 7EF37A", self.rb(STORE_PC, 4).hex(), STORE_BYTES.hex())
        self.check("08CC3B is JML", hook[0], 0x5C)
        if symbol is not None:
            self.check("collector JML matches candidate symbol", target, symbol)
        call_pc, call = COLLISION_CALL
        self.check("Ancilla29 collision call", self.rb(call_pc, len(call)).hex(), call.hex())
        tables = self.rb(COLLISION_TABLES[0], len(COLLISION_TABLES[1]))
        self.check("Ancilla_CheckLinkCollision tables", tables.hex(), COLLISION_TABLES[1].hex())
        return [tables[t * 10 + 4] | tables[t * 10 + 5] << 8 for t in range(6)]

    def admit(self):
        require(self.paused(), "Session must be paused at admission")
        self.neutral()
        base = dict(mode=self.mode(), indoors=self.r(INDOORS), room=self.w16(ROOM), dungeon=self.r(DUNGEON),
                    world=self.r(WORLD), tags=list(self.rb(TAGS, 2)), room_flags=self.r(ROOM_FLAGS),
                    link_state=self.r(LINK_STATE), recoil=self.r(RECOIL), hookshot=self.r(HOOKSHOT), hp=self.r(HP),
                    link=self.link(), crystals=self.r(CRYSTALS), map_icon=self.r(MAP_ICON),
                    follower=list(self.rb(FOLLOWER, 8)), ancillae=self.types())
        self.result["baseline"] = base
        self.check("admitted normal indoor gameplay", [base["mode"], base["indoors"]], [[0x07, 0x00], 1])
        self.check("ordinary Link alive", [base["link_state"], base["recoil"], base["hookshot"], base["hp"] > 0],
                   [0, 0, 0, True])
        self.check("no falling/rising prize", [t for t in base["ancillae"] if t in (FALLING, RISING)], [])
        self.check("0403 bit 40 clear (Ancilla29 terminate)", base["room_flags"] & 0x40, 0)
        return base

    def trigger(self, crystals, reason):
        self.fixture(CRYSTALS, crystals, reason)
        self.fixture(ROOM_FLAGS, self.r(ROOM_FLAGS) | 0x80, "boss heart taken")
        self.fixture(TAGS + 1, 0x00, "second room tag off")
        self.fixture(TAGS, HEART_TAG, "RoomTag_GetHeartForPrize")
        for name in WATCHES:
            self.watch_add(name)

    def sky(self):
        base = self.admit()
        self.check("room word 0096", base["room"], SKY_ROOM)
        oy, ox, height, width, ly, lx = self.guard_code()
        self.trigger(PRE_AWARD, "synthetic pre-award: all seven essences owned (incl. shared D3 bit 40)")
        found = []
        for _ in range(SPAWN_STEPS):
            self.step(STEP)
            found = [i for i, t in enumerate(self.types()[:5]) if t == FALLING]
            if found:
                break
        require(len(found) == 1, f"Expected one native falling prize in slots 0-4, got {found}")
        prize = self.ancilla(found[0])
        camera = [self.w16(CAMERA_X) + FALL_OFFSET, self.w16(CAMERA_Y) + FALL_OFFSET]
        self.result["spawn"] = dict(prize, frame=self.frames, timer=self.r(PRIZE_TIMER), link=self.link(), camera_xy=camera)
        self.check("native spawn deleted heart tag", self.r(TAGS), 0)
        self.check("prize at camera + 78", [prize["x"], prize["y"]], camera)
        self.snap("spawn")
        target, tol, still = [prize["x"] + ox - lx, prize["y"] + oy - ly], min(height, width) // 2 - 1, 0
        self.result["walk"] = dict(target=target, tolerance=tol, collision_box=[height, width])
        for _ in range(WALK_STEPS):
            if self.r(ANC_TYPE + prize["slot"]) != FALLING:
                break
            x, y = self.link()
            dx, dy = target[0] - x, target[1] - y
            button = ("RIGHT" if dx > 0 else "LEFT") if abs(dx) > tol else ("DOWN" if dy > 0 else "UP") if abs(dy) > tol else ""
            self.step(STEP, button)
            still = still + 1 if button and self.link() == [x, y] else 0
            self.result["path"].append([self.frames, x, y, button])
            require(still < STALL_STEPS, f"Route blocked at Link {x:04X},{y:04X} toward {target}; no bypass attempted")
        else:
            raise Failure("Falling prize not collected within the walk cap")
        self.result["collect"] = dict(frame=self.frames, link=self.link(), link_state=self.r(LINK_STATE))
        seen, last, limit = [], None, self.frames + CEREMONY_FRAMES
        while self.frames < limit:
            mode = self.mode()
            if mode != last:
                self.result["modules"].append([self.frames] + mode)
                seen.append(mode)
                last = mode
            if "rising" not in self.result and RISING in self.types():
                self.result["rising"] = dict(self.ancilla(self.types().index(RISING)), frame=self.frames)
                self.snap("receipt")
            if mode == list(EXIT_MODE) and any(m[0] == VICTORY_MODULE for m in seen):
                break
            self.step(STEP)
        else:
            raise Failure(f"No overworld exit within {CEREMONY_FRAMES} frames; modules {self.result['modules']}")
        self.step(SETTLE)
        self.snap("exit")
        self.check("observed rising crystal 3E", "rising" in self.result, True)
        self.check("observed Module07_18", list(CRYSTAL_SUB) in seen, True)
        self.check("exit overworld 09/00 indoors 0 area 7A", [self.mode(), self.r(INDOORS), self.r(AREA)],
                   [list(EXIT_MODE), 0, EXIT_AREA])
        crystals = self.blame("crystals")
        self.check("Crystals writes", [[w["pc"], w["value"]] for w in crystals], [[STORE_PC, PRE_AWARD | SKY_BIT]])
        final = self.r(CRYSTALS)
        self.check("Crystals final FF: low 7 kept, sole 80 added", [final, final & 0x7F, final ^ PRE_AWARD],
                   [PRE_AWARD | SKY_BIT, PRE_AWARD, SKY_BIT])
        follower = self.blame("follower")
        maiden = [w for w in follower if w["addr"] == FOLLOWER and
                  (w["pc"] in MAIDEN_FOLLOWER_PCS or w["value"] != base["follower"][0])]
        self.check("no maiden follower write", maiden, [])
        final_follower = list(self.rb(FOLLOWER, 8))
        self.result["follower_final"] = final_follower
        cache = [w for w in follower if w["addr"] != FOLLOWER]
        if cache:
            self.result["review"].append(dict(what="follower cache 7EF3CD-D3 writes", writes=len(cache)))
        self.check("follower block 7EF3CC-D3 unchanged", final_follower, base["follower"])
        self.check("MapIcon writes", [w["value"] for w in self.blame("map_icon") if w["value"] != base["map_icon"]], [])
        self.check("MapIcon unchanged", self.r(MAP_ICON), base["map_icon"])
        self.result["expected_reopen"] = {f"{CRYSTALS:06X}": PRE_AWARD | SKY_BIT,
                                          f"{FOLLOWER:06X}": base["follower"][0], f"{MAP_ICON:06X}": base["map_icon"]}

    def control(self):
        base = self.admit()
        if self.case == "owned":
            self.check("room word 0096", base["room"], SKY_ROOM)
            crystals = PRE_AWARD | SKY_BIT
        else:
            index = base["dungeon"] >> 1
            self.check("legacy room, valid 040C index, dark world flag",
                       [base["room"] != SKY_ROOM, base["dungeon"] & 1, index <= 0x0C, base["world"] != 0],
                       [True, 0, True, True])
            crystals = self.r(PRIZE_CHECKS + index)
            self.result["prize_mask"] = dict(index=index, mask=crystals)
            require(crystals and not crystals & SKY_BIT, f"RoomTagPrizeChecks[{index:X}]={crystals:02X} is not a low-7 mask")
        self.trigger(crystals, f"{self.case}: prize already owned")
        spawned = set()
        for _ in range(CONTROL_FRAMES // STEP):
            self.step(STEP)
            spawned |= {t for t in self.types() if t in (FALLING, RISING)}
        self.check("tag deleted, no prize, no Crystals write", [self.r(TAGS), sorted(spawned), self.blame("crystals")],
                   [0, [], []])
        self.check("Crystals, room and mode unchanged", [self.r(CRYSTALS), self.w16(ROOM), self.mode()],
                   [crystals, base["room"], [0x07, 0x00]])
        self.snap("control")

    def cleanup(self):
        for name, ident in list(self.watches.items()):
            if name not in self.result.get("writes", {}):
                try:
                    self.blame(name)
                except Exception as error:
                    self.result["cleanup_errors"].append(f"blame {name} {ident}: {error!r}")
            try:
                reply = self.b.mem_watch_remove(ident)
                require(isinstance(reply, dict) and reply.get("success"), f"remove failed: {reply!r}")
                del self.watches[name]
            except Exception as error:
                self.result["cleanup_errors"].append(f"watch {name} {ident}: {error!r}")
        for name, op in (("neutral", self.neutral), ("pause", lambda: self.active.session.pause())):
            try:
                op()
            except Exception as error:
                self.result["cleanup_errors"].append(f"{name}: {error!r}")
        require(self.paused(), "Session not paused after cleanup")

    def finish(self):
        self.result["frames"] = self.frames
        self.result["review_required"] = bool(self.result["review"])
        self.result["passed"] = bool(self.result.get("runtime_checks_passed") and not self.result["cleanup_errors"]
                                     and "error" not in self.result)
        self.output.parent.mkdir(parents=True, exist_ok=True)
        self.output.write_text(json.dumps(self.result, indent=2, default=str) + "\n")
        return json.loads(json.dumps(self.result, default=str))


def run(active, output_path, case="sky"):
    flow = SkyEighth(active, output_path, case)
    try:
        require(case in CASES, f"case must be one of {CASES}")
        flow.sky() if case == "sky" else flow.control()
        flow.result["runtime_checks_passed"] = True
    except Exception as error:
        flow.result["error"] = repr(error)
        try:
            flow.snap("failure")
        except Exception as snap_error:
            flow.result["cleanup_errors"].append(f"failure snap: {snap_error!r}")
    finally:
        try:
            flow.cleanup()
        except Exception as error:
            flow.result["cleanup_errors"].append(repr(error))
    return flow.finish()


def verify_reopened(active, output_path, expected):
    flow = SkyEighth(active, output_path, "reopen")
    try:
        allowed = {f"{a:06X}" for a in (CRYSTALS, FOLLOWER, MAP_ICON)}
        require(isinstance(expected, dict) and set(expected) == allowed, f"expected keys must be exactly {allowed}")
        require(flow.paused(), "Reopened session must be paused")
        flow.check("reopened normal gameplay", flow.mode() in ([0x07, 0x00], list(EXIT_MODE)), True)
        actual = {key: flow.r(int(key, 16)) for key in sorted(expected)}
        flow.result["reopened"] = actual
        flow.check("reopened save values", actual, {key: number(expected[key]) for key in sorted(expected)})
        flow.result["runtime_checks_passed"] = True
    except Exception as error:
        flow.result["error"] = repr(error)
    return flow.finish()


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--describe", action="store_true", help="print the offline contract and exit")
    if not parser.parse_args().describe:
        parser.error("import run(active, output_path, case) from the caller; only --describe runs offline")
    print(json.dumps(describe(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
