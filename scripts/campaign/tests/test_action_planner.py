"""Tests for action_planner module.

Campaign Goals Supported:
- D.5: Goal-oriented action planner
"""

import pytest
from unittest.mock import Mock, MagicMock, patch

import sys
from pathlib import Path

# Add project root to path for imports
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


class TestGoalType:
    """Tests for GoalType enum."""

    def test_goal_types_exist(self):
        """Test all goal types are defined."""
        assert GoalType.REACH_LOCATION is not None
        assert GoalType.ENTER_BUILDING is not None
        assert GoalType.EXIT_BUILDING is not None
        assert GoalType.DEFEAT_ENEMY is not None
        assert GoalType.COMPLETE_DUNGEON is not None


class TestPlanStatus:
    """Tests for PlanStatus enum."""

    def test_status_values(self):
        """Test all status values."""
        assert PlanStatus.NOT_STARTED is not None
        assert PlanStatus.IN_PROGRESS is not None
        assert PlanStatus.COMPLETED is not None
        assert PlanStatus.FAILED is not None
        assert PlanStatus.BLOCKED is not None


class TestGoal:
    """Tests for Goal dataclass."""

    def test_basic_goal(self):
        """Test creating basic goal."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test goal",
            parameters={"x": 100, "y": 200}
        )
        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["x"] == 100

    def test_reach_location_factory(self):
        """Test reach_location factory method."""
        goal = Goal.reach_location(0x29, 512, 480)

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 512
        assert goal.parameters["y"] == 480
        assert "tolerance" in goal.parameters

    def test_reach_location_with_tolerance(self):
        """Test reach_location with custom tolerance."""
        goal = Goal.reach_location(0x29, 512, 480, tolerance=32)
        assert goal.parameters["tolerance"] == 32

    def test_enter_building_factory(self):
        """Test enter_building factory method."""
        goal = Goal.enter_building(0x12)

        assert goal.goal_type == GoalType.ENTER_BUILDING
        assert goal.parameters["entrance_id"] == 0x12

    def test_exit_building_factory(self):
        """Test exit_building factory method."""
        goal = Goal.exit_building()

        assert goal.goal_type == GoalType.EXIT_BUILDING

    def test_talk_to_npc_factory(self):
        """Test talk_to_npc factory method."""
        goal = Goal.talk_to_npc(0x55)

        assert goal.goal_type == GoalType.TALK_TO_NPC
        assert goal.parameters["npc_id"] == 0x55

    def test_get_item_factory(self):
        """Test get_item factory method."""
        goal = Goal.get_item(0x01)

        assert goal.goal_type == GoalType.GET_ITEM
        assert goal.parameters["item_id"] == 0x01

    def test_defeat_enemy_factory(self):
        """Test defeat_enemy factory method."""
        goal = Goal.defeat_enemy(0x10)

        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters["sprite_id"] == 0x10

    def test_defeat_enemy_no_id(self):
        """Test defeat_enemy without specific ID."""
        goal = Goal.defeat_enemy()

        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters["sprite_id"] is None


class TestAction:
    """Tests for Action dataclass."""

    def test_basic_action(self):
        """Test creating basic action."""
        action = Action(
            name="test_action",
            description="A test action"
        )
        assert action.name == "test_action"
        assert action.timeout_frames == 600  # Default

    def test_action_with_condition(self):
        """Test action with completion condition."""
        def check_position(state):
            return state.link_position[0] > 100

        action = Action(
            name="move_right",
            description="Move right until x > 100",
            condition=check_position
        )
        assert action.condition is not None

    def test_is_complete_no_condition(self):
        """Test is_complete with no condition returns True."""
        action = Action(name="simple", description="Simple action")
        mock_state = Mock()
        assert action.is_complete(mock_state) is True

    def test_is_complete_with_condition(self):
        """Test is_complete uses condition."""
        action = Action(
            name="conditional",
            description="Conditional action",
            condition=lambda s: s.is_indoors
        )

        indoor_state = Mock(is_indoors=True)
        outdoor_state = Mock(is_indoors=False)

        assert action.is_complete(indoor_state) is True
        assert action.is_complete(outdoor_state) is False


class TestPlan:
    """Tests for Plan dataclass."""

    @pytest.fixture
    def simple_goal(self):
        """Create simple test goal."""
        return Goal(GoalType.REACH_LOCATION, "Test", {"x": 100})

    def test_plan_initial_state(self, simple_goal):
        """Test plan starts in correct state."""
        plan = Plan(goal=simple_goal)

        assert plan.status == PlanStatus.NOT_STARTED
        assert plan.current_action_index == 0
        assert len(plan.actions) == 0

    def test_add_action(self, simple_goal):
        """Test adding actions to plan."""
        plan = Plan(goal=simple_goal)
        action = Action("test", "Test action")

        plan.add_action(action)

        assert len(plan.actions) == 1
        assert plan.current_action == action

    def test_current_action(self, simple_goal):
        """Test current_action property."""
        plan = Plan(goal=simple_goal)

        # No actions
        assert plan.current_action is None

        # Add action
        action = Action("test", "Test")
        plan.add_action(action)
        assert plan.current_action == action

    def test_advance(self, simple_goal):
        """Test advancing through actions."""
        plan = Plan(goal=simple_goal)
        plan.add_action(Action("first", "First"))
        plan.add_action(Action("second", "Second"))

        assert plan.current_action.name == "first"

        has_more = plan.advance()
        assert has_more is True
        assert plan.current_action.name == "second"

        has_more = plan.advance()
        assert has_more is False
        assert plan.current_action is None

    def test_log(self, simple_goal):
        """Test logging."""
        plan = Plan(goal=simple_goal)
        plan.log("Test message")

        assert "Test message" in plan.execution_log


class TestActionPlanner:
    """Tests for ActionPlanner class."""

    @pytest.fixture
    def planner(self):
        """Create planner without emulator."""
        return ActionPlanner()

    def test_create_reach_location_plan(self, planner):
        """Test creating plan for reach location."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)

        assert plan.goal == goal
        assert len(plan.actions) > 0
        assert plan.status == PlanStatus.NOT_STARTED

    def test_create_enter_building_plan(self, planner):
        """Test creating plan for entering building."""
        goal = Goal.enter_building(0x12)
        plan = planner.create_plan(goal)

        assert plan.goal == goal
        assert len(plan.actions) >= 2  # Approach + wait

    def test_create_exit_building_plan(self, planner):
        """Test creating plan for exiting building."""
        goal = Goal.exit_building()
        plan = planner.create_plan(goal)

        assert plan.goal == goal
        assert len(plan.actions) >= 2

    def test_create_defeat_enemy_plan(self, planner):
        """Test creating plan for defeating enemy."""
        goal = Goal.defeat_enemy()
        plan = planner.create_plan(goal)

        assert plan.goal == goal
        assert len(plan.actions) >= 1  # At least one attack

    def test_execute_plan_no_emulator(self, planner):
        """Test execute_plan fails without emulator."""
        goal = Goal.reach_location(0x29, 512, 480)
        plan = planner.create_plan(goal)

        status = planner.execute_plan(plan)

        assert status == PlanStatus.FAILED
        assert "No emulator" in plan.execution_log[-1]

    def test_get_current_state_no_emulator(self, planner):
        """Test get_current_state with no emulator."""
        state = planner.get_current_state()
        assert state is None


