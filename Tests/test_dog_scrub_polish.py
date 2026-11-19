#!/usr/bin/env python3
"""Compiled 65816 unit tests (Lakesnes) for Village Dog & Business/Eon Scrub polish.

Assembles the real worktree source files:
  - Sprites/NPCs/village_dog.asm
  - Sprites/Enemies/business_scrub.asm
  - Sprites/Enemies/business_scrub_shield.asm
  - Sprites/Enemies/eon_scrub.asm

Executes real 65816 routines on Lakesnes' CPU core with explicit vanilla engine
ABI stubs (including authentic Sprite_CheckIfLifted $0E90 clear and ThrownSprite
Z-gravity/bounce physics). No emulator process, socket, or shared ROM write is used.
"""
from __future__ import annotations

import argparse
import ctypes as C
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile

TESTS_DIR = Path(__file__).resolve().parent
ROOT = TESTS_DIR.parent
if str(TESTS_DIR) not in sys.path:
    sys.path.insert(0, str(TESTS_DIR))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402


# Stub addresses in unused vanilla ROM regions (never collide with banks $30/$31)
STUB_PREP_OAM        = 0x06E416
STUB_OAM_DEFER       = 0x06F864
STUB_OAM_REGION_C    = 0x0DBA88
STUB_DRAW_SHADOW     = 0x06DC54
STUB_CHECK_LIFTED    = 0x06AA0C
STUB_THROWN_INTERACT = 0x06DFF2
STUB_CANT_PASS       = 0x1EF4F3
STUB_IS_BELOW        = 0x06EAE4
STUB_IS_RIGHT        = 0x068860
STUB_CHECK_TILE      = 0x068890
STUB_BOUNCE_TILE     = 0x0688A0
STUB_APPLY_SPEED     = 0x0688B0
STUB_GET_RANDOM      = 0x0DBA71
STUB_RECEIVE_ITEM    = 0x0791B3
STUB_SHOW_SOLICITED  = 0x05E1A7
STUB_SPAWN_DYN       = 0x1DF65D
STUB_SETUP_HITBOX    = 0x0683EA
STUB_OVERLAP_HITBOX  = 0x0683E6
STUB_DMG_FROM_PLAYER = 0x068820
STUB_DMG_TO_SAME     = 0x06F129
STUB_SFX2_PAN        = 0x0DBB7C
STUB_RICHARD_MAIN    = 0x348100
STUB_RICHARD_PAL     = 0x348110
STUB_DOG_FORM_INT    = 0x2B8100


FIXTURE_ASM = """lorom

; ---- Shared symbol definitions matching Core/symbols.asm & sprite_registry_ids.asm ----
Sprite_BusinessScrub = $14
Sprite_VillageDog    = $25

WORLDFLAG     = $7E0FFF
Offspring1_Id = $7E1E84

struct TimeState $7EE000
  .Hours: skip 1
endstruct

POSY          = $20
POSX          = $22
SprCachedY    = $0FD8
SprCachedX    = $0FDA

pos1_x_low    = $00
pos1_y_low    = $01
pos1_size     = $02
pos1_height   = $03
pos2_x_low    = $04
pos2_y_low    = $05
pos2_size     = $06
pos2_height   = $07
pos1_x_high   = $08
pos1_y_high   = $09
pos2_x_high   = $0A
pos2_y_high   = $0B

SprY          = $0D00
SprX          = $0D10
SprYH         = $0D20
SprXH         = $0D30
SprYSpeed     = $0D40
SprXSpeed     = $0D50
SprYRound     = $0D60
SprXRound     = $0D70
SprAction     = $0D80
SprFrame      = $0D90
SprMiscA      = $0DA0
SprMiscB      = $0DB0
SprGfx        = $0DC0
SprState      = $0DD0
SprMiscC      = $0DE0
SprTimerA     = $0DF0
SprTimerB     = $0E00
SprTimerC     = $0E10
SprType       = $0E20
SprSubtype    = $0E30
SprNbrOAM     = $0E40
SprHealth     = $0E50
SprGfxProps   = $0E60
SprCollision  = $0E70
SprDelay      = $0E80
SprMiscD      = $0E90
SprMiscE      = $0EB0
SprMiscF      = $0EC0
SprMiscG      = $0ED0
SprTimerD     = $0EE0
SprPause      = $0F00
SprFloor      = $0F20
SprHitbox     = $0F60
SprHeight     = $0F70
SprTimerF     = $0F80
SprHeightS    = $0F90
SprFreeze     = $0FC1
SprBump       = $0CD2
SprPrize      = $0BE0
SprDefl       = $0CAA

Sprite_PrepOamCoord                       = $06E416
Sprite_OAM_AllocateDeferToPlayer          = $06F864
OAM_AllocateFromRegionC                   = $0DBA88
Sprite_DrawShadow                         = $06DC54
Sprite_CheckIfLifted                      = $06AA0C
ThrownSprite_TileAndSpriteInteraction_long = $06DFF2
Sprite_PlayerCantPassThrough              = $1EF4F3
Sprite_IsBelowPlayer                      = $06EAE4
Sprite_IsToRightOfPlayer                  = $068860
Sprite_CheckTileCollision                 = $068890
Sprite_BounceFromTileCollision            = $0688A0
Sprite_ApplySpeedTowardsPlayer            = $0688B0
GetRandomInt                              = $0DBA71
Link_ReceiveItem                          = $0791B3
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7
Sprite_SpawnDynamically                   = $1DF65D
Sprite_SetupHitBox                        = $0683EA
CheckIfHitBoxesOverlap                    = $0683E6
Sprite_CheckDamageFromPlayer              = $068820
Sprite_CheckDamageToPlayerSameLayer       = $06F129
SpriteSFX_QueueSFX2WithPan                = $0DBB7C
RichardDog_Main                           = $348100
RichardDog_PaletteMask                    = $348110
VillageDog_FormInteractLong               = $2B8100

; ---- Minimal macros matching Core/sprite_macros.asm ----
macro Set_Sprite_Properties(SprPrep, SprMain)
endmacro

macro GotoAction(action)
  LDA.b #<action> : STA.w SprAction, X
endmacro

macro SetFrame(frame)
  LDA.b #<frame> : STA.w SprFrame, X
endmacro

macro StartOnFrame(frame)
  LDA.w SprFrame, X : CMP.b #<frame> : BCS +
    LDA.b #<frame> : STA.w SprFrame, X
  +
endmacro

macro PlayAnimation(frame_start, frame_end, frame_wait)
  LDA.w SprTimerB, X : BNE +
    LDA.w SprFrame, X : INC : STA.w SprFrame, X
                        CMP.b #<frame_end>+1 : BCC ++
      LDA.b #<frame_start> : STA.w SprFrame, X
    ++
    LDA.b #<frame_wait> : STA.w SprTimerB, X
  +
endmacro

macro ShowSolicitedMessage(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL Sprite_ShowSolicitedMessageIfPlayerFacing
endmacro

macro SetHarmless(value)
  LDA.w SprNbrOAM, X
  AND #$7F
  if <value> != 0
    ORA.b #(<value>)<<7
  endif
  STA.w SprNbrOAM, X
endmacro

; ---- Exact vanilla JumpTableLocal ($00:8781) ----
org $008781
JumpTableLocal:
{
  STY.b $03
  PLY
  STY.b $00
  REP #$30
  AND.w #$00FF
  ASL A
  TAY
  PLA
  STA.b $01
  INY
  LDA [$00], Y
  STA.b $00
  SEP #$30
  LDY.b $03
  JML [$0000]
}

; ---- Real engine routines from Core/sprite_functions.asm ----
org $318000
Sprite_CheckActive:
{
  LDA.w SprState, X : CMP.b #$09 : BNE .inactive
    LDA.w SprFreeze : BNE .inactive
      LDA.b $11 : BNE .inactive
        LDA.w SprDefl, X : BMI .active
          LDA.w SprPause, X : BEQ .active
  .inactive
  CLC
  RTL
  .active
  SEC
  RTL
}

Sprite_MoveHoriz:
{
  LDA.w SprXSpeed, X : BEQ .no_velocity
    ASL #4 : CLC : ADC.w SprXRound, X : STA.w SprXRound, X
    LDY.b #$00
    LDA.w SprXSpeed, X
    PHP : LSR #4 : PLP : BPL ++
      ORA.b #$F0
      DEY
    ++
    ADC.w SprX, X : STA.w SprX, X
    TYA : ADC.w SprXH, X : STA.w SprXH, X
  .no_velocity
  RTL
}

Sprite_MoveLong:
Sprite_Move:
  JSL Sprite_MoveHoriz
Sprite_MoveVert:
{
  LDA.w SprYSpeed, X : BEQ .no_velocity
    ASL #4 : CLC : ADC.w SprYRound, X : STA.w SprYRound, X
    LDY.b #$00
    LDA.w SprYSpeed, X
    PHP : LSR #4 : PLP : BPL ++
      ORA.b #$F0
      DEY
    ++
    ADC.w SprY, X : STA.w SprY, X
    TYA : ADC.w SprYH, X : STA.w SprYH, X
  .no_velocity
  RTL
}

GetDistance8bit_Long:
{
  LDA.b POSX : STA.b $02
  LDA.b POSY : STA.b $03
  LDA.w SprX, X : STA.b $04
  LDA.w SprY, X : STA.b $05
  LDA.b $04 : SEC : SBC.b $02 : BPL +
    EOR.b #$FF : INC A
  +
  STA.b $00
  LDA.b $05 : SEC : SBC.b $03 : BPL +
    EOR.b #$FF : INC A
  +
  CLC : ADC.b $00 : STA.b $00
  RTL
}

; ---- Assemble real Bank $31 owned modules ----
incsrc "village_dog.asm"
incsrc "business_scrub_shield.asm"

VillageDog_MainWrap:
  PHB : PHK : PLB
  JSR Sprite_VillageDog_Main
  PLB
  RTL

; ---- Assemble real Bank $30 owned modules ----
org $308000
incsrc "business_scrub.asm"
incsrc "eon_scrub.asm"

BusinessScrub_MainWrap:
  PHB : PHK : PLB
  JSR Sprite_BusinessScrub_Main
  PLB
  RTL

EonScrub_MainWrap:
  PHB : PHK : PLB
  JSR Sprite_EonScrub_Main
  PLB
  RTL

CheckForPeaShotRedirect_Wrap:
  PHB : PHK : PLB
  JSR CheckForPeaShotRedirect
  PLB
  RTL
"""


