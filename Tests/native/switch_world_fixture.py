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
FIELDS = (0xD00, 0xD10, 0xD20, 0xD30, 0xDD0, 0xE20, 0xE30, 0xF20)


def describe():
    return dict(native_executed=False, room="0104", layer=0,
                initial_link="X0960..0990/Y2178; controller positioning only",
                fixture="One unused sprite slot; D5 with native initialize state08",
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


def safe(points):
    return all(point["attr"] in SAFE for point in points)


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


class WorldFlow(combined.NewItemsFlow):
    def __init__(self, args, bridge):
        super().__init__(args, bridge)
        self.slot = None
        self.saved = {}
        self.result["scope"] = dict(native_world_fixture=True, actor="D5/native state08 prep",
                                    no_link_position_writes=True, acquisition_tested=False,
                                    art_acceptance=False, page_boundary_crossing_tested=False)
        self.result["world_cases"] = []

    def snap(self):
        ram = self.block(0x7E0000, 0x1000)
        result = switch_hook.snapshot(lambda address: ram[address - 0x7E0000]
                                      if address < 0x7E1000 else self.r(address), self.slot)
        result.update(facing=ram[0x2F], link_state=ram[0x5D],
                      speed=[ram[a + self.slot] for a in (0xD40, 0xD50, 0xF80)],
                      height=ram[0xF70 + self.slot], timer=ram[0xDF0 + self.slot],
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
        native.require(kind in (0xD5, 0x1C), "Fixture supports ice blocks and native statues")
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
        tiles = self.block(0x7F2000, 0x2000)
        link = (word(ram, 0x22), word(ram, 0x20))
        layer = ram[0xEE]
        record = dict(label=label, tiles_sha256=native.digest(tiles), layer=layer,
                      source=footprint(tiles, link[0], link[1] + 8, layer))
        native.require(safe(record["source"]), "Link source footprint is not safe")
        if block is not None:
            record["target"] = footprint(tiles, *block, layer)
        self.result.setdefault("floor_reads", []).append(record)
        return record

    def face(self, direction):
        self.ready()
        self.tap(direction, 2)
        self.ready()
        expected = {"Up": 0, "Down": 2, "Left": 4, "Right": 6}[direction]
        self.check("Controller facing", self.r(0x7E002F), expected)

    def cast(self, label, accepted=False, require_overlap=False):
        before = self.snap()
        case = dict(name=label, before=before, trace=[])
        self.result["world_cases"].append(case)
        self.tap("Y", 1)
        saw_chain = saw_overlap = saw_retract = False
        for _ in range(180):
            now = self.snap()
            case["trace"].append(now)
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
            switch_hook.check_exchange(before, after)
            self.check(label + " full-word exchange", True, True)
        else:
            switch_hook.check_rejected(before, after)
            self.check(label + " retracts and releases its latch", (after["active"], after["heads"]), (0, []))
            self.check(label + " had a retract phase", saw_retract, True)
            if require_overlap:
                self.check(label + " chain reached actor footprint", saw_overlap, True)
        self.shot(label)
        case["passed"] = True

    def clear_actor(self):
        if self.slot is None:
            return
        self.check_owner()
        native.require(self.r(0x7E0E20 + self.slot) == self.actor_kind
                       and (self.r(0x7E00A0) | self.r(0x7E00A1) << 8) == 0x104,
                       "Do not delete an actor after identity/room changed")
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
