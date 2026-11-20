#!/usr/bin/env python3
"""Asar + LakeSnes tests for dungeon webs and the rideable lily pad.

Assembles the real Sprites/Objects/dungeon_web.asm and lily_pad.asm into an
isolated synthetic LoROM image and executes the compiled 65816 on LakeSnes's
CPU core. No writes to shared Roms/ or the live .yazeproj/rom.
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
WEB = ROOT / "Sprites" / "Objects" / "dungeon_web.asm"
LILY = ROOT / "Sprites" / "Objects" / "lily_pad.asm"

SPR_Y, SPR_X, SPR_YH, SPR_XH = 0x0D00, 0x0D10, 0x0D20, 0x0D30
SPR_YSPD, SPR_XSPD = 0x0D40, 0x0D50
SPR_ACTION, SPR_MISCA, SPR_MISCB = 0x0D80, 0x0DA0, 0x0DB0
SPR_STATE, SPR_MISCC = 0x0DD0, 0x0DE0
SPR_SUBTYPE, SPR_FLOOR = 0x0E30, 0x0F20
SPR_MISCD, SPR_MISCE, SPR_MISCF, SPR_MISCG = 0x0E90, 0x0EB0, 0x0EC0, 0x0ED0
SPR_TIMERA, SPR_PAUSE = 0x0DF0, 0x0F00
LINK_Y, LINK_X = 0x0020, 0x0022
GUST_STATE, GUST_CHARGE, GUST_TIER = 0x0273, 0x0275, 0x0276
GUST_DIR, GUST_WAVE_X, GUST_WAVE_Y, GUST_FLAGS = 0x0277, 0x027B, 0x027D, 0x027F
MASK = 0xCA00
CAM_X, CAM_Y = 0x00E2, 0x00E8
OAM, OAM_HI = 0x0800, 0x0A20


def find_lakesnes() -> Path | None:
    cands = [
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ]
    for cand in cands:
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def parse_sym(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in sym_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        match = re.match(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", line.strip())
        if match and ":" not in match.group(3):
            labels[match.group(3)] = (int(match.group(1), 16) << 16) | int(match.group(2), 16)
    return labels


def lorom_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


HARNESS_ASM = r"""
lorom
!DISABLE_ITEMS = 0
incsrc "Config/feature_flags.asm"
incsrc "Config/module_flags.asm"

incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"

Sprite_CheckActive = $30FE00
DekuStick_State = $7E046D
DekuStick_SwipeTimer = $7E046F

org $31F000
Deku_TorchProbeX:
  dw 8, 8, -4, 20
Deku_TorchProbeY:
  dw -4, 24, 8, 8
Deku_HitProbeOffX:
  dw 0, 0, -10, 16
Deku_HitProbeOffY:
  dw -10, 16, 4, 4
Deku_HitProbeWidth:
  db 16, 16, 12, 12
Deku_HitProbeHeight:
  db 12, 12, 16, 16

org $308000
incsrc "Core/sprite_new_table.asm"

org $318000
incsrc "Sprites/Objects/dungeon_web.asm"

