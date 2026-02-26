#!/usr/bin/env python3
"""Wait for Link to be in a specific dungeon room, then save and pin a state.

Usage:
    python3 scripts/capture_dungeon_state.py \
        --room 0x98 \
        --output Roms/SaveStates/library/oos168x/inside_d6.mss \
        [--instance smoke-test] \
        [--rom Roms/oos168x.sfc] \
        [--timeout 300]

Polls Mesen2 until Link is indoors and in --room, then saves the state to
--output and runs z3ed mesen-state-regen to pin fresh SHA1 metadata.

Typical workflow:
  1. Load pre_d6_entrance.mss in Mesen2 (or the script can do it for you
     with --load-state).
  2. Walk into the dungeon manually (or via another save state).
  3. Run this script.  It waits, prints live position, and fires once the
     target room is stable for a few frames.
  4. Check the printed sha1s — they are what mesen-state-verify will gate on.
"""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.mesen2_client_lib.client import OracleDebugClient


REPO_ROOT = Path(__file__).parent.parent
DEFAULT_ROM = str(REPO_ROOT / "Roms" / "oos168x.sfc")
Z3ED = str(Path.home() / "src/hobby/yaze/build/bin/Debug/z3ed")
STABLE_FRAMES = 8   # room must read the same value this many polls in a row
POLL_INTERVAL = 1 / 15  # seconds between polls (~15 Hz)


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--room", default="0x98",
                   help="Target room ID in hex (default: 0x98)")
    p.add_argument("--output", required=True,
                   help="Path to write the .mss save state")
    p.add_argument("--instance", default="smoke-test",
                   help="Mesen2 instance name (used to find socket)")
    p.add_argument("--rom", default=DEFAULT_ROM,
                   help="ROM path for mesen-state-regen")
    p.add_argument("--timeout", type=int, default=300,
                   help="Seconds to wait before giving up (default: 300)")
    p.add_argument("--load-state",
                   help="Optional: load this save state before waiting")
    return p.parse_args()


def regen_meta(z3ed: str, state_path: str, rom: str) -> bool:
    result = subprocess.run(
        [z3ed, "mesen-state-regen", "--state", state_path, "--rom-file", rom],
        capture_output=True, text=True, timeout=15,
    )
    if result.returncode != 0:
        print(f"  [regen] FAILED: {result.stderr.strip()}")
        return False
    import json
    try:
        meta = json.loads(result.stdout)
        print(f"  [regen] state_sha1 = {meta.get('state_sha1', '?')}")
        print(f"  [regen] rom_sha1   = {meta.get('rom_sha1', '?')}")
    except Exception:
        print(f"  [regen] {result.stdout.strip()}")
    return True


def main() -> int:
    args = parse_args()
    target_room = int(args.room, 16)
    output = Path(os.path.abspath(args.output))
    rom = os.path.abspath(args.rom)

    sock_env = os.environ.get("MESEN2_SOCKET_PATH")
    sock = sock_env or f"/tmp/mesen2-{args.instance}.sock"

    if not Path(sock).exists():
        print(f"[ERROR] Mesen2 socket not found: {sock}")
        print("  Set MESEN2_SOCKET_PATH or start Mesen2 with the right instance name.")
        return 1

    client = OracleDebugClient(sock)

    # Optional: pre-load a save state
    if args.load_state:
        print(f"Loading {Path(args.load_state).name} ...")
        ok = client.bridge.load_state(path=args.load_state)
        if not ok:
            print("  [ERROR] Failed to load state")
            return 1
        time.sleep(0.5)

    print(f"Waiting for room 0x{target_room:02X} (timeout {args.timeout}s) ...")
    print("  Walk into the dungeon in Mesen2 now.\n")

    deadline = time.monotonic() + args.timeout
    stable_count = 0
    last_room = None
    last_print_room = None

    while time.monotonic() < deadline:
        try:
            state = client.get_oracle_state()
        except Exception as exc:
            print(f"  [poll error] {exc}")
            time.sleep(1)
            stable_count = 0
            continue

        room = state.get("dungeon_room", 0) & 0xFF
        indoors = bool(state.get("indoors"))
        mode = state.get("mode_name", "?")

        # Print whenever room changes
        if room != last_print_room:
            lx = state.get("link_x", 0)
            ly = state.get("link_y", 0)
            print(f"  {mode} | room=0x{room:02X} | "
                  f"link=({lx},{ly}) | indoors={indoors}")
            last_print_room = room

        if indoors and room == target_room:
            stable_count = stable_count + 1 if room == last_room else 1
            if stable_count >= STABLE_FRAMES:
                break
        else:
            stable_count = 0

        last_room = room
        time.sleep(POLL_INTERVAL)
    else:
        print(f"\n[TIMEOUT] Never reached room 0x{target_room:02X} within {args.timeout}s.")
        return 1

    # ------------------------------------------------------------------ #
    # Capture
    # ------------------------------------------------------------------ #
    print(f"\nRoom 0x{target_room:02X} stable — saving state ...")
    output.parent.mkdir(parents=True, exist_ok=True)

    ok = client.bridge.save_state(path=str(output))
    if not ok:
        print(f"  [ERROR] SAVESTATE failed")
        return 1
    print(f"  Saved  → {output}")

    # Verify the file was actually written
    if not output.exists():
        print("  [ERROR] State file not found after save")
        return 1
    print(f"  Size   = {output.stat().st_size:,} bytes")

    # Pin metadata
    print("  Pinning SHA1 metadata ...")
    if not regen_meta(Z3ED, str(output), rom):
        print("  [WARN] Metadata regen failed — run mesen-state-regen manually.")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
