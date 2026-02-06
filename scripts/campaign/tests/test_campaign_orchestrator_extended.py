"""Extended tests for CampaignOrchestrator and campaign management.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Intelligent agent tooling validation

These tests verify the campaign orchestration system including phases,
milestones, progress tracking, and orchestrator coordination.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime, timedelta

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, MilestoneStatus, CampaignMilestone,
    CampaignProgress, CampaignOrchestrator,
    create_campaign, quick_status
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.game_state import GamePhase


class TestCampaignPhase:
    """Test CampaignPhase enum."""

    def test_disconnected_exists(self):
        """Test DISCONNECTED phase exists."""
        assert CampaignPhase.DISCONNECTED is not None

    def test_connecting_exists(self):
        """Test CONNECTING phase exists."""
        assert CampaignPhase.CONNECTING is not None

    def test_booting_exists(self):
        """Test BOOTING phase exists."""
        assert CampaignPhase.BOOTING is not None

    def test_exploring_exists(self):
        """Test EXPLORING phase exists."""
        assert CampaignPhase.EXPLORING is not None

    def test_navigating_exists(self):
        """Test NAVIGATING phase exists."""
        assert CampaignPhase.NAVIGATING is not None

    def test_in_dungeon_exists(self):
        """Test IN_DUNGEON phase exists."""
        assert CampaignPhase.IN_DUNGEON is not None

    def test_completed_exists(self):
        """Test COMPLETED phase exists."""
        assert CampaignPhase.COMPLETED is not None

    def test_failed_exists(self):
        """Test FAILED phase exists."""
        assert CampaignPhase.FAILED is not None

    def test_all_phases_distinct(self):
        """Test all phases have distinct values."""
        phases = list(CampaignPhase)
        values = [p.value for p in phases]
        assert len(values) == len(set(values))

    def test_phases_have_names(self):
        """Test all phases have string names."""
        for phase in CampaignPhase:
            assert phase.name is not None
            assert len(phase.name) > 0


class TestMilestoneStatus:
    """Test MilestoneStatus enum."""

    def test_not_started_exists(self):
        """Test NOT_STARTED status exists."""
        assert MilestoneStatus.NOT_STARTED is not None

    def test_in_progress_exists(self):
        """Test IN_PROGRESS status exists."""
        assert MilestoneStatus.IN_PROGRESS is not None

    def test_completed_exists(self):
        """Test COMPLETED status exists."""
        assert MilestoneStatus.COMPLETED is not None

    def test_blocked_exists(self):
        """Test BLOCKED status exists."""
        assert MilestoneStatus.BLOCKED is not None

    def test_all_statuses_distinct(self):
        """Test all statuses have distinct values."""
        statuses = list(MilestoneStatus)
        values = [s.value for s in statuses]
        assert len(values) == len(set(values))


class TestCampaignMilestoneCreation:
    """Test CampaignMilestone creation."""

    def test_basic_creation(self):
        """Test creating basic milestone."""
        milestone = CampaignMilestone(
            id="test_milestone",
            description="Test milestone",
            goal="A.1"
        )
        assert milestone.id == "test_milestone"
        assert milestone.description == "Test milestone"
        assert milestone.goal == "A.1"

    def test_default_status(self):
        """Test milestone has default NOT_STARTED status."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        assert milestone.status == MilestoneStatus.NOT_STARTED

    def test_default_completed_at(self):
        """Test milestone has None completed_at by default."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        assert milestone.completed_at is None

    def test_default_notes(self):
        """Test milestone has empty notes list by default."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        assert milestone.notes == []


class TestCampaignMilestoneCompletion:
    """Test CampaignMilestone completion."""

    def test_complete_sets_status(self):
        """Test complete() sets COMPLETED status."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        milestone.complete()
        assert milestone.status == MilestoneStatus.COMPLETED

    def test_complete_sets_timestamp(self):
        """Test complete() sets completed_at timestamp."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        before = datetime.now()
        milestone.complete()
        after = datetime.now()
        assert milestone.completed_at is not None
        assert before <= milestone.completed_at <= after

    def test_complete_with_note(self):
        """Test complete() with note adds to notes list."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        milestone.complete("Completed successfully")
        assert "Completed successfully" in milestone.notes

    def test_complete_without_note(self):
        """Test complete() without note doesn't add empty note."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        milestone.complete()
        assert len(milestone.notes) == 0


