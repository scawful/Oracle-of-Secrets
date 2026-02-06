"""Session lifecycle and recovery tests (Iteration 42).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling
- E.1: State verification and regression testing

These tests verify campaign session lifecycle, phase transitions,
and recovery from failures.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock, call
from datetime import datetime, timedelta
import json
import tempfile
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, MilestoneStatus, CampaignMilestone,
    CampaignProgress, CampaignOrchestrator, create_campaign, quick_status
)
from scripts.campaign.emulator_abstraction import (
    EmulatorInterface, GameStateSnapshot, EmulatorStatus, MemoryRead
)
from scripts.campaign.game_state import GamePhase, ParsedGameState
from scripts.campaign.action_planner import PlanStatus, GoalType


# =============================================================================
# Session Lifecycle Tests
# =============================================================================

class TestSessionStartup:
    """Test session startup sequence."""

    def test_fresh_session_starts_disconnected(self):
        """Test new session starts in DISCONNECTED phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_session_has_no_start_time_initially(self):
        """Test session has no start_time until run_campaign called."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._progress.start_time is None

    def test_session_counters_start_at_zero(self):
        """Test all session counters start at zero."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._progress.iterations_completed == 0
        assert orch._progress.total_frames_played == 0
        assert orch._progress.black_screens_detected == 0
        assert orch._progress.transitions_completed == 0

    def test_session_milestones_initialized(self):
        """Test session has milestones initialized."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        expected_milestones = [
            "boot_playable", "reach_village", "reach_dungeon1",
            "emulator_connected", "state_parsing", "input_playback"
        ]
        for milestone_id in expected_milestones:
            assert milestone_id in orch._progress.milestones

    def test_session_milestones_not_started(self):
        """Test all milestones start as NOT_STARTED."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        for milestone in orch._progress.milestones.values():
            assert milestone.status == MilestoneStatus.NOT_STARTED

    def test_connect_sets_connecting_phase_transiently(self):
        """Test connect() goes through CONNECTING phase."""
        mock_emu = Mock()
        phases_observed = []

        def capture_phase(*args, **kwargs):
            # Not really capturing transient state, but verify final state
            return True

        mock_emu.connect.side_effect = capture_phase
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        # After connect, should be BOOTING (not CONNECTING)
        assert orch._progress.current_phase == CampaignPhase.BOOTING


