#!/usr/bin/env python3
"""Attach-only Bombchu world-art check; caller owns launch and cleanup.

Only Bombchu ownership ($7EF3AD=1) and bomb ammunition ($7EF343=30) are
fixture writes. Four directional casts, menu selection, movement and the
ordinary-bomb control use controllers. Caller supplies open floor with enough
space for at least 16 travel frames in all four directions. No position, CPU,
actor, story, SRAM, save-state or ROM writes; no save/reopen qualification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

sys.dont_write_bytecode = True
import new_items_prototype as prototype

native = prototype.native
DIRECTIONS = ("Up", "Down", "Left", "Right")
PROTECTED_TILES = (*range(0x2A, 0x2E), *range(0x3A, 0x3E), 0x6E, 0x6F, 0x7E, 0x7F)


def describe():
    return dict(native_executed=False, fixture_writes={"7EF3AD": 1, "7EF343": 30},
                checks=["Four controller casts: tile2E/page0, large OAM, palette2 before native fuse flash, directional flips",
                        "Both crawl frames match ROM bytes uploaded to VRAM85C0/87C0",
                        "Forward travel, one ammo debit, native explosion and lifetime",
                        "Bombchu and ordinary bomb coexist as tile2E/tile6E; arrow/bomb tiles remain unchanged"],
                prerequisite="Paused owned headless gameplay, ordinary Link, open floor in all directions",
                limitations="Open-floor fixture only; acquisition, route and save/reopen are not tested")


class BombchuArtFlow(prototype.NewItemsFlow):
    def write(self, address, value, reason):
        native.require({0x7EF3AD: 1, prototype.BOMBS: 30}.get(address) == value,
                       "Write outside Bombchu ownership/ammunition fixture")
        super().write(address, value, reason)

    def memory(self, address, size, kind):
        data = bytes(self.b.read_block(address, size, memtype=kind))
        native.require(len(data) == size, f"Short {kind} read at {address:04X}")
        return data

    def tile_bytes(self, tiles):
        return b"".join(self.memory(0x8000 + t * 32, 32, "SnesVideoRam") for t in tiles)

    def oam(self, tile):
        raw = self.memory(0, 544, "SnesSpriteRam")
        found = []
        for i in range(128):
            x, y, char, props = raw[i * 4:i * 4 + 4]
            ext = raw[512 + i // 4] >> ((i % 4) * 2) & 3
            if char == tile and not props & 1 and y < 224 and not ext & 1:
                found.append(dict(index=i, x=x, y=y, props=props, large=bool(ext & 2)))
        return found

    def cast(self, direction):
        name = DIRECTIONS[direction]
        self.tap(name, 2); self.ready()
        before = self.r(prototype.BOMBS)
        self.tap("Y", 1)
        self.until(lambda: self.r(0x7E07F1) != 0, name + " did not allocate Bombchu", 24)
        slot = self.r(0x7E07F1) - 1
        native.require(slot in (0, 1), "Bombchu used a non-bomb slot")
        self.check(name + " direction", self.r(0x7E07F2), direction)
        self.check(name + " signature", self.r(0x7E03EA + slot), 0xBC)
        origin, seen, trace, moved, exploded = self.position(slot), set(), [], False, False
        self.result.setdefault("casts", {})[name] = trace
        for _ in range(64):
            kind, phase = self.r(0x7E0C4A + slot), self.r(0x7E0C5E + slot)
            if kind != 7:
                break
            point = self.position(slot)
            row = dict(kind=kind, phase=phase, position=point, fuse=self.r(0x7E039F + slot))
            trace.append(row)
            if phase == 0:
                objects = self.oam(0x2E)
                native.require(len(objects) == 1, f"{name}: expected one visible Bombchu, got {objects}")
                obj = objects[0]
                native.require(obj["large"] and obj["props"] & 0xC1 == (0, 0x80, 0x40, 0)[direction],
                               f"{name}: wrong OAM size, page or flips: {obj}")
                if row["fuse"] >= 32:
                    native.require(obj["props"] & 0x0E == 4, f"{name}: wrong pre-flash palette: {obj}")
                pixels = self.tile_bytes((0x2E, 0x2F, 0x3E, 0x3F))
                family = self.frames[:2] if direction < 2 else self.frames[2:]
                native.require(pixels in family, f"{name}: VRAM does not match either directional ROM frame")
                frame = family.index(pixels)
                if frame not in seen:
                    self.shot(f"bombchu-{name.lower()}-{frame}")
                seen.add(frame)
                row.update(oam=obj, frame=frame, vram_sha256=native.digest(pixels))
                dx, dy = (point[i] - origin[i] for i in (0, 1))
                moved |= (-dy, dy, -dx, dx)[direction] >= 2
            else:
                if exploded:
                    native.require(not self.oam(0x2E), name + ": custom sprite survived into native explosion")
                exploded = True
            self.advance("", 4)
        self.check(name + " both crawl frames", sorted(seen), [0, 1])
        self.check(name + " forward travel", moved, True)
        self.check(name + " native explosion", exploded, True)
        self.check(name + " native lifetime complete", self.r(0x7E0C4A + slot), 0)
        self.check(name + " owner cleared", self.r(0x7E07F1), 0)
        self.check(name + " one ammunition debit", self.r(prototype.BOMBS), before - 1)
        self.check(name + " protected arrow/bomb tiles", native.digest(self.tile_bytes(PROTECTED_TILES)), self.protected)
        self.ready()

    def coexistence(self):
        self.tap("Right", 2); self.ready()
        before = self.r(prototype.BOMBS)
        self.tap("Y", 1)
        self.until(lambda: self.r(0x7E07F1) != 0, "Coexistence Bombchu did not spawn", 24)
        chu = self.r(0x7E07F1) - 1
        self.equip(0x04)  # Menu pauses travel while the ordinary bomb is selected.
        self.tap("Y", 1)
        self.until(lambda: len(self.ancilla(7)) == 2, "Two-bomb coexistence was not reached", 24)
        other = next(s for s in self.ancilla(7) if s != chu)
        self.check("Coexistence keeps Bombchu ownership", self.r(0x7E07F1), chu + 1)
        self.check("Coexistence keeps Bombchu travelling", self.r(0x7E0C5E + chu), 0)
        native.require(self.r(0x7E03EA + other) != 0xBC, "Ordinary bomb adopted Bombchu signature")
        self.check("Coexistence draws both world sprites", [bool(self.oam(0x2E)), bool(self.oam(0x6E))], [True, True])
        self.check("Coexistence debits two bombs", self.r(prototype.BOMBS), before - 2)
        self.check("Coexistence preserves arrow/bomb tiles", native.digest(self.tile_bytes(PROTECTED_TILES)), self.protected)
        self.shot("bombchu-and-ordinary-bomb")
        self.advance("Left", 18); self.advance("", 2)
        self.until(lambda: not self.ancilla(7), "Coexisting bombs did not finish", 300)
        self.check("Coexistence clears Bombchu ownership", self.r(0x7E07F1), 0)
        self.check("Coexistence lifetime costs two bombs", self.r(prototype.BOMBS), before - 2)
        self.ready()

    def run(self):
        self.result["scope"] = describe()
        self.result["scope"]["native_executed"] = True
        self.ready()
        native.require(self.r(0x7E0010) in (7, 9) and self.r(0x7E02B2) in (0, 6)
                       and not self.r(0x7E0055) and not self.ancilla(7), "Need ordinary Link without active bombs")
        native.require(self.r(prototype.menu.HP) >= 24, "Need at least three hearts for damage-on checks")
        start = native.pc_offset(self.symbol("BombchuWorldGfx"))
        self.frames = [self.rom[start + i * 128:start + (i + 1) * 128] for i in range(4)]
        native.require(all(len(f) == 128 and any(f) for f in self.frames)
                       and len(set(self.frames)) == 4, "Need four distinct nonblank world frames")
        self.write(0x7EF3AD, 1, "Declared Bombchu ownership")
        self.write(prototype.BOMBS, 30, "Declared shared bomb ammunition")
        self.equip(0x1C)
        self.protected = native.digest(self.tile_bytes(PROTECTED_TILES))
        for direction in range(4):
            self.cast(direction)
        self.coexistence()
        self.equip(0x04)
        before = self.r(prototype.BOMBS)
        self.tap("Y", 1)
        self.until(lambda: bool(self.ancilla(7)), "Ordinary bomb did not spawn", 24)
        self.check("Ordinary bomb has no Bombchu owner", self.r(0x7E07F1), 0)
        native.require(all(self.r(0x7E03EA + s) != 0xBC for s in self.ancilla(7)),
                       "Ordinary bomb acquired Bombchu signature")
        self.check("Ordinary bomb keeps tile6E", bool(self.oam(0x6E)), True)
        self.check("Ordinary bomb does not draw Bombchu", self.oam(0x2E), [])
        self.shot("ordinary-bomb-control")
        self.advance("Left", 18); self.advance("", 2)
        self.until(lambda: not self.ancilla(7), "Ordinary bomb did not finish", 260)
        self.check("Ordinary bomb one ammunition debit", self.r(prototype.BOMBS), before - 1)
        self.check("Final protected arrow/bomb tiles", native.digest(self.tile_bytes(PROTECTED_TILES)), self.protected)
        self.result["runtime_checks_passed"] = True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute-fixtures", action="store_true")
    parser.add_argument("--session", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    if args.describe:
        print(json.dumps(describe(), indent=2)); return 0
    native.require(args.execute_fixtures and args.session and args.output, "Need --execute-fixtures, --session and --output")
    values = json.loads(args.session.read_text())
    for key in ("status_file", "owner_file", "owned_rom", "symbols", "client_root"):
        values[key] = Path(values[key])
    values["output"] = args.output
    identity = SimpleNamespace(**values)
    native.require(identity.socket.startswith("/tmp/mesen2-bombchu-world-")
                   and identity.owner.startswith("codex-bombchu-world-") and "oos-rc-play" not in str(values),
                   "Only the owned Bombchu world-art session is admitted")
    native.require(native.digest(identity.owned_rom.read_bytes()) == identity.rom_sha256, "ROM hash differs")
    native.require(native.digest(identity.symbols.read_bytes()) == identity.symbols_sha256, "Symbols hash differs")
    identity.rom_sha1 = native.digest(identity.owned_rom.read_bytes(), "sha1")
    command = subprocess.check_output(["ps", "-o", "command=", "-p", str(identity.pid)], text=True)
    native.require("--headless" in command and str(identity.owned_rom) in command, "PID is not the private ROM process")
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(identity.client_root))
    from mesen2_client_lib.bridge import MesenBridge
    flow = BombchuArtFlow(identity, MesenBridge(identity.socket, auto_reconnect=False, max_retries=0))
    flow.result["inputs"] = values
    admitted = False
    try:
        flow.check_owner()
        native.require(flow.paused() and not flow.b.list_breakpoints(), "Need paused private session without breakpoints")
        admitted = True
        flow.run()
    except Exception as error:
        flow.result["error"] = repr(error)
    finally:
        if admitted:
            try:
                flow.check_owner(); flow.input(""); flow.b.pause()
            except Exception as error:
                flow.result["cleanup_errors"].append(repr(error))
        flow.result["passed"] = bool(flow.result.get("runtime_checks_passed") and not flow.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(flow.result, indent=2, default=str) + "\n")
    print(json.dumps(dict(passed=flow.result["passed"], result=str(args.output / "RESULT.json"))))
    return 0 if flow.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
