#!/usr/bin/env python3
"""Read-only 192-map rev5 OOSOW192 overworld seam, landing & arrival auditor.

Reuses Scripts/Build/check_tile16_pins.py, Scripts/Build/lyra_native_loaders.py,
and Scripts/Tools/scene_intent_common.py for all ROM, Map32, Tile16, Record 413
page_tile16, and OverworldTileTypes decoding.

Checks:
  1. Horizontal & Vertical Seam Continuity across adjacent overworld maps
     (ignoring internal seams within the same Large/Wide/Tall parent area and
     respecting Overworld/lyra_edge_guard.asm on Special Overworld $80-$BF,
     while auditing bidirectional LW Col 7 <-> SW Col 0 cross-world seams):
       - walkable_into_solid : walkable land abutting solid cliff/wall/pit
       - open_sea_cutoff     : deep water abutting dry walkable land
       - unclosed_cliff_edge : deep/shallow water abutting solid cliff across seam
  2. Entrance / Exit Arrival Clearance:
       - All active OW Exits ($00-$4E) land on non-solid, non-deep-water terrain
       - All active OW Entrances (129 triggers) are in-bounds and have at least
         one passable entry/approach tile (not trapped in solid wall/deep water)
       - Optional ASM cached landings (Boat_Caches, SpecialSoaring_Caches)

Usage:
  python3 Scripts/Build/check_overworld_seams.py --rom <rom.sfc>
  python3 Scripts/Build/check_overworld_seams.py --rom <rom.sfc> --region zora-coast
  python3 Scripts/Build/check_overworld_seams.py --rom <rom.sfc> --out-json /tmp/seams.json --out-md /tmp/seams.md
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _rel in ("Scripts/Build", "Scripts/Tools"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_tile16_pins as ctp  # noqa: E402
import lyra_native_loaders as lnl  # noqa: E402
import scene_intent_common as sic  # noqa: E402

# ---------------------------------------------------------------------------
# Region Presets (shared with Scripts/Tools/overworld_region_board.py)
# ---------------------------------------------------------------------------
REGION_GRIDS: dict[str, list[list[int]]] = {
    # 4x3 grid: LW cross-world column ($17/$1F/$27) + Sea Zora / Zora Coast ($90-$A2)
    "zora-coast": [
        [0x17, 0x90, 0x91, 0x92],
        [0x1F, 0x98, 0x99, 0x9A],
        [0x27, 0xA0, 0xA1, 0xA2],
    ],
    # 4x3 grid: LW cross-world column + Deku north + Goron Desert ($B0/$B1/$B8/$B9) + Sea east
    "goron-coast": [
        [0x2F, 0xA8, 0xA9, 0xAA],
        [0x37, 0xB0, 0xB1, 0xB2],
        [0x3F, 0xB8, 0xB9, 0xBA],
    ],
    # 5x4 grid: Full Lyra Sea & Courage Island without splitting Large area $B3 ($B3/$B4/$BB/$BC)
    "courage-lyra": [
        [0xA3, 0xA4, 0xA5, 0xA6, 0xA7],
        [0xAB, 0xAC, 0xAD, 0xAE, 0xAF],
        [0xB3, 0xB4, 0xB5, 0xB6, 0xB7],
        [0xBB, 0xBC, 0xBD, 0xBE, 0xBF],
    ],
    # 5x2 grid: Unbroken Tail Pond ($2D) -> Tail Swamp ($2E) -> Tail Palace ($2F) <-> Deku Grove ($A8/$A9)
    # with south approach context ($35/$36/$37 <-> $B0/$B1)
    "deku-swamp": [
        [0x2D, 0x2E, 0x2F, 0xA8, 0xA9],
        [0x35, 0x36, 0x37, 0xB0, 0xB1],
    ],
}

REGION_CORE_MAPS: dict[str, set[int]] = {
    "zora-coast": {0x90, 0x91, 0x92, 0x98, 0x99, 0x9A, 0xA0, 0xA1, 0xA2},
    "goron-coast": {0xB0, 0xB1, 0xB8, 0xB9},
    "courage-lyra": {m for row in REGION_GRIDS["courage-lyra"] for m in row},
    "deku-swamp": {0x2D, 0x2E, 0x2F, 0xA8, 0xA9},
}

REGION_TITLES: dict[str, str] = {
    "zora-coast": "Zora Coast & Sea Zora Temple ($90-$92 / $98-$9A / $A0-$A2 + LW $17/$1F/$27)",
    "goron-coast": "Goron Coast & Shrine of Power ($B0/$B1/$B8/$B9 + $A8-$AA / $B2/$BA / LW $2F-$3F)",
    "courage-lyra": "Courage Island & Lyra Sea ($A3-$A7 / $AB-$AF / $B3-$B7 / $BB-$BF)",
    "deku-swamp": "Tail Pond -> Tail Swamp -> Tail Palace -> Deku Grove ($2D-$2F <-> $A8/$A9)",
}

# Bidirectional cross-world mosaic crossings (Overworld/special_overworld_transitions.asm)
CROSS_WORLD_SEAMS: tuple[tuple[int, int], ...] = (
    (0x1F, 0x98),
    (0x27, 0xA0),
    (0x2F, 0xA8),
    (0x37, 0xB0),
    (0x3F, 0xB8),
)

# ---------------------------------------------------------------------------
# OverworldTileTypes classification (grounded in Bank $0E + tile_type_classes.json)
# ---------------------------------------------------------------------------
DEEP_WATER_TT = frozenset({0x08, 0x4B, 0x80})
SHALLOW_WATER_TT = frozenset({0x09})
LEDGE_TT = frozenset({0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F})
INTERACTIVE_TT = frozenset({0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57})
WALKABLE_TT = frozenset({
    0x00, 0x05, 0x06, 0x07, 0x0E, 0x0F,
    0x14, 0x15, 0x16, 0x17,
    0x21, 0x22, 0x23, 0x24, 0x25, 0x26,
    *range(0x30, 0x40),
    0x40, 0x46, 0x48, 0x4A, 0x4F,
    0x64, 0x65,
})
PIT_TT = frozenset({0x20})

# LyraEdgeGuard bitmasks (Overworld/lyra_edge_guard.asm)
EG_NONE = 0x00
EG_R = 0x01
EG_L = 0x02
EG_D = 0x04
EG_U = 0x08
EG_ALL = 0x0F

# Fallback permissions matching Overworld/lyra_edge_guard.asm if source file is unavailable
DEFAULT_LYRA_EDGE_PERMS: tuple[int, ...] = (
    # Row 0 ($80-$87)
    0x00, EG_R | EG_D, EG_R | EG_L | EG_D, EG_L | EG_D, 0x00, 0x00, 0x00, EG_D,
    # Row 1 ($88-$8F)
    0x00, EG_R | EG_U, EG_ALL, EG_L | EG_U, EG_R, EG_R | EG_L, EG_R | EG_L, EG_L | EG_U,
    # Row 2 ($90-$97)
    EG_D, EG_D, EG_U, 0x00, 0x00, 0x00, 0x00, 0x00,
    # Row 3 ($98-$9F)
    EG_ALL, EG_ALL, EG_L | EG_D, 0x00, 0x00, 0x00, 0x00, 0x00,
    # Row 4 ($A0-$A7)
    EG_R | EG_L | EG_U, EG_R | EG_L | EG_U, EG_ALL, EG_R | EG_L | EG_D,
    EG_R | EG_L | EG_D, EG_R | EG_L | EG_D, EG_R | EG_L | EG_D, EG_L | EG_D,
    # Row 5 ($A8-$AF)
    EG_R | EG_L | EG_D, EG_L | EG_D, EG_R | EG_D | EG_U, EG_ALL,
    EG_ALL, EG_ALL, EG_ALL, EG_L | EG_D | EG_U,
    # Row 6 ($B0-$B7)
    EG_ALL, EG_ALL, EG_ALL, EG_ALL, EG_ALL, EG_ALL, EG_ALL, EG_L | EG_D | EG_U,
    # Row 7 ($B8-$BF)
    EG_R | EG_L | EG_U, EG_R | EG_L | EG_U, EG_R | EG_L | EG_U, EG_R | EG_L | EG_U,
    EG_R | EG_L | EG_U, EG_R | EG_L | EG_U, EG_R | EG_L | EG_U, EG_L | EG_U,
)


def classify_tiletype(tt: int) -> str:
    """Classify one OverworldTileTypes byte into a semantic terrain category."""
    if tt in DEEP_WATER_TT:
        return "deep_water"
    if tt in SHALLOW_WATER_TT:
        return "shallow_water"
    if tt in WALKABLE_TT:
        return "walkable"
    if tt in LEDGE_TT:
        return "ledge"
    if tt in INTERACTIVE_TT:
        return "interactive"
    return "solid"


def load_lyra_edge_permissions(root: Path = ROOT) -> tuple[int, ...]:
    """Parse Special Overworld ($80-$BF) edge transition masks from Overworld/lyra_edge_guard.asm."""
    asm_path = root / "Overworld" / "lyra_edge_guard.asm"
    if not asm_path.is_file():
        return DEFAULT_LYRA_EDGE_PERMS
    symbols = {
        "!EG_NONE": EG_NONE,
        "!EG_R": EG_R,
        "!EG_L": EG_L,
        "!EG_D": EG_D,
        "!EG_U": EG_U,
        "!EG_ALL": EG_ALL,
    }
    in_perms = False
    perms: list[int] = []
    for raw in asm_path.read_text(encoding="utf-8", errors="replace").splitlines():
        code = raw.split(";", 1)[0].strip()
        if not code:
            continue
        if code.startswith(".Permissions"):
            in_perms = True
            continue
        if not in_perms:
            continue
        if code.startswith("}") or code.startswith("print"):
            break
        if code.lower().startswith("db "):
            for tok in code[3:].split(","):
                expr = tok.strip()
                if not expr:
                    continue
                val = 0
                for part in expr.split("|"):
                    part = part.strip()
                    if part in symbols:
                        val |= symbols[part]
                    elif part.startswith("$"):
                        val |= int(part[1:], 16)
                    else:
                        val |= int(part, 0)
                perms.append(val)
    return tuple(perms) if len(perms) == 64 else DEFAULT_LYRA_EDGE_PERMS


def load_page_tile16_overrides(rom: bytes, capacity: int) -> dict[tuple[int, int], tuple[int, int, int, int]]:
    """Decode rev5 Record 413 page-qualified Tile16 overrides if present."""
    try:
        info = lnl.read_native_directory(rom, experimental_page_tile16=True)
        if info is None:
            return {}
        _cap, _bank, entries = info
        if 413 not in entries:
            return {}
        addr, rows = entries[413]
        start = ctp.snes_to_pc(addr)
        raw = rom[start:start + rows * 12]
        return lnl.decode_page_tile16(raw, capacity)
    except Exception:
        return {}


def resolve_native_tables(rom: bytes) -> tuple[int, dict[str, int]]:
    """Return (map_capacity, {table_name: pc_addr}) for both base and compiled rev3/4/5 ROMs."""
    try:
        info = lnl.read_native_directory(rom, experimental_page_tile16=True)
        if info is not None:
            capacity, bank, entries = info
            tables: dict[str, int] = {"_tail_actor_bank": bank}
            for family in lnl.current_table_layout(lnl.TABLE_BASE):
                if family.id in entries:
                    tables[family.name] = ctp.snes_to_pc(entries[family.id][0])
            return capacity, tables
    except Exception:
        pass
    return ctp._native_table_addresses(rom)


class OverworldContext:
    """Cached read-only 192-map rev5 OOSOW192 decoder for seam & board tools."""

    def __init__(self, rom: bytes, root: Path = ROOT) -> None:
        self.rom = rom
        self.root = root
        self.capacity, self.native_tables = resolve_native_tables(rom)
        self.tail_bank = self.native_tables.get("_tail_actor_bank", 0x4C)
        self.map32_table = ctp.decode_map32_table(rom)
        self.tile16_table = sic.decode_tile16_table(rom)
        self.ow_tt = list(rom[sic.PC_TILETYPE:sic.PC_TILETYPE + 0x200])
        self.page_tile16 = load_page_tile16_overrides(rom, self.capacity)
        self.edge_perms = load_lyra_edge_permissions(root)
        self.overlay_maps: set[int] = set()
        for _tid, users in ctp.extract_overlay_stream_refs(rom).items():
            for u in users:
                if u.startswith("ov"):
                    self.overlay_maps.add(int(u[2:], 16))
        self._grid_cache: dict[int, list[list[int]]] = {}
        self._parent_cache: dict[int, tuple[int, int]] = {}
        self._area_grid_cache: dict[int, list[list[int]]] = {}

    def parent_and_size(self, area_id: int) -> tuple[int, int]:
        """Return (parent_id, size_code: 0=Small, 1=Large, 2=Wide, 3=Tall)."""
        cached = self._parent_cache.get(area_id)
        if cached is not None:
            return cached
        if area_id < 0xA0:
            parent = sic.area_parent_id(self.rom, area_id)
            if sic.zs_version(self.rom) >= 3 and 0x1788D + parent < len(self.rom):
                sz = self.rom[0x1788D + parent]
            elif parent < 0x80 and 0x12844 + (parent & 0x3F) < len(self.rom):
                sz = 1 if self.rom[0x12844 + (parent & 0x3F)] != 0 else 0
            else:
                sz = 0
        elif "parent" in self.native_tables and "area_size" in self.native_tables:
            parent = self.rom[self.native_tables["parent"] + area_id]
            sz = self.rom[self.native_tables["area_size"] + parent]
        else:
            parent, sz = area_id, 0
        self._parent_cache[area_id] = (parent, sz)
        return parent, sz

    def screen_grid(self, map_id: int) -> list[list[int]]:
        """Return 32x32 Tile16 grid for a single physical map $00-$BF."""
        g = self._grid_cache.get(map_id)
        if g is None:
            g = ctp.decode_map16_grid(self.rom, map_id, self.map32_table, self.native_tables)
            self._grid_cache[map_id] = g
        return g

    def area_grid(self, map_id: int) -> tuple[int, int, list[list[int]]]:
        """Return (parent, size_code, full_area_grid) for parent area of map_id."""
        parent, sz = self.parent_and_size(map_id)
        g = self._area_grid_cache.get(parent)
        if g is not None:
            return parent, sz, g
        nw = self.screen_grid(parent)
        if sz == 1:
            ne = self.screen_grid(parent + 1)
            sw = self.screen_grid(parent + 8)
            se = self.screen_grid(parent + 9)
            g = [nw[r] + ne[r] for r in range(32)] + [sw[r] + se[r] for r in range(32)]
        elif sz == 2:
            ne = self.screen_grid(parent + 1)
            g = [nw[r] + ne[r] for r in range(32)]
        elif sz == 3:
            sw = self.screen_grid(parent + 8)
            g = nw + sw
        else:
            g = nw
        self._area_grid_cache[parent] = g
        return parent, sz, g

    def tile16_words(self, map_id: int, tid: int) -> tuple[int, int, int, int]:
        """Resolve (tl, tr, bl, br) Tile8 words honoring rev5 Record 413 page overrides."""
        override = self.page_tile16.get((map_id, tid))
        if override is not None:
            return override
        if 0 <= tid < len(self.tile16_table):
            return self.tile16_table[tid]
        return (0, 0, 0, 0)

    def tile16_quadrant_types(self, map_id: int, tid: int) -> tuple[int, int, int, int]:
        """Return raw OverworldTileTypes (tl, tr, bl, br) for a Tile16 on physical map_id."""
        w0, w1, w2, w3 = self.tile16_words(map_id, tid)
        return (
            self.ow_tt[w0 & 0x1FF],
            self.ow_tt[w1 & 0x1FF],
            self.ow_tt[w2 & 0x1FF],
            self.ow_tt[w3 & 0x1FF],
        )

    def tile16_quadrant_classes(self, map_id: int, tid: int) -> tuple[str, str, str, str]:
        """Return terrain classes (tl, tr, bl, br) for a Tile16 on physical map_id."""
        t0, t1, t2, t3 = self.tile16_quadrant_types(map_id, tid)
        return (
            classify_tiletype(t0),
            classify_tiletype(t1),
            classify_tiletype(t2),
            classify_tiletype(t3),
        )

    def tile16_summary_class(self, map_id: int, tid: int) -> str:
        """Dominant terrain class of a Tile16 for map visualization and arrival checks."""
        classes = self.tile16_quadrant_classes(map_id, tid)
        if all(c == "deep_water" for c in classes):
            return "deep_water"
        if any(c == "deep_water" for c in classes) and not any(c == "walkable" for c in classes):
            return "deep_water"
        if all(c in ("shallow_water", "deep_water") for c in classes):
            return "shallow_water"
        if any(c == "shallow_water" for c in classes) and not any(c == "solid" for c in classes):
            return "shallow_water"
        if all(c == "walkable" for c in classes):
            return "walkable"
        if any(c == "solid" for c in classes):
            # Mixed solid+walkable: solid if >=2 solid quadrants else ledge/walkable border
            if sum(1 for c in classes if c == "solid") >= 2:
                return "solid"
            if any(c == "walkable" for c in classes):
                return "walkable"
            return "solid"
        if any(c == "ledge" for c in classes):
            return "ledge"
        if any(c == "interactive" for c in classes):
            return "interactive"
        return "walkable"

    def special_seam_permitted(self, map_a: int, map_b: int, axis: str) -> bool:
        """Return True if LyraEdgeGuard permits crossing between map_a and map_b."""
        if not (0x80 <= map_a < 0xC0 and 0x80 <= map_b < 0xC0):
            return True
        pa = self.edge_perms[map_a - 0x80]
        pb = self.edge_perms[map_b - 0x80]
        if axis == "H":
            return bool((pa & EG_R) or (pb & EG_L))
        return bool((pa & EG_D) or (pb & EG_U))

    def read_sprites(self, map_id: int, phase: int = 1) -> list[tuple[int, int, int]]:
        """Return [(x_tile, y_tile, sprite_id)] placed on physical map_id for given phase."""
        out: list[tuple[int, int, int]] = []
        if map_id < 0xA0:
            ptrs = (0x141438, 0x141578, 0x1416B8)
            ptr = ctp.read_u16(self.rom, ptrs[phase] + map_id * 2)
            p = ctp.snes_to_pc(0x090000 | ptr)
        else:
            nt_key = ("sprite_phase0", "sprite_phase1", "sprite_phase2")[phase]
            if nt_key not in self.native_tables:
                return out
            ptr = ctp.read_u16(self.rom, self.native_tables[nt_key] + map_id * 2)
            p = ctp.snes_to_pc((self.tail_bank << 16) | ptr) if ptr >= 0x8000 else -1
        if p < 0:
            return out
        while p + 2 < len(self.rom) and self.rom[p] != 0xFF and len(out) < 64:
            sy = self.rom[p] & 0x3F
            sx = self.rom[p + 1] & 0x3F
            sid = self.rom[p + 2]
            out.append((sx, sy, sid))
            p += 3
        return out

    def read_exits(self) -> list[dict[str, Any]]:
        """Read all active Overworld Exit records ($00-$4E)."""
        exits: list[dict[str, Any]] = []
        for i in range(0x4F):
            room = ctp.read_u16(self.rom, 0x15D8A + i * 2)
            mp = self.rom[0x15E28 + i]
            yp = ctp.read_u16(self.rom, 0x16051 + i * 2)
            xp = ctp.read_u16(self.rom, 0x160EF + i * 2)
            if xp == 0xFFFF and yp == 0xFFFF:
                continue
            if mp >= self.capacity:
                continue
            dt1 = ctp.read_u16(self.rom, 0x16367 + i * 2)
            dt2 = ctp.read_u16(self.rom, 0x16405 + i * 2)
            parent, sz = self.parent_and_size(mp)
            local_m = parent & 0x3F
            origin_x = (local_m % 8) * 512
            origin_y = (local_m // 8) * 512
            exits.append({
                "exit_id": i,
                "room_id": room,
                "map_id": mp,
                "parent_id": parent,
                "size": sz,
                "door_type_1": dt1,
                "door_type_2": dt2,
                "world_x": xp,
                "world_y": yp,
                "local_px_x": xp - origin_x,
                "local_px_y": yp - origin_y,
                # Link's feet sit around (+8, +16) from top-left pixel origin
                "foot_tile_x": (xp - origin_x + 8) // 16,
                "foot_tile_y": (yp - origin_y + 16) // 16,
            })
        return exits

    def read_entrances(self) -> list[dict[str, Any]]:
        """Read all active Overworld Entrance trigger records (0..128)."""
        entrances: list[dict[str, Any]] = []
        for i in range(129):
            scr = ctp.read_u16(self.rom, 0x0DB96F + i * 2)
            tile = ctp.read_u16(self.rom, 0x0DBA71 + i * 2)
            eid = self.rom[0x0DBB73 + i]
            if scr == 0xFFFF or tile == 0xFFFF or eid >= 133:
                continue
            if scr >= self.capacity:
                continue
            parent, sz = self.parent_and_size(scr)
            idx = (tile & 0x7FFF) // 2
            cx = idx % 64
            cy = idx // 64
            room = ctp.read_u16(self.rom, 0x14813 + eid * 2)
            entrances.append({
                "ow_ent_index": i,
                "entrance_id": eid,
                "room_id": room,
                "map_id": scr,
                "parent_id": parent,
                "size": sz,
                "tile_cell": tile,
                "local_tile_x": cx,
                "local_tile_y": cy,
            })
        return entrances


# ---------------------------------------------------------------------------
# Seam & Arrival Auditors
# ---------------------------------------------------------------------------

def _classify_edge_pair(c_a: str, c_b: str) -> tuple[str, str] | None:
    """Return (kind, severity) if touching 8x8 terrain classes mismatch, else None."""
    if c_a == c_b:
        return None
    pair = {c_a, c_b}
    if pair == {"walkable", "solid"}:
        return ("walkable_into_solid", "error")
    if pair == {"deep_water", "walkable"}:
        return ("open_sea_cutoff", "error")
    if pair == {"deep_water", "solid"}:
        return ("unclosed_cliff_band", "warn")
    if pair == {"shallow_water", "solid"}:
        return ("shallow_water_into_solid", "warn")
    if pair == {"ledge", "deep_water"}:
        return ("ledge_into_deep_water", "warn")
    # Valid transitions:
    #   walkable <-> shallow_water (beach/shore wading)
    #   shallow_water <-> deep_water (natural reef dropoff)
    #   walkable <-> ledge (jumpable cliff edge)
    #   walkable <-> interactive (bush/rock/sign on walkable ground)
    #   solid <-> ledge (cliff band continuity)
    #   solid <-> interactive (bush/rock next to tree/cliff)
    return None


def _group_mismatch_spans(
    hits: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Collapse adjacent Tile16 mismatch hits of the same kind into readable spans."""
    if not hits:
        return []
    grouped: list[dict[str, Any]] = []
    # Deduplicate by (index, kind) keeping highest severity
    by_idx: dict[tuple[int, str], dict[str, Any]] = {}
    for h in hits:
        key = (h["tile_index"], h["kind"])
        if key not in by_idx:
            by_idx[key] = h
    ordered = sorted(by_idx.values(), key=lambda x: (x["kind"], x["tile_index"]))
    for h in ordered:
        if (
            grouped
            and grouped[-1]["kind"] == h["kind"]
            and h["tile_index"] == grouped[-1]["end_tile"] + 1
        ):
            grouped[-1]["end_tile"] = h["tile_index"]
            grouped[-1]["tile_count"] += 1
            grouped[-1]["tiles"].append(h["tile_index"])
        else:
            grouped.append({
                "kind": h["kind"],
                "severity": h["severity"],
                "start_tile": h["tile_index"],
                "end_tile": h["tile_index"],
                "tile_count": 1,
                "tiles": [h["tile_index"]],
                "sample_a": h["sample_a"],
                "sample_b": h["sample_b"],
            })
    return grouped


