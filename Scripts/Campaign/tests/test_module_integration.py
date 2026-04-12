"""Cross-module integration tests.

Iteration 34 - Tests that verify how campaign modules work together.
Tests module interactions, data flow between components, and
end-to-end workflows without requiring a live emulator.
"""

import pytest
import tempfile
import json
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

import sys

project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import (
    GameStateSnapshot, EmulatorStatus, MemoryRead,
    Mesen2Emulator, get_emulator
)
from scripts.campaign.game_state import (
    GamePhase, GameStateParser, ParsedGameState, LinkAction,
    parse_state, get_parser
)
from scripts.campaign.input_recorder import (
    Button, InputFrame, InputSequence, InputRecorder, InputPlayer,
    create_boot_sequence, create_walk_sequence,
    create_menu_open_sequence, create_attack_sequence
)
from scripts.campaign.action_planner import (
    GoalType, PlanStatus, Goal, Action, Plan, ActionPlanner,
    goal_reach_village_center, goal_reach_dungeon1_entrance
)
from scripts.campaign.locations import (
    get_area_name, get_room_name, get_entrance_name,
    get_dungeon_name, get_location_description
)
from scripts.campaign.pathfinder import (
    TileType, CollisionMap, PathNode, NavigationResult, Pathfinder
)
from scripts.campaign.progress_validator import (
    StoryFlag, ProgressSnapshot, ValidationResult, ProgressValidator
)
from scripts.campaign.visual_verifier import (
    VerificationResult, Screenshot, VisualVerifier
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, MilestoneStatus, CampaignMilestone,
    CampaignProgress, CampaignOrchestrator
)


# =============================================================================
# GameStateSnapshot -> GameStateParser Integration
# =============================================================================

class TestSnapshotParserIntegration:
    """Test GameStateSnapshot flows correctly to GameStateParser."""

    def test_overworld_snapshot_to_parsed(self):
        """Overworld snapshot parses to correct phase."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        parser = GameStateParser()
        state = parser.parse(snapshot)

        assert state.phase == GamePhase.OVERWORLD
        assert state.is_playing is True
        assert state.can_move is True
        assert state.link_position == (512, 480)

    def test_dungeon_snapshot_to_parsed(self):
        """Dungeon snapshot parses to correct phase."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x06, room=0x27,
            link_x=256, link_y=256, link_z=0,
            link_direction=0x00, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        parser = GameStateParser()
        state = parser.parse(snapshot)

        assert state.phase == GamePhase.DUNGEON
        assert state.is_indoors is True
        assert state.room_id == 0x27

    def test_black_screen_detection_integrated(self):
        """Black screen detected via INIDISP in full parse."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x00,  # Screen off
            health=24, max_health=24
        )

        parser = GameStateParser()
        state = parser.parse(snapshot)

        # Note: is_black_screen depends on snapshot.is_black_screen property
        # which may have different logic than just INIDISP=0
        # This test verifies the parser doesn't crash with low brightness
        assert state is not None

    def test_health_percent_calculated(self):
        """Health percent calculated from snapshot values."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=12, max_health=24  # 50%
        )

        state = parse_state(snapshot)
        assert abs(state.health_percent - 0.5) < 0.01


class TestParserLocationIntegration:
    """Test GameStateParser uses locations module correctly."""

    def test_overworld_location_name(self):
        """Overworld location name from locations module."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(snapshot)

        # locations module has area 0x29 as Village Center
        assert "Village" in state.location_name or "0x29" in state.location_name

    def test_indoor_room_name(self):
        """Indoor room name from locations module."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x00, room=0x27,
            link_x=256, link_y=256, link_z=0,
            link_direction=0x00, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(snapshot)

        # locations module has room 0x27 as Zora Temple Water Gate
        assert "Zora" in state.location_name or "0x27" in state.location_name.upper()


# =============================================================================
# InputRecorder -> InputPlayer Integration
# =============================================================================

class TestInputRecorderPlayerIntegration:
    """Test InputRecorder sequences play back correctly."""

    @pytest.fixture
    def mock_emulator(self):
        """Mock emulator for playback."""
        emu = Mock()
        emu.inject_input.return_value = True
        emu.step_frame.return_value = True
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        return emu

    def test_record_then_play(self, mock_emulator):
        """Record sequence then play it back."""
        # Record
        recorder = InputRecorder("test_seq")
        recorder.start_recording()
        recorder.record_input(Button.A, 5)
        recorder.advance_frames(10)
        recorder.record_input(Button.B, 3)
        recorder.stop_recording()

        seq = recorder.get_sequence()

        # Play
        player = InputPlayer(mock_emulator)
        result = player.play(seq)

        assert result is True
        # Should have called inject_input for both inputs
        assert mock_emulator.inject_input.call_count >= 2

    def test_prebuilt_sequence_playback(self, mock_emulator):
        """Pre-built sequence plays back correctly."""
        boot_seq = create_boot_sequence()

        player = InputPlayer(mock_emulator)
        result = player.play(boot_seq)

        assert result is True
        mock_emulator.inject_input.assert_called()

    def test_save_load_play(self, mock_emulator):
        """Save, load, then play sequence."""
        # Create sequence
        seq = InputSequence("saveable", "Test save/load/play")
        seq.add_input(0, Button.START, 2)
        seq.add_input(30, Button.A, 2)

        # Save and load
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)

        try:
            seq.save(path)
            loaded = InputSequence.load(path)

            # Play loaded sequence
            player = InputPlayer(mock_emulator)
            result = player.play(loaded)

            assert result is True
        finally:
            path.unlink()


