"""Iteration 50 - Extended Campaign Orchestrator Tests.

Tests for CampaignPhase, MilestoneStatus, CampaignMilestone, CampaignProgress,
CampaignOrchestrator, and utility functions.

Focus: Phase transitions, milestone tracking, progress serialization,
orchestrator initialization, status report generation, edge cases.
"""

import json
import pytest
import tempfile
import time
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock, patch, PropertyMock

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
    CampaignOrchestrator,
    create_campaign,
    quick_status,
)
from scripts.campaign.action_planner import GoalType, PlanStatus, Goal, Plan
from scripts.campaign.game_state import GamePhase


# =============================================================================
# CampaignPhase Enum Tests
# =============================================================================

class TestCampaignPhase:
    """Tests for CampaignPhase enum."""

    def test_all_phases_exist(self):
        """All expected phases are defined."""
        phases = [
            CampaignPhase.DISCONNECTED,
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.IN_DUNGEON,
            CampaignPhase.COMPLETED,
            CampaignPhase.FAILED,
        ]
        assert len(phases) == 8
        assert len(set(phases)) == 8  # All unique

    def test_phase_values_are_auto(self):
        """Phase values use auto() and are sequential."""
        phases = list(CampaignPhase)
        for i, phase in enumerate(phases):
            assert phase.value == i + 1  # auto() starts at 1

    def test_phase_names(self):
        """Phase names are strings."""
        for phase in CampaignPhase:
            assert isinstance(phase.name, str)
            assert phase.name == phase.name.upper()

    def test_phase_from_name(self):
        """Phases can be looked up by name."""
        assert CampaignPhase["DISCONNECTED"] == CampaignPhase.DISCONNECTED
        assert CampaignPhase["COMPLETED"] == CampaignPhase.COMPLETED

    def test_phase_iteration(self):
        """Phases can be iterated."""
        phase_list = list(CampaignPhase)
        assert CampaignPhase.DISCONNECTED in phase_list
        assert CampaignPhase.FAILED in phase_list


# =============================================================================
# MilestoneStatus Enum Tests
# =============================================================================

class TestMilestoneStatus:
    """Tests for MilestoneStatus enum."""

    def test_all_statuses_exist(self):
        """All expected statuses are defined."""
        statuses = [
            MilestoneStatus.NOT_STARTED,
            MilestoneStatus.IN_PROGRESS,
            MilestoneStatus.COMPLETED,
            MilestoneStatus.BLOCKED,
        ]
        assert len(statuses) == 4
        assert len(set(statuses)) == 4

    def test_status_values_are_auto(self):
        """Status values use auto()."""
        statuses = list(MilestoneStatus)
        for i, status in enumerate(statuses):
            assert status.value == i + 1

    def test_status_from_name(self):
        """Statuses can be looked up by name."""
        assert MilestoneStatus["NOT_STARTED"] == MilestoneStatus.NOT_STARTED
        assert MilestoneStatus["COMPLETED"] == MilestoneStatus.COMPLETED
        assert MilestoneStatus["BLOCKED"] == MilestoneStatus.BLOCKED


# =============================================================================
# CampaignMilestone Tests
# =============================================================================

