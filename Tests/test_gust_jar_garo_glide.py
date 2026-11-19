#!/usr/bin/env python3
"""Compiled 65816 CPU unit tests for QUEUE323:
  1. Garo Mask Roc's Cape Glide (Masks/garo_mask.asm) + Garo regression checks
  2. Gust Jar (Items/gust_jar.asm) on logical item $1D ($7EF3AE) for Y & X
  3. Switch Hook Hookshot-trade gate preservation (Items/switch_hook.asm)
  4. Book of Secrets ownership fix (Items/book_of_secrets.asm:56 -> $7EF34E)

Executes real Asar-assembled 65816 bytes on Lakesnes' CPU core.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

LAKESNES_CANDIDATES = [
    Path(os.environ.get("OOS_LAKESNES", "")) if os.environ.get("OOS_LAKESNES") else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]


def find_lakesnes() -> Path:
    for p in LAKESNES_CANDIDATES:
        if p and (p / "snes/cpu.c").is_file():
            return p
    raise RuntimeError("Could not locate lakesnes (set OOS_LAKESNES)")


# Shared stubs for vanilla SNES services called by tested modules.
STUB_OAM_A = 0x0DBA80
STUB_OAM_B = 0x0DBA84
STUB_OAM_C = 0x0DBA88
STUB_OAM_D = 0x0DBA8C
STUB_OW_TILE_ACT = 0x1BBD7A
STUB_CANCEL_DASH = 0x0790B0
STUB_SPR_EXEC_SINGLE = 0x0684DA
STUB_SELECTED_ITEM = 0x548800


def _assemble_suite(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    # Build standalone fixture assembling our real source files cleanly.
    # For garo_mask.asm, strip the two pushpc vanilla ROM asserts ($079104, $06F633, $06ED8E)
    # or pre-populate those exact preimage bytes in the synthetic ROM image!
    # Pre-populating preimage bytes lets us assemble the UNMODIFIED source files directly!
    image = bytearray(b"\xFF" * 0x220000)

    def put_rom(snes_addr: int, data: bytes):
        pc = ((snes_addr >> 16) & 0x7F) * 0x8000 + (snes_addr & 0x7FFF)
        image[pc:pc + len(data)] = data

    # Preimages asserted by Masks/garo_mask.asm
    put_rom(0x079104, bytes.fromhex("AF C5 F3 7E"))
    put_rom(0x06F633, bytes.fromhex("BD AE F4 85 02 BD 30 F5"))
    put_rom(0x06ED8E, bytes.fromhex("BD 60 0E 29 40 D0 0A"))
    # Preimages asserted by Items/switch_hook.asm
    put_rom(0x0DB871, bytes.fromhex("9E 00 0F 9E 90 0E"))
    put_rom(0x08BD74, bytes.fromhex("A5 11"))
    put_rom(0x08BDD7, bytes.fromhex("20 68 8D"))
    put_rom(0x08BECA, bytes.fromhex("BD 5E 0C"))
    put_rom(0x0287E5, bytes.fromhex("C2 21 A5 E2"))
    put_rom(0x028053, bytes.fromhex("6B"))
    put_rom(0x02A5CC, bytes.fromhex("22 FA E3 00 20 90 BB"))
    # Preimages asserted by Items/gust_jar.asm (LinkOAM_ContinueWithAnimation, Sprite_Main, Ancilla_ExecuteAll)
    put_rom(0x0DA435, bytes.fromhex("8C 54 03 C0 05"))
    put_rom(0x0683A1, bytes.fromhex("8E A0 0F 20 E2 84"))
    put_rom(0x08832D, bytes.fromhex("8E A0 0F BD 4A 0C"))
    # Vanilla Sprite_ExecuteSingle_Long ($0684DA) stubbed by Q323Fixture (RTL = $6B)
    put_rom(0x0684DA, bytes.fromhex("6B"))
    # Preimages asserted by Items/bombchu.asm
    put_rom(0x098127, bytes.fromhex("AF 43 F3 7E"))
    put_rom(0x098133, bytes.fromhex("8F 43 F3 7E"))
    put_rom(0x008B56, bytes.fromhex("AE 34 01 8E 16 21"))
    put_rom(0x08A7D7, bytes.fromhex("BD 10 9D 00 00 00 BD 11 9D"))

    rom_path = folder / "fixture.sfc"
    rom_path.write_bytes(image)

    asm = folder / "fixture.asm"
    asm.write_text(f"""lorom
!DISABLE_SPRITES = 1
!DISABLE_ITEMS = 0
!ENABLE_GOLDSTAR_CELL = 1
!LOG_ITEMS = 0
macro log_end(name, flag)
endmacro
macro a8()
  SEP #$20
endmacro
macro a16()
  REP #$20
endmacro
macro m8()
  SEP #$20
endmacro
macro m16()
  REP #$20
endmacro
macro SelectedItem()
  JSL Test_SelectedItem
endmacro

; Shared RAM/SRAM symbols matching Core/sram.asm, Core/symbols.asm, Masks/all_masks.asm
!CurrentMask = $02B2
GaroGuardTimer = $07EE
GaroCounterTimer = $07EF
GaroCooldown = $07F0
GaroLungeTimer = $07FF
GaroMaskOwned = $7EF3AF
SwitchHookOwned = $7EF3AE
BombchuOwned = $7EF3B0
BombchuAmmo = $7EF3B1
GoldstarInventoryVersion = $7EF3AA
ItemBindingButton = $7E02B6
GameState = $7EF3C5
CameraCache = $7E0618
Link_CancelDash = ${STUB_CANCEL_DASH:06X}
Sprite_IceBlock = $D5
Sprite_SwapDiamond = $D6
!Stone_Marker = $E6
SprY = $0D00
SprX = $0D10
SprYH = $0D20
SprXH = $0D30
SprYSpeed = $0D40
SprXSpeed = $0D50
SprYRound = $0D60
SprXRound = $0D70
SprFrame = $0D90
SprState = $0DD0
SprTimerA = $0DF0
SprType = $0E20
SprSubtype = $0E30
SprNbrOAM = $0E40
SprHealth = $0E50
SprGfxProps = $0E60
SprRecoil = $0EA0
SprFloor = $0F20
SprYRecoil = $0F30
SprXRecoil = $0F40
SprHitbox = $0F60
SprHeight = $0F70
SprTimerF = $0F80
SprStunTimer = $0B58
SprDefl = $0CAA
SprMiscA = $0DA0
SprMiscC = $0DC0
SprDeath = $0E80
SprBulletproof = $0BA0
Stone_SwitchX = $2B8000
Stone_SwitchY = $2B8008
Ancilla_CheckSpriteCollision_long = $088D68
ApplyLinksMovementToCamera = $028053
Overworld_OperateCameraScroll_Long = $028053
SpriteSFX_QueueSFX2WithPan = $028053
Sprite_GetTileAttr = $028053

; Test-only SelectedItem helper: returns TestSelectedItem ($7E0260) if nonzero else $0202
org ${STUB_SELECTED_ITEM:06X}
Test_SelectedItem:
  LDA.l $7E0260 : BNE +
  LDA.l $7E0202
  +
  RTL

; Assemble real Masks/garo_mask.asm in Bank $42 (matching Masks/all_masks.asm)
org $42F000
incsrc "{(ROOT / 'Masks/garo_mask.asm').as_posix()}"

; Assemble real Items/book_of_secrets.asm in Bank $2B
org $2B8800
pushpc
incsrc "{(ROOT / 'Items/book_of_secrets.asm').as_posix()}"
; book_of_secrets ends with pushpc

; Assemble real Items/switch_hook.asm & Items/bombchu.asm in Bank $2B
incsrc "{(ROOT / 'Items/switch_hook.asm').as_posix()}"
pullpc
org $2BA000
incsrc "{(ROOT / 'Items/bombchu.asm').as_posix()}"

