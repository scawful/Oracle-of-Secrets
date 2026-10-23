#!/usr/bin/env python3
"""Shared heavy lock for native emulator runs, C++ builds and large test batches.

One heavy job at a time on this machine (scawful, 2026-09-26). The lock is the
directory /tmp/oos-heavy.lock (OOS_HEAVY_LOCK overrides it) with a JSON file
`owner` inside. mkdir is the atomic acquire, as before.

New since 2026-10-23 (scawful: "any agent may reclaim when the recorded owner
process has exited"): the owner file records the PID of the process that does
the work and that process's start time. A lock is stale, and any agent may
reclaim it, when:
  - the recorded PID no longer exists, or
  - the PID exists but its start time differs from the recorded one (PID reuse), or
  - the lock directory has no owner file and is older than 120 s (a crashed acquire).
A lock with a live owner, or an owner file without a PID (legacy text), is
never reclaimed. Reclaim copies the old owner file to the archive directory
(/tmp/oos-heavy-lock-reclaimed by default) before removing the lock.

Commands:
  heavy_lock.py status
  heavy_lock.py acquire --owner NAME --purpose TEXT [--pid PID] [--wait SEC] [--poll SEC]
  heavy_lock.py release --token TOKEN
`acquire` prints the token. --pid defaults to the caller's parent process,
which is the shell or script that ran the command; pass the PID of the process
that does the heavy work (for example a Mesen window) when it lives longer.
Exit codes: 0 ok, 1 refused (wrong token, lock not held), 3 wait timed out.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

LOCK = Path(os.environ.get("OOS_HEAVY_LOCK", "/tmp/oos-heavy.lock"))
ARCHIVE = Path(os.environ.get("OOS_HEAVY_LOCK_ARCHIVE", "/tmp/oos-heavy-lock-reclaimed"))
ORPHAN_AGE = 120  # seconds a lock directory may exist without an owner file
MUTEX_AGE = 60  # seconds before a crashed reclaimer's mutex is ignored


def _mutex() -> Path:
    return LOCK.with_name(LOCK.name + ".reclaim")


def process_start(pid: int) -> str | None:
    """Start time as `ps -o lstart=` prints it (24 chars), or None if the PID is gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass  # exists, owned by another user
    out = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart="], capture_output=True, text=True)
    start = " ".join(out.stdout.split())
    return start or None


def read_owner() -> dict | None:
    try:
        text = (LOCK / "owner").read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return {"legacy": text.strip()}
    return data if isinstance(data, dict) else {"legacy": text.strip()}


def recorded_start(owner: dict) -> str | None:
    if owner.get("pid_start"):
        return " ".join(str(owner["pid_start"]).split())
    ident = owner.get("process_identity")  # Codex lease format: lstart then command
    if isinstance(ident, str) and len(ident) >= 24:
        return " ".join(ident[:24].split())
    return None


def status() -> dict:
    """{'state': 'free'|'held'|'stale', 'reason': str, 'owner': dict|None}."""
    if not LOCK.exists():
        return {"state": "free", "reason": "no lock", "owner": None}
    owner = read_owner()
    if owner is None:
        try:
            age = time.time() - LOCK.stat().st_mtime
        except FileNotFoundError:
            return {"state": "free", "reason": "no lock", "owner": None}
        if age > ORPHAN_AGE:
            return {"state": "stale", "reason": f"no owner file for {int(age)} s", "owner": None}
        return {"state": "held", "reason": "owner file not written yet", "owner": None}
    pid = owner.get("pid")
    if not isinstance(pid, int) or pid <= 0:
        return {"state": "held", "reason": "owner has no pid (legacy); not reclaimable", "owner": owner}
    start = process_start(pid)
    if start is None:
        return {"state": "stale", "reason": f"pid {pid} has exited", "owner": owner}
    want = recorded_start(owner)
    if want and want != start:
        return {"state": "stale", "reason": f"pid {pid} was reused (started {start}, recorded {want})",
                "owner": owner}
    return {"state": "held", "reason": f"pid {pid} is running", "owner": owner}


def _take_mutex() -> bool:
    m = _mutex()
    try:
        m.mkdir()
        return True
    except FileExistsError:
        try:
            if time.time() - m.stat().st_mtime > MUTEX_AGE:
                m.rmdir()
        except FileNotFoundError:
            pass
        return False


def reclaim_if_stale() -> dict | None:
    """Remove a stale lock. Returns the status it acted on, or None if nothing was removed."""
    if not _take_mutex():
        return None
    try:
        st = status()
        if st["state"] != "stale":
            return None
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        moved = LOCK.with_name(f"{LOCK.name}.stale-{stamp}-{uuid.uuid4().hex[:6]}")
        try:
            LOCK.rename(moved)
        except FileNotFoundError:
            return None
        ARCHIVE.mkdir(parents=True, exist_ok=True)
        if (moved / "owner").exists():
            shutil.copy2(moved / "owner", ARCHIVE / f"{stamp}-owner.json")
        (ARCHIVE / f"{stamp}-reason.txt").write_text(st["reason"] + "\n", encoding="utf-8")
        shutil.rmtree(moved, ignore_errors=True)
        return st
    finally:
        try:
            _mutex().rmdir()
        except FileNotFoundError:
            pass


def acquire(owner: str, purpose: str, pid: int | None = None, wait: float = 0, poll: float = 60,
            log=None) -> str | None:
    """Take the lock for `pid` (default: this process). Returns the token, or None
    if `wait` seconds pass first."""
    pid = pid or os.getpid()
    deadline = time.monotonic() + wait
    while True:
        try:
            LOCK.mkdir()
        except FileExistsError:
            st = reclaim_if_stale()
            if st is not None:
                if log:
                    log(f"reclaimed stale lock: {st['reason']}")
                continue
            if time.monotonic() >= deadline:
                return None
            if log:
                cur = status()
                who = (cur["owner"] or {}).get("owner") or (cur["owner"] or {}).get("legacy") or "?"
                log(f"lock busy: {who} ({cur['reason']})")
            time.sleep(max(0.0, min(poll, deadline - time.monotonic())))
            continue
        token = str(uuid.uuid4())
        data = {"owner": owner, "token": token,
                "acquired_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                "purpose": purpose, "pid": pid, "pid_start": process_start(pid)}
        tmp = LOCK / "owner.tmp"
        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        tmp.replace(LOCK / "owner")
        return token


def release(token: str) -> bool:
    owner = read_owner()
    if not owner or owner.get("token") != token:
        return False
    shutil.rmtree(LOCK, ignore_errors=True)
    return True


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    a = sub.add_parser("acquire")
    a.add_argument("--owner", required=True)
    a.add_argument("--purpose", required=True)
    a.add_argument("--pid", type=int)
    a.add_argument("--wait", type=float, default=0)
    a.add_argument("--poll", type=float, default=60)
    r = sub.add_parser("release")
    r.add_argument("--token", required=True)
    args = ap.parse_args(argv)
    if args.cmd == "status":
        print(json.dumps(status(), indent=2))
        return 0
    if args.cmd == "acquire":
        token = acquire(args.owner, args.purpose, args.pid or os.getppid(), args.wait, args.poll,
                        log=lambda m: print(m, file=sys.stderr, flush=True))
        if token is None:
            print("heavy lock not free before --wait ran out", file=sys.stderr)
            return 3
        print(token)
        return 0
    if release(args.token):
        return 0
    print("refused: token does not match the current owner", file=sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
