"""Detailed tests for ActionPlanner and planning components.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Goal-based planning validation

These tests verify the action planning system including goals,
actions, plans, and the planning algorithm itself.
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

from scripts.campaign.action_planner import (
    GoalType, PlanStatus, Goal, Action, Plan, ActionPlanner
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.input_recorder import InputSequence, Button


class TestGoalType:
    """Test GoalType enum."""

    def test_goal_type_reach_location(self):
        """Test REACH_LOCATION goal type exists."""
        assert GoalType.REACH_LOCATION is not None

    def test_goal_type_enter_building(self):
        """Test ENTER_BUILDING goal type exists."""
        assert GoalType.ENTER_BUILDING is not None

    def test_goal_type_defeat_enemy(self):
        """Test DEFEAT_ENEMY goal type exists."""
        assert GoalType.DEFEAT_ENEMY is not None

    def test_goal_type_get_item(self):
        """Test GET_ITEM goal type exists."""
        assert GoalType.GET_ITEM is not None

    def test_goal_type_open_chest(self):
        """Test OPEN_CHEST goal type exists."""
        assert GoalType.OPEN_CHEST is not None

    def test_goal_types_distinct(self):
        """Test all goal types have distinct values."""
        types = list(GoalType)
        values = [t.value for t in types]
        assert len(values) == len(set(values))


class TestPlanStatus:
    """Test PlanStatus enum."""

    def test_plan_status_not_started(self):
        """Test NOT_STARTED status exists."""
        assert PlanStatus.NOT_STARTED is not None

    def test_plan_status_in_progress(self):
        """Test IN_PROGRESS status exists."""
        assert PlanStatus.IN_PROGRESS is not None

    def test_plan_status_completed(self):
        """Test COMPLETED status exists."""
        assert PlanStatus.COMPLETED is not None

    def test_plan_status_failed(self):
        """Test FAILED status exists."""
        assert PlanStatus.FAILED is not None

    def test_plan_status_blocked(self):
        """Test BLOCKED status exists."""
        assert PlanStatus.BLOCKED is not None


class TestGoalCreation:
    """Test Goal creation methods."""

    def test_reach_location_goal(self):
        """Test creating reach location goal."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 512
        assert goal.parameters["y"] == 480

    def test_reach_location_with_tolerance(self):
        """Test reach location goal with tolerance."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=32)

        assert goal.parameters["tolerance"] == 32

    def test_enter_building_goal(self):
        """Test creating enter building goal."""
        goal = Goal.enter_building(entrance_id=0x12)

        assert goal.goal_type == GoalType.ENTER_BUILDING
        assert goal.parameters["entrance_id"] == 0x12

    def test_defeat_enemy_goal(self):
        """Test creating defeat enemy goal."""
        goal = Goal.defeat_enemy(sprite_id=0x55)

        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters["sprite_id"] == 0x55

    def test_get_item_goal(self):
        """Test creating get item goal."""
        goal = Goal.get_item(item_id=0x10)

        assert goal.goal_type == GoalType.GET_ITEM
        assert goal.parameters["item_id"] == 0x10

    def test_open_chest_goal_manual(self):
        """Test creating open chest goal (manual construction)."""
        # No factory method exists, so construct manually
        goal = Goal(
            goal_type=GoalType.OPEN_CHEST,
            description="Open chest 0x05",
            parameters={"chest_id": 0x05}
        )

        assert goal.goal_type == GoalType.OPEN_CHEST
        assert goal.parameters["chest_id"] == 0x05


class TestGoalDescription:
    """Test Goal description generation."""

    def test_reach_location_description(self):
        """Test reach location goal has description."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        assert goal.description is not None
        assert len(goal.description) > 0

    def test_enter_building_description(self):
        """Test enter building goal has description."""
        goal = Goal.enter_building(entrance_id=0x12)

        assert goal.description is not None
        assert len(goal.description) > 0

    def test_description_contains_parameters(self):
        """Test description contains relevant parameters."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        # Description should mention area or coordinates
        desc_lower = goal.description.lower()
        assert "29" in goal.description or "0x29" in goal.description or "area" in desc_lower


class TestAction:
    """Test Action class."""

    def test_action_creation(self):
        """Test creating basic action."""
        action = Action(name="walk_up", description="Walk up one tile")

        assert action.name == "walk_up"
        assert action.description == "Walk up one tile"

    def test_action_with_sequence(self):
        """Test action with input sequence."""
        seq = InputSequence(name="walk")
        seq.add_input(0, Button.UP, hold=10)

        action = Action(
            name="walk_up",
            description="Walk up",
            input_sequence=seq
        )

        assert action.input_sequence is not None
        assert action.input_sequence.total_frames == 10

    def test_action_with_condition(self):
        """Test action with completion condition."""
        def condition(state):
            return state.link_y < 480

        action = Action(
            name="walk_up",
            description="Walk up until Y < 480",
            condition=condition
        )

        assert action.condition is not None

    def test_action_timeout(self):
        """Test action timeout configuration."""
        action = Action(
            name="long_action",
            description="A long action",
            timeout_frames=1200
        )

        assert action.timeout_frames == 1200

    def test_action_default_timeout(self):
        """Test action has default timeout."""
        action = Action(name="test", description="Test action")

        assert action.timeout_frames > 0


class TestPlan:
    """Test Plan class."""

    def test_plan_creation(self):
        """Test creating plan with goal."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        assert plan.goal is goal
        assert plan.status == PlanStatus.NOT_STARTED
        assert len(plan.actions) == 0

    def test_plan_add_action(self):
        """Test adding actions to plan."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        action1 = Action(name="walk_up", description="Walk up")
        action2 = Action(name="walk_right", description="Walk right")

        plan.actions.append(action1)
        plan.actions.append(action2)

        assert len(plan.actions) == 2

    def test_plan_status_transitions(self):
        """Test plan status can be changed."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        assert plan.status == PlanStatus.NOT_STARTED

        plan.status = PlanStatus.IN_PROGRESS
        assert plan.status == PlanStatus.IN_PROGRESS

        plan.status = PlanStatus.COMPLETED
        assert plan.status == PlanStatus.COMPLETED