def enumerate_active_seams(ctx: OverworldContext) -> tuple[list[tuple[int, int, str, bool]], int]:
    """Return ([(map_a, map_b, axis, is_cross_world)], skipped_edge_guard_count)."""
    seams: list[tuple[int, int, str, bool]] = []
    skipped_eg = 0

    worlds = [(0x00, min(0x40, ctx.capacity)), (0x40, min(0x80, ctx.capacity))]
    if ctx.capacity > 0x80:
        worlds.append((0x80, min(0xC0, ctx.capacity)))

    for w_start, w_end in worlds:
        is_special = w_start == 0x80
        for m in range(w_start, w_end):
            local = m - w_start
            col = local % 8
            row = local // 8
            parent_m, _ = ctx.parent_and_size(m)

            # Horizontal seam with East neighbor
            if col < 7 and m + 1 < w_end:
                nb = m + 1
                parent_nb, _ = ctx.parent_and_size(nb)
                if parent_m != parent_nb:
                    if is_special and not ctx.special_seam_permitted(m, nb, "H"):
                        skipped_eg += 1
                    else:
                        seams.append((m, nb, "H", False))

            # Vertical seam with South neighbor
            if row < 7 and m + 8 < w_end:
                nb = m + 8
                parent_nb, _ = ctx.parent_and_size(nb)
                if parent_m != parent_nb:
                    if is_special and not ctx.special_seam_permitted(m, nb, "V"):
                        skipped_eg += 1
                    else:
                        seams.append((m, nb, "V", False))

    # Cross-world LW Col 7 <-> SW Col 0 horizontal crossings
    if ctx.capacity >= 0xC0:
        for lw_m, sw_m in CROSS_WORLD_SEAMS:
            seams.append((lw_m, sw_m, "H", True))

    return seams, skipped_eg


