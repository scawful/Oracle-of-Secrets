#!/usr/bin/env python3
"""Attach-only physical Sky D8 $90-$91-$92 Somaria lesson route.

The caller owns the heavy lane, launch, the canonical cold House start, the
declared checkpoint/warp setup (see --describe "setup") and process disposal.
It hands over a paused private headless session in room $0090, landed by the
native entrance $29 load. This fixture never launches or stops Mesen, writes
memory, loads or saves states, resets, sets CPU/PC, runs Lua, installs
breakpoints, free-runs, or writes ROM. The body is controller input plus
readback only: every frame is advanced with FRAME after an INPUT change.

Route, in order: menu-equip the owned cane; enter $91 from the west; the closed
shutter blocks Link; Link alone on the plate keeps it closed; a real Y cast puts
a $2C block on the authored plate and opens it; walk east into $92; walk back
west into $91 through the shutter (no trap); cast/split until magic is spent
(each split closes the shutter); lift both pots for +$10 each; re-enter $91
without a POTLIFT reset; leave through the $90 south door and come back in; one
pot again gives +$10.

Movement is bounded by observed room-local targets with frame caps and a
no-progress stall check; it never holds blind through an unknown room.
--describe is source-only; --validate-candidate is offline; --inspect reads one
snapshot; the route needs explicit --execute-fixtures.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_rod_spawn_return as native  # noqa: E402
import somaria_socket_door as door  # noqa: E402

require, number, digest, pc_offset = native.require, native.number, native.digest, native.pc_offset

ENTRY_ROOM, LESSON_ROOM, RECOVERY_ROOM = 0x90, 0x91, 0x92
OUTSIDE_AREA = 0x7A
ENTRANCE = 0x29
ENTRANCE_FIELDS = {"ypos": (0x078E52, bytes.fromhex("d813")),
                   "yscroll": (0x078C52, bytes.fromhex("1013")),
                   "edges": (0x078348, bytes.fromhex("1312131301000101"))}
ENTRANCE_Y = 0x13D8
WARP_CLIENT_ROOM_TABLE = 0x02C813
HEADER_POINTER_PC, HEADER_BANK_PC = 0xB5DD, 0xB5E7
OBJECT_POINTERS_PC = 0x0F8000
POT_POINTERS = 0x01DB69
EXIT_ROOMS, EXIT_COUNT = 0x02DD8A, 0x4F
SOMARIA_COSTS = (0x07B093, bytes.fromhex("080402"))
EXPECTED_TAGS = {ENTRY_ROOM: (0x00, 0x00), LESSON_ROOM: (0x24, 0x00), RECOVERY_ROOM: (0x00, 0x00)}
EXPECTED_DOORS = {ENTRY_ROOM: {(0x83, 0x00)}, LESSON_ROOM: {(0x22, 0x00), (0x83, 0x18)},
                  RECOVERY_ROOM: {(0x22, 0x00)}}
SHUTTER = 0x18
PLATE = (0xFD0, 52, 53)
POTS = ((12, 54, 0x0C), (18, 54, 0x0C))
STAIRS = frozenset({0x138, 0x139})
CHEST = 0xF99

SOMARIA_SELECTION, SOMARIA_Y_ITEM = 0x0F, 0x12
BLOCK, FISSION = 0x2C, 0x2E
BUTTONS = frozenset({"", "Up", "Down", "Left", "Right", "A", "Y", "Start"})
FACING = {"Up": 0, "Down": 2, "Left": 4, "Right": 6}
POTLIFT = 0x7EF580 + LESSON_ROOM * 2
MAGIC_SMALL = 0x10

# Room-local pixels of Link's $22/$20. The recipe's cast waypoint (424,408) is
# Link's centre; the block spawns at Link + (8, 31) facing south ($08:E068), so
# Link (416,400) puts it near (424,431) on the plate at x416-431/y424-439.
DEFAULT_ROUTE = {"cast_x": 416, "cast_y": 400, "corridor_y": 384}
ROUTE_BOUNDS = {"cast_x": (408, 424), "cast_y": (392, 408), "corridor_y": (376, 392)}
PLATE_STAND_Y = 416          # Link's feet (y+16..23) on plate rows 53-54
POT_LINK_X = (144, 96)       # pots (18,54) then (12,54); Link stands above, facing south
WEST_CLEAR_X, EAST_CLEAR_X = 24, 440
CHUNK, FINE, STALL_FRAMES = 4, 6, 24
RUNTIME_SECONDS = 540

PHASES = ("preconditions", "equip-somaria", "enter-91", "closed-shutter-blocks", "link-only-plate",
          "cast-onto-plate", "east-91-to-92", "reverse-92-to-91", "drain-and-split", "zero-magic-pots",
          "room-reentry-keeps-potlift", "exit-and-reenter", "refill-proof")


def route_plan(overrides):
    """Validated waypoints; any override must stay inside the recipe geometry."""
    route = dict(DEFAULT_ROUTE)
    for name, value in overrides.items():
        if value is None:
            continue
        low, high = ROUTE_BOUNDS[name]
        require(low <= value <= high, f"Route override {name}={value} outside {low}..{high}")
        route[name] = value
    return route


def word(data, at):
    return data[at] | data[at + 1] << 8


def decode_object(b1, b2, b3):
    if b1 >= 0xFC:
        return (0x100 + (b3 & 0x3F), ((b1 & 3) << 4) | (b2 >> 4), ((b2 & 0x0F) << 2) | (b3 >> 6))
    if b3 >= 0xF8:
        return (0xF80 | ((b3 & 7) << 4) | ((b2 & 3) << 2) | (b1 & 3), b1 >> 2, b2 >> 2)
    return (b3, b1 >> 2, b2 >> 2)


def object_stream(rom, room):
    """(id, x, y) objects and (b1, type) door words of one room stream."""
    slot = OBJECT_POINTERS_PC + room * 3
    at = pc_offset(int.from_bytes(rom[slot:slot + 3], "little")) + 2
    objects, doors = [], []
    for _ in range(3):
        for _ in range(512):
            require(at + 2 <= len(rom), f"Room {room:02X} object stream overruns ROM")
            if rom[at:at + 2] == b"\xff\xff":
                at += 2
                break
            if rom[at:at + 2] == b"\xf0\xff":
                at += 2
                for _ in range(64):
                    if rom[at:at + 2] == b"\xff\xff":
                        return objects, doors
                    doors.append((rom[at], rom[at + 1]))
                    at += 2
                raise RuntimeError(f"Room {room:02X} door list is unterminated")
            objects.append(decode_object(*rom[at:at + 3]))
            at += 3
        else:
            raise RuntimeError(f"Room {room:02X} object layer is unterminated")
    return objects, doors


def room_header(rom, room):
    table = pc_offset(int.from_bytes(rom[HEADER_POINTER_PC:HEADER_POINTER_PC + 3], "little"))
    at = pc_offset(rom[HEADER_BANK_PC] << 16 | word(rom, table + room * 2))
    return rom[at:at + 14]


def pot_items(rom, room):
    at = pc_offset(0x010000 | word(rom, pc_offset(POT_POINTERS) + room * 2))
    items = []
    for _ in range(32):
        if rom[at:at + 2] == b"\xff\xff":
            return items
        position = word(rom, at)
        items.append(((position % 0x80) // 2, position // 0x80, rom[at + 2]))
        at += 3
    raise RuntimeError(f"Room {room:02X} pot list is unterminated")


def exit_area(rom, room):
    data = rom[pc_offset(EXIT_ROOMS):pc_offset(EXIT_ROOMS) + EXIT_COUNT * 3]
    for index in range(EXIT_COUNT - 1, -1, -1):
        if word(data, index * 2) == room:
            return data[EXIT_COUNT * 2 + index]
    return None


def validate_candidate(rom, symbols):
    """Offline identity of the authored, wired candidate; raises before any runtime access."""
    report = {"tag24": door.validate_candidate(rom, symbols)}
    for room, tags in EXPECTED_TAGS.items():
        header = room_header(rom, room)
        require(tuple(header[5:7]) == tags,
                f"Room {room:02X} header tags {header[5:7].hex()} (need {bytes(tags).hex()})")
        require(header[10:14] == bytes(4), f"Room {room:02X} header keeps stair destinations {header[10:14].hex()}")
        objects, doors = object_stream(rom, room)
        require(not {o[0] for o in objects} & STAIRS, f"Room {room:02X} keeps a bypass stair object")
        require(EXPECTED_DOORS[room] <= set(doors), f"Room {room:02X} doors {doors} lack {EXPECTED_DOORS[room]}")
        shutters = [d for d in doors if d[1] == SHUTTER]
        require(shutters == ([(0x83, SHUTTER)] if room == LESSON_ROOM else []),
                f"Room {room:02X} shutters {shutters} (only the $91 east E8 shutter is admitted)")
        if room == LESSON_ROOM:
            require(objects.count(PLATE) == 1, "Room 91 lacks the one authored plate 0xFD0 at (52,53)")
            for x, y, _ in POTS:
                require(objects.count((0xFAF, x, y)) == 1, f"Room 91 lacks pot object 0xFAF at ({x},{y})")
        if room == RECOVERY_ROOM:
            require(CHEST not in {o[0] for o in objects}, "Room 92 keeps the prototype chest object")
        report[f"room_{room:02X}"] = {"header": header.hex(), "doors": [f"{a:02X}{b:02X}" for a, b in doors],
                                      "objects": len(objects)}
    require(pot_items(rom, LESSON_ROOM) == list(POTS), f"Room 91 pot items {pot_items(rom, LESSON_ROOM)} != {POTS}")
    for name, (at, expected) in ENTRANCE_FIELDS.items():
        require(rom[at:at + len(expected)] == expected,
                f"Entrance $29 {name} is {rom[at:at + len(expected)].hex()} (need {expected.hex()})")
    require(exit_area(rom, ENTRY_ROOM) == OUTSIDE_AREA, "Room 90 no longer exits to overworld area $7A")
    address, costs = SOMARIA_COSTS
    require(rom[pc_offset(address):pc_offset(address) + 3] == costs, "Somaria magic cost table differs")
    report.update(pots=[list(p) for p in POTS], entrance_29={k: v[1].hex() for k, v in ENTRANCE_FIELDS.items()},
                  exit_area=f"{OUTSIDE_AREA:02X}",
                  warp_client_room_02C813=f"{word(rom, pc_offset(WARP_CLIENT_ROOM_TABLE) + ENTRANCE * 2):04X}")
    return report


def state_from(low, anc, save, potlift):
    """Compact readback: low = $7E0000[0x700], anc = $7E0BF0[0x1F0], save = $7EF340[0x90]."""
    room = word(low, 0xA0)
    x, y = word(low, 0x22), word(low, 0x20)
    base_x, base_y = (room & 0x0F) << 9, (room & 0xF0) << 5
    slots = []
    for s in range(5):
        slots.append({"id": anc[0x5A + s], "lx": (anc[0x14 + s] | anc[0x28 + s] << 8) - base_x,
                      "ly": (anc[0x0A + s] | anc[0x1E + s] << 8) - base_y, "delay": low[0x394 + s],
                      "bounce": low[0x3C5 + s], "lifted": low[0x380 + s], "probes": low[0x3DB + s],
                      "z": low[0x29E + s]})
    return {"module": low[0x10], "submodule": low[0x11], "indoors": low[0x1B], "room": room,
            "area": low[0x8A], "x": x, "y": y, "lx": x - base_x, "ly": y - base_y, "dir": low[0x2F],
            "doorway": low[0x6C], "shutter": low[0x468], "sombtn": low[0x646], "switch": low[0x642],
            "carry": low[0x308], "lock": low[0x2E4], "recoil": low[0x4D], "sfx3": low[0x12F],
            "ysel": low[0x202], "yitem": low[0x303], "menu": low[0x200], "somaria": save[0x10],
            "hpmax": save[0x2C], "hp": save[0x2D], "magic": save[0x2E], "refill": save[0x33],
            "usage": save[0x3B], "potlift": potlift[0] | potlift[1] << 8, "slots": slots,
            "sprites": list(anc[0x1E0:0x1F0])}


def block_slot(state):
    found = [i for i, slot in enumerate(state["slots"]) if slot["id"] == BLOCK]
    return found[0] if found else None


def settled_on_plate(state, slot):
    s = state["slots"][slot]
    return (s["id"] == BLOCK and s["delay"] == 0 and s["bounce"] == 0 and s["lifted"] == 0
            and s["probes"] == 4 and s["z"] in (0, 0xFF))


def where(state):
    return (f"module {state['module']:02X}/{state['submodule']:02X} room {state['room']:04X} "
            f"area {state['area']:02X} local ({state['lx']},{state['ly']}) doorway {state['doorway']:02X} "
            f"shutter {state['shutter']} hp {state['hp']}")


def checkpoint_writes():
    """The d8-entrance chain as the existing client resolves it (oldest first, last write wins)."""
    path = Path(__file__).resolve().parents[2] / "Data" / "debug" / "checkpoints.json"
    data = json.loads(path.read_text())
    by_id = {c["id"]: c for c in data["checkpoints"]}
    chain, current = [], by_id["d8-entrance"]
    while current:
        chain.append(current["id"])
        current = by_id.get(current.get("after"))
    chain.reverse()
    final = {}
    for cid in chain:
        for write in by_id[cid].get("writes", []):
            op = next(k for k in ("value", "set_bits", "clear_bits") if k in write)
            final[write["addr"]] = f"{write['name']} {op} {write[op]}"
    return chain, final


def describe(route=None):
    route = route or route_plan({})
    chain, writes = checkpoint_writes()
    client = "env MESEN2_OOS_ROOT=/Users/scawful/src/hobby/mesen2-oos OOS_ROOT=<source> python3 " \
             "<source>/Scripts/Mesen2/mesen2_client.py --socket <private socket>"
    return {
        "claim": "physical Sky D8 $90-$92 Somaria lesson: real cane cast on the authored plate, shutter "
                 "traversal both ways, zero-magic pot refill and its dungeon-exit reset",
        "not_claimed": ["natural overworld access to entrance $29 (setup warps there)",
                        "new-file acceptance (canonical seed is a constructed start)",
                        "death/continue or save/reopen", "Stone echo, statue or ice-block refusals",
                        "offscreen cube persistence", "other D8 rooms, bosses or prizes"],
        "setup": {
            "owner": "root, outside this fixture; every step is a declared fixture, not route proof",
            "steps": [
                "RUN.py lifecycle: heavy lane, owned headless candidate launch, canonical seed "
                "47e7002072330556402324c1b3a7f6dbd2f4490b548f1b9a325072bf2008b150 file 2, controller cold House 0104",
                client + " checkpoint d8-entrance --wram-only --no-warp --json",
                client + " warp-entrance 0x29 --method reload --json   (expect ok, room 0x0090; client re-pauses)",
                "fixture --execute-fixtures (or --inspect / --stop-after for calibration)"],
            "checkpoint_chain": chain,
            "checkpoint_wram_writes": writes,
            "warp_reload_wram_writes": {"0x7EF3CA": "SavedWorld 0x40 (area $7A)", "0x7E0FFF": "0x01",
                                        "0x7E010E": "0x29", "0x7E010F": "0x00", "0x7E010A": "0x01",
                                        "0x7E04AA": "0x00", "0x7E001B": "0x01", "0x7E0011": "0x00",
                                        "0x7E00B0": "0x00", "0x7E0010": "0x05 (Module05 continue-load)"},
            "not_used": ["SpawnPoint $7EF3C8", "prepare_authoring_checkpoint.py", "position/CPU/PC/ROM writes"],
        },
        "body": {"memory_writes": [], "controls": ["INPUT", "FRAME", "READ/read_block", "STATE",
                                                   "screenshot", "pause", "breakpoint list (refuse if any)"],
                 "buttons": sorted(b for b in BUTTONS if b), "chunk_frames": CHUNK, "fine_window_px": FINE,
                 "stall_frames": STALL_FRAMES, "deadline_seconds": RUNTIME_SECONDS},
        "route": route, "route_bounds": ROUTE_BOUNDS, "phases": list(PHASES),
        "waypoints": {"cast_link": [route["cast_x"], route["cast_y"]],
                      "predicted_block": [route["cast_x"] + 8, route["cast_y"] + 31],
                      "plate_px": [416, 424, 431, 439], "plate_stand_y": PLATE_STAND_Y,
                      "pot_link_x": list(POT_LINK_X), "west_clear_x": WEST_CLEAR_X,
                      "east_clear_x": EAST_CLEAR_X, "entrance_y": f"{ENTRANCE_Y:04X}"},
        "reads": {"low": "7E0000+0x700 (10/11/1B/20-23/2F/4D/6C/8A/A0/12F/200/202/029E/2E4/303/308/"
                         "380/394/3C5/3DB/468/642/646)",
                  "ancilla": "7E0BF0+0x1F0 (0BFA/0C04/0C0E/0C18 coords, 0C4A ids, 0DD0 sprites)",
                  "save": "7EF340+0x90 (350 cane, 36C-36E hp/magic, 373 refill, 37B usage)",
                  "potlift": f"{POTLIFT:06X}+2"},
        "pass_requires": [
            "candidate: $91 tag24, $90/$92 tags 0, no stairs, E8 shutter only in $91, plate+pots, "
            "entrance $29 ypos/yscroll/edges, exit $7A, 01CC89 JML 2CFD00 with pinned handler",
            "start in room $0090 at entrance $29 $20=$13D8; cane owned and menu-equipped ($0303=$12)",
            "closed shutter blocks Link; Link on plate leaves $0468 closed and $0646 clear",
            "one Y press: new $2C block, magic -cost, settled with 4 plate probes, $0646 set, $0468=0",
            "walk east into $92; no $2C block remains there",
            "walk west into $91: transition ends, doorway clears, Link reaches x<=440 and keeps moving",
            "each split closes $0468; magic spent to the cost remainder; next Y makes no block",
            "each pot +$10 magic once refill drains; POTLIFT gains one bit per pot",
            "re-entering $91 keeps POTLIFT; leaving via $90 south to area $7A and back clears it",
            "after re-entry one pot gives +$10 again"],
        "native_executed": False,
    }


class LessonRoute(native.Fixture):
    def __init__(self, args, bridge, route):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + RUNTIME_SECONDS
        self.route = route
        self.last = None
        self.entry = None
        self.trace = None
        self.phase = "attach"
        self.log = None
        self.result.update(scope=describe(route)["claim"], route=route, checks=[], observations={},
                           screenshots=[], phases=[], step_count=0)

    def write(self, *_args, **_kwargs):
        raise RuntimeError("The physical lesson body admits no memory writes")

    def check(self, name, ok, detail):
        self.result["checks"].append({"phase": self.phase, "name": name, "passed": bool(ok), "detail": detail})
        require(ok, f"{self.phase}: {name}: {detail}")

    def note(self, name, value):
        self.result["observations"].setdefault(self.phase, {})[name] = value

    def snap(self):
        self.last = state_from(self.block(0x7E0000, 0x700), self.block(0x7E0BF0, 0x1F0),
                               self.block(0x7EF340, 0x90), self.block(POTLIFT, 2))
        return self.last

    def shot(self, name):
        data = self.b.screenshot()
        require(bool(data), "Missing screenshot " + name)
        path = self.a.output / f"{len(self.result['screenshots']):02d}-{name}.png"
        path.write_bytes(data)
        self.result["screenshots"].append({"phase": self.phase, "path": str(path), "sha256": digest(data)})

    def advance(self, buttons, count):
        require(buttons in BUTTONS and 1 <= count <= 8, f"Undeclared controller step {buttons!r} x{count}")
        self.check_owner()
        require(self.paused(), "Controller FRAME requires a paused CPU")
        self.input(buttons)
        before = number(self.b.get_rom_info()["frameCount"])
        require(self.b.send_command("FRAME", {"count": str(count)}).get("success"), "FRAME rejected")
        until = min(self.deadline, time.monotonic() + 5)
        while time.monotonic() < until:
            after = number(self.b.get_rom_info()["frameCount"])
            if after >= before + count and self.paused():
                require(after <= before + count + 1, "FRAME overshoot")
                break
            time.sleep(0.005)
        else:
            raise RuntimeError("Controller FRAME timeout")
        s = self.snap()
        self.result["step_count"] += 1
        if self.trace is not None:
            self.trace.append(s)
        self.log.write(json.dumps({"phase": self.phase, "buttons": buttons, "frames": count, "before": before,
                                   "after": after, **{k: v for k, v in s.items() if k != "sprites"}}) + "\n")
        require(s["hp"] > 0 and s["module"] != 0x12, f"{self.phase}: Link died at {where(s)}")
        require(s["module"] != 0x0E or self.phase == "equip-somaria",
                f"{self.phase}: unexpected text/menu at {where(s)}")
        return s

    def neutral(self, frames):
        for _ in range(frames):
            self.advance("", 1)
        return self.last

    def tap(self, button, hold=2, settle=2):
        self.advance("", 1)
        for _ in range(hold):
            self.advance(button, 1)
        return self.neutral(settle)

    def wait_for(self, name, done, frames):
        for _ in range(frames):
            if done(self.last):
                return self.last
            self.advance("", 1)
        self.check(name, done(self.last), f"not reached in {frames} frames at {where(self.last)}")
        return self.last

    def hold_until(self, button, done, frames, fine=None, blocked_ok=False, every_frame=False):
        """Hold one direction until done(state); refuse frame-cap overruns and stalls."""
        s, spent, still = self.last, 0, 0
        while not done(s):
            require(spent < frames, f"{self.phase}: holding {button} missed target in {frames} frames at {where(s)}")
            step = 1 if every_frame or (fine and fine(s)) else CHUNK
            prev = s
            s = self.advance(button, step)
            spent += step
            key = ("x", "y", "room", "module", "submodule", "indoors")
            busy = (s["submodule"] != 0 or s["module"] not in (0x07, 0x09)
                    or (s["doorway"] != 0 and not blocked_ok))
            still = 0 if busy or any(s[k] != prev[k] for k in key) else still + step
            if still >= STALL_FRAMES:
                if blocked_ok:
                    break
                raise RuntimeError(f"{self.phase}: no progress holding {button} for {still} frames at {where(s)}")
        self.advance("", 1)
        return self.last

    def approach(self, axis, target, tol=1):
        key = "lx" if axis == "x" else "ly"
        plus, minus = ("Right", "Left") if axis == "x" else ("Down", "Up")
        near = lambda s: abs(s[key] - target) <= FINE  # noqa: E731
        for _ in range(4):
            delta = target - self.last[key]
            if abs(delta) <= tol:
                return self.last
            if delta > 0:
                self.hold_until(plus, lambda s: s[key] >= target - tol, 600, fine=near)
            else:
                self.hold_until(minus, lambda s: s[key] <= target + tol, 600, fine=near)
        self.check(f"reach {axis}={target}", abs(self.last[key] - target) <= tol, where(self.last))
        return self.last

    def settle_room(self, room, clear):
        self.check(f"entered room {room:02X}", self.last["room"] == room and self.last["indoors"] == 1,
                   where(self.last))
        return self.wait_for("transition settled", lambda s: s["submodule"] == 0 and s["doorway"] == 0
                             and clear(s), 1)

    def cross(self, button, room, clear, frames=600, every_frame=False):
        done = lambda s: (s["room"] == room and s["submodule"] == 0 and s["doorway"] == 0  # noqa: E731
                          and s["module"] == 0x07 and clear(s))
        self.hold_until(button, done, frames, every_frame=every_frame)
        return self.settle_room(room, clear)

    def face_south_at(self, x, y, tol=1):
        self.approach("y", self.route["corridor_y"], tol=2)
        self.approach("x", x)
        if self.last["ly"] > y - 6:
            self.hold_until("Up", lambda s: s["ly"] <= y - 6, 120)
        self.hold_until("Down", lambda s: s["ly"] >= y - tol, 120, fine=lambda s: s["ly"] >= y - FINE)
        s = self.last
        self.check("Link at waypoint facing south", abs(s["lx"] - x) <= tol and abs(s["ly"] - y) <= tol
                   and s["dir"] == FACING["Down"], where(s) + f" dir {s['dir']}")
        return s

    def begin(self, name):
        self.phase = name
        self.result["phases"].append({"name": name, "start": where(self.last)})

    def end(self, name, stop_after):
        self.result["phases"][-1]["end"] = where(self.last)
        self.result["completed_through"] = name
        return name == stop_after

    # -- phases
    def preconditions(self):
        s = self.snap()
        self.check("start room $0090 normal play", (s["module"], s["submodule"], s["indoors"], s["room"])
                   == (0x07, 0x00, 0x01, ENTRY_ROOM), where(s))
        self.check("native entrance $29 landing y", s["y"] == ENTRANCE_Y, f"$20={s['y']:04X}")
        self.check("no doorway, recoil or lock", (s["doorway"], s["recoil"], s["lock"]) == (0, 0, 0), where(s))
        self.check("cane owned", s["somaria"] == 1, f"$7EF350={s['somaria']:02X}")
        self.check("magic covers a cast", s["magic"] >= self.cost(s), f"magic {s['magic']:02X}")
        self.check("no block before the first cast", block_slot(s) is None, str(s["slots"]))
        self.note("entry", {"lx": s["lx"], "ly": s["ly"], "x": s["x"], "y": s["y"], "magic": s["magic"],
                            "usage": s["usage"], "potlift": s["potlift"], "hp": s["hp"]})
        self.entry = (s["lx"], s["ly"])
        self.shot("start-room90")

    def cost(self, s):
        return SOMARIA_COSTS[1][min(s["usage"], 2)]

    def equip(self):
        if (self.last["ysel"], self.last["yitem"]) == (SOMARIA_SELECTION, SOMARIA_Y_ITEM):
            self.note("already_equipped", True)
            return
        self.tap("Start", settle=4)
        self.wait_for("items menu open", lambda s: s["module"] == 0x0E and s["menu"] == 4, 240)
        for _ in range(24):
            if self.last["ysel"] == SOMARIA_SELECTION:
                break
            self.tap("Right", settle=3)
        self.check("menu cursor on cane cell", self.last["ysel"] == SOMARIA_SELECTION, f"$0202={self.last['ysel']:02X}")
        self.tap("Start", settle=4)
        self.wait_for("menu closed", lambda s: (s["module"], s["submodule"]) == (0x07, 0x00), 240)
        self.check("Y item is the cane", self.last["yitem"] == SOMARIA_Y_ITEM, f"$0303={self.last['yitem']:02X}")

    def enter_lesson(self):
        self.approach("y", self.route["corridor_y"], tol=2)
        self.cross("Right", LESSON_ROOM, lambda s: s["lx"] >= WEST_CLEAR_X)
        self.note("arrival", {"lx": self.last["lx"], "ly": self.last["ly"], "shutter": self.last["shutter"],
                              "sombtn": self.last["sombtn"], "sprites": self.last["sprites"]})

    def closed_shutter_blocks(self):
        self.check("shutter closed before any cast", self.last["shutter"] != 0, where(self.last))
        self.approach("x", self.route["cast_x"])
        self.hold_until("Right", lambda s: s["room"] != LESSON_ROOM, 240, blocked_ok=True)
        s = self.last
        self.check("closed shutter stops Link inside $91", s["room"] == LESSON_ROOM and s["doorway"] == 0
                   and s["shutter"] != 0 and 424 <= s["lx"] <= 472, where(s))
        self.shot("closed-shutter-blocks")

    def link_only_plate(self):
        self.approach("x", self.route["cast_x"])
        self.hold_until("Down", lambda s: s["ly"] >= PLATE_STAND_Y, 120, blocked_ok=True)
        s = self.neutral(60)
        self.check("Link stands on the plate rows", s["ly"] >= PLATE_STAND_Y - 4
                   and abs(s["lx"] - self.route["cast_x"]) <= 1, where(s))
        self.check("Link alone keeps the shutter closed", s["shutter"] != 0 and s["sombtn"] == 0
                   and block_slot(s) is None, where(s) + f" sombtn {s['sombtn']}")
        self.note("plate_stand", {"lx": s["lx"], "ly": s["ly"], "switch_0642": s["switch"]})
        self.shot("link-on-plate")

    def cast(self, label):
        s = self.last
        require(block_slot(s) is None, "A block already exists before a cast")
        magic, cost = s["magic"], self.cost(s)
        seen = {"sfx3": set(), "submodules": set()}

        def track(state):
            seen["sfx3"].add(state["sfx3"])
            seen["submodules"].add(state["submodule"])
        self.tap("Y")
        for _ in range(90):
            track(self.last)
            if block_slot(self.last) is not None:
                break
            self.advance("", 1)
        slot = block_slot(self.last)
        self.check(f"{label}: Y press made a $2C block", slot is not None, str(self.last["slots"]))
        self.check(f"{label}: cast cost", self.last["magic"] == magic - cost, f"{magic:02X}->{self.last['magic']:02X}")
        for _ in range(150):
            track(self.last)
            if settled_on_plate(self.last, slot) and self.last["sombtn"] != 0 and self.last["shutter"] == 0:
                break
            self.advance("", 1)
        block = self.last["slots"][slot]
        self.note(label, {"slot": slot, "block": block, "predicted": [self.route["cast_x"] + 8, self.route["cast_y"] + 31],
                          "link": [self.last["lx"], self.last["ly"]], "sfx3_seen": sorted(seen["sfx3"]),
                          "submodules_seen": sorted(seen["submodules"])})
        self.check(f"{label}: block settled on all four plate probes", settled_on_plate(self.last, slot),
                   f"block {block}; rerun with --stop-after cast-onto-plate and bounded --cast-x/--cast-y")
        self.check(f"{label}: plate opened the shutter", self.last["sombtn"] != 0 and self.last["shutter"] == 0,
                   where(self.last) + f" sombtn {self.last['sombtn']}")
        self.wait_for("door animation done", lambda st: st["submodule"] == 0, 90)
        return slot

    def split(self, label):
        magic = self.last["magic"]
        self.tap("Y")
        self.wait_for(f"{label}: block split", lambda s: block_slot(s) is None, 60)
        self.wait_for(f"{label}: split closes the shutter", lambda s: s["shutter"] != 0, 60)
        self.check(f"{label}: split costs no magic", self.last["magic"] == magic, f"{magic:02X}->{self.last['magic']:02X}")
        self.wait_for(f"{label}: fission and door settled", lambda s: s["submodule"] == 0
                      and all(slot["id"] not in (BLOCK, FISSION) for slot in s["slots"]), 180)

    def east_to_recovery(self):
        self.approach("y", self.route["corridor_y"], tol=2)
        self.cross("Right", RECOVERY_ROOM, lambda s: s["lx"] >= 32)
        self.check("block unloaded in $92", block_slot(self.last) is None, str(self.last["slots"]))
        self.note("arrival", {"lx": self.last["lx"], "ly": self.last["ly"], "sprites": self.last["sprites"],
                              "hp": self.last["hp"]})
        self.shot("room92-after-shutter")

    def reverse_entry(self):
        first = self.result["step_count"]
        self.trace = []
        try:
            self.cross("Left", LESSON_ROOM, lambda s: s["lx"] <= EAST_CLEAR_X, frames=300, every_frame=True)
        finally:
            doorway = [t for t in self.trace if t["room"] == LESSON_ROOM and t["doorway"] != 0]
            self.note("doorway_frames", {"count": len(doorway),
                                         "shutter_values": sorted({t["shutter"] for t in doorway}),
                                         "lx_range": [min((t["lx"] for t in doorway), default=None),
                                                      max((t["lx"] for t in doorway), default=None)]})
            self.trace = None
        s = self.last
        self.check("Link not frozen after reverse entry", (s["lock"], s["recoil"], s["module"]) == (0, 0, 0x07),
                   where(s))
        x = s["lx"]
        self.hold_until("Left", lambda st: st["lx"] <= x - 8, 32)
        self.note("reverse_entry", {"steps": [first, self.result["step_count"]], "lx": self.last["lx"],
                                    "shutter_after": self.last["shutter"], "sombtn_after": self.last["sombtn"]})
        self.shot("reverse-entry-clear")

    def drain(self):
        x, y = self.route["cast_x"], self.route["cast_y"]
        self.face_south_at(x, y)
        cycles = 0
        while self.last["magic"] >= self.cost(self.last):
            require(cycles < 20, "Magic drain exceeded 20 casts")
            self.cast(f"drain-cast-{cycles + 1}")
            self.split(f"drain-split-{cycles + 1}")
            cycles += 1
        magic = self.last["magic"]
        self.tap("Y")
        self.neutral(40)
        self.check("spent cane refuses a cast", block_slot(self.last) is None and self.last["magic"] == magic,
                   f"magic {magic:02X}->{self.last['magic']:02X} slots {self.last['slots']}")
        self.check("magic spent to the cost remainder",
                   magic == self.result["observations"]["preconditions"]["entry"]["magic"] % self.cost(self.last),
                   f"magic {magic:02X}")
        self.note("drain", {"cycles": cycles, "magic": magic})
        self.shot("zero-magic-shutter-closed")

    def lift_pot(self, link_x):
        self.approach("y", self.route["corridor_y"], tol=2)
        self.approach("x", link_x)
        self.hold_until("Down", lambda s: False, 60, blocked_ok=True)
        before = self.last
        self.check("pressed against the pot facing south", before["dir"] == FACING["Down"]
                   and abs(before["lx"] - link_x) <= 1 and 392 <= before["ly"] <= 424, where(before))
        self.tap("A")
        self.wait_for("pot lifted", lambda s: s["carry"] != 0, 30)
        gained = self.last["potlift"] & ~before["potlift"]
        self.check("POTLIFT gained one record bit", gained in (1, 2) and self.last["potlift"] == before["potlift"] | gained,
                   f"{before['potlift']:04X}->{self.last['potlift']:04X}")
        self.neutral(24)
        self.tap("A")
        self.wait_for("pot thrown", lambda s: s["carry"] == 0, 60)
        magic = before["magic"]
        self.hold_until("Down", lambda s: s["magic"] != magic or s["refill"] != 0, 60)
        self.wait_for("magic refill drained", lambda s: s["refill"] == 0, 120)
        stable = self.neutral(4)
        self.check("small magic +$10", stable["magic"] - magic == MAGIC_SMALL,
                   f"{magic:02X}->{stable['magic']:02X}")
        self.result["observations"].setdefault(self.phase, {}).setdefault("pots", []).append(
            {"link_x": link_x, "magic": [magic, stable["magic"]], "potlift": [before["potlift"], stable["potlift"]]})

    def zero_magic_pots(self):
        self.check("POTLIFT clear before pots", self.last["potlift"] & 3 == 0, f"{self.last['potlift']:04X}")
        for link_x in POT_LINK_X:
            self.lift_pot(link_x)
        self.check("both pot records lifted", self.last["potlift"] & 3 == 3, f"{self.last['potlift']:04X}")
        self.shot("after-pots")

    def room_reentry(self):
        potlift = self.last["potlift"]
        self.approach("y", self.route["corridor_y"], tol=2)
        self.cross("Left", ENTRY_ROOM, lambda s: s["lx"] <= EAST_CLEAR_X)
        self.cross("Right", LESSON_ROOM, lambda s: s["lx"] >= WEST_CLEAR_X)
        self.check("room re-entry keeps POTLIFT", self.last["potlift"] == potlift,
                   f"{potlift:04X}->{self.last['potlift']:04X}")
        self.cross("Left", ENTRY_ROOM, lambda s: s["lx"] <= EAST_CLEAR_X)

    def exit_and_reenter(self):
        potlift = self.last["potlift"]
        self.approach("x", self.entry[0], tol=2)
        self.hold_until("Down", lambda s: (s["module"], s["submodule"], s["indoors"]) == (0x09, 0x00, 0x00), 900)
        s = self.last
        self.check("outside on area $7A", s["area"] == OUTSIDE_AREA, where(s))
        self.note("outside", {"x": s["x"], "y": s["y"], "potlift": s["potlift"], "kept_until_entry": s["potlift"] == potlift})
        self.shot("outside-area7A")
        self.hold_until("Up", lambda st: (st["module"], st["submodule"], st["indoors"], st["room"])
                        == (0x07, 0x00, 0x01, ENTRY_ROOM), 900)
        s = self.last
        self.check("dungeon re-entry clears the $91 POTLIFT bits", s["potlift"] & 3 == 0, f"{s['potlift']:04X}")
        self.note("reentry", {"lx": s["lx"], "ly": s["ly"], "y": s["y"], "matches_warp_landing": s["y"] == ENTRANCE_Y})
        self.shot("reentered-room90")

    def refill_proof(self):
        self.enter_lesson()
        self.lift_pot(POT_LINK_X[0])
        self.shot("refill-after-reentry")

    def first_cast(self):
        self.face_south_at(self.route["cast_x"], self.route["cast_y"])
        self.cast("first-cast")
        self.shot("shutter-open-block-on-plate")

    def run(self, stop_after):
        steps = (self.preconditions, self.equip, self.enter_lesson, self.closed_shutter_blocks,
                 self.link_only_plate, self.first_cast, self.east_to_recovery, self.reverse_entry,
                 self.drain, self.zero_magic_pots, self.room_reentry, self.exit_and_reenter,
                 self.refill_proof)
        self.log = (self.a.output / "controller-steps.jsonl").open("x")
        try:
            self.snap()
            for name, step in zip(PHASES, steps):
                self.begin(name)
                step()
                if self.end(name, stop_after):
                    break
            self.result["runtime_checks_passed"] = True
        finally:
            self.log.close()

    def cleanup(self):
        errors = self.result["cleanup_errors"]
        try:
            self.check_owner()
        except BaseException as error:
            errors.append("Ownership check refused cleanup: " + repr(error))
            return
        for step in (lambda: self.input(""), self.b.pause):
            try:
                require(step() is not False, "Owned cleanup action rejected")
            except BaseException as error:
                errors.append(repr(error))


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--describe", action="store_true", help="print the source-only plan and exit")
    parser.add_argument("--validate-candidate", action="store_true",
                        help="offline ROM/symbol identity of the authored, wired candidate; no socket")
    parser.add_argument("--inspect", action="store_true", help="read one snapshot and screenshot; no input")
    parser.add_argument("--execute-fixtures", action="store_true", help="run the controller route")
    parser.add_argument("--stop-after", choices=PHASES, help="calibration: stop after this phase")
    for name in ("cast-x", "cast-y", "corridor-y"):
        parser.add_argument("--" + name, type=int, help="bounded route override, see --describe")
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner"):
        parser.add_argument("--" + name)
    for name in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--pid", type=int)
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    route = route_plan({"cast_x": args.cast_x, "cast_y": args.cast_y, "corridor_y": args.corridor_y})
    if args.describe:
        print(json.dumps(describe(route), indent=2))
        return 0
    if args.validate_candidate:
        require(args.owned_rom and args.symbols, "--validate-candidate needs --owned-rom and --symbols")
        try:
            report = {"candidate_ok": True, **validate_candidate(args.owned_rom.read_bytes(), args.symbols.read_text())}
        except RuntimeError as error:
            report = {"candidate_ok": False, "error": str(error)}
        print(json.dumps(report, indent=2))
        return 0 if report["candidate_ok"] else 2
    require(args.execute_fixtures != args.inspect,
            "Use --describe, --validate-candidate, --inspect or explicitly --execute-fixtures")
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
    args.rom_sha1 = rom_sha1
    code = validate_candidate(rom, symbols.decode())
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    require("--headless" in command and str(args.owned_rom) in command,
            "PID is not the explicit headless private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    route_run = LessonRoute(args, bridge, route)
    route_run.result.update(inputs={k: str(v) for k, v in vars(args).items()}, code=code,
                            source_sha256=digest(Path(__file__).read_bytes()))
    admitted = False
    try:
        route_run.check_owner()
        require(route_run.paused(), "Caller must provide a paused private session")
        require(not bridge.list_breakpoints(), "Existing breakpoints: refuse shared debug session")
        admitted = True
        if args.inspect:
            route_run.result["inspect"] = route_run.snap()
            route_run.shot("inspect")
            route_run.result["runtime_checks_passed"] = True
        else:
            route_run.run(args.stop_after)
    except BaseException as error:
        route_run.result["error"] = repr(error)
        if admitted:
            try:
                route_run.result["failure_state"] = route_run.snap()
                route_run.shot("failure")
            except BaseException as capture_error:
                route_run.result["failure_capture_error"] = repr(capture_error)
    finally:
        if admitted and not args.inspect:
            route_run.cleanup()
        for path, expected, label in ((args.owned_rom, args.rom_sha256, "ROM"),
                                      (args.symbols, args.symbols_sha256, "Symbols")):
            if digest(path.read_bytes()) != expected.lower():
                route_run.result["cleanup_errors"].append(f"{label} file changed")
        ok = bool(route_run.result.get("runtime_checks_passed") and not route_run.result["cleanup_errors"])
        complete = args.execute_fixtures and route_run.result.get("completed_through") == PHASES[-1]
        route_run.result.update(passed=ok and complete, partial_passed=ok and not complete,
                                mode="inspect" if args.inspect else "execute")
        (args.output / "RESULT.json").write_text(json.dumps(route_run.result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": route_run.result["passed"], "partial_passed": route_run.result["partial_passed"],
                      "result": str(args.output / "RESULT.json")}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