def find_lakesnes(explicit: Path | None = None) -> Path:
    if explicit is not None:
        return explicit
    env = os.environ.get("LAKESNES_DIR", "").strip()
    if env:
        return Path(env)
    for cand in (
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ):
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    raise FileNotFoundError("Could not locate lakesnes checkout; pass --lakesnes or set LAKESNES_DIR")


def build_cpu_lib(lakesnes: Path, build_dir: Path):
    library = build_dir / "cpu.dylib"
    subprocess.run(
        [
            "cc", "-shared", "-fPIC", "-O2",
            str(lakesnes / "snes" / "cpu.c"),
            str(lakesnes / "snes" / "statehandler.c"),
            "-o", str(library),
        ],
        check=True,
    )
    lib = C.CDLL(str(library))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def assemble_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    for rel in (
        "Sprites/NPCs/village_dog.asm",
        "Sprites/Enemies/business_scrub.asm",
        "Sprites/Enemies/business_scrub_shield.asm",
        "Sprites/Enemies/eon_scrub.asm",
    ):
        (folder / Path(rel).name).write_bytes((ROOT / rel).read_bytes())
    asm = folder / "fixture.asm"
    asm.write_text(FIXTURE_ASM, encoding="utf-8")
    image = folder / "fixture.sfc"
    image.write_bytes(b"\xFF" * 0x200000)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(image)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"Asar failed:\n{res.stdout}\n{res.stderr}"
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            image.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return image.read_bytes(), labels


def s8(v: int) -> int:
    v &= 0xFF
    return v - 256 if v >= 128 else v


class DogScrubFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.stubs = {
            STUB_PREP_OAM:        "prep_oam",
            STUB_OAM_DEFER:       "oam_defer",
            STUB_OAM_REGION_C:    "oam_region_c",
            STUB_DRAW_SHADOW:     "draw_shadow",
            STUB_CHECK_LIFTED:    "check_lifted",
            STUB_THROWN_INTERACT: "thrown_interact",
            STUB_CANT_PASS:       "cant_pass",
            STUB_IS_BELOW:        "is_below",
            STUB_IS_RIGHT:        "is_right",
            STUB_CHECK_TILE:      "check_tile",
            STUB_BOUNCE_TILE:     "bounce_tile",
            STUB_APPLY_SPEED:     "apply_speed",
            STUB_GET_RANDOM:      "get_random",
            STUB_RECEIVE_ITEM:    "receive_item",
            STUB_SHOW_SOLICITED:  "show_solicited",
            STUB_SPAWN_DYN:       "spawn_dyn",
            STUB_SETUP_HITBOX:    "setup_hitbox",
            STUB_OVERLAP_HITBOX:  "overlap_hitbox",
            STUB_DMG_FROM_PLAYER: "dmg_from_player",
            STUB_DMG_TO_SAME:     "dmg_to_same",
            STUB_SFX2_PAN:        "sfx2_pan",
            STUB_RICHARD_MAIN:    "richard_main",
            STUB_RICHARD_PAL:     "richard_pal",
            STUB_DOG_FORM_INT:    "dog_form_int",
        }
        self.screen = (120, 100)
        self.offscreen = False
        self.region_c_allocs: list[int] = []
        self.defer_allocs: int = 0
        self.shadow_calls: int = 0
        self.lift_trigger = False
        self.thrown_hazard_state: int | None = None
        self.is_below_override: int | None = None
        self.to_right = 0
        self.talk_accept = True
        self.messages: list[int] = []
        self.items_received: list[int] = []
        self.sfx2: list[int] = []
        self.dmg_to_player_calls: int = 0
        self.dmg_from_player = False
        self.next_spawn_slot = 4
        self.spawned: list[tuple[int, int]] = []
        self.oam_base = 0x0800
        self.oam_hi_base = 0x0A00

    def oam_tiles(self, count: int) -> list[tuple[int, int, int, int, int]]:
        """Read (x, y, chr, prop, size) tuples written to the allocated OAM buffer."""
        out = []
        for i in range(count):
            base = self.oam_base + i * 4
            x = self.get(base + 0)
            y = self.get(base + 1)
            ch = self.get(base + 2)
            prop = self.get(base + 3)
            sz = self.get(self.oam_hi_base + i)
            out.append((x, y, ch, prop, sz))
        return out

    def clear_oam(self):
        for i in range(0x40):
            self.put(self.oam_base + i, 0xF0 if (i % 4 == 1) else 0x00)
        for i in range(0x10):
            self.put(self.oam_hi_base + i, 0x00)

    def _spr_xy(self, slot: int) -> tuple[int, int]:
        x = self.get(0x0D10 + slot) | (self.get(0x0D30 + slot) << 8)
        y = self.get(0x0D00 + slot) | (self.get(0x0D20 + slot) << 8)
        return x, y

    def _set_spr_xy(self, slot: int, x: int, y: int):
        self.put(0x0D10 + slot, x & 0xFF)
        self.put(0x0D30 + slot, (x >> 8) & 0xFF)
        self.put(0x0D00 + slot, y & 0xFF)
        self.put(0x0D20 + slot, (y >> 8) & 0xFF)
        self.word(0x0FDA, x & 0xFFFF)
        self.word(0x0FD8, y & 0xFFFF)

    def stub(self, name: str):
        c = self.cpu
        slot = c.x & 0xFF
        self.calls.append(name)

        if name == "prep_oam":
            self.word(0x00, self.screen[0] & 0xFFFF)
            self.word(0x02, self.screen[1] & 0xFFFF)
            c.c = self.offscreen
        elif name == "oam_defer":
            self.defer_allocs += 1
            self.oam_base = 0x09D0  # Region B mock address
            self.oam_hi_base = 0x0A74
            self.word(0x90, self.oam_base)
            self.word(0x92, self.oam_hi_base)
        elif name == "oam_region_c":
            self.region_c_allocs.append(c.a & 0xFF)
            self.oam_base = 0x0800  # Region C mock address (OAM 0..11)
            self.oam_hi_base = 0x0A00
            self.word(0x90, self.oam_base)
            self.word(0x92, self.oam_hi_base)
        elif name == "draw_shadow":
            self.shadow_calls += 1
        elif name == "check_lifted":
            # Authentic vanilla Sprite_CheckIfLifted ($06F27C): zeroes SprMiscD ($0E90,X)!
            if self.lift_trigger:
                vx = self.get(0x0D50 + slot)
                vy = self.get(0x0D40 + slot)
                if (vx | vy) == 0:
                    self.put(0x0E90 + slot, 0x00)  # Vanilla STZ $0E90, X!
                    self.put(0x7FFA2C + slot, self.get(0x0DD0 + slot))
                    self.put(0x0DD0 + slot, 0x0A)
                    self.put(0x0DF0 + slot, 0x10)
                    self.put(0x7FFA1C + slot, 0x00)
                    self.lift_trigger = False
        elif name == "thrown_interact":
            # Authentic vanilla ThrownSprite_TileAndSpriteInteraction ($06E066..$06E140)
            vz = s8(self.get(0x0F80 + slot))
            z_sub = self.get(0x0F90 + slot) + ((vz & 0x0F) << 4)
            carry = 1 if z_sub >= 0x100 else 0
            self.put(0x0F90 + slot, z_sub & 0xFF)
            dz = (vz >> 4) + carry
            h = (self.get(0x0F70 + slot) + dz) & 0xFF
            vz_next = (vz - 2) & 0xFF
            self.put(0x0F80 + slot, vz_next)
            if h == 0 or h >= 0xF1:
                self.put(0x0F70 + slot, 0)
                if self.thrown_hazard_state is not None:
                    self.put(0x0DD0 + slot, self.thrown_hazard_state)
                    self.put(0x0F80 + slot, 0)
                    return
                svz = s8(vz_next)
                if svz < 0:
                    bounce = (-svz) >> 1
                    self.put(0x0F80 + slot, bounce if bounce >= 9 else 0)
                else:
                    self.put(0x0F80 + slot, 0)
                # Halve XY speeds on bounce (signed)
                for spd_base in (0x0D50, 0x0D40):
                    sv = s8(self.get(spd_base + slot))
                    nv = int(sv / 2)
                    self.put(spd_base + slot, nv & 0xFF)
            else:
                self.put(0x0F70 + slot, h)
        elif name == "is_below":
            if self.is_below_override is not None:
                c.y = self.is_below_override & 0xFF
            else:
                # Authentic vanilla Sprite_IsBelowPlayer ($06EAE8):
                # LinkY + 8 + SprHeight - SprY >= 0 -> Y=0 (Link south); < 0 -> Y=1 (Link north)
                link_y = self.get(0x20) | (self.get(0x21) << 8)
                spr_y = self.get(0x0D00 + slot) | (self.get(0x0D20 + slot) << 8)
                spr_h = self.get(0x0F70 + slot)
                diff = (link_y + 8 + spr_h - spr_y) & 0xFFFF
                c.y = 1 if (diff & 0x8000) else 0
        elif name == "is_right":
            c.y = self.to_right & 0xFF
        elif name == "check_tile":
            self.put(0x0E70 + slot, 0x00)
            self.acc(0x00)
        elif name == "get_random":
            self.acc(0x01)
        elif name == "receive_item":
            self.items_received.append(c.y & 0xFF)
        elif name == "show_solicited":
            mid = ((c.y & 0xFF) << 8) | (c.a & 0xFF)
            if self.talk_accept:
                self.messages.append(mid)
                c.c = True
            else:
                c.c = False
        elif name == "spawn_dyn":
            spr_id = c.a & 0xFF
            s = self.next_spawn_slot
            self.next_spawn_slot += 1
            if s < 16:
                self.put(0x0DD0 + s, 0x09)
                self.put(0x0E20 + s, spr_id)
                self.put(0x0E30 + s, 0x00)
                self.put(0x0D40 + s, 0x00)
                self.put(0x0D50 + s, 0x00)
                self.put(0x0F20 + s, 0x00)
                c.y = s
                c.n = False
                self.spawned.append((s, spr_id))
            else:
                c.y = 0xFF
                c.n = True
        elif name == "setup_hitbox":
            # Authentic pos2 ($04-$07, $0A-$0B) from slot X (16x16 box)
            sx, sy = self._spr_xy(slot)
            sh = self.get(0x0F70 + slot)
            sy_eff = (sy - sh) & 0xFFFF
            self.put(0x04, sx & 0xFF)
            self.put(0x0A, (sx >> 8) & 0xFF)
            self.put(0x05, sy_eff & 0xFF)
            self.put(0x0B, (sy_eff >> 8) & 0xFF)
            self.put(0x06, 0x10)
            self.put(0x07, 0x10)
        elif name == "overlap_hitbox":
            x1 = self.get(0x00) | (self.get(0x08) << 8)
            y1 = self.get(0x01) | (self.get(0x09) << 8)
            w1 = self.get(0x02)
            h1 = self.get(0x03)
            x2 = self.get(0x04) | (self.get(0x0A) << 8)
            y2 = self.get(0x05) | (self.get(0x0B) << 8)
            w2 = self.get(0x06)
            h2 = self.get(0x07)
            # Vanilla ALTTP CheckIfHitBoxesOverlap semantics (matches $0683E6)
            dx = (x1 - x2) & 0xFFFF
            dy = (y1 - y2) & 0xFFFF
            hit_x = (dx < w2) or (((x2 - x1) & 0xFFFF) < w1)
            hit_y = (dy < h2) or (((y2 - y1) & 0xFFFF) < h1)
            c.c = hit_x and hit_y
        elif name == "dmg_from_player":
            c.c = self.dmg_from_player
        elif name == "dmg_to_same":
            self.dmg_to_player_calls += 1
            c.c = True
        elif name == "sfx2_pan":
            self.sfx2.append(c.a & 0xFF)
        elif name == "richard_main":
            c.c = False
        elif name == "richard_pal":
            self.put(0x0C, 0x04 if self.get(0x0E30 + slot) else 0x00)

    def tick_timers(self, slot: int):
        """Mimic vanilla Sprite_TimersAndOAM timer decrements ($068420)."""
        for base in (0x0DF0, 0x0E00, 0x0E10, 0x0EE0):
            v = self.get(base + slot)
            if v > 0:
                self.put(base + slot, v - 1)

    def call_jsl(self, label: str, *, a: int = 0, x: int = 0, y: int = 0,
                 db: int = 0x06, max_ops: int = 30000):
        c = self.cpu
        c.mf = True
        c.xf = True
        c.a = a & 0xFF
        c.x = x & 0xFF
        c.y = y & 0xFF
        c.db = db
        c.c = c.z = c.n = c.v = False
        entry = self.addr(label)
        assert entry is not None, f"Missing label: {label}"
        c.k = entry >> 16
        c.pc = entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        sentinel = (c.k << 16) | 0x7000
        for count in range(max_ops):
            pc_addr = (c.k << 16) | c.pc
            if pc_addr == sentinel:
                assert c.sp == sp, f"{label}: stack imbalance {c.sp:#x} != {sp:#x}"
                assert not self.bad_writes, f"{label}: bad writes {self.bad_writes}"
                assert (c.x & 0xFF) == (x & 0xFF), f"{label}: X clobbered {c.x:#x} != {x:#x}"
                return count
            if pc_addr in self.stubs:
                self.stub(self.stubs[pc_addr])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{label}: exceeded {max_ops} ops at ${(c.k << 16) | c.pc:06X}")


