"""Private process-tree containment prototype; not a Build entry point.

Windows children start suspended inside a non-breakaway, kill-on-close job.
Other platforms refuse before launch. No receipt, ROM, or lock is changed here.
"""
from __future__ import annotations

import ctypes
from ctypes import wintypes
from dataclasses import dataclass
import math
import os
from pathlib import Path
import subprocess
import time


class ContainmentUnavailable(RuntimeError):
    """No child was launched because containment is unavailable."""


class ContainmentUncertain(RuntimeError):
    """A launched process tree could not be confirmed stopped."""


@dataclass(frozen=True)
class ContainedResult:
    exit_code: int | None
    timed_out: bool


def _windows_environment_block(environment):
    """Validate and encode an explicit child environment, without mutating os.environ."""
    if environment is None:
        return None
    if type(environment) is not dict:
        raise ValueError('Child environment must be a dictionary')
    normalized = set()
    entries = []
    for key, value in environment.items():
        if (type(key) is not str or not key or '=' in key or '\0' in key
                or type(value) is not str or '\0' in value):
            raise ValueError('Child environment contains an invalid name or value')
        folded = key.upper()
        if folded in normalized:
            raise ValueError('Child environment contains duplicate Windows names')
        normalized.add(folded)
        entries.append((folded, key + '=' + value))
    return '\0'.join(value for _, value in sorted(entries)) + '\0\0'


def prepare_contained(argv, *, cwd, timeout, environment=None):
    """Validate a Windows command without creating a process."""
    if os.name != 'nt':
        raise ContainmentUnavailable('Process-tree containment is not implemented on this platform')
    if (not argv or not isinstance(timeout, (int, float)) or isinstance(timeout, bool)
            or not math.isfinite(timeout) or timeout <= 0):
        raise ValueError('A command and positive timeout are required')
    executable = Path(argv[0])
    directory = Path(cwd)
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError('Contained executable must be an absolute regular file')
    if not directory.is_absolute() or not directory.is_dir():
        raise ValueError('Contained working directory must be an absolute directory')
    return ([str(part) for part in argv], directory, float(timeout),
            _windows_environment_block(environment))


def run_contained(argv, *, cwd, timeout, environment=None):
    """Run an absolute executable and wait until its entire Windows job exits.

    A timeout terminates the owned job and returns only after it is empty. An
    exception after launch means a caller must conservatively retain its locks.
    Standard output is not captured by this prototype.
    """
    return _run_windows(*prepare_contained(argv, cwd=cwd, timeout=timeout,
                                           environment=environment))


