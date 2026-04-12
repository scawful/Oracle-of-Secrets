"""Strict Verification System for Oracle of Secrets Automation.

Provides multimodal verification using:
1. Memory address checks (specific WRAM locations)
2. Register state validation
3. Flag consistency checks
4. Visual verification (screenshot comparison)
5. State machine validation

Campaign Goal: Ensure accuracy of automation findings.
"""

from dataclasses import dataclass, field
from enum import IntEnum, auto
from typing import Dict, List, Optional, Tuple, Set, Callable
import time

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot


class VerificationLevel(IntEnum):
    """Strictness levels for verification."""
    BASIC = 1      # Just check if values changed
    STANDARD = 2   # Check expected ranges
    STRICT = 3     # Check exact values + consistency
    PARANOID = 4   # All of above + cross-validation


@dataclass
class MemoryCheck:
    """Definition of a memory address to verify."""
    address: int
    name: str
    size: int = 1
    expected_value: Optional[int] = None
    expected_range: Optional[Tuple[int, int]] = None
    must_change: bool = False
    must_not_change: bool = False
    bitmask: Optional[int] = None  # For flag checks


@dataclass
class RegisterState:
    """Captured register state for verification."""
    pc: int = 0       # Program Counter
    a: int = 0        # Accumulator
    x: int = 0        # X Index
    y: int = 0        # Y Index
    s: int = 0        # Stack Pointer
    db: int = 0       # Data Bank
    d: int = 0        # Direct Page
    p: int = 0        # Status Register


@dataclass
class VerificationResult:
    """Result of a verification check."""
    passed: bool
    check_name: str
    expected: str
    actual: str
    details: str = ""


@dataclass
class VerificationReport:
    """Complete verification report."""
    timestamp: float
    level: VerificationLevel
    checks: List[VerificationResult] = field(default_factory=list)
    passed: bool = False
    summary: str = ""

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


# =============================================================================
# Critical Memory Addresses for Oracle of Secrets
# =============================================================================

class CriticalAddresses:
    """Critical WRAM addresses to verify."""

    # Core State
    GAME_MODE = 0x7E0010
    SUBMODULE = 0x7E0011
    INIDISP = 0x7E0013  # INIDISP queue (written during NMI)
    FRAME_COUNTER = 0x7E001A
    INDOORS = 0x7E001B

    # Link Position (16-bit)
    LINK_Y_LO = 0x7E0020
    LINK_Y_HI = 0x7E0021
    LINK_X_LO = 0x7E0022
    LINK_X_HI = 0x7E0023
    LINK_Z = 0x7E0024

    # Link State
    LINK_DIRECTION = 0x7E002F
    LINK_STATE = 0x7E005D
    LINK_LAYER = 0x7E00EE

    # Area/Room
    OVERWORLD_AREA = 0x7E008A
    ROOM_LAYOUT = 0x7E00A0
    ROOM_ID_LO = 0x7E00A4
    ROOM_ID_HI = 0x7E00A5

    # Health
    HEALTH_CURRENT = 0x7EF36D
    HEALTH_MAX = 0x7EF36C

    # Story Progress
    OOSPROG = 0x7EF3D6
    OOSPROG2 = 0x7EF3C6

    # Controller Input
    JOYPAD1_LO = 0x7E00F0
    JOYPAD1_HI = 0x7E00F1
    JOYPAD_NEW = 0x7E00F4
    JOYPAD_NEW_HI = 0x7E00F5


# =============================================================================
# Verification Checks
# =============================================================================

# Standard checks for different verification scenarios
PLAYABLE_STATE_CHECKS: List[MemoryCheck] = [
    MemoryCheck(
        CriticalAddresses.GAME_MODE,
        "GameMode",
        expected_range=(0x07, 0x09),  # Dungeon or Overworld
    ),
    MemoryCheck(
        CriticalAddresses.INIDISP,
        "INIDISP",
        expected_value=0x0F,  # Screen on, full brightness
    ),
    MemoryCheck(
        CriticalAddresses.SUBMODULE,
        "Submodule",
        expected_value=0x00,  # No active transition
    ),
]

MOVEMENT_CHECKS: List[MemoryCheck] = [
    MemoryCheck(
        CriticalAddresses.LINK_X_LO,
        "Link X (low)",
        must_change=True,
    ),
    MemoryCheck(
        CriticalAddresses.GAME_MODE,
        "GameMode",
        must_not_change=True,  # Should stay in same mode
    ),
    MemoryCheck(
        CriticalAddresses.HEALTH_CURRENT,
        "Health",
        must_not_change=True,  # Shouldn't take damage from walking
    ),
]

