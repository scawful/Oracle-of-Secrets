#!/usr/bin/env python3
"""Focused Android report tests; no real device or emulator socket is opened."""
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch


DEVICE_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(DEVICE_DIR))
SPEC = importlib.util.spec_from_file_location("android_report_test_subject", DEVICE_DIR / "oos_android_report.py")
report = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(report)


def system_stat(ticks, count=4):
    return "cpu  " + " ".join(map(str, ticks)) + "\n" + "".join(
        f"cpu{i} 0 0 0 0 0 0 0 0\n" for i in range(count))


def process_stat(pid=42, comm="Mesen (main) worker)", user=15, system=5, start=100, threads=8):
    fields = [0] * 21  # fields 4..24
    fields[10], fields[11], fields[16], fields[18] = user, system, threads, start
    return f"{pid} ({comm}) S " + " ".join(map(str, fields))


FIRST_SYSTEM = [100, 0, 100, 800, 0, 0, 0, 0, 10, 0]
LAST_SYSTEM = [200, 0, 150, 1050, 0, 0, 0, 0, 20, 0]


def endpoint(ticks, process=None, cores=4):
    return {"system": {"status": "ok", "data": report.parse_system_stat(system_stat(ticks, cores))},
            "process": {"status": "ok", "data": {"running": True, **report.parse_process_stat(process or process_stat())}}}


class FakeDevice:
    serial = "test-rg353p"

    def __init__(self, closed=False, failures=(), restart=False):
        self.closed = closed
        self.failures = set(failures)
        self.restart = restart
        self.calls = []
        self.system_reads = 0
        self.process_reads = 0

    def shell(self, *args):
        self.calls.append(args)
        if args in self.failures:
            raise RuntimeError("permission denied\nprivate diagnostic text must not be retained")
        responses = {
            ("getprop",): b"[ro.product.model]: [RG353P]\n[ro.build.version.release]: [11]\n[ro.build.version.sdk]: [30]\n[ro.product.cpu.abi]: [arm64-v8a]\n[ro.build.display.id]: [test-build]\n[private.value]: [secret]\n",
            ("wm", "size"): b"Physical size: 640x480\n",
            ("wm", "density"): b"Physical density: 160\nOverride density: 180\n",
            ("dumpsys", "package", report.PACKAGE): b"versionCode=7 minSdk=26 targetSdk=30\nversionName=0.7\nfirstInstallTime=2026-09-01 01:02:03\nlastUpdateTime=2026-09-15 02:03:04\notherSecret=hidden\n",
            ("pm", "path", report.PACKAGE): b"package:/data/app/mesen/base.apk\n",
            ("cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"): b"priority=0\ncom.launcher/.Home\n",
            ("dumpsys", "activity", "activities"): b"unrelated full activity dump secret=hidden\n  mResumedActivity: ActivityRecord{abc u0 ca.mesen.oos/.MesenActivity t12} intent=private-url\n",
            ("settings", "get", "global", "low_power"): b"0\n",
        }
        if args == ("ps", "-A", "-o", "PID,NAME"):
            return b"PID NAME\n77 private.app\n" + (b"" if self.closed else b"42 ca.mesen.oos\n")
        if args in responses:
            return responses[args]
        raise AssertionError("Unexpected device command: " + repr(args))

    def hash(self, path):
        self.calls.append(("sha256sum", path))
        if path != "/data/app/mesen/base.apk":
            raise AssertionError(path)
        return "a" * 64

    def read(self, path):
        self.calls.append(("cat", path))
        if ("cat", path) in self.failures:
            raise RuntimeError("permission denied")
        if path == "/proc/meminfo":
            return b"MemTotal: 2048000 kB\nMemAvailable: 1024000 kB\nMemFree: 500000 kB\nSwapTotal: 0 kB\nSwapFree: 0 kB\n"
        if path == "/proc/stat":
            value = FIRST_SYSTEM if self.system_reads == 0 else LAST_SYSTEM
            self.system_reads += 1
            return system_stat(value).encode()
        if path == "/proc/42/stat":
            last = self.process_reads > 0
            self.process_reads += 1
            return process_stat(user=100 if last else 15, system=20 if last else 5,
                                start=200 if last and self.restart else 100).encode()
        raise AssertionError("Unexpected device file: " + path)