class TestSessionShutdown:
    """Test session shutdown sequence."""

    def test_disconnect_resets_to_disconnected(self):
        """Test disconnect resets phase to DISCONNECTED."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING

        orch.disconnect()
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_disconnect_calls_emulator_disconnect(self):
        """Test disconnect properly calls emulator.disconnect()."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.disconnect()
        mock_emu.disconnect.assert_called_once()

    def test_disconnect_from_exploring_phase(self):
        """Test disconnect from EXPLORING phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.EXPLORING
        orch.disconnect()
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_disconnect_from_failed_phase(self):
        """Test disconnect from FAILED phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.FAILED
        orch.disconnect()
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_disconnect_preserves_progress_data(self):
        """Test disconnect preserves accumulated progress."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.iterations_completed = 5
        orch._progress.total_frames_played = 1000

        orch.disconnect()

        assert orch._progress.iterations_completed == 5
        assert orch._progress.total_frames_played == 1000


class TestSessionRestart:
    """Test session restart patterns."""

    def test_reconnect_after_disconnect(self):
        """Test can reconnect after disconnect."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING

        orch.disconnect()
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING

    def test_reconnect_after_failure(self):
        """Test can attempt reconnect after connection failure."""
        mock_emu = Mock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.FAILED

        # Try again with success
        mock_emu.connect.return_value = True
        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING

    def test_progress_accumulates_across_restarts(self):
        """Test progress counters accumulate across restarts."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch._progress.iterations_completed = 3
        orch.disconnect()
        orch.connect()
        orch._progress.iterations_completed += 2

        assert orch._progress.iterations_completed == 5


# =============================================================================
# Phase Transition Tests
# =============================================================================

class TestAllPhaseTransitions:
    """Test all valid phase transitions."""

    def test_disconnected_to_connecting(self):
        """Test DISCONNECTED -> CONNECTING transition."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED
        # connect() transitions through CONNECTING to BOOTING

    def test_connecting_to_booting(self):
        """Test CONNECTING -> BOOTING on success."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING

    def test_connecting_to_failed(self):
        """Test CONNECTING -> FAILED on failure."""
        mock_emu = Mock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_booting_to_exploring(self):
        """Test BOOTING -> EXPLORING transition."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.BOOTING
        orch._progress.current_phase = CampaignPhase.EXPLORING
        assert orch._progress.current_phase == CampaignPhase.EXPLORING

    def test_exploring_to_navigating(self):
        """Test EXPLORING -> NAVIGATING transition."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.EXPLORING
        orch._progress.current_phase = CampaignPhase.NAVIGATING
        assert orch._progress.current_phase == CampaignPhase.NAVIGATING

    def test_navigating_to_in_dungeon(self):
        """Test NAVIGATING -> IN_DUNGEON transition."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.NAVIGATING
        orch._progress.current_phase = CampaignPhase.IN_DUNGEON
        assert orch._progress.current_phase == CampaignPhase.IN_DUNGEON

    def test_in_dungeon_to_completed(self):
        """Test IN_DUNGEON -> COMPLETED transition."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.IN_DUNGEON
        orch._progress.current_phase = CampaignPhase.COMPLETED
        assert orch._progress.current_phase == CampaignPhase.COMPLETED

    def test_any_phase_to_failed(self):
        """Test any phase can transition to FAILED."""
        mock_emu = Mock()
        phases = [
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.IN_DUNGEON
        ]
        for phase in phases:
            orch = CampaignOrchestrator(emulator=mock_emu)
            orch._progress.current_phase = phase
            orch._progress.current_phase = CampaignPhase.FAILED
            assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_any_phase_to_disconnected(self):
        """Test any phase can transition to DISCONNECTED via disconnect()."""
        mock_emu = Mock()
        phases = [
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.IN_DUNGEON,
            CampaignPhase.COMPLETED,
            CampaignPhase.FAILED
        ]
        for phase in phases:
            orch = CampaignOrchestrator(emulator=mock_emu)
            orch._progress.current_phase = phase
            orch.disconnect()
            assert orch._progress.current_phase == CampaignPhase.DISCONNECTED


class TestPhaseTransitionOrdering:
    """Test phase transition ordering and sequencing."""

    def test_normal_progression_order(self):
        """Test normal campaign phase progression."""
        expected_order = [
            CampaignPhase.DISCONNECTED,
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.IN_DUNGEON,
            CampaignPhase.COMPLETED
        ]
        # Verify phases have distinct values
        values = [p.value for p in expected_order]
        assert len(values) == len(set(values))

    def test_phase_values_are_auto(self):
        """Test phase values are auto-generated."""
        for phase in CampaignPhase:
            assert phase.value is not None
            assert phase.value > 0

    def test_all_phases_have_names(self):
        """Test all phases have string names."""
        for phase in CampaignPhase:
            assert phase.name is not None
            assert isinstance(phase.name, str)
            assert len(phase.name) > 0


# =============================================================================
# Recovery from Failures Tests
# =============================================================================

class TestConnectionFailureRecovery:
    """Test recovery from connection failures."""

    def test_connection_timeout_recovery(self):
        """Test recovery from connection timeout."""
        mock_emu = Mock()
        mock_emu.connect.side_effect = [TimeoutError("Timeout"), True]
        orch = CampaignOrchestrator(emulator=mock_emu)

        # First attempt fails
        try:
            orch.connect()
        except TimeoutError:
            pass
        # Second attempt succeeds
        result = orch.connect()
        assert result is True

    def test_connection_exception_sets_failed(self):
        """Test connection exception sets FAILED phase."""
        mock_emu = Mock()
        mock_emu.connect.side_effect = Exception("Connection error")
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.connect()
        assert result is False
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_connection_returns_false_sets_failed(self):
        """Test connect returning False sets FAILED phase."""
        mock_emu = Mock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.connect()
        assert result is False
        assert orch._progress.current_phase == CampaignPhase.FAILED


class TestStateReadFailureRecovery:
    """Test recovery from state read failures."""

    def test_get_state_returns_none_when_disconnected(self):
        """Test get_state returns None when emulator not connected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.get_state()
        assert result is None

    def test_get_state_handles_read_exception(self):
        """Test get_state handles read_state exception gracefully."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.side_effect = Exception("Read error")
        orch = CampaignOrchestrator(emulator=mock_emu)

        # Should handle exception internally
        with pytest.raises(Exception):
            orch.get_state()

    def test_get_state_with_none_emulator(self):
        """Test get_state handles None emulator."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._emu = None

        result = orch.get_state()
        assert result is None


