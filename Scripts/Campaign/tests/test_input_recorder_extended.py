"""Extended tests for input_recorder module.

Iteration 31 - Comprehensive input recorder testing.
Covers Button enum operations, InputFrame serialization,
InputSequence compression/metadata, InputRecorder sessions,
InputPlayer playback, and pre-built sequence factories.
"""

import json
import pytest
import tempfile
import time
from pathlib import Path
from unittest.mock import Mock, patch, call

import sys

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


# =============================================================================
# Button Enum Extended Tests
# =============================================================================

class TestButtonEnumValues:
    """Test Button enum value properties."""

    def test_all_buttons_are_unique(self):
        """All button values should be distinct."""
        values = [b.value for b in Button if b != Button.NONE]
        assert len(values) == len(set(values))

    def test_all_buttons_are_powers_of_two(self):
        """All buttons (except NONE) should be single bits."""
        for button in Button:
            if button != Button.NONE:
                # Power of 2 check: value & (value - 1) == 0
                assert button.value & (button.value - 1) == 0

    def test_button_none_is_zero(self):
        """NONE button should have value 0."""
        assert Button.NONE.value == 0

    def test_button_count(self):
        """Should have 12 actual buttons (NONE is value 0, not in iteration)."""
        all_buttons = list(Button)
        # IntFlag iteration doesn't include 0/NONE value
        assert len(all_buttons) == 12

    def test_dpad_buttons_exist(self):
        """D-pad buttons should all exist."""
        assert hasattr(Button, 'UP')
        assert hasattr(Button, 'DOWN')
        assert hasattr(Button, 'LEFT')
        assert hasattr(Button, 'RIGHT')

    def test_face_buttons_exist(self):
        """Face buttons should all exist."""
        assert hasattr(Button, 'A')
        assert hasattr(Button, 'B')
        assert hasattr(Button, 'X')
        assert hasattr(Button, 'Y')

    def test_shoulder_buttons_exist(self):
        """Shoulder buttons should exist."""
        assert hasattr(Button, 'L')
        assert hasattr(Button, 'R')

    def test_special_buttons_exist(self):
        """START and SELECT should exist."""
        assert hasattr(Button, 'START')
        assert hasattr(Button, 'SELECT')


class TestButtonFromString:
    """Test Button.from_string conversion."""

    def test_lowercase_conversion(self):
        """Lowercase names should work."""
        assert Button.from_string("a") == Button.A
        assert Button.from_string("b") == Button.B
        assert Button.from_string("up") == Button.UP
        assert Button.from_string("start") == Button.START

    def test_uppercase_conversion(self):
        """Uppercase names should work."""
        assert Button.from_string("A") == Button.A
        assert Button.from_string("SELECT") == Button.SELECT

    def test_mixed_case_conversion(self):
        """Mixed case should work."""
        assert Button.from_string("Start") == Button.START
        assert Button.from_string("DoWn") == Button.DOWN

    def test_empty_string(self):
        """Empty string returns NONE."""
        assert Button.from_string("") == Button.NONE

    def test_whitespace_string(self):
        """Whitespace-only string returns NONE."""
        assert Button.from_string("   ") == Button.NONE

    def test_numeric_string(self):
        """Numeric strings return NONE."""
        assert Button.from_string("123") == Button.NONE

    def test_partial_match_fails(self):
        """Partial button names return NONE."""
        assert Button.from_string("STA") == Button.NONE
        assert Button.from_string("U") == Button.NONE


class TestButtonFromStrings:
    """Test Button.from_strings combining multiple buttons."""

    def test_empty_list(self):
        """Empty list returns NONE."""
        assert Button.from_strings([]) == Button.NONE

    def test_single_button(self):
        """Single button list works."""
        assert Button.from_strings(["A"]) == Button.A

    def test_two_buttons(self):
        """Two buttons combine."""
        combo = Button.from_strings(["A", "B"])
        assert combo == (Button.A | Button.B)

    def test_all_dpad(self):
        """All D-pad buttons combine."""
        combo = Button.from_strings(["UP", "DOWN", "LEFT", "RIGHT"])
        assert combo & Button.UP
        assert combo & Button.DOWN
        assert combo & Button.LEFT
        assert combo & Button.RIGHT

    def test_mixed_valid_invalid(self):
        """Mix of valid and invalid keeps only valid."""
        combo = Button.from_strings(["A", "invalid", "B"])
        assert combo == (Button.A | Button.B)

    def test_all_invalid(self):
        """All invalid names return NONE."""
        assert Button.from_strings(["x1", "y2", "z3"]) == Button.NONE

    def test_duplicate_buttons(self):
        """Duplicates don't change result."""
        combo = Button.from_strings(["A", "A", "A"])
        assert combo == Button.A


