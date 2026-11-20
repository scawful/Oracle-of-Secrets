#!/usr/bin/env python3
"""Unit and compiled 65816 CPU tests for Eon Abyss GBC Interiors (Q327-1A / Q328 A4).

Verifies:
1. Declarative Dungeons/Data/abyss_gbc/styles.json schema, room parity (all 31
   live Abyss entrance targets + connected Fortress/Finale/Volcanic/Cave rooms,
   excluding Lyra Sea pendant shrines), and deterministic --check drift detection.
2. Pure-Python --preview-room fallback contact sheet generation.
3. Compiled 65816 execution (Asar + LakeSnes CPU) of the real
   Dungeons/abyss_gbc_interiors.asm + Dungeons/Data/abyss_gbc/abyss_gbc.asm:
   - Every styled room activates GBC sheets & palettes when $1B=1, $7EF3CA=$40.
   - All shared rooms ($102/$107/$10E/$114/$11E/$122/$124) and newly styled rooms
     stay 100% vanilla SNES when $7EF3CA=$00 (Kalyxo LW), $7EF3CA=$80 (Special OW),
     or $1B=0 (outdoors).
   - Unstyled and out-of-range rooms stay vanilla SNES even in Eon Abyss.
   - Style-boundary sync (AbyssGbc_FullLoadEntry, AbyssGbc_SyncStyle, door-scroll
     aux->main palette copy) preserves registers, stack, and brightness ($13).
   - Bank $5A and Bank $5B end addresses remain strictly inside $5A8000-$5AFFFF
     and $5B8000-$5BFFFF (zero Bank $5A/$5B overflow).
"""
from __future__ import annotations

import ctypes as C
import json
import os
from pathlib import Path
import re
import shutil
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

ABYSS_DIR = ROOT / "Dungeons" / "Data" / "abyss_gbc"
LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]

SHARED_KALYXO_ABYSS_ROOMS = (0x102, 0x107, 0x10E, 0x114, 0x11E, 0x122, 0x124)
LIVE_ABYSS_ENTRANCE_TARGET_ROOMS = {
    # Finale
    0x002, 0x010,
    # Palace
    0x005, 0x116,
    # Fortress entrance
    0x00C,
    # Houses (b3 + b17)
    0x00F, 0x0C9, 0x0F4, 0x0F5, 0x100, 0x102, 0x107, 0x110, 0x111, 0x11C, 0x122,
    # Volcanic (b13)
    0x014, 0x015, 0x023, 0x024,
    # Caves (b6 + b20)
    0x0D0, 0x0D1, 0x0F6, 0x10E, 0x112, 0x114, 0x117, 0x11E, 0x123, 0x124, 0x125,
}
EXCLUDED_LYRA_SHRINE_ROOMS = (0x053, 0x073, 0x074, 0x075, 0x076, 0x083, 0x084, 0x085, 0x086, 0x0CA)


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


