#!/usr/bin/env python3
"""Compiled checks for Korok Cove NPC polish (Sprites/NPCs/korok.asm).

Runs the real draw and idle routines on Lakesnes' 65816 core. Engine calls are
RTL stubs. No emulator process, socket, shared ROM, or Roms/ write.
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

SLOT = 0
HOME = 0x40
SCREEN_X = 0x20
SCREEN_Y = 0x40
OAM_BASE = 0x0800
DRAW = (
    "Sprite_Korok_DrawMakar",
    "Sprite_Korok_DrawHollo",
    "Sprite_Korok_DrawRown",
)
# DirectionToFacePlayer Y -> still frame (right, left, down, up).
FACE_FRAMES = (0x09, 0x06, 0x00, 0x03)

FIXTURE_ASM = r"""lorom

macro Set_Sprite_Properties(prep, main)
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

Sprite_Korok = $F1
SprY = $0D00
SprX = $0D10
SprYSpeed = $0D40
SprXSpeed = $0D50
SprAction = $0D80
SprFrame = $0D90
SprMiscA = $0DA0
SprMiscB = $0DB0
SprMiscC = $0DE0
SprTimerA = $0DF0
SprTimerB = $0E00
SprSubtype = $0E30
SprCollision = $0E70
SprTimerD = $0EE0

Sprite_PrepOamCoord = $06E416
Sprite_OAM_AllocateDeferToPlayer = $06F864
OAM_AllocateFromRegionA = $0DBA80
Sprite_CheckDamageFromPlayer = $068820
Sprite_PlayerCantPassThrough = $1EF4F3
Sprite_DirectionToFacePlayer = $06EAA0
Sprite_ApplySpeedTowardsPlayer = $0688B0
Sprite_CheckTileCollision = $06E496
Sprite_Move = $1D808C
GetDistance8bit_Long = $1D8100
Sprite_CheckDamageToPlayerSameLayer = $06F129
SpriteSFX_QueueSFX2WithPan = $0DBB7C
Link_ReceiveItem = $0791B3
GetRandomInt = $0DBA71
Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7
ApplyKorokSpriteSheets = $018000
Sprite_DrawShadow = $06DC54
Sprite_CheckActive = $06E400

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

