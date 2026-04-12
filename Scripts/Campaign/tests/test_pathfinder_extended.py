"""Extended tests for Pathfinder and navigation components.

Campaign Goals Supported:
- C.3: Comprehensive test infrastructure
- A.2: Navigate overworld to specific locations

These tests verify the pathfinding system including collision maps,
A* algorithm, and path-to-input conversion.
"""

import pytest
from pathlib import Path
from unittest.mock import Mock, MagicMock, patch

import sys

# Add project root to path for imports
project_root = Path(__file__).parent.parent.parent.parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from scripts.campaign.pathfinder import (
    TileType, WALKABLE_TILES, SWIM_TILES, LEDGE_TILES,
    CollisionMap, PathNode, NavigationResult, Pathfinder,
    get_pathfinder, find_path
)


class TestTileTypeEnum:
    """Test TileType IntEnum."""

    def test_walkable_value(self):
        """Test WALKABLE value."""
        assert TileType.WALKABLE == 0x00

    def test_solid_value(self):
        """Test SOLID value."""
        assert TileType.SOLID == 0x01

    def test_deep_water_value(self):
        """Test DEEP_WATER value."""
        assert TileType.DEEP_WATER == 0x08

    def test_shallow_water_value(self):
        """Test SHALLOW_WATER value."""
        assert TileType.SHALLOW_WATER == 0x09

    def test_water_edge_value(self):
        """Test WATER_EDGE value."""
        assert TileType.WATER_EDGE == 0x0A

    def test_pit_value(self):
        """Test PIT value."""
        assert TileType.PIT == 0x20

    def test_ladder_value(self):
        """Test LADDER value."""
        assert TileType.LADDER == 0x22

    def test_ledge_values(self):
        """Test LEDGE values."""
        assert TileType.LEDGE_UP == 0x28
        assert TileType.LEDGE_DOWN == 0x29
        assert TileType.LEDGE_LEFT == 0x2A
        assert TileType.LEDGE_RIGHT == 0x2B

    def test_grass_value(self):
        """Test GRASS value."""
        assert TileType.GRASS == 0x40

    def test_damage_floor_value(self):
        """Test DAMAGE_FLOOR value."""
        assert TileType.DAMAGE_FLOOR == 0x60

    def test_spike_value(self):
        """Test SPIKE value."""
        assert TileType.SPIKE == 0x62

    def test_warp_value(self):
        """Test WARP value."""
        assert TileType.WARP == 0x80


class TestTileSets:
    """Test predefined tile sets."""

    def test_walkable_tiles_contains_walkable(self):
        """Test WALKABLE_TILES contains WALKABLE."""
        assert TileType.WALKABLE in WALKABLE_TILES

    def test_walkable_tiles_contains_grass(self):
        """Test WALKABLE_TILES contains GRASS."""
        assert TileType.GRASS in WALKABLE_TILES

    def test_walkable_tiles_contains_shallow_water(self):
        """Test WALKABLE_TILES contains SHALLOW_WATER."""
        assert TileType.SHALLOW_WATER in WALKABLE_TILES

    def test_walkable_tiles_contains_ladder(self):
        """Test WALKABLE_TILES contains LADDER."""
        assert TileType.LADDER in WALKABLE_TILES

    def test_walkable_tiles_not_contains_solid(self):
        """Test WALKABLE_TILES does not contain SOLID."""
        assert TileType.SOLID not in WALKABLE_TILES

    def test_swim_tiles_contains_deep_water(self):
        """Test SWIM_TILES contains DEEP_WATER."""
        assert TileType.DEEP_WATER in SWIM_TILES

    def test_ledge_tiles_contains_all_ledges(self):
        """Test LEDGE_TILES contains all ledge types."""
        assert TileType.LEDGE_UP in LEDGE_TILES
        assert TileType.LEDGE_DOWN in LEDGE_TILES
        assert TileType.LEDGE_LEFT in LEDGE_TILES
        assert TileType.LEDGE_RIGHT in LEDGE_TILES


class TestCollisionMapConstants:
    """Test CollisionMap class constants."""

    def test_colmapa_address(self):
        """Test COLMAPA_ADDR constant."""
        assert CollisionMap.COLMAPA_ADDR == 0x7F2000

    def test_colmapb_address(self):
        """Test COLMAPB_ADDR constant."""
        assert CollisionMap.COLMAPB_ADDR == 0x7F6000

    def test_map_size(self):
        """Test MAP_SIZE constant."""
        assert CollisionMap.MAP_SIZE == 0x1000


