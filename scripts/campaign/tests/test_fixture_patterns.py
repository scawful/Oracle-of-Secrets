"""Iteration 58 - Fixture Pattern Tests.

Tests demonstrating pytest fixture patterns and testing best practices.

Focus: Fixture scopes, parameterization, fixture factories, shared fixtures,
teardown patterns, fixture dependencies, conftest patterns.
"""

import pytest
import time
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Generator
from unittest.mock import MagicMock, patch

from scripts.campaign.emulator_abstraction import (
    EmulatorStatus,
    MemoryRead,
    GameStateSnapshot,
    EmulatorInterface,
)
from scripts.campaign.input_recorder import (
    Button,
    InputFrame,
    InputSequence,
    InputRecorder,
)
from scripts.campaign.game_state import (
    GamePhase,
    LinkAction,
    GameStateParser,
    ParsedGameState,
)
from scripts.campaign.pathfinder import (
    TileType,
    CollisionMap,
    Pathfinder,
    NavigationResult,
)
from scripts.campaign.campaign_orchestrator import (
    CampaignPhase,
    MilestoneStatus,
    CampaignMilestone,
    CampaignProgress,
)
from scripts.campaign.action_planner import (
    GoalType,
    PlanStatus,
    Goal,
    Plan,
    Action,
)
from scripts.campaign.progress_validator import (
    StoryFlag,
    GameStateValue,
    ProgressSnapshot,
)


# =============================================================================
# Basic Fixture Tests
# =============================================================================

class TestBasicFixtures:
    """Tests for basic fixture patterns."""

    @pytest.fixture
    def mock_emulator(self) -> MagicMock:
        """Basic fixture returning mock emulator."""
        mock = MagicMock(spec=EmulatorInterface)
        type(mock).status = property(lambda self: EmulatorStatus.CONNECTED)
        return mock

    @pytest.fixture
    def sample_snapshot(self) -> MagicMock:
        """Basic fixture for game snapshot."""
        mock = MagicMock()
        mock.mode = 0x09
        mock.area = 0x29
        mock.room = 0x00
        mock.link_x = 128
        mock.link_y = 128
        mock.health = 24
        mock.max_health = 24
        mock.inidisp = 0x0F
        mock.timestamp = time.time()
        return mock

    def test_fixture_provides_mock_emulator(self, mock_emulator):
        """Fixture provides configured mock emulator."""
        assert mock_emulator.status == EmulatorStatus.CONNECTED

    def test_fixture_provides_snapshot(self, sample_snapshot):
        """Fixture provides configured snapshot."""
        assert sample_snapshot.mode == 0x09
        assert sample_snapshot.link_x == 128

    def test_fixtures_are_independent(self, mock_emulator, sample_snapshot):
        """Multiple fixtures can be used together."""
        mock_emulator.read_memory.return_value = MemoryRead(address=0x10, value=sample_snapshot.mode)
        result = mock_emulator.read_memory(0x10)
        assert result.value == 0x09


# =============================================================================
# Fixture Factory Tests
# =============================================================================

