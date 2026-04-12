"""Tests for state persistence and serialization in campaign modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Reliable state saving/loading

These tests verify that state can be saved and loaded correctly,
including progress tracking, sequences, and configuration.
"""

import pytest
import json
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock
import tempfile

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputFrame, InputRecorder
)
from scripts.campaign.action_planner import Goal, GoalType, Plan, PlanStatus
from scripts.campaign.campaign_orchestrator import (
    CampaignOrchestrator, CampaignPhase, CampaignProgress,
    CampaignMilestone, MilestoneStatus
)
from scripts.campaign.visual_verifier import Screenshot, VerificationResult, VerificationReport


class TestInputSequencePersistence:
    """Test input sequence save/load functionality."""

    @pytest.fixture
    def temp_file(self):
        """Create temporary file for testing."""
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            path = Path(f.name)
        yield path
        if path.exists():
            path.unlink()

    def test_save_empty_sequence(self, temp_file):
        """Test saving empty sequence."""
        seq = InputSequence(name="empty")
        seq.save(str(temp_file))

        assert temp_file.exists()
        data = json.loads(temp_file.read_text())
        assert data["name"] == "empty"
        assert data["frames"] == []

    def test_save_load_roundtrip(self, temp_file):
        """Test save/load preserves all data."""
        original = InputSequence(
            name="test_sequence",
            description="A test sequence",
            metadata={"test": True, "version": 1}
        )
        original.add_input(0, Button.A, hold=5)
        original.add_input(10, Button.B | Button.RIGHT, hold=3)
        original.add_input(20, Button.START, hold=1)

        original.save(str(temp_file))
        loaded = InputSequence.load(str(temp_file))

        assert loaded.name == original.name
        assert loaded.description == original.description
        assert loaded.metadata["test"] is True
        assert loaded.metadata["version"] == 1
        assert len(loaded.frames) == len(original.frames)
        assert loaded.total_frames == original.total_frames

    def test_load_preserves_buttons(self, temp_file):
        """Test button combinations are preserved through save/load."""
        original = InputSequence(name="buttons")
        combo = Button.A | Button.B | Button.UP | Button.L
        original.add_input(0, combo, hold=1)

        original.save(str(temp_file))
        loaded = InputSequence.load(str(temp_file))

        loaded_buttons = loaded.frames[0].buttons
        assert loaded_buttons & Button.A
        assert loaded_buttons & Button.B
        assert loaded_buttons & Button.UP
        assert loaded_buttons & Button.L
        assert not (loaded_buttons & Button.DOWN)

    def test_save_requires_existing_directory(self):
        """Test save requires parent directory to exist.

        Note: Current implementation doesn't create parent directories.
        This documents the actual behavior for callers.
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            deep_path = Path(tmpdir) / "a" / "b" / "c" / "test.json"
            seq = InputSequence(name="nested")

            # Should fail without parent directories
            with pytest.raises(FileNotFoundError):
                seq.save(str(deep_path))

            # But works when directories exist
            deep_path.parent.mkdir(parents=True)
            seq.save(str(deep_path))
            assert deep_path.exists()


class TestProgressPersistence:
    """Test campaign progress serialization."""

    def test_progress_to_dict_empty(self):
        """Test empty progress serializes correctly."""
        progress = CampaignProgress()
        progress.milestones.clear()

        data = progress.to_dict()

        assert data["iterations_completed"] == 0
        assert data["total_frames_played"] == 0
        assert data["black_screens_detected"] == 0
        assert data["milestones"] == {}

    def test_progress_to_dict_with_milestones(self):
        """Test progress with milestones serializes correctly."""
        progress = CampaignProgress()
        progress.add_milestone(CampaignMilestone(
            id="test1",
            description="Test milestone 1",
            goal="T.1"
        ))
        progress.add_milestone(CampaignMilestone(
            id="test2",
            description="Test milestone 2",
            goal="T.2"
        ))
        progress.complete_milestone("test1", "Completed!")

        data = progress.to_dict()

        assert len(data["milestones"]) == 2
        assert data["milestones"]["test1"]["status"] == "COMPLETED"
        assert data["milestones"]["test2"]["status"] == "NOT_STARTED"

    def test_milestone_notes_persist(self):
        """Test milestone notes are included in serialization."""
        milestone = CampaignMilestone(
            id="test",
            description="Test",
            goal="T.1"
        )
        milestone.notes.append("First note")
        milestone.notes.append("Second note")
        milestone.complete("Final note")

        data = milestone.to_dict()

        assert "First note" in data["notes"]
        assert "Second note" in data["notes"]
        assert "Final note" in data["notes"]


class TestGameStateSnapshot:
    """Test GameStateSnapshot serialization capabilities."""

    def test_snapshot_to_dict(self):
        """Test snapshot can be converted to dict."""
        snapshot = GameStateSnapshot(
            timestamp=12345.678,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x00,
            link_x=512,
            link_y=480,
            link_z=0,
            link_direction=2,
            link_state=0,
            indoors=False,
            inidisp=0x0F,
            health=24,
            max_health=24
        )

        # Convert to dict using dataclass asdict or to_dict method
        from dataclasses import asdict
        data = asdict(snapshot)

        assert data["timestamp"] == 12345.678
        assert data["mode"] == 0x09
        assert data["area"] == 0x29
        assert data["link_x"] == 512

    def test_snapshot_json_serializable(self):
        """Test snapshot can be JSON serialized."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        from dataclasses import asdict
        json_str = json.dumps(asdict(snapshot))
        loaded = json.loads(json_str)

        assert loaded["mode"] == 0x09
        assert loaded["link_x"] == 512


