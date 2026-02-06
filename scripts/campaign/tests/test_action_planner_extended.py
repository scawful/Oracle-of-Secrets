"""Extended tests for action_planner module.

Iteration 33 - Comprehensive action planner testing.
Covers GoalType/PlanStatus enums, Goal factory methods,
Action conditions, Plan execution flow, ActionPlanner
plan creation and execution, and pre-built goals.
"""

import pytest
from unittest.mock import Mock, MagicMock, patch, call
import sys
from pathlib import Path

project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.action_planner import (
    GoalType,
    PlanStatus,
    Goal,
    Action,
    Plan,
    ActionPlanner,
    goal_reach_village_center,
    goal_reach_dungeon1_entrance,
    goal_complete_dungeon1,
)
from scripts.campaign.game_state import GamePhase, ParsedGameState, LinkAction
from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.input_recorder import InputSequence, Button


# =============================================================================
# GoalType Enum Extended Tests
# =============================================================================

class TestGoalTypeEnumValues:
    """Test GoalType enum value properties."""

    def test_all_goal_types_unique(self):
        """All goal type values should be distinct."""
        values = [gt.value for gt in GoalType]
        assert len(values) == len(set(values))

    def test_reach_location_exists(self):
        """REACH_LOCATION is defined."""
        assert GoalType.REACH_LOCATION is not None

    def test_enter_building_exists(self):
        """ENTER_BUILDING is defined."""
        assert GoalType.ENTER_BUILDING is not None

    def test_exit_building_exists(self):
        """EXIT_BUILDING is defined."""
        assert GoalType.EXIT_BUILDING is not None

    def test_talk_to_npc_exists(self):
        """TALK_TO_NPC is defined."""
        assert GoalType.TALK_TO_NPC is not None

    def test_get_item_exists(self):
        """GET_ITEM is defined."""
        assert GoalType.GET_ITEM is not None

    def test_use_item_exists(self):
        """USE_ITEM is defined."""
        assert GoalType.USE_ITEM is not None

    def test_defeat_enemy_exists(self):
        """DEFEAT_ENEMY is defined."""
        assert GoalType.DEFEAT_ENEMY is not None

    def test_open_chest_exists(self):
        """OPEN_CHEST is defined."""
        assert GoalType.OPEN_CHEST is not None

    def test_solve_puzzle_exists(self):
        """SOLVE_PUZZLE is defined."""
        assert GoalType.SOLVE_PUZZLE is not None

    def test_complete_dungeon_exists(self):
        """COMPLETE_DUNGEON is defined."""
        assert GoalType.COMPLETE_DUNGEON is not None

    def test_goal_type_count(self):
        """Expected number of goal types."""
        all_types = list(GoalType)
        assert len(all_types) == 10


class TestGoalTypeMembership:
    """Test GoalType membership and comparison."""

    def test_is_member_of_enum(self):
        """Goal types are members of GoalType."""
        assert GoalType.REACH_LOCATION in GoalType
        assert GoalType.DEFEAT_ENEMY in GoalType

    def test_equality_same_type(self):
        """Same goal type equals itself."""
        assert GoalType.REACH_LOCATION == GoalType.REACH_LOCATION

    def test_inequality_different_types(self):
        """Different goal types are not equal."""
        assert GoalType.REACH_LOCATION != GoalType.ENTER_BUILDING


# =============================================================================
# PlanStatus Enum Extended Tests
# =============================================================================

class TestPlanStatusEnumValues:
    """Test PlanStatus enum value properties."""

    def test_all_statuses_unique(self):
        """All status values should be distinct."""
        values = [ps.value for ps in PlanStatus]
        assert len(values) == len(set(values))

    def test_not_started_exists(self):
        """NOT_STARTED is defined."""
        assert PlanStatus.NOT_STARTED is not None

    def test_in_progress_exists(self):
        """IN_PROGRESS is defined."""
        assert PlanStatus.IN_PROGRESS is not None

    def test_completed_exists(self):
        """COMPLETED is defined."""
        assert PlanStatus.COMPLETED is not None

    def test_failed_exists(self):
        """FAILED is defined."""
        assert PlanStatus.FAILED is not None

    def test_blocked_exists(self):
        """BLOCKED is defined."""
        assert PlanStatus.BLOCKED is not None

    def test_status_count(self):
        """Expected number of statuses."""
        all_statuses = list(PlanStatus)
        assert len(all_statuses) == 5