; Assemble real Items/gust_jar.asm in Bank $39 tail ($39F000-$39FFFF) & Bank $34 ($34E000-$34EFFF)
incsrc "{(ROOT / 'Items/gust_jar.asm').as_posix()}"
""")

    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla",
         f"-I{ROOT}", f"-I{ROOT / 'Masks'}",
         str(asm), str(rom_path)],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, f"asar failed:\n{res.stdout}\n{res.stderr}"
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$", rom_path.with_suffix(".sym").read_text())
    }
    return rom_path.read_bytes(), labels


class Q323Fixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.stubs = {
            STUB_OAM_A: "oam_a",
            STUB_OAM_B: "oam_b",
            STUB_OAM_C: "oam_c",
            STUB_OAM_D: "oam_d",
            STUB_OW_TILE_ACT: "ow_tile_act",
            STUB_CANCEL_DASH: "cancel_dash",
            STUB_SPR_EXEC_SINGLE: "spr_exec_single",
        }
        self.oam_allocs: list[int] = []
        self.oam_records: list[tuple[str, int, int, int]] = []  # (region, size, low_addr, hi_addr)
        self._oam_a_off = 0x0040
        self._oam_b_off = 0x01D0
        self._oam_c_off = 0x0000
        self._oam_d_off = 0x0030
        self.ow_cuts: list[tuple[int, int, int]] = []
        self.cancel_dash_calls = 0
        self.spr_exec_slots: list[int] = []
        self.cpu.db = 0x07  # Gameplay DBR mirror
        # SNES hardware register & DMA0 tracking for NMI VRAM upload tests
        self.hw_regs: dict[int, int] = {
            0x2116: 0, 0x2117: 0,
            0x4302: 0, 0x4303: 0, 0x4304: 0x7E,
            0x4305: 0, 0x4306: 0,
        }
        self.vram = bytearray(0x10000)
        self.dma_transfers: list[tuple[int, int, int, bytes]] = []  # (vram_word, src24, length, data)

    def write(self, a: int, v: int):
        bank = a >> 16
        lo = a & 0xFFFF
        if (bank & 0x7F) < 0x40 and lo in (0x2116, 0x2117, 0x4302, 0x4303, 0x4304, 0x4305, 0x4306, 0x420B):
            if lo == 0x420B:
                if v & 0x01:
                    vram_word = self.hw_regs[0x2116] | (self.hw_regs[0x2117] << 8)
                    src_lo = self.hw_regs[0x4302] | (self.hw_regs[0x4303] << 8)
                    src_bank = self.hw_regs[0x4304]
                    src24 = (src_bank << 16) | src_lo
                    length = self.hw_regs[0x4305] | (self.hw_regs[0x4306] << 8)
                    if length == 0:
                        length = 0x10000
                    payload = bytes(self.read(src24 + i) for i in range(length))
                    vaddr = (vram_word * 2) & 0xFFFF
                    self.vram[vaddr:vaddr + length] = payload
                    self.dma_transfers.append((vram_word, src24, length, payload))
            else:
                self.hw_regs[lo] = v & 0xFF
            return
        super().write(a, v)

    def run_nmi_jsl(self, label: str, a: int = 0xA5, x: int = 0x1234, y: int = 0x5678, limit: int = 60000):
        """Invoke an NMI handler matching vanilla $008B56 ABI: M=8, X=16, DBR=$00."""
        c = self.cpu
        c.mf = True
        c.xf = False
        c.a = a & 0xFF
        c.x = x & 0xFFFF
        c.y = y & 0xFFFF
        c.db = 0x00
        c.dp = 0
        self.dma_transfers.clear()
        entry = self.addr(label)
        assert entry is not None, f"Missing label {label}"
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        sentinel = (entry & 0xFF0000) | 0x7000
        for _ in range(limit):
            pc = (c.k << 16) | c.pc
            if pc == sentinel:
                assert c.sp == sp, f"{label}: stack imbalance {c.sp:#x} != {sp:#x}"
                assert not self.bad_writes, f"{label}: bad writes {self.bad_writes}"
                return
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{label}: exceeded {limit} opcodes at {pc:#08x}")

    def reset_oam_frame(self):
        self.oam_records.clear()
        self._oam_a_off = 0x0040
        self._oam_b_off = 0x01D0
        self._oam_c_off = 0x0000
        self._oam_d_off = 0x0030

    def read_oam_sprites(self, region: str | None = None) -> list[tuple[str, int, int, int, int, int]]:
        """Return list of (region, x, y, tile, attr, hi) for OAM records emitted since reset."""
        out = []
        for reg, size, lo, hi in self.oam_records:
            if region is not None and reg != region:
                continue
            for i in range(size // 4):
                x = self.get(lo + i * 4)
                y = self.get(lo + i * 4 + 1)
                tile = self.get(lo + i * 4 + 2)
                attr = self.get(lo + i * 4 + 3)
                h = self.get(hi + i)
                out.append((reg, x, y, tile, attr, h))
        return out

    def stub(self, name: str):
        if name == "oam_a":
            size = self.cpu.a & 0xFF
            self.oam_allocs.append(size)
            off = self._oam_a_off
            if off + size > 0x0170:
                off = 0x0040
            self._oam_a_off = off + size
            lo, hi = 0x0800 + off, 0x0A20 + (off >> 2)
            self.word(0x90, lo)
            self.word(0x92, hi)
            self.put(0x0E, size); self.put(0x0F, 0)
            self.cpu.y = lo & 0xFF
            self.oam_records.append(("A", size, lo, hi))
        elif name == "oam_b":
            size = self.cpu.a & 0xFF
            self.oam_allocs.append(size)
            off = self._oam_b_off
            if off + size > 0x0200:
                off = 0x01D0
            self._oam_b_off = off + size
            lo, hi = 0x0800 + off, 0x0A20 + (off >> 2)
            self.word(0x90, lo)
            self.word(0x92, hi)
            # Match vanilla $0DBB0A/$0DBB58: clobbers $0E/$0F and returns Y = $90 (non-zero!).
            self.put(0x0E, size); self.put(0x0F, 0)
            self.cpu.y = lo & 0xFF
            self.oam_records.append(("B", size, lo, hi))
        elif name == "oam_c":
            size = self.cpu.a & 0xFF
            self.oam_allocs.append(size)
            off = self._oam_c_off
            if off + size > 0x0030:
                off = 0x0000
            self._oam_c_off = off + size
            lo, hi = 0x0800 + off, 0x0A20 + (off >> 2)
            self.word(0x90, lo)
            self.word(0x92, hi)
            self.put(0x0E, size); self.put(0x0F, 0)
            self.cpu.y = lo & 0xFF
            self.oam_records.append(("C", size, lo, hi))
        elif name == "oam_d":
            size = self.cpu.a & 0xFF
            self.oam_allocs.append(size)
            off = self._oam_d_off
            if off + size > 0x00C0:
                off = 0x0030
            self._oam_d_off = off + size
            lo, hi = 0x0800 + off, 0x0A20 + (off >> 2)
            self.word(0x90, lo)
            self.word(0x92, hi)
            self.put(0x0E, size); self.put(0x0F, 0)
            self.cpu.y = lo & 0xFF
            self.oam_records.append(("D", size, lo, hi))
        elif name == "ow_tile_act":
            self.ow_cuts.append((self.get(0x0301), self.get(0x00) | (self.get(0x01) << 8),
                                 self.get(0x02) | (self.get(0x03) << 8)))
            self.put(0x76, 1)
        elif name == "cancel_dash":
            self.cancel_dash_calls += 1
            self.put(0x0372, 0)
        elif name == "spr_exec_single":
            self.spr_exec_slots.append(self.cpu.x & 0xFF)

    def run_jsl(self, label: str, a: int = 0, x: int = 0, y: int = 0, db: int = 0x07, limit: int = 60000):
        c = self.cpu
        c.mf = c.xf = True
        c.a = a & 0xFF
        c.x = x & 0xFF
        c.y = y & 0xFF
        c.db = db
        c.dp = 0
        entry = self.addr(label)
        assert entry is not None, f"Missing label {label}"
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        sentinel = (entry & 0xFF0000) | 0x7000
        for _ in range(limit):
            pc = (c.k << 16) | c.pc
            if pc == sentinel:
                assert c.sp == sp, f"{label}: stack imbalance {c.sp:#x} != {sp:#x}"
                assert not self.bad_writes, f"{label}: bad writes {self.bad_writes}"
                return c.a & 0xFF, bool(c.c), bool(c.z)
            if pc in self.stubs:
                self.stub(self.stubs[pc])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{label}: exceeded {limit} opcodes at {pc:#08x}")

    def signed8(self, addr: int) -> int:
        v = self.get(addr)
        return v - 256 if v >= 128 else v

    def word16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def set_word(self, addr: int, val: int):
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def setup_link(self, x: int = 0x0100, y: int = 0x0100, facing: int = 6, module: int = 7, indoors: int = 1):
        self.put(0x10, module)
        self.put(0x11, 0)
        self.put(0x1B, indoors)
        self.set_word(0x22, x)
        self.set_word(0x20, y)
        self.set_word(0xE2, max(0, x - 0x60))
        self.set_word(0xE8, max(0, y - 0x60))
        self.put(0x2F, facing)
        self.put(0xEE, 0)
        self.put(0x5D, 0)
        self.put(0x4D, 0)
        self.put(0x46, 0)
        self.put(0x6C, 0)
        self.put(0x24, 0)
        self.put(0x25, 0)

    def step_vanilla_recoil_physics(self):
        """Exact mirror of vanilla LinkState_Recoil ($0786B5) Z/XY integration and landing."""
        if self.get(0x5D) != 2:
            return
        # Link_HandleChangeInZVelocity ($078926): $29 -= 2 unless $29<0 and $24<=0
        z = self.signed8(0x24)
        vz = self.signed8(0x29)
        if vz < 0 and z <= 0:
            self.put(0x24, 0xFF)
            self.put(0x25, 0xFF)
            self.put(0x29, 0xFF)
        else:
            self.put(0x29, (vz - 2) & 0xFF)

        # Link_HandleRecoilAndTimer ($07871A)
        t = (self.get(0x46) - 1) & 0xFF
        self.put(0x46, t)
        landed = False
        if t == 0:
            self.put(0x46, 1)
            z_cur = self.signed8(0x24)
            vz_cur = self.signed8(0x29)
            if (z_cur <= 1) and vz_cur < 0:
                landed = True
        if landed:
            self.put(0x037B, 0)
            self.put(0x5D, 0)
            self.put(0x4D, 0)
            self.put(0x46, 0)
            self.put(0x24, 0)
            self.put(0x25, 0)
            self.put(0x27, 0)
            self.put(0x28, 0)
            return

        # LinkHop_FindArbitraryLandingSpot ($07E3A4): 1/16 fixed-point integration for Y($27), X($28), Z($29)
        for idx, (vel_addr, sub_addr, pos_addr) in enumerate(((0x27, 0x2A, 0x20), (0x28, 0x2B, 0x22), (0x29, 0x2C, 0x24))):
            v = self.get(vel_addr)
            lo_add = (v << 4) & 0xFF
            sub = self.get(sub_addr) + lo_add
            carry = 1 if sub >= 256 else 0
            self.put(sub_addr, sub & 0xFF)
            hi = v >> 4
            if hi >= 8:
                hi -= 16
            pos = self.word16(pos_addr)
            if idx == 2 and pos >= 0x8000:
                pos -= 0x10000
            new_pos = pos + hi + carry
            if idx == 2 and new_pos < 0:
                self.put(0x24, 0xFF)
                self.put(0x25, 0xFF)
            else:
                self.set_word(pos_addr, new_pos & 0xFFFF)

    def place_sprite(self, slot: int, stype: int, x: int, y: int, state: int = 9, health: int = 4,
                     frame: int = 0, subtype: int = 0, nbroam: int = 2, gfxprops: int = 0,
                     defl: int = 0, hitbox: int = 0, floor: int = 0, wall: int = 0):
        self.put(0x0DD0 + slot, state)
        self.put(0x0E20 + slot, stype)
        self.put(0x0E30 + slot, subtype)
        self.put(0x0D10 + slot, x & 0xFF)
        self.put(0x0D30 + slot, (x >> 8) & 0xFF)
        self.put(0x0D00 + slot, y & 0xFF)
        self.put(0x0D20 + slot, (y >> 8) & 0xFF)
        self.put(0x0E50 + slot, health)
        self.put(0x0D90 + slot, frame)
        self.put(0x0E40 + slot, nbroam)
        self.put(0x0E60 + slot, gfxprops)
        self.put(0x0CAA + slot, defl)
        self.put(0x0F60 + slot, hitbox)
        self.put(0x0F20 + slot, floor)
        self.put(0x0E70 + slot, wall)

    def place_ancilla(self, slot: int, aid: int, x: int, y: int, fuse_state: int = 0, lift: int = 0):
        self.put(0x0C4A + slot, aid)
        self.put(0x0C04 + slot, x & 0xFF)
        self.put(0x0C18 + slot, (x >> 8) & 0xFF)
        self.put(0x0BFA + slot, y & 0xFF)
        self.put(0x0C0E + slot, (y >> 8) & 0xFF)
        self.put(0x0C5E + slot, fuse_state)
        self.put(0x0380 + slot, lift)
        self.put(0x0C22 + slot, 0)
        self.put(0x0C2C + slot, 0)
        self.put(0x029E + slot, 0)


class TestQ323GustJarAndGaroGlide(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="oos-q323-cpu-")
        d = Path(cls.tmp.name)
        lakesnes = find_lakesnes()
        lib_path = d / "cpu.dylib"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2",
             str(lakesnes / "snes/cpu.c"),
             str(lakesnes / "snes/statehandler.c"),
             "-o", str(lib_path)],
            check=True,
        )
        cls.lib = C.CDLL(str(lib_path))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.rom, cls.labels = _assemble_suite(d / "build")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make_fx(self) -> Q323Fixture:
        fx = Q323Fixture(self.lib, self.rom, self.labels)
        self.addCleanup(fx.close)
        return fx

    # =========================================================================
    # DELIVERABLE 1: GARO MASK CAPE GLIDE + REGRESSION CHECKS
    # =========================================================================

    def _setup_garo(self, fx: Q323Fixture, facing: int = 6):
        fx.setup_link(x=0x0100, y=0x0100, facing=facing)
        fx.put(0x02B2, 0x08)       # !CurrentMask = Garo Master
        fx.put(0x7EF3AF, 0x01)     # GaroMaskOwned = 1
        fx.put(0x7EF359, 0x01)     # Sword owned

    def test_garo_glide_from_cape_hop_crosses_wide_gap_and_lands_clean(self):
        fx = self.make_fx()
        self._setup_garo(fx, facing=6)  # Facing Right
        # Start Lunge (hold Right + press Y)
        fx.put(0xF0, 0x41)
        fx.put(0xF4, 0x40)
        fx.run_jsl("GaroMask_Tick")
        self.assertEqual(fx.get(0x5D), 0x11)
        self.assertEqual(fx.get(0x07FF), 0x0E)

        # Frame 2 of lunge: press & hold Y -> triggers GaroMask_CapeHop
        fx.put(0xF4, 0x40)
        fx.put(0xF0, 0x40)
        fx.run_jsl("GaroMask_FrameTick")
        self.assertEqual(fx.get(0x5D), 0x02)
        self.assertEqual(fx.get(0x4D), 0x02)
        self.assertEqual(fx.get(0x0271), 0x00)  # Not yet at apex

        x0 = fx.word16(0x22)
        fx.put(0xF4, 0x00)
        glide_frames = 0
        saw_whoosh = False
        z_during_glide = []
        for frame in range(120):
            fx.put(0x1A, frame & 0xFF)
            fx.put(0xF0, 0x40)  # Keep holding Y
            fx.put(0x012E, 0)
            fx.run_jsl("GaroMask_FrameTick")
            if fx.get(0x0271) not in (0, 0x80):
                glide_frames += 1
                z_during_glide.append(fx.get(0x24))
                if fx.get(0x012E) == 0x07:
                    saw_whoosh = True
            fx.step_vanilla_recoil_physics()
            if fx.get(0x5D) == 0:
                break

        dx = fx.word16(0x22) - x0
        self.assertTrue(saw_whoosh, "Cape unfurl Fwoosh SFX ($07) must play")
        self.assertGreaterEqual(glide_frames, 48, f"Expected >=48 glide frames, got {glide_frames}")
        self.assertLessEqual(glide_frames, 56)
        self.assertGreaterEqual(dx, 80, f"Expected 4-8 tile glide (>=80 px), got {dx} px")
        self.assertLessEqual(dx, 136, f"Glide travel should stay bounded, got {dx} px")
        self.assertGreater(z_during_glide[0], z_during_glide[-1], "Glide must gently descend")
        self.assertGreater(len(fx.oam_allocs), 40, "Cape flutter OAM wisps must draw during glide")
        # Clean landing + next tick resets glide state to 0
        self.assertEqual((fx.get(0x5D), fx.get(0x4D), fx.get(0x037B)), (0, 0, 0))
        fx.put(0xF0, 0x00)
        fx.run_jsl("GaroMask_FrameTick")
        self.assertEqual(fx.get(0x0271), 0x00)

    def test_garo_glide_from_feather_jump_entry(self):
        fx = self.make_fx()
        self._setup_garo(fx, facing=6)
        # Simulate Roc's Feather jump state directly ($5D=2, $4D=2, $29=$24, $28=$10)
        fx.put(0x5D, 2); fx.put(0x4D, 2); fx.put(0x46, 0x20)
        fx.put(0x29, 0x24); fx.put(0x02C7, 0x24); fx.put(0x02C6, 3)
        fx.put(0x28, 0x10); fx.put(0x27, 0x00)
        x0 = fx.word16(0x22)
        entered_glide = False
        for frame in range(110):
            fx.put(0x1A, frame & 0xFF)
            fx.put(0xF0, 0x40)  # Hold Y while airborne from Feather
            fx.run_jsl("GaroMask_FrameTick")
            if 1 <= fx.get(0x0271) <= 52:
                entered_glide = True
            fx.step_vanilla_recoil_physics()
            if fx.get(0x5D) == 0:
                break
        dx = fx.word16(0x22) - x0
        self.assertTrue(entered_glide, "Holding Y during Feather hop must enter Garo Cape Glide")
        self.assertGreaterEqual(dx, 76, f"Feather->Glide should cross 4-6+ tiles, got {dx} px")
        self.assertEqual((fx.get(0x5D), fx.get(0x4D), fx.get(0x037B)), (0, 0, 0))

    def test_garo_glide_perpendicular_steering_all_facings(self):
        cases = [
            # (facing, dpad_bits, expect_vy, expect_vx)
            (6, 0x08, -6, 0x16),   # Right + Up
            (6, 0x04, +6, 0x16),   # Right + Down
            (4, 0x08, -6, -0x16),  # Left + Up
            (4, 0x04, +6, -0x16),  # Left + Down
            (0, 0x02, -0x16, -6),  # Up + Left
            (0, 0x01, -0x16, +6),  # Up + Right
            (2, 0x02, +0x16, -6),  # Down + Left
            (2, 0x01, +0x16, +6),  # Down + Right
        ]
        for facing, dpad, exp_vy, exp_vx in cases:
            with self.subTest(facing=facing, dpad=dpad):
                fx = self.make_fx()
                self._setup_garo(fx, facing=facing)
                fx.put(0x5D, 2); fx.put(0x4D, 2); fx.put(0x46, 0x10)
                fx.put(0x24, 0x12); fx.put(0x29, 0x02)  # At apex
                fx.put(0x6B, 0x0F)  # Stale corner collision bits must be cleared!
                fx.put(0xF0, 0x40 | dpad)
                fx.run_jsl("GaroMask_FrameTick")
                self.assertEqual(fx.signed8(0x27), exp_vy)
                self.assertEqual(fx.signed8(0x28), exp_vx)
                self.assertEqual(fx.get(0x29), 0xFE)  # Vanilla -2 -> $FC (-0.25 px/f)
                self.assertEqual(fx.get(0x6B), 0x00)
                self.assertLess(fx.get(0x46), 0x21)  # Ensures per-frame vanilla wall collision

    def test_garo_glide_early_release_drops_and_blocks_reglide(self):
        fx = self.make_fx()
        self._setup_garo(fx, facing=6)
        fx.put(0x5D, 2); fx.put(0x4D, 2); fx.put(0x46, 0x10)
        fx.put(0x24, 0x12); fx.put(0x29, 0x02)
        fx.put(0xF0, 0x40)
        fx.run_jsl("GaroMask_FrameTick")
        self.assertEqual(fx.get(0x0271), 52)
        self.assertEqual(fx.signed8(0x28), 0x16)

        # Release Y -> immediate cancel, gravity restored, carry halved, marked $80
        fx.put(0xF0, 0x00)
        fx.run_jsl("GaroMask_FrameTick")
        self.assertEqual(fx.get(0x0271), 0x80)
        self.assertEqual(fx.get(0x29), 0xF8)
        self.assertEqual(fx.signed8(0x28), 0x0B)

        # Holding Y again mid-fall MUST NOT re-engage glide!
        fx.put(0xF0, 0x40)
        fx.put(0x24, 0x0E)
        fx.put(0x29, 0xF6)
        fx.run_jsl("GaroMask_FrameTick")
        self.assertEqual(fx.get(0x0271), 0x80)
        self.assertEqual(fx.get(0x29), 0xF6)

    def test_garo_glide_aborts_on_doorway_transition_or_unmask(self):
        for field, val in ((0x6C, 1), (0x11, 5), (0x02B2, 0), (0x7EF3AF, 0)):
            with self.subTest(field=hex(field), val=val):
                fx = self.make_fx()
                self._setup_garo(fx)
                fx.put(0x5D, 2); fx.put(0x4D, 2); fx.put(0x24, 0x10); fx.put(0x29, 0x02)
                fx.put(0x0271, 30); fx.put(0x0272, 10)
                fx.put(field, val)
                fx.run_jsl("GaroMask_FrameTick")
                self.assertEqual(fx.get(0x0271), 0)
                self.assertEqual(fx.get(0x0272), 0)

    def test_garo_regression_parry_counter_backleap_and_tap_capehop(self):
        fx = self.make_fx()
        self._setup_garo(fx, facing=4)  # Facing Left
        # 1. Standing Y opens Guard
        fx.put(0xF0, 0x40); fx.put(0xF4, 0x40)
        fx.run_jsl("GaroMask_Tick")
        self.assertEqual(fx.get(0x07EE), 0x0C)  # GaroGuardTimer
        # 2. Contact Parry cancels damage & opens Counter window
        fx.put(0x0373, 0x08); fx.put(0x46, 0x10)
        fx.run_jsl("GaroMask_ParryContact")
        self.assertEqual(fx.get(0x0373), 0x00)
        self.assertEqual(fx.get(0x07EE), 0x00)
        self.assertEqual(fx.get(0x07EF), 0x20)  # GaroCounterTimer
        # 3. Counter Input converts Y into counter slash (bit 7)
        fx.put(0xF4, 0x40)
        fx.run_jsl("GaroMask_CounterInput")
        self.assertEqual(fx.get(0x07EF), 0x80)
        self.assertEqual(fx.get(0xF4) & 0x80, 0x80)

        # 4. Evasive Back-Leap (away tap during guard) uses $4D=1, NEVER triggers Glide
        fx2 = self.make_fx()
        self._setup_garo(fx2, facing=4)  # Facing Left
        fx2.put(0x07EE, 0x0A)            # Guard open
        fx2.put(0xF4, 0x01)              # Tap Right (away)
        fx2.run_jsl("GaroMask_Tick")
        self.assertEqual(fx2.get(0x4D), 0x01)
        self.assertEqual(fx2.get(0x037B), 0x01)
        self.assertEqual(fx2.get(0x0271), 0x00)  # Not glide!

        # 5. Plain CapeHop (tap Y, do NOT hold at apex) never triggers Glide
        fx3 = self.make_fx()
        self._setup_garo(fx3, facing=6)
        fx3.put(0xF0, 0x41); fx3.put(0xF4, 0x40)
        fx3.run_jsl("GaroMask_Tick")
        fx3.put(0xF4, 0x40); fx3.put(0xF0, 0x40)
        fx3.run_jsl("GaroMask_FrameTick")
        fx3.put(0xF4, 0x00); fx3.put(0xF0, 0x00)
        for frame in range(50):
            fx3.run_jsl("GaroMask_FrameTick")
            self.assertEqual(fx3.get(0x0271), 0x00)
            fx3.step_vanilla_recoil_physics()
            if fx3.get(0x5D) == 0:
                break
        self.assertEqual(fx3.get(0x5D), 0x00)

    # =========================================================================
    # DELIVERABLE 2: GUST JAR ($1D / $7EF3AE)
    # =========================================================================

    def _start_gust(self, fx: Q323Fixture, button: int = 1, facing: int = 6, indoors: int = 1):
        fx.setup_link(x=0x0100, y=0x0100, facing=facing, module=7 if indoors else 9, indoors=indoors)
        fx.put(0x7EF3AE, 0x01)  # GustJarOwned = SwitchHookOwned = 1
        fx.put(0x0202, 0x1D)
        fx.put(0x7E02B6, button)  # ItemBindingButton (1=Y, 2=X)
        fx.put(0x3A, 0x40)        # Claimed by CheckYButtonPress
        if button == 2:
            fx.put(0xF2, 0x40)
            fx.put(0xF0, 0x00)
        else:
            fx.put(0xF0, 0x40)
            fx.put(0xF2, 0x00)
        fx.run_jsl("GustJar_Start")

    def test_gust_jar_y_and_x_hold_and_release_lifecycle(self):
        for btn, held_reg, other_reg in ((1, 0xF0, 0xF2), (2, 0xF2, 0xF0)):
            with self.subTest(button="Y" if btn == 1 else "X"):
                fx = self.make_fx()
                self._start_gust(fx, button=btn, facing=6)
                self.assertEqual(fx.get(0x0273), 1)    # Inhaling
                self.assertEqual(fx.get(0x0274), btn)  # Button latched
                self.assertEqual(fx.get(0x5E), 0x0E)   # Tier 1 slow strafe stance
                self.assertEqual(fx.get(0x50) & 0x01, 0x01)  # Facing locked

                # Holding latched button advances charge while ignoring the other button
                for i in range(6):
                    fx.put(0x1A, i)
                    fx.put(held_reg, 0x40)
                    fx.put(other_reg, 0x00)
                    fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 1)
                self.assertEqual(fx.get(0x0275), 6)
                self.assertEqual(fx.get(0x3A) & 0x40, 0x40)

                # Releasing latched button (even if the other button is pressed!) fires Blast!
                fx.put(held_reg, 0x00)
                fx.put(other_reg, 0x40)
                fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 2)     # Blast Wave active!
                self.assertEqual(fx.get(0x012E), 0x07)  # Fwoosh SFX!
                self.assertGreater(fx.get(0x027A), 0)   # Wave timer active
                self.assertEqual(fx.get(0x027F) & 0x0C, 0x0C)  # Follow-through pose + recoil peak!

                # After follow-through, $3A bit 6, $50 bit 0 & $5E release while wave finishes flying
                for i in range(20):
                    fx.put(0x1A, 10 + i)
                    fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 0)
                self.assertEqual(fx.get(0x3A) & 0x40, 0)
                self.assertEqual(fx.get(0x50) & 0x01, 0)
                self.assertEqual(fx.get(0x5E), 0)
                self.assertEqual(fx.get(0x02E3), 0)

    def test_gust_jar_three_charge_tiers_and_wind_signal_hook(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        # Idle before start check on separate fixture
        fx_idle = self.make_fx()
        a, c, z = fx_idle.run_jsl("GustJar_WindSignal")
        self.assertEqual((a, c, z), (0, False, True))

        # Tier 1 -> Tier 2 at charge $18 -> Tier 3 at charge $38
        tiers_seen = set()
        for f in range(0x40):
            fx.put(0x1A, f)
            fx.run_jsl("GustJar_FrameTick")
            tiers_seen.add(fx.get(0x0276))
        self.assertEqual(tiers_seen, {1, 2, 3})
        self.assertEqual(fx.get(0x0276), 3)
        self.assertEqual(fx.get(0x027F) & 0x01, 0x01)  # Public wind signal bit
        a, c, z = fx.run_jsl("GustJar_WindSignal")
        self.assertEqual((a, c, z), (3, False, False))

        # Release at Tier 3 -> Wave timer = 26, WindSignal carry = True
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x027A), 26)
        a, c, z = fx.run_jsl("GustJar_WindSignal")
        self.assertEqual((a, c, z), (3, True, False))

    def test_gust_jar_all_four_directions_pickup_vacuum_and_cone_filter(self):
        # (facing, in_cone_offset, behind_offset)
        dir_cases = [
            (0, (0, -32), (0, +32)),   # Up
            (2, (0, +32), (0, -32)),   # Down
            (4, (-32, 0), (+32, 0)),   # Left
            (6, (+32, 0), (-32, 0)),   # Right
        ]
        for facing, (ix, iy), (bx, by) in dir_cases:
            with self.subTest(facing=facing):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=facing)
                # Rupee ($D9) inside cone, Heart ($D8) behind Link
                fx.place_sprite(0, 0xD9, 0x100 + ix, 0x100 + iy)
                fx.place_sprite(1, 0xD8, 0x100 + bx, 0x100 + by)
                for i in range(4):
                    fx.put(0x1A, i)
                    fx.run_jsl("GustJar_FrameTick")
                rx = fx.get(0x0D10) | (fx.get(0x0D30) << 8)
                ry = fx.get(0x0D00) | (fx.get(0x0D20) << 8)
                # Must have moved strictly closer to Link (0x100, 0x104) by ~8 px in 4 frames
                dist_before = abs((0x100 + ix) - 0x100) + abs((0x100 + iy) - 0x104)
                dist_after = abs(rx - 0x100) + abs(ry - 0x104)
                self.assertLessEqual(dist_after, dist_before - 6)
                # Behind pickup MUST NOT move!
                hx = fx.get(0x0D11) | (fx.get(0x0D31) << 8)
                hy = fx.get(0x0D01) | (fx.get(0x0D21) << 8)
                self.assertEqual((hx, hy), (0x100 + bx, 0x100 + by))

    def test_gust_jar_bomb_pull_capture_and_launch(self):
        fx = self.make_fx()
        self._start_gust(fx, button=2, facing=6)  # Triggered via X!
        # Active Bomb ($07) 34 px to the right of Link
        fx.place_ancilla(0, 0x07, 0x12A, 0x10A)
        for i in range(15):
            fx.put(0x1A, i)
            fx.run_jsl("GustJar_FrameTick")
            if fx.get(0x0278) == 2:
                break
        self.assertEqual(fx.get(0x0278), 2, "Bomb must be captured at nozzle")
        self.assertEqual(fx.get(0x0279), 0)
        self.assertEqual(fx.get(0x029E), 4)  # Lifted slightly at nozzle

        # Release X -> launches bomb briskly right with airborne arc
        fx.put(0xF2, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0273), 2)
        self.assertGreaterEqual(fx.signed8(0x0C2C), 0x38)  # Positive X velocity!
        self.assertEqual(fx.get(0x029E), 0x0A)             # Airborne arc!

    def test_gust_jar_somaria_block_and_statue_pull_and_blast_push(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        # Movable Statue ($1C, frame 0), Elegy of Stone ($1C, frame $E6), and Somaria Block ($2C)
        fx.place_sprite(0, 0x1C, 0x128, 0x102, frame=0)
        fx.place_sprite(1, 0x1C, 0x128, 0x102, frame=0xE6)
        fx.place_ancilla(0, 0x2C, 0x12C, 0x10A)
        fx.put(0x0642, 1)

        # Inhale 3 frames -> movable statue & Somaria pull left toward Link; Stone echo unmoved!
        for i in range(3):
            fx.put(0x1A, i)
            fx.run_jsl("GustJar_FrameTick")
        sx_in = fx.get(0x0D10) | (fx.get(0x0D30) << 8)
        stone_x = fx.get(0x0D11) | (fx.get(0x0D31) << 8)
        som_in = fx.get(0x0C04) | (fx.get(0x0C18) << 8)
        self.assertLess(sx_in, 0x128)
        self.assertEqual(stone_x, 0x128, "Elegy of Stone echo must never be moved")
        self.assertLess(som_in, 0x12C)
        self.assertEqual(fx.get(0x0642), 0, "Statue pull must clear $0642 for plate re-eval")

        # Release -> Gust Wave pushes statue & Somaria forward (right)!
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        for i in range(8):
            fx.put(0x1A, 10 + i)
            fx.run_jsl("GustJar_FrameTick")
        sx_out = fx.get(0x0D10) | (fx.get(0x0D30) << 8)
        som_out = fx.get(0x0C04) | (fx.get(0x0C18) << 8)
        self.assertGreater(sx_out, sx_in)
        self.assertGreater(som_out, som_in)
        self.assertEqual(fx.get(0x0D11) | (fx.get(0x0D31) << 8), 0x128)

    def test_gust_jar_enemy_capture_launch_deals_impact_damage(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        # Light enemy (slot 0, HP=4) near nozzle; second enemy (slot 1, HP=4) ahead at 0x130
        fx.place_sprite(0, 0x0D, 0x114, 0x102, health=4)  # Buzzblob
        fx.place_sprite(1, 0x12, 0x132, 0x102, health=4)  # Moblin target
        # Charge to Tier 2 while capturing slot 0
        for i in range(0x1A):
            fx.put(0x1A, i)
            fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0278), 1)   # Captured sprite!
        self.assertEqual(fx.get(0x0279), 0)
        self.assertEqual(fx.get(0x0DD0), 0x0B)  # Stun-frozen while captured

        # Release at Tier 2 -> launches slot 0 right into slot 1 (4 dmg = kill -> state 6!)
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x027F) & 0x02, 0x02)
        for i in range(10):
            fx.put(0x1A, 0x20 + i)
            fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0E51), 0, "Launched enemy must damage/kill target enemy")
        self.assertEqual(fx.get(0x0DD1), 6, "Killed target enemy must enter death module 6")

    def test_gust_jar_boss_and_npc_excluded_and_projectiles_deflected(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        # Slot 0: Boss (invulnerable bit $40)
        fx.place_sprite(0, 0x09, 0x120, 0x102, health=10, gfxprops=0x40)
        # Slot 1: Harmless NPC (nbroam bit $80)
        fx.place_sprite(1, 0x10, 0x120, 0x102, health=4, nbroam=0x82)
        # Slot 2: High-HP miniboss (HP=$20)
        fx.place_sprite(2, 0x12, 0x120, 0x102, health=0x20)
        # Slot 3: Normal pullable enemy (HP=10, too heavy to capture but gets knocked back)
        fx.place_sprite(3, 0x12, 0x122, 0x102, health=10)
        # Slot 4: Octorok Stone projectile ($0C)
        fx.place_sprite(4, 0x0C, 0x124, 0x102, health=0, nbroam=0x80)
        # Slot 5: Enemy Arrow ($1B)
        fx.place_sprite(5, 0x1B, 0x124, 0x102, health=0, nbroam=0x80)

        fx.run_jsl("GustJar_FrameTick")
        # Boss, NPC, miniboss MUST NOT move or be captured
        for s in (0, 1, 2):
            self.assertEqual(fx.get(0x0D10 + s) | (fx.get(0x0D30 + s) << 8), 0x120)
        # Normal enemy pulled left
        self.assertLess(fx.get(0x0D13) | (fx.get(0x0D33) << 8), 0x122)

        # Release -> Gust Wave deflects projectiles & knocks back normal enemy, never bosses/NPCs!
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        for i in range(6):
            fx.put(0x1A, i + 1)
            fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0DD4), 0, "Octorok stone must be cleared by Gust Wave")
        self.assertEqual(fx.get(0x0DD5), 0, "Enemy arrow must be cleared by Gust Wave")
        self.assertGreater(fx.signed8(0x0F43), 0, "Normal enemy must receive right knockback recoil")
        self.assertEqual(fx.get(0x0DD3), 0x0B, "Normal enemy must be briefly stunned")
        for s in (0, 1, 2):
            self.assertEqual(fx.get(0x0F40 + s), 0, f"Protected slot {s} must not receive recoil")

    def test_gust_jar_blasts_bomb_and_somaria_through_portal_rod_nodes(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        # Orange Portal (slot 2, subtype 1) at (0x124, 0x10A), Blue Portal (slot 3, subtype 2) at (0x180, 0x150)
        fx.place_sprite(2, 0x03, 0x124, 0x10A, subtype=1, nbroam=0x80, gfxprops=0x40)
        fx.place_sprite(3, 0x03, 0x180, 0x150, subtype=2, nbroam=0x80, gfxprops=0x40)
        fx.put(0x0632, 3)  # BlueSpriteIndex
        fx.put(0x0633, 2)  # OrangeSpriteIndex
        # Somaria Block ($2C) right in front of Orange Portal
        fx.place_ancilla(0, 0x2C, 0x11C, 0x10A)
        # Release immediately -> Wave pushes Somaria into Orange Portal -> warps to BlueX+16, BlueY!
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        for i in range(6):
            fx.put(0x1A, i)
            fx.run_jsl("GustJar_FrameTick")
        sx = fx.get(0x0C04) | (fx.get(0x0C18) << 8)
        sy = fx.get(0x0BFA) | (fx.get(0x0C0E) << 8)
        self.assertEqual((sx, sy), (0x190, 0x150), "Somaria pushed into Orange portal must exit BlueX+16, BlueY")

    def test_gust_jar_cuts_overworld_bushes_at_tier2(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6, indoors=0)
        # Set $7E2000 tilemap lookup masks to simple identity slot 0 with green bush $0036
        fx.set_word(0x0708, 0); fx.set_word(0x070A, 0)
        fx.set_word(0x070C, 0); fx.set_word(0x070E, 0)
        fx.set_word(0x7E2000, 0x0036)
        fx.put(0x0301, 0xAA); fx.put(0x037A, 0x55)  # Must be preserved across cut!
        # Advance to Tier 2 ($18)
        for i in range(0x19):
            fx.put(0x1A, i)
            fx.run_jsl("GustJar_FrameTick")
        self.assertGreaterEqual(len(fx.ow_cuts), 1, "Tier 2 suction must invoke Overworld bush cut")
        self.assertEqual(fx.ow_cuts[0][0], 0x02)  # Sword/cut class
        self.assertEqual(fx.get(0x0301), 0xAA)
        self.assertEqual(fx.get(0x037A), 0x55)

    def test_gust_jar_safety_aborts_cleanly_on_interrupts(self):
        interrupts = [
            ("transition", 0x11, 0x05),
            ("damage_recoil", 0x5D, 0x02),
            ("swimming", 0x5D, 0x04),
            ("damage_timer", 0x46, 0x10),
            ("doorway", 0x6C, 0x01),
            ("menu_locked", 0x0FFC, 0x01),
            ("form_change", 0x02B2, 0x01),
        ]
        for label, addr, val in interrupts:
            with self.subTest(interrupt=label):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=6)
                fx.place_sprite(0, 0x0D, 0x114, 0x102, health=4)
                fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 1)
                fx.put(addr, val)
                fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 0, f"{label} must abort Gust Jar")
                self.assertEqual(fx.get(0x3A) & 0x40, 0, f"{label} must clear $3A bit 6")
                self.assertEqual(fx.get(0x50) & 0x01, 0, f"{label} must unlock facing $50 bit 0")
                self.assertEqual(fx.get(0x5E), 0, f"{label} must clear slow-walk $5E")
                self.assertEqual(fx.get(0x02E3), 0, f"{label} must clear sword hold $02E3")
                self.assertEqual(fx.get(0x0F70), 0, f"{label} must ground any captured sprite")

    def test_gust_jar_facing_lock_strafe_speed_and_blast_follow_through(self):
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)  # Start facing Right
        self.assertEqual(fx.get(0x50) & 0x01, 0x01)
        self.assertEqual(fx.get(0x5E), 0x0E)
        self.assertEqual(fx.get(0x02E3), 2)

        # Simulate sideways/backwards movement attempting to turn Link Left ($2F=4):
        # Gust Jar must keep Link's facing locked to Right (6) for Minish Cap strafing!
        for i in range(0x18):
            fx.put(0x1A, i)
            fx.put(0x2F, 4)  # External facing perturbation
            fx.run_jsl("GustJar_FrameTick")
            self.assertEqual(fx.get(0x2F), 6, "Facing must stay locked to !GustJarDir during inhale")
            self.assertEqual(fx.get(0x50) & 0x01, 0x01)
            self.assertEqual(fx.get(0x02E3), 2)
        # At Tier 2 ($18 frames), slow strafe deepens to heavy braced footing ($5E=$06)
        self.assertEqual(fx.get(0x0276), 2)
        self.assertEqual(fx.get(0x5E), 0x06)

        # Release Y -> fires Tier 2 blast (WaveLife=20) with 7-frame recoil follow-through
        fx.put(0xF0, 0x00)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0273), 2)
        self.assertEqual(fx.get(0x027A), 20)
        self.assertEqual(fx.get(0x027F) & 0x0C, 0x0C)  # pose + recoil peak active

        # Frames 0..3 of follow-through: peak kickback bit 3 stays set, facing locked
        for f in range(4):
            fx.put(0x1A, 30 + f)
            fx.put(0x2F, 2)
            fx.run_jsl("GustJar_FrameTick")
            self.assertEqual(fx.get(0x2F), 6)
            self.assertEqual(fx.get(0x027F) & 0x0C, 0x0C, f"Peak recoil expected on elapsed={f}")

        # Frames 4..6 of follow-through: peak bit 3 clears -> planted recovery (bit 2 still set)
        for f in range(4, 7):
            fx.put(0x1A, 30 + f)
            fx.run_jsl("GustJar_FrameTick")
            self.assertEqual(fx.get(0x027F) & 0x0C, 0x04, f"Recovery pose expected on elapsed={f}")
            self.assertEqual(fx.get(0x50) & 0x01, 0x01)

        # Frame 7: pose/facing/speed/sword lock release cleanly while blast wave keeps flying!
        fx.put(0x1A, 40)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0273), 2, "Wave must still be flying after follow-through")
        self.assertEqual(fx.get(0x027F) & 0x0C, 0)
        self.assertEqual(fx.get(0x3A) & 0x40, 0)
        self.assertEqual(fx.get(0x50) & 0x01, 0)
        self.assertEqual(fx.get(0x5E), 0)
        self.assertEqual(fx.get(0x02E3), 0)

        # If Link immediately starts charging sword ($50=1, $5E=$0C) while wave finishes,
        # wave expiry MUST NOT clobber Link's new sword facing lock or speed!
        fx.put(0x50, 0x01)
        fx.put(0x5E, 0x0C)
        for f in range(15):
            fx.put(0x1A, 50 + f)
            fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0273), 0)
        self.assertEqual(fx.get(0x50), 0x01, "Wave expiry must not stomp new sword facing lock")
        self.assertEqual(fx.get(0x5E), 0x0C, "Wave expiry must not stomp new sword speed")

        # Cannot start Gust Jar mid-sword-swing ($3C != 0)
        fx2 = self.make_fx()
        fx2.setup_link(x=0x100, y=0x100, facing=2)
        fx2.put(0x7EF3AE, 1); fx2.put(0x3C, 3); fx2.put(0x3A, 0x40)
        fx2.run_jsl("GustJar_Start")
        self.assertEqual(fx2.get(0x0273), 0)
        self.assertEqual(fx2.get(0x3A) & 0x40, 0)

    def test_gust_jar_link_pose_oam_hook_all_states_and_passthrough(self):
        fx = self.make_fx()
        # 1. Idle passthrough: preserves Y, writes $0354, and Z flag matches CPY #$05
        fx.put(0x0273, 0)
        _, _, z5 = fx.run_jsl("GustJar_LinkPoseOamHook", y=0x05, db=0x0D)
        self.assertEqual(fx.get(0x0354), 0x05)
        self.assertTrue(z5, "Idle CPY #$05 must set Z=1 when Y==5")
        _, _, z0 = fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
        self.assertEqual(fx.get(0x0354), 0x00)
        self.assertFalse(z0, "Idle CPY #$05 must set Z=0 when Y==0")

        # 2. Inhale pose: Up/Down -> $0E (symmetrical hold), Left/Right -> $16, walk $2E wraps mod 6
        for facing, exp_pose in ((0, 0x0E), (2, 0x0E), (4, 0x16), (6, 0x16)):
            with self.subTest(phase="inhale", facing=facing):
                fx.put(0x0273, 1); fx.put(0x027F, 0x04); fx.put(0x5D, 0); fx.put(0x02E0, 0)
                fx.put(0x2F, facing); fx.put(0x2E, 7)  # $2E=7 wraps -> frame 1
                _, _, z = fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                self.assertEqual(fx.get(0x0354), exp_pose)
                self.assertEqual(fx.get(0x02), 1)
                self.assertFalse(z)

        # Planted Tier 2/3 brace pulse toggles $02 between 0 and 1 on charge bit 3
        fx.put(0x2F, 6); fx.put(0x2E, 0); fx.put(0x0276, 2)
        fx.put(0x0275, 0x18)  # bit 3 set
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
        self.assertEqual(fx.get(0x02), 1)
        fx.put(0x0275, 0x20)  # bit 3 clear
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
        self.assertEqual(fx.get(0x02), 0)

        # 3. Blast follow-through recoil ($18): peak -> frame 1 on D/L/R, frame 0 on Up; recovery -> frame 0
        fx.put(0x0273, 2); fx.put(0x027F, 0x0D)  # bit2+bit3 recoil peak
        for facing, exp_fr in ((0, 0), (2, 1), (4, 1), (6, 1)):
            fx.put(0x2F, facing)
            fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
            self.assertEqual(fx.get(0x0354), 0x18)
            self.assertEqual(fx.get(0x02), exp_fr)
        fx.put(0x027F, 0x05); fx.put(0x2F, 6)  # recovery (bit3 clear)
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
        self.assertEqual(fx.get(0x0354), 0x18)
        self.assertEqual(fx.get(0x02), 0)

        # 4. Bunny ($02E0!=0) or special LinkState ($5D!=0) must NOT be overridden
        fx.put(0x02E0, 1)
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x21, db=0x0D)
        self.assertEqual(fx.get(0x0354), 0x21)
        fx.put(0x02E0, 0); fx.put(0x5D, 2)
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x05, db=0x0D)
        self.assertEqual(fx.get(0x0354), 0x05)

        # 5. Live OAM render inside GustJar_LinkPoseOamHook MUST preserve ALL of
        #    LinkOAM's zero-page $00..$0F (screen coords in $00/$01, etc.), X, and DBR!
        fx_dp = self.make_fx()
        self._start_gust(fx_dp, button=1, facing=6)
        fx_dp.put(0x1A, 3)
        fx_dp.run_jsl("GustJar_FrameTick")
        sentinel_dp = [0xA0 + i for i in range(16)]
        for i, val in enumerate(sentinel_dp):
            fx_dp.put(i, val)
        fx_dp.run_jsl("GustJar_LinkPoseOamHook", x=0x77, y=0x00, db=0x0D)
        self.assertEqual(fx_dp.cpu.x & 0xFF, 0x77, "LinkPoseOamHook must preserve X")
        self.assertEqual(fx_dp.cpu.db, 0x0D, "LinkPoseOamHook must preserve DBR=$0D")
        for i, val in enumerate(sentinel_dp):
            if i == 2:
                continue  # $02 is intentionally updated with Link's pose frame index
            self.assertEqual(fx_dp.get(i), val, f"LinkPoseOamHook clobbered LinkOAM DP ${i:02X}")

    def test_gust_jar_visible_held_jar_oam_all_dirs_priority_tremble_and_glow(self):
        # Verify custom 16x16 held Minish Cap Gust Jar (tile $07, hi=$02) across all 4 directions
        # + Region B (Up, behind Link) vs Region C (D/L/R, top-priority in front of Link & Ancilla!)
        # + custom Minish Cap mouth sheen ($1A L/R, $19 Down)
        # + ZERO recycled Small Magic Jar ($72) or Portal Rod ($EE) tiles!
        dir_expect = [
            (0, "B", 0x60 + 0, 0x60 - 11, 0x00, None),   # Up: behind Link in Region B, no H-flip
            (2, "C", 0x60 + 0, 0x60 + 15, 0x00, 0x19),   # Down: top-priority in Region C, $19 curl sheen
            (4, "C", 0x60 - 12, 0x60 + 8, 0x40, 0x1A),   # Left: held clear of face, H-flipped, $1A sheen
            (6, "C", 0x60 + 12, 0x60 + 8, 0x00, 0x1A),   # Right: held clear of face, no H-flip, $1A sheen
        ]
        for facing, exp_reg, exp_x, exp_y, exp_hflip, exp_mouth in dir_expect:
            with self.subTest(facing=facing):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=facing)
                fx.reset_oam_frame()
                # Pre-dirty high OAM bytes with $FF to verify exact 8x8 ($00) vs 16x16 ($02) writes!
                for hi_addr in range(0x0A20, 0x0AA0):
                    fx.put(hi_addr, 0xFF)
                fx.put(0x1A, 0)
                fx.run_jsl("GustJar_FrameTick")
                fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                all_sprs = fx.read_oam_sprites()
                for s in all_sprs:
                    self.assertNotIn(s[3], (0x72, 0xEE), f"Forbidden recycled tile {s[3]:#04x} emitted")
                reg_sprites = fx.read_oam_sprites(exp_reg)
                jar_sprites = [s for s in reg_sprites if s[3] == 0x07]
                self.assertEqual(len(jar_sprites), 1, f"Expected 1 held Minish Jar ($07) in Region {exp_reg}")
                _, jx, jy, jtile, jattr, jhi = jar_sprites[0]
                self.assertEqual((jx, jy), (exp_x, exp_y))
                self.assertEqual(jattr & 0x0E, 0x08, "Tier 1 jar must use emerald/gold OAM Palette 4 ($08)")
                self.assertEqual(jattr & 0x40, exp_hflip)
                self.assertEqual(jattr & 0x30, 0x20, "Normal floor ($EE=0) uses BG prio 2 ($20)")
                self.assertEqual(jhi, 0x02, "Held Minish Cap Gust Jar must be 16x16 ($02)")
                if exp_mouth is not None:
                    self.assertEqual(reg_sprites[0][3], exp_mouth, "Expected custom Minish Cap nozzle sheen")
                    self.assertEqual(reg_sprites[0][5], 0x00, "Mouth sheen slot 0 must be 8x8 ($00)")

        # Verify smooth left-edge clipping when facing Left at LinkScreenX=4 (jar_sx = 4 - 12 = -8 -> $F8, hi=$03!)
        fx_edge = self.make_fx()
        self._start_gust(fx_edge, button=1, facing=4)
        fx_edge.set_word(0xE2, 0x00FC)  # LinkX=0x100 -> screenX=4, jar_sx = 4 - 12 = -8 ($F8)
        fx_edge.reset_oam_frame()
        fx_edge.run_jsl("GustJar_FrameTick")
        fx_edge.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
        jar_edge = [s for s in fx_edge.read_oam_sprites("C") if s[3] == 0x07][0]
        self.assertEqual(jar_edge[1], 0xF8)
        self.assertEqual(jar_edge[5], 0x03, "Left-edge overhang must use 16x16 + X-msb=1 ($03)")

        # Verify Tier 3 / Full holds the swollen jar 2px further forward (Right: 0x60+12+2 = 0x6E)
        # + rapid +/-1px tremble AND Pal 4 <-> Pal 2 pulsing glow
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        fx.put(0x0275, 0x40)  # Tier 3 charge
        ys_seen, pals_seen = set(), set()
        for f in (0, 2, 4, 6):
            fx.reset_oam_frame()
            fx.put(0x1A, f)
            fx.run_jsl("GustJar_FrameTick")
            fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
            jar = [s for s in fx.read_oam_sprites("C") if s[3] == 0x07][0]
            self.assertEqual(jar[1], 0x60 + 14, "Full/swollen jar must shift +2px further out of Link's face")
            ys_seen.add(jar[2])
            pals_seen.add(jar[4] & 0x0E)
        self.assertEqual(ys_seen, {0x60 + 8 - 1, 0x60 + 8 + 1}, "Tier 3 must rumble +/-1px on Y when facing Right")
        self.assertEqual(pals_seen, {0x04, 0x08}, "Tier 3 must pulse between Pal 4 (emerald) and Pal 2 (wind glow)")

        # Verify Blast Peak 2px recoil kickback + Pal 2 flash + muzzle burst ($A9)
        # starts immediately on frame 0 (FireBlast release frame — zero 1-frame flicker!)
        fx.reset_oam_frame()
        fx.put(0xF0, 0x00)
        fx.put(0x1A, 1)
        fx.run_jsl("GustJar_FrameTick")  # enters state 2
        fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)  # renders frame-0 recoil + wave!
        jar_f0 = [s for s in fx.read_oam_sprites("C") if s[3] == 0x07]
        self.assertEqual(len(jar_f0), 1, "Frame-0 release must draw held jar ($07) without 1-frame blink")
        self.assertEqual(jar_f0[0][1], 0x60 + 12 - 2, "Blast peak must kick jar 2px back toward Link")
        self.assertEqual(jar_f0[0][4] & 0x0E, 0x04, "Blast peak must flash Pal 2")
        self.assertEqual(jar_f0[0][5], 0x02, "Held jar stays 16x16 during blast peak")
        self.assertEqual(fx.read_oam_sprites("C")[0][3], 0xA9, "Blast peak must emit $A9 muzzle burst")

    def test_gust_jar_minish_inhale_funnel_and_crescent_wave_oam(self):
        # 1. Inhale OAM scales 4 / 5 / 6 wind sprites across Tier 1 / 2 / 3 using ONLY
        #    our dedicated custom Minish Cap Inhale Wind Set ($09, $0A, $19, $1A)!
        mc_inhale_tiles = {0x09, 0x0A, 0x19, 0x1A}
        for charge, exp_tier, exp_wind_cnt in ((0x04, 1, 4), (0x1A, 2, 5), (0x40, 3, 6)):
            with self.subTest(inhale_tier=exp_tier):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=6)
                fx.put(0x0275, charge)
                fx.reset_oam_frame()
                fx.put(0x1A, 5)
                fx.run_jsl("GustJar_FrameTick")
                fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                self.assertEqual(len(fx.oam_records), 2)
                self.assertEqual(fx.oam_records[0][0], "C")
                self.assertEqual(fx.oam_records[0][1], 8)
                self.assertEqual(fx.oam_records[1][0], "A")
                self.assertEqual(fx.oam_records[1][1], exp_wind_cnt * 4)
                wind_sprs = fx.read_oam_sprites("A")
                self.assertEqual(len(wind_sprs), exp_wind_cnt)
                for _, x, y, tile, attr, hi in wind_sprs:
                    self.assertIn(tile, mc_inhale_tiles, f"Expected custom Minish inhale tile, got {tile:#04x}")
                    self.assertEqual(attr & 0x0E, 0x04, "Wind particles must use OAM Pal 2 ($04)")
                    self.assertEqual(hi, 0x00)
                # Horizontal inhale streaks ($09) when facing Right must H-flip ($40) to point inward Left!
                h_streaks = [s for s in wind_sprs if s[3] == 0x09]
                self.assertGreaterEqual(len(h_streaks), 1)
                for s in h_streaks:
                    self.assertEqual(s[4] & 0x40, 0x40, "Right-facing inhale streak $09 must H-flip inward")

        # Vertical inhale uses $0A vertical ribbon (V-flip $80 when facing Down, $00 when facing Up)
        for facing, exp_vflip in ((0, 0x00), (2, 0x80)):
            fx_v = self.make_fx()
            self._start_gust(fx_v, button=1, facing=facing)
            fx_v.reset_oam_frame()
            fx_v.put(0x1A, 1)
            fx_v.run_jsl("GustJar_FrameTick")
            fx_v.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
            v_streaks = [s for s in fx_v.read_oam_sprites("A") if s[3] == 0x0A]
            self.assertGreaterEqual(len(v_streaks), 1, f"Expected $0A vertical ribbon for facing={facing}")
            for s in v_streaks:
                self.assertEqual(s[4] & 0x80, exp_vflip)

        # 2. Blast Wave OAM: ALL Tiers (1/2/3) emit 16x16 custom Minish Crescent Wave ($09)
        #    with directional orientation flip (U=$80, D=$00, L=$40, R=$00) + expanding wing puffs,
        #    and ZERO Portal Rod ($EE) tiles at any wave age!
        dir_flips = ((0, 0x80), (2, 0x00), (4, 0x40), (6, 0x00))
        for facing, exp_flip in dir_flips:
            with self.subTest(wave_dir=facing):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=facing)
                fx.put(0x0275, 0x40)  # Tier 3
                fx.run_jsl("GustJar_FrameTick")
                fx.put(0xF0, 0x00)
                fx.run_jsl("GustJar_FrameTick")  # FireBlast
                fx.reset_oam_frame()
                fx.put(0x1A, 4)
                fx.run_jsl("GustJar_FrameTick")
                fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                wave_sprs = fx.read_oam_sprites("A")
                self.assertEqual(wave_sprs[0][3], 0x09, "Primary Blast Wave core must be custom 16x16 $09")
                self.assertEqual(wave_sprs[0][5], 0x02, "Blast Crescent core must be 16x16 ($02)")
                self.assertEqual(wave_sprs[0][4] & 0xC0, exp_flip, "Blast Crescent must orient in travel direction")

        for charge, exp_tier, exp_cnt in ((0x04, 1, 3), (0x1A, 2, 4), (0x40, 3, 5)):
            with self.subTest(wave_tier=exp_tier):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=6)
                fx.put(0x0275, charge)
                fx.run_jsl("GustJar_FrameTick")
                fx.put(0xF0, 0x00)
                fx.run_jsl("GustJar_FrameTick")  # FireBlast
                fx.reset_oam_frame()
                fx.put(0x1A, 2)
                fx.run_jsl("GustJar_FrameTick")
                fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                wave_rec = fx.oam_records[-1]
                self.assertEqual(wave_rec[0], "A")
                self.assertEqual(wave_rec[1], exp_cnt * 4)
                wave_sprs_early = fx.read_oam_sprites("A")
                self.assertEqual(wave_sprs_early[0][3], 0x09)
                self.assertEqual(wave_sprs_early[0][5], 0x02)
                spread_early = abs(wave_sprs_early[1][2] - wave_sprs_early[2][2])

                for k in range(6):
                    fx.reset_oam_frame()
                    fx.put(0x1A, 4 + k)
                    fx.run_jsl("GustJar_FrameTick")
                    fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                    for s in fx.read_oam_sprites():
                        self.assertNotIn(s[3], (0xEE, 0x72), "Never emit Portal Rod $EE or Magic Jar $72")
                wave_sprs_late = fx.read_oam_sprites("A")
                self.assertEqual(wave_sprs_late[0][3], 0x09)
                self.assertEqual(wave_sprs_late[0][5], 0x02)
                spread_late = abs(wave_sprs_late[1][2] - wave_sprs_late[2][2])
                self.assertGreater(spread_late, spread_early, "Wing puffs must widen as wave travels")

        # 3. Graceful fallback: if another $0109 item ($0301/$037A/$0308/$5D) becomes active
        #    while a Blast Wave is still flying after follow-through (bit 2 clear), DrawWaveOAM
        #    falls back cleanly from $09 to resident white billowing cloud $86 (16x16)!
        for conflict_addr, conflict_val in ((0x0301, 0x01), (0x037A, 0x04), (0x0308, 0x01), (0x5D, 0x13)):
            with self.subTest(fallback_addr=hex(conflict_addr)):
                fx = self.make_fx()
                self._start_gust(fx, button=1, facing=6)
                fx.put(0x0275, 0x40)
                fx.run_jsl("GustJar_FrameTick")
                fx.put(0xF0, 0x00)
                fx.run_jsl("GustJar_FrameTick")
                for f in range(8):  # Finish 7-frame follow-through -> bit 2 clears
                    fx.put(0x1A, f)
                    fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 2)
                self.assertEqual(fx.get(0x027F) & 0x04, 0)
                fx.put(conflict_addr, conflict_val)
                fx.reset_oam_frame()
                fx.put(0x1A, 12)
                fx.run_jsl("GustJar_FrameTick")
                fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
                wave_sprs = fx.read_oam_sprites("A")
                self.assertEqual(wave_sprs[0][3], 0x86, "Must fall back to resident cloud $86 on $0109 item conflict")
                self.assertEqual(wave_sprs[0][5], 0x02, "Fallback cloud $86 must remain 16x16")

    def test_gust_jar_nmi_upload_vram_slots_frames_restore_and_bombchu_chain(self):
        gfx_bytes = (ROOT / "Data/graphics/items/gust_jar_world.4bpp").read_bytes()
        self.assertEqual(len(gfx_bytes), 0x500)
        gfx_addr = self.labels["GustJarWorldGfx"]
        self.assertEqual(gfx_addr >> 16, 0x34, "GustJarWorldGfx must reside in Bank $34")
        self.assertGreaterEqual(gfx_addr & 0xFFFF, 0xE000)
        self.assertLessEqual((gfx_addr & 0xFFFF) + len(gfx_bytes), 0xF000)

        def block(idx: int) -> bytes:
            return gfx_bytes[idx * 128:(idx + 1) * 128]

        # 1. Idle fast-path: zero DMA transfers, preserves A/X/Y/P/DBR and $4304/$4302!
        fx = self.make_fx()
        fx.put(0x10, 0x07)
        fx.set_word(0x0ADC, 0x9A3C)
        fx.hw_regs[0x4302] = 0x3C; fx.hw_regs[0x4303] = 0x9A; fx.hw_regs[0x4304] = 0x7E
        fx.run_nmi_jsl("GustJar_NmiUpload", a=0x5A, x=0x1357, y=0x2468)
        self.assertEqual(fx.dma_transfers, [])
        self.assertEqual((fx.cpu.a & 0xFF, fx.cpu.x, fx.cpu.y, fx.cpu.mf, fx.cpu.xf), (0x5A, 0x1357, 0x2468, True, False))
        self.assertEqual((fx.hw_regs[0x4304], fx.hw_regs[0x4302], fx.hw_regs[0x4303]), (0x7E, 0x3C, 0x9A))

        # 2. Non-gameplay module ($0E pause/menu) skips DMA cleanly!
        fx.put(0x0273, 1); fx.put(0x027F, 0x04); fx.put(0x10, 0x0E)
        fx.run_nmi_jsl("GustJar_NmiUpload")
        self.assertEqual(fx.dma_transfers, [])

        # 3. Inhale frames across all directions, Tier 1 vs Tier 2 pulse vs Tier 3 / Corked ->
        #    Slot 1 ($4070/$4170) gets exact Jar block 0/1/2/3/9; Slot 2 ($4090/$4190) gets Inhale block 4!
        inhale_cases = [
            ("right_t1",      6, 1, 0, 0x00, 0),
            ("left_t1",       4, 1, 0, 0x04, 0),
            ("right_t2_even", 6, 2, 0, 0x00, 0),
            ("right_t2_odd",  6, 2, 0, 0x04, 1),  # Swollen pulse!
            ("right_t3",      6, 3, 0, 0x00, 1),  # Tier 3 always swollen!
            ("left_corked",   4, 1, 1, 0x00, 1),  # Corked -> always swollen!
            ("down_t1",       2, 1, 0, 0x04, 2),  # Normal open front nozzle
            ("down_t3_full",  2, 3, 0, 0x04, 9),  # Swollen full front jar (Block 9)!
            ("down_corked",   2, 1, 2, 0x00, 9),  # Corked front jar (Block 9)!
            ("up_back",       0, 3, 0, 0x04, 3),
        ]
        for name, facing, tier, cap, frame_ctr, exp_jar_blk in inhale_cases:
            with self.subTest(inhale_nmi=name):
                fx = self.make_fx()
                fx.put(0x10, 0x09)
                fx.set_word(0x0ADC, 0xBCDE)
                fx.put(0x0273, 1); fx.put(0x027F, 0x04)
                fx.put(0x0277, facing); fx.put(0x0276, tier)
                fx.put(0x0278, cap); fx.put(0x1A, frame_ctr)
                fx.run_nmi_jsl("GustJar_NmiUpload", a=0x33, x=0xCAFE, y=0xBEEF)
                self.assertEqual(len(fx.dma_transfers), 4, "Expected 2 rows Jar + 2 rows Inhale Wind")
                self.assertEqual([t[0] for t in fx.dma_transfers], [0x4070, 0x4170, 0x4090, 0x4190])
                self.assertEqual([t[2] for t in fx.dma_transfers], [0x40, 0x40, 0x40, 0x40])
                self.assertEqual(fx.dma_transfers[0][3] + fx.dma_transfers[1][3], block(exp_jar_blk))
                self.assertEqual(fx.dma_transfers[2][3] + fx.dma_transfers[3][3], block(4))
                # Verify $4304=$7E, $4302=$0ADC restored and registers/M8/X16 preserved!
                self.assertEqual(fx.hw_regs[0x4304], 0x7E)
                self.assertEqual(fx.hw_regs[0x4302] | (fx.hw_regs[0x4303] << 8), 0xBCDE)
                self.assertEqual((fx.cpu.a & 0xFF, fx.cpu.x, fx.cpu.y, fx.cpu.mf, fx.cpu.xf), (0x33, 0xCAFE, 0xBEEF, True, False))
                # Verify ZERO writes to Sword ($4050/$4150) or Somaria ($40C0/$41C0)!
                for vword, _, _, _ in fx.dma_transfers:
                    self.assertNotIn(vword, (0x4050, 0x4150, 0x40C0, 0x41C0))

        # 4. Blast Wave NMI: directional H0/H1 (5/6) & V0/V1 (7/8) toggle on !GustJarWaveTmr bit 2;
        #    Slot 1 ($4070) uploaded during follow-through (bit 2=1) and SKIPPED after (bit 2=0)!
        blast_cases = [
            ("R_peak_H0",  6, 0x0D, 0x10, 1, 5),
            ("R_rec_H1",   6, 0x05, 0x14, 0, 6),
            ("L_free_H1",  4, 0x01, 0x0C, None, 6),  # Follow-through ended -> Shield untouched!
            ("D_free_V0",  2, 0x01, 0x10, None, 7),
            ("U_free_V1",  0, 0x01, 0x0C, None, 8),
        ]
        for name, facing, flags, wtmr, exp_jar_blk, exp_wave_blk in blast_cases:
            with self.subTest(blast_nmi=name):
                fx = self.make_fx()
                fx.put(0x10, 0x07)
                fx.set_word(0x0ADC, 0xABCD)
                fx.put(0x0273, 2); fx.put(0x027F, flags)
                fx.put(0x0277, facing); fx.put(0x027A, wtmr)
                fx.run_nmi_jsl("GustJar_NmiUpload")
                if exp_jar_blk is not None:
                    self.assertEqual([t[0] for t in fx.dma_transfers], [0x4070, 0x4170, 0x4090, 0x4190])
                    self.assertEqual(fx.dma_transfers[0][3] + fx.dma_transfers[1][3], block(exp_jar_blk))
                    self.assertEqual(fx.dma_transfers[2][3] + fx.dma_transfers[3][3], block(exp_wave_blk))
                else:
                    self.assertEqual([t[0] for t in fx.dma_transfers], [0x4090, 0x4190], "Shield $4070 must be skipped once follow-through ends")
                    self.assertEqual(fx.dma_transfers[0][3] + fx.dma_transfers[1][3], block(exp_wave_blk))
                self.assertEqual(fx.hw_regs[0x4304], 0x7E)
                self.assertEqual(fx.hw_regs[0x4302] | (fx.hw_regs[0x4303] << 8), 0xABCD)

        # 5. Another $0109 item active after follow-through skips Slot 2 ($4090/$4190) cleanly!
        fx_item = self.make_fx()
        fx_item.put(0x10, 0x07); fx_item.set_word(0x0ADC, 0x8888)
        fx_item.put(0x0273, 2); fx_item.put(0x027F, 0x01); fx_item.put(0x0301, 0x01)
        fx_item.run_nmi_jsl("GustJar_NmiUpload")
        self.assertEqual(fx_item.dma_transfers, [], "Active $0301 item must prevent $4090/$4190 overwrite")
        self.assertEqual(fx_item.hw_regs[0x4304], 0x7E)
        self.assertEqual(fx_item.hw_regs[0x4302] | (fx_item.hw_regs[0x4303] << 8), 0x8888)

        # 6. Full Bombchu_NmiUpload -> GustJar_NmiUpload chain: BOTH upload cleanly with zero conflict!
        fx_chain = self.make_fx()
        fx_chain.put(0x10, 0x07)
        fx_chain.set_word(0x0ADC, 0x9999)
        fx_chain.set_word(0x0134, 0x2200)
        # Active Bombchu in slot 0 + active Gust Jar inhale facing Right!
        fx_chain.put(0x7E07F6, 0xBC); fx_chain.put(0x7E07F1, 1); fx_chain.put(0x7E07F2, 0)
        fx_chain.put(0x0C4A, 0x07); fx_chain.put(0x03EA, 0xBC); fx_chain.put(0x0C5E, 0)
        fx_chain.put(0x0273, 1); fx_chain.put(0x027F, 0x04); fx_chain.put(0x0277, 6); fx_chain.put(0x0276, 1)
        fx_chain.run_nmi_jsl("Bombchu_NmiUpload", a=0x42, x=0x1111, y=0x2222)
        self.assertEqual([t[0] for t in fx_chain.dma_transfers],
                         [0x42E0, 0x43E0, 0x4070, 0x4170, 0x4090, 0x4190])
        self.assertEqual(fx_chain.hw_regs[0x4304], 0x7E)
        self.assertEqual(fx_chain.hw_regs[0x4302] | (fx_chain.hw_regs[0x4303] << 8), 0x9999)
        self.assertEqual(fx_chain.hw_regs[0x2116] | (fx_chain.hw_regs[0x2117] << 8), 0x2200,
                         "Bombchu_NmiUpload displaced LDX $0134 : STX $2116 must run after GustJar_NmiUpload")
        self.assertEqual((fx_chain.cpu.a & 0xFF, fx_chain.cpu.y, fx_chain.cpu.mf, fx_chain.cpu.xf),
                         (0x42, 0x2222, True, False))

        # 7. Source-level static check: ZERO #$EE or #$72 tile constants anywhere in Items/gust_jar.asm!
        gust_src = (ROOT / "Items/gust_jar.asm").read_text()
        self.assertNotIn("#$EE", gust_src, "Items/gust_jar.asm must never reference Portal Rod tile #$EE")
        self.assertNotIn("#$72", gust_src, "Items/gust_jar.asm must never reference Small Magic Jar tile #$72")

    def test_gust_jar_absorbs_hides_and_restores_sprites_and_somaria_safely(self):
        # 1. Absorbed Sprite (enemy / throwable $EC): GustJar_SpriteHideHook skips
        #    Sprite_ExecuteSingle ONLY for captured slot while inhaling, and restores
        #    immediately on release OR abort!
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        fx.place_sprite(0, 0x0D, 0x114, 0x102, health=4)  # Light enemy near nozzle -> captured!
        fx.place_sprite(1, 0x12, 0x138, 0x102, health=10) # Other sprite -> NOT hidden!
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual((fx.get(0x0278), fx.get(0x0279)), (1, 0))

        fx.spr_exec_slots.clear()
        fx.run_jsl("GustJar_SpriteHideHook", x=0, db=0x06)
        fx.run_jsl("GustJar_SpriteHideHook", x=1, db=0x06)
        self.assertEqual(fx.spr_exec_slots, [1], "Captured sprite slot 0 must be hidden; slot 1 must still run")

        # Abort (e.g. Link hurt) -> snaps sprite to nozzle, grounds SprHeight=0, unhides immediately!
        fx.put(0x46, 0x10)
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0273), 0)
        self.assertEqual(fx.get(0x0F70), 0)
        fx.spr_exec_slots.clear()
        fx.run_jsl("GustJar_SpriteHideHook", x=0, db=0x06)
        self.assertEqual(fx.spr_exec_slots, [0], "Aborted sprite must immediately become visible again")

        # 2. Absorbed Somaria Block ($2C): pulls into nozzle, gets captured & hidden by
        #    GustJar_AncillaHideHook (A=0, Z=1), then pops out & blasts forward on release!
        fx2 = self.make_fx()
        self._start_gust(fx2, button=1, facing=6)
        fx2.place_ancilla(0, 0x2C, 0x118, 0x10A)  # Somaria within 20 px of nozzle -> absorbed!
        fx2.place_ancilla(1, 0x07, 0x140, 0x10A)  # Other bomb -> NOT hidden!
        fx2.run_jsl("GustJar_FrameTick")
        self.assertEqual((fx2.get(0x0278), fx2.get(0x0279)), (2, 0), "Close Somaria Block must be absorbed into jar")

        a0, _, z0 = fx2.run_jsl("GustJar_AncillaHideHook", x=0, db=0x08)
        a1, _, z1 = fx2.run_jsl("GustJar_AncillaHideHook", x=1, db=0x08)
        self.assertEqual((a0, z0), (0x00, True), "Absorbed Somaria slot 0 must be hidden (A=0, Z=1)")
        self.assertEqual((a1, z1), (0x07, False), "Non-captured ancilla slot 1 must stay visible")

        # Release Y -> unhides immediately, pops out of nozzle, and blasts right with wave!
        fx2.put(0xF0, 0x00)
        fx2.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx2.get(0x0273), 2)
        a0_rel, _, z0_rel = fx2.run_jsl("GustJar_AncillaHideHook", x=0, db=0x08)
        self.assertEqual((a0_rel, z0_rel), (0x2C, False), "Released Somaria must immediately unhide")
        som_x0 = fx2.get(0x0C04) | (fx2.get(0x0C18) << 8)
        self.assertEqual(som_x0, 0x100 + 22 + 10, "Released Somaria must pop 10px clear of nozzle ahead of wave crest")
        for f in range(5):
            fx2.put(0x1A, f + 1)
            fx2.run_jsl("GustJar_FrameTick")
        som_x1 = fx2.get(0x0C04) | (fx2.get(0x0C18) << 8)
        self.assertGreater(som_x1, som_x0 + 6, "Released Somaria must ride Crescent Wave forward")

        # 3. Heavy Movable Statue ($1C) stops cleanly outside nozzle (fwd < 19 px) without sliding onto Link!
        fx3 = self.make_fx()
        self._start_gust(fx3, button=1, facing=6)
        fx3.place_sprite(0, 0x1C, 0x110, 0x102, frame=0)  # center 0x118 -> fwd = 16 px (< 19)
        fx3.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx3.get(0x0D10) | (fx3.get(0x0D30) << 8), 0x110, "Heavy statue must not pull onto Link")

    def test_gust_jar_full_primed_coiled_pressure_halo_and_mouth_core_oam(self):
        # When FULL / ABSORBED (!GustJarCapKind != 0):
        #   - Region C Slot 0 emits rapid spinning glowing mouth core orb ($19) cycling H/V flips!
        #   - Region C Slot 1 emits swollen pulsing jar ($07) with +/-1px tremble & Pal 4<->2!
        #   - Region A collapses long suction funnel into tight 4-sprite orbiting pressure halo ($19/$1A)
        #     strictly within 16 px of the nozzle!
        fx = self.make_fx()
        self._start_gust(fx, button=1, facing=6)
        fx.place_sprite(0, 0xEC, 0x114, 0x102)  # Pot near nozzle -> absorbed!
        fx.run_jsl("GustJar_FrameTick")
        self.assertEqual(fx.get(0x0278), 1)

        mouth_flips = set()
        for f in range(4):
            fx.reset_oam_frame()
            fx.put(0x1A, f)
            fx.run_jsl("GustJar_FrameTick")
            fx.run_jsl("GustJar_LinkPoseOamHook", y=0x00, db=0x0D)
            reg_c = fx.read_oam_sprites("C")
            self.assertEqual(reg_c[0][3], 0x19, "Full/primed mouth FX must be glowing pressure orb $19")
            mouth_flips.add(reg_c[0][4] & 0xC0)
            halo = fx.read_oam_sprites("A")
            self.assertEqual(len(halo), 4, "Full/absorbed state must emit 4-sprite coiled pressure halo")
            nozzle_sx, nozzle_sy = 0x60 + 22 - 4, 0x60 + 10 - 4
            for _, sx, sy, tile, attr, hi in halo:
                self.assertIn(tile, (0x19, 0x1A), f"Halo must use custom pressure tiles $19/$1A, got {tile:#04x}")
                self.assertEqual(attr & 0x0E, 0x04)
                self.assertEqual(hi, 0x00)
                self.assertLessEqual(abs(sx - nozzle_sx), 14, "Coiled halo must stay tight around nozzle X")
                self.assertLessEqual(abs(sy - nozzle_sy), 14, "Coiled halo must stay tight around nozzle Y")
        self.assertEqual(mouth_flips, {0x00, 0x40, 0x80, 0xC0}, "Primed mouth core must spin through all 4 H/V quadrants")

    def test_switch_hook_trade_gate_isolated_from_gust_jar_1d(self):
        fx = self.make_fx()
        fx.setup_link(x=0x100, y=0x100)
        fx.put(0x0304, 0x0E)
        fx.put(0x7EF3AE, 1)  # GustJarOwned = 1
        # 1. Logical item $1D MUST NOT latch Switch Hook!
        fx.put(0x7E0260, 0x1D)
        fx.run_jsl("SwitchHook_Init")
        self.assertEqual(fx.get(0x07F8), 0x00)
        # 2. Unmigrated legacy Goldstar save ($7EF342=2, version!=A5) MUST NOT latch Switch Hook!
        fx.put(0x7E0260, 0x03)
        fx.put(0x7EF342, 0x02)
        fx.put(0x7EF3AA, 0x00)
        fx.run_jsl("SwitchHook_Init")
        self.assertEqual(fx.get(0x07F8), 0x00)
        # 3. Traded Hookshot ($03, migrated version=$A5, $7EF342=2) DOES latch Switch Hook!
        fx.put(0x7EF3AA, 0xA5)
        fx.run_jsl("SwitchHook_Init")
        self.assertEqual(fx.get(0x07F8), 0xA5)

    # =========================================================================
    # DELIVERABLE 3: BOOK OF SECRETS OWNERSHIP FIX ($7EF34E)
    # =========================================================================

    def test_book_of_secrets_checks_7ef34e_not_feather_7ef34d(self):
        # 1. Owning ONLY Roc's Feather ($7EF34D=1, $7EF34E=0) + holding L indoors -> BG2 stays ON!
        fx = self.make_fx()
        fx.put(0x1B, 1)         # Indoors
        fx.put(0x7EF34D, 1)     # Roc's Feather owned
        fx.put(0x7EF34E, 0)     # Book of Secrets NOT owned
        fx.put(0xF2, 0x20)      # L held
        fx.put(0x1C, 0x15)      # BG2 currently off -> must be forced ON ($02)
        fx.run_jsl("Dungeon_RevealSecrets")
        self.assertEqual(fx.get(0x1C) & 0x02, 0x02, "Feather alone must NOT peel BG2")

        # 2. Owning Book of Secrets ($7EF34E=1, $7EF34D=0) + holding L indoors -> peels BG2 OFF!
        fx.put(0x7EF34D, 0)
        fx.put(0x7EF34E, 1)
        fx.put(0x1C, 0x17)      # BG2 currently on
        fx.put(0xF2, 0x20)      # L held
        fx.run_jsl("Dungeon_RevealSecrets")
        self.assertEqual(fx.get(0x1C) & 0x02, 0x00, "Book of Secrets + L indoors must disable BG2")

        # 3. Releasing L restores BG2 ON!
        fx.put(0xF2, 0x00)
        fx.run_jsl("Dungeon_RevealSecrets")
        self.assertEqual(fx.get(0x1C) & 0x02, 0x02, "Releasing L must re-enable BG2")


if __name__ == "__main__":
    unittest.main(verbosity=2)
