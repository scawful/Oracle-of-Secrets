# -*- coding: utf-8 -*-
"""Iteration 64 - Autonomous Transition Testing Module.

This module provides automated testing of game transitions (overworld→cave,
cave→overworld, dungeon→room, etc.) with black screen detection.

Goal B (Black Screen Bug Resolution) requires testing all transition types
and capturing any failures with detailed diagnostic state.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any
import json
import time


class TransitionType(Enum):
    """Types of transitions in Oracle of Secrets."""
    OVERWORLD_TO_CAVE = auto()
    CAVE_TO_OVERWORLD = auto()
    OVERWORLD_TO_DUNGEON = auto()
    DUNGEON_TO_OVERWORLD = auto()
    INTRA_DUNGEON = auto()  # Room-to-room within dungeon
    OVERWORLD_SCREEN = auto()  # Screen edge transition


@dataclass
class TransitionState:
    """Captured state during a transition."""
    timestamp: str
    game_mode: int
    submodule: int
    inidisp: int
    link_x: int
    link_y: int
    area_id: int = 0
    room_id: int = 0
    frame_count: int = 0

    @property
    def is_black_screen(self) -> bool:
        """Detect black screen condition.

        Black screen = Mode 0x07 + INIDISP 0x80 + Submodule 0x00
        """
        return (
            self.game_mode == 0x07 and
            self.inidisp == 0x80 and
            self.submodule == 0x00
        )

    @property
    def is_transitioning(self) -> bool:
        """Check if currently in transition mode."""
        return self.game_mode == 0x06

    @property
    def is_indoors(self) -> bool:
        """Check if indoors (dungeon/cave)."""
        return self.game_mode == 0x07

    @property
    def is_overworld(self) -> bool:
        """Check if on overworld."""
        return self.game_mode == 0x09


@dataclass
class TransitionResult:
    """Result of a transition test."""
    transition_type: TransitionType
    success: bool
    start_state: TransitionState
    end_state: TransitionState
    intermediate_states: list[TransitionState] = field(default_factory=list)
    black_screen_detected: bool = False
    black_screen_frame: int | None = None
    duration_frames: int = 0
    error_message: str | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "transition_type": self.transition_type.name,
            "success": self.success,
            "black_screen_detected": self.black_screen_detected,
            "black_screen_frame": self.black_screen_frame,
            "duration_frames": self.duration_frames,
            "error_message": self.error_message,
            "start_state": {
                "game_mode": hex(self.start_state.game_mode),
                "submodule": hex(self.start_state.submodule),
                "inidisp": hex(self.start_state.inidisp),
                "position": (self.start_state.link_x, self.start_state.link_y),
            },
            "end_state": {
                "game_mode": hex(self.end_state.game_mode),
                "submodule": hex(self.end_state.submodule),
                "inidisp": hex(self.end_state.inidisp),
                "position": (self.end_state.link_x, self.end_state.link_y),
            },
        }


class TransitionTester:
    """Tests game transitions for black screen bugs.

    Uses Mesen2 socket API to:
    1. Load save states at specific positions
    2. Inject directional inputs to trigger transitions
    3. Monitor INIDISP, GameMode, Submodule during transition
    4. Detect and report black screen conditions
    """

    # SNES memory addresses
    ADDR_GAME_MODE = 0x7E0010
    ADDR_SUBMODULE = 0x7E0011
    ADDR_INIDISP = 0x7E001A
    ADDR_LINK_X = 0x7E0022
    ADDR_LINK_Y = 0x7E0020
    ADDR_AREA_ID = 0x7E008A
    ADDR_ROOM_ID = 0x7E00A0

    def __init__(self, bridge: Any):
        """Initialize with Mesen2 bridge connection.

        Args:
            bridge: MesenBridge instance connected to running emulator
        """
        self.bridge = bridge
        self.results: list[TransitionResult] = []

    def capture_state(self) -> TransitionState:
        """Capture current game state for analysis."""
        return TransitionState(
            timestamp=datetime.now().isoformat(),
            game_mode=self.bridge.read_memory(self.ADDR_GAME_MODE),
            submodule=self.bridge.read_memory(self.ADDR_SUBMODULE),
            inidisp=self.bridge.read_memory(self.ADDR_INIDISP),
            link_x=self.bridge.read_memory16(self.ADDR_LINK_X),
            link_y=self.bridge.read_memory16(self.ADDR_LINK_Y),
            area_id=self.bridge.read_memory(self.ADDR_AREA_ID),
            room_id=self.bridge.read_memory(self.ADDR_ROOM_ID),
        )

    def wait_for_stable_state(
        self,
        timeout_frames: int = 180,
        poll_interval_frames: int = 5
    ) -> tuple[bool, list[TransitionState]]:
        """Wait for game to reach stable state after transition.

        Monitors INIDISP and GameMode until:
        - Normal gameplay (Mode 0x07 or 0x09, INIDISP != 0x80)
        - Black screen detected (Mode 0x07, INIDISP 0x80, Sub 0x00)
        - Timeout

        Returns:
            Tuple of (success, list of captured intermediate states)
        """
        states: list[TransitionState] = []
        frames_elapsed = 0
        stable_frames = 0
        last_mode = -1

        while frames_elapsed < timeout_frames:
            # Run a few frames
            self.bridge.run_frames(poll_interval_frames)
            frames_elapsed += poll_interval_frames

            # Capture state
            state = self.capture_state()
            state.frame_count = frames_elapsed
            states.append(state)

            # Check for black screen (failure)
            if state.is_black_screen:
                return False, states

            # Check for stable gameplay
            if not state.is_transitioning:
                # Same mode for multiple captures = stable
                if state.game_mode == last_mode:
                    stable_frames += poll_interval_frames
                    if stable_frames >= 30:  # ~0.5 seconds
                        return True, states
                else:
                    stable_frames = 0
                    last_mode = state.game_mode

        # Timeout - might still be ok if last state wasn't black screen
        return not states[-1].is_black_screen if states else False, states

    def test_transition(
        self,
        transition_type: TransitionType,
        direction: str,
        hold_frames: int = 60,
        setup_state_path: str | None = None
    ) -> TransitionResult:
        """Test a specific transition.

        Args:
            transition_type: Type of transition being tested
            direction: Direction to move ("UP", "DOWN", "LEFT", "RIGHT")
            hold_frames: How long to hold direction
            setup_state_path: Optional save state to load first

        Returns:
            TransitionResult with detailed analysis
        """
        # Load setup state if provided
        if setup_state_path:
            if not self.bridge.load_state(path=setup_state_path):
                return TransitionResult(
                    transition_type=transition_type,
                    success=False,
                    start_state=TransitionState(
                        timestamp=datetime.now().isoformat(),
                        game_mode=0, submodule=0, inidisp=0,
                        link_x=0, link_y=0
                    ),
                    end_state=TransitionState(
                        timestamp=datetime.now().isoformat(),
                        game_mode=0, submodule=0, inidisp=0,
                        link_x=0, link_y=0
                    ),
                    error_message=f"Failed to load state: {setup_state_path}"
                )
            # Wait for state to load
            self.bridge.run_frames(10)

        # Capture start state
        start_state = self.capture_state()

        # Execute transition by moving in direction
        self.bridge.press_button(direction, hold_frames)

        # Wait for transition to complete
        success, intermediate_states = self.wait_for_stable_state()

        # Capture end state
        end_state = self.capture_state()

        # Check for black screen in intermediate states
        black_screen_frame = None
        for state in intermediate_states:
            if state.is_black_screen:
                black_screen_frame = state.frame_count
                break

        # Determine total duration
        duration = intermediate_states[-1].frame_count if intermediate_states else 0

        result = TransitionResult(
            transition_type=transition_type,
            success=success and black_screen_frame is None,
            start_state=start_state,
            end_state=end_state,
            intermediate_states=intermediate_states,
            black_screen_detected=black_screen_frame is not None,
            black_screen_frame=black_screen_frame,
            duration_frames=duration,
        )

        self.results.append(result)
        return result

    def test_overworld_to_cave(
        self,
        state_path: str | None = None
    ) -> TransitionResult:
        """Test transition from overworld into a cave/building.

        This is the primary black screen bug vector.
        """
        return self.test_transition(
            TransitionType.OVERWORLD_TO_CAVE,
            direction="UP",
            hold_frames=90,  # Walk into entrance
            setup_state_path=state_path
        )

    def test_cave_to_overworld(
        self,
        state_path: str | None = None
    ) -> TransitionResult:
        """Test transition from cave/building to overworld."""
        return self.test_transition(
            TransitionType.CAVE_TO_OVERWORLD,
            direction="DOWN",
            hold_frames=90,
            setup_state_path=state_path
        )

    def run_comprehensive_test(
        self,
        state_library_path: str | None = None
    ) -> dict[str, Any]:
        """Run all transition tests using available save states.

        Returns:
            Summary dict with all test results
        """
        summary = {
            "timestamp": datetime.now().isoformat(),
            "tests_run": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "black_screens_detected": 0,
            "results": []
        }

        # Test current state (whatever is loaded)
        print("Testing current state transitions...")

        # Move in each direction to test screen edges
        for direction in ["UP", "DOWN", "LEFT", "RIGHT"]:
            print(f"  Testing {direction} movement...")
            result = self.test_transition(
                TransitionType.OVERWORLD_SCREEN,
                direction=direction,
                hold_frames=120
            )
            summary["tests_run"] += 1
            if result.success:
                summary["tests_passed"] += 1
            else:
                summary["tests_failed"] += 1
            if result.black_screen_detected:
                summary["black_screens_detected"] += 1
            summary["results"].append(result.to_dict())

        return summary

    def save_results(self, output_path: str) -> None:
        """Save test results to JSON file."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": len(self.results),
            "passed": sum(1 for r in self.results if r.success),
            "failed": sum(1 for r in self.results if not r.success),
            "black_screens": sum(1 for r in self.results if r.black_screen_detected),
            "results": [r.to_dict() for r in self.results]
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)


