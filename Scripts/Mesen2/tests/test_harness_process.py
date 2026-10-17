"""Offline ownership/cancellation checks; no subprocess or emulator is launched."""
import errno
from pathlib import Path
import signal
import struct
import unittest
from unittest.mock import patch

from Scripts.Mesen2.harness.process import (
    CleanupUnconfirmed, MacProcessBackend, OwnedProcessCleanup, owns_process,
    parse_procargs2,
)


BINARY = Path("/private/test/Mesen 2.app/Contents/MacOS/Mesen")
ROM = Path("/private/test/new run/game.sfc")
SOURCE_ROM = Path("/private/test/source run/game.sfc")


class FakeBackend:
    def __init__(self):
        self.now = 0.0
        self.processes = {}
        self.signals = []
        self.on_sleep = lambda: None
        self.on_terminate = lambda pid: self.processes.pop(pid)

    def add(self, pid, *, binary=BINARY, rom=ROM):
        self.processes[pid] = [binary, (str(binary), str(rom))]

    def pids(self):
        return list(self.processes)

    def executable(self, pid):
        return self.processes.get(pid, [None])[0]

    def arguments(self, pid):
        return self.processes[pid][1]

    def exists(self, pid):
        return pid in self.processes

    def terminate(self, pid):
        self.signals.append(pid)
        self.on_terminate(pid)

    def monotonic(self):
        return self.now

    def sleep(self, seconds):
        self.now += seconds
        self.on_sleep()