class TestButtonToStrings:
    """Test Button.to_strings conversion back to names."""

    def test_none_to_strings(self):
        """NONE returns empty list."""
        assert Button.NONE.to_strings() == []

    def test_single_button_to_strings(self):
        """Single button returns single name."""
        assert Button.A.to_strings() == ["A"]

    def test_combo_to_strings(self):
        """Combo returns all names."""
        combo = Button.A | Button.B | Button.UP
        names = combo.to_strings()
        assert "A" in names
        assert "B" in names
        assert "UP" in names
        assert len(names) == 3

    def test_roundtrip_conversion(self):
        """from_strings -> to_strings roundtrip."""
        original = ["A", "Y", "START"]
        combo = Button.from_strings(original)
        result = combo.to_strings()
        # Order might differ
        assert set(result) == set(original)


class TestButtonOperations:
    """Test Button flag operations."""

    def test_or_operation(self):
        """OR combines buttons."""
        combo = Button.A | Button.B
        assert combo & Button.A
        assert combo & Button.B
        assert not combo & Button.X

    def test_and_operation(self):
        """AND checks membership."""
        combo = Button.UP | Button.DOWN
        assert bool(combo & Button.UP)
        assert not bool(combo & Button.LEFT)

    def test_xor_operation(self):
        """XOR toggles buttons."""
        combo = Button.A | Button.B
        toggled = combo ^ Button.A
        assert not toggled & Button.A
        assert toggled & Button.B

    def test_not_operation(self):
        """NOT inverts bits."""
        single = Button.A
        inverted = ~single
        assert not inverted & Button.A
        # All other buttons should be set
        assert inverted & Button.B

    def test_in_place_or(self):
        """|= adds buttons."""
        combo = Button.A
        combo |= Button.B
        assert combo == (Button.A | Button.B)


# =============================================================================
# InputFrame Extended Tests
# =============================================================================

class TestInputFrameCreation:
    """Test InputFrame creation."""

    def test_default_hold_frames(self):
        """Default hold is 1."""
        frame = InputFrame(0, Button.A)
        assert frame.hold_frames == 1

    def test_zero_frame_number(self):
        """Frame 0 is valid."""
        frame = InputFrame(0, Button.A, 5)
        assert frame.frame_number == 0

    def test_large_frame_number(self):
        """Large frame numbers work."""
        frame = InputFrame(999999, Button.A, 1)
        assert frame.frame_number == 999999

    def test_none_buttons(self):
        """NONE buttons is valid (no press)."""
        frame = InputFrame(10, Button.NONE, 30)
        assert frame.buttons == Button.NONE

    def test_combo_buttons(self):
        """Combo buttons work."""
        frame = InputFrame(0, Button.A | Button.B | Button.UP, 1)
        assert frame.buttons & Button.A
        assert frame.buttons & Button.B
        assert frame.buttons & Button.UP


class TestInputFrameSerialization:
    """Test InputFrame to_dict/from_dict."""

    def test_to_dict_structure(self):
        """to_dict has expected keys."""
        frame = InputFrame(100, Button.A, 5)
        data = frame.to_dict()
        assert "frame" in data
        assert "buttons" in data
        assert "hold" in data

    def test_to_dict_buttons_as_list(self):
        """buttons should be a list of strings."""
        frame = InputFrame(0, Button.A | Button.B, 1)
        data = frame.to_dict()
        assert isinstance(data["buttons"], list)
        assert all(isinstance(b, str) for b in data["buttons"])

    def test_from_dict_missing_hold(self):
        """Missing hold defaults to 1."""
        data = {"frame": 50, "buttons": ["A"]}
        frame = InputFrame.from_dict(data)
        assert frame.hold_frames == 1

    def test_from_dict_empty_buttons(self):
        """Empty buttons list works."""
        data = {"frame": 0, "buttons": [], "hold": 10}
        frame = InputFrame.from_dict(data)
        assert frame.buttons == Button.NONE

    def test_roundtrip_none_buttons(self):
        """NONE buttons roundtrip."""
        original = InputFrame(0, Button.NONE, 60)
        data = original.to_dict()
        restored = InputFrame.from_dict(data)
        assert restored.buttons == Button.NONE
        assert restored.hold_frames == 60

    def test_roundtrip_all_buttons(self):
        """All buttons combination roundtrip."""
        all_buttons = Button.NONE
        for b in Button:
            all_buttons |= b
        original = InputFrame(0, all_buttons, 1)
        data = original.to_dict()
        restored = InputFrame.from_dict(data)
        assert restored.buttons == all_buttons


