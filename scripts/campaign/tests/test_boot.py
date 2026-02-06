"""Boot verification test for Oracle of Secrets.

This test verifies that the ROM boots to a playable state.
Part of Campaign Goal C.3 (Automated regression suite).

Usage:
    # With pytest
    pytest scripts/campaign/tests/test_boot.py -v

    # Standalone (requires Mesen2 running)
    python3 scripts/campaign/tests/test_boot.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

# Add parent to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.campaign import (
    GamePhase,
    GameStateParser,
    Mesen2Emulator,
    parse_state,
)


class TestBoot:
    """Test suite for boot verification."""

    @classmethod
    def setup_class(cls):
        """Set up emulator connection for all tests."""
        cls.emu = Mesen2Emulator()
        cls.parser = GameStateParser()
        cls._connected = False

        try:
            cls._connected = cls.emu.connect()
        except Exception as e:
            print(f"Warning: Could not connect to emulator: {e}")

    def test_emulator_connection(self):
        """Test that we can connect to Mesen2."""
        if not self._connected:
            raise AssertionError(
                "Cannot connect to Mesen2. "
                "Ensure emulator is running with socket enabled."
            )
        assert self.emu.is_connected(), "Emulator should be connected"

    def test_state_readable(self):
        """Test that we can read game state."""
        if not self._connected:
            raise AssertionError("Not connected to emulator")

        state = self.emu.read_state()

        assert state is not None, "State should not be None"
        assert 0 <= state.mode <= 0x20, f"Mode {state.mode:#x} out of expected range"
        assert 0 <= state.submode <= 0xFF, "Submode out of range"

    def test_state_parsing(self):
        """Test semantic state parsing."""
        if not self._connected:
            raise AssertionError("Not connected to emulator")

        raw_state = self.emu.read_state()
        parsed = parse_state(raw_state)

        assert parsed is not None, "Parsed state should not be None"
        assert isinstance(parsed.phase, GamePhase), "Phase should be GamePhase enum"
        assert parsed.location_name, "Location name should not be empty"

    def test_not_black_screen(self):
        """Test that game is not in black screen state."""
        if not self._connected:
            raise AssertionError("Not connected to emulator")

        raw_state = self.emu.read_state()
        parsed = parse_state(raw_state)

        assert not parsed.is_black_screen, (
            f"Game is in black screen state! "
            f"Mode={raw_state.mode:#x}, INIDISP={raw_state.inidisp:#x}"
        )

    def test_playable_state(self):
        """Test that game is in a playable state (overworld or dungeon)."""
        if not self._connected:
            raise AssertionError("Not connected to emulator")

        raw_state = self.emu.read_state()
        parsed = parse_state(raw_state)

        assert parsed.is_playing, (
            f"Game not in playable state. "
            f"Phase={parsed.phase.name}, Mode={raw_state.mode:#x}"
        )

    def test_link_position_valid(self):
        """Test that Link's position is within valid range."""
        if not self._connected:
            raise AssertionError("Not connected to emulator")

        raw_state = self.emu.read_state()

        # Link position should be within world bounds
        # Typical overworld is 8192x8192, dungeons smaller
        assert 0 <= raw_state.link_x <= 16384, f"Link X {raw_state.link_x} out of bounds"
        assert 0 <= raw_state.link_y <= 16384, f"Link Y {raw_state.link_y} out of bounds"


def run_standalone():
    """Run tests standalone without pytest."""
    print("=" * 60)
    print("Oracle of Secrets Boot Test")
    print("=" * 60)

    emu = Mesen2Emulator()
    parser = GameStateParser()

    print("\n1. Testing emulator connection...")
    try:
        connected = emu.connect()
        if not connected:
            print("   FAIL: Could not connect to Mesen2")
            print("   Make sure Mesen2 is running with socket enabled")
            return False
        print("   PASS: Connected to Mesen2")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    print("\n2. Reading game state...")
    try:
        state = emu.read_state()
        print(f"   Mode: {state.mode:#04x}")
        print(f"   Submode: {state.submode:#04x}")
        print(f"   INIDISP: {state.inidisp:#04x}")
        print(f"   Link Position: ({state.link_x}, {state.link_y})")
        print("   PASS: State readable")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    print("\n3. Parsing game state semantically...")
    try:
        parsed = parser.parse(state)
        print(f"   Phase: {parsed.phase.name}")
        print(f"   Location: {parsed.location_name}")
        print(f"   Action: {parsed.link_action.name}")
        print(f"   Is Playing: {parsed.is_playing}")
        print(f"   Is Black Screen: {parsed.is_black_screen}")
        print("   PASS: Semantic parsing works")
    except Exception as e:
        print(f"   FAIL: {e}")
        return False

    print("\n4. Checking for black screen...")
    if parsed.is_black_screen:
        print(f"   FAIL: Black screen detected!")
        print(f"   Mode={state.mode:#x}, INIDISP={state.inidisp:#x}")
        return False
    print("   PASS: No black screen")

    print("\n5. Checking playable state...")
    if not parsed.is_playing:
        print(f"   WARN: Not in playable state (Phase={parsed.phase.name})")
        print("   This may be expected if in menu/cutscene")
    else:
        print("   PASS: In playable state")

    print("\n" + "=" * 60)
    print("All basic tests passed!")
    print("=" * 60)
    return True


if __name__ == "__main__":
    success = run_standalone()
    sys.exit(0 if success else 1)