def region_map_filter(region: str, capacity: int) -> set[int]:
    """Resolve CLI --region selector into the set of core map IDs to audit."""
    if region == "all":
        return set(range(capacity))
    if region == "special":
        return set(range(0x80, min(0xC0, capacity)))
    if region == "kalyxo":
        return set(range(0x00, min(0x40, capacity)))
    if region == "abyss":
        return set(range(0x40, min(0x80, capacity)))
    if region in REGION_CORE_MAPS:
        return {m for m in REGION_CORE_MAPS[region] if m < capacity}
    raise ValueError(f"Unknown region {region!r}")


def audit_seam_pair(
    ctx: OverworldContext,
    map_a: int,
    map_b: int,
    axis: str,
    is_cross_world: bool = False,
) -> dict[str, Any]:
    """Compare touching 8x8 subtile edges along one 32-Tile16 border between map_a and map_b."""
    ga = ctx.screen_grid(map_a)
    gb = ctx.screen_grid(map_b)
    raw_hits: list[dict[str, Any]] = []

    for i in range(32):
        if axis == "H":
            tid_a = ga[i][31]
            tid_b = gb[i][0]
            ta = ctx.tile16_quadrant_types(map_a, tid_a)
            tb = ctx.tile16_quadrant_types(map_b, tid_b)
            ca = ctx.tile16_quadrant_classes(map_a, tid_a)
            cb = ctx.tile16_quadrant_classes(map_b, tid_b)
            pairs = (
                ("top", ca[1], cb[0], ta[1], tb[0]),
                ("bot", ca[3], cb[2], ta[3], tb[2]),
            )
        else:
            tid_a = ga[31][i]
            tid_b = gb[0][i]
            ta = ctx.tile16_quadrant_types(map_a, tid_a)
            tb = ctx.tile16_quadrant_types(map_b, tid_b)
            ca = ctx.tile16_quadrant_classes(map_a, tid_a)
            cb = ctx.tile16_quadrant_classes(map_b, tid_b)
            pairs = (
                ("left", ca[2], cb[0], ta[2], tb[0]),
                ("right", ca[3], cb[1], ta[3], tb[1]),
            )

        for half, c_a, c_b, tt_a, tt_b in pairs:
            mm = _classify_edge_pair(c_a, c_b)
            if mm is not None:
                kind, sev = mm
                raw_hits.append({
                    "tile_index": i,
                    "half": half,
                    "kind": kind,
                    "severity": sev,
                    "sample_a": {"tile16": f"0x{tid_a:03X}", "tt": f"0x{tt_a:02X}", "class": c_a},
                    "sample_b": {"tile16": f"0x{tid_b:03X}", "tt": f"0x{tt_b:02X}", "class": c_b},
                })

    spans = _group_mismatch_spans(raw_hits)
    error_tiles = sorted({h["tile_index"] for h in raw_hits if h["severity"] == "error"})
    warn_tiles = sorted({h["tile_index"] for h in raw_hits if h["severity"] == "warn"})
    return {
        "map_a": f"0x{map_a:02X}",
        "map_b": f"0x{map_b:02X}",
        "map_a_int": map_a,
        "map_b_int": map_b,
        "axis": axis,
        "cross_world": is_cross_world,
        "error_tile_count": len(error_tiles),
        "warn_tile_count": len(warn_tiles),
        "error_tiles": error_tiles,
        "warn_tiles": warn_tiles,
        "spans": spans,
    }


