#!/usr/bin/env python3
"""Compiled 65816 unit tests (Lakesnes) for Wayward Village living-town ASM.

Assembles the real worktree source files:
  - Sprites/NPCs/village_elder.asm
  - Overworld/village_bar_exit.asm
  - Overworld/richard_quest.asm
  - Sprites/NPCs/village_animals.asm

Each routine executes on Lakesnes' 65816 core with explicit ABI stubs for
vanilla engine calls. No emulator process, socket, or shared ROM write is used.
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


# Stub addresses (all in unmapped/stubbed engine ROM sites, never colliding with assembled banks)
STUB_CANT_PASS      = 0x1EF4F3
STUB_SHOW_SOLICITED = 0x05E1A7
STUB_SHOW_UNCOND    = 0x05E219
STUB_SHOW_CONTACT   = 0x05E1F0
STUB_SPAWN_DYN      = 0x1DF674
STUB_SPR_MOVE       = 0x068800
STUB_SPR_MOVE_LONG  = 0x068810
STUB_CHK_DMG_FROM   = 0x068820
STUB_CHK_DMG_TO     = 0x068830
STUB_SFX2_PAN       = 0x068840
STUB_SFX3_PAN       = 0x068850
STUB_IS_RIGHT       = 0x068860
STUB_DIR_FACE       = 0x068870
STUB_RECEIVE_ITEM   = 0x0791B3
STUB_DRAW_RACE_LADY = 0x1AF92C
STUB_DRAW_SHADOW    = 0x06DC54
STUB_DRAW_TAB       = 0x05DF75
STUB_CHK_ACTIVE     = 0x06D9EC
STUB_VAN_SNITCH_PRP = 0x05E675
STUB_VAN_SNITCH_MN  = 0x05E69A


FIXTURE_ASM = """lorom

; ---- Shared symbol definitions matching Core/symbols.asm & Core/sram.asm ----
OOSPROG             = $7EF3D6
Flute               = $7EF34C
ElderGuideStage     = $7EF388
GameState           = $7EF3C5
RichardQuestFlags   = $7EF3C4
!Richard_Asked      = $01
!Richard_Found      = $02
!Richard_Delivered  = $04
!Richard_Rewarded   = $08
!Crystal_D1_MushroomGrotto = $02
!Crystal_D2_TailPalace     = $10

struct TimeState $7EE000
  .Hours: skip 1
endstruct

SprY        = $0D00
SprX        = $0D10
SprYH       = $0D20
SprXH       = $0D30
SprYSpeed   = $0D40
SprXSpeed   = $0D50
SprAction   = $0D80
SprFrame    = $0D90
SprGfx      = $0DC0
SprState    = $0DD0
SprMiscC    = $0DE0
SprTimerA   = $0DF0
SprTimerB   = $0E00
SprType     = $0E20
SprSubtype  = $0E30
SprMiscB    = $0E80
SprMiscD    = $0E90
SprMiscE    = $0EB0
SprMiscF    = $0EC0
SprFloor    = $0F20
SprHeight   = $0F70
SprTimerF   = $0F80

Sprite_PlayerCantPassThrough             = $1EF4F3
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7
Sprite_ShowMessageUnconditional          = $05E219
Sprite_SpawnDynamically                  = $1DF674
Sprite_Move                              = $068800
Sprite_MoveLong                          = $068810
Sprite_CheckDamageFromPlayer             = $068820
Sprite_CheckDamageToPlayer               = $068830
Sound_SetSfx2PanLong                     = $068840
Sound_SetSfx3PanLong                     = $068850
Sprite_IsToRightOfPlayer                 = $068860
Sprite_DirectionToFacePlayer             = $068870
Link_ReceiveItem                         = $0791B3
SpriteDraw_RaceGameLady                  = $1AF92C
Sprite_DrawShadow                        = $06DC54
Sprite_CheckActive                       = $06D9EC

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

; ---- Assemble real owned modules into isolated banks ----
org $308000
VillageElder_Wrap:
  PHB : PHK : PLB
  JSR Sprite_VillageElder_Main
  PLB
  RTL
incsrc "village_elder.asm"

