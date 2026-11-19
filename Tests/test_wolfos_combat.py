#!/usr/bin/env python3
"""Compiled 65816 (LakeSnes) + art contract tests for Wolfos & Ice Wolfos overhaul.

Assembles the real `Sprites/Bosses/wolfos.asm` (including embedded GameyFireBro
`Data/graphics/sprites/ice_wolfos.4bpp`) with asar into an isolated synthetic
LoROM image and runs the compiled 65816 routines on LakeSnes's C CPU core.
Zero writes to shared Roms/ or .yazeproj/rom.
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

# Sprite RAM base addresses (8-bit X indexed)
SPR_Y          = 0x0D00
SPR_X          = 0x0D10
SPR_YH         = 0x0D20
SPR_XH         = 0x0D30
SPR_YSPD       = 0x0D40
SPR_XSPD       = 0x0D50
SPR_ACTION     = 0x0D80
SPR_FRAME      = 0x0D90
SPR_MISCA      = 0x0DA0
SPR_MISCB      = 0x0DB0
SPR_GFX        = 0x0DC0
SPR_STATE      = 0x0DD0
SPR_MISCC      = 0x0DE0
SPR_TIMERA     = 0x0DF0
SPR_TIMERB     = 0x0E00
SPR_TIMERC     = 0x0E10
SPR_TYPE       = 0x0E20
SPR_SUBTYPE    = 0x0E30
SPR_NBROAM     = 0x0E40
SPR_HEALTH     = 0x0E50
SPR_E60        = 0x0E60
SPR_MISCD      = 0x0E90
SPR_MISCE      = 0x0EB0
SPR_MISCF      = 0x0EC0
SPR_MISCG      = 0x0ED0
SPR_TIMERD     = 0x0EE0
SPR_DEATH      = 0x0EF0
SPR_TIMERE     = 0x0F10
SPR_HITBOX     = 0x0F60
SPR_FLASH      = 0x0B89
SPR_BULLETPR   = 0x0BA0
SPR_PRIZE      = 0x0BE0
SPR_DEFL       = 0x0CAA
SPR_BUMP       = 0x0CD2

# Player / World / Quest RAM
INIDISPQ       = 0x0013
CGRAM_UPD      = 0x0015
FRAME_CTR      = 0x001A
INDOORS        = 0x001B
LINK_Y         = 0x0020
LINK_X         = 0x0022
BFLAG          = 0x003C
OW_AREA        = 0x008A
ROOM_ID        = 0x00A0
PLAYER_LOCK    = 0x02E4
BRANDISH       = 0x02DA
SONG_FLAG      = 0x030F  # read dynamically from labels["SongFlag"]
WOLF_MASK      = 0x7EF358
IN_CUTSCENE    = 0x7EF303
DMGTABLE_A9    = 0x7F6A90

# Wolfos constants matching Sprites/Bosses/wolfos.asm
FLAG_ICE       = 0x01
FLAG_ALPHA     = 0x02
FLAG_QUEST     = 0x04
FLAG_ENRAGED   = 0x08

ACT_STALK      = 0x00
ACT_CIRCLE     = 0x01
ACT_GUARD      = 0x02
ACT_DODGEHOP   = 0x03
ACT_TELEGRAPH  = 0x04
ACT_LUNGE      = 0x05
ACT_RECOVER    = 0x06
ACT_STAGGER    = 0x07
ACT_SUBDUED    = 0x08
ACT_HEALPULSE  = 0x09
ACT_GRANTMASK  = 0x0A
ACT_DISMISS    = 0x0B


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
    _LAKESNES_TMP = tempfile.TemporaryDirectory(prefix="oos-wolfos-lakesnes-")
    so_path = Path(_LAKESNES_TMP.name) / "libcpu.dylib"
    cmd = [
        "cc", "-shared", "-fPIC", "-O2",
        str(src_root / "snes" / "cpu.c"),
        str(src_root / "snes" / "statehandler.c"),
        "-o", str(so_path),
    ]
    subprocess.run(cmd, check=True)
    lib = C.CDLL(str(so_path))
    lib.cpu_init.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_runOpcode.restype = C.c_int
    _LAKESNES_LIB = lib
    return lib


def parse_sym(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in sym_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", line.strip())
        if m and ":" not in m.group(3):
            labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


def lorom_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


JUMP_TABLE_LOCAL_ASM = """
org JumpTableLocal
  REP #$30
  AND.w #$00FF : ASL A : TAY
  PLA : INC A : STA.b $00
  SEP #$20
  PLA : STA.b $02 : PHA
  REP #$20
  LDA.b [$00], Y : DEC A : PHA
  SEP #$30
  RTL
"""


def _build_wolfos_rom() -> tuple[bytes, dict[str, int]]:
    asar = find_asar()
    assert asar, "asar binary required"
    asm_source = f"""
lorom
incsrc "Config/feature_flags.asm"
incsrc "Core/sram.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"

!ENABLE_OCARINA_SONG_TINT = 1
!SongTint_Healing = $01
SongTint_Start = $2BFF00

; Minimal WRAM aliases from Core/ram.asm (Oracle_main includes symbols/ram in order)
POSY     = $0020
POSYH    = $0021
POSX     = $0022
POSXH    = $0023
BRANDISH = $02DA

