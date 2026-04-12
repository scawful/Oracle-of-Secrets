"""Milestone validation and completion criteria tests (Iteration 41).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- E.1: State verification and regression testing
- E.3: Progress flag tracking

These tests verify milestone-based validation workflows integrating
progress_validator and campaign_orchestrator completion criteria.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, PropertyMock
from datetime import datetime, timedelta
import json
import tempfile
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.progress_validator import (
    StoryFlag, GameStateValue, ProgressAddresses,
    ProgressSnapshot, ValidationResult, ProgressReport,
    ProgressValidator, print_progress_report
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, MilestoneStatus, CampaignMilestone,
    CampaignProgress, CampaignOrchestrator, create_campaign
)


# =============================================================================
# Milestone Completion Criteria Tests
# =============================================================================

class TestMilestoneCompletionCriteria:
    """Test milestone completion criteria validation."""

    def test_intro_complete_flag_required_for_loom_beach(self):
        """Test that INTRO_COMPLETE flag is required for LOOM_BEACH state."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=GameStateValue.LOOM_BEACH,
            story_flags=StoryFlag.INTRO_COMPLETE,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )
        # Verify flag consistency
        assert snapshot.has_flag(StoryFlag.INTRO_COMPLETE)

    def test_loom_beach_state_without_flag_fails_validation(self):
        """Test LOOM_BEACH state without INTRO_COMPLETE flag fails."""
        mock_emu = Mock()
        validator = ProgressValidator(mock_emu)

        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=GameStateValue.LOOM_BEACH,
            story_flags=0,  # Missing INTRO_COMPLETE
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )

        results = validator._check_story_consistency(snapshot)
        # Should have a failed check for intro flag consistency
        assert len(results) > 0
        intro_check = next((r for r in results if "Intro" in r.name), None)
        assert intro_check is not None
        assert intro_check.passed is False

    def test_farore_free_requires_farore_rescued_flag(self):
        """Test FARORE_FREE state requires FARORE_RESCUED flag."""
        mock_emu = Mock()
        validator = ProgressValidator(mock_emu)

        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=GameStateValue.FARORE_FREE,
            story_flags=StoryFlag.INTRO_COMPLETE,  # Missing FARORE_RESCUED
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )

        results = validator._check_story_consistency(snapshot)
        farore_check = next((r for r in results if "Farore" in r.name), None)
        assert farore_check is not None
        assert farore_check.passed is False

    def test_farore_free_with_all_required_flags_passes(self):
        """Test FARORE_FREE with correct flags passes validation."""
        mock_emu = Mock()
        validator = ProgressValidator(mock_emu)

        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=GameStateValue.FARORE_FREE,
            story_flags=StoryFlag.INTRO_COMPLETE | StoryFlag.FARORE_RESCUED,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )

        results = validator._check_story_consistency(snapshot)
        # All consistency checks should pass
        for r in results:
            assert r.passed is True

    def test_start_state_has_no_flag_requirements(self):
        """Test START state has no flag requirements."""
        mock_emu = Mock()
        validator = ProgressValidator(mock_emu)

        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=GameStateValue.START,
            story_flags=0,  # No flags needed
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )

        results = validator._check_story_consistency(snapshot)
        # Should have no requirements for START state
        assert len(results) == 0