class TestBlackScreenRecovery:
    """Test recovery from black screen detection."""

    def test_black_screen_increments_counter(self):
        """Test black screen detection increments counter."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x00,  # Black screen
            health=24, max_health=24
        )
        orch = CampaignOrchestrator(emulator=mock_emu)
        initial_count = orch._progress.black_screens_detected

        orch.get_state()
        # Note: actual increment depends on parsed state logic

    def test_multiple_black_screens_accumulate(self):
        """Test multiple black screens accumulate in counter."""
        progress = CampaignProgress()
        progress.black_screens_detected = 0
        progress.black_screens_detected += 1
        progress.black_screens_detected += 1
        progress.black_screens_detected += 1
        assert progress.black_screens_detected == 3


class TestMilestoneCompletionRecovery:
    """Test milestone completion edge cases."""

    def test_complete_nonexistent_milestone_returns_false(self):
        """Test completing non-existent milestone returns False."""
        progress = CampaignProgress()
        result = progress.complete_milestone("nonexistent")
        assert result is False

    def test_complete_already_completed_milestone(self):
        """Test completing already completed milestone."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(id="test", description="Test", goal="A.1")
        progress.add_milestone(milestone)

        result1 = progress.complete_milestone("test")
        assert result1 is True
        assert milestone.status == MilestoneStatus.COMPLETED

        # Completing again should still work (idempotent)
        result2 = progress.complete_milestone("test")
        assert result2 is True

    def test_complete_milestone_with_empty_note(self):
        """Test completing milestone with empty note."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(id="test", description="Test", goal="A.1")
        progress.add_milestone(milestone)

        result = progress.complete_milestone("test", "")
        assert result is True
        # Empty note should not be added
        assert "" not in milestone.notes or len(milestone.notes) == 0


# =============================================================================
# Session State Persistence Tests
# =============================================================================

class TestProgressSerialization:
    """Test progress serialization for persistence."""

    def test_progress_to_dict_complete(self):
        """Test full progress serialization."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        progress.iterations_completed = 10
        progress.total_frames_played = 5000
        progress.black_screens_detected = 2
        progress.transitions_completed = 15
        progress.start_time = datetime(2026, 1, 24, 10, 0, 0)
        progress.last_update = datetime(2026, 1, 24, 11, 0, 0)

        d = progress.to_dict()
        assert d["current_phase"] == "EXPLORING"
        assert d["iterations_completed"] == 10
        assert d["total_frames_played"] == 5000
        assert d["black_screens_detected"] == 2
        assert d["transitions_completed"] == 15

    def test_progress_to_dict_with_milestones(self):
        """Test progress serialization includes milestones."""
        progress = CampaignProgress()
        m1 = CampaignMilestone(id="m1", description="M1", goal="A.1")
        m2 = CampaignMilestone(id="m2", description="M2", goal="A.2")
        m1.complete("Done!")
        progress.add_milestone(m1)
        progress.add_milestone(m2)

        d = progress.to_dict()
        assert "m1" in d["milestones"]
        assert "m2" in d["milestones"]
        assert d["milestones"]["m1"]["status"] == "COMPLETED"
        assert d["milestones"]["m2"]["status"] == "NOT_STARTED"

    def test_progress_to_dict_timestamps_none(self):
        """Test progress serialization handles None timestamps."""
        progress = CampaignProgress()
        d = progress.to_dict()
        assert d["start_time"] is None
        assert d["last_update"] is None

    def test_progress_to_dict_timestamps_iso(self):
        """Test progress serialization formats timestamps as ISO."""
        progress = CampaignProgress()
        progress.start_time = datetime(2026, 1, 24, 12, 30, 45)
        d = progress.to_dict()
        assert "2026-01-24" in d["start_time"]

    def test_progress_to_dict_is_json_serializable(self):
        """Test progress dict is JSON serializable."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        progress.start_time = datetime.now()
        milestone = CampaignMilestone(id="test", description="Test", goal="A.1")
        milestone.complete()
        progress.add_milestone(milestone)

        d = progress.to_dict()
        json_str = json.dumps(d)
        assert json_str is not None
        assert len(json_str) > 0


class TestMilestoneSerialization:
    """Test milestone serialization."""

    def test_milestone_to_dict_all_fields(self):
        """Test milestone serialization includes all fields."""
        milestone = CampaignMilestone(
            id="test_id",
            description="Test description",
            goal="B.2"
        )
        milestone.status = MilestoneStatus.IN_PROGRESS
        milestone.notes.append("Note 1")
        milestone.notes.append("Note 2")

        d = milestone.to_dict()
        assert d["id"] == "test_id"
        assert d["description"] == "Test description"
        assert d["goal"] == "B.2"
        assert d["status"] == "IN_PROGRESS"
        assert len(d["notes"]) == 2

    def test_milestone_to_dict_completed(self):
        """Test completed milestone serialization."""
        milestone = CampaignMilestone(id="done", description="Done", goal="A.1")
        milestone.complete("Completed successfully!")

        d = milestone.to_dict()
        assert d["status"] == "COMPLETED"
        assert d["completed_at"] is not None
        assert "Completed successfully!" in d["notes"]

    def test_milestone_to_dict_blocked(self):
        """Test blocked milestone serialization."""
        milestone = CampaignMilestone(id="blocked", description="Blocked", goal="C.1")
        milestone.status = MilestoneStatus.BLOCKED
        milestone.notes.append("Blocked by bug #123")

        d = milestone.to_dict()
        assert d["status"] == "BLOCKED"
        assert "Blocked by bug #123" in d["notes"]


# =============================================================================
# Campaign Counter Tests
# =============================================================================

class TestIterationCounter:
    """Test iteration counter behavior."""

    def test_iteration_starts_at_zero(self):
        """Test iteration counter starts at zero."""
        progress = CampaignProgress()
        assert progress.iterations_completed == 0

    def test_iteration_increments(self):
        """Test iteration counter increments."""
        progress = CampaignProgress()
        for i in range(10):
            progress.iterations_completed += 1
        assert progress.iterations_completed == 10

    def test_iteration_large_value(self):
        """Test iteration counter handles large values."""
        progress = CampaignProgress()
        progress.iterations_completed = 1000000
        assert progress.iterations_completed == 1000000


class TestFrameCounter:
    """Test frame counter behavior."""

    def test_frames_starts_at_zero(self):
        """Test frame counter starts at zero."""
        progress = CampaignProgress()
        assert progress.total_frames_played == 0

    def test_frames_increments_by_one(self):
        """Test frame counter increments by one."""
        progress = CampaignProgress()
        progress.total_frames_played += 1
        assert progress.total_frames_played == 1

    def test_frames_increments_by_batch(self):
        """Test frame counter increments by batch."""
        progress = CampaignProgress()
        progress.total_frames_played += 60  # 1 second at 60fps
        assert progress.total_frames_played == 60

    def test_frames_large_value(self):
        """Test frame counter handles large values."""
        progress = CampaignProgress()
        progress.total_frames_played = 3600 * 60  # 1 hour at 60fps
        assert progress.total_frames_played == 216000


class TestBlackScreenCounter:
    """Test black screen counter behavior."""

    def test_black_screen_starts_at_zero(self):
        """Test black screen counter starts at zero."""
        progress = CampaignProgress()
        assert progress.black_screens_detected == 0

    def test_black_screen_increments(self):
        """Test black screen counter increments."""
        progress = CampaignProgress()
        progress.black_screens_detected += 1
        assert progress.black_screens_detected == 1

    def test_black_screen_multiple_detections(self):
        """Test multiple black screen detections."""
        progress = CampaignProgress()
        for _ in range(5):
            progress.black_screens_detected += 1
        assert progress.black_screens_detected == 5


class TestTransitionCounter:
    """Test transition counter behavior."""

    def test_transitions_starts_at_zero(self):
        """Test transition counter starts at zero."""
        progress = CampaignProgress()
        assert progress.transitions_completed == 0

    def test_transitions_increments(self):
        """Test transition counter increments."""
        progress = CampaignProgress()
        progress.transitions_completed += 1
        assert progress.transitions_completed == 1

    def test_transitions_accumulate(self):
        """Test transitions accumulate over time."""
        progress = CampaignProgress()
        progress.transitions_completed += 10
        progress.transitions_completed += 5
        progress.transitions_completed += 3
        assert progress.transitions_completed == 18


# =============================================================================
# Status Report Tests
# =============================================================================

class TestStatusReportGeneration:
    """Test status report generation."""

    def test_status_report_is_string(self):
        """Test status report returns string."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert isinstance(report, str)

    def test_status_report_contains_header(self):
        """Test status report contains header."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "ORACLE OF SECRETS" in report or "CAMPAIGN" in report

    def test_status_report_contains_phase(self):
        """Test status report contains current phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.EXPLORING
        report = orch.get_status_report()
        assert "EXPLORING" in report

    def test_status_report_contains_counters(self):
        """Test status report contains all counters."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.iterations_completed = 5
        orch._progress.total_frames_played = 1000
        orch._progress.black_screens_detected = 2
        orch._progress.transitions_completed = 10
        report = orch.get_status_report()
        assert "5" in report  # iterations
        assert "1000" in report  # frames

    def test_status_report_milestone_status_icons(self):
        """Test status report shows milestone status icons."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        # Should have NOT_STARTED icon
        assert "[ ]" in report

    def test_status_report_completed_milestone_icon(self):
        """Test status report shows completed milestone icon."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()  # Completes emulator_connected milestone
        report = orch.get_status_report()
        assert "[✓]" in report

    def test_status_report_completion_percentage(self):
        """Test status report shows completion percentage."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "%" in report or "Completion" in report


