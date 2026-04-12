"""Dungeon room navigator for Oracle of Secrets / ALTTP.

Navigates Link between dungeon rooms using z3ed graph data and Mesen2
pos-teleport primitives.

Algorithm per hop:
  1. Load door tile data from z3ed (dungeon-describe-room)
  2. Compute door's world pixel coordinate from room grid formula
  3. Align Link's X (N/S door) or Y (E/W door) to the door
  4. Press direction button until ROOM_ID changes, or timeout

Room grid world coordinate formula (calibrated from save state):
  room_base_x = 9   + (room_id & 0xF) * 512
  room_base_y = -139 + (room_id >> 4) * 512
  door_world_x = room_base_x + tile_x * 8
  door_world_y = room_base_y + tile_y * 8

Source calibration: room 0x98 save state with Link at (4217, 4677),
south door to 0xA8 at tile (14, 26) → room_base = (4105, 4469).
  col=8 → col_base = 4105 - 8*512 = 9
  row=9 → row_base = 4469 - 9*512 = -139
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .constants import OracleRAM

# ---------------------------------------------------------------------------
# World coordinate constants (calibrated, see module docstring)
# ---------------------------------------------------------------------------

_DUNGEON_COL_BASE = 9
_DUNGEON_ROW_BASE = -139
_ROOM_WIDTH = 512   # pixels
_ROOM_HEIGHT = 512  # pixels
_TILE_SIZE = 8      # pixels per tile


def room_world_base(room_id: int) -> tuple[int, int]:
    """Return (world_base_x, world_base_y) for a dungeon room."""
    col = room_id & 0xF
    row = room_id >> 4
    return (
        _DUNGEON_COL_BASE + col * _ROOM_WIDTH,
        _DUNGEON_ROW_BASE + row * _ROOM_HEIGHT,
    )


def door_world_pos(room_id: int, tile_x: int, tile_y: int) -> tuple[int, int]:
    """Return absolute world coordinates for a door tile in a room."""
    bx, by = room_world_base(room_id)
    return (bx + tile_x * _TILE_SIZE, by + tile_y * _TILE_SIZE)


# ---------------------------------------------------------------------------
# Door edge data
# ---------------------------------------------------------------------------

# Map from z3ed direction string to gamepad button
_DIR_TO_BUTTON: dict[str, str] = {
    "door_north": "up",
    "door_south": "down",
    "door_west":  "left",
    "door_east":  "right",
}

# Map from z3ed direction to the axis used for alignment
# N/S doors: align on X axis; E/W doors: align on Y axis
_DIR_ALIGNS_X = {"door_north", "door_south"}


@dataclass
class DoorEdge:
    """A traversable door connection between two dungeon rooms."""
    from_room: int
    to_room: int
    direction: str       # "door_north" | "door_south" | "door_west" | "door_east"
    door_type: str       # human-readable type name
    tile_x: int
    tile_y: int

    @property
    def button(self) -> str:
        return _DIR_TO_BUTTON.get(self.direction, "up")

    @property
    def aligns_x(self) -> bool:
        """True if this door requires X alignment (N/S doors)."""
        return self.direction in _DIR_ALIGNS_X

    def world_pos(self) -> tuple[int, int]:
        return door_world_pos(self.from_room, self.tile_x, self.tile_y)


@dataclass
class StairEdge:
    """A staircase or holewarp connection (handled differently from doors)."""
    from_room: int
    to_room: int
    kind: str  # "stair1"-"stair4" or "holewarp"


# ---------------------------------------------------------------------------
# Graph type
# ---------------------------------------------------------------------------

@dataclass
class DungeonGraph:
    """Adjacency graph for dungeon navigation."""
    door_edges: dict[int, list[DoorEdge]] = field(default_factory=dict)
    stair_edges: dict[int, list[StairEdge]] = field(default_factory=dict)
    rooms: list[int] = field(default_factory=list)

    def add_door(self, edge: DoorEdge) -> None:
        self.door_edges.setdefault(edge.from_room, []).append(edge)

    def add_stair(self, edge: StairEdge) -> None:
        self.stair_edges.setdefault(edge.from_room, []).append(edge)

    def bfs_path(self, from_room: int, to_room: int) -> list[DoorEdge]:
        """BFS shortest path using door edges only. Returns edge list."""
        if from_room == to_room:
            return []
        queue: deque[tuple[int, list[DoorEdge]]] = deque([(from_room, [])])
        visited: set[int] = {from_room}
        while queue:
            room, path = queue.popleft()
            for edge in self.door_edges.get(room, []):
                if edge.to_room in visited:
                    continue
                new_path = path + [edge]
                if edge.to_room == to_room:
                    return new_path
                visited.add(edge.to_room)
                queue.append((edge.to_room, new_path))
        return []


# ---------------------------------------------------------------------------
# Navigator
# ---------------------------------------------------------------------------

class DungeonNavigator:
    """Navigate Link between dungeon rooms via pos-teleport + direction press.

    Usage::

        nav = DungeonNavigator(client, rom_path="/path/to/oos168x.sfc",
                               entrance_id=0x27)
        nav.build_graph()
        ok = nav.go_to_room(0xDA)

    The navigator builds a graph once via z3ed and caches it.  Each call to
    go_to_room() does a fresh BFS and executes the path step-by-step.
    """

    def __init__(
        self,
        client,
        rom_path: str,
        entrance_id: int,
        z3ed_path: Optional[str] = None,
        step_frames: int = 30,
        timeout_frames: int = 180,
    ) -> None:
        self.client = client
        self.rom_path = rom_path
        self.entrance_id = entrance_id
        self.z3ed_path = z3ed_path or self._find_z3ed()
        self.step_frames = step_frames       # frames to press button per step
        self.timeout_frames = timeout_frames  # frames before giving up on transition
        self._graph: Optional[DungeonGraph] = None

    # ------------------------------------------------------------------
    # Graph building
    # ------------------------------------------------------------------

    def build_graph(self, same_blockset: bool = True) -> DungeonGraph:
        """Build navigation graph from z3ed dungeon-room-graph output."""
        args = [
            "dungeon-room-graph",
            f"--entrance=0x{self.entrance_id:02X}",
        ]
        if same_blockset:
            args.append("--same-blockset")
        data = self._run_z3ed(*args)["room_graph"]

        graph = DungeonGraph()
        graph.rooms = [int(r["room_id"], 16) for r in data.get("rooms", [])]

        for edge in data.get("door_edges", []):
            if edge.get("is_exit"):
                continue
            to_str = edge.get("to", "exit")
            if to_str == "exit":
                continue
            graph.add_door(DoorEdge(
                from_room=int(edge["from"], 16),
                to_room=int(to_str, 16),
                direction=edge["type"],
                door_type=edge["door_type"],
                tile_x=edge["tile_x"],
                tile_y=edge["tile_y"],
            ))

        for edge in data.get("stair_edges", []):
            graph.add_stair(StairEdge(
                from_room=int(edge["from"], 16),
                to_room=int(edge["to"], 16),
                kind=edge["type"],
            ))

        self._graph = graph
        n_rooms = len(graph.rooms)
        n_door_edges = sum(len(v) for v in graph.door_edges.values())
        print(
            f"[DungeonNavigator] Graph built: "
            f"{n_rooms} rooms, {n_door_edges} door edges"
        )
        return graph

    def get_graph(self) -> DungeonGraph:
        if self._graph is None:
            self.build_graph()
        return self._graph

    # ------------------------------------------------------------------
    # High-level navigation
    # ------------------------------------------------------------------

    def go_to_room(self, target_room_id: int) -> bool:
        """Navigate Link from current room to target_room_id.

        Returns True on success, False on failure.
        """
        graph = self.get_graph()
        current_room = self._read_room_id()
        if current_room == target_room_id:
            print(f"[DungeonNavigator] Already in room 0x{target_room_id:02X}")
            return True

        path = graph.bfs_path(current_room, target_room_id)
        if not path:
            print(
                f"[DungeonNavigator] No door path from "
                f"0x{current_room:02X} to 0x{target_room_id:02X}"
            )
            return False

        route = " → ".join(
            [f"0x{path[0].from_room:02X}"] + [f"0x{e.to_room:02X}" for e in path]
        )
        print(f"[DungeonNavigator] Path ({len(path)} steps): {route}")

        for step_idx, edge in enumerate(path):
            step_num = step_idx + 1
            print(
                f"[DungeonNavigator] Step {step_num}/{len(path)}: "
                f"0x{edge.from_room:02X} → 0x{edge.to_room:02X} "
                f"({edge.direction}, tile={edge.tile_x},{edge.tile_y})"
            )
            if not self._traverse_door(edge):
                print(f"[DungeonNavigator] Step {step_num} failed")
                return False
            # After each room transition, wait for the walk-in animation
            # to complete (~60 frames) before attempting the next step.
            if step_idx < len(path) - 1:
                time.sleep(60 / 60)

        final = self._read_room_id()
        if final != target_room_id:
            print(
                f"[DungeonNavigator] Navigation ended in 0x{final:02X}, "
                f"expected 0x{target_room_id:02X}"
            )
            return False
        print(f"[DungeonNavigator] Arrived at 0x{target_room_id:02X}")
        return True

    # ------------------------------------------------------------------
    # Door traversal primitive
    # ------------------------------------------------------------------

    def _pick_closest_door(self, edge: DoorEdge, link_x: int, link_y: int) -> DoorEdge:
        """Among all door edges with same (from_room, to_room, direction),
        return the one whose alignment coordinate is closest to Link."""
        graph = self.get_graph()
        candidates = [
            e for e in graph.door_edges.get(edge.from_room, [])
            if e.to_room == edge.to_room and e.direction == edge.direction
        ]
        if len(candidates) <= 1:
            return edge

        def alignment_dist(e: DoorEdge) -> int:
            wx, wy = e.world_pos()
            return abs(wx - link_x) if e.aligns_x else abs(wy - link_y)

        best = min(candidates, key=alignment_dist)
        if best.tile_x != edge.tile_x or best.tile_y != edge.tile_y:
            print(
                f"[DungeonNavigator] Selecting door at tile({best.tile_x},{best.tile_y}) "
                f"over tile({edge.tile_x},{edge.tile_y}) (closer to Link at "
                f"x={link_x},y={link_y})"
            )
        return best

    def _traverse_door(self, edge: DoorEdge) -> bool:
        """Navigate Link to a door and press through it.

        For N/S doors:
          - Teleports Link's X to align with the door column (tile_x).
          - Keeps Link's current Y and presses the direction.

        For E/W doors:
          - Walks Link up or down first (perpendicular pre-alignment) to
            approach the door's Y row (tile_y), since teleporting into the
            door Y may land inside collision.
          - Then presses the direction button.

        When multiple door edges exist for the same (from_room, to_room,
        direction), picks the one whose alignment coordinate is closest to
        Link's current position.
        """
        link_x = self.client.bridge.read_memory16(OracleRAM.LINK_X)
        link_y = self.client.bridge.read_memory16(OracleRAM.LINK_Y)

        # Pick the door closest to Link's current position
        best_edge = self._pick_closest_door(edge, link_x, link_y)
        door_x, door_y = best_edge.world_pos()
        expected_room = edge.to_room
        start_room = self._read_room_id()

        if best_edge.aligns_x:
            # N/S door: teleport X alignment, keep Y, then press direction
            self.client.set_position(door_x, link_y)
            time.sleep(0.05)
        else:
            # E/W door: walk perpendicular (up/down) toward door_y first.
            # Avoids teleporting into collision-blocked rows.  Run until Link
            # reaches door_y or stops moving (natural collision boundary).
            perp_button = "up" if door_y < link_y else "down"
            prev_y = link_y
            stuck_count = 0
            for _ in range(self.timeout_frames):
                self.client.press_button(perp_button, frames=4)
                time.sleep(4 / 60)
                # Bail early if room changed during pre-alignment
                if self._read_room_id() != start_room:
                    return self._read_room_id() == expected_room
                cur_y = self.client.bridge.read_memory16(OracleRAM.LINK_Y)
                if abs(cur_y - door_y) < 32:
                    break  # close enough to door row
                if cur_y == prev_y:
                    stuck_count += 1
                    if stuck_count >= 8:
                        break  # Link isn't moving, stop pre-aligning
                else:
                    stuck_count = 0
                prev_y = cur_y

        # Press door direction and poll for room change
        for _ in range(self.timeout_frames):
            self.client.press_button(best_edge.button, frames=4)
            time.sleep(4 / 60)
            current = self._read_room_id()
            if current == expected_room:
                time.sleep(8 / 60)
                if self._read_room_id() == expected_room:
                    return True
            elif current != start_room:
                print(
                    f"[DungeonNavigator] Warning: entered 0x{current:02X} "
                    f"instead of 0x{expected_room:02X}"
                )
                return False

        print(
            f"[DungeonNavigator] Timeout waiting for 0x{expected_room:02X} "
            f"(still in 0x{self._read_room_id():02X})"
        )
        return False

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _read_room_id(self) -> int:
        return self.client.bridge.read_memory16(OracleRAM.ROOM_ID) & 0xFF

    def _find_z3ed(self) -> str:
        z3ed = shutil.which("z3ed")
        if z3ed:
            return z3ed
        candidates = [
            str(Path.home() / "src/hobby/yaze/build/bin/Debug/z3ed"),
            str(Path.home() / "src/hobby/yaze/build/bin/z3ed"),
            "/usr/local/bin/z3ed",
        ]
        for c in candidates:
            if Path(c).exists():
                return c
        raise FileNotFoundError(
            "z3ed binary not found. Set z3ed_path= or put z3ed on PATH."
        )

    def _run_z3ed(self, *args) -> dict:
        # z3ed requires: z3ed <command> --rom <path> --format json [command-flags]
        subcmd = list(args[:1])
        flags = list(args[1:])
        cmd = [self.z3ed_path] + subcmd + ["--rom", self.rom_path, "--format", "json"] + flags
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if result.returncode != 0:
            raise RuntimeError(f"z3ed command failed: {result.stderr.strip()}")
        return json.loads(result.stdout)
