"""Iteration 52 - Input Playback and Recording Tests.

Tests for Button enum, InputFrame, InputSequence, InputRecorder, InputPlayer,
and pre-built sequence factories.

Focus: Button flag operations, frame serialization, sequence compression,
recording lifecycle, playback mechanics, pre-built sequences.
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import MagicMock, patch

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


# =============================================================================
# Button Flag Tests
# =============================================================================

class TestButtonFlags:
    """Tests for Button IntFlag enum."""

    def test_button_none_is_zero(self):
        """NONE is 0."""
        assert Button.NONE == 0

    def test_button_values_are_powers_of_two(self):
        """Non-NONE buttons are powers of 2."""
        for button in Button:
            if button != Button.NONE:
                # Should be a power of 2
                assert (button.value & (button.value - 1)) == 0

    def test_button_combination_bitwise_or(self):
        """Buttons can be combined with OR."""
        combo = Button.A | Button.B
        assert combo & Button.A
        assert combo & Button.B
        assert not (combo & Button.X)

    def test_button_from_string_valid(self):
        """from_string converts valid names."""
        assert Button.from_string("A") == Button.A
        assert Button.from_string("START") == Button.START
        assert Button.from_string("UP") == Button.UP

    def test_button_from_string_lowercase(self):
        """from_string handles lowercase."""
        assert Button.from_string("a") == Button.A
        assert Button.from_string("start") == Button.START

    def test_button_from_string_invalid(self):
        """from_string returns NONE for invalid names."""
        assert Button.from_string("INVALID") == Button.NONE
        assert Button.from_string("") == Button.NONE

    def test_button_from_strings_multiple(self):
        """from_strings combines multiple buttons."""
        combo = Button.from_strings(["A", "B", "START"])
        assert combo & Button.A
        assert combo & Button.B
        assert combo & Button.START
        assert not (combo & Button.X)

    def test_button_from_strings_empty(self):
        """from_strings with empty list returns NONE."""
        assert Button.from_strings([]) == Button.NONE

    def test_button_to_strings(self):
        """to_strings converts buttons to names."""
        combo = Button.A | Button.B
        names = combo.to_strings()
        assert "A" in names
        assert "B" in names
        assert len(names) == 2

    def test_button_to_strings_none(self):
        """to_strings for NONE returns empty list."""
        names = Button.NONE.to_strings()
        assert names == []

    def test_button_to_strings_single(self):
        """to_strings for single button."""
        names = Button.START.to_strings()
        assert names == ["START"]

    def test_button_round_trip(self):
        """from_strings and to_strings round-trip."""
        original = ["A", "B", "UP"]
        combo = Button.from_strings(original)
        result = combo.to_strings()
        assert set(result) == set(original)


# =============================================================================
# InputFrame Tests
# =============================================================================

class TestInputFrame:
    """Tests for InputFrame dataclass."""

    def test_frame_creation(self):
        """Create input frame."""
        frame = InputFrame(frame_number=10, buttons=Button.A)
        assert frame.frame_number == 10
        assert frame.buttons == Button.A
        assert frame.hold_frames == 1  # default

    def test_frame_with_hold(self):
        """Create frame with hold."""
        frame = InputFrame(frame_number=0, buttons=Button.B, hold_frames=5)
        assert frame.hold_frames == 5

    def test_frame_to_dict(self):
        """Frame serializes to dict."""
        frame = InputFrame(frame_number=100, buttons=Button.A | Button.B, hold_frames=3)
        d = frame.to_dict()

        assert d["frame"] == 100
        assert "A" in d["buttons"]
        assert "B" in d["buttons"]
        assert d["hold"] == 3

    def test_frame_from_dict(self):
        """Frame deserializes from dict."""
        d = {"frame": 50, "buttons": ["START", "A"], "hold": 10}
        frame = InputFrame.from_dict(d)

        assert frame.frame_number == 50
        assert frame.buttons & Button.START
        assert frame.buttons & Button.A
        assert frame.hold_frames == 10

    def test_frame_from_dict_default_hold(self):
        """Frame from dict defaults hold to 1."""
        d = {"frame": 0, "buttons": ["UP"]}
        frame = InputFrame.from_dict(d)

        assert frame.hold_frames == 1

    def test_frame_round_trip(self):
        """Frame to_dict/from_dict round-trip."""
        original = InputFrame(frame_number=25, buttons=Button.L | Button.R, hold_frames=7)
        d = original.to_dict()
        restored = InputFrame.from_dict(d)

        assert restored.frame_number == original.frame_number
        assert restored.buttons == original.buttons
        assert restored.hold_frames == original.hold_frames


# =============================================================================
# InputSequence Tests
# =============================================================================

class TestInputSequence:
    """Tests for InputSequence dataclass."""

    def test_sequence_creation(self):
        """Create empty sequence."""
        seq = InputSequence(name="test")
        assert seq.name == "test"
        assert seq.description == ""
        assert seq.frames == []
        assert seq.metadata == {}

    def test_sequence_with_description(self):
        """Sequence with description."""
        seq = InputSequence(name="test", description="Test sequence")
        assert seq.description == "Test sequence"

    def test_sequence_total_frames_empty(self):
        """Empty sequence has 0 total frames."""
        seq = InputSequence(name="empty")
        assert seq.total_frames == 0

    def test_sequence_total_frames_with_frames(self):
        """Total frames includes hold."""
        seq = InputSequence(name="test")
        seq.frames.append(InputFrame(0, Button.A, hold_frames=10))
        seq.frames.append(InputFrame(10, Button.B, hold_frames=5))

        # Last frame at 10, hold 5 = 15 total
        assert seq.total_frames == 15

    def test_sequence_duration_seconds(self):
        """Duration in seconds at 60fps."""
        seq = InputSequence(name="test")
        seq.frames.append(InputFrame(0, Button.A, hold_frames=60))

        # 60 frames at 60fps = 1 second
        assert seq.duration_seconds == 1.0

    def test_sequence_add_input_buttons(self):
        """add_input with Button enum."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.START, hold=5)

        assert len(seq.frames) == 1
        assert seq.frames[0].buttons == Button.START
        assert seq.frames[0].hold_frames == 5

    def test_sequence_add_input_strings(self):
        """add_input with string list."""
        seq = InputSequence(name="test")
        seq.add_input(0, ["A", "B"], hold=3)

        assert len(seq.frames) == 1
        assert seq.frames[0].buttons & Button.A
        assert seq.frames[0].buttons & Button.B

    def test_sequence_add_wait_empty(self):
        """add_wait on empty sequence."""
        seq = InputSequence(name="test")
        next_frame = seq.add_wait(10)
        assert next_frame == 10

    def test_sequence_add_wait_with_frames(self):
        """add_wait after existing frames."""
        seq = InputSequence(name="test")
        seq.add_input(0, Button.A, hold=5)
        next_frame = seq.add_wait(10)

        # Frame 0 + hold 5 + wait 10 = 15
        assert next_frame == 15

    def test_sequence_compress_empty(self):
        """Compress empty sequence."""
        seq = InputSequence(name="test")
        compressed = seq.compress()
        assert len(compressed.frames) == 0

    def test_sequence_compress_merges_consecutive(self):
        """Compress merges consecutive identical inputs."""
        seq = InputSequence(name="test")
        seq.frames = [
            InputFrame(0, Button.A, hold_frames=5),
            InputFrame(5, Button.A, hold_frames=5),  # Consecutive, same button
        ]
        compressed = seq.compress()

        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 10

    def test_sequence_compress_keeps_different(self):
        """Compress keeps different button presses."""
        seq = InputSequence(name="test")
        seq.frames = [
            InputFrame(0, Button.A, hold_frames=5),
            InputFrame(5, Button.B, hold_frames=5),  # Different button
        ]
        compressed = seq.compress()

        assert len(compressed.frames) == 2

    def test_sequence_to_dict(self):
        """Sequence serializes to dict."""
        seq = InputSequence(
            name="test_seq",
            description="Test description",
            metadata={"key": "value"}
        )
        seq.add_input(0, Button.A, hold=2)

        d = seq.to_dict()

        assert d["name"] == "test_seq"
        assert d["description"] == "Test description"
        assert len(d["frames"]) == 1
        assert d["metadata"]["key"] == "value"
        assert "total_frames" in d
        assert "duration_seconds" in d

    def test_sequence_from_dict(self):
        """Sequence deserializes from dict."""
        d = {
            "name": "loaded",
            "description": "Loaded sequence",
            "frames": [{"frame": 0, "buttons": ["START"], "hold": 2}],
            "metadata": {"source": "test"}
        }
        seq = InputSequence.from_dict(d)

        assert seq.name == "loaded"
        assert seq.description == "Loaded sequence"
        assert len(seq.frames) == 1
        assert seq.metadata["source"] == "test"

    def test_sequence_save_load_round_trip(self):
        """Save and load sequence from file."""
        seq = InputSequence(name="savable", description="Test save")
        seq.add_input(0, ["A", "B"], hold=5)
        seq.add_input(10, ["START"], hold=2)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            loaded = InputSequence.load(path)

            assert loaded.name == "savable"
            assert loaded.description == "Test save"
            assert len(loaded.frames) == 2
        finally:
            path.unlink()


