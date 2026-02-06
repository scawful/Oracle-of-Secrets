"""Iteration 56 - Workflow Scenario Tests.

Tests for complete workflow scenarios simulating real gameplay loops.

Focus: Boot-to-gameplay flow, navigation workflows, milestone achievement,
phase transitions, input-action-verify loops, recovery scenarios.
"""

import pytest
import time
from unittest.mock import MagicMock, patch
from dataclasses import replace

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
    InputPlayer,
)
from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
    ParsedGameState,
    GameStateParser,
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
    ActionPlanner,
)
from scripts.campaign.pathfinder import (
    TileType,
    CollisionMap,
    NavigationResult,
    Pathfinder,
)


# =============================================================================
# Helper Functions
# =============================================================================

def _snapshot(**overrides) -> GameStateSnapshot:
    """Create GameStateSnapshot with defaults."""
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
    return GameStateSnapshot(**defaults)


def _parsed_state(snapshot: GameStateSnapshot) -> ParsedGameState:
    """Parse snapshot to ParsedGameState."""
    parser = GameStateParser()
    return parser.parse(snapshot)


def _simple_map(size: int = 64) -> CollisionMap:
    """Create all-walkable collision map."""
    return CollisionMap(
        data=bytes([TileType.WALKABLE] * (size * size)),
        width=size,
        height=size
    )


# =============================================================================
# Boot Sequence Workflow Tests
# =============================================================================

class TestBootSequenceWorkflow:
    """Tests for boot sequence workflows."""

    def test_boot_to_title_screen(self):
        """Workflow: Boot -> Title Screen."""
        states = [
            _snapshot(mode=0x00, inidisp=0x00),  # Boot
            _snapshot(mode=0x00, inidisp=0x80),  # Boot (screen on)
            _snapshot(mode=0x01, inidisp=0x0F),  # Title screen
        ]

        parser = GameStateParser()
        phases = [parser.parse(s).phase for s in states]

        assert phases[0] == GamePhase.BOOT
        assert phases[2] == GamePhase.TITLE_SCREEN

    def test_title_to_file_select(self):
        """Workflow: Title -> File Select."""
        states = [
            _snapshot(mode=0x01),  # Title
            _snapshot(mode=0x02),  # File select
        ]

        parser = GameStateParser()
        phases = [parser.parse(s).phase for s in states]

        assert phases[0] == GamePhase.TITLE_SCREEN
        assert phases[1] == GamePhase.FILE_SELECT

    def test_file_select_to_intro(self):
        """Workflow: File Select -> Intro."""
        states = [
            _snapshot(mode=0x02),  # File select
            _snapshot(mode=0x05),  # Intro
        ]

        parser = GameStateParser()
        phases = [parser.parse(s).phase for s in states]

        assert phases[0] == GamePhase.FILE_SELECT
        assert phases[1] == GamePhase.INTRO

    def test_intro_to_overworld(self):
        """Workflow: Intro -> Overworld."""
        states = [
            _snapshot(mode=0x05),  # Intro
            _snapshot(mode=0x09),  # Overworld
        ]

        parser = GameStateParser()
        phases = [parser.parse(s).phase for s in states]

        assert phases[0] == GamePhase.INTRO
        assert phases[1] == GamePhase.OVERWORLD

    def test_full_boot_sequence(self):
        """Full boot sequence from power-on to gameplay."""
        states = [
            _snapshot(mode=0x00),  # Boot
            _snapshot(mode=0x01),  # Title
            _snapshot(mode=0x02),  # File select
            _snapshot(mode=0x05),  # Intro
            _snapshot(mode=0x09),  # Overworld
        ]

        parser = GameStateParser()
        phases = [parser.parse(s).phase for s in states]

        expected = [
            GamePhase.BOOT,
            GamePhase.TITLE_SCREEN,
            GamePhase.FILE_SELECT,
            GamePhase.INTRO,
            GamePhase.OVERWORLD,
        ]
        assert phases == expected


# =============================================================================
# Navigation Workflow Tests
# =============================================================================

