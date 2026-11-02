"""A* for Link inside one underworld room, over the live 8 px collision map.

Sources (usdasm = ~/src/hobby/usdasm, vanilla US disassembly):
  Collision map: COLMAPA $7F2000 (layer BG2/lower), COLMAPB $7F3000 (upper);
    Core/ram.asm:5993-5994. Layer select: $EE != 0 adds $1000
    (usdasm bank_07.asm TileDetection_Execute_underworld #_07D9FC-#_07DA01).
  Index: ((Y & $1F8) << 3) + ((X >> 3) & $3F): 64x64 cells of 8 px per layer,
    room-local (#_07D9EA-#_07D9F9; same formula in Tests/native/portal_placement.py).
  Link position: $22 X, $20 Y (16-bit absolute), $EE layer, $A0 room. Room-local
    = absolute - ((room & 15) * 512, (room >> 4) * 512) (Tests/native/goron97_cart_gate.py snap()).
  Body: TileDetect_Movement offsets (#_07CD7B-#_07CD97). Vertical moves probe
    X+0/+8/+15 at Y+8 (up) or Y+24 (down, the next row); horizontal moves probe
    Y+8/+16/+23 at X+0 (left) or X+15 (right). Link's solid body is therefore the
    16x16 box X..X+15, Y+8..Y+23.
  Feet: TileDetect_MainHandler offset_x 8 / offset_y 20 (#_07CFCC, #_07D01C) is the
    standing-tile probe for pits, deep water and spikes: (X+8, Y+20). This is the
    "+20 px Y offset" in MEMORY gotcha 4.
  Tile behaviors: underworld vector table $07D7D8 (bank_07.asm:17972-18229).
    Oracle patches $64/$65 to Minish portal handlers (Masks/minish_form.asm:13).

A node (col, row) puts Link's body on cells col..col+1, row..row+1, i.e. Link
X = 8*col, Y = 8*row - 8. Waypoints are room-local Link (lx, ly) pairs, the same
coordinates `goron97_cart_gate.Route.walk()` consumes. Paths are 4-connected, so
each waypoint differs from the previous one on a single axis and the walker's
X-then-Y axis moves follow the path exactly.
"""
from __future__ import annotations

import heapq
from dataclasses import dataclass, field

GRID = 64
CELL = 8
COLMAP_A = 0x7F2000
COLMAP_B = 0x7F3000
LAYER_SIZE = 0x1000

# Vanilla TileBehavior_Nothing ids (UW table), minus Oracle's patched $64/$65.
_NOTHING = ({0x00, 0x05, 0x06, 0x07, 0x14, 0x15, 0x16, 0x17, 0x21, 0x23, 0x24, 0x25,
             0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x41, 0x42, 0x45, 0x47, 0x49, 0x4C, 0x4D,
             0x4E, 0x4F, 0x5E, 0x5F, 0x61, 0x62, 0x66, 0xA6, 0xA7, 0xBE, 0xBF}
            | set(range(0xD0, 0xF0)))
# Walkable but slower or imprecise for the axis walker (ice slides, water slows).
_SLOW = {0x09: 3, 0x0E: 3, 0x0F: 3, 0x40: 2, 0x48: 1, 0x4A: 1}
FLOOR = frozenset(_NOTHING | set(_SLOW))
# Standing on these hurts, drops, swims, moves or transforms Link.
HAZARD = frozenset({0x20, *range(0xB0, 0xBE),   # TileBehavior_Pit
                    0x08,                        # DeepWater
                    0x0D, 0x44,                  # SpikeFloor, Spike
                    0x68, 0x69, 0x6A, 0x6B,      # Conveyors
                    0x64, 0x65})                 # Oracle Minish portal tiles
DOOR = frozenset({*range(0x80, 0xB0), *range(0xF0, 0x100)})
STAIRS = frozenset({0x1D, 0x1E, 0x1F, 0x22, *range(0x30, 0x38), 0x3D, 0x3E, 0x3F, 0x4B})
TRANSITION = DOOR | STAIRS


def classify(attr: int) -> str:
    """floor | hazard | door | stairs | solid for one underworld collision byte."""
    if attr in FLOOR:
        return "floor"
    if attr in HAZARD:
        return "hazard"
    if attr in DOOR:
        return "door"
    if attr in STAIRS:
        return "stairs"
    return "solid"


