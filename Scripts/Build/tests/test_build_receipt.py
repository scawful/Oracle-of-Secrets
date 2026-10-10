"""Receipt identity, failure propagation and actual-profile regressions."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock

SPEC = importlib.util.spec_from_file_location(
    "build_receipt", Path(__file__).resolve().parents[1] / "build_receipt.py")
receipt = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(receipt)


class BuildReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        # Production scratch roots are also below .context.
        self.root = Path(self.temporary.name) / ".context" / "src"
        self.root.mkdir(parents=True)
        self.put("Oracle_main.asm", 'incsrc "Util/macros.asm"\nincsrc "Config/feature_flags.asm"\n')
        self.put("Util/macros.asm", "!ENABLE_TEST = 0\n!DISABLE_MUSIC = 0\n")
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = 0\n")
        self.put("Config/module_flags.asm", "!DISABLE_MUSIC = 1\n")
        self.put("Core/main.asm", 'incbin "gfx/boat.bin"\n')
        self.put("Core/gfx/boat.bin", b"boat pixels")
        self.put("Scripts/Generate/generate.py", "print('generated')\n")
        self.put("Tests/smoke/current_state.json", '{"steps": []}\n')
        self.base = self.put("Roms/base.sfc", b"immutable base")
        self.output = self.root / "Roms" / "receipt.json"

    def put(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content if isinstance(content, bytes) else content.encode())
        return path

    def command(self, command, *args):
        return receipt.main([command, "--receipt", str(self.output), *map(str, args)])

    def initialize(self, base=None):
        return self.command("init", "--root", self.root, "--base-rom", base or self.base,
                            "--version", "168", "--requested-profile", "rc-explicit",
                            "--assembler", "/test/asar")

    def read(self):
        return json.loads(self.output.read_text())

    def check(self, status, required):
        return self.command("check", "--name", "smoke", "--status", status,
                            "--required", int(required), "--detail", "fixture outcome")

    def finish(self, code=0, stage="completed"):
        return self.command("finish", "--exit-code", code, "--stage", stage)

    def snapshot(self):
        self.assertEqual(self.command("snapshot", "--phase", "pre_assembly"), 0)

    def test_missing_base_keeps_actionable_receipt_and_cannot_finish_successfully(self):
        self.assertEqual(self.initialize(self.root / "missing.sfc"), 0)
        self.assertEqual(self.read()["state"], "in_progress")
        self.assertEqual(self.read()["checks"][0]["status"], "unavailable")
        self.assertEqual(self.finish(), 1)
        self.assertEqual(self.read()["state"], "failed")

    def test_each_required_nonpass_blocks_success(self):
        for status in ("failed", "unavailable", "skipped"):
            with self.subTest(status=status):
                self.assertEqual(self.initialize(), 0)
                self.snapshot()
                self.assertEqual(self.check(status, True), 0)
                self.assertEqual(self.finish(), 1)
                final = self.read()
                self.assertEqual(final["state"], "failed")
                self.assertIn("smoke", final["finish"]["required_gaps"])

    def test_optional_nonpasses_are_visible_gaps(self):
        for status in ("failed", "unavailable", "skipped"):
            with self.subTest(status=status):
                self.initialize()
                self.snapshot()
                self.check(status, False)
                self.assertEqual(self.finish(), 0)
                self.assertEqual(self.read()["state"], "completed_with_gaps")

    def test_passes_and_explicit_failure_have_distinct_states(self):
        self.initialize()
        self.snapshot()
        self.check("passed", True)
        self.assertEqual(self.finish(), 0)
        self.assertEqual(self.read()["state"], "completed")
        self.initialize()
        self.assertEqual(self.finish(7, "assembler"), 7)
        final = self.read()
        self.assertEqual(final["state"], "failed")
        self.assertEqual(final["finish"]["stage"], "assembler")
        self.assertEqual(final["finish"]["supplied_exit_code"], 7)
        self.assertEqual(final["source_snapshot_status"], "not_reached")
        self.assertNotIn("source_snapshot", final["finish"]["required_gaps"])

    def test_success_without_source_snapshot_is_rejected(self):
        self.initialize()
        self.assertEqual(self.finish(), 1)
        self.assertIn("source_snapshot", self.read()["finish"]["required_gaps"])
        self.assertEqual(self.read()["source_snapshot_status"], "not_reached")

    def test_failure_cannot_be_hidden_by_a_later_pass(self):
        self.initialize()
        self.snapshot()
        self.check("failed", True)
        self.check("passed", True)
        self.assertEqual(self.finish(), 1)
        self.assertEqual(len(self.read()["checks"]), 2)

    def test_preassembly_profile_survives_flag_restoration(self):
        self.initialize()
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = 1\n")
        self.assertEqual(self.command("snapshot", "--phase", "pre_assembly"), 0)
        snap = self.read()["snapshots"]["pre_assembly"]
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = 0\n")
        self.assertEqual(self.finish(), 0)
        final = self.read()
        self.assertEqual(final["initial_profile"]["effective_flags"]["ENABLE_TEST"], 0)
        self.assertEqual(final["snapshots"]["pre_assembly"], snap)
        self.assertEqual(snap["profile"]["effective_flags"]["ENABLE_TEST"], 1)
        self.assertEqual(snap["profile"]["effective_flags"]["DISABLE_MUSIC"], 1)
        self.assertNotEqual(snap["profile"]["files"]["Config/feature_flags.asm"]["sha256"],
                            receipt.identity(self.root / "Config/feature_flags.asm")["sha256"])

    def test_originally_absent_flags_may_be_restored_by_removal(self):
        flags = self.root / "Config/feature_flags.asm"
        flags.unlink()
        self.initialize()
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = 1\n")
        self.snapshot()
        flags.unlink()
        self.assertEqual(self.finish(), 0)
        final = self.read()
        self.assertEqual(final["initial_profile"]["files"]["Config/feature_flags.asm"]["status"], "unavailable")
        self.assertEqual(final["snapshots"]["pre_assembly"]["profile"]["effective_flags"]["ENABLE_TEST"], 1)

    def test_removing_an_originally_present_flags_file_is_not_restoration(self):
        self.initialize()
        self.snapshot()
        (self.root / "Config/feature_flags.asm").unlink()
        self.assertEqual(self.finish(), 1)
        self.assertIn("source_snapshot_identity", self.read()["finish"]["required_gaps"])

    def test_snapshot_cannot_be_overwritten_after_restore(self):
        self.initialize()
        self.command("snapshot", "--phase", "pre_assembly")
        original = self.output.read_bytes()
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = 1\n")
        self.assertEqual(self.command("snapshot", "--phase", "pre_assembly"), 1)
        self.assertEqual(self.output.read_bytes(), original)

    def test_base_mutation_before_snapshot_is_rejected(self):
        self.initialize()
        self.base.write_bytes(b"edited base")
        self.assertEqual(self.command("snapshot", "--phase", "pre_assembly"), 1)
        self.assertEqual(self.finish(), 1)
        self.assertIn("base_rom_snapshot_identity", self.read()["finish"]["required_gaps"])

    def test_source_mutation_after_snapshot_blocks_success(self):
        for relative in ("Core/main.asm", "Core/gfx/boat.bin", "Data/new.json",
                         "Config/feature_flags.asm"):
            with self.subTest(relative=relative):
                existing = (self.root / relative).read_bytes() if (self.root / relative).exists() else None
                self.initialize()
                self.command("snapshot", "--phase", "pre_assembly")
                self.put(relative, (existing or b"") + b"\n")
                self.assertEqual(self.finish(), 1)
                self.assertIn("source_snapshot_identity", self.read()["finish"]["required_gaps"])
                if existing is None:
                    (self.root / relative).unlink()
                else:
                    self.put(relative, existing)

    def test_artifact_and_tool_identity_are_rechecked_at_finish(self):
        for kind in ("artifact", "tool"):
            with self.subTest(kind=kind):
                self.initialize()
                self.snapshot()
                path = self.put("Roms/output.bin", b"first")
                self.assertEqual(self.command(kind, "--name", "produced", "--path", path), 0)
                path.write_bytes(b"other")  # same size, different digest
                self.assertEqual(self.finish(), 1)
                self.assertEqual(self.read()["state"], "failed")

    def test_missing_artifact_is_recorded_and_rejected(self):
        self.initialize()
        self.snapshot()
        self.assertEqual(self.command("artifact", "--name", "symbols", "--path",
                                      self.root / "absent.sym"), 1)
        self.assertEqual(self.read()["artifacts"]["symbols"]["status"], "unavailable")
        self.assertEqual(self.finish(), 1)

    def test_source_digest_tracks_code_assets_and_profile_but_not_outputs(self):
        original = receipt.source_snapshot(self.root, self.output)
        self.assertIn("Core/gfx/boat.bin", original["files"])
        self.assertIn("Scripts/Generate/generate.py", original["files"])
        self.assertIn("Tests/smoke/current_state.json", original["files"])
        for relative in ("Roms/output.sfc", ".context/notes.md", "Core/__pycache__/x.pyc"):
            self.put(relative, b"unrelated output")
        self.assertEqual(original["aggregate_sha256"],
                         receipt.source_snapshot(self.root, self.output)["aggregate_sha256"])
        for relative in ("Core/main.asm", "Core/gfx/boat.bin", "Config/feature_flags.asm",
                         "Scripts/Generate/generate.py", "Tests/smoke/current_state.json"):
            with self.subTest(relative=relative):
                before = (self.root / relative).read_bytes()
                self.put(relative, before + b"\n")
                self.assertNotEqual(original["aggregate_sha256"],
                                    receipt.source_snapshot(self.root, self.output)["aggregate_sha256"])
                self.put(relative, before)

    def test_source_digest_is_independent_of_root_and_creation_order(self):
        first = receipt.source_snapshot(self.root, self.output)
        other = Path(self.temporary.name) / "other"
        for relative in reversed(list(first["files"])):
            destination = other / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes((self.root / relative).read_bytes())
        second = receipt.source_snapshot(other, other / "Roms/receipt.json")
        self.assertEqual(first["aggregate_sha256"], second["aggregate_sha256"])

    def test_generated_screenshots_do_not_invalidate_but_png_fixtures_do(self):
        self.put("Tests/fixtures/expected.png", b"fixture pixels")
        self.initialize()
        self.snapshot()
        before = self.read()["snapshots"]["pre_assembly"]
        for relative in ("Tests/screenshots/run.png", "Tests/ScreenShots/nested/run.png",
                         "tests/screenshots/lowercase.png"):
            self.put(relative, b"captured screenshot")
        after = receipt.source_snapshot(self.root, self.output)
        self.assertEqual(before["aggregate_sha256"], after["aggregate_sha256"])
        self.assertEqual(self.finish(), 0)
        self.assertIn("Tests/fixtures/expected.png", after["files"])
        self.put("Tests/fixtures/expected.png", b"changed fixture")
        self.assertEqual(self.finish(), 1)
        self.assertIn("source_snapshot_identity", self.read()["finish"]["required_gaps"])

    def test_unresolved_profile_values_are_not_guessed(self):
        self.put("Config/feature_flags.asm", "!ENABLE_TEST = !OTHER + 1\n")
        parsed = receipt.profile(self.root)
        self.assertIsNone(parsed["effective_flags"]["ENABLE_TEST"])
        self.assertEqual(len(parsed["unresolved_assignments"]), 1)

    def test_atomic_replace_failure_preserves_previous_receipt(self):
        self.initialize()
        before = self.output.read_bytes()
        with mock.patch.object(receipt.os, "replace", side_effect=OSError("fixture failure")):
            self.assertEqual(self.check("passed", True), 1)
        self.assertEqual(self.output.read_bytes(), before)
        self.assertEqual(list(self.output.parent.glob(f".{self.output.name}.*")), [])

    def test_receipt_cannot_overwrite_or_alias_base_rom(self):
        original = self.base.read_bytes()
        aliases = [self.base, self.root / "Roms/alias.json"]
        aliases[1].hardlink_to(self.base)
        for path in aliases:
            with self.subTest(path=path):
                self.output = path
                self.assertEqual(self.initialize(), 1)
                self.assertEqual(self.base.read_bytes(), original)

    def test_receipt_refuses_source_and_managed_artifact_destinations(self):
        names = ("Oracle_main.asm", "Config/feature_flags.asm", "Tests/manifest.json",
                 ".github/workflows/build.yml", "z3dk.toml", "Oracle-of-Secrets.yaze",
                 "Roms/oos168x.sfc", "Roms/oos168x.sym", "Roms/oos168x.mlb",
                 "Roms/hooks.json", "Roms/hack_manifest.json", "Roms/sourcemap.json",
                 "Roms/oos168x.smoke.json", "Roms/oos168x.reload-identity.json")
        for relative in names:
            with self.subTest(relative=relative):
                path = self.root / relative
                if not path.exists():
                    self.put(relative, b"preserved input or output")
                before = path.read_bytes()
                self.output = path
                self.assertEqual(self.initialize(), 1)
                self.assertEqual(path.read_bytes(), before)

    def test_receipt_refuses_new_source_paths_and_managed_artifacts(self):
        for relative in ("Config/new.json", "Tests/new.json", ".github/new.yml",
                         "new.asm", "new.toml", "Roms/oos168x.smoke.json"):
            with self.subTest(relative=relative):
                self.output = self.root / relative
                self.assertEqual(self.initialize(), 1)
                self.assertFalse(self.output.exists())

    def test_receipt_refuses_source_and_artifact_aliases_outside_root(self):
        for relative in ("Oracle_main.asm", "Config/feature_flags.asm", "Roms/hooks.json"):
            protected = self.root / relative
            if not protected.exists():
                self.put(relative, b"preserved")
            before = protected.read_bytes()
            for alias_kind in ("symlink", "hardlink"):
                with self.subTest(relative=relative, alias_kind=alias_kind):
                    alias = Path(self.temporary.name) / "alias.json"
                    alias.unlink(missing_ok=True)
                    if alias_kind == "symlink":
                        alias.symlink_to(protected)
                    else:
                        alias.hardlink_to(protected)
                    self.output = alias
                    self.assertEqual(self.initialize(), 1)
                    self.assertEqual(protected.read_bytes(), before)
                    self.assertEqual(alias.read_bytes(), before)

    def test_receipt_accepts_build_json_and_external_afs_paths(self):
        for path in (self.root / "Roms/oos168x.build.json",
                     Path(self.temporary.name) / "afs/receipts/build.json"):
            with self.subTest(path=path):
                self.output = path
                self.assertEqual(self.initialize(), 0)
                self.assertEqual(self.read()["state"], "in_progress")


if __name__ == "__main__":
    unittest.main()
