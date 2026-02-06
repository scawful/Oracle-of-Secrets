"""Pathfinder module for Oracle of Secrets.

Provides collision-aware navigation for autonomous gameplay.
Reads collision maps from WRAM and plans paths using A* algorithm.

Campaign Goals Supported:
- A.2: Navigate overworld to specific locations
- D.2: Collision map reader for pathfinding

Key Addresses:
- $7F2000: COLMAPA (primary collision map)
- $7F6000: COLMAPB (secondary collision map)
- $7E0020-23: Link position (Y, X low/high bytes)

Usage:
    from scripts.campaign.pathfinder import Pathfinder, CollisionMap

    pf = Pathfinder(emulator)
    path = pf.find_path((100, 100), (200, 200))
    for step in path:
        pf.navigate_to(step)
"""

from dataclasses import dataclass, field
from enum import IntEnum
from typing import List, Tuple, Optional, Set, Dict
import heapq

from .emulator_abstraction import EmulatorInterface, GameStateSnapshot


class TileType(IntEnum):
    """Collision tile types from ALTTP."""
    WALKABLE = 0x00
    SOLID = 0x01
    DEEP_WATER = 0x08
    SHALLOW_WATER = 0x09
    WATER_EDGE = 0x0A
    PIT = 0x20
    LADDER = 0x22
    LEDGE_UP = 0x28
    LEDGE_DOWN = 0x29
    LEDGE_LEFT = 0x2A
    LEDGE_RIGHT = 0x2B
    GRASS = 0x40
    DAMAGE_FLOOR = 0x60
    SPIKE = 0x62
    WARP = 0x80


# Tiles Link can walk on without special items
WALKABLE_TILES: Set[int] = {
    TileType.WALKABLE,
    TileType.GRASS,
    TileType.SHALLOW_WATER,  # Can walk in shallow water
    TileType.WATER_EDGE,
    TileType.LADDER,
}

# Tiles that require flippers
SWIM_TILES: Set[int] = {
    TileType.DEEP_WATER,
}

# Tiles that are one-way (can jump down only)
LEDGE_TILES: Set[int] = {
    TileType.LEDGE_UP,
    TileType.LEDGE_DOWN,
    TileType.LEDGE_LEFT,
    TileType.LEDGE_RIGHT,
}


@dataclass
class CollisionMap:
    """Represents a collision map section.

    COLMAPA is at $7F2000, organized as 64x64 tiles (4096 bytes)
    Each tile is 8x8 pixels, so full map is 512x512 pixels.
    """
    data: bytes
    width: int = 64
    height: int = 64
    tile_size: int = 8

    # RAM addresses
    COLMAPA_ADDR = 0x7F2000
    COLMAPB_ADDR = 0x7F6000
    MAP_SIZE = 0x1000  # 4096 bytes

    def get_tile(self, tile_x: int, tile_y: int) -> int:
        """Get collision value at tile coordinates."""
        if 0 <= tile_x < self.width and 0 <= tile_y < self.height:
            index = tile_y * self.width + tile_x
            if index < len(self.data):
                return self.data[index]
        return TileType.SOLID  # Out of bounds = solid

    def get_tile_at_pixel(self, px: int, py: int) -> int:
        """Get collision value at pixel coordinates."""
        tile_x = px // self.tile_size
        tile_y = py // self.tile_size
        return self.get_tile(tile_x, tile_y)

    def is_walkable(self, tile_x: int, tile_y: int, has_flippers: bool = False) -> bool:
        """Check if tile is walkable."""
        tile = self.get_tile(tile_x, tile_y)
        if tile in WALKABLE_TILES:
            return True
        if has_flippers and tile in SWIM_TILES:
            return True
        return False

    def get_neighbors(self, tile_x: int, tile_y: int,
                      has_flippers: bool = False) -> List[Tuple[int, int]]:
        """Get walkable neighboring tiles."""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = tile_x + dx, tile_y + dy
            if self.is_walkable(nx, ny, has_flippers):
                neighbors.append((nx, ny))
        return neighbors


