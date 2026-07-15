from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from Scripts.Validate.validate_sprite_table_safety import (
    CANONICAL_SENTINEL,
    LOAD_PROPERTIES_SENTINEL,
    MAIN_OVERFLOW_START,
    PREP_OVERFLOW_START,
    TWINROVA_HOOK_SIZE,
    resolve_base_rom_path,
    snes_to_pc,
    validate_sprite_table_safety,
)


class SpriteTableSafetyTest(unittest.TestCase):
    def test_default_base_rom_resolves_from_repo_root(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "project"
            base_rom = repo_root / "Roms/oos168.sfc"
            base_rom.parent.mkdir(parents=True)
            base_rom.write_bytes(b"default")

            resolved = resolve_base_rom_path(None, repo_root=repo_root, environ={})

            self.assertEqual(resolved, base_rom.resolve())
            self.assertEqual(resolved.read_bytes(), b"default")

    def test_portable_env_base_rom_resolves_from_repo_root(self) -> None:
        with TemporaryDirectory() as tmp:
            bundle_root = Path(tmp) / "Oracle.yazeproj"
            repo_root = bundle_root / "project"
            unrelated_cwd = Path(tmp) / "caller"
            portable_rom = bundle_root / "rom"
            fallback_rom = repo_root / "Roms/oos168.sfc"
            fallback_rom.parent.mkdir(parents=True)
            fallback_rom.write_bytes(b"fallback")
            portable_rom.write_bytes(b"portable")

            resolved = resolve_base_rom_path(
                None,
                repo_root=repo_root,
                caller_cwd=unrelated_cwd,
                environ={"OOS_BASE_ROM": "../rom"},
            )

            self.assertEqual(resolved, portable_rom.resolve())
            self.assertEqual(resolved.read_bytes(), b"portable")

    def test_explicit_relative_base_rom_keeps_caller_semantics(self) -> None:
        with TemporaryDirectory() as tmp:
            repo_root = Path(tmp) / "project"
            caller_cwd = Path(tmp) / "caller"

            resolved = resolve_base_rom_path(
                Path("fixtures/base.sfc"),
                repo_root=repo_root,
                caller_cwd=caller_cwd,
                environ={"OOS_BASE_ROM": "ignored.sfc"},
            )

            self.assertEqual(resolved, (caller_cwd / "fixtures/base.sfc").resolve())

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