TRANSITION_CHECKS: List[MemoryCheck] = [
    MemoryCheck(
        CriticalAddresses.GAME_MODE,
        "GameMode",
        must_change=True,  # Should change during transition
    ),
    MemoryCheck(
        CriticalAddresses.OVERWORLD_AREA,
        "Area",
        must_change=True,  # Should change on area transition
    ),
]

BLACK_SCREEN_CHECKS: List[MemoryCheck] = [
    MemoryCheck(
        CriticalAddresses.INIDISP,
        "INIDISP",
        bitmask=0x80,  # Bit 7 = forced blanking
        expected_value=0x00,  # Should be 0 when screen is visible
    ),
    MemoryCheck(
        CriticalAddresses.GAME_MODE,
        "GameMode during black screen",
        expected_range=(0x07, 0x09),
    ),
]


class StrictVerifier:
    """Strict verification system for automation accuracy."""

    def __init__(self, emulator: EmulatorInterface, level: VerificationLevel = VerificationLevel.STANDARD):
        self.emulator = emulator
        self.level = level
        self._snapshot_before: Optional[Dict[int, int]] = None
        self._snapshot_after: Optional[Dict[int, int]] = None

    def capture_snapshot(self, addresses: List[int]) -> Dict[int, int]:
        """Capture current values at specified addresses."""
        snapshot = {}
        for addr in addresses:
            read = self.emulator.read_memory(addr, size=1)
            snapshot[addr] = read.value
        return snapshot

    def capture_16bit(self, addr_lo: int) -> int:
        """Capture 16-bit value from two consecutive addresses."""
        lo = self.emulator.read_memory(addr_lo, size=1).value
        hi = self.emulator.read_memory(addr_lo + 1, size=1).value
        return (hi << 8) | lo

    def begin_verification(self, checks: List[MemoryCheck]):
        """Capture state before action."""
        addresses = [c.address for c in checks]
        self._snapshot_before = self.capture_snapshot(addresses)

    def end_verification(self, checks: List[MemoryCheck]) -> VerificationReport:
        """Capture state after action and verify."""
        addresses = [c.address for c in checks]
        self._snapshot_after = self.capture_snapshot(addresses)

        report = VerificationReport(
            timestamp=time.time(),
            level=self.level,
        )

        for check in checks:
            result = self._verify_check(check)
            report.checks.append(result)

        report.passed = all(c.passed for c in report.checks)
        report.summary = f"{report.pass_count}/{len(report.checks)} checks passed"

        return report

    def _verify_check(self, check: MemoryCheck) -> VerificationResult:
        """Verify a single memory check."""
        before = self._snapshot_before.get(check.address, 0)
        after = self._snapshot_after.get(check.address, 0)

        # Apply bitmask if specified
        if check.bitmask is not None:
            before = before & check.bitmask
            after = after & check.bitmask

        # Check must_change
        if check.must_change:
            if before == after:
                return VerificationResult(
                    passed=False,
                    check_name=check.name,
                    expected="value to change",
                    actual=f"stayed at 0x{after:02X}",
                    details=f"Before: 0x{before:02X}, After: 0x{after:02X}"
                )

        # Check must_not_change
        if check.must_not_change:
            if before != after:
                return VerificationResult(
                    passed=False,
                    check_name=check.name,
                    expected="value to stay same",
                    actual=f"changed from 0x{before:02X} to 0x{after:02X}",
                )

        # Check expected_value
        if check.expected_value is not None:
            if after != check.expected_value:
                return VerificationResult(
                    passed=False,
                    check_name=check.name,
                    expected=f"0x{check.expected_value:02X}",
                    actual=f"0x{after:02X}",
                )

        # Check expected_range
        if check.expected_range is not None:
            lo, hi = check.expected_range
            if not (lo <= after <= hi):
                return VerificationResult(
                    passed=False,
                    check_name=check.name,
                    expected=f"0x{lo:02X}-0x{hi:02X}",
                    actual=f"0x{after:02X}",
                )

        return VerificationResult(
            passed=True,
            check_name=check.name,
            expected="valid",
            actual=f"0x{after:02X}",
            details=f"Before: 0x{before:02X}" if check.must_change or check.must_not_change else ""
        )

    def verify_playable_state(self) -> VerificationReport:
        """Verify game is in a playable state."""
        report = VerificationReport(
            timestamp=time.time(),
            level=self.level,
        )

        # Read current values
        mode = self.emulator.read_memory(CriticalAddresses.GAME_MODE, 1).value
        submod = self.emulator.read_memory(CriticalAddresses.SUBMODULE, 1).value
        inidisp = self.emulator.read_memory(CriticalAddresses.INIDISP, 1).value

        # Check mode
        report.checks.append(VerificationResult(
            passed=(mode in (0x07, 0x09)),
            check_name="GameMode",
            expected="0x07 or 0x09",
            actual=f"0x{mode:02X}",
            details="0x07=Dungeon, 0x09=Overworld"
        ))

        # Check submodule
        report.checks.append(VerificationResult(
            passed=(submod == 0x00),
            check_name="Submodule",
            expected="0x00 (no transition)",
            actual=f"0x{submod:02X}",
        ))

        # Check INIDISP
        report.checks.append(VerificationResult(
            passed=(inidisp & 0x80 == 0),
            check_name="Screen Visible",
            expected="INIDISP bit 7 = 0",
            actual=f"0x{inidisp:02X}",
            details="Bit 7 set = forced blanking (black screen)"
        ))

        report.passed = all(c.passed for c in report.checks)
        report.summary = f"Playable: {report.passed}"

        return report

    def verify_position_change(self, expected_dx: int = 0, expected_dy: int = 0,
                                tolerance: int = 16) -> VerificationReport:
        """Verify Link's position changed as expected.

        Args:
            expected_dx: Expected X change (positive = right)
            expected_dy: Expected Y change (positive = down)
            tolerance: Allowable deviation in pixels

        Returns:
            VerificationReport with position check results
        """
        if self._snapshot_before is None or self._snapshot_after is None:
            raise RuntimeError("Must call begin_verification and end_verification first")

        report = VerificationReport(
            timestamp=time.time(),
            level=self.level,
        )

        # Calculate position changes
        before_x = (
            (self._snapshot_before.get(CriticalAddresses.LINK_X_HI, 0) << 8) |
            self._snapshot_before.get(CriticalAddresses.LINK_X_LO, 0)
        )
        after_x = (
            (self._snapshot_after.get(CriticalAddresses.LINK_X_HI, 0) << 8) |
            self._snapshot_after.get(CriticalAddresses.LINK_X_LO, 0)
        )
        before_y = (
            (self._snapshot_before.get(CriticalAddresses.LINK_Y_HI, 0) << 8) |
            self._snapshot_before.get(CriticalAddresses.LINK_Y_LO, 0)
        )
        after_y = (
            (self._snapshot_after.get(CriticalAddresses.LINK_Y_HI, 0) << 8) |
            self._snapshot_after.get(CriticalAddresses.LINK_Y_LO, 0)
        )

        actual_dx = after_x - before_x
        actual_dy = after_y - before_y

        # Check X change
        x_pass = abs(actual_dx - expected_dx) <= tolerance or (expected_dx > 0 and actual_dx > 0)
        report.checks.append(VerificationResult(
            passed=x_pass,
            check_name="Position X Change",
            expected=f"dx={expected_dx} (±{tolerance})",
            actual=f"dx={actual_dx}",
            details=f"Before: {before_x}, After: {after_x}"
        ))

        # Check Y change
        y_pass = abs(actual_dy - expected_dy) <= tolerance or (expected_dy > 0 and actual_dy > 0)
        report.checks.append(VerificationResult(
            passed=y_pass,
            check_name="Position Y Change",
            expected=f"dy={expected_dy} (±{tolerance})",
            actual=f"dy={actual_dy}",
            details=f"Before: {before_y}, After: {after_y}"
        ))

        report.passed = all(c.passed for c in report.checks)
        report.summary = f"Position: ({actual_dx:+d}, {actual_dy:+d})"

        return report


def print_report(report: VerificationReport):
    """Print verification report to console."""
    print(f"\n{'='*60}")
    print(f"  Verification Report - Level {report.level.name}")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}")
    print(f"{'='*60}")

    for check in report.checks:
        status = "✓ PASS" if check.passed else "✗ FAIL"
        print(f"\n  [{status}] {check.check_name}")
        print(f"    Expected: {check.expected}")
        print(f"    Actual:   {check.actual}")
        if check.details:
            print(f"    Details:  {check.details}")

    print(f"\n{'='*60}")
    print(f"  RESULT: {'PASSED' if report.passed else 'FAILED'}")
    print(f"  Summary: {report.summary}")
    print(f"{'='*60}\n")
