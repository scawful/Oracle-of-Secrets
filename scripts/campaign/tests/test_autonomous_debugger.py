"""Unit tests for scripts.campaign.autonomous_debugger.

These tests validate the pure detection logic (SoftLockDetector) without
requiring a live Mesen2 instance.
"""

from __future__ import annotations

from dataclasses import replace

from scripts.campaign.autonomous_debugger import SoftLockDetector


class TestSoftLockDetector:
    def test_position_stagnation_triggers(self, sample_overworld_state):
        detector = SoftLockDetector(
            stagnation_threshold=5,
            black_screen_threshold=999,
            mode_stuck_threshold=999,
        )

        anomaly = None
        for i in range(5):
            anomaly = detector.update(
                replace(sample_overworld_state, timestamp=1000.0 + i, link_state=0x01)
            )

        assert anomaly is not None
        assert anomaly.type == "stagnation"
        assert anomaly.severity == "warning"
        assert anomaly.frame_count == 5

    def test_black_screen_triggers(self, sample_black_screen_state):
        detector = SoftLockDetector(
            stagnation_threshold=999,
            black_screen_threshold=3,
            mode_stuck_threshold=999,
        )

        anomaly = None
        for i in range(3):
            anomaly = detector.update(replace(sample_black_screen_state, timestamp=2000.0 + i))

        assert anomaly is not None
        assert anomaly.type == "black_screen"
        assert anomaly.severity == "critical"
        assert anomaly.frame_count == 3

    def test_stagnation_requires_playable_window(self, sample_overworld_state):
        detector = SoftLockDetector(
            stagnation_threshold=5,
            black_screen_threshold=999,
            mode_stuck_threshold=999,
        )

        anomaly = None
        for i in range(4):
            anomaly = detector.update(
                replace(sample_overworld_state, timestamp=3000.0 + i, mode=0x09, link_state=0x01)
            )
        # One non-playable sample in the window should suppress stagnation.
        anomaly = detector.update(
            replace(sample_overworld_state, timestamp=3004.0, mode=0x00, link_state=0x01)
        )

        assert anomaly is None

    def test_mode_stuck_triggers_for_non_playable_modes(self, sample_overworld_state):
        detector = SoftLockDetector(
            stagnation_threshold=999,
            black_screen_threshold=999,
            mode_stuck_threshold=4,
        )

        anomaly = None
        for i in range(4):
            anomaly = detector.update(replace(sample_overworld_state, timestamp=4000.0 + i, mode=0x14))

        assert anomaly is not None
        assert anomaly.type == "mode_stuck"
        assert anomaly.severity == "error"
        assert anomaly.frame_count == 4

    def test_mode_stuck_excludes_playable_modes(self, sample_overworld_state):
        detector = SoftLockDetector(
            stagnation_threshold=999,
            black_screen_threshold=999,
            mode_stuck_threshold=4,
        )

        # Keep mode constant but vary position to avoid any other detector.
        anomaly = None
        for i in range(4):
            anomaly = detector.update(replace(sample_overworld_state, timestamp=5000.0 + i, link_x=384 + i, mode=0x09))

        assert anomaly is None
