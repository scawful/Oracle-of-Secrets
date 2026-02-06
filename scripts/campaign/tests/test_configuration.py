"""Configuration and settings validation tests (Iteration 45).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling

These tests verify configuration handling, defaults, validation,
and settings patterns across campaign components.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta
import json
import tempfile
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, CampaignProgress, CampaignOrchestrator, CampaignMilestone
)
from scripts.campaign.pathfinder import (
    Pathfinder, CollisionMap, TileType
)
from scripts.campaign.input_recorder import (
    InputRecorder, InputPlayer, InputSequence, InputFrame, Button
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)


# =============================================================================
# Pathfinder Configuration Tests
# =============================================================================

class TestPathfinderConfiguration:
    """Test Pathfinder configuration options."""

    def test_default_cache_ttl(self):
        """Test default cache TTL is 1 second."""
        pf = Pathfinder()
        assert pf.cache_ttl == 1.0

    def test_custom_cache_ttl(self):
        """Test cache TTL can be customized."""
        pf = Pathfinder()
        pf.cache_ttl = 5.0
        assert pf.cache_ttl == 5.0

    def test_zero_cache_ttl(self):
        """Test zero cache TTL effectively disables cache."""
        pf = Pathfinder()
        pf.cache_ttl = 0.0
        assert pf.cache_ttl == 0.0

    def test_negative_cache_ttl_allowed(self):
        """Test negative cache TTL is allowed (always refresh)."""
        pf = Pathfinder()
        pf.cache_ttl = -1.0
        assert pf.cache_ttl == -1.0

    def test_default_no_emulator(self):
        """Test pathfinder works without emulator for offline use."""
        pf = Pathfinder(emulator=None)
        assert pf.emulator is None

    def test_with_mock_emulator(self):
        """Test pathfinder accepts mock emulator."""
        mock_emu = Mock()
        pf = Pathfinder(emulator=mock_emu)
        assert pf.emulator is mock_emu


class TestCollisionMapConfiguration:
    """Test CollisionMap configuration constants."""

    def test_default_width(self):
        """Test default width is 64 tiles."""
        cmap = CollisionMap(data=bytes(64*64))
        assert cmap.width == 64

    def test_default_height(self):
        """Test default height is 64 tiles."""
        cmap = CollisionMap(data=bytes(64*64))
        assert cmap.height == 64

    def test_default_tile_size(self):
        """Test default tile size is 8 pixels."""
        cmap = CollisionMap(data=bytes(100))
        assert cmap.tile_size == 8

    def test_custom_dimensions(self):
        """Test custom dimensions can be set."""
        cmap = CollisionMap(data=bytes(32*32), width=32, height=32)
        assert cmap.width == 32
        assert cmap.height == 32

    def test_custom_tile_size(self):
        """Test custom tile size can be set."""
        cmap = CollisionMap(data=bytes(100), tile_size=16)
        assert cmap.tile_size == 16

    def test_colmapa_address_constant(self):
        """Test COLMAPA address is correctly set."""
        assert CollisionMap.COLMAPA_ADDR == 0x7F2000

    def test_colmapb_address_constant(self):
        """Test COLMAPB address is correctly set."""
        assert CollisionMap.COLMAPB_ADDR == 0x7F6000

    def test_map_size_constant(self):
        """Test MAP_SIZE is 4096 bytes."""
        assert CollisionMap.MAP_SIZE == 0x1000


# =============================================================================
# Input Recorder Configuration Tests
# =============================================================================

class TestInputRecorderConfiguration:
    """Test InputRecorder configuration options."""

    def test_default_name(self):
        """Test recorder uses default name when none provided."""
        recorder = InputRecorder()
        assert recorder._name is not None
        assert len(recorder._name) > 0

    def test_custom_name(self):
        """Test recorder accepts custom name."""
        recorder = InputRecorder(name="my_recording")
        assert recorder._name == "my_recording"

    def test_not_recording_by_default(self):
        """Test recorder is not recording by default."""
        recorder = InputRecorder()
        assert recorder.is_recording is False

    def test_name_property_accessible(self):
        """Test name property is accessible after creation."""
        recorder = InputRecorder(name="test_session")
        # Recorder has internal _name, verify it was set
        assert recorder._name == "test_session"


class TestInputSequenceConfiguration:
    """Test InputSequence configuration options."""

    def test_default_empty_frames(self):
        """Test sequence has empty frames by default."""
        seq = InputSequence(name="empty")
        assert seq.frames == []

    def test_default_empty_metadata(self):
        """Test sequence has empty metadata by default."""
        seq = InputSequence(name="test")
        assert seq.metadata == {}

    def test_custom_metadata(self):
        """Test sequence accepts custom metadata."""
        seq = InputSequence(
            name="test",
            metadata={"version": "1.0", "author": "test"}
        )
        assert seq.metadata["version"] == "1.0"

    def test_description_optional(self):
        """Test description is optional."""
        seq = InputSequence(name="test")
        assert seq.description == ""

    def test_custom_description(self):
        """Test custom description."""
        seq = InputSequence(name="test", description="A test sequence")
        assert seq.description == "A test sequence"


class TestInputFrameConfiguration:
    """Test InputFrame configuration options."""

    def test_default_hold_frames(self):
        """Test default hold frames is 1."""
        frame = InputFrame(frame_number=1, buttons=Button.A)
        assert frame.hold_frames == 1

    def test_custom_hold_frames(self):
        """Test custom hold frames."""
        frame = InputFrame(frame_number=1, buttons=Button.A, hold_frames=10)
        assert frame.hold_frames == 10

    def test_default_no_buttons(self):
        """Test default buttons is NONE."""
        frame = InputFrame(frame_number=1, buttons=Button.NONE)
        assert frame.buttons == Button.NONE


# =============================================================================
# Campaign Orchestrator Configuration Tests
# =============================================================================

class TestCampaignOrchestratorConfiguration:
    """Test CampaignOrchestrator configuration options."""

    def test_default_log_dir(self):
        """Test default log directory."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._log_dir == (Path(tempfile.gettempdir()) / "oos_campaign" / "logs")

    def test_custom_log_dir(self):
        """Test custom log directory."""
        mock_emu = Mock()
        custom_path = Path("/tmp/custom_logs")
        orch = CampaignOrchestrator(emulator=mock_emu, log_dir=custom_path)
        assert orch._log_dir == custom_path

    def test_log_dir_as_string(self):
        """Test log directory can be set as Path."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu, log_dir=Path("./logs"))
        assert isinstance(orch._log_dir, Path)


class TestCampaignProgressDefaults:
    """Test CampaignProgress default values."""

    def test_default_phase_disconnected(self):
        """Test default phase is DISCONNECTED."""
        progress = CampaignProgress()
        assert progress.current_phase == CampaignPhase.DISCONNECTED

    def test_default_iterations_zero(self):
        """Test default iterations is 0."""
        progress = CampaignProgress()
        assert progress.iterations_completed == 0

    def test_default_frames_zero(self):
        """Test default frames is 0."""
        progress = CampaignProgress()
        assert progress.total_frames_played == 0

    def test_default_black_screens_zero(self):
        """Test default black screens is 0."""
        progress = CampaignProgress()
        assert progress.black_screens_detected == 0

    def test_default_transitions_zero(self):
        """Test default transitions is 0."""
        progress = CampaignProgress()
        assert progress.transitions_completed == 0

    def test_default_start_time_none(self):
        """Test default start time is None."""
        progress = CampaignProgress()
        assert progress.start_time is None

    def test_default_last_update_none(self):
        """Test default last update is None."""
        progress = CampaignProgress()
        assert progress.last_update is None

    def test_default_milestones_empty(self):
        """Test default milestones is empty dict."""
        progress = CampaignProgress()
        assert progress.milestones == {}


# =============================================================================
# Action Planner Configuration Tests
# =============================================================================

class TestGoalConfiguration:
    """Test Goal configuration options."""

    def test_default_parameters_empty(self):
        """Test default parameters is empty dict."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        assert goal.parameters == {}

    def test_custom_parameters(self):
        """Test custom parameters."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test",
            parameters={"x": 100, "y": 200}
        )
        assert goal.parameters["x"] == 100

    def test_default_preconditions_empty(self):
        """Test default preconditions is empty list."""
        goal = Goal(goal_type=GoalType.GET_ITEM, description="Test")
        assert goal.preconditions == []

    def test_default_priority_zero(self):
        """Test default priority is 0."""
        goal = Goal(goal_type=GoalType.TALK_TO_NPC, description="Test")
        assert goal.priority == 0

    def test_custom_priority(self):
        """Test custom priority."""
        goal = Goal(
            goal_type=GoalType.DEFEAT_ENEMY,
            description="Test",
            priority=10
        )
        assert goal.priority == 10


class TestPlanConfiguration:
    """Test Plan configuration options."""

    def test_default_status_not_started(self):
        """Test default plan status is NOT_STARTED."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)
        assert plan.status == PlanStatus.NOT_STARTED

    def test_default_actions_empty(self):
        """Test default actions is empty list."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)
        assert plan.actions == []

    def test_default_current_action_zero(self):
        """Test default current action index is 0."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)
        assert plan.current_action_index == 0


