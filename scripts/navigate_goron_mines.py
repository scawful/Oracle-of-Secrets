#!/usr/bin/env python3
"""Navigate to Goron Mines minecart rooms and capture screenshots.

Usage:
    python3 scripts/navigate_goron_mines.py \
        --instance smoke-test \
        --rom Roms/oos168x.sfc \
        [--save-state Roms/SaveStates/library/oos168x/inside_d6.mss] \
        [--target-rooms 0xA8,0xD8,0xDA]

Navigates to each target room, waits for the room to settle, and
captures a dungeon-render PNG + live screenshot for comparison.
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.mesen2_client_lib.bridge import MesenBridge
from scripts.mesen2_client_lib.client import OracleDebugClient
from scripts.mesen2_client_lib.constants import OracleRAM
from scripts.mesen2_client_lib.dungeon_navigator import DungeonNavigator


REPO_ROOT = Path(__file__).parent.parent
DEFAULT_ROM = str(REPO_ROOT / "Roms" / "oos168x.sfc")
DEFAULT_SAVE_STATE = str(
    REPO_ROOT / "Roms" / "SaveStates" / "library" / "oos168x" / "inside_d6.mss"
)
DEFAULT_TARGETS = [0xA8, 0xD8, 0xDA]
GORON_MINES_ENTRANCE = 0x27
Z3ED = str(Path.home() / "src/hobby/yaze/build/bin/Debug/z3ed")
OUTPUT_DIR = REPO_ROOT / "Roms" / "Screenshots" / "minecart_smoke"


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--instance", default="smoke-test", help="Mesen2 instance name")
    p.add_argument("--rom", default=DEFAULT_ROM)
    p.add_argument("--save-state", default=DEFAULT_SAVE_STATE)
    p.add_argument(
        "--target-rooms",
        default=",".join(f"0x{r:02X}" for r in DEFAULT_TARGETS),
        help="Comma-separated hex room IDs to visit",
    )
    p.add_argument("--no-navigate", action="store_true",
                   help="Skip navigation, just render each room statically")
    return p.parse_args()


def render_room(z3ed: str, rom: str, room_id: int, output_path: Path) -> bool:
    """Render a dungeon room to PNG using dungeon-render."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run(
        [
            z3ed, "--rom", rom,
            "dungeon-render",
            f"--room=0x{room_id:02X}",
            f"--output={output_path}",
            "--overlays=track,sprites",
            "--scale=2",
        ],
        capture_output=True, text=True, timeout=30,
    )
    if result.returncode != 0:
        print(f"  [render] FAILED: {result.stderr.strip()}")
        return False
    print(f"  [render] → {output_path.name}")
    return True


def main() -> int:
    args = parse_args()

    target_rooms = [int(r, 16) for r in args.target_rooms.split(",")]
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Target rooms: {[f'0x{r:02X}' for r in target_rooms]}")
    print(f"ROM: {args.rom}")

    # --- Static renders (always done) ---
    print("\n=== Static dungeon-render ===")
    for room_id in target_rooms:
        out = OUTPUT_DIR / f"room_{room_id:02X}_static.png"
        render_room(Z3ED, args.rom, room_id, out)

    if args.no_navigate:
        print("\nSkipping live navigation (--no-navigate).")
        return 0

    # --- Live navigation ---
    sock = f"/tmp/mesen2-{args.instance}.sock"
    if not Path(sock).exists():
        print(f"\n[SKIP] Mesen2 socket not found at {sock}.")
        print("  Start Mesen2 with: bash scripts/mesen2_launch_instance.sh ...")
        return 0

    print(f"\n=== Live navigation via {sock} ===")
    bridge = MesenBridge(sock)
    client = OracleDebugClient(bridge)

    # Health check
    try:
        health = bridge.send_command("HEALTH", {})
        print(f"  Mesen2 health: {health.get('status', '?')}")
    except Exception as exc:
        print(f"  [ERROR] Cannot reach Mesen2: {exc}")
        return 1

    # Load save state
    print(f"  Loading save state: {Path(args.save_state).name}")
    try:
        bridge.send_command("LOAD_STATE", {"path": str(args.save_state)})
        time.sleep(0.5)
    except Exception as exc:
        print(f"  [ERROR] Failed to load save state: {exc}")
        return 1

    # Build navigation graph
    nav = DungeonNavigator(
        client=client,
        rom_path=args.rom,
        entrance_id=GORON_MINES_ENTRANCE,
        z3ed_path=Z3ED,
    )
    nav.build_graph(same_blockset=True)

    # Visit each target room
    for room_id in target_rooms:
        print(f"\n--- Room 0x{room_id:02X} ---")

        # Reload save state to start fresh from entrance each time
        bridge.send_command("LOAD_STATE", {"path": str(args.save_state)})
        time.sleep(0.5)

        current = nav._read_room_id()
        print(f"  Start room: 0x{current:02X}")

        ok = nav.go_to_room(room_id)
        if not ok:
            print(f"  [FAIL] Could not navigate to 0x{room_id:02X}")
            continue

        # Short settle pause
        time.sleep(0.3)

        # Capture state
        state = client.get_oracle_state()
        print(f"  Mode: {state.get('mode_name')}, Room: 0x{state.get('dungeon_room', 0):02X}")
        link_x = state.get("link_x", 0)
        link_y = state.get("link_y", 0)
        print(f"  Link: ({link_x}, {link_y})")

        # Screenshot
        out = OUTPUT_DIR / f"room_{room_id:02X}_live.png"
        try:
            bridge.send_command("SCREENSHOT", {"path": str(out)})
            print(f"  [screenshot] → {out.name}")
        except Exception as exc:
            print(f"  [screenshot] FAILED: {exc}")

    print("\nDone.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
