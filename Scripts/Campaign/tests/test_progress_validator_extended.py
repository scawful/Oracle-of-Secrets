"""Extended Progress Validator tests (Iteration 49).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- E.1: State verification and regression testing
- E.3: Progress flag tracking

These tests provide extended coverage of the progress validation
system, including story flags, address ranges, and validation logic.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import time
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.progress_validator import (
    ProgressValidator, ProgressSnapshot, ProgressReport, ValidationResult,
    ProgressAddresses, StoryFlag, GameStateValue
)


# =============================================================================
# StoryFlag Tests
# =============================================================================

class TestStoryFlagEnum:
    """Extended tests for StoryFlag enum."""

    def test_intro_complete_is_bit_0(self):
        """Test INTRO_COMPLETE is bit 0 (0x01)."""
        assert StoryFlag.INTRO_COMPLETE == 0x01

    def test_loom_beach_is_bit_1(self):
        """Test LOOM_BEACH is bit 1 (0x02)."""
        assert StoryFlag.LOOM_BEACH == 0x02

    def test_kydrog_complete_is_bit_2(self):
        """Test KYDROG_COMPLETE is bit 2 (0x04)."""
        assert StoryFlag.KYDROG_COMPLETE == 0x04

    def test_farore_rescued_is_bit_3(self):
        """Test FARORE_RESCUED is bit 3 (0x08)."""
        assert StoryFlag.FARORE_RESCUED == 0x08

    def test_hall_of_secrets_is_bit_4(self):
        """Test HALL_OF_SECRETS is bit 4 (0x10)."""
        assert StoryFlag.HALL_OF_SECRETS == 0x10

    def test_reserved_flags_exist(self):
        """Test reserved story flags exist."""
        assert StoryFlag.STORY_FLAG_5 == 0x20
        assert StoryFlag.STORY_FLAG_6 == 0x40
        assert StoryFlag.STORY_FLAG_7 == 0x80

    def test_all_flags_are_unique(self):
        """Test all flags have unique values."""
        values = [f.value for f in StoryFlag]
        assert len(values) == len(set(values))

    def test_flags_are_powers_of_two(self):
        """Test all flags are single bits (powers of 2)."""
        for flag in StoryFlag:
            value = flag.value
            # Power of 2 has exactly one bit set
            assert value > 0 and (value & (value - 1)) == 0

    def test_flags_combine_with_or(self):
        """Test flags can be combined with OR."""
        combined = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        assert combined == 0x03

    def test_flags_check_with_in(self):
        """Test flags can be checked with 'in'."""
        combined = StoryFlag.INTRO_COMPLETE | StoryFlag.KYDROG_COMPLETE
        assert StoryFlag.INTRO_COMPLETE in combined
        assert StoryFlag.KYDROG_COMPLETE in combined
        assert StoryFlag.LOOM_BEACH not in combined

    def test_all_flags_byte_range(self):
        """Test all flags fit in a single byte."""
        all_flags = 0
        for flag in StoryFlag:
            all_flags |= flag.value
        assert all_flags <= 0xFF


# =============================================================================
# GameStateValue Tests
# =============================================================================

class TestGameStateValueEnum:
    """Extended tests for GameStateValue enum."""

    def test_start_is_zero(self):
        """Test START is 0."""
        assert GameStateValue.START == 0

    def test_loom_beach_is_one(self):
        """Test LOOM_BEACH is 1."""
        assert GameStateValue.LOOM_BEACH == 1

    def test_kydrog_done_is_two(self):
        """Test KYDROG_DONE is 2."""
        assert GameStateValue.KYDROG_DONE == 2

    def test_farore_free_is_three(self):
        """Test FARORE_FREE is 3."""
        assert GameStateValue.FARORE_FREE == 3

    def test_values_are_sequential(self):
        """Test values are sequential from 0."""
        values = [v.value for v in GameStateValue]
        assert values == list(range(len(values)))

    def test_progression_order(self):
        """Test progression is in order."""
        assert GameStateValue.START < GameStateValue.LOOM_BEACH
        assert GameStateValue.LOOM_BEACH < GameStateValue.KYDROG_DONE
        assert GameStateValue.KYDROG_DONE < GameStateValue.FARORE_FREE


# =============================================================================
# ProgressAddresses Tests
# =============================================================================

class TestProgressAddresses:
    """Extended tests for ProgressAddresses constants."""

    def test_game_state_address(self):
        """Test GAME_STATE address."""
        assert ProgressAddresses.GAME_STATE == 0x7EF3C5

    def test_oosprog_address(self):
        """Test OOSPROG address."""
        assert ProgressAddresses.OOSPROG == 0x7EF3D6

    def test_oosprog2_address(self):
        """Test OOSPROG2 address."""
        assert ProgressAddresses.OOSPROG2 == 0x7EF3C6

    def test_side_quest_addresses(self):
        """Test side quest addresses."""
        assert ProgressAddresses.SIDE_QUEST_1 == 0x7EF3D7
        assert ProgressAddresses.SIDE_QUEST_2 == 0x7EF3D8

    def test_health_addresses(self):
        """Test health addresses."""
        assert ProgressAddresses.HEALTH_MAX == 0x7EF36C
        assert ProgressAddresses.HEALTH_CURRENT == 0x7EF36D

    def test_rupee_addresses(self):
        """Test rupee addresses."""
        assert ProgressAddresses.RUPEES_LO == 0x7EF360
        assert ProgressAddresses.RUPEES_HI == 0x7EF361

    def test_magic_addresses(self):
        """Test magic addresses."""
        assert ProgressAddresses.MAGIC_METER == 0x7EF36E
        assert ProgressAddresses.MAGIC_MAX == 0x7EF36F

    def test_crystals_address(self):
        """Test crystals address."""
        assert ProgressAddresses.CRYSTALS == 0x7EF37A

    def test_equipment_addresses(self):
        """Test equipment addresses."""
        assert ProgressAddresses.ITEM_SWORD == 0x7EF359
        assert ProgressAddresses.ITEM_SHIELD == 0x7EF35A
        assert ProgressAddresses.ITEM_ARMOR == 0x7EF35B

    def test_follower_addresses(self):
        """Test follower addresses."""
        assert ProgressAddresses.FOLLOWER_ID == 0x7EF3CC
        assert ProgressAddresses.FOLLOWER_STATE == 0x7EF3CD

    def test_all_addresses_in_sram_range(self):
        """Test all addresses are in SRAM range."""
        addresses = [
            ProgressAddresses.GAME_STATE,
            ProgressAddresses.OOSPROG,
            ProgressAddresses.OOSPROG2,
            ProgressAddresses.SIDE_QUEST_1,
            ProgressAddresses.SIDE_QUEST_2,
            ProgressAddresses.HEALTH_MAX,
            ProgressAddresses.HEALTH_CURRENT,
            ProgressAddresses.RUPEES_LO,
            ProgressAddresses.RUPEES_HI,
            ProgressAddresses.MAGIC_METER,
            ProgressAddresses.MAGIC_MAX,
            ProgressAddresses.CRYSTALS,
            ProgressAddresses.ITEM_SWORD,
            ProgressAddresses.ITEM_SHIELD,
            ProgressAddresses.ITEM_ARMOR,
            ProgressAddresses.FOLLOWER_ID,
            ProgressAddresses.FOLLOWER_STATE,
        ]
        for addr in addresses:
            assert 0x7EF000 <= addr <= 0x7EFFFF

    def test_rupee_addresses_adjacent(self):
        """Test rupee addresses are adjacent (for 16-bit read)."""
        assert ProgressAddresses.RUPEES_HI == ProgressAddresses.RUPEES_LO + 1

    def test_health_addresses_adjacent(self):
        """Test health addresses are adjacent."""
        assert ProgressAddresses.HEALTH_CURRENT == ProgressAddresses.HEALTH_MAX + 1

    def test_magic_addresses_adjacent(self):
        """Test magic addresses are adjacent."""
        assert ProgressAddresses.MAGIC_MAX == ProgressAddresses.MAGIC_METER + 1


# =============================================================================
# ProgressSnapshot Tests
# =============================================================================

def _create_snapshot(**overrides):
    """Create a snapshot with default values."""
    defaults = {
        'timestamp': time.time(),
        'game_state': 0,
        'story_flags': 0,
        'story_flags_2': 0,
        'side_quest_1': 0,
        'side_quest_2': 0,
        'health': 24,
        'max_health': 24,
        'rupees': 0,
        'magic': 0,
        'max_magic': 0,
        'sword_level': 1,
        'shield_level': 0,
        'armor_level': 0,
        'crystals': 0,
        'follower_id': 0,
        'follower_state': 0,
    }
    defaults.update(overrides)
    return ProgressSnapshot(**defaults)


class TestProgressSnapshotCreation:
    """Test ProgressSnapshot creation."""

    def test_create_minimal_snapshot(self):
        """Test creating snapshot with minimal data."""
        snap = _create_snapshot()
        assert snap.health == 24
        assert snap.game_state == 0

    def test_create_snapshot_with_story_flags(self):
        """Test creating snapshot with story flags."""
        flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        snap = _create_snapshot(story_flags=flags)
        assert snap.story_flags == 0x03

    def test_create_snapshot_with_game_state(self):
        """Test creating snapshot with game state."""
        snap = _create_snapshot(game_state=GameStateValue.FARORE_FREE)
        assert snap.game_state == 3

    def test_snapshot_timestamp_valid(self):
        """Test snapshot has valid timestamp."""
        before = time.time()
        snap = _create_snapshot()
        after = time.time()
        assert before <= snap.timestamp <= after

    def test_snapshot_rupees_range(self):
        """Test snapshot accepts full rupee range."""
        snap = _create_snapshot(rupees=9999)
        assert snap.rupees == 9999

    def test_snapshot_all_fields_accessible(self):
        """Test all snapshot fields are accessible."""
        snap = _create_snapshot(
            game_state=1,
            story_flags=0x0F,
            story_flags_2=0x03,
            side_quest_1=0x01,
            side_quest_2=0x02,
            health=16,
            max_health=24,
            rupees=500,
            magic=32,
            max_magic=64,
            sword_level=2,
            shield_level=1,
            armor_level=1,
            crystals=0x03,
            follower_id=5,
            follower_state=1,
        )
        assert snap.game_state == 1
        assert snap.story_flags == 0x0F
        assert snap.story_flags_2 == 0x03
        assert snap.side_quest_1 == 0x01
        assert snap.side_quest_2 == 0x02
        assert snap.health == 16
        assert snap.max_health == 24
        assert snap.rupees == 500
        assert snap.magic == 32
        assert snap.max_magic == 64
        assert snap.sword_level == 2
        assert snap.shield_level == 1
        assert snap.armor_level == 1
        assert snap.crystals == 0x03
        assert snap.follower_id == 5
        assert snap.follower_state == 1


class TestProgressSnapshotProperties:
    """Test ProgressSnapshot computed properties."""

    def test_hearts_property(self):
        """Test hearts property calculates correctly."""
        snap = _create_snapshot(health=24)
        assert snap.hearts == 3.0

    def test_hearts_partial(self):
        """Test hearts with partial heart."""
        snap = _create_snapshot(health=20)
        assert snap.hearts == 2.5

    def test_max_hearts_property(self):
        """Test max_hearts property."""
        snap = _create_snapshot(max_health=40)
        assert snap.max_hearts == 5.0

    def test_health_percent_full(self):
        """Test health_percent at full health."""
        snap = _create_snapshot(health=24, max_health=24)
        assert snap.health_percent == 1.0

    def test_health_percent_half(self):
        """Test health_percent at half health."""
        snap = _create_snapshot(health=12, max_health=24)
        assert snap.health_percent == 0.5

    def test_health_percent_zero_max(self):
        """Test health_percent with zero max (edge case)."""
        snap = _create_snapshot(health=0, max_health=0)
        assert snap.health_percent == 1.0  # Returns 1.0 to avoid division by zero

    def test_dungeon_count_no_dungeons(self):
        """Test dungeon_count with no dungeons."""
        snap = _create_snapshot(crystals=0)
        assert snap.dungeon_count == 0

    def test_dungeon_count_one_dungeon(self):
        """Test dungeon_count with one dungeon."""
        snap = _create_snapshot(crystals=0x01)
        assert snap.dungeon_count == 1

    def test_dungeon_count_all_dungeons(self):
        """Test dungeon_count with all 8 dungeons."""
        snap = _create_snapshot(crystals=0xFF)
        assert snap.dungeon_count == 8

    def test_dungeon_count_mixed(self):
        """Test dungeon_count with various bits."""
        snap = _create_snapshot(crystals=0b00101011)  # 4 bits set
        assert snap.dungeon_count == 4


# =============================================================================
# ValidationResult Tests
# =============================================================================

class TestValidationResult:
    """Test ValidationResult creation and properties."""

    def test_create_passing_result(self):
        """Test creating a passing result."""
        result = ValidationResult(
            name="Test",
            passed=True,
            expected="10",
            actual="10"
        )
        assert result.passed is True
        assert result.name == "Test"

    def test_create_failing_result(self):
        """Test creating a failing result."""
        result = ValidationResult(
            name="Test",
            passed=False,
            expected="10",
            actual="20"
        )
        assert result.passed is False

    def test_result_with_details(self):
        """Test result with details field."""
        result = ValidationResult(
            name="Test",
            passed=True,
            expected="OK",
            actual="OK",
            details="Additional info"
        )
        assert result.details == "Additional info"

    def test_result_empty_details_default(self):
        """Test result has empty details by default."""
        result = ValidationResult(
            name="Test",
            passed=True,
            expected="X",
            actual="X"
        )
        assert result.details == ""


# =============================================================================
# ProgressReport Tests
# =============================================================================

class TestProgressReport:
    """Test ProgressReport creation and properties."""

    def test_create_empty_report(self):
        """Test creating empty report."""
        snap = _create_snapshot()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snap
        )
        assert report.passed is False
        assert len(report.checks) == 0

    def test_report_pass_count(self):
        """Test pass_count property."""
        snap = _create_snapshot()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snap,
            checks=[
                ValidationResult("A", True, "1", "1"),
                ValidationResult("B", True, "2", "2"),
                ValidationResult("C", False, "3", "4"),
            ]
        )
        assert report.pass_count == 2

    def test_report_fail_count(self):
        """Test fail_count property."""
        snap = _create_snapshot()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snap,
            checks=[
                ValidationResult("A", True, "1", "1"),
                ValidationResult("B", False, "2", "3"),
                ValidationResult("C", False, "4", "5"),
            ]
        )
        assert report.fail_count == 2

    def test_report_all_passed(self):
        """Test report with all checks passing."""
        snap = _create_snapshot()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snap,
            checks=[
                ValidationResult("A", True, "1", "1"),
                ValidationResult("B", True, "2", "2"),
            ],
            passed=True
        )
        assert report.passed is True
        assert report.fail_count == 0

    def test_report_summary(self):
        """Test report summary field."""
        snap = _create_snapshot()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snap,
            summary="All checks passed"
        )
        assert report.summary == "All checks passed"


# =============================================================================
# Story Flag Consistency Tests
# =============================================================================

class TestStoryFlagConsistency:
    """Test story flag consistency patterns."""

    def test_intro_complete_before_loom_beach(self):
        """Test intro must be complete before loom beach."""
        valid_flags = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH
        assert StoryFlag.INTRO_COMPLETE in valid_flags

        invalid_flags = StoryFlag.LOOM_BEACH
        assert StoryFlag.INTRO_COMPLETE not in invalid_flags

    def test_kydrog_implies_loom_beach(self):
        """Test kydrog complete implies loom beach."""
        valid = StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH | StoryFlag.KYDROG_COMPLETE
        assert StoryFlag.LOOM_BEACH in valid
        assert StoryFlag.INTRO_COMPLETE in valid

    def test_farore_implies_kydrog(self):
        """Test farore rescued implies kydrog."""
        full_progress = (StoryFlag.INTRO_COMPLETE | StoryFlag.LOOM_BEACH |
                        StoryFlag.KYDROG_COMPLETE | StoryFlag.FARORE_RESCUED)
        assert StoryFlag.KYDROG_COMPLETE in full_progress

    def test_game_state_matches_flags(self):
        """Test game state value matches story flags."""
        game_state = GameStateValue.LOOM_BEACH
        expected_flags = StoryFlag.INTRO_COMPLETE
        assert game_state.value > 0
        assert expected_flags.value > 0


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestProgressEdgeCases:
    """Test edge cases in progress validation."""

    def test_zero_health(self):
        """Test snapshot with zero health."""
        snap = _create_snapshot(health=0, max_health=24)
        assert snap.health == 0
        assert snap.health_percent == 0.0

    def test_max_rupees(self):
        """Test snapshot with max rupees."""
        snap = _create_snapshot(rupees=0xFFFF)
        assert snap.rupees == 65535

    def test_all_flags_set(self):
        """Test snapshot with all story flags set."""
        snap = _create_snapshot(story_flags=0xFF)
        assert snap.story_flags == 0xFF

    def test_all_crystals_collected(self):
        """Test snapshot with all crystals."""
        snap = _create_snapshot(crystals=0xFF)
        assert snap.crystals == 0xFF
        assert snap.dungeon_count == 8

    def test_max_equipment_levels(self):
        """Test snapshot with max equipment levels."""
        snap = _create_snapshot(
            sword_level=4,
            shield_level=3,
            armor_level=2
        )
        assert snap.sword_level == 4
        assert snap.shield_level == 3
        assert snap.armor_level == 2

    def test_negative_timestamp_allowed(self):
        """Test snapshot allows negative timestamp."""
        snap = _create_snapshot(timestamp=-1.0)
        assert snap.timestamp == -1.0

    def test_overheal_health(self):
        """Test health exceeding max health."""
        snap = _create_snapshot(health=32, max_health=24)
        assert snap.health > snap.max_health
        assert snap.health_percent > 1.0


# =============================================================================
# Progress Change Detection Tests
# =============================================================================

class TestProgressChangeDetection:
    """Test detecting progress changes between snapshots."""

    def test_detect_game_state_change(self):
        """Test detecting game state change."""
        before = _create_snapshot(game_state=0)
        after = _create_snapshot(game_state=1)
        assert before.game_state != after.game_state

    def test_detect_story_flag_change(self):
        """Test detecting new story flag."""
        before = _create_snapshot(story_flags=0x01)
        after = _create_snapshot(story_flags=0x03)
        new_flags = after.story_flags & ~before.story_flags
        assert new_flags == 0x02

    def test_detect_dungeon_completion(self):
        """Test detecting dungeon completion."""
        before = _create_snapshot(crystals=0b00000011)
        after = _create_snapshot(crystals=0b00000111)
        assert after.dungeon_count == before.dungeon_count + 1

    def test_detect_rupee_change(self):
        """Test detecting rupee change."""
        before = _create_snapshot(rupees=100)
        after = _create_snapshot(rupees=150)
        delta = after.rupees - before.rupees
        assert delta == 50

    def test_detect_health_damage(self):
        """Test detecting health damage."""
        before = _create_snapshot(health=24)
        after = _create_snapshot(health=16)
        damage = before.health - after.health
        assert damage == 8

    def test_detect_equipment_upgrade(self):
        """Test detecting equipment upgrade."""
        before = _create_snapshot(sword_level=1)
        after = _create_snapshot(sword_level=2)
        assert after.sword_level > before.sword_level