class TestCampaignMilestone:
    """Tests for CampaignMilestone dataclass."""

    def test_milestone_creation_minimal(self):
        """Milestone with minimal fields."""
        m = CampaignMilestone(id="test", description="Test milestone", goal="A.1")
        assert m.id == "test"
        assert m.description == "Test milestone"
        assert m.goal == "A.1"
        assert m.status == MilestoneStatus.NOT_STARTED
        assert m.completed_at is None
        assert m.notes == []

    def test_milestone_creation_full(self):
        """Milestone with all fields."""
        now = datetime.now()
        m = CampaignMilestone(
            id="full",
            description="Full milestone",
            goal="B.2",
            status=MilestoneStatus.COMPLETED,
            completed_at=now,
            notes=["Note 1", "Note 2"]
        )
        assert m.status == MilestoneStatus.COMPLETED
        assert m.completed_at == now
        assert len(m.notes) == 2

    def test_milestone_complete_basic(self):
        """Complete method updates status and timestamp."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        before = datetime.now()
        m.complete()
        after = datetime.now()

        assert m.status == MilestoneStatus.COMPLETED
        assert before <= m.completed_at <= after

    def test_milestone_complete_with_note(self):
        """Complete method adds note."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete("Completed successfully")

        assert m.status == MilestoneStatus.COMPLETED
        assert len(m.notes) == 1
        assert "Completed successfully" in m.notes

    def test_milestone_complete_multiple_notes(self):
        """Multiple completion attempts add notes."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.notes.append("Initial note")
        m.complete("Final note")

        assert len(m.notes) == 2
        assert "Initial note" in m.notes
        assert "Final note" in m.notes

    def test_milestone_complete_empty_note(self):
        """Complete with empty string doesn't add note."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete("")

        assert m.status == MilestoneStatus.COMPLETED
        assert len(m.notes) == 0

    def test_milestone_to_dict_not_completed(self):
        """Serialize incomplete milestone."""
        m = CampaignMilestone(id="test", description="Test desc", goal="C.3")
        d = m.to_dict()

        assert d["id"] == "test"
        assert d["description"] == "Test desc"
        assert d["goal"] == "C.3"
        assert d["status"] == "NOT_STARTED"
        assert d["completed_at"] is None
        assert d["notes"] == []

    def test_milestone_to_dict_completed(self):
        """Serialize completed milestone."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete("Done")
        d = m.to_dict()

        assert d["status"] == "COMPLETED"
        assert d["completed_at"] is not None
        assert len(d["notes"]) == 1

    def test_milestone_to_dict_json_safe(self):
        """Serialized milestone is JSON-safe."""
        m = CampaignMilestone(
            id="test",
            description="Special chars: <>&\"'",
            goal="A.1",
            notes=["Unicode: \u00e9\u00f1"]
        )
        m.complete()
        d = m.to_dict()

        # Should not raise
        json_str = json.dumps(d)
        parsed = json.loads(json_str)
        assert parsed["description"] == "Special chars: <>&\"'"


# =============================================================================
# CampaignProgress Tests
# =============================================================================

class TestCampaignProgress:
    """Tests for CampaignProgress dataclass."""

    def test_progress_defaults(self):
        """Progress has correct defaults."""
        p = CampaignProgress()
        assert p.milestones == {}
        assert p.current_phase == CampaignPhase.DISCONNECTED
        assert p.iterations_completed == 0
        assert p.total_frames_played == 0
        assert p.black_screens_detected == 0
        assert p.transitions_completed == 0
        assert p.start_time is None
        assert p.last_update is None

    def test_add_milestone(self):
        """Add milestone to progress."""
        p = CampaignProgress()
        m = CampaignMilestone(id="m1", description="Test", goal="A.1")
        p.add_milestone(m)

        assert "m1" in p.milestones
        assert p.milestones["m1"] == m

    def test_add_multiple_milestones(self):
        """Add multiple milestones."""
        p = CampaignProgress()
        for i in range(5):
            m = CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            p.add_milestone(m)

        assert len(p.milestones) == 5

    def test_add_duplicate_milestone_overwrites(self):
        """Adding duplicate ID overwrites."""
        p = CampaignProgress()
        m1 = CampaignMilestone(id="dup", description="First", goal="A.1")
        m2 = CampaignMilestone(id="dup", description="Second", goal="B.1")

        p.add_milestone(m1)
        p.add_milestone(m2)

        assert len(p.milestones) == 1
        assert p.milestones["dup"].description == "Second"

    def test_complete_milestone_success(self):
        """Complete existing milestone."""
        p = CampaignProgress()
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        p.add_milestone(m)

        result = p.complete_milestone("test", "Done")

        assert result is True
        assert p.milestones["test"].status == MilestoneStatus.COMPLETED
        assert p.last_update is not None

    def test_complete_milestone_nonexistent(self):
        """Complete nonexistent milestone returns False."""
        p = CampaignProgress()
        result = p.complete_milestone("nonexistent")

        assert result is False

    def test_completion_percentage_empty(self):
        """Completion percentage with no milestones."""
        p = CampaignProgress()
        assert p.get_completion_percentage() == 0.0

    def test_completion_percentage_none_completed(self):
        """Completion percentage with no completions."""
        p = CampaignProgress()
        for i in range(4):
            m = CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            p.add_milestone(m)

        assert p.get_completion_percentage() == 0.0

    def test_completion_percentage_all_completed(self):
        """Completion percentage with all completed."""
        p = CampaignProgress()
        for i in range(4):
            m = CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            m.complete()
            p.add_milestone(m)

        assert p.get_completion_percentage() == 100.0

    def test_completion_percentage_partial(self):
        """Completion percentage with some completed."""
        p = CampaignProgress()
        for i in range(4):
            m = CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            if i < 2:
                m.complete()
            p.add_milestone(m)

        assert p.get_completion_percentage() == 50.0

    def test_completion_percentage_one_of_three(self):
        """Completion percentage 1/3."""
        p = CampaignProgress()
        for i in range(3):
            m = CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            if i == 0:
                m.complete()
            p.add_milestone(m)

        expected = (1 / 3) * 100
        assert abs(p.get_completion_percentage() - expected) < 0.01

    def test_progress_to_dict_minimal(self):
        """Serialize minimal progress."""
        p = CampaignProgress()
        d = p.to_dict()

        assert d["current_phase"] == "DISCONNECTED"
        assert d["iterations_completed"] == 0
        assert d["total_frames_played"] == 0
        assert d["black_screens_detected"] == 0
        assert d["transitions_completed"] == 0
        assert d["completion_percentage"] == 0.0
        assert d["start_time"] is None
        assert d["last_update"] is None
        assert d["milestones"] == {}

    def test_progress_to_dict_with_data(self):
        """Serialize progress with data."""
        p = CampaignProgress()
        p.current_phase = CampaignPhase.EXPLORING
        p.iterations_completed = 5
        p.total_frames_played = 3000
        p.black_screens_detected = 2
        p.transitions_completed = 10
        p.start_time = datetime.now()
        p.last_update = datetime.now()

        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete()
        p.add_milestone(m)

        d = p.to_dict()

        assert d["current_phase"] == "EXPLORING"
        assert d["iterations_completed"] == 5
        assert d["total_frames_played"] == 3000
        assert d["black_screens_detected"] == 2
        assert d["transitions_completed"] == 10
        assert d["completion_percentage"] == 100.0
        assert d["start_time"] is not None
        assert "test" in d["milestones"]

    def test_progress_to_dict_json_safe(self):
        """Serialized progress is JSON-safe."""
        p = CampaignProgress()
        p.current_phase = CampaignPhase.COMPLETED
        p.start_time = datetime.now()
        p.last_update = datetime.now()
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        p.add_milestone(m)

        d = p.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["current_phase"] == "COMPLETED"


# =============================================================================
# CampaignOrchestrator Initialization Tests
# =============================================================================

class TestCampaignOrchestratorInit:
    """Tests for CampaignOrchestrator initialization."""

    def test_init_with_defaults(self):
        """Initialize with defaults."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator') as mock_emu:
            mock_emu.return_value = MagicMock()
            orch = CampaignOrchestrator()

            assert orch._progress is not None
            assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_init_with_mock_emulator(self):
        """Initialize with provided emulator."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._emu == mock_emu

    def test_init_with_log_dir(self):
        """Initialize with custom log directory."""
        mock_emu = MagicMock()
        log_dir = Path("/tmp/test_logs")
        orch = CampaignOrchestrator(emulator=mock_emu, log_dir=log_dir)

        assert orch._log_dir == log_dir

    def test_setup_milestones_called(self):
        """_setup_milestones populates milestones."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        # Should have milestones from _setup_milestones
        assert len(orch._progress.milestones) > 0

    def test_default_milestones_present(self):
        """Default milestones are set up."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        expected_ids = [
            "boot_playable",
            "reach_village",
            "reach_dungeon1",
            "enter_dungeon1",
            "complete_dungeon1",
            "no_black_screen",
            "transition_test",
            "emulator_connected",
            "state_parsing",
            "input_playback",
            "action_planning",
        ]
        for m_id in expected_ids:
            assert m_id in orch._progress.milestones

    def test_initial_phase_is_disconnected(self):
        """Initial phase is DISCONNECTED."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED


# =============================================================================
# CampaignOrchestrator Connection Tests
# =============================================================================

class TestCampaignOrchestratorConnection:
    """Tests for connection handling."""

    def test_connect_success(self):
        """Successful connection."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.connect(timeout=1.0)

        assert result is True
        assert orch._progress.current_phase == CampaignPhase.BOOTING
        mock_emu.connect.assert_called_once_with(1.0)

    def test_connect_failure(self):
        """Failed connection."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.connect()

        assert result is False
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_connect_exception(self):
        """Connection with exception."""
        mock_emu = MagicMock()
        mock_emu.connect.side_effect = Exception("Connection error")
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.connect()

        assert result is False
        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_connect_completes_milestone(self):
        """Successful connection completes emulator_connected milestone."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch.connect()

        m = orch._progress.milestones["emulator_connected"]
        assert m.status == MilestoneStatus.COMPLETED

    def test_disconnect(self):
        """Disconnect updates phase."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.current_phase = CampaignPhase.EXPLORING

        orch.disconnect()

        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED
        mock_emu.disconnect.assert_called_once()


# =============================================================================
# CampaignOrchestrator State Tests
# =============================================================================

class TestCampaignOrchestratorState:
    """Tests for state reading."""

    def test_get_state_not_connected(self):
        """Get state when not connected returns None."""
        mock_emu = MagicMock()
        mock_emu.is_connected.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.get_state()

        assert result is None

    def test_get_state_connected(self):
        """Get state when connected."""
        mock_emu = MagicMock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = MagicMock(
            mode=0x07,
            submode=0x00,
            area=0x00,
            room=0x00,
            link_x=100,
            link_y=100,
            link_z=0,
            link_direction=0,
            link_state=0,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24,
            timestamp=time.time()
        )
        orch = CampaignOrchestrator(emulator=mock_emu)

        result = orch.get_state()

        assert result is not None
        mock_emu.read_state.assert_called_once()

    def test_get_state_black_screen_detection(self):
        """Black screen is detected and counted."""
        mock_emu = MagicMock()
        mock_emu.is_connected.return_value = True

        # Create state that triggers black screen detection
        mock_state = MagicMock()
        mock_state.mode = 0x07  # Playing mode
        mock_state.inidisp = 0x00  # Screen off
        mock_emu.read_state.return_value = mock_state

        orch = CampaignOrchestrator(emulator=mock_emu)

        # Mock the parser to return a state that indicates black screen
        with patch.object(orch._parser, 'parse') as mock_parse:
            parsed_state = MagicMock()
            parsed_state.is_black_screen = True
            parsed_state.is_playing = True
            mock_parse.return_value = parsed_state

            orch.get_state()

            assert orch._progress.black_screens_detected == 1

    def test_get_state_no_emulator(self):
        """Get state with no emulator returns None."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._emu = None

        result = orch.get_state()

        assert result is None


# =============================================================================
# Status Report Tests
# =============================================================================

class TestStatusReport:
    """Tests for status report generation."""

    def test_status_report_basic(self):
        """Basic status report generation."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        report = orch.get_status_report()

        assert "ORACLE OF SECRETS AUTONOMOUS CAMPAIGN STATUS" in report
        assert "Phase:" in report
        assert "DISCONNECTED" in report

    def test_status_report_includes_counters(self):
        """Status report includes counters."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)
        orch._progress.iterations_completed = 5
        orch._progress.total_frames_played = 3000
        orch._progress.black_screens_detected = 2
        orch._progress.transitions_completed = 10

        report = orch.get_status_report()

        assert "Iterations: 5" in report
        assert "Frames Played: 3000" in report
        assert "Black Screens: 2" in report
        assert "Transitions: 10" in report

    def test_status_report_includes_milestones(self):
        """Status report includes milestones."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        report = orch.get_status_report()

        assert "MILESTONES:" in report
        assert "boot_playable" in report or "Boot to playable" in report

    def test_status_report_milestone_icons(self):
        """Status report uses correct icons for milestone status."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        # Complete one milestone
        orch._progress.complete_milestone("emulator_connected")

        report = orch.get_status_report()

        # Completed milestone should have checkmark
        assert "[✓]" in report


# =============================================================================
# Utility Function Tests
# =============================================================================

class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_create_campaign_returns_orchestrator(self):
        """create_campaign returns orchestrator."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator') as mock_emu:
            mock_emu.return_value = MagicMock()
            orch = create_campaign()

            assert isinstance(orch, CampaignOrchestrator)

    def test_create_campaign_with_log_dir(self):
        """create_campaign with custom log dir."""
        with patch('scripts.campaign.campaign_orchestrator.Mesen2Emulator') as mock_emu:
            mock_emu.return_value = MagicMock()
            log_dir = Path("/tmp/custom_logs")
            orch = create_campaign(log_dir=log_dir)

            assert orch._log_dir == log_dir

    def test_quick_status_returns_string(self):
        """quick_status returns status string."""
        status = quick_status()

        assert isinstance(status, str)
        assert "Campaign Infrastructure Status" in status

    def test_quick_status_lists_components(self):
        """quick_status lists available components."""
        status = quick_status()

        assert "EmulatorInterface" in status
        assert "GameStateParser" in status
        assert "InputRecorder" in status
        assert "ActionPlanner" in status
        assert "CampaignOrchestrator" in status