class AndroidReportTests(unittest.TestCase):
    def setUp(self):
        # A regression cannot accidentally reach adb or any real socket.
        self.guards = [patch.object(subprocess, "run", side_effect=AssertionError("Real subprocess forbidden")),
                       patch.object(socket, "socket", side_effect=AssertionError("Real socket forbidden"))]
        for guard in self.guards:
            guard.start()
            self.addCleanup(guard.stop)

    def collect(self, device=None):
        clock = iter([100.0, 100.05, 105.05, 105.30])
        return report.collect(device or FakeDevice(), 5, sleep=lambda _: None, monotonic=lambda: next(clock))

    def test_process_stat_handles_spaces_and_parentheses(self):
        parsed = report.parse_process_stat(process_stat())
        self.assertEqual(parsed["comm"], "Mesen (main) worker)")
        self.assertEqual((parsed["pid"], parsed["utime_ticks"], parsed["stime_ticks"], parsed["starttime_ticks"], parsed["threads"]),
                         (42, 15, 5, 100, 8))

    def test_truncated_process_stat_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "Truncated"):
            report.parse_process_stat("42 (name with spaces) S 0 0")

    def test_system_total_excludes_double_counted_guest_time(self):
        parsed = report.parse_system_stat(system_stat(FIRST_SYSTEM))
        self.assertEqual(parsed["total_ticks"], 1000)
        self.assertEqual(parsed["cpu_count"], 4)

    def test_cpu_percentages_use_named_denominators(self):
        before = endpoint(FIRST_SYSTEM)
        after = endpoint(LAST_SYSTEM, process_stat(user=100, system=20))
        delta = report.cpu_delta(before, after)
        self.assertEqual(delta["system_cpu"]["busy_percent"], 37.5)
        self.assertEqual(delta["app_cpu"]["process_delta_ticks"], 100)
        self.assertEqual(delta["app_cpu"]["total_delta_ticks"], 400)
        self.assertEqual(delta["app_cpu"]["total_capacity_percent"], 25)
        self.assertEqual(delta["app_cpu"]["one_core_equivalent_percent"], 100)

    def test_iowait_is_distinct_from_busy_time(self):
        last = LAST_SYSTEM.copy()
        last[3] -= 40
        last[4] += 40
        delta = report.cpu_delta(endpoint(FIRST_SYSTEM), endpoint(last))
        self.assertEqual(delta["system_cpu"]["busy_percent"], 37.5)
        self.assertEqual(delta["system_cpu"]["iowait_percent"], 10)

    def test_restart_invalidates_app_cpu(self):
        for changed in (process_stat(pid=99), process_stat(start=999)):
            with self.subTest(changed=changed):
                delta = report.cpu_delta(endpoint(FIRST_SYSTEM), endpoint(LAST_SYSTEM, changed))
                self.assertEqual(delta["app_cpu"]["status"], "unavailable")
                self.assertIn("restarted", delta["app_cpu"]["reason"])
                self.assertNotIn("total_capacity_percent", delta["app_cpu"])

    def test_cpu_hotplug_invalidates_normalization(self):
        delta = report.cpu_delta(endpoint(FIRST_SYSTEM), endpoint(LAST_SYSTEM, cores=3))
        self.assertEqual(delta["system_cpu"]["status"], "ok")
        self.assertIn("CPU set changed", delta["app_cpu"]["reason"])

    def test_impossible_app_delta_is_rejected_not_clamped(self):
        delta = report.cpu_delta(endpoint(FIRST_SYSTEM), endpoint(LAST_SYSTEM, process_stat(user=500)))
        self.assertEqual(delta["app_cpu"]["status"], "unavailable")
        self.assertIn("exceeds total", delta["app_cpu"]["reason"])
        self.assertNotIn("total_capacity_percent", delta["app_cpu"])

    def test_slow_snapshot_invalidates_app_cpu_but_keeps_system_counters(self):
        clock = iter([100.0, 100.1, 105.1, 106.1])
        result = report.collect(FakeDevice(), 5, sleep=lambda _: None, monotonic=lambda: next(clock))
        sample = result["cpu_sample"]
        self.assertFalse(sample["read_span_within_bound"])
        self.assertEqual(sample["after"]["read_span_seconds"], 1)
        self.assertEqual(sample["max_allowed_read_span_seconds"], 0.5)
        self.assertEqual(sample["system_cpu"]["status"], "ok")
        self.assertEqual(sample["app_cpu"]["status"], "unavailable")
        self.assertNotIn("total_capacity_percent", sample["app_cpu"])

    def test_unrelated_properties_do_not_claim_device_identity(self):
        with self.assertRaisesRegex(ValueError, "Selected Android identity"):
            report.parse_properties("[vendor.unrelated]: [value]\n")

    def test_counter_reset_or_no_progress_is_unavailable(self):
        for last in (FIRST_SYSTEM, [0] * 10):
            with self.subTest(last=last):
                delta = report.cpu_delta(endpoint(FIRST_SYSTEM), endpoint(last))
                self.assertEqual(delta["system_cpu"]["status"], "unavailable")
                self.assertEqual(delta["app_cpu"]["status"], "unavailable")

    def test_closed_app_is_not_zero_percent_success(self):
        result = self.collect(FakeDevice(closed=True))
        self.assertEqual(result["status"], "partial")
        sample = result["cpu_sample"]
        self.assertEqual(sample["system_cpu"]["status"], "ok")
        self.assertFalse(sample["before"]["process"]["data"]["running"])
        self.assertEqual(sample["app_cpu"]["status"], "unavailable")
        self.assertNotIn("total_capacity_percent", sample["app_cpu"])
        self.assertIn("Mesen CPU: unavailable", report.summary(result))

    def test_optional_failure_does_not_discard_the_report(self):
        result = self.collect(FakeDevice(failures=[("wm", "density")]))
        self.assertEqual(result["status"], "partial")
        self.assertEqual(result["display_density"], {"status": "unavailable", "reason": "permission denied"})
        self.assertEqual(result["cpu_sample"]["app_cpu"]["status"], "ok")
        self.assertEqual(result["device"]["data"]["model"], "RG353P")

    def test_missing_system_counters_is_unavailable(self):
        result = self.collect(FakeDevice(failures=[("cat", "/proc/stat")]))
        self.assertEqual(result["cpu_sample"]["system_cpu"]["status"], "unavailable")
        self.assertEqual(result["cpu_sample"]["app_cpu"]["status"], "unavailable")

    def test_private_dumps_are_filtered_and_installed_apk_is_identified(self):
        result = self.collect()
        serialized = json.dumps(result)
        for private in ("secret", "private-url", "otherSecret", "private.app"):
            self.assertNotIn(private, serialized)
        self.assertEqual(result["foreground_activity"]["data"], ["mResumedActivity: ca.mesen.oos/.MesenActivity"])
        self.assertEqual(result["resolved_home"]["data"], "com.launcher/.Home")
        self.assertEqual(result["installed_apks"]["data"]["apks"][0]["sha256"], "a" * 64)
        self.assertEqual(result["package_version"]["data"]["lastUpdateTime"], "2026-09-15 02:03:04")

    def test_full_snapshot_only_uses_read_commands(self):
        device = FakeDevice()
        result = self.collect(device)
        self.assertEqual(result["status"], "ok")
        self.assertAlmostEqual(result["cpu_sample"]["elapsed_seconds"], 5.25)
        self.assertTrue(result["cpu_sample"]["read_span_within_bound"])
        self.assertTrue(all(call[0] in ("getprop", "wm", "dumpsys", "pm", "cmd", "settings", "ps", "cat", "sha256sum")
                            for call in device.calls))
        self.assertEqual([call for call in device.calls if call[0] == "settings"], [("settings", "get", "global", "low_power")])
        self.assertNotIn("adb", serialized := json.dumps(device.calls))
        self.assertNotIn("forward", serialized)

    def test_main_writes_unique_reports_and_honors_serial(self):
        result = self.collect()
        with tempfile.TemporaryDirectory(prefix="oos-android-report-test-") as temp:
            output = Path(temp)
            with patch.object(report, "Device", return_value=FakeDevice()) as factory, \
                    patch.object(report, "collect", side_effect=lambda *args: dict(result)), \
                    contextlib.redirect_stdout(io.StringIO()):
                for _ in range(2):
                    self.assertEqual(report.main(["--seconds", "1", "--serial", "chosen", "--out", temp]), 0)
                factory.assert_called_with("chosen")
            folders = list(output.iterdir())
            self.assertEqual(len(folders), 2)
            for folder in folders:
                self.assertEqual(json.loads((folder / "report.json").read_text())["kind"], "android-report")
                self.assertIn("CPU sample", (folder / "summary.txt").read_text())

    def test_duration_rejected_before_device_access(self):
        with patch.object(report, "Device") as factory, contextlib.redirect_stderr(io.StringIO()):
            for value in ("0", "31", "1.5", "bad"):
                with self.subTest(value=value), self.assertRaises(SystemExit):
                    report.main(["--seconds", value])
            factory.assert_not_called()


