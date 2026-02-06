# -*- coding: utf-8 -*-
"""Tests for file select navigator module.

These tests verify the file select navigation functionality
for Goal A.2 (Navigate file select).
"""

import json
import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call

from scripts.campaign.file_select_navigator import (
    FileSelectState,
    FileSlotStatus,
    SelectionResult,
    FileSlotInfo,
    FileSelectSnapshot,
    NavigationAttempt,
    FileSelectAddresses,
    FileSelectNavigator,
    create_file_select_sequence,
    create_new_game_sequence,
)


class TestFileSelectState:
    """Test FileSelectState enum."""

    def test_all_states_exist(self):
        """All expected states should exist."""
        assert FileSelectState.NOT_ON_SCREEN
        assert FileSelectState.MAIN_MENU
        assert FileSelectState.SLOT_SELECTED
        assert FileSelectState.COPY_MENU
        assert FileSelectState.ERASE_MENU
        assert FileSelectState.CONFIRM_DIALOG
        assert FileSelectState.LOADING
        assert FileSelectState.NAME_ENTRY

    def test_states_are_unique(self):
        """Each state should have a unique value."""
        states = list(FileSelectState)
        values = [s.value for s in states]
        assert len(values) == len(set(values))

    def test_state_count(self):
        """Should have 8 file select states."""
        assert len(FileSelectState) == 8


class TestFileSlotStatus:
    """Test FileSlotStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses should exist."""
        assert FileSlotStatus.EMPTY
        assert FileSlotStatus.HAS_DATA
        assert FileSlotStatus.UNKNOWN

    def test_status_count(self):
        """Should have 3 slot statuses."""
        assert len(FileSlotStatus) == 3


class TestSelectionResult:
    """Test SelectionResult enum."""

    def test_success_exists(self):
        """SUCCESS result should exist."""
        assert SelectionResult.SUCCESS

    def test_failure_modes_exist(self):
        """All failure modes should exist."""
        assert SelectionResult.FAILED_NOT_ON_SCREEN
        assert SelectionResult.FAILED_TIMEOUT
        assert SelectionResult.FAILED_WRONG_STATE
        assert SelectionResult.FAILED_EMPTY_SLOT
        assert SelectionResult.FAILED_NAVIGATION

    def test_result_count(self):
        """Should have 6 result types."""
        assert len(SelectionResult) == 6


class TestFileSlotInfo:
    """Test FileSlotInfo dataclass."""

    def test_create_empty_slot(self):
        """Can create info for empty slot."""
        info = FileSlotInfo(slot_number=1, status=FileSlotStatus.EMPTY)
        assert info.slot_number == 1
        assert info.status == FileSlotStatus.EMPTY
        assert info.player_name == ""
        assert info.heart_containers == 0

    def test_create_full_slot(self):
        """Can create info with all fields."""
        info = FileSlotInfo(
            slot_number=2,
            status=FileSlotStatus.HAS_DATA,
            player_name="LINK",
            heart_containers=10,
            death_count=5,
            dungeon_progress=3,
        )
        assert info.player_name == "LINK"
        assert info.heart_containers == 10
        assert info.death_count == 5
        assert info.dungeon_progress == 3