# =====================================================================
# 1. Village Dog & Eon Dog Carried Priority / Shadow / Pose / Toss
# =====================================================================

def case_dog_carried_region_c_and_no_shadow(f: DogScrubFixture):
    slot = 2
    f.put(0x0FFF, 0x00)        # LW Village Dog
    f.put(0x0DD0 + slot, 0x0A)   # Carried
    f.put(0x7FFA1C + slot, 0x01) # Mid-lift frame (where vanilla DrawShadow STILL draws!)
    f.put(0x002F, 0x02)          # Link facing down
    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.region_c_allocs == [0x10], f"Expected Region C $10, got {f.region_c_allocs}"
    assert f.defer_allocs == 0
    assert f.shadow_calls == 0, "Carried Village Dog must skip Sprite_DrawShadow!"

    # Eon Dog (WORLDFLAG == 1) when carried: Region C $04, no shadow
    f.region_c_allocs.clear()
    f.defer_allocs = 0
    f.shadow_calls = 0
    f.put(0x0FFF, 0x40)
    f.put(0x0DD0 + slot, 0x0A)
    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.region_c_allocs == [0x04], f"Expected EonDog Region C $04, got {f.region_c_allocs}"
    assert f.defer_allocs == 0
    assert f.shadow_calls == 0


def case_dog_grounded_defer_to_player_and_shadow(f: DogScrubFixture):
    slot = 2
    f.put(0x0FFF, 0x00)
    f.put(0x0DD0 + slot, 0x09)   # Grounded active
    f.put(0x0D90 + slot, 8)
    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.defer_allocs == 1
    assert f.region_c_allocs == []
    assert f.shadow_calls == 1


def case_dog_carried_bg_priority_layer_and_palettes(f: DogScrubFixture):
    slot = 3
    f.put(0x0FFF, 0x00)
    f.put(0x002F, 0x02)  # Sitting frame 8 (1 tile)

    # Check all 3 coat variants (default SP3, stray SP6, Richard SP1) across:
    #   (SprState=$0A, SprFloor=0) -> pri 2 ($20)
    #   (SprState=$0A, SprFloor=1) -> pri 3 ($30)
    #   (SprState=$09, SprFloor=0) -> pri 3 ($30, grounded preserved!)
    variants = [
        ("default_SP3", 0, 0x00, 0x07),  # base $37 -> low nibble $7
        ("stray_SP6",   0, 0x0A, 0x0D),  # $37 ^ $0A = $3D -> low nibble $D
        ("richard_SP1", 1, 0x00, 0x03),  # $37 ^ $04 = $33 -> low nibble $3
    ]
    for name, subtype, misc_g, low_nib in variants:
        f.put(0x0E30 + slot, subtype)
        f.put(0x0ED0 + slot, misc_g)

        for state, floor, expected_pri in ((0x0A, 0, 0x20), (0x0A, 1, 0x30), (0x09, 0, 0x30)):
            f.clear_oam()
            f.put(0x0DD0 + slot, state)
            f.put(0x0F20 + slot, floor)
            f.put(0x0D90 + slot, 8)
            f.call_jsl("Sprite_VillageDog_Long", x=slot)
            _, _, _, prop, _ = f.oam_tiles(1)[0]
            assert (prop & 0x30) == expected_pri, (name, state, floor, hex(prop))
            assert (prop & 0x0F) == low_nib, (name, state, floor, hex(prop))
            assert ((prop >> 1) & 0x07) != 7, f"Forbidden SP7 emitted: {prop:#04x}"

    # Eon Dog carried layer 0 -> pri 2 ($2B/$6B), layer 1 -> pri 3 ($3B/$7B)
    f.put(0x0FFF, 0x40)
    for floor, expected_pri in ((0, 0x20), (1, 0x30)):
        f.clear_oam()
        f.put(0x0DD0 + slot, 0x0A)
        f.put(0x0F20 + slot, floor)
        f.put(0x002F, 0x04)
        f.call_jsl("Sprite_VillageDog_Long", x=slot)
        _, _, _, prop, _ = f.oam_tiles(1)[0]
        assert (prop & 0x30) == expected_pri, (floor, hex(prop))


def case_dog_carried_compact_pose_and_freeze(f: DogScrubFixture):
    slot = 1
    f.put(0x0FFF, 0x00)
    f.screen = (120, 100)

    # Pre-seed stale wag pose (Frame 0 has y_offset=+12!) + speed + nonzero SprGfx!
    cases = [
        (0x00, 0x00, 8, 1),   # Up -> sitting puppy 8
        (0x02, 0x08, 8, 1),   # Down -> sitting puppy 8
        (0x04, 0x00, 2, 4),   # Left ($1A&$08==0) -> frame 2
        (0x04, 0x08, 3, 4),   # Left ($1A&$08!=0) -> frame 3
        (0x06, 0x00, 5, 4),   # Right ($1A&$08==0) -> frame 5
        (0x06, 0x08, 10, 1),  # Right ($1A&$08!=0) -> frame 10
    ]
    for facing, frame_ctr, expected_frame, tile_count in cases:
        f.clear_oam()
        f.put(0x0DD0 + slot, 0x0A)
        f.put(0x0D50 + slot, 0x18)  # stale XSpeed
        f.put(0x0D40 + slot, 0xEC)  # stale YSpeed
        f.put(0x0E90 + slot, 0x03)  # stale SprMiscD
        f.put(0x0DC0 + slot, 0x05)  # stale SprGfx!
        f.put(0x0D90 + slot, 0x00)  # stale wag Frame 0 (y_offset +12!)
        f.put(0x002F, facing)
        f.put(0x001A, frame_ctr)
        f.call_jsl("Sprite_VillageDog_Long", x=slot)
        assert f.get(0x0D50 + slot) == 0
        assert f.get(0x0D40 + slot) == 0
        assert f.get(0x0E90 + slot) == 0
        assert f.get(0x0DC0 + slot) == 0
        assert f.get(0x0D90 + slot) == expected_frame, (facing, frame_ctr, f.get(0x0D90 + slot))
        for tx, ty, ch, prop, sz in f.oam_tiles(tile_count):
            assert ty <= f.screen[1], f"Carried dog tile overhangs below base Y: {ty} > {f.screen[1]} (frame {expected_frame})"

    # Direct Sprite_VillageDog_Main call while carried must NOT trigger Ocarina dance or AI
    f.put(0x0DD0 + slot, 0x0A)
    f.put(0x0D80 + slot, 0x00)
    f.put(0x0010, 0x09)
    f.put(0x003A, 0x40)
    f.put(0x03F0, 0x80)  # Fresh Ocarina cast!
    f.put(0x0F80 + slot, 0x04)  # Even stray SprTimerF must be ignored while SprState==$0A
    f.call_jsl("VillageDog_MainWrap", x=slot, db=0x31)
    assert f.get(0x0D80 + slot) == 0x00, "Carried dog must not enter Ocarina dance or Dog_Tossed!"

    # Eon Dog carried frame stays strictly in 0..3 (never OOB!)
    f.put(0x0FFF, 0x40)
    for facing, ctr, exp in ((0x04, 0, 0), (0x04, 8, 1), (0x06, 0, 2), (0x06, 8, 3), (0x02, 0, 0)):
        f.put(0x0DD0 + slot, 0x0A)
        f.put(0x002F, facing)
        f.put(0x001A, ctr)
        f.call_jsl("Sprite_VillageDog_Long", x=slot)
        assert f.get(0x0D90 + slot) == exp

    # Carried dog while SprFreeze/$11 nonzero: still draws Region C, skips shadow, freezes frame
    f.put(0x0FFF, 0x00)
    f.put(0x0DD0 + slot, 0x0A)
    f.put(0x0D90 + slot, 0x08)
    f.put(0x002F, 0x04)  # Would change to frame 2/3 if unfrozen
    f.put(0x0FC1, 0x01)  # SprFreeze = 1
    f.region_c_allocs.clear()
    f.shadow_calls = 0
    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.get(0x0D90 + slot) == 0x08, "Frozen carried dog must retain frame"
    assert f.region_c_allocs == [0x10]
    assert f.shadow_calls == 0
    f.put(0x0FC1, 0x00)


