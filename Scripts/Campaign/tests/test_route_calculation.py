"""Route calculation and obstacle handling tests (Iteration 43).

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- A.2: Navigate overworld to specific locations
- D.2: Collision map reader for pathfinding

These tests verify A* route calculation, obstacle handling scenarios,
path optimization, and multi-room navigation patterns.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch
import time

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.pathfinder import (
    TileType, WALKABLE_TILES, SWIM_TILES, LEDGE_TILES,
    CollisionMap, PathNode, NavigationResult, Pathfinder
)


# =============================================================================
# Route Calculation Algorithm Tests
# =============================================================================

class TestAStarBasicCases:
    """Test A* algorithm basic cases."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    @pytest.fixture
    def empty_map(self):
        """Create empty (all walkable) collision map."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        return CollisionMap(data=data)

    def test_path_same_start_and_goal(self, pathfinder, empty_map):
        """Test path when start equals goal."""
        result = pathfinder.find_path((10, 10), (10, 10), empty_map)
        assert result.success is True
        assert result.path == [(10, 10)]

    def test_path_adjacent_horizontal(self, pathfinder, empty_map):
        """Test path between horizontally adjacent tiles."""
        result = pathfinder.find_path((10, 10), (11, 10), empty_map)
        assert result.success is True
        assert len(result.path) == 2
        assert result.path[0] == (10, 10)
        assert result.path[1] == (11, 10)

    def test_path_adjacent_vertical(self, pathfinder, empty_map):
        """Test path between vertically adjacent tiles."""
        result = pathfinder.find_path((10, 10), (10, 11), empty_map)
        assert result.success is True
        assert len(result.path) == 2

    def test_path_diagonal_requires_two_moves(self, pathfinder, empty_map):
        """Test diagonal movement requires 2 cardinal moves."""
        result = pathfinder.find_path((10, 10), (11, 11), empty_map)
        assert result.success is True
        # Diagonal = 2 moves (no diagonal movement allowed)
        assert len(result.path) == 3

    def test_path_straight_line_horizontal(self, pathfinder, empty_map):
        """Test straight horizontal path."""
        result = pathfinder.find_path((10, 10), (15, 10), empty_map)
        assert result.success is True
        assert len(result.path) == 6  # 5 tiles distance + 1 for start
        # Verify all tiles have same Y
        for x, y in result.path:
            assert y == 10

    def test_path_straight_line_vertical(self, pathfinder, empty_map):
        """Test straight vertical path."""
        result = pathfinder.find_path((10, 10), (10, 15), empty_map)
        assert result.success is True
        assert len(result.path) == 6
        # Verify all tiles have same X
        for x, y in result.path:
            assert x == 10

    def test_path_distance_calculated(self, pathfinder, empty_map):
        """Test path distance is calculated correctly."""
        result = pathfinder.find_path((10, 10), (15, 10), empty_map)
        assert result.success is True
        assert result.distance == 5  # 5 moves

    def test_path_includes_start_and_goal(self, pathfinder, empty_map):
        """Test path includes both start and goal."""
        start = (5, 5)
        goal = (10, 10)
        result = pathfinder.find_path(start, goal, empty_map)
        assert result.success is True
        assert result.path[0] == start
        assert result.path[-1] == goal


class TestAStarObstacleAvoidance:
    """Test A* obstacle avoidance behavior."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    def test_path_around_single_obstacle(self, pathfinder):
        """Test path goes around single solid tile."""
        # Create map with one solid tile blocking direct path
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.SOLID  # Block (11, 10)
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        # Should go around: either up or down
        assert (11, 10) not in result.path

    def test_path_around_wall(self, pathfinder):
        """Test path goes around a wall."""
        # Create horizontal wall
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        for x in range(5, 15):
            data[10 * 64 + x] = TileType.SOLID  # Wall at y=10
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 5), (10, 15), cmap)
        assert result.success is True
        # Path must go around the wall
        for x, y in result.path:
            if 5 <= x < 15:
                assert y != 10  # Never on the wall

    def test_path_through_opening(self, pathfinder):
        """Test path finds opening in wall."""
        # Create wall with one opening
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        for x in range(5, 15):
            if x != 10:  # Leave opening at x=10
                data[10 * 64 + x] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 5), (10, 15), cmap)
        assert result.success is True
        # Should go through the opening at x=10
        assert (10, 10) in result.path

    def test_no_path_completely_blocked(self, pathfinder):
        """Test no path when completely surrounded."""
        # Surround start position
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            data[(10 + dy) * 64 + (10 + dx)] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (20, 20), cmap)
        assert result.success is False

    def test_unwalkable_start_fails(self, pathfinder):
        """Test path fails when start is unwalkable."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 10] = TileType.SOLID  # Start is solid
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (20, 20), cmap)
        assert result.success is False
        assert "Start" in result.reason

    def test_unwalkable_goal_fails(self, pathfinder):
        """Test path fails when goal is unwalkable."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[20 * 64 + 20] = TileType.SOLID  # Goal is solid
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (20, 20), cmap)
        assert result.success is False
        assert "Goal" in result.reason


