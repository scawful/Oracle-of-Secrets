"""Tests for visual_verifier module.

Campaign Goals Supported:
- B.1: Black screen detection verification
- B.5: Visual regression test infrastructure
"""

import pytest
import tempfile
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.visual_verifier import (
    VerificationResult,
    Screenshot,
    VerificationReport,
    VisualVerifier,
    create_verifier,
    quick_black_screen_check,
)


class TestVerificationResult:
    """Tests for VerificationResult enum."""

    def test_results_exist(self):
        """Test all result types are defined."""
        assert VerificationResult.PASS is not None
        assert VerificationResult.FAIL is not None
        assert VerificationResult.BLACK_SCREEN is not None
        assert VerificationResult.ERROR is not None
        assert VerificationResult.SKIPPED is not None


class TestScreenshot:
    """Tests for Screenshot dataclass."""

    def test_create_screenshot(self):
        """Test creating a screenshot object."""
        path = Path("/tmp/test.png")
        screenshot = Screenshot(
            path=path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29,
            room_id=0x00
        )
        assert screenshot.path == path
        assert screenshot.frame_number == 100
        assert screenshot.area_id == 0x29

    def test_hash_nonexistent_file(self):
        """Test hash returns empty for nonexistent file."""
        screenshot = Screenshot(
            path=Path("/nonexistent/file.png"),
            timestamp=datetime.now(),
            frame_number=0
        )
        assert screenshot.hash == ""

    def test_hash_existing_file(self):
        """Test hash returns value for existing file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"test content for hashing")
            path = Path(f.name)

        try:
            screenshot = Screenshot(
                path=path,
                timestamp=datetime.now(),
                frame_number=0
            )
            assert len(screenshot.hash) == 16  # Truncated SHA256
        finally:
            path.unlink()

    def test_to_dict(self):
        """Test screenshot serialization."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime(2026, 1, 24, 12, 0, 0),
            frame_number=500,
            area_id=0x29,
            metadata={"test": True}
        )
        data = screenshot.to_dict()

        assert data["frame_number"] == 500
        assert data["area_id"] == 0x29
        assert data["metadata"]["test"] is True
        assert "2026-01-24" in data["timestamp"]


