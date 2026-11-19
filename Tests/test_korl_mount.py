#!/usr/bin/env python3
"""Compiled 65816 LakeSnes tests for King of Red Lions Water Mount (Bank $60).

Assembles the real Bank $60 King of Red Lions ASM (Masks/korl_mount.asm +
Data/graphics/mounts/korl_sparse*.4bpp/.asm/.bin) chained together with the
real Bank $53 Epona runtime (Masks/horse_form.asm + Masks/horse_sparse_runtime.asm)
and DekuWings_NmiUpload sentinel into a 4 MiB LoROM image and runs real 65816
machine code on LakeSnes with hardware-accurate $43x2 auto-increment DMA.

Covers:
  1. Art packer --check & structural/palette/DMA-budget invariants (<= 960 B)
  2. All 12 KORL frames bit-exact VRAM upload, per-group Hull/Rider/Sail dedup,
     dropable safety, and 256 B dismount restore
  3. 4-dir + diagonal sailing physics, Wind Waker Sail Boost speed (2.91 px/f),
     Flippers bypass, and vanilla/Zora swim non-interference
  4. Boarding via R / parked anchor, Zora Mask non-hijack, boat-only button
     suppression, automatic shore docking, and manual R shore/water dismount
  5. Menu $0E safe-overlay hold vs unsafe restore & OAM priority/H-flip layout
  6. Cross-world Day/Night SP-3[9..15] palette refresh (Lyra Sea / Goron $B0)
  7. Full non-regression of Epona & Deku Wings with KORL_MOUNT_DEFINED = 1
"""
from __future__ import annotations

import ctypes as C
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "Tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402
from test_horse_vblank_budget import (  # noqa: E402
    HORSE_DISMOUNT_CD,
    HORSE_FRAME,
    HORSE_MARKER,
    HORSE_NPC_UPLOADED,
    HORSE_PAL_LOADED,
    HORSE_UPLOADED_FRAME,
    PROTECTED_VRAM_RANGES,
    STUB_DEKU_WINGS_NMI,
    STUB_DMA_CONT_8ADB,
    STUB_DMA_CONT_8B25,
    STUB_DMA_NATIVE_8A12,
    STUB_FRAME_END_SCAN,
    STUB_GET_TILE_ATTR,
    STUB_HORSE_GAME_TICK,
    STUB_KID_START,
    STUB_LOAD_DAYNIGHT,
    STUB_MAINTAIN_NPC,
    STUB_OFF_RANCH_NPC,
    STUB_OFF_RESTORE,
    STUB_PAL_ARMOR,
    STUB_RESET_LINK_GFX,
    STUB_SAVE_ANCHOR,
    STUB_SFX_PAN,
    STUB_SPRITE_SPAWN,
    VBlankBudgetFixture,
    find_lakesnes,
)

STUB_SWIM_CONTINUE = 0x07E4D3
STUB_RESET_SWIM = 0x07983A

# Exact KORL WRAM / SRAM addresses matching Masks/korl_mount.asm
KORL_MOUNTED = 0x7FF3D4
KORL_SAIL_ACTIVE = 0x7FF3D5
KORL_FRAME = 0x7FF3D6
KORL_UPLOADED_FRAME = 0x7FF3D7
KORL_PAL_LOADED = 0x7FF3D8
KORL_ANIM_TIMER = 0x7FF3D9
KORL_COOLDOWN = 0x7FF3DA
KORL_HAS_ANCHOR = 0x7FF3DB
KORL_ANCHOR_AREA = 0x7FF3DC
KORL_ANCHOR_DIR = 0x7FF3DD
KORL_ANCHOR_X = 0x7FF3DE
KORL_ANCHOR_Y = 0x7FF3E0
KORL_MARKER = 0x7FF3E2
KORL_LAST_WATER_X = 0x7FF3E4
KORL_LAST_WATER_Y = 0x7FF3E6
KORL_VEL_Y = 0x7FF3E8
KORL_VEL_X = 0x7FF3EA
KORL_DOCK_STATE = 0x7FF3EC
KORL_DOCK_SHEET = 0x7FF3ED
KORL_DOCK_FRAME = 0x7FF3EE
KORL_DOCK_UPLOADED = 0x7FF3EF
KORL_DOCK_CLEAR = 0x7FF3F0
KORL_DOCK_BOB_TIMER = 0x7FF3F1
KORL_DOCK_OAM = 0x7FF3F2
KORL_UNLOCKED = 0x7EF439

KORL_PROTECTED_VRAM = PROTECTED_VRAM_RANGES + [
    ("Boomerang top ($26)", 0x4260, 0x4280),
    ("Boomerang bot ($36)", 0x4360, 0x4380),
]


def _extract_horse_table_header() -> str:
    lines = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text().splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("assert "))