class TestCollisionMapCreation:
    """Test CollisionMap dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic collision map."""
        data = bytes([0] * 100)
        cmap = CollisionMap(data=data)
        assert cmap.data == data

    def test_default_dimensions(self):
        """Test default dimensions."""
        cmap = CollisionMap(data=bytes(100))
        assert cmap.width == 64
        assert cmap.height == 64
        assert cmap.tile_size == 8

    def test_custom_dimensions(self):
        """Test custom dimensions."""
        cmap = CollisionMap(data=bytes(100), width=32, height=32, tile_size=16)
        assert cmap.width == 32
        assert cmap.height == 32
        assert cmap.tile_size == 16


class TestCollisionMapGetTile:
    """Test CollisionMap get_tile method."""

    @pytest.fixture
    def collision_map(self):
        """Create collision map with known pattern."""
        # 64x64 map with some non-walkable tiles
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Place solid tile at (5, 5)
        data[5 * 64 + 5] = TileType.SOLID
        # Place deep water at (10, 10)
        data[10 * 64 + 10] = TileType.DEEP_WATER
        return CollisionMap(data=bytes(data))

    def test_get_walkable_tile(self, collision_map):
        """Test getting walkable tile."""
        assert collision_map.get_tile(0, 0) == TileType.WALKABLE

    def test_get_solid_tile(self, collision_map):
        """Test getting solid tile."""
        assert collision_map.get_tile(5, 5) == TileType.SOLID

    def test_get_deep_water_tile(self, collision_map):
        """Test getting deep water tile."""
        assert collision_map.get_tile(10, 10) == TileType.DEEP_WATER

    def test_get_out_of_bounds_returns_solid(self, collision_map):
        """Test out of bounds returns SOLID."""
        assert collision_map.get_tile(-1, 0) == TileType.SOLID
        assert collision_map.get_tile(0, -1) == TileType.SOLID
        assert collision_map.get_tile(100, 0) == TileType.SOLID
        assert collision_map.get_tile(0, 100) == TileType.SOLID


class TestCollisionMapGetTileAtPixel:
    """Test CollisionMap get_tile_at_pixel method."""

    @pytest.fixture
    def collision_map(self):
        """Create collision map."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Place solid at tile (1, 1)
        data[1 * 64 + 1] = TileType.SOLID
        return CollisionMap(data=bytes(data))

    def test_pixel_to_tile_origin(self, collision_map):
        """Test pixel at origin maps to tile 0,0."""
        assert collision_map.get_tile_at_pixel(0, 0) == TileType.WALKABLE

    def test_pixel_to_tile_offset(self, collision_map):
        """Test pixel at (12, 12) maps to tile 1,1."""
        # Tile size is 8, so (12, 12) -> tile (1, 1)
        assert collision_map.get_tile_at_pixel(12, 12) == TileType.SOLID

    def test_pixel_to_tile_boundary(self, collision_map):
        """Test pixel at tile boundary."""
        # (7, 7) is still tile 0,0
        assert collision_map.get_tile_at_pixel(7, 7) == TileType.WALKABLE
        # (8, 8) is tile 1,1
        assert collision_map.get_tile_at_pixel(8, 8) == TileType.SOLID


class TestCollisionMapIsWalkable:
    """Test CollisionMap is_walkable method."""

    @pytest.fixture
    def collision_map(self):
        """Create collision map with various tiles."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[1 * 64 + 1] = TileType.SOLID
        data[2 * 64 + 2] = TileType.DEEP_WATER
        data[3 * 64 + 3] = TileType.GRASS
        return CollisionMap(data=bytes(data))

    def test_walkable_is_walkable(self, collision_map):
        """Test WALKABLE tile is walkable."""
        assert collision_map.is_walkable(0, 0) is True

    def test_solid_not_walkable(self, collision_map):
        """Test SOLID tile is not walkable."""
        assert collision_map.is_walkable(1, 1) is False

    def test_deep_water_not_walkable_without_flippers(self, collision_map):
        """Test DEEP_WATER is not walkable without flippers."""
        assert collision_map.is_walkable(2, 2) is False

    def test_deep_water_walkable_with_flippers(self, collision_map):
        """Test DEEP_WATER is walkable with flippers."""
        assert collision_map.is_walkable(2, 2, has_flippers=True) is True

    def test_grass_is_walkable(self, collision_map):
        """Test GRASS tile is walkable."""
        assert collision_map.is_walkable(3, 3) is True


