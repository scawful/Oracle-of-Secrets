"""Tests for error recovery and edge case handling in campaign modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Robust error handling in tooling

These tests verify that modules handle errors gracefully,
including connection failures, timeouts, invalid states, and unexpected data.
"""

import pytest
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
import tempfile
import socket

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import (
    GameStateSnapshot, Mesen2Emulator, EmulatorStatus
)
from scripts.campaign.game_state import (
    GamePhase, GameStateParser, ParsedGameState
)
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputPlayer, InputFrame
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, MilestoneStatus
)
from scripts.campaign.visual_verifier import (
    VisualVerifier, Screenshot, VerificationResult
)


class TestParserEdgeCases:
    """Test game state parser edge cases."""

    def test_parse_zero_state(self):
        """Test parsing all-zero state."""
        parser = GameStateParser()
        state = GameStateSnapshot(
            timestamp=0.0, mode=0, submode=0,
            area=0, room=0,
            link_x=0, link_y=0, link_z=0,
            link_direction=0, link_state=0,
            indoors=False, inidisp=0,
            health=0, max_health=0
        )
        parsed = parser.parse(state)
        # Should not raise, should return valid ParsedGameState
        assert parsed is not None
        assert isinstance(parsed.phase, GamePhase)

    def test_parse_max_values(self):
        """Test parsing maximum values."""
        parser = GameStateParser()
        state = GameStateSnapshot(
            timestamp=float('inf'), mode=0xFF, submode=0xFF,
            area=0xFF, room=0xFF,
            link_x=65535, link_y=65535, link_z=65535,
            link_direction=0xFF, link_state=0xFF,
            indoors=True, inidisp=0xFF,
            health=255, max_health=255
        )
        parsed = parser.parse(state)
        assert parsed is not None

    def test_parse_negative_timestamp(self):
        """Test parsing negative timestamp."""
        parser = GameStateParser()
        state = GameStateSnapshot(
            timestamp=-1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )
        parsed = parser.parse(state)
        assert parsed is not None