class TestMilestoneProgressTracking:
    """Test milestone progress tracking across game states."""

    def test_milestone_tracks_game_state_progression(self):
        """Test milestone correctly tracks game state progression."""
        milestone = CampaignMilestone(
            id="reach_loom_beach",
            description="Reach Loom Beach",
            goal="A.2"
        )
        assert milestone.status == MilestoneStatus.NOT_STARTED

        # Simulate progress
        milestone.status = MilestoneStatus.IN_PROGRESS
        assert milestone.status == MilestoneStatus.IN_PROGRESS

        # Complete with note
        milestone.complete("Reached via intro sequence")
        assert milestone.status == MilestoneStatus.COMPLETED
        assert len(milestone.notes) == 1

    def test_multiple_milestones_independent(self):
        """Test multiple milestones track independently."""
        m1 = CampaignMilestone(id="m1", description="First", goal="A.1")
        m2 = CampaignMilestone(id="m2", description="Second", goal="A.2")

        m1.complete()

        assert m1.status == MilestoneStatus.COMPLETED
        assert m2.status == MilestoneStatus.NOT_STARTED

    def test_blocked_milestone_cannot_proceed(self):
        """Test blocked milestone tracking."""
        milestone = CampaignMilestone(
            id="blocked_test",
            description="Blocked milestone",
            goal="B.1"
        )
        milestone.status = MilestoneStatus.BLOCKED
        assert milestone.status == MilestoneStatus.BLOCKED

    def test_milestone_notes_accumulate(self):
        """Test milestone notes accumulate over time."""
        milestone = CampaignMilestone(
            id="noted", description="Noted milestone", goal="C.1"
        )
        milestone.notes.append("First attempt failed")
        milestone.notes.append("Second attempt in progress")
        milestone.complete("Third attempt succeeded")

        assert len(milestone.notes) == 3
        assert "Third attempt succeeded" in milestone.notes


