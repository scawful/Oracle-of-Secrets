#!/usr/bin/env python3
"""Compiled Asar + 65816 execution tests for QUEUE322:
Unified Special Overworld Transitions, Cross-World Boundary Crossings,
Dynamic Mixed-Size ByScreen, Two-Sided Mosaic, Module $09 Unification,
and Special Overworld Mode 7 World Map.
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

DIR_RIGHT = 0x00
DIR_LEFT = 0x02
DIR_DOWN = 0x04
DIR_UP = 0x06

SIZE_SMALL = 0
SIZE_LARGE = 1
SIZE_WIDE = 2
SIZE_TALL = 3

CROSS_WORLD_SEAMS = (
    (0x1F, 0x98, 0x1E, 0x90, SIZE_LARGE, SIZE_TALL),
    (0x27, 0xA0, 0x1E, 0xA0, SIZE_LARGE, SIZE_WIDE),
    (0x2F, 0xA8, 0x2F, 0xA8, SIZE_SMALL, SIZE_WIDE),
    (0x37, 0xB0, 0x36, 0xB0, SIZE_LARGE, SIZE_LARGE),
    (0x3F, 0xB8, 0x36, 0xB0, SIZE_LARGE, SIZE_LARGE),
)


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def expected_by_screen(
    src_cell: int,
    src_parent: int,
    dst_cell: int,
    dst_parent: int,
    dst_size: int,
    direction: int,
) -> int:
    """Exact closed-form ZSCustomOverworld v3 / yaze ByScreen1..4 formula."""
    src_off = src_cell - src_parent
    dst_off = dst_cell - dst_parent
    src_qx, src_qy = src_off & 1, (src_off >> 3) & 1
    dst_qx, dst_qy = dst_off & 1, (dst_off >> 3) & 1
    if direction == DIR_RIGHT:
        return (0x0060 + (dst_qy - src_qy) * 0x1000) & 0xFFFF
    if direction == DIR_LEFT:
        base = 0x0080 if dst_size in (SIZE_LARGE, SIZE_WIDE) else 0x0040
        return (base + (dst_qy - src_qy) * 0x1000) & 0xFFFF
    if direction == DIR_DOWN:
        return (0x1800 + (dst_qx - src_qx) * 0x0040) & 0xFFFF
    if direction == DIR_UP:
        base = 0x2000 if dst_size in (SIZE_LARGE, SIZE_TALL) else 0x1000
        return (base + (dst_qx - src_qx) * 0x0040) & 0xFFFF
    raise ValueError(direction)


def build_test_harness(directory: Path) -> tuple[bytes, dict[str, int]]:
    rom_path = directory / "harness.sfc"
    asm_path = directory / "harness.asm"
    sym_path = directory / "harness.sym"
    # 6 MB LoROM image (banks $00-$BF)
    buf = bytearray(0x600000)

    # Pre-seed vanilla preimage bytes checked by assertions in special_overworld_transitions.asm
    def put_bytes(snes: int, raw: bytes) -> None:
        pc = snes_to_pc(snes)
        buf[pc:pc + len(raw)] = raw

    put_bytes(0x02B1B4, bytes.fromhex("A908851164B060"))
    put_bytes(0x02A53C, bytes.fromhex("AD12010DE402"))
    put_bytes(0x02AE98, bytes.fromhex("AD0A04F019"))
    put_bytes(0x0AB9F0, bytes.fromhex("A68AE080B00CA5208F08C17EA5228F0AC17EE220"))
    put_bytes(0x0ABA40, bytes.fromhex("8BA90A48ABC230A2FE00A0FE00A58A294000F003A0FE01B927DB9F00C57E8888CACA10F3E230AB"))

    # Seed distinct LW ($0ADB27) and DW ($0ADC27) 256-byte World Map palettes
    lw_pal = b"".join(((0x1000 + i) & 0x7FFF).to_bytes(2, "little") for i in range(128))
    dw_pal = b"".join(((0x2000 + i) & 0x7FFF).to_bytes(2, "little") for i in range(128))
    put_bytes(0x0ADB27, lw_pal)
    put_bytes(0x0ADC27, dw_pal)
    rom_path.write_bytes(buf)

    # Build a self-contained test harness including special_overworld_transitions.asm
    # and RAM-backed Lyra_Read* stubs so tests can configure any 192-map layout dynamically!
    asm_src = f"""