# =============================================================================
# Goal Factory Methods Extended Tests
# =============================================================================

class TestGoalReachLocation:
    """Test Goal.reach_location factory method."""

    def test_creates_correct_type(self):
        """Creates REACH_LOCATION goal type."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert goal.goal_type == GoalType.REACH_LOCATION

    def test_stores_area_id(self):
        """Stores area_id in parameters."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert goal.parameters["area_id"] == 0x29

    def test_stores_coordinates(self):
        """Stores x and y coordinates."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert goal.parameters["x"] == 512
        assert goal.parameters["y"] == 480

    def test_default_tolerance(self):
        """Default tolerance is 16."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert goal.parameters["tolerance"] == 16

    def test_custom_tolerance(self):
        """Custom tolerance is stored."""
        goal = Goal.reach_location(0x29, 512, 480, tolerance=32)
        assert goal.parameters["tolerance"] == 32

    def test_description_contains_coordinates(self):
        """Description mentions coordinates."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert "512" in goal.description
        assert "480" in goal.description

    def test_description_contains_area_hex(self):
        """Description contains area ID in hex."""
        goal = Goal.reach_location(0x29, 512, 480)
        assert "29" in goal.description.upper()

    def test_zero_coordinates(self):
        """Handles zero coordinates."""
        goal = Goal.reach_location(0x00, 0, 0)
        assert goal.parameters["x"] == 0
        assert goal.parameters["y"] == 0

    def test_large_coordinates(self):
        """Handles large coordinates."""
        goal = Goal.reach_location(0xFF, 4096, 4096)
        assert goal.parameters["x"] == 4096
        assert goal.parameters["y"] == 4096


class TestGoalEnterBuilding:
    """Test Goal.enter_building factory method."""

    def test_creates_correct_type(self):
        """Creates ENTER_BUILDING goal type."""
        goal = Goal.enter_building(0x12)
        assert goal.goal_type == GoalType.ENTER_BUILDING

    def test_stores_entrance_id(self):
        """Stores entrance_id in parameters."""
        goal = Goal.enter_building(0x12)
        assert goal.parameters["entrance_id"] == 0x12

    def test_description_contains_entrance_hex(self):
        """Description contains entrance ID in hex."""
        goal = Goal.enter_building(0x12)
        assert "12" in goal.description.upper()


class TestGoalExitBuilding:
    """Test Goal.exit_building factory method."""

    def test_creates_correct_type(self):
        """Creates EXIT_BUILDING goal type."""
        goal = Goal.exit_building()
        assert goal.goal_type == GoalType.EXIT_BUILDING

    def test_empty_parameters(self):
        """Exit building has no specific parameters."""
        goal = Goal.exit_building()
        assert len(goal.parameters) == 0

    def test_has_description(self):
        """Has meaningful description."""
        goal = Goal.exit_building()
        assert len(goal.description) > 0
        assert "exit" in goal.description.lower()


class TestGoalTalkToNpc:
    """Test Goal.talk_to_npc factory method."""

    def test_creates_correct_type(self):
        """Creates TALK_TO_NPC goal type."""
        goal = Goal.talk_to_npc(0x55)
        assert goal.goal_type == GoalType.TALK_TO_NPC

    def test_stores_npc_id(self):
        """Stores npc_id in parameters."""
        goal = Goal.talk_to_npc(0x55)
        assert goal.parameters["npc_id"] == 0x55


class TestGoalGetItem:
    """Test Goal.get_item factory method."""

    def test_creates_correct_type(self):
        """Creates GET_ITEM goal type."""
        goal = Goal.get_item(0x01)
        assert goal.goal_type == GoalType.GET_ITEM

    def test_stores_item_id(self):
        """Stores item_id in parameters."""
        goal = Goal.get_item(0x01)
        assert goal.parameters["item_id"] == 0x01


class TestGoalDefeatEnemy:
    """Test Goal.defeat_enemy factory method."""

    def test_creates_correct_type(self):
        """Creates DEFEAT_ENEMY goal type."""
        goal = Goal.defeat_enemy(0x10)
        assert goal.goal_type == GoalType.DEFEAT_ENEMY

    def test_stores_sprite_id(self):
        """Stores sprite_id in parameters."""
        goal = Goal.defeat_enemy(0x10)
        assert goal.parameters["sprite_id"] == 0x10

    def test_no_sprite_id(self):
        """None sprite_id for generic defeat."""
        goal = Goal.defeat_enemy()
        assert goal.parameters["sprite_id"] is None

    def test_description_with_sprite(self):
        """Description mentions sprite when provided."""
        goal = Goal.defeat_enemy(0x10)
        assert "10" in goal.description.upper()

    def test_description_without_sprite(self):
        """Description is generic without sprite."""
        goal = Goal.defeat_enemy()
        assert "all" in goal.description.lower()


# =============================================================================
# Goal Dataclass Extended Tests
# =============================================================================

class TestGoalDataclass:
    """Test Goal dataclass properties."""

    def test_default_preconditions(self):
        """Default preconditions is empty list."""
        goal = Goal(GoalType.REACH_LOCATION, "Test")
        assert goal.preconditions == []

    def test_default_priority(self):
        """Default priority is 0."""
        goal = Goal(GoalType.REACH_LOCATION, "Test")
        assert goal.priority == 0

    def test_default_parameters(self):
        """Default parameters is empty dict."""
        goal = Goal(GoalType.REACH_LOCATION, "Test")
        assert goal.parameters == {}

    def test_custom_priority(self):
        """Custom priority is stored."""
        goal = Goal(GoalType.REACH_LOCATION, "High priority", priority=10)
        assert goal.priority == 10

    def test_preconditions_list(self):
        """Preconditions can be set."""
        prereq = Goal(GoalType.GET_ITEM, "Get key", {"item_id": 1})
        goal = Goal(GoalType.ENTER_BUILDING, "Enter", preconditions=[prereq])
        assert len(goal.preconditions) == 1
        assert goal.preconditions[0].goal_type == GoalType.GET_ITEM


# =============================================================================
# Action Dataclass Extended Tests
# =============================================================================

class TestActionDataclass:
    """Test Action dataclass properties."""

    def test_default_timeout(self):
        """Default timeout is 600 frames."""
        action = Action(name="test", description="Test action")
        assert action.timeout_frames == 600

    def test_custom_timeout(self):
        """Custom timeout is stored."""
        action = Action(name="test", description="Test", timeout_frames=300)
        assert action.timeout_frames == 300

    def test_default_input_sequence(self):
        """Default input_sequence is None."""
        action = Action(name="test", description="Test")
        assert action.input_sequence is None

    def test_default_condition(self):
        """Default condition is None."""
        action = Action(name="test", description="Test")
        assert action.condition is None

    def test_with_input_sequence(self):
        """Input sequence can be set."""
        seq = InputSequence("test_seq")
        action = Action(name="test", description="Test", input_sequence=seq)
        assert action.input_sequence == seq


class TestActionIsComplete:
    """Test Action.is_complete method."""

    def test_no_condition_returns_true(self):
        """No condition means always complete."""
        action = Action(name="test", description="Test")
        mock_state = Mock()
        assert action.is_complete(mock_state) is True

    def test_condition_true(self):
        """Condition returning True means complete."""
        action = Action(
            name="test",
            description="Test",
            condition=lambda s: True
        )
        assert action.is_complete(Mock()) is True

    def test_condition_false(self):
        """Condition returning False means not complete."""
        action = Action(
            name="test",
            description="Test",
            condition=lambda s: False
        )
        assert action.is_complete(Mock()) is False

    def test_condition_checks_state(self):
        """Condition receives state object."""
        received_states = []
        def capture_state(state):
            received_states.append(state)
            return True

        action = Action(name="test", description="Test", condition=capture_state)
        mock_state = Mock(value=42)
        action.is_complete(mock_state)

        assert len(received_states) == 1
        assert received_states[0].value == 42

    def test_condition_based_on_position(self):
        """Condition can check position."""
        action = Action(
            name="reach_x",
            description="Reach X > 100",
            condition=lambda s: s.link_position[0] > 100
        )

        at_50 = Mock(link_position=(50, 50))
        at_150 = Mock(link_position=(150, 50))

        assert action.is_complete(at_50) is False
        assert action.is_complete(at_150) is True


# =============================================================================
# Plan Dataclass Extended Tests
# =============================================================================

class TestPlanDataclass:
    """Test Plan dataclass properties."""

    @pytest.fixture
    def test_goal(self):
        """Create test goal."""
        return Goal(GoalType.REACH_LOCATION, "Test goal")

    def test_default_status(self, test_goal):
        """Default status is NOT_STARTED."""
        plan = Plan(goal=test_goal)
        assert plan.status == PlanStatus.NOT_STARTED

    def test_default_action_index(self, test_goal):
        """Default action index is 0."""
        plan = Plan(goal=test_goal)
        assert plan.current_action_index == 0

    def test_default_actions(self, test_goal):
        """Default actions is empty list."""
        plan = Plan(goal=test_goal)
        assert plan.actions == []

    def test_default_execution_log(self, test_goal):
        """Default execution_log is empty list."""
        plan = Plan(goal=test_goal)
        assert plan.execution_log == []


class TestPlanCurrentAction:
    """Test Plan.current_action property."""

    @pytest.fixture
    def test_goal(self):
        return Goal(GoalType.REACH_LOCATION, "Test")

    def test_no_actions_returns_none(self, test_goal):
        """No actions means current_action is None."""
        plan = Plan(goal=test_goal)
        assert plan.current_action is None

    def test_returns_first_action(self, test_goal):
        """Returns first action initially."""
        plan = Plan(goal=test_goal)
        action = Action(name="first", description="First")
        plan.add_action(action)
        assert plan.current_action == action

    def test_returns_current_indexed_action(self, test_goal):
        """Returns action at current index."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="first", description="First"))
        plan.add_action(Action(name="second", description="Second"))
        plan.current_action_index = 1
        assert plan.current_action.name == "second"

    def test_past_end_returns_none(self, test_goal):
        """Past end of actions returns None."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="only", description="Only"))
        plan.current_action_index = 1
        assert plan.current_action is None


class TestPlanAddAction:
    """Test Plan.add_action method."""

    @pytest.fixture
    def test_goal(self):
        return Goal(GoalType.REACH_LOCATION, "Test")

    def test_adds_to_list(self, test_goal):
        """Action is added to actions list."""
        plan = Plan(goal=test_goal)
        action = Action(name="test", description="Test")
        plan.add_action(action)
        assert action in plan.actions

    def test_maintains_order(self, test_goal):
        """Actions maintain insertion order."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="first", description="First"))
        plan.add_action(Action(name="second", description="Second"))
        plan.add_action(Action(name="third", description="Third"))
        assert [a.name for a in plan.actions] == ["first", "second", "third"]


