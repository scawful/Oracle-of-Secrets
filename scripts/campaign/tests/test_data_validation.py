"""Iteration 55 - Data Validation Tests.

Tests for data validation, input sanitization, and data integrity
across all campaign modules.

Focus: Input validation, type checking, bounds validation, null handling,
string sanitization, numeric limits, enum validation.
"""

import pytest
import math
import time
from unittest.mock import MagicMock

from scripts.campaign.emulator_abstraction import (
    EmulatorStatus,
    MemoryRead,
    GameStateSnapshot,
)
from scripts.campaign.input_recorder import (
    Button,
    InputFrame,
    InputSequence,
    InputRecorder,
)
from scripts.campaign.progress_validator import (
    StoryFlag,
    GameStateValue,
    ProgressAddresses,
    ProgressSnapshot,
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
)
from scripts.campaign.action_planner import (
    GoalType,
    PlanStatus,
    Goal,
    Action,
    Plan,
)
from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
)
from scripts.campaign.pathfinder import (
    TileType,
    CollisionMap,
    PathNode,
    NavigationResult,
)


# =============================================================================
# EmulatorStatus Validation Tests
# =============================================================================

class TestEmulatorStatusValidation:
    """Validation tests for EmulatorStatus enum."""

    def test_all_statuses_valid_values(self):
        """All statuses have valid integer values."""
        for status in EmulatorStatus:
            assert isinstance(status.value, int)
            assert status.value >= 0

    def test_status_from_value(self):
        """Status can be created from value."""
        for status in EmulatorStatus:
            assert EmulatorStatus(status.value) == status

    def test_invalid_status_value_raises(self):
        """Invalid value raises ValueError."""
        with pytest.raises(ValueError):
            EmulatorStatus(999)


# =============================================================================
# MemoryRead Validation Tests
# =============================================================================

class TestMemoryReadValidation:
    """Validation tests for MemoryRead dataclass."""

    def test_address_zero(self):
        """Address zero is valid."""
        read = MemoryRead(address=0, value=42)
        assert read.address == 0

    def test_address_max_24bit(self):
        """24-bit address is valid (SNES address space)."""
        read = MemoryRead(address=0xFFFFFF, value=0)
        assert read.address == 0xFFFFFF

    def test_value_byte_range(self):
        """Byte values 0-255 are valid."""
        for val in [0, 127, 255]:
            read = MemoryRead(address=0, value=val, size=1)
            assert read.value == val

    def test_value_word_range(self):
        """Word values 0-65535 are valid."""
        for val in [0, 32767, 65535]:
            read = MemoryRead(address=0, value=val, size=2)
            assert read.value == val

    def test_size_default(self):
        """Default size is 1."""
        read = MemoryRead(address=0, value=0)
        assert read.size == 1

    def test_size_values(self):
        """Size 1, 2, 3 are valid."""
        for size in [1, 2, 3]:
            read = MemoryRead(address=0, value=0, size=size)
            assert read.size == size

    def test_value16_property(self):
        """value16 property works."""
        read = MemoryRead(address=0, value=0x1234, size=2)
        assert read.value16 == 0x1234

    def test_value24_property(self):
        """value24 property works."""
        read = MemoryRead(address=0, value=0x123456, size=3)
        assert read.value24 == 0x123456


# =============================================================================
# GameStateSnapshot Validation Tests
# =============================================================================