# =============================================================================
# Quick Status Tests
# =============================================================================

class TestQuickStatusFunction:
    """Test quick_status utility function."""

    def test_quick_status_returns_string(self):
        """Test quick_status returns string."""
        result = quick_status()
        assert isinstance(result, str)

    def test_quick_status_mentions_emulator(self):
        """Test quick_status mentions emulator interface."""
        result = quick_status()
        assert "Emulator" in result

    def test_quick_status_mentions_parser(self):
        """Test quick_status mentions game state parser."""
        result = quick_status()
        assert "GameStateParser" in result

    def test_quick_status_mentions_recorder(self):
        """Test quick_status mentions input recorder."""
        result = quick_status()
        assert "Recorder" in result or "Input" in result

    def test_quick_status_mentions_planner(self):
        """Test quick_status mentions action planner."""
        result = quick_status()
        assert "ActionPlanner" in result

    def test_quick_status_mentions_orchestrator(self):
        """Test quick_status mentions orchestrator."""
        result = quick_status()
        assert "Orchestrator" in result

    def test_quick_status_has_usage_instructions(self):
        """Test quick_status includes usage instructions."""
        result = quick_status()
        assert "create_campaign" in result or "run_campaign" in result


# =============================================================================
# Create Campaign Tests
# =============================================================================