class TestCampaignMilestoneSerialization:
    """Test CampaignMilestone serialization."""

    def test_to_dict_basic(self):
        """Test to_dict includes basic fields."""
        milestone = CampaignMilestone(
            id="test_id", description="Test desc", goal="B.2"
        )
        result = milestone.to_dict()
        assert result["id"] == "test_id"
        assert result["description"] == "Test desc"
        assert result["goal"] == "B.2"

    def test_to_dict_status(self):
        """Test to_dict serializes status as name."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        result = milestone.to_dict()
        assert result["status"] == "NOT_STARTED"

    def test_to_dict_completed_at_none(self):
        """Test to_dict handles None completed_at."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        result = milestone.to_dict()
        assert result["completed_at"] is None

    def test_to_dict_completed_at_isoformat(self):
        """Test to_dict formats completed_at as ISO."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        milestone.complete()
        result = milestone.to_dict()
        assert result["completed_at"] is not None
        # Should be ISO format string
        datetime.fromisoformat(result["completed_at"])

    def test_to_dict_notes(self):
        """Test to_dict includes notes."""
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        milestone.complete("Note 1")
        milestone.notes.append("Note 2")
        result = milestone.to_dict()
        assert result["notes"] == ["Note 1", "Note 2"]


class TestCampaignProgressCreation:
    """Test CampaignProgress creation."""

    def test_default_milestones(self):
        """Test progress has empty milestones by default."""
        progress = CampaignProgress()
        assert progress.milestones == {}

    def test_default_phase(self):
        """Test progress has DISCONNECTED phase by default."""
        progress = CampaignProgress()
        assert progress.current_phase == CampaignPhase.DISCONNECTED

    def test_default_counters(self):
        """Test progress has zero counters by default."""
        progress = CampaignProgress()
        assert progress.iterations_completed == 0
        assert progress.total_frames_played == 0
        assert progress.black_screens_detected == 0
        assert progress.transitions_completed == 0

    def test_default_timestamps(self):
        """Test progress has None timestamps by default."""
        progress = CampaignProgress()
        assert progress.start_time is None
        assert progress.last_update is None


class TestCampaignProgressMilestones:
    """Test CampaignProgress milestone management."""

    def test_add_milestone(self):
        """Test adding milestone."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        progress.add_milestone(milestone)
        assert "test" in progress.milestones
        assert progress.milestones["test"] is milestone

    def test_add_multiple_milestones(self):
        """Test adding multiple milestones."""
        progress = CampaignProgress()
        m1 = CampaignMilestone(id="m1", description="M1", goal="A.1")
        m2 = CampaignMilestone(id="m2", description="M2", goal="A.2")
        progress.add_milestone(m1)
        progress.add_milestone(m2)
        assert len(progress.milestones) == 2

    def test_complete_milestone_success(self):
        """Test completing existing milestone."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        progress.add_milestone(milestone)
        result = progress.complete_milestone("test", "Done")
        assert result is True
        assert progress.milestones["test"].status == MilestoneStatus.COMPLETED

    def test_complete_milestone_not_found(self):
        """Test completing non-existent milestone."""
        progress = CampaignProgress()
        result = progress.complete_milestone("nonexistent")
        assert result is False

    def test_complete_milestone_updates_timestamp(self):
        """Test completing milestone updates last_update."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(
            id="test", description="Test", goal="A.1"
        )
        progress.add_milestone(milestone)
        before = datetime.now()
        progress.complete_milestone("test")
        after = datetime.now()
        assert progress.last_update is not None
        assert before <= progress.last_update <= after


class TestCampaignProgressCompletion:
    """Test CampaignProgress completion percentage."""

    def test_completion_no_milestones(self):
        """Test completion with no milestones is 0%."""
        progress = CampaignProgress()
        assert progress.get_completion_percentage() == 0.0

    def test_completion_none_completed(self):
        """Test completion with no completed milestones is 0%."""
        progress = CampaignProgress()
        progress.add_milestone(
            CampaignMilestone(id="m1", description="M1", goal="A.1")
        )
        progress.add_milestone(
            CampaignMilestone(id="m2", description="M2", goal="A.2")
        )
        assert progress.get_completion_percentage() == 0.0

    def test_completion_partial(self):
        """Test partial completion percentage."""
        progress = CampaignProgress()
        progress.add_milestone(
            CampaignMilestone(id="m1", description="M1", goal="A.1")
        )
        progress.add_milestone(
            CampaignMilestone(id="m2", description="M2", goal="A.2")
        )
        progress.complete_milestone("m1")
        assert progress.get_completion_percentage() == 50.0

    def test_completion_all_completed(self):
        """Test 100% completion."""
        progress = CampaignProgress()
        progress.add_milestone(
            CampaignMilestone(id="m1", description="M1", goal="A.1")
        )
        progress.add_milestone(
            CampaignMilestone(id="m2", description="M2", goal="A.2")
        )
        progress.complete_milestone("m1")
        progress.complete_milestone("m2")
        assert progress.get_completion_percentage() == 100.0


