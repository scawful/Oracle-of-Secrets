#!/usr/bin/env python3
"""Capture overworld checkpoint states for Oracle of Secrets testing.

This script helps create a comprehensive library of overworld save states
for regression testing of area transitions, camera behavior, and more.

Usage:
    # Check current position and suggest checkpoint name
    ./scripts/capture_overworld_states.py check

    # Capture state at current position
    ./scripts/capture_overworld_states.py capture --name "lost_woods_entrance"

    # List all required checkpoints
    ./scripts/capture_overworld_states.py list-required

    # Interactive mode - guide through capturing all checkpoints
    ./scripts/capture_overworld_states.py interactive
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime
from pathlib import Path

# Try to import bridge
try:
    from mesen2_client_lib.bridge import MesenBridge
    HAS_BRIDGE = True
except ImportError:
    HAS_BRIDGE = False

REPO_ROOT = Path(__file__).resolve().parents[1]
SAVESTATE_DIR = REPO_ROOT / "Roms" / "SaveStates" / "oos168x" / "overworld"
MANIFEST_PATH = REPO_ROOT / "Docs" / "Debugging" / "Testing" / "save_state_library.json"
MESEN2_CLIENT = REPO_ROOT / "scripts" / "mesen2_client.py"

# Overworld area definitions
AREA_NAMES = {
    0x00: "Light World - Northwest",
    0x01: "Light World - North",
    0x02: "Death Mountain West",
    0x03: "Death Mountain East",
    0x05: "Kakariko Village",
    0x07: "Lake Hylia North",
    0x0F: "Hyrule Castle",
    0x18: "Kakariko Village",
    0x1A: "Haunted Grove",
    0x1B: "Link's House",
    0x21: "Lost Woods North",
    0x22: "Sanctuary Area",
    0x23: "Village Area",  # Where Lost Woods exits to
    0x28: "Lost Woods West",
    0x29: "Lost Woods Center",
    0x2A: "Lost Woods East",
    0x31: "Lost Woods South",
    0x3A: "Graveyard",
    0x40: "Dark World - Pyramid",
    0x43: "Dark World - Village",
    0x5B: "Dark World - Pyramid BG",
}

# Required checkpoint states for comprehensive testing
REQUIRED_CHECKPOINTS = [
    {
        "id": "ow_lost_woods_entrance",
        "area": 0x29,
        "description": "Lost Woods center - puzzle testing",
        "tags": ["overworld", "lost-woods", "puzzle", "transition"],
        "notes": "Central Lost Woods area for puzzle sequence testing",
        "priority": "high"
    },
    {
        "id": "ow_lost_woods_east_exit",
        "area": 0x2A,
        "description": "Lost Woods east exit - boundary testing",
        "tags": ["overworld", "lost-woods", "transition", "small-map"],
        "notes": "Exit from Lost Woods, tests small-to-large transition",
        "priority": "high"
    },
    {
        "id": "ow_village_west",
        "area": 0x23,
        "description": "Village area west - near Lost Woods boundary",
        "tags": ["overworld", "village", "transition", "large-map"],
        "notes": "Large map area adjacent to Lost Woods for transition testing",
        "priority": "high"
    },
    {
        "id": "ow_sanctuary",
        "area": 0x22,
        "description": "Sanctuary area",
        "tags": ["overworld", "sanctuary", "early-game"],
        "notes": "Common early game area with indoor entrance",
        "priority": "medium"
    },
    {
        "id": "ow_links_house",
        "area": 0x1B,
        "description": "Link's House area",
        "tags": ["overworld", "start", "indoor-entrance"],
        "notes": "Starting area with indoor transition",
        "priority": "medium"
    },
    {
        "id": "ow_kakariko_entrance",
        "area": 0x18,
        "description": "Kakariko Village entrance",
        "tags": ["overworld", "village", "transition"],
        "notes": "Village with multiple indoor entrances",
        "priority": "medium"
    },
    {
        "id": "ow_graveyard",
        "area": 0x3A,
        "description": "Graveyard area",
        "tags": ["overworld", "graveyard", "dungeon-entrance"],
        "notes": "Access to graveyard dungeon",
        "priority": "medium"
    },
    {
        "id": "ow_pyramid_dw",
        "area": 0x40,
        "description": "Dark World Pyramid",
        "tags": ["overworld", "dark-world", "pyramid"],
        "notes": "Dark World starting area",
        "priority": "medium"
    },
    {
        "id": "ow_death_mountain",
        "area": 0x03,
        "description": "Death Mountain",
        "tags": ["overworld", "mountain", "hazards"],
        "notes": "Mountain area with falling rocks",
        "priority": "low"
    },
    {
        "id": "ow_lake_hylia",
        "area": 0x07,
        "description": "Lake Hylia",
        "tags": ["overworld", "water", "swimming"],
        "notes": "Water area for swimming tests",
        "priority": "low"
    }
]


def get_bridge():
    """Get Mesen2 bridge connection."""
    if not HAS_BRIDGE:
        print("ERROR: mesen2_client_lib not available")
        print("Make sure you're running from the oracle-of-secrets directory")
        sys.exit(1)

    bridge = MesenBridge()
    if not bridge.is_connected():
        print("ERROR: Not connected to Mesen2")
        print("Start Mesen2 with socket server enabled:")
        print("  mesen-agent launch oos")
        print("  # or isolated:")
        print("  ./scripts/mesen2_launch_instance.sh --instance oos-overworld-capture --owner you --source manual")
        sys.exit(1)

    return bridge


def get_current_state(bridge):
    """Read current game state from Mesen2."""
    return {
        "area": bridge.read_memory(0x7E008A),
        "mode": bridge.read_memory(0x7E0010),
        "submode": bridge.read_memory(0x7E0011),
        "link_x": bridge.read_memory16(0x7E0022),
        "link_y": bridge.read_memory16(0x7E0020),
        "indoors": bridge.read_memory(0x7E001B),
        "scroll_x": bridge.read_memory16(0x7E00E1) | (bridge.read_memory(0x7E00E3) << 8),
        "scroll_y": bridge.read_memory16(0x7E00E7) | (bridge.read_memory(0x7E00E9) << 8),
    }


def print_state(state):
    """Pretty print game state."""
    area = state["area"]
    area_name = AREA_NAMES.get(area, "Unknown")

    print(f"\n{'='*50}")
    print(f"Current Position")
    print(f"{'='*50}")
    print(f"  Area:    0x{area:02X} ({area_name})")
    print(f"  Mode:    0x{state['mode']:02X} ({'Overworld' if state['mode'] == 0x09 else 'Other'})")
    print(f"  Indoors: {'Yes' if state['indoors'] else 'No'}")
    print(f"  Link:    ({state['link_x']}, {state['link_y']})")
    print(f"  Scroll:  ({state['scroll_x']}, {state['scroll_y']})")

    # Suggest checkpoint
    for cp in REQUIRED_CHECKPOINTS:
        if cp["area"] == area:
            print(f"\n  Suggested checkpoint: {cp['id']}")
            print(f"  Description: {cp['description']}")
            break


def cmd_check(args):
    """Check current position."""
    bridge = get_bridge()
    state = get_current_state(bridge)
    print_state(state)


def cmd_list_required(args):
    """List all required checkpoints."""
    print("\nRequired Overworld Checkpoints:")
    print("="*60)

    # Check which already exist
    existing = set()
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        for entry in manifest.get("entries", []):
            label = (entry.get("label") or "").strip()
            tags = set(entry.get("tags") or [])
            # Consider a checkpoint captured if its canonical id appears as a label or tag.
            if label:
                existing.add(label)
            for t in tags:
                existing.add(str(t))

    for cp in REQUIRED_CHECKPOINTS:
        status = "[EXISTS]" if cp["id"] in existing else "[NEEDED]"
        priority = cp["priority"].upper()
        print(f"\n{status} {cp['id']} [{priority}]")
        print(f"  Area: 0x{cp['area']:02X} - {AREA_NAMES.get(cp['area'], 'Unknown')}")
        print(f"  {cp['description']}")
        print(f"  Tags: {', '.join(cp['tags'])}")


def cmd_capture(args):
    """Capture current state as checkpoint."""
    bridge = get_bridge()
    state = get_current_state(bridge)

    if state["mode"] != 0x09:
        print("ERROR: Must be in Overworld mode (0x09) to capture overworld checkpoint")
        sys.exit(1)

    if state["indoors"]:
        print("ERROR: Must be outdoors to capture overworld checkpoint")
        sys.exit(1)

    # Find matching checkpoint definition or use provided name
    checkpoint_def = None
    for cp in REQUIRED_CHECKPOINTS:
        if cp["area"] == state["area"]:
            checkpoint_def = cp
            break

    state_id = args.name
    if not state_id and checkpoint_def:
        state_id = checkpoint_def["id"]

    if not state_id:
        state_id = f"ow_area_{state['area']:02x}"

    print(f"\nCapturing checkpoint: {state_id}")
    print_state(state)

    if not MESEN2_CLIENT.exists():
        print("ERROR: scripts/mesen2_client.py not found")
        sys.exit(1)

    if getattr(args, "slot", None) is not None:
        print("NOTE: --slot is deprecated; this script now saves directly to the state library.")

    # Create metadata JSON
    metadata = {
        "name": checkpoint_def["description"] if checkpoint_def else f"Area 0x{state['area']:02X}",
        "description": checkpoint_def["notes"] if checkpoint_def else "",
        "category": "overworld",
        "tags": checkpoint_def["tags"] if checkpoint_def else ["overworld", f"area-{state['area']:02x}"],
        "created": datetime.now().isoformat(),
        "romVersion": "oos168x",
        "gameState": {
            "mode": state["mode"],
            "modeDesc": "Overworld",
            "submode": state["submode"],
            "roomId": f"0x{state['area']:02X}",
            "overworldArea": f"0x{state['area']:02X}",
            "indoors": False
        },
        "linkState": {
            "x": state["link_x"],
            "y": state["link_y"],
        },
    }

    tags = list(dict.fromkeys(["overworld", state_id] + (metadata.get("tags") or [])))

    print("\nSaving to state library...")
    cmd = [sys.executable, str(MESEN2_CLIENT), "lib-save", state_id, "--captured-by", "human", "--json"]
    for t in tags:
        cmd += ["-t", str(t)]
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT)
    if result.returncode != 0:
        err = result.stderr.strip() or result.stdout.strip()
        print(f"ERROR: lib-save failed: {err}")
        sys.exit(1)

    entry_id = None
    try:
        out = json.loads(result.stdout)
        entry_id = out.get("id") or out.get("entry", {}).get("id")
    except Exception:
        pass

    if entry_id:
        print(f"Saved: {entry_id}")
    else:
        print("Saved (see library list for id).")
    print("\nNext:")
    print("  MESEN2_AUTO_ATTACH=1 python3 scripts/mesen2_client.py library")


def cmd_interactive(args):
    """Interactive mode to capture all required checkpoints."""
    print("\nInteractive Checkpoint Capture")
    print("="*60)
    print("\nThis will guide you through capturing all required checkpoints.")
    print("Navigate to each location in Mesen2, then press Enter to capture.\n")

    for cp in REQUIRED_CHECKPOINTS:
        if cp["priority"] == "low" and not args.include_low:
            continue

        area_name = AREA_NAMES.get(cp["area"], "Unknown")
        print(f"\n{'='*60}")
        print(f"Checkpoint: {cp['id']}")
        print(f"Area: 0x{cp['area']:02X} ({area_name})")
        print(f"Description: {cp['description']}")
        print(f"Notes: {cp['notes']}")
        print(f"\nNavigate to this location and press Enter (or 's' to skip)...")

        response = input().strip().lower()
        if response == 's':
            print("Skipped.")
            continue

        try:
            # Create namespace for capture
            class CaptureArgs:
                name = cp["id"]
                slot = 10

            cmd_capture(CaptureArgs())
        except SystemExit:
            print("Failed to capture, continuing...")


def main():
    parser = argparse.ArgumentParser(description="Capture overworld checkpoint states")
    sub = parser.add_subparsers(dest="command", required=True)

    check_cmd = sub.add_parser("check", help="Check current position")
    check_cmd.set_defaults(func=cmd_check)

    list_cmd = sub.add_parser("list-required", help="List required checkpoints")
    list_cmd.set_defaults(func=cmd_list_required)

    capture_cmd = sub.add_parser("capture", help="Capture current state")
    capture_cmd.add_argument("--name", help="Checkpoint name/id")
    capture_cmd.add_argument("--slot", type=int, default=None, help="(deprecated) Save slot (no longer used)")
    capture_cmd.set_defaults(func=cmd_capture)

    interactive_cmd = sub.add_parser("interactive", help="Interactive capture mode")
    interactive_cmd.add_argument("--include-low", action="store_true", help="Include low priority checkpoints")
    interactive_cmd.set_defaults(func=cmd_interactive)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
