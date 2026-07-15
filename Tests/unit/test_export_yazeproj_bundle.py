from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from Scripts.Generate.export_yazeproj_bundle import (
    copy_repo_snapshot,
    should_skip,
    write_ios_manifest,
    write_portable_hack_manifest,
)


class ShouldSkipTest(unittest.TestCase):
    def test_skips_canonical_evaluations_root(self) -> None:
        self.assertTrue(should_skip(Path("Evaluations")))
        self.assertTrue(should_skip(Path("Evaluations/results/report.json")))

    def test_skips_visual_test_artifacts(self) -> None:
        for directory in ("screenshots", "baselines", "baseline", "current", "diffs"):
            with self.subTest(directory=directory):
                self.assertTrue(should_skip(Path("Tests") / directory / "artifact.png"))

    def test_preserves_normal_test_and_project_files(self) -> None:
        for path in (
            Path("Tests/smoke/lint_pass.json"),
            Path("Tests/unit/test_validator.py"),
            Path("Docs/Planning/editor_plan.md"),
            Path("Sprites/Npcs/test_sprite.asm"),
        ):
            with self.subTest(path=path):
                self.assertFalse(should_skip(path))

    def test_skips_current_and_legacy_scratchpad_roots(self) -> None:
        self.assertTrue(should_skip(Path("Scratchpad/notes.md")))
        self.assertTrue(should_skip(Path("scratchpad/notes.md")))

    def test_skips_sensitive_cache_rom_and_archive_files(self) -> None:
        for path in (
            Path(".mcp.json"),
            Path(".env"),
            Path(".env.local"),
            Path("Scripts/__pycache__/tool.pyc"),
            Path("Assets/base.sfc"),
            Path("Saves/session.mss"),
            Path("output/source.zip"),
        ):
            with self.subTest(path=path):
                self.assertTrue(should_skip(path))


class CopyRepoSnapshotTest(unittest.TestCase):
    def test_copies_tracked_edits_but_not_untracked_host_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "repo"
            destination = Path(tmp) / "snapshot"
            root.mkdir()
            subprocess.run(["git", "init", "-q", str(root)], check=True)

            tracked = root / "Docs" / "README.md"
            tracked.parent.mkdir()
            tracked.write_text("indexed\n", encoding="utf-8")
            subprocess.run(["git", "-C", str(root), "add", str(tracked)], check=True)
            tracked.write_text("working tree edit\n", encoding="utf-8")

            (root / ".mcp.json").write_text("secret\n", encoding="utf-8")
            (root / ".env.local").write_text("TOKEN=secret\n", encoding="utf-8")
            cache = root / "Scripts" / "__pycache__" / "tool.pyc"
            cache.parent.mkdir(parents=True)
            cache.write_bytes(b"cache")
            (root / "untracked.asm").write_text("source\n", encoding="utf-8")

            copy_repo_snapshot(root, destination)

            self.assertEqual(
                (destination / "Docs" / "README.md").read_text(encoding="utf-8"),
                "working tree edit\n",
            )
            for rel in (".mcp.json", ".env.local", "Scripts/__pycache__", "untracked.asm"):
                with self.subTest(rel=rel):
                    self.assertFalse((destination / rel).exists())


class PortableHackManifestTest(unittest.TestCase):
    def test_rewrites_rom_lifecycle_and_build_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            source = root / "source.json"
            destination = root / "bundle" / "project" / "hack_manifest.json"
            source.write_text(
                json.dumps(
                    {
                        "build_pipeline": {
                            "dev_rom": "Roms/oos168.sfc",
                            "patched_rom": "Roms/oos168x.sfc",
                            "entry_point": "Oracle_main.asm",
                            "build_script": "Scripts/Build/build_rom.sh",
                        },
                        "rom": {
                            "path": "Roms/oos168.sfc",
                            "sha1": "old",
                            "size": 1,
                        },
                    }
                ),
                encoding="utf-8",
            )

            write_portable_hack_manifest(
                source,
                destination,
                "abc123",
                2_097_152,
            )

            manifest = json.loads(destination.read_text(encoding="utf-8"))
            self.assertEqual(manifest["build_pipeline"]["dev_rom"], "rom")
            self.assertEqual(
                manifest["build_pipeline"]["patched_rom"],
                "project/Roms/oos168x.sfc",
            )
            self.assertEqual(
                manifest["build_pipeline"]["entry_point"],
                "project/Oracle_main.asm",
            )
            self.assertEqual(manifest["rom"]["path"], "rom")
            self.assertEqual(manifest["rom"]["sha1"], "abc123")
            self.assertEqual(manifest["rom"]["dev_rom_sha1"], "abc123")
            self.assertEqual(manifest["rom"]["size"], 2_097_152)

    def test_ios_manifest_includes_z3ed_hash_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            bundle = Path(tmp)

            write_ios_manifest(bundle, "Oracle", "abc123")

            manifest = json.loads((bundle / "manifest.json").read_text())
            self.assertEqual(manifest["romChecksum"], "abc123")
            self.assertEqual(manifest["rom_sha1"], "abc123")


if __name__ == "__main__":
    unittest.main()
