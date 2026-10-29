"""Synthetic-only checks for the guarded object catalog migration."""
import contextlib
import io
import json
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


if __name__ == "__main__":
    unittest.main()
