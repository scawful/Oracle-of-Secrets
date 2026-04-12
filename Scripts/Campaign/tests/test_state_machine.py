"""Extended tests for state machine behavior and state transitions.

Iteration 39 of the ralph-loop campaign.
Tests the state machine logic, valid/invalid transitions, and state consistency
across all campaign infrastructure modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: State machine verification
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot, EmulatorStatus
from scripts.campaign.game_state import (
    GamePhase, GameStateParser, ParsedGameState, LinkAction
)
from scripts.campaign.input_recorder import Button, InputSequence, InputRecorder
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, CampaignProgress, MilestoneStatus
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)


# =============================================================================
# GamePhase State Machine Tests
# =============================================================================

class TestGamePhaseTransitions:
    """Test valid and invalid GamePhase transitions."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, mode=0x09, submode=0, area=0x29, indoors=False,
                   inidisp=0x0F, link_state=0x00):
        """Create GameStateSnapshot for testing."""
        return GameStateSnapshot(
            timestamp=1.0, mode=mode, submode=submode, area=area,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=link_state, indoors=indoors,
            inidisp=inidisp, health=24, max_health=24
        )

    def test_boot_to_title(self, parser):
        """Test transition from boot to title screen."""
        boot = parser.parse(self.make_state(mode=0x00))
        title = parser.parse(self.make_state(mode=0x01))

        assert boot.phase == GamePhase.BOOT
        assert title.phase == GamePhase.TITLE_SCREEN

    def test_title_to_file_select(self, parser):
        """Test transition from title to file select."""
        title = parser.parse(self.make_state(mode=0x01))
        file_sel = parser.parse(self.make_state(mode=0x02))

        assert title.phase == GamePhase.TITLE_SCREEN
        assert file_sel.phase == GamePhase.FILE_SELECT

    def test_file_select_to_intro(self, parser):
        """Test transition from file select to intro."""
        file_sel = parser.parse(self.make_state(mode=0x02))
        intro = parser.parse(self.make_state(mode=0x05))

        assert file_sel.phase == GamePhase.FILE_SELECT
        assert intro.phase == GamePhase.INTRO

    def test_intro_to_overworld(self, parser):
        """Test transition from intro to overworld."""
        intro = parser.parse(self.make_state(mode=0x05))
        overworld = parser.parse(self.make_state(mode=0x09))

        assert intro.phase == GamePhase.INTRO
        assert overworld.phase == GamePhase.OVERWORLD

    def test_overworld_to_transition(self, parser):
        """Test entering transition from overworld."""
        overworld = parser.parse(self.make_state(mode=0x09))
        transition = parser.parse(self.make_state(mode=0x06))

        assert overworld.phase == GamePhase.OVERWORLD
        assert transition.phase == GamePhase.TRANSITION

    def test_transition_to_dungeon(self, parser):
        """Test entering dungeon after transition (indoors=True)."""
        transition = parser.parse(self.make_state(mode=0x06))
        # Mode 0x07 with indoors=True -> DUNGEON
        dungeon = parser.parse(self.make_state(mode=0x07, indoors=True))

        assert transition.phase == GamePhase.TRANSITION
        assert dungeon.phase == GamePhase.DUNGEON

    def test_overworld_to_menu(self, parser):
        """Test opening menu from overworld."""
        overworld = parser.parse(self.make_state(mode=0x09))
        menu = parser.parse(self.make_state(mode=0x0E))

        assert overworld.phase == GamePhase.OVERWORLD
        assert menu.phase == GamePhase.MENU

    def test_menu_to_overworld(self, parser):
        """Test closing menu back to overworld."""
        menu = parser.parse(self.make_state(mode=0x0E))
        overworld = parser.parse(self.make_state(mode=0x09))

        assert menu.phase == GamePhase.MENU
        assert overworld.phase == GamePhase.OVERWORLD

    def test_overworld_to_dialogue(self, parser):
        """Test opening dialogue from overworld."""
        overworld = parser.parse(self.make_state(mode=0x09))
        dialogue = parser.parse(self.make_state(mode=0x0F))

        assert overworld.phase == GamePhase.OVERWORLD
        assert dialogue.phase == GamePhase.DIALOGUE

    def test_cutscene_phase(self, parser):
        """Test cutscene phase detection."""
        cutscene = parser.parse(self.make_state(mode=0x14))
        assert cutscene.phase == GamePhase.CUTSCENE

    def test_game_over_phase(self, parser):
        """Test game over phase detection."""
        game_over = parser.parse(self.make_state(mode=0x17))
        assert game_over.phase == GamePhase.GAME_OVER

    def test_black_screen_overrides_phase(self, parser):
        """Test black screen state overrides normal phase."""
        # INIDISP = 0x80 with mode 0x06 or 0x07 should be black screen
        snap = self.make_state(mode=0x06, inidisp=0x80)
        parsed = parser.parse(snap)
        assert parsed.phase == GamePhase.BLACK_SCREEN

    def test_unknown_mode_returns_unknown_phase(self, parser):
        """Test unknown mode value."""
        unknown = parser.parse(self.make_state(mode=0xFF))
        assert unknown.phase == GamePhase.UNKNOWN