def case_dog_fresh_throw_hops_and_lands_wagging(f: DogScrubFixture):
    slot = 1
    f.put(0x0FFF, 0x00)
    f._set_spr_xy(slot, 0x0100, 0x0100)
    # Simulate fresh throw from vanilla CarriedSprite_CheckForThrow ($06DF6D)
    f.put(0x0DD0 + slot, 0x09)
    f.put(0x0D80 + slot, 0x05)  # Was wagging before lift
    f.put(0x0F70 + slot, 0x10)  # Carry height 16
    f.put(0x0F80 + slot, 0x04)  # Vanilla +4 Z velocity
    f.put(0x0D50 + slot, 0x3E)  # +62 throw right
    f.put(0x0D40 + slot, 0x00)
    f.to_right = 1

    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.get(0x0D80 + slot) == 0x09, "Fresh toss must enter Dog_Tossed ($09)"
    assert f.get(0x0D50 + slot) == 0x1F, "Dog throw XSpeed must be halved to +31 ($1F)"
    assert f.get(0x0D90 + slot) == 8, "Dog_Tossed uses compact frame 8"

    landed = False
    for _ in range(80):
        f.tick_timers(slot)
        f.call_jsl("Sprite_VillageDog_Long", x=slot)
        if f.get(0x0D80 + slot) in (5, 6):
            landed = True
            break
    assert landed, "Tossed dog failed to land and transition to happy tail wag"
    sx, _ = f._spr_xy(slot)
    assert sx > 0x0120, f"Tossed dog should travel right, only reached {sx:#x}"
    assert f.get(0x0D50 + slot) == 0 and f.get(0x0D40 + slot) == 0
    assert f.get(0x0EE0 + slot) == 0x40  # Happy wag SprTimerD

    # Mid-air re-lift out of Action 9 resets SprAction so second throw works identically
    f.put(0x0D80 + slot, 0x09)
    f.put(0x0DD0 + slot, 0x0A)
    f.call_jsl("Sprite_VillageDog_Long", x=slot)
    assert f.get(0x0D80 + slot) == 0x00


# =====================================================================
# 2. Business Scrub & Eon Scrub Behind-Approach, Lift/Throw & Multi-Scrub
# =====================================================================

def case_scrub_behind_approach_and_duck(f: DogScrubFixture):
    for world_name, worldflag in (("LW", 0x00), ("DW_Eon", 0x40)):
        slot = 2
        f.put(0x0FFF, worldflag)
        f.put(0x0E20 + slot, 0x14)
        f.put(0x0E30 + slot, 0x00)
        f.put(0x0EB0 + slot, 0xFF)
        f.put(0x0DD0 + slot, 0x09)

        # Scrub at (0x100, 0x100)
        f._set_spr_xy(slot, 0x0100, 0x0100)

        # (a) Attack ($01), Link walks NORTH/behind (0x100, 0x0D0) -> ducks to $00 without shooting!
        f.spawned.clear()
        f.word(0x22, 0x0100); f.word(0x20, 0x00D0)  # Link 48px north (behind)
        f.put(0x0D80 + slot, 0x01)
        f.put(0x0DF0 + slot, 0x00)  # Timer ready to shoot!
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x00, f"{world_name}: Attack must duck when Link is behind!"
        assert not f.spawned, f"{world_name}: Must NOT fire downward when Link is behind!"

        # (b) Attack ($01), Link south/front but too close (< $20: 24px south) -> ducks to $00!
        f.word(0x22, 0x0100); f.word(0x20, 0x0118)  # Link 24px south (< $20)
        f.put(0x0D80 + slot, 0x01)
        f.put(0x0DF0 + slot, 0x00)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x00, f"{world_name}: Attack must duck when Link < $20!"
        assert not f.spawned

        # (c) PostAttack ($02), Link walks behind (north) with long timer -> ducks immediately!
        f.word(0x22, 0x0100); f.word(0x20, 0x00D0)
        f.put(0x0D80 + slot, 0x02)
        f.put(0x0DF0 + slot, 0x80)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x00, f"{world_name}: PostAttack must duck when Link is behind!"

        # (d) PostAttack ($02), Link approaches close (< $20) from front -> ducks immediately!
        f.word(0x22, 0x0100); f.word(0x20, 0x0118)
        f.put(0x0D80 + slot, 0x02)
        f.put(0x0DF0 + slot, 0x80)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x00, f"{world_name}: PostAttack must duck when Link < $20!"

        # (e) Hiding ($00), Link behind -> stays $00, solid, liftable, NO ThrownSprite call!
        f.calls.clear()
        f.word(0x22, 0x0100); f.word(0x20, 0x00E8)  # Link 24px north (behind)
        f.put(0x0D80 + slot, 0x00)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x00
        assert "cant_pass" in f.calls
        assert "check_lifted" in f.calls
        assert "thrown_interact" not in f.calls, f"{world_name}: Hiding must not call ThrownSprite!"

        # (f) Hiding ($00), Link south & >= $24 -> pops up to Attack ($01)!
        f.word(0x22, 0x0100); f.word(0x20, 0x0130)  # Link 48px south
        f.put(0x0D80 + slot, 0x00)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D80 + slot) == 0x01, f"{world_name}: Must pop up when Link is south >= $24!"

        # (g) HidingDefeated ($07) -> solid + liftable, NO ThrownSprite call!
        f.calls.clear()
        f.put(0x0D80 + slot, 0x07)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert "cant_pass" in f.calls, f"{world_name}: Defeated scrub must be solid!"
        assert "check_lifted" in f.calls
        assert "thrown_interact" not in f.calls


