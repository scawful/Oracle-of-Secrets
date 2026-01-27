#!/usr/bin/env python3
"""Deprecated wrapper; use mesen2_client.py agent."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
ENTRYPOINT = SCRIPT_DIR / "mesen2_client.py"


def main() -> int:
    if os.getenv("MESEN_AGENT_NO_WARN") is None:
        print("mesen_agent.py is deprecated; use: ./scripts/mesen2_client.py agent ...", file=sys.stderr)
    cmd = [sys.executable, str(ENTRYPOINT), "agent", *sys.argv[1:]]
    return subprocess.call(cmd)


if __name__ == "__main__":
    raise SystemExit(main())
