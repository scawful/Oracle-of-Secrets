#!/usr/bin/env python3
"""Tier 2 Smoke Test Launcher for Oracle of Secrets.

Launches Mesen2 OOS.app with the current ROM and optional save state for manual
visual verification of transitions. This is used for Tier 2 testing when
automated emulator control is unavailable.

Campaign Goal: B.2 (Verify black screen fix), C.1 (Test infrastructure)

Usage:
    # List available test scenarios
    python -m scripts.campaign.tier2_test_launcher --list

    # Launch specific test
    python -m scripts.campaign.tier2_test_launcher --test ow_to_cave

    # Launch with specific save state
    python -m scripts.campaign.tier2_test_launcher --state current_4

    # Launch fresh (no save state)
    python -m scripts.campaign.tier2_test_launcher --fresh
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional


# Paths
PROJECT_ROOT = Path(__file__).parent.parent.parent
ROM_PATH = PROJECT_ROOT / "Roms" / "oos168x.sfc"
STATE_LIBRARY_PATH = PROJECT_ROOT / "Docs" / "Testing" / "save_state_library.json"
SAVE_STATES_DIR = PROJECT_ROOT / "Roms" / "SaveStates" / "library"

# Mesen2 OOS app locations (agent-only)
MESEN_PATHS = [
    Path("/Applications/Mesen2 OOS.app"),  # Fork with debugging extensions
]


@dataclass
class TestScenario:
    """A Tier 2 test scenario for manual verification."""
    id: str
    name: str
    description: str
    state_id: str
    instructions: str
    expected_result: str


# Define Tier 2 test scenarios based on TieredTestingPlan.md
TIER2_SCENARIOS: List[TestScenario] = [
    TestScenario(
        id="ow_to_cave",
        name="Overworld to Cave",
        description="Walk into any cave entrance from overworld",
        state_id="current_1",
        instructions="Walk Link into a cave entrance",
        expected_result="Screen fades to black, then fades in to cave interior"
    ),
    TestScenario(
        id="ow_to_dungeon",
        name="Overworld to Dungeon",
        description="Enter dungeon from overworld (e.g., graveyard entrance)",
        state_id="current_3",
        instructions="Navigate to dungeon entrance and walk in",
        expected_result="Spotlight effect, room loads normally"
    ),
    TestScenario(
        id="ow_to_building",
        name="Overworld to Building",
        description="Enter a Kakariko-style building from overworld",
        state_id="current_1",
        instructions="Walk into a house door",
        expected_result="Screen transitions to building interior"
    ),
    TestScenario(
        id="dungeon_stairs_inter",
        name="Dungeon Interroom Stairs",
        description="Use stairs that change rooms within dungeon",
        state_id="current_4",
        instructions="Walk onto stairs that lead to different room",
        expected_result="New room loads, no black screen"
    ),
    TestScenario(
        id="dungeon_stairs_intra",
        name="Dungeon Intraroom Stairs",
        description="Use stairs that change layers within same room",
        state_id="current_7",
        instructions="Walk onto stairs within same room (layer change)",
        expected_result="Same room visible, layer changes smoothly"
    ),
    TestScenario(
        id="dungeon_to_ow",
        name="Dungeon to Overworld",
        description="Exit dungeon back to overworld",
        state_id="current_4",
        instructions="Walk out of dungeon entrance",
        expected_result="Return to overworld, screen fades in"
    ),
]


def find_mesen() -> Optional[Path]:
    """Find Mesen2 OOS.app on the system."""
    for path in MESEN_PATHS:
        if path.exists():
            return path
    return None


def load_state_library() -> Dict:
    """Load the save state library JSON."""
    if not STATE_LIBRARY_PATH.exists():
        return {"entries": []}

    with open(STATE_LIBRARY_PATH) as f:
        return json.load(f)


def find_state_path(state_id: str, library: Dict) -> Optional[Path]:
    """Find the path for a given state ID."""
    for entry in library.get("entries", []):
        if entry.get("id") == state_id:
            state_path = entry.get("state_path") or entry.get("path")
            if state_path:
                full_path = PROJECT_ROOT / state_path
                if full_path.exists():
                    return full_path
                # Try library directory
                lib_path = SAVE_STATES_DIR / Path(state_path).name
                if lib_path.exists():
                    return lib_path
    return None


def launch_mesen(rom_path: Path, state_path: Optional[Path] = None) -> bool:
    """Launch Mesen2 OOS with the specified ROM and optionally load a state.

    Note: Mesen command-line state loading varies by version. This uses
    the most common approach of loading the ROM and relying on user to
    load the state manually if command-line loading fails.
    """
    mesen = find_mesen()
    if not mesen:
        print("ERROR: Mesen2 OOS.app not found. Check these locations:")
        for path in MESEN_PATHS:
            print(f"  - {path}")
        return False

    if not rom_path.exists():
        print(f"ERROR: ROM not found: {rom_path}")
        print("Run ./scripts/build_rom.sh 168 to build it.")
        return False

    # Launch Mesen with ROM
    print(f"Launching: {mesen.name}")
    print(f"ROM: {rom_path.name}")

    cmd = ["open", str(mesen), "--args", str(rom_path)]

    if state_path and state_path.exists():
        print(f"Save state: {state_path.name}")
        # Try to pass state as additional argument
        cmd.extend(["--load-state", str(state_path)])

    try:
        subprocess.run(cmd, check=True)
        print("\nMesen launched successfully.")

        if state_path:
            print(f"\nIf state didn't auto-load, manually load:")
            print(f"  File > Load State... > {state_path}")

        return True
    except subprocess.CalledProcessError as e:
        print(f"ERROR launching Mesen: {e}")
        return False


def list_scenarios():
    """Print all available test scenarios."""
    print("\n" + "=" * 70)
    print("TIER 2 SMOKE TEST SCENARIOS")
    print("=" * 70)

    for scenario in TIER2_SCENARIOS:
        print(f"\n{scenario.id}:")
        print(f"  Name: {scenario.name}")
        print(f"  Description: {scenario.description}")
        print(f"  State: {scenario.state_id}")
        print(f"  Instructions: {scenario.instructions}")
        print(f"  Expected: {scenario.expected_result}")

    print("\n" + "-" * 70)
    print("Usage: python -m scripts.campaign.tier2_test_launcher --test <id>")
    print("-" * 70)


def list_states():
    """Print all available save states."""
    library = load_state_library()

    print("\n" + "=" * 70)
    print("AVAILABLE SAVE STATES")
    print("=" * 70)

    # Group by ROM base
    by_rom: Dict[str, List] = {}
    for entry in library.get("entries", []):
        rom_base = entry.get("rom_base", "unknown")
        if rom_base not in by_rom:
            by_rom[rom_base] = []
        by_rom[rom_base].append(entry)

    for rom_base, entries in sorted(by_rom.items()):
        print(f"\n{rom_base}:")
        for entry in entries:
            state_id = entry.get("id", "?")
            label = entry.get("meta", {}).get("label", entry.get("description", ""))
            print(f"  {state_id}: {label}")

    print("\n" + "-" * 70)
    print("Usage: python -m scripts.campaign.tier2_test_launcher --state <id>")
    print("-" * 70)


def run_scenario(scenario_id: str):
    """Run a specific test scenario."""
    scenario = None
    for s in TIER2_SCENARIOS:
        if s.id == scenario_id:
            scenario = s
            break

    if not scenario:
        print(f"ERROR: Unknown scenario: {scenario_id}")
        print("Use --list to see available scenarios.")
        return False

    library = load_state_library()
    state_path = find_state_path(scenario.state_id, library)

    print("\n" + "=" * 70)
    print(f"TIER 2 TEST: {scenario.name}")
    print("=" * 70)
    print(f"\nDescription: {scenario.description}")
    print(f"\nInstructions:")
    print(f"  1. Wait for Mesen to launch")
    print(f"  2. {scenario.instructions}")
    print(f"\nExpected result:")
    print(f"  {scenario.expected_result}")
    print(f"\nIf screen stays BLACK for >3 seconds, the test FAILS.")
    print("=" * 70)

    return launch_mesen(ROM_PATH, state_path)


def record_result(scenario_id: str, passed: bool, notes: str = ""):
    """Record a test result (placeholder for future automation)."""
    result = {
        "scenario_id": scenario_id,
        "passed": passed,
        "notes": notes,
    }
    print(f"Result recorded: {result}")
    # Future: Write to test results file


def main():
    parser = argparse.ArgumentParser(
        description="Tier 2 Smoke Test Launcher for Oracle of Secrets"
    )
    parser.add_argument(
        "--list", "-l",
        action="store_true",
        help="List all available test scenarios"
    )
    parser.add_argument(
        "--list-states",
        action="store_true",
        help="List all available save states"
    )
    parser.add_argument(
        "--test", "-t",
        metavar="ID",
        help="Run a specific test scenario by ID"
    )
    parser.add_argument(
        "--state", "-s",
        metavar="ID",
        help="Launch with a specific save state by ID"
    )
    parser.add_argument(
        "--fresh",
        action="store_true",
        help="Launch fresh without any save state"
    )
    parser.add_argument(
        "--rom",
        metavar="PATH",
        help="Override ROM path (default: Roms/oos168x.sfc)"
    )

    args = parser.parse_args()

    # Handle listing
    if args.list:
        list_scenarios()
        return 0

    if args.list_states:
        list_states()
        return 0

    # Determine ROM path
    rom_path = Path(args.rom) if args.rom else ROM_PATH

    # Handle test scenario
    if args.test:
        success = run_scenario(args.test)
        return 0 if success else 1

    # Handle state launch
    if args.state:
        library = load_state_library()
        state_path = find_state_path(args.state, library)
        if not state_path:
            print(f"ERROR: State not found: {args.state}")
            print("Use --list-states to see available states.")
            return 1
        success = launch_mesen(rom_path, state_path)
        return 0 if success else 1

    # Handle fresh launch
    if args.fresh:
        success = launch_mesen(rom_path)
        return 0 if success else 1

    # No action specified - show help
    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
