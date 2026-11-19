#!/usr/bin/env python3
"""Compiled 65816 + contract tests for Menu v5 Special Overworld ($80-$BF)
location names and unified multi-cell Mini-Map footprints (Small/Large/Wide/Tall).

Assembles the real Menu/menu_v5_ext.asm, Menu/menu_map_names.asm, and
Menu/menu_text.asm (DrawLocationName) with asar into isolated synthetic LoROM
images (both native rev5 !SPECIAL_OVERWORLD_NATIVE=1 and legacy =0) and runs
the compiled 65816 code on LakeSnes's C CPU core.
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d4_compiled_fight_check import Cpu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# Synthetic ROM table addresses for !SPECIAL_OVERWORLD_NATIVE == 1 test build
NAT_PARENT_ADDR = 0x468000
NAT_SIZE_ADDR = 0x468100
LEG_PARENT_ADDR = 0x288998
LEG_SIZE_ADDR = 0x02F88D

PANEL_BLANK = 0x3417

EXPECTED_SPECIAL_NAMES: dict[int, str] = {
    0x80: "FOREST GLADE",
    0x81: "KOROK COVE",
    0x82: "KOROK COVE",
    0x83: "ROYAL GARRISON",
    0x84: "SKY ISLANDS",
    0x85: "SKY ISLANDS",
    0x86: "SKY ISLANDS",
    0x87: "SKY TOWER",
    0x88: "FOREST GLADE",
    0x89: "KOROK COVE",
    0x8A: "KOROK COVE",
    0x8B: "ROYAL GARRISON",
    0x8C: "SKY ISLANDS",
    0x8D: "SKY ISLANDS",
    0x8E: "SKY ISLANDS",
    0x8F: "SKY ISLANDS",
    0x90: "SEA ZORA TEMPLE",
    0x91: "SHRINE OF WISDOM",
    0x92: "ZORA COAST",
    0x93: "LYRA SEA",
    0x94: "LYRA SEA",
    0x95: "LYRA SEA",
    0x96: "LYRA SEA",
    0x97: "LYRA SEA",
    0x98: "ZORA LAGOON",
    0x99: "ZORA QUAY",
    0x9A: "LYRA SEA",
    0x9B: "LYRA SEA",
    0x9C: "LYRA SEA",
    0x9D: "LYRA SEA",
    0x9E: "LYRA SEA",
    0x9F: "LYRA SEA",
    0xA0: "ZORA COAST",
    0xA1: "ZORA COAST",
    0xA2: "LYRA SEA",
    0xA3: "LYRA SEA",
    0xA4: "LYRA SEA",
    0xA5: "LYRA SEA",
    0xA6: "COURAGE ISLAND",
    0xA7: "COURAGE ISLAND",
    0xA8: "DEKU GROVE",
    0xA9: "DEKU GROVE",
    0xAA: "LYRA SEA",
    0xAB: "LYRA SEA",
    0xAC: "LYRA SEA",
    0xAD: "LYRA SEA",
    0xAE: "COURAGE ISLAND",
    0xAF: "COURAGE ISLAND",
    0xB0: "GORON COAST",
    0xB1: "GORON COAST",
    0xB2: "LYRA SEA",
    0xB3: "CRESCENT ATOLL",
    0xB4: "CRESCENT ATOLL",
    0xB5: "PIRATE SHIP",
    0xB6: "LYRA SEA",
    0xB7: "LYRA SEA",
    0xB8: "GORON COAST",
    0xB9: "GORON COAST",
    0xBA: "LYRA SEA",
    0xBB: "CRESCENT ATOLL",
    0xBC: "CRESCENT ATOLL",
    0xBD: "PIRATE SHIP",
    0xBE: "FROST GLACIER",
    0xBF: "FROST GLACIER",
}

EXPECTED_SPECIAL_WRAPPED: dict[str, tuple[str, str]] = {
    "FOREST GLADE": ("FOREST GLADE", ""),
    "KOROK COVE": ("KOROK COVE", ""),
    "ROYAL GARRISON": ("ROYAL", "GARRISON"),
    "SKY ISLANDS": ("SKY ISLANDS", ""),
    "SKY TOWER": ("SKY TOWER", ""),
    "SEA ZORA TEMPLE": ("SEA ZORA", "TEMPLE"),
    "SHRINE OF WISDOM": ("SHRINE OF", "WISDOM"),
    "ZORA COAST": ("ZORA COAST", ""),
    "LYRA SEA": ("LYRA SEA", ""),
    "ZORA LAGOON": ("ZORA LAGOON", ""),
    "ZORA QUAY": ("ZORA QUAY", ""),
    "COURAGE ISLAND": ("COURAGE", "ISLAND"),
    "DEKU GROVE": ("DEKU GROVE", ""),
    "GORON COAST": ("GORON COAST", ""),
    "CRESCENT ATOLL": ("CRESCENT", "ATOLL"),
    "PIRATE SHIP": ("PIRATE SHIP", ""),
    "FROST GLACIER": ("FROST", "GLACIER"),
}


def build_rev5_geometry() -> tuple[list[int], list[int]]:
    """Canonical 192-map (parent, size) tables matching live rev5 ROM."""
    parent = list(range(0xC0))
    size = [0] * 0xC0

    def set_large(p: int) -> None:
        for d in (0, 1, 8, 9):
            parent[p + d] = p
            size[p + d] = 1

    def set_wide(p: int) -> None:
        for d in (0, 1):
            parent[p + d] = p
            size[p + d] = 2

    def set_tall(p: int) -> None:
        for d in (0, 8):
            parent[p + d] = p
            size[p + d] = 3

    # LW ($00-$3F)
    for p in (0x00, 0x0B, 0x18, 0x1E, 0x23, 0x33, 0x36):
        set_large(p)
    for p in (0x30, 0x38):
        set_wide(p)

    # DW ($40-$7F)
    for p in (0x40, 0x4B, 0x58, 0x5E, 0x63, 0x70, 0x73, 0x76):
        set_large(p)

    # SW ($80-$BF)
    for p in (0x81, 0xA6, 0xB0, 0xB3):
        set_large(p)
    for p in (0xA0, 0xA8, 0xBE):
        set_wide(p)
    for p in (0x83, 0x90, 0xB5):
        set_tall(p)

    return parent, size


def find_lakesnes() -> Path | None:
    env = os.environ.get("OOS_LAKESNES")
    cands = [Path(env)] if env else []
    cands.extend([
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ])
    for cand in cands:
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def find_asar() -> str | None:
    return shutil.which("asar") or shutil.which("z3asm")


_LAKESNES_LIB = None
_LAKESNES_TMP = None


def get_lakesnes_lib():
    global _LAKESNES_LIB, _LAKESNES_TMP
    if _LAKESNES_LIB is not None:
        return _LAKESNES_LIB
    src_root = find_lakesnes()
    if src_root is None:
        return None
    _LAKESNES_TMP = tempfile.TemporaryDirectory(prefix="oos-minimap-lakesnes-")
    so_path = Path(_LAKESNES_TMP.name) / "libcpu.dylib"
    subprocess.run(
        [
            "cc", "-shared", "-fPIC", "-O2",
            str(src_root / "snes" / "cpu.c"),
            str(src_root / "snes" / "statehandler.c"),
            "-o", str(so_path),
        ],
        check=True,
    )
    lib = C.CDLL(str(so_path))
    lib.cpu_init.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_runOpcode.restype = C.c_int
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    _LAKESNES_LIB = lib
    return lib


def lorom_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def parse_sym(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in sym_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", line.strip())
        if m and ":" not in m.group(3):
            labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


def extract_block(text: str, label: str) -> str:
    start = text.index(label + ":")
    opened = text.index("{", start)
    depth = 1
    i = opened + 1
    while depth:
        depth += (text[i] == "{") - (text[i] == "}")
        i += 1
    return text[start:i] + "\n"


def assemble_menu_fixture(
    native: bool,
    parent_tbl: list[int],
    size_tbl: list[int],
) -> tuple[bytes, dict[str, int]]:
    asar = find_asar()
    assert asar is not None, "asar binary required"

    menu_text = (ROOT / "Menu" / "menu_text.asm").read_text(encoding="utf-8")
    draw_loc_block = extract_block(menu_text, "DrawLocationName")

    with tempfile.TemporaryDirectory(prefix="oos-minimap-asm-") as tmp:
        td = Path(tmp)
        rom = bytearray(0x280000)  # 2.5 MiB LoROM covers banks $00..$4F -> extend to 3.5 MiB for $54
        rom = bytearray(0x300000)  # banks $00..$5F
        # Populate legacy ($00..$9F) and native ($00..$BF) geometry tables
        p_leg = lorom_pc(LEG_PARENT_ADDR)
        s_leg = lorom_pc(LEG_SIZE_ADDR)
        rom[p_leg:p_leg + 0xA0] = bytes(parent_tbl[:0xA0])
        rom[s_leg:s_leg + 0xA0] = bytes(size_tbl[:0xA0])
        p_nat = lorom_pc(NAT_PARENT_ADDR)
        s_nat = lorom_pc(NAT_SIZE_ADDR)
        rom[p_nat:p_nat + 0xC0] = bytes(parent_tbl[:0xC0])
        rom[s_nat:s_nat + 0xC0] = bytes(size_tbl[:0xC0])

        rom_path = td / "fixture.sfc"
        asm_path = td / "fixture.asm"
        sym_path = td / "fixture.sym"
        rom_path.write_bytes(rom)

        menu_dir = ROOT / "Menu"
        asm_src = f"""lorom