# =============================================================================
# InputSequence Extended Tests
# =============================================================================

class TestInputSequenceProperties:
    """Test InputSequence computed properties."""

    def test_empty_total_frames(self):
        """Empty sequence has 0 total frames."""
        seq = InputSequence("empty")
        assert seq.total_frames == 0

    def test_single_frame_total(self):
        """Single input total frames calculation."""
        seq = InputSequence("single")
        seq.add_input(0, Button.A, 10)
        assert seq.total_frames == 10

    def test_multiple_frames_total(self):
        """Multiple inputs - total is last frame + hold."""
        seq = InputSequence("multi")
        seq.add_input(0, Button.A, 5)
        seq.add_input(10, Button.B, 20)
        seq.add_input(50, Button.Y, 10)
        # Last frame is 50, hold is 10 -> 60
        assert seq.total_frames == 60

    def test_duration_empty(self):
        """Empty sequence has 0 duration."""
        seq = InputSequence("empty")
        assert seq.duration_seconds == 0.0

    def test_duration_one_second(self):
        """60 frames = 1 second at 60fps."""
        seq = InputSequence("one_sec")
        seq.add_input(0, Button.A, 60)
        assert abs(seq.duration_seconds - 1.0) < 0.001

    def test_duration_fractional(self):
        """30 frames = 0.5 seconds."""
        seq = InputSequence("half_sec")
        seq.add_input(0, Button.A, 30)
        assert abs(seq.duration_seconds - 0.5) < 0.001


class TestInputSequenceAddInput:
    """Test InputSequence.add_input method."""

    def test_add_with_button_enum(self):
        """Add input with Button enum."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 5)
        assert seq.frames[0].buttons == Button.A

    def test_add_with_string_list(self):
        """Add input with string list."""
        seq = InputSequence("test")
        seq.add_input(0, ["A", "B"], 5)
        assert seq.frames[0].buttons == (Button.A | Button.B)

    def test_add_multiple_in_order(self):
        """Add multiple inputs maintains order."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 1)
        seq.add_input(5, Button.B, 1)
        seq.add_input(10, Button.Y, 1)
        assert len(seq.frames) == 3
        assert seq.frames[0].buttons == Button.A
        assert seq.frames[1].buttons == Button.B
        assert seq.frames[2].buttons == Button.Y

    def test_add_out_of_order(self):
        """Inputs can be added out of order."""
        seq = InputSequence("test")
        seq.add_input(100, Button.B, 1)
        seq.add_input(0, Button.A, 1)
        assert seq.frames[0].frame_number == 100
        assert seq.frames[1].frame_number == 0


