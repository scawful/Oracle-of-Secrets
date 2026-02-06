"""Tests for input sequence serialization and recording.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.4: Input sequence recording validation

These tests verify input sequence save/load, compression,
and recorder functionality work correctly.
"""

import pytest
import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.input_recorder import (
    Button, InputFrame, InputSequence, InputRecorder, InputPlayer,
    create_walk_sequence, create_boot_sequence, create_attack_sequence,
    create_menu_open_sequence
)


class TestButtonCombinations:
    """Test Button flag combinations."""

    def test_single_button(self):
        """Test single button flag."""
        assert Button.A.value != 0
        assert Button.B.value != 0

    def test_button_combination(self):
        """Test combining buttons."""
        combo = Button.A | Button.B
        assert combo & Button.A
        assert combo & Button.B
        assert not (combo & Button.X)

    def test_all_buttons_combined(self):
        """Test all buttons can be combined."""
        all_buttons = (Button.A | Button.B | Button.X | Button.Y |
                       Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT |
                       Button.START | Button.SELECT | Button.L | Button.R)
        assert all_buttons != Button.NONE

    def test_from_string_case_insensitive(self):
        """Test from_string is case insensitive."""
        assert Button.from_string("a") == Button.A
        assert Button.from_string("A") == Button.A
        assert Button.from_string("up") == Button.UP
        assert Button.from_string("UP") == Button.UP

    def test_from_strings_multiple(self):
        """Test from_strings with multiple buttons."""
        buttons = Button.from_strings(["A", "B", "UP"])
        assert buttons & Button.A
        assert buttons & Button.B
        assert buttons & Button.UP
        assert not (buttons & Button.DOWN)

    def test_to_strings_round_trip(self):
        """Test to_strings then from_strings round trip."""
        original = Button.A | Button.B | Button.UP
        names = original.to_strings()
        reconstructed = Button.from_strings(names)
        assert reconstructed == original

    def test_none_button_value(self):
        """Test NONE button has value 0."""
        assert Button.NONE.value == 0

    def test_invalid_button_returns_none(self):
        """Test invalid button string returns NONE."""
        assert Button.from_string("INVALID") == Button.NONE


class TestInputFrameSerialization:
    """Test InputFrame serialization."""

    def test_to_dict_basic(self):
        """Test basic frame to_dict."""
        frame = InputFrame(frame_number=10, buttons=Button.A, hold_frames=5)
        d = frame.to_dict()

        assert d["frame"] == 10
        assert "A" in d["buttons"]
        assert d["hold"] == 5

    def test_to_dict_multiple_buttons(self):
        """Test multiple buttons in to_dict."""
        frame = InputFrame(
            frame_number=0,
            buttons=Button.A | Button.B | Button.UP,
            hold_frames=1
        )
        d = frame.to_dict()

        assert "A" in d["buttons"]
        assert "B" in d["buttons"]
        assert "UP" in d["buttons"]

    def test_from_dict_basic(self):
        """Test basic from_dict."""
        d = {"frame": 20, "buttons": ["A"], "hold": 10}
        frame = InputFrame.from_dict(d)

        assert frame.frame_number == 20
        assert frame.buttons == Button.A
        assert frame.hold_frames == 10

    def test_from_dict_default_hold(self):
        """Test from_dict with missing hold defaults to 1."""
        d = {"frame": 0, "buttons": ["B"]}
        frame = InputFrame.from_dict(d)

        assert frame.hold_frames == 1

    def test_round_trip(self):
        """Test to_dict then from_dict round trip."""
        original = InputFrame(
            frame_number=50,
            buttons=Button.START | Button.SELECT,
            hold_frames=30
        )
        reconstructed = InputFrame.from_dict(original.to_dict())

        assert reconstructed.frame_number == original.frame_number
        assert reconstructed.buttons == original.buttons
        assert reconstructed.hold_frames == original.hold_frames