function menu_offset(row, col) = (row*64)+(col*2)
!SPECIAL_OVERWORLD_NATIVE = {1 if native else 0}
!LYRA_CURRENT_TABLE_parent = ${NAT_PARENT_ADDR:06X}
!LYRA_CURRENT_TABLE_area_size = ${NAT_SIZE_ADDR:06X}
!C4_Corner  = $012D
!C4_Horiz   = $012E
!C4_Vert    = $012F
!C4_ActiveL = $353F
!Menu_DivV  = $214F
!Menu_DivH  = $217A
MenuScrollLevelH = $1E71

org $2D8000
Menu_DrawBackground_Long:
  RTL
Menu_OracleTreasureOwned_Long:
  STZ.b $02
  RTL
{draw_loc_block}
; Character table for menu_map_names.asm (identical to Menu/menu_text.asm)
'A' = $2550
'B' = $2551
'C' = $2552
'D' = $2553
'E' = $2554
'F' = $2555
'G' = $2556
'H' = $2557
'I' = $2558
'J' = $2559
'K' = $255A
'L' = $255B
'M' = $255C
'N' = $255D
'O' = $255E
'P' = $255F
'Q' = $2560
'R' = $2561
'S' = $2562
'T' = $2563
'U' = $2564
'V' = $2565
'W' = $2566
'X' = $2567
'Y' = $2568
'Z' = $2569
'.' = $256A
':' = $256B
'0' = $2570
'1' = $2571
'2' = $2572
'3' = $2573
'4' = $2574
'5' = $2575
'6' = $2576
'7' = $2577
'8' = $2578
'9' = $2579
'_' = $20F5
incsrc "{menu_dir / 'menu_map_names.asm'}"