class TestInputSequenceEdgeCases:
    """Test input sequence edge cases."""

    def test_empty_sequence_total_frames(self):
        """Test empty input sequence reports zero frames."""
        seq = InputSequence(name="empty_test", frames=[])
        assert seq.total_frames == 0
        assert len(seq.frames) == 0

    def test_sequence_with_single_frame(self):
        """Test sequence with one frame."""
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=1)
        seq = InputSequence(name="single", frames=[frame])
        assert seq.total_frames == 1
        assert len(seq.frames) == 1

    def test_player_with_mock_disconnected(self):
        """Test InputPlayer behavior with disconnected emulator.

        Note: Current implementation doesn't check connection status during play,
        it relies on step_frame/inject_input to fail. This test documents the
        actual behavior.
        """
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False
        mock_emu.step_frame.return_value = True  # Mock still returns success
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        player = InputPlayer(mock_emu)
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=1)
        seq = InputSequence(name="test", frames=[frame])
        result = player.play(seq)
        # With mock returning success for operations, play completes
        # In real scenario, step_frame would fail and propagate
        assert result is True

    def test_play_empty_sequence_mock(self):
        """Test playing empty sequence with mock."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.inject_input.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        player = InputPlayer(mock_emu)
        seq = InputSequence(name="empty", frames=[])
        result = player.play(seq)
        # Empty sequence should "succeed" (nothing to do)
        assert result is True


class TestActionPlannerEdgeCases:
    """Test action planner edge cases."""

    def test_plan_with_disconnected_emulator(self):
        """Test planning when emulator is disconnected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False
        mock_emu.read_state.return_value = None

        planner = ActionPlanner(mock_emu)
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = planner.create_plan(goal)

        # Should return a plan (possibly empty or failed status)
        assert plan is not None
        assert isinstance(plan, Plan)

    def test_goal_with_extreme_coordinates(self):
        """Test goal with extreme coordinate values."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        planner = ActionPlanner(mock_emu)
        # Large coordinates
        goal = Goal.reach_location(area_id=0xFF, x=65535, y=65535)
        plan = planner.create_plan(goal)

        assert plan is not None

    def test_goal_enter_building(self):
        """Test enter building goal creation."""
        goal = Goal.enter_building(entrance_id=0x12)
        assert goal.goal_type == GoalType.ENTER_BUILDING
        assert goal.parameters["entrance_id"] == 0x12

    def test_goal_defeat_enemy_no_sprite(self):
        """Test defeat enemy goal without specific sprite."""
        goal = Goal.defeat_enemy()
        assert goal.goal_type == GoalType.DEFEAT_ENEMY
        assert goal.parameters.get("sprite_id") is None


class TestOrchestratorEdgeCases:
    """Test campaign orchestrator edge cases."""

    def test_get_state_when_disconnected(self):
        """Test get_state returns None when disconnected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        state = orchestrator.get_state()

        assert state is None

    def test_execute_boot_without_player(self):
        """Test boot execution when _player is explicitly None."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        # Explicitly set _player to None to test this path
        orchestrator._player = None
        result = orchestrator.execute_boot_sequence()

        assert result is False

    def test_milestone_completion_idempotent(self):
        """Test completing same milestone twice."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        mock_emu.is_connected.return_value = True

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        orchestrator.connect()

        # Complete same milestone twice
        success1 = orchestrator._progress.complete_milestone("emulator_connected", "First")
        success2 = orchestrator._progress.complete_milestone("emulator_connected", "Second")

        # Both should succeed (idempotent)
        assert success1 is True
        # Second completion adds to notes but doesn't fail
        milestone = orchestrator._progress.milestones["emulator_connected"]
        assert milestone.status == MilestoneStatus.COMPLETED

    def test_complete_nonexistent_milestone(self):
        """Test completing milestone that doesn't exist."""
        mock_emu = Mock()
        orchestrator = CampaignOrchestrator(emulator=mock_emu)

        result = orchestrator._progress.complete_milestone("nonexistent_milestone")
        assert result is False

    def test_progress_percentage_empty_milestones(self):
        """Test progress percentage with no milestones."""
        from scripts.campaign.campaign_orchestrator import CampaignProgress

        progress = CampaignProgress()
        progress.milestones.clear()

        pct = progress.get_completion_percentage()
        assert pct == 0.0

    def test_disconnect_idempotent(self):
        """Test disconnect when already disconnected."""
        mock_emu = Mock()
        mock_emu.disconnect.return_value = None

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        # Disconnect multiple times
        orchestrator.disconnect()
        orchestrator.disconnect()
        orchestrator.disconnect()

        assert orchestrator._progress.current_phase == CampaignPhase.DISCONNECTED


class TestVisualVerifierEdgeCases:
    """Test visual verifier edge cases."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            capture_dir = Path(tmpdir) / "captures"
            baseline_dir.mkdir()
            capture_dir.mkdir()
            yield baseline_dir, capture_dir

    def test_compare_both_missing(self, temp_dirs):
        """Test comparison when both files are missing."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        baseline = Screenshot(
            path=Path("/missing/baseline.png"),
            timestamp=datetime.now(),
            frame_number=0
        )
        current = Screenshot(
            path=Path("/missing/current.png"),
            timestamp=datetime.now(),
            frame_number=100
        )

        report = verifier.compare_screenshots(baseline, current)
        assert report.result == VerificationResult.ERROR

    def test_verify_transition_both_black(self, temp_dirs):
        """Test transition verification when both are black screens."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Both files are very small (black screens)
        before_path = capture_dir / "before.png"
        before_path.write_bytes(b"\x89PNG" + b"\x00" * 100)

        after_path = capture_dir / "after.png"
        after_path.write_bytes(b"\x89PNG" + b"\x00" * 100)

        before = Screenshot(
            path=before_path,
            timestamp=datetime.now(),
            frame_number=0,
            area_id=0x09
        )
        after = Screenshot(
            path=after_path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29
        )

        report = verifier.verify_transition(before, after, expected_area=0x29)
        # Should detect black screen in after
        assert report.result == VerificationResult.BLACK_SCREEN

    def test_screenshot_hash_missing_file(self):
        """Test screenshot hash with missing file."""
        screenshot = Screenshot(
            path=Path("/nonexistent/path/file.png"),
            timestamp=datetime.now(),
            frame_number=0
        )

        # Hash should return empty string for missing file
        assert screenshot.hash == ""

    def test_get_baseline_nonexistent_area(self, temp_dirs):
        """Test get_baseline for area with no baseline."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        baseline = verifier.get_baseline(0xFE)  # Very unlikely area ID
        assert baseline is None