class TestStoryFlagValidation:
    """Test story flag validation specifics."""

    def test_all_story_flags_have_unique_values(self):
        """Test all StoryFlag values are unique powers of 2."""
        flags = [f for f in StoryFlag if not f.name.startswith('STORY_FLAG')]
        values = [f.value for f in flags]
        assert len(values) == len(set(values))

        # Each should be power of 2
        for v in values:
            assert v > 0
            assert (v & (v - 1)) == 0

    def test_story_flag_combination_bitwise(self):
        """Test story flags combine correctly via bitwise OR."""
        combined = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH | StoryFlag.KYDROG_COMPLETE
        assert combined == 0x07

        # Can check each flag
        assert combined & StoryFlag.INTRO_COMPLETE
        assert combined & StoryFlag.LOOM_BEACH
        assert combined & StoryFlag.KYDROG_COMPLETE
        assert not (combined & StoryFlag.FARORE_RESCUED)

    def test_story_flag_removal(self):
        """Test story flags can be removed via bitwise operations."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        removed = flags & ~StoryFlag.LOOM_BEACH

        assert removed & StoryFlag.INTRO_COMPLETE
        assert not (removed & StoryFlag.LOOM_BEACH)

    def test_empty_flags_is_zero(self):
        """Test no flags set equals zero."""
        assert StoryFlag(0) == 0

    def test_all_main_flags_combined(self):
        """Test combining all main story flags."""
        all_flags = (
            StoryFlag.INTRO_COMPLETE |
            StoryFlag.LOOM_BEACH |
            StoryFlag.KYDROG_COMPLETE |
            StoryFlag.FARORE_RESCUED |
            StoryFlag.HALL_OF_SECRETS
        )
        assert all_flags == 0x1F

    def test_reserved_flags_exist(self):
        """Test reserved story flags exist."""
        assert StoryFlag.STORY_FLAG_5 == 0x20
        assert StoryFlag.STORY_FLAG_6 == 0x40
        assert StoryFlag.STORY_FLAG_7 == 0x80


class TestProgressSnapshotValidation:
    """Test ProgressSnapshot validation edge cases."""

    def test_zero_health_snapshot(self):
        """Test snapshot with zero health (dead state)."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=0,  # Dead
            max_health=24,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )
        assert snapshot.hearts == 0.0
        assert snapshot.health_percent == 0.0

    def test_max_health_snapshot(self):
        """Test snapshot with maximum possible health."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=160,  # 20 hearts (max)
            max_health=160,
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )
        assert snapshot.hearts == 20.0
        assert snapshot.max_hearts == 20.0
        assert snapshot.health_percent == 1.0

    def test_partial_heart_calculation(self):
        """Test partial heart calculation."""
        # 3 and 3/8 hearts = 27 health
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=27,
            max_health=64,  # 8 hearts
            rupees=0, magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )
        assert snapshot.hearts == 3.375

    def test_all_crystals_completed(self):
        """Test snapshot with all 8 crystals."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=3,
            story_flags=0x1F,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=160, max_health=160,
            rupees=9999, magic=128, max_magic=128,
            sword_level=4, shield_level=3, armor_level=2,
            crystals=0xFF,  # All 8 dungeons
            follower_id=0, follower_state=0
        )
        assert snapshot.dungeon_count == 8

    def test_max_rupees(self):
        """Test snapshot with maximum rupees."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0,
            health=24, max_health=24,
            rupees=9999,  # Max
            magic=0, max_magic=0,
            sword_level=0, shield_level=0, armor_level=0,
            crystals=0, follower_id=0, follower_state=0
        )
        assert snapshot.rupees == 9999


class TestCampaignProgressCompletion:
    """Test campaign progress completion percentage calculation."""

    def test_zero_milestones_zero_percent(self):
        """Test empty milestones gives 0%."""
        progress = CampaignProgress()
        assert progress.get_completion_percentage() == 0.0

    def test_all_milestones_completed(self):
        """Test all milestones completed gives 100%."""
        progress = CampaignProgress()
        for i in range(5):
            m = CampaignMilestone(id=f"m{i}", description=f"M{i}", goal="A.1")
            m.complete()
            progress.add_milestone(m)
        assert progress.get_completion_percentage() == 100.0

    def test_half_milestones_completed(self):
        """Test half milestones completed gives 50%."""
        progress = CampaignProgress()
        for i in range(4):
            m = CampaignMilestone(id=f"m{i}", description=f"M{i}", goal="A.1")
            if i < 2:
                m.complete()
            progress.add_milestone(m)
        assert progress.get_completion_percentage() == 50.0

    def test_partial_completion_precision(self):
        """Test partial completion with precision."""
        progress = CampaignProgress()
        for i in range(3):
            m = CampaignMilestone(id=f"m{i}", description=f"M{i}", goal="A.1")
            if i == 0:
                m.complete()
            progress.add_milestone(m)
        # 1/3 = 33.33...%
        completion = progress.get_completion_percentage()
        assert 33.0 < completion < 34.0

    def test_complete_milestone_updates_percentage(self):
        """Test completing milestone updates percentage."""
        progress = CampaignProgress()
        m1 = CampaignMilestone(id="m1", description="M1", goal="A.1")
        m2 = CampaignMilestone(id="m2", description="M2", goal="A.2")
        progress.add_milestone(m1)
        progress.add_milestone(m2)

        assert progress.get_completion_percentage() == 0.0

        progress.complete_milestone("m1")
        assert progress.get_completion_percentage() == 50.0

        progress.complete_milestone("m2")
        assert progress.get_completion_percentage() == 100.0


class TestMilestoneStatusTransitions:
    """Test valid milestone status transitions."""

    def test_not_started_to_in_progress(self):
        """Test transition from NOT_STARTED to IN_PROGRESS."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        assert m.status == MilestoneStatus.NOT_STARTED
        m.status = MilestoneStatus.IN_PROGRESS
        assert m.status == MilestoneStatus.IN_PROGRESS

    def test_in_progress_to_completed(self):
        """Test transition from IN_PROGRESS to COMPLETED."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.status = MilestoneStatus.IN_PROGRESS
        m.complete()
        assert m.status == MilestoneStatus.COMPLETED

    def test_not_started_to_completed(self):
        """Test direct transition from NOT_STARTED to COMPLETED."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete()
        assert m.status == MilestoneStatus.COMPLETED

    def test_in_progress_to_blocked(self):
        """Test transition from IN_PROGRESS to BLOCKED."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.status = MilestoneStatus.IN_PROGRESS
        m.status = MilestoneStatus.BLOCKED
        assert m.status == MilestoneStatus.BLOCKED

    def test_blocked_to_in_progress(self):
        """Test transition from BLOCKED back to IN_PROGRESS."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.status = MilestoneStatus.BLOCKED
        m.status = MilestoneStatus.IN_PROGRESS
        assert m.status == MilestoneStatus.IN_PROGRESS