; Stubs for engine helpers defined in Core/sprite_functions.asm / BossKit
Sprite_CheckActive             = $30FE00
Sprite_DamageFlash_Long        = $30FE10
Sprite_CheckIfRecoiling        = $30FE20
Sprite_InvertSpeed_XY          = $30FE30
BossKit_FxAtSprite             = $30FE40
BossKit_FxAtOffset             = $30FE50
Sprite_Move                    = $30FE60
Sprite_BounceFromTileCollision = $30FE70
NewMainSprFunction             = $308000
NewSprPrepFunction             = $308010
NewSprRoutinesLong             = $309000
NewSprPrepRoutinesLong         = $309400

{JUMP_TABLE_LOCAL_ASM}

org $318000
incsrc "Sprites/Bosses/wolfos.asm"
"""
    with tempfile.TemporaryDirectory(prefix="oos-wolfos-asm-") as td:
        tmp = Path(td)
        rom_path = tmp / "wolfos_test.sfc"
        rom_path.write_bytes(b"\x00" * 0x200000)  # 2 MiB LoROM (covers up to bank $3F)
        src_path = tmp / "main.asm"
        src_path.write_text(asm_source, encoding="utf-8")
        sym_path = tmp / "wolfos_test.sym"
        res = subprocess.run(
            [asar, "--no-title-check", "-I" + str(ROOT), "--symbols=wla",
             f"--symbols-path={sym_path}", str(src_path), str(rom_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            errors="replace",
        )
        if res.returncode != 0:
            raise AssertionError(f"asar failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return rom_path.read_bytes(), parse_sym(sym_path)


class WolfosHarness:
    """LakeSnes 65816 execution harness for compiled `Sprites/Bosses/wolfos.asm`."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        self.lib = lib
        self.rom = bytearray(rom)
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.hw_writes: list[tuple[int, int]] = []
        self.stubs: dict[int, str] = {}
        self.stub_handlers: dict[str, callable] = {}
        self.calls: list[tuple[str, int, int, int]] = []
        self.sfx2: list[int] = []
        self.sfx3: list[int] = []
        self.messages: list[int] = []
        self.garnishes: list[tuple[str, int]] = []
        self.rng_seq: list[int] = [0]
        self.rng_idx = 0
        self.tile_collision = 0
        self.prep_oam_offscreen = False
        self.damage_to_player_hit = False

        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self._install_default_stubs()

    def addr(self, name: str) -> int:
        return self.labels[name]

    @staticmethod
    def ram_offset(a: int) -> int | None:
        bank = (a >> 16) & 0xFF
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def read(self, a: int) -> int:
        if a in self.stubs:
            return 0x6B  # RTL
        off = self.ram_offset(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = lorom_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def write(self, a: int, v: int):
        v &= 0xFF
        off = self.ram_offset(a)
        if off is not None:
            self.ram[off] = v
            return
        lo = a & 0xFFFF
        if 0x2100 <= lo <= 0x43FF:
            self.hw_writes.append((lo, v))

    def get(self, a: int) -> int:
        return self.read(a)

    def get16(self, a: int) -> int:
        return self.get(a) | (self.get(a + 1) << 8)

    def put(self, a: int, v: int):
        off = self.ram_offset(a)
        assert off is not None, f"Non-RAM address {a:06X}"
        self.ram[off] = v & 0xFF

    def put16(self, a: int, v: int):
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def set_spr_pos(self, slot: int, x: int, y: int):
        self.put(SPR_X + slot, x & 0xFF)
        self.put(SPR_XH + slot, (x >> 8) & 0xFF)
        self.put(SPR_Y + slot, y & 0xFF)
        self.put(SPR_YH + slot, (y >> 8) & 0xFF)

    def set_link_pos(self, x: int, y: int):
        self.put16(LINK_X, x)
        self.put16(LINK_Y, y)

    def add_stub(self, name: str, handler=None):
        a = self.addr(name)
        self.stubs[a] = name
        if handler is not None:
            self.stub_handlers[name] = handler

    def _install_default_stubs(self):
        # Active check: returns Carry set when SprState,X == $09
        def _check_active(h):
            h.cpu.c = (h.get(SPR_STATE + h.cpu.x) == 0x09)

        def _rng(h):
            val = h.rng_seq[h.rng_idx % len(h.rng_seq)]
            h.rng_idx += 1
            h.cpu.a = (h.cpu.a & 0xFF00) | (val & 0xFF)
            h.cpu.z = (val & 0xFF) == 0
            h.cpu.n = bool(val & 0x80)

        def _sfx2(h):
            h.sfx2.append(h.cpu.a & 0xFF)

        def _sfx3(h):
            h.sfx3.append(h.cpu.a & 0xFF)

        def _msg_uncond(h):
            mid = (h.cpu.a & 0xFF) | ((h.cpu.y & 0xFF) << 8)
            h.messages.append(mid)

        def _msg_solicit(h):
            h.cpu.c = False

        def _apply_speed_toward(h):
            spd = h.cpu.a & 0xFF
            slot = h.cpu.x & 0xFF
            sx = h.get(SPR_X + slot) | (h.get(SPR_XH + slot) << 8)
            sy = h.get(SPR_Y + slot) | (h.get(SPR_YH + slot) << 8)
            lx = h.get16(LINK_X)
            ly = h.get16(LINK_Y)
            dx, dy = lx - sx, ly - sy
            mag = max(abs(dx), abs(dy), 1)
            vx = int(round(spd * dx / mag))
            vy = int(round(spd * dy / mag))
            h.put(SPR_XSPD + slot, vx & 0xFF)
            h.put(SPR_YSPD + slot, vy & 0xFF)

        def _invert_speed(h):
            slot = h.cpu.x & 0xFF
            vx = (-h.get(SPR_XSPD + slot)) & 0xFF
            vy = (-h.get(SPR_YSPD + slot)) & 0xFF
            h.put(SPR_XSPD + slot, vx)
            h.put(SPR_YSPD + slot, vy)

        def _sprite_move(h):
            slot = h.cpu.x & 0xFF
            vx = h.get(SPR_XSPD + slot)
            vy = h.get(SPR_YSPD + slot)
            if vx >= 0x80:
                vx -= 0x100
            if vy >= 0x80:
                vy -= 0x100
            sx = (h.get(SPR_X + slot) | (h.get(SPR_XH + slot) << 8)) + (vx // 16 if abs(vx) >= 16 else (1 if vx > 0 else (-1 if vx < 0 else 0)))
            sy = (h.get(SPR_Y + slot) | (h.get(SPR_YH + slot) << 8)) + (vy // 16 if abs(vy) >= 16 else (1 if vy > 0 else (-1 if vy < 0 else 0)))
            h.set_spr_pos(slot, sx & 0xFFFF, sy & 0xFFFF)

        def _tile_col(h):
            h.cpu.a = (h.cpu.a & 0xFF00) | (h.tile_collision & 0xFF)
            h.cpu.z = (h.tile_collision == 0)

        def _spawn_dyn(h):
            # Find first free slot (SprState == 0) in 0..15
            for s in range(16):
                if h.get(SPR_STATE + s) == 0:
                    h.put(SPR_STATE + s, 0x09)
                    h.put(SPR_TYPE + s, h.cpu.a & 0xFF)
                    h.cpu.y = s
                    h.cpu.n = False
                    return
            h.cpu.y = 0xFF
            h.cpu.n = True

        def _prep_oam(h):
            h.cpu.c = h.prep_oam_offscreen
            slot = h.cpu.x & 0xFF
            h.put16(0x00, h.get(SPR_X + slot))
            h.put16(0x02, h.get(SPR_Y + slot))
            # Point OAM buffers $90/$92 to $0800 / $0A20
            h.put16(0x90, 0x0800)
            h.put16(0x92, 0x0A20)

        def _dmg_to_player(h):
            h.cpu.c = h.damage_to_player_hit

        def _fx_sprite(h):
            h.garnishes.append(("sprite", h.cpu.a & 0xFF))
            h.cpu.y = 0x06  # Real BossKit_SpawnFx clobbers Y with free garnish slot
            h.cpu.c = True

        def _fx_offset(h):
            h.garnishes.append(("offset", h.cpu.a & 0xFF))
            h.cpu.y = 0x06  # Real BossKit_SpawnFx clobbers Y with free garnish slot
            h.cpu.c = True

        def _nop(h):
            pass

        self.add_stub("Sprite_CheckActive", _check_active)
        self.add_stub("GetRandomInt", _rng)
        self.add_stub("Sound_SetSfx2PanLong", _sfx2)
        self.add_stub("Sound_SetSfx3PanLong", _sfx3)
        self.add_stub("Sprite_ShowMessageUnconditional", _msg_uncond)
        self.add_stub("Sprite_ShowSolicitedMessageIfPlayerFacing", _msg_solicit)
        self.add_stub("Sprite_ApplySpeedTowardsPlayer", _apply_speed_toward)
        self.add_stub("Sprite_InvertSpeed_XY", _invert_speed)
        self.add_stub("Sprite_Move", _sprite_move)
        self.add_stub("Sprite_CheckTileCollision", _tile_col)
        self.add_stub("Sprite_BounceFromTileCollision", _nop)
        self.add_stub("Sprite_DamageFlash_Long", _nop)
        self.add_stub("Sprite_CheckIfRecoiling", _nop)
        self.add_stub("Sprite_CheckDamageFromPlayer", _nop)
        self.add_stub("Sprite_CheckDamageToPlayerSameLayer", _dmg_to_player)
        self.add_stub("Sprite_PlayerCantPassThrough", _nop)
        self.add_stub("Sprite_SpawnDynamically", _spawn_dyn)
        self.add_stub("Sprite_PrepOamCoord", _prep_oam)
        self.add_stub("Sprite_OAM_AllocateDeferToPlayer", _nop)
        self.add_stub("BossKit_FxAtSprite", _fx_sprite)
        self.add_stub("BossKit_FxAtOffset", _fx_offset)
        self.add_stub("SongTint_Start", _nop)

    def call_jsl(self, name: str, *, x: int = 0, y: int = 0, a: int = 0, max_steps: int = 8000):
        target = self.addr(name)
        sentinel_bank, sentinel_pc = 0x00, 0x1FFE
        self.cpu.db = 0x7E
        self.cpu.mf = True
        self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.a = a & 0xFF
        self.cpu.x = x & 0xFF
        self.cpu.y = y & 0xFF
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped"):
            setattr(self.cpu, flag, False)
        ret = sentinel_pc - 1
        self.ram[0x01FF] = sentinel_bank
        self.ram[0x01FE] = (ret >> 8) & 0xFF
        self.ram[0x01FD] = ret & 0xFF
        self.cpu.sp = 0x01FC
        self.cpu.k = (target >> 16) & 0xFF
        self.cpu.pc = target & 0xFFFF
        steps = 0
        while steps < max_steps:
            if self.cpu.k == sentinel_bank and self.cpu.pc == sentinel_pc:
                assert self.cpu.sp == 0x01FF, f"Stack imbalance after {name}: sp=${self.cpu.sp:04X}"
                assert self.cpu.mf and self.cpu.xf, f"Width imbalance after {name}: mf={self.cpu.mf} xf={self.cpu.xf}"
                return steps
            cur = (self.cpu.k << 16) | self.cpu.pc
            if cur in self.stubs:
                sname = self.stubs[cur]
                self.calls.append((sname, self.cpu.a, self.cpu.x, self.cpu.y))
                if sname in self.stub_handlers:
                    self.stub_handlers[sname](self)
            self.lib.cpu_runOpcode(self.p)
            steps += 1
        raise AssertionError(f"{name} hung at {self.cpu.k:02X}:{self.cpu.pc:04X}")

    def tick_timers(self, slot: int):
        """Mimic vanilla Sprite_TimersAndOAM auto-decrementing timers."""
        for base in (SPR_TIMERA, SPR_TIMERB, SPR_TIMERC, SPR_TIMERD, SPR_TIMERE):
            v = self.get(base + slot)
            if v > 0:
                self.put(base + slot, v - 1)
        self.put(FRAME_CTR, (self.get(FRAME_CTR) + 1) & 0xFF)


class TestWolfosCombat(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = get_lakesnes_lib()
        if cls.lib is None:
            raise unittest.SkipTest("LakeSnes C CPU source not found")
        if find_asar() is None:
            raise unittest.SkipTest("asar binary not found")
        cls.rom, cls.labels = _build_wolfos_rom()
        cls.song_flag_addr = cls.labels["SongFlag"]

    def make(self) -> WolfosHarness:
        return WolfosHarness(self.lib, self.rom, self.labels)

    # --- 1. Art & Palette Contract ---

    def test_ice_wolfos_art_generator_check(self):
        res = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/build_ice_wolfos_art.py"), "--check"],
            capture_output=True, text=True, check=False,
        )
        self.assertEqual(res.returncode, 0, res.stderr + res.stdout)
        art = (ROOT / "Data/graphics/sprites/ice_wolfos.4bpp").read_bytes()
        self.assertEqual(len(art), 4096)
        pc = lorom_pc(self.labels["Wolfos_Art4bpp"])
        self.assertEqual(self.rom[pc:pc + 4096], art)

    def test_prep_uploads_palettes_safely_and_restores_inidispq(self):
        # Standard Quest Wolfos (Castle $1B): OAM Pal 5 C1..C7; Link Sword C9..C11 untouched!
        h = self.make()
        h.put(INIDISPQ, 0x0F)
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(SPR_STATE + 2, 0x09)
        h.put16(0x7EC6B2, 0x1234)  # Link sword color sentinel in SP-5 C9
        h.call_jsl("Sprite_Wolfos_Prep", x=2)
        self.assertEqual(h.get(SPR_MISCG + 2), 0x0A)
        self.assertEqual(h.get16(0x7EC6A2), 0x7FFF)  # C1 white
        self.assertEqual(h.get16(0x7EC6A4), 0x02BF)  # C2 gold eyes
        self.assertEqual(h.get16(0x7EC6B2), 0x1234, "Must never clobber Link Sword SP-5 C9..C11!")
        # Verify VRAM DMA to $5800 for $1000 bytes and INIDISP restored to $13 ($0F)
        inidisp_writes = [v for reg, v in h.hw_writes if reg == 0x2100]
        self.assertEqual(inidisp_writes, [0x80, 0x0F])
        self.assertIn((0x2116, 0x00), h.hw_writes)
        self.assertIn((0x2117, 0x58), h.hw_writes)
        self.assertIn((0x4305, 0x00), h.hw_writes)
        self.assertIn((0x4306, 0x10), h.hw_writes)
        self.assertIn((0x420B, 0x01), h.hw_writes)

        # Ice Wolfos (Snowpeak $04): OAM Pal 6 C1..C7; INIDISPQ=$80 fade-in preserved!
        h2 = self.make()
        h2.put(INIDISPQ, 0x80)
        h2.put(INDOORS, 0)
        h2.put(OW_AREA, 0x04)
        h2.put(SPR_STATE + 1, 0x09)
        h2.put16(0x7EC6D2, 0x5678)
        h2.call_jsl("Sprite_Wolfos_Prep", x=1)
        self.assertEqual(h2.get(SPR_MISCG + 1), 0x0C)
        self.assertEqual(h2.get16(0x7EC6C8), 0x7E56)  # GameyFireBro lavender-ice mane!
        self.assertEqual(h2.get16(0x7EC6CC), 0x7FDD)  # Snow-white fur!
        self.assertEqual(h2.get16(0x7EC4C8), 0x7E56)  # Fade buffer mirrored!
        self.assertEqual(h2.get16(0x7EC6D2), 0x5678, "C8..C15 must stay untouched!")
        self.assertEqual([v for reg, v in h2.hw_writes if reg == 0x2100], [0x80, 0x80])

    # --- 2. Variant Detection & Bug #1 Despawn Fix ---

    def test_castle_quest_wolfos_despawns_when_wolf_mask_owned(self):
        # Bug #1 regression: InCutSceneFlag=0, WolfMask=1 MUST despawn Castle Wolfos
        h = self.make()
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(IN_CUTSCENE, 0)
        h.put(WOLF_MASK, 1)
        h.put(SPR_STATE + 0, 0x09)
        h.call_jsl("Sprite_Wolfos_Prep", x=0)
        self.assertEqual(h.get(SPR_STATE + 0), 0x00, "Castle Wolfos must stay gone after WolfMask earned!")

        # Conversely, Snowpeak Ice Wolfos MUST still spawn even when WolfMask == 1!
        h2 = self.make()
        h2.put(INDOORS, 0)
        h2.put(OW_AREA, 0x06)
        h2.put(WOLF_MASK, 1)
        h2.put(SPR_STATE + 0, 0x09)
        h2.call_jsl("Sprite_Wolfos_Prep", x=0)
        self.assertEqual(h2.get(SPR_STATE + 0), 0x09)
        self.assertEqual(h2.get(SPR_MISCA + 0), FLAG_ICE)
        self.assertEqual(h2.get(SPR_HEALTH + 0), 0x24)  # 36 HP roving Ice Wolfos

    def test_room_120_auto_detects_alpha_ice_wolfos_and_fire_weakness(self):
        h = self.make()
        h.put(INDOORS, 1)
        h.put16(ROOM_ID, 0x0120)  # Wolfos Cave (Ice Rod fight!)
        h.put(SPR_STATE + 0, 0x09)
        h.call_jsl("Sprite_Wolfos_Prep", x=0)
        self.assertEqual(h.get(SPR_MISCA + 0), FLAG_ICE | FLAG_ALPHA)
        self.assertEqual(h.get(SPR_HEALTH + 0), 0x30)  # 48 HP Alpha Mini-Boss
        self.assertEqual(h.get(SPR_BUMP + 0), 0x03)    # 2-heart Green / 1-heart Blue
        # Check DMGTABLE row ($7F6A90): Fire Rod ($0B) == $05 (16 HP), Ice Rod ($0C) == $00 (immune), Bombos ($0D) == $02 (64 HP)
        self.assertEqual(h.get(DMGTABLE_A9 + 0x0B), 0x05)
        self.assertEqual(h.get(DMGTABLE_A9 + 0x0C), 0x00)
        self.assertEqual(h.get(DMGTABLE_A9 + 0x0D), 0x02)
        self.assertEqual(h.get(DMGTABLE_A9 + 0x0E), 0x00)

    # --- 3. 4-Direction Symmetric Telegraph -> Lunge -> Recover ---

    def test_four_direction_lunge_timer_and_frame_symmetry(self):
        # Verify Right (0), Left (1), Down (2), Up (3) all share identical Telegraph/Lunge/Recover durations!
        cases = [
            # (name, link_dx, link_dy, expected_facing, tele_frame, lunge_frame)
            ("Right", +32,   0, 0, 12, 13),
            ("Left",  -32,   0, 1, 14, 15),
            ("Down",    0, +32, 2,  1,  2),
            ("Up",      0, -32, 3,  4,  5),
        ]
        for label, dx, dy, exp_dir, exp_tele_f, exp_lunge_f in cases:
            with self.subTest(direction=label):
                h = self.make()
                h.put(INDOORS, 0)
                h.put(OW_AREA, 0x1B)
                h.put(SPR_STATE + 0, 0x09)
                h.set_spr_pos(0, 0x0100, 0x0100)
                h.set_link_pos(0x0100 + dx, 0x0100 + dy)
                h.call_jsl("Sprite_Wolfos_Prep", x=0)
                h.put(SPR_TIMERC + 0, 0)  # Attack cooldown ready!

                # Frame 1: Stalk -> enters Telegraph
                h.call_jsl("Sprite_Wolfos_Long", x=0)
                self.assertEqual(h.get(SPR_ACTION + 0), ACT_TELEGRAPH)
                self.assertEqual(h.get(SPR_MISCE + 0), exp_dir)
                self.assertEqual(h.get(SPR_TIMERA + 0), 0x18)
                self.assertEqual(h.get(SPR_FRAME + 0), exp_tele_f)

                # Tick down Telegraph -> launches Lunge
                for _ in range(0x18):
                    h.tick_timers(0)
                    h.call_jsl("Sprite_Wolfos_Long", x=0)
                self.assertEqual(h.get(SPR_ACTION + 0), ACT_LUNGE)
                self.assertEqual(h.get(SPR_TIMERA + 0), 0x16, f"{label} lunge timer must be $16!")
                self.assertEqual(h.get(SPR_FRAME + 0), exp_lunge_f)
                # Must actually move along the attack axis!
                vx = h.get(SPR_XSPD + 0)
                vy = h.get(SPR_YSPD + 0)
                self.assertTrue(vx != 0 or vy != 0, f"{label} lunge had zero velocity!")

                # Tick down Lunge -> transitions to vulnerable Recover
                for _ in range(0x16):
                    h.tick_timers(0)
                    h.call_jsl("Sprite_Wolfos_Long", x=0)
                self.assertEqual(h.get(SPR_ACTION + 0), ACT_RECOVER)
                self.assertEqual(h.get(SPR_TIMERA + 0), 0x22)
                self.assertEqual(h.get(SPR_DEFL + 0) & 0x04, 0, "Recover MUST clear ImpervSwordHammer!")

    # --- 4. Frontal Guard, Flank Bypass, Spin Break, Circle & Dodge ---

    def test_frontal_guard_flank_bypass_and_spin_attack_break(self):
        h = self.make()
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(SPR_STATE + 0, 0x09)
        h.set_spr_pos(0, 0x0100, 0x0100)
        h.set_link_pos(0x0120, 0x0100)  # Link 32px to the Right (in front!)
        h.call_jsl("Sprite_Wolfos_Prep", x=0)

        # Link swings normal sword ($3C = $04) in front -> Wolfos raises Guard!
        h.put(BFLAG, 0x04)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_GUARD)
        self.assertEqual(h.get(SPR_DEFL + 0) & 0x04, 0x04, "Guard must set ImpervSwordHammer bit!")
        self.assertIn(0x05, h.sfx2)  # Guard clink

        # Link moves behind Wolfos (left side) -> Guard drops immediately so backstab hits!
        h.set_link_pos(0x00E0, 0x0100)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_DEFL + 0) & 0x04, 0x00, "Flank/back MUST bypass guard!")

        # Link steps back in front with Spin Attack ($3C = $94) -> Spin breaks guard!
        h.set_link_pos(0x0120, 0x0100)
        h.put(BFLAG, 0x94)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_DEFL + 0) & 0x04, 0x00, "Spin Attack MUST break guard!")

    def test_circle_orbit_and_dodge_backhop_have_real_velocities(self):
        h = self.make()
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(SPR_STATE + 0, 0x09)
        h.set_spr_pos(0, 0x0100, 0x0100)
        h.set_link_pos(0x0140, 0x0100)  # 64px to the right -> enters Circle when TimerA==0
        h.call_jsl("Sprite_Wolfos_Prep", x=0)
        h.put(SPR_TIMERA + 0, 0)
        h.rng_seq = [0]  # CW orbit
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_CIRCLE)

        # Next frame: Circle computes tangential velocity (vx=0, vy=-13 for Link directly right!)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        vy = h.get(SPR_YSPD + 0)
        self.assertNotEqual(vy, 0, "CirclePlayer must produce real perpendicular orbital velocity!")

        # Trigger hit -> Stagger -> DodgeHop away from Link
        prev_hp = h.get(SPR_HEALTH + 0)
        h.put(SPR_HEALTH + 0, prev_hp - 4)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_STAGGER)

        # Tick down Stagger with RNG=1 -> enters DodgeHop moving LEFT (away from Link at +X!)
        h.rng_seq = [1]
        for _ in range(0x0E):
            h.tick_timers(0)
            h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_DODGEHOP)
        vx = h.get(SPR_XSPD + 0)
        self.assertGreaterEqual(vx, 0x80, "DodgeHop must leap negatively (away from Link on right)!")
        self.assertEqual((0x100 - vx), 0x18, "DodgeHop speed must be full $18 (not stale $02)!")

    # --- 5. Ice Wolfos Shards, Alpha Enrage & Fire Melt ---

    def test_alpha_ice_wolfos_spawns_shards_and_enrages_at_half_hp(self):
        h = self.make()
        h.put(INDOORS, 1)
        h.put16(ROOM_ID, 0x0120)
        h.put(SPR_STATE + 3, 0x09)  # Use non-zero slot X=3 to also verify PHX/PHA stack safety!
        h.set_spr_pos(3, 0x0100, 0x0100)
        h.set_link_pos(0x0128, 0x0100)
        h.call_jsl("Sprite_Wolfos_Prep", x=3)
        h.put(SPR_TIMERC + 3, 0)

        # Phase 1: Telegraph -> Frost Burst spawns exactly 4 sparkles (even though BossKit clobbers Y!)
        h.garnishes.clear()
        h.call_jsl("Sprite_Wolfos_Long", x=3)
        self.assertEqual(h.get(SPR_ACTION + 3), ACT_TELEGRAPH)
        self.assertEqual(
            len([g for g in h.garnishes if g == ("offset", 0x05)]),
            4,
            "Wolfos_SpawnFrostBurst must emit all 4 frost sparkles without Y-clobber hang!",
        )
        for _ in range(0x14):
            h.tick_timers(3)
            h.call_jsl("Sprite_Wolfos_Long", x=3)
        self.assertEqual(h.get(SPR_ACTION + 3), ACT_LUNGE)
        shards = [s for s in range(16) if h.get(SPR_STATE + s) == 0x09 and h.get(SPR_SUBTYPE + s) == 0x80]
        self.assertEqual(len(shards), 1, "Phase 1 Ice Wolfos lunge must spawn 1 Ice Shard!")
        sh = shards[0]
        self.assertGreater(
            h.get(SPR_XSPD + sh),
            h.get(SPR_XSPD + 3),
            "Ice Shard must travel strictly faster than lunging Ice Wolfos!",
        )
        self.assertEqual(h.get(SPR_HITBOX + sh) & 0x40, 0x40, "Ice Shard MUST have Statis=1 so it never blocks shutters!")
        self.assertEqual(h.get(SPR_PRIZE + sh) & 0x20, 0x20, "Ice Shard must be shield-blockable!")
        self.assertEqual(h.get(SPR_MISCA + sh), 3, "Ice Shard must record parent slot 3!")

        # Drop Alpha Ice Wolfos HP by 24 (Fire Rod melt!) -> triggers Enrage + heavy melt stagger!
        h.put(SPR_HEALTH + 3, 0x18)  # 24 HP (50%)
        h.sfx3.clear()
        h.call_jsl("Sprite_Wolfos_Long", x=3)
        self.assertTrue(h.get(SPR_MISCA + 3) & FLAG_ENRAGED, "Alpha Ice Wolfos must enrage at <= 24 HP!")
        self.assertIn(0x26, h.sfx3)  # Fierce enrage howl
        self.assertIn(0x21, h.sfx3)  # Heavy melt crunch

        # Clear old shard & launch Phase 2 Enraged lunge -> spawns TWO fanned shards!
        h.put(SPR_STATE + sh, 0)
        h.put(SPR_ACTION + 3, ACT_STALK)
        h.put(SPR_TIMERC + 3, 0)
        h.call_jsl("Sprite_Wolfos_Long", x=3)
        self.assertEqual(h.get(SPR_ACTION + 3), ACT_TELEGRAPH)
        self.assertEqual(h.get(SPR_TIMERA + 3), 0x10, "Enraged telegraph must be faster ($10)!")
        for _ in range(0x10):
            h.tick_timers(3)
            h.call_jsl("Sprite_Wolfos_Long", x=3)
        shards2 = [s for s in range(16) if h.get(SPR_STATE + s) == 0x09 and h.get(SPR_SUBTYPE + s) == 0x80]
        self.assertEqual(len(shards2), 2, "Enraged Alpha Ice Wolfos lunge must spawn 2 fanned Ice Shards!")
        # Verify the two shards have distinct spread velocities
        v0 = (h.get(SPR_XSPD + shards2[0]), h.get(SPR_YSPD + shards2[0]))
        v1 = (h.get(SPR_XSPD + shards2[1]), h.get(SPR_YSPD + shards2[1]))
        self.assertNotEqual(v0, v1, "Enraged dual Ice Shards must fan apart!")

        # Kill parent -> shards despawn cleanly on next tick!
        h.put(SPR_STATE + 3, 0x06)
        for s in shards2:
            h.call_jsl("Sprite_Wolfos_Long", x=s)
            self.assertEqual(h.get(SPR_STATE + s), 0x00, "Shard must despawn when parent dies!")

    # --- 6. Subdued -> Song of Healing -> Wolf Mask & Draw OOB Fix ---

    def test_song_of_healing_wolf_mask_sequence_and_overkill_protection(self):
        h = self.make()
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(SPR_STATE + 0, 0x09)
        h.set_spr_pos(0, 0x0100, 0x0100)
        h.set_link_pos(0x0118, 0x0108)  # POSY=$0108 -> tests 16-bit borrow POSY-$10 = $00F8!
        h.call_jsl("Sprite_Wolfos_Prep", x=0)
        self.assertEqual(h.get(SPR_HEALTH + 0), 0x32)  # 30 eff + 20 buffer

        # Simulate massive 16 HP overkill blow from HP=21 ($15) -> HP=5 (>0, cannot die!), enters Subdued!
        h.put(SPR_HEALTH + 0, 0x05)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_SUBDUED)
        self.assertEqual(h.get(SPR_STATE + 0), 0x09)
        self.assertEqual(h.get(SPR_NBROAM + 0) & 0x80, 0x80, "Subdued Wolfos must be harmless!")
        self.assertEqual(h.get(SPR_E60 + 0) & 0x40, 0x40, "Subdued Wolfos must be impervious!")
        self.assertIn(0x23, h.messages)

        # Non-healing song ($02 Song of Time) must NOT trigger healing or clear SongFlag!
        h.put(self.song_flag_addr, 0x02)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_SUBDUED)
        self.assertEqual(h.get(self.song_flag_addr), 0x02)

        # Play Song of Healing ($01) -> consumes SongFlag, starts SongTint, locks movement, enters HealPulse!
        h.put(self.song_flag_addr, 0x01)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(self.song_flag_addr), 0x00)
        self.assertEqual(h.get(PLAYER_LOCK), 0x01)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_HEALPULSE)
        self.assertEqual(h.get(SPR_TIMERD + 0), 0x50)
        self.assertIn("SongTint_Start", [c[0] for c in h.calls])

        # Tick down HealPulse -> places Wolf Mask at (POSX, POSY-$10) with 16-bit borrow, grants WolfMask!
        for _ in range(0x50):
            h.tick_timers(0)
            h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_GRANTMASK)
        self.assertEqual(h.get(SPR_FRAME + 0), 16)
        self.assertEqual(h.get(BRANDISH), 0x01)
        self.assertEqual(h.get(WOLF_MASK), 0x01)
        self.assertEqual(h.get(SPR_Y + 0) | (h.get(SPR_YH + 0) << 8), 0x00F8)
        self.assertIn(0x10F, h.messages)
        self.assertIn(0x0F, h.sfx3)  # Item fanfare!
        self.assertEqual(h.get(SPR_TIMERD + 0), 0x3C, "GrantMask must hold brandish for 60 frames (not 0)!")

        # After 1 frame of GrantMask, Wolfos is STILL holding brandish (fixes Bug #7 instant abort!)
        h.tick_timers(0)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_GRANTMASK)
        self.assertEqual(h.get(BRANDISH), 0x01)

        # Finish remaining 59 frames + Dismiss frame -> clears BRANDISH, unlocks movement, despawns!
        for _ in range(0x3B):
            h.tick_timers(0)
            h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(SPR_ACTION + 0), ACT_DISMISS)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(BRANDISH), 0x00)
        self.assertEqual(h.get(PLAYER_LOCK), 0x00)
        self.assertEqual(h.get(SPR_STATE + 0), 0x00)

    def test_draw_wolf_mask_single_tile_no_oob_and_proper_flash_palette(self):
        h = self.make()
        h.put(INDOORS, 0)
        h.put(OW_AREA, 0x1B)
        h.put(SPR_STATE + 0, 0x09)
        h.set_spr_pos(0, 0x0080, 0x0080)
        h.call_jsl("Sprite_Wolfos_Prep", x=0)

        # Sentinel in OAM slot 1 ($0804) to verify Frame 16 writes ONLY 1 tile (slot 0)!
        for i in range(8):
            h.put(0x0800 + i, 0xAA)
        h.put(SPR_ACTION + 0, ACT_GRANTMASK)
        h.put(SPR_TIMERD + 0, 0x20)
        h.put(SPR_FRAME + 0, 16)
        h.put(SPR_FLASH + 0, 0)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(0x0802), 0xCC, "Frame 16 tile 0 must be Wolf Mask $CC!")
        self.assertEqual(h.get(0x0803), 0x2B, "Standard Wolfos OAM prop must be $2B (Pal 5, n=1)!")
        self.assertEqual(h.get(0x0804), 0xAA, "Frame 16 MUST NOT write a 2nd OOB OAM tile!")

        # Verify damage flash shifts SprFlash<<1 and XORs SprMiscG without corrupting nametable bit 0!
        h.put(SPR_MISCG + 0, 0x0C)  # Ice Wolfos Pal 6
        h.put(SPR_FLASH + 0, 0x03)  # Flash counter 3 -> (3<<1)^$0C = $06^$0C = $0A
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(0x0803), 0x21 | 0x0A, "Flash must preserve nametable bit 0 and pri bits!")

        # Also verify H-flipped walk frame preserves H-flip ($61 | $0A = $6B)!
        h.put(SPR_FRAME + 0, 9)
        h.put(SPR_STATE + 0, 0x09)
        h.put(SPR_ACTION + 0, ACT_RECOVER)
        h.put(SPR_TIMERA + 0, 0x10)
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h.get(0x0803), 0x61 | 0x0A, "Flash must preserve H-flip bit $40 and nametable bit $01!")

        # Verify offscreen clip skips OAM allocation!
        h.calls.clear()
        h.prep_oam_offscreen = True
        h.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertNotIn("Sprite_OAM_AllocateDeferToPlayer", [c[0] for c in h.calls])

    def test_ice_shard_draw_and_16bit_distance_no_wrap(self):
        # Verify Ice Shard draws global Sheet $79 crystal ($AA -> $AC) with spinning OAM Pal 2 ($24/$64/$A4/$E4)
        h = self.make()
        h.put(SPR_STATE + 4, 0x09)
        h.put(SPR_SUBTYPE + 4, 0x80)
        h.put(SPR_MISCA + 4, 0)
        h.put(SPR_STATE + 0, 0x09)  # Live parent
        h.put(SPR_TIMERA + 4, 0x20)
        h.set_spr_pos(4, 0x0080, 0x0070)
        h.put(FRAME_CTR, 0x04)  # ($04 & $0C) << 4 | $24 = $64
        h.call_jsl("Sprite_Wolfos_Long", x=4)
        self.assertEqual(h.get(0x0802), 0xAA, "Live Ice Shard must draw frost crystal $AA!")
        self.assertEqual(h.get(0x0803), 0x64, "Ice Shard must spin with OAM Pal 2 ($04), n=0!")

        # Near end of life (TimerA < 8) switches to shattering frost shard $AC
        h.put(SPR_TIMERA + 4, 0x04)
        h.put(FRAME_CTR, 0x08)  # ($08 & $0C) << 4 | $24 = $A4
        h.call_jsl("Sprite_Wolfos_Long", x=4)
        self.assertEqual(h.get(0x0802), 0xAC, "Expiring Ice Shard must draw shatter tile $AC!")
        self.assertEqual(h.get(0x0803), 0xA4)

        # Verify 16-bit distance at dx=260px does NOT wrap to 4px and trigger melee telegraph!
        h2 = self.make()
        h2.put(INDOORS, 0)
        h2.put(OW_AREA, 0x1B)
        h2.put(SPR_STATE + 0, 0x09)
        h2.set_spr_pos(0, 0x0020, 0x0100)
        h2.set_link_pos(0x0020 + 260, 0x0100)
        h2.call_jsl("Sprite_Wolfos_Prep", x=0)
        h2.put(SPR_TIMERC + 0, 0)
        h2.call_jsl("Sprite_Wolfos_Long", x=0)
        self.assertEqual(h2.get(SPR_ACTION + 0), ACT_STALK, "260px away must NOT wrap 8-bit and trigger lunge!")


if __name__ == "__main__":
    unittest.main()