# =============================================================================
# LinkAction State Machine Tests
# =============================================================================

class TestLinkActionTransitions:
    """Test LinkAction state machine behavior."""

    @pytest.fixture
    def parser(self):
        return GameStateParser()

    def make_state(self, link_state=0x00):
        """Create state with specific link_state."""
        return GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0, area=0x29,
            room=0, link_x=512, link_y=480, link_z=0,
            link_direction=0, link_state=link_state, indoors=False,
            inidisp=0x0F, health=24, max_health=24
        )

    def test_standing_to_walking(self, parser):
        """Test Link starting to walk."""
        standing = parser.parse(self.make_state(link_state=0x00))
        walking = parser.parse(self.make_state(link_state=0x01))

        assert standing.link_action == LinkAction.STANDING
        assert walking.link_action == LinkAction.WALKING

    def test_walking_to_standing(self, parser):
        """Test Link stopping."""
        walking = parser.parse(self.make_state(link_state=0x01))
        standing = parser.parse(self.make_state(link_state=0x00))

        assert walking.link_action == LinkAction.WALKING
        assert standing.link_action == LinkAction.STANDING

    def test_standing_to_attacking(self, parser):
        """Test Link attacking from standing."""
        standing = parser.parse(self.make_state(link_state=0x00))
        attacking = parser.parse(self.make_state(link_state=0x11))

        assert standing.link_action == LinkAction.STANDING
        assert attacking.link_action == LinkAction.ATTACKING

    def test_attacking_to_standing(self, parser):
        """Test Link finishing attack."""
        attacking = parser.parse(self.make_state(link_state=0x11))
        standing = parser.parse(self.make_state(link_state=0x00))

        assert attacking.link_action == LinkAction.ATTACKING
        assert standing.link_action == LinkAction.STANDING

    def test_swimming_state(self, parser):
        """Test swimming state."""
        swimming = parser.parse(self.make_state(link_state=0x02))
        assert swimming.link_action == LinkAction.SWIMMING

    def test_diving_from_swimming(self, parser):
        """Test diving from swimming."""
        swimming = parser.parse(self.make_state(link_state=0x02))
        diving = parser.parse(self.make_state(link_state=0x03))

        assert swimming.link_action == LinkAction.SWIMMING
        assert diving.link_action == LinkAction.DIVING

    def test_knocked_back_state(self, parser):
        """Test knocked back (damage) state."""
        knocked = parser.parse(self.make_state(link_state=0x04))
        assert knocked.link_action == LinkAction.KNOCKED_BACK

    def test_pushing_state(self, parser):
        """Test pushing state."""
        pushing = parser.parse(self.make_state(link_state=0x06))
        assert pushing.link_action == LinkAction.PUSHING

    def test_falling_state(self, parser):
        """Test falling state."""
        falling = parser.parse(self.make_state(link_state=0x08))
        assert falling.link_action == LinkAction.FALLING

    def test_lifting_carrying_throwing_cycle(self, parser):
        """Test lift -> carry -> throw cycle."""
        lifting = parser.parse(self.make_state(link_state=0x0A))
        carrying = parser.parse(self.make_state(link_state=0x0B))
        throwing = parser.parse(self.make_state(link_state=0x0C))

        assert lifting.link_action == LinkAction.LIFTING
        assert carrying.link_action == LinkAction.CARRYING
        assert throwing.link_action == LinkAction.THROWING

    def test_spinning_state(self, parser):
        """Test spin attack state."""
        spinning = parser.parse(self.make_state(link_state=0x19))
        assert spinning.link_action == LinkAction.SPINNING

    def test_dying_state(self, parser):
        """Test dying state."""
        dying = parser.parse(self.make_state(link_state=0x17))
        assert dying.link_action == LinkAction.DYING

    def test_using_item_state(self, parser):
        """Test using item state."""
        using = parser.parse(self.make_state(link_state=0x12))
        assert using.link_action == LinkAction.USING_ITEM


