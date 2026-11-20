#!/usr/bin/env python3
"""Asar + LakeSnes compiled 65816 tests for Sprite_NightPoe ($B4).

Verifies:
  1. Day/night spawn gate on Kalyxo LW / Special OW (Subtype 0 despawns 06:00-17:59,
     spawns 18:00-05:59; Subtype 1, Indoors, and Eon Abyss always spawn).
  2. Zero-lag ghost pursuit (16-bit Link delta, symmetric +/-$14 clamp, Sprite_MoveLong,
     no tile-collision sweep) and hit-recoil ethereal phase-shift (SprAction=1, 28f).
  3. NightPoe_NmiUpload 4-cycle fast exit and exact 4 x 64B DMA uploads to
     $5EC0/$5FC0/$5EE0/$5FE0 with $4304=$7E and $4302=$0ADC restoration.
  4. Byte-exact fidelity of embedded 256B 4BPP tiles vs GameyFireBro source
     Data/graphics/sprites/gameyfirebro/eow_poe_lantern/sheet.4bpp remapped to OAM Pal 4.
  5. OAM draw gating (pending VRAM, death poof $0DD0==6, ethereal flicker),
     true SNES 9-bit 16x16 clipping ([-15..255]), lantern L/R flip, and flash-safe
     palette XOR preserving Page 1 nametable bit 0.
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
POE_ASM = ROOT / "Sprites" / "Enemies" / "night_poe.asm"
POE_SRC_4BPP = ROOT / "Data" / "graphics" / "sprites" / "gameyfirebro" / "eow_poe_lantern" / "sheet.4bpp"

SPR_Y, SPR_X, SPR_YH, SPR_XH = 0x0D00, 0x0D10, 0x0D20, 0x0D30
SPR_YSPD, SPR_XSPD = 0x0D40, 0x0D50
SPR_ACTION, SPR_MISCA, SPR_MISCB = 0x0D80, 0x0DA0, 0x0DB0
SPR_STATE, SPR_MISCC, SPR_TIMERA = 0x0DD0, 0x0DE0, 0x0DF0
SPR_SUBTYPE, SPR_MISCD = 0x0E30, 0x0E90
SPR_FLASH, SPR_RECOIL = 0x0B89, 0x0EA0
LINK_Y, LINK_X = 0x0020, 0x0022
CAM_X, CAM_Y = 0x00E2, 0x00E8
OAM, OAM_HI = 0x0800, 0x0A20

TIME_HOURS = 0x7EE000
POE_VRAM_STATE = 0x7F540A
POE_LAST_AREA = 0x7F540B
POE_LAST_IND = 0x7F540C


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
incsrc "Sprites/Enemies/night_poe.asm"
"""


def build_rom() -> tuple[bytes, dict[str, int], str]:
    asar = shutil.which("asar")
    if not asar:
        raise AssertionError("asar binary required")
    with tempfile.TemporaryDirectory(prefix="oos-poe-asm-") as tmp:
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
    _TMP = tempfile.TemporaryDirectory(prefix="oos-poe-lakesnes-")
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
        self.dma_transfers: list[tuple[int, int, int]] = []  # (vmaddr, src24, size)
        self.io: dict[int, int] = {}
        self.hit_next = False
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
            h.cpu.c = False
            h.put16(0x90, OAM)
            h.put16(0x92, OAM_HI)

        def dmg_from(h: "Harness") -> None:
            slot = h.cpu.x & 0xFF
            if h.hit_next:
                h.hit_next = False
                h.set_spr(SPR_RECOIL, 0x10, slot)
                h.cpu.c = True
            else:
                h.cpu.c = False

        def nop(h: "Harness") -> None:
            return None

        self.add_stub("Sprite_CheckActive", check_active)
        self.add_stub("Sprite_PrepOamCoord", prep_oam)
        self.add_stub("Sprite_OAM_AllocateDeferToPlayer", nop)
        self.add_stub("Sprite_MoveLong", nop)
        self.add_stub("Sprite_CheckDamageFromPlayer", dmg_from)
        self.add_stub("Sprite_CheckDamageToPlayer", nop)

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
        self.hit_next = False


class CompiledNightPoeTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lib = lakesnes_lib()
        if lib is None:
            raise AssertionError("LakeSnes cpu.c not found")
        cls.rom, cls.labels, cls.asm_log = build_rom()
        cls.lib = lib

    def harness(self) -> Harness:
        return Harness(self.lib, self.rom, self.labels)

    def test_day_night_spawn_gate_and_subtype_override(self):
        h = self.harness()
        # Daytime 12:00 on Kalyxo LW ($1B=0, $8A=$18), Subtype 0 -> despawns.
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x00)
        h.put(0x001B, 0x00)
        h.put(0x008A, 0x18)
        h.put(TIME_HOURS, 12)
        h.call("Sprite_NightPoe_Prep")
        self.assertEqual(h.spr(SPR_STATE), 0x00)
        self.assertEqual(h.get(POE_VRAM_STATE), 0x00)

        # Nighttime 20:00 and 02:00 on Kalyxo LW -> spawns and queues VRAM ($80).
        for hr in (20, 2, 18, 5):
            h.reset()
            h.set_spr(SPR_STATE, 0x09)
            h.put(0x008A, 0x18)
            h.put(TIME_HOURS, hr)
            h.call("Sprite_NightPoe_Prep")
            self.assertEqual(h.spr(SPR_STATE), 0x09, hr)
            self.assertEqual(h.get(POE_VRAM_STATE), 0x80, hr)

        # Daytime Subtype 1, Indoors ($1B=1), and Eon Abyss ($8A=$52) always spawn.
        for label, sub, ind, area in [
            ("subtype1", 1, 0, 0x18),
            ("indoors", 0, 1, 0x00),
            ("abyss", 0, 0, 0x52),
        ]:
            h.reset()
            h.set_spr(SPR_STATE, 0x09)
            h.set_spr(SPR_SUBTYPE, sub)
            h.put(0x001B, ind)
            h.put(0x008A, area)
            h.put(TIME_HOURS, 12)
            h.call("Sprite_NightPoe_Prep")
            self.assertEqual(h.spr(SPR_STATE), 0x09, label)
            self.assertEqual(h.get(POE_VRAM_STATE), 0x80, label)

    def test_pursuit_steering_symmetric_clamp_and_hit_phase_shift(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(200, 160)
        h.put(0x008A, 0x18)
        h.put(TIME_HOURS, 22)
        h.call("Sprite_NightPoe_Prep")
        h.put(POE_VRAM_STATE, 0x01)

        # Link to the right and below -> accelerate to +$14 (+20), face Right (1).
        h.set_link(300, 240)
        for _ in range(50):
            h.call("Sprite_NightPoe_Main", long=False)
        self.assertEqual(h.spr(SPR_MISCA), 1)
        self.assertEqual(h.spr(SPR_XSPD), 0x14)
        self.assertEqual(h.spr(SPR_YSPD), 0x14)
        self.assertIn("Sprite_MoveLong", h.calls)
        self.assertIn("Sprite_CheckDamageToPlayer", h.calls)

        # Link to the left and above -> clamp symmetrically at -$14 ($EC), face Left (0).
        h.set_link(50, 40)
        for _ in range(90):
            h.call("Sprite_NightPoe_Main", long=False)
        self.assertEqual(h.spr(SPR_MISCA), 0)
        self.assertEqual(h.spr(SPR_XSPD), 0xEC)
        self.assertEqual(h.spr(SPR_YSPD), 0xEC)

        # Hit recoil -> enters ethereal phase-shift (SprAction=1, SprTimerA=$1C),
        # reverses X speed, and skips contact damage while phased.
        h.hit_next = True
        h.call("Sprite_NightPoe_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_TIMERA), 0x1C)
        self.assertEqual(h.spr(SPR_XSPD), 0x14)

        h.set_spr(SPR_TIMERA, 0x05)
        h.call("Sprite_NightPoe_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertNotIn("Sprite_CheckDamageToPlayer", h.calls)
        self.assertNotIn("Sprite_CheckDamageFromPlayer", h.calls)

        # Timer expires -> materializes solid again.
        h.set_spr(SPR_TIMERA, 0x00)
        h.call("Sprite_NightPoe_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 0)

    def test_nmi_upload_fast_exits_and_streams_four_dma_rows(self):
        h = self.harness()
        h.reset()
        h.put(0x0010, 0x09)
        h.put16(0x0ADC, 0xBEEF)

        # Idle ($00) and already live ($01): zero DMA transfers.
        for state in (0x00, 0x01):
            h.dma_transfers.clear()
            h.put(POE_VRAM_STATE, state)
            h.call("NightPoe_NmiUpload", xf16=True)
            self.assertEqual(h.dma_transfers, [], state)

        # Pending ($80) in gameplay module $09: uploads 4 x 64B rows and restores DMA regs.
        h.dma_transfers.clear()
        h.put(POE_VRAM_STATE, 0x80)
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.get(POE_VRAM_STATE), 0x01)
        self.assertEqual([t[0] for t in h.dma_transfers], [0x5EC0, 0x5FC0, 0x5EE0, 0x5FE0])
        self.assertEqual([t[2] for t in h.dma_transfers], [0x40, 0x40, 0x40, 0x40])
        self.assertEqual(h.dma_transfers[0][1], self.labels["NightPoe_BodyTop"])
        self.assertEqual(h.dma_transfers[1][1], self.labels["NightPoe_BodyBot"])
        self.assertEqual(h.dma_transfers[2][1], self.labels["NightPoe_LanternTop"])
        self.assertEqual(h.dma_transfers[3][1], self.labels["NightPoe_LanternBot"])
        self.assertEqual(h.io.get(0x4304), 0x7E)
        self.assertEqual(h.io.get(0x4302) | (h.io.get(0x4303) << 8), 0xBEEF)

    def test_draw_vram_gate_death_poof_flash_and_9bit_oam_clipping(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(120, 100)
        h.put(0x008A, 0x18)

        # Pending VRAM ($80): must not draw garbled tiles.
        h.put(POE_VRAM_STATE, 0x80)
        h.put(OAM, 0xA5)
        h.call("Sprite_NightPoe_Long")
        self.assertEqual(h.get(OAM), 0xA5)

        # Death poof ($0DD0 == $06): must not draw over death poof.
        h.put(POE_VRAM_STATE, 0x01)
        h.set_spr(SPR_STATE, 0x06)
        h.put(OAM, 0xA5)
        h.call("Sprite_NightPoe_Long")
        self.assertEqual(h.get(OAM), 0xA5)

        # Solid draw facing Left (0): body at X=120 ($EC), lantern at X=111 ($EE), prop=$29 (Pal 4, Page 1).
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCA, 0)
        h.set_spr(SPR_FLASH, 0)
        h.set_spr(SPR_MISCC, 0)
        h.put(POE_LAST_AREA, 0x18)
        h.call("Sprite_NightPoe_Draw", long=False)
        self.assertEqual(h.get(OAM + 0), 120)
        self.assertEqual(h.get(OAM + 1), 100)
        self.assertEqual(h.get(OAM + 2), 0xEC)
        self.assertEqual(h.get(OAM + 3), 0x29)
        self.assertEqual(h.get(OAM_HI + 0), 0x02)
        self.assertEqual(h.get(OAM + 4), 111)
        self.assertEqual(h.get(OAM + 5), 104)
        self.assertEqual(h.get(OAM + 6), 0xEE)
        self.assertEqual(h.get(OAM + 7), 0x29)
        self.assertEqual(h.get(OAM_HI + 1), 0x02)

        # Facing Right (1) with SprFlash=3: H-flip ($61) + ((3<<1)^8)&$0E = $0E -> prop=$6F (Page 1 bit 0 intact!).
        h.set_spr(SPR_MISCA, 1)
        h.set_spr(SPR_FLASH, 3)
        h.call("Sprite_NightPoe_Draw", long=False)
        self.assertEqual(h.get(OAM + 3), 0x6F)
        self.assertEqual(h.get(OAM + 4), 129)  # 120 + 9
        self.assertEqual(h.get(OAM + 3) & 0x01, 0x01)

        # Left-edge 16x16 clip (X = -8): X=$F8, HI=$03 (16x16 + X-MSB=1); lantern at -17 hidden!
        h.set_spr(SPR_MISCA, 0)
        h.set_spr(SPR_FLASH, 0)
        h.set_spr_pos(40, 100)
        h.put16(CAM_X, 48)  # body X = -8, lantern X = -17
        h.call("Sprite_NightPoe_Draw", long=False)
        self.assertEqual(h.get(OAM + 0), 0xF8)
        self.assertEqual(h.get(OAM + 1), 100)
        self.assertEqual(h.get(OAM_HI + 0), 0x03)
        self.assertEqual(h.get(OAM + 5), 0xF0)  # lantern at -17 hidden
        self.assertEqual(h.get(OAM_HI + 1), 0x00)

        # Off-screen right (X = 508): both hidden (Y=$F0, HI=0), never wraps onto left edge.
        h.set_spr_pos(508, 100)
        h.put16(CAM_X, 0)
        h.call("Sprite_NightPoe_Draw", long=False)
        self.assertEqual(h.get(OAM + 1), 0xF0)
        self.assertEqual(h.get(OAM_HI + 0), 0x00)
        self.assertEqual(h.get(OAM + 5), 0xF0)
        self.assertEqual(h.get(OAM_HI + 1), 0x00)

    def test_embedded_tiles_match_gameyfirebro_eow_poe_lantern_remap(self):
        src = POE_SRC_4BPP.read_bytes()
        remap = {0: 0, 1: 5, 2: 7, 3: 7, 4: 6, 5: 1, 6: 4, 7: 2, 8: 4, 9: 1}
        expected = bytearray()
        for tid in (0x08, 0x09, 0x18, 0x19, 0x0A, 0x0B, 0x1A, 0x1B):
            off = tid * 32
            rows = [[0] * 8 for _ in range(8)]
            for y in range(8):
                b0, b1 = src[off + y * 2], src[off + y * 2 + 1]
                b2, b3 = src[off + 16 + y * 2], src[off + 16 + y * 2 + 1]
                for x in range(8):
                    bit = 7 - x
                    v = ((b0 >> bit) & 1) | (((b1 >> bit) & 1) << 1) | (((b2 >> bit) & 1) << 2) | (((b3 >> bit) & 1) << 3)
                    rows[y][x] = remap[v]
            for y in range(8):
                b0 = b1 = 0
                for x in range(8):
                    v = rows[y][x]
                    bit = 7 - x
                    if v & 1:
                        b0 |= 1 << bit
                    if v & 2:
                        b1 |= 1 << bit
                expected.extend((b0, b1))
            for y in range(8):
                b2 = b3 = 0
                for x in range(8):
                    v = rows[y][x]
                    bit = 7 - x
                    if v & 4:
                        b2 |= 1 << bit
                    if v & 8:
                        b3 |= 1 << bit
                expected.extend((b2, b3))
        pc = lorom_pc(self.labels["NightPoe_GfxStart"])
        got = self.rom[pc:pc + 256]
        self.assertEqual(got, bytes(expected))

    def test_wiring_and_registry_contracts(self):
        all_sprites = (ROOT / "Sprites" / "all_sprites.asm").read_text(encoding="utf-8")
        reg_csv = (ROOT / "Sprites" / "registry.csv").read_text(encoding="utf-8")
        reg_ids = (ROOT / "Sprites" / "sprite_registry_ids.asm").read_text(encoding="utf-8")
        bombchu = (ROOT / "Items" / "bombchu.asm").read_text(encoding="utf-8")
        self.assertIn('incsrc "Sprites/Enemies/night_poe.asm"', all_sprites)
        self.assertIn("Sprite_NightPoe,$B4,Sprites/Enemies/night_poe.asm", reg_csv)
        self.assertIn("Sprite_NightPoe = $B4", reg_ids)
        self.assertIn("JSL NightPoe_NmiUpload", bombchu)


if __name__ == "__main__":
    unittest.main()
