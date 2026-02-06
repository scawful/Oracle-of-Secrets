"""Tests for transition_tester module (Iteration 64).

These tests validate the transition testing infrastructure without
requiring a live emulator connection.
"""

import pytest
from datetime import datetime
from unittest.mock import Mock, MagicMock, patch

from scripts.campaign.transition_tester import (
    TransitionType,
    TransitionState,
    TransitionResult,
    TransitionTester,
)


# =============================================================================
# TransitionType Tests
# =============================================================================

class TestTransitionType:
    """Tests for TransitionType enum."""

    def test_has_overworld_to_cave(self):
        """TransitionType should have OVERWORLD_TO_CAVE."""
        assert TransitionType.OVERWORLD_TO_CAVE is not None

    def test_has_cave_to_overworld(self):
        """TransitionType should have CAVE_TO_OVERWORLD."""
        assert TransitionType.CAVE_TO_OVERWORLD is not None

    def test_has_overworld_to_dungeon(self):
        """TransitionType should have OVERWORLD_TO_DUNGEON."""
        assert TransitionType.OVERWORLD_TO_DUNGEON is not None

    def test_has_dungeon_to_overworld(self):
        """TransitionType should have DUNGEON_TO_OVERWORLD."""
        assert TransitionType.DUNGEON_TO_OVERWORLD is not None

    def test_has_intra_dungeon(self):
        """TransitionType should have INTRA_DUNGEON."""
        assert TransitionType.INTRA_DUNGEON is not None

    def test_has_overworld_screen(self):
        """TransitionType should have OVERWORLD_SCREEN."""
        assert TransitionType.OVERWORLD_SCREEN is not None

    def test_all_types_are_unique(self):
        """All transition types should have unique values."""
        values = [t.value for t in TransitionType]
        assert len(values) == len(set(values))


# =============================================================================
# TransitionState Tests
# =============================================================================

class TestTransitionState:
    """Tests for TransitionState dataclass."""

    def test_creation(self):
        """TransitionState can be created with required fields."""
        state = TransitionState(
            timestamp="2026-01-24T12:00:00",
            game_mode=0x09,
            submodule=0x00,
            inidisp=0x0F,
            link_x=100,
            link_y=200
        )
        assert state.game_mode == 0x09
        assert state.link_x == 100

    def test_is_black_screen_true(self):
        """Detects black screen condition correctly."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x00,
            inidisp=0x80,
            link_x=0, link_y=0
        )
        assert state.is_black_screen is True

    def test_is_black_screen_false_wrong_mode(self):
        """Not black screen when mode is not 0x07."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x09,  # Overworld
            submodule=0x00,
            inidisp=0x80,
            link_x=0, link_y=0
        )
        assert state.is_black_screen is False

    def test_is_black_screen_false_screen_on(self):
        """Not black screen when INIDISP has screen on."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x00,
            inidisp=0x0F,  # Screen on
            link_x=0, link_y=0
        )
        assert state.is_black_screen is False

    def test_is_black_screen_false_submodule_active(self):
        """Not black screen when submodule is non-zero."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x05,  # Active submodule
            inidisp=0x80,
            link_x=0, link_y=0
        )
        assert state.is_black_screen is False

    def test_is_transitioning_true(self):
        """Detects transition mode correctly."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x06,  # Transition mode
            submodule=0x00,
            inidisp=0x80,
            link_x=0, link_y=0
        )
        assert state.is_transitioning is True

    def test_is_transitioning_false(self):
        """Not transitioning when mode is not 0x06."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x00,
            inidisp=0x0F,
            link_x=0, link_y=0
        )
        assert state.is_transitioning is False

    def test_is_indoors_true(self):
        """Detects indoors mode correctly."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x00,
            inidisp=0x0F,
            link_x=0, link_y=0
        )
        assert state.is_indoors is True

    def test_is_indoors_false(self):
        """Not indoors when on overworld."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x09,
            submodule=0x00,
            inidisp=0x0F,
            link_x=0, link_y=0
        )
        assert state.is_indoors is False

    def test_is_overworld_true(self):
        """Detects overworld mode correctly."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x09,
            submodule=0x00,
            inidisp=0x0F,
            link_x=0, link_y=0
        )
        assert state.is_overworld is True

    def test_is_overworld_false(self):
        """Not overworld when indoors."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x07,
            submodule=0x00,
            inidisp=0x0F,
            link_x=0, link_y=0
        )
        assert state.is_overworld is False


# =============================================================================
# TransitionResult Tests
# =============================================================================

