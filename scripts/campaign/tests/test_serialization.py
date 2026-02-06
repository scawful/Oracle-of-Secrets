"""Serialization and persistence tests (Iteration 44).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling
- E.1: State verification and regression testing

These tests verify save/load campaign state, JSON round-trips,
and data persistence patterns.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
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
    CampaignProgress, CampaignOrchestrator
)
from scripts.campaign.progress_validator import (
    ProgressSnapshot, ValidationResult, ProgressReport
)
from scripts.campaign.emulator_abstraction import (
    GameStateSnapshot, MemoryRead
)
from scripts.campaign.input_recorder import (
    Button, InputFrame, InputSequence
)
from scripts.campaign.action_planner import (
    Goal, GoalType, Action, Plan, PlanStatus
)
from scripts.campaign.pathfinder import (
    NavigationResult, PathNode, CollisionMap
)


# =============================================================================
# JSON Round-Trip Tests
# =============================================================================

class TestCampaignProgressRoundTrip:
    """Test CampaignProgress serialization round-trips."""

    def test_empty_progress_round_trip(self):
        """Test empty progress serializes and deserializes."""
        progress = CampaignProgress()
        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["current_phase"] == "DISCONNECTED"
        assert restored["iterations_completed"] == 0
        assert restored["milestones"] == {}

    def test_progress_with_milestones_round_trip(self):
        """Test progress with milestones round-trips."""
        progress = CampaignProgress()
        m1 = CampaignMilestone(id="m1", description="First", goal="A.1")
        m2 = CampaignMilestone(id="m2", description="Second", goal="A.2")
        m1.complete("Done!")
        progress.add_milestone(m1)
        progress.add_milestone(m2)

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert len(restored["milestones"]) == 2
        assert restored["milestones"]["m1"]["status"] == "COMPLETED"
        assert restored["milestones"]["m2"]["status"] == "NOT_STARTED"

    def test_progress_with_counters_round_trip(self):
        """Test progress with counters round-trips."""
        progress = CampaignProgress()
        progress.iterations_completed = 42
        progress.total_frames_played = 123456
        progress.black_screens_detected = 3
        progress.transitions_completed = 99

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["iterations_completed"] == 42
        assert restored["total_frames_played"] == 123456
        assert restored["black_screens_detected"] == 3
        assert restored["transitions_completed"] == 99

    def test_progress_with_timestamps_round_trip(self):
        """Test progress with timestamps round-trips."""
        progress = CampaignProgress()
        progress.start_time = datetime(2026, 1, 24, 10, 30, 45)
        progress.last_update = datetime(2026, 1, 24, 11, 45, 30)

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        # Timestamps are ISO format strings
        assert "2026-01-24" in restored["start_time"]
        assert "10:30:45" in restored["start_time"]


class TestMilestoneRoundTrip:
    """Test CampaignMilestone serialization round-trips."""

    def test_basic_milestone_round_trip(self):
        """Test basic milestone round-trips."""
        milestone = CampaignMilestone(
            id="test_id",
            description="Test description",
            goal="B.2"
        )

        d = milestone.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["id"] == "test_id"
        assert restored["description"] == "Test description"
        assert restored["goal"] == "B.2"
        assert restored["status"] == "NOT_STARTED"

    def test_completed_milestone_round_trip(self):
        """Test completed milestone round-trips."""
        milestone = CampaignMilestone(id="done", description="Done", goal="A.1")
        milestone.complete("Completed at checkpoint")

        d = milestone.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["status"] == "COMPLETED"
        assert restored["completed_at"] is not None
        assert "Completed at checkpoint" in restored["notes"]

    def test_milestone_with_multiple_notes_round_trip(self):
        """Test milestone with multiple notes round-trips."""
        milestone = CampaignMilestone(id="noted", description="Noted", goal="C.1")
        milestone.notes.append("First note")
        milestone.notes.append("Second note")
        milestone.notes.append("Third note")

        d = milestone.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert len(restored["notes"]) == 3
        assert "First note" in restored["notes"]

    def test_milestone_special_characters_round_trip(self):
        """Test milestone with special characters round-trips."""
        milestone = CampaignMilestone(
            id="special",
            description="Test with 'quotes' and \"double quotes\"",
            goal="A.1"
        )
        milestone.notes.append("Note with unicode: 日本語")
        milestone.notes.append("Note with emoji: 🎮")

        d = milestone.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        restored = json.loads(json_str)

        assert "quotes" in restored["description"]
        assert "日本語" in restored["notes"][0]


class TestProgressSnapshotRoundTrip:
    """Test ProgressSnapshot serialization round-trips."""

    def test_basic_snapshot_round_trip(self):
        """Test basic snapshot round-trips."""
        snapshot = ProgressSnapshot(
            timestamp=1000.5,
            game_state=2,
            story_flags=0x1F,
            story_flags_2=0x03,
            side_quest_1=0x05,
            side_quest_2=0x00,
            health=48,
            max_health=64,
            rupees=500,
            magic=32,
            max_magic=64,
            sword_level=2,
            shield_level=1,
            armor_level=1,
            crystals=0x03,
            follower_id=1,
            follower_state=2
        )

        d = snapshot.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        # Note: to_dict() doesn't include timestamp
        assert restored["game_state"] == 2
        assert restored["story_flags"] == 0x1F
        assert restored["health"] == 48
        assert restored["rupees"] == 500

    def test_snapshot_dungeon_count_in_dict(self):
        """Test snapshot dungeon_count computed property is in dict."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=3,
            story_flags=0x1F,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=64, max_health=80,
            rupees=9999, magic=128, max_magic=128,
            sword_level=4, shield_level=3, armor_level=2,
            crystals=0xFF,
            follower_id=0, follower_state=0
        )

        d = snapshot.to_dict()

        # dungeon_count is included
        assert "dungeon_count" in d
        assert d["dungeon_count"] == 8