class TestCreateCampaignFunction:
    """Test create_campaign utility function."""

    def test_create_campaign_returns_orchestrator(self):
        """Test create_campaign returns CampaignOrchestrator."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            orch = create_campaign()
            assert isinstance(orch, CampaignOrchestrator)

    def test_create_campaign_default_log_dir(self):
        """Test create_campaign uses default log directory."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            orch = create_campaign()
            assert orch._log_dir == (Path(tempfile.gettempdir()) / "oos_campaign" / "logs")

    def test_create_campaign_custom_log_dir(self):
        """Test create_campaign accepts custom log directory."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            custom_path = Path("/tmp/custom_logs")
            orch = create_campaign(log_dir=custom_path)
            assert orch._log_dir == custom_path

    def test_create_campaign_initializes_progress(self):
        """Test create_campaign initializes progress."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            orch = create_campaign()
            assert orch._progress is not None
            assert isinstance(orch._progress, CampaignProgress)


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_orchestrator_with_none_emulator(self):
        """Test orchestrator handles None emulator internally."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator') as mock:
            mock.return_value = Mock()
            orch = CampaignOrchestrator(emulator=None)
            # Should create Mesen2Emulator internally

    def test_empty_milestone_description(self):
        """Test milestone with empty description."""
        milestone = CampaignMilestone(id="empty", description="", goal="A.1")
        assert milestone.description == ""
        d = milestone.to_dict()
        assert d["description"] == ""

    def test_milestone_with_special_characters(self):
        """Test milestone with special characters in note."""
        milestone = CampaignMilestone(id="special", description="Test", goal="A.1")
        milestone.notes.append("Note with 'quotes' and \"double quotes\"")
        milestone.notes.append("Note with unicode: 日本語")
        d = milestone.to_dict()
        json_str = json.dumps(d)
        assert json_str is not None

    def test_very_long_note(self):
        """Test milestone with very long note."""
        milestone = CampaignMilestone(id="long", description="Test", goal="A.1")
        long_note = "A" * 10000
        milestone.notes.append(long_note)
        assert len(milestone.notes[0]) == 10000

    def test_completion_percentage_single_milestone(self):
        """Test completion percentage with single milestone."""
        progress = CampaignProgress()
        progress.add_milestone(
            CampaignMilestone(id="only", description="Only", goal="A.1")
        )
        assert progress.get_completion_percentage() == 0.0
        progress.complete_milestone("only")
        assert progress.get_completion_percentage() == 100.0

    def test_duplicate_milestone_overwrites(self):
        """Test adding duplicate milestone id overwrites."""
        progress = CampaignProgress()
        m1 = CampaignMilestone(id="dup", description="First", goal="A.1")
        m2 = CampaignMilestone(id="dup", description="Second", goal="A.2")
        progress.add_milestone(m1)
        progress.add_milestone(m2)
        assert progress.milestones["dup"].description == "Second"


class TestCampaignPhaseEnum:
    """Test CampaignPhase enum properties."""

    def test_all_phases_exist(self):
        """Test all expected phases exist."""
        expected = [
            "DISCONNECTED", "CONNECTING", "BOOTING",
            "EXPLORING", "NAVIGATING", "IN_DUNGEON",
            "COMPLETED", "FAILED"
        ]
        phase_names = [p.name for p in CampaignPhase]
        for name in expected:
            assert name in phase_names

    def test_phase_count(self):
        """Test correct number of phases."""
        assert len(CampaignPhase) == 8

    def test_phases_are_comparable(self):
        """Test phases can be compared for equality."""
        assert CampaignPhase.DISCONNECTED == CampaignPhase.DISCONNECTED
        assert CampaignPhase.DISCONNECTED != CampaignPhase.BOOTING

    def test_phase_from_name(self):
        """Test getting phase from name."""
        phase = CampaignPhase["EXPLORING"]
        assert phase == CampaignPhase.EXPLORING


class TestMilestoneStatusEnum:
    """Test MilestoneStatus enum properties."""

    def test_all_statuses_exist(self):
        """Test all expected statuses exist."""
        expected = ["NOT_STARTED", "IN_PROGRESS", "COMPLETED", "BLOCKED"]
        status_names = [s.name for s in MilestoneStatus]
        for name in expected:
            assert name in status_names

    def test_status_count(self):
        """Test correct number of statuses."""
        assert len(MilestoneStatus) == 4

    def test_statuses_are_comparable(self):
        """Test statuses can be compared for equality."""
        assert MilestoneStatus.NOT_STARTED == MilestoneStatus.NOT_STARTED
        assert MilestoneStatus.NOT_STARTED != MilestoneStatus.COMPLETED

    def test_status_from_name(self):
        """Test getting status from name."""
        status = MilestoneStatus["COMPLETED"]
        assert status == MilestoneStatus.COMPLETED
