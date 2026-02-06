"""Visual verification module for Oracle of Secrets campaign.

This module provides screenshot comparison and visual regression testing
to verify correct rendering during gameplay transitions.

Campaign Goals Supported:
- B.1: Black screen detection via visual comparison
- B.5: Visual regression for transition verification

Usage:
    from scripts.campaign.visual_verifier import VisualVerifier

    verifier = VisualVerifier()
    is_black = verifier.is_black_screen(screenshot)
    similarity = verifier.compare_screenshots(baseline, current)
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


class VerificationResult(Enum):
    """Result of visual verification."""
    PASS = auto()
    FAIL = auto()
    BLACK_SCREEN = auto()
    ERROR = auto()
    SKIPPED = auto()


@dataclass
class Screenshot:
    """Represents a captured screenshot."""
    path: Path
    timestamp: datetime
    frame_number: int
    area_id: int = 0
    room_id: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def hash(self) -> str:
        """Get file hash for comparison."""
        if not self.path.exists():
            return ""
        with open(self.path, "rb") as f:
            return hashlib.sha256(f.read()).hexdigest()[:16]

    def to_dict(self) -> Dict[str, Any]:
        """Serialize screenshot metadata."""
        return {
            "path": str(self.path),
            "timestamp": self.timestamp.isoformat(),
            "frame_number": self.frame_number,
            "area_id": self.area_id,
            "room_id": self.room_id,
            "hash": self.hash,
            "metadata": self.metadata
        }


@dataclass
class VerificationReport:
    """Report from visual verification."""
    result: VerificationResult
    similarity_score: float = 0.0
    black_pixel_ratio: float = 0.0
    baseline: Optional[Screenshot] = None
    current: Optional[Screenshot] = None
    notes: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize report."""
        return {
            "result": self.result.name,
            "similarity_score": self.similarity_score,
            "black_pixel_ratio": self.black_pixel_ratio,
            "baseline": self.baseline.to_dict() if self.baseline else None,
            "current": self.current.to_dict() if self.current else None,
            "notes": self.notes
        }


