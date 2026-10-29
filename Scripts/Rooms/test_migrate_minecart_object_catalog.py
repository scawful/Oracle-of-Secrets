"""Synthetic-only checks for the guarded object catalog migration."""
import contextlib
import io
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import migrate_minecart_object_catalog as migration


def pc_to_snes(pc):
    return ((pc & 0x3F8000) << 1) | (pc & 0x7FFF) | 0x8000


def fixture():
    data = bytearray(0x200000)
    table = 0xF8000
    data[0x874C:0x874F] = pc_to_snes(table).to_bytes(3, "little")
    for room in range(296):
        start = 0x50000 + room * 0x100
        data[table + room * 3:table + room * 3 + 3] = pc_to_snes(start).to_bytes(3, "little")
        objects = []
        for index in range(37 if room == 0 else 1):
            subtype = 12 + index % 4
            objects.append(bytes((((index % 20) << 2) | (subtype >> 2),
                                  (8 << 2) | (subtype & 3), 0x31 if room == 0 else 0x05)))
        stream = b"\x01\x0C" + b"".join(objects) + b"\xFF\xFF\xFF\xFF\xF0\xFF\x81\x00\xFF\xFF"
        data[start:start + len(stream)] = stream
    data[0x100000:0x100008] = b"KEEPDATA"
    return bytes(data)