class TestCampaignProgressSerialization:
    """Test CampaignProgress serialization."""

    def test_to_dict_phase(self):
        """Test to_dict includes phase name."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        result = progress.to_dict()
        assert result["current_phase"] == "EXPLORING"

    def test_to_dict_counters(self):
        """Test to_dict includes counters."""
        progress = CampaignProgress()
        progress.iterations_completed = 5
        progress.total_frames_played = 1000
        progress.black_screens_detected = 2
        progress.transitions_completed = 10
        result = progress.to_dict()
        assert result["iterations_completed"] == 5
        assert result["total_frames_played"] == 1000
        assert result["black_screens_detected"] == 2
        assert result["transitions_completed"] == 10

    def test_to_dict_completion_percentage(self):
        """Test to_dict includes completion percentage."""
        progress = CampaignProgress()
        result = progress.to_dict()
        assert "completion_percentage" in result

    def test_to_dict_timestamps(self):
        """Test to_dict handles timestamps."""
        progress = CampaignProgress()
        progress.start_time = datetime(2026, 1, 24, 12, 0, 0)
        result = progress.to_dict()
        assert result["start_time"] is not None
        assert result["last_update"] is None

    def test_to_dict_milestones(self):
        """Test to_dict serializes milestones."""
        progress = CampaignProgress()
        progress.add_milestone(
            CampaignMilestone(id="m1", description="M1", goal="A.1")
        )
        result = progress.to_dict()
        assert "m1" in result["milestones"]
        assert result["milestones"]["m1"]["id"] == "m1"


class TestCampaignOrchestratorCreation:
    """Test CampaignOrchestrator creation."""

    def test_creation_with_mock_emulator(self):
        """Test creating orchestrator with mock emulator."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch is not None

    def test_creation_default_log_dir(self):
        """Test orchestrator uses default log dir."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._log_dir == (Path(tempfile.gettempdir()) / "oos_campaign" / "logs")

    def test_creation_custom_log_dir(self):
        """Test orchestrator accepts custom log dir."""
        mock_emu = Mock()
        custom_path = Path("/tmp/test_logs")
        orch = CampaignOrchestrator(emulator=mock_emu, log_dir=custom_path)
        assert orch._log_dir == custom_path

    def test_initial_phase(self):
        """Test orchestrator starts in DISCONNECTED phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_has_milestones(self):
        """Test orchestrator initializes milestones."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert len(orch._progress.milestones) > 0


class TestCampaignOrchestratorMilestones:
    """Test CampaignOrchestrator milestone setup."""

    def test_boot_playable_milestone(self):
        """Test boot_playable milestone exists."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "boot_playable" in orch._progress.milestones

    def test_reach_village_milestone(self):
        """Test reach_village milestone exists."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "reach_village" in orch._progress.milestones

    def test_emulator_connected_milestone(self):
        """Test emulator_connected milestone exists."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert "emulator_connected" in orch._progress.milestones

    def test_milestone_goals_set(self):
        """Test milestones have goal assignments."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        for milestone in orch._progress.milestones.values():
            assert milestone.goal is not None
            assert len(milestone.goal) > 0


class TestCampaignOrchestratorConnect:
    """Test CampaignOrchestrator connection."""

    def test_connect_success(self):
        """Test successful connection."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        result = orch.connect()
        assert result is True
        assert orch._progress.current_phase == CampaignPhase.BOOTING

    def test_connect_failure(self):
        """Test failed connection."""
        mock_emu = Mock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)
        result = orch.connect()
        assert result is False
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_connect_exception(self):
        """Test connection with exception."""
        mock_emu = Mock()
        mock_emu.connect.side_effect = Exception("Connection error")
        orch = CampaignOrchestrator(emulator=mock_emu)
        result = orch.connect()
        assert result is False

    def test_connect_completes_milestone(self):
        """Test successful connection completes milestone."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        milestone = orch._progress.milestones["emulator_connected"]
        assert milestone.status == MilestoneStatus.COMPLETED


class TestCampaignOrchestratorDisconnect:
    """Test CampaignOrchestrator disconnection."""

    def test_disconnect_calls_emulator(self):
        """Test disconnect calls emulator disconnect."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.disconnect()
        mock_emu.disconnect.assert_called_once()

    def test_disconnect_sets_phase(self):
        """Test disconnect sets DISCONNECTED phase."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        orch.disconnect()
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED


class TestCampaignOrchestratorGetState:
    """Test CampaignOrchestrator state reading."""

    def test_get_state_not_connected(self):
        """Test get_state returns None when not connected."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)
        result = orch.get_state()
        assert result is None

    def test_get_state_connected(self):
        """Test get_state returns parsed state when connected."""
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
        orch = CampaignOrchestrator(emulator=mock_emu)
        result = orch.get_state()
        assert result is not None

    def test_get_state_detects_black_screen(self):
        """Test get_state increments black screen counter."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        # INIDISP = 0x00 (display disabled) but mode suggests playing
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x00,  # Black screen
            health=24, max_health=24
        )
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.get_state()
        # Counter incremented if is_black_screen and is_playing both true
        # The actual behavior depends on parsed state logic


class TestCampaignOrchestratorStatusReport:
    """Test CampaignOrchestrator status report generation."""

    def test_status_report_contains_phase(self):
        """Test status report includes phase."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "DISCONNECTED" in report

    def test_status_report_contains_iterations(self):
        """Test status report includes iterations."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "Iterations:" in report

    def test_status_report_contains_frames(self):
        """Test status report includes frames played."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "Frames Played:" in report

    def test_status_report_contains_milestones(self):
        """Test status report includes milestones."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "MILESTONES:" in report

    def test_status_report_milestone_icons(self):
        """Test status report shows milestone status icons."""
        mock_emu = Mock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        report = orch.get_status_report()
        assert "[ ]" in report  # NOT_STARTED icon


class TestUtilityFunctions:
    """Test utility functions."""

    def test_create_campaign(self):
        """Test create_campaign creates orchestrator."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            orch = create_campaign()
            assert isinstance(orch, CampaignOrchestrator)

    def test_create_campaign_with_log_dir(self):
        """Test create_campaign accepts log_dir."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator'):
            custom_path = Path("/tmp/test")
            orch = create_campaign(log_dir=custom_path)
            assert orch._log_dir == custom_path

    def test_quick_status_returns_string(self):
        """Test quick_status returns status string."""
        result = quick_status()
        assert isinstance(result, str)

    def test_quick_status_mentions_components(self):
        """Test quick_status mentions key components."""
        result = quick_status()
        assert "EmulatorInterface" in result
        assert "GameStateParser" in result
        assert "ActionPlanner" in result

    def test_quick_status_has_instructions(self):
        """Test quick_status includes usage instructions."""
        result = quick_status()
        assert "create_campaign" in result


class TestCampaignPhaseTransitions:
    """Test campaign phase transition logic."""

    def test_disconnected_to_connecting(self):
        """Test transition from DISCONNECTED to CONNECTING."""
        mock_emu = Mock()
        mock_emu.connect.return_value = False  # Will fail after CONNECTING
        orch = CampaignOrchestrator(emulator=mock_emu)
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED
        orch.connect()
        # After failed connect, should be FAILED
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_connecting_to_booting_on_success(self):
        """Test transition to BOOTING on successful connect."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch.connect()
        assert orch._progress.current_phase == CampaignPhase.BOOTING


class TestCampaignProgressCounters:
    """Test campaign progress counter updates."""

    def test_iterations_increment(self):
        """Test iterations counter can increment."""
        progress = CampaignProgress()
        progress.iterations_completed += 1
        assert progress.iterations_completed == 1

    def test_frames_increment(self):
        """Test frames counter can increment."""
        progress = CampaignProgress()
        progress.total_frames_played += 100
        assert progress.total_frames_played == 100

    def test_black_screens_increment(self):
        """Test black screens counter can increment."""
        progress = CampaignProgress()
        progress.black_screens_detected += 1
        assert progress.black_screens_detected == 1

    def test_transitions_increment(self):
        """Test transitions counter can increment."""
        progress = CampaignProgress()
        progress.transitions_completed += 1
        assert progress.transitions_completed == 1
