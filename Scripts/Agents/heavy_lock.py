#!/usr/bin/env python3
"""Shared heavy lock for native emulator runs, C++ builds and large test batches.

One heavy job at a time on this machine (scawful, 2026-09-26). The lock is the
directory /tmp/oos-heavy.lock (OOS_HEAVY_LOCK overrides it) with a JSON file
`owner` inside. A stable advisory mutex serializes all lease mutations.

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
import fcntl
from contextlib import contextmanager
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
class ProcessInspectionError(RuntimeError):
    """Process identity could not be determined safely."""


@contextmanager
def _critical_section():
    # Never unlink this inode: all cooperating writers lock the same file.
    path = LOCK.with_name(LOCK.name + ".mutex")
    with path.open("a+") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            yield False
            return
        try:
            yield True
        finally:
            fcntl.flock(handle, fcntl.LOCK_UN)


def process_start(pid: int) -> str | None:
    """Start time as `ps -o lstart=` prints it (24 chars), or None if the PID is gone."""
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return None
    except PermissionError:
        pass  # exists, owned by another user
    try:
        out = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "lstart="],
                             capture_output=True, text=True)
    except OSError as error:
        raise ProcessInspectionError(str(error)) from error
    start = " ".join(out.stdout.split())
    if out.returncode != 0 or not start:
        raise ProcessInspectionError(f"cannot inspect pid {pid}")
    return start


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
    try:
        start = process_start(pid)
    except ProcessInspectionError:
        return {"state": "held", "reason": f"pid {pid} identity unknown; not reclaimable", "owner": owner}
    if start is None:
        return {"state": "stale", "reason": f"pid {pid} has exited", "owner": owner}
    want = recorded_start(owner)
    if want and want != start:
        return {"state": "stale", "reason": f"pid {pid} was reused (started {start}, recorded {want})",
                "owner": owner}
    return {"state": "held", "reason": f"pid {pid} is running", "owner": owner}


def _reclaim_if_stale() -> dict | None:
    """Caller must hold the shared namespace mutex."""
    st = status()
    if st["state"] != "stale":
        return None
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    receipt = f"{stamp}-{uuid.uuid4().hex}"
    ARCHIVE.mkdir(parents=True, exist_ok=True)
    # Preserve receipts before removing the lease. Exclusive creation avoids loss.
    owner_text = (LOCK / "owner").read_text() if (LOCK / "owner").exists() else None
    if owner_text is not None:
        with (ARCHIVE / f"{receipt}-owner.json").open("x") as out:
            out.write(owner_text)
    with (ARCHIVE / f"{receipt}-reason.txt").open("x") as out:
        out.write(st["reason"] + "\n")
    shutil.rmtree(LOCK)
    return st


def reclaim_if_stale() -> dict | None:
    """Remove a confirmed stale lease under the shared namespace mutex."""
    with _critical_section() as locked:
        return _reclaim_if_stale() if locked else None


def acquire(owner: str, purpose: str, pid: int | None = None, wait: float = 0, poll: float = 60,
            log=None) -> str | None:
    """Take the lock for `pid` (default: this process). Returns the token, or None
    if `wait` seconds pass first."""
    pid = os.getpid() if pid is None else pid
    if type(pid) is not int or pid <= 0:
        return None
    deadline = time.monotonic() + wait
    while True:
        with _critical_section() as locked:
            if locked:
                try:
                    start = process_start(pid)
                except ProcessInspectionError:
                    return None
                if start is None:
                    return None
                if LOCK.exists():
                    st = _reclaim_if_stale()
                    if st is not None and log:
                        log(f"reclaimed stale lock: {st['reason']}")
                if not LOCK.exists():
                    LOCK.mkdir()
                    token = str(uuid.uuid4())
                    data = {"owner": owner, "token": token,
                            "acquired_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                            "purpose": purpose, "pid": pid, "pid_start": start}
                    try:
                        tmp = LOCK / "owner.tmp"
                        tmp.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
                        tmp.replace(LOCK / "owner")
                    except Exception:
                        shutil.rmtree(LOCK)
                        raise
                    return token
        if time.monotonic() >= deadline:
            return None
        if log:
            log("lock busy")
        time.sleep(max(0.0, min(poll, deadline - time.monotonic())))


def release(token: str) -> bool:
    with _critical_section() as locked:
        if not locked:
            return False
        owner = read_owner()
        if not owner or owner.get("token") != token:
            return False
        shutil.rmtree(LOCK)
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
        token = acquire(args.owner, args.purpose, os.getppid() if args.pid is None else args.pid, args.wait, args.poll,
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
