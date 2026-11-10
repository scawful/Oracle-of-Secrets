"""Tests for Scripts/Agents/native_session.py (owned native runs and teardown).

A fake Mesen is a `sleep` outside the caller's process group with a status
file beside a socket path, as Mesen writes one. Every test points the heavy
lock at a temporary directory; nothing touches /tmp/oos-heavy.lock.
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "Scripts" / "Agents" / "native_session.py"
spec = importlib.util.spec_from_file_location("native_session", SCRIPT)
ns = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = ns
spec.loader.exec_module(ns)
hl = ns.heavy_lock


FAKE_DIR = tempfile.TemporaryDirectory()
FAKE_MESEN = Path(FAKE_DIR.name) / "fake-mesen"  # a sleep whose name passes the Mesen check
shutil.copyfile(shutil.which("sleep"), FAKE_MESEN)
FAKE_MESEN.chmod(0o755)


def spawn_orphan(binary: Path | str = FAKE_MESEN) -> int:
    """A process whose parent exits at once, so init reaps it (like `open -n`)."""
    out = subprocess.run(["sh", "-c", f"'{binary}' 120 >/dev/null 2>&1 & echo $!"],
                         capture_output=True, text=True, check=True)
    return int(out.stdout.strip())


def alive(pid: int) -> bool:
    return hl.process_start(pid) is not None


def write_status(socket: Path, pid: int, socket_field: str | None = None) -> None:
    ns.status_path(socket).write_text(json.dumps(
        {"pid": pid, "socketPath": socket_field or str(socket)}), encoding="utf-8")


class NativeSessionTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        self.saved = (hl.LOCK, hl.ARCHIVE, hl.MODE_FILE, os.environ.pop(ns.REGISTRY_ENV, None))
        hl.LOCK = self.root / "oos-heavy.lock"
        hl.ARCHIVE = self.root / "reclaimed"
        hl.MODE_FILE = self.root / "build_mode"
        self.strays: list[int] = []

    def tearDown(self):
        for pid in self.strays:
            try:
                os.kill(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        hl.LOCK, hl.ARCHIVE, hl.MODE_FILE, registry = self.saved
        if registry is not None:
            os.environ[ns.REGISTRY_ENV] = registry
        self.tmp.cleanup()

    def fake_mesen(self, name: str) -> tuple[int, Path]:
        pid = spawn_orphan()
        self.strays.append(pid)
        socket = self.root / f"mesen2-{name}.sock"
        write_status(socket, pid)
        return pid, socket

    def session(self, **kwargs) -> ns.NativeSession:
        kwargs.setdefault("deadline", 60)
        kwargs.setdefault("term_wait", 2)
        return ns.NativeSession("Unit Test", "native_session test", self.root / "run", **kwargs)

    def log_text(self) -> str:
        return (self.root / "run" / "session.log").read_text(encoding="utf-8")

    def test_teardown_stops_registered_pid_and_releases_lock(self):
        since = time.time()
        pid, socket = self.fake_mesen("a")
        with self.session() as session:
            self.assertEqual(hl.status()["state"], "held")
            self.assertEqual(session.register(socket, since=since, timeout=5), pid)
        self.assertFalse(alive(pid))
        self.assertEqual(hl.status()["state"], "free")
        self.assertIn("teardown: stopped 1 pids, lock released", self.log_text())
        self.assertFalse(ns.status_path(socket).exists())

    def test_unregistered_and_reused_pids_are_not_stopped(self):
        stranger, _ = self.fake_mesen("stranger")
        reused, _ = self.fake_mesen("reused")
        with self.session() as session:
            session.registry.add({"pid": reused, "pid_start": "Mon Jan  1 00:00:00 2001"})
        self.assertTrue(alive(stranger))
        self.assertTrue(alive(reused))
        self.assertEqual(session.teardown_result["reused"], 1)
        self.assertIn("teardown: stopped 0 pids, lock released", self.log_text())

    def test_status_file_for_another_socket_older_or_non_mesen_process_is_refused(self):
        since = time.time()
        pid, socket = self.fake_mesen("mismatch")
        write_status(socket, pid, socket_field="/tmp/mesen2-someone-else.sock")
        older, older_socket = self.fake_mesen("older")
        stranger = spawn_orphan("sleep")
        self.strays.append(stranger)
        stranger_socket = self.root / "mesen2-stranger.sock"
        write_status(stranger_socket, stranger)
        with self.session() as session:
            with self.assertRaisesRegex(ns.LaunchError, "another socket"):
                session.register(socket, since=since, timeout=0.5)
            with self.assertRaisesRegex(ns.LaunchError, "before this launch"):
                session.register(older_socket, since=time.time() + 3600, timeout=0.5)
            with self.assertRaisesRegex(ns.LaunchError, "not a mesen process"):
                session.register(stranger_socket, since=since, timeout=0.5)
        for survivor in (pid, older, stranger):
            self.assertTrue(alive(survivor))
        self.assertEqual(session.registry.entries(), [])
        self.assertIn("pending launch still unidentified", self.log_text())

    def test_deadline_interrupts_and_tears_down(self):
        since = time.time()
        pid, socket = self.fake_mesen("deadline")
        with self.assertRaises(ns.SessionInterrupted) as caught:
            with self.session(deadline=0.5) as session:
                session.register(socket, since=since, timeout=5)
                time.sleep(10)
        self.assertEqual(caught.exception.exit_code, 124)
        self.assertFalse(alive(pid))
        self.assertEqual(hl.status()["state"], "free")
        self.assertIn("interrupted: deadline", self.log_text())

    def test_case_body_cannot_swallow_the_interrupt(self):
        cases = []
        with self.assertRaises(ns.SessionInterrupted):
            with self.session(deadline=0.3):
                for case in (1, 2, 3):
                    try:
                        cases.append(case)
                        time.sleep(5)
                    except Exception:
                        continue
        self.assertEqual(cases, [1])

    def test_cancelled_run_stops_the_command_and_owned_pids(self):
        case_script = self.root / "cases.py"
        marker = self.root / "cases.txt"
        case_script.write_text(textwrap.dedent(f"""
            import json, os, subprocess, sys, time
            from pathlib import Path
            for case in (1, 2, 3):
                with open({str(marker)!r}, "a") as out:
                    out.write(f"case {{case}} start\\n")
                since = time.time()
                fake = subprocess.Popen([{str(FAKE_MESEN)!r}, "120"], start_new_session=True,
                                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                socket = Path({str(self.root)!r}) / f"mesen2-case{{case}}.sock"
                socket.with_suffix(".status").write_text(
                    json.dumps({{"pid": fake.pid, "socketPath": str(socket)}}))
                subprocess.run([sys.executable, {str(SCRIPT)!r}, "register", "--registry",
                                os.environ[{ns.REGISTRY_ENV!r}], "--socket", str(socket),
                                "--since", str(since), "--timeout", "5"], check=True)
                time.sleep(60)
                with open({str(marker)!r}, "a") as out:
                    out.write(f"case {{case}} end\\n")
        """), encoding="utf-8")
        env = dict(os.environ, OOS_HEAVY_LOCK=str(hl.LOCK), OOS_HEAVY_LOCK_ARCHIVE=str(hl.ARCHIVE),
                   OOS_BUILD_MODE_FILE=str(hl.MODE_FILE))
        run_dir = self.root / "run"
        wrapper = subprocess.Popen(
            [sys.executable, str(SCRIPT), "run", "--owner", "Unit Test", "--purpose", "cancel demo",
             "--run-dir", str(run_dir), "--deadline", "120", "--", sys.executable, str(case_script)],
            env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        registry = run_dir / "owned_pids.jsonl"
        end = time.monotonic() + 20
        while time.monotonic() < end and not registry.exists():
            time.sleep(0.1)
        entries = ns.Registry(registry).entries()
        self.assertEqual(len(entries), 1)
        owned = entries[0]["pid"]
        self.strays.append(owned)
        self.assertTrue(alive(owned))
        self.assertEqual(hl.status()["state"], "held")

        wrapper.send_signal(signal.SIGTERM)
        self.assertEqual(wrapper.wait(timeout=40), 128 + signal.SIGTERM)
        self.assertFalse(alive(owned))
        self.assertEqual(hl.status()["state"], "free")
        self.assertEqual(marker.read_text(encoding="utf-8"), "case 1 start\n")
        log = (run_dir / "session.log").read_text(encoding="utf-8")
        self.assertIn("interrupted: signal SIGTERM", log)
        self.assertIn("teardown: stopped 1 pids, lock released", log)

    def test_mesen_that_comes_up_after_a_failed_register_is_stopped(self):
        since = time.time()
        socket = self.root / "mesen2-late.sock"
        with self.session() as session:
            with self.assertRaises(ns.LaunchError):
                session.register(socket, since=since, timeout=0.3)
            self.assertEqual(len(session.registry.pending()), 1)
            pid = spawn_orphan()
            self.strays.append(pid)
            write_status(socket, pid)
        self.assertFalse(alive(pid))
        self.assertIn(f"late registration: pid {pid}", self.log_text())
        self.assertIn("teardown: stopped 1 pids, lock released", self.log_text())

    def test_teardown_command_cleans_up_after_a_killed_wrapper(self):
        since = time.time()
        pid, socket = self.fake_mesen("killed")
        registry = self.root / "owned.jsonl"
        ns.register(ns.Registry(registry), socket, since, 5, "killed-run")
        self.assertEqual(ns.main(["teardown", "--registry", str(registry)]), 0)
        self.assertFalse(alive(pid))


if __name__ == "__main__":
    unittest.main()