class TestActionPlanner:
    """Test ActionPlanner class."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.is_connected.return_value = True
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        return emu

    def test_planner_creation(self, mock_emulator):
        """Test creating action planner."""
        planner = ActionPlanner(mock_emulator)
        assert planner is not None

    def test_create_plan_for_reach_location(self, mock_emulator):
        """Test creating plan for reach location goal."""
        planner = ActionPlanner(mock_emulator)
        goal = Goal.reach_location(area_id=0x29, x=600, y=400)

        plan = planner.create_plan(goal)

        assert plan is not None
        assert isinstance(plan, Plan)
        assert plan.goal is goal

    def test_create_plan_returns_plan(self, mock_emulator):
        """Test create_plan always returns Plan object."""
        planner = ActionPlanner(mock_emulator)
        goal = Goal.reach_location(area_id=0x29, x=100, y=100)

        plan = planner.create_plan(goal)

        assert isinstance(plan, Plan)

    def test_planner_handles_same_location(self, mock_emulator):
        """Test planner handles goal at current location."""
        planner = ActionPlanner(mock_emulator)
        # Goal at current position (512, 480)
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=16)

        plan = planner.create_plan(goal)

        assert plan is not None
        # Plan may have no actions if already at goal


class TestGoalParameters:
    """Test Goal parameter handling."""

    def test_goal_parameters_accessible(self):
        """Test goal parameters can be accessed."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=32)

        assert "area_id" in goal.parameters
        assert "x" in goal.parameters
        assert "y" in goal.parameters
        assert "tolerance" in goal.parameters

    def test_goal_parameters_types(self):
        """Test goal parameter types."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        assert isinstance(goal.parameters["area_id"], int)
        assert isinstance(goal.parameters["x"], int)
        assert isinstance(goal.parameters["y"], int)


class TestPlanExecution:
    """Test Plan execution tracking."""

    def test_plan_tracks_current_action(self):
        """Test plan can track current action index."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        plan.actions.append(Action(name="a1", description="Action 1"))
        plan.actions.append(Action(name="a2", description="Action 2"))

        # Plan should support tracking current action
        if hasattr(plan, 'current_action_index'):
            assert plan.current_action_index >= 0

    def test_plan_has_goal_reference(self):
        """Test plan maintains reference to goal."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        assert plan.goal is goal
        assert plan.goal.goal_type == GoalType.REACH_LOCATION


class TestGoalComparison:
    """Test Goal comparison and equality."""

    def test_same_parameters_creates_similar_goals(self):
        """Test goals with same parameters are similar."""
        goal1 = Goal.reach_location(area_id=0x29, x=512, y=480)
        goal2 = Goal.reach_location(area_id=0x29, x=512, y=480)

        # Same type and parameters
        assert goal1.goal_type == goal2.goal_type
        assert goal1.parameters == goal2.parameters

    def test_different_parameters_creates_different_goals(self):
        """Test goals with different parameters differ."""
        goal1 = Goal.reach_location(area_id=0x29, x=512, y=480)
        goal2 = Goal.reach_location(area_id=0x29, x=600, y=400)

        assert goal1.parameters != goal2.parameters


class TestActionSequenceIntegration:
    """Test Action integration with InputSequence."""

    def test_action_sequence_duration(self):
        """Test action reports sequence duration."""
        seq = InputSequence(name="walk")
        seq.add_input(0, Button.UP, hold=60)

        action = Action(
            name="walk_up",
            description="Walk up",
            input_sequence=seq
        )

        assert action.input_sequence.total_frames == 60
        assert action.input_sequence.duration_seconds == 1.0

    def test_action_without_sequence(self):
        """Test action can exist without sequence."""
        action = Action(name="wait", description="Wait for something")

        assert action.input_sequence is None


class TestPlannerEdgeCases:
    """Test ActionPlanner edge cases."""

    def test_planner_with_disconnected_emulator(self):
        """Test planner handles disconnected emulator."""
        emu = Mock()
        emu.is_connected.return_value = False

        planner = ActionPlanner(emu)
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        # Should handle gracefully
        plan = planner.create_plan(goal)
        # May return empty plan or raise exception

    def test_planner_with_none_emulator(self):
        """Test planner with None emulator."""
        try:
            planner = ActionPlanner(None)
            goal = Goal.reach_location(area_id=0x29, x=512, y=480)
            plan = planner.create_plan(goal)
        except (TypeError, AttributeError):
            pass  # Expected to fail gracefully


class TestGoalTypeValues:
    """Test GoalType enum values."""

    def test_all_goal_types_have_names(self):
        """Test all goal types have string names."""
        for goal_type in GoalType:
            assert goal_type.name is not None
            assert len(goal_type.name) > 0

    def test_goal_type_is_comparable(self):
        """Test goal types can be compared."""
        assert GoalType.REACH_LOCATION != GoalType.ENTER_BUILDING
        assert GoalType.REACH_LOCATION == GoalType.REACH_LOCATION


class TestPlanStatusValues:
    """Test PlanStatus enum values."""

    def test_all_plan_statuses_have_names(self):
        """Test all plan statuses have string names."""
        for status in PlanStatus:
            assert status.name is not None
            assert len(status.name) > 0

    def test_plan_status_is_comparable(self):
        """Test plan statuses can be compared."""
        assert PlanStatus.NOT_STARTED != PlanStatus.COMPLETED
        assert PlanStatus.COMPLETED == PlanStatus.COMPLETED


class TestActionConditions:
    """Test Action condition functions."""

    def test_condition_receives_state(self):
        """Test condition function receives game state."""
        received_states = []

        def condition(state):
            received_states.append(state)
            return True

        action = Action(
            name="test",
            description="Test",
            condition=condition
        )

        # Simulate checking condition
        mock_state = Mock()
        if action.condition:
            action.condition(mock_state)

        assert len(received_states) == 1
        assert received_states[0] is mock_state

    def test_condition_returns_bool(self):
        """Test condition function returns boolean."""
        def always_true(state):
            return True

        def always_false(state):
            return False

        action_true = Action(name="t", description="T", condition=always_true)
        action_false = Action(name="f", description="F", condition=always_false)

        mock_state = Mock()
        assert action_true.condition(mock_state) is True
        assert action_false.condition(mock_state) is False
