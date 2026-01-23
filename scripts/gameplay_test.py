#!/usr/bin/env python3
"""
Automated gameplay test framework using native Mesen2 socket API.

Usage:
    ./scripts/gameplay_test.py run tests/overworld_basic.json
    ./scripts/gameplay_test.py smoke
    ./scripts/gameplay_test.py capture <name> [--tag TAG]
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from mesen2_client_lib.client import OracleDebugClient
from mesen2_client_lib.constants import MODE_NAMES

# ANSI colors
GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
BLUE = "\033[94m"
RESET = "\033[0m"
BOLD = "\033[1m"


@dataclass
class TestResult:
    passed: bool
    message: str
    details: Optional[dict] = None


class GameplayTestRunner:
    """Runs automated gameplay tests using native socket API."""

    def __init__(self):
        self.client = OracleDebugClient()
        self.verbose = False
        self.screenshots_dir = Path("tests/screenshots")

    def log(self, msg: str, color: str = ""):
        print(f"{color}{msg}{RESET}")

    def wait_for_mode(
        self, expected: int, timeout: float = 2.0, interval: float = 0.1
    ) -> tuple[bool, dict]:
        """Wait for game to reach expected mode."""
        start = time.time()
        while time.time() - start < timeout:
            state = self.client.get_oracle_state()
            if state["mode"] == expected:
                return True, state
            time.sleep(interval)
        return False, self.client.get_oracle_state()

    def wait_for_address(
        self,
        addr: int,
        expected: int,
        timeout: float = 2.0,
        condition: str = "equals",
        values: list = None,
    ) -> tuple[bool, int]:
        """Wait for memory address to match condition."""
        start = time.time()
        while time.time() - start < timeout:
            actual = self.client.read_address(addr)
            if self._check_condition(actual, expected, condition, values):
                return True, actual
            time.sleep(0.1)
        return False, self.client.read_address(addr)

    def _check_condition(
        self, actual: int, expected: int, condition: str, values: list = None
    ) -> bool:
        if condition == "equals":
            return actual == expected
        elif condition == "not_equals":
            return actual != expected
        elif condition == "in":
            return actual in (values or [])
        elif condition == "greater":
            return actual > expected
        elif condition == "less":
            return actual < expected
        return False

    def run_step(self, step: dict) -> TestResult:
        """Execute a single test step."""
        step_type = step.get("type", "")
        desc = step.get("description", step_type)

        try:
            if step_type == "press":
                button = step["button"]
                frames = step.get("frames", 5)
                self.client.press_button(button, frames=frames)
                if self.verbose:
                    self.log(f"  -> Press {button} ({frames}f)", BLUE)
                return TestResult(True, f"Pressed {button}")

            elif step_type == "wait":
                seconds = step.get("seconds", step.get("ms", 100) / 1000.0)
                time.sleep(seconds)
                return TestResult(True, f"Waited {seconds:.3f}s")

            elif step_type == "wait_state":
                key = step.get("key", "mode")
                expected = step.get("equals", step.get("value"))
                timeout = step.get("timeout", 5.0)

                start = time.time()
                while time.time() - start < timeout:
                    state = self.client.get_oracle_state()
                    actual = state.get(key)
                    if actual == expected:
                        if self.verbose:
                            self.log(f"  ✓ {desc}: {key}={actual}", GREEN)
                        return TestResult(True, f"{key} == {expected}")
                    time.sleep(0.1)

                state = self.client.get_oracle_state()
                actual = state.get(key)
                return TestResult(
                    False, f"{desc}: timeout ({key}={actual}, expected {expected})"
                )

            elif step_type == "wait_addr":
                addr_str = step.get("address", "")
                if addr_str.startswith("$"):
                    addr = int(addr_str[1:], 16)
                else:
                    addr = int(addr_str, 0)

                expected = step.get("equals", step.get("value", 0))
                if isinstance(expected, str):
                    expected = int(expected, 0)
                condition = step.get("condition", "equals")
                values = step.get("values", step.get("in"))
                timeout = step.get("timeout", 5.0)

                ok, actual = self.wait_for_address(
                    addr, expected, timeout, condition, values
                )
                if ok:
                    if self.verbose:
                        self.log(f"  ✓ {desc}", GREEN)
                    return TestResult(True, f"Address check passed")
                return TestResult(
                    False, f"{desc}: got 0x{actual:02X}, expected 0x{expected:02X}"
                )

            elif step_type == "assert":
                addr_str = step.get("address", "")
                if addr_str.startswith("$"):
                    addr = int(addr_str[1:], 16)
                else:
                    addr = int(addr_str, 0)

                expected = step.get("equals", step.get("value", 0))
                if isinstance(expected, str):
                    expected = int(expected, 0)
                condition = step.get("condition", "equals")
                values = step.get("values", step.get("in"))

                actual = self.client.read_address(addr)
                if self._check_condition(actual, expected, condition, values):
                    if self.verbose:
                        self.log(f"  ✓ {desc}", GREEN)
                    return TestResult(True, f"Assert passed")
                return TestResult(
                    False, f"{desc}: got 0x{actual:02X}, expected 0x{expected:02X}"
                )

            elif step_type == "write":
                addr_str = step.get("address", "")
                if addr_str.startswith("$"):
                    addr = int(addr_str[1:], 16)
                else:
                    addr = int(addr_str, 0)

                value = step.get("value", step.get("equals", 0))
                if isinstance(value, str):
                    value = int(value, 0)

                self.client.write_address(addr, value)
                return TestResult(True, f"Wrote 0x{value:02X} to 0x{addr:04X}")

            elif step_type == "screenshot":
                path = step.get("path", "")
                result = self.client.screenshot()
                if self.verbose:
                    self.log(f"  -> Screenshot: {path or 'auto'}", BLUE)
                return TestResult(True, f"Screenshot taken")

            elif step_type == "command":
                cmd = step.get("command", "")
                args = step.get("args", [])
                if self.verbose:
                    self.log(f"  -> Command: {cmd} {args}", BLUE)
                # Commands are just logged, actual execution depends on bridge
                return TestResult(True, f"Command {cmd}")

            else:
                return TestResult(False, f"Unknown step type: {step_type}")

        except Exception as e:
            return TestResult(False, f"Exception: {e}")

    def run_test(self, test_path: Path) -> str:
        """Run a test file. Returns 'passed', 'failed', or 'skipped'."""
        with open(test_path) as f:
            test = json.load(f)

        self.log(f"\n{'='*60}", BOLD)
        self.log(f"Test: {test['name']}", BOLD)
        self.log(f"{'='*60}")
        self.log(f"Description: {test.get('description', 'N/A')}")

        # Check connection
        if not self.client.is_connected():
            self.log(f"{RED}Not connected to Mesen2{RESET}")
            return "failed"

        # Run steps
        for i, step in enumerate(test.get("steps", []), 1):
            desc = step.get("description", step.get("type", f"Step {i}"))
            result = self.run_step(step)

            if not result.passed:
                self.log(f"\n{RED}FAILED at step {i}: {desc}{RESET}")
                self.log(f"  {result.message}", RED)
                return "failed"

        self.log(f"\n{GREEN}{'='*60}{RESET}")
        self.log(f"{GREEN}TEST PASSED: {test['name']}{RESET}")
        self.log(f"{GREEN}{'='*60}{RESET}")
        return "passed"

    def run_smoke_test(self) -> bool:
        """Run a quick smoke test to verify the connection and basic functionality."""
        self.log(f"\n{BOLD}=== Smoke Test ==={RESET}")

        # Test 1: Connection
        self.log("\n1. Testing connection...")
        if not self.client.is_connected():
            self.log(f"  {RED}✗ Not connected{RESET}")
            return False
        self.log(f"  {GREEN}✓ Connected{RESET}")

        # Test 2: State read
        self.log("\n2. Reading game state...")
        try:
            state = self.client.get_oracle_state()
            mode_name = MODE_NAMES.get(state["mode"], f"0x{state['mode']:02X}")
            self.log(f"  Mode: {mode_name}")
            self.log(f"  Area: 0x{state['area']:02X}")
            self.log(f"  Position: ({state['link_x']}, {state['link_y']})")
            self.log(f"  {GREEN}✓ State read successful{RESET}")
        except Exception as e:
            self.log(f"  {RED}✗ State read failed: {e}{RESET}")
            return False

        # Test 3: Memory read
        self.log("\n3. Testing memory read...")
        try:
            mode = self.client.read_address(0x7E0010)
            self.log(f"  Mode at $7E0010: 0x{mode:02X}")
            self.log(f"  {GREEN}✓ Memory read successful{RESET}")
        except Exception as e:
            self.log(f"  {RED}✗ Memory read failed: {e}{RESET}")
            return False

        # Test 4: Input injection (if in gameplay mode)
        if state["mode"] in (0x07, 0x09):  # Dungeon or Overworld
            self.log("\n4. Testing input injection...")
            start_x = state["link_x"]
            self.client.hold_direction("right", frames=15)
            time.sleep(0.3)
            new_state = self.client.get_oracle_state()
            delta = new_state["link_x"] - start_x
            if delta > 0:
                self.log(f"  Moved right by {delta} pixels")
                self.log(f"  {GREEN}✓ Input injection working{RESET}")
            else:
                self.log(f"  {YELLOW}⚠ No movement detected (may be blocked){RESET}")
        else:
            self.log(f"\n4. Skipping input test (not in gameplay mode)")

        self.log(f"\n{GREEN}=== Smoke Test Passed ==={RESET}")
        return True

    def capture_state(self, name: str, tags: list = None) -> dict:
        """Capture current game state for library."""
        state = self.client.get_oracle_state()
        story = self.client.get_story_state()

        metadata = {
            "id": name,
            "description": f"Captured state: {name}",
            "tags": tags or ["captured"],
            "gameState": {
                "mode": f"0x{state['mode']:02X}",
                "submode": f"0x{state['submode']:02X}",
                "area": f"0x{state['area']:02X}",
                "room": f"0x{state['room']:02X}",
                "indoors": bool(state["indoors"]),
            },
            "position": {
                "x": state["link_x"],
                "y": state["link_y"],
                "direction": state["link_dir_name"],
            },
            "story": {
                "game_state": story["game_state"],
                "oosprog": f"0x{story['oosprog']:02X}",
                "oosprog2": f"0x{story['oosprog2']:02X}",
                "crystals": f"0x{story['crystals']:02X}",
                "pendants": f"0x{story['pendants']:02X}",
            },
        }

        return metadata


def main():
    parser = argparse.ArgumentParser(description="Oracle of Secrets Gameplay Tests")
    subparsers = parser.add_subparsers(dest="command")

    # Run command
    run_parser = subparsers.add_parser("run", help="Run test file(s)")
    run_parser.add_argument("tests", nargs="+", help="Test JSON files")
    run_parser.add_argument("-v", "--verbose", action="store_true")

    # Smoke command
    smoke_parser = subparsers.add_parser("smoke", help="Run smoke test")
    smoke_parser.add_argument("-v", "--verbose", action="store_true")

    # Capture command
    capture_parser = subparsers.add_parser("capture", help="Capture state metadata")
    capture_parser.add_argument("name", help="State name/ID")
    capture_parser.add_argument("--tag", "-t", action="append", help="Tags")

    args = parser.parse_args()

    runner = GameplayTestRunner()

    if args.command == "smoke":
        runner.verbose = getattr(args, "verbose", False)
        ok = runner.run_smoke_test()
        sys.exit(0 if ok else 1)

    elif args.command == "run":
        runner.verbose = args.verbose
        passed = 0
        failed = 0

        for test_pattern in args.tests:
            test_path = Path(test_pattern)
            if test_path.is_file():
                result = runner.run_test(test_path)
                if result == "passed":
                    passed += 1
                else:
                    failed += 1

        print(f"\nResults: {passed} passed, {failed} failed")
        sys.exit(0 if failed == 0 else 1)

    elif args.command == "capture":
        metadata = runner.capture_state(args.name, args.tag)
        print(json.dumps(metadata, indent=2))

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