# =============================================================================
# InputRecorder Tests
# =============================================================================

class TestInputRecorder:
    """Tests for InputRecorder class."""

    def test_recorder_creation(self):
        """Create recorder with default name."""
        rec = InputRecorder()
        assert rec._name == "recorded_sequence"
        assert not rec.is_recording

    def test_recorder_custom_name(self):
        """Create recorder with custom name."""
        rec = InputRecorder(name="my_recording")
        assert rec._name == "my_recording"

    def test_recorder_start_recording(self):
        """Start recording."""
        rec = InputRecorder()
        rec.start_recording()

        assert rec.is_recording is True

    def test_recorder_stop_recording(self):
        """Stop recording."""
        rec = InputRecorder()
        rec.start_recording()
        rec.stop_recording()

        assert rec.is_recording is False

    def test_recorder_record_input(self):
        """Record input during recording."""
        rec = InputRecorder()
        rec.start_recording()
        rec.record_input(Button.A, hold=3)
        rec.stop_recording()

        seq = rec.get_sequence()
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons == Button.A
        assert seq.frames[0].hold_frames == 3

    def test_recorder_record_input_not_recording(self):
        """Record input ignored when not recording."""
        rec = InputRecorder()
        rec.record_input(Button.A)  # Not recording

        seq = rec.get_sequence()
        assert len(seq.frames) == 0

    def test_recorder_record_input_strings(self):
        """Record input with string list."""
        rec = InputRecorder()
        rec.start_recording()
        rec.record_input(["B", "Y"], hold=2)
        rec.stop_recording()

        seq = rec.get_sequence()
        assert seq.frames[0].buttons & Button.B
        assert seq.frames[0].buttons & Button.Y

    def test_recorder_advance_frames(self):
        """Advance frame counter."""
        rec = InputRecorder()
        rec.start_recording()
        rec.advance_frames(10)
        rec.record_input(Button.A, hold=1)
        rec.stop_recording()

        seq = rec.get_sequence()
        assert seq.frames[0].frame_number == 10

    def test_recorder_advance_frames_not_recording(self):
        """Advance frames ignored when not recording."""
        rec = InputRecorder()
        rec.advance_frames(100)  # Not recording

        rec.start_recording()
        rec.record_input(Button.A)
        rec.stop_recording()

        seq = rec.get_sequence()
        assert seq.frames[0].frame_number == 0

    def test_recorder_get_sequence_metadata(self):
        """Sequence has recording metadata."""
        rec = InputRecorder()
        rec.start_recording()
        rec.record_input(Button.START)
        rec.stop_recording()

        seq = rec.get_sequence()
        assert "recorded_at" in seq.metadata
        assert "total_frames" in seq.metadata

    def test_recorder_multiple_inputs(self):
        """Record multiple inputs."""
        rec = InputRecorder()
        rec.start_recording()
        rec.record_input(Button.A, hold=5)  # Frame 0, hold 5
        rec.record_input(Button.B, hold=3)  # Frame 5, hold 3
        rec.record_input(Button.START, hold=2)  # Frame 8, hold 2
        rec.stop_recording()

        seq = rec.get_sequence()
        assert len(seq.frames) == 3
        assert seq.frames[0].frame_number == 0
        assert seq.frames[1].frame_number == 5
        assert seq.frames[2].frame_number == 8


