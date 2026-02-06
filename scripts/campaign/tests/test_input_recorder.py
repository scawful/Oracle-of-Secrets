"""Tests for input_recorder module.

Campaign Goals Supported:
- D.4: Input sequence recorder and playback
"""

import json
import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.input_recorder import (
    Button,
    InputFrame,
    InputSequence,
    InputRecorder,
    InputPlayer,
    create_boot_sequence,
    create_walk_sequence,
    create_menu_open_sequence,
    create_attack_sequence,
)


class TestButton:
    """Tests for Button enum and utilities."""

    def test_button_values(self):
        """Test button enum values are distinct."""
        assert Button.A != Button.B
        assert Button.UP != Button.DOWN
        assert Button.NONE == 0

    def test_from_string_valid(self):
        """Test converting string to button."""
        assert Button.from_string("A") == Button.A
        assert Button.from_string("start") == Button.START
        assert Button.from_string("UP") == Button.UP

    def test_from_string_invalid(self):
        """Test invalid string returns NONE."""
        assert Button.from_string("invalid") == Button.NONE
        assert Button.from_string("") == Button.NONE

    def test_from_strings(self):
        """Test converting multiple strings to combined flags."""
        combo = Button.from_strings(["A", "B"])
        assert combo & Button.A
        assert combo & Button.B
        assert not combo & Button.Y

    def test_to_strings(self):
        """Test converting button flags to string list."""
        combo = Button.A | Button.B | Button.UP
        strings = combo.to_strings()
        assert "A" in strings
        assert "B" in strings
        assert "UP" in strings
        assert "DOWN" not in strings

    def test_button_combinations(self):
        """Test combining buttons with OR."""
        dash = Button.Y | Button.RIGHT
        assert dash & Button.Y
        assert dash & Button.RIGHT
        assert not dash & Button.LEFT


class TestInputFrame:
    """Tests for InputFrame dataclass."""

    def test_basic_frame(self):
        """Test creating basic input frame."""
        frame = InputFrame(100, Button.A, 5)
        assert frame.frame_number == 100
        assert frame.buttons == Button.A
        assert frame.hold_frames == 5

    def test_to_dict(self):
        """Test serialization to dict."""
        frame = InputFrame(50, Button.A | Button.B, 3)
        data = frame.to_dict()
        assert data["frame"] == 50
        assert "A" in data["buttons"]
        assert "B" in data["buttons"]
        assert data["hold"] == 3

    def test_from_dict(self):
        """Test deserialization from dict."""
        data = {"frame": 100, "buttons": ["UP", "A"], "hold": 10}
        frame = InputFrame.from_dict(data)
        assert frame.frame_number == 100
        assert frame.buttons & Button.UP
        assert frame.buttons & Button.A
        assert frame.hold_frames == 10

    def test_roundtrip(self):
        """Test serialization roundtrip."""
        original = InputFrame(75, Button.START | Button.SELECT, 2)
        data = original.to_dict()
        restored = InputFrame.from_dict(data)
        assert restored.frame_number == original.frame_number
        assert restored.buttons == original.buttons
        assert restored.hold_frames == original.hold_frames


class TestInputSequence:
    """Tests for InputSequence class."""

    def test_empty_sequence(self):
        """Test empty sequence properties."""
        seq = InputSequence("empty")
        assert seq.total_frames == 0
        assert seq.duration_seconds == 0.0
        assert len(seq.frames) == 0

    def test_add_input(self):
        """Test adding inputs to sequence."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 5)
        seq.add_input(10, ["B", "Y"], 3)

        assert len(seq.frames) == 2
        assert seq.frames[0].buttons == Button.A
        assert seq.frames[1].buttons & Button.B
        assert seq.frames[1].buttons & Button.Y

    def test_total_frames(self):
        """Test total frame calculation."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 10)
        seq.add_input(20, Button.B, 5)

        # Last frame is 20, hold is 5, so total is 25
        assert seq.total_frames == 25

    def test_duration_seconds(self):
        """Test duration calculation."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 60)  # 60 frames = 1 second at 60fps

        assert abs(seq.duration_seconds - 1.0) < 0.01

    def test_add_wait(self):
        """Test add_wait returns correct frame."""
        seq = InputSequence("test")

        # Initial wait
        frame = seq.add_wait(30)
        assert frame == 30

        # Add input and wait more
        seq.add_input(frame, Button.A, 10)
        frame = seq.add_wait(20)
        assert frame == 60  # 30 + 10 + 20

    def test_compress(self):
        """Test compressing consecutive identical inputs."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 1)
        seq.add_input(1, Button.A, 1)
        seq.add_input(2, Button.A, 1)
        seq.add_input(10, Button.B, 2)

        compressed = seq.compress()
        assert len(compressed.frames) == 2
        assert compressed.frames[0].hold_frames == 3  # Merged A presses
        assert compressed.frames[1].buttons == Button.B

    def test_to_dict(self):
        """Test sequence serialization."""
        seq = InputSequence("test", "A test sequence")
        seq.add_input(0, Button.A, 5)
        seq.metadata["author"] = "campaign"

        data = seq.to_dict()
        assert data["name"] == "test"
        assert data["description"] == "A test sequence"
        assert len(data["frames"]) == 1
        assert data["metadata"]["author"] == "campaign"

    def test_from_dict(self):
        """Test sequence deserialization."""
        data = {
            "name": "loaded",
            "description": "From dict",
            "frames": [
                {"frame": 0, "buttons": ["A"], "hold": 5},
                {"frame": 10, "buttons": ["B"], "hold": 3}
            ],
            "metadata": {"version": 1}
        }
        seq = InputSequence.from_dict(data)

        assert seq.name == "loaded"
        assert len(seq.frames) == 2
        assert seq.metadata["version"] == 1

    def test_save_and_load(self):
        """Test saving and loading from file."""
        seq = InputSequence("saveable", "Test save/load")
        seq.add_input(0, Button.A | Button.B, 10)
        seq.add_input(20, Button.UP, 30)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            loaded = InputSequence.load(path)

            assert loaded.name == seq.name
            assert loaded.description == seq.description
            assert len(loaded.frames) == len(seq.frames)
            assert loaded.frames[0].buttons == seq.frames[0].buttons
        finally:
            path.unlink()


