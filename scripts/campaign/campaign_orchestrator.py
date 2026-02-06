"""Campaign orchestrator for Oracle of Secrets autonomous exploration.

This module coordinates all campaign components to achieve gameplay goals:
- Emulator connection and state management
- Game state parsing and awareness
- Input recording and playback
- Goal-oriented action planning
- Progress tracking and logging

Campaign Goals Supported:
- A.1-A.5: Autonomous Gameplay (boot → Dungeon 1 completion)
- B.1-B.5: Black Screen Bug Detection
- D.1-D.5: Intelligent Agent Tooling

Usage:
    from scripts.campaign.campaign_orchestrator import CampaignOrchestrator

    orchestrator = CampaignOrchestrator()
    orchestrator.connect()
    orchestrator.run_campaign()
"""

from __future__ import annotations

import json
import logging
import tempfile
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot, Mesen2Emulator
from .game_state import GamePhase, GameStateParser, ParsedGameState, parse_state
from .input_recorder import (
    Button,
    InputPlayer,
    InputRecorder,
    InputSequence,
    create_boot_sequence,
    create_walk_sequence,
)
from .action_planner import (
    ActionPlanner,
    Goal,
    GoalType,
    Plan,
    PlanStatus,
    goal_reach_village_center,
    goal_reach_dungeon1_entrance,
    goal_complete_dungeon1,
)


class CampaignPhase(Enum):
    """High-level campaign phases."""
    DISCONNECTED = auto()
    CONNECTING = auto()
    BOOTING = auto()
    EXPLORING = auto()
    NAVIGATING = auto()
    IN_DUNGEON = auto()
    COMPLETED = auto()
    FAILED = auto()


class MilestoneStatus(Enum):
    """Status of campaign milestones."""
    NOT_STARTED = auto()
    IN_PROGRESS = auto()
    COMPLETED = auto()
    BLOCKED = auto()