lorom
!SPECIAL_OVERWORLD_NATIVE = 1
!OverworldMusicCache = $7EC900
SavedWorld = $7EF3CA
Pendants = $7EF374
Crystals = $7EF37A
!Pendant_Wisdom = $01
!Pendant_Power = $02
!Pendant_Courage = $04
!Crystal_D8_Sky = $80

; Test-controlled RAM tables in Bank $7F ($7F0000-$7F1FFF):
;   $7F0000..$7F00BF: parent[192]
;   $7F0100..$7F01BF: area_size[192]
;   $7F0200..$7F02BF: mosaic[192]
;   $7F0300..$7F03BF: main_palette[192]
;   $7F0400..$7F057F: overlay[192] (words)
;   $7F0600..$7F0BFF: gfx[192*8]
;   $7F0C00..$7F0D7F: transition_y[192] (words)
;   $7F0E00..$7F0F7F: transition_x[192] (words)
;   $7F1000: call counters (bitfield/bytes for stubs)

org $02AE9D
VanillaFBlankNonZero:
  LDA.b #$AA : STA.l $7F1000
  RTS

org $02AEB5
VanillaFBlankRts:
  RTS

org $02AEB6
VanillaFBlankZero:
  LDA.b #$BB : STA.l $7F1000
  RTS

org $0ED61D
Stub_SetScreenBGColorCacheOnly:
  PHP : SEP #$20
  LDA.b #$01 : STA.l $7F1003
  PLP : RTL

org $348000
Lyra_ReadParent:
  LDA.l $7F0000, X
  RTL
Lyra_ReadSize:
  LDA.l $7F0100, X
  RTL
Lyra_ReadMosaic:
  LDA.l $7F0200, X
  RTL
Lyra_ReadMainPalette:
  LDA.l $7F0300, X
  RTL
Lyra_ReadOverlay:
  LDA.l $7F0400, X
  RTL
Lyra_ReadGfx0:
  LDA.l $7F0600, X
  RTL
Lyra_ReadGfx1:
  LDA.l $7F0601, X
  RTL
Lyra_ReadGfx2:
  LDA.l $7F0602, X
  RTL
Lyra_ReadGfx7:
  LDA.l $7F0607, X
  RTL
Lyra_ReadByScreen:
  LDA.w #$BEEF
  RTL

Overworld_LoadMapProperties_Long:
  PHP : REP #$30 : PHA : PHX
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  LDA.l $7F0C00, X : STA.w $0708
  LDA.l $7F0E00, X : LSR #3 : STA.w $070C
  SEP #$20
  LDA.b #$01 : STA.l $7F1001
  REP #$30 : PLX : PLA : PLP
  RTL

Overworld_LoadAreaPalettes_Long:
  PHP : SEP #$20
  LDA.b #$01 : STA.l $7F1002
  PLP : RTL

Copy0716:
  LDA.b #$E4 : STA.w $0716 : STA.w $0718
  RTL

NewOverworld_SetCameraBounds:
  ; Entry M=16, X=8; compute $0600..$0606 from transition_y/x + area_size
  PHP : PHB : PHK : PLB : REP #$30 : PHA : PHX : PHY
  LDA.b $8A : AND.w #$00FF : TAX
  LDA.l $7F0100, X : AND.w #$00FF : ASL : TAY ; Y = size*2
  LDA.b $8A : AND.w #$00FF : ASL : TAX
  LDA.l $7F0C00, X : STA.w $0600
  CLC : ADC.w .y_span, Y : STA.w $0602
  LDA.l $7F0E00, X : STA.w $0604
  CLC : ADC.w .x_span, Y : STA.w $0606
  PLY : PLX : PLA : PLB : PLP
  RTL
  .y_span: dw $011E, $031E, $011E, $031E
  .x_span: dw $0100, $0300, $0300, $0100

org $5F8000
SWWorldMap_Tiles:
  incbin "{ROOT}/Overworld/world_map/SwMapTileset.bin"
SWWorldMap_Gfx:
  incbin "{ROOT}/Overworld/world_map/SwMapGfx.bin"