class TestPlanAdvance:
    """Test Plan.advance method."""

    @pytest.fixture
    def test_goal(self):
        return Goal(GoalType.REACH_LOCATION, "Test")

    def test_increments_index(self, test_goal):
        """Advance increments action index."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="test", description="Test"))
        initial = plan.current_action_index
        plan.advance()
        assert plan.current_action_index == initial + 1

    def test_returns_true_if_more(self, test_goal):
        """Returns True if more actions remain."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="first", description="First"))
        plan.add_action(Action(name="second", description="Second"))
        assert plan.advance() is True

    def test_returns_false_at_end(self, test_goal):
        """Returns False at end of actions."""
        plan = Plan(goal=test_goal)
        plan.add_action(Action(name="only", description="Only"))
        assert plan.advance() is False


class TestPlanLog:
    """Test Plan.log method."""

    @pytest.fixture
    def test_goal(self):
        return Goal(GoalType.REACH_LOCATION, "Test")

    def test_adds_message(self, test_goal):
        """Log adds message to execution_log."""
        plan = Plan(goal=test_goal)
        plan.log("Test message")
        assert "Test message" in plan.execution_log

    def test_preserves_order(self, test_goal):
        """Log entries maintain order."""
        plan = Plan(goal=test_goal)
        plan.log("First")
        plan.log("Second")
        plan.log("Third")
        assert plan.execution_log == ["First", "Second", "Third"]


