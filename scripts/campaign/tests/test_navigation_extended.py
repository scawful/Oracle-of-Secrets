"""Iteration 54 - Extended Navigation Tests.

Tests for pathfinding algorithm edge cases, complex navigation scenarios,
tile interactions, and path optimization.

Focus: A* algorithm edge cases, maze navigation, direction merging,
tile type interactions, path optimization, blocked path scenarios.
"""

import pytest
from unittest.mock import MagicMock, patch

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


# =============================================================================
# Helper Functions
# =============================================================================

def _collision_map(pattern: str, width: int = 8, height: int = 8) -> CollisionMap:
    """Create collision map from ASCII pattern.

    '.' = walkable (0x00)
    '#' = solid (0x01)
    'W' = deep water (0x08)
    'w' = shallow water (0x09)
    'G' = grass (0x40)
    'L' = ladder (0x22)
    'P' = pit (0x20)
    'S' = spike (0x62)
    """
    char_to_tile = {
        '.': TileType.WALKABLE,
        '#': TileType.SOLID,
        'W': TileType.DEEP_WATER,
        'w': TileType.SHALLOW_WATER,
        'G': TileType.GRASS,
        'L': TileType.LADDER,
        'P': TileType.PIT,
        'S': TileType.SPIKE,
    }

    lines = pattern.strip().split('\n')
    data = bytearray()

    for line in lines:
        for char in line.strip():
            data.append(char_to_tile.get(char, TileType.SOLID))

    # Pad to expected size
    expected_size = width * height
    while len(data) < expected_size:
        data.append(TileType.SOLID)

    return CollisionMap(data=bytes(data), width=width, height=height)


def _simple_map(size: int = 64) -> CollisionMap:
    """Create simple all-walkable collision map."""
    return CollisionMap(data=bytes([TileType.WALKABLE] * (size * size)), width=size, height=size)


# =============================================================================
# TileType Extended Tests
# =============================================================================

class TestTileTypeExtended:
    """Extended tests for TileType enum."""

    def test_all_tile_values_distinct(self):
        """All tile types have distinct values."""
        values = [t.value for t in TileType]
        assert len(values) == len(set(values))

    def test_walkable_tiles_set(self):
        """WALKABLE_TILES contains expected tiles."""
        assert TileType.WALKABLE in WALKABLE_TILES
        assert TileType.GRASS in WALKABLE_TILES
        assert TileType.SHALLOW_WATER in WALKABLE_TILES
        assert TileType.SOLID not in WALKABLE_TILES

    def test_swim_tiles_set(self):
        """SWIM_TILES contains only deep water."""
        assert TileType.DEEP_WATER in SWIM_TILES
        assert len(SWIM_TILES) == 1

    def test_ledge_tiles_set(self):
        """LEDGE_TILES contains all ledge types."""
        assert TileType.LEDGE_UP in LEDGE_TILES
        assert TileType.LEDGE_DOWN in LEDGE_TILES
        assert TileType.LEDGE_LEFT in LEDGE_TILES
        assert TileType.LEDGE_RIGHT in LEDGE_TILES
        assert len(LEDGE_TILES) == 4

    def test_damage_tiles(self):
        """Damage tiles have correct values."""
        assert TileType.DAMAGE_FLOOR == 0x60
        assert TileType.SPIKE == 0x62

    def test_warp_tile(self):
        """Warp tile has correct value."""
        assert TileType.WARP == 0x80


# =============================================================================
# CollisionMap Extended Tests
# =============================================================================