class TestInputSequenceRoundTrip:
    """Test InputSequence serialization round-trips."""

    def test_empty_sequence_round_trip(self):
        """Test empty sequence round-trips."""
        seq = InputSequence(name="empty", frames=[])
        d = seq.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["name"] == "empty"
        assert restored["frames"] == []

    def test_sequence_with_frames_round_trip(self):
        """Test sequence with frames round-trips."""
        seq = InputSequence(
            name="test_seq",
            frames=[
                InputFrame(frame_number=1, buttons=Button.A),
                InputFrame(frame_number=2, buttons=Button.B),
                InputFrame(frame_number=3, buttons=Button.NONE),
            ]
        )

        d = seq.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["name"] == "test_seq"
        assert len(restored["frames"]) == 3

    def test_sequence_with_metadata_round_trip(self):
        """Test sequence with metadata round-trips."""
        seq = InputSequence(
            name="meta_seq",
            frames=[],
            metadata={"recorded_by": "test", "version": "1.0"}
        )

        d = seq.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["metadata"]["recorded_by"] == "test"


class TestNavigationResultRoundTrip:
    """Test NavigationResult serialization patterns."""

    def test_success_result_serializable(self):
        """Test successful result is JSON serializable."""
        result = NavigationResult(
            success=True,
            path=[(0, 0), (1, 0), (2, 0), (3, 0)],
            distance=3.0
        )

        d = {
            "success": result.success,
            "path": result.path,
            "distance": result.distance,
            "reason": result.reason
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["success"] is True
        assert len(restored["path"]) == 4

    def test_failure_result_serializable(self):
        """Test failed result is JSON serializable."""
        result = NavigationResult(
            success=False,
            path=[],
            blocked_at=(5, 5),
            reason="Path blocked by wall"
        )

        d = {
            "success": result.success,
            "path": result.path,
            "blocked_at": result.blocked_at,
            "reason": result.reason
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["success"] is False
        assert restored["blocked_at"] == [5, 5]


class TestGameStateSnapshotRoundTrip:
    """Test GameStateSnapshot serialization patterns."""

    def test_snapshot_fields_serializable(self):
        """Test snapshot fields are JSON serializable."""
        snapshot = GameStateSnapshot(
            timestamp=1234.5,
            mode=0x09,
            submode=0x00,
            area=0x29,
            room=0x1234,
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

        # Manually create serializable dict from dataclass fields
        from dataclasses import asdict
        d = asdict(snapshot)
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["mode"] == 0x09
        assert restored["area"] == 0x29
        assert restored["link_x"] == 512

    def test_snapshot_all_fields_present(self):
        """Test all fields present in serialized snapshot."""
        snapshot = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        from dataclasses import asdict
        d = asdict(snapshot)
        expected_fields = [
            "timestamp", "mode", "submode", "area", "room",
            "link_x", "link_y", "link_z", "link_direction",
            "link_state", "indoors", "inidisp", "health", "max_health"
        ]
        for field in expected_fields:
            assert field in d


# =============================================================================
# File Persistence Tests
# =============================================================================

class TestFilePersistence:
    """Test file-based persistence."""

    def test_save_progress_to_file(self):
        """Test saving progress to JSON file."""
        progress = CampaignProgress()
        progress.iterations_completed = 10
        progress.add_milestone(
            CampaignMilestone(id="test", description="Test", goal="A.1")
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(progress.to_dict(), f, indent=2)
            temp_path = f.name

        try:
            with open(temp_path, 'r') as f:
                restored = json.load(f)
            assert restored["iterations_completed"] == 10
            assert "test" in restored["milestones"]
        finally:
            Path(temp_path).unlink()

    def test_save_and_load_snapshot(self):
        """Test saving and loading snapshot."""
        snapshot = ProgressSnapshot(
            timestamp=time.time(),
            game_state=2,
            story_flags=0x0F,
            story_flags_2=0x00,
            side_quest_1=0x00, side_quest_2=0x00,
            health=64, max_health=80,
            rupees=999, magic=64, max_magic=128,
            sword_level=3, shield_level=2, armor_level=1,
            crystals=0x07,
            follower_id=0, follower_state=0
        )

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(snapshot.to_dict(), f)
            temp_path = f.name

        try:
            with open(temp_path, 'r') as f:
                restored = json.load(f)
            assert restored["game_state"] == 2
            assert restored["crystals"] == 0x07
        finally:
            Path(temp_path).unlink()

    def test_save_multiple_snapshots(self):
        """Test saving multiple snapshots to array."""
        snapshots = []
        for i in range(5):
            snapshots.append(ProgressSnapshot(
                timestamp=1000.0 + i,
                game_state=i,
                story_flags=i,
                story_flags_2=0,
                side_quest_1=0, side_quest_2=0,
                health=24, max_health=24,
                rupees=i * 100, magic=0, max_magic=0,
                sword_level=1, shield_level=0, armor_level=0,
                crystals=0,
                follower_id=0, follower_state=0
            ))

        data = [s.to_dict() for s in snapshots]

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(data, f)
            temp_path = f.name

        try:
            with open(temp_path, 'r') as f:
                restored = json.load(f)
            assert len(restored) == 5
            assert restored[2]["rupees"] == 200
        finally:
            Path(temp_path).unlink()


# =============================================================================
# Edge Case Serialization Tests
# =============================================================================

class TestSerializationEdgeCases:
    """Test serialization edge cases."""

    def test_large_counters(self):
        """Test large counter values serialize correctly."""
        progress = CampaignProgress()
        progress.total_frames_played = 2**31 - 1  # Max 32-bit signed
        progress.iterations_completed = 1000000

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["total_frames_played"] == 2**31 - 1

    def test_unicode_in_notes(self):
        """Test unicode characters in notes."""
        milestone = CampaignMilestone(id="uni", description="Test", goal="A.1")
        milestone.notes.append("日本語テスト")
        milestone.notes.append("Émojis: 🎮🕹️")
        milestone.notes.append("Symbols: ∑∏∫")

        d = milestone.to_dict()
        json_str = json.dumps(d, ensure_ascii=False)
        restored = json.loads(json_str)

        assert "日本語" in restored["notes"][0]

    def test_empty_strings(self):
        """Test empty strings serialize correctly."""
        milestone = CampaignMilestone(id="", description="", goal="")

        d = milestone.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["id"] == ""
        assert restored["description"] == ""

    def test_null_timestamps(self):
        """Test null timestamps serialize as null."""
        progress = CampaignProgress()
        progress.start_time = None
        progress.last_update = None

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["start_time"] is None
        assert restored["last_update"] is None

    def test_zero_values(self):
        """Test zero values serialize correctly."""
        snapshot = ProgressSnapshot(
            timestamp=0.0,
            game_state=0,
            story_flags=0,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=0, max_health=0,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0,
            follower_id=0, follower_state=0
        )

        d = snapshot.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        # to_dict doesn't include timestamp, but includes other fields
        assert restored["game_state"] == 0
        assert restored["health"] == 0

    def test_large_rupee_value(self):
        """Test large rupee value preserved."""
        snapshot = ProgressSnapshot(
            timestamp=0.0,
            game_state=0,
            story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=9999, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0,
            follower_id=0, follower_state=0
        )

        d = snapshot.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["rupees"] == 9999

    def test_nested_data_structures(self):
        """Test nested data structures serialize correctly."""
        progress = CampaignProgress()
        for i in range(3):
            m = CampaignMilestone(id=f"m{i}", description=f"M{i}", goal="A.1")
            m.notes.append(f"Note {i}")
            m.notes.append(f"Another note {i}")
            progress.add_milestone(m)

        d = progress.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert len(restored["milestones"]) == 3
        assert len(restored["milestones"]["m0"]["notes"]) == 2


# =============================================================================
# Validation Result Serialization Tests
# =============================================================================

class TestValidationResultSerialization:
    """Test ValidationResult serialization."""

    def test_pass_result_serializable(self):
        """Test passing result is serializable."""
        result = ValidationResult(
            name="Health Check",
            passed=True,
            expected="0-24",
            actual="24",
            details="Full health"
        )

        d = {
            "name": result.name,
            "passed": result.passed,
            "expected": result.expected,
            "actual": result.actual,
            "details": result.details
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["passed"] is True
        assert restored["name"] == "Health Check"

    def test_fail_result_serializable(self):
        """Test failing result is serializable."""
        result = ValidationResult(
            name="Story Flag Check",
            passed=False,
            expected="INTRO_COMPLETE set",
            actual="No flags",
            details="Missing required story flag"
        )

        d = {
            "name": result.name,
            "passed": result.passed,
            "expected": result.expected,
            "actual": result.actual,
            "details": result.details
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["passed"] is False


class TestProgressReportSerialization:
    """Test ProgressReport serialization."""

    def test_report_serializable(self):
        """Test progress report is serializable."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0,
            snapshot=snapshot,
            checks=[
                ValidationResult("Check1", True, "a", "a"),
                ValidationResult("Check2", False, "b", "c", "Mismatch"),
            ],
            passed=False,
            summary="1/2 passed"
        )

        # Build serializable dict
        d = {
            "timestamp": report.timestamp,
            "snapshot": report.snapshot.to_dict(),
            "checks": [
                {"name": c.name, "passed": c.passed, "expected": c.expected,
                 "actual": c.actual, "details": c.details}
                for c in report.checks
            ],
            "passed": report.passed,
            "summary": report.summary
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["passed"] is False
        assert len(restored["checks"]) == 2


# =============================================================================
# Button/Input Serialization Tests
# =============================================================================

class TestButtonSerialization:
    """Test Button enum serialization."""

    def test_button_value_serializable(self):
        """Test button value is serializable."""
        button = Button.A | Button.B
        d = {"buttons": int(button)}
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["buttons"] == int(Button.A | Button.B)

    def test_button_name_serializable(self):
        """Test button name is serializable."""
        d = {"button": Button.START.name}
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["button"] == "START"

    def test_all_buttons_as_value(self):
        """Test all buttons combined value is serializable."""
        all_buttons = (Button.A | Button.B | Button.X | Button.Y |
                       Button.L | Button.R | Button.START | Button.SELECT |
                       Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT)

        d = {"all_buttons": int(all_buttons)}
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["all_buttons"] == int(all_buttons)


class TestInputFrameSerialization:
    """Test InputFrame serialization."""

    def test_frame_to_dict_serializable(self):
        """Test frame to_dict is JSON serializable."""
        frame = InputFrame(frame_number=10, buttons=Button.A | Button.UP)

        d = frame.to_dict()
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        # to_dict uses "frame" key, not "frame_number"
        assert restored["frame"] == 10
        assert "buttons" in restored

    def test_multiple_frames_serializable(self):
        """Test multiple frames are serializable."""
        frames = [
            InputFrame(frame_number=i, buttons=Button.A if i % 2 == 0 else Button.NONE)
            for i in range(10)
        ]

        d = [f.to_dict() for f in frames]
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert len(restored) == 10


# =============================================================================
# Plan/Goal/Action Serialization Tests
# =============================================================================

class TestGoalSerialization:
    """Test Goal serialization."""

    def test_goal_parameters_serializable(self):
        """Test goal parameters are serializable."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Reach village center",
            parameters={"area_id": 0x29, "x": 512, "y": 480}
        )

        d = {
            "goal_type": goal.goal_type.name,
            "description": goal.description,
            "parameters": goal.parameters
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["goal_type"] == "REACH_LOCATION"
        assert restored["parameters"]["area_id"] == 0x29

    def test_goal_preconditions_serializable(self):
        """Test goal preconditions are serializable."""
        # Note: preconditions are Goal objects, so we serialize differently
        goal = Goal(
            goal_type=GoalType.GET_ITEM,
            description="Get sword",
            preconditions=[]  # Empty list for simple serialization
        )

        d = {
            "goal_type": goal.goal_type.name,
            "description": goal.description,
            "preconditions_count": len(goal.preconditions)
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["preconditions_count"] == 0


class TestPlanSerialization:
    """Test Plan serialization."""

    def test_plan_status_serializable(self):
        """Test plan status is serializable."""
        for status in PlanStatus:
            d = {"status": status.name}
            json_str = json.dumps(d)
            restored = json.loads(json_str)
            assert restored["status"] == status.name

    def test_plan_with_actions_serializable(self):
        """Test plan with actions is serializable."""
        goal = Goal(
            goal_type=GoalType.REACH_LOCATION,
            description="Test",
            parameters={}
        )
        # Action takes name and description, not parameters
        plan = Plan(
            goal=goal,
            actions=[
                Action(name="walk_right", description="Walk right 5 tiles"),
                Action(name="wait", description="Wait 30 frames"),
            ]
        )

        d = {
            "goal": {
                "goal_type": plan.goal.goal_type.name,
                "description": plan.goal.description
            },
            "actions": [
                {"name": a.name, "description": a.description}
                for a in plan.actions
            ],
            "status": plan.status.name
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert len(restored["actions"]) == 2


# =============================================================================
# Collision Map Serialization Tests
# =============================================================================

class TestCollisionMapSerialization:
    """Test CollisionMap serialization patterns."""

    def test_collision_map_bytes_to_list(self):
        """Test collision map bytes can be serialized as list."""
        data = bytes([0, 1, 2, 3, 0x40, 0x08])
        cmap = CollisionMap(data=data, width=3, height=2)

        # Serialize as list of integers
        d = {
            "width": cmap.width,
            "height": cmap.height,
            "tile_size": cmap.tile_size,
            "data": list(cmap.data)
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        assert restored["data"] == [0, 1, 2, 3, 0x40, 0x08]

    def test_collision_map_round_trip(self):
        """Test collision map round-trips through JSON."""
        original_data = bytes([0] * 64 + [1] * 64)
        cmap = CollisionMap(data=original_data, width=64, height=2)

        d = {
            "width": cmap.width,
            "height": cmap.height,
            "data": list(cmap.data)
        }
        json_str = json.dumps(d)
        restored = json.loads(json_str)

        restored_data = bytes(restored["data"])
        assert restored_data == original_data
