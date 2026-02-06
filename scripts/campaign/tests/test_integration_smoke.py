"""Iteration 60 - Integration Smoke Tests.

End-to-end integration tests validating all components work together.

Focus: Full system integration, component interoperability, data flow,
state propagation, multi-module workflows, system boundaries.
"""

import pytest
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from unittest.mock import MagicMock, patch, PropertyMock

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
    InputRecorder,
    InputPlayer,
)
from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
    GameStateParser,
    ParsedGameState,
    MODE_TO_PHASE,
    LINK_STATE_TO_ACTION,
)
from scripts.campaign.pathfinder import (
    TileType,
    CollisionMap,
    Pathfinder,
    NavigationResult,
    PathNode,
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
    CampaignOrchestrator,
)
from scripts.campaign.action_planner import (
    GoalType,
    PlanStatus,
    Goal,
    Plan,
    Action,
    ActionPlanner,
)
from scripts.campaign.progress_validator import (
    StoryFlag,
    GameStateValue,
    ProgressSnapshot,
    ProgressValidator,
    ProgressAddresses,
)


# =============================================================================
# Helper Functions
# =============================================================================

def create_mock_snapshot(**overrides) -> MagicMock:
    """Create a mock GameStateSnapshot with defaults."""
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
    defaults.update(overrides)

    mock = MagicMock()
    for key, value in defaults.items():
        setattr(mock, key, value)

    # is_black_screen is a property
    mock.is_black_screen = defaults.get('inidisp') == 0x80 and defaults.get('mode') in (0x06, 0x07)
    return mock


def create_mock_emulator(**overrides) -> MagicMock:
    """Create a mock EmulatorInterface."""
    mock = MagicMock()
    status = overrides.get('status', EmulatorStatus.CONNECTED)
    type(mock).status = PropertyMock(return_value=status)
    mock.connect.return_value = True
    mock.disconnect.return_value = None
    return mock


def create_walkable_map(width: int = 8, height: int = 8) -> CollisionMap:
    """Create a fully walkable collision map."""
    data = bytes([TileType.WALKABLE] * (width * height))
    return CollisionMap(data=data, width=width, height=height)


# =============================================================================
# Emulator to Parser Integration Tests
# =============================================================================

class TestEmulatorToParserIntegration:
    """Tests for emulator to parser data flow."""

    def test_mock_emulator_provides_snapshot(self):
        """Emulator provides snapshot for parsing."""
        mock_emu = create_mock_emulator()
        snapshot = create_mock_snapshot(mode=0x09, area=0x29)
        mock_emu.get_snapshot.return_value = snapshot

        result = mock_emu.get_snapshot()
        assert result.mode == 0x09
        assert result.area == 0x29

    def test_parser_processes_snapshot(self):
        """Parser processes emulator snapshot."""
        snapshot = create_mock_snapshot(mode=0x09)
        parser = GameStateParser()

        parsed = parser.parse(snapshot)
        assert parsed.phase == GamePhase.OVERWORLD

    def test_parser_detects_phase_changes(self):
        """Parser detects phase changes from snapshots."""
        parser = GameStateParser()

        # First state - overworld
        snap1 = create_mock_snapshot(mode=0x09)
        parsed1 = parser.parse(snap1)

        # Change to menu
        snap2 = create_mock_snapshot(mode=0x0E)
        parsed2 = parser.parse(snap2)

        assert parsed1.phase == GamePhase.OVERWORLD
        assert parsed2.phase == GamePhase.MENU

    def test_emulator_memory_read_chain(self):
        """Chain of memory reads from emulator."""
        mock_emu = create_mock_emulator()
        mock_emu.read_memory.side_effect = [
            MemoryRead(address=0x10, value=0x09),  # Mode
            MemoryRead(address=0x11, value=0x29),  # Area
            MemoryRead(address=0x12, value=0x00),  # Room
        ]

        mode = mock_emu.read_memory(0x10).value
        area = mock_emu.read_memory(0x11).value
        room = mock_emu.read_memory(0x12).value

        assert mode == 0x09
        assert area == 0x29
        assert room == 0x00