class TestCollisionMapExtended:
    """Extended tests for CollisionMap."""

    def test_get_tile_out_of_bounds_negative(self):
        """Negative coordinates return SOLID."""
        cmap = _simple_map()
        assert cmap.get_tile(-1, 0) == TileType.SOLID
        assert cmap.get_tile(0, -1) == TileType.SOLID
        assert cmap.get_tile(-10, -10) == TileType.SOLID

    def test_get_tile_out_of_bounds_overflow(self):
        """Overflow coordinates return SOLID."""
        cmap = _simple_map(size=8)
        assert cmap.get_tile(8, 0) == TileType.SOLID
        assert cmap.get_tile(0, 8) == TileType.SOLID
        assert cmap.get_tile(100, 100) == TileType.SOLID

    def test_get_tile_at_pixel_conversion(self):
        """Pixel to tile conversion is correct."""
        cmap = _simple_map()
        # Each tile is 8 pixels
        assert cmap.get_tile_at_pixel(0, 0) == cmap.get_tile(0, 0)
        assert cmap.get_tile_at_pixel(7, 7) == cmap.get_tile(0, 0)
        assert cmap.get_tile_at_pixel(8, 8) == cmap.get_tile(1, 1)
        assert cmap.get_tile_at_pixel(16, 24) == cmap.get_tile(2, 3)

    def test_is_walkable_various_tiles(self):
        """is_walkable works for various tile types."""
        pattern = """
        .#WwGL
        ......
        """
        cmap = _collision_map(pattern, width=6, height=2)

        # Row 0
        assert cmap.is_walkable(0, 0) is True   # walkable
        assert cmap.is_walkable(1, 0) is False  # solid
        assert cmap.is_walkable(2, 0) is False  # deep water (no flippers)
        assert cmap.is_walkable(3, 0) is True   # shallow water
        assert cmap.is_walkable(4, 0) is True   # grass
        assert cmap.is_walkable(5, 0) is True   # ladder

    def test_is_walkable_with_flippers(self):
        """Deep water is walkable with flippers."""
        pattern = "W"
        cmap = _collision_map(pattern, width=1, height=1)

        assert cmap.is_walkable(0, 0) is False
        assert cmap.is_walkable(0, 0, has_flippers=True) is True

    def test_get_neighbors_cardinal(self):
        """get_neighbors returns only cardinal directions."""
        pattern = """
        ...
        ...
        ...
        """
        cmap = _collision_map(pattern, width=3, height=3)
        neighbors = cmap.get_neighbors(1, 1)

        # Should have 4 cardinal neighbors, not 8
        assert len(neighbors) == 4
        assert (0, 1) in neighbors  # left
        assert (2, 1) in neighbors  # right
        assert (1, 0) in neighbors  # up
        assert (1, 2) in neighbors  # down

    def test_get_neighbors_corner(self):
        """get_neighbors handles corners correctly."""
        cmap = _simple_map(size=8)
        neighbors = cmap.get_neighbors(0, 0)

        # Corner has only 2 valid neighbors
        assert len(neighbors) == 2
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_get_neighbors_blocked(self):
        """get_neighbors excludes blocked tiles."""
        pattern = """
        .#.
        #.#
        .#.
        """
        cmap = _collision_map(pattern, width=3, height=3)
        neighbors = cmap.get_neighbors(1, 1)

        # Center is surrounded by walls
        assert len(neighbors) == 0

    def test_get_neighbors_with_flippers(self):
        """get_neighbors includes water with flippers."""
        pattern = """
        .W.
        W.W
        .W.
        """
        cmap = _collision_map(pattern, width=3, height=3)

        # Without flippers
        neighbors = cmap.get_neighbors(1, 1)
        assert len(neighbors) == 0

        # With flippers
        neighbors = cmap.get_neighbors(1, 1, has_flippers=True)
        assert len(neighbors) == 4


# =============================================================================
# PathNode Extended Tests
# =============================================================================

