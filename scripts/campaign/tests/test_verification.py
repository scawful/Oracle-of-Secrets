"""Tests for verification module.

Verifies the strict verification system works correctly.
"""

import pytest
import sys
from pathlib import Path
from unittest.mock import Mock

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.verification import (
    VerificationLevel,
    MemoryCheck,
    VerificationResult,
    VerificationReport,
    CriticalAddresses,
    StrictVerifier,
    PLAYABLE_STATE_CHECKS,
    MOVEMENT_CHECKS,
    BLACK_SCREEN_CHECKS,
)
from scripts.campaign.emulator_abstraction import MemoryRead


class TestVerificationLevel:
    """Tests for VerificationLevel enum."""

    def test_basic_lowest(self):
        """Test BASIC is lowest level."""
        assert VerificationLevel.BASIC < VerificationLevel.STANDARD

    def test_paranoid_highest(self):
        """Test PARANOID is highest level."""
        assert VerificationLevel.PARANOID > VerificationLevel.STRICT


class TestMemoryCheck:
    """Tests for MemoryCheck dataclass."""

    def test_basic_check(self):
        """Test basic memory check creation."""
        check = MemoryCheck(0x7E0010, "GameMode")
        assert check.address == 0x7E0010
        assert check.name == "GameMode"
        assert check.size == 1

    def test_expected_value_check(self):
        """Test check with expected value."""
        check = MemoryCheck(0x7E001A, "INIDISP", expected_value=0x0F)
        assert check.expected_value == 0x0F

    def test_expected_range_check(self):
        """Test check with expected range."""
        check = MemoryCheck(0x7E0010, "GameMode", expected_range=(0x07, 0x09))
        assert check.expected_range == (0x07, 0x09)

    def test_must_change_check(self):
        """Test check that expects change."""
        check = MemoryCheck(0x7E0022, "Link X", must_change=True)
        assert check.must_change is True

    def test_bitmask_check(self):
        """Test check with bitmask."""
        check = MemoryCheck(0x7E001A, "INIDISP bit 7", bitmask=0x80)
        assert check.bitmask == 0x80


class TestVerificationResult:
    """Tests for VerificationResult dataclass."""

    def test_pass_result(self):
        """Test passing result."""
        result = VerificationResult(
            passed=True,
            check_name="Test",
            expected="0x0F",
            actual="0x0F"
        )
        assert result.passed is True

    def test_fail_result(self):
        """Test failing result."""
        result = VerificationResult(
            passed=False,
            check_name="Test",
            expected="0x0F",
            actual="0x80"
        )
        assert result.passed is False


