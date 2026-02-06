"""Tests for pathfinder module.

Verifies A* pathfinding and collision map handling.
"""

import pytest
import sys
from pathlib import Path

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.pathfinder import (
    TileType,
    WALKABLE_TILES,
    SWIM_TILES,
    LEDGE_TILES,
    CollisionMap,
    PathNode,
    NavigationResult,
    Pathfinder,
    get_pathfinder,
    find_path,
)


class TestTileType:
    """Tests for TileType enum."""

    def test_walkable_value(self):
        """Test walkable tile value."""
        assert TileType.WALKABLE == 0x00

    def test_solid_value(self):
        """Test solid tile value."""
        assert TileType.SOLID == 0x01

    def test_deep_water_value(self):
        """Test deep water value."""
        assert TileType.DEEP_WATER == 0x08

    def test_walkable_tiles_set(self):
        """Test walkable tiles set."""
        assert TileType.WALKABLE in WALKABLE_TILES
        assert TileType.GRASS in WALKABLE_TILES
        assert TileType.SOLID not in WALKABLE_TILES

    def test_swim_tiles_set(self):
        """Test swim tiles set."""
        assert TileType.DEEP_WATER in SWIM_TILES


class TestCollisionMap:
    """Tests for CollisionMap."""

    @pytest.fixture
    def simple_map(self):
        """Create a simple 8x8 collision map."""
        # 8x8 map with a wall in the middle
        data = bytearray(64)
        for i in range(64):
            data[i] = TileType.WALKABLE
        # Add wall row at y=4
        for x in range(8):
            if x != 4:  # Leave gap at x=4
                data[4 * 8 + x] = TileType.SOLID
        return CollisionMap(data=bytes(data), width=8, height=8)

    @pytest.fixture
    def water_map(self):
        """Create a map with water tiles."""
        data = bytearray(64)
        for i in range(64):
            data[i] = TileType.WALKABLE
        # Add deep water at center
        for y in range(2, 6):
            for x in range(2, 6):
                data[y * 8 + x] = TileType.DEEP_WATER
        return CollisionMap(data=bytes(data), width=8, height=8)

    def test_get_tile_in_bounds(self, simple_map):
        """Test getting tile within bounds."""
        assert simple_map.get_tile(0, 0) == TileType.WALKABLE
        assert simple_map.get_tile(0, 4) == TileType.SOLID

    def test_get_tile_out_of_bounds(self, simple_map):
        """Test getting tile out of bounds returns solid."""
        assert simple_map.get_tile(-1, 0) == TileType.SOLID
        assert simple_map.get_tile(100, 100) == TileType.SOLID

    def test_get_tile_at_pixel(self, simple_map):
        """Test pixel to tile conversion."""
        # Tile size is 8 pixels
        assert simple_map.get_tile_at_pixel(0, 0) == TileType.WALKABLE
        assert simple_map.get_tile_at_pixel(7, 7) == TileType.WALKABLE
        assert simple_map.get_tile_at_pixel(8, 8) == TileType.WALKABLE  # Tile (1,1)
        assert simple_map.get_tile_at_pixel(0, 32) == TileType.SOLID  # y=4 tiles

    def test_is_walkable_floor(self, simple_map):
        """Test walkability of floor tiles."""
        assert simple_map.is_walkable(0, 0) is True
        assert simple_map.is_walkable(0, 4) is False  # Wall

    def test_is_walkable_gap(self, simple_map):
        """Test gap in wall is walkable."""
        assert simple_map.is_walkable(4, 4) is True  # Gap in wall

    def test_is_walkable_water_no_flippers(self, water_map):
        """Test deep water not walkable without flippers."""
        assert water_map.is_walkable(3, 3) is False

    def test_is_walkable_water_with_flippers(self, water_map):
        """Test deep water walkable with flippers."""
        assert water_map.is_walkable(3, 3, has_flippers=True) is True

    def test_get_neighbors(self, simple_map):
        """Test getting walkable neighbors."""
        neighbors = simple_map.get_neighbors(0, 0)
        # Corner has 2 neighbors
        assert len(neighbors) == 2
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_get_neighbors_blocked(self, simple_map):
        """Test neighbors near wall."""
        # Position above wall (y=3)
        neighbors = simple_map.get_neighbors(0, 3)
        # Can't go down to wall
        assert (0, 4) not in neighbors