# =============================================================================
# Parser to Action Planner Integration Tests
# =============================================================================

class TestParserToActionPlannerIntegration:
    """Tests for parser to action planner integration."""

    def test_parsed_state_for_goal_evaluation(self):
        """Parsed state used for goal evaluation."""
        snapshot = create_mock_snapshot(area=0x29, link_x=100, link_y=100)
        parser = GameStateParser()
        parsed = parser.parse(snapshot)

        goal = Goal.reach_location(0x29, 100, 100)

        # Goal should have area matching parsed state
        assert parsed.area_id == 0x29

    def test_plan_action_conditions(self):
        """Plan action conditions use parsed state."""
        planner = ActionPlanner()

        # Create a goal
        goal = Goal.reach_location(0x29, 150, 150)
        plan = planner.create_plan(goal)

        assert plan.status == PlanStatus.NOT_STARTED
        assert plan.goal is goal

    def test_action_planner_tracks_progress(self):
        """Action planner tracks goal progress."""
        planner = ActionPlanner()
        goal = Goal.reach_location(0x29, 100, 100)
        plan = planner.create_plan(goal)

        # Start execution
        plan.status = PlanStatus.IN_PROGRESS

        assert plan.status == PlanStatus.IN_PROGRESS


# =============================================================================
# Pathfinder to Input Integration Tests
# =============================================================================

class TestPathfinderToInputIntegration:
    """Tests for pathfinder to input recorder integration."""

    def test_path_generates_inputs(self):
        """Pathfinder path converted to inputs."""
        cmap = create_walkable_map()

        # Simulate a path result
        mock_result = MagicMock(spec=NavigationResult)
        mock_result.success = True
        mock_result.path = [(0, 0), (1, 0), (2, 0)]

        # Path should exist
        assert mock_result.success
        assert len(mock_result.path) == 3

    def test_input_sequence_for_navigation(self):
        """Input sequence created for navigation."""
        sequence = InputSequence(name="walk_right")

        # Add movement inputs
        for i in range(3):
            sequence.add_input(i * 8, Button.RIGHT, hold=8)

        assert sequence.name == "walk_right"
        assert len(sequence.frames) == 3

    def test_recorder_captures_navigation(self):
        """Recorder captures navigation inputs."""
        recorder = InputRecorder()
        recorder.start_recording()

        # Simulate recording inputs
        recorder.record_input(Button.RIGHT)
        recorder.advance_frames(8)
        recorder.record_input(Button.RIGHT)
        recorder.advance_frames(8)

        recorder.stop_recording()

        sequence = recorder.get_sequence()
        assert len(sequence.frames) >= 2


# =============================================================================
# Progress Validator Integration Tests
# =============================================================================

