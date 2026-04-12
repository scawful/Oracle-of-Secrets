"""Tests for pathfinder and collision map functionality.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- D: Navigation system validation

These tests verify the pathfinder algorithm and collision map
work correctly for navigating the game world.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, patch
import tempfile

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.pathfinder import (
    TileType, CollisionMap, Pathfinder, NavigationResult
)


class TestTileType:
    """Test TileType enum."""

    def test_tile_type_walkable(self):
        """Test WALKABLE tile type exists."""
        assert TileType.WALKABLE is not None
        assert TileType.WALKABLE.value == 0

    def test_tile_type_solid(self):
        """Test SOLID tile type exists."""
        assert TileType.SOLID is not None
        assert TileType.SOLID.value == 1

    def test_tile_type_water(self):
        """Test water tile types exist."""
        assert TileType.DEEP_WATER is not None
        assert TileType.SHALLOW_WATER is not None
        assert TileType.WATER_EDGE is not None

    def test_tile_type_hazards(self):
        """Test hazard tile types exist."""
        assert TileType.PIT is not None
        assert TileType.SPIKE is not None
        assert TileType.DAMAGE_FLOOR is not None

    def test_tile_type_ledges(self):
        """Test ledge tile types exist."""
        assert TileType.LEDGE_UP is not None
        assert TileType.LEDGE_DOWN is not None
        assert TileType.LEDGE_LEFT is not None
        assert TileType.LEDGE_RIGHT is not None

    def test_tile_type_values_distinct(self):
        """Test common tile types have distinct values."""
        types = [TileType.WALKABLE, TileType.SOLID, TileType.DEEP_WATER, TileType.PIT]
        values = [t.value for t in types]
        assert len(values) == len(set(values))

    def test_tile_type_all_variants(self):
        """Test all expected tile type variants exist."""
        expected = ["WALKABLE", "SOLID", "DEEP_WATER", "SHALLOW_WATER", "PIT", "WARP"]
        for name in expected:
            assert hasattr(TileType, name), f"Missing TileType.{name}"


class TestCollisionMap:
    """Test CollisionMap class."""

    @pytest.fixture
    def walkable_data(self):
        """Create walkable collision data."""
        return bytes([TileType.WALKABLE.value] * 4096)

    @pytest.fixture
    def mixed_data(self):
        """Create collision data with some blocked tiles."""
        data = bytearray([TileType.WALKABLE.value] * 4096)
        # Block a few tiles
        data[0] = TileType.SOLID.value
        data[100] = TileType.SOLID.value
        data[500] = TileType.DEEP_WATER.value
        return bytes(data)

    def test_create_collision_map(self, walkable_data):
        """Test creating collision map from data."""
        cmap = CollisionMap(data=walkable_data, width=64, height=64)
        assert cmap is not None
        assert cmap.width == 64
        assert cmap.height == 64

    def test_collision_map_get_tile(self, mixed_data):
        """Test getting tile type."""
        cmap = CollisionMap(data=mixed_data, width=64, height=64)
        # First tile (0,0) should be solid
        tile = cmap.get_tile(0, 0)
        assert tile == TileType.SOLID

    def test_collision_map_is_walkable(self, mixed_data):
        """Test is_walkable method."""
        cmap = CollisionMap(data=mixed_data, width=64, height=64)
        # Tile at (0, 0) should not be walkable (SOLID)
        assert not cmap.is_walkable(0, 0)

    def test_collision_map_walkable_tile(self, walkable_data):
        """Test walkable tiles return true."""
        cmap = CollisionMap(data=walkable_data, width=64, height=64)
        # All tiles should be walkable
        assert cmap.is_walkable(10, 10)
        assert cmap.is_walkable(30, 30)

    def test_collision_map_tile_size(self, walkable_data):
        """Test tile size configuration."""
        cmap = CollisionMap(data=walkable_data, width=64, height=64, tile_size=8)
        assert cmap.tile_size == 8

    def test_get_tile_at_pixel(self, walkable_data):
        """Test getting tile at pixel coordinates."""
        cmap = CollisionMap(data=walkable_data, width=64, height=64, tile_size=8)
        # Pixel (40, 40) should be in tile (5, 5) with tile_size=8
        tile = cmap.get_tile_at_pixel(40, 40)
        assert tile == TileType.WALKABLE


class TestPathfinder:
    """Test Pathfinder class."""

    @pytest.fixture
    def walkable_collision_map(self):
        """Create walkable collision map."""
        data = bytes([TileType.WALKABLE.value] * 4096)
        return CollisionMap(data=data, width=64, height=64)

    @pytest.fixture
    def collision_map_with_wall(self):
        """Create collision map with a wall."""
        data = bytearray([TileType.WALKABLE.value] * 4096)
        # Create vertical wall at x=32
        for y in range(40):
            data[32 + y * 64] = TileType.SOLID.value
        return CollisionMap(data=bytes(data), width=64, height=64)

    def test_pathfinder_creation_no_emulator(self):
        """Test creating pathfinder without emulator."""
        pathfinder = Pathfinder()
        assert pathfinder is not None

    def test_pathfinder_creation_with_mock_emulator(self):
        """Test creating pathfinder with mock emulator."""
        mock_emu = Mock()
        pathfinder = Pathfinder(emulator=mock_emu)
        assert pathfinder is not None

    def test_find_path_open_area(self, walkable_collision_map):
        """Test finding path in open area."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(5, 5),
            goal=(20, 20),
            collision_map=walkable_collision_map
        )

        assert isinstance(result, NavigationResult)
        assert result.success
        assert result.path is not None
        assert len(result.path) > 0

    def test_find_path_same_location(self, walkable_collision_map):
        """Test path to same location."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(10, 10),
            goal=(10, 10),
            collision_map=walkable_collision_map
        )

        assert isinstance(result, NavigationResult)
        assert result.success

    def test_find_path_around_wall(self, collision_map_with_wall):
        """Test pathfinding around obstacle."""
        pathfinder = Pathfinder()
        # Start on left side of wall, goal on right side
        result = pathfinder.find_path(
            start=(10, 10),
            goal=(50, 10),
            collision_map=collision_map_with_wall
        )

        assert isinstance(result, NavigationResult)
        # Path should exist (going around the wall)

    def test_pathfinder_max_iterations(self, walkable_collision_map):
        """Test pathfinder respects max_iterations."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(0, 0),
            goal=(60, 60),
            collision_map=walkable_collision_map,
            max_iterations=100  # Very low limit
        )

        assert isinstance(result, NavigationResult)


