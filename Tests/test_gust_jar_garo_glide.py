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
STUB_OAM_D = 0x0DBA8C
STUB_OW_TILE_ACT = 0x1BBD7A
STUB_CANCEL_DASH = 0x0790B0
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

; Assemble real Items/switch_hook.asm in Bank $2B (expects bank cursor on stack)
incsrc "{(ROOT / 'Items/switch_hook.asm').as_posix()}"
pullpc

; Assemble real Items/gust_jar.asm in Bank $39 tail ($39F000-$39FFFF)
incsrc "{(ROOT / 'Items/gust_jar.asm').as_posix()}"
""")

    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(rom_path)],
        cwd=str(ROOT / "Masks"),
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
            STUB_OAM_D: "oam_d",
            STUB_OW_TILE_ACT: "ow_tile_act",
            STUB_CANCEL_DASH: "cancel_dash",
        }
        self.oam_allocs: list[int] = []
        self.ow_cuts: list[tuple[int, int, int]] = []
        self.cancel_dash_calls = 0
        self.cpu.db = 0x07  # Gameplay DBR mirror

    def stub(self, name: str):
        if name == "oam_d":
            size = self.cpu.a & 0xFF
            self.oam_allocs.append(size)
            self.word(0x90, 0x0830)
            self.word(0x92, 0x0A2C)
        elif name == "ow_tile_act":
            self.ow_cuts.append((self.get(0x0301), self.get(0x00) | (self.get(0x01) << 8),
                                 self.get(0x02) | (self.get(0x03) << 8)))
            self.put(0x76, 1)
        elif name == "cancel_dash":
            self.cancel_dash_calls += 1
            self.put(0x0372, 0)

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
                self.assertEqual(fx.get(0x5E), 0x08)   # Slow creep stance

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

                # After follow-through, $3A bit 6 & $5E release while wave finishes flying
                for i in range(20):
                    fx.put(0x1A, 10 + i)
                    fx.run_jsl("GustJar_FrameTick")
                self.assertEqual(fx.get(0x0273), 0)
                self.assertEqual(fx.get(0x3A) & 0x40, 0)
                self.assertEqual(fx.get(0x5E), 0)

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
                self.assertEqual(fx.get(0x5E), 0, f"{label} must clear slow-walk $5E")
                self.assertEqual(fx.get(0x0F70), 0, f"{label} must ground any captured sprite")

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
