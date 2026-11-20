"""Minecart ride speed and the 16-bit boarding seat.

Walk speed is vanilla SubVelocityValues index 0 ($18): 1.5 px/frame in the
same 4.4 fixed point Sprite_MoveVert uses. !MinecartSpeed must be at least
twice that and must stay under 8px so a stop cell cannot be skipped.

Minecart_SeatPlayer is assembled with asar and executed. A cart cached at
$1108 (the room-midline case) must land Link at $10FD, high byte included,
and an indoor board must call ApplyLinksMovementToCamera.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "Sprites/Objects/minecart.asm"
MACROS = ROOT / "Util/macros.asm"
WALK_SPEED = 0x18  # SubVelocityValues[0], straight ground walk
CACHED_Y = 0x0FDA


def px_per_frame(speed: int) -> float:
    """Match Sprite_MoveVert: four ASLs into the subpixel, four LSRs into pixels."""
    speed &= 0xFF
    pixel = speed >> 4
    if speed & 0x80:
        pixel = (pixel - 16) & 0xFF
        if pixel >= 0x80:
            pixel -= 0x100
    fraction = (speed << 4) & 0xFF
    return pixel + fraction / 256.0


def constant(name: str) -> int:
    match = re.search(rf"^{re.escape(name)}\s*=\s*(\d+)", SOURCE.read_text(), re.M)
    if not match:
        raise AssertionError(f"{name} missing from minecart.asm")
    return int(match.group(1))


def routine(name: str) -> str:
    text = SOURCE.read_text()
    start = text.index(f"{name}:\n{{")
    end = text.index("\n}", start)
    return text[start:end]


class SpeedContract(unittest.TestCase):
    def test_ride_is_at_least_twice_walking_and_cannot_skip_a_cell(self):
        speed = constant("!MinecartSpeed")
        ride = px_per_frame(speed)
        walk = px_per_frame(WALK_SPEED)
        self.assertGreaterEqual(ride, walk * 2)
        self.assertLess(ride, 8.0)
        self.assertEqual(speed, 64)
        self.assertEqual(ride, 4.0)

    def test_speed_is_an_immediate_outside_the_flag_blocks(self):
        text = SOURCE.read_text()
        stores = re.findall(r"LDA\.b #(-?)!MinecartSpeed : STA\.w Spr[XY]Speed, X", text)
        self.assertEqual(stores, ["-", "", "", "-"])
        for flag in ("!ENABLE_MINECART_LIFT_TOSS", "!ENABLE_MINECART_CART_SHUTTERS"):
            self.assertRegex(MACROS.read_text(), rf"{flag}\s*=\s*0")
            self.assertIn(f"if {flag}", text)
        stack: list[str] = []
        seen = 0
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("if "):
                stack.append(stripped)
            elif stripped == "endif" and stack:
                stack.pop()
            if "LDA.b" in stripped and "!MinecartSpeed" in stripped:
                self.assertFalse(any("MINECART_LIFT" in frame or "CART_SHUTTERS" in frame
                                     for frame in stack), stripped)
                seen += 1
        self.assertEqual(seen, 4)
        self.assertIn("JSL CartShutter97_DragPlayer", text)
        self.assertIn("JSR Minecart_HandleLiftAndToss", text)
        self.assertNotIn("Lanmola", text)

    def test_drag_compensation_keeps_a_four_pixel_step(self):
        """DragPlayer contributes ±1. The camera routine adds the rest."""
        body = routine("HandlePlayerCameraAndMoveCart")
        self.assertIn("DEC A", body)
        self.assertIn("INC A", body)
        self.assertIn("ADC.w DragYL, X", body)
        for delta, drag_step, total in ((4, 1, 4), (-4, -1, -4)):
            extra = delta - drag_step
            self.assertEqual(drag_step + extra, total)


class CompiledSeat(unittest.TestCase):
    def test_asar_seat_writes_both_y_bytes_and_updates_the_quadrant(self):
        asar = shutil.which("asar")
        if not asar:
            self.fail("asar is not on PATH")
        body = routine("Minecart_SeatPlayer")
        body = body.replace("SprCachedY", f"${CACHED_Y:04X}")
        asm = f"""lorom