def assemble_korl_rom(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Masks").mkdir(exist_ok=True)
    (folder / "Masks/gfx").mkdir(exist_ok=True)
    (folder / "Data/graphics/mounts").mkdir(parents=True, exist_ok=True)

    for rel in [
        "Masks/horse_ground_clearance.asm",
        "Masks/horse_mounted_helpers.asm",
        "Masks/horse_sparse_runtime.asm",
        "Masks/horse_form.asm",
        "Masks/korl_mount.asm",
    ]:
        txt = (ROOT / rel).read_text()
        txt = re.sub(r"(?m)^(\s*)assert\s+read\d.*$", r"\1; [stripped]", txt)
        (folder / rel).write_text(txt)

    for bin_rel in [
        "Masks/gfx/horse_sparse.4bpp",
        "Masks/gfx/horse_item_restore.4bpp",
        "Masks/gfx/horse_ranch_restore.4bpp",
        "Masks/gfx/horse_palette.bin",
        "Masks/gfx/horse_npc_rows.4bpp",
        "Data/graphics/mounts/korl_sparse.4bpp",
        "Data/graphics/mounts/korl_palette.bin",
    ]:
        (folder / bin_rel).write_bytes((ROOT / bin_rel).read_bytes())

    (folder / "Masks/gfx/horse_sparse_tables.asm").write_text(_extract_horse_table_header() + "\n")
    (folder / "Data/graphics/mounts/korl_sparse_tables.asm").write_text(
        (ROOT / "Data/graphics/mounts/korl_sparse_tables.asm").read_text()
    )

    asm = folder / "fixture.asm"
    asm.write_text(
        f"""lorom
macro m8()
  SEP #$20
endmacro
macro a16()
  REP #$20
endmacro

!CurrentMask = $02B2
!ZoraDiving = $0AAB
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 1
!ENABLE_HORSE_CROWD_CHARGE = 0
!SideQuest2_RanchGirl = $01
!DEKU_WINGS_NMI_DEFINED = 1
!KORL_MOUNT_DEFINED = 1

InCutScene = $7EF303
SideQuestProg2 = $7EF3D8
LoadDayNightPaletteEffect = ${STUB_LOAD_DAYNIGHT:06X}
Palette_ArmorAndGloves = ${STUB_PAL_ARMOR:06X}
ResetToLinkGraphics = ${STUB_RESET_LINK_GFX:06X}
Sprite_SpawnDynamically = ${STUB_SPRITE_SPAWN:06X}
HorseGame_State = $7F5410
HorseGame_Tick = ${STUB_HORSE_GAME_TICK:06X}
HorseGame_KidStartCheck = ${STUB_KID_START:06X}
HorseForm_SuppressMountedButtons = $53E800
Horse_AnchorArea = $7E1EFE
Horse_OffState = $7F5400
Horse_OffClear = $7F5402
HorseForm_SaveOutdoorAnchor_Long = ${STUB_SAVE_ANCHOR:06X}
HorseForm_MaintainParkedNpc_Long = ${STUB_MAINTAIN_NPC:06X}
Horse_OffRestore = ${STUB_OFF_RESTORE:06X}
Horse_OffRanchNpc = ${STUB_OFF_RANCH_NPC:06X}
Horse_FrameEndScan = ${STUB_FRAME_END_SCAN:06X}
DekuWings_NmiUpload = ${STUB_DEKU_WINGS_NMI:06X}

SprX = $0D10
SprXH = $0D30
SprY = $0D00
SprYH = $0D20
SprAction = $0D80
SprFrame = $0DC0
SprMiscA = $0DA0
SprBulletproof = $0BA0

Horse_Marker           = $7E1EDE
Horse_State            = $7E1EE0
Horse_JumpTimer        = $7E1EE1
Horse_JumpCooldown     = $7E1EE2
Horse_JumpDir          = $7E1EE3
Horse_JumpZ            = $7E1EE4
Horse_AnimTimer        = $7E1EE5
Horse_Frame            = $7E1EE6
Horse_UploadedFrame    = $7E1EE7
Horse_NpcActive        = $7E1EE8
Horse_NpcFrame         = $7E1EE9
Horse_NpcUploadedFrame = $7E1EEA
Horse_PalLoaded        = $7E1EEB
Horse_DismountCooldown = $7E1EEC
Horse_HasAnchor        = $7E1EED
Horse_JumpStep         = $7E1EEE
Horse_PushTimer        = $7E1EEF
Horse_JumpStartX       = $7E1EF0
Horse_JumpStartY       = $7E1EF2
Horse_JumpEndX         = $7E1EF4
Horse_JumpEndY         = $7E1EF6
Horse_AnchorX          = $7E1EF8
Horse_AnchorY          = $7E1EFA
Horse_NpcSlot          = $7E1EFC
Horse_InteractDelay    = $7E1EFD

org $058000
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  LDA.b #$00 : RTL : NOP
  LDA.b #$00 : CLC : RTL
  RTL : NOP : NOP : NOP
org ${STUB_DEKU_WINGS_NMI:06X}
  RTL
org ${STUB_SFX_PAN:06X}
  LDA.b #$00 : RTL
org ${STUB_RESET_SWIM:06X}
  RTL
org ${STUB_GET_TILE_ATTR:06X}
  SEP #$30 : RTL

org $53E800
  RTS

org $538000
HorseGraphics:
  incbin "Masks/gfx/horse_sparse.4bpp"
HorseGraphics_End:
HorseItemRestore:
  incbin "Masks/gfx/horse_item_restore.4bpp"
HorseRanchRestore:
  incbin "Masks/gfx/horse_ranch_restore.4bpp"
  incsrc "Masks/gfx/horse_sparse_tables.asm"
HorsePalette:
  incbin "Masks/gfx/horse_palette.bin"
HorseNpcTail:
  incbin "Masks/gfx/horse_npc_rows.4bpp"
  incsrc "Masks/horse_form.asm"
assert pc() <= $53D000

org $53D000
  incsrc "Masks/horse_mounted_helpers.asm"
assert pc() <= $53E000

org $608000
KORL_Graphics:
  incbin "Data/graphics/mounts/korl_sparse.4bpp"
KORL_Graphics_End:
KORL_Palette:
  incbin "Data/graphics/mounts/korl_palette.bin"
  incsrc "Data/graphics/mounts/korl_sparse_tables.asm"
  incsrc "Masks/korl_mount.asm"
assert pc() <= $60C000

org $0DA120
  dw $00C0, $00C0, $00C0
org $0DA126
  dw $2000, $2000, $2000, $2000
"""
    )
    image = folder / "fixture.sfc"
    image.write_bytes(b"\x00" * 0x400000)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", asm.name, image.name],
        cwd=folder,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            image.with_suffix(".sym").read_text(),
        )
    }
    return image.read_bytes(), labels