class TestFileSelectSnapshot:
    """Test FileSelectSnapshot dataclass."""

    def test_create_snapshot(self):
        """Can create basic snapshot."""
        snap = FileSelectSnapshot(
            timestamp="2026-01-24T12:00:00",
            game_mode=0x02,
            cursor_position=0,
            sub_state=0x00,
        )
        assert snap.game_mode == 0x02
        assert snap.cursor_position == 0

    def test_is_on_file_select_true(self):
        """is_on_file_select True when mode is 0x02."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=0, sub_state=0
        )
        assert snap.is_on_file_select is True

    def test_is_on_file_select_false(self):
        """is_on_file_select False for other modes."""
        for mode in [0x00, 0x01, 0x07, 0x09]:
            snap = FileSelectSnapshot(
                timestamp="now", game_mode=mode, cursor_position=0, sub_state=0
            )
            assert snap.is_on_file_select is False

    def test_current_slot_position_0(self):
        """Cursor position 0 = slot 1."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=0, sub_state=0
        )
        assert snap.current_slot == 1

    def test_current_slot_position_1(self):
        """Cursor position 1 = slot 2."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=1, sub_state=0
        )
        assert snap.current_slot == 2

    def test_current_slot_position_2(self):
        """Cursor position 2 = slot 3."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=2, sub_state=0
        )
        assert snap.current_slot == 3

    def test_current_slot_menu_option(self):
        """Cursor on menu option (position > 2) returns 0."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=3, sub_state=0
        )
        assert snap.current_slot == 0

    def test_to_dict(self):
        """to_dict produces valid dictionary."""
        snap = FileSelectSnapshot(
            timestamp="2026-01-24T12:00:00",
            game_mode=0x02,
            cursor_position=1,
            sub_state=0x00,
            slot_states=[FileSlotStatus.HAS_DATA, FileSlotStatus.EMPTY, FileSlotStatus.UNKNOWN],
            frame_count=100,
        )
        d = snap.to_dict()
        assert d["timestamp"] == "2026-01-24T12:00:00"
        assert d["game_mode"] == 0x02
        assert d["cursor_position"] == 1
        assert d["is_on_file_select"] is True
        assert d["current_slot"] == 2
        assert len(d["slot_states"]) == 3

    def test_to_dict_serializable(self):
        """to_dict output is JSON serializable."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=0, sub_state=0,
            slot_states=[FileSlotStatus.EMPTY]
        )
        json_str = json.dumps(snap.to_dict())
        assert len(json_str) > 0


