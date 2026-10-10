"""Offline control-flow tests for the module isolation runner; no build or emulator."""

from __future__ import annotations

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


SCRIPT = Path(__file__).resolve().parents[1] / "run_module_isolation_auto.py"
spec = importlib.util.spec_from_file_location("oos_module_isolation_auto", SCRIPT)
isolation = importlib.util.module_from_spec(spec)
spec.loader.exec_module(isolation)


class ModuleIsolationFailureTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root / "Roms").mkdir()
        self.rom = self.root / "Roms/oos168x.sfc"
        self.report = self.root / "result.json"
        root_patch = mock.patch.object(isolation, "REPO_ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def run_main(self, responses, *args):
        with mock.patch.object(isolation, "run_cmd", side_effect=responses) as commands:
            with mock.patch.object(sys, "argv", [str(SCRIPT), *args, "--json", str(self.report)]):
                with contextlib.redirect_stdout(io.StringIO()) as output:
                    status = isolation.main()
        report = json.loads(self.report.read_text())
        return status, report, commands, output.getvalue()

    def test_successful_build_without_output_never_reloads_or_bisects(self):
        status, report, commands, _ = self.run_main(
            [(0, "", ""), (0, "", "")], "--module", "menu")
        self.assertEqual(status, 1)
        self.assertEqual(commands.call_count, 2)
        self.assertEqual(report["results"][0]["result"], "error")
        self.assertIn("ROM output is missing", report["results"][0]["note"])

    def test_failed_rom_reload_never_runs_the_softlock_probe(self):
        self.rom.write_bytes(b"candidate")
        status, report, commands, _ = self.run_main(
            [(0, "", ""), (0, "", ""), (1, "", "connection refused")],
            "--module", "menu")
        self.assertEqual(status, 1)
        self.assertEqual(commands.call_count, 3)
        self.assertEqual(report["results"][0]["result"], "error")
        self.assertIn("connection refused", report["results"][0]["note"])
        self.assertNotIn("menu", report["guilty_candidates"])

    def test_failed_restore_flags_is_reported_and_fails_the_run(self):
        self.rom.write_bytes(b"candidate")
        with mock.patch.object(isolation, "MODULES_ORDER", ["menu"]):
            status, report, commands, output = self.run_main(
                [(0, "", ""), (0, "", ""), (0, "", ""), (0, "", ""),
                 (1, "", "read-only config")])
        self.assertEqual(status, 1)
        self.assertEqual(commands.call_count, 5)
        self.assertEqual(report["results"][0]["result"], "pass")
        self.assertEqual(report["restoration"]["status"], "failed")
        self.assertIn("read-only config", report["restoration"]["note"])
        self.assertIn("RESTORE FAILED", output)

    def test_failed_restore_build_is_reported_and_fails_the_run(self):
        self.rom.write_bytes(b"candidate")
        with mock.patch.object(isolation, "MODULES_ORDER", ["menu"]):
            status, report, commands, _ = self.run_main(
                [(0, "", ""), (0, "", ""), (0, "", ""), (1, "", "softlock"),
                 (0, "", ""), (1, "", "restore build failed")])
        self.assertEqual(status, 1)
        self.assertEqual(commands.call_count, 6)
        self.assertEqual(report["results"][0]["result"], "fail")
        self.assertEqual(report["restoration"]["status"], "failed")
        self.assertIn("restore build failed", report["restoration"]["note"])

    def test_command_timeout_is_an_infrastructure_failure(self):
        with mock.patch.object(isolation.subprocess, "run",
                               side_effect=subprocess.TimeoutExpired(["fake"], 10)):
            self.assertEqual(isolation.run_cmd(["fake"], self.root, timeout=10)[0], 124)


if __name__ == "__main__":
    unittest.main()
