"""Extended tests for strict verification system.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- Goal C milestone: Verification accuracy testing

These tests cover edge cases and complete workflows
for the strict verification system.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, PropertyMock
from dataclasses import asdict

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.verification import (
    VerificationLevel, MemoryCheck, RegisterState, VerificationResult,
    VerificationReport, CriticalAddresses, StrictVerifier,
    PLAYABLE_STATE_CHECKS, MOVEMENT_CHECKS, TRANSITION_CHECKS,
    BLACK_SCREEN_CHECKS
)


class TestVerificationLevelEnum:
    """Test VerificationLevel enum values."""

    def test_basic_value(self):
        """Test BASIC has lowest value."""
        assert VerificationLevel.BASIC.value == 1

    def test_standard_value(self):
        """Test STANDARD value."""
        assert VerificationLevel.STANDARD.value == 2

    def test_strict_value(self):
        """Test STRICT value."""
        assert VerificationLevel.STRICT.value == 3

    def test_paranoid_value(self):
        """Test PARANOID has highest value."""
        assert VerificationLevel.PARANOID.value == 4

    def test_levels_ordered(self):
        """Test levels are in ascending order."""
        assert (VerificationLevel.BASIC < VerificationLevel.STANDARD <
                VerificationLevel.STRICT < VerificationLevel.PARANOID)

    def test_level_comparison(self):
        """Test levels can be compared."""
        assert VerificationLevel.PARANOID > VerificationLevel.BASIC


class TestMemoryCheckDataclass:
    """Test MemoryCheck dataclass."""

    def test_basic_creation(self):
        """Test basic MemoryCheck creation."""
        check = MemoryCheck(address=0x7E0010, name="GameMode")
        assert check.address == 0x7E0010
        assert check.name == "GameMode"

    def test_default_values(self):
        """Test MemoryCheck default values."""
        check = MemoryCheck(address=0x7E0010, name="Test")
        assert check.size == 1
        assert check.expected_value is None
        assert check.expected_range is None
        assert check.must_change is False
        assert check.must_not_change is False
        assert check.bitmask is None

    def test_with_expected_value(self):
        """Test MemoryCheck with expected value."""
        check = MemoryCheck(
            address=0x7E0010,
            name="Mode",
            expected_value=0x09
        )
        assert check.expected_value == 0x09

    def test_with_expected_range(self):
        """Test MemoryCheck with expected range."""
        check = MemoryCheck(
            address=0x7E0010,
            name="Mode",
            expected_range=(0x07, 0x09)
        )
        assert check.expected_range == (0x07, 0x09)

    def test_with_must_change(self):
        """Test MemoryCheck with must_change flag."""
        check = MemoryCheck(
            address=0x7E0020,
            name="Link X",
            must_change=True
        )
        assert check.must_change is True

    def test_with_bitmask(self):
        """Test MemoryCheck with bitmask."""
        check = MemoryCheck(
            address=0x7E0013,
            name="INIDISP",
            bitmask=0x80
        )
        assert check.bitmask == 0x80

    def test_with_all_options(self):
        """Test MemoryCheck with all options."""
        check = MemoryCheck(
            address=0x7E0010,
            name="Full",
            size=2,
            expected_value=0x09,
            expected_range=(0x07, 0x0A),
            must_change=False,
            must_not_change=True,
            bitmask=0xFF
        )
        assert check.size == 2
        assert check.must_not_change is True


class TestRegisterStateDataclass:
    """Test RegisterState dataclass."""

    def test_default_values(self):
        """Test RegisterState default values are zero."""
        state = RegisterState()
        assert state.pc == 0
        assert state.a == 0
        assert state.x == 0
        assert state.y == 0
        assert state.s == 0
        assert state.db == 0
        assert state.d == 0
        assert state.p == 0

    def test_with_values(self):
        """Test RegisterState with specific values."""
        state = RegisterState(
            pc=0x8000,
            a=0x0042,
            x=0x0010,
            y=0x0020,
            s=0x01FF,
            db=0x7E,
            d=0x0000,
            p=0x30
        )
        assert state.pc == 0x8000
        assert state.a == 0x0042
        assert state.db == 0x7E


class TestVerificationResultDataclass:
    """Test VerificationResult dataclass."""

    def test_pass_result(self):
        """Test passing verification result."""
        result = VerificationResult(
            passed=True,
            check_name="GameMode",
            expected="0x09",
            actual="0x09"
        )
        assert result.passed is True
        assert result.check_name == "GameMode"

    def test_fail_result(self):
        """Test failing verification result."""
        result = VerificationResult(
            passed=False,
            check_name="INIDISP",
            expected="0x0F",
            actual="0x80",
            details="Screen is blanked"
        )
        assert result.passed is False
        assert result.details == "Screen is blanked"

    def test_default_details(self):
        """Test default empty details."""
        result = VerificationResult(
            passed=True,
            check_name="Test",
            expected="X",
            actual="X"
        )
        assert result.details == ""


class TestVerificationReportDataclass:
    """Test VerificationReport dataclass."""

    def test_empty_report(self):
        """Test empty verification report."""
        report = VerificationReport(
            timestamp=1.0,
            level=VerificationLevel.STANDARD
        )
        assert report.timestamp == 1.0
        assert report.level == VerificationLevel.STANDARD
        assert report.checks == []
        assert report.passed is False

    def test_pass_count_zero(self):
        """Test pass_count with no checks."""
        report = VerificationReport(timestamp=1.0, level=VerificationLevel.BASIC)
        assert report.pass_count == 0

    def test_pass_count_with_checks(self):
        """Test pass_count with mixed results."""
        report = VerificationReport(timestamp=1.0, level=VerificationLevel.BASIC)
        report.checks = [
            VerificationResult(True, "A", "X", "X"),
            VerificationResult(True, "B", "Y", "Y"),
            VerificationResult(False, "C", "Z", "W"),
        ]
        assert report.pass_count == 2
        assert report.fail_count == 1

    def test_all_pass(self):
        """Test report with all checks passing."""
        report = VerificationReport(timestamp=1.0, level=VerificationLevel.STRICT)
        report.checks = [
            VerificationResult(True, "A", "X", "X"),
            VerificationResult(True, "B", "Y", "Y"),
        ]
        report.passed = True
        assert report.pass_count == 2
        assert report.fail_count == 0

    def test_all_fail(self):
        """Test report with all checks failing."""
        report = VerificationReport(timestamp=1.0, level=VerificationLevel.PARANOID)
        report.checks = [
            VerificationResult(False, "A", "X", "Y"),
            VerificationResult(False, "B", "Z", "W"),
        ]
        assert report.pass_count == 0
        assert report.fail_count == 2


class TestCriticalAddressesConstants:
    """Test CriticalAddresses constants."""

    def test_game_mode_in_wram(self):
        """Test GAME_MODE address is in WRAM."""
        assert CriticalAddresses.GAME_MODE >= 0x7E0000
        assert CriticalAddresses.GAME_MODE < 0x800000

    def test_link_position_addresses_consecutive(self):
        """Test Link position addresses are consecutive."""
        assert CriticalAddresses.LINK_Y_HI == CriticalAddresses.LINK_Y_LO + 1
        assert CriticalAddresses.LINK_X_HI == CriticalAddresses.LINK_X_LO + 1

    def test_health_addresses_consecutive(self):
        """Test Health addresses are near each other."""
        diff = abs(CriticalAddresses.HEALTH_CURRENT - CriticalAddresses.HEALTH_MAX)
        assert diff < 16

    def test_all_addresses_are_integers(self):
        """Test all address constants are integers."""
        addresses = [
            CriticalAddresses.GAME_MODE,
            CriticalAddresses.SUBMODULE,
            CriticalAddresses.INIDISP,
            CriticalAddresses.LINK_X_LO,
            CriticalAddresses.LINK_Y_LO,
            CriticalAddresses.HEALTH_CURRENT,
            CriticalAddresses.OOSPROG,
        ]
        for addr in addresses:
            assert isinstance(addr, int)

    def test_story_progress_in_sram(self):
        """Test story progress addresses are in SRAM region."""
        # Oracle uses $7EF3xx for SRAM mirrors
        assert CriticalAddresses.OOSPROG >= 0x7EF000


class TestPredefinedCheckLists:
    """Test predefined check lists."""

    def test_playable_state_checks_not_empty(self):
        """Test PLAYABLE_STATE_CHECKS has entries."""
        assert len(PLAYABLE_STATE_CHECKS) > 0

    def test_playable_state_checks_game_mode(self):
        """Test playable checks include game mode."""
        names = [c.name for c in PLAYABLE_STATE_CHECKS]
        assert "GameMode" in names

    def test_movement_checks_must_change(self):
        """Test movement checks have must_change flag."""
        must_change_checks = [c for c in MOVEMENT_CHECKS if c.must_change]
        assert len(must_change_checks) > 0

    def test_movement_checks_must_not_change(self):
        """Test movement checks have must_not_change flag."""
        must_not_change = [c for c in MOVEMENT_CHECKS if c.must_not_change]
        assert len(must_not_change) > 0

    def test_transition_checks_must_change(self):
        """Test transition checks expect values to change."""
        must_change = [c for c in TRANSITION_CHECKS if c.must_change]
        assert len(must_change) > 0

    def test_black_screen_checks_bitmask(self):
        """Test black screen checks use bitmask."""
        bitmask_checks = [c for c in BLACK_SCREEN_CHECKS if c.bitmask is not None]
        assert len(bitmask_checks) > 0


class TestStrictVerifierCreation:
    """Test StrictVerifier creation."""

    def test_creation_with_emulator(self):
        """Test verifier creation with mock emulator."""
        mock_emu = Mock()
        verifier = StrictVerifier(mock_emu)
        assert verifier.emulator is mock_emu

    def test_default_level(self):
        """Test default verification level is STANDARD."""
        mock_emu = Mock()
        verifier = StrictVerifier(mock_emu)
        assert verifier.level == VerificationLevel.STANDARD

    def test_custom_level(self):
        """Test verifier with custom level."""
        mock_emu = Mock()
        verifier = StrictVerifier(mock_emu, level=VerificationLevel.PARANOID)
        assert verifier.level == VerificationLevel.PARANOID

    def test_initial_snapshot_state(self):
        """Test initial snapshot state is None."""
        mock_emu = Mock()
        verifier = StrictVerifier(mock_emu)
        assert verifier._snapshot_before is None
        assert verifier._snapshot_after is None


class TestStrictVerifierCaptureSnapshot:
    """Test StrictVerifier snapshot capture."""

    @pytest.fixture
    def mock_emulator(self):
        """Create mock emulator."""
        emu = Mock()
        # Return mock memory read result
        read_result = Mock()
        read_result.value = 0x42
        emu.read_memory.return_value = read_result
        return emu

    def test_capture_single_address(self, mock_emulator):
        """Test capturing single address."""
        verifier = StrictVerifier(mock_emulator)
        snapshot = verifier.capture_snapshot([0x7E0010])

        assert 0x7E0010 in snapshot
        mock_emulator.read_memory.assert_called()

    def test_capture_multiple_addresses(self, mock_emulator):
        """Test capturing multiple addresses."""
        verifier = StrictVerifier(mock_emulator)
        addresses = [0x7E0010, 0x7E0011, 0x7E0020]
        snapshot = verifier.capture_snapshot(addresses)

        assert len(snapshot) == 3
        for addr in addresses:
            assert addr in snapshot


class TestStrictVerifierBeginEnd:
    """Test StrictVerifier begin/end verification."""

    @pytest.fixture
    def verifier_with_mock(self):
        """Create verifier with mock emulator."""
        emu = Mock()
        read_result = Mock()
        read_result.value = 0x09
        emu.read_memory.return_value = read_result
        return StrictVerifier(emu)

    def test_begin_verification(self, verifier_with_mock):
        """Test begin_verification captures state."""
        checks = [MemoryCheck(0x7E0010, "Mode")]
        verifier_with_mock.begin_verification(checks)

        assert verifier_with_mock._snapshot_before is not None
        assert 0x7E0010 in verifier_with_mock._snapshot_before

    def test_end_verification_returns_report(self, verifier_with_mock):
        """Test end_verification returns report."""
        checks = [MemoryCheck(0x7E0010, "Mode", expected_value=0x09)]
        verifier_with_mock.begin_verification(checks)
        report = verifier_with_mock.end_verification(checks)

        assert isinstance(report, VerificationReport)
        assert len(report.checks) == 1


class TestStrictVerifierVerifyPlayableState:
    """Test verify_playable_state method."""

    def test_playable_state_pass(self):
        """Test playable state passes with correct values."""
        emu = Mock()

        def mock_read(addr, size):
            result = Mock()
            if addr == CriticalAddresses.GAME_MODE:
                result.value = 0x09  # Overworld
            elif addr == CriticalAddresses.SUBMODULE:
                result.value = 0x00  # No transition
            elif addr == CriticalAddresses.INIDISP:
                result.value = 0x0F  # Screen on
            else:
                result.value = 0x00
            return result

        emu.read_memory = mock_read
        verifier = StrictVerifier(emu)
        report = verifier.verify_playable_state()

        assert report.passed is True

    def test_playable_state_fail_mode(self):
        """Test playable state fails with wrong mode."""
        emu = Mock()

        def mock_read(addr, size):
            result = Mock()
            if addr == CriticalAddresses.GAME_MODE:
                result.value = 0x01  # Title screen
            elif addr == CriticalAddresses.SUBMODULE:
                result.value = 0x00
            elif addr == CriticalAddresses.INIDISP:
                result.value = 0x0F
            else:
                result.value = 0x00
            return result

        emu.read_memory = mock_read
        verifier = StrictVerifier(emu)
        report = verifier.verify_playable_state()

        assert report.passed is False

    def test_playable_state_fail_black_screen(self):
        """Test playable state fails on black screen."""
        emu = Mock()

        def mock_read(addr, size):
            result = Mock()
            if addr == CriticalAddresses.GAME_MODE:
                result.value = 0x09
            elif addr == CriticalAddresses.SUBMODULE:
                result.value = 0x00
            elif addr == CriticalAddresses.INIDISP:
                result.value = 0x80  # Forced blanking
            else:
                result.value = 0x00
            return result

        emu.read_memory = mock_read
        verifier = StrictVerifier(emu)
        report = verifier.verify_playable_state()

        assert report.passed is False


class TestVerificationCheckLogic:
    """Test individual check verification logic."""

    @pytest.fixture
    def verifier(self):
        """Create verifier with configurable mock."""
        emu = Mock()
        return StrictVerifier(emu)

    def test_expected_value_pass(self, verifier):
        """Test expected_value check passes."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x09}
        check = MemoryCheck(0x7E0010, "Mode", expected_value=0x09)

        result = verifier._verify_check(check)
        assert result.passed is True

    def test_expected_value_fail(self, verifier):
        """Test expected_value check fails."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x01}
        check = MemoryCheck(0x7E0010, "Mode", expected_value=0x09)

        result = verifier._verify_check(check)
        assert result.passed is False

    def test_expected_range_pass(self, verifier):
        """Test expected_range check passes."""
        verifier._snapshot_before = {0x7E0010: 0x00}
        verifier._snapshot_after = {0x7E0010: 0x08}
        check = MemoryCheck(0x7E0010, "Mode", expected_range=(0x07, 0x09))

        result = verifier._verify_check(check)
        assert result.passed is True

    def test_expected_range_fail_below(self, verifier):
        """Test expected_range check fails below range."""
        verifier._snapshot_before = {0x7E0010: 0x00}
        verifier._snapshot_after = {0x7E0010: 0x05}
        check = MemoryCheck(0x7E0010, "Mode", expected_range=(0x07, 0x09))

        result = verifier._verify_check(check)
        assert result.passed is False

    def test_expected_range_fail_above(self, verifier):
        """Test expected_range check fails above range."""
        verifier._snapshot_before = {0x7E0010: 0x00}
        verifier._snapshot_after = {0x7E0010: 0x0F}
        check = MemoryCheck(0x7E0010, "Mode", expected_range=(0x07, 0x09))

        result = verifier._verify_check(check)
        assert result.passed is False

    def test_must_change_pass(self, verifier):
        """Test must_change passes when value changes."""
        verifier._snapshot_before = {0x7E0020: 0x100}
        verifier._snapshot_after = {0x7E0020: 0x110}
        check = MemoryCheck(0x7E0020, "Link X", must_change=True)

        result = verifier._verify_check(check)
        assert result.passed is True

    def test_must_change_fail(self, verifier):
        """Test must_change fails when value unchanged."""
        verifier._snapshot_before = {0x7E0020: 0x100}
        verifier._snapshot_after = {0x7E0020: 0x100}
        check = MemoryCheck(0x7E0020, "Link X", must_change=True)

        result = verifier._verify_check(check)
        assert result.passed is False

    def test_must_not_change_pass(self, verifier):
        """Test must_not_change passes when value unchanged."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x09}
        check = MemoryCheck(0x7E0010, "Mode", must_not_change=True)

        result = verifier._verify_check(check)
        assert result.passed is True

    def test_must_not_change_fail(self, verifier):
        """Test must_not_change fails when value changes."""
        verifier._snapshot_before = {0x7E0010: 0x09}
        verifier._snapshot_after = {0x7E0010: 0x07}
        check = MemoryCheck(0x7E0010, "Mode", must_not_change=True)

        result = verifier._verify_check(check)
        assert result.passed is False

    def test_bitmask_applied(self, verifier):
        """Test bitmask is applied to values."""
        verifier._snapshot_before = {0x7E0013: 0x0F}
        verifier._snapshot_after = {0x7E0013: 0x8F}
        check = MemoryCheck(0x7E0013, "INIDISPQ", bitmask=0x80, expected_value=0x80)

        result = verifier._verify_check(check)
        # After applying mask: 0x8F & 0x80 = 0x80
        assert result.passed is True

    def test_bitmask_check_zero(self, verifier):
        """Test bitmask check for zero."""
        verifier._snapshot_before = {0x7E0013: 0x0F}
        verifier._snapshot_after = {0x7E0013: 0x0F}
        check = MemoryCheck(0x7E0013, "INIDISPQ", bitmask=0x80, expected_value=0x00)

        result = verifier._verify_check(check)
        # After applying mask: 0x0F & 0x80 = 0x00
        assert result.passed is True


class TestVerificationWorkflow:
    """Test complete verification workflow."""

    def test_full_workflow(self):
        """Test complete begin->action->end workflow."""
        emu = Mock()
        call_count = [0]

        def mock_read(addr, size):
            call_count[0] += 1
            result = Mock()
            # First calls (before) return one set of values
            # Later calls (after) return different values
            if call_count[0] <= 2:  # Before snapshot
                result.value = 0x100
            else:  # After snapshot
                result.value = 0x110
            return result

        emu.read_memory = mock_read
        verifier = StrictVerifier(emu)

        checks = [
            MemoryCheck(0x7E0020, "Link X", must_change=True),
            MemoryCheck(0x7E0010, "Mode"),
        ]

        verifier.begin_verification(checks)
        # ... action would happen here ...
        report = verifier.end_verification(checks)

        assert isinstance(report, VerificationReport)
        assert report.timestamp > 0
        assert len(report.checks) == 2