# =============================================================================
# ActionPlanner Extended Tests
# =============================================================================

class TestActionPlannerInit:
    """Test ActionPlanner initialization."""

    def test_init_without_emulator(self):
        """Can initialize without emulator."""
        planner = ActionPlanner()
        assert planner._emu is None

    def test_init_with_emulator(self):
        """Can initialize with emulator."""
        mock_emu = Mock()
        planner = ActionPlanner(emulator=mock_emu)
        assert planner._emu == mock_emu

    def test_init_creates_parser(self):
        """Creates default parser."""
        planner = ActionPlanner()
        assert planner._parser is not None


class TestActionPlannerCreatePlan:
    """Test ActionPlanner.create_plan method."""

    @pytest.fixture
    def planner(self):
        return ActionPlanner()

    def test_creates_plan_for_reach_location(self, planner):
        """Creates plan for REACH_LOCATION goal."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)
        assert plan.goal == goal
        assert len(plan.actions) >= 1

    def test_creates_plan_for_enter_building(self, planner):
        """Creates plan for ENTER_BUILDING goal."""
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)
        assert plan.goal == goal
        assert len(plan.actions) >= 2

    def test_creates_plan_for_exit_building(self, planner):
        """Creates plan for EXIT_BUILDING goal."""
        goal = Goal.exit_building()
        plan = planner.create_plan(goal)
        assert plan.goal == goal
        assert len(plan.actions) >= 2

    def test_creates_plan_for_defeat_enemy(self, planner):
        """Creates plan for DEFEAT_ENEMY goal."""
        goal = Goal.defeat_enemy()
        plan = planner.create_plan(goal)
        assert plan.goal == goal
        assert len(plan.actions) >= 1

    def test_unsupported_goal_type_fails(self, planner):
        """Unsupported goal type sets FAILED status."""
        goal = Goal(GoalType.SOLVE_PUZZLE, "Unsupported")
        plan = planner.create_plan(goal)
        assert plan.status == PlanStatus.FAILED

    def test_reach_location_has_condition(self, planner):
        """Reach location plan has completion condition."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)
        # At least one action should have a condition
        has_condition = any(a.condition is not None for a in plan.actions)
        assert has_condition

    def test_enter_building_has_walk_action(self, planner):
        """Enter building plan has walk action."""
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)
        has_approach = any("approach" in a.name.lower() for a in plan.actions)
        assert has_approach

    def test_defeat_enemy_has_attack_actions(self, planner):
        """Defeat enemy plan has attack actions."""
        goal = Goal.defeat_enemy()
        plan = planner.create_plan(goal)
        has_attack = any("attack" in a.name.lower() for a in plan.actions)
        assert has_attack


