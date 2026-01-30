#!/usr/bin/env python3
"""Bisect runner for overworld softlock: build, load state 1, run N frames, report good/bad.

For use with git bisect run:
  cd ~/src/hobby/oracle-of-secrets
  git bisect start HEAD <last-known-good-commit>
  git bisect run python3 scripts/bisect_softlock.py

Requires Mesen2 running with ROM loaded and socket available (MESEN2_SOCKET_PATH or
single /tmp/mesen2-*.sock). After each bisect step the script builds the ROM; you must
reload the ROM in Mesen2 (or use a launcher that auto-reloads) before the next run.

Exit 0 = good (no softlock), exit 1 = bad (softlock/corruption detected).
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Add scripts/ so we can import mesen2_client_lib
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

# Game mode $7E0010; if 0 = reset/dead/black screen
MODE_ADDR = 0x7E0010
# PC where corruption manifests (invalid JSL $1D66CC)
INVALID_PC = 0x83A66D
DEFAULT_SLOT = 1
DEFAULT_FRAMES = 600


def main() -> int:
    parser = argparse.ArgumentParser(description="Bisect runner for overworld softlock")
    parser.add_argument("--no-build", action="store_true", help="Skip build (ROM already built)")
    parser.add_argument("--slot", type=int, default=DEFAULT_SLOT, help="Save state slot (default 1)")
    parser.add_argument("--frames", type=int, default=DEFAULT_FRAMES, help="Frames to run (default 600)")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    os.chdir(REPO_ROOT)

    if not args.no_build:
        if args.verbose:
            print("Building ROM...")
        r = subprocess.run(
            ["./scripts/build_rom.sh", "168"],
            cwd=REPO_ROOT,
            capture_output=not args.verbose,
            timeout=120,
        )
        if r.returncode != 0:
            if not args.verbose:
                print(r.stderr.decode() if r.stderr else "Build failed")
            return 125  # bisect skip: build failed

    try:
        from mesen2_client_lib.bridge import MesenBridge
    except ImportError:
        print("mesen2_client_lib not found", file=sys.stderr)
        return 125

    bridge = MesenBridge()
    if not bridge.ensure_connected():
        print("Mesen2 socket not found. Start Mesen2 with ROM loaded and socket enabled.", file=sys.stderr)
        return 125

    if args.verbose:
        print(f"Loading state slot {args.slot}...")
    if not bridge.load_state(slot=args.slot):
        print("Load state failed", file=sys.stderr)
        return 125

    if args.verbose:
        print(f"Running {args.frames} frames...")
    if not bridge.run_frames(count=args.frames):
        print("Run frames failed", file=sys.stderr)
        return 125

    mode = bridge.read_memory(MODE_ADDR)
    cpu = bridge.get_cpu_state()
    pc_str = cpu.get("pc", "0x0")
    try:
        pc = int(pc_str.replace("0x", "").replace("0X", ""), 16)
    except (ValueError, TypeError):
        pc = 0

    if mode == 0:
        if args.verbose:
            print(f"BAD: mode=$7E0010=0 (softlock/reset)")
        return 1
    if pc == INVALID_PC:
        if args.verbose:
            print(f"BAD: PC=0x83A66D (corruption site)")
        return 1
    if mode >= 32:
        if args.verbose:
            print(f"BAD: mode={mode} (corrupted, expected 0x00-0x1F)")
        return 1

    if args.verbose:
        print(f"GOOD: mode=0x{mode:02X}, PC=0x{pc:06X}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
