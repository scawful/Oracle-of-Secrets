#!/usr/bin/env python3
"""Attach-only Maple graphics readback; caller owns boot, entry and cleanup.

The probe never launches/stops Mesen, loads states, warps, or writes game memory.
It requires an explicit owned headless PID/socket and a paused, freshly loaded
room. Optional controller-only door traversal is bounded and records every
advance. A phase label does not establish how the caller entered or saved.
Use --describe for an offline plan without connecting to an emulator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def number(value):
    return int(value, 0) if isinstance(value, str) else int(value)


def plan():
    return {
        "scope": "native loader state and rendered room; no gameplay/save proof by phase name",
        "entry": {"room": "000F", "entrance": "68", "main": 3, "secondary": 3},
        "control": {"room": "011C", "entrances": ["53", "54"],
                    "main": 3, "secondary": 3,
                    "bg_sheets": [0x61, 1, 0x13, 7, 0x0E, 0x23, 0x1C, 0x0F]},
        "reads": {"bg_vram_bytes": "4000..7FFF", "palette_target": "7EC300..7EC4FF",
                  "palette_current": "7EC500..7EC6FF", "cgram": "0000..01FF"},
        "animation": "Native DMA bytes7600..79FF (32 tiles) compare to WRAM source$0ADC; other480 compare to profile",
        "phases": ["fresh entrance68", "controller exit and return",
                   "trader11C against original sheets/control palette", "new-process reopen and fresh entrance68"],
        "fixtures": "Caller records SRAM source and entrance-loader fixture writes; do not load historical graphics states.",
        "cold_reopen": "Caller saves normally and launches a new owned PID; this probe only reads the resulting room.",
    }


def read_bundle(path):
    """Hash every expected payload before trusting compiler metadata."""
    data = json.loads((path / "bundle.json").read_text())
    require(data["schema_version"] == 1, "Unsupported graphics bundle schema")
    files = {}
    for name, meta in data["files"].items():
        target = (path / name).resolve()
        require(target.is_relative_to(path.resolve()), "Bundle path escapes output directory")
        blob = target.read_bytes()
        require(len(blob) == meta["bytes"] and sha(blob) == meta["sha256"],
                f"Bundle payload changed: {name}")
        files[name] = blob
    require({entry["slot"] for entry in data["sheets"]} == set(range(8)),
            "Native probe requires all eight expected BG slots")
    require(all(len(files[entry["vram"]]) == 0x800 for entry in data["sheets"]),
            "Expected BG payload must be 2048 bytes per slot")
    require(all(len(files[entry["file"]]) == 30 for entry in data["palette_rows"]),
            "Expected palette row must contain colors 1..15")
    return data, files


def mismatches(actual, expected, unit=1):
    require(len(actual) == len(expected), "Comparison length mismatch")
    return [i // unit for i in range(0, len(expected), unit)
            if actual[i:i + unit] != expected[i:i + unit]]


class Probe:
    def __init__(self, args, bridge, bundle, files):
        self.a, self.b, self.bundle, self.files = args, bridge, bundle, files
        self.deadline = time.monotonic() + 120
        self.result = {"passed": False, "phase": args.phase, "captures": [],
                       "frame_advances": [], "fixture_writes": [], "cleanup_errors": [],
                       "scope": plan()["scope"], "setup_disclosure": args.setup_disclosure,
                       "palette_assertions": not args.skip_palette,
                       "inputs": vars(args), "source_sha256": sha(Path(__file__).read_bytes())}

    def guard(self, connected=True):
        require(time.monotonic() < self.deadline, "120-second probe deadline exceeded")
        raw = self.a.owner_file.read_text().strip()
        try:
            owner = json.loads(raw)["owner"]
        except (ValueError, KeyError, TypeError):
            owner = next((s.split("=", 1)[1] for s in raw.splitlines()
                          if s.startswith("owner=")), raw)
        require(owner == self.a.owner, "Heavy-lock owner changed")
        status = json.loads(self.a.status_file.read_text())
        require(number(status["pid"]) == self.a.pid, "Status PID mismatch")
        require(status["socketPath"] == self.a.socket, "Status socket mismatch")
        require(str(status["romHash"]).lower() == self.a.rom_sha1.lower(), "Status ROM mismatch")
        os.kill(self.a.pid, 0)
        command = subprocess.check_output(["ps", "-p", str(self.a.pid), "-o", "command="], text=True)
        require("--headless" in command and str(self.a.owned_rom.resolve()) in command,
                "PID is not the specified owned headless ROM process")
        if connected:
            info = self.b.get_rom_info()
            require(str(info.get("sha1", "")).lower() == self.a.rom_sha1.lower(), "Loaded ROM mismatch")
            return info

    def paused(self):
        reply = self.b.send_command("STATE")
        require(reply.get("success"), "STATE rejected")
        data = reply.get("data", {})
        if isinstance(data, str):
            data = json.loads(data)
        require("paused" in data, "Unknown native pause state")
        return data["paused"] is True

    def block(self, address, size, memtype=None):
        blob = bytearray()
        for offset in range(0, size, 0x1000):
            count = min(0x1000, size - offset)
            chunk = bytes(self.b.read_block(address + offset, count, memtype))
            require(len(chunk) == count, f"Short {memtype or 'bus'} read {address + offset:06X}+{count:X}")
            blob.extend(chunk)
        return bytes(blob)

    def where(self):
        ram = self.block(0x7E0000, 0xB00)
        word = lambda a: int.from_bytes(ram[a:a + 2], "little")
        return dict(module=ram[0x10], submodule=ram[0x11], indoors=ram[0x1B],
                    room=word(0xA0), entrance=word(0x10E), main=ram[0xAA1], secondary=ram[0xAA2],
                    brightness=ram[0x13], x=word(0x22), y=word(0x20),
                    x_local=word(0x22) & 511, y_local=word(0x20) & 511,
                    link_state=ram[0x5D], doorway=ram[0x6C],
                    animation_vram_word=word(0x134), animation_source=word(0xADC))

    def input(self, buttons):
        require(self.b.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"}).get("success"),
                "Controller INPUT rejected")

    def advance(self, frames, buttons=""):
        info = self.guard()
        require(self.paused(), "Frame advance requires paused CPU")
        require(1 <= frames <= 120, "Advance must be 1..120 frames")
        self.input(buttons)
        before = number(info["frameCount"])
        require(self.b.send_command("FRAME", {"count": str(frames)}).get("success"), "FRAME rejected")
        until = min(self.deadline, time.monotonic() + 8)
        while time.monotonic() < until:
            after = number(self.b.get_rom_info()["frameCount"])
            if after >= before + frames and self.paused():
                require(after <= before + frames + 1, "Unexpected frame overshoot")
                self.input("")
                self.result["frame_advances"].append(dict(buttons=buttons, requested=frames,
                                                          before=before, after=after, state=self.where()))
                return
            time.sleep(0.01)
        raise RuntimeError("Bounded FRAME timed out")

    def capture(self, name, expected_room=None, compare=True):
        info = self.guard()
        require(self.paused(), "Capture requires paused CPU")
        state = self.where()
        entry = dict(name=name, frame=number(info["frameCount"]), state=state, checks=[])
        self.result["captures"].append(entry)
        image = self.b.screenshot()
        require(image and image.startswith(b"\x89PNG"), "Native PNG screenshot missing")
        (self.a.output / f"{name}.png").write_bytes(image)
        blocks = {"bg-vram": self.block(0x4000, 0x4000, "SnesVideoRam"),
                  "palette-target": self.block(0x7EC300, 0x200),
                  "palette-current": self.block(0x7EC500, 0x200),
                  "cgram": self.block(0, 0x200, "SnesCgRam"),
                  "tilemap-2000": self.block(0x7E2000, 0x2000),
                  "tilemap-4000": self.block(0x7E4000, 0x2000)}
        if compare:
            # NMI $008B50..64 uploads exactly 0x400 bytes, not 0x200.
            # The native timer selects one of three frames at $7EA680+$400*n.
            require(state["animation_vram_word"] == 0x3B00 and
                    state["animation_source"] in (0xA680, 0xAA80, 0xAE80),
                    "Unexpected native animation destination/source")
            blocks["animation-source"] = self.block(0x7E0000 | state["animation_source"], 0x400)
        entry["files"] = {}
        for kind, blob in blocks.items():
            filename = f"{name}-{kind}.bin"
            (self.a.output / filename).write_bytes(blob)
            entry["files"][kind] = dict(file=filename, bytes=len(blob), sha256=sha(blob))
        if expected_room is not None:
            require((state["module"], state["submodule"], state["indoors"], state["room"]) ==
                    (7, 0, 1, expected_room), "Capture is not stable gameplay in expected room")
            require(state["entrance"] == self.a.expected_entrance, "Unexpected entrance context")
        if compare:
            ctx = self.bundle["context"]
            require((state["main"], state["secondary"]) == (ctx["main_blockset"], ctx["room_blockset"]),
                    "Graphics context differs from expected bundle")
            require(state["brightness"] == 15, "Room fade has not settled to full brightness")
            for sheet in self.bundle["sheets"]:
                slot = sheet["slot"]
                bad = mismatches(blocks["bg-vram"][slot * 0x800:(slot + 1) * 0x800],
                                 self.files[sheet["vram"]], 32)
                dynamic = [tile for tile in range(64)
                           if 0x7600 <= 0x4000 + slot * 0x800 + tile * 32 < 0x7A00]
                bad = [tile for tile in bad if tile not in dynamic]
                entry["checks"].append(dict(kind="sheet", slot=slot, mismatching_tiles=bad,
                                            animation_tiles_compared_separately=dynamic, passed=not bad))
            bad = mismatches(blocks["bg-vram"][0x3600:0x3A00], blocks["animation-source"], 32)
            entry["checks"].append(dict(kind="animation-upload", start_byte=0x7600, bytes=0x400,
                                        source=0x7E0000 | state["animation_source"],
                                        mismatching_tiles=bad, passed=not bad))
            if not self.a.skip_palette:
                for row in self.bundle["palette_rows"]:
                    offset = row["row"] * 32 + 2
                    expected = self.files[row["file"]]
                    for kind in ("palette-target", "palette-current", "cgram"):
                        bad = mismatches(blocks[kind][offset:offset + 30], expected, 2)
                        entry["checks"].append(dict(kind=kind, row=row["row"],
                                                    mismatching_colors=[n + 1 for n in bad], passed=not bad))
            require(all(check["passed"] for check in entry["checks"]), "Graphics/palette readback differs; see capture checks")
        entry["passed"] = True
        return entry

    def roundtrip(self):
        state = self.where()
        require(self.a.expected_room == 0xF and 368 <= state["x_local"] <= 384
                and 440 <= state["y_local"] <= 480,
                "Door roundtrip requires fresh Maple south-door entry position")
        for _ in range(24):
            self.advance(8, "Down")
            s = self.where()
            if s["module"] == 9 and s["submodule"] == 0 and s["indoors"] == 0:
                break
        else:
            raise RuntimeError("Controller exit did not reach stable overworld within 192 frames")
        self.advance(8)
        self.capture("outside", compare=False)
        for _ in range(30):
            self.advance(8, "Up")
            s = self.where()
            if (s["module"], s["submodule"], s["indoors"], s["room"]) == (7, 0, 1, 0xF):
                break
        else:
            raise RuntimeError("Controller return did not reach Maple within 240 frames; inspect outside placement")
        self.advance(8)
        self.capture("return", 0xF)


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--describe", action="store_true")
    parser.add_argument("--execute", action="store_true")
    for key in ("socket", "rom-sha256", "rom-sha1", "owner", "phase", "setup-disclosure"):
        parser.add_argument("--" + key)
    for key in ("status-file", "owned-rom", "client-root", "owner-file", "output", "bundle"):
        parser.add_argument("--" + key, type=Path)
    parser.add_argument("--pid", type=int)
    parser.add_argument("--expected-room", type=lambda s: int(s, 0), default=0xF)
    parser.add_argument("--expected-entrance", type=lambda s: int(s, 0), default=0x68)
    parser.add_argument("--settle-frames", type=int, default=8)
    parser.add_argument("--skip-palette", action="store_true",
                        help="Sheet-only control; palettes still captured, not asserted")
    parser.add_argument("--door-roundtrip", action="store_true")
    return parser.parse_args()


def main():
    args = parse_args()
    if args.describe:
        print(json.dumps(plan(), indent=2))
        return 0
    require(args.execute, "Native connection requires --execute")
    for key in ("socket", "rom_sha256", "rom_sha1", "owner", "phase", "setup_disclosure",
                "status_file", "owned_rom", "client_root", "owner_file", "output", "bundle", "pid"):
        require(getattr(args, key), f"Missing --{key.replace('_', '-')}")
    require(args.pid > 0 and 1 <= args.settle_frames <= 120, "Invalid PID/frame bound")
    rom = args.owned_rom.read_bytes()
    require(sha(rom) == args.rom_sha256.lower(), "Private ROM SHA256 mismatch")
    require(hashlib.sha1(rom).hexdigest() == args.rom_sha1.lower(), "Private ROM SHA1 mismatch")
    require(rom[0xB5C:0xB5F] == bytes.fromhex("A20004"), "Native animation DMA size changed")
    bundle, files = read_bundle(args.bundle)
    probe = Probe(args, None, bundle, files)
    probe.guard(connected=False)
    args.output.mkdir(parents=True, exist_ok=False)
    sys.path.insert(0, str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    probe.b = MesenBridge(args.socket, auto_reconnect=False, max_retries=0)
    owned = False
    try:
        probe.guard()
        require(probe.paused(), "Caller must supply paused private session")
        require(not probe.b.list_breakpoints(), "Existing breakpoints; refuse shared debugger")
        owned = True
        probe.advance(args.settle_frames)
        probe.capture("initial", args.expected_room)
        if args.door_roundtrip:
            probe.roundtrip()
        probe.result["checks_passed"] = True
    except Exception as error:
        probe.result["error"] = repr(error)
    finally:
        if owned:
            try:
                probe.guard()
                probe.input("")
                require(probe.b.pause(), "Owned final pause rejected")
            except Exception as error:
                probe.result["cleanup_errors"].append(repr(error))
        if sha(args.owned_rom.read_bytes()) != args.rom_sha256.lower():
            probe.result["cleanup_errors"].append("Private ROM changed")
        probe.result["passed"] = bool(probe.result.get("checks_passed") and not probe.result["cleanup_errors"])
        (args.output / "RESULT.json").write_text(json.dumps(probe.result, indent=2, default=str) + "\n")
    print(json.dumps({"passed": probe.result["passed"], "result": str(args.output / "RESULT.json")}))
    return 0 if probe.result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
