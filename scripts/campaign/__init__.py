"""
Oracle of Secrets Autonomous Campaign Tools

This package contains tools built during the autonomous exploration campaign.
Each module provides capabilities for different aspects of gameplay automation
and debugging.

Modules:
- emulator_abstraction: Unified interface for Mesen2
- game_state: State parsing and awareness
- pathfinder: Collision-aware navigation
- action_planner: Goal-oriented action planning
- input_recorder: Record and playback input sequences
- visual_verifier: Screenshot comparison and verification

Usage:
    from scripts.campaign import emulator_abstraction
    emu = emulator_abstraction.get_emulator("mesen2")
    emu.connect()
    state = emu.read_game_state()
"""

__version__ = "0.1.0"
__campaign_start__ = "2026-01-24"

# Import available modules
from .emulator_abstraction import (
    EmulatorInterface,
    EmulatorStatus,
    GameStateSnapshot,
    Mesen2Emulator,
    MemoryRead,
    get_emulator,
)
from .game_state import (
    GamePhase,
    GameStateParser,
    LinkAction,
    ParsedGameState,
    get_parser,
    parse_state,
)
from .locations import (
    DUNGEONS,
    ENTRANCE_NAMES,
    OVERWORLD_AREAS,
    ROOM_NAMES,
    get_area_name,
    get_coverage_stats,
    get_dungeon_name,
    get_entrance_name,
    get_location_description,
    get_room_name,
)
from .pathfinder import (
    TileType,
    CollisionMap,
    Pathfinder,
    NavigationResult,
    get_pathfinder,
    find_path,
)
from .input_recorder import (
    Button,
    InputFrame,
    InputSequence,
    InputRecorder,
    InputPlayer,
    create_boot_sequence,
    create_walk_sequence,
    create_menu_open_sequence,
    create_attack_sequence,
)
from .action_planner import (
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
from .campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
    CampaignOrchestrator,
    create_campaign,
    quick_status,
)
from .verification import (
    VerificationLevel,
    MemoryCheck,
    VerificationResult as StrictVerificationResult,
    VerificationReport as StrictVerificationReport,
    CriticalAddresses,
    StrictVerifier,
    PLAYABLE_STATE_CHECKS,
    MOVEMENT_CHECKS,
    BLACK_SCREEN_CHECKS,
)
from .visual_verifier import (
    VerificationResult,
    Screenshot,
    VerificationReport,
    VisualVerifier,
    create_verifier,
    quick_black_screen_check,
)
from .progress_validator import (
    StoryFlag,
    GameStateValue,
    ProgressAddresses,
    ProgressSnapshot,
    ProgressReport,
    ProgressValidator,
    print_progress_report,
)
from .file_select_navigator import (
    FileSelectState,
    FileSlotStatus,
    SelectionResult,
    FileSlotInfo,
    FileSelectSnapshot,
    NavigationAttempt,
    FileSelectNavigator,
    create_file_select_sequence,
    create_new_game_sequence,
)

__all__ = [
    # Emulator abstraction
    "EmulatorInterface",
    "EmulatorStatus",
    "GameStateSnapshot",
    "Mesen2Emulator",
    "MemoryRead",
    "get_emulator",
    # Game state parsing
    "GamePhase",
    "GameStateParser",
    "LinkAction",
    "ParsedGameState",
    "get_parser",
    "parse_state",
    # Location data
    "DUNGEONS",
    "ENTRANCE_NAMES",
    "OVERWORLD_AREAS",
    "ROOM_NAMES",
    "get_area_name",
    "get_coverage_stats",
    "get_dungeon_name",
    "get_entrance_name",
    "get_location_description",
    "get_room_name",
    # Pathfinding
    "TileType",
    "CollisionMap",
    "Pathfinder",
    "NavigationResult",
    "get_pathfinder",
    "find_path",
    # Input recording
    "Button",
    "InputFrame",
    "InputSequence",
    "InputRecorder",
    "InputPlayer",
    "create_boot_sequence",
    "create_walk_sequence",
    "create_menu_open_sequence",
    "create_attack_sequence",
    # Action planning
    "GoalType",
    "PlanStatus",
    "Goal",
    "Action",
    "Plan",
    "ActionPlanner",
    "goal_reach_village_center",
    "goal_reach_dungeon1_entrance",
    "goal_complete_dungeon1",
    # Campaign orchestration
    "CampaignPhase",
    "MilestoneStatus",
    "CampaignMilestone",
    "CampaignProgress",
    "CampaignOrchestrator",
    "create_campaign",
    "quick_status",
    # Visual verification
    "VerificationResult",
    "Screenshot",
    "VerificationReport",
    "VisualVerifier",
    "create_verifier",
    "quick_black_screen_check",
    # Progress validation
    "StoryFlag",
    "GameStateValue",
    "ProgressAddresses",
    "ProgressSnapshot",
    "ProgressReport",
    "ProgressValidator",
    "print_progress_report",
    # File select navigation
    "FileSelectState",
    "FileSlotStatus",
    "SelectionResult",
    "FileSlotInfo",
    "FileSelectSnapshot",
    "NavigationAttempt",
    "FileSelectNavigator",
    "create_file_select_sequence",
    "create_new_game_sequence",
    # Autonomous debugger
    "Anomaly",
    "AnomalyReport",
    "SoftLockDetector",
    "DebugSession",
]

# Note: `autonomous_debugger` provides a standalone CLI entry point and is
# typically executed via `python -m scripts.campaign.autonomous_debugger`.
# Importing it eagerly from here triggers the standard runpy RuntimeWarning
# (module found in sys.modules prior to execution). Keep these exports lazy.
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .autonomous_debugger import (  # noqa: F401
        Anomaly,
        AnomalyReport,
        SoftLockDetector,
        DebugSession,
    )

_AUTONOMOUS_DEBUGGER_EXPORTS = {
    "Anomaly",
    "AnomalyReport",
    "SoftLockDetector",
    "DebugSession",
}


def __getattr__(name: str):
    if name in _AUTONOMOUS_DEBUGGER_EXPORTS:
        from . import autonomous_debugger as _autonomous_debugger

        return getattr(_autonomous_debugger, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")


def __dir__():
    return sorted(list(globals().keys()) + list(_AUTONOMOUS_DEBUGGER_EXPORTS))
