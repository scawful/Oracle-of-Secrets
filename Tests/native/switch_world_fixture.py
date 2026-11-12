#!/usr/bin/env python3
"""Attach-only Switch Hook world fixture; never starts or stops an emulator.

Use --describe without a session, or --plan-dump DIR for a file-only floor review.
Runtime requires a paused,
owned new-items session and --execute-fixtures. A single unused sprite slot gets
D5 or native statue 1C and initialize state08; game code runs its prep/main routines.
Both endpoints are read-only checked against the live dungeon collision map.
Controller input selects/casts each item. No CPU, room, collision-map, story,
SRAM, ROM, invincibility or Link-position writes are made.

This deliberately uses house0104's known clear aisle and existing hookable pot.
It proves mechanics in a controlled world fixture, not acquisition or ice art.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

sys.dont_write_bytecode = True
if "--support-root" in sys.argv:
    sys.path.insert(0, sys.argv[sys.argv.index("--support-root") + 1])
elif "--session" in sys.argv:
    _session = json.loads(Path(sys.argv[sys.argv.index("--session") + 1]).read_text())
    sys.path.insert(0, _session["support_root"])
import new_items_prototype as combined
import switch_hook

native = combined.native
SAFE = {0x00, 0x0E, 0x23, 0x24, 0x25, 0x3B}
# Items/switch_hook.asm SwitchHook_FootprintSafe_overworld: ground, shallow
# water, thick grass, diggable ground. Deep water $08 and all else refuse.
OW_SAFE = {0x00, 0x09, 0x40, 0x48, 0x4A}
OW_HOOKABLE = 0x27      # usdasm bank_07 TileBehavior_Hookshottables (OW)
FIELDS = (0xD00, 0xD10, 0xD20, 0xD30, 0xDD0, 0xE20, 0xE30, 0xF20)
# Ordinary-Hookshot sentinel (ASTRA_REVIEW_18eba8ea.md item 2): beat/target RAM.
SENTINELS = (0x7E0268, 0x7E0269)
# Area $33 (Loom Beach): cheat warp_area lands Link at X07B8/Y0D8B. Routes are
# 8px-grid BFS paths over walkable tiles from that landing (no position writes).
OW_AREA, OW_LANDING = 0x33, (0x07B8, 0x0D8B)
ROUTE_HOOK = (("Down", 0xD9B), ("Left", 0x740), ("Up", 0xD83), ("Left", 0x718),
              ("Up", 0xD03), ("Left", 0x710), ("Up", 0xCF3), ("Left", 0x708),
              ("Up", 0xCEB), ("Left", 0x6B0), ("Down", 0xD7B), ("Right", 0x6C8), ("Down", 0xD8B))
ROUTE_SWAP = (("Down", 0xE1B), ("Left", 0x750), ("Down", 0xE5B), ("Left", 0x720),
              ("Down", 0xE6B), ("Left", 0x6F0), ("Down", 0xEEB))
ROUTE_EDGE = (("Down", 0xD9B), ("Left", 0x740), ("Up", 0xD83), ("Left", 0x718),
              ("Up", 0xD03), ("Left", 0x710), ("Up", 0xCF3), ("Left", 0x708),
              ("Up", 0xCEB), ("Left", 0x6C8), ("Up", 0xC73), ("Right", 0x6D8), ("Up", 0xC6B))


def lorom(address):
    return ((address >> 16) & 0x7F) * 0x8000 + (address & 0x7FFF)


def overworld_tables(rom):
    """Map16Definitions and OverworldTileTypes long addresses, read from the
    LDA.l operands inside Overworld_GetTileTypeAtLocation ($00882E)."""
    code = rom[lorom(0x00882E):lorom(0x008888)]
    first = code.index(bytes([0x0A, 0xAA, 0xBF])) + 3
    second = code.index(bytes([0xAA, 0xBF]), first) + 2
    return (int.from_bytes(code[first:first + 3], "little"),
            int.from_bytes(code[second:second + 3], "little"))


def overworld_tile(rom, ram, map16, x, y):
    """Mirror of Overworld_GetTileTypeAtLocation: ram = 7E0000..0FFF, map16 = 7E2000..3FFF."""
    definitions, types = overworld_tables(rom)
    column = x >> 3
    index = ((((y - word(ram, 0x708)) & word(ram, 0x70A)) << 3)
             | ((column - word(ram, 0x70C)) & word(ram, 0x70E))) & 0xFFFF
    tile = word(map16, index)
    entry = word(rom, lorom(definitions) + ((tile << 2 | (y & 8) >> 2 | column & 1) << 1 & 0xFFFF))
    kind = rom[lorom(types) + (entry & 0x1FF)]
    return kind | (1 if 0x10 <= kind < 0x1C and entry & 0x4000 else 0)


def overworld_footprint(rom, ram, map16, x, y):
    return [dict(x=x + dx, y=y + dy, attr=overworld_tile(rom, ram, map16, x + dx, y + dy))
            for dy in (0, 7, 15) for dx in (0, 7, 15)]


def describe():
    return dict(native_executed=False, room="0104", layer=0,
                initial_link="X0960..0990/Y2178; controller positioning only",
                fixture="One unused sprite slot; D5 with native initialize state08",
                ages_cases=["5F camera step (a)", "5F statue hold plate (b)", "59 pit gap (c)"],
                checks=["Y exchange and return with full-word coordinates and retained reset origin",
                        "Opposite-layer and existing-wall footprint refusals",
                        "Ordinary Hookshot still pulls to the existing pot"],
                writes="Declared actor fields only; no Link/CPU/story/ROM/SRAM/collision writes",
                acquisition_tested=False, art_acceptance=False, page_boundary_crossing_tested=False)


def floor_index(x, y, layer):
    native.require(layer in (0, 1), "Dungeon layer outside 0..1")
    return layer * 0x1000 + ((y & 0x1F8) << 3) + ((x & 0x1FF) >> 3)


def footprint(tiles, x, y, layer):
    return [dict(x=x + dx, y=y + dy,
                 address=f"{0x7F2000 + floor_index(x + dx, y + dy, layer):06X}",
                 attr=tiles[floor_index(x + dx, y + dy, layer)])
            for dy in (0, 7, 15) for dx in (0, 7, 15)]


def safe(points, allowed=SAFE):
    return all(point["attr"] in allowed for point in points)


def overlap(head, block):
    return all(-7 <= head[i] - block[i] < 16 for i in (0, 1))


def word(blob, low):
    return int.from_bytes(blob[low:low + 2], "little")


def dump_plan(directory):
    ram = (directory / "world-ram.bin").read_bytes()
    tiles = (directory / "world-tiles.bin").read_bytes()
    native.require(len(ram) == len(tiles) == 0x2000, "Unexpected offline dump sizes")
    points = {"cold_boot_source": (0x978, 0x2180),
              "safe_target": (0x9A8, 0x2180),
              "unsafe_wall_edge": (0x9D0, 0x2180),
              "ordinary_hook_pot": (0x928, 0x2180)}
    probes = {name: footprint(tiles, *xy, 0) for name, xy in points.items()}
    native.require(safe(probes["cold_boot_source"]) and safe(probes["safe_target"]),
                   "Known aisle is not floor in this dump")
    native.require(not safe(probes["unsafe_wall_edge"]), "Wall-edge fixture became safe")
    native.require(any(p["attr"] == 0x27 for p in probes["ordinary_hook_pot"]),
                   "Hookable pot absent")
    return dict(native_executed=False, room=word(ram, 0xA0),
                link=(word(ram, 0x22), word(ram, 0x20)),
                camera=(word(ram, 0xE2), word(ram, 0xE8)),
                floor_formula="layer*0x1000 + ((Y&0x1F8)<<3) + ((X&0x1FF)>>3)",
                probes=probes, note="Runtime re-reads all floor bytes; dump does not authorize position writes.")


def switch_hook_labels(text):
    """Sorted (address, label) pairs from the asar WLA .sym text for writer blame."""
    labels, section = [], None
    for line in text.splitlines():
        if line.startswith("["):
            section = line.strip()
            continue
        parts = line.split()
        if section != "[labels]":
            continue
        if len(parts) == 2 and ":" in parts[0] and not parts[1].startswith(":"):
            bank, address = parts[0].split(":")
            labels.append((int(bank, 16) << 16 | int(address, 16), parts[1]))
    return sorted(labels)


def owner(labels, pc):
    """Nearest preceding label in the same bank, or None."""
    pc &= 0x7FFFFF if pc >> 16 >= 0x80 else 0xFFFFFF   # FastROM mirror -> sym bank
    best = None
    for address, label in labels:
        if address > pc:
            break
        best = (address, label)
    return best[1] if best and best[0] >> 16 == pc >> 16 else None


class WorldFlow(combined.NewItemsFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.slot = None
        self.saved = {}
        self.room = 0x104
        self.area = None
        self.result["scope"] = dict(native_world_fixture=True, actor="D5/native state08 prep",
                                    no_link_position_writes=True, acquisition_tested=False,
                                    art_acceptance=False, page_boundary_crossing_tested=False)
        self.result["world_cases"] = []

    def snap(self):
        ram = self.block(0x7E0000, 0x1000)
        slot = 0 if self.slot is None else self.slot   # actor fields are unused when no fixture is owned
        result = switch_hook.snapshot(lambda address: ram[address - 0x7E0000]
                                      if address < 0x7E1000 else self.r(address), slot)
        result.update(facing=ram[0x2F], link_state=ram[0x5D],
                      speed=[ram[a + slot] for a in (0xD40, 0xD50, 0xF80)],
                      height=ram[0xF70 + slot], timer=ram[0xDF0 + slot],
                      heads=[dict(slot=i, position=(ram[0xC04 + i] | ram[0xC18 + i] << 8,
                                                     ram[0xBFA + i] | ram[0xC0E + i] << 8),
                                  retract=ram[0xC54 + i])
                             for i in range(5) if ram[0xC4A + i] == 0x1F])
        return result

    def fixture_write(self, offset, value, reason):
        self.check_owner()
        native.require(self.slot is not None and offset in FIELDS and self.paused(),
                       "World write outside owned inactive actor fields")
        address = 0x7E0000 + offset + self.slot
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "World fixture write rejected")
        self.check("Fixture readback", self.r(address), value)

    def spawn(self, x, y, layer, kind=0xD5):
        self.ready()
        native.require(kind in switch_hook.TARGETS, "Fixture supports ice blocks, native statues and diamonds")
        if self.slot is None:
            unused = [i for i in range(15, -1, -1) if self.r(0x7E0DD0 + i) == 0]
            native.require(bool(unused), "No unused sprite slot; do not evict a native actor")
            self.slot = unused[0]
            self.saved = {offset: self.r(0x7E0000 + offset + self.slot) for offset in FIELDS}
        else:
            native.require(self.r(0x7E0E20 + self.slot) == self.actor_kind, "Owned actor was replaced")
        self.actor_kind = kind
        self.fixture_write(0xDD0, 0, "Disable only the task's fixture slot while assigning coordinates")
        # Native Statue prep adds seven to Y; supply its authored origin.
        prep_y = y - 7 if kind == 0x1C else y
        for offset, value in ((0xE20, kind), (0xD10, x & 255), (0xD30, x >> 8),
                              (0xD00, prep_y & 255), (0xD20, prep_y >> 8), (0xF20, layer), (0xE30, 0)):
            self.fixture_write(offset, value, "Declared live D5 world fixture")
        self.fixture_write(0xDD0, 8, "Native initialize module runs properties and D5 prep")
        self.advance("", 2)
        after = self.snap()
        self.check("Native actor prep produced active state", after["state"], 9)
        if kind == 0xD5:
            self.check("Native D5 prep cached origin", after["block_origin"], (x, y))
        self.check("Actor remains at declared position", after["block"], (x, y))
        self.check("Actor remains stationary", after["speed"] + [after["height"], after["timer"]], [0] * 5)

    def floors(self, label, block=None):
        ram = self.block(0x7E0000, 0x1000)
        link = (word(ram, 0x22), word(ram, 0x20))
        layer = ram[0xEE]
        if ram[0x1B] == 0:
            tiles = self.block(0x7E2000, 0x2000)
            probe = lambda x, y: overworld_footprint(self.rom, ram, tiles, x, y)
            allowed = OW_SAFE
        else:
            tiles = self.block(0x7F2000, 0x2000)
            probe = lambda x, y: footprint(tiles, x, y, layer)
            allowed = SAFE
        record = dict(label=label, tiles_sha256=native.digest(tiles), layer=layer,
                      overworld=ram[0x1B] == 0, area=ram[0x8A], allowed=sorted(allowed),
                      source=probe(link[0], link[1] + 8))
        native.require(safe(record["source"], allowed), "Link source footprint is not safe")
        if block is not None:
            record["target"] = probe(*block)
            record["target_safe"] = safe(record["target"], allowed)
        self.result.setdefault("floor_reads", []).append(record)
        return record

    def face(self, direction):
        self.ready()
        self.tap(direction, 2)
        self.ready()
        expected = {"Up": 0, "Down": 2, "Left": 4, "Right": 6}[direction]
        self.check("Controller facing", self.r(0x7E002F), expected)

    def cast(self, label, accepted=False, require_overlap=False, frames=False):
        before = self.snap()
        switch_hook.check_minish(before)
        case = dict(name=label, before=before, trace=[])
        self.result["world_cases"].append(case)
        if frames:
            self.shot(label + "-before")
        self.tap("Y", 1)
        saw_chain = saw_overlap = saw_retract = False
        for _ in range(400):
            now = self.snap()
            switch_hook.check_minish(now)
            case["trace"].append(now)
            if frames and now["beat"] == switch_hook.SWAP - 1:
                self.shot(label + "-peak")
            saw_chain |= bool(now["heads"])
            saw_overlap |= any(overlap(h["position"], before["block"]) for h in now["heads"])
            saw_retract |= any(h["retract"] for h in now["heads"])
            native.require(now["drag"] == 0, "Switch Hook unexpectedly activated vanilla dragging")
            if saw_chain and not now["heads"] and now["active"] == 0:
                break
            self.advance("", 1)
        self.check(label + " created a real chain", saw_chain, True)
        self.ready()
        after = self.snap()
        case.update(after=after, saw_overlap=saw_overlap, saw_retract=saw_retract)
        if accepted:
            switch_hook.check_exchange(before, after, camera_may_move=True)
            self.check(label + " full-word exchange", True, True)
            case["beat"] = switch_hook.check_beat(before, case["trace"])
            self.check(label + " Ages turn-around", after["facing"], before["facing"] ^ 2)
            self.advance("", 4)
            self.check(label + " camera settled before control", self.snap()["camera"], after["camera"])
        else:
            switch_hook.check_rejected(before, after)
            self.check(label + " retracts and releases its latch", (after["active"], after["heads"]), (0, []))
            self.check(label + " had a retract phase", saw_retract, True)
            if require_overlap:
                self.check(label + " chain reached actor footprint", saw_overlap, True)
        self.shot(label + "-landed" if frames else label)
        case["passed"] = True
        return before, after

    # --- Ages beat cases (room fixtures reached by entrance warp in the driver) ---

    def settle(self, limit=120):
        """Wait out an in-room submodule ($11), e.g. the plate sink animation
        that vanilla PushPressurePlate starts when Link steps on a plate."""
        for _ in range(limit):
            if not self.r(0x7E0011):
                return
            self.advance("", 1)
        raise AssertionError("Dungeon submodule did not return to player control")

    def walk(self, direction, done, limit=160):
        for _ in range(limit):
            ram = self.block(0x7E0000, 0x100)
            if done(word(ram, 0x22), word(ram, 0x20)):
                self.advance("", 2)
                return word(ram, 0x22), word(ram, 0x20)
            self.advance(direction, 1)
        raise AssertionError(f"Walk {direction} did not reach its goal")

    def pick(self, item):
        """Right at a row end turns to the Equipment page (custom grid), so
        reach a bottom-row item with Down, then move within the row."""
        if item not in combined.BOTTOM:
            return super().pick(item)
        native.require(self.screen() == "items", "Need Items screen")
        for _ in range(6):
            if self.r(0x7E0202) in combined.BOTTOM:
                break
            self.tap("Down")
        row = combined.BOTTOM
        for _ in range(len(row)):
            current = self.r(0x7E0202)
            native.require(self.screen() == "items" and current in row,
                           f"Cursor left the bottom row at {current:02X}")
            if current == item:
                return
            self.tap("Right" if row.index(current) < row.index(item) else "Left")
        raise RuntimeError(f"Item {item:02X} is unreachable")

    def enter(self, room):
        self.room = room
        self.ready()
        ram = self.block(0x7E0000, 0x1000)
        self.check("Case room", word(ram, 0xA0), room)
        switch_hook.check_minish(dict(gbc=ram[0xFFF], mask=ram[0x2B2]))
        if self.r(0x7EF3AE) != 1:
            self.write(0x7EF3AE, 1, "Declared new-item ownership fixture (private save only)")
        self.equip(0x1D)

    def place(self, label, target, kind=0xD5, expect_safe=True):
        self.check(label + " target safe", self.floors(label, target)["target_safe"], expect_safe)
        self.spawn(*target, 0, kind=kind)

    def case_camera(self):
        """(a) Room 28 bottom hall scrolls horizontally: a 72px swap left
        leaves the follow box, so the camera must step after landing."""
        self.enter(0x28)
        x, y = self.walk("Up", lambda x, y: y <= 0x05B0)
        self.face("Left")
        x, y = (word(self.block(0x7E0000, 0x100), o) for o in (0x22, 0x20))
        self.place("camera", (x - 0x48, y + 8))
        before, after = self.cast("ages-camera", accepted=True, frames=True)
        self.check("Camera stepped toward Link", after["camera"][0] < before["camera"][0], True)
        self.clear_actor()

    def case_plate(self):
        """(b) Room 5F: statue presses the hold plate; swaps move it off and back on."""
        self.enter(0x5F)
        self.walk("Up", lambda x, y: y <= 0x0BB8)
        self.walk("Right", lambda x, y: x >= 0x1F7E)
        self.place("plate-statue", (0x1F80, 0x0B80), kind=0x1C)
        self.advance("", 2)
        self.check("Statue presses plate", self.r(0x7E0642), 1)
        self.face("Up")
        self.shot("ages-plate-pressed")
        self.cast("ages-plate-off", accepted=True, frames=True)
        self.walk("Down", lambda x, y: y >= 0x0B98)
        self.advance("", 2)
        self.check("Moved statue releases plate", self.r(0x7E0642), 0)
        self.shot("ages-plate-released")
        # face("Down") taps 2 frames and walks ~3 px back down; aim above
        # the 0B75..0B7B window. The plate sink/shutter submodule runs first.
        self.walk("Up", lambda x, y: y <= 0x0B76)
        self.settle()
        self.face("Down")
        y = word(self.block(0x7E0000, 0x100), 0x20)
        native.require(0x0B75 <= y <= 0x0B7B, f"Link Y {y:04X} would not put the statue on the plate")
        self.cast("ages-plate-on", accepted=True, frames=True)
        self.advance("", 2)
        native.require(self.snap()["link"][1] + 8 > 0x0B8F, "Link feet still on the plate")
        self.check("Swapped statue presses plate", self.r(0x7E0642), 1)
        self.shot("ages-plate-pressed-again")
        self.clear_actor()

    def case_pit(self):
        """(c) Room 59: swap straight up across the pit band (Y 0B80..0B97)."""
        self.enter(0x59)
        x, y = self.walk("Up", lambda x, y: y <= 0x0BA8)
        self.face("Up")
        x, y = (word(self.block(0x7E0000, 0x100), o) for o in (0x22, 0x20))
        tiles = self.block(0x7F2000, 0x2000)
        gap = [tiles[floor_index(x + 8, row, 0)] for row in range(0x0B80, 0x0B98, 8)]
        self.result["pit_gap"] = gap
        self.check("Pit band between Link and target", all(t == 0x20 for t in gap), True)
        self.place("pit", (x, 0x0B60))
        self.cast("ages-pit", accepted=True, frames=True)
        self.clear_actor()

    def case_diamond(self):
        """(d) Room 59: Swap Diamond across the pit band, then swap it back.
        After the first swap the diamond stands at Link's old spot and the
        Ages turn-around already faces it, so the return cast needs no input."""
        self.enter(0x59)
        x, y = self.walk("Up", lambda x, y: y <= 0x0BA8)
        self.face("Up")
        x, y = (word(self.block(0x7E0000, 0x100), o) for o in (0x22, 0x20))
        tiles = self.block(0x7F2000, 0x2000)
        gap = [tiles[floor_index(x + 8, row, 0)] for row in range(0x0B80, 0x0B98, 8)]
        self.result["pit_gap"] = gap
        self.check("Pit band between Link and diamond", all(t == 0x20 for t in gap), True)
        self.place("diamond", (x, 0x0B60), kind=switch_hook.TARGETS[2])
        before, after = self.cast("ages-diamond", accepted=True, frames=True)
        self.check("Diamond re-placed at Link's old spot", after["block"],
                   (before["link"][0], (before["link"][1] + 8) & 0xFFFF))
        self.check("Return cast faces the diamond", self.r(0x7E002F), 2)
        self.check("Return target safe", safe(self.floors("diamond-back", after["block"])["target"]), True)
        back, again = self.cast("ages-diamond-back", accepted=True, frames=True)
        self.check("Second swap restores the start", (again["link"], again["block"]),
                   (before["link"], before["block"]))
        self.clear_actor()

    # --- Overworld cases (driver warps to area $33 by cheat before these run) ---

    def enter_area(self, area, item=0x1D):
        self.area, self.room = area, None
        self.ready()
        ram = self.block(0x7E0000, 0x1000)
        self.check("Case module/area", (ram[0x10], ram[0x1B], ram[0x8A]), (0x09, 0, area))
        self.check("Area landing", (word(ram, 0x22), word(ram, 0x20)), OW_LANDING)
        switch_hook.check_minish(dict(gbc=ram[0xFFF], mask=ram[0x2B2]))
        if self.r(0x7EF3AE) != 1:
            self.write(0x7EF3AE, 1, "Declared new-item ownership fixture (private save only)")
        self.equip(item)

    def route(self, segments):
        """Controller-only walk; each segment holds one direction until its axis passes the goal."""
        tests = {"Down": lambda x, y, g: y >= g, "Up": lambda x, y, g: y <= g,
                 "Left": lambda x, y, g: x <= g, "Right": lambda x, y, g: x >= g}
        for direction, goal in segments:
            self.walk(direction, lambda x, y: tests[direction](x, y, goal), limit=400)
            switch_hook.check_minish(self.snap() if self.slot is not None
                                     else dict(gbc=self.r(0x7E0FFF), mask=self.r(0x7E02B2)))
        self.ready()
        position = tuple(word(self.block(0x7E0000, 0x100), o) for o in (0x22, 0x20))
        self.result.setdefault("routes", []).append(dict(segments=segments, end=position))
        return position

    def link(self):
        ram = self.block(0x7E0000, 0x100)
        return word(ram, 0x22), word(ram, 0x20)

    def case_ow_swap(self):
        """(a)+(b) Area 33 beach: Link on sand faces down across deep water ($08)
        to a 16px shallow islet. Deep-water target refuses; islet swap and the
        return swap are accepted and the camera follows each way."""
        self.enter_area(OW_AREA)
        self.route(ROUTE_SWAP)
        self.face("Down")
        x, y = self.link()
        ram, tiles = self.block(0x7E0000, 0x1000), self.block(0x7E2000, 0x2000)
        lane = [overworld_tile(self.rom, ram, tiles, x + 8, row) for row in range(y + 24, 0x0F28, 8)]
        self.result["deep_water_lane"] = lane
        self.check("Deep water between Link and islet", 0x08 in lane and set(lane) <= OW_SAFE | {0x08}, True)
        self.place("ow-deep-water", (0x06F0, 0x0F13), kind=switch_hook.TARGETS[2], expect_safe=False)
        self.cast("ow-refuse-deep-water", require_overlap=True)
        self.place("ow-islet", (0x06F0, 0x0F2B), kind=switch_hook.TARGETS[2])
        before, after = self.cast("ow-swap", accepted=True, frames=True)
        self.check("Overworld camera followed Link down", after["camera"][1] > before["camera"][1], True)
        self.check("Return cast faces the diamond", self.r(0x7E002F), 0)
        self.check("Return target safe", self.floors("ow-back", after["block"])["target_safe"], True)
        back, again = self.cast("ow-swap-back", accepted=True, frames=True)
        self.check("Overworld camera followed Link up", again["camera"][1] < back["camera"][1], True)
        self.check("Second swap restores the start", (again["link"], again["block"]),
                   (before["link"], before["block"]))
        self.clear_actor()

    def case_ow_edge(self):
        """(c) Area 33 north path: the landing margin is 16px inside the ZS
        transition threshold (Y-$0708 >= 4). Link landing Y-$0708 = $13 refuses,
        $14 accepts; then a miss shot and a walk across the top edge."""
        self.enter_area(OW_AREA)
        self.route(ROUTE_EDGE)
        self.face("Up")
        x = self.link()[0] & 0xFFF8      # 8px column; the hook overlap box tolerates drift
        origin = self.r(0x7E0708) | self.r(0x7E0709) << 8
        refuse, accept = (x, origin + 0x13 + 8), (x, origin + 0x14 + 8)
        self.result["edge_targets"] = dict(area_top=origin, refuse=refuse, accept=accept)
        self.place("ow-edge-refuse", refuse, kind=switch_hook.TARGETS[2])
        self.cast("ow-edge-refuse", require_overlap=True)
        self.place("ow-edge-accept", accept, kind=switch_hook.TARGETS[2])
        before, after = self.cast("ow-edge-accept", accepted=True, frames=True)
        self.check("Camera stepped up, inside the area", (after["camera"][1] <= before["camera"][1],
                                                          after["camera"][1] >= origin), (True, True))
        self.clear_actor()
        self.face("Up")
        self.cast_miss("ow-edge-miss")
        start = self.snap()
        transition = []
        for _ in range(600):
            ram = self.block(0x7E0000, 0x1000)
            transition.append(dict(module=ram[0x10], submodule=ram[0x11], area=ram[0x8A],
                                   active=ram[0x7F8], beat=ram[0x268], link_state=ram[0x5D]))
            native.require(ram[0x7F8] == 0, "Switch Hook latch set during the area transition")
            if ram[0x8A] != OW_AREA and ram[0x10] == 0x09 and ram[0x11] == 0:
                break
            self.advance("Up", 1)
        self.input(""); self.ready()
        end = self.snap()
        switch_hook.check_minish(end)
        self.result["edge_transition"] = dict(trace=transition, start=start, end=end)
        self.check("Area transition happened", end["area"] != OW_AREA and end["module"] == 0x09, True)
        self.check("No stuck shot or beat after the transition",
                   (end["active"], end["drag"], 0x1F in end["ancilla"], end["link_state"],
                    end["z"] in (0, 0xFFFF)), (0, 0, False, 0, True))
        self.area = end["area"]
        self.advance("", 30)                 # let the post-transition walk-in finish
        self.cast_miss("ow-after-transition-miss")
        self.shot("ow-after-transition")

    def cast_miss(self, label):
        """Switch Hook with no target: chain extends, retracts, latch releases."""
        self.ready()
        before = self.snap()
        self.tap("Y", 1)
        saw_chain = False
        for _ in range(240):
            now = self.snap()
            switch_hook.check_minish(now)
            native.require(now["drag"] == 0 and now["beat"] in (0, before["beat"]),
                           "Miss shot started a pull or a beat")
            saw_chain |= bool(now["heads"])
            if saw_chain and not now["heads"] and now["active"] == 0:
                break
            self.advance("", 1)
        self.ready()
        after = self.snap()
        self.check(label + " chain and release", (saw_chain, after["active"], after["link"]),
                   (True, 0, before["link"]))
        self.result["world_cases"].append(dict(name=label, before=before, after=after, passed=True))

    def sentinel_write(self, address, value, reason):
        self.check_owner()
        native.require(address in SENTINELS and self.paused() and self.r(0x7E07F8) == 0,
                       "Sentinel write outside the inactive beat/target bytes")
        entry = dict(address=f"{address:06X}", before=self.r(address), value=value, reason=reason)
        self.result["writes"].append(entry)
        native.require(self.b.write_memory(address, value), "Sentinel write rejected")
        self.check("Sentinel readback", self.r(address), value)

    def case_ow_hook(self):
        """(e) Ordinary Hookshot on the overworld with the Astra sentinel:
        $07F8=0, $0268=$30 (>= swap beat 34), $0269 = a live unrelated diamond.
        The vanilla pull must run and leave sentinel, actor height and latch untouched."""
        self.enter_area(OW_AREA, item=3)     # from the seed cursor; the custom bottom row has no path up
        self.route(ROUTE_HOOK)
        x, y = self.link()
        spots = [(x, y + 0x28), (x + 0x20, y + 8), (x, y - 0x18), (x + 0x30, y + 8)]
        spot = next((p for p in spots if self.floors("ow-sentinel-probe", p)["target_safe"]), None)
        native.require(spot is not None, "No safe off-lane spot for the sentinel actor")
        self.place("ow-sentinel-actor", spot, kind=switch_hook.TARGETS[2])
        self.face("Left")
        self.sentinel_write(0x7E0268, 0x30, "Sentinel: stale beat past the swap frame while inactive")
        self.sentinel_write(0x7E0269, self.slot, "Sentinel: stale target = declared unrelated actor")
        ram, tiles = self.block(0x7E0000, 0x1000), self.block(0x7E2000, 0x2000)
        origin = (word(ram, 0x22), word(ram, 0x20))
        lane = []
        for column in range(origin[0] - 8, origin[0] - 128, -8):   # the chain head travels on Link Y+8
            kind = overworld_tile(self.rom, ram, tiles, column, origin[1] + 8)
            lane.append(kind)
            if kind not in OW_SAFE | {0x08}:
                break
        self.check("Hookshottable $27 ends a clear lane to the left", lane[-1], OW_HOOKABLE)
        rows = {f"y+{dy}": [overworld_tile(self.rom, ram, tiles, column, origin[1] + dy)
                             for column in range(origin[0] - 8, origin[0] - 136, -8)] for dy in range(0, 32, 4)}
        sprites = [dict(slot=i, kind=ram[0xE20 + i], state=ram[0xDD0 + i],
                        x=ram[0xD10 + i] | ram[0xD30 + i] << 8, y=ram[0xD00 + i] | ram[0xD20 + i] << 8)
                   for i in range(16) if ram[0xDD0 + i]]
        record = self.result["ordinary_hook_control"] = dict(before=origin, lane=lane, trace=[], rows=rows,
                                                             sprites=sprites, sentinel=(0x30, self.slot))
        watched = {0x7E0030: "$30 follow-box Y", 0x7E0031: "$31 follow-box X", 0x7E0024: "Link Z",
                   0x7E0268: "beat", 0x7E0269: "target", 0x7E07F8: "latch",
                   0x7E0F70 + self.slot: "sentinel actor height"}
        watches = {address: self.writer_watch(address) for address in watched}
        self.tap("Y", 1)
        saw_chain = saw_pull = moved = False
        for _ in range(240):
            ram = self.block(0x7E0000, 0x1000)
            point = (word(ram, 0x22), word(ram, 0x20))
            chains = [i for i in range(5) if ram[0xC4A + i] == 0x1F]
            row = dict(link=point, camera=(word(ram, 0xE2), word(ram, 0xE8)), drag=ram[0x37E], frame=ram[0x1A],
                       chains=chains, active=ram[0x7F8], beat=ram[0x268], target=ram[0x269],
                       height=ram[0xF70 + self.slot], z=word(ram, 0x24), state=ram[0x5D],
                       heads=[(ram[0xC04 + i] | ram[0xC18 + i] << 8, ram[0xBFA + i] | ram[0xC0E + i] << 8)
                              for i in chains])
            record["trace"].append(row)
            switch_hook.check_minish(dict(gbc=ram[0xFFF], mask=ram[0x2B2]))
            native.require(row["active"] == 0, "Ordinary Hookshot acquired Switch Hook latch")
            native.require((row["beat"], row["target"]) == (0x30, self.slot), "Ordinary Hookshot wrote the sentinel")
            native.require(row["height"] == 0, "Ordinary Hookshot lifted the sentinel actor")
            saw_chain |= bool(chains)
            saw_pull |= row["drag"] != 0
            moved |= point[0] < origin[0]
            if saw_chain and not chains and ram[0x5D] == 0:
                break
            self.advance("", 1)
        labels = switch_hook_labels(self.symbols)
        writers = record["writers"] = {}
        for address, ident in watches.items():
            rows = self.writer_blame(ident)
            writers[f"{address:06X} {watched[address]}"] = sorted({(pc, value, owner(labels, pc)) for pc, value in rows})
        # Root's fire-time guard: SwitchHook_Init clears the latch (STZ, value 0) on every
        # Hookshot fire before its item-$1D test. That is the only Switch Hook write allowed.
        guard = [row for row in writers["7E07F8 latch"]
                 if row[1] == 0 and row[2] == "Oracle_SwitchHook_Init"]
        owned = [(name, pc, value, label) for name, rows in writers.items() for pc, value, label in rows
                 if label and "SwitchHook" in label and (pc, value, label) not in guard]
        self.check("Ordinary Hookshot frames run no Switch Hook writer (camera step, Clear, Exchange)", owned, [])
        self.check("Only Root's fire-time Init guard clears the latch", writers["7E07F8 latch"], guard)
        for name in ("7E0268 beat", "7E0269 target", "7E0F%02X sentinel actor height" % (0x70 + self.slot)):
            self.check(f"No writer touches {name}", writers[name], [])
        self.check("Ordinary Hookshot creates chain", saw_chain, True)
        self.check("Ordinary Hookshot still pulls to the overworld $27 tile", saw_pull and moved, True)
        self.ready()
        record["after"] = self.snap()
        self.shot("ow-ordinary-hookshot-pull")
        self.clear_actor()

    def writer_watch(self, address):
        reply = self.b.mem_watch_add(address, 1, 128)
        native.require(reply.get("success"), "Native watch rejected: " + str(reply))
        value = reply.get("data", {})
        value = json.loads(value) if isinstance(value, str) else value
        return native.number(value["watch_id"])

    def writer_blame(self, ident):
        reply = self.b.mem_blame(watch_id=ident)
        value = reply.get("data", {})
        value = json.loads(value) if isinstance(value, str) else value
        self.b.mem_watch_remove(ident)
        return [(native.number(w["pc"]), native.number(w["value"])) for w in (value or {}).get("writes", [])]

    def clear_actor(self):
        if self.slot is None:
            return
        self.check_owner()
        if self.area is None:
            same_place = (self.r(0x7E00A0) | self.r(0x7E00A1) << 8) == self.room
        else:
            same_place = self.r(0x7E001B) == 0 and self.r(0x7E008A) == self.area
        native.require(self.r(0x7E0E20 + self.slot) == self.actor_kind and same_place,
                       "Do not delete an actor after identity/room/area changed")
        self.fixture_write(0xDD0, 0, "Remove only the task-created actor fixture")
        for offset, value in self.saved.items():
            if offset != 0xDD0:
                self.fixture_write(offset, value, "Restore originally unused slot's explicit fixture fields")
        self.result["fixture_cleanup"].append(dict(slot=self.slot, state=0,
                                                    note="Native prep scratch remains inactive; next spawn owns it."))
        self.slot = None

    def ordinary_control(self):
        self.equip(3)
        self.face("Left")
        ram = self.block(0x7E0000, 0x1000)
        tiles = self.block(0x7F2000, 0x2000)
        origin = (word(ram, 0x22), word(ram, 0x20))
        pots = [(x, origin[1] + 8) for x in range(origin[0] - 16, max(0x920, origin[0] - 128), -1)
                if tiles[floor_index(x, origin[1] + 8, ram[0xEE])] == 0x27]
        native.require(bool(pots), "Ordinary Hookshot control needs visible existing hookable pot to left")
        self.result["ordinary_hook_control"] = dict(before=origin, existing_hook_tiles=pots)
        self.tap("Y", 1)
        trace, saw_chain, saw_pull, moved = [], False, False, False
        for _ in range(180):
            ram = self.block(0x7E0000, 0x1000)
            point = (word(ram, 0x22), word(ram, 0x20))
            chains = [i for i in range(5) if ram[0xC4A + i] == 0x1F]
            trace.append(dict(link=point, drag=ram[0x37E], chains=chains, active=ram[0x7F8]))
            native.require(ram[0x7F8] == 0, "Ordinary Hookshot acquired Switch Hook latch")
            saw_chain |= bool(chains)
            saw_pull |= ram[0x37E] != 0
            moved |= point[0] < origin[0]
            if saw_chain and not chains and ram[0x5D] == 0:
                break
            self.advance("", 1)
        self.result["ordinary_hook_control"]["trace"] = trace
        self.check("Ordinary Hookshot creates chain", saw_chain, True)
        self.check("Ordinary Hookshot still pulls to native pot", saw_pull and moved, True)
        self.ready()
        self.shot("ordinary-hookshot-pull")

    def run(self):
        self.ready()
        ram = self.block(0x7E0000, 0x1000)
        self.check("Fixture room", word(ram, 0xA0), 0x104)
        self.check("Fixture layer", ram[0xEE], 0)
        native.require(ram[0x1B] == 1 and ram[0x2B2] in (0, 6), "Need ordinary indoor Link")
        native.require(0x960 <= word(ram, 0x22) <= 0x990 and word(ram, 0x20) == 0x2178,
                       "Need cold-boot house aisle (X0960..0990/Y2178); no position writes permitted")
        native.require(self.r(0x7EF3AE) == 1 and self.r(combined.HOOK) == 1,
                       "Private save must retain already-granted Switch Hook and ordinary Hookshot")
        self.equip(0x1D)
        self.face("Right")
        ram = self.block(0x7E0000, 0x1000)
        target = (word(ram, 0x22) + 48, word(ram, 0x20) + 8)
        self.check("Forward target safe", safe(self.floors("forward", target)["target"]), True)
        self.spawn(*target, 0)
        self.shot("switch-world-before")
        self.cast("switch-exchange", accepted=True)
        self.face("Left")
        self.check("Return target safe", safe(self.floors("return", self.snap()["block"])["target"]), True)
        self.cast("switch-return", accepted=True)
        self.face("Right")
        self.fixture_write(0xF20, 1, "Opposite-layer refusal fixture on task-owned D5")
        self.cast("switch-opposite-layer", require_overlap=True)
        self.fixture_write(0xF20, 0, "Restore task-owned actor layer")
        target = (0x9D0, 0x2180)
        self.check("Existing wall makes target unsafe", safe(self.floors("unsafe-wall", target)["target"]), False)
        self.spawn(*target, 0)
        self.cast("switch-unsafe-wall", require_overlap=True)
        self.clear_actor()
        self.face("Right")
        ram = self.block(0x7E0000, 0x1000)
        target = (word(ram, 0x22) + 48, word(ram, 0x20) + 8)
        self.check("Statue target safe", safe(self.floors("statue", target)["target"]), True)
        self.spawn(*target, 0, kind=0x1C)
        self.cast("switch-statue-exchange", accepted=True)
        self.face("Left")
        self.cast("switch-statue-return", accepted=True)
        self.clear_actor()
        self.ordinary_control()
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--support-root", type=Path)
    parser.add_argument("--plan-dump", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--execute-fixtures", action="store_true")
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    if args.plan_dump:
        print(json.dumps(dump_plan(args.plan_dump), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output,
                   "Require explicit --session, --output and --execute-fixtures")
    session = json.loads(args.session.read_text())
    for key in ("pid", "socket", "owner", "rom_sha256", "symbols_sha256"):
        setattr(args, key, session[key])
    for key in ("owned_rom", "symbols", "client_root", "status_file", "owner_file"):
        setattr(args, key, Path(session[key]))
    native.require(args.socket.startswith("/tmp/mesen2-new-items-")
                   and args.owner.startswith("codex-new-items-") and "oos-rc-play" not in str(args),
                   "Only task-owned new-items session admitted")
    native.require(native.digest(args.owned_rom.read_bytes()) == args.rom_sha256, "Private ROM hash differs")
    native.require(native.digest(args.symbols.read_bytes()) == args.symbols_sha256, "Symbols hash differs")
    args.rom_sha1 = native.digest(args.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(args.pid)], text=True)
    native.require("--headless" in command and str(args.owned_rom) in command, "PID identity differs")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = WorldFlow(args, MesenBridge(args.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = vars(args)
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused session with no breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.check_owner(); flow.input(""); flow.b.pause(); flow.clear_actor()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
