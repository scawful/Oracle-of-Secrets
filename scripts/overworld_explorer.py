#!/usr/bin/env python3
"""
Overworld exploration and bug detection tool.

Explores the overworld by walking in cardinal directions and monitors
for issues like:
- Camera glitches (scroll position vs link position mismatch)
- Area transition failures
- Mode changes during movement
- Sprite anomalies

Usage:
    ./scripts/overworld_explorer.py explore [--direction DIR] [--steps N]
    ./scripts/overworld_explorer.py transitions  # Test area transitions
    ./scripts/overworld_explorer.py camera       # Check camera sync
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from typing import Optional

from mesen2_client_lib.client import OracleDebugClient
from mesen2_client_lib.constants import MODE_NAMES, OracleRAM

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
CYAN = "\033[96m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class AreaSnapshot:
    """Snapshot of area state for comparison."""

    area: int
    room: int
    link_x: int
    link_y: int
    scroll_x: int
    scroll_y: int
    mode: int
    submode: int
    timestamp: float

    @classmethod
    def capture(cls, client: OracleDebugClient) -> "AreaSnapshot":
        state = client.get_oracle_state()
        return cls(
            area=state["area"],
            room=state["room"],
            link_x=state["link_x"],
            link_y=state["link_y"],
            scroll_x=state["scroll_x"],
            scroll_y=state["scroll_y"],
            mode=state["mode"],
            submode=state["submode"],
            timestamp=time.time(),
        )


class OverworldExplorer:
    """Explores overworld areas and checks for issues."""

    def __init__(self, verbose: bool = False):
        self.client = OracleDebugClient()
        self.verbose = verbose
        self.issues_found: list[dict] = []
        self.transitions: list[dict] = []

    def log(self, msg: str, color: str = ""):
        print(f"{color}{msg}{RESET}")

    def capture_issue(
        self, issue_type: str, description: str, before: AreaSnapshot, after: AreaSnapshot
    ):
        """Record an issue for later analysis."""
        issue = {
            "type": issue_type,
            "description": description,
            "before": {
                "area": f"0x{before.area:02X}",
                "room": f"0x{before.room:02X}",
                "position": (before.link_x, before.link_y),
                "scroll": (before.scroll_x, before.scroll_y),
                "mode": f"0x{before.mode:02X}",
            },
            "after": {
                "area": f"0x{after.area:02X}",
                "room": f"0x{after.room:02X}",
                "position": (after.link_x, after.link_y),
                "scroll": (after.scroll_x, after.scroll_y),
                "mode": f"0x{after.mode:02X}",
            },
            "timestamp": time.time(),
        }
        self.issues_found.append(issue)
        self.log(f"  {RED}ISSUE: {description}{RESET}")

    def get_full_scroll(self) -> tuple[int, int]:
        """Get full 16-bit scroll values from raw registers."""
        scroll_x_lo = self.client.read_address(OracleRAM.SCROLL_X_LO)
        scroll_x_hi = self.client.read_address(OracleRAM.SCROLL_X_HI)
        scroll_y_lo = self.client.read_address(OracleRAM.SCROLL_Y_LO)
        scroll_y_hi = self.client.read_address(OracleRAM.SCROLL_Y_HI)

        full_x = (scroll_x_hi << 8) | scroll_x_lo
        full_y = (scroll_y_hi << 8) | scroll_y_lo
        return full_x, full_y

    def check_camera_sync(self, snapshot: AreaSnapshot) -> Optional[str]:
        """Check if camera is properly synced with Link's position.

        Returns issue description if there's a problem, None otherwise.
        """
        # Get full 16-bit scroll values
        scroll_x, scroll_y = self.get_full_scroll()

        # Camera offset from Link should be reasonable (within ~128 pixels)
        # The camera typically centers on Link with some offset
        offset_x = abs(snapshot.link_x - scroll_x)
        offset_y = abs(snapshot.link_y - scroll_y)

        # Screen is 256x224, so camera should be within ~200 pixels of Link
        # Large offsets indicate camera desync
        MAX_OFFSET = 200

        if offset_x > MAX_OFFSET or offset_y > MAX_OFFSET:
            return f"Camera desync: Link=({snapshot.link_x},{snapshot.link_y}), Scroll=({scroll_x},{scroll_y}), Offset=({offset_x},{offset_y})"

        return None

    def explore_direction(
        self,
        direction: str,
        steps: int = 5,
        frames_per_step: int = 30,
        check_interval: float = 0.2,
    ) -> list[dict]:
        """Walk in a direction and monitor for issues.

        Args:
            direction: up, down, left, right
            steps: Number of movement segments
            frames_per_step: Frames to hold direction per step
            check_interval: Seconds between state checks

        Returns:
            List of issues found
        """
        self.log(f"\n{BOLD}Exploring {direction.upper()}{RESET}")
        self.log(f"Steps: {steps}, Frames/step: {frames_per_step}")

        issues = []
        before = AreaSnapshot.capture(self.client)
        self.log(
            f"Start: Area=0x{before.area:02X} ({before.link_x}, {before.link_y})"
        )

        for step in range(steps):
            # Record pre-movement state
            pre_move = AreaSnapshot.capture(self.client)

            # Execute movement
            self.client.hold_direction(direction, frames=frames_per_step)
            time.sleep(frames_per_step / 60.0 + check_interval)

            # Check post-movement state
            post_move = AreaSnapshot.capture(self.client)

            # Check for mode changes (shouldn't happen during normal movement)
            if post_move.mode != pre_move.mode:
                if post_move.mode == 0x05:  # Transition mode
                    self.log(
                        f"  Step {step+1}: Transition detected (mode 0x{post_move.mode:02X})",
                        YELLOW,
                    )
                    # Wait for transition to complete
                    for _ in range(50):  # 5 second timeout
                        time.sleep(0.1)
                        check = AreaSnapshot.capture(self.client)
                        if check.mode != 0x05:
                            break
                    post_move = AreaSnapshot.capture(self.client)
                else:
                    self.capture_issue(
                        "mode_change",
                        f"Unexpected mode change during movement: 0x{pre_move.mode:02X} -> 0x{post_move.mode:02X}",
                        pre_move,
                        post_move,
                    )

            # Check for area transitions
            if post_move.area != pre_move.area:
                transition = {
                    "from_area": f"0x{pre_move.area:02X}",
                    "to_area": f"0x{post_move.area:02X}",
                    "direction": direction,
                    "from_pos": (pre_move.link_x, pre_move.link_y),
                    "to_pos": (post_move.link_x, post_move.link_y),
                }
                self.transitions.append(transition)
                self.log(
                    f"  Step {step+1}: Area transition 0x{pre_move.area:02X} -> 0x{post_move.area:02X}",
                    CYAN,
                )

            # Check camera sync
            camera_issue = self.check_camera_sync(post_move)
            if camera_issue:
                self.capture_issue("camera_desync", camera_issue, pre_move, post_move)

            # Check for stuck movement (no position change in non-blocked situation)
            delta_x = abs(post_move.link_x - pre_move.link_x)
            delta_y = abs(post_move.link_y - pre_move.link_y)

            if delta_x == 0 and delta_y == 0:
                # Could be blocked by obstacle or stuck
                if self.verbose:
                    self.log(f"  Step {step+1}: No movement (blocked?)", YELLOW)
            else:
                if self.verbose:
                    self.log(
                        f"  Step {step+1}: Moved ({delta_x}, {delta_y}) px -> ({post_move.link_x}, {post_move.link_y})"
                    )

        after = AreaSnapshot.capture(self.client)
        total_delta = (
            abs(after.link_x - before.link_x),
            abs(after.link_y - before.link_y),
        )
        self.log(
            f"End: Area=0x{after.area:02X} ({after.link_x}, {after.link_y}), moved {total_delta}"
        )

        return self.issues_found

    def test_area_transitions(self, timeout_per_direction: float = 10.0) -> dict:
        """Walk in all directions looking for area transitions.

        Returns summary of transitions found and any issues.
        """
        self.log(f"\n{BOLD}=== Area Transition Test ==={RESET}")

        initial = AreaSnapshot.capture(self.client)
        self.log(f"Starting at Area 0x{initial.area:02X}")

        results = {
            "start_area": f"0x{initial.area:02X}",
            "transitions": [],
            "issues": [],
            "directions_tested": [],
        }

        for direction in ["up", "down", "left", "right"]:
            self.log(f"\n--- Testing {direction.upper()} ---")
            results["directions_tested"].append(direction)

            # Walk until we hit an area transition or timeout
            start_time = time.time()
            start_area = AreaSnapshot.capture(self.client).area
            steps_taken = 0

            while time.time() - start_time < timeout_per_direction:
                self.client.hold_direction(direction, frames=30)
                time.sleep(0.6)
                steps_taken += 1

                current = AreaSnapshot.capture(self.client)

                if current.area != start_area:
                    self.log(
                        f"  Transition: 0x{start_area:02X} -> 0x{current.area:02X} after {steps_taken} steps",
                        GREEN,
                    )
                    results["transitions"].append(
                        {
                            "direction": direction,
                            "from": f"0x{start_area:02X}",
                            "to": f"0x{current.area:02X}",
                            "steps": steps_taken,
                        }
                    )
                    break

                # Check for issues during exploration
                camera_issue = self.check_camera_sync(current)
                if camera_issue:
                    results["issues"].append(
                        {"direction": direction, "issue": camera_issue}
                    )
            else:
                self.log(
                    f"  No transition found (timeout after {steps_taken} steps)",
                    YELLOW,
                )

            # Return to starting position (load state would be better)
            # For now, just record where we ended up

        return results

    def camera_check(self) -> dict:
        """Comprehensive camera sync check."""
        self.log(f"\n{BOLD}=== Camera Sync Check ==={RESET}")

        snapshot = AreaSnapshot.capture(self.client)
        scroll_x, scroll_y = self.get_full_scroll()

        self.log(f"Area: 0x{snapshot.area:02X}")
        self.log(f"Link Position: ({snapshot.link_x}, {snapshot.link_y})")
        self.log(f"Full Scroll: ({scroll_x}, {scroll_y})")

        offset_x = snapshot.link_x - scroll_x
        offset_y = snapshot.link_y - scroll_y
        self.log(f"Camera Offset: ({offset_x}, {offset_y})")

        # Read raw scroll registers for debugging
        scroll_x_lo = self.client.read_address(OracleRAM.SCROLL_X_LO)
        scroll_x_hi = self.client.read_address(OracleRAM.SCROLL_X_HI)
        scroll_y_lo = self.client.read_address(OracleRAM.SCROLL_Y_LO)
        scroll_y_hi = self.client.read_address(OracleRAM.SCROLL_Y_HI)

        self.log(f"\nRaw scroll registers:")
        self.log(f"  $E1/$E3 (X): 0x{scroll_x_hi:02X}{scroll_x_lo:02X} = {scroll_x}")
        self.log(f"  $E7/$E9 (Y): 0x{scroll_y_hi:02X}{scroll_y_lo:02X} = {scroll_y}")

        issue = self.check_camera_sync(snapshot)
        if issue:
            self.log(f"\n{RED}Camera issue: {issue}{RESET}")
            return {"status": "issue", "issue": issue, "offset": (offset_x, offset_y)}
        else:
            self.log(f"\n{GREEN}Camera appears synced (offset within tolerance){RESET}")
            return {"status": "ok", "offset": (offset_x, offset_y)}


def main():
    parser = argparse.ArgumentParser(description="Overworld Explorer")
    parser.add_argument("-v", "--verbose", action="store_true")
    subparsers = parser.add_subparsers(dest="command")

    # Explore command
    explore_parser = subparsers.add_parser("explore", help="Explore in a direction")
    explore_parser.add_argument(
        "-d", "--direction", default="right", choices=["up", "down", "left", "right"]
    )
    explore_parser.add_argument("-n", "--steps", type=int, default=5)
    explore_parser.add_argument("-f", "--frames", type=int, default=30)

    # Transitions command
    subparsers.add_parser("transitions", help="Test area transitions")

    # Camera command
    subparsers.add_parser("camera", help="Check camera sync")

    args = parser.parse_args()

    explorer = OverworldExplorer(verbose=args.verbose)

    if args.command == "explore":
        issues = explorer.explore_direction(
            args.direction, steps=args.steps, frames_per_step=args.frames
        )
        if issues:
            print(f"\n{RED}Issues found: {len(issues)}{RESET}")
            print(json.dumps(issues, indent=2))
        else:
            print(f"\n{GREEN}No issues found{RESET}")

    elif args.command == "transitions":
        results = explorer.test_area_transitions()
        print("\n=== Summary ===")
        print(json.dumps(results, indent=2))

    elif args.command == "camera":
        result = explorer.camera_check()
        print(json.dumps(result, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