class TestInputSequenceSerialization:
    """Test InputSequence serialization."""

    def test_to_dict_empty_sequence(self):
        """Test to_dict with empty sequence."""
        seq = InputSequence(name="empty", description="Empty sequence")
        d = seq.to_dict()

        assert d["name"] == "empty"
        assert d["description"] == "Empty sequence"
        assert d["frames"] == []
        assert d["total_frames"] == 0
        assert d["duration_seconds"] == 0.0

    def test_to_dict_with_frames(self):
        """Test to_dict with frames."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=10)
        seq.add_input(10, Button.B, hold=20)
        d = seq.to_dict()

        assert len(d["frames"]) == 2
        assert d["total_frames"] == 30

    def test_from_dict_basic(self):
        """Test from_dict creates valid sequence."""
        d = {
            "name": "loaded",
            "description": "Loaded sequence",
            "frames": [
                {"frame": 0, "buttons": ["A"], "hold": 5}
            ],
            "metadata": {"key": "value"}
        }
        seq = InputSequence.from_dict(d)

        assert seq.name == "loaded"
        assert seq.description == "Loaded sequence"
        assert len(seq.frames) == 1
        assert seq.metadata["key"] == "value"

    def test_from_dict_missing_optional_fields(self):
        """Test from_dict handles missing optional fields."""
        d = {"name": "minimal"}
        seq = InputSequence.from_dict(d)

        assert seq.name == "minimal"
        assert seq.description == ""
        assert seq.frames == []
        assert seq.metadata == {}

    def test_round_trip(self):
        """Test to_dict then from_dict round trip."""
        original = InputSequence(
            name="roundtrip",
            description="Test round trip",
            metadata={"version": 1}
        )
        original.add_input(0, Button.UP, hold=60)
        original.add_input(60, Button.DOWN, hold=60)

        reconstructed = InputSequence.from_dict(original.to_dict())

        assert reconstructed.name == original.name
        assert reconstructed.description == original.description
        assert len(reconstructed.frames) == len(original.frames)


class TestInputSequenceFileIO:
    """Test InputSequence file save/load."""

    def test_save_creates_file(self):
        """Test save creates JSON file."""
        seq = InputSequence(name="file_test")
        seq.add_input(0, Button.A, hold=1)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            assert path.exists()

            with open(path) as f:
                data = json.load(f)
            assert data["name"] == "file_test"
        finally:
            path.unlink()

    def test_load_from_file(self):
        """Test load reads JSON file."""
        data = {
            "name": "loaded_from_file",
            "description": "Test",
            "frames": [{"frame": 0, "buttons": ["B"], "hold": 2}]
        }

        with tempfile.NamedTemporaryFile(
            suffix=".json", mode='w', delete=False
        ) as f:
            json.dump(data, f)
            path = Path(f.name)

        try:
            seq = InputSequence.load(path)
            assert seq.name == "loaded_from_file"
            assert len(seq.frames) == 1
        finally:
            path.unlink()

    def test_save_load_round_trip(self):
        """Test save then load round trip."""
        original = InputSequence(
            name="save_load_test",
            description="Testing save/load",
            metadata={"test": True}
        )
        original.add_input(0, Button.START, hold=5)
        original.add_input(60, Button.A, hold=10)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            original.save(path)
            loaded = InputSequence.load(path)

            assert loaded.name == original.name
            assert loaded.description == original.description
            assert len(loaded.frames) == len(original.frames)
            assert loaded.metadata["test"] == True
        finally:
            path.unlink()


class TestInputSequenceCompression:
    """Test InputSequence compression."""

    def test_compress_empty_sequence(self):
        """Test compressing empty sequence."""
        seq = InputSequence(name="empty")
        compressed = seq.compress()

        assert compressed.name == "empty"
        assert len(compressed.frames) == 0

    def test_compress_single_frame(self):
        """Test compressing single frame sequence."""
        seq = InputSequence(name="single")
        seq.add_input(0, Button.A, hold=10)
        compressed = seq.compress()

        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 10

    def test_compress_consecutive_same_buttons(self):
        """Test consecutive identical inputs are merged."""
        seq = InputSequence(name="consecutive")
        # Add consecutive frames with same button
        seq.frames.append(InputFrame(0, Button.A, 1))
        seq.frames.append(InputFrame(1, Button.A, 1))
        seq.frames.append(InputFrame(2, Button.A, 1))

        compressed = seq.compress()

        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 3

    def test_compress_preserves_different_buttons(self):
        """Test different buttons are not merged."""
        seq = InputSequence(name="different")
        seq.add_input(0, Button.A, hold=1)
        seq.add_input(1, Button.B, hold=1)
        seq.add_input(2, Button.A, hold=1)

        compressed = seq.compress()

        assert len(compressed.frames) == 3

    def test_compress_preserves_metadata(self):
        """Test compress preserves metadata."""
        seq = InputSequence(
            name="meta",
            description="With metadata",
            metadata={"key": "value"}
        )
        seq.add_input(0, Button.UP, hold=5)
        compressed = seq.compress()

        assert compressed.metadata["key"] == "value"
        assert compressed.description == "With metadata"


class TestInputSequenceCalculations:
    """Test InputSequence duration calculations."""

    def test_total_frames_empty(self):
        """Test total frames for empty sequence."""
        seq = InputSequence(name="empty")
        assert seq.total_frames == 0

    def test_total_frames_single(self):
        """Test total frames for single input."""
        seq = InputSequence(name="single")
        seq.add_input(0, Button.A, hold=60)
        assert seq.total_frames == 60

    def test_total_frames_multiple(self):
        """Test total frames calculation."""
        seq = InputSequence(name="multi")
        seq.add_input(0, Button.A, hold=10)
        seq.add_input(100, Button.B, hold=50)  # Starts at 100, holds 50
        assert seq.total_frames == 150  # 100 + 50

    def test_duration_seconds(self):
        """Test duration in seconds at 60fps."""
        seq = InputSequence(name="duration")
        seq.add_input(0, Button.A, hold=60)  # 1 second
        assert seq.duration_seconds == 1.0

    def test_duration_seconds_fractional(self):
        """Test fractional duration."""
        seq = InputSequence(name="frac")
        seq.add_input(0, Button.A, hold=30)  # 0.5 seconds
        assert seq.duration_seconds == 0.5


class TestInputRecorderBasic:
    """Test InputRecorder basic functionality."""

    def test_recorder_creation(self):
        """Test creating recorder."""
        recorder = InputRecorder()
        assert recorder is not None
        assert not recorder.is_recording

    def test_recorder_with_name(self):
        """Test creating recorder with name."""
        recorder = InputRecorder(name="my_sequence")
        seq = recorder.get_sequence()
        assert seq.name == "my_sequence"

    def test_start_recording(self):
        """Test starting recording."""
        recorder = InputRecorder()
        recorder.start_recording()
        assert recorder.is_recording

    def test_stop_recording(self):
        """Test stopping recording."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.stop_recording()
        assert not recorder.is_recording

    def test_record_input_while_recording(self):
        """Test recording input while active."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, hold=5)
        seq = recorder.get_sequence()

        assert len(seq.frames) == 1
        assert seq.frames[0].buttons == Button.A

    def test_record_input_while_not_recording(self):
        """Test recording input while not active does nothing."""
        recorder = InputRecorder()
        recorder.record_input(Button.A, hold=5)
        seq = recorder.get_sequence()

        assert len(seq.frames) == 0

    def test_record_string_buttons(self):
        """Test recording with string button names."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(["A", "B"], hold=3)
        seq = recorder.get_sequence()

        assert seq.frames[0].buttons == (Button.A | Button.B)