class TestTransitionResult:
    """Tests for TransitionResult dataclass."""

    def test_creation_success(self):
        """TransitionResult can represent successful transition."""
        start = TransitionState(
            timestamp="2026-01-24", game_mode=0x09,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        end = TransitionState(
            timestamp="2026-01-24", game_mode=0x07,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        result = TransitionResult(
            transition_type=TransitionType.OVERWORLD_TO_CAVE,
            success=True,
            start_state=start,
            end_state=end,
        )
        assert result.success is True
        assert result.black_screen_detected is False

    def test_creation_failure(self):
        """TransitionResult can represent failed transition."""
        start = TransitionState(
            timestamp="2026-01-24", game_mode=0x09,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        end = TransitionState(
            timestamp="2026-01-24", game_mode=0x07,
            submodule=0x00, inidisp=0x80, link_x=100, link_y=100
        )
        result = TransitionResult(
            transition_type=TransitionType.OVERWORLD_TO_CAVE,
            success=False,
            start_state=start,
            end_state=end,
            black_screen_detected=True,
            black_screen_frame=45
        )
        assert result.success is False
        assert result.black_screen_detected is True
        assert result.black_screen_frame == 45

    def test_to_dict_has_required_keys(self):
        """to_dict returns expected keys."""
        start = TransitionState(
            timestamp="2026-01-24", game_mode=0x09,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        end = TransitionState(
            timestamp="2026-01-24", game_mode=0x07,
            submodule=0x00, inidisp=0x0F, link_x=120, link_y=120
        )
        result = TransitionResult(
            transition_type=TransitionType.OVERWORLD_TO_CAVE,
            success=True,
            start_state=start,
            end_state=end,
        )
        d = result.to_dict()
        assert "transition_type" in d
        assert "success" in d
        assert "start_state" in d
        assert "end_state" in d
        assert "black_screen_detected" in d

    def test_to_dict_has_hex_values(self):
        """to_dict formats values as hex strings."""
        start = TransitionState(
            timestamp="2026-01-24", game_mode=0x09,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        end = TransitionState(
            timestamp="2026-01-24", game_mode=0x07,
            submodule=0x00, inidisp=0x0F, link_x=120, link_y=120
        )
        result = TransitionResult(
            transition_type=TransitionType.OVERWORLD_TO_CAVE,
            success=True,
            start_state=start,
            end_state=end,
        )
        d = result.to_dict()
        assert d["start_state"]["game_mode"].startswith("0x")
        assert d["end_state"]["game_mode"].startswith("0x")


# =============================================================================
# TransitionTester Tests
# =============================================================================

class TestTransitionTester:
    """Tests for TransitionTester class."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock Mesen2 bridge."""
        bridge = Mock()
        bridge.read_memory.return_value = 0x09  # Default to overworld mode
        bridge.read_memory16.return_value = 100  # Default position
        bridge.run_frames.return_value = True
        bridge.press_button.return_value = True
        bridge.load_state.return_value = True
        return bridge

    def test_creation(self, mock_bridge):
        """TransitionTester can be created with bridge."""
        tester = TransitionTester(mock_bridge)
        assert tester.bridge is mock_bridge
        assert len(tester.results) == 0

    def test_capture_state(self, mock_bridge):
        """capture_state reads from correct memory addresses."""
        tester = TransitionTester(mock_bridge)
        state = tester.capture_state()

        # Verify memory reads were made
        assert mock_bridge.read_memory.called
        assert mock_bridge.read_memory16.called

    def test_capture_state_returns_transition_state(self, mock_bridge):
        """capture_state returns TransitionState object."""
        tester = TransitionTester(mock_bridge)
        state = tester.capture_state()
        assert isinstance(state, TransitionState)

    def test_wait_for_stable_returns_states(self, mock_bridge):
        """wait_for_stable_state returns captured states."""
        # Make bridge return stable overworld mode
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        success, states = tester.wait_for_stable_state(timeout_frames=60)

        assert isinstance(states, list)
        assert len(states) > 0

    def test_test_transition_success(self, mock_bridge):
        """test_transition returns success for stable state."""
        # Simulate stable overworld
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        result = tester.test_transition(
            TransitionType.OVERWORLD_SCREEN,
            direction="UP",
            hold_frames=30
        )

        assert isinstance(result, TransitionResult)
        assert result.transition_type == TransitionType.OVERWORLD_SCREEN

    def test_test_transition_presses_button(self, mock_bridge):
        """test_transition calls press_button with direction."""
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        tester.test_transition(
            TransitionType.OVERWORLD_SCREEN,
            direction="RIGHT",
            hold_frames=45
        )

        mock_bridge.press_button.assert_called_with("RIGHT", 45)

    def test_test_transition_with_state_load(self, mock_bridge):
        """test_transition loads state when path provided."""
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        tester.test_transition(
            TransitionType.OVERWORLD_TO_CAVE,
            direction="UP",
            setup_state_path="/path/to/state.mss"
        )

        mock_bridge.load_state.assert_called_with(path="/path/to/state.mss")

    def test_results_accumulate(self, mock_bridge):
        """Results are stored after each test."""
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        tester.test_transition(TransitionType.OVERWORLD_SCREEN, "UP")
        tester.test_transition(TransitionType.OVERWORLD_SCREEN, "DOWN")

        assert len(tester.results) == 2

    def test_test_overworld_to_cave(self, mock_bridge):
        """test_overworld_to_cave uses correct transition type."""
        mock_bridge.read_memory.return_value = 0x09
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        result = tester.test_overworld_to_cave()

        assert result.transition_type == TransitionType.OVERWORLD_TO_CAVE

    def test_test_cave_to_overworld(self, mock_bridge):
        """test_cave_to_overworld uses correct transition type."""
        mock_bridge.read_memory.return_value = 0x07  # Indoor mode
        mock_bridge.read_memory16.return_value = 100

        tester = TransitionTester(mock_bridge)
        result = tester.test_cave_to_overworld()

        assert result.transition_type == TransitionType.CAVE_TO_OVERWORLD


# =============================================================================
# Black Screen Detection Tests
# =============================================================================

class TestBlackScreenDetection:
    """Tests specifically for black screen detection logic."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock bridge for black screen tests."""
        bridge = Mock()
        bridge.run_frames.return_value = True
        bridge.press_button.return_value = True
        bridge.load_state.return_value = True
        bridge.read_memory16.return_value = 100
        return bridge

    def test_detects_black_screen_during_wait(self, mock_bridge):
        """Black screen condition detected during wait_for_stable_state."""
        call_count = [0]

        def mock_read(addr):
            call_count[0] += 1
            # Simulate: normal -> transition -> black screen
            if addr == TransitionTester.ADDR_GAME_MODE:
                if call_count[0] < 5:
                    return 0x06  # Transitioning
                return 0x07  # Indoor
            if addr == TransitionTester.ADDR_INIDISP:
                if call_count[0] < 5:
                    return 0x80  # Expected during transition
                return 0x80  # Still 0x80 = black screen!
            if addr == TransitionTester.ADDR_SUBMODULE:
                return 0x00
            return 0

        mock_bridge.read_memory.side_effect = mock_read

        tester = TransitionTester(mock_bridge)
        success, states = tester.wait_for_stable_state(timeout_frames=120)

        # Should detect black screen
        assert success is False
        assert any(s.is_black_screen for s in states)

    def test_no_false_positive_during_transition(self, mock_bridge):
        """INIDISP 0x80 during mode 0x06 is NOT a black screen."""
        call_count = [0]

        def mock_read(addr):
            call_count[0] += 1
            if addr == TransitionTester.ADDR_GAME_MODE:
                if call_count[0] < 10:
                    return 0x06  # Transitioning
                return 0x07  # Indoor
            if addr == TransitionTester.ADDR_INIDISP:
                if call_count[0] < 10:
                    return 0x80  # Expected during transition
                return 0x0F  # Screen on after transition
            if addr == TransitionTester.ADDR_SUBMODULE:
                return 0x00
            return 0

        mock_bridge.read_memory.side_effect = mock_read

        tester = TransitionTester(mock_bridge)
        success, states = tester.wait_for_stable_state(timeout_frames=120)

        # Transition phase with INIDISP 0x80 should not trigger black screen
        transition_states = [s for s in states if s.game_mode == 0x06]
        assert all(not s.is_black_screen for s in transition_states)


# =============================================================================
# Address Constants Tests
# =============================================================================

class TestAddressConstants:
    """Tests for memory address constants."""

    def test_game_mode_address(self):
        """ADDR_GAME_MODE is correct."""
        assert TransitionTester.ADDR_GAME_MODE == 0x7E0010

    def test_submodule_address(self):
        """ADDR_SUBMODULE is correct."""
        assert TransitionTester.ADDR_SUBMODULE == 0x7E0011

    def test_inidisp_address(self):
        """ADDR_INIDISP is correct."""
        assert TransitionTester.ADDR_INIDISP == 0x7E001A

    def test_link_x_address(self):
        """ADDR_LINK_X is correct."""
        assert TransitionTester.ADDR_LINK_X == 0x7E0022

    def test_link_y_address(self):
        """ADDR_LINK_Y is correct."""
        assert TransitionTester.ADDR_LINK_Y == 0x7E0020


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_results_list(self):
        """New TransitionTester has empty results."""
        bridge = Mock()
        tester = TransitionTester(bridge)
        assert len(tester.results) == 0

    def test_transition_state_with_defaults(self):
        """TransitionState uses defaults for optional fields."""
        state = TransitionState(
            timestamp="2026-01-24",
            game_mode=0x09,
            submodule=0x00,
            inidisp=0x0F,
            link_x=100,
            link_y=200
        )
        assert state.area_id == 0
        assert state.room_id == 0
        assert state.frame_count == 0

    def test_transition_result_with_defaults(self):
        """TransitionResult uses defaults for optional fields."""
        start = TransitionState(
            timestamp="2026-01-24", game_mode=0x09,
            submodule=0x00, inidisp=0x0F, link_x=100, link_y=100
        )
        result = TransitionResult(
            transition_type=TransitionType.OVERWORLD_SCREEN,
            success=True,
            start_state=start,
            end_state=start,
        )
        assert result.intermediate_states == []
        assert result.black_screen_detected is False
        assert result.black_screen_frame is None
        assert result.error_message is None

    def test_load_state_failure(self):
        """Handles state load failure gracefully."""
        bridge = Mock()
        bridge.load_state.return_value = False

        tester = TransitionTester(bridge)
        result = tester.test_transition(
            TransitionType.OVERWORLD_TO_CAVE,
            direction="UP",
            setup_state_path="/nonexistent/state.mss"
        )

        assert result.success is False
        assert result.error_message is not None
        assert "Failed to load" in result.error_message
