#!/usr/bin/env python3
"""Import save states from Mesen2 directory into the test library.

Usage:
    python scripts/import_states.py --source oos91x --dest baseline
    python scripts/import_states.py --list
    python scripts/import_states.py --inspect ~/Documents/Mesen2/SaveStates/oos91x_1.mss
"""

import argparse
import json
import shutil
import sys
from pathlib import Path
from datetime import datetime

# Paths
MESEN2_STATES = Path.home() / "Documents" / "Mesen2" / "SaveStates"
PROJECT_ROOT = Path(__file__).parent.parent
LIBRARY_ROOT = PROJECT_ROOT / "Roms" / "SaveStates" / "library"
MANIFEST_PATH = PROJECT_ROOT / "Docs" / "Testing" / "save_state_library.json"


def list_available_states():
    """List all .mss files in Mesen2 SaveStates directory."""
    if not MESEN2_STATES.exists():
        print(f"Mesen2 SaveStates directory not found: {MESEN2_STATES}")
        return

    # Group by ROM name
    states = {}
    for mss in sorted(MESEN2_STATES.glob("*.mss")):
        # Parse name: romname_slot.mss
        name = mss.stem
        parts = name.rsplit("_", 1)
        if len(parts) == 2:
            rom_name, slot = parts
        else:
            rom_name, slot = name, "?"

        if rom_name not in states:
            states[rom_name] = []
        states[rom_name].append((slot, mss))

    print(f"=== Available Save States in {MESEN2_STATES} ===\n")
    for rom_name in sorted(states.keys()):
        slots = states[rom_name]
        print(f"{rom_name}: {len(slots)} states")
        for slot, path in sorted(slots, key=lambda x: int(x[0]) if x[0].isdigit() else 99):
            mtime = datetime.fromtimestamp(path.stat().st_mtime).strftime("%Y-%m-%d %H:%M")
            size = path.stat().st_size // 1024
            print(f"  [{slot:>2}] {path.name} ({size}KB, {mtime})")
        print()


def import_states(source_pattern: str, dest_folder: str, slots: list = None):
    """Import states matching pattern to library folder."""
    source_files = sorted(MESEN2_STATES.glob(f"{source_pattern}_*.mss"))

    if not source_files:
        print(f"No states found matching: {source_pattern}_*.mss")
        return []

    dest_path = LIBRARY_ROOT / dest_folder
    dest_path.mkdir(parents=True, exist_ok=True)

    imported = []
    for src in source_files:
        # Extract slot number
        slot = src.stem.rsplit("_", 1)[-1]
        if slots and slot not in slots:
            continue

        dest_file = dest_path / src.name
        shutil.copy2(src, dest_file)
        imported.append({
            "source": str(src),
            "dest": str(dest_file),
            "slot": slot,
            "name": src.stem
        })
        print(f"Copied: {src.name} -> {dest_folder}/")

    print(f"\nImported {len(imported)} states to {dest_path}")
    return imported


def update_manifest(imported_states: list, rom_version: str, dest_folder: str):
    """Add imported states to the manifest."""
    manifest = {"version": 1, "library_root": "Roms/SaveStates/library", "entries": [], "sets": []}

    if MANIFEST_PATH.exists():
        with open(MANIFEST_PATH) as f:
            manifest = json.load(f)

    # Create entries for imported states
    for state in imported_states:
        entry_id = f"{dest_folder}_{state['slot']}"

        # Check if already exists
        existing = next((e for e in manifest["entries"] if e["id"] == entry_id), None)
        if existing:
            print(f"Entry {entry_id} already exists, skipping")
            continue

        entry = {
            "id": entry_id,
            "path": f"{dest_folder}/{Path(state['dest']).name}",
            "romVersion": rom_version,
            "description": f"Slot {state['slot']} from {rom_version}",
            "tags": [dest_folder, f"slot-{state['slot']}"],
            "imported": datetime.now().isoformat(),
            "gameState": {
                "mode": "unknown",
                "room": "unknown",
                "indoors": None
            }
        }
        manifest["entries"].append(entry)
        print(f"Added manifest entry: {entry_id}")

    # Create a set for this import
    set_id = f"{dest_folder}_set"
    if not any(s["id"] == set_id for s in manifest["sets"]):
        state_set = {
            "id": set_id,
            "name": f"{dest_folder.title()} States",
            "description": f"All states from {rom_version}",
            "entries": [f"{dest_folder}_{s['slot']}" for s in imported_states]
        }
        manifest["sets"].append(state_set)
        print(f"Created set: {set_id}")

    with open(MANIFEST_PATH, "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"\nUpdated manifest: {MANIFEST_PATH}")


def create_test_definitions(dest_folder: str):
    """Create basic test definitions for imported states."""
    tests_dir = PROJECT_ROOT / "tests" / dest_folder
    tests_dir.mkdir(parents=True, exist_ok=True)

    # Boot test template
    boot_test = {
        "name": f"{dest_folder} Boot Verification",
        "description": f"Verify {dest_folder} states load without crash",
        "saveState": {
            "id": f"{dest_folder}_1",
            "waitSeconds": 3
        },
        "steps": [
            {"type": "wait", "seconds": 1},
            {"type": "assert", "address": "$7E0010", "in": [0, 7, 9], "description": "Valid game mode"},
            {"type": "screenshot", "name": f"{dest_folder}_loaded"}
        ],
        "tags": [dest_folder, "boot", "smoke-test"]
    }

    test_file = tests_dir / "boot_test.json"
    if not test_file.exists():
        with open(test_file, "w") as f:
            json.dump(boot_test, f, indent=2)
        print(f"Created test: {test_file}")


def main():
    parser = argparse.ArgumentParser(description="Import save states to test library")
    parser.add_argument("--list", action="store_true", help="List available states")
    parser.add_argument("--source", help="Source ROM pattern (e.g., oos91x)")
    parser.add_argument("--dest", help="Destination folder name (e.g., baseline)")
    parser.add_argument("--slots", help="Comma-separated slot numbers to import (e.g., 1,2,3)")
    parser.add_argument("--no-manifest", action="store_true", help="Skip manifest update")
    parser.add_argument("--no-tests", action="store_true", help="Skip test definition creation")

    args = parser.parse_args()

    if args.list:
        list_available_states()
        return

    if not args.source or not args.dest:
        parser.print_help()
        print("\nExamples:")
        print("  python scripts/import_states.py --list")
        print("  python scripts/import_states.py --source oos91x --dest baseline")
        print("  python scripts/import_states.py --source oos168x --dest current --slots 1,2,3")
        return

    slots = args.slots.split(",") if args.slots else None
    imported = import_states(args.source, args.dest, slots)

    if imported and not args.no_manifest:
        update_manifest(imported, args.source, args.dest)

    if imported and not args.no_tests:
        create_test_definitions(args.dest)


if __name__ == "__main__":
    main()
