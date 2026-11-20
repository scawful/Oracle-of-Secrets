#!/usr/bin/env python3
"""Asar + LakeSnes compiled 65816 tests for Lyra Sea Cheep-Cheep & Blooper ($AB).

Verifies:
  1. Subtype 0 Cheep-Cheep: submerged water swim, dry-shore reversal, parabolic
     SprHeight leap arc + splash SFX ($28), shadow drawn only while airborne,
     fast wing-flap CHR ($E8/$EA), OAM Pal 1 ($23/$63), and flash-safe palette XOR.
  2. Subtype 1 Blooper: float/sink telegraph (CHR $CA, OAM Pal 2 $25), diagonal
     jet dash (CHR $C8, upward pulse by default / downward when Link >= 24px below),
     and dry-shore stop so Bloopers never enter land.
  3. 2-frame staged NMI VRAM streamer (LyraSea_NmiUpload tail-called from
     NightPoe_NmiUpload in Bank $32): peak DMA <= 256B/frame even when both
     NightPoe and LyraSea are pending simultaneously.
  4. True SNES 9-bit 16x16 OAM X clipping ([-15..255]) + death poof & VRAM gating.
  5. Byte-exact 512B fidelity against GameyFireBro cheep_blooper/sheet.4bpp.
"""
from __future__ import annotations

import ctypes as C
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
SRC_4BPP = ROOT / "Data" / "graphics" / "sprites" / "gameyfirebro" / "cheep_blooper" / "sheet.4bpp"

SPR_Y, SPR_X, SPR_YH, SPR_XH = 0x0D00, 0x0D10, 0x0D20, 0x0D30
SPR_YSPD, SPR_XSPD = 0x0D40, 0x0D50
SPR_ACTION, SPR_MISCA, SPR_MISCB = 0x0D80, 0x0DA0, 0x0DB0
SPR_STATE, SPR_MISCC, SPR_TIMERA = 0x0DD0, 0x0DE0, 0x0DF0
SPR_SUBTYPE, SPR_MISCD, SPR_FLOOR = 0x0E30, 0x0E90, 0x0F20
SPR_HEIGHT, SPR_FLASH = 0x0F70, 0x0B89
LINK_Y, LINK_X = 0x0020, 0x0022
CAM_X, CAM_Y = 0x00E2, 0x00E8
OAM, OAM_HI = 0x0800, 0x0A20

POE_VRAM_STATE = 0x7F540A
LYRA_VRAM_STATE = 0x7F540D