org $2B8000
incsrc "village_bar_exit.asm"
incsrc "village_animals.asm"

org $348000
incsrc "richard_quest.asm"
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


def assemble_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    for rel in (
        "Sprites/NPCs/village_elder.asm",
        "Overworld/village_bar_exit.asm",
        "Overworld/richard_quest.asm",
        "Sprites/NPCs/village_animals.asm",
    ):
        (folder / Path(rel).name).write_bytes((ROOT / rel).read_bytes())
    asm = folder / "fixture.asm"
    asm.write_text(FIXTURE_ASM, encoding="utf-8")
    image = folder / "fixture.sfc"
    buf = bytearray(b"\xFF" * 0x200000)

    def seed(snes: int, raw: bytes):
        pc = (((snes >> 16) & 0x7F) << 15) | (snes & 0x7FFF)
        buf[pc : pc + len(raw)] = raw

    # Pre-seed vanilla hook-site bytes checked by assert read*() in village_animals.asm
    seed(0x06F244, bytes([0xBD, 0x20, 0x0E, 0xC9, 0x0B, 0xF0, 0x0C, 0xC9, 0x4A, 0xF0, 0x08]))
    seed(0x05A8CE, bytes([0x20, 0x93, 0xAB, 0x20, 0xED, 0xF9]))
    seed(0x068CA1, bytes([0xA5, 0xA0, 0xA0, 0x00, 0xD9, 0x99, 0x8C, 0xF0, 0x03, 0xC8, 0xD0, 0xF8]))
    seed(0x06AE34, bytes([0xBD, 0xF0, 0x0D, 0xD0, 0x19]))
    seed(0x06AF1A, bytes([0xBD, 0x80, 0x0E, 0x0A, 0x7D, 0xC0, 0x0D]))
    image.write_bytes(buf)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(image)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, f"Asar failed:\n{res.stdout}\n{res.stderr}"
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
                             image.with_suffix(".sym").read_text(encoding="utf-8"))
    }
    return image.read_bytes(), labels


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


class WaywardFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.stubs = {
            STUB_CANT_PASS:      "cant_pass",
            STUB_SHOW_SOLICITED: "show_solicited",
            STUB_SHOW_UNCOND:    "show_uncond",
            STUB_SHOW_CONTACT:   "show_contact",
            STUB_SPAWN_DYN:      "spawn_dyn",
            STUB_SPR_MOVE:       "spr_move",
            STUB_SPR_MOVE_LONG:  "spr_move_long",
            STUB_CHK_DMG_FROM:   "chk_dmg_from",
            STUB_CHK_DMG_TO:     "chk_dmg_to",
            STUB_SFX2_PAN:       "sfx2_pan",
            STUB_SFX3_PAN:       "sfx3_pan",
            STUB_IS_RIGHT:       "is_right",
            STUB_DIR_FACE:       "dir_face",
            STUB_RECEIVE_ITEM:   "receive_item",
            STUB_DRAW_RACE_LADY: "draw_race_lady",
            STUB_DRAW_SHADOW:    "draw_shadow",
            STUB_DRAW_TAB:       "draw_tab",
            STUB_CHK_ACTIVE:     "chk_active",
            STUB_VAN_SNITCH_PRP: "van_snitch_prep",
            STUB_VAN_SNITCH_MN:  "van_snitch_main",
        }
        self.talk_accept = True
        self.messages: list[int] = []
        self.spawned: list[tuple[int, int]] = []
        self.sfx2: list[int] = []
        self.sfx3: list[int] = []
        self.to_right = 0
        self.next_spawn_slot = 5

    def stub(self, name: str):
        c = self.cpu
        self.calls.append(name)
        if name == "show_solicited":
            mid = ((c.y & 0xFF) << 8) | (c.a & 0xFF)
            if self.talk_accept:
                self.messages.append(mid)
                c.c = True
            else:
                c.c = False
        elif name == "show_uncond":
            mid = ((c.y & 0xFF) << 8) | (c.a & 0xFF)
            self.messages.append(mid)
        elif name == "spawn_dyn":
            spr_id = c.a & 0xFF
            slot = self.next_spawn_slot
            self.next_spawn_slot += 1
            if slot < 16:
                self.put(0x0DD0 + slot, 0x09)
                self.put(0x0E20 + slot, spr_id)
                self.put(0x0E30 + slot, 0x00)
                c.y = slot
                c.n = False
                self.spawned.append((slot, spr_id))
            else:
                c.y = 0xFF
                c.n = True
        elif name == "sfx2_pan":
            self.sfx2.append(c.a & 0xFF)
        elif name == "sfx3_pan":
            self.sfx3.append(c.a & 0xFF)
        elif name == "is_right":
            c.y = self.to_right
        elif name == "chk_active":
            c.c = True

    def call_jsl(self, label: str, *, a: int = 0, x: int = 0, y: int = 0,
                 db: int = 0x06, m16: bool = False, x16: bool = False, max_ops: int = 30000):
        c = self.cpu
        c.mf = not m16
        c.xf = not x16
        c.a = a & (0xFFFF if m16 else 0xFF)
        c.x = x & (0xFFFF if x16 else 0xFF)
        c.y = y & (0xFFFF if x16 else 0xFF)
        c.db = db
        c.c = c.z = c.n = c.v = False
        entry = self.addr(label)
        assert entry is not None, f"Missing label: {label}"
        c.k = entry >> 16
        c.pc = entry & 0xFFFF
        sp = c.sp
        # Push 24-bit return address ($<entry_bank>:6FFF -> RTL lands on $7000)
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
                return count
            if pc_addr in self.stubs:
                self.stub(self.stubs[pc_addr])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{label}: exceeded {max_ops} ops at ${(c.k << 16) | c.pc:06X}")