class KorlFixture(VBlankBudgetFixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.tile_fn = lambda x, y: 0x08  # default: ALTTP deep water ($08)
        self.daynight_fn = lambda color, off: color  # default: midday (identity tint)
        self.reset_swim_calls = 0
        self.dma_reads: list[tuple[int, int, int, int]] = []
        self.stubs.update({
            STUB_SWIM_CONTINUE: "swim_continue",
            STUB_RESET_SWIM: "reset_swim",
            STUB_GET_TILE_ATTR: "get_tile_attr",
            STUB_LOAD_DAYNIGHT: "load_daynight",
        })

    def _write_mmio(self, off: int, val: int) -> None:
        if off == 0x420B:
            self.mmio[off] = val & 0xFF
            for ch in range(5):
                if not (val & (1 << ch)):
                    continue
                base = 0x4300 + ch * 0x10
                mode = self.mmio.get(base + 0, 0x01)
                bbus = self.mmio.get(base + 1, 0x18)
                src = self.mmio.get(base + 2, 0) | (self.mmio.get(base + 3, 0) << 8)
                bank = self.mmio.get(base + 4, 0)
                size = self.mmio.get(base + 5, 0) | (self.mmio.get(base + 6, 0) << 8)
                if size == 0:
                    size = 0x10000
                start_vram = self.vram_addr
                if (mode & 0x80) and bbus == 0x39:
                    # Hardware-accurate B->A SNES VRAM read ($2139/$213A):
                    # First word prefetched on $2116 write -> returned twice before advancing!
                    for i in range(size):
                        v_off = 0 if i < 2 else (i - 2)
                        vbyte = ((start_vram * 2) + v_off) & 0xFFFF
                        b = self.vram[vbyte]
                        dst_off = (src + i) & 0xFFFF
                        if bank == 0x7E:
                            self.ram[dst_off] = b
                        elif bank == 0x7F:
                            self.ram[0x10000 + dst_off] = b
                    new_src = (src + size) & 0xFFFF
                    self.mmio[base + 2] = new_src & 0xFF
                    self.mmio[base + 3] = (new_src >> 8) & 0xFF
                    self.mmio[base + 5] = 0
                    self.mmio[base + 6] = 0
                    self.vram_addr = (start_vram + max(0, (size - 2) // 2)) & 0xFFFF
                    self.dma_reads.append((start_vram, bank, src, size))
                else:
                    super()._write_mmio(0x420B, 1 << ch)
            return
        super()._write_mmio(off, val)

    def stub(self, name: str):
        c = self.cpu
        if name == "swim_continue":
            self.jumped_target = "swim_continue"
            return "STOP"
        if name == "reset_swim":
            self.reset_swim_calls += 1
            return False
        if name == "get_tile_attr":
            y = self.get(0x00) | (self.get(0x01) << 8)
            x8 = self.get(0x02) | (self.get(0x03) << 8)
            attr = self.tile_fn(x8 * 8, y)
            # Vanilla Overworld_GetTileAttrAtLocation ($00882E) clobbers DP $00-$07!
            self.word(0x04, 0xBEEF)
            self.word(0x06, 0x1DB4)
            c.mf, c.xf = True, True
            self.acc(attr)
            # Execute RTL at $008830 (after SEP #$30)
            c.pc = (STUB_GET_TILE_ATTR & 0xFFFF) + 2
            return True
        if name == "load_daynight":
            tinted = self.daynight_fn(c.a & 0xFFFF, c.x & 0xFFFF)
            c.a = tinted & 0xFFFF
            # Also write aux CGRAM $7EC300 + X like real LoadDayNightPaletteEffect
            aux = 0x7EC300 + (c.x & 0xFFFF)
            self.put(aux, tinted & 0xFF)
            self.put(aux + 1, (tinted >> 8) & 0xFF)
            return False  # execute RTL at stub
        return super().stub(name)

    def init_korl_mounted(self, frame: int = 4, facing: int = 6, sail: int = 0) -> None:
        self.word(KORL_MARKER, 0x4B4C)
        self.put(KORL_MOUNTED, 1)
        self.put(KORL_SAIL_ACTIVE, sail)
        self.put(KORL_FRAME, frame)
        self.put(KORL_UPLOADED_FRAME, 0xFF)
        self.put(KORL_PAL_LOADED, 0x01)
        self.put(KORL_COOLDOWN, 0)
        self.put(0x10, 0x09)
        self.put(0x11, 0x00)
        self.put(0x1B, 0x00)
        self.put(0x5D, 0x04)
        self.put(0x2F, facing)
        self.put(0x13, 0x0F)
        self.word(0x22, 0x0180)
        self.word(0x20, 0x0180)
        self.word(0xE2, 0x0100)
        self.word(0xE8, 0x0100)
        self.word(0x0ADC, 0x9200)
        self.word(0x0134, 0x3800)


class TestKorlMount(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="korl-mount-test-")
        d = Path(cls._tmp.name)
        lakesnes = find_lakesnes()
        lib_path = d / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes/cpu.c"),
                str(lakesnes / "snes/statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        cls.lib = C.CDLL(str(lib_path))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.rom, cls.labels = assemble_korl_rom(d / "build")
        cls.sparse_bin = (ROOT / "Data/graphics/mounts/korl_sparse.4bpp").read_bytes()
        cls.pal_bin = (ROOT / "Data/graphics/mounts/korl_palette.bin").read_bytes()
        cls.item_restore_bin = (ROOT / "Masks/gfx/horse_item_restore.4bpp").read_bytes()
        tbl = (ROOT / "Data/graphics/mounts/korl_sparse_tables.asm").read_text()
        cls.frame_ptrs = [
            [int(x, 16) for x in m]
            for m in re.findall(
                r"dw KORL_Graphics\+\$([0-9A-F]+),KORL_Graphics\+\$([0-9A-F]+),"
                r"KORL_Graphics\+\$([0-9A-F]+),KORL_Graphics\+\$([0-9A-F]+),KORL_Graphics\+\$([0-9A-F]+)",
                tbl,
            )
        ]
        cls.frame_has_sail = [
            int(x, 16)
            for x in re.search(r"KORL_Frame_HasSail:\s*\n\s*db\s+([^\n]+)", tbl).group(1).replace("$", "").split(",")
        ]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def make_fx(self) -> KorlFixture:
        fx = KorlFixture(self.lib, self.rom, self.labels)
        self.addCleanup(fx.close)
        return fx

    # ------------------------------------------------------------------
    # 1. Art Packer --check & Asset Contracts
    # ------------------------------------------------------------------
    def test_art_packer_check_mode_exits_zero(self):
        res = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/build_korl_art.py"), "--check"],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
        )
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertEqual(len(self.pal_bin), 14)
        self.assertEqual(len(self.frame_ptrs), 12)
        self.assertEqual(self.frame_has_sail, [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1])

    # ------------------------------------------------------------------
    # 2. All 12 Frames Bit-Exact VRAM, Per-Group Dedup & <= 960 B VBlank Budget
    # ------------------------------------------------------------------
    def test_all_12_frames_bit_exact_vram_and_dropable_safety(self):
        for frame in range(12):
            with self.subTest(frame=frame):
                fx = self.make_fx()
                fx.init_korl_mounted(frame=frame, sail=self.frame_has_sail[frame])
                fx.word(0x0AE0, 0xB280)
                fx.word(0x0AE2, 0xB2E0)

                # Step 1: Chained Horse_LinkDmaPrefix -> KORL_LinkDmaPrefix
                fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                self.assertEqual(fx.jumped_target, "dma_8adb")
                self.assertEqual(fx.get(KORL_PAL_LOADED), 0x81)

                # Step 2: Chained Horse_NmiUpload -> KORL_NmiUpload -> DekuWings_NmiUpload
                fx.dma_writes.clear()
                fx.word(0x04, 0x1234)
                fx.word(0x06, 0x5678)
                fx.run_jsl("Horse_NmiUpload", mf=True, xf=False, y=0xABCD)

                self.assertEqual(fx.get(KORL_UPLOADED_FRAME), frame)
                self.assertEqual(fx.get(KORL_PAL_LOADED), 0x01)
                self.assertEqual(fx.cpu.y, 0xABCD)
                self.assertEqual(fx.get(0x04) | (fx.get(0x05) << 8), 0x1234)
                self.assertEqual(fx.get(0x06) | (fx.get(0x07) << 8), 0x5678)

                # Animated tiles ($3800) MUST be skipped on upload frame; DekuWings still chained!
                self.assertFalse(any(s == 0x3800 for s, *_ in fx.dma_writes))
                self.assertEqual(len(fx.deku_wings_calls), 1)
                self.assertEqual(fx.deku_wings_calls[0]["4304"], 0x7E)
                self.assertEqual(fx.deku_wings_calls[0]["4314"], 0x7E)
                self.assertEqual(fx.deku_wings_calls[0]["4302"], 0x9200)

                # Dropable & Boomerang VRAM safety check
                for s, e, bk, src, sz in fx.dma_writes:
                    for pname, plo, phi in KORL_PROTECTED_VRAM:
                        self.assertTrue(
                            e <= plo or s >= phi,
                            f"Frame {frame} write [${s:04X}..${e:04X}) hit {pname} [${plo:04X}..${phi:04X})",
                        )

                # Total NMI DMA MUST be <= 960 B!
                total_bytes = sum(sz for *_, sz in fx.dma_writes)
                expected_bytes = 960 if self.frame_has_sail[frame] else 640
                self.assertEqual(total_bytes, expected_bytes)
                self.assertLessEqual(total_bytes, 960)

                # Bit-exact pixel verification for Hull, Rider, and Sail!
                p_hull, p_rider, p_s0, p_s1, p_sn = self.frame_ptrs[frame]
                self.assertEqual(fx.vram_slice(0x4000, 256), self.sparse_bin[p_hull : p_hull + 256])
                self.assertEqual(fx.vram_slice(0x4100, 256), self.sparse_bin[p_hull + 256 : p_hull + 512])
                self.assertEqual(fx.vram_slice(0x4080, 64), self.sparse_bin[p_rider : p_rider + 64])
                self.assertEqual(fx.vram_slice(0x4180, 64), self.sparse_bin[p_rider + 64 : p_rider + 128])
                if self.frame_has_sail[frame]:
                    self.assertEqual(fx.vram_slice(0x42A0, 64), self.sparse_bin[p_s0 : p_s0 + 64])
                    self.assertEqual(fx.vram_slice(0x43A0, 64), self.sparse_bin[p_s0 + 64 : p_s0 + 128])
                    self.assertEqual(fx.vram_slice(0x42C0, 64), self.sparse_bin[p_s1 : p_s1 + 64])
                    self.assertEqual(fx.vram_slice(0x43C0, 64), self.sparse_bin[p_s1 + 64 : p_s1 + 128])
                    self.assertEqual(fx.vram_slice(0x40A0, 32), self.sparse_bin[p_sn : p_sn + 32])
                    self.assertEqual(fx.vram_slice(0x41A0, 32), self.sparse_bin[p_sn + 32 : p_sn + 64])

    def test_per_group_dedup_steady_and_dismount_restore(self):
        fx = self.make_fx()
        fx.init_korl_mounted(frame=4)

        def nmi_step(frame: int) -> int:
            fx.put(KORL_FRAME, frame)
            fx.put(KORL_PAL_LOADED, 0x81)
            fx.dma_writes.clear()
            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            return sum(sz for s, _, _, _, sz in fx.dma_writes if s != 0x3800)

        # Cold mount Side Cruise A (frame 4): Hull 512 + Rider 128 = 640 B
        self.assertEqual(nmi_step(4), 640)
        # Steady unchanged frame 4: 0 B KORL DMA (only 1KB anim tile $3800 runs)
        self.assertEqual(nmi_step(4), 0)
        self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x3800, 0x0400)])
        # Cruise bob 4 -> 5 (same Rider): 512 B (Rider deduplicated!)
        self.assertEqual(nmi_step(5), 512)
        # Raise Wind Waker Sail 5 -> 11 (same Hull + same Rider!): ONLY 320 B Sail!
        self.assertEqual(nmi_step(11), 320)
        # Sail Boost billow+bob 11 -> 10 (same Rider!): 512 + 320 = 832 B (<= 960 B!)
        self.assertEqual(nmi_step(10), 832)
        # Lower Sail 10 -> 4 (same Hull + same Rider!): 0 B!
        self.assertEqual(nmi_step(4), 0)
        # Worst-case cold 90-degree turn with Sail raised (4 -> 6 Down Sail A): 512 + 128 + 320 = 960 B!
        self.assertEqual(nmi_step(6), 960)

        # Dismount restore (bit 7 clear -> restores 256 B $42A0/$43A0 native arrow cells, skips anim tiles!)
        fx.put(KORL_MOUNTED, 0)
        fx.put(KORL_PAL_LOADED, 0x00)
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(KORL_UPLOADED_FRAME), 0xFF)
        self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x42A0, 128), (0x43A0, 128)])
        self.assertEqual(fx.vram_slice(0x42A0, 128), self.item_restore_bin[64:192])
        self.assertEqual(fx.vram_slice(0x43A0, 128), self.item_restore_bin[256:384])

    # ------------------------------------------------------------------
    # 3. 4-Dir Sailing Physics & Wind Waker Sail Boost Speed (~2.91 px/f)
    # ------------------------------------------------------------------
    def test_sailing_physics_cruise_sail_boost_and_vanilla_passthrough(self):
        # 1) Vanilla / Zora swimming (KORL_Mounted == 0): untouched!
        fx0 = self.make_fx()
        fx0.put(KORL_MOUNTED, 0)
        fx0.put(0x5D, 0x04)
        fx0.put(0x27, 0x77)
        fx0.put(0x28, 0x88)
        fx0.run_jsl("KORL_SwimVelocityHook", mf=True, xf=True, db=0x07)
        self.assertIsNone(fx0.jumped_target)
        self.assertEqual((fx0.get(0x27), fx0.get(0x28)), (0, 0))

        # 2) Flippers bypass when mounted vs native passthrough when unmounted
        fx0.put(0x7EF356, 0x00)
        fx0.run_jsl("KORL_CheckFlippersOrBoat", mf=True, xf=True)
        self.assertEqual(fx0.cpu.a & 0xFF, 0)
        fx0.put(KORL_MOUNTED, 1)
        fx0.run_jsl("KORL_CheckFlippersOrBoat", mf=True, xf=True)
        self.assertEqual(fx0.cpu.a & 0xFF, 1)

        # 3) All 4 cardinal directions: Cruise (2.00 px/f) vs Sail Boost (2.91 px/f = $02E8)!
        dir_cases = [
            ("Up",    0x08, 0x00, -1,  0),
            ("Down",  0x04, 0x02, +1,  0),
            ("Left",  0x02, 0x04,  0, -1),
            ("Right", 0x01, 0x06,  0, +1),
        ]
        for name, pad, exp_face, sy, sx in dir_cases:
            for sail, exp_mag in ((0, 0x0200), (1, 0x02E8)):
                with self.subTest(dir=name, sail=sail):
                    fx = self.make_fx()
                    fx.init_korl_mounted(sail=sail)
                    fx.put(0xF0, pad)
                    total_y = 0
                    total_x = 0
                    for _ in range(60):
                        fx.jumped_target = None
                        fx.run_jsl("KORL_SwimVelocityHook", mf=True, xf=True, db=0x07)
                        self.assertEqual(fx.jumped_target, "swim_continue")
                        vy = fx.get(0x08) | (fx.get(0x09) << 8)
                        vx = fx.get(0x0A) | (fx.get(0x0B) << 8)
                        if vy >= 0x8000:
                            vy -= 0x10000
                        if vx >= 0x8000:
                            vx -= 0x10000
                        total_y += vy
                        total_x += vx
                    self.assertEqual(fx.get(0x2F), exp_face)
                    self.assertEqual(fx.get(0x67), pad)
                    # Final steady-state velocity must match exact target!
                    self.assertEqual(vy, sy * exp_mag)
                    self.assertEqual(vx, sx * exp_mag)
                    dist_px = abs(total_y if sy else total_x) / 256.0
                    if sail:
                        # Wind Waker Sail Boost: ~169..174 px in 60 frames (2.82..2.91 px/f)!
                        self.assertGreaterEqual(dist_px, 165.0)
                        self.assertLessEqual(dist_px, 180.0)
                    else:
                        # Normal cruise: ~117..120 px in 60 frames (~2.00 px/f)!
                        self.assertGreaterEqual(dist_px, 114.0)
                        self.assertLessEqual(dist_px, 122.0)

        # 4) Coast deceleration to 0 when D-pad released
        fx = self.make_fx()
        fx.init_korl_mounted(sail=1)
        fx.word(KORL_VEL_X, 0x02E8)
        fx.put(0xF0, 0x00)
        for _ in range(12):
            fx.run_jsl("KORL_SwimVelocityHook", mf=True, xf=True, db=0x07)
        self.assertEqual(fx.get(KORL_VEL_X) | (fx.get(KORL_VEL_X + 1) << 8), 0)

    # ------------------------------------------------------------------
    # 4. Mounting, Zora Protection, Automatic Shore Docking & Manual R Dismount
    # ------------------------------------------------------------------
    def test_boarding_shore_docking_and_zora_non_hijack(self):
        # 1) R while swimming (unlocked, Human Link) -> mounts KORL!
        fx = self.make_fx()
        fx.put(KORL_UNLOCKED, 0x01)
        fx.put(0x10, 0x09)
        fx.put(0x11, 0x00)
        fx.put(0x1B, 0x00)
        fx.put(0x5D, 0x04)
        fx.put(0x02B2, 0x00)
        fx.put(0x2F, 0x06)
        fx.put(0xF6, 0x10)  # Fresh R press
        fx.word(0x22, 0x0220)
        fx.word(0x20, 0x0190)
        fx.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_MOUNTED), 1)
        self.assertEqual(fx.get(0xF6) & 0x10, 0)
        self.assertEqual(fx.pal_armor_calls, 1)

        # 2) Boat-only button suppression + Sail Boost on A hold
        fx.put(KORL_COOLDOWN, 0)
        fx.put(0xF2, 0x80)  # A held
        fx.put(0xF6, 0xC0)  # A+X new presses
        fx.put(0xF4, 0xF0)  # B+Y+Select+Start new presses
        fx.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_SAIL_ACTIVE), 1)
        self.assertEqual(fx.get(0xF6) & 0xC0, 0)     # A/X suppressed!
        self.assertEqual(fx.get(0xF4) & 0xC0, 0)     # B/Y suppressed!
        self.assertEqual(fx.get(0xF4) & 0x30, 0x30)  # Start/Select preserved!

        # 3) Automatic shore dock when vanilla transitions $5D -> $06 (hop onto shore!)
        fx.word(0x22, 0x0240)
        fx.word(0x20, 0x0190)
        fx.put(0x5D, 0x06)
        fx.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_MOUNTED), 0)
        self.assertEqual(fx.get(KORL_HAS_ANCHOR), 1)
        self.assertEqual(fx.get(KORL_ANCHOR_X) | (fx.get(KORL_ANCHOR_X + 1) << 8), 0x0220)

        # 4) Manual R dismount onto adjacent walkable shore ($00 east of Link)
        fx2 = self.make_fx()
        fx2.init_korl_mounted(facing=6)
        fx2.put(KORL_UNLOCKED, 0x01)
        fx2.word(0x22, 0x0180)
        fx2.word(0x20, 0x0180)
        # Walkable ground ($00) or shallow water ($09) to the east (X >= 0x0190), deep water ($08) elsewhere
        fx2.tile_fn = lambda x, y: 0x09 if x >= 0x0190 else 0x08
        fx2.put(0xF6, 0x10)  # Fresh R press
        fx2.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx2.get(KORL_MOUNTED), 0)
        self.assertEqual(fx2.get(0x5D), 0x00)        # Standing cleanly on shore!
        self.assertEqual(fx2.get(0x0345), 0x00)      # Deep water flag cleared!
        self.assertEqual(fx2.get(0x22) | (fx2.get(0x23) << 8), 0x0194)
        self.assertEqual(fx2.get(KORL_HAS_ANCHOR), 1)
        self.assertEqual(fx2.get(KORL_ANCHOR_X) | (fx2.get(KORL_ANCHOR_X + 1) << 8), 0x0180)

        # 5) NO automatic remount when walking/swimming right beside moored boat!
        fx2.put(KORL_COOLDOWN, 0)
        fx2.put(0x5D, 0x04)  # Even if Link enters water right next to moored boat...
        fx2.put(0xF6, 0x00)  # ...with NO button pressed!
        fx2.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx2.get(KORL_MOUNTED), 0, "Boat MUST NOT auto-remount without A/R press!")

        # 6) Deliberate A press while standing on shore beside moored boat -> snaps & boards!
        fx2.put(0x5D, 0x00)
        fx2.put(0x0308, 0x00)
        fx2.put(0x3C, 0x00)
        fx2.put(0xF6, 0x80)  # Fresh A press!
        fx2.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx2.get(KORL_MOUNTED), 1, "Deliberate A beside moored boat must board!")
        self.assertEqual(fx2.get(0x22) | (fx2.get(0x23) << 8), 0x0180)
        self.assertEqual(fx2.get(0x20) | (fx2.get(0x21) << 8), 0x0180)
        self.assertEqual(fx2.get(0x5D), 0x04)

        # 7) Zora Mask ($02B2 == 2) MUST NOT be hijacked by R or docked anchor!
        fx3 = self.make_fx()
        fx3.put(KORL_UNLOCKED, 0x01)
        fx3.put(0x10, 0x09)
        fx3.put(0x1B, 0x00)
        fx3.put(0x5D, 0x04)
        fx3.put(0x02B2, 0x02)  # Zora Mask active!
        fx3.put(0xF6, 0x10)
        fx3.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx3.get(KORL_MOUNTED), 0)

    # ------------------------------------------------------------------
    # 4b. Visibly Docked Boat: Page 1 $5C00/$5D00 Save/Upload/OAM/Conflict/Restore
    # ------------------------------------------------------------------
    def test_visibly_docked_boat_vram_oam_menu_and_deferred_restore(self):
        fx = self.make_fx()
        fx.word(KORL_MARKER, 0x4B4C)
        fx.put(KORL_UNLOCKED, 0x01)
        fx.put(KORL_MOUNTED, 0)
        fx.put(KORL_UPLOADED_FRAME, 0xFF)
        fx.put(KORL_DOCK_UPLOADED, 0xFF)
        fx.put(KORL_HAS_ANCHOR, 1)
        fx.put(KORL_ANCHOR_AREA, 0x99)
        fx.put(KORL_ANCHOR_DIR, 6)  # Right-facing docked boat
        fx.word(KORL_ANCHOR_X, 0x0330)
        fx.word(KORL_ANCHOR_Y, 0x07A0)
        fx.put(KORL_DOCK_FRAME, 4)  # Side empty hull A
        fx.put(0x10, 0x09)
        fx.put(0x11, 0x00)
        fx.put(0x1B, 0x00)
        fx.put(0x8A, 0x99)
        fx.word(0xE2, 0x02B0)
        fx.word(0xE8, 0x0730)
        fx.put(0x7EC2FF, 0x52)  # Page 1 Slot 3 sheet ID
        fx.word(0x0134, 0x3800)

        # Fill native Page 1 $5C00-$5C7F & $5D00-$5D7F with recognizable sentinel bytes
        orig_top = bytes((0xA0 + (i % 53)) & 0xFF for i in range(256))
        orig_bot = bytes((0x40 + (i % 59)) & 0xFF for i in range(256))
        fx.vram[0x5C00 * 2 : 0x5C00 * 2 + 256] = orig_top
        fx.vram[0x5D00 * 2 : 0x5D00 * 2 + 256] = orig_bot

        # Clear OAM ($0800-$09FF) to $F0
        for i in range(128):
            fx.put(0x0801 + i * 4, 0xF0)

        # 2 conflict-free OAM frames -> KORL_DockClear reaches 2
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_DOCK_CLEAR), 2)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0)

        # NMI 1: saves $5C00/$5D00 (516 B VRAM read) -> state $A1, skips 1KB anim DMA!
        fx.dma_writes.clear()
        fx.dma_reads.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0xA1)
        self.assertEqual(sum(sz for *_, sz in fx.dma_reads), 516)
        self.assertEqual(len(fx.dma_writes), 0, "1KB anim DMA must be skipped on 516B VRAM save NMI!")
        self.assertEqual(bytes(fx.ram[0x15406 : 0x15406 + 256]), orig_top)
        self.assertEqual(bytes(fx.ram[0x15508 : 0x15508 + 256]), orig_bot)

        # NMI 2: promotes $A1->$A2 & uploads 512 B empty hull to $5C00/$5D00!
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0xA2)
        self.assertEqual(fx.get(KORL_DOCK_UPLOADED), 4)
        self.assertEqual(sum(sz for *_, sz in fx.dma_writes), 512)
        # Bit-exact check of empty hull tiles in VRAM $5C00 & $5D00!
        hull_off = self.frame_ptrs[4][0]
        self.assertEqual(bytes(fx.vram[0x5C00 * 2 : 0x5C00 * 2 + 256]), self.sparse_bin[hull_off : hull_off + 256])
        self.assertEqual(bytes(fx.vram[0x5D00 * 2 : 0x5D00 * 2 + 256]), self.sparse_bin[hull_off + 256 : hull_off + 512])

        # Frame-end emits 4 empty-hull OAM entries at $09F0..$09FC (CHR $C0,$C2,$C4,$C6, attr $27)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_DOCK_OAM) | (fx.get(KORL_DOCK_OAM + 1) << 8), 0x09F0)
        dock_chrs = [fx.get(0x09F0 + i * 4 + 2) for i in range(4)]
        dock_attrs = [fx.get(0x09F0 + i * 4 + 3) for i in range(4)]
        dock_ys = [fx.get(0x09F0 + i * 4 + 1) for i in range(4)]
        self.assertEqual(dock_chrs, [0xC0, 0xC2, 0xC4, 0xC6])
        self.assertEqual(dock_attrs, [0x27, 0x27, 0x27, 0x27])
        self.assertTrue(all(y != 0xF0 for y in dock_ys))

        # Steady docked NMI = 0 B KORL DMA (only 1KB anim tile DMA runs)
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x3800, 0x0400)])

        # Safe Pause Menu ($0E/$01): keeps docked OAM frozen & $5C00/$5D00 untouched!
        fx.put(0x10, 0x0E)
        fx.put(0x11, 0x01)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        self.assertTrue(all(fx.get(0x09F0 + i * 4 + 1) != 0xF0 for i in range(4)))
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0xA2)

        # Unsafe Overlay ($0E/$07, $0200=1): hides docked OAM BEFORE NMI restores $5C00/$5D00 bit-for-bit!
        fx.put(0x11, 0x07)
        fx.put(0x0200, 0x01)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        self.assertTrue(all(fx.get(0x09F0 + i * 4 + 1) == 0xF0 for i in range(4)))
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0)
        self.assertEqual(sum(sz for *_, sz in fx.dma_writes), 512)
        self.assertEqual(bytes(fx.vram[0x5C00 * 2 : 0x5C00 * 2 + 256]), orig_top)
        self.assertEqual(bytes(fx.vram[0x5D00 * 2 : 0x5D00 * 2 + 256]), orig_bot)

        # Re-dock & verify deferred restore when re-boarding (never > 960 B in 1 NMI!)
        fx.put(0x10, 0x09)
        fx.put(0x11, 0x00)
        fx.put(0x0200, 0x00)
        for i in range(128):
            fx.put(0x0801 + i * 4, 0xF0)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)  # Save ($A1)
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)  # Upload ($A2)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0xA2)

        # Now mount KORL! NMI 1 uploads mounted (640 B <= 960 B), NMI 2 restores $5C00/$5D00 (512 B <= 960 B)!
        fx.put(KORL_MOUNTED, 1)
        fx.put(KORL_FRAME, 4)
        fx.put(KORL_UPLOADED_FRAME, 0xFF)
        fx.put(KORL_PAL_LOADED, 0x01)
        fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(sum(sz for *_, sz in fx.dma_writes), 640)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0xA2, "Deferred restore waits for steady NMI!")

        fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(sum(sz for *_, sz in fx.dma_writes), 512)
        self.assertEqual(fx.get(KORL_DOCK_STATE), 0x00)
        self.assertEqual(bytes(fx.vram[0x5C00 * 2 : 0x5C00 * 2 + 256]), orig_top)
        self.assertEqual(bytes(fx.vram[0x5D00 * 2 : 0x5D00 * 2 + 256]), orig_bot)

        # Page 1 CHR $C2 OAM conflict immediately yields & clears KORL_DockClear -> 0!
        fx.put(KORL_MOUNTED, 0)
        fx.put(KORL_DOCK_CLEAR, 5)
        fx.put(0x0840 + 1, 0x60)  # visible enemy sprite
        fx.put(0x0840 + 2, 0xC2)  # uses Page 1 tile $C2!
        fx.put(0x0840 + 3, 0x21)  # Page 1 bit set!
        fx.run_jsl("KORL_FrameEndDockedOam", mf=True, xf=True)
        self.assertEqual(fx.get(KORL_DOCK_CLEAR), 0, "Page 1 $C2 OAM conflict must yield immediately!")

    # ------------------------------------------------------------------
    # 5. Menu $0E Safe-Overlay Hold/Restore & OAM Layering
    # ------------------------------------------------------------------
    def test_menu_overlay_safety_and_oam_layering(self):
        safe_cases = [(0x01, 0), (0x02, 0), (0x0B, 0), (0x04, 0), (0x08, 0), (0x09, 0), (0x07, 0), (0x0A, 0)]
        unsafe_cases = [(0x05, 0), (0x07, 1), (0x0A, 1), (0x03, 0)]

        for sub, s200 in safe_cases:
            fx = self.make_fx()
            fx.init_korl_mounted(frame=10, facing=6, sail=1)
            fx.put(0x10, 0x0E)
            fx.put(0x11, sub)
            fx.put(0x0200, s200)
            fx.put(KORL_UPLOADED_FRAME, 10)
            fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            self.assertEqual(fx.jumped_target, "dma_8adb", f"Safe $0E/${sub:02X} rejected!")
            self.assertEqual(fx.get(KORL_PAL_LOADED), 0x81)
            fx.dma_writes.clear()
            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            self.assertEqual(fx.get(KORL_UPLOADED_FRAME), 10)
            self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x3800, 0x0400)])

        for sub, s200 in unsafe_cases:
            fx = self.make_fx()
            fx.init_korl_mounted(frame=10, facing=6, sail=1)
            fx.put(0x10, 0x0E)
            fx.put(0x11, sub)
            fx.put(0x0200, s200)
            fx.put(KORL_UPLOADED_FRAME, 10)
            fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            self.assertEqual(fx.jumped_target, "dma_8a12", f"Unsafe $0E/${sub:02X} wrongly granted!")
            self.assertEqual(fx.get(KORL_PAL_LOADED) & 0x80, 0)
            # OAM hook MUST fall back to native Link OAM (returns Y=0, A=$11)
            fx.run_jsl("Horse_PlayerOamHook", mf=True, xf=True, db=0x0D)
            self.assertEqual(fx.cpu.y & 0xFF, 0x00)
            self.assertEqual(fx.cpu.a & 0xFF, sub)

        # Verify OAM layering: Side Sail (Left H-flip) emits Sail ($2A,$2C,$0A,$1A) -> Hull ($00..$06) -> Rider ($08)
        fx = self.make_fx()
        fx.init_korl_mounted(frame=10, facing=4, sail=1)  # Left + Wind Waker Sail!
        fx.run_jsl("KORL_DrawPlayerOam_Long", mf=True, xf=True)
        oam_base = 0x0800 + 0x00C0
        chrs = [fx.get(oam_base + i * 4 + 2) for i in range(9)]
        attrs = [fx.get(oam_base + i * 4 + 3) for i in range(9)]
        self.assertEqual(chrs, [0x2A, 0x2C, 0x0A, 0x1A, 0x00, 0x02, 0x04, 0x06, 0x08])
        # All Left-facing pieces must carry H-flip ($40) + SP-3 ($06) for boat/sail, SP-7 ($0E) for Link!
        for i in range(8):
            self.assertEqual(attrs[i] & 0x4E, 0x46)
        self.assertEqual(attrs[8] & 0x4E, 0x4E)
        # Unused slots 9..11 cleared offscreen ($F0)
        for i in range(9, 12):
            self.assertEqual(fx.get(oam_base + i * 4 + 1), 0xF0)

    # ------------------------------------------------------------------
    # 6. Cross-World Day/Night SP-3 Palette Refresh (Lyra Sea / Goron $B0)
    # ------------------------------------------------------------------
    def test_cross_world_sp3_palette_refresh(self):
        fx = self.make_fx()
        fx.init_korl_mounted(frame=4, facing=6)
        # Simulate Goron Coast ($B0) non-uniform green SP-3[15] overwriting $7EC67E
        fx.word(0x7EC67E, 0x0240)
        fx.run_jsl("KORL_FrameTick", mf=True, xf=True)
        # KORL_LoadPalette MUST have written all 7 BGR555 colors into $7EC672..$7EC67E!
        for i in range(7):
            got = fx.get(0x7EC672 + i * 2) | (fx.get(0x7EC673 + i * 2) << 8)
            exp = int.from_bytes(self.pal_bin[i * 2 : i * 2 + 2], "little")
            self.assertEqual(got, exp, f"SP-3[{9 + i}] mismatch")
        self.assertEqual(fx.get(0x15), 1)

        # Steady frame with matching $7EC67E MUST NOT spam INC $15!
        fx.put(0x15, 0)
        fx.run_jsl("KORL_FrameTick", mf=True, xf=True)
        self.assertEqual(fx.get(0x15), 0)

    # ------------------------------------------------------------------
    # 7. Non-Regression of Epona + Deku Wings with KORL_MOUNT_DEFINED = 1
    # ------------------------------------------------------------------
    def test_epona_and_deku_non_regression_with_korl_chained(self):
        fx = self.make_fx()
        fx.word(HORSE_MARKER, 0x4852)
        fx.put(0x02B2, 0x09)
        fx.put(HORSE_NPC_UPLOADED, 0xFF)
        fx.put(HORSE_UPLOADED_FRAME, 7)
        fx.put(HORSE_FRAME, 8)
        fx.put(HORSE_DISMOUNT_CD, 0)
        fx.put(KORL_MOUNTED, 0)
        fx.put(KORL_UPLOADED_FRAME, 0xFF)
        fx.put(0x10, 0x09)
        fx.put(0x11, 0x00)
        fx.word(0x0ADC, 0x9000)
        fx.word(0x0134, 0x3800)

        fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
        self.assertEqual(fx.jumped_target, "dma_8adb")
        self.assertEqual(fx.get(HORSE_PAL_LOADED) & 0x80, 0x80)

        fx.dma_writes.clear()
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
        self.assertEqual(fx.get(HORSE_UPLOADED_FRAME), 8)
        self.assertEqual(sum(sz for *_, sz in fx.dma_writes), 960)
        self.assertEqual(len(fx.deku_wings_calls), 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