class TestCollisionMapGetNeighbors:
    """Test CollisionMap get_neighbors method."""

    @pytest.fixture
    def collision_map(self):
        """Create collision map with walkable center."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        return CollisionMap(data=bytes(data))

    def test_neighbors_all_walkable(self, collision_map):
        """Test all neighbors returned when walkable."""
        neighbors = collision_map.get_neighbors(5, 5)
        assert (4, 5) in neighbors  # Left
        assert (6, 5) in neighbors  # Right
        assert (5, 4) in neighbors  # Up
        assert (5, 6) in neighbors  # Down
        assert len(neighbors) == 4

    def test_neighbors_with_solid(self):
        """Test solid neighbors not returned."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5 * 64 + 4] = TileType.SOLID  # (4, 5) is solid
        cmap = CollisionMap(data=bytes(data))

        neighbors = cmap.get_neighbors(5, 5)
        assert (4, 5) not in neighbors
        assert len(neighbors) == 3


class TestPathNodeCreation:
    """Test PathNode dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic path node."""
        node = PathNode(x=10, y=20)
        assert node.x == 10
        assert node.y == 20

    def test_default_costs(self):
        """Test default cost values."""
        node = PathNode(x=0, y=0)
        assert node.g_cost == 0.0
        assert node.h_cost == 0.0

    def test_default_parent(self):
        """Test default parent is None."""
        node = PathNode(x=0, y=0)
        assert node.parent is None


class TestPathNodeProperties:
    """Test PathNode properties."""

    def test_f_cost_sum(self):
        """Test f_cost is sum of g and h."""
        node = PathNode(x=0, y=0, g_cost=5.0, h_cost=10.0)
        assert node.f_cost == 15.0

    def test_f_cost_zero(self):
        """Test f_cost is zero when costs are zero."""
        node = PathNode(x=0, y=0)
        assert node.f_cost == 0.0


class TestPathNodeComparison:
    """Test PathNode comparison methods."""

    def test_lt_comparison(self):
        """Test less than comparison by f_cost."""
        node1 = PathNode(x=0, y=0, g_cost=5.0, h_cost=5.0)  # f=10
        node2 = PathNode(x=1, y=1, g_cost=10.0, h_cost=10.0)  # f=20
        assert node1 < node2
        assert not (node2 < node1)

    def test_eq_by_position(self):
        """Test equality is based on position."""
        node1 = PathNode(x=5, y=5, g_cost=10.0)
        node2 = PathNode(x=5, y=5, g_cost=20.0)  # Same position, different cost
        assert node1 == node2

    def test_eq_different_position(self):
        """Test inequality for different positions."""
        node1 = PathNode(x=5, y=5)
        node2 = PathNode(x=5, y=6)
        assert not (node1 == node2)

    def test_hash_by_position(self):
        """Test hash is based on position."""
        node1 = PathNode(x=5, y=5, g_cost=10.0)
        node2 = PathNode(x=5, y=5, g_cost=20.0)
        assert hash(node1) == hash(node2)


class TestNavigationResultCreation:
    """Test NavigationResult dataclass creation."""

    def test_basic_creation(self):
        """Test creating basic result."""
        result = NavigationResult(success=True, path=[(0, 0), (1, 1)])
        assert result.success is True
        assert result.path == [(0, 0), (1, 1)]

    def test_default_distance(self):
        """Test default distance is 0."""
        result = NavigationResult(success=True, path=[])
        assert result.distance == 0.0

    def test_default_blocked_at(self):
        """Test default blocked_at is None."""
        result = NavigationResult(success=True, path=[])
        assert result.blocked_at is None

    def test_default_reason(self):
        """Test default reason is empty."""
        result = NavigationResult(success=True, path=[])
        assert result.reason == ""

    def test_with_blocked_at(self):
        """Test result with blocked position."""
        result = NavigationResult(
            success=False,
            path=[],
            blocked_at=(5, 5),
            reason="Hit solid tile"
        )
        assert result.blocked_at == (5, 5)
        assert result.reason == "Hit solid tile"


class TestPathfinderCreation:
    """Test Pathfinder creation."""

    def test_creation_without_emulator(self):
        """Test creating pathfinder without emulator."""
        pf = Pathfinder()
        assert pf.emulator is None

    def test_creation_with_emulator(self):
        """Test creating pathfinder with emulator."""
        mock_emu = Mock()
        pf = Pathfinder(emulator=mock_emu)
        assert pf.emulator is mock_emu

    def test_initial_cache_none(self):
        """Test initial collision cache is None."""
        pf = Pathfinder()
        assert pf._collision_cache is None

    def test_default_cache_ttl(self):
        """Test default cache TTL."""
        pf = Pathfinder()
        assert pf.cache_ttl == 1.0