def find_lakesnes() -> Path | None:
    for cand in (
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ):
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def parse_sym(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in sym_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", line.strip())
        if m and ":" not in m.group(3):
            labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


def lorom_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


HARNESS_ASM = r"""
lorom
!DISABLE_ITEMS = 0
incsrc "Config/feature_flags.asm"
incsrc "Config/module_flags.asm"

incsrc "Core/structs.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"

Sprite_CheckActive = $30FE00

org $308000
incsrc "Core/sprite_new_table.asm"

org $328000
incsrc "Sprites/Enemies/lyra_sea_enemies.asm"
incsrc "Sprites/Enemies/night_poe.asm"
"""


def build_rom() -> tuple[bytes, dict[str, int], str]:
    asar = shutil.which("asar")
    if not asar:
        raise AssertionError("asar binary required")
    with tempfile.TemporaryDirectory(prefix="oos-lyra-asm-") as tmp:
        td = Path(tmp)
        src, rom, sym = td / "main.asm", td / "test.sfc", td / "test.sym"
        src.write_text(HARNESS_ASM, encoding="utf-8")
        rom.write_bytes(b"\x00" * 0x200000)
        res = subprocess.run(
            [asar, "--no-title-check", "-I" + str(ROOT), "--symbols=wla",
             f"--symbols-path={sym}", str(src), str(rom)],
            cwd=str(ROOT), capture_output=True, text=True, errors="replace",
        )
        if res.returncode != 0:
            raise AssertionError(f"asar failed:\n{res.stdout}\n{res.stderr}")
        return rom.read_bytes(), parse_sym(sym), res.stdout + res.stderr


_LIB = None
_TMP = None


def lakesnes_lib():
    global _LIB, _TMP
    if _LIB is not None:
        return _LIB
    src = find_lakesnes()
    if src is None:
        return None
    _TMP = tempfile.TemporaryDirectory(prefix="oos-lyra-lakesnes-")
    so = Path(_TMP.name) / "libcpu.dylib"
    subprocess.run(
        ["cc", "-shared", "-fPIC", "-O2",
         str(src / "snes" / "cpu.c"), str(src / "snes" / "statehandler.c"),
         "-o", str(so)],
        check=True,
    )
    lib = C.CDLL(str(so))
    lib.cpu_init.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_runOpcode.restype = C.c_int
    _LIB = lib
    return lib


class Harness:
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.stubs: dict[int, str] = {}
        self.handlers: dict[str, object] = {}
        self.calls: list[str] = []
        self.sfx2: list[int] = []
        self.tiles: dict[tuple[int, int], int] = {}
        self.default_tile = 0x08
        self.dma_transfers: list[tuple[int, int, int]] = []
        self.io: dict[int, int] = {}
        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self._install_stubs()

    def addr(self, name: str) -> int:
        return self.labels[name]

    @staticmethod
    def ram_offset(addr: int) -> int | None:
        bank = (addr >> 16) & 0xFF
        lo = addr & 0xFFFF
        if bank in (0x7E, 0x7F):
            return addr - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def read(self, addr: int) -> int:
        if addr in self.stubs:
            return 0x6B
        off = self.ram_offset(addr)
        if off is not None:
            return self.ram[off]
        lo = addr & 0xFFFF
        if lo in self.io:
            return self.io[lo]
        if addr & 0x8000:
            pc = lorom_pc(addr)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def write(self, addr: int, val: int) -> None:
        val &= 0xFF
        off = self.ram_offset(addr)
        if off is not None:
            self.ram[off] = val
            if off == 0x012E:
                self.sfx2.append(val)
            return
        lo = addr & 0xFFFF
        if 0x2100 <= lo <= 0x43FF:
            self.io[lo] = val
            if lo == 0x420B and (val & 0x01):
                vm = self.io.get(0x2116, 0) | (self.io.get(0x2117, 0) << 8)
                src = (self.io.get(0x4302, 0)
                       | (self.io.get(0x4303, 0) << 8)
                       | (self.io.get(0x4304, 0) << 16))
                sz = self.io.get(0x4305, 0) | (self.io.get(0x4306, 0) << 8)
                self.dma_transfers.append((vm, src, sz))

    def get(self, addr: int) -> int:
        return self.read(addr)

    def put(self, addr: int, val: int) -> None:
        self.write(addr, val)

    def get16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def put16(self, addr: int, val: int) -> None:
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def set_spr(self, base: int, val: int, slot: int = 0) -> None:
        self.put(base + slot, val & 0xFF)

    def spr(self, base: int, slot: int = 0) -> int:
        return self.get(base + slot)

    def set_spr_pos(self, x: int, y: int, slot: int = 0) -> None:
        self.set_spr(SPR_X, x, slot)
        self.set_spr(SPR_XH, x >> 8, slot)
        self.set_spr(SPR_Y, y, slot)
        self.set_spr(SPR_YH, y >> 8, slot)

    def set_link(self, x: int, y: int) -> None:
        self.put16(LINK_X, x)
        self.put16(LINK_Y, y)

    def add_stub(self, name: str, handler) -> None:
        self.stubs[self.addr(name)] = name
        self.handlers[name] = handler

    def _install_stubs(self) -> None:
        def check_active(h: "Harness") -> None:
            h.cpu.c = h.spr(SPR_STATE, h.cpu.x & 0xFF) == 0x09

        def prep_oam(h: "Harness") -> None:
            slot = h.cpu.x & 0xFF
            sx = ((h.spr(SPR_X, slot) | (h.spr(SPR_XH, slot) << 8)) - h.get16(CAM_X)) & 0xFFFF
            h.cpu.c = False
            h.put16(0x00, sx)
            h.put(0x05, 0x22)
            h.put16(0x90, OAM)
            h.put16(0x92, OAM_HI)

        def tile(h: "Harness") -> None:
            x = h.get16(0x0002)
            y = h.get16(0x0000)
            kind = h.tiles.get((x // 8, y // 8), h.default_tile) & 0xFF
            for dp in range(8):
                h.put(dp, 0xCC)
            h.cpu.a = (h.cpu.a & 0xFF00) | kind
            h.cpu.mf = True
            h.cpu.xf = True

        def draw_shadow(h: "Harness") -> None:
            h.shadow_dp = (h.get16(0x00), h.get(0x05))

        def nop(h: "Harness") -> None:
            return None

        self.shadow_dp = None
        self.add_stub("Sprite_CheckActive", check_active)
        self.add_stub("Sprite_PrepOamCoord", prep_oam)
        self.add_stub("Sprite_OAM_AllocateDeferToPlayer", nop)
        self.add_stub("Sprite_DrawShadow", draw_shadow)
        self.add_stub("Sprite_MoveLong", nop)
        self.add_stub("Sprite_CheckDamageFromPlayer", nop)
        self.add_stub("Sprite_CheckDamageToPlayer", nop)
        self.add_stub("Sprite_GetTileAttr", tile)

    def call(self, name: str, *, slot: int = 0, long: bool = True, xf16: bool = False, limit: int = 20000) -> None:
        target = self.addr(name)
        self.calls.clear()
        cpu = self.cpu
        cpu.mf = True
        cpu.xf = not xf16
        cpu.dp = 0
        cpu.x = slot & 0xFF
        cpu.y = 0
        cpu.a = 0
        cpu.db = 0
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped"):
            setattr(cpu, flag, False)
        sp = 0x01FF
        if long:
            cpu.k = 0
            self.ram[sp] = 0x00
            self.ram[sp - 1] = 0x6F
            self.ram[sp - 2] = 0xFF
            cpu.sp = sp - 3
            sentinel = 0x007000
        else:
            cpu.k = (target >> 16) & 0xFF
            self.ram[sp] = 0x6F
            self.ram[sp - 1] = 0xFF
            cpu.sp = sp - 2
            sentinel = (cpu.k << 16) | 0x7000
        cpu.k = (target >> 16) & 0xFF
        cpu.pc = target & 0xFFFF
        for _ in range(limit):
            pc = (cpu.k << 16) | cpu.pc
            if pc == sentinel:
                if not cpu.mf or cpu.xf != (not xf16):
                    raise AssertionError(f"width leak after {name}: mf={cpu.mf} xf={cpu.xf}")
                return
            if pc in self.stubs:
                sname = self.stubs[pc]
                self.calls.append(sname)
                self.handlers[sname](self)
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} hung at ${cpu.k:02X}:{cpu.pc:04X}")

    def reset(self) -> None:
        self.ram[:] = b"\x00" * len(self.ram)
        self.io.clear()
        self.dma_transfers.clear()
        self.sfx2.clear()
        self.tiles.clear()
        self.default_tile = 0x08


class CompiledLyraSeaEnemiesTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lib = lakesnes_lib()
        if lib is None:
            raise AssertionError("LakeSnes cpu.c not found")
        cls.rom, cls.labels, cls.asm_log = build_rom()
        cls.lib = lib

    def harness(self) -> Harness:
        return Harness(self.lib, self.rom, self.labels)

    def test_cheep_cheep_swims_reverses_on_shore_and_leaps_parabolically(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x00)
        h.set_spr_pos(128, 128)
        h.put(0x008A, 0xA3)
        h.call("Sprite_LyraSea_Prep")
        self.assertEqual(h.spr(SPR_MISCD), 0)
        self.assertEqual(h.spr(SPR_TIMERA), 0x30)
        self.assertEqual(h.get(LYRA_VRAM_STATE), 0x80)
        h.put(LYRA_VRAM_STATE, 0x01)

        # Submerged swim toward Link on the right -> +$10 X speed.
        h.set_link(200, 128)
        h.set_spr(SPR_MISCC, 0xFF)  # next INC -> 0x00 triggers aim
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_XSPD), 0x10)
        self.assertEqual(h.spr(SPR_MISCA), 1)
        self.assertEqual(h.spr(SPR_HEIGHT), 0)

        # Dry shore tile ahead (x=144 -> tile 18) reverses submerged Cheep-Cheep.
        h.tiles[(144 // 8, 136 // 8)] = 0x00  # walkable land, not water
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_XSPD), 0xF0)  # reversed to -$10
        self.assertEqual(h.spr(SPR_MISCA), 0)

        # TimerA reaches 0 -> launches parabolic leap with splash SFX ($28)!
        h.tiles.clear()
        h.set_spr(SPR_TIMERA, 0x00)
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_MISCB), 4)
        self.assertEqual(h.spr(SPR_HEIGHT), 1)
        self.assertIn(0x28, h.sfx2)
        self.assertEqual(h.spr(SPR_XSPD), 0x16)  # leaping right toward Link

        # Step airborne frames: height peaks > 10 then lands back at 0 with splash!
        peak_h = 0
        landed = False
        for _ in range(80):
            h.call("Sprite_LyraSea_Main", long=False)
            peak_h = max(peak_h, h.spr(SPR_HEIGHT))
            if h.spr(SPR_ACTION) == 0:
                landed = True
                break
        self.assertGreater(peak_h, 12)
        self.assertTrue(landed)
        self.assertEqual(h.spr(SPR_HEIGHT), 0)
        self.assertEqual(h.sfx2.count(0x28), 2)

    def test_blooper_floats_jets_diagonally_and_stops_at_shore(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x01)
        h.set_spr_pos(128, 128)
        h.put(0x008A, 0xAC)
        h.call("Sprite_LyraSea_Prep")
        self.assertEqual(h.spr(SPR_MISCD), 1)
        self.assertEqual(h.spr(SPR_TIMERA), 0x18)
        h.put(LYRA_VRAM_STATE, 0x01)

        # Action 0 float: drifts downward (+$06) while waiting.
        h.set_link(90, 120)
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 0)
        self.assertEqual(h.spr(SPR_YSPD), 0x06)

        # TimerA reaches 0 with Link left/level -> upward-left jet (-$18, -$14).
        h.set_spr(SPR_TIMERA, 0x00)
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_XSPD), 0xE8)
        self.assertEqual(h.spr(SPR_YSPD), 0xEC)

        # Shore ahead stops Blooper cleanly at water edge.
        h.tiles[(128 // 8, 128 // 8)] = 0x01
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_XSPD), 0)
        self.assertEqual(h.spr(SPR_YSPD), 0)

        # Link far below (>= 24 px) -> downward-right jet (+$18, +$12).
        h.tiles.clear()
        h.set_spr(SPR_ACTION, 0)
        h.set_spr(SPR_TIMERA, 0)
        h.set_link(200, 180)
        h.call("Sprite_LyraSea_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_XSPD), 0x18)
        self.assertEqual(h.spr(SPR_YSPD), 0x12)

    def test_staged_2frame_nmi_upload_and_night_poe_budget_sharing(self):
        h = self.harness()
        h.reset()
        h.put(0x0010, 0x0B)
        h.put16(0x0ADC, 0xCAFE)

        # Both NightPoe ($80) and LyraSea ($80) pending at once:
        # Frame 1: NightPoe uploads 256B -> $01; LyraSea waits (peak <= 256B/frame!).
        h.put(POE_VRAM_STATE, 0x80)
        h.put(LYRA_VRAM_STATE, 0x80)
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.get(POE_VRAM_STATE), 0x01)
        self.assertEqual(h.get(LYRA_VRAM_STATE), 0x80)
        self.assertEqual(len(h.dma_transfers), 4)
        self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)

        # Frame 2: NightPoe fast-exits -> LyraSea Stage 1 uploads Cheep-Cheep 256B ($80->$81).
        h.dma_transfers.clear()
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.get(LYRA_VRAM_STATE), 0x81)
        self.assertEqual([t[0] for t in h.dma_transfers], [0x5E80, 0x5F80, 0x5EA0, 0x5FA0])
        self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)

        # Frame 3: LyraSea Stage 2 uploads Blooper 256B ($81->$01) & restores DMA regs.
        h.dma_transfers.clear()
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.get(LYRA_VRAM_STATE), 0x01)
        self.assertEqual([t[0] for t in h.dma_transfers], [0x5C80, 0x5D80, 0x5CA0, 0x5DA0])
        self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)
        self.assertEqual(h.io.get(0x4304), 0x7E)
        self.assertEqual(h.io.get(0x4302) | (h.io.get(0x4303) << 8), 0xCAFE)

        # Frame 4: Both live ($01) -> 0 DMA transfers!
        h.dma_transfers.clear()
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.dma_transfers, [])

    def test_draw_palettes_airborne_shadow_death_poof_and_oam_clipping(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(120, 100)

        # Pending VRAM ($80 or $81) must not draw garbled tiles.
        for st in (0x80, 0x81):
            h.put(LYRA_VRAM_STATE, st)
            h.put(OAM, 0xA5)
            h.call("Sprite_LyraSea_Long")
            self.assertEqual(h.get(OAM), 0xA5, st)

        # Death poof ($0DD0 == $06): skip draw.
        h.put(LYRA_VRAM_STATE, 0x01)
        h.set_spr(SPR_STATE, 0x06)
        h.put(OAM, 0xA5)
        h.call("Sprite_LyraSea_Long")
        self.assertEqual(h.get(OAM), 0xA5)

        # Cheep-Cheep airborne (SprHeight=16) facing Right: Y=84, CHR=$E8, prop=$63 (Pal 1 + H-flip + Page 1), draws shadow!
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCD, 0)
        h.set_spr(SPR_MISCA, 1)
        h.set_spr(SPR_HEIGHT, 16)
        h.set_spr(SPR_ACTION, 1)
        h.set_spr(SPR_MISCC, 0)
        h.call("Sprite_LyraSea_Draw", long=False)
        self.assertEqual(h.get(OAM + 0), 120)
        self.assertEqual(h.get(OAM + 1), 84)
        self.assertEqual(h.get(OAM + 2), 0xE8)
        self.assertEqual(h.get(OAM + 3), 0x63)
        self.assertEqual(h.get(OAM_HI + 0), 0x02)
        self.assertIn("Sprite_DrawShadow", h.calls)
        self.assertEqual(h.shadow_dp, (120, 0x22))

        # Blooper jetting (Action=1) with SprFlash=2: CHR=$C8, prop=$21 | ((2<<1)^4)&$0E = $21, no shadow.
        h.set_spr(SPR_MISCD, 1)
        h.set_spr(SPR_HEIGHT, 0)
        h.set_spr(SPR_ACTION, 1)
        h.set_spr(SPR_FLASH, 2)
        h.call("Sprite_LyraSea_Draw", long=False)
        self.assertEqual(h.get(OAM + 2), 0xC8)
        self.assertEqual(h.get(OAM + 3), 0x21)
        self.assertNotIn("Sprite_DrawShadow", h.calls)

        # Left-edge clip (X = -8) uses HI=$03; off-screen right (X = 508) hides cleanly.
        h.set_spr(SPR_FLASH, 0)
        h.set_spr_pos(40, 100)
        h.put16(CAM_X, 48)
        h.call("Sprite_LyraSea_Draw", long=False)
        self.assertEqual(h.get(OAM + 0), 0xF8)
        self.assertEqual(h.get(OAM_HI + 0), 0x03)

        h.set_spr_pos(508, 100)
        h.put16(CAM_X, 0)
        h.call("Sprite_LyraSea_Draw", long=False)
        self.assertEqual(h.get(OAM + 1), 0xF0)
        self.assertEqual(h.get(OAM_HI + 0), 0x00)

    def test_embedded_512b_tiles_match_gameyfirebro_cheep_blooper_remap(self):
        src = SRC_4BPP.read_bytes()
        cheep_map = {0: 0, 1: 5, 3: 2, 4: 2, 5: 7, 7: 6, 8: 7, 9: 6, 10: 1}
        blooper_map = {0: 0, 1: 5, 2: 3, 6: 4, 10: 1}
        order = [
            (0x00, cheep_map), (0x01, cheep_map), (0x10, cheep_map), (0x11, cheep_map),
            (0x02, cheep_map), (0x03, cheep_map), (0x12, cheep_map), (0x13, cheep_map),
            (0x04, blooper_map), (0x05, blooper_map), (0x14, blooper_map), (0x15, blooper_map),
            (0x06, blooper_map), (0x07, blooper_map), (0x16, blooper_map), (0x17, blooper_map),
        ]
        expected = bytearray()
        for tid, rmap in order:
            off = tid * 32
            rows = [[0] * 8 for _ in range(8)]
            for y in range(8):
                b0, b1 = src[off + y * 2], src[off + y * 2 + 1]
                b2, b3 = src[off + 16 + y * 2], src[off + 16 + y * 2 + 1]
                for x in range(8):
                    bit = 7 - x
                    v = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1) | (((b2 >> bit) & 1) << 2) | (((b3 >> bit) & 1) << 3)
                    rows[y][x] = rmap[v]
            for y in range(8):
                b0 = b1 = 0
                for x in range(8):
                    v = rows[y][x]; bit = 7 - x
                    if v & 1: b0 |= 1 << bit
                    if v & 2: b1 |= 1 << bit
                expected.extend((b0, b1))
            for y in range(8):
                b2 = b3 = 0
                for x in range(8):
                    v = rows[y][x]; bit = 7 - x
                    if v & 4: b2 |= 1 << bit
                    if v & 8: b3 |= 1 << bit
                expected.extend((b2, b3))
        pc = lorom_pc(self.labels["LyraSea_GfxStart"])
        self.assertEqual(self.rom[pc:pc + 512], bytes(expected))

    def test_wiring_and_registry_contracts(self):
        all_sprites = (ROOT / "Sprites" / "all_sprites.asm").read_text(encoding="utf-8")
        reg_csv = (ROOT / "Sprites" / "registry.csv").read_text(encoding="utf-8")
        reg_ids = (ROOT / "Sprites" / "sprite_registry_ids.asm").read_text(encoding="utf-8")
        self.assertIn('incsrc "Sprites/Enemies/lyra_sea_enemies.asm"', all_sprites)
        self.assertIn('incsrc "Sprites/Enemies/night_poe.asm"', all_sprites)
        self.assertLess(
            all_sprites.index('incsrc "Sprites/Enemies/lyra_sea_enemies.asm"'),
            all_sprites.index('incsrc "Sprites/Enemies/night_poe.asm"'),
            "lyra_sea_enemies.asm must precede night_poe.asm for !LYRA_SEA_NMI_UPLOAD tail-call",
        )
        self.assertIn("Sprite_CheepCheep,$AB,Sprites/Enemies/lyra_sea_enemies.asm", reg_csv)
        self.assertIn("Sprite_Blooper,$AB,Sprites/Enemies/lyra_sea_enemies.asm", reg_csv)
        self.assertIn("Sprite_CheepCheep = $AB", reg_ids)
        self.assertIn("Sprite_Blooper = $AB", reg_ids)


if __name__ == "__main__":
    unittest.main()