org $328000
incsrc "Sprites/Objects/lily_pad.asm"
"""


def build_rom() -> tuple[bytes, dict[str, int], str]:
    asar = shutil.which("asar")
    if not asar:
        raise AssertionError("asar binary required")
    with tempfile.TemporaryDirectory(prefix="oos-webs-asm-") as tmp:
        td = Path(tmp)
        src = td / "main.asm"
        rom = td / "test.sfc"
        sym = td / "test.sym"
        src.write_text(HARNESS_ASM, encoding="utf-8")
        rom.write_bytes(b"\x00" * 0x200000)
        res = subprocess.run(
            [asar, "--no-title-check", "-I" + str(ROOT), "--symbols=wla",
             f"--symbols-path={sym}", str(src), str(rom)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            errors="replace",
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
    _TMP = tempfile.TemporaryDirectory(prefix="oos-webs-lakesnes-")
    so = Path(_TMP.name) / "libcpu.dylib"
    subprocess.run(
        ["cc", "-shared", "-fPIC", "-O2",
         str(src / "snes" / "cpu.c"),
         str(src / "snes" / "statehandler.c"),
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
        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self._install_stubs()

    def addr(self, name: str) -> int:
        if name not in self.labels:
            raise AssertionError(f"missing label {name}")
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
        if 0x2100 <= lo <= 0x21FF:
            return

    def get(self, addr: int) -> int:
        return self.read(addr)

    def put(self, addr: int, val: int) -> None:
        self.write(addr, val)

    def put16(self, addr: int, val: int) -> None:
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def get16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def spr(self, base: int, slot: int = 0) -> int:
        return self.get(base + slot)

    def set_spr(self, base: int, val: int, slot: int = 0) -> None:
        self.put(base + slot, val & 0xFF)

    def set_spr_pos(self, x: int, y: int, slot: int = 0) -> None:
        self.set_spr(SPR_X, x, slot)
        self.set_spr(SPR_XH, x >> 8, slot)
        self.set_spr(SPR_Y, y, slot)
        self.set_spr(SPR_YH, y >> 8, slot)

    def spr_pos(self, slot: int = 0) -> tuple[int, int]:
        return (
            self.spr(SPR_X, slot) | (self.spr(SPR_XH, slot) << 8),
            self.spr(SPR_Y, slot) | (self.spr(SPR_YH, slot) << 8),
        )

    def set_link(self, x: int, y: int) -> None:
        self.put16(LINK_X, x)
        self.put16(LINK_Y, y)

    def link_pos(self) -> tuple[int, int]:
        return self.get16(LINK_X), self.get16(LINK_Y)

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

        def coords(h: "Harness") -> None:
            slot = h.cpu.x & 0xFF
            h.put16(0x0FD8, h.spr(SPR_X, slot) | (h.spr(SPR_XH, slot) << 8))
            h.put16(0x0FDA, h.spr(SPR_Y, slot) | (h.spr(SPR_YH, slot) << 8))

        def tile(h: "Harness") -> None:
            x = h.get16(0x0002)
            y = h.get16(0x0000)
            kind = h.tiles.get((x // 8, y // 8), h.default_tile) & 0xFF
            # Real vanilla Sprite_GetTileAttr ($06E87B) clobbers DP $00-$07.
            for dp in range(8):
                h.put(dp, 0xCC)
            h.cpu.a = (h.cpu.a & 0xFF00) | kind
            h.cpu.mf = True
            h.cpu.xf = True
            h.put(0x0FA5, kind)

        def nop(h: "Harness") -> None:
            return None

        self.add_stub("Sprite_CheckActive", check_active)
        self.add_stub("Sprite_PrepOamCoord", prep_oam)
        self.add_stub("Sprite_OAM_AllocateDeferToPlayer", nop)
        self.add_stub("OAM_AllocateFromRegionB", nop)
        self.add_stub("Sprite_Get_16_bit_Coords", coords)
        self.add_stub("Sprite_PlayerCantPassThrough", nop)
        self.add_stub("Sprite_CheckDamageFromPlayer", nop)
        self.add_stub("Sprite_GetTileAttr", tile)

    def call(self, name: str, *, slot: int = 0, long: bool = False, limit: int = 20000) -> None:
        target = self.addr(name)
        self.calls.clear()
        cpu = self.cpu
        cpu.mf = True
        cpu.xf = True
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
                if not (cpu.mf and cpu.xf):
                    raise AssertionError(f"width leak after {name}: mf={cpu.mf} xf={cpu.xf}")
                return
            if pc in self.stubs:
                sname = self.stubs[pc]
                self.calls.append(sname)
                handler = self.handlers.get(sname)
                if handler:
                    handler(self)
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} hung at ${cpu.k:02X}:{cpu.pc:04X}")

    def reset_ram(self) -> None:
        self.ram[:] = b"\x00" * len(self.ram)
        self.sfx2.clear()
        self.tiles.clear()
        self.default_tile = 0x08

    def mask_word(self, index: int) -> int:
        # DungeonWeb_BurnedMask is $7ECA00, which the harness stores at RAM offset $CA00.
        off = MASK + index * 2
        return self.ram[off] | (self.ram[off + 1] << 8)


class CompiledWebLilyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        lib = lakesnes_lib()
        if lib is None:
            raise AssertionError("LakeSnes cpu.c was not found")
        cls.rom, cls.labels, cls.asm_log = build_rom()
        cls.lib = lib

    def harness(self) -> Harness:
        return Harness(self.lib, self.rom, self.labels)

    def test_web_bank_slot_and_lily_are_in_the_image(self):
        self.assertIn("End of Sprites/Objects/dungeon_web.asm", self.asm_log)
        self.assertIn("Lily pad bytes:", self.asm_log)
        web_end = self.labels["DungeonWeb_CodeEnd"]
        self.assertGreaterEqual(web_end, 0x36F200)
        self.assertLessEqual(web_end, 0x36F800)
        gust_start = self.labels["DungeonWeb_GustCodeStart"]
        self.assertGreaterEqual(gust_start, 0x318000)
        self.assertLess(gust_start, 0x320000)
        self.assertLess(self.labels["LilyPad_CodeEnd"], 0x330000)
        self.assertGreaterEqual(self.labels["LilyPad_Tile60"], self.labels["LilyPad_CodeStart"])
        # Six distinct 4bpp tiles, 32 bytes each, first pixel column is the rim.
        self.assertNotEqual(self.rom[lorom_pc(self.labels["LilyPad_Tile60"])], 0)

    def test_fire_rod_burns_and_sets_persistence_mask(self):
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x00)
        h.set_spr(SPR_MISCC, 0x00)
        h.set_spr(SPR_MISCA, 0x00)
        h.set_spr_pos(0x64, 0x64)
        h.put(0x001B, 1)
        h.put16(0x00A0, 0x46)
        h.put(0x0C4A, 0x02)
        h.put16(0x0C04, 0x68)
        h.put(0x0C18, 0x00)
        h.put16(0x0BFA, 0x68)
        h.put(0x0C0E, 0x00)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.spr(SPR_TIMERA), 0x14)
        self.assertEqual(h.spr(SPR_STATE), 0x09)
        self.assertEqual(h.mask_word(0x46) & 0x0001, 0x0001)
        self.assertIn(0x2A, h.sfx2)
        self.assertGreaterEqual(h.calls.count("Sprite_PlayerCantPassThrough"), 2)

    def test_lit_deku_stick_still_ignites(self):
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCC, 0x00)
        h.set_spr(SPR_MISCA, 0x01)
        h.set_spr_pos(0x64, 0x64)
        h.put(0x001B, 1)
        h.put16(0x00A0, 0x10)
        h.put(0x002F, 0x06)  # face right
        h.put16(LINK_X, 0x5A)
        h.put16(LINK_Y, 0x60)
        h.put(0x046D, 0x02)  # lit held stick
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_ACTION), 1)
        self.assertEqual(h.mask_word(0x10) & 0x0002, 0x0002)

    def test_gust_inhale_shakes_then_rips_and_tier1_blast_does_not(self):
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCC, 0x00)
        h.set_spr(SPR_MISCA, 0x00)
        h.set_spr_pos(100, 100)
        h.put(0x001B, 1)
        h.put16(0x00A0, 0x46)
        h.set_link(70, 96)
        h.put(GUST_STATE, 1)
        h.put(GUST_FLAGS, 0x01)
        h.put(GUST_DIR, 0x06)
        h.put(GUST_TIER, 1)
        h.put(GUST_CHARGE, 0x20)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_STATE), 0x09)
        self.assertEqual(h.spr(SPR_MISCB), 1)
        self.assertEqual(h.mask_word(0x46), 0)

        h.put(GUST_CHARGE, 0x60)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_STATE), 0x00)
        self.assertEqual(h.mask_word(0x46) & 0x0001, 0x0001)
        self.assertIn(0x15, h.sfx2)

        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCC, 0x00)
        h.set_spr(SPR_MISCA, 0x03)
        h.set_spr_pos(100, 100)
        h.put(0x001B, 1)
        h.put16(0x00A0, 0x46)
        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x01)
        h.put(GUST_TIER, 1)
        h.put16(GUST_WAVE_X, 116)
        h.put16(GUST_WAVE_Y, 108)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_STATE), 0x09)
        self.assertEqual(h.mask_word(0x46), 0)

    def test_tier2_blast_shreds_and_prep_honors_the_mask(self):
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x02)
        h.set_spr(SPR_MISCC, 0x02)
        h.set_spr(SPR_MISCA, 0x00)
        h.set_spr_pos(100, 100)
        h.put(0x001B, 0)
        h.put(0x008A, 0x90)
        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x01)
        h.put(GUST_TIER, 2)
        h.put16(GUST_WAVE_X, 116)
        h.put16(GUST_WAVE_Y, 108)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_STATE), 0x00)
        self.assertEqual(h.mask_word(0x90) & 0x0001, 0x0001)

        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_SUBTYPE, 0x02)
        h.put(0x0BC0, 0x00)
        h.call("Sprite_DungeonWeb_Prep", long=True)
        self.assertEqual(h.spr(SPR_STATE), 0x00)
        self.assertEqual(h.spr(SPR_MISCC), 0x02)

    def test_inhale_from_the_side_does_not_rip(self):
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr(SPR_MISCC, 0x00)
        h.set_spr_pos(100, 100)
        h.put(0x001B, 1)
        h.put16(0x00A0, 0x22)
        h.set_link(70, 96)
        h.put(GUST_STATE, 1)
        h.put(GUST_FLAGS, 0x01)
        h.put(GUST_DIR, 0x00)  # facing up, web is to the right
        h.put(GUST_CHARGE, 0x60)
        h.put(GUST_TIER, 3)
        h.call("Sprite_DungeonWeb_Main")
        self.assertEqual(h.spr(SPR_STATE), 0x09)
        self.assertEqual(h.mask_word(0x22), 0)

    def test_lily_boards_carries_and_dismounts(self):
        h = self.harness()
        h.reset_ram()
        h.default_tile = 0x08
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(128, 128)
        h.set_link(136, 120)
        h.put(0x005D, 0x04)
        h.put(0x0345, 0x01)
        h.put(0x005B, 0x02)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr(SPR_MISCA), 1)
        self.assertEqual(h.get(0x005D), 0)
        self.assertEqual(h.get(0x0345), 0)
        self.assertEqual(h.get(0x005B), 0)
        self.assertEqual(h.link_pos(), (136, 120))
        self.assertEqual(h.spr_pos(), (128, 128))

        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x01)
        h.put(GUST_TIER, 2)
        h.put(GUST_DIR, 0x06)  # face right, recoil left
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (124, 128))
        self.assertEqual(h.link_pos(), (132, 120))
        self.assertEqual(h.get(0x005D), 0)
        self.assertEqual(h.spr(SPR_XSPD), 0xFD)  # -4, then friction -> -3

        # Shore: step off the deck onto ground. Pad is not pushed this frame.
        h.put(GUST_STATE, 0)
        h.put(GUST_FLAGS, 0)
        h.set_spr(SPR_XSPD, 0)
        h.set_spr(SPR_YSPD, 0)
        h.set_link(176, 120)
        h.tiles[(184 // 8, 134 // 8)] = 0x00
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr(SPR_MISCA), 0)
        self.assertEqual(h.link_pos(), (176, 120))
        self.assertEqual(h.get(0x005D), 0)
        self.assertEqual(h.get(0x0345), 0)

    def test_lily_gust_recoil_four_directions_and_wall_stop(self):
        # Off-pad Gust Blast must not push an unoccupied lily pad away.
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(128, 128)
        h.set_link(40, 120)
        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x0D)
        h.put(GUST_TIER, 3)
        h.put(GUST_DIR, 0x04)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (128, 128))
        self.assertEqual(h.spr(SPR_XSPD), 0)

        # While aboard, Tier 2/3 inhale (state=1, flags bit0=1) charges without
        # premature recoil; releasing Tier 3 blast (state=2) fires 6 px/f recoil.
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(128, 128)
        h.set_link(136, 120)
        h.call("Sprite_LilyPad_Long", long=True)  # board
        h.put(GUST_STATE, 1)
        h.put(GUST_FLAGS, 0x05)
        h.put(GUST_TIER, 3)
        h.put(GUST_DIR, 0x04)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (128, 128))
        self.assertEqual(h.spr(SPR_MISCB), 0)
        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x0D)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (134, 128))
        self.assertEqual(h.link_pos(), (142, 120))
        self.assertEqual(h.spr(SPR_XSPD), 5)  # +6 then friction -> +5

        expected = {
            0x00: (0, 4),    # face up, recoil down
            0x02: (0, -4),   # face down, recoil up
            0x04: (4, 0),    # face left, recoil right
            0x06: (-4, 0),   # face right, recoil left
        }
        for direction, (dx, dy) in expected.items():
            h = self.harness()
            h.reset_ram()
            h.set_spr(SPR_STATE, 0x09)
            h.set_spr_pos(128, 128)
            h.set_link(136, 120)
            h.call("Sprite_LilyPad_Long", long=True)  # board
            h.put(GUST_STATE, 2)
            h.put(GUST_FLAGS, 0x0D)
            h.put(GUST_TIER, 2)
            h.put(GUST_DIR, direction)
            h.call("Sprite_LilyPad_Long", long=True)
            self.assertEqual(h.spr_pos(), ((128 + dx) & 0xFFFF, (128 + dy) & 0xFFFF), direction)
            self.assertEqual(h.link_pos(), ((136 + dx) & 0xFFFF, (120 + dy) & 0xFFFF), direction)

        # Diagonal glide must preserve X carry delta across Sprite_GetTileAttr's
        # $00-$07 clobber during LilyPad_MoveY.
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(128, 128)
        h.set_link(136, 120)
        h.call("Sprite_LilyPad_Long", long=True)  # board
        h.set_spr(SPR_XSPD, 4)
        h.set_spr(SPR_YSPD, 2)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (132, 130))
        self.assertEqual(h.link_pos(), (140, 122))

        # High-speed (6 px/f) lookahead stops BEFORE entering a cliff starting at x=160.
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(128, 128)
        h.set_link(136, 120)
        h.call("Sprite_LilyPad_Long", long=True)  # board and remember feet
        for ty in (132 // 8, 148 // 8):
            h.tiles[(160 // 8, ty)] = 0x01
        h.put(GUST_STATE, 2)
        h.put(GUST_FLAGS, 0x0D)
        h.put(GUST_TIER, 3)
        h.put(GUST_DIR, 0x04)  # recoil +6 toward x=160 cliff
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.spr_pos(), (128, 128))
        self.assertEqual(h.spr(SPR_XSPD), 0)
        self.assertEqual(h.link_pos(), (136, 120))

        # Feet in a wall: restore the saved on-pad coordinates.
        h.put(GUST_STATE, 0)
        h.set_link(96, 120)
        h.tiles[(104 // 8, 134 // 8)] = 0x01
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.link_pos(), (136, 120))
        self.assertEqual(h.spr(SPR_MISCA), 1)

    def test_lily_oam_clips_negative_x_and_sets_the_high_bit(self):
        # Fully off-screen left (X = -32): all 12 tiles hidden.
        h = self.harness()
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(16, 64)
        h.put16(CAM_X, 48)  # screen X = -32
        h.put16(CAM_Y, 0)
        for i in range(48):
            h.put(OAM + i, 0xA5)
        h.call("Sprite_LilyPad_Long", long=True)
        for i in range(12):
            self.assertEqual(h.get(OAM + i * 4), 0x00, i)
            self.assertEqual(h.get(OAM + i * 4 + 1), 0xF0, i)
            self.assertEqual(h.get(OAM_HI + i), 0x00, i)

        # Partially off-screen left (X = -4): col 0 uses SNES 9-bit X=$FC, HI=1.
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(44, 64)
        h.put16(CAM_X, 48)  # screen X = -4, +4, +12, +20
        h.put16(CAM_Y, 0)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.get(OAM + 0), 0xFC)
        self.assertEqual(h.get(OAM + 1), 64)
        self.assertEqual(h.get(OAM_HI + 0), 1)
        self.assertEqual(h.get(OAM + 4), 4)
        self.assertEqual(h.get(OAM + 5), 64)
        self.assertEqual(h.get(OAM_HI + 1), 0)

        # Right-edge straddle (X = 248): col 0 visible, cols 1..3 (256..272) hidden.
        h.reset_ram()
        h.set_spr(SPR_STATE, 0x09)
        h.set_spr_pos(248, 64)
        h.put16(CAM_X, 0)
        h.put16(CAM_Y, 0)
        h.call("Sprite_LilyPad_Long", long=True)
        self.assertEqual(h.get(OAM + 0), 248)
        self.assertEqual(h.get(OAM + 1), 64)
        self.assertEqual(h.get(OAM_HI + 0), 0)
        for col in (1, 2, 3):
            self.assertEqual(h.get(OAM + col * 4 + 1), 0xF0, col)
            self.assertEqual(h.get(OAM_HI + col), 0, col)

        # Far off-screen right (X = 508 and X = 520): must NEVER wrap onto X=-4 or X=0.
        for far_x in (508, 520):
            h.reset_ram()
            h.set_spr(SPR_STATE, 0x09)
            h.set_spr_pos(far_x, 64)
            h.put16(CAM_X, 0)
            h.put16(CAM_Y, 0)
            h.call("Sprite_LilyPad_Long", long=True)
            for i in range(12):
                self.assertEqual(h.get(OAM + i * 4 + 1), 0xF0, (far_x, i))
                self.assertEqual(h.get(OAM_HI + i), 0x00, (far_x, i))

    def test_source_contract_keeps_shared_files_out_of_this_track(self):
        web = WEB.read_text(encoding="utf-8")
        lily = LILY.read_text(encoding="utf-8")
        all_sprites = (ROOT / "Sprites" / "all_sprites.asm").read_text(encoding="utf-8")
        self.assertIn("!WebGustState  = $0273", web)
        self.assertIn("!WebGustFlags  = $027F", web)
        self.assertIn("DungeonWeb_RipAway", web)
        self.assertNotIn("org $37F800", web)
        self.assertNotIn("lily_pad.asm", all_sprites)
        self.assertIn("!SPRID              = $AD", lily)
        self.assertNotIn("org $", lily)
        self.assertIn("OAM_AllocateFromRegionB", lily)


if __name__ == "__main__":
    unittest.main()