# =====================================================================
# 1. Village Elder (Sprites/NPCs/village_elder.asm)
# =====================================================================

def case_elder_snaps_to_frame2_no_bean_flash(f: WaywardFixture):
    slot = 1
    f.put(0x0D90 + slot, 0x00)  # Fresh spawn SprFrame = 0 (would flash Bean Vendor / Magic Bean!)
    f.put(0x0E00 + slot, 0x00)  # SprTimerB = 0
    f.talk_accept = False
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    # %StartOnFrame(2) clamps 0 -> 2, then %PlayAnimation(2,3,16) advances 2 -> 3 with timer 16!
    assert f.get(0x0D90 + slot) in (2, 3), f"Expected Mayor frame 2/3, got {f.get(0x0D90 + slot)}"
    assert f.get(0x0E00 + slot) == 16
    # Verify cycling stays strictly within {2, 3}
    f.put(0x0E00 + slot, 0x00)
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.get(0x0D90 + slot) == 2
    f.put(0x0E00 + slot, 0x00)
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.get(0x0D90 + slot) == 3


def case_elder_dialogue_progression(f: WaywardFixture):
    slot = 1
    f.put(0x0D90 + slot, 2)
    f.put(0x7EF3D6, 0x00)  # OOSPROG = 0
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.messages == [0x0143]
    assert f.get(0x7EF3D6) == 0x10

    # After first meeting, before D1 -> default $0019
    f.messages.clear()
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.messages == [0x0019]

    # Post-D1, pre-D2, no Ocarina -> Ranch Girl hint $01CB + sets ElderGuideStage low nibble
    f.messages.clear()
    f.put(0x7EF37A, 0x02)  # Crystal D1
    f.put(0x7EF34C, 0x00)  # No Ocarina
    f.put(0x7EF388, 0x00)  # ElderGuideStage = 0
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.messages == [0x01CB]
    assert (f.get(0x7EF388) & 0x0F) == 1

    # Once Ocarina is owned -> falls back to $0019 even if hint stage was 0
    f.messages.clear()
    f.put(0x7EF388, 0x00)
    f.put(0x7EF34C, 0x01)
    f.call_jsl("VillageElder_Wrap", x=slot, db=0x30)
    assert f.messages == [0x0019]


# =====================================================================
# 2. Wayward Bar & $0106 Shed Exit Precheck (Overworld/village_bar_exit.asm)
# =====================================================================