class TestNavigationAttempt:
    """Test NavigationAttempt dataclass."""

    def test_create_success_attempt(self):
        """Can create successful attempt."""
        attempt = NavigationAttempt(
            success=True,
            slot=1,
            result=SelectionResult.SUCCESS,
        )
        assert attempt.success is True
        assert attempt.slot == 1
        assert attempt.result == SelectionResult.SUCCESS

    def test_create_failed_attempt(self):
        """Can create failed attempt with error message."""
        attempt = NavigationAttempt(
            success=False,
            slot=2,
            result=SelectionResult.FAILED_TIMEOUT,
            error_message="Timed out waiting for load",
        )
        assert attempt.success is False
        assert attempt.error_message == "Timed out waiting for load"

    def test_to_dict(self):
        """to_dict produces valid dictionary."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=0, sub_state=0
        )
        attempt = NavigationAttempt(
            success=True,
            slot=1,
            result=SelectionResult.SUCCESS,
            start_snapshot=snap,
            inputs_used=["MOVE", "A"],
            duration_frames=50,
        )
        d = attempt.to_dict()
        assert d["success"] is True
        assert d["slot"] == 1
        assert d["result"] == "SUCCESS"
        assert d["inputs_used"] == ["MOVE", "A"]
        assert d["start_snapshot"] is not None

    def test_to_dict_without_snapshots(self):
        """to_dict works without snapshots."""
        attempt = NavigationAttempt(
            success=False,
            slot=3,
            result=SelectionResult.FAILED_NOT_ON_SCREEN,
        )
        d = attempt.to_dict()
        assert d["start_snapshot"] is None
        assert d["end_snapshot"] is None


class TestFileSelectAddresses:
    """Test memory address constants."""

    def test_game_mode_address(self):
        """GameMode address is correct."""
        assert FileSelectAddresses.GAME_MODE == 0x7E0010

    def test_cursor_position_address(self):
        """Cursor position address is defined."""
        assert FileSelectAddresses.CURSOR_POSITION == 0x7E0200

    def test_sub_state_address(self):
        """Sub-state address is defined."""
        assert FileSelectAddresses.SUB_STATE == 0x7E0202


class TestFileSelectNavigator:
    """Test FileSelectNavigator class."""

    @pytest.fixture
    def mock_bridge(self):
        """Create a mock bridge."""
        bridge = Mock()
        bridge.read_memory = Mock(return_value=[0x02])  # Default: on file select
        bridge.press_button = Mock()
        bridge.run_frames = Mock()
        return bridge

    @pytest.fixture
    def navigator(self, mock_bridge):
        """Create navigator with mock bridge."""
        return FileSelectNavigator(mock_bridge)

    def test_init_default_timeout(self, mock_bridge):
        """Default timeout is 300 frames."""
        nav = FileSelectNavigator(mock_bridge)
        assert nav.timeout_frames == 300

    def test_init_custom_timeout(self, mock_bridge):
        """Can set custom timeout."""
        nav = FileSelectNavigator(mock_bridge, timeout_frames=500)
        assert nav.timeout_frames == 500

    def test_capture_state_returns_snapshot(self, navigator, mock_bridge):
        """capture_state returns FileSelectSnapshot."""
        # Set up memory returns for mode, cursor, sub_state
        mock_bridge.read_memory.side_effect = [
            [0x02],  # game_mode
            [0x01],  # cursor_position
            [0x00],  # sub_state
        ]
        snap = navigator.capture_state()
        assert isinstance(snap, FileSelectSnapshot)
        assert snap.game_mode == 0x02
        assert snap.cursor_position == 0x01

    def test_capture_state_increments_frame_count(self, navigator, mock_bridge):
        """Each capture increments frame count."""
        mock_bridge.read_memory.return_value = [0x02]
        navigator.capture_state()
        navigator.capture_state()
        navigator.capture_state()
        assert navigator._frame_count >= 3

    def test_get_state_not_on_screen(self, navigator, mock_bridge):
        """get_state returns NOT_ON_SCREEN for wrong mode."""
        mock_bridge.read_memory.side_effect = [
            [0x09],  # game_mode = overworld
            [0x00],  # cursor
            [0x00],  # sub_state
        ]
        state = navigator.get_state()
        assert state == FileSelectState.NOT_ON_SCREEN

    def test_get_state_main_menu(self, navigator, mock_bridge):
        """get_state returns MAIN_MENU for sub_state 0."""
        mock_bridge.read_memory.side_effect = [
            [0x02],  # game_mode = file select
            [0x00],  # cursor
            [0x00],  # sub_state = 0 (main)
        ]
        state = navigator.get_state()
        assert state == FileSelectState.MAIN_MENU

    def test_get_state_slot_selected(self, navigator, mock_bridge):
        """get_state returns SLOT_SELECTED for sub_state 1."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x01],  # sub_state = 1
        ]
        state = navigator.get_state()
        assert state == FileSelectState.SLOT_SELECTED

    def test_get_state_copy_menu(self, navigator, mock_bridge):
        """get_state returns COPY_MENU for sub_state 2."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x02],  # sub_state = 2
        ]
        state = navigator.get_state()
        assert state == FileSelectState.COPY_MENU

    def test_get_state_erase_menu(self, navigator, mock_bridge):
        """get_state returns ERASE_MENU for sub_state 3."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x03],  # sub_state = 3
        ]
        state = navigator.get_state()
        assert state == FileSelectState.ERASE_MENU

    def test_get_state_confirm_dialog(self, navigator, mock_bridge):
        """get_state returns CONFIRM_DIALOG for sub_state 4."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x04],  # sub_state = 4
        ]
        state = navigator.get_state()
        assert state == FileSelectState.CONFIRM_DIALOG

    def test_get_state_loading(self, navigator, mock_bridge):
        """get_state returns LOADING for sub_state 5."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x05],  # sub_state = 5
        ]
        state = navigator.get_state()
        assert state == FileSelectState.LOADING

    def test_get_state_name_entry(self, navigator, mock_bridge):
        """get_state returns NAME_ENTRY for sub_state 6."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x06],  # sub_state = 6
        ]
        state = navigator.get_state()
        assert state == FileSelectState.NAME_ENTRY


class TestNavigatorCursorMovement:
    """Test cursor movement functionality."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge for cursor tests."""
        bridge = Mock()
        bridge.press_button = Mock()
        bridge.run_frames = Mock()
        return bridge

    @pytest.fixture
    def navigator(self, mock_bridge):
        """Create navigator."""
        return FileSelectNavigator(mock_bridge)

    def test_move_to_slot_invalid_low(self, navigator, mock_bridge):
        """Slot 0 is invalid."""
        result = navigator.move_cursor_to_slot(0)
        assert result is False

    def test_move_to_slot_invalid_high(self, navigator, mock_bridge):
        """Slot 4 is invalid."""
        result = navigator.move_cursor_to_slot(4)
        assert result is False

    def test_move_to_slot_not_on_file_select(self, navigator, mock_bridge):
        """Moving fails when not on file select."""
        mock_bridge.read_memory.side_effect = [
            [0x09],  # game_mode = overworld (not file select)
            [0x00], [0x00],
        ]
        result = navigator.move_cursor_to_slot(2)
        assert result is False

    def test_move_to_same_slot(self, navigator, mock_bridge):
        """Moving to current slot succeeds immediately."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Already on slot 1 (position 0)
        ]
        result = navigator.move_cursor_to_slot(1)
        assert result is True

    def test_move_down_one_slot(self, navigator, mock_bridge):
        """Moving from slot 1 to slot 2 presses DOWN once."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Start at slot 1
            [0x02], [0x01], [0x00],  # After move, at slot 2
        ]
        result = navigator.move_cursor_to_slot(2)
        assert result is True
        mock_bridge.press_button.assert_called()

    def test_move_up_one_slot(self, navigator, mock_bridge):
        """Moving from slot 2 to slot 1 presses UP once."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x01], [0x00],  # Start at slot 2
            [0x02], [0x00], [0x00],  # After move, at slot 1
        ]
        result = navigator.move_cursor_to_slot(1)
        assert result is True


class TestNavigatorFileSelection:
    """Test file selection functionality."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = Mock()
        bridge.press_button = Mock()
        bridge.run_frames = Mock()
        return bridge

    @pytest.fixture
    def navigator(self, mock_bridge):
        """Create navigator."""
        return FileSelectNavigator(mock_bridge, timeout_frames=10)

    def test_select_file_not_on_screen(self, navigator, mock_bridge):
        """select_file fails when not on file select."""
        mock_bridge.read_memory.side_effect = [
            [0x09], [0x00], [0x00],  # Overworld mode
        ]
        result = navigator.select_file(1)
        assert result.success is False
        assert result.result == SelectionResult.FAILED_NOT_ON_SCREEN

    def test_select_file_success(self, navigator, mock_bridge):
        """select_file succeeds when game loads."""
        # Start on file select, cursor at slot 1
        # Then after selection, mode changes to intro (0x05)
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Initial: file select
            [0x02], [0x00], [0x00],  # move_cursor check
            [0x02], [0x00], [0x00],  # After move verify
            [0x05], [0x00], [0x00],  # Mode changed to intro
        ]
        result = navigator.select_file(1)
        assert result.success is True
        assert result.result == SelectionResult.SUCCESS
        assert result.slot == 1

    def test_select_file_timeout(self, navigator, mock_bridge):
        """select_file fails on timeout."""
        # Stay on file select forever (mode never changes)
        # Must provide proper sequence: initial state, move check, verify, then wait loop
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Initial: file select, cursor at 0
            [0x02], [0x00], [0x00],  # move_cursor check
            [0x02], [0x00], [0x00],  # After move verify (cursor at slot 1)
        ] + [[0x02], [0x00], [0x00]] * 20  # Timeout loop - stays on file select
        result = navigator.select_file(1)
        assert result.success is False
        assert result.result == SelectionResult.FAILED_TIMEOUT


