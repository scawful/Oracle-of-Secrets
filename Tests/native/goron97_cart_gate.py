#!/usr/bin/env python3
"""Attach-only, input-only qualification of the private $97 cart gate.

Root owns the cold House seed, declared entrance-$27 reload to $98, one
headless process and its disposal. This body never bootstraps, writes memory,
changes CPU state, loads states, installs breakpoints, launches or stops Mesen.
The hashed route file contains room-local walking waypoints, never commands.
Only the complete named lifecycle can PASS; --stop-after is calibration.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import signal
import subprocess
import sys
import time

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parent))
import portal_rod_spawn_return as native  # noqa: E402
import somaria_socket_door as dispatch  # noqa: E402
import sky_somaria_lesson as room_data  # noqa: E402
import cart_shutter_door as legacy  # noqa: E402

require, number, digest = native.require, native.number, native.digest
PHASES = ("preconditions", "98-to-97", "earn-key", "unlock-key-door", "strike-lever",
          "foot-south-denied", "ride-north", "foot-north-denied", "ride-south",
          "foot-south-denied-again", "room-reload", "repeat-north", "finish")
PATHS = ("entry-to-cart", "west-to-key", "key-to-key-door", "key-door-to-lever",
         "lever-to-foot-south", "foot-south-to-west", "north-to-foot-north",
         "foot-north-to-north", "west-to-foot-south", "foot-south-to-lever",
         "lever-to-west", "west-to-lever", "reentry-to-foot-south")
BUTTONS = frozenset({"", "Up", "Down", "Left", "Right", "B"})
ROOM, ENTRY, WEST, NORTH = 0x97, 0x98, (256, 352), (384, 160)
GATE_MASK, KEY_MASK = 0x8080, 0x4000  # lower index0 and automatic upper partner index8
FACE_INDEXES = (5, 6, 9, 10, 21, 22, 25, 26)


def face_values(cells):
    require(len(cells) == 32, "Missing paired shutter collision sample")
    return tuple(cells[i] for i in FACE_INDEXES)


def closed_faces(state):
    return (state["shutter"] == 1 and not state["door_open_bits"] & GATE_MASK
            and face_values(state["cells"]) == (0xF8,) * 4 + (0xF0,) * 4)


def open_faces(state):
    return (state["shutter"] == 0 and state["door_open_bits"] & GATE_MASK == GATE_MASK
            and face_values(state["cells"]) == (0x82,) * 8)


def word(data, offset):
    return int.from_bytes(data[offset:offset + 2], "little")


def load_route(path):
    r = json.loads(path.read_text())
    require(r.get("schema") == "goron97-controller-route-v1", "Wrong waypoint schema")
    require(set(r["paths"]) == set(PATHS), "Missing or extra named walking path")
    for name, points in r["paths"].items():
        require(isinstance(points, list) and 1 <= len(points) <= 24, "Invalid path " + name)
        for point in points:
            require(isinstance(point, list) and len(point) == 2
                    and all(type(v) is int and 8 <= v <= 496 for v in point), "Invalid waypoint " + name)
    require(r["key-door-direction"] == "Up", "Only the authored North key door is admitted")
    require(r["lever-facing"] in ("Up", "Down", "Left", "Right"), "Invalid lever facing")
    require(type(r["key-door-end-y"]) is int and 176 <= r["key-door-end-y"] <= 208,
            "Invalid key-door crossing target")
    return r


def validate_drag_calls(rom, symbols, wrapper):
    calls = []
    expected = b"\x22" + wrapper.to_bytes(3, "little")
    for direction, owner, following in (("North", "Minecart_MoveNorth", "Minecart_MoveEast"),
                                         ("South", "Minecart_MoveSouth", "Minecart_MoveWest")):
        name = "CartShutter97_Drag" + direction + "Call"
        start = dispatch.symbol(symbols, name)
        end = dispatch.symbol(symbols, name + "_End")
        lo, hi = dispatch.symbol(symbols, owner), dispatch.symbol(symbols, following)
        require(lo >> 16 == hi >> 16 == 0x31 and lo <= start < end <= hi and end - start == 4,
                "Invalid vertical drag callsite " + name)
        at = native.pc_offset(start)
        require(rom[at:at + 4] == expected, "Vertical drag JSL target mismatch " + name)
        calls.append({"name": name, "start": f"{start:06X}", "end": f"{end:06X}",
                      "target": f"{wrapper:06X}"})
    return calls


def validate_candidate(rom, symbols, expected_code, legacy_control=False):
    spans, body = [], bytearray()
    for name in ("RoomTag_CartShutterDispatch", "RoomTag_CartShutter97", "CartShutter97_DragPlayer"):
        start = dispatch.symbol(symbols, name)
        end = dispatch.symbol(symbols, name + "_End")
        require(start >> 16 == end >> 16 and 0 < end - start <= 0x600, "Invalid handler span " + name)
        at = native.pc_offset(start)
        raw = rom[at:at + end - start]
        require(len(raw) == end - start, "Short handler " + name)
        body.extend(raw)
        spans.append({"name": name, "start": f"{start:06X}", "end": f"{end:06X}", "sha256": digest(raw)})
    target = (dispatch.symbol(symbols, "RoomTag_ShutterDoorRequiresCart") if legacy_control
              else int(spans[0]["start"], 16))
    at = native.pc_offset(0x01CC14)
    require(rom[at:at + 4] == b"\x5c" + target.to_bytes(3, "little"), "Tag37 JML target mismatch")
    require(rom[native.pc_offset(0x01C2EB):native.pc_offset(0x01C2EB) + 2] == b"\x14\xcc",
            "Tag37 dispatch vector mismatch")
    require(digest(body) == expected_code.lower(), "Compiled dispatch/local-handler/drag SHA256 mismatch")
    wrapper, wrapper_end = int(spans[2]["start"], 16), int(spans[2]["end"], 16)
    require(wrapper == 0x2CFA00 and wrapper < wrapper_end <= 0x2CFB00,
            "Cart drag wrapper escaped its source-owned page")
    drag_calls = validate_drag_calls(rom, symbols, wrapper)
    at = native.pc_offset(0x0289F3)
    transition = rom[at:at + 5]
    try:
        bridge = dispatch.symbol(symbols, "CartShutter97_TransitionHold")
    except RuntimeError:
        require(legacy_control and transition == bytes.fromhex("ad6804d00d"),
                "Candidate is missing the intraroom close guard")
    else:
        start, end = int(spans[1]["start"], 16), int(spans[1]["end"], 16)
        require(start <= bridge < end and transition == b"\x5c" + bridge.to_bytes(3, "little") + b"\xea",
                "Intraroom close hook differs from the hashed bridge")
    if legacy_control:
        at = native.pc_offset(target)
        require(rom[at:at + len(legacy.HANDLER_BYTES)] == legacy.HANDLER_BYTES,
                "Legacy control requires the qualified41-byte opener")
    header = room_data.room_header(rom, ROOM)
    require(tuple(header[5:7]) == (0x37, 0), "Room97 requires tag37,00")
    _, doors = room_data.object_stream(rom, ROOM)
    require(doors[:2] == [(0x80, 0x18), (0x60, 0x1C)], "Room97 gate0/key1 contract differs")
    require([d for d in doors if d[1] in (0x18, 0x44)] == [(0x80, 0x18)],
            "Room97 must have exactly the one local shutter")
    require(word(rom, 0x78000 + 0x27 * 2) == ENTRY, "Expanded entrance27 does not lead to98")
    return {"handlers": spans, "compiled_code_sha256": digest(body), "doors": doors,
            "hook_target": f"{target:06X}", "legacy_control": legacy_control,
            "transition_hook": transition.hex(), "drag_calls": drag_calls}


class Route(native.Fixture):
    def __init__(self, args, bridge, route):
        super().__init__(args, bridge)
        self.deadline = time.monotonic() + 600
        self.route, self.last, self.phase, self.log = route, None, "attach", None
        self.closed_cells = None
        self.animation_frames = 0
        self.frame_count, self.last_advance = None, 0
        self.owned_cart, self.seam = None, None
        self.result.update(checks=[], phases=[], screenshots=[], mode="input-only", memory_writes=[],
                           bootstrap="caller-owned canonical seed and native entrance27 reload to98")
        if args.legacy_control:
            self.result.update(mode="legacy-control", claim="legacy opener opens remoteP on initial T0 ride; not new-gate acceptance")

    def write(self, *_args, **_kwargs):
        raise RuntimeError("The Goron97 controller body admits no memory writes")

    def snap(self):
        low = self.block(0x7E0000, 0x800)
        actors = self.block(0x7E0D00, 0x240)
        save = self.block(0x7EF340, 0x40)
        door_types = self.block(0x7E1980, 0x20)
        room = word(low, 0xA0)
        bx, by = (room & 15) * 512, (room >> 4) * 512
        sprites = []
        for i in range(16):
            sprites.append({"slot": i, "state": actors[0xD0 + i], "kind": actors[0x120 + i],
                            "subtype": actors[0x130 + i], "action": actors[0x80 + i],
                            "direction": actors[0xB0 + i], "timer": actors[0xF0 + i],
                            "floor": actors[0x220 + i],
                            "x": (actors[0x10 + i] | actors[0x30 + i] << 8) - bx,
                            "y": (actors[i] | actors[0x20 + i] << 8) - by})
        cells = []
        if room == ROOM:
            # Internal North doors have an upper paired face as well as the
            # lower aperture. Observe both across the vanilla camera gap.
            data = self.block(0x7F2000 + 26 * 64 + 46, 13 * 64 + 4)
            cells = [data[(row - 26) * 64 + x] for row in (26, 27, 28, 29, 36, 37, 38, 39)
                     for x in range(4)]
        self.last = {"module": low[0x10], "submodule": low[0x11], "indoors": low[0x1B], "room": room,
                     "x": word(low, 0x22), "y": word(low, 0x20), "lx": word(low, 0x22) - bx,
                     "ly": word(low, 0x20) - by, "layer": low[0xEE], "mounted": low[0x35],
                     "shutter": word(low, 0x468), "door_open_bits": word(low, 0x68C),
                     "key_open_bits": word(low, 0x400), "timer": word(low, 0x690), "switch": low[0x231],
                     "doorway": low[0x6C], "control_lock": low[0x2E4], "movement": low[0x5D],
                     "keys": save[0x2F], "sword": save[0x19], "hp": save[0x2D],
                     "track": low[0x7E8], "cart_slot": word(low, 0x7EA),
                     "parked_room": word(low, 0x728), "parked_x": word(low, 0x768),
                     "parked_y": word(low, 0x7A8), "cells": cells, "sprites": sprites}
        self.last.update(door_type0=word(door_types, 0), door_type8=word(door_types, 16))
        return self.last

    def check(self, name, ok, detail=None):
        self.result["checks"].append({"phase": self.phase, "name": name, "passed": bool(ok), "detail": detail})
        require(ok, f"{self.phase}: {name}: {detail or self.last}")

    def shot(self, name):
        data = self.b.screenshot()
        require(bool(data), "Missing screenshot " + name)
        path = self.a.output / (name + ".png")
        path.write_bytes(data)
        self.result["screenshots"].append({"path": str(path), "sha256": digest(data)})

    @staticmethod
    def live_cart(state):
        return next((a for a in state["sprites"] if a["slot"] == state["cart_slot"]
                     and a["state"] == 9 and a["kind"] == 0xA3
                     and a["subtype"] == 0 and a["floor"] == 0), None)

    def validate_cart(self, previous, state):
        """Admit only the observed rail-seam follower reconstruction window."""
        if not state["mounted"]:
            require(self.seam is None, "Ride ended before seam cart reconstruction")
            return None
        require(state["track"] == 0, "Mounted ride changed track")
        if previous["room"] != state["room"]:
            require(self.seam is None and previous["mounted"] and self.owned_cart
                    and self.owned_cart[0] == previous["room"], "Unadmitted mounted room change")
            west = previous["room"] == ENTRY and state["room"] == ROOM
            east = previous["room"] == ROOM and state["room"] == ENTRY
            require((west and previous["lx"] <= 48 and state["lx"] >= 448)
                    or (east and previous["lx"] >= 464 and state["lx"] <= 64), "Ride left the rail seam")
            require(368 <= state["ly"] <= 400, "Wrong rail-seam row")
            self.seam = {"from": previous["room"], "to": state["room"], "old_slot": self.owned_cart[1],
                         "start_frame": self.frame_count, "normal_frame": None}
        cart = self.live_cart(state)
        if self.seam is not None:
            require(state["room"] == self.seam["to"] and 368 <= state["ly"] <= 400
                    and (state["lx"] >= 448 if state["room"] == ROOM else state["lx"] <= 64),
                    "Seam grace reached the room interior or gate")
            require(self.frame_count - self.seam["start_frame"] <= 192, "Seam reconstruction exceeded192 frames")
            reconstructed = (cart is not None and state["submodule"] == 0
                             and 0 <= cart["x"] < 512 and 0 <= cart["y"] < 512
                             and abs(cart["x"] - state["lx"]) <= 16
                             and abs(cart["y"] - state["ly"]) <= 24)
            if not reconstructed:
                require(state["submodule"] in (0, 1, 2, 5), "Unexpected seam submodule")
                if state["submodule"] == 0:
                    if self.seam["normal_frame"] is None:
                        self.seam["normal_frame"] = self.frame_count
                    require(self.frame_count - self.seam["normal_frame"] <= 4,
                            "Cart did not reconstruct at normal cadence")
                return None
            self.result.setdefault("seam_reconstructions", []).append({**self.seam,
                "new_slot": cart["slot"], "end_frame": self.frame_count, "state": state})
            self.owned_cart, self.seam = (state["room"], cart["slot"]), None
        require(cart is not None and self.owned_cart == (state["room"], state["cart_slot"]),
                "Mounted state lost the owned T0 slot inside the room")
        return cart

    def chunk(self):
        s = self.last
        if s["submodule"] in (1, 5):
            return 1
        if self.seam is not None:
            return 4 if s["submodule"] == 2 else 1
        if s["mounted"] and s["room"] == ROOM:
            cart = self.live_cart(s)
            if cart is None or (328 <= cart["x"] <= 440 and 152 <= cart["y"] <= 368):
                return 1
        return 4

    def advance(self, button="", frames=1):
        require(button in BUTTONS and type(frames) is int and 1 <= frames <= 4, "Invalid controller step")
        info = self.check_owner()
        require(self.paused(), "FRAME requires paused owned CPU")
        self.input(button)
        before = number(info["frameCount"])
        previous = self.last
        try:
            require(self.b.send_command("FRAME", {"count": str(frames)}).get("success"), "FRAME rejected")
            until = min(self.deadline, time.monotonic() + 5)
            while time.monotonic() < until:
                after = number(self.b.get_rom_info()["frameCount"])
                if after >= before + frames and self.paused():
                    require(after <= before + frames + 1, "FRAME overshoot")
                    break
                time.sleep(0.005)
            else:
                raise RuntimeError("FRAME timeout")
        finally:
            self.input("")
        self.frame_count, self.last_advance = after, after - before
        s = self.snap()
        self.log.write(json.dumps({"phase": self.phase, "button": button, "frames": frames,
                                   "frame_before": before, "frame_after": after, **s}) + "\n")
        require(s["hp"] > 0 and s["module"] == 7, "Death or unexpected module")
        self.animation_frames = self.animation_frames + self.last_advance if s["submodule"] == 5 else 0
        require(self.animation_frames <= 32, "Shutter animation did not return control")
        cart = self.validate_cart(previous, s)
        if s["room"] == ROOM and s["mounted"]:
            if cart and (192 <= cart["y"] <= 240 or 284 <= cart["y"] <= 324):
                require(s["shutter"] == 0, "Cart entered the aperture while shutter was closed")
                if s["submodule"] != 5:
                    require(open_faces(s), "Cart entered before all eight shutter face cells opened")
        return s

    def neutral(self, frames):
        spent = 0
        while spent < frames:
            self.advance(frames=min(self.chunk(), frames - spent))
            spent += self.last_advance

    def tap(self, button, settle=2):
        self.advance()
        self.advance(button)
        self.neutral(settle)

    def until(self, predicate, frames, button=""):
        spent = 0
        while spent < frames:
            if predicate(self.last):
                return
            self.advance(button)
            spent += self.last_advance
        self.check("bounded target", predicate(self.last), f"missed after {frames} frames")

    def axis(self, key, target):
        plus, minus = ("Right", "Left") if key == "lx" else ("Down", "Up")
        still, spent = 0, 0
        while spent < 600:
            value = self.last[key]
            if abs(value - target) <= 2:
                return
            step = min(self.chunk() if abs(value - target) > 10 else 1, 600 - spent)
            self.advance(plus if value < target else minus, step)
            spent += self.last_advance
            still = still + self.last_advance if self.last[key] == value and self.last["submodule"] == 0 else 0
            require(still < 24, f"Walking stalled at {key}={value}, target {target}")
        raise RuntimeError("Walking frame bound exceeded")

    def walk(self, name):
        require(not self.last["mounted"], "Walking path requires unmounted Link")
        room = self.last["room"]
        for x, y in self.route["paths"][name]:
            self.axis("lx", x)
            self.axis("ly", y)
            require(self.last["room"] == room, "Walking path unexpectedly changed rooms")

    def board(self):
        carts = [a for a in self.last["sprites"] if a["state"] == 9 and a["kind"] == 0xA3
                 and a["subtype"] == 0 and a["floor"] == 0]
        self.check("one parked T0", len(carts) == 1, carts)
        cart = carts[0]
        self.check("natural board overlap", abs(cart["x"] - self.last["lx"]) <= 8
                   and abs(cart["y"] - self.last["ly"]) <= 17)
        self.neutral(64)
        self.check("unmounted before B", self.last["mounted"] == 0)
        self.owned_cart = (self.last["room"], cart["slot"])
        self.tap("B", 0)
        self.until(lambda s: s["mounted"] == 1 and s["track"] == 0, 16)
        self.check("B sets riding flag naturally", self.last["mounted"] == 1 and self.last["track"] == 0)
        self.check("B boards the observed T0 slot", self.last["cart_slot"] == cart["slot"])

    def stopped(self, point, room=ROOM):
        bx, by = (room & 15) * 512, (room >> 4) * 512
        return (self.last["room"] == room and self.last["mounted"] == 0
                and self.last["parked_room"] == room
                and (self.last["parked_x"] - bx, self.last["parked_y"] - by) == point
                and self.last["submodule"] == 0)

    def ride(self, destination, prove_gate=True, room=ROOM, expect_closed=True):
        seen = {"animation": False, "open": False, "collision_open": False, "crossed": False}
        first, intraroom = {}, []
        spent = 0
        while spent < 1600:
            s = self.last
            if self.stopped(destination, room):
                break
            if s["room"] == ROOM:
                seen["animation"] |= s["submodule"] == 5
                seen["open"] |= s["shutter"] == 0 and s["door_open_bits"] & GATE_MASK == GATE_MASK
                seen["collision_open"] |= bool(self.closed_cells and s["submodule"] == 0 and open_faces(s))
                cart = self.live_cart(s)
                seen["crossed"] |= bool(cart and s["mounted"] and
                                         (192 <= cart["y"] <= 240 or 284 <= cart["y"] <= 324))
                for event, happened in seen.items():
                    if happened:
                        first.setdefault(event, self.frame_count)
                if s["submodule"] == 1:
                    intraroom.append({"frame": self.frame_count, "state": s})
                    if s["mounted"] and (176 <= s["ly"] <= 344
                                         or cart and 176 <= cart["y"] <= 344):
                        self.check("intraroom passage keeps gate open", s["shutter"] == 0)
                if (self.a.legacy_control and s["submodule"] != 5 and s["shutter"] == 0
                        and s["door_open_bits"] & GATE_MASK == GATE_MASK and s["keys"] == 0
                        and s["switch"] == 0 and not s["key_open_bits"] & KEY_MASK
                        and not (336 <= s["lx"] <= 432 and 176 <= s["ly"] <= 344)):
                    self.result.setdefault("legacy_remote_open", {"frame": self.frame_count, "state": s,
                                                                   "seam_pending": self.seam})
            self.advance(frames=min(self.chunk(), 1600 - spent))
            spent += self.last_advance
        self.check("natural destination stop/dismount", self.stopped(destination, room), {"room": room, "point": destination})
        if prove_gate:
            for name, value in seen.items():
                self.check("gate " + name, value)
            self.check("collision opens before aperture crossing", first["collision_open"] < first["crossed"], first)
            self.result.setdefault("gate_rides", []).append({"phase": self.phase, "first_events": first,
                                                             "intraroom": intraroom})
        if room == ROOM and expect_closed:
            self.until(lambda s: s["shutter"] == 1 and s["submodule"] == 0, 90)
            if self.closed_cells:
                self.check("closed shutter faces restored", closed_faces(self.last)
                           and face_values(self.last["cells"]) == face_values(self.closed_cells))
            self.check("closed gate bit", not self.last["door_open_bits"] & GATE_MASK)

    def foot_denied(self, side):
        self.until(lambda s: s["submodule"] == 0 and s["shutter"] == 1
                   and not s["door_open_bits"] & GATE_MASK, 90)
        self.check("unmounted closed gate", self.last["mounted"] == 0 and closed_faces(self.last))
        before = self.last["ly"]
        self.check("foot probe aligned with gate", self.last["room"] == ROOM and self.last["layer"] == 0
                   and abs(self.last["lx"] - 376) <= 2)
        self.check("foot approach starts beside gate", 312 <= before <= 352 if side == "south"
                   else 176 <= before <= 208)
        direction = "Up" if side == "south" else "Down"
        positions = []
        spent = 0
        while spent < 48:
            self.advance(direction)
            spent += self.last_advance
            positions.append(self.last["ly"])
            self.check("foot does not open gate", self.last["mounted"] == 0 and closed_faces(self.last))
        self.check("foot attempt stays on initial side", min(positions) >= 296 if side == "south"
                   else max(positions) < 216, {"initial_y": before, "ys": positions})
        self.check("foot collision stalls", max(positions[-12:]) - min(positions[-12:]) <= 1)
        self.check("stall is at the gate", 296 <= positions[-1] <= 320 if side == "south"
                   else 192 <= positions[-1] <= 208, positions[-1])
        self.check("foot shutter faces unchanged", closed_faces(self.last)
                   and face_values(self.last["cells"]) == face_values(self.closed_cells))

    def preconditions(self):
        s = self.last
        self.check("entrance27 starts98", (s["module"], s["submodule"], s["room"], s["layer"])
                   == (7, 0, ENTRY, 0))
        self.check("initial earned-key invariant", s["keys"] == 0)
        self.check("sword available", s["sword"] in (1, 2, 3, 4))
        self.check("T0 remains original98", s["parked_room"] == ENTRY
                   and (s["parked_x"], s["parked_y"]) == (0x1190, 0x1380))

    def enter97(self):
        self.walk("entry-to-cart")
        self.board()
        self.ride(WEST, prove_gate=False, expect_closed=not self.a.legacy_control)
        self.closed_cells = list(self.last["cells"])
        if not self.a.legacy_control:
            self.check("initial closed shutter face types", closed_faces(self.last))
        self.check("initial lever off", self.last["switch"] == 0)
        self.check("initial key door locked", not self.last["key_open_bits"] & KEY_MASK)
        self.check("runtime paired doors belong to shutter animator", self.last["door_type0"] & 0xFF in (0x18, 0x44)
                   and self.last["door_type8"] & 0xFF in (0x18, 0x44),
                   [self.last["door_type0"], self.last["door_type8"]])

    def legacy_remote_open(self):
        if self.stopped(WEST) and self.last["shutter"] == 0 and self.last["door_open_bits"] & GATE_MASK == GATE_MASK:
            self.result.setdefault("legacy_remote_open", {"frame": self.frame_count, "state": self.last,
                                                           "seam_pending": self.seam})
        self.check("legacy opens remoteP at entry or W", self.stopped(WEST) and self.seam is None
                   and bool(self.result.get("legacy_remote_open")))
        self.check("legacy opener bypasses key/selector task", self.last["keys"] == 0
                   and self.last["switch"] == 0 and not self.last["key_open_bits"] & KEY_MASK)
        self.check("W is outside local hold", self.last["lx"] < 336 and self.last["mounted"] == 0)

    def earn_key(self):
        self.walk("west-to-key")
        self.check("key initially unearned", self.last["keys"] == 0)
        for _ in range(24):
            if self.last["keys"] == 1:
                break
            self.tap("B", 18)
            self.neutral(4)
        self.check("actual enemy key collected", self.last["keys"] == 1)

    def unlock_key(self):
        self.walk("key-to-key-door")
        self.check("one key before K", self.last["keys"] == 1)
        self.until(lambda s: bool(s["key_open_bits"] & KEY_MASK) and s["keys"] == 0,
                   180, self.route["key-door-direction"])
        self.axis("ly", self.route["key-door-end-y"])
        self.check("one key spent at K", self.last["keys"] == 0 and self.last["key_open_bits"] & KEY_MASK)

    def strike_lever(self, path="key-door-to-lever", before=0):
        self.walk(path)
        self.advance(self.route["lever-facing"])
        self.check("selector before strike", self.last["switch"] == before)
        self.tap("B", 24)
        self.check("sword switches group1", self.last["switch"] == 1 - before)

    def reload(self):
        # The ordinary East walking door is sealed. OFF sends T0 from W
        # through J/C and the existing rail seam to98; no walking exit claim.
        self.strike_lever("foot-south-to-lever", before=1)
        self.walk("lever-to-west")
        self.board()
        self.ride((400, 384), prove_gate=False, room=ENTRY)
        self.board()
        self.ride(WEST, prove_gate=False)
        self.check("reload closes gate", self.last["shutter"] == 1)
        self.check("reload retains earned key door", self.last["key_open_bits"] & KEY_MASK)
        self.check("reload retains OFF selector", self.last["switch"] == 0)
        self.check("reload retains W cart", self.stopped(WEST))
        self.strike_lever("west-to-lever", before=0)

    def run(self, stop_after):
        def foot(path, side):
            self.walk(path)
            self.foot_denied(side)

        def ride(path, destination):
            self.walk(path)
            self.board()
            self.ride(destination)

        def repeat():
            foot("reentry-to-foot-south", "south")
            ride("foot-south-to-west", NORTH)

        def finish():
            before = (self.last["lx"], self.last["ly"])
            self.advance("Left", 4)
            self.check("ordinary post-route control", self.last["submodule"] == 0
                       and (self.last["lx"], self.last["ly"]) != before and self.last["mounted"] == 0)

        phases = PHASES
        steps = (self.preconditions, self.enter97, self.earn_key, self.unlock_key, self.strike_lever,
                 lambda: foot("lever-to-foot-south", "south"),
                 lambda: ride("foot-south-to-west", NORTH),
                 lambda: foot("north-to-foot-north", "north"),
                 lambda: ride("foot-north-to-north", WEST),
                 lambda: foot("west-to-foot-south", "south"), self.reload, repeat, finish)
        if self.a.legacy_control:
            phases = ("preconditions", "98-to-97", "legacy-remote-open")
            steps = (self.preconditions, self.enter97, self.legacy_remote_open)
        self.log = (self.a.output / "controller-steps.jsonl").open("x")
        try:
            self.snap()
            for name, step in zip(phases, steps):
                self.phase = name
                before = self.last
                step()
                self.result["phases"].append({"name": name, "before": before, "after": self.last})
                self.shot(name)
                self.result["completed_through"] = name
                if name == stop_after:
                    break
            self.result["runtime_checks_passed"] = True
        finally:
            self.log.close()

    def cleanup(self):
        # Expiry must not leave a held input, but identity must still match.
        self.deadline = time.monotonic() + 10
        try:
            self.check_owner()
        except BaseException as error:
            self.result["cleanup_errors"].append("Ownership refused cleanup: " + repr(error))
            return
        for action in (lambda: self.input(""), self.b.pause):
            try:
                require(action() is not False, "Owned cleanup rejected")
            except BaseException as error:
                self.result["cleanup_errors"].append(repr(error))


def parse_args(argv=None):
    p = argparse.ArgumentParser(description=__doc__)
    for name in ("describe", "validate-candidate", "inspect", "execute-fixtures"):
        p.add_argument("--" + name, action="store_true")
    p.add_argument("--stop-after", choices=PHASES)
    p.add_argument("--legacy-control", action="store_true", help="admit the source-built legacy hook variant; only prove remote opening")
    for name in ("socket", "rom-sha256", "rom-sha1", "symbols-sha256", "owner", "code-sha256", "route-sha256"):
        p.add_argument("--" + name)
    for name in ("owned-rom", "symbols", "client-root", "status-file", "owner-file", "output", "route"):
        p.add_argument("--" + name, type=Path)
    p.add_argument("--pid", type=int)
    return p.parse_args(argv)


def main(argv=None):
    a = parse_args(argv)
    require(sum(bool(getattr(a, n)) for n in ("describe", "validate_candidate", "inspect", "execute_fixtures")) == 1,
            "Choose exactly one mode")
    if a.describe:
        print(json.dumps({"scope": __doc__, "phases": ("preconditions", "98-to-97", "legacy-remote-open")
                          if a.legacy_control else PHASES, "legacy_control": a.legacy_control, "paths": PATHS,
                          "route_schema": "goron97-controller-route-v1", "native_executed": False}, indent=2))
        return 0
    require(a.owned_rom and a.symbols and a.code_sha256, "Candidate requires ROM/symbols/compiled-code hash")
    rom, symbols = a.owned_rom.read_bytes(), a.symbols.read_bytes()
    code = validate_candidate(rom, symbols.decode(), a.code_sha256, a.legacy_control)
    if a.validate_candidate:
        print(json.dumps({"candidate_ok": True, **code}, indent=2))
        return 0
    identity = ("socket", "rom_sha256", "symbols_sha256", "owner", "client_root", "status_file",
                "owner_file", "output", "pid", "route", "route_sha256")
    require(all(getattr(a, n) for n in identity) and a.pid > 0, "Missing explicit private-session identity")
    require(a.socket.startswith("/tmp/mesen2-") and "oos-rc-play" not in " ".join(map(str, vars(a).values())),
            "Only an owned private socket is admitted")
    require(digest(rom) == a.rom_sha256.lower() and digest(symbols) == a.symbols_sha256.lower(), "Input hash mismatch")
    sha1 = digest(rom, "sha1")
    require(not a.rom_sha1 or a.rom_sha1.lower() == sha1, "ROM SHA1 mismatch")
    a.rom_sha1 = sha1
    route_bytes = a.route.read_bytes()
    require(digest(route_bytes) == a.route_sha256.lower(), "Waypoint file hash mismatch")
    route = load_route(a.route)
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(a.pid)], text=True)
    require("--headless" in command and str(a.owned_rom) in command, "PID is not the explicit private ROM process")
    a.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(a.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    f = Route(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0), route)
    f.result.update(inputs={k: str(v) for k, v in vars(a).items()}, code=code,
                    source_sha256=digest(Path(__file__).read_bytes()))
    def interrupted(signum, _frame):
        raise RuntimeError(f"Controller fixture interrupted by signal {signum}")

    previous_term = signal.signal(signal.SIGTERM, interrupted)
    admitted = False
    try:
        f.check_owner()
        require(f.paused(), "Caller must provide a paused private session")
        require(not f.b.list_breakpoints(), "Refuse existing breakpoints")
        admitted = True
        if a.inspect:
            f.result.update(mode="inspect", inspection=f.snap())
            f.shot("inspection")
        else:
            f.run(a.stop_after)
    except BaseException as error:
        f.result["error"] = repr(error)
        if admitted:
            try:
                f.result["failure_state"] = f.snap()
                f.shot("failure")
            except BaseException as capture_error:
                f.result["capture_error"] = repr(capture_error)
    finally:
        if admitted:
            f.cleanup()
        for path, expected in ((a.owned_rom, a.rom_sha256), (a.symbols, a.symbols_sha256), (a.route, a.route_sha256)):
            if digest(path.read_bytes()) != expected.lower():
                f.result["cleanup_errors"].append("Input file changed: " + str(path))
        complete = f.result.get("completed_through") == ("legacy-remote-open" if a.legacy_control else PHASES[-1])
        ok = bool(f.result.get("runtime_checks_passed") and not f.result["cleanup_errors"] and not f.result.get("error"))
        f.result.update(passed=bool(ok and complete), partial_passed=bool(ok and not complete))
        (a.output / "RESULT.json").write_text(json.dumps(f.result, indent=2) + "\n")
        signal.signal(signal.SIGTERM, previous_term)
    print(json.dumps({"passed": f.result["passed"], "partial_passed": f.result["partial_passed"],
                      "result": str(a.output / "RESULT.json")}))
    return 0 if f.result["passed"] or (a.inspect and not f.result.get("error") and not f.result["cleanup_errors"]) else 1


if __name__ == "__main__":
    raise SystemExit(main())