class TestScreenshotPersistence:
    """Test screenshot metadata serialization."""

    def test_screenshot_to_dict(self):
        """Test screenshot serializes to dict."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime(2026, 1, 24, 12, 0, 0),
            frame_number=100,
            area_id=0x29,
            room_id=0x05,
            metadata={"custom": "value"}
        )

        data = screenshot.to_dict()

        assert "/tmp/test.png" in data["path"]
        assert data["frame_number"] == 100
        assert data["area_id"] == 0x29
        assert data["room_id"] == 0x05
        assert data["metadata"]["custom"] == "value"

    def test_verification_report_to_dict(self):
        """Test verification report serializes correctly."""
        screenshot = Screenshot(
            path=Path("/tmp/current.png"),
            timestamp=datetime.now(),
            frame_number=0
        )
        report = VerificationReport(
            result=VerificationResult.PASS,
            similarity_score=0.95,
            current=screenshot,
            notes=["Test passed", "High similarity"]
        )

        data = report.to_dict()

        assert data["result"] == "PASS"
        assert data["similarity_score"] == 0.95
        assert "Test passed" in data["notes"]
        assert data["current"] is not None


class TestGoalSerialization:
    """Test goal and plan serialization."""

    def test_goal_parameters_accessible(self):
        """Test goal parameters can be accessed."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480, tolerance=32)

        # Parameters should be accessible as dict
        assert goal.parameters["area_id"] == 0x29
        assert goal.parameters["x"] == 512
        assert goal.parameters["y"] == 480
        assert goal.parameters["tolerance"] == 32

    def test_goal_description_generated(self):
        """Test goals generate meaningful descriptions."""
        reach_goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        enter_goal = Goal.enter_building(entrance_id=0x12)
        defeat_goal = Goal.defeat_enemy(sprite_id=0x55)

        assert "0x29" in reach_goal.description or "29" in reach_goal.description
        assert "0x12" in enter_goal.description or "12" in enter_goal.description
        assert "0x55" in defeat_goal.description or "55" in defeat_goal.description

    def test_plan_tracks_goal(self):
        """Test plan maintains reference to goal."""
        goal = Goal.reach_location(area_id=0x29, x=512, y=480)
        plan = Plan(goal=goal)

        assert plan.goal is goal
        assert plan.goal.goal_type == GoalType.REACH_LOCATION


class TestInputFrameSerialization:
    """Test InputFrame serialization."""

    def test_frame_to_dict(self):
        """Test frame converts to dict."""
        frame = InputFrame(
            frame_number=100,
            buttons=Button.A | Button.B,
            hold_frames=10
        )

        data = frame.to_dict()

        assert data["frame"] == 100
        assert "A" in data["buttons"]
        assert "B" in data["buttons"]
        assert data["hold"] == 10

    def test_frame_from_dict(self):
        """Test frame can be reconstructed from dict."""
        data = {
            "frame": 50,
            "buttons": ["A", "START"],
            "hold": 5
        }

        frame = InputFrame.from_dict(data)

        assert frame.frame_number == 50
        assert frame.buttons & Button.A
        assert frame.buttons & Button.START
        assert frame.hold_frames == 5

    def test_frame_roundtrip(self):
        """Test frame survives to_dict/from_dict roundtrip."""
        original = InputFrame(
            frame_number=200,
            buttons=Button.L | Button.R | Button.UP,
            hold_frames=15
        )

        data = original.to_dict()
        restored = InputFrame.from_dict(data)

        assert restored.frame_number == original.frame_number
        assert restored.buttons == original.buttons
        assert restored.hold_frames == original.hold_frames


class TestPhaseEnumSerialization:
    """Test enum serialization for phases and statuses."""

    def test_campaign_phase_names(self):
        """Test CampaignPhase has string names."""
        phases = [
            CampaignPhase.DISCONNECTED,
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
            CampaignPhase.IN_DUNGEON,
            CampaignPhase.COMPLETED,
            CampaignPhase.FAILED
        ]

        for phase in phases:
            assert phase.name is not None
            assert len(phase.name) > 0

    def test_milestone_status_names(self):
        """Test MilestoneStatus has string names."""
        statuses = [
            MilestoneStatus.NOT_STARTED,
            MilestoneStatus.IN_PROGRESS,
            MilestoneStatus.COMPLETED,
            MilestoneStatus.BLOCKED
        ]

        for status in statuses:
            assert status.name is not None
            assert len(status.name) > 0

    def test_plan_status_names(self):
        """Test PlanStatus has string names."""
        statuses = [
            PlanStatus.NOT_STARTED,
            PlanStatus.IN_PROGRESS,
            PlanStatus.COMPLETED,
            PlanStatus.FAILED,
            PlanStatus.BLOCKED
        ]

        for status in statuses:
            assert status.name is not None
            assert len(status.name) > 0

    def test_verification_result_names(self):
        """Test VerificationResult has string names."""
        results = [
            VerificationResult.PASS,
            VerificationResult.FAIL,
            VerificationResult.BLACK_SCREEN,
            VerificationResult.ERROR,
            VerificationResult.SKIPPED
        ]

        for result in results:
            assert result.name is not None
            assert len(result.name) > 0