class TestGameStateSnapshotValidation:
    """Validation tests for GameStateSnapshot."""

    def _snapshot(self, **kwargs):
        """Create snapshot with defaults."""
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
        }
        defaults.update(kwargs)
        return GameStateSnapshot(**defaults)

    def test_mode_byte_range(self):
        """Mode is valid byte range."""
        for mode in [0x00, 0x09, 0xFF]:
            snapshot = self._snapshot(mode=mode)
            assert snapshot.mode == mode

    def test_coordinates_valid(self):
        """Coordinates are valid."""
        snapshot = self._snapshot(link_x=0, link_y=0)
        assert snapshot.link_x == 0

        snapshot = self._snapshot(link_x=512, link_y=512)
        assert snapshot.link_x == 512

    def test_health_range(self):
        """Health values are valid."""
        snapshot = self._snapshot(health=0, max_health=24)
        assert snapshot.health == 0

        snapshot = self._snapshot(health=24, max_health=24)
        assert snapshot.health == 24

    def test_health_exceeds_max(self):
        """Health can exceed max (game quirk)."""
        snapshot = self._snapshot(health=30, max_health=24)
        assert snapshot.health == 30

    def test_max_health_zero(self):
        """Max health zero is handled."""
        snapshot = self._snapshot(health=0, max_health=0)
        assert snapshot.max_health == 0


# =============================================================================
# Button Validation Tests
# =============================================================================

class TestButtonValidation:
    """Validation tests for Button IntFlag."""

    def test_button_values_power_of_two(self):
        """Button values are powers of 2."""
        for button in Button:
            if button != Button.NONE:
                assert button.value > 0
                assert (button.value & (button.value - 1)) == 0  # Power of 2

    def test_button_none_is_zero(self):
        """NONE button is 0."""
        assert Button.NONE == 0

    def test_button_combination_valid(self):
        """Button combinations are valid."""
        combo = Button.A | Button.B
        assert combo & Button.A
        assert combo & Button.B
        assert not (combo & Button.X)

    def test_all_buttons_combined(self):
        """All buttons can be combined."""
        all_buttons = Button.NONE
        for button in Button:
            all_buttons |= button
        assert all_buttons != 0

    def test_button_from_string_invalid(self):
        """Invalid button string returns NONE."""
        result = Button.from_string("INVALID")
        assert result == Button.NONE


# =============================================================================
# InputFrame Validation Tests
# =============================================================================

class TestInputFrameValidation:
    """Validation tests for InputFrame dataclass."""

    def test_frame_number_zero(self):
        """Frame number zero is valid."""
        frame = InputFrame(frame_number=0, buttons=Button.A)
        assert frame.frame_number == 0

    def test_frame_number_large(self):
        """Large frame numbers are valid."""
        frame = InputFrame(frame_number=999999, buttons=Button.A)
        assert frame.frame_number == 999999

    def test_hold_frames_default(self):
        """Default hold frames is 1."""
        frame = InputFrame(frame_number=0, buttons=Button.A)
        assert frame.hold_frames == 1

    def test_hold_frames_custom(self):
        """Custom hold frames are valid."""
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=100)
        assert frame.hold_frames == 100

    def test_to_dict_valid_format(self):
        """to_dict produces valid format."""
        frame = InputFrame(frame_number=5, buttons=Button.A | Button.B, hold_frames=10)
        d = frame.to_dict()

        assert 'frame' in d
        assert 'buttons' in d
        assert 'hold' in d
        assert isinstance(d['buttons'], list)

    def test_from_dict_round_trip(self):
        """from_dict round trip preserves data."""
        original = InputFrame(frame_number=5, buttons=Button.A | Button.B, hold_frames=10)
        d = original.to_dict()
        restored = InputFrame.from_dict(d)

        assert restored.frame_number == original.frame_number
        assert restored.buttons == original.buttons
        assert restored.hold_frames == original.hold_frames


# =============================================================================
# InputSequence Validation Tests
# =============================================================================