class TestInputSequenceAddWait:
    """Test InputSequence.add_wait method."""

    def test_add_wait_empty_sequence(self):
        """Wait on empty sequence returns wait frames."""
        seq = InputSequence("test")
        result = seq.add_wait(30)
        assert result == 30

    def test_add_wait_after_input(self):
        """Wait after input calculates correctly."""
        seq = InputSequence("test")
        seq.add_input(10, Button.A, 5)  # Ends at frame 15
        result = seq.add_wait(10)  # 15 + 10 = 25
        assert result == 25

    def test_add_wait_zero(self):
        """Zero wait returns current position."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 10)
        result = seq.add_wait(0)
        assert result == 10


class TestInputSequenceCompress:
    """Test InputSequence.compress method."""

    def test_compress_empty(self):
        """Compress empty sequence."""
        seq = InputSequence("empty")
        compressed = seq.compress()
        assert len(compressed.frames) == 0

    def test_compress_single_frame(self):
        """Single frame doesn't change."""
        seq = InputSequence("single")
        seq.add_input(0, Button.A, 5)
        compressed = seq.compress()
        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 5

    def test_compress_merges_consecutive(self):
        """Consecutive identical inputs merge."""
        seq = InputSequence("merge")
        seq.add_input(0, Button.A, 1)
        seq.add_input(1, Button.A, 1)
        seq.add_input(2, Button.A, 1)
        compressed = seq.compress()
        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 3

    def test_compress_no_merge_different(self):
        """Different buttons don't merge."""
        seq = InputSequence("different")
        seq.add_input(0, Button.A, 1)
        seq.add_input(1, Button.B, 1)
        compressed = seq.compress()
        assert len(compressed.frames) == 2

    def test_compress_no_merge_gap(self):
        """Same buttons with gap don't merge."""
        seq = InputSequence("gap")
        seq.add_input(0, Button.A, 1)
        seq.add_input(5, Button.A, 1)  # Gap at frames 1-4
        compressed = seq.compress()
        assert len(compressed.frames) == 2

    def test_compress_preserves_metadata(self):
        """Compress preserves name, description, metadata."""
        seq = InputSequence("test", "Test description")
        seq.metadata["key"] = "value"
        seq.add_input(0, Button.A, 1)
        compressed = seq.compress()
        assert compressed.name == "test"
        assert compressed.description == "Test description"
        assert compressed.metadata["key"] == "value"

    def test_compress_sorts_frames(self):
        """Compress sorts frames by frame number."""
        seq = InputSequence("unsorted")
        seq.add_input(10, Button.B, 1)
        seq.add_input(0, Button.A, 1)
        compressed = seq.compress()
        assert compressed.frames[0].frame_number == 0
        assert compressed.frames[1].frame_number == 10


class TestInputSequenceSerialization:
    """Test InputSequence to_dict/from_dict."""

    def test_to_dict_includes_computed(self):
        """to_dict includes computed properties."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 60)
        data = seq.to_dict()
        assert "total_frames" in data
        assert "duration_seconds" in data

    def test_to_dict_metadata(self):
        """to_dict includes metadata."""
        seq = InputSequence("test")
        seq.metadata["author"] = "tester"
        seq.metadata["version"] = 2
        data = seq.to_dict()
        assert data["metadata"]["author"] == "tester"
        assert data["metadata"]["version"] == 2

    def test_from_dict_missing_optional_fields(self):
        """from_dict handles missing optional fields."""
        data = {
            "name": "minimal",
            "frames": []
        }
        seq = InputSequence.from_dict(data)
        assert seq.name == "minimal"
        assert seq.description == ""
        assert seq.metadata == {}

    def test_roundtrip_complex(self):
        """Complex sequence roundtrip."""
        original = InputSequence("complex", "A complex sequence")
        original.add_input(0, Button.A | Button.B, 10)
        original.add_input(30, ["UP", "Y"], 60)
        original.add_input(100, Button.START, 2)
        original.metadata["test"] = True

        data = original.to_dict()
        restored = InputSequence.from_dict(data)

        assert restored.name == original.name
        assert restored.description == original.description
        assert len(restored.frames) == len(original.frames)
        assert restored.metadata["test"] is True


class TestInputSequenceFileSaveLoad:
    """Test InputSequence file operations."""

    def test_save_creates_file(self):
        """Save creates JSON file."""
        seq = InputSequence("test")
        seq.add_input(0, Button.A, 5)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            assert path.exists()
            content = path.read_text()
            data = json.loads(content)
            assert data["name"] == "test"
        finally:
            path.unlink()

    def test_save_with_string_path(self):
        """Save accepts string path."""
        seq = InputSequence("test")
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = f.name

        try:
            seq.save(path)  # String, not Path
            assert Path(path).exists()
        finally:
            Path(path).unlink()

    def test_load_returns_sequence(self):
        """Load returns InputSequence."""
        seq = InputSequence("original")
        seq.add_input(0, Button.B, 10)

        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            loaded = InputSequence.load(path)
            assert isinstance(loaded, InputSequence)
            assert loaded.name == "original"
        finally:
            path.unlink()

    def test_load_file_not_found(self):
        """Load raises on missing file."""
        with pytest.raises(FileNotFoundError):
            InputSequence.load("/nonexistent/path/seq.json")


# =============================================================================
# InputRecorder Extended Tests
# =============================================================================

class TestInputRecorderInit:
    """Test InputRecorder initialization."""

    def test_default_name(self):
        """Default name is recorded_sequence."""
        recorder = InputRecorder()
        seq = recorder.get_sequence()
        assert seq.name == "recorded_sequence"

    def test_custom_name(self):
        """Custom name is used."""
        recorder = InputRecorder("my_recording")
        seq = recorder.get_sequence()
        assert seq.name == "my_recording"


class TestInputRecorderRecording:
    """Test InputRecorder recording state."""

    def test_not_recording_initially(self):
        """Starts not recording."""
        recorder = InputRecorder()
        assert recorder.is_recording is False

    def test_start_sets_recording(self):
        """start_recording sets flag."""
        recorder = InputRecorder()
        recorder.start_recording()
        assert recorder.is_recording is True

    def test_stop_clears_recording(self):
        """stop_recording clears flag."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.stop_recording()
        assert recorder.is_recording is False

    def test_multiple_start_stop_cycles(self):
        """Can start/stop multiple times."""
        recorder = InputRecorder()
        for _ in range(3):
            recorder.start_recording()
            assert recorder.is_recording
            recorder.stop_recording()
            assert not recorder.is_recording


