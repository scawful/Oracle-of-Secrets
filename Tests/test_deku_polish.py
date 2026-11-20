#!/usr/bin/env python3
"""Compiled 65816 CPU unit tests & art contract checks for Deku Polish:
  1. Majora's Mask Spinning Deku Flower Hover Wings (Masks/deku_mask.asm +
     Horse_NmiUpload tail chain in Masks/horse_sparse_runtime.asm +
     Data/graphics/items/deku_flower_wings.4bpp)
  2. Deku Flower ($77, Sprites/Objects/deku_leaf.asm) burrow/approach/launch
     pulse, multi-flower $71 safety, 4-leaf Region C launch burst, and $3D
     Whirlpool preservation
  3. Deku Scrub NPCs ($A0, Sprites/NPCs/deku_scrub.asm) + cleaned Sheet 0x33
     (Data/graphics/spr33.txt) Butler & Princess 2-frame out-of-phase idle
     animations and Withered ($F2) preservation

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
for p in (TESTS_DIR, ROOT / "Scripts" / "Generate"):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402
import build_deku_wings_art as wings_art  # noqa: E402
import build_deku_npcs_sheet as npcs_art  # noqa: E402


def find_lakesnes() -> Path:
    candidates = [
        Path(os.environ["OOS_LAKESNES"]) if os.environ.get("OOS_LAKESNES") else None,
        ROOT.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ]
    for cand in candidates:
        if cand and (cand / "snes/cpu.c").is_file():
            return cand
    raise RuntimeError("Could not locate lakesnes (set OOS_LAKESNES)")


def build_cpu_lib(work_dir: Path) -> C.CDLL:
    lakesnes = find_lakesnes()
    lib_path = work_dir / "cpu.dylib"
    subprocess.run(
        ["cc", "-shared", "-fPIC", "-O2",
         str(lakesnes / "snes/cpu.c"),
         str(lakesnes / "snes/statehandler.c"),
         "-o", str(lib_path)],
        check=True,
    )
    lib = C.CDLL(str(lib_path))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib

# Stubbed vanilla SNES routines
STUB_OAM_A = 0x0DBA80
STUB_OAM_B = 0x0DBA84
STUB_OAM_C = 0x0DBA88
STUB_PREP_OAM = 0x06E416
STUB_DEFER_OAM = 0x06F864
STUB_POOF_GARNISH = 0x05AB9C
STUB_SPARKLE_GARNISH = 0x058008
STUB_CANT_PASS = 0x1EF4F3
STUB_SOLICITED_MSG = 0x05E1A7
STUB_UNCOND_MSG = 0x05E219
STUB_CHECK_ACTIVE = 0x06E400
STUB_COLOR_SUB = 0x35F7E0
STUB_JUMP_TABLE = 0x008781
STUB_RESET_GFX = 0x3A8100


def _assemble_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    image = bytearray(b"\xFF" * 0x2C0000)

    def put_rom(snes_addr: int, data: bytes):
        pc = ((snes_addr >> 16) & 0x7F) * 0x8000 + (snes_addr & 0x7FFF)
        image[pc:pc + len(data)] = data

    # Preimages asserted by Masks/horse_form.asm & Masks/horse_sparse_runtime.asm
    put_rom(0x008A0C, bytes.fromhex("A0 00 41 8C 16 21"))
    put_rom(0x008B5C, bytes.fromhex("A2 00 04 8E 05 43 A9 01 8D 0B 42"))
    put_rom(0x08A41B, bytes.fromhex("A5 72 91 90 C8"))
    put_rom(0x0DA191, bytes.fromhex("A0 00 A5 11"))

    rom_path = folder / "deku_fixture.sfc"
    rom_path.write_bytes(image)

    # Extract only the Deku bank-$35 block of Masks/deku_mask.asm (up to assert pc() <= $35F800)
    # so we don't need Bank 07 LinkItem_DekuMask symbols, while assembling the exact unmodified
    # DekuWings_NmiUpload, DekuWings_DrawHoverOam, and DekuFlowerWingsGfx bytes!
    deku_mask_lines = (ROOT / "Masks/deku_mask.asm").read_text().splitlines()
    cut_idx = next(i for i, ln in enumerate(deku_mask_lines) if ln.strip().startswith("org $07A64B"))
    deku_b35_asm = folder / "deku_b35.asm"
    deku_b35_asm.write_text("\n".join(deku_mask_lines[:cut_idx]) + "\n")

    # Minimal CheckIfPlayerIsOn matching Sprites/Objects/minecart.asm:1242 verbatim
    minecart_lines = (ROOT / "Sprites/Objects/minecart.asm").read_text().splitlines()
    chk_start = next(i for i, ln in enumerate(minecart_lines) if ln.strip() == "CheckIfPlayerIsOn:")
    chk_end = next(i for i in range(chk_start + 1, len(minecart_lines)) if minecart_lines[i].strip() == "}")
    check_on_src = "\n".join(minecart_lines[chk_start:chk_end + 1])

    asm = folder / "deku_fixture.asm"
    asm.write_text(f"""lorom
!DEBUG = 0
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 0
!ENABLE_OCARINA_SONG_TINT = 0

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
macro Set_Sprite_Properties(prep, main)
endmacro
macro StartOnFrame(f)
  LDA.w SprFrame, X : CMP.b #<f> : BCS + : LDA.b #<f> : STA.w SprFrame, X : +
endmacro
macro PlayAnimation(start, end, speed)
  LDA.w SprFrame, X : CMP.b #<start> : BCS + : LDA.b #<start> : STA.w SprFrame, X : +
endmacro
macro GotoAction(a)
  LDA.b #<a> : STA.w SprAction, X
endmacro
macro ShowSolicitedMessage(msg)
  LDA.b #(<msg>&$FF) : LDY.b #(<msg>>>8) : JSL Sprite_ShowSolicitedMessage
endmacro
macro ShowUnconditionalMessage(msg)
  LDA.b #(<msg>&$FF) : LDY.b #(<msg>>>8) : JSL Sprite_ShowMessageUnconditional
endmacro

; Shared symbols matching Core/symbols.asm, Core/link.asm & Masks/all_masks.asm
!CurrentMask = $02B2
LinkFaceDir = $2F
FallTimer = $5C
DekuFloating = $70
DekuHover = $71
FrameCounter = $1A
AreaIndex = $8A
SongFlag = $FE
SideQuestProg = $7EF3D7
SideQuestProg2 = $7EF3D8
Crystals = $7EF37A
InCutScene = $7E0FFC
struct TimeState $7EC000
  .SubColor: skip 2
endstruct

Sprite_DekuLeaf = $77
Sprite_DekuScrubNPCs = $A0

