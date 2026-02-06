"""Iteration 57 - Mock Behavior Tests.

Tests for mocking patterns and mock object behaviors used across the test suite.

Focus: Mock object configuration, side effects, call tracking,
return value sequences, patch patterns, mock assertions.
"""

import pytest
import time
from unittest.mock import MagicMock, Mock, patch, call, PropertyMock
from typing import List, Optional

from scripts.campaign.emulator_abstraction import (
    EmulatorStatus,
    MemoryRead,
    GameStateSnapshot,
    EmulatorInterface,
)
from scripts.campaign.input_recorder import (
    Button,
    InputFrame,
    InputSequence,
)
from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
    GameStateParser,
)
from scripts.campaign.pathfinder import (
    TileType,
    CollisionMap,
    Pathfinder,
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
)


# =============================================================================
# Basic Mock Configuration Tests
# =============================================================================

class TestBasicMockConfiguration:
    """Tests for basic mock configuration patterns."""

    def test_mock_return_value(self):
        """Configure mock with return value."""
        mock = MagicMock(return_value=42)
        assert mock() == 42

    def test_mock_method_return(self):
        """Configure mock method return value."""
        mock = MagicMock()
        mock.get_value.return_value = 100
        assert mock.get_value() == 100

    def test_mock_property(self):
        """Configure mock property."""
        mock = MagicMock()
        type(mock).status = PropertyMock(return_value=EmulatorStatus.CONNECTED)
        assert mock.status == EmulatorStatus.CONNECTED

    def test_mock_attribute(self):
        """Configure mock attribute."""
        mock = MagicMock()
        mock.name = "test_name"
        assert mock.name == "test_name"

    def test_mock_nested_attribute(self):
        """Configure nested mock attribute."""
        mock = MagicMock()
        mock.config.setting = "value"
        assert mock.config.setting == "value"


# =============================================================================
# Mock Call Tracking Tests
# =============================================================================

class TestMockCallTracking:
    """Tests for mock call tracking patterns."""

    def test_assert_called(self):
        """Verify mock was called."""
        mock = MagicMock()
        mock()
        mock.assert_called()

    def test_assert_called_once(self):
        """Verify mock was called exactly once."""
        mock = MagicMock()
        mock()
        mock.assert_called_once()

    def test_assert_called_with(self):
        """Verify mock was called with arguments."""
        mock = MagicMock()
        mock(42, key="value")
        mock.assert_called_with(42, key="value")

    def test_call_count(self):
        """Track call count."""
        mock = MagicMock()
        mock()
        mock()
        mock()
        assert mock.call_count == 3

    def test_call_args_list(self):
        """Track all call arguments."""
        mock = MagicMock()
        mock(1)
        mock(2)
        mock(3)
        assert mock.call_args_list == [call(1), call(2), call(3)]

    def test_assert_not_called(self):
        """Verify mock was not called."""
        mock = MagicMock()
        mock.assert_not_called()


# =============================================================================
# Mock Side Effect Tests
# =============================================================================

class TestMockSideEffects:
    """Tests for mock side effect patterns."""

    def test_side_effect_exception(self):
        """Side effect raises exception."""
        mock = MagicMock(side_effect=ValueError("test error"))
        with pytest.raises(ValueError, match="test error"):
            mock()

    def test_side_effect_list(self):
        """Side effect returns sequence of values."""
        mock = MagicMock(side_effect=[1, 2, 3])
        assert mock() == 1
        assert mock() == 2
        assert mock() == 3

    def test_side_effect_function(self):
        """Side effect calls function."""
        def double(x):
            return x * 2
        mock = MagicMock(side_effect=double)
        assert mock(5) == 10

    def test_side_effect_iterator(self):
        """Side effect uses iterator."""
        mock = MagicMock(side_effect=iter([10, 20, 30]))
        results = [mock(), mock(), mock()]
        assert results == [10, 20, 30]


# =============================================================================
# Mock Emulator Tests
# =============================================================================