class TestInputRecorderFrameCounter:
    """Test InputRecorder frame counting."""

    def test_advance_frames(self):
        """Test advancing frame counter."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.advance_frames(30)
        recorder.record_input(Button.A, hold=1)
        seq = recorder.get_sequence()

        assert seq.frames[0].frame_number == 30

    def test_record_advances_counter(self):
        """Test recording advances counter by hold amount."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, hold=10)
        recorder.record_input(Button.B, hold=20)
        seq = recorder.get_sequence()

        assert seq.frames[0].frame_number == 0
        assert seq.frames[1].frame_number == 10

    def test_advance_frames_not_recording(self):
        """Test advance_frames while not recording."""
        recorder = InputRecorder()
        recorder.advance_frames(100)  # Should do nothing
        recorder.start_recording()
        recorder.record_input(Button.A, hold=1)
        seq = recorder.get_sequence()

        assert seq.frames[0].frame_number == 0


class TestInputRecorderMetadata:
    """Test InputRecorder metadata."""

    def test_sequence_has_recorded_at(self):
        """Test recorded sequence has timestamp metadata."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, hold=1)
        seq = recorder.get_sequence()

        assert "recorded_at" in seq.metadata

    def test_sequence_has_total_frames(self):
        """Test recorded sequence has total frames metadata."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, hold=30)
        seq = recorder.get_sequence()

        assert "total_frames" in seq.metadata
        assert seq.metadata["total_frames"] == 30

    def test_sequence_has_description(self):
        """Test recorded sequence has description."""
        recorder = InputRecorder()
        recorder.start_recording()
        seq = recorder.get_sequence()

        assert seq.description != ""
        assert "Recorded" in seq.description