class TestPathNodeExtended:
    """Extended tests for PathNode."""

    def test_f_cost_calculation(self):
        """f_cost is sum of g_cost and h_cost."""
        node = PathNode(x=0, y=0, g_cost=5.0, h_cost=10.0)
        assert node.f_cost == 15.0

    def test_node_comparison_by_f_cost(self):
        """Nodes compare by f_cost."""
        node1 = PathNode(x=0, y=0, g_cost=5.0, h_cost=5.0)   # f=10
        node2 = PathNode(x=1, y=1, g_cost=3.0, h_cost=5.0)   # f=8
        node3 = PathNode(x=2, y=2, g_cost=10.0, h_cost=5.0)  # f=15

        assert node2 < node1 < node3

    def test_node_equality_by_position(self):
        """Nodes are equal if same position."""
        node1 = PathNode(x=5, y=10, g_cost=1.0)
        node2 = PathNode(x=5, y=10, g_cost=99.0)  # Different cost
        node3 = PathNode(x=5, y=11)

        assert node1 == node2
        assert node1 != node3

    def test_node_hash_by_position(self):
        """Node hash based on position."""
        node1 = PathNode(x=5, y=10)
        node2 = PathNode(x=5, y=10, g_cost=99.0)

        assert hash(node1) == hash(node2)

    def test_node_in_set(self):
        """Nodes can be stored in sets."""
        node1 = PathNode(x=0, y=0)
        node2 = PathNode(x=0, y=0, g_cost=10.0)
        node3 = PathNode(x=1, y=0)

        node_set = {node1, node3}
        assert node2 in node_set  # Same position as node1

    def test_node_parent_chain(self):
        """Node parent chain reconstructs path."""
        root = PathNode(x=0, y=0)
        n1 = PathNode(x=1, y=0, parent=root)
        n2 = PathNode(x=2, y=0, parent=n1)
        n3 = PathNode(x=3, y=0, parent=n2)

        path = []
        node = n3
        while node is not None:
            path.append((node.x, node.y))
            node = node.parent

        path.reverse()
        assert path == [(0, 0), (1, 0), (2, 0), (3, 0)]


# =============================================================================
# NavigationResult Tests
# =============================================================================

class TestNavigationResult:
    """Tests for NavigationResult."""

    def test_successful_result(self):
        """Successful navigation result."""
        result = NavigationResult(
            success=True,
            path=[(0, 0), (1, 0), (2, 0)],
            distance=2.0
        )
        assert result.success is True
        assert len(result.path) == 3
        assert result.distance == 2.0

    def test_failed_result_blocked(self):
        """Failed navigation with blocked position."""
        result = NavigationResult(
            success=False,
            path=[],
            blocked_at=(5, 5),
            reason="Path blocked"
        )
        assert result.success is False
        assert result.blocked_at == (5, 5)

    def test_failed_result_no_path(self):
        """Failed navigation with no path found."""
        result = NavigationResult(
            success=False,
            path=[],
            reason="No path found"
        )
        assert result.success is False
        assert len(result.path) == 0


# =============================================================================
# Pathfinder A* Algorithm Tests
# =============================================================================