class AndroidShellDelegationTests(unittest.TestCase):
    def test_shell_passes_serial_duration_and_output_before_device_detection(self):
        with tempfile.TemporaryDirectory(prefix="oos-android-shell-test-") as temp:
            root = Path(temp)
            device_dir = root / "project/Scripts/Device"
            device_dir.mkdir(parents=True)
            shell = device_dir / "oos_rg353p.sh"
            shutil.copyfile(DEVICE_DIR / shell.name, shell)
            (device_dir / "oos_android_report.py").write_text("import json,sys; print(json.dumps(sys.argv[1:]))\n")
            fake_bin = root / "bin"
            fake_bin.mkdir()
            called = root / "adb-was-called"
            adb = fake_bin / "adb"
            adb.write_text("#!/bin/sh\ntouch '" + str(called) + "'\nexit 99\n")
            adb.chmod(0o755)
            environment = dict(os.environ, PATH=str(fake_bin) + os.pathsep + os.environ.get("PATH", ""))
            args = ["--seconds", "5", "--serial", "chosen", "--out", str(root / "reports")]
            result = subprocess.run(["/bin/bash", str(shell), "android-report", *args], env=environment,
                                    capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), args)
            self.assertFalse(called.exists())

    def test_real_report_help_requires_no_device(self):
        with tempfile.TemporaryDirectory(prefix="oos-android-help-test-") as temp:
            root = Path(temp)
            adb = root / "adb"
            called = root / "called"
            adb.write_text("#!/bin/sh\ntouch '" + str(called) + "'\nexit 99\n")
            adb.chmod(0o755)
            environment = dict(os.environ, PATH=str(root) + os.pathsep + os.environ.get("PATH", ""))
            result = subprocess.run(["/bin/bash", str(DEVICE_DIR / "oos_rg353p.sh"), "android-report", "--help"],
                                    env=environment, capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("--seconds", result.stdout)
            self.assertFalse(called.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