class TestPrebuiltSequences:
    """Test pre-built sequence factory functions."""

    def test_walk_sequence_up(self):
        """Test walk UP sequence."""
        seq = create_walk_sequence("UP", tiles=1)
        assert seq is not None
        assert len(seq.frames) > 0
        # Should have UP button
        assert any(f.buttons & Button.UP for f in seq.frames)

    def test_walk_sequence_down(self):
        """Test walk DOWN sequence."""
        seq = create_walk_sequence("DOWN", tiles=1)
        assert any(f.buttons & Button.DOWN for f in seq.frames)

    def test_walk_sequence_left(self):
        """Test walk LEFT sequence."""
        seq = create_walk_sequence("LEFT", tiles=1)
        assert any(f.buttons & Button.LEFT for f in seq.frames)

    def test_walk_sequence_right(self):
        """Test walk RIGHT sequence."""
        seq = create_walk_sequence("RIGHT", tiles=1)
        assert any(f.buttons & Button.RIGHT for f in seq.frames)

    def test_walk_sequence_multiple_tiles(self):
        """Test walking multiple tiles."""
        seq1 = create_walk_sequence("UP", tiles=1)
        seq2 = create_walk_sequence("UP", tiles=3)
        # More tiles should take more frames
        assert seq2.total_frames >= seq1.total_frames

    def test_boot_sequence_exists(self):
        """Test boot sequence can be created."""
        seq = create_boot_sequence()
        assert seq is not None
        assert seq.total_frames > 0

    def test_boot_sequence_has_start_button(self):
        """Test boot sequence includes START."""
        seq = create_boot_sequence()
        assert any(f.buttons & Button.START for f in seq.frames)

    def test_attack_sequence_exists(self):
        """Test attack sequence can be created."""
        seq = create_attack_sequence()
        assert seq is not None

    def test_menu_open_sequence_exists(self):
        """Test menu open sequence can be created."""
        seq = create_menu_open_sequence()
        assert seq is not None
        # Menu opens with START
        assert any(f.buttons & Button.START for f in seq.frames)


class TestInputPlayerBasic:
    """Test InputPlayer basic functionality."""

    def test_player_creation(self):
        """Test creating player."""
        mock_emu = Mock()
        player = InputPlayer(mock_emu)
        assert player is not None

    def test_player_initial_state(self):
        """Test player initial state."""
        mock_emu = Mock()
        player = InputPlayer(mock_emu)
        assert not player.is_playing
        assert player.current_frame == 0

    def test_play_empty_sequence(self):
        """Test playing empty sequence."""
        mock_emu = Mock()
        mock_emu.inject_input.return_value = True
        mock_emu.step_frame.return_value = True

        player = InputPlayer(mock_emu)
        seq = InputSequence(name="empty")

        result = player.play(seq)
        assert result is True


class TestInputSequenceAddWait:
    """Test InputSequence add_wait method."""

    def test_add_wait_empty_sequence(self):
        """Test add_wait on empty sequence."""
        seq = InputSequence(name="test")
        next_frame = seq.add_wait(30)
        assert next_frame == 30

    def test_add_wait_after_input(self):
        """Test add_wait after input."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=10)
        next_frame = seq.add_wait(20)
        assert next_frame == 30  # 10 (hold) + 20 (wait)

    def test_add_wait_sequence(self):
        """Test sequential waits."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=10)
        frame1 = seq.add_wait(5)
        seq.add_input(frame1, Button.B, hold=10)
        frame2 = seq.add_wait(5)

        assert frame1 == 15
        assert frame2 == 30


class TestInputSequenceAddInput:
    """Test InputSequence add_input method."""

    def test_add_input_button_enum(self):
        """Test add_input with Button enum."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=5)

        assert len(seq.frames) == 1
        assert seq.frames[0].buttons == Button.A

    def test_add_input_string_list(self):
        """Test add_input with string list."""
        seq = InputSequence(name="test")
        seq.add_input(0, ["A", "B"], hold=5)

        assert seq.frames[0].buttons == (Button.A | Button.B)

    def test_add_input_default_hold(self):
        """Test add_input default hold is 1."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A)

        assert seq.frames[0].hold_frames == 1

    def test_add_multiple_inputs(self):
        """Test adding multiple inputs."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=5)
        seq.add_input(10, Button.B, hold=5)
        seq.add_input(20, Button.Y, hold=5)

        assert len(seq.frames) == 3
