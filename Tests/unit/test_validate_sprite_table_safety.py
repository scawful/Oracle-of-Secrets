from __future__ import annotations

import unittest

from Scripts.Validate.validate_sprite_table_safety import (
    CANONICAL_SENTINEL,
    LOAD_PROPERTIES_SENTINEL,
    MAIN_OVERFLOW_START,
    PREP_OVERFLOW_START,
    TWINROVA_HOOK_SIZE,
    snes_to_pc,
    validate_sprite_table_safety,
)


class SpriteTableSafetyTest(unittest.TestCase):
    def make_roms(self) -> tuple[bytearray, bytearray]:
        size = snes_to_pc(LOAD_PROPERTIES_SENTINEL) + len(CANONICAL_SENTINEL)
        base = bytearray(size)
        sentinel = snes_to_pc(LOAD_PROPERTIES_SENTINEL)
        base[sentinel : sentinel + len(CANONICAL_SENTINEL)] = CANONICAL_SENTINEL
        patched = bytearray(base)
        prep = snes_to_pc(PREP_OVERFLOW_START)
        patched[prep : prep + TWINROVA_HOOK_SIZE] = bytes.fromhex("22 6D A8 32 60")
        return base, patched

    def test_accepts_only_documented_prep_hook(self) -> None:
        base, patched = self.make_roms()

        self.assertEqual(validate_sprite_table_safety(base, patched), [])

    def test_rejects_main_overflow_change(self) -> None:
        base, patched = self.make_roms()
        patched[snes_to_pc(MAIN_OVERFLOW_START) + 4] ^= 0xFF

        errors = validate_sprite_table_safety(base, patched)

        self.assertTrue(any("main pointer overflow" in error for error in errors))
        self.assertTrue(any("$06946D" in error for error in errors))

    def test_rejects_prep_change_outside_hook(self) -> None:
        base, patched = self.make_roms()
        patched[snes_to_pc(PREP_OVERFLOW_START) + TWINROVA_HOOK_SIZE] ^= 0xFF

        errors = validate_sprite_table_safety(base, patched)

        self.assertTrue(any("outside the allowed" in error for error in errors))
        self.assertTrue(any("$068846" in error for error in errors))

    def test_rejects_malformed_prep_hook(self) -> None:
        base, patched = self.make_roms()
        patched[snes_to_pc(PREP_OVERFLOW_START)] = 0xEA

        errors = validate_sprite_table_safety(base, patched)

        self.assertTrue(any("not a LoROM JSL" in error for error in errors))

    def test_rejects_wram_prep_hook_targets(self) -> None:
        for bank in (0x7E, 0x7F, 0xFE, 0xFF):
            with self.subTest(bank=bank):
                base, patched = self.make_roms()
                prep = snes_to_pc(PREP_OVERFLOW_START)
                patched[prep : prep + TWINROVA_HOOK_SIZE] = bytes(
                    (0x22, 0x00, 0x80, bank, 0x60)
                )

                errors = validate_sprite_table_safety(base, patched)

                self.assertTrue(any("not a LoROM JSL" in error for error in errors))

    def test_rejects_changed_sentinel(self) -> None:
        base, patched = self.make_roms()
        patched[snes_to_pc(LOAD_PROPERTIES_SENTINEL) + 2] ^= 0xFF

        errors = validate_sprite_table_safety(base, patched)

        self.assertTrue(any("patched ROM sentinel" in error for error in errors))

    def test_rejects_truncated_rom(self) -> None:
        base, patched = self.make_roms()

        errors = validate_sprite_table_safety(base[:100], patched)

        self.assertEqual(len(errors), 1)
        self.assertIn("too small", errors[0])


if __name__ == "__main__":
    unittest.main()
