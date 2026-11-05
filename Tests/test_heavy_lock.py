"""Process-exit observation and conservative heavy-lease regression checks."""

import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock


class HeavyLockProcessTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if os.name != "posix":
            raise unittest.SkipTest("heavy_lock uses POSIX process and lease APIs")
        path = Path(__file__).resolve().parents[1] / "Scripts/Agents/heavy_lock.py"
        spec = importlib.util.spec_from_file_location("heavy_lock_process_test", path)
        cls.heavy = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.heavy)

    def result(self, code=0, stdout="Thu Nov 5 01:00:00 2026\n"):
        return subprocess.CompletedProcess([], code, stdout, "")

    def test_live_identity_is_normalized(self):
        with mock.patch.object(self.heavy.os, "kill") as probe, mock.patch.object(
            self.heavy.subprocess, "run", return_value=self.result(stdout=" Thu  Nov 5 01:00:00 2026\n")
        ):
            self.assertEqual(self.heavy.process_start(12345), "Thu Nov 5 01:00:00 2026")
            probe.assert_called_once_with(12345, 0)

    def test_pid_absent_before_ps(self):
        with mock.patch.object(self.heavy.os, "kill", side_effect=ProcessLookupError), mock.patch.object(
            self.heavy.subprocess, "run"
        ) as inspect:
            self.assertIsNone(self.heavy.process_start(12345))
            inspect.assert_not_called()

    def test_permission_to_probe_still_uses_ps(self):
        with mock.patch.object(self.heavy.os, "kill", side_effect=PermissionError), mock.patch.object(
            self.heavy.subprocess, "run", return_value=self.result()
        ):
            self.assertEqual(self.heavy.process_start(12345), "Thu Nov 5 01:00:00 2026")

    def test_exit_between_probe_and_failed_ps(self):
        for result in (self.result(1, ""), self.result(0, ""), self.result(1, "old identity")):
            with self.subTest(result=result), mock.patch.object(
                self.heavy.os, "kill", side_effect=[None, ProcessLookupError()]
            ) as probe, mock.patch.object(self.heavy.subprocess, "run", return_value=result):
                self.assertIsNone(self.heavy.process_start(12345))
                self.assertEqual(probe.call_args_list, [mock.call(12345, 0)] * 2)

    def test_failed_ps_keeps_live_or_unknown_identity_protected(self):
        for second_probe in (None, PermissionError(), OSError("probe unavailable")):
            with self.subTest(second_probe=second_probe), mock.patch.object(
                self.heavy.os, "kill", side_effect=[None, second_probe]
            ), mock.patch.object(self.heavy.subprocess, "run", return_value=self.result(1, "")):
                with self.assertRaises(self.heavy.ProcessInspectionError):
                    self.heavy.process_start(12345)

    def test_unavailable_ps_remains_unknown(self):
        with mock.patch.object(self.heavy.os, "kill") as probe, mock.patch.object(
            self.heavy.subprocess, "run", side_effect=FileNotFoundError("ps unavailable")
        ):
            with self.assertRaises(self.heavy.ProcessInspectionError):
                self.heavy.process_start(12345)
            probe.assert_called_once_with(12345, 0)

    def test_unknown_identity_cannot_reclaim_lease(self):
        with tempfile.TemporaryDirectory(prefix="heavy-process-test-") as root:
            root = Path(root)
            lock = root / "heavy.lock"
            lock.mkdir()
            owner = json.dumps({"pid": 12345, "pid_start": "original identity", "token": "owned-token"})
            (lock / "owner").write_text(owner)
            with mock.patch.object(self.heavy, "ARCHIVE", root / "archive"), mock.patch.object(
                self.heavy.os, "kill"
            ), mock.patch.object(self.heavy.subprocess, "run", return_value=self.result(1, "")):
                self.assertIsNone(self.heavy._reclaim_if_stale(lock))
            self.assertEqual((lock / "owner").read_text(), owner)
            self.assertFalse((root / "archive").exists())

    def test_real_child_exit_between_probe_and_ps(self):
        # Reap our own child before the real ps call to reproduce the exit race.
        child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
        real_run = subprocess.run

        def exit_before_ps(*args, **kwargs):
            child.terminate()
            child.wait(timeout=5)
            return real_run(*args, **kwargs)

        try:
            with mock.patch.object(self.heavy.subprocess, "run", side_effect=exit_before_ps):
                self.assertIsNone(self.heavy.process_start(child.pid))
            self.assertIsNotNone(child.returncode)
        finally:
            if child.poll() is None:
                child.kill()
                child.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
