"""Synthetic SRAM checks for declared prerequisites and safe publication."""
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import prepare_progression_fixture as fixture


def seed(slot=1, gloves=0, rods=0, owned=0):
    # Distinct canaries make unrelated slot/tail mutations visible.
    data = bytearray((i * 17 + i // 256 + 31) & 255 for i in range(8192))
    start = (slot - 1) * 0x500
    block = bytearray(data[start:start + 0x500])
    block[0x3E5:0x3E7] = b"\xAA\x55"
    block[0x354], block[0x351], block[0x3A6] = gloves, rods, owned
    block[0x4FE:] = b"\0\0"
    block[0x4FE:] = ((0x5A5A - fixture.word_sum(block)) & 65535).to_bytes(2, "little")
    for offset in (start, start + 0xF00):
        data[offset:offset + 0x500] = block
    return bytes(data)


class ProgressionFixtureTest(unittest.TestCase):
    def test_all_slots_change_only_glove_and_mirrored_checksum(self):
        for slot in (1, 2, 3):
            with self.subTest(slot=slot):
                source = seed(slot)
                result, report = fixture.prepare(source, slot)
                primary = (slot - 1) * 0x500
                allowed = {start + offset for start in (primary, primary + 0xF00)
                           for offset in (0x354, 0x4FE, 0x4FF)}
                changed = {i for i, (a, b) in enumerate(zip(source, result)) if a != b}
                self.assertTrue(changed <= allowed)
                self.assertIn(primary + 0x354, changed)
                block = result[primary:primary + 0x500]
                self.assertEqual(block, result[primary + 0xF00:primary + 0x1400])
                self.assertEqual(fixture.word_sum(block), 0x5A5A)
                self.assertEqual((block[0x354], block[0x351], block[0x3A6]), (1, 0, 0))
                self.assertEqual(report["changed_offsets"], [f"0x{i:04X}" for i in sorted(changed)])
                self.assertTrue(report["prerequisites"][0]["supplied"])
                self.assertFalse(report["acquisition_tested"])

    def test_existing_power_glove_and_mitt_are_retained_without_any_byte_change(self):
        for gloves in (1, 2):
            with self.subTest(gloves=gloves):
                source = seed(gloves=gloves)
                result, report = fixture.prepare(source, 1)
                self.assertEqual(result, source)
                self.assertEqual(report["changed_offsets"], [])
                self.assertEqual(report["prerequisites"][0]["after"], gloves)
                self.assertFalse(report["prerequisites"][0]["supplied"])

    def test_rejects_rod_or_portal_ownership_instead_of_removing_it(self):
        for rods, owned in ((1, 0), (2, 0), (0, 1)):
            with self.subTest(rods=rods, owned=owned):
                with self.assertRaisesRegex(ValueError, "CustomRods=0"):
                    fixture.prepare(seed(rods=rods, owned=owned), 1)

    def test_rejects_unknown_profile_slot_and_glove_level(self):
        for kwargs in ({"profile": "all-items"}, {"slot": 0}, {"slot": 4},
                       {"slot": True}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                fixture.prepare(seed(), **({"slot": 1} | kwargs))
        with self.assertRaisesRegex(ValueError, "Gloves must"):
            fixture.prepare(seed(gloves=3), 1)

    def test_rejects_size_magic_checksum_and_backup_corruption(self):
        cases = [(seed()[:-1], "8192")]
        for offset, message in ((0x3E5, "initialized"), (0x4FE, "backup/checksum"),
                                (0xF10, "backup/checksum")):
            data = bytearray(seed())
            data[offset] ^= 1
            cases.append((bytes(data), message))
        data = bytearray(seed())
        data[0x4FE] ^= 1
        data[0xF00:0x1400] = data[:0x500]
        cases.append((bytes(data), "backup/checksum"))
        for data, message in cases:
            with self.subTest(message=message), self.assertRaisesRegex(ValueError, message):
                fixture.prepare(data, 1)

    def test_cli_creates_declared_fixture_and_preserves_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, report = (root / n for n in ("in.srm", "out.srm", "out.json"))
            data = seed(slot=2)
            source.write_bytes(data)
            proc = subprocess.run([sys.executable, fixture.__file__, "--input", str(source),
                                   "--output", str(output), "--report", str(report),
                                   "--slot", "2", "--profile", fixture.PROFILE],
                                  capture_output=True, text=True)
            self.assertEqual(proc.returncode, 0, proc.stderr)
            metadata = json.loads(report.read_text())
            self.assertEqual(json.loads(proc.stdout), metadata)
            self.assertEqual(metadata["output_sha256"], fixture.sha256(output.read_bytes()))
            self.assertEqual(metadata["ungranted"], {"CustomRods": 0, "PortalRodOwned": 0})
            self.assertEqual(source.read_bytes(), data)

    def test_existing_output_or_report_is_never_overwritten(self):
        for occupied in ("out.srm", "out.json"):
            with self.subTest(occupied=occupied), tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                source = root / "in.srm"
                source.write_bytes(seed())
                (root / occupied).write_bytes(b"existing unique artifact")
                with self.assertRaisesRegex(ValueError, "already exists"):
                    fixture.write_fixture(source, root / "out.srm", root / "out.json", 1)
                self.assertEqual((root / occupied).read_bytes(), b"existing unique artifact")
                self.assertEqual(len(list(root.iterdir())), 2)

    def test_alias_paths_are_refused(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, report = (root / n for n in ("in.srm", "out.srm", "out.json"))
            source.write_bytes(seed())
            alias = root / "alias.srm"
            alias.symlink_to(source)
            for paths in ((source, source, report), (source, output, source),
                          (source, output, output), (source, alias, report)):
                with self.subTest(paths=paths), self.assertRaisesRegex(ValueError, "separate"):
                    fixture.write_fixture(*paths, 1)
            self.assertEqual(source.read_bytes(), seed())

    def test_report_reservation_failure_removes_only_own_empty_output(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, report = (root / n for n in ("in.srm", "out.srm", "out.json"))
            source.write_bytes(seed())
            report.symlink_to(root / "missing-target")
            with self.assertRaises(FileExistsError):
                fixture.write_fixture(source, output, report, 1)
            self.assertFalse(output.exists())
            self.assertTrue(report.is_symlink())
            self.assertFalse((root / "missing-target").exists())

    def test_write_failure_cleans_both_new_artifacts(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source, output, report = (root / n for n in ("in.srm", "out.srm", "out.json"))
            source.write_bytes(seed())
            with mock.patch.object(fixture.os, "fsync", side_effect=OSError("disk failure")):
                with self.assertRaisesRegex(OSError, "disk failure"):
                    fixture.write_fixture(source, output, report, 1)
            self.assertFalse(output.exists())
            self.assertFalse(report.exists())
            self.assertEqual(source.read_bytes(), seed())


if __name__ == "__main__":
    unittest.main()