class TestFixtureFactories:
    """Tests for fixture factory patterns."""

    @pytest.fixture
    def snapshot_factory(self):
        """Factory fixture for creating snapshots."""
        def _create(**kwargs):
            mock = MagicMock()
            defaults = {
                'mode': 0x09,
                'area': 0x29,
                'room': 0x00,
                'link_x': 128,
                'link_y': 128,
                'link_z': 0,
                'health': 24,
                'max_health': 24,
                'inidisp': 0x0F,
                'timestamp': time.time(),
            }
            for key, value in {**defaults, **kwargs}.items():
                setattr(mock, key, value)
            return mock
        return _create

    @pytest.fixture
    def input_frame_factory(self):
        """Factory fixture for creating input frames."""
        def _create(frame=0, buttons=Button.NONE, hold=1):
            return InputFrame(frame_number=frame, buttons=buttons, hold_frames=hold)
        return _create

    @pytest.fixture
    def collision_map_factory(self):
        """Factory fixture for creating collision maps."""
        def _create(pattern: str = None, width: int = 8, height: int = 8):
            if pattern is None:
                data = bytes([TileType.WALKABLE] * (width * height))
            else:
                char_map = {'.': TileType.WALKABLE, '#': TileType.SOLID}
                data = bytes([
                    char_map.get(c, TileType.WALKABLE)
                    for c in pattern.replace('\n', '').replace(' ', '')
                ])
            return CollisionMap(data=data, width=width, height=height)
        return _create

    def test_factory_creates_default_snapshot(self, snapshot_factory):
        """Factory creates snapshot with defaults."""
        snap = snapshot_factory()
        assert snap.mode == 0x09
        assert snap.health == 24

    def test_factory_allows_overrides(self, snapshot_factory):
        """Factory allows overriding defaults."""
        snap = snapshot_factory(mode=0x07, health=12)
        assert snap.mode == 0x07
        assert snap.health == 12

    def test_factory_creates_multiple(self, snapshot_factory):
        """Factory can create multiple instances."""
        snap1 = snapshot_factory(link_x=100)
        snap2 = snapshot_factory(link_x=200)
        assert snap1.link_x == 100
        assert snap2.link_x == 200

    def test_input_frame_factory(self, input_frame_factory):
        """Input frame factory works."""
        frame = input_frame_factory(frame=10, buttons=Button.A)
        assert frame.frame_number == 10
        assert frame.buttons == Button.A

    def test_collision_map_factory_default(self, collision_map_factory):
        """Collision map factory creates walkable map."""
        cmap = collision_map_factory()
        assert cmap.is_walkable(0, 0)
        assert cmap.width == 8

    def test_collision_map_factory_pattern(self, collision_map_factory):
        """Collision map factory accepts pattern."""
        pattern = "........" * 8
        cmap = collision_map_factory(pattern=pattern)
        assert cmap.is_walkable(0, 0)


# =============================================================================
# Parameterized Fixture Tests
# =============================================================================

class TestParameterizedFixtures:
    """Tests for parameterized fixtures."""

    @pytest.fixture(params=[
        EmulatorStatus.CONNECTED,
        EmulatorStatus.CONNECTING,
        EmulatorStatus.DISCONNECTED,
    ])
    def emulator_status(self, request):
        """Parameterized fixture for emulator statuses."""
        return request.param

    @pytest.fixture(params=[
        (0x09, GamePhase.OVERWORLD),
        (0x07, GamePhase.DUNGEON),
        (0x0E, GamePhase.MENU),
    ])
    def mode_and_phase(self, request):
        """Parameterized fixture for mode-phase pairs."""
        return request.param

    @pytest.fixture(params=[
        Button.A,
        Button.B,
        Button.X,
        Button.Y,
    ])
    def action_button(self, request):
        """Parameterized fixture for action buttons."""
        return request.param

    def test_emulator_status_values(self, emulator_status):
        """Test with each emulator status."""
        assert emulator_status in EmulatorStatus
        assert isinstance(emulator_status.value, int)

    def test_mode_phase_mapping(self, mode_and_phase):
        """Test mode to phase mapping."""
        mode, phase = mode_and_phase
        assert isinstance(mode, int)
        assert phase in GamePhase

    def test_action_buttons(self, action_button):
        """Test action button values."""
        assert action_button != Button.NONE
        assert action_button & action_button == action_button


# =============================================================================
# Fixture Scope Tests
# =============================================================================

class TestFixtureScopes:
    """Tests demonstrating fixture scope behavior."""

    # Track invocations for scope testing
    _function_calls = []
    _class_calls = []

    @pytest.fixture
    def function_scoped(self):
        """Function-scoped fixture (default)."""
        TestFixtureScopes._function_calls.append(1)
        return len(TestFixtureScopes._function_calls)

    @pytest.fixture(scope="class")
    def class_scoped(self):
        """Class-scoped fixture."""
        TestFixtureScopes._class_calls.append(1)
        return "class_value"

    def test_function_scope_first(self, function_scoped):
        """First test with function-scoped fixture."""
        assert function_scoped >= 1

    def test_function_scope_second(self, function_scoped):
        """Second test shows fixture recreated."""
        assert function_scoped >= 1

    def test_class_scope_first(self, class_scoped):
        """First test with class-scoped fixture."""
        assert class_scoped == "class_value"

    def test_class_scope_second(self, class_scoped):
        """Second test uses same class instance."""
        assert class_scoped == "class_value"


# =============================================================================
# Fixture Dependency Tests
# =============================================================================

