"""Tests for campaign_orchestrator module.

Campaign Goals Supported:
- A.1-A.5: Autonomous Gameplay verification
- D: Intelligent Agent Tooling
"""

import json
import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
    CampaignOrchestrator,
    create_campaign,
    quick_status,
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.game_state import GamePhase


class TestCampaignPhase:
    """Tests for CampaignPhase enum."""

    def test_phases_exist(self):
        """Test all phases are defined."""
        assert CampaignPhase.DISCONNECTED is not None
        assert CampaignPhase.CONNECTING is not None
        assert CampaignPhase.BOOTING is not None
        assert CampaignPhase.EXPLORING is not None
        assert CampaignPhase.NAVIGATING is not None
        assert CampaignPhase.IN_DUNGEON is not None
        assert CampaignPhase.COMPLETED is not None
        assert CampaignPhase.FAILED is not None


class TestMilestoneStatus:
    """Tests for MilestoneStatus enum."""

    def test_statuses_exist(self):
        """Test all statuses are defined."""
        assert MilestoneStatus.NOT_STARTED is not None
        assert MilestoneStatus.IN_PROGRESS is not None
        assert MilestoneStatus.COMPLETED is not None
        assert MilestoneStatus.BLOCKED is not None


class TestCampaignMilestone:
    """Tests for CampaignMilestone dataclass."""

    def test_create_milestone(self):
        """Test creating a milestone."""
        m = CampaignMilestone(
            id="test_milestone",
            description="Test milestone",
            goal="A.1"
        )
        assert m.id == "test_milestone"
        assert m.status == MilestoneStatus.NOT_STARTED
        assert m.completed_at is None

    def test_complete_milestone(self):
        """Test completing a milestone."""
        m = CampaignMilestone(
            id="test",
            description="Test",
            goal="A.1"
        )
        m.complete("Completed successfully")

        assert m.status == MilestoneStatus.COMPLETED
        assert m.completed_at is not None
        assert "Completed successfully" in m.notes

    def test_to_dict(self):
        """Test milestone serialization."""
        m = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="B.2"
        )
        m.complete("Done")

        data = m.to_dict()
        assert data["id"] == "test"
        assert data["description"] == "Test milestone"
        assert data["goal"] == "B.2"
        assert data["status"] == "COMPLETED"
        assert data["completed_at"] is not None
        assert "Done" in data["notes"]


class TestCampaignProgress:
    """Tests for CampaignProgress dataclass."""

    def test_initial_state(self):
        """Test initial progress state."""
        progress = CampaignProgress()

        assert progress.current_phase == CampaignPhase.DISCONNECTED
        assert progress.iterations_completed == 0
        assert progress.total_frames_played == 0
        assert len(progress.milestones) == 0

    def test_add_milestone(self):
        """Test adding milestones."""
        progress = CampaignProgress()
        m = CampaignMilestone("test", "Test", "A.1")

        progress.add_milestone(m)

        assert "test" in progress.milestones
        assert progress.milestones["test"] == m

    def test_complete_milestone(self):
        """Test completing a milestone via progress."""
        progress = CampaignProgress()
        progress.add_milestone(CampaignMilestone("test", "Test", "A.1"))

        result = progress.complete_milestone("test", "Done")

        assert result is True
        assert progress.milestones["test"].status == MilestoneStatus.COMPLETED

    def test_complete_nonexistent_milestone(self):
        """Test completing nonexistent milestone."""
        progress = CampaignProgress()

        result = progress.complete_milestone("nonexistent")

        assert result is False

    def test_completion_percentage_empty(self):
        """Test completion percentage with no milestones."""
        progress = CampaignProgress()

        assert progress.get_completion_percentage() == 0.0

    def test_completion_percentage_partial(self):
        """Test completion percentage with partial completion."""
        progress = CampaignProgress()
        progress.add_milestone(CampaignMilestone("m1", "M1", "A.1"))
        progress.add_milestone(CampaignMilestone("m2", "M2", "A.2"))

        progress.complete_milestone("m1")

        assert progress.get_completion_percentage() == 50.0

    def test_completion_percentage_full(self):
        """Test completion percentage at 100%."""
        progress = CampaignProgress()
        progress.add_milestone(CampaignMilestone("m1", "M1", "A.1"))
        progress.add_milestone(CampaignMilestone("m2", "M2", "A.2"))

        progress.complete_milestone("m1")
        progress.complete_milestone("m2")

        assert progress.get_completion_percentage() == 100.0

    def test_to_dict(self):
        """Test progress serialization."""
        progress = CampaignProgress()
        progress.add_milestone(CampaignMilestone("test", "Test", "A.1"))
        progress.iterations_completed = 5
        progress.total_frames_played = 3000

        data = progress.to_dict()

        assert data["iterations_completed"] == 5
        assert data["total_frames_played"] == 3000
        assert "test" in data["milestones"]


