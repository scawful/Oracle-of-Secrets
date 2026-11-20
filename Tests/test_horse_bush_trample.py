#!/usr/bin/env python3
"""Compiled 65816 unit tests for Epona Bush Trampling (HorseForm_TrampleBushes).

Assembles the real Bank $53 Horse ASM (Masks/horse_form.asm,
Masks/horse_mounted_helpers.asm, Masks/horse_ground_clearance.asm,
Masks/horse_sparse_runtime.asm) into a synthetic LoROM image and executes
compiled 65816 instructions on the LakeSnes CPU core.

Runnable both via `pytest Tests/test_horse_bush_trample.py` and directly via
`python3 Tests/test_horse_bush_trample.py`.
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

# Vanilla & stubbed call targets
STUB_GET_TILE_ATTR = 0x00882E
STUB_HANDLE_OW_TILE_ACTION = 0x1BBD7A
STUB_PAL_ARMOR = 0x058000
STUB_LOAD_DAYNIGHT = 0x058004
STUB_SFX_PAN = 0x0DBB67
STUB_RESET_LINK_GFX = 0x058008
STUB_SPRITE_SPAWN = 0x1DF65D
STUB_DASH_TREMOR = 0x0993F3
STUB_KID_START = 0x05800C
STUB_HORSE_GAME_TICK = 0x058010
STUB_SAVE_ANCHOR = 0x058014
STUB_MAINTAIN_NPC = 0x058018
STUB_OFF_RESTORE = 0x05801C
STUB_OFF_RANCH_NPC = 0x058020
STUB_FRAME_END_SCAN = 0x058024
STUB_SUPPRESS_BTNS = 0x53E800

HORSE_MARKER_ADDR = 0x7E1EDE
HORSE_STATE_ADDR = 0x7E1EE0
HORSE_JUMP_TIMER_ADDR = 0x7E1EE1
HORSE_PUSH_TIMER_ADDR = 0x7E1EE5
HORSE_GAME_STATE_ADDR = 0x7F5410


def find_lakesnes() -> Path:
    env = os.environ.get("LAKESNES_DIR", "").strip()
    candidates = [Path(env)] if env else []
    candidates += [
        ROOT.parent / "lakesnes",
        ROOT.parent / "lakesnes" / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ]
    for path in candidates:
        if path and (path / "snes" / "cpu.c").is_file():
            return path
    raise RuntimeError("Could not locate lakesnes/snes/cpu.c")


def _extract_horse_table_header() -> str:
    lines = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text().splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("assert "))


def assemble_horse_rom(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Masks").mkdir(exist_ok=True)
    (folder / "Masks/gfx").mkdir(exist_ok=True)
    for rel in [
        "Masks/horse_ground_clearance.asm",
        "Masks/horse_mounted_helpers.asm",
        "Masks/horse_sparse_runtime.asm",
        "Masks/horse_form.asm",
    ]:
        txt = (ROOT / rel).read_text()
        txt = re.sub(r"(?m)^(\s*)assert\s+read\d.*$", r"\1; [stripped rom preimage assert]", txt)
        (folder / rel).write_text(txt)
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
        """lorom
macro m8()
  SEP #$20
endmacro
macro a16()
  REP #$20
endmacro