class TestValidationResultDetails:
    """Test ValidationResult details and formatting."""

    def test_result_with_all_fields(self):
        """Test ValidationResult with all fields populated."""
        result = ValidationResult(
            name="Health Check",
            passed=True,
            expected="0-160",
            actual="64",
            details="8 hearts"
        )
        assert result.name == "Health Check"
        assert result.passed is True
        assert result.expected == "0-160"
        assert result.actual == "64"
        assert result.details == "8 hearts"

    def test_result_comparison_pass(self):
        """Test result with matching expected/actual."""
        result = ValidationResult(
            name="Flag Check",
            passed=True,
            expected="0x01",
            actual="0x01"
        )
        assert result.expected == result.actual

    def test_result_comparison_fail(self):
        """Test result with mismatching expected/actual."""
        result = ValidationResult(
            name="State Check",
            passed=False,
            expected="LOOM_BEACH",
            actual="START"
        )
        assert result.expected != result.actual
        assert result.passed is False


class TestProgressReportGeneration:
    """Test ProgressReport generation and formatting."""

    def test_report_all_passed(self):
        """Test report with all checks passed."""
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
                ValidationResult("Check2", True, "b", "b"),
                ValidationResult("Check3", True, "c", "c"),
            ],
            passed=True
        )
        assert report.pass_count == 3
        assert report.fail_count == 0
        assert report.passed is True

    def test_report_some_failed(self):
        """Test report with some checks failed."""
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
                ValidationResult("Check2", False, "b", "x"),
                ValidationResult("Check3", True, "c", "c"),
            ],
            passed=False
        )
        assert report.pass_count == 2
        assert report.fail_count == 1
        assert report.passed is False

    def test_report_all_failed(self):
        """Test report with all checks failed."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=0, max_health=0,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0,
            snapshot=snapshot,
            checks=[
                ValidationResult("C1", False, "a", "x"),
                ValidationResult("C2", False, "b", "y"),
            ],
            passed=False
        )
        assert report.pass_count == 0
        assert report.fail_count == 2


class TestValidatorCaptureProgress:
    """Test ProgressValidator capture_progress method."""

    def test_capture_returns_snapshot(self):
        """Test capture_progress returns ProgressSnapshot."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 0
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        snapshot = validator.capture_progress()

        assert isinstance(snapshot, ProgressSnapshot)

    def test_capture_stores_last_snapshot(self):
        """Test capture_progress stores _last_snapshot."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 42
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        assert validator._last_snapshot is None

        snapshot = validator.capture_progress()
        assert validator._last_snapshot is snapshot

    def test_capture_reads_all_addresses(self):
        """Test capture_progress reads all required addresses."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 0
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        validator.capture_progress()

        # Verify read_memory was called multiple times
        assert mock_emu.read_memory.call_count >= 10


class TestSnapshotComparison:
    """Test snapshot comparison and change detection."""

    @pytest.fixture
    def validator(self):
        """Create validator with mock emulator."""
        return ProgressValidator(Mock())

    def test_compare_detects_flag_set(self, validator):
        """Test comparison detects flag being set."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0,
            story_flags=StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("INTRO_COMPLETE" in c for c in changes)
        assert any("LOOM_BEACH" in c for c in changes)

    def test_compare_detects_flag_cleared(self, validator):
        """Test comparison detects flag being cleared."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0,
            story_flags=StoryFlag.INTRO_COMPLETE,
            story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("CLEARED" in c for c in changes)

    def test_compare_detects_health_gain(self, validator):
        """Test comparison detects health increase."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=16, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("Health" in c and "+" in c for c in changes)

    def test_compare_detects_health_loss(self, validator):
        """Test comparison detects health decrease."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=8, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("Health" in c and "-" in c for c in changes)

    def test_compare_detects_rupee_gain(self, validator):
        """Test comparison detects rupee increase."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=250, magic=0, max_magic=0, sword_level=0, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("Rupees" in c and "+150" in c for c in changes)

    def test_compare_detects_sword_upgrade(self, validator):
        """Test comparison detects sword upgrade."""
        before = ProgressSnapshot(
            timestamp=1000.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        after = ProgressSnapshot(
            timestamp=1001.0, game_state=0, story_flags=0, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=0, magic=0, max_magic=0, sword_level=2, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(before, after)
        assert any("Sword" in c for c in changes)

    def test_compare_identical_snapshots(self, validator):
        """Test comparison of identical snapshots returns empty list."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )

        changes = validator.compare_snapshots(snapshot, snapshot)
        assert len(changes) == 0