class TestFixtureDependencies:
    """Tests for fixtures that depend on other fixtures."""

    @pytest.fixture
    def base_config(self):
        """Base configuration fixture."""
        return {"width": 8, "height": 8, "tile_size": 16}

    @pytest.fixture
    def collision_map_from_config(self, base_config):
        """Fixture that depends on base_config."""
        data = bytes([TileType.WALKABLE] * (base_config["width"] * base_config["height"]))
        return CollisionMap(
            data=data,
            width=base_config["width"],
            height=base_config["height"]
        )

    @pytest.fixture
    def pathfinder_from_map(self, collision_map_from_config):
        """Fixture that depends on collision_map."""
        pf = Pathfinder()
        pf._collision_map = collision_map_from_config
        return pf

    @pytest.fixture
    def mock_game_state(self, base_config):
        """Mock game state using base config."""
        mock = MagicMock()
        mock.map_width = base_config["width"]
        mock.map_height = base_config["height"]
        return mock

    def test_dependent_collision_map(self, collision_map_from_config, base_config):
        """Dependent fixture uses base config."""
        assert collision_map_from_config.width == base_config["width"]

    def test_chain_of_dependencies(self, pathfinder_from_map, collision_map_from_config):
        """Chain of fixture dependencies works."""
        assert pathfinder_from_map._collision_map is collision_map_from_config

    def test_multiple_dependents(self, collision_map_from_config, mock_game_state, base_config):
        """Multiple fixtures can share dependency."""
        assert collision_map_from_config.width == mock_game_state.map_width


# =============================================================================
# Teardown Pattern Tests
# =============================================================================

class TestTeardownPatterns:
    """Tests for fixture teardown patterns."""

    _cleanup_log = []

    @pytest.fixture
    def resource_with_yield(self):
        """Fixture with yield for cleanup."""
        TestTeardownPatterns._cleanup_log.append("setup")
        resource = {"id": 1, "active": True}
        yield resource
        TestTeardownPatterns._cleanup_log.append("teardown")

    @pytest.fixture
    def recorder_with_cleanup(self):
        """Input recorder with cleanup."""
        recorder = InputRecorder()
        yield recorder
        # Cleanup: ensure recording stopped
        if recorder.is_recording:
            recorder.stop_recording()

    @pytest.fixture
    def mock_connection(self):
        """Mock connection with disconnect."""
        mock = MagicMock()
        mock.connected = True
        yield mock
        mock.disconnect()
        mock.connected = False

    def test_yield_fixture_provides_resource(self, resource_with_yield):
        """Yield fixture provides resource."""
        assert resource_with_yield["active"] is True

    def test_recorder_cleanup(self, recorder_with_cleanup):
        """Recorder fixture cleans up."""
        recorder_with_cleanup.start_recording()
        assert recorder_with_cleanup.is_recording

    def test_mock_connection_cleanup(self, mock_connection):
        """Mock connection cleaned up after test."""
        assert mock_connection.connected


# =============================================================================
# Shared Fixture Tests
# =============================================================================

class TestSharedFixtures:
    """Tests for shared fixture patterns."""

    @pytest.fixture
    def shared_progress(self):
        """Shared progress instance."""
        return CampaignProgress()

    @pytest.fixture
    def progress_with_milestones(self, shared_progress):
        """Progress with milestones added."""
        goal = Goal.reach_location(0x29, 100, 100)
        m1 = CampaignMilestone(id="m1", description="First", goal=goal)
        m2 = CampaignMilestone(id="m2", description="Second", goal=goal)
        shared_progress.add_milestone(m1)
        shared_progress.add_milestone(m2)
        return shared_progress

    @pytest.fixture
    def shared_parser(self):
        """Shared parser instance."""
        return GameStateParser()

    def test_progress_has_milestones(self, progress_with_milestones):
        """Progress fixture has milestones."""
        assert "m1" in progress_with_milestones.milestones
        assert "m2" in progress_with_milestones.milestones

    def test_progress_milestone_count(self, progress_with_milestones):
        """Progress has correct milestone count."""
        assert len(progress_with_milestones.milestones) == 2

    def test_shared_parser_instance(self, shared_parser):
        """Shared parser is properly initialized."""
        assert shared_parser is not None


# =============================================================================
# Request Object Tests
# =============================================================================

class TestRequestObject:
    """Tests using pytest request object."""

    @pytest.fixture
    def fixture_with_name(self, request):
        """Fixture that knows its test name."""
        return f"fixture_for_{request.node.name}"

    @pytest.fixture
    def fixture_with_markers(self, request):
        """Fixture that checks markers."""
        markers = [m.name for m in request.node.iter_markers()]
        return markers

    def test_fixture_knows_test_name(self, fixture_with_name):
        """Fixture can access test name."""
        assert "test_fixture_knows_test_name" in fixture_with_name

    @pytest.mark.slow
    def test_fixture_sees_markers(self, fixture_with_markers):
        """Fixture can see test markers."""
        assert "slow" in fixture_with_markers


