"""Canonical graphics edits: exact identities, native policy and safe publication."""
from pathlib import Path
import contextlib
import copy
import fcntl
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

GRAPHICS = Path(__file__).resolve().parents[2] / "Graphics"
sys.path.insert(0, str(GRAPHICS))
import compile_graphics_pack as pack
import compile_runtime_graphics as runtime
import edit_graphics_source as edit


class EditGraphicsSourceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="graphics-edit-test-")
        self.addCleanup(self.temporary.cleanup)
        self.work = Path(self.temporary.name).resolve()
        self.source = self.work / "source"
        self.overworld = self.source / "Overworld"
        self.overworld.mkdir(parents=True)
        self.original_root = GRAPHICS.parents[1]
        canonical = pack.read_json(self.original_root / edit.SOURCE_CATALOG)
        files = {edit.SOURCE_CATALOG, edit.SOURCE_POLICY, edit.SOURCE_TABLES}
        files.update("Overworld/" + value["path"] for value in canonical["resources"].values())
        files.update("Overworld/" + name for name in runtime.LEGACY_ALIASES)
        for name in files:
            target = self.source / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(self.original_root / name, target)
        self.portable = self.work / "portable"
        pack.compile_pack(self.source / edit.SOURCE_CATALOG, self.portable,
                          runtime_policy=self.source / edit.SOURCE_POLICY)
        self.catalog = canonical
        self.resource_id = next(key for key, value in canonical["resources"].items()
                                if value["path"].endswith("lyra_stepped_fort_83.bin"))
        self.resource_path = self.overworld / canonical["resources"][self.resource_id]["path"]
        self.replacement = self.work / "replacement.bin"
        pixels = bytearray(self.resource_path.read_bytes())
        # First pixel is index1. Change it to3, retaining the reviewed
        # transparent0 / forbidden8 fort authoring contract.
        self.assertEqual(sum(((pixels[(p // 2) * 16 + p % 2] >> 7) & 1) << p
                             for p in range(4)), 1)
        pixels[1] ^= 0x80
        self.replacement.write_bytes(pixels)
        self.before = self.protected_bytes()

    def protected_bytes(self):
        return {str(path): path.read_bytes() for root in (self.source, self.portable)
                for path in root.rglob("*") if path.is_file() and path.name != edit.LOCK_NAME}

    def plan(self):
        return edit.make_plan(self.source, self.portable / "catalog.json",
                              self.resource_id, self.replacement)

    def apply(self, plan):
        return edit.apply_plan(plan, self.source, self.portable / "catalog.json")

    def test_inspect_maps_exact_fort_slices_without_writing(self):
        info, _, _ = edit.collect(self.source, self.portable / "catalog.json", self.resource_id)
        self.assertEqual(info["resource_byte_count"], 3072)
        self.assertEqual(info["affected_profiles"], ["stepped-waterfront-fort"])
        self.assertEqual(info["affected_parent_maps"], [0x83])
        self.assertEqual(len(info["transfers"]), 96)
        self.assertEqual([t["source_offset"] for t in info["transfers"]], list(range(0, 3072, 32)))
        self.assertEqual(self.protected_bytes(), self.before)
        self.assertFalse(list(self.work.rglob(edit.LOCK_NAME)))

    def test_publish_fort_rekeys_catalog_and_preserves_sparse_layout_and_old_art(self):
        plan = self.plan()
        self.assertEqual(self.protected_bytes(), self.before)
        after_id = "snes4bpp:" + pack.sha256(self.replacement.read_bytes())
        self.assertEqual(plan["after_resource_id"], after_id)
        result = self.apply(plan)
        self.assertEqual(result["result"], "published")
        canonical, assets = pack.load(self.source / edit.SOURCE_CATALOG)
        portable, exported = pack.load(self.portable / "catalog.json")
        self.assertEqual(edit.semantic(canonical), edit.semantic(portable))
        self.assertEqual(assets, exported)
        self.assertNotIn(self.resource_id, canonical["resources"])
        self.assertEqual(assets[after_id], self.replacement.read_bytes())
        self.assertEqual(self.resource_path.read_bytes(), self.before[str(self.resource_path)])
        old_transfers = self.catalog["profiles"]["stepped-waterfront-fort"]["transfers"]
        self.assertEqual(canonical["profiles"]["stepped-waterfront-fort"]["transfers"],
                         [dict(t, resource_id=after_id) for t in old_transfers])
        text, report = self.compile_current()
        self.assertEqual((self.source / edit.SOURCE_TABLES).read_text(), text)
        self.assertEqual(report["staging_counts"]["stepped-waterfront-fort"], 96)
        self.assertEqual(report["new_payload_bytes"], 5120)
        edit.collect(self.source, self.portable / "catalog.json", after_id)

    def compile_current(self):
        return runtime.compile_tables(self.source / edit.SOURCE_CATALOG,
                                      self.source / edit.SOURCE_POLICY,
                                      self.source / edit.SOURCE_TABLES, legacy_root=self.source)

    def test_legacy_resource_edit_uses_new_payload_and_updates_phase_references(self):
        self.resource_id = next(key for key, value in self.catalog["resources"].items()
                                if value["path"] == "gfx/boat.bin")
        legacy = self.overworld / "gfx/boat.bin"
        replacement = bytearray(legacy.read_bytes())
        replacement[0] ^= 1
        self.replacement.write_bytes(replacement)
        plan = self.plan()
        self.apply(plan)
        self.assertEqual(legacy.read_bytes(), self.before[str(legacy)])
        policy = pack.read_json(self.source / edit.SOURCE_POLICY)
        transfer = policy["profiles"]["dragon-ship"]["transition"]["transfer"]
        self.assertEqual(transfer["resource_id"], plan["after_resource_id"])
        _, report = self.compile_current()
        self.assertNotIn(plan["after_resource_id"], report["aliases"])
        self.assertEqual(report["new_payload_bytes"], 5120 + 8192)

    def test_stale_source_binary_refuses_before_any_publication(self):
        plan = self.plan()
        self.resource_path.write_bytes(bytes(3072))
        changed = self.protected_bytes()
        with self.assertRaises((edit.EditError, pack.PackError)):
            self.apply(plan)
        self.assertEqual(self.protected_bytes(), changed)

    def test_stale_portable_receipt_file_refuses_before_publication(self):
        plan = self.plan()
        (self.portable / "preview-v1.json").write_text("{}")
        changed = self.protected_bytes()
        with self.assertRaises(edit.EditError):
            self.apply(plan)
        self.assertEqual(self.protected_bytes(), changed)

    def test_stale_replacement_and_replaced_same_bytes_input_refuse(self):
        plan = self.plan()
        self.replacement.write_bytes(self.replacement.read_bytes())
        with self.assertRaises(edit.EditError):
            self.apply(plan)
        self.assertEqual(self.protected_bytes(), self.before)

    def test_forbidden_opaque8_and_size_change_refuse_before_writes(self):
        data = bytearray(self.replacement.read_bytes())
        for plane in range(4):
            at = (plane // 2) * 16 + plane % 2
            data[at] = (data[at] & 0x7F) | (0x80 if plane == 3 else 0)
        self.replacement.write_bytes(data)
        with self.assertRaisesRegex(pack.PackError, "forbidden opaque index 8"):
            self.plan()
        self.replacement.write_bytes(bytes(32))
        with self.assertRaisesRegex(edit.EditError, "preserve the resource byte count"):
            self.plan()
        self.assertEqual(self.protected_bytes(), self.before)

    def test_write_failure_rolls_back_every_published_target(self):
        plan = self.plan()
        original = edit.replace_file
        writes = 0

        def fail_second(target, data):
            nonlocal writes
            writes += 1
            if writes == 2:
                raise OSError("fixture publication failure")
            original(target, data)

        with mock.patch.object(edit, "replace_file", side_effect=fail_second):
            with self.assertRaisesRegex(OSError, "fixture publication failure"):
                self.apply(plan)
        self.assertEqual(self.protected_bytes(), self.before)
        # A fresh review remains usable after the rollback.
        self.apply(self.plan())

    def test_final_compiler_failure_rolls_back_source_and_pack(self):
        plan = self.plan()
        original = runtime.compile_tables
        def fail_readback(*args, **kwargs):
            if (args[0] == self.source / edit.SOURCE_CATALOG and
                    (self.source / edit.SOURCE_TABLES).read_bytes() !=
                    self.before[str(self.source / edit.SOURCE_TABLES)]):
                raise pack.PackError("fixture final compiler failure")
            return original(*args, **kwargs)

        with mock.patch.object(runtime, "compile_tables", side_effect=fail_readback):
            with self.assertRaisesRegex(pack.PackError, "fixture final compiler failure"):
                self.apply(plan)
        self.assertEqual(self.protected_bytes(), self.before)

    def test_forged_targets_refuse_before_creating_foreign_locks(self):
        plan = self.plan()
        foreign = self.work / "foreign"
        foreign.mkdir()
        plan["publication_targets"].append(dict(path=str(foreign / "fake.bin"), before_sha256=None))
        with self.assertRaisesRegex(edit.EditError, "differs from the reviewed plan"):
            self.apply(plan)
        self.assertFalse((foreign / edit.LOCK_NAME).exists())
        self.assertEqual(self.protected_bytes(), self.before)

    def test_new_source_path_created_after_plan_refuses(self):
        plan = self.plan()
        target = Path(plan["after_source_resource_path"])
        target.write_bytes(b"foreign")
        changed = self.protected_bytes()
        with self.assertRaises(edit.EditError):
            self.apply(plan)
        self.assertEqual(self.protected_bytes(), changed)

    def test_symlink_and_hardlink_inputs_refuse(self):
        data = self.resource_path.read_bytes()
        original = self.work / "original.bin"
        self.resource_path.rename(original)
        self.resource_path.symlink_to(original)
        with self.assertRaisesRegex(edit.EditError, "Symbolic links"):
            self.plan()
        self.resource_path.unlink()
        os.link(original, self.resource_path)
        with self.assertRaisesRegex(edit.EditError, "one hard link"):
            self.plan()
        self.assertEqual(original.read_bytes(), data)

    def test_catalog_path_escape_and_mismatched_pack_refuse(self):
        catalog = copy.deepcopy(self.catalog)
        catalog["resources"][self.resource_id]["path"] = "../outside.bin"
        (self.source / edit.SOURCE_CATALOG).write_bytes(pack.json_bytes(catalog))
        with self.assertRaisesRegex(edit.EditError, "escapes its catalog"):
            self.plan()
        (self.source / edit.SOURCE_CATALOG).write_bytes(self.before[str(self.source / edit.SOURCE_CATALOG)])
        portable = pack.read_json(self.portable / "catalog.json")
        portable["bindings"][0]["parent_maps"] = [0x31]
        (self.portable / "catalog.json").write_bytes(pack.json_bytes(portable))
        with self.assertRaisesRegex(edit.EditError, "differs from canonical"):
            self.plan()

    def test_stale_generated_source_refuses_without_repairing_unrelated_changes(self):
        tables = self.source / edit.SOURCE_TABLES
        tables.write_bytes(tables.read_bytes() + b"; foreign edit\n")
        changed = self.protected_bytes()
        with self.assertRaisesRegex(edit.EditError, "runtime tables are stale"):
            self.plan()
        self.assertEqual(self.protected_bytes(), changed)

    def test_overlapping_source_and_pack_folders_refuse(self):
        alias = self.overworld / "catalog.json"
        alias.write_bytes((self.source / edit.SOURCE_CATALOG).read_bytes())
        with self.assertRaisesRegex(edit.EditError, "must not overlap"):
            edit.collect(self.source, alias, self.resource_id)

    def test_same_lock_namespace_refuses_busy_writer(self):
        plan = self.plan()
        lock = self.portable / edit.LOCK_NAME
        with lock.open("wb") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX | fcntl.LOCK_NB)
            with self.assertRaisesRegex(edit.EditError, "publication is busy"):
                self.apply(plan)
        self.assertEqual(self.protected_bytes(), self.before)

    def test_compiler_alias_verification_uses_explicit_selected_source_root(self):
        legacy_id = next(key for key, value in self.catalog["resources"].items()
                         if value["path"] == "gfx/boat.bin")
        legacy = self.overworld / "gfx/boat.bin"
        data = bytearray(legacy.read_bytes())
        data[0] ^= 1
        legacy.write_bytes(data)
        self.catalog["resources"][legacy_id]["sha256"] = pack.sha256(data)
        (self.source / edit.SOURCE_CATALOG).write_bytes(pack.json_bytes(self.catalog))
        # The script checkout's unchanged boat bytes differ from this fixture.
        # Only an explicitly passed root can verify the selected legacy label.
        _, report = self.compile_current()
        self.assertEqual(report["aliases"][legacy_id], "ShipBackgroundGraphics")

    def test_command_line_json_plan_and_apply_in_separate_processes(self):
        receipt = self.work / "plan.json"
        command = [sys.executable, str(GRAPHICS / "edit_graphics_source.py")]
        selection = ["--source-root", str(self.source), "--portable-catalog", str(self.portable / "catalog.json")]
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")

        def run(arguments):
            process = subprocess.run(command + arguments + selection, env=env,
                                     capture_output=True, text=True, check=False)
            self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
            return json.loads(process.stdout)

        inspected = run(["inspect", "--resource-id", self.resource_id])
        self.assertEqual(inspected["operation"], "inspect")
        planned = run(["plan", "--resource-id", self.resource_id,
                       "--replacement", str(self.replacement), "--plan", str(receipt)])
        self.assertEqual(planned, json.loads(receipt.read_text()))
        applied = run(["apply", "--plan", str(receipt), "--expected-plan-sha256",
                       pack.sha256(receipt.read_bytes())])
        self.assertEqual(applied["after_resource_id"], planned["after_resource_id"])
        self.assertEqual(applied["result"], "published")

    def test_held_plan_hash_and_mid_publication_change_refuse_with_rollback(self):
        plan = self.plan()
        path = self.work / "review-plan.json"
        path.write_bytes(pack.json_bytes(plan))
        plan_guard, _ = edit.snapshot(path)
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = edit.main(["apply", "--source-root", str(self.source), "--portable-catalog",
                              str(self.portable / "catalog.json"), "--plan", str(path),
                              "--expected-plan-sha256", "0" * 64])
        self.assertEqual(code, 1)
        self.assertIn("held review", json.loads(output.getvalue())["error"])
        self.assertEqual(self.protected_bytes(), self.before)

        original = edit.replace_file
        changed = False

        def change_plan_after_first_write(target, data):
            nonlocal changed
            original(target, data)
            if not changed:
                changed = True
                path.write_bytes(path.read_bytes() + b"\n")

        with mock.patch.object(edit, "replace_file", side_effect=change_plan_after_first_write):
            with self.assertRaisesRegex(edit.EditError, "Source changed since plan"):
                edit.apply_plan(plan, self.source, self.portable / "catalog.json", plan_guard=plan_guard)
        self.assertEqual(self.protected_bytes(), self.before)

    def test_cli_error_is_json_and_preserves_inputs(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            code = edit.main(["plan", "--source-root", str(self.source), "--portable-catalog",
                              str(self.portable / "catalog.json"), "--resource-id", self.resource_id])
        self.assertEqual(code, 1)
        self.assertEqual(json.loads(output.getvalue())["result"], "error")
        self.assertEqual(self.protected_bytes(), self.before)


if __name__ == "__main__":
    unittest.main()
