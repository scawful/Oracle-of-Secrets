#!/usr/bin/env python3
"""Compiled Asar + headless 65816 CPU unit tests for Overworld/entrances.asm
directional doorway gating, UP-intent strafe guard, D8 recessed arch depth,
and Shrine/D4/DW-70/Tavern-back doorway entry parity.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASAR_BIN = os.environ.get("ASAR_BIN") or shutil.which("asar")
LAKESNES_DIR = Path(os.environ.get("LAKESNES_DIR", "/Users/scawful/src/hobby/LakeSnes"))

sys.path.insert(0, str(ROOT / "Tests"))
from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def _compile_cpu(tmp_dir: Path) -> C.CDLL:
    libpath = tmp_dir / "cpu_doorways.dylib"
    subprocess.run(
        [
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            str(LAKESNES_DIR / "snes/cpu.c"),
            str(LAKESNES_DIR / "snes/statehandler.c"),
            "-o",
            str(libpath),
        ],
        check=True,
    )
    lib = C.CDLL(str(libpath))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _assemble(tmp_dir: Path, name: str, rom_buf: bytearray, asm_src: str) -> tuple[bytes, dict[str, int]]:
    rom_path = tmp_dir / f"{name}.sfc"
    asm_path = tmp_dir / f"{name}.asm"
    sym_path = tmp_dir / f"{name}.sym"
    rom_path.write_bytes(rom_buf)
    asm_path.write_text(asm_src, encoding="utf-8")
    proc = subprocess.run(
        [
            ASAR_BIN,
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"--symbols-path={sym_path}",
            str(asm_path),
            str(rom_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"asar failed for {name}:\n{proc.stdout}\n{proc.stderr}")
    labels: dict[str, int] = {}
    for bank, offset, lname in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z0-9_.:]+)$",
        sym_path.read_text(encoding="utf-8"),
        re.M,
    ):
        labels[lname] = (int(bank, 16) << 16) | int(offset, 16)
    return rom_path.read_bytes(), labels


def _run_call(f: Fixture, addr: int, *, db: int = 0x02, max_steps: int = 20000) -> int:
    p = f.cpu
    p.k = (addr >> 16) & 0xFF
    p.pc = addr & 0xFFFF
    p.a = 0
    p.x = 0
    p.y = 0
    p.db = db
    p.dp = 0x0000
    p.e = False
    p.mf = True
    p.xf = True
    p.c = False
    initial_sp = p.sp
    for b in (p.k, 0x6F, 0xFF):
        f.put(p.sp, b)
        p.sp -= 1
    target_k = (addr >> 16) & 0xFF
    for steps in range(1, max_steps + 1):
        if p.pc == 0x7000 and p.k == target_k:
            assert p.sp == initial_sp, f"Stack imbalance: sp={p.sp:04X} vs {initial_sp:04X}"
            assert not f.bad_writes, f"Bad ROM/IO writes: {f.bad_writes}"
            return steps
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction limit at ${p.k:02X}:{p.pc:04X}")


# Vanilla entrance table fixtures matching real Oracle ROM rows:
# (row_index, map_id, cell_offset, ent_id)
ENTRANCE_ROWS = (
    (7, 0x001E, 0x0164, 0x25),   # D4 Zora Temple
    (8, 0x004B, 0x0254, 0x37),   # Fortress of Secrets
    (11, 0x002F, 0x02A8, 0x15),  # D2 Tail Palace
    (16, 0x00A6, 0x046A, 0x0C),  # Shrine of Courage L
    (122, 0x00A6, 0x046C, 0x0C), # Shrine of Courage R
    (41, 0x0063, 0x035E, 0x33),  # DW Windmill
    (52, 0x00B0, 0x0AAA, 0x09),  # Shrine of Power Mid
    (53, 0x00B0, 0x088E, 0x0B),  # Shrine of Power W
    (59, 0x0023, 0x11DA, 0x43),  # Wayward Tavern Back Door
    (70, 0x00B0, 0x023A, 0x05),  # Shrine of Power N-W
    (71, 0x00B0, 0x0240, 0x03),  # Shrine of Power N-E
    (87, 0x0057, 0x07AE, 0x24),  # Final Boss / Pyramid
    (98, 0x0087, 0x071E, 0x29),  # D8 Windward Spire
    (111, 0x0070, 0x0340, 0x6A), # DW $70 recessed cave
    (128, 0x0091, 0x0434, 0x81), # Shrine of Wisdom
    (99, 0x0036, 0x0EA0, 0x27),  # D6 Goron Mines
)

# Real Tile16 4-quadrant definitions (TL, TR, BL, BR) from Oracle ROM:
TILE16_DEFS = {
    # D2 Tail Palace
    0x0A81: (0x0112, 0x0112, 0x0112, 0x0112),  # DOOR[37]
    # D4 Zora Temple
    0x057F: (0x0141, 0x0141, 0x0163, 0x0163),  # DOOR[39]
    # D6 Goron Mines
    0x0BD8: (0x0164, 0x0164, 0x0174, 0x0174),  # DOOR[46]
    0x0BE4: (0x0163, 0x0162, 0x0173, 0x0172),  # DOOR[40]
    # D8 Windward Spire
    0x07FD: (0x01AB, 0x00C9, 0x01AC, 0x01AD),
    0x0EFF: (0x00C9, 0x01AB, 0x01AD, 0x01AE),
    # Shrine of Wisdom
    0x07CD: (0x0036, 0x0036, 0x00C5, 0x00C5),  # DOOR[49]
    0x07CE: (0x0036, 0x0163, 0x00C5, 0x00C4),  # DOOR[1]
    # Shrine of Power cave arches & mid temple
    0x0FF6: (0x00F4, 0x00DD, 0x00E9, 0x00EA),  # DOOR[50]
    0x0FF7: (0x00DF, 0x00DF, 0x00F5, 0x00F5),  # DOOR[7]
    0x0FF8: (0x00DD, 0x00F4, 0x00EA, 0x00E9),
    0x0FD1: (0x00F9, 0x00FA, 0x00C5, 0x00C4),  # DOOR[1]
    0x0FD2: (0x00FA, 0x00F9, 0x00E2, 0x00EE),  # DOOR[8]
    0x0FD3: (0x00FC, 0x00D1, 0x00CB, 0x00CB),
    # Shrine of Courage
    0x0FA7: (0x00FA, 0x00FC, 0x0114, 0x0115),  # DOOR[3]
    0x0FA8: (0x00FC, 0x00FA, 0x0115, 0x0114),  # DOOR[4]
    0x0FA5: (0x00F5, 0x00F6, 0x00F8, 0x00F9),
    # Fortress of Secrets
    0x018C: (0x0163, 0x0163, 0x0163, 0x0163),  # DOOR[39]
    # Pyramid
    0x0E41: (0x00F1, 0x00F1, 0x00F5, 0x00F5),  # DOOR[7]
    # DW Windmill
    0x0FE5: (0x0135, 0x01B8, 0x0138, 0x0139),
    0x0FE6: (0x01B9, 0x01BC, 0x01A4, 0x01A4),  # DOOR[51]
    0x0FE7: (0x0131, 0x01A1, 0x0131, 0x0131),  # DOOR[36]
    0x0FE8: (0x01B9, 0x0188, 0x01A4, 0x01A4),  # DOOR[51]
    0x0FE9: (0x018B, 0x0132, 0x0139, 0x0138),  # DOOR[52]
    # DW $70 recessed cave
    0x0E19: (0x0144, 0x0144, 0x0154, 0x0154),
    0x0E1A: (0x0144, 0x0145, 0x0154, 0x0155),
    # Wayward Tavern back door
    0x05D3: (0x00DD, 0x00DD, 0x00D5, 0x00D5),
    0x05D4: (0x00DD, 0x00DD, 0x00D5, 0x00D5),
    # Closed wooden house door & castle door
    0x00FB: (0x00E8, 0x00E9, 0x00F8, 0x00F9),
    0x00FC: (0x40E9, 0x00E8, 0x00FA, 0x00F8),
    0x0467: (0x0168, 0x0169, 0x0158, 0x0159),
    0x0468: (0x4169, 0x0168, 0x0159, 0x0158),
}


@unittest.skipUnless(ASAR_BIN and LAKESNES_DIR.is_dir(), "Asar and LakeSnes sources required")
class TestDungeonDoorways(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory()
        tmp_dir = Path(cls._tmp.name)
        buf = bytearray(0x400000)

        def put_bytes(snes: int, raw: bytes) -> None:
            pc = snes_to_pc(snes)
            buf[pc:pc + len(raw)] = raw

        def put_u16(snes: int, val: int) -> None:
            pc = snes_to_pc(snes)
            buf[pc] = val & 0xFF
            buf[pc + 1] = (val >> 8) & 0xFF

        # Seed OverworldDoor_ExitOpen preimages asserted by entrances.asm
        put_bytes(0x02EEF7, bytes.fromhex("A9A40D9F00207E"))
        put_bytes(0x02EF1A, bytes.fromhex("9F02207E"))
        put_bytes(0x02EF26, bytes.fromhex("9C9606"))

        # Clear all 129 entrance table rows, then seed our real Oracle rows
        for i in range(129):
            put_u16(0x1BB96F + i * 2, 0xFFFF)
            put_u16(0x1BBA71 + i * 2, 0xFFFF)
            buf[snes_to_pc(0x1BBB73 + i)] = 0xFF
        for row, mp, pos, eid in ENTRANCE_ROWS:
            put_u16(0x1BB96F + row * 2, mp)
            put_u16(0x1BBA71 + row * 2, pos)
            buf[snes_to_pc(0x1BBB73 + row)] = eid

        # Seed Tile16 definitions at $3D8000
        for tid, ws in TILE16_DEFS.items():
            for q, w in enumerate(ws):
                put_u16(0x3D8000 + tid * 8 + q * 2, w)

        asm_src = f"""
