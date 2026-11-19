#!/usr/bin/env python3
"""T2 native headless Mesen2-OOS verification for Whirlpool ($77) & Goriya ($2C).

Never touches shared Roms/, live .yazeproj/rom, or GUI Mesen instances.
Copies the caller-specified candidate ROM into a private temp home and runs
under Scripts/Agents/native_session.py (heavy_lock + owned-PID teardown).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import sys
import time

sys.dont_write_bytecode = True

REPO = Path(__file__).resolve().parents[2]
SCRATCH = Path.home() / "src/hobby/oracle-of-secrets-scratch"
DEFAULT_SEED = SCRATCH / "claude-d8-boss-20261116/fixture.srm"
ARTIFACTS_DIR = Path("/tmp/oos-whirlpool-goriya-proof")

sys.path.insert(0, str(REPO / "Scripts/Agents"))
sys.path.insert(0, "/Users/scawful/src/hobby/mesen2-oos/tools/oos_client")
os.environ.setdefault("MESEN2_OOS_ROOT", "/Users/scawful/src/hobby/mesen2-oos")

from native_session import NativeSession  # noqa: E402
from mesen2_client_lib.bridge import MesenBridge  # noqa: E402

# Overworld Sprite RAM ($7E0B00..$7E0F9F)
SPR_Y = 0x7E0D00
SPR_X = 0x7E0D10
SPR_YH = 0x7E0D20
SPR_XH = 0x7E0D30
SPR_YSPEED = 0x7E0D40
SPR_XSPEED = 0x7E0D50
SPR_ACTION = 0x7E0D80
SPR_FRAME = 0x7E0D90
SPR_MISCA = 0x7E0DA0
SPR_MISCB = 0x7E0DB0
SPR_STATE = 0x7E0DD0
SPR_MISCC = 0x7E0DE0
SPR_TIMERC = 0x7E0E10
SPR_TYPE = 0x7E0E20
SPR_SUBTYPE = 0x7E0E30
SPR_NBROAM = 0x7E0E40
SPR_MISCE = 0x7E0EB0
SPR_MISCG = 0x7E0ED0
SPR_TIMERD = 0x7E0EE0
SPR_FLASH = 0x7E0B89
SPR_TIMERE = 0x7E0F10

MOD = 0x7E0010
SUB = 0x7E0011
BRIGHT = 0x7E0013
INDOORS = 0x7E001B
LINK_Y = 0x7E0020
LINK_X = 0x7E0022
AREA = 0x7E008A
CAM_X = 0x7E00E2
CAM_Y = 0x7E00E8
ROOM = 0x7E00A0
OAM_PTR = 0x7E0090


def pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def sym_addr(sym_text: str, name: str) -> int:
    m = re.search(rf"^([0-9A-Fa-f]{{2}}):([0-9A-Fa-f]{{4}})\s+(?:Oracle_)?{re.escape(name)}\s*$", sym_text, re.M)
    if not m:
        raise RuntimeError(f"Missing symbol: {name}")
    return int(m[1] + m[2], 16)


def s8(v: int) -> int:
    return v - 256 if v >= 128 else v


def is_paused(b: MesenBridge) -> bool:
    reply = b.send_command("STATE")
    if not reply.get("success"):
        return False
    state = reply.get("data", {})
    if isinstance(state, str):
        state = json.loads(state)
    return state.get("paused") is True


def pause_wait(b: MesenBridge, timeout: float = 5.0) -> None:
    if is_paused(b):
        return
    b.pause()
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if is_paused(b):
            return
        time.sleep(0.01)
    raise RuntimeError("Timed out waiting for Mesen pause")


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
    end = time.monotonic() + max(5.0, count / 10.0)
    while time.monotonic() < end:
        if frame_count(b) >= before + count and is_paused(b):
            break
        time.sleep(0.005)
    else:
        raise RuntimeError(f"FRAME({count}) timed out at frame {frame_count(b)} (was {before})")
    if buttons:
        r_clr = b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
        assert r_clr.get("success"), f"INPUT clear rejected: {r_clr}"


def tap_button(b: MesenBridge, button: str, hold: int = 4, settle: int = 12) -> None:
    step_frames(b, 2, "")
    step_frames(b, hold, button)
    step_frames(b, settle, "")


def wait_until_boot_state(b: MesenBridge, pred, max_frames: int, step: int, label: str) -> None:
    spent = 0
    while spent < max_frames:
        mod, sub = b.read_memory(MOD), b.read_memory(SUB)
        if pred(mod, sub):
            return
        chunk = min(step, max_frames - spent)
        step_frames(b, chunk)
        spent += chunk
    mod, sub = b.read_memory(MOD), b.read_memory(SUB)
    if pred(mod, sub):
        return
    raise RuntimeError(f"Boot timeout awaiting {label} after {max_frames} frames; mod=${mod:02X} sub=${sub:02X}")


def run_to(b: MesenBridge, targets: set[int], timeout: float = 5.0) -> dict:
    pause_wait(b)
    b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
    bp_ids = []
    for addr in sorted(targets):
        bid = b.add_breakpoint(addr, bptype="exec")
        assert bid >= 0, f"Failed to add breakpoint at ${addr:06X}"
        bp_ids.append(bid)
    try:
        assert b.resume(), "Mesen resume rejected"
        end = time.monotonic() + timeout
        while time.monotonic() < end:
            if is_paused(b):
                cpu = b.get_cpu_state()
                raw_pc = cpu.get("pc", cpu.get("PC", 0))
                pc_val = int(raw_pc, 0) if isinstance(raw_pc, str) else int(raw_pc)
                if pc_val in targets:
                    return cpu
            time.sleep(0.005)
        raise RuntimeError(f"Timed out waiting for breakpoint {[f'${t:06X}' for t in targets]}")
    finally:
        for bid in bp_ids:
            b.remove_breakpoint(bid)
        pause_wait(b)


def wait_mod(b: MesenBridge, target_mod: int, max_steps: int = 120) -> None:
    for _ in range(max_steps):
        step_frames(b, 4)
        mod = b.read_memory(MOD)
        sub = b.read_memory(SUB)
        br = b.read_memory(BRIGHT)
        if mod == target_mod and sub == 0 and br == 0x0F:
            step_frames(b, 4)
            return
    raise RuntimeError(
        f"Timed out waiting for module=${target_mod:02X}; "
        f"got mod=${b.read_memory(MOD):02X} sub=${b.read_memory(SUB):02X} br=${b.read_memory(BRIGHT):02X}"
    )


def warp_ow_via_room(b: MesenBridge, via_room: int, expected_area: int) -> None:
    pause_wait(b)
    b.write_memory(0x7EF3C5, 0x02)  # GameState >= 2 so phase 1/2 sprites load
    b.write_memory(0x7EE000, 12)    # Daytime (12:00) so state_1 day list loads cleanly
    b.write_memory(0x7EF37A, 0x00)  # Clear crystals/essences so LoadPeacetimeSprites keeps state_1 enemies
    b.write_memory(0x7EF3CA, 0x00)  # Light world
    b.write_memory(0x7E0FFF, 0x00)
    b.write_memory(0x7EF3CC, 0x00)  # No follower
    b.write_memory(0x7EF356, 0x01)  # Flippers
    b.write_memory16(ROOM, via_room)
    b.write_memory(0x7E010A, 0x00)
    b.write_memory(0x7E04AA, 0x00)
    b.write_memory(BRIGHT, 0x80)
    b.write_memory(0x7E009B, 0x00)
    b.write_memory(SUB, 0x00)
    b.write_memory(0x7E00B0, 0x00)
    b.write_memory(MOD, 0x08)
    wait_mod(b, 0x09)
    area = b.read_memory(AREA)
    assert area == expected_area, f"Expected OW area ${expected_area:02X}, got ${area:02X}"


def cross_ow_border(
    b: MesenBridge,
    start_x: int,
    start_y: int,
    button: str,
    expected_area: int,
    cam_xy: tuple[int, int] | None = None,
) -> None:
    pause_wait(b)
    b.write_memory16(LINK_X, start_x)
    b.write_memory16(LINK_Y, start_y)
    if cam_xy is not None:
        b.write_memory16(CAM_X, cam_xy[0])
        b.write_memory16(CAM_Y, cam_xy[1])
    step_frames(b, 2)
    for _ in range(40):
        step_frames(b, 4, button)
        if b.read_memory(AREA) == expected_area or b.read_memory(SUB) != 0:
            break
    for _ in range(120):
        if b.read_memory(AREA) == expected_area and b.read_memory(SUB) == 0:
            step_frames(b, 6)
            return
        step_frames(b, 4)
    if b.read_memory(AREA) == expected_area and b.read_memory(SUB) == 0:
        step_frames(b, 6)
        return
    raise RuntimeError(
        f"Failed border crossing ({button}) from ({start_x:04X},{start_y:04X}) to area ${expected_area:02X}; "
        f"at area=${b.read_memory(AREA):02X} sub=${b.read_memory(SUB):02X} "
        f"pos=({b.read_memory16(LINK_X):04X},{b.read_memory16(LINK_Y):04X})"
    )


def find_sprites(b: MesenBridge, sid: int, subtype: int | None = None) -> list[int]:
    states = b.read_block(SPR_STATE, 16)
    types = b.read_block(SPR_TYPE, 16)
    subs = b.read_block(SPR_SUBTYPE, 16)
    out = []
    for i in range(16):
        if states[i] == 0x09 and types[i] == sid and (subtype is None or subs[i] == subtype):
            out.append(i)
    return out


def spr_xy(b: MesenBridge, slot: int) -> tuple[int, int]:
    x = b.read_memory(SPR_X + slot) | (b.read_memory(SPR_XH + slot) << 8)
    y = b.read_memory(SPR_Y + slot) | (b.read_memory(SPR_YH + slot) << 8)
    return x, y


def set_spr_xy(b: MesenBridge, slot: int, x: int, y: int) -> None:
    b.write_memory(SPR_X + slot, x & 0xFF)
    b.write_memory(SPR_XH + slot, (x >> 8) & 0xFF)
    b.write_memory(SPR_Y + slot, y & 0xFF)
    b.write_memory(SPR_YH + slot, (y >> 8) & 0xFF)


def describe() -> dict:
    return {
        "native_executed": False,
        "checks": [
            "Whirlpool/DekuLeaf ($77): $0DB0F7 == $83, OAM_AllocateFromRegionB ($0DBA84) 4 slots on OW $3D, 0 OAM slots when clipped offscreen",
            "Goriya ($2C): SprMiscG alternating Red($06)/Blue($08) on $17/$2E and Sand($0C)/Red($06) on Desert $36 + SprFlash XOR math",
            "Goriya ($2C): Goriya_SyncFrame frame alignment across turns & throw pause (0 moonwalk)",
            "Goriya ($2C): 16-bit $68 range detection (exact < $68 & page-crossing) and chase speed 16 vs patrol 12",
            "Goriya ($2C): Child Boomerang (SprSubtype=1) outward flight -> return -> parent catch (<= 12px despawn & SprTimerC=1)",
        ],
    }


def run_suite(rom_path: Path, sym_path: Path, seed_path: Path, out_dir: Path) -> dict:
    rom_bytes = rom_path.read_bytes()
    sym_text = sym_path.read_text(encoding="utf-8")

    # 1. Static ROM contracts
    assert rom_bytes[pc(0x0DB0F7)] == 0x83, f"Expected $0DB0F7 == $83, got ${rom_bytes[pc(0x0DB0F7)]:02X}"
    oam_region_b = sym_addr(sym_text, "OAM_AllocateFromRegionB") if "OAM_AllocateFromRegionB" in sym_text else 0x0DBA84
    draw_on_screen = sym_addr(sym_text, "Oracle_DekuLeaf_DrawFrame_draw_on_screen")
    draw_entry = sym_addr(sym_text, "Oracle_DekuLeaf_DrawFrame")
    draw_clipped = sym_addr(sym_text, "Oracle_DekuLeaf_DrawFrame_clipped")
    draw_rts = sym_addr(sym_text, "Oracle_DekuLeaf_DrawFrame_start_index") - 1
    jsl_oam_pc = draw_on_screen + 4  # SEP #$20 (2B), LDA #$10 (2B) -> JSL $0DBA84
    assert rom_bytes[pc(jsl_oam_pc):pc(jsl_oam_pc) + 4] == b"\x22" + oam_region_b.to_bytes(3, "little"), (
        f"DekuLeaf_DrawFrame does not JSL OAM_AllocateFromRegionB at ${jsl_oam_pc:06X}"
    )
    assert rom_bytes[pc(draw_rts)] == 0x60

    goriya_draw_on_screen = sym_addr(sym_text, "Oracle_Sprite_Goriya_Draw_on_screen")
    goriya_draw_rts = sym_addr(sym_text, "Oracle_Sprite_Goriya_Draw_start_index") - 1
    assert rom_bytes[pc(goriya_draw_rts)] == 0x60

    shutil.rmtree(out_dir, ignore_errors=True)
    out_dir.mkdir(parents=True)
    test_rom = out_dir / "oos168x.sfc"
    shutil.copy2(rom_path, test_rom)
    home = out_dir / "home"
    (home / "Saves").mkdir(parents=True)
    shutil.copy2(seed_path, home / "Saves/oos168x.srm")

    report: dict = {"rom_checks": {"0DB0F7": "0x83", "jsl_oam_b": f"0x{jsl_oam_pc:06X}"}, "checks": {}}

    with NativeSession("whirlpool-goriya-t2", "T2 native check: Whirlpool ($77) & Goriya ($2C)", out_dir, deadline=240) as session:
        _pid, sock = session.launch_mesen(test_rom, home=home)
        for _ in range(80):
            if sock.exists():
                break
            time.sleep(0.25)
        b = MesenBridge(str(sock), auto_reconnect=False, max_retries=0)
        assert b.ensure_connected(retries=15, delay=0.4), "Failed to connect to Mesen2 socket"
        rom_sha1 = hashlib.sha1(rom_bytes).hexdigest().lower()
        for _ in range(100):
            if str(b.get_rom_info().get("sha1", "")).lower() == rom_sha1:
                break
            time.sleep(0.1)
        else:
            raise RuntimeError(f"ROM identity did not settle: {b.get_rom_info()}")
        pause_wait(b)
        for _ in range(50):
            r_in = b.send_command("INPUT", {"buttons": "", "frames": "0", "player": "0"})
            if r_in.get("success") and b.get_cpu_state():
                break
            time.sleep(0.1)
        else:
            raise RuntimeError("Debugger/INPUT did not initialize after ROM load")

        # Boot deterministically through Title (00/08) -> File Select (01/05) -> Gameplay (07/00 or 09/00)
        step_frames(b, 1)
        wait_until_boot_state(b, lambda m, s: (m == 0x00 and s == 0x08) or m in (0x01, 0x07, 0x09), 2700, 16, "title (00/08)")
        if b.read_memory(MOD) == 0x00:
            tap_button(b, "Start", hold=4, settle=12)
        wait_until_boot_state(b, lambda m, s: (m == 0x01 and s == 0x05) or m in (0x07, 0x09), 400, 8, "file select (01/05)")
        if b.read_memory(MOD) == 0x01:
            tap_button(b, "Start", hold=4, settle=16)
        wait_until_boot_state(b, lambda m, s: m in (0x07, 0x09) and s == 0x00, 1800, 16, "gameplay (07/09, sub 0)")

        # ------------------------------------------------------------------
        # 2. Desert OW $36 Goriya ($2C): Sand ($0C) / Red ($06) palettes
        # ------------------------------------------------------------------
        warp_ow_via_room(b, 0x0098, 0x36)
        step_frames(b, 8)
        g_36 = find_sprites(b, 0x2C, 0)
        for _ in range(30):
            if g_36:
                break
            step_frames(b, 4, "Down")
            g_36 = find_sprites(b, 0x2C, 0)
        assert g_36, (
            f"No Goriya ($2C) loaded on OW $36: pos=({b.read_memory16(LINK_X):04X},{b.read_memory16(LINK_Y):04X}) "
            f"cam=({b.read_memory16(CAM_X):04X},{b.read_memory16(CAM_Y):04X}) hr={b.read_memory(0x7EE000)}"
        )
        pal_36 = {slot: b.read_memory(SPR_MISCG + slot) for slot in g_36}
        for slot, pal in pal_36.items():
            exp = 0x06 if (slot & 1) else 0x0C
            assert pal == exp, f"OW $36 slot {slot} SprMiscG=${pal:02X} != ${exp:02X}"
        report["checks"]["goriya_36_palettes"] = {str(k): f"0x{v:02X}" for k, v in pal_36.items()}

        # ------------------------------------------------------------------
        # 3. OW $3D Whirlpool ($77): Region B 4-slot OAM + offscreen clipping
        # ------------------------------------------------------------------
        cross_ow_border(b, 0x0C03, 0x0F20, "Left", 0x3D, cam_xy=(0x0C00, 0x0EA0))
        w_slots = find_sprites(b, 0x77)
        assert w_slots, "Whirlpool ($77) did not load on OW $3D"
        w = w_slots[0]
        assert (b.read_memory(SPR_NBROAM + w) & 0x1F) == 0x03, "Whirlpool SprNbrOAM & 1F != 3"
        wx, wy = spr_xy(b, w)
        # Position Link in open sea near Whirlpool so it is cleanly inside the viewport (away from dock NPC)
        b.write_memory16(LINK_X, wx + 0x28)
        b.write_memory16(LINK_Y, wy + 0x18)
        step_frames(b, 4)

        cpu_alloc = run_to(b, {jsl_oam_pc})
        a_reg = int(cpu_alloc.get("a", 0), 0) if isinstance(cpu_alloc.get("a"), str) else int(cpu_alloc.get("a", 0))
        assert (a_reg & 0xFF) == 0x10, f"Expected A=$10 (4 OAM slots) at OAM_AllocateFromRegionB, got ${a_reg:04X}"
        # Continue to DekuLeaf_DrawFrame RTS and inspect exact 4 written OAM slots + verify Region B ($01D0..$01FF)
        run_to(b, {draw_rts})
        oam_ptr = b.read_memory16(OAM_PTR)
        assert 0x0800 <= oam_ptr < 0x0A00, f"Unexpected ($90) pointer ${oam_ptr:04X}"
        oam_bytes = b.read_block(0x7E0000 + oam_ptr, 16)
        chrs = [oam_bytes[i * 4 + 2] for i in range(4)]
        attrs = [oam_bytes[i * 4 + 3] for i in range(4)]
        assert chrs == [0xE6, 0xE4, 0xC6, 0xC4], f"Unexpected whirlpool OAM tiles: {chrs}"
        assert all((a & 0x0F) == 0x09 for a in attrs), f"Unexpected whirlpool OAM palette/nametable: {attrs}"
        # Step to frame end and screenshot on-screen Whirlpool
        step_frames(b, 2)
        png = b.screenshot()
        assert png and png.startswith(b"\x89PNG")
        (out_dir / "whirlpool_3d_onscreen.png").write_bytes(png)

        # Now place Whirlpool just off the bottom edge of the settled camera viewport
        # (dy = $EC -> $02+$17 = $103 >= $FF) while keeping X centered (dx = $80) so !Persist keeps it alive.
        cam_x = b.read_memory16(CAM_X)
        cam_y = b.read_memory16(CAM_Y)
        set_spr_xy(b, w, cam_x + 0x0080, cam_y + 0x00EC)
        step_frames(b, 2)
        assert b.read_memory(SPR_STATE + w) == 0x09, (
            f"Persist Whirlpool did not stay alive offscreen: state={b.read_memory(SPR_STATE + w)} "
            f"xy={spr_xy(b, w)} cam=({cam_x:04X},{cam_y:04X})"
        )
        # Check draw_clipped is reached and draw_on_screen (OAM alloc) is NOT reached
        clipped_hits = 0
        alloc_hits = 0
        for _ in range(4):
            hit_cpu = run_to(b, {draw_clipped, draw_on_screen})
            raw_pc = hit_cpu.get("pc", hit_cpu.get("PC", 0))
            cur_pc = int(raw_pc, 0) if isinstance(raw_pc, str) else int(raw_pc)
            if cur_pc == draw_clipped:
                clipped_hits += 1
            elif cur_pc == draw_on_screen:
                alloc_hits += 1
            step_frames(b, 1)
        assert clipped_hits >= 1 and alloc_hits == 0, (
            f"Offscreen Whirlpool clipping failed: clipped={clipped_hits}, alloc_hits={alloc_hits}, "
            f"xy={spr_xy(b, w)}, cam=({b.read_memory16(CAM_X):04X},{b.read_memory16(CAM_Y):04X})"
        )
        report["checks"]["whirlpool_3d"] = {
            "slot": w,
            "oam_ptr": f"0x{oam_ptr:04X}",
            "chrs": [f"0x{c:02X}" for c in chrs],
            "offscreen_clipped_hits": clipped_hits,
            "offscreen_alloc_hits": alloc_hits,
        }

        # ------------------------------------------------------------------
        # 4. OW $17 Goriya ($2C): Red ($06) / Blue ($08) palettes
        # ------------------------------------------------------------------
        warp_ow_via_room(b, 0x00E8, 0x16)
        cross_ow_border(b, 0x0DFB, 0x05C4, "Right", 0x17, cam_xy=(0x0D00, 0x0510))
        g_17 = find_sprites(b, 0x2C, 0)
        assert g_17, "No Goriya ($2C) loaded on OW $17"
        pal_17 = {slot: b.read_memory(SPR_MISCG + slot) for slot in g_17}
        for slot, pal in pal_17.items():
            exp = 0x08 if (slot & 1) else 0x06
            assert pal == exp, f"OW $17 slot {slot} SprMiscG=${pal:02X} != ${exp:02X}"
        report["checks"]["goriya_17_palettes"] = {str(k): f"0x{v:02X}" for k, v in pal_17.items()}

        # ------------------------------------------------------------------
        # 5. OW $2E Goriya ($2C): Palettes, SprFlash XOR, SyncFrame, $68 Range,
        #    Chase 16 vs Patrol 12, Boomerang outward -> return -> catch
        # ------------------------------------------------------------------
        warp_ow_via_room(b, 0x00E7, 0x2E)
        step_frames(b, 8)
        g_2e = find_sprites(b, 0x2C, 0)
        if len(g_2e) < 2:
            for _ in range(8):
                step_frames(b, 4, "Right")
            for _ in range(25):
                g_2e = find_sprites(b, 0x2C, 0)
                if len(g_2e) >= 2:
                    break
                step_frames(b, 4, "Down")
        assert len(g_2e) >= 2, f"Expected >= 2 Goriyas on OW $2E, found {g_2e}"
        pal_2e = {slot: b.read_memory(SPR_MISCG + slot) for slot in g_2e}
        for slot, pal in pal_2e.items():
            exp = 0x08 if (slot & 1) else 0x06
            assert pal == exp, f"OW $2E slot {slot} SprMiscG=${pal:02X} != ${exp:02X}"
        report["checks"]["goriya_2e_palettes"] = {str(k): f"0x{v:02X}" for k, v in pal_2e.items()}

        # Pick first Goriya on OW $2E; disable siblings cleanly so OAM/slot observation is isolated
        g = g_2e[0]
        for other in g_2e[1:]:
            b.write_memory(SPR_STATE + other, 0)
        g_pal = pal_2e[g]
        gx, gy = 0x0C50, 0x0AA0
        set_spr_xy(b, g, gx, gy)

        # Keep Link nearby (56 px east on dirt ledge) while Goriya holds stationary stance for flash test
        b.write_memory16(LINK_X, gx + 0x38)
        b.write_memory16(LINK_Y, gy)
        b.write_memory(SPR_MISCB + g, 4)
        b.write_memory(SPR_TIMERC + g, 40)
        step_frames(b, 2)

        # 5a. SprFlash XOR math on live OAM output at Sprite_Goriya_Draw RTS
        flash_results = {}
        for f in (0, 1, 2, 3, 7):
            b.write_memory(SPR_TIMERC + g, 40)
            cpu_on = run_to(b, {goriya_draw_on_screen})
            x_reg = int(cpu_on.get("x", 0), 0) if isinstance(cpu_on.get("x"), str) else int(cpu_on.get("x", 0))
            assert (x_reg & 0xFF) == g, f"Unexpected Goriya slot X={x_reg} != {g} at Sprite_Goriya_Draw"
            b.write_memory(SPR_FLASH + g, f)
            run_to(b, {goriya_draw_rts})
            g_oam_ptr = b.read_memory16(OAM_PTR)
            g_oam = b.read_block(0x7E0000 + g_oam_ptr, 8)
            exp_pal = ((f << 1) ^ g_pal) & 0x0E
            body_attr, head_attr = g_oam[3], g_oam[7]
            assert (body_attr & 0x0F) == (exp_pal | 0x01), (
                f"Flash={f}: body attr=${body_attr:02X} != expected pal ${exp_pal:02X}|1"
            )
            assert (head_attr & 0x0F) == (exp_pal | 0x01), (
                f"Flash={f}: head attr=${head_attr:02X} != expected pal ${exp_pal:02X}|1"
            )
            flash_results[str(f)] = f"0x{body_attr:02X}/0x{head_attr:02X}"
        # Also verify live HitTimer ($7E0EF0) drives SprFlash ($7E0B89) across frame step
        b.write_memory(SPR_TIMERC + g, 40)
        b.write_memory(SPR_FLASH + g, 0)
        b.write_memory(0x7E0EF0 + g, 5)
        step_frames(b, 1)
        run_to(b, {goriya_draw_rts})
        live_flash = b.read_memory(SPR_FLASH + g) & 0x0E
        live_oam_ptr = b.read_memory16(OAM_PTR)
        live_attr = b.read_block(0x7E0000 + live_oam_ptr, 8)[3]
        exp_live = ((live_flash << 1) ^ g_pal) & 0x0E
        assert live_flash != 0 and (live_attr & 0x0F) == (exp_live | 0x01), (
            f"Live HitTimer flash mismatch: SprFlash=${live_flash:02X} attr=${live_attr:02X}"
        )
        flash_results["live_hit_timer"] = f"flash=0x{live_flash:02X},attr=0x{live_attr:02X}"
        b.write_memory(0x7E0EF0 + g, 0)
        b.write_memory(SPR_FLASH + g, 0)
        step_frames(b, 1)
        report["checks"]["goriya_flash_xor"] = flash_results

        # 5b. Range boundary ($68 exact miss vs $67 hit + 256px page cross) & speed 12 vs 16
        for tbl in (0x7E0EA0, 0x7E0F00, 0x7E0F30, 0x7E0F40, 0x7E0EF0, 0x7E0B89):
            b.write_memory(tbl + g, 0)
        set_spr_xy(b, g, 0x0C40, 0x0AA0)
        b.write_memory(SPR_XSPEED + g, 0)
        b.write_memory(SPR_YSPEED + g, 0)
        b.write_memory(SPR_TIMERE + g, 0)
        b.write_memory(SPR_MISCB + g, 3)  # walking Right on flat ledge
        b.write_memory(SPR_ACTION + g, 3)
        b.write_memory(SPR_TIMERC + g, 20)
        b.write_memory16(LINK_X, 0x0C40 + 0x68)  # exact $68 px away -> out of range!
        b.write_memory16(LINK_Y, 0x0AA0)
        step_frames(b, 2)
        assert b.read_memory(SPR_TIMERE + g) == 0, "Goriya detected Link at exact $68 px boundary!"
        vx = s8(b.read_memory(SPR_XSPEED + g))
        vy = s8(b.read_memory(SPR_YSPEED + g))
        patrol_spd = abs(vx) + abs(vy)
        assert patrol_spd == 12, f"Expected patrol speed 12, got {patrol_spd} (vx={vx}, vy={vy})"

        # Page boundary crossing: Goriya at $0CFA, Link at $0D20 -> |dx| = $26 < $68 across $0CFF/$0D00
        set_spr_xy(b, g, 0x0CFA, 0x0AA0)
        b.write_memory(SPR_TIMERE + g, 0)
        b.write_memory16(LINK_X, 0x0D20)
        b.write_memory16(LINK_Y, 0x0AA0)
        step_frames(b, 2)
        te = b.read_memory(SPR_TIMERE + g)
        chase_spd = abs(s8(b.read_memory(SPR_XSPEED + g))) + abs(s8(b.read_memory(SPR_YSPEED + g)))
        assert te >= 0x5E, f"Page-crossing < $68 detection failed: SprTimerE={te}"
        assert chase_spd == 16, f"Expected chase speed 16, got {chase_spd}"

        # Exact $67 detection check too
        set_spr_xy(b, g, 0x0C40, 0x0AA0)
        b.write_memory(SPR_TIMERE + g, 0)
        b.write_memory16(LINK_X, 0x0C40 + 0x67)
        b.write_memory16(LINK_Y, 0x0AA0)
        step_frames(b, 2)
        assert b.read_memory(SPR_TIMERE + g) >= 0x5E, "Goriya failed detection at dx=$67 px"
        report["checks"]["goriya_range_speed"] = {
            "patrol_speed": patrol_spd,
            "chase_speed": chase_spd,
            "page_cross_timerE": te,
        }

        # 5c. Goriya_SyncFrame across all 4 directions (0 moonwalking)
        sync_log = {}
        set_spr_xy(b, g, 0x0C50, 0x0AA0)
        b.write_memory16(LINK_X, 0x0D80)
        b.write_memory16(LINK_Y, 0x0AA0)
        b.write_memory(SPR_TIMERC + g, 20)
        for act in (0, 1, 2, 3):
            b.write_memory(SPR_MISCB + g, act)
            b.write_memory(SPR_FRAME + g, ((act ^ 2) * 2) & 0x07)  # deliberately mismatched frame before step!
            step_frames(b, 1)
            cur_act = b.read_memory(SPR_ACTION + g) & 0x03
            cur_fr = b.read_memory(SPR_FRAME + g)
            assert (cur_fr & 0xFE) == (cur_act << 1), (
                f"Moonwalk detected: dir={act} -> SprAction={cur_act}, SprFrame={cur_fr}"
            )
            sync_log[str(act)] = f"action={cur_act},frame={cur_fr}"
        report["checks"]["goriya_sync_frame"] = sync_log

        # 5d. Child Boomerang ($2C subtype 1): throw -> outward -> return -> parent catch (despawn & SprTimerC<=1)
        # Position Goriya at (0x0D20, 0x0AA0) facing South over clear open water (col 18, row 10..16)
        set_spr_xy(b, g, 0x0D20, 0x0AA0)
        b.write_memory(SPR_TIMERE + g, 0x60)
        b.write_memory(SPR_TIMERD + g, 0x00)  # cooldown ready
        b.write_memory(SPR_TIMERC + g, 0x10)
        b.write_memory(SPR_MISCB + g, 0x01)
        b.write_memory(SPR_ACTION + g, 0x01)
        b.write_memory16(LINK_X, 0x0D20)
        b.write_memory16(LINK_Y, 0x0AD8)  # 56 px south (< $78 throw range, plenty of open southward flight room)
        b.write_memory16(CAM_X, 0x0C80)
        b.write_memory16(CAM_Y, 0x0A20)

        boom = None
        for _ in range(30):
            step_frames(b, 1)
            bs = find_sprites(b, 0x2C, 1)
            if bs:
                boom = bs[0]
                break
        assert boom is not None, "Goriya did not spawn child Boomerang (SprSubtype=1)"
        assert b.read_memory(SPR_MISCB + g) == 4, "Parent Goriya did not enter throw wait state (SprMiscB=4)"
        assert (b.read_memory(SPR_FRAME + g) & 0xFE) == ((b.read_memory(SPR_ACTION + g) & 3) << 1), "Parent frame not synced on throw"
        assert b.read_memory(SPR_XSPEED + g) == 0 and b.read_memory(SPR_YSPEED + g) == 0, "Parent moved during throw pause"
        assert b.read_memory(SPR_MISCA + boom) == g, "Child Boomerang SprMiscA != parent slot"
        assert b.read_memory(SPR_MISCC + boom) == 0, "Child Boomerang did not start outward (SprMiscC=0)"

        # Move Link east of the flight path so Link does not block return while camera stays centered
        b.write_memory16(LINK_X, 0x0D60)
        b.write_memory16(LINK_Y, 0x0AA0)
        step_frames(b, 4)
        bpng = b.screenshot()
        if bpng and bpng.startswith(b"\x89PNG"):
            (out_dir / "goriya_boomerang_outward.png").write_bytes(bpng)

        # Wait for outward -> return transition (SprMiscC == 1) -> catch despawn
        saw_return = False
        caught = False
        last_boom_xy = spr_xy(b, boom)
        for _ in range(120):
            # Keep Link east of the flight path so Link cannot absorb or block return catch
            b.write_memory16(LINK_X, 0x0D60)
            b.write_memory16(LINK_Y, 0x0AA0)
            step_frames(b, 1)
            st = b.read_memory(SPR_STATE + boom)
            if st == 0x09:
                last_boom_xy = spr_xy(b, boom)
            if not saw_return and st == 0x09 and b.read_memory(SPR_MISCC + boom) == 1:
                saw_return = True
                # Refresh parent wait timer high (0x40) so only catch can cut wait state 4 early!
                b.write_memory(SPR_TIMERC + g, 0x40)
            if saw_return and st == 0x00:
                tc = b.read_memory(SPR_TIMERC + g)
                mb = b.read_memory(SPR_MISCB + g)
                assert tc in (0, 1) or mb != 4, (
                    f"Boomerang despawned without cutting parent throw pause (SprTimerC={tc}, SprMiscB={mb})"
                )
                step_frames(b, 2)
                assert b.read_memory(SPR_MISCB + g) != 4, (
                    f"Parent Goriya stuck in throw wait after catch (SprTimerC={b.read_memory(SPR_TIMERC + g)})"
                )
                caught = True
                break
        assert saw_return, "Boomerang never entered returning phase (SprMiscC=1)"
        assert caught, "Boomerang did not return and get caught by parent Goriya"

        gx_end, gy_end = spr_xy(b, g)
        report["checks"]["goriya_boomerang"] = {
            "parent_slot": g,
            "child_slot": boom,
            "saw_outward": True,
            "saw_return": saw_return,
            "caught_despawned": caught,
            "last_return_gap_px": [abs(last_boom_xy[0] - gx_end), abs(last_boom_xy[1] - gy_end)],
        }

    report["status"] = "PASS"
    (out_dir / "result.json").write_text(json.dumps(report, indent=2) + "\n")
    return report


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--describe", action="store_true")
    ap.add_argument("--rom", type=Path, help="Compiled candidate ROM path (copied to /tmp; never edited)")
    ap.add_argument("--sym", type=Path, help="Matching WLA .sym path (defaults to --rom with .sym)")
    ap.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    ap.add_argument("--out", type=Path, default=ARTIFACTS_DIR)
    args = ap.parse_args(argv)
    if args.describe:
        print(json.dumps(describe(), indent=2))
        return 0
    if not args.rom:
        ap.error("--rom is required unless --describe is set")
    sym = args.sym or args.rom.with_suffix(".sym")
    if not args.rom.is_file() or not sym.is_file() or not args.seed.is_file():
        ap.error(f"Missing required input: rom={args.rom}, sym={sym}, seed={args.seed}")
    report = run_suite(args.rom.resolve(), sym.resolve(), args.seed.resolve(), args.out)
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
