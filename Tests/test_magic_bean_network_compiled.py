#!/usr/bin/env python3
"""Compile Sprites/NPCs/bean_vendor.asm and run unit tests on LakeSnes 65816.

Tests the 4-spot Magic Bean network, repeatable 100-rupee vendor sales,
Good Bee vs Ordinary Bee filtering, Song of Storms watering, daily growth
isolation ($7EF39B + $7EF3C0..$7EF3C2), 3-leg flower flight physics,
reset-to-home + !SideQuest2_BeanstalkGrown, and offscreen OAM draw guard.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu, Fixture

ROOT = Path(__file__).resolve().parents[1]

STUB_ADDRS = {
    0x05E219: "show_uncond",
    0x05E220: "show_solic",
    0x06DC54: "draw_shadow",
    0x318000: "check_active",
    0x30A000: "house_villager",
    0x069400: "cant_pass",
    0x06AA00: "check_lifted",
    0x06AB00: "thrown_interact",
    0x0683EA: "setup_hitbox",
    0x0683EE: "setup_hitbox_alt",
    0x0683E6: "overlap",
    0x0683F2: "link_hitbox",
    0x31820D: "drag_player",
    0x07F42F: "camera_doors",
    0x0791B9: "cancel_dash",
    0x068400: "sprite_move",
    0x1DF65D: "spawn_dyn",
    0x0DFA58: "rebuild_hud",
    0x06E416: "prep_oam",
    0x068500: "alloc_oam",
}

HEADER = """lorom
!SideQuest2_BeanstalkGrown = $40
SideQuestProg2 = $7EF3D8
Sprite_BeanVendor = $07
LinkSomaria = $02F5
POSZ = $24
POSZH = $25
SprY = $0D00
SprX = $0D10
SprYH = $0D20
SprXH = $0D30
SprYSpeed = $0D40
SprXSpeed = $0D50
SprYRound = $0D60
SprXRound = $0D70
SprAction = $0D80
SprFrame = $0D90
SprMiscA = $0DA0
SprMiscB = $0DB0
SprTimerB = $0E00
SprTimerC = $0E10
SprMiscC = $0DE0
SprTimerA = $0DF0
SprState = $0DD0
SprType = $0E20
SprSubtype = $0E30
SprDefl = $0E60
SprMiscD = $0E90
SprMiscE = $0EB0
SprMiscF = $0EC0
SprMiscG = $0ED0
SprHeight = $0F70
SprCachedX = $0FD8
SprCachedY = $0FDA

Sprite_ShowMessageUnconditional = $05E219
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E220
Sprite_DrawShadow = $06DC54
Sprite_CheckActive = $318000
HouseVillager_Main = $30A000
Sprite_PlayerCantPassThrough = $069400
Sprite_CheckIfLifted = $06AA00
ThrownSprite_TileAndSpriteInteraction_long = $06AB00
Sprite_SetupHitBox = $0683EA
Sprite_SetupHitBox_Alt = $0683EE
CheckIfHitBoxesOverlap = $0683E6
Link_SetupHitBox = $0683F2
DragPlayer = $31820D
HandleIndoorCameraAndDoors = $07F42F
Link_CancelDash = $0791B9
Sprite_Move = $068400
Sprite_SpawnDynamically = $1DF65D
RebuildHUD_long = $0DFA58
Sprite_PrepOamCoord = $06E416
Sprite_OAM_AllocateDeferToPlayer = $068500

macro Set_Sprite_Properties(SprPrep, SprMain)
endmacro

macro GotoAction(action)
  LDA.b #<action> : STA.w SprAction, X
endmacro

macro SetFrame(frame)
  LDA.b #<frame> : STA.w SprFrame, X
endmacro

macro SpriteJumpTable(...)
  LDA.w SprAction, X
  JSL JumpTableLocal
  !a #= 0
  while !a < sizeof(...)
    dw <...[!a]>
    !a #= !a+1
  endwhile
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

macro ShowUnconditionalMessage(message_id)
  LDY.b #(<message_id>)>>8
  LDA.b #<message_id>
  JSL Sprite_ShowMessageUnconditional
endmacro

org $008781
JumpTableLocal:
  ASL A : TAY
  INY
  LDA.b $01, S : STA.b $00
  LDA.b $02, S : STA.b $01
  LDA.b $03, S : STA.b $02
  LDA.b [$00], Y : PHA
  INY
  LDA.b [$00], Y : STA.b $03
  PLA : STA.b $00
  LDA.b $03 : STA.b $01
  PLA : PLA : PLA
  LDA.b $02 : PHA
  REP #$20
  LDA.b $00 : DEC A : PHA
  SEP #$20
  RTL

