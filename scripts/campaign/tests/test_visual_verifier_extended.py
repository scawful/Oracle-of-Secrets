"""Extended tests for VisualVerifier and visual verification components.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- B.1: Black screen detection via visual comparison

These tests verify the visual verification system including screenshots,
comparison logic, and transition verification.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
from datetime import datetime
import tempfile
import os

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.visual_verifier import (
    VerificationResult, Screenshot, VerificationReport,
    VisualVerifier, create_verifier, quick_black_screen_check
)


class TestVerificationResultEnum:
    """Test VerificationResult enum."""

    def test_pass_exists(self):
        """Test PASS result exists."""
        assert VerificationResult.PASS is not None

    def test_fail_exists(self):
        """Test FAIL result exists."""
        assert VerificationResult.FAIL is not None

    def test_black_screen_exists(self):
        """Test BLACK_SCREEN result exists."""
        assert VerificationResult.BLACK_SCREEN is not None

    def test_error_exists(self):
        """Test ERROR result exists."""
        assert VerificationResult.ERROR is not None

    def test_skipped_exists(self):
        """Test SKIPPED result exists."""
        assert VerificationResult.SKIPPED is not None

    def test_all_results_distinct(self):
        """Test all results have distinct values."""
        results = list(VerificationResult)
        values = [r.value for r in results]
        assert len(values) == len(set(values))

    def test_results_have_names(self):
        """Test all results have string names."""
        for result in VerificationResult:
            assert result.name is not None
            assert len(result.name) > 0


class TestScreenshotCreation:
    """Test Screenshot dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic screenshot."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert screenshot.path == Path("/tmp/test.png")
        assert screenshot.frame_number == 100

    def test_default_area_id(self):
        """Test default area_id is 0."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert screenshot.area_id == 0

    def test_default_room_id(self):
        """Test default room_id is 0."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert screenshot.room_id == 0

    def test_default_metadata(self):
        """Test default metadata is empty dict."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert screenshot.metadata == {}

    def test_custom_area_room(self):
        """Test custom area_id and room_id."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29,
            room_id=0x05
        )
        assert screenshot.area_id == 0x29
        assert screenshot.room_id == 0x05

    def test_custom_metadata(self):
        """Test custom metadata dict."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100,
            metadata={"mode": 0x09, "health": 24}
        )
        assert screenshot.metadata["mode"] == 0x09
        assert screenshot.metadata["health"] == 24


class TestScreenshotHash:
    """Test Screenshot hash property."""

    def test_hash_nonexistent_file(self):
        """Test hash returns empty string for nonexistent file."""
        screenshot = Screenshot(
            path=Path("/nonexistent/path.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert screenshot.hash == ""

    def test_hash_existing_file(self):
        """Test hash returns value for existing file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"test data for hash")
            temp_path = Path(f.name)

        try:
            screenshot = Screenshot(
                path=temp_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            assert len(screenshot.hash) == 16
        finally:
            temp_path.unlink()

    def test_hash_deterministic(self):
        """Test hash is deterministic for same content."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"deterministic content")
            temp_path = Path(f.name)

        try:
            screenshot = Screenshot(
                path=temp_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            hash1 = screenshot.hash
            hash2 = screenshot.hash
            assert hash1 == hash2
        finally:
            temp_path.unlink()


class TestScreenshotSerialization:
    """Test Screenshot serialization."""

    def test_to_dict_includes_path(self):
        """Test to_dict includes path as string."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        result = screenshot.to_dict()
        assert result["path"] == "/tmp/test.png"

    def test_to_dict_includes_timestamp(self):
        """Test to_dict includes timestamp as ISO string."""
        timestamp = datetime(2026, 1, 24, 12, 0, 0)
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=timestamp,
            frame_number=100
        )
        result = screenshot.to_dict()
        assert result["timestamp"] == timestamp.isoformat()

    def test_to_dict_includes_frame_number(self):
        """Test to_dict includes frame_number."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=12345
        )
        result = screenshot.to_dict()
        assert result["frame_number"] == 12345

    def test_to_dict_includes_area_room(self):
        """Test to_dict includes area_id and room_id."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100,
            area_id=0x29,
            room_id=0x05
        )
        result = screenshot.to_dict()
        assert result["area_id"] == 0x29
        assert result["room_id"] == 0x05

    def test_to_dict_includes_hash(self):
        """Test to_dict includes hash."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        result = screenshot.to_dict()
        assert "hash" in result

    def test_to_dict_includes_metadata(self):
        """Test to_dict includes metadata."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100,
            metadata={"key": "value"}
        )
        result = screenshot.to_dict()
        assert result["metadata"] == {"key": "value"}