class TestNavigatorNewGame:
    """Test new game functionality."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = Mock()
        bridge.press_button = Mock()
        bridge.run_frames = Mock()
        return bridge

    @pytest.fixture
    def navigator(self, mock_bridge):
        """Create navigator."""
        return FileSelectNavigator(mock_bridge, timeout_frames=10)

    def test_new_game_not_on_screen(self, navigator, mock_bridge):
        """start_new_game fails when not on file select."""
        mock_bridge.read_memory.side_effect = [
            [0x07], [0x00], [0x00],  # Dungeon mode
        ]
        result = navigator.start_new_game(1)
        assert result.success is False
        assert result.result == SelectionResult.FAILED_NOT_ON_SCREEN

    def test_new_game_enters_name_entry(self, navigator, mock_bridge):
        """start_new_game handles name entry screen."""
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Initial: file select
            [0x02], [0x00], [0x00],  # move check
            [0x02], [0x00], [0x00],  # verify position
            [0x02], [0x00], [0x06],  # Sub-state 6 = name entry
            [0x05], [0x00], [0x00],  # Mode changes to intro
        ]
        result = navigator.start_new_game(1)
        assert result.success is True


class TestNavigatorWaitFunctions:
    """Test wait functionality."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = Mock()
        bridge.run_frames = Mock()
        return bridge

    @pytest.fixture
    def navigator(self, mock_bridge):
        """Create navigator."""
        return FileSelectNavigator(mock_bridge)

    def test_wait_for_file_select_immediate(self, navigator, mock_bridge):
        """wait_for_file_select returns True when already there."""
        mock_bridge.read_memory.return_value = [0x02]
        result = navigator.wait_for_file_select(timeout_frames=10)
        assert result is True

    def test_wait_for_file_select_timeout(self, navigator, mock_bridge):
        """wait_for_file_select returns False on timeout."""
        mock_bridge.read_memory.return_value = [0x01]  # Title screen
        result = navigator.wait_for_file_select(timeout_frames=5)
        assert result is False


