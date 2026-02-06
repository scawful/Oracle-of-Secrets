# -*- coding: utf-8 -*-
"""Tests for the collision-aware navigation module.

These tests verify:
- Collision map reading and parsing
- A* pathfinding algorithm
- Direction calculation and merging
- Navigation state tracking
- Obstacle avoidance behavior
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

from scripts.campaign.collision_navigator import (
    CollisionNavigator,
    CollisionMap,
    NavAttempt,
    NavResult,
    NavState,
    PathNode,
    TileType,
    WALKABLE_TILES,
    OVERWORLD_WALKABLE_TILES,
    GAMEMODE_DUNGEON,
    GAMEMODE_OVERWORLD,
)


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def mock_bridge():
    """Create a mock MesenBridge."""
    bridge = Mock()
    bridge.read_memory = Mock(return_value=0)
    bridge.read_memory16 = Mock(return_value=0)
    bridge.read_block = Mock(return_value=b'\x00' * 4096)
    bridge.press_button = Mock()
    bridge.run_frames = Mock()
    bridge.ensure_connected = Mock(return_value=True)
    return bridge


@pytest.fixture
def navigator(mock_bridge):
    """Create a CollisionNavigator with mock bridge."""
    return CollisionNavigator(mock_bridge)


@pytest.fixture
def simple_collision_map():
    """Create a simple collision map with known layout."""
    # 8x8 section: open path in the middle, walls on edges
    data = bytearray(4096)
    # Fill with walkable
    for i in range(4096):
        data[i] = TileType.WALKABLE
    # Add a wall at tiles (5-10, 10)
    for x in range(5, 11):
        idx = 10 * 64 + x
        data[idx] = TileType.SOLID
    return CollisionMap(data=bytes(data))


@pytest.fixture
def maze_collision_map():
    """Create a collision map with a simple maze."""
    data = bytearray(4096)
    # Fill with walkable
    for i in range(4096):
        data[i] = TileType.WALKABLE

    # Create a U-shaped obstacle
    # Horizontal wall at y=10 from x=5 to x=15
    for x in range(5, 16):
        data[10 * 64 + x] = TileType.SOLID
    # Left wall from y=10 to y=20 at x=5
    for y in range(10, 21):
        data[y * 64 + 5] = TileType.SOLID
    # Right wall from y=10 to y=20 at x=15
    for y in range(10, 21):
        data[y * 64 + 15] = TileType.SOLID

    return CollisionMap(data=bytes(data))


# =============================================================================
# CollisionMap Tests
# =============================================================================

class TestCollisionMap:
    """Tests for CollisionMap class."""

    def test_get_tile_valid(self):
        """Test getting tile at valid coordinates."""
        data = bytes([TileType.SOLID] * 4096)
        cmap = CollisionMap(data=data)
        assert cmap.get_tile(0, 0) == TileType.SOLID
        assert cmap.get_tile(63, 63) == TileType.SOLID

    def test_get_tile_out_of_bounds(self):
        """Test getting tile at invalid coordinates returns SOLID."""
        data = bytes([TileType.WALKABLE] * 4096)
        cmap = CollisionMap(data=data)
        assert cmap.get_tile(-1, 0) == TileType.SOLID
        assert cmap.get_tile(0, -1) == TileType.SOLID
        assert cmap.get_tile(64, 0) == TileType.SOLID
        assert cmap.get_tile(0, 64) == TileType.SOLID

    def test_get_tile_at_pixel(self):
        """Test pixel-to-tile coordinate conversion."""
        data = bytearray(4096)
        # Set tile at (1, 2) to SOLID
        data[2 * 64 + 1] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        # Pixel (8, 16) should be tile (1, 2)
        assert cmap.get_tile_at_pixel(8, 16) == TileType.SOLID
        # Pixel (0, 0) should be tile (0, 0)
        assert cmap.get_tile_at_pixel(0, 0) == TileType.WALKABLE

    def test_get_tile_at_pixel_wraps(self):
        """Test that pixel coordinates wrap at 512."""
        data = bytearray(4096)
        data[0] = TileType.SOLID  # Tile (0, 0)
        cmap = CollisionMap(data=bytes(data))

        # 512 pixels = full screen, should wrap to tile 0
        assert cmap.get_tile_at_pixel(512, 0) == TileType.SOLID
        assert cmap.get_tile_at_pixel(0, 512) == TileType.SOLID

    def test_is_walkable_for_walkable_tiles(self):
        """Test is_walkable returns True for walkable tile types."""
        data = bytearray(4096)
        for i, tile_type in enumerate(WALKABLE_TILES):
            if i < 64:  # First row
                data[i] = tile_type
        cmap = CollisionMap(data=bytes(data))

        for i, tile_type in enumerate(WALKABLE_TILES):
            if i < 64:
                assert cmap.is_walkable(i, 0), f"Tile type {tile_type} should be walkable"

    def test_is_walkable_for_solid_tiles(self):
        """Test is_walkable returns False for solid tiles."""
        data = bytes([TileType.SOLID] * 4096)
        cmap = CollisionMap(data=data)
        assert not cmap.is_walkable(0, 0)

    def test_is_walkable_for_water(self):
        """Test is_walkable behavior for water tiles."""
        data = bytearray(4096)
        data[0] = TileType.DEEP_WATER
        data[1] = TileType.SHALLOW_WATER
        cmap = CollisionMap(data=bytes(data))

        assert not cmap.is_walkable(0, 0)  # Deep water not walkable without flippers
        assert cmap.is_walkable(1, 0)  # Shallow water is walkable

    def test_get_neighbors_open_area(self):
        """Test getting neighbors in open area."""
        data = bytes([TileType.WALKABLE] * 4096)
        cmap = CollisionMap(data=data)

        # Middle of map should have 4 neighbors
        neighbors = cmap.get_neighbors(32, 32)
        assert len(neighbors) == 4
        assert (31, 32) in neighbors  # Left
        assert (33, 32) in neighbors  # Right
        assert (32, 31) in neighbors  # Up
        assert (32, 33) in neighbors  # Down

    def test_get_neighbors_at_corner(self):
        """Test getting neighbors at corner."""
        data = bytes([TileType.WALKABLE] * 4096)
        cmap = CollisionMap(data=data)

        neighbors = cmap.get_neighbors(0, 0)
        assert len(neighbors) == 2
        assert (1, 0) in neighbors
        assert (0, 1) in neighbors

    def test_get_neighbors_with_wall(self, simple_collision_map):
        """Test getting neighbors with adjacent wall."""
        # Tile (5, 9) is above the wall at y=10
        neighbors = simple_collision_map.get_neighbors(5, 9)
        # Should not include (5, 10) which is a wall
        assert (5, 10) not in neighbors

    def test_get_walkable_ratio(self):
        """Test walkable ratio calculation."""
        data = bytearray(4096)
        # Fill half with walkable, half with solid
        for i in range(2048):
            data[i] = TileType.WALKABLE
        for i in range(2048, 4096):
            data[i] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        ratio = cmap.get_walkable_ratio()
        assert abs(ratio - 0.5) < 0.01

    def test_get_walkable_ratio_empty(self):
        """Test walkable ratio with empty data."""
        cmap = CollisionMap(data=b'')
        assert cmap.get_walkable_ratio() == 0.0


# =============================================================================
# PathNode Tests
# =============================================================================

class TestPathNode:
    """Tests for PathNode class."""

    def test_f_cost_calculation(self):
        """Test f_cost is sum of g_cost and h_cost."""
        node = PathNode(x=5, y=10, g_cost=3.0, h_cost=7.0)
        assert node.f_cost == 10.0

    def test_comparison(self):
        """Test nodes compare by f_cost."""
        node_a = PathNode(x=0, y=0, g_cost=5.0, h_cost=5.0)  # f=10
        node_b = PathNode(x=1, y=1, g_cost=3.0, h_cost=3.0)  # f=6
        assert node_b < node_a

    def test_hash(self):
        """Test nodes hash by position."""
        node_a = PathNode(x=5, y=10)
        node_b = PathNode(x=5, y=10)
        assert hash(node_a) == hash(node_b)

    def test_equality(self):
        """Test nodes equal by position."""
        node_a = PathNode(x=5, y=10, g_cost=1.0)
        node_b = PathNode(x=5, y=10, g_cost=2.0)
        assert node_a == node_b

    def test_inequality(self):
        """Test nodes unequal for different positions."""
        node_a = PathNode(x=5, y=10)
        node_b = PathNode(x=5, y=11)
        assert node_a != node_b


# =============================================================================
# NavState Tests
# =============================================================================

class TestNavState:
    """Tests for NavState class."""

    def test_is_overworld(self):
        """Test overworld detection."""
        state = NavState(
            timestamp="",
            link_x=100,
            link_y=200,
            game_mode=0x09,
            area_id=0x29,
            tile_x=12,
            tile_y=25,
            current_tile=0,
        )
        assert state.is_overworld
        assert not state.is_indoors

    def test_is_indoors(self):
        """Test indoors detection."""
        state = NavState(
            timestamp="",
            link_x=100,
            link_y=200,
            game_mode=0x07,
            area_id=0x00,
            tile_x=12,
            tile_y=25,
            current_tile=0,
        )
        assert state.is_indoors
        assert not state.is_overworld

    def test_position_property(self):
        """Test position tuple property."""
        state = NavState(
            timestamp="",
            link_x=150,
            link_y=300,
            game_mode=0x09,
            area_id=0x29,
            tile_x=18,
            tile_y=37,
            current_tile=0,
        )
        assert state.position == (150, 300)


# =============================================================================
# NavAttempt Tests
# =============================================================================

class TestNavAttempt:
    """Tests for NavAttempt class."""

    def test_success_property(self):
        """Test success property for successful attempt."""
        attempt = NavAttempt(
            result=NavResult.SUCCESS,
            start_x=100,
            start_y=200,
            end_x=200,
            end_y=200,
            target_x=200,
            target_y=200,
        )
        assert attempt.success

    def test_success_property_failure(self):
        """Test success property for failed attempt."""
        attempt = NavAttempt(
            result=NavResult.FAILED_STUCK,
            start_x=100,
            start_y=200,
            end_x=150,
            end_y=200,
            target_x=200,
            target_y=200,
        )
        assert not attempt.success

    def test_distance_remaining(self):
        """Test distance calculation."""
        attempt = NavAttempt(
            result=NavResult.FAILED_TIMEOUT,
            start_x=0,
            start_y=0,
            end_x=30,
            end_y=40,
            target_x=30,
            target_y=90,  # 50 pixels away in Y
        )
        assert attempt.distance_remaining == 50.0

    def test_to_dict(self):
        """Test serialization to dict."""
        attempt = NavAttempt(
            result=NavResult.SUCCESS,
            start_x=100,
            start_y=200,
            end_x=300,
            end_y=400,
            target_x=300,
            target_y=400,
            path_length=10,
            frames_elapsed=150,
        )
        d = attempt.to_dict()
        assert d["result"] == "SUCCESS"
        assert d["start"] == (100, 200)
        assert d["end"] == (300, 400)
        assert d["target"] == (300, 400)
        assert d["path_length"] == 10
        assert d["frames_elapsed"] == 150


# =============================================================================
# CollisionNavigator Tests
# =============================================================================

class TestCollisionNavigator:
    """Tests for CollisionNavigator class."""

    def test_init(self, navigator, mock_bridge):
        """Test navigator initialization."""
        assert navigator.bridge == mock_bridge
        assert navigator.timeout_frames == 1800

    def test_read_collision_map_success(self, navigator, mock_bridge):
        """Test successful collision map reading."""
        expected_data = bytes([TileType.WALKABLE] * 4096)
        mock_bridge.read_block.return_value = expected_data

        cmap = navigator.read_collision_map()
        assert cmap is not None
        assert len(cmap.data) == 4096
        mock_bridge.read_block.assert_called_once()

    def test_read_collision_map_cached(self, navigator, mock_bridge):
        """Test collision map caching."""
        expected_data = bytes([TileType.WALKABLE] * 4096)
        mock_bridge.read_block.return_value = expected_data

        # First read
        cmap1 = navigator.read_collision_map()
        # Second read (should use cache)
        cmap2 = navigator.read_collision_map()

        # Should only have called read_block once (cached)
        assert mock_bridge.read_block.call_count == 1
        assert cmap1 is cmap2

    def test_read_collision_map_force_refresh(self, navigator, mock_bridge):
        """Test force refresh bypasses cache."""
        expected_data = bytes([TileType.WALKABLE] * 4096)
        mock_bridge.read_block.return_value = expected_data

        navigator.read_collision_map()
        navigator.read_collision_map(force_refresh=True)

        assert mock_bridge.read_block.call_count == 2

    def test_capture_state(self, navigator, mock_bridge):
        """Test state capture."""
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,  # game_mode = overworld
            0x7E008A: 0x29,  # area_id
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 3320,  # link_x
            0x7E0020: 3688,  # link_y
        }.get(addr, 0)

        state = navigator.capture_state()
        assert state.game_mode == 0x09
        assert state.link_x == 3320
        assert state.link_y == 3688
        assert state.is_overworld


class TestFindPath:
    """Tests for A* pathfinding."""

    def test_find_path_straight_line(self, navigator, simple_collision_map):
        """Test finding path in straight line."""
        path = navigator.find_path((0, 0), (10, 0), simple_collision_map)
        assert path is not None
        assert path[0] == (0, 0)
        assert path[-1] == (10, 0)
        # Straight line should be 11 tiles
        assert len(path) == 11

    def test_find_path_around_wall(self, navigator, simple_collision_map):
        """Test finding path around a wall."""
        # Wall is at tiles (5-10, 10)
        # Path from (7, 5) to (7, 15) should go around
        path = navigator.find_path((7, 5), (7, 15), simple_collision_map)
        assert path is not None
        assert path[0] == (7, 5)
        assert path[-1] == (7, 15)
        # Should not go through the wall
        for x, y in path:
            if y == 10 and 5 <= x <= 10:
                pytest.fail(f"Path went through wall at ({x}, {y})")

    def test_find_path_around_u_shape(self, navigator, maze_collision_map):
        """Test finding path around U-shaped obstacle."""
        # U-shaped wall from (5,10) to (15,10), down to (5,20) and (15,20)
        # Path from (10, 5) to (10, 25) should go around the bottom
        path = navigator.find_path((10, 5), (10, 25), maze_collision_map)
        assert path is not None
        assert path[0] == (10, 5)
        assert path[-1] == (10, 25)

    def test_find_path_blocked_start(self, navigator):
        """Test pathfinding when start is blocked (finds adjacent)."""
        data = bytearray(4096)
        for i in range(4096):
            data[i] = TileType.WALKABLE
        data[0] = TileType.SOLID  # Block (0, 0)
        cmap = CollisionMap(data=bytes(data))

        path = navigator.find_path((0, 0), (10, 0), cmap)
        # Should find alternate start
        assert path is not None
        # First tile should be adjacent to (0, 0)
        first = path[0]
        assert first in [(1, 0), (0, 1)]

    def test_find_path_blocked_goal(self, navigator):
        """Test pathfinding when goal is blocked (finds nearest)."""
        data = bytearray(4096)
        for i in range(4096):
            data[i] = TileType.WALKABLE
        data[10 * 64 + 10] = TileType.SOLID  # Block (10, 10)
        cmap = CollisionMap(data=bytes(data))

        path = navigator.find_path((0, 0), (10, 10), cmap)
        assert path is not None
        # Should end adjacent to (10, 10)
        last = path[-1]
        assert last != (10, 10)
        # Should be within 1 tile
        dx = abs(last[0] - 10)
        dy = abs(last[1] - 10)
        assert dx <= 1 and dy <= 1

    def test_find_path_no_path_exists(self, navigator):
        """Test pathfinding when completely blocked."""
        data = bytearray(4096)
        # Create an island at (0,0) surrounded by walls
        data[0] = TileType.WALKABLE
        data[1] = TileType.SOLID
        data[64] = TileType.SOLID
        # Everything else is solid
        for i in range(2, 4096):
            if i != 64:
                data[i] = TileType.SOLID
        cmap = CollisionMap(data=bytes(data))

        path = navigator.find_path((0, 0), (50, 50), cmap)
        assert path is None


class TestPathToDirections:
    """Tests for path-to-directions conversion."""

    def test_single_direction(self, navigator):
        """Test path going in one direction."""
        path = [(0, 0), (1, 0), (2, 0), (3, 0)]
        directions = navigator.path_to_directions(path)
        assert len(directions) == 1
        assert directions[0] == ("RIGHT", 3)

    def test_multiple_directions(self, navigator):
        """Test path with direction changes."""
        path = [(0, 0), (1, 0), (2, 0), (2, 1), (2, 2)]
        directions = navigator.path_to_directions(path)
        assert len(directions) == 2
        assert directions[0] == ("RIGHT", 2)
        assert directions[1] == ("DOWN", 2)

    def test_all_directions(self, navigator):
        """Test all four directions."""
        path = [(5, 5), (6, 5), (6, 6), (5, 6), (5, 5)]
        directions = navigator.path_to_directions(path)
        assert directions == [
            ("RIGHT", 1),
            ("DOWN", 1),
            ("LEFT", 1),
            ("UP", 1),
        ]

    def test_empty_path(self, navigator):
        """Test empty path returns no directions."""
        directions = navigator.path_to_directions([])
        assert directions == []

    def test_single_point_path(self, navigator):
        """Test single-point path returns no directions."""
        directions = navigator.path_to_directions([(5, 5)])
        assert directions == []


class TestNavigateTo:
    """Tests for navigation execution."""

    def test_navigate_already_at_target(self, navigator, mock_bridge):
        """Test navigation when already at target."""
        # Position at target
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,  # overworld
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 100,  # link_x
            0x7E0020: 200,  # link_y
        }.get(addr, 0)
        mock_bridge.read_block.return_value = bytes([0] * 4096)

        result = navigator.navigate_to(100, 200)
        assert result.success
        assert result.distance_remaining < 24

    def test_navigate_wrong_mode(self, navigator, mock_bridge):
        """Test navigation fails on wrong game mode."""
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x00,  # Invalid mode (not overworld/indoors)
            0x7E008A: 0x00,
        }.get(addr, 0)
        mock_bridge.read_memory16.return_value = 0

        result = navigator.navigate_to(100, 200)
        assert result.result == NavResult.FAILED_WRONG_MODE

    def test_navigate_greedy_success(self, navigator, mock_bridge):
        """Test successful greedy navigation."""
        # Start position then move toward target
        positions = [(100, 200), (115, 200), (130, 200), (145, 200), (160, 200)]
        pos_idx = [0]

        def get_x(addr):
            if addr == 0x7E0022:
                return positions[min(pos_idx[0], len(positions) - 1)][0]
            return 0

        def get_y(addr):
            if addr == 0x7E0020:
                return positions[min(pos_idx[0], len(positions) - 1)][1]
            return 0

        def read_mem16(addr):
            if addr == 0x7E0022:
                x = positions[min(pos_idx[0], len(positions) - 1)][0]
                pos_idx[0] += 1
                return x
            if addr == 0x7E0020:
                return 200
            return 0

        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = read_mem16
        mock_bridge.read_block.return_value = bytes([0] * 4096)

        result = navigator.navigate_to(160, 200)
        assert result.success


class TestGetCollisionDebug:
    """Tests for collision debug information."""

    def test_get_collision_debug(self, navigator, mock_bridge):
        """Test debug info collection in dungeon mode."""
        # Use dungeon mode (0x07) for predictable collision interpretation
        # WALKABLE (0x00) for first half, SOLID (0x01) for second half
        data = bytes([TileType.WALKABLE] * 2048 + [TileType.SOLID] * 2048)
        mock_bridge.read_block.return_value = data
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x07,  # Dungeon mode (not overworld)
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 256,
            0x7E0020: 128,
        }.get(addr, 0)

        debug = navigator.get_collision_debug()
        assert debug["map_size"] == 4096
        assert abs(debug["walkable_ratio"] - 0.5) < 0.01  # In dungeon mode, SOLID blocks count
        assert debug["link_position"] == (256, 128)
        assert debug["area_id"] == 0x29


# =============================================================================
# Dual-Mode Collision Tests (Iteration 78)
# =============================================================================

class TestDualModeCollision:
    """Tests for dual-mode collision detection (overworld vs dungeon).

    This tests the key discovery from Iteration 78:
    - Dungeons use $7F2000 (COLMAPA) with collision type values
    - Overworld uses $7E2000 (TILEMAPA) with Map16 tile IDs
    """

    def test_collision_map_dungeon_mode(self):
        """Test CollisionMap walkability in dungeon mode."""
        # Dungeon collision types: 0x00=walkable, 0x01=solid
        data = bytes([0x00, 0x01, 0x00, 0x01] * 1024)
        cmap = CollisionMap(data=data, is_overworld=False)

        # WALKABLE (0x00) should be walkable
        assert cmap.is_walkable(0, 0) is True
        # SOLID (0x01) should not be walkable
        assert cmap.is_walkable(1, 0) is False

    def test_collision_map_overworld_mode(self):
        """Test CollisionMap walkability in overworld mode (Map16 heuristic)."""
        # Overworld Map16 tiles: low values (0x00-0x0F) are typically walkable
        data = bytes([0x00, 0x05, 0x0A, 0x0F, 0x10, 0x20, 0x40, 0x80] * 512)
        cmap = CollisionMap(data=data, is_overworld=True)

        # Tiles 0x00-0x0F should be walkable (grass/floor)
        assert cmap.is_walkable(0, 0) is True   # 0x00
        assert cmap.is_walkable(1, 0) is True   # 0x05
        assert cmap.is_walkable(2, 0) is True   # 0x0A
        assert cmap.is_walkable(3, 0) is True   # 0x0F

        # Tiles >= 0x10 are not walkable by default (trees, rocks, etc.)
        assert cmap.is_walkable(4, 0) is False  # 0x10
        assert cmap.is_walkable(5, 0) is False  # 0x20
        assert cmap.is_walkable(6, 0) is False  # 0x40
        assert cmap.is_walkable(7, 0) is False  # 0x80

    def test_walkable_ratio_dungeon_vs_overworld(self):
        """Test that walkable ratio differs based on mode."""
        # Same data, interpreted differently
        data = bytes([0x00] * 2048 + [0x01] * 2048)

        # In dungeon mode: 0x00=walkable, 0x01=solid → 50%
        dungeon_map = CollisionMap(data=data, is_overworld=False)
        assert abs(dungeon_map.get_walkable_ratio() - 0.5) < 0.01

        # In overworld mode: both 0x00 and 0x01 have low nibble → 100%
        overworld_map = CollisionMap(data=data, is_overworld=True)
        assert abs(overworld_map.get_walkable_ratio() - 1.0) < 0.01

    def test_navigator_reads_correct_address_dungeon(self, navigator, mock_bridge):
        """Test that navigator reads from COLMAPA in dungeon mode."""
        # Set up dungeon mode (0x07)
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: GAMEMODE_DUNGEON,  # Dungeon mode
            0x7E008A: 0x10,
        }.get(addr, 0)

        navigator.read_collision_map()

        # Should read from $7F2000 (COLMAPA)
        mock_bridge.read_block.assert_called_with(
            CollisionMap.COLMAPA_ADDR,
            CollisionMap.MAP_SIZE
        )

    def test_navigator_reads_correct_address_overworld(self, navigator, mock_bridge):
        """Test that navigator reads from TILEMAPA in overworld mode."""
        # Set up overworld mode (0x09)
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: GAMEMODE_OVERWORLD,  # Overworld mode
            0x7E008A: 0x40,
        }.get(addr, 0)

        navigator.read_collision_map()

        # Should read from $7E2000 (TILEMAPA)
        mock_bridge.read_block.assert_called_with(
            CollisionMap.TILEMAPA_ADDR,
            CollisionMap.MAP_SIZE
        )

    def test_cache_invalidated_on_mode_change(self, navigator, mock_bridge):
        """Test that collision cache is invalidated when switching modes."""
        mode_call_count = [0]

        def read_memory_side_effect(addr):
            if addr == 0x7E0010:  # Game mode address
                mode_call_count[0] += 1
                # First 2 mode checks return dungeon, then overworld
                return GAMEMODE_DUNGEON if mode_call_count[0] <= 2 else GAMEMODE_OVERWORLD
            if addr == 0x7E008A:
                return 0x10
            return 0

        mock_bridge.read_memory.side_effect = read_memory_side_effect
        mock_bridge.read_block.return_value = b'\x00' * 4096

        # First read (dungeon mode)
        cmap1 = navigator.read_collision_map()
        assert cmap1.is_overworld is False, f"Expected dungeon mode, got overworld. mode_calls={mode_call_count[0]}"

        # Second read (same mode) - should use cache (mode read once for check)
        cmap2 = navigator.read_collision_map()
        assert cmap2.is_overworld is False, "Cache should return dungeon mode map"

        # Third read (overworld mode) - cache should be invalidated
        cmap3 = navigator.read_collision_map()
        assert cmap3.is_overworld is True, "Should detect overworld mode"

    def test_constants_defined(self):
        """Test that mode constants are properly defined."""
        assert GAMEMODE_DUNGEON == 0x07
        assert GAMEMODE_OVERWORLD == 0x09
        assert 0x00 in OVERWORLD_WALKABLE_TILES


# =============================================================================
# Integration-Style Tests
# =============================================================================

class TestNavigationScenarios:
    """Tests for complete navigation scenarios."""

    def test_navigate_with_obstacle(self, navigator, mock_bridge, simple_collision_map):
        """Test navigation that requires going around obstacle."""
        # This is a more complex test simulating actual navigation
        mock_bridge.read_block.return_value = simple_collision_map.data

        # Simulate position updates as navigation progresses
        call_count = [0]

        def mock_read_memory16(addr):
            call_count[0] += 1
            if call_count[0] < 5:
                return 64 if addr == 0x7E0022 else 72
            elif call_count[0] < 10:
                return 80 if addr == 0x7E0022 else 72
            else:
                return 100 if addr == 0x7E0022 else 72

        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = mock_read_memory16

        result = navigator.navigate_to(100, 72)
        # Should eventually succeed or timeout
        assert result.result in (NavResult.SUCCESS, NavResult.FAILED_TIMEOUT)

    def test_navigate_to_tile(self, navigator, mock_bridge):
        """Test tile-based navigation."""
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 20,  # Already at tile (2, 2)
            0x7E0020: 20,
        }.get(addr, 0)
        mock_bridge.read_block.return_value = bytes([0] * 4096)

        result = navigator.navigate_to_tile(2, 2)
        # Should succeed (already there)
        assert result.success


# =============================================================================
# Edge Case Tests
# =============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_timeout(self, navigator, mock_bridge):
        """Test navigation timeout."""
        navigator.timeout_frames = 30  # Very short timeout

        # Position never changes (stuck)
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 100,
            0x7E0020: 100,
        }.get(addr, 0)
        mock_bridge.read_block.return_value = bytes([0] * 4096)

        result = navigator.navigate_to(500, 500)
        # Should timeout since we never move
        assert result.result in (NavResult.FAILED_TIMEOUT, NavResult.FAILED_STUCK)

    def test_negative_coordinates(self, navigator, mock_bridge):
        """Test handling of negative coordinates."""
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 0,
            0x7E0020: 0,
        }.get(addr, 0)
        mock_bridge.read_block.return_value = bytes([0] * 4096)

        # Navigating to negative coords should handle gracefully
        result = navigator.navigate_to(-100, -100)
        # Should try but fail (can't reach negative coords)
        assert not result.success

    def test_very_large_coordinates(self, navigator, mock_bridge):
        """Test handling of large coordinates."""
        mock_bridge.read_memory.side_effect = lambda addr: {
            0x7E0010: 0x09,
            0x7E008A: 0x29,
        }.get(addr, 0)
        mock_bridge.read_memory16.side_effect = lambda addr: {
            0x7E0022: 100,
            0x7E0020: 100,
        }.get(addr, 0)
        mock_bridge.read_block.return_value = bytes([0] * 4096)
        navigator.timeout_frames = 30

        result = navigator.navigate_to(10000, 10000)
        assert result.result in (NavResult.FAILED_TIMEOUT, NavResult.FAILED_STUCK)
