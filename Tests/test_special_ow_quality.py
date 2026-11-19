#!/usr/bin/env python3
"""Compiled Asar + 65816 Lakesnes tests for Q329 Special Overworld Quality/Perf/Music/
Palette/Spritesheet fixes and A4 Abyss Return Vortex ($6C) bidirectional lifecycle.
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
ASAR_BIN = os.environ.get("ASAR_BIN") or shutil.which("asar")
LAKESNES_DIR = Path(os.environ.get("LAKESNES_DIR", "/Users/scawful/src/hobby/LakeSnes"))

sys.path.insert(0, str(ROOT / "Tests"))
from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def _compile_lakesnes(tmp_dir: Path) -> C.CDLL:
    libpath = tmp_dir / "cpu_q329.dylib"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            str(LAKESNES_DIR / "snes/cpu.c"),
            str(LAKESNES_DIR / "snes/statehandler.c"),
            "-o",
            str(libpath),
        ],
        check=True,
    )
    lib = C.CDLL(str(libpath))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _assemble(tmp_dir: Path, name: str, rom_buf: bytearray, asm_src: str) -> tuple[bytes, dict[str, int]]:
    rom_path = tmp_dir / f"{name}.sfc"
    asm_path = tmp_dir / f"{name}.asm"
    sym_path = tmp_dir / f"{name}.sym"
    rom_path.write_bytes(rom_buf)
    asm_path.write_text(asm_src, encoding="utf-8")
    proc = subprocess.run(
        [
            ASAR_BIN,
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"--symbols-path={sym_path}",
            str(asm_path),
            str(rom_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"asar failed for {name}:\n{proc.stdout}\n{proc.stderr}")
    labels: dict[str, int] = {}
    for bank, offset, lname in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z0-9_.:]+)$",
        sym_path.read_text(encoding="utf-8"),
        re.M,
    ):
        labels[lname] = (int(bank, 16) << 16) | int(offset, 16)
    return rom_path.read_bytes(), labels


def _run_call(
    f: Fixture,
    addr: int,
    *,
    a: int = 0,
    x: int = 0,
    y: int = 0,
    m16: bool = False,
    x16: bool = False,
    db: int = 0x02,
    carry: bool = False,
    is_rts: bool = False,
    extra_stack: bytes = b"",
    max_steps: int = 50000,
) -> int:
    """Execute routine until sentinel return at $7000; return executed opcode count."""
    p = f.cpu
    p.k = (addr >> 16) & 0xFF
    p.pc = addr & 0xFFFF
    p.a = a & 0xFFFF
    p.x = x & (0xFFFF if x16 else 0xFF)
    p.y = y & (0xFFFF if x16 else 0xFF)
    p.db = db
    p.dp = 0x0000
    p.e = False
    p.mf = not m16
    p.xf = not x16
    p.c = carry
    initial_sp = p.sp
    frame = (0x6F, 0xFF) if is_rts else (p.k, 0x6F, 0xFF)
    for b in frame:
        f.put(p.sp, b)
        p.sp -= 1
    for b in extra_stack:
        f.put(p.sp, b)
        p.sp -= 1
    target_k = (addr >> 16) & 0xFF
    for steps in range(1, max_steps + 1):
        if p.pc == 0x7000 and p.k == target_k:
            assert p.sp == initial_sp, f"Stack imbalance: sp={p.sp:04X} vs {initial_sp:04X}"
            assert not f.bad_writes, f"Bad ROM/IO writes: {f.bad_writes}"
            return steps
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction limit at ${p.k:02X}:{p.pc:04X}")


def _build_quality_harness(tmp_dir: Path) -> tuple[bytes, dict[str, int]]:
    """Harness combining special_overworld_transitions.asm + special_overworld_quality.asm
    with RAM-backed tables for dynamic testing of music, mosaic, spritesheet, palette, and A4 vortex."""
    buf = bytearray(0x600000)

    def put_bytes(snes: int, raw: bytes) -> None:
        pc = snes_to_pc(snes)
        buf[pc:pc + len(raw)] = raw

    # Preimages asserted by special_overworld_transitions.asm
    put_bytes(0x02B1B4, bytes.fromhex("A908851164B060"))
    put_bytes(0x02A53C, bytes.fromhex("AD12010DE402"))
    put_bytes(0x02AE98, bytes.fromhex("AD0A04F019"))
    put_bytes(0x0AB9F0, bytes.fromhex("A68AE080B00CA5208F08C17EA5228F0AC17EE220"))
    put_bytes(0x0ABA40, bytes.fromhex("8BA90A48ABC230A2FE00A0FE00A58A294000F003A0FE01B927DB9F00C57E8888CACA10F3E230AB"))

    # Preimages asserted by special_overworld_quality.asm
    put_bytes(0x0ED5C9, bytes.fromhex("A5000AAA"))
    put_bytes(0x07A97E, bytes.fromhex("A58A2940857BF014A5208FDF1A7EA5218FEF1A7EA5228FBF1A7EA5238FCF1A7E"))
    put_bytes(0x05AF75, bytes.fromhex("AFCAF37ED064"))
    put_bytes(0x05AFD9, bytes.fromhex("A58A2940857B"))

    # Stub Sprite_ReinitWarpVortex ($09AF89): increments counter at $7F1100 and RTLs
    put_bytes(0x09AF89, bytes.fromhex("AF00117F1A8F00117F6B"))

    # Seed distinct LW/DW world map palettes
    put_bytes(0x0ADB27, b"".join(((0x1000 + i) & 0x7FFF).to_bytes(2, "little") for i in range(128)))
    put_bytes(0x0ADC27, b"".join(((0x2000 + i) & 0x7FFF).to_bytes(2, "little") for i in range(128)))

    asm_src = f"""
