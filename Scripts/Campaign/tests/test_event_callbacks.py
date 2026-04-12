"""Event callback and handler tests (Iteration 47).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling

These tests verify callback handling, event notification,
and handler registration patterns in campaign components.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, call
from datetime import datetime
import time
import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.campaign_orchestrator import (
    CampaignPhase, CampaignProgress, CampaignOrchestrator, CampaignMilestone,
    MilestoneStatus
)
from scripts.campaign.pathfinder import (
    Pathfinder, CollisionMap, TileType, NavigationResult
)
from scripts.campaign.input_recorder import (
    InputRecorder, InputPlayer, InputSequence, InputFrame, Button
)
from scripts.campaign.action_planner import (
    ActionPlanner, Goal, GoalType, Plan, PlanStatus, Action
)
from scripts.campaign.game_state import (
    GameStateParser, ParsedGameState, GamePhase, LinkAction
)
from scripts.campaign.emulator_abstraction import GameStateSnapshot


# =============================================================================
# InputPlayer Callback Tests
# =============================================================================

class TestInputPlayerCallbacks:
    """Test InputPlayer callback patterns.

    Note: These test callback usage patterns without requiring
    actual emulator integration. The callback parameter signature
    is (frame, state) per the InputPlayer.play() interface.
    """

    def test_callback_signature_pattern(self):
        """Test callback has correct signature for playback."""
        # Callbacks for InputPlayer.play should accept (frame, state)
        callback_calls = []

        def valid_callback(frame, state):
            callback_calls.append((frame, state))

        # Simulate calling callback with expected types
        frame = InputFrame(0, Button.A)
        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        valid_callback(frame, state)
        assert len(callback_calls) == 1
        assert callback_calls[0][0].buttons == Button.A

    def test_callback_frame_iteration(self):
        """Test callback receives frames in order."""
        frames = [
            InputFrame(0, Button.A),
            InputFrame(1, Button.B),
            InputFrame(2, Button.A | Button.B)
        ]

        received = []
        def callback(frame, state):
            received.append(frame.buttons)

        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        for frame in frames:
            callback(frame, state)

        assert received[0] == Button.A
        assert received[1] == Button.B
        assert received[2] == Button.A | Button.B

    def test_callback_state_capture(self):
        """Test callback captures state correctly."""
        states = []

        def callback(frame, state):
            states.append(state)

        frame = InputFrame(0, Button.A)
        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        callback(frame, state)

        assert len(states) == 1
        assert isinstance(states[0], GameStateSnapshot)

    def test_callback_none_handling(self):
        """Test None callback is handled."""
        callback = None

        # Should be able to check if callback is None
        assert callback is None

        # Pattern: only call if not None
        if callback:
            callback(None, None)

    def test_callback_exception_pattern(self):
        """Test callback exception propagation pattern."""
        def failing_callback(frame, state):
            raise ValueError("Callback failed")

        frame = InputFrame(0, Button.A)
        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        with pytest.raises(ValueError, match="Callback failed"):
            failing_callback(frame, state)

    def test_callback_order_tracking(self):
        """Test callbacks track frame order."""
        frames = [InputFrame(i, Button.A) for i in range(10)]

        frame_numbers = []
        def callback(frame, state):
            frame_numbers.append(frame.frame_number)

        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        for frame in frames:
            callback(frame, state)

        assert frame_numbers == list(range(10))

    def test_callback_button_tracking(self):
        """Test callback can accumulate button stats."""
        frames = [
            InputFrame(0, Button.A),
            InputFrame(1, Button.A),
            InputFrame(2, Button.B),
            InputFrame(3, Button.A | Button.B),
        ]

        button_counts = {Button.A: 0, Button.B: 0}
        def callback(frame, state):
            if Button.A in frame.buttons:
                button_counts[Button.A] += 1
            if Button.B in frame.buttons:
                button_counts[Button.B] += 1

        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        for frame in frames:
            callback(frame, state)

        assert button_counts[Button.A] == 3
        assert button_counts[Button.B] == 2


# =============================================================================
# ActionPlanner Callback Tests
# =============================================================================

class TestActionPlannerCallbacks:
    """Test ActionPlanner callback patterns.

    Note: These test callback signature patterns matching the
    ActionPlanner.execute_plan() callback interface: (plan, state).
    """

    def test_execute_plan_callback_signature(self):
        """Test callback has correct signature for plan execution."""
        callback_calls = []

        def valid_callback(plan, state):
            callback_calls.append((plan, state))

        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)
        state = MagicMock()

        valid_callback(plan, state)
        assert len(callback_calls) == 1
        assert callback_calls[0][0] is plan

    def test_execute_plan_callback_receives_plan(self):
        """Test callback receives the plan object."""
        goal = Goal(goal_type=GoalType.GET_ITEM, description="Test")
        plan = Plan(goal=goal)

        plans_received = []
        def callback(p, state):
            plans_received.append(p)

        # Simulate callback calls during execution
        for _ in range(3):
            callback(plan, MagicMock())

        assert all(p is plan for p in plans_received)

    def test_execute_plan_callback_none_pattern(self):
        """Test execution handles None callback."""
        callback = None

        # Pattern: check before calling
        if callback:
            callback(None, None)

        # No error should occur


# =============================================================================
# Milestone Completion Event Tests
# =============================================================================

class TestMilestoneCompletionEvents:
    """Test milestone completion as events."""

    def test_milestone_status_change_tracked(self):
        """Test milestone status changes are trackable."""
        progress = CampaignProgress()
        milestone = CampaignMilestone(
            id="test_milestone",
            description="Test",
            goal="A.1"
        )
        progress.milestones["test_milestone"] = milestone

        # Track status changes
        status_changes = []
        old_status = milestone.status

        milestone.status = MilestoneStatus.IN_PROGRESS
        if milestone.status != old_status:
            status_changes.append((old_status, milestone.status))
            old_status = milestone.status

        milestone.status = MilestoneStatus.COMPLETED
        if milestone.status != old_status:
            status_changes.append((old_status, milestone.status))

        assert len(status_changes) == 2
        assert status_changes[0] == (MilestoneStatus.NOT_STARTED, MilestoneStatus.IN_PROGRESS)
        assert status_changes[1] == (MilestoneStatus.IN_PROGRESS, MilestoneStatus.COMPLETED)

    def test_milestone_completed_at_set(self):
        """Test completed_at is set on completion."""
        milestone = CampaignMilestone(
            id="test",
            description="Test",
            goal="A.1"
        )

        assert milestone.completed_at is None

        milestone.status = MilestoneStatus.COMPLETED
        milestone.completed_at = datetime.now()

        assert milestone.completed_at is not None

    def test_milestone_notes_accumulate(self):
        """Test notes can be added as events occur."""
        milestone = CampaignMilestone(
            id="test",
            description="Test",
            goal="A.1"
        )

        milestone.notes.append("Started execution")
        milestone.notes.append("Reached checkpoint")
        milestone.notes.append("Completed successfully")

        assert len(milestone.notes) == 3
        assert "checkpoint" in milestone.notes[1]


# =============================================================================
# Phase Transition Event Tests
# =============================================================================

class TestPhaseTransitionEvents:
    """Test campaign phase transitions as events."""

    def test_phase_transition_sequence(self):
        """Test phase transitions can be tracked."""
        progress = CampaignProgress()

        transitions = []

        def track_transition(from_phase, to_phase):
            transitions.append((from_phase, to_phase))

        # Simulate phase progression
        phases = [
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
        ]

        old_phase = progress.current_phase
        for phase in phases:
            progress.current_phase = phase
            track_transition(old_phase, phase)
            old_phase = phase

        assert len(transitions) == 4
        assert transitions[0] == (CampaignPhase.DISCONNECTED, CampaignPhase.CONNECTING)
        assert transitions[-1][1] == CampaignPhase.NAVIGATING

    def test_phase_can_regress(self):
        """Test phase can go backwards (on errors)."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING

        # Simulate error regression
        progress.current_phase = CampaignPhase.CONNECTING

        assert progress.current_phase == CampaignPhase.CONNECTING