class TestInputRecorderInputs:
    """Test InputRecorder input recording."""

    def test_record_button_enum(self):
        """Record with Button enum."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, 5)
        seq = recorder.get_sequence()
        assert len(seq.frames) == 1
        assert seq.frames[0].buttons == Button.A

    def test_record_string_list(self):
        """Record with string list."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(["B", "Y"], 3)
        seq = recorder.get_sequence()
        assert seq.frames[0].buttons == (Button.B | Button.Y)

    def test_record_ignores_when_not_recording(self):
        """Inputs ignored when not recording."""
        recorder = InputRecorder()
        recorder.record_input(Button.A, 5)
        seq = recorder.get_sequence()
        assert len(seq.frames) == 0

    def test_frame_counter_advances(self):
        """Frame counter advances with each input."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, 10)  # frames 0-9
        recorder.record_input(Button.B, 5)   # frames 10-14
        seq = recorder.get_sequence()
        assert seq.frames[0].frame_number == 0
        assert seq.frames[1].frame_number == 10

    def test_advance_frames_without_input(self):
        """advance_frames increases counter."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.advance_frames(50)
        recorder.record_input(Button.A, 1)
        seq = recorder.get_sequence()
        assert seq.frames[0].frame_number == 50

    def test_advance_frames_ignores_when_not_recording(self):
        """advance_frames ignored when not recording."""
        recorder = InputRecorder()
        recorder.advance_frames(100)
        recorder.start_recording()
        recorder.record_input(Button.A, 1)
        seq = recorder.get_sequence()
        assert seq.frames[0].frame_number == 0


class TestInputRecorderGetSequence:
    """Test InputRecorder.get_sequence method."""

    def test_get_sequence_copies_frames(self):
        """get_sequence returns copy of frames."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, 5)
        seq1 = recorder.get_sequence()
        seq2 = recorder.get_sequence()
        assert seq1.frames is not seq2.frames

    def test_get_sequence_has_metadata(self):
        """Sequence includes metadata."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, 10)
        seq = recorder.get_sequence()
        assert "recorded_at" in seq.metadata
        assert "total_frames" in seq.metadata

    def test_get_sequence_has_description(self):
        """Sequence includes timestamp description."""
        recorder = InputRecorder()
        recorder.start_recording()
        seq = recorder.get_sequence()
        assert "Recorded at" in seq.description


