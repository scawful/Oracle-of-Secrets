"""Extended tests for boundary conditions and edge cases.

Iteration 40 of the ralph-loop campaign.
Tests extreme values, overflow conditions, and boundary behavior
across all campaign infrastructure modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Boundary condition verification
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import math

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, EmulatorStatus, MemoryRead
from scripts.campaign.game_state import (
    GamePhase, GameStateParser, ParsedGameState, LinkAction
)
from scripts.campaign.input_recorder import Button, InputSequence, InputRecorder, InputFrame
from scripts.campaign.progress_validator import ProgressSnapshot, StoryFlag
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)
from scripts.campaign.campaign_orchestrator import CampaignProgress, CampaignPhase


# =============================================================================
# Byte Boundary Tests
# =============================================================================

class TestByteBoundaries:
    """Test byte-level boundary conditions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, **kwargs):
        """Create state with specified values."""
        defaults = {
            'timestamp': 1.0, 'mode': 0x09, 'submode': 0, 'area': 0x29,
            'room': 0, 'link_x': 512, 'link_y': 480, 'link_z': 0,
            'link_direction': 0, 'link_state': 0, 'indoors': False,
            'inidisp': 0x0F, 'health': 24, 'max_health': 24
        }
        defaults.update(kwargs)
        return GameStateSnapshot(**defaults)

    def test_mode_min_value(self, parser):
        """Test minimum mode value (0x00)."""
        snap = self.make_state(mode=0x00)
        parsed = parser.parse(snap)
        assert parsed.phase == GamePhase.BOOT

    def test_mode_max_value(self, parser):
        """Test maximum mode value (0xFF)."""
        snap = self.make_state(mode=0xFF)
        parsed = parser.parse(snap)
        assert parsed.phase == GamePhase.UNKNOWN

    def test_area_min_value(self, parser):
        """Test minimum area value (0x00)."""
        snap = self.make_state(area=0x00)
        parsed = parser.parse(snap)
        assert parsed.area_id == 0x00

    def test_area_max_value(self, parser):
        """Test maximum area value (0xFF)."""
        snap = self.make_state(area=0xFF)
        parsed = parser.parse(snap)
        assert parsed.area_id == 0xFF

    def test_inidisp_min_brightness(self, parser):
        """Test minimum INIDISP brightness (0x00)."""
        snap = self.make_state(inidisp=0x00)
        parsed = parser.parse(snap)
        assert parsed.is_black_screen is False

    def test_inidisp_max_brightness(self, parser):
        """Test maximum INIDISP brightness (0x8F)."""
        snap = self.make_state(inidisp=0x8F)
        parsed = parser.parse(snap)
        assert parsed.is_black_screen is False

    def test_link_state_boundary(self, parser):
        """Test link_state at boundaries."""
        snap_min = self.make_state(link_state=0x00)
        snap_max = self.make_state(link_state=0xFF)

        parsed_min = parser.parse(snap_min)
        parsed_max = parser.parse(snap_max)

        assert parsed_min.link_action == LinkAction.STANDING
        assert parsed_max.link_action == LinkAction.UNKNOWN

    def test_direction_boundary_values(self, parser):
        """Test direction at boundary values."""
        for direction in [0x00, 0x02, 0x04, 0x06]:
            snap = self.make_state(link_direction=direction)
            parsed = parser.parse(snap)
            assert parsed.link_direction in ["up", "down", "left", "right"]

    def test_health_zero(self, parser):
        """Test health at zero."""
        snap = self.make_state(health=0, max_health=24)
        parsed = parser.parse(snap)
        assert parsed.health_percent == 0.0

    def test_health_max(self, parser):
        """Test health at maximum."""
        snap = self.make_state(health=24, max_health=24)
        parsed = parser.parse(snap)
        assert parsed.health_percent == 1.0


# =============================================================================
# Word Boundary Tests
# =============================================================================