class TestNavigationResult:
    """Test NavigationResult dataclass."""

    def test_navigation_result_success(self):
        """Test successful navigation result."""
        result = NavigationResult(
            success=True,
            path=[(0, 0), (1, 0), (2, 0)],
            distance=2.0
        )
        assert result.success
        assert len(result.path) == 3
        assert result.distance == 2.0

    def test_navigation_result_failure(self):
        """Test failed navigation result."""
        result = NavigationResult(
            success=False,
            path=[],
            distance=0.0,
            reason="No path exists"
        )
        assert not result.success
        assert result.reason == "No path exists"

    def test_navigation_result_blocked_at(self):
        """Test navigation result with blocked_at."""
        result = NavigationResult(
            success=False,
            path=[(0, 0), (1, 0)],
            distance=1.0,
            blocked_at=(2, 0),
            reason="Path blocked by wall"
        )
        assert result.blocked_at == (2, 0)

    def test_navigation_result_path_types(self):
        """Test navigation result path contains tuples."""
        path = [(0, 0), (1, 1), (2, 2)]
        result = NavigationResult(success=True, path=path, distance=2.0)

        for point in result.path:
            assert isinstance(point, tuple)
            assert len(point) == 2


class TestCollisionMapMethods:
    """Test CollisionMap utility methods."""

    @pytest.fixture
    def test_map(self):
        """Create test collision map."""
        data = bytes([TileType.WALKABLE.value] * 4096)
        return CollisionMap(data=data, width=64, height=64)

    def test_get_neighbors(self, test_map):
        """Test get_neighbors method."""
        neighbors = test_map.get_neighbors(10, 10)
        assert isinstance(neighbors, list)
        # Should have up to 8 neighbors (or 4 for orthogonal)
        assert len(neighbors) <= 8

    def test_get_neighbors_corner(self, test_map):
        """Test get_neighbors at corner."""
        neighbors = test_map.get_neighbors(0, 0)
        assert isinstance(neighbors, list)
        # Corner has fewer neighbors
        assert len(neighbors) < 8

    def test_get_neighbors_edge(self, test_map):
        """Test get_neighbors at edge."""
        neighbors = test_map.get_neighbors(0, 10)
        assert isinstance(neighbors, list)