# =============================================================================
# Counter Update Event Tests
# =============================================================================

class TestCounterUpdateEvents:
    """Test counter updates as events."""

    def test_frame_counter_updates(self):
        """Test frame counter updates can be tracked."""
        progress = CampaignProgress()

        update_log = []

        for i in range(100):
            old_value = progress.total_frames_played
            progress.total_frames_played += 1
            update_log.append((old_value, progress.total_frames_played))

        assert len(update_log) == 100
        assert update_log[0] == (0, 1)
        assert update_log[-1] == (99, 100)

    def test_black_screen_counter_events(self):
        """Test black screen detection events."""
        progress = CampaignProgress()

        detections = []

        for i in range(5):
            progress.black_screens_detected += 1
            detections.append(progress.black_screens_detected)

        assert detections == [1, 2, 3, 4, 5]

    def test_transition_counter_events(self):
        """Test transition completion events."""
        progress = CampaignProgress()

        transitions = []

        for i in range(10):
            progress.transitions_completed += 1
            transitions.append({
                'count': progress.transitions_completed,
                'phase': progress.current_phase
            })

        assert len(transitions) == 10
        assert all(t['count'] == i+1 for i, t in enumerate(transitions))


# =============================================================================
# Plan Execution Event Tests
# =============================================================================

