"""Bounded cleanup of one private Mesen launch, including delayed macOS startup.

The caller must allocate a unique ROM path for the new run before launching it.
Never construct a cleanup object for a source play window or reuse one after a
successful handoff. No process names, parent groups, sockets, or receipt statuses
confer ownership: both the executable and a complete ROM argv element must match.

The macOS readers come from the qualified Lyra launch_profile helpers; positive
exit and delayed discovery follow resume_lyra. They remain independent here of
launching, profile/save management, and receipt writing.
"""
from __future__ import annotations

import ctypes
from dataclasses import dataclass
import math
import os
from pathlib import Path
import signal
import struct
import subprocess
import sys
import time
from typing import Protocol


def _valid_pid(pid: int) -> bool:
    return isinstance(pid, int) and not isinstance(pid, bool) and 0 < pid <= 0x7FFFFFFF


def parse_procargs2(data: bytes) -> tuple[str, ...]:
    """Decode argc argv strings, excluding the trailing process environment."""
    if len(data) < 4:
        raise ValueError("Incomplete KERN_PROCARGS2 header")
    argc = struct.unpack_from("=i", data)[0]
    if not 0 < argc <= 4096:
        raise ValueError("Invalid KERN_PROCARGS2 argument count")
    position = data.find(b"\0", 4)
    if position < 0:
        raise ValueError("Missing KERN_PROCARGS2 executable terminator")
    while position < len(data) and data[position] == 0:
        position += 1
    arguments = []
    for _ in range(argc):
        end = data.find(b"\0", position)
        if end < 0:
            raise ValueError("Incomplete KERN_PROCARGS2 argv")
        arguments.append(os.fsdecode(data[position:end]))
        position = end + 1
    return tuple(arguments)


class ProcessBackend(Protocol):
    """Injectable process observations and PID-only termination; errors propagate."""

    def pids(self) -> list[int]: ...
    def executable(self, pid: int) -> Path | None: ...
    def arguments(self, pid: int) -> tuple[str, ...]: ...
    def exists(self, pid: int) -> bool: ...
    def terminate(self, pid: int) -> None: ...
    def monotonic(self) -> float: ...
    def sleep(self, seconds: float) -> None: ...


class MacProcessBackend:
    """macOS libproc/sysctl identity; only ESRCH establishes PID absence."""

    def pids(self) -> list[int]:
        result = subprocess.run(["/bin/ps", "-axo", "pid="], text=True,
                                capture_output=True, check=True, timeout=5)
        return [int(value) for line in result.stdout.splitlines()
                if (value := line.strip()).isdecimal() and int(value) > 0]

    def executable(self, pid: int) -> Path | None:
        if sys.platform != "darwin" or not _valid_pid(pid):
            return None
        library = ctypes.CDLL("/usr/lib/libproc.dylib", use_errno=True)
        query = library.proc_pidpath
        query.argtypes = (ctypes.c_int, ctypes.c_void_p, ctypes.c_uint32)
        query.restype = ctypes.c_int
        buffer = ctypes.create_string_buffer(4096)
        if query(pid, buffer, len(buffer)) <= 0:
            return None
        return Path(os.fsdecode(buffer.value)).resolve()

    def arguments(self, pid: int) -> tuple[str, ...]:
        if sys.platform != "darwin" or not _valid_pid(pid):
            raise OSError("KERN_PROCARGS2 requires macOS and a positive PID")
        libc = ctypes.CDLL("/usr/lib/libSystem.B.dylib", use_errno=True)
        query = libc.sysctl
        query.argtypes = (ctypes.POINTER(ctypes.c_int), ctypes.c_uint,
                          ctypes.c_void_p, ctypes.POINTER(ctypes.c_size_t),
                          ctypes.c_void_p, ctypes.c_size_t)
        query.restype = ctypes.c_int
        limit = ctypes.c_int()
        size = ctypes.c_size_t(ctypes.sizeof(limit))
        # SDK sys/sysctl.h: CTL_KERN=1, KERN_ARGMAX=8, KERN_PROCARGS2=49.
        argmax = (ctypes.c_int * 2)(1, 8)
        if query(argmax, 2, ctypes.byref(limit), ctypes.byref(size), None, 0) != 0:
            raise OSError(ctypes.get_errno(), "Could not read kernel argv size limit")
        if not 0 < limit.value <= 8 * 1024 * 1024:
            raise ValueError("Kernel argv size limit is outside the bounded range")
        buffer = ctypes.create_string_buffer(limit.value)
        size = ctypes.c_size_t(len(buffer))
        selector = (ctypes.c_int * 3)(1, 49, pid)
        if query(selector, 3, buffer, ctypes.byref(size), None, 0) != 0:
            raise OSError(ctypes.get_errno(), "Could not verify matching Mesen PID argv")
        return parse_procargs2(buffer.raw[:size.value])

    def exists(self, pid: int) -> bool:
        if not _valid_pid(pid):
            raise ValueError("A positive PID is required")
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        return True

    def terminate(self, pid: int) -> None:
        if not _valid_pid(pid):
            raise ValueError("A positive PID is required")
        os.kill(pid, signal.SIGTERM)

    monotonic = staticmethod(time.monotonic)
    sleep = staticmethod(time.sleep)