!CurrentMask = $02B2
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 1
HorseCharge_Tick_Long = $058024
!SideQuest2_RanchGirl = $01
InCutScene = $7E02E4
SideQuestProg2 = $7EF3D8
LoadDayNightPaletteEffect = $058004
Palette_ArmorAndGloves = $058000
ResetToLinkGraphics = $058008
Sprite_SpawnDynamically = $1DF65D
HorseGame_State = $7F5410
HorseGame_Tick = $058010
HorseGame_KidStartCheck = $05800C
HorseForm_SuppressMountedButtons = $53E800
Horse_AnchorArea = $7E1EFE
Horse_OffState = $7F5400
Horse_OffClear = $7F5402
HorseForm_SaveOutdoorAnchor_Long = $058014
HorseForm_MaintainParkedNpc_Long = $058018
Horse_OffRestore = $05801C
Horse_OffRanchNpc = $058020
Horse_FrameEndScan = $058024

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
Horse_JumpStep         = $7E1EE2
Horse_JumpDir          = $7E1EE3
Horse_JumpZ            = $7E1EE4
Horse_PushTimer        = $7E1EE5
Horse_AnimTimer        = $7E1EE6
Horse_Frame            = $7E1EE7
Horse_UploadedFrame    = $7E1EE8
Horse_NpcActive        = $7E1EE9
Horse_NpcFrame         = $7E1EEA
Horse_NpcUploadedFrame = $7E1EEB
Horse_PalLoaded        = $7E1EEC
Horse_DismountCooldown = $7E1EED
Horse_InteractDelay    = $7E1EEE
Horse_JumpCooldown     = $7E1EEF
Horse_JumpStartX       = $7E1EF0
Horse_JumpStartY       = $7E1EF2
Horse_JumpEndX         = $7E1EF4
Horse_JumpEndY         = $7E1EF6
Horse_AnchorX          = $7E1EF8
Horse_AnchorY          = $7E1EFA
Horse_HasAnchor        = $7E1EFC

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
HorseForm_TestEnd:
assert pc() <= $53D000

org $53D000
  incsrc "Masks/horse_mounted_helpers.asm"
assert pc() <= $53E000

org $0DA120
  dw $00C0, $00C0, $00C0
org $0DA126
  dw $2000, $2000, $2000, $2000