lorom
!SPECIAL_OVERWORLD_NATIVE = 1
!SPECIAL_OVERWORLD_RESOURCES_ENABLED = 1
!SPECIAL_OVERWORLD_PALETTE_ENABLED = 1
!OverworldMusicCache = $7EC900
!LYRA_CURRENT_FIRST = $00A0
!LYRA_CURRENT_END = $00C0
!LYRA_CURRENT_TABLE_music_phase0 = $7F2000
!LYRA_CURRENT_TABLE_music_phase1 = $7F2100
!LYRA_CURRENT_TABLE_music_phase2 = $7F2200
!LYRA_CURRENT_TABLE_music_phase3 = $7F2300
!SPECIAL_OVERWORLD_TRANSFER_DIRECTORY = $7F3000
!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY = $7F3400
SavedWorld = $7EF3CA
Pendants = $7EF374
Crystals = $7EF37A
!Pendant_Wisdom = $01
!Pendant_Power = $02
!Pendant_Courage = $04
!Crystal_D1 = $02
!Crystal_D2 = $10
!Crystal_D3 = $40
!Crystal_D4 = $20
!Crystal_D5 = $04
!Crystal_D6 = $01
!Crystal_D7 = $08
!Crystal_D8_Sky = $01

namespace Oracle
org $468000
Oracle_CheckIfNight:
  LDA.l $7F1200
  RTL

Lyra_ReadParent:
  LDA.l $7F0000, X : RTL
Lyra_ReadSize:
  LDA.l $7F0100, X : RTL
Lyra_ReadAreaSize:
  LDA.l $7F0100, X : RTL
Lyra_ReadMosaic:
  LDA.l $7F0200, X : RTL
Lyra_ReadMainPalette:
  LDA.l $7F0300, X : RTL
Lyra_ReadOverlay:
  LDA.l $7F0400, X : RTL
Lyra_ReadGfx0:
  LDA.l $7F0600, X : RTL
Lyra_ReadGfx1:
  LDA.l $7F0601, X : RTL
Lyra_ReadGfx2:
  LDA.l $7F0602, X : RTL
Lyra_ReadGfx7:
  LDA.l $7F0607, X : RTL
Lyra_ReadByScreen:
  LDA.w #$0000 : RTL
Lyra_ReadSpriteGfxByArea:
  LDA.l $7F2800, X : RTL
Lyra_ReadSpecialSpriteGfx:
  LDA.l $7F2900, X : RTL

Lyra_ReadTransitionY:
  LDA.l $7F0C00, X : RTL
Lyra_ReadTransitionX:
  LDA.l $7F0E00, X : RTL
Overworld_LoadMapProperties_Long:
  RTL
Overworld_LoadAreaGFX_Long:
  RTL
Overworld_LoadAreaPalettes_Long:
  RTL
Copy0716:
  RTL
NewOverworld_SetCameraBounds:
  RTL

org $5F8000
SWWorldMap_Tiles:
  incbin "{ROOT}/Overworld/world_map/SwMapTileset.bin"
SWWorldMap_Gfx:
  incbin "{ROOT}/Overworld/world_map/SwMapGfx.bin"
SWPalettes:
  incbin "{ROOT}/Overworld/world_map/sw_palette.bin"

