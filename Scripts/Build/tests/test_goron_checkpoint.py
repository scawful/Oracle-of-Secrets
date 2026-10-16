"""Protect the two-file SRAM boundary and refuse substituted/overwritten saves."""
import importlib.util
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).resolve().parents[1] / "prepare_goron_checkpoint.py"
spec = importlib.util.spec_from_file_location("goron_checkpoint", SCRIPT)
checkpoint = importlib.util.module_from_spec(spec)
spec.loader.exec_module(checkpoint)


class GoronCheckpointTest(unittest.TestCase):
    def setUp(self):
        # Nonzero canaries in every byte make collateral writes observable.
        image = bytearray((i * 17 + 31) & 255 for i in range(8192))
        block = bytearray(image[0x500:0xA00])
        for offset in (0x3C8, 0x3CA, 0x3CC):
            block[offset] = 0
        block[0x3C5] = 2
        block[0x4FE:] = b"\0\0"
        block[0x4FE:] = ((0x5A5A - checkpoint.word_sum(block)) & 65535).to_bytes(2, "little")
        image[0x500:0xA00] = block
        image[0x1400:0x1900] = block
        self.image = bytes(image)

    def test_native_checksum_mirror_and_only_six_authorized_bytes(self):
        with mock.patch.object(checkpoint, "CANONICAL_SHA256", checkpoint.sha256(self.image)):
            result = checkpoint.prepare(self.image)
        changed = {i for i, (a, b) in enumerate(zip(self.image, result)) if a != b}
        self.assertTrue(changed <= {0x8C8, 0x9FE, 0x9FF, 0x17C8, 0x18FE, 0x18FF})
        self.assertTrue({0x8C8, 0x17C8} <= changed)
        self.assertEqual(result[0x8C8], 7)
        self.assertEqual(result[0x500:0xA00], result[0x1400:0x1900])
        self.assertEqual(checkpoint.word_sum(result[0x500:0xA00]), 0x5A5A)

    def test_other_valid_native_save_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "exact canonical"):
            checkpoint.prepare(self.image)

    def test_truncated_save_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "8192"):
            checkpoint.prepare(self.image[:-1])

    def test_cli_never_overwrites_existing_output(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source, output, report = (root / name for name in ("input.srm", "output.srm", "report.json"))
            source.write_bytes(self.image)
            output.write_bytes(b"saved game")
            proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source),
                                   "--output", str(output), "--report", str(report)],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("already exists", proc.stderr)
            self.assertEqual(output.read_bytes(), b"saved game")
            self.assertEqual(source.read_bytes(), self.image)
            self.assertFalse(report.exists())

    def test_cli_refuses_input_as_output(self):
        with tempfile.TemporaryDirectory() as temp:
            source = Path(temp) / "input.srm"
            source.write_bytes(self.image)
            proc = subprocess.run([sys.executable, str(SCRIPT), "--input", str(source),
                                   "--output", str(source), "--report", str(Path(temp) / "report")],
                                  capture_output=True, text=True)
            self.assertNotEqual(proc.returncode, 0)
            self.assertIn("separate paths", proc.stderr)
            self.assertEqual(source.read_bytes(), self.image)


if __name__ == "__main__":
    unittest.main()