class TestAStarSpecialTiles:
    """Test A* behavior with special tile types."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    def test_path_through_grass(self, pathfinder):
        """Test path can go through grass tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.GRASS
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        assert (11, 10) in result.path

    def test_path_through_shallow_water(self, pathfinder):
        """Test path can go through shallow water."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.SHALLOW_WATER
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        assert (11, 10) in result.path

    def test_path_through_ladder(self, pathfinder):
        """Test path can go through ladder tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.LADDER
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        assert (11, 10) in result.path

    def test_path_avoids_deep_water_without_flippers(self, pathfinder):
        """Test path avoids deep water when no flippers."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Fill direct path with deep water
        for x in range(11, 15):
            data[10 * 64 + x] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (20, 10), cmap, has_flippers=False)
        assert result.success is True
        # Should not go through deep water
        for x, y in result.path:
            if 11 <= x < 15:
                assert y != 10

    def test_path_through_deep_water_with_flippers(self, pathfinder):
        """Test path can go through deep water with flippers."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap, has_flippers=True)
        assert result.success is True
        assert (11, 10) in result.path

    def test_path_avoids_pit(self, pathfinder):
        """Test path avoids pit tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.PIT
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        assert (11, 10) not in result.path

    def test_path_avoids_spikes(self, pathfinder):
        """Test path avoids spike tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.SPIKE
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 10), (12, 10), cmap)
        assert result.success is True
        assert (11, 10) not in result.path


class TestAStarMaxIterations:
    """Test A* iteration limits."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    def test_max_iterations_stops_search(self, pathfinder):
        """Test search stops at max iterations."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        # Very distant goal with low max_iterations
        result = pathfinder.find_path((0, 0), (60, 60), cmap, max_iterations=10)
        assert result.success is False
        assert "iterations" in result.reason.lower()

    def test_high_max_iterations_finds_long_path(self, pathfinder):
        """Test high max iterations finds long paths."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        result = pathfinder.find_path((0, 0), (60, 60), cmap, max_iterations=100000)
        assert result.success is True

    def test_default_max_iterations_sufficient(self, pathfinder):
        """Test default max iterations is sufficient for most paths."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        # Moderate distance
        result = pathfinder.find_path((10, 10), (50, 50), cmap)
        assert result.success is True


# =============================================================================
# Heuristic Function Tests
# =============================================================================

class TestHeuristicFunction:
    """Test Manhattan distance heuristic."""

    def test_heuristic_same_point(self):
        """Test heuristic between same point is 0."""
        result = Pathfinder.heuristic((10, 10), (10, 10))
        assert result == 0

    def test_heuristic_horizontal(self):
        """Test horizontal distance."""
        result = Pathfinder.heuristic((0, 0), (5, 0))
        assert result == 5

    def test_heuristic_vertical(self):
        """Test vertical distance."""
        result = Pathfinder.heuristic((0, 0), (0, 5))
        assert result == 5

    def test_heuristic_diagonal(self):
        """Test diagonal distance (Manhattan)."""
        result = Pathfinder.heuristic((0, 0), (5, 5))
        assert result == 10  # |5| + |5| = 10

    def test_heuristic_negative_coords(self):
        """Test heuristic with negative coordinates."""
        result = Pathfinder.heuristic((-5, -5), (5, 5))
        assert result == 20  # |10| + |10| = 20

    def test_heuristic_symmetric(self):
        """Test heuristic is symmetric."""
        a = (5, 10)
        b = (15, 25)
        assert Pathfinder.heuristic(a, b) == Pathfinder.heuristic(b, a)


# =============================================================================
# PathNode Tests
# =============================================================================

