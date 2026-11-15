#!/usr/bin/env python3
"""Owned native runs: heavy lock, owned Mesen PIDs, deadline and teardown.

On 2026-11-10, 49 headless Mesen processes were left running after native
test batches. Every native run should go through one NativeSession:
  - a unique instance ID per run;
  - the heavy lock (Scripts/Agents/heavy_lock.py), held by this process;
  - an owned-PID registry file. A Mesen is registered only when the status
    file beside a socket this run chose names it, the process started after
    the launch began, and its executable file is Mesen. The PID's start time
    is recorded with it. A launch not identified in time stays pending and
    is checked again at teardown;
  - a deadline (SIGALRM), and SIGTERM/SIGINT/SIGHUP handlers that raise
    SessionInterrupted, so teardown runs and the caller starts no next case;
  - teardown: stop and wait for every registered PID whose start time still
    matches, release the lock, then log `teardown: stopped N pids, lock released`.

Library:
    with NativeSession(owner, purpose, run_dir, deadline=600) as session:
        pid, socket = session.launch_mesen(rom, home=home)
        ...

Commands:
  native_session.py run --owner NAME --purpose TEXT --run-dir DIR
                        [--deadline SEC] [--wait SEC] -- CMD [ARG...]
      Runs CMD in its own process group inside one session. Each Mesen that
      Scripts/Mesen2/mesen2_launch_instance.sh starts under CMD registers
      itself (the launcher sees OOS_NATIVE_SESSION_REGISTRY). On cancel or
      deadline the wrapper stops CMD's process group first, then the Mesens.
  native_session.py register --registry FILE --socket PATH [--since EPOCH] [--timeout SEC]
  native_session.py teardown --registry FILE
      Manual cleanup when a wrapper was killed with SIGKILL and could not
      run its own teardown.
Exit codes for `run`: CMD's code; 124 deadline; 128+N on signal N; 3 lock wait
ran out.

Process inspection is per PID (`ps -p PID -o lstart=`). Nothing here reads
or prints process arguments, and nothing stops a PID it did not register.
"""
from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import importlib.util
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
LAUNCHER = REPO / "Scripts" / "Mesen2" / "mesen2_launch_instance.sh"
REGISTRY_ENV = "OOS_NATIVE_SESSION_REGISTRY"
INSTANCE_ENV = "OOS_NATIVE_SESSION_INSTANCE"
CANCEL_SIGNALS = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
PROCESS_NAME = "mesen"  # a registered PID's executable name must contain this
TERM_WAIT = 5.0  # seconds between SIGTERM and SIGKILL for an owned PID
GROUP_WAIT = 15.0  # seconds a cancelled CMD gets to run its own teardown
# `ps` start times are whole seconds, and Linux adds them to a boot time that
# is also whole seconds, so a fresh process can read up to ~2 s early.
START_SLACK = 2.0

_spec = importlib.util.spec_from_file_location("heavy_lock", Path(__file__).with_name("heavy_lock.py"))
heavy_lock = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(heavy_lock)


class SessionInterrupted(BaseException):
    """Deadline or cancel signal. BaseException, so a case body's
    `except Exception` cannot swallow it and go on to the next case."""

    def __init__(self, reason: str, exit_code: int):
        super().__init__(reason)
        self.reason = reason
        self.exit_code = exit_code


class LaunchError(RuntimeError):
    """The launched Mesen could not be identified as this run's."""


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _start_epoch(start: str) -> float | None:
    try:
        return time.mktime(time.strptime(start, "%a %b %d %H:%M:%S %Y"))
    except ValueError:
        return None


def process_name(pid: int) -> str:
    """The executable file's name (`ps -o ucomm=`), never the arguments.
    `comm` on macOS follows argv[0], which a caller can set to anything."""
    out = subprocess.run(["/bin/ps", "-p", str(pid), "-o", "ucomm="], capture_output=True, text=True)
    return Path(out.stdout.strip()).name


def status_path(socket: Path) -> Path:
    """Mesen writes <socket minus .sock>.status with its pid and socketPath."""
    text = str(socket)
    return Path(text[:-5] + ".status" if text.endswith(".sock") else text + ".status")


