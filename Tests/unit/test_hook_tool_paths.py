from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

from Scripts.Validate.verify_hooks_json import _run_generator


REPO_ROOT = Path(__file__).resolve().parents[2]
HOOK_GENERATOR = REPO_ROOT / "Scripts" / "Generate" / "generate_hooks_json.py"
ROM_SIZE = 0x130000
SUCCESSFUL_HOOK_GENERATOR = textwrap.dedent(
    """\
    import sys
    from pathlib import Path

    output = Path(sys.argv[sys.argv.index("--output") + 1])
    output.write_text('{"hooks": []}\\n', encoding="utf-8")
    """
)


def copy_repo_file(target_root: Path, relative: str) -> None:
    source = REPO_ROOT / relative
    target = target_root / relative
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, target)


class HookToolPathTest(unittest.TestCase):
    def prepare_build_fixture(
        self, root: Path, *, generator_source: str, verifier_source: str
    ) -> tuple[Path, Path]:
        repo = root / "oracle-of-secrets"
        repo.mkdir()
        for relative in (
            "Scripts/Build/build_rom.sh",
            "Dungeons/generated/water_fill_table.asm",
            "Dungeons/generated/water_gate_runtime_tables.asm",
        ):
            copy_repo_file(repo, relative)

        scripts = {
            "Scripts/Build/verify_feature_flags.py": "print('flags ok')\n",
            "Scripts/Build/check_zscream_overlap.py": "print('overlap ok')\n",
            "Scripts/Build/set_feature_flags.py": textwrap.dedent(
                """\
                import sys
                from pathlib import Path

                output = Path(sys.argv[sys.argv.index("--output") + 1])
                output.parent.mkdir(parents=True, exist_ok=True)
                output.write_text("!ENABLE_FIXTURE = 1\\n", encoding="utf-8")
                """
            ),
            "Scripts/Generate/generate_hooks_json.py": generator_source,
            "Scripts/Generate/generate_hack_manifest.py": textwrap.dedent(
                """\
                import sys
                from pathlib import Path

                output = Path(sys.argv[sys.argv.index("--output") + 1])
                output.write_text('{"fixture": "manifest"}\\n', encoding="utf-8")
                """
            ),
            "Scripts/Validate/verify_hooks_json.py": verifier_source,
            "Scripts/Validate/validate_sprite_registry.py": "print('sprites ok')\n",
        }
        for relative, source in scripts.items():
            path = repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(source, encoding="utf-8")

        rom_dir = repo / "Roms"
        rom_dir.mkdir()
        (rom_dir / "oos168.sfc").write_bytes(bytes(ROM_SIZE))

        fake_asar = root / "fake-asar"
        fake_asar.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        fake_asar.chmod(0o755)
        return repo, fake_asar

    def run_fixture_build(
        self,
        root: Path,
        repo: Path,
        fake_asar: Path,
        *,
        version: str = "168",
        extra_args: tuple[str, ...] = (),
        **overrides: str,
    ) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        env.update(
            {
                "OOS_BACKUP_ROOT": str(root / "backups"),
                "OOS_SKIP_MENU_VALIDATE": "1",
                "SKIP_ANALYSIS": "1",
                **overrides,
            }
        )
        return subprocess.run(
            [
                str(repo / "Scripts/Build/build_rom.sh"),
                version,
                str(fake_asar),
                *extra_args,
                "--no-symbols",
                "--skip-tests",
            ],
            cwd=repo,
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_verifier_uses_categorized_generator_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            generator = root / "Scripts" / "Generate" / "generate_hooks_json.py"
            generator.parent.mkdir(parents=True)
            generator.write_text(
                textwrap.dedent(
                    """\
                    import argparse
                    import json

                    parser = argparse.ArgumentParser()
                    parser.add_argument("--root")
                    parser.add_argument("--output")
                    parser.add_argument("--rom")
                    args = parser.parse_args()
                    with open(args.output, "w", encoding="utf-8") as handle:
                        json.dump({"hooks": []}, handle)
                    """
                ),
                encoding="utf-8",
            )
            output = root / "generated.json"

            _run_generator(root, root / "rom.sfc", output)

            self.assertEqual(
                json.loads(output.read_text(encoding="utf-8")), {"hooks": []}
            )
            self.assertFalse((root / "scripts" / "generate_hooks_json.py").exists())

    def test_generator_canonicalizes_absolute_rom_path_before_relativizing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            temp_root = Path(tmp)
            real_root = temp_root / "real"
            alias_root = temp_root / "alias"
            rom = real_root / "Roms" / "test.sfc"
            rom.parent.mkdir(parents=True)
            rom.write_bytes(b"test-rom")
            (real_root / "test.asm").write_text("org $008000\nnop\n", encoding="utf-8")

            try:
                os.symlink(real_root, alias_root, target_is_directory=True)
            except (OSError, NotImplementedError) as exc:
                self.skipTest(f"directory symlinks unavailable: {exc}")

            output = temp_root / "hooks.json"
            result = subprocess.run(
                [
                    sys.executable,
                    str(HOOK_GENERATOR),
                    "--root",
                    str(alias_root),
                    "--rom",
                    str(alias_root / "Roms" / "test.sfc"),
                    "--output",
                    str(output),
                ],
                cwd=REPO_ROOT,
                text=True,
                capture_output=True,
            )

            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            metadata = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(metadata["rom"]["path"], "Roms/test.sfc")

    def test_hook_generation_failure_is_fatal_only_when_explicit(self) -> None:
        generator = "import sys\nsys.exit(23)\n"
        verifier = "print('verification should not run')\n"
        for explicit in (False, True):
            with self.subTest(explicit=explicit), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, fake_asar = self.prepare_build_fixture(
                    root, generator_source=generator, verifier_source=verifier
                )
                overrides = {"OOS_GENERATE_HOOKS": "1"} if explicit else {}

                result = self.run_fixture_build(
                    root, repo, fake_asar, **overrides
                )

                combined_output = result.stdout + result.stderr
                if explicit:
                    self.assertNotEqual(result.returncode, 0, combined_output)
                    self.assertIn(
                        "ERROR: Required hooks.json generation failed.",
                        combined_output,
                    )
                else:
                    self.assertEqual(result.returncode, 0, combined_output)
                    self.assertIn(
                        "Warning: hooks.json generation failed", combined_output
                    )
                self.assertFalse((repo / "Roms/hooks.json").exists())

    def test_explicit_hook_generation_requires_nonempty_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source="print('intentionally no output')\n",
                verifier_source="print('verification should not run')\n",
            )
            hooks_path = repo / "Roms/hooks.json"
            stale_hooks = '{"stale": true}\n'
            hooks_path.write_text(stale_hooks, encoding="utf-8")

            result = self.run_fixture_build(
                root, repo, fake_asar, OOS_GENERATE_HOOKS="1"
            )

            combined_output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined_output)
            self.assertIn(
                "ERROR: Required hooks.json generation produced no output:",
                combined_output,
            )
            self.assertEqual(hooks_path.read_text(encoding="utf-8"), stale_hooks)

    def test_hook_validation_failure_is_fatal_only_when_explicit(self) -> None:
        generator = textwrap.dedent(
            """\
            import argparse
            from pathlib import Path

            parser = argparse.ArgumentParser()
            parser.add_argument("--root")
            parser.add_argument("--output")
            parser.add_argument("--rom")
            args = parser.parse_args()
            Path(args.output).write_text('{"hooks": []}\\n', encoding="utf-8")
            """
        )
        verifier = "import sys\nsys.exit(24)\n"
        for explicit in (False, True):
            with self.subTest(explicit=explicit), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                repo, fake_asar = self.prepare_build_fixture(
                    root, generator_source=generator, verifier_source=verifier
                )
                flag = (
                    {"OOS_VALIDATE_HOOKS": "1"}
                    if explicit
                    else {"OOS_VALIDATE_ON_BUILD": "1"}
                )

                result = self.run_fixture_build(root, repo, fake_asar, **flag)

                combined_output = result.stdout + result.stderr
                if explicit:
                    self.assertNotEqual(result.returncode, 0, combined_output)
                    self.assertIn(
                        "ERROR: Required hooks.json validation failed.",
                        combined_output,
                    )
                else:
                    self.assertEqual(result.returncode, 0, combined_output)
                    self.assertIn(
                        "Warning: hooks.json validation failed", combined_output
                    )

    def test_manifest_generation_failure_preserves_tracked_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            manifest_path = repo / "Roms" / "hack_manifest.json"
            original_manifest = '{"fixture": "preexisting"}\n'
            manifest_path.write_text(original_manifest, encoding="utf-8")
            (repo / "Scripts/Generate/generate_hack_manifest.py").write_text(
                "import sys\nsys.exit(31)\n",
                encoding="utf-8",
            )
            reload_marker = root / "reload-ran"
            mesen_client = repo / "Scripts/Mesen2/mesen2_client.py"
            mesen_client.parent.mkdir(parents=True, exist_ok=True)
            mesen_client.write_text(
                "from pathlib import Path\n"
                f"Path({str(reload_marker)!r}).write_text('ran')\n",
                encoding="utf-8",
            )

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                extra_args=("--reload",),
            )

            combined_output = result.stdout + result.stderr
            self.assertNotEqual(result.returncode, 0, combined_output)
            self.assertIn(
                "ERROR: Required hack manifest generation failed.",
                combined_output,
            )
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                original_manifest,
            )
            self.assertFalse(reload_marker.exists())

    def test_external_base_rom_preserves_portable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            external_base = root / "portable-bundle-rom.sfc"
            external_base.write_bytes((repo / "Roms/oos168.sfc").read_bytes())
            manifest_path = repo / "Roms/hack_manifest.json"
            portable_manifest = '{"rom": {"path": "rom"}}\n'
            manifest_path.write_text(portable_manifest, encoding="utf-8")

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                OOS_BASE_ROM=str(external_base),
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertIn(
                "Preserving existing hack manifest because the build used a "
                "non-canonical base ROM.",
                combined_output,
            )
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                portable_manifest,
            )

    def test_temporary_feature_flags_do_not_replace_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            manifest_path = repo / "Roms/hack_manifest.json"
            original_manifest = '{"fixture": "default-flags"}\n'
            manifest_path.write_text(original_manifest, encoding="utf-8")

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                extra_args=("--enable", "fixture"),
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertIn(
                "Preserving existing hack manifest because feature-flag "
                "overrides are temporary.",
                combined_output,
            )
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                original_manifest,
            )
            self.assertFalse((repo / "Config/feature_flags.asm").exists())

    def test_non_project_rom_version_does_not_replace_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            (repo / "Roms/oos167.sfc").write_bytes(
                (repo / "Roms/oos168.sfc").read_bytes()
            )
            manifest_path = repo / "Roms/hack_manifest.json"
            original_manifest = '{"fixture": "version-168"}\n'
            manifest_path.write_text(original_manifest, encoding="utf-8")

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                version="167",
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertIn(
                "Preserving existing hack manifest because build version 167 "
                "is not the project ROM version 168.",
                combined_output,
            )
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                original_manifest,
            )

    def test_persisted_feature_flags_remove_temporary_backup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            feature_flags = repo / "Config/feature_flags.asm"
            feature_flags.parent.mkdir(parents=True)
            feature_flags.write_text("!ENABLE_FIXTURE = 0\n", encoding="utf-8")

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                extra_args=("--enable", "fixture", "--persist-flags"),
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 0, combined_output)
            self.assertEqual(
                feature_flags.read_text(encoding="utf-8"),
                "!ENABLE_FIXTURE = 1\n",
            )
            self.assertEqual(
                list((repo / "Roms").glob(".feature_flags_backup.*")),
                [],
            )

    def test_reload_failure_happens_after_manifest_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            repo, fake_asar = self.prepare_build_fixture(
                root,
                generator_source=SUCCESSFUL_HOOK_GENERATOR,
                verifier_source="print('hooks valid')\n",
            )
            manifest_path = repo / "Roms/hack_manifest.json"
            manifest_path.write_text(
                '{"fixture": "preexisting"}\n',
                encoding="utf-8",
            )
            mesen_client = repo / "Scripts/Mesen2/mesen2_client.py"
            mesen_client.parent.mkdir(parents=True, exist_ok=True)
            mesen_client.write_text(
                "import sys\n"
                "from pathlib import Path\n"
                "root = Path(__file__).resolve().parents[2]\n"
                "manifest = (root / 'Roms/hack_manifest.json').read_text()\n"
                "print(f'reload observed: {manifest.strip()}')\n"
                "sys.exit(44)\n",
                encoding="utf-8",
            )

            result = self.run_fixture_build(
                root,
                repo,
                fake_asar,
                extra_args=("--reload",),
            )

            combined_output = result.stdout + result.stderr
            self.assertEqual(result.returncode, 44, combined_output)
            self.assertIn(
                'reload observed: {"fixture": "manifest"}',
                combined_output,
            )
            self.assertEqual(
                manifest_path.read_text(encoding="utf-8"),
                '{"fixture": "manifest"}\n',
            )


if __name__ == "__main__":
    unittest.main()