def run_live_test():
    """Run transition tests against live Mesen2 instance."""
    try:
        from scripts.mesen2_client_lib.bridge import MesenBridge
    except ImportError:
        print("ERROR: Could not import MesenBridge. Are the oracle-of-secrets scripts available?")
        return None

    # Connect to Mesen2
    bridge = MesenBridge()
    if not bridge.is_connected():
        print("ERROR: Cannot connect to Mesen2. Is it running?")
        print("Available sockets:", bridge.socket_path)
        return None

    print(f"Connected to Mesen2 at {bridge.socket_path}")

    # Create tester
    tester = TransitionTester(bridge)

    # Capture initial state
    state = tester.capture_state()
    print(f"\nCurrent state:")
    print(f"  Mode: {hex(state.game_mode)}")
    print(f"  Submodule: {hex(state.submodule)}")
    print(f"  INIDISP: {hex(state.inidisp)}")
    print(f"  Position: ({state.link_x}, {state.link_y})")
    print(f"  Black screen: {state.is_black_screen}")

    # Run tests
    print("\n" + "="*50)
    print("Running transition tests...")
    print("="*50)

    results = tester.run_comprehensive_test()

    # Summary
    print("\n" + "="*50)
    print("TRANSITION TEST SUMMARY")
    print("="*50)
    print(f"Tests run:    {results['tests_run']}")
    print(f"Passed:       {results['tests_passed']}")
    print(f"Failed:       {results['tests_failed']}")
    print(f"Black screens: {results['black_screens_detected']}")

    # Save results
    output_path = "Docs/Campaign/Evidence/iteration-064/transition_results.json"
    tester.save_results(output_path)
    print(f"\nResults saved to: {output_path}")

    return results


if __name__ == "__main__":
    run_live_test()