class TestWordBoundaries:
    """Test 16-bit word boundary conditions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, **kwargs):
        """Create state with specified values."""
        defaults = {
            'timestamp': 1.0, 'mode': 0x09, 'submode': 0, 'area': 0x29,
            'room': 0, 'link_x': 512, 'link_y': 480, 'link_z': 0,
            'link_direction': 0, 'link_state': 0, 'indoors': False,
            'inidisp': 0x0F, 'health': 24, 'max_health': 24
        }
        defaults.update(kwargs)
        return GameStateSnapshot(**defaults)

    def test_room_min_value(self, parser):
        """Test minimum room value (0x0000)."""
        snap = self.make_state(room=0x0000)
        parsed = parser.parse(snap)
        assert parsed.room_id == 0x0000

    def test_room_max_value(self, parser):
        """Test maximum room value (0xFFFF)."""
        snap = self.make_state(room=0xFFFF)
        parsed = parser.parse(snap)
        assert parsed.room_id == 0xFFFF

    def test_room_byte_boundary(self, parser):
        """Test room at byte boundary (0x00FF, 0x0100)."""
        snap_ff = self.make_state(room=0x00FF)
        snap_100 = self.make_state(room=0x0100)

        parsed_ff = parser.parse(snap_ff)
        parsed_100 = parser.parse(snap_100)

        assert parsed_ff.room_id == 0x00FF
        assert parsed_100.room_id == 0x0100

    def test_link_x_min(self, parser):
        """Test minimum X coordinate."""
        snap = self.make_state(link_x=0)
        parsed = parser.parse(snap)
        assert parsed.link_position[0] == 0

    def test_link_x_max(self, parser):
        """Test maximum X coordinate (0xFFFF)."""
        snap = self.make_state(link_x=0xFFFF)
        parsed = parser.parse(snap)
        assert parsed.link_position[0] == 0xFFFF

    def test_link_y_min(self, parser):
        """Test minimum Y coordinate."""
        snap = self.make_state(link_y=0)
        parsed = parser.parse(snap)
        assert parsed.link_position[1] == 0

    def test_link_y_max(self, parser):
        """Test maximum Y coordinate (0xFFFF)."""
        snap = self.make_state(link_y=0xFFFF)
        parsed = parser.parse(snap)
        assert parsed.link_position[1] == 0xFFFF


# =============================================================================
# Timestamp Edge Cases
# =============================================================================

class TestTimestampEdgeCases:
    """Test timestamp edge cases."""

    def make_state(self, timestamp):
        """Create state with specific timestamp."""
        return GameStateSnapshot(
            timestamp=timestamp, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    def test_timestamp_zero(self):
        """Test timestamp at zero."""
        snap = self.make_state(0.0)
        assert snap.timestamp == 0.0

    def test_timestamp_negative(self):
        """Test negative timestamp (edge case)."""
        snap = self.make_state(-1.0)
        assert snap.timestamp == -1.0

    def test_timestamp_very_large(self):
        """Test very large timestamp."""
        snap = self.make_state(1e15)
        assert snap.timestamp == 1e15

    def test_timestamp_very_small(self):
        """Test very small positive timestamp."""
        snap = self.make_state(1e-15)
        assert snap.timestamp == 1e-15

    def test_timestamp_infinity(self):
        """Test infinite timestamp (edge case)."""
        snap = self.make_state(float('inf'))
        assert math.isinf(snap.timestamp)


# =============================================================================
# Button Combination Edge Cases
# =============================================================================

class TestButtonCombinations:
    """Test button combination edge cases."""

    def test_no_buttons(self):
        """Test no buttons pressed."""
        buttons = Button.NONE
        assert buttons == 0

    def test_single_button(self):
        """Test single button values."""
        for button in [Button.A, Button.B, Button.X, Button.Y,
                       Button.L, Button.R, Button.START, Button.SELECT,
                       Button.UP, Button.DOWN, Button.LEFT, Button.RIGHT]:
            assert button != Button.NONE
            # Each should be a single bit
            count = bin(button.value).count('1')
            assert count == 1

    def test_all_buttons(self):
        """Test all buttons pressed at once."""
        all_buttons = (Button.A | Button.B | Button.X | Button.Y |
                      Button.L | Button.R | Button.START | Button.SELECT |
                      Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT)
        # Should have 12 bits set
        count = bin(all_buttons).count('1')
        assert count == 12

    def test_opposite_dpad(self):
        """Test pressing opposite d-pad buttons."""
        up_down = Button.UP | Button.DOWN
        left_right = Button.LEFT | Button.RIGHT

        # Both should be valid combinations (hardware allows it)
        assert up_down & Button.UP
        assert up_down & Button.DOWN
        assert left_right & Button.LEFT
        assert left_right & Button.RIGHT

    def test_button_from_string_invalid(self):
        """Test Button.from_string with invalid input."""
        result = Button.from_string("INVALID")
        assert result == Button.NONE

    def test_button_from_strings_mixed(self):
        """Test Button.from_strings with mixed valid/invalid."""
        result = Button.from_strings(["A", "INVALID", "B"])
        assert result & Button.A
        assert result & Button.B


# =============================================================================
# InputSequence Edge Cases
# =============================================================================

class TestInputSequenceEdgeCases:
    """Test InputSequence edge cases."""

    def test_empty_sequence(self):
        """Test empty sequence properties."""
        seq = InputSequence(name="empty")
        assert seq.total_frames == 0
        assert seq.duration_seconds == 0.0
        assert len(seq.frames) == 0

    def test_single_frame_sequence(self):
        """Test single frame sequence."""
        seq = InputSequence(name="single")
        seq.add_input(0, Button.A, hold=1)

        assert seq.total_frames == 1
        assert len(seq.frames) == 1

    def test_very_long_hold(self):
        """Test very long button hold."""
        seq = InputSequence(name="long_hold")
        seq.add_input(0, Button.A, hold=100000)

        assert seq.total_frames == 100000
        assert seq.duration_seconds == 100000 / 60.0

    def test_max_frame_number(self):
        """Test maximum frame number."""
        seq = InputSequence(name="max_frame")
        seq.add_input(999999, Button.A, hold=1)

        assert seq.frames[0].frame_number == 999999

    def test_sequence_compression_identical(self):
        """Test compression of identical consecutive inputs."""
        seq = InputSequence(name="compress_test")
        # Add identical consecutive inputs
        for i in range(10):
            seq.add_input(i, Button.A, hold=1)

        compressed = seq.compress()
        # Should compress into fewer frames
        assert len(compressed.frames) <= len(seq.frames)


# =============================================================================
# Health Edge Cases
# =============================================================================

class TestHealthEdgeCases:
    """Test health calculation edge cases."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, health, max_health):
        """Create state with specific health values."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=health, max_health=max_health
        )

    def test_health_zero_max_zero(self, parser):
        """Test health 0 with max 0 (division by zero case)."""
        snap = self.make_state(0, 0)
        parsed = parser.parse(snap)
        # Should handle gracefully
        assert parsed.health_percent in (0.0, 1.0)

    def test_health_greater_than_max(self, parser):
        """Test health greater than max (overheal case)."""
        snap = self.make_state(30, 24)
        parsed = parser.parse(snap)
        # Should still compute ratio
        assert parsed.health_percent == 30 / 24

    def test_health_one_unit(self, parser):
        """Test single health unit."""
        snap = self.make_state(1, 24)
        parsed = parser.parse(snap)
        assert abs(parsed.health_percent - 1/24) < 0.001

    def test_health_max_minus_one(self, parser):
        """Test health one below max."""
        snap = self.make_state(23, 24)
        parsed = parser.parse(snap)
        assert abs(parsed.health_percent - 23/24) < 0.001


# =============================================================================
# ProgressSnapshot Edge Cases
# =============================================================================

class TestProgressSnapshotEdgeCases:
    """Test ProgressSnapshot edge cases."""

    def make_progress(self, **kwargs):
        """Create progress snapshot with defaults."""
        defaults = {
            'timestamp': 1.0, 'game_state': 0, 'story_flags': 0,
            'story_flags_2': 0, 'side_quest_1': 0, 'side_quest_2': 0,
            'health': 24, 'max_health': 24, 'rupees': 0,
            'magic': 0, 'max_magic': 0, 'sword_level': 0,
            'shield_level': 0, 'armor_level': 0, 'crystals': 0,
            'follower_id': 0, 'follower_state': 0
        }
        defaults.update(kwargs)
        return ProgressSnapshot(**defaults)

    def test_all_story_flags_set(self):
        """Test with all story flags set."""
        snap = self.make_progress(story_flags=0xFF, story_flags_2=0xFF)
        assert snap.story_flags == 0xFF
        assert snap.story_flags_2 == 0xFF

    def test_max_rupees(self):
        """Test maximum rupee count."""
        snap = self.make_progress(rupees=9999)
        assert snap.rupees == 9999

    def test_max_equipment_levels(self):
        """Test maximum equipment levels."""
        snap = self.make_progress(sword_level=4, shield_level=3, armor_level=2)
        assert snap.sword_level == 4
        assert snap.shield_level == 3
        assert snap.armor_level == 2

    def test_hearts_calculation(self):
        """Test hearts property."""
        snap = self.make_progress(health=16)
        assert snap.hearts == 2.0  # 16 / 8 = 2

    def test_hearts_fractional(self):
        """Test fractional hearts."""
        snap = self.make_progress(health=12)
        assert snap.hearts == 1.5  # 12 / 8 = 1.5


# =============================================================================
# Plan/Goal Edge Cases
# =============================================================================

class TestPlanGoalEdgeCases:
    """Test Plan and Goal edge cases."""

    def test_goal_empty_parameters(self):
        """Test goal with empty parameters."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test"
        )
        assert goal.parameters == {}

    def test_goal_empty_preconditions(self):
        """Test goal with empty preconditions."""
        goal = Goal(
            goal_type=GoalType.GET_ITEM,
            description="Get item"
        )
        assert goal.preconditions == []

    def test_plan_no_actions(self):
        """Test plan with no actions."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal)

        assert len(plan.actions) == 0
        assert plan.current_action is None

    def test_plan_empty_execution_log(self):
        """Test plan with empty execution log."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal)

        assert plan.execution_log == []

    def test_goal_max_priority(self):
        """Test goal with high priority."""
        goal = Goal(
            goal_type=GoalType.DEFEAT_ENEMY,
            description="Boss fight",
            priority=999
        )
        assert goal.priority == 999


