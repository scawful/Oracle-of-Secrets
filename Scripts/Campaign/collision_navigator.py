# -*- coding: utf-8 -*-
"""Collision-Aware Navigation Module for Goal A.2/A.3.

This module provides collision-aware navigation that can avoid obstacles
by reading the game's collision data from WRAM and using A* pathfinding.

Campaign Goals Supported:
- A.2: Navigate overworld to specific locations
- A.3: Enter and exit buildings/caves/dungeons
- D.2: Collision map reader for pathfinding

IMPORTANT - Dual Mode Collision Detection:
==========================================
Oracle of Secrets uses DIFFERENT collision systems for overworld vs dungeons:

DUNGEONS (GameMode 0x07):
- $7F2000 (COLMAPA): Direct collision map with type values
- Values: 0x00=walkable, 0x01/0x02=solid, 0x08=deep water, 0x09=shallow
- 64x64 tiles (4096 bytes), each byte is collision type

OVERWORLD (GameMode 0x09):
- $7F2000 is repurposed as MAP16 decompression buffer (NOT collision!)
- $7E2000 (TILEMAPA): Map16 tile IDs for current screen
- Collision determined by looking up tile properties in ROM ($3D8000)
- We use a simplified heuristic: tile IDs < 0x10 are typically walkable grass/floor

If available, we prefer Mesen2's COLLISION_DUMP command for overworld, which
returns collision values derived from Map16 properties (more accurate than heuristics).

Key Addresses:
- $7F2000: COLMAPA (dungeon collision) / MAP16 buffer (overworld)
- $7E2000: TILEMAPA (Map16 tile IDs in overworld)
- $7E0020-23: Link position (Y low, Y high, X low, X high)
- $7E0010: GameMode (0x07=dungeon, 0x09=overworld)
- $7E008A: Current area/screen ID

Usage:
    from scripts.campaign.collision_navigator import CollisionNavigator

    nav = CollisionNavigator(bridge)
    result = nav.navigate_to(target_x, target_y)
    if result.success:
        print(f"Arrived at ({result.end_x}, {result.end_y})")
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import IntEnum, Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
import heapq
import time
import math
import os


class TileType(IntEnum):
    """Collision tile types from ALTTP/Oracle."""
    WALKABLE = 0x00
    SOLID = 0x01
    SOLID_2 = 0x02
    SOLID_3 = 0x03
    SOLID_4 = 0x04
    DEEP_WATER = 0x08
    SHALLOW_WATER = 0x09
    WATER_EDGE = 0x0A
    TALL_GRASS = 0x0B
    PIT = 0x20
    LEDGE_UP = 0x28
    LEDGE_DOWN = 0x29
    LEDGE_LEFT = 0x2A
    LEDGE_RIGHT = 0x2B
    STAIRS_UP = 0x30
    STAIRS_DOWN = 0x31
    GRASS = 0x40
    DAMAGE_FLOOR = 0x60
    SPIKE = 0x62
    WARP = 0x80


# Tiles Link can walk through without special items (DUNGEON collision types)
WALKABLE_TILES: Set[int] = {
    TileType.WALKABLE,
    TileType.SHALLOW_WATER,
    TileType.WATER_EDGE,
    TileType.TALL_GRASS,
    TileType.GRASS,
    TileType.STAIRS_UP,
    TileType.STAIRS_DOWN,
}

# Game mode constants
GAMEMODE_DUNGEON = 0x07
GAMEMODE_OVERWORLD = 0x09

# Overworld Map16 tile classification (empirically determined)
# These are Map16 tile IDs from $7E2000, NOT collision types
# Based on common ALTTP overworld patterns - may need refinement
OVERWORLD_WALKABLE_TILES: Set[int] = set(range(0x00, 0x10))  # Basic grass/floor tiles
OVERWORLD_SOLID_TILES: Set[int] = {
    0x20, 0x21, 0x22, 0x23,  # Trees/rocks
    0x40, 0x41, 0x42, 0x43,  # Walls
    0x50, 0x51, 0x52, 0x53,  # Cliffs
    0x60, 0x61, 0x62, 0x63,  # Buildings/barriers
}
# Note: This is a heuristic. True Map16 collision requires ROM table lookup.


class NavResult(Enum):
    """Result status of navigation attempt."""
    SUCCESS = auto()
    IN_PROGRESS = auto()
    FAILED_NO_PATH = auto()
    FAILED_STUCK = auto()
    FAILED_TIMEOUT = auto()
    FAILED_COLLISION_READ = auto()
    FAILED_WRONG_MODE = auto()


@dataclass
class CollisionMap:
    """Collision map data for one screen.

    IMPORTANT: Behavior differs based on data_kind:
    - data_kind="collision": data contains collision types (0x00-0x09, etc.)
    - data_kind="tile_ids": data contains Map16 tile IDs
    """
    data: bytes
    width: int = 64
    height: int = 64
    tile_size: int = 8
    is_overworld: bool = False  # Game mode context (overworld vs dungeon)
    data_kind: str = "auto"  # "auto", "collision", or "tile_ids"
    source: str = "wram"  # "wram-tilemap", "wram-colmap", "collision_dump"
    learned_walkable: Set[int] = field(default_factory=set)
    learned_blocked: Set[int] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.data_kind == "auto":
            self.data_kind = "tile_ids" if self.is_overworld else "collision"

    # Base addresses in WRAM
    COLMAPA_ADDR = 0x7F2000      # Dungeon collision map
    COLMAPB_ADDR = 0x7F3000      # Dungeon collision map layer 2 (fixed from 0x7F6000)
    TILEMAPA_ADDR = 0x7E2000     # Overworld Map16 tile IDs
    MAP_SIZE = 0x1000            # 4096 bytes

    def get_tile(self, tile_x: int, tile_y: int) -> int:
        """Get tile value at tile coordinates (collision type or Map16 ID)."""
        if 0 <= tile_x < self.width and 0 <= tile_y < self.height:
            index = tile_y * self.width + tile_x
            if index < len(self.data):
                return self.data[index]
        return TileType.SOLID  # Out of bounds = solid

    def get_tile_at_pixel(self, px: int, py: int) -> int:
        """Get tile value at pixel coordinates (screen-relative)."""
        tile_x = (px % 512) // self.tile_size
        tile_y = (py % 512) // self.tile_size
        return self.get_tile(tile_x, tile_y)

    def is_walkable(self, tile_x: int, tile_y: int) -> bool:
        """Check if tile is walkable (mode-aware).

        For collision data: checks against WALKABLE_TILES (collision types)
        For tile ID data: checks against OVERWORLD_WALKABLE_TILES (Map16 IDs)
        """
        tile = self.get_tile(tile_x, tile_y)
        if self.data_kind == "tile_ids":
            if tile in self.learned_blocked:
                return False
            if tile in self.learned_walkable:
                return True
            # Overworld: use Map16 tile ID heuristics
            # Low tile IDs (0x00-0x0F) are typically walkable grass/floor
            # This is a simplification - true collision needs ROM lookup
            return tile in OVERWORLD_WALKABLE_TILES or (tile & 0xF0) == 0
        # Collision map: use direct collision type
        return tile in WALKABLE_TILES or tile == 0

    def get_neighbors(self, tile_x: int, tile_y: int) -> List[Tuple[int, int]]:
        """Get walkable neighboring tiles (4-directional)."""
        neighbors = []
        for dx, dy in [(-1, 0), (1, 0), (0, -1), (0, 1)]:
            nx, ny = tile_x + dx, tile_y + dy
            if 0 <= nx < self.width and 0 <= ny < self.height:
                if self.is_walkable(nx, ny):
                    neighbors.append((nx, ny))
        return neighbors

    def get_walkable_ratio(self) -> float:
        """Calculate the ratio of walkable tiles (for debugging, mode-aware)."""
        if not self.data:
            return 0.0
        if self.data_kind == "tile_ids":
            walkable = 0
            for b in self.data:
                if b in self.learned_blocked:
                    continue
                if b in self.learned_walkable or (b in OVERWORLD_WALKABLE_TILES or (b & 0xF0) == 0):
                    walkable += 1
        else:
            walkable = sum(1 for b in self.data if b in WALKABLE_TILES or b == 0)
        return walkable / len(self.data)


@dataclass
class PathNode:
    """Node for A* pathfinding."""
    x: int
    y: int
    g_cost: float = 0.0
    h_cost: float = 0.0
    parent: Optional['PathNode'] = None

    @property
    def f_cost(self) -> float:
        return self.g_cost + self.h_cost

    def __lt__(self, other: 'PathNode') -> bool:
        return self.f_cost < other.f_cost

    def __hash__(self) -> int:
        return hash((self.x, self.y))

    def __eq__(self, other: object) -> bool:
        if isinstance(other, PathNode):
            return self.x == other.x and self.y == other.y
        return False


@dataclass
class NavState:
    """Navigation state snapshot."""
    timestamp: str
    link_x: int
    link_y: int
    game_mode: int
    area_id: int
    tile_x: int
    tile_y: int
    current_tile: int
    frame: int = 0

    @property
    def is_overworld(self) -> bool:
        return self.game_mode == 0x09

    @property
    def is_indoors(self) -> bool:
        return self.game_mode == 0x07

    @property
    def position(self) -> Tuple[int, int]:
        return (self.link_x, self.link_y)


@dataclass
class NavAttempt:
    """Result of a navigation attempt."""
    result: NavResult
    start_x: int
    start_y: int
    end_x: int
    end_y: int
    target_x: int
    target_y: int
    path_length: int = 0
    frames_elapsed: int = 0
    error_message: str = ""
    path_taken: List[Tuple[int, int]] = field(default_factory=list)
    states: List[NavState] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.result == NavResult.SUCCESS

    @property
    def distance_remaining(self) -> float:
        return math.sqrt((self.end_x - self.target_x)**2 +
                        (self.end_y - self.target_y)**2)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "result": self.result.name,
            "start": (self.start_x, self.start_y),
            "end": (self.end_x, self.end_y),
            "target": (self.target_x, self.target_y),
            "path_length": self.path_length,
            "frames_elapsed": self.frames_elapsed,
            "distance_remaining": self.distance_remaining,
            "error_message": self.error_message,
        }


class CollisionNavigator:
    """Collision-aware navigation using A* pathfinding.

    This navigator reads the game's collision map from WRAM and uses
    A* pathfinding to navigate around obstacles. It falls back to
    greedy direct navigation when the path is clear.
    """

    # Memory addresses
    ADDR_LINK_Y_LO = 0x7E0020
    ADDR_LINK_Y_HI = 0x7E0021
    ADDR_LINK_X_LO = 0x7E0022
    ADDR_LINK_X_HI = 0x7E0023
    ADDR_GAME_MODE = 0x7E0010
    ADDR_AREA_ID = 0x7E008A
    GLOBAL_COLLISION_TABLE_ADDR = 0x0E9659  # SNES address (LoROM) for global collision tables
    GLOBAL_COLLISION_TABLE_SIZE = 0x200     # 512 bytes (8 tables * 64 entries)

    def __init__(self, bridge: Any, timeout_frames: int = 1800, rom_path: Optional[str] = None):
        """Initialize collision navigator.

        Args:
            bridge: MesenBridge instance for emulator control
            timeout_frames: Maximum frames before navigation timeout (default 30 seconds)
            rom_path: Optional ROM path for Map16 collision table lookup
        """
        self.bridge = bridge
        self.timeout_frames = timeout_frames
        self._prefer_16bit_tilemap = os.getenv("OOS_TILEMAP_16BIT") == "1"
        self._rom_path = self._resolve_rom_path(rom_path)
        self._global_collision_table: Optional[List[int]] = None
        self._collision_cache: Optional[CollisionMap] = None
        self._cache_area: Optional[int] = None
        self._stuck_threshold = 8  # Steps without movement = stuck
        self._arrival_threshold = 24  # Pixels to consider "arrived"
        self._states: List[NavState] = []
        self._ow_walkable_by_area: Dict[int, Set[int]] = {}
        self._ow_blocked_by_area: Dict[int, Set[int]] = {}
        self._ow_tile_stats: Dict[int, Dict[int, Dict[str, int]]] = {}
        self._learn_ok_threshold = 1
        self._learn_fail_threshold = 2
        self._micro_step_frames = 6

    def read_collision_map(self, force_refresh: bool = False) -> Optional[CollisionMap]:
        """Read collision map from WRAM (mode-aware).

        Reads from different addresses based on game mode:
        - Dungeons (0x07): $7F2000 (COLMAPA) - direct collision types
        - Overworld (0x09): $7E2000 (TILEMAPA) - Map16 tile IDs

        Args:
            force_refresh: If True, bypass cache

        Returns:
            CollisionMap or None if read failed
        """
        # Check game mode and determine correct address
        game_mode = self._read_byte(self.ADDR_GAME_MODE)
        is_overworld = (game_mode == GAMEMODE_OVERWORLD)

        # Determine read address based on mode
        if is_overworld:
            read_addr = CollisionMap.TILEMAPA_ADDR  # $7E2000 for Map16 IDs
        else:
            read_addr = CollisionMap.COLMAPA_ADDR   # $7F2000 for collision types

        # Check cache (invalidate on mode change too)
        area = self._read_byte(self.ADDR_AREA_ID)
        learned_walkable: Set[int] = set()
        learned_blocked: Set[int] = set()
        if is_overworld:
            learned_walkable = self._ow_walkable_by_area.setdefault(area, set())
            learned_blocked = self._ow_blocked_by_area.setdefault(area, set())
        data_kind = "tile_ids" if is_overworld else "collision"
        cache_valid = (
            not force_refresh and
            self._collision_cache and
            self._cache_area == area and
            self._collision_cache.is_overworld == is_overworld
        )
        if cache_valid:
            return self._collision_cache

        # Prefer emulator-provided collision dump in overworld for accurate Map16-derived collision.
        if is_overworld:
            dump = self._read_collision_dump()
            if dump:
                self._collision_cache = CollisionMap(
                    data=dump,
                    is_overworld=is_overworld,
                    data_kind="collision",
                    source="collision_dump",
                )
                self._cache_area = area
                return self._collision_cache

            rom_collision = self._read_overworld_collision_from_rom()
            if rom_collision:
                self._collision_cache = CollisionMap(
                    data=rom_collision,
                    is_overworld=is_overworld,
                    data_kind="collision",
                    source="rom-global-collision",
                )
                self._cache_area = area
                return self._collision_cache

        # Read collision data using block read
        try:
            data = self.bridge.read_block(read_addr, CollisionMap.MAP_SIZE)
            if data and len(data) == CollisionMap.MAP_SIZE:
                self._collision_cache = CollisionMap(
                    data=data,
                    is_overworld=is_overworld,
                    data_kind=data_kind,
                    source="wram-tilemap" if is_overworld else "wram-colmap",
                    learned_walkable=learned_walkable,
                    learned_blocked=learned_blocked,
                )
                self._cache_area = area
                return self._collision_cache
        except Exception as e:
            # Fall back to byte-by-byte read if block read fails
            try:
                data = bytearray()
                for i in range(CollisionMap.MAP_SIZE):
                    val = self._read_byte(read_addr + i)
                    data.append(val)
                self._collision_cache = CollisionMap(
                    data=bytes(data),
                    is_overworld=is_overworld,
                    data_kind=data_kind,
                    source="wram-tilemap" if is_overworld else "wram-colmap",
                    learned_walkable=learned_walkable,
                    learned_blocked=learned_blocked,
                )
                self._cache_area = area
                return self._collision_cache
            except Exception:
                pass

        return None

    def _resolve_rom_path(self, rom_path: Optional[str]) -> Optional[Path]:
        if rom_path:
            candidate = Path(rom_path).expanduser()
            if candidate.exists():
                return candidate
        env_path = os.getenv("OOS_ROM_PATH") or os.getenv("ROM_PATH")
        if env_path:
            candidate = Path(env_path).expanduser()
            if candidate.exists():
                return candidate
        try:
            if hasattr(self.bridge, "get_rom_info"):
                info = self.bridge.get_rom_info()
                for key in ("path", "filename", "file"):
                    if key in info:
                        candidate = Path(str(info[key])).expanduser()
                        if candidate.exists():
                            return candidate
        except Exception:
            pass

        repo_root = Path(__file__).resolve().parents[2]
        default_rom = repo_root / "Roms" / "oos168x.sfc"
        if default_rom.exists():
            return default_rom
        return None

    def _snes_to_pc(self, addr: int) -> Optional[int]:
        bank = (addr >> 16) & 0xFF
        offset = addr & 0x7FFF
        if (addr & 0x8000) == 0:
            return None
        return (bank * 0x8000) + offset

    def _load_global_collision_table(self) -> Optional[List[int]]:
        if self._global_collision_table:
            return self._global_collision_table
        if not self._rom_path:
            return None
        pc = self._snes_to_pc(self.GLOBAL_COLLISION_TABLE_ADDR)
        if pc is None:
            return None
        try:
            with self._rom_path.open("rb") as f:
                f.seek(pc)
                data = f.read(self.GLOBAL_COLLISION_TABLE_SIZE)
            if len(data) != self.GLOBAL_COLLISION_TABLE_SIZE:
                return None
            self._global_collision_table = [b for b in data]
            return self._global_collision_table
        except Exception:
            return None

    def _read_overworld_tile_ids(self) -> Optional[List[int]]:
        # Optional 16-bit tile IDs (Map16 IDs can be 9-bit)
        if self._prefer_16bit_tilemap:
            try:
                data = self.bridge.read_block(CollisionMap.TILEMAPA_ADDR, CollisionMap.MAP_SIZE * 2)
                if data and len(data) >= CollisionMap.MAP_SIZE * 2:
                    hi_bytes = data[1::2]
                    hi_ok = sum(1 for b in hi_bytes if b in (0x00, 0x01))
                    hi_ratio = hi_ok / len(hi_bytes) if hi_bytes else 0.0
                    if hi_ratio >= 0.9:
                        tile_ids: List[int] = []
                        for i in range(0, CollisionMap.MAP_SIZE * 2, 2):
                            tile_ids.append(data[i] | (data[i + 1] << 8))
                        return tile_ids
                if data and len(data) == CollisionMap.MAP_SIZE:
                    return [b for b in data]
            except Exception:
                pass
        # Fallback to 8-bit tile IDs (default)
        try:
            data = self.bridge.read_block(CollisionMap.TILEMAPA_ADDR, CollisionMap.MAP_SIZE)
            if data and len(data) == CollisionMap.MAP_SIZE:
                return [b for b in data]
        except Exception:
            pass

        try:
            tile_ids = []
            for i in range(CollisionMap.MAP_SIZE):
                tile_ids.append(self._read_byte(CollisionMap.TILEMAPA_ADDR + i))
            return tile_ids
        except Exception:
            return None

    def _read_overworld_collision_from_rom(self) -> Optional[bytes]:
        tile_ids = self._read_overworld_tile_ids()
        if not tile_ids:
            return None
        table = self._load_global_collision_table()
        if not table:
            return None
        if len(table) < self.GLOBAL_COLLISION_TABLE_SIZE:
            return None
        collision = bytearray()
        for tile in tile_ids[:CollisionMap.MAP_SIZE]:
            idx = tile & 0x01FF
            collision.append(table[idx] & 0xFF)
        if len(collision) != CollisionMap.MAP_SIZE:
            return None
        return bytes(collision)

    def _read_collision_dump(self) -> Optional[bytes]:
        """Attempt to read collision map via emulator (Map16-derived)."""
        if not hasattr(self.bridge, "collision_dump"):
            return None
        try:
            result = self.bridge.collision_dump("A")
        except Exception:
            return None

        data = None
        if isinstance(result, dict):
            if result.get("success") is False:
                return None
            data = result.get("data")
            if isinstance(data, dict):
                for key in ("map", "values", "tiles", "data"):
                    if key in data:
                        data = data[key]
                        break
        else:
            data = result

        if data is None:
            return None

        flat: list[int] = []
        if isinstance(data, list):
            if data and isinstance(data[0], list):
                for row in data:
                    flat.extend(int(v) & 0xFF for v in row)
            else:
                flat = [int(v) & 0xFF for v in data]
        elif isinstance(data, str):
            parts = [p.strip() for p in data.replace("\n", " ").split(",") if p.strip()]
            try:
                flat = [int(p, 0) & 0xFF for p in parts]
            except ValueError:
                return None
        else:
            return None

        if len(flat) < CollisionMap.MAP_SIZE:
            return None
        return bytes(flat[:CollisionMap.MAP_SIZE])

    def _read_byte(self, address: int) -> int:
        """Read a single byte from memory."""
        return self.bridge.read_memory(address)

    def _read_word(self, address: int) -> int:
        """Read a 16-bit word (little-endian)."""
        if hasattr(self.bridge, 'read_memory16'):
            return self.bridge.read_memory16(address)
        lo = self._read_byte(address)
        hi = self._read_byte(address + 1)
        return lo | (hi << 8)

    def _primary_direction(self, dx: int, dy: int) -> str:
        if abs(dx) > abs(dy):
            return "RIGHT" if dx > 0 else "LEFT"
        return "DOWN" if dy > 0 else "UP"

    def _record_overworld_observation(self, area_id: int, tile_id: int, moved: bool) -> None:
        stats = self._ow_tile_stats.setdefault(area_id, {}).setdefault(tile_id, {"ok": 0, "fail": 0})
        if moved:
            stats["ok"] += 1
            if stats["ok"] >= self._learn_ok_threshold:
                self._ow_walkable_by_area.setdefault(area_id, set()).add(tile_id)
                self._ow_blocked_by_area.setdefault(area_id, set()).discard(tile_id)
        else:
            stats["fail"] += 1
            if stats["ok"] == 0 and stats["fail"] >= self._learn_fail_threshold:
                self._ow_blocked_by_area.setdefault(area_id, set()).add(tile_id)
                self._ow_walkable_by_area.setdefault(area_id, set()).discard(tile_id)

    def _learn_from_movement(
        self,
        prev_state: NavState,
        new_state: NavState,
        direction: str,
        cmap: Optional[CollisionMap],
        moved: bool,
    ) -> None:
        if not cmap or not prev_state.is_overworld or cmap.data_kind != "tile_ids":
            return

        dir_map = {
            "UP": (0, -1),
            "DOWN": (0, 1),
            "LEFT": (-1, 0),
            "RIGHT": (1, 0),
        }
        if direction not in dir_map:
            return

        dx, dy = dir_map[direction]
        target_x = prev_state.tile_x + dx
        target_y = prev_state.tile_y + dy
        tile_id = cmap.get_tile(target_x, target_y)
        self._record_overworld_observation(prev_state.area_id, tile_id, moved)

    def _attempt_move(
        self,
        direction: str,
        frames: int,
        frames_elapsed: int,
        cmap: Optional[CollisionMap],
    ) -> Tuple[NavState, bool, int]:
        prev_state = self.capture_state(frames_elapsed)
        self.execute_move(direction, frames)
        frames_elapsed += frames
        new_state = self.capture_state(frames_elapsed)
        moved = (new_state.link_x, new_state.link_y) != (prev_state.link_x, prev_state.link_y)
        self._learn_from_movement(prev_state, new_state, direction, cmap, moved)
        return new_state, moved, frames_elapsed

    def _try_micro_adjust(
        self,
        primary_dir: str,
        frames_elapsed: int,
        cmap: Optional[CollisionMap],
    ) -> Tuple[bool, int]:
        if primary_dir in ("UP", "DOWN"):
            perpendiculars = ("LEFT", "RIGHT")
        elif primary_dir in ("LEFT", "RIGHT"):
            perpendiculars = ("UP", "DOWN")
        else:
            return False, frames_elapsed

        for perp in perpendiculars:
            _, moved, frames_elapsed = self._attempt_move(perp, self._micro_step_frames, frames_elapsed, cmap)
            if moved:
                return True, frames_elapsed
            _, moved, frames_elapsed = self._attempt_move(primary_dir, self._micro_step_frames, frames_elapsed, cmap)
            if moved:
                return True, frames_elapsed

        return False, frames_elapsed

    def capture_state(self, frame: int = 0) -> NavState:
        """Capture current navigation state."""
        link_x = self._read_word(self.ADDR_LINK_X_LO)
        link_y = self._read_word(self.ADDR_LINK_Y_LO)
        game_mode = self._read_byte(self.ADDR_GAME_MODE)
        area_id = self._read_byte(self.ADDR_AREA_ID)

        # Calculate tile position (screen-relative)
        tile_x = (link_x % 512) // 8
        tile_y = (link_y % 512) // 8

        # Get current tile type
        cmap = self._collision_cache
        current_tile = cmap.get_tile(tile_x, tile_y) if cmap else 0

        state = NavState(
            timestamp=datetime.now().isoformat(),
            link_x=link_x,
            link_y=link_y,
            game_mode=game_mode,
            area_id=area_id,
            tile_x=tile_x,
            tile_y=tile_y,
            current_tile=current_tile,
            frame=frame,
        )
        self._states.append(state)
        return state

    def find_path(self, start_tile: Tuple[int, int],
                  goal_tile: Tuple[int, int],
                  collision_map: CollisionMap,
                  max_iterations: int = 5000) -> Optional[List[Tuple[int, int]]]:
        """Find path using A* algorithm.

        Args:
            start_tile: Starting tile (x, y)
            goal_tile: Goal tile (x, y)
            collision_map: Collision map to use
            max_iterations: Maximum iterations before giving up

        Returns:
            List of tile coordinates or None if no path found
        """
        # Check if start/goal are valid
        if not collision_map.is_walkable(start_tile[0], start_tile[1]):
            # If start is blocked, try adjacent tiles
            for dx, dy in [(0, 0), (-1, 0), (1, 0), (0, -1), (0, 1)]:
                nx, ny = start_tile[0] + dx, start_tile[1] + dy
                if collision_map.is_walkable(nx, ny):
                    start_tile = (nx, ny)
                    break
            else:
                return None

        if not collision_map.is_walkable(goal_tile[0], goal_tile[1]):
            # If goal is blocked, find nearest walkable tile
            best_dist = float('inf')
            best_tile = None
            for dy in range(-5, 6):
                for dx in range(-5, 6):
                    nx, ny = goal_tile[0] + dx, goal_tile[1] + dy
                    if collision_map.is_walkable(nx, ny):
                        dist = abs(dx) + abs(dy)
                        if dist < best_dist:
                            best_dist = dist
                            best_tile = (nx, ny)
            if best_tile:
                goal_tile = best_tile
            else:
                return None

        # A* algorithm
        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> float:
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        open_set: List[PathNode] = []
        start_node = PathNode(
            x=start_tile[0],
            y=start_tile[1],
            g_cost=0,
            h_cost=heuristic(start_tile, goal_tile)
        )
        heapq.heappush(open_set, start_node)

        closed_set: Set[Tuple[int, int]] = set()
        came_from: Dict[Tuple[int, int], PathNode] = {start_tile: start_node}

        iterations = 0
        while open_set and iterations < max_iterations:
            iterations += 1
            current = heapq.heappop(open_set)
            current_pos = (current.x, current.y)

            if current_pos == goal_tile:
                # Reconstruct path
                path = []
                node = current
                while node:
                    path.append((node.x, node.y))
                    node = node.parent
                return list(reversed(path))

            if current_pos in closed_set:
                continue
            closed_set.add(current_pos)

            for nx, ny in collision_map.get_neighbors(current.x, current.y):
                neighbor_pos = (nx, ny)
                if neighbor_pos in closed_set:
                    continue

                tentative_g = current.g_cost + 1

                if neighbor_pos in came_from:
                    existing = came_from[neighbor_pos]
                    if tentative_g >= existing.g_cost:
                        continue

                neighbor = PathNode(
                    x=nx,
                    y=ny,
                    g_cost=tentative_g,
                    h_cost=heuristic(neighbor_pos, goal_tile),
                    parent=current
                )
                came_from[neighbor_pos] = neighbor
                heapq.heappush(open_set, neighbor)

        return None

    def path_to_directions(self, path: List[Tuple[int, int]]) -> List[Tuple[str, int]]:
        """Convert tile path to movement directions.

        Args:
            path: List of tile coordinates

        Returns:
            List of (direction, tiles) tuples with merged consecutive directions
        """
        if len(path) < 2:
            return []

        directions = []
        current_dir = None
        current_count = 0

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

            if direction == current_dir:
                current_count += 1
            else:
                if current_dir:
                    directions.append((current_dir, current_count))
                current_dir = direction
                current_count = 1

        if current_dir:
            directions.append((current_dir, current_count))

        return directions

    def execute_move(self, direction: str, frames: int = 15) -> None:
        """Execute a movement in the given direction.

        Args:
            direction: "UP", "DOWN", "LEFT", "RIGHT"
            frames: Number of frames to hold the button
        """
        self.bridge.press_button(direction, frames)
        # Run frames to advance emulation
        if hasattr(self.bridge, 'run_frames'):
            self.bridge.run_frames(frames)
        time.sleep(frames / 60.0 * 0.3)  # Brief pause

    def navigate_to(self, target_x: int, target_y: int,
                    use_pathfinding: bool = True) -> NavAttempt:
        """Navigate to target coordinates with obstacle avoidance.

        Args:
            target_x: Target X pixel coordinate
            target_y: Target Y pixel coordinate
            use_pathfinding: If True, use A* when stuck; otherwise greedy only

        Returns:
            NavAttempt with result and path information
        """
        self._states.clear()
        frames_elapsed = 0
        path_taken = []
        stuck_count = 0
        last_position = None

        # Capture initial state
        start_state = self.capture_state(0)
        if not start_state.is_overworld and not start_state.is_indoors:
            return NavAttempt(
                result=NavResult.FAILED_WRONG_MODE,
                start_x=start_state.link_x,
                start_y=start_state.link_y,
                end_x=start_state.link_x,
                end_y=start_state.link_y,
                target_x=target_x,
                target_y=target_y,
                error_message=f"Invalid game mode: {start_state.game_mode:#x}",
            )

        # Read collision map
        cmap = self.read_collision_map(force_refresh=True)
        if cmap is None and use_pathfinding:
            # Can still try greedy navigation without collision map
            pass

        # Navigation loop
        while frames_elapsed < self.timeout_frames:
            state = self.capture_state(frames_elapsed)
            path_taken.append((state.link_x, state.link_y))

            # Check arrival
            dx = target_x - state.link_x
            dy = target_y - state.link_y
            distance = math.sqrt(dx*dx + dy*dy)
            primary_dir = self._primary_direction(dx, dy)

            if distance < self._arrival_threshold:
                return NavAttempt(
                    result=NavResult.SUCCESS,
                    start_x=start_state.link_x,
                    start_y=start_state.link_y,
                    end_x=state.link_x,
                    end_y=state.link_y,
                    target_x=target_x,
                    target_y=target_y,
                    path_length=len(path_taken),
                    frames_elapsed=frames_elapsed,
                    path_taken=path_taken,
                    states=list(self._states),
                )

            # Check if stuck
            current_pos = (state.link_x, state.link_y)
            if current_pos == last_position:
                stuck_count += 1
            else:
                stuck_count = 0
            last_position = current_pos

            if stuck_count >= self._stuck_threshold:
                if state.is_overworld:
                    moved, frames_elapsed = self._try_micro_adjust(primary_dir, frames_elapsed, cmap)
                    if moved:
                        stuck_count = 0
                        continue
                if use_pathfinding and cmap:
                    # Try A* pathfinding to get around obstacle
                    start_tile = (state.tile_x, state.tile_y)
                    goal_tile = ((target_x % 512) // 8, (target_y % 512) // 8)

                    path = self.find_path(start_tile, goal_tile, cmap)
                    if path and len(path) > 1:
                        # Execute first few moves of the path
                        directions = self.path_to_directions(path[:10])
                        for direction, tiles in directions[:3]:
                            frames_per_tile = 10  # 10 frames per tile movement
                            move_frames = tiles * frames_per_tile
                            _, _, frames_elapsed = self._attempt_move(direction, move_frames, frames_elapsed, cmap)
                        stuck_count = 0
                        continue

                # Stuck and no path found - try alternate direction
                stuck_count = 0
                alternate_dirs = ["LEFT", "RIGHT", "UP", "DOWN"]
                # Try perpendicular direction first
                if abs(dx) > abs(dy):
                    alternate_dirs = ["UP", "DOWN", "LEFT", "RIGHT"]
                for alt_dir in alternate_dirs:
                    _, moved, frames_elapsed = self._attempt_move(alt_dir, 20, frames_elapsed, cmap)
                    if moved:
                        break
                continue

            # Greedy navigation: move toward target
            direction = primary_dir

            _, _, frames_elapsed = self._attempt_move(direction, 15, frames_elapsed, cmap)

        # Timeout
        final_state = self.capture_state(frames_elapsed)
        return NavAttempt(
            result=NavResult.FAILED_TIMEOUT,
            start_x=start_state.link_x,
            start_y=start_state.link_y,
            end_x=final_state.link_x,
            end_y=final_state.link_y,
            target_x=target_x,
            target_y=target_y,
            path_length=len(path_taken),
            frames_elapsed=frames_elapsed,
            path_taken=path_taken,
            states=list(self._states),
            error_message=f"Timeout after {frames_elapsed} frames",
        )

    def navigate_to_tile(self, tile_x: int, tile_y: int) -> NavAttempt:
        """Navigate to a specific tile coordinate.

        Args:
            tile_x: Target tile X (0-63)
            tile_y: Target tile Y (0-63)

        Returns:
            NavAttempt with result
        """
        # Convert tile to pixel (center of tile)
        target_x = (tile_x * 8) + 4
        target_y = (tile_y * 8) + 4
        return self.navigate_to(target_x, target_y)

    def get_collision_debug(self) -> Dict[str, Any]:
        """Get debug information about collision map.

        Returns:
            Dict with collision map statistics
        """
        cmap = self.read_collision_map()
        if not cmap:
            return {"error": "Could not read collision map"}

        # Count tile types
        tile_counts: Dict[int, int] = {}
        for b in cmap.data:
            tile_counts[b] = tile_counts.get(b, 0) + 1

        # Get current state
        state = self.capture_state()

        return {
            "map_size": len(cmap.data),
            "walkable_ratio": cmap.get_walkable_ratio(),
            "link_position": (state.link_x, state.link_y),
            "link_tile": (state.tile_x, state.tile_y),
            "current_tile_type": state.current_tile,
            "top_tile_types": sorted(tile_counts.items(), key=lambda x: -x[1])[:5],
            "area_id": state.area_id,
            "data_kind": cmap.data_kind,
            "source": cmap.source,
            "learned_walkable_tiles": len(self._ow_walkable_by_area.get(state.area_id, set())),
            "learned_blocked_tiles": len(self._ow_blocked_by_area.get(state.area_id, set())),
        }


def run_collision_test():
    """Run a collision navigation test against live Mesen2."""
    try:
        from scripts.mesen2_client_lib.bridge import MesenBridge
    except ImportError:
        print("ERROR: Could not import MesenBridge")
        return None

    bridge = MesenBridge()
    if not bridge.ensure_connected():
        print("ERROR: Cannot connect to Mesen2")
        return None

    print("Connected to Mesen2")

    nav = CollisionNavigator(bridge)

    # Get debug info
    debug = nav.get_collision_debug()
    print(f"\nCollision Map Debug:")
    for key, value in debug.items():
        print(f"  {key}: {value}")

    # Capture current state
    state = nav.capture_state()
    print(f"\nCurrent Position: ({state.link_x}, {state.link_y})")
    print(f"Current Tile: ({state.tile_x}, {state.tile_y}) = {state.current_tile:#x}")

    # Try navigating a short distance
    target_x = state.link_x + 100
    target_y = state.link_y
    print(f"\nAttempting to navigate to ({target_x}, {target_y})...")

    result = nav.navigate_to(target_x, target_y)
    print(f"\nResult: {result.result.name}")
    print(f"  Start: ({result.start_x}, {result.start_y})")
    print(f"  End: ({result.end_x}, {result.end_y})")
    print(f"  Distance remaining: {result.distance_remaining:.1f} px")
    print(f"  Frames elapsed: {result.frames_elapsed}")

    return nav


if __name__ == "__main__":
    run_collision_test()
