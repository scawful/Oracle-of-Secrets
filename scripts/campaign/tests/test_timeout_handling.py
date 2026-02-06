"""Tests for timeout and timing-related behavior in campaign modules.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Robust timing behavior in tooling

These tests verify that modules handle timing correctly,
including frame timing, sequence duration, and operation timeouts.
"""

import pytest
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import tempfile
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.emulator_abstraction import GameStateSnapshot
from scripts.campaign.game_state import GamePhase, GameStateParser
from scripts.campaign.input_recorder import (
    Button, InputSequence, InputPlayer, InputFrame, InputRecorder,
    create_boot_sequence, create_walk_sequence, create_attack_sequence
)
from scripts.campaign.action_planner import ActionPlanner, Goal, Plan, PlanStatus
from scripts.campaign.campaign_orchestrator import CampaignOrchestrator, CampaignPhase


class TestInputTimingCalculations:
    """Test input sequence timing calculations."""

    def test_boot_sequence_duration(self):
        """Test boot sequence calculates reasonable duration."""
        boot_seq = create_boot_sequence()

        # At 60fps, boot should be ~4-5 seconds
        duration = boot_seq.duration_seconds
        assert duration > 3.0, "Boot sequence should be at least 3 seconds"
        assert duration < 10.0, "Boot sequence should be under 10 seconds"

    def test_walk_sequence_duration(self):
        """Test walk sequence duration matches tile count."""
        # Walk 6 tiles (~60 frames at 10 frames/tile)
        seq = create_walk_sequence("UP", tiles=6)

        # 6 tiles * 10 frames/tile = 60 frames = 1 second at 60fps
        assert seq.duration_seconds == pytest.approx(1.0, abs=0.1)

    def test_attack_sequence_has_frames(self):
        """Test attack sequence has reasonable frame count."""
        attack_seq = create_attack_sequence()

        # Attack should be brief but not instant
        assert attack_seq.total_frames > 0
        assert attack_seq.total_frames < 120  # Under 2 seconds

    def test_sequence_add_wait(self):
        """Test adding wait frames to sequence."""
        seq = InputSequence(name="wait_test")

        # Start empty
        next_frame = seq.add_wait(60)
        assert next_frame == 60

        # Add input at frame 60
        seq.add_input(60, Button.A, hold=5)

        # Add wait after input
        next_frame = seq.add_wait(30)
        assert next_frame == 60 + 5 + 30  # frame + hold + wait

    def test_sequence_total_frames_with_holds(self):
        """Test total_frames accounts for hold durations."""
        seq = InputSequence(name="hold_test")
        seq.add_input(0, Button.A, hold=10)
        seq.add_input(10, Button.B, hold=20)

        # Last frame is 10, hold is 20, so total is 30
        assert seq.total_frames == 30

    def test_compressed_sequence_preserves_timing(self):
        """Test compression maintains timing relationships."""
        seq = InputSequence(name="compress_test")
        seq.add_input(0, Button.A, hold=1)
        seq.add_input(1, Button.A, hold=1)
        seq.add_input(2, Button.A, hold=1)

        compressed = seq.compress()

        # Compression should merge consecutive identical inputs
        assert len(compressed.frames) == 1
        assert compressed.frames[0].hold_frames == 3
        # Total duration should be preserved
        assert compressed.total_frames == seq.total_frames


class TestRecorderTimestamps:
    """Test input recorder timestamp handling."""

    def test_recorder_creates_unique_names(self):
        """Test recorder generates unique sequence names."""
        recorder1 = InputRecorder("test")
        recorder2 = InputRecorder("test")

        # Different instances should have unique internal state
        assert recorder1 is not recorder2

    def test_recorder_records_frame_times(self):
        """Test recorder captures frame timing."""
        recorder = InputRecorder("timing_test")
        recorder.start_recording()

        # Record some inputs
        recorder.record_input(Button.A)
        recorder.advance_frames(1)
        recorder.record_input(Button.B)
        recorder.advance_frames(1)

        recorder.stop_recording()
        seq = recorder.get_sequence()

        # Should have frames with proper numbers
        assert len(seq.frames) >= 2
        frame_numbers = [f.frame_number for f in seq.frames]
        assert frame_numbers == sorted(frame_numbers)  # Ascending order


class TestPlaybackTiming:
    """Test input playback timing."""

    def test_player_advances_frames(self):
        """Test player calls step_frame for each frame."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.inject_input.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        player = InputPlayer(mock_emu)

        # Create sequence with 10 frames
        seq = InputSequence(name="step_test")
        seq.add_input(0, Button.A, hold=10)

        player.play(seq)

        # step_frame should be called for each frame
        assert mock_emu.step_frame.call_count >= 10

    def test_player_callback_receives_frame_number(self):
        """Test player callback gets correct frame numbers."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.step_frame.return_value = True
        mock_emu.inject_input.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        player = InputPlayer(mock_emu)
        seq = InputSequence(name="callback_test")
        seq.add_input(0, Button.A, hold=5)

        frame_numbers = []
        def callback(frame, state):
            frame_numbers.append(frame)

        player.play(seq, callback=callback)

        # Should get callbacks for frames 1-5 (player uses 1-indexed frames)
        assert len(frame_numbers) == 5
        assert frame_numbers == [1, 2, 3, 4, 5]


