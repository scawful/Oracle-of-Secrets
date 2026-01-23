#!/usr/bin/env python3
"""Unified save state capture tool for Oracle of Secrets testing.

Supports capturing states for all categories: overworld, dungeons, bosses, events, items.

Usage:
    # Check current position and suggest checkpoint
    ./scripts/capture_state.py check

    # List all required checkpoints (all categories)
    ./scripts/capture_state.py list-required

    # List required checkpoints for specific category
    ./scripts/capture_state.py list-required --category dungeons

    # Capture state at current position
    ./scripts/capture_state.py capture --name "lost_woods_entrance"

    # Capture with auto-detect category
    ./scripts/capture_state.py capture --auto

    # Interactive mode - guide through capturing checkpoints
    ./scripts/capture_state.py interactive --category overworld
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
SAVESTATE_ROOT = REPO_ROOT / "Roms" / "SaveStates" / "oos168x"
SAVESTATE_SHARED = REPO_ROOT / "Roms" / "SaveStates"  # Shared metadata location
MANIFEST_PATH = REPO_ROOT / "Docs" / "Testing" / "save_state_library.json"

CATEGORIES = ["overworld", "dungeons", "bosses", "events", "items"]

# Game mode descriptions
MODE_NAMES = {
    0x00: "Title Screen",
    0x07: "Dungeon",
    0x09: "Overworld",
    0x0E: "Cutscene/Menu",
    0x14: "Messaging",
    0x19: "Victory/Item Get",
    0x23: "World Transition",
}


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
        print("  ./scripts/mesen_launch.sh")
        sys.exit(1)

    return bridge


def get_current_state(bridge):
    """Read current game state from Mesen2."""
    # Oracle RAM addresses
    LINK_FORM = 0x7E02B2  # 0=normal, 3=wolf, 5=minish, 6=GBC Link
    TIME_HOURS = 0x7EE000
    TIME_MINUTES = 0x7EE001
    TIME_SPEED = 0x7EE002
    HEALTH_CURRENT = 0x7EF36D
    HEALTH_MAX = 0x7EF36C
    MAGIC_POWER = 0x7EF36E
    RUPEES = 0x7EF360
    GAME_STATE = 0x7EF3C5
    OOSPROG = 0x7EF3D6
    CRYSTALS = 0x7EF37A

    link_form = bridge.read_memory(LINK_FORM)
    form_names = {0x00: "Normal", 0x03: "Wolf", 0x05: "Minish", 0x06: "GBC Link"}

    return {
        # Core game state
        "area": bridge.read_memory(0x7E008A),
        "room": bridge.read_memory(0x7E00A0),
        "mode": bridge.read_memory(0x7E0010),
        "submode": bridge.read_memory(0x7E0011),
        "indoors": bridge.read_memory(0x7E001B),
        "dungeon_id": bridge.read_memory(0x7E040C),
        # Link position
        "link_x": bridge.read_memory16(0x7E0022),
        "link_y": bridge.read_memory16(0x7E0020),
        "link_dir": bridge.read_memory(0x7E002F),
        "link_state": bridge.read_memory(0x7E005D),
        # Link form (Oracle custom)
        "link_form": link_form,
        "link_form_name": form_names.get(link_form, f"Unknown (0x{link_form:02X})"),
        # Scroll registers
        "scroll_x": bridge.read_memory16(0x7E00E1) | (bridge.read_memory(0x7E00E3) << 8),
        "scroll_y": bridge.read_memory16(0x7E00E7) | (bridge.read_memory(0x7E00E9) << 8),
        # Time system (Oracle custom)
        "time_hours": bridge.read_memory(TIME_HOURS),
        "time_minutes": bridge.read_memory(TIME_MINUTES),
        "time_speed": bridge.read_memory(TIME_SPEED),
        # Player stats
        "health": bridge.read_memory(HEALTH_CURRENT),
        "max_health": bridge.read_memory(HEALTH_MAX),
        "magic": bridge.read_memory(MAGIC_POWER),
        "rupees": bridge.read_memory16(RUPEES),
        # Story progress
        "game_state": bridge.read_memory(GAME_STATE),
        "oosprog": bridge.read_memory(OOSPROG),
        "crystals": bridge.read_memory(CRYSTALS),
    }


def detect_category(state):
    """Auto-detect state category based on game state."""
    mode = state["mode"]
    indoors = state["indoors"]

    if mode == 0x09 and not indoors:
        return "overworld"
    elif mode == 0x07 or indoors:
        # Check if in boss room (would need boss room list)
        return "dungeons"
    elif mode in (0x0E, 0x14, 0x19, 0x23):
        return "events"
    else:
        return "overworld"  # Default


def load_category_metadata(category):
    """Load required checkpoints from category metadata.

    Checks both oos168x subdirectory and shared metadata location.
    """
    # First check oos168x-specific location
    meta_path = SAVESTATE_ROOT / category / "metadata.json"
    if meta_path.exists():
        return json.loads(meta_path.read_text())

    # Fall back to shared metadata location
    shared_path = SAVESTATE_SHARED / category / "metadata.json"
    if shared_path.exists():
        return json.loads(shared_path.read_text())

    return {"requiredCheckpoints": [], "states": {}}


def load_all_checkpoints():
    """Load all required checkpoints from all categories."""
    all_checkpoints = []
    for category in CATEGORIES:
        meta = load_category_metadata(category)
        for cp in meta.get("requiredCheckpoints", []):
            cp["_category"] = category
            all_checkpoints.append(cp)
    return all_checkpoints


def print_state(state):
    """Pretty print game state."""
    mode = state["mode"]
    mode_name = MODE_NAMES.get(mode, "Unknown")

    print(f"\n{'='*50}")
    print(f"Current Position")
    print(f"{'='*50}")
    print(f"  Mode:      0x{mode:02X} ({mode_name})")
    print(f"  Area:      0x{state['area']:02X}")
    print(f"  Room:      0x{state['room']:02X}")
    print(f"  Dungeon:   0x{state['dungeon_id']:02X}")
    print(f"  Indoors:   {'Yes' if state['indoors'] else 'No'}")
    print(f"  Link:      ({state['link_x']}, {state['link_y']})")
    print(f"  Form:      {state['link_form_name']} (0x{state['link_form']:02X})")
    print(f"  Scroll:    ({state['scroll_x']}, {state['scroll_y']})")

    # Time system
    print(f"\n  Time:      {state['time_hours']:02d}:{state['time_minutes']:02d} (speed: {state['time_speed']})")

    # Player stats
    print(f"  Health:    {state['health']}/{state['max_health']}")
    print(f"  Magic:     {state['magic']}")
    print(f"  Rupees:    {state['rupees']}")

    # Story progress
    print(f"\n  GameState: {state['game_state']}")
    print(f"  OOSPROG:   0x{state['oosprog']:02X}")
    print(f"  Crystals:  0x{state['crystals']:02X}")

    category = detect_category(state)
    print(f"\n  Detected Category: {category}")


def cmd_check(args):
    """Check current position."""
    bridge = get_bridge()
    state = get_current_state(bridge)
    print_state(state)

    # Find matching checkpoint suggestions
    category = detect_category(state)
    meta = load_category_metadata(category)

    for cp in meta.get("requiredCheckpoints", []):
        # Match by area for overworld, room for dungeons
        if category == "overworld":
            if int(cp.get("area", "0x00"), 16) == state["area"]:
                print(f"\n  Suggested checkpoint: {cp['id']}")
                print(f"  Purpose: {cp['purpose']}")
                break
        elif category == "dungeons":
            if int(cp.get("roomId", "0x00"), 16) == state["room"]:
                print(f"\n  Suggested checkpoint: {cp['id']}")
                print(f"  Purpose: {cp['purpose']}")
                break


def cmd_list_required(args):
    """List all required checkpoints."""
    if args.category:
        categories = [args.category]
    else:
        categories = CATEGORIES

    # Check manifest for existing states
    existing = set()
    if MANIFEST_PATH.exists():
        manifest = json.loads(MANIFEST_PATH.read_text())
        for entry in manifest.get("entries", []):
            existing.add(entry.get("id"))

    total_needed = 0
    total_existing = 0

    for category in categories:
        meta = load_category_metadata(category)
        checkpoints = meta.get("requiredCheckpoints", [])

        if not checkpoints:
            continue

        print(f"\n{'='*60}")
        print(f"Category: {category.upper()}")
        print(f"{'='*60}")

        for cp in checkpoints:
            cp_id = cp["id"]
            status = "[EXISTS]" if cp_id in existing else "[NEEDED]"
            priority = cp.get("priority", "medium").upper()

            if status == "[NEEDED]":
                total_needed += 1
            else:
                total_existing += 1

            print(f"\n{status} {cp_id} [{priority}]")
            print(f"  {cp['purpose']}")
            if cp.get("tags"):
                print(f"  Tags: {', '.join(cp['tags'])}")

    print(f"\n{'='*60}")
    print(f"Summary: {total_existing} existing, {total_needed} needed")
    print(f"{'='*60}")


def cmd_capture(args):
    """Capture current state as checkpoint."""
    bridge = get_bridge()
    state = get_current_state(bridge)

    # Auto-detect or use provided category
    category = args.category or detect_category(state)

    print(f"\nCapturing checkpoint in category: {category}")
    print_state(state)

    # Find or create checkpoint ID
    state_id = args.name
    if not state_id:
        if args.auto:
            state_id = f"{category[:2]}_{state['mode']:02x}_{state['area']:02x}"
        else:
            print("ERROR: Must provide --name or use --auto")
            sys.exit(1)

    # Ensure category directory exists
    category_dir = SAVESTATE_ROOT / category
    category_dir.mkdir(parents=True, exist_ok=True)

    # Trigger save state
    slot = args.slot or 10
    print(f"\nSaving to slot {slot}...")

    cli_path = REPO_ROOT / "scripts" / "mesen_cli.sh"
    result = subprocess.run(
        [str(cli_path), "savestate", str(slot)],
        capture_output=True, text=True, cwd=REPO_ROOT
    )

    if result.returncode != 0:
        print(f"ERROR: Failed to save state: {result.stderr}")
        sys.exit(1)

    # Wait for save
    subprocess.run(
        [str(cli_path), "wait-save", "5"],
        capture_output=True, text=True, cwd=REPO_ROOT
    )

    # Create metadata
    metadata = {
        "name": state_id,
        "description": f"Captured at {category} position",
        "category": category,
        "tags": [category, f"area-{state['area']:02x}"],
        "created": datetime.now().isoformat(),
        "romVersion": "oos168x",
        "gameState": {
            "mode": f"0x{state['mode']:02X}",
            "modeDesc": MODE_NAMES.get(state["mode"], "Unknown"),
            "area": f"0x{state['area']:02X}",
            "room": f"0x{state['room']:02X}",
            "indoors": bool(state["indoors"]),
            "dungeonId": f"0x{state['dungeon_id']:02X}",
        },
        "linkState": {
            "x": state["link_x"],
            "y": state["link_y"],
            "direction": state["link_dir"],
            "state": state["link_state"],
            "form": state["link_form"],
            "formName": state["link_form_name"],
        },
        "scrollState": {
            "x": state["scroll_x"],
            "y": state["scroll_y"],
        },
        "timeState": {
            "hours": state["time_hours"],
            "minutes": state["time_minutes"],
            "speed": state["time_speed"],
        },
        "playerStats": {
            "health": state["health"],
            "maxHealth": state["max_health"],
            "magic": state["magic"],
            "rupees": state["rupees"],
        },
        "storyProgress": {
            "gameState": state["game_state"],
            "oosprog": f"0x{state['oosprog']:02X}",
            "crystals": f"0x{state['crystals']:02X}",
        },
    }

    # Save state file path
    state_path = category_dir / f"{state_id}.mss"
    meta_path = category_dir / f"{state_id}.json"

    # Move save state from slot to library
    # Note: Actual .mss file location depends on Mesen2 config
    # For now, save metadata and provide manual instructions

    meta_path.write_text(json.dumps(metadata, indent=2))

    print(f"\nMetadata saved to: {meta_path}")
    print(f"\nTo complete import:")
    print(f"  1. Find save state file from Mesen2 slot {slot}")
    print(f"  2. Copy to: {state_path}")
    print(f"  3. Run: python3 scripts/state_library.py import \\")
    print(f"       --id {state_id} \\")
    print(f"       --rom Roms/oos168x.sfc \\")
    print(f"       --slot {slot}")


def cmd_interactive(args):
    """Interactive mode to capture checkpoints."""
    category = args.category or "overworld"
    meta = load_category_metadata(category)
    checkpoints = meta.get("requiredCheckpoints", [])

    if not checkpoints:
        print(f"No checkpoints defined for category: {category}")
        return

    # Filter by priority
    if args.priority:
        checkpoints = [cp for cp in checkpoints if cp.get("priority") == args.priority]

    print(f"\nInteractive Checkpoint Capture: {category.upper()}")
    print("="*60)
    print(f"\nFound {len(checkpoints)} checkpoints to capture.")
    print("Navigate to each location in Mesen2, then press Enter to capture.\n")

    for cp in checkpoints:
        print(f"\n{'='*60}")
        print(f"Checkpoint: {cp['id']}")
        print(f"Purpose: {cp['purpose']}")
        if cp.get("conditions"):
            print(f"Conditions: {json.dumps(cp['conditions'], indent=2)}")
        print(f"\nNavigate to this location and press Enter (or 's' to skip)...")

        response = input().strip().lower()
        if response == 's':
            print("Skipped.")
            continue

        try:
            class CaptureArgs:
                name = cp["id"]
                category = category
                slot = 10
                auto = False

            cmd_capture(CaptureArgs())
        except SystemExit:
            print("Failed to capture, continuing...")


def cmd_sync(args):
    """Sync metadata between manifest and category files."""
    if not MANIFEST_PATH.exists():
        print("ERROR: Manifest not found")
        sys.exit(1)

    manifest = json.loads(MANIFEST_PATH.read_text())
    entries = manifest.get("entries", [])

    print(f"Found {len(entries)} entries in manifest")

    # Group by category based on tags
    categorized = {cat: [] for cat in CATEGORIES}
    uncategorized = []

    for entry in entries:
        tags = entry.get("tags", [])
        assigned = False

        if "overworld" in tags or entry.get("gameState", {}).get("mode") == "0x09":
            if not entry.get("gameState", {}).get("indoors", True):
                categorized["overworld"].append(entry)
                assigned = True

        if "dungeon" in tags or entry.get("gameState", {}).get("mode") == "0x07":
            categorized["dungeons"].append(entry)
            assigned = True

        if "boss" in tags:
            categorized["bosses"].append(entry)
            assigned = True

        if "items" in tags or "hookshot" in tags or "goldstar" in tags:
            categorized["items"].append(entry)
            assigned = True

        if not assigned:
            uncategorized.append(entry)

    for category, entries_list in categorized.items():
        print(f"\n{category}: {len(entries_list)} states")

    if uncategorized:
        print(f"\nUncategorized: {len(uncategorized)} states")
        for entry in uncategorized:
            print(f"  - {entry['id']}: {entry.get('description', 'No description')}")


def main():
    parser = argparse.ArgumentParser(description="Unified save state capture tool")
    sub = parser.add_subparsers(dest="command", required=True)

    # Check command
    check_cmd = sub.add_parser("check", help="Check current position")
    check_cmd.set_defaults(func=cmd_check)

    # List-required command
    list_cmd = sub.add_parser("list-required", help="List required checkpoints")
    list_cmd.add_argument("--category", "-c", choices=CATEGORIES, help="Filter by category")
    list_cmd.set_defaults(func=cmd_list_required)

    # Capture command
    capture_cmd = sub.add_parser("capture", help="Capture current state")
    capture_cmd.add_argument("--name", "-n", help="Checkpoint name/id")
    capture_cmd.add_argument("--category", "-c", choices=CATEGORIES, help="Category")
    capture_cmd.add_argument("--slot", "-s", type=int, default=10, help="Save slot")
    capture_cmd.add_argument("--auto", "-a", action="store_true", help="Auto-generate name")
    capture_cmd.set_defaults(func=cmd_capture)

    # Interactive command
    interactive_cmd = sub.add_parser("interactive", help="Interactive capture mode")
    interactive_cmd.add_argument("--category", "-c", choices=CATEGORIES, help="Category to capture")
    interactive_cmd.add_argument("--priority", "-p", choices=["high", "medium", "low"], help="Filter by priority")
    interactive_cmd.set_defaults(func=cmd_interactive)

    # Sync command
    sync_cmd = sub.add_parser("sync", help="Sync metadata between manifest and categories")
    sync_cmd.set_defaults(func=cmd_sync)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