# =============================================================================
# InputPlayer Tests
# =============================================================================

class TestInputPlayer:
    """Tests for InputPlayer class."""

    def test_player_creation(self):
        """Create player with emulator."""
        mock_emu = MagicMock()
        player = InputPlayer(mock_emu)

        assert not player.is_playing
        assert player.current_frame == 0

    def test_player_play_empty_sequence(self):
        """Play empty sequence returns True."""
        mock_emu = MagicMock()
        player = InputPlayer(mock_emu)

        seq = InputSequence(name="empty")
        result = player.play(seq)

        assert result is True

    def test_player_play_basic_sequence(self):
        """Play basic sequence."""
        mock_emu = MagicMock()
        mock_emu.inject_input.return_value = True
        mock_emu.step_frame.return_value = True

        player = InputPlayer(mock_emu)

        seq = InputSequence(name="test")
        seq.add_input(0, ["A"], hold=2)

        result = player.play(seq)

        assert result is True
        mock_emu.inject_input.assert_called()

    def test_player_play_with_callback(self):
        """Play with callback."""
        mock_emu = MagicMock()
        mock_emu.inject_input.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.read_state.return_value = MagicMock()

        player = InputPlayer(mock_emu)

        seq = InputSequence(name="test")
        seq.add_input(0, ["A"], hold=1)

        callback_frames = []

        def callback(frame, state):
            callback_frames.append(frame)

        player.play(seq, callback=callback)

        assert len(callback_frames) > 0

    def test_player_stop(self):
        """Stop player."""
        mock_emu = MagicMock()
        player = InputPlayer(mock_emu)

        player._playing = True
        player.stop()

        assert not player.is_playing

    def test_player_inject_failure(self):
        """Playback fails on inject failure."""
        mock_emu = MagicMock()
        mock_emu.inject_input.return_value = False

        player = InputPlayer(mock_emu)

        seq = InputSequence(name="test")
        seq.add_input(0, ["A"], hold=1)

        result = player.play(seq)

        assert result is False