SprY = $0D00
SprX = $0D10
SprYH = $0D20
SprXH = $0D30
SprAction = $0D80
SprFrame = $0D90
SprMiscA = $0DA0
SprMiscB = $0DB0
SprGfx = $0DC0
SprState = $0DD0
SprMiscC = $0DE0
SprTimerA = $0DF0
SprTimerB = $0E00
SprType = $0E20
SprSubtype = $0E30
SprNbrOAM = $0E40
SprMiscD = $0E90
SprDefl = $0CAA
SprTimerD = $0EE0
SprBulletproof = $0BA0
SprCachedX = $0FD8
SprCachedY = $0FDA

; Horse WRAM symbols (for Horse_NmiUpload tail chain verification)
Horse_Marker = $7E1EDE
Horse_State = $7E1EE0
Horse_JumpTimer = $7E1EE1
Horse_JumpCooldown = $7E1EE2
Horse_JumpDir = $7E1EE3
Horse_JumpZ = $7E1EE4
Horse_AnimTimer = $7E1EE5
Horse_Frame = $7E1EE6
Horse_UploadedFrame = $7E1EE7
Horse_NpcActive = $7E1EE8
Horse_NpcFrame = $7E1EE9
Horse_NpcUploadedFrame = $7E1EEA
Horse_PalLoaded = $7E1EEB
Horse_DismountCooldown = $7E1EEC
Horse_HasAnchor = $7E1EED
Horse_JumpStep = $7E1EEE
Horse_PushTimer = $7E1EEF
Horse_JumpStartX = $7E1EF0
Horse_JumpStartY = $7E1EF2
Horse_JumpEndX = $7E1EF4
Horse_JumpEndY = $7E1EF6
Horse_AnchorX = $7E1EF8
Horse_AnchorY = $7E1EFA
Horse_NpcSlot = $7E1EFC
Horse_InteractDelay = $7E1EFD

OAM_AllocateFromRegionA = ${STUB_OAM_A:06X}
OAM_AllocateFromRegionB = ${STUB_OAM_B:06X}
OAM_AllocateFromRegionC = ${STUB_OAM_C:06X}
Sprite_PrepOamCoord = ${STUB_PREP_OAM:06X}
Sprite_OAM_AllocateDeferToPlayer = ${STUB_DEFER_OAM:06X}
Sprite_SpawnPoofGarnish = ${STUB_POOF_GARNISH:06X}
Sprite_SpawnSparkleGarnish = ${STUB_SPARKLE_GARNISH:06X}
Sprite_PlayerCantPassThrough = ${STUB_CANT_PASS:06X}
Sprite_ShowSolicitedMessage = ${STUB_SOLICITED_MSG:06X}
Sprite_ShowMessageUnconditional = ${STUB_UNCOND_MSG:06X}
Sprite_CheckActive = ${STUB_CHECK_ACTIVE:06X}
ColorSubEffect = ${STUB_COLOR_SUB:06X}
ResetToLinkGraphics = ${STUB_RESET_GFX:06X}
Link_ReceiveItem = ${STUB_RESET_GFX:06X}

; Vanilla JumpTableLocal ($008781): M=8, X=8, A=index; stack = [ret_lo, ret_hi, ret_bank]
org ${STUB_JUMP_TABLE:06X}
JumpTableLocal:
  REP #$20
  AND.w #$00FF : ASL A : STA.b $0A
  SEP #$20
  PLA : STA.b $0C
  PLA : STA.b $0D
  PLA : STA.b $0E
  REP #$20
  LDA.b $0C : INC A : CLC : ADC.b $0A : STA.b $0C
  LDA.b [$0C] : STA.b $0C
  SEP #$20
  JML [$000C]

Horse_RanchActorsSafe:
  SEC : RTL

; Bank $35: real Masks/deku_mask.asm Bank-$35 code + Data/graphics/items/deku_flower_wings.4bpp
org $35F000
incsrc "{deku_b35_asm.as_posix()}"

; Bank $31: real Sprites/Objects/deku_leaf.asm & Sprites/NPCs/deku_scrub.asm + CheckIfPlayerIsOn
org $318000
{check_on_src}
incsrc "{(ROOT / 'Sprites/Objects/deku_leaf.asm').as_posix()}"
incsrc "{(ROOT / 'Sprites/NPCs/deku_scrub.asm').as_posix()}"

; Bank $53: real Masks/horse_sparse_runtime.asm (to test Horse_NmiUpload -> DekuWings_NmiUpload chain!)
org $538000
HorseGraphics:
  fillbyte $00 : fill 512
HorseItemRestore:
  fillbyte $00 : fill 384
HorseRanchRestore:
  fillbyte $00 : fill 1024
HorseNpcTail:
  fillbyte $00 : fill 512
!Horse_MagicMarker = $4852
!Horse_MaskId = $09
!Horse_FrameCount = 19
!Horse_NpcHeadOffset = 0
HorseFrame_GroupPointers:
  fillbyte $00 : fill 256
HorseFrame_Count:
  fillbyte $06 : fill 20
Horse_DmaRider:
Horse_DmaPart4Narrow:
  RTS
incsrc "{(ROOT / 'Masks/horse_sparse_runtime.asm').as_posix()}"
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


class DekuFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.stubs = {
            STUB_OAM_A: "oam_a",
            STUB_OAM_B: "oam_b",
            STUB_OAM_C: "oam_c",
            STUB_PREP_OAM: "prep_oam",
            STUB_DEFER_OAM: "defer_oam",
            STUB_POOF_GARNISH: "poof",
            STUB_SPARKLE_GARNISH: "sparkle",
            STUB_CANT_PASS: "cant_pass",
            STUB_SOLICITED_MSG: "sol_msg",
            STUB_UNCOND_MSG: "uncond_msg",
            STUB_CHECK_ACTIVE: "check_active",
            STUB_COLOR_SUB: "color_sub",
            STUB_RESET_GFX: "reset_gfx",
        }
        self.oam_allocs: list[tuple[str, int, int, int]] = []
        self._oam_b_off = 0x0180
        self._oam_c_off = 0x0000
        self._oam_a_off = 0x0060
        self._oam_defer_off = 0x0080
        self.poof_count = 0
        self.sparkle_count = 0
        self.cant_pass_count = 0
        self.solicited_msgs: list[int] = []
        self.prep_oam_onscreen = True
        self.prep_oam_sx = 120
        self.prep_oam_sy = 100
        self.hw_regs: dict[int, int] = {
            0x2116: 0, 0x2117: 0,
            0x4302: 0, 0x4303: 0, 0x4304: 0x7E,
            0x4305: 0, 0x4306: 0,
        }
        self.vram = bytearray(0x10000)
        self.dma_transfers: list[tuple[int, int, int, bytes]] = []

    def write(self, a: int, v: int):
        bank, lo = a >> 16, a & 0xFFFF
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
                    payload = bytearray(length)
                    for i in range(length):
                        payload[i] = self.read(src24 + i)
                    vram_byte = (vram_word * 2) & 0xFFFF
                    for i in range(length):
                        self.vram[(vram_byte + i) & 0xFFFF] = payload[i]
                    self.dma_transfers.append((vram_word, src24, length, bytes(payload)))
                    new_src = (src_lo + length) & 0xFFFF
                    self.hw_regs[0x4302] = new_src & 0xFF
                    self.hw_regs[0x4303] = new_src >> 8
                    self.hw_regs[0x4305] = 0
                    self.hw_regs[0x4306] = 0
                    new_vw = (vram_word + length // 2) & 0xFFFF
                    self.hw_regs[0x2116] = new_vw & 0xFF
                    self.hw_regs[0x2117] = new_vw >> 8
                return
            self.hw_regs[lo] = v & 0xFF
            return
        super().write(a, v)

    def read(self, a: int) -> int:
        bank, lo = a >> 16, a & 0xFFFF
        if (bank & 0x7F) < 0x40 and lo in self.hw_regs:
            return self.hw_regs[lo]
        return super().read(a)

    def _alloc_region(self, region: str, off: int, size: int) -> int:
        low_addr = 0x0800 + off
        hi_addr = 0x0A20 + (off >> 2)
        self.ram[0x90] = low_addr & 0xFF
        self.ram[0x91] = low_addr >> 8
        self.ram[0x92] = hi_addr & 0xFF
        self.ram[0x93] = hi_addr >> 8
        self.oam_allocs.append((region, size, low_addr, hi_addr))
        # Mimic vanilla $0DBB0A..$0DBB58 clobbering $0C..$0F and leaving Y non-zero!
        self.ram[0x0C] = 0x55
        self.ram[0x0D] = 0xAA
        self.ram[0x0E] = size & 0xFF
        self.ram[0x0F] = 0x00
        self.cpu.y = 0x90
        return off + size

    def _handle_stub(self, kind: str) -> None:
        if kind == "oam_a":
            size = self.cpu.a & 0xFF
            self._oam_a_off = self._alloc_region("A", self._oam_a_off, size)
        elif kind == "oam_b":
            size = self.cpu.a & 0xFF
            self._oam_b_off = self._alloc_region("B", self._oam_b_off, size)
        elif kind == "oam_c":
            size = self.cpu.a & 0xFF
            self._oam_c_off = self._alloc_region("C", self._oam_c_off, size)
        elif kind == "defer_oam":
            self._oam_defer_off = self._alloc_region("D", self._oam_defer_off, 16)
        elif kind == "prep_oam":
            sx = self.prep_oam_sx & 0xFFFF
            sy = self.prep_oam_sy & 0xFFFF
            self.ram[0x00] = sx & 0xFF
            self.ram[0x01] = sx >> 8
            self.ram[0x02] = sy & 0xFF
            self.ram[0x03] = sy >> 8
            self.cpu.c = not self.prep_oam_onscreen
        elif kind == "poof":
            self.poof_count += 1
        elif kind == "sparkle":
            self.sparkle_count += 1
        elif kind == "cant_pass":
            self.cant_pass_count += 1
        elif kind == "sol_msg":
            msg = (self.cpu.a & 0xFF) | ((self.cpu.y & 0xFF) << 8)
            self.solicited_msgs.append(msg)
            self.cpu.c = False
        elif kind == "check_active":
            self.cpu.c = True

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def run_jsl(self, name: str, *, a: int = 0, x: int = 0, y: int = 0,
                db: int = 0x00, mf: bool = True, xf: bool = True, limit: int = 40000) -> int:
        addr = self.labels[name]
        self.cpu.a = a
        self.cpu.x = x
        self.cpu.y = y
        self.cpu.db = db
        self.cpu.mf = mf
        self.cpu.xf = xf
        self.cpu.k = addr >> 16
        self.cpu.pc = addr & 0xFFFF
        # Push synthetic RTL return $00:0000 (stop sentinel $000001)
        self.ram[0x01FF] = 0x00
        self.ram[0x01FE] = 0x00
        self.ram[0x01FD] = 0x00
        self.cpu.sp = 0x01FC
        steps = 0
        while steps < limit:
            pc24 = (self.cpu.k << 16) | self.cpu.pc
            if pc24 == 0x000001:
                return steps
            if pc24 in self.stubs:
                self._handle_stub(self.stubs[pc24])
                # Execute RTL from stub
                lo = self.ram[self.cpu.sp + 1]
                hi = self.ram[self.cpu.sp + 2]
                bk = self.ram[self.cpu.sp + 3]
                self.cpu.sp += 3
                ret = ((bk << 16) | (hi << 8) | lo) + 1
                self.cpu.k = (ret >> 16) & 0xFF
                self.cpu.pc = ret & 0xFFFF
                steps += 1
                continue
            self.lib.cpu_runOpcode(self.cpu)
            steps += 1
        raise AssertionError(f"{name} hit step limit ({limit}) at ${self.cpu.k:02X}:{self.cpu.pc:04X}")

    def read_oam_slots(self, low_addr: int, hi_addr: int, count: int) -> list[tuple[int, int, int, int, int]]:
        out = []
        for i in range(count):
            base = low_addr + i * 4
            out.append((
                self.ram[base],
                self.ram[base + 1],
                self.ram[base + 2],
                self.ram[base + 3],
                self.ram[hi_addr + i],
            ))
        return out


class DekuPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory(prefix="oos_deku_test_")
        cls.lib = build_cpu_lib(Path(cls.tmp.name))
        cls.rom, cls.labels = _assemble_fixture(Path(cls.tmp.name) / "asm")

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def make_fx(self) -> DekuFixture:
        fx = DekuFixture(self.lib, self.rom, self.labels)
        self.addCleanup(fx.close)
        return fx

    # ------------------------------------------------------------------
    # 1. Deku Flower-Leaves Art & NMI Uploader (Bank $35 code + Bank $38 GFX)
    # ------------------------------------------------------------------
    def test_wings_art_binary_matches_generator_and_sp7_bounds(self):
        raw = wings_art.build_4bpp()
        self.assertEqual(len(raw), 1536)
        self.assertEqual((ROOT / "Data/graphics/items/deku_flower_wings.4bpp").read_bytes(), raw)
        # All 12 frames (6 Front/Back + 6 Side Profile) must be distinct
        frames = [raw[i * 128:(i + 1) * 128] for i in range(12)]
        self.assertEqual(len(set(frames)), 12)
        # Front/Back frames (0..5): curved stem anchors in bottom-inner corner
        # (cols 12..15, rows 10..15) while keeping face-clearance cols 14..15 clear on rows 0..7.
        for name, rows in wings_art.FRONT_FRAMES:
            grid = wings_art.parse_grid(name, rows)
            grip_pixels = sum(1 for r in range(10, 16) for c in range(12, 16) if grid[r][c] != 0)
            self.assertGreaterEqual(grip_pixels, 8, f"{name}: missing bottom-inner stem grip pixels")
            face_intrusions = sum(1 for r in range(0, 8) for c in range(14, 16) if grid[r][c] != 0)
            self.assertEqual(face_intrusions, 0, f"{name}: blossom intrudes into face-clearance cols 14..15")
        # Side Profile frames (6..11): strictly ONE centered overhead flower (stem cols 6..9)
        # and S5 Flap-Down leaves rows 13..15 clear so drooping petals never cover cap/eyes.
        for name, rows in wings_art.SIDE_FRAMES:
            grid = wings_art.parse_grid(name, rows)
            stem_pixels = sum(1 for r in range(9, 15) for c in range(6, 10) if grid[r][c] != 0)
            self.assertGreaterEqual(stem_pixels, 10, f"{name}: missing centered overhead side stem pixels (cols 6..9)")
            if name == "side5_flap_down":
                for r in range(13, 16):
                    self.assertTrue(all(v == 0 for v in grid[r]), f"{name}: row {r} should stay clear above Deku Link's cap/eyes")

    def test_nmi_upload_fast_exits_when_not_deku_hovering(self):
        cases = [
            ("DekuFloating=0",     0, 0x01, 0x0A, 0x09),
            ("Human mask=0",       1, 0x00, 0x0A, 0x09),
            ("Zora mask=2",        1, 0x02, 0x0A, 0x09),
            ("Moosh mask=7",       1, 0x07, 0x0A, 0x09),
            ("Non-hover state=0",  1, 0x01, 0x00, 0x09),
            ("Pause menu mod=$0E", 1, 0x01, 0x0A, 0x0E),
            ("Title mod=$00",      1, 0x01, 0x0A, 0x00),
        ]
        for label, flt, mask, state, mod in cases:
            with self.subTest(case=label):
                fx = self.make_fx()
                fx.ram[0x70] = flt
                fx.ram[0x02B2] = mask
                fx.ram[0x5D] = state
                fx.ram[0x10] = mod
                fx.hw_regs[0x4304] = 0x7E
                fx.hw_regs[0x4302] = 0x34
                fx.hw_regs[0x4303] = 0x12
                steps = fx.run_jsl("DekuWings_NmiUpload", x=0x1122, y=0x3344, db=0x00, mf=True, xf=False)
                self.assertEqual(fx.dma_transfers, [])
                self.assertEqual(fx.hw_regs[0x4304], 0x7E)
                self.assertEqual(fx.hw_regs[0x4302] | (fx.hw_regs[0x4303] << 8), 0x1234)
                self.assertEqual(fx.cpu.x, 0x1122)
                self.assertEqual(fx.cpu.y, 0x3344)
                if flt == 0:
                    self.assertLessEqual(steps, 4, "Fast-path when DekuFloating==0 should exit immediately")

    def test_nmi_upload_phase1_spin_and_phase2_flap_frames_and_dma_restore(self):
        expected_bin = (ROOT / "Data/graphics/items/deku_flower_wings.4bpp").read_bytes()
        # Verify BOTH Front/Back ($00 Up / $02 Down -> base 0) and Side Profile ($04 Left / $06 Right -> base 6)
        dir_banks = [
            ("Up",    0x00, 0),
            ("Down",  0x02, 0),
            ("Left",  0x04, 6),
            ("Right", 0x06, 6),
        ]
        # Phase 1: FallTimer >= $50 -> spin frames (0..3 or 6..9) via base + (($1A >> 1) & 3)
        for mod in (0x07, 0x09, 0x0B):
            for dir_name, dval, base in dir_banks:
                for frame_off in range(4):
                    with self.subTest(phase=1, module=f"${mod:02X}", dir=dir_name, frame=base + frame_off):
                        fx = self.make_fx()
                        fx.ram[0x70] = 1
                        fx.ram[0x02B2] = 0x01
                        fx.ram[0x5D] = 0x0A
                        fx.ram[0x10] = mod
                        fx.ram[0x2F] = dval
                        fx.ram[0x5C] = 0xC0 if frame_off != 0 else 0x50
                        fx.ram[0x1A] = frame_off * 2
                        fx.ram[0x0ADC] = 0x80
                        fx.ram[0x0ADD] = 0xA4
                        fx.run_jsl("DekuWings_NmiUpload", x=0xBEEF, y=0xCAFE, db=0x00, mf=True, xf=False)

                        self.assertEqual(len(fx.dma_transfers), 2)
                        top_vw, top_src, top_len, top_data = fx.dma_transfers[0]
                        bot_vw, bot_src, bot_len, bot_data = fx.dma_transfers[1]
                        self.assertEqual((top_vw, top_len), (0x4070, 64))
                        self.assertEqual((bot_vw, bot_len), (0x4170, 64))
                        self.assertEqual(top_src >> 16, 0x38)
                        self.assertEqual(bot_src >> 16, 0x38)
                        exp_idx = base + frame_off
                        exp_frame = expected_bin[exp_idx * 128:(exp_idx + 1) * 128]
                        self.assertEqual(top_data, exp_frame[:64])
                        self.assertEqual(bot_data, exp_frame[64:128])
                        self.assertEqual(bytes(fx.vram[0x80E0:0x8120]), exp_frame[:64])
                        self.assertEqual(bytes(fx.vram[0x82E0:0x8320]), exp_frame[64:128])
                        self.assertEqual(fx.hw_regs[0x4304], 0x7E)
                        self.assertEqual(fx.hw_regs[0x4302] | (fx.hw_regs[0x4303] << 8), 0xA480)
                        self.assertEqual(fx.cpu.x, 0xBEEF)
                        self.assertEqual(fx.cpu.y, 0xCAFE)
                        self.assertTrue(fx.cpu.mf)
                        self.assertFalse(fx.cpu.xf)

        # Phase 2a ($20..$4F): 4-frame cadence Flap-Up (base+4) <-> Flap-Down (base+5)
        for dir_name, dval, base in dir_banks:
            for fall_timer in (0x4F, 0x38, 0x20):
                for fc, off in ((0x00, 4), (0x02, 4), (0x04, 5), (0x06, 5), (0x08, 4)):
                    with self.subTest(phase="2a", dir=dir_name, fall=f"${fall_timer:02X}", fc=fc):
                        fx = self.make_fx()
                        fx.ram[0x70] = 1
                        fx.ram[0x02B2] = 0x01
                        fx.ram[0x5D] = 0x0A
                        fx.ram[0x10] = 0x09
                        fx.ram[0x2F] = dval
                        fx.ram[0x5C] = fall_timer
                        fx.ram[0x1A] = fc
                        fx.ram[0x0ADC] = 0x80
                        fx.ram[0x0ADD] = 0xA4
                        fx.run_jsl("DekuWings_NmiUpload", db=0x00, mf=True, xf=False)
                        exp_idx = base + off
                        exp_frame = expected_bin[exp_idx * 128:(exp_idx + 1) * 128]
                        self.assertEqual(fx.dma_transfers[0][3] + fx.dma_transfers[1][3], exp_frame)

        # Phase 2b (< $20): frantic 2-frame cadence Flap-Up (base+4) <-> Flap-Down (base+5)
        for dir_name, dval, base in dir_banks:
            for fall_timer in (0x1F, 0x14, 0x01):
                for fc, off in ((0x00, 4), (0x01, 4), (0x02, 5), (0x03, 5), (0x04, 4)):
                    with self.subTest(phase="2b", dir=dir_name, fall=f"${fall_timer:02X}", fc=fc):
                        fx = self.make_fx()
                        fx.ram[0x70] = 1
                        fx.ram[0x02B2] = 0x01
                        fx.ram[0x5D] = 0x0A
                        fx.ram[0x10] = 0x09
                        fx.ram[0x2F] = dval
                        fx.ram[0x5C] = fall_timer
                        fx.ram[0x1A] = fc
                        fx.ram[0x0ADC] = 0x80
                        fx.ram[0x0ADD] = 0xA4
                        fx.run_jsl("DekuWings_NmiUpload", db=0x00, mf=True, xf=False)
                        exp_idx = base + off
                        exp_frame = expected_bin[exp_idx * 128:(exp_idx + 1) * 128]
                        self.assertEqual(fx.dma_transfers[0][3] + fx.dma_transfers[1][3], exp_frame)

    def test_horse_nmi_upload_tail_chains_deku_wings(self):
        expected_bin = (ROOT / "Data/graphics/items/deku_flower_wings.4bpp").read_bytes()
        for dir_name, dval, exp_idx in (("Down", 0x02, 2), ("Left", 0x04, 8)):
            with self.subTest(dir=dir_name):
                fx = self.make_fx()
                # Horse marker uninit -> takes fast .replay path -> animated tile DMA -> DekuWings_NmiUpload
                fx.ram[0x70] = 1
                fx.ram[0x02B2] = 0x01
                fx.ram[0x5D] = 0x0A
                fx.ram[0x10] = 0x09
                fx.ram[0x2F] = dval
                fx.ram[0x5C] = 0xC0  # Phase 1 steady levitation spin
                fx.ram[0x1A] = 0x04  # spin frame +2 (F2 on Down, S2=8 on Left)
                fx.ram[0x0ADC] = 0x00
                fx.ram[0x0ADD] = 0x90
                fx.ram[0x0134] = 0x00
                fx.ram[0x0135] = 0x38
                fx.run_jsl("Horse_NmiUpload", y=0x5566, db=0x00, mf=True, xf=False)
                # Expect animated tile DMA (1024B to $3800) + 2 Deku Wings DMAs (64B to $4070 & $4170)
                self.assertEqual(len(fx.dma_transfers), 3)
                self.assertEqual((fx.dma_transfers[0][0], fx.dma_transfers[0][2]), (0x3800, 0x0400))
                self.assertEqual((fx.dma_transfers[1][0], fx.dma_transfers[1][2]), (0x4070, 64))
                self.assertEqual((fx.dma_transfers[2][0], fx.dma_transfers[2][2]), (0x4170, 64))
                self.assertEqual(
                    fx.dma_transfers[1][3] + fx.dma_transfers[2][3],
                    expected_bin[exp_idx * 128:(exp_idx + 1) * 128],
                )
                self.assertEqual(fx.hw_regs[0x4304], 0x7E)
                self.assertEqual(fx.hw_regs[0x4302] | (fx.hw_regs[0x4303] << 8), 0x9000)
                self.assertEqual(fx.cpu.y, 0x5566)

    def test_wings_draw_hover_oam_overhead_all_4_dirs_single_side_and_2phase_flap(self):
        # Per-facing overhead Deku Flower-Leaf layout:
        #   - Up/Down:    2 OAM slots (8 B) — symmetric twin flowers at dx=+-13, hand-anchored (dy=-7/-6)
        #   - Left/Right: 1 OAM slot  (4 B) — ONE single centered flower at dx=0, dy=-9
        front_back = [
            ("Up",   0x00, -13, -7, 0x2E, +13, -7, 0x6E),
            ("Down", 0x02, -13, -6, 0x2E, +13, -6, 0x6E),
        ]
        side_single = [
            ("Left",  0x04, 0, -9, 0x2E),
            ("Right", 0x06, 0, -9, 0x6E),
        ]
        # Phase 1: FallTimer = $C0, $1A = $08 (bob index 1 -> -1px), SX = 128, SY_air = 94
        for name, dval, dx0, dy0, attr0, dx1, dy1, attr1 in front_back:
            with self.subTest(phase=1, dir=name):
                fx = self.make_fx()
                fx.ram[0x10] = 0x09
                fx.ram[0x11] = 0x00
                fx.ram[0x22] = 0x80; fx.ram[0x23] = 0x01  # LinkX = $0180
                fx.ram[0x20] = 0x70; fx.ram[0x21] = 0x01  # LinkY = $0170
                fx.ram[0xE2] = 0x00; fx.ram[0xE3] = 0x01  # CamX  = $0100 -> SX = 128
                fx.ram[0xE8] = 0x00; fx.ram[0xE9] = 0x01  # CamY  = $0100 -> SY = 112
                fx.ram[0x24] = 0x12; fx.ram[0x25] = 0x00  # AirZ  = 18 -> SY_air = 94
                fx.ram[0x2F] = dval
                fx.ram[0x5C] = 0xC0                       # Phase 1 steady levitation
                fx.ram[0xEE] = 0x00                       # prio $20
                fx.ram[0x1A] = 0x08                       # bob index 1 -> -1 px
                canary = bytes(range(0xA0, 0xB0))
                fx.ram[0x00:0x10] = canary

                fx.run_jsl("DekuWings_DrawHoverOam", x=0x33, y=0x05, db=0x0D, mf=True, xf=True)

                self.assertEqual(bytes(fx.ram[0x00:0x10]), canary)
                self.assertEqual(fx.cpu.db, 0x0D)
                self.assertEqual(fx.cpu.x, 0x33)
                self.assertEqual(fx.cpu.y, 0x05)
                self.assertEqual(len(fx.oam_allocs), 1)
                region, size, low_addr, hi_addr = fx.oam_allocs[0]
                self.assertEqual((region, size), ("C", 8))
                slots = fx.read_oam_slots(low_addr, hi_addr, 2)
                self.assertEqual(slots[0], (128 + dx0, 94 + dy0 - 1, 0x07, attr0, 0x02))
                self.assertEqual(slots[1], (128 + dx1, 94 + dy1 - 1, 0x07, attr1, 0x02))

        for name, dval, dx0, dy0, attr0 in side_single:
            with self.subTest(phase=1, dir=name):
                fx = self.make_fx()
                fx.ram[0x10] = 0x09
                fx.ram[0x11] = 0x00
                fx.ram[0x22] = 0x80; fx.ram[0x23] = 0x01
                fx.ram[0x20] = 0x70; fx.ram[0x21] = 0x01
                fx.ram[0xE2] = 0x00; fx.ram[0xE3] = 0x01
                fx.ram[0xE8] = 0x00; fx.ram[0xE9] = 0x01
                fx.ram[0x24] = 0x12; fx.ram[0x25] = 0x00
                fx.ram[0x2F] = dval
                fx.ram[0x5C] = 0xC0
                fx.ram[0xEE] = 0x00
                fx.ram[0x1A] = 0x08
                canary = bytes(range(0xA0, 0xB0))
                fx.ram[0x00:0x10] = canary

                fx.run_jsl("DekuWings_DrawHoverOam", x=0x33, y=0x05, db=0x0D, mf=True, xf=True)

                self.assertEqual(bytes(fx.ram[0x00:0x10]), canary)
                self.assertEqual(fx.cpu.db, 0x0D)
                self.assertEqual(fx.cpu.x, 0x33)
                self.assertEqual(fx.cpu.y, 0x05)
                self.assertEqual(len(fx.oam_allocs), 1)
                region, size, low_addr, hi_addr = fx.oam_allocs[0]
                self.assertEqual((region, size), ("C", 4))  # strictly 1 OAM slot!
                slots = fx.read_oam_slots(low_addr, hi_addr, 1)
                self.assertEqual(slots[0], (128 + dx0, 94 + dy0 - 1, 0x07, attr0, 0x02))

        # Phase 2a ($38) & Phase 2b ($14): Flap-Up (-2px Y) vs Flap-Down (+2px Y)
        # Front/Back splay +-1px on Flap-Down; Side stays centered (dx=0, 1 OAM slot)!
        flap_cases = [
            ("2a_up",   0x38, 0x00, -2, False),
            ("2a_down", 0x38, 0x04, +2, True),
            ("2b_up",   0x14, 0x00, -2, False),
            ("2b_down", 0x14, 0x02, +2, True),
        ]
        for dname, dval, dy0 in (("Up", 0x00, -7), ("Down", 0x02, -6)):
            for label, ft, fc, bob_y, is_down in flap_cases:
                with self.subTest(dir=dname, flap=label):
                    fx = self.make_fx()
                    fx.ram[0x10] = 0x09
                    fx.ram[0x22] = 0x80; fx.ram[0x23] = 0x01
                    fx.ram[0x20] = 0x70; fx.ram[0x21] = 0x01
                    fx.ram[0xE2] = 0x00; fx.ram[0xE3] = 0x01
                    fx.ram[0xE8] = 0x00; fx.ram[0xE9] = 0x01
                    fx.ram[0x24] = 0x12; fx.ram[0x25] = 0x00
                    fx.ram[0x2F] = dval
                    fx.ram[0x5C] = ft
                    fx.ram[0x1A] = fc
                    fx.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
                    region, size, low_addr, hi_addr = fx.oam_allocs[0]
                    self.assertEqual((region, size), ("C", 8))
                    slots = fx.read_oam_slots(low_addr, hi_addr, 2)
                    dx = 14 if is_down else 13
                    self.assertEqual(slots[0], (128 - dx, 94 + dy0 + bob_y, 0x07, 0x2E, 0x02))
                    self.assertEqual(slots[1], (128 + dx, 94 + dy0 + bob_y, 0x07, 0x6E, 0x02))

        for dname, dval, attr0 in (("Left", 0x04, 0x2E), ("Right", 0x06, 0x6E)):
            for label, ft, fc, bob_y, _ in flap_cases:
                with self.subTest(dir=dname, flap=label):
                    fx = self.make_fx()
                    fx.ram[0x10] = 0x09
                    fx.ram[0x22] = 0x80; fx.ram[0x23] = 0x01
                    fx.ram[0x20] = 0x70; fx.ram[0x21] = 0x01
                    fx.ram[0xE2] = 0x00; fx.ram[0xE3] = 0x01
                    fx.ram[0xE8] = 0x00; fx.ram[0xE9] = 0x01
                    fx.ram[0x24] = 0x12; fx.ram[0x25] = 0x00
                    fx.ram[0x2F] = dval
                    fx.ram[0x5C] = ft
                    fx.ram[0x1A] = fc
                    fx.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
                    region, size, low_addr, hi_addr = fx.oam_allocs[0]
                    self.assertEqual((region, size), ("C", 4))
                    slots = fx.read_oam_slots(low_addr, hi_addr, 1)
                    self.assertEqual(slots[0], (128, 94 - 9 + bob_y, 0x07, attr0, 0x02))

    def test_wings_draw_hover_oam_hidden_and_left_edge_clip(self):
        # Hidden via $4B=$0C or $55=1 -> zero OAM allocated
        for addr, val in ((0x4B, 0x0C), (0x55, 0x01), (0x11, 0x02)):
            fx = self.make_fx()
            fx.ram[0x10] = 0x09
            fx.ram[addr] = val
            fx.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
            self.assertEqual(fx.oam_allocs, [], f"Expected no OAM when ${addr:02X}=${val:02X}")

        # Left-edge smooth clipping: Down (dx0=-13, dx1=+13), SX=4 -> Left X=-9 ($F7, hi=$03), Right X=17 (hi=$02)
        fx = self.make_fx()
        fx.ram[0x10] = 0x09
        fx.ram[0x2F] = 0x02
        fx.ram[0x5C] = 0xC0
        fx.ram[0x22] = 0x04; fx.ram[0x20] = 0x50; fx.ram[0x24] = 0x10
        fx.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
        _, _, low_addr, hi_addr = fx.oam_allocs[0]
        slots = fx.read_oam_slots(low_addr, hi_addr, 2)
        self.assertEqual((slots[0][0], slots[0][4]), (0xF7, 0x03))  # X=-9 with X-msb=1
        self.assertEqual((slots[1][0], slots[1][4]), (17, 0x02))

        # Full off-left clip: Down + Flap-Down (dx0=-14, dx1=+14); SX=-4 -> Left X=-18 (clipped!), Right X=-4+14=10
        fx2 = self.make_fx()
        fx2.ram[0x10] = 0x09
        fx2.ram[0x2F] = 0x02
        fx2.ram[0x5C] = 0x14
        fx2.ram[0x1A] = 0x02  # Flap-Down (spread=1 -> dx0=-14, dx1=+14)
        fx2.ram[0x22] = 0xFC; fx2.ram[0x23] = 0xFF  # LinkSX = -4 -> Left X = -18 (clipped!)
        fx2.ram[0x20] = 0x50; fx2.ram[0x24] = 0x10
        fx2.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
        _, _, low2, hi2 = fx2.oam_allocs[0]
        slots2 = fx2.read_oam_slots(low2, hi2, 2)
        self.assertEqual(slots2[0][1], 0xF0)        # Left wing cleanly clipped offscreen
        self.assertEqual((slots2[1][0], slots2[1][4]), (10, 0x02))  # Right wing at -4 + 14 = 10

        # Side Right smooth partial left-edge clip (1 slot): SX=-4 -> X=-4 ($FC, hi=$03)
        fx3 = self.make_fx()
        fx3.ram[0x10] = 0x09
        fx3.ram[0x2F] = 0x06  # Right: single centered slot at dx=0
        fx3.ram[0x5C] = 0xC0
        fx3.ram[0x22] = 0xFC; fx3.ram[0x23] = 0xFF
        fx3.ram[0x20] = 0x50; fx3.ram[0x24] = 0x10
        fx3.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
        region3, size3, low3, hi3 = fx3.oam_allocs[0]
        self.assertEqual((region3, size3), ("C", 4))
        slots3 = fx3.read_oam_slots(low3, hi3, 1)
        self.assertEqual((slots3[0][0], slots3[0][4]), (0xFC, 0x03))  # X=-4 with X-msb=1

        # Side Left full off-left clip (1 slot): SX=-16 -> clipped ($F0)
        fx4 = self.make_fx()
        fx4.ram[0x10] = 0x09
        fx4.ram[0x2F] = 0x04
        fx4.ram[0x5C] = 0xC0
        fx4.ram[0x22] = 0xF0; fx4.ram[0x23] = 0xFF
        fx4.ram[0x20] = 0x50; fx4.ram[0x24] = 0x10
        fx4.run_jsl("DekuWings_DrawHoverOam", db=0x0D)
        _, size4, low4, hi4 = fx4.oam_allocs[0]
        self.assertEqual(size4, 4)
        slots4 = fx4.read_oam_slots(low4, hi4, 1)
        self.assertEqual(slots4[0][1], 0xF0)

    # ------------------------------------------------------------------
    # 2. Deku Flower ($77, Sprites/Objects/deku_leaf.asm) Polish
    # ------------------------------------------------------------------
    def test_deku_leaf_burrow_launch_burst_and_multiflower_safety(self):
        fx = self.make_fx()
        slot0, slot1 = 0, 1
        # Place Flower 0 at (160, 160) and Flower 1 at (240, 160)
        fx.ram[0x8A] = 0x2D  # Tail Pond (not $3D whirlpool)
        fx.ram[0x02B2] = 0x01  # Deku Link
        fx.ram[0x22] = 160; fx.ram[0x23] = 0
        fx.ram[0x20] = 160; fx.ram[0x21] = 0

        # Frame 1: Deku Link steps onto Flower 0 -> sets $71=1, SprMiscA=1, spawns 1 entry sparkle (0 poof!)
        fx.ram[0x0FD8] = 160; fx.ram[0x0FD9] = 0
        fx.ram[0x0FDA] = 160; fx.ram[0x0FDB] = 0
        fx.ram[0x1A] = 1
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot0, db=0x31)
        self.assertEqual(fx.ram[0x71], 1)
        self.assertEqual(fx.ram[0x0DA0 + slot0], 1)  # SprMiscA
        self.assertEqual(fx.ram[0x0DE0 + slot0], 1)  # SprMiscC (within 40px)
        self.assertEqual(fx.poof_count, 0, "Standing on flower must use sparkle, not dust puff")
        self.assertEqual(fx.sparkle_count, 1)

        # Same frame: Flower 1 (far away) runs -> must NOT clobber $71!
        fx.ram[0x0FD8] = 240; fx.ram[0x0FD9] = 0
        fx.ram[0x0FDA] = 160; fx.ram[0x0FDB] = 0
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot1, db=0x31)
        self.assertEqual(fx.ram[0x71], 1, "Unrelated flower must not clobber $71")
        self.assertEqual(fx.ram[0x0DE0 + slot1], 0, "Far flower proximity flag must stay 0")

        # Frame 2: Still standing on Flower 0 at FrameCounter=2 -> sparkle throttled (no spam!)
        fx.ram[0x0FD8] = 160; fx.ram[0x0FDA] = 160
        fx.ram[0x1A] = 2
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot0, db=0x31)
        self.assertEqual(fx.poof_count, 0)
        self.assertEqual(fx.sparkle_count, 1, "Standing sparkle must throttle instead of firing every frame")

        # Frame 3: Deku Link launches ($5D = $0A) -> triggers launch burst ONCE (SprMiscD = $18, poof+sparkle)
        fx.ram[0x5D] = 0x0A
        fx.ram[0x1A] = 3
        fx.oam_allocs.clear()
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot0, db=0x31)
        self.assertEqual(fx.ram[0x0DB0 + slot0], 1)     # SprMiscB latched
        self.assertEqual(fx.ram[0x0E90 + slot0], 0x18)  # SprMiscD = 24-frame burst
        self.assertEqual(fx.poof_count, 1)
        self.assertEqual(fx.sparkle_count, 2)

        # Next frame: launch burst draws Region B (4 flower tiles) + Region C (4 leaf flutter particles)!
        fx.oam_allocs.clear()
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot0, db=0x31)
        self.assertEqual(fx.ram[0x0E90 + slot0], 0x17)
        self.assertEqual([(r, s) for r, s, _, _ in fx.oam_allocs], [("B", 16), ("C", 16)])
        # Verify the 4 launch leaves use Page-0 resident tiles $72/$62 & Pal 1 ($32 base)
        _, _, c_low, c_hi = fx.oam_allocs[1]
        leaves = fx.read_oam_slots(c_low, c_hi, 4)
        for lx, ly, ch, attr, hi in leaves:
            self.assertIn(ch, (0xE4, 0xE5))
            self.assertEqual(attr & 0x3F, 0x32)
            self.assertEqual(hi, 0x00)
        # Must NOT re-trigger launch burst while $5D remains $0A
        self.assertEqual(fx.sparkle_count, 2)

        # Leaving Flower 0 clears $71 and SprMiscA cleanly
        fx.ram[0x22] = 200
        fx.ram[0x5D] = 0x00
        fx.run_jsl("Sprite_DekuLeaf_Long", x=slot0, db=0x31)
        self.assertEqual(fx.ram[0x71], 0)
        self.assertEqual(fx.ram[0x0DA0 + slot0], 0)
        self.assertEqual(fx.ram[0x0DB0 + slot0], 0)  # launch latch re-armed

    def test_deku_leaf_whirlpool_path_untouched(self):
        fx = self.make_fx()
        fx.ram[0x8A] = 0x3D  # Beach Whirlpool area
        fx.ram[0x0D80] = 1   # SprAction = 1 (Whirlpool)
        fx.ram[0x0D90] = 0   # SprFrame = 0
        fx.ram[0x0E90] = 0x10  # even if SprMiscD were nonzero, whirlpool must ignore it
        fx.run_jsl("Sprite_DekuLeaf_Long", x=0, db=0x31)
        # Only Region B (16B = 4 tiles) drawn, NEVER Region C launch burst!
        self.assertEqual([(r, s) for r, s, _, _ in fx.oam_allocs], [("B", 16)])
        _, _, b_low, b_hi = fx.oam_allocs[0]
        slots = fx.read_oam_slots(b_low, b_hi, 4)
        self.assertEqual([s[2] for s in slots], [0xE6, 0xE4, 0xC6, 0xC4])
        self.assertTrue(all(s[3] == 0x29 for s in slots))

    # ------------------------------------------------------------------
    # 3. Deku Scrub NPCs ($A0, Sprites/NPCs/deku_scrub.asm) & Sheet 0x33
    # ------------------------------------------------------------------
    def test_sheet33_source_art_and_blank_col_b_preserved(self):
        grid = npcs_art.build_grid()
        self.assertEqual((ROOT / "Data/graphics/spr33.txt").read_text(),
                         __import__("sheet_codec").grid_to_text(grid))
        # Col $B ($0B/$1B/$2B/$3B -> x=88..95) remains 100% blank
        self.assertTrue(all(grid[y][x] == 0 for y in range(32) for x in range(88, 96)))
        # Butler idle1 head ($09/$0A/$19/$1A) & Princess idle1 body ($29/$2A/$39/$3A) are populated
        self.assertGreater(sum(1 for y in range(16) for x in range(72, 88) if grid[y][x] != 0), 80)
        self.assertGreater(sum(1 for y in range(16, 32) for x in range(72, 88) if grid[y][x] != 0), 80)

    def test_deku_scrub_prep_and_butler_princess_2frame_idle_toggling(self):
        # 1. Prep initializes Butler (sub=1 -> act 5, frame 3) and Princess (sub=2 -> act 6, frame 4)
        fx = self.make_fx()
        fx.ram[0x8A] = 0x00
        fx.ram[0x0E30 + 0] = 1  # Butler
        fx.ram[0x0E30 + 1] = 2  # Princess
        fx.run_jsl("Sprite_DekuScrub_Prep", x=0, db=0x31)
        fx.run_jsl("Sprite_DekuScrub_Prep", x=1, db=0x31)
        self.assertEqual((fx.ram[0x0D80 + 0], fx.ram[0x0D90 + 0]), (5, 3))
        self.assertEqual((fx.ram[0x0D80 + 1], fx.ram[0x0D90 + 1]), (6, 4))

        # Peacetime areas $2E (Butler -> act 7, frame 3) and $2F (Princess -> act 8, frame 4)
        fx.ram[0x8A] = 0x2E
        fx.run_jsl("Sprite_DekuScrub_Prep", x=2, db=0x31)
        self.assertEqual((fx.ram[0x0D80 + 2], fx.ram[0x0D90 + 2]), (7, 3))
        fx.ram[0x8A] = 0x2F
        fx.run_jsl("Sprite_DekuScrub_Prep", x=3, db=0x31)
        self.assertEqual((fx.ram[0x0D80 + 3], fx.ram[0x0D90 + 3]), (8, 4))

        # 2. Butler idle toggling across FrameCounter & $3F (< $30 -> F3, >= $30 -> F5)
        for act, expected_msg in ((5, 0x080), (7, 0x1B9)):
            fx = self.make_fx()
            fx.ram[0x0D80] = act
            fx.ram[0x1A] = 0x10  # open eyes -> frame 3
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            self.assertEqual(fx.ram[0x0D90], 3)
            self.assertIn(expected_msg, fx.solicited_msgs)

            fx.oam_allocs.clear()
            fx.ram[0x1A] = 0x35  # blink/bob -> frame 5
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            self.assertEqual(fx.ram[0x0D90], 5)
            # Run one more draw pass on frame 5 to inspect emitted OAM tiles!
            fx.oam_allocs.clear()
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            _, _, low_addr, hi_addr = fx.oam_allocs[0]
            slots = fx.read_oam_slots(low_addr, hi_addr, 4)
            # Frame 5 draws head $09 (H-mirrored $7B/$3B at dy=-11) in front (slots 0,1), body $25/$24 behind (slots 2,3)
            self.assertEqual([s[2] for s in slots], [0x09, 0x09, 0x25, 0x24])
            self.assertEqual([s[3] for s in slots], [0x7B, 0x3B, 0x3B, 0x3B])
            self.assertEqual([s[1] for s in slots], [89, 89, 104, 104])  # sy=100: -11=89, +4=104

        # 3. Princess idle toggling (out-of-phase +$20: $1A=$00 -> F4, $1A=$15 -> F6)
        for act, expected_msg in ((6, 0x0C3), (8, 0x1BA)):
            fx = self.make_fx()
            fx.ram[0x0D80] = act
            fx.ram[0x1A] = 0x00  # ($00+$20)&$3F = $20 < $30 -> frame 4
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            self.assertEqual(fx.ram[0x0D90], 4)
            self.assertIn(expected_msg, fx.solicited_msgs)

            fx.ram[0x1A] = 0x15  # ($15+$20)&$3F = $35 >= $30 -> frame 6
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            self.assertEqual(fx.ram[0x0D90], 6)
            fx.oam_allocs.clear()
            fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
            _, _, low_addr, hi_addr = fx.oam_allocs[0]
            slots = fx.read_oam_slots(low_addr, hi_addr, 4)
            # Frame 6 draws dipped crown $07 (dy=-11) + blinked face/dress $29 (dy=+4), H-mirrored
            self.assertEqual([s[2] for s in slots], [0x07, 0x29, 0x07, 0x29])
            self.assertEqual([s[3] for s in slots], [0x7B, 0x7B, 0x3B, 0x3B])
            self.assertEqual([s[1] for s in slots], [89, 104, 89, 104])

        # 4. Withered Deku (state 4) remains intact on frame 2 ($20/$00/$02/$22)
        fx = self.make_fx()
        fx.ram[0x0D80] = 4
        fx.ram[0x0D90] = 2
        fx.ram[0x1A] = 0x35
        fx.run_jsl("Sprite_DekuScrub_Long", x=0, db=0x31)
        self.assertEqual(fx.ram[0x0D90], 2)
        _, _, low_addr, hi_addr = fx.oam_allocs[0]
        slots = fx.read_oam_slots(low_addr, hi_addr, 4)
        self.assertEqual([s[2] for s in slots], [0x22, 0x02, 0x00, 0x20])


if __name__ == "__main__":
    unittest.main()
