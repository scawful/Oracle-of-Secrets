#!/usr/bin/env python3
"""Compiled 65816 CPU proof for Special Overworld 8-pin Mode 7 Lyra Sea Map
Soaring (real Travel Bird pickup, visited-unlocks, spread pins, cancel cleanup,
and native Bird drop-off) plus Light World Bird Travel non-regression via Lakesnes.

Covers:
  - SpecialSoaring_Open ($80..$BF -> AddTravelBird $0994FE, duplicate-bird guard,
    HorseForm_SilentDismount before pickup, LW/DW/out-of-range rejection)
  - TravelDest_MarkVisited ($09C4C7 hook: all 26 Special OW parent/child areas
    -> exact SpecialTravelSpotsVisited $7EF438 bits, non-target areas untouched,
    LW $7EF412 non-regression)
  - TravelPicker_LoadMap ($0AB74B: SpecialSoaring_LoadStep clear, baseline starts
    at Pin 2 Garrison [idx 1], Korok unlock starts at Pin 1 [idx 0], LW intact)
  - TravelPicker_Move ($0AB7AC: wrap across baseline [1,2,3], partial Crescent
    [1,2,3,4], garbage bit-7 stripping [0..6], full 8-pin [0..7], LW intact)
  - TravelPicker_Numeral ($0AB813: exact spread coordinates for all 8 Lyra Sea
    pins, baseline/partial/full lock visibility, LW vanilla dispatch)
  - TravelPicker_CheckAction ($0AB78F) & SpecialSoaring_CancelCleanup:
    SW B/X cancel clears ALL Travel Bird pickup locks ($4B/$5D/$02DA/$02E4/
    $037B/$02F9/$0300/$0301/$037A/$03F0/$0FC1/$3A bit 6, stray Ancilla $27,
    SpecialSoaring_LoadStep) and exits via Sub $07; A/START confirms; LW intact
  - TravelPicker_LoadSelectedScreen ($0AB8C5) & SpecialSoaring_ExecuteTransport:
    enforces unlocked bitmask for all 8 pins (+ cancel cleanup on reject ->
    WorldMap_ExitMap fallback), copies all 8 verified $32-byte $7EC140 exit
    caches, drives Module $08 ($0283BF) across steps 0->1->2, sets music/ambient/
    swoosh & Link/mask palette, preserves Bird-carry locks, and arms native
    FluteMenu_FadeInAndQuack ($0200=9) -> SpawnLandingDuck drop-off!
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu, Fixture

STOPS = [
    # (index, label, area_id, cam_y, cam_x, link_y, link_x, origin, pin_x, pin_y, visit_bit)
    (0, "KOROK_COVE",    0x0081, 0x00B0, 0x02C8, 0x0100, 0x0340, 0x0598, 0x02B0, 0x01C0, 0x01),
    (1, "GARRISON",      0x0083, 0x00F0, 0x0688, 0x0140, 0x0700, 0x0790, 0x0700, 0x0140, 0x02),
    (2, "ZORA_QUAY",     0x0099, 0x06C0, 0x0218, 0x0710, 0x0290, 0x0602, 0x0290, 0x0710, 0x04),
    (3, "GORON_COAST",   0x00B0, 0x0C30, 0x0178, 0x0C80, 0x01F0, 0x01AE, 0x01F0, 0x0C80, 0x08),
    (4, "CRESCENT_ISLE", 0x00B3, 0x0E60, 0x0758, 0x0EB0, 0x07D0, 0x132A, 0x06A0, 0x0DA0, 0x10),
    (5, "COURAGE_ISLE",  0x00A6, 0x09D0, 0x0DA8, 0x0A20, 0x0E20, 0x0EB4, 0x0E20, 0x0A20, 0x20),
    (6, "FROST_GLACIER", 0x00BE, 0x0F00, 0x0D78, 0x0F50, 0x0DF0, 0x082E, 0x0DD0, 0x0E80, 0x40),
    (7, "SKY_SPIRE",     0x008C, 0x0260, 0x0868, 0x02B0, 0x08E0, 0x030C, 0x0B80, 0x02B0, 0x80),
]

SPECIAL_VISIT_AREAS = [
    (0x81, 0x01), (0x82, 0x01), (0x89, 0x01), (0x8A, 0x01),
    (0x83, 0x02), (0x8B, 0x02),
    (0x90, 0x04), (0x91, 0x04), (0x98, 0x04), (0x99, 0x04), (0xA0, 0x04), (0xA1, 0x04),
    (0xB0, 0x08), (0xB1, 0x08), (0xB8, 0x08), (0xB9, 0x08),
    (0xB3, 0x10), (0xB4, 0x10), (0xBB, 0x10), (0xBC, 0x10),
    (0xA6, 0x20), (0xA7, 0x20), (0xAE, 0x20), (0xAF, 0x20),
    (0xBE, 0x40), (0xBF, 0x40),
]

SW_VISITED_SRAM = 0x7EF438
ABYSS_VISITED_SRAM = 0x7EF43A
LW_VISITED_SRAM = 0x7EF412
SKY_LEARNED_SRAM = 0x7EF3B2
MAP_SWITCH_WRAM = 0x7EC13B
ORIGIN_WORLD_WRAM = 0x7EC13C
VIEW_WORLD_WRAM = 0x7EC13D
LOAD_STEP_WRAM = 0x7EC13E
ADD_TRAVEL_BIRD = 0x0994FE
MODULE08_OVERWORLD_LOAD = 0x0283BF

ABYSS_STOPS = [
    # (index, label, area_id, cam_y, cam_x, link_y, link_x, origin, pin_x, pin_y, visit_bit)
    (0, "TEMPORAL_PYRAMID", 0x0040, 0x0120, 0x01C8, 0x0170, 0x0240, 0x0938, 0x0240, 0x0170, 0x01),
    (1, "ABYSS_WINDMILL",   0x0063, 0x0840, 0x0868, 0x0890, 0x08E0, 0x020C, 0x08E0, 0x0890, 0x02),
    (2, "FORTRESS",         0x004B, 0x02F0, 0x0818, 0x0340, 0x0890, 0x0782, 0x0890, 0x0340, 0x04),
    (3, "TWIN_BROTHERS",    0x0056, 0x0510, 0x0C68, 0x0560, 0x0CE0, 0x088C, 0x0CE0, 0x0560, 0x08),
    (4, "SHRINE_COURAGE",   0x0050, 0x04F0, 0x00E8, 0x0540, 0x0160, 0x079C, 0x0160, 0x0540, 0x10),
    (5, "LUPO_TEMPLE",      0x005E, 0x0850, 0x0DD8, 0x08A0, 0x0E50, 0x02BA, 0x0E50, 0x08A0, 0x20),
    (6, "FOREST_DREAMS",    0x0058, 0x08A0, 0x0178, 0x08F0, 0x01F0, 0x052E, 0x01F0, 0x08F0, 0x40),
    (7, "ABYSS_BEACH",      0x0076, 0x0E50, 0x0DC8, 0x0EA0, 0x0E40, 0x02B8, 0x0E40, 0x0EA0, 0x80),
]

ABYSS_VISIT_AREAS = [
    (0x40, 0x01), (0x41, 0x01), (0x48, 0x01), (0x49, 0x01),
    (0x63, 0x02), (0x64, 0x02), (0x6B, 0x02), (0x6C, 0x02),
    (0x4B, 0x04), (0x4C, 0x04), (0x53, 0x04), (0x54, 0x04),
    (0x56, 0x08),
    (0x50, 0x10),
    (0x5E, 0x20), (0x5F, 0x20), (0x66, 0x20), (0x67, 0x20),
    (0x58, 0x40), (0x59, 0x40), (0x60, 0x40), (0x61, 0x40),
    (0x76, 0x80), (0x77, 0x80), (0x7E, 0x80), (0x7F, 0x80),
]


def run_until(f, entry, *, db=0x0A, long_return=True, stop_addrs=(), jsl_stubs=None, limit=40000):
    """Execute from SNES address `entry` until sentinel RTL/RTS or one of `stop_addrs`.

    `jsl_stubs` maps SNES entry addresses -> callable(fixture) executed in place
    of a JSL target (auto-synthesizing RTL after popping the 3-byte return address).
    """
    p = f.cpu
    p.k = entry >> 16
    p.pc = entry & 0xFFFF
    p.db = db
    p.mf = True
    p.xf = True
    p.dp = 0
    initial_sp = p.sp
    sentinel = (entry & 0xFF0000) | 0x7000
    frame = ([entry >> 16, 0x6F, 0xFF] if long_return else [0x6F, 0xFF])
    for v in frame:
        f.put(p.sp, v)
        p.sp -= 1
    stops = set(stop_addrs)
    stubs = jsl_stubs or {}
    for _ in range(limit):
        cur = (p.k << 16) | p.pc
        if cur == sentinel:
            assert p.sp == initial_sp, (hex(entry), "stack", hex(p.sp), hex(initial_sp))
            assert p.db == db, (hex(entry), "DBR", hex(p.db), hex(db))
            assert not f.bad_writes, (hex(entry), f.bad_writes)
            return "RETURN"
        if cur in stops:
            assert p.db == db, (hex(entry), "DBR at stop", hex(cur), hex(p.db))
            assert not f.bad_writes, (hex(entry), f.bad_writes)
            return cur
        if cur in stubs:
            stubs[cur](f)
            # Perform RTL manually: pull PCL, PCH, PB and +1
            p.sp += 1
            lo = f.get(p.sp)
            p.sp += 1
            hi = f.get(p.sp)
            p.sp += 1
            bank = f.get(p.sp)
            p.k = bank
            p.pc = ((lo | (hi << 8)) + 1) & 0xFFFF
            continue
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError((hex(entry), "instruction limit", hex(p.k), hex(p.pc)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for n in ("rom", "symbols", "lakesnes", "output"):
        ap.add_argument("--" + n, type=Path, required=True)
    a = ap.parse_args()
    rom = a.rom.read_bytes()
    sym = a.symbols.read_text()
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\dA-Fa-f]{2}):([\dA-Fa-f]{4}) (\S+)$", sym)
    }

    def sym_addr(name):
        return labels.get("Oracle_" + name) or labels.get(name)

    cases = []
    with tempfile.TemporaryDirectory(prefix="soaring-cpu-") as tmp:
        libpath = Path(tmp) / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(a.lakesnes / "snes/cpu.c"),
                str(a.lakesnes / "snes/statehandler.c"),
                "-o", str(libpath),
            ],
            check=True,
        )
        lib = C.CDLL(str(libpath))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        def fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05):
            f = Fixture(lib, rom, labels)
            f.word(0x8A, area)
            f.put(0x10, module)
            f.put(0x11, sub)
            f.put(0x0200, step)
            f.word(0x010C, 0x09)
            return f

        def read_word(f, at):
            return f.get(at) | (f.get(at + 1) << 8)

        # ------------------------------------------------------------------
        # 1. SpecialSoaring_Open: real AddTravelBird spawn, dup & horse guards
        # ------------------------------------------------------------------
        open_addr = sym_addr("SpecialSoaring_Open")
        horse_dismount = sym_addr("HorseForm_SilentDismount")
        assert open_addr is not None, "SpecialSoaring_Open missing"

        for source, opens in (
            (0x00, False), (0x2C, False), (0x7F, False),
            (0x80, True), (0x81, True), (0x83, True), (0x8C, True),
            (0x99, True), (0xA6, True), (0xB0, True), (0xB3, True),
            (0xBE, True), (0xBF, True), (0xC0, False),
        ):
            f = fresh(area=source, module=0x09, sub=0x00, step=0x00)
            f.put(LOAD_STEP_WRAM, 0x02)
            f.put(0x037A, 0x04)
            f.put(0x03F8, 0x05)
            bird_calls = []

            def stub_bird(fx):
                aid = fx.cpu.a & 0xFF
                max_slot = fx.cpu.y & 0xFF
                bird_calls.append((aid, max_slot))
                for slot in range(max_slot, -1, -1):
                    if fx.get(0x0C4A + slot) == 0:
                        fx.put(0x0C4A + slot, aid)
                        break

            res = run_until(f, open_addr, db=0x07, long_return=True, jsl_stubs={ADD_TRAVEL_BIRD: stub_bird})
            assert res == "RETURN"
            if opens:
                assert bird_calls == [(0x27, 0x04)], (hex(source), bird_calls)
                assert f.get(0x0C4E) == 0x27
                assert f.get(LOAD_STEP_WRAM) == 0x00 and f.get(0x037A) == 0x00 and f.get(0x03F8) == 0x00
                # Does NOT shortcut directly into Module $0E — Bird carries Link first!
                assert f.get(0x10) == 0x09 and f.get(0x11) == 0x00
            else:
                assert bird_calls == [], (hex(source), bird_calls)
                assert f.get(LOAD_STEP_WRAM) == 0x02
            cases.append(f"open-bird-{source:02x}")
            f.close()

        # Full ancilla table ($0C4A..$0C4E all busy with transient FX $0E):
        # SpecialSoaring_Open must evict slot 4 and retry AddTravelBird so the
        # Travel Bird pickup animation ALWAYS spawns.
        f = fresh(area=0x83, module=0x09, sub=0x00, step=0x00)
        for slot in range(5):
            f.put(0x0C4A + slot, 0x0E)
        bird_calls = []

        def stub_bird_full(fx):
            aid = fx.cpu.a & 0xFF
            max_slot = fx.cpu.y & 0xFF
            bird_calls.append((aid, max_slot, [fx.get(0x0C4A + s) for s in range(5)]))
            for slot in range(max_slot, -1, -1):
                if fx.get(0x0C4A + slot) == 0:
                    fx.put(0x0C4A + slot, aid)
                    break

        res = run_until(f, open_addr, db=0x07, long_return=True, jsl_stubs={ADD_TRAVEL_BIRD: stub_bird_full})
        assert res == "RETURN"
        assert len(bird_calls) == 2, bird_calls
        assert bird_calls[0][2] == [0x0E, 0x0E, 0x0E, 0x0E, 0x0E]
        assert bird_calls[1][2] == [0x0E, 0x0E, 0x0E, 0x0E, 0x00]
        assert [f.get(0x0C4A + s) for s in range(5)] == [0x0E, 0x0E, 0x0E, 0x0E, 0x27]
        assert f.get(0x03F8) == 0x00
        cases.append("open-full-ancilla-evicts-slot4-and-spawns-bird")
        f.close()

        # Duplicate Travel Bird guard across all 5 ancilla slots ($0C4A..$0C4E)
        for slot in range(5):
            f = fresh(area=0x83, module=0x09, sub=0x00, step=0x00)
            f.put(0x0C4A + slot, 0x27)
            bird_calls = []
            res = run_until(f, open_addr, db=0x07, long_return=True,
                            jsl_stubs={ADD_TRAVEL_BIRD: lambda fx: bird_calls.append(1)})
            assert res == "RETURN" and bird_calls == [], (slot, bird_calls)
            f.close()
        cases.append("open-dup-bird-blocked")

        # Horse silent dismount before Bird swoop when riding Epona ($02B2 == $09)
        if horse_dismount is not None:
            f = fresh(area=0x83, module=0x09, sub=0x00, step=0x00)
            f.put(0x02B2, 0x09)
            events = []
            res = run_until(
                f, open_addr, db=0x07, long_return=True,
                jsl_stubs={
                    horse_dismount: lambda fx: (events.append("dismount"), fx.put(0x02B2, 0x00)),
                    ADD_TRAVEL_BIRD: lambda fx: (events.append("bird"), fx.put(0x0C4E, 0x27)),
                },
            )
            assert res == "RETURN" and events == ["dismount", "bird"], events
            cases.append("open-horse-dismount-before-bird")
            f.close()

        # ------------------------------------------------------------------
        # 2. TravelDest_MarkVisited: all 26 SW areas + non-targets + LW intact
        # ------------------------------------------------------------------
        mark_addr = sym_addr("TravelDest_MarkVisited")
        check_night = sym_addr("CheckIfNight")
        assert mark_addr is not None and check_night is not None

        for area, exp_bit in SPECIAL_VISIT_AREAS:
            f = fresh(area=area, module=0x09, sub=0x00, step=0x00)
            f.put(0x040A, area)
            f.put(SW_VISITED_SRAM, 0x00)
            f.put(LW_VISITED_SRAM, 0x00)
            res = run_until(f, mark_addr, db=0x09, stop_addrs=(check_night,))
            assert res == check_night
            assert f.get(SW_VISITED_SRAM) == exp_bit, (hex(area), hex(f.get(SW_VISITED_SRAM)), hex(exp_bit))
            assert f.get(LW_VISITED_SRAM) == 0x00
            f.close()
        cases.append("mark-visited-sw-26-areas")

        # Non-region Special OW areas (incl. Sky $8C, curtain $88, Deku $A8, sea $A2) must NOT set bits!
        for area in (0x80, 0x88, 0x8C, 0xA2, 0xA8, 0xB5, 0xC0):
            f = fresh(area=area, module=0x09, sub=0x00, step=0x00)
            f.put(0x040A, area)
            f.put(SW_VISITED_SRAM, 0x00)
            res = run_until(f, mark_addr, db=0x09, stop_addrs=(check_night,))
            assert res == check_night
            assert f.get(SW_VISITED_SRAM) == 0x00, (hex(area), hex(f.get(SW_VISITED_SRAM)))
            f.close()
        cases.append("mark-visited-sw-non-targets-clean")

        # Light World TravelDest_MarkVisited non-regression (slot 0 -> $02EAE5)
        lw_area0 = rom[0x016AE5]  # LoROM $02EAE5 -> PC $016AE5
        f = fresh(area=lw_area0, module=0x09, sub=0x00, step=0x00)
        f.put(0x040A, lw_area0)
        f.put(LW_VISITED_SRAM, 0x00)
        f.put(SW_VISITED_SRAM, 0x00)
        res = run_until(f, mark_addr, db=0x09, stop_addrs=(check_night,))
        assert res == check_night and f.get(LW_VISITED_SRAM) == 0x01 and f.get(SW_VISITED_SRAM) == 0x00
        cases.append("mark-visited-lw-regression")
        f.close()

        # ------------------------------------------------------------------
        # 3. TravelPicker_LoadMap ($0AB74B): cursor init + LoadStep clear
        # ------------------------------------------------------------------
        for area, lw_vis, sw_vis, sky, exp_cursor in (
            (0x83, 0x00, 0x00, 0x00, 1),  # Baseline hubs $0E -> Pin 2 (idx 1)
            (0x83, 0x00, 0x10, 0x00, 1),  # Crescent visited $1E -> still starts Pin 2 (idx 1)
            (0x83, 0x00, 0x01, 0x00, 0),  # Korok visited $0F -> Pin 1 (idx 0)
            (0x83, 0x00, 0x80, 0x00, 1),  # Garbage bit 7 ignored -> Pin 2 (idx 1)
            (0xA6, 0x00, 0x7F, 0xA5, 0),  # Full 8-pin -> Pin 1 (idx 0)
            (0x2C, 0x00, 0x7F, 0xA5, 0),  # LW empty -> 0
            (0x2C, 0x08, 0x7F, 0x00, 3),  # LW visited bit 3 -> 3
            (0x2C, 0x80, 0x00, 0x00, 7),  # LW visited bit 7 -> 7
        ):
            f = fresh(area=area, step=0x01)
            f.put(LW_VISITED_SRAM, lw_vis)
            f.put(SW_VISITED_SRAM, sw_vis)
            f.put(SKY_LEARNED_SRAM, sky)
            f.put(LOAD_STEP_WRAM, 0x03)
            f.put(0x1AF0, 0x77)
            res = run_until(f, 0x0AB74B, stop_addrs=(0x0ABA30,))
            assert res == 0x0ABA30
            assert f.get(0x1AF0) == exp_cursor, (hex(area), hex(sw_vis), hex(sky), f.get(0x1AF0))
            assert f.get(LOAD_STEP_WRAM) == 0x00
            cases.append(f"loadmap-{area:02x}-sw{sw_vis:02x}-s{sky:02x}")
            f.close()

        # ------------------------------------------------------------------
        # 4. TravelPicker_Move ($0AB7AC): baseline / partial / full / LW wrap
        # ------------------------------------------------------------------
        for sw_vis, sky, ring, tag in (
            (0x00, 0x00, [1, 2, 3], "baseline"),
            (0x10, 0x00, [1, 2, 3, 4], "crescent"),
            (0xFF, 0x00, [0, 1, 2, 3, 4, 5, 6], "garbage-bit7-sky-locked"),
            (0x7F, 0xA5, [0, 1, 2, 3, 4, 5, 6, 7], "full8"),
        ):
            for btn, dir_tag, step_dir in ((0x04, "down", 1), (0x01, "right", 1), (0x08, "up", -1), (0x02, "left", -1)):
                for i, cur in enumerate(ring):
                    f = fresh(area=0x83)
                    f.put(SW_VISITED_SRAM, sw_vis)
                    f.put(SKY_LEARNED_SRAM, sky)
                    f.put(LW_VISITED_SRAM, 0x00)
                    f.cpu.x = cur
                    f.put(0xF4, btn)
                    assert run_until(f, sym_addr("TravelPicker_Move"), long_return=True) == "RETURN"
                    exp = ring[(i + step_dir) % len(ring)]
                    assert f.get(0x1AF0) == exp, (tag, dir_tag, cur, f.get(0x1AF0), exp)
                    assert f.get(0x012F) == 0x20
                    assert f.cpu.x == cur
                    f.close()
            cases.append(f"sw-move-{tag}")

        # LW visited mask regression: bits 0, 2, 5 ($25)
        lw_ring = [0, 2, 5]
        for idx, cur in enumerate(lw_ring):
            f = fresh(area=0x2C)
            f.put(LW_VISITED_SRAM, 0x25)
            f.put(SW_VISITED_SRAM, 0x7F)
            f.put(SKY_LEARNED_SRAM, 0xA5)
            f.cpu.x = cur
            f.put(0xF4, 0x04)
            assert run_until(f, sym_addr("TravelPicker_Move"), long_return=True) == "RETURN"
            assert f.get(0x1AF0) == lw_ring[(idx + 1) % len(lw_ring)]
            f.close()
        cases.append("lw-move-visited-mask-regression")

        # ------------------------------------------------------------------
        # 5. TravelPicker_Numeral ($0AB813): all 8 pin coords & unlock gating
        # ------------------------------------------------------------------
        for sw_vis, sky, unlocked, tag in (
            (0x00, 0x00, {1, 2, 3}, "baseline"),
            (0x10, 0x00, {1, 2, 3, 4}, "crescent"),
            (0xFF, 0x00, {0, 1, 2, 3, 4, 5, 6}, "no-sky"),
            (0x7F, 0xA5, {0, 1, 2, 3, 4, 5, 6, 7}, "full8"),
        ):
            cursor = min(unlocked)
            for pin in range(8):
                f = fresh(area=0x83)
                f.put(SW_VISITED_SRAM, sw_vis)
                f.put(SKY_LEARNED_SRAM, sky)
                f.put(LW_VISITED_SRAM, 0x00)
                f.put(0x1AF0, cursor)
                f.cpu.x = pin
                res = run_until(
                    f, 0x0AB813,
                    stop_addrs=(0x0AB818, 0x0AB844, 0x0AB864, 0x0AB890, 0x0AB8AA),
                )
                if pin not in unlocked:
                    assert res == 0x0AB8AA, (tag, pin, hex(res))
                else:
                    exp_stop = 0x0AB844 if pin == cursor else 0x0AB890
                    assert res == exp_stop, (tag, pin, hex(res), hex(exp_stop))
                    exp_px, exp_py = STOPS[pin][8], STOPS[pin][9]
                    assert read_word(f, 0x7EC10A) == exp_px, (pin, hex(read_word(f, 0x7EC10A)), hex(exp_px))
                    assert read_word(f, 0x7EC108) == exp_py, (pin, hex(read_word(f, 0x7EC108)), hex(exp_py))
                    assert f.get(0x1AB0 + pin) == (exp_px & 0xFF)
                    assert f.get(0x1AC0 + pin) == (exp_px >> 8)
                    assert f.get(0x1AD0 + pin) == (exp_py & 0xFF)
                    assert f.get(0x1AE0 + pin) == (exp_py >> 8)
                f.close()
            cases.append(f"sw-numerals-{tag}")

        # LW numeral regression
        for pin, cursor, visited, exp_stop in (
            (0, 0, 0x01, 0x0AB818),
            (3, 0, 0x09, 0x0AB864),
            (4, 0, 0x09, 0x0AB8AA),
            (7, 7, 0x80, 0x0AB818),
        ):
            f = fresh(area=0x2C)
            f.put(LW_VISITED_SRAM, visited)
            f.put(0x1AF0, cursor)
            f.cpu.x = pin
            res = run_until(
                f, 0x0AB813, stop_addrs=(0x0AB818, 0x0AB844, 0x0AB864, 0x0AB890, 0x0AB8AA)
            )
            assert res == exp_stop, (pin, cursor, hex(visited), hex(res))
            f.close()
        cases.append("lw-numerals-regression")

        # ------------------------------------------------------------------
        # 6. TravelPicker_CheckAction ($0AB78F) + Bird-pickup Cancel Cleanup
        # ------------------------------------------------------------------
        for f4, f6, tag in ((0x80, 0x00, "B"), (0x00, 0x40, "X"), (0x80, 0x80, "B+A")):
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
            f.put(0x1AF0, 0x03)
            # Arm ALL Bird-pickup locks & stray Ancilla $27
            f.put(0x0C4C, 0x27)
            f.put(LOAD_STEP_WRAM, 0x02)
            f.put(0x4B, 0x0C)
            f.put(0x5D, 0x04)
            f.put(0x02DA, 0x01)
            f.put(0x02E4, 0x01)
            f.put(0x037B, 0x01)
            f.put(0x02F9, 0x01)
            f.put(0x0300, 0x01)
            f.put(0x0301, 0x02)
            f.put(0x037A, 0x04)
            f.put(0x03F0, 0x40)
            f.put(0x0FC1, 0x01)
            f.put(0x3A, 0xC0)
            f.put(0xF4, f4)
            f.put(0xF6, f6)
            res = run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,))
            assert res == "RETURN", (tag, res)
            assert f.get(0x11) == 0x07 and f.get(0x0200) == 0x06 and f.get(0x1AF0) == 0x00
            assert f.get(0x0C4C) == 0x00 and f.get(LOAD_STEP_WRAM) == 0x00
            for addr in (0x4B, 0x5D, 0x02DA, 0x02E4, 0x037B, 0x02F9, 0x0300, 0x0301, 0x037A, 0x03F0, 0x0FC1):
                assert f.get(addr) == 0x00, (tag, hex(addr), hex(f.get(addr)))
            # Because $03F0 was still non-zero (early grab near left edge), full BGM volume ($F3) is restored.
            assert f.get(0x012C) == 0xF3, (tag, hex(f.get(0x012C)))
            assert (f.get(0x3A) & 0x40) == 0x00
            cases.append(f"sw-cancel-cleanup-{tag}")
            f.close()

        # Cancel after $03F0 already finished (normal case): does not clobber $012C;
        # and if $012C already has a queued track switch while $03F0 != 0, preserves it.
        for timer, init_12c, exp_12c, subtag in (
            (0x00, 0x00, 0x00, "timer-zero-leaves-12c"),
            (0x40, 0x07, 0x07, "queued-song-preserved"),
        ):
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
            f.put(0x03F0, timer)
            f.put(0x012C, init_12c)
            f.put(0xF4, 0x80)
            assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == "RETURN"
            assert f.get(0x012C) == exp_12c and f.get(0x03F0) == 0x00
            cases.append(f"sw-cancel-bgm-{subtag}")
            f.close()

        # SW confirm: A ($F6=$80) and START ($F4=$10)
        for f4, f6, tag in ((0x00, 0x80, "A"), (0x10, 0x00, "START")):
            f = fresh(area=0xA6, module=0x0E, sub=0x0A, step=0x05)
            f.put(0x1AF0, 0x04)
            f.put(0xF4, f4)
            f.put(0xF6, f6)
            assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == "RETURN"
            assert f.get(0x11) == 0x0A and f.get(0x0200) == 0x06 and f.get(0x1AF0) == 0x04
            cases.append(f"sw-confirm-{tag}")
            f.close()

        # SW no-op held ignored & LW confirm/idle regression
        f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
        f.put(0xF0, 0xC0)
        f.put(0xF2, 0xC0)
        f.put(0xF4, 0x04)
        assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == 0x0AB79D
        assert f.get(0x0200) == 0x05 and f.get(0x11) == 0x0A
        f.close()

        f = fresh(area=0x2C, module=0x0E, sub=0x0A, step=0x05)
        f.put(0xF2, 0x80)
        assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == "RETURN"
        assert f.get(0x0200) == 0x06 and f.get(0x11) == 0x0A
        f.close()
        cases.append("lw-action-regression")

        # ------------------------------------------------------------------
        # 7. TravelPicker_LoadSelectedScreen ($0AB8C5) & ExecuteTransport
        # ------------------------------------------------------------------
        exec_addr = sym_addr("SpecialSoaring_ExecuteTransport")
        pal_armor = sym_addr("Palette_ArmorAndGloves")
        assert exec_addr is not None

        # Locked / OOB rejections -> cancel cleanup runs, returns C=0, hook jumps to WorldMap_ExitMap ($0ABC54)
        for cursor, sw_vis, sky in (
            (0, 0x00, 0x00),  # Korok locked
            (4, 0x00, 0x00),  # Crescent locked
            (5, 0x00, 0x00),  # Courage locked
            (6, 0x00, 0x00),  # Glacier locked
            (7, 0xFF, 0x00),  # Sky locked despite bit7 garbage in $7EF438
            (7, 0x7F, 0xA4),  # Sky locked with wrong token
            (8, 0x7F, 0xA5),  # OOB
            (0xFF, 0x7F, 0xA5),
        ):
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x07)
            f.put(0x1AF0, cursor)
            f.put(SW_VISITED_SRAM, sw_vis)
            f.put(SKY_LEARNED_SRAM, sky)
            f.put(LOAD_STEP_WRAM, 0x00)
            f.put(0x4B, 0x0C)
            f.put(0x02E4, 0x01)
            res = run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9))
            assert res == 0x0ABC54, (cursor, hex(sw_vis), hex(sky), hex(res))
            assert f.get(0x4B) == 0x00 and f.get(0x02E4) == 0x00
            cases.append(f"reject-{cursor:02x}-v{sw_vis:02x}-s{sky:02x}")
            f.close()

        # LW LoadSelectedScreen regression -> reads $7EF2BB and resumes at $0AB8C9
        f = fresh(area=0x2C, module=0x0E, sub=0x0A, step=0x07)
        f.put(0x7EF2BB, 0x5A)
        res = run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9))
        assert res == 0x0AB8C9 and (f.cpu.a & 0xFF) == 0x5A
        cases.append("lw-load-selected-regression")
        f.close()

        # All 8 valid Special Overworld landings via $0AB8C5 hook across 3 Module08 frames -> FadeInAndQuack ($0200=9)!
        boat_marker = sym_addr("Boat_Marker")
        for idx, label, area_id, cam_y, cam_x, link_y, link_x, origin, _px, _py, visit_bit in STOPS:
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x07)
            f.put(0x1AF0, idx)
            f.put(SW_VISITED_SRAM, visit_bit & 0x7F)
            f.put(SKY_LEARNED_SRAM, 0xA5 if idx == 7 else 0x00)
            f.put(LOAD_STEP_WRAM, 0x00)
            # Arm SpecialOverworld_MapSavedPos backup to verify restore!
            f.word(0x7EC133, 0x0412)
            f.word(0x7EC135, 0x0734)
            f.put(0x7EC137, 0x01)
            f.word(0x7EC108, 0x9999)
            f.word(0x7EC10A, 0x8888)
            # Dirty boat, swim, blink, Korok flag, stale map HDMA $7EC229
            if boat_marker is not None:
                f.word(boat_marker, 0x4254)
            f.put(0x0345, 0x01)
            f.put(0x0351, 0x01)
            f.put(0x02CB, 0x01)
            f.put(0x034F, 0x01)
            f.put(0x032A, 0x01)
            f.put(0x031F, 0x90)
            f.put(0x0AA5, 0x01)
            f.put(0x7EC229, 0x80)
            f.put(0x0130, 0x02)  # previous BGM track
            f.put(0x7F5B00 + area_id, 0x37)  # synthetic OverworldMusicCache entry (amb=3, song=7)

            mod08_subs = []

            def stub_mod08(fx):
                assert fx.get(0x10) == 0x08
                sub = fx.get(0x11)
                mod08_subs.append(sub)
                if sub == 0:
                    # Simulate Module08_00 loading $8A from $7EC140 and advancing $11 -> 1
                    fx.word(0x8A, read_word(fx, 0x7EC140))
                    fx.put(0x11, 0x01)
                elif sub == 1:
                    fx.put(0x11, 0x02)
                elif sub == 2:
                    fx.put(0x10, 0x10)
                    fx.put(0x11, 0x00)

            stubs = {MODULE08_OVERWORLD_LOAD: stub_mod08}
            if pal_armor is not None:
                stubs[pal_armor] = lambda fx: None

            # Frame 1: prepares $7EC140 cache + runs Module08 Sub 0
            assert run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9), jsl_stubs=stubs) == "RETURN"
            assert f.get(LOAD_STEP_WRAM) == 0x02
            assert f.get(0x10) == 0x0E and f.get(0x11) == 0x0A and f.get(0x0200) == 0x07
            assert read_word(f, 0x7EC140) == area_id
            assert read_word(f, 0x7EC142) == 0x0016
            assert read_word(f, 0x7EC144) == cam_y
            assert read_word(f, 0x7EC146) == cam_x
            assert read_word(f, 0x7EC148) == link_y
            assert read_word(f, 0x7EC14A) == link_x
            assert read_word(f, 0x7EC14C) == area_id
            assert read_word(f, 0x7EC14E) == origin
            assert read_word(f, 0x7EC150) == (link_y + 0x1F)
            assert read_word(f, 0x7EC152) == (link_x + 0x07)
            for off in (0x6A, 0x6C, 0x6E, 0x70):
                assert read_word(f, 0x7EC100 + off) == 0
            assert f.get(0x7EC137) == 0x00
            assert read_word(f, 0x7EC108) == 0x0412 and read_word(f, 0x7EC10A) == 0x0734
            if boat_marker is not None:
                assert read_word(f, boat_marker) == 0

            # Frame 2: runs Module08 Sub 1
            assert run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9), jsl_stubs=stubs) == "RETURN"
            assert f.get(LOAD_STEP_WRAM) == 0x03
            assert f.get(0x10) == 0x0E and f.get(0x11) == 0x0A and f.get(0x0200) == 0x07

            # Frame 3: runs Module08 Sub 2 -> loaded -> hands off to FluteMenu_FadeInAndQuack ($0200 = 9)!
            # Seed stray $27 + occupied slot 4 to prove landing duck slot is guaranteed free.
            f.put(0x0C4B, 0x27)
            f.put(0x0C4E, 0x0E)
            assert run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9), jsl_stubs=stubs) == "RETURN"
            assert mod08_subs == [0, 1, 2], (label, mod08_subs)
            assert f.get(LOAD_STEP_WRAM) == 0x00
            assert f.get(0x0C4B) == 0x00 and f.get(0x0C4E) == 0x00
            assert f.get(0x10) == 0x0E and f.get(0x11) == 0x0A and f.get(0x0200) == 0x09
            assert f.get(0x010C) == 0x09 and f.get(0x13) == 0x00 and f.get(0xB0) == 0x00
            assert f.get(0x7EC229) == 0x00  # clean HDMA mask saved for SpawnLandingDuck
            assert f.get(0x012F) == 0x10
            # Bird-carry locks kept armed until SpawnLandingDuck drops Link!
            assert f.get(0x4B) == 0x0C and f.get(0x5D) == 0x00
            assert f.get(0x02DA) == 0x01 and f.get(0x02E4) == 0x01
            assert f.get(0x037B) == 0x01 and f.get(0x02F9) == 0x01
            assert f.get(0x0345) == 0 and f.get(0x0351) == 0 and f.get(0x0AA5) == 0
            assert f.get(0x7EF3CA) == 0x00
            cases.append(f"transport-dropoff-stop-{idx}-{label.lower()}")
            f.close()

        # ------------------------------------------------------------------
        # 8. Cross-World Flip (SW <-> LW), MapPos Guard, ResolveMapWorld,
        #    Fallback Pin 1, Link Dot Hide + Toggle Badge, SW->LW Scrub
        # ------------------------------------------------------------------
        resolve_map = sym_addr("SpecialOverworld_ResolveMapWorld")
        save_mappos = sym_addr("SpecialOverworld_SaveAndSetMapPos")
        assert resolve_map is not None and save_mappos is not None

        # ResolveMapWorld respects Soaring_ViewWorld ONLY during Module $0E Sub $0A
        for mod, sub, area, orig, view, exp_w in (
            (0x0E, 0x0A, 0x83, 2, 0, 0),
            (0x0E, 0x0A, 0x2C, 0, 2, 2),
            (0x0E, 0x0A, 0x40, 1, 1, 1),
            (0x0E, 0x07, 0x83, 2, 0, 2),  # X world map ignores ViewWorld
            (0x0E, 0x07, 0x40, 0, 2, 1),
            (0x0E, 0x07, 0x2C, 2, 0, 0),
        ):
            f = fresh(area=area, module=mod, sub=sub)
            f.put(ORIGIN_WORLD_WRAM, orig)
            f.put(VIEW_WORLD_WRAM, view)
            assert run_until(f, resolve_map, db=0x0A) == "RETURN"
            assert (f.cpu.a & 0xFF) == exp_w, (mod, sub, area, orig, view, f.cpu.a)
            f.close()
        cases.append("resolve-map-world-3way")

        # SaveAndSetMapPos preserves backed-up MapSavedPos when MapSavedFlag == 1 (world-flip)
        f = fresh(area=0x83, module=0x0E, sub=0x0A)
        f.word(0x20, 0x0111)
        f.word(0x22, 0x0222)
        f.word(0x7EC108, 0xAAAA)
        f.word(0x7EC10A, 0xBBBB)
        f.put(0x7EC137, 0x01)
        f.word(0x7EC133, 0x0412)
        f.word(0x7EC135, 0x0734)
        p = f.cpu
        f.cpu.k = save_mappos >> 16
        # Execute via fresh run_until setting M=16, X=8 cleanly with wrapper? Wait:
        # run_until sets M=8, X=8; call SaveAndSetMapPos with M=16 wrapper on stack-less stub:
        # Patch temporary REP #$20 : JSL save_mappos : SEP #$20 : RTL at $5FFA00 in fixture RAM/ROM mirror
        f.put(0x7F8000, 0xC2); f.put(0x7F8001, 0x20)  # REP #$20
        f.put(0x7F8002, 0x22)
        f.put(0x7F8003, save_mappos & 0xFF); f.put(0x7F8004, (save_mappos >> 8) & 0xFF); f.put(0x7F8005, (save_mappos >> 16) & 0xFF)
        f.put(0x7F8006, 0xE2); f.put(0x7F8007, 0x20)  # SEP #$20
        f.put(0x7F8008, 0x6B)                         # RTL
        assert run_until(f, 0x7F8000, db=0x0A) == "RETURN"
        assert read_word(f, 0x7EC133) == 0x0412 and read_word(f, 0x7EC135) == 0x0734
        assert read_word(f, 0x7EC108) == 0x0111 and read_word(f, 0x7EC10A) == 0x0222
        f.close()
        cases.append("save-mappos-flip-guard")

        # LoadMap: world-flip reload from SW ($8C) to Kalyxo LW with TravelSpotsVisited==0 -> fallback Pin 1 ($1AF0==0)
        f = fresh(area=0x8C, module=0x0E, sub=0x0A, step=0x01)
        f.put(MAP_SWITCH_WRAM, 0x01)
        f.put(ORIGIN_WORLD_WRAM, 0x02)
        f.put(VIEW_WORLD_WRAM, 0x00)
        f.put(LW_VISITED_SRAM, 0x00)
        f.put(0x1AF0, 0x05)
        res = run_until(f, 0x0AB74B, stop_addrs=(0x0ABA30,))
        assert res == 0x0ABA30
        assert f.get(MAP_SWITCH_WRAM) == 0x00
        assert f.get(ORIGIN_WORLD_WRAM) == 0x02 and f.get(VIEW_WORLD_WRAM) == 0x00
        assert f.get(0x1AF0) == 0x00
        f.close()
        cases.append("sw-to-lw-fallback-pin1-loadmap")

        # CheckAction L/R/SELECT flip & Abyss lock
        for f4, f6, orig, view, sw_vis, sky, exp_flip, exp_view in (
            (0x00, 0x20, 2, 2, 0x00, 0x00, True, 0),   # SW->LW via L
            (0x00, 0x10, 2, 0, 0x00, 0x00, True, 2),   # LW->SW via R
            (0x20, 0x00, 0, 0, 0x02, 0x00, True, 2),   # LW->SW via SELECT (SW visited)
            (0x00, 0x20, 0, 0, 0x00, 0xA5, True, 2),   # LW->SW via L (Sky learned)
            (0x00, 0x20, 0, 0, 0x00, 0x00, False, 0),  # LW cannot flip when SW locked
            (0x00, 0x20, 1, 1, 0xFF, 0xA5, False, 1),  # Eon Abyss never flips
            (0x20, 0x00, 1, 1, 0xFF, 0xA5, False, 1),
        ):
            f = fresh(area=(0x83 if orig == 2 else (0x40 if orig == 1 else 0x2C)), module=0x0E, sub=0x0A, step=0x05)
            f.put(ORIGIN_WORLD_WRAM, orig)
            f.put(VIEW_WORLD_WRAM, view)
            f.put(SW_VISITED_SRAM, sw_vis)
            f.put(SKY_LEARNED_SRAM, sky)
            f.put(0xF4, f4)
            f.put(0xF6, f6)
            res = run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,))
            if exp_flip:
                assert res == "RETURN"
                assert f.get(VIEW_WORLD_WRAM) == exp_view
                assert f.get(MAP_SWITCH_WRAM) == 0x01
                assert f.get(0x0200) == 0x00
                assert f.get(0x012F) == 0x20
            else:
                assert res == 0x0AB79D
                assert f.get(VIEW_WORLD_WRAM) == exp_view
                assert f.get(MAP_SWITCH_WRAM) == 0x00
            f.close()
        cases.append("check-action-world-flip")

        # TravelPicker_LinkAndBadge ($0AB7D3): foreign view hides Link dot + draws badge; DW hides badge
        f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
        f.put(ORIGIN_WORLD_WRAM, 2); f.put(VIEW_WORLD_WRAM, 0); f.put(0x1A, 0x10)
        assert run_until(f, 0x0AB7D3, stop_addrs=(0x0AB7D9, 0x0AB7FD)) == 0x0AB7FD
        assert f.get(0x084E) == 0x0E and f.get(0x0A33) == 0x02
        assert f.get(0x084A) == 0x3D and f.get(0x0852) == 0x3D
        f.close()

        f = fresh(area=0x40, module=0x0E, sub=0x0A, step=0x05)
        f.put(ORIGIN_WORLD_WRAM, 1); f.put(VIEW_WORLD_WRAM, 1); f.put(0x1A, 0x10)
        assert run_until(f, 0x0AB7D3, stop_addrs=(0x0AB7D9, 0x0AB7FD)) == 0x0AB7D9
        assert f.get(0x084E) == 0x00  # badge hidden in Eon Abyss
        f.close()
        cases.append("link-dot-hide-and-badge")

        # ReturnToKalyxo scrub (SW Origin=2 -> LW View=0)
        f = fresh(area=0x8C, module=0x0E, sub=0x0A, step=0x07)
        f.put(ORIGIN_WORLD_WRAM, 2); f.put(VIEW_WORLD_WRAM, 0); f.put(MAP_SWITCH_WRAM, 0x01)
        f.put(LOAD_STEP_WRAM, 0x02)
        f.put(0x7EC137, 0x01); f.word(0x7EC133, 0x0333); f.word(0x7EC135, 0x0444)
        f.put(0x7EF3CA, 0x40); f.put(0x0FFF, 0x01)
        f.put(0x04CB, 0x22); f.put(0x7EC2F8, 0x33); f.put(0x0FC0, 0x05)
        f.put(0x8C, 0x94); f.put(0x1D, 0x02); f.put(0x9A, 0x72)
        f.put(0x0C4B, 0x27); f.put(0x0C4E, 0x11)
        res = run_until(f, 0x0AB8C5, stop_addrs=(0x0AB8C9,))
        assert res == 0x0AB8C9
        assert f.get(0x7EF3CA) == 0x00 and f.get(0x0FFF) == 0x00
        assert all(f.get(0x04CB + i) == 0xFE for i in range(8))
        assert all(f.get(0x7EC2F8 + i) == 0xFF for i in range(4))
        assert f.get(0x0FC0) == 0x00 and f.get(0x8C) == 0xFF and f.get(0x1D) == 0x00 and f.get(0x9A) == 0x00
        assert f.get(0x0C4B) == 0x00 and f.get(0x0C4E) == 0x00 and f.get(0x010C) == 0x09
        assert f.get(ORIGIN_WORLD_WRAM) == 0 and f.get(VIEW_WORLD_WRAM) == 0 and f.get(MAP_SWITCH_WRAM) == 0
        assert read_word(f, 0x7EC108) == 0x0333 and read_word(f, 0x7EC10A) == 0x0444
        f.close()
        cases.append("sw-to-lw-return-scrub")

        # ------------------------------------------------------------------
        # 9. Eon Abyss 8-Pin Soaring + GBC Rooster NMI ($4304 Restore!)
        # ------------------------------------------------------------------
        abyss_open = sym_addr("AbyssSoaring_Open")
        assert abyss_open is not None
        for area, opens in ((0x40, True), (0x63, True), (0x76, True), (0x3F, False), (0x80, False)):
            f = fresh(area=area, module=0x09, sub=0x00, step=0x00)
            bcalls = []
            def stub_abird(fx):
                bcalls.append(fx.cpu.a & 0xFF)
                fx.put(0x0C4E, fx.cpu.a & 0xFF)
            assert run_until(f, abyss_open, db=0x07, jsl_stubs={ADD_TRAVEL_BIRD: stub_abird}) == "RETURN"
            assert (len(bcalls) == 1) == opens
            f.close()
        cases.append("abyss-soaring-open")

        # MarkVisited across all 20 Eon Abyss areas
        f = fresh(area=0x00, module=0x09, sub=0x00, step=0x00)
        f.put(ABYSS_VISITED_SRAM, 0x00)
        seen_dw = 0
        for area, bit in ABYSS_VISIT_AREAS:
            f.word(0x040A, area)
            assert run_until(f, mark_addr, db=0x09, stop_addrs=(check_night,)) == check_night
            seen_dw |= bit
            assert f.get(ABYSS_VISITED_SRAM) == seen_dw
        assert seen_dw == 0xFF
        assert f.get(LW_VISITED_SRAM) == 0x00 and f.get(SW_VISITED_SRAM) == 0x00
        for non_dw in (0x42, 0x4A, 0x55, 0x70):
            f.put(ABYSS_VISITED_SRAM, 0x00)
            f.word(0x040A, non_dw)
            assert run_until(f, mark_addr, db=0x09, stop_addrs=(check_night,)) == check_night
            assert f.get(ABYSS_VISITED_SRAM) == 0x00
        f.close()
        cases.append("abyss-mark-visited-20-areas")

        # Abyss pins + transport ($40..$7F, SavedWorld=$40, $0FFF=$01)
        for idx, label, area_id, cam_y, cam_x, link_y, link_x, origin, pin_x, pin_y, visit_bit in ABYSS_STOPS:
            f = fresh(area=0x40, module=0x0E, sub=0x0A, step=0x05)
            f.put(ORIGIN_WORLD_WRAM, 1); f.put(VIEW_WORLD_WRAM, 1)
            f.put(ABYSS_VISITED_SRAM, 0xFC)
            f.put(0x1AF0, 0 if idx != 0 else 1)
            f.cpu.x = idx
            res = run_until(f, 0x0AB813, stop_addrs=(0x0AB844, 0x0AB890, 0x0AB8AA))
            assert res == 0x0AB890
            assert (f.get(0x1AB0 + idx) | (f.get(0x1AC0 + idx) << 8)) == pin_x
            assert (f.get(0x1AD0 + idx) | (f.get(0x1AE0 + idx) << 8)) == pin_y
            f.close()

            f = fresh(area=0x40, module=0x0E, sub=0x0A, step=0x07)
            f.put(ORIGIN_WORLD_WRAM, 1); f.put(VIEW_WORLD_WRAM, 1)
            f.put(ABYSS_VISITED_SRAM, 0xFC)
            f.put(0x1AF0, idx)
            f.put(0x7F5B00 + area_id, 0x25)
            stubs = {
                MODULE08_OVERWORLD_LOAD: lambda fx: fx.put(0x10, 0x10) if fx.get(0x11) == 2 else fx.put(0x11, fx.get(0x11) + 1),
                pal_armor: lambda fx: None,
            }
            for step in range(3):
                assert run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9), jsl_stubs=stubs) == "RETURN"
            assert read_word(f, 0x7EC140) == area_id
            assert read_word(f, 0x7EC144) == cam_y and read_word(f, 0x7EC146) == cam_x
            assert read_word(f, 0x7EC148) == link_y and read_word(f, 0x7EC14A) == link_x
            assert read_word(f, 0x7EC14E) == origin
            assert f.get(0x7EF3CA) == 0x40 and f.get(0x0FFF) == 0x01
            assert f.get(ORIGIN_WORLD_WRAM) == 0 and f.get(VIEW_WORLD_WRAM) == 0 and f.get(0x0200) == 0x09
            f.close()
        cases.append("abyss-8-pins-and-transport")

        # AbyssBird_SetPose ($08DF7F) & MaybeUploadBirdGraphicsToOam ($008B2A) $4304=$7E restore
        for area, raw_pose, exp_pose in (
            (0x40, 0x00, 0x01), (0x7F, 0x00, 0x01), (0x4B, 0x20, 0x20),
            (0x4B, 0x40, 0x40), (0x4B, 0xE0, 0xE0), (0x10, 0x00, 0x00), (0x83, 0x00, 0x00),
        ):
            idx = {0x00: 0, 0x20: 1, 0x40: 2, 0xE0: 3}[raw_pose]
            f = fresh(area=area)
            f.put(0x0AF4, 0x99)
            f.cpu.y = idx
            # $08DF7F replaces 6 bytes ending at $08DF85
            assert run_until(f, 0x08DF7F, db=0x08, stop_addrs=(0x08DF85,)) == 0x08DF85
            assert f.get(0x0AF4) == exp_pose
            f.close()

        # MaybeUploadBirdGraphicsToOam: M=8, X=16, X=$0040, $4304=$7E -> uploads 2x64B from Bank $5F
        # ($40E0/$41E0) and restores $4304=$7E and X=$0040 before jumping to $008B50!
        nmi_bird = sym_addr("MaybeUploadBirdGraphicsToOam")
        gbc_gfx_addr = sym_addr("GbcTravelBirdGfx")
        assert nmi_bird is not None and gbc_gfx_addr is not None
        gbc_bin = (Path(__file__).resolve().parents[1] / "Items/gfx/gbc_travel_bird.4bpp").read_bytes()
        for f_idx, pose in enumerate((0x01, 0x20, 0x40, 0xE0)):
            f = fresh(area=0x4B)
            f.put(0x0C4C, 0x27)
            f.put(0x0AF4, pose)
            f.cpu.k = nmi_bird >> 16; f.cpu.pc = nmi_bird & 0xFFFF
            f.cpu.db = 0x00; f.cpu.mf = True; f.cpu.xf = False; f.cpu.dp = 0; f.cpu.x = 0x0040
            for _ in range(500):
                if ((f.cpu.k << 16) | f.cpu.pc) == 0x008B50:
                    break
                f.lib.cpu_runOpcode(f.p)
            assert ((f.cpu.k << 16) | f.cpu.pc) == 0x008B50
            assert f.cpu.x == 0x0040
            mmio_4304 = [v for a_w, v in f.bad_writes if a_w == 0x004304]
            assert mmio_4304 == [gbc_gfx_addr >> 16, 0x7E], (pose, mmio_4304)
            # Reconstruct both 64B DMA transfers triggered by MDMAEN ($420B = 1)
            regs = {}
            dmas = []
            for a_w, v in f.bad_writes:
                regs[a_w] = v
                if a_w == 0x00420B and v == 0x01:
                    vm = regs[0x002116] | (regs[0x002117] << 8)
                    src = (regs[0x004304] << 16) | regs[0x004302] | (regs[0x004303] << 8)
                    sz = regs[0x004305] | (regs[0x004306] << 8)
                    pc = ((src >> 16) & 0x7F) * 0x8000 + (src & 0x7FFF)
                    dmas.append((vm, sz, rom[pc:pc + sz]))
            assert len(dmas) == 2 and dmas[0][0] == 0x40E0 and dmas[1][0] == 0x41E0
            assert dmas[0][1] == 64 and dmas[1][1] == 64
            assert dmas[0][2] + dmas[1][2] == gbc_bin[f_idx * 128 : (f_idx + 1) * 128]
            f.close()

        # Stale $0AF4 without live Ancilla $27 OR outside DW ($40..$7F) falls back to vanilla $008B30
        for area, slot_val, exp_dest in ((0x4B, 0x00, 0x008B30), (0x10, 0x27, 0x008B30), (0x83, 0x27, 0x008B30)):
            f = fresh(area=area)
            f.put(0x0C4C, slot_val); f.put(0x0AF4, 0x20)
            f.cpu.k = nmi_bird >> 16; f.cpu.pc = nmi_bird & 0xFFFF
            f.cpu.db = 0x00; f.cpu.mf = True; f.cpu.xf = False; f.cpu.dp = 0; f.cpu.x = 0x0040
            for _ in range(300):
                if ((f.cpu.k << 16) | f.cpu.pc) in (0x008B30, 0x008B50):
                    break
                f.lib.cpu_runOpcode(f.p)
            assert ((f.cpu.k << 16) | f.cpu.pc) == exp_dest
            f.close()
        cases.append("gbc-bird-nmi-and-pose")

        # ------------------------------------------------------------------
        # 10. Moosh Relocation (Song 6) + IsOcarina Z=0 + Y Hover + R Dismiss
        # ------------------------------------------------------------------
        epona_eff = sym_addr("OcarinaEffect_Epona")
        trans_moosh = sym_addr("Link_TransformMoosh")
        mb_is_oc = sym_addr("MaskBinding_IsOcarina")
        ib_is_oc = sym_addr("ItemBindings_IsOcarina")
        mb_tick = sym_addr("MaskBinding_Tick")
        prep_quake = sym_addr("PrepareQuakeSpell")
        player_trans = sym_addr("PlayerTransform")
        reset_gfx = sym_addr("ResetToLinkGraphics")
        hud_ref = sym_addr("HUD_RefreshLong")
        assert all(x is not None for x in (epona_eff, trans_moosh, mb_is_oc, ib_is_oc, mb_tick, prep_quake))

        # Song 6 outdoors in Eon Abyss ($40..$7F) calls Link_TransformMoosh and clears $03F0/$3A bit 6
        f = fresh(area=0x40)
        f.put(0x1B, 0x00); f.put(0x03F0, 0x80); f.put(0x3A, 0x40); f.put(0x012C, 0x00)
        moosh_calls = []
        assert run_until(f, epona_eff, db=0x07, jsl_stubs={trans_moosh: lambda fx: moosh_calls.append(1)}) == "RETURN"
        assert moosh_calls == [1]
        assert f.get(0x03F0) == 0x00 and (f.get(0x3A) & 0x40) == 0x00 and f.get(0x012C) == 0xF3
        f.close()

        # Indoors or in LW/SW does NOT transform into Moosh
        for area, ind in ((0x40, 0x01), (0x20, 0x00), (0x83, 0x00)):
            f = fresh(area=area); f.put(0x1B, ind)
            mc = []
            assert run_until(f, epona_eff, db=0x07, jsl_stubs={trans_moosh: lambda fx: mc.append(1), sym_addr("HorseCall_Long") or 0: lambda fx: None}) == "RETURN"
            assert mc == []
            f.close()

        # IsOcarina returns Z=0 for Moosh ($07) & Wolf ($03), Z=1 for Link ($00) & GBC ($06)
        for mask, exp_z in ((0x07, False), (0x03, False), (0x00, True), (0x06, True)):
            f = fresh(area=0x40)
            f.put(0x02B2, mask); f.put(0x0202, 0x0D)
            assert run_until(f, mb_is_oc, db=0x07) == "RETURN"
            assert f.cpu.z == exp_z, (hex(mask), f.cpu.z)
            assert run_until(f, ib_is_oc, db=0x07) == "RETURN"
            assert f.cpu.z == exp_z, (hex(mask), f.cpu.z)
            f.close()

        # MaskBinding_Tick: Moosh Y press -> PrepareQuakeSpell, clears $F4&$40, $0303==0; R press -> take_off
        f = fresh(area=0x40)
        f.put(0x02B2, 0x07); f.put(0x0202, 0x0D); f.put(0x0303, 0x0F); f.put(0x5D, 0x00); f.put(0xF4, 0x40)
        quakes = []
        assert run_until(f, mb_tick, db=0x07, jsl_stubs={prep_quake: lambda fx: quakes.append(1), hud_ref: lambda fx: None}) == "RETURN"
        assert quakes == [1] and f.get(0x0303) == 0x00 and (f.get(0xF4) & 0x40) == 0x00
        f.close()

        f = fresh(area=0x40)
        f.put(0x02B2, 0x07); f.put(0x0202, 0x0D); f.put(0x0303, 0x00); f.put(0xF6, 0x10)
        offs = []
        assert run_until(f, mb_tick, db=0x07, jsl_stubs={player_trans: lambda fx: offs.append("p"), reset_gfx: lambda fx: offs.append("r"), hud_ref: lambda fx: None}) == "RETURN"
        assert offs == ["p", "r"]
        f.close()
        cases.append("moosh-relocation-isocarina-yhover-rdismiss")

    result = {
        "passed": True,
        "case_count": len(cases),
        "cases": cases,
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "scope": "Compiled 65816 proof for 8-pin spread Lyra Sea Soaring, visited-unlocks, real Travel Bird pickup & drop-off, cancel cleanup, and LW Bird Travel non-regression.",
    }
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