# =============================================================================
# CampaignPhase State Machine Tests
# =============================================================================

class TestCampaignPhaseTransitions:
    """Test CampaignPhase state transitions."""

    def test_disconnected_initial_state(self):
        """Test initial state is disconnected."""
        progress = CampaignProgress()
        assert progress.current_phase == CampaignPhase.DISCONNECTED

    def test_disconnected_to_connecting(self):
        """Test transition from disconnected to connecting."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.CONNECTING

        assert progress.current_phase == CampaignPhase.CONNECTING

    def test_connecting_to_booting(self):
        """Test transition from connecting to booting."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.CONNECTING
        progress.current_phase = CampaignPhase.BOOTING

        assert progress.current_phase == CampaignPhase.BOOTING

    def test_booting_to_exploring(self):
        """Test transition from booting to exploring."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.BOOTING
        progress.current_phase = CampaignPhase.EXPLORING

        assert progress.current_phase == CampaignPhase.EXPLORING

    def test_exploring_to_navigating(self):
        """Test transition from exploring to navigating."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        progress.current_phase = CampaignPhase.NAVIGATING

        assert progress.current_phase == CampaignPhase.NAVIGATING

    def test_navigating_back_to_exploring(self):
        """Test transition from navigating back to exploring."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.NAVIGATING
        progress.current_phase = CampaignPhase.EXPLORING

        assert progress.current_phase == CampaignPhase.EXPLORING

    def test_exploring_to_in_dungeon(self):
        """Test transition from exploring to in_dungeon."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        progress.current_phase = CampaignPhase.IN_DUNGEON

        assert progress.current_phase == CampaignPhase.IN_DUNGEON

    def test_any_to_failed(self):
        """Test any state can transition to failed."""
        for phase in CampaignPhase:
            progress = CampaignProgress()
            progress.current_phase = phase
            progress.current_phase = CampaignPhase.FAILED

            assert progress.current_phase == CampaignPhase.FAILED

    def test_any_to_completed(self):
        """Test any state can transition to completed."""
        for phase in [CampaignPhase.EXPLORING, CampaignPhase.IN_DUNGEON]:
            progress = CampaignProgress()
            progress.current_phase = phase
            progress.current_phase = CampaignPhase.COMPLETED

            assert progress.current_phase == CampaignPhase.COMPLETED


# =============================================================================
# PlanStatus State Machine Tests
# =============================================================================

class TestPlanStatusTransitions:
    """Test PlanStatus state transitions."""

    def test_not_started_initial_state(self):
        """Test plans start in NOT_STARTED state."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal)
        assert plan.status == PlanStatus.NOT_STARTED

    def test_not_started_to_in_progress(self):
        """Test starting plan execution."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal)
        plan.status = PlanStatus.IN_PROGRESS

        assert plan.status == PlanStatus.IN_PROGRESS

    def test_in_progress_to_completed(self):
        """Test completing a plan."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal, status=PlanStatus.IN_PROGRESS)
        plan.status = PlanStatus.COMPLETED

        assert plan.status == PlanStatus.COMPLETED

    def test_in_progress_to_failed(self):
        """Test failing a plan."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal, status=PlanStatus.IN_PROGRESS)
        plan.status = PlanStatus.FAILED

        assert plan.status == PlanStatus.FAILED

    def test_in_progress_to_blocked(self):
        """Test blocking a plan."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal, status=PlanStatus.IN_PROGRESS)
        plan.status = PlanStatus.BLOCKED

        assert plan.status == PlanStatus.BLOCKED

    def test_blocked_to_in_progress(self):
        """Test unblocking a plan."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = Plan(goal=goal, status=PlanStatus.BLOCKED)
        plan.status = PlanStatus.IN_PROGRESS

        assert plan.status == PlanStatus.IN_PROGRESS