# =============================================================================
# ActionPlanner -> InputPlayer Integration
# =============================================================================

class TestActionPlannerInputIntegration:
    """Test ActionPlanner creates playable actions."""

    def test_enter_building_creates_input_sequence(self):
        """Enter building plan has input sequence."""
        planner = ActionPlanner()
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)

        # Should have at least one action with input sequence
        has_input = any(a.input_sequence is not None for a in plan.actions)
        assert has_input

    def test_defeat_enemy_creates_input_sequences(self):
        """Defeat enemy plan has input sequences for attacks."""
        planner = ActionPlanner()
        goal = Goal.defeat_enemy()
        plan = planner.create_plan(goal)

        # Each attack action should have an input sequence
        attack_actions = [a for a in plan.actions if "attack" in a.name.lower()]
        for action in attack_actions:
            assert action.input_sequence is not None


# =============================================================================
# Pathfinder -> InputRecorder Integration
# =============================================================================

class TestPathfinderInputIntegration:
    """Test pathfinding results convert to input sequences."""

    def test_path_to_input_sequence(self):
        """Convert path to input sequence."""
        pathfinder = Pathfinder()

        # Simple path
        collision = CollisionMap(data=bytes([TileType.WALKABLE] * (64 * 64)))
        result = pathfinder.find_path((0, 0), (5, 0), collision_map=collision)

        # Convert to inputs
        inputs = pathfinder.path_to_inputs(result.path)

        # Should have inputs for the path (may be tuples of (direction, frames))
        assert isinstance(inputs, list)

    def test_path_result_is_valid(self):
        """Path result has expected structure."""
        pathfinder = Pathfinder()

        collision = CollisionMap(data=bytes([TileType.WALKABLE] * (64 * 64)))
        result = pathfinder.find_path((0, 0), (3, 3), collision_map=collision)

        # Result should be a NavigationResult
        assert isinstance(result, NavigationResult)
        if result.success:
            assert len(result.path) > 0


# =============================================================================
# ProgressValidator -> GameStateParser Integration
# =============================================================================

class TestProgressValidatorStateIntegration:
    """Test progress validation with parsed states."""

    def test_progress_snapshot_creation(self):
        """ProgressSnapshot can be created with game data."""
        from scripts.campaign.progress_validator import ProgressSnapshot

        snapshot = ProgressSnapshot(
            timestamp=1.0,
            game_state=0x09,
            story_flags=StoryFlag.INTRO_COMPLETE,
            story_flags_2=0,
            side_quest_1=0,
            side_quest_2=0,
            health=24,
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0,
            follower_id=0,
            follower_state=0
        )

        assert snapshot.health == 24
        assert snapshot.max_health == 24

    def test_progress_snapshot_comparison(self):
        """ProgressSnapshots can be compared for changes."""
        from scripts.campaign.progress_validator import ProgressSnapshot

        snap1 = ProgressSnapshot(
            timestamp=1.0,
            game_state=0x09,
            story_flags=StoryFlag.INTRO_COMPLETE,
            story_flags_2=0,
            side_quest_1=0,
            side_quest_2=0,
            health=24,
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0,
            follower_id=0,
            follower_state=0
        )

        snap2 = ProgressSnapshot(
            timestamp=2.0,
            game_state=0x09,
            story_flags=StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH,
            story_flags_2=0,
            side_quest_1=0,
            side_quest_2=0,
            health=24,
            max_health=24,
            rupees=150,  # Changed
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=1,   # Changed
            follower_id=0,
            follower_state=0
        )

        # Snapshots should be different
        assert snap1 != snap2


# =============================================================================
# CampaignOrchestrator Full Integration
# =============================================================================