class TestCampaignMilestoneSerialization:
    """Test milestone serialization for persistence."""

    def test_milestone_to_dict_complete(self):
        """Test complete milestone serializes correctly."""
        m = CampaignMilestone(id="test", description="Test", goal="A.1")
        m.complete("Success!")

        d = m.to_dict()
        assert d["id"] == "test"
        assert d["status"] == "COMPLETED"
        assert d["completed_at"] is not None
        assert "Success!" in d["notes"]

    def test_milestone_to_dict_blocked(self):
        """Test blocked milestone serializes correctly."""
        m = CampaignMilestone(id="blocked", description="Blocked", goal="B.1")
        m.status = MilestoneStatus.BLOCKED
        m.notes.append("Blocked by bug")

        d = m.to_dict()
        assert d["status"] == "BLOCKED"
        assert "Blocked by bug" in d["notes"]

    def test_progress_to_dict_includes_all_milestones(self):
        """Test progress to_dict includes all milestones."""
        progress = CampaignProgress()
        for i in range(3):
            progress.add_milestone(
                CampaignMilestone(id=f"m{i}", description=f"M{i}", goal="A.1")
            )

        d = progress.to_dict()
        assert len(d["milestones"]) == 3

    def test_progress_to_dict_includes_stats(self):
        """Test progress to_dict includes all statistics."""
        progress = CampaignProgress()
        progress.iterations_completed = 5
        progress.total_frames_played = 1000
        progress.black_screens_detected = 2
        progress.transitions_completed = 10

        d = progress.to_dict()
        assert d["iterations_completed"] == 5
        assert d["total_frames_played"] == 1000
        assert d["black_screens_detected"] == 2
        assert d["transitions_completed"] == 10


class TestProgressAddressConstants:
    """Test progress address constants are correct."""

    def test_game_state_address(self):
        """Test GAME_STATE address."""
        assert ProgressAddresses.GAME_STATE == 0x7EF3C5

    def test_oosprog_in_sram_range(self):
        """Test OOSPROG address is in SRAM range."""
        addr = ProgressAddresses.OOSPROG
        assert 0x7EF000 <= addr <= 0x7EFFFF

    def test_health_addresses_sequential(self):
        """Test health addresses are sequential."""
        assert ProgressAddresses.HEALTH_MAX + 1 == ProgressAddresses.HEALTH_CURRENT

    def test_rupee_addresses_sequential(self):
        """Test rupee addresses are sequential."""
        assert ProgressAddresses.RUPEES_LO + 1 == ProgressAddresses.RUPEES_HI

    def test_item_addresses_sequential(self):
        """Test item addresses are sequential."""
        assert ProgressAddresses.ITEM_SWORD + 1 == ProgressAddresses.ITEM_SHIELD
        assert ProgressAddresses.ITEM_SHIELD + 1 == ProgressAddresses.ITEM_ARMOR

    def test_follower_addresses_sequential(self):
        """Test follower addresses are sequential."""
        assert ProgressAddresses.FOLLOWER_ID + 1 == ProgressAddresses.FOLLOWER_STATE


class TestGameStateValueProgression:
    """Test GameStateValue enum represents valid progression."""

    def test_values_are_sequential(self):
        """Test game state values are sequential starting from 0."""
        assert GameStateValue.START == 0
        assert GameStateValue.LOOM_BEACH == 1
        assert GameStateValue.KYDROG_DONE == 2
        assert GameStateValue.FARORE_FREE == 3

    def test_can_compare_states(self):
        """Test game states can be compared."""
        assert GameStateValue.START < GameStateValue.LOOM_BEACH
        assert GameStateValue.LOOM_BEACH < GameStateValue.KYDROG_DONE
        assert GameStateValue.KYDROG_DONE < GameStateValue.FARORE_FREE

    def test_state_arithmetic(self):
        """Test game state arithmetic."""
        assert GameStateValue.LOOM_BEACH - GameStateValue.START == 1
        assert GameStateValue.FARORE_FREE - GameStateValue.START == 3


