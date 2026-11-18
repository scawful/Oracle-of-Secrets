#!/usr/bin/env python3
"""Editor lock for the real Oracle project ROM (scawful, 2026-11-16, option 1).

While scawful has yaze open on the project, agents must not write
`Oracle-of-Secrets.yazeproj/rom`: his open session can save over their write,
or their write can change data under his edits.

The lock is a JSON file next to the project bundle (OOS_ROM_LOCK overrides):
  ~/Zelda/Projects/Oracle-of-Secrets/.rom-editor.lock
It records owner, the PID of the editor process and that process's start time.
A lock whose PID is gone or whose start time differs (PID reuse) is stale and
is removed automatically.

`check` also scans running processes (/bin/ps) for a yaze whose command line
names the project bundle, so a yaze started outside the hub still counts.
A yaze opened from the Dock and then File > Open is not visible to that scan.

Commands:
  project_rom_lock.py hold --owner NAME -- CMD [ARGS...]
      Take the lock, run CMD, keep the lock until CMD exits. The sketchybar
      hub runs `hold --owner scawful -- /bin/zsh "Open Oracle.command"`.
  project_rom_lock.py check
      Agents run this before any project-ROM write.
      Exit 0 = free, write allowed. Exit 2 = held, do not write.
  project_rom_lock.py status [--short]
      Print the lock state. Exit 0 = free, 2 = held.

Agent rule: `python3 Scripts/Agents/project_rom_lock.py check || stop`.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import signal
import subprocess
import sys
from pathlib import Path

PROJECT = Path(os.environ.get(
    "OOS_PROJECT_BUNDLE",
    "~/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj")).expanduser()
LOCK = Path(os.environ.get("OOS_ROM_LOCK", str(PROJECT.parent / ".rom-editor.lock"))).expanduser()
HELD = 2


def process_start(pid: int) -> str | None:
    """`ps -o lstart=` for PID, or None when the PID does not exist."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass
    out = subprocess.run(["/bin/ps", "-o", "lstart=", "-p", str(pid)],
                         capture_output=True, text=True, check=False).stdout.strip()
    return out or None


def read_lock() -> dict | None:
    """Return the live lock record, removing a stale one."""
    try:
        record = json.loads(LOCK.read_text())
    except FileNotFoundError:
        return None
    except (OSError, ValueError):
        return {"owner": "unreadable lock file", "pid": None}
    pid = record.get("pid")
    if isinstance(pid, int) and pid > 0 and process_start(pid) != record.get("start"):
        try:
            LOCK.unlink()
        except FileNotFoundError:
            pass
        return None
    return record


def yaze_processes() -> list[tuple[int, str]]:
    """Running yaze GUI processes whose command line names the project bundle."""
    out = subprocess.run(["/bin/ps", "-axo", "pid=,command="],
                         capture_output=True, text=True, check=False).stdout
    rows = []
    for line in out.splitlines():
        pid_text, _, command = line.strip().partition(" ")
        exe = command.split(" --", 1)[0]
        if exe.endswith("/yaze") and PROJECT.name in command:
            rows.append((int(pid_text), command))
    return rows


def describe(record: dict) -> str:
    since = record.get("since", "")[11:16]
    return f"{record.get('owner', '?')} (pid {record.get('pid')}, since {since}Z)"


def state() -> tuple[bool, str]:
    record = read_lock()
    if record:
        return True, "held by " + describe(record)
    procs = yaze_processes()
    if procs:
        return True, f"yaze open on the project without the hub lock (pid {procs[0][0]})"
    return False, "free"


def cmd_status(args: argparse.Namespace) -> int:
    held, text = state()
    print(f"ROM lock: {text}" if args.short else f"{LOCK}\nproject: {PROJECT}\nstate: {text}")
    return HELD if held else 0


def cmd_check(_: argparse.Namespace) -> int:
    held, text = state()
    if held:
        print(f"project ROM is locked: {text}. Do not write {PROJECT}/rom.", file=sys.stderr)
        return HELD
    return 0


def cmd_hold(args: argparse.Namespace) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("hold needs a command after --", file=sys.stderr)
        return 1
    if read_lock():
        print(f"project ROM already locked: {state()[1]}", file=sys.stderr)
        return HELD
    child = subprocess.Popen(command)
    record = {"owner": args.owner, "pid": child.pid, "start": process_start(child.pid),
              "command": command, "since": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")}
    try:
        fd = os.open(LOCK, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    except FileExistsError:
        child.terminate()
        print("project ROM lock was taken at the same moment; editor not started", file=sys.stderr)
        return HELD
    with os.fdopen(fd, "w") as handle:
        json.dump(record, handle, indent=2)

    def forward(signum, _frame):
        child.send_signal(signum)
    for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
        signal.signal(sig, forward)
    try:
        code = child.wait()
        return code if code >= 0 else 128 - code
    finally:
        try:
            if json.loads(LOCK.read_text()).get("pid") == child.pid:
                LOCK.unlink()
        except (OSError, ValueError):
            pass


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="cmd", required=True)
    hold = sub.add_parser("hold")
    hold.add_argument("--owner", required=True)
    hold.add_argument("command", nargs=argparse.REMAINDER)
    hold.set_defaults(func=cmd_hold)
    sub.add_parser("check").set_defaults(func=cmd_check)
    status = sub.add_parser("status")
    status.add_argument("--short", action="store_true")
    status.set_defaults(func=cmd_status)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