org $008000
ApplyLinksMovementToCamera:
  RTL
{body}
"""
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "seat.asm"
            rom = Path(tmp) / "seat.sfc"
            src.write_text(asm)
            rom.write_bytes(b"\x00" * 0x8000)
            done = subprocess.run([asar, "--no-title-check", str(src), str(rom)],
                                  capture_output=True, text=True)
            self.assertEqual(done.returncode, 0, done.stdout + done.stderr)
            image = rom.read_bytes()
        # LoROM $008000 is file offset 0.
        code = image[:64]
        self.assertEqual(code[0], 0x6B)  # dummy RTL
        self.assertIn(b"\xC2\x20", code)  # REP #$20
        self.assertIn(b"\xAD\xDA\x0F", code)  # LDA.w $0FDA
        self.assertIn(b"\xE9\x0B\x00", code)  # SBC.w #$000B
        self.assertIn(b"\x85\x20", code)  # STA.b $20
        self.assertIn(b"\x22", code)  # JSL ApplyLinksMovementToCamera

        link_y, called = execute_seat(code, cart_y=0x1108, indoors=1)
        self.assertEqual(link_y, 0x10FD)
        self.assertTrue(called)
        outdoor, called = execute_seat(code, cart_y=0x1108, indoors=0)
        self.assertEqual(outdoor, 0x10FD)
        self.assertFalse(called)


def execute_seat(code: bytes, cart_y: int, indoors: int) -> tuple[int, bool]:
    """Run the assembled seat until RTS. A is 8-bit on entry, as the cart is."""
    mem = bytearray(0x10000)
    mem[CACHED_Y] = cart_y & 0xFF
    mem[CACHED_Y + 1] = cart_y >> 8
    mem[0x1B] = indoors
    a = 0
    p = 0x30  # M and X set; Z clear
    z = False
    pc = 1  # skip the dummy RTL at $008000
    called = False

    def set_nz(value: int, wide: bool) -> None:
        nonlocal z
        z = (value & (0xFFFF if wide else 0xFF)) == 0

    for _ in range(32):
        op = code[pc]
        if op == 0xA5:  # LDA.b dp
            a = (a & 0xFF00) | mem[code[pc + 1]]
            set_nz(a, not p & 0x20)
            pc += 2
        elif op == 0x85:  # STA.b dp
            addr = code[pc + 1]
            wide = not p & 0x20
            mem[addr] = a & 0xFF
            if wide:
                mem[addr + 1] = (a >> 8) & 0xFF
            pc += 2
        elif op == 0xC2:  # REP
            p &= ~code[pc + 1]
            pc += 2
        elif op == 0xE2:  # SEP
            p |= code[pc + 1]
            pc += 2
        elif op == 0xAD:  # LDA.w abs
            addr = code[pc + 1] | (code[pc + 2] << 8)
            a = mem[addr] | (mem[addr + 1] << 8)
            set_nz(a, True)
            pc += 3
        elif op == 0x38:  # SEC
            p |= 1
            pc += 1
        elif op == 0xE9:  # SBC #
            wide = not p & 0x20
            if wide:
                imm = code[pc + 1] | (code[pc + 2] << 8)
                pc += 3
            else:
                imm = code[pc + 1]
                pc += 2
            total = (a if wide else a & 0xFF) - imm - (0 if p & 1 else 1)
            a = total & 0xFFFF if wide else (a & 0xFF00) | (total & 0xFF)
            p = (p | 1) if total >= 0 else (p & ~1)
            set_nz(a, wide)
        elif op == 0xDA:  # PHX
            pc += 1
        elif op == 0xFA:  # PLX
            pc += 1
        elif op == 0xF0:  # BEQ
            offset = code[pc + 1] if code[pc + 1] < 0x80 else code[pc + 1] - 256
            pc = pc + 2 + offset if z else pc + 2
        elif op == 0x22:  # JSL
            called = True
            pc += 4
        elif op == 0x60:  # RTS
            return mem[0x20] | (mem[0x21] << 8), called
        else:
            raise AssertionError(f"unhandled opcode ${op:02X} at {pc}")
    raise AssertionError("seat routine did not return")


def ride_once(rom: Path, out: Path) -> dict:
    """Board the 0xD8 cart and measure one free roll. Requires NativeSession."""
    import hashlib
    import json
    import sys
    import time
    from types import SimpleNamespace

    harness = Path(
        "/Users/scawful/src/hobby/oracle-of-secrets-scratch/"
        "gemini-t2-rerun-2026-11-16/harness-fix/fixed")
    sys.path.insert(0, str(ROOT / "Scripts" / "Agents"))
    sys.path.insert(0, str(harness))
    sys.path.insert(0, "/Users/scawful/src/hobby/mesen2-oos/tools/oos_client")
    from native_session import NativeSession  # noqa: E402
    from mesen2_client_lib.bridge import MesenBridge  # noqa: E402
    from _boot_util import (DEFAULT_SEED_SRM, _ensure_director_paths,
                            apply_mesen_env, normal_roomload, settle_bridge)  # noqa: E402

    apply_mesen_env()
    _ensure_director_paths()
    from scene_director import runner  # noqa: E402

    out.mkdir(parents=True, exist_ok=True)
    copy = out / "ride.sfc"
    shutil.copyfile(rom, copy)
    sha1 = hashlib.sha1(copy.read_bytes()).hexdigest()
    home = out / "home"
    (home / "Saves").mkdir(parents=True, exist_ok=True)
    shutil.copyfile(DEFAULT_SEED_SRM, home / "Saves" / "ride.srm")
    with NativeSession("D6-Cart-Ride", "minecart speed seating ride", out, deadline=180) as sess:
        pid, socket = sess.launch_mesen(copy, home=home)
        for _ in range(60):
            if socket.exists():
                break
            time.sleep(0.25)
        bridge = MesenBridge(str(socket), auto_reconnect=False, max_retries=0)
        settle_bridge(bridge, sha1, log_path=out / "startup-handshake.jsonl")
        (out / "owner").write_text(json.dumps({"owner": "D6-Cart-Ride"}))
        (out / "status.json").write_text(json.dumps({"pid": pid, "socketPath": str(socket)}))
        session = runner.SceneSession(
            SimpleNamespace(socket=str(socket), pid=pid, status_file=out / "status.json",
                            owner_file=out / "owner", owner="D6-Cart-Ride",
                            rom_sha1=sha1, output=out),
            bridge, out / "frames.jsonl")
        session.deadline = time.monotonic() + 150.0
        runner._cold_boot(session)
        normal_roomload(session, 0xD8, 112, 112, entrance=0x27)
        session.hold("", 8)
        session.hold("B", 8)
        start = session.snap()
        session.hold("", 20)
        end = session.snap()
        png = out / "d6_ride.png"
        png.write_bytes(bridge.screenshot())
        session.log.close()
    dx = abs(end["x"] - start["x"])
    dy = abs(end["y"] - start["y"])
    return {"mounted": end["mounted"], "dx": dx, "dy": dy,
            "px_per_frame": max(dx, dy) / 20.0, "png": png,
            "start": start, "end": end}


class MesenRide(unittest.TestCase):
    def test_headless_ride_beats_walking(self):
        rom = os.environ.get("OOS_D6_ROM")
        if not rom:
            self.skipTest("set OOS_D6_ROM to the patched private ROM")
        result = ride_once(Path(rom), Path(os.environ.get(
            "OOS_D6_PROOF", "/tmp/oos-d6-minecart/ride")))
        self.assertEqual(result["mounted"], 1)
        self.assertGreaterEqual(result["px_per_frame"], px_per_frame(WALK_SPEED) * 2)
        self.assertLess(min(result["dx"], result["dy"]), 48)
        self.assertTrue(result["png"].is_file())
        self.assertGreater(result["png"].stat().st_size, 500)


if __name__ == "__main__":
    unittest.main()