def case_scrub_carried_squirm_and_region_c_oam(f: DogScrubFixture):
    configs = [
        ("LW",     0x00, 13, (8, 9),   0x10, 4),
        ("DW_Eon", 0x40,  0, (11, 12), 0x08, 2),
    ]
    for name, worldflag, init_frame, squirm_frames, alloc_bytes, tile_count in configs:
        slot = 3
        f.put(0x0FFF, worldflag)
        f.put(0x0E20 + slot, 0x14)
        f.put(0x0E30 + slot, 0x00)
        f.put(0x0DD0 + slot, 0x0A)  # Carried!
        f.put(0x0D90 + slot, init_frame)
        f.put(0x0DC0 + slot, 0x03)  # Stale SprGfx
        f.put(0x0E00 + slot, 0x0A)  # Nonzero SprTimerB (must still snap frame immediately!)
        f.put(0x0D50 + slot, 0x10)
        f.put(0x0D40 + slot, 0xF0)
        f.screen = (120, 100)

        for floor, expected_pri in ((0, 0x20), (1, 0x30)):
            f.clear_oam()
            f.region_c_allocs.clear()
            f.defer_allocs = 0
            f.shadow_calls = 0
            f.put(0x0F20 + slot, floor)
            f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
            assert f.region_c_allocs == [alloc_bytes], (name, f.region_c_allocs)
            assert f.defer_allocs == 0
            assert f.shadow_calls == 0
            assert f.get(0x0DC0 + slot) == 0
            assert f.get(0x0D50 + slot) == 0 and f.get(0x0D40 + slot) == 0
            assert f.get(0x0D90 + slot) == squirm_frames[0], (name, f.get(0x0D90 + slot))
            for tx, ty, ch, prop, sz in f.oam_tiles(tile_count):
                assert ty <= f.screen[1], f"{name}: carried tile overhangs below Y ({ty} > {f.screen[1]})"
                assert (prop & 0x30) == expected_pri, (name, floor, hex(prop))

        # Expire SprTimerB -> advances to second squirm frame, then wraps back
        f.put(0x0E00 + slot, 0x00)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D90 + slot) == squirm_frames[1], (name, f.get(0x0D90 + slot))
        f.put(0x0E00 + slot, 0x00)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D90 + slot) == squirm_frames[0], (name, f.get(0x0D90 + slot))


def case_scrub_throw_all_4_directions_and_subdue_flow(f: DogScrubFixture):
    directions = [
        ("NORTH", 0x00, 0xC2, 0, -1),  # The critical bug direction (used to float frozen!)
        ("SOUTH", 0x00, 0x3E, 0, +1),
        ("WEST",  0xC2, 0x00, -1, 0),
        ("EAST",  0x3E, 0x00, +1, 0),
    ]
    for world_name, worldflag in (("LW", 0x00), ("DW_Eon", 0x40)):
        for dir_name, vx, vy, sign_x, sign_y in directions:
            slot = 2
            f.put(0x0FFF, worldflag)
            f.put(0x0E20 + slot, 0x14)
            f.put(0x0E30 + slot, 0x00)
            f.put(0x0EB0 + slot, 0xFF)
            f.put(0x0EC0 + slot, 0x00)  # SprMiscF = 0 (unsubdued)
            f.put(0x0DD0 + slot, 0x09)
            f.put(0x0D80 + slot, 0x00)  # Was hiding before lift
            f.put(0x0F70 + slot, 0x10)  # Carry height 16
            f.put(0x0F80 + slot, 0x04)  # Fresh throw SprTimerF = +4
            f.put(0x0D50 + slot, vx)
            f.put(0x0D40 + slot, vy)
            f.put(0x0D60 + slot, 0)
            f.put(0x0D70 + slot, 0)
            f.put(0x0F90 + slot, 0)
            f._set_spr_xy(slot, 0x0100, 0x0100)
            # Link is south of the scrub (Sprite_IsBelowPlayer == 0) — exactly where old NORTH throw froze!
            f.word(0x22, 0x0100); f.word(0x20, 0x0120)
            f.sfx2.clear()

            # Frame 0: must enter Action 8 (Thrown)
            f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
            assert f.get(0x0D80 + slot) == 0x08, f"{world_name} {dir_name}: must enter Action 8"

            # Tick until landed
            landed = False
            for _ in range(80):
                f.tick_timers(slot)
                f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
                if f.get(0x0D80 + slot) == 0x03:  # Recoil
                    landed = True
                    break
            assert landed, f"{world_name} {dir_name}: thrown scrub never landed into Recoil! (h={f.get(0x0F70+slot)}, vz={f.get(0x0F80+slot)})"
            assert f.get(0x0F70 + slot) == 0 and f.get(0x0F80 + slot) == 0
            assert f.get(0x0D50 + slot) == 0 and f.get(0x0D40 + slot) == 0
            assert 0x21 in f.sfx2, f"{world_name} {dir_name}: expected bonk SFX $21"
            assert f.get(0x0DF0 + slot) == 0x20

            end_x, end_y = f._spr_xy(slot)
            if sign_x < 0:
                assert end_x < 0x00E0, f"{world_name} {dir_name}: expected west travel, got {end_x:#x}"
            elif sign_x > 0:
                assert end_x > 0x0120, f"{world_name} {dir_name}: expected east travel, got {end_x:#x}"
            if sign_y < 0:
                assert end_y < 0x00E0, f"{world_name} {dir_name}: expected NORTH travel, got {end_y:#x}"
            elif sign_y > 0:
                assert end_y > 0x0120, f"{world_name} {dir_name}: expected south travel, got {end_y:#x}"

        # Follow Recoil ($03) -> Dazed ($04) -> Subdued ($05) -> Talk ($12D + prize) -> Defeated ($07)
        slot = 2
        f.messages.clear()
        f.items_received.clear()
        f.talk_accept = True
        for _ in range(200):
            f.tick_timers(slot)
            f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
            if f.get(0x0D80 + slot) == 0x07:
                break
        assert f.get(0x0D80 + slot) == 0x07, f"{world_name}: failed to complete Recoil->Dazed->Subdued->Defeated"
        assert f.messages == [0x012D], f"{world_name}: expected message $12D, got {f.messages}"
        assert len(f.items_received) == 1
        assert f.get(0x0EC0 + slot) == 0x01, f"{world_name}: SprMiscF subdued flag must be 1"


def case_scrub_already_subdued_re_lift_no_reprize(f: DogScrubFixture):
    """Regression check: vanilla Sprite_CheckIfLifted ($06F27C) zeroes SprMiscD ($0E90,X).
    Using SprMiscF ($0EC0,X) ensures re-lifting and throwing an already-subdued scrub
    returns cleanly to HidingDefeated ($07) without re-triggering Recoil or infinite prizes!
    """
    for world_name, worldflag in (("LW", 0x00), ("DW_Eon", 0x40)):
        slot = 2
        f.put(0x0FFF, worldflag)
        f.put(0x0E20 + slot, 0x14)
        f.put(0x0E30 + slot, 0x00)
        f.put(0x0EB0 + slot, 0xFF)
        f.put(0x0EC0 + slot, 0x01)  # Already subdued!
        f.put(0x0E90 + slot, 0x01)  # Even if legacy SprMiscD was set...
        f.put(0x0DD0 + slot, 0x09)
        f.put(0x0D80 + slot, 0x07)  # HidingDefeated / EonScrub_Defeated
        f.put(0x0D50 + slot, 0x00)
        f.put(0x0D40 + slot, 0x00)
        f._set_spr_xy(slot, 0x0100, 0x0100)

        # Lift from HidingDefeated -> stub zeroes $0E90 (SprMiscD) just like vanilla!
        f.lift_trigger = True
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0DD0 + slot) == 0x0A
        assert f.get(0x0E90 + slot) == 0x00, "Sanity: vanilla lift clears SprMiscD"
        assert f.get(0x0EC0 + slot) == 0x01, "SprMiscF must survive vanilla Sprite_CheckIfLifted!"

        # Carry frame -> squirms overhead
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0DD0 + slot) == 0x0A

        # Throw north
        f.put(0x0DD0 + slot, 0x09)
        f.put(0x0F70 + slot, 0x10)
        f.put(0x0F80 + slot, 0x04)
        f.put(0x0D50 + slot, 0x00)
        f.put(0x0D40 + slot, 0xC2)
        f.sfx2.clear()

        for _ in range(80):
            f.tick_timers(slot)
            f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
            if f.get(0x0D80 + slot) == 0x07 and f.get(0x0F70 + slot) == 0 and f.get(0x0F80 + slot) == 0:
                break
        assert f.get(0x0D80 + slot) == 0x07, f"{world_name}: already-subdued toss must return to Action 7!"
        assert 0x21 not in f.sfx2, f"{world_name}: already-subdued landing must not play bonk/recoil SFX"


