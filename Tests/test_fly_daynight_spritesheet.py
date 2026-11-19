#!/usr/bin/env python3
"""Compiled 65816 proof for Day/Night/Peacetime $7EFCC0/$7EFD40 sprite-sheet &
sprite-palette refresh during Overworld screen scroll AND Bird Travel fly-in.

Exercises the REAL compiled ROM routines via Lakesnes 65816 CPU core:
  - Overworld_LoadGFXAndScreenSize ($02AB08) -> Overworld_LoadMapProperties_Interupt
    ($02AB0D) -> Overworld_SyncSpriteGfxPhase -> Sprite_LoadGraphicsProperties ($00FC62)
    -> Sprite_LoadGfxProperties_Interupt -> Oracle_CheckIfNight
  - FluteMenu_LoadTransport ($02EC39) -> Overworld_LoadNewScreenProperties ($02E58B)
    -> Overworld_LoadGFXAndScreenSize ($02AB08)
  - FluteMenu_LoadSelectedScreenPalettes ($02ECDD) -> $02ECE2 ($7EFD40, X -> $00)

Verifies:
  1. Day -> Night OW scroll onto OW $2D refreshes $0AA3 & $7EFD40[$2D] to p2 (Night)
  2. Night -> Day OW scroll onto OW $2D refreshes $0AA3 & $7EFD40[$2D] to p1 (Day)
  3. Pre-D2 -> Peacetime OW scroll onto OW $2E, $2F (Crystals & $10) & OW $1E
     (Crystals & $20) refreshes $0AA3 & $7EFD40 to p0 (Peacetime), even at night!
  4. Peacetime -> Normal OW scroll ($2E -> $2D) restores live Day/Night tables
  5. Bird Travel fly-in (FluteMenu_LoadTransport + FluteMenu_LoadSelectedScreenPalettes)
     for Day, Night, and Peacetime loads fresh $0AA3 AND passes fresh $00 sprite palette
     into OverworldPalettesLoader (never reading stale $7EFCC0/$7EFD40!)
  6. Special Overworld ($83, $A0, $A8, $B0, $A6, $8C) preserves registers/DBR/P and
     populates exact SW $0AA3 & refreshes $7EFDC0 ($80-$9F) cleanly
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import lyra_native_loaders as lnl  # noqa: E402

OW_SPR_GFX_PC = 0x007A41  # LW ph0 (+0), ph1 (+$40), ph2 (+$80)
OW_SPR_PAL_PC = 0x007B41
SW_SPR_GFX_PC = 0x0166E1  # $80-$9F

# Addresses in Bank $02
ADDR_LOAD_MAP_PROPS = 0x02AB08
ADDR_FLUTE_TRANSPORT = 0x02EC39
ADDR_FLUTE_PALETTES = 0x02ECDD
ADDR_FLUTE_SCREEN_IDS_PC = 0x016AE5  # $02EAE5 (8 words)

# WRAM addresses (Core/structs.asm TimeState $7EE000, Core/sram.asm)
TIMESTATE_HOURS = 0x7EE000
TIMESTATE_GFX_LAST_AREA = 0x7EE003
TIMESTATE_GFX_LAST_PHASE = 0x7EE005
TIMESTATE_GFX_DIRTY = 0x7EE007
GAMESTATE_ADDR = 0x7EF3C5
CRYSTALS_ADDR = 0x7EF37A


def rom_lw_meta(rom: bytes, area: int, phase: int) -> tuple[int, int]:
    return (
        rom[OW_SPR_GFX_PC + area + phase * 0x40],
        rom[OW_SPR_PAL_PC + area + phase * 0x40],
    )


def call_routine(f: Fixture, entry: int, *, long_return: bool, db: int = 0x02,
                 stop_stubs: dict[int, callable] | None = None, limit: int = 60000):
    p = f.cpu
    p.k = entry >> 16
    p.pc = entry & 0xFFFF
    p.db = db
    p.mf = True
    p.xf = True
    p.dp = 0
    initial_sp = p.sp
    sentinel_addr = (entry & 0xFF0000) | 0x7000
    frame = [entry >> 16, 0x6F, 0xFF] if long_return else [0x6F, 0xFF]
    for v in frame:
        f.put(p.sp, v)
        p.sp -= 1
    stubs = stop_stubs or {}
    for _ in range(limit):
        cur = (p.k << 16) | p.pc
        if cur == sentinel_addr:
            assert p.sp == initial_sp, (hex(entry), "stack drift", hex(p.sp), hex(initial_sp))
            assert not f.bad_writes, (hex(entry), "unexpected non-WRAM writes", f.bad_writes)
            return
        if cur in stubs:
            is_long = stubs[cur](f)
            # Simulate RTS or RTL cleanly
            lo = f.get(p.sp + 1)
            hi = f.get(p.sp + 2)
            if is_long:
                bank = f.get(p.sp + 3)
                p.sp += 3
                p.k = bank
            else:
                p.sp += 2
            p.pc = ((hi << 8) | lo) + 1
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
    kydrog_removed = labels.get("Oracle_KydrogFaroreRemoved") or labels.get("KydrogFaroreRemoved")
    assert kydrog_removed is not None, "KydrogFaroreRemoved symbol missing"
    assert "Overworld_SyncSpriteGfxPhase" in labels, "Overworld_SyncSpriteGfxPhase symbol missing"
    native_tables: dict[str, int] = {}
    dir_info = lnl.read_native_directory(rom, experimental_page_tile16=True)
    if dir_info is not None:
        _, _, dir_entries = dir_info
        for idx, (tname, *_rest) in enumerate(lnl.CURRENT_TABLE_SPECS):
            eid = idx + 1 if idx < 28 else idx + 2
            if eid in dir_entries:
                native_tables[tname] = ctp.snes_to_pc(dir_entries[eid][0])

    cases: list[str] = []
    with tempfile.TemporaryDirectory(prefix="fly-daynight-cpu-") as tmp:
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

        def make_fixture(*, area: int, hours: int, game_state: int = 2,
                         crystals: int = 0, poison: int = 0xAA) -> Fixture:
            f = Fixture(lib, rom, labels)
            f.put(0x8A, area)
            f.put(0x040A, area)
            f.put(GAMESTATE_ADDR, game_state)
            f.put(kydrog_removed, 1)  # Post-ambush so night phase ($03) is active
            f.put(TIMESTATE_HOURS, hours)
            f.put(CRYSTALS_ADDR, crystals)
            f.put(TIMESTATE_GFX_DIRTY, 1)
            # Poison $7EFCC0..$7EFDFF so any stale read is caught immediately!
            for off in range(0x140):
                f.put(0x7EFCC0 + off, poison)
            return f

        # ------------------------------------------------------------------
        # 1. Day -> Night OW scroll onto OW $2D
        # ------------------------------------------------------------------
        f = make_fixture(area=0x2D, hours=0x13)  # 19:00 Night
        call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
        exp_sg, exp_sp = rom_lw_meta(rom, 0x2D, 2)
        assert f.get(0x0AA3) == exp_sg, (hex(f.get(0x0AA3)), hex(exp_sg))
        assert f.get(0x7EFCC0 + 0x2D) == exp_sg
        assert f.get(0x7EFD40 + 0x2D) == exp_sp, (hex(f.get(0x7EFD40 + 0x2D)), hex(exp_sp))
        assert f.get(TIMESTATE_GFX_LAST_AREA) == 0x2D
        assert f.get(TIMESTATE_GFX_LAST_PHASE) == 0x03
        assert f.get(TIMESTATE_GFX_DIRTY) == 0
        cases.append("ow-scroll-day-to-night-2D")
        f.close()

        # ------------------------------------------------------------------
        # 2. Night -> Day OW scroll onto OW $2D
        # ------------------------------------------------------------------
        f = make_fixture(area=0x2D, hours=0x0A)  # 10:00 Day
        call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
        exp_sg, exp_sp = rom_lw_meta(rom, 0x2D, 1)
        assert f.get(0x0AA3) == exp_sg
        assert f.get(0x7EFD40 + 0x2D) == exp_sp
        assert f.get(TIMESTATE_GFX_LAST_AREA) == 0x2D
        assert f.get(TIMESTATE_GFX_LAST_PHASE) == 0x02
        assert f.get(TIMESTATE_GFX_DIRTY) == 0
        cases.append("ow-scroll-night-to-day-2D")
        f.close()

        # ------------------------------------------------------------------
        # 3. Pre-D2 -> Peacetime OW scroll (OW $2E, $2F w/ $10; OW $1E w/ $20)
        #    Tested at BOTH Day (10:00) AND Night (20:00)!
        # ------------------------------------------------------------------
        for area, crystal_mask in ((0x2E, 0x10), (0x2F, 0x10), (0x1E, 0x20)):
            exp_p0_sg, exp_p0_sp = rom_lw_meta(rom, area, 0)
            for label_t, hour in (("day", 0x0A), ("night", 0x14)):
                f = make_fixture(area=area, hours=hour, crystals=crystal_mask)
                call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
                assert f.get(0x0AA3) == exp_p0_sg, (hex(area), label_t, hex(f.get(0x0AA3)), hex(exp_p0_sg))
                assert f.get(0x7EFD40 + area) == exp_p0_sp, (hex(area), label_t, hex(f.get(0x7EFD40 + area)), hex(exp_p0_sp))
                assert f.get(TIMESTATE_GFX_LAST_AREA) == area
                assert f.get(TIMESTATE_GFX_LAST_PHASE) == 0x01
                assert f.get(TIMESTATE_GFX_DIRTY) == 0
                cases.append(f"ow-scroll-peacetime-{area:02x}-{label_t}")
                f.close()

        # ------------------------------------------------------------------
        # 4. Peacetime ($2E) -> Normal ($2D) scroll restores live Day & Night!
        # ------------------------------------------------------------------
        for label_t, hour, phase_idx, exp_phase_code in (
            ("day", 0x0A, 1, 0x02),
            ("night", 0x15, 2, 0x03),
        ):
            f = make_fixture(area=0x2E, hours=hour, crystals=0x10)
            call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
            assert f.get(TIMESTATE_GFX_LAST_PHASE) == 0x01
            # Now scroll onto OW $2D (same session RAM!)
            f.put(0x8A, 0x2D)
            f.put(0x040A, 0x2D)
            call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
            exp_sg, exp_sp = rom_lw_meta(rom, 0x2D, phase_idx)
            assert f.get(0x0AA3) == exp_sg
            assert f.get(0x7EFD40 + 0x2D) == exp_sp
            assert f.get(TIMESTATE_GFX_LAST_AREA) == 0x2D
            assert f.get(TIMESTATE_GFX_LAST_PHASE) == exp_phase_code
            cases.append(f"ow-scroll-peace-to-normal-2D-{label_t}")
            f.close()

        # ------------------------------------------------------------------
        # 5. Bird Travel fly-in (FluteMenu_LoadTransport $02EC39 +
        #    FluteMenu_LoadSelectedScreenPalettes $02ECDD)
        #    Test EVERY Light World flute stop at Day, Night, AND Peacetime!
        # ------------------------------------------------------------------
        flute_areas = [
            rom[ADDR_FLUTE_SCREEN_IDS_PC + i * 2] | (rom[ADDR_FLUTE_SCREEN_IDS_PC + i * 2 + 1] << 8)
            for i in range(8)
        ]
        # Pick stops that differ between Day/Night or trigger Peacetime!
        # Always test stop 4 (check actual area IDs from ROM!) plus any stop with p1!=p2
        test_stops = []
        for idx, area in enumerate(flute_areas):
            if area < 0x40:
                p0 = rom_lw_meta(rom, area, 0)
                p1 = rom_lw_meta(rom, area, 1)
                p2 = rom_lw_meta(rom, area, 2)
                if p1 != p2 or area in (0x1E, 0x2E, 0x2F) or idx == 0:
                    test_stops.append((idx, area))
        assert test_stops, "No Light World flute stops found"

        # Resolve Bank $02 stub targets used by FluteMenu_LoadTransport & LoadSelectedScreenPalettes
        # $02ECCF: JSL Sprite_ResetAll ($09C44E), $02ECD3: JSL Sprite_ReloadAll_Overworld ($09C4AC)
        # $02ECD9: JSR DeleteCertainAncillaeStopDashing ($02EFB9)
        # $02ECDD: JSR OverworldLoadScreensPaletteSet ($02C692)
        # $02ECEC: JSL OverworldPalettesLoader ($0ED5A8 or SpecialPaletteLoadCompleteBuffer)
        # $02ECF0: JSL Overworld_SetScreenBGColor ($0ED5D8)
        # $02ECF4: JSR Overworld_CopyPalettesToCache_WithPrep ($02C763)
        def read_call_target(pc_snes: int) -> int:
            pc = ctp.snes_to_pc(pc_snes)
            op = rom[pc]
            if op == 0x22:  # JSL
                return rom[pc + 1] | (rom[pc + 2] << 8) | (rom[pc + 3] << 16)
            if op == 0x20:  # JSR
                return (pc_snes & 0xFF0000) | rom[pc + 1] | (rom[pc + 2] << 8)
            raise AssertionError((hex(pc_snes), hex(op)))

        t_spr_reset = read_call_target(0x02ECCF)
        t_spr_reload = read_call_target(0x02ECD3)
        t_del_anc = read_call_target(0x02ECD9)
        t_load_scr_pal = read_call_target(0x02ECDD)
        t_pal_loader = read_call_target(0x02ECEC)
        t_bg_color = read_call_target(0x02ECF0)
        t_copy_pal = read_call_target(0x02ECF4)

        for idx, area in test_stops:
            scenarios = [
                ("day", 0x0A, 0x00, 1),
                ("night", 0x15, 0x00, 2),
            ]
            if area in (0x2E, 0x2F):
                scenarios.append(("peacetime", 0x15, 0x10, 0))
            elif area == 0x1E:
                scenarios.append(("peacetime", 0x15, 0x20, 0))

            for tag, hour, crystals, exp_phase in scenarios:
                f = make_fixture(area=0x00, hours=hour, crystals=crystals)
                f.word(0x1AF0, idx)
                captured_pal_arg = []

                def on_pal_loader(fx):
                    captured_pal_arg.append(fx.get(0x00))
                    return True  # RTL

                stubs = {
                    t_spr_reset: lambda fx: True,
                    t_spr_reload: lambda fx: True,
                    t_del_anc: lambda fx: False,
                    t_load_scr_pal: lambda fx: False,
                    t_pal_loader: on_pal_loader,
                    t_bg_color: lambda fx: True,
                    t_copy_pal: lambda fx: False,
                }
                # Step A: FluteMenu_LoadTransport ($02EC39)
                call_routine(f, ADDR_FLUTE_TRANSPORT, long_return=True, stop_stubs=stubs)
                exp_sg, exp_sp = rom_lw_meta(rom, area, exp_phase)
                assert f.get(0x8A) == area, (idx, hex(f.get(0x8A)), hex(area))
                assert f.get(0x0AA3) == exp_sg, (
                    f"Bird Travel stop {idx} area 0x{area:02X} ({tag}): "
                    f"$0AA3=0x{f.get(0x0AA3):02X} != expected 0x{exp_sg:02X}"
                )
                assert f.get(0x7EFD40 + area) == exp_sp

                # Step B: FluteMenu_LoadSelectedScreenPalettes ($02ECDD)
                call_routine(f, ADDR_FLUTE_PALETTES, long_return=True, stop_stubs=stubs)
                assert captured_pal_arg == [exp_sp], (
                    f"Bird Travel palette stop {idx} area 0x{area:02X} ({tag}): "
                    f"$00={captured_pal_arg} != expected [0x{exp_sp:02X}]"
                )
                cases.append(f"bird-travel-stop{idx}-area{area:02x}-{tag}")
                f.close()

        # ------------------------------------------------------------------
        # 6. Special Overworld areas ($83, $8C, $A0, $A6, $A8, $B0) via $02AB08
        # ------------------------------------------------------------------
        for area in (0x83, 0x8C, 0xA0, 0xA6, 0xA8, 0xB0):
            f = make_fixture(area=area, hours=0x0A)
            call_routine(f, ADDR_LOAD_MAP_PROPS, long_return=False)
            if area < 0xA0:
                exp_sg = rom[SW_SPR_GFX_PC + (area - 0x80)]
                exp_sp = rom[0x016701 + (area - 0x80)]
                # ExpandedSpritePalArray ($7EFDC0) also refreshed by $00FC62!
                assert f.get(0x7EFD40 + area) == exp_sp, (hex(area), hex(f.get(0x7EFD40 + area)), hex(exp_sp))
            else:
                exp_sg = rom[native_tables["special_sprite_gfx_phase1"] + area]
            assert f.get(0x0AA3) == exp_sg, (hex(area), hex(f.get(0x0AA3)), hex(exp_sg))
            assert f.get(TIMESTATE_GFX_LAST_AREA) == area
            assert f.get(TIMESTATE_GFX_DIRTY) == 0
            cases.append(f"special-ow-load-{area:02x}")
            f.close()

    result = {
        "passed": True,
        "case_count": len(cases),
        "cases": cases,
        "flute_areas": [f"0x{x:02X}" for x in flute_areas],
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "scope": "Compiled 65816 proof for OW scroll, Peacetime, Bird Travel fly-in, and Special OW sprite-sheet/palette phase sync.",
    }
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