def _assemble_real_abyss_module(folder: Path) -> tuple[bytes, dict[str, int]]:
    """Compile the actual Dungeons/abyss_gbc_interiors.asm + abyss_gbc.asm into a 4MB LoROM image."""
    folder.mkdir(parents=True, exist_ok=True)
    image = bytearray(b"\xFF" * 0x400000)

    # Seed exact vanilla hook assertion bytes expected by Dungeons/abyss_gbc_interiors.asm
    struct.pack_into("<I", image, _snes_to_pc(0x00E219), 0x00A930C2)
    struct.pack_into("<I", image, _snes_to_pc(0x00E21D), 0x21168D20)
    struct.pack_into("<I", image, _snes_to_pc(0x028A63), 0x00D6F922)
    struct.pack_into("<I", image, _snes_to_pc(0x028CED), 0x00D66E22)
    struct.pack_into("<I", image, _snes_to_pc(0x02940F), 0x00D66E22)
    struct.pack_into("<H", image, _snes_to_pc(0x1BEE74), 0x21C2)
    image[_snes_to_pc(0x1BEE76)] = 0xAE
    struct.pack_into("<H", image, _snes_to_pc(0x1BEE77), 0x0AB6)

    rom_path = folder / "abyss_fixture.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "harness.asm"
    asm_path.write_text(
        "lorom\n"
        # Minimal vanilla Palettes_Load_UnderworldSet body at $1BEE79:
        # writes sentinel word $2468 across aux BG rows 2-7 ($7EC342..$7EC3FE),
        # then exits via SEP #$30 : RTL just like vanilla $1BEEA7.
        "org $1BEE79\n"
        "VanillaPalLoad:\n"
        "  REP #$30\n"
        "  LDA.l $7E0AA8 : CLC : ADC.w #$0042 : TAX\n"
        "  LDA.w #$0005 : STA.b $08\n"
        ".vrow:\n"
        "  PHX\n"
        "  LDA.w #$000E : STA.b $06\n"
        ".vcol:\n"
        "  LDA.w #$2468 : STA.l $7EC300,X\n"
        "  INX #2\n"
        "  DEC.b $06 : BPL .vcol\n"
        "  PLA : CLC : ADC.w #$0020 : TAX\n"
        "  DEC.b $08 : BPL .vrow\n"
        "  SEP #$30\n"
        "  RTL\n"
        # Minimal InitializeTilesets BG-load tail at $00E221: AbyssGbc_FullLoadEntry
        # returns with REP #$30, so drop back to SEP #$30 before writing breadcrumb,
        # popping PHB (vanilla PLB at $00E2CE), and returning via RTL.
        "org $00E221\n"
        "  SEP #$30\n"
        "  LDA.b #$5A : STA.l $7E0270\n"  # breadcrumb proving full BG reload executed
        "  PLB\n"
        "  RTL\n"
        f'incsrc "{(ROOT / "Dungeons" / "abyss_gbc_interiors.asm").as_posix()}"\n',
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
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            rom_path.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return rom_path.read_bytes(), labels


def _run_call(
    f: Fixture,
    entry: str,
    *,
    long_return: bool = True,
    m8: bool = True,
    x8: bool = True,
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
    c.a = a & (0xFF if m8 else 0xFFFF)
    c.x = x & (0xFF if x8 else 0xFFFF)
    c.y = y & (0xFF if x8 else 0xFFFF)
    ret_addr = (addr & 0xFF0000) | 0x7000
    if long_return:
        f.put(sp, addr >> 16)
        f.put(sp - 1, 0x6F)
        f.put(sp - 2, 0xFF)
        c.sp -= 3
    else:
        f.put(sp, 0x6F)
        f.put(sp - 1, 0xFF)
        c.sp -= 2
    for _ in range(50000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack in {entry}: {c.sp:#x} != {sp:#x}"
            return
        if pc in f.stubs:
            f.stub(f.stubs[pc])
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction ceiling reached in {entry}")


class AbyssGbcToolingTests(unittest.TestCase):
    def test_styles_json_schema_and_full_abyss_parity(self) -> None:
        _, defaults, styles, _ = gag.load_styles_config(ABYSS_DIR / "styles.json")
        self.assertEqual([s["name"] for s in styles], [
            "onox", "fire", "rites", "finale", "palace", "house", "volcanic", "cave"
        ])
        self.assertTrue(defaults["skip_unchanged_sheets"])
        self.assertIn(0xB, defaults["skip_floors"])

        room_to_style = {}
        for style in styles:
            for r in style["rooms"] + style["more_rooms"]:
                room_to_style[r] = style["name"]

        # Every one of the 31 live Abyss entrance/hole target rooms must be styled
        missing = sorted(LIVE_ABYSS_ENTRANCE_TARGET_ROOMS - set(room_to_style))
        self.assertEqual(missing, [], f"Unstyled live Abyss entrance rooms: {[hex(r) for r in missing]}")

        # Spot-check exact style mapping for all newly added families
        self.assertEqual(room_to_style[0x002], "finale")
        for r in (0x00F, 0x0C9, 0x0F4, 0x0F5, 0x100, 0x102, 0x107, 0x110, 0x11C, 0x111, 0x122):
            self.assertEqual(room_to_style[r], "house", f"Room 0x{r:03X} expected house")
        for r in (0x004, 0x013, 0x014, 0x015, 0x023, 0x024):
            self.assertEqual(room_to_style[r], "volcanic", f"Room 0x{r:03X} expected volcanic")
        for r in (0x0D0, 0x0D1, 0x0D2, 0x0F6, 0x10E, 0x112, 0x114, 0x117, 0x11E, 0x123, 0x124, 0x125):
            self.assertEqual(room_to_style[r], "cave", f"Room 0x{r:03X} expected cave")
        self.assertEqual(room_to_style[0x005], "palace")
        self.assertEqual(room_to_style[0x116], "palace")

        # Lyra Sea pendant shrines remain SNES (unmapped)
        for r in EXCLUDED_LYRA_SHRINE_ROOMS:
            self.assertNotIn(r, room_to_style, f"Pendant shrine room 0x{r:03X} must not be GBC-styled")

    def test_check_mode_passes_clean_and_detects_all_drift_vectors(self) -> None:
        self.assertEqual(gag.main(["--check"]), 0)

        with tempfile.TemporaryDirectory(prefix="oos-abyss-drift-") as td:
            base_copy = Path(td) / "abyss_gbc"
            shutil.copytree(ABYSS_DIR, base_copy)
            self.assertEqual(gag.main(["--check", "--out-dir", str(base_copy)]), 0)

            # 1. styles.json drift
            d1 = Path(td) / "drift_styles"
            shutil.copytree(base_copy, d1)
            cfg = json.loads((d1 / "styles.json").read_text(encoding="utf-8"))
            cfg["styles"][0]["notes"] += " DRIFT"
            (d1 / "styles.json").write_text(json.dumps(cfg, indent=2) + "\n", encoding="utf-8")
            self.assertNotEqual(gag.main(["--check", "--out-dir", str(d1)]), 0)

            # 2. .lz2 drift
            d2 = Path(td) / "drift_lz2"
            shutil.copytree(base_copy, d2)
            lz = bytearray((d2 / "cave.03.lz2").read_bytes())
            lz[0] ^= 0xFF
            (d2 / "cave.03.lz2").write_bytes(bytes(lz))
            self.assertNotEqual(gag.main(["--check", "--out-dir", str(d2)]), 0)

            # 3. .txt drift
            d3 = Path(td) / "drift_txt"
            shutil.copytree(base_copy, d3)
            txt = (d3 / "volcanic.03.txt").read_text(encoding="utf-8")
            mutated = ("1" if txt[0] != "1" else "2") + txt[1:]
            (d3 / "volcanic.03.txt").write_text(mutated, encoding="utf-8")
            self.assertNotEqual(gag.main(["--check", "--out-dir", str(d3)]), 0)

            # 4. abyss_gbc.asm drift
            d4 = Path(td) / "drift_asm"
            shutil.copytree(base_copy, d4)
            (d4 / "abyss_gbc.asm").write_text(
                (d4 / "abyss_gbc.asm").read_text(encoding="utf-8") + "; drift\n",
                encoding="utf-8",
            )
            self.assertNotEqual(gag.main(["--check", "--out-dir", str(d4)]), 0)

            # 5. Orphan .lz2 file drift
            d5 = Path(td) / "drift_orphan"
            shutil.copytree(base_copy, d5)
            (d5 / "orphan.FF.lz2").write_bytes(b"\xFF")
            self.assertNotEqual(gag.main(["--check", "--out-dir", str(d5)]), 0)

    def test_preview_room_fallback_renders_png_without_z3ed(self) -> None:
        live_rom = Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom")
        if not live_rom.is_file():
            self.skipTest("Live authoring ROM not present in this environment")
        with tempfile.TemporaryDirectory(prefix="oos-abyss-prev-") as td:
            out_png = Path(td) / "preview_002_014.png"
            rc = gag.main([
                "--preview-room", "0x002,0x014",
                "--rom", str(live_rom),
                "--no-z3ed",
                "--panel-size", "192",
                "--out", str(out_png),
            ])
            self.assertEqual(rc, 0)
            self.assertTrue(out_png.is_file())
            self.assertGreater(out_png.stat().st_size, 2000)


class AbyssGbcCompiled65816Tests(unittest.TestCase):
    _tmpdir: tempfile.TemporaryDirectory[str]
    _lib: C.CDLL
    _rom: bytes
    _labels: dict[str, int]
    _styles: list[dict]
    _coverage: dict

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="oos-abyss-65816-")
        base = Path(cls._tmpdir.name)
        cls._lib = _build_cpu_lib(base)
        cls._rom, cls._labels = _assemble_real_abyss_module(base / "asm")
        _, _, cls._styles, _ = gag.load_styles_config(ABYSS_DIR / "styles.json")
        cls._coverage = json.loads((ABYSS_DIR / "coverage.json").read_text(encoding="utf-8"))

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def _new_fixture(self) -> Fixture:
        return Fixture(self._lib, self._rom, self._labels)

    def test_bank_5a_and_5b_headroom_no_overflow(self) -> None:
        bank5a_syms = [(name, addr) for name, addr in self._labels.items() if (addr >> 16) == 0x5A]
        bank5b_syms = [(name, addr) for name, addr in self._labels.items() if (addr >> 16) == 0x5B]
        self.assertTrue(bank5a_syms, "Expected Bank $5A symbols")
        self.assertTrue(bank5b_syms, "Expected Bank $5B symbols")
        max_5a = max(addr for _, addr in bank5a_syms)
        max_5b = max(addr for _, addr in bank5b_syms)
        self.assertLess(max_5a, 0x5B0000)
        self.assertLess(max_5b, 0x5C0000)
        metrics = self._coverage["bank_metrics"]
        self.assertLessEqual(metrics["bank5a_stream_bytes"], metrics["bank5a_stream_budget"])
        self.assertLess(metrics["bank5b_stream_bytes"], gag.BANK_CAPACITY)
        self.assertGreater(metrics["bank5b_free_bytes"], 10000)

    def test_every_styled_room_activates_gbc_sheets_and_palettes_in_abyss(self) -> None:
        f = self._new_fixture()
        try:
            for sid, style in enumerate(self._styles, 1):
                sname = style["name"]
                centry = self._coverage["styles"][sname]
                expected_pal = [int(w, 16) for w in centry["palette_words"]]
                remapped_sheets = [
                    int(shex, 16)
                    for shex, sinfo in centry["sheets"].items()
                    if isinstance(sinfo, dict) and sinfo.get("remapped", True)
                ]
                passthrough_sheets = [
                    int(shex, 16)
                    for shex, sinfo in centry["sheets"].items()
                    if isinstance(sinfo, dict) and not sinfo.get("remapped", True)
                ]
                rooms = style["rooms"] + style["more_rooms"]

                for room in rooms:
                    with self.subTest(style=sname, room=f"0x{room:03X}"):
                        f.put(0x001B, 0x01)
                        f.put(0x7EF3CA, 0x40)  # Eon Abyss
                        f.put(0x00A0, room & 0xFF)
                        f.put(0x00A1, (room >> 8) & 0xFF)

                        # 1. AbyssGbc_GetStyle returns exact style ID
                        _run_call(f, "AbyssGbc_GetStyle", long_return=False, m8=True, x8=True)
                        self.assertEqual(f.cpu.a & 0xFF, sid)

                        # 2. AbyssGbc_RemapBg remaps every modified sheet for this style
                        for sheet in remapped_sheets:
                            f.put(0x00C8, 0x11)
                            f.put(0x00C9, 0x22)
                            f.put(0x00CA, 0x33)
                            _run_call(f, "AbyssGbc_RemapBg", long_return=True, m8=True, x8=False, x=sheet)
                            got_ptr = f.get(0x00C8) | (f.get(0x00C9) << 8) | (f.get(0x00CA) << 16)
                            expected_ptr = self._labels[f"AbyssGbc_{sname}_{sheet:02X}"]
                            self.assertEqual(got_ptr, expected_ptr)
                            self.assertEqual(f.cpu.x, sheet)

                        # 3. Slot 7 ($0F) and vanilla-pass sheets keep vanilla pointer
                        for sheet in [0x0F, *passthrough_sheets]:
                            f.put(0x00C8, 0x44)
                            f.put(0x00C9, 0x55)
                            f.put(0x00CA, 0x66)
                            _run_call(f, "AbyssGbc_RemapBg", long_return=True, m8=True, x8=False, x=sheet)
                            got_ptr = f.get(0x00C8) | (f.get(0x00C9) << 8) | (f.get(0x00CA) << 16)
                            self.assertEqual(got_ptr, 0x665544)
                            self.assertEqual(f.cpu.x, sheet)

                        # 4. AbyssGbc_PalWrap overwrites aux BG rows 2-7 with style palette
                        f.put(0x0AA8, 0x00)
                        f.put(0x0AA9, 0x00)
                        f.put(0x0010, 0x07)
                        f.put(0x0011, 0x00)
                        f.put(0x7EC005, 0x00)
                        f.put(0x7F5409, 0x00)
                        f.put(0x027F, 0xA5)  # Gust Jar !GustJarFlags sentinel must stay untouched
                        _run_call(f, "AbyssGbc_PalWrap", long_return=True, m8=True, x8=True)
                        self.assertEqual(f.get(0x7F5409), sid)
                        self.assertEqual(f.get(0x027F), 0xA5, "AbyssGbc_PalWrap must not clobber Gust Jar $027F")
                        got_words = []
                        for row in range(6):
                            base_addr = 0x7EC342 + row * 0x20
                            for col in range(15):
                                lo = f.get(base_addr + col * 2)
                                hi = f.get(base_addr + col * 2 + 1)
                                got_words.append(lo | (hi << 8))
                        self.assertEqual(got_words, expected_pal)
        finally:
            f.close()

    def test_shared_and_new_rooms_stay_vanilla_snes_outside_abyss(self) -> None:
        test_rooms = sorted(set(SHARED_KALYXO_ABYSS_ROOMS) | {0x002, 0x00F, 0x0F4, 0x014, 0x0D0, 0x111, 0x116})
        # Non-Abyss states: Kalyxo LW ($00), Special OW ($80), arbitrary non-$40 ($C0), and Outdoors ($1B=0)
        non_abyss_states = [
            ("kalyxo_lw", 0x01, 0x00),
            ("special_ow", 0x01, 0x80),
            ("other_world_flag", 0x01, 0xC0),
            ("abyss_outdoors", 0x00, 0x40),
        ]
        f = self._new_fixture()
        try:
            for label, indoor, world_flag in non_abyss_states:
                for room in test_rooms:
                    with self.subTest(state=label, room=f"0x{room:03X}"):
                        f.put(0x001B, indoor)
                        f.put(0x7EF3CA, world_flag)
                        f.put(0x00A0, room & 0xFF)
                        f.put(0x00A1, (room >> 8) & 0xFF)

                        _run_call(f, "AbyssGbc_GetStyle", long_return=False, m8=True, x8=True)
                        self.assertEqual(f.cpu.a & 0xFF, 0)

                        # Test sheets commonly remapped across styles (01, 03, 07, 0B, 10, 12, 13)
                        for sheet in (0x01, 0x03, 0x07, 0x0B, 0x10, 0x12, 0x13):
                            f.put(0x00C8, 0xAA)
                            f.put(0x00C9, 0xBB)
                            f.put(0x00CA, 0xCC)
                            _run_call(f, "AbyssGbc_RemapBg", long_return=True, m8=True, x8=False, x=sheet)
                            got_ptr = f.get(0x00C8) | (f.get(0x00C9) << 8) | (f.get(0x00CA) << 16)
                            self.assertEqual(got_ptr, 0xCCBBAA)

                        # PalWrap keeps vanilla sentinel $2468 untouched across all 6 BG rows
                        f.put(0x0AA8, 0x00)
                        f.put(0x0AA9, 0x00)
                        f.put(0x0010, 0x07)
                        f.put(0x0011, 0x00)
                        f.put(0x7F5409, 0x00)
                        f.put(0x027F, 0x5A)
                        _run_call(f, "AbyssGbc_PalWrap", long_return=True, m8=True, x8=True)
                        self.assertEqual(f.get(0x7F5409), 0)
                        self.assertEqual(f.get(0x027F), 0x5A)
                        for row in range(6):
                            base_addr = 0x7EC342 + row * 0x20
                            for col in range(15):
                                word = f.get(base_addr + col * 2) | (f.get(base_addr + col * 2 + 1) << 8)
                                self.assertEqual(word, 0x2468)
        finally:
            f.close()

    def test_unstyled_and_out_of_range_rooms_stay_vanilla_even_in_abyss(self) -> None:
        f = self._new_fixture()
        try:
            for room in (0x001, 0x053, 0x073, 0x0CA, 0x128, 0x01FF):
                with self.subTest(room=f"0x{room:03X}"):
                    f.put(0x001B, 0x01)
                    f.put(0x7EF3CA, 0x40)
                    f.put(0x00A0, room & 0xFF)
                    f.put(0x00A1, (room >> 8) & 0xFF)
                    _run_call(f, "AbyssGbc_GetStyle", long_return=False, m8=True, x8=True)
                    self.assertEqual(f.cpu.a & 0xFF, 0)
                    f.put(0x00C8, 0x12)
                    f.put(0x00C9, 0x34)
                    f.put(0x00CA, 0x56)
                    _run_call(f, "AbyssGbc_RemapBg", long_return=True, m8=True, x8=False, x=0x01)
                    self.assertEqual(f.get(0x00C8) | (f.get(0x00C9) << 8) | (f.get(0x00CA) << 16), 0x563412)
        finally:
            f.close()

    def test_full_load_sync_style_and_door_scroll_palette_copy(self) -> None:
        f = self._new_fixture()
        try:
            # 1. AbyssGbc_FullLoadEntry records volcanic style (#7) for room $014
            #    without clobbering Gust Jar WRAM ($027E/$027F).
            f.put(0x001B, 0x01)
            f.put(0x7EF3CA, 0x40)
            f.put(0x00A0, 0x14)
            f.put(0x00A1, 0x00)
            f.put(0x7F5408, 0x00)
            f.put(0x027E, 0xCC)
            f.put(0x027F, 0x33)
            _run_call(f, "AbyssGbc_FullLoadEntry", long_return=True, m8=True, x8=True)
            self.assertEqual(f.get(0x7F5408), 7)
            self.assertEqual(f.get(0x027E), 0xCC, "AbyssGbc_FullLoadEntry must not clobber Gust Jar $027E")
            self.assertEqual(f.get(0x027F), 0x33, "AbyssGbc_FullLoadEntry must not clobber Gust Jar $027F")

            # 2. Same-style transition ($014 -> $023, both volcanic #7): SyncStyle skips reload
            f.put(0x00A0, 0x23)
            f.put(0x00A1, 0x00)
            f.put(0x0013, 0x0F)
            f.put(0x0270, 0x00)
            _run_call(f, "AbyssGbc_SyncStyle", long_return=True, m8=True, x8=True)
            self.assertEqual(f.get(0x0270), 0x00, "Same-style transition must not force-blank reload")
            self.assertEqual(f.get(0x0013), 0x0F)
            self.assertEqual(f.get(0x7F5408), 7)
            self.assertEqual(f.get(0x027E), 0xCC)

            # 3. Cross-style transition (volcanic #7 -> cave #8, room $0D0): SyncStyle reloads and restores $13
            f.put(0x00A0, 0xD0)
            f.put(0x00A1, 0x00)
            f.put(0x0013, 0x0F)
            f.put(0x0270, 0x00)
            _run_call(f, "AbyssGbc_SyncStyle", long_return=True, m8=True, x8=True)
            self.assertEqual(f.get(0x0270), 0x5A, "Cross-style transition must invoke full BG reload")
            self.assertEqual(f.get(0x0013), 0x0F, "Brightness $13 must be restored after reload")
            self.assertEqual(f.get(0x7F5408), 8, "!AbyssGbc_LoadedStyle must update to cave #8")
            self.assertEqual(f.get(0x027E), 0xCC)

            # 4. Door scroll across style boundary copies aux ($7EC342) -> main ($7EC542) and sets $15
            f.put(0x0010, 0x07)  # Dungeon module
            f.put(0x0011, 0x02)  # Door scroll submodule
            f.put(0x7EC005, 0x00)
            f.put(0x0AA8, 0x00)
            f.put(0x0AA9, 0x00)
            f.put(0x0015, 0x00)
            f.put(0x7F5409, 0x07)  # Previous palette was volcanic #7, now entering cave #8
            for off in range(0x42, 0x100, 2):
                f.put(0x7EC500 + off, 0x00)
                f.put(0x7EC500 + off + 1, 0x00)
            _run_call(f, "AbyssGbc_PalWrap", long_return=True, m8=True, x8=True)
            self.assertEqual(f.get(0x7F5409), 8)
            self.assertEqual(f.get(0x027F), 0x33)
            self.assertEqual(f.get(0x0015), 0x01)
            expected_cave_first = int(self._coverage["styles"]["cave"]["palette_words"][0], 16)
            live_first = f.get(0x7EC542) | (f.get(0x7EC543) << 8)
            self.assertEqual(live_first, expected_cave_first)
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
