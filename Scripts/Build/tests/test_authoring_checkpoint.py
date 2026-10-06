"""Saved author edits must never discard newer RC repairs or mutate the inputs."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "prepare_authoring_checkpoint.py"
spec = importlib.util.spec_from_file_location("authoring_checkpoint", SCRIPT)
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


class AuthoringCheckpointTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.base = self.root / "baseline"
        self.author = self.root / "author"
        self.rc = self.root / "rc"
        self.output = self.root / "packet"
        self.manifest = self.root / "baseline.json"
        self.receipt = self.root / "receipt.json"
        self.project = b"[files]\nrom_filename=Roms/oos168.sfc\ncustom_collision_json=Data/collision.json\n"
        self.common = {"Roms/oos168.sfc": bytes(range(32)),
                       "Dungeons/walls.asm": b"top\na\nb\nc\nd\ne\nf\nbottom\n",
                       "Data/collision.json": b'{"room": 137}\n'}
        for root in (self.base, self.author, self.rc):
            for name, data in self.common.items():
                self.write(root, name, data)
            self.write(root, "Weekend.yaze", self.project)
        rom = bytearray(self.common["Roms/oos168.sfc"])
        rom[2] = 128  # A newer RC fix absent from the original editing copy.
        self.write(self.rc, "Roms/oos168.sfc", bytes(rom))
        self.write(self.rc, "Masks/fix.asm", b"; newer RC fix\n")
        self.write(self.rc, "Roms/oos168x.sfc", b"stale build must not be copied")
        self.manifest.write_text(json.dumps({
            "checkpoint": str(self.base), "project": str(self.author / "Weekend.yaze"),
            "project_sha256": checkpoint.sha(self.project),
            "copied_files": {n: checkpoint.sha(d) for n, d in self.common.items()}}))
        self.seal_rc()

    def write(self, root, name, data):
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def seal_rc(self):
        files = checkpoint.inventory(self.rc)
        self.receipt.write_text(json.dumps({
            "state": "completed_with_gaps",
            "base_rom": {"sha256": checkpoint.sha((self.rc / "Roms/oos168.sfc").read_bytes())},
            "snapshots": {"pre_assembly": {"files": checkpoint.fingerprints(files)}}}))

    def prepare(self):
        return checkpoint.prepare(self.author / "Weekend.yaze", self.manifest,
                                  self.rc, self.receipt, self.output)

    def test_unchanged_author_preserves_new_rc_and_omits_stale_build(self):
        report = self.prepare()
        self.assertEqual(report["changes"], [])
        self.assertEqual((self.output / "src/Roms/oos168.sfc").read_bytes()[2], 128)
        self.assertTrue((self.output / "src/Masks/fix.asm").exists())
        self.assertFalse((self.output / "src/Roms/oos168x.sfc").exists())
        self.assertEqual((self.author / "Roms/oos168.sfc").read_bytes(), bytes(range(32)))

    def test_disjoint_rom_and_sidecar_edits_preserve_rc_fix(self):
        rom = bytearray(self.common["Roms/oos168.sfc"])
        rom[20] = 200
        self.write(self.author, "Roms/oos168.sfc", bytes(rom))
        self.write(self.author, "Data/collision.json", b'{"room": 152}\n')
        report = self.prepare()
        merged = (self.output / "src/Roms/oos168.sfc").read_bytes()
        self.assertEqual((merged[2], merged[20]), (128, 200))
        self.assertEqual(len(report["changes"]), 2)
        self.assertEqual((self.output / "src/Data/collision.json").read_bytes(), b'{"room": 152}\n')
        self.assertEqual((self.rc / "Roms/oos168.sfc").read_bytes()[20], 20)

    def test_rom_conflict_publishes_nothing(self):
        rom = bytearray(self.common["Roms/oos168.sfc"])
        rom[2] = 77
        self.write(self.author, "Roms/oos168.sfc", bytes(rom))
        with self.assertRaisesRegex(ValueError, "ROM byte conflicts at 0x000002"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_identical_overlap_is_allowed(self):
        self.write(self.author, "Roms/oos168.sfc", (self.rc / "Roms/oos168.sfc").read_bytes())
        self.prepare()
        self.assertEqual((self.output / "src/Roms/oos168.sfc").read_bytes()[2], 128)

    def test_nonoverlapping_text_changes_merge(self):
        original = self.common["Dungeons/walls.asm"]
        self.write(self.rc, "Dungeons/walls.asm", original.replace(b"top", b"RC top"))
        self.write(self.author, "Dungeons/walls.asm", original.replace(b"bottom", b"author bottom"))
        self.seal_rc()
        self.prepare()
        merged = (self.output / "src/Dungeons/walls.asm").read_bytes()
        self.assertIn(b"RC top", merged)
        self.assertIn(b"author bottom", merged)

    def test_overlapping_text_changes_refuse(self):
        original = self.common["Dungeons/walls.asm"]
        self.write(self.rc, "Dungeons/walls.asm", original.replace(b"top", b"RC top"))
        self.write(self.author, "Dungeons/walls.asm", original.replace(b"top", b"author top"))
        self.seal_rc()
        with self.assertRaisesRegex(ValueError, "Overlapping source edits"):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_conflicting_binary_growth_refuses(self):
        self.write(self.author, "Roms/oos168.sfc", bytes(range(33)))
        with self.assertRaisesRegex(ValueError, "binary data or ROM size"):
            self.prepare()

    def test_source_addition_and_unmodified_source_deletion(self):
        self.write(self.author, "Dungeons/new.asm", b"new object\n")
        (self.author / "Data/collision.json").unlink()
        self.prepare()
        self.assertTrue((self.output / "src/Dungeons/new.asm").exists())
        self.assertFalse((self.output / "src/Data/collision.json").exists())

    def test_delete_changed_rc_source_refuses(self):
        (self.author / "Data/collision.json").unlink()
        self.write(self.rc, "Data/collision.json", b'{"room": 88}\n')
        self.seal_rc()
        with self.assertRaisesRegex(ValueError, "Conflicting addition/deletion"):
            self.prepare()

    def test_save_as_rom_name_resolves_from_selected_project(self):
        self.write(self.author, "Weekend.yaze", self.project.replace(b"oos168.sfc", b"edited.sfc"))
        self.write(self.author, "Roms/edited.sfc", self.common["Roms/oos168.sfc"])
        self.prepare()
        self.assertTrue((self.output / "authoring/Roms/edited.sfc").exists())
        self.assertTrue((self.output / "src/Roms/oos168.sfc").exists())

    def test_baseline_tampering_refuses(self):
        self.write(self.base, "Data/collision.json", b"changed")
        with self.assertRaisesRegex(ValueError, "Original checkpoint hash changed"):
            self.prepare()

    def test_rc_base_and_source_tampering_refuse(self):
        for name in ("Masks/fix.asm", "Roms/oos168.sfc"):
            with self.subTest(name=name):
                path = self.rc / name
                original = path.read_bytes()
                path.write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "RC (source|base ROM) no longer matches"):
                    self.prepare()
                path.write_bytes(original)

    def test_source_rebinding_refuses_instead_of_ignoring_it(self):
        self.write(self.author, "Weekend.yaze", self.project.replace(b"Data/collision.json", b"Data/other.json"))
        with self.assertRaisesRegex(ValueError, "Changed project source binding"):
            self.prepare()

    def test_symlink_and_path_escape_refuse(self):
        (self.author / "Dungeons/escape.asm").symlink_to(self.rc / "Masks/fix.asm")
        with self.assertRaisesRegex(ValueError, "Symlinks"):
            self.prepare()
        (self.author / "Dungeons/escape.asm").unlink()
        with self.assertRaises(ValueError):
            checkpoint.read_local(self.author, "../rc/Masks/fix.asm")

    def test_existing_output_and_output_inside_author_refuse(self):
        self.output.mkdir()
        (self.output / "canary").write_text("keep")
        with self.assertRaisesRegex(ValueError, "already exists"):
            self.prepare()
        self.assertEqual((self.output / "canary").read_text(), "keep")
        self.output = self.author / "oops"
        with self.assertRaisesRegex(ValueError, "separate"):
            self.prepare()

    def test_concurrent_author_save_refuses_partial_checkpoint(self):
        real_inventory = checkpoint.inventory
        reads = 0

        def changing_inventory(root, authoring_only=False):
            nonlocal reads
            result = real_inventory(root, authoring_only)
            if root == self.author:
                reads += 1
                if reads == 2:
                    result["Dungeons/walls.asm"] = b"changed during snapshot"
            return result

        with mock.patch.object(checkpoint, "inventory", side_effect=changing_inventory):
            with self.assertRaisesRegex(ValueError, "Editing files changed during capture"):
                self.prepare()
        self.assertFalse(self.output.exists())


if __name__ == "__main__":
    unittest.main()
