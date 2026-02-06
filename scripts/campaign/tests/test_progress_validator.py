"""Tests for progress_validator module.

These tests verify the progress flag and player state validation
functionality without requiring a running emulator (mock-based tests).
"""

import pytest
from unittest.mock import Mock, patch, MagicMock
import json
from pathlib import Path

import sys
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.progress_validator import (
    StoryFlag,
    GameStateValue,
    ProgressAddresses,
    ProgressSnapshot,
    ProgressReport,
    ProgressValidator,
    ValidationResult,
    print_progress_report,
)


class TestStoryFlag:
    """Tests for StoryFlag enum."""

    def test_intro_complete_value(self):
        """Test INTRO_COMPLETE flag value."""
        assert StoryFlag.INTRO_COMPLETE == 0x01

    def test_hall_of_secrets_value(self):
        """Test HALL_OF_SECRETS flag value."""
        assert StoryFlag.HALL_OF_SECRETS == 0x10

    def test_flag_combination(self):
        """Test combining flags."""
        combined = StoryFlag.INTRO_COMPLETE | StoryFlag.FARORE_RESCUED
        assert combined == 0x09

    def test_flag_check(self):
        """Test checking if flag is set."""
        flags = 0x09  # INTRO_COMPLETE | FARORE_RESCUED
        assert flags & StoryFlag.INTRO_COMPLETE
        assert flags & StoryFlag.FARORE_RESCUED
        assert not (flags & StoryFlag.HALL_OF_SECRETS)


class TestGameStateValue:
    """Tests for GameStateValue enum."""

    def test_state_values(self):
        """Test game state values."""
        assert GameStateValue.START == 0
        assert GameStateValue.LOOM_BEACH == 1
        assert GameStateValue.KYDROG_DONE == 2
        assert GameStateValue.FARORE_FREE == 3


class TestProgressAddresses:
    """Tests for progress address constants."""

    def test_oosprog_address(self):
        """Test OOSPROG address is correct."""
        assert ProgressAddresses.OOSPROG == 0x7EF3D6

    def test_game_state_address(self):
        """Test GameState address is correct."""
        assert ProgressAddresses.GAME_STATE == 0x7EF3C5

    def test_health_addresses(self):
        """Test health addresses are correct."""
        assert ProgressAddresses.HEALTH_CURRENT == 0x7EF36D
        assert ProgressAddresses.HEALTH_MAX == 0x7EF36C


class TestProgressSnapshot:
    """Tests for ProgressSnapshot dataclass."""

    @pytest.fixture
    def basic_snapshot(self):
        """Create a basic progress snapshot."""
        return ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,  # LOOM_BEACH
            story_flags=0x01,  # INTRO_COMPLETE
            story_flags_2=0x00,
            side_quest_1=0x00,
            side_quest_2=0x00,
            health=24,  # 3 hearts
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0x00,
            follower_id=0,
            follower_state=0,
        )

    @pytest.fixture
    def advanced_snapshot(self):
        """Create an advanced progress snapshot."""
        return ProgressSnapshot(
            timestamp=2000.0,
            game_state=3,  # FARORE_FREE
            story_flags=0x19,  # INTRO | FARORE | HALL_OF_SECRETS
            story_flags_2=0x05,
            side_quest_1=0x03,
            side_quest_2=0x00,
            health=64,  # 8 hearts
            max_health=80,  # 10 max hearts
            rupees=500,
            magic=32,
            max_magic=64,
            sword_level=2,
            shield_level=1,
            armor_level=1,
            crystals=0x03,  # 2 dungeons completed
            follower_id=1,
            follower_state=2,
        )

    def test_hearts_property(self, basic_snapshot):
        """Test hearts calculation."""
        assert basic_snapshot.hearts == 3.0

    def test_max_hearts_property(self, basic_snapshot):
        """Test max hearts calculation."""
        assert basic_snapshot.max_hearts == 3.0

    def test_health_percent(self, advanced_snapshot):
        """Test health percentage calculation."""
        assert advanced_snapshot.health_percent == 0.8  # 64/80

    def test_health_percent_max(self, basic_snapshot):
        """Test health percentage at full."""
        assert basic_snapshot.health_percent == 1.0

    def test_dungeon_count(self, advanced_snapshot):
        """Test dungeon count from crystals."""
        assert advanced_snapshot.dungeon_count == 2

    def test_dungeon_count_zero(self, basic_snapshot):
        """Test dungeon count when no crystals."""
        assert basic_snapshot.dungeon_count == 0

    def test_to_dict(self, basic_snapshot):
        """Test serialization to dict."""
        d = basic_snapshot.to_dict()
        assert d['game_state'] == 1
        assert d['story_flags'] == 0x01
        assert d['health'] == 24
        assert d['rupees'] == 100
        assert d['dungeon_count'] == 0