# =============================================================================
# Phase Transition Tests
# =============================================================================

class TestPhaseTransitions:
    """Tests for campaign phase transitions."""

    def test_phase_transition_connecting_to_booting(self):
        """Phase transitions from CONNECTING to BOOTING on connect."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = True
        orch = CampaignOrchestrator(emulator=mock_emu)

        # Before connect
        assert orch._progress.current_phase == CampaignPhase.DISCONNECTED

        orch.connect()

        assert orch._progress.current_phase == CampaignPhase.BOOTING

    def test_phase_transition_to_failed(self):
        """Phase transitions to FAILED on connection failure."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = False
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch.connect()

        assert orch._progress.current_phase == CampaignPhase.FAILED

    def test_phase_manual_transition(self):
        """Manual phase transition."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        orch._progress.current_phase = CampaignPhase.EXPLORING
        assert orch._progress.current_phase == CampaignPhase.EXPLORING

        orch._progress.current_phase = CampaignPhase.IN_DUNGEON
        assert orch._progress.current_phase == CampaignPhase.IN_DUNGEON


# =============================================================================
# Counter Behavior Tests
# =============================================================================

class TestCounters:
    """Tests for counter behavior."""

    def test_iterations_counter_default(self):
        """Iterations counter starts at 0."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.iterations_completed == 0

    def test_frames_counter_default(self):
        """Frames counter starts at 0."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.total_frames_played == 0

    def test_black_screens_counter_default(self):
        """Black screens counter starts at 0."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.black_screens_detected == 0

    def test_transitions_counter_default(self):
        """Transitions counter starts at 0."""
        mock_emu = MagicMock()
        orch = CampaignOrchestrator(emulator=mock_emu)

        assert orch._progress.transitions_completed == 0

    def test_counter_increment(self):
        """Counters can be incremented."""
        p = CampaignProgress()

        p.iterations_completed += 1
        p.total_frames_played += 60
        p.black_screens_detected += 1
        p.transitions_completed += 1

        assert p.iterations_completed == 1
        assert p.total_frames_played == 60
        assert p.black_screens_detected == 1
        assert p.transitions_completed == 1

    def test_counter_large_values(self):
        """Counters handle large values."""
        p = CampaignProgress()

        p.iterations_completed = 1000
        p.total_frames_played = 1000000
        p.black_screens_detected = 500
        p.transitions_completed = 10000

        d = p.to_dict()
        assert d["iterations_completed"] == 1000
        assert d["total_frames_played"] == 1000000