class NoPathError(RuntimeError):
    """No in-room path for Link between two points."""


class NeedsRoomChangeError(NoPathError):
    """A path exists only through a door, stairs or warp tile (out of scope)."""


def colmap_address(layer: int) -> int:
    return COLMAP_B if layer else COLMAP_A


def cell_index(lx: int, ly: int) -> int:
    """Collision byte offset for a room-local pixel (TileDetection_Execute_underworld)."""
    return ((ly & 0x1F8) << 3) + ((lx >> 3) & 0x3F)


def node_to_link(col: int, row: int) -> tuple[int, int]:
    return col * CELL, row * CELL - CELL


def link_cells(lx: int, ly: int) -> list[tuple[int, int]]:
    """Cells under Link's 16x16 body at room-local (lx, ly)."""
    c0, c1 = lx // CELL, (lx + 15) // CELL
    r0, r1 = (ly + 8) // CELL, (ly + 23) // CELL
    return [(c, r) for r in range(r0, r1 + 1) for c in range(c0, c1 + 1)]


def feet_cell(lx: int, ly: int) -> tuple[int, int]:
    return (lx + 8) // CELL, (ly + 20) // CELL


@dataclass
class Grid:
    """One layer of the room collision map (4096 bytes, row-major 64x64)."""
    attrs: bytes
    allow_doors: bool = False
    allow_hazard_edge: bool = False
    blocked: set = field(default_factory=set)

    def __post_init__(self):
        if len(self.attrs) != GRID * GRID:
            raise ValueError(f"collision layer must be {GRID * GRID} bytes, got {len(self.attrs)}")
        self.attrs = bytes(self.attrs)
        self.blocked = {tuple(cell) for cell in self.blocked}

    @classmethod
    def from_rows(cls, rows, legend=None, **kwargs):
        """Build from text rows (tests). Unlisted cells are floor ($00)."""
        legend = legend or {".": 0x00, "#": 0x01, "o": 0x20, "~": 0x08, "D": 0x80, "S": 0x1D, "i": 0x0E}
        data = bytearray(GRID * GRID)
        for r, line in enumerate(rows):
            for c, ch in enumerate(line):
                data[r * GRID + c] = legend[ch]
        return cls(bytes(data), **kwargs)

    def attr(self, col: int, row: int) -> int:
        return self.attrs[row * GRID + col]

    def kind(self, col: int, row: int) -> str:
        if not (0 <= col < GRID and 0 <= row < GRID) or (col, row) in self.blocked:
            return "solid"
        kind = classify(self.attr(col, row))
        if kind == "door" and self.allow_doors:
            return "floor"
        return kind

    def cost(self, col: int, row: int) -> int:
        return _SLOW.get(self.attr(col, row), 1)

    def link_fits(self, lx: int, ly: int, transitions: bool = False) -> bool:
        """True when Link at room-local (lx, ly) touches no solid tile and stands safely."""
        if lx < 0 or ly < -8 or lx + 15 >= GRID * CELL or ly + 23 >= GRID * CELL:
            return False
        ok = {"floor"} | ({"door", "stairs"} if transitions else set())
        if self.allow_hazard_edge:
            ok = ok | {"hazard"}
        if any(self.kind(c, r) not in ok for c, r in link_cells(lx, ly)):
            return False
        feet = self.kind(*feet_cell(lx, ly))
        return feet != "hazard" and feet in ok

    def node_fits(self, col: int, row: int, transitions: bool = False) -> bool:
        return self.link_fits(*node_to_link(col, row), transitions=transitions)

    def snap(self, lx: int, ly: int, transitions: bool = False):
        """Nearest free node to a Link position, or None."""
        cols = {lx // CELL, -(-lx // CELL)}
        rows = {(ly + 8) // CELL, -(-(ly + 8) // CELL)}
        best = None
        for c in cols:
            for r in rows:
                if self.node_fits(c, r, transitions):
                    nx, ny = node_to_link(c, r)
                    d = abs(nx - lx) + abs(ny - ly)
                    if best is None or d < best[0]:
                        best = (d, (c, r))
        return best and best[1]


_STEPS = ((1, 0), (-1, 0), (0, 1), (0, -1))


def _astar(grid: Grid, start, goal, transitions: bool, turn_cost: int):
    def h(node):
        return abs(node[0] - goal[0]) + abs(node[1] - goal[1])

    frontier = [(h(start), 0, start, -1)]
    best = {(start, -1): 0}
    parent = {(start, -1): None}
    while frontier:
        _, g, node, d = heapq.heappop(frontier)
        if node == goal:
            path, key = [], (node, d)
            while key is not None:
                path.append(key[0])
                key = parent[key]
            return path[::-1]
        if g > best.get((node, d), 1 << 30):
            continue
        for nd, (dc, dr) in enumerate(_STEPS):
            nxt = (node[0] + dc, node[1] + dr)
            if not grid.node_fits(*nxt, transitions=transitions):
                continue
            step = max(grid.cost(c, r) for c, r in link_cells(*node_to_link(*nxt)))
            ng = g + step + (turn_cost if d not in (-1, nd) else 0)
            if ng < best.get((nxt, nd), 1 << 30):
                best[(nxt, nd)] = ng
                parent[(nxt, nd)] = (node, d)
                heapq.heappush(frontier, (ng + h(nxt), ng, nxt, nd))
    return None


def _corners(nodes):
    """Keep the end of each straight run."""
    out = []
    for i, node in enumerate(nodes[1:], 1):
        last = i == len(nodes) - 1
        if last or (nodes[i - 1][0] == node[0]) != (node[0] == nodes[i + 1][0]):
            out.append(node)
    return out


def find_path(grid: Grid, start: tuple[int, int], goal: tuple[int, int], turn_cost: int = 4):
    """Waypoints [(lx, ly), ...] from Link's room-local position to `goal`.

    The first waypoint aligns Link to the start node; the last is `goal` itself
    when Link fits there, otherwise the nearest free node. Raises NoPathError or
    NeedsRoomChangeError.
    """
    s = grid.snap(*start)
    if s is None:
        raise NoPathError(f"Link at {start} does not fit any free node (body cells "
                          f"{link_cells(*start)}); collision map or layer mismatch?")
    g = grid.snap(*goal)
    if g is None:
        detail = {cell: f"{grid.attr(*cell):02X}" for cell in link_cells(*goal)
                  if 0 <= cell[0] < GRID and 0 <= cell[1] < GRID}
        raise NoPathError(f"target {goal} is blocked for Link's body: {detail}")
    nodes = _astar(grid, s, g, transitions=False, turn_cost=turn_cost)
    if nodes is None:
        via = _astar(grid, s, g, transitions=True, turn_cost=turn_cost)
        if via is not None:
            hits = [(c, r, f"{grid.attr(c, r):02X}") for node in via
                    for c, r in link_cells(*node_to_link(*node))
                    if grid.kind(c, r) in ("door", "stairs")]
            raise NeedsRoomChangeError(
                f"path from {start} to {goal} needs a door/stairs/warp tile (room change is out of "
                f"scope); first transition cell (col,row,attr) = {hits[0]}")
        raise NoPathError(f"no in-room path from {start} to {goal}")
    points = [node_to_link(*s)] + [node_to_link(*n) for n in _corners(nodes)] if len(nodes) > 1 \
        else [node_to_link(*s)]
    end = points[-1]
    if tuple(goal) != end and grid.link_fits(goal[0], end[1]) and grid.link_fits(*goal):
        points.append(tuple(goal))
    deduped = [points[0]]
    for p in points[1:]:
        if p != deduped[-1]:
            deduped.append(p)
    return deduped


def render(grid: Grid, waypoints=(), rows=None, cols=None) -> str:
    """ASCII map for errors and reports: # solid, o hazard, D door, S stairs, * path."""
    marks = {}
    for (x0, y0), (x1, y1) in zip(waypoints, waypoints[1:]):
        for x in range(min(x0, x1), max(x0, x1) + 1):
            for y in range(min(y0, y1), max(y0, y1) + 1):
                marks[feet_cell(x, y)] = "*"
    glyph = {"floor": ".", "solid": "#", "hazard": "o", "door": "D", "stairs": "S"}
    rows = rows or range(GRID)
    cols = cols or range(GRID)
    return "\n".join("".join(marks.get((c, r), glyph[grid.kind(c, r)]) for c in cols) for r in rows)
