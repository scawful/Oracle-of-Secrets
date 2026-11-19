#!/usr/bin/env python3
"""Compiled 65816 unit tests for Whirlpool ($11 == #$2E) GFX, DMA, BG color & overlay fixes.

Assembles the real ASM routines extracted from Overworld/ZSCustomOverworld.asm
with Asar and executes them on the LakeSnes 65816 CPU:
  1. NewOverworld_FinishTransGfx (.whirpool -> .loadAnimated):
     - Schedules animated tile upload via NMI ($17 = #$06 -> NewNMITarget1=$0134,
       NewNMISource1=$0ADC, NewNMICount1=#$0400, NewNMICount2=0) with ZERO direct
       writes to PPU/DMA registers ($2116/$4300/$420B).
     - Safely skips scheduling when $0134 == 0 or $0ADC < #$8000.
  2. NMI_UpdateChr_Bg2HalfAndAnimatedLONG:
     - Uses bank $7E and size #$0400 when NewNMISource1 >= #$8000 (Whirlpool animated
       upload), always setting VMAIN=#$80 and DMA0MODE=#$1801 and clearing $0710.
     - Uses bank $7F and NewNMICount1/2 for regular BG CHR sheets (< #$8000).
  3. ResolveDefaultOWGFXSheet8 + BlockGFXCheck + NewLoadTransAuxGFX + LoadTransMainGFX
     + Whirlpool_LoadDestinationMap_Interupt:
     - $FF sentinel resolves to LW/DW/SW Pool_DefaultGFXGroups ($3D/$3E LW, $45/$3F DW,
       $3D/$3E SW) across BlockGFXCheck, NewLoadTransAuxGFX, and LoadTransMainGFX.
     - BlockGFXCheck on FIELD $15 from Docks $30 reloads Slots 3, 4, 5, 6 and updates
       PriorSheets to [$3A,$3B,$3C,$3D,$51,$4E,$3E,$5B].
     - NewLoadTransAuxGFX Whirlpool multi-frame re-entry ($11=#$2E, TransGFXModuleFrame!=0)
       skips re-decompression, sets $04=0, preserves TransGFXModuleFrame, and keeps the
       stack balanced (matching $00D66E caller PHB + own PHB).
     - Whirlpool_LoadDestinationMap_Interupt ($02B490) clears TransGFXModuleFrame and
       invalidates PriorSheets[3..6] to #$FE while preserving #$FF entries.
  4. Whirlpool_ReloadSubscreenOverlay_Interupt ($02B47E):
     - Resets stale source R/G fixed-color mirrors ($9C=#$20, $9D=#$40).
     - When destination $8C == #$FF, populates $7F4000..$7F407F with safe BG1 tilemap
       addresses ($1000..$1FC0) so $02B482/$02B48A ($17=#$0C/$0D) never corrupt BG CHR/OBJ.
     - When $8C != #$FF, preserves existing $7F4000..$7F407F overlay upload targets.
  5. CheckForChangeGraphicsTransitionLoad ($11=#$2E vs #$02 vs #$0F):
     - Whirlpool ($11=#$2E): routes to buffer-only .mosaic (Palette_OverworldBgMain,
       Oracle_MosaicFix, Oracle_SpecialOverworldPaletteCompleteBuffer) and skips
       direct-DMA Oracle_DocksNormalLoad.
     - Normal OW scroll ($11=#$02): keeps live Palette_OverworldBgMain2,
       Oracle_BackgroundFix, and CompleteBoth (non-regression).
     - Mosaic transition ($11=#$0F): runs .mosaic AND Oracle_DocksNormalLoad (non-regression).
  6. Whirlpool $B0=9 palette/backdrop hooks & ReplaceBGColor:
     - ReplaceBGColor uses Oracle_MosaicFix (buffer-only) for $11=#$2E and
       Oracle_BackgroundFix for non-Whirlpool ($11=#$00/#$02).
     - $02B4D1 calls SpecialPaletteLoadFinishBuffer (CompleteBuffer, not CompleteBoth).
     - $02B4D5 calls Overworld_SetScreenBGColorCacheOnly ($0ED61D).
     - $02B4DD calls Whirlpool_LoadSpritesAndFinishPalettes ($00E031 -> $02B4E5),
       skipping $02B4E1 (LDA #$80 : STA $9E) so destination COLDATA $9E is preserved.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

ASAR = shutil.which("asar")
LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]


def _find_lakesnes() -> Path | None:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def _build_cpu_lib(temp_dir: Path) -> C.CDLL:
    lakesnes = _find_lakesnes()
    assert lakesnes is not None, "LakeSnes checkout not found (set LAKESNES_DIR)"
    dll = temp_dir / "cpu.dylib"
    subprocess.run(
        [
            "cc", "-shared", "-fPIC", "-O2",
            str(lakesnes / "snes" / "cpu.c"),
            str(lakesnes / "snes" / "statehandler.c"),
            "-o", str(dll),
        ],
        check=True,
    )
    lib = C.CDLL(str(dll))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def _extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]


def _assemble_whirlpool_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    zs = (ROOT / "Overworld" / "ZSCustomOverworld.asm").read_text(encoding="utf-8")

    finish_and_block_and_check = _extract_block(
        zs,
        "NewOverworld_FinishTransGfx:",
        "    SkipOverworld_FinishTransGfx_firstHalf:\n\n    ; Move on to next submodule.\n    INC.b $11\n\n    RTS\n}",
    )
    load_main_gfx = _extract_block(
        zs,
        "LoadTransMainGFX:",
        "    .noBgGfxChange7\n\n    RTS\n}",
    )
    replace_bg_color = _extract_block(
        zs,
        "ReplaceBGColor:",
        "    .disabled\n    REP #$20\n    PLB\n    RTL\n}",
    )
    new_load_aux_and_nmi = _extract_block(
        zs,
        "NewLoadTransAuxGFX:",
        "    STZ.w $0710\n\n    PLB\n\n    RTL\n}",
    )
    whirlpool_hooks_block = _extract_block(
        zs,
        "if !Func02AF58 == 1\n\norg $02B47E",
        "Whirlpool_LoadSpritesAndFinishPalettes:\n{\n    JSL.l $00E031 ; LoadNewSpriteGFXSet (replaced call)\n    JML.l $02B4E5 ; Whirlpool_SetBrightness (preserve $02B4D9's COLDATA $9E)\n}",
    )
    mirror_table_block = _extract_block(
        zs,
        "MirrorWarp_NoOverlayUploadTable:",
        "    PLP\n\n    RTL\n}",
    )
    palette_hook_block = _extract_block(
        zs,
        "org $02B4D1 ; @hook module=Overworld name=SpecialPaletteWhirlpoolComplete kind=jsl target=SpecialPaletteLoadFinishBuffer",
        "assert pc() <= $02B4D5",
    )
    palette_adapter_block = _extract_block(
        zs,
        "SpecialPaletteLoadFinishBuffer:",
        "    JSL Oracle_SpecialOverworldPaletteCompleteBuffer\n    RTL",
    )

    image = bytearray(b"\x00" * 0x280000)
    # Pre-seed vanilla $02B4E1..$02B4EE tail for Whirlpool_LoadSpritesAndFinishPalettes test:
    # $02B4E1: LDA #$80 : STA $9E (must be SKIPPED by $02B4DD hook!)
    # $02B4E5: LDA #$0F : STA $13 : INC $0710 : INC $B0 : RTS
    image[_snes_to_pc(0x02B4E1):_snes_to_pc(0x02B4E5)] = bytes.fromhex("A980859E")
    image[_snes_to_pc(0x02B4E5):_snes_to_pc(0x02B4EF)] = bytes.fromhex("A90F8513EE1007E6B060")

    rom_path = folder / "whirlpool_fix_test.sfc"
    rom_path.write_bytes(image)

    harness = f'''lorom
incsrc "Overworld/HardwareRegisters.asm"

!SPECIAL_OVERWORLD_NATIVE = 0
!SPECIAL_OVERWORLD_RESOURCES_ENABLED = 0
!SPECIAL_OVERWORLD_PALETTE_ENABLED = 1
!ENABLE_KALYXO_DOCKS_PROFILE = 1
!ENABLE_SKY_OVERWORLD_ROUTE = 0
!Func02AF58 = 1
!Func00E221 = 1
!Func0ED627 = 1
!Func0BFEB6 = 1

TransGFXModule_PriorSheets = $04CB
NewNMITarget1              = $04D3
NewNMISource1              = $04D5
NewNMICount1               = $04D7
NewNMITarget2              = $04D9
NewNMISource2              = $04DB
NewNMICount2               = $04DD
TransGFXModuleFrame        = $0CF3
AnimatedTileGFXSet         = $0FC0

; Call counter scratch in free WRAM ($7E0F00..$7E0F7F):
;   $0F00 = Palette_OverworldBgMain count
;   $0F02 = Palette_OverworldBgMain2 count
;   $0F04 = Oracle_BackgroundFix count
;   $0F06 = Oracle_MosaicFix count
;   $0F08 = Oracle_SpecialOverworldPaletteCompleteBuffer count
;   $0F0A = Oracle_SpecialOverworldPaletteCompleteBoth count
;   $0F0C = Oracle_DocksNormalLoad count
;   $0F0E = Overworld_LoadPalettes count
;   $0F10 = Overworld_SetScreenBGColorCacheOnly ($0ED61D) count
;   $0F12 = Palette_SetOwBgColor_Long ($0ED618) count
;   $0F14 = LoadNewSpriteGFXSet ($00E031) count
;   $0F16 = Overworld_ReloadSubscreenOverlayAndAdvance count
;   $0F18 = BirdTravel_LoadAmbientOverlay count
;   $0F1A = Decomp_bg_variableLONG count (and log of Y sheets at $0F40+)
;   $0F1C = PrepTransMainGFX count
;   $0F1E = LoadTransAuxGFX_sprite_continue count
;   $0F20 = DecompOwAnimatedTiles count
;   $0F22 = $00D673 normal-load fallback count

; Engine hook addresses used by Whirlpool routines
org $00D66E
Test_CallNewLoadTransAuxGFX:
  PHB
  JML NewLoadTransAuxGFX

org $00D673
LoadTransAuxGFX_normal_fallback:
  INC.w $0F22
  PLB
  RTL

org $00D706
LoadTransAuxGFX_sprite_continue:
  INC.w $0F1E
  PLB
  RTL

org $00E031
LoadNewSpriteGFXSet:
  INC.w $0F14
  RTL

org $02B1F4
Overworld_ReloadSubscreenOverlayAndAdvance:
  INC.w $0F16
  RTL

org $0AB948
BirdTravel_LoadAmbientOverlay:
  INC.w $0F18
  RTL

org $0ED5A8
Overworld_LoadPalettes:
  INC.w $0F0E
  RTL

org $0ED618
Palette_SetOwBgColor_Long:
  INC.w $0F12
  RTL

org $0ED61D
Overworld_SetScreenBGColorCacheOnly:
  INC.w $0F10
  RTL

; Test entry wrappers in Bank $02 (calls $02B4D1, $02B4D5, $02B4DD directly)
org $029000
Test_Call02B47E:
  JSR $B47E
  RTL

Test_Call02B490:
  JSR $B490
  RTL

Test_Call02B4D1:
  JSR $B4D1
  RTL

Test_Call02B4D5:
  JSR $B4D5
  RTL

Test_Call02B4DD:
  JSR $B4DD
  RTL

; Put RTS right after each 4-byte JSL hook so JSR wrappers isolate each site!
org $02B482
  RTS
org $02B494
  RTS
org $02B4D5
  ; filled below by hook
org $02B4D9
  RTS

; Bank $28: extracted ZSCustomOverworld routines + tables + test wrappers
org $288000

; Wrappers for RTS-terminated Bank $28 subroutines
Test_CallResolveDefault8:
  PHB : PHK : PLB
  JSR ResolveDefaultOWGFXSheet8
  PLB
  RTL

Test_CallBlockGFXCheck:
  PHB : PHK : PLB
  JSR BlockGFXCheck
  PLB
  RTL

Test_CallCheckForChangeGraphics:
  PHB : PHK : PLB
  JSR CheckForChangeGraphicsTransitionLoad
  PLB
  RTL

Test_CallLoadTransMainGFX:
  PHB : PHK : PLB
  JSR LoadTransMainGFX
  PLB
  RTL

{finish_and_block_and_check}

{load_main_gfx}

{replace_bg_color}

{new_load_aux_and_nmi}

pushpc
{whirlpool_hooks_block}

{mirror_table_block}

; SpecialPaletteWhirlpoolComplete hook ($02B4D1) + adapter
pushpc
{palette_hook_block}
pullpc
{palette_adapter_block}

; Ensure $02B4D5 hook returns when called via Test_Call02B4D5 (put RTS at $02B4D9)
; and $02B4D1 hook returns when called via Test_Call02B4D1 (we call JSL target or wrapper).
; Note: $02B4D1 falls into $02B4D5 in real ROM, so Test_Call02B4D1_and_D5 tests both in sequence!

; Stubbed external helpers & compact test tables in Bank $28
PrepTransMainGFX:
  INC.w $0F1C
  RTS

ReadAnimatedTable:
  LDA.l $7E0F30
  RTL

DecompOwAnimatedTiles:
  INC.w $0F20
  RTL

Decomp_bg_variableLONG:
  PHP
  SEP #$30
  PHX
  LDX.w $0F1A
  TYA
  STA.w $0F40, X
  INC.w $0F1A
  PLX
  PLP
  RTL

Palette_OverworldBgMain:
  INC.w $0F00
  RTL

Palette_OverworldBgMain2:
  INC.w $0F02
  RTL

Oracle_ReadOverworldBackdropColor:
  LDA.w #$45EE
  RTL

Oracle_BackgroundFix:
  INC.w $0F04
  RTL

Oracle_MosaicFix:
  INC.w $0F06
  RTL

Oracle_SpecialOverworldPaletteBegin:
  RTL

Oracle_SpecialOverworldPaletteCompleteBuffer:
  INC.w $0F08
  RTL

Oracle_SpecialOverworldPaletteCompleteBoth:
  INC.w $0F0A
  RTL

Oracle_DocksNormalLoad:
  INC.w $0F0C
  RTL

; Pass-through mock for Docks sheet resolver (keeps sheet in A unchanged)
Oracle_DocksResolveTransitionSheet:
  RTL

LoadTransAuxGFX_return = $00D673

; Config enables (active in live ROM)
Pool_EnableBGColor:
  db $01
Pool_EnableMainPalette:
  db $01
Pool_EnableAnimated:
  db $01
Pool_EnableTransitionGFXGroupLoad:
  db $01

; Default GFX groups (matching live ROM Pool_DefaultGFXGroups_sheet0):
;   LW ($00..$3F, offset 0):  3A 3B 3C 3D 3E 3F 3E 5B
;   DW ($40..$7F, offset 8):  3A 3B 3C 45 3E 3F 3F 5B
;   SW ($80..$BF, offset 16): 3A 3B 3C 3D 3E 3F 3E 5B
Pool_DefaultGFXGroups_sheet0:
  db $3A, $3B, $3C, $3D, $3E, $3F, $3E, $5B
  db $3A, $3B, $3C, $45, $3E, $3F, $3F, $5B
  db $3A, $3B, $3C, $3D, $3E, $3F, $3E, $5B

; Compact tables covering areas $00..$8F (144 areas)
Pool_MainPaletteTable:
  fillbyte $00 : fill 144

Pool_OverlayTable:
  fillbyte $FF : fill 288

; Area GFX groups (8 bytes per area, 144 areas = 1152 bytes) at fixed Bank $28 offset
org $28C000
Pool_OWGFXGroupTable_sheet0 = $28C000
Pool_OWGFXGroupTable_sheet1 = $28C001
Pool_OWGFXGroupTable_sheet2 = $28C002
Pool_OWGFXGroupTable_sheet3 = $28C003
Pool_OWGFXGroupTable_sheet4 = $28C004
Pool_OWGFXGroupTable_sheet5 = $28C005
Pool_OWGFXGroupTable_sheet6 = $28C006
Pool_OWGFXGroupTable_sheet7 = $28C007
  fillbyte $FF : fill 144*8
  ; FIELD $15 ($15 * 8 = $00A8) = ['3A','3B','3C','FF','51','4E','FF','5B']
  org $28C0A8
  db $3A, $3B, $3C, $FF, $51, $4E, $FF, $5B
  ; DW $55 ($55 * 8 = $02A8) = ['FF','3B','3C','FF','52','49','FF','5B'] (tests Slot 0=$FF too!)
  org $28C2A8
  db $FF, $3B, $3C, $FF, $52, $49, $FF, $5B
'''
    asm_path = folder / "whirlpool_fix_test.asm"
    asm_path.write_text(harness, encoding="utf-8")
    sym_path = rom_path.with_suffix(".sym")
    proc = subprocess.run(
        [ASAR, "--no-title-check", "--fix-checksum=off",
         "--symbols=wla", f"--symbols-path={sym_path}",
         str(asm_path), str(rom_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
                             sym_path.read_text(encoding="utf-8"))
    }
    return rom_path.read_bytes(), labels


def _call(f: Fixture, entry: str, *, m8: bool = True, x8: bool = True,
          a: int = 0, x: int = 0, y: int = 0, db: int = 0x28) -> None:
    c = f.cpu
    addr = f.addr(entry)
    assert addr is not None, f"Missing symbol {entry}"
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    c.db = db
    c.dp = 0
    c.mf = m8
    c.xf = x8
    c.a = a & (0xFF if m8 else 0xFFFF)
    c.x = x & (0xFF if x8 else 0xFFFF)
    c.y = y & (0xFF if x8 else 0xFFFF)
    ret_addr = (addr & 0xFF0000) | 0x7000
    f.put(sp, addr >> 16)
    f.put(sp - 1, 0x6F)
    f.put(sp - 2, 0xFF)
    c.sp -= 3
    for _ in range(50000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack in {entry}: {c.sp:#x} != {sp:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction ceiling reached in {entry}")


def _put16(f: Fixture, addr: int, val: int) -> None:
    f.put(addr, val & 0xFF)
    f.put(addr + 1, (val >> 8) & 0xFF)


def _get16(f: Fixture, addr: int) -> int:
    return f.get(addr) | (f.get(addr + 1) << 8)


@unittest.skipUnless(ASAR and _find_lakesnes(), "Asar and LakeSnes checkout required")
class WhirlpoolGfxBackdropCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory(prefix="oos-whirlpool-test-")
        cls.td = Path(cls._td.name)
        cls.lib = _build_cpu_lib(cls.td)
        cls.rom, cls.labels = _assemble_whirlpool_fixture(cls.td)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _fx(self) -> Fixture:
        return Fixture(self.lib, self.rom, self.labels)

    # 1. .whirpool -> .loadAnimated NMI scheduling (ZERO mid-frame PPU/DMA writes)
    def test_load_animated_schedules_nmi_without_midframe_dma(self) -> None:
        f = self._fx()
        f.put(0x11, 0x2E)
        f.put(0xB0, 0x08)
        _put16(f, 0x0134, 0x3C00)
        _put16(f, 0x0ADC, 0xAE80)
        # Pre-dirty slot 2 NMI vars to confirm they get cleared
        _put16(f, 0x04D9, 0x2400)
        _put16(f, 0x04DB, 0x2800)
        _put16(f, 0x04DD, 0x0800)
        f.bad_writes.clear()

        _call(f, "NewOverworld_FinishTransGfx", m8=True, x8=True, db=0x02)

        self.assertEqual(f.bad_writes, [], "Whirlpool .loadAnimated must NOT touch PPU/DMA mid-frame")
        self.assertEqual(_get16(f, 0x04D3), 0x3C00)  # NewNMITarget1
        self.assertEqual(_get16(f, 0x04D5), 0xAE80)  # NewNMISource1
        self.assertEqual(_get16(f, 0x04D7), 0x0400)  # NewNMICount1
        self.assertEqual(_get16(f, 0x04D9), 0x0000)  # NewNMITarget2
        self.assertEqual(_get16(f, 0x04DB), 0x0000)  # NewNMISource2
        self.assertEqual(_get16(f, 0x04DD), 0x0000)  # NewNMICount2
        self.assertEqual(f.get(0x17), 0x06)
        self.assertEqual(f.get(0x0710), 0x06)
        self.assertEqual(f.get(0x11), 0x2F)

    def test_load_animated_skips_when_pointers_uninitialized(self) -> None:
        for t0134, s0adc in ((0x0000, 0xAE80), (0x3C00, 0x0000), (0x3C00, 0x7FFF)):
            with self.subTest(t0134=hex(t0134), s0adc=hex(s0adc)):
                f = self._fx()
                f.put(0x11, 0x2E)
                f.put(0xB0, 0x08)
                _put16(f, 0x0134, t0134)
                _put16(f, 0x0ADC, s0adc)
                f.bad_writes.clear()
                _call(f, "NewOverworld_FinishTransGfx", m8=True, x8=True, db=0x02)
                self.assertEqual(f.bad_writes, [])
                self.assertEqual(f.get(0x17), 0x00)
                self.assertEqual(f.get(0x11), 0x2F)

    # 2. NMI_UpdateChr_Bg2HalfAndAnimatedLONG (bank $7E animated vs bank $7F regular)
    def test_nmi_update_chr_bank7e_animated_and_bank7f_regular(self) -> None:
        # Animated tiles path: NewNMISource1 >= $8000 -> bank $7E, 0x0400 bytes
        f = self._fx()
        _put16(f, 0x04D3, 0x3C00)
        _put16(f, 0x04D5, 0xAE80)
        _put16(f, 0x04D7, 0x0400)
        _put16(f, 0x04DD, 0x0000)
        f.put(0x0710, 0x07)
        f.bad_writes.clear()

        _call(f, "NMI_UpdateChr_Bg2HalfAndAnimatedLONG", m8=True, x8=True, db=0x00)

        regs = [(a & 0xFFFF, v) for a, v in f.bad_writes]
        self.assertEqual(
            regs,
            [
                (0x2115, 0x80),  # VMAIN
                (0x4300, 0x01),  # DMA0MODE low
                (0x4301, 0x18),  # DMA0MODE high (VMDATAL)
                (0x2116, 0x00),  # VMADDL
                (0x2117, 0x3C),  # VMADDH
                (0x4302, 0x80),  # A1T0L
                (0x4303, 0xAE),  # A1T0H
                (0x4304, 0x7E),  # A1B0 = bank $7E!
                (0x4305, 0x00),  # DAS0L
                (0x4306, 0x04),  # DAS0H = $0400
                (0x420B, 0x01),  # MDMAEN
            ],
        )
        self.assertEqual(f.get(0x0710), 0x00)

        # Regular dual-sheet path: NewNMISource1/2 < $8000 -> bank $7F
        f2 = self._fx()
        _put16(f2, 0x04D3, 0x2C00)
        _put16(f2, 0x04D5, 0x0000)
        _put16(f2, 0x04D7, 0x0800)
        _put16(f2, 0x04D9, 0x3000)
        _put16(f2, 0x04DB, 0x0800)
        _put16(f2, 0x04DD, 0x0800)
        f2.put(0x0710, 0x06)
        f2.bad_writes.clear()

        _call(f2, "NMI_UpdateChr_Bg2HalfAndAnimatedLONG", m8=True, x8=True, db=0x00)

        regs2 = [(a & 0xFFFF, v) for a, v in f2.bad_writes]
        banks = [v for r, v in regs2 if r == 0x4304]
        triggers = [v for r, v in regs2 if r == 0x420B]
        self.assertEqual(banks, [0x7F, 0x7F])
        self.assertEqual(triggers, [0x01, 0x01])
        self.assertEqual(f2.get(0x0710), 0x00)

    # 3. $FF default sheet resolution + BlockGFXCheck + NewLoadTransAuxGFX + LoadTransMainGFX
    def test_resolve_default_ow_gfx_sheet8_lw_dw_sw(self) -> None:
        cases = [
            (0x15, 3, 0xFF, 0x3D),  # LW Slot 3 -> $3D
            (0x15, 6, 0xFF, 0x3E),  # LW Slot 6 -> $3E
            (0x55, 3, 0xFF, 0x45),  # DW Slot 3 -> $45
            (0x55, 6, 0xFF, 0x3F),  # DW Slot 6 -> $3F
            (0x80, 3, 0xFF, 0x3D),  # SW Slot 3 -> $3D
            (0x15, 4, 0x51, 0x51),  # Explicit non-$FF unchanged
        ]
        for area, slot, sheet, expected in cases:
            with self.subTest(area=hex(area), slot=slot, sheet=hex(sheet)):
                f = self._fx()
                f.put(0x8A, area)
                _call(f, "Test_CallResolveDefault8", m8=True, x8=True, a=sheet, x=slot)
                self.assertEqual(f.cpu.a & 0xFF, expected)
                self.assertEqual(f.cpu.x & 0xFF, slot)

    def test_block_gfx_check_resolves_ff_slots_from_docks_to_field15(self) -> None:
        f = self._fx()
        f.put(0x8A, 0x15)  # FIELD $15: ['3A','3B','3C','FF','51','4E','FF','5B']
        # Stale Docks $30 PriorSheets: Slot 3=$E4, Slot 4=$E5, Slot 5=$E6, Slot 6=$E3
        for idx, val in enumerate([0x3A, 0x3B, 0x3C, 0xE4, 0xE5, 0xE6, 0xE3, 0x5B]):
            f.put(0x04CB + idx, val)
        f.put(0x0CF3, 0x00)  # TransGFXModuleFrame = 0

        # Frame 1: should queue Slots 3 ($3D -> $2C00) & 4 ($51 -> $3000)
        f.put(0x06, 0x08)
        _call(f, "Test_CallBlockGFXCheck", m8=True, x8=True)
        self.assertEqual(f.get(0x17), 0x06)
        self.assertEqual(_get16(f, 0x04D3), 0x2C00)  # Slot 3 target
        self.assertEqual(_get16(f, 0x04D9), 0x3000)  # Slot 4 target
        self.assertEqual(f.get(0x0CF3), 0x02)

        # Frame 2: should queue Slots 5 ($4E -> $3400) & 6 ($3E -> $3800)
        f.put(0x06, 0x08)
        _call(f, "Test_CallBlockGFXCheck", m8=True, x8=True)
        self.assertEqual(f.get(0x17), 0x06)
        self.assertEqual(_get16(f, 0x04D3), 0x3400)  # Slot 5 target
        self.assertEqual(_get16(f, 0x04D9), 0x3800)  # Slot 6 target
        self.assertEqual(f.get(0x0CF3), 0x04)

        # Frame 3: remaining slots 0,1,2,7 already match -> reaches frame 8
        f.put(0x06, 0x08)
        _call(f, "Test_CallBlockGFXCheck", m8=True, x8=True)
        self.assertEqual(f.get(0x0CF3), 0x08)

        prior = [f.get(0x04CB + i) for i in range(8)]
        self.assertEqual(prior, [0x3A, 0x3B, 0x3C, 0x3D, 0x51, 0x4E, 0x3E, 0x5B])

    def test_new_load_trans_aux_gfx_whirlpool_guard_and_ff_resolution(self) -> None:
        # First Whirlpool frame (TransGFXModuleFrame == 0): decompresses resolved aux slots 3..6
        f = self._fx()
        f.put(0x1B, 0x00)
        f.put(0x11, 0x2E)
        f.put(0x8A, 0x15)
        f.put(0x0CF3, 0x00)
        for idx, val in enumerate([0x3A, 0x3B, 0x3C, 0xE4, 0xE5, 0xE6, 0xE3, 0x5B]):
            f.put(0x04CB + idx, val)

        _call(f, "Test_CallNewLoadTransAuxGFX", m8=True, x8=True, db=0x00)

        self.assertEqual(f.get(0x04), 4)
        self.assertEqual(f.get(0x0F1A), 4)
        self.assertEqual([f.get(0x0F40 + i) for i in range(4)], [0x3D, 0x51, 0x4E, 0x3E])
        self.assertEqual(f.get(0x0F1E), 1)  # continued to sprite aux

        # Subsequent Whirlpool frame (TransGFXModuleFrame == 2): skips re-decomp & keeps frame!
        f2 = self._fx()
        f2.put(0x1B, 0x00)
        f2.put(0x11, 0x2E)
        f2.put(0x8A, 0x15)
        f2.put(0x0CF3, 0x02)
        f2.put(0x04, 0x07)

        _call(f2, "Test_CallNewLoadTransAuxGFX", m8=True, x8=True, db=0x00)

        self.assertEqual(f2.get(0x04), 0)
        self.assertEqual(f2.get(0x0F1A), 0)
        self.assertEqual(f2.get(0x0CF3), 0x02)
        self.assertEqual(f2.get(0x0F1E), 0)

    def test_load_trans_main_gfx_resolves_ff_slot0(self) -> None:
        f = self._fx()
        f.put(0x8A, 0x55)  # DW $55 has Slot 0 = $FF -> resolves to $3A
        for idx, val in enumerate([0x2D, 0x3B, 0x3C, 0x45, 0x52, 0x49, 0x3F, 0x5B]):
            f.put(0x04CB + idx, val)

        _call(f, "Test_CallLoadTransMainGFX", m8=True, x8=True)

        self.assertEqual(f.get(0x04), 1)
        self.assertEqual(f.get(0x0F1A), 1)
        self.assertEqual(f.get(0x0F40), 0x3A)

    def test_whirlpool_load_destination_map_invalidates_aux_prior_sheets(self) -> None:
        f = self._fx()
        f.put(0x0CF3, 0x05)
        # Include one #$FF entry in slot 5 to confirm #$FF is preserved while non-$FF -> #$FE
        for idx, val in enumerate([0x3A, 0x3B, 0x3C, 0x3D, 0x51, 0xFF, 0x3E, 0x5B]):
            f.put(0x04CB + idx, val)

        _call(f, "Test_Call02B490", m8=True, x8=True, db=0x02)

        self.assertEqual(f.get(0x0F18), 1)
        self.assertEqual(f.get(0x0CF3), 0x00)
        prior = [f.get(0x04CB + i) for i in range(8)]
        self.assertEqual(prior, [0x3A, 0x3B, 0x3C, 0xFE, 0xFE, 0xFF, 0xFE, 0x5B])

    # 4. Whirlpool_ReloadSubscreenOverlay_Interupt ($02B47E)
    def test_whirlpool_reload_overlay_clears_poisoned_7f4000_when_no_overlay(self) -> None:
        f = self._fx()
        f.put(0x8C, 0xFF)
        f.put(0x9C, 0x26)  # stale DM R fixed color
        f.put(0x9D, 0x4C)  # stale DM G fixed color
        # Poison $7F4000..$7F407F with CHR-range words $2000..$3FC0
        for i in range(64):
            _put16(f, 0x7F4000 + i * 2, 0x2000 + i * 0x40)

        _call(f, "Test_Call02B47E", m8=True, x8=True, db=0x02)

        self.assertEqual(f.get(0x0F16), 1)
        self.assertEqual(f.get(0x9C), 0x20)
        self.assertEqual(f.get(0x9D), 0x40)
        words = [_get16(f, 0x7F4000 + i * 2) for i in range(64)]
        self.assertEqual(words, [0x1000 + i * 0x40 for i in range(64)])

    def test_whirlpool_reload_overlay_preserves_7f4000_when_overlay_present(self) -> None:
        f = self._fx()
        f.put(0x8C, 0x9E)  # Canopy overlay active
        for i in range(64):
            _put16(f, 0x7F4000 + i * 2, 0x1400 + i * 0x20)

        _call(f, "Test_Call02B47E", m8=True, x8=True, db=0x02)

        self.assertEqual(f.get(0x0F16), 1)
        self.assertEqual(f.get(0x9C), 0x20)
        self.assertEqual(f.get(0x9D), 0x40)
        words = [_get16(f, 0x7F4000 + i * 2) for i in range(64)]
        self.assertEqual(words, [0x1400 + i * 0x20 for i in range(64)])

    # 5. CheckForChangeGraphicsTransitionLoad ($11=#$2E vs #$02 vs #$0F)
    def test_check_for_change_gfx_whirlpool_uses_buffer_only_and_skips_docks_dma(self) -> None:
        f = self._fx()
        f.put(0x11, 0x2E)
        f.put(0x8A, 0x15)
        f.put(0x0AB3, 0x03)  # differs from table's 0x00 -> triggers main pal reload
        f.put(0x0FC0, 0x5A)  # differs from $0F30=$5B -> triggers anim decomp
        f.put(0x0F30, 0x5B)

        _call(f, "Test_CallCheckForChangeGraphics", m8=True, x8=True)

        self.assertEqual(f.get(0x0F20), 1)  # DecompOwAnimatedTiles
        self.assertEqual(f.get(0x0F00), 1)  # Palette_OverworldBgMain (buffer-only!)
        self.assertEqual(f.get(0x0F02), 0)  # NOT Palette_OverworldBgMain2
        self.assertEqual(f.get(0x0F06), 1)  # Oracle_MosaicFix (buffer-only!)
        self.assertEqual(f.get(0x0F04), 0)  # NOT Oracle_BackgroundFix
        self.assertEqual(f.get(0x0F0C), 0)  # Skipped direct-DMA Oracle_DocksNormalLoad!
        self.assertEqual(f.get(0x0F08), 1)  # CompleteBuffer
        self.assertEqual(f.get(0x0F0A), 0)  # NOT CompleteBoth

    def test_check_for_change_gfx_nonregression_scroll_and_mosaic(self) -> None:
        # Normal OW scroll ($11 == #$02): live update path
        f_scroll = self._fx()
        f_scroll.put(0x11, 0x02)
        f_scroll.put(0x8A, 0x15)
        f_scroll.put(0x0AB3, 0x03)
        f_scroll.put(0x0FC0, 0x5B)
        f_scroll.put(0x0F30, 0x5B)
        _call(f_scroll, "Test_CallCheckForChangeGraphics", m8=True, x8=True)
        self.assertEqual(f_scroll.get(0x0F02), 1)  # Palette_OverworldBgMain2
        self.assertEqual(f_scroll.get(0x0F04), 1)  # Oracle_BackgroundFix
        self.assertEqual(f_scroll.get(0x0F0A), 1)  # CompleteBoth
        self.assertEqual(f_scroll.get(0x0F00), 0)
        self.assertEqual(f_scroll.get(0x0F06), 0)

        # Mosaic transition ($11 == #$0F): buffer-only + DOES run Oracle_DocksNormalLoad
        f_mos = self._fx()
        f_mos.put(0x11, 0x0F)
        f_mos.put(0x8A, 0x15)
        f_mos.put(0x0AB3, 0x03)
        f_mos.put(0x0FC0, 0x5B)
        f_mos.put(0x0F30, 0x5B)
        _call(f_mos, "Test_CallCheckForChangeGraphics", m8=True, x8=True)
        self.assertEqual(f_mos.get(0x0F00), 1)  # Palette_OverworldBgMain
        self.assertEqual(f_mos.get(0x0F06), 1)  # Oracle_MosaicFix
        self.assertEqual(f_mos.get(0x0F0C), 1)  # Oracle_DocksNormalLoad RUNS for $0F
        self.assertEqual(f_mos.get(0x0F08), 1)  # CompleteBuffer

    # 6. ReplaceBGColor + $02B4D1/$02B4D5/$02B4DD Whirlpool $B0=9 hooks
    def test_replace_bg_color_whirlpool_vs_normal(self) -> None:
        f_wp = self._fx()
        f_wp.put(0x11, 0x2E)
        _call(f_wp, "ReplaceBGColor", m8=False, x8=False, db=0x0B)
        self.assertEqual(f_wp.get(0x0F06), 1)  # Oracle_MosaicFix
        self.assertEqual(f_wp.get(0x0F04), 0)  # NOT Oracle_BackgroundFix

        f_norm = self._fx()
        f_norm.put(0x11, 0x00)
        _call(f_norm, "ReplaceBGColor", m8=False, x8=False, db=0x0B)
        self.assertEqual(f_norm.get(0x0F04), 1)  # Oracle_BackgroundFix
        self.assertEqual(f_norm.get(0x0F06), 0)

    def test_whirlpool_b0_9_hooks_cache_only_and_preserve_coldata_9e(self) -> None:
        # $02B4D1 falls straight into $02B4D5 (and RTS at $02B4D9 in harness):
        # verifies BOTH SpecialPaletteLoadFinishBuffer and Overworld_SetScreenBGColorCacheOnly!
        f = self._fx()
        _call(f, "Test_Call02B4D1", m8=True, x8=True, db=0x02)
        self.assertEqual(f.get(0x0F0E), 1)  # Overworld_LoadPalettes
        self.assertEqual(f.get(0x0F08), 1)  # CompleteBuffer (NOT CompleteBoth)
        self.assertEqual(f.get(0x0F0A), 0)
        self.assertEqual(f.get(0x0F10), 1)  # Overworld_SetScreenBGColorCacheOnly ($0ED61D)
        self.assertEqual(f.get(0x0F12), 0)  # NOT Palette_SetOwBgColor_Long ($0ED618)

        # $02B4DD -> Whirlpool_LoadSpritesAndFinishPalettes -> $00E031 -> $02B4E5 (skips $02B4E1!)
        for dest_9e in (0x8C, 0x87, 0x89, 0x80):
            with self.subTest(dest_9e=hex(dest_9e)):
                f2 = self._fx()
                f2.put(0x9E, dest_9e)
                f2.put(0xB0, 0x09)
                f2.put(0x0710, 0x00)
                _call(f2, "Test_Call02B4DD", m8=True, x8=True, db=0x02)
                self.assertEqual(f2.get(0x0F14), 1)   # LoadNewSpriteGFXSet ($00E031) called
                self.assertEqual(f2.get(0x9E), dest_9e, "$02B4DD must preserve destination COLDATA $9E")
                self.assertEqual(f2.get(0x13), 0x0F)  # $02B4E5 brightness set
                self.assertEqual(f2.get(0x0710), 0x01)
                self.assertEqual(f2.get(0xB0), 0x0A)


if __name__ == "__main__":
    unittest.main()