class TestConcurrentAccess:
    """Test handling of concurrent access scenarios."""

    def test_multiple_connect_calls(self):
        """Test calling connect multiple times."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        orchestrator = CampaignOrchestrator(emulator=mock_emu)

        # Connect multiple times
        result1 = orchestrator.connect()
        result2 = orchestrator.connect()
        result3 = orchestrator.connect()

        # All should succeed without error
        assert result1 is True
        assert result2 is True
        assert result3 is True

    def test_state_read_race_condition(self):
        """Test rapid state reads don't cause issues."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True

        counter = [0]
        def get_state():
            counter[0] += 1
            return GameStateSnapshot(
                timestamp=float(counter[0]),
                mode=0x09, submode=0x00,
                area=0x29, room=0x00,
                link_x=512 + counter[0], link_y=480, link_z=0,
                link_direction=2, link_state=0,
                indoors=False, inidisp=0x0F,
                health=24, max_health=24
            )

        mock_emu.read_state.side_effect = get_state

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        orchestrator._emu = mock_emu  # Bypass connect

        # Rapid state reads
        states = [orchestrator.get_state() for _ in range(100)]

        # All should succeed
        assert all(s is not None for s in states)
        # Each should have different timestamp
        timestamps = [s.raw.timestamp for s in states]
        assert len(set(timestamps)) == 100


class TestDataSerialization:
    """Test serialization edge cases."""

    def test_progress_to_dict_with_none_times(self):
        """Test progress serialization with None timestamps."""
        from scripts.campaign.campaign_orchestrator import CampaignProgress

        progress = CampaignProgress()
        # start_time and last_update are None by default

        data = progress.to_dict()
        assert data["start_time"] is None
        assert data["last_update"] is None

    def test_milestone_to_dict_incomplete(self):
        """Test milestone serialization when not completed."""
        from scripts.campaign.campaign_orchestrator import CampaignMilestone

        milestone = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="T.1"
        )

        data = milestone.to_dict()
        assert data["status"] == "NOT_STARTED"
        assert data["completed_at"] is None

    def test_screenshot_to_dict_minimal(self):
        """Test screenshot serialization with minimal data."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime(2026, 1, 24, 12, 0, 0),
            frame_number=0
        )

        data = screenshot.to_dict()
        assert "path" in data
        assert "timestamp" in data
        assert "frame_number" in data

    def test_input_frame_to_dict(self):
        """Test input frame serialization."""
        frame = InputFrame(frame_number=100, buttons=Button.A | Button.B, hold_frames=5)
        data = frame.to_dict()

        assert data["frame"] == 100
        assert "A" in data["buttons"]
        assert "B" in data["buttons"]
        assert data["hold"] == 5

    def test_goal_parameters_serialization(self):
        """Test goal parameters can be accessed."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)

        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 512
        assert goal.parameters["y"] == 480
        assert goal.parameters["tolerance"] == 16  # default


class TestButtonFlags:
    """Test Button IntFlag operations."""

    def test_button_combinations(self):
        """Test combining multiple buttons."""
        combo = Button.A | Button.B | Button.UP
        assert combo & Button.A
        assert combo & Button.B
        assert combo & Button.UP
        assert not (combo & Button.DOWN)

    def test_button_from_string(self):
        """Test button from string conversion."""
        assert Button.from_string("A") == Button.A
        assert Button.from_string("a") == Button.A  # Case insensitive
        assert Button.from_string("invalid") == Button.NONE

    def test_button_from_strings(self):
        """Test button from multiple strings."""
        combo = Button.from_strings(["A", "B", "START"])
        assert combo & Button.A
        assert combo & Button.B
        assert combo & Button.START

    def test_button_to_strings(self):
        """Test button to string list conversion."""
        combo = Button.A | Button.START
        names = combo.to_strings()
        assert "A" in names
        assert "START" in names
        assert len(names) == 2