def owns_process(pid: int, binary: Path, rom: Path, backend: ProcessBackend) -> bool:
    """Exact executable plus unique ROM argv; unknown identity never matches."""
    if not _valid_pid(pid):
        return False
    expected = binary.resolve()
    try:
        if backend.executable(pid) != expected:
            return False
        arguments = backend.arguments(pid)
        # Recheck executable identity after argv in case the PID was reused.
        return str(rom.resolve()) in arguments[1:] and backend.executable(pid) == expected
    except (OSError, ValueError):
        return False


class CleanupUnconfirmed(RuntimeError):
    """Cleanup could not positively establish exit; the caller must retain it."""


@dataclass(frozen=True)
class CleanupResult:
    checked_pids: tuple[int, ...]
    stopped_owned_pids: tuple[int, ...]
    pid_exit_confirmed: bool = True


class OwnedProcessCleanup:
    """One cancellation operation, retained across repeated cancellation requests.

    Construct before launching with this run's private binary/ROM pair. Call
    cancel(pid=...) if launch already returned a PID, otherwise let bounded
    discovery find it. A completed result is cached, so repeated calls cannot
    signal a subsequently reused PID. Uncertainty raises CleanupUnconfirmed and
    must not be recorded as successful cleanup. This is a single-threaded helper;
    the future signal adapter must suppress reentrant cancellation while it runs.
    """

    def __init__(self, binary: Path, rom: Path, *, backend: ProcessBackend | None = None):
        self.binary = binary.resolve()
        self.rom = rom.resolve()
        self.backend = backend if backend is not None else MacProcessBackend()
        self._pids: set[int] = set()
        self._signalled: set[int] = set()
        self._exited: set[int] = set()
        self._result: CleanupResult | None = None

    def cancel(self, *, pid: int | None = None, discovery_timeout: float = 10,
               exit_timeout: float = 8, poll_interval: float = 0.05) -> CleanupResult:
        """Discover delayed launches, send PID-only SIGTERM, and confirm absence."""
        if pid is not None and not _valid_pid(pid):
            raise ValueError("A positive PID is required")
        if any(not math.isfinite(value) or value < 0
               for value in (discovery_timeout, exit_timeout)) or not (
                   math.isfinite(poll_interval) and poll_interval > 0):
            raise ValueError("Cleanup timeouts must be finite and polling positive")
        if pid is not None:
            if self._pids and pid not in self._pids:
                raise ValueError("Cleanup already belongs to a different PID")
            self._pids.add(pid)
        if self._result is not None:
            return self._result
        try:
            if not self._pids:
                deadline = self.backend.monotonic() + discovery_timeout
                while not self._pids:
                    self._pids.update(candidate for candidate in self.backend.pids()
                                      if owns_process(candidate, self.binary, self.rom,
                                                      self.backend))
                    if self._pids:
                        break
                    if self.backend.monotonic() >= deadline:
                        raise CleanupUnconfirmed("No owned launch PID discovered; cleanup unconfirmed")
                    self.backend.sleep(max(0, min(poll_interval,
                                                  deadline - self.backend.monotonic())))
            for candidate in sorted(self._pids - self._exited):
                self._stop(candidate, exit_timeout, poll_interval)
        except (OSError, subprocess.SubprocessError) as error:
            raise CleanupUnconfirmed("Process observation or termination failed; cleanup unconfirmed") from error
        self._result = CleanupResult(tuple(sorted(self._pids)), tuple(sorted(self._signalled)))
        return self._result

    def _stop(self, pid: int, timeout: float, poll_interval: float) -> None:
        deadline = self.backend.monotonic() + timeout
        while self.backend.exists(pid):
            if not owns_process(pid, self.binary, self.rom, self.backend):
                raise CleanupUnconfirmed(f"PID {pid} is live but ownership is unconfirmed")
            if pid not in self._signalled:
                try:
                    self.backend.terminate(pid)
                except ProcessLookupError:
                    # A race with exit still requires a separate absence check.
                    pass
                else:
                    self._signalled.add(pid)
                if not self.backend.exists(pid):
                    break
            if self.backend.monotonic() >= deadline:
                raise CleanupUnconfirmed(f"Owned PID {pid} did not exit before the deadline")
            self.backend.sleep(max(0, min(poll_interval,
                                          deadline - self.backend.monotonic())))
        self._exited.add(pid)
