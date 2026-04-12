"""Input sequence recording and playback for Oracle of Secrets.

This module provides tools for recording, saving, and replaying
input sequences for automated gameplay testing.

Campaign Goals Supported:
- A.1: Boot to playable state
- A.2: Navigate overworld to specific locations
- D.4: Input sequence recorder and playback

Usage:
    from scripts.campaign.input_recorder import InputRecorder, InputSequence

    # Record inputs
    recorder = InputRecorder()
    recorder.start_recording()
    # ... play the game ...
    recorder.stop_recording()
    sequence = recorder.get_sequence()
    sequence.save("my_sequence.json")

    # Playback inputs
    sequence = InputSequence.load("my_sequence.json")
    player = InputPlayer(emulator)
    player.play(sequence)
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from enum import IntFlag, auto
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot


class Button(IntFlag):
    """SNES controller buttons as bitflags."""
    NONE = 0
    B = auto()
    Y = auto()
    SELECT = auto()
    START = auto()
    UP = auto()
    DOWN = auto()
    LEFT = auto()
    RIGHT = auto()
    A = auto()
    X = auto()
    L = auto()
    R = auto()

    @classmethod
    def from_string(cls, name: str) -> 'Button':
        """Convert button name to Button enum."""
        name = name.upper()
        try:
            return cls[name]
        except KeyError:
            return cls.NONE

    @classmethod
    def from_strings(cls, names: List[str]) -> 'Button':
        """Convert list of button names to combined Button flags."""
        result = cls.NONE
        for name in names:
            result |= cls.from_string(name)
        return result

    def to_strings(self) -> List[str]:
        """Convert Button flags to list of button names."""
        names = []
        for button in Button:
            if button != Button.NONE and self & button:
                names.append(button.name)
        return names


@dataclass
class InputFrame:
    """Single frame of input."""
    frame_number: int
    buttons: Button
    hold_frames: int = 1

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "frame": self.frame_number,
            "buttons": self.buttons.to_strings(),
            "hold": self.hold_frames
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InputFrame':
        """Create from dictionary."""
        return cls(
            frame_number=data["frame"],
            buttons=Button.from_strings(data["buttons"]),
            hold_frames=data.get("hold", 1)
        )


@dataclass
class InputSequence:
    """A sequence of input frames."""
    name: str
    description: str = ""
    frames: List[InputFrame] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def total_frames(self) -> int:
        """Total frames including holds."""
        if not self.frames:
            return 0
        last = self.frames[-1]
        return last.frame_number + last.hold_frames

    @property
    def duration_seconds(self) -> float:
        """Approximate duration at 60fps."""
        return self.total_frames / 60.0

    def add_input(
        self,
        frame: int,
        buttons: Button | List[str],
        hold: int = 1
    ) -> None:
        """Add input at specified frame."""
        if isinstance(buttons, list):
            buttons = Button.from_strings(buttons)
        self.frames.append(InputFrame(frame, buttons, hold))

    def add_wait(self, frames: int) -> int:
        """Add wait (no input) and return the frame number after wait.

        Returns the frame number where the next input should go.
        """
        if not self.frames:
            return frames
        return self.frames[-1].frame_number + self.frames[-1].hold_frames + frames

    def compress(self) -> 'InputSequence':
        """Compress sequence by merging consecutive identical inputs."""
        if not self.frames:
            return InputSequence(self.name, self.description, [], self.metadata.copy())

        compressed = []
        current = None

        for frame in sorted(self.frames, key=lambda f: f.frame_number):
            if current is None:
                current = InputFrame(
                    frame.frame_number,
                    frame.buttons,
                    frame.hold_frames
                )
            elif (frame.buttons == current.buttons and
                  frame.frame_number == current.frame_number + current.hold_frames):
                # Merge consecutive identical inputs
                current.hold_frames += frame.hold_frames
            else:
                compressed.append(current)
                current = InputFrame(
                    frame.frame_number,
                    frame.buttons,
                    frame.hold_frames
                )

        if current is not None:
            compressed.append(current)

        return InputSequence(
            self.name,
            self.description,
            compressed,
            self.metadata.copy()
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "name": self.name,
            "description": self.description,
            "frames": [f.to_dict() for f in self.frames],
            "metadata": self.metadata,
            "total_frames": self.total_frames,
            "duration_seconds": self.duration_seconds
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'InputSequence':
        """Create from dictionary."""
        return cls(
            name=data["name"],
            description=data.get("description", ""),
            frames=[InputFrame.from_dict(f) for f in data.get("frames", [])],
            metadata=data.get("metadata", {})
        )

    def save(self, path: str | Path) -> None:
        """Save sequence to JSON file."""
        path = Path(path)
        with open(path, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

    @classmethod
    def load(cls, path: str | Path) -> 'InputSequence':
        """Load sequence from JSON file."""
        path = Path(path)
        with open(path, 'r') as f:
            return cls.from_dict(json.load(f))


class InputRecorder:
    """Record input sequences during gameplay.

    Note: This records conceptual inputs. For actual recording from
    emulator, the emulator must support input logging.
    """

    def __init__(self, name: str = "recorded_sequence"):
        """Initialize recorder."""
        self._name = name
        self._recording = False
        self._start_time: Optional[float] = None
        self._frames: List[InputFrame] = []
        self._frame_counter = 0

    @property
    def is_recording(self) -> bool:
        """Check if currently recording."""
        return self._recording

    def start_recording(self) -> None:
        """Start recording inputs."""
        self._recording = True
        self._start_time = time.time()
        self._frames = []
        self._frame_counter = 0

    def stop_recording(self) -> None:
        """Stop recording inputs."""
        self._recording = False

    def record_input(self, buttons: Button | List[str], hold: int = 1) -> None:
        """Record an input at current frame.

        Args:
            buttons: Buttons pressed
            hold: Number of frames to hold
        """
        if not self._recording:
            return

        if isinstance(buttons, list):
            buttons = Button.from_strings(buttons)

        self._frames.append(InputFrame(
            self._frame_counter,
            buttons,
            hold
        ))
        self._frame_counter += hold

    def advance_frames(self, count: int = 1) -> None:
        """Advance frame counter without input."""
        if self._recording:
            self._frame_counter += count

    def get_sequence(self) -> InputSequence:
        """Get recorded sequence."""
        return InputSequence(
            name=self._name,
            description=f"Recorded at {time.strftime('%Y-%m-%d %H:%M:%S')}",
            frames=self._frames.copy(),
            metadata={
                "recorded_at": time.time(),
                "total_frames": self._frame_counter
            }
        )


class InputPlayer:
    """Play back input sequences on an emulator."""

    def __init__(self, emulator: EmulatorInterface):
        """Initialize player.

        Args:
            emulator: Emulator to send inputs to
        """
        self._emu = emulator
        self._current_frame = 0
        self._playing = False

    @property
    def is_playing(self) -> bool:
        """Check if currently playing."""
        return self._playing

    @property
    def current_frame(self) -> int:
        """Get current playback frame."""
        return self._current_frame

    def play(
        self,
        sequence: InputSequence,
        callback: Optional[callable] = None
    ) -> bool:
        """Play back a sequence.

        Args:
            sequence: Input sequence to play
            callback: Optional callback(frame, state) called each frame

        Returns:
            True if playback completed successfully
        """
        self._playing = True
        self._current_frame = 0

        # Sort frames by frame number
        sorted_frames = sorted(sequence.frames, key=lambda f: f.frame_number)
        frame_iter = iter(sorted_frames)
        current_input: Optional[InputFrame] = None
        try:
            current_input = next(frame_iter)
        except StopIteration:
            self._playing = False
            return True  # Empty sequence is "successful"

        try:
            while self._playing:
                # Check if we need to inject input at this frame
                if current_input and self._current_frame == current_input.frame_number:
                    # Inject input
                    buttons = current_input.buttons.to_strings()
                    if buttons:
                        success = self._emu.inject_input(
                            buttons,
                            frames=current_input.hold_frames,
                            release=True
                        )
                        if not success:
                            self._playing = False
                            return False

                    # Move to next input
                    try:
                        current_input = next(frame_iter)
                    except StopIteration:
                        current_input = None

                # Advance emulator by one frame
                if not self._emu.step_frame(1):
                    self._playing = False
                    return False

                self._current_frame += 1

                # Call callback if provided
                if callback:
                    state = self._emu.read_state()
                    callback(self._current_frame, state)

                # Check if sequence is complete
                if current_input is None:
                    # All inputs processed, but continue until total frames
                    if self._current_frame >= sequence.total_frames:
                        break

        finally:
            self._playing = False

        return True

    def stop(self) -> None:
        """Stop playback."""
        self._playing = False


# =============================================================================
# Pre-built Input Sequences
# =============================================================================

def create_boot_sequence() -> InputSequence:
    """Create a sequence that boots to playable state.

    This sequence:
    1. Waits for title screen
    2. Presses START to begin
    3. Selects file slot 1
    4. Waits for game to load

    Returns:
        InputSequence for booting to playable state
    """
    seq = InputSequence(
        name="boot_to_playable",
        description="Boot ROM to playable overworld state",
        metadata={"goal": "A.1", "type": "automation"}
    )

    # Wait for title screen animation (approx 3 seconds)
    frame = 180

    # Press START to begin
    seq.add_input(frame, ["START"], hold=2)
    frame += 30

    # Wait for file select screen
    frame += 60

    # Select file 1 (press A)
    seq.add_input(frame, ["A"], hold=2)
    frame += 30

    # Wait for game to load
    frame += 120

    return seq


def create_walk_sequence(
    direction: str,
    tiles: int,
    hold_run: bool = False
) -> InputSequence:
    """Create a sequence that walks in a direction.

    Args:
        direction: UP, DOWN, LEFT, or RIGHT
        tiles: Number of tiles to walk (approx 16 pixels each)
        hold_run: Whether to hold Y for running

    Returns:
        InputSequence for walking
    """
    direction = direction.upper()
    if direction not in ("UP", "DOWN", "LEFT", "RIGHT"):
        raise ValueError(f"Invalid direction: {direction}")

    # Approximately 10 frames per tile at walking speed
    frames_per_tile = 10 if not hold_run else 6
    total_hold = tiles * frames_per_tile

    seq = InputSequence(
        name=f"walk_{direction.lower()}_{tiles}",
        description=f"Walk {direction} for {tiles} tiles",
        metadata={"direction": direction, "tiles": tiles, "running": hold_run}
    )

    buttons = [direction]
    if hold_run:
        buttons.append("Y")

    seq.add_input(0, buttons, hold=total_hold)

    return seq


def create_menu_open_sequence() -> InputSequence:
    """Create sequence to open the menu."""
    seq = InputSequence(
        name="open_menu",
        description="Open the game menu with START",
        metadata={"type": "menu"}
    )
    seq.add_input(0, ["START"], hold=2)
    return seq


def create_attack_sequence() -> InputSequence:
    """Create sequence for a basic attack."""
    seq = InputSequence(
        name="basic_attack",
        description="Perform a basic sword attack",
        metadata={"type": "combat"}
    )
    seq.add_input(0, ["B"], hold=2)
    return seq