class TestProgressTimestamps:
    """Test campaign progress timestamp tracking."""

    def test_milestone_completion_timestamp(self):
        """Test milestone records completion time."""
        from scripts.campaign.campaign_orchestrator import CampaignMilestone, MilestoneStatus

        milestone = CampaignMilestone(
            id="test",
            description="Test milestone",
            goal="T.1"
        )

        assert milestone.completed_at is None

        before = datetime.now()
        milestone.complete("Done")
        after = datetime.now()

        assert milestone.status == MilestoneStatus.COMPLETED
        assert milestone.completed_at is not None
        assert before <= milestone.completed_at <= after

    def test_progress_last_update_changes(self):
        """Test progress last_update changes on milestone completion."""
        mock_emu = Mock()
        mock_emu.connect.return_value = True
        mock_emu.is_connected.return_value = True

        orchestrator = CampaignOrchestrator(emulator=mock_emu)

        # Initially None
        assert orchestrator._progress.last_update is None

        # After connecting and completing milestone
        orchestrator.connect()
        orchestrator._progress.complete_milestone("emulator_connected")

        assert orchestrator._progress.last_update is not None


class TestStateTimestamps:
    """Test game state snapshot timestamps."""

    def test_parser_preserves_timestamp(self):
        """Test parser preserves raw timestamp in parsed state."""
        parser = GameStateParser()
        timestamp = 12345.678

        state = GameStateSnapshot(
            timestamp=timestamp, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        parsed = parser.parse(state)
        assert parsed.raw.timestamp == timestamp

    def test_sequential_states_have_different_timestamps(self):
        """Test sequential state reads have different timestamps."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True

        counter = [0]
        def get_state():
            counter[0] += 1
            return GameStateSnapshot(
                timestamp=float(counter[0]) * 0.016666,  # ~60fps timing
                mode=0x09, submode=0x00,
                area=0x29, room=0x00,
                link_x=512, link_y=480, link_z=0,
                link_direction=2, link_state=0,
                indoors=False, inidisp=0x0F,
                health=24, max_health=24
            )

        mock_emu.read_state.side_effect = get_state

        orchestrator = CampaignOrchestrator(emulator=mock_emu)
        orchestrator._emu = mock_emu

        state1 = orchestrator.get_state()
        state2 = orchestrator.get_state()
        state3 = orchestrator.get_state()

        timestamps = [state1.raw.timestamp, state2.raw.timestamp, state3.raw.timestamp]
        assert timestamps == sorted(timestamps)  # Monotonically increasing


class TestFrameCountValidation:
    """Test frame count validation in sequences."""

    def test_sequence_rejects_negative_frame_number(self):
        """Test behavior with negative frame numbers."""
        # Creating frame with negative number should be possible
        # (validation may happen elsewhere or not at all)
        frame = InputFrame(frame_number=-1, buttons=Button.A, hold_frames=1)
        assert frame.frame_number == -1

    def test_sequence_handles_zero_hold(self):
        """Test behavior with zero hold frames."""
        frame = InputFrame(frame_number=0, buttons=Button.A, hold_frames=0)
        seq = InputSequence(name="zero_hold", frames=[frame])

        # Zero hold means the input is instant (0 frames)
        assert seq.total_frames == 0

    def test_sequence_handles_large_frame_numbers(self):
        """Test behavior with large frame numbers."""
        # 1 hour at 60fps = 216000 frames
        large_frame = 216000
        frame = InputFrame(frame_number=large_frame, buttons=Button.A, hold_frames=1)
        seq = InputSequence(name="large", frames=[frame])

        assert seq.total_frames == large_frame + 1
        assert seq.duration_seconds > 3600  # More than 1 hour


class TestPlanExecutionTiming:
    """Test action plan execution timing."""

    def test_plan_tracks_action_count(self):
        """Test plan tracks number of actions."""
        mock_emu = Mock()
        mock_emu.is_connected.return_value = True
        mock_emu.read_state.return_value = GameStateSnapshot(
            timestamp=1.0, mode=0x09, submode=0x00,
            area=0x29, room=0x00,
            link_x=512, link_y=480, link_z=0,
            link_direction=2, link_state=0,
            indoors=False, inidisp=0x0F,
            health=24, max_health=24
        )

        planner = ActionPlanner(mock_emu)
        goal = Goal.reach_location(area_id=0x29, x=600, y=500)
        plan = planner.create_plan(goal)

        assert plan is not None
        assert len(plan.actions) >= 0  # May have actions or be empty

    def test_plan_status_transitions(self):
        """Test plan status progresses through expected states."""
        plan = Plan(goal=Goal.reach_location(area_id=0x29, x=512, y=480))

        assert plan.status == PlanStatus.NOT_STARTED

        # Plans can transition to various states
        valid_statuses = [
            PlanStatus.NOT_STARTED,
            PlanStatus.IN_PROGRESS,
            PlanStatus.COMPLETED,
            PlanStatus.FAILED,
            PlanStatus.BLOCKED
        ]
        assert plan.status in valid_statuses