def _physical_map_for_area_tile(parent: int, cx: int, cy: int) -> int:
    """Resolve physical screen ID for a local (cx, cy) coordinate inside parent area."""
    dx = 1 if cx >= 32 else 0
    dy = 1 if cy >= 32 else 0
    return parent + dy * 8 + dx


def audit_exits_and_entrances(
    ctx: OverworldContext,
    allowed_maps: set[int],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Verify every OW exit lands on passable terrain and every OW entrance is reachable."""
    exit_findings: list[dict[str, Any]] = []
    entrance_findings: list[dict[str, Any]] = []

    for ex in ctx.read_exits():
        mp = ex["map_id"]
        parent, sz, grid = ctx.area_grid(mp)
        fx, fy = ex["foot_tile_x"], ex["foot_tile_y"]
        phys = _physical_map_for_area_tile(parent, max(0, fx), max(0, fy))
        if mp not in allowed_maps and parent not in allowed_maps and phys not in allowed_maps:
            continue
        h, w = len(grid), len(grid[0])
        if not (0 <= fy < h and 0 <= fx < w):
            exit_findings.append({
                "kind": "exit_landing_oob",
                "severity": "error",
                "exit_id": f"0x{ex['exit_id']:02X}",
                "room_id": f"0x{ex['room_id']:04X}",
                "map_id": f"0x{mp:02X}",
                "parent_id": f"0x{parent:02X}",
                "foot_tile": [fx, fy],
                "area_dims": [w, h],
            })
            continue
        tid = grid[fy][fx]
        t_class = ctx.tile16_summary_class(phys, tid)
        q_classes = ctx.tile16_quadrant_classes(phys, tid)
        # An exit landing is safe if at least one quadrant of the foot tile is
        # walkable/shallow_water, OR Link steps out 1-2 tiles south of a doorway
        # (ALTTP door-exit walkout animation moves Link 24-32px south onto the doormat).
        passable = any(c in ("walkable", "shallow_water") for c in q_classes)
        if not passable:
            # Closed house doors (dt1/dt2) and cave/dungeon mouths step Link south onto fy+1 or fy+2.
            max_step = 2 if (ex.get("door_type_1") or ex.get("door_type_2") or phys in ctx.overlay_maps) else 2
            for dy in range(1, max_step + 1):
                if fy + dy < h:
                    s_phys = _physical_map_for_area_tile(parent, fx, fy + dy)
                    s_q = ctx.tile16_quadrant_classes(s_phys, grid[fy + dy][fx])
                    if sum(1 for c in s_q if c in ("walkable", "shallow_water")) >= 2:
                        passable = True
                        break
            # Dungeon mouths opened by ROM overlay streams (e.g. Tail Palace ov2F) can span 3 tiles tall
            if not passable and (phys in ctx.overlay_maps or parent in ctx.overlay_maps) and fy + 3 < h:
                s_phys = _physical_map_for_area_tile(parent, fx, fy + 3)
                s_q = ctx.tile16_quadrant_classes(s_phys, grid[fy + 3][fx])
                if sum(1 for c in s_q if c in ("walkable", "shallow_water")) >= 2:
                    passable = True
        if not passable:
            exit_findings.append({
                "kind": "exit_landing_blocked",
                "severity": "error",
                "exit_id": f"0x{ex['exit_id']:02X}",
                "room_id": f"0x{ex['room_id']:04X}",
                "map_id": f"0x{mp:02X}",
                "parent_id": f"0x{parent:02X}",
                "foot_tile": [fx, fy],
                "tile16": f"0x{tid:03X}",
                "terrain_class": t_class,
                "quadrant_classes": list(q_classes),
            })

    for ent in ctx.read_entrances():
        scr = ent["map_id"]
        parent, sz, grid = ctx.area_grid(scr)
        cx, cy = ent["local_tile_x"], ent["local_tile_y"]
        phys = _physical_map_for_area_tile(parent, max(0, cx), max(0, cy))
        if scr not in allowed_maps and parent not in allowed_maps and phys not in allowed_maps:
            continue
        h, w = len(grid), len(grid[0])
        if not (0 <= cy < h and 0 <= cx < w):
            entrance_findings.append({
                "kind": "entrance_trigger_oob",
                "severity": "error",
                "ow_ent_index": ent["ow_ent_index"],
                "entrance_id": f"0x{ent['entrance_id']:02X}",
                "room_id": f"0x{ent['room_id']:04X}",
                "map_id": f"0x{scr:02X}",
                "parent_id": f"0x{parent:02X}",
                "tile": [cx, cy],
                "area_dims": [w, h],
            })
            continue
        # Check trigger tile itself and nearby approach tiles (incl. +2/+3 south of overlay-opened dungeon mouths)
        reachable = False
        probe_offsets = [(0, 0), (0, 1), (0, 2), (0, -1), (-1, 0), (1, 0)]
        if phys in ctx.overlay_maps or parent in ctx.overlay_maps:
            probe_offsets.append((0, 3))
        for dx, dy in probe_offsets:
            nx, ny = cx + dx, cy + dy
            if 0 <= ny < h and 0 <= nx < w:
                n_phys = _physical_map_for_area_tile(parent, nx, ny)
                q = ctx.tile16_quadrant_classes(n_phys, grid[ny][nx])
                if any(c in ("walkable", "shallow_water", "interactive") for c in q):
                    reachable = True
                    break
        if not reachable:
            tid = grid[cy][cx]
            entrance_findings.append({
                "kind": "entrance_trapped_in_solid_or_deep_water",
                "severity": "error",
                "ow_ent_index": ent["ow_ent_index"],
                "entrance_id": f"0x{ent['entrance_id']:02X}",
                "room_id": f"0x{ent['room_id']:04X}",
                "map_id": f"0x{scr:02X}",
                "parent_id": f"0x{parent:02X}",
                "tile": [cx, cy],
                "tile16": f"0x{tid:03X}",
                "quadrant_classes": list(ctx.tile16_quadrant_classes(phys, tid)),
            })

    return exit_findings, entrance_findings


def audit_asm_cached_landings(
    ctx: OverworldContext,
    allowed_maps: set[int],
    root: Path = ROOT,
) -> list[dict[str, Any]]:
    """Audit SpecialSoaring_Caches and Boat_Caches landing coordinates against ROM terrain."""
    findings: list[dict[str, Any]] = []
    targets: list[tuple[str, int, int, int]] = []  # (label, area_id, world_x, world_y)

    # Parse BoatNativeCache(area, sy, sx, y, x, ...)
    boat_asm = root / "Data" / "overworld" / "kalyxo_boat_placements.asm"
    if boat_asm.is_file():
        boat_re = re.compile(
            r"%BoatNativeCache\(\$([0-9A-Fa-f]+),\s*\$[0-9A-Fa-f]+,\s*\$[0-9A-Fa-f]+,\s*\$([0-9A-Fa-f]+),\s*\$([0-9A-Fa-f]+)"
        )
        for idx, m in enumerate(boat_re.finditer(boat_asm.read_text(encoding="utf-8", errors="replace"))):
            area = int(m.group(1), 16)
            wy = int(m.group(2), 16)
            wx = int(m.group(3), 16)
            targets.append((f"Boat_Cache[{idx}]", area, wx, wy))

    # Parse SpecialSoaring_Caches dw rows: dw area, $0016, sy, sx, y, x, ...
    soar_asm = root / "Items" / "special_soaring.asm"
    if soar_asm.is_file():
        text = soar_asm.read_text(encoding="utf-8", errors="replace")
        if "SpecialSoaring_Caches:" in text:
            body = text.split("SpecialSoaring_Caches:", 1)[1]
            row_re = re.compile(
                r"dw\s+\$([0-9A-Fa-f]{4}),\s*\$0016,\s*\$[0-9A-Fa-f]{4},\s*\$[0-9A-Fa-f]{4},\s*\$([0-9A-Fa-f]{4}),\s*\$([0-9A-Fa-f]{4})"
            )
            for idx, m in enumerate(row_re.finditer(body)):
                area = int(m.group(1), 16)
                wy = int(m.group(2), 16)
                wx = int(m.group(3), 16)
                targets.append((f"SpecialSoaring_Cache[{idx}]", area, wx, wy))

    for label, area, wx, wy in targets:
        if area >= ctx.capacity:
            continue
        parent, sz, grid = ctx.area_grid(area)
        local_m = parent & 0x3F
        fx = (wx - (local_m % 8) * 512 + 8) // 16
        fy = (wy - (local_m // 8) * 512 + 16) // 16
        phys = _physical_map_for_area_tile(parent, max(0, fx), max(0, fy))
        if area not in allowed_maps and parent not in allowed_maps and phys not in allowed_maps:
            continue
        h, w = len(grid), len(grid[0])
        if not (0 <= fy < h and 0 <= fx < w):
            findings.append({
                "kind": "cached_landing_oob",
                "severity": "error",
                "label": label,
                "map_id": f"0x{area:02X}",
                "foot_tile": [fx, fy],
                "area_dims": [w, h],
            })
            continue
        tid = grid[fy][fx]
        q = ctx.tile16_quadrant_classes(phys, tid)
        if not any(c in ("walkable", "shallow_water") for c in q):
            findings.append({
                "kind": "cached_landing_blocked",
                "severity": "error",
                "label": label,
                "map_id": f"0x{area:02X}",
                "foot_tile": [fx, fy],
                "tile16": f"0x{tid:03X}",
                "quadrant_classes": list(q),
            })
    return findings


def audit_overworld_seams(
    rom: bytes,
    *,
    region: str = "all",
    root: Path = ROOT,
) -> dict[str, Any]:
    """Run full seam continuity & arrival clearance audit on a ROM."""
    ctx = OverworldContext(rom, root=root)
    allowed = region_map_filter(region, ctx.capacity)
    all_seams, skipped_eg = enumerate_active_seams(ctx)

    checked_seams: list[dict[str, Any]] = []
    seam_error_pairs: list[dict[str, Any]] = []
    seam_warn_pairs: list[dict[str, Any]] = []
    total_error_tiles = 0
    total_warn_tiles = 0

    for ma, mb, axis, is_cw in all_seams:
        if ma not in allowed and mb not in allowed:
            continue
        res = audit_seam_pair(ctx, ma, mb, axis, is_cw)
        checked_seams.append(res)
        if res["error_tile_count"] > 0:
            seam_error_pairs.append(res)
            total_error_tiles += res["error_tile_count"]
        elif res["warn_tile_count"] > 0:
            seam_warn_pairs.append(res)
        total_warn_tiles += res["warn_tile_count"]

    exit_findings, entrance_findings = audit_exits_and_entrances(ctx, allowed)
    cached_findings = audit_asm_cached_landings(ctx, allowed, root=root)

    return {
        "region": region,
        "maps_capacity": ctx.capacity,
        "region_map_count": len(allowed),
        "seams_checked": len(checked_seams),
        "skipped_edge_guard_seams": skipped_eg,
        "seam_error_pair_count": len(seam_error_pairs),
        "seam_warn_only_pair_count": len(seam_warn_pairs),
        "total_seam_error_tiles": total_error_tiles,
        "total_seam_warn_tiles": total_warn_tiles,
        "exit_error_count": len(exit_findings),
        "entrance_error_count": len(entrance_findings),
        "cached_landing_error_count": len(cached_findings),
        "seam_errors": seam_error_pairs,
        "seam_warnings": seam_warn_pairs,
        "exit_findings": exit_findings,
        "entrance_findings": entrance_findings,
        "cached_landing_findings": cached_findings,
    }


def format_markdown_report(report: dict[str, Any]) -> str:
    """Format an audit report as concise GitHub-flavored Markdown."""
    lines = [
        f"# Overworld Seam & Arrival Audit (`region={report['region']}`)",
        "",
        f"- **ROM map capacity:** {report['maps_capacity']} maps (`$00-${report['maps_capacity'] - 1:02X}`)",
        f"- **Active seams checked:** {report['seams_checked']} (edge-guard skipped: {report['skipped_edge_guard_seams']})",
        f"- **Seam pairs with errors:** {report['seam_error_pair_count']} ({report['total_seam_error_tiles']} mismatched border tiles)",
        f"- **Seam pairs with warnings only:** {report['seam_warn_only_pair_count']} ({report['total_seam_warn_tiles']} total warning tiles)",
        f"- **Exit landing errors:** {report['exit_error_count']}",
        f"- **Entrance arrival errors:** {report['entrance_error_count']}",
        f"- **Cached landing errors (Boat/Soaring):** {report['cached_landing_error_count']}",
        "",
    ]
    if report["seam_errors"]:
        lines += [
            "## Seam Mismatches (Errors)",
            "",
            "| Seam | Axis | Cross-World | Error Tiles | Spans |",
            "|---|---|---|---:|---|",
        ]
        for s in report["seam_errors"]:
            span_desc = ", ".join(
                f"`{sp['kind']}` @{sp['start_tile']}..{sp['end_tile']}"
                if sp["start_tile"] != sp["end_tile"]
                else f"`{sp['kind']}` @{sp['start_tile']}"
                for sp in s["spans"] if sp["severity"] == "error"
            )
            lines.append(
                f"| `{s['map_a']} <-> {s['map_b']}` | {s['axis']} | "
                f"{'yes' if s['cross_world'] else 'no'} | {s['error_tile_count']} | {span_desc} |"
            )
        lines.append("")
    if report["exit_findings"] or report["entrance_findings"] or report["cached_landing_findings"]:
        lines += ["## Arrival / Landing Findings", ""]
        for item in report["exit_findings"]:
            lines.append(f"- **[EXIT]** `{item['exit_id']}` map `{item['map_id']}` room `{item['room_id']}`: `{item['kind']}` at {item.get('foot_tile')}")
        for item in report["entrance_findings"]:
            lines.append(f"- **[ENT]** `#{item['ow_ent_index']}` (eid `{item['entrance_id']}`) map `{item['map_id']}` room `{item['room_id']}`: `{item['kind']}` at {item.get('tile')}")
        for item in report["cached_landing_findings"]:
            lines.append(f"- **[CACHE]** `{item['label']}` map `{item['map_id']}`: `{item['kind']}` at {item.get('foot_tile')}")
        lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path, help="Path to rev5 OOSOW192 or ZSOW ROM")
    ap.add_argument(
        "--region",
        default="all",
        choices=("all", "special", "kalyxo", "abyss", "zora-coast", "goron-coast", "courage-lyra", "deku-swamp"),
        help="Region filter (default: all)",
    )
    ap.add_argument("--out-json", type=Path, help="Write full structured JSON report to path")
    ap.add_argument("--out-md", type=Path, help="Write Markdown summary report to path")
    ap.add_argument("--strict", action="store_true", help="Exit 1 when any error-severity finding exists")
    args = ap.parse_args(argv)

    rom = sic.load_rom_bytes(args.rom)
    report = audit_overworld_seams(rom, region=args.region)

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(format_markdown_report(report), encoding="utf-8")

    print(
        f"[*] Overworld Seam Audit ({report['region']}, {report['maps_capacity']} maps): "
        f"{report['seams_checked']} seams checked ({report['skipped_edge_guard_seams']} edge-guard skipped) | "
        f"{report['seam_error_pair_count']} error seams ({report['total_seam_error_tiles']} tiles), "
        f"{report['seam_warn_only_pair_count']} warn-only seams | "
        f"exits={report['exit_error_count']} entrances={report['entrance_error_count']} "
        f"cached={report['cached_landing_error_count']}"
    )
    for s in report["seam_errors"][:25]:
        err_spans = [
            f"{sp['kind']}@{sp['start_tile']}..{sp['end_tile']}"
            if sp["start_tile"] != sp["end_tile"]
            else f"{sp['kind']}@{sp['start_tile']}"
            for sp in s["spans"] if sp["severity"] == "error"
        ]
        cw = " [CW]" if s["cross_world"] else ""
        print(f"  [SEAM] {s['map_a']}<->{s['map_b']} ({s['axis']}{cw}): {s['error_tile_count']} tiles — {', '.join(err_spans)}")
    if len(report["seam_errors"]) > 25:
        print(f"  ... {len(report['seam_errors']) - 25} additional error seams")
    for item in report["exit_findings"][:10]:
        print(f"  [EXIT] {item['exit_id']} map={item['map_id']} room={item['room_id']} {item['kind']} @{item.get('foot_tile')}")
    for item in report["entrance_findings"][:10]:
        print(f"  [ENT ] #{item['ow_ent_index']} eid={item['entrance_id']} map={item['map_id']} {item['kind']} @{item.get('tile')}")
    for item in report["cached_landing_findings"]:
        print(f"  [CACH] {item['label']} map={item['map_id']} {item['kind']} @{item.get('foot_tile')}")

    has_errors = (
        report["seam_error_pair_count"] > 0
        or report["exit_error_count"] > 0
        or report["entrance_error_count"] > 0
        or report["cached_landing_error_count"] > 0
    )
    return 1 if (args.strict and has_errors) else 0


if __name__ == "__main__":
    raise SystemExit(main())