class TestNavigatorSlotInfo:
    """Test slot info retrieval."""

    @pytest.fixture
    def navigator(self):
        """Create navigator with mock."""
        return FileSelectNavigator(Mock())

    def test_get_slot_info_valid_slot(self, navigator):
        """get_slot_info returns info for valid slot."""
        info = navigator.get_slot_info(1)
        assert info is not None
        assert info.slot_number == 1

    def test_get_slot_info_invalid_low(self, navigator):
        """get_slot_info returns None for slot 0."""
        info = navigator.get_slot_info(0)
        assert info is None

    def test_get_slot_info_invalid_high(self, navigator):
        """get_slot_info returns None for slot 4."""
        info = navigator.get_slot_info(4)
        assert info is None


class TestNavigatorResultSaving:
    """Test result saving functionality."""

    @pytest.fixture
    def navigator(self):
        """Create navigator."""
        return FileSelectNavigator(Mock())

    def test_save_results_default_path(self, navigator, tmp_path):
        """save_results uses default path."""
        attempt = NavigationAttempt(
            success=True, slot=1, result=SelectionResult.SUCCESS
        )
        with patch('builtins.open', create=True) as mock_open:
            mock_open.return_value.__enter__ = Mock()
            mock_open.return_value.__exit__ = Mock(return_value=False)
            path = navigator.save_results(attempt)
            assert path == Path("file_select_result.json")

    def test_save_results_custom_path(self, navigator, tmp_path):
        """save_results uses custom path."""
        attempt = NavigationAttempt(
            success=False, slot=2, result=SelectionResult.FAILED_TIMEOUT
        )
        custom_path = tmp_path / "custom_result.json"
        result_path = navigator.save_results(attempt, custom_path)
        assert result_path == custom_path
        assert custom_path.exists()

        # Verify content
        with open(custom_path) as f:
            data = json.load(f)
        assert data["success"] is False
        assert data["slot"] == 2
        assert data["result"] == "FAILED_TIMEOUT"