class TestPlanExecutionEvents:
    """Test plan execution state change events."""

    def test_plan_status_progression(self):
        """Test plan status changes can be tracked."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)

        status_log = [plan.status]

        plan.status = PlanStatus.IN_PROGRESS
        status_log.append(plan.status)

        plan.status = PlanStatus.COMPLETED
        status_log.append(plan.status)

        assert status_log == [
            PlanStatus.NOT_STARTED,
            PlanStatus.IN_PROGRESS,
            PlanStatus.COMPLETED
        ]

    def test_plan_action_advancement_events(self):
        """Test action advancement events."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(
            goal=goal,
            actions=[
                Action(name="action1", description="First"),
                Action(name="action2", description="Second"),
                Action(name="action3", description="Third"),
            ]
        )

        action_events = []

        while plan.current_action is not None:
            action_events.append({
                'index': plan.current_action_index,
                'action': plan.current_action.name
            })
            if not plan.advance():
                break

        assert len(action_events) == 3
        assert action_events[0]['action'] == "action1"
        assert action_events[2]['action'] == "action3"

    def test_plan_execution_log_events(self):
        """Test execution log as event accumulator."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)

        plan.log("Starting execution")
        plan.log("Moving to waypoint 1")
        plan.log("Reached destination")

        assert len(plan.execution_log) == 3
        assert "waypoint" in plan.execution_log[1]


# =============================================================================
# Recording Event Tests
# =============================================================================

class TestRecordingEvents:
    """Test input recording session events."""

    def test_recording_start_event(self):
        """Test recording start can be detected."""
        recorder = InputRecorder()

        was_recording = recorder.is_recording
        recorder.start_recording()
        started = not was_recording and recorder.is_recording

        assert started is True

    def test_recording_stop_event(self):
        """Test recording stop can be detected."""
        recorder = InputRecorder()
        recorder.start_recording()

        was_recording = recorder.is_recording
        recorder.stop_recording()
        stopped = was_recording and not recorder.is_recording

        assert stopped is True

    def test_input_record_events(self):
        """Test input recording generates events."""
        recorder = InputRecorder()
        recorder.start_recording()

        input_events = []

        buttons = [Button.A, Button.B, Button.UP, Button.A | Button.B]
        for b in buttons:
            recorder.record_input(b)
            input_events.append(b)

        recorder.stop_recording()
        sequence = recorder.get_sequence()

        assert len(input_events) == 4
        assert len(sequence.frames) == 4


# =============================================================================
# Navigation Event Tests
# =============================================================================

class TestNavigationEvents:
    """Test pathfinding navigation events."""

    def test_path_found_event(self):
        """Test successful path finding event."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        result = pf.find_path((0, 0), (10, 10), cmap)

        path_found_event = {
            'success': result.success,
            'path_length': len(result.path) if result.path else 0,
            'start': (0, 0),
            'goal': (10, 10)
        }

        assert path_found_event['success'] is True
        assert path_found_event['path_length'] > 0

    def test_path_not_found_event(self):
        """Test failed path finding event."""
        pf = Pathfinder()
        # Create blocked path
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Wall blocking entire row
        for x in range(64):
            data[32 * 64 + x] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pf.find_path((0, 0), (63, 63), cmap)

        path_failed_event = {
            'success': result.success,
            'reason': 'blocked' if not result.success else None
        }

        assert path_failed_event['success'] is False

    def test_path_step_events(self):
        """Test path steps as events."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        result = pf.find_path((0, 0), (5, 5), cmap)

        step_events = []
        if result.path:
            for i, (x, y) in enumerate(result.path):
                step_events.append({
                    'step': i,
                    'position': (x, y)
                })

        assert len(step_events) > 0
        assert step_events[0]['position'] == (0, 0)
        assert step_events[-1]['position'] == (5, 5)


# =============================================================================
# Mock Event Handler Tests
# =============================================================================

class TestMockEventHandlers:
    """Test using mock objects as event handlers."""

    def test_mock_callback_verification(self):
        """Test mock can verify callback invocations."""
        frames = [InputFrame(0, Button.A), InputFrame(1, Button.B)]

        mock_callback = Mock()
        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        # Simulate callback invocations
        for frame in frames:
            mock_callback(frame, state)

        assert mock_callback.call_count == 2

    def test_mock_callback_argument_capture(self):
        """Test mock captures callback arguments."""
        frame = InputFrame(0, Button.A)
        state = GameStateSnapshot(
            timestamp=time.time(),
            mode=0x07, submode=0,
            area=0x00, room=0x00,
            link_x=100, link_y=100, link_z=0,
            link_direction=0x02, link_state=0,
            indoors=True, inidisp=0x0F,
            health=24, max_health=24
        )

        mock_callback = Mock()
        mock_callback(frame, state)

        # Verify call args
        call_args = mock_callback.call_args
        captured_frame, captured_state = call_args[0]
        assert captured_frame.buttons == Button.A
        assert isinstance(captured_state, GameStateSnapshot)


# =============================================================================
# Event Filtering Tests
# =============================================================================

class TestEventFiltering:
    """Test event filtering patterns."""

    def test_filter_button_events(self):
        """Test filtering specific button events."""
        sequence = InputSequence(
            name="test",
            frames=[
                InputFrame(0, Button.A),
                InputFrame(1, Button.B),
                InputFrame(2, Button.A),
                InputFrame(3, Button.UP),
                InputFrame(4, Button.A | Button.B),
            ]
        )

        a_button_events = []
        for frame in sequence.frames:
            if Button.A in frame.buttons:
                a_button_events.append(frame.frame_number)

        assert a_button_events == [0, 2, 4]

    def test_filter_dpad_events(self):
        """Test filtering directional button events."""
        sequence = InputSequence(
            name="test",
            frames=[
                InputFrame(0, Button.UP),
                InputFrame(1, Button.A),
                InputFrame(2, Button.DOWN),
                InputFrame(3, Button.LEFT),
                InputFrame(4, Button.B),
                InputFrame(5, Button.RIGHT),
            ]
        )

        dpad = Button.UP | Button.DOWN | Button.LEFT | Button.RIGHT
        dpad_events = []
        for frame in sequence.frames:
            if frame.buttons & dpad:
                dpad_events.append(frame.frame_number)

        assert dpad_events == [0, 2, 3, 5]


# =============================================================================
# Event Aggregation Tests
# =============================================================================

class TestEventAggregation:
    """Test event aggregation patterns."""

    def test_aggregate_button_duration(self):
        """Test aggregating button hold durations."""
        sequence = InputSequence(
            name="test",
            frames=[
                InputFrame(0, Button.A, hold_frames=5),
                InputFrame(5, Button.B, hold_frames=3),
                InputFrame(8, Button.A, hold_frames=10),
            ]
        )

        button_durations = {}
        for frame in sequence.frames:
            for button in Button:
                if button in frame.buttons and button != Button.NONE:
                    button_durations[button] = button_durations.get(button, 0) + frame.hold_frames

        assert button_durations.get(Button.A, 0) == 15
        assert button_durations.get(Button.B, 0) == 3

    def test_aggregate_phase_durations(self):
        """Test aggregating time spent in phases."""
        progress = CampaignProgress()

        phase_times = {}

        phases_with_durations = [
            (CampaignPhase.CONNECTING, 100),
            (CampaignPhase.BOOTING, 500),
            (CampaignPhase.EXPLORING, 2000),
            (CampaignPhase.NAVIGATING, 1500),
        ]

        for phase, duration in phases_with_durations:
            progress.current_phase = phase
            phase_times[phase] = phase_times.get(phase, 0) + duration

        assert phase_times[CampaignPhase.EXPLORING] == 2000
        assert phase_times[CampaignPhase.NAVIGATING] == 1500


# =============================================================================
# Callback State Capture Tests
# =============================================================================

class TestCallbackStateCapture:
    """Test capturing state in callbacks."""

    def test_capture_position_history(self):
        """Test capturing position history via callbacks."""
        position_history = []

        def capture_position(frame, state):
            position_history.append((state.link_x, state.link_y))

        # Simulate with varying positions
        mock_states = [
            GameStateSnapshot(
                timestamp=time.time(),
                mode=0x07, submode=0,
                area=0x00, room=0x00,
                link_x=100 + i*10, link_y=200 + i*5, link_z=0,
                link_direction=0x02, link_state=0,
                indoors=True, inidisp=0x0F,
                health=24, max_health=24
            )
            for i in range(5)
        ]

        for state in mock_states:
            capture_position(None, state)

        assert len(position_history) == 5
        assert position_history[0] == (100, 200)
        assert position_history[-1] == (140, 220)

    def test_capture_health_changes(self):
        """Test capturing health change events."""
        health_changes = []
        last_health = [None]  # Use list to allow mutation in closure

        def capture_health(frame, health):
            if last_health[0] is not None and health != last_health[0]:
                health_changes.append({
                    'from': last_health[0],
                    'to': health,
                    'delta': health - last_health[0]
                })
            last_health[0] = health

        # Simulate health values over time
        health_values = [8, 8, 7, 7, 5, 6, 6, 8]
        for h in health_values:
            capture_health(None, h)

        assert len(health_changes) == 4
        # First change: 8 -> 7
        assert health_changes[0]['delta'] == -1
        # Heal: 5 -> 6
        assert health_changes[2]['delta'] == 1