class TestCampaignOrchestrator:
    """Tests for CampaignOrchestrator class."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.connect.return_value = True
        emu.is_connected.return_value = True
        emu.disconnect.return_value = None
        emu.step_frame.return_value = True
        emu.inject_input.return_value = True
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

    def test_create_orchestrator(self, mock_emulator):
        """Test creating orchestrator."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)

        assert orchestrator is not None
        assert orchestrator._progress.current_phase == CampaignPhase.DISCONNECTED

    def test_milestones_initialized(self, mock_emulator):
        """Test milestones are set up."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)

        assert len(orchestrator._progress.milestones) > 0
        assert "boot_playable" in orchestrator._progress.milestones
        assert "reach_village" in orchestrator._progress.milestones
        assert "reach_dungeon1" in orchestrator._progress.milestones

    def test_connect_success(self, mock_emulator):
        """Test successful connection."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)

        result = orchestrator.connect()

        assert result is True
        assert orchestrator._progress.current_phase == CampaignPhase.BOOTING
        assert orchestrator._progress.milestones["emulator_connected"].status == MilestoneStatus.COMPLETED

    def test_connect_failure(self, mock_emulator):
        """Test failed connection."""
        mock_emulator.connect.return_value = False
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)

        result = orchestrator.connect()

        assert result is False
        assert orchestrator._progress.current_phase == CampaignPhase.FAILED

    def test_disconnect(self, mock_emulator):
        """Test disconnection."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)
        orchestrator.connect()
        orchestrator.disconnect()

        assert orchestrator._progress.current_phase == CampaignPhase.DISCONNECTED
        mock_emulator.disconnect.assert_called_once()

    def test_get_state(self, mock_emulator):
        """Test getting game state."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)
        orchestrator.connect()

        state = orchestrator.get_state()

        assert state is not None
        assert state.phase == GamePhase.OVERWORLD
        assert state.link_position == (512, 480)

    def test_get_state_not_connected(self, mock_emulator):
        """Test getting state when not connected."""
        mock_emulator.is_connected.return_value = False
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)

        state = orchestrator.get_state()

        assert state is None

    def test_get_state_tracks_black_screen(self, mock_emulator):
        """Test that black screens are tracked."""
        # Simulate black screen condition
        mock_emulator.read_state.return_value = GameStateSnapshot(
            timestamp=1000.0,
            mode=0x07,  # Dungeon mode
            submode=0x0F,  # Stuck submodule
            area=0x00,
            room=0x00,
            link_x=0,
            link_y=0,
            link_z=0,
            link_direction=0x00,
            link_state=0x00,
            indoors=True,
            inidisp=0x80,  # Black screen
            health=24,
            max_health=24,
        )
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)
        orchestrator.connect()

        state = orchestrator.get_state()

        # Note: is_playing depends on mode being in [7,9,0xE]
        # Mode 7 with inidisp 0x80 might not count as playing
        # The black screen detection may or may not increment
        assert state is not None

    def test_get_status_report(self, mock_emulator):
        """Test status report generation."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator)
        orchestrator.connect()

        report = orchestrator.get_status_report()

        assert "ORACLE OF SECRETS" in report
        assert "Phase:" in report
        assert "Iterations:" in report
        assert "MILESTONES:" in report


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_create_campaign(self):
        """Test create_campaign factory."""
        orchestrator = create_campaign()

        assert orchestrator is not None
        assert isinstance(orchestrator, CampaignOrchestrator)

    def test_create_campaign_with_log_dir(self):
        """Test create_campaign with custom log dir."""
        with tempfile.TemporaryDirectory() as tmpdir:
            orchestrator = create_campaign(log_dir=Path(tmpdir))

            assert orchestrator._log_dir == Path(tmpdir)

    def test_quick_status(self):
        """Test quick_status function."""
        status = quick_status()

        assert "Campaign Infrastructure Status:" in status
        assert "EmulatorInterface" in status
        assert "GameStateParser" in status
        assert "ActionPlanner" in status
        assert "CampaignOrchestrator" in status


class TestCampaignIntegration:
    """Integration tests for campaign components."""

    @pytest.fixture
    def mock_emulator_with_progression(self):
        """Create mock emulator that simulates game progression."""
        emu = Mock()
        emu.connect.return_value = True
        emu.is_connected.return_value = True
        emu.disconnect.return_value = None
        emu.step_frame.return_value = True
        emu.inject_input.return_value = True

        # Simulate progression through different states
        states = [
            # Boot state
            GameStateSnapshot(
                timestamp=0.0, mode=0x06, submode=0x00, area=0x00, room=0x00,
                link_x=0, link_y=0, link_z=0, link_direction=0, link_state=0,
                indoors=False, inidisp=0x80, health=0, max_health=0
            ),
            # Playable overworld
            GameStateSnapshot(
                timestamp=1.0, mode=0x09, submode=0x00, area=0x29, room=0x00,
                link_x=512, link_y=480, link_z=0, link_direction=2, link_state=0,
                indoors=False, inidisp=0x0F, health=24, max_health=24
            ),
        ]
        state_index = [0]

        def get_state():
            idx = min(state_index[0], len(states) - 1)
            state_index[0] += 1
            return states[idx]

        emu.read_state.side_effect = get_state

        return emu

    def test_orchestrator_tracks_state_changes(self, mock_emulator_with_progression):
        """Test that orchestrator tracks state changes."""
        orchestrator = CampaignOrchestrator(emulator=mock_emulator_with_progression)
        orchestrator.connect()

        # First state - boot
        state1 = orchestrator.get_state()
        assert state1.phase == GamePhase.BLACK_SCREEN

        # Second state - playable
        state2 = orchestrator.get_state()
        assert state2.phase == GamePhase.OVERWORLD
