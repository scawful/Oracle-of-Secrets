"""Compiled-data checks must detect rain, music loss, and overbroad muting."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import unittest


SCRIPT = Path(__file__).resolve().parents[1] / "validate_intro_ambience.py"
spec = importlib.util.spec_from_file_location("validate_intro_ambience", SCRIPT)
validator = importlib.util.module_from_spec(spec)
spec.loader.exec_module(validator)


class IntroAmbienceTests(unittest.TestCase):
    def setUp(self):
        self.base = bytearray(validator.TABLE_PC + validator.TABLE_SIZE)
        start = validator.TABLE_PC
        # Give every music ID a rain entry; leave another ambient command in
        # phase 00 and intentional rain in later phases and special areas.
        self.base[start:start + 16] = bytes(range(0x10, 0x20))
        self.base[start + 0x23] = 0x17
        self.base[start + 0x30] = 0x97
        self.base[start + 0x40] = 0x13
        self.base[start + 0x15F] = 0x12
        self.fixed = self.base.copy()
        self.fixed[start:start + 16] = bytes(range(0x50, 0x60))
        self.fixed[start + 0x23] = 0x57

    def test_silence_preserves_every_music_id_and_other_ambient_commands(self):
        self.assertEqual(validator.check_ambience(self.base, self.fixed), [])

    def test_original_rom_fails_including_wayward_village(self):
        issues = validator.check_ambience(self.base, self.base)
        self.assertEqual(len(issues), 17)
        self.assertIn("$02C326: base $17, expected $57, got $17", issues)

    def test_zero_command_is_not_silence(self):
        self.fixed[validator.TABLE_PC + 0x23] = 0x07
        self.assertEqual(len(validator.check_ambience(self.base, self.fixed)), 1)

    def test_music_change_is_rejected(self):
        for index in (0x23, 0x31, 0x40, 0x15F):
            with self.subTest(index=index):
                rom = self.fixed.copy()
                rom[validator.TABLE_PC + index] ^= 1
                self.assertEqual(len(validator.check_ambience(self.base, rom)), 1)

    def test_muting_other_ambience_is_rejected(self):
        for index in (0x30, 0x40, 0x15F):
            with self.subTest(index=index):
                rom = self.fixed.copy()
                rom[validator.TABLE_PC + index] = 0x50 | (rom[validator.TABLE_PC + index] & 15)
                self.assertEqual(len(validator.check_ambience(self.base, rom)), 1)

    def test_truncated_input_is_rejected(self):
        for base, rom in ((b"", self.fixed), (self.base, self.fixed[:-1])):
            with self.assertRaises(ValueError):
                validator.check_ambience(base, rom)


if __name__ == "__main__":
    unittest.main()
