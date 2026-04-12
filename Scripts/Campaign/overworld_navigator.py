# -*- coding: utf-8 -*-
"""Overworld Navigation Module for Goal A.2.

This module provides autonomous overworld navigation capabilities,
enabling Link to travel between points of interest across the game world.

Campaign Goals Supported:
- A.2: Navigate overworld to specific locations
- A.3: Enter buildings (integrates with building_navigator)
- D.2: Collision-aware pathfinding

The overworld in Oracle of Secrets is organized into:
- Light World areas (0x00-0x3F)
- Dark World areas (0x40-0x7F with bit 0x80 set)
- Underwater areas (0x70-0x7F)

Key Memory Addresses:
- $7E0010: GameMode (0x09 = overworld)
- $7E008A: Current area ID
- $7E0020-23: Link position (Y, X as low/high byte pairs)
- $7E0022: Link X position (low byte)
- $7E0023: Link X position (high byte)
- $7E0020: Link Y position (low byte)
- $7E0021: Link Y position (high byte)

Usage:
    from scripts.campaign.overworld_navigator import OverworldNavigator

    navigator = OverworldNavigator(bridge)
    result = navigator.navigate_to_poi("village_center")
    result = navigator.navigate_to_coordinates(3200, 3600)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Set
import json
import time
import math

from .locations import (
    OVERWORLD_AREAS,
    get_area_name,
)
from .pathfinder import (
    Pathfinder,
    CollisionMap,
    TileType,
    WALKABLE_TILES,
)


class NavigationMode(Enum):
    """Mode of navigation."""
    DIRECT = auto()          # Walk directly toward target
    PATHFINDING = auto()     # Use A* pathfinding
    AREA_CROSSING = auto()   # Cross between overworld areas
    FOLLOW_WAYPOINTS = auto() # Follow predefined waypoint path


class NavigationStatus(Enum):
    """Status of navigation attempt."""
    SUCCESS = auto()
    IN_PROGRESS = auto()
    FAILED_WRONG_MODE = auto()
    FAILED_NO_PATH = auto()
    FAILED_STUCK = auto()
    FAILED_TIMEOUT = auto()
    FAILED_BLACK_SCREEN = auto()
    FAILED_AREA_MISMATCH = auto()


@dataclass
class PointOfInterest:
    """A named location in the overworld."""
    name: str
    area_id: int
    x: int
    y: int
    description: str = ""
    tags: List[str] = field(default_factory=list)
    entrance_id: Optional[int] = None  # If this POI is a building entrance
    waypoints: List[Tuple[int, int]] = field(default_factory=list)  # Path to reach from nearby

    @property
    def position(self) -> Tuple[int, int]:
        return (self.x, self.y)

    def distance_to(self, x: int, y: int) -> float:
        """Calculate distance from position to this POI."""
        return math.sqrt((self.x - x) ** 2 + (self.y - y) ** 2)


@dataclass
class OverworldState:
    """Captured state of Link on the overworld."""
    timestamp: str
    game_mode: int
    area_id: int
    link_x: int
    link_y: int
    direction: int
    inidisp: int
    submodule: int
    frame_count: int = 0

    @property
    def is_on_overworld(self) -> bool:
        """Check if on overworld."""
        return self.game_mode == 0x09

    @property
    def position(self) -> Tuple[int, int]:
        return (self.link_x, self.link_y)

    @property
    def area_name(self) -> str:
        return get_area_name(self.area_id)

    @property
    def is_light_world(self) -> bool:
        """Check if in light world."""
        return self.area_id < 0x40 or (self.area_id & 0x80) == 0

    @property
    def is_dark_world(self) -> bool:
        """Check if in dark world."""
        return (self.area_id & 0x80) != 0 or (0x40 <= self.area_id < 0x70)

    @property
    def is_underwater(self) -> bool:
        """Check if underwater."""
        return 0x70 <= self.area_id <= 0x7F


@dataclass
class NavigationResult:
    """Result of a navigation attempt."""
    status: NavigationStatus
    start_position: Tuple[int, int]
    end_position: Tuple[int, int]
    target_position: Tuple[int, int]
    frames_elapsed: int
    path_length: int
    states_captured: List[OverworldState] = field(default_factory=list)
    error_message: str = ""

    @property
    def success(self) -> bool:
        return self.status == NavigationStatus.SUCCESS

    @property
    def distance_to_target(self) -> float:
        """Distance from end position to target."""
        return math.sqrt(
            (self.end_position[0] - self.target_position[0]) ** 2 +
            (self.end_position[1] - self.target_position[1]) ** 2
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "status": self.status.name,
            "start_position": self.start_position,
            "end_position": self.end_position,
            "target_position": self.target_position,
            "frames_elapsed": self.frames_elapsed,
            "path_length": self.path_length,
            "distance_to_target": self.distance_to_target,
            "error_message": self.error_message,
            "states_captured": len(self.states_captured),
        }


# =============================================================================
# Points of Interest Database
# =============================================================================
# Key locations for autonomous navigation

POINTS_OF_INTEREST: Dict[str, PointOfInterest] = {
    # Village Area
    "village_center": PointOfInterest(
        name="Village Center",
        area_id=0x29,
        x=3320,
        y=3688,
        description="Central hub of the starting village",
        tags=["town", "start", "shops"],
    ),
    "village_south": PointOfInterest(
        name="Village South",
        area_id=0x28,
        x=3288,
        y=3952,
        description="Southern exit from village",
        tags=["town", "exit"],
    ),
    "village_east": PointOfInterest(
        name="Village East",
        area_id=0x2A,
        x=3576,
        y=3688,
        description="Eastern area of village",
        tags=["town"],
    ),

    # Ranch Area
    "loom_ranch": PointOfInterest(
        name="Loom Ranch",
        area_id=0x00,
        x=496,
        y=688,
        description="Starting ranch area",
        tags=["start", "ranch"],
    ),
    "ranch_fields": PointOfInterest(
        name="Ranch Fields",
        area_id=0x11,
        x=1520,
        y=1712,
        description="Open fields near ranch",
        tags=["ranch", "field"],
    ),

    # Castle Area
    "hyrule_castle": PointOfInterest(
        name="Hyrule Castle Entrance",
        area_id=0x02,
        x=1000,
        y=648,
        description="Main entrance to Hyrule Castle",
        tags=["castle", "landmark"],
    ),

    # Beach/Harbor
    "maku_beach": PointOfInterest(
        name="Maku Beach",
        area_id=0x32,
        x=4144,
        y=2224,
        description="Beach area with Maku tree",
        tags=["beach", "landmark"],
    ),
    "dragon_ship_harbor": PointOfInterest(
        name="Dragon Ship Harbor",
        area_id=0x30,
        x=3600,
        y=2208,
        description="Harbor with the dragon ship",
        tags=["harbor", "dungeon_entrance"],
    ),

    # Dungeon Entrances
    "tail_palace_entrance": PointOfInterest(
        name="Tail Palace Entrance",
        area_id=0x2F,
        x=3800,
        y=3208,
        description="Entrance to Dungeon 1: Tail Palace",
        tags=["dungeon", "dungeon_1"],
    ),
    "zora_temple_entrance": PointOfInterest(
        name="Zora Temple Area",
        area_id=0x1E,
        x=3600,
        y=1200,
        description="Area near Zora Temple (Dungeon 2)",
        tags=["dungeon", "dungeon_2", "water"],
    ),
    "mushroom_grotto_entrance": PointOfInterest(
        name="Mushroom Grotto Entrance",
        area_id=0x10,
        x=1520,
        y=2480,
        description="Entrance to Mushroom Grotto (Dungeon 3)",
        tags=["dungeon", "dungeon_3", "forest"],
    ),

    # Shrines
    "shrine_of_power": PointOfInterest(
        name="Shrine of Power",
        area_id=0x4B,
        x=5400,
        y=3400,
        description="Shrine of Power location",
        tags=["shrine", "landmark"],
    ),

    # Lost Woods
    "lost_woods_entrance": PointOfInterest(
        name="Lost Woods Entrance",
        area_id=0x40,
        x=256,
        y=3088,
        description="Entrance to the Lost Woods",
        tags=["forest", "puzzle"],
    ),

    # Special Locations
    "hall_of_secrets": PointOfInterest(
        name="Hall of Secrets Area",
        area_id=0x0E,
        x=1776,
        y=1232,
        description="Near the Hall of Secrets",
        tags=["special", "secret"],
    ),
    "sanctuary": PointOfInterest(
        name="Sanctuary",
        area_id=0x13,
        x=2000,
        y=1712,
        description="Church/Sanctuary building",
        tags=["sanctuary", "healing"],
    ),
}


# Area connectivity graph for cross-area navigation
AREA_CONNECTIONS: Dict[int, List[Tuple[int, str, Tuple[int, int]]]] = {
    # Format: area_id -> [(connected_area, direction, exit_position), ...]
    0x29: [  # Village Center
        (0x28, "south", (3288, 3952)),  # To Village South
        (0x2A, "east", (3576, 3688)),   # To Village East
        (0x1D, "north", (3320, 3400)),  # To East Castle Field
    ],
    0x28: [  # Village South
        (0x29, "north", (3288, 3688)),  # To Village Center
        (0x38, "west", (2800, 3952)),   # To Ranch Area
    ],
    0x2A: [  # Village East
        (0x29, "west", (3320, 3688)),   # To Village Center
        (0x2D, "east", (3850, 3688)),   # To Tail Pond
    ],
}


class OverworldNavigator:
    """Autonomous overworld navigation controller.

    Provides high-level navigation commands that combine:
    - State monitoring
    - Pathfinding
    - Input generation
    - Area transitions
    """

    def __init__(self, bridge: Any, timeout_frames: int = 3600):
        """Initialize navigator.

        Args:
            bridge: Mesen2Bridge instance for emulator control
            timeout_frames: Maximum frames before navigation timeout (default 60 seconds at 60fps)
        """
        self.bridge = bridge
        self.timeout_frames = timeout_frames
        self.pathfinder: Optional[Pathfinder] = None
        self._current_state: Optional[OverworldState] = None
        self._states_history: List[OverworldState] = []
        self._stuck_threshold = 60  # Frames without movement = stuck
        self._arrival_threshold = 16  # Pixels within target = arrived

    def capture_state(self) -> OverworldState:
        """Capture current overworld state from emulator.

        Returns:
            OverworldState with current position and status
        """
        # Read key memory addresses
        game_mode = self._read_byte(0x7E0010)
        submodule = self._read_byte(0x7E0011)
        inidisp = self._read_byte(0x7E0013)  # INIDISP queue (WRAM)
        area_id = self._read_byte(0x7E008A)

        # Link position (16-bit values)
        link_y = self._read_word(0x7E0020)
        link_x = self._read_word(0x7E0022)

        # Link direction
        direction = self._read_byte(0x7E002F)

        state = OverworldState(
            timestamp=datetime.now().isoformat(),
            game_mode=game_mode,
            area_id=area_id,
            link_x=link_x,
            link_y=link_y,
            direction=direction,
            inidisp=inidisp,
            submodule=submodule,
            frame_count=len(self._states_history),
        )

        self._current_state = state
        self._states_history.append(state)

        return state

    def get_state(self) -> Optional[OverworldState]:
        """Get most recent captured state."""
        return self._current_state

    def _read_byte(self, address: int) -> int:
        """Read a single byte from memory."""
        if hasattr(self.bridge, 'read_memory'):
            # MesenBridge.read_memory(address) returns a single int
            return self.bridge.read_memory(address)
        return 0

    def _read_word(self, address: int) -> int:
        """Read a 16-bit word from memory (little-endian)."""
        # Prefer read_memory16 if available (more efficient)
        if hasattr(self.bridge, 'read_memory16'):
            return self.bridge.read_memory16(address)
        elif hasattr(self.bridge, 'read_memory'):
            # Fallback: Read two consecutive bytes and combine
            lo = self.bridge.read_memory(address)
            hi = self.bridge.read_memory(address + 1)
            return lo | (hi << 8)
        return 0

    def get_poi(self, name: str) -> Optional[PointOfInterest]:
        """Get a point of interest by name.

        Args:
            name: POI identifier (e.g., "village_center")

        Returns:
            PointOfInterest or None if not found
        """
        return POINTS_OF_INTEREST.get(name.lower().replace(" ", "_"))

    def list_pois(self, tag: Optional[str] = None) -> List[PointOfInterest]:
        """List all points of interest, optionally filtered by tag.

        Args:
            tag: Optional tag to filter by (e.g., "dungeon", "town")

        Returns:
            List of matching POIs
        """
        pois = list(POINTS_OF_INTEREST.values())
        if tag:
            pois = [p for p in pois if tag.lower() in [t.lower() for t in p.tags]]
        return pois

    def find_nearest_poi(self, x: int, y: int,
                         tag: Optional[str] = None) -> Optional[PointOfInterest]:
        """Find nearest POI to given coordinates.

        Args:
            x: Current X position
            y: Current Y position
            tag: Optional tag to filter candidates

        Returns:
            Nearest POI or None if no candidates
        """
        candidates = self.list_pois(tag)
        if not candidates:
            return None

        return min(candidates, key=lambda p: p.distance_to(x, y))

    def calculate_direction(self, from_x: int, from_y: int,
                           to_x: int, to_y: int) -> str:
        """Calculate cardinal direction from one point to another.

        Args:
            from_x, from_y: Starting position
            to_x, to_y: Target position

        Returns:
            Direction string: "UP", "DOWN", "LEFT", "RIGHT", or compound
        """
        dx = to_x - from_x
        dy = to_y - from_y

        # Determine primary direction based on larger delta
        if abs(dx) > abs(dy):
            return "RIGHT" if dx > 0 else "LEFT"
        else:
            return "DOWN" if dy > 0 else "UP"

    def walk_toward(self, target_x: int, target_y: int,
                    frames: int = 30) -> bool:
        """Walk toward a target position for specified frames.

        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            frames: Number of frames to walk

        Returns:
            True if movement was executed
        """
        state = self.capture_state()
        if not state.is_on_overworld:
            return False

        direction = self.calculate_direction(
            state.link_x, state.link_y,
            target_x, target_y
        )

        # Execute movement via bridge
        if hasattr(self.bridge, 'press_button'):
            self.bridge.press_button(direction, frames)
            return True
        elif hasattr(self.bridge, 'input_inject'):
            self.bridge.input_inject(buttons=[direction], frames=frames)
            return True

        return False

    def is_at_position(self, target_x: int, target_y: int,
                       threshold: Optional[int] = None) -> bool:
        """Check if Link is at (or near) target position.

        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            threshold: Distance threshold (default: self._arrival_threshold)

        Returns:
            True if within threshold of target
        """
        if threshold is None:
            threshold = self._arrival_threshold

        state = self.capture_state()
        distance = math.sqrt(
            (state.link_x - target_x) ** 2 +
            (state.link_y - target_y) ** 2
        )
        return distance <= threshold

    def is_stuck(self) -> bool:
        """Check if Link appears stuck (no movement for threshold frames).

        Returns:
            True if position unchanged for _stuck_threshold frames
        """
        if len(self._states_history) < self._stuck_threshold:
            return False

        recent = self._states_history[-self._stuck_threshold:]
        first_pos = (recent[0].link_x, recent[0].link_y)

        return all(
            (s.link_x, s.link_y) == first_pos
            for s in recent[1:]
        )

    def navigate_to_coordinates(self, target_x: int, target_y: int,
                                mode: NavigationMode = NavigationMode.DIRECT
                                ) -> NavigationResult:
        """Navigate to specific coordinates.

        Args:
            target_x: Target X coordinate
            target_y: Target Y coordinate
            mode: Navigation mode (DIRECT or PATHFINDING)

        Returns:
            NavigationResult with success/failure status
        """
        self._states_history.clear()
        start_state = self.capture_state()

        if not start_state.is_on_overworld:
            return NavigationResult(
                status=NavigationStatus.FAILED_WRONG_MODE,
                start_position=start_state.position,
                end_position=start_state.position,
                target_position=(target_x, target_y),
                frames_elapsed=0,
                path_length=0,
                error_message=f"Not on overworld (mode={start_state.game_mode:#x})",
            )

        frames_elapsed = 0
        path_length = 0

        while frames_elapsed < self.timeout_frames:
            state = self.capture_state()

            # Check for success
            if self.is_at_position(target_x, target_y):
                return NavigationResult(
                    status=NavigationStatus.SUCCESS,
                    start_position=start_state.position,
                    end_position=state.position,
                    target_position=(target_x, target_y),
                    frames_elapsed=frames_elapsed,
                    path_length=path_length,
                    states_captured=list(self._states_history),
                )

            # Check for stuck
            if self.is_stuck():
                return NavigationResult(
                    status=NavigationStatus.FAILED_STUCK,
                    start_position=start_state.position,
                    end_position=state.position,
                    target_position=(target_x, target_y),
                    frames_elapsed=frames_elapsed,
                    path_length=path_length,
                    states_captured=list(self._states_history),
                    error_message="Link stuck - no movement detected",
                )

            # Check for mode change (entered building, etc.)
            if not state.is_on_overworld:
                return NavigationResult(
                    status=NavigationStatus.FAILED_WRONG_MODE,
                    start_position=start_state.position,
                    end_position=state.position,
                    target_position=(target_x, target_y),
                    frames_elapsed=frames_elapsed,
                    path_length=path_length,
                    states_captured=list(self._states_history),
                    error_message=f"Left overworld (mode={state.game_mode:#x})",
                )

            # Walk toward target
            if mode == NavigationMode.DIRECT:
                self.walk_toward(target_x, target_y, frames=30)
                frames_elapsed += 30
                path_length += 1

        # Timeout
        final_state = self.capture_state()
        return NavigationResult(
            status=NavigationStatus.FAILED_TIMEOUT,
            start_position=start_state.position,
            end_position=final_state.position,
            target_position=(target_x, target_y),
            frames_elapsed=frames_elapsed,
            path_length=path_length,
            states_captured=list(self._states_history),
            error_message=f"Timeout after {frames_elapsed} frames",
        )

    def navigate_to_poi(self, poi_name: str) -> NavigationResult:
        """Navigate to a named point of interest.

        Args:
            poi_name: Name of POI (e.g., "village_center", "tail_palace_entrance")

        Returns:
            NavigationResult with success/failure status
        """
        poi = self.get_poi(poi_name)
        if poi is None:
            return NavigationResult(
                status=NavigationStatus.FAILED_NO_PATH,
                start_position=(0, 0),
                end_position=(0, 0),
                target_position=(0, 0),
                frames_elapsed=0,
                path_length=0,
                error_message=f"Unknown POI: {poi_name}",
            )

        return self.navigate_to_coordinates(poi.x, poi.y)

    def navigate_to_area(self, area_id: int) -> NavigationResult:
        """Navigate to a specific overworld area.

        Uses AREA_CONNECTIONS to find exit points.

        Args:
            area_id: Target area ID

        Returns:
            NavigationResult with success/failure status
        """
        state = self.capture_state()
        if state.area_id == area_id:
            return NavigationResult(
                status=NavigationStatus.SUCCESS,
                start_position=state.position,
                end_position=state.position,
                target_position=state.position,
                frames_elapsed=0,
                path_length=0,
            )

        # Find connection from current area to target
        connections = AREA_CONNECTIONS.get(state.area_id, [])
        for connected_area, direction, exit_pos in connections:
            if connected_area == area_id:
                return self.navigate_to_coordinates(exit_pos[0], exit_pos[1])

        # No direct connection found
        return NavigationResult(
            status=NavigationStatus.FAILED_NO_PATH,
            start_position=state.position,
            end_position=state.position,
            target_position=(0, 0),
            frames_elapsed=0,
            path_length=0,
            error_message=f"No path from area {state.area_id:#x} to {area_id:#x}",
        )

    def get_area_pois(self, area_id: Optional[int] = None) -> List[PointOfInterest]:
        """Get all POIs in an area.

        Args:
            area_id: Area to search (default: current area)

        Returns:
            List of POIs in the area
        """
        if area_id is None:
            state = self.capture_state()
            area_id = state.area_id

        return [p for p in POINTS_OF_INTEREST.values() if p.area_id == area_id]

    def patrol_area(self, waypoints: Optional[List[Tuple[int, int]]] = None,
                    loops: int = 1) -> List[NavigationResult]:
        """Patrol through waypoints in current area.

        Args:
            waypoints: List of (x, y) coordinates to visit
            loops: Number of times to repeat the patrol

        Returns:
            List of NavigationResults for each leg
        """
        if waypoints is None:
            # Default: visit all POIs in current area
            state = self.capture_state()
            pois = self.get_area_pois(state.area_id)
            waypoints = [p.position for p in pois]

        results = []
        for _ in range(loops):
            for x, y in waypoints:
                result = self.navigate_to_coordinates(x, y)
                results.append(result)
                if not result.success:
                    return results

        return results

    def get_navigation_stats(self) -> Dict[str, Any]:
        """Get statistics about recent navigation.

        Returns:
            Dict with navigation statistics
        """
        if not self._states_history:
            return {}

        first = self._states_history[0]
        last = self._states_history[-1]

        total_distance = 0
        for i in range(1, len(self._states_history)):
            prev = self._states_history[i - 1]
            curr = self._states_history[i]
            total_distance += math.sqrt(
                (curr.link_x - prev.link_x) ** 2 +
                (curr.link_y - prev.link_y) ** 2
            )

        return {
            "total_frames": len(self._states_history),
            "start_position": first.position,
            "end_position": last.position,
            "total_distance_traveled": total_distance,
            "areas_visited": len(set(s.area_id for s in self._states_history)),
            "stuck_count": sum(1 for i in range(self._stuck_threshold, len(self._states_history))
                              if all(self._states_history[i - j].position == self._states_history[i].position
                                    for j in range(self._stuck_threshold))),
        }

    def reset(self):
        """Reset navigator state."""
        self._states_history.clear()
        self._current_state = None


# =============================================================================
# Convenience Functions
# =============================================================================

def get_poi_names() -> List[str]:
    """Get all POI names."""
    return list(POINTS_OF_INTEREST.keys())


def get_pois_by_tag(tag: str) -> List[PointOfInterest]:
    """Get POIs with a specific tag."""
    return [p for p in POINTS_OF_INTEREST.values() if tag.lower() in [t.lower() for t in p.tags]]


def get_dungeon_pois() -> List[PointOfInterest]:
    """Get all dungeon entrance POIs."""
    return get_pois_by_tag("dungeon")


def get_town_pois() -> List[PointOfInterest]:
    """Get all town/village POIs."""
    return get_pois_by_tag("town")