class TestPathNodeDataclass:
    """Test PathNode dataclass."""

    def test_pathnode_creation(self):
        """Test creating PathNode."""
        node = PathNode(x=10, y=20)
        assert node.x == 10
        assert node.y == 20

    def test_pathnode_default_costs(self):
        """Test PathNode default costs are 0."""
        node = PathNode(x=0, y=0)
        assert node.g_cost == 0.0
        assert node.h_cost == 0.0

    def test_pathnode_f_cost(self):
        """Test PathNode f_cost property."""
        node = PathNode(x=0, y=0, g_cost=5.0, h_cost=10.0)
        assert node.f_cost == 15.0

    def test_pathnode_parent_default_none(self):
        """Test PathNode parent defaults to None."""
        node = PathNode(x=0, y=0)
        assert node.parent is None

    def test_pathnode_with_parent(self):
        """Test PathNode with parent."""
        parent = PathNode(x=0, y=0)
        child = PathNode(x=1, y=0, parent=parent)
        assert child.parent is parent

    def test_pathnode_comparison(self):
        """Test PathNode comparison by f_cost."""
        node_low = PathNode(x=0, y=0, g_cost=1, h_cost=1)
        node_high = PathNode(x=1, y=1, g_cost=5, h_cost=5)
        assert node_low < node_high

    def test_pathnode_equality_by_position(self):
        """Test PathNode equality is by position only."""
        node1 = PathNode(x=5, y=10, g_cost=1, h_cost=1)
        node2 = PathNode(x=5, y=10, g_cost=999, h_cost=999)
        assert node1 == node2

    def test_pathnode_hash(self):
        """Test PathNode is hashable."""
        node = PathNode(x=5, y=10)
        assert hash(node) == hash((5, 10))

    def test_pathnode_in_set(self):
        """Test PathNode can be in set."""
        nodes = {PathNode(x=1, y=1), PathNode(x=2, y=2)}
        assert len(nodes) == 2
        assert PathNode(x=1, y=1) in nodes


# =============================================================================
# NavigationResult Tests
# =============================================================================

class TestNavigationResultDataclass:
    """Test NavigationResult dataclass."""

    def test_success_result(self):
        """Test successful navigation result."""
        result = NavigationResult(
            success=True,
            path=[(0, 0), (1, 0), (2, 0)],
            distance=2.0
        )
        assert result.success is True
        assert len(result.path) == 3
        assert result.distance == 2.0

    def test_failure_result(self):
        """Test failed navigation result."""
        result = NavigationResult(
            success=False,
            path=[],
            reason="No path found"
        )
        assert result.success is False
        assert result.path == []
        assert result.reason == "No path found"

    def test_blocked_at_field(self):
        """Test blocked_at field for partial paths."""
        result = NavigationResult(
            success=False,
            path=[(0, 0), (1, 0)],
            blocked_at=(2, 0),
            reason="Blocked by wall"
        )
        assert result.blocked_at == (2, 0)

    def test_default_distance_zero(self):
        """Test default distance is 0."""
        result = NavigationResult(success=True, path=[])
        assert result.distance == 0.0

    def test_default_blocked_at_none(self):
        """Test default blocked_at is None."""
        result = NavigationResult(success=True, path=[])
        assert result.blocked_at is None

    def test_default_reason_empty(self):
        """Test default reason is empty string."""
        result = NavigationResult(success=True, path=[])
        assert result.reason == ""


# =============================================================================
# Pixel Coordinate Conversion Tests
# =============================================================================

class TestPixelCoordinateConversion:
    """Test pixel to tile coordinate conversion."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    @pytest.fixture
    def empty_map(self):
        """Create empty collision map."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        return CollisionMap(data=data)

    def test_find_path_pixels_converts_start(self, pathfinder, empty_map):
        """Test pixel coordinates converted correctly for start."""
        # 80 pixels = 10 tiles (8 pixels per tile)
        result = pathfinder.find_path_pixels(
            (80, 80), (88, 80), collision_map=empty_map
        )
        assert result.success is True
        assert result.path[0] == (10, 10)

    def test_find_path_pixels_converts_goal(self, pathfinder, empty_map):
        """Test pixel coordinates converted correctly for goal."""
        result = pathfinder.find_path_pixels(
            (80, 80), (96, 80), collision_map=empty_map
        )
        assert result.success is True
        assert result.path[-1] == (12, 10)

    def test_find_path_pixels_subpixel_rounding(self, pathfinder, empty_map):
        """Test subpixel values round down to tile."""
        # 85 pixels -> tile 10 (85 // 8 = 10)
        result = pathfinder.find_path_pixels(
            (85, 85), (95, 95), collision_map=empty_map
        )
        assert result.success is True
        assert result.path[0] == (10, 10)

    def test_find_path_pixels_origin(self, pathfinder, empty_map):
        """Test pixel (0,0) maps to tile (0,0)."""
        result = pathfinder.find_path_pixels(
            (0, 0), (8, 0), collision_map=empty_map
        )
        assert result.success is True
        assert result.path[0] == (0, 0)

    def test_find_path_pixels_large_coordinates(self, pathfinder, empty_map):
        """Test large pixel coordinates."""
        # 500 pixels = 62.5 tiles -> 62
        result = pathfinder.find_path_pixels(
            (400, 400), (450, 450), collision_map=empty_map
        )
        assert result.success is True
        # Path should contain valid tile coordinates