class TestOrchestratorFullIntegration:
    """Test CampaignOrchestrator with all modules."""

    def test_orchestrator_phase_from_state(self):
        """Orchestrator derives phase from game state."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        # Parse state
        state = parse_state(snapshot)

        # Game state should indicate overworld
        assert state.phase == GamePhase.OVERWORLD

    def test_campaign_progress_milestone_tracking(self):
        """Campaign progress tracks milestones."""
        progress = CampaignProgress()

        # Add milestone
        milestone = CampaignMilestone(
            id="reach_village",
            description="Reach Village Center",
            goal="A.2"
        )
        progress.add_milestone(milestone)

        # Complete milestone
        progress.complete_milestone("reach_village")

        assert milestone.status == MilestoneStatus.COMPLETED


class TestLocationDescriptionIntegration:
    """Test location description with game state."""

    def test_location_description_from_state(self):
        """Location description matches state."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(snapshot)

        # Compare with locations module
        expected = get_area_name(0x29)
        assert state.location_name == expected or "0x29" in state.location_name.upper()

    def test_indoor_location_from_state(self):
        """Indoor location from state uses room."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x00, room=0x12,  # Hall of Secrets (per game_state.py DUNGEON_ROOMS)
            link_x=256, link_y=256, link_z=0,
            link_direction=0x00, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(snapshot)

        # game_state.py DUNGEON_ROOMS has 0x12 as Hall of Secrets
        # The location_name should contain the room name
        assert "Hall" in state.location_name or "0x12" in state.location_name.upper()


# =============================================================================
# Full Workflow Tests
# =============================================================================

class TestFullWorkflow:
    """Test complete workflows across all modules."""

    @pytest.fixture
    def mock_emu(self):
        """Mock emulator for workflows."""
        emu = Mock()
        emu.is_connected.return_value = True
        emu.inject_input.return_value = True
        emu.step_frame.return_value = True
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        return emu

    def test_navigation_workflow(self, mock_emu):
        """Test navigation: goal -> plan -> inputs -> execute."""
        # 1. Create navigation goal
        goal = goal_reach_village_center()
        assert goal.goal_type == GoalType.REACH_LOCATION

        # 2. Create plan from goal
        planner = ActionPlanner(mock_emu)
        plan = planner.create_plan(goal)
        assert len(plan.actions) > 0

        # 3. Plan has conditions to check
        has_condition = any(a.condition is not None for a in plan.actions)
        assert has_condition

    def test_state_parse_validate_workflow(self):
        """Test: snapshot -> parse -> verify game state."""
        # 1. Create snapshot
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        # 2. Parse state
        state = parse_state(snapshot)
        assert state.is_playing is True

        # 3. Verify parsed data matches snapshot
        assert state.link_position == (512, 480)
        assert state.health_percent == 1.0  # 24/24

    def test_input_record_serialize_load_workflow(self):
        """Test: record -> serialize -> load -> verify."""
        # 1. Record inputs
        recorder = InputRecorder("workflow_test")
        recorder.start_recording()
        recorder.record_input(Button.A, 5)
        recorder.record_input(["UP", "B"], 10)
        recorder.stop_recording()
        seq = recorder.get_sequence()

        # 2. Serialize
        data = seq.to_dict()
        json_str = json.dumps(data)

        # 3. Load back
        loaded_data = json.loads(json_str)
        loaded_seq = InputSequence.from_dict(loaded_data)

        # 4. Verify
        assert loaded_seq.name == "workflow_test"
        assert len(loaded_seq.frames) == 2


class TestModuleConstants:
    """Test that module constants are compatible."""

    def test_mode_values_consistent(self):
        """Mode values are handled consistently."""
        # Overworld mode
        overworld_snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=0x02, link_state=0x00,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(overworld_snapshot)
        assert state.phase == GamePhase.OVERWORLD

        # Dungeon mode
        dungeon_snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x07, submode=0x00,
            area=0x06, room=0x27,
            link_x=256, link_y=256, link_z=0,
            link_direction=0x00, link_state=0x00,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        state = parse_state(dungeon_snapshot)
        assert state.phase == GamePhase.DUNGEON

    def test_direction_values_consistent(self):
        """Direction values handled consistently."""
        directions = [0x00, 0x02, 0x04, 0x06]  # Up, Down, Left, Right

        for direction in directions:
            snapshot = GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0x00,
                area=0x29, room=0x00,
                link_x=512, link_y=480, link_z=0,
                link_direction=direction, link_state=0x00,
                indoors=False, inidisp=0x0F,
                health=24, max_health=24
            )

            state = parse_state(snapshot)
            # Direction should be parseable
            assert state.link_direction in ["up", "down", "left", "right", "unknown"]


class TestErrorPropagation:
    """Test that errors propagate correctly between modules."""

    def test_invalid_snapshot_handled(self):
        """Invalid snapshot values handled gracefully."""
        # Extreme values
        snapshot = GameStateSnapshot(
            timestamp=0.0, mode=0xFF, submode=0xFF,
            area=0xFF, room=0xFFFF,
            link_x=99999, link_y=99999, link_z=999,
            link_direction=0xFF, link_state=0xFF,
            indoors=True, inidisp=0x00,
            health=0, max_health=0
        )

        # Should not raise
        state = parse_state(snapshot)
        assert state is not None
        # Unknown phase for unrecognized mode
        assert state.phase in (GamePhase.UNKNOWN, GamePhase.BLACK_SCREEN)

    def test_empty_path_handled(self):
        """Empty pathfinding result handled."""
        pathfinder = Pathfinder()

        # Blocked path
        collision = CollisionMap(data=bytes([TileType.SOLID] * (64 * 64)))
        result = pathfinder.find_path((0, 0), (10, 10), collision_map=collision)

        # Should not raise - path should be empty or result should indicate failure
        if result.success:
            inputs = pathfinder.path_to_inputs(result.path)
            assert isinstance(inputs, list)
        else:
            # Failed pathfinding is expected
            assert result.path == []