class TestFactoryFunctions:
    """Test factory functions for input sequences."""

    def test_create_file_select_sequence_slot_1(self):
        """create_file_select_sequence for slot 1."""
        seq = create_file_select_sequence(1)
        assert seq.name == "file_select_slot_1"
        assert seq.metadata["goal"] == "A.2"
        assert seq.metadata["slot"] == 1

    def test_create_file_select_sequence_slot_2(self):
        """create_file_select_sequence for slot 2."""
        seq = create_file_select_sequence(2)
        assert seq.name == "file_select_slot_2"
        assert seq.metadata["slot"] == 2
        # Should have at least one DOWN input
        has_down = any(
            "DOWN" in str(f.buttons.to_strings())
            for f in seq.frames
        )
        assert has_down

    def test_create_file_select_sequence_slot_3(self):
        """create_file_select_sequence for slot 3."""
        seq = create_file_select_sequence(3)
        assert seq.metadata["slot"] == 3
        # Should have two DOWN inputs
        down_count = sum(
            1 for f in seq.frames
            if "DOWN" in f.buttons.to_strings()
        )
        assert down_count == 2

    def test_create_file_select_sequence_has_A_button(self):
        """File select sequence should press A."""
        seq = create_file_select_sequence(1)
        has_a = any(
            "A" in f.buttons.to_strings()
            for f in seq.frames
        )
        assert has_a

    def test_create_new_game_sequence_slot_1(self):
        """create_new_game_sequence for slot 1."""
        seq = create_new_game_sequence(1)
        assert seq.name == "new_game_slot_1"
        assert seq.metadata["goal"] == "A.3"
        assert seq.metadata["type"] == "new_game"

    def test_create_new_game_sequence_has_start(self):
        """New game sequence should press START for name confirmation."""
        seq = create_new_game_sequence(1)
        has_start = any(
            "START" in f.buttons.to_strings()
            for f in seq.frames
        )
        assert has_start

    def test_create_new_game_sequence_has_A(self):
        """New game sequence should press A to select slot."""
        seq = create_new_game_sequence(1)
        has_a = any(
            "A" in f.buttons.to_strings()
            for f in seq.frames
        )
        assert has_a


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge."""
        bridge = Mock()
        bridge.read_memory = Mock(side_effect=Exception("Connection lost"))
        bridge.press_button = Mock()
        bridge.run_frames = Mock()
        return bridge

    def test_read_memory_exception_handled(self, mock_bridge):
        """Memory read exceptions are handled gracefully."""
        navigator = FileSelectNavigator(mock_bridge)
        # Should not raise, returns 0 on error
        snap = navigator.capture_state()
        assert snap.game_mode == 0

    def test_press_button_exception_handled(self):
        """Button press exceptions are handled."""
        bridge = Mock()
        bridge.read_memory = Mock(return_value=[0x02])
        bridge.press_button = Mock(side_effect=Exception("Socket error"))
        bridge.run_frames = Mock()

        navigator = FileSelectNavigator(bridge)
        # Should not raise
        navigator._press_button("A", frames=5)

    def test_run_frames_fallback(self):
        """Falls back to time.sleep when run_frames unavailable."""
        bridge = Mock()
        bridge.read_memory = Mock(return_value=[0x02])
        del bridge.run_frames  # Remove run_frames attribute

        navigator = FileSelectNavigator(bridge)
        with patch('time.sleep') as mock_sleep:
            navigator._wait_frames(6)
            mock_sleep.assert_called_once_with(6 / 60.0)


class TestIntegration:
    """Integration tests combining multiple components."""

    @pytest.fixture
    def mock_bridge(self):
        """Create comprehensive mock bridge."""
        bridge = Mock()
        bridge.press_button = Mock()
        bridge.run_frames = Mock()

        # Simulate full file select flow
        bridge.read_memory.side_effect = [
            # Initial capture
            [0x02], [0x00], [0x00],
            # Move cursor check
            [0x02], [0x00], [0x00],
            # After move
            [0x02], [0x00], [0x00],
            # Wait for load - mode change
            [0x05], [0x00], [0x00],
            # End snapshot
            [0x05], [0x00], [0x00],
        ]
        return bridge

    def test_full_file_select_flow(self, mock_bridge):
        """Test complete file selection flow."""
        navigator = FileSelectNavigator(mock_bridge, timeout_frames=10)
        result = navigator.select_file(1)

        assert result.success is True
        assert result.slot == 1
        assert "A" in result.inputs_used
        assert result.start_snapshot is not None
        assert result.start_snapshot.is_on_file_select is True

    def test_flow_with_slot_change(self, mock_bridge):
        """Test file selection with cursor movement."""
        # Set up for moving from slot 1 to slot 2
        mock_bridge.read_memory.side_effect = [
            [0x02], [0x00], [0x00],  # Start at slot 1
            [0x02], [0x00], [0x00],  # Check position
            [0x02], [0x01], [0x00],  # After DOWN, at slot 2
            [0x05], [0x00], [0x00],  # Mode changed
        ]

        navigator = FileSelectNavigator(mock_bridge, timeout_frames=10)
        result = navigator.select_file(2)

        assert result.success is True
        assert result.slot == 2


class TestSerialization:
    """Test JSON serialization of all components."""

    def test_snapshot_round_trip(self):
        """Snapshot serializes and deserializes correctly."""
        snap = FileSelectSnapshot(
            timestamp="2026-01-24T12:00:00",
            game_mode=0x02,
            cursor_position=1,
            sub_state=0x00,
            slot_states=[FileSlotStatus.HAS_DATA, FileSlotStatus.EMPTY, FileSlotStatus.UNKNOWN],
            frame_count=42,
        )
        json_str = json.dumps(snap.to_dict())
        loaded = json.loads(json_str)

        assert loaded["game_mode"] == 0x02
        assert loaded["cursor_position"] == 1
        assert loaded["current_slot"] == 2
        assert loaded["frame_count"] == 42

    def test_attempt_round_trip(self):
        """NavigationAttempt serializes correctly."""
        snap = FileSelectSnapshot(
            timestamp="now", game_mode=0x02, cursor_position=0, sub_state=0
        )
        attempt = NavigationAttempt(
            success=True,
            slot=1,
            result=SelectionResult.SUCCESS,
            start_snapshot=snap,
            inputs_used=["MOVE_TO_SLOT_1", "A"],
            duration_frames=100,
        )

        json_str = json.dumps(attempt.to_dict())
        loaded = json.loads(json_str)

        assert loaded["success"] is True
        assert loaded["result"] == "SUCCESS"
        assert len(loaded["inputs_used"]) == 2