# =============================================================================
# Path to Input Conversion Tests
# =============================================================================

class TestPathToInputConversion:
    """Test path_to_inputs conversion."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    def test_empty_path_no_inputs(self, pathfinder):
        """Test empty path produces no inputs."""
        result = pathfinder.path_to_inputs([])
        assert result == []

    def test_single_point_no_inputs(self, pathfinder):
        """Test single point path produces no inputs."""
        result = pathfinder.path_to_inputs([(10, 10)])
        assert result == []

    def test_horizontal_right_movement(self, pathfinder):
        """Test horizontal right movement."""
        path = [(10, 10), (11, 10), (12, 10)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 1
        assert result[0][0] == "RIGHT"
        assert result[0][1] == 16  # 2 tiles * 8 frames

    def test_horizontal_left_movement(self, pathfinder):
        """Test horizontal left movement."""
        path = [(12, 10), (11, 10), (10, 10)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 1
        assert result[0][0] == "LEFT"

    def test_vertical_down_movement(self, pathfinder):
        """Test vertical down movement."""
        path = [(10, 10), (10, 11), (10, 12)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 1
        assert result[0][0] == "DOWN"

    def test_vertical_up_movement(self, pathfinder):
        """Test vertical up movement."""
        path = [(10, 12), (10, 11), (10, 10)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 1
        assert result[0][0] == "UP"

    def test_turn_creates_multiple_inputs(self, pathfinder):
        """Test turning creates separate input commands."""
        path = [(10, 10), (11, 10), (11, 11)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 2
        assert result[0][0] == "RIGHT"
        assert result[1][0] == "DOWN"

    def test_custom_frames_per_tile(self, pathfinder):
        """Test custom frames per tile."""
        path = [(10, 10), (11, 10)]
        result = pathfinder.path_to_inputs(path, frames_per_tile=12)
        assert result[0][1] == 12

    def test_consecutive_same_direction_merged(self, pathfinder):
        """Test consecutive same-direction moves are merged."""
        path = [(10, 10), (11, 10), (12, 10), (13, 10), (14, 10)]
        result = pathfinder.path_to_inputs(path)
        assert len(result) == 1
        assert result[0][0] == "RIGHT"
        assert result[0][1] == 32  # 4 tiles * 8 frames


# =============================================================================
# CollisionMap Tests
# =============================================================================

class TestCollisionMapTileAccess:
    """Test CollisionMap tile access methods."""

    def test_get_tile_valid(self):
        """Test getting valid tile."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 5] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        assert cmap.get_tile(5, 10) == TileType.SOLID

    def test_get_tile_out_of_bounds_returns_solid(self):
        """Test out of bounds returns SOLID."""
        cmap = CollisionMap(data=bytes([TileType.WALKABLE] * 100))

        assert cmap.get_tile(-1, 0) == TileType.SOLID
        assert cmap.get_tile(0, -1) == TileType.SOLID
        assert cmap.get_tile(100, 0) == TileType.SOLID
        assert cmap.get_tile(0, 100) == TileType.SOLID

    def test_get_tile_at_pixel(self):
        """Test getting tile at pixel coordinates."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 5] = TileType.GRASS
        cmap = CollisionMap(data=bytes(data))

        # Pixel (40, 80) = tile (5, 10)
        assert cmap.get_tile_at_pixel(40, 80) == TileType.GRASS

    def test_is_walkable_true(self):
        """Test is_walkable returns True for walkable tiles."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        assert cmap.is_walkable(5, 5) is True

    def test_is_walkable_false_for_solid(self):
        """Test is_walkable returns False for solid tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5 * 64 + 5] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        assert cmap.is_walkable(5, 5) is False

    def test_is_walkable_deep_water_with_flippers(self):
        """Test deep water walkable with flippers."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5 * 64 + 5] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))

        assert cmap.is_walkable(5, 5, has_flippers=False) is False
        assert cmap.is_walkable(5, 5, has_flippers=True) is True