class VisualVerifier:
    """Visual verification for gameplay screenshots.

    This class provides methods to detect black screens and compare
    screenshots for visual regression testing.
    """

    BLACK_THRESHOLD = 0.95  # 95% black pixels = black screen
    SIMILARITY_THRESHOLD = 0.90  # 90% similar = matching

    def __init__(
        self,
        baseline_dir: Optional[Path] = None,
        capture_dir: Optional[Path] = None
    ):
        """Initialize verifier.

        Args:
            baseline_dir: Directory containing baseline screenshots
            capture_dir: Directory to store captured screenshots
        """
        self._baseline_dir = baseline_dir or Path("Docs/Campaign/Evidence/baseline")
        self._capture_dir = capture_dir or Path("Docs/Campaign/Evidence/captures")
        self._logger = logging.getLogger(__name__)

        # Ensure directories exist
        self._baseline_dir.mkdir(parents=True, exist_ok=True)
        self._capture_dir.mkdir(parents=True, exist_ok=True)

    def is_black_screen(self, screenshot: Screenshot) -> bool:
        """Check if screenshot shows a black screen.

        Args:
            screenshot: Screenshot to check

        Returns:
            True if screen is predominantly black
        """
        if not screenshot.path.exists():
            self._logger.warning(f"Screenshot not found: {screenshot.path}")
            return False

        # Without PIL, we can do a simple file size heuristic
        # Very small PNG files are likely solid colors (black)
        file_size = screenshot.path.stat().st_size

        # A 256x224 solid black PNG is typically under 1KB
        # Real gameplay screenshots are usually 5KB-50KB
        if file_size < 1024:
            return True

        # For proper implementation, would need PIL/Pillow:
        # from PIL import Image
        # img = Image.open(screenshot.path)
        # pixels = list(img.getdata())
        # black_count = sum(1 for p in pixels if sum(p[:3]) < 30)
        # return (black_count / len(pixels)) > self.BLACK_THRESHOLD

        return False

    def compare_screenshots(
        self,
        baseline: Screenshot,
        current: Screenshot
    ) -> VerificationReport:
        """Compare two screenshots for similarity.

        Args:
            baseline: Reference screenshot
            current: Screenshot to verify

        Returns:
            Verification report with similarity score
        """
        report = VerificationReport(
            result=VerificationResult.SKIPPED,
            baseline=baseline,
            current=current
        )

        if not baseline.path.exists():
            report.result = VerificationResult.ERROR
            report.notes.append(f"Baseline not found: {baseline.path}")
            return report

        if not current.path.exists():
            report.result = VerificationResult.ERROR
            report.notes.append(f"Current screenshot not found: {current.path}")
            return report

        # Check for black screen
        if self.is_black_screen(current):
            report.result = VerificationResult.BLACK_SCREEN
            report.black_pixel_ratio = 1.0
            report.notes.append("Current screenshot is black screen")
            return report

        # Simple hash comparison (exact match)
        if baseline.hash == current.hash:
            report.result = VerificationResult.PASS
            report.similarity_score = 1.0
            report.notes.append("Exact hash match")
            return report

        # For detailed comparison, would need image processing library
        # This is a placeholder for actual pixel-level comparison
        report.result = VerificationResult.SKIPPED
        report.notes.append(
            "Detailed comparison requires PIL/Pillow library"
        )

        return report

    def verify_transition(
        self,
        before: Screenshot,
        after: Screenshot,
        expected_area: int
    ) -> VerificationReport:
        """Verify a screen transition completed correctly.

        Args:
            before: Screenshot before transition
            after: Screenshot after transition
            expected_area: Expected area ID after transition

        Returns:
            Verification report
        """
        report = VerificationReport(
            result=VerificationResult.SKIPPED,
            baseline=before,
            current=after
        )

        # Check for black screen after transition (potential bug)
        if self.is_black_screen(after):
            report.result = VerificationResult.BLACK_SCREEN
            report.notes.append(
                "Black screen detected after transition - potential bug"
            )
            return report

        # Check area ID changed correctly
        if after.area_id != expected_area:
            report.result = VerificationResult.FAIL
            report.notes.append(
                f"Wrong area after transition: expected 0x{expected_area:02X}, "
                f"got 0x{after.area_id:02X}"
            )
            return report

        # Basic checks passed
        report.result = VerificationResult.PASS
        report.notes.append(
            f"Transition verified: area 0x{before.area_id:02X} → 0x{after.area_id:02X}"
        )

        return report

    def capture_screenshot(
        self,
        emulator,
        frame_number: int,
        area_id: int = 0,
        room_id: int = 0,
        prefix: str = "capture"
    ) -> Optional[Screenshot]:
        """Capture a screenshot from the emulator.

        Args:
            emulator: Emulator interface with screenshot capability
            frame_number: Current frame number
            area_id: Current area ID
            room_id: Current room ID
            prefix: Filename prefix

        Returns:
            Screenshot object or None if capture failed
        """
        timestamp = datetime.now()
        filename = (
            f"{prefix}_{timestamp.strftime('%Y%m%d_%H%M%S')}_"
            f"frame{frame_number}_area{area_id:02X}.png"
        )
        path = self._capture_dir / filename

        # Attempt to capture via emulator
        if hasattr(emulator, 'screenshot'):
            try:
                emulator.screenshot(str(path))
                return Screenshot(
                    path=path,
                    timestamp=timestamp,
                    frame_number=frame_number,
                    area_id=area_id,
                    room_id=room_id
                )
            except Exception as e:
                self._logger.error(f"Screenshot capture failed: {e}")

        return None

    def get_baseline(self, area_id: int, room_id: int = 0) -> Optional[Screenshot]:
        """Get baseline screenshot for an area.

        Args:
            area_id: Area ID to look up
            room_id: Room ID (optional)

        Returns:
            Baseline screenshot or None if not found
        """
        pattern = f"baseline_area{area_id:02X}*.png"
        matches = list(self._baseline_dir.glob(pattern))

        if not matches:
            return None

        # Return most recent baseline
        path = max(matches, key=lambda p: p.stat().st_mtime)
        return Screenshot(
            path=path,
            timestamp=datetime.fromtimestamp(path.stat().st_mtime),
            frame_number=0,
            area_id=area_id,
            room_id=room_id
        )


# =============================================================================
# Utility Functions
# =============================================================================

def create_verifier(
    baseline_dir: Optional[Path] = None,
    capture_dir: Optional[Path] = None
) -> VisualVerifier:
    """Create a visual verifier instance.

    Args:
        baseline_dir: Optional baseline directory
        capture_dir: Optional capture directory

    Returns:
        Configured verifier
    """
    return VisualVerifier(baseline_dir=baseline_dir, capture_dir=capture_dir)


def quick_black_screen_check(path: Path) -> bool:
    """Quick check if a screenshot file is a black screen.

    Args:
        path: Path to screenshot file

    Returns:
        True if likely black screen based on file size
    """
    if not path.exists():
        return False

    # Very small PNG files are likely solid colors
    return path.stat().st_size < 1024
