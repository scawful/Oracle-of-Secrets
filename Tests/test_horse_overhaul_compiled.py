#!/usr/bin/env python3
"""Compiled 65816 LakeSnes regression tests for the 6-item Epona Overhaul.

Assembles the real OoS 65816 modules (Masks/horse_form.asm,
Masks/horse_mounted_helpers.asm, Masks/horse_ground_clearance.asm,
Masks/horse_mounted_bow.asm, Masks/horse_park_anywhere.asm,
Masks/horse_sparse_runtime.asm, Masks/horse_charge.asm, Masks/bunny_hood.asm,
and Sprites/NPCs/horse.asm) into an isolated 4 MiB LoROM image and runs real
machine code on LakeSnes's C CPU core.

Covers all 6 deliverables:
  1. Dismounted Top-Left Ghost Bug (PrepOamCoord C=1 + 16-bit X/Y clip + Horse_OffOam=0)
  2. Removal of mid-screen enemy despawn + hot-loop caching + FrameEndScan early-out
  3. Fence-jump & long water-gap jump camera sync (Horse_SyncJumpCamera at $02BB90)
  4. Grounded B dismount, Y mounted Bow preservation, A spur stamina + speed decay
     + empty penalty regen, A lift/grab suppression ($F6/$F2/$3B/$3C/$5D), and
     5-carrot BG3 HUD ($7EC7C4..$7EC7CC) change-only $16 queueing
  5. Dismounted facing preservation ($2F <-> Horse_AnchorDir) + H-flip Left / N / S
     6-tile rendering + 192-frame in-place graze/head-bob idle (0 drift)
  6. WRAM layout safety ($7F5670..$7F568A < $7F5800; Menu/KORL ranges untouched)
"""
from __future__ import annotations

import ctypes as C
import os
import re
import shutil
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
    PROTECTED_VRAM_RANGES,
    STUB_DASH_TREMOR,
    STUB_DEKU_WINGS_NMI,
    STUB_DMA_CONT_8ADB,
    STUB_DMA_CONT_8B25,
    STUB_DMA_NATIVE_8A12,
    STUB_GET_TILE_ATTR,
    STUB_HORSE_GAME_TICK,
    STUB_KID_START,
    STUB_LOAD_DAYNIGHT,
    STUB_PAL_ARMOR,
    STUB_RESET_LINK_GFX,
    STUB_SFX_PAN,
    STUB_SPRITE_SPAWN,
    find_lakesnes,
)

# Additional external vanilla/engine stubs used by horse.asm, horse_park_anywhere.asm,
# horse_mounted_bow.asm, and bunny_hood.asm
STUB_HANDLE_OW_TILE_ACTION = 0x1BBD7A
STUB_PREP_OAM_COORD = 0x069C80
STUB_OAM_ALLOC_DEFER = 0x0681B0
STUB_SPRITE_CHECK_ACTIVE = 0x069D40
STUB_PLAYER_CANT_PASS = 0x06A310
STUB_FLOATER_BOY_CHECK = 0x058040
STUB_SPAWN_POOF = 0x099B20
STUB_GET_TILE16_ATTR = 0x07E000
STUB_MODULE_MAIN_ROUTING = 0x0080B5
STUB_COLOR_SUB_EFFECT = 0x07D100
STUB_LINK_TRANSFORM_MASK = 0x07D110
STUB_ANCILLA_SET_COORDS = 0x0990FC

# New Epona WRAM symbols in $7F5670..$7F57AB
HORSE_ANCHOR_DIR = 0x7F5670
HORSE_CARROTS = 0x7F5671
HORSE_SPUR_TIMER = 0x7F5672
HORSE_REGEN_TIMER = 0x7F5673
HORSE_HUD_STATE = 0x7F5674
HORSE_JUMP_PREV_X = 0x7F5675
HORSE_JUMP_PREV_Y = 0x7F5677
HORSE_JUMP_CAM_ACTIVE = 0x7F5679
HORSE_NPC_LAST_DIR = 0x7F568A
HORSE_MOMENTUM = 0x7F57A8
HORSE_PREV_MOVE_DIR = 0x7F57A9
HORSE_PREV_DPAD = 0x7F57AA
HUD_CARROT_TOP = 0x7EC866
HUD_CARROT_BOT = 0x7EC870


def _extract_horse_table_header() -> str:
    lines = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text().splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("assert "))


