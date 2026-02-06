"""Iteration 51 - Action Execution Tests.

Tests for action execution flow, plan state management, goal completion,
condition evaluation, and execution callbacks.

Focus: Plan execution lifecycle, action advancement, status transitions,
execution logging, timeout handling, failure recovery.
"""

import pytest
import time
from unittest.mock import MagicMock, patch, call

from scripts.campaign.action_planner import (
    GoalType,
    PlanStatus,
    Goal,
    Plan,
    Action,
    ActionPlanner,
    goal_reach_village_center,
    goal_reach_dungeon1_entrance,
    goal_complete_dungeon1,
)
from scripts.campaign.game_state import GamePhase


# =============================================================================
# Helper to create actions with required fields
# =============================================================================

def _action(name: str, condition=None, description: str = "Test action"):
    """Create action with required fields."""
    return Action(name=name, description=description, condition=condition)


# =============================================================================
# Plan Status Lifecycle Tests
# =============================================================================

class TestPlanStatusLifecycle:
    """Tests for plan status lifecycle."""

    def test_plan_starts_not_started(self):
        """New plan has NOT_STARTED status."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        assert plan.status == PlanStatus.NOT_STARTED

    def test_plan_status_to_in_progress(self):
        """Plan status can transition to IN_PROGRESS."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        plan.status = PlanStatus.IN_PROGRESS
        assert plan.status == PlanStatus.IN_PROGRESS

    def test_plan_status_to_completed(self):
        """Plan status can transition to COMPLETED."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        plan.status = PlanStatus.COMPLETED
        assert plan.status == PlanStatus.COMPLETED

    def test_plan_status_to_failed(self):
        """Plan status can transition to FAILED."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        plan.status = PlanStatus.FAILED
        assert plan.status == PlanStatus.FAILED

    def test_plan_status_to_blocked(self):
        """Plan status can transition to BLOCKED."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        plan.status = PlanStatus.BLOCKED
        assert plan.status == PlanStatus.BLOCKED


# =============================================================================
# Action Index Tests
# =============================================================================

class TestActionIndex:
    """Tests for action index management."""

    def test_current_action_index_starts_zero(self):
        """Current action index starts at 0."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])
        assert plan.current_action_index == 0

    def test_advance_increments_index(self):
        """Advance increments action index."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("Action1", lambda s: True),
            _action("Action2", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        plan.advance()
        assert plan.current_action_index == 1

    def test_advance_past_end(self):
        """Advance past last action."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])

        plan.advance()  # Now at index 1, past the single action
        assert plan.current_action_index == 1

    def test_current_action_property(self):
        """Get current action by index."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action1 = _action("Action1", lambda s: True)
        action2 = _action("Action2", lambda s: True)
        plan = Plan(goal=goal, actions=[action1, action2])

        assert plan.current_action == action1
        plan.advance()
        assert plan.current_action == action2

    def test_current_action_none_when_empty(self):
        """Current action is None for empty plan."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        assert plan.current_action is None

    def test_current_action_none_when_past_end(self):
        """Current action is None when past end."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])

        plan.advance()
        assert plan.current_action is None


# =============================================================================
# Action Condition Tests
# =============================================================================

class TestActionConditions:
    """Tests for action condition evaluation."""

    def test_action_condition_true(self):
        """Action condition returns True."""
        action = _action("Test", lambda s: True)
        mock_state = MagicMock()
        assert action.condition(mock_state) is True

    def test_action_condition_false(self):
        """Action condition returns False."""
        action = _action("Test", lambda s: False)
        mock_state = MagicMock()
        assert action.condition(mock_state) is False

    def test_action_condition_with_state(self):
        """Action condition uses state."""
        def check_health(state):
            return state.health > 10

        action = _action("CheckHealth", check_health)

        good_state = MagicMock()
        good_state.health = 24
        assert action.condition(good_state) is True

        bad_state = MagicMock()
        bad_state.health = 5
        assert action.condition(bad_state) is False

    def test_action_condition_phase_check(self):
        """Action condition checks game phase."""
        def in_overworld(state):
            return state.phase == GamePhase.OVERWORLD

        action = _action("OverworldCheck", in_overworld)

        ow_state = MagicMock()
        ow_state.phase = GamePhase.OVERWORLD
        assert action.condition(ow_state) is True

        dungeon_state = MagicMock()
        dungeon_state.phase = GamePhase.DUNGEON
        assert action.condition(dungeon_state) is False

    def test_action_is_complete_method(self):
        """Action is_complete method uses condition."""
        action = _action("Test", lambda s: s.done)

        done_state = MagicMock()
        done_state.done = True
        assert action.is_complete(done_state) is True

        not_done = MagicMock()
        not_done.done = False
        assert action.is_complete(not_done) is False

    def test_action_is_complete_no_condition(self):
        """Action without condition is always complete."""
        action = _action("NoCondition", None)
        assert action.is_complete(MagicMock()) is True


# =============================================================================
# Plan Completion Tests
# =============================================================================

class TestPlanCompletion:
    """Tests for plan completion detection."""

    def test_empty_plan_has_no_current_action(self):
        """Empty plan has no current action."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        assert plan.current_action is None

    def test_plan_with_actions_not_complete_at_start(self):
        """Plan with actions has current action at start."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])
        assert plan.current_action is not None

    def test_plan_complete_after_all_actions(self):
        """Plan has no current action after all advances."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])

        plan.advance()
        assert plan.current_action is None

    def test_plan_complete_multiple_actions(self):
        """Plan with multiple actions completes correctly."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("Action1", lambda s: True),
            _action("Action2", lambda s: True),
            _action("Action3", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        assert plan.current_action is not None
        plan.advance()
        assert plan.current_action is not None
        plan.advance()
        assert plan.current_action is not None
        plan.advance()
        assert plan.current_action is None

    def test_advance_returns_true_while_more_actions(self):
        """Advance returns True while more actions remain."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("A", lambda s: True),
            _action("B", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        assert plan.advance() is True  # More actions
        assert plan.advance() is False  # No more actions


# =============================================================================
# Goal Factory Tests
# =============================================================================

class TestGoalFactories:
    """Tests for pre-built goal factories."""

    def test_goal_reach_village_center(self):
        """Reach village center goal."""
        goal = goal_reach_village_center()
        assert goal.goal_type == GoalType.REACH_LOCATION
        assert len(goal.description) > 0

    def test_goal_reach_dungeon1_entrance(self):
        """Reach dungeon 1 entrance goal."""
        goal = goal_reach_dungeon1_entrance()
        assert goal.goal_type == GoalType.REACH_LOCATION

    def test_goal_complete_dungeon1(self):
        """Complete dungeon 1 goal."""
        goal = goal_complete_dungeon1()
        # This goal could be DEFEAT_ENEMY or other type
        assert goal.goal_type in list(GoalType)


# =============================================================================
# Goal Type Tests
# =============================================================================

class TestGoalTypes:
    """Tests for GoalType enum."""

    def test_reach_location_exists(self):
        """REACH_LOCATION goal type exists."""
        assert hasattr(GoalType, 'REACH_LOCATION')

    def test_enter_building_exists(self):
        """ENTER_BUILDING goal type exists."""
        assert hasattr(GoalType, 'ENTER_BUILDING')

    def test_exit_building_exists(self):
        """EXIT_BUILDING goal type exists."""
        assert hasattr(GoalType, 'EXIT_BUILDING')

    def test_talk_to_npc_exists(self):
        """TALK_TO_NPC goal type exists."""
        assert hasattr(GoalType, 'TALK_TO_NPC')

    def test_get_item_exists(self):
        """GET_ITEM goal type exists."""
        assert hasattr(GoalType, 'GET_ITEM')

    def test_defeat_enemy_exists(self):
        """DEFEAT_ENEMY goal type exists."""
        assert hasattr(GoalType, 'DEFEAT_ENEMY')

    def test_all_goal_types_unique(self):
        """All goal types have unique values."""
        values = [gt.value for gt in GoalType]
        assert len(values) == len(set(values))


# =============================================================================
# Action Planner Creation Tests
# =============================================================================

class TestActionPlannerCreation:
    """Tests for ActionPlanner creation."""

    def test_create_with_mock_emulator(self):
        """Create planner with mock emulator."""
        mock_emu = MagicMock()
        mock_parser = MagicMock()
        planner = ActionPlanner(mock_emu, mock_parser)
        assert planner is not None

    def test_create_plan_basic(self):
        """Create basic plan from goal."""
        mock_emu = MagicMock()
        mock_parser = MagicMock()
        planner = ActionPlanner(mock_emu, mock_parser)

        # REACH_LOCATION requires x, y, area_id parameters
        goal = Goal.reach_location(area_id=0x29, x=100, y=200)
        plan = planner.create_plan(goal)

        assert isinstance(plan, Plan)
        assert plan.goal == goal


# =============================================================================
# Execution Log Tests
# =============================================================================

class TestExecutionLog:
    """Tests for execution logging."""

    def test_plan_has_execution_log(self):
        """Plan has execution log."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        assert hasattr(plan, 'execution_log')

    def test_execution_log_starts_empty(self):
        """Execution log starts empty."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])
        assert len(plan.execution_log) == 0

    def test_log_adds_entry(self):
        """Log method adds entry."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])

        plan.log("Test message")
        assert len(plan.execution_log) == 1
        assert "Test message" in plan.execution_log

    def test_multiple_log_entries(self):
        """Multiple log entries accumulate."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])

        plan.log("Entry 1")
        plan.log("Entry 2")
        plan.log("Entry 3")
        assert len(plan.execution_log) == 3


# =============================================================================
# Multiple Action Execution Tests
# =============================================================================

class TestMultipleActionExecution:
    """Tests for executing multiple actions."""

    def test_execute_three_actions(self):
        """Execute plan with three actions."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("Step1", lambda s: True),
            _action("Step2", lambda s: True),
            _action("Step3", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        # Simulate execution
        assert plan.current_action.name == "Step1"
        plan.advance()
        assert plan.current_action.name == "Step2"
        plan.advance()
        assert plan.current_action.name == "Step3"
        plan.advance()
        assert plan.current_action is None

    def test_action_names_unique(self):
        """Action names in plan are accessible."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("Action A", lambda s: True),
            _action("Action B", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        names = [a.name for a in plan.actions]
        assert "Action A" in names
        assert "Action B" in names


# =============================================================================
# Goal Parameters Tests
# =============================================================================

class TestGoalParameters:
    """Tests for goal parameters."""

    def test_goal_with_parameters(self):
        """Goal with parameters."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Go to location",
            parameters={"x": 100, "y": 200, "area_id": 0x29}
        )

        assert goal.parameters["x"] == 100
        assert goal.parameters["y"] == 200
        assert goal.parameters["area_id"] == 0x29

    def test_goal_empty_parameters_default(self):
        """Goal with default empty parameters."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test"
        )

        assert goal.parameters == {}

    def test_goal_classmethod_reach_location(self):
        """Goal.reach_location class method."""
        goal = Goal.reach_location(area_id=0x29, x=100, y=200)
        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 100
        assert goal.parameters["y"] == 200

    def test_goal_classmethod_enter_building(self):
        """Goal.enter_building class method."""
        goal = Goal.enter_building(entrance_id=0x10)
        assert goal.goal_type == GoalType.ENTER_BUILDING
        assert goal.parameters["entrance_id"] == 0x10

    def test_goal_classmethod_talk_to_npc(self):
        """Goal.talk_to_npc class method."""
        goal = Goal.talk_to_npc(npc_id=0x05)
        assert goal.goal_type == GoalType.TALK_TO_NPC
        assert goal.parameters["npc_id"] == 0x05

    def test_goal_classmethod_get_item(self):
        """Goal.get_item class method."""
        goal = Goal.get_item(item_id=0x01)
        assert goal.goal_type == GoalType.GET_ITEM
        assert goal.parameters["item_id"] == 0x01

    def test_goal_classmethod_defeat_enemy(self):
        """Goal.defeat_enemy class method."""
        goal = Goal.defeat_enemy(sprite_id=0x20)
        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters["sprite_id"] == 0x20


# =============================================================================
# Condition Lambda Tests
# =============================================================================

class TestConditionLambdas:
    """Tests for condition lambda functions."""

    def test_position_condition(self):
        """Condition checking position."""
        def at_target(state):
            return state.link_x == 100 and state.link_y == 200

        action = _action("CheckPosition", at_target)

        at_pos = MagicMock()
        at_pos.link_x = 100
        at_pos.link_y = 200
        assert action.condition(at_pos) is True

        not_at = MagicMock()
        not_at.link_x = 50
        not_at.link_y = 50
        assert action.condition(not_at) is False

    def test_health_threshold_condition(self):
        """Condition checking health threshold."""
        def has_enough_health(state):
            return state.health >= 12  # At least 3 hearts

        action = _action("CheckHealth", has_enough_health)

        full_health = MagicMock()
        full_health.health = 24
        assert action.condition(full_health) is True

        low_health = MagicMock()
        low_health.health = 8
        assert action.condition(low_health) is False

    def test_area_condition(self):
        """Condition checking area."""
        def in_village(state):
            return state.area_id == 0x29

        action = _action("InVillage", in_village)

        village = MagicMock()
        village.area_id = 0x29
        assert action.condition(village) is True

        wilderness = MagicMock()
        wilderness.area_id = 0x00
        assert action.condition(wilderness) is False


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_action_with_none_condition(self):
        """Action with None condition is allowed."""
        action = _action("Test", None)
        assert action.condition is None
        # is_complete returns True when no condition
        assert action.is_complete(MagicMock()) is True

    def test_empty_goal_description(self):
        """Goal with empty description."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="")
        assert goal.description == ""

    def test_very_long_goal_description(self):
        """Goal with very long description."""
        long_desc = "A" * 1000
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description=long_desc)
        assert len(goal.description) == 1000

    def test_action_with_special_characters(self):
        """Action with special characters in name."""
        action = _action("Walk → North ↑", lambda s: True)
        assert "→" in action.name

    def test_plan_with_many_actions(self):
        """Plan with many actions."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action(f"Action_{i}", lambda s: True)
            for i in range(100)
        ]
        plan = Plan(goal=goal, actions=actions)

        assert len(plan.actions) == 100
        assert plan.current_action_index == 0

    def test_advance_many_times(self):
        """Advance many times safely."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        action = _action("Test", lambda s: True)
        plan = Plan(goal=goal, actions=[action])

        for _ in range(100):
            plan.advance()

        assert plan.current_action_index == 100
        assert plan.current_action is None

    def test_goal_type_comparison(self):
        """Goal types can be compared."""
        assert GoalType.REACH_LOCATION == GoalType.REACH_LOCATION
        assert GoalType.REACH_LOCATION != GoalType.DEFEAT_ENEMY

    def test_plan_status_comparison(self):
        """Plan statuses can be compared."""
        assert PlanStatus.NOT_STARTED == PlanStatus.NOT_STARTED
        assert PlanStatus.NOT_STARTED != PlanStatus.COMPLETED

    def test_condition_with_exception(self):
        """Condition that raises exception."""
        def bad_condition(state):
            raise ValueError("Bad state")

        action = _action("Risky", bad_condition)
        mock_state = MagicMock()

        with pytest.raises(ValueError):
            action.condition(mock_state)

    def test_action_timeout_frames_default(self):
        """Action has default timeout_frames."""
        action = _action("Test", lambda s: True)
        assert action.timeout_frames == 600


# =============================================================================
# Plan Reset Tests
# =============================================================================

class TestPlanReset:
    """Tests for plan reset functionality."""

    def test_plan_can_be_reset(self):
        """Plan index can be reset."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        actions = [
            _action("A", lambda s: True),
            _action("B", lambda s: True),
        ]
        plan = Plan(goal=goal, actions=actions)

        plan.advance()
        plan.advance()
        assert plan.current_action_index == 2

        # Manual reset
        plan.current_action_index = 0
        assert plan.current_action_index == 0
        assert plan.current_action.name == "A"

    def test_plan_status_reset(self):
        """Plan status can be reset."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])

        plan.status = PlanStatus.FAILED
        assert plan.status == PlanStatus.FAILED

        plan.status = PlanStatus.NOT_STARTED
        assert plan.status == PlanStatus.NOT_STARTED


# =============================================================================
# Plan Add Action Tests
# =============================================================================

class TestPlanAddAction:
    """Tests for dynamically adding actions to plans."""

    def test_add_action_to_empty_plan(self):
        """Add action to empty plan."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])

        action = _action("New", lambda s: True)
        plan.add_action(action)

        assert len(plan.actions) == 1
        assert plan.current_action == action

    def test_add_multiple_actions(self):
        """Add multiple actions dynamically."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal, actions=[])

        for i in range(5):
            plan.add_action(_action(f"Action{i}", lambda s: True))

        assert len(plan.actions) == 5


# =============================================================================
# Goal Priority Tests
# =============================================================================

class TestGoalPriority:
    """Tests for goal priority."""

    def test_goal_default_priority(self):
        """Goal has default priority of 0."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        assert goal.priority == 0

    def test_goal_custom_priority(self):
        """Goal with custom priority."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test",
            priority=10
        )
        assert goal.priority == 10

    def test_goal_priority_comparison(self):
        """Goals can be compared by priority."""
        low = Goal(goal_type=GoalType.REACH_LOCATION, description="Low", priority=1)
        high = Goal(goal_type=GoalType.REACH_LOCATION, description="High", priority=10)

        assert low.priority < high.priority


# =============================================================================
# Goal Preconditions Tests
# =============================================================================

class TestGoalPreconditions:
    """Tests for goal preconditions."""

    def test_goal_empty_preconditions(self):
        """Goal has empty preconditions by default."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        assert goal.preconditions == []

    def test_goal_with_preconditions(self):
        """Goal with preconditions."""
        pre = Goal(goal_type=GoalType.GET_ITEM, description="Get key")
        goal = Goal(
            goal_type=GoalType.ENTER_BUILDING,
            description="Enter building",
            preconditions=[pre]
        )

        assert len(goal.preconditions) == 1
        assert goal.preconditions[0] == pre
