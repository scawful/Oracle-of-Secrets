#!/usr/bin/env python3
"""Autonomous Gameplay Demonstration Script.

This script demonstrates the campaign's ability to autonomously control
the game. It loads a save state, reads game state, injects inputs,
and verifies the result.

Campaign Goal A Evidence:
- Connects to Mesen2 via socket
- Reads game state (mode, position, etc.)
- Injects movement inputs
- Verifies position changed

Usage:
    python3 scripts/campaign/automation_demo.py

Requirements:
    - Mesen2 running with socket enabled
    - ROM loaded and in playable state (or use --load-state)
"""

import sys
import time
import argparse
from pathlib import Path

# Add project root
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import get_emulator, Mesen2Emulator
from scripts.campaign.game_state import parse_state, GamePhase
from scripts.campaign.input_recorder import create_walk_sequence, Button


def print_header(msg: str):
    """Print a section header."""
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def print_state(state, label: str = "Current State"):
    """Print parsed game state."""
    print(f"\n--- {label} ---")
    print(f"  Phase: {state.phase.name}")
    print(f"  Location: {state.location_name}")
    print(f"  Position: {state.link_position}")
    print(f"  Direction: {state.link_direction}")
    print(f"  Can Move: {state.can_move}")
    print(f"  Health: {state.health_percent*100:.0f}%")


def demo_walk_right(emu: Mesen2Emulator, frames: int = 60) -> bool:
    """Demo: Walk right and verify position changed.

    This is the simplest possible automation test:
    1. Read current X position
    2. Inject RIGHT input for N frames
    3. Read new X position
    4. Verify X increased

    Returns:
        True if position increased as expected
    """
    print_header("Demo: Walk Right")

    # Step 1: Read initial state
    print("\n[Step 1] Reading initial state...")
    initial_raw = emu.read_state()
    initial_state = parse_state(initial_raw)
    print_state(initial_state, "Initial State")

    if not initial_state.can_move:
        print("ERROR: Link cannot move in current state!")
        return False

    initial_x = initial_state.link_position[0]
    print(f"\n  Initial X: {initial_x}")

    # Step 2: Inject RIGHT input
    print(f"\n[Step 2] Injecting RIGHT input for {frames} frames...")
    result = emu.inject_input(["RIGHT"], frames=frames)
    if not result:
        print("ERROR: Failed to inject input!")
        return False
    print("  Input injected successfully")

    # Step 3: Wait for input to be processed
    print("\n[Step 3] Waiting for game to process input...")
    time.sleep(frames / 60.0 + 0.5)  # 60fps + buffer

    # Step 4: Read final state
    print("\n[Step 4] Reading final state...")
    final_raw = emu.read_state()
    final_state = parse_state(final_raw)
    print_state(final_state, "Final State")

    final_x = final_state.link_position[0]
    print(f"\n  Final X: {final_x}")

    # Step 5: Verify position changed
    delta_x = final_x - initial_x
    print(f"\n[Step 5] Verifying position change...")
    print(f"  Delta X: {delta_x} pixels")

    if delta_x > 0:
        print(f"\n  SUCCESS! Link moved {delta_x} pixels to the right.")
        return True
    elif delta_x == 0:
        print("\n  FAILED: Position did not change. Link may be blocked.")
        return False
    else:
        print(f"\n  UNEXPECTED: Position decreased by {abs(delta_x)} pixels.")
        return False


def demo_boot_sequence(emu: Mesen2Emulator) -> bool:
    """Demo: Execute boot sequence.

    Uses the pre-built boot sequence to navigate from
    title screen to gameplay.

    Returns:
        True if reached playable state
    """
    print_header("Demo: Boot Sequence")

    from scripts.campaign.input_recorder import create_boot_sequence, InputPlayer

    # Get boot sequence
    boot_seq = create_boot_sequence()
    print(f"Boot sequence: {boot_seq.frame_count} frames, {len(boot_seq.frames)} inputs")

    # Create player and execute
    player = InputPlayer(emu)

    print("\n[Executing boot sequence...]")
    success = player.play(boot_seq)

    if success:
        # Verify we're in playable state
        raw = emu.read_state()
        state = parse_state(raw)
        print_state(state, "State After Boot")

        if state.is_playing and state.can_move:
            print("\nSUCCESS! Reached playable state.")
            return True
        else:
            print(f"\nReached {state.phase.name} but not playable yet.")
            return False
    else:
        print("\nFAILED: Boot sequence execution failed.")
        return False


def main():
    parser = argparse.ArgumentParser(
        description="Oracle of Secrets Autonomous Gameplay Demo"
    )
    parser.add_argument(
        "--demo",
        choices=["walk", "boot", "all"],
        default="walk",
        help="Which demo to run"
    )
    parser.add_argument(
        "--frames",
        type=int,
        default=60,
        help="Frames to walk (for walk demo)"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without emulator"
    )
    args = parser.parse_args()

    print_header("Oracle of Secrets Autonomous Gameplay Demo")
    print(f"Demo: {args.demo}")
    print(f"Dry run: {args.dry_run}")

    if args.dry_run:
        print("\n[Dry run mode - showing planned actions]")
        print("\n1. Connect to Mesen2 via socket")
        print("2. Read initial game state")
        print("3. Inject controller inputs")
        print("4. Wait for game to process")
        print("5. Read final game state")
        print("6. Verify state changed as expected")
        print("\nTo run for real, start Mesen2 and run without --dry-run")
        return 0

    # Connect to emulator
    print("\n[Connecting to Mesen2...]")
    try:
        emu = get_emulator("mesen2")
        emu.connect()

        if not emu.is_connected():
            print("ERROR: Failed to connect to Mesen2!")
            print("Make sure Mesen2 is running with socket API enabled.")
            return 1

        print("Connected successfully!")

    except Exception as e:
        print(f"ERROR: {e}")
        print("\nMake sure Mesen2 is running with socket API enabled.")
        print("Socket should be at /tmp/mesen2-<pid>.sock")
        return 1

    # Run demos
    results = {}

    if args.demo in ["walk", "all"]:
        results["walk"] = demo_walk_right(emu, frames=args.frames)

    if args.demo in ["boot", "all"]:
        results["boot"] = demo_boot_sequence(emu)

    # Summary
    print_header("Results Summary")
    for name, success in results.items():
        status = "PASS" if success else "FAIL"
        print(f"  {name}: {status}")

    all_passed = all(results.values())
    print(f"\nOverall: {'ALL PASSED' if all_passed else 'SOME FAILED'}")

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