class TestActionPlannerWithMockEmulator:
    """Tests with mocked emulator."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.is_connected.return_value = True
        emu.step_frame.return_value = True
        emu.inject_input.return_value = True

        # Create a proper GameStateSnapshot
        emu.read_state.return_value = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=0x02,
            link_state=0x00,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
        )
        return emu

    def test_execute_simple_plan(self, mock_emulator):
        """Test executing a simple plan."""
        planner = ActionPlanner(mock_emulator)

        # Create goal that will be immediately satisfied
        goal = Goal.reach_location(0x29, 512, 480, tolerance=100)
        plan = planner.create_plan(goal)

        # The mock state is already at the target
        status = planner.execute_plan(plan)

        # Should complete since we're already there
        assert status in (PlanStatus.COMPLETED, PlanStatus.IN_PROGRESS)

    def test_get_current_state_connected(self, mock_emulator):
        """Test get_current_state with connected emulator."""
        planner = ActionPlanner(mock_emulator)
        state = planner.get_current_state()

        assert state is not None
        assert state.phase == GamePhase.OVERWORLD


class TestPrebuiltGoals:
    """Tests for pre-built navigation goals."""

    def test_village_center_goal(self):
        """Test village center goal."""
        goal = goal_reach_village_center()

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x29

    def test_dungeon1_entrance_goal(self):
        """Test dungeon 1 entrance goal."""
        goal = goal_reach_dungeon1_entrance()

        assert goal.goal_type == GoalType.REACH_LOCATION
        assert goal.parameters["area_id"] == 0x1E  # Zora Sanctuary

    def test_complete_dungeon1_goal(self):
        """Test complete dungeon 1 goal."""
        goal = goal_complete_dungeon1()

        assert goal.goal_type == GoalType.COMPLETE_DUNGEON
        assert goal.parameters["dungeon_id"] == 0x06