class TestPathfinderAlgorithm:
    """Tests for A* pathfinding algorithm."""

    def test_same_start_and_goal(self):
        """Path to same position is just that position."""
        pf = Pathfinder()
        cmap = _simple_map()
        result = pf.find_path((5, 5), (5, 5), collision_map=cmap)

        assert result.success is True
        assert result.path == [(5, 5)]
        assert result.distance == 0

    def test_adjacent_path(self):
        """Path to adjacent tile."""
        pf = Pathfinder()
        cmap = _simple_map()
        result = pf.find_path((5, 5), (6, 5), collision_map=cmap)

        assert result.success is True
        assert result.path == [(5, 5), (6, 5)]
        assert result.distance == 1

    def test_straight_line_path(self):
        """Path in straight line."""
        pf = Pathfinder()
        cmap = _simple_map()
        result = pf.find_path((0, 0), (5, 0), collision_map=cmap)

        assert result.success is True
        assert len(result.path) == 6
        assert result.distance == 5

    def test_diagonal_path(self):
        """Path that requires diagonal movement."""
        pf = Pathfinder()
        cmap = _simple_map()
        result = pf.find_path((0, 0), (3, 3), collision_map=cmap)

        assert result.success is True
        # Manhattan distance is 6 (3 right + 3 down)
        assert result.distance == 6

    def test_path_around_obstacle(self):
        """Path navigates around single obstacle."""
        pattern = """
        ........
        ........
        ........
        ...#....
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 3), (7, 3), collision_map=cmap)

        assert result.success is True
        # Path should avoid obstacle at (3, 3)
        assert (3, 3) not in result.path

    def test_path_through_corridor(self):
        """Path through narrow corridor."""
        pattern = """
        ########
        ........
        ########
        ########
        ########
        ########
        ########
        ########
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 1), (7, 1), collision_map=cmap)

        assert result.success is True
        # All steps should be on row 1
        for x, y in result.path:
            assert y == 1

    def test_path_through_maze(self):
        """Path through simple maze."""
        pattern = """
        .#......
        .#.####.
        .#.#....
        .#.#.###
        .#.#....
        .#.####.
        .#......
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (7, 0), collision_map=cmap)

        assert result.success is True
        # Path exists but is long due to maze
        assert result.distance > 10

    def test_no_path_blocked_goal(self):
        """No path when goal is blocked."""
        pattern = """
        ........
        ........
        ........
        ........
        ........
        ........
        ........
        #######.
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        # Goal is on solid tile
        cmap_data = bytearray(cmap.data)
        cmap_data[7 * 8 + 7] = TileType.SOLID
        cmap = CollisionMap(data=bytes(cmap_data), width=8, height=8)

        result = pf.find_path((0, 0), (7, 7), collision_map=cmap)

        assert result.success is False
        assert "not walkable" in result.reason

    def test_no_path_blocked_start(self):
        """No path when start is blocked."""
        cmap_data = bytes([TileType.SOLID] + [TileType.WALKABLE] * 63)
        cmap = CollisionMap(data=cmap_data, width=8, height=8)
        pf = Pathfinder()

        result = pf.find_path((0, 0), (7, 7), collision_map=cmap)

        assert result.success is False
        assert "not walkable" in result.reason

    def test_no_path_isolated(self):
        """No path when areas are isolated."""
        pattern = """
        ....#...
        ....#...
        ....#...
        ....#...
        ....#...
        ....#...
        ....#...
        ....#...
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        # Both sides are walkable but separated by wall
        result = pf.find_path((0, 0), (7, 0), collision_map=cmap)

        assert result.success is False
        assert "No path found" in result.reason

    def test_max_iterations_limit(self):
        """Path finding respects max_iterations."""
        pf = Pathfinder()
        cmap = _simple_map()
        result = pf.find_path((0, 0), (63, 63), collision_map=cmap, max_iterations=10)

        # With only 10 iterations, can't find long path
        assert result.success is False
        assert "iterations" in result.reason


# =============================================================================
# Pathfinder with Different Tile Types
# =============================================================================

class TestPathfinderTileTypes:
    """Tests for pathfinding with different tile types."""

    def test_path_through_grass(self):
        """Grass tiles are walkable."""
        pattern = """
        .GGG....
        .GGG....
        .GGG....
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (3, 0), collision_map=cmap)

        assert result.success is True

    def test_path_through_shallow_water(self):
        """Shallow water is walkable."""
        pattern = """
        .www....
        .www....
        .www....
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (3, 0), collision_map=cmap)

        assert result.success is True

    def test_path_avoids_deep_water(self):
        """Deep water is avoided without flippers."""
        pattern = """
        .WWW....
        .WWW....
        ........
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (4, 0), collision_map=cmap)

        assert result.success is True
        # Path should go around water (row 2+)
        for x, y in result.path[1:-1]:
            assert y >= 2 or x == 0 or x >= 4

    def test_path_through_deep_water_with_flippers(self):
        """Deep water is walkable with flippers."""
        pattern = """
        .WWW....
        .WWW....
        ........
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (4, 0), collision_map=cmap, has_flippers=True)

        assert result.success is True
        # Should take shorter path through water
        assert result.distance <= 5

    def test_path_through_ladder(self):
        """Ladder tiles are walkable."""
        pattern = """
        .L......
        .L......
        ........
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (2, 0), collision_map=cmap)

        assert result.success is True

    def test_path_avoids_pits(self):
        """Pits are avoided."""
        pattern = """
        .PP.....
        .PP.....
        ........
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (3, 0), collision_map=cmap)

        assert result.success is True
        # Path should avoid pits
        for x, y in result.path:
            assert cmap.get_tile(x, y) != TileType.PIT

    def test_path_avoids_spikes(self):
        """Spikes are avoided."""
        pattern = """
        .SS.....
        .SS.....
        ........
        ........
        ........
        ........
        ........
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        result = pf.find_path((0, 0), (3, 0), collision_map=cmap)

        assert result.success is True
        # Path should avoid spikes
        for x, y in result.path:
            assert cmap.get_tile(x, y) != TileType.SPIKE


# =============================================================================
# Pathfinder Pixel Coordinate Tests
# =============================================================================