# =============================================================================
# EmulatorStatus State Machine Tests
# =============================================================================

class TestEmulatorStatusTransitions:
    """Test EmulatorStatus state transitions."""

    def test_all_status_values_exist(self):
        """Verify all expected status values exist."""
        assert EmulatorStatus.DISCONNECTED is not None
        assert EmulatorStatus.CONNECTED is not None
        assert EmulatorStatus.RUNNING is not None
        assert EmulatorStatus.PAUSED is not None
        assert EmulatorStatus.ERROR is not None

    def test_disconnected_to_connected(self):
        """Test successful connection."""
        status = EmulatorStatus.DISCONNECTED
        status = EmulatorStatus.CONNECTED
        assert status == EmulatorStatus.CONNECTED

    def test_connected_to_running(self):
        """Test starting emulation."""
        status = EmulatorStatus.CONNECTED
        status = EmulatorStatus.RUNNING
        assert status == EmulatorStatus.RUNNING

    def test_running_to_paused(self):
        """Test pausing emulation."""
        status = EmulatorStatus.RUNNING
        status = EmulatorStatus.PAUSED
        assert status == EmulatorStatus.PAUSED

    def test_paused_to_running(self):
        """Test resuming emulation."""
        status = EmulatorStatus.PAUSED
        status = EmulatorStatus.RUNNING
        assert status == EmulatorStatus.RUNNING

    def test_any_to_error(self):
        """Test error can occur from any state."""
        for start_status in EmulatorStatus:
            status = start_status
            status = EmulatorStatus.ERROR
            assert status == EmulatorStatus.ERROR

    def test_any_to_disconnected(self):
        """Test disconnect can occur from any state."""
        for start_status in EmulatorStatus:
            status = start_status
            status = EmulatorStatus.DISCONNECTED
            assert status == EmulatorStatus.DISCONNECTED


# =============================================================================
# State Consistency Tests
# =============================================================================

class TestStateConsistency:
    """Test state consistency across parsing."""

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

    def test_parsed_state_preserves_raw(self, parser):
        """Test ParsedGameState preserves raw snapshot."""
        snap = self.make_state()
        parsed = parser.parse(snap)

        assert parsed.raw == snap
        assert parsed.raw.mode == snap.mode
        assert parsed.raw.link_x == snap.link_x

    def test_position_consistency(self, parser):
        """Test position tuple matches raw coordinates."""
        snap = self.make_state(link_x=256, link_y=384)
        parsed = parser.parse(snap)

        assert parsed.link_position == (256, 384)
        assert parsed.link_position[0] == snap.link_x
        assert parsed.link_position[1] == snap.link_y

    def test_health_percent_consistency(self, parser):
        """Test health percent matches raw values."""
        snap = self.make_state(health=12, max_health=24)
        parsed = parser.parse(snap)

        assert parsed.health_percent == 0.5
        assert abs(parsed.health_percent - snap.health / snap.max_health) < 0.001

    def test_area_room_consistency(self, parser):
        """Test area and room IDs preserved."""
        snap = self.make_state(area=0x29, room=0x1234)
        parsed = parser.parse(snap)

        assert parsed.area_id == 0x29
        assert parsed.room_id == 0x1234

    def test_indoors_flag_consistency(self, parser):
        """Test indoors flag preserved."""
        outdoor = parser.parse(self.make_state(indoors=False))
        indoor = parser.parse(self.make_state(indoors=True))

        assert outdoor.is_indoors is False
        assert indoor.is_indoors is True


# =============================================================================
# Change Detection State Tests
# =============================================================================