class Registry:
    """Append-only JSON lines: one entry per owned PID, plus a pending entry
    (socket and launch time, no pid) for each launch that could not be
    identified in time."""

    def __init__(self, path: Path):
        self.path = Path(path)

    def add(self, entry: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a", encoding="utf-8") as handle:
            fcntl.flock(handle, fcntl.LOCK_EX)
            handle.write(json.dumps(entry) + "\n")
            handle.flush()
            fcntl.flock(handle, fcntl.LOCK_UN)

    def _read(self) -> list[dict]:
        try:
            lines = self.path.read_text(encoding="utf-8").splitlines()
        except FileNotFoundError:
            return []
        out = []
        for line in lines:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(entry, dict):
                out.append(entry)
        return out

    def entries(self) -> list[dict]:
        return [e for e in self._read() if isinstance(e.get("pid"), int)]

    def pending(self) -> list[dict]:
        return [e for e in self._read() if e.get("pending") and e.get("socket")]


def find_owned_pid(socket: Path, since: float, timeout: float) -> tuple[int, str]:
    """PID and start time of the Mesen serving `socket`, from its status file.
    The process must have started at or after `since` (epoch seconds)."""
    status = status_path(socket)
    deadline = time.monotonic() + timeout
    reason = "no status file"
    while True:
        try:
            data = json.loads(status.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
        if isinstance(data, dict):
            pid = data.get("pid")
            if data.get("socketPath") != str(socket):
                reason = "status file names another socket"
            elif not isinstance(pid, int) or pid <= 0:
                reason = "status file has no pid"
            else:
                start = heavy_lock.process_start(pid)
                started = _start_epoch(start) if start else None
                if start is None:
                    reason = f"pid {pid} from the status file has exited"
                elif started is None or started < since - START_SLACK:
                    reason = f"pid {pid} started before this launch"
                elif PROCESS_NAME not in process_name(pid).lower():
                    reason = f"pid {pid} is not a {PROCESS_NAME} process"
                else:
                    return pid, start
        if time.monotonic() >= deadline:
            raise LaunchError(f"{socket}: {reason}")
        time.sleep(0.2)


def register(registry: Registry, socket: Path, since: float, timeout: float, instance: str) -> int:
    """Register the Mesen serving `socket`. On failure the socket is kept as a
    pending entry, so teardown can still stop a Mesen that came up late."""
    try:
        pid, start = find_owned_pid(Path(socket), since, timeout)
    except LaunchError as error:
        registry.add({"pending": True, "socket": str(socket), "since": since,
                      "instance": instance, "reason": str(error), "at": _now()})
        raise
    registry.add({"pid": pid, "pid_start": start, "socket": str(socket),
                  "instance": instance, "registered_at": _now()})
    return pid


def resolve_pending(registry: Registry, log=print) -> None:
    """Look at each pending socket's status file once more and register the
    Mesen it names when that process started after the launch."""
    known = {e.get("socket") for e in registry.entries()}
    for entry in registry.pending():
        if entry["socket"] in known:
            continue
        try:
            pid, start = find_owned_pid(Path(entry["socket"]), float(entry.get("since", 0)), 0)
        except LaunchError as error:
            log(f"pending launch still unidentified: {error}")
            continue
        registry.add({"pid": pid, "pid_start": start, "socket": entry["socket"],
                      "instance": entry.get("instance"), "registered_at": _now(), "late": True})
        known.add(entry["socket"])
        log(f"late registration: pid {pid} ({entry['socket']})")


def stop_owned(entries: list[dict], log=print, term_wait: float = TERM_WAIT) -> dict:
    """Stop each entry whose PID still has its recorded start time.
    Returns counts: stopped, gone (already exited), reused, running (pids)."""
    result = {"stopped": 0, "gone": 0, "reused": 0, "running": []}
    seen = set()
    for entry in entries:
        pid, want = entry["pid"], " ".join(str(entry.get("pid_start", "")).split())
        if pid in seen:
            continue
        seen.add(pid)
        try:
            start = heavy_lock.process_start(pid)
        except heavy_lock.ProcessInspectionError:
            log(f"pid {pid}: identity unknown; not stopped")
            result["running"].append(pid)
            continue
        if start is None:
            result["gone"] += 1
            continue
        if not want or start != want:
            log(f"pid {pid}: start time changed (reused); not stopped")
            result["reused"] += 1
            continue
        for sig, wait in ((signal.SIGTERM, term_wait), (signal.SIGKILL, 3.0)):
            try:
                os.kill(pid, sig)
            except ProcessLookupError:
                break
            end = time.monotonic() + wait
            while time.monotonic() < end and heavy_lock.process_start(pid) == want:
                time.sleep(0.1)
            if heavy_lock.process_start(pid) != want:
                break
        if heavy_lock.process_start(pid) == want:
            result["running"].append(pid)
        else:
            result["stopped"] += 1
            for path in (Path(entry.get("socket", "")), status_path(Path(entry.get("socket", "")))):
                if entry.get("socket") and path.exists():
                    path.unlink(missing_ok=True)
    return result


class NativeSession:
    def __init__(self, owner: str, purpose: str, run_dir, deadline: float = 600.0,
                 wait: float = 3600.0, poll: float = 10.0, term_wait: float = TERM_WAIT):
        slug = re.sub(r"[^A-Za-z0-9]+", "-", owner).strip("-").lower()[:20] or "agent"
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        self.instance = f"{slug}-{stamp}-{uuid.uuid4().hex[:8]}"
        self.owner, self.purpose = owner, purpose
        self.run_dir = Path(run_dir)
        self.deadline, self.wait, self.poll, self.term_wait = deadline, wait, poll, term_wait
        inherited = os.environ.get(REGISTRY_ENV)
        self.nested = inherited is not None
        self.registry = Registry(Path(inherited) if inherited else self.run_dir / "owned_pids.jsonl")
        self.log_path = self.run_dir / "session.log"
        self.token: str | None = None
        self.teardown_result: dict | None = None
        self._launches = 0
        self._saved_handlers: dict = {}
        self._deferred: list[int] = []
        self._closed = False

    def log(self, message: str) -> None:
        line = f"{_now()} [{self.instance}] {message}"
        self.run_dir.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        print(line, file=sys.stderr, flush=True)

    def _raise_for(self, signum, _frame):
        raise SessionInterrupted(f"signal {signal.Signals(signum).name}", 128 + signum)

    def _raise_deadline(self, _signum, _frame):
        raise SessionInterrupted(f"deadline {self.deadline:g}s", 124)

    def _defer(self, signum, _frame):
        self._deferred.append(signum)

    def defer_cancels(self) -> None:
        """From here on a cancel signal is recorded, not raised, so cleanup
        cannot be cut short by a second Ctrl-C or SIGTERM."""
        for sig in CANCEL_SIGNALS:
            signal.signal(sig, self._defer)

    def __enter__(self):
        if threading.current_thread() is not threading.main_thread():
            raise RuntimeError("NativeSession needs the main thread for its signal handlers")
        self.log(f"start: owner {self.owner}, purpose {self.purpose}, pid {os.getpid()}, "
                 f"deadline {self.deadline:g}s, registry {self.registry.path}"
                 + (" (nested; the parent session holds the lock)" if self.nested else ""))
        for sig in CANCEL_SIGNALS:
            self._saved_handlers[sig] = signal.signal(sig, self._raise_for)
        self._saved_handlers[signal.SIGALRM] = signal.signal(signal.SIGALRM, self._raise_deadline)
        try:
            if not self.nested:
                self.token = heavy_lock.acquire(self.owner, f"{self.purpose} [{self.instance}]",
                                                pid=os.getpid(), wait=self.wait, poll=self.poll,
                                                log=self.log)
                if self.token is None:
                    raise SessionInterrupted("heavy lock not free before the wait ran out", 3)
                self.log("heavy lock acquired")
            if self.deadline > 0:
                signal.setitimer(signal.ITIMER_REAL, self.deadline)
        except BaseException:
            self.close()
            raise
        return self

    def __exit__(self, exc_type, exc, tb):
        if isinstance(exc, SessionInterrupted):
            self.log(f"interrupted: {exc.reason}")
        elif exc is not None:
            self.log(f"error: {exc_type.__name__}: {exc}")
        self.close()
        if exc is None and self._deferred:
            signum = self._deferred[0]
            raise SessionInterrupted(f"signal {signal.Signals(signum).name} during teardown", 128 + signum)
        return False

    def launch_mesen(self, rom, home=None, launcher_args=(), env=None, timeout: float = 40.0):
        """Start a headless Mesen through the shared launcher and register it.
        Returns (pid, socket)."""
        self._launches += 1
        name = f"{self.instance}-{self._launches}"
        socket = Path(f"/tmp/mesen2-{name}.sock")
        cmd = ["bash", str(LAUNCHER), "--headless", "--no-register", "--instance", name,
               "--socket", str(socket), "--rom", str(rom), *launcher_args]
        if home is not None:
            cmd += ["--home", str(home)]
        launch_env = dict(os.environ if env is None else env)
        launch_env.pop(REGISTRY_ENV, None)
        since = time.time()
        with (self.run_dir / f"launch-{self._launches}.log").open("w") as out:
            subprocess.run(cmd, cwd=REPO, stdout=out, stderr=out, check=True, timeout=timeout,
                           env=launch_env)
        return self.register(socket, since=since, timeout=timeout), socket

    def register(self, socket, since: float, timeout: float = 40.0) -> int:
        try:
            pid = register(self.registry, Path(socket), since, timeout, self.instance)
        except LaunchError as error:
            self.log(f"register failed: {error}. Kept as pending; teardown checks it again.")
            raise
        self.log(f"registered pid {pid} ({socket})")
        return pid

    def close(self) -> None:
        """Teardown. Safe to call twice; cancel signals are deferred meanwhile."""
        if self._closed:
            return
        self._closed = True
        signal.setitimer(signal.ITIMER_REAL, 0)
        self.defer_cancels()
        try:
            resolve_pending(self.registry, log=self.log)
            result = stop_owned(self.registry.entries(), log=self.log, term_wait=self.term_wait)
            if self.nested:
                lock = "lock held by the parent session"
            elif self.token is None:
                lock = "lock not held"
            elif result["running"]:
                lock = "lock kept"
            else:
                lock = "lock released" if heavy_lock.release(self.token) else "lock release refused"
            self.teardown_result = dict(result, lock=lock)
            extra = []
            if result["gone"]:
                extra.append(f"{result['gone']} already exited")
            if result["reused"]:
                extra.append(f"{result['reused']} reused, not stopped")
            if result["running"]:
                extra.append(f"{len(result['running'])} STILL RUNNING {result['running']}")
            self.log(f"teardown: stopped {result['stopped']} pids, {lock}"
                     + (f" ({'; '.join(extra)})" if extra else ""))
        finally:
            for sig, handler in self._saved_handlers.items():
                signal.signal(sig, handler)


def _stop_group(child: subprocess.Popen, log) -> None:
    """Stop CMD and everything in its process group, waiting for CMD."""
    for sig, wait in ((signal.SIGTERM, GROUP_WAIT), (signal.SIGKILL, 5.0)):
        try:
            os.killpg(child.pid, sig)
        except ProcessLookupError:
            return
        try:
            child.wait(timeout=wait)
            return
        except subprocess.TimeoutExpired:
            log(f"command pid {child.pid} still running after {signal.Signals(sig).name}")


def cmd_run(args) -> int:
    command = args.command[1:] if args.command[:1] == ["--"] else args.command
    if not command:
        print("run: give the command after --", file=sys.stderr)
        return 2
    session = NativeSession(args.owner, args.purpose, args.run_dir, deadline=args.deadline,
                            wait=args.wait, poll=args.poll)
    try:
        with session:
            env = dict(os.environ, **{REGISTRY_ENV: str(session.registry.path),
                                      INSTANCE_ENV: session.instance})
            child = subprocess.Popen(command, env=env, start_new_session=True)
            session.log(f"command started: pid {child.pid}")
            try:
                code = child.wait()
            finally:
                if child.poll() is None:
                    signal.setitimer(signal.ITIMER_REAL, 0)
                    session.defer_cancels()
                    session.log("stopping the command's process group")
                    _stop_group(child, session.log)
            session.log(f"command exited: {code}")
            return code
    except SessionInterrupted as interrupted:
        return interrupted.exit_code


def cmd_register(args) -> int:
    instance = os.environ.get(INSTANCE_ENV, "unknown")
    since = args.since if args.since is not None else time.time() - args.timeout
    try:
        pid = register(Registry(args.registry), Path(args.socket), since, args.timeout, instance)
    except LaunchError as error:
        print(f"register failed: {error}", file=sys.stderr)
        return 1
    print(pid)
    return 0


def cmd_teardown(args) -> int:
    registry = Registry(args.registry)
    resolve_pending(registry, log=lambda m: print(m, file=sys.stderr))
    result = stop_owned(registry.entries(), log=lambda m: print(m, file=sys.stderr))
    print(f"teardown: stopped {result['stopped']} pids ({result['gone']} already exited, "
          f"{result['reused']} reused, {len(result['running'])} still running)")
    return 1 if result["running"] else 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run")
    r.add_argument("--owner", required=True)
    r.add_argument("--purpose", required=True)
    r.add_argument("--run-dir", required=True)
    r.add_argument("--deadline", type=float, default=600)
    r.add_argument("--wait", type=float, default=3600)
    r.add_argument("--poll", type=float, default=10)
    r.add_argument("command", nargs=argparse.REMAINDER)
    g = sub.add_parser("register")
    g.add_argument("--registry", required=True)
    g.add_argument("--socket", required=True)
    g.add_argument("--since", type=float)
    g.add_argument("--timeout", type=float, default=30)
    t = sub.add_parser("teardown")
    t.add_argument("--registry", required=True)
    args = ap.parse_args(argv)
    return {"run": cmd_run, "register": cmd_register, "teardown": cmd_teardown}[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
