"""Tests for module-level API and factory functions.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Clean module API

These tests verify the public API exported from scripts.campaign,
ensuring factory functions and convenience wrappers work correctly.
"""

import pytest
from pathlib import Path
import tempfile

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))


class TestEmulatorFactories:
    """Test emulator factory functions."""

    def test_get_emulator_mesen2(self):
        """Test get_emulator returns Mesen2Emulator."""
        from scripts.campaign import get_emulator, Mesen2Emulator

        emu = get_emulator("mesen2")
        assert isinstance(emu, Mesen2Emulator)

    def test_get_emulator_default(self):
        """Test get_emulator default is Mesen2."""
        from scripts.campaign import get_emulator, Mesen2Emulator

        emu = get_emulator()
        assert isinstance(emu, Mesen2Emulator)

    def test_get_emulator_invalid(self):
        """Test get_emulator raises for invalid type."""
        from scripts.campaign import get_emulator

        with pytest.raises((ValueError, KeyError)):
            get_emulator("invalid_emulator_type")


class TestParserFactories:
    """Test game state parser factory functions."""

    def test_get_parser(self):
        """Test get_parser returns GameStateParser."""
        from scripts.campaign import get_parser, GameStateParser

        parser = get_parser()
        assert isinstance(parser, GameStateParser)

    def test_parse_state_convenience(self):
        """Test parse_state convenience function."""
        from scripts.campaign import parse_state, GameStateSnapshot, ParsedGameState

        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        parsed = parse_state(snapshot)
        assert isinstance(parsed, ParsedGameState)


class TestPathfinderFactories:
    """Test pathfinder factory functions."""

    def test_get_pathfinder(self):
        """Test get_pathfinder returns Pathfinder."""
        from scripts.campaign import get_pathfinder, Pathfinder

        pathfinder = get_pathfinder()
        assert isinstance(pathfinder, Pathfinder)

    def test_find_path_convenience(self):
        """Test find_path convenience function."""
        from scripts.campaign import find_path, NavigationResult
        from scripts.campaign.pathfinder import TileType

        # Create walkable collision data for test
        collision_data = bytes([TileType.WALKABLE] * 4096)

        # Find path in open area with collision data provided
        result = find_path(start=(100, 100), goal=(150, 150), collision_data=collision_data)
        assert isinstance(result, NavigationResult)


class TestCampaignFactories:
    """Test campaign factory functions."""

    def test_create_campaign(self):
        """Test create_campaign returns CampaignOrchestrator."""
        from scripts.campaign import create_campaign, CampaignOrchestrator

        orchestrator = create_campaign()
        assert isinstance(orchestrator, CampaignOrchestrator)

    def test_quick_status(self):
        """Test quick_status returns string."""
        from scripts.campaign import quick_status

        status = quick_status()
        assert isinstance(status, str)
        assert len(status) > 0


class TestVerifierFactories:
    """Test visual verifier factory functions."""

    def test_create_verifier(self):
        """Test create_verifier returns VisualVerifier."""
        from scripts.campaign import create_verifier, VisualVerifier

        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline"
            capture = Path(tmpdir) / "capture"

            verifier = create_verifier(baseline_dir=baseline, capture_dir=capture)
            assert isinstance(verifier, VisualVerifier)

    def test_quick_black_screen_check(self):
        """Test quick_black_screen_check function."""
        from scripts.campaign import quick_black_screen_check

        # Non-existent file returns False
        result = quick_black_screen_check(Path("/nonexistent/file.png"))
        assert result is False


class TestInputFactories:
    """Test input sequence factory functions."""

    def test_create_boot_sequence(self):
        """Test create_boot_sequence returns InputSequence."""
        from scripts.campaign import create_boot_sequence, InputSequence

        seq = create_boot_sequence()
        assert isinstance(seq, InputSequence)
        assert seq.total_frames > 0

    def test_create_walk_sequence(self):
        """Test create_walk_sequence returns InputSequence."""
        from scripts.campaign import create_walk_sequence, InputSequence

        seq = create_walk_sequence("UP", tiles=3)
        assert isinstance(seq, InputSequence)
        assert seq.total_frames > 0

    def test_create_menu_open_sequence(self):
        """Test create_menu_open_sequence returns InputSequence."""
        from scripts.campaign import create_menu_open_sequence, InputSequence

        seq = create_menu_open_sequence()
        assert isinstance(seq, InputSequence)

    def test_create_attack_sequence(self):
        """Test create_attack_sequence returns InputSequence."""
        from scripts.campaign import create_attack_sequence, InputSequence

        seq = create_attack_sequence()
        assert isinstance(seq, InputSequence)