class TestPathfinderPixelCoordinates:
    """Tests for pixel coordinate navigation."""

    def test_find_path_pixels_basic(self):
        """Find path using pixel coordinates."""
        pf = Pathfinder()
        cmap = _simple_map()
        # Pixels to tiles: 0-7 = tile 0, 8-15 = tile 1, etc.
        result = pf.find_path_pixels((0, 0), (64, 64), collision_map=cmap)

        assert result.success is True
        # Path should be in tiles (0,0) to (8,8)
        assert result.path[0] == (0, 0)
        assert result.path[-1] == (8, 8)

    def test_find_path_pixels_same_tile(self):
        """Same-tile path in pixel coordinates."""
        pf = Pathfinder()
        cmap = _simple_map()
        # Both in tile (0, 0)
        result = pf.find_path_pixels((1, 2), (5, 6), collision_map=cmap)

        assert result.success is True
        assert len(result.path) == 1

    def test_find_path_pixels_fractional(self):
        """Pixel coordinates round correctly."""
        pf = Pathfinder()
        cmap = _simple_map()
        # Pixel 15 = tile 1, pixel 16 = tile 2
        result = pf.find_path_pixels((15, 15), (16, 16), collision_map=cmap)

        assert result.success is True
        # From tile (1,1) to tile (2,2)
        assert result.path[0] == (1, 1)
        assert result.path[-1] == (2, 2)


# =============================================================================
# Path to Inputs Tests
# =============================================================================

class TestPathToInputs:
    """Tests for converting paths to input commands."""

    def test_path_to_inputs_single_step_right(self):
        """Single step right."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        assert inputs == [("RIGHT", 8)]

    def test_path_to_inputs_single_step_left(self):
        """Single step left."""
        pf = Pathfinder()
        path = [(1, 0), (0, 0)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        assert inputs == [("LEFT", 8)]

    def test_path_to_inputs_single_step_down(self):
        """Single step down."""
        pf = Pathfinder()
        path = [(0, 0), (0, 1)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        assert inputs == [("DOWN", 8)]

    def test_path_to_inputs_single_step_up(self):
        """Single step up."""
        pf = Pathfinder()
        path = [(0, 1), (0, 0)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        assert inputs == [("UP", 8)]

    def test_path_to_inputs_merges_directions(self):
        """Consecutive same-direction steps are merged."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0), (2, 0), (3, 0)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        # 3 right moves merged into one
        assert inputs == [("RIGHT", 24)]

    def test_path_to_inputs_multiple_directions(self):
        """Path with direction changes."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        inputs = pf.path_to_inputs(path, frames_per_tile=8)

        assert len(inputs) == 2
        assert inputs[0] == ("RIGHT", 16)  # 2 right
        assert inputs[1] == ("DOWN", 16)   # 2 down

    def test_path_to_inputs_zigzag(self):
        """Zigzag path produces alternating inputs."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)]
        inputs = pf.path_to_inputs(path, frames_per_tile=10)

        assert len(inputs) == 4
        assert inputs[0] == ("RIGHT", 10)
        assert inputs[1] == ("DOWN", 10)
        assert inputs[2] == ("RIGHT", 10)
        assert inputs[3] == ("DOWN", 10)

    def test_path_to_inputs_empty_path(self):
        """Empty path produces no inputs."""
        pf = Pathfinder()
        inputs = pf.path_to_inputs([], frames_per_tile=8)
        assert inputs == []

    def test_path_to_inputs_single_point(self):
        """Single point path produces no inputs."""
        pf = Pathfinder()
        inputs = pf.path_to_inputs([(5, 5)], frames_per_tile=8)
        assert inputs == []

    def test_path_to_inputs_custom_frames(self):
        """Custom frames_per_tile is respected."""
        pf = Pathfinder()
        path = [(0, 0), (1, 0)]
        inputs = pf.path_to_inputs(path, frames_per_tile=16)

        assert inputs == [("RIGHT", 16)]


# =============================================================================
# Heuristic Tests
# =============================================================================