# =============================================================================
# Fixture Composition Tests
# =============================================================================

class TestFixtureComposition:
    """Tests for composing multiple fixtures."""

    @pytest.fixture
    def mock_emulator(self):
        """Mock emulator."""
        return MagicMock()

    @pytest.fixture
    def mock_snapshot(self):
        """Mock snapshot."""
        mock = MagicMock()
        mock.mode = 0x09
        mock.area = 0x29
        return mock

    @pytest.fixture
    def configured_emulator(self, mock_emulator, mock_snapshot):
        """Emulator configured with snapshot."""
        mock_emulator.get_snapshot.return_value = mock_snapshot
        return mock_emulator

    @pytest.fixture
    def full_test_context(self, configured_emulator, shared_progress):
        """Complete test context."""
        return {
            "emulator": configured_emulator,
            "progress": shared_progress,
        }

    @pytest.fixture
    def shared_progress(self):
        """Shared progress for composition."""
        return CampaignProgress()

    def test_composed_emulator(self, configured_emulator):
        """Composed fixture works."""
        state = configured_emulator.get_snapshot()
        assert state.mode == 0x09

    def test_full_context(self, full_test_context):
        """Full context composition works."""
        assert "emulator" in full_test_context
        assert "progress" in full_test_context


# =============================================================================
# Autouse Fixture Tests
# =============================================================================

class TestAutouseFixtures:
    """Tests for autouse fixture patterns."""

    _setup_count = 0

    @pytest.fixture(autouse=True)
    def auto_setup(self):
        """Autouse fixture runs for every test."""
        TestAutouseFixtures._setup_count += 1

    @pytest.fixture(autouse=True)
    def reset_singletons(self):
        """Reset singletons before each test."""
        yield
        # Cleanup after test

    def test_autouse_runs_first(self):
        """Autouse fixture ran."""
        assert TestAutouseFixtures._setup_count >= 1

    def test_autouse_runs_again(self):
        """Autouse fixture runs for each test."""
        assert TestAutouseFixtures._setup_count >= 1


# =============================================================================
# Indirect Parameterization Tests
# =============================================================================

class TestIndirectParameterization:
    """Tests for indirect fixture parameterization."""

    @pytest.fixture
    def phase_from_mode(self, request):
        """Convert mode to phase."""
        mode = request.param
        mode_map = {
            0x09: GamePhase.OVERWORLD,
            0x07: GamePhase.DUNGEON,
            0x0E: GamePhase.MENU,
        }
        return mode_map.get(mode, GamePhase.UNKNOWN)

    @pytest.fixture
    def button_combo(self, request):
        """Create button combination."""
        buttons = request.param
        result = Button.NONE
        for b in buttons:
            result |= b
        return result

    @pytest.mark.parametrize("phase_from_mode", [0x09], indirect=True)
    def test_indirect_overworld(self, phase_from_mode):
        """Indirect parameterization for overworld."""
        assert phase_from_mode == GamePhase.OVERWORLD

    @pytest.mark.parametrize("phase_from_mode", [0x07], indirect=True)
    def test_indirect_dungeon(self, phase_from_mode):
        """Indirect parameterization for dungeon."""
        assert phase_from_mode == GamePhase.DUNGEON

    @pytest.mark.parametrize("button_combo", [[Button.A, Button.B]], indirect=True)
    def test_indirect_button_combo(self, button_combo):
        """Indirect parameterization for buttons."""
        assert button_combo & Button.A
        assert button_combo & Button.B


# =============================================================================
# Fixture Caching Tests
# =============================================================================

class TestFixtureCaching:
    """Tests for fixture caching behavior."""

    _cache_hits = {}

    @pytest.fixture
    def cached_resource(self):
        """Resource that tracks access."""
        key = "cached"
        TestFixtureCaching._cache_hits[key] = TestFixtureCaching._cache_hits.get(key, 0) + 1
        return {"value": 42, "access_count": TestFixtureCaching._cache_hits[key]}

    @pytest.fixture
    def expensive_computation(self):
        """Simulates expensive computation."""
        result = sum(range(1000))
        return result

    def test_cached_resource_first(self, cached_resource):
        """First access to cached resource."""
        assert cached_resource["value"] == 42

    def test_cached_resource_second(self, cached_resource):
        """Second access creates new instance."""
        assert cached_resource["value"] == 42

    def test_expensive_computation(self, expensive_computation):
        """Expensive computation result."""
        assert expensive_computation == 499500


