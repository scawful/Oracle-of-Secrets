#!/usr/bin/env python3
"""Schema, collision, and compiled 65816 CPU tests for Q-OOS-21 Abyss GBC wall profiles.

Verifies:
1. gen_wall_profiles.py build --check passes with zero drift.
2. All 46 Abyss-exclusive rooms in Dungeons/Data/abyss_gbc/styles.json bind to
   their floor-matched words-only single-course GBC wall profile (profiles 4-7),
   while all 7 shared Kalyxo/Abyss rooms ($102/$107/$10E/$114/$11E/$122/$124)
   and Light World Archery ($111) stay unbound (profile 0 = vanilla SNES walls).
3. Zero corrupted Abyss GBC chars ($091 unremapped, $093/$09E corner-corrupted)
   appear in top walls or corners ($001/$002/$061/$062/$100-$107).
4. Collision invariants hold for straight walls, corners, lower-wall ledges
   ($28/$2A), diagonal slopes ($18/$10), and outer-trimmed wall decor ($3C15).
5. Compiled 65816 execution (Asar + LakeSnes CPU) of the real
   Dungeons/wall_profile_selector.asm + wall_profiles.asm confirms exact
   WallSel_Buffer ($7E1EA9) word delivery, vanilla fallback on shared rooms,
   and untouched header blockset/palette ($0AA2/$0AB6) on words-only profiles.
"""
from __future__ import annotations

import ctypes as C
import json
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))
sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402
import gen_abyss_gbc as gag  # noqa: E402
import gen_wall_profiles as gw  # noqa: E402

PROFILES_DIR = ROOT / "Dungeons" / "Data" / "wall_profiles"
ABYSS_STYLES = ROOT / "Dungeons" / "Data" / "abyss_gbc" / "styles.json"
LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]

SHARED_KALYXO_ABYSS_ROOMS = (0x102, 0x107, 0x10E, 0x114, 0x11E, 0x122, 0x124)
ABYSS_PROFILE_NAMES = (
    "abyss_gbc_ee_p5",
    "abyss_gbc_ee_p3",
    "abyss_gbc_ec_p5",
    "abyss_gbc_ec_p3",
)
CORRUPTED_ABYSS_CHARS = {0x091, 0x093, 0x09E}
WALLSEL_BUFFER = 0x7E1EA9
WALLSEL_BUFFER_OFFSET = 0x8357


def _find_lakesnes() -> Path:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    raise RuntimeError("LakeSnes checkout not found (set LAKESNES_DIR)")