class TestInputRecorderRestart:
    """Test InputRecorder restart behavior."""

    def test_start_clears_previous(self):
        """Starting recording clears previous data."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A, 10)
        recorder.stop_recording()

        recorder.start_recording()  # Should clear
        seq = recorder.get_sequence()
        assert len(seq.frames) == 0


# =============================================================================
# InputPlayer Extended Tests
# =============================================================================

class TestInputPlayerInit:
    """Test InputPlayer initialization."""

    def test_not_playing_initially(self):
        """Starts not playing."""
        emu = Mock()
        player = InputPlayer(emu)
        assert player.is_playing is False

    def test_frame_starts_at_zero(self):
        """Current frame starts at 0."""
        emu = Mock()
        player = InputPlayer(emu)
        assert player.current_frame == 0


class TestInputPlayerPlay:
    """Test InputPlayer.play method."""

    @pytest.fixture
    def mock_emu(self):
        """Create mock emulator."""
        emu = Mock()
        emu.inject_input.return_value = True
        emu.step_frame.return_value = True
        emu.read_state.return_value = Mock()
        return emu

    def test_play_empty_sequence(self, mock_emu):
        """Playing empty sequence succeeds."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("empty")
        result = player.play(seq)
        assert result is True

    def test_play_single_input(self, mock_emu):
        """Playing single input calls inject and step."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("single")
        seq.add_input(0, Button.A, 1)
        result = player.play(seq)
        assert result is True
        mock_emu.inject_input.assert_called()

    def test_play_calls_step_frame(self, mock_emu):
        """Play calls step_frame for each frame."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("steps")
        seq.add_input(0, Button.A, 5)
        player.play(seq)
        # Should step for each frame up to total_frames
        assert mock_emu.step_frame.call_count >= 5

    def test_play_inject_fails_returns_false(self, mock_emu):
        """Returns False if inject_input fails."""
        mock_emu.inject_input.return_value = False
        player = InputPlayer(mock_emu)
        seq = InputSequence("fail")
        seq.add_input(0, Button.A, 1)
        result = player.play(seq)
        assert result is False

    def test_play_step_fails_returns_false(self, mock_emu):
        """Returns False if step_frame fails."""
        mock_emu.step_frame.return_value = False
        player = InputPlayer(mock_emu)
        seq = InputSequence("fail")
        seq.add_input(0, Button.A, 1)
        result = player.play(seq)
        assert result is False

    def test_play_with_callback(self, mock_emu):
        """Callback receives frame and state."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("callback")
        seq.add_input(0, Button.A, 3)

        received = []
        def cb(frame, state):
            received.append((frame, state))

        player.play(seq, callback=cb)
        assert len(received) > 0
        # First callback should be frame 1 (after first step)
        assert received[0][0] == 1

    def test_play_multiple_inputs(self, mock_emu):
        """Multiple inputs at different frames."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("multi")
        seq.add_input(0, Button.A, 2)
        seq.add_input(5, Button.B, 2)
        result = player.play(seq)
        assert result is True
        # inject_input called for both inputs
        assert mock_emu.inject_input.call_count >= 2

    def test_play_none_buttons_skipped(self, mock_emu):
        """Inputs with NONE buttons don't call inject."""
        player = InputPlayer(mock_emu)
        seq = InputSequence("none")
        seq.add_input(0, Button.NONE, 5)
        player.play(seq)
        # NONE buttons result in empty to_strings(), so inject not called
        mock_emu.inject_input.assert_not_called()


class TestInputPlayerStop:
    """Test InputPlayer.stop method."""

    def test_stop_sets_flag(self):
        """Stop sets is_playing to False."""
        emu = Mock()
        player = InputPlayer(emu)
        player._playing = True
        player.stop()
        assert player.is_playing is False


# =============================================================================
# Pre-built Sequence Tests
# =============================================================================

class TestCreateBootSequence:
    """Test create_boot_sequence factory."""

    def test_name(self):
        """Boot sequence has correct name."""
        seq = create_boot_sequence()
        assert seq.name == "boot_to_playable"

    def test_has_frames(self):
        """Boot sequence has input frames."""
        seq = create_boot_sequence()
        assert len(seq.frames) > 0

    def test_metadata_goal(self):
        """Metadata includes goal A.1."""
        seq = create_boot_sequence()
        assert seq.metadata.get("goal") == "A.1"

    def test_metadata_type(self):
        """Metadata includes type."""
        seq = create_boot_sequence()
        assert seq.metadata.get("type") == "automation"

    def test_includes_start_press(self):
        """Sequence includes START press."""
        seq = create_boot_sequence()
        has_start = any(f.buttons & Button.START for f in seq.frames)
        assert has_start

    def test_includes_a_press(self):
        """Sequence includes A press for file select."""
        seq = create_boot_sequence()
        has_a = any(f.buttons & Button.A for f in seq.frames)
        assert has_a


