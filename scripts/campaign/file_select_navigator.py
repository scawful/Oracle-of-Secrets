# -*- coding: utf-8 -*-
"""File Select Screen Navigation for Goal A.2.

This module provides autonomous navigation of the file select screen,
enabling automated game start for testing and gameplay automation.

Campaign Goals Supported:
- A.2: Navigate file select
- A.3: Start new game (integrates with this module)

The file select screen in Oracle of Secrets has:
- 3 save file slots (1-3)
- Copy/Erase options
- Visual cursor indicator

Memory Layout (from vanilla ALTTP):
- $7E0010: GameMode (0x02 = file select)
- $7E0200: Current cursor position (0-2 for slots, 3-4 for copy/erase)
- $7E0202: File select sub-state

Usage:
    from scripts.campaign.file_select_navigator import FileSelectNavigator

    navigator = FileSelectNavigator(bridge)
    result = navigator.select_file(slot=1)
    if result.success:
        print(f"Loaded file {result.slot}")
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple
import json
import time


class FileSelectState(Enum):
    """States of the file select screen."""
    NOT_ON_SCREEN = auto()      # Not on file select screen
    MAIN_MENU = auto()          # Viewing main file list
    SLOT_SELECTED = auto()       # Cursor on a slot
    COPY_MENU = auto()           # In copy sub-menu
    ERASE_MENU = auto()          # In erase sub-menu
    CONFIRM_DIALOG = auto()      # Confirmation dialog shown
    LOADING = auto()             # File is loading
    NAME_ENTRY = auto()          # New game name entry


class FileSlotStatus(Enum):
    """Status of a file slot."""
    EMPTY = auto()              # No save data
    HAS_DATA = auto()           # Contains save data
    UNKNOWN = auto()            # Status not determined


class SelectionResult(Enum):
    """Result of a file selection attempt."""
    SUCCESS = auto()
    FAILED_NOT_ON_SCREEN = auto()
    FAILED_TIMEOUT = auto()
    FAILED_WRONG_STATE = auto()
    FAILED_EMPTY_SLOT = auto()
    FAILED_NAVIGATION = auto()


@dataclass
class FileSlotInfo:
    """Information about a file slot."""
    slot_number: int            # 1-3
    status: FileSlotStatus
    player_name: str = ""
    heart_containers: int = 0
    death_count: int = 0
    dungeon_progress: int = 0   # Number of dungeons completed


@dataclass
class FileSelectSnapshot:
    """Captured state of file select screen."""
    timestamp: str
    game_mode: int
    cursor_position: int
    sub_state: int
    slot_states: List[FileSlotStatus] = field(default_factory=list)
    frame_count: int = 0

    @property
    def is_on_file_select(self) -> bool:
        """Check if on file select screen."""
        return self.game_mode == 0x02

    @property
    def current_slot(self) -> int:
        """Get currently highlighted slot (1-3) or 0 if on menu option."""
        if 0 <= self.cursor_position <= 2:
            return self.cursor_position + 1
        return 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "timestamp": self.timestamp,
            "game_mode": self.game_mode,
            "cursor_position": self.cursor_position,
            "sub_state": self.sub_state,
            "slot_states": [s.name for s in self.slot_states],
            "frame_count": self.frame_count,
            "is_on_file_select": self.is_on_file_select,
            "current_slot": self.current_slot,
        }


@dataclass
class NavigationAttempt:
    """Result of a navigation attempt."""
    success: bool
    slot: int
    result: SelectionResult
    start_snapshot: Optional[FileSelectSnapshot] = None
    end_snapshot: Optional[FileSelectSnapshot] = None
    inputs_used: List[str] = field(default_factory=list)
    error_message: str = ""
    duration_frames: int = 0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "success": self.success,
            "slot": self.slot,
            "result": self.result.name,
            "start_snapshot": self.start_snapshot.to_dict() if self.start_snapshot else None,
            "end_snapshot": self.end_snapshot.to_dict() if self.end_snapshot else None,
            "inputs_used": self.inputs_used,
            "error_message": self.error_message,
            "duration_frames": self.duration_frames,
        }


# Memory addresses for file select screen
class FileSelectAddresses:
    """Memory addresses for file select state."""
    GAME_MODE = 0x7E0010
    CURSOR_POSITION = 0x7E0200
    SUB_STATE = 0x7E0202
    FILE_STATUS_BASE = 0x7EF000    # Status flags for each file
    PLAYER_NAME_BASE = 0x7EF3D9    # Player name storage


class FileSelectNavigator:
    """Navigate the file select screen autonomously.

    Provides methods for:
    - Detecting file select state
    - Moving cursor between slots
    - Selecting files
    - Starting new games
    - Handling sub-menus

    Args:
        bridge: Mesen2 bridge instance for emulator control
        timeout_frames: Maximum frames to wait for operations
    """

    def __init__(self, bridge: Any, timeout_frames: int = 300):
        """Initialize the navigator.

        Args:
            bridge: Mesen2 bridge instance
            timeout_frames: Maximum frames to wait (5 seconds at 60fps)
        """
        self.bridge = bridge
        self.timeout_frames = timeout_frames
        self._frame_count = 0
        self._last_snapshot: Optional[FileSelectSnapshot] = None

    def capture_state(self) -> FileSelectSnapshot:
        """Capture current file select state from memory.

        Returns:
            FileSelectSnapshot with current state
        """
        timestamp = datetime.now().isoformat()

        # Read key memory values
        game_mode = self._read_byte(FileSelectAddresses.GAME_MODE)
        cursor_pos = self._read_byte(FileSelectAddresses.CURSOR_POSITION)
        sub_state = self._read_byte(FileSelectAddresses.SUB_STATE)

        # Detect slot states (simplified - would need more analysis)
        slot_states = []
        for i in range(3):
            # Placeholder - real implementation would check save data
            slot_states.append(FileSlotStatus.UNKNOWN)

        self._frame_count += 1
        snapshot = FileSelectSnapshot(
            timestamp=timestamp,
            game_mode=game_mode,
            cursor_position=cursor_pos,
            sub_state=sub_state,
            slot_states=slot_states,
            frame_count=self._frame_count,
        )
        self._last_snapshot = snapshot
        return snapshot

    def _read_byte(self, address: int) -> int:
        """Read a byte from memory.

        Args:
            address: Memory address to read

        Returns:
            Byte value at address (0-255)
        """
        try:
            result = self.bridge.read_memory(address, 1)
            if isinstance(result, (list, bytes)):
                return result[0] if result else 0
            return result & 0xFF
        except Exception:
            return 0

    def get_state(self) -> FileSelectState:
        """Determine current file select state.

        Returns:
            Current FileSelectState
        """
        snapshot = self.capture_state()

        if not snapshot.is_on_file_select:
            return FileSelectState.NOT_ON_SCREEN

        # Interpret sub_state for file select screen
        sub = snapshot.sub_state
        if sub == 0x00:
            return FileSelectState.MAIN_MENU
        elif sub == 0x01:
            return FileSelectState.SLOT_SELECTED
        elif sub == 0x02:
            return FileSelectState.COPY_MENU
        elif sub == 0x03:
            return FileSelectState.ERASE_MENU
        elif sub == 0x04:
            return FileSelectState.CONFIRM_DIALOG
        elif sub == 0x05:
            return FileSelectState.LOADING
        elif sub == 0x06:
            return FileSelectState.NAME_ENTRY
        else:
            return FileSelectState.MAIN_MENU

    def move_cursor_to_slot(self, target_slot: int) -> bool:
        """Move cursor to a specific slot.

        Args:
            target_slot: Target slot number (1-3)

        Returns:
            True if cursor moved successfully
        """
        if not 1 <= target_slot <= 3:
            return False

        snapshot = self.capture_state()
        if not snapshot.is_on_file_select:
            return False

        current = snapshot.current_slot
        target_pos = target_slot - 1  # Convert to 0-indexed

        # Calculate moves needed
        current_pos = snapshot.cursor_position
        if current_pos == target_pos:
            return True

        # Determine direction
        if target_pos > current_pos:
            direction = "DOWN"
            moves = target_pos - current_pos
        else:
            direction = "UP"
            moves = current_pos - target_pos

        # Execute moves
        for _ in range(moves):
            self._press_button(direction, frames=5)
            self._wait_frames(10)

        # Verify position
        snapshot = self.capture_state()
        return snapshot.cursor_position == target_pos

    def select_file(self, slot: int = 1) -> NavigationAttempt:
        """Select a file slot and load the game.

        Args:
            slot: Slot number to select (1-3)

        Returns:
            NavigationAttempt with result
        """
        start_snapshot = self.capture_state()
        inputs_used = []

        # Validate we're on file select
        if not start_snapshot.is_on_file_select:
            return NavigationAttempt(
                success=False,
                slot=slot,
                result=SelectionResult.FAILED_NOT_ON_SCREEN,
                start_snapshot=start_snapshot,
                error_message="Not on file select screen",
            )

        # Move cursor to target slot
        if not self.move_cursor_to_slot(slot):
            return NavigationAttempt(
                success=False,
                slot=slot,
                result=SelectionResult.FAILED_NAVIGATION,
                start_snapshot=start_snapshot,
                error_message=f"Could not move to slot {slot}",
            )
        inputs_used.append(f"MOVE_TO_SLOT_{slot}")

        # Press A to select
        self._press_button("A", frames=2)
        inputs_used.append("A")
        self._wait_frames(30)

        # Wait for mode change (game loading)
        success = self._wait_for_mode_change(
            from_mode=0x02,
            timeout_frames=self.timeout_frames
        )

        end_snapshot = self.capture_state()

        if success:
            return NavigationAttempt(
                success=True,
                slot=slot,
                result=SelectionResult.SUCCESS,
                start_snapshot=start_snapshot,
                end_snapshot=end_snapshot,
                inputs_used=inputs_used,
                duration_frames=self._frame_count,
            )
        else:
            return NavigationAttempt(
                success=False,
                slot=slot,
                result=SelectionResult.FAILED_TIMEOUT,
                start_snapshot=start_snapshot,
                end_snapshot=end_snapshot,
                inputs_used=inputs_used,
                error_message="Timeout waiting for game load",
                duration_frames=self._frame_count,
            )

    def start_new_game(self, slot: int = 1, player_name: str = "LINK") -> NavigationAttempt:
        """Start a new game in an empty slot.

        Args:
            slot: Slot number to use (1-3)
            player_name: Name for the player (up to 6 characters)

        Returns:
            NavigationAttempt with result
        """
        start_snapshot = self.capture_state()
        inputs_used = []

        if not start_snapshot.is_on_file_select:
            return NavigationAttempt(
                success=False,
                slot=slot,
                result=SelectionResult.FAILED_NOT_ON_SCREEN,
                start_snapshot=start_snapshot,
                error_message="Not on file select screen",
            )

        # Move to slot
        if not self.move_cursor_to_slot(slot):
            return NavigationAttempt(
                success=False,
                slot=slot,
                result=SelectionResult.FAILED_NAVIGATION,
                start_snapshot=start_snapshot,
                error_message=f"Could not move to slot {slot}",
            )
        inputs_used.append(f"MOVE_TO_SLOT_{slot}")

        # Press A to select empty slot (enters name entry)
        self._press_button("A", frames=2)
        inputs_used.append("A")
        self._wait_frames(60)

        # Wait for name entry screen
        state = self.get_state()
        if state == FileSelectState.NAME_ENTRY:
            # In name entry - would need to implement name typing
            # For now, just press START to accept default name
            self._press_button("START", frames=2)
            inputs_used.append("START")
            self._wait_frames(30)

        # Wait for mode change (intro/game start)
        success = self._wait_for_mode_change(
            from_mode=0x02,
            timeout_frames=self.timeout_frames
        )

        end_snapshot = self.capture_state()

        return NavigationAttempt(
            success=success,
            slot=slot,
            result=SelectionResult.SUCCESS if success else SelectionResult.FAILED_TIMEOUT,
            start_snapshot=start_snapshot,
            end_snapshot=end_snapshot,
            inputs_used=inputs_used,
            duration_frames=self._frame_count,
        )

    def wait_for_file_select(self, timeout_frames: int = 300) -> bool:
        """Wait for file select screen to appear.

        Args:
            timeout_frames: Maximum frames to wait

        Returns:
            True if file select screen appeared
        """
        for _ in range(timeout_frames):
            snapshot = self.capture_state()
            if snapshot.is_on_file_select:
                return True
            self._wait_frames(1)
        return False

    def _wait_for_mode_change(self, from_mode: int, timeout_frames: int) -> bool:
        """Wait for game mode to change from a specific value.

        Args:
            from_mode: Mode value to wait to leave
            timeout_frames: Maximum frames to wait

        Returns:
            True if mode changed within timeout
        """
        for _ in range(timeout_frames):
            snapshot = self.capture_state()
            if snapshot.game_mode != from_mode:
                return True
            self._wait_frames(1)
        return False

    def _press_button(self, button: str, frames: int = 5) -> None:
        """Press a button.

        Args:
            button: Button name (A, B, START, UP, DOWN, etc.)
            frames: Number of frames to hold
        """
        try:
            self.bridge.press_button(button, frames)
        except Exception:
            pass  # Swallow errors for mock testing

    def _wait_frames(self, count: int) -> None:
        """Wait for a number of frames.

        Args:
            count: Number of frames to wait
        """
        try:
            # Attempt to advance frames if emulator supports it
            for _ in range(count):
                self.bridge.run_frames(1)
                self._frame_count += 1
        except AttributeError:
            # Fallback to time-based wait
            time.sleep(count / 60.0)
            self._frame_count += count

    def get_slot_info(self, slot: int) -> Optional[FileSlotInfo]:
        """Get information about a file slot.

        Args:
            slot: Slot number (1-3)

        Returns:
            FileSlotInfo if available, None if slot doesn't exist
        """
        if not 1 <= slot <= 3:
            return None

        # This would need actual memory reading for full implementation
        # Returning placeholder for now
        return FileSlotInfo(
            slot_number=slot,
            status=FileSlotStatus.UNKNOWN,
        )

    def save_results(
        self,
        attempt: NavigationAttempt,
        path: Optional[Path] = None
    ) -> Path:
        """Save navigation attempt results to JSON.

        Args:
            attempt: NavigationAttempt to save
            path: Optional path for output file

        Returns:
            Path to saved file
        """
        if path is None:
            path = Path("file_select_result.json")

        with open(path, "w") as f:
            json.dump(attempt.to_dict(), f, indent=2)

        return path


# Factory functions for common operations
def create_file_select_sequence(slot: int = 1) -> "InputSequence":
    """Create an input sequence that navigates file select.

    Args:
        slot: Target slot number (1-3)

    Returns:
        InputSequence for file select navigation
    """
    from .input_recorder import InputSequence

    seq = InputSequence(
        name=f"file_select_slot_{slot}",
        description=f"Navigate to file slot {slot} and select",
        metadata={"goal": "A.2", "type": "navigation", "slot": slot}
    )

    # Start from file select screen (after title)
    frame = 0

    # Move to correct slot (from slot 1)
    for i in range(1, slot):
        seq.add_input(frame, ["DOWN"], hold=2)
        frame += 15

    # Wait a moment
    frame += 30

    # Press A to select
    seq.add_input(frame, ["A"], hold=2)
    frame += 30

    # Wait for load
    frame += 120

    return seq


def create_new_game_sequence(slot: int = 1) -> "InputSequence":
    """Create an input sequence that starts a new game.

    Args:
        slot: Target slot number (1-3)

    Returns:
        InputSequence for starting new game
    """
    from .input_recorder import InputSequence

    seq = InputSequence(
        name=f"new_game_slot_{slot}",
        description=f"Start new game in slot {slot}",
        metadata={"goal": "A.3", "type": "new_game", "slot": slot}
    )

    # Navigate to slot
    frame = 0
    for i in range(1, slot):
        seq.add_input(frame, ["DOWN"], hold=2)
        frame += 15

    # Press A to select empty slot
    frame += 30
    seq.add_input(frame, ["A"], hold=2)
    frame += 60

    # Name entry: just press START to accept default
    seq.add_input(frame, ["START"], hold=2)
    frame += 30

    # Wait for intro to start
    frame += 180

    return seq