class TestInputRecorder:
    """Tests for InputRecorder class."""

    def test_initial_state(self):
        """Test recorder starts not recording."""
        recorder = InputRecorder()
        assert not recorder.is_recording

    def test_start_stop_recording(self):
        """Test starting and stopping recording."""
        recorder = InputRecorder()

        recorder.start_recording()
        assert recorder.is_recording

        recorder.stop_recording()
        assert not recorder.is_recording

    def test_record_input(self):
        """Test recording inputs."""
        recorder = InputRecorder("test")
        recorder.start_recording()

        recorder.record_input(Button.A, 5)
        recorder.record_input(["B", "Y"], 3)

        seq = recorder.get_sequence()
        assert len(seq.frames) == 2
        assert seq.frames[0].frame_number == 0
        assert seq.frames[1].frame_number == 5  # After first input

    def test_record_when_not_recording(self):
        """Test that inputs are ignored when not recording."""
        recorder = InputRecorder()
        recorder.record_input(Button.A, 5)  # Should be ignored

        seq = recorder.get_sequence()
        assert len(seq.frames) == 0

    def test_advance_frames(self):
        """Test advancing frame counter."""
        recorder = InputRecorder()
        recorder.start_recording()

        recorder.advance_frames(30)  # Wait 30 frames
        recorder.record_input(Button.A, 5)

        seq = recorder.get_sequence()
        assert seq.frames[0].frame_number == 30


class TestInputPlayer:
    """Tests for InputPlayer class."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.inject_input.return_value = True
        emu.step_frame.return_value = True
        emu.read_state.return_value = Mock(mode=0x09, link_x=100, link_y=100)
        return emu

    def test_initial_state(self, mock_emulator):
        """Test player starts not playing."""
        player = InputPlayer(mock_emulator)
        assert not player.is_playing
        assert player.current_frame == 0

    def test_play_empty_sequence(self, mock_emulator):
        """Test playing empty sequence succeeds."""
        player = InputPlayer(mock_emulator)
        seq = InputSequence("empty")

        result = player.play(seq)
        assert result is True
        assert not player.is_playing

    def test_play_simple_sequence(self, mock_emulator):
        """Test playing simple sequence."""
        player = InputPlayer(mock_emulator)
        seq = InputSequence("simple")
        seq.add_input(0, Button.A, 2)
        seq.add_input(5, Button.B, 1)

        result = player.play(seq)

        assert result is True
        mock_emulator.inject_input.assert_called()
        mock_emulator.step_frame.assert_called()

    def test_play_with_callback(self, mock_emulator):
        """Test playing with frame callback."""
        player = InputPlayer(mock_emulator)
        seq = InputSequence("callback_test")
        seq.add_input(0, Button.A, 2)

        frames_seen = []
        def callback(frame, state):
            frames_seen.append(frame)

        result = player.play(seq, callback=callback)

        assert result is True
        assert len(frames_seen) > 0

    def test_stop_playback(self, mock_emulator):
        """Test stopping playback."""
        player = InputPlayer(mock_emulator)
        seq = InputSequence("long")
        seq.add_input(0, Button.A, 1000)  # Long sequence

        # Can't easily test async stop, but verify method exists
        player.stop()
        assert not player.is_playing


class TestPrebuiltSequences:
    """Tests for pre-built input sequences."""

    def test_boot_sequence(self):
        """Test boot sequence is valid."""
        seq = create_boot_sequence()

        assert seq.name == "boot_to_playable"
        assert len(seq.frames) > 0
        assert seq.total_frames > 0
        assert seq.metadata.get("goal") == "A.1"

    def test_walk_sequence_up(self):
        """Test walk up sequence."""
        seq = create_walk_sequence("UP", 5)

        assert "walk_up" in seq.name
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons & Button.UP

    def test_walk_sequence_running(self):
        """Test walk sequence with running."""
        seq = create_walk_sequence("RIGHT", 3, hold_run=True)

        assert seq.frames[0].buttons & Button.RIGHT
        assert seq.frames[0].buttons & Button.Y
        assert seq.metadata["running"] is True

    def test_walk_sequence_invalid_direction(self):
        """Test walk sequence rejects invalid direction."""
        with pytest.raises(ValueError):
            create_walk_sequence("DIAGONAL", 5)

    def test_menu_sequence(self):
        """Test menu open sequence."""
        seq = create_menu_open_sequence()

        assert seq.frames[0].buttons & Button.START

    def test_attack_sequence(self):
        """Test attack sequence."""
        seq = create_attack_sequence()

        assert seq.frames[0].buttons & Button.B
        assert seq.metadata["type"] == "combat"