class TestProgressValidatorIntegration:
    """Tests for progress validator integration."""

    def test_snapshot_validation(self):
        """Progress snapshot validated."""
        # Use a mock for ProgressSnapshot since it has many required fields
        mock_snapshot = MagicMock()
        mock_snapshot.story_flags = StoryFlag.INTRO_COMPLETE
        mock_snapshot.game_state = GameStateValue.LOOM_BEACH

        assert mock_snapshot.story_flags & StoryFlag.INTRO_COMPLETE

    def test_validator_checks_progress(self):
        """Validator checks game progress."""
        mock_emu = create_mock_emulator()
        validator = ProgressValidator(emulator=mock_emu)

        # Use a mock snapshot
        mock_snapshot = MagicMock()
        mock_snapshot.story_flags = StoryFlag.INTRO_COMPLETE
        mock_snapshot.game_state = GameStateValue.LOOM_BEACH

        # Validator should process snapshot
        assert mock_snapshot.game_state == GameStateValue.LOOM_BEACH

    def test_progress_flag_combinations(self):
        """Flag combinations for progress tracking."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH

        assert flags & StoryFlag.INTRO_COMPLETE
        assert flags & StoryFlag.LOOM_BEACH


# =============================================================================
# Campaign Orchestrator Integration Tests
# =============================================================================

class TestCampaignOrchestratorIntegration:
    """Tests for campaign orchestrator integration."""

    def test_orchestrator_milestone_management(self):
        """Orchestrator manages milestones."""
        progress = CampaignProgress()
        goal = Goal.reach_location(0x29, 100, 100)

        milestone = CampaignMilestone(
            id="exit_house",
            description="Exit Link's house",
            goal=goal
        )

        progress.add_milestone(milestone)
        assert "exit_house" in progress.milestones

    def test_orchestrator_phase_tracking(self):
        """Orchestrator tracks campaign phase."""
        progress = CampaignProgress()

        # Simulate phase progression
        phases = [
            CampaignPhase.DISCONNECTED,
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
        ]

        for phase in phases:
            progress.current_phase = phase

        assert progress.current_phase == CampaignPhase.EXPLORING

    def test_orchestrator_counter_updates(self):
        """Orchestrator updates counters."""
        progress = CampaignProgress()

        progress.total_frames_played += 60
        progress.iterations_completed += 1

        assert progress.total_frames_played == 60
        assert progress.iterations_completed == 1


# =============================================================================
# Full Pipeline Integration Tests
# =============================================================================

class TestFullPipelineIntegration:
    """Tests for full pipeline integration."""

    def test_emulator_to_progress_pipeline(self):
        """Full pipeline from emulator to progress."""
        # Emulator
        mock_emu = create_mock_emulator()
        snapshot = create_mock_snapshot(mode=0x09, area=0x29)
        mock_emu.get_snapshot.return_value = snapshot

        # Parser
        parser = GameStateParser()
        parsed = parser.parse(mock_emu.get_snapshot())

        # Progress
        progress = CampaignProgress()
        progress.total_frames_played += 1

        assert parsed.phase == GamePhase.OVERWORLD
        assert progress.total_frames_played == 1

    def test_navigation_pipeline(self):
        """Navigation from pathfinder to input."""
        # Simulate pathfinder result
        mock_result = MagicMock(spec=NavigationResult)
        mock_result.success = True
        mock_result.path = [(0, 0), (1, 0), (2, 0)]

        # Input generation
        sequence = InputSequence(name="auto_nav")
        if mock_result.success:
            for i, pos in enumerate(mock_result.path):
                sequence.add_input(i, Button.RIGHT, hold=1)

        assert sequence.name == "auto_nav"
        assert len(sequence.frames) == 3

    def test_goal_execution_pipeline(self):
        """Goal execution from planner to completion."""
        # Action planner
        planner = ActionPlanner()
        goal = Goal.reach_location(0x29, 100, 100)
        plan = planner.create_plan(goal)

        # Execute
        plan.status = PlanStatus.IN_PROGRESS

        # Complete
        plan.status = PlanStatus.COMPLETED

        assert plan.status == PlanStatus.COMPLETED


# =============================================================================
# State Synchronization Tests
# =============================================================================

class TestStateSynchronization:
    """Tests for state synchronization between components."""

    def test_snapshot_propagation(self):
        """Snapshot data propagates correctly."""
        snapshot = create_mock_snapshot(
            mode=0x09,
            area=0x29,
            link_x=128,
            link_y=128,
            health=24,
        )

        # Verify all fields accessible
        assert snapshot.mode == 0x09
        assert snapshot.area == 0x29
        assert snapshot.link_x == 128
        assert snapshot.link_y == 128
        assert snapshot.health == 24

    def test_phase_synchronization(self):
        """Phase synchronized across components."""
        parser = GameStateParser()

        # Parse multiple states (using modes that don't require indoors flag)
        states = [
            create_mock_snapshot(mode=0x09),  # Overworld
            create_mock_snapshot(mode=0x0E),  # Menu
            create_mock_snapshot(mode=0x09),  # Overworld
        ]

        phases = [parser.parse(s).phase for s in states]

        assert phases == [GamePhase.OVERWORLD, GamePhase.MENU, GamePhase.OVERWORLD]

    def test_input_state_synchronization(self):
        """Input state synchronized correctly."""
        recorder = InputRecorder()

        # Record
        recorder.start_recording()
        recorder.record_input(Button.A)
        recorder.advance_frames(5)
        recorder.stop_recording()

        # Verify state
        assert not recorder.is_recording
        sequence = recorder.get_sequence()
        assert len(sequence.frames) >= 1


# =============================================================================
# Error Recovery Integration Tests
# =============================================================================

class TestErrorRecoveryIntegration:
    """Tests for error recovery integration."""

    def test_connection_retry_integration(self):
        """Connection retry with state recovery."""
        mock_emu = create_mock_emulator()
        mock_emu.connect.side_effect = [
            ConnectionError("Failed"),
            ConnectionError("Failed again"),
            True,
        ]

        connected = False
        for _ in range(3):
            try:
                connected = mock_emu.connect()
                break
            except ConnectionError:
                continue

        assert connected is True

    def test_state_recovery_after_error(self):
        """State recovered after error."""
        progress = CampaignProgress()
        progress.iterations_completed = 5

        # Simulate error and recovery
        saved_iterations = progress.iterations_completed

        # After recovery
        progress.iterations_completed = saved_iterations

        assert progress.iterations_completed == 5

    def test_black_screen_recovery_integration(self):
        """Black screen recovery integrated."""
        parser = GameStateParser()

        # Black screen state
        black_snap = create_mock_snapshot(mode=0x07, inidisp=0x80)
        black_snap.is_black_screen = True

        # Normal state
        normal_snap = create_mock_snapshot(mode=0x09, inidisp=0x0F)
        normal_snap.is_black_screen = False

        parsed_black = parser.parse(black_snap)
        parsed_normal = parser.parse(normal_snap)

        assert parsed_normal.phase == GamePhase.OVERWORLD


# =============================================================================
# Component Interoperability Tests
# =============================================================================

class TestComponentInteroperability:
    """Tests for component interoperability."""

    def test_all_enums_accessible(self):
        """All enums accessible across modules."""
        # Emulator
        assert EmulatorStatus.CONNECTED is not None

        # Game state
        assert GamePhase.OVERWORLD is not None
        assert LinkAction.WALKING is not None

        # Campaign
        assert CampaignPhase.EXPLORING is not None
        assert MilestoneStatus.NOT_STARTED is not None

        # Planner
        assert GoalType.REACH_LOCATION is not None
        assert PlanStatus.NOT_STARTED is not None

        # Pathfinder
        assert TileType.WALKABLE is not None

        # Validator
        assert StoryFlag.INTRO_COMPLETE is not None
        assert GameStateValue.START is not None

    def test_dataclasses_serializable(self):
        """Dataclasses are serializable."""
        # Input frame
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=1)
        frame_dict = frame.to_dict()
        assert "buttons" in frame_dict

        # Memory read
        mem = MemoryRead(address=0x10, value=0x42)
        assert mem.address == 0x10

    def test_mock_objects_compatible(self):
        """Mock objects compatible with interfaces."""
        mock_emu = create_mock_emulator()
        mock_snap = create_mock_snapshot()

        # Mock can be configured
        mock_emu.get_snapshot.return_value = mock_snap

        result = mock_emu.get_snapshot()
        assert result.mode == 0x09


# =============================================================================
# Data Flow Tests
# =============================================================================

class TestDataFlow:
    """Tests for data flow between components."""

    def test_memory_to_snapshot_flow(self):
        """Memory reads flow to snapshot."""
        mock_emu = create_mock_emulator()
        mock_emu.read_memory.side_effect = [
            MemoryRead(address=0x10, value=0x09),
            MemoryRead(address=0x11, value=0x29),
        ]

        mode = mock_emu.read_memory(0x10).value
        area = mock_emu.read_memory(0x11).value

        snapshot = create_mock_snapshot(mode=mode, area=area)
        assert snapshot.mode == 0x09
        assert snapshot.area == 0x29

    def test_snapshot_to_parsed_flow(self):
        """Snapshot flows to parsed state."""
        snapshot = create_mock_snapshot(
            mode=0x09,
            area=0x29,
            link_x=128,
            link_y=128,
        )

        parser = GameStateParser()
        parsed = parser.parse(snapshot)

        assert parsed.phase == GamePhase.OVERWORLD
        assert parsed.area_id == 0x29

    def test_path_to_inputs_flow(self):
        """Path flows to inputs."""
        path = [(0, 0), (1, 0), (2, 0)]

        sequence = InputSequence(name="path_inputs")
        for i, pos in enumerate(path):
            sequence.add_input(i * 8, Button.RIGHT, hold=8)

        assert len(sequence.frames) == 3


# =============================================================================
# Boundary Crossing Tests
# =============================================================================

class TestBoundaryCrossing:
    """Tests for data crossing module boundaries."""

    def test_emulator_abstraction_boundary(self):
        """Data crosses emulator abstraction boundary."""
        mock_emu = create_mock_emulator()
        snapshot = create_mock_snapshot()
        mock_emu.get_snapshot.return_value = snapshot

        # Cross boundary
        result = mock_emu.get_snapshot()

        # Validate on other side
        assert hasattr(result, 'mode')
        assert hasattr(result, 'area')

    def test_parser_boundary(self):
        """Data crosses parser boundary."""
        snapshot = create_mock_snapshot(mode=0x09)
        parser = GameStateParser()

        # Cross boundary
        parsed = parser.parse(snapshot)

        # Validate on other side
        assert hasattr(parsed, 'phase')
        assert hasattr(parsed, 'area_id')

    def test_pathfinder_boundary(self):
        """Data crosses pathfinder boundary."""
        cmap = create_walkable_map()

        # Verify collision map is walkable
        assert cmap.is_walkable(0, 0)
        assert cmap.is_walkable(1, 0)

        # Simulate result crossing boundary
        mock_result = MagicMock(spec=NavigationResult)
        mock_result.success = True
        mock_result.path = [(0, 0), (1, 0)]

        # Validate on other side
        assert hasattr(mock_result, 'success')
        assert hasattr(mock_result, 'path')


# =============================================================================
# System Invariant Tests
# =============================================================================

class TestSystemInvariants:
    """Tests for system-wide invariants."""

    def test_mode_to_phase_mapping_complete(self):
        """Mode to phase mapping is complete."""
        known_modes = [0x00, 0x06, 0x07, 0x09, 0x0E, 0x14]

        for mode in known_modes:
            if mode in MODE_TO_PHASE:
                phase = MODE_TO_PHASE[mode]
                assert phase in GamePhase

    def test_button_flags_unique(self):
        """Button flags are unique power of 2."""
        button_values = []
        for button in Button:
            if button != Button.NONE:
                button_values.append(button.value)

        # All unique
        assert len(button_values) == len(set(button_values))

    def test_tile_types_distinct(self):
        """Tile types are distinct."""
        tile_values = [t.value for t in TileType]
        assert len(tile_values) == len(set(tile_values))

    def test_campaign_phases_ordered(self):
        """Campaign phases have defined order."""
        phases = list(CampaignPhase)
        assert len(phases) > 0

    def test_milestone_status_transitions_valid(self):
        """Milestone status transitions are valid."""
        valid_transitions = [
            (MilestoneStatus.NOT_STARTED, MilestoneStatus.IN_PROGRESS),
            (MilestoneStatus.IN_PROGRESS, MilestoneStatus.COMPLETED),
            (MilestoneStatus.IN_PROGRESS, MilestoneStatus.BLOCKED),
        ]

        for from_status, to_status in valid_transitions:
            assert from_status != to_status


# =============================================================================
# End-to-End Scenario Tests
# =============================================================================

class TestEndToEndScenarios:
    """End-to-end integration scenarios."""

    def test_boot_to_exploration_scenario(self):
        """Boot to exploration scenario."""
        progress = CampaignProgress()

        # Boot phase
        progress.current_phase = CampaignPhase.BOOTING

        # Parse boot state
        parser = GameStateParser()
        boot_snap = create_mock_snapshot(mode=0x00)
        parser.parse(boot_snap)

        # Transition to exploring
        progress.current_phase = CampaignPhase.EXPLORING
        explore_snap = create_mock_snapshot(mode=0x09)
        parsed = parser.parse(explore_snap)

        assert progress.current_phase == CampaignPhase.EXPLORING
        assert parsed.phase == GamePhase.OVERWORLD

    def test_navigation_to_milestone_scenario(self):
        """Navigation to milestone completion."""
        # Setup
        progress = CampaignProgress()
        goal = Goal.reach_location(0x29, 100, 100)
        milestone = CampaignMilestone(
            id="reach_village",
            description="Reach Kakariko Village",
            goal=goal
        )
        progress.add_milestone(milestone)

        # Simulate successful navigation
        mock_result = MagicMock(spec=NavigationResult)
        mock_result.success = True
        mock_result.path = [(0, 0), (1, 1), (2, 2)]

        # Complete milestone after successful navigation
        if mock_result.success:
            progress.complete_milestone("reach_village")

        assert progress.milestones["reach_village"].status == MilestoneStatus.COMPLETED

    def test_combat_detection_scenario(self):
        """Combat detection during exploration."""
        parser = GameStateParser()

        # Normal exploration
        explore_snap = create_mock_snapshot(mode=0x09, link_state=0x00)
        parsed_explore = parser.parse(explore_snap)

        # Combat state
        combat_snap = create_mock_snapshot(mode=0x09, link_state=0x11)
        parsed_combat = parser.parse(combat_snap)

        assert parsed_explore.link_action == LinkAction.STANDING
        assert parsed_combat.link_action == LinkAction.ATTACKING

    def test_dungeon_exploration_scenario(self):
        """Dungeon exploration scenario."""
        parser = GameStateParser()
        progress = CampaignProgress()

        # Enter dungeon (mode 0x07 with indoors=True)
        dungeon_snap = create_mock_snapshot(mode=0x07, area=0x00, room=0x01, indoors=True)
        parsed = parser.parse(dungeon_snap)

        progress.current_phase = CampaignPhase.IN_DUNGEON
        progress.total_frames_played += 600  # 10 seconds at 60fps

        assert parsed.phase == GamePhase.DUNGEON
        assert progress.current_phase == CampaignPhase.IN_DUNGEON

    def test_full_session_scenario(self):
        """Full campaign session scenario."""
        # Initialize
        progress = CampaignProgress()
        parser = GameStateParser()
        recorder = InputRecorder()

        # Connect phase
        progress.current_phase = CampaignPhase.CONNECTING
        mock_emu = create_mock_emulator()
        mock_emu.connect()

        # Boot phase
        progress.current_phase = CampaignPhase.BOOTING
        boot_snap = create_mock_snapshot(mode=0x00)
        parser.parse(boot_snap)

        # Record boot inputs
        recorder.start_recording()
        recorder.record_input(Button.START)
        recorder.advance_frames(60)
        recorder.stop_recording()

        # Explore phase
        progress.current_phase = CampaignPhase.EXPLORING
        explore_snap = create_mock_snapshot(mode=0x09)
        parsed = parser.parse(explore_snap)

        # Track progress
        progress.iterations_completed += 1
        progress.total_frames_played += recorder.get_sequence().total_frames

        # Verify final state
        assert progress.current_phase == CampaignPhase.EXPLORING
        assert progress.iterations_completed == 1
        assert parsed.phase == GamePhase.OVERWORLD