class MigrationTest(unittest.TestCase):
    def setUp(self):
        self.data = fixture()
        self.sha = migration.digest(self.data)

    def plan(self, data=None):
        data = self.data if data is None else data
        return migration.plan_migration(data, migration.digest(data))

    def test_exact_37_records_111_bytes_and_full_room_structure(self):
        candidate, report = self.plan()
        self.assertEqual(report["record_count"], 37)
        self.assertEqual(report["changed_bytes"], 111)
        self.assertEqual(report["rooms_parsed"], 296)
        self.assertFalse(report["editor_ready"])
        self.assertFalse(report["runtime_ready"])
        self.assertEqual(report["state"], "intermediate-old-runtime")
        self.assertEqual(candidate[0x100000:0x100008], b"KEEPDATA")
        self.assertEqual(candidate[migration.MARKER_PC:migration.MARKER_PC + 8], bytes(8))
        for record in report["records"]:
            self.assertEqual(record["new_subtype"], record["old_subtype"] - 7)
            self.assertEqual(bytes.fromhex(record["old"])[0] >> 2, record["x"])
            self.assertEqual(bytes.fromhex(record["new"])[0] >> 2, record["x"])
            self.assertEqual(bytes.fromhex(record["old"])[1] >> 2, record["y"])
            self.assertEqual(bytes.fromhex(record["new"])[1] >> 2, record["y"])

    def test_wrong_hash_refuses(self):
        with self.assertRaisesRegex(migration.PlanError, "SHA-256 differs"):
            migration.plan_migration(self.data, "0" * 64)

    def test_malformed_expected_hash_refuses(self):
        with self.assertRaisesRegex(migration.PlanError, "64 hexadecimal"):
            migration.plan_migration(self.data, "not-a-hash")

    def test_new_marker_refuses_before_migration(self):
        data = bytearray(self.data)
        data[migration.MARKER_PC:migration.MARKER_PC + 8] = b"MCR2\x10\x0D\x02\x00"
        with self.assertRaisesRegex(migration.PlanError, "already present"):
            self.plan(bytes(data))

    def test_already_migrated_records_refuse_without_marker(self):
        candidate, _ = self.plan()
        with self.assertRaisesRegex(migration.PlanError, "Already migrated or ambiguous"):
            self.plan(candidate)

    def test_reserved_or_mixed_object32_catalog_refuses(self):
        data = bytearray(self.data)
        data[0x50102:0x50105] = bytes((0, 3, 0x32))
        with self.assertRaisesRegex(migration.PlanError, "ambiguous"):
            self.plan(bytes(data))

    def test_changed_record_count_refuses(self):
        data = bytearray(self.data)
        data[0x50004] = 0x05
        with self.assertRaisesRegex(migration.PlanError, "found 36"):
            self.plan(bytes(data))

    def test_aliased_target_room_refuses(self):
        data = bytearray(self.data)
        data[0xF8003:0xF8006] = data[0xF8000:0xF8003]
        with self.assertRaisesRegex(migration.PlanError, "aliased room consumers"):
            self.plan(bytes(data))

    def test_overlapping_stream_pointer_refuses(self):
        data = bytearray(self.data)
        data[0xF8003:0xF8006] = pc_to_snes(0x50003).to_bytes(3, "little")
        with self.assertRaises(migration.PlanError):
            self.plan(bytes(data))

    def test_unterminated_unrelated_room_refuses(self):
        data = bytearray(self.data)
        data[0x58000:0x58100] = b"\x01" * 0x100
        with self.assertRaises(migration.PlanError):
            self.plan(bytes(data))

    def invoke(self, directory, *extra):
        source = directory / "source.sfc"
        if not source.exists():
            source.write_bytes(self.data)
        output = io.StringIO()
        error = io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            rc = migration.main(["--rom", str(source), "--expected-sha256", self.sha, *map(str, extra)],
                                protected_dirs=())
        self.assertEqual(source.read_bytes(), self.data)
        return rc, output.getvalue(), error.getvalue()

    def test_default_dry_run_writes_no_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            rc, output, _ = self.invoke(directory)
            self.assertEqual(rc, 0)
            self.assertEqual(json.loads(output)["mode"], "dry-run")
            self.assertEqual({p.name for p in directory.iterdir()}, {"source.sfc"})

    def test_exclusive_output_and_exact_receipt_readback(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target, receipt = directory / "candidate.sfc", directory / "receipt.json"
            rc, output, _ = self.invoke(directory, "--output", target, "--receipt", receipt)
            self.assertEqual(rc, 0)
            report = json.loads(output)
            self.assertEqual(json.loads(receipt.read_text()), report)
            self.assertEqual(migration.digest(target.read_bytes()), report["output_sha256"])

    def test_existing_target_is_never_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "existing.sfc"
            target.write_bytes(b"external sentinel")
            rc, _, _ = self.invoke(directory, "--output", target, "--receipt", directory / "receipt.json")
            self.assertEqual(rc, 1)
            self.assertEqual(target.read_bytes(), b"external sentinel")

    def test_dangling_symlink_is_never_replaced(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target = directory / "alias.sfc"
            target.symlink_to(directory / "absent")
            rc, _, _ = self.invoke(directory, "--output", target, "--receipt", directory / "receipt.json")
            self.assertEqual(rc, 1)
            self.assertTrue(target.is_symlink())

    def test_live_project_output_is_refused(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with self.assertRaisesRegex(migration.PlanError, "protected directory"):
                migration.check_new_target(directory / "new.sfc", "output", (directory,), ())

    def test_input_change_before_publish_refuses(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            with mock.patch.object(migration, "read_input", side_effect=[self.data, self.data + b"changed"]):
                rc, _, error = self.invoke(directory, "--output", directory / "new.sfc",
                                           "--receipt", directory / "receipt.json")
            self.assertEqual(rc, 1)
            self.assertIn("Input changed during planning", error)
            self.assertFalse((directory / "new.sfc").exists())

    def test_receipt_failure_retains_published_recovery_image(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            target, receipt = directory / "new.sfc", directory / "receipt.json"
            publish = migration.publish_exclusive

            def race(path, data, mode):
                if path == receipt.resolve():
                    receipt.write_bytes(b"external receipt")
                publish(path, data, mode)

            with mock.patch.object(migration, "publish_exclusive", side_effect=race):
                rc, _, error = self.invoke(directory, "--output", target, "--receipt", receipt)
            self.assertEqual(rc, 1)
            self.assertEqual(receipt.read_bytes(), b"external receipt")
            self.assertEqual(target.read_bytes(), self.plan()[0])
            self.assertTrue(json.loads(error)["output_exists"])

    def migrated_input(self):
        candidate, report = self.plan()
        report["mode"] = "published"
        return candidate, report

    def test_unmarked_base_requires_receipt(self):
        with self.assertRaisesRegex(migration.PlanError, "OOS_MINECART_MIGRATION_RECEIPT"):
            migration.verify_build_input(self.data)

    def test_marked_base_passes_without_receipt(self):
        candidate, _ = self.migrated_input()
        candidate = bytearray(candidate)
        candidate[migration.MARKER_PC:migration.MARKER_PC + 8] = migration.MCR2_MARKER
        report = migration.verify_build_input(bytes(candidate))
        self.assertEqual(report["catalog"], "MCR2")
        self.assertFalse(report["receipt_required"])

    def test_marked_base_with_wrong_counts_refuses(self):
        data = bytearray(self.data)
        data[migration.MARKER_PC:migration.MARKER_PC + 8] = b"MCR2\x10\x05\x02\x00"
        with self.assertRaisesRegex(migration.PlanError, "Unsupported MCR2"):
            migration.verify_build_input(bytes(data))

    def test_receipt_reconstructs_exact_original_and_records(self):
        candidate, receipt = self.migrated_input()
        report = migration.verify_build_input(candidate, receipt)
        self.assertEqual(report["catalog"], "migrated-for-MCR2")
        self.assertEqual(report["record_count"], 37)
        self.assertTrue(report["receipt_required"])

    def test_stale_receipt_output_hash_refuses(self):
        candidate, receipt = self.migrated_input()
        receipt["output_sha256"] = "0" * 64
        with self.assertRaisesRegex(migration.PlanError, "output SHA-256 differs"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_counters_cannot_replace_structural_proof(self):
        candidate, receipt = self.migrated_input()
        receipt["records"][0]["x"] += 1
        with self.assertRaisesRegex(migration.PlanError, "structural record proof"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_raw_cas_refuses_even_with_replaced_output_hash(self):
        candidate, receipt = self.migrated_input()
        candidate = bytearray(candidate)
        candidate[receipt["records"][0]["pc"]] ^= 4
        receipt["output_sha256"] = migration.digest(candidate)
        with self.assertRaisesRegex(migration.PlanError, "record CAS differs"):
            migration.verify_build_input(bytes(candidate), receipt)

    def test_receipt_partial_list_refuses(self):
        candidate, receipt = self.migrated_input()
        receipt["records"].pop()
        with self.assertRaisesRegex(migration.PlanError, "record list is incomplete"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_wrong_counter_refuses(self):
        candidate, receipt = self.migrated_input()
        receipt["changed_bytes"] = 110
        with self.assertRaisesRegex(migration.PlanError, "37 records / 111 bytes"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_unpublished_plan_refuses(self):
        candidate, receipt = self.plan()
        with self.assertRaisesRegex(migration.PlanError, "unpublished"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_duplicate_offsets_refuse(self):
        candidate, receipt = self.migrated_input()
        receipt["records"][1] = receipt["records"][0].copy()
        with self.assertRaisesRegex(migration.PlanError, "duplicate"):
            migration.verify_build_input(candidate, receipt)

    def test_receipt_invalid_original_hash_type_refuses(self):
        candidate, receipt = self.migrated_input()
        receipt["input_sha256"] = None
        with self.assertRaisesRegex(migration.PlanError, "original SHA-256 is invalid"):
            migration.verify_build_input(candidate, receipt)

    def test_verification_mode_cannot_publish_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            rc, _, error = self.invoke(directory, "--verify-build-input", "--output", directory / "out.sfc",
                                       "--receipt", directory / "out.json")
            self.assertEqual(rc, 1)
            self.assertIn("cannot publish", error)
            self.assertFalse((directory / "out.sfc").exists())


class ProjectAdmissionTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minecart-project-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.project_dir = self.root / "project"
        self.project_dir.mkdir()
        self.source = self.project_dir / "rom"
        self.project = self.project_dir / "project.yaze"
        self.migration_path = self.project_dir / "migration.json"
        self.initial, self.receipt = migration.plan_migration(fixture(), migration.digest(fixture()))
        self.receipt.update(mode="published", output=str(self.source), receipt=str(self.migration_path))
        self.source.write_bytes(self.initial)
        self.migration_path.write_text(json.dumps(self.receipt))
        self.project.write_text("[files]\nrom_filename=rom\nminecart_catalog_migration_receipt=migration.json\n"
                                "[dungeon_overlay]\nminecart_catalog_version=2\n")
        self.producer = self.root / "producer"
        self.producer.write_bytes(b"synthetic producer; not an executable")
        self.sidecar = self.project_dir / "collision.json"
        self.sidecar.write_text('{"synthetic":true}')
        self.save_path = Path(str(self.project) + ".native-save.json")
        control = self.root / "native-saves"
        control.mkdir()
        self.context_path = control / (migration.digest(str(self.source).encode()) + ".json")

    def verify(self, data=None, **extra):
        return migration.verify_build_input(self.source.read_bytes() if data is None else data,
                                           project=self.project, project_rom=self.source,
                                           native_receipt=self.save_path, native_context=self.context_path, **extra)

    def save_json(self, path, value):
        path.write_text(json.dumps(value))

    def native_save(self):
        data = bytearray(self.initial)
        record = self.receipt["records"][0]
        # A legitimate post-migration edit replaces the old floor-cross object
        # with a new 31:C junction. Initial migration CAS no longer qualifies it.
        data[record["pc"]:record["pc"] + 3] = bytes((3, 32, 0x31))
        self.source.write_bytes(data)
        bindings = {"rom": self.source, "project": self.project, "producer": self.producer,
                    "dependency.minecart_catalog_migration": self.migration_path,
                    "dependency.custom_collision_json": self.sidecar}
        artifacts = [{"role": role, "path": str(path), "sha256": migration.digest(path.read_bytes()),
                      "bytes": path.stat().st_size} for role, path in bindings.items()]
        self.save = {"kind": "yaze.native_save.v1", "generation": 7, "operation_id": "synthetic-save-7",
                     "operation": "save", "receipt_path": str(self.save_path), "bindings_complete": True,
                     "binding_errors": [], "artifacts": artifacts}
        self.context = {"kind": "yaze.native_save_context.v1", "editing_source_path": str(self.source),
                        "project_path": str(self.project), "rom_path": str(self.source), "state": "committed",
                        "producer": next(a for a in artifacts if a["role"] == "producer"),
                        "native_commit": {"receipt_path": str(self.save_path), "generation": 7,
                                          "operation_id": "synthetic-save-7"}}
        self.save_json(self.save_path, self.save)
        self.save_json(self.context_path, self.context)

    def test_initial_ini_v2_receipt_admits_without_native_save(self):
        self.assertEqual(self.verify()["catalog"], "migrated-for-MCR2")

    def test_initial_json_v2_admits(self):
        self.save_json(self.project, {"yaze_project": {"rom_filename": "rom",
                       "minecart_catalog_migration_receipt": "migration.json",
                       "dungeon_overlay": {"minecart_catalog_version": 2}}})
        self.assertEqual(self.verify()["catalog"], "migrated-for-MCR2")

    def test_legacy_missing_or_malformed_versions_refuse(self):
        for version in (None, 1, True, 2.0, "2"):
            with self.subTest(version=version):
                overlay = {} if version is None else {"minecart_catalog_version": version}
                self.save_json(self.project, {"yaze_project": {"rom_filename": "rom",
                               "minecart_catalog_migration_receipt": "migration.json", "dungeon_overlay": overlay}})
                with self.assertRaisesRegex(migration.PlanError, "version 2"):
                    self.verify()

    def test_descriptor_rom_and_explicit_environment_must_match(self):
        other = self.project_dir / "other-rom"
        other.write_bytes(self.initial)
        self.project.write_text(self.project.read_text().replace("rom_filename=rom", "rom_filename=other-rom"))
        with self.assertRaisesRegex(migration.PlanError, "YAZE_PROJECT_ROM"):
            self.verify()

    def test_explicit_migration_receipt_must_match_descriptor(self):
        other = self.root / "other-migration.json"
        other.write_bytes(self.migration_path.read_bytes())
        with self.assertRaisesRegex(migration.PlanError, "descriptor dependency"):
            self.verify(migration_path=other)

    def test_legitimate_new_junction_edit_with_current_native_save_admits(self):
        self.native_save()
        proof = self.verify()
        self.assertEqual((proof["catalog"], proof["generation"]), ("project-v2-native-save", 7))
        self.assertEqual(proof["migration_sha256"], migration.digest(self.migration_path.read_bytes()))

    def test_copied_input_must_match_current_saved_project_rom(self):
        self.native_save()
        data = bytearray(self.source.read_bytes())
        data[0x100000] ^= 1
        with self.assertRaisesRegex(migration.PlanError, "Copied assembly input"):
            self.verify(bytes(data))

    def test_stale_initial_image_cannot_qualify_a_later_project_rom(self):
        data = bytearray(self.initial)
        data[0x100000] ^= 1
        self.source.write_bytes(data)
        with self.assertRaisesRegex(migration.PlanError, "Copied assembly input"):
            self.verify(self.initial)

    def test_edited_project_requires_both_receipt_and_current_context(self):
        self.native_save()
        with self.assertRaisesRegex(migration.PlanError, "current native Save"):
            migration.verify_build_input(self.source.read_bytes(), project=self.project,
                                          project_rom=self.source, native_receipt=self.save_path)

    def test_every_declared_artifact_is_rehashed(self):
        for changed in (self.source, self.project, self.producer, self.sidecar, self.migration_path):
            with self.subTest(path=changed.name):
                self.native_save()
                before = changed.read_bytes()
                try:
                    changed.write_bytes(before + b" ")
                    with self.assertRaisesRegex(migration.PlanError, "changed after Save"):
                        self.verify()
                finally:
                    changed.write_bytes(before)

    def test_incomplete_native_receipt_refuses(self):
        self.native_save()
        self.save.update(bindings_complete=False, binding_errors=["rom: synthetic failure"])
        self.save_json(self.save_path, self.save)
        with self.assertRaisesRegex(migration.PlanError, "fully bound"):
            self.verify()

    def test_missing_migration_dependency_refuses(self):
        self.native_save()
        self.save["artifacts"] = [a for a in self.save["artifacts"] if a["role"] != "dependency.minecart_catalog_migration"]
        self.save_json(self.save_path, self.save)
        with self.assertRaisesRegex(migration.PlanError, "required roles"):
            self.verify()

    def test_duplicate_role_wrong_bytes_and_extra_root_key_refuse(self):
        self.native_save()
        original = json.loads(json.dumps(self.save))
        variants = []
        duplicate = json.loads(json.dumps(original))
        duplicate["artifacts"].append(duplicate["artifacts"][0])
        variants.append(duplicate)
        bad_bytes = json.loads(json.dumps(original))
        bad_bytes["artifacts"][0]["bytes"] = True
        variants.append(bad_bytes)
        variants.append({**original, "minecart_version": 2})
        for receipt in variants:
            with self.subTest(receipt=receipt):
                self.save_json(self.save_path, receipt)
                with self.assertRaises(migration.PlanError):
                    self.verify()

    def test_duplicate_json_keys_refuse(self):
        self.native_save()
        self.save_path.write_text(self.save_path.read_text().replace('"generation": 7', '"generation": 7, "generation": 7'))
        with self.assertRaisesRegex(migration.PlanError, "Duplicate JSON"):
            self.verify()

    def test_stale_generation_operation_and_retired_context_refuse(self):
        self.native_save()
        original = json.loads(json.dumps(self.context))
        for key, value in (("generation", 6), ("generation", True), ("operation_id", "old-save")):
            with self.subTest(key=key, value=value):
                context = json.loads(json.dumps(original))
                context["native_commit"][key] = value
                self.save_json(self.context_path, context)
                with self.assertRaisesRegex(migration.PlanError, "generation is stale"):
                    self.verify()
        self.save_json(self.context_path, {**original, "state": "rebound", "native_commit": None})
        with self.assertRaisesRegex(migration.PlanError, "retired"):
            self.verify()

    def test_context_producer_project_rom_or_identity_mismatch_refuses(self):
        self.native_save()
        original = json.loads(json.dumps(self.context))
        for key, value in (("project_path", str(self.root / "other.yaze")),
                           ("rom_path", str(self.root / "other-rom")),
                           ("producer", {**original["producer"], "sha256": "0" * 64}),
                           ("editing_source_path", str(self.root / "other-origin"))):
            with self.subTest(key=key):
                self.save_json(self.context_path, {**original, key: value})
                with self.assertRaises(migration.PlanError):
                    self.verify()

    def test_context_cannot_move_inside_project_or_use_another_identity_filename(self):
        self.native_save()
        for directory, name in ((self.project_dir / "native-saves", self.context_path.name),
                                (self.root / "native-saves", "another-context.json")):
            directory.mkdir(exist_ok=True)
            path = directory / name
            path.write_bytes(self.context_path.read_bytes())
            with self.subTest(path=path):
                with self.assertRaisesRegex(migration.PlanError, "stable editing-source identity"):
                    migration.verify_build_input(self.source.read_bytes(), project=self.project,
                        project_rom=self.source, native_receipt=self.save_path, native_context=path)

    def test_native_artifact_symlink_refuses(self):
        self.native_save()
        link = self.root / "producer-link"
        link.symlink_to(self.producer)
        next(a for a in self.save["artifacts"] if a["role"] == "producer")["path"] = str(link)
        self.save_json(self.save_path, self.save)
        with self.assertRaisesRegex(migration.PlanError, "non-symlink"):
            self.verify()

    def test_descriptor_replacement_cannot_mix_old_version_decision_with_new_receipt(self):
        self.native_save()
        real_bound = migration.bound_file
        def replace_project(path):
            if path == self.project:
                self.project.write_text(self.project.read_text().replace("minecart_catalog_version=2", "minecart_catalog_version=1"))
                row = next(a for a in self.save["artifacts"] if a["role"] == "project")
                row.update(sha256=migration.digest(self.project.read_bytes()), bytes=self.project.stat().st_size)
                self.save_json(self.save_path, self.save)
            return real_bound(path)
        with mock.patch.object(migration, "bound_file", side_effect=replace_project):
            with self.assertRaisesRegex(migration.PlanError, "descriptor changed during admission"):
                self.verify()

    def test_migration_replacement_cannot_mix_old_header_with_new_native_binding(self):
        self.native_save()
        real_bound = migration.bound_file
        changed = False
        def replace_evidence(path):
            nonlocal changed
            if path == self.migration_path and not changed:
                changed = True
                self.migration_path.write_text('{}')
                row = next(a for a in self.save["artifacts"] if a["role"] == "dependency.minecart_catalog_migration")
                row.update(sha256=migration.digest(self.migration_path.read_bytes()), bytes=self.migration_path.stat().st_size)
                self.save_json(self.save_path, self.save)
            return real_bound(path)
        with mock.patch.object(migration, "bound_file", side_effect=replace_evidence):
            with self.assertRaisesRegex(migration.PlanError, "evidence changed during admission"):
                self.verify()

    def test_artifact_reread_cannot_replace_the_pinned_project_snapshot(self):
        self.native_save()
        replacement = self.project.read_bytes() + b"# older persisted descriptor\n"
        row = next(a for a in self.save["artifacts"] if a["role"] == "project")
        row.update(sha256=migration.digest(replacement), bytes=len(replacement))
        self.save_json(self.save_path, self.save)
        real_bound = migration.bound_file
        project_reads = 0
        def replace_at_artifact(path):
            nonlocal project_reads
            if path == self.project:
                project_reads += 1
                if project_reads == 2:
                    self.project.write_bytes(replacement)
            return real_bound(path)
        with mock.patch.object(migration, "bound_file", side_effect=replace_at_artifact):
            with self.assertRaisesRegex(migration.PlanError, "input changed during admission"):
                self.verify()

    def test_native_cli_uses_existing_environment_contract(self):
        self.native_save()
        env = {"YAZE_PROJECT_FILE": str(self.project), "YAZE_PROJECT_ROM": str(self.source),
               "YAZE_NATIVE_SAVE_RECEIPT": str(self.save_path), "YAZE_NATIVE_SAVE_CONTEXT": str(self.context_path)}
        output = io.StringIO()
        with mock.patch.dict(os.environ, env, clear=True), contextlib.redirect_stdout(output):
            result = migration.main(["--rom", str(self.source), "--verify-build-input"])
        self.assertEqual(result, 0)
        self.assertEqual(json.loads(output.getvalue())["generation"], 7)


class ProjectBundleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="minecart-bundle-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.rom = self.root / "source.sfc"
        self.original = fixture()
        self.rom.write_bytes(self.original)
        self.project = self.root / "source.yaze"
        self.sidecar = self.root / "collision.json"
        self.sidecar.write_bytes(b'{"rooms":[],"version":1}\n')
        self.terrain = self.root / "terrain.json"
        self.terrain.write_bytes(b'{"synthetic_terrain":true}\n')
        self.project.write_text("# Keep this comment\n[files]\nrom_filename=source.sfc\n"
                                "custom_collision_json=collision.json\nlyra_terrain_file=terrain.json\ncustom_objects_folder=old-assets\n"
                                "[dungeon_overlay]\ntrack_object_ids=0x31\n"
                                "[build]\nbuild_script=old-shared-writer\n"
                                "[custom_objects]\nobject_0x54=kydreeok_body.bin,manhandla_body_1a.bin\n"
                                "[workspace]\nrecent_files=shared.yaze\n")
        self.assets = self.root / "candidate-assets"
        self.assets.mkdir()
        source_assets = Path(migration.__file__).resolve().parents[2] / "Dungeons/Objects/Data"
        for name in {v for values in migration.OBJECT_FILES.values() for v in values if v}:
            (self.assets / name).write_bytes((source_assets / name).read_bytes())
        self.legacy_assets = self.root / "old-assets"
        self.legacy_assets.mkdir()
        for name in {v for values in migration.LEGACY_OBJECT_FILES.values() for v in values}:
            (self.legacy_assets / name).write_bytes((self.assets / name).read_bytes())
        self.bundle = self.root / "candidate.yazeproj"

    def publish(self, **extra):
        result, report = migration.plan_migration(self.original, migration.digest(self.original))
        return migration.publish_project_bundle(self.project, self.rom, result, report, self.bundle,
                                                migration.digest(self.project.read_bytes()), (), self.assets, **extra)

    def test_bundle_preserves_inputs_and_publishes_29_assets_reserved_slots_and_private_sidecar(self):
        before = {p: p.read_bytes() for p in (self.project, self.rom, self.sidecar, self.terrain)}
        proof = self.publish()
        fields, overlay, objects, _ = migration.project_fields((self.bundle / "project.yaze").read_bytes())
        self.assertEqual(overlay["minecart_catalog_version"], "2")
        self.assertEqual(overlay["track_object_ids"], "0x31,0x32")
        self.assertEqual(objects["object_0x32"].split(",")[3:5], ["", ""])
        self.assertEqual(len(objects["object_0x32"].split(",")), 13)
        self.assertEqual(len(list((self.bundle / "custom_objects").iterdir())), 29)
        owned_collision = Path(migration.__file__).resolve().parents[2] / "Data/dungeons/custom_collision.json"
        self.assertEqual(fields["custom_collision_json"], str(owned_collision))
        self.assertEqual(proof["external_writable_owned_sources"]["custom_collision_json"]["sha256"],
                         migration.digest(owned_collision.read_bytes()))
        self.assertEqual((self.bundle / fields["lyra_terrain_file"]).read_bytes(), before[self.terrain])
        self.assertEqual(fields["custom_objects_folder"], str(self.assets))
        self.assertEqual(fields["rom_filename"], "rom")
        self.assertNotIn("old-shared-writer", (self.bundle / "project.yaze").read_text())
        self.assertIn("# Keep this comment", (self.bundle / "project.yaze").read_text())
        self.assertEqual((self.bundle / "migration-receipt.json").stat().st_mode & 0o777, 0o444)
        self.assertEqual(migration.verify_build_input((self.bundle / "rom").read_bytes(),
                         project=self.bundle / "project.yaze", project_rom=self.bundle / "rom")["catalog"],
                         "migrated-for-MCR2")
        for path, expected in before.items():
            self.assertEqual(path.read_bytes(), expected)
        for name, binding in proof["files"].items():
            self.assertEqual(migration.digest((self.bundle / name).read_bytes()), binding["sha256"])

    def test_existing_bundle_is_never_overwritten(self):
        self.bundle.mkdir()
        sentinel = self.bundle / "saved-game"
        sentinel.write_bytes(b"preserve")
        with self.assertRaisesRegex(migration.PlanError, "already exists"):
            self.publish()
        self.assertEqual(sentinel.read_bytes(), b"preserve")
        self.assertEqual(list(self.bundle.iterdir()), [sentinel])

    def test_wrong_project_hash_refuses_before_bundle_creation(self):
        result, report = migration.plan_migration(self.original, migration.digest(self.original))
        with self.assertRaisesRegex(migration.PlanError, "Project SHA-256"):
            migration.publish_project_bundle(self.project, self.rom, result, report, self.bundle,
                                              "0" * 64, (), self.assets)
        self.assertFalse(self.bundle.exists())

    def test_failure_retains_private_recovery_and_no_descriptor(self):
        real_publish = migration.publish_exclusive
        def fail_on_rom(path, content, mode):
            if path.name == "rom":
                raise OSError("synthetic publication failure")
            real_publish(path, content, mode)
        with mock.patch.object(migration, "publish_exclusive", side_effect=fail_on_rom):
            with self.assertRaisesRegex(OSError, "synthetic"):
                self.publish()
        self.assertTrue(self.bundle.is_dir())
        self.assertFalse((self.bundle / "project.yaze").exists())
        self.assertEqual(self.rom.read_bytes(), self.original)

    def test_unreviewed_custom_family_refuses_before_any_output(self):
        self.project.write_text(self.project.read_text().replace("object_0x54=", "object_0x33="))
        with self.assertRaisesRegex(migration.PlanError, "allocation review"):
            self.publish()
        self.assertFalse(self.bundle.exists())

    def test_json_bundle_preserves_typed_arrays_and_reserved_entries(self):
        self.project.write_text(json.dumps({"yaze_project": {"name": "fixture",
            "rom_filename": "source.sfc", "additional_roms": [], "custom_objects_folder": "old-assets",
            "custom_objects": {"0x31": migration.LEGACY_OBJECT_FILES["0x31"]},
            "dungeon_overlay": {"minecart_catalog_version": 1}}}))
        self.publish()
        fields, overlay, objects, _ = migration.project_fields((self.bundle / "project.yaze").read_bytes())
        self.assertEqual(fields["additional_roms"], [])
        self.assertEqual(overlay["track_object_ids"], [0x31, 0x32])
        self.assertIs(type(overlay["minecart_catalog_version"]), int)
        self.assertEqual(objects["0x32"][3:5], ["", ""])

    def test_explicit_filename_override_refuses_without_changing_inputs(self):
        self.project.write_text(self.project.read_text().replace("kydreeok_body.bin", "custom-boss.bin"))
        before = self.project.read_bytes()
        with self.assertRaisesRegex(migration.PlanError, "filename overrides"):
            self.publish()
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(self.bundle.exists())

    def test_changed_legacy_artwork_refuses_instead_of_switching_source(self):
        asset = self.legacy_assets / "track_LR.bin"
        asset.write_bytes(asset.read_bytes() + b"external custom artwork")
        before = asset.read_bytes()
        with self.assertRaisesRegex(migration.PlanError, "artwork differs"):
            self.publish()
        self.assertEqual(asset.read_bytes(), before)
        self.assertFalse(self.bundle.exists())

    def test_cli_publishes_only_the_new_bundle_and_requires_project_pin(self):
        args = ["--rom", str(self.rom), "--expected-sha256", migration.digest(self.original),
                "--project", str(self.project), "--project-output", str(self.bundle)]
        output, error = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertEqual(migration.main(args, protected_dirs=()), 1)
        self.assertIn("expected-project-sha256", error.getvalue())
        self.assertFalse(self.bundle.exists())
        with contextlib.redirect_stdout(output), contextlib.redirect_stderr(error):
            self.assertEqual(migration.main([*args, "--expected-project-sha256",
                migration.digest(self.project.read_bytes())], protected_dirs=()), 0)
        self.assertTrue((self.bundle / "project.yaze").exists())
        self.assertEqual(self.rom.read_bytes(), self.original)

    def test_source_change_during_publication_refuses_before_descriptor(self):
        real_publish = migration.publish_exclusive
        def race_source(path, content, mode):
            real_publish(path, content, mode)
            if path.name == "rom":
                self.rom.write_bytes(self.original + b"external edit")
        with mock.patch.object(migration, "publish_exclusive", side_effect=race_source):
            with self.assertRaisesRegex(migration.PlanError, "changed during bundle"):
                self.publish()
        self.assertFalse((self.bundle / "project.yaze").exists())
        self.assertEqual(self.rom.read_bytes(), self.original + b"external edit")


if __name__ == "__main__":
    unittest.main()