class TestPathNode:
    """Tests for PathNode."""

    def test_f_cost_calculation(self):
        """Test f_cost is sum of g and h."""
        node = PathNode(x=0, y=0, g_cost=5.0, h_cost=10.0)
        assert node.f_cost == 15.0

    def test_comparison(self):
        """Test nodes compare by f_cost."""
        node1 = PathNode(x=0, y=0, g_cost=5.0, h_cost=5.0)
        node2 = PathNode(x=1, y=1, g_cost=3.0, h_cost=3.0)
        assert node2 < node1  # node2 has lower f_cost

    def test_equality(self):
        """Test nodes equal by position."""
        node1 = PathNode(x=5, y=5, g_cost=0)
        node2 = PathNode(x=5, y=5, g_cost=10)
        assert node1 == node2

    def test_hash(self):
        """Test nodes hash by position."""
        node1 = PathNode(x=5, y=5)
        node2 = PathNode(x=5, y=5)
        assert hash(node1) == hash(node2)


class TestNavigationResult:
    """Tests for NavigationResult."""

    def test_success_result(self):
        """Test successful navigation result."""
        result = NavigationResult(
            success=True,
            path=[(0, 0), (1, 0), (2, 0)],
            distance=2.0
        )
        assert result.success is True
        assert len(result.path) == 3

    def test_failure_result(self):
        """Test failed navigation result."""
        result = NavigationResult(
            success=False,
            path=[],
            blocked_at=(5, 5),
            reason="Wall in the way"
        )
        assert result.success is False
        assert result.blocked_at == (5, 5)


