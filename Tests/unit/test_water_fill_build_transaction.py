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

        manifest_generator = (
            repo / "Scripts/Generate/generate_hack_manifest.py"
        )
        manifest_generator.write_text(
            """\
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index("--output") + 1])
output.write_text('{"fixture": "manifest"}\\n', encoding="utf-8")
"""
        )

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
        self,
        root: Path,
        repo: Path,
        fake_asar: Path,
        authoring_rom: Path | None,
        *,
        emit_symbols: bool = False,
        extra_env: dict[str, str] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        for name in (
            "OOS_GENERATE_HOOKS",
            "OOS_VALIDATE_HOOKS",
            "OOS_VALIDATE_ON_BUILD",
            "OOS_WATER_FILL_TABLE_ROM",
            "OOS_WATER_TABLE_ROM",
        ):
            env.pop(name, None)
        env.update(
            {
                "OOS_BACKUP_ROOT": str(root / "backups"),
                "OOS_REFRESH_WATER_TABLES": "1",
                "OOS_SKIP_MENU_VALIDATE": "1",
                "SKIP_ANALYSIS": "1",
            }
        )
        if authoring_rom is not None:
            env["OOS_WATER_FILL_TABLE_ROM"] = str(authoring_rom)
        if extra_env is not None:
            env.update(extra_env)

        command = [
            str(repo / "Scripts/Build/build_rom.sh"),
            "168",
            str(fake_asar),
        ]
        if not emit_symbols:
            command.append("--no-symbols")
        command.append("--skip-tests")
        return subprocess.run(
            command,
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

    def test_refresh_without_authoring_rom_uses_newly_assembled_patched_rom(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            patched_rom = repo / "Roms/oos168x.sfc"
            patched_rom.unlink()

            stable_generator = """\
import argparse
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--rom", required=True)
parser.add_argument("--out-asm", required=True)
args, _ = parser.parse_known_args()
source = Path(args.rom)
if not source.is_file():
    raise SystemExit(f"authoring ROM missing: {source}")
Path(args.out_asm).write_text(
    "; stable transaction fixture\\n"
    "  db $25, $00\\n"
    "  db $27, $00\\n"
)
print(f"stub generated from {source}")
"""
            for relative in (
                "Scripts/Generate/generate_water_fill_table.py",
                "Scripts/Generate/generate_water_gate_runtime_tables.py",
            ):
                (repo / relative).write_text(stable_generator)

            overlap_check = repo / "Scripts/Build/check_zscream_overlap.py"
            overlap_check.write_text("print('overlap fixture passed')\n")

            result = self.run_refresh(root, repo, fake_asar, None)

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertTrue(patched_rom.is_file())
            self.assertEqual(
                patched_rom.read_bytes(),
                (repo / "Roms/oos168.sfc").read_bytes(),
            )
            self.assertIn("stub generated from Roms/oos168x.sfc", combined_output)
            self.assertIn("Water table pair promoted", combined_output)

    def test_failed_overlap_restores_preexisting_symbol_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            authoring_rom = root / "authoring-complete.sfc"
            make_authoring_rom(authoring_rom, (0x25, 0x27))

            fake_asar.write_text(
                """#!/bin/sh
symbols_path=""
for arg in "$@"; do
  case "$arg" in
    --symbols-path=*) symbols_path="${arg#--symbols-path=}" ;;
  esac
done
if [ -n "$symbols_path" ]; then
  mkdir -p "$(dirname "$symbols_path")"
  printf 'new symbols from fake asar\\n' > "$symbols_path"
fi
exit 0
"""
            )

            export_symbols = repo / "Scripts/Generate/export_symbols.py"
            export_symbols.write_text(
                """\
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index("-o") + 1])
output.write_text("new labels from export fixture\\n")
print("symbol export fixture ran")
"""
            )

            post_stage_check = repo / "Scripts/Build/check_zscream_overlap.py"
            post_stage_check.write_text(
                "import sys\nprint('intentional symbol-stage failure')\nsys.exit(23)\n"
            )

            symbols_path = repo / "Roms/oos168x.sym"
            mlb_path = repo / "Roms/oos168x.mlb"
            symbols_before = b"preexisting symbols\n"
            mlb_before = b"preexisting labels\n"
            symbols_path.write_bytes(symbols_before)
            mlb_path.write_bytes(mlb_before)

            result = self.run_refresh(
                root, repo, fake_asar, authoring_rom, emit_symbols=True
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 23, combined_output)
            self.assertIn("symbol export fixture ran", combined_output)
            self.assertIn("intentional symbol-stage failure", combined_output)
            self.assertIn(
                "Restored water includes and patched ROM after failed refresh",
                combined_output,
            )
            self.assertEqual(symbols_path.read_bytes(), symbols_before)
            self.assertEqual(mlb_path.read_bytes(), mlb_before)

    def test_failed_explicit_hook_validation_restores_preexisting_hooks(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            authoring_rom = root / "authoring-complete.sfc"
            make_authoring_rom(authoring_rom, (0x25, 0x27))

            overlap_check = repo / "Scripts/Build/check_zscream_overlap.py"
            overlap_check.write_text("print('overlap fixture passed')\n")

            hook_generator = repo / "Scripts/Generate/generate_hooks_json.py"
            hook_generator.write_text(
                """\
import sys
from pathlib import Path

output = Path(sys.argv[sys.argv.index("--output") + 1])
output.write_text('{"fixture": "new"}\\n')
print("hook generation fixture ran")
"""
            )
            hook_verifier = repo / "Scripts/Validate/verify_hooks_json.py"
            hook_verifier.parent.mkdir(parents=True, exist_ok=True)
            hook_verifier.write_text(
                "import sys\nprint('intentional hook validation failure')\nsys.exit(29)\n"
            )

            hooks_path = repo / "Roms/hooks.json"
            hooks_before = b'{"fixture": "preexisting"}\n'
            hooks_path.write_bytes(hooks_before)

            result = self.run_refresh(
                root,
                repo,
                fake_asar,
                authoring_rom,
                extra_env={
                    "OOS_GENERATE_HOOKS": "1",
                    "OOS_VALIDATE_HOOKS": "1",
                },
            )

            combined_output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined_output)
            self.assertIn("hook generation fixture ran", combined_output)
            self.assertIn("intentional hook validation failure", combined_output)
            self.assertIn(
                "Restored water includes and patched ROM after failed refresh",
                combined_output,
            )
            self.assertEqual(hooks_path.read_bytes(), hooks_before)

    def test_failed_manifest_generation_preserves_manifest_and_rolls_back_water(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_fixture(root)
            authoring_rom = root / "authoring-complete.sfc"
            make_authoring_rom(authoring_rom, (0x25, 0x27))

            overlap_check = repo / "Scripts/Build/check_zscream_overlap.py"
            overlap_check.write_text("print('overlap fixture passed')\n")

            manifest_path = repo / "Roms/hack_manifest.json"
            manifest_before = b'{"fixture": "preexisting"}\n'
            manifest_path.write_bytes(manifest_before)
            (repo / "Scripts/Generate/generate_hack_manifest.py").write_text(
                "import sys\nprint('intentional manifest failure')\nsys.exit(37)\n"
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
            self.assertNotEqual(result.returncode, 0, combined_output)
            self.assertIn("intentional manifest failure", combined_output)
            self.assertIn(
                "ERROR: Required hack manifest generation failed.",
                combined_output,
            )
            self.assertIn(
                "Restored water includes and patched ROM after failed refresh",
                combined_output,
            )
            self.assert_transaction_restored(
                repo, patched_before, fill_before, runtime_before
            )
            self.assertEqual(manifest_path.read_bytes(), manifest_before)


if __name__ == "__main__":
    unittest.main()
