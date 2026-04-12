"""Progress flag and player state validation for Oracle of Secrets.

This module provides validation of game progression, story flags,
inventory state, and save state verification.

Campaign Goals Supported:
- E.1: State verification and regression testing
- E.2: Save state library integration
- E.3: Progress flag tracking

Usage:
    from scripts.campaign.progress_validator import ProgressValidator

    validator = ProgressValidator(emulator)
    report = validator.validate_progression()
    print(report.summary)
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import IntEnum, IntFlag, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot
from .verification import CriticalAddresses


# =============================================================================
# Story Flag Definitions
# =============================================================================

class StoryFlag(IntFlag):
    """Main story progression flags (OOSPROG at $7EF3D6).

    Flags are bit positions in the OOSPROG byte.
    """
    INTRO_COMPLETE = 0x01      # !Story_IntroComplete
    LOOM_BEACH = 0x02          # Arrived at Loom Beach
    KYDROG_COMPLETE = 0x04     # Completed Kydrog quest
    FARORE_RESCUED = 0x08      # Rescued Farore
    HALL_OF_SECRETS = 0x10     # Entered Hall of Secrets
    STORY_FLAG_5 = 0x20        # Reserved
    STORY_FLAG_6 = 0x40        # Reserved
    STORY_FLAG_7 = 0x80        # Reserved


class GameStateValue(IntEnum):
    """GameState byte values ($7EF3C5)."""
    START = 0         # New game
    LOOM_BEACH = 1    # After intro, at Loom Beach
    KYDROG_DONE = 2   # Kydrog complete
    FARORE_FREE = 3   # Farore rescued


# =============================================================================
# SRAM Addresses for Progress
# =============================================================================

class ProgressAddresses:
    """SRAM addresses for progress tracking."""

    # Story Progression
    GAME_STATE = 0x7EF3C5       # Main game state (0-3+)
    OOSPROG = 0x7EF3D6         # Main story flags
    OOSPROG2 = 0x7EF3C6        # Secondary story flags
    SIDE_QUEST_1 = 0x7EF3D7    # Side quest progress
    SIDE_QUEST_2 = 0x7EF3D8    # Side quest progress 2

    # Player Stats (SRAM)
    HEALTH_MAX = 0x7EF36C      # Max health (hearts * 8)
    HEALTH_CURRENT = 0x7EF36D  # Current health
    RUPEES_LO = 0x7EF360       # Rupees low byte
    RUPEES_HI = 0x7EF361       # Rupees high byte
    MAGIC_METER = 0x7EF36E     # Magic meter
    MAGIC_MAX = 0x7EF36F       # Max magic

    # Dungeon Completion
    CRYSTALS = 0x7EF37A        # Crystals/dungeon completion bitfield

    # Key Items (subset)
    ITEM_SWORD = 0x7EF359      # Sword level
    ITEM_SHIELD = 0x7EF35A     # Shield level
    ITEM_ARMOR = 0x7EF35B      # Armor/tunic level

    # Follower System
    FOLLOWER_ID = 0x7EF3CC     # Current follower
    FOLLOWER_STATE = 0x7EF3CD  # Follower state


@dataclass
class ProgressSnapshot:
    """Snapshot of player progress at a point in time."""
    timestamp: float

    # Story state
    game_state: int
    story_flags: int
    story_flags_2: int
    side_quest_1: int
    side_quest_2: int

    # Stats
    health: int
    max_health: int
    rupees: int
    magic: int
    max_magic: int

    # Equipment
    sword_level: int
    shield_level: int
    armor_level: int

    # Dungeon progress
    crystals: int

    # Follower
    follower_id: int
    follower_state: int

    @property
    def hearts(self) -> float:
        """Current health in hearts."""
        return self.health / 8.0

    @property
    def max_hearts(self) -> float:
        """Max health in hearts."""
        return self.max_health / 8.0

    @property
    def health_percent(self) -> float:
        """Health as percentage (0.0-1.0)."""
        if self.max_health == 0:
            return 1.0
        return self.health / self.max_health

    @property
    def has_flag(self) -> callable:
        """Check if a story flag is set."""
        def check(flag: StoryFlag) -> bool:
            return bool(self.story_flags & flag)
        return check

    @property
    def dungeon_count(self) -> int:
        """Number of completed dungeons (based on crystals)."""
        return bin(self.crystals).count('1')

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            'game_state': self.game_state,
            'story_flags': self.story_flags,
            'story_flags_2': self.story_flags_2,
            'health': self.health,
            'max_health': self.max_health,
            'rupees': self.rupees,
            'sword_level': self.sword_level,
            'crystals': self.crystals,
            'dungeon_count': self.dungeon_count,
        }


@dataclass
class ValidationResult:
    """Result of a progress validation check."""
    name: str
    passed: bool
    expected: str
    actual: str
    details: str = ""


@dataclass
class ProgressReport:
    """Complete progress validation report."""
    timestamp: float
    snapshot: ProgressSnapshot
    checks: List[ValidationResult] = field(default_factory=list)
    passed: bool = False
    summary: str = ""

    @property
    def pass_count(self) -> int:
        return sum(1 for c in self.checks if c.passed)

    @property
    def fail_count(self) -> int:
        return sum(1 for c in self.checks if not c.passed)


class ProgressValidator:
    """Validates player progress and state.

    This validator checks:
    - Story progression flags consistency
    - Player stat validity (health, rupees, etc.)
    - Equipment state
    - Dungeon completion state
    - Save state integrity
    """

    def __init__(self, emulator: EmulatorInterface):
        """Initialize with emulator interface.

        Args:
            emulator: Connected emulator instance
        """
        self.emulator = emulator
        self._last_snapshot: Optional[ProgressSnapshot] = None

    def capture_progress(self) -> ProgressSnapshot:
        """Capture current progress state from emulator.

        Returns:
            ProgressSnapshot with all progress values
        """
        import time

        def read(addr: int) -> int:
            return self.emulator.read_memory(addr, size=1).value

        def read16(addr: int) -> int:
            return self.emulator.read_memory(addr, size=2).value

        snapshot = ProgressSnapshot(
            timestamp=time.time(),
            game_state=read(ProgressAddresses.GAME_STATE),
            story_flags=read(ProgressAddresses.OOSPROG),
            story_flags_2=read(ProgressAddresses.OOSPROG2),
            side_quest_1=read(ProgressAddresses.SIDE_QUEST_1),
            side_quest_2=read(ProgressAddresses.SIDE_QUEST_2),
            health=read(ProgressAddresses.HEALTH_CURRENT),
            max_health=read(ProgressAddresses.HEALTH_MAX),
            rupees=read16(ProgressAddresses.RUPEES_LO),
            magic=read(ProgressAddresses.MAGIC_METER),
            max_magic=read(ProgressAddresses.MAGIC_MAX),
            sword_level=read(ProgressAddresses.ITEM_SWORD),
            shield_level=read(ProgressAddresses.ITEM_SHIELD),
            armor_level=read(ProgressAddresses.ITEM_ARMOR),
            crystals=read(ProgressAddresses.CRYSTALS),
            follower_id=read(ProgressAddresses.FOLLOWER_ID),
            follower_state=read(ProgressAddresses.FOLLOWER_STATE),
        )

        self._last_snapshot = snapshot
        return snapshot

    def validate_progression(self) -> ProgressReport:
        """Validate current progression state.

        Returns:
            ProgressReport with validation results
        """
        import time

        snapshot = self.capture_progress()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snapshot,
        )

        # Validate stats are in valid ranges
        report.checks.append(self._check_health_valid(snapshot))
        report.checks.append(self._check_rupees_valid(snapshot))
        report.checks.append(self._check_equipment_valid(snapshot))

        # Validate story flag consistency
        report.checks.extend(self._check_story_consistency(snapshot))

        # Validate dungeon progress
        report.checks.append(self._check_dungeon_progress(snapshot))

        report.passed = all(c.passed for c in report.checks)
        report.summary = self._generate_summary(report)

        return report

    def validate_state_library_entry(
        self,
        entry_id: str,
        library_path: Optional[Path] = None
    ) -> ProgressReport:
        """Validate current state matches a library entry.

        Args:
            entry_id: State library entry ID (e.g., 'baseline_1')
            library_path: Path to save_state_library.json

        Returns:
            ProgressReport comparing actual vs expected
        """
        import time

        if library_path is None:
            library_path = Path(__file__).parent.parent.parent / "Docs/Debugging/Testing/save_state_library.json"

        snapshot = self.capture_progress()
        report = ProgressReport(
            timestamp=time.time(),
            snapshot=snapshot,
        )

        # Load library entry
        try:
            with open(library_path) as f:
                library = json.load(f)

            entry = None
            for e in library.get('entries', []):
                if e.get('id') == entry_id:
                    entry = e
                    break

            if entry is None:
                report.checks.append(ValidationResult(
                    name="Library Entry",
                    passed=False,
                    expected=entry_id,
                    actual="Not found",
                    details=f"Entry '{entry_id}' not in library"
                ))
                report.passed = False
                report.summary = f"Entry '{entry_id}' not found"
                return report

            # Validate game state matches entry metadata
            game_state = entry.get('gameState', {})

            if 'mode' in game_state:
                expected_mode = int(game_state['mode'], 16) if isinstance(game_state['mode'], str) else game_state['mode']
                actual_mode = self.emulator.read_memory(CriticalAddresses.GAME_MODE, 1).value
                report.checks.append(ValidationResult(
                    name="GameMode",
                    passed=(actual_mode == expected_mode),
                    expected=f"0x{expected_mode:02X}",
                    actual=f"0x{actual_mode:02X}",
                ))

            if 'indoors' in game_state:
                expected_indoors = game_state['indoors']
                actual_indoors = self.emulator.read_memory(CriticalAddresses.INDOORS, 1).value != 0
                report.checks.append(ValidationResult(
                    name="Indoors",
                    passed=(actual_indoors == expected_indoors),
                    expected=str(expected_indoors),
                    actual=str(actual_indoors),
                ))

            if 'room' in game_state:
                expected_room = int(game_state['room'], 16) if isinstance(game_state['room'], str) else game_state['room']
                actual_room = self.emulator.read_memory(CriticalAddresses.ROOM_LAYOUT, 1).value
                report.checks.append(ValidationResult(
                    name="Room",
                    passed=(actual_room == expected_room),
                    expected=f"0x{expected_room:02X}",
                    actual=f"0x{actual_room:02X}",
                ))

            report.checks.append(ValidationResult(
                name="Entry Match",
                passed=True,
                expected=entry_id,
                actual=entry.get('meta', {}).get('label', entry_id),
                details=entry.get('description', '')
            ))

        except Exception as e:
            report.checks.append(ValidationResult(
                name="Library Load",
                passed=False,
                expected="Valid JSON",
                actual=str(e),
            ))

        report.passed = all(c.passed for c in report.checks)
        report.summary = self._generate_summary(report)

        return report

    def compare_snapshots(
        self,
        before: ProgressSnapshot,
        after: ProgressSnapshot
    ) -> List[str]:
        """Compare two progress snapshots and describe changes.

        Args:
            before: Earlier snapshot
            after: Later snapshot

        Returns:
            List of change descriptions
        """
        changes = []

        if before.game_state != after.game_state:
            changes.append(f"GameState: {before.game_state} -> {after.game_state}")

        if before.story_flags != after.story_flags:
            # Identify which flags changed
            added = after.story_flags & ~before.story_flags
            removed = before.story_flags & ~after.story_flags
            for flag in StoryFlag:
                if added & flag:
                    changes.append(f"Flag SET: {flag.name}")
                if removed & flag:
                    changes.append(f"Flag CLEARED: {flag.name}")

        if before.health != after.health:
            delta = after.health - before.health
            hearts_delta = delta / 8.0
            changes.append(f"Health: {before.hearts:.1f} -> {after.hearts:.1f} ({hearts_delta:+.1f})")

        if before.rupees != after.rupees:
            delta = after.rupees - before.rupees
            changes.append(f"Rupees: {before.rupees} -> {after.rupees} ({delta:+d})")

        if before.crystals != after.crystals:
            changes.append(f"Crystals: {before.dungeon_count} -> {after.dungeon_count} dungeons")

        if before.sword_level != after.sword_level:
            changes.append(f"Sword: level {before.sword_level} -> {after.sword_level}")

        return changes

    # =========================================================================
    # Private validation methods
    # =========================================================================

    def _check_health_valid(self, snap: ProgressSnapshot) -> ValidationResult:
        """Check health values are valid."""
        valid = (
            snap.health >= 0 and
            snap.health <= snap.max_health and
            snap.max_health > 0 and
            snap.max_health <= 160  # Max 20 hearts
        )
        return ValidationResult(
            name="Health Valid",
            passed=valid,
            expected="0 <= health <= max_health <= 160",
            actual=f"health={snap.health}, max={snap.max_health}",
            details=f"{snap.hearts:.1f}/{snap.max_hearts:.1f} hearts"
        )

    def _check_rupees_valid(self, snap: ProgressSnapshot) -> ValidationResult:
        """Check rupees are in valid range."""
        valid = 0 <= snap.rupees <= 9999
        return ValidationResult(
            name="Rupees Valid",
            passed=valid,
            expected="0-9999",
            actual=str(snap.rupees),
        )

    def _check_equipment_valid(self, snap: ProgressSnapshot) -> ValidationResult:
        """Check equipment levels are valid."""
        valid = (
            0 <= snap.sword_level <= 4 and
            0 <= snap.shield_level <= 3 and
            0 <= snap.armor_level <= 3
        )
        return ValidationResult(
            name="Equipment Valid",
            passed=valid,
            expected="sword(0-4), shield(0-3), armor(0-3)",
            actual=f"sword={snap.sword_level}, shield={snap.shield_level}, armor={snap.armor_level}",
        )

    def _check_story_consistency(self, snap: ProgressSnapshot) -> List[ValidationResult]:
        """Check story flags are consistent with game state."""
        results = []

        # Game state should match story flags
        if snap.game_state >= GameStateValue.LOOM_BEACH:
            has_intro = bool(snap.story_flags & StoryFlag.INTRO_COMPLETE)
            results.append(ValidationResult(
                name="Intro Flag Consistency",
                passed=has_intro,
                expected="INTRO_COMPLETE set after GameState >= 1",
                actual=f"GameState={snap.game_state}, INTRO_COMPLETE={'set' if has_intro else 'clear'}",
            ))

        if snap.game_state >= GameStateValue.FARORE_FREE:
            has_farore = bool(snap.story_flags & StoryFlag.FARORE_RESCUED)
            results.append(ValidationResult(
                name="Farore Flag Consistency",
                passed=has_farore,
                expected="FARORE_RESCUED set after GameState >= 3",
                actual=f"GameState={snap.game_state}, FARORE_RESCUED={'set' if has_farore else 'clear'}",
            ))

        return results

    def _check_dungeon_progress(self, snap: ProgressSnapshot) -> ValidationResult:
        """Check dungeon progress is valid."""
        # Crystals bitfield should have at most 8 bits set
        count = snap.dungeon_count
        valid = 0 <= count <= 8
        return ValidationResult(
            name="Dungeon Progress",
            passed=valid,
            expected="0-8 dungeons completed",
            actual=f"{count} dungeons (crystals=0x{snap.crystals:02X})",
        )

    def _generate_summary(self, report: ProgressReport) -> str:
        """Generate human-readable summary."""
        snap = report.snapshot
        parts = [
            f"GameState: {snap.game_state}",
            f"Health: {snap.hearts:.1f}/{snap.max_hearts:.1f}",
            f"Rupees: {snap.rupees}",
            f"Dungeons: {snap.dungeon_count}/8",
            f"Checks: {report.pass_count}/{len(report.checks)} passed",
        ]
        return " | ".join(parts)


def print_progress_report(report: ProgressReport):
    """Print progress report to console."""
    import time

    print(f"\n{'='*60}")
    print(f"  Progress Validation Report")
    print(f"  {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(report.timestamp))}")
    print(f"{'='*60}")

    snap = report.snapshot
    print(f"\n  Progress Snapshot:")
    print(f"    GameState: {snap.game_state}")
    print(f"    Story Flags: 0x{snap.story_flags:02X}")
    print(f"    Health: {snap.hearts:.1f}/{snap.max_hearts:.1f} hearts ({snap.health_percent*100:.0f}%)")
    print(f"    Rupees: {snap.rupees}")
    print(f"    Sword: level {snap.sword_level}")
    print(f"    Dungeons: {snap.dungeon_count}/8 (crystals=0x{snap.crystals:02X})")

    print(f"\n  Validation Checks:")
    for check in report.checks:
        status = "PASS" if check.passed else "FAIL"
        print(f"\n    [{status}] {check.name}")
        print(f"      Expected: {check.expected}")
        print(f"      Actual:   {check.actual}")
        if check.details:
            print(f"      Details:  {check.details}")

    print(f"\n{'='*60}")
    print(f"  RESULT: {'PASSED' if report.passed else 'FAILED'}")
    print(f"  Summary: {report.summary}")
    print(f"{'='*60}\n")