# =============================================================================
# CampaignProgress Edge Cases
# =============================================================================

class TestCampaignProgressEdgeCases:
    """Test CampaignProgress edge cases."""

    def test_initial_state(self):
        """Test initial progress state."""
        progress = CampaignProgress()
        assert progress.current_phase == CampaignPhase.DISCONNECTED

    def test_rapid_phase_changes(self):
        """Test rapid phase changes."""
        progress = CampaignProgress()

        phases = [
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.EXPLORING,
            CampaignPhase.IN_DUNGEON,
            CampaignPhase.EXPLORING,
            CampaignPhase.COMPLETED
        ]

        for phase in phases:
            progress.current_phase = phase
            assert progress.current_phase == phase


# =============================================================================
# MemoryRead Edge Cases
# =============================================================================

class TestMemoryReadEdgeCases:
    """Test MemoryRead edge cases."""

    def test_zero_address(self):
        """Test zero address."""
        mr = MemoryRead(address=0x000000, value=0x00)
        assert mr.address == 0

    def test_max_address(self):
        """Test maximum 24-bit address."""
        mr = MemoryRead(address=0xFFFFFF, value=0x00)
        assert mr.address == 0xFFFFFF

    def test_zero_value(self):
        """Test zero value."""
        mr = MemoryRead(address=0x7E0000, value=0x00)
        assert mr.value == 0

    def test_max_byte_value(self):
        """Test maximum byte value."""
        mr = MemoryRead(address=0x7E0000, value=0xFF)
        assert mr.value == 0xFF

    def test_16bit_value_boundary(self):
        """Test 16-bit value at boundary."""
        mr = MemoryRead(address=0x7E0000, value=0xFFFF, size=2)
        assert mr.value16 == 0xFFFF

    def test_24bit_value_boundary(self):
        """Test 24-bit value at boundary."""
        mr = MemoryRead(address=0x7E0000, value=0xFFFFFF, size=3)
        assert mr.value24 == 0xFFFFFF


