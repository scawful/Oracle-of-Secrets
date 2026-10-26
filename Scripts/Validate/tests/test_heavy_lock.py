"""Tests for Scripts/Agents/heavy_lock.py (shared heavy lock with dead-owner reclaim).

Each test points the module at a lock path inside a temporary directory;
nothing touches /tmp/oos-heavy.lock.
"""
from __future__ import annotations

import importlib.util
import datetime
from unittest.mock import patch
import json
import os
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "Scripts" / "Agents" / "heavy_lock.py"
spec = importlib.util.spec_from_file_location("heavy_lock", SCRIPT)
hl = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = hl
spec.loader.exec_module(hl)


def dead_pid() -> int:
    proc = subprocess.Popen(["/usr/bin/true"])
    proc.wait()
    return proc.pid


class HeavyLockTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        self.saved = (hl.LOCK, hl.ARCHIVE)
        hl.LOCK = root / "oos-heavy.lock"
        hl.ARCHIVE = root / "reclaimed"

    def tearDown(self):
        hl.LOCK, hl.ARCHIVE = self.saved
        self.tmp.cleanup()

    def write_owner(self, data):
        hl.LOCK.mkdir()
        text = data if isinstance(data, str) else json.dumps(data)
        (hl.LOCK / "owner").write_text(text, encoding="utf-8")

    def test_acquire_release(self):
        token = hl.acquire("t", "unit test")
        self.assertIsNotNone(token)
        owner = hl.read_owner()
        self.assertEqual(owner["pid"], os.getpid())
        self.assertEqual(owner["pid_start"], hl.process_start(os.getpid()))
        self.assertEqual(hl.status()["state"], "held")
        self.assertTrue(hl.release(token))
        self.assertEqual(hl.status()["state"], "free")

    def test_release_wrong_token_refused(self):
        token = hl.acquire("t", "unit test")
        self.assertFalse(hl.release("not-the-token"))
        self.assertTrue(hl.LOCK.exists())
        self.assertTrue(hl.release(token))

    def test_live_owner_kept(self):
        self.write_owner({"owner": "other", "token": "x", "pid": os.getpid(),
                          "pid_start": hl.process_start(os.getpid())})
        self.assertIsNone(hl.acquire("t", "unit test", wait=0))
        self.assertEqual(hl.read_owner()["owner"], "other")

    def test_dead_owner_reclaimed_and_archived(self):
        self.write_owner({"owner": "gone", "token": "x", "pid": dead_pid()})
        token = hl.acquire("t", "unit test", wait=0)
        self.assertIsNotNone(token)
        self.assertEqual(hl.read_owner()["owner"], "t")
        archived = list(hl.ARCHIVE.glob("*-owner.json"))
        self.assertEqual(len(archived), 1)
        self.assertEqual(json.loads(archived[0].read_text())["owner"], "gone")
        self.assertIn("has exited", next(hl.ARCHIVE.glob("*-reason.txt")).read_text())

    def test_reused_pid_reclaimed(self):
        self.write_owner({"owner": "old", "token": "x", "pid": os.getpid(),
                          "pid_start": "Mon Jan  1 00:00:00 2001"})
        self.assertEqual(hl.status()["state"], "stale")
        self.assertIsNotNone(hl.acquire("t", "unit test", wait=0))

    def test_codex_process_identity_format(self):
        start = hl.process_start(os.getpid())
        self.write_owner({"owner": "codex", "token": "x", "pid": os.getpid(),
                          "process_identity": f"{start}     /bin/sh"})
        self.assertEqual(hl.status()["state"], "held")
        (hl.LOCK / "owner").write_text(json.dumps(
            {"owner": "codex", "token": "x", "pid": os.getpid(),
             "process_identity": "Mon Jan  1 00:00:00 2001     /bin/sh"}))
        self.assertEqual(hl.status()["state"], "stale")

    def test_legacy_owner_kept(self):
        self.write_owner("owner=someone\n")
        st = hl.status()
        self.assertEqual(st["state"], "held")
        self.assertIn("legacy", st["reason"])
        self.assertIsNone(hl.acquire("t", "unit test", wait=0))
        self.assertTrue(hl.LOCK.exists())

    def test_orphan_dir_reclaimed_only_when_old(self):
        hl.LOCK.mkdir()
        self.assertEqual(hl.status()["state"], "held")
        old = time.time() - hl.ORPHAN_AGE - 5
        os.utime(hl.LOCK, (old, old))
        self.assertEqual(hl.status()["state"], "stale")
        self.assertIsNotNone(hl.acquire("t", "unit test", wait=0))

    def test_wait_times_out(self):
        self.write_owner({"owner": "other", "token": "x", "pid": os.getpid()})
        t0 = time.monotonic()
        self.assertIsNone(hl.acquire("t", "unit test", wait=0.3, poll=0.05))
        self.assertGreaterEqual(time.monotonic() - t0, 0.25)

    def test_reclaim_excludes_release_and_new_acquire(self):
        self.write_owner({"owner": "gone", "token": "old", "pid": dead_pid()})
        original = hl.status
        def interleave():
            snapshot = original()
            self.assertFalse(hl.release("old"))
            self.assertIsNone(hl.acquire("new", "test"))
            return snapshot
        with patch.object(hl, "status", side_effect=interleave):
            self.assertIsNotNone(hl.reclaim_if_stale())
        token = hl.acquire("new", "test")
        self.assertIsNotNone(token)
        self.assertFalse(hl.release("old"))
        self.assertEqual(hl.read_owner()["token"], token)

    def test_release_excludes_reclaim_and_new_acquire(self):
        self.write_owner({"owner": "gone", "token": "old", "pid": dead_pid()})
        original = hl.read_owner
        def interleave():
            snapshot = original()
            self.assertIsNone(hl.reclaim_if_stale())
            self.assertIsNone(hl.acquire("new", "test"))
            return snapshot
        with patch.object(hl, "read_owner", side_effect=interleave):
            self.assertTrue(hl.release("old"))
        token = hl.acquire("new", "test")
        self.assertIsNotNone(token)
        self.assertFalse(hl.release("old"))
        self.assertEqual(hl.status()["state"], "held")

    def test_failed_ps_keeps_live_owner_and_refuses_acquire(self):
        token = hl.acquire("live", "test")
        for reply in (subprocess.CompletedProcess([], 1, "", "failed"),
                      subprocess.CompletedProcess([], 0, "", "")):
            with patch.object(hl.subprocess, "run", return_value=reply):
                self.assertEqual(hl.status()["state"], "held")
                self.assertIsNone(hl.reclaim_if_stale())
                self.assertIsNone(hl.acquire("other", "test"))
        self.assertTrue(hl.release(token))

    def test_dead_or_invalid_worker_refused(self):
        for pid in (dead_pid(), 0, -1, True):
            self.assertIsNone(hl.acquire("dead", "test", pid=pid))
            self.assertFalse(hl.LOCK.exists())

    def test_same_second_archives_are_distinct(self):
        class FrozenDatetime(datetime.datetime):
            @classmethod
            def now(cls, tz=None):
                return cls(2026, 10, 23, 20, 0, 0, tzinfo=tz)
        with patch.object(hl.dt, "datetime", FrozenDatetime):
            for owner in ("first", "second"):
                self.write_owner({"owner": owner, "pid": dead_pid()})
                self.assertIsNotNone(hl.reclaim_if_stale())
        receipts = list(hl.ARCHIVE.glob("*-owner.json"))
        self.assertEqual({json.loads(p.read_text())["owner"] for p in receipts}, {"first", "second"})
        self.assertEqual(len(list(hl.ARCHIVE.glob("*-reason.txt"))), 2)

    def test_cli_exit_codes(self):
        env = dict(os.environ, OOS_HEAVY_LOCK=str(hl.LOCK), OOS_HEAVY_LOCK_ARCHIVE=str(hl.ARCHIVE))
        run = lambda *a: subprocess.run([sys.executable, str(SCRIPT), *a], env=env,
                                        capture_output=True, text=True)
        got = run("acquire", "--owner", "cli", "--purpose", "unit test", "--pid", str(os.getpid()))
        self.assertEqual(got.returncode, 0, got.stderr)
        token = got.stdout.strip()
        self.assertEqual(run("acquire", "--owner", "cli2", "--purpose", "x", "--wait", "0").returncode, 3)
        self.assertEqual(run("release", "--token", "wrong").returncode, 1)
        self.assertEqual(run("release", "--token", token).returncode, 0)
        self.assertEqual(json.loads(run("status").stdout)["state"], "free")


if __name__ == "__main__":
    unittest.main()