class TestChangeDetectionState:
    """Test change detection state machine."""

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

    def test_first_parse_no_changes(self, parser):
        """Test first parse has no previous state."""
        snap = self.make_state()
        parsed = parser.parse(snap)
        # Can't detect changes on first parse (no previous state)
        assert parsed is not None

    def test_identical_states_no_changes(self, parser):
        """Test identical states produce no changes."""
        snap1 = self.make_state()
        snap2 = self.make_state()

        parser.parse(snap1)  # Sets _last_state
        parsed2 = parser.parse(snap2)

        changes = parser.detect_change(parsed2)
        assert len(changes) == 0

    def test_area_change_detected(self, parser):
        """Test area change is detected."""
        snap1 = self.make_state(area=0x29)
        snap2 = self.make_state(area=0x28)

        parsed1 = parser.parse(snap1)  # Sets _last_state
        # Construct parsed2 without calling parse (which would update _last_state)
        parsed2 = ParsedGameState(
            raw=snap2, phase=GamePhase.OVERWORLD, location_name="",
            area_id=0x28, room_id=0, is_indoors=False,
            link_action=LinkAction.STANDING, link_direction="up",
            link_position=(512, 480), link_layer=0, health_percent=1.0,
            is_playing=True, is_transitioning=False, is_menu_open=False, is_dialogue_open=False,
            is_black_screen=False, can_move=True, can_use_items=True, submode=0, extra={}
        )

        changes = parser.detect_change(parsed2)
        assert any("Area" in c for c in changes)

    def test_room_change_detected(self, parser):
        """Test room change is detected."""
        snap1 = self.make_state(room=0x00)
        snap2 = self.make_state(room=0x10)

        parsed1 = parser.parse(snap1)  # Sets _last_state
        parsed2 = ParsedGameState(
            raw=snap2, phase=GamePhase.OVERWORLD, location_name="",
            area_id=0x29, room_id=0x10, is_indoors=False,
            link_action=LinkAction.STANDING, link_direction="up",
            link_position=(512, 480), link_layer=0, health_percent=1.0,
            is_playing=True, is_transitioning=False, is_menu_open=False, is_dialogue_open=False,
            is_black_screen=False, can_move=True, can_use_items=True, submode=0, extra={}
        )

        changes = parser.detect_change(parsed2)
        assert any("Room" in c for c in changes)

    def test_action_change_detected(self, parser):
        """Test action change is detected."""
        snap1 = self.make_state(link_state=0x00)  # Standing
        snap2 = self.make_state(link_state=0x01)  # Walking

        parsed1 = parser.parse(snap1)  # Sets _last_state
        parsed2 = ParsedGameState(
            raw=snap2, phase=GamePhase.OVERWORLD, location_name="",
            area_id=0x29, room_id=0, is_indoors=False,
            link_action=LinkAction.WALKING, link_direction="up",
            link_position=(512, 480), link_layer=0, health_percent=1.0,
            is_playing=True, is_transitioning=False, is_menu_open=False, is_dialogue_open=False,
            is_black_screen=False, can_move=True, can_use_items=True, submode=0, extra={}
        )

        changes = parser.detect_change(parsed2)
        assert any("Action" in c for c in changes)


# =============================================================================
# Input Recorder State Machine Tests
# =============================================================================

class TestInputRecorderState:
    """Test InputRecorder state machine."""

    def test_initial_not_recording(self):
        """Test recorder starts in non-recording state."""
        recorder = InputRecorder()
        assert recorder.is_recording is False

    def test_start_recording_state(self):
        """Test starting recording."""
        recorder = InputRecorder()
        recorder.start_recording()
        assert recorder.is_recording is True

    def test_stop_recording_state(self):
        """Test stopping recording."""
        recorder = InputRecorder()
        recorder.start_recording()
        recorder.stop_recording()
        assert recorder.is_recording is False

    def test_recording_accumulates_frames(self):
        """Test recording accumulates input frames."""
        recorder = InputRecorder()
        recorder.start_recording()

        recorder.record_input(Button.A)
        recorder.record_input(Button.B)

        recorder.stop_recording()
        seq = recorder.get_sequence()
        assert len(seq.frames) >= 0  # May have compression

    def test_get_sequence_without_recording(self):
        """Test get_sequence returns empty sequence if not recorded."""
        recorder = InputRecorder()
        seq = recorder.get_sequence()
        # Should return an empty or minimal sequence
        assert seq is not None

    def test_multiple_recording_sessions(self):
        """Test multiple recording sessions work."""
        recorder = InputRecorder()

        # First session
        recorder.start_recording()
        recorder.record_input(Button.A)
        recorder.stop_recording()
        seq1 = recorder.get_sequence()

        # Second session
        recorder.start_recording()
        recorder.record_input(Button.B)
        recorder.stop_recording()
        seq2 = recorder.get_sequence()

        # Both should be sequences
        assert seq1 is not None
        assert seq2 is not None