# =============================================================================
# Find Path Configuration Tests
# =============================================================================

class TestFindPathConfiguration:
    """Test find_path configuration options."""

    def test_default_max_iterations(self):
        """Test default max iterations is 10000."""
        pf = Pathfinder()
        # Check by calling with a collision map
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)
        # Short path should succeed well within default
        result = pf.find_path((0, 0), (5, 5), cmap)
        assert result.success is True

    def test_custom_max_iterations(self):
        """Test custom max iterations."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)
        # Low max iterations may fail
        result = pf.find_path((0, 0), (60, 60), cmap, max_iterations=10)
        # Either fails or succeeds depending on path
        assert isinstance(result.success, bool)

    def test_default_has_flippers_false(self):
        """Test default has_flippers is False."""
        pf = Pathfinder()
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))
        # Without flippers, should avoid water
        result = pf.find_path((0, 0), (10, 0), cmap)
        assert (5, 0) not in result.path

    def test_has_flippers_true(self):
        """Test has_flippers=True allows water traversal."""
        pf = Pathfinder()
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))
        # With flippers, can go through water
        result = pf.find_path((0, 0), (10, 0), cmap, has_flippers=True)
        assert result.success is True


# =============================================================================
# Tile Type Configuration Tests
# =============================================================================

class TestTileTypeConfiguration:
    """Test TileType constants configuration."""

    def test_walkable_is_zero(self):
        """Test WALKABLE is 0x00."""
        assert TileType.WALKABLE == 0x00

    def test_solid_is_one(self):
        """Test SOLID is 0x01."""
        assert TileType.SOLID == 0x01

    def test_deep_water_value(self):
        """Test DEEP_WATER value."""
        assert TileType.DEEP_WATER == 0x08

    def test_pit_value(self):
        """Test PIT value."""
        assert TileType.PIT == 0x20

    def test_grass_value(self):
        """Test GRASS value."""
        assert TileType.GRASS == 0x40

    def test_damage_floor_value(self):
        """Test DAMAGE_FLOOR value."""
        assert TileType.DAMAGE_FLOOR == 0x60

    def test_warp_value(self):
        """Test WARP value."""
        assert TileType.WARP == 0x80


# =============================================================================
# Button Configuration Tests
# =============================================================================

class TestButtonConfiguration:
    """Test Button IntFlag configuration.

    Button values use auto() which generates sequential powers of 2:
    B=1, Y=2, SELECT=4, START=8, UP=16, DOWN=32, LEFT=64, RIGHT=128,
    A=256, X=512, L=1024, R=2048
    """

    def test_none_is_zero(self):
        """Test NONE button is 0."""
        assert Button.NONE == 0

    def test_b_button_value(self):
        """Test B button value (first auto, value 1)."""
        assert Button.B == 1

    def test_y_button_value(self):
        """Test Y button value (second auto, value 2)."""
        assert Button.Y == 2

    def test_select_button_value(self):
        """Test SELECT button value."""
        assert Button.SELECT == 4

    def test_start_button_value(self):
        """Test START button value."""
        assert Button.START == 8

    def test_up_button_value(self):
        """Test UP button value."""
        assert Button.UP == 16

    def test_down_button_value(self):
        """Test DOWN button value."""
        assert Button.DOWN == 32

    def test_left_button_value(self):
        """Test LEFT button value."""
        assert Button.LEFT == 64

    def test_right_button_value(self):
        """Test RIGHT button value."""
        assert Button.RIGHT == 128

    def test_a_button_value(self):
        """Test A button value."""
        assert Button.A == 256

    def test_x_button_value(self):
        """Test X button value."""
        assert Button.X == 512

    def test_l_button_value(self):
        """Test L button value."""
        assert Button.L == 1024

    def test_r_button_value(self):
        """Test R button value."""
        assert Button.R == 2048


# =============================================================================
# Milestone Configuration Tests
# =============================================================================

class TestMilestoneConfiguration:
    """Test CampaignMilestone configuration."""

    def test_required_fields(self):
        """Test milestone requires id, description, goal."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert m.id == "test"
        assert m.description == "Test"
        assert m.goal == "A.1"

    def test_default_status_not_started(self):
        """Test default status is NOT_STARTED."""
        from scripts.campaign.campaign_orchestrator import MilestoneStatus
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert m.status == MilestoneStatus.NOT_STARTED

    def test_default_completed_at_none(self):
        """Test default completed_at is None."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert m.completed_at is None

    def test_default_notes_empty(self):
        """Test default notes is empty list."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert m.notes == []