class TestPathfinderHeuristic:
    """Test Pathfinder heuristic method."""

    def test_heuristic_same_point(self):
        """Test heuristic at same point is 0."""
        assert Pathfinder.heuristic((5, 5), (5, 5)) == 0

    def test_heuristic_horizontal(self):
        """Test heuristic for horizontal distance."""
        assert Pathfinder.heuristic((0, 0), (10, 0)) == 10

    def test_heuristic_vertical(self):
        """Test heuristic for vertical distance."""
        assert Pathfinder.heuristic((0, 0), (0, 10)) == 10

    def test_heuristic_diagonal(self):
        """Test heuristic for diagonal (Manhattan) distance."""
        # Manhattan distance: |5-0| + |5-0| = 10
        assert Pathfinder.heuristic((0, 0), (5, 5)) == 10

    def test_heuristic_negative_coords(self):
        """Test heuristic with negative-ish coords."""
        # Uses absolute values
        assert Pathfinder.heuristic((10, 10), (5, 5)) == 10


class TestPathfinderFindPath:
    """Test Pathfinder find_path method."""

    @pytest.fixture
    def walkable_map(self):
        """Create fully walkable collision map."""
        data = bytes([TileType.WALKABLE] * (64 * 64))
        return CollisionMap(data=data)

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder without emulator."""
        return Pathfinder()

    def test_path_same_point(self, pathfinder, walkable_map):
        """Test path from point to itself."""
        result = pathfinder.find_path((5, 5), (5, 5), collision_map=walkable_map)
        assert result.success is True
        assert len(result.path) == 1
        assert result.path[0] == (5, 5)

    def test_path_adjacent_point(self, pathfinder, walkable_map):
        """Test path to adjacent point."""
        result = pathfinder.find_path((5, 5), (6, 5), collision_map=walkable_map)
        assert result.success is True
        assert len(result.path) == 2
        assert result.path[0] == (5, 5)
        assert result.path[1] == (6, 5)

    def test_path_straight_line(self, pathfinder, walkable_map):
        """Test path in straight line."""
        result = pathfinder.find_path((0, 0), (5, 0), collision_map=walkable_map)
        assert result.success is True
        assert len(result.path) == 6  # Start + 5 moves
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (5, 0)

    def test_path_around_obstacle(self, pathfinder):
        """Test path routes around obstacle."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Create a wall at x=3
        for y in range(10):
            data[y * 64 + 3] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        # Path from (0, 5) to (6, 5) must go around
        result = pathfinder.find_path((0, 5), (6, 5), collision_map=cmap)
        assert result.success is True
        # Path should not cross x=3 at y<10
        for x, y in result.path:
            if y < 10:
                assert x != 3

    def test_path_start_unwalkable(self, pathfinder):
        """Test path fails if start is unwalkable."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[5 * 64 + 5] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((5, 5), (10, 10), collision_map=cmap)
        assert result.success is False
        assert "not walkable" in result.reason.lower()

    def test_path_goal_unwalkable(self, pathfinder):
        """Test path fails if goal is unwalkable."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        data[10 * 64 + 10] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((5, 5), (10, 10), collision_map=cmap)
        assert result.success is False
        assert "not walkable" in result.reason.lower()

    def test_path_no_path_exists(self, pathfinder):
        """Test path fails when no path exists."""
        data = bytearray([TileType.WALKABLE] * (64 * 64))
        # Create a complete wall around goal
        for x in range(9, 12):
            for y in range(9, 12):
                if x != 10 or y != 10:  # Leave goal walkable
                    data[y * 64 + x] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        result = pathfinder.find_path((0, 0), (10, 10), collision_map=cmap)
        assert result.success is False


class TestPathfinderFindPathPixels:
    """Test Pathfinder find_path_pixels method."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder."""
        return Pathfinder()

    @pytest.fixture
    def walkable_map(self):
        """Create walkable collision map."""
        return CollisionMap(data=bytes([TileType.WALKABLE] * (64 * 64)))

    def test_pixel_to_tile_conversion(self, pathfinder, walkable_map):
        """Test pixel coordinates converted to tiles."""
        # Pixels (0, 0) and (40, 40) -> tiles (0, 0) and (5, 5)
        result = pathfinder.find_path_pixels(
            (0, 0), (40, 40), collision_map=walkable_map
        )
        assert result.success is True
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (5, 5)