"""
    )
    image = folder / "fixture.sfc"
    image.write_bytes(b"\x00" * 0x300000)
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


class BushTrampleFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.cpu.db = 0x00
        self.tile_attr_map: dict[tuple[int, int], int] = {}
        self.default_tile_attr = 0x00
        self.tile_actions: list[dict] = []
        self.tile_action_clobber_dbr = True
        self.stubs = {
            STUB_GET_TILE_ATTR: "get_tile_attr",
            STUB_HANDLE_OW_TILE_ACTION: "handle_ow_tile_action",
            STUB_PAL_ARMOR: "rtl",
            STUB_LOAD_DAYNIGHT: "rtl",
            STUB_SFX_PAN: "sfx_pan",
            STUB_RESET_LINK_GFX: "rtl",
            STUB_SPRITE_SPAWN: "rtl",
            STUB_DASH_TREMOR: "rtl",
            STUB_KID_START: "rtl",
            STUB_HORSE_GAME_TICK: "rtl",
            STUB_SAVE_ANCHOR: "rtl",
            STUB_MAINTAIN_NPC: "rtl",
            STUB_OFF_RESTORE: "rtl",
            STUB_OFF_RANCH_NPC: "rtl",
            STUB_FRAME_END_SCAN: "rtl",
        }
        # Default valid mounted Overworld state on a 512x512 map at origin (0, 0).
        self.setup_area(origin_x=0, origin_y=0, width=512, height=512)
        self.setup_mounted_state()

    def setup_area(self, origin_x: int = 0, origin_y: int = 0, width: int = 512, height: int = 512):
        self.word(0x0708, origin_y)
        self.word(0x070A, height - 16)       # $01F0 (512) or $03F0 (1024)
        self.word(0x070C, origin_x >> 3)
        self.word(0x070E, (width >> 3) - 2)  # $003E (512) or $007E (1024)
        self.word(0xE2, origin_x)            # camera X
        self.word(0xE8, origin_y)            # camera Y
        self.word(0x1000, 0x0000)            # empty VRAM BG queue

    def setup_mounted_state(self, link_x: int = 0x0080, link_y: int = 0x0080, facing: int = 0x06):
        self.put(0x02B2, 0x09)               # !CurrentMask = Horse
        self.put(0x1B, 0x00)                 # outdoors
        self.put(0x10, 0x09)                 # Module $09 Overworld
        self.put(0x11, 0x00)                 # Submodule 0
        self.put(0x5D, 0x00)                 # Normal ground Link state
        self.put(0x4D, 0x00)
        self.put(0x6C, 0x00)
        self.put(0x5B, 0x00)
        self.put(0x0FFC, 0x00)
        self.put(0x02E4, 0x00)
        self.put(0x2F, facing)
        self.word(0x22, link_x)
        self.word(0x20, link_y)
        self.put(0xF0, 0x00)
        self.put(0xF2, 0x00)
        # Cold-init horse marker + grounded state + SP-3 distinct canary colors
        self.ram[0x1EDE] = 0x52
        self.ram[0x1EDF] = 0x48
        self.ram[0x1EE0] = 0x00              # Horse_State = 0
        self.ram[0x1EE1] = 0x00              # Horse_JumpTimer = 0
        self.ram[0x1EE5] = 0x00              # Horse_PushTimer = 0
        self.ram[0x1EEF] = 0x00              # Horse_JumpCooldown = 0
        self.ram[0xC67C] = 0x11
        self.ram[0xC67D] = 0x22
        self.ram[0xC67E] = 0x33
        self.ram[0xC67F] = 0x44
        self.ram[0x15410] = 0x00             # HorseGame_State ($7F5410) = 0

    def map16_offset(self, tx: int, ty: int) -> int:
        return (ty * 128) + (tx * 2)

    def set_tile16(self, tx: int, ty: int, tile16: int, attr: int | None = None):
        off = self.map16_offset(tx, ty)
        self.ram[0x2000 + off] = tile16 & 0xFF
        self.ram[0x2000 + off + 1] = (tile16 >> 8) & 0xFF
        if attr is not None:
            self.tile_attr_map[(tx, ty)] = attr

    def get_tile16(self, tx: int, ty: int) -> int:
        off = self.map16_offset(tx, ty)
        return self.ram[0x2000 + off] | (self.ram[0x2000 + off + 1] << 8)

    def _rtl(self):
        c = self.cpu
        c.sp += 1
        lo = self.ram[c.sp]
        c.sp += 1
        hi = self.ram[c.sp]
        c.sp += 1
        bank = self.ram[c.sp]
        c.pc = ((hi << 8) | lo) + 1
        c.k = bank

    def handle_stub(self, name: str):
        c = self.cpu
        if name == "get_tile_attr":
            y_px = self.get(0x00) | (self.get(0x01) << 8)
            x_t8 = self.get(0x02) | (self.get(0x03) << 8)
            y0 = self.get(0x0708) | (self.get(0x0709) << 8)
            ym = self.get(0x070A) | (self.get(0x070B) << 8)
            x0 = self.get(0x070C) | (self.get(0x070D) << 8)
            xm = self.get(0x070E) | (self.get(0x070F) << 8)
            ty = ((y_px - y0) & ym) >> 4
            tx = ((x_t8 - x0) & xm) >> 1
            attr = self.tile_attr_map.get((tx, ty), self.default_tile_attr)
            c.mf = c.xf = True
            c.a = (c.a & 0xFF00) | (attr & 0xFF)
            self._rtl()
        elif name == "handle_ow_tile_action":
            # Verify HandleItemTileAction_Overworld entry ABI strictly!
            assert c.mf and c.xf, f"Expected M=8, X=8 at $1BBD7A, got M={c.mf} X={c.xf}"
            assert c.db == 0x00, f"Expected DBR=$00 at $1BBD7A, got ${c.db:02X}"
            assert self.get(0x1B) == 0x00, "Called HandleItemTileAction_Overworld indoors!"
            assert self.get(0x0301) == 0x00, f"$0301 must be 0 (no hammer/powder), got ${self.get(0x0301):02X}"
            assert self.get(0x037A) == 0x00, f"$037A must be 0 (no shovel), got ${self.get(0x037A):02X}"

            y_px = self.get(0x00) | (self.get(0x01) << 8)
            x_t8 = self.get(0x02) | (self.get(0x03) << 8)
            y0 = self.get(0x0708) | (self.get(0x0709) << 8)
            ym = self.get(0x070A) | (self.get(0x070B) << 8)
            x0 = self.get(0x070C) | (self.get(0x070D) << 8)
            xm = self.get(0x070E) | (self.get(0x070F) << 8)
            off = (((y_px - y0) & ym) << 3) + ((x_t8 - x0) & xm)
            tile16 = self.ram[0x2000 + off] | (self.ram[0x2000 + off + 1] << 8)
            tx = ((x_t8 - x0) & xm) >> 1
            ty = ((y_px - y0) & ym) >> 4
            self.tile_actions.append(
                dict(
                    tx=tx,
                    ty=ty,
                    y_px=y_px,
                    x_t8=x_t8,
                    tile16=tile16,
                    coll_0302=self.get(0x0302),
                    nopain_037b=self.get(0x037B),
                )
            )
            # Mimic vanilla OverworldTileAction_Bush side effects:
            # replace $0036 with $0DC7, advance $1000 VRAM queue by $10, clobber DP $00..$0E & DBR!
            if tile16 == 0x0036:
                self.ram[0x2000 + off] = 0xC7
                self.ram[0x2000 + off + 1] = 0x0D
                q = self.get(0x1000) | (self.get(0x1001) << 8)
                self.word(0x1000, q + 0x10)
                self.put(0x14, 0x01)
                self.put(0x012E, 0x1E)
                self.put(0x76, 0x02)
            # Deliberately clobber scratch DP $00..$0F and DBR to prove caller preserves them!
            for dp in range(0x00, 0x10):
                self.put(dp, 0xA5)
            if self.tile_action_clobber_dbr:
                c.db = 0x1B
            c.mf = c.xf = True
            self._rtl()
        elif name == "sfx_pan":
            c.a = (c.a & 0xFF00) | 0x00
            self._rtl()
        elif name == "rtl":
            self._rtl()

    def run_jsr(self, name: str, *, x: int = 0x33, y: int = 0x44, a: int = 0x55):
        c = self.cpu
        c.mf = c.xf = True
        c.db = 0x00
        c.x, c.y = x, y
        c.a = (c.a & 0xFF00) | a
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, 0x6F)
        self.put(sp - 1, 0xFF)
        c.sp -= 2
        sentinel = (entry & 0xFF0000) | 0x7000
        for count in range(60000):
            addr = (c.k << 16) | c.pc
            if addr == sentinel:
                assert c.sp == sp, f"{name}: SP drift {c.sp:#x} != {sp:#x}"
                assert not self.bad_writes, f"{name}: bad writes {self.bad_writes}"
                assert c.db == 0x00 and c.mf and c.xf, f"{name}: ABI drift db={c.db:#x} mf={c.mf} xf={c.xf}"
                assert (c.x & 0xFF) == x and (c.y & 0xFF) == y, (
                    f"{name}: X/Y clobbered ({c.x & 0xFF:#x},{c.y & 0xFF:#x}) != ({x:#x},{y:#x})"
                )
                return count
            if addr in self.stubs:
                self.handle_stub(self.stubs[addr])
                continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name}: instruction bound at {((c.k << 16) | c.pc):#08x}")

    def run_jsl(self, name: str):
        c = self.cpu
        c.mf = c.xf = True
        c.db = 0x00
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        sentinel = (entry & 0xFF0000) | 0x7000
        for count in range(100000):
            addr = (c.k << 16) | c.pc
            if addr == sentinel:
                assert c.sp == sp, f"{name}: SP drift {c.sp:#x} != {sp:#x}"
                assert not self.bad_writes, f"{name}: bad writes {self.bad_writes}"
                return count
            if addr in self.stubs:
                self.handle_stub(self.stubs[addr])
                continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name}: instruction bound at {((c.k << 16) | c.pc):#08x}")


class TestHorseBushTrample(unittest.TestCase):
    _tmpdir: tempfile.TemporaryDirectory
    _lib: C.CDLL
    _rom: bytes
    _labels: dict[str, int]

    @classmethod
    def setUpClass(cls):
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="horse-bush-trample-")
        d = Path(cls._tmpdir.name)
        lakesnes = find_lakesnes()
        lib_path = d / "cpu.dylib"
        subprocess.run(
            [
                "cc",
                "-shared",
                "-fPIC",
                "-O2",
                str(lakesnes / "snes" / "cpu.c"),
                str(lakesnes / "snes" / "statehandler.c"),
                "-o",
                str(lib_path),
            ],
            check=True,
        )
        cls._lib = C.CDLL(str(lib_path))
        cls._lib.cpu_init.restype = C.POINTER(Cpu)
        cls._lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls._lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls._rom, cls._labels = assemble_horse_rom(d / "build")

    @classmethod
    def tearDownClass(cls):
        cls._tmpdir.cleanup()

    def make_fixture(self) -> BushTrampleFixture:
        fx = BushTrampleFixture(self._lib, self._rom, self._labels)
        self.addCleanup(fx.close)
        return fx

    def test_bank53_slice_bounds(self):
        self.assertLessEqual(self._labels["HorseForm_TestEnd"], 0x53D000)
        self.assertLessEqual(self._labels["HorseMountedHelpers_End"], 0x53E000)
        self.assertLessEqual(self._labels["HorseGroundClearance_End"], 0x53E800)
        self.assertGreaterEqual(self._labels["HorseForm_TrampleBushes"], 0x53F000)
        self.assertLessEqual(self._labels["HorseBushTrample_End"], 0x53F400)

    def test_cardinal_directions_trample_bush_and_preserve_state(self):
        # Link at (0x80, 0x80) occupies tile (8, 8..9) -> X=[0x80..0x8F], Y=[0x88..0x97].
        # Leading probes:
        #   N ($08): (0x80, 0x84) & (0x8F, 0x84) -> tile (8, 8) when link_y=0x8C -> Y+4=0x90 (ty=9), wait:
        #   Let's position Link flush next to a bush in each of the 4 cardinal directions!
        cases = [
            # (name, pad, link_x, link_y, bush_tx, bush_ty)
            ("north", 0x08, 0x0080, 0x0088, 8, 8),  # Y+4 = 0x8C -> ty=8 (bush [0x80..0x8F])
            ("south", 0x04, 0x0080, 0x0078, 8, 9),  # Y+28 = 0x94 -> ty=9 (bush [0x90..0x9F])
            ("west",  0x02, 0x0090, 0x0080, 8, 8),  # X-4 = 0x8C -> tx=8, Y+8 = 0x88 -> ty=8
            ("east",  0x01, 0x0070, 0x0080, 8, 8),  # X+19 = 0x83 -> tx=8, Y+8 = 0x88 -> ty=8
        ]
        for name, pad, lx, ly, btx, bty in cases:
            with self.subTest(direction=name):
                fx = self.make_fixture()
                fx.setup_mounted_state(link_x=lx, link_y=ly)
                fx.set_tile16(btx, bty, 0x0036, attr=0x50)
                fx.put(0xF0, pad)
                # Set non-zero sentinel values in $0301/$0302/$037A/$037B and DP $00-$0F
                fx.put(0x0301, 0x42)
                fx.put(0x0302, 0x77)
                fx.put(0x037A, 0x01)
                fx.put(0x037B, 0x88)
                for dp in range(0x00, 0x10):
                    fx.put(dp, 0x30 + dp)

                fx.run_jsr("HorseForm_TrampleBushes")

                # Exactly ONE cut call (second probe hits $0DC7 and skips!)
                self.assertEqual(len(fx.tile_actions), 1, fx.tile_actions)
                act = fx.tile_actions[0]
                self.assertEqual((act["tx"], act["ty"], act["tile16"]), (btx, bty, 0x0036))
                self.assertEqual(act["coll_0302"], 0x77)
                self.assertEqual(act["nopain_037b"], 0x88)
                self.assertEqual(fx.get_tile16(btx, bty), 0x0DC7)
                # Verify full preservation of $0301/$0302/$037A/$037B and DP $00-$0F
                self.assertEqual(fx.get(0x0301), 0x42)
                self.assertEqual(fx.get(0x0302), 0x77)
                self.assertEqual(fx.get(0x037A), 0x01)
                self.assertEqual(fx.get(0x037B), 0x88)
                for dp in range(0x00, 0x10):
                    self.assertEqual(fx.get(dp), 0x30 + dp, f"DP ${dp:02X} not preserved")

    def test_two_adjacent_bushes_trampled_in_one_frame(self):
        # Straddling tiles tx=7 and tx=8 while riding North: p0 hits tx=7, p1 hits tx=8.
        fx = self.make_fixture()
        fx.setup_mounted_state(link_x=0x0078, link_y=0x0088)  # X+0=0x78 (tx=7), X+15=0x87 (tx=8), Y+4=0x8C (ty=8)
        fx.set_tile16(7, 8, 0x0036, attr=0x50)
        fx.set_tile16(8, 8, 0x0036, attr=0x50)
        fx.put(0xF0, 0x08)

        fx.run_jsr("HorseForm_TrampleBushes")

        self.assertEqual({(a["tx"], a["ty"]) for a in fx.tile_actions}, {(7, 8), (8, 8)})
        self.assertEqual(fx.get_tile16(7, 8), 0x0DC7)
        self.assertEqual(fx.get_tile16(8, 8), 0x0DC7)

    def test_diagonal_corner_bushes_trampled_all_4_diagonals(self):
        # Position Link so the bush touches ONLY the leading diagonal corner (missed by cardinal probes):
        # Link at (0x0080, 0x0088):
        #   NE (0x09): N=(0x80..0x8F, 0x8C), E=(0x93, 0x90..0x9F), NE=(0x93, 0x8C) -> tile (9, 8) ONLY hit by NE!
        #   NW (0x0A): N=(0x80..0x8F, 0x8C), W=(0x7C, 0x90..0x9F), NW=(0x7C, 0x8C) -> tile (7, 8) ONLY hit by NW!
        #   SE (0x05): link_y=0x0078 -> S=(0x80..0x8F, 0x94), E=(0x93, 0x80..0x8F), SE=(0x93, 0x94) -> tile (9, 9) ONLY hit by SE!
        #   SW (0x06): link_y=0x0078 -> S=(0x80..0x8F, 0x94), W=(0x7C, 0x80..0x8F), SW=(0x7C, 0x94) -> tile (7, 9) ONLY hit by SW!
        cases = [
            ("NE", 0x09, 0x0080, 0x0088, 9, 8),
            ("NW", 0x0A, 0x0080, 0x0088, 7, 8),
            ("SE", 0x05, 0x0080, 0x0078, 9, 9),
            ("SW", 0x06, 0x0080, 0x0078, 7, 9),
        ]
        for name, pad, lx, ly, btx, bty in cases:
            with self.subTest(diag=name):
                fx = self.make_fixture()
                fx.setup_mounted_state(link_x=lx, link_y=ly)
                fx.set_tile16(btx, bty, 0x0036, attr=0x50)
                fx.put(0xF0, pad)

                fx.run_jsr("HorseForm_TrampleBushes")

                self.assertEqual(len(fx.tile_actions), 1, fx.tile_actions)
                self.assertEqual((fx.tile_actions[0]["tx"], fx.tile_actions[0]["ty"]), (btx, bty))
                self.assertEqual(fx.get_tile16(btx, bty), 0x0DC7)

    def test_non_bush_tiles_never_trampled(self):
        non_bushes = [
            ("small_light_rock", 0x020F, 0x52),
            ("small_heavy_rock", 0x0239, 0x53),
            ("large_light_rock", 0x036D, 0x55),
            ("large_heavy_rock", 0x023B, 0x56),
            ("rock_pile",        0x0226, 0x57),
            ("lw_sign",          0x0101, 0x54),
            ("dw_sign",          0x017D, 0x54),
            ("hammer_peg",       0x021B, 0x54),
            ("ranch_fence_78",   0x0078, 0x01),
            ("ranch_fence_7b",   0x007B, 0x01),
            ("tall_grass",       0x037E, 0x40),
            ("lw22_brick_072a",  0x072A, 0x00),
            ("solid_wall",       0x0020, 0x01),
            ("plain_grass",      0x0000, 0x00),
        ]
        for label, tid, attr in non_bushes:
            with self.subTest(tile=label, tid=hex(tid)):
                fx = self.make_fixture()
                fx.setup_mounted_state(link_x=0x0070, link_y=0x0080)
                fx.set_tile16(8, 8, tid, attr=attr)
                fx.put(0xF0, 0x01)  # moving East into tile (8, 8)

                fx.run_jsr("HorseForm_TrampleBushes")

                self.assertEqual(fx.tile_actions, [], f"{label} ({tid:#06x}) must NEVER be trampled!")
                self.assertEqual(fx.get_tile16(8, 8), tid)

    def test_safety_guards_block_trampling(self):
        guard_mutations = [
            ("dismounted_link",     lambda fx: fx.put(0x02B2, 0x00)),
            ("dismounted_deku",     lambda fx: fx.put(0x02B2, 0x01)),
            ("indoors",             lambda fx: fx.put(0x1B, 0x01)),
            ("dungeon_module_07",   lambda fx: fx.put(0x10, 0x07)),
            ("pause_module_0e",     lambda fx: fx.put(0x10, 0x0E)),
            ("submodule_nonzero",   lambda fx: fx.put(0x11, 0x01)),
            ("link_state_nonzero",  lambda fx: fx.put(0x5D, 0x04)),
            ("link_recoil_nonzero", lambda fx: fx.put(0x4D, 0x01)),
            ("doorway_nonzero",     lambda fx: fx.put(0x6C, 0x01)),
            ("freeze_0ffc",         lambda fx: fx.put(0x0FFC, 0x01)),
            ("cutscene_02e4",       lambda fx: fx.put(0x02E4, 0x01)),
            ("minigame_intro_1",    lambda fx: fx.ram.__setitem__(0x15410, 0x01)),
            ("minigame_finish_3",   lambda fx: fx.ram.__setitem__(0x15410, 0x03)),
            ("fence_jumping",       lambda fx: fx.ram.__setitem__(0x1EE0, 0x01)),
            ("long_jumping",        lambda fx: fx.ram.__setitem__(0x1EE1, 0x10)),
            ("standing_still",      lambda fx: fx.put(0xF0, 0x00)),
        ]
        for label, mutate in guard_mutations:
            with self.subTest(guard=label):
                fx = self.make_fixture()
                fx.setup_mounted_state(link_x=0x0070, link_y=0x0080)
                fx.set_tile16(8, 8, 0x0036, attr=0x50)
                fx.put(0xF0, 0x01)
                mutate(fx)

                fx.run_jsr("HorseForm_TrampleBushes")

                self.assertEqual(fx.tile_actions, [], f"Guard {label} failed to block trample!")
                self.assertEqual(fx.get_tile16(8, 8), 0x0036)

    def test_module_0b_and_active_minigame_ride_allow_trampling(self):
        for label, mod, mg_state in [("ow_special_0b", 0x0B, 0x00), ("minigame_active_2", 0x09, 0x02)]:
            with self.subTest(case=label):
                fx = self.make_fixture()
                fx.setup_mounted_state(link_x=0x0070, link_y=0x0080)
                fx.set_tile16(8, 8, 0x0036, attr=0x50)
                fx.put(0x10, mod)
                fx.ram[0x15410] = mg_state
                fx.put(0xF0, 0x01)

                fx.run_jsr("HorseForm_TrampleBushes")

                self.assertEqual(len(fx.tile_actions), 1)
                self.assertEqual(fx.get_tile16(8, 8), 0x0DC7)

    def test_area_boundary_no_wraparound_and_viewport_and_queue_guards(self):
        # 1. Area West border wraparound: Link at X=0x0002 moving West -> X-4 = 0xFFFE (outside area!)
        #    Place bush at far East tile (31, 8) that wraparound would falsely alias!
        fx = self.make_fixture()
        fx.setup_area(origin_x=0x0000, origin_y=0x0000, width=512, height=512)
        fx.setup_mounted_state(link_x=0x0002, link_y=0x0080)
        fx.set_tile16(31, 8, 0x0036, attr=0x50)
        fx.put(0xF0, 0x02)
        fx.run_jsr("HorseForm_TrampleBushes")
        self.assertEqual(fx.tile_actions, [], "Out-of-area West probe must not wrap to East edge!")
        self.assertEqual(fx.get_tile16(31, 8), 0x0036)

        # 2. Out-of-viewport probe: camera scrolled away so bush is offscreen
        fx2 = self.make_fixture()
        fx2.setup_area(origin_x=0x0000, origin_y=0x0000, width=512, height=512)
        fx2.word(0xE2, 0x0100)  # viewport X = [0x100..0x1FF]
        fx2.setup_mounted_state(link_x=0x0070, link_y=0x0080)
        fx2.set_tile16(8, 8, 0x0036, attr=0x50)
        fx2.put(0xF0, 0x01)
        fx2.run_jsr("HorseForm_TrampleBushes")
        self.assertEqual(fx2.tile_actions, [], "Off-viewport bush must not be trampled!")
        self.assertEqual(fx2.get_tile16(8, 8), 0x0036)

        # 3. $1000 VRAM BG update buffer near full (>= $00D0) skips safely
        fx3 = self.make_fixture()
        fx3.setup_mounted_state(link_x=0x0070, link_y=0x0080)
        fx3.set_tile16(8, 8, 0x0036, attr=0x50)
        fx3.word(0x1000, 0x00D0)
        fx3.put(0xF0, 0x01)
        fx3.run_jsr("HorseForm_TrampleBushes")
        self.assertEqual(fx3.tile_actions, [], "Full $1000 BG queue must skip bush cut safely!")
        self.assertEqual(fx3.get_tile16(8, 8), 0x0036)

    def test_frame_tick_integration_trample_vs_wall_vs_fence_jump(self):
        # A) Full HorseForm_FrameTick riding East into bush: tramples AND keeps $F0 East bit clear of snag
        fx = self.make_fixture()
        fx.setup_mounted_state(link_x=0x0070, link_y=0x0080, facing=0x06)
        fx.set_tile16(8, 8, 0x0036, attr=0x50)
        fx.put(0xF0, 0x01)
        fx.run_jsl("HorseForm_FrameTick")
        self.assertEqual(len(fx.tile_actions), 1)
        self.assertEqual(fx.get_tile16(8, 8), 0x0DC7)
        self.assertEqual(fx.get(0xF0) & 0x01, 0x01, "East input must remain live so Epona rides smoothly")
        self.assertEqual(fx.ram[0x1EE0], 0x00, "Must stay grounded on bush trample")

        # B) Solid wall ($01) directly in front strips East input in ConstrainGroundInput
        #    so bush behind wall is NOT trampled!
        fx2 = self.make_fixture()
        fx2.setup_mounted_state(link_x=0x006C, link_y=0x0080, facing=0x06)
        # Edge X for East clearance is link_x + $15 = 0x81 -> tile (8, 8) solid wall ($01)!
        # Bush probe East is link_x + $13 = 0x7F -> tile (7, 8) bush? Wait: test solid wall at (8,8) blocking East
        # while bush is at (8,9) inside probe range:
        fx2.set_tile16(8, 8, 0x0020, attr=0x01)  # solid wall blocks East middle probe (Y+8, Y+12)
        fx2.set_tile16(8, 9, 0x0036, attr=0x50)  # bush at Y+23 right beside/behind wall
        fx2.put(0xF0, 0x01)
        fx2.run_jsl("HorseForm_FrameTick")
        self.assertEqual(fx2.get(0xF0) & 0x01, 0x00, "Solid wall should strip East input")
        self.assertEqual(fx2.tile_actions, [], "Blocked direction must not trample bush")
        self.assertEqual(fx2.get_tile16(8, 9), 0x0036)

        # C) Wooden fence ($007B) ahead still launches fence jump (Horse_State=1) without touching tile actions
        fx3 = self.make_fixture()
        fx3.setup_mounted_state(link_x=0x006E, link_y=0x0080, facing=0x06)
        fx3.set_tile16(8, 8, 0x007B, attr=0x01)  # Toto Ranch wooden fence
        fx3.set_tile16(9, 8, 0x0000, attr=0x00)  # walkable landing past fence
        fx3.set_tile16(9, 9, 0x0000, attr=0x00)
        fx3.ram[0x1EE5] = 0x01                   # PushTimer = 1 -> next frame triggers fence jump
        fx3.put(0xF0, 0x01)
        fx3.run_jsl("HorseForm_FrameTick")
        self.assertEqual(fx3.ram[0x1EE0], 0x01, "Fence jump must still launch!")
        self.assertEqual(fx3.tile_actions, [], "Fence jump must never invoke bush trampling")


if __name__ == "__main__":
    unittest.main(verbosity=2)