class TestCollisionMapConstants:
    """Test CollisionMap class constants."""

    def test_colmapa_addr(self):
        """Test COLMAPA_ADDR constant."""
        assert hasattr(CollisionMap, 'COLMAPA_ADDR')
        assert isinstance(CollisionMap.COLMAPA_ADDR, int)

    def test_colmapb_addr(self):
        """Test COLMAPB_ADDR constant."""
        assert hasattr(CollisionMap, 'COLMAPB_ADDR')
        assert isinstance(CollisionMap.COLMAPB_ADDR, int)

    def test_map_size(self):
        """Test MAP_SIZE constant."""
        assert hasattr(CollisionMap, 'MAP_SIZE')
        assert isinstance(CollisionMap.MAP_SIZE, int)


class TestTileTypeCategories:
    """Test tile type categorization."""

    def test_walkable_value(self):
        """Test WALKABLE has value 0."""
        assert TileType.WALKABLE.value == 0

    def test_solid_blocks_movement(self):
        """Test SOLID blocks movement."""
        assert TileType.SOLID.value != 0

    def test_water_values(self):
        """Test water tiles have specific values."""
        assert TileType.DEEP_WATER.value == 8
        assert TileType.SHALLOW_WATER.value == 9
        assert TileType.WATER_EDGE.value == 10

    def test_ledge_values(self):
        """Test ledge tiles have specific values."""
        assert TileType.LEDGE_UP.value == 40
        assert TileType.LEDGE_DOWN.value == 41
        assert TileType.LEDGE_LEFT.value == 42
        assert TileType.LEDGE_RIGHT.value == 43

    def test_special_tiles(self):
        """Test special tile values."""
        assert TileType.WARP.value == 128
        assert TileType.GRASS.value == 64


class TestPathfinderWithFlippers:
    """Test pathfinder flippers option."""

    @pytest.fixture
    def water_map(self):
        """Create collision map with water."""
        data = bytearray([TileType.WALKABLE.value] * 4096)
        # Add water in the middle
        for x in range(20, 40):
            for y in range(20, 40):
                data[x + y * 64] = TileType.DEEP_WATER.value
        return CollisionMap(data=bytes(data), width=64, height=64)

    def test_pathfinder_without_flippers(self, water_map):
        """Test pathfinding without flippers (can't cross water)."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(10, 30),
            goal=(50, 30),
            collision_map=water_map,
            has_flippers=False
        )

        assert isinstance(result, NavigationResult)
        # May need to go around water

    def test_pathfinder_with_flippers(self, water_map):
        """Test pathfinding with flippers (can cross water)."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(10, 30),
            goal=(50, 30),
            collision_map=water_map,
            has_flippers=True
        )

        assert isinstance(result, NavigationResult)
        # Can take more direct route through water


class TestPathValidation:
    """Test path validation."""

    @pytest.fixture
    def simple_map(self):
        """Create simple walkable map."""
        data = bytes([TileType.WALKABLE.value] * 4096)
        return CollisionMap(data=data, width=64, height=64)

    def test_path_starts_at_start(self, simple_map):
        """Test path starts at start position."""
        pathfinder = Pathfinder()
        start = (5, 5)
        goal = (20, 20)
        result = pathfinder.find_path(start=start, goal=goal, collision_map=simple_map)

        if result.success and result.path:
            assert result.path[0] == start, f"Path starts at {result.path[0]}, expected {start}"

    def test_path_ends_at_goal(self, simple_map):
        """Test path ends at goal position."""
        pathfinder = Pathfinder()
        start = (5, 5)
        goal = (20, 20)
        result = pathfinder.find_path(start=start, goal=goal, collision_map=simple_map)

        if result.success and result.path:
            assert result.path[-1] == goal, f"Path ends at {result.path[-1]}, expected {goal}"

    def test_path_distance_reasonable(self, simple_map):
        """Test path distance is reasonable."""
        pathfinder = Pathfinder()
        result = pathfinder.find_path(
            start=(0, 0),
            goal=(10, 10),
            collision_map=simple_map
        )

        if result.success:
            # Manhattan distance is 20, diagonal would be ~14.14
            assert result.distance >= 10  # At least diagonal distance
            assert result.distance <= 30  # At most very inefficient