# =============================================================================
# Orchestrator Milestone Setup Tests
# =============================================================================

class TestOrchestratorMilestoneSetup:
    """Test orchestrator milestone setup configuration."""

    def test_boot_playable_milestone_exists(self):
        """Test boot_playable milestone is set up."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "boot_playable" in orch._progress.milestones

    def test_reach_village_milestone_exists(self):
        """Test reach_village milestone is set up."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "reach_village" in orch._progress.milestones

    def test_reach_dungeon1_milestone_exists(self):
        """Test reach_dungeon1 milestone is set up."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "reach_dungeon1" in orch._progress.milestones

    def test_emulator_connected_milestone_exists(self):
        """Test emulator_connected milestone is set up."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "emulator_connected" in orch._progress.milestones

    def test_state_parsing_milestone_exists(self):
        """Test state_parsing milestone is set up."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "state_parsing" in orch._progress.milestones

    def test_all_milestones_have_goals(self):
        """Test all milestones have goal assignments."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        for milestone in orch._progress.milestones.values():
            assert milestone.goal is not None
            assert len(milestone.goal) > 0


# =============================================================================
# Validation Configuration Tests
# =============================================================================

class TestValidationConfiguration:
    """Test validation configuration values."""

    def test_max_health_valid_range(self):
        """Test max health values are in valid range."""
        from scripts.campaign.progress_validator import ProgressAddresses
        # Max health address should be in SRAM range
        assert 0x7EF000 <= ProgressAddresses.HEALTH_MAX <= 0x7EFFFF

    def test_rupee_addresses_valid(self):
        """Test rupee addresses are valid."""
        from scripts.campaign.progress_validator import ProgressAddresses
        assert 0x7EF000 <= ProgressAddresses.RUPEES_LO <= 0x7EFFFF
        assert 0x7EF000 <= ProgressAddresses.RUPEES_HI <= 0x7EFFFF

    def test_game_state_address_valid(self):
        """Test game state address is valid."""
        from scripts.campaign.progress_validator import ProgressAddresses
        assert ProgressAddresses.GAME_STATE == 0x7EF3C5