class TestPathfinderPathToInputs:
    """Test Pathfinder path_to_inputs method."""

    @pytest.fixture
    def pathfinder(self):
        """Create pathfinder."""
        return Pathfinder()

    def test_empty_path(self, pathfinder):
        """Test empty path returns empty inputs."""
        inputs = pathfinder.path_to_inputs([])
        assert inputs == []

    def test_single_point_path(self, pathfinder):
        """Test single point path returns empty inputs."""
        inputs = pathfinder.path_to_inputs([(5, 5)])
        assert inputs == []

    def test_right_movement(self, pathfinder):
        """Test right movement generates RIGHT input."""
        inputs = pathfinder.path_to_inputs([(0, 0), (1, 0)])
        assert len(inputs) == 1
        assert inputs[0][0] == "RIGHT"

    def test_left_movement(self, pathfinder):
        """Test left movement generates LEFT input."""
        inputs = pathfinder.path_to_inputs([(1, 0), (0, 0)])
        assert len(inputs) == 1
        assert inputs[0][0] == "LEFT"

    def test_down_movement(self, pathfinder):
        """Test down movement generates DOWN input."""
        inputs = pathfinder.path_to_inputs([(0, 0), (0, 1)])
        assert len(inputs) == 1
        assert inputs[0][0] == "DOWN"

    def test_up_movement(self, pathfinder):
        """Test up movement generates UP input."""
        inputs = pathfinder.path_to_inputs([(0, 1), (0, 0)])
        assert len(inputs) == 1
        assert inputs[0][0] == "UP"

    def test_consecutive_same_direction_merged(self, pathfinder):
        """Test consecutive same-direction moves are merged."""
        inputs = pathfinder.path_to_inputs([(0, 0), (1, 0), (2, 0)])
        assert len(inputs) == 1
        assert inputs[0][0] == "RIGHT"
        assert inputs[0][1] == 16  # 2 moves * 8 frames

    def test_direction_change(self, pathfinder):
        """Test direction changes create new inputs."""
        inputs = pathfinder.path_to_inputs([(0, 0), (1, 0), (1, 1)])
        assert len(inputs) == 2
        assert inputs[0][0] == "RIGHT"
        assert inputs[1][0] == "DOWN"

    def test_custom_frames_per_tile(self, pathfinder):
        """Test custom frames_per_tile."""
        inputs = pathfinder.path_to_inputs([(0, 0), (1, 0)], frames_per_tile=16)
        assert inputs[0][1] == 16


class TestGetPathfinderSingleton:
    """Test get_pathfinder singleton function."""

    def test_creates_pathfinder(self):
        """Test creates new pathfinder."""
        # Reset singleton for test
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        pf = get_pathfinder()
        assert pf is not None
        assert isinstance(pf, Pathfinder)

    def test_returns_same_instance(self):
        """Test returns same instance on subsequent calls."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        pf1 = get_pathfinder()
        pf2 = get_pathfinder()
        assert pf1 is pf2

    def test_attaches_emulator(self):
        """Test attaches emulator to existing pathfinder."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        pf1 = get_pathfinder()  # No emulator
        assert pf1.emulator is None

        mock_emu = Mock()
        pf2 = get_pathfinder(emulator=mock_emu)
        assert pf2.emulator is mock_emu
        assert pf1 is pf2  # Same instance


class TestFindPathConvenience:
    """Test find_path convenience function."""

    def test_with_collision_data(self):
        """Test find_path with raw collision data."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        data = bytes([TileType.WALKABLE] * (64 * 64))
        result = find_path((0, 0), (5, 5), collision_data=data)
        assert result.success is True

    def test_path_straight_line(self):
        """Test find_path for straight line."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        data = bytes([TileType.WALKABLE] * (64 * 64))
        result = find_path((0, 0), (3, 0), collision_data=data)
        assert result.success is True
        assert len(result.path) == 4


class TestPathNodeWithParent:
    """Test PathNode parent chain."""

    def test_path_reconstruction(self):
        """Test path can be reconstructed from parent chain."""
        node1 = PathNode(x=0, y=0)
        node2 = PathNode(x=1, y=0, parent=node1)
        node3 = PathNode(x=2, y=0, parent=node2)

        # Reconstruct path
        path = []
        node = node3
        while node is not None:
            path.append((node.x, node.y))
            node = node.parent
        path.reverse()

        assert path == [(0, 0), (1, 0), (2, 0)]


class TestCollisionMapEdgeCases:
    """Test CollisionMap edge cases."""

    def test_empty_data(self):
        """Test collision map with empty data."""
        cmap = CollisionMap(data=bytes())
        assert cmap.get_tile(0, 0) == TileType.SOLID  # Out of bounds

    def test_small_data(self):
        """Test collision map with smaller than expected data."""
        cmap = CollisionMap(data=bytes([TileType.WALKABLE] * 10))
        assert cmap.get_tile(0, 0) == TileType.WALKABLE
        assert cmap.get_tile(5, 5) == TileType.SOLID  # Index 325 out of range