incsrc "{ROOT}/Overworld/special_overworld_transitions.asm"
incsrc "{ROOT}/Overworld/special_overworld_quality.asm"
namespace off
"""
    return _assemble(tmp_dir, "quality", buf, asm_src)


def _build_semantic_perf_harness(tmp_dir: Path) -> tuple[bytes, dict[str, int]]:
    """Compile real Overworld/special_overworld_semantic.asm with 1024-slot Record 413
    matching the real ROM profile (rows only on $87 and $90; 0 rows on $A0/$99)."""
    buf = bytearray(0x600000)

    def put_u16(snes: int, val: int) -> None:
        pc = snes_to_pc(snes)
        buf[pc] = val & 0xFF
        buf[pc + 1] = (val >> 8) & 0xFF

    # Seed preimage Record 413 at $519000: 1024 * 12 bytes = 6 LE16 words per row
    # (physical_page, local_id, TL, TR, BL, BR). All-FF trailing padding.
    row_idx = 0
    for i in range(60):
        base = 0x519000 + row_idx * 12
        put_u16(base + 0, 0x0087)
        put_u16(base + 2, 10 + i)
        put_u16(base + 4, 0x55A0 + i)  # TL
        put_u16(base + 6, 0x55B0 + i)  # TR
        put_u16(base + 8, 0x55C0 + i)  # BL
        put_u16(base + 10, 0x55D0 + i)  # BR
        row_idx += 1
    for i in range(40):
        base = 0x519000 + row_idx * 12
        put_u16(base + 0, 0x0090)
        put_u16(base + 2, 20 + i)
        put_u16(base + 4, 0x66B0 + i)
        put_u16(base + 6, 0x66C0 + i)
        put_u16(base + 8, 0x66D0 + i)
        put_u16(base + 10, 0x66E0 + i)
        row_idx += 1
    while row_idx < 1024:
        base = 0x519000 + row_idx * 12
        for k in range(6):
            put_u16(base + k * 2, 0xFFFF)
        row_idx += 1

    # Seed preimage hooks asserted by special_overworld_semantic.asm
    def put_bytes(snes: int, raw: bytes) -> None:
        pc = snes_to_pc(snes)
        buf[pc:pc + len(raw)] = raw

    put_bytes(0x008864, bytes.fromhex("BF00803D"))
    put_bytes(0x0EDE4E, bytes.fromhex("BF00803D"))
    put_bytes(0x0EDEE8, bytes.fromhex("BF00803D"))
    put_bytes(0x1BBEDF, bytes.fromhex("0A0A8506A5002908004A4A0406A50229010005060AAABF00803D"))
    put_bytes(0x1BBF1E, bytes.fromhex("0A0A0AAABF00803D"))
    put_bytes(0x1BC027, bytes.fromhex("0A0A8506A5022908004A4A0406A5004A4A4A29010005060AAABF00803D"))

    # Seed identity parent table at $508000 for 192 maps
    parent_pc = snes_to_pc(0x508000)
    for m in range(192):
        buf[parent_pc + m] = m

    # Seed base Map16 definitions at $3D8000 for local_id $0014 and $0019
    put_u16(0x3D8000 + 0x0014 * 8 + 0, 0x1111)
    put_u16(0x3D8000 + 0x0014 * 8 + 2, 0x1112)
    put_u16(0x3D8000 + 0x0014 * 8 + 4, 0x1113)
    put_u16(0x3D8000 + 0x0014 * 8 + 6, 0x1114)
    put_u16(0x3D8000 + 0x0019 * 8 + 0, 0x2221)

    asm_src = f"""
lorom
!SPECIAL_OVERWORLD_NATIVE = 1
!SPECIAL_OVERWORLD_RESIDENT_ENABLED = 1
!SPECIAL_OVERWORLD_RESIDENT_FIRST = $0080
!SPECIAL_OVERWORLD_RESIDENT_END = $00C0
!LYRA_CURRENT_RESIDENT_CODE_BASE = $46D000
!LYRA_CURRENT_RESIDENT_CODE_END = $46D400
!LYRA_CURRENT_TABLE_parent = $508000
!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 1
!SPECIAL_OVERWORLD_SEMANTIC_REVISION = 5
!SPECIAL_OVERWORLD_SEMANTIC_CAPACITY = 192
!SPECIAL_OVERWORLD_SEMANTIC_ROWS = $519000
!SPECIAL_OVERWORLD_SEMANTIC_COUNT = 1024
!SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE = $518000
!SPECIAL_OVERWORLD_SEMANTIC_CODE_END = $518400
!LYRA_CURRENT_MAP16_DEFINITIONS = $3D8000
!ENABLE_SKY_OVERWORLD_GRAPHICS = 0

namespace Oracle
org $46D000
; Simple physical page lookup stub: returns $8A with Carry set (1:1 SmallArea pages)
Lyra_ResidentPhysicalPageLong:
  LDA.l $7E008A
  SEC
  RTL

incsrc "{ROOT}/Overworld/special_overworld_semantic.asm"
namespace off
"""
    return _assemble(tmp_dir, "semantic_perf", buf, asm_src)


def _build_palette_aux_harness(tmp_dir: Path) -> tuple[bytes, dict[str, int]]:
    """Compile real Overworld/special_overworld_palette.asm with ENABLE_OW_AUX_EXTENSION=1
    to verify SpecialPaletteSelectors accepts $0AB4/$0AB5 in $14..$33 (e.g. PSet $13 -> $16)."""
    buf = bytearray(0x600000)
    asm_src = f"""
