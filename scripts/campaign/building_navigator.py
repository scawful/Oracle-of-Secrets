# -*- coding: utf-8 -*-
"""Building Navigation Module for Goal A.3 - Enter/Exit Buildings.

This module provides autonomous navigation for entering and exiting
buildings, caves, and dungeons in Oracle of Secrets.

Campaign Goals Supported:
- A.3: Enter and exit buildings/caves/dungeons
- B.5: Regression test all transition types

The module combines:
- Location awareness (from locations.py)
- Action planning (from action_planner.py)
- Transition testing (from transition_tester.py)

Usage:
    from scripts.campaign.building_navigator import BuildingNavigator

    navigator = BuildingNavigator(bridge)
    result = navigator.enter_nearest_building()
    result = navigator.exit_to_overworld()
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Optional
import json
import time

from .locations import (
    ENTRANCE_NAMES,
    OVERWORLD_AREAS,
    ROOM_NAMES,
    get_area_name,
    get_entrance_name,
    get_room_name,
)


class BuildingType(Enum):
    """Types of enterable buildings in the game."""
    HOUSE = auto()
    CAVE = auto()
    DUNGEON = auto()
    SHOP = auto()
    FAIRY_FOUNTAIN = auto()
    SPECIAL = auto()
    UNKNOWN = auto()


class NavigationResult(Enum):
    """Result of a navigation attempt."""
    SUCCESS = auto()
    FAILED_NO_ENTRANCE = auto()
    FAILED_BLACK_SCREEN = auto()
    FAILED_TIMEOUT = auto()
    FAILED_WRONG_MODE = auto()
    FAILED_STUCK = auto()


@dataclass
class BuildingInfo:
    """Information about a building/entrance."""
    entrance_id: int
    name: str
    building_type: BuildingType
    overworld_area: int
    target_room: Optional[int] = None
    x_position: Optional[int] = None
    y_position: Optional[int] = None
    direction: str = "UP"  # Direction to walk to enter


@dataclass
class NavigationState:
    """Captured state during navigation."""
    timestamp: str
    game_mode: int
    submodule: int
    inidisp: int
    link_x: int
    link_y: int
    area_id: int
    room_id: int
    frame_count: int = 0

    @property
    def is_indoors(self) -> bool:
        """Check if currently indoors."""
        return self.game_mode == 0x07

    @property
    def is_overworld(self) -> bool:
        """Check if on overworld."""
        return self.game_mode == 0x09

    @property
    def is_transitioning(self) -> bool:
        """Check if in transition mode."""
        return self.game_mode == 0x06

    @property
    def is_black_screen(self) -> bool:
        """Detect potential black screen (needs stuck detection)."""
        return (
            self.game_mode == 0x07 and
            self.inidisp == 0x80 and
            self.submodule == 0x00
        )


@dataclass
class NavigationAttempt:
    """Result of a navigation attempt."""
    result: NavigationResult
    start_state: NavigationState
    end_state: NavigationState
    target_building: Optional[BuildingInfo] = None
    transition_states: list[NavigationState] = field(default_factory=list)
    duration_frames: int = 0
    error_message: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        """Serialize to dictionary."""
        return {
            "result": self.result.name,
            "target_building": self.target_building.name if self.target_building else None,
            "duration_frames": self.duration_frames,
            "error_message": self.error_message,
            "start": {
                "mode": hex(self.start_state.game_mode),
                "position": (self.start_state.link_x, self.start_state.link_y),
                "area": hex(self.start_state.area_id),
                "room": hex(self.start_state.room_id),
            },
            "end": {
                "mode": hex(self.end_state.game_mode),
                "position": (self.end_state.link_x, self.end_state.link_y),
                "area": hex(self.end_state.area_id),
                "room": hex(self.end_state.room_id),
            },
            "mode_changed": (
                self.start_state.game_mode != self.end_state.game_mode
            ),
        }


# Known building entrances with positions
# Format: (area_id, approx_x, approx_y, direction, building_type, target_room)
KNOWN_ENTRANCES: list[tuple[int, int, int, str, BuildingType, int]] = [
    # Link's House area (0x29 Village Center)
    (0x29, 1000, 1432, "UP", BuildingType.HOUSE, 0x00),  # Link's House

    # Village buildings
    (0x29, 896, 1360, "UP", BuildingType.SHOP, 0x00),    # Village shop
    (0x28, 768, 1488, "UP", BuildingType.HOUSE, 0x00),   # Village South house

    # Ranch area
    (0x00, 520, 352, "UP", BuildingType.HOUSE, 0x00),    # Loom Ranch house
    (0x38, 400, 624, "UP", BuildingType.HOUSE, 0x00),    # Ranch Area house

    # Caves and dungeons
    (0x40, 256, 368, "UP", BuildingType.CAVE, 0x06),     # Lost Woods cave
    (0x1E, 512, 496, "UP", BuildingType.DUNGEON, 0x28),  # Zora Temple entrance

    # Fairy fountains
    (0x08, 256, 352, "UP", BuildingType.FAIRY_FOUNTAIN, 0x08),
]


class BuildingNavigator:
    """Autonomous building entry/exit navigation.

    This class provides high-level building navigation that:
    1. Identifies nearby entrances based on current position
    2. Navigates Link to the entrance
    3. Enters the building and monitors for black screens
    4. Can exit buildings back to overworld

    Designed to advance Goal A.3: Enter and exit buildings/caves/dungeons.
    """

    # SNES memory addresses
    ADDR_GAME_MODE = 0x7E0010
    ADDR_SUBMODULE = 0x7E0011
    ADDR_INIDISP = 0x7E0013  # INIDISP queue (WRAM)
    ADDR_LINK_X = 0x7E0022
    ADDR_LINK_Y = 0x7E0020
    ADDR_AREA_ID = 0x7E008A
    ADDR_ROOM_ID = 0x7E00A0

    def __init__(self, bridge: Any):
        """Initialize with Mesen2 bridge.

        Args:
            bridge: MesenBridge instance connected to emulator
        """
        self.bridge = bridge
        self.attempts: list[NavigationAttempt] = []

    def capture_state(self, frame_count: int = 0) -> NavigationState:
        """Capture current navigation state."""
        return NavigationState(
            timestamp=datetime.now().isoformat(),
            game_mode=self.bridge.read_memory(self.ADDR_GAME_MODE),
            submodule=self.bridge.read_memory(self.ADDR_SUBMODULE),
            inidisp=self.bridge.read_memory(self.ADDR_INIDISP),
            link_x=self.bridge.read_memory16(self.ADDR_LINK_X),
            link_y=self.bridge.read_memory16(self.ADDR_LINK_Y),
            area_id=self.bridge.read_memory(self.ADDR_AREA_ID),
            room_id=self.bridge.read_memory(self.ADDR_ROOM_ID),
            frame_count=frame_count,
        )

    def find_nearest_entrance(self, state: NavigationState) -> Optional[BuildingInfo]:
        """Find nearest known entrance to current position.

        Args:
            state: Current navigation state

        Returns:
            BuildingInfo for nearest entrance, or None if none nearby
        """
        if not state.is_overworld:
            return None

        best_distance = float('inf')
        best_entrance = None

        for area, x, y, direction, btype, room in KNOWN_ENTRANCES:
            if area != state.area_id:
                continue

            # Calculate distance
            dx = x - state.link_x
            dy = y - state.link_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < best_distance:
                best_distance = distance
                best_entrance = BuildingInfo(
                    entrance_id=len(KNOWN_ENTRANCES),  # placeholder
                    name=f"Entrance at ({x}, {y})",
                    building_type=btype,
                    overworld_area=area,
                    target_room=room,
                    x_position=x,
                    y_position=y,
                    direction=direction,
                )

        return best_entrance

    def walk_toward(
        self,
        target_x: int,
        target_y: int,
        tolerance: int = 32,
        max_frames: int = 300
    ) -> bool:
        """Walk Link toward a target position.

        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            tolerance: Distance considered "arrived"
            max_frames: Maximum frames to attempt

        Returns:
            True if reached target, False if timeout/stuck
        """
        frames_elapsed = 0
        last_position = (0, 0)
        stuck_count = 0

        while frames_elapsed < max_frames:
            state = self.capture_state(frames_elapsed)

            # Check if arrived
            dx = target_x - state.link_x
            dy = target_y - state.link_y
            distance = (dx**2 + dy**2) ** 0.5

            if distance < tolerance:
                return True

            # Determine direction
            if abs(dx) > abs(dy):
                direction = "RIGHT" if dx > 0 else "LEFT"
            else:
                direction = "DOWN" if dy > 0 else "UP"

            # Move
            self.bridge.press_button(direction, 15)
            frames_elapsed += 15

            # Check if stuck
            current_position = (state.link_x, state.link_y)
            if current_position == last_position:
                stuck_count += 1
                if stuck_count > 5:
                    return False
            else:
                stuck_count = 0
            last_position = current_position

        return False

    def wait_for_transition(
        self,
        timeout_frames: int = 180,
        poll_interval: int = 5
    ) -> tuple[NavigationResult, list[NavigationState]]:
        """Wait for transition to complete.

        Monitors for:
        - Successful mode change (OW→Indoor or Indoor→OW)
        - Black screen (stuck INIDISP=0x80)
        - Timeout

        Returns:
            Tuple of (result, list of intermediate states)
        """
        states: list[NavigationState] = []
        frames_elapsed = 0
        black_screen_count = 0  # Count consecutive black screen samples

        while frames_elapsed < timeout_frames:
            self.bridge.run_frames(poll_interval)
            frames_elapsed += poll_interval

            state = self.capture_state(frames_elapsed)
            states.append(state)

            # Check for stuck black screen (30+ samples = ~0.5s)
            if state.is_black_screen:
                black_screen_count += 1
                if black_screen_count >= 30:
                    return NavigationResult.FAILED_BLACK_SCREEN, states
            else:
                black_screen_count = 0

            # Check for stable non-transitioning state
            if not state.is_transitioning:
                # Give a few more samples to confirm stability
                stable_count = 0
                for _ in range(6):
                    self.bridge.run_frames(poll_interval)
                    frames_elapsed += poll_interval
                    check_state = self.capture_state(frames_elapsed)
                    states.append(check_state)
                    if not check_state.is_transitioning:
                        stable_count += 1

                if stable_count >= 4:
                    return NavigationResult.SUCCESS, states

        return NavigationResult.FAILED_TIMEOUT, states

    def enter_building(
        self,
        building: Optional[BuildingInfo] = None,
        direction: str = "UP",
        hold_frames: int = 90
    ) -> NavigationAttempt:
        """Attempt to enter a building.

        If no building specified, walks in the given direction hoping
        to hit an entrance.

        Args:
            building: Optional building info with position
            direction: Direction to walk (default UP for most entrances)
            hold_frames: How long to hold direction

        Returns:
            NavigationAttempt with result
        """
        start_state = self.capture_state()

        # Verify we're on overworld
        if not start_state.is_overworld:
            return NavigationAttempt(
                result=NavigationResult.FAILED_WRONG_MODE,
                start_state=start_state,
                end_state=start_state,
                target_building=building,
                error_message="Not on overworld - cannot enter building",
            )

        # Navigate to building if specified
        if building and building.x_position and building.y_position:
            arrived = self.walk_toward(
                building.x_position,
                building.y_position,
                tolerance=48,  # Get close but not exact
            )
            if not arrived:
                end_state = self.capture_state()
                return NavigationAttempt(
                    result=NavigationResult.FAILED_NO_ENTRANCE,
                    start_state=start_state,
                    end_state=end_state,
                    target_building=building,
                    error_message="Could not reach building entrance",
                )
            direction = building.direction

        # Walk into entrance
        self.bridge.press_button(direction, hold_frames)

        # Wait for transition
        result, transition_states = self.wait_for_transition()

        end_state = self.capture_state()
        duration = transition_states[-1].frame_count if transition_states else 0

        # Verify we're now indoors
        if result == NavigationResult.SUCCESS and not end_state.is_indoors:
            result = NavigationResult.FAILED_NO_ENTRANCE

        attempt = NavigationAttempt(
            result=result,
            start_state=start_state,
            end_state=end_state,
            target_building=building,
            transition_states=transition_states,
            duration_frames=duration,
        )

        self.attempts.append(attempt)
        return attempt

    def exit_building(self, hold_frames: int = 90) -> NavigationAttempt:
        """Attempt to exit current building to overworld.

        Most exits are by walking DOWN through the door.

        Args:
            hold_frames: How long to hold direction

        Returns:
            NavigationAttempt with result
        """
        start_state = self.capture_state()

        # Verify we're indoors
        if not start_state.is_indoors:
            return NavigationAttempt(
                result=NavigationResult.FAILED_WRONG_MODE,
                start_state=start_state,
                end_state=start_state,
                error_message="Not indoors - cannot exit building",
            )

        # Walk toward exit (usually down)
        self.bridge.press_button("DOWN", hold_frames)

        # Wait for transition
        result, transition_states = self.wait_for_transition()

        end_state = self.capture_state()
        duration = transition_states[-1].frame_count if transition_states else 0

        # Verify we're now on overworld
        if result == NavigationResult.SUCCESS and not end_state.is_overworld:
            # Might still be in a multi-room building
            result = NavigationResult.FAILED_STUCK

        attempt = NavigationAttempt(
            result=result,
            start_state=start_state,
            end_state=end_state,
            transition_states=transition_states,
            duration_frames=duration,
        )

        self.attempts.append(attempt)
        return attempt

    def enter_nearest_building(self) -> NavigationAttempt:
        """Find and enter the nearest building.

        Returns:
            NavigationAttempt with result
        """
        state = self.capture_state()
        building = self.find_nearest_entrance(state)

        if building:
            return self.enter_building(building)
        else:
            # No known entrance nearby - try walking up
            return self.enter_building(direction="UP")

    def round_trip_test(self) -> tuple[NavigationAttempt, Optional[NavigationAttempt]]:
        """Test entering a building and immediately exiting.

        This is the core test for Goal A.3 milestone validation.

        Returns:
            Tuple of (enter_attempt, exit_attempt or None if enter failed)
        """
        # Enter
        enter_result = self.enter_nearest_building()

        if enter_result.result != NavigationResult.SUCCESS:
            return enter_result, None

        # Small delay to ensure state is stable
        self.bridge.run_frames(30)

        # Exit
        exit_result = self.exit_building()

        return enter_result, exit_result

    def save_results(self, output_path: str) -> None:
        """Save navigation results to JSON."""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_attempts": len(self.attempts),
            "successful": sum(1 for a in self.attempts if a.result == NavigationResult.SUCCESS),
            "failed": sum(1 for a in self.attempts if a.result != NavigationResult.SUCCESS),
            "black_screens": sum(
                1 for a in self.attempts
                if a.result == NavigationResult.FAILED_BLACK_SCREEN
            ),
            "attempts": [a.to_dict() for a in self.attempts],
        }

        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)


def run_building_test():
    """Run building entry/exit test against live Mesen2."""
    try:
        from scripts.mesen2_client_lib.bridge import MesenBridge
    except ImportError:
        print("ERROR: Could not import MesenBridge")
        return None

    bridge = MesenBridge()
    if not bridge.is_connected():
        print("ERROR: Cannot connect to Mesen2")
        return None

    print(f"Connected to Mesen2")

    navigator = BuildingNavigator(bridge)

    # Capture initial state
    state = navigator.capture_state()
    print(f"\nCurrent state:")
    print(f"  Mode: {hex(state.game_mode)} ({'Indoors' if state.is_indoors else 'Overworld'})")
    print(f"  Area: {get_area_name(state.area_id)} (0x{state.area_id:02X})")
    print(f"  Position: ({state.link_x}, {state.link_y})")

    # Check for nearby entrance
    nearest = navigator.find_nearest_entrance(state)
    if nearest:
        print(f"  Nearest entrance: {nearest.name} ({nearest.building_type.name})")
    else:
        print(f"  No known entrances nearby")

    # Run round-trip test
    print("\n" + "="*50)
    print("BUILDING ROUND-TRIP TEST")
    print("="*50)

    enter_result, exit_result = navigator.round_trip_test()

    print(f"\nEnter result: {enter_result.result.name}")
    if enter_result.result == NavigationResult.SUCCESS:
        print(f"  Mode: {hex(enter_result.start_state.game_mode)} -> {hex(enter_result.end_state.game_mode)}")
        print(f"  Duration: {enter_result.duration_frames} frames")

    if exit_result:
        print(f"\nExit result: {exit_result.result.name}")
        if exit_result.result == NavigationResult.SUCCESS:
            print(f"  Mode: {hex(exit_result.start_state.game_mode)} -> {hex(exit_result.end_state.game_mode)}")
            print(f"  Duration: {exit_result.duration_frames} frames")

    # Save results
    output_path = "Docs/Campaign/Evidence/iteration-066/building_navigation.json"
    navigator.save_results(output_path)
    print(f"\nResults saved to: {output_path}")

    return navigator


if __name__ == "__main__":
    run_building_test()
