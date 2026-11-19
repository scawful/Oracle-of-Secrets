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
LW_VISITED_SRAM = 0x7EF412
SKY_LEARNED_SRAM = 0x7EF3B2
LOAD_STEP_WRAM = 0x7EC13E
ADD_TRAVEL_BIRD = 0x0994FE
MODULE08_OVERWORLD_LOAD = 0x0283BF


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