def assemble_overhaul_rom(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Core").mkdir(exist_ok=True)
    (folder / "Masks").mkdir(exist_ok=True)
    (folder / "Masks/gfx").mkdir(exist_ok=True)
    (folder / "Sprites/NPCs").mkdir(parents=True, exist_ok=True)

    for rel in [
        "Core/sprite_macros.asm",
        "Core/structs.asm",
        "Masks/horse_ground_clearance.asm",
        "Masks/horse_mounted_helpers.asm",
        "Masks/horse_sparse_runtime.asm",
        "Masks/horse_form.asm",
        "Masks/horse_park_anywhere.asm",
        "Masks/horse_mounted_bow.asm",
        "Masks/horse_minigame.asm",
        "Masks/horse_charge.asm",
        "Masks/bunny_hood.asm",
        "Sprites/NPCs/horse.asm",
    ]:
        txt = (ROOT / rel).read_text()
        txt = re.sub(r"(?m)^(\s*)assert\s+read\d.*$", r"\1; [stripped]", txt)
        (folder / rel).write_text(txt)

    # Strip the top macro/define header from horse_park_anywhere? No, it has none except ! defines.
    # Strip bunny_hood LinkItem_Ether JSR $9427? No, $079427 is a valid Bank $07 offset.
    for bin_rel in [
        "Masks/gfx/horse_sparse.4bpp",
        "Masks/gfx/horse_item_restore.4bpp",
        "Masks/gfx/horse_ranch_restore.4bpp",
        "Masks/gfx/horse_palette.bin",
        "Masks/gfx/horse_npc_rows.4bpp",
    ]:
        (folder / bin_rel).write_bytes((ROOT / bin_rel).read_bytes())

    (folder / "Masks/gfx/horse_sparse_tables.asm").write_text(_extract_horse_table_header() + "\n")

    asm = folder / "fixture.asm"
    asm.write_text(
        f"""lorom
macro x8()
  SEP #$10
endmacro

; Feature flags & core aliases matching Defaults + Overhaul
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 1
!DEKU_WINGS_NMI_DEFINED = 1
!NO_KORL_MOUNT = 1
!CurrentMask = $02B2
!ZoraDiving = $0AAB
!SideQuest2_RanchGirl = $01
!BowsEquipped = $7E0202

; WRAM / SRAM aliases
InCutScene = $7EF303
SideQuestProg2 = $7EF3D8
MenuMapTravel_Pending = $7E1EFF
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
Horse_AnchorArea = $7E1EFE
Horse_OffDma = $7F5000
Horse_OffBuf = $7F5002
Horse_OffState = $7F5402
Horse_OffClear = $7F5403
Horse_OffSheet = $7F5404
Horse_OffOam = $7F5405
KORL_Mounted = $7FF3D4
NewSprRoutinesLong = $308000
NewSprPrepRoutinesLong = $308300
SprMiscA = $0DA0
SprTimerB = $0E00
SprBulletproof = $0BA0
Sprite_KillSelf = $09F1F8
Sprite_SetupHitbox_long = $0683EA
SpriteIsNotActive = $069D48

; Sprite WRAM tables matching Core/symbols.asm
SprY = $0D00
SprX = $0D10
SprYH = $0D20
SprXH = $0D30
SprYVel = $0D40
SprXVel = $0D50
SprZ = $0F70
SprAction = $0D80
SprFrame = $0D90
SprState = $0DD0
SprMiscC = $0DE0
SprMiscF = $0EC0
SprMiscE = $0EB0
SprID = $0E20
SprType = $0E20
SprSubtype = $0E30
SprHarm = $0E40
SprHealth = $0E50
SprOAMProp = $0E60
SprProps = $0E40
SprGfxProps = $0F50
SprDefl = $0E60
SprTimerA = $0DF0
SprTimerC = $0E10
SprTimerD = $0EE0
SprObjCol = $0E70
SprCachedX = $0FD0
SprCachedY = $0FE0
SprDie = $0CD2
SprFloor = $0F20
SprFreeze = $0F00
SprBump = $0CAA
SprOam = $0F50
SprPause = $0F00

; New Epona Overhaul transient WRAM ($7F5670..$7F568A)
!Horse_OverhaulWramDefined = 1
Horse_AnchorDir        = $7F5670
Horse_Carrots          = $7F5671
Horse_SpurTimer        = $7F5672
Horse_RegenTimer       = $7F5673
Horse_HudState         = $7F5674
Horse_JumpPrevX        = $7F5675
Horse_JumpPrevY        = $7F5677
Horse_JumpCamActive    = $7F5679
Horse_PrioCacheX       = $7F567A
Horse_PrioCacheY       = $7F567C
Horse_PrioCacheDir     = $7F567E
Horse_PrioCacheArea    = $7F567F
Horse_PrioCacheState   = $7F5680
Horse_PrioCacheResult  = $7F5681
Horse_PrioCacheValid   = $7F5682
NewMainSprFunction = $068800
NewSprPrepFunction = $068900
Horse_TrampleCacheX    = $7F5683
Horse_TrampleCacheY    = $7F5685
Horse_TrampleCacheDir  = $7F5687
Horse_TrampleCacheArea = $7F5688
Horse_TrampleCacheValid = $7F5689
Horse_NpcLastDir       = $7F568A
Horse_PalCachedColor   = $7F568B
Horse_PalCachedHour    = $7F568D
Horse_PalCacheValid    = $7F568E
Horse_NorthCacheValid  = $7F568F
Horse_NorthCacheRes    = $7F5690
Horse_NorthCacheArea   = $7F5691
Horse_NorthCacheY8     = $7F5692
Horse_NorthCacheXL     = $7F5694
Horse_NorthCacheXR     = $7F5696
Horse_NorthCacheT16L   = $7F5698
Horse_NorthCacheT16R   = $7F569A
Horse_CgiCacheValid    = $7F569C
Horse_FrameFenceCheckedDir = $7F569D
Horse_CgiCache         = $7F56A0
Horse_SafeTile16Cache  = $7F5720
Horse_SafeTile16Valid  = $7F57A0
Horse_PrioFenceCacheHdr = $7F57A1
Horse_PrioFenceCacheRes = $7F57A3
Horse_PrioFenceCacheXZ = $7F57A4
Horse_PrioFenceCacheYZ = $7F57A6
!Horse_PolishWramDefined   = 1
Horse_Momentum         = $7F57A8
Horse_PrevMoveDir      = $7F57A9
Horse_PrevDpad         = $7F57AA
Horse_CgiCache_End     = $7F57AB
assert Horse_CgiCache_End < $7F5800
!Horse_CarrotHudWramDefined = 1
HudCarrotTopBuffer     = $7EC866
HudCarrotBotBuffer     = $7EC870

; External routines & vanilla hooks (HorseGame_*, Horse_HandleItemTileAction_Overworld defined by real ASM)
LoadDayNightPaletteEffect = ${STUB_LOAD_DAYNIGHT:06X}
Palette_ArmorAndGloves = ${STUB_PAL_ARMOR:06X}
ResetToLinkGraphics = ${STUB_RESET_LINK_GFX:06X}
Sprite_SpawnDynamically = ${STUB_SPRITE_SPAWN:06X}
Sprite_PrepOamCoord = ${STUB_PREP_OAM_COORD:06X}
Sprite_OAM_AllocateDeferToPlayer = ${STUB_OAM_ALLOC_DEFER:06X}
Sprite_CheckActive = ${STUB_SPRITE_CHECK_ACTIVE:06X}
Sprite_PlayerCantPassThrough = ${STUB_PLAYER_CANT_PASS:06X}
Sprite_SpawnPoofGarnish = ${STUB_SPAWN_POOF:06X}
FloaterBoySpriteCheck = ${STUB_FLOATER_BOY_CHECK:06X}
DekuWings_NmiUpload = ${STUB_DEKU_WINGS_NMI:06X}
ColorSubEffect = ${STUB_COLOR_SUB_EFFECT:06X}
Link_TransformMask = ${STUB_LINK_TRANSFORM_MASK:06X}
HorseForm_CheckMinigamePrompt = $058050
Horse_PlaySoundPan = ${STUB_SFX_PAN:06X}

incsrc "Core/sprite_macros.asm"
incsrc "Core/structs.asm"

; Sentinel return & stub landing pads
org $008000 : JML Horse_TestSentinel
org $538000 : Horse_TestSentinel: NOP

org ${STUB_PAL_ARMOR:06X} : RTL
org ${STUB_LOAD_DAYNIGHT:06X} : RTL
org ${STUB_RESET_LINK_GFX:06X} : RTL
org $058050 : RTL
org ${STUB_DEKU_WINGS_NMI:06X} : RTL
org ${STUB_FLOATER_BOY_CHECK:06X} : RTL
org ${STUB_SPAWN_POOF:06X} : RTL
org ${STUB_PLAYER_CANT_PASS:06X} : RTL
org ${STUB_SPRITE_CHECK_ACTIVE:06X} : SEC : RTL
org ${STUB_PREP_OAM_COORD:06X} : CLC : RTL
org ${STUB_OAM_ALLOC_DEFER:06X} : RTL
org ${STUB_SPRITE_SPAWN:06X} : LDA #$FF : RTL
org ${STUB_SFX_PAN:06X} : RTL
org ${STUB_DASH_TREMOR:06X} : CLC : RTL
org ${STUB_GET_TILE_ATTR:06X} : LDA #$00 : RTL
org ${STUB_HANDLE_OW_TILE_ACTION:06X} : SEP #$30 : RTL
org ${STUB_MODULE_MAIN_ROUTING:06X} : RTL
org ${STUB_COLOR_SUB_EFFECT:06X} : RTL
org ${STUB_LINK_TRANSFORM_MASK:06X} : RTL
org $079427 : RTS
org $09F1F8 : RTL
org $0683EA : RTL
org $069D48 : RTL

org $008ADB : NOP #8 : RTL
org $008B25 : NOP #8 : RTL
org $008A12 : NOP #8 : RTL
org $07E000 : RTL
org $0DA120 : dw $0000, $0030, $0060
org $0DA126 : dw $2020, $1010, $0000, $3030

; Include Bank $02 / Bank $07 / Bank $09 / Bank $20 / Bank $53 real implementations
org $538000
HorseGraphics:
  incbin "Masks/gfx/horse_sparse.4bpp"
HorseItemRestore:
  incbin "Masks/gfx/horse_item_restore.4bpp"
HorseRanchRestore:
  incbin "Masks/gfx/horse_ranch_restore.4bpp"
incsrc "Masks/gfx/horse_sparse_tables.asm"
HorsePalette:
  incbin "Masks/gfx/horse_palette.bin"
HorseNpcTail:
  incbin "Masks/gfx/horse_npc_rows.4bpp"
HorseArt_TestEnd:

incsrc "Masks/horse_form.asm"
assert pc() <= $53D000
incsrc "Sprites/NPCs/horse.asm"
incsrc "Masks/horse_mounted_bow.asm"

org $07F800
pushpc
incsrc "Masks/bunny_hood.asm"
pullpc
"""
    )

    sym = folder / "fixture.sym"
    out = folder / "fixture.sfc"
    out.write_bytes(b"\x00" * (4 * 1024 * 1024))
    res = subprocess.run(
        ["asar", "--no-title-check", f"--symbols-path={sym}", "--symbols=wla", str(asm), str(out)],
        cwd=folder,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if res.returncode != 0:
        raise RuntimeError(f"asar failed:\n{res.stderr}\n{res.stdout}")

    labels: dict[str, int] = {}
    in_labels = False
    for line in sym.read_text().splitlines():
        s = line.strip()
        if s == "[labels]":
            in_labels = True
            continue
        if s.startswith("["):
            in_labels = False
            continue
        if in_labels and ":" in s:
            loc, name = s.split(None, 1)
            bank, addr = loc.split(":")
            labels[name] = (int(bank, 16) << 16) | int(addr, 16)
    return out.read_bytes(), labels


class OverhaulFixture(Fixture):
    def __init__(self, lib: C.CDLL, rom: bytes, labels: dict[str, int]):
        self.vram = bytearray(0x10000)
        self.vram_addr = 0
        self.mmio: dict[int, int] = {}
        self.tile16_grid: dict[tuple[int, int], int] = {}
        self.tile_attr_fn = lambda wx, wy: 0x00
        self.prep_carry = False
        self.prep_x = 120
        self.prep_y = 120
        self.spawn_poof_calls = 0
        self.spawn_npc_slot = 0xFF
        self.link_dma_calls = 0
        self.tile_actions: list[tuple[int, int]] = []
        self.oam_alloc_calls = 0
        super().__init__(lib, rom, labels)
        self.stubs = {
            STUB_GET_TILE_ATTR: "get_tile_attr",
            STUB_PREP_OAM_COORD: "prep_oam",
            STUB_OAM_ALLOC_DEFER: "oam_alloc",
            STUB_SPRITE_CHECK_ACTIVE: "check_active",
            STUB_PLAYER_CANT_PASS: "rtl",
            STUB_SPRITE_SPAWN: "sprite_spawn",
            STUB_SPAWN_POOF: "spawn_poof",
            STUB_PAL_ARMOR: "rtl",
            STUB_LOAD_DAYNIGHT: "rtl",
            STUB_RESET_LINK_GFX: "reset_link_gfx",
            STUB_DEKU_WINGS_NMI: "rtl",
            STUB_SFX_PAN: "rtl",
            STUB_DASH_TREMOR: "rtl",
            STUB_FLOATER_BOY_CHECK: "rtl",
            STUB_MODULE_MAIN_ROUTING: "rtl",
            STUB_COLOR_SUB_EFFECT: "rtl",
            STUB_LINK_TRANSFORM_MASK: "rtl",
            STUB_HANDLE_OW_TILE_ACTION: "handle_tile_act",
            STUB_DMA_CONT_8ADB: "dma_8adb",
            STUB_DMA_CONT_8B25: "dma_8b25",
            STUB_DMA_NATIVE_8A12: "dma_8a12",
        }
        self.setup_base_overworld()

    def setup_base_overworld(self) -> None:
        self.put(0x7E0010, 0x09)
        self.put(0x7E0011, 0x00)
        self.put(0x7E001B, 0x00)
        self.put(0x7E008A, 0x00)
        self.put(0x7E002F, 0x06)
        self.put16(0x7E0022, 0x01C0)
        self.put16(0x7E0020, 0x0294)
        self.put16(0x7E00E2, 0x0140)
        self.put16(0x7E00E8, 0x0220)
        self.put16(0x7E0708, 0x0000)
        self.put16(0x7E070A, 0x03F0)
        self.put16(0x7E070C, 0x0000)
        self.put16(0x7E070E, 0x007E)
        self.put(0x7EC73A, 0x00)  # HUD visible (!= $7F)
        self.put(0x7E02B2, 0x00)

    def put16(self, addr: int, val: int) -> None:
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def get16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def set_tile16(self, tx: int, ty: int, tile16: int, attr: int = 0x00) -> None:
        self.tile16_grid[(tx, ty)] = tile16
        idx = ((ty * 64 + tx) * 2) & 0x1FFF
        self.put16(0x7E2000 + idx, tile16)
        old_fn = self.tile_attr_fn
        self.tile_attr_fn = lambda wx, wy, _tx=tx, _ty=ty, _a=attr, _prev=old_fn: (
            _a if (wx >> 4) == _tx and (wy >> 4) == _ty else _prev(wx, wy)
        )

    def _write_mmio(self, off: int, val: int) -> None:
        self.mmio[off] = val
        if off == 0x2116:
            self.vram_addr = (self.vram_addr & 0xFF00) | val
        elif off == 0x2117:
            self.vram_addr = (self.vram_addr & 0x00FF) | (val << 8)
        elif off == 0x420B and val:
            for ch in range(5):
                if val & (1 << ch):
                    base = 0x4300 + ch * 0x10
                    src = self.mmio.get(base + 2, 0) | (self.mmio.get(base + 3, 0) << 8)
                    bank = self.mmio.get(base + 4, 0)
                    size = self.mmio.get(base + 5, 0) | (self.mmio.get(base + 6, 0) << 8)
                    if size == 0:
                        size = 0x10000
                    for i in range(size):
                        b = self._read_bus_byte(bank, (src + i) & 0xFFFF)
                        self.vram[((self.vram_addr * 2) + i) & 0xFFFF] = b
                    new_src = (src + size) & 0xFFFF
                    self.mmio[base + 2] = new_src & 0xFF
                    self.mmio[base + 3] = (new_src >> 8) & 0xFF
                    self.vram_addr = (self.vram_addr + (size // 2)) & 0xFFFF

    def _read_bus_byte(self, bank: int, off: int) -> int:
        full = (bank << 16) | off
        if bank in (0x7E, 0x7F):
            return self.get(full)
        return self.read(full)

    def write(self, addr: int, val: int) -> None:
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (off in (0x2116, 0x2117, 0x420B) or 0x4300 <= off <= 0x434F):
            self._write_mmio(off, val)
            return
        if bank in (0x00, 0x80) and 0x4202 <= off <= 0x4206:
            self.mmio[off] = val
            if off == 0x4203:
                prod = self.mmio.get(0x4202, 0) * val
                self.mmio[0x4216] = prod & 0xFF
                self.mmio[0x4217] = (prod >> 8) & 0xFF
            elif off == 0x4206:
                num = self.mmio.get(0x4204, 0) | (self.mmio.get(0x4205, 0) << 8)
                if val:
                    q, r = divmod(num, val)
                else:
                    q, r = 0xFFFF, num
                self.mmio[0x4214] = q & 0xFF
                self.mmio[0x4215] = (q >> 8) & 0xFF
                self.mmio[0x4216] = r & 0xFF
                self.mmio[0x4217] = (r >> 8) & 0xFF
            return
        super().write(addr, val)

    def read(self, addr: int) -> int:
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (
            off in (0x2116, 0x2117, 0x420B) or 0x4202 <= off <= 0x4217 or 0x4300 <= off <= 0x434F
        ):
            return self.mmio.get(off, 0)
        return super().read(addr)

    def stub(self, name: str):
        c = self.cpu
        if name == "reset_link_gfx":
            self.put(0x02B2, 0x00)
            return False
        if name == "get_tile_attr":
            wx = self.get16(0x00)
            wy = self.get16(0x02)
            attr = self.tile_attr_fn(wx, wy)
            c.mf = True
            c.xf = True
            self.acc(attr)
            return False
        if name == "prep_oam":
            self.put16(0x00, self.prep_x & 0xFFFF)
            self.put16(0x02, self.prep_y & 0xFFFF)
            c.c = self.prep_carry
            return False
        if name == "oam_alloc":
            self.oam_alloc_calls += 1
            self.put16(0x90, 0x0800)
            self.put16(0x92, 0x0A20)
            return False
        if name == "check_active":
            c.c = True
            return False
        if name == "sprite_spawn":
            slot = self.spawn_npc_slot
            c.mf = True
            self.acc(slot)
            if slot != 0xFF:
                self.put(0x0DD0 + slot, 9)
                self.put(0x0E20 + slot, 0x2D)
            return False
        if name == "spawn_poof":
            self.spawn_poof_calls += 1
            return False
        if name == "handle_tile_act":
            self.tile_actions.append((self.get16(0x0C), self.get16(0x0A)))
            c.mf = True
            c.xf = True
            return False
        if name in ("dma_8adb", "dma_8b25", "dma_8a12"):
            self.link_dma_calls += 1
            return "STOP"
        return False

    def run_jsr(self, name: str, mf: bool = True, xf: bool = True, a: int = 0, x: int = 0, y: int = 0, db: int = 0) -> int:
        c = self.cpu
        c.db = db
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, 0x6F)
        self.put(sp - 1, 0xFF)
        c.sp -= 2
        for count in range(40000):
            addr = (c.k << 16) | c.pc
            if addr == ((entry & 0xFF0000) | 0x7000):
                assert c.sp == sp and not self.bad_writes, (name, hex(c.sp), hex(sp), self.bad_writes)
                return count
            if addr in self.stubs:
                r = self.stub(self.stubs[addr])
                if r == "STOP":
                    return count
                if r is True:
                    continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

    def run_jsl(self, name: str, mf: bool = True, xf: bool = True, a: int = 0, x: int = 0, y: int = 0, db: int = 0) -> int:
        c = self.cpu
        c.db = db
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        for count in range(40000):
            addr = (c.k << 16) | c.pc
            if addr == ((entry & 0xFF0000) | 0x7000):
                assert c.sp == sp and not self.bad_writes, (name, hex(c.sp), hex(sp), self.bad_writes)
                return count
            if addr in self.stubs:
                r = self.stub(self.stubs[addr])
                if r == "STOP":
                    return count
                if r is True:
                    continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

    def mount_link(self, direction: int = 6) -> None:
        self.put(HORSE_ANCHOR_DIR, direction)
        self.put(0x7E002F, direction)
        self.run_jsl("HorseForm_Mount")

    def read_oam_entries(self, count: int = 8) -> list[dict]:
        out = []
        for i in range(count):
            ox, oy, ch, pr = (self.get(0x0800 + i * 4 + j) for j in range(4))
            hi = (self.get(0x0A20 + (i >> 2)) >> ((i & 3) * 2)) & 3
            out.append({
                "x": ox + (256 if (hi & 1) else 0),
                "y": oy,
                "chr": ch,
                "props": pr,
                "large": bool(hi & 2),
                "x9": hi & 1,
            })
        return out


class TestHorseOverhaul(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lakesnes = find_lakesnes()
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="horse-overhaul-")
        d = Path(cls._tmpdir.name)
        lib_path = d / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes" / "cpu.c"),
                str(lakesnes / "snes" / "statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        cls._lib = C.CDLL(str(lib_path))
        cls._lib.cpu_init.restype = C.POINTER(Cpu)
        cls._lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls._lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls._rom, cls._labels = assemble_overhaul_rom(d / "build")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def make_fixture(self) -> OverhaulFixture:
        fx = OverhaulFixture(self._lib, self._rom, self._labels)
        self.addCleanup(fx.close)
        return fx

    # === 0. WRAM & BANK BOUNDS + KORL MERGE GUARD ===
    def test_bank_bounds_and_wram_safety(self):
        self.assertLessEqual(self._labels["HorseNpc_End"], 0x53D800)
        self.assertLessEqual(self._labels["HorseMountedHelpers_End"], 0x53E000)
        self.assertLessEqual(self._labels["HorseGroundClearance_End"], 0x53E800)
        self.assertLessEqual(self._labels["HorseMountedBow_End"], 0x53F000)
        self.assertLessEqual(self._labels["HorseBushTrample_End"], 0x53F400)
        self.assertLess(self._labels["Horse_SyncJumpCamera"], 0x53E000)
        self.assertLess(self._labels["HorseForm_UpdateAnimFrame_Impl"], 0x53EFF0)
        self.assertLess(self._labels["Horse_EmitFootReaction_Long"], 0x540000)
        self.assertLessEqual(self._labels["HorseBank5EHelpers_End"], 0x5F0000)

        # WRAM invariants: $7F5670..$7F568A < $7F5800, KORL $7FF3D4 untouched, MenuMapTravel_Pending $7E1EFF untouched
        self.assertEqual(self._labels["Horse_AnchorDir"], 0x7F5670)
        self.assertEqual(self._labels["Horse_NpcLastDir"], 0x7F568A)
        self.assertLess(self._labels["Horse_NpcLastDir"], 0x7F5800)
        self.assertEqual(self._labels["MenuMapTravel_Pending"], 0x7E1EFF)

        # Ensure Masks/horse_park_anywhere.asm .reset/.done KORL merge point is preserved cleanly
        park_src = (ROOT / "Masks/horse_park_anywhere.asm").read_text().splitlines()
        self.assertIn("  .reset", park_src[224:236])
        self.assertIn("  .done", park_src[224:236])

    # === 1. DELIVERABLE 1: DISMOUNTED TOP-LEFT GHOST BUG ===
    def test_npc_draw_hides_all_when_prep_oam_returns_carry(self):
        fx = self.make_fixture()
        fx.put(0x0EC0, 0)  # SprMiscF[0] = 0
        fx.put(0x0CAA, 0x80)
        fx.put16(0x7F5405, 0x0800)  # stale Horse_OffOam
        fx.prep_carry = True
        fx.prep_x, fx.prep_y = 20, 20  # would otherwise look on-screen!

        fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)

        self.assertEqual(fx.get16(0x7F5405), 0x0000, "Offscreen Epona must clear Horse_OffOam")
        self.assertEqual(fx.oam_alloc_calls, 0, "C=1 must skip OAM allocation completely")

    def test_npc_draw_16bit_x_clip_prevents_256px_wrap_ghost(self):
        # 1) Completely off-screen horizontally (>256 px): coarse guard skips OAM allocation completely.
        for bad_x in (0x0130, 0xFFCE):
            with self.subTest(coarse_offscreen_x=hex(bad_x)):
                fx = self.make_fixture()
                fx.put(HORSE_ANCHOR_DIR, 6)
                fx.put(0x7F5402, 0)
                fx.put16(0x7F5405, 0x0800)
                fx.prep_carry = False
                fx.prep_x, fx.prep_y = bad_x, 80

                fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)

                self.assertEqual(fx.get16(0x7F5405), 0x0000)
                self.assertEqual(fx.oam_alloc_calls, 0)

        # 2) Just outside edge (passes coarse guard +-0x30, but every sub-tile is outside [-16..255]):
        #    every allocated tile must be written Y=$F0 and Horse_OffOam cleared to 0.
        for edge_x in (0x0118, 0xFFD8):
            with self.subTest(per_tile_offscreen_x=hex(edge_x)):
                fx = self.make_fixture()
                fx.put(HORSE_ANCHOR_DIR, 6)
                fx.put(0x7F5402, 0)
                fx.put16(0x7F5405, 0x0800)
                fx.prep_carry = False
                fx.prep_x, fx.prep_y = edge_x, 80

                fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)

                self.assertEqual(fx.get16(0x7F5405), 0x0000)
                entries = fx.read_oam_entries(8)
                self.assertTrue(all(e["y"] == 0xF0 for e in entries), f"Wrap ghost at {edge_x:#x}: {entries}")

    def test_npc_draw_partial_screen_edge_clips_only_offscreen_tiles(self):
        fx = self.make_fixture()
        fx.put(HORSE_ANCHOR_DIR, 6)
        fx.prep_carry = False
        # screen_x = 250 ($00FA): x_offset +18 = 268 (>=256, <272 -> clipped),
        # while x_offset -14 = 236 stays visible.
        fx.prep_x, fx.prep_y = 250, 120

        fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)

        entries = fx.read_oam_entries(8)
        visible_xs = [e["x"] for e in entries if e["y"] != 0xF0]
        self.assertTrue(len(visible_xs) > 0)
        self.assertTrue(all(vx < 256 for vx in visible_xs), f"Wrapped tile leaked to left edge: {entries}")

    # === 2. DELIVERABLE 2: ZERO MID-SCREEN ENEMY DESPAWN + HOT-LOOP CACHE ===
    def test_throttle_hostiles_never_deletes_active_enemies_midscreen(self):
        fx = self.make_fixture()
        fx.mount_link(6)
        for s in range(8):
            fx.put(0x0DD0 + s, 0x09)
            fx.put(0x0E20 + s, 0x08)  # Octorok
            fx.put16(0x0D10 + s, 0x01C0)  # handled below: proper low/high bytes
            fx.put(0x0D10 + s, 0xC0 + s * 4)
            fx.put(0x0D30 + s, 0x01)
            fx.put(0x0D00 + s, 0x90)
            fx.put(0x0D20 + s, 0x02)

        fx.run_jsr("HorseForm_ThrottleHostiles")

        alive = [fx.get(0x0DD0 + s) for s in range(8)]
        self.assertEqual(alive, [0x09] * 8, "Mid-screen active enemies must never be despawned!")

    def test_fence_priority_cache_saves_cycles_and_invalidates_on_move(self):
        fx = self.make_fixture()
        fx.mount_link(6)
        fx.put16(0x0022, 0x0100)
        fx.put16(0x0020, 0x0100)
        fx.set_tile16(16, 16, 0x0078, attr=0x01)  # fence tile in footprint

        ins_miss = fx.run_jsr("Horse_ApplyFencePriority")
        self.assertEqual(fx.get(0x64) & 0x30, 0x30)
        self.assertEqual(fx.get(0x65) & 0x30, 0x30)

        fx.put(0x64, 0x00)
        fx.put(0x65, 0x00)
        ins_hit = fx.run_jsr("Horse_ApplyFencePriority")
        self.assertEqual(fx.get(0x64) & 0x30, 0x30)
        self.assertEqual(fx.get(0x65) & 0x30, 0x30)
        self.assertLess(ins_hit, ins_miss // 2, f"Cache hit ({ins_hit}) should be >2x faster than miss ({ins_miss})")

        # Moving out of fence clears priority on next miss
        fx.put16(0x0022, 0x0040)
        fx.put16(0x0020, 0x0040)
        fx.put(0x64, 0x00)
        fx.put(0x65, 0x00)
        fx.run_jsr("Horse_ApplyFencePriority")
        self.assertEqual(fx.get(0x64) & 0x30, 0x00)
        self.assertEqual(fx.get(0x65) & 0x30, 0x00)

    def test_frame_end_scan_early_outs_when_off_ranch_inactive(self):
        fx = self.make_fixture()
        fx.put(0x7F5402, 0x00)  # Horse_OffState = 0
        fx.put(0x7E008A, 0x18)  # non-ranch area
        fx.put(0x7E0011, 0x00)
        # Pre-seed an OAM tile at slot 0; early-out skips scanning all 128 slots.
        ins = fx.run_jsl("Horse_FrameEndScan")
        self.assertLess(ins, 40, f"Horse_FrameEndScan should fast-path early out ({ins} ops)")

    # === 3. DELIVERABLE 3: JUMP CAMERA SYNC (FENCE + LONG WATER GAP) ===
    def test_fence_jump_and_long_jump_drive_sync_jump_camera(self):
        # Fence jump (16 frames)
        fx = self.make_fixture()
        fx.mount_link(6)
        fx.put(0x7E1EE0, 0x01)   # Horse_State = jumping
        fx.put(0x7E1EE4, 0x00)   # step 0
        fx.put16(0x7E0022, 0x01C0)
        fx.put16(0x7E0020, 0x0280)
        fx.put16(0x7E1EF0, 0x01C0)  # JumpStartX
        fx.put16(0x7E1EF2, 0x0280)  # JumpStartY
        fx.put16(0x7E1EF4, 0x01F0)  # JumpEndX (+48px across fence)
        fx.put16(0x7E1EF6, 0x0280)  # JumpEndY

        fx.run_jsr("HorseForm_JumpTick")
        self.assertEqual(fx.get(HORSE_JUMP_CAM_ACTIVE), 1)
        prev_x = fx.get16(HORSE_JUMP_PREV_X)
        cur_x = fx.get16(0x0022)
        self.assertGreater(cur_x, prev_x)

        fx.run_jsl("Horse_SyncJumpCamera", mf=False, xf=False, db=0x00)
        self.assertEqual(fx.get(HORSE_JUMP_CAM_ACTIVE), 0)
        self.assertEqual(fx.get(0x31), (cur_x - prev_x) & 0xFF)
        self.assertEqual(fx.get(0x30), 0)

        # Long water-gap jump (Horse_JumpTimer = 18)
        fx2 = self.make_fixture()
        fx2.mount_link(2)  # South
        fx2.put(0x7E1EE0, 0x01)
        fx2.put(0x7E1EE1, 18)    # Horse_JumpTimer = 18
        fx2.put(0x7E1EEE, 0x00)  # Horse_JumpStep = 0
        fx2.put16(0x7E0022, 0x0200)
        fx2.put16(0x7E0020, 0x0100)
        fx2.put16(0x7E1EF0, 0x0200)
        fx2.put16(0x7E1EF2, 0x0100)
        fx2.put16(0x7E1EF4, 0x0200)
        fx2.put16(0x7E1EF6, 0x0140)  # +64px South across water gap

        fx2.run_jsr("HorseForm_JumpTick")
        self.assertEqual(fx2.get(HORSE_JUMP_CAM_ACTIVE), 1)
        prev_y = fx2.get16(HORSE_JUMP_PREV_Y)
        cur_y = fx2.get16(0x0020)
        self.assertGreater(cur_y, prev_y)

        fx2.run_jsl("Horse_SyncJumpCamera", mf=False, xf=False, db=0x00)
        self.assertEqual(fx2.get(HORSE_JUMP_CAM_ACTIVE), 0)
        self.assertEqual(fx2.get(0x30), (cur_y - prev_y) & 0xFF)
        self.assertEqual(fx2.get(0x31), 0)

    # === 4. DELIVERABLE 4: B DISMOUNT, Y BOW, A SPUR DECAY, NO LIFT, 5-CARROT HUD ===
    def test_b_dismount_grounded_and_blocked_midjump(self):
        fx = self.make_fixture()
        fx.mount_link(4)

        # Mid-jump B is consumed (no sword swing) and does NOT dismount!
        fx.put(0x7E1EE0, 0x01)
        fx.put(0xF4, 0x80)
        fx.run_jsr("Horse_TryBDismount")
        self.assertFalse(fx.cpu.c)
        self.assertEqual(fx.get(0xF4) & 0x80, 0x00)
        self.assertEqual(fx.get(0x02B2), 0x09)

        # Grounded B dismounts, saves facing, and clears HUD carrots above clock!
        fx.put(0x7E1EE0, 0x00)
        fx.put(0x002F, 0x04)
        fx.put(0xF4, 0x80)
        fx.put(0xF6, 0x80)
        fx.run_jsr("Horse_TryBDismount")
        self.assertTrue(fx.cpu.c)
        self.assertEqual(fx.get(0x02B2), 0x00)
        self.assertEqual(fx.get(HORSE_ANCHOR_DIR), 0x04)
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x01)
        for i in range(5):
            self.assertEqual(fx.get16(HUD_CARROT_TOP + i * 2), 0x207F)
            self.assertEqual(fx.get16(HUD_CARROT_BOT + i * 2), 0x207F)
            self.assertEqual(fx.get16(0x7EC7C4 + i * 2), 0x0000)

    def test_a_spur_decay_regen_and_lift_suppression_and_y_bow(self):
        fx = self.make_fixture()
        fx.mount_link(6)
        self.assertEqual(fx.get(HORSE_CARROTS), 5)

        # 7-tier acceleration pickup curve across Horse_Momentum 0..24 ($1A..$24 card, $14..$1E diag)
        expected_card = [(0, 0x1A), (4, 0x1C), (8, 0x1E), (12, 0x20), (16, 0x22), (20, 0x23), (24, 0x24)]
        expected_diag = [(0, 0x14), (4, 0x16), (8, 0x18), (12, 0x19), (16, 0x1B), (20, 0x1C), (24, 0x1E)]
        for mom, want_c in expected_card:
            fx.put(HORSE_MOMENTUM, mom)
            fx.run_jsl("HorseSpeed_GetSubVel", x=0)
            self.assertEqual(fx.cpu.a & 0xFF, want_c)
        for mom, want_d in expected_diag:
            fx.put(HORSE_MOMENTUM, mom)
            fx.run_jsl("HorseSpeed_GetSubVel", x=1)
            self.assertEqual(fx.cpu.a & 0xFF, want_d)
        fx.run_jsl("HorseSpeed_GetSubVel", x=13)
        self.assertEqual(fx.cpu.a & 0xFF, 0x1A)
        fx.put(HORSE_MOMENTUM, 0)

        # A spur spends 1 carrot, pops Momentum=24, suppresses A lift/grab, preserves Y Bow
        fx.put(0xF6, 0xC0)   # A + Y pressed
        fx.put(0xF2, 0xC0)   # A + Y held
        fx.put(0x3B, 0x80)   # A latch
        fx.put(0x3C, 0x02)
        fx.put(0x0308, 0x01)
        fx.put(0x0376, 0x01)
        fx.put(0x02EC, 0x05)
        fx.put(0x5D, 0x11)   # LinkState 11 carrying/grabbing
        fx.put(0x7E0202, 0x01)  # Bow equipped -> keep Y ($F6 & $40)
        fx.run_jsr("HorseForm_SuppressMountedButtons")  # leaves Y alone when bow equipped
        self.assertEqual(fx.get(0xF6) & 0x40, 0x40, "Y bow press must remain intact")
        self.assertEqual(fx.get(0x5D), 0x11, "Pre-move control tick hasn't run yet; Y kept")

        # Now run PreMoveControlTick while $5D=0 (grounded): spends carrot & clears ALL lift state
        fx.put(0x5D, 0x00)
        fx.put(0xF6, 0xC0)
        fx.put(0xF2, 0x80)
        fx.put(0x3B, 0x80)
        fx.put(0x3C, 0x03)
        fx.put(0x0308, 0x02)
        fx.put(0x0376, 0x01)
        fx.put(0x02EC, 0x04)
        fx.put(0x50, 0x01)
        fx.put(0x3A, 0x00)
        fx.run_jsl("Horse_PreMoveControlTick")
        self.assertEqual(fx.get(HORSE_CARROTS), 4)
        self.assertEqual(fx.get(HORSE_SPUR_TIMER), 48)
        self.assertEqual(fx.get(HORSE_MOMENTUM), 24)
        self.assertEqual(fx.get(0x012E), 0x20)
        self.assertEqual(fx.get(0xF6) & 0x80, 0x00)
        self.assertEqual(fx.get(0xF2) & 0x80, 0x00)
        self.assertEqual(fx.get(0x3B) & 0x80, 0x00)
        self.assertEqual(fx.get(0x3C), 0x00)
        self.assertEqual(fx.get(0x0308), 0x00)
        self.assertEqual(fx.get(0x0376), 0x00)
        self.assertEqual(fx.get(0x02EC), 0x00)
        self.assertEqual(fx.get(0x50) & 0x01, 0x00)

        # Mounted bow hold ($3A & $40) preserves $50 dir lock cleanly
        fx.put(0x50, 0x01)
        fx.put(0x3A, 0x40)
        fx.put(0xF6, 0x00)
        fx.run_jsl("Horse_PreMoveControlTick")
        self.assertEqual(fx.get(0x50) & 0x01, 0x01)
        fx.put(0x3A, 0x00)

        # $5D == $11 is also force-exited
        fx.put(0x5D, 0x11)
        fx.put(0xF6, 0x00)
        fx.run_jsl("Horse_PreMoveControlTick")
        self.assertEqual(fx.get(0x5D), 0x00)

        # Peak burst speed ($32 cardinal, $29 diagonal), smooth decay down to sustained $24/$1E
        fx.run_jsl("HorseSpeed_GetSubVel", x=0)
        self.assertEqual(fx.cpu.a & 0xFF, 0x32)
        fx.run_jsl("HorseSpeed_GetSubVel", x=1)
        self.assertEqual(fx.cpu.a & 0xFF, 0x29)

        fx.put(0x2F, 6)      # Right
        fx.put(0xF0, 0x01)   # holding Right
        speeds = []
        for _ in range(48):
            fx.run_jsr("Horse_PostMoveDecayTick")
            fx.run_jsl("HorseSpeed_GetSubVel", x=0)
            speeds.append(fx.cpu.a & 0xFF)
        self.assertEqual(fx.get(HORSE_SPUR_TIMER), 0)
        self.assertEqual(speeds[-1], 0x24)
        self.assertTrue(all(speeds[i] >= speeds[i + 1] for i in range(len(speeds) - 1)))

        # Cornering physics: diagonal-assisted bank caps momentum at 18+1=19; sharp 90 snap caps at 10+1=11 & scrubs spur 12
        fx.put(HORSE_MOMENTUM, 24); fx.put(HORSE_PREV_MOVE_DIR, 6); fx.put(HORSE_PREV_DPAD, 0x09)  # Right+Up
        fx.put(0x2F, 0); fx.put(0xF0, 0x08)  # finish banking to Up
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_MOMENTUM), 19)

        fx.put(HORSE_MOMENTUM, 24); fx.put(HORSE_SPUR_TIMER, 30)
        fx.put(HORSE_PREV_MOVE_DIR, 6); fx.put(HORSE_PREV_DPAD, 0x01)  # pure Right
        fx.put(0x2F, 0); fx.put(0xF0, 0x08)  # snap 90 to pure Up
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_MOMENTUM), 11)
        self.assertEqual(fx.get(HORSE_SPUR_TIMER), 17)  # 30 - 1 tick - 12 snap scrub

        # 180-degree reversal resets momentum & spur cleanly (starts +1 from 0 -> 1)
        fx.put(HORSE_MOMENTUM, 24); fx.put(HORSE_SPUR_TIMER, 25)
        fx.put(HORSE_PREV_MOVE_DIR, 6); fx.put(HORSE_PREV_DPAD, 0x01)
        fx.put(0x2F, 4); fx.put(0xF0, 0x02)  # Right -> Left
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_MOMENTUM), 1)
        self.assertEqual(fx.get(HORSE_SPUR_TIMER), 0)

        # Shallow water / tall grass caps unspurred momentum at 12, unless spurring
        fx.put(HORSE_MOMENTUM, 24); fx.put(HORSE_SPUR_TIMER, 0); fx.put(0x0351, 1)
        fx.put(HORSE_PREV_MOVE_DIR, 4); fx.put(0x2F, 4); fx.put(0xF0, 0x02)
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_MOMENTUM), 12)
        fx.put(HORSE_MOMENTUM, 24); fx.put(HORSE_SPUR_TIMER, 20)
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_MOMENTUM), 24)
        fx.put(0x0351, 0)

        # Stop resets burst immediately and decays Momentum by -3/frame
        fx.put(HORSE_SPUR_TIMER, 40)
        fx.put(HORSE_MOMENTUM, 9)
        fx.put(0xF0, 0x00)  # D-pad released
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_SPUR_TIMER), 0)
        self.assertEqual(fx.get(HORSE_MOMENTUM), 6)

        # Spend down to 0 carrots -> empty penalty delay (135 frames) -> regenerates
        fx.put(HORSE_CARROTS, 1)
        fx.put(HORSE_REGEN_TIMER, 0)
        fx.put(0xF6, 0x80)
        fx.run_jsl("Horse_PreMoveControlTick")
        self.assertEqual(fx.get(HORSE_CARROTS), 0)
        self.assertEqual(fx.get(HORSE_REGEN_TIMER), 135)
        fx.put(HORSE_SPUR_TIMER, 0)
        fx.put(0xF0, 0x01)
        for _ in range(134):
            fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_CARROTS), 0)
        fx.run_jsr("Horse_PostMoveDecayTick")
        self.assertEqual(fx.get(HORSE_CARROTS), 1)

    def test_carrot_hud_queues_vblank_only_on_change_and_clears_on_menu_indoor(self):
        fx = self.make_fixture()
        fx.mount_link(6)
        fx.put(0x16, 0)
        fx.put(HORSE_CARROTS, 3)

        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 1)
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x83)
        self.assertEqual(
            [fx.get16(HUD_CARROT_TOP + i * 2) for i in range(5)],
            [0x3D49, 0x3D49, 0x3D49, 0x3142, 0x3142],
        )
        self.assertEqual(
            [fx.get16(HUD_CARROT_BOT + i * 2) for i in range(5)],
            [0x294A, 0x294A, 0x294A, 0x3143, 0x3143],
        )
        self.assertEqual([fx.get16(0x7EC7C4 + i * 2) for i in range(5)], [0x0000] * 5,
                         "Legacy below-hearts $7EC7C4..$7EC7CC must stay untouched")

        # Steady state: zero $16 NMI queue
        fx.put(0x16, 0)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 0, "HUD steady state must not re-queue $16")

        # Indoor queues a one-shot clear (Horse_HudState = $01) and blanks buffers to $207F
        fx.put(0x1B, 1)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x01)
        self.assertEqual(fx.get(0x16), 1)
        self.assertEqual([fx.get16(HUD_CARROT_TOP + i * 2) for i in range(5)], [0x207F] * 5)
        self.assertEqual([fx.get16(HUD_CARROT_BOT + i * 2) for i in range(5)], [0x207F] * 5)
        fx.put(0x16, 0)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 0, "Pending blank must not re-queue $16 every frame")

        # Restores back on return outdoors
        fx.put(0x1B, 0)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 1)
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x83)
        self.assertEqual(
            [fx.get16(HUD_CARROT_BOT + i * 2) for i in range(5)],
            [0x294A, 0x294A, 0x294A, 0x3143, 0x3143],
        )

        # Menu / Dialogue ($10 == $0E) clears state cleanly WITHOUT queuing $16
        fx.put(0x16, 0)
        fx.put(0x10, 0x0E)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 0)
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x00)
        fx.put(0x10, 0x09)
        fx.run_jsl("Horse_SyncCarrotHud")
        self.assertEqual(fx.get(0x16), 1)
        self.assertEqual(fx.get(HORSE_HUD_STATE), 0x83)

    # === 5. DELIVERABLE 5: FACING PRESERVATION + LEFT H-FLIP + N/S 6-TILE + IN-PLACE GRAZE ===
    def test_facing_direction_preserved_across_dismount_and_remount(self):
        for direction in (0, 2, 4, 6):
            with self.subTest(dir=direction):
                fx = self.make_fixture()
                fx.mount_link(6)
                fx.put(0x002F, direction)
                fx.run_jsl("HorseForm_Dismount")
                self.assertEqual(fx.get(HORSE_ANCHOR_DIR), direction)
                self.assertEqual(fx.get(0x02B2), 0x00)

                # Scramble Link facing & grab lock before remounting; Mount clears lock & restores direction!
                fx.put(0x002F, (direction ^ 0x02) & 0x06)
                fx.put(0x0050, 0x01)
                fx.put(0x0376, 0x01)
                fx.run_jsl("HorseForm_Mount")
                self.assertEqual(fx.get(0x002F), direction)
                self.assertEqual(fx.get(0x0050) & 0x01, 0x00)
                self.assertEqual(fx.get(0x0376), 0x00)

    def test_npc_draw_renders_left_hflip_right_and_6tile_north_south(self):
        # Left ($04) uses H-flip props $67 and mirrored X offsets; Right ($06) uses $27
        fx_l = self.make_fixture()
        fx_l.put(HORSE_ANCHOR_DIR, 4)
        fx_l.put(0x0EC0, 0)
        fx_l.prep_x, fx_l.prep_y = 120, 120
        fx_l.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)
        oam_l = fx_l.read_oam_entries(8)
        self.assertTrue(all(e["props"] == 0x67 for e in oam_l))

        fx_r = self.make_fixture()
        fx_r.put(HORSE_ANCHOR_DIR, 6)
        fx_r.put(0x0EC0, 0)
        fx_r.prep_x, fx_r.prep_y = 120, 120
        fx_r.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)
        oam_r = fx_r.read_oam_entries(8)
        self.assertTrue(all(e["props"] == 0x27 for e in oam_r))
        # Left offsets mirror Right offsets around anchor x=120
        self.assertEqual([e["x"] - 120 for e in oam_l], [120 - e["x"] for e in oam_r])

        # North ($00) and South ($02) render 6 tiles (0..5 visible, 6..7 hidden $F0)
        for d in (0, 2):
            fx_ns = self.make_fixture()
            fx_ns.put(HORSE_ANCHOR_DIR, d)
            fx_ns.put(0x0EC0, 0)
            fx_ns.prep_x, fx_ns.prep_y = 120, 120
            fx_ns.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)
            oam_ns = fx_ns.read_oam_entries(8)
            visible = [e for e in oam_ns if e["y"] != 0xF0]
            hidden = [e for e in oam_ns if e["y"] == 0xF0]
            self.assertEqual(len(visible), 6)
            self.assertEqual(len(hidden), 2)

    def test_npc_graze_idle_192f_stays_in_place_without_drift(self):
        fx = self.make_fixture()
        fx.put(0x0DD0, 9)
        fx.put(0x0E20, 0x2D)
        fx.put(0x0D10, 0xC0); fx.put(0x0D30, 0x01)
        fx.put(0x0D00, 0x94); fx.put(0x0D20, 0x02)
        fx.put(HORSE_ANCHOR_DIR, 6)
        fx.prep_x, fx.prep_y = 120, 120

        # Neutral frame vs graze dip frame (SprMiscF=120): head tiles dip +3px in-place
        fx.put(0x0EC0, 0)
        fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)
        y_neutral = [e["y"] for e in fx.read_oam_entries(8)]

        fx.put(0x0EC0, 120)
        fx.run_jsr("Sprite_HorseNPC_Draw", x=0, db=0x30)
        y_graze = [e["y"] for e in fx.read_oam_entries(8)]
        self.assertGreater(y_graze[7], y_neutral[7])  # head dip +3px (tile index reversed 7..0 -> OAM 0..7)

        # Stepping Sprite_HorseNPC_Main 192 frames keeps NPC world X/Y invariant
        fx.put16(0x0022, 0x0100)  # far enough so Link doesn't bump/mount
        fx.put16(0x0020, 0x0294)
        for _ in range(192):
            fx.run_jsr("Sprite_HorseNPC_Main", x=0, db=0x30)
        nx = fx.get(0x0D10) | (fx.get(0x0D30) << 8)
        ny = fx.get(0x0D00) | (fx.get(0x0D20) << 8)
        self.assertEqual((nx, ny), (0x01C0, 0x0294))

    def test_up_down_stride_cadence_and_tall_grass_water_foot_oam(self):
        # 1. Up ($2F=0 -> [4,3,5,3]) & Down ($2F=2 -> [1,0,2,0]) 4-beat gallop synced to 24 ticks
        fx = self.make_fixture()
        fx.mount_link(0)
        fx.put(0x2F, 0)  # North
        fx.put(0xF0, 0x08)  # North
        up_frames = []
        for _ in range(26):
            fx.run_jsr("HorseForm_UpdateAnimFrame")
            up_frames.append(fx.get(0x7E1EE6))
            self.assertLess(fx.get(0x7E1EE5), 24, "N/S AnimTimer must wrap at 24")
        # Ticks 1..23, 0, 1, 2
        self.assertEqual(up_frames[:24], [4]*5 + [3]*6 + [5]*6 + [3]*6 + [4])

        fx.put(0x2F, 2)
        fx.put(0x7E1EE5, 0)
        fx.put(0xF0, 0x04)  # South
        dn_frames = []
        for _ in range(25):
            fx.run_jsr("HorseForm_UpdateAnimFrame")
            dn_frames.append(fx.get(0x7E1EE6))
            self.assertLess(fx.get(0x7E1EE5), 24, "N/S AnimTimer must wrap at 24")
        self.assertEqual(dn_frames[:24], [1]*5 + [0]*6 + [2]*6 + [0]*6 + [1])

        # Symmetric -2px vertical suspension bob on N/S walk frames (1&2 vs 0, 4&5 vs 3)
        head_y = {}
        for facing, fids in [(2, (0, 1, 2)), (0, (3, 4, 5))]:
            for fid in fids:
                fx.put(0x2F, facing)
                fx.put(0x7E1EE0, 0)
                fx.put(0x7E1EE6, fid)
                fx.put(0x7E1EE7, 0xFF)
                fx.put(0x0351, 0)
                fx.put16(0x22, 0x0140); fx.put16(0x20, 0x0140)
                fx.put16(0xE2, 0x0100); fx.put16(0xE8, 0x0100)
                fx.run_jsl("Horse_DrawPlayerOam_Long")
                head_y[fid] = fx.read_oam_entries(1)[0]["y"]
        self.assertEqual(head_y[1], head_y[0] - 2)
        self.assertEqual(head_y[2], head_y[0] - 2)
        self.assertEqual(head_y[4], head_y[3] - 2)
        self.assertEqual(head_y[5], head_y[3] - 2)

        # N/S tall grass never overflows $C8..$CA for ANY AnimTimer 0..255
        for sample_timer in (0, 4, 24, 63, 128, 255):
            fx.put(0x2F, 2)
            fx.put(0x7E1EE6, 1)
            fx.put(0x7E1EE7, 0xFF)
            fx.put(0x0351, 2)
            fx.put(0x7E1EE5, sample_timer)
            fx.run_jsl("Horse_DrawPlayerOam_Long")
            oam_ns = fx.read_oam_entries(12)
            g = [e for e in oam_ns if 0xC8 <= e["chr"] <= 0xCA]
            self.assertEqual(len(g), 2, f"Grass glitch for AnimTimer={sample_timer}: {oam_ns}")

        # 2. East/West 6/7-part tall grass ($0351=2) emits wide rear/front hoof spread ($C8..$CA Pal1)
        fx_g = self.make_fixture()
        fx_g.mount_link(6)
        fx_g.put16(0x22, 0x0140); fx_g.put16(0x20, 0x0140)
        fx_g.put16(0xE2, 0x0100); fx_g.put16(0xE8, 0x0100)
        fx_g.put(0x7E1EE6, 6)    # 7-part side idle frame
        fx_g.put(0x7E1EE7, 0xFF)
        fx_g.put(0x0351, 2)      # tall grass
        fx_g.put(0x7E1EE5, 4)    # AnimTimer=4 -> step 1 -> tile $C9
        fx_g.run_jsl("Horse_DrawPlayerOam_Long")
        oam_g = fx_g.read_oam_entries(12)
        grass_tiles = [e for e in oam_g if e["chr"] in (0xC8, 0xC9, 0xCA)]
        self.assertEqual(len(grass_tiles), 2)
        self.assertTrue(all(e["chr"] == 0xC9 for e in grass_tiles))
        self.assertEqual([e["props"] for e in grass_tiles], [0x22, 0x62])
        self.assertEqual([e["x"] for e in grass_tiles], [0x3C, 0x4C])  # SX16-4 ($40-4), SX16+12 ($40+12)
        self.assertEqual(sum(1 for e in oam_g if e["y"] != 0xF0), 11)  # 1+2+7+1=11 <= 12

        # 3. 8-part gallop frame (frame 8) emits 1 shallow water splash ($D8..$DA Pal2) driven continuously by $1A
        fx_w = self.make_fixture()
        fx_w.mount_link(6)
        fx_w.put16(0x22, 0x0140); fx_w.put16(0x20, 0x0140)
        fx_w.put16(0xE2, 0x0100); fx_w.put16(0xE8, 0x0100)
        fx_w.put(0x7E1EE6, 8)    # 8-part gallop frame (uses 11 slots for rider+Epona)
        fx_w.put(0x7E1EE7, 0xFF)
        fx_w.put(0x0351, 1)      # shallow water
        fx_w.put(0xF0, 0x01)     # moving -> $1A >> 2 = 2 -> tile $DA
        fx_w.put(0x1A, 8)
        fx_w.run_jsl("Horse_DrawPlayerOam_Long")
        oam_w = fx_w.read_oam_entries(12)
        water_tiles = [e for e in oam_w if e["chr"] in (0xD8, 0xD9, 0xDA)]
        self.assertEqual(len(water_tiles), 1)
        self.assertEqual(water_tiles[0]["chr"], 0xDA)
        self.assertEqual(water_tiles[0]["props"], 0x24)
        self.assertEqual(sum(1 for e in oam_w if e["y"] != 0xF0), 12)  # exact 12-slot cap

        # Standing still in shallow water still animates continuously via $1A >> 3 (1 -> $D9)
        fx_w.put(0xF0, 0x00)
        fx_w.put(0x1A, 8)
        fx_w.run_jsl("Horse_DrawPlayerOam_Long")
        water_idle = [e for e in fx_w.read_oam_entries(12) if e["chr"] in (0xD8, 0xD9, 0xDA)]
        self.assertEqual(water_idle[0]["chr"], 0xD9)

        # Dual-beat hoof SFX by terrain ($0351=1 -> $1C water, 2 -> $1A grass, 0 -> $23 dry)
        for terrain, want_sfx in [(0, 0x23), (1, 0x1C), (2, 0x1A)]:
            for tick in (4, 16):
                fx_s = self.make_fixture()
                fx_s.put(0xF0, 0x01)
                fx_s.put(0x0351, terrain)
                fx_s.put(0x7E1EE5, tick)
                fx_s.put(0x012E, 0x00)
                fx_s.run_jsl("HorseForm_PlayHoofBeat")
                self.assertEqual(fx_s.get(0x012E), want_sfx)

        # 4. Airborne (Horse_State != 0) suppresses $0351 grass/water and draws hoof shadow $6C
        fx_w.put(0x7E1EE0, 1)
        fx_w.put(0x7E1EE4, 8)
        fx_w.put(0x7E1EE6, 10)   # 7-part jump frame
        fx_w.run_jsl("Horse_DrawPlayerOam_Long")
        oam_air = fx_w.read_oam_entries(12)
        self.assertFalse(any(e["chr"] in (0xC8, 0xC9, 0xCA, 0xD8, 0xD9, 0xDA) for e in oam_air))
        self.assertEqual(sum(1 for e in oam_air if e["chr"] == 0x6C), 2)

    def test_parked_npc_nmi_uploads_north_south_and_side_vram_exact(self):
        gfx = (ROOT / "Masks/gfx/horse_sparse.4bpp").read_bytes()
        npc_tail = (ROOT / "Masks/gfx/horse_npc_rows.4bpp").read_bytes()
        north_tail = gfx[0x0D80:0x0DC0] + gfx[0x0E00:0x0E40] + bytes(128) + gfx[0x0DC0:0x0E00] + gfx[0x0E40:0x0E80] + bytes(128)
        south_tail = gfx[0x0300:0x0340] + gfx[0x0380:0x03C0] + bytes(128) + gfx[0x0340:0x0380] + gfx[0x03C0:0x0400] + bytes(128)

        cases = [
            (12, gfx[0x0A80:0x0C80], north_tail),   # North parked
            (13, gfx[0x0000:0x0200], south_tail),   # South parked
            (14, gfx[0x1480:0x1680], npc_tail),     # East/West parked
        ]
        for frame_id, ch0, ch1 in cases:
            with self.subTest(npc_frame=frame_id):
                fx = self.make_fixture()
                fx.put16(0x7E1EDE, 0x4852)  # Horse_Marker = !Horse_MagicMarker
                fx.put(0x7E0AA3, 6)         # Ranch sprite group 06
                fx.put(0x7EC2FC, 0x4F); fx.put(0x7EC2FD, 0x49)
                fx.put(0x7EC2FE, 0x4A); fx.put(0x7EC2FF, 0x50)  # RanchProfileReady = true
                fx.put(0x10, 0x09)
                fx.put(0x7E1EE8, 1)         # Horse_NpcActive = 1
                fx.put(0x7E1EE9, frame_id)  # Horse_NpcFrame
                fx.put(0x7E1EE7, 0xFF)      # Horse_UploadedFrame = none
                fx.put(0x7E1EEA, 0xFF)      # Horse_NpcUploadedFrame = none
                fx.put(0x7E1EED, 1)         # skip unrelated trailing BG replay
                fx.run_jsl("Horse_NmiUpload", mf=True, xf=False, db=0x00)
                expected_vram = ch0[:256] + ch1[:256] + ch0[256:512] + ch1[256:512]
                actual_vram = bytes(fx.vram[0xA000:0xA400])
                self.assertEqual(actual_vram, expected_vram, f"VRAM $5000 mismatch for NpcFrame={frame_id}")
                self.assertEqual(fx.get(0x7E1EEA), frame_id)

    def test_ranch_npc_ignores_sword_beam_and_page0_drops_and_dismount_clears_locks(self):
        # 1. Ranch NPC NMI & Sprite_HorseNPC_Long must NOT blink out or restore VRAM
        #    when Master Sword Beam ($0C), BeamHit ($04), bush debris ($EC), or Page 0
        #    drops ($D8-$E2) are active; Page 1 fairy ($E3) must still safely fail.
        fx = self.make_fixture()
        fx.put16(0x7E1EDE, 0x4852)
        fx.put(0x7E0AA3, 6)
        fx.put(0x7EC2FC, 0x4F); fx.put(0x7EC2FD, 0x49)
        fx.put(0x7EC2FE, 0x4A); fx.put(0x7EC2FF, 0x50)
        fx.put(0x10, 0x09)
        fx.put(0x7E1EE8, 1)    # Horse_NpcActive = 1
        fx.put(0x7E1EE9, 14)   # Horse_NpcFrame = 14
        fx.put(0x7E1EE7, 0xFF)
        fx.put(0x7E1EEA, 14)   # already uploaded
        fx.put(0x7E1EED, 1)
        # Active Master Sword beam ($0C) + beam hit ($04) + bush debris ($EC) + Rupee ($D9)
        fx.put(0x0C4A, 0x0C)
        fx.put(0x0C4B, 0x04)
        fx.put(0x0DD1, 0x09); fx.put(0x0E21, 0xEC)
        fx.put(0x0DD2, 0x09); fx.put(0x0E22, 0xD9)

        # Horse_SlotsBusy must exempt $0C and $04 (C=0)
        fx.run_jsl("Horse_SlotsBusy", mf=True, xf=True, db=0x00)
        self.assertFalse(bool(fx.cpu.c), "Master Sword Beam ($0C) and BeamHit ($04) must not trip Horse_SlotsBusy")

        # Horse_RanchActorsSafe must accept $EC bush debris and $D8-$E2 drops (C=1)
        fx.run_jsl("Horse_RanchActorsSafe", mf=True, xf=True, db=0x00)
        self.assertTrue(bool(fx.cpu.c), "Page 0 bush debris ($EC) and drops ($D8-$E2) must be Ranch-safe")

        # Horse_NmiUpload must keep Horse_NpcUploadedFrame == 14 (0 restore DMA)
        fx.run_jsl("Horse_NmiUpload", mf=True, xf=False, db=0x00)
        self.assertEqual(fx.get(0x7E1EEA), 14, "Ranch Epona must stay uploaded during Master Sword beam")

        # Page 1 fairy ($E3) must still fail Horse_RanchActorsSafe (C=0)
        fx.put(0x0DD3, 0x09); fx.put(0x0E23, 0xE3)
        fx.run_jsl("Horse_RanchActorsSafe", mf=True, xf=True, db=0x00)
        self.assertFalse(bool(fx.cpu.c), "Page 1 fairy ($E3) must remain excluded from RanchActorsSafe")

        # 2. HorseForm_ClearLinkLocks clears all residual sword/action locks on dismount
        fx2 = self.make_fixture()
        for addr in (0x3A, 0x3B, 0x3C, 0x0301, 0x037A, 0x0372, 0x0308, 0x0376, 0x0377, 0x02E3):
            fx2.put(addr, 0x10)
        fx2.put(0x50, 0x03)
        fx2.put(0x5D, 0x11)
        fx2.run_jsl("HorseForm_ClearLinkLocks", mf=True, xf=True, db=0x00)
        for addr in (0x3A, 0x3B, 0x3C, 0x0301, 0x037A, 0x0372, 0x0308, 0x0376, 0x0377, 0x02E3):
            self.assertEqual(fx2.get(addr), 0x00, f"Lock byte {addr:#x} not cleared by HorseForm_ClearLinkLocks")
        self.assertEqual(fx2.get(0x50), 0x02, "Only bit 0 of $50 should be cleared")
        self.assertEqual(fx2.get(0x5D), 0x00, "Stale grab state $5D=$11 must clear to $00")


if __name__ == "__main__":
    unittest.main(verbosity=2)