class TestNavigationWorkflow:
    """Tests for navigation workflows."""

    def test_walk_single_tile(self):
        """Workflow: Walk one tile right."""
        start = _snapshot(link_x=128, link_y=128)
        end = _snapshot(link_x=136, link_y=128)

        parser = GameStateParser()
        start_pos = parser.parse(start).link_position
        end_pos = parser.parse(end).link_position

        assert start_pos == (128, 128)
        assert end_pos == (136, 128)
        # Moved 8 pixels right (1 tile)
        assert end_pos[0] - start_pos[0] == 8

    def test_walk_path_sequence(self):
        """Workflow: Walk multi-tile path."""
        positions = [(128, 128), (136, 128), (144, 128), (144, 136)]
        states = [_snapshot(link_x=x, link_y=y) for x, y in positions]

        parser = GameStateParser()
        parsed_positions = [parser.parse(s).link_position for s in states]

        assert parsed_positions == positions

    def test_navigation_with_pathfinder(self):
        """Workflow: Use pathfinder for navigation."""
        pf = Pathfinder()
        cmap = _simple_map()

        # Plan path from (2, 2) to (5, 5)
        result = pf.find_path((2, 2), (5, 5), collision_map=cmap)

        assert result.success is True
        assert result.path[0] == (2, 2)
        assert result.path[-1] == (5, 5)

    def test_navigation_generates_inputs(self):
        """Workflow: Path to input sequence."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        # Should have RIGHT (2 tiles) then DOWN (2 tiles)
        assert len(inputs) == 2
        assert inputs[0] == ("RIGHT", 16)
        assert inputs[1] == ("DOWN", 16)


# =============================================================================
# Transition Workflow Tests
# =============================================================================

class TestTransitionWorkflow:
    """Tests for area/room transition workflows."""

    def test_overworld_to_dungeon(self):
        """Workflow: Enter dungeon from overworld."""
        states = [
            _snapshot(mode=0x09, indoors=False),   # Overworld
            _snapshot(mode=0x06, indoors=False),   # Transition
            _snapshot(mode=0x07, indoors=True),    # Dungeon
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert parsed[0].phase == GamePhase.OVERWORLD
        assert parsed[1].is_transitioning
        assert parsed[2].phase == GamePhase.DUNGEON

    def test_dungeon_to_overworld(self):
        """Workflow: Exit dungeon to overworld."""
        states = [
            _snapshot(mode=0x07, indoors=True),    # Dungeon
            _snapshot(mode=0x06, indoors=True),    # Transition
            _snapshot(mode=0x09, indoors=False),   # Overworld
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert parsed[0].phase == GamePhase.DUNGEON
        assert parsed[2].phase == GamePhase.OVERWORLD

    def test_room_transition(self):
        """Workflow: Move between rooms."""
        states = [
            _snapshot(room=0x10, link_x=128),
            _snapshot(room=0x10, link_x=250),      # Near edge
            _snapshot(room=0x11, link_x=10),       # New room
        ]

        parser = GameStateParser()
        room_ids = [parser.parse(s).room_id for s in states]

        assert room_ids[0] == 0x10
        assert room_ids[2] == 0x11

    def test_area_transition(self):
        """Workflow: Move between overworld areas."""
        states = [
            _snapshot(area=0x29),
            _snapshot(area=0x2A),  # Adjacent area
        ]

        parser = GameStateParser()
        area_ids = [parser.parse(s).area_id for s in states]

        assert area_ids[0] == 0x29
        assert area_ids[1] == 0x2A


# =============================================================================
# Menu Interaction Workflow Tests
# =============================================================================

class TestMenuWorkflow:
    """Tests for menu interaction workflows."""

    def test_open_close_menu(self):
        """Workflow: Open and close menu."""
        states = [
            _snapshot(mode=0x09),  # Overworld
            _snapshot(mode=0x0E),  # Menu open
            _snapshot(mode=0x09),  # Overworld (menu closed)
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert not parsed[0].is_menu_open
        assert parsed[1].is_menu_open
        assert not parsed[2].is_menu_open

    def test_dialogue_sequence(self):
        """Workflow: Talk to NPC."""
        states = [
            _snapshot(mode=0x09, link_state=0x00),  # Standing
            _snapshot(mode=0x0F),                     # Dialogue
            _snapshot(mode=0x0F),                     # Still talking
            _snapshot(mode=0x09),                     # Done
        ]

        parser = GameStateParser()
        dialogue_states = [parser.parse(s).is_dialogue_open for s in states]

        assert not dialogue_states[0]
        assert dialogue_states[1]
        assert dialogue_states[2]
        assert not dialogue_states[3]


# =============================================================================
# Combat Workflow Tests
# =============================================================================

class TestCombatWorkflow:
    """Tests for combat workflows."""

    def test_attack_sequence(self):
        """Workflow: Perform attack."""
        states = [
            _snapshot(link_state=0x00),  # Standing
            _snapshot(link_state=0x11),  # Attacking
            _snapshot(link_state=0x00),  # Done
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert not parsed[0].is_combat
        assert parsed[1].is_combat
        assert not parsed[2].is_combat

    def test_take_damage(self):
        """Workflow: Take damage from enemy."""
        states = [
            _snapshot(health=24, link_state=0x00),  # Full health
            _snapshot(health=24, link_state=0x04),  # Knocked back
            _snapshot(health=20, link_state=0x00),  # After damage
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert parsed[0].health_percent == 1.0
        assert parsed[1].link_action == LinkAction.KNOCKED_BACK
        assert parsed[2].health_percent < 1.0

    def test_defeat_sequence(self):
        """Workflow: Health depletes to zero."""
        states = [
            _snapshot(health=4, link_state=0x00),
            _snapshot(health=0, link_state=0x17),  # Dying
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert parsed[0].health_percent > 0
        assert parsed[1].link_action == LinkAction.DYING


# =============================================================================
# Input Recording Workflow Tests
# =============================================================================

class TestInputRecordingWorkflow:
    """Tests for input recording workflows."""

    def test_record_simple_sequence(self):
        """Workflow: Record simple input sequence."""
        recorder = InputRecorder(name="test_sequence")

        recorder.start_recording()
        recorder.record_input(Button.RIGHT)
        recorder.advance_frames()
        recorder.record_input(Button.RIGHT)
        recorder.advance_frames()
        recorder.record_input(Button.A)
        recorder.advance_frames()
        recorder.stop_recording()

        sequence = recorder.get_sequence()
        assert len(sequence.frames) > 0

    def test_record_and_get_sequence(self):
        """Workflow: Record and retrieve sequence."""
        recorder = InputRecorder(name="playback_test")

        recorder.start_recording()
        recorder.record_input(Button.UP)
        recorder.advance_frames()
        recorder.record_input(Button.A)
        recorder.advance_frames()
        recorder.stop_recording()

        sequence = recorder.get_sequence()

        # Verify sequence is valid
        assert sequence.name == "playback_test"
        assert len(sequence.frames) > 0

        # Verify frames can be iterated
        frame_list = list(sequence.frames)
        assert len(frame_list) > 0


# =============================================================================
# Milestone Achievement Workflow Tests
# =============================================================================

class TestMilestoneWorkflow:
    """Tests for milestone achievement workflows."""

    def test_complete_milestone(self):
        """Workflow: Achieve and complete milestone."""
        progress = CampaignProgress()
        ms = CampaignMilestone(
            id="reach_village",
            description="Reach the village",
            goal="A.2"
        )
        progress.add_milestone(ms)

        # Initially not completed
        assert progress.milestones["reach_village"].status == MilestoneStatus.NOT_STARTED

        # Complete it
        progress.milestones["reach_village"].complete("Arrived at village")
        assert progress.milestones["reach_village"].status == MilestoneStatus.COMPLETED

    def test_multiple_milestones(self):
        """Workflow: Track multiple milestones."""
        progress = CampaignProgress()

        milestones = [
            CampaignMilestone(id="boot", description="Boot game", goal="A.1"),
            CampaignMilestone(id="navigate", description="Navigate to area", goal="A.2"),
            CampaignMilestone(id="complete", description="Complete objective", goal="A.3"),
        ]

        for ms in milestones:
            progress.add_milestone(ms)

        # Complete in order
        progress.milestones["boot"].complete()
        assert progress.milestones["boot"].status == MilestoneStatus.COMPLETED
        assert progress.milestones["navigate"].status == MilestoneStatus.NOT_STARTED

        progress.milestones["navigate"].complete()
        assert progress.milestones["navigate"].status == MilestoneStatus.COMPLETED


# =============================================================================
# Goal and Plan Workflow Tests
# =============================================================================

class TestGoalPlanWorkflow:
    """Tests for goal and plan workflows."""

    def test_create_navigation_goal(self):
        """Workflow: Create and inspect navigation goal."""
        goal = Goal.reach_location(area_id=0x29, x=200, y=200)

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters['x'] == 200
        assert goal.parameters['y'] == 200

    def test_create_plan_with_actions(self):
        """Workflow: Create plan with multiple actions."""
        goal = Goal.reach_location(area_id=0x29, x=200, y=200)

        actions = [
            Action(name="move_right", description="Move right"),
            Action(name="move_down", description="Move down"),
            Action(name="verify", description="Verify position"),
        ]

        plan = Plan(goal=goal, actions=actions)

        assert plan.status == PlanStatus.NOT_STARTED
        assert len(plan.actions) == 3

    def test_plan_execution_flow(self):
        """Workflow: Execute plan step by step."""
        goal = Goal.reach_location(area_id=0x29, x=200, y=200)
        actions = [
            Action(name="step1", description="First step"),
            Action(name="step2", description="Second step"),
        ]
        plan = Plan(goal=goal, actions=actions)

        # Start plan
        plan.status = PlanStatus.IN_PROGRESS
        assert plan.current_action_index == 0

        # Advance through actions
        plan.advance()
        assert plan.current_action_index == 1

        plan.advance()
        assert plan.current_action is None  # Past end


# =============================================================================
# Black Screen Recovery Workflow Tests
# =============================================================================

class TestBlackScreenWorkflow:
    """Tests for black screen detection and recovery."""

    def test_detect_black_screen(self):
        """Workflow: Detect black screen condition."""
        # is_black_screen is true when inidisp=0x80 AND mode in (0x06, 0x07)
        states = [
            _snapshot(inidisp=0x0F, mode=0x09),       # Normal
            _snapshot(inidisp=0x80, mode=0x09),       # Screen blanked but wrong mode
            _snapshot(inidisp=0x80, mode=0x06),       # Black screen (transition)
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert not parsed[0].is_black_screen
        assert not parsed[1].is_black_screen  # Mode not 0x06/0x07
        assert parsed[2].is_black_screen

    def test_black_screen_recovery(self):
        """Workflow: Recover from black screen."""
        states = [
            _snapshot(inidisp=0x80, mode=0x06),       # Black during transition
            _snapshot(inidisp=0x80, mode=0x06),       # Still black
            _snapshot(inidisp=0x0F, mode=0x09),       # Recovered
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        assert parsed[0].is_black_screen
        assert not parsed[2].is_black_screen
        assert parsed[2].phase == GamePhase.OVERWORLD


# =============================================================================
# End-to-End Scenario Tests
# =============================================================================

class TestEndToEndScenarios:
    """End-to-end scenario tests."""

    def test_boot_navigate_menu_scenario(self):
        """Full scenario: Boot, navigate, open menu."""
        states = [
            _snapshot(mode=0x00),                       # Boot
            _snapshot(mode=0x01),                       # Title
            _snapshot(mode=0x09, area=0x18),            # Overworld (start area)
            _snapshot(mode=0x09, area=0x18, link_x=128),
            _snapshot(mode=0x09, area=0x28, link_x=100),  # Different area
            _snapshot(mode=0x0E),                       # Menu opened
            _snapshot(mode=0x09, area=0x28),            # Menu closed
        ]

        parser = GameStateParser()

        # Track phases
        phases = [parser.parse(s).phase for s in states]
        assert GamePhase.BOOT in phases
        assert GamePhase.TITLE_SCREEN in phases
        assert GamePhase.OVERWORLD in phases
        assert GamePhase.MENU in phases

    def test_explore_dungeon_scenario(self):
        """Full scenario: Enter and explore dungeon."""
        states = [
            _snapshot(mode=0x09, indoors=False, area=0x29),  # Overworld
            _snapshot(mode=0x06, indoors=False),              # Entering
            _snapshot(mode=0x07, indoors=True, room=0x10),    # Dungeon room 1
            _snapshot(mode=0x07, indoors=True, room=0x11),    # Dungeon room 2
            _snapshot(mode=0x07, indoors=True, room=0x12),    # Dungeon room 3
            _snapshot(mode=0x06, indoors=True),               # Exiting
            _snapshot(mode=0x09, indoors=False, area=0x29),   # Back outside
        ]

        parser = GameStateParser()

        # Track indoor state
        indoor_states = [parser.parse(s).is_indoors for s in states]
        assert not indoor_states[0]  # Start outside
        assert indoor_states[3]       # In dungeon
        assert not indoor_states[-1]  # Back outside

    def test_combat_heal_scenario(self):
        """Full scenario: Combat with damage and healing."""
        states = [
            _snapshot(health=24, link_state=0x00),  # Full health, standing
            _snapshot(health=24, link_state=0x11),  # Attack!
            _snapshot(health=24, link_state=0x00),  # End attack
            _snapshot(health=16, link_state=0x04),  # Hit! Knocked back
            _snapshot(health=16, link_state=0x00),  # Recover
            _snapshot(health=16, mode=0x0E),        # Open menu (heal)
            _snapshot(health=24, mode=0x09),        # Healed!
        ]

        parser = GameStateParser()
        parsed = [parser.parse(s) for s in states]

        # Verify combat sequence
        assert parsed[1].is_combat  # Attacking
        assert parsed[3].is_combat  # Knocked back

        # Verify health changes
        assert parsed[0].health_percent == 1.0
        assert parsed[4].health_percent < 1.0
        assert parsed[6].health_percent == 1.0  # Healed

    def test_navigation_with_obstacles_scenario(self):
        """Full scenario: Navigate around obstacles."""
        # Create map with obstacle
        map_data = bytearray([TileType.WALKABLE] * 64)
        map_data[3 + 3 * 8] = TileType.SOLID  # Obstacle at (3, 3)
        cmap = CollisionMap(data=bytes(map_data), width=8, height=8)

        pf = Pathfinder()
        result = pf.find_path((0, 3), (7, 3), collision_map=cmap)

        assert result.success is True
        assert (3, 3) not in result.path  # Avoided obstacle


# =============================================================================
# Progress Tracking Workflow Tests
# =============================================================================

class TestProgressTrackingWorkflow:
    """Tests for progress tracking workflows."""

    def test_track_frame_count(self):
        """Workflow: Track total frames played."""
        progress = CampaignProgress()

        progress.total_frames_played += 60   # 1 second
        progress.total_frames_played += 300  # 5 more seconds

        assert progress.total_frames_played == 360

    def test_track_iterations(self):
        """Workflow: Track iteration count."""
        progress = CampaignProgress()

        for _ in range(5):
            progress.iterations_completed += 1

        assert progress.iterations_completed == 5

    def test_track_transitions(self):
        """Workflow: Track transition count."""
        progress = CampaignProgress()

        # Simulate transitions
        transition_count = 0
        states = [0x09, 0x06, 0x07, 0x06, 0x09]  # Modes

        for i in range(1, len(states)):
            if states[i] == 0x06:  # Transition mode
                transition_count += 1

        progress.transitions_completed = transition_count
        assert progress.transitions_completed == 2