def case_bar_exit_north_and_south(f: WaywardFixture):
    # Preserve sprite sheet bytes $7EC164-$7EC167 when cached area is $0023
    f.word(0x7EC140, 0x0023)
    f.word(0x7EC164, 0x492B)
    f.word(0x7EC166, 0x504A)

    # North exit (Backdoor $43): room $0103, $22 < $0700, $20 < $2100
    f.word(0x00A0, 0x0103)
    f.word(0x0022, 0x0678)
    f.word(0x0020, 0x2020)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.cpu.db == 0x02 and not f.cpu.mf and f.cpu.xf
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0xFFFF
    assert f.get(0x0698) | (f.get(0x0699) << 8) == 0x0000
    assert f.get(0x7EC148) | (f.get(0x7EC149) << 8) == 0x0A29  # Backdoor spawn Y
    assert f.get(0x7EC164) | (f.get(0x7EC165) << 8) == 0x492B  # Preserved live sheets
    assert f.get(0x7EC166) | (f.get(0x7EC167) << 8) == 0x504A
    assert not f.cpu.z and not f.cpu.c  # $0103 < $0104

    # South exit (Frontdoor $42): room $0103, $22 < $0700, $20 >= $2100
    f.word(0x0020, 0x21D8)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0x14DA
    assert f.get(0x7EC148) | (f.get(0x7EC149) << 8) == 0x0A88  # Frontdoor spawn Y

    # Right half ($44 cottage): $22 >= $0700 -> untouched
    f.word(0x0696, 0x15CA)
    f.word(0x0022, 0x0778)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0x15CA


def case_shed_0106_exit_opened_door_overlay(f: WaywardFixture):
    # Room $0106 exiting to OW $23 with $0696 == 0 -> sets $0696 = $1112, $0698 = 0
    f.word(0x00A0, 0x0106)
    f.word(0x7EC140, 0x0023)
    f.word(0x0696, 0x0000)
    f.word(0x0698, 0x1234)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0x1112
    assert f.get(0x0698) | (f.get(0x0699) << 8) == 0x0000
    assert not f.cpu.z and f.cpu.c  # $0106 > $0104
    assert f.cpu.db == 0x02 and not f.cpu.mf and f.cpu.xf

    # If ROM already supplies $0696 != 0 -> leave untouched
    f.word(0x0696, 0x1114)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0x1114

    # If cached exit area is not $0023 -> leave $0696 == 0 untouched
    f.word(0x7EC140, 0x0018)
    f.word(0x0696, 0x0000)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.get(0x0696) | (f.get(0x0697) << 8) == 0x0000

    # Other room $0104 returns Z=1, C=1
    f.word(0x00A0, 0x0104)
    f.call_jsl("VillageBar_ExitPrecheck", db=0x02, m16=True, x16=False)
    assert f.cpu.z and f.cpu.c


# =====================================================================
# 3. Richard Quest Phase-2 Home Lady & Talk (Overworld/richard_quest.asm)
# =====================================================================

def case_richard_home_lady_phase2_fallback(f: WaywardFixture):
    # Nighttime / Phase 2 on OW $23, GameState = 2, not yet delivered, Link near (1680, 2464)
    f.put(0x0010, 0x09)    # Overworld mode
    f.put(0x0011, 0x00)
    f.put(0x008A, 0x23)    # OW $23
    f.put(0x7EF3C5, 0x02)  # GameState = 2
    f.put(0x7EF3C4, 0x03)  # Asked | Found (not Delivered)
    f.put(0x7EE000, 22)    # 22:00 night (Phase 2)
    f.word(0x0022, 0x06A0) # Near X = $0690
    f.word(0x0020, 0x09B0) # Near Y = $09A0

    f.call_jsl("RichardQuest_Tick", db=0x00)
    # Must spawn BOTH missing lady ($3D sub=0) AND home Richard ($25 sub=1) beside her!
    ids = [spr_id for _, spr_id in f.spawned]
    assert ids == [0x3D, 0x25], f"Expected [$3D, $25], got {[hex(x) for x in ids]}"
    lady_slot = f.spawned[0][0]
    dog_slot = f.spawned[1][0]
    assert f.get(0x0DD0 + lady_slot) == 0x08  # Queued for RichardLady_Prep -> SpritePrep_Snitch
    assert (f.get(0x0D10 + lady_slot) | (f.get(0x0D30 + lady_slot) << 8)) == 0x0690
    assert (f.get(0x0D00 + lady_slot) | (f.get(0x0D20 + lady_slot) << 8)) == 0x09A0
    assert f.get(0x0E30 + dog_slot) == 0x01
    assert (f.get(0x0D10 + dog_slot) | (f.get(0x0D30 + dog_slot) << 8)) == 0x06A4

    # Calling again must NOT double-spawn either actor
    f.spawned.clear()
    f.call_jsl("RichardQuest_Tick", db=0x00)
    assert f.spawned == []


