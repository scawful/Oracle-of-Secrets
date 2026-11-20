#!/usr/bin/env python3
"""Asar + LakeSnes compiled 65816 tests for Endgame Pig Moblin ($9C, GameyFireBro art)."""
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
sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))
from build_gameyfirebro_sprites import encode_tile8, tile8  # noqa: E402

SRC_4BPP = ROOT / "Data" / "graphics" / "sprites" / "gameyfirebro" / "pig_moblins" / "sheet.4bpp"

SPR_Y, SPR_X, SPR_YH, SPR_XH = 0x0D00, 0x0D10, 0x0D20, 0x0D30
SPR_YSPD, SPR_XSPD = 0x0D40, 0x0D50
SPR_ACTION, SPR_MISCA, SPR_MISCB = 0x0D80, 0x0DA0, 0x0DB0
SPR_STATE, SPR_MISCC, SPR_TIMERA = 0x0DD0, 0x0DE0, 0x0DF0
SPR_SUBTYPE, SPR_HEALTH, SPR_COLLISION = 0x0E30, 0x0E50, 0x0E70
SPR_MISCD, SPR_RECOIL = 0x0E90, 0x0EA0
SPR_BUMP, SPR_FLASH = 0x0CD2, 0x0B89
LINK_Y, LINK_X = 0x0020, 0x0022
CAM_X, CAM_Y = 0x00E2, 0x00E8
OAM, OAM_HI = 0x0800, 0x0A20