class TestCreateWalkSequence:
    """Test create_walk_sequence factory."""

    @pytest.mark.parametrize("direction", ["UP", "DOWN", "LEFT", "RIGHT"])
    def test_all_directions(self, direction):
        """All cardinal directions work."""
        seq = create_walk_sequence(direction, 1)
        expected_button = Button.from_string(direction)
        assert seq.frames[0].buttons & expected_button

    def test_lowercase_direction(self):
        """Lowercase direction works."""
        seq = create_walk_sequence("up", 1)
        assert seq.frames[0].buttons & Button.UP

    def test_tiles_affect_hold(self):
        """More tiles = longer hold."""
        seq1 = create_walk_sequence("UP", 1)
        seq5 = create_walk_sequence("UP", 5)
        assert seq5.frames[0].hold_frames > seq1.frames[0].hold_frames

    def test_running_adds_y(self):
        """Running adds Y button."""
        seq = create_walk_sequence("UP", 1, hold_run=True)
        assert seq.frames[0].buttons & Button.UP
        assert seq.frames[0].buttons & Button.Y

    def test_running_shorter_hold(self):
        """Running has shorter hold per tile."""
        walk = create_walk_sequence("UP", 5, hold_run=False)
        run = create_walk_sequence("UP", 5, hold_run=True)
        assert run.frames[0].hold_frames < walk.frames[0].hold_frames

    def test_metadata_direction(self):
        """Metadata includes direction."""
        seq = create_walk_sequence("LEFT", 3)
        assert seq.metadata["direction"] == "LEFT"

    def test_metadata_tiles(self):
        """Metadata includes tile count."""
        seq = create_walk_sequence("RIGHT", 7)
        assert seq.metadata["tiles"] == 7

    def test_metadata_running(self):
        """Metadata includes running flag."""
        seq = create_walk_sequence("DOWN", 1, hold_run=True)
        assert seq.metadata["running"] is True

    def test_invalid_direction_raises(self):
        """Invalid direction raises ValueError."""
        with pytest.raises(ValueError, match="Invalid direction"):
            create_walk_sequence("DIAGONAL", 1)

    def test_invalid_direction_updown(self):
        """UPDOWN is invalid."""
        with pytest.raises(ValueError):
            create_walk_sequence("UPDOWN", 1)


class TestCreateMenuOpenSequence:
    """Test create_menu_open_sequence factory."""

    def test_name(self):
        """Has correct name."""
        seq = create_menu_open_sequence()
        assert seq.name == "open_menu"

    def test_presses_start(self):
        """Presses START button."""
        seq = create_menu_open_sequence()
        assert seq.frames[0].buttons & Button.START

    def test_single_frame(self):
        """Only one input frame."""
        seq = create_menu_open_sequence()
        assert len(seq.frames) == 1

    def test_metadata_type(self):
        """Metadata type is menu."""
        seq = create_menu_open_sequence()
        assert seq.metadata["type"] == "menu"


class TestCreateAttackSequence:
    """Test create_attack_sequence factory."""

    def test_name(self):
        """Has correct name."""
        seq = create_attack_sequence()
        assert seq.name == "basic_attack"

    def test_presses_b(self):
        """Presses B button for attack."""
        seq = create_attack_sequence()
        assert seq.frames[0].buttons & Button.B

    def test_single_frame(self):
        """Only one input frame."""
        seq = create_attack_sequence()
        assert len(seq.frames) == 1

    def test_metadata_type(self):
        """Metadata type is combat."""
        seq = create_attack_sequence()
        assert seq.metadata["type"] == "combat"


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestRecordAndPlayback:
    """Test recording and playing back sequences."""

    def test_record_then_serialize_then_play(self):
        """Full workflow: record -> save -> load -> play."""
        # Record
        recorder = InputRecorder("workflow_test")
        recorder.start_recording()
        recorder.record_input(Button.START, 2)
        recorder.advance_frames(30)
        recorder.record_input(Button.A, 5)
        recorder.stop_recording()
        seq = recorder.get_sequence()

        # Save and load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            loaded = InputSequence.load(path)

            # Play
            mock_emu = Mock()
            mock_emu.inject_input.return_value = True
            mock_emu.step_frame.return_value = True
            mock_emu.read_state.return_value = Mock()

            player = InputPlayer(mock_emu)
            result = player.play(loaded)

            assert result is True
            assert mock_emu.inject_input.call_count >= 2
        finally:
            path.unlink()

    def test_compress_before_save(self):
        """Compress sequence before saving reduces size."""
        seq = InputSequence("compressible")
        # Add 100 consecutive A presses
        for i in range(100):
            seq.add_input(i, Button.A, 1)

        uncompressed_data = seq.to_dict()
        compressed = seq.compress()
        compressed_data = compressed.to_dict()

        # Compressed should have fewer frames
        assert len(compressed_data["frames"]) < len(uncompressed_data["frames"])
        # But total duration same
        assert compressed.total_frames == seq.total_frames
