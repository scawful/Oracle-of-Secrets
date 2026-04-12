"""Retry logic and recovery pattern tests (Iteration 48).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling

These tests verify retry mechanisms, backoff strategies,
recovery patterns, and error handling across campaign components.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
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
from scripts.campaign.emulator_abstraction import GameStateSnapshot


# =============================================================================
# Retry Count Tests
# =============================================================================

class TestRetryCount:
    """Test retry counting patterns."""

    def test_simple_retry_loop(self):
        """Test simple retry loop pattern."""
        max_retries = 3
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            attempt += 1
            # Simulate failure on first 2 attempts
            if attempt == 3:
                success = True

        assert attempt == 3
        assert success is True

    def test_retry_with_early_success(self):
        """Test retry exits early on success."""
        max_retries = 5
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            attempt += 1
            if attempt == 2:
                success = True

        assert attempt == 2
        assert success is True

    def test_retry_exhaustion(self):
        """Test retry exhausts all attempts."""
        max_retries = 3
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            attempt += 1
            # Never succeed
            success = False

        assert attempt == 3
        assert success is False

    def test_retry_zero_max(self):
        """Test zero max retries means no attempts."""
        max_retries = 0
        attempt = 0
        success = False

        while attempt < max_retries and not success:
            attempt += 1
            success = True

        assert attempt == 0
        assert success is False


# =============================================================================
# Backoff Strategy Tests
# =============================================================================

class TestBackoffStrategies:
    """Test backoff strategy patterns."""

    def test_constant_backoff(self):
        """Test constant backoff strategy."""
        delays = []
        constant_delay = 0.1

        for i in range(5):
            delays.append(constant_delay)

        assert all(d == 0.1 for d in delays)

    def test_linear_backoff(self):
        """Test linear backoff strategy."""
        delays = []
        base_delay = 0.1

        for i in range(5):
            delays.append(base_delay * (i + 1))

        expected = [0.1, 0.2, 0.3, 0.4, 0.5]
        for d, e in zip(delays, expected):
            assert abs(d - e) < 0.0001

    def test_exponential_backoff(self):
        """Test exponential backoff strategy."""
        delays = []
        base_delay = 0.1
        factor = 2

        for i in range(5):
            delays.append(base_delay * (factor ** i))

        assert delays == [0.1, 0.2, 0.4, 0.8, 1.6]

    def test_exponential_backoff_with_cap(self):
        """Test exponential backoff with maximum cap."""
        delays = []
        base_delay = 0.1
        factor = 2
        max_delay = 1.0

        for i in range(5):
            delay = base_delay * (factor ** i)
            delays.append(min(delay, max_delay))

        assert delays == [0.1, 0.2, 0.4, 0.8, 1.0]

    def test_jitter_backoff(self):
        """Test backoff with jitter variation."""
        import random
        random.seed(42)

        base_delays = [0.1] * 5
        jittered = []

        for d in base_delays:
            # Add up to 10% jitter
            jitter = random.uniform(0, d * 0.1)
            jittered.append(d + jitter)

        # All should be close to 0.1 but slightly different
        assert all(0.1 <= d <= 0.11 for d in jittered)
        assert len(set(jittered)) > 1  # Should have variation


# =============================================================================
# Connection Retry Tests
# =============================================================================

class TestConnectionRetry:
    """Test connection retry patterns."""

    def test_connection_retry_success(self):
        """Test connection succeeds after retries."""
        mock_emu = MagicMock()
        connect_attempts = [False, False, True]
        attempt_idx = [0]

        def mock_connect():
            result = connect_attempts[attempt_idx[0]]
            attempt_idx[0] += 1
            return result

        mock_emu.connect.side_effect = mock_connect

        # Retry loop
        connected = False
        for _ in range(3):
            if mock_emu.connect():
                connected = True
                break

        assert connected is True
        assert attempt_idx[0] == 3

    def test_connection_retry_failure(self):
        """Test connection fails after all retries."""
        mock_emu = MagicMock()
        mock_emu.connect.return_value = False

        connected = False
        attempts = 0
        for _ in range(3):
            attempts += 1
            if mock_emu.connect():
                connected = True
                break

        assert connected is False
        assert attempts == 3

    def test_connection_retry_with_exception(self):
        """Test connection handles exceptions."""
        mock_emu = MagicMock()
        call_count = [0]

        def flaky_connect():
            call_count[0] += 1
            if call_count[0] < 3:
                raise ConnectionError("Failed")
            return True

        mock_emu.connect.side_effect = flaky_connect

        connected = False
        for _ in range(3):
            try:
                if mock_emu.connect():
                    connected = True
                    break
            except ConnectionError:
                continue

        assert connected is True
        assert call_count[0] == 3


# =============================================================================
# State Recovery Tests
# =============================================================================

class TestStateRecovery:
    """Test state recovery patterns."""

    def test_progress_recovery_on_failure(self):
        """Test progress can be recovered on failure."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.EXPLORING
        progress.iterations_completed = 10

        # Save state before risky operation
        saved_phase = progress.current_phase
        saved_iterations = progress.iterations_completed

        # Simulate failure
        try:
            progress.current_phase = CampaignPhase.IN_DUNGEON
            raise RuntimeError("Operation failed")
        except RuntimeError:
            # Recover state
            progress.current_phase = saved_phase
            progress.iterations_completed = saved_iterations

        assert progress.current_phase == CampaignPhase.EXPLORING
        assert progress.iterations_completed == 10

    def test_milestone_rollback(self):
        """Test milestone can be rolled back."""
        milestone = CampaignMilestone(
            id="test",
            description="Test",
            goal="A.1"
        )
        milestone.status = MilestoneStatus.IN_PROGRESS

        # Save state
        saved_status = milestone.status

        # Attempt completion
        try:
            milestone.status = MilestoneStatus.COMPLETED
            raise RuntimeError("Completion failed")
        except RuntimeError:
            milestone.status = saved_status

        assert milestone.status == MilestoneStatus.IN_PROGRESS

    def test_plan_reset_on_failure(self):
        """Test plan can be reset on failure."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(
            goal=goal,
            actions=[
                Action(name="a1", description="Action 1"),
                Action(name="a2", description="Action 2"),
            ]
        )

        # Start execution
        plan.status = PlanStatus.IN_PROGRESS
        plan.current_action_index = 1

        # Simulate failure - reset plan
        def reset_plan(p: Plan):
            p.status = PlanStatus.NOT_STARTED
            p.current_action_index = 0
            p.execution_log.clear()

        reset_plan(plan)

        assert plan.status == PlanStatus.NOT_STARTED
        assert plan.current_action_index == 0


# =============================================================================
# Retry with Context Tests
# =============================================================================

class TestRetryWithContext:
    """Test retry patterns with context tracking."""

    def test_retry_tracks_attempts(self):
        """Test retry tracks attempt history."""
        attempts = []

        def operation(attempt_num):
            attempts.append({
                'attempt': attempt_num,
                'timestamp': time.time()
            })
            return attempt_num == 3  # Succeed on 3rd

        success = False
        for i in range(1, 4):
            success = operation(i)
            if success:
                break

        assert len(attempts) == 3
        assert all('attempt' in a and 'timestamp' in a for a in attempts)

    def test_retry_tracks_errors(self):
        """Test retry tracks error types."""
        errors = []
        error_sequence = [
            ConnectionError("Network error"),
            TimeoutError("Timed out"),
            None  # Success
        ]

        for i, error in enumerate(error_sequence):
            if error:
                errors.append({
                    'attempt': i + 1,
                    'error': type(error).__name__
                })
            else:
                break

        assert len(errors) == 2
        assert errors[0]['error'] == 'ConnectionError'
        assert errors[1]['error'] == 'TimeoutError'

    def test_retry_context_preserved(self):
        """Test context is preserved across retries."""
        context = {
            'start_time': time.time(),
            'operation': 'connect',
            'attempts': 0
        }

        for _ in range(3):
            context['attempts'] += 1
            # Simulate work

        assert context['attempts'] == 3
        assert context['operation'] == 'connect'
        assert 'start_time' in context


# =============================================================================
# Pathfinder Retry Tests
# =============================================================================

class TestPathfinderRetry:
    """Test pathfinder retry patterns."""

    def test_path_retry_different_start(self):
        """Test retrying path from different starting point."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        starts = [(0, 0), (5, 5), (10, 10)]
        goal = (30, 30)

        for start in starts:
            result = pf.find_path(start, goal, cmap)
            if result.success:
                break

        assert result.success is True

    def test_path_retry_with_constraints(self):
        """Test retrying path with different constraints."""
        pf = Pathfinder()
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Add water
        data[16] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))

        # Try without flippers first
        result = pf.find_path((0, 0), (32, 0), cmap, has_flippers=False)

        # If failed, try with flippers
        if not result.success:
            result = pf.find_path((0, 0), (32, 0), cmap, has_flippers=True)

        assert result.success is True

    def test_path_retry_reduced_iterations(self):
        """Test retrying with different iteration limits."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        iteration_limits = [100, 1000, 10000]

        for limit in iteration_limits:
            result = pf.find_path((0, 0), (30, 30), cmap, max_iterations=limit)
            if result.success:
                break

        assert result.success is True


# =============================================================================
# Recording Retry Tests
# =============================================================================

class TestRecordingRetry:
    """Test recording retry patterns."""

    def test_recording_restart_on_error(self):
        """Test recording can be restarted on error."""
        recorder = InputRecorder()

        for attempt in range(3):
            try:
                recorder.start_recording()
                if attempt < 2:
                    # Simulate error
                    recorder.stop_recording()
                    raise RuntimeError("Recording failed")
                else:
                    # Success on 3rd attempt
                    recorder.record_input(Button.A)
                    break
            except RuntimeError:
                continue

        recorder.stop_recording()
        seq = recorder.get_sequence()
        assert len(seq.frames) == 1

    def test_sequence_rebuild_on_corruption(self):
        """Test sequence can be rebuilt if corrupted."""
        original_frames = [
            InputFrame(0, Button.A),
            InputFrame(1, Button.B),
            InputFrame(2, Button.UP)
        ]

        # Create sequence
        seq = InputSequence(name="test", frames=original_frames.copy())

        # Simulate corruption (empty frames)
        corrupted = InputSequence(name="test", frames=[])

        # Rebuild from backup
        if len(corrupted.frames) == 0:
            rebuilt = InputSequence(name="test", frames=original_frames)
        else:
            rebuilt = corrupted

        assert len(rebuilt.frames) == 3


# =============================================================================
# Progress Validator Retry Tests
# =============================================================================

class TestValidatorRetry:
    """Test progress validator retry patterns."""

    def test_snapshot_retry_on_invalid_data(self):
        """Test snapshot capture retried on invalid data."""
        def create_snapshot(attempt):
            if attempt < 2:
                # Invalid data
                return None
            # Valid data on 3rd attempt
            return {
                'health': 24,
                'x': 100,
                'y': 200
            }

        snapshot = None
        for i in range(3):
            snapshot = create_snapshot(i)
            if snapshot is not None:
                break

        assert snapshot is not None
        assert snapshot['health'] == 24

    def test_validation_retry_on_failure(self):
        """Test validation retried on failure."""
        def validate(data, strict=True):
            if strict and data['health'] < 0:
                return False
            return True

        data = {'health': -1}

        # First try strict validation
        valid = validate(data, strict=True)

        # Retry with relaxed validation
        if not valid:
            valid = validate(data, strict=False)

        assert valid is True


# =============================================================================
# Transition Retry Tests
# =============================================================================

class TestTransitionRetry:
    """Test transition retry patterns."""

    def test_phase_transition_retry(self):
        """Test phase transition with retry."""
        progress = CampaignProgress()
        progress.current_phase = CampaignPhase.CONNECTING

        target_phase = CampaignPhase.EXPLORING
        transition_attempts = 0

        # Simulate transition that may fail
        while progress.current_phase != target_phase and transition_attempts < 3:
            transition_attempts += 1
            # Succeed on 3rd attempt
            if transition_attempts == 3:
                progress.current_phase = target_phase

        assert progress.current_phase == target_phase
        assert transition_attempts == 3

    def test_milestone_transition_retry(self):
        """Test milestone status transition with retry."""
        milestone = CampaignMilestone(
            id="test",
            description="Test",
            goal="A.1"
        )

        target_status = MilestoneStatus.COMPLETED
        attempts = 0

        while milestone.status != target_status and attempts < 3:
            attempts += 1
            try:
                if attempts < 3:
                    raise RuntimeError("Transition failed")
                milestone.status = target_status
            except RuntimeError:
                continue

        assert milestone.status == target_status


# =============================================================================
# Timeout Retry Tests
# =============================================================================

class TestTimeoutRetry:
    """Test timeout-based retry patterns."""

    def test_operation_timeout_retry(self):
        """Test operation retried after timeout."""
        start_time = time.time()
        timeout = 0.5
        operation_time = 0.1
        success = False

        while time.time() - start_time < timeout:
            time.sleep(operation_time)
            success = True
            break

        assert success is True
        assert time.time() - start_time < timeout

    def test_deadline_based_retry(self):
        """Test retry until deadline."""
        deadline = time.time() + 0.3
        attempts = 0
        success = False

        while time.time() < deadline and not success:
            attempts += 1
            time.sleep(0.1)
            if attempts == 2:
                success = True

        assert success is True
        assert attempts == 2


# =============================================================================
# Idempotency Tests
# =============================================================================

class TestIdempotency:
    """Test idempotent retry operations."""

    def test_recording_start_idempotent(self):
        """Test recording start is idempotent."""
        recorder = InputRecorder()

        # Multiple starts should be safe
        recorder.start_recording()
        recorder.start_recording()
        recorder.start_recording()

        assert recorder.is_recording is True

    def test_recording_stop_idempotent(self):
        """Test recording stop is idempotent."""
        recorder = InputRecorder()
        recorder.start_recording()

        # Multiple stops should be safe
        recorder.stop_recording()
        recorder.stop_recording()
        recorder.stop_recording()

        assert recorder.is_recording is False

    def test_phase_set_idempotent(self):
        """Test phase setting is idempotent."""
        progress = CampaignProgress()

        # Multiple sets to same phase should be safe
        progress.current_phase = CampaignPhase.EXPLORING
        progress.current_phase = CampaignPhase.EXPLORING
        progress.current_phase = CampaignPhase.EXPLORING

        assert progress.current_phase == CampaignPhase.EXPLORING


# =============================================================================
# Circuit Breaker Pattern Tests
# =============================================================================

class TestCircuitBreaker:
    """Test circuit breaker patterns."""

    def test_circuit_breaker_open_after_failures(self):
        """Test circuit opens after consecutive failures."""
        failure_threshold = 3
        consecutive_failures = 0
        circuit_open = False

        for i in range(5):
            try:
                raise RuntimeError("Failed")
            except RuntimeError:
                consecutive_failures += 1
                if consecutive_failures >= failure_threshold:
                    circuit_open = True
                    break

        assert circuit_open is True
        assert consecutive_failures == 3

    def test_circuit_breaker_reset_on_success(self):
        """Test circuit resets on success."""
        failure_threshold = 3
        consecutive_failures = 2  # Almost at threshold
        circuit_open = False

        # Successful operation resets counter
        success = True
        if success:
            consecutive_failures = 0

        # Next failure shouldn't open circuit
        consecutive_failures += 1
        circuit_open = consecutive_failures >= failure_threshold

        assert circuit_open is False
        assert consecutive_failures == 1

    def test_circuit_half_open_test(self):
        """Test circuit allows test request in half-open state."""
        circuit_state = "open"
        half_open_time = 0.1

        # Wait for half-open period
        time.sleep(half_open_time)

        # Transition to half-open
        circuit_state = "half-open"

        # Allow one test request
        test_allowed = circuit_state == "half-open"

        assert test_allowed is True


# =============================================================================
# Fallback Strategy Tests
# =============================================================================

class TestFallbackStrategy:
    """Test fallback strategy patterns."""

    def test_primary_fallback_pattern(self):
        """Test primary fails, fallback succeeds."""
        def primary():
            raise RuntimeError("Primary failed")

        def fallback():
            return "fallback_result"

        result = None
        try:
            result = primary()
        except RuntimeError:
            result = fallback()

        assert result == "fallback_result"

    def test_cascade_fallback(self):
        """Test cascading fallback chain."""
        def strategy_a():
            raise RuntimeError("A failed")

        def strategy_b():
            raise RuntimeError("B failed")

        def strategy_c():
            return "C worked"

        strategies = [strategy_a, strategy_b, strategy_c]
        result = None

        for strategy in strategies:
            try:
                result = strategy()
                break
            except RuntimeError:
                continue

        assert result == "C worked"

    def test_fallback_with_degraded_result(self):
        """Test fallback returns degraded result."""
        def full_operation():
            raise RuntimeError("Full failed")

        def degraded_operation():
            return {"status": "partial", "data": [1, 2]}

        try:
            result = full_operation()
        except RuntimeError:
            result = degraded_operation()

        assert result["status"] == "partial"


# =============================================================================
# Retry Decorator Pattern Tests
# =============================================================================

class TestRetryDecoratorPattern:
    """Test retry decorator-like patterns."""

    def test_retry_wrapper_function(self):
        """Test retry wrapper function."""
        def retry_wrapper(func, max_retries=3):
            for i in range(max_retries):
                try:
                    return func()
                except Exception:
                    if i == max_retries - 1:
                        raise
            return None

        call_count = [0]

        def flaky_operation():
            call_count[0] += 1
            if call_count[0] < 3:
                raise RuntimeError("Failed")
            return "success"

        result = retry_wrapper(flaky_operation)
        assert result == "success"
        assert call_count[0] == 3

    def test_retry_with_args(self):
        """Test retry wrapper with arguments."""
        def retry_wrapper(func, *args, max_retries=3, **kwargs):
            for i in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except Exception:
                    if i == max_retries - 1:
                        raise
            return None

        call_count = [0]

        def operation_with_args(x, y, multiplier=1):
            call_count[0] += 1
            if call_count[0] < 2:
                raise RuntimeError("Failed")
            return (x + y) * multiplier

        result = retry_wrapper(operation_with_args, 2, 3, multiplier=2)
        assert result == 10
        assert call_count[0] == 2


# =============================================================================
# Retry Metrics Tests
# =============================================================================

class TestRetryMetrics:
    """Test retry metrics collection."""

    def test_retry_success_rate(self):
        """Test calculating retry success rate."""
        total_operations = 10
        successful = 7

        success_rate = successful / total_operations
        assert success_rate == 0.7

    def test_average_retry_count(self):
        """Test calculating average retry count."""
        retry_counts = [1, 3, 2, 1, 5, 2]
        average = sum(retry_counts) / len(retry_counts)
        assert round(average, 2) == 2.33

    def test_retry_histogram(self):
        """Test retry count distribution."""
        retry_counts = [1, 1, 2, 2, 2, 3, 3, 3, 3, 5]
        histogram = {}

        for count in retry_counts:
            histogram[count] = histogram.get(count, 0) + 1

        assert histogram == {1: 2, 2: 3, 3: 4, 5: 1}