class TestProgressValidatorValidation:
    """Test ProgressValidator validate_progression method."""

    def test_validate_progression_returns_report(self):
        """Test validate_progression returns ProgressReport."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 24
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        report = validator.validate_progression()

        assert isinstance(report, ProgressReport)

    def test_validate_progression_includes_health_check(self):
        """Test validate_progression includes health check."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 24
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        report = validator.validate_progression()

        health_check = next((c for c in report.checks if "Health" in c.name), None)
        assert health_check is not None

    def test_validate_progression_includes_rupees_check(self):
        """Test validate_progression includes rupees check."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 100
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        report = validator.validate_progression()

        rupees_check = next((c for c in report.checks if "Rupees" in c.name), None)
        assert rupees_check is not None

    def test_validate_progression_includes_equipment_check(self):
        """Test validate_progression includes equipment check."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 1
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        report = validator.validate_progression()

        equip_check = next((c for c in report.checks if "Equipment" in c.name), None)
        assert equip_check is not None

    def test_validate_progression_includes_dungeon_check(self):
        """Test validate_progression includes dungeon check."""
        mock_emu = Mock()
        mock_read = Mock()
        mock_read.value = 0
        mock_emu.read_memory.return_value = mock_read

        validator = ProgressValidator(mock_emu)
        report = validator.validate_progression()

        dungeon_check = next((c for c in report.checks if "Dungeon" in c.name), None)
        assert dungeon_check is not None


class TestPrintProgressReport:
    """Test print_progress_report function."""

    def test_prints_report_header(self, capsys):
        """Test print includes header."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0, snapshot=snapshot,
            checks=[], passed=True, summary="OK"
        )
        print_progress_report(report)
        captured = capsys.readouterr()
        assert "Progress Validation Report" in captured.out

    def test_prints_game_state(self, capsys):
        """Test print includes game state."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=2, story_flags=0x03, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=48, max_health=48,
            rupees=200, magic=0, max_magic=0, sword_level=2, shield_level=0,
            armor_level=0, crystals=0x01, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0, snapshot=snapshot,
            checks=[], passed=True, summary="OK"
        )
        print_progress_report(report)
        captured = capsys.readouterr()
        assert "GameState: 2" in captured.out

    def test_prints_check_results(self, capsys):
        """Test print includes check results."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0, snapshot=snapshot,
            checks=[
                ValidationResult("TestCheck", True, "expected", "actual")
            ],
            passed=True, summary="1/1 passed"
        )
        print_progress_report(report)
        captured = capsys.readouterr()
        assert "PASS" in captured.out
        assert "TestCheck" in captured.out

    def test_prints_passed_result(self, capsys):
        """Test print shows PASSED for passing report."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0, snapshot=snapshot,
            checks=[], passed=True, summary="OK"
        )
        print_progress_report(report)
        captured = capsys.readouterr()
        assert "PASSED" in captured.out

    def test_prints_failed_result(self, capsys):
        """Test print shows FAILED for failing report."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0, game_state=1, story_flags=0x01, story_flags_2=0,
            side_quest_1=0, side_quest_2=0, health=24, max_health=24,
            rupees=100, magic=0, max_magic=0, sword_level=1, shield_level=0,
            armor_level=0, crystals=0, follower_id=0, follower_state=0
        )
        report = ProgressReport(
            timestamp=1000.0, snapshot=snapshot,
            checks=[ValidationResult("Fail", False, "a", "b")],
            passed=False, summary="0/1 passed"
        )
        print_progress_report(report)
        captured = capsys.readouterr()
        assert "FAILED" in captured.out