def _run_windows(argv, directory, timeout, environment_block):
    # Fixed-width DWORDs matter even when Python itself is 64-bit.
    dword = ctypes.c_uint32
    boolean = ctypes.c_int32
    handle = wintypes.HANDLE
    size_t = ctypes.c_size_t

    class BasicLimit(ctypes.Structure):
        _fields_ = [('process_time', ctypes.c_int64), ('job_time', ctypes.c_int64),
                    ('flags', dword), ('min_working_set', size_t),
                    ('max_working_set', size_t), ('active_limit', dword),
                    ('affinity', size_t), ('priority', dword), ('scheduling', dword)]

    class IoCounters(ctypes.Structure):
        _fields_ = [(name, ctypes.c_uint64) for name in
                    ('read_ops', 'write_ops', 'other_ops', 'read_bytes', 'write_bytes', 'other_bytes')]

    class ExtendedLimit(ctypes.Structure):
        _fields_ = [('basic', BasicLimit), ('io', IoCounters),
                    ('process_memory', size_t), ('job_memory', size_t),
                    ('peak_process_memory', size_t), ('peak_job_memory', size_t)]

    class Accounting(ctypes.Structure):
        _fields_ = [('total_user', ctypes.c_int64), ('total_kernel', ctypes.c_int64),
                    ('period_user', ctypes.c_int64), ('period_kernel', ctypes.c_int64),
                    ('page_faults', dword), ('total_processes', dword),
                    ('active_processes', dword), ('terminated_processes', dword)]

    class StartupInfo(ctypes.Structure):
        _fields_ = [('cb', dword), ('reserved', wintypes.LPWSTR), ('desktop', wintypes.LPWSTR),
                    ('title', wintypes.LPWSTR), ('x', dword), ('y', dword),
                    ('x_size', dword), ('y_size', dword), ('x_chars', dword),
                    ('y_chars', dword), ('fill', dword), ('flags', dword),
                    ('show', ctypes.c_uint16), ('reserved2_size', ctypes.c_uint16),
                    ('reserved2', ctypes.POINTER(ctypes.c_ubyte)),
                    ('stdin', handle), ('stdout', handle), ('stderr', handle)]

    class ProcessInfo(ctypes.Structure):
        _fields_ = [('process', handle), ('thread', handle), ('pid', dword), ('tid', dword)]

    kernel = ctypes.WinDLL('kernel32', use_last_error=True)
    kernel.CreateJobObjectW.argtypes = [ctypes.c_void_p, wintypes.LPCWSTR]
    kernel.CreateJobObjectW.restype = handle
    kernel.SetInformationJobObject.argtypes = [handle, dword, ctypes.c_void_p, dword]
    kernel.SetInformationJobObject.restype = boolean
    kernel.QueryInformationJobObject.argtypes = [handle, dword, ctypes.c_void_p, dword,
                                                 ctypes.POINTER(dword)]
    kernel.QueryInformationJobObject.restype = boolean
    kernel.CreateProcessW.argtypes = [wintypes.LPCWSTR, wintypes.LPWSTR, ctypes.c_void_p,
                                     ctypes.c_void_p, boolean, dword, ctypes.c_void_p,
                                     wintypes.LPCWSTR, ctypes.POINTER(StartupInfo),
                                     ctypes.POINTER(ProcessInfo)]
    kernel.CreateProcessW.restype = boolean
    kernel.AssignProcessToJobObject.argtypes = [handle, handle]
    kernel.AssignProcessToJobObject.restype = boolean
    kernel.ResumeThread.argtypes = [handle]
    kernel.ResumeThread.restype = dword
    kernel.WaitForSingleObject.argtypes = [handle, dword]
    kernel.WaitForSingleObject.restype = dword
    kernel.GetExitCodeProcess.argtypes = [handle, ctypes.POINTER(dword)]
    kernel.GetExitCodeProcess.restype = boolean
    kernel.TerminateJobObject.argtypes = [handle, dword]
    kernel.TerminateJobObject.restype = boolean
    kernel.TerminateProcess.argtypes = [handle, dword]
    kernel.TerminateProcess.restype = boolean
    kernel.CloseHandle.argtypes = [handle]
    kernel.CloseHandle.restype = boolean

    def failure(action):
        return ContainmentUncertain(f'{action} failed (Windows error {ctypes.get_last_error()})')

    job = kernel.CreateJobObjectW(None, None)
    if not job:
        raise ContainmentUnavailable(f'Cannot create job (Windows error {ctypes.get_last_error()})')
    process = ProcessInfo()
    assigned = False
    try:
        limits = ExtendedLimit()
        limits.basic.flags = 0x00002000  # JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE; no breakaway flags.
        if not kernel.SetInformationJobObject(job, 9, ctypes.byref(limits), ctypes.sizeof(limits)):
            raise ContainmentUnavailable(f'Cannot configure job (Windows error {ctypes.get_last_error()})')
        startup = StartupInfo()
        startup.cb = ctypes.sizeof(startup)
        command = ctypes.create_unicode_buffer(subprocess.list2cmdline(argv))
        environment = (None if environment_block is None
                       else ctypes.create_unicode_buffer(environment_block))
        flags = 0x00000004 | (0x00000400 if environment is not None else 0)
        environment_ptr = (None if environment is None
                           else ctypes.cast(environment, ctypes.c_void_p))
        if not kernel.CreateProcessW(argv[0], command, None, None, False, flags,
                                     environment_ptr, str(directory), ctypes.byref(startup), ctypes.byref(process)):
            raise ContainmentUnavailable(f'Cannot create suspended child (Windows error {ctypes.get_last_error()})')
        if not kernel.AssignProcessToJobObject(job, process.process):
            raise failure('Assigning suspended child to job')
        assigned = True
        if kernel.ResumeThread(process.thread) == 0xFFFFFFFF:
            raise failure('Resuming contained child')

        deadline = time.monotonic() + timeout
        exit_code = None
        timed_out = False
        while True:
            if exit_code is None:
                wait = kernel.WaitForSingleObject(process.process, 0)
                if wait == 0:
                    code = dword()
                    if not kernel.GetExitCodeProcess(process.process, ctypes.byref(code)):
                        raise failure('Reading child exit code')
                    exit_code = int(code.value)
                elif wait != 0x00000102:
                    raise failure('Waiting for child')
            accounting = Accounting()
            if not kernel.QueryInformationJobObject(job, 1, ctypes.byref(accounting),
                                                    ctypes.sizeof(accounting), None):
                raise failure('Inspecting contained process tree')
            if exit_code is not None and accounting.active_processes == 0:
                return ContainedResult(exit_code, timed_out)
            if time.monotonic() >= deadline:
                timed_out = True
                if not kernel.TerminateJobObject(job, 1):
                    raise failure('Terminating timed-out job')
                cleanup_deadline = time.monotonic() + 10
                while time.monotonic() < cleanup_deadline:
                    accounting = Accounting()
                    if not kernel.QueryInformationJobObject(job, 1, ctypes.byref(accounting),
                                                            ctypes.sizeof(accounting), None):
                        raise failure('Inspecting terminated job')
                    if accounting.active_processes == 0:
                        return ContainedResult(None, True)
                    time.sleep(0.02)
                raise ContainmentUncertain('Timed-out job did not become empty')
            time.sleep(0.02)
    finally:
        if process.process and not assigned:
            # The unassigned child has never been resumed.
            kernel.TerminateProcess(process.process, 1)
            kernel.WaitForSingleObject(process.process, 10000)
        if process.thread:
            kernel.CloseHandle(process.thread)
        if process.process:
            kernel.CloseHandle(process.process)
        kernel.CloseHandle(job)  # Kills contained descendants if the caller exits early.