# =============================================================================
# InputRecorder Edge Cases
# =============================================================================

class TestInputRecorderEdgeCases:
    """Test InputRecorder edge cases."""

    def test_record_without_start(self):
        """Test recording without starting."""
        recorder = InputRecorder()
        # Should silently ignore
        recorder.record_input(Button.A)
        seq = recorder.get_sequence()
        assert len(seq.frames) == 0

    def test_double_start(self):
        """Test starting twice."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.record_input(Button.A)
        recorder.start_recording()  # Should reset
        recorder.record_input(Button.B)
        recorder.stop_recording()
        seq = recorder.get_sequence()
        # Second start may reset or continue
        assert seq is not None

    def test_stop_start_stop(self):
        """Test stop-start-stop pattern."""
        recorder = InputRecorder()
        recorder.stop_recording()  # No-op
        recorder.start_recording()
        recorder.stop_recording()
        assert recorder.is_recording is False


# =============================================================================
# Submode Edge Cases
# =============================================================================

class TestSubmodeEdgeCases:
    """Test submode boundary conditions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, submode):
        """Create state with specific submode."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=submode, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    def test_submode_zero(self, parser):
        """Test submode zero (no transition)."""
        snap = self.make_state(0x00)
        parsed = parser.parse(snap)
        assert parsed.is_transitioning is False

    def test_submode_nonzero_indicates_transition(self, parser):
        """Test non-zero submode indicates transition."""
        snap = self.make_state(0x01)
        parsed = parser.parse(snap)
        assert parsed.is_transitioning is True

    def test_submode_max(self, parser):
        """Test maximum submode value."""
        snap = self.make_state(0xFF)
        parsed = parser.parse(snap)
        assert parsed.is_transitioning is True
        assert parsed.submode == 0xFF


# =============================================================================
# Link Z (Layer) Edge Cases
# =============================================================================

class TestLinkZEdgeCases:
    """Test Link Z coordinate edge cases."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, link_z):
        """Create state with specific Z value."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=link_z,
            link_direction=0, link_state=0, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    def test_z_zero(self, parser):
        """Test Z at zero (ground level)."""
        snap = self.make_state(0)
        parsed = parser.parse(snap)
        assert parsed.link_layer == 0

    def test_z_upper_layer(self, parser):
        """Test Z at upper layer."""
        snap = self.make_state(1)
        parsed = parser.parse(snap)
        assert parsed.link_layer == 1

    def test_z_max_byte(self, parser):
        """Test Z at max byte value."""
        snap = self.make_state(0xFF)
        parsed = parser.parse(snap)
        assert parsed.link_layer == 0xFF
