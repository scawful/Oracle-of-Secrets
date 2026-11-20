#!/usr/bin/env python3
"""Compiled 65816 CPU tests for Toadstool Woods inhabitants & Archery intro.

Verifies:
1. Sprites/NPCs/toadstool_inhabitants.asm:
   - $05:F48A hook (ToadstoolForager_Idle): in Room $00F3, shows expanded message
     $022A via Sprite_ShowSolicitedMessage ($05E1A7), leaves SprAction=0, and
     jumps to MrsSahasrahla_Animate ($05F49F) with balanced stack.
   - Outside Room $00F3, falls back to vanilla $05F490 with accurate Carry from
     LDA.l $7EF359 : CMP.b #$02.
   - $05:8292 hook (ToadstoolArchery_ShowIntro): sets $1CF0=$2B, $1CF1=$02
     ($022B), invokes Sprite_ShowMessageMinimal ($05FA8E), clears SprTimerA, X,
     and returns cleanly to $058297 (INC.w SprAction, X).
2. Sprites/NPCs/village_animals.asm:
   - VillageCat_Prep assigns Cat action (Y=$03) indoors in Room $00F2.
   - VillageCat_Draw uses native 0xC0 sitting-cat draw (C=0) for UW ss=5 ($0AA3=$45).
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

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]


def _find_lakesnes() -> Path:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    raise RuntimeError("LakeSnes checkout not found")


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


def _assemble_fixture(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    image = bytearray(b"\x00" * 0x200000)

    # Seed vanilla hook assertion bytes for toadstool_inhabitants.asm
    # $05F48A: AF 59 F3 7E C9 02 (LDA.l $7EF359 : CMP.b #$02)
    image[_snes_to_pc(0x05F48A):_snes_to_pc(0x05F490)] = bytes([0xAF, 0x59, 0xF3, 0x7E, 0xC9, 0x02])
    # $058292: A9 85 20 BF 82 (LDA.b #$85 : JSR $82BF)
    image[_snes_to_pc(0x058292):_snes_to_pc(0x058297)] = bytes([0xA9, 0x85, 0x20, 0xBF, 0x82])

    # Seed vanilla hook assertion bytes for village_animals.asm
    image[_snes_to_pc(0x06F244):_snes_to_pc(0x06F24F)] = bytes([
        0xBD, 0x20, 0x0E,
        0xC9, 0x0B, 0xF0, 0x0C,
        0xC9, 0x4A, 0xF0, 0x08,
    ])
    image[_snes_to_pc(0x05A8CE):_snes_to_pc(0x05A8D4)] = bytes([
        0x20, 0x93, 0xAB,
        0x20, 0xED, 0xF9,
    ])
    image[_snes_to_pc(0x068CA1):_snes_to_pc(0x068CAD)] = bytes([
        0xA5, 0xA0, 0xA0, 0x00,
        0xD9, 0x99, 0x8C, 0xF0,
        0x03, 0xC8, 0xD0, 0xF8,
    ])
    image[_snes_to_pc(0x06AE34):_snes_to_pc(0x06AE39)] = bytes([0xBD, 0xF0, 0x0D, 0xD0, 0x19])
    image[_snes_to_pc(0x06AF1A):_snes_to_pc(0x06AF21)] = bytes([0xBD, 0x80, 0x0E, 0x0A, 0x7D, 0xC0, 0x0D])

    rom_path = folder / "fixture.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "harness.asm"
    asm_path.write_text(
        "lorom\n"
        "SprY = $0D00\n"
        "SprX = $0D10\n"
        "SprYH = $0D20\n"
        "SprXH = $0D30\n"
        "SprYSpeed = $0D40\n"
        "SprXSpeed = $0D50\n"
        "SprAction = $0D80\n"
        "SprFrame = $0DC0\n"
        "SprTimerA = $0DF0\n"
        "SprTimerF = $0F80\n"
        "SprSubtype = $0E30\n"
        "SprHeight = $0F70\n"
        "Sprite_ShowSolicitedMessage = $05E1A7\n"
        "Sprite_ShowSolicitedMessageIfPlayerFacing = $05E1A7\n"
        "Sprite_CheckDamageFromPlayer = $06F128\n"
        "Sprite_CheckDamageToPlayer = $06F154\n"
        "Sprite_MoveLong = $05E724\n"
        "Sprite_IsToRightOfPlayer = $06E77B\n"
        "Sprite_DrawShadow = $06F806\n"
        "Sound_SetSfx2PanLong = $0DBB64\n"
        "Sound_SetSfx3PanLong = $0DBB67\n"
        "org $05E1A7\n"
        "Stub_ShowSolicited:\n"
        "  STA.l $7E0400\n"
        "  TYA : STA.l $7E0401\n"
        "  LDA.l $7E0402 : INC A : STA.l $7E0402\n"
        "  SEC : RTL\n"
        "org $05FA8E\n"
        "Stub_ShowMinimal:\n"
        "  LDA.l $7E0403 : INC A : STA.l $7E0403\n"
        "  RTL\n"
        "org $05F490\n"
        "Vanilla_05F490:\n"
        "  LDA.b #$00 : ROL A : STA.l $7E0404\n"  # capture Carry (1 if >=2, 0 if <2)
        "  LDA.b #$BB : STA.l $7E0405\n"
        "  RTS\n"
        "org $05F49F\n"
        "MrsSahasrahla_Animate:\n"
        "  LDA.b #$AA : STA.l $7E0406\n"
        "  RTS\n"
        "org $058297\n"
        "Archery_AfterIntro:\n"
        "  INC.w $0D80, X\n"
        "  RTS\n"
        "org $2B8000\n"
        f'incsrc "{(ROOT / "Sprites" / "NPCs" / "village_animals.asm").as_posix()}"\n'
        "org $328000\n"
        f'incsrc "{(ROOT / "Sprites" / "NPCs" / "toadstool_inhabitants.asm").as_posix()}"\n',
        encoding="utf-8",
    )

    proc = subprocess.run(
        [
            "asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla",
            f"-I{ROOT.as_posix()}", str(asm_path), str(rom_path),
        ],
        capture_output=True, text=True, cwd=ROOT,
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


def _run_at(
    f: Fixture,
    addr: int,
    *,
    long_return: bool,
    db: int = 0x05,
    x: int = 0,
    a: int = 0,
) -> None:
    c = f.cpu
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    c.db = db
    c.mf = True
    c.xf = True
    c.a = a & 0xFF
    c.x = x & 0xFF
    c.y = 0
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
    for _ in range(5000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack at {addr:#x}: {c.sp:#x} != {sp:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Step ceiling reached at {addr:#x}")


class ToadstoolInhabitantsCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory(prefix="oos-toadstool-inh-")
        td = Path(cls._td.name)
        cls.lib = _build_cpu_lib(td)
        cls.rom, cls.labels = _assemble_fixture(td / "asm")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _fixture(self) -> Fixture:
        return Fixture(self.lib, self.rom, self.labels)

    def test_forager_in_room_00f3_shows_022a_and_animates(self) -> None:
        f = self._fixture()
        try:
            f.put(0x00A0, 0xF3)
            f.put(0x00A1, 0x00)
            f.put(0x0D82, 0x00)  # SprAction[slot 2]
            f.put(0x7EF359, 0x03)  # Even with Master Sword, $00F3 shows $022A
            _run_at(f, 0x05F48A, long_return=False, db=0x05, x=2)
            self.assertEqual(f.get(0x0400), 0x2A, "Expected low byte $2A of $022A")
            self.assertEqual(f.get(0x0401), 0x02, "Expected high byte $02 of $022A")
            self.assertEqual(f.get(0x0402), 0x01, "Expected 1 Sprite_ShowSolicitedMessage call")
            self.assertEqual(f.get(0x0406), 0xAA, "Expected jump to MrsSahasrahla_Animate")
            self.assertEqual(f.get(0x0405), 0x00, "Must not take vanilla fallback in $00F3")
            self.assertEqual(f.get(0x0D82), 0x00, "SprAction must remain 0 in $00F3")
        finally:
            f.close()

    def test_forager_outside_00f3_falls_back_to_vanilla(self) -> None:
        for sword, expected_carry in ((0x01, 0), (0x02, 1)):
            with self.subTest(sword=sword):
                f = self._fixture()
                try:
                    f.put(0x00A0, 0x04)
                    f.put(0x00A1, 0x01)
                    f.put(0x7EF359, sword)
                    _run_at(f, 0x05F48A, long_return=False, db=0x05, x=1)
                    self.assertEqual(f.get(0x0405), 0xBB, "Expected vanilla $05F490 path")
                    self.assertEqual(f.get(0x0404), expected_carry)
                    self.assertEqual(f.get(0x0402), 0x00)
                finally:
                    f.close()

    def test_archery_intro_shows_022b_clears_timer_and_advances_action(self) -> None:
        f = self._fixture()
        try:
            f.put(0x0D83, 0x00)  # SprAction[3]
            f.put(0x0DF3, 0x42)  # SprTimerA[3]
            _run_at(f, 0x058292, long_return=False, db=0x05, x=3)
            self.assertEqual(f.get(0x1CF0), 0x2B, "Expected $1CF0=$2B")
            self.assertEqual(f.get(0x1CF1), 0x02, "Expected $1CF1=$02")
            self.assertEqual(f.get(0x0403), 0x01, "Expected Sprite_ShowMessageMinimal call")
            self.assertEqual(f.get(0x0DF3), 0x00, "Expected SprTimerA cleared")
            self.assertEqual(f.get(0x0D83), 0x01, "Expected SprAction incremented to 1")
        finally:
            f.close()

    def test_village_cat_prep_and_draw_in_room_00f2_ss5(self) -> None:
        f = self._fixture()
        try:
            f.put(0x001B, 0x01)
            f.put(0x00A0, 0xF2)
            f.put(0x00A1, 0x00)
            _run_at(f, self.labels["VillageCat_Prep"], long_return=True, db=0x06, x=0)
            self.assertEqual(f.cpu.y & 0xFF, 0x03, "Expected Cat action Y=$03 for Room $00F2")

            f.put(0x0D80, 0x03)  # SprAction = Cat
            f.put(0x0DC0, 0x00)  # SprFrame = 0
            f.put(0x0AA3, 0x45)  # UW ss=5 (loads 0xC0 in slot 1)
            _run_at(f, self.labels["VillageCat_Draw"], long_return=True, db=0x06, x=0)
            self.assertEqual(f.cpu.c, 0, "Expected C=0 native 0xC0 sitting-cat draw for $0AA3=$45")
            self.assertEqual(f.cpu.a & 0xFF, 0x06)
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
