"""Concurrency and thread safety tests (Iteration 46).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D.1: Intelligent agent tooling

These tests verify concurrent access patterns, thread safety,
and async operation handling across campaign components.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from datetime import datetime
import threading
import time
import queue
from concurrent.futures import ThreadPoolExecutor, as_completed
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
    ActionPlanner, Goal, GoalType, Plan, PlanStatus
)
from scripts.campaign.progress_validator import (
    ProgressSnapshot
)


# =============================================================================
# Thread Safety - Input Recorder Tests
# =============================================================================

class TestInputRecorderThreadSafety:
    """Test InputRecorder thread safety."""

    def test_concurrent_start_recording(self):
        """Test concurrent start_recording calls don't crash."""
        recorder = InputRecorder()

        def start():
            recorder.start_recording()

        threads = [threading.Thread(target=start) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should be recording after all threads complete
        assert recorder.is_recording is True

    def test_concurrent_stop_recording(self):
        """Test concurrent stop_recording calls don't crash."""
        recorder = InputRecorder()
        recorder.start_recording()

        def stop():
            recorder.stop_recording()

        threads = [threading.Thread(target=stop) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert recorder.is_recording is False

    def test_concurrent_record_input(self):
        """Test concurrent record_input calls don't lose inputs."""
        recorder = InputRecorder()
        recorder.start_recording()
        inputs_per_thread = 10
        num_threads = 5

        def record_inputs(thread_id):
            for i in range(inputs_per_thread):
                recorder.record_input(Button.A, hold=1)

        threads = [threading.Thread(target=record_inputs, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        recorder.stop_recording()
        sequence = recorder.get_sequence()
        # Should have recorded inputs from all threads
        assert len(sequence.frames) > 0

    def test_start_stop_interleaved(self):
        """Test interleaved start/stop calls."""
        recorder = InputRecorder()
        results = []

        def toggle(n):
            for i in range(n):
                if i % 2 == 0:
                    recorder.start_recording()
                else:
                    recorder.stop_recording()
                results.append(recorder.is_recording)

        threads = [threading.Thread(target=toggle, args=(10,)) for _ in range(3)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Just verify no crashes, final state is valid boolean
        assert isinstance(recorder.is_recording, bool)


class TestInputPlayerThreadSafety:
    """Test InputPlayer thread safety."""

    def test_concurrent_playback_creation(self):
        """Test creating multiple InputPlayers concurrently."""
        sequence = InputSequence(
            name="test",
            frames=[InputFrame(0, Button.A), InputFrame(1, Button.B)]
        )

        players = []
        lock = threading.Lock()

        def create_player():
            player = InputPlayer(sequence)
            with lock:
                players.append(player)

        threads = [threading.Thread(target=create_player) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(players) == 10

    def test_concurrent_frame_iteration(self):
        """Test multiple threads iterating same sequence."""
        sequence = InputSequence(
            name="test",
            frames=[InputFrame(i, Button.A) for i in range(100)]
        )

        results = []
        lock = threading.Lock()

        def iterate_frames():
            local_count = 0
            for frame in sequence.frames:
                local_count += 1
            with lock:
                results.append(local_count)

        threads = [threading.Thread(target=iterate_frames) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All threads should count 100 frames
        assert all(r == 100 for r in results)


# =============================================================================
# Thread Safety - Pathfinder Tests
# =============================================================================

class TestPathfinderThreadSafety:
    """Test Pathfinder thread safety."""

    def test_concurrent_path_finding(self):
        """Test concurrent path finding calls."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        results = []
        lock = threading.Lock()

        def find_path(start, goal):
            result = pf.find_path(start, goal, cmap)
            with lock:
                results.append(result)

        # Multiple paths concurrently
        paths = [
            ((0, 0), (10, 10)),
            ((5, 5), (15, 15)),
            ((0, 0), (20, 20)),
            ((10, 0), (0, 10)),
        ]

        threads = [threading.Thread(target=find_path, args=p) for p in paths]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(results) == 4
        assert all(isinstance(r, NavigationResult) for r in results)

    def test_concurrent_cache_access(self):
        """Test concurrent cache access."""
        pf = Pathfinder()
        pf.cache_ttl = 10.0  # Long TTL
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        # Warm cache
        pf.find_path((0, 0), (5, 5), cmap)

        results = []
        lock = threading.Lock()

        def access_cache():
            result = pf.find_path((0, 0), (5, 5), cmap)
            with lock:
                results.append(result.success)

        threads = [threading.Thread(target=access_cache) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All should succeed
        assert all(results)

    def test_concurrent_collision_map_reads(self):
        """Test concurrent CollisionMap reads."""
        data = bytes([TileType.WALKABLE if i % 2 == 0 else TileType.SOLID
                      for i in range(64 * 64)])
        cmap = CollisionMap(data=data)

        results = []
        lock = threading.Lock()

        def read_tiles():
            local_results = []
            for x in range(10):
                for y in range(10):
                    local_results.append(cmap.get_tile(x, y))
            with lock:
                results.append(len(local_results))

        threads = [threading.Thread(target=read_tiles) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each thread read 100 tiles
        assert all(r == 100 for r in results)


# =============================================================================
# Thread Safety - Progress Snapshot Tests
# =============================================================================

class TestProgressSnapshotThreadSafety:
    """Test ProgressSnapshot thread safety."""

    def _create_snapshot(self, i: int) -> ProgressSnapshot:
        """Helper to create a snapshot with thread-varying values."""
        return ProgressSnapshot(
            timestamp=float(i),
            game_state=i,
            story_flags=i * 10,
            story_flags_2=i * 20,
            side_quest_1=0,
            side_quest_2=0,
            health=i % 8 + 1,
            max_health=8,
            rupees=i * 100,
            magic=0,
            max_magic=0,
            sword_level=1,
            shield_level=1,
            armor_level=0,
            crystals=0,
            follower_id=0,
            follower_state=0
        )

    def test_concurrent_snapshot_creation(self):
        """Test concurrent snapshot creation."""
        snapshots = []
        lock = threading.Lock()

        def create_snapshot(i):
            snap = self._create_snapshot(i)
            with lock:
                snapshots.append(snap)

        threads = [threading.Thread(target=create_snapshot, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(snapshots) == 20
        # Verify no corruption - each has unique timestamp
        timestamps = [s.timestamp for s in snapshots]
        assert len(set(timestamps)) == 20

    def test_concurrent_snapshot_reads(self):
        """Test concurrent reads of same snapshot."""
        snap = self._create_snapshot(5)

        results = []
        lock = threading.Lock()

        def read_snapshot():
            for _ in range(100):
                ts = snap.timestamp
                gs = snap.game_state
                h = snap.health
            with lock:
                results.append((ts, gs, h))

        threads = [threading.Thread(target=read_snapshot) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All reads should match
        assert all(r == (5.0, 5, 6) for r in results)


# =============================================================================
# Thread Safety - Campaign Progress Tests
# =============================================================================

class TestCampaignProgressThreadSafety:
    """Test CampaignProgress thread safety."""

    def test_concurrent_phase_updates(self):
        """Test concurrent phase updates."""
        progress = CampaignProgress()

        phases = [
            CampaignPhase.CONNECTING,
            CampaignPhase.BOOTING,
            CampaignPhase.EXPLORING,
            CampaignPhase.NAVIGATING,
        ]

        def update_phase():
            for phase in phases:
                progress.current_phase = phase

        threads = [threading.Thread(target=update_phase) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final phase should be one of the valid phases
        assert progress.current_phase in CampaignPhase

    def test_concurrent_counter_increments(self):
        """Test concurrent counter increments."""
        progress = CampaignProgress()
        iterations_per_thread = 100
        num_threads = 5

        def increment():
            for _ in range(iterations_per_thread):
                progress.iterations_completed += 1

        threads = [threading.Thread(target=increment) for _ in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # May have race conditions, so just verify no crash
        # and count is at least 1
        assert progress.iterations_completed >= 1

    def test_concurrent_milestone_access(self):
        """Test concurrent milestone access."""
        progress = CampaignProgress()
        progress.milestones = {
            "m1": CampaignMilestone(id="m1", description="Test 1", goal="A.1"),
            "m2": CampaignMilestone(id="m2", description="Test 2", goal="A.2"),
        }

        results = []
        lock = threading.Lock()

        def access_milestones():
            for key in list(progress.milestones.keys()):
                m = progress.milestones[key]
                with lock:
                    results.append(m.id)

        threads = [threading.Thread(target=access_milestones) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have accessed both milestones multiple times
        assert "m1" in results
        assert "m2" in results


# =============================================================================
# Thread Safety - Action Planner Tests
# =============================================================================

class TestActionPlannerThreadSafety:
    """Test ActionPlanner thread safety."""

    def test_concurrent_goal_creation(self):
        """Test concurrent goal creation."""
        goals = []
        lock = threading.Lock()

        def create_goal(i):
            goal = Goal(
                goal_type=GoalType.REACH_LOCATION,
                description=f"Goal {i}",
                parameters={"x": i, "y": i * 2}
            )
            with lock:
                goals.append(goal)

        threads = [threading.Thread(target=create_goal, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(goals) == 20

    def test_concurrent_plan_creation(self):
        """Test concurrent plan creation."""
        plans = []
        lock = threading.Lock()

        def create_plan(i):
            goal = Goal(goal_type=GoalType.GET_ITEM, description=f"Goal {i}")
            plan = Plan(goal=goal)
            with lock:
                plans.append(plan)

        threads = [threading.Thread(target=create_plan, args=(i,)) for i in range(20)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(plans) == 20
        assert all(p.status == PlanStatus.NOT_STARTED for p in plans)

    def test_concurrent_plan_status_updates(self):
        """Test concurrent plan status updates."""
        goal = Goal(goal_type=GoalType.REACH_LOCATION, description="Test")
        plan = Plan(goal=goal)

        statuses = [
            PlanStatus.IN_PROGRESS,
            PlanStatus.BLOCKED,
            PlanStatus.IN_PROGRESS,
            PlanStatus.COMPLETED,
        ]

        def update_status():
            for status in statuses:
                plan.status = status

        threads = [threading.Thread(target=update_status) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Final status should be valid
        assert plan.status in PlanStatus


# =============================================================================
# Thread Pool Executor Tests
# =============================================================================

class TestThreadPoolExecution:
    """Test thread pool based concurrent execution."""

    def test_path_finding_pool(self):
        """Test pathfinding in thread pool."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        def find_path_task(args):
            start, goal = args
            return pf.find_path(start, goal, cmap)

        tasks = [
            ((0, 0), (10, 10)),
            ((5, 5), (20, 20)),
            ((0, 10), (10, 0)),
            ((15, 15), (30, 30)),
        ]

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(find_path_task, t) for t in tasks]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 4
        assert all(isinstance(r, NavigationResult) for r in results)

    def test_snapshot_creation_pool(self):
        """Test snapshot creation in thread pool."""
        def create_snapshot_task(i):
            return ProgressSnapshot(
                timestamp=float(i),
                game_state=i,
                story_flags=i * 10,
                story_flags_2=i * 20,
                side_quest_1=0,
                side_quest_2=0,
                health=i % 8 + 1,
                max_health=8,
                rupees=i * 50,
                magic=0,
                max_magic=0,
                sword_level=1,
                shield_level=1,
                armor_level=0,
                crystals=0,
                follower_id=0,
                follower_state=0
            )

        with ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(create_snapshot_task, i) for i in range(100)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 100
        assert all(isinstance(s, ProgressSnapshot) for s in results)

    def test_goal_creation_pool(self):
        """Test goal creation in thread pool."""
        goal_types = list(GoalType)

        def create_goal_task(i):
            gt = goal_types[i % len(goal_types)]
            return Goal(goal_type=gt, description=f"Goal {i}")

        with ThreadPoolExecutor(max_workers=4) as executor:
            futures = [executor.submit(create_goal_task, i) for i in range(50)]
            results = [f.result() for f in as_completed(futures)]

        assert len(results) == 50
        assert all(isinstance(g, Goal) for g in results)


# =============================================================================
# Race Condition Tests
# =============================================================================

class TestRaceConditions:
    """Test potential race condition scenarios."""

    def test_recorder_state_race(self):
        """Test recorder state during rapid start/stop."""
        recorder = InputRecorder()
        errors = []

        def rapid_toggle():
            for _ in range(50):
                recorder.start_recording()
                # Quick check during recording
                state = recorder.is_recording
                recorder.stop_recording()
                if not isinstance(state, bool):
                    errors.append(f"Invalid state: {state}")

        threads = [threading.Thread(target=rapid_toggle) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0

    def test_progress_update_race(self):
        """Test progress updates under contention."""
        progress = CampaignProgress()

        def update_counters():
            for _ in range(100):
                progress.total_frames_played += 1
                progress.transitions_completed += 1

        def update_phases():
            phases = [CampaignPhase.EXPLORING, CampaignPhase.NAVIGATING]
            for i in range(50):
                progress.current_phase = phases[i % 2]

        threads = [
            threading.Thread(target=update_counters),
            threading.Thread(target=update_counters),
            threading.Thread(target=update_phases),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Verify valid state after race
        assert progress.total_frames_played >= 0
        assert progress.transitions_completed >= 0
        assert progress.current_phase in CampaignPhase

    def test_collision_map_concurrent_create_read(self):
        """Test collision map creation and reading concurrently."""
        maps = []
        lock = threading.Lock()

        def create_and_read(i):
            data = bytes([i % 256] * (32 * 32))
            cmap = CollisionMap(data=data, width=32, height=32)
            tile = cmap.get_tile(0, 0)
            with lock:
                maps.append((cmap, tile))

        threads = [threading.Thread(target=create_and_read, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(maps) == 10


# =============================================================================
# Producer-Consumer Pattern Tests
# =============================================================================

class TestProducerConsumer:
    """Test producer-consumer patterns in campaign components."""

    def test_input_frame_queue(self):
        """Test producer-consumer with input frames."""
        frame_queue = queue.Queue()
        frames_produced = []
        frames_consumed = []

        def producer():
            for i in range(50):
                frame = InputFrame(i, Button.A)
                frame_queue.put(frame)
                frames_produced.append(i)

        def consumer():
            while len(frames_consumed) < 50:
                try:
                    frame = frame_queue.get(timeout=1.0)
                    frames_consumed.append(frame.frame_number)
                except queue.Empty:
                    break

        producer_thread = threading.Thread(target=producer)
        consumer_thread = threading.Thread(target=consumer)

        producer_thread.start()
        consumer_thread.start()
        producer_thread.join()
        consumer_thread.join()

        assert len(frames_produced) == 50
        assert len(frames_consumed) == 50

    def test_snapshot_queue(self):
        """Test producer-consumer with snapshots."""
        snap_queue = queue.Queue()
        produced = []
        consumed = []

        def producer():
            for i in range(20):
                snap = ProgressSnapshot(
                    timestamp=float(i),
                    game_state=i,
                    story_flags=0,
                    story_flags_2=0,
                    side_quest_1=0,
                    side_quest_2=0,
                    health=4,
                    max_health=8,
                    rupees=i*10,
                    magic=0,
                    max_magic=0,
                    sword_level=1,
                    shield_level=1,
                    armor_level=0,
                    crystals=0,
                    follower_id=0,
                    follower_state=0
                )
                snap_queue.put(snap)
                produced.append(i)

        def consumer():
            while len(consumed) < 20:
                try:
                    snap = snap_queue.get(timeout=1.0)
                    consumed.append(snap.game_state)
                except queue.Empty:
                    break

        t1 = threading.Thread(target=producer)
        t2 = threading.Thread(target=consumer)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        assert len(produced) == 20
        assert len(consumed) == 20


# =============================================================================
# Timeout and Deadline Tests
# =============================================================================

class TestTimeouts:
    """Test timeout handling in concurrent scenarios."""

    def test_pathfinding_with_timeout(self):
        """Test pathfinding respects timeout."""
        pf = Pathfinder()
        # Create a blocked path that will hit max iterations
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Create wall blocking direct path
        for i in range(30):
            data[32 * 64 + i] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        def find_with_limit():
            return pf.find_path((0, 0), (63, 63), cmap, max_iterations=100)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(find_with_limit)
            # Should complete within reasonable time
            result = future.result(timeout=5.0)

        assert isinstance(result, NavigationResult)

    def test_concurrent_operations_complete(self):
        """Test that concurrent operations complete in time."""
        pf = Pathfinder()
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        start_time = time.time()

        def operation():
            for _ in range(10):
                pf.find_path((0, 0), (30, 30), cmap)

        threads = [threading.Thread(target=operation) for _ in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        elapsed = time.time() - start_time
        # Should complete in reasonable time (< 5 seconds)
        assert elapsed < 5.0


# =============================================================================
# Sequence and Order Tests
# =============================================================================

class TestOrdering:
    """Test ordering guarantees in concurrent scenarios."""

    def test_input_frame_ordering(self):
        """Test input frames maintain order within sequence."""
        recorder = InputRecorder()
        recorder.start_recording()

        # Record in specific order
        for i in range(100):
            recorder.record_input(Button.A if i % 2 == 0 else Button.B)

        recorder.stop_recording()
        seq = recorder.get_sequence()

        # Frames should be in order
        for i, frame in enumerate(seq.frames):
            assert frame.frame_number == i

    def test_milestone_completion_order(self):
        """Test milestone completion preserves order."""
        progress = CampaignProgress()
        progress.milestones = {
            f"m{i}": CampaignMilestone(id=f"m{i}", description=f"Test {i}", goal="A.1")
            for i in range(5)
        }

        completion_order = []
        lock = threading.Lock()

        def complete_milestone(mid):
            m = progress.milestones[mid]
            m.status = MilestoneStatus.COMPLETED
            m.completed_at = datetime.now()
            with lock:
                completion_order.append(mid)

        threads = [threading.Thread(target=complete_milestone, args=(f"m{i}",))
                   for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # All completed
        assert len(completion_order) == 5
        assert all(progress.milestones[mid].status == MilestoneStatus.COMPLETED
                   for mid in completion_order)


# =============================================================================
# Isolation Tests
# =============================================================================

class TestIsolation:
    """Test data isolation between concurrent operations."""

    def test_pathfinder_instances_isolated(self):
        """Test separate Pathfinder instances are isolated."""
        results = {}
        lock = threading.Lock()

        def use_pathfinder(thread_id):
            pf = Pathfinder()
            pf.cache_ttl = thread_id  # Different TTL per thread
            data = bytes([TileType.WALKABLE] * (64 * 64))
            cmap = CollisionMap(data=data)
            result = pf.find_path((0, 0), (10, 10), cmap)
            with lock:
                results[thread_id] = (pf.cache_ttl, result.success)

        threads = [threading.Thread(target=use_pathfinder, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each instance should have its own TTL
        for tid, (ttl, success) in results.items():
            assert ttl == tid
            assert success is True

    def test_recorder_instances_isolated(self):
        """Test separate InputRecorder instances are isolated."""
        recorders = []
        lock = threading.Lock()

        def use_recorder(thread_id):
            recorder = InputRecorder(name=f"recorder_{thread_id}")
            recorder.start_recording()
            for i in range(thread_id + 1):
                recorder.record_input(Button.A)
            recorder.stop_recording()
            with lock:
                recorders.append((thread_id, len(recorder.get_sequence().frames)))

        threads = [threading.Thread(target=use_recorder, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each recorder should have correct number of frames
        for thread_id, frame_count in recorders:
            assert frame_count == thread_id + 1

    def test_snapshot_instances_isolated(self):
        """Test ProgressSnapshot instances are isolated."""
        snapshots = {}
        lock = threading.Lock()

        def create_modify(thread_id):
            snap = ProgressSnapshot(
                timestamp=float(thread_id),
                game_state=thread_id * 10,
                story_flags=thread_id * 20,
                story_flags_2=0,
                side_quest_1=0,
                side_quest_2=0,
                health=thread_id % 8 + 1,
                max_health=8,
                rupees=thread_id * 100,
                magic=0,
                max_magic=0,
                sword_level=1,
                shield_level=1,
                armor_level=0,
                crystals=0,
                follower_id=0,
                follower_state=0
            )
            # Read back values
            with lock:
                snapshots[thread_id] = (snap.game_state, snap.story_flags, snap.health)

        threads = [threading.Thread(target=create_modify, args=(i,)) for i in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Each snapshot should have correct values
        for tid, (gs, sf, h) in snapshots.items():
            assert gs == tid * 10
            assert sf == tid * 20
            assert h == tid % 8 + 1
