#!/usr/bin/env python3
"""Read-only Android identity and CPU snapshot; no emulator socket or controls.

Every device command uses oos_handheld.Device's pinned serial and 15s timeout.
Only selected metadata is retained from Android service/process output.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
import time

from oos_handheld import Device, PACKAGE, ROOT, emulator_fingerprint, new_bundle, now


PROPERTIES = {
    "model": "ro.product.model",
    "manufacturer": "ro.product.manufacturer",
    "android": "ro.build.version.release",
    "api": "ro.build.version.sdk",
    "abi": "ro.product.cpu.abi",
    "abis": "ro.product.cpu.abilist",
    "build": "ro.build.display.id",
    "build_type": "ro.build.type",
    "build_fingerprint": "ro.build.fingerprint",
}
MEMORY_KEYS = ("MemTotal", "MemAvailable", "MemFree", "Buffers", "Cached",
               "SwapTotal", "SwapFree")
COMPONENT = re.compile(r"[A-Za-z0-9_.]+/[A-Za-z0-9_.$]+")


def optional(function):
    try:
        return {"status": "ok", "data": function()}
    except Exception as exc:
        # Do not retain potentially lengthy service dumps in error output.
        first_line = str(exc).splitlines()[0] if str(exc) else type(exc).__name__
        return {"status": "unavailable", "reason": first_line[:240]}


def text(data):
    return data.decode(errors="replace").strip()


def parse_properties(raw):
    values = dict(re.findall(r"^\[([^\]]+)\]: \[(.*)\]$", raw, re.MULTILINE))
    selected = {name: values.get(key) or None for name, key in PROPERTIES.items()}
    if not any(selected.values()):
        raise ValueError("Selected Android identity properties unavailable")
    return selected


def parse_display(raw):
    lines = [line.strip() for line in raw.splitlines()
             if re.fullmatch(r"\s*(Physical|Override) (size|density): [0-9]+(?:x[0-9]+)?\s*", line)]
    if not lines:
        raise ValueError("Display measurement unavailable")
    return lines


def parse_package(raw):
    result = {}
    for key in ("versionCode", "versionName", "firstInstallTime", "lastUpdateTime"):
        match = re.search(r"^\s*" + key + r"=([^\r\n]+)", raw, re.MULTILINE)
        result[key] = match.group(1).strip() if match else None
    if not result["versionCode"] and not result["versionName"]:
        raise ValueError("Installed Mesen version unavailable")
    return result


def parse_home(raw):
    components = [line.strip() for line in raw.splitlines() if COMPONENT.fullmatch(line.strip())]
    if not components:
        raise ValueError("Resolved HOME activity unavailable")
    return components[-1]


def parse_foreground(raw):
    result = []
    for line in raw.splitlines():
        field = re.search(r"\b(mResumedActivity|topResumedActivity|mFocusedActivity)\s*[:=]", line)
        component = COMPONENT.search(line[field.end():]) if field else None
        if component:
            # Keep the activity identity, excluding intents, URLs and other dumps.
            value = f"{field.group(1)}: {component.group(0)}"
            if value not in result:
                result.append(value)
    if not result:
        raise ValueError("Foreground activity not reported")
    return result


def parse_meminfo(raw):
    values = {key: int(value) for key, value in
              re.findall(r"^(\w+):\s+(\d+)\s+kB\s*$", raw, re.MULTILINE)}
    if "MemTotal" not in values:
        raise ValueError("MemTotal unavailable")
    return {"unit": "KiB", **{key: values.get(key) for key in MEMORY_KEYS}}


def parse_low_power(raw):
    if raw not in ("0", "1"):
        raise ValueError("low_power setting unavailable")
    return {"enabled": raw == "1", "raw": raw}


def parse_system_stat(raw):
    aggregate = next((line.split()[1:] for line in raw.splitlines() if line.startswith("cpu ")), None)
    if aggregate is None or len(aggregate) < 4:
        raise ValueError("Aggregate /proc/stat CPU counters unavailable")
    counters = [int(value) for value in aggregate]
    if any(value < 0 for value in counters):
        raise ValueError("Negative system CPU counter")
    counters += [0] * max(0, 8 - len(counters))
    # guest and guest_nice (fields 9/10) already contribute to user/nice.
    total = sum(counters[:8])
    cpus = sorted(set(re.findall(r"^(cpu\d+)\s", raw, re.MULTILINE)))
    return {"ticks": counters[:8], "total_ticks": total,
            "idle_ticks": counters[3], "iowait_ticks": counters[4],
            "cpu_ids": cpus, "cpu_count": len(cpus)}


def parse_process_stat(raw):
    # comm may contain spaces and parentheses; fields begin after the LAST ')'.
    match = re.fullmatch(r"(\d+)\s+\((.*)\)\s+(\S)\s+(.*)", raw.strip(), re.DOTALL)
    if not match:
        raise ValueError("Malformed /proc/PID/stat")
    fields = match.group(4).split()  # starts with field 4, ppid
    if len(fields) < 19:
        raise ValueError("Truncated /proc/PID/stat")
    values = {"pid": int(match.group(1)), "comm": match.group(2), "state": match.group(3),
              "utime_ticks": int(fields[10]), "stime_ticks": int(fields[11]),
              "threads": int(fields[16]), "starttime_ticks": int(fields[18])}
    if any(values[key] < 0 for key in ("utime_ticks", "stime_ticks", "threads", "starttime_ticks")):
        raise ValueError("Negative process counter")
    values["cpu_ticks"] = values["utime_ticks"] + values["stime_ticks"]
    return values


def process_snapshot(device):
    listing = text(device.shell("ps", "-A", "-o", "PID,NAME"))
    if not listing or not re.search(r"\bPID\b", listing.splitlines()[0]):
        raise ValueError("Process list unavailable")
    pids = [int(parts[0]) for line in listing.splitlines()[1:]
            if len(parts := line.split()) == 2 and parts[0].isdigit() and parts[1] == PACKAGE]
    if not pids:
        return {"running": False, "reason": "Mesen main process is not running"}
    if len(pids) != 1:
        raise ValueError("Multiple Mesen main processes; CPU target is ambiguous")
    result = parse_process_stat(text(device.read(f"/proc/{pids[0]}/stat")))
    if result["pid"] != pids[0]:
        raise ValueError("Process changed while reading its counters")
    return {"running": True, **result}


def cpu_snapshot(device):
    return {"observed_at": now(),
            "system": optional(lambda: parse_system_stat(text(device.read("/proc/stat")))),
            "process": optional(lambda: process_snapshot(device))}


def cpu_delta(before, after):
    unavailable = lambda reason: {"status": "unavailable", "reason": reason}
    result = {"system_cpu": unavailable("System counters unavailable"),
              "app_cpu": unavailable("Process counters unavailable")}
    if before["system"]["status"] != "ok" or after["system"]["status"] != "ok":
        return result
    first, last = before["system"]["data"], after["system"]["data"]
    delta = last["total_ticks"] - first["total_ticks"]
    idle = last["idle_ticks"] - first["idle_ticks"]
    wait = last["iowait_ticks"] - first["iowait_ticks"]
    if delta <= 0 or any(b < a for a, b in zip(first["ticks"], last["ticks"])):
        result["system_cpu"] = unavailable("System counters did not advance consistently")
        result["app_cpu"] = unavailable("System CPU denominator is invalid")
        return result
    result["system_cpu"] = {"status": "ok", "busy_percent": 100 * (delta - idle - wait) / delta,
                            "iowait_percent": 100 * wait / delta, "total_delta_ticks": delta,
                            "denominator": "All logical CPUs; idle and iowait excluded from busy time"}
    if before["process"]["status"] != "ok" or after["process"]["status"] != "ok":
        return result
    process_first, process_last = before["process"]["data"], after["process"]["data"]
    if not process_first["running"] or not process_last["running"]:
        result["app_cpu"] = unavailable("Mesen was not running at both sample endpoints")
        return result
    if (process_first["pid"], process_first["starttime_ticks"]) != (process_last["pid"], process_last["starttime_ticks"]):
        result["app_cpu"] = unavailable("Mesen restarted or its PID changed during the sample")
        return result
    if not first["cpu_count"] or first["cpu_ids"] != last["cpu_ids"]:
        result["app_cpu"] = unavailable("Logical CPU set changed or is unavailable; normalization is invalid")
        return result
    ticks = process_last["cpu_ticks"] - process_first["cpu_ticks"]
    if ticks < 0 or any(process_last[key] < process_first[key] for key in ("utime_ticks", "stime_ticks")):
        result["app_cpu"] = unavailable("Process CPU counters decreased")
        return result
    if ticks > delta:
        result["app_cpu"] = unavailable("Process CPU delta exceeds total CPU delta; sample intervals are inconsistent")
        return result
    capacity = 100 * ticks / delta
    result["app_cpu"] = {"status": "ok", "pid": process_last["pid"],
                         "starttime_ticks": process_last["starttime_ticks"],
                         "process_delta_ticks": ticks, "total_delta_ticks": delta,
                         "cpu_count": first["cpu_count"], "total_capacity_percent": capacity,
                         "one_core_equivalent_percent": capacity * first["cpu_count"],
                         "threads_before": process_first["threads"], "threads_after": process_last["threads"],
                         "denominator": "utime+stime / aggregate CPU ticks; one-core equivalent multiplies by logical CPU count"}
    return result


def sample_cpu(device, seconds, sleep=None, monotonic=None):
    sleep = sleep or time.sleep
    monotonic = monotonic or time.monotonic
    before_start = monotonic()
    before = cpu_snapshot(device)
    before_end = monotonic()
    sleep(seconds)
    after_start = monotonic()
    after = cpu_snapshot(device)
    after_end = monotonic()
    elapsed = after_end - before_end
    before["read_span_seconds"] = before_end - before_start
    after["read_span_seconds"] = after_end - after_start
    allowed_span = seconds * 0.1
    span_ok = all(0 <= snapshot["read_span_seconds"] <= allowed_span for snapshot in (before, after))
    usage = cpu_delta(before, after)
    if not span_ok and usage["app_cpu"]["status"] == "ok":
        usage["app_cpu"] = {"status": "unavailable", "reason": "Counter read span exceeds 10% of the requested interval; process/system sampling skew is too large"}
    return {"requested_seconds": seconds, "elapsed_seconds": elapsed,
            "timing": "Host interval includes the second counter read; device reads are sequential, not atomic",
            "before": before, "after": after,
            "max_allowed_read_span_seconds": allowed_span, "read_span_within_bound": span_ok, **usage}


def collect(device, seconds=5, sleep=None, monotonic=None):
    report = {"kind": "android-report", "observed_at": now(), "serial": device.serial,
              "package": PACKAGE, "scope": "Read-only Android metadata and CPU counters; no game controls or emulator socket calls",
              "limitations": "CPU usage is not emulator FPS, audio quality, thermal throttling, or controller acceptance"}
    probes = {
        "device": lambda: parse_properties(text(device.shell("getprop"))),
        "display_size": lambda: parse_display(text(device.shell("wm", "size"))),
        "display_density": lambda: parse_display(text(device.shell("wm", "density"))),
        "package_version": lambda: parse_package(text(device.shell("dumpsys", "package", PACKAGE))),
        "installed_apks": lambda: emulator_fingerprint(device),
        "resolved_home": lambda: parse_home(text(device.shell("cmd", "package", "resolve-activity", "--brief", "-a", "android.intent.action.MAIN", "-c", "android.intent.category.HOME"))),
        "foreground_activity": lambda: parse_foreground(text(device.shell("dumpsys", "activity", "activities"))),
        "memory": lambda: parse_meminfo(text(device.read("/proc/meminfo"))),
        "low_power": lambda: parse_low_power(text(device.shell("settings", "get", "global", "low_power"))),
    }
    report.update({key: optional(probe) for key, probe in probes.items()})
    report["cpu_sample"] = sample_cpu(device, seconds, sleep, monotonic)
    outcomes = [report[key] for key in probes] + [report["cpu_sample"][key] for key in ("system_cpu", "app_cpu")]
    report["status"] = "ok" if all(outcome["status"] == "ok" for outcome in outcomes) else "partial"
    return report


def summary(report):
    device = report["device"].get("data", {})
    lines = [f"Android report: {report['status']} ({report['serial']})",
             f"Device: {device.get('model') or 'unavailable'}; Android {device.get('android') or '?'}; API {device.get('api') or '?'}; ABI {device.get('abi') or '?'}",
             f"Build: {device.get('build') or 'unavailable'}"]
    for key, label in (("display_size", "Display"), ("display_density", "Density"),
                       ("package_version", "Mesen version"), ("installed_apks", "Installed APK fingerprints"),
                       ("resolved_home", "HOME"), ("foreground_activity", "Foreground"),
                       ("memory", "Memory"), ("low_power", "Low power")):
        row = report[key]
        value = json.dumps(row["data"], ensure_ascii=False) if row["status"] == "ok" else "unavailable: " + row["reason"]
        lines.append(f"{label}: {value}")
    sample = report["cpu_sample"]
    lines.append(f"CPU sample: {sample['requested_seconds']}s requested; {sample['elapsed_seconds']:.2f}s observed")
    lines.append(f"Counter read spans: {sample['before']['read_span_seconds']:.3f}s / {sample['after']['read_span_seconds']:.3f}s; app CPU limit {sample['max_allowed_read_span_seconds']:.3f}s per endpoint")
    system, app = sample["system_cpu"], sample["app_cpu"]
    lines.append(f"System CPU: {system['busy_percent']:.1f}% busy across all CPUs; {system['iowait_percent']:.1f}% iowait"
                 if system["status"] == "ok" else "System CPU: unavailable: " + system["reason"])
    lines.append(f"Mesen CPU: {app['total_capacity_percent']:.1f}% of total capacity; {app['one_core_equivalent_percent']:.1f}% of one core ({app['cpu_count']} logical CPUs), PID {app['pid']}"
                 if app["status"] == "ok" else "Mesen CPU: unavailable: " + app["reason"])
    lines.extend([report["limitations"], report["scope"]])
    if report.get("folder"):
        lines.append("Saved: " + report["folder"])
    return "\n".join(lines)


def duration(value):
    try:
        seconds = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("seconds must be an integer from 1 to 30")
    if not 1 <= seconds <= 30:
        raise argparse.ArgumentTypeError("seconds must be from 1 to 30")
    return seconds


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seconds", type=duration, default=5, help="CPU sample interval, 1..30 seconds (default 5)")
    parser.add_argument("--serial", default=os.getenv("OOS_DEVICE_SERIAL"))
    parser.add_argument("--out", type=Path, help="Parent directory; each report creates a unique child")
    args = parser.parse_args(argv)
    try:
        device = Device(args.serial)
        folder = new_bundle(args.out or ROOT / "Roms/device-diagnostics", "android")
        report = collect(device, args.seconds)
        report["folder"] = str(folder)
        rendered = summary(report)
        (folder / "report.json").write_text(json.dumps(report, indent=2) + "\n")
        (folder / "summary.txt").write_text(rendered + "\n")
        print(rendered)
        return 0
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