class TestVerificationReportCreation:
    """Test VerificationReport dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic report."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.result == VerificationResult.PASS

    def test_default_similarity_score(self):
        """Test default similarity_score is 0.0."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.similarity_score == 0.0

    def test_default_black_pixel_ratio(self):
        """Test default black_pixel_ratio is 0.0."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.black_pixel_ratio == 0.0

    def test_default_baseline(self):
        """Test default baseline is None."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.baseline is None

    def test_default_current(self):
        """Test default current is None."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.current is None

    def test_default_notes(self):
        """Test default notes is empty list."""
        report = VerificationReport(result=VerificationResult.PASS)
        assert report.notes == []

    def test_with_screenshots(self):
        """Test report with screenshot references."""
        baseline = Screenshot(
            path=Path("/tmp/baseline.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        current = Screenshot(
            path=Path("/tmp/current.png"),
            timestamp=datetime.now(),
            frame_number=200
        )
        report = VerificationReport(
            result=VerificationResult.PASS,
            baseline=baseline,
            current=current
        )
        assert report.baseline is baseline
        assert report.current is current


class TestVerificationReportSerialization:
    """Test VerificationReport serialization."""

    def test_to_dict_includes_result(self):
        """Test to_dict includes result name."""
        report = VerificationReport(result=VerificationResult.PASS)
        result = report.to_dict()
        assert result["result"] == "PASS"

    def test_to_dict_includes_scores(self):
        """Test to_dict includes similarity and black pixel scores."""
        report = VerificationReport(
            result=VerificationResult.PASS,
            similarity_score=0.95,
            black_pixel_ratio=0.02
        )
        result = report.to_dict()
        assert result["similarity_score"] == 0.95
        assert result["black_pixel_ratio"] == 0.02

    def test_to_dict_with_none_screenshots(self):
        """Test to_dict handles None screenshots."""
        report = VerificationReport(result=VerificationResult.PASS)
        result = report.to_dict()
        assert result["baseline"] is None
        assert result["current"] is None

    def test_to_dict_with_screenshots(self):
        """Test to_dict serializes screenshots."""
        baseline = Screenshot(
            path=Path("/tmp/baseline.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        report = VerificationReport(
            result=VerificationResult.PASS,
            baseline=baseline
        )
        result = report.to_dict()
        assert result["baseline"] is not None
        assert result["baseline"]["path"] == "/tmp/baseline.png"

    def test_to_dict_includes_notes(self):
        """Test to_dict includes notes."""
        report = VerificationReport(
            result=VerificationResult.PASS,
            notes=["Note 1", "Note 2"]
        )
        result = report.to_dict()
        assert result["notes"] == ["Note 1", "Note 2"]


class TestVisualVerifierCreation:
    """Test VisualVerifier creation."""

    def test_default_directories(self):
        """Test verifier uses default directories."""
        verifier = VisualVerifier()
        assert verifier._baseline_dir == Path("Docs/Campaign/Evidence/baseline")
        assert verifier._capture_dir == Path("Docs/Campaign/Evidence/captures")

    def test_custom_directories(self):
        """Test verifier accepts custom directories."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline"
            capture = Path(tmpdir) / "capture"
            verifier = VisualVerifier(
                baseline_dir=baseline,
                capture_dir=capture
            )
            assert verifier._baseline_dir == baseline
            assert verifier._capture_dir == capture

    def test_creates_directories(self):
        """Test verifier creates directories if they don't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "new_baseline"
            capture = Path(tmpdir) / "new_capture"
            verifier = VisualVerifier(
                baseline_dir=baseline,
                capture_dir=capture
            )
            assert baseline.exists()
            assert capture.exists()

    def test_thresholds(self):
        """Test verifier has threshold constants."""
        assert VisualVerifier.BLACK_THRESHOLD == 0.95
        assert VisualVerifier.SIMILARITY_THRESHOLD == 0.90


class TestVisualVerifierBlackScreen:
    """Test VisualVerifier black screen detection."""

    def test_nonexistent_file_not_black(self):
        """Test nonexistent file is not detected as black screen."""
        verifier = VisualVerifier()
        screenshot = Screenshot(
            path=Path("/nonexistent/file.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        assert verifier.is_black_screen(screenshot) is False

    def test_small_file_is_black_screen(self):
        """Test very small file is detected as black screen."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Write less than 1KB
            f.write(b"x" * 500)
            temp_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            screenshot = Screenshot(
                path=temp_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            assert verifier.is_black_screen(screenshot) is True
        finally:
            temp_path.unlink()

    def test_large_file_not_black_screen(self):
        """Test larger file is not detected as black screen."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Write more than 1KB
            f.write(b"x" * 5000)
            temp_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            screenshot = Screenshot(
                path=temp_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            assert verifier.is_black_screen(screenshot) is False
        finally:
            temp_path.unlink()


class TestVisualVerifierCompare:
    """Test VisualVerifier screenshot comparison."""

    def test_compare_baseline_not_found(self):
        """Test comparison fails if baseline not found."""
        verifier = VisualVerifier()
        baseline = Screenshot(
            path=Path("/nonexistent/baseline.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        current = Screenshot(
            path=Path("/nonexistent/current.png"),
            timestamp=datetime.now(),
            frame_number=200
        )
        report = verifier.compare_screenshots(baseline, current)
        assert report.result == VerificationResult.ERROR
        assert "Baseline not found" in report.notes[0]

    def test_compare_current_not_found(self):
        """Test comparison fails if current not found."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"baseline content")
            baseline_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            baseline = Screenshot(
                path=baseline_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            current = Screenshot(
                path=Path("/nonexistent/current.png"),
                timestamp=datetime.now(),
                frame_number=200
            )
            report = verifier.compare_screenshots(baseline, current)
            assert report.result == VerificationResult.ERROR
            assert "Current screenshot not found" in report.notes[0]
        finally:
            baseline_path.unlink()

    def test_compare_black_screen_detected(self):
        """Test comparison detects black screen."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"baseline content large enough" * 100)
            baseline_path = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Small file = black screen
            f.write(b"x" * 500)
            current_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            baseline = Screenshot(
                path=baseline_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            current = Screenshot(
                path=current_path,
                timestamp=datetime.now(),
                frame_number=200
            )
            report = verifier.compare_screenshots(baseline, current)
            assert report.result == VerificationResult.BLACK_SCREEN
            assert report.black_pixel_ratio == 1.0
        finally:
            baseline_path.unlink()
            current_path.unlink()

    def test_compare_exact_match(self):
        """Test comparison detects exact hash match."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Content must be > 1024 bytes to avoid black screen detection
            content = b"exact same content for both files" * 100
            f.write(content)
            baseline_path = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(content)
            current_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            baseline = Screenshot(
                path=baseline_path,
                timestamp=datetime.now(),
                frame_number=100
            )
            current = Screenshot(
                path=current_path,
                timestamp=datetime.now(),
                frame_number=200
            )
            report = verifier.compare_screenshots(baseline, current)
            assert report.result == VerificationResult.PASS
            assert report.similarity_score == 1.0
        finally:
            baseline_path.unlink()
            current_path.unlink()


class TestVisualVerifierTransition:
    """Test VisualVerifier transition verification."""

    def test_transition_black_screen_detected(self):
        """Test transition fails on black screen after."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"before content" * 100)
            before_path = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            # Small file = black screen
            f.write(b"x" * 500)
            after_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            before = Screenshot(
                path=before_path,
                timestamp=datetime.now(),
                frame_number=100,
                area_id=0x29
            )
            after = Screenshot(
                path=after_path,
                timestamp=datetime.now(),
                frame_number=200,
                area_id=0x1E
            )
            report = verifier.verify_transition(before, after, expected_area=0x1E)
            assert report.result == VerificationResult.BLACK_SCREEN
            assert "potential bug" in report.notes[0].lower()
        finally:
            before_path.unlink()
            after_path.unlink()

    def test_transition_wrong_area(self):
        """Test transition fails on wrong area."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"before content" * 100)
            before_path = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"after content" * 100)
            after_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            before = Screenshot(
                path=before_path,
                timestamp=datetime.now(),
                frame_number=100,
                area_id=0x29
            )
            after = Screenshot(
                path=after_path,
                timestamp=datetime.now(),
                frame_number=200,
                area_id=0x2A  # Wrong area
            )
            report = verifier.verify_transition(before, after, expected_area=0x1E)
            assert report.result == VerificationResult.FAIL
            assert "Wrong area" in report.notes[0]
        finally:
            before_path.unlink()
            after_path.unlink()

    def test_transition_success(self):
        """Test successful transition verification."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"before content" * 100)
            before_path = Path(f.name)

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"after content" * 100)
            after_path = Path(f.name)

        try:
            verifier = VisualVerifier()
            before = Screenshot(
                path=before_path,
                timestamp=datetime.now(),
                frame_number=100,
                area_id=0x29
            )
            after = Screenshot(
                path=after_path,
                timestamp=datetime.now(),
                frame_number=200,
                area_id=0x1E  # Correct area
            )
            report = verifier.verify_transition(before, after, expected_area=0x1E)
            assert report.result == VerificationResult.PASS
            assert "verified" in report.notes[0].lower()
        finally:
            before_path.unlink()
            after_path.unlink()


class TestVisualVerifierCapture:
    """Test VisualVerifier screenshot capture."""

    def test_capture_with_screenshot_method(self):
        """Test capture uses emulator's screenshot method."""
        with tempfile.TemporaryDirectory() as tmpdir:
            capture_dir = Path(tmpdir) / "captures"
            verifier = VisualVerifier(capture_dir=capture_dir)

            mock_emu = Mock()
            mock_emu.screenshot = Mock()

            screenshot = verifier.capture_screenshot(
                mock_emu,
                frame_number=1000,
                area_id=0x29,
                room_id=0x05,
                prefix="test"
            )

            assert screenshot is not None
            assert screenshot.frame_number == 1000
            assert screenshot.area_id == 0x29
            assert screenshot.room_id == 0x05
            mock_emu.screenshot.assert_called_once()

    def test_capture_without_screenshot_method(self):
        """Test capture returns None if emulator lacks screenshot."""
        verifier = VisualVerifier()
        mock_emu = Mock(spec=[])  # No screenshot attribute

        screenshot = verifier.capture_screenshot(mock_emu, frame_number=1000)
        assert screenshot is None

    def test_capture_exception_handled(self):
        """Test capture handles exceptions gracefully."""
        verifier = VisualVerifier()
        mock_emu = Mock()
        mock_emu.screenshot = Mock(side_effect=Exception("Capture failed"))

        screenshot = verifier.capture_screenshot(mock_emu, frame_number=1000)
        assert screenshot is None


class TestVisualVerifierBaseline:
    """Test VisualVerifier baseline lookup."""

    def test_get_baseline_not_found(self):
        """Test get_baseline returns None if not found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            baseline_dir.mkdir()
            verifier = VisualVerifier(baseline_dir=baseline_dir)

            result = verifier.get_baseline(area_id=0x29)
            assert result is None

    def test_get_baseline_found(self):
        """Test get_baseline returns screenshot if found."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline_dir = Path(tmpdir) / "baseline"
            baseline_dir.mkdir()

            # Create a matching baseline file
            baseline_file = baseline_dir / "baseline_area29_test.png"
            baseline_file.write_bytes(b"baseline content")

            verifier = VisualVerifier(baseline_dir=baseline_dir)
            result = verifier.get_baseline(area_id=0x29)

            assert result is not None
            assert result.path == baseline_file
            assert result.area_id == 0x29


class TestUtilityFunctions:
    """Test utility functions."""

    def test_create_verifier(self):
        """Test create_verifier creates VisualVerifier."""
        verifier = create_verifier()
        assert isinstance(verifier, VisualVerifier)

    def test_create_verifier_with_dirs(self):
        """Test create_verifier accepts custom dirs."""
        with tempfile.TemporaryDirectory() as tmpdir:
            baseline = Path(tmpdir) / "baseline"
            capture = Path(tmpdir) / "capture"
            verifier = create_verifier(
                baseline_dir=baseline,
                capture_dir=capture
            )
            assert verifier._baseline_dir == baseline
            assert verifier._capture_dir == capture

    def test_quick_black_screen_check_nonexistent(self):
        """Test quick_black_screen_check on nonexistent file."""
        result = quick_black_screen_check(Path("/nonexistent/file.png"))
        assert result is False

    def test_quick_black_screen_check_small_file(self):
        """Test quick_black_screen_check on small file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 500)
            temp_path = Path(f.name)

        try:
            result = quick_black_screen_check(temp_path)
            assert result is True
        finally:
            temp_path.unlink()

    def test_quick_black_screen_check_large_file(self):
        """Test quick_black_screen_check on large file."""
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            f.write(b"x" * 5000)
            temp_path = Path(f.name)

        try:
            result = quick_black_screen_check(temp_path)
            assert result is False
        finally:
            temp_path.unlink()


class TestVerificationResultComparison:
    """Test VerificationResult comparisons."""

    def test_pass_not_equal_fail(self):
        """Test PASS != FAIL."""
        assert VerificationResult.PASS != VerificationResult.FAIL

    def test_pass_equals_pass(self):
        """Test PASS == PASS."""
        assert VerificationResult.PASS == VerificationResult.PASS

    def test_black_screen_not_equal_error(self):
        """Test BLACK_SCREEN != ERROR."""
        assert VerificationResult.BLACK_SCREEN != VerificationResult.ERROR


class TestScreenshotMetadata:
    """Test Screenshot metadata handling."""

    def test_metadata_mutable(self):
        """Test metadata can be modified."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100
        )
        screenshot.metadata["new_key"] = "new_value"
        assert screenshot.metadata["new_key"] == "new_value"

    def test_metadata_preserves_types(self):
        """Test metadata preserves various types."""
        screenshot = Screenshot(
            path=Path("/tmp/test.png"),
            timestamp=datetime.now(),
            frame_number=100,
            metadata={
                "string": "value",
                "int": 42,
                "float": 3.14,
                "list": [1, 2, 3],
                "dict": {"nested": "value"}
            }
        )
        assert screenshot.metadata["string"] == "value"
        assert screenshot.metadata["int"] == 42
        assert screenshot.metadata["float"] == 3.14
        assert screenshot.metadata["list"] == [1, 2, 3]
        assert screenshot.metadata["dict"]["nested"] == "value"