def case_scrub_pit_or_water_aborts_recoil(f: DogScrubFixture):
    for worldflag in (0x00, 0x40):
        for hazard_state in (0x01, 0x03):  # 01 = pit fall, 03 = water splash
            slot = 2
            f.put(0x0FFF, worldflag)
            f.put(0x0E20 + slot, 0x14)
            f.put(0x0E30 + slot, 0x00)
            f.put(0x0EC0 + slot, 0x00)
            f.put(0x0DD0 + slot, 0x09)
            f.put(0x0D80 + slot, 0x08)  # Already in Thrown
            f.put(0x0F70 + slot, 0x01)
            f.put(0x0F80 + slot, 0xF0)  # Falling fast -> lands this frame
            f.thrown_hazard_state = hazard_state
            f.sfx2.clear()

            f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
            assert f.get(0x0DD0 + slot) == hazard_state
            assert f.get(0x0D80 + slot) == 0x08, "Pit/water hazard must not transition to Recoil!"
            assert not f.sfx2
    f.thrown_hazard_state = None


def case_scrub_per_slot_child_tracking_and_isolation(f: DogScrubFixture):
    boss_sentinel = 0x0D
    f.put(0x7E1E84, boss_sentinel)  # Offspring1_Id owned by a boss!
    f.put(0x0FFF, 0x00)

    # Prep Slot 0 and Slot 2 parents
    for slot in (0, 2):
        f.put(0x0E20 + slot, 0x14)
        f.put(0x0E30 + slot, 0x00)
        f.put(0x0DD0 + slot, 0x09)
        f.put(0x0D80 + slot, 0x01)  # Attack
        f.call_jsl("Sprite_BusinessScrub_Prep", x=slot)
        assert f.get(0x0EB0 + slot) == 0xFF, f"Prep must init SprMiscE[{slot}] = $FF"
    assert f.get(0x7E1E84) == boss_sentinel

    # Slot 0 runs CheckForPeaShotRedirect before firing -> MUST NOT self-kill!
    f._set_spr_xy(0, 0x0100, 0x0100)
    f.call_jsl("CheckForPeaShotRedirect_Wrap", x=0, db=0x30)
    assert f.get(0x0DD0 + 0) == 0x09 and f.get(0x0D80 + 0) == 0x01
    assert f.get(0x7E1E84) == boss_sentinel

    # Both scrubs fire -> get separate child slots 4 and 5 in SprMiscE (Offspring1_Id untouched!)
    f.next_spawn_slot = 4
    f.word(0x22, 0x0100); f.word(0x20, 0x0140)  # Link 64px south
    f._set_spr_xy(0, 0x0100, 0x0100)
    f.put(0x0DF0 + 0, 0x00)
    f.call_jsl("Sprite_BusinessScrub_Long", x=0)
    assert f.get(0x0EB0 + 0) == 4
    assert f.get(0x0D80 + 0) == 0x02  # PostAttack
    assert f.get(0x7E1E84) == boss_sentinel

    f._set_spr_xy(2, 0x0140, 0x0100)
    f.put(0x0DF0 + 2, 0x00)
    f.call_jsl("Sprite_BusinessScrub_Long", x=2)
    assert f.get(0x0EB0 + 2) == 5
    assert f.get(0x0D80 + 2) == 0x02
    assert f.get(0x7E1E84) == boss_sentinel

    # Downward unreflected nut (SprYSpeed = +$10) overlapping Slot 2 -> MUST NOT recoil!
    f._set_spr_xy(5, 0x0140, 0x0100)
    f.put(0x0D40 + 5, 0x10)
    f.call_jsl("CheckForPeaShotRedirect_Wrap", x=2, db=0x30)
    assert f.get(0x0D80 + 2) == 0x02 and f.get(0x0DD0 + 5) == 0x09

    # Reflect ONLY Slot 5 (SprYSpeed = -$10 = $F0) onto Slot 2:
    # Slot 0 must stay unaffected; Slot 2 must recoil and kill ONLY Slot 5!
    f.put(0x0D40 + 5, 0xF0)
    f._set_spr_xy(0, 0x0100, 0x0100)
    f.call_jsl("CheckForPeaShotRedirect_Wrap", x=0, db=0x30)
    assert f.get(0x0D80 + 0) == 0x02 and f.get(0x0DD0 + 4) == 0x09 and f.get(0x0DD0 + 5) == 0x09

    f._set_spr_xy(2, 0x0140, 0x0100)
    f.call_jsl("CheckForPeaShotRedirect_Wrap", x=2, db=0x30)
    assert f.get(0x0D80 + 2) == 0x03, "Reflected nut must recoil Slot 2"
    assert f.get(0x0DF0 + 2) == 0x20, "LW BeginRecoil must set 32-frame spin timer"
    assert f.get(0x0DD0 + 5) == 0x00, "Slot 2's child (Slot 5) must be consumed"
    assert f.get(0x0EB0 + 2) == 0xFF, "Slot 2's SprMiscE must reset to $FF"
    assert f.get(0x0DD0 + 4) == 0x09, "Slot 0's child (Slot 4) must NOT be killed!"
    assert f.get(0x7E1E84) == boss_sentinel, "Offspring1_Id must remain untouched!"

    # Recycled slot safety: if Slot 4 is reused by an unrelated sprite ($55) moving north,
    # Slot 0 must NOT recoil or kill it!
    f.put(0x0E20 + 4, 0x55)  # Unrelated sprite type
    f.put(0x0D40 + 4, 0xF0)
    f._set_spr_xy(4, 0x0100, 0x0100)
    f._set_spr_xy(0, 0x0100, 0x0100)
    f.call_jsl("CheckForPeaShotRedirect_Wrap", x=0, db=0x30)
    assert f.get(0x0D80 + 0) == 0x02 and f.get(0x0DD0 + 4) == 0x09

    # Eon Scrub (WORLDFLAG != 0) spawns per-slot child in SprMiscE (never touches Offspring1_Id),
    # and a reflected nut hitting it during Attack or Stalking recoils cleanly even if Link is behind!
    f.put(0x0FFF, 0x40)
    eon_slot = 3
    f.put(0x0E20 + eon_slot, 0x14)
    f.put(0x0E30 + eon_slot, 0x00)
    f.put(0x0DD0 + eon_slot, 0x09)
    f.put(0x0D80 + eon_slot, 0x01)
    f.call_jsl("Sprite_BusinessScrub_Prep", x=eon_slot)
    assert f.get(0x0EB0 + eon_slot) == 0xFF
    f.next_spawn_slot = 6
    f._set_spr_xy(eon_slot, 0x0100, 0x0100)
    f.word(0x22, 0x0100); f.word(0x20, 0x0140)  # Link south
    f.put(0x0DF0 + eon_slot, 0x00)
    f.call_jsl("Sprite_BusinessScrub_Long", x=eon_slot)
    assert f.get(0x0EB0 + eon_slot) == 6
    assert f.get(0x7E1E84) == boss_sentinel
    # Duck to Stalking (0), reflect Slot 6 back onto Eon Scrub while Link stands close/behind
    f.put(0x0D80 + eon_slot, 0x00)
    f.put(0x0D40 + 6, 0xF0)
    f._set_spr_xy(6, 0x0100, 0x0100)
    f.word(0x22, 0x0100); f.word(0x20, 0x00F0)  # Link north/behind!
    f.call_jsl("Sprite_BusinessScrub_Long", x=eon_slot)
    assert f.get(0x0D80 + eon_slot) == 0x03, "Reflected nut must recoil stalking Eon Scrub!"
    assert f.get(0x0DD0 + 6) == 0x00
    assert f.get(0x0EB0 + eon_slot) == 0xFF
    assert f.get(0x7E1E84) == boss_sentinel