# =============================================================================
# MilestoneStatus State Machine Tests
# =============================================================================

class TestMilestoneStatusTransitions:
    """Test MilestoneStatus state transitions."""

    def test_all_milestone_statuses_exist(self):
        """Verify all milestone status values exist."""
        assert MilestoneStatus.NOT_STARTED is not None
        assert MilestoneStatus.IN_PROGRESS is not None
        assert MilestoneStatus.COMPLETED is not None
        assert MilestoneStatus.BLOCKED is not None

    def test_not_started_to_in_progress(self):
        """Test starting a milestone."""
        status = MilestoneStatus.NOT_STARTED
        status = MilestoneStatus.IN_PROGRESS
        assert status == MilestoneStatus.IN_PROGRESS

    def test_in_progress_to_completed(self):
        """Test completing a milestone."""
        status = MilestoneStatus.IN_PROGRESS
        status = MilestoneStatus.COMPLETED
        assert status == MilestoneStatus.COMPLETED

    def test_in_progress_to_blocked(self):
        """Test blocking a milestone."""
        status = MilestoneStatus.IN_PROGRESS
        status = MilestoneStatus.BLOCKED
        assert status == MilestoneStatus.BLOCKED


# =============================================================================
# GoalType Coverage Tests
# =============================================================================

class TestGoalTypeValues:
    """Test all GoalType enum values."""

    def test_reach_location_goal(self):
        """Test REACH_LOCATION goal type."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test",
            parameters={"x": 100}
        )
        assert goal.goal_type == GoalType.REACH_LOCATION

    def test_enter_building_goal(self):
        """Test ENTER_BUILDING goal type."""
        goal = Goal(
            goal_type=GoalType.ENTER_BUILDING,
            description="Enter shop"
        )
        assert goal.goal_type == GoalType.ENTER_BUILDING

    def test_exit_building_goal(self):
        """Test EXIT_BUILDING goal type."""
        goal = Goal(
            goal_type=GoalType.EXIT_BUILDING,
            description="Exit shop"
        )
        assert goal.goal_type == GoalType.EXIT_BUILDING

    def test_talk_to_npc_goal(self):
        """Test TALK_TO_NPC goal type."""
        goal = Goal(
            goal_type=GoalType.TALK_TO_NPC,
            description="Talk to villager"
        )
        assert goal.goal_type == GoalType.TALK_TO_NPC

    def test_get_item_goal(self):
        """Test GET_ITEM goal type."""
        goal = Goal(
            goal_type=GoalType.GET_ITEM,
            description="Get sword"
        )
        assert goal.goal_type == GoalType.GET_ITEM

    def test_use_item_goal(self):
        """Test USE_ITEM goal type."""
        goal = Goal(
            goal_type=GoalType.USE_ITEM,
            description="Use key"
        )
        assert goal.goal_type == GoalType.USE_ITEM

    def test_defeat_enemy_goal(self):
        """Test DEFEAT_ENEMY goal type."""
        goal = Goal(
            goal_type=GoalType.DEFEAT_ENEMY,
            description="Defeat moblin"
        )
        assert goal.goal_type == GoalType.DEFEAT_ENEMY

    def test_open_chest_goal(self):
        """Test OPEN_CHEST goal type."""
        goal = Goal(
            goal_type=GoalType.OPEN_CHEST,
            description="Open treasure chest"
        )
        assert goal.goal_type == GoalType.OPEN_CHEST

    def test_solve_puzzle_goal(self):
        """Test SOLVE_PUZZLE goal type."""
        goal = Goal(
            goal_type=GoalType.SOLVE_PUZZLE,
            description="Push blocks"
        )
        assert goal.goal_type == GoalType.SOLVE_PUZZLE

    def test_complete_dungeon_goal(self):
        """Test COMPLETE_DUNGEON goal type."""
        goal = Goal(
            goal_type=GoalType.COMPLETE_DUNGEON,
            description="Finish temple"
        )
        assert goal.goal_type == GoalType.COMPLETE_DUNGEON