class TestVerificationReport:
    """Tests for VerificationReport dataclass."""

    def test_create_report(self):
        """Test creating a verification report."""
        report = VerificationReport(
            result=VerificationResult.PASS,
            similarity_score=0.95
        )
        assert report.result == VerificationResult.PASS
        assert report.similarity_score == 0.95

    def test_report_with_notes(self):
        """Test report with notes."""
        report = VerificationReport(
            result=VerificationResult.FAIL,
            notes=["Mismatch detected", "Area changed unexpectedly"]
        )
        assert len(report.notes) == 2
        assert "Mismatch" in report.notes[0]

    def test_to_dict(self):
        """Test report serialization."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=0
        )
        report = VerificationReport(
            result=VerificationResult.BLACK_SCREEN,
            black_pixel_ratio=0.99,
            current=screenshot
        )
        data = report.to_dict()

        assert data["result"] == "BLACK_SCREEN"
        assert data["black_pixel_ratio"] == 0.99
        assert data["current"] is not None


class TestVisualVerifier:
    """Tests for VisualVerifier class."""

    @pytest.fixture
    def temp_dirs(self):
        """Create temporary directories for testing."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            capture_dir = Path(tmpdir) / "captures"
            baseline_dir.mkdir()
            capture_dir.mkdir()
            yield baseline_dir, capture_dir

    def test_create_verifier(self, temp_dirs):
        """Test creating verifier."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(
            baseline_dir=baseline_dir,
            capture_dir=capture_dir
        )
        assert verifier is not None
        assert verifier._baseline_dir == baseline_dir

    def test_default_directories_created(self):
        """Test default directories are created."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "test_baseline"
            capture = Path(tmpdir) / "test_capture"

            verifier = VisualVerifier(
                baseline_dir=baseline,
                capture_dir=capture
            )

            assert baseline.exists()
            assert capture.exists()

    def test_is_black_screen_nonexistent(self, temp_dirs):
        """Test black screen check for nonexistent file."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        screenshot = Screenshot(
            path=Path("/nonexistent.png"),
            timestamp=datetime.now(),
            frame_number=0
        )

        assert verifier.is_black_screen(screenshot) is False

    def test_is_black_screen_small_file(self, temp_dirs):
        """Test black screen detection for small file."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Create a very small file (simulates black screen)
        small_file = capture_dir / "black.png"
        small_file.write_bytes(b"\x89PNG" + b"\x00" * 100)

        screenshot = Screenshot(
            path=small_file,
            timestamp=datetime.now(),
            frame_number=0
        )

        assert verifier.is_black_screen(screenshot) is True

    def test_is_black_screen_normal_file(self, temp_dirs):
        """Test black screen detection for normal file."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Create a larger file (simulates real screenshot)
        normal_file = capture_dir / "normal.png"
        normal_file.write_bytes(b"\x89PNG" + b"\x00" * 10000)

        screenshot = Screenshot(
            path=normal_file,
            timestamp=datetime.now(),
            frame_number=0
        )

        assert verifier.is_black_screen(screenshot) is False

    def test_compare_screenshots_baseline_missing(self, temp_dirs):
        """Test comparison when baseline is missing."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        baseline = Screenshot(
            path=Path("/missing/baseline.png"),
            timestamp=datetime.now(),
            frame_number=0
        )
        current = Screenshot(
            path=capture_dir / "current.png",
            timestamp=datetime.now(),
            frame_number=100
        )

        report = verifier.compare_screenshots(baseline, current)

        assert report.result == VerificationResult.ERROR
        assert "Baseline not found" in report.notes[0]

    def test_compare_screenshots_current_missing(self, temp_dirs):
        """Test comparison when current is missing."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Create baseline
        baseline_path = baseline_dir / "baseline.png"
        baseline_path.write_bytes(b"baseline content")

        baseline = Screenshot(
            path=baseline_path,
            timestamp=datetime.now(),
            frame_number=0
        )
        current = Screenshot(
            path=Path("/missing/current.png"),
            timestamp=datetime.now(),
            frame_number=100
        )

        report = verifier.compare_screenshots(baseline, current)

        assert report.result == VerificationResult.ERROR
        assert "Current screenshot not found" in report.notes[0]

    def test_compare_screenshots_exact_match(self, temp_dirs):
        """Test comparison with exact match."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Content must be >1KB to not be detected as black screen
        content = b"identical screenshot content" * 100

        baseline_path = baseline_dir / "baseline.png"
        baseline_path.write_bytes(content)

        current_path = capture_dir / "current.png"
        current_path.write_bytes(content)

        baseline = Screenshot(
            path=baseline_path,
            timestamp=datetime.now(),
            frame_number=0
        )
        current = Screenshot(
            path=current_path,
            timestamp=datetime.now(),
            frame_number=100
        )

        report = verifier.compare_screenshots(baseline, current)

        assert report.result == VerificationResult.PASS
        assert report.similarity_score == 1.0
        assert "Exact hash match" in report.notes[0]

    def test_compare_screenshots_black_screen_detected(self, temp_dirs):
        """Test comparison detects black screen in current."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Normal baseline
        baseline_path = baseline_dir / "baseline.png"
        baseline_path.write_bytes(b"x" * 5000)

        # Black screen current (small file)
        current_path = capture_dir / "current.png"
        current_path.write_bytes(b"\x89PNG" + b"\x00" * 100)

        baseline = Screenshot(
            path=baseline_path,
            timestamp=datetime.now(),
            frame_number=0
        )
        current = Screenshot(
            path=current_path,
            timestamp=datetime.now(),
            frame_number=100
        )

        report = verifier.compare_screenshots(baseline, current)

        assert report.result == VerificationResult.BLACK_SCREEN

    def test_verify_transition_black_screen(self, temp_dirs):
        """Test transition verification catches black screen."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        before_path = capture_dir / "before.png"
        before_path.write_bytes(b"x" * 5000)

        after_path = capture_dir / "after.png"
        after_path.write_bytes(b"\x89PNG" + b"\x00" * 100)  # Black

        before = Screenshot(
            path=before_path,
            timestamp=datetime.now(),
            frame_number=0,
            area_id=0x09
        )
        after = Screenshot(
            path=after_path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29
        )

        report = verifier.verify_transition(before, after, expected_area=0x29)

        assert report.result == VerificationResult.BLACK_SCREEN
        assert "Black screen detected" in report.notes[0]

    def test_verify_transition_wrong_area(self, temp_dirs):
        """Test transition verification catches wrong area."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        before_path = capture_dir / "before.png"
        before_path.write_bytes(b"x" * 5000)

        after_path = capture_dir / "after.png"
        after_path.write_bytes(b"y" * 5000)

        before = Screenshot(
            path=before_path,
            timestamp=datetime.now(),
            frame_number=0,
            area_id=0x09
        )
        after = Screenshot(
            path=after_path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x1E  # Wrong area
        )

        report = verifier.verify_transition(before, after, expected_area=0x29)

        assert report.result == VerificationResult.FAIL
        assert "Wrong area" in report.notes[0]

    def test_verify_transition_success(self, temp_dirs):
        """Test successful transition verification."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        before_path = capture_dir / "before.png"
        before_path.write_bytes(b"x" * 5000)

        after_path = capture_dir / "after.png"
        after_path.write_bytes(b"y" * 5000)

        before = Screenshot(
            path=before_path,
            timestamp=datetime.now(),
            frame_number=0,
            area_id=0x09
        )
        after = Screenshot(
            path=after_path,
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29  # Correct area
        )

        report = verifier.verify_transition(before, after, expected_area=0x29)

        assert report.result == VerificationResult.PASS
        assert "Transition verified" in report.notes[0]

    def test_get_baseline_not_found(self, temp_dirs):
        """Test get_baseline returns None when not found."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        baseline = verifier.get_baseline(0x99)  # Nonexistent

        assert baseline is None

    def test_get_baseline_found(self, temp_dirs):
        """Test get_baseline finds matching file."""
        baseline_dir, capture_dir = temp_dirs
        verifier = VisualVerifier(baseline_dir, capture_dir)

        # Create a baseline file
        baseline_path = baseline_dir / "baseline_area29_test.png"
        baseline_path.write_bytes(b"test baseline")

        baseline = verifier.get_baseline(0x29)

        assert baseline is not None
        assert baseline.path == baseline_path
        assert baseline.area_id == 0x29


class TestUtilityFunctions:
    """Tests for utility functions."""

    def test_create_verifier(self):
        """Test create_verifier factory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            verifier = create_verifier(
                baseline_dir=Path(tmpdir) / "base",
                capture_dir=Path(tmpdir) / "cap"
            )
            assert verifier is not None
            assert isinstance(verifier, VisualVerifier)

    def test_quick_black_screen_check_nonexistent(self):
        """Test quick check for nonexistent file."""
        assert quick_black_screen_check(Path("/nonexistent.png")) is False

    def test_quick_black_screen_check_small(self):
        """Test quick check for small file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 500)  # Small file
            path = Path(f.name)

        try:
            assert quick_black_screen_check(path) is True
        finally:
            path.unlink()

    def test_quick_black_screen_check_normal(self):
        """Test quick check for normal file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 5000)  # Normal file
            path = Path(f.name)

        try:
            assert quick_black_screen_check(path) is False
        finally:
            path.unlink()