def case_shield_reflects_both_lw_and_eon_peashots(f: DogScrubFixture):
    for world_name, worldflag in (("LW", 0x00), ("DW_Eon", 0x40)):
        slot = 5
        f.put(0x0FFF, worldflag)
        f.put(0x0E20 + slot, 0x14)
        f.put(0x0E30 + slot, 0x01)  # PeaShot subtype!
        f.put(0x0D80 + slot, 0x06)  # PeaShot action
        f.put(0x0DD0 + slot, 0x09)
        f.put(0x0DE0 + slot, 0x02)  # SprMiscC = 2
        f.put(0x0F20 + slot, 0x00)  # Layer 0
        f.put(0x0D40 + slot, 0x10)  # Falling downward (+16)
        f._set_spr_xy(slot, 0x0100, 0x0100)

        # Idle human Link facing north with Fighter Shield right at the nut
        f.put(0x7EF35A, 0x01)  # Fighter Shield
        f.put(0x002F, 0x00)    # Facing North
        f.put(0x005D, 0x00); f.put(0x003C, 0x00)
        f.put(0x02E0, 0x00); f.put(0x037B, 0x00); f.put(0x02B2, 0x00)
        f.put(0x0308, 0x00); f.put(0x00EE, 0x00)
        f.word(0x22, 0x0100); f.word(0x20, 0x0104)

        f.sfx2.clear()
        f.dmg_to_player_calls = 0
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.get(0x0D40 + slot) == 0xF0, f"{world_name}: Shield must reflect nut to -$10 ($F0)!"
        assert f.get(0x0DE0 + slot) == 0x00, f"{world_name}: Reflected nut must clear SprMiscC"
        assert 0x06 in f.sfx2, f"{world_name}: Shield reflection must play clink SFX $06"
        assert f.dmg_to_player_calls == 0, f"{world_name}: Shield-reflected nut must NOT hurt Link!"

        # Outgoing reflected nut on next frame must STILL not hurt Link
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.dmg_to_player_calls == 0

        # Without shield ($7EF35A = 0), downward nut falls through to player damage
        f.put(0x7EF35A, 0x00)
        f.put(0x0D40 + slot, 0x10)
        f._set_spr_xy(slot, 0x0100, 0x0100)
        f.call_jsl("Sprite_BusinessScrub_Long", x=slot)
        assert f.dmg_to_player_calls == 1, f"{world_name}: Unshielded nut must call DamageToPlayer!"


ALL_CASES = [
    ("dog_carried_region_c_and_no_shadow",         case_dog_carried_region_c_and_no_shadow),
    ("dog_grounded_defer_to_player_and_shadow",    case_dog_grounded_defer_to_player_and_shadow),
    ("dog_carried_bg_priority_layer_and_palettes", case_dog_carried_bg_priority_layer_and_palettes),
    ("dog_carried_compact_pose_and_freeze",        case_dog_carried_compact_pose_and_freeze),
    ("dog_fresh_throw_hops_and_lands_wagging",     case_dog_fresh_throw_hops_and_lands_wagging),
    ("scrub_behind_approach_and_duck",             case_scrub_behind_approach_and_duck),
    ("scrub_carried_squirm_and_region_c_oam",      case_scrub_carried_squirm_and_region_c_oam),
    ("scrub_throw_all_4_directions_and_subdue",    case_scrub_throw_all_4_directions_and_subdue_flow),
    ("scrub_already_subdued_re_lift_no_reprize",   case_scrub_already_subdued_re_lift_no_reprize),
    ("scrub_pit_or_water_aborts_recoil",           case_scrub_pit_or_water_aborts_recoil),
    ("scrub_per_slot_child_tracking_isolation",    case_scrub_per_slot_child_tracking_and_isolation),
    ("shield_reflects_both_lw_and_eon_peashots",   case_shield_reflects_both_lw_and_eon_peashots),
]


def run_all(lakesnes: Path | None = None) -> list[str]:
    ls = find_lakesnes(lakesnes)
    passed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="dog-scrub-cpu-") as tmp:
        d = Path(tmp)
        lib = build_cpu_lib(ls, d)
        rom, labels = assemble_fixture(d / "build")
        for name, fn in ALL_CASES:
            f = DogScrubFixture(lib, rom, labels)
            try:
                fn(f)
                passed.append(name)
            finally:
                f.close()
    return passed


# Shared compiled fixture for fast individual pytest cases
_SHARED_TMP: tempfile.TemporaryDirectory | None = None
_SHARED_ENV: tuple | None = None


def _get_shared_env():
    global _SHARED_TMP, _SHARED_ENV
    if _SHARED_ENV is None:
        ls = find_lakesnes()
        _SHARED_TMP = tempfile.TemporaryDirectory(prefix="dog-scrub-pytest-")
        d = Path(_SHARED_TMP.name)
        lib = build_cpu_lib(ls, d)
        rom, labels = assemble_fixture(d / "build")
        _SHARED_ENV = (lib, rom, labels)
    return _SHARED_ENV


def _run_case(name: str):
    lib, rom, labels = _get_shared_env()
    f = DogScrubFixture(lib, rom, labels)
    try:
        dict(ALL_CASES)[name](f)
    finally:
        f.close()


def test_dog_carried_region_c_and_no_shadow():
    _run_case("dog_carried_region_c_and_no_shadow")


def test_dog_grounded_defer_to_player_and_shadow():
    _run_case("dog_grounded_defer_to_player_and_shadow")


def test_dog_carried_bg_priority_layer_and_palettes():
    _run_case("dog_carried_bg_priority_layer_and_palettes")


def test_dog_carried_compact_pose_and_freeze():
    _run_case("dog_carried_compact_pose_and_freeze")


def test_dog_fresh_throw_hops_and_lands_wagging():
    _run_case("dog_fresh_throw_hops_and_lands_wagging")


def test_scrub_behind_approach_and_duck():
    _run_case("scrub_behind_approach_and_duck")


def test_scrub_carried_squirm_and_region_c_oam():
    _run_case("scrub_carried_squirm_and_region_c_oam")


def test_scrub_throw_all_4_directions_and_subdue():
    _run_case("scrub_throw_all_4_directions_and_subdue")


def test_scrub_already_subdued_re_lift_no_reprize():
    _run_case("scrub_already_subdued_re_lift_no_reprize")


def test_scrub_pit_or_water_aborts_recoil():
    _run_case("scrub_pit_or_water_aborts_recoil")


def test_scrub_per_slot_child_tracking_isolation():
    _run_case("scrub_per_slot_child_tracking_isolation")


def test_shield_reflects_both_lw_and_eon_peashots():
    _run_case("shield_reflects_both_lw_and_eon_peashots")


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lakesnes", type=Path, default=None)
    ap.add_argument("--output", type=Path, default=None)
    args = ap.parse_args()
    passed = run_all(args.lakesnes)
    result = {"status": "PASS", "count": len(passed), "cases": passed}
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