class TestPathfinder:
    """Tests for Pathfinder class."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder()

    @pytest.fixture
    def open_map(self):
        """Create fully open 16x16 map."""
        data = bytes([TileType.WALKABLE] * 256)
        return CollisionMap(data=data, width=16, height=16)

    @pytest.fixture
    def maze_map(self):
        """Create simple maze map."""
        # 8x8 with corridor
        data = bytearray(64)
        for i in range(64):
            data[i] = TileType.SOLID

        # Horizontal corridor at y=0
        for x in range(8):
            data[0 * 8 + x] = TileType.WALKABLE
        # Vertical corridor at x=7
        for y in range(8):
            data[y * 8 + 7] = TileType.WALKABLE
        # Horizontal corridor at y=7
        for x in range(8):
            data[7 * 8 + x] = TileType.WALKABLE

        return CollisionMap(data=bytes(data), width=8, height=8)

    def test_heuristic(self, pathfinder):
        """Test Manhattan distance heuristic."""
        assert pathfinder.heuristic((0, 0), (3, 4)) == 7
        assert pathfinder.heuristic((5, 5), (5, 5)) == 0

    def test_find_path_straight_line(self, pathfinder, open_map):
        """Test pathfinding in open area."""
        result = pathfinder.find_path((0, 0), (5, 0), collision_map=open_map)

        assert result.success is True
        assert len(result.path) == 6
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (5, 0)

    def test_find_path_diagonal(self, pathfinder, open_map):
        """Test pathfinding to diagonal destination."""
        result = pathfinder.find_path((0, 0), (3, 3), collision_map=open_map)

        assert result.success is True
        # Manhattan path length is 7 (3 right + 3 down + start)
        # But A* can vary - just check endpoints
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (3, 3)

    def test_find_path_around_obstacle(self, pathfinder, maze_map):
        """Test pathfinding around walls through maze."""
        # Path from (0,0) to (0,7) must go around
        result = pathfinder.find_path((0, 0), (0, 7), collision_map=maze_map)

        assert result.success is True
        # Path goes right to (7,0), down to (7,7), left to (0,7)
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (0, 7)
        # Path length: 7 right + 7 down + 7 left + start = 22
        assert len(result.path) == 22

    def test_find_path_no_path(self, pathfinder):
        """Test when no path exists."""
        # Isolated start
        data = bytearray(64)
        for i in range(64):
            data[i] = TileType.SOLID
        data[0] = TileType.WALKABLE  # Only start is walkable
        data[63] = TileType.WALKABLE  # Goal is walkable but unreachable

        isolated_map = CollisionMap(data=bytes(data), width=8, height=8)
        result = pathfinder.find_path((0, 0), (7, 7), collision_map=isolated_map)

        assert result.success is False
        assert "No path found" in result.reason

    def test_find_path_start_blocked(self, pathfinder, open_map):
        """Test when start is blocked."""
        # Make start solid
        data = bytearray(open_map.data)
        data[0] = TileType.SOLID
        blocked_map = CollisionMap(data=bytes(data), width=16, height=16)

        result = pathfinder.find_path((0, 0), (5, 5), collision_map=blocked_map)

        assert result.success is False
        assert "not walkable" in result.reason

    def test_find_path_goal_blocked(self, pathfinder, open_map):
        """Test when goal is blocked."""
        data = bytearray(open_map.data)
        data[5 * 16 + 5] = TileType.SOLID  # Block (5,5)
        blocked_map = CollisionMap(data=bytes(data), width=16, height=16)

        result = pathfinder.find_path((0, 0), (5, 5), collision_map=blocked_map)

        assert result.success is False
        assert "not walkable" in result.reason

    def test_find_path_pixels(self, pathfinder, open_map):
        """Test pixel-based pathfinding."""
        # 40 pixels = 5 tiles
        result = pathfinder.find_path_pixels(
            (0, 0), (40, 0), collision_map=open_map
        )

        assert result.success is True
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (5, 0)

    def test_path_to_inputs_horizontal(self, pathfinder):
        """Test converting horizontal path to inputs."""
        path = [(0, 0), (1, 0), (2, 0), (3, 0)]
        inputs = pathfinder.path_to_inputs(path, frames_per_tile=8)

        assert len(inputs) == 1
        assert inputs[0] == ("RIGHT", 24)  # 3 moves * 8 frames

    def test_path_to_inputs_vertical(self, pathfinder):
        """Test converting vertical path to inputs."""
        path = [(0, 0), (0, 1), (0, 2)]
        inputs = pathfinder.path_to_inputs(path, frames_per_tile=10)

        assert len(inputs) == 1
        assert inputs[0] == ("DOWN", 20)

    def test_path_to_inputs_turn(self, pathfinder):
        """Test path with direction changes."""
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        inputs = pathfinder.path_to_inputs(path, frames_per_tile=8)

        assert len(inputs) == 2
        assert inputs[0] == ("RIGHT", 16)  # 2 moves
        assert inputs[1] == ("DOWN", 16)   # 2 moves

    def test_path_to_inputs_empty(self, pathfinder):
        """Test empty path."""
        inputs = pathfinder.path_to_inputs([])
        assert inputs == []

    def test_path_to_inputs_single_point(self, pathfinder):
        """Test single point path."""
        inputs = pathfinder.path_to_inputs([(5, 5)])
        assert inputs == []


class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_pathfinder_singleton(self):
        """Test singleton behavior."""
        pf1 = get_pathfinder()
        pf2 = get_pathfinder()
        assert pf1 is pf2

    def test_find_path_convenience(self):
        """Test convenience function."""
        # Create 64x64 collision map (4096 bytes)
        data = bytes([TileType.WALKABLE] * 4096)
        result = find_path((0, 0), (3, 3), collision_data=data)

        assert result.success is True