org $308000
incsrc "korok.asm"
"""


def find_lakesnes() -> Path:
    candidates = [
        Path(os.environ["OOS_LAKESNES"]) if os.environ.get("OOS_LAKESNES") else None,
        Path("/Users/scawful/src/hobby/lakesnes"),
        ROOT.parent / "lakesnes",
    ]
    for cand in candidates:
        if cand and (cand / "snes/cpu.c").is_file():
            return cand
    raise RuntimeError("Could not locate lakesnes (set OOS_LAKESNES)")


def build_cpu_lib(lakesnes: Path, work_dir: Path) -> C.CDLL:
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


def assemble_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "korok.asm").write_bytes((ROOT / "Sprites/NPCs/korok.asm").read_bytes())
    asm = folder / "fixture.asm"
    asm.write_text(FIXTURE_ASM, encoding="utf-8")
    image = folder / "fixture.sfc"
    image.write_bytes(b"\xFF" * 0x200000)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla",
         str(asm), str(image)],
        capture_output=True, text=True,
    )
    if res.returncode != 0:
        raise AssertionError(f"Asar failed:\n{res.stdout}\n{res.stderr}")
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            image.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return image.read_bytes(), labels


class KorokFixture(Fixture):
    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        for name in ("GetRandomInt", "Sprite_ShowSolicitedMessageIfPlayerFacing"):
            addr = self.addr(name)
            if addr is None:
                raise AssertionError(f"missing stub label {name}")
            self.stubs[addr] = name
        self.cpu.db = 0x30
        self.prep_carry = False
        self.screen_x = SCREEN_X
        self.screen_y = SCREEN_Y
        self.message_open = False
        self.random_q: list[int] = []
        self.direction = 2

    def stub(self, name):
        if name == "Sprite_PrepOamCoord":
            self.word(0, self.screen_x & 0xFFFF)
            self.word(2, self.screen_y & 0xFFFF)
            self.cpu.c = bool(self.prep_carry)
            return
        if name == "Sprite_ShowSolicitedMessageIfPlayerFacing":
            self.cpu.c = bool(self.message_open)
            return
        if name == "GetRandomInt":
            value = self.random_q.pop(0) if self.random_q else 0
            self.cpu.a = (self.cpu.a & 0xFF00) | (value & 0xFF)
            self.cpu.z = (value & 0xFF) == 0
            self.cpu.n = bool(value & 0x80)
            return
        super().stub(name)

    def invoke(self, name: str, slot: int = SLOT):
        self.cpu.db = 0x30
        self.cpu.mf = True
        self.cpu.xf = True
        self.call(name, x=slot)

    def clear_oam(self):
        for i in range(64):
            self.ram[OAM_BASE + i] = 0xEE

    def tiles(self, count: int) -> list[tuple[int, int, int, int]]:
        out = []
        for i in range(count):
            o = OAM_BASE + i * 4
            out.append(tuple(self.ram[o:o + 4]))  # type: ignore[arg-type]
        return out

    def reset_actor(self, slot: int = SLOT):
        for addr in (
            0x0D00, 0x0D10, 0x0D20, 0x0D30, 0x0D40, 0x0D50,
            0x0D80, 0x0D90, 0x0DA0, 0x0DB0, 0x0DC0, 0x0DE0,
            0x0DF0, 0x0E00, 0x0E30, 0x0E70, 0x0EE0,
        ):
            self.ram[addr + slot] = 0
        self.ram[0x0DA0 + slot] = HOME
        self.ram[0x0DB0 + slot] = HOME
        self.ram[0x0D10 + slot] = HOME
        self.ram[0x0D00 + slot] = HOME
        self.ram[0x10] = 0x09
        self.ram[0x1A] = 0
        self.message_open = False
        self.prep_carry = False
        self.random_q = []
        self.direction = 2


class KorokPolishTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._tmp = tempfile.TemporaryDirectory(prefix="korok-polish-")
        work = Path(cls._tmp.name)
        cls.lib = build_cpu_lib(find_lakesnes(), work)
        cls.rom, cls.labels = assemble_fixture(work / "build")

    @classmethod
    def tearDownClass(cls):
        cls._tmp.cleanup()

    def fixture(self) -> KorokFixture:
        fix = KorokFixture(self.lib, self.rom, self.labels)
        fix.reset_actor()
        return fix

    def test_legacy_main_has_no_asm_callers(self):
        hits = []
        for path in ROOT.rglob("*.asm"):
            rel = path.relative_to(ROOT)
            if any(part.startswith(".") for part in rel.parts):
                continue
            if "Sprite_Korok_Main" in path.read_text(encoding="utf-8", errors="ignore"):
                hits.append(str(rel))
        self.assertEqual(hits, [])

    def test_offscreen_carry_skips_oam(self):
        fix = self.fixture()
        fix.prep_carry = True
        fix.screen_x = 0x0200
        for name in DRAW:
            fix.clear_oam()
            fix.invoke(name)
            self.assertTrue(all(b == 0xEE for b in fix.ram[OAM_BASE:OAM_BASE + 32]), name)
        fix.close()

    def test_far_horizontal_never_wraps_on_screen(self):
        """X = $0200 and X = $FF00 used to store the low byte and appear at X=0."""
        for screen_x in (0x0200, 0xFF00):
            for name in DRAW:
                fix = self.fixture()
                fix.prep_carry = False
                fix.screen_x = screen_x
                fix.screen_y = SCREEN_Y
                fix.ram[0x0D80] = 1  # stroll, so the idle bob does not move Y
                fix.clear_oam()
                fix.invoke(name)
                tiles = fix.tiles(2)
                for index, (x, y, _chr, _prop) in enumerate(tiles):
                    self.assertEqual(y, 0xF0, (name, hex(screen_x), index, x, y))
                    self.assertNotEqual(y, SCREEN_Y & 0xFF, name)
                fix.close()

    def test_draw_parity_palette_and_makar_frames(self):
        expected_chr = {
            "Sprite_Korok_DrawMakar": (0x00, 0x10),
            "Sprite_Korok_DrawHollo": (0x40, 0x50),
            "Sprite_Korok_DrawRown": (0x82, 0x92),
        }
        # The tile loop counts down, so OAM order is the reverse of the table.
        for name, chrs in expected_chr.items():
            fix = self.fixture()
            fix.screen_x = SCREEN_X
            fix.screen_y = SCREEN_Y
            fix.ram[0x0D80] = 1
            fix.clear_oam()
            fix.invoke(name)
            tiles = fix.tiles(2)
            self.assertEqual(
                tiles,
                [
                    (SCREEN_X, SCREEN_Y, chrs[1], 0x27),
                    (SCREEN_X, SCREEN_Y - 8, chrs[0], 0x27),
                ],
                name,
            )
            fix.close()

        # Makar walk-down frame 2: feet $20/$21 at x+0 and x+8, unflipped palette 3.
        fix = self.fixture()
        fix.screen_x = SCREEN_X
        fix.screen_y = SCREEN_Y
        fix.ram[0x0D80] = 1
        fix.ram[0x0D90] = 2
        fix.clear_oam()
        fix.invoke("Sprite_Korok_DrawMakar")
        self.assertEqual(
            fix.tiles(3),
            [
                (SCREEN_X + 8, SCREEN_Y + 8, 0x21, 0x27),
                (SCREEN_X, SCREEN_Y + 8, 0x20, 0x27),
                (SCREEN_X, SCREEN_Y - 8, 0x00, 0x27),
            ],
        )
        fix.close()

        # Makar walk-right frame 9 stays mirrored (hflip, crest swapped in X).
        fix = self.fixture()
        fix.screen_x = SCREEN_X
        fix.screen_y = SCREEN_Y
        fix.ram[0x0D80] = 1
        fix.ram[0x0D90] = 9
        fix.clear_oam()
        fix.invoke("Sprite_Korok_DrawMakar")
        tiles = fix.tiles(3)
        self.assertEqual([t[0] for t in tiles], [SCREEN_X, SCREEN_X + 8, SCREEN_X])
        self.assertEqual([t[1] for t in tiles], [SCREEN_Y - 8, SCREEN_Y - 8, SCREEN_Y])
        self.assertTrue(all(prop == 0x67 for *_, prop in tiles))
        fix.close()

    def test_stroll_resets_frame_on_all_four_directions(self):
        # (random axis bit, dx, dy, action, frame)
        # Past the leash, PickDir does not consume a second random.
        cases = (
            (0x00, 0x20, 0x00, 0x01, 0x06),  # too far right -> left, frame 6
            (0x00, -0x20, 0x00, 0x02, 0x09),  # too far left -> right, frame 9
            (0x01, 0x00, 0x20, 0x03, 0x03),  # too far down -> up, frame 3
            (0x01, 0x00, -0x20, 0x04, 0x00),  # too far up -> down, frame 0
        )
        for axis, dx, dy, action, frame in cases:
            fix = self.fixture()
            fix.ram[0x0D90] = 0x0B  # stale frame from another direction
            fix.ram[0x0D10] = (HOME + dx) & 0xFF
            fix.ram[0x0D00] = (HOME + dy) & 0xFF
            fix.ram[0x0DF0] = 0
            fix.random_q = [axis, 0x00]
            fix.invoke("Sprite_Korok_PolishIdle")
            self.assertEqual(fix.ram[0x0D80], action, (dx, dy, fix.ram[0x0D80]))
            self.assertEqual(fix.ram[0x0D90], frame, (dx, dy, fix.ram[0x0D90]))
            fix.close()

    def test_face_link_while_talking_then_resume_idle(self):
        for face_y, frame in enumerate(FACE_FRAMES):
            fix = self.fixture()
            fix.ram[0x0D80] = 0x02
            fix.ram[0x0D90] = 0x0B
            fix.ram[0x0D50] = 0x04
            fix.ram[0x0D40] = 0x04
            fix.message_open = True
            fix.direction = face_y
            fix.invoke("Sprite_Korok_PolishMain")
            self.assertEqual(fix.ram[0x0D80], 0, face_y)
            self.assertEqual(fix.ram[0x0D90], frame, face_y)
            self.assertEqual(fix.ram[0x0DE0], 1, face_y)
            self.assertEqual(fix.ram[0x0D50], 0, face_y)
            self.assertEqual(fix.ram[0x0D40], 0, face_y)

            # Text still up: the pose stays put.
            fix.message_open = False
            fix.ram[0x10] = 0x0E
            fix.ram[0x1A] = 0x10  # would otherwise rock Makar to frame 1
            fix.invoke("Sprite_Korok_PolishMain")
            self.assertEqual(fix.ram[0x0D90], frame, face_y)
            self.assertEqual(fix.ram[0x0DE0], 1, face_y)

            # Text closed: latch drops and the front idle pose returns.
            fix.ram[0x10] = 0x09
            fix.ram[0x0EE0] = 0
            fix.ram[0x1A] = 0
            fix.invoke("Sprite_Korok_PolishMain")
            self.assertEqual(fix.ram[0x0DE0], 0, face_y)
            self.assertEqual(fix.ram[0x0D80], 0, face_y)
            self.assertEqual(fix.ram[0x0D90], 0, face_y)
            fix.close()

    def test_idle_flavor_is_distinct_per_variant(self):
        # (subtype, frame counter, expected frame)
        cases = (
            (0, 0x00, 0x00),
            (0, 0x10, 0x01),  # Makar rocks the two front frames
            (1, 0x04, 0x01),  # Hollo crest-up during the hop window
            (1, 0x20, 0x00),
            (2, 0x00, 0x00),
            (2, 0x20, 0x06),  # Rown glances left
        )
        for subtype, frame_counter, frame in cases:
            fix = self.fixture()
            fix.ram[0x0E30] = subtype
            fix.ram[0x1A] = frame_counter
            fix.ram[0x0DF0] = 0x20
            fix.ram[0x0D90] = 0x0B
            fix.invoke("Sprite_Korok_PolishIdle")
            self.assertEqual(fix.ram[0x0D80], 0, (subtype, frame_counter))
            self.assertEqual(fix.ram[0x0D90], frame, (subtype, frame_counter, fix.ram[0x0D90]))
            fix.close()

        # Makar's bob lifts the sprite one pixel; a stroll does not.
        fix = self.fixture()
        fix.screen_x = SCREEN_X
        fix.screen_y = SCREEN_Y
        fix.ram[0x0E30] = 0
        fix.ram[0x0D80] = 0
        fix.ram[0x1A] = 0x10
        fix.clear_oam()
        fix.invoke("Sprite_Korok_DrawMakar")
        # First OAM slot is the lower tile (table Y 0), lifted 1px by the bob.
        self.assertEqual(fix.tiles(1)[0][1], SCREEN_Y - 1)
        fix.close()

        fix = self.fixture()
        fix.screen_x = SCREEN_X
        fix.screen_y = SCREEN_Y
        fix.ram[0x0E30] = 1
        fix.ram[0x0D80] = 0
        fix.ram[0x1A] = 0x04
        fix.clear_oam()
        fix.invoke("Sprite_Korok_DrawHollo")
        self.assertEqual(fix.tiles(1)[0][1], SCREEN_Y - 2)
        fix.close()


if __name__ == "__main__":
    unittest.main()