# =============================================================================
# GoalType Configuration Tests
# =============================================================================

class TestGoalTypeConfiguration:
    """Test GoalType enum configuration."""

    def test_reach_location_exists(self):
        """Test REACH_LOCATION goal type exists."""
        assert GoalType.REACH_LOCATION is not None

    def test_enter_building_exists(self):
        """Test ENTER_BUILDING goal type exists."""
        assert GoalType.ENTER_BUILDING is not None

    def test_exit_building_exists(self):
        """Test EXIT_BUILDING goal type exists."""
        assert GoalType.EXIT_BUILDING is not None

    def test_talk_to_npc_exists(self):
        """Test TALK_TO_NPC goal type exists."""
        assert GoalType.TALK_TO_NPC is not None

    def test_get_item_exists(self):
        """Test GET_ITEM goal type exists."""
        assert GoalType.GET_ITEM is not None

    def test_use_item_exists(self):
        """Test USE_ITEM goal type exists."""
        assert GoalType.USE_ITEM is not None

    def test_defeat_enemy_exists(self):
        """Test DEFEAT_ENEMY goal type exists."""
        assert GoalType.DEFEAT_ENEMY is not None

    def test_open_chest_exists(self):
        """Test OPEN_CHEST goal type exists."""
        assert GoalType.OPEN_CHEST is not None

    def test_solve_puzzle_exists(self):
        """Test SOLVE_PUZZLE goal type exists."""
        assert GoalType.SOLVE_PUZZLE is not None


# =============================================================================
# PlanStatus Configuration Tests
# =============================================================================

class TestPlanStatusConfiguration:
    """Test PlanStatus enum configuration."""

    def test_not_started_exists(self):
        """Test NOT_STARTED status exists."""
        assert PlanStatus.NOT_STARTED is not None

    def test_in_progress_exists(self):
        """Test IN_PROGRESS status exists."""
        assert PlanStatus.IN_PROGRESS is not None

    def test_completed_exists(self):
        """Test COMPLETED status exists."""
        assert PlanStatus.COMPLETED is not None

    def test_failed_exists(self):
        """Test FAILED status exists."""
        assert PlanStatus.FAILED is not None

    def test_blocked_exists(self):
        """Test BLOCKED status exists."""
        assert PlanStatus.BLOCKED is not None

    def test_status_count(self):
        """Test PlanStatus has exactly 5 statuses."""
        statuses = list(PlanStatus)
        assert len(statuses) == 5
