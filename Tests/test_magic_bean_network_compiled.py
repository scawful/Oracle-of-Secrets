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
import sys
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
    (folder / "Data" / "overworld").mkdir(parents=True)
    (folder / "Data/overworld/magic_bean_spots_table.asm").write_bytes(
        (ROOT / "Data/overworld/magic_bean_spots_table.asm").read_bytes()
    )
    asm = folder / "fixture.asm"
    asm.write_text(HEADER)
    image = folder / "fixture.sfc"
    image.write_bytes(b"\xff" * 0x300000)
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
        self.next_oam_slot = 0
        self.vram = [((0x5000 + i) & 0xFFFF) for i in range(0x8000)]
        self.vmain = 0x80
        self.vmadd = 0
        self.vram_latch = 0
        self.dma = {0x4300: 0x01, 0x4301: 0x18, 0x4302: 0x00, 0x4303: 0x00, 0x4304: 0x7E, 0x4305: 0x00, 0x4306: 0x00}
        self.dma_ops = []
        self.io_writes = 0
        for i in range(128):
            self.put(0x0801 + i * 4, 0xF0)
            self.put(0x0A20 + i, 0x00)
        self.put(0x7EC2FC, 0xBB)
        self.put(0x7EC2FD, 0xBC)
        self.put(0x7EC2FE, 0x7F)
        self.put(0x7EC2FF, 0x84)
        self.put(0x10, 0x09)
        self.put(0x11, 0x00)
        self.word(0xA0, 0x0000)
        self.put(0x1B, 0)
        self.put(0x8A, 0)
        self.bottles(0x02, 0x00, 0x00, 0x00)

    def write(self, address, value):
        bank = (address >> 16) & 0xFF
        off = address & 0xFFFF
        if bank in (0x00, 0x80) and 0x2100 <= off <= 0x437F:
            self.io_writes += 1
            if off == 0x2115:
                self.vmain = value
            elif off == 0x2116:
                self.vmadd = (self.vmadd & 0xFF00) | (value & 0xFF)
            elif off == 0x2117:
                self.vmadd = ((value & 0x7F) << 8) | (self.vmadd & 0xFF)
                self.vram_latch = self.vram[self.vmadd]
            elif off == 0x2118:
                self.vram[self.vmadd] = (self.vram[self.vmadd] & 0xFF00) | (value & 0xFF)
                if not (self.vmain & 0x80):
                    self.vmadd = (self.vmadd + 1) & 0x7FFF
            elif off == 0x2119:
                self.vram[self.vmadd] = (self.vram[self.vmadd] & 0x00FF) | ((value & 0xFF) << 8)
                if self.vmain & 0x80:
                    self.vmadd = (self.vmadd + 1) & 0x7FFF
            elif 0x4300 <= off <= 0x4306:
                self.dma[off] = value & 0xFF
            elif off == 0x420B and (value & 0x01):
                ctrl = self.dma[0x4300]
                breg = self.dma[0x4301]
                src = (self.dma[0x4304] << 16) | (self.dma[0x4303] << 8) | self.dma[0x4302]
                size = (self.dma[0x4306] << 8) | self.dma[0x4305]
                if size == 0:
                    size = 0x10000
                self.dma_ops.append((ctrl, breg, src, self.vmadd, size))
                if ctrl == 0x01 and breg == 0x18:
                    for i in range(0, size, 2):
                        lo = self.read(src + i)
                        hi = self.read(src + i + 1) if i + 1 < size else 0
                        self.vram[self.vmadd] = lo | (hi << 8)
                        self.vmadd = (self.vmadd + 1) & 0x7FFF
                elif ctrl == 0x81 and breg == 0x39:
                    # Hardware $2139/$213A DMA read: $2139 gives latch lo, $213A gives latch hi then reloads & vmadd++.
                    for i in range(0, size, 2):
                        word = self.vram_latch
                        super().write(src + i, word & 0xFF)
                        if i + 1 < size:
                            super().write(src + i + 1, (word >> 8) & 0xFF)
                        self.vram_latch = self.vram[self.vmadd]
                        self.vmadd = (self.vmadd + 1) & 0x7FFF
            return
        super().write(address, value)

    def vram_bytes(self, vram_word, n_bytes):
        out = bytearray()
        for i in range(n_bytes // 2):
            w = self.vram[(vram_word + i) & 0x7FFF]
            out.append(w & 0xFF)
            out.append((w >> 8) & 0xFF)
        return bytes(out)

    def run_hook(self, name, x=0, y=0, a=0, db=0x00, x16=True):
        c = self.cpu
        c.mf = True
        c.xf = not x16
        c.x = x & (0xFFFF if x16 else 0xFF)
        c.y = y & (0xFFFF if x16 else 0xFF)
        c.a = (c.a & 0xFF00) | (a & 0xFF)
        c.db = db
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k); self.put(sp - 1, 0x6F); self.put(sp - 2, 0xFF); c.sp -= 3
        for count in range(120000):
            addr = (c.k << 16) | c.pc
            if addr == ((entry & 0xFF0000) | 0x7000):
                assert c.sp == sp and not self.bad_writes, (name, c.sp, self.bad_writes)
                assert c.db == db and c.mf and c.xf == (not x16), (name, c.db, c.mf, c.xf)
                return count
            if addr in self.stubs:
                self.calls.append(self.stubs[addr])
                self.stub(self.stubs[addr])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

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
            slot = self.next_oam_slot
            self.word(0x90, 0x800 + slot * 4)
            self.word(0x92, 0xA20 + slot)
            self.next_oam_slot = (slot + 4) % 120

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