class TestInputSequenceValidation:
    """Validation tests for InputSequence dataclass."""

    def test_empty_sequence_valid(self):
        """Empty sequence is valid."""
        seq = InputSequence(name="empty")
        assert len(seq.frames) == 0
        assert seq.total_frames == 0

    def test_name_empty_string(self):
        """Empty name string is valid."""
        seq = InputSequence(name="")
        assert seq.name == ""

    def test_name_special_chars(self):
        """Special characters in name are valid."""
        seq = InputSequence(name="test_123-abc.def")
        assert seq.name == "test_123-abc.def"

    def test_name_unicode(self):
        """Unicode in name is valid."""
        seq = InputSequence(name="テスト")
        assert seq.name == "テスト"

    def test_metadata_empty_dict(self):
        """Empty metadata dict is valid."""
        seq = InputSequence(name="test", metadata={})
        assert seq.metadata == {}

    def test_metadata_nested(self):
        """Nested metadata is valid."""
        seq = InputSequence(name="test", metadata={"nested": {"key": "value"}})
        assert seq.metadata["nested"]["key"] == "value"


# =============================================================================
# StoryFlag Validation Tests
# =============================================================================

class TestStoryFlagValidation:
    """Validation tests for StoryFlag IntFlag."""

    def test_intro_complete_value(self):
        """INTRO_COMPLETE has expected value."""
        assert StoryFlag.INTRO_COMPLETE == 0x01

    def test_story_flag_combinations(self):
        """Story flag combinations work."""
        combo = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        assert combo & StoryFlag.INTRO_COMPLETE
        assert combo & StoryFlag.LOOM_BEACH

    def test_story_flag_bitwise_and(self):
        """Bitwise AND works for flag checking."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.KYDROG_COMPLETE
        assert flags & StoryFlag.INTRO_COMPLETE
        assert not (flags & StoryFlag.FARORE_RESCUED)


# =============================================================================
# GameStateValue Validation Tests
# =============================================================================

class TestGameStateValueValidation:
    """Validation tests for GameStateValue IntEnum."""

    def test_start_is_zero(self):
        """START is 0."""
        assert GameStateValue.START == 0

    def test_values_sequential(self):
        """Values are sequential for ordering."""
        values = [v.value for v in GameStateValue]
        sorted_values = sorted(values)
        assert values == sorted_values

    def test_comparison_ordering(self):
        """Values can be compared for progression."""
        assert GameStateValue.START < GameStateValue.LOOM_BEACH
        assert GameStateValue.LOOM_BEACH < GameStateValue.KYDROG_DONE


# =============================================================================
# ProgressAddresses Validation Tests
# =============================================================================

class TestProgressAddressesValidation:
    """Validation tests for ProgressAddresses."""

    def test_game_state_address(self):
        """GAME_STATE address is valid WRAM."""
        assert 0x7E0000 <= ProgressAddresses.GAME_STATE <= 0x7FFFFF

    def test_oosprog_address(self):
        """OOSPROG address is valid SRAM."""
        assert 0x7E0000 <= ProgressAddresses.OOSPROG <= 0x7FFFFF

    def test_health_addresses(self):
        """Health addresses are valid."""
        assert 0x7E0000 <= ProgressAddresses.HEALTH_MAX <= 0x7FFFFF
        assert 0x7E0000 <= ProgressAddresses.HEALTH_CURRENT <= 0x7FFFFF


# =============================================================================
# CampaignPhase Validation Tests
# =============================================================================

class TestCampaignPhaseValidation:
    """Validation tests for CampaignPhase enum."""

    def test_all_phases_distinct(self):
        """All phases have distinct values."""
        values = [p.value for p in CampaignPhase]
        assert len(values) == len(set(values))

    def test_phase_from_name(self):
        """Phases can be accessed by name."""
        assert CampaignPhase["DISCONNECTED"] == CampaignPhase.DISCONNECTED
        assert CampaignPhase["EXPLORING"] == CampaignPhase.EXPLORING


# =============================================================================
# MilestoneStatus Validation Tests
# =============================================================================

class TestMilestoneStatusValidation:
    """Validation tests for MilestoneStatus enum."""

    def test_all_statuses_distinct(self):
        """All statuses are distinct."""
        values = [s.value for s in MilestoneStatus]
        assert len(values) == len(set(values))

    def test_not_started_exists(self):
        """NOT_STARTED status exists."""
        assert hasattr(MilestoneStatus, 'NOT_STARTED')


# =============================================================================
# CampaignMilestone Validation Tests
# =============================================================================

class TestCampaignMilestoneValidation:
    """Validation tests for CampaignMilestone dataclass."""

    def test_basic_creation(self):
        """Basic milestone creation works."""
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert ms.id == "test"
        assert ms.description == "Test"
        assert ms.goal == "A.1"

    def test_id_empty_string(self):
        """Empty ID string is valid but not recommended."""
        ms = CampaignMilestone(id="", description="Test", goal="A.1")
        assert ms.id == ""

    def test_description_empty(self):
        """Empty description is valid."""
        ms = CampaignMilestone(id="test", description="", goal="A.1")
        assert ms.description == ""

    def test_notes_empty_list(self):
        """Empty notes list is default."""
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert ms.notes == []

    def test_notes_with_entries(self):
        """Notes with entries are valid."""
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        ms.notes.append("Note 1")
        ms.notes.append("Note 2")
        assert len(ms.notes) == 2

    def test_complete_sets_status(self):
        """complete() sets status to COMPLETED."""
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        ms.complete()
        assert ms.status == MilestoneStatus.COMPLETED

    def test_complete_with_note(self):
        """complete() with note adds to notes."""
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        ms.complete("Completed successfully")
        assert "Completed successfully" in ms.notes


# =============================================================================
# CampaignProgress Validation Tests
# =============================================================================

class TestCampaignProgressValidation:
    """Validation tests for CampaignProgress dataclass."""

    def test_milestones_empty_default(self):
        """Milestones dict is empty by default."""
        progress = CampaignProgress()
        assert len(progress.milestones) == 0

    def test_iterations_completed_default(self):
        """iterations_completed defaults to 0."""
        progress = CampaignProgress()
        assert progress.iterations_completed == 0

    def test_counter_increment(self):
        """Counters can be incremented."""
        progress = CampaignProgress()
        progress.iterations_completed += 1
        assert progress.iterations_completed == 1

    def test_frame_counter_large_value(self):
        """Frame counter supports large values."""
        progress = CampaignProgress()
        progress.total_frames_played = 2**32 - 1
        assert progress.total_frames_played == 2**32 - 1

    def test_add_milestone(self):
        """add_milestone works."""
        progress = CampaignProgress()
        ms = CampaignMilestone(id="test", description="Test", goal="A.1")
        progress.add_milestone(ms)
        assert "test" in progress.milestones


# =============================================================================
# GoalType Validation Tests
# =============================================================================

class TestGoalTypeValidation:
    """Validation tests for GoalType enum."""

    def test_all_types_distinct(self):
        """All goal types are distinct."""
        values = [g.value for g in GoalType]
        assert len(values) == len(set(values))

    def test_goal_type_from_name(self):
        """Goal types can be accessed by name."""
        assert GoalType["REACH_LOCATION"] == GoalType.REACH_LOCATION
        assert GoalType["DEFEAT_ENEMY"] == GoalType.DEFEAT_ENEMY


# =============================================================================
# PlanStatus Validation Tests
# =============================================================================

class TestPlanStatusValidation:
    """Validation tests for PlanStatus enum."""

    def test_all_statuses_distinct(self):
        """All plan statuses are distinct."""
        values = [s.value for s in PlanStatus]
        assert len(values) == len(set(values))

    def test_not_started_exists(self):
        """NOT_STARTED status exists."""
        assert hasattr(PlanStatus, 'NOT_STARTED')


# =============================================================================
# Action Validation Tests
# =============================================================================

class TestActionValidation:
    """Validation tests for Action dataclass."""

    def test_name_empty(self):
        """Empty name is valid."""
        action = Action(name="", description="Test")
        assert action.name == ""

    def test_description_required(self):
        """Description is required."""
        action = Action(name="test", description="Required description")
        assert action.description == "Required description"

    def test_condition_none(self):
        """None condition is valid default."""
        action = Action(name="test", description="Test", condition=None)
        assert action.condition is None

    def test_condition_callable(self):
        """Callable condition is stored."""
        cond = lambda state: True
        action = Action(name="test", description="Test", condition=cond)
        assert action.condition is cond

    def test_input_sequence_optional(self):
        """input_sequence is optional."""
        action = Action(name="test", description="Test")
        assert action.input_sequence is None

    def test_timeout_frames_default(self):
        """Default timeout frames is 600."""
        action = Action(name="test", description="Test")
        assert action.timeout_frames == 600


# =============================================================================
# Goal Validation Tests
# =============================================================================

class TestGoalValidation:
    """Validation tests for Goal dataclass."""

    def test_reach_location_requires_coords(self):
        """reach_location requires coordinates."""
        goal = Goal.reach_location(area_id=0x29, x=100, y=200)
        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters['x'] == 100
        assert goal.parameters['y'] == 200

    def test_enter_building_type(self):
        """enter_building creates correct type."""
        goal = Goal.enter_building(entrance_id=0x10)
        assert goal.goal_type == GoalType.ENTER_BUILDING

    def test_defeat_enemy_type(self):
        """defeat_enemy creates correct type."""
        goal = Goal.defeat_enemy(sprite_id=0x50)
        assert goal.goal_type == GoalType.DEFEAT_ENEMY

    def test_defeat_enemy_no_sprite(self):
        """defeat_enemy works without sprite_id."""
        goal = Goal.defeat_enemy()
        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters['sprite_id'] is None


# =============================================================================
# Plan Validation Tests
# =============================================================================

class TestPlanValidation:
    """Validation tests for Plan dataclass."""

    def test_empty_actions_list(self):
        """Empty actions list is valid."""
        goal = Goal.reach_location(area_id=0x29, x=0, y=0)
        plan = Plan(goal=goal, actions=[])
        assert len(plan.actions) == 0

    def test_status_not_started_initial(self):
        """Initial status is NOT_STARTED."""
        goal = Goal.reach_location(area_id=0x29, x=0, y=0)
        plan = Plan(goal=goal, actions=[])
        assert plan.status == PlanStatus.NOT_STARTED

    def test_execution_log_empty(self):
        """Execution log starts empty."""
        goal = Goal.reach_location(area_id=0x29, x=0, y=0)
        plan = Plan(goal=goal, actions=[])
        assert plan.execution_log == []


# =============================================================================
# GamePhase Validation Tests
# =============================================================================

class TestGamePhaseValidation:
    """Validation tests for GamePhase enum."""

    def test_all_phases_distinct(self):
        """All phases are distinct."""
        values = [p.value for p in GamePhase]
        assert len(values) == len(set(values))

    def test_unknown_is_zero(self):
        """UNKNOWN is 0."""
        assert GamePhase.UNKNOWN == 0


# =============================================================================
# LinkAction Validation Tests
# =============================================================================

class TestLinkActionValidation:
    """Validation tests for LinkAction enum."""

    def test_all_actions_distinct(self):
        """All actions are distinct."""
        values = [a.value for a in LinkAction]
        assert len(values) == len(set(values))

    def test_standing_is_zero(self):
        """STANDING is 0."""
        assert LinkAction.STANDING == 0

    def test_unknown_is_255(self):
        """UNKNOWN is 255."""
        assert LinkAction.UNKNOWN == 255


# =============================================================================
# TileType Validation Tests
# =============================================================================

class TestTileTypeValidation:
    """Validation tests for TileType enum."""

    def test_all_tiles_distinct(self):
        """All tile types are distinct."""
        values = [t.value for t in TileType]
        assert len(values) == len(set(values))

    def test_walkable_is_zero(self):
        """WALKABLE is 0."""
        assert TileType.WALKABLE == 0


# =============================================================================
# CollisionMap Validation Tests
# =============================================================================

class TestCollisionMapValidation:
    """Validation tests for CollisionMap."""

    def test_empty_data(self):
        """Empty data is handled."""
        cmap = CollisionMap(data=b'', width=0, height=0)
        assert cmap.get_tile(0, 0) == TileType.SOLID

    def test_mismatched_dimensions(self):
        """Data smaller than dimensions returns SOLID."""
        cmap = CollisionMap(data=bytes([0x00] * 4), width=8, height=8)
        # Index 10 is beyond data length
        assert cmap.get_tile(2, 1) == TileType.SOLID


# =============================================================================
# PathNode Validation Tests
# =============================================================================

class TestPathNodeValidation:
    """Validation tests for PathNode."""

    def test_negative_coordinates(self):
        """Negative coordinates are valid."""
        node = PathNode(x=-5, y=-10)
        assert node.x == -5
        assert node.y == -10

    def test_zero_costs(self):
        """Zero costs are valid."""
        node = PathNode(x=0, y=0, g_cost=0.0, h_cost=0.0)
        assert node.f_cost == 0.0

    def test_large_costs(self):
        """Large costs are valid."""
        node = PathNode(x=0, y=0, g_cost=1e10, h_cost=1e10)
        assert node.f_cost == 2e10

    def test_infinity_costs(self):
        """Infinity costs are handled."""
        node = PathNode(x=0, y=0, g_cost=float('inf'), h_cost=0.0)
        assert math.isinf(node.f_cost)


# =============================================================================
# NavigationResult Validation Tests
# =============================================================================

class TestNavigationResultValidation:
    """Validation tests for NavigationResult."""

    def test_empty_path_failed(self):
        """Empty path with failure is valid."""
        result = NavigationResult(success=False, path=[], reason="No path")
        assert result.success is False
        assert len(result.path) == 0

    def test_single_point_path(self):
        """Single point path is valid."""
        result = NavigationResult(success=True, path=[(0, 0)], distance=0)
        assert len(result.path) == 1

    def test_reason_empty_string(self):
        """Empty reason string is valid."""
        result = NavigationResult(success=False, path=[], reason="")
        assert result.reason == ""

    def test_blocked_at_none(self):
        """blocked_at None is valid."""
        result = NavigationResult(success=False, path=[], reason="Test")
        assert result.blocked_at is None


# =============================================================================
# Cross-Module Type Consistency Tests
# =============================================================================

class TestCrossModuleTypeConsistency:
    """Tests for type consistency across modules."""

    def test_button_as_int(self):
        """Button can be used as int."""
        val: int = Button.A.value
        assert val > 0

    def test_status_as_int(self):
        """Status enums can be used as int."""
        val: int = EmulatorStatus.CONNECTED.value
        assert isinstance(val, int)

    def test_phase_as_int(self):
        """Phase enums can be used as int."""
        val: int = GamePhase.OVERWORLD.value
        assert isinstance(val, int)

    def test_milestone_status_as_int(self):
        """MilestoneStatus can be used as int."""
        val: int = MilestoneStatus.IN_PROGRESS.value
        assert isinstance(val, int)


# =============================================================================
# Boundary Value Tests
# =============================================================================

class TestBoundaryValues:
    """Tests for boundary values."""

    def test_coordinates_zero(self):
        """Zero coordinates are valid."""
        node = PathNode(x=0, y=0)
        assert node.x == 0

    def test_coordinates_large(self):
        """Large coordinates are valid."""
        node = PathNode(x=999999, y=999999)
        assert node.x == 999999

    def test_hold_frames_max_int(self):
        """Large hold frames are valid."""
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=2**31 - 1)
        assert frame.hold_frames == 2**31 - 1

    def test_address_boundary(self):
        """Address at SNES boundary is valid."""
        read = MemoryRead(address=0x7FFFFF, value=0)
        assert read.address == 0x7FFFFF

    def test_value_max_byte(self):
        """Max byte value is valid."""
        read = MemoryRead(address=0, value=0xFF)
        assert read.value == 0xFF