POE_VRAM_STATE = 0x7F540A
LYRA_VRAM_STATE = 0x7F540D
MOB_VRAM_STATE = 0x7F57FC
MOB_LAST_AREA = 0x7F57FD
MOB_LAST_IND = 0x7F57FE


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
incsrc "Sprites/Enemies/pig_moblin.asm"
incsrc "Sprites/Enemies/lyra_sea_enemies.asm"
incsrc "Sprites/Enemies/night_poe.asm"
"""


def build_rom() -> tuple[bytes, dict[str, int], str]:
    asar = shutil.which("asar")
    if not asar:
        raise AssertionError("asar binary required")
    with tempfile.TemporaryDirectory(prefix="oos-moblin-asm-") as tmp:
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
    _TMP = tempfile.TemporaryDirectory(prefix="oos-moblin-lakesnes-")
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
        self.dma_transfers: list[tuple[int, int, int]] = []
        self.io: dict[int, int] = {}
        self.shadow_dp: tuple[int, int] | None = None
        self.next_collision = 0
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
                src = (
                    self.io.get(0x4302, 0)
                    | (self.io.get(0x4303, 0) << 8)
                    | (self.io.get(0x4304, 0) << 16)
                )
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
            h.put(0x05, 0x28)
            h.put16(0x90, OAM)
            h.put16(0x92, OAM_HI)

        def draw_shadow(h: "Harness") -> None:
            h.shadow_dp = (h.get16(0x00), h.get(0x05))

        def tile_col(h: "Harness") -> None:
            slot = h.cpu.x & 0xFF
            h.set_spr(SPR_COLLISION, h.next_collision, slot)

        def nop(h: "Harness") -> None:
            return None

        self.add_stub("Sprite_CheckActive", check_active)
        self.add_stub("Sprite_PrepOamCoord", prep_oam)
        self.add_stub("Sprite_OAM_AllocateDeferToPlayer", nop)
        self.add_stub("Sprite_DrawShadow", draw_shadow)
        self.add_stub("Sprite_MoveLong", nop)
        self.add_stub("Sprite_CheckTileCollision", tile_col)
        self.add_stub("Sprite_CheckDamageFromPlayer", nop)
        self.add_stub("Sprite_CheckDamageToPlayer", nop)
        self.add_stub("Sprite_GetTileAttr", nop)

    def call(self, name: str, *, slot: int = 0, long: bool = True, xf16: bool = False, limit: int = 25000) -> None:
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
            sentinel = (0x00, 0x7000)
        else:
            cpu.db = (target >> 16) & 0xFF
            self.ram[sp] = 0x6F
            self.ram[sp - 1] = 0xFF
            cpu.sp = sp - 2
            sentinel = ((target >> 16) & 0xFF, 0x7000)
        cpu.k = (target >> 16) & 0xFF
        cpu.pc = target & 0xFFFF
        for _ in range(limit):
            if (cpu.k, cpu.pc) == sentinel:
                return
            full = (cpu.k << 16) | cpu.pc
            if full in self.stubs:
                sname = self.stubs[full]
                self.calls.append(sname)
                self.handlers[sname](self)
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} did not return within {limit} steps (pc=${cpu.k:02X}:{cpu.pc:04X})")

    def reset(self) -> None:
        self.ram[:] = bytes(len(self.ram))
        self.io.clear()
        self.dma_transfers.clear()
        self.sfx2.clear()
        self.calls.clear()
        self.shadow_dp = None
        self.next_collision = 0


class CompiledPigMoblinTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rom, cls.labels, cls.log = build_rom()
        cls.lib = lakesnes_lib()

    def harness(self) -> Harness:
        if self.lib is None:
            self.skipTest("lakesnes cpu.c unavailable")
        return Harness(self.lib, self.rom, self.labels)

    def test_prep_green_and_blue_elite_stats_and_vram_queue(self):
        h = self.harness()
        h.reset()
        h.put(0x001B, 0x01)
        h.put(0x00A0, 0x2D)
        h.put(0x00A1, 0x00)
        h.set_spr(SPR_SUBTYPE, 0)
        h.set_spr(SPR_HEALTH, 12)
        h.set_spr(SPR_BUMP, 4)
        h.set_spr_pos(120, 100)
        h.set_link(180, 104)
        h.call("Sprite_PigMoblin_Prep")
        self.assertEqual(h.spr(SPR_MISCD), 0)
        self.assertEqual(h.spr(SPR_HEALTH), 12)
        self.assertEqual(h.spr(SPR_BUMP), 4)
        self.assertEqual(h.spr(SPR_MISCA), 3)
        self.assertEqual(h.get(MOB_VRAM_STATE), 0x80)
        self.assertEqual(h.get(MOB_LAST_AREA), 0x2D)
        self.assertEqual(h.get(MOB_LAST_IND), 0x80)

        h.set_spr(SPR_SUBTYPE, 1)
        h.set_link(120, 40)
        h.call("Sprite_PigMoblin_Prep")
        self.assertEqual(h.spr(SPR_MISCD), 1)
        self.assertEqual(h.spr(SPR_HEALTH), 0x14)
        self.assertEqual(h.spr(SPR_BUMP), 0x08)
        self.assertEqual(h.spr(SPR_MISCA), 0)

    def test_patrol_wall_reversal_los_aggro_and_ambush_turn(self):
        h = self.harness()
        h.reset()
        h.put(MOB_VRAM_STATE, 0x01)
        h.put(MOB_LAST_AREA, 0x00)
        h.put(MOB_LAST_IND, 0x00)
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_ACTION, 0)
        h.set_spr(SPR_MISCD, 0)
        h.set_spr(SPR_MISCA, 3)
        h.set_spr(SPR_TIMERA, 0x20)
        h.set_spr_pos(120, 120)
        h.set_link(400, 400)

        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 0)
        self.assertEqual(h.spr(SPR_XSPD), 0x0E)
        self.assertEqual(h.spr(SPR_YSPD), 0x00)

        h.next_collision = 0x01
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_MISCA), 2)
        h.next_collision = 0

        h.set_link(220, 120)
        h.set_spr(SPR_RECOIL, 8)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_MISCA), 3)
        self.assertEqual(h.spr(SPR_ACTION), 1)

        h.set_spr(SPR_RECOIL, 0)
        h.set_spr(SPR_ACTION, 0)
        h.set_spr(SPR_MISCC, 7)
        h.set_link(120, 180)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_MISCA), 1)

    def test_chase_telegraph_sword_lunge_and_recovery_combat(self):
        h = self.harness()
        h.reset()
        h.put(MOB_VRAM_STATE, 0x01)
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCD, 1)
        h.set_spr(SPR_ACTION, 1)
        h.set_spr(SPR_MISCA, 3)
        h.set_spr(SPR_TIMERA, 0x20)
        h.set_spr_pos(120, 120)

        h.set_link(184, 120)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_XSPD), 0x18)

        h.set_link(152, 124)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 2)
        self.assertEqual(h.spr(SPR_XSPD), 0)
        self.assertEqual(h.spr(SPR_TIMERA), 0x09)

        h.set_spr(SPR_TIMERA, 0)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 3)
        self.assertEqual(h.spr(SPR_MISCB), 3)
        self.assertIn(0x03, h.sfx2)

        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 3)
        self.assertEqual(h.spr(SPR_XSPD), 0x28)

        h.next_collision = 0x01
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 4)
        self.assertEqual(h.spr(SPR_MISCB), 0)
        self.assertEqual(h.spr(SPR_XSPD), 0)
        h.next_collision = 0

        h.set_spr(SPR_TIMERA, 4)
        h.call("Sprite_PigMoblin_Main", long=False)
        self.assertEqual(h.spr(SPR_ACTION), 4)
        self.assertIn("Sprite_CheckDamageFromPlayer", h.calls)
        self.assertIn("Sprite_CheckDamageToPlayer", h.calls)

    def test_staged_5frame_nmi_upload_and_3way_budget_sharing(self):
        h = self.harness()
        h.reset()
        h.put(0x0010, 0x07)
        h.put16(0x0ADC, 0xBEEF)

        h.put(POE_VRAM_STATE, 0x80)
        h.put(LYRA_VRAM_STATE, 0x80)
        h.put(MOB_VRAM_STATE, 0x80)

        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.get(POE_VRAM_STATE), 0x01)
        self.assertEqual(h.get(LYRA_VRAM_STATE), 0x80)
        self.assertEqual(h.get(MOB_VRAM_STATE), 0x80)
        self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)

        for exp_state in (0x81, 0x01):
            h.dma_transfers.clear()
            h.call("NightPoe_NmiUpload", xf16=True)
            self.assertEqual(h.get(LYRA_VRAM_STATE), exp_state)
            self.assertEqual(h.get(MOB_VRAM_STATE), 0x80)
            self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)

        expected_stages = [
            (0x81, [0x5C00, 0x5D00, 0x5C20, 0x5D20]),
            (0x82, [0x5C40, 0x5D40, 0x5C60, 0x5D60]),
            (0x83, [0x5CC0, 0x5DC0, 0x5CE0, 0x5DE0]),
            (0x84, [0x5E00, 0x5F00, 0x5E20, 0x5F20]),
            (0x01, [0x5E40, 0x5F40, 0x5E60, 0x5F60]),
        ]
        all_mob_vram = set()
        for exp_st, exp_addrs in expected_stages:
            h.dma_transfers.clear()
            h.call("NightPoe_NmiUpload", xf16=True)
            self.assertEqual(h.get(MOB_VRAM_STATE), exp_st)
            self.assertEqual([t[0] for t in h.dma_transfers], exp_addrs)
            self.assertEqual(sum(t[2] for t in h.dma_transfers), 256)
            self.assertEqual(h.io.get(0x4304), 0x7E)
            self.assertEqual(h.io.get(0x4302) | (h.io.get(0x4303) << 8), 0xBEEF)
            all_mob_vram.update(exp_addrs)

        reserved_others = {0x5C80, 0x5D80, 0x5CA0, 0x5DA0, 0x5E80, 0x5F80, 0x5EA0, 0x5FA0, 0x5EC0, 0x5FC0, 0x5EE0, 0x5FE0}
        self.assertTrue(all_mob_vram.isdisjoint(reserved_others))

        h.dma_transfers.clear()
        h.call("NightPoe_NmiUpload", xf16=True)
        self.assertEqual(h.dma_transfers, [])

    def test_draw_all_4_facings_palettes_lunge_shadow_dp_and_9bit_oam_clipping(self):
        h = self.harness()
        h.reset()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(120, 100)

        for st in (0x80, 0x81, 0x82, 0x83, 0x84):
            h.put(MOB_VRAM_STATE, st)
            h.put(OAM, 0xA5)
            h.call("Sprite_PigMoblin_Long")
            self.assertEqual(h.get(OAM), 0xA5, hex(st))

        h.put(MOB_VRAM_STATE, 0x01)
        h.set_spr(SPR_STATE, 0x06)
        h.put(OAM, 0xA5)
        h.call("Sprite_PigMoblin_Long")
        self.assertEqual(h.get(OAM), 0xA5)

        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCD, 0)
        h.set_spr(SPR_MISCA, 3)
        h.set_spr(SPR_ACTION, 3)
        h.set_spr(SPR_MISCB, 3)
        h.call("Sprite_PigMoblin_Draw", long=False)
        self.assertEqual((h.get(OAM + 0), h.get(OAM + 1), h.get(OAM + 2), h.get(OAM + 3), h.get(OAM_HI + 0)), (134, 107, 0xE6, 0x29, 0x00))
        self.assertEqual((h.get(OAM + 4), h.get(OAM + 5), h.get(OAM + 6), h.get(OAM + 7), h.get(OAM_HI + 1)), (142, 107, 0xE7, 0x29, 0x00))
        self.assertEqual((h.get(OAM + 8), h.get(OAM + 9), h.get(OAM + 10), h.get(OAM + 11), h.get(OAM_HI + 2)), (120, 95, 0xE0, 0x29, 0x02))
        self.assertEqual((h.get(OAM + 12), h.get(OAM + 13), h.get(OAM + 14), h.get(OAM + 15), h.get(OAM_HI + 3)), (120, 101, 0xE4, 0x29, 0x02))
        self.assertIn("Sprite_DrawShadow", h.calls)
        self.assertEqual(h.shadow_dp, (120, 0x28))

        h.set_spr(SPR_MISCD, 1)
        h.set_spr(SPR_MISCA, 2)
        h.set_spr(SPR_ACTION, 0)
        h.set_spr(SPR_MISCB, 0)
        h.set_spr(SPR_MISCC, 0)
        h.call("Sprite_PigMoblin_Draw", long=False)
        self.assertEqual((h.get(OAM + 0), h.get(OAM + 2), h.get(OAM + 3)), (117, 0xE6, 0x65))
        self.assertEqual((h.get(OAM + 4), h.get(OAM + 6), h.get(OAM + 7)), (109, 0xE7, 0x65))
        self.assertEqual((h.get(OAM + 8), h.get(OAM + 10), h.get(OAM + 11)), (120, 0xE0, 0x65))
        self.assertEqual((h.get(OAM + 12), h.get(OAM + 14), h.get(OAM + 15)), (120, 0xE2, 0x65))

        h.set_spr(SPR_MISCA, 0)
        h.call("Sprite_PigMoblin_Draw", long=False)
        self.assertEqual(h.get(OAM + 2), 0xC0)
        self.assertEqual(h.get(OAM + 6), 0xC2)
        self.assertEqual((h.get(OAM + 10), h.get(OAM + 11)), (0xF7, 0xA5))
        self.assertEqual((h.get(OAM + 14), h.get(OAM + 15)), (0xF6, 0xA5))

        h.set_spr(SPR_MISCA, 1)
        h.call("Sprite_PigMoblin_Draw", long=False)
        self.assertEqual([h.get(OAM + i * 4 + 2) for i in range(4)], [0xF6, 0xF7, 0xC4, 0xC6])

        h.set_spr(SPR_MISCA, 2)
        h.set_spr_pos(44, 100)
        h.put16(CAM_X, 48)
        h.call("Sprite_PigMoblin_Draw", long=False)
        self.assertEqual((h.get(OAM + 0), h.get(OAM_HI + 0)), (0xF9, 0x01))
        self.assertEqual((h.get(OAM + 5), h.get(OAM_HI + 1)), (0xF0, 0x00))
        self.assertEqual((h.get(OAM + 8), h.get(OAM_HI + 2)), (0xFC, 0x03))

        h.set_spr_pos(508, 100)
        h.put16(CAM_X, 0)
        h.call("Sprite_PigMoblin_Draw", long=False)
        for i in range(4):
            self.assertEqual((h.get(OAM + i * 4 + 1), h.get(OAM_HI + i)), (0xF0, 0x00))

    def test_embedded_1280b_tiles_match_gameyfirebro_pig_moblins_remap(self):
        sheet = SRC_4BPP.read_bytes()
        frame_specs = {
            0: [(0x00, 0, 0), (0x02, 16, 0), (0x04, 0, 16), (0x06, 16, 16)],
            1: [(0x08, 0, 0), (0x0A, 16, 0), (0x0C, 0, 16), (0x0E, 16, 16)],
            2: [(0x20, 0, 0), (0x22, 16, 0), (0x24, 0, 16), (0x26, 16, 16)],
            3: [(0x28, 0, 0), (0x2A, 16, 0), (0x2C, 0, 16), (0x2E, 16, 16)],
            4: [(0x40, 0, 0), (0x42, 0, 16), (0x44, 16, 16)],
            5: [(0x46, 0, 0), (0x48, 16, 0), (0x4A, 0, 16), (0x4C, 16, 16)],
        }
        remap = {0: 0, 1: 11, 2: 13, 6: 15, 7: 12, 8: 15, 9: 10, 10: 10, 11: 15, 12: 14, 13: 14, 14: 14, 15: 9}

        def render(fid):
            g = [[0] * 32 for _ in range(32)]
            for tid, ox, oy in frame_specs[fid]:
                for dx, dy, delta in ((0, 0, 0), (8, 0, 1), (0, 8, 16), (8, 8, 17)):
                    t = tile8(sheet, tid + delta)
                    for y in range(8):
                        for x in range(8):
                            if t[y][x]:
                                g[oy + dy + y][ox + dx + x] = t[y][x]
            return g

        def crop(g, x0, y0, w, h, mask=None):
            out = [[0] * w for _ in range(h)]
            for y in range(h):
                for x in range(w):
                    sx, sy = x0 + x, y0 + y
                    if 0 <= sx < 32 and 0 <= sy < 32:
                        v = g[sy][sx]
                        if v and (mask is None or mask(sx, sy, v)):
                            out[y][x] = remap[v]
            return out

        f = {i: render(i) for i in range(6)}
        blocks = [
            crop(f[0], 7, 9, 16, 16, lambda x, y, v: y <= 18 and x <= 22),
            crop(f[0], 6, 15, 16, 16, lambda x, y, v: 16 <= y <= 29 and not (x >= 22 and y <= 17)),
            crop(f[2], 8, 4, 16, 16, lambda x, y, v: y <= 15),
            crop(f[2], 9, 14, 16, 16, lambda x, y, v: 14 <= y <= 26 and not (x <= 11 and y >= 17)),
            crop(f[1], 6, 15, 16, 16, lambda x, y, v: 16 <= y <= 29 and not (x >= 22 and y <= 17)),
            crop(f[3], 9, 11, 16, 16, lambda x, y, v: 11 <= y <= 23 and not (x <= 11 and y >= 14)),
            crop(f[4], 2, 10, 16, 16, lambda x, y, v: y <= 21),
            crop(f[4], 2, 16, 16, 16, lambda x, y, v: 18 <= y <= 30 and not (x >= 16 and y >= 24)),
            crop(f[5], 3, 15, 16, 16, lambda x, y, v: 17 <= y <= 29 and not (x >= 17 and y >= 23)),
        ]
        expected = bytearray()
        for px in blocks:
            expected.extend(encode_tile8([r[0:8] for r in px[0:8]]))
            expected.extend(encode_tile8([r[8:16] for r in px[0:8]]))
            expected.extend(encode_tile8([r[0:8] for r in px[8:16]]))
            expected.extend(encode_tile8([r[8:16] for r in px[8:16]]))
        expected.extend(encode_tile8(crop(f[4], 14, 22, 8, 8, lambda x, y, v: 24 <= y <= 28)))
        expected.extend(encode_tile8(crop(f[4], 22, 22, 8, 8, lambda x, y, v: 24 <= y <= 28)))
        expected.extend(encode_tile8(crop(f[2], 6, 16, 8, 8, lambda x, y, v: x <= 11)))
        expected.extend(encode_tile8(crop(f[2], 6, 24, 8, 8, lambda x, y, v: x <= 11)))

        pc = lorom_pc(self.labels["PigMoblin_GfxStart"])
        self.assertEqual(len(expected), 1280)
        self.assertEqual(self.rom[pc:pc + 1280], bytes(expected))

    def test_wiring_and_registry_contracts(self):
        all_sprites = (ROOT / "Sprites" / "all_sprites.asm").read_text(encoding="utf-8")
        reg_csv = (ROOT / "Sprites" / "registry.csv").read_text(encoding="utf-8")
        reg_ids = (ROOT / "Sprites" / "sprite_registry_ids.asm").read_text(encoding="utf-8")
        i_mob = all_sprites.index('incsrc "Sprites/Enemies/pig_moblin.asm"')
        i_lyra = all_sprites.index('incsrc "Sprites/Enemies/lyra_sea_enemies.asm"')
        i_poe = all_sprites.index('incsrc "Sprites/Enemies/night_poe.asm"')
        self.assertLess(i_mob, i_lyra)
        self.assertLess(i_lyra, i_poe)
        self.assertIn("Sprite_PigMoblin,$9C,Sprites/Enemies/pig_moblin.asm", reg_csv)
        self.assertIn("Sprite_BlueMoblin,$9C,Sprites/Enemies/pig_moblin.asm", reg_csv)
        self.assertIn("Sprite_PigMoblin = $9C", reg_ids)
        self.assertIn("Sprite_BlueMoblin = $9C", reg_ids)


if __name__ == "__main__":
    unittest.main()