org $309000
incsrc "bean_vendor.asm"
Sprite_VillageElder_Main:
  INC.w $0EF0
  RTS
"""


def assemble(folder: Path):
    folder.mkdir()
    (folder / "bean_vendor.asm").write_bytes((ROOT / "Sprites/NPCs/bean_vendor.asm").read_bytes())
    asm = folder / "fixture.asm"
    asm.write_text(HEADER)
    image = folder / "fixture.sfc"
    image.write_bytes(b"\xff" * 0x200000)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(image)],
        capture_output=True, text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$", image.with_suffix(".sym").read_text())
    }
    return image.read_bytes(), labels


class BeanFixture(Fixture):
    SPOTS = {0: 0x7EF39B, 1: 0x7EF3C0, 2: 0x7EF3C1, 3: 0x7EF3C2}

    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.stubs = dict(STUB_ADDRS)
        self.cpu.db = 0x30
        self.messages = []
        self.hud_rebuilds = 0
        self.shadows = 0
        self.oam_allocs = 0
        self.house_calls = 0
        self.talk_solic = False
        self.box_a = None
        self.box_b = None
        self.cam = (0, 0)
        self.drag_dirs = []
        self.put(0x1B, 0)
        self.put(0x8A, 0)
        self.bottles(0x02, 0x00, 0x00, 0x00)

    def rupees(self, n=None):
        if n is not None:
            self.word(0x7EF360, n)
        return self.get(0x7EF360) | (self.get(0x7EF361) << 8)

    def bottles(self, *vals):
        if vals:
            for i, v in enumerate(vals):
                self.put(0x7EF35C + i, v)
        return [self.get(0x7EF35C + i) for i in range(4)]

    def link_pos(self, x=None, y=None):
        if x is not None and y is not None:
            self.word(0x22, x)
            self.word(0x20, y)
        return (self.get(0x22) | (self.get(0x23) << 8), self.get(0x20) | (self.get(0x21) << 8))

    def spr_pos(self, slot, x=None, y=None):
        if x is not None and y is not None:
            self.put(0xD10 + slot, x & 0xFF)
            self.put(0xD30 + slot, (x >> 8) & 0xFF)
            self.put(0xD00 + slot, y & 0xFF)
            self.put(0xD20 + slot, (y >> 8) & 0xFF)
        return (self.get(0xD10 + slot) | (self.get(0xD30 + slot) << 8),
                self.get(0xD00 + slot) | (self.get(0xD20 + slot) << 8))

    def setup_sprite(self, slot, sid=0x07, state=9, action=0, subtype=0, x=0, y=0):
        self.put(0xDD0 + slot, state)
        self.put(0xE20 + slot, sid)
        self.put(0xD80 + slot, action)
        self.put(0xE30 + slot, subtype)
        self.put(0xE10 + slot, 0)
        self.put(0xDE0 + slot, 0)
        self.put(0xE90 + slot, 0)
        self.put(0xEB0 + slot, 0)
        self.spr_pos(slot, x, y)

    def stub(self, name):
        c = self.cpu
        slot = c.x & 0xFF
        if name == "show_uncond":
            self.messages.append((c.y & 0xFF) << 8 | (c.a & 0xFF))
        elif name == "show_solic":
            if self.talk_solic:
                self.messages.append((c.y & 0xFF) << 8 | (c.a & 0xFF))
            c.c = self.talk_solic
        elif name == "draw_shadow":
            self.shadows += 1
        elif name == "check_active":
            c.c = self.get(0xDD0 + slot) == 9
        elif name == "house_villager":
            self.house_calls += 1
        elif name in ("cant_pass", "check_lifted", "thrown_interact", "camera_doors", "cancel_dash"):
            pass
        elif name == "setup_hitbox":
            x, y = self.spr_pos(slot)
            self.box_a = (x, y, 16, 16)
        elif name == "setup_hitbox_alt":
            x, y = self.spr_pos(slot)
            self.box_b = (x, y, 16, 16)
        elif name == "link_hitbox":
            lx, ly = self.link_pos()
            self.box_b = (lx, ly, 16, 16)
        elif name == "overlap":
            ax, ay, aw, ah = self.box_a
            bx, by, bw, bh = self.box_b
            c.c = ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah
        elif name == "drag_player":
            self.drag_dirs.append(c.y & 0xFF)
            lx, ly = self.link_pos()
            vx = self.get(0xD50 + slot); vx = vx - 256 if vx >= 128 else vx
            vy = self.get(0xD40 + slot); vy = vy - 256 if vy >= 128 else vy
            xr = self.get(0xD70 + slot) + vx * 16
            yr = self.get(0xD60 + slot) + vy * 16
            dx = xr >> 8 if xr >= 0 else -((-xr + 255) >> 8)
            dy = yr >> 8 if yr >= 0 else -((-yr + 255) >> 8)
            self.link_pos(lx + dx, ly + dy)
        elif name == "sprite_move":
            vx = self.get(0xD50 + slot); vx = vx - 256 if vx >= 128 else vx
            vy = self.get(0xD40 + slot); vy = vy - 256 if vy >= 128 else vy
            sx, sy = self.spr_pos(slot)
            xr = self.get(0xD70 + slot) + vx * 16
            yr = self.get(0xD60 + slot) + vy * 16
            dx = xr >> 8 if xr >= 0 else -((-xr + 255) >> 8)
            dy = yr >> 8 if yr >= 0 else -((-yr + 255) >> 8)
            self.put(0xD70 + slot, xr & 0xFF)
            self.put(0xD60 + slot, yr & 0xFF)
            self.spr_pos(slot, sx + dx, sy + dy)
        elif name == "spawn_dyn":
            for cand in range(15, -1, -1):
                if self.get(0xDD0 + cand) == 0:
                    self.put(0xDD0 + cand, 9)
                    self.put(0xE20 + cand, c.a & 0xFF)
                    c.y = cand
                    c.n = False
                    return
            c.y = 0xFF
            c.n = True
        elif name == "rebuild_hud":
            self.hud_rebuilds += 1
        elif name == "prep_oam":
            sx, sy = self.spr_pos(slot)
            rx = (sx - self.cam[0]) & 0xFFFF
            ry = (sy - self.cam[1]) & 0xFFFF
            self.word(0x00, rx)
            self.word(0x02, ry)
        elif name == "alloc_oam":
            self.oam_allocs += 1
            self.word(0x90, 0x800)
            self.word(0x92, 0xA00)

    def run_sub(self, name, long_call=True, x=0, y=0, a=0, db=0x30):
        c = self.cpu
        c.mf = c.xf = True
        c.x, c.y = x & 0xFF, y & 0xFF
        c.a = (c.a & 0xFF00) | (a & 0xFF)
        c.db = db
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        if long_call:
            self.put(sp, c.k); self.put(sp - 1, 0x6F); self.put(sp - 2, 0xFF); c.sp -= 3
        else:
            self.put(sp, 0x6F); self.put(sp - 1, 0xFF); c.sp -= 2
        for count in range(40000):
            addr = (c.k << 16) | c.pc
            if addr == ((entry & 0xFF0000) | 0x7000):
                assert c.sp == sp and not self.bad_writes, (name, c.sp, self.bad_writes)
                assert c.db == db and c.mf and c.xf, (name, c.db, c.mf, c.xf)
                return count
            if addr in self.stubs:
                self.calls.append(self.stubs[addr])
                self.stub(self.stubs[addr])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lakesnes", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    a = ap.parse_args()
    cases = []

    with tempfile.TemporaryDirectory(prefix="magic-bean-cpu-") as tmp:
        d = Path(tmp)
        lib_path = d / "cpu.dylib"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2", str(a.lakesnes / "snes/cpu.c"),
             str(a.lakesnes / "snes/statehandler.c"), "-o", str(lib_path)],
            check=True,
        )
        lib = C.CDLL(str(lib_path))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        rom, labels = assemble(d / "build")

        def case(name, fn):
            f = BeanFixture(lib, rom, labels)
            try:
                fn(f)
                cases.append(name)
            finally:
                f.close()

        def test_vendor_sale_and_guards(f):
            f.setup_sprite(0, action=0)
            f.rupees(100)
            f.bottles(0x03, 0x02, 0x00, 0x00)
            f.talk_solic = True
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages == [0x142] and f.get(0xD80) == 2, (f.messages, f.get(0xD80), f.calls)

            # Full bottles refusal preserves rupees
            f.bottles(0x03, 0x04, 0x05, 0x06)
            f.put(0x1CE8, 0)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x033 and f.rupees() == 100 and f.get(0xD80) == 0

            # Successful 100-rupee purchase puts $09 in first empty bottle
            f.bottles(0x03, 0x02, 0x00, 0x00)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x142
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x034 and f.rupees() == 0 and f.bottles() == [0x03, 0x09, 0, 0]

            # Holding $09 blocks buying a duplicate
            f.rupees(200)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x144 and f.get(0xD80) == 0 and f.rupees() == 200

            # After planting ($09 -> empty) on Spot 0, vendor sells again for Spot 1
            f.bottles(0x03, 0x02, 0x00, 0x00)
            f.put(f.SPOTS[0], 0x01)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x142 and f.get(0xD80) == 2

            # Once all 4 spots planted, vendor says $144
            for addr in f.SPOTS.values():
                f.put(addr, 0x01)
            f.put(0xD80, 0)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x144 and f.get(0xD80) == 0

        def test_prep_states_and_offscreen_draw(f):
            # Indoors ignores bean tables (HouseVillager / Vendor unaffected)
            f.put(0x1B, 1); f.put(0x8A, 0)
            f.setup_sprite(0, subtype=2, x=50, y=50)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            assert f.get(0xE90) == 0 and f.get(0xD80) == 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.house_calls == 1

            # Outdoors Spot 1 unplanted -> SprMiscD=1, SprAction=4
            f.put(0x1B, 0); f.put(0x8A, 0x2D); f.put(f.SPOTS[1], 0x00)
            f.setup_sprite(0, x=2976, y=2752)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            assert f.get(0xE90) == 1 and f.get(0xD80) == 4
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.oam_allocs == 0 and f.shadows == 0  # invisible until planted

            # Growing sprout -> SprAction=5, SprFrame=5, visible onscreen
            f.put(f.SPOTS[1], 0x07)
            f.cam = (2976 - 100, 2752 - 100)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            assert f.get(0xE90) == 0 and f.get(0xD80) == 5 and f.get(0xD90) == 5
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.oam_allocs == 1 and f.shadows == 1

            # Grown ($3F and $7F) -> Frame 4, SideQuest2_BeanstalkGrown set, offscreen draw skipped
            f.put(f.SPOTS[1], 0x7F)
            f.put(0x7EF3D8, 0x00)
            f.cam = (0, 0)
            f.oam_allocs = f.shadows = 0
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            assert f.get(0xD80) == 5 and f.get(0xD90) == 4 and (f.get(0x7EF3D8) & 0x40) == 0x40
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.oam_allocs == 0 and f.shadows == 0  # offscreen guard prevents wraparound!

        def test_plant_water_bee_daily_and_isolation(f):
            # Non-spot release keeps bottle and shows $030
            f.put(0x1B, 0); f.put(0x8A, 0x10)
            f.bottles(0x09, 0, 0, 0)
            f.link_pos(100, 100)
            f.run_sub("ReleaseMagicBean", x=0)
            assert f.bottles() == [0x09, 0, 0, 0] and f.messages == [0x030]

            # Spot 2 ($15): plant -> water -> reject ordinary bee -> accept Good Bee -> Days 1..3
            f.put(0x8A, 0x15)
            f.setup_sprite(0, action=4, x=2960, y=1472)
            f.put(0xE90 + 0, 1)
            f.link_pos(2960, 1472)
            f.run_sub("ReleaseMagicBean", x=0)
            assert f.bottles() == [0x02, 0, 0, 0] and f.hud_rebuilds == 1
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.get(f.SPOTS[2]) == 0x01 and f.get(0xD80 + 0) == 5 and f.get(0xE90 + 0) == 0
            assert f.get(f.SPOTS[0]) == 0x00 and f.get(f.SPOTS[1]) == 0x00 and f.get(f.SPOTS[3]) == 0x00

            # Song of Storms waters Spot 2 only
            f.run_sub("MagicBean_WaterCurrentSpot_Long")
            assert f.get(f.SPOTS[2]) == 0x05

            # Ordinary Bee ($B2, action=1, $0EB0=0) & Windmill ($B2, action=0) must NOT pollinate
            f.setup_sprite(2, sid=0xB2, action=0, x=2960, y=1472)
            f.put(0xEB0 + 2, 0)
            f.setup_sprite(3, sid=0xB2, action=1, x=2960, y=1472)
            f.put(0xEB0 + 3, 0)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert (f.get(f.SPOTS[2]) & 0x02) == 0

            # Honeycomb/Good Bee in slot 4 ($B2, action=1, $0EB0=1) DOES pollinate!
            f.setup_sprite(4, sid=0xB2, action=1, x=2960, y=1472)
            f.put(0xEB0 + 4, 1)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.get(f.SPOTS[2]) == 0x07

            # Three daily advances reach $3F only for planted Spot 2 (Spots 0,1,3 untouched)
            for exp in (0x0F, 0x1F, 0x3F):
                f.run_sub("MagicBean_AdvanceDailyGrowth_Long")
                assert f.get(f.SPOTS[2]) == exp
                assert f.get(f.SPOTS[0]) == 0 and f.get(f.SPOTS[1]) == 0 and f.get(f.SPOTS[3]) == 0

        def test_all_four_3leg_flights_and_reset(f):
            expected = {
                0: (0x00, (576, 208), (996, 420), [3, 3, 3]),
                1: (0x2D, (2976, 2752), (2720, 2656), [2, 2, 2]),
                2: (0x15, (2960, 1472), (2896, 1104), [0, 0, 0]),
                3: (0x33, (1856, 3632), (2064, 3152), [0, 0, 0]),
            }
            for idx, (scr, home, target, dirs) in expected.items():
                f.put(0x1B, 0); f.put(0x8A, scr)
                for s in f.SPOTS.values():
                    f.put(s, 0)
                f.put(f.SPOTS[idx], 0x3F)
                f.put(0x7EF3D8, 0)
                f.drag_dirs.clear()
                f.setup_sprite(0, x=home[0], y=home[1])
                f.run_sub("Sprite_BeanVendor_Prep", x=0)
                f.link_pos(*home)
                f.run_sub("Sprite_BeanVendor_Long", x=0)  # Mount flower -> action 6
                assert f.get(0xD80) == 6
                for _ in range(500):
                    if f.get(0xE10) > 0:
                        f.put(0xE10, f.get(0xE10) - 1)  # mirror bank_06 DEC $0E10,X
                    f.run_sub("Sprite_BeanVendor_Long", x=0)
                    if f.get(0xD80) == 5:
                        break
                assert f.get(0xD80) == 5, (idx, f.get(0xD80))
                assert f.link_pos() == target, (idx, f.link_pos(), target)
                assert f.spr_pos(0) == home, (idx, f.spr_pos(0), home)
                assert f.get(f.SPOTS[idx]) == 0x7F and (f.get(0x7EF3D8) & 0x40) == 0x40
                assert set(f.drag_dirs) == set(dirs)
                assert f.get(0xE10) == 0x20 and f.get(0xD90) == 4  # remount cooldown + flower frame

        def test_vendor_reject_poor_and_elder_untouched(f):
            # Less than 100 rupees -> $144, rupees untouched, action=0
            f.setup_sprite(0, action=0)
            f.rupees(99)
            f.bottles(0x02, 0, 0, 0)
            f.talk_solic = True
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.get(0xD80) == 2
            f.put(0x1CE8, 0)
            f.run_sub("Sprite_BeanVendor_Long", x=0)  # Action 2 -> 3 (PlayerSaidNo)
            assert f.get(0xD80) == 3
            f.run_sub("Sprite_BeanVendor_Long", x=0)  # Action 3 -> $144 & Action 0
            assert f.messages[-1] == 0x144 and f.rupees() == 99 and f.get(0xD80) == 0

            # Choosing "No" ($1CE8=1) with 200 rupees -> $144, rupees untouched
            f.rupees(200)
            f.put(0xD80, 2)
            f.put(0x1CE8, 1)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.get(0xD80) == 3
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.messages[-1] == 0x144 and f.rupees() == 200 and f.get(0xD80) == 0

            # VillageElder (SprSubtype=1) preserves subtype across Prep & routes to VillageElder_Main
            f.setup_sprite(1, subtype=1, x=100, y=100)
            f.run_sub("Sprite_BeanVendor_Prep", x=1)
            assert f.get(0xE30 + 1) == 1
            f.run_sub("Sprite_BeanVendor_Long", x=1)
            assert f.get(0xEF0) == 1

        case("vendor_sale_and_guards", test_vendor_sale_and_guards)
        case("vendor_reject_poor_and_elder_untouched", test_vendor_reject_poor_and_elder_untouched)
        case("prep_states_and_offscreen_draw", test_prep_states_and_offscreen_draw)
        case("plant_water_bee_daily_and_isolation", test_plant_water_bee_daily_and_isolation)
        case("all_four_3leg_flights_and_reset", test_all_four_3leg_flights_and_reset)

    res = {"status": "PASS", "cases": cases, "count": len(cases)}
    out = json.dumps(res, indent=2)
    if a.output:
        a.output.write_text(out + "\n")
    print(out)


if __name__ == "__main__":
    main()