# =============================================================================
# Edge Cases
# =============================================================================

class TestEdgeCases:
    """Edge case tests."""

    def test_empty_milestone_id(self):
        """Empty milestone ID."""
        m = CampaignMilestone(id="", description="Empty ID", goal="A.1")
        assert m.id == ""
        d = m.to_dict()
        assert d["id"] == ""

    def test_very_long_description(self):
        """Very long milestone description."""
        long_desc = "A" * 10000
        m = CampaignMilestone(id="long", description=long_desc, goal="A.1")
        assert len(m.description) == 10000

    def test_special_characters_in_goal(self):
        """Special characters in goal field."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1-beta_v2")
        assert m.goal == "A.1-beta_v2"

    def test_many_notes(self):
        """Many notes on milestone."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        for i in range(100):
            m.notes.append(f"Note {i}")

        assert len(m.notes) == 100
        d = m.to_dict()
        assert len(d["notes"]) == 100

    def test_progress_with_no_start_time(self):
        """Progress serialization without start time."""
        p = CampaignProgress()
        d = p.to_dict()

        assert d["start_time"] is None
        json.dumps(d)  # Should not raise

    def test_milestone_complete_twice(self):
        """Completing milestone twice."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")

        m.complete("First completion")
        first_time = m.completed_at

        time.sleep(0.001)  # Small delay
        m.complete("Second completion")
        second_time = m.completed_at

        # Second completion should update timestamp
        assert second_time >= first_time
        assert len(m.notes) == 2

    def test_progress_phase_all_values(self):
        """Progress can have all phase values."""
        p = CampaignProgress()

        for phase in CampaignPhase:
            p.current_phase = phase
            d = p.to_dict()
            assert d["current_phase"] == phase.name

    def test_milestone_status_blocked(self):
        """Milestone can be set to BLOCKED."""
        m = CampaignMilestone(id="blocked", description="Blocked", goal="A.1")
        m.status = MilestoneStatus.BLOCKED

        d = m.to_dict()
        assert d["status"] == "BLOCKED"


# =============================================================================
# Serialization Round-Trip Tests
# =============================================================================

class TestSerializationRoundTrip:
    """Tests for serialization round-trip."""

    def test_milestone_round_trip(self):
        """Milestone serializes and can be reconstructed."""
        m = CampaignMilestone(
            id="roundtrip",
            description="Round trip test",
            goal="B.3",
            notes=["Note 1"]
        )
        m.complete("Final note")

        d = m.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        # Verify key fields
        assert parsed["id"] == "roundtrip"
        assert parsed["status"] == "COMPLETED"
        assert len(parsed["notes"]) == 2

    def test_progress_round_trip(self):
        """Progress serializes and can be reconstructed."""
        p = CampaignProgress()
        p.current_phase = CampaignPhase.NAVIGATING
        p.iterations_completed = 10
        p.total_frames_played = 5000
        p.start_time = datetime.now()

        m = CampaignMilestone(id="m1", description="Test", goal="A.1")
        m.complete()
        p.add_milestone(m)

        d = p.to_dict()
        json_str = json.dumps(d)
        parsed = json.loads(json_str)

        assert parsed["current_phase"] == "NAVIGATING"
        assert parsed["iterations_completed"] == 10
        assert "m1" in parsed["milestones"]
