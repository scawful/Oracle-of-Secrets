"""Underworld collision map and a 4 px route finder for Link's body.

Extracted from Scripts/Validate/scenarios/keyblock_unlock.py (same route rules
as discord_quick_fixes.py).
"""
from __future__ import annotations

import collections


def room_origin(room: int) -> tuple[int, int]:
    """Absolute pixel origin of a dungeon room (16 rooms per row, 512 px each)."""
    return (room & 0x0F) * 0x200, (room >> 4) * 0x200


def rect(tx0: int, ty0: int, tx1: int, ty1: int) -> list[tuple[int, int]]:
    """Tile cells (tx, ty) of an inclusive rectangle, row by row."""
    return [(tx, ty) for ty in range(ty0, ty1 + 1) for tx in range(tx0, tx1 + 1)]


class DungeonTiles:
    """Underworld collision for the current room: $7F2000 (layer 1) or $7F3000 (layer 2,
    when $EE is set), 64x64 tiles of 8 px."""
    WALK = tuple([0x00, 0x09, 0x1D, 0x22, 0x3D, 0x3E, 0x3F, 0x48, 0x4B] +
                 list(range(0x80, 0x90)) + list(range(0xA0, 0xB0)))

    def __init__(self, buf: bytes):
        self.buf = buf

    @classmethod
    def read(cls, session) -> 'DungeonTiles':
        return cls(session.b.read_block(0x7F3000 if session.r(0x7E00EE) else 0x7F2000, 0x1000))

    def attr(self, px: int, py: int) -> int:
        return self.buf[((py & 0x1FF) >> 3) * 64 + ((px & 0x1FF) >> 3)]

    def route(self, start, goal, bounds, nearest=False):
        """4 px BFS for Link's body (x+1..14, y+9..22) on walkable tiles; simplified waypoints."""
        x0, y0, x1, y1 = bounds

        def ok(x, y):
            return all(self.attr(x + dx, y + dy) in self.WALK for dx in (1, 14) for dy in (9, 22))
        start = (start[0] // 4 * 4, start[1] // 4 * 4)
        goal = (goal[0] // 4 * 4, goal[1] // 4 * 4)
        prev, queue, best = {start: None}, collections.deque([start]), start

        def path_to(c):
            path = []
            while c:
                path.append(c)
                c = prev[c]
            path.reverse()
            return [p for i, p in enumerate(path) if i in (0, len(path) - 1) or
                    not (path[i - 1][0] == p[0] == path[i + 1][0] or path[i - 1][1] == p[1] == path[i + 1][1])]
        while queue:
            c = queue.popleft()
            if abs(c[0] - goal[0]) + abs(c[1] - goal[1]) < abs(best[0] - goal[0]) + abs(best[1] - goal[1]):
                best = c
            if c == goal:
                return path_to(c)
            for dx, dy in ((4, 0), (-4, 0), (0, 4), (0, -4)):
                n = (c[0] + dx, c[1] + dy)
                if n not in prev and x0 <= n[0] <= x1 and y0 <= n[1] <= y1 and ok(*n):
                    prev[n] = c
                    queue.append(n)
        return path_to(best) if nearest and best != start else None
