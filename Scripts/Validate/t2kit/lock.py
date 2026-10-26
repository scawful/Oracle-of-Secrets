"""Heavy lock for one native episode, through the shared Scripts/Agents/heavy_lock.py.

Board rule: native runs take /tmp/oos-heavy.lock through heavy_lock.py (never
mkdir/rm by hand) and release between episodes.
"""
from __future__ import annotations

import importlib.util
import os
import sys
from contextlib import contextmanager
from pathlib import Path

HEAVY_LOCK = Path(__file__).resolve().parents[2] / 'Agents' / 'heavy_lock.py'


class LockTimeout(RuntimeError):
    pass


def heavy_lock_module():
    if 'heavy_lock' in sys.modules:
        return sys.modules['heavy_lock']
    spec = importlib.util.spec_from_file_location('heavy_lock', HEAVY_LOCK)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@contextmanager
def heavy_lock(owner: str, purpose: str, wait: float = 3600, poll: float = 30, log=None):
    """Hold the heavy lock for this process; wait up to `wait` s; always release."""
    hl = heavy_lock_module()
    token = hl.acquire(owner, purpose, pid=os.getpid(), wait=wait, poll=poll, log=log)
    if token is None:
        st = hl.status()
        raise LockTimeout(f'heavy lock not free after {wait:.0f} s: {st["reason"]} {st["owner"]}')
    try:
        yield token
    finally:
        hl.release(token)