SWPalettes:
  incbin "{ROOT}/Overworld/world_map/sw_palette.bin"

incsrc "{ROOT}/Overworld/special_overworld_transitions.asm"
"""
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
        raise AssertionError(f"asar failed:\n{proc.stdout}\n{proc.stderr}")
    labels: dict[str, int] = {}
    for bank, offset, name in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z0-9_.:]+)$",
        sym_path.read_text(encoding="utf-8"),
        re.M,
    ):
        labels[name] = (int(bank, 16) << 16) | int(offset, 16)
    return rom_path.read_bytes(), labels


def _run_jsl(
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
    max_steps: int = 50000,
) -> None:
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
    if is_rts:
        frame = (0x6F, 0xFF)
    else:
        frame = (p.k, 0x6F, 0xFF)
    for b in frame:
        f.put(p.sp, b)
        p.sp -= 1
    target_k = p.k if not is_rts else 0x02
    for _ in range(max_steps):
        if p.pc == 0x7000 and p.k == target_k:
            assert p.sp == initial_sp, f"Stack imbalance: sp={p.sp:04X} vs {initial_sp:04X}"
            assert not f.bad_writes, f"Bad ROM/IO writes: {f.bad_writes}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction limit at ${p.k:02X}:{p.pc:04X}")


@unittest.skipUnless(ASAR_BIN and LAKESNES_DIR.exists(), "asar and LakeSnes required")
class SpecialOverworldTransitionsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="q322-tests-")
        tmp_path = Path(cls.tmp.name)
        cls.rom, cls.labels = build_test_harness(tmp_path)
        libpath = tmp_path / "cpu.dylib"
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
        cls.lib = C.CDLL(str(libpath))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _fresh(self) -> Fixture:
        f = Fixture(self.lib, self.rom, self.labels)
        # Initialize default identity parents, small sizes, FF overlays, standard gfx8
        for m in range(0xC0):
            f.put(0x7F0000 + m, m)
            f.put(0x7F0100 + m, SIZE_SMALL)
            f.put(0x7F0200 + m, 0x00)
            f.put(0x7F0300 + m, 0x00)
            f.word(0x7F0400 + m * 2, 0x00FF)
            r = (m & 0x3F) >> 3
            c = m & 7
            f.word(0x7F0C00 + m * 2, r * 0x200)
            f.word(0x7F0E00 + m * 2, c * 0x200)
            for k, b in enumerate((0x3A, 0x3B, 0x3C, 0x3D, 0x47, 0x48, 0x3E, 0x5B)):
                f.put(0x7F0600 + m * 8 + k, b)
        # Configure the real Special Overworld & seam LW multi-area structures
        multi_areas = [
            # LW Col 7 seam parents
            (0x1E, SIZE_LARGE, (0x1E, 0x1F, 0x26, 0x27)),
            (0x36, SIZE_LARGE, (0x36, 0x37, 0x3E, 0x3F)),
            # Special Overworld multi-areas
            (0x81, SIZE_LARGE, (0x81, 0x82, 0x89, 0x8A)),
            (0x83, SIZE_TALL, (0x83, 0x8B)),
            (0x90, SIZE_TALL, (0x90, 0x98)),
            (0xA0, SIZE_WIDE, (0xA0, 0xA1)),
            (0xA6, SIZE_LARGE, (0xA6, 0xA7, 0xAE, 0xAF)),
            (0xA8, SIZE_WIDE, (0xA8, 0xA9)),
            (0xB0, SIZE_LARGE, (0xB0, 0xB1, 0xB8, 0xB9)),
            (0xB3, SIZE_LARGE, (0xB3, 0xB4, 0xBB, 0xBC)),
            (0xB5, SIZE_TALL, (0xB5, 0xBD)),
            (0xBE, SIZE_WIDE, (0xBE, 0xBF)),
        ]
        for parent, sz, cells in multi_areas:
            pr = (parent & 0x3F) >> 3
            pc = parent & 7
            for cell in cells:
                f.put(0x7F0000 + cell, parent)
                f.put(0x7F0100 + cell, sz)
                f.word(0x7F0C00 + cell * 2, pr * 0x200)
                f.word(0x7F0E00 + cell * 2, pc * 0x200)
        return f

    def test_cross_world_all_5_bidirectional_seams(self) -> None:
        for lw, sw, lw_par, sw_par, _lw_sz, _sw_sz in CROSS_WORLD_SEAMS:
            row = (lw & 0x3F) >> 3
            test_y = row * 0x200 + 0x00E0

            # 1. LW Col 7 East -> SW Col 0
            with self.subTest(seam=f"${lw:02X}->${sw:02X}"):
                f = self._fresh()
                try:
                    f.put(0x10, 0x09)
                    f.word(0x8A, lw_par)
                    f.word(0x040A, lw_par)
                    f.word(0x0700, (lw & 0x3F) * 2)
                    f.put(0x02, DIR_RIGHT)
                    f.word(0x20, test_y)
                    f.word(0x22, 0x0FE8)
                    f.put(0x0130, 0x02)
                    f.put(0x7EC900 + sw_par, 0x09)  # different music track
                    f.put(0x7EF3CA, 0x00)
                    f.word(0xA0, 0x0182)  # stale special exit must be cleared

                    _run_jsl(f, self.labels["SpecialOverworld_TryCrossWorld"])
                    self.assertTrue(f.cpu.c, "Cross-world East should set Carry")
                    self.assertEqual(f.get(0x7EC132), sw)
                    self.assertEqual(f.get(0x10), 0x09)
                    self.assertEqual(f.get(0x11), 0x24)
                    self.assertEqual(f.get(0x012C), 0xF1)

                    # Now execute FBlank hook at $02AE98 (DBR=$02, RTS exit at $02AEB5)
                    _run_jsl(f, 0x02AE98, db=0x02, is_rts=True)
                    self.assertEqual(f.get(0x7EC132), 0x00)
                    self.assertEqual(f.get(0x8A), sw_par)
                    self.assertEqual(f.get(0x040A), sw_par)
                    self.assertEqual(f.get(0x7EF3CA), 0x00)
                    self.assertEqual(f.get(0xA0) | (f.get(0xA1) << 8), 0x0000)
                    self.assertEqual(f.get(0x22) | (f.get(0x23) << 8), 0x000E)
                    self.assertEqual(f.get(0x20) | (f.get(0x21) << 8), test_y)
                    self.assertEqual(f.get(0x2F), 0x06)  # facing Right
                    self.assertEqual(f.get(0x069C), 0x03)
                    self.assertEqual(f.get(0x11), 0x25)
                    self.assertEqual(f.get(0x0700) | (f.get(0x0701) << 8), (sw & 0x3F) * 2)
                    # Verify camera clamped within [$0600..$0602] and [$0604..$0606]
                    cam_y = f.get(0xE8) | (f.get(0xE9) << 8)
                    cam_x = f.get(0xE2) | (f.get(0xE3) << 8)
                    min_y = f.get(0x0600) | (f.get(0x0601) << 8)
                    max_y = f.get(0x0602) | (f.get(0x0603) << 8)
                    min_x = f.get(0x0604) | (f.get(0x0605) << 8)
                    max_x = f.get(0x0606) | (f.get(0x0607) << 8)
                    self.assertTrue(min_y <= cam_y <= max_y, f"cam_y {cam_y:04X} outside [{min_y:04X}..{max_y:04X}]")
                    self.assertTrue(min_x <= cam_x <= max_x, f"cam_x {cam_x:04X} outside [{min_x:04X}..{max_x:04X}]")
                    self.assertEqual(cam_x, 0x0000)
                    # Verify exact $84 formula
                    orig_y = f.get(0x0708) | (f.get(0x0709) << 8)
                    orig_x = (f.get(0x070C) | (f.get(0x070D) << 8)) << 3
                    exp84 = ((((cam_y - orig_y) & 0x03F0) << 3) | (((cam_x - orig_x) & 0x03F0) >> 3)) & 0xFFFF
                    self.assertEqual(f.get(0x84) | (f.get(0x85) << 8), exp84)
                    self.assertEqual(f.get(0x7F1001), 1)
                    self.assertEqual(f.get(0x7F1002), 1)
                    self.assertEqual(f.get(0x7F1003), 1)
                finally:
                    f.close()

            # 2. SW Col 0 West -> LW Col 7
            with self.subTest(seam=f"${sw:02X}->${lw:02X}"):
                f = self._fresh()
                try:
                    f.put(0x10, 0x09)
                    f.word(0x8A, sw_par)
                    f.word(0x040A, sw_par)
                    f.word(0x0700, (sw & 0x3F) * 2)
                    f.put(0x02, DIR_LEFT)
                    f.word(0x20, test_y)
                    f.word(0x22, 0x0004)
                    f.put(0x0130, 0x09)
                    f.put(0x7EC900 + lw_par, 0x02)

                    _run_jsl(f, self.labels["SpecialOverworld_TryCrossWorld"])
                    self.assertTrue(f.cpu.c, "Cross-world West should set Carry")
                    self.assertEqual(f.get(0x7EC132), lw)
                    self.assertEqual(f.get(0x11), 0x24)

                    _run_jsl(f, 0x02AE98, db=0x02, is_rts=True)
                    self.assertEqual(f.get(0x8A), lw_par)
                    self.assertEqual(f.get(0x040A), lw_par)
                    self.assertEqual(f.get(0x7EF3CA), 0x00)
                    self.assertEqual(f.get(0x22) | (f.get(0x23) << 8), 0x0FE2)
                    self.assertEqual(f.get(0x20) | (f.get(0x21) << 8), test_y)
                    self.assertEqual(f.get(0x2F), 0x04)  # facing Left
                    self.assertEqual(f.get(0x069C), 0x02)
                    self.assertEqual(f.get(0x11), 0x25)
                    self.assertEqual(f.get(0x0700) | (f.get(0x0701) << 8), (lw & 0x3F) * 2)
                    cam_x = f.get(0xE2) | (f.get(0xE3) << 8)
                    self.assertEqual(cam_x, 0x0F00)
                finally:
                    f.close()

    def test_non_seam_edges_do_not_trigger_cross_world(self) -> None:
        reject_cases = [
            (0x07, 0x07, DIR_RIGHT),  # LW row 0 col 7
            (0x0F, 0x0F, DIR_RIGHT),  # LW row 1 col 7
            (0x17, 0x17, DIR_RIGHT),  # LW row 2 col 7
            (0x1F, 0x1E, DIR_LEFT),   # wrong direction on LW seam
            (0x1F, 0x1E, DIR_DOWN),   # wrong direction
            (0x5F, 0x5E, DIR_RIGHT),  # Dark World col 7
            (0x80, 0x80, DIR_LEFT),   # SW row 0 col 0
            (0x88, 0x88, DIR_LEFT),   # SW row 1 col 0
            (0x90, 0x90, DIR_LEFT),   # SW row 2 col 0
            (0x98, 0x90, DIR_RIGHT),  # wrong direction on SW seam
            (0xA1, 0xA0, DIR_LEFT),   # interior SW col 1
        ]
        for cell, parent, direction in reject_cases:
            with self.subTest(cell=f"${cell:02X}", dir=direction):
                f = self._fresh()
                try:
                    f.word(0x8A, parent)
                    f.word(0x0700, (cell & 0x3F) * 2)
                    f.put(0x02, direction)
                    _run_jsl(f, self.labels["SpecialOverworld_TryCrossWorld"])
                    self.assertFalse(f.cpu.c)
                    self.assertEqual(f.get(0x7EC132), 0x00)
                finally:
                    f.close()

    def test_dynamic_by_screen_all_mixed_size_combinations(self) -> None:
        f = self._fresh()
        try:
            # Test key Special Overworld mixed-size transitions including $8A <-> $92
            pairs = [
                (0x8A, 0x92, DIR_DOWN),   # Large SE -> Small ($17C0)
                (0x92, 0x8A, DIR_UP),     # Small -> Large SE ($2040)
                (0x82, 0x83, DIR_RIGHT),  # Large NE -> Tall N ($0060)
                (0x83, 0x82, DIR_LEFT),   # Tall N -> Large NE ($0080)
                (0x8A, 0x8B, DIR_RIGHT),  # Large SE -> Tall S ($0060)
                (0x8B, 0x8A, DIR_LEFT),   # Tall S -> Large SE ($0080)
                (0x98, 0x99, DIR_RIGHT),  # Tall S -> Small ($F060)
                (0x99, 0x98, DIR_LEFT),   # Small -> Tall S ($1040)
                (0x98, 0xA0, DIR_DOWN),   # Tall S -> Wide W ($1800)
                (0xA0, 0x98, DIR_UP),     # Wide W -> Tall S ($2000)
                (0x99, 0xA1, DIR_DOWN),   # Small -> Wide E ($1840)
                (0xA1, 0x99, DIR_UP),     # Wide E -> Small ($0FC0)
                (0xA1, 0xA2, DIR_RIGHT),  # Wide E -> Small ($0060)
                (0xA2, 0xA1, DIR_LEFT),   # Small -> Wide E ($0080)
                (0xA5, 0xA6, DIR_RIGHT),  # Small -> Large NW ($0060)
                (0xAD, 0xAE, DIR_RIGHT),  # Small -> Large SW ($1060)
                (0xAE, 0xAD, DIR_LEFT),   # Large SW -> Small ($F040)
                (0xA9, 0xB1, DIR_DOWN),   # Wide E -> Large NE ($1800)
                (0xB1, 0xA9, DIR_UP),     # Large NE -> Wide E ($1000)
                (0xB9, 0xBA, DIR_RIGHT),  # Large SE -> Small ($F060)
                (0xBA, 0xB9, DIR_LEFT),   # Small -> Large SE ($1080)
                (0xBC, 0xBD, DIR_RIGHT),  # Large SE -> Tall S ($0060)
                (0xBD, 0xBC, DIR_LEFT),   # Tall S -> Large SE ($0080)
                (0xBD, 0xBE, DIR_RIGHT),  # Tall S -> Wide W ($F060)
                (0xBE, 0xBD, DIR_LEFT),   # Wide W -> Tall S ($1040)
                (0xAF, 0xB7, DIR_DOWN),   # Large SE -> Small ($17C0)
                (0xB7, 0xAF, DIR_UP),     # Small -> Large SE ($2040)
                (0xB7, 0xBF, DIR_DOWN),   # Small -> Wide E ($1840)
                (0xBF, 0xB7, DIR_UP),     # Wide E -> Small ($0FC0)
            ]
            for src, dst, direction in pairs:
                src_par = f.get(0x7F0000 + src)
                dst_par = f.get(0x7F0000 + dst)
                dst_sz = f.get(0x7F0100 + dst_par)
                exp = expected_by_screen(src, src_par, dst, dst_par, dst_sz, direction)
                with self.subTest(src=f"${src:02X}", dst=f"${dst:02X}", dir=direction):
                    f.word(0x8A, src_par)
                    f.word(0x0700, (src & 0x3F) * 2)
                    _run_jsl(
                        f,
                        self.labels["SpecialOverworld_ReadByScreen"],
                        a=dst * 2,
                        x=direction,
                        y=0x1234,
                        m16=True,
                        x16=True,
                    )
                    self.assertEqual(f.cpu.a, exp, f"got ${f.cpu.a:04X}, expected ${exp:04X}")
                    self.assertEqual(f.cpu.x, direction)
                    self.assertEqual(f.cpu.y, 0x1234)

            # Non-special (< $80) delegates to Lyra_ReadByScreen ($BEEF stub)
            f.word(0x8A, 0x10)
            f.word(0x0700, 0x20)
            _run_jsl(
                f,
                self.labels["SpecialOverworld_ReadByScreen"],
                a=0x11 * 2,
                x=DIR_RIGHT,
                m16=True,
                x16=True,
            )
            self.assertEqual(f.cpu.a, 0xBEEF)
        finally:
            f.close()

    def test_two_sided_mosaic_and_special_compatibility(self) -> None:
        f = self._fresh()
        try:
            # Seed one-sided East mosaic bits matching Q319 audit ($02->$03, $40->$42, $81->$83)
            f.put(0x7F0200 + 0x02, 0x01)
            f.put(0x7F0200 + 0x40, 0x01)
            f.put(0x7F0200 + 0x81, 0x01)
            # Korok Cove ($81) has fog overlay $0097; North Reef ($92) has $00FF
            f.word(0x7F0400 + 0x81 * 2, 0x0097)
            f.word(0x7F0400 + 0x92 * 2, 0x00FF)
            # Shrine of Courage ($A6) has main_palette $05 and gfx0=$69
            f.put(0x7F0300 + 0xA6, 0x05)
            f.put(0x7F0600 + 0xA6 * 8, 0x69)
            # Sea Zora ($90) has gfx0=$5E
            f.put(0x7F0600 + 0x90 * 8, 0x5E)
            # Sky hosts ($87, $8C-$8F) share overlay $0094, differ in main_palette/gfx0
            for sky in (0x87, 0x8C, 0x8D, 0x8E, 0x8F):
                f.word(0x7F0400 + sky * 2, 0x0094)
            f.put(0x7F0300 + 0x87, 0x03)
            f.put(0x7F0300 + 0x8C, 0x02)
            f.put(0x7F0600 + 0x87 * 8, 0xEB)
            f.put(0x7F0600 + 0x8F * 8, 0xEB)
            f.put(0x7F0600 + 0x87 * 8 + 1, 0xF2)
            f.put(0x7F0600 + 0x8F * 8 + 1, 0xF5)

            # (old_parent, new_parent, dir_bit, dir_idx_0418, expect_mosaic)
            # $0418: 0=Up($08), 1=Down($04), 2=Left($02), 3=Right($01)
            cases = [
                # Symmetric LW & DW MosaicTable fix
                (0x02, 0x03, 0x01, 3, True),
                (0x03, 0x02, 0x02, 2, True),
                (0x40, 0x42, 0x01, 3, True),
                (0x42, 0x40, 0x02, 2, True),
                (0x05, 0x06, 0x01, 3, False),
                # Symmetric SW MosaicTable ($81 <-> $83)
                (0x81, 0x83, 0x01, 3, True),
                (0x83, 0x81, 0x02, 2, True),
                # Overlay mismatch ($81 <-> $92)
                (0x81, 0x92, 0x04, 1, True),
                (0x92, 0x81, 0x08, 0, True),
                # Main palette & main BG sheet mismatch ($A5 <-> $A6, $90 <-> $A0)
                (0xA5, 0xA6, 0x01, 3, True),
                (0xA6, 0xA5, 0x02, 2, True),
                (0x90, 0xA0, 0x04, 1, True),
                (0xA0, 0x90, 0x08, 0, True),
                # Compatible Lyra Sea & Zora Coast & Deku/Goron -> smooth normal scroll!
                (0xA2, 0xA3, 0x01, 3, False),
                (0xA0, 0xA2, 0x01, 3, False),
                (0xA8, 0xB0, 0x04, 1, False),
                # Sky-to-Sky route -> smooth normal scroll (preserves sky_overlay_transition.asm)
                (0x8C, 0x8D, 0x01, 3, False),
                (0x8F, 0x87, 0x08, 0, False),
            ]
            for old_p, new_p, dbit, didx, expect in cases:
                with self.subTest(old=f"${old_p:02X}", new=f"${new_p:02X}", dbit=dbit):
                    f.word(0x8A, new_p)
                    f.put(0x0416, dbit)
                    f.put(0x0418, didx)
                    _run_jsl(f, self.labels["SpecialOverworld_ShouldMosaic"], x=old_p, y=0x77)
                    self.assertEqual(bool(f.cpu.a & 0xFF), expect)
                    self.assertEqual(f.cpu.x & 0xFF, old_p)
                    self.assertEqual(f.cpu.y & 0xFF, 0x77)
        finally:
            f.close()

    def test_module09_unification_helpers(self) -> None:
        f = self._fresh()
        try:
            f.put(0x10, 0x0B)
            f.put(0x11, 0x1C)
            f.put(0xB0, 0x02)
            _run_jsl(f, self.labels["SpecialOverworld_FinishSpecialEntry"])
            self.assertEqual(f.get(0x10), 0x09)
            self.assertEqual(f.get(0x11), 0x08)
            self.assertEqual(f.get(0xB0), 0x00)

            f.put(0x10, 0x0B)
            _run_jsl(f, self.labels["SpecialOverworld_NormalizeModule09"])
            self.assertEqual(f.get(0x10), 0x09)

            f.put(0x10, 0x09)
            _run_jsl(f, self.labels["SpecialOverworld_NormalizeModule09"])
            self.assertEqual(f.get(0x10), 0x09)
        finally:
            f.close()

    def test_special_world_map_pos_palette_icons_and_assets(self) -> None:
        # 1. Verify Mode 7 binary assets and Bank $5F bounds
        wm_dir = ROOT / "Overworld" / "world_map"
        tileset = (wm_dir / "SwMapTileset.bin").read_bytes()
        gfx = (wm_dir / "SwMapGfx.bin").read_bytes()
        pal = (wm_dir / "sw_palette.bin").read_bytes()
        self.assertEqual(len(tileset), 4096)
        self.assertEqual(len(gfx), 16384)
        self.assertEqual(len(pal), 256)
        self.assertLess(max(gfx), 128, "Mode 7 pixels must remain in BG palette 0..127")
        self.assertLessEqual(self.labels["SWPalettes"] + len(pal), 0x5FD200)
        self.assertLessEqual(self.labels["SpecialOverworld_TransitionsCodeEnd"], 0x5FFFFF)

        # 2. Link dot save/restore preserves Korok Cove return cache on $80-$BF
        f = self._fresh()
        try:
            f.word(0x7EC108, 0x0244)  # saved $0F return Y
            f.word(0x7EC10A, 0x0E88)  # saved $0F return X
            f.word(0x8A, 0x81)
            f.word(0x20, 0x0350)
            f.word(0x22, 0x0520)
            _run_jsl(f, self.labels["SpecialOverworld_SaveAndSetMapPos"], m16=True, x16=False, db=0x0A)
            self.assertEqual(f.get(0x7EC108) | (f.get(0x7EC109) << 8), 0x0350)
            self.assertEqual(f.get(0x7EC10A) | (f.get(0x7EC10B) << 8), 0x0520)
            self.assertEqual(f.get(0x7EC137), 0x01)

            _run_jsl(f, self.labels["SpecialOverworld_RestoreMapPos"], db=0x0A)
            self.assertEqual(f.get(0x7EC108) | (f.get(0x7EC109) << 8), 0x0244)
            self.assertEqual(f.get(0x7EC10A) | (f.get(0x7EC10B) << 8), 0x0E88)
            self.assertEqual(f.get(0x7EC137), 0x00)

            # 3. 3-way palette loader: LW, DW, SW
            for area, exp_word0 in ((0x18, 0x1000), (0x5B, 0x2000), (0xA6, int.from_bytes(pal[:2], "little"))):
                f.word(0x8A, area)
                _run_jsl(f, self.labels["SpecialOverworld_LoadWorldMapPalette"], db=0x0A)
                got0 = f.get(0x7EC500) | (f.get(0x7EC501) << 8)
                self.assertEqual(got0, exp_word0, f"palette word0 mismatch for area ${area:02X}")

            # 4. Special Overworld landmark icons (shown when uncollected, hidden when collected)
            f.put(0x7EF374, 0x00)  # no pendants
            f.put(0x7EF37A, 0x00)  # no crystals
            expected_coords = [
                (0x0300, 0x04E0),  # 0: Shrine of Wisdom ($91)
                (0x0DC0, 0x09C0),  # 1: Shrine of Courage ($A6)
                (0x0200, 0x0DC0),  # 2: Shrine of Power ($B0)
                (0x0F00, 0x0100),  # 3: Sky Tower / D8 ($87)
            ]
            for idx, (ex, ey) in enumerate(expected_coords):
                _run_jsl(f, self.labels["SpecialOverworld_SetupMapIcon"], a=idx)
                self.assertTrue(f.cpu.c, f"Icon {idx} should draw when uncollected")
                gx = f.get(0x7EC10A) | (f.get(0x7EC10B) << 8)
                gy = f.get(0x7EC108) | (f.get(0x7EC109) << 8)
                self.assertEqual((gx, gy), (ex, ey))

            # Collect all 3 pendants + D8 crystal -> all 4 icons hide cleanly
            f.put(0x7EF374, 0x07)
            f.put(0x7EF37A, 0x80)
            for idx in range(4):
                _run_jsl(f, self.labels["SpecialOverworld_SetupMapIcon"], a=idx)
                self.assertFalse(f.cpu.c, f"Icon {idx} should hide when collected")
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