class TestHeuristic:
    """Tests for A* heuristic function."""

    def test_heuristic_same_point(self):
        """Distance to same point is 0."""
        assert Pathfinder.heuristic((0, 0), (0, 0)) == 0

    def test_heuristic_horizontal(self):
        """Horizontal Manhattan distance."""
        assert Pathfinder.heuristic((0, 0), (5, 0)) == 5
        assert Pathfinder.heuristic((5, 0), (0, 0)) == 5

    def test_heuristic_vertical(self):
        """Vertical Manhattan distance."""
        assert Pathfinder.heuristic((0, 0), (0, 5)) == 5
        assert Pathfinder.heuristic((0, 5), (0, 0)) == 5

    def test_heuristic_diagonal(self):
        """Diagonal Manhattan distance."""
        assert Pathfinder.heuristic((0, 0), (3, 4)) == 7
        assert Pathfinder.heuristic((3, 4), (0, 0)) == 7

    def test_heuristic_negative_coordinates(self):
        """Heuristic works with any coordinates."""
        assert Pathfinder.heuristic((-5, -5), (5, 5)) == 20


# =============================================================================
# Module-Level Functions Tests
# =============================================================================

class TestModuleFunctions:
    """Tests for module-level convenience functions."""

    def test_get_pathfinder_singleton(self):
        """get_pathfinder returns singleton."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        pf1 = get_pathfinder()
        pf2 = get_pathfinder()

        assert pf1 is pf2

    def test_get_pathfinder_with_emulator(self):
        """get_pathfinder can set emulator."""
        import scripts.campaign.pathfinder as pf_module
        pf_module._pathfinder = None

        mock_emu = MagicMock()
        pf = get_pathfinder(mock_emu)

        assert pf.emulator is mock_emu

    def test_find_path_convenience(self):
        """find_path convenience function."""
        collision_data = bytes([TileType.WALKABLE] * 4096)
        result = find_path((0, 0), (5, 5), collision_data)

        assert result.success is True


# =============================================================================
# Cache Tests
# =============================================================================

class TestPathfinderCache:
    """Tests for collision map caching."""

    def test_cache_ttl_default(self):
        """Default cache TTL is 1 second."""
        pf = Pathfinder()
        assert pf.cache_ttl == 1.0

    def test_cache_custom_ttl(self):
        """Cache TTL can be modified."""
        pf = Pathfinder()
        pf.cache_ttl = 5.0
        assert pf.cache_ttl == 5.0


# =============================================================================
# Edge Cases
# =============================================================================

class TestPathfinderEdgeCases:
    """Edge case tests for pathfinder."""

    def test_long_straight_path(self):
        """Very long straight path."""
        cmap = _simple_map()
        pf = Pathfinder()
        result = pf.find_path((0, 0), (63, 0), collision_map=cmap)

        assert result.success is True
        assert result.distance == 63

    def test_path_to_corner(self):
        """Path to map corner."""
        cmap = _simple_map()
        pf = Pathfinder()
        result = pf.find_path((0, 0), (63, 63), collision_map=cmap)

        assert result.success is True
        assert result.distance == 126  # 63 + 63

    def test_path_from_corner(self):
        """Path from corner to center."""
        cmap = _simple_map()
        pf = Pathfinder()
        result = pf.find_path((63, 63), (32, 32), collision_map=cmap)

        assert result.success is True
        assert result.distance == 62  # 31 + 31

    def test_path_along_edge(self):
        """Path along map edge."""
        cmap = _simple_map()
        pf = Pathfinder()
        result = pf.find_path((0, 0), (0, 63), collision_map=cmap)

        assert result.success is True
        assert result.distance == 63

    def test_path_around_obstacle_block(self):
        """Path around a solid block obstacle."""
        pattern = """
        ........
        .######.
        .######.
        .######.
        .######.
        .######.
        .######.
        ........
        """
        cmap = _collision_map(pattern)
        pf = Pathfinder()
        # Path from top-left to bottom-right goes around the block
        result = pf.find_path((0, 0), (7, 7), collision_map=cmap)

        # Path must go around: either along row 0 or row 7
        assert result.success is True
        # Should take longer than direct path due to obstacle
        assert result.distance >= 14  # Must go around

    def test_no_emulator_read_raises(self):
        """read_collision_map raises without emulator."""
        pf = Pathfinder()
        with pytest.raises(RuntimeError, match="No emulator"):
            pf.read_collision_map()