class OwnedProcessTest(unittest.TestCase):
    def setUp(self):
        self.backend = FakeBackend()
        self.cleanup = OwnedProcessCleanup(BINARY, ROM, backend=self.backend)

    def test_procargs_boundaries_exclude_environment(self):
        data = (struct.pack("=i", 3) + b"/bin/Mesen\0\0" + b"Mesen\0\0" +
                str(ROM).encode() + b"\0SECRET=value\0")
        self.assertEqual(parse_procargs2(data), ("Mesen", "", str(ROM)))
        for malformed in (b"", struct.pack("=i", 0), struct.pack("=i", 4097),
                          struct.pack("=i", 1) + b"no terminator",
                          struct.pack("=i", 2) + b"/bin/Mesen\0Mesen\0"):
            with self.subTest(data=malformed), self.assertRaises(ValueError):
                parse_procargs2(malformed)

    def test_exact_binary_and_complete_rom_argument_required(self):
        self.backend.add(20)
        self.assertTrue(owns_process(20, BINARY, ROM, self.backend))
        for binary, arguments in (
                (Path(str(BINARY) + "-other"), (str(BINARY), str(ROM))),
                (None, (str(BINARY), str(ROM))),
                (BINARY, (str(BINARY), str(SOURCE_ROM))),
                (BINARY, (str(BINARY), str(ROM) + ".old")),
                (BINARY, (str(BINARY), "--rom=" + str(ROM))),
                (BINARY, (str(ROM),))):
            with self.subTest(binary=binary, arguments=arguments):
                self.backend.processes[20] = [binary, arguments]
                self.assertFalse(owns_process(20, BINARY, ROM, self.backend))

    def test_executable_is_rechecked_after_argv(self):
        self.backend.add(20)
        def replaced(pid):
            self.backend.processes[pid][0] = Path("/bin/unrelated")
            return (str(BINARY), str(ROM))
        self.backend.arguments = replaced
        self.assertFalse(owns_process(20, BINARY, ROM, self.backend))
        with self.assertRaises(CleanupUnconfirmed):
            self.cleanup.cancel(pid=20)
        self.assertEqual(self.backend.signals, [])

    def test_delayed_discovery_stops_only_new_private_run(self):
        self.backend.add(10, rom=SOURCE_ROM)
        self.backend.add(11, binary=Path("/bin/unrelated"))
        self.backend.on_sleep = lambda: self.backend.add(20) if self.backend.now >= .2 else None
        result = self.cleanup.cancel(discovery_timeout=1, poll_interval=.1)
        self.assertEqual(result.checked_pids, (20,))
        self.assertEqual(result.stopped_owned_pids, (20,))
        self.assertTrue(result.pid_exit_confirmed)
        self.assertEqual(self.backend.signals, [20])
        self.assertEqual(set(self.backend.processes), {10, 11})

    def test_repeated_cancel_does_not_signal_reused_pid(self):
        self.backend.add(20)
        first = self.cleanup.cancel(pid=20)
        self.backend.add(20, rom=SOURCE_ROM)
        self.assertIs(self.cleanup.cancel(pid=20), first)
        self.assertEqual(self.backend.signals, [20])
        self.assertIn(20, self.backend.processes)

    def test_known_absent_pid_is_confirmed_without_signal(self):
        result = self.cleanup.cancel(pid=20)
        self.assertEqual(result.checked_pids, (20,))
        self.assertEqual(result.stopped_owned_pids, ())
        self.assertTrue(result.pid_exit_confirmed)

    def test_waits_for_positive_exit_after_sigterm(self):
        self.backend.add(20)
        self.backend.on_terminate = lambda pid: None
        self.backend.on_sleep = lambda: self.backend.processes.pop(20, None) if self.backend.now >= .3 else None
        self.cleanup.cancel(pid=20, poll_interval=.1)
        self.assertGreaterEqual(self.backend.now, .3)
        self.assertEqual(self.backend.signals, [20])
        self.assertFalse(self.backend.exists(20))

    def test_live_identity_loss_is_not_exit_and_never_resignals(self):
        self.backend.add(20)
        self.backend.on_terminate = lambda pid: self.backend.processes[pid].__setitem__(0, None)
        for _ in range(2):
            with self.assertRaisesRegex(CleanupUnconfirmed, "live but ownership"):
                self.cleanup.cancel(pid=20)
        self.assertEqual(self.backend.signals, [20])
        self.assertTrue(self.backend.exists(20))

    def test_unknown_argv_and_source_pid_refuse_termination(self):
        self.backend.add(20, rom=SOURCE_ROM)
        with self.assertRaises(CleanupUnconfirmed):
            self.cleanup.cancel(pid=20)
        self.backend.add(20)
        with patch.object(self.backend, "arguments", side_effect=PermissionError):
            with self.assertRaises(CleanupUnconfirmed):
                self.cleanup.cancel(pid=20)
        self.assertEqual(self.backend.signals, [])

    def test_exit_and_discovery_timeouts_are_not_success(self):
        with self.assertRaisesRegex(CleanupUnconfirmed, "No owned launch PID"):
            self.cleanup.cancel(discovery_timeout=.2, poll_interval=.1)
        self.backend.add(20)
        self.backend.on_terminate = lambda pid: None
        for _ in range(2):
            with self.assertRaisesRegex(CleanupUnconfirmed, "did not exit"):
                self.cleanup.cancel(pid=20, exit_timeout=.2, poll_interval=.1)
        self.assertEqual(self.backend.signals, [20])

    def test_observation_error_and_exit_race_require_positive_absence(self):
        self.backend.add(20)
        with patch.object(self.backend, "exists", side_effect=PermissionError):
            with self.assertRaises(CleanupUnconfirmed):
                self.cleanup.cancel(pid=20)
        self.assertEqual(self.backend.signals, [])
        def vanished(pid):
            self.backend.processes.pop(pid)
            raise ProcessLookupError(errno.ESRCH, "exited")
        self.backend.on_terminate = vanished
        result = self.cleanup.cancel(pid=20)
        self.assertTrue(result.pid_exit_confirmed)
        self.assertEqual(result.stopped_owned_pids, ())

    def test_native_backend_signals_only_positive_pid_and_esrch_means_exit(self):
        backend = MacProcessBackend()
        with patch("Scripts.Mesen2.harness.process.os.kill") as kill:
            backend.terminate(20)
            kill.assert_called_once_with(20, signal.SIGTERM)
            kill.reset_mock()
            self.assertTrue(backend.exists(20))
            kill.assert_called_once_with(20, 0)
            for pid in (0, -1, True, "20", 0x80000000):
                with self.subTest(pid=pid), self.assertRaises(ValueError):
                    self.cleanup.cancel(pid=pid)
                with self.assertRaises(ValueError):
                    backend.terminate(pid)
            kill.side_effect = ProcessLookupError(errno.ESRCH, "absent")
            self.assertFalse(backend.exists(20))
            kill.side_effect = PermissionError(errno.EPERM, "unknown")
            with self.assertRaises(PermissionError):
                backend.exists(20)


if __name__ == "__main__":
    unittest.main()