def _default_lakesnes():
    for cand in (ROOT.parent / "lakesnes", ROOT.parent.parent / "lakesnes", Path.home() / "src/hobby/lakesnes"):
        if (cand / "snes/cpu.c").is_file():
            return cand
    return ROOT.parent / "lakesnes"


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lakesnes", type=Path, default=_default_lakesnes())
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
            # Indoors Room $0104 routes subtype 2 to HouseVillager; Room $0119 (Mayor Ruul) does not
            f.put(0x1B, 1); f.put(0x8A, 0); f.word(0xA0, 0x0119)
            f.setup_sprite(0, subtype=2, x=50, y=50)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            assert f.get(0xE90) == 0 and f.get(0xD80) == 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.house_calls == 0

            f.word(0xA0, 0x0104)
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.house_calls == 1

            # Outdoors Spot 1 unplanted -> SprMiscD=1, SprAction=4
            f.oam_allocs = f.shadows = 0
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

        def test_spots_table_sync_and_bytes(f):
            sync_res = subprocess.run(
                [sys.executable, str(ROOT / "Scripts/Generate/sync_magic_bean_spots.py"), "--check"],
                capture_output=True, text=True,
            )
            assert sync_res.returncode == 0, sync_res.stdout + sync_res.stderr

            def rom_bytes(name, length):
                addr = labels[name]
                pc = ((addr >> 16) * 0x8000) + (addr & 0x7FFF)
                return rom[pc:pc + length]

            assert rom_bytes("MagicBeanSpot_Screens", 4) == bytes([0x00, 0x2D, 0x15, 0x33])
            assert rom_bytes("MagicBeanSpot_SramLow", 4) == bytes([0x9B, 0xC0, 0xC1, 0xC2])
            assert rom_bytes("MagicBeanSpot_HomeXLo", 4) == bytes([0x40, 0xA0, 0x90, 0x40])
            assert rom_bytes("MagicBeanSpot_HomeXHi", 4) == bytes([0x02, 0x0B, 0x0B, 0x07])
            assert rom_bytes("MagicBeanSpot_HomeYLo", 4) == bytes([0xD0, 0xC0, 0xC0, 0x30])
            assert rom_bytes("MagicBeanSpot_HomeYHi", 4) == bytes([0x00, 0x0A, 0x05, 0x0E])
            assert rom_bytes("MagicBean_LegXSpeed", 12) == bytes([
                0x0C, 0x18, 0x18, 0xF0, 0xE8, 0xF8, 0xF8, 0x00, 0xF8, 0x08, 0x08, 0x10
            ])
            assert rom_bytes("MagicBean_LegYSpeed", 12) == bytes([
                0xFC, 0x0E, 0x0E, 0xF0, 0xFC, 0xFC, 0xE8, 0xE8, 0xEC, 0xE8, 0xE8, 0xE8
            ])
            assert rom_bytes("MagicBean_LegTimers", 12) == bytes([
                0x30, 0x80, 0x80, 0x30, 0x70, 0x50, 0x40, 0x80, 0x40, 0x60, 0x80, 0x60
            ])
            assert rom_bytes("MagicBean_LegDragDir", 12) == bytes([
                0x03, 0x03, 0x03, 0x02, 0x02, 0x02, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00
            ])

        def test_non_ranch_flower_and_bean_oam_vram(f):
            def payload(name):
                addr = labels[name]
                pc = ((addr >> 16) * 0x8000) + (addr & 0x7FFF)
                return rom[pc:pc + 128]

            # 1) Ranch OW ($7EC2FE=$4A) keeps native $A8/$A4/$A6 + $3B/$7B with zero VRAM DMA
            f.put(0x1B, 0); f.put(0x8A, 0x00); f.put(0x7EC2FE, 0x4A)
            f.put(f.SPOTS[0], 0x7F)
            f.setup_sprite(0, x=576, y=208)
            f.cam = (576 - 100, 208 - 100)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            f.next_oam_slot = 0
            f.shadows = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.shadows == 1
            assert [f.get(0x0802 + i * 4) for i in range(4)] == [0xA4, 0xA4, 0xA8, 0xA8]
            assert [f.get(0x0803 + i * 4) for i in range(4)] == [0x7B, 0x3B, 0x7B, 0x3B]
            f.run_hook("MagicBean_FrameEndScan_Long")
            f.run_hook("MagicBean_NmiUpload_Long")
            assert not f.dma_ops

            # 2) Non-Ranch OW ($8A=$2D, sheets=[$BB,$BC,$7F,$84]):
            # occupy blocks in sheet 2 (row 4 col 0=$80, row 5 col 7=$AE) and sheet 3 row 6 (KoRL $CE)
            f.put(0x8A, 0x2D)
            f.put(0x7EC2FC, 0xBB); f.put(0x7EC2FD, 0xBC); f.put(0x7EC2FE, 0x7F); f.put(0x7EC2FF, 0x84)
            f.put(f.SPOTS[1], 0x7F)
            f.setup_sprite(0, x=2976, y=2752)
            f.cam = (2976 - 100, 2752 - 100)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            # Also add a Released Bean sprite in slot 1 (action=1, frame=1, x=2996, y=2752)
            f.setup_sprite(1, action=1, x=2996, y=2752)
            f.put(0xD90 + 1, 1)

            # Frame 1 draw before residency: OAM hidden (Y=$F0) and shadows skipped
            f.next_oam_slot = 0
            f.shadows = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            f.run_sub("Sprite_BeanVendor_Long", x=1)
            assert f.shadows == 0
            assert all(f.get(0x0801 + i * 4) == 0xF0 for i in range(5))
            # Place enemy OAM entries in high OAM slots (16, 17, 18) using $80, $AE, $CE
            for idx, (ey, echr) in enumerate([(80, 0x80), (90, 0xAE), (100, 0xCE)], start=16):
                f.put(0x0800 + idx * 4, 40)
                f.put(0x0801 + idx * 4, ey)
                f.put(0x0802 + idx * 4, echr)
                f.put(0x0803 + idx * 4, 0x39)
                f.put(0x0A20 + idx, 0x02)

            f.run_hook("MagicBean_FrameEndScan_Long")
            assert f.get(labels["MagicBean_PendingUpload"]) == 0x07
            chrs = [f.get(labels["MagicBean_BlockChr"] + k) for k in range(3)]
            assert len(set(chrs)) == 3
            assert all(c not in (0x80, 0xAE, 0xCE) for c in chrs), chrs

            # Upload takes 1 block per NMI (3 NMIs total) and resets DMA0 defaults afterwards
            expected_gfx = [
                payload("MagicBean_FlowerTopGfx"),
                payload("MagicBean_FlowerBotGfx"),
                payload("MagicBean_BeanGfx"),
            ]
            for step, exp_res in enumerate((0x01, 0x03, 0x07)):
                f.run_hook("MagicBean_NmiUpload_Long")
                assert f.get(labels["MagicBean_ResidentMask"]) == exp_res
                assert f.dma[0x4300] == 0x01 and f.dma[0x4301] == 0x18 and f.dma[0x4304] == 0x7E
                assert f.vmain == 0x80
                vtop = 0x5000 + (chrs[step] << 4)
                assert f.vram_bytes(vtop, 64) == expected_gfx[step][:64]
                assert f.vram_bytes(vtop + 0x0100, 64) == expected_gfx[step][64:]

            # Next draw: Flower + Bean both emit SP1 ($33/$73) OAM and shadows!
            f.next_oam_slot = 0
            f.shadows = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            f.run_sub("Sprite_BeanVendor_Long", x=1)
            assert f.shadows == 2
            assert [f.get(0x0802 + i * 4) for i in range(4)] == [chrs[0], chrs[0], chrs[1], chrs[1]]
            assert [f.get(0x0803 + i * 4) for i in range(4)] == [0x73, 0x33, 0x73, 0x33]
            assert [f.get(0x0A20 + i) & 0x02 for i in range(4)] == [2, 2, 2, 2]
            assert f.get(0x0802 + 4 * 4) == chrs[2] and f.get(0x0803 + 4 * 4) == 0x33

        def test_non_ranch_collision_restore_and_reallocate(f):
            # Setup resident non-Ranch Flower + active Horse & KoRL markers
            f.put(0x8A, 0x15)
            f.put(0x7EC2FC, 0xBB); f.put(0x7EC2FD, 0xBC); f.put(0x7EC2FE, 0x7F); f.put(0x7EC2FF, 0x84)
            f.word(0x7E1EDE, 0x4852); f.put(0x7F5402, 0xA2)  # Horse active (row 0 reserved)
            f.word(0x7FF3E2, 0x4B4C); f.put(0x7FF3EC, 0xA2)  # KoRL active (row 6 reserved)
            f.put(f.SPOTS[2], 0x7F)
            f.setup_sprite(0, x=2960, y=1472)
            f.cam = (2960 - 100, 1472 - 100)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)

            for _ in range(3):
                f.next_oam_slot = 0
                f.run_sub("Sprite_BeanVendor_Long", x=0)
                f.run_hook("MagicBean_FrameEndScan_Long")
                f.run_hook("MagicBean_NmiUpload_Long")
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x03
            c0 = f.get(labels["MagicBean_BlockChr"])
            c1 = f.get(labels["MagicBean_BlockChr"] + 1)
            assert (c0 >> 5) not in (0, 6) and (c1 >> 5) not in (0, 6)

            # Frame N: draw Flower onscreen, then an enemy spawns odd-aligned colliding with c0
            f.next_oam_slot = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            assert f.get(0x0801) != 0xF0
            # Enemy odd 16x16 at ((c0 & $E0) | ((c0 - 2) & $0E)) + $01 hits c0 via odd-col expansion
            # or simpler: exact chr c0 on enemy OAM slot 20
            f.put(0x0800 + 20 * 4, 60)
            f.put(0x0801 + 20 * 4, 60)
            f.put(0x0802 + 20 * 4, c0)
            f.put(0x0803 + 20 * 4, 0x35)
            f.put(0x0A20 + 20, 0x02)

            f.run_hook("MagicBean_FrameEndScan_Long")
            # Immediate OAM hide before NMI & restore queued
            assert all(f.get(0x0801 + i * 4) == 0xF0 for i in range(4))
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x02
            assert f.get(labels["MagicBean_PendingRestore"]) == 0x01

            # NMI restores exact original sentinel words in c0's VRAM block (2-byte prefetch dropped)
            v0 = 0x5000 + (c0 << 4)
            f.run_hook("MagicBean_NmiUpload_Long")
            assert f.get(labels["MagicBean_PendingRestore"]) == 0x00
            exp_top = b"".join(bytes([(0x5000 + v0 + i) & 0xFF, ((0x5000 + v0 + i) >> 8) & 0xFF]) for i in range(32))
            exp_bot = b"".join(bytes([(0x5000 + v0 + 0x100 + i) & 0xFF, ((0x5000 + v0 + 0x100 + i) >> 8) & 0xFF]) for i in range(32))
            assert f.vram_bytes(v0, 64) == exp_top
            assert f.vram_bytes(v0 + 0x0100, 64) == exp_bot

            # Next frame re-allocates FlowerTop cleanly to a non-colliding block (avoiding c0, c1, Epona, KoRL)
            f.next_oam_slot = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            f.run_hook("MagicBean_FrameEndScan_Long")
            f.run_hook("MagicBean_NmiUpload_Long")
            c0_new = f.get(labels["MagicBean_BlockChr"])
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x03
            assert c0_new not in (c0, c1) and (c0_new >> 5) not in (0, 6)

        def test_sheet_reload_and_safe_overlay_preserves_state(f):
            f.put(0x8A, 0x2D)
            f.put(f.SPOTS[1], 0x7F)
            f.setup_sprite(0, x=2976, y=2752)
            f.cam = (2976 - 100, 2752 - 100)
            f.run_sub("Sprite_BeanVendor_Prep", x=0)
            for _ in range(3):
                f.next_oam_slot = 0
                f.run_sub("Sprite_BeanVendor_Long", x=0)
                f.run_hook("MagicBean_FrameEndScan_Long")
                f.run_hook("MagicBean_NmiUpload_Long")
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x03

            # Safe $0E Pause overlay ($10=$0E, $11=$01) freezes resident VRAM without decaying or restoring
            f.put(0x10, 0x0E); f.put(0x11, 0x01)
            f.run_hook("MagicBean_FrameEndScan_Long")
            f.run_hook("MagicBean_NmiUpload_Long")
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x03
            assert f.get(labels["MagicBean_PendingRestore"]) == 0x00

            # Return to play and mutate slot sheet natively without calling OnSheetReload:
            # FrameEndScan catches sheet mismatch and drops block without clobbering new VRAM
            f.put(0x10, 0x09); f.put(0x11, 0x00)
            slot0 = f.get(labels["MagicBean_BlockSlot"])
            f.put(0x7EC2FC + slot0, 0x99)
            f.next_oam_slot = 0
            f.run_sub("Sprite_BeanVendor_Long", x=0)
            f.run_hook("MagicBean_FrameEndScan_Long")
            assert f.get(labels["MagicBean_PendingRestore"]) == 0x00

            # Explicit OnSheetReload preserves A/X/Y/P and resets MagicBean state
            f.run_hook("MagicBean_NmiUpload_Long")
            f.run_hook("MagicBean_OnSheetReload_Long", x=0x1234, y=0x5678, a=0xAB, x16=True)
            assert (f.cpu.a & 0xFF) == 0xAB and f.cpu.x == 0x1234 and f.cpu.y == 0x5678
            assert f.get(labels["MagicBean_ResidentMask"]) == 0x00
            assert f.get(labels["MagicBean_PendingUpload"]) == 0x00
            assert f.get(labels["MagicBean_PendingRestore"]) == 0x00

        case("vendor_sale_and_guards", test_vendor_sale_and_guards)
        case("vendor_reject_poor_and_elder_untouched", test_vendor_reject_poor_and_elder_untouched)
        case("prep_states_and_offscreen_draw", test_prep_states_and_offscreen_draw)
        case("plant_water_bee_daily_and_isolation", test_plant_water_bee_daily_and_isolation)
        case("all_four_3leg_flights_and_reset", test_all_four_3leg_flights_and_reset)
        case("spots_table_sync_and_bytes", test_spots_table_sync_and_bytes)
        case("non_ranch_flower_and_bean_oam_vram", test_non_ranch_flower_and_bean_oam_vram)
        case("non_ranch_collision_restore_and_reallocate", test_non_ranch_collision_restore_and_reallocate)
        case("sheet_reload_and_safe_overlay_preserves_state", test_sheet_reload_and_safe_overlay_preserves_state)

    res = {"status": "PASS", "cases": cases, "count": len(cases)}
    out = json.dumps(res, indent=2)
    if a.output:
        a.output.write_text(out + "\n")
    print(out)


if __name__ == "__main__":
    main()