class TestCollisionMapNeighbors:
    """Test CollisionMap neighbor finding."""

    def test_get_neighbors_all_four(self):
        """Test all four neighbors returned when walkable."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        neighbors = cmap.get_neighbors(10, 10)
        assert len(neighbors) == 4
        assert (9, 10) in neighbors
        assert (11, 10) in neighbors
        assert (10, 9) in neighbors
        assert (10, 11) in neighbors

    def test_get_neighbors_one_blocked(self):
        """Test blocked neighbor excluded."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.SOLID  # Block (11, 10)
        cmap = CollisionMap(data=bytes(data))

        neighbors = cmap.get_neighbors(10, 10)
        assert len(neighbors) == 3
        assert (11, 10) not in neighbors

    def test_get_neighbors_at_corner(self):
        """Test neighbors at corner of map."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        neighbors = cmap.get_neighbors(0, 0)
        assert len(neighbors) == 2
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_get_neighbors_with_flippers(self):
        """Test neighbors include water with flippers."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 11] = TileType.DEEP_WATER
        cmap = CollisionMap(data=bytes(data))

        without_flippers = cmap.get_neighbors(10, 10, has_flippers=False)
        with_flippers = cmap.get_neighbors(10, 10, has_flippers=True)

        assert (11, 10) not in without_flippers
        assert (11, 10) in with_flippers


# =============================================================================
# Cache Behavior Tests
# =============================================================================

class TestPathfinderCache:
    """Test pathfinder cache behavior."""

    def test_cache_initially_none(self):
        """Test cache is None initially."""
        pf = Pathfinder()
        assert pf._collision_cache is None

    def test_cache_timestamp_initially_zero(self):
        """Test cache timestamp is 0 initially."""
        pf = Pathfinder()
        assert pf._cache_timestamp == 0.0

    def test_default_cache_ttl(self):
        """Test default cache TTL is 1 second."""
        pf = Pathfinder()
        assert pf.cache_ttl == 1.0

    def test_custom_cache_ttl(self):
        """Test custom cache TTL can be set."""
        pf = Pathfinder()
        pf.cache_ttl = 5.0
        assert pf.cache_ttl == 5.0


# =============================================================================
# Edge Cases Tests
# =============================================================================

class TestPathfindingEdgeCases:
    """Test pathfinding edge cases."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder(emulator=None)

    def test_path_at_map_boundary(self, pathfinder):
        """Test path along map boundary."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        result = pathfinder.find_path((0, 0), (0, 10), cmap)
        assert result.success is True

    def test_path_across_map(self, pathfinder):
        """Test path across entire map."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        cmap = CollisionMap(data=data)

        result = pathfinder.find_path((0, 0), (63, 63), cmap, max_iterations=100000)
        assert result.success is True

    def test_maze_path(self, pathfinder):
        """Test path through simple maze."""
        # Create simple maze: walls with corridor
        data = bytearray([TileType.SOLID] * (64 * 64))
        # Create corridor: x=10, y=0 to y=20
        for y in range(21):
            data[y * 64 + 10] = TileType.WALKABLE
        # Horizontal corridor: y=20, x=10 to x=20
        for x in range(10, 21):
            data[20 * 64 + x] = TileType.WALKABLE
        # Vertical corridor: x=20, y=20 to y=30
        for y in range(20, 31):
            data[y * 64 + 20] = TileType.WALKABLE
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((10, 0), (20, 30), cmap)
        assert result.success is True
        # Path should follow the corridor

    def test_narrow_corridor(self, pathfinder):
        """Test path through 1-tile wide corridor."""
        data = bytearray([TileType.SOLID] * (64 * 64))
        # Create 1-tile corridor
        for x in range(5, 15):
            data[10 * 64 + x] = TileType.WALKABLE
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((5, 10), (14, 10), cmap)
        assert result.success is True
        assert len(result.path) == 10


class TestTileTypeValues:
    """Test TileType enum values are correct."""

    def test_all_tile_types_unique(self):
        """Test all tile types have unique values."""
        values = [t.value for t in TileType]
        assert len(values) == len(set(values))

    def test_tile_types_are_bytes(self):
        """Test all tile type values fit in a byte."""
        for t in TileType:
            assert 0 <= t.value <= 255

    def test_tile_types_match_alttp_spec(self):
        """Test key tile values match ALTTP specification."""
        assert TileType.WALKABLE == 0x00
        assert TileType.SOLID == 0x01
        assert TileType.DEEP_WATER == 0x08
        assert TileType.PIT == 0x20
        assert TileType.WARP == 0x80