def case_richard_home_lady_guards(f: WaywardFixture):
    f.put(0x0010, 0x09)
    f.put(0x0011, 0x00)
    f.put(0x008A, 0x23)
    f.word(0x0022, 0x0690)
    f.word(0x0020, 0x09A0)

    # Guard 1: Part00 (GameState < 2) -> never spawns
    f.put(0x7EF3C5, 0x00)
    f.put(0x7EF3C4, 0x00)
    f.call_jsl("RichardQuest_Tick", db=0x00)
    assert f.spawned == []

    # Guard 2: Already delivered -> never spawns outdoors
    f.put(0x7EF3C5, 0x02)
    f.put(0x7EF3C4, 0x07)  # Delivered set
    f.call_jsl("RichardQuest_Tick", db=0x00)
    assert f.spawned == []

    # Guard 3: Link far away on OW $23 -> off-camera cull guard skips spawn
    f.put(0x7EF3C4, 0x00)
    f.word(0x0022, 0x0900)
    f.call_jsl("RichardQuest_Tick", db=0x00)
    assert f.spawned == []


def case_richard_lady_talk_solicited_no_guards(f: WaywardFixture):
    slot = 3
    f.put(0x008A, 0x23)
    f.put(0x7EF3C4, 0x00)  # Not yet asked/found
    f.call_jsl("RichardLady_Talk", a=0x2F, x=slot, y=0x00, db=0x05)
    assert not f.cpu.c  # Always carry clear -> never reaches Snitch_SpawnGuard!
    assert "show_contact" not in f.calls
    assert f.get(0x7EF3C4) == 0x01  # !Richard_Asked

    # After Richard is found -> delivery triggers run action 4 + sets Delivered
    f.put(0x7EF3C4, 0x03)  # Asked | Found
    f.call_jsl("RichardLady_Talk", a=0x2F, x=slot, y=0x00, db=0x05)
    assert not f.cpu.c
    assert f.get(0x7EF3C4) == 0x07  # Delivered set
    assert f.get(0x0D80 + slot) == 0x04  # !RichardRunAction


# =====================================================================
# 4. Village Animals (Sprites/NPCs/village_animals.asm)
# =====================================================================

def case_village_cat_prep_all_wayward_rooms(f: WaywardFixture):
    # Overworld $23 -> Action 3 (Cat)
    f.put(0x001B, 0x00)
    f.put(0x008A, 0x23)
    f.call_jsl("VillageCat_Prep", db=0x06)
    assert (f.cpu.y & 0xFF) == 0x03

    # All 7 peaceful Wayward interiors + legacy $000F -> Action 3
    for room in (0x000F, 0x0102, 0x0103, 0x0104, 0x0106, 0x0107, 0x0119, 0x011F):
        f.put(0x001B, 0x01)
        f.word(0x00A0, room)
        f.call_jsl("VillageCat_Prep", db=0x06)
        assert (f.cpu.y & 0xFF) == 0x03, f"Room {room:#06x} got Y={f.cpu.y:#x}"

    # Vanilla storyteller room $0112 -> index 2 preserved
    f.put(0x001B, 0x01)
    f.word(0x00A0, 0x0112)
    f.call_jsl("VillageCat_Prep", db=0x06)
    assert (f.cpu.y & 0xFF) == 0x02