@dataclass
class PathNode:
    """Node for A* pathfinding."""
    x: int
    y: int
    g_cost: float = 0.0  # Cost from start
    h_cost: float = 0.0  # Heuristic cost to goal
    parent: Optional['PathNode'] = None

    @property
    def f_cost(self) -> float:
        return self.g_cost + self.h_cost

    def __lt__(self, other: 'PathNode') -> bool:
        return self.f_cost < other.f_cost

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PathNode):
            return self.x == other.x and self.y == other.y
        return False

    def __hash__(self) -> int:
        return hash((self.x, self.y))


@dataclass
class NavigationResult:
    """Result of a navigation attempt."""
    success: bool
    path: List[Tuple[int, int]]
    distance: float = 0.0
    blocked_at: Optional[Tuple[int, int]] = None
    reason: str = ""


class Pathfinder:
    """A* pathfinder for game navigation.

    Uses collision maps to find walkable paths between points.
    Supports overworld and dungeon navigation.
    """

    def __init__(self, emulator: Optional[EmulatorInterface] = None):
        """Initialize pathfinder.

        Args:
            emulator: Optional emulator interface for live collision reading
        """
        self.emulator = emulator
        self._collision_cache: Optional[CollisionMap] = None
        self._cache_timestamp: float = 0.0
        self.cache_ttl: float = 1.0  # Cache collision map for 1 second

    def read_collision_map(self, use_secondary: bool = False) -> CollisionMap:
        """Read collision map from emulator.

        Args:
            use_secondary: If True, read COLMAPB instead of COLMAPA

        Returns:
            CollisionMap with current collision data
        """
        if self.emulator is None:
            raise RuntimeError("No emulator connected")

        addr = CollisionMap.COLMAPB_ADDR if use_secondary else CollisionMap.COLMAPA_ADDR

        # Read collision data in chunks
        data = bytearray()
        chunk_size = 256
        for offset in range(0, CollisionMap.MAP_SIZE, chunk_size):
            # Read each byte - simplified for now
            chunk = []
            for i in range(chunk_size):
                read = self.emulator.read_memory(addr + offset + i, size=1)
                chunk.append(read.value)
            data.extend(chunk)

        return CollisionMap(data=bytes(data))

    def get_collision_map(self, force_refresh: bool = False) -> CollisionMap:
        """Get collision map, using cache if available.

        Args:
            force_refresh: If True, bypass cache

        Returns:
            Current collision map
        """
        import time
        now = time.time()

        if (self._collision_cache is None or
            force_refresh or
            now - self._cache_timestamp > self.cache_ttl):
            self._collision_cache = self.read_collision_map()
            self._cache_timestamp = now

        return self._collision_cache

    @staticmethod
    def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
        """Manhattan distance heuristic."""
        return abs(a[0] - b[0]) + abs(a[1] - b[1])

    def find_path(
        self,
        start: Tuple[int, int],
        goal: Tuple[int, int],
        collision_map: Optional[CollisionMap] = None,
        has_flippers: bool = False,
        max_iterations: int = 10000
    ) -> NavigationResult:
        """Find path from start to goal using A*.

        Args:
            start: Starting tile coordinates (x, y)
            goal: Goal tile coordinates (x, y)
            collision_map: Collision map to use (reads from emulator if None)
            has_flippers: Whether Link has flippers (allows deep water)
            max_iterations: Maximum iterations before giving up

        Returns:
            NavigationResult with path if found
        """
        if collision_map is None:
            collision_map = self.get_collision_map()

        # Check start and goal validity
        if not collision_map.is_walkable(start[0], start[1], has_flippers):
            return NavigationResult(
                success=False,
                path=[],
                reason=f"Start position {start} is not walkable"
            )

        if not collision_map.is_walkable(goal[0], goal[1], has_flippers):
            return NavigationResult(
                success=False,
                path=[],
                reason=f"Goal position {goal} is not walkable"
            )

        # A* algorithm
        open_set: List[PathNode] = []
        closed_set: Set[Tuple[int, int]] = set()

        start_node = PathNode(
            x=start[0],
            y=start[1],
            g_cost=0,
            h_cost=self.heuristic(start, goal)
        )
        heapq.heappush(open_set, start_node)

        # For reconstructing path
        came_from: Dict[Tuple[int, int], PathNode] = {}

        iterations = 0
        while open_set and iterations < max_iterations:
            iterations += 1

            current = heapq.heappop(open_set)
            current_pos = (current.x, current.y)

            if current_pos == goal:
                # Reconstruct path
                path = []
                node = current
                while node is not None:
                    path.append((node.x, node.y))
                    node = node.parent
                path.reverse()

                return NavigationResult(
                    success=True,
                    path=path,
                    distance=current.g_cost
                )

            closed_set.add(current_pos)

            # Check neighbors
            for nx, ny in collision_map.get_neighbors(current.x, current.y, has_flippers):
                neighbor_pos = (nx, ny)

                if neighbor_pos in closed_set:
                    continue

                # Cost to reach neighbor
                tentative_g = current.g_cost + 1

                # Check if this path is better
                existing = came_from.get(neighbor_pos)
                if existing is not None and tentative_g >= existing.g_cost:
                    continue

                neighbor = PathNode(
                    x=nx,
                    y=ny,
                    g_cost=tentative_g,
                    h_cost=self.heuristic(neighbor_pos, goal),
                    parent=current
                )

                came_from[neighbor_pos] = neighbor
                heapq.heappush(open_set, neighbor)

        return NavigationResult(
            success=False,
            path=[],
            reason=f"No path found after {iterations} iterations"
        )

    def find_path_pixels(
        self,
        start_px: Tuple[int, int],
        goal_px: Tuple[int, int],
        **kwargs
    ) -> NavigationResult:
        """Find path using pixel coordinates.

        Args:
            start_px: Starting pixel coordinates
            goal_px: Goal pixel coordinates
            **kwargs: Additional args for find_path

        Returns:
            NavigationResult with tile-based path
        """
        tile_size = 8
        start_tile = (start_px[0] // tile_size, start_px[1] // tile_size)
        goal_tile = (goal_px[0] // tile_size, goal_px[1] // tile_size)
        return self.find_path(start_tile, goal_tile, **kwargs)

    def path_to_inputs(
        self,
        path: List[Tuple[int, int]],
        frames_per_tile: int = 8
    ) -> List[Tuple[str, int]]:
        """Convert a tile path to input commands.

        Args:
            path: List of tile coordinates
            frames_per_tile: Frames to hold direction per tile

        Returns:
            List of (direction, frames) tuples
        """
        if len(path) < 2:
            return []

        inputs = []
        for i in range(1, len(path)):
            prev = path[i - 1]
            curr = path[i]

            dx = curr[0] - prev[0]
            dy = curr[1] - prev[1]

            if dx > 0:
                direction = "RIGHT"
            elif dx < 0:
                direction = "LEFT"
            elif dy > 0:
                direction = "DOWN"
            elif dy < 0:
                direction = "UP"
            else:
                continue

            # Merge consecutive same-direction moves
            if inputs and inputs[-1][0] == direction:
                inputs[-1] = (direction, inputs[-1][1] + frames_per_tile)
            else:
                inputs.append((direction, frames_per_tile))

        return inputs


# Module-level singleton
_pathfinder: Optional[Pathfinder] = None


def get_pathfinder(emulator: Optional[EmulatorInterface] = None) -> Pathfinder:
    """Get or create the pathfinder singleton.

    Args:
        emulator: Emulator interface to use

    Returns:
        Pathfinder instance
    """
    global _pathfinder
    if _pathfinder is None:
        _pathfinder = Pathfinder(emulator)
    elif emulator is not None and _pathfinder.emulator is None:
        _pathfinder.emulator = emulator
    return _pathfinder


def find_path(
    start: Tuple[int, int],
    goal: Tuple[int, int],
    collision_data: Optional[bytes] = None
) -> NavigationResult:
    """Convenience function for pathfinding.

    Args:
        start: Starting tile position
        goal: Goal tile position
        collision_data: Raw collision bytes (uses singleton if None)

    Returns:
        NavigationResult
    """
    pf = get_pathfinder()

    if collision_data is not None:
        cmap = CollisionMap(data=collision_data)
        return pf.find_path(start, goal, collision_map=cmap)

    return pf.find_path(start, goal)