# =============================================================================
# Pre-built Sequence Tests
# =============================================================================

class TestPrebuiltSequences:
    """Tests for pre-built sequence factories."""

    def test_boot_sequence_created(self):
        """Boot sequence is created."""
        seq = create_boot_sequence()

        assert seq.name == "boot_to_playable"
        assert len(seq.frames) > 0
        assert seq.metadata.get("goal") == "A.1"

    def test_boot_sequence_has_start(self):
        """Boot sequence includes START press."""
        seq = create_boot_sequence()

        start_presses = [f for f in seq.frames if f.buttons & Button.START]
        assert len(start_presses) > 0

    def test_walk_sequence_up(self):
        """Walk sequence UP."""
        seq = create_walk_sequence("UP", tiles=5)

        assert seq.name == "walk_up_5"
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons & Button.UP
        assert seq.metadata["direction"] == "UP"
        assert seq.metadata["tiles"] == 5

    def test_walk_sequence_with_run(self):
        """Walk sequence with running."""
        seq = create_walk_sequence("RIGHT", tiles=3, hold_run=True)

        assert seq.frames[0].buttons & Button.RIGHT
        assert seq.frames[0].buttons & Button.Y
        assert seq.metadata["running"] is True

    def test_walk_sequence_invalid_direction(self):
        """Walk sequence with invalid direction raises."""
        with pytest.raises(ValueError):
            create_walk_sequence("DIAGONAL", tiles=1)

    def test_menu_open_sequence(self):
        """Menu open sequence."""
        seq = create_menu_open_sequence()

        assert seq.name == "open_menu"
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons & Button.START

    def test_attack_sequence(self):
        """Attack sequence."""
        seq = create_attack_sequence()

        assert seq.name == "basic_attack"
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons & Button.B


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_button_all_pressed(self):
        """All buttons pressed."""
        all_buttons = (Button.A | Button.B | Button.X | Button.Y |
                       Button.L | Button.R | Button.START | Button.SELECT |
                       Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT)
        names = all_buttons.to_strings()
        assert len(names) == 12

    def test_sequence_large_hold(self):
        """Frame with large hold value."""
        frame = InputFrame(0, Button.A, hold_frames=10000)
        assert frame.hold_frames == 10000

    def test_sequence_zero_hold(self):
        """Frame with zero hold."""
        frame = InputFrame(0, Button.A, hold_frames=0)
        d = frame.to_dict()
        restored = InputFrame.from_dict(d)
        assert restored.hold_frames == 0

    def test_recorder_restart_clears(self):
        """Restart recording clears previous data."""
        rec = InputRecorder()
        rec.start_recording()
        rec.record_input(Button.A)
        rec.stop_recording()

        rec.start_recording()  # Restart
        rec.stop_recording()

        seq = rec.get_sequence()
        assert len(seq.frames) == 0

    def test_sequence_metadata_preserved(self):
        """Metadata is preserved through operations."""
        seq = InputSequence(
            name="test",
            metadata={"custom": "data", "number": 42}
        )
        compressed = seq.compress()
        assert compressed.metadata["custom"] == "data"
        assert compressed.metadata["number"] == 42

    def test_walk_sequence_all_directions(self):
        """Walk sequence works for all directions."""
        for direction in ["UP", "DOWN", "LEFT", "RIGHT"]:
            seq = create_walk_sequence(direction, tiles=1)
            assert seq.frames[0].buttons & Button.from_string(direction)

    def test_button_dpad_combinations(self):
        """D-pad combinations."""
        # UP + LEFT
        combo = Button.UP | Button.LEFT
        assert combo & Button.UP
        assert combo & Button.LEFT
        assert not (combo & Button.DOWN)

    def test_sequence_json_safe(self):
        """Sequence serializes to valid JSON."""
        seq = InputSequence(
            name="json_test",
            description="Unicode: \u00e9\u00f1"
        )
        seq.add_input(0, ["A", "B"], hold=5)

        d = seq.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["name"] == "json_test"

    def test_player_frame_counter(self):
        """Player frame counter updates."""
        mock_emu = MagicMock()
        mock_emu.inject_input.return_value = True
        mock_emu.step_frame.return_value = True

        player = InputPlayer(mock_emu)

        seq = InputSequence(name="test")
        seq.add_input(0, ["A"], hold=5)

        player.play(seq)

        assert player.current_frame >= 5