class TestProgressValidator:
    """Tests for ProgressValidator with mocks."""

    @pytest.fixture
    def mock_emulator(self):
        """Create a mock emulator."""
        emu = Mock()

        # Default return values for progress reading
        def read_memory(addr, size=1):
            mock_read = Mock()
            values = {
                ProgressAddresses.GAME_STATE: 1,
                ProgressAddresses.OOSPROG: 0x01,
                ProgressAddresses.OOSPROG2: 0x00,
                ProgressAddresses.SIDE_QUEST_1: 0x00,
                ProgressAddresses.SIDE_QUEST_2: 0x00,
                ProgressAddresses.HEALTH_CURRENT: 24,
                ProgressAddresses.HEALTH_MAX: 24,
                ProgressAddresses.RUPEES_LO: 100,
                ProgressAddresses.MAGIC_METER: 0,
                ProgressAddresses.MAGIC_MAX: 0,
                ProgressAddresses.ITEM_SWORD: 1,
                ProgressAddresses.ITEM_SHIELD: 0,
                ProgressAddresses.ITEM_ARMOR: 0,
                ProgressAddresses.CRYSTALS: 0,
                ProgressAddresses.FOLLOWER_ID: 0,
                ProgressAddresses.FOLLOWER_STATE: 0,
            }
            mock_read.value = values.get(addr, 0)
            return mock_read

        emu.read_memory.side_effect = read_memory
        return emu

    @pytest.fixture
    def validator(self, mock_emulator):
        """Create validator with mock emulator."""
        return ProgressValidator(mock_emulator)

    def test_capture_progress(self, validator):
        """Test capturing progress snapshot."""
        snapshot = validator.capture_progress()

        assert snapshot.game_state == 1
        assert snapshot.story_flags == 0x01
        assert snapshot.health == 24
        assert snapshot.sword_level == 1

    def test_validate_progression_passes(self, validator):
        """Test validation passes with valid state."""
        report = validator.validate_progression()

        # All basic checks should pass
        assert report.passed is True
        assert len(report.checks) > 0
        assert all(c.passed for c in report.checks)

    def test_health_validation_invalid(self, mock_emulator):
        """Test health validation with invalid values."""
        # Override to return invalid health
        def bad_health(addr, size=1):
            mock_read = Mock()
            if addr == ProgressAddresses.HEALTH_CURRENT:
                mock_read.value = 200  # Over max possible
            elif addr == ProgressAddresses.HEALTH_MAX:
                mock_read.value = 24
            else:
                mock_read.value = 0
            return mock_read

        mock_emulator.read_memory.side_effect = bad_health
        validator = ProgressValidator(mock_emulator)
        report = validator.validate_progression()

        # Should have at least one failed check
        health_check = next((c for c in report.checks if "Health" in c.name), None)
        assert health_check is not None
        assert health_check.passed is False

    def test_compare_snapshots(self, validator):
        """Test snapshot comparison."""
        before = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0x00,
            side_quest_1=0x00,
            side_quest_2=0x00,
            health=24,
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0x00,
            follower_id=0,
            follower_state=0,
        )

        after = ProgressSnapshot(
            timestamp=2000.0,
            game_state=2,  # Changed
            story_flags=0x03,  # Added LOOM_BEACH flag
            story_flags_2=0x00,
            side_quest_1=0x00,
            side_quest_2=0x00,
            health=16,  # Lost health
            max_health=24,
            rupees=150,  # Gained rupees
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0x01,  # Completed dungeon
            follower_id=0,
            follower_state=0,
        )

        changes = validator.compare_snapshots(before, after)

        # Should detect multiple changes
        assert len(changes) >= 3
        assert any("GameState" in c for c in changes)
        assert any("Rupees" in c for c in changes)
        assert any("Crystal" in c or "dungeon" in c.lower() for c in changes)


class TestValidationResult:
    """Tests for ValidationResult dataclass."""

    def test_pass_result(self):
        """Test creating a passing result."""
        result = ValidationResult(
            name="Test Check",
            passed=True,
            expected="valid",
            actual="valid",
        )
        assert result.passed is True

    def test_fail_result_with_details(self):
        """Test creating a failing result with details."""
        result = ValidationResult(
            name="Health Check",
            passed=False,
            expected="0-24",
            actual="200",
            details="Value exceeds max health",
        )
        assert result.passed is False
        assert "exceeds" in result.details


class TestProgressReport:
    """Tests for ProgressReport dataclass."""

    @pytest.fixture
    def sample_report(self):
        """Create a sample report."""
        snapshot = ProgressSnapshot(
            timestamp=1000.0,
            game_state=1,
            story_flags=0x01,
            story_flags_2=0x00,
            side_quest_1=0x00,
            side_quest_2=0x00,
            health=24,
            max_health=24,
            rupees=100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=0,
            armor_level=0,
            crystals=0x00,
            follower_id=0,
            follower_state=0,
        )
        return ProgressReport(
            timestamp=1000.0,
            snapshot=snapshot,
            checks=[
                ValidationResult("Check 1", True, "a", "a"),
                ValidationResult("Check 2", True, "b", "b"),
                ValidationResult("Check 3", False, "c", "d"),
            ],
            passed=False,
            summary="2/3 passed"
        )

    def test_pass_count(self, sample_report):
        """Test pass count calculation."""
        assert sample_report.pass_count == 2

    def test_fail_count(self, sample_report):
        """Test fail count calculation."""
        assert sample_report.fail_count == 1