def _build_cpu_lib(temp_dir: Path) -> C.CDLL:
    lakesnes = _find_lakesnes()
    dll = temp_dir / "cpu.dylib"
    subprocess.run(
        [
            "cc", "-shared", "-fPIC", "-O2",
            str(lakesnes / "snes" / "cpu.c"),
            str(lakesnes / "snes" / "statehandler.c"),
            "-o", str(dll),
        ],
        check=True,
    )
    lib = C.CDLL(str(dll))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def _assemble_wall_selector(folder: Path) -> tuple[bytes, dict[str, int], int]:
    """Compile the real Dungeons/wall_profile_selector.asm into a 4.5MB LoROM image."""
    folder.mkdir(parents=True, exist_ok=True)
    # 5MB LoROM image so Bank $44 ($44E000 -> PC $226000) and $0E97F5 are mapped cleanly
    image = bytearray(b"\xFF" * 0x400000)

    # Seed vanilla bytes checked by wall_profile_selector.asm assertions
    image[_snes_to_pc(0x018979):_snes_to_pc(0x01897E)] = bytes([0xBF, 0x00, 0x80, 0x01, 0xAA])
    image[_snes_to_pc(0x0189AE):_snes_to_pc(0x0189B3)] = bytes([0xBF, 0xF0, 0x83, 0x01, 0xAA])
    image[_snes_to_pc(0x00E636):_snes_to_pc(0x00E63C)] = bytes([0xA6, 0x0F, 0xE0, 0x04, 0xB0, 0xF7])
    struct.pack_into("<I", image, _snes_to_pc(0x00DF1A), 0x02857EA9)
    image[_snes_to_pc(0x0E97F5):_snes_to_pc(0x0E97FD)] = bytes([0xBF, 0x19, 0x97, 0x0E, 0x9F, 0xC0, 0xFE, 0x7E])
    image[_snes_to_pc(0x01B641):_snes_to_pc(0x01B647)] = bytes([0xC8, 0xB7, 0x0D, 0x8D, 0xA2, 0x0A])

    # Seed recognizable vanilla offsets at $01:8000 (sub1) and $01:83F0 (sub2)
    for obj in range(0xF8):
        struct.pack_into("<H", image, _snes_to_pc(0x018000) + obj * 2, 0x1000 + obj * 2)
    for obj in range(0x40):
        struct.pack_into("<H", image, _snes_to_pc(0x0183F0) + obj * 2, 0x2000 + obj * 2)

    rom_path = folder / "wallsel_fixture.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "harness.asm"
    asm_path.write_text(
        "lorom\n"
        f"WallSel_Buffer = ${WALLSEL_BUFFER:06X}\n"
        "Dungeon_LoadCustomTileAttr = $0E9430\n"
        "org $0E9430 : RTL\n"
        f'incsrc "{(ROOT / "Dungeons" / "wall_profile_selector.asm").as_posix()}"\n',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "asar",
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"-I{ROOT.as_posix()}",
            str(asm_path),
            str(rom_path),
        ],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    m = re.search(r"End of wall_profile_selector\.asm\s+([0-9A-Fa-f]+)", proc.stdout)
    assert m is not None, f"Missing end address print:\n{proc.stdout}"
    end_addr = int(m.group(1), 16)
    labels = {
        mm[3]: int(mm[1] + mm[2], 16)
        for mm in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            rom_path.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return rom_path.read_bytes(), labels, end_addr


def _run_call(
    f: Fixture,
    entry: str,
    *,
    m8: bool = False,
    x8: bool = False,
    a: int = 0,
    x: int = 0,
    y: int = 0,
) -> None:
    c = f.cpu
    addr = f.addr(entry)
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    c.mf = m8
    c.xf = x8
    c.db = 0x00
    c.dp = 0x0000
    c.a = a & (0xFF if m8 else 0xFFFF)
    c.x = x & (0xFF if x8 else 0xFFFF)
    c.y = y & (0xFF if x8 else 0xFFFF)
    ret_addr = (addr & 0xFF0000) | 0x7000
    f.put(sp, addr >> 16)
    f.put(sp - 1, 0x6F)
    f.put(sp - 2, 0xFF)
    c.sp -= 3
    for _ in range(50000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack in {entry}: {c.sp:#x} != {sp:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction ceiling reached in {entry}")


class AbyssGbcWallProfileDataTests(unittest.TestCase):
    def test_gen_wall_profiles_build_check_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ROOT / "Scripts/Generate/gen_wall_profiles.py"), "build", "--check"],
            cwd=ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr or proc.stdout)

    def test_exact_phase1_and_phase2_abyss_partition_and_wsr1_safety(self) -> None:
        _, _, styles, _ = gag.load_styles_config(ABYSS_STYLES)
        all_styled = {r for s in styles for r in s["rooms"] + s["more_rooms"]}
        expected_abyss_excl = all_styled - set(SHARED_KALYXO_ABYSS_ROOMS)
        self.assertEqual(len(expected_abyss_excl), 46)

        profiles, groups, room_profile, _ = gw.load_config()
        by_name = {p["name"]: p for p in profiles}
        abyss_pids = {by_name[name]["id"] for name in ABYSS_PROFILE_NAMES}
        abyss_shared = dict(gw.load_abyss_only_rooms(profiles, groups))

        # All 4 Abyss profiles are words-only (no kit route)
        for name in ABYSS_PROFILE_NAMES:
            self.assertNotIn("kit", by_name[name], f"{name} must be words-only (no kit)")

        # Every unconditional entry in WallSel_RoomProfile stays strictly <= profile_count (WSR1/Yaze safe)
        self.assertTrue(all(0 <= pid <= len(profiles) for pid in room_profile))

        # Every Abyss-exclusive room resolves unconditionally to profiles 4..7
        bound_abyss = {r for r, pid in enumerate(room_profile) if pid in abyss_pids}
        self.assertEqual(bound_abyss, expected_abyss_excl)

        # Every shared Kalyxo/Abyss room stays 0 in WallSel_RoomProfile (LW/WSR1 vanilla)
        # and binds in WallSel_AbyssOnlyRooms ($7EF3CA == $40) to its floor-matched profile
        self.assertEqual(set(abyss_shared.keys()), set(SHARED_KALYXO_ABYSS_ROOMS))
        for r in SHARED_KALYXO_ABYSS_ROOMS:
            self.assertEqual(
                room_profile[r], 0,
                f"Shared LW/Abyss room ${r:03X} must stay 0 in WallSel_RoomProfile for LW/WSR1 safety",
            )
            self.assertIn(abyss_shared[r], abyss_pids)

        # Unconditional + Abyss-gated cover 100% of all 53 styled Eon Abyss rooms
        self.assertEqual(bound_abyss | set(abyss_shared.keys()), all_styled)
        self.assertEqual(room_profile[0x111], 0)
        self.assertNotIn(0x111, abyss_shared)

    def test_pure_gbc_glyphs_and_collision_invariants(self) -> None:
        for name in ABYSS_PROFILE_NAMES:
            doc = json.loads((PROFILES_DIR / f"{name}.words.json").read_text())
            cls = {int(k, 16): [int(v.lstrip("$"), 16) for v in ws] for k, ws in doc["classes"].items()}
            self.assertEqual(set(cls.keys()), set(gw.CLASSES), f"{name} missing selector classes")

            # Top straight walls and top corners must never use corrupted chars $091/$093/$09E
            for oid in (0x001, 0x002, 0x061, 0x062) + tuple(range(0x100, 0x108)):
                chars = {w & 0x3FF for w in cls[oid]}
                self.assertEqual(
                    chars & CORRUPTED_ABYSS_CHARS, set(),
                    f"{name} obj ${oid:03X} uses corrupted Abyss GBC char(s): {chars & CORRUPTED_ABYSS_CHARS}",
                )

            # Straight walls: outer cap = $3C15 (void), inner strip = expected floor char family
            is_ec = "_ec_" in name
            pal_bits = 0x1400 if name.endswith("_p5") else 0x0C00
            fl_chars = {0x0EC, 0x0ED, 0x0FC, 0x0FD} if is_ec else {0x0EE, 0x0EF, 0x0FE, 0x0FF}

            # North $001: r0=$3C15, r1=$0890, r2=$0896, r3=floor
            self.assertEqual((cls[0x001][0], cls[0x001][4]), (0x3C15, 0x3C15))
            self.assertEqual((cls[0x001][1], cls[0x001][5]), (0x0890, 0x0890))
            self.assertEqual((cls[0x001][2], cls[0x001][6]), (0x0896, 0x0896))
            for k in (3, 7):
                self.assertEqual(cls[0x001][k] & 0x1C00, pal_bits)
                self.assertIn(cls[0x001][k] & 0x3FF, fl_chars)

            # South $002: r0=floor, r1=$8896, r2=$8890, r3=$3C15
            self.assertEqual((cls[0x002][3], cls[0x002][7]), (0x3C15, 0x3C15))
            self.assertEqual((cls[0x002][1], cls[0x002][5]), (0x8896, 0x8896))
            self.assertEqual((cls[0x002][2], cls[0x002][6]), (0x8890, 0x8890))
            for k in (0, 4):
                self.assertIn(cls[0x002][k] & 0x3FF, fl_chars)

            # Lower walls preserve jumpable ledges ($050/$051 tt=$28, $043/$053 tt=$2A)
            self.assertEqual((cls[0x003][0] & 0x3FF, cls[0x003][4] & 0x3FF), (0x050, 0x051))
            self.assertEqual((cls[0x004][3] & 0x3FF, cls[0x004][7] & 0x3FF), (0x050, 0x051))
            self.assertEqual((cls[0x063][0] & 0x3FF, cls[0x063][4] & 0x3FF), (0x043, 0x053))
            self.assertEqual((cls[0x064][3] & 0x3FF, cls[0x064][7] & 0x3FF), (0x043, 0x053))

            # Diagonals preserve slope chars $09A ($18) and $09B ($10), and replace $0AB with floor
            for oid in range(0x009, 0x015):
                chars = {w & 0x3FF for w in cls[oid]}
                self.assertIn(0x09A, chars)
                self.assertIn(0x09B, chars)
                self.assertNotIn(0x0AB, chars)
                self.assertTrue(chars & fl_chars)

            # Outer decor edge trimmed to solid void $3C15
            for k in (0, 3, 6, 9):
                self.assertEqual(cls[0x03A][k], 0x3C15)
            for k in (2, 5, 8, 11):
                self.assertEqual(cls[0x03B][k], 0x3C15)
            for oid in (0x076, 0x081):
                for k in (0, 1, 2, 3):
                    self.assertEqual(cls[oid][k], 0x3C15)
            for oid in (0x077, 0x082):
                for k in (8, 9, 10, 11):
                    self.assertEqual(cls[oid][k], 0x3C15)


class AbyssGbcWallProfileCompiledCpuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory(prefix="oos-wallsel-cpu-")
        td = Path(cls._td.name)
        cls.lib = _build_cpu_lib(td)
        cls.rom, cls.labels, cls.end_addr = _assemble_wall_selector(td)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _fixture(self) -> Fixture:
        return Fixture(self.lib, self.rom, self.labels)

    def _read_buffer(self, f: Fixture, n_words: int) -> list[int]:
        out = []
        for i in range(n_words):
            lo = f.ram[(WALLSEL_BUFFER & 0x1FFFF) + i * 2]
            hi = f.ram[(WALLSEL_BUFFER & 0x1FFFF) + i * 2 + 1]
            out.append(lo | (hi << 8))
        return out

    def test_bank44_slot_headroom(self) -> None:
        self.assertLessEqual(
            self.end_addr, 0x450000,
            f"wall_profile_selector.asm overflowed $44E000-$44FFFF: end=${self.end_addr:06X}",
        )

    def test_all_four_abyss_profiles_deliver_exact_words_via_sub1_and_sub2(self) -> None:
        samples = [
            (0x00C, "abyss_gbc_ee_p5"),
            (0x000, "abyss_gbc_ee_p5"),
            (0x005, "abyss_gbc_ee_p5"),
            (0x014, "abyss_gbc_ee_p5"),
            (0x0D0, "abyss_gbc_ee_p5"),
            (0x02D, "abyss_gbc_ee_p3"),
            (0x03D, "abyss_gbc_ee_p3"),
            (0x116, "abyss_gbc_ee_p3"),
            (0x0C9, "abyss_gbc_ec_p5"),
            (0x00F, "abyss_gbc_ec_p5"),
            (0x00D, "abyss_gbc_ec_p5"),
            (0x01D, "abyss_gbc_ec_p3"),
        ]
        words_cache = {
            name: {
                int(k, 16): [int(v.lstrip("$"), 16) for v in ws]
                for k, ws in json.loads((PROFILES_DIR / f"{name}.words.json").read_text())["classes"].items()
            }
            for name in ABYSS_PROFILE_NAMES
        }

        f = self._fixture()
        try:
            for room, pname in samples:
                # Set current room $A0 (16-bit)
                f.ram[0xA0] = room & 0xFF
                f.ram[0xA1] = (room >> 8) & 0xFF
                expected_map = words_cache[pname]

                # Subtype 1: straight wall, lower wall, decor, diagonal
                for obj in (0x001, 0x002, 0x061, 0x062, 0x003, 0x03A, 0x076, 0x00D):
                    _run_call(f, "WallSel_Sub1", m8=False, x8=False, x=obj * 2)
                    self.assertEqual(
                        f.cpu.a, WALLSEL_BUFFER_OFFSET,
                        f"room ${room:03X} obj ${obj:03X} did not redirect to WallSel_Buffer",
                    )
                    got = self._read_buffer(f, len(expected_map[obj]))
                    self.assertEqual(got, expected_map[obj], f"room ${room:03X} obj ${obj:03X} word mismatch")

                # Subtype 2: concave & convex top corners + lower corner
                for obj in (0x100, 0x101, 0x102, 0x103, 0x104, 0x107, 0x108):
                    _run_call(f, "WallSel_Sub2", m8=False, x8=False, x=(obj - 0x100) * 2)
                    self.assertEqual(
                        f.cpu.a, WALLSEL_BUFFER_OFFSET,
                        f"room ${room:03X} obj ${obj:03X} did not redirect to WallSel_Buffer",
                    )
                    got = self._read_buffer(f, len(expected_map[obj]))
                    self.assertEqual(got, expected_map[obj], f"room ${room:03X} obj ${obj:03X} word mismatch")
        finally:
            f.close()

    def test_shared_kalyxo_abyss_rooms_world_gate_lw_vs_abyss(self) -> None:
        words_cache = {
            name: {
                int(k, 16): [int(v.lstrip("$"), 16) for v in ws]
                for k, ws in json.loads((PROFILES_DIR / f"{name}.words.json").read_text())["classes"].items()
            }
            for name in ABYSS_PROFILE_NAMES
        }
        shared_expected = [
            (0x102, "abyss_gbc_ec_p5"),
            (0x107, "abyss_gbc_ec_p5"),
            (0x122, "abyss_gbc_ee_p3"),
            (0x10E, "abyss_gbc_ee_p5"),
            (0x114, "abyss_gbc_ee_p5"),
            (0x11E, "abyss_gbc_ee_p5"),
            (0x124, "abyss_gbc_ee_p5"),
        ]
        f = self._fixture()
        try:
            # 1. Light World ($00) and Special OW ($80): ALL 7 shared rooms + LW rooms stay 100% vanilla
            for world in (0x00, 0x80):
                f.ram[0x0F3CA] = world
                for room in SHARED_KALYXO_ABYSS_ROOMS + (0x104, 0x111, 0x001, 0x0FF):
                    f.ram[0xA0] = room & 0xFF
                    f.ram[0xA1] = (room >> 8) & 0xFF
                    for obj in (0x001, 0x002, 0x061, 0x062, 0x03B, 0x076, 0x00D):
                        _run_call(f, "WallSel_Sub1", m8=False, x8=False, x=obj * 2)
                        self.assertEqual(
                            f.cpu.a, 0x1000 + obj * 2,
                            f"world=${world:02X} room ${room:03X} obj ${obj:03X} must return vanilla offset",
                        )
                    for obj in (0x100, 0x103, 0x104, 0x107):
                        _run_call(f, "WallSel_Sub2", m8=False, x8=False, x=(obj - 0x100) * 2)
                        self.assertEqual(
                            f.cpu.a, 0x2000 + (obj - 0x100) * 2,
                            f"world=${world:02X} room ${room:03X} obj ${obj:03X} must return vanilla offset",
                        )

            # 2. Eon Abyss ($7EF3CA == $40): ALL 7 shared rooms deliver exact simplified GBC wall words
            f.ram[0x0F3CA] = 0x40
            for room, pname in shared_expected:
                f.ram[0xA0] = room & 0xFF
                f.ram[0xA1] = (room >> 8) & 0xFF
                expected_map = words_cache[pname]
                for obj in (0x001, 0x002, 0x061, 0x062, 0x003, 0x03B, 0x076, 0x00D):
                    _run_call(f, "WallSel_Sub1", m8=False, x8=False, x=obj * 2)
                    self.assertEqual(
                        f.cpu.a, WALLSEL_BUFFER_OFFSET,
                        f"Abyss shared room ${room:03X} obj ${obj:03X} must redirect to WallSel_Buffer",
                    )
                    self.assertEqual(self._read_buffer(f, len(expected_map[obj])), expected_map[obj])
                for obj in (0x100, 0x103, 0x104, 0x107, 0x108):
                    _run_call(f, "WallSel_Sub2", m8=False, x8=False, x=(obj - 0x100) * 2)
                    self.assertEqual(
                        f.cpu.a, WALLSEL_BUFFER_OFFSET,
                        f"Abyss shared room ${room:03X} obj ${obj:03X} must redirect to WallSel_Buffer",
                    )
                    self.assertEqual(self._read_buffer(f, len(expected_map[obj])), expected_map[obj])

            # 3. Unstyled LW rooms (including relocated Archery $111) stay vanilla EVEN when $7EF3CA == $40
            for room in (0x104, 0x111, 0x001, 0x0FF):
                f.ram[0xA0] = room & 0xFF
                f.ram[0xA1] = (room >> 8) & 0xFF
                for obj in (0x001, 0x061):
                    _run_call(f, "WallSel_Sub1", m8=False, x8=False, x=obj * 2)
                    self.assertEqual(
                        f.cpu.a, 0x1000 + obj * 2,
                        f"Unstyled room ${room:03X} must stay vanilla even in Abyss",
                    )
                _run_call(f, "WallSel_Sub2", m8=False, x8=False, x=0)
                self.assertEqual(f.cpu.a, 0x2000)
        finally:
            f.close()

    def test_header_gfx_keeps_blockset_and_palette_for_words_only_abyss_profiles(self) -> None:
        f = self._fixture()
        try:
            # Point DP $0D/$0E/$0F at a dummy header in WRAM $7E:0800 where byte[2] = $0E (blockset 14)
            f.ram[0x0D] = 0x00
            f.ram[0x0E] = 0x08
            f.ram[0x0F] = 0x7E
            f.ram[0x0802] = 0x0E
            for room in (0x00C, 0x02D, 0x0C9, 0x01D, 0x102, 0x10E, 0x122):
                f.ram[0x0F3CA] = 0x40
                f.ram[0xA0] = room & 0xFF
                f.ram[0xA1] = (room >> 8) & 0xFF
                f.ram[0x0AA2] = 0x00
                f.ram[0x0AB6] = 0x06
                _run_call(f, "WallSel_HeaderGfx", m8=True, x8=False, y=1)
                self.assertEqual(f.ram[0x0AA2], 0x0E, f"room ${room:03X} should keep header blockset")
                self.assertEqual(f.ram[0x0AB6], 0x06, f"room ${room:03X} should keep header palette")
                self.assertEqual(f.cpu.y, 2, "Y must advance by 1 as vanilla")
        finally:
            f.close()

    def test_existing_glacia_profiles_exact_words_after_span_dedup(self) -> None:
        kits = {k["kit"]: k for k in gw.load_kits()}
        f = self._fixture()
        try:
            for room, pname, kname in (
                (0x0DB, "glacia_frozen_timber", "glacia_estate_timber"),
                (0x09E, "glacia_cave_art17", "glacia_cave_art17"),
            ):
                doc = json.loads((PROFILES_DIR / f"{pname}.words.json").read_text())
                cmap = kits[kname]["_cmap"]
                f.ram[0xA0] = room & 0xFF
                f.ram[0xA1] = (room >> 8) & 0xFF
                for obj_hex, raw_ws in doc["classes"].items():
                    obj = int(obj_hex, 16)
                    expected = [
                        ((int(v.lstrip("$"), 16) & ~0x3FF) | cmap.get(int(v.lstrip("$"), 16) & 0x3FF, int(v.lstrip("$"), 16) & 0x3FF))
                        for v in raw_ws
                    ]
                    if obj < 0x100:
                        _run_call(f, "WallSel_Sub1", m8=False, x8=False, x=obj * 2)
                    else:
                        _run_call(f, "WallSel_Sub2", m8=False, x8=False, x=(obj - 0x100) * 2)
                    self.assertEqual(f.cpu.a, WALLSEL_BUFFER_OFFSET)
                    self.assertEqual(self._read_buffer(f, len(expected)), expected, f"Glacia ${room:03X} obj ${obj:03X} mismatch")
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