def case_village_cucco_multiform_routing(f: WaywardFixture):
    slot = 2
    f.put(0x0E20 + slot, 0x0B)  # Cucco

    # Human ($02B2=0): C=1 -> vanilla permissive lift
    f.put(0x02B2, 0x00)
    f.call_jsl("VillageCucco_LiftOrTalk", x=slot, db=0x06)
    assert f.cpu.c

    # Minish ($02B2=5): C=0, Z=1 -> skip lift, solicited talk + cluck + hop action 1
    f.messages.clear(); f.sfx2.clear()
    f.put(0x02B2, 0x05)
    f.put(0x0D80 + slot, 0x00)
    f.call_jsl("VillageCucco_LiftOrTalk", x=slot, db=0x06)
    assert not f.cpu.c and f.cpu.z
    assert f.messages == [0x0018] and f.sfx2 == [0x30]
    assert f.get(0x0D80 + slot) == 0x01

    # Wolf ($02B2=3): C=0, Z=1 -> panicked talk + cluck + flee action 2
    f.messages.clear(); f.sfx2.clear()
    f.put(0x02B2, 0x03)
    f.put(0x0D80 + slot, 0x00)
    f.call_jsl("VillageCucco_LiftOrTalk", x=slot, db=0x06)
    assert not f.cpu.c and f.cpu.z
    assert f.messages == [0x001B] and f.sfx2 == [0x30]
    assert f.get(0x0D80 + slot) == 0x02


def case_village_rat_peaceful_vs_hostile(f: WaywardFixture):
    slot = 4
    f.put(0x001B, 0x01)   # Indoors
    f.put(0x0FFF, 0x00)   # Light World
    f.word(0x0022, 0x0100)
    f.word(0x0020, 0x0100)
    f.put(0x0D10 + slot, 0x08); f.put(0x0D30 + slot, 0x01)
    f.put(0x0D00 + slot, 0x00); f.put(0x0D20 + slot, 0x01)

    # Minish in Library $0107 -> peaceful talk, zero damage calls
    f.word(0x00A0, 0x0107)
    f.put(0x02B2, 0x05)
    f.call_jsl("VillageRat_InteractOrCombat", x=slot, db=0x05)
    assert "chk_dmg_to" not in f.calls and "chk_dmg_from" not in f.calls
    assert f.messages == [0x0018] and f.sfx3 == [0x17]

    # Cave $00FE -> hostile even in Minish form
    f.calls.clear(); f.messages.clear()
    f.word(0x00A0, 0x00FE)
    f.call_jsl("VillageRat_InteractOrCombat", x=slot, db=0x05)
    assert "chk_dmg_from" in f.calls and "chk_dmg_to" in f.calls and "spr_move_long" in f.calls


ALL_CASES = [
    ("elder_snaps_to_frame2_no_bean_flash", case_elder_snaps_to_frame2_no_bean_flash),
    ("elder_dialogue_progression",          case_elder_dialogue_progression),
    ("bar_exit_north_and_south",            case_bar_exit_north_and_south),
    ("shed_0106_exit_opened_door_overlay",  case_shed_0106_exit_opened_door_overlay),
    ("richard_home_lady_phase2_fallback",   case_richard_home_lady_phase2_fallback),
    ("richard_home_lady_guards",            case_richard_home_lady_guards),
    ("richard_lady_talk_solicited_no_guards", case_richard_lady_talk_solicited_no_guards),
    ("village_cat_prep_all_wayward_rooms",  case_village_cat_prep_all_wayward_rooms),
    ("village_cucco_multiform_routing",     case_village_cucco_multiform_routing),
    ("village_rat_peaceful_vs_hostile",     case_village_rat_peaceful_vs_hostile),
]


def run_all(lakesnes: Path | None = None) -> list[str]:
    ls = find_lakesnes(lakesnes)
    passed: list[str] = []
    with tempfile.TemporaryDirectory(prefix="wayward-living-cpu-") as tmp:
        d = Path(tmp)
        lib = build_cpu_lib(ls, d)
        rom, labels = assemble_fixture(d / "build")
        for name, fn in ALL_CASES:
            f = WaywardFixture(lib, rom, labels)
            try:
                fn(f)
                passed.append(name)
            finally:
                f.close()
    return passed


# Pytest entrypoints
def test_wayward_living_all():
    passed = run_all()
    assert len(passed) == len(ALL_CASES)


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