@dataclass
class CampaignMilestone:
    """A campaign milestone to achieve."""
    id: str
    description: str
    goal: str  # Campaign goal (A.1, B.2, etc.)
    status: MilestoneStatus = MilestoneStatus.NOT_STARTED
    completed_at: Optional[datetime] = None
    notes: List[str] = field(default_factory=list)

    def complete(self, note: str = "") -> None:
        """Mark milestone as completed."""
        self.status = MilestoneStatus.COMPLETED
        self.completed_at = datetime.now()
        if note:
            self.notes.append(note)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize milestone."""
        return {
            "id": self.id,
            "description": self.description,
            "goal": self.goal,
            "status": self.status.name,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "notes": self.notes
        }


@dataclass
class CampaignProgress:
    """Tracks overall campaign progress."""
    milestones: Dict[str, CampaignMilestone] = field(default_factory=dict)
    current_phase: CampaignPhase = CampaignPhase.DISCONNECTED
    iterations_completed: int = 0
    total_frames_played: int = 0
    black_screens_detected: int = 0
    transitions_completed: int = 0
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None

    def add_milestone(self, milestone: CampaignMilestone) -> None:
        """Add a milestone to track."""
        self.milestones[milestone.id] = milestone

    def complete_milestone(self, milestone_id: str, note: str = "") -> bool:
        """Mark a milestone as completed."""
        if milestone_id in self.milestones:
            self.milestones[milestone_id].complete(note)
            self.last_update = datetime.now()
            return True
        return False

    def get_completion_percentage(self) -> float:
        """Get percentage of milestones completed."""
        if not self.milestones:
            return 0.0
        completed = sum(
            1 for m in self.milestones.values()
            if m.status == MilestoneStatus.COMPLETED
        )
        return (completed / len(self.milestones)) * 100

    def to_dict(self) -> Dict[str, Any]:
        """Serialize progress."""
        return {
            "current_phase": self.current_phase.name,
            "iterations_completed": self.iterations_completed,
            "total_frames_played": self.total_frames_played,
            "black_screens_detected": self.black_screens_detected,
            "transitions_completed": self.transitions_completed,
            "completion_percentage": self.get_completion_percentage(),
            "start_time": self.start_time.isoformat() if self.start_time else None,
            "last_update": self.last_update.isoformat() if self.last_update else None,
            "milestones": {k: v.to_dict() for k, v in self.milestones.items()}
        }


class CampaignOrchestrator:
    """Orchestrates the autonomous campaign.

    This class coordinates all campaign components to achieve
    the grand goals of autonomous gameplay and debugging.
    """

    def __init__(
        self,
        emulator: Optional[EmulatorInterface] = None,
        log_dir: Optional[Path] = None
    ):
        """Initialize orchestrator.

        Args:
            emulator: Emulator interface (creates Mesen2Emulator if None)
            log_dir: Directory for campaign logs
        """
        self._emu = emulator or Mesen2Emulator()
        self._parser = GameStateParser()
        self._planner = ActionPlanner(self._emu, self._parser)
        self._player = InputPlayer(self._emu) if emulator else None
        self._recorder = InputRecorder("campaign_recording")

        # Default to /tmp to avoid dirtying the repo with runtime artifacts.
        self._log_dir = log_dir or (Path(tempfile.gettempdir()) / "oos_campaign" / "logs")
        self._logger = logging.getLogger(__name__)

        self._progress = CampaignProgress()
        self._current_state: Optional[ParsedGameState] = None
        self._current_plan: Optional[Plan] = None

        self._setup_milestones()

    def _setup_milestones(self) -> None:
        """Initialize campaign milestones."""
        milestones = [
            CampaignMilestone("boot_playable", "Boot to playable state", "A.1"),
            CampaignMilestone("reach_village", "Reach village center", "A.2"),
            CampaignMilestone("reach_dungeon1", "Reach Dungeon 1 entrance", "A.2"),
            CampaignMilestone("enter_dungeon1", "Enter Dungeon 1", "A.3"),
            CampaignMilestone("complete_dungeon1", "Complete Dungeon 1", "A.4"),
            CampaignMilestone("no_black_screen", "No black screen bugs detected", "B.1"),
            CampaignMilestone("transition_test", "All transitions tested", "B.5"),
            CampaignMilestone("emulator_connected", "Emulator abstraction working", "C.1"),
            CampaignMilestone("state_parsing", "Game state parsing working", "D.1"),
            CampaignMilestone("input_playback", "Input recording/playback working", "D.4"),
            CampaignMilestone("action_planning", "Action planner working", "D.5"),
        ]
        for m in milestones:
            self._progress.add_milestone(m)

    def connect(self, timeout: float = 5.0) -> bool:
        """Connect to emulator.

        Args:
            timeout: Connection timeout in seconds (forwarded if supported)

        Returns:
            True if connected successfully
        """
        self._progress.current_phase = CampaignPhase.CONNECTING
        self._logger.info("Connecting to emulator...")

        try:
            try:
                ok = self._emu.connect(timeout)
            except TypeError:
                # Some emulator implementations don't accept a timeout param.
                ok = self._emu.connect()
        except TimeoutError:
            # Let callers decide whether/how to retry.
            raise
        except Exception as e:
            self._logger.error("Connection failed: %s", e)
            self._progress.current_phase = CampaignPhase.FAILED
            return False

        if ok:
            self._progress.current_phase = CampaignPhase.BOOTING
            self._progress.complete_milestone(
                "emulator_connected",
                f"Connected at {datetime.now().isoformat()}"
            )
            self._player = InputPlayer(self._emu)
            self._logger.info("Connected to emulator")
            return True

        self._progress.current_phase = CampaignPhase.FAILED
        return False

    def disconnect(self) -> None:
        """Disconnect from emulator."""
        if self._emu:
            self._emu.disconnect()
        self._progress.current_phase = CampaignPhase.DISCONNECTED

    def get_state(self) -> Optional[ParsedGameState]:
        """Get current parsed game state."""
        if not self._emu or not self._emu.is_connected():
            return None

        raw = self._emu.read_state()
        self._current_state = self._parser.parse(raw)

        # Track black screens
        if self._current_state.is_black_screen and self._current_state.is_playing:
            self._progress.black_screens_detected += 1
            self._logger.warning(
                f"Black screen detected! Total: {self._progress.black_screens_detected}"
            )

        return self._current_state

    def execute_boot_sequence(self) -> bool:
        """Execute boot sequence to reach playable state.

        Returns:
            True if boot successful and game is playable
        """
        if not self._player:
            self._logger.error("No input player available")
            return False

        self._logger.info("Executing boot sequence...")
        boot_seq = create_boot_sequence()

        frames_played = 0

        def frame_callback(frame: int, state: GameStateSnapshot) -> None:
            nonlocal frames_played
            frames_played += 1
            parsed = self._parser.parse(state)
            if frames_played % 60 == 0:
                self._logger.debug(
                    f"Frame {frame}: Mode={parsed.mode_name}, "
                    f"Phase={parsed.phase.name}"
                )

        success = self._player.play(boot_seq, callback=frame_callback)
        self._progress.total_frames_played += frames_played

        if success:
            state = self.get_state()
            if state and state.is_playing:
                self._progress.complete_milestone("boot_playable")
                self._progress.complete_milestone("state_parsing")
                self._progress.complete_milestone("input_playback")
                self._logger.info("Boot successful - game is playable")
                return True

        self._logger.error("Boot sequence failed")
        return False

    def navigate_to_goal(self, goal: Goal) -> PlanStatus:
        """Navigate to achieve a goal.

        Args:
            goal: Goal to achieve

        Returns:
            Final plan status
        """
        self._logger.info(f"Creating plan for: {goal.description}")
        plan = self._planner.create_plan(goal)
        self._current_plan = plan

        def plan_callback(plan: Plan, state: ParsedGameState) -> None:
            self._progress.total_frames_played += 1

            # Track transitions
            if state.phase == GamePhase.TRANSITION:
                self._progress.transitions_completed += 1

            # Log progress periodically
            if self._progress.total_frames_played % 300 == 0:
                self._logger.debug(
                    f"Plan progress: Action {plan.current_action_index + 1}/"
                    f"{len(plan.actions)}, Phase: {state.phase.name}"
                )

        self._progress.current_phase = CampaignPhase.NAVIGATING
        status = self._planner.execute_plan(plan, callback=plan_callback)

        if status == PlanStatus.COMPLETED:
            self._progress.complete_milestone("action_planning")
            self._logger.info(f"Goal achieved: {goal.description}")
        else:
            self._logger.warning(f"Plan ended with status: {status.name}")

        return status

    def run_exploration_iteration(self) -> bool:
        """Run one exploration iteration.

        Returns:
            True if iteration completed successfully
        """
        self._logger.info(
            f"Starting iteration {self._progress.iterations_completed + 1}"
        )

        state = self.get_state()
        if not state:
            self._logger.error("Cannot read game state")
            return False

        # Log current state
        self._logger.info(
            f"Current state: Phase={state.phase.name}, "
            f"Position=({state.link_position[0]}, {state.link_position[1]}), "
            f"Area=0x{state.area_id:02X}"
        )

        # Check for black screen bug
        if state.is_black_screen and state.is_playing:
            self._logger.error("BLACK SCREEN BUG DETECTED!")
            self._progress.current_phase = CampaignPhase.FAILED
            return False

        # Determine next goal based on progress
        if "reach_village" not in [
            m.id for m in self._progress.milestones.values()
            if m.status == MilestoneStatus.COMPLETED
        ]:
            goal = goal_reach_village_center()
        elif "reach_dungeon1" not in [
            m.id for m in self._progress.milestones.values()
            if m.status == MilestoneStatus.COMPLETED
        ]:
            goal = goal_reach_dungeon1_entrance()
        else:
            self._logger.info("All navigation goals completed!")
            return True

        # Execute goal
        status = self.navigate_to_goal(goal)

        if status == PlanStatus.COMPLETED:
            if goal.goal_type == GoalType.REACH_LOCATION:
                if goal.parameters.get("area_id") == 0x29:
                    self._progress.complete_milestone("reach_village")
                elif goal.parameters.get("area_id") == 0x1E:
                    self._progress.complete_milestone("reach_dungeon1")

        self._progress.iterations_completed += 1
        self._progress.last_update = datetime.now()

        return status == PlanStatus.COMPLETED

    def run_campaign(self, max_iterations: int = 10) -> CampaignProgress:
        """Run the full campaign.

        Args:
            max_iterations: Maximum iterations to run

        Returns:
            Final campaign progress
        """
        self._progress.start_time = datetime.now()
        self._logger.info("Starting autonomous campaign")

        # Connect to emulator
        if not self.connect():
            self._logger.error("Failed to connect to emulator")
            return self._progress

        # Boot to playable
        if not self.execute_boot_sequence():
            self._logger.error("Failed to boot to playable state")
            return self._progress

        self._progress.current_phase = CampaignPhase.EXPLORING

        # Run exploration iterations
        for i in range(max_iterations):
            self._logger.info(f"=== Iteration {i + 1}/{max_iterations} ===")

            if not self.run_exploration_iteration():
                self._logger.warning(f"Iteration {i + 1} failed")
                break

            # Check if all goals achieved
            completion = self._progress.get_completion_percentage()
            self._logger.info(f"Campaign completion: {completion:.1f}%")

            if completion >= 100:
                self._progress.current_phase = CampaignPhase.COMPLETED
                break

        self._progress.last_update = datetime.now()
        self._save_progress()

        return self._progress

    def _save_progress(self) -> None:
        """Save campaign progress to file."""
        self._log_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        progress_file = self._log_dir / f"progress_{timestamp}.json"

        with open(progress_file, "w") as f:
            json.dump(self._progress.to_dict(), f, indent=2)

        self._logger.info(f"Progress saved to {progress_file}")

    def get_status_report(self) -> str:
        """Generate human-readable status report."""
        lines = [
            "=" * 60,
            "ORACLE OF SECRETS AUTONOMOUS CAMPAIGN STATUS",
            "=" * 60,
            f"Phase: {self._progress.current_phase.name}",
            f"Iterations: {self._progress.iterations_completed}",
            f"Frames Played: {self._progress.total_frames_played}",
            f"Black Screens: {self._progress.black_screens_detected}",
            f"Transitions: {self._progress.transitions_completed}",
            f"Completion: {self._progress.get_completion_percentage():.1f}%",
            "",
            "MILESTONES:",
        ]

        for m in self._progress.milestones.values():
            status_icon = {
                MilestoneStatus.NOT_STARTED: "[ ]",
                MilestoneStatus.IN_PROGRESS: "[~]",
                MilestoneStatus.COMPLETED: "[✓]",
                MilestoneStatus.BLOCKED: "[X]",
            }.get(m.status, "[?]")
            lines.append(f"  {status_icon} {m.goal}: {m.description}")

        lines.append("=" * 60)
        return "\n".join(lines)


# =============================================================================
# Utility Functions
# =============================================================================

def create_campaign(log_dir: Optional[Path] = None) -> CampaignOrchestrator:
    """Create a campaign orchestrator instance.

    Args:
        log_dir: Optional log directory

    Returns:
        Configured orchestrator
    """
    return CampaignOrchestrator(log_dir=log_dir)


def quick_status() -> str:
    """Get quick status without connecting to emulator.

    Returns:
        Status message about campaign infrastructure
    """
    lines = [
        "Campaign Infrastructure Status:",
        "  ✓ EmulatorInterface available",
        "  ✓ GameStateParser available",
        "  ✓ InputRecorder/Player available",
        "  ✓ ActionPlanner available",
        "  ✓ CampaignOrchestrator available",
        "",
        "To start campaign:",
        "  orchestrator = create_campaign()",
        "  orchestrator.run_campaign()",
    ]
    return "\n".join(lines)
