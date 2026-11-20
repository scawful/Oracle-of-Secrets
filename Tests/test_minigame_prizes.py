#!/usr/bin/env python3
"""Compiled 65816 CPU tests for Archery ($0111) Power Ring & Chest Hut ($0118) rules.

Verifies:
1. Items/magic_rings.asm ArcheryGame_RingPrize ($05:8436 hook) + ArcheryRing_ShowWinMsg:
   - Streak < 5 ($0B88 = 0..4): never mutates FOUNDRINGS, never writes SFX3 $0F,
     never opens message $022D, returns exact vanilla rupee prize with B=0.
   - Streak == 5 first time: sets Power Ring bit $20 in FOUNDRINGS ($7EF3A1),
     plays SFX3 $0F ($012F), loads $1CF0=$2D/$1CF1=$02 ($022D) and calls
     Sprite_ShowMessageMinimal ($05FA8E), preserves X/Y, returns 64 Rupees.
   - Repeat 5/5 when bit $20 is already in FOUNDRINGS or MAGICRINGS ($7EF3A2):
     never replays SFX3 $0F or $022D, never mutates ring bytes, still pays rupees.
2. Sprites/NPCs/chest_hut_game.asm:
   - $1EF0A4 patches MiniChestGameGuy offer to $022C (LDA #$2C : LDY #$02).
   - $1EF0B7 patches price to 30 Rupees ($1E); $1EF0C0 patches credits to 2 ($02).
   - $1EF0E1 hook ChestHut_GetAfterMsgIndex returns Y=0 for $04C4==0 ($0163) and
     clamps $04C4==1 and $04C4==2 to Y=1 ($017F) so 2-chest play never reads OOB.
   - $01EEFF hook ChestHut_RollPrize grants one-time Seashell ($7EF391, capped at 99)
     with dual persistence ($0403 + $7EF231 bit $40) + SFX3 $0F, and otherwise rolls
     strictly across the DECIDED 1/20/50/100 Rupee set ($34/$47/$41/$40) + SFX3 $0E.
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

    # Seed vanilla ArcheryGame_Octo payout bytes at $058436: A9 00 EB B9 CE 83
    image[_snes_to_pc(0x058436):_snes_to_pc(0x05843C)] = bytes([0xA9, 0x00, 0xEB, 0xB9, 0xCE, 0x83])
    # Seed vanilla ArcheryGame_Prizes table at $0583CF: 4, 8, 16, 32, 64, 99, 99, 99, 99, 99
    image[_snes_to_pc(0x0583CF):_snes_to_pc(0x0583D9)] = bytes([4, 8, 16, 32, 64, 99, 99, 99, 99, 99])

    # Seed vanilla toadstool_inhabitants hook sites ($05F48A, $058292)
    image[_snes_to_pc(0x05F48A):_snes_to_pc(0x05F490)] = bytes([0xAF, 0x59, 0xF3, 0x7E, 0xC9, 0x02])
    image[_snes_to_pc(0x058292):_snes_to_pc(0x058297)] = bytes([0xA9, 0x85, 0x20, 0xBF, 0x82])

    # Seed vanilla MiniChestGameGuy sites ($1EF0A4, $1EF0B7, $1EF0C0, $1EF0E1)
    image[_snes_to_pc(0x1EF0A4):_snes_to_pc(0x1EF0A8)] = bytes([0xA9, 0x7E, 0xA0, 0x01])
    image[_snes_to_pc(0x1EF0B7):_snes_to_pc(0x1EF0B9)] = bytes([0xA9, 0x14])
    image[_snes_to_pc(0x1EF0C0):_snes_to_pc(0x1EF0C2)] = bytes([0xA9, 0x01])
    image[_snes_to_pc(0x1EF0E1):_snes_to_pc(0x1EF0E5)] = bytes([0xAD, 0xC4, 0x04, 0xA8])

    # Seed vanilla OpenMiniGameChest_LowStake bytes at $01EEFF: 22 71 BA 0D 29 0F 18 69 10
    image[_snes_to_pc(0x01EEFF):_snes_to_pc(0x01EF08)] = bytes([
        0x22, 0x71, 0xBA, 0x0D, 0x29, 0x0F, 0x18, 0x69, 0x10,
    ])

    rom_path = folder / "fixture.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "harness.asm"
    asm_path.write_text(
        "lorom\n"
        "!DISABLE_MASKS = 1\n"
        "RingSaveBlock = $7EF3A1\n"
        "Seashells = $7EF391\n"
        "CURHP = $7EF36D\n"
        "MAXHP = $7EF36C\n"
        "FrameCounter = $7E001A\n"
        "LinkRecoilX = $28\n"
        "LinkRecoilY = $27\n"
        "SprTimerA = $0DF0\n"
        "Sprite_ShowSolicitedMessage = $05E1A7\n"
        "GetRandomInt = $0DBA71\n"
        "GaroMask_ParryContact = $008000\n"
        # Stub GetRandomInt: returns controlled byte from $7E0410
        "org $0DBA71\n"
        "  LDA.l $7E0410\n"
        "  RTL\n"
        # Stub Sprite_ShowMessageMinimal ($05FA8E): increments $7E0412, preserves X/Y
        "org $05FA8E\n"
        "  LDA.l $7E0412 : INC A : STA.l $7E0412\n"
        "  RTL\n"
        # Vanilla FinalizeChestGamePrize at $01EEC5..$01EED6
        "org $01EEC5\n"
        "FinalizeChestGamePrize:\n"
        "  STX.b $C8\n"
        "  STA.b $0C\n"
        "  STZ.b $0D\n"
        "  LDA.b #$01 : STA.b $14\n"
        "  LDA.b #$0E : STA.w $012F\n"
        "  PLB\n"
        "  SEC\n"
        "  RTL\n"
        "org $2B8000\n"
        f'incsrc "{(ROOT / "Items" / "magic_rings.asm").as_posix()}"\n'
        "org $328000\n"
        f'incsrc "{(ROOT / "Sprites" / "NPCs" / "toadstool_inhabitants.asm").as_posix()}"\n'
        f'incsrc "{(ROOT / "Sprites" / "NPCs" / "chest_hut_game.asm").as_posix()}"\n',
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


def _run_long(
    f: Fixture,
    addr: int,
    *,
    db: int,
    x: int = 0,
    y: int = 0,
    a: int = 0,
    push_db_frame: bool = False,
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
    c.y = y & 0xFF
    ret_addr = (addr & 0xFF0000) | 0x7000
    f.put(sp, addr >> 16)
    f.put(sp - 1, 0x6F)
    f.put(sp - 2, 0xFF)
    c.sp -= 3
    if push_db_frame:
        f.put(c.sp, db)
        c.sp -= 1
    for _ in range(5000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack at {addr:#x}: {c.sp:#x} != {sp:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Step ceiling reached at {addr:#x}")


class MinigamePrizesCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory(prefix="oos-minigame-prizes-")
        td = Path(cls._td.name)
        cls.lib = _build_cpu_lib(td)
        cls.rom, cls.labels = _assemble_fixture(td / "asm")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _fixture(self) -> Fixture:
        return Fixture(self.lib, self.rom, self.labels)

    def test_archery_power_ring_requires_5_streak_shows_022d_and_grants_once(self) -> None:
        # 1. Streaks 1..4 never grant Power Ring ($20), SFX3 $0F, or message $022D
        for streak, prize_idx, expected_rupees in ((1, 1, 4), (2, 2, 8), (3, 3, 16), (4, 4, 32)):
            with self.subTest(streak=streak):
                f = self._fixture()
                try:
                    f.put(0x0B88, streak)
                    f.put(0x7EF3A1, 0x04)
                    f.put(0x7EF3A2, 0x00)
                    f.put(0x012F, 0x00)
                    f.put(0x0412, 0x00)
                    _run_long(f, self.labels["ArcheryGame_RingPrize"], db=0x05, x=3, y=prize_idx)
                    self.assertEqual(f.cpu.a & 0xFFFF, expected_rupees)
                    self.assertEqual(f.get(0x7EF3A1), 0x04)
                    self.assertEqual(f.get(0x012F), 0x00)
                    self.assertEqual(f.get(0x0412), 0x00)
                finally:
                    f.close()

        # 2. Streak == 5 first win grants Power Ring $20 + SFX3 $0F + shows $022D
        f = self._fixture()
        try:
            f.put(0x0B88, 5)
            f.put(0x7EF3A1, 0x04)
            f.put(0x7EF3A2, 0x01)
            f.put(0x012F, 0x00)
            f.put(0x0412, 0x00)
            _run_long(f, self.labels["ArcheryGame_RingPrize"], db=0x05, x=3, y=5)
            self.assertEqual(f.cpu.a & 0xFFFF, 64)
            self.assertEqual(f.cpu.x & 0xFF, 3)
            self.assertEqual(f.cpu.y & 0xFF, 5)
            self.assertEqual(f.get(0x7EF3A1), 0x24)
            self.assertEqual(f.get(0x012F), 0x0F)
            self.assertEqual(f.get(0x1CF0), 0x2D)
            self.assertEqual(f.get(0x1CF1), 0x02)
            self.assertEqual(f.get(0x0412), 0x01)

            # 3. Repeat 5/5 with Power Ring already in FOUNDRINGS: no duplicate SFX or msg
            f.put(0x012F, 0x00)
            f.put(0x0412, 0x00)
            _run_long(f, self.labels["ArcheryGame_RingPrize"], db=0x05, x=3, y=5)
            self.assertEqual(f.cpu.a & 0xFFFF, 64)
            self.assertEqual(f.get(0x012F), 0x00)
            self.assertEqual(f.get(0x0412), 0x00)

            # 4. Repeat 5/5 when Power Ring is appraised in MAGICRINGS: no re-grant or msg
            f.put(0x7EF3A1, 0x00)
            f.put(0x7EF3A2, 0x20)
            f.put(0x012F, 0x00)
            f.put(0x0412, 0x00)
            _run_long(f, self.labels["ArcheryGame_RingPrize"], db=0x05, x=3, y=5)
            self.assertEqual(f.get(0x7EF3A1), 0x00)
            self.assertEqual(f.get(0x012F), 0x00)
            self.assertEqual(f.get(0x0412), 0x00)
        finally:
            f.close()

    def test_chest_hut_30r_2_chests_patches_and_after_msg_clamp(self) -> None:
        # Verify exact compiled ROM patch bytes in Bank $1E
        self.assertEqual(self.rom[_snes_to_pc(0x1EF0A4):_snes_to_pc(0x1EF0A8)], bytes([0xA9, 0x2C, 0xA0, 0x02]))
        self.assertEqual(self.rom[_snes_to_pc(0x1EF0B7):_snes_to_pc(0x1EF0B9)], bytes([0xA9, 0x1E]))
        self.assertEqual(self.rom[_snes_to_pc(0x1EF0C0):_snes_to_pc(0x1EF0C2)], bytes([0xA9, 0x02]))

        # Verify ChestHut_GetAfterMsgIndex clamps $04C4 = 0->0, 1->1, 2->1 (no OOB read!)
        for credits_left, expected_y in ((0, 0), (1, 1), (2, 1)):
            with self.subTest(credits_left=credits_left):
                f = self._fixture()
                try:
                    f.put(0x04C4, credits_left)
                    _run_long(f, self.labels["ChestHut_GetAfterMsgIndex"], db=0x1E)
                    self.assertEqual(f.cpu.y & 0xFF, expected_y)
                finally:
                    f.close()

    def test_chest_hut_one_time_seashell_and_rupee_gamble(self) -> None:
        # 1. Unclaimed Seashell + jackpot roll (rand=4 -> X=4, X&3==0)
        f = self._fixture()
        try:
            f.put(0x0410, 0x04)
            f.put(0x0403, 0x00)
            f.put(0x7EF231, 0x00)
            f.put(0x7EF391, 0x07)
            _run_long(f, 0x01EEFF, db=0x01, push_db_frame=True)
            self.assertEqual(f.cpu.c, 1)
            self.assertEqual(f.get(0x0403), 0x40)
            self.assertEqual(f.get(0x7EF231), 0x40)
            self.assertEqual(f.get(0x7EF391), 0x08)
            self.assertEqual(f.get(0x000C), 0x40)
            self.assertEqual(f.get(0x012F), 0x0F)

            # 2. Same roll after claimed: no second Seashell; normal rupee & SFX3.$0E
            f.put(0x0410, 0x04)
            f.put(0x012F, 0x00)
            _run_long(f, 0x01EEFF, db=0x01, push_db_frame=True)
            self.assertEqual(f.get(0x7EF391), 0x08)
            self.assertIn(f.get(0x000C), (0x34, 0x47, 0x41, 0x40))
            self.assertEqual(f.get(0x012F), 0x0E)
        finally:
            f.close()

        # 3. Save & Quit protection ($0403 cleared, $7EF231 still set -> no second Seashell)
        f = self._fixture()
        try:
            f.put(0x0410, 0x00)
            f.put(0x0403, 0x00)
            f.put(0x7EF231, 0x40)
            f.put(0x7EF391, 0x05)
            _run_long(f, 0x01EEFF, db=0x01, push_db_frame=True)
            self.assertEqual(f.get(0x7EF391), 0x05)
            self.assertEqual(f.get(0x012F), 0x0E)
        finally:
            f.close()

        # 4. 99-Seashell cap doesn't wrap
        f = self._fixture()
        try:
            f.put(0x0410, 0x08)
            f.put(0x0403, 0x00)
            f.put(0x7EF231, 0x00)
            f.put(0x7EF391, 99)
            _run_long(f, 0x01EEFF, db=0x01, push_db_frame=True)
            self.assertEqual(f.get(0x7EF391), 99)
            self.assertEqual(f.get(0x0403), 0x40)
        finally:
            f.close()

        # 5. All 16 rolls after Seashell claimed cover the full 1/20/50/100 Rupee set
        seen = set()
        f = self._fixture()
        try:
            f.put(0x0403, 0x40)
            for roll in range(16):
                f.put(0x0410, roll)
                _run_long(f, 0x01EEFF, db=0x01, push_db_frame=True)
                prize = f.get(0x000C)
                self.assertIn(prize, (0x34, 0x47, 0x41, 0x40))
                seen.add(prize)
        finally:
            f.close()
        self.assertEqual(seen, {0x34, 0x47, 0x41, 0x40})


if __name__ == "__main__":
    unittest.main()