class TestVerificationReport:
    """Tests for VerificationReport dataclass."""

    @pytest.fixture
    def sample_report(self):
        """Create sample report with mixed results."""
        return VerificationReport(
            timestamp=1000.0,
            level=VerificationLevel.STANDARD,
            checks=[
                VerificationResult(True, "Check1", "A", "A"),
                VerificationResult(True, "Check2", "B", "B"),
                VerificationResult(False, "Check3", "C", "D"),
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


class TestCriticalAddresses:
    """Tests for CriticalAddresses constants."""

    def test_game_mode_address(self):
        """Verify GameMode address."""
        assert CriticalAddresses.GAME_MODE == 0x7E0010

    def test_inidisp_address(self):
        """Verify INIDISP address."""
        assert CriticalAddresses.INIDISP == 0x7E001A

    def test_link_x_addresses(self):
        """Verify Link X position addresses."""
        assert CriticalAddresses.LINK_X_LO == 0x7E0022
        assert CriticalAddresses.LINK_X_HI == 0x7E0023

    def test_health_addresses(self):
        """Verify health addresses."""
        assert CriticalAddresses.HEALTH_CURRENT == 0x7EF36D
        assert CriticalAddresses.HEALTH_MAX == 0x7EF36C

    def test_oosprog_address(self):
        """Verify OOSPROG story flag address."""
        assert CriticalAddresses.OOSPROG == 0x7EF3D6


class TestPredefinedChecks:
    """Tests for predefined check lists."""

    def test_playable_state_checks_exist(self):
        """Verify playable state checks defined."""
        assert len(PLAYABLE_STATE_CHECKS) >= 3

    def test_movement_checks_exist(self):
        """Verify movement checks defined."""
        assert len(MOVEMENT_CHECKS) >= 3

    def test_black_screen_checks_exist(self):
        """Verify black screen checks defined."""
        assert len(BLACK_SCREEN_CHECKS) >= 2


class TestStrictVerifier:
    """Tests for StrictVerifier class."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        emu.read_memory.return_value = MemoryRead(0, 0, 1)
        return emu

    @pytest.fixture
    def verifier(self, mock_emulator):
        """Create verifier with mock emulator."""
        return StrictVerifier(mock_emulator, VerificationLevel.STANDARD)

    def test_capture_snapshot(self, verifier, mock_emulator):
        """Test snapshot capture."""
        mock_emulator.read_memory.side_effect = [
            MemoryRead(0x7E0010, 0x09, 1),
            MemoryRead(0x7E0011, 0x00, 1),
        ]
        snapshot = verifier.capture_snapshot([0x7E0010, 0x7E0011])

        assert snapshot[0x7E0010] == 0x09
        assert snapshot[0x7E0011] == 0x00

    def test_verify_playable_state_pass(self, verifier, mock_emulator):
        """Test playable state verification - pass."""
        mock_emulator.read_memory.side_effect = [
            MemoryRead(0x7E0010, 0x09, 1),  # Mode = overworld
            MemoryRead(0x7E0011, 0x00, 1),  # Submodule = 0
            MemoryRead(0x7E001A, 0x0F, 1),  # INIDISP = screen on
        ]

        report = verifier.verify_playable_state()

        assert report.passed is True
        assert report.pass_count == 3

    def test_verify_playable_state_fail_black_screen(self, verifier, mock_emulator):
        """Test playable state verification - fail on black screen."""
        mock_emulator.read_memory.side_effect = [
            MemoryRead(0x7E0010, 0x07, 1),  # Mode = dungeon
            MemoryRead(0x7E0011, 0x00, 1),  # Submodule = 0
            MemoryRead(0x7E001A, 0x80, 1),  # INIDISP = screen OFF
        ]

        report = verifier.verify_playable_state()

        assert report.passed is False
        # Check that screen visibility failed
        screen_check = next(c for c in report.checks if "Screen" in c.check_name)
        assert screen_check.passed is False


class TestVerifyPositionChange:
    """Tests for position change verification."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        return emu

    @pytest.fixture
    def verifier(self, mock_emulator):
        """Create verifier."""
        return StrictVerifier(mock_emulator, VerificationLevel.STANDARD)

    def test_position_increase(self, verifier, mock_emulator):
        """Test position increased correctly."""
        # Setup before/after snapshots manually
        verifier._snapshot_before = {
            CriticalAddresses.LINK_X_LO: 0x00,
            CriticalAddresses.LINK_X_HI: 0x01,  # X = 256
            CriticalAddresses.LINK_Y_LO: 0x00,
            CriticalAddresses.LINK_Y_HI: 0x02,  # Y = 512
        }
        verifier._snapshot_after = {
            CriticalAddresses.LINK_X_LO: 0x20,
            CriticalAddresses.LINK_X_HI: 0x01,  # X = 288 (+32)
            CriticalAddresses.LINK_Y_LO: 0x00,
            CriticalAddresses.LINK_Y_HI: 0x02,  # Y = 512 (unchanged)
        }

        report = verifier.verify_position_change(expected_dx=32, expected_dy=0)

        assert report.passed is True
        assert "+32" in report.summary or "32" in report.summary

    def test_position_no_change_when_expected(self, verifier, mock_emulator):
        """Test position didn't change when movement expected."""
        verifier._snapshot_before = {
            CriticalAddresses.LINK_X_LO: 0x00,
            CriticalAddresses.LINK_X_HI: 0x01,
            CriticalAddresses.LINK_Y_LO: 0x00,
            CriticalAddresses.LINK_Y_HI: 0x02,
        }
        verifier._snapshot_after = {
            CriticalAddresses.LINK_X_LO: 0x00,  # Same!
            CriticalAddresses.LINK_X_HI: 0x01,
            CriticalAddresses.LINK_Y_LO: 0x00,
            CriticalAddresses.LINK_Y_HI: 0x02,
        }

        report = verifier.verify_position_change(expected_dx=32, expected_dy=0)

        # Should fail because we expected movement
        assert report.passed is False


class TestMustChangeVerification:
    """Tests for must_change and must_not_change checks."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        return emu

    @pytest.fixture
    def verifier(self, mock_emulator):
        """Create verifier."""
        return StrictVerifier(mock_emulator)

    def test_must_change_passes_when_changed(self, verifier):
        """Test must_change passes when value changes."""
        verifier._snapshot_before = {0x7E0022: 0x10}
        verifier._snapshot_after = {0x7E0022: 0x20}

        check = MemoryCheck(0x7E0022, "Link X", must_change=True)
        result = verifier._verify_check(check)

        assert result.passed is True

    def test_must_change_fails_when_unchanged(self, verifier):
        """Test must_change fails when value unchanged."""
        verifier._snapshot_before = {0x7E0022: 0x10}
        verifier._snapshot_after = {0x7E0022: 0x10}

        check = MemoryCheck(0x7E0022, "Link X", must_change=True)
        result = verifier._verify_check(check)

        assert result.passed is False

    def test_must_not_change_passes_when_unchanged(self, verifier):
        """Test must_not_change passes when unchanged."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x09}

        check = MemoryCheck(0x7E0010, "GameMode", must_not_change=True)
        result = verifier._verify_check(check)

        assert result.passed is True

    def test_must_not_change_fails_when_changed(self, verifier):
        """Test must_not_change fails when changed."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x07}

        check = MemoryCheck(0x7E0010, "GameMode", must_not_change=True)
        result = verifier._verify_check(check)

        assert result.passed is False


class TestBitmaskVerification:
    """Tests for bitmask-based verification."""

    @pytest.fixture
    def verifier(self):
        """Create verifier."""
        return StrictVerifier(Mock())

    def test_bitmask_check_bit7_set(self, verifier):
        """Test bitmask extracts bit 7."""
        verifier._snapshot_before = {0x7E001A: 0x8F}  # Bit 7 set
        verifier._snapshot_after = {0x7E001A: 0x8F}

        check = MemoryCheck(0x7E001A, "INIDISP bit 7", bitmask=0x80, expected_value=0x00)
        result = verifier._verify_check(check)

        # Expected 0x00, but got 0x80 (bit 7 set)
        assert result.passed is False

    def test_bitmask_check_bit7_clear(self, verifier):
        """Test bitmask with bit 7 clear."""
        verifier._snapshot_before = {0x7E001A: 0x0F}  # Bit 7 clear
        verifier._snapshot_after = {0x7E001A: 0x0F}

        check = MemoryCheck(0x7E001A, "INIDISP bit 7", bitmask=0x80, expected_value=0x00)
        result = verifier._verify_check(check)

        # Expected 0x00, got 0x00 (bit 7 clear)
        assert result.passed is True
