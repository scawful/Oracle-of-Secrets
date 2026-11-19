#!/usr/bin/env python3
"""T2 live headless Mesen2-OOS proof for Special Overworld / Sky Travel Bird
pickup, Mode 7 Lyra Sea Map Pin 8 ($8C Sky Spire) drop-off, Sky Tower ($87)
BG1 cloud overlay priority + B-cancel, and full-ancilla slot-4 eviction + X-cancel.

Never touches shared Roms/, live .yazeproj/rom, or GUI Mesen instances.
Copies the candidate ROM into a private temp directory and runs under
Scripts/Agents/native_session.py (heavy_lock + owned-PID teardown).
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import sys
import time

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path.home() / "src/hobby/oracle-of-secrets-scratch"
DEFAULT_SEED = SCRATCH / "claude-d8-boss-20261116/fixture.srm"

sys.path.insert(0, str(REPO / "Scripts/Agents"))
sys.path.insert(0, "/Users/scawful/src/hobby/mesen2-oos/tools/oos_client")
os.environ.setdefault("MESEN2_OOS_ROOT", "/Users/scawful/src/hobby/mesen2-oos")

from native_session import NativeSession  # noqa: E402
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402

MOD = 0x7E0010
SUB = 0x7E0011
BRIGHT = 0x7E0013
AREA = 0x7E008A
ROOM = 0x7E00A0
LINK_Y = 0x7E0020
LINK_X = 0x7E0022

# Verified $32-byte native cached-exit record for Royal Garrison ($83).
CACHE_83 = [
    0x0083, 0x0016, 0x00F0, 0x0688, 0x0140, 0x0700, 0x0083, 0x0790,
    0x015F, 0x0707, 0x0000, 0x031E, 0x0600, 0x0700, 0xFF20, 0x0400, 0x0500, 0x0800,
    0x2000, 0x0E24, 0x0000, 0x0000, 0x0000, 0x0000, 0x0000,
]


def is_paused(b: MesenBridge) -> bool:
    reply = b.send_command("STATE")
    if not reply.get("success"):
        return False
    data = reply.get("data", {})
    if isinstance(data, str):
        data = json.loads(data)
    return data.get("paused") is True


def pause_wait(b: MesenBridge, timeout: float = 5.0) -> None:
    if is_paused(b):
        return
    b.pause()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if is_paused(b):
            return
        time.sleep(0.01)
    raise RuntimeError("Timed out waiting for Mesen2 pause")


def frame_count(b: MesenBridge) -> int:
    val = b.get_rom_info().get("frameCount", 0)
    return int(val, 0) if isinstance(val, str) else int(val)


def step_frames(b: MesenBridge, count: int = 1, buttons: str = "") -> None:
    pause_wait(b)
    r_in = b.send_command("INPUT", {"buttons": buttons, "frames": "0", "player": "0"})
    assert r_in.get("success"), f"INPUT({buttons!r}) rejected: {r_in}"
    before = frame_count(b)
    r_fr = b.send_command("FRAME", {"count": str(count)})
    assert r_fr.get("success"), f"FRAME({count}) rejected: {r_fr}"
    end = time.monotonic() + max(6.0, count / 10.0)
    while time.monotonic() < end:
        if frame_count(b) >= before + count and is_paused(b):
            break
        time.sleep(0.005)
    else:
        raise RuntimeError(f"FRAME({count}) timed out at {frame_count(b)} (wanted {before + count})")
    if buttons:
        b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})


def tap_button(b: MesenBridge, button: str, hold: int = 4, settle: int = 10) -> None:
    step_frames(b, 2)
    step_frames(b, hold, button)
    step_frames(b, settle)


def wait_until(b: MesenBridge, pred, max_frames: int, step: int, label: str) -> int:
    spent = 0
    while spent < max_frames:
        if pred():
            return spent
        chunk = min(step, max_frames - spent)
        step_frames(b, chunk)
        spent += chunk
    if pred():
        return spent
    raise RuntimeError(
        f"Timeout awaiting {label}: mod={b.read_memory(MOD):02X} "
        f"sub={b.read_memory(SUB):02X} br={b.read_memory(BRIGHT):02X} "
        f"area={b.read_memory(AREA):02X}"
    )


def bird_oam(b: MesenBridge) -> list[tuple[int, int, int, int, int]]:
    """Return active Travel Bird OAM entries (tile $0E, on-screen Y < $E8)."""
    oam = b.read_block(0x7E0800, 512)
    out = []
    for i in range(128):
        x, y, tile, prop = oam[i * 4 : i * 4 + 4]
        if y < 0xE8 and tile == 0x0E:
            out.append((i, x, y, tile, prop))
    return out


def snap_bytes(b: MesenBridge) -> bytes:
    png = b.screenshot()
    assert png and png.startswith(b"\x89PNG"), "Invalid PNG from Mesen2"
    return png


def arm_soaring_state(b: MesenBridge) -> None:
    for i in range(5):
        b.write_memory(0x7E0C4A + i, 0)
    for addr in (
        0x7E004B, 0x7E005D, 0x7E02DA, 0x7E02E4, 0x7E037B, 0x7E02F9,
        0x7E037A, 0x7E03F0, 0x7E0FC1, 0x7E0200, 0x7EC13E, 0x7E02B2,
        0x7E0300, 0x7E0301, 0x7E0308, 0x7E037E, 0x7E03EF, 0x7E003A,
        0x7E0345, 0x7E0351,
    ):
        b.write_memory(addr, 0)
    b.write_memory(0x7EF3C5, 0x02)  # Post-intro peacetime
    b.write_memory(0x7EE000, 12)    # Noon daytime
    b.write_memory(0x7EE00E, 0)     # Clear weather
    b.write_memory(0x7EF3CA, 0)     # Light/Special Overworld
    b.write_memory(0x7E0FFF, 0)
    b.write_memory(0x7EF3CC, 0)     # No follower
    b.write_memory(0x7EF34C, 6)     # Ocarina with all songs
    b.write_memory(0x7EF3AB, 3)     # Saved song = Song of Soaring
    b.write_memory(0x7E030F, 3)     # Active song = Song of Soaring
    b.write_memory(0x7E0202, 0x0D)  # Ocarina on Y
    b.write_memory(0x7EF3B9, 1)     # Dual-bind v1: Y=Ocarina, X=empty
    b.write_memory(0x7EF3BA, 0x0D)
    b.write_memory(0x7EF3BB, 0x00)
    b.write_memory(0x7E02B3, 0x0D)
    b.write_memory(0x7EF3B2, 0xA5)  # SkySoaringLearned
    b.write_memory(0x7EF412, 0xFF)  # LW visited
    b.write_memory(0x7EF438, 0x7F)  # All 7 non-sky SW hubs visited


def warp_garrison_83(b: MesenBridge) -> None:
    pause_wait(b)
    arm_soaring_state(b)
    for i, w in enumerate(CACHE_83):
        b.write_memory16(0x7EC140 + i * 2, w)
    b.write_memory16(0x7E0696, 0)
    b.write_memory16(0x7E0698, 0)
    b.write_memory16(ROOM, 0x0151)
    b.write_memory(0x7E010A, 0)
    b.write_memory(0x7E04AA, 0)
    b.write_memory(BRIGHT, 0x80)
    b.write_memory(0x7E009B, 0)
    b.write_memory(SUB, 0)
    b.write_memory(0x7E00B0, 0)
    b.write_memory(MOD, 0x08)
    wait_until(
        b,
        lambda: b.read_memory(MOD) == 0x09 and b.read_memory(SUB) == 0 and b.read_memory(BRIGHT) == 0x0F,
        480, 4, "area $83",
    )
    step_frames(b, 8)
    assert b.read_memory(AREA) == 0x83, hex(b.read_memory(AREA))


def enter_sky_tower_87(b: MesenBridge) -> None:
    """Exit dungeon room $0090 onto Sky Tower ($87) with live BG1 clouds ($94)."""
    pause_wait(b)
    arm_soaring_state(b)
    b.write_memory(0x7E001B, 0x01)  # Indoors
    b.write_memory16(ROOM, 0x0090)  # Exit #66 -> Area $87
    b.write_memory(BRIGHT, 0x80)
    b.write_memory(SUB, 0)
    b.write_memory(0x7E00B0, 0)
    b.write_memory(MOD, 0x08)
    wait_until(
        b,
        lambda: b.read_memory(MOD) == 0x09 and b.read_memory(SUB) == 0 and b.read_memory(BRIGHT) == 0x0F,
        480, 4, "Sky Tower $87",
    )
    step_frames(b, 8)
    assert b.read_memory(AREA) == 0x87, hex(b.read_memory(AREA))
    assert b.read_memory(0x7E001D) == 0x01 and b.read_memory(0x7E008C) == 0x94, (
        hex(b.read_memory(0x7E001D)), hex(b.read_memory(0x7E008C))
    )


def assert_unlocked_and_walkable(b: MesenBridge, tag: str) -> None:
    locks = {
        "4B": b.read_memory(0x7E004B),
        "5D": b.read_memory(0x7E005D),
        "02DA": b.read_memory(0x7E02DA),
        "02E4": b.read_memory(0x7E02E4),
        "037B": b.read_memory(0x7E037B),
        "02F9": b.read_memory(0x7E02F9),
        "0FC1": b.read_memory(0x7E0FC1),
        "03F0": b.read_memory(0x7E03F0),
        "3A_bit6": b.read_memory(0x7E003A) & 0x40,
    }
    assert all(v == 0 for v in locks.values()), f"[{tag}] stuck locks: {locks}"
    y0, x0 = b.read_memory16(LINK_Y), b.read_memory16(LINK_X)
    step_frames(b, 16, "Down")
    y1, x1 = b.read_memory16(LINK_Y), b.read_memory16(LINK_X)
    assert (y1, x1) != (y0, x0), f"[{tag}] Link could not walk after sequence ({x0},{y0})"


def build_proof_strip(panels: list[tuple[str, bytes]], out_path: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont

    imgs = [Image.open(io.BytesIO(raw)).convert("RGB") for _, raw in panels]
    w, h = imgs[0].size
    cols, rows = 4, 2
    pad = 8
    header_h = 22
    title_h = 28
    canvas_w = cols * w + (cols + 1) * pad
    canvas_h = title_h + rows * (h + header_h) + (rows + 1) * pad
    canvas = Image.new("RGB", (canvas_w, canvas_h), (18, 22, 30))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 12)
        title_font = ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", 14)
    except OSError:
        font = ImageFont.load_default()
        title_font = font

    draw.text(
        (pad, 6),
        "Oracle of Secrets — Special Overworld / Sky Travel Bird Pickup & Drop-Off (Live Mesen2-OOS)",
        fill=(240, 245, 255),
        font=title_font,
    )
    for idx, ((label, _), im) in enumerate(zip(panels, imgs)):
        r, c = divmod(idx, cols)
        x0 = pad + c * (w + pad)
        y0 = title_h + pad + r * (h + header_h + pad)
        draw.rectangle([x0 - 1, y0 - 1, x0 + w, y0 + header_h + h], outline=(90, 110, 145))
        draw.rectangle([x0, y0, x0 + w - 1, y0 + header_h - 1], fill=(30, 38, 54))
        draw.text((x0 + 6, y0 + 4), label, fill=(235, 240, 255), font=font)
        canvas.paste(im, (x0, y0 + header_h))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--rom", type=Path, required=True, help="Candidate ROM with ENABLE_SPECIAL_OVERWORLD_SOARING=1")
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    ap.add_argument("--work", type=Path, default=Path("/tmp/sky-bird-native-work"))
    ap.add_argument("--proof-out", type=Path, default=None, help="Optional 8-panel proof strip PNG output path")
    ap.add_argument("--report-out", type=Path, default=None, help="Optional JSON report output path")
    args = ap.parse_args()

    shutil.rmtree(args.work, ignore_errors=True)
    args.work.mkdir(parents=True)
    test_rom = args.work / "oos168x.sfc"
    shutil.copy2(args.rom, test_rom)
    home = args.work / "home"
    (home / "Saves").mkdir(parents=True)
    shutil.copy2(args.seed, home / "Saves/oos168x.srm")

    panels: list[tuple[str, bytes]] = []
    report: dict = {"rom": str(args.rom), "rom_sha256": hashlib.sha256(args.rom.read_bytes()).hexdigest(), "checks": []}

    with NativeSession("special-soaring-bird", "Verify Sky/SW Travel Bird pickup & drop-off", args.work, deadline=300) as sess:
        _pid, sock = sess.launch_mesen(test_rom, home=home)
        for _ in range(80):
            if sock.exists():
                break
            time.sleep(0.25)
        assert sock.exists(), f"Mesen2 socket did not appear: {sock}"

        b = MesenBridge(str(sock), auto_reconnect=False, max_retries=0)
        assert b.ensure_connected(retries=15, delay=0.4)
        sha1 = hashlib.sha1(args.rom.read_bytes()).hexdigest().lower()
        for _ in range(100):
            if str(b.get_rom_info().get("sha1", "")).lower() == sha1:
                break
            time.sleep(0.1)
        pause_wait(b)
        for _ in range(50):
            if b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"}).get("success") and b.get_cpu_state():
                break
            time.sleep(0.1)
        step_frames(b, 1)

        # Boot through Title -> File Select -> Gameplay
        wait_until(
            b,
            lambda: (b.read_memory(MOD) == 0 and b.read_memory(SUB) == 8) or b.read_memory(MOD) in (1, 7, 9),
            2700, 16, "title",
        )
        if b.read_memory(MOD) == 0:
            tap_button(b, "Start", 4, 12)
        wait_until(
            b,
            lambda: (b.read_memory(MOD) == 1 and b.read_memory(SUB) == 5) or b.read_memory(MOD) in (7, 9),
            400, 8, "file select",
        )
        if b.read_memory(MOD) == 1:
            tap_button(b, "Start", 4, 16)
        wait_until(b, lambda: b.read_memory(MOD) in (7, 9) and b.read_memory(SUB) == 0, 1800, 16, "gameplay")

        # ------------------------------------------------------------------
        # 1. Full sequence: Garrison ($83) Ocarina -> Bird Swoop -> Grab/Lift
        #    -> Lyra Sea Mode 7 Map Pin 8 -> Sky Spire ($8C) Drop-off & Walk
        # ------------------------------------------------------------------
        warp_garrison_83(b)
        step_frames(b, 3, "Y")
        anc = list(b.read_block(0x7E0C4A, 5))
        assert 0x27 in anc, f"Expected Ancilla $27 on $83, got {anc}"
        step_frames(b, 20)
        panels.append(("1. Ocarina Song ($83)", snap_bytes(b)))

        approach_snap = None
        lift_snap = None
        map_frame = None
        for f in range(20, 280, 2):
            bo = bird_oam(b)
            grabbed = b.read_memory(0x7E02DA) == 1
            if bo and not grabbed and approach_snap is None and bo[0][1] >= 48:
                assert (bo[0][4] & 0x30) == 0x30, f"Bird must be Priority 3, got {bo[0]}"
                approach_snap = snap_bytes(b)
            if bo and grabbed and lift_snap is None and bo[0][1] >= 156:
                assert (bo[0][4] & 0x30) == 0x30, f"Lifting bird must be Priority 3, got {bo[0]}"
                lift_snap = snap_bytes(b)
            if b.read_memory(MOD) == 0x0E and b.read_memory(SUB) == 0x0A and b.read_memory(0x7E0200) == 0x05:
                map_frame = f
                break
            step_frames(b, 2)

        assert approach_snap is not None, "Bird approach OAM never appeared on $83"
        assert lift_snap is not None, "Bird grab/lift OAM never appeared on $83"
        assert map_frame is not None, "Lyra Sea Mode 7 map never opened after Bird lift"
        panels.append(("2. Bird Swoops In ($83)", approach_snap))
        panels.append(("3. Bird Lifts Link ($83)", lift_snap))

        # Select Pin 8 ($1AF0 == 7, Sky Spire $8C) on Mode 7 Lyra Sea Map
        wait_until(
            b,
            lambda: b.read_memory(0x7E00C8) == 0 and b.read_memory(BRIGHT) == 0x0F,
            90, 2, "Mode 7 map input ready ($83)",
        )
        step_frames(b, 4)
        for _ in range(10):
            if b.read_memory(0x7E1AF0) == 7:
                break
            tap_button(b, "Right", 3, 5)
        assert b.read_memory(0x7E1AF0) == 7, f"Failed to select Pin 8, cursor={b.read_memory(0x7E1AF0)}"
        # Capture on a blink-ON frame so Pin 8's numeral is visibly rendered.
        for _ in range(32):
            if (b.read_memory(0x7E001A) & 0x10) == 0:
                break
            step_frames(b, 1)
        panels.append(("4. Lyra Sea Map (Pin 8 Sky)", snap_bytes(b)))

        # Confirm Pin 8 -> Sky Spire ($8C) Bird Drop-Off
        step_frames(b, 4, "A")
        wait_until(
            b,
            lambda: b.read_memory(MOD) == 0x09 and b.read_memory(SUB) == 0 and b.read_memory(BRIGHT) == 0x0F,
            360, 2, "Sky Spire $8C fade-in",
        )
        assert b.read_memory(AREA) == 0x8C, hex(b.read_memory(AREA))

        drop_carry_snap = None
        touchdown_snap = None
        for _ in range(90):
            bo = bird_oam(b)
            grabbed = b.read_memory(0x7E02DA) == 1
            if bo and grabbed and drop_carry_snap is None and bo[0][1] >= 44:
                assert (bo[0][4] & 0x30) == 0x30, f"Drop-off bird must be Priority 3, got {bo[0]}"
                drop_carry_snap = snap_bytes(b)
            if bo and not grabbed and touchdown_snap is None and bo[0][1] >= 165:
                # Step single frames if Link is currently blinked off on $031F invuln.
                for _ in range(4):
                    if (b.read_memory(0x7E031F) & 0x03) == 0:
                        break
                    step_frames(b, 1)
                touchdown_snap = snap_bytes(b)
            if not bo and not grabbed and b.read_memory(0x7E02E4) == 0:
                break
            step_frames(b, 2)

        assert drop_carry_snap is not None, "Drop-off Bird carrying Link never rendered on Sky $8C"
        assert touchdown_snap is not None, "Bird post-touchdown fly-away never rendered on Sky $8C"
        panels.append(("5. Bird Carry to Sky ($8C)", drop_carry_snap))
        panels.append(("6. Sky Touchdown & Free ($8C)", touchdown_snap))
        wait_until(b, lambda: b.read_memory(0x7E02E4) == 0 and not bird_oam(b), 120, 2, "Sky $8C unlock")
        assert_unlocked_and_walkable(b, "sky_8c_landing")
        report["checks"].append({"name": "garrison_83_to_sky_8c_full_flight", "passed": True, "map_frame": map_frame})

        # ------------------------------------------------------------------
        # 2. Sky Tower ($87) with live BG1 Cloud Overlay ($94) -> Pickup + B-Cancel
        # ------------------------------------------------------------------
        enter_sky_tower_87(b)
        step_frames(b, 3, "Y")
        assert 0x27 in b.read_block(0x7E0C4A, 5), "Bird did not spawn on Sky Tower $87"
        sky87_snap = None
        for f in range(0, 280, 2):
            bo = bird_oam(b)
            if bo and b.read_memory(0x7E02DA) == 1 and sky87_snap is None and bo[0][1] >= 140:
                assert (bo[0][4] & 0x30) == 0x30, f"$87 bird must draw over BG1 clouds: {bo[0]}"
                sky87_snap = snap_bytes(b)
            if b.read_memory(MOD) == 0x0E and b.read_memory(SUB) == 0x0A and b.read_memory(0x7E0200) == 0x05:
                break
            step_frames(b, 2)
        assert sky87_snap is not None, "Bird lift over Sky $87 BG1 clouds never captured"
        panels.append(("7. Lift Over Clouds ($87)", sky87_snap))
        wait_until(
            b,
            lambda: b.read_memory(0x7E00C8) == 0 and b.read_memory(BRIGHT) == 0x0F,
            90, 2, "Mode 7 map input ready ($87)",
        )
        step_frames(b, 4)
        step_frames(b, 4, "B")
        wait_until(
            b,
            lambda: b.read_memory(MOD) == 0x09 and b.read_memory(SUB) == 0 and b.read_memory(BRIGHT) == 0x0F,
            320, 2, "Sky $87 B-cancel return",
        )
        assert b.read_memory(AREA) == 0x87
        assert b.read_memory(0x7E001D) == 0x01 and b.read_memory(0x7E008C) == 0x94
        assert_unlocked_and_walkable(b, "sky_87_b_cancel")
        report["checks"].append({"name": "sky_tower_87_bg1_clouds_pickup_and_b_cancel", "passed": True})

        # ------------------------------------------------------------------
        # 3. Full-Ancilla ($0C4A..$0C4E all $0E) Regression -> Slot-4 Evict + X-Cancel
        # ------------------------------------------------------------------
        warp_garrison_83(b)
        for i in range(5):
            b.write_memory(0x7E0C4A + i, 0x0E)
            b.write_memory(0x7E0C54 + i, 0x00)
        step_frames(b, 3, "Y")
        anc_full = list(b.read_block(0x7E0C4A, 5))
        assert anc_full[4] == 0x27, f"Expected slot-4 eviction to spawn $27, got {[hex(x) for x in anc_full]}"
        evict_snap = None
        for f in range(0, 280, 2):
            bo = bird_oam(b)
            if bo and b.read_memory(0x7E02DA) == 1 and evict_snap is None and bo[0][1] >= 120:
                evict_snap = snap_bytes(b)
            if b.read_memory(MOD) == 0x0E and b.read_memory(SUB) == 0x0A and b.read_memory(0x7E0200) == 0x05:
                break
            step_frames(b, 2)
        assert evict_snap is not None, "Full-ancilla evicted Bird never grabbed Link"
        panels.append(("8. Full-Ancilla Evict ($83)", evict_snap))
        wait_until(
            b,
            lambda: b.read_memory(0x7E00C8) == 0 and b.read_memory(BRIGHT) == 0x0F,
            90, 2, "Mode 7 map input ready (evict)",
        )
        step_frames(b, 4)
        step_frames(b, 4, "X")
        wait_until(
            b,
            lambda: b.read_memory(MOD) == 0x09 and b.read_memory(SUB) == 0 and b.read_memory(BRIGHT) == 0x0F,
            240, 2, "full-ancilla X-cancel return",
        )
        assert_unlocked_and_walkable(b, "full_ancilla_x_cancel")
        report["checks"].append({"name": "full_ancilla_eviction_and_x_cancel", "passed": True})

    if args.proof_out is not None:
        build_proof_strip(panels, args.proof_out)
        report["proof_out"] = str(args.proof_out)
    report["passed"] = True
    report["check_count"] = len(report["checks"])
    if args.report_out is not None:
        args.report_out.parent.mkdir(parents=True, exist_ok=True)
        args.report_out.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