class TestGoalFactories:
    """Test goal factory functions."""

    def test_goal_reach_village_center(self):
        """Test goal_reach_village_center factory."""
        from scripts.campaign import goal_reach_village_center, Goal

        goal = goal_reach_village_center()
        assert isinstance(goal, Goal)
        assert goal.parameters["area_id"] == 0x29

    def test_goal_reach_dungeon1_entrance(self):
        """Test goal_reach_dungeon1_entrance factory."""
        from scripts.campaign import goal_reach_dungeon1_entrance, Goal

        goal = goal_reach_dungeon1_entrance()
        assert isinstance(goal, Goal)
        assert goal.parameters["area_id"] == 0x1E

    def test_goal_complete_dungeon1(self):
        """Test goal_complete_dungeon1 factory."""
        from scripts.campaign import goal_complete_dungeon1, Goal

        goal = goal_complete_dungeon1()
        assert isinstance(goal, Goal)


class TestExportedClasses:
    """Test that all expected classes are exported."""

    def test_emulator_classes(self):
        """Test emulator classes are exported."""
        from scripts.campaign import (
            EmulatorInterface,
            EmulatorStatus,
            GameStateSnapshot,
            Mesen2Emulator,
            MemoryRead
        )
        assert EmulatorInterface is not None
        assert EmulatorStatus is not None
        assert GameStateSnapshot is not None
        assert Mesen2Emulator is not None
        assert MemoryRead is not None

    def test_game_state_classes(self):
        """Test game state classes are exported."""
        from scripts.campaign import (
            GamePhase,
            GameStateParser,
            LinkAction,
            ParsedGameState
        )
        assert GamePhase is not None
        assert GameStateParser is not None
        assert LinkAction is not None
        assert ParsedGameState is not None

    def test_location_exports(self):
        """Test location data is exported."""
        from scripts.campaign import (
            DUNGEONS,
            ENTRANCE_NAMES,
            OVERWORLD_AREAS,
            ROOM_NAMES,
            get_area_name,
            get_coverage_stats,
            get_dungeon_name,
            get_entrance_name,
            get_location_description,
            get_room_name
        )
        assert DUNGEONS is not None
        assert OVERWORLD_AREAS is not None
        assert get_area_name is not None

    def test_pathfinder_classes(self):
        """Test pathfinder classes are exported."""
        from scripts.campaign import (
            TileType,
            CollisionMap,
            Pathfinder,
            NavigationResult
        )
        assert TileType is not None
        assert CollisionMap is not None
        assert Pathfinder is not None
        assert NavigationResult is not None

    def test_input_classes(self):
        """Test input classes are exported."""
        from scripts.campaign import (
            Button,
            InputFrame,
            InputSequence,
            InputRecorder,
            InputPlayer
        )
        assert Button is not None
        assert InputFrame is not None
        assert InputSequence is not None
        assert InputRecorder is not None
        assert InputPlayer is not None

    def test_action_planner_classes(self):
        """Test action planner classes are exported."""
        from scripts.campaign import (
            GoalType,
            PlanStatus,
            Goal,
            Action,
            Plan,
            ActionPlanner
        )
        assert GoalType is not None
        assert PlanStatus is not None
        assert Goal is not None
        assert Action is not None
        assert Plan is not None
        assert ActionPlanner is not None

    def test_orchestrator_classes(self):
        """Test orchestrator classes are exported."""
        from scripts.campaign import (
            CampaignPhase,
            MilestoneStatus,
            CampaignMilestone,
            CampaignProgress,
            CampaignOrchestrator
        )
        assert CampaignPhase is not None
        assert MilestoneStatus is not None
        assert CampaignMilestone is not None
        assert CampaignProgress is not None
        assert CampaignOrchestrator is not None

    def test_verifier_classes(self):
        """Test verifier classes are exported."""
        from scripts.campaign import (
            VerificationResult,
            Screenshot,
            VerificationReport,
            VisualVerifier
        )
        assert VerificationResult is not None
        assert Screenshot is not None
        assert VerificationReport is not None
        assert VisualVerifier is not None


class TestModuleMetadata:
    """Test module metadata."""

    def test_version_defined(self):
        """Test __version__ is defined."""
        from scripts.campaign import __version__
        assert __version__ is not None
        assert len(__version__) > 0

    def test_campaign_start_defined(self):
        """Test __campaign_start__ is defined."""
        from scripts.campaign import __campaign_start__
        assert __campaign_start__ is not None
        assert "2026" in __campaign_start__
