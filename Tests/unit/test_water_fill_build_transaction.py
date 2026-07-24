from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from Scripts.Generate import generate_water_fill_table as water_fill


REPO_ROOT = Path(__file__).resolve().parents[2]
ROM_SIZE = 0x130000


def pc_to_lorom(pc: int) -> int:
    bank = (pc >> 15) & 0x7F
    address = (pc & 0x7FFF) | 0x8000
    return (bank << 16) | address


def make_authoring_rom(path: Path, rooms: tuple[int, ...]) -> None:
    data = bytearray(ROM_SIZE)
    pointer_table = water_fill.snes_to_pc(water_fill.ROOM_POINTER_SNES)
    for index, room_id in enumerate(rooms):
        stream_pc = water_fill.CUSTOM_COLLISION_DATA_PC_START + (index * 0x10)
        pointer_pc = pointer_table + (room_id * 3)
        data[pointer_pc : pointer_pc + 3] = pc_to_lorom(stream_pc).to_bytes(
            3, "little"
        )
        data[stream_pc : stream_pc + 7] = bytes(
            (0xF0, 0xF0, room_id, 0x01, 0xF5, 0xFF, 0xFF)
        )
    path.write_bytes(data)


def copy_repo_file(source_root: Path, target_root: Path, relative: str) -> None:
    source = source_root / relative
    target = target_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


class WaterFillBuildTransactionTest(unittest.TestCase):
    def prepare_fixture(self, root: Path) -> tuple[Path, Path]:
        repo = root / "oracle-of-secrets"
        repo.mkdir()

        for relative in (
            "Scripts/Build/build_rom.sh",
            "Scripts/Generate/generate_water_fill_table.py",
            "Scripts/Generate/generate_water_gate_runtime_tables.py",
            "Dungeons/generated/water_fill_table.asm",
            "Dungeons/generated/water_gate_runtime_tables.asm",
        ):
            copy_repo_file(REPO_ROOT, repo, relative)

        verifier = repo / "Scripts/Build/verify_feature_flags.py"
        verifier.write_text("print('Feature flags OK (transaction fixture).')\n")

        fake_asar = root / "fake-asar"
        fake_asar.write_text("#!/bin/sh\nexit 0\n")
        fake_asar.chmod(0o755)

        rom_dir = repo / "Roms"
        rom_dir.mkdir()
        base_data = bytes(ROM_SIZE)
        patched_data = bytearray(base_data)
        patched_data[0x40] = 0xA5  # Proves assemble_rom mutates the output.
        (rom_dir / "oos168.sfc").write_bytes(base_data)
        (rom_dir / "oos168x.sfc").write_bytes(patched_data)
        return repo, fake_asar

    def run_refresh(
        self, root: Path, repo: Path, fake_asar: Path, authoring_rom: Path
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "OOS_BACKUP_ROOT": str(root / "backups"),
                "OOS_REFRESH_WATER_TABLES": "1",
                "OOS_SKIP_MENU_VALIDATE": "1",
                "OOS_WATER_FILL_TABLE_ROM": str(authoring_rom),
            }
        )
        return subprocess.run(
            [
                str(repo / "Scripts/Build/build_rom.sh"),
                "168",
                str(fake_asar),
                "--no-symbols",
                "--skip-tests",
            ],
            cwd=repo,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def assert_transaction_restored(
        self,
        repo: Path,
        patched_before: bytes,
        fill_before: bytes,
        runtime_before: bytes,
    ) -> None:
        self.assertEqual((repo / "Roms/oos168x.sfc").read_bytes(), patched_before)
        self.assertEqual(
            (repo / "Dungeons/generated/water_fill_table.asm").read_bytes(),
            fill_before,
        )
        self.assertEqual(
            (repo / "Dungeons/generated/water_gate_runtime_tables.asm").read_bytes(),
            runtime_before,
        )

    def test_failed_generation_restores_patched_rom_and_tracked_tables(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            authoring_rom = root / "authoring-missing-room27.sfc"
            make_authoring_rom(authoring_rom, (0x25,))

            patched_before = (repo / "Roms/oos168x.sfc").read_bytes()
            fill_before = (
                repo / "Dungeons/generated/water_fill_table.asm"
            ).read_bytes()
            runtime_before = (
                repo / "Dungeons/generated/water_gate_runtime_tables.asm"
            ).read_bytes()

            result = self.run_refresh(root, repo, fake_asar, authoring_rom)

            combined_output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Required water-fill rooms have no marker tiles: 0x27",
                combined_output,
            )
            self.assertIn(
                "Restored water includes and patched ROM after failed refresh",
                combined_output,
            )
            self.assert_transaction_restored(
                repo, patched_before, fill_before, runtime_before
            )

    def test_failed_post_stage_check_restores_patched_rom_and_tracked_tables(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            authoring_rom = root / "authoring-complete.sfc"
            make_authoring_rom(authoring_rom, (0x25, 0x27))

            post_stage_check = repo / "Scripts/Build/check_zscream_overlap.py"
            post_stage_check.write_text(
                "import sys\nprint('intentional post-stage failure')\nsys.exit(23)\n"
            )

            patched_before = (repo / "Roms/oos168x.sfc").read_bytes()
            fill_before = (
                repo / "Dungeons/generated/water_fill_table.asm"
            ).read_bytes()
            runtime_before = (
                repo / "Dungeons/generated/water_gate_runtime_tables.asm"
            ).read_bytes()

            result = self.run_refresh(root, repo, fake_asar, authoring_rom)

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 23, combined_output)
            self.assertIn("Water table candidates staged", combined_output)
            self.assertIn("intentional post-stage failure", combined_output)
            self.assertIn(
                "Restored water includes and patched ROM after failed refresh",
                combined_output,
            )
            self.assert_transaction_restored(
                repo, patched_before, fill_before, runtime_before
            )


if __name__ == "__main__":
    unittest.main()