lorom
!SPECIAL_OVERWORLD_NATIVE = 1
!SPECIAL_OVERWORLD_RESIDENT_ENABLED = 1
!SPECIAL_OVERWORLD_RESIDENT_FIRST = $0080
!SPECIAL_OVERWORLD_RESIDENT_END = $00C0
!SPECIAL_OVERWORLD_PALETTE_ENABLED = 1
!SPECIAL_OVERWORLD_PALETTE_CODE_BASE = $4DF000
!SPECIAL_OVERWORLD_PALETTE_CODE_END = $4E0000
!SPECIAL_OVERWORLD_RESIDENT_PALETTE_DIRECTORY = $528000
!SPECIAL_OVERWORLD_RESIDENT_PALETTE_STRIDE = 3
!ENABLE_OW_AUX_EXTENSION = 1
Oracle_SpecialOverworldPaletteHoleReference = $7E1E8C
Oracle_SpecialOverworldPaletteHoleEffective = $7E1E98
Oracle_SpecialOverworldPaletteHoleState = $7E1EA4
Oracle_SpecialOverworldPaletteHoleArea = $7E1EA5
struct TimeState $7E1E70
  .BlueVal: skip 2
  .GreenVal: skip 2
  .RedVal: skip 2
  .TempColor: skip 2
  .SubColor: skip 2
  .Red: skip 2
  .Green: skip 2
  .Blue: skip 2
endstruct

org $528000
  fillbyte $00 : fill 192

org $4DE000
Oracle_ApplyTintToColor:
  RTL
Oracle_LoadDayNightPaletteEffect:
  RTL

