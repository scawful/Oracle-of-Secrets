#!/usr/bin/env python3
"""Attach-only grounded Bombchu crawl test; caller owns launch and cleanup.

Grants only Bombchu ownership and 30 bombs, then replaces a bounded hut104
collision patch with floor and a 2x2 obstacle. Each solid type uses the same
geometry. Collision cells restore in finally; inventory fixtures are not saved.
Controller casts exercise 1px/frame movement, wall/corner following, explosions
and ordinary bomb control. No XY, CPU, actor, story, SRAM or ROM writes.
This covers collision-map objects, not NPC/sprite obstruction or acquisition.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
import bombchu_world_sprite as art

native, prototype = art.native, art.prototype


def describe():
    return dict(native_executed=False, footprint="15x15: ancilla center±7",
                fixtures="Restored 20x14 collision patch; ownership $7EF3AD=1 and ammo $7EF343=30; no saved writes",
                checks=["One pixel per active frame", "Right→Up→Right→Down around the same compact obstacle",
                        "No footprint intersection with solid cells; native explosion and one ammo debit",
                        "Directional Bombchu OAM and ordinary bomb control"],
                limitations="Hut collision-map fixture only; no NPC/sprite obstruction, acquisition or persistence claim")


class CrawlFlow(art.BombchuArtFlow):
    def fixture(self):
        native.require((self.r(0x7E0010), self.r(0x7E0011), self.r(0x7E00EE)) == (7, 0, 0)
                       and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104, "Need stable hut104 layer0")
        x, y = (int.from_bytes(self.block(a, 2), "little") for a in (0x7E0022, 0x7E0020))
        c, r = (x & 511) // 8, (y & 511) // 8
        native.require(3 <= c <= 47 and 5 <= r <= 55, "Hut position does not fit bounded crawl fixture")
        self.c0, self.r0, self.c, self.r = c - 3, r - 5, c, r
        self.saved_rows = {0x7F2000 + ty * 64 + self.c0: self.block(0x7F2000 + ty * 64 + self.c0, 20)
                           for ty in range(self.r0, self.r0 + 14)}
        self.solids = {(tx, ty) for tx in (c + 8, c + 9) for ty in (r + 1, r + 2)}
        self.result["fixture_geometry"] = dict(link=[x, y], solid_cells=sorted(self.solids),
            obstacle_world=[(x & ~511) + (c + 8) * 8, (y & ~511) + (r + 1) * 8, 16, 16])

    def paint(self, tile):
        self.check_owner(); native.require(self.paused() and not self.ancilla(7), "Paint requires paused gameplay without bombs")
        for address in self.saved_rows:
            ty = (address - 0x7F2000) // 64
            value = bytes(tile if (tx, ty) in self.solids else 0 for tx in range(self.c0, self.c0 + 20))
            self.result["writes"].append(dict(address=f"{address:06X}", before=self.block(address, 20).hex(), value=value.hex(), reason=f"Declared obstacle {tile:02X}"))
            native.require(self.b.write_block(address, value) and self.block(address, 20) == value, "Collision fixture rejected")

    def sample(self, slot):
        data = self.block(0x7E0BFA, 0x7D)
        return dict(frame=self.result["frame_advances"][-1]["after"], kind=data[0x50 + slot], phase=data[0x64 + slot],
                    xy=[data[0x0A + slot] | data[0x1E + slot] << 8, data[slot] | data[0x14 + slot] << 8],
                    direction=self.r(0x7E07F2), fuse=self.r(0x7E039F + slot))

    def footprint_clear(self, point):
        x, y = (p & 511 for p in point)
        covered = {(c, r) for c in range((x - 7) // 8, (x + 7) // 8 + 1)
                   for r in range((y - 7) // 8, (y + 7) // 8 + 1)}
        native.require(all(self.c0 <= c < self.c0 + 20 and self.r0 <= r < self.r0 + 14 for c, r in covered),
                       f"Crawl escaped the declared floor patch: {point}")
        native.require(not covered & self.solids, f"15x15 footprint intersects solid cells: {point}, {sorted(covered & self.solids)}")

    def crawl(self, tile):
        table = native.pc_offset(0x1DF6CF)
        native.require(self.rom[table + tile] != 0, f"Tile {tile:02X} is not solid in ROM ground table")
        native.require(self.r(0x7E002F) == 6, "Fixture requires Link still facing Right before each cast")
        self.paint(tile)
        before = self.r(prototype.BOMBS)
        self.tap("Y", 1)
        self.until(lambda: self.r(0x7E07F1) != 0, "Bombchu did not spawn", 24)
        slot = self.r(0x7E07F1) - 1
        native.require(slot in (0, 1), "Invalid Bombchu slot")
        rows, segments, exploded, previous, travel_frames = [], [], False, None, 0
        self.result.setdefault("cases", []).append(dict(tile=f"{tile:02X}", ground_table_value=self.rom[table + tile], trace=rows, segments=segments))
        for _ in range(400):
            row = self.sample(slot); rows.append(row)
            if row["kind"] != 7: break
            if row["phase"] == 0:
                self.footprint_clear(row["xy"])
                if previous and previous["phase"] == 0:
                    dx, dy = (row["xy"][i] - previous["xy"][i] for i in (0, 1))
                    elapsed = row["frame"] - previous["frame"]
                    native.require(abs(dx) + abs(dy) == elapsed, f"Expected 1px/frame: delta {dx,dy} across {elapsed} frames")
                    travel_frames += elapsed
                    direction = 3 if dx > 0 else 2 if dx < 0 else 1 if dy > 0 else 0
                    if not segments or segments[-1]["direction"] != direction:
                        segments.append(dict(direction=direction, pixels=0, at=row["xy"]))
                    segments[-1]["pixels"] += abs(dx) + abs(dy)
                if len(rows) == 1 or len(rows) % 16 == 0:
                    objects = self.oam(0x2E)
                    native.require(len(objects) == 1 and objects[0]["large"], "Missing 16x16 Bombchu world sprite")
                    allowed = {(0, 0x80, 0x40, 0)[row["direction"]]}
                    if previous: allowed.add((0, 0x80, 0x40, 0)[previous["direction"]])
                    native.require(objects[0]["props"] & 0xC1 in allowed, "World sprite flip disagrees with crawl direction")
                    row["oam"] = objects[0]
                if len(segments) == 4 and segments[-1]["pixels"] == 1:
                    self.shot(f"crawl-{tile:02X}-far-corner")
            else:
                exploded = True
            previous = row
            self.advance("", 1 if row["phase"] == 0 else 4)
        self.check(f"{tile:02X} wall and convex turns", [s["direction"] for s in segments[:4]], [3, 0, 3, 1])
        native.require(all(s["pixels"] >= 4 for s in segments[:4]) and travel_frames >= 80, "Insufficient physical corner-following path")
        self.check(f"{tile:02X} native explosion", exploded, True)
        self.check(f"{tile:02X} native lifetime completes", self.r(0x7E0C4A + slot), 0)
        self.check(f"{tile:02X} ownership clears", self.r(0x7E07F1), 0)
        self.check(f"{tile:02X} one ammo debit", self.r(prototype.BOMBS), before - 1)
        self.ready()

    def run(self):
        self.result["scope"] = describe(); self.result["scope"]["native_executed"] = True
        self.ready()
        native.require(self.r(0x7E02B2) == 0 and self.r(prototype.menu.HP) >= 24 and not self.ancilla(7), "Need human Link, three hearts and no bombs")
        self.write(0x7EF3AD, 1, "Declared Bombchu ownership"); self.write(prototype.BOMBS, 30, "Declared ammunition")
        self.equip(0x1C)
        if self.r(0x7E002F) != 6: self.tap("Right", 1)
        self.ready(); self.fixture()
        for tile in self.a.solid_tiles: self.crawl(tile)
        self.equip(4)
        before = self.r(prototype.BOMBS)
        self.tap("Y", 1); self.until(lambda: bool(self.ancilla(7)), "Ordinary bomb did not spawn", 24)
        self.check("Ordinary bomb has no crawl owner", self.r(0x7E07F1), 0)
        native.require(all(self.r(0x7E03EA + s) != 0xBC for s in self.ancilla(7)), "Ordinary bomb adopted Bombchu signature")
        self.check("Ordinary bomb retains tile 6E", bool(self.oam(0x6E)), True)
        self.shot("ordinary-bomb-control")
        self.advance("Left", 18); self.advance("", 2)
        self.until(lambda: not self.ancilla(7), "Ordinary bomb did not finish", 300)
        self.check("Ordinary bomb costs one ammo", self.r(prototype.BOMBS), before - 1)
        self.result["runtime_checks_passed"] = True

    def restore(self):
        self.check_owner(); self.input("")
        native.require(self.paused(), "Restoration requires pause")
        native.require(self.r(0x7E0010) == 7 and int.from_bytes(self.block(0x7E00A0, 2), "little") == 0x104, "Room changed; collision restore withheld")
        for address, value in getattr(self, "saved_rows", {}).items():
            native.require(self.b.write_block(address, value) and self.block(address, len(value)) == value, "Collision restore failed")
            self.result["fixture_cleanup"].append(dict(address=f"{address:06X}", restored=value.hex()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true"); parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path); parser.add_argument("--output", type=Path)
    parser.add_argument("--solid-tile", type=lambda s: int(s, 0), action="append", dest="solid_tiles")
    args = parser.parse_args()
    if args.describe: print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output, "Need explicit fixtures, session and output")
    tiles = args.solid_tiles or [0x01, 0x50, 0xC0]
    native.require(1 <= len(tiles) <= 3 and all(t in (0x01, 0x50, 0xC0) for t in tiles), "Use at most three fixture solid types: 01/50/C0")
    values = json.loads(args.session.read_text())
    for key in ("status_file", "owner_file", "owned_rom", "symbols", "client_root"): values[key] = Path(values[key])
    values.update(output=args.output, solid_tiles=tiles); a = SimpleNamespace(**values)
    native.require(a.socket.startswith("/tmp/mesen2-bombchu-crawl-") and a.owner.startswith("codex-bombchu-crawl-")
                   and "oos-rc-play" not in str(values), "Need task-owned private crawl session")
    native.require(native.digest(a.owned_rom.read_bytes()) == a.rom_sha256 and native.digest(a.symbols.read_bytes()) == a.symbols_sha256, "Artifact hash mismatch")
    a.rom_sha1 = native.digest(a.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(a.pid)], text=True)
    native.require("--headless" in command and str(a.owned_rom) in command, "PID is not the private ROM process")
    args.output.mkdir(parents=True, exist_ok=False); sys.path.insert(0, str(a.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = CrawlFlow(a, MesenBridge(a.socket, auto_reconnect=False, max_retries=0)); flow.result["inputs"] = values
    admitted = False
    try:
        flow.check_owner(); native.require(flow.paused() and not flow.b.list_breakpoints(), "Need pause without breakpoints")
        admitted = True; flow.run()
    except Exception as error: flow.result["error"] = repr(error)
    finally:
        if admitted:
            try: flow.restore()
            except Exception as error: flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__": raise SystemExit(main())