class TestActionPlannerExecutePlan:
    """Test ActionPlanner.execute_plan method."""

    def test_fails_without_emulator(self):
        """Execute fails without emulator."""
        planner = ActionPlanner()
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)
        status = planner.execute_plan(plan)
        assert status == PlanStatus.FAILED

    def test_logs_no_emulator_error(self):
        """Logs error message without emulator."""
        planner = ActionPlanner()
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)
        planner.execute_plan(plan)
        assert any("emulator" in msg.lower() for msg in plan.execution_log)

    def test_sets_in_progress_status(self):
        """Sets IN_PROGRESS when starting."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.inject_input.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=0, mode=0x09, submode=0, area=0x29, room=0,
            link_x=512, link_y=480, link_z=0, link_direction=0,
            link_state=0, indoors=False, inidisp=0x0F, health=24, max_health=24
        )

        planner = ActionPlanner(mock_emu)
        goal = Goal.reach_location(0x29, 512, 480, tolerance=100)
        plan = planner.create_plan(goal)
        planner.execute_plan(plan)
        # Should have been IN_PROGRESS at some point (logged)
        assert any("Starting" in msg for msg in plan.execution_log)


class TestActionPlannerGetCurrentState:
    """Test ActionPlanner.get_current_state method."""

    def test_returns_none_without_emulator(self):
        """Returns None without emulator."""
        planner = ActionPlanner()
        state = planner.get_current_state()
        assert state is None

    def test_returns_none_if_disconnected(self):
        """Returns None if emulator disconnected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False
        planner = ActionPlanner(mock_emu)
        state = planner.get_current_state()
        assert state is None

    def test_returns_parsed_state_if_connected(self):
        """Returns ParsedGameState if connected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=0, mode=0x09, submode=0, area=0x29, room=0,
            link_x=512, link_y=480, link_z=0, link_direction=2,
            link_state=0, indoors=False, inidisp=0x0F, health=24, max_health=24
        )

        planner = ActionPlanner(mock_emu)
        state = planner.get_current_state()
        assert state is not None
        assert state.phase == GamePhase.OVERWORLD


# =============================================================================
# Pre-built Goals Extended Tests
# =============================================================================

class TestGoalReachVillageCenter:
    """Test goal_reach_village_center function."""

    def test_returns_goal(self):
        """Returns a Goal object."""
        goal = goal_reach_village_center()
        assert isinstance(goal, Goal)

    def test_correct_goal_type(self):
        """Has REACH_LOCATION type."""
        goal = goal_reach_village_center()
        assert goal.goal_type == GoalType.REACH_LOCATION

    def test_correct_area_id(self):
        """Area ID is 0x29 (Village Center)."""
        goal = goal_reach_village_center()
        assert goal.parameters["area_id"] == 0x29

    def test_has_coordinates(self):
        """Has x and y coordinates."""
        goal = goal_reach_village_center()
        assert "x" in goal.parameters
        assert "y" in goal.parameters

    def test_has_tolerance(self):
        """Has tolerance parameter."""
        goal = goal_reach_village_center()
        assert "tolerance" in goal.parameters


class TestGoalReachDungeon1Entrance:
    """Test goal_reach_dungeon1_entrance function."""

    def test_returns_goal(self):
        """Returns a Goal object."""
        goal = goal_reach_dungeon1_entrance()
        assert isinstance(goal, Goal)

    def test_correct_goal_type(self):
        """Has REACH_LOCATION type."""
        goal = goal_reach_dungeon1_entrance()
        assert goal.goal_type == GoalType.REACH_LOCATION

    def test_correct_area_id(self):
        """Area ID is 0x1E (Zora Sanctuary)."""
        goal = goal_reach_dungeon1_entrance()
        assert goal.parameters["area_id"] == 0x1E

    def test_has_coordinates(self):
        """Has x and y coordinates."""
        goal = goal_reach_dungeon1_entrance()
        assert "x" in goal.parameters
        assert "y" in goal.parameters


class TestGoalCompleteDungeon1:
    """Test goal_complete_dungeon1 function."""

    def test_returns_goal(self):
        """Returns a Goal object."""
        goal = goal_complete_dungeon1()
        assert isinstance(goal, Goal)

    def test_correct_goal_type(self):
        """Has COMPLETE_DUNGEON type."""
        goal = goal_complete_dungeon1()
        assert goal.goal_type == GoalType.COMPLETE_DUNGEON

    def test_correct_dungeon_id(self):
        """Dungeon ID is 0x06 (Zora Temple)."""
        goal = goal_complete_dungeon1()
        assert goal.parameters["dungeon_id"] == 0x06

    def test_has_description(self):
        """Has meaningful description."""
        goal = goal_complete_dungeon1()
        assert len(goal.description) > 0
        assert "Zora" in goal.description or "Temple" in goal.description


# =============================================================================
# Integration-style Tests
# =============================================================================

class TestPlanWorkflow:
    """Test complete plan creation and structure."""

    def test_reach_location_workflow(self):
        """Complete workflow for reach location."""
        planner = ActionPlanner()
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)

        # Plan should be ready
        assert plan.status == PlanStatus.NOT_STARTED
        assert plan.goal == goal
        assert len(plan.actions) > 0
        assert len(plan.execution_log) > 0  # Planning logs

    def test_enter_building_workflow(self):
        """Complete workflow for enter building."""
        planner = ActionPlanner()
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)

        # Should have approach and wait actions
        action_names = [a.name for a in plan.actions]
        assert any("approach" in n for n in action_names)
        assert any("wait" in n for n in action_names)

    def test_defeat_enemy_workflow(self):
        """Complete workflow for defeat enemy."""
        planner = ActionPlanner()
        goal = Goal.defeat_enemy(0x10)
        plan = planner.create_plan(goal)

        # Should have multiple attack actions
        attack_count = sum(1 for a in plan.actions if "attack" in a.name.lower())
        assert attack_count >= 1