org $549000
incsrc "{menu_dir / 'menu_v5_ext.asm'}"
FixtureEnd:
"""
        asm_path.write_text(asm_src, encoding="utf-8")
        proc = subprocess.run(
            [asar, "--no-title-check", "--fix-checksum=off", "--symbols=wla",
             f"--symbols-path={sym_path}", str(asm_path), str(rom_path)],
            capture_output=True, text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"asar failed:\n{proc.stdout}\n{proc.stderr}")
        return rom_path.read_bytes(), parse_sym(sym_path)


class MiniMapCpu:
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.bad_writes: list[tuple[int, int]] = []
        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self._read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self._write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def reset_ram(self) -> None:
        self.ram[:] = bytes(len(self.ram))
        self.bad_writes.clear()
        # Fill $7E1000..$7E17FF with panel blank $3417 (matches Menu_DrawBackground)
        for off in range(0x1000, 0x1800, 2):
            self.ram[off] = PANEL_BLANK & 0xFF
            self.ram[off + 1] = PANEL_BLANK >> 8

    @staticmethod
    def _ram_offset(a: int) -> int | None:
        bank = a >> 16
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def _read(self, a: int) -> int:
        off = self._ram_offset(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = lorom_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, a: int, v: int) -> None:
        off = self._ram_offset(a)
        if off is None:
            self.bad_writes.append((a, v))
            return
        self.ram[off] = v & 0xFF

    def w8(self, addr: int, val: int) -> None:
        self._write(addr, val & 0xFF)

    def w16(self, addr: int, val: int) -> None:
        self._write(addr, val & 0xFF)
        self._write(addr + 1, (val >> 8) & 0xFF)

    def r16(self, addr: int) -> int:
        return self._read(addr) | (self._read(addr + 1) << 8)

    def call(self, name: str, *, long_call: bool = True, db: int = 0x2D, limit: int = 20000) -> None:
        addr = self.labels[name]
        c = self.cpu
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped",
                     "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(c, flag, False)
        c.mf = True
        c.xf = True
        c.dp = 0
        c.sp = 0x01FF
        c.a = 0
        c.x = 0
        c.y = 0
        c.db = db
        c.k = addr >> 16
        c.pc = addr & 0xFFFF
        sentinel_bank = 0x2D if not long_call else (addr >> 16)
        sp0 = c.sp
        if long_call:
            self._write(sp0, sentinel_bank)
            self._write(sp0 - 1, 0x6F)
            self._write(sp0 - 2, 0xFF)
            c.sp -= 3
        else:
            self._write(sp0, 0x6F)
            self._write(sp0 - 1, 0xFF)
            c.sp -= 2
        target = (sentinel_bank << 16) | 0x7000
        for _ in range(limit):
            if ((c.k << 16) | c.pc) == target:
                assert c.sp == sp0, f"{name}: stack imbalance sp=${c.sp:04X} != ${sp0:04X}"
                assert not self.bad_writes, f"{name}: illegal writes {self.bad_writes}"
                return
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name}: instruction ceiling reached at ${c.k:02X}:{c.pc:04X}")

    def decode_row(self, row: int, c0: int = 15, c1: int = 26) -> str:
        out = []
        for col in range(c0, c1 + 1):
            w = self.r16(0x7E1000 + row * 64 + col * 2)
            if 0x2550 <= w <= 0x2569:
                out.append(chr(ord("A") + (w - 0x2550)))
            elif w in (0x20F5, PANEL_BLANK):
                out.append(" ")
            else:
                out.append(f"[{w:04X}]")
        return "".join(out).strip()

    def decode_draw_location_name(self) -> str:
        out = []
        for i in range(16):
            w = self.r16(0x7E12CC + i * 2)
            if 0x2550 <= w <= 0x2569:
                out.append(chr(ord("A") + (w - 0x2550)))
            elif w == 0x20F5:
                out.append(" ")
            else:
                out.append(f"[{w:04X}]")
        return "".join(out).strip()

    def minimap_grid(self) -> list[int]:
        grid = []
        for idx in range(64):
            r, c = divmod(idx, 8)
            grid.append(self.r16(0x7E1000 + (11 + r) * 64 + (6 + c) * 2))
        return grid


class TestMiniMapAndSpecialNames(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.lib = get_lakesnes_lib()
        if cls.lib is None or find_asar() is None:
            raise unittest.SkipTest("LakeSnes or asar unavailable")
        cls.parent_tbl, cls.size_tbl = build_rev5_geometry()
        cls.rom_nat, cls.labels_nat = assemble_menu_fixture(True, cls.parent_tbl, cls.size_tbl)
        cls.rom_leg, cls.labels_leg = assemble_menu_fixture(False, cls.parent_tbl, cls.size_tbl)

    def test_all_64_special_ow_names_wrapped_and_draw_location_name(self) -> None:
        cpu = MiniMapCpu(self.lib, self.rom_nat, self.labels_nat)
        try:
            for area_id in range(0x80, 0xC0):
                expected = EXPECTED_SPECIAL_NAMES[area_id]
                exp_l1, exp_l2 = EXPECTED_SPECIAL_WRAPPED[expected]

                # 1. MenuMap_DrawAreaNameRight_Long (2-line wrapped right of Mini-Map)
                cpu.reset_ram()
                cpu.w8(0x7E001B, 0)
                cpu.w16(0x7E008A, area_id)
                cpu.call("MenuMap_DrawAreaNameRight_Long", long_call=True, db=0x2D)
                self.assertEqual(
                    (cpu.decode_row(11), cpu.decode_row(12)),
                    (exp_l1, exp_l2),
                    f"MenuMap_DrawAreaNameRight_Long mismatch for ${area_id:02X}",
                )
                # Guard: never clip into right border col 27
                self.assertEqual(cpu.r16(0x7E1000 + 11 * 64 + 27 * 2), PANEL_BLANK)
                self.assertEqual(cpu.r16(0x7E1000 + 12 * 64 + 27 * 2), PANEL_BLANK)

                # 2. DrawLocationName (Bank $2D trampoline -> Bank $54 Menu_DrawLocationName_Long)
                cpu.reset_ram()
                cpu.w8(0x7E001B, 0)
                cpu.w16(0x7E008A, area_id)
                cpu.w16(0x7E0000, 0xCAFE)
                cpu.w16(0x7E0002, 0xBEEF)
                cpu.call("DrawLocationName", long_call=False, db=0x2D)
                self.assertEqual(
                    cpu.decode_draw_location_name(),
                    expected,
                    f"DrawLocationName mismatch for ${area_id:02X}",
                )
                # Scratch $00-$03 preserved by Menu_DrawLocationName_Long
                self.assertEqual(cpu.r16(0x7E0000), 0xCAFE)
                self.assertEqual(cpu.r16(0x7E0002), 0xBEEF)
        finally:
            cpu.close()

    def test_lw_dw_indoors_and_invalid_area_zero_regression(self) -> None:
        cpu = MiniMapCpu(self.lib, self.rom_nat, self.labels_nat)
        try:
            cases = [
                # (indoors, area_8A, room_A0, exp_full, exp_l1, exp_l2)
                (0, 0x00, 0x0000, "RANCH", "RANCH", ""),
                (0, 0x23, 0x0000, "WAYWARD VILLAGE", "WAYWARD", "VILLAGE"),
                (0, 0x36, 0x0000, "GARO DESERT", "GARO DESERT", ""),
                (0, 0x40, 0x0000, "TEMPORAL GATE", "TEMPORAL", "GATE"),
                (0, 0x4B, 0x0000, "THE FORTRESS", "THE FORTRESS", ""),
                (0, 0x63, 0x0000, "WISDOM SWAMP", "WISDOM SWAMP", ""),
                (0, 0x76, 0x0000, "ABYSS BEACH", "ABYSS BEACH", ""),
                (1, 0x23, 0x0006, "ZORA TEMPLE", "ZORA TEMPLE", ""),
                (1, 0x4B, 0x000C, "FORTRESS SECRETS", "FORTRESS", "SECRETS"),
                (1, 0x23, 0x0104, "YOUR HOUSE", "YOUR HOUSE", ""),
            ]
            for ind, area, room, full, l1, l2 in cases:
                cpu.reset_ram()
                cpu.w8(0x7E001B, ind)
                cpu.w16(0x7E008A, area)
                cpu.w16(0x7E00A0, room)
                cpu.call("MenuMap_DrawAreaNameRight_Long", long_call=True, db=0x2D)
                self.assertEqual((cpu.decode_row(11), cpu.decode_row(12)), (l1, l2), f"Wrapped fail {cases}")

                cpu.reset_ram()
                cpu.w8(0x7E001B, ind)
                cpu.w16(0x7E008A, area)
                cpu.w16(0x7E00A0, room)
                cpu.call("DrawLocationName", long_call=False, db=0x2D)
                self.assertEqual(cpu.decode_draw_location_name(), full, f"DrawLocationName fail {full}")

            # Invalid $8A >= $C0 exits cleanly without touching tilemap
            cpu.reset_ram()
            cpu.w8(0x7E001B, 0)
            cpu.w16(0x7E008A, 0xC0)
            cpu.call("MenuMap_DrawAreaNameRight_Long", long_call=True, db=0x2D)
            self.assertEqual((cpu.decode_row(11), cpu.decode_row(12)), ("", ""))
        finally:
            cpu.close()

    def test_minimap_all_four_shapes_lw_dw_sw_and_subquadrants(self) -> None:
        cpu = MiniMapCpu(self.lib, self.rom_nat, self.labels_nat)
        try:
            # Verify Small (1x1), Wide (2x1), Tall (1x2), Large (2x2) across LW, DW, SW
            shape_cases = [
                # Small (1x1)
                ("LW $22 Small", 0x22, 0x22, {0x22: 0x256D}),
                ("DW $42 Small", 0x42, 0x02, {0x02: 0x256D}),
                ("SW $87 Small", 0x87, 0x07, {0x07: 0x256D}),
                ("SW $99 Small", 0x99, 0x19, {0x19: 0x256D}),
                # Wide (2x1) — both West and East sub-quadrants
                ("LW $30 Wide W", 0x30, 0x30, {0x30: 0x256D, 0x31: 0x657B}),
                ("LW $30 Wide E", 0x30, 0x31, {0x30: 0x257B, 0x31: 0x256D}),
                ("SW $A0 Wide W", 0xA0, 0x20, {0x20: 0x256D, 0x21: 0x657B}),
                ("SW $A0 Wide E", 0xA0, 0x21, {0x20: 0x257B, 0x21: 0x256D}),
                ("SW $A8 Wide W", 0xA8, 0x28, {0x28: 0x256D, 0x29: 0x657B}),
                ("SW $BE Wide E", 0xBE, 0x3F, {0x3E: 0x257B, 0x3F: 0x256D}),
                # Tall (1x2) — both North and South sub-quadrants
                ("SW $83 Tall N", 0x83, 0x03, {0x03: 0x256D, 0x0B: 0xA57B}),
                ("SW $83 Tall S", 0x83, 0x0B, {0x03: 0x257B, 0x0B: 0x256D}),
                ("SW $90 Tall S", 0x90, 0x18, {0x10: 0x257B, 0x18: 0x256D}),
                ("SW $B5 Tall N", 0xB5, 0x35, {0x35: 0x256D, 0x3D: 0xA57B}),
                ("SW $B5 Tall S", 0xB5, 0x3D, {0x35: 0x257B, 0x3D: 0x256D}),
                # Large (2x2) — all 4 sub-quadrants across LW, DW, SW
                ("LW $23 Large NW", 0x23, 0x23, {0x23: 0x256D, 0x24: 0x657B, 0x2B: 0xA57B, 0x2C: 0xE57B}),
                ("LW $23 Large NE", 0x23, 0x24, {0x23: 0x257B, 0x24: 0x256D, 0x2B: 0xA57B, 0x2C: 0xE57B}),
                ("LW $23 Large SW", 0x23, 0x2B, {0x23: 0x257B, 0x24: 0x657B, 0x2B: 0x256D, 0x2C: 0xE57B}),
                ("LW $23 Large SE", 0x23, 0x2C, {0x23: 0x257B, 0x24: 0x657B, 0x2B: 0xA57B, 0x2C: 0x256D}),
                ("DW $4B Large SE", 0x4B, 0x14, {0x0B: 0x257B, 0x0C: 0x657B, 0x13: 0xA57B, 0x14: 0x256D}),
                ("SW $81 Large NW", 0x81, 0x01, {0x01: 0x256D, 0x02: 0x657B, 0x09: 0xA57B, 0x0A: 0xE57B}),
                ("SW $A6 Large NE", 0xA6, 0x27, {0x26: 0x257B, 0x27: 0x256D, 0x2E: 0xA57B, 0x2F: 0xE57B}),
                ("SW $B0 Large SE", 0xB0, 0x39, {0x30: 0x257B, 0x31: 0x657B, 0x38: 0xA57B, 0x39: 0x256D}),
                ("SW $B3 Large SW", 0xB3, 0x3B, {0x33: 0x257B, 0x34: 0x657B, 0x3B: 0x256D, 0x3C: 0xE57B}),
            ]
            for label, area, subcell, expected_fp in shape_cases:
                for blink, add_gold in ((0x00, 0x0000), (0x10, 0x1000)):
                    cpu.reset_ram()
                    cpu.w8(0x7E001B, 0)
                    cpu.w8(0x7E008A, area)
                    cpu.w8(0x7E0700, (subcell & 0x3F) * 2)
                    cpu.w8(0x7E0207, blink)
                    cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x54)
                    grid = cpu.minimap_grid()
                    for idx, base_word in expected_fp.items():
                        self.assertEqual(
                            grid[idx],
                            base_word + add_gold,
                            f"{label} blink=${blink:02X} cell ${idx:02X}",
                        )
                    # Non-footprint cells must never have marker pin or H/V flips
                    for idx, w in enumerate(grid):
                        if idx not in expected_fp:
                            self.assertNotEqual(w & 0x03FF, 0x016D, f"{label}: stray pin at ${idx:02X}")
                            self.assertEqual(w & 0xC000, 0, f"{label}: unexpected flip at ${idx:02X}")
        finally:
            cpu.close()

    def test_minimap_stale_0700_child_8a_indoors_and_edge_guards(self) -> None:
        cpu = MiniMapCpu(self.lib, self.rom_nat, self.labels_nat)
        try:
            # 1. Stale $0700 (outside footprint) falls back cleanly to $8A & $3F
            cpu.reset_ram()
            cpu.w8(0x7E001B, 0)
            cpu.w8(0x7E008A, 0xA6)
            cpu.w8(0x7E0700, 0x00)  # stale cell 0 (not in Courage Island {$26,$27,$2E,$2F})
            cpu.w8(0x7E0207, 0x00)
            cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x2B)
            grid = cpu.minimap_grid()
            self.assertEqual(grid[0x26], 0x256D)
            self.assertEqual(grid[0x27], 0x657B)
            self.assertEqual(grid[0x2E], 0xA57B)
            self.assertEqual(grid[0x2F], 0xE57B)

            # 2. Child $8A (e.g. $A9 Deku Grove E) still resolves parent $A8 and draws full 2x1
            cpu.reset_ram()
            cpu.w8(0x7E001B, 0)
            cpu.w8(0x7E008A, 0xA9)
            cpu.w8(0x7E0700, 0x00)  # stale -> fallback uses $8A & $3F = $29!
            cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x2D)
            grid = cpu.minimap_grid()
            self.assertEqual(grid[0x28], 0x257B)
            self.assertEqual(grid[0x29], 0x256D)

            # 3. Indoors ($1B != 0) keeps single entrance pin + 63 muted gray $317B cells
            cpu.reset_ram()
            cpu.w8(0x7E001B, 1)
            cpu.w8(0x7E008A, 0x23)  # Large 2x2 parent, must NOT expand indoors
            cpu.w8(0x7E0700, 0x2C * 2)
            cpu.w8(0x7E0207, 0x00)
            cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x2D)
            grid = cpu.minimap_grid()
            self.assertEqual(grid[0x23], 0x256D)
            for idx in range(64):
                if idx != 0x23:
                    self.assertEqual(grid[idx], 0x317B, f"Indoor cell ${idx:02X} not muted gray")
        finally:
            cpu.close()

        # 4. Boundary-column/row guard test with synthetic edge-case sizes (col==7, row==7)
        edge_par = list(range(0xC0))
        edge_sz = [0] * 0xC0
        edge_sz[0x07] = 1  # Large at col 7 -> may only expand down to $0F, never wrap to $08!
        edge_sz[0x38] = 1  # Large at row 7 -> may only expand right to $39, never >= 64!
        edge_sz[0x3F] = 1  # Large at corner (7,7) -> clamped to single cell $3F!
        rom_edge, labels_edge = assemble_menu_fixture(True, edge_par, edge_sz)
        cpu_e = MiniMapCpu(self.lib, rom_edge, labels_edge)
        try:
            for area, expected_cells in (
                (0x07, {0x07: 0x256D, 0x0F: 0xA57B}),
                (0x38, {0x38: 0x256D, 0x39: 0x657B}),
                (0x3F, {0x3F: 0x256D}),
            ):
                cpu_e.reset_ram()
                cpu_e.w8(0x7E001B, 0)
                cpu_e.w8(0x7E008A, area)
                cpu_e.w8(0x7E0700, area * 2)
                cpu_e.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x54)
                grid = cpu_e.minimap_grid()
                for idx, w in expected_cells.items():
                    self.assertEqual(grid[idx], w, f"Edge guard ${area:02X} cell ${idx:02X}")
                for idx, w in enumerate(grid):
                    if idx not in expected_cells:
                        self.assertEqual(w & 0xC000, 0, f"Edge guard ${area:02X} leaked flip to ${idx:02X}")
        finally:
            cpu_e.close()

    def test_legacy_build_mode_lw_dw_sw_footprints(self) -> None:
        cpu = MiniMapCpu(self.lib, self.rom_leg, self.labels_leg)
        try:
            # LW $23 Large (2x2) works identically under !SPECIAL_OVERWORLD_NATIVE == 0
            cpu.reset_ram()
            cpu.w8(0x7E001B, 0)
            cpu.w8(0x7E008A, 0x23)
            cpu.w8(0x7E0700, 0x24 * 2)
            cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x2D)
            grid = cpu.minimap_grid()
            self.assertEqual(grid[0x23], 0x257B)
            self.assertEqual(grid[0x24], 0x256D)
            self.assertEqual(grid[0x2B], 0xA57B)
            self.assertEqual(grid[0x2C], 0xE57B)

            # Tail map $A6 safely degrades to 1x1 without out-of-bounds table reads
            cpu.reset_ram()
            cpu.w8(0x7E001B, 0)
            cpu.w8(0x7E008A, 0xA6)
            cpu.call("MenuMap_DrawMiniMap_Long", long_call=True, db=0x2D)
            grid = cpu.minimap_grid()
            self.assertEqual(grid[0x26], 0x256D)
            self.assertEqual(grid[0x27] & 0xC000, 0)
        finally:
            cpu.close()


if __name__ == "__main__":
    unittest.main()