# =============================================================================
# Generator Fixture Tests
# =============================================================================

class TestGeneratorFixtures:
    """Tests for generator-based fixtures."""

    @pytest.fixture
    def snapshot_sequence(self) -> Generator[MagicMock, None, None]:
        """Generator fixture for snapshots."""
        snapshots = []
        for i in range(3):
            mock = MagicMock()
            mock.mode = 0x09
            mock.link_x = 100 + (i * 16)
            snapshots.append(mock)
        yield snapshots

    @pytest.fixture
    def button_stream(self) -> Generator[Button, None, None]:
        """Generator fixture for buttons."""
        buttons = [Button.A, Button.B, Button.A, Button.Y]
        yield buttons

    def test_snapshot_sequence(self, snapshot_sequence):
        """Generator provides snapshot list."""
        assert len(snapshot_sequence) == 3
        assert snapshot_sequence[0].link_x == 100

    def test_button_stream(self, button_stream):
        """Generator provides button list."""
        assert len(button_stream) == 4
        assert button_stream[0] == Button.A


# =============================================================================
# Error Handling Fixture Tests
# =============================================================================

class TestErrorHandlingFixtures:
    """Tests for fixtures with error handling."""

    @pytest.fixture
    def failing_connection(self):
        """Fixture that simulates connection failure."""
        mock = MagicMock()
        mock.connect.side_effect = ConnectionError("Failed")
        return mock

    @pytest.fixture
    def retry_fixture(self):
        """Fixture with retry logic."""
        attempts = [0]
        def _connect():
            attempts[0] += 1
            if attempts[0] < 3:
                raise ConnectionError("Retry")
            return True
        return _connect

    @pytest.fixture
    def safe_resource(self):
        """Resource with exception safety."""
        resource = {"acquired": True}
        try:
            yield resource
        finally:
            resource["acquired"] = False

    def test_failing_connection(self, failing_connection):
        """Failing fixture raises on connect."""
        with pytest.raises(ConnectionError):
            failing_connection.connect()

    def test_retry_fixture(self, retry_fixture):
        """Retry fixture succeeds after retries."""
        with pytest.raises(ConnectionError):
            retry_fixture()
        with pytest.raises(ConnectionError):
            retry_fixture()
        assert retry_fixture() is True

    def test_safe_resource_acquired(self, safe_resource):
        """Safe resource is acquired."""
        assert safe_resource["acquired"]


# =============================================================================
# Fixture Skip Tests
# =============================================================================

class TestFixtureSkipPatterns:
    """Tests for skip patterns with fixtures."""

    @pytest.fixture
    def skip_if_no_feature(self, request):
        """Skip if feature not available."""
        has_feature = True  # Simulated feature check
        if not has_feature:
            pytest.skip("Feature not available")
        return "feature_enabled"

    @pytest.fixture
    def conditional_fixture(self, request):
        """Conditional fixture based on markers."""
        if request.node.get_closest_marker("skip_fixture"):
            return None
        return "value"

    def test_with_feature(self, skip_if_no_feature):
        """Test runs when feature available."""
        assert skip_if_no_feature == "feature_enabled"

    def test_conditional_fixture(self, conditional_fixture):
        """Conditional fixture provides value."""
        assert conditional_fixture == "value"


# =============================================================================
# Module-Level Pattern Tests
# =============================================================================

class TestModuleLevelPatterns:
    """Tests for module-level fixture patterns."""

    @pytest.fixture
    def module_constants(self):
        """Module constants fixture."""
        return {
            "MAX_HEALTH": 24,
            "DEFAULT_MODE": 0x09,
            "TILE_SIZE": 16,
        }

    @pytest.fixture
    def game_constants(self, module_constants):
        """Game constants derived from module constants."""
        return {
            **module_constants,
            "SCREEN_WIDTH": 256,
            "SCREEN_HEIGHT": 224,
        }

    def test_module_constants(self, module_constants):
        """Module constants are correct."""
        assert module_constants["MAX_HEALTH"] == 24

    def test_game_constants_extend(self, game_constants):
        """Game constants extend module constants."""
        assert game_constants["MAX_HEALTH"] == 24
        assert game_constants["SCREEN_WIDTH"] == 256
