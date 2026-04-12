"""Goal-oriented action planner for Oracle of Secrets.

This module provides high-level planning for achieving gameplay goals,
combining state awareness with input generation.

Campaign Goals Supported:
- A.2: Navigate overworld to specific locations
- A.4: Complete a fetch quest
- D.5: Goal-oriented action planner

Usage:
    from scripts.campaign.action_planner import ActionPlanner, Goal

    planner = ActionPlanner(emulator)
    goal = Goal.reach_location(area_id=0x29, x=512, y=480)
    plan = planner.create_plan(goal)
    result = planner.execute_plan(plan)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Callable, Dict, Iterator, List, Optional, Tuple

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot
from .game_state import GamePhase, GameStateParser, ParsedGameState, parse_state
from .input_recorder import Button, InputSequence, create_walk_sequence


class GoalType(Enum):
    """Types of goals the planner can handle."""
    REACH_LOCATION = auto()
    ENTER_BUILDING = auto()
    EXIT_BUILDING = auto()
    TALK_TO_NPC = auto()
    GET_ITEM = auto()
    USE_ITEM = auto()
    DEFEAT_ENEMY = auto()
    OPEN_CHEST = auto()
    SOLVE_PUZZLE = auto()
    COMPLETE_DUNGEON = auto()


class PlanStatus(Enum):
    """Status of plan execution."""
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    FAILED = auto()
    BLOCKED = auto()


@dataclass
class Goal:
    """A goal to achieve in the game."""
    goal_type: GoalType
    description: str
    parameters: Dict[str, Any] = field(default_factory=dict)
    preconditions: List['Goal'] = field(default_factory=list)
    priority: int = 0

    @classmethod
    def reach_location(
        cls,
        area_id: int,
        x: int,
        y: int,
        tolerance: int = 16
    ) -> 'Goal':
        """Create a goal to reach a specific location."""
        return cls(
            goal_type=GoalType.REACH_LOCATION,
            description=f"Reach ({x}, {y}) in area 0x{area_id:02X}",
            parameters={
                "area_id": area_id,
                "x": x,
                "y": y,
                "tolerance": tolerance
            }
        )

    @classmethod
    def enter_building(cls, entrance_id: int) -> 'Goal':
        """Create a goal to enter a building."""
        return cls(
            goal_type=GoalType.ENTER_BUILDING,
            description=f"Enter building at entrance 0x{entrance_id:02X}",
            parameters={"entrance_id": entrance_id}
        )

    @classmethod
    def exit_building(cls) -> 'Goal':
        """Create a goal to exit current building."""
        return cls(
            goal_type=GoalType.EXIT_BUILDING,
            description="Exit current building to overworld"
        )

    @classmethod
    def talk_to_npc(cls, npc_id: int) -> 'Goal':
        """Create a goal to talk to an NPC."""
        return cls(
            goal_type=GoalType.TALK_TO_NPC,
            description=f"Talk to NPC 0x{npc_id:02X}",
            parameters={"npc_id": npc_id}
        )

    @classmethod
    def get_item(cls, item_id: int) -> 'Goal':
        """Create a goal to obtain an item."""
        return cls(
            goal_type=GoalType.GET_ITEM,
            description=f"Get item 0x{item_id:02X}",
            parameters={"item_id": item_id}
        )

    @classmethod
    def defeat_enemy(cls, sprite_id: Optional[int] = None) -> 'Goal':
        """Create a goal to defeat enemy/enemies."""
        desc = f"Defeat sprite 0x{sprite_id:02X}" if sprite_id else "Defeat all enemies"
        return cls(
            goal_type=GoalType.DEFEAT_ENEMY,
            description=desc,
            parameters={"sprite_id": sprite_id}
        )


@dataclass
class Action:
    """A single action in a plan."""
    name: str
    description: str
    input_sequence: Optional[InputSequence] = None
    condition: Optional[Callable[[ParsedGameState], bool]] = None
    timeout_frames: int = 600  # 10 seconds default

    def is_complete(self, state: ParsedGameState) -> bool:
        """Check if action completed based on state."""
        if self.condition:
            return self.condition(state)
        return True  # No condition = always complete after execution


@dataclass
class Plan:
    """A sequence of actions to achieve a goal."""
    goal: Goal
    actions: List[Action] = field(default_factory=list)
    status: PlanStatus = PlanStatus.NOT_STARTED
    current_action_index: int = 0
    execution_log: List[str] = field(default_factory=list)

    @property
    def current_action(self) -> Optional[Action]:
        """Get current action to execute."""
        if self.current_action_index < len(self.actions):
            return self.actions[self.current_action_index]
        return None

    def add_action(self, action: Action) -> None:
        """Add action to plan."""
        self.actions.append(action)

    def advance(self) -> bool:
        """Advance to next action. Returns True if more actions remain."""
        self.current_action_index += 1
        return self.current_action_index < len(self.actions)

    def log(self, message: str) -> None:
        """Add log entry."""
        self.execution_log.append(message)


class ActionPlanner:
    """High-level planner for gameplay goals.

    This planner creates and executes plans to achieve goals,
    using game state awareness to make decisions.
    """

    def __init__(
        self,
        emulator: Optional[EmulatorInterface] = None,
        parser: Optional[GameStateParser] = None
    ):
        """Initialize planner.

        Args:
            emulator: Emulator interface (optional for planning-only)
            parser: Game state parser
        """
        self._emu = emulator
        self._parser = parser or GameStateParser()
        self._logger = logging.getLogger(__name__)

    def create_plan(self, goal: Goal) -> Plan:
        """Create a plan to achieve a goal.

        Args:
            goal: Goal to achieve

        Returns:
            Plan with actions to execute
        """
        plan = Plan(goal=goal)

        if goal.goal_type == GoalType.REACH_LOCATION:
            self._plan_reach_location(plan, goal)
        elif goal.goal_type == GoalType.ENTER_BUILDING:
            self._plan_enter_building(plan, goal)
        elif goal.goal_type == GoalType.EXIT_BUILDING:
            self._plan_exit_building(plan, goal)
        elif goal.goal_type == GoalType.DEFEAT_ENEMY:
            self._plan_defeat_enemy(plan, goal)
        else:
            plan.log(f"No planner implemented for {goal.goal_type}")
            plan.status = PlanStatus.FAILED

        return plan

    def _plan_reach_location(self, plan: Plan, goal: Goal) -> None:
        """Plan to reach a specific location."""
        target_x = goal.parameters["x"]
        target_y = goal.parameters["y"]
        tolerance = goal.parameters.get("tolerance", 16)

        # Create condition for reaching target
        def at_target(state: ParsedGameState) -> bool:
            dx = abs(state.link_position[0] - target_x)
            dy = abs(state.link_position[1] - target_y)
            return dx <= tolerance and dy <= tolerance

        # For now, create a simple walk toward target
        # A real implementation would use pathfinding

        # Create walk sequences for each direction
        # This is a simplified version - real planner would calculate path

        plan.add_action(Action(
            name="navigate_to_target",
            description=f"Navigate to ({target_x}, {target_y})",
            condition=at_target,
            timeout_frames=1800  # 30 seconds
        ))

        plan.log("Created navigation plan (simplified)")

    def _plan_enter_building(self, plan: Plan, goal: Goal) -> None:
        """Plan to enter a building."""
        # Walk toward entrance and press up
        walk_up = create_walk_sequence("UP", 2)

        def is_indoors(state: ParsedGameState) -> bool:
            return state.is_indoors

        plan.add_action(Action(
            name="approach_entrance",
            description="Walk toward building entrance",
            input_sequence=walk_up,
            timeout_frames=120
        ))

        plan.add_action(Action(
            name="wait_for_transition",
            description="Wait for building entry transition",
            condition=is_indoors,
            timeout_frames=300
        ))

        plan.log("Created building entry plan")

    def _plan_exit_building(self, plan: Plan, goal: Goal) -> None:
        """Plan to exit current building."""
        walk_down = create_walk_sequence("DOWN", 3)

        def is_overworld(state: ParsedGameState) -> bool:
            return state.phase == GamePhase.OVERWORLD

        plan.add_action(Action(
            name="walk_to_exit",
            description="Walk toward exit",
            input_sequence=walk_down,
            timeout_frames=120
        ))

        plan.add_action(Action(
            name="wait_for_transition",
            description="Wait for exit transition",
            condition=is_overworld,
            timeout_frames=300
        ))

        plan.log("Created building exit plan")

    def _plan_defeat_enemy(self, plan: Plan, goal: Goal) -> None:
        """Plan to defeat enemies."""
        from .input_recorder import create_attack_sequence

        attack_seq = create_attack_sequence()

        # Simple: just attack repeatedly
        # Real implementation would track enemy positions

        def no_enemies(state: ParsedGameState) -> bool:
            # Would check sprite slots for enemies
            # For now, assume complete after some attacks
            return False  # Placeholder

        for i in range(5):  # Try 5 attacks
            plan.add_action(Action(
                name=f"attack_{i+1}",
                description=f"Attack #{i+1}",
                input_sequence=attack_seq,
                timeout_frames=60
            ))

        plan.log("Created combat plan (5 attacks)")

    def execute_plan(
        self,
        plan: Plan,
        callback: Optional[Callable[[Plan, ParsedGameState], None]] = None
    ) -> PlanStatus:
        """Execute a plan on the emulator.

        Args:
            plan: Plan to execute
            callback: Optional callback(plan, state) called each frame

        Returns:
            Final plan status
        """
        if self._emu is None:
            plan.log("ERROR: No emulator connected")
            plan.status = PlanStatus.FAILED
            return plan.status

        plan.status = PlanStatus.IN_PROGRESS
        plan.log("Starting plan execution")

        from .input_recorder import InputPlayer
        player = InputPlayer(self._emu)

        while plan.current_action:
            action = plan.current_action
            plan.log(f"Executing: {action.name}")

            # Execute input sequence if present
            if action.input_sequence:
                success = player.play(action.input_sequence)
                if not success:
                    plan.log(f"Failed to execute input for {action.name}")
                    plan.status = PlanStatus.FAILED
                    return plan.status

            # Wait for condition if present
            if action.condition:
                frames_waited = 0
                while frames_waited < action.timeout_frames:
                    if not self._emu.step_frame(1):
                        plan.log("Emulator step failed")
                        plan.status = PlanStatus.FAILED
                        return plan.status

                    raw_state = self._emu.read_state()
                    state = self._parser.parse(raw_state)

                    if callback:
                        callback(plan, state)

                    if action.is_complete(state):
                        plan.log(f"Completed: {action.name}")
                        break

                    # Check for black screen (stuck)
                    if state.is_black_screen:
                        plan.log(f"BLACK SCREEN detected during {action.name}")
                        plan.status = PlanStatus.BLOCKED
                        return plan.status

                    frames_waited += 1

                if frames_waited >= action.timeout_frames:
                    plan.log(f"Timeout waiting for {action.name}")
                    plan.status = PlanStatus.FAILED
                    return plan.status

            # Advance to next action
            if not plan.advance():
                break

        plan.status = PlanStatus.COMPLETED
        plan.log("Plan completed successfully")
        return plan.status

    def get_current_state(self) -> Optional[ParsedGameState]:
        """Get current game state if connected."""
        if self._emu is None or not self._emu.is_connected():
            return None
        raw = self._emu.read_state()
        return self._parser.parse(raw)


# =============================================================================
# Pre-built Navigation Goals
# =============================================================================

def goal_reach_village_center() -> Goal:
    """Goal to reach village center (area 0x29)."""
    return Goal.reach_location(
        area_id=0x29,
        x=512,
        y=480,
        tolerance=32
    )


def goal_reach_dungeon1_entrance() -> Goal:
    """Goal to reach Dungeon 1 entrance.

    This is the primary Goal A target.
    """
    # Zora Temple entrance is in area with specific coordinates
    return Goal.reach_location(
        area_id=0x1E,  # Zora Sanctuary area
        x=256,
        y=256,
        tolerance=32
    )


def goal_complete_dungeon1() -> Goal:
    """Goal to complete Dungeon 1 (Zora Temple)."""
    return Goal(
        goal_type=GoalType.COMPLETE_DUNGEON,
        description="Complete Zora Temple",
        parameters={"dungeon_id": 0x06}  # Zora Temple
    )