lorom
!SPECIAL_OVERWORLD_NATIVE = 0
!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 0
!ENABLE_SKY_OVERWORLD_ROUTE = 1
!ENABLE_HORSE_FORM = 0

org $368000
Overworld_DrawMap16_Persist:
  STA.l $7E2000, X
  PHA : SEP #$20 : LDA.l $7F1200 : INC A : STA.l $7F1200 : REP #$20 : PLA
  RTL
org $1BC983
  RTL
org $0EDD40
  RTL
org $0FFDAA
  RTL

org $358000
incsrc "{ROOT}/Overworld/entrances.asm"
"""
        cls.rom, cls.labels = _assemble(tmp_dir, "doorways", buf, asm_src)
        cls.lib = _compile_cpu(tmp_dir)
        cls.entry = cls.labels["Overworld_UseEntranceEntry"]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _run_probe(
        self,
        *,
        area: int,
        x: int,
        y: int,
        facing: int,
        dpad: int,
        tiles: dict[int, int],
        origin_y: int = 0x0000,
        origin_x: int = 0x0000,
        large: bool = True,
        game_state: int = 0x02,
        module: int = 0x09,
        dash: int = 0x00,
    ) -> Fixture:
        f = Fixture(self.lib, self.rom, self.labels)
        f.put(0x7E0010, module)
        f.put(0x7E0372, dash)
        f.word(0x7E040A, area)
        f.word(0x7E0708, origin_y)
        f.word(0x7E070A, 0x03F0 if large else 0x01F0)
        f.word(0x7E070C, origin_x // 8)
        f.word(0x7E070E, 0x007E if large else 0x003E)
        f.word(0x7E0020, y)
        f.word(0x7E0022, x)
        f.put(0x7E002F, facing)
        f.put(0x7E00F0, dpad)
        f.put(0x7EF3C5, game_state)
        for cell, t16 in tiles.items():
            f.word(0x7E2000 + cell, t16)
        _run_call(f, self.entry)
        return f

    def test_non_up_facing_blocks_proximity_brush_across_dungeons_and_shrines(self) -> None:
        cases = [
            # (name, area, large, cx, cy, t_y, t_y2, exp_ent)
            ("D2 Tail Palace", 0x2F, False, 20, 5, 0x0A81, 0x0A81, 0x15),
            ("D4 Zora Temple", 0x1E, True, 50, 2, 0x057F, 0x057F, 0x25),
            ("D6 Goron Mines", 0x36, True, 16, 29, 0x0BD8, 0x0BE4, 0x27),
            ("Shrine of Wisdom", 0x91, False, 26, 8, 0x07CD, 0x07CE, 0x81),
            ("Shrine of Power N-E", 0xB0, True, 32, 4, 0x0FF6, 0x0FF7, 0x03),
            ("Shrine of Power N-W", 0xB0, True, 29, 4, 0x0FF6, 0x0FF7, 0x05),
            ("Shrine of Power Mid", 0xB0, True, 21, 21, 0x0FD1, 0x0FD2, 0x09),
            ("Shrine of Power W", 0xB0, True, 7, 17, 0x0FF6, 0x0FF7, 0x0B),
            ("Shrine of Courage L", 0xA6, True, 53, 8, 0x0FA7, 0x0FA8, 0x0C),
            ("Shrine of Courage R", 0xA6, True, 54, 8, 0x0FA8, 0x0FA5, 0x0C),
            ("Fortress of Secrets", 0x4B, True, 42, 4, 0x018C, 0x018C, 0x37),
            ("Pyramid", 0x57, False, 23, 15, 0x0E41, 0x0E41, 0x24),
            ("DW Windmill", 0x63, True, 47, 6, 0x0FE6, 0x0FE7, 0x33),
        ]
        for name, area, large, cx, cy, t_y, t_y2, exp_ent in cases:
            cell = (cy << 7) | (cx << 1)
            tiles = {cell: t_y, cell + 2: t_y2}
            x = cx * 16
            y = cy * 16 + 8  # front threshold where (y + 7) >> 4 == cy
            for fname, fval, dpad in (
                ("DOWN", 0x02, 0x04),
                ("LEFT", 0x04, 0x02),
                ("RIGHT", 0x06, 0x01),
                ("RIGHT_NEUTRAL", 0x06, 0x00),
            ):
                f = self._run_probe(area=area, x=x, y=y, facing=fval, dpad=dpad, tiles=tiles, large=large)
                self.assertEqual(
                    f.get(0x7E0010), 0x09,
                    f"{name} must NOT trigger when facing {fname} ($2F=${fval:02X}, $F0=${dpad:02X})",
                )
            f = self._run_probe(area=area, x=x, y=y, facing=0x00, dpad=0x08, tiles=tiles, large=large)
            self.assertEqual(f.get(0x7E0010), 0x0F, f"{name} must enter when facing UP + holding Up")
            self.assertEqual(f.get(0x7E010E), exp_ent, f"{name} resolved wrong entrance ID")

    def test_sword_charge_strafe_and_idle_standing_refused_in_live_overworld(self) -> None:
        cell = 0x0434  # Shrine of Wisdom (26, 8)
        tiles = {cell: 0x07CD, cell + 2: 0x07CE}
        # In live overworld ($10 == $09): standing neutral ($00), swinging sword ($80),
        # or strafing Left/Right/Down without Up MUST NOT suck Link into doorway!
        for bad_dpad in (0x00, 0x80, 0x40, 0x01, 0x02, 0x04, 0x05, 0x06, 0x81, 0x82, 0x84):
            f = self._run_probe(
                area=0x91, x=26 * 16, y=8 * 16 + 8, facing=0x00, dpad=bad_dpad, tiles=tiles, large=False
            )
            self.assertEqual(f.get(0x7E0010), 0x09, f"Live $F0=${bad_dpad:02X} without Up must NOT enter")
        # Holding Up (straight or diagonal) enters cleanly!
        for ok_dpad in (0x08, 0x09, 0x0A, 0x88):
            f = self._run_probe(
                area=0x91, x=26 * 16, y=8 * 16 + 8, facing=0x00, dpad=ok_dpad, tiles=tiles, large=False
            )
            self.assertEqual(f.get(0x7E0010), 0x0F, f"Live Up $F0=${ok_dpad:02X} must enter")
        # Pegasus Boots dashing UP ($0372 != 0) with neutral D-pad enters cleanly!
        f = self._run_probe(
            area=0x91, x=26 * 16, y=8 * 16 + 8, facing=0x00, dpad=0x00, dash=0x01, tiles=tiles, large=False
        )
        self.assertEqual(f.get(0x7E0010), 0x0F, "Pegasus Boots dash UP with neutral D-pad must enter")
        # Standalone zeroed-RAM harness ($10 == $00) still accepts neutral $F0=$00
        f = self._run_probe(
            area=0x91, x=26 * 16, y=8 * 16 + 8, facing=0x00, dpad=0x00, module=0x00, tiles=tiles, large=False
        )
        self.assertEqual(f.get(0x7E0010), 0x0F)

        # Also verify closed wooden house door & castle door refuse sword-charge strafe / idle!
        door_tiles = {0x0200: 0x00FB, 0x0202: 0x00FC}
        for bad_dpad in (0x00, 0x80, 0x01):
            f = self._run_probe(area=0x23, x=0, y=4 * 16 + 8, facing=0x00, dpad=bad_dpad, tiles=door_tiles)
            self.assertEqual(f.get(0x7F1200), 0, f"House door must NOT open for $F0=${bad_dpad:02X}")
        f = self._run_probe(area=0x23, x=0, y=4 * 16 + 8, facing=0x00, dpad=0x08, tiles=door_tiles)
        self.assertEqual(f.get(0x7F1200), 1, "Walking UP into house door must open it")

        castle_tiles = {0x0200: 0x0467, 0x0202: 0x0468}
        for bad_dpad in (0x00, 0x80, 0x02):
            f = self._run_probe(area=0x0B, x=0, y=4 * 16 + 8, facing=0x00, dpad=bad_dpad, tiles=castle_tiles)
            self.assertEqual(f.get(0x7E0011), 0x00, f"Castle door must NOT open for $F0=${bad_dpad:02X}")
        f = self._run_probe(area=0x0B, x=0, y=4 * 16 + 8, facing=0x00, dpad=0x08, tiles=castle_tiles)
        self.assertEqual(f.get(0x7E0011), 0x0C, "Walking UP into castle door must trigger opening submode $0C")

    def test_d8_windward_spire_requires_recessed_arch_depth(self) -> None:
        tiles = {0x071E: 0x07FD, 0x0720: 0x0EFF}
        # Standing outside in row 15 ($E8..$E3) must NOT trigger early
        for early_y in (0x00E8, 0x00E6, 0x00E3):
            f = self._run_probe(
                area=0x87, x=15 * 16 + 8, y=early_y, facing=0x00, dpad=0x08, tiles=tiles, large=False
            )
            self.assertEqual(f.get(0x7E0010), 0x09, f"D8 must refuse early front-edge y=${early_y:04X}")
        # Stepped INTO row 14 walkable arch ($E2..$D9) enters cleanly
        for deep_y in (0x00E2, 0x00E0, 0x00D9):
            f = self._run_probe(
                area=0x87, x=15 * 16 + 8, y=deep_y, facing=0x00, dpad=0x08, tiles=tiles, large=False
            )
            self.assertEqual(f.get(0x7E0010), 0x0F, f"D8 must enter inside recessed arch y=${deep_y:04X}")
            self.assertEqual(f.get(0x7E010E), 0x29)
        # Non-zero screen origin $0708=$0200 uses relative depth ($20 - $0708)
        f = self._run_probe(
            area=0x87, x=15 * 16 + 8, y=0x02E3, origin_y=0x0200, facing=0x00, dpad=0x08, tiles=tiles, large=False
        )
        self.assertEqual(f.get(0x7E0010), 0x09)
        f = self._run_probe(
            area=0x87, x=15 * 16 + 8, y=0x02E2, origin_y=0x0200, facing=0x00, dpad=0x08, tiles=tiles, large=False
        )
        self.assertEqual(f.get(0x7E0010), 0x0F)
        self.assertEqual(f.get(0x7E010E), 0x29)

    def test_shrine_of_power_center_cave_arch_and_mid_right_stair(self) -> None:
        # Three $FF6/$FF7/$FF8 cave arches on $B0
        for cx, cy, exp_ent in ((32, 4, 0x03), (29, 4, 0x05), (7, 17, 0x0B)):
            cell = (cy << 7) | (cx << 1)
            tiles = {cell: 0x0FF6, cell + 2: 0x0FF7, cell + 4: 0x0FF8}
            # Dead center under black arch $FF7 (col=cx+1, low nibble 0..7) enters!
            for nib in (0, 4, 7):
                f = self._run_probe(
                    area=0xB0, x=(cx + 1) * 16 + nib, y=cy * 16 + 8, facing=0x00, dpad=0x08, tiles=tiles
                )
                self.assertEqual(f.get(0x7E0010), 0x0F, f"Power $B0 Ent ${exp_ent:02X} center nib={nib} must enter")
                self.assertEqual(f.get(0x7E010E), exp_ent)
            # Outer east rock wall (col=cx+1, low nibble >= 8) refused!
            f = self._run_probe(
                area=0xB0, x=(cx + 1) * 16 + 8, y=cy * 16 + 8, facing=0x00, dpad=0x08, tiles=tiles
            )
            self.assertEqual(f.get(0x7E0010), 0x09, f"Power $B0 Ent ${exp_ent:02X} outer east nib=8 must refuse")

        # Mid temple right stair half ($0AAC, Y+2=$FD3)
        mid_tiles = {0x0AAA: 0x0FD1, 0x0AAC: 0x0FD2, 0x0AAE: 0x0FD3}
        f = self._run_probe(area=0xB0, x=22 * 16 + 4, y=21 * 16 + 8, facing=0x00, dpad=0x08, tiles=mid_tiles)
        self.assertEqual(f.get(0x7E0010), 0x0F)
        self.assertEqual(f.get(0x7E010E), 0x09)
        f = self._run_probe(area=0xB0, x=22 * 16 + 8, y=21 * 16 + 8, facing=0x00, dpad=0x08, tiles=mid_tiles)
        self.assertEqual(f.get(0x7E0010), 0x09)

    def test_d4_wide_alcove_right_half_and_dw70_cave_enter_north_only(self) -> None:
        # D4 Zora Temple ($1E) right alcove half ($0166 -> normalized to $0164, Ent $25)
        d4_tiles = {0x0164: 0x057F, 0x0166: 0x057F, 0x0168: 0x057F}
        f = self._run_probe(area=0x1E, x=51 * 16, y=2 * 16 + 8, facing=0x00, dpad=0x08, tiles=d4_tiles)
        self.assertEqual(f.get(0x7E0010), 0x0F)
        self.assertEqual(f.get(0x7E010E), 0x25)
        f = self._run_probe(area=0x1E, x=51 * 16, y=2 * 16 + 8, facing=0x04, dpad=0x02, tiles=d4_tiles)
        self.assertEqual(f.get(0x7E0010), 0x09)

        # DW $70 recessed cave ($E19/$E1A -> $0154/$0155)
        dw70_tiles = {0x0340: 0x0E19, 0x0342: 0x0E1A}
        f = self._run_probe(area=0x70, x=32 * 16, y=6 * 16 + 8, facing=0x00, dpad=0x08, tiles=dw70_tiles)
        self.assertEqual(f.get(0x7E0010), 0x0F)
        self.assertEqual(f.get(0x7E010E), 0x6A)
        f = self._run_probe(area=0x70, x=32 * 16, y=6 * 16 + 8, facing=0x06, dpad=0x01, tiles=dw70_tiles)
        self.assertEqual(f.get(0x7E0010), 0x09)

    def test_wayward_tavern_back_door_south_facing_preserved(self) -> None:
        # Map $23, origin_y=$0800 -> local row 35 ($0230) is world y=$0A30; row 34 ($0220) is world y=$0A20
        tiles = {0x115A: 0x05D3, 0x115C: 0x05D4, 0x11DA: 0x05D3, 0x11DC: 0x05D4}
        # Direct cell $11DA & neighbor $11DC facing DOWN + Down held (or Pegasus dash Down)
        for x, y, dpad, dash, mod in (
            (45 * 16, 0x0A30, 0x04, 0x00, 0x09),
            (45 * 16, 0x0A30, 0x00, 0x01, 0x09),  # Pegasus dash Down
            (45 * 16, 0x0A30, 0x00, 0x00, 0x00),  # zeroed-RAM harness
            (46 * 16, 0x0A30, 0x04, 0x00, 0x09),
            (45 * 16, 0x0A20, 0x04, 0x00, 0x09),  # seamless north-eave $115A at $0A20
            (46 * 16, 0x0A24, 0x04, 0x00, 0x09),  # seamless north-eave $115C at $0A24
        ):
            f = self._run_probe(
                area=0x23, x=x, y=y, origin_y=0x0800, facing=0x02, dpad=dpad, dash=dash, module=mod, tiles=tiles
            )
            self.assertEqual(f.get(0x7E0010), 0x0F, f"Tavern back ({x:04X},{y:04X}) dpad=${dpad:02X} must enter")
            self.assertEqual(f.get(0x7E010E), 0x43)

        # Standing neutral in live OW ($09), or facing DOWN holding UP, or UP/LEFT/RIGHT, or north of $0A20 -> refused!
        for x, y, facing, dpad in (
            (45 * 16, 0x0A30, 0x02, 0x00),  # live standing still
            (45 * 16, 0x0A30, 0x02, 0x80),  # live sword swing
            (45 * 16, 0x0A30, 0x02, 0x08),  # facing Down, holding Up
            (45 * 16, 0x0A30, 0x00, 0x08),  # facing Up
            (45 * 16, 0x0A30, 0x04, 0x02),  # facing Left
            (45 * 16, 0x0A30, 0x06, 0x01),  # facing Right
            (45 * 16, 0x0A1F, 0x02, 0x04),  # north of $0A20 threshold
        ):
            f = self._run_probe(
                area=0x23, x=x, y=y, origin_y=0x0800, facing=facing, dpad=dpad, tiles=tiles
            )
            self.assertEqual(
                f.get(0x7E0010), 0x09,
                f"Tavern back ({x:04X},{y:04X}) facing=${facing:02X} dpad=${dpad:02X} must refuse",
            )


if __name__ == "__main__":
    unittest.main()