incsrc "{ROOT}/Overworld/special_overworld_palette.asm"
"""
    return _assemble(tmp_dir, "pal_aux", buf, asm_src)


@unittest.skipUnless(ASAR_BIN and LAKESNES_DIR.exists(), "asar and LakeSnes required")
class SpecialOverworldQualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="q329-quality-tests-")
        tmp_path = Path(cls.tmp.name)
        cls.lib = _compile_lakesnes(tmp_path)
        cls.q_rom, cls.q_labels = _build_quality_harness(tmp_path)
        cls.s_rom, cls.s_labels = _build_semantic_perf_harness(tmp_path)
        cls.p_rom, cls.p_labels = _build_palette_aux_harness(tmp_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _fresh_q(self) -> Fixture:
        f = Fixture(self.lib, self.q_rom, self.q_labels)
        for m in range(0xC0):
            f.put(0x7F0000 + m, m)
            f.put(0x7F0100 + m, 0)
            f.put(0x7F0200 + m, 0)
            f.put(0x7F0300 + m, 0)
            f.word(0x7F0400 + m * 2, 0x00FF)
            for k, b in enumerate((0x3A, 0x3B, 0x3C, 0x3D, 0x47, 0x48, 0x3E, 0x5B)):
                f.put(0x7F0600 + m * 8 + k, b)
            f.word(0x7F3000 + m * 2, 0x0000)
        for idx in range(0x40):
            base = 0x7F3400 + idx * 3
            f.put(base, 0)
            f.put(base + 1, 0)
            f.put(base + 2, 0)
        return f

    # ------------------------------------------------------------------
    # 1. Special Overworld Music ($A0-$BF InitMusicTail + FinishSpecialEntry)
    # ------------------------------------------------------------------

    def test_init_music_tail_replaces_silent_rom_bytes_with_biome_defaults(self) -> None:
        expected_defaults = {
            0xA0: 0x5C, 0xA1: 0x5C, 0xA2: 0x5C, 0xA7: 0x5C,  # Great Sea
            0xA8: 0x55, 0xA9: 0x55,                          # Deku Coast (Lost Woods)
            0xAA: 0x5C, 0xAF: 0x5C,                          # Lyra Sea / Courage
            0xB0: 0x5D, 0xB1: 0x5D,                          # Goron N (Mountain)
            0xB2: 0x5C, 0xB7: 0x5C,                          # Crescent / Tower N
            0xB8: 0x5D, 0xB9: 0x5D,                          # Goron S (Mountain)
            0xBA: 0x5C, 0xBD: 0x5C,                          # Harbor / Tower S
            0xBE: 0x56, 0xBF: 0x56,                          # Snow Island (Frozen Hyrule)
        }
        for phase, tbl_base in enumerate((0x7F2000, 0x7F2100, 0x7F2200, 0x7F2300)):
            f = self._fresh_q()
            f.put(0x7F1200, phase)  # Oracle_CheckIfNight return value
            # All ROM bytes $00 except $A3 = $50 (high ambience only, still silent music nibble -> fallback)
            # and $A5 = $38 (authored non-zero music nibble -> MUST be preserved!)
            f.put(tbl_base + 0xA3, 0x50)
            f.put(tbl_base + 0xA5, 0x38)
            # Entry contract from $02C4BC: M=8, X=16, saved DBR ($02) pushed on stack before JML
            _run_call(
                f,
                self.q_labels["Oracle_SpecialOverworld_InitMusicTail"],
                m16=False,
                x16=True,
                db=0x00,
                extra_stack=bytes([0x02]),
            )
            self.assertEqual(f.cpu.db, 0x02, f"phase {phase}: DBR not restored")
            for area, want in expected_defaults.items():
                got = f.get(0x7EC900 + area)
                self.assertEqual(got, want, f"phase {phase} area ${area:02X}: got ${got:02X}, want ${want:02X}")
            self.assertEqual(f.get(0x7EC900 + 0xA3), 0x5C, f"phase {phase}: $50 silent low nibble must fallback")
            self.assertEqual(f.get(0x7EC900 + 0xA5), 0x38, f"phase {phase}: authored $38 must be preserved")

    def test_finish_special_entry_syncs_music_and_ambience_on_special_ow(self) -> None:
        f = self._fresh_q()
        f.put(0x7E008A, 0xA0)
        f.put(0x7EC9A0, 0x5C)  # ambience=5, song=$0C (Great Sea -> remapped at NMI to $10)
        f.put(0x7E0130, 0x02)  # previous song was Overworld
        _run_call(
            f,
            self.q_labels["Oracle_SpecialOverworld_FinishSpecialEntry"],
            db=0x02,
        )
        self.assertEqual(f.get(0x7E0011), 0x08)
        self.assertEqual(f.get(0x7E00B0), 0x00)
        self.assertEqual(f.get(0x7E012D), 0x05)
        self.assertEqual(f.get(0x7E012C), 0x0C)

        # Already playing same song -> do not re-trigger $012C
        f2 = self._fresh_q()
        f2.put(0x7E008A, 0xA0)
        f2.put(0x7EC9A0, 0x5C)
        f2.put(0x7E0130, 0x0C)
        f2.put(0x7E012C, 0x00)
        _run_call(f2, self.q_labels["Oracle_SpecialOverworld_FinishSpecialEntry"], db=0x02)
        self.assertEqual(f2.get(0x7E012C), 0x00)
        self.assertEqual(f2.get(0x7E012D), 0x05)

        # Light World ($8A < $80) -> FinishSpecialEntry does not touch $012C/$012D
        f3 = self._fresh_q()
        f3.put(0x7E008A, 0x23)
        f3.put(0x7EC923, 0x5C)
        f3.put(0x7E012C, 0x00)
        f3.put(0x7E012D, 0x00)
        _run_call(f3, self.q_labels["Oracle_SpecialOverworld_FinishSpecialEntry"], db=0x02)
        self.assertEqual(f3.get(0x7E012C), 0x00)
        self.assertEqual(f3.get(0x7E012D), 0x00)

    # ------------------------------------------------------------------
    # 2. Sprite Palette Clamp ($0ED5C9) & $90 Spriteset Guard
    # ------------------------------------------------------------------

    def test_safe_overworld_sprite_pal_index_clamps_oob_to_01(self) -> None:
        addr = self.q_labels["Oracle_SafeOverworldSpritePalIndex"]
        for valid in range(0x00, 0x14):
            f = self._fresh_q()
            f.put(0x7E0000, valid)
            _run_call(f, addr, db=0x0E)
            self.assertEqual(f.cpu.x & 0xFF, valid * 2, f"valid ${valid:02X}")
        # Every real .yazeproj/rom legacy $02E701 $90-$9E garbage byte plus boundary $14/$FF
        for oob in (0x14, 0x1C, 0x20, 0x7E, 0x8F, 0x9C, 0xA5, 0xAC, 0xAD, 0xC1, 0xC2, 0xFF):
            f = self._fresh_q()
            f.put(0x7E0000, oob)
            _run_call(f, addr, db=0x0E)
            self.assertEqual(f.cpu.x & 0xFF, 0x02, f"OOB ${oob:02X} must clamp to $01 -> X=$02")

    def test_special_overworld_read_sprite_gfx_clamps_oob_and_preserves_8e_8f(self) -> None:
        by_area = self.q_labels["Oracle_SpecialOverworld_ReadSpriteGfxByArea"]
        special = self.q_labels["Oracle_SpecialOverworld_ReadSpecialSpriteGfx"]

        f = self._fresh_q()
        f.put(0x7F2890, 0x8E)  # intentional LyraTempleZora ($8E -> sheet $E7) MUST pass through
        f.put(0x7F2891, 0x8F)  # valid upper bound ($8F -> D4 sheets $DF-$E2) MUST pass through
        f.put(0x7F2892, 0x90)  # OOB (>= $90) MUST clamp to $01
        f.put(0x7F2893, 0xFF)  # OOB ($FF) MUST clamp to $01
        f.put(0x7F2910, 0x8E)  # special offset $10 (= $90) preserves $8E
        f.put(0x7F2911, 0x90)  # special offset $11 OOB clamps to $01

        _run_call(f, by_area, x=0x90)
        self.assertEqual(f.cpu.a & 0xFF, 0x8E)
        _run_call(f, by_area, x=0x91)
        self.assertEqual(f.cpu.a & 0xFF, 0x8F)
        _run_call(f, by_area, x=0x92)
        self.assertEqual(f.cpu.a & 0xFF, 0x01)
        _run_call(f, by_area, x=0x93)
        self.assertEqual(f.cpu.a & 0xFF, 0x01)
        _run_call(f, special, x=0x10)
        self.assertEqual(f.cpu.a & 0xFF, 0x8E)
        _run_call(f, special, x=0x11)
        self.assertEqual(f.cpu.a & 0xFF, 0x01)

    # ------------------------------------------------------------------
    # 3. ShouldMosaic Resident Transfer / Resident Palette Compatibility
    # ------------------------------------------------------------------

    def test_should_mosaic_detects_resident_transfer_and_palette_diffs(self) -> None:
        addr = self.q_labels["Oracle_SpecialOverworld_ShouldMosaic"]

        # Same legacy main_pal & gfx0/1/2/7, DIFFERENT resident transfer ptr ($A0 -> $A2) -> Mosaic!
        f = self._fresh_q()
        f.word(0x7F3000 + 0xA0 * 2, 0x8100)
        f.word(0x7F3000 + 0xA2 * 2, 0x8400)
        f.put(0x7E008A, 0xA2)
        f.put(0x7E0418, 0x00)
        _run_call(f, addr, x=0xA0)
        self.assertEqual(f.cpu.a & 0xFF, 0x01, "$A0 -> $A2 with differing resident Transfer must force Mosaic")

        # Same resident Transfer ptr, DIFFERENT resident Palette ptr ($A8 -> $B0) -> Mosaic!
        f2 = self._fresh_q()
        f2.word(0x7F3000 + 0xA8 * 2, 0x9000)
        f2.word(0x7F3000 + 0xB0 * 2, 0x9000)
        # Palette dir indexed by (area - $80) * 3
        p_a8 = 0x7F3400 + (0xA8 - 0x80) * 3
        p_b0 = 0x7F3400 + (0xB0 - 0x80) * 3
        f2.put(p_a8, 0x10); f2.put(p_a8 + 1, 0x80); f2.put(p_a8 + 2, 0xD0)
        f2.put(p_b0, 0x20); f2.put(p_b0 + 1, 0x80); f2.put(p_b0 + 2, 0xD0)
        f2.put(0x7E008A, 0xB0)
        _run_call(f2, addr, x=0xA8)
        self.assertEqual(f2.cpu.a & 0xFF, 0x01, "$A8 -> $B0 with differing resident Palette must force Mosaic")

        # Identical Transfer & Palette ptrs -> smooth scroll (A=0)
        f3 = self._fresh_q()
        f3.word(0x7F3000 + 0xA0 * 2, 0x8100)
        f3.word(0x7F3000 + 0xA1 * 2, 0x8100)
        for m in (0xA0, 0xA1):
            p = 0x7F3400 + (m - 0x80) * 3
            f3.put(p, 0x40); f3.put(p + 1, 0x90); f3.put(p + 2, 0xD0)
        f3.put(0x7E008A, 0xA1)
        _run_call(f3, addr, x=0xA0)
        self.assertEqual(f3.cpu.a & 0xFF, 0x00, "$A0 -> $A1 identical resident Transfer & Palette should smooth scroll")

        # Sky-to-Sky chain ($87 -> $8F, $8C -> $8D) stays smooth even with different Transfer/Palette ptrs!
        for src, dst in ((0x87, 0x8F), (0x8C, 0x8D)):
            f4 = self._fresh_q()
            f4.word(0x7F3000 + src * 2, 0x8100)
            f4.word(0x7F3000 + dst * 2, 0x8900)
            p_src = 0x7F3400 + (src - 0x80) * 3
            p_dst = 0x7F3400 + (dst - 0x80) * 3
            f4.put(p_src, 0x10); f4.put(p_src + 1, 0x80); f4.put(p_src + 2, 0xD0)
            f4.put(p_dst, 0x50); f4.put(p_dst + 1, 0x88); f4.put(p_dst + 2, 0xD1)
            f4.put(0x7E008A, dst)
            _run_call(f4, addr, x=src)
            self.assertEqual(f4.cpu.a & 0xFF, 0x00, f"Sky-to-Sky ${src:02X} -> ${dst:02X} must remain smooth")

    # ------------------------------------------------------------------
    # 4. SpecialPaletteSelectors Aux Extension ($14..$33 accepted)
    # ------------------------------------------------------------------

    def test_special_palette_selectors_accepts_extended_aux_indices(self) -> None:
        addr = self.p_labels["Oracle_SpecialPaletteSelectors"]
        # Valid extended aux2=$16 (PSet $13 from Docks $30/$31) must succeed (Carry=1)
        f = Fixture(self.lib, self.p_rom, self.p_labels)
        f.put(0x7E0AB3, 0x02)  # main_pal < $06
        f.put(0x7E0AB4, 0x15)  # aux1 in $14..$33
        f.put(0x7E0AB5, 0x16)  # aux2 in $14..$33
        f.put(0x7E0AB6, 0x04)  # anim < $0E
        _run_call(f, addr, m16=True, x16=True, db=0x00, is_rts=True)
        self.assertTrue(f.cpu.c, "Extended aux1=$15/aux2=$16 must be accepted when ENABLE_OW_AUX_EXTENSION==1")

        # Out-of-range aux2=$34 must still fail (Carry=0)
        f2 = Fixture(self.lib, self.p_rom, self.p_labels)
        f2.put(0x7E0AB3, 0x02)
        f2.put(0x7E0AB4, 0x05)
        f2.put(0x7E0AB5, 0x34)
        f2.put(0x7E0AB6, 0x04)
        _run_call(f2, addr, m16=True, x16=True, db=0x00, is_rts=True)
        self.assertFalse(f2.cpu.c, "aux2=$34 (>= $34) must be rejected")

    # ------------------------------------------------------------------
    # 5. Semantic Collision Fast-Path Correctness & CPU Performance Benchmark
    # ------------------------------------------------------------------

    def test_semantic_collision_fast_path_correctness_and_perf(self) -> None:
        coll = self.s_labels["Oracle_Lyra_SemanticCollisionWord"]
        src_fn = self.s_labels["Oracle_Lyra_SemanticSourceWord"]

        # Case A: Non-semantic tail page $A0 (0 Record 413 rows) -> fast-path skips binary search!
        f_empty = Fixture(self.lib, self.s_rom, self.s_labels)
        f_empty.word(0x7E008A, 0x00A0)
        f_empty.word(0x7E0002, 0x0000)  # quadrant 0
        f_empty.word(0x7E2000 + 0x0010, 0x0014)  # cell $0010 holds local Tile16 $0014
        steps_empty = _run_call(
            f_empty, coll, a=0x0000, x=0x0014 * 8, y=0x0010, m16=True, x16=True, db=0x00
        )
        self.assertEqual(f_empty.cpu.a, 0x1111, "Empty semantic page $A0 must return base Map16 word")
        self.assertLess(
            steps_empty,
            40,
            f"Empty semantic page $A0 should take <40 opcodes via quad fast-path (took {steps_empty})",
        )

        # Case B: Semantic page $87 HIT (local_id=$0014 -> source_id=$010A -> word $55AA)
        f_hit = Fixture(self.lib, self.s_rom, self.s_labels)
        f_hit.word(0x7E008A, 0x0087)
        f_hit.word(0x7E0002, 0x0000)
        f_hit.word(0x7E2000 + 0x0010, 0x0014)
        steps_hit = _run_call(
            f_hit, coll, a=0x0000, x=0x0014 * 8, y=0x0010, m16=True, x16=True, db=0x00
        )
        self.assertEqual(f_hit.cpu.a, 0x55AA, "Semantic page $87 hit must return remapped source word $55AA")
        self.assertLess(steps_hit, 300, f"Page-scoped search on 60-row page $87 took too long: {steps_hit}")

        # Case C: Semantic page $90 HIT (local_id=$0019 = 20+5 -> TL=$66B5)
        f_hit90 = Fixture(self.lib, self.s_rom, self.s_labels)
        f_hit90.word(0x7E008A, 0x0090)
        f_hit90.word(0x7E0002, 0x0000)
        f_hit90.word(0x7E2000 + 0x0010, 0x0019)
        _run_call(f_hit90, coll, a=0x0000, x=0x0019 * 8, y=0x0010, m16=True, x16=True, db=0x00)
        self.assertEqual(f_hit90.cpu.a, 0x66B5, "Semantic page $90 hit must return source word $66B5")

        # Case D: Semantic page $87 MISS (local_id=$0005 not in 10..69 -> returns fallback word $BEEF)
        f_miss = Fixture(self.lib, self.s_rom, self.s_labels)
        _run_call(
            f_miss, src_fn, a=0xBEEF, x=0x0087, y=0x0005 * 8, m16=True, x16=True, db=0x00
        )
        self.assertEqual(f_miss.cpu.a, 0xBEEF, "Miss on page $87 must return fallback word $BEEF")
        # Also verify non-semantic page $A0 is >3x faster in opcode count than semantic page $87 hit
        self.assertLess(steps_empty * 3, steps_hit, f"Fast-path ({steps_empty}) should beat binary search ({steps_hit}) by >3x")

    # ------------------------------------------------------------------
    # 6. A4 Abyss Return Vortex ($6C) Bidirectional Lifecycle
    # ------------------------------------------------------------------

    def test_a4_abyss_return_vortex_full_lifecycle(self) -> None:
        capture = self.q_labels["Oracle_AbyssVortex_CaptureOrigin"]
        reinit = self.q_labels["Oracle_SpecialOverworld_ReinitWarpVortex"]
        world_chk = self.q_labels["Oracle_AbyssVortex_Sprite6CWorldCheck"]
        consume = self.q_labels["Oracle_AbyssVortex_ConsumeOnEnter"]
        vortex_world = 0x7EC138

        # 1. Intro Pyramid drop (VortexWorld == $00 on Eon Abyss $4B) -> suppressed!
        f = self._fresh_q()
        f.put(0x7E008A, 0x4B)
        f.put(0x7EF3CA, 0x40)
        f.put(vortex_world, 0x00)
        _run_call(f, reinit)
        self.assertEqual(f.get(0x7F1100), 0, "Intro Pyramid drop must NOT spawn $6C")
        _run_call(f, world_chk, db=0x05)
        self.assertEqual(f.cpu.a & 0xFF, 0x01, "$6C must despawn in DW when VortexWorld==$00")

        # 2. Kalyxo ($0F) warp pad -> Eon Abyss ($4F): arms VortexWorld=$40, saves coords, spawns $6C!
        f.put(0x7E008A, 0x0F)
        f.word(0x7E0020, 0x0248)
        f.word(0x7E0022, 0x0E80)
        _run_call(f, capture, db=0x07)
        self.assertEqual(f.get(0x7E007B), 0x00)
        self.assertEqual(f.get(vortex_world), 0x40)
        self.assertEqual(f.get(0x7E1ADF), 0x48)
        self.assertEqual(f.get(0x7E1AEF), 0x02)
        self.assertEqual(f.get(0x7E1ABF), 0x80)
        self.assertEqual(f.get(0x7E1ACF), 0x0E)

        # Arrive on Eon Abyss $4F -> spawns $6C and keeps it alive!
        f.put(0x7E008A, 0x4F)
        f.put(0x7EF3CA, 0x40)
        _run_call(f, reinit)
        self.assertEqual(f.get(0x7F1100), 1, "Kalyxo->Abyss warp pad arrival MUST spawn $6C")
        _run_call(f, world_chk, db=0x05)
        self.assertEqual(f.cpu.a & 0xFF, 0x00, "$6C must stay alive in DW while VortexWorld==$40")

        # 3. Enter $6C in Eon Abyss ($4F) to return to Kalyxo ($0F) -> consumes VortexWorld!
        _run_call(f, consume, db=0x05)
        self.assertEqual(f.get(0x7E007B), 0x40)
        self.assertEqual(f.get(vortex_world), 0x00)

        # Arrive back on Kalyxo $0F -> NO duplicate $6C, and later house exit ALSO no ghost $6C!
        f.put(0x7E008A, 0x0F)
        f.put(0x7EF3CA, 0x00)
        _run_call(f, reinit)
        _run_call(f, reinit)
        self.assertEqual(f.get(0x7F1100), 1, "Returning via DW $6C must not spawn duplicate or ghost LW $6C")

        # 4. Eon Abyss ($4F) Magic Mirror -> Kalyxo ($0F): arms VortexWorld=$01, spawns LW $6C!
        f.put(0x7E008A, 0x4F)
        _run_call(f, capture, db=0x07)
        self.assertEqual(f.get(0x7E007B), 0x40)
        self.assertEqual(f.get(vortex_world), 0x01)
        f.put(0x7E008A, 0x0F)
        f.put(0x7EF3CA, 0x00)
        _run_call(f, reinit)
        self.assertEqual(f.get(0x7F1100), 2, "DW->LW Mirror must still spawn LW $6C")
        _run_call(f, world_chk, db=0x05)
        self.assertEqual(f.cpu.a & 0xFF, 0x00)
        _run_call(f, consume, db=0x05)
        self.assertEqual(f.get(0x7E007B), 0x00)
        self.assertEqual(f.get(vortex_world), 0x00)

        # 5. Special Overworld ($80-$BF) -> always suppressed!
        for area in (0x80, 0x99, 0xA0, 0xBF):
            f.put(0x7E008A, area)
            f.put(vortex_world, 0x40)
            _run_call(f, reinit)
            self.assertEqual(f.get(0x7F1100), 2, f"Special OW ${area:02X} must never spawn $6C")
            f.put(0x7EF3CA, 0x40)
            _run_call(f, world_chk, db=0x05)
            self.assertEqual(f.cpu.a & 0xFF, 0x01, f"Special OW ${area:02X} must despawn $6C")
            _run_call(f, capture, db=0x07)
            self.assertEqual(f.get(vortex_world), 0x00, f"Special OW ${area:02X} capture must clear VortexWorld")


if __name__ == "__main__":
    unittest.main()