class TestMockEmulator:
    """Tests for mocking emulator interface."""

    def test_mock_emulator_status(self):
        """Mock emulator status property."""
        mock_emu = MagicMock(spec=EmulatorInterface)
        type(mock_emu).status = PropertyMock(return_value=EmulatorStatus.CONNECTED)
        assert mock_emu.status == EmulatorStatus.CONNECTED

    def test_mock_memory_read(self):
        """Mock emulator memory read."""
        mock_emu = MagicMock()
        mock_emu.read_memory.return_value = MemoryRead(address=0x7E0010, value=0x42)
        result = mock_emu.read_memory(0x7E0010)
        assert result.value == 0x42

    def test_mock_memory_read_sequence(self):
        """Mock sequence of memory reads."""
        mock_emu = MagicMock()
        mock_emu.read_memory.side_effect = [
            MemoryRead(address=0x10, value=0x09),  # Mode
            MemoryRead(address=0x11, value=0x29),  # Area
            MemoryRead(address=0x12, value=0x00),  # Room
        ]

        assert mock_emu.read_memory(0x10).value == 0x09
        assert mock_emu.read_memory(0x11).value == 0x29
        assert mock_emu.read_memory(0x12).value == 0x00

    def test_mock_emulator_connect_disconnect(self):
        """Mock emulator connect/disconnect."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = True
        mock_emu.disconnect.return_value = None

        assert mock_emu.connect() is True
        mock_emu.disconnect()
        mock_emu.disconnect.assert_called_once()


# =============================================================================
# Mock Game State Tests
# =============================================================================

class TestMockGameState:
    """Tests for mocking game state."""

    def _mock_snapshot(self, **kwargs) -> MagicMock:
        """Create mock snapshot with defaults."""
        defaults = {
            'mode': 0x09,
            'submode': 0x00,
            'area': 0x29,
            'room': 0x00,
            'link_x': 128,
            'link_y': 128,
            'link_z': 0,
            'link_direction': 0x00,
            'link_state': 0x00,
            'indoors': False,
            'inidisp': 0x0F,
            'health': 24,
            'max_health': 24,
            'timestamp': time.time(),
            'raw_data': {},
            'is_black_screen': False,
        }
        defaults.update(kwargs)

        mock = MagicMock()
        for key, value in defaults.items():
            setattr(mock, key, value)
        return mock

    def test_mock_snapshot_mode(self):
        """Mock snapshot with specific mode."""
        mock = self._mock_snapshot(mode=0x07)
        assert mock.mode == 0x07

    def test_mock_snapshot_health(self):
        """Mock snapshot with health values."""
        mock = self._mock_snapshot(health=12, max_health=24)
        assert mock.health == 12
        assert mock.max_health == 24

    def test_mock_snapshot_position(self):
        """Mock snapshot with position."""
        mock = self._mock_snapshot(link_x=200, link_y=150)
        assert mock.link_x == 200
        assert mock.link_y == 150

    def test_mock_state_sequence(self):
        """Create sequence of mock states."""
        states = [
            self._mock_snapshot(mode=0x09, link_x=100),
            self._mock_snapshot(mode=0x09, link_x=108),
            self._mock_snapshot(mode=0x09, link_x=116),
        ]

        positions = [(s.link_x, s.link_y) for s in states]
        assert len(positions) == 3
        assert positions[0] == (100, 128)


# =============================================================================
# Mock Pathfinder Tests
# =============================================================================

class TestMockPathfinder:
    """Tests for mocking pathfinder."""

    def test_mock_collision_map(self):
        """Mock collision map data."""
        data = bytes([TileType.WALKABLE] * 64)
        cmap = CollisionMap(data=data, width=8, height=8)
        assert cmap.is_walkable(0, 0) is True

    def test_mock_navigation_result(self):
        """Mock navigation result."""
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.path = [(0, 0), (1, 0), (2, 0)]
        mock_result.distance = 2.0

        assert mock_result.success is True
        assert len(mock_result.path) == 3

    def test_mock_pathfinder_find_path(self):
        """Mock pathfinder find_path method."""
        mock_pf = MagicMock()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.path = [(0, 0), (5, 5)]
        mock_pf.find_path.return_value = mock_result

        result = mock_pf.find_path((0, 0), (5, 5))
        assert result.success is True


# =============================================================================
# Mock Progress Tests
# =============================================================================

class TestMockProgress:
    """Tests for mocking progress tracking."""

    def test_mock_milestone(self):
        """Mock milestone behavior."""
        mock_ms = MagicMock(spec=CampaignMilestone)
        mock_ms.id = "test"
        mock_ms.status = MilestoneStatus.NOT_STARTED

        assert mock_ms.id == "test"
        assert mock_ms.status == MilestoneStatus.NOT_STARTED

    def test_mock_progress(self):
        """Mock campaign progress."""
        mock_progress = MagicMock(spec=CampaignProgress)
        mock_progress.milestones = {}
        mock_progress.iterations_completed = 5
        mock_progress.total_frames_played = 3600

        assert mock_progress.iterations_completed == 5

    def test_mock_phase_transitions(self):
        """Mock phase transition sequence."""
        phases = [
            CampaignPhase.DISCONNECTED,
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
        ]

        mock_progress = MagicMock()
        mock_progress.current_phase = phases[0]

        for phase in phases[1:]:
            mock_progress.current_phase = phase

        assert mock_progress.current_phase == CampaignPhase.EXPLORING


# =============================================================================
# Patch Decorator Tests
# =============================================================================

class TestPatchPatterns:
    """Tests for patch decorator patterns."""

    def test_patch_function(self):
        """Patch a function."""
        with patch('time.time', return_value=1000.0):
            import time
            assert time.time() == 1000.0

    def test_patch_method(self):
        """Patch an object method."""
        parser = GameStateParser()
        with patch.object(parser, '_determine_phase', return_value=GamePhase.OVERWORLD):
            # The patched method returns OVERWORLD
            mock_snapshot = MagicMock()
            mock_snapshot.is_black_screen = False
            mock_snapshot.mode = 0xFF  # Would normally be UNKNOWN
            # Direct call to patched method
            assert parser._determine_phase(mock_snapshot) == GamePhase.OVERWORLD

    def test_patch_as_decorator(self):
        """Use patch as decorator."""
        @patch('time.time')
        def test_func(mock_time):
            mock_time.return_value = 500.0
            import time
            return time.time()

        assert test_func() == 500.0


# =============================================================================
# Mock Input Tests
# =============================================================================

class TestMockInput:
    """Tests for mocking input systems."""

    def test_mock_button_flags(self):
        """Mock button flags."""
        mock_frame = MagicMock(spec=InputFrame)
        mock_frame.buttons = Button.A | Button.B
        mock_frame.hold_frames = 5

        assert mock_frame.buttons & Button.A
        assert mock_frame.hold_frames == 5

    def test_mock_input_sequence(self):
        """Mock input sequence."""
        mock_seq = MagicMock(spec=InputSequence)
        mock_seq.name = "test_sequence"
        mock_seq.frames = []
        mock_seq.total_frames = 0

        assert mock_seq.name == "test_sequence"
        assert len(mock_seq.frames) == 0

    def test_mock_input_callback(self):
        """Mock input callback."""
        callback = MagicMock()
        callback.return_value = None

        # Simulate callback invocations
        for i in range(5):
            callback(frame=i, buttons=Button.A)

        assert callback.call_count == 5


# =============================================================================
# Complex Mock Scenarios
# =============================================================================

class TestComplexMockScenarios:
    """Tests for complex mocking scenarios."""

    def test_mock_emulator_with_state_machine(self):
        """Mock emulator with state machine behavior."""
        mock_emu = MagicMock()
        states = [
            EmulatorStatus.DISCONNECTED,
            EmulatorStatus.CONNECTING,
            EmulatorStatus.CONNECTED,
        ]
        state_iter = iter(states)
        type(mock_emu).status = PropertyMock(side_effect=lambda: next(state_iter))

        assert mock_emu.status == EmulatorStatus.DISCONNECTED
        assert mock_emu.status == EmulatorStatus.CONNECTING
        assert mock_emu.status == EmulatorStatus.CONNECTED

    def test_mock_failing_then_succeeding(self):
        """Mock operation that fails then succeeds."""
        mock_connect = MagicMock()
        mock_connect.side_effect = [
            ConnectionError("Failed"),
            ConnectionError("Failed again"),
            True,  # Success on third try
        ]

        with pytest.raises(ConnectionError):
            mock_connect()
        with pytest.raises(ConnectionError):
            mock_connect()
        assert mock_connect() is True

    def test_mock_with_context_manager(self):
        """Mock context manager."""
        mock_cm = MagicMock()
        mock_cm.__enter__ = MagicMock(return_value="resource")
        mock_cm.__exit__ = MagicMock(return_value=False)

        with mock_cm as resource:
            assert resource == "resource"

        mock_cm.__enter__.assert_called_once()
        mock_cm.__exit__.assert_called_once()


# =============================================================================
# Mock Verification Tests
# =============================================================================

class TestMockVerification:
    """Tests for mock verification patterns."""

    def test_verify_call_order(self):
        """Verify call order with call objects."""
        mock = MagicMock()
        mock.step1()
        mock.step2()
        mock.step3()

        expected_calls = [call.step1(), call.step2(), call.step3()]
        mock.assert_has_calls(expected_calls)

    def test_verify_any_call(self):
        """Verify specific call among many."""
        mock = MagicMock()
        mock(1)
        mock(2)
        mock(3)
        mock(special=True)

        mock.assert_any_call(2)
        mock.assert_any_call(special=True)

    def test_reset_mock(self):
        """Reset mock state."""
        mock = MagicMock()
        mock(1)
        mock(2)
        assert mock.call_count == 2

        mock.reset_mock()
        assert mock.call_count == 0


# =============================================================================
# Spec and Autospec Tests
# =============================================================================

class TestSpecAndAutospec:
    """Tests for spec and autospec patterns."""

    def test_mock_with_spec(self):
        """Mock with spec restricts attributes."""
        mock = MagicMock(spec=['method1', 'attribute1'])
        mock.method1.return_value = "result"
        mock.attribute1 = "value"

        assert mock.method1() == "result"
        assert mock.attribute1 == "value"

    def test_mock_spec_class(self):
        """Mock with class spec."""
        mock = MagicMock(spec=CampaignProgress)
        mock.iterations_completed = 10

        # Methods exist on CampaignProgress spec
        assert hasattr(mock, 'add_milestone')
        assert hasattr(mock, 'complete_milestone')
        # Fields can be set dynamically on the mock
        mock.milestones = {}
        assert mock.milestones == {}

    def test_mock_instance_attribute(self):
        """Mock instance with specific attributes."""
        mock = MagicMock()
        mock.configure_mock(
            name="test",
            value=42,
            nested=MagicMock(inner="value")
        )

        assert mock.name == "test"
        assert mock.value == 42
        assert mock.nested.inner == "value"
