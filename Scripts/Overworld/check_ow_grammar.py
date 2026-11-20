#!/usr/bin/env python3
"""Deterministic 192-Map Scawful Overworld Design Grammar Checker (Read-Only).

Audits rev5 OOSOW192 / ZSCustomOverworld ROMs across 9 formal grammar axes
grounded in Scawful's hand-crafted Kalyxo ($00-$3F), Eon Abyss ($40-$7F), and
Special Overworld ($80-$BF) maps:

  1. LANE-* : Open navigable lanes, choke-point bottlenecks, trapped pockets,
              and multi-map sea navigation channels
  2. CURV-* : Organic curved cliff/shore framing vs boxy 90-deg staircases,
              flat walls, twin islands, checkerboards, and uncapped bands
  3. PROP-* : Ground prop grouping vs isolated 1-tile noise and barren monotone
  4. SEAM-* : Multi-map Tile16 passability + aux_pal/main_pal/bg_gfx/overlay/
              mosaic/music/rain attribute continuity across seams
  5. EDGE-* : Edge-of-map safety, OOB exits/entrances/sprites/caches,
              embedded ground sprites, and cut-off seam objects
  6. LAND-* : Landmarks, entrance/exit doormat framing, and focal hierarchy
  7. SPR-*  : Day/Night/Peacetime sprite-palette parity, sheet format/slots,
              aquatic-on-dry-land, persistent NPC phase parity, MainPal collisions
  8. INT-*  : Magic Bean 2x2 soil pad & flight landing affordances, ledge jumps
  9. STAIR-*: Unnecessary short cliff ladders (<= 2 tiles tall) vs biome stairs
              in Kalyxo ($00-$3F) and Special Overworld ($80-$BF)

Reuses existing repo ROM decoders in Scripts/Build/ and Scripts/Tools/ without
duplicating Tile16/Map32/sprite decoding logic.

Usage:
  python3 Scripts/Overworld/check_ow_grammar.py --rom <rom.sfc>
  python3 Scripts/Overworld/check_ow_grammar.py --rom <rom.sfc> --maps kalyxo
  python3 Scripts/Overworld/check_ow_grammar.py --rom <rom.sfc> --maps 0x11,0x1C-0x1D --json
  python3 Scripts/Overworld/check_ow_grammar.py --rom <rom.sfc> --write-baseline base.json
  python3 Scripts/Overworld/check_ow_grammar.py --rom <rom.sfc> --baseline base.json
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
for _rel in ("Scripts/Build", "Scripts/Tools"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_overworld_seams as cos  # noqa: E402
import check_sprite_sheet_compat as cssc  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402

TOOL_NAME = "oos-ow-grammar"
SCHEMA_VERSION = 1

SEVERITIES = ("INFO", "WARN", "ERROR")
SEV_RANK = {"INFO": 0, "WARN": 1, "ERROR": 2}

# Overlay/curtain/unlinked/reserved Special OW pages ($80-$BF) excluded from
# layout/silhouette/monotone aesthetic rules while still checked for OOB safety.
NON_PLAYABLE_SW_PAGES = frozenset({
    0x84, 0x85, 0x86, 0x88,
    0x93, 0x94, 0x95, 0x96, 0x97,
    0x9B, 0x9C, 0x9D, 0x9E, 0x9F,
})

SKY_ROUTE_MAPS = frozenset({0x84, 0x85, 0x86, 0x87, 0x8C, 0x8D, 0x8E, 0x8F})
SIGN_TILE16_IDS = frozenset({0x101, 0x17D})
LONELY_PROP_TILE16_IDS = frozenset({0x036, 0x20F})
WATERFALL_TILE16_IDS = frozenset({0x084})
DOOR_HALF_TILES = {
    0x00FB: 0x00FC, 0x00FC: 0x00FB,
    0x075D: 0x075E, 0x075E: 0x075D,
    0x05D8: 0x05D9, 0x05D9: 0x05D8,
    0x0B82: 0x0B83, 0x0B83: 0x0B82,
}
# Verified sheet 0x3C cliff-ladder Tile16s (chars 0x0A9/0x0B9, TileType 0x22)
# across Kalyxo ($00-$3F) and Special OW ($80-$BF); excludes carved stone steps
# (0x3F0-0x3F2, 0x4AA/0x4AE/0x4ED, 0x2E4, 0x530, 0x7E1), snow/wood bridges, and
# ranch fence stiles (0x731).
LADDER_CAP_TILE16_IDS = frozenset({
    0x016F, 0x0174, 0x0434, 0x044D, 0x046D, 0x0AC8, 0x0AC9, 0x0AD4,
})
LADDER_BODY_TILE16_IDS = frozenset({0x017E, 0x0184, 0x0185, 0x03F6})
LADDER_TILE16_IDS = LADDER_CAP_TILE16_IDS | LADDER_BODY_TILE16_IDS

# Aerial, treetop, cliff-perched, or ambient/object sprites that legitimately
# occupy solid tree/cliff/door coordinates without being stuck inside walls.
NON_GROUND_SPRITES = frozenset({
    0x00,  # Raven (treetops)
    0x01,  # Vulture (aerial)
    0x0A,  # EonOwl / KaeporaGaebora (perched)
    0x19,  # Poe (flies through walls)
    0x59,  # Boulder / FallingRock
    0xAA,  # FallingRock
    0xAC,  # Apple (dash-tree drop)
    0xB3,  # PedestalPlaque / ambient
    0xF3,  # Overworld ambient/swarm
    0xF4,  # Whirlpool / ambient
})

# Persistent NPC / vendor / quest-giver sprites that should remain consistent
# between Day (phase 1) and Night (phase 2) unless intentionally scheduled.
PERSISTENT_NPC_SPRITES: dict[int, str] = {
    0x07: "BeanVendor",
    0x14: "BusinessScrub",
    0x25: "VillageDog",
    0x52: "Goron_ZoraKing",
    0x73: "Farore",
    0x7B: "KydrogNPC",
    0x9E: "MakuTree",
    0xA0: "DekuScrubNPC",
    0xB2: "WindmillGuy",
    0xB8: "SeaZora_Princess",
    0xD7: "Vasu",
    0xE8: "MaskSalesman",
    0xF0: "Mermaid",
    0xF1: "Korok",
}

DEFAULT_BEAN_SPOTS: tuple[dict[str, Any], ...] = (
    {"index": 0, "map_id": 0x00, "home_x": 0x0240, "home_y": 0x00D0,
     "dx": 420, "dy": 212},
    {"index": 1, "map_id": 0x2D, "home_x": 0x0BA0, "home_y": 0x0AC0,
     "dx": -256, "dy": -96},
    {"index": 2, "map_id": 0x15, "home_x": 0x0B90, "home_y": 0x05C0,
     "dx": -64, "dy": -368},
    {"index": 3, "map_id": 0x33, "home_x": 0x0740, "home_y": 0x0E30,
     "dx": 208, "dy": -480},
)


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def parse_map_spec(spec: str, capacity: int) -> set[int]:
    """Parse --maps spec (world alias, region preset, hex IDs, or ranges) into map set."""
    s = (spec or "all").strip()
    low = s.lower()
    if low in ("all", "kalyxo", "abyss", "special") or low in cos.REGION_CORE_MAPS:
        return cos.region_map_filter(low, capacity)

    selected: set[int] = set()
    for part in s.split(","):
        tok = part.strip()
        if not tok:
            continue
        tok_low = tok.lower()
        if tok_low in ("all", "kalyxo", "abyss", "special") or tok_low in cos.REGION_CORE_MAPS:
            selected.update(cos.region_map_filter(tok_low, capacity))
            continue
        sep = ".." if ".." in tok else ("-" if "-" in tok else None)
        if sep is not None:
            a_str, b_str = tok.split(sep, 1)
            a = _parse_map_token(a_str)
            b = _parse_map_token(b_str)
            if a > b:
                raise ValueError(f"Invalid descending map range: {tok!r}")
            for m in range(a, b + 1):
                if 0 <= m < capacity:
                    selected.add(m)
        else:
            m = _parse_map_token(tok)
            if not (0 <= m < capacity):
                raise ValueError(f"Map ID 0x{m:02X} out of ROM capacity {capacity}")
            selected.add(m)
    if not selected:
        raise ValueError(f"Empty --maps selection from {spec!r}")
    return selected


def _parse_map_token(tok: str) -> int:
    t = tok.strip()
    if t.startswith("$"):
        return int(t[1:], 16)
    if t.lower().startswith("0x"):
        return int(t, 16)
    if re.fullmatch(r"[0-9A-Fa-f]{1,2}", t):
        return int(t, 16)
    return int(t, 0)


def _signed_i8(b: int) -> int:
    return b - 256 if b >= 128 else b


def _load_sky_tiletypes(root: Path = ROOT) -> tuple[list[int] | None, list[int] | None]:
    """Parse SkyTileTypes_WestLanding and SkyTileTypes from Overworld/sky_tile_types.asm."""
    asm_path = root / "Overworld" / "sky_tile_types.asm"
    if not asm_path.is_file():
        return None, None
    text = asm_path.read_text(encoding="utf-8", errors="replace")

    def extract_table(label: str, end_label: str) -> list[int] | None:
        m = re.search(rf"^{label}:\s*\n(.*?)^{end_label}:", text, re.MULTILINE | re.DOTALL)
        if not m:
            return None
        vals: list[int] = []
        for raw in m.group(1).splitlines():
            code = raw.split(";", 1)[0].strip()
            if code.lower().startswith("db "):
                for tok in code[3:].split(","):
                    t = tok.strip()
                    if t.startswith("$"):
                        vals.append(int(t[1:], 16))
                    elif t:
                        vals.append(int(t, 0))
        return vals[:0x200] if len(vals) >= 0x200 else None

    return (
        extract_table("SkyTileTypes_WestLanding", "SkyTileTypes_WestLandingEnd"),
        extract_table("SkyTileTypes", "SkyTileTypesEnd"),
    )


def _load_bean_spots(root: Path = ROOT) -> list[dict[str, Any]]:
    """Load Magic Bean spots from Data/overworld/magic_bean_spots.json or bean_vendor.asm."""
    json_path = root / "Data" / "overworld" / "magic_bean_spots.json"
    if json_path.is_file():
        try:
            data = json.loads(json_path.read_text(encoding="utf-8"))
            spots_out: list[dict[str, Any]] = []
            for entry in data.get("spots", []):
                raw_map = entry["parent_map"]
                map_id = int(raw_map[1:], 16) if isinstance(raw_map, str) and raw_map.startswith("$") else (
                    int(raw_map, 0) if isinstance(raw_map, str) else int(raw_map)
                )
                legs = entry.get("legs", [])
                dx = sum(int(leg["x_speed"]) * int(leg["timer"]) for leg in legs) // 16
                dy = sum(int(leg["y_speed"]) * int(leg["timer"]) for leg in legs) // 16
                spots_out.append({
                    "index": int(entry["index"]),
                    "map_id": map_id,
                    "home_x": int(entry["home_x"]),
                    "home_y": int(entry["home_y"]),
                    "dx": dx,
                    "dy": dy,
                })
            if spots_out:
                return spots_out
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            pass

    asm_path = root / "Sprites" / "NPCs" / "bean_vendor.asm"
    if not asm_path.is_file():
        return []
    text = asm_path.read_text(encoding="utf-8", errors="replace")

    def read_db_list(label: str) -> list[int]:
        m = re.search(rf"^{label}:\s*\n((?:\s*db\s+[^\n]+\n)+)", text, re.MULTILINE)
        if not m:
            return []
        out: list[int] = []
        for line in m.group(1).splitlines():
            code = line.split(";", 1)[0].strip()
            if code.lower().startswith("db "):
                for tok in code[3:].split(","):
                    t = tok.strip()
                    if t.startswith("$"):
                        out.append(int(t[1:], 16))
                    elif t:
                        out.append(int(t, 0))
        return out

    screens = read_db_list("MagicBeanSpot_Screens")
    x_lo = read_db_list("MagicBeanSpot_HomeXLo")
    x_hi = read_db_list("MagicBeanSpot_HomeXHi")
    y_lo = read_db_list("MagicBeanSpot_HomeYLo")
    y_hi = read_db_list("MagicBeanSpot_HomeYHi")
    vx = read_db_list("MagicBean_LegXSpeed")
    vy = read_db_list("MagicBean_LegYSpeed")
    tm = read_db_list("MagicBean_LegTimers")
    if len(screens) != 4 or len(x_lo) != 4 or len(y_lo) != 4:
        return [dict(x) for x in DEFAULT_BEAN_SPOTS]

    spots: list[dict[str, Any]] = []
    for i in range(4):
        hx = x_lo[i] | (x_hi[i] << 8)
        hy = y_lo[i] | (y_hi[i] << 8)
        dx = dy = 0
        if len(vx) >= (i + 1) * 3 and len(vy) >= (i + 1) * 3 and len(tm) >= (i + 1) * 3:
            dx = sum(_signed_i8(vx[i * 3 + k]) * tm[i * 3 + k] for k in range(3)) // 16
            dy = sum(_signed_i8(vy[i * 3 + k]) * tm[i * 3 + k] for k in range(3)) // 16
        spots.append({
            "index": i,
            "map_id": screens[i],
            "home_x": hx,
            "home_y": hy,
            "dx": dx,
            "dy": dy,
        })
    return spots


class GrammarContext(cos.OverworldContext):
    """Extended read-only overworld context with Sky TileTypes, area metadata, and raw sprites."""

    def __init__(self, rom: bytes, root: Path = ROOT) -> None:
        super().__init__(rom, root=root)
        self.sky_west_tt, self.sky_tt = _load_sky_tiletypes(root)
        self.sky_route_active = self._detect_sky_route()
        self.custom_names = cssc.load_custom_sprite_names(root)
        self.labels = sic.load_resource_labels(root).get("overworld_map", {})
        self._meta_cache: dict[int, dict[str, Any]] = {}
        self._cls_grid_cache: dict[int, list[list[str]]] = {}

    def _detect_sky_route(self) -> bool:
        """Detect whether Sky maps ($8C) use the Sky TileType layout (tile 0x128 cloud void)."""
        if self.capacity <= 0x8C or self.sky_west_tt is None or self.sky_tt is None:
            return False
        g = self.screen_grid(0x8C)
        # Sky West Landing uses Tile16 0x128 as void cloud sky filler.
        cnt_128 = sum(1 for row in g for t in row if t == 0x128)
        return cnt_128 >= 32

    def map_label(self, map_id: int) -> str:
        for k in (f"0x{map_id:02x}", f"0x{map_id:x}", f"{map_id}", f"${map_id:02x}"):
            if k in self.labels:
                return self.labels[k]
        return f"Map 0x{map_id:02X}"

    def tile16_quadrant_types(self, map_id: int, tid: int) -> tuple[int, int, int, int]:
        w0, w1, w2, w3 = self.tile16_words(map_id, tid)
        table = self.ow_tt
        if self.sky_route_active and map_id in SKY_ROUTE_MAPS:
            par, sz = self.parent_and_size(map_id)
            if map_id == 0x8C and par == 0x8C and sz == 0 and self.sky_west_tt is not None:
                table = self.sky_west_tt
            elif self.sky_tt is not None:
                table = self.sky_tt
        return (
            table[w0 & 0x1FF],
            table[w1 & 0x1FF],
            table[w2 & 0x1FF],
            table[w3 & 0x1FF],
        )

    def class_grid(self, map_id: int) -> list[list[str]]:
        cg = self._cls_grid_cache.get(map_id)
        if cg is None:
            g = self.screen_grid(map_id)
            cg = [[self.tile16_summary_class(map_id, g[y][x]) for x in range(32)] for y in range(32)]
            self._cls_grid_cache[map_id] = cg
        return cg

    def area_metadata(self, map_id: int) -> dict[str, Any]:
        """Decode main_pal, aux1/aux2, anim_pal, mosaic, anim_gfx, overlay, gfx8, area_gfx, music, spr."""
        par, sz = self.parent_and_size(map_id)
        cached = self._meta_cache.get(par)
        if cached is not None:
            return cached
        rom = self.rom
        if par < 0xA0:
            main_pal = rom[sic.PC_ZS_MAIN_PAL_ARR + par]
            pal_set = rom[0x4C635 + par] if 0x4C635 + par < len(rom) else 0
            mosaic = rom[0x140200 + par] if 0x140200 + par < len(rom) else 0
            anim_gfx = rom[sic.PC_ZS_ANIM_GFX_ARR + par]
            overlay = ctp.read_u16(rom, sic.PC_ZS_OVERLAY_ARR + par * 2)
            bg_col = ctp.read_u16(rom, sic.PC_ZS_CUSTOM_BG_PAL + par * 2)
            gfx8 = tuple(rom[sic.PC_ZS_TILE_GFX_ARR + par * 8:sic.PC_ZS_TILE_GFX_ARR + par * 8 + 8])
            area_gfx = rom[sic.PC_AREA_GFX + par]
            if par < 0x40:
                music = tuple(rom[0x14303 + par + p * 0x40] for p in range(4))
            else:
                music = (rom[0x14403 + (par - 0x40)],) * 4
        else:
            nt = self.native_tables
            main_pal = rom[nt["main_palette"] + par]
            pal_set = rom[nt["palette_set"] + par]
            mosaic = rom[nt["mosaic"] + par]
            anim_gfx = rom[nt["animated"] + par]
            overlay = ctp.read_u16(rom, nt["overlay"] + par * 2)
            bg_col = ctp.read_u16(rom, nt["bg_color"] + par * 2)
            gfx8 = tuple(rom[nt["gfx"] + par * 8:nt["gfx"] + par * 8 + 8])
            area_gfx = rom[nt["area_gfx"] + par]
            music = tuple(rom[nt[f"music_phase{p}"] + par] for p in range(4))

        pg_off = sic.PC_PAL_GROUP + pal_set * 4
        if pg_off + 3 <= len(rom):
            aux1, aux2, anim_pal = rom[pg_off], rom[pg_off + 1], rom[pg_off + 2]
        else:
            aux1, aux2, anim_pal = 0, 0, 0

        spr_meta: list[tuple[int, int]] = []
        for ph in range(3):
            if par < 0x40:
                sg = rom[cssc.OW_SPR_GFX_PC + par + ph * 0x40]
                sp = rom[cssc.OW_SPR_PAL_PC + par + ph * 0x40]
            elif par < 0x80:
                sg = rom[cssc.OW_SPR_GFX_PC + par + 0x80]
                sp = rom[cssc.OW_SPR_PAL_PC + par + 0x80]
            elif par < 0xA0:
                sg = rom[cssc.SW_SPR_GFX_PC + (par - 0x80)]
                sp = rom[cssc.SW_SPR_PAL_PC + (par - 0x80)]
            else:
                gk = ("special_sprite_gfx", "special_sprite_gfx_phase1", "special_sprite_gfx_phase2")[ph]
                pk = ("special_sprite_palettes", "special_sprite_palettes_phase1", "special_sprite_palettes_phase2")[ph]
                sg = rom[self.native_tables[gk] + par] if gk in self.native_tables else 0
                sp = rom[self.native_tables[pk] + par] if pk in self.native_tables else 0
            spr_meta.append((sg, sp))

        meta = {
            "parent": par,
            "size": sz,
            "main_pal": main_pal,
            "pal_set": pal_set,
            "aux1": aux1,
            "aux2": aux2,
            "anim_pal": anim_pal,
            "mosaic": mosaic,
            "anim_gfx": anim_gfx,
            "overlay": overlay,
            "bg_col": bg_col,
            "gfx8": gfx8,
            "area_gfx": area_gfx,
            "music": music,
            "spr_meta": spr_meta,
        }
        self._meta_cache[par] = meta
        return meta

    def read_raw_sprites(self, map_id: int, phase: int) -> list[dict[str, int]]:
        """Read sprite entries preserving raw coordinate bytes before & 0x3F masking."""
        out: list[dict[str, int]] = []
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
            ry, rx, sid = self.rom[p], self.rom[p + 1], self.rom[p + 2]
            out.append({
                "raw_x": rx,
                "raw_y": ry,
                "x": rx & 0x3F,
                "y": ry & 0x3F,
                "sid": sid,
            })
            p += 3
        return out

    def sprite_name(self, sid: int) -> str:
        return (
            self.custom_names.get(sid)
            or (cssc.SPRITE_SHEET_RULES[sid]["name"] if sid in cssc.SPRITE_SHEET_RULES else f"Spr_0x{sid:02X}")
        )


def _make_finding(
    *,
    rule_id: str,
    category: str,
    severity: str,
    map_id: int,
    parent_id: int,
    key_suffix: str,
    location: str,
    message: str,
    fix_hint: str,
    related_map_id: int | None = None,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "finding_key": f"{rule_id}.map_0x{map_id:02X}.{key_suffix}",
        "rule_id": rule_id,
        "category": category,
        "severity": severity,
        "map_id": f"0x{map_id:02X}",
        "parent_id": f"0x{parent_id:02X}",
        **({"related_map_id": f"0x{related_map_id:02X}"} if related_map_id is not None else {}),
        "location": location,
        "message": message,
        "fix_hint": fix_hint,
        "details": details or {},
    }


def _collect_entities_by_map(ctx: GrammarContext) -> tuple[dict[int, list[dict]], dict[int, list[dict]]]:
    exits_by_map: dict[int, list[dict]] = defaultdict(list)
    ents_by_map: dict[int, list[dict]] = defaultdict(list)
    for ex in ctx.read_exits():
        par = ex["parent_id"]
        fx, fy = ex["foot_tile_x"], ex["foot_tile_y"]
        if 0 <= fx < 64 and 0 <= fy < 64:
            phys = par + (8 if fy >= 32 else 0) + (1 if fx >= 32 else 0)
            if phys < ctx.capacity:
                exits_by_map[phys].append({"lx": fx % 32, "ly": fy % 32, **ex})
    for ent in ctx.read_entrances():
        par = ent["parent_id"]
        cx, cy = ent["local_tile_x"], ent["local_tile_y"]
        if 0 <= cx < 64 and 0 <= cy < 64:
            phys = par + (8 if cy >= 32 else 0) + (1 if cx >= 32 else 0)
            if phys < ctx.capacity:
                ents_by_map[phys].append({"lx": cx % 32, "ly": cy % 32, **ent})
    return exits_by_map, ents_by_map


# ---------------------------------------------------------------------------
# Rule Evaluators (1..8)
# ---------------------------------------------------------------------------

def _check_lanes_and_curves_and_props(
    ctx: GrammarContext,
    selected: set[int],
    exits_by_map: dict[int, list[dict]],
    ents_by_map: dict[int, list[dict]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    # Precompute hidden items flags per map if needed (non-zero indicates map uses buried/bush secrets)
    for m in sorted(selected):
        if m in NON_PLAYABLE_SW_PAGES:
            continue
        par, _ = ctx.parent_and_size(m)
        g = ctx.screen_grid(m)
        cls = ctx.class_grid(m)
        counts = Counter(c for row in cls for c in row)
        tid_counts = Counter(g[y][x] for y in range(32) for x in range(32))
        top_tid, top_cnt = tid_counts.most_common(1)[0]
        uniq = len(tid_counts)

        # --- LANE-001: Sustained 1-tile narrow interior corridor bottleneck (>= 8 tiles in [1..30]) ---
        # Exclude stairs/ledges so mountain staircases aren't penalized.
        max_run = 0
        best_pos = (0, 0, "V")
        blocked = {"solid", "deep_water"}
        pass_land = {"walkable", "shallow_water"}
        for x in range(1, 31):
            run = 0
            for y in range(1, 31):
                if cls[y][x] in pass_land and cls[y][x - 1] in blocked and cls[y][x + 1] in blocked:
                    tts = ctx.tile16_quadrant_types(m, g[y][x])
                    if any(t in (0x12, 0x18, 0x1A, 0x22) for t in tts):
                        run = 0
                    else:
                        run += 1
                        if run > max_run:
                            max_run = run
                            best_pos = (x, y - run + 1, "V")
                else:
                    run = 0
        for y in range(1, 31):
            run = 0
            for x in range(1, 31):
                if cls[y][x] in pass_land and cls[y - 1][x] in blocked and cls[y + 1][x] in blocked:
                    tts = ctx.tile16_quadrant_types(m, g[y][x])
                    if any(t in (0x12, 0x18, 0x1A, 0x22) for t in tts):
                        run = 0
                    else:
                        run += 1
                        if run > max_run:
                            max_run = run
                            best_pos = (x - run + 1, y, "H")
                else:
                    run = 0
        if max_run >= 10:
            bx, by, axis = best_pos
            findings.append(_make_finding(
                rule_id="LANE-001",
                category="lanes",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix=f"narrow_{axis}_{bx}_{by}",
                location=f"({bx},{by}) {axis}-run len={max_run}",
                message=f"Sustained {max_run}-tile-long 1-tile-wide interior choke corridor ({axis}) restricts movement and Epona riding.",
                fix_hint=f"Widen corridor around ({bx},{by}) to >= 2-3 walkable tiles by trimming adjacent interior wall/tree blocks (see $11/$12/$2A edits).",
                details={"length": max_run, "x": bx, "y": by, "axis": axis},
            ))

        # --- LANE-002: Sealed unreachable walkable pocket (8x8 subtile BFS including swim + ledge + seams) ---
        sub = [[""] * 64 for _ in range(64)]
        for ty in range(32):
            for tx in range(32):
                q = ctx.tile16_quadrant_classes(m, g[ty][tx])
                sub[ty * 2][tx * 2] = q[0]
                sub[ty * 2][tx * 2 + 1] = q[1]
                sub[ty * 2 + 1][tx * 2] = q[2]
                sub[ty * 2 + 1][tx * 2 + 1] = q[3]
        pass_or_water = {"walkable", "shallow_water", "deep_water", "interactive", "ledge"}
        vis = [[False] * 64 for _ in range(64)]
        for sy in range(64):
            for sx in range(64):
                if sub[sy][sx] in ("walkable", "shallow_water") and not vis[sy][sx]:
                    q = deque([(sx, sy)])
                    vis[sy][sx] = True
                    cells: list[tuple[int, int]] = []
                    touches_border = False
                    has_water_or_ledge = False
                    while q:
                        cx, cy = q.popleft()
                        cells.append((cx, cy))
                        if cx in (0, 63) or cy in (0, 63):
                            touches_border = True
                        if sub[cy][cx] in ("deep_water", "ledge"):
                            has_water_or_ledge = True
                        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < 64 and 0 <= ny < 64 and not vis[ny][nx] and sub[ny][nx] in pass_or_water:
                                vis[ny][nx] = True
                                q.append((nx, ny))
                    walk_sub = sum(1 for cx, cy in cells if sub[cy][cx] in ("walkable", "shallow_water"))
                    if not touches_border and not has_water_or_ledge and walk_sub >= 24:
                        tset = {(cx // 2, cy // 2) for cx, cy in cells}
                        ent_hit = any(
                            (e["lx"] + dx, e["ly"] + dy) in tset
                            for e in (exits_by_map[m] + ents_by_map[m])
                            for dx in (-1, 0, 1) for dy in (-2, -1, 0, 1, 2)
                        )
                        if not ent_hit:
                            ax, ay = min(tset)
                            findings.append(_make_finding(
                                rule_id="LANE-002",
                                category="lanes",
                                severity="WARN",
                                map_id=m,
                                parent_id=par,
                                key_suffix=f"pocket_{ax}_{ay}",
                                location=f"({ax},{ay}) {walk_sub // 4} tiles",
                                message=f"Enclosed walkable pocket (~{walk_sub // 4} tiles) around ({ax},{ay}) has no border, water, ledge, or entrance connection.",
                                fix_hint=f"Open a passage or ledge/stair into pocket ({ax},{ay}), or fill unused hollow interior with solid terrain.",
                                details={"subtiles": walk_sub, "anchor": [ax, ay]},
                            ))

        # --- CURV-001: Boxy unchamfered solid interior rectangle (>= 5x5 exposed on >= 3 sides without diagonal corners) ---
        box_found = False
        for y0 in range(2, 26):
            if box_found:
                break
            for x0 in range(2, 26):
                if cls[y0][x0] != "solid":
                    continue
                w = 0
                while x0 + w < 30 and cls[y0][x0 + w] == "solid" and len(set(ctx.tile16_quadrant_classes(m, g[y0][x0 + w]))) == 1:
                    w += 1
                if w < 5:
                    continue
                h = 1
                while y0 + h < 30:
                    ok_row = all(
                        cls[y0 + h][x] == "solid" and len(set(ctx.tile16_quadrant_classes(m, g[y0 + h][x]))) == 1
                        for x in range(x0, x0 + w)
                    )
                    if not ok_row:
                        break
                    h += 1
                if h >= 5:
                    # Check how many outer faces directly expose walkable/shallow ground with sharp pure-solid tiles
                    n_face = sum(1 for x in range(x0, x0 + w) if cls[y0 - 1][x] in pass_land) >= w - 1
                    s_face = sum(1 for x in range(x0, x0 + w) if cls[y0 + h][x] in pass_land) >= w - 1
                    w_face = sum(1 for y in range(y0, y0 + h) if cls[y][x0 - 1] in pass_land) >= h - 1
                    e_face = sum(1 for y in range(y0, y0 + h) if cls[y][x0 + w] in pass_land) >= h - 1
                    if sum((n_face, s_face, w_face, e_face)) >= 3:
                        findings.append(_make_finding(
                            rule_id="CURV-001",
                            category="curves",
                            severity="WARN",
                            map_id=m,
                            parent_id=par,
                            key_suffix=f"box_{x0}_{y0}_{w}x{h}",
                            location=f"({x0},{y0}) {w}x{h}",
                            message=f"Boxy unchamfered {w}x{h} axis-aligned solid rectangle at ({x0},{y0}) exposes flat 90-degree edges without curved diagonal corners.",
                            fix_hint=f"Break up rigid rectangular block ({x0},{y0})..({x0+w-1},{y0+h-1}) with stepped/curved diagonal Tile16 corners or carve an organic clearing.",
                            details={"x": x0, "y": y0, "w": w, "h": h},
                        ))
                        box_found = True
                        break

        # --- CURV-002: Long flat identical boundary run (>= 16 tiles in interior [2..29]) ---
        flat_best = (0, 0, 0, "H")
        for y in range(2, 30):
            run = 0
            prev_tid = -1
            for x in range(2, 30):
                is_bnd = (
                    (cls[y][x] in ("solid", "deep_water") and (cls[y - 1][x] in pass_land or cls[y + 1][x] in pass_land))
                    and g[y][x] == prev_tid
                )
                if is_bnd:
                    run += 1
                    if run > flat_best[0]:
                        flat_best = (run, x - run, y, "H")
                else:
                    run = 1 if (cls[y][x] in ("solid", "deep_water") and (cls[y - 1][x] in pass_land or cls[y + 1][x] in pass_land)) else 0
                prev_tid = g[y][x]
        for x in range(2, 30):
            run = 0
            prev_tid = -1
            for y in range(2, 30):
                is_bnd = (
                    (cls[y][x] in ("solid", "deep_water") and (cls[y][x - 1] in pass_land or cls[y][x + 1] in pass_land))
                    and g[y][x] == prev_tid
                )
                if is_bnd:
                    run += 1
                    if run > flat_best[0]:
                        flat_best = (run, x, y - run, "V")
                else:
                    run = 1 if (cls[y][x] in ("solid", "deep_water") and (cls[y][x - 1] in pass_land or cls[y][x + 1] in pass_land)) else 0
                prev_tid = g[y][x]
        if flat_best[0] >= 16:
            flen, fx, fy, faxis = flat_best
            findings.append(_make_finding(
                rule_id="CURV-002",
                category="curves",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix=f"flat_{faxis}_{fx}_{fy}",
                location=f"({fx},{fy}) {faxis}-run len={flen}",
                message=f"Flat straight {flen}-tile identical boundary wall/shoreline at ({fx},{fy}) lacks organic stepped zigzags.",
                fix_hint=f"Introduce 1-2 tile stepped setbacks or diagonal bends along the {flen}-tile straight wall at ({fx},{fy}) (see $1C/$1D/$92).",
                details={"length": flen, "x": fx, "y": fy, "axis": faxis},
            ))

        # --- CURV-003: Twin/Copy-Pasted Islands or Boxy Rectangular Floating Island ---
        if counts["deep_water"] >= 200:
            vis_isl = [[False] * 32 for _ in range(32)]
            islands: list[dict[str, Any]] = []
            for y in range(32):
                for x in range(32):
                    if cls[y][x] != "deep_water" and not vis_isl[y][x]:
                        q = deque([(x, y)])
                        vis_isl[y][x] = True
                        icells: list[tuple[int, int]] = []
                        edge = False
                        while q:
                            cx, cy = q.popleft()
                            icells.append((cx, cy))
                            if cx in (0, 31) or cy in (0, 31):
                                edge = True
                            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                                nx, ny = cx + dx, cy + dy
                                if 0 <= nx < 32 and 0 <= ny < 32 and not vis_isl[ny][nx] and cls[ny][nx] != "deep_water":
                                    vis_isl[ny][nx] = True
                                    q.append((nx, ny))
                        if not edge and len(icells) >= 16:
                            xs = [p[0] for p in icells]
                            ys = [p[1] for p in icells]
                            bw = max(xs) - min(xs) + 1
                            bh = max(ys) - min(ys) + 1
                            rect_ratio = len(icells) / float(bw * bh)
                            islands.append({
                                "area": len(icells), "w": bw, "h": bh,
                                "x": min(xs), "y": min(ys), "rect_ratio": rect_ratio,
                            })
            twin_hit = False
            for i in range(len(islands)):
                for j in range(i + 1, len(islands)):
                    a1, a2 = islands[i], islands[j]
                    if abs(a1["area"] - a2["area"]) <= 4 and abs(a1["w"] - a2["w"]) <= 1 and abs(a1["h"] - a2["h"]) <= 1:
                        twin_hit = True
                        findings.append(_make_finding(
                            rule_id="CURV-003",
                            category="curves",
                            severity="WARN",
                            map_id=m,
                            parent_id=par,
                            key_suffix=f"twin_islands_{a1['x']}_{a1['y']}",
                            location=f"({a1['x']},{a1['y']}) & ({a2['x']},{a2['y']})",
                            message=f"Duplicate twin island silhouettes ({a1['w']}x{a1['h']}, area {a1['area']} vs {a2['area']}) read as copy-pasted symmetry.",
                            fix_hint="Give each islet an asymmetric coastline, vary scale/shoal tails, or merge into one organic cove.",
                            details={"island_a": a1, "island_b": a2},
                        ))
                        break
                if twin_hit:
                    break
            if not twin_hit:
                for isl in islands:
                    if isl["area"] >= 120 and isl["rect_ratio"] >= 0.85 and isl["w"] >= 10 and isl["h"] >= 10:
                        findings.append(_make_finding(
                            rule_id="CURV-003",
                            category="curves",
                            severity="WARN",
                            map_id=m,
                            parent_id=par,
                            key_suffix=f"box_island_{isl['x']}_{isl['y']}",
                            location=f"({isl['x']},{isl['y']}) {isl['w']}x{isl['h']}",
                            message=f"Boxy island silhouette ({isl['w']}x{isl['h']}, fill={isl['rect_ratio']:.2f}) reads as a flat geometric block.",
                            fix_hint="Carve asymmetric coves, diagonal headlands, and shoal spits along the island shoreline (see $92/$32/$33).",
                            details=isl,
                        ))
                        break

        # --- CURV-004: Checkerboard Edge Teeth (#W#W#W) ---
        cb_rows: list[int] = []
        for y in range(32):
            alt = 0
            for x in range(1, 31):
                if (cls[y][x] == "solid" and cls[y][x - 1] == "deep_water" and cls[y][x + 1] == "deep_water"):
                    alt += 1
            if alt >= 4:
                cb_rows.append(y)
        if cb_rows:
            findings.append(_make_finding(
                rule_id="CURV-004",
                category="curves",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix=f"checkerboard_rows_{cb_rows[0]}",
                location=f"rows {cb_rows}",
                message=f"Alternating solid/deep-water checkerboard edge teeth (#W#W#W) on row(s) {cb_rows}.",
                fix_hint="Replace checkerboard edge rocks with continuous reef rings or rounded shoal transitions (see $92).",
                details={"rows": cb_rows},
            ))

        # --- CURV-005: Unclosed / Uncapped Mid-Screen 1-Tile Band (len >= 4) ---
        # Look for horizontal/vertical 1-tile-thick solid cliff/wall strips ending mid-screen with 3 open sides.
        uncapped: list[tuple[int, int]] = []
        for y in range(3, 29):
            x = 3
            while x < 29:
                if cls[y][x] == "solid" and cls[y - 1][x] in pass_land and cls[y + 1][x] in pass_land:
                    x_start = x
                    while x < 29 and cls[y][x] == "solid" and cls[y - 1][x] in pass_land and cls[y + 1][x] in pass_land:
                        x += 1
                    run = x - x_start
                    if run >= 4:
                        left_open = cls[y][x_start - 1] in pass_land
                        right_open = cls[y][x] in pass_land
                        if left_open and right_open:
                            uncapped.append((x_start, y))
                else:
                    x += 1
        if uncapped:
            ux, uy = uncapped[0]
            findings.append(_make_finding(
                rule_id="CURV-005",
                category="curves",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix=f"uncapped_{ux}_{uy}",
                location=f"({ux},{uy})",
                message=f"Unclosed mid-screen 1-tile wall/cliff band at ({ux},{uy}) terminates without corner cap or border anchor ({len(uncapped)} total).",
                fix_hint="Extend cliff/wall band to a proper cap/corner piece or connect cleanly to a map border.",
                details={"locations": [list(p) for p in uncapped[:6]]},
            ))

        # --- PROP-001: Isolated 1-Tile Interactive Bush / Rock Noise ---
        iso_props: list[tuple[int, int, int]] = []
        for y in range(1, 31):
            for x in range(1, 31):
                tid = g[y][x]
                if tid in LONELY_PROP_TILE16_IDS or (cls[y][x] == "interactive" and tid not in SIGN_TILE16_IDS):
                    nbr8 = [cls[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)]
                    if all(n in ("walkable", "shallow_water") for n in nbr8):
                        iso_props.append((x, y, tid))
        if iso_props:
            sev = "WARN" if len(iso_props) >= 3 else "INFO"
            sample = [f"0x{t:03X}@({x},{y})" for x, y, t in iso_props[:4]]
            findings.append(_make_finding(
                rule_id="PROP-001",
                category="props",
                severity=sev,
                map_id=m,
                parent_id=par,
                key_suffix="isolated_interactive",
                location=", ".join(sample),
                message=f"{len(iso_props)} lonely 1-tile interactive prop(s) (bushes/rocks) sitting isolated in open walkable ground.",
                fix_hint="Group props into rhythmic 2-4 tile clusters anchored near landmarks/walls or remove stray singles (see $15/$27/$35/$52 cleanups).",
                details={"count": len(iso_props), "samples": [[x, y, f"0x{t:03X}"] for x, y, t in iso_props[:10]]},
            ))

        # --- PROP-002: Isolated 1-Tile Deep-Water / Meadow Solid Stray Pixel ---
        dw_singles: list[tuple[int, int, int]] = []
        for y in range(2, 30):
            for x in range(2, 30):
                if cls[y][x] == "solid":
                    nbr8 = [cls[y + dy][x + dx] for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dx, dy) != (0, 0)]
                    if all(n == "deep_water" for n in nbr8):
                        dw_singles.append((x, y, g[y][x]))
        if dw_singles:
            sample = [f"0x{t:03X}@({x},{y})" for x, y, t in dw_singles[:4]]
            findings.append(_make_finding(
                rule_id="PROP-002",
                category="props",
                severity="INFO",
                map_id=m,
                parent_id=par,
                key_suffix="isolated_sea_rock",
                location=", ".join(sample),
                message=f"{len(dw_singles)} isolated 1-tile solid rock(s) sitting alone in open deep water.",
                fix_hint="Cluster sea rocks with shallow shoal rings (see $92) or remove stray single-tile noise (see $AA).",
                details={"count": len(dw_singles), "samples": [[x, y, f"0x{t:03X}"] for x, y, t in dw_singles[:10]]},
            ))

        # --- PROP-003: Barren Monotone Screen ---
        top_pct = top_cnt / 1024.0
        if top_pct >= 0.85 and uniq <= 30:
            findings.append(_make_finding(
                rule_id="PROP-003",
                category="props",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix="barren_monotone",
                location=f"top=0x{top_tid:03X} ({top_pct * 100:.1f}%)",
                message=f"Barren monotone screen: tile 0x{top_tid:03X} covers {top_pct * 100:.1f}% with only {uniq} unique Tile16 IDs.",
                fix_hint="Add organic shoal reefs, sea stacks, ground texture variation (walkable->walkable), or focal landmarks (see $92/$52).",
                details={"top_tile16": f"0x{top_tid:03X}", "top_pct": round(top_pct, 4), "unique_tiles": uniq},
            ))
        elif top_pct >= 0.72 and uniq <= 38:
            findings.append(_make_finding(
                rule_id="PROP-003",
                category="props",
                severity="INFO",
                map_id=m,
                parent_id=par,
                key_suffix="low_variety",
                location=f"top=0x{top_tid:03X} ({top_pct * 100:.1f}%)",
                message=f"Low-variety screen: tile 0x{top_tid:03X} covers {top_pct * 100:.1f}% with {uniq} unique Tile16 IDs.",
                fix_hint="Consider adding visual landmarks, shoal accents, or floor texture breakup without blocking movement.",
                details={"top_tile16": f"0x{top_tid:03X}", "top_pct": round(top_pct, 4), "unique_tiles": uniq},
            ))

        # --- LAND-002: Featureless Playable Screen (zero entrances/exits/signs & low content) ---
        if (
            not exits_by_map[m]
            and not ents_by_map[m]
            and not any(t in SIGN_TILE16_IDS for t in tid_counts)
            and (top_pct >= 0.85 or (counts["deep_water"] >= 850 and uniq <= 30))
        ):
            findings.append(_make_finding(
                rule_id="LAND-002",
                category="landmarks",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix="featureless_screen",
                location=f"deep_water={counts['deep_water']}/1024",
                message="Featureless playable screen has zero entrances/exits/signs and >85% uniform filler.",
                fix_hint="Give the screen a memorable navigation landmark, reef/shoal chain, or hidden secret so crossing it feels purposeful.",
                details={"deep_water": counts["deep_water"], "unique_tiles": uniq, "top_pct": round(top_pct, 4)},
            ))

    return findings


def _check_seams_and_attributes(ctx: GrammarContext, selected: set[int]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    seams, _ = cos.enumerate_active_seams(ctx)
    for ma, mb, axis, is_cw in seams:
        if ma not in selected and mb not in selected:
            continue
        par_a, _ = ctx.parent_and_size(ma)
        par_b, _ = ctx.parent_and_size(mb)

        # 1. Tile16 Seam Continuity (SEAM-001 / SEAM-002)
        res = cos.audit_seam_pair(ctx, ma, mb, axis, is_cw)
        for sp in res["spans"]:
            rule_id = "SEAM-001" if sp["severity"] == "error" else "SEAM-002"
            sev = "ERROR" if sp["severity"] == "error" else "WARN"
            t_range = f"@{sp['start_tile']}..{sp['end_tile']}" if sp["start_tile"] != sp["end_tile"] else f"@{sp['start_tile']}"
            findings.append(_make_finding(
                rule_id=rule_id,
                category="seams",
                severity=sev,
                map_id=ma,
                parent_id=par_a,
                related_map_id=mb,
                key_suffix=f"to_0x{mb:02X}_{axis}_{sp['kind']}_{sp['start_tile']}",
                location=f"seam 0x{ma:02X}<->0x{mb:02X} ({axis}) {t_range}",
                message=(
                    f"{sp['kind']} across {'cross-world ' if is_cw else ''}seam "
                    f"0x{ma:02X}<->0x{mb:02X} ({axis}) for {sp['tile_count']} tile(s) {t_range}."
                ),
                fix_hint=(
                    f"Match edge Tile16 collision quarters at {t_range} on both sides of 0x{ma:02X}<->0x{mb:02X} "
                    f"(sample A={sp['sample_a']['tile16']} [{sp['sample_a']['class']}], B={sp['sample_b']['tile16']} [{sp['sample_b']['class']}])."
                ),
                details={"axis": axis, "cross_world": is_cw, **sp},
            ))

        # 2. Check Special OW sea channel choke on permitted water seams (LANE-003)
        ga = ctx.screen_grid(ma)
        gb = ctx.screen_grid(mb)
        open_subtiles = 0
        water_subtiles = 0
        for i in range(32):
            if axis == "H":
                ca = ctx.tile16_quadrant_classes(ma, ga[i][31])
                cb = ctx.tile16_quadrant_classes(mb, gb[i][0])
                pairs = ((ca[1], cb[0]), (ca[3], cb[2]))
            else:
                ca = ctx.tile16_quadrant_classes(ma, ga[31][i])
                cb = ctx.tile16_quadrant_classes(mb, gb[0][i])
                pairs = ((ca[2], cb[0]), (ca[3], cb[1]))
            for c1, c2 in pairs:
                if c1 in ("walkable", "shallow_water", "deep_water") and c2 in ("walkable", "shallow_water", "deep_water"):
                    open_subtiles += 1
                if c1 in ("shallow_water", "deep_water") and c2 in ("shallow_water", "deep_water"):
                    water_subtiles += 1

        if ma >= 0x80 and mb >= 0x80 and ma not in NON_PLAYABLE_SW_PAGES and mb not in NON_PLAYABLE_SW_PAGES:
            # If both maps have major deep water (>300 tiles) and EdgeGuard permits crossing,
            # warn if open water continuity is completely blocked (0 subtiles) or 1-tile narrow (< 4 subtiles).
            ca_dw = sum(1 for row in ctx.class_grid(ma) for c in row if c == "deep_water")
            cb_dw = sum(1 for row in ctx.class_grid(mb) for c in row if c == "deep_water")
            if ca_dw >= 300 and cb_dw >= 300 and 0 < water_subtiles < 4:
                findings.append(_make_finding(
                    rule_id="LANE-003",
                    category="lanes",
                    severity="WARN",
                    map_id=ma,
                    parent_id=par_a,
                    related_map_id=mb,
                    key_suffix=f"sea_channel_{mb:02X}_{axis}",
                    location=f"seam 0x{ma:02X}<->0x{mb:02X} ({axis})",
                    message=f"Narrow boat/swim channel ({water_subtiles} open water subtiles) across permitted Lyra Sea seam.",
                    fix_hint="Widen sailable water passage to >= 2 Tile16 tiles (4 subtiles) across seam.",
                    details={"water_subtiles": water_subtiles},
                ))

        if open_subtiles == 0 or is_cw:
            continue

        # 3. Attribute & VRAM Continuity Across Open Seams (SEAM-003 / SEAM-004)
        ma_m = ctx.area_metadata(ma)
        mb_m = ctx.area_metadata(mb)
        mos = bool((ma_m["mosaic"] & 0x01) or (mb_m["mosaic"] & 0x02)) if axis == "H" else bool((ma_m["mosaic"] & 0x04) or (mb_m["mosaic"] & 0x08))

        # Unsupported smooth scroll changes (main_pal, main_gfx 0/1/2/7, overlay)
        main_gfx_diff = (ma_m["gfx8"][:3] != mb_m["gfx8"][:3]) or (ma_m["gfx8"][7] != mb_m["gfx8"][7])
        main_pal_diff = ma_m["main_pal"] != mb_m["main_pal"]
        ov_diff = ma_m["overlay"] != mb_m["overlay"]
        if not mos and (main_gfx_diff or main_pal_diff or ov_diff):
            reasons = []
            if main_pal_diff:
                reasons.append(f"main_pal 0x{ma_m['main_pal']:02X}->0x{mb_m['main_pal']:02X}")
            if main_gfx_diff:
                reasons.append("main_gfx[0,1,2,7]")
            if ov_diff:
                reasons.append(f"overlay 0x{ma_m['overlay']:04X}->0x{mb_m['overlay']:04X}")
            # In Special OW ($80-$BF) SpecialOverworld_ShouldMosaic dynamically forces mosaic,
            # while in LW/DW ($00-$7F) only snow overlays $95/$9D auto-mosaic!
            in_sw = (ma >= 0x80 and mb >= 0x80)
            snow_auto = (not in_sw) and (not main_pal_diff) and (not main_gfx_diff) and ({ma_m["overlay"], mb_m["overlay"]} & {0x0095, 0x009D})
            if not snow_auto:
                sev_3 = "WARN" if (in_sw or not (main_pal_diff or main_gfx_diff)) else "ERROR"
                findings.append(_make_finding(
                    rule_id="SEAM-003",
                    category="seams",
                    severity=sev_3,
                    map_id=ma,
                    parent_id=par_a,
                    related_map_id=mb,
                    key_suffix=f"smooth_scroll_{mb:02X}_{axis}",
                    location=f"seam 0x{ma:02X}<->0x{mb:02X} ({axis})",
                    message=(
                        f"Open seam ({open_subtiles} passable subtiles) without Mosaic toggles "
                        + ", ".join(reasons)
                        + (" (triggers forced runtime mosaic)." if in_sw else " during smooth scroll.")
                    ),
                    fix_hint=(
                        f"Set symmetric Mosaic bits on 0x{ma:02X}/0x{mb:02X}, or unify "
                        + ", ".join(reasons)
                        + " across the seam."
                    ),
                    details={"open_subtiles": open_subtiles, "reasons": reasons, "mosaic": mos},
                ))

        # Open-seam aux_pal / aux_gfx / area_gfx / spr_gfx / music pops (SEAM-004)
        if open_subtiles >= 16:
            aux_pal_diff = (ma_m["aux1"], ma_m["aux2"]) != (mb_m["aux1"], mb_m["aux2"])
            aux_gfx_diffs = sum(1 for k in range(3, 7) if ma_m["gfx8"][k] != mb_m["gfx8"][k])
            agfx_diff = ma_m["area_gfx"] != mb_m["area_gfx"]
            spr_diff = ma_m["spr_meta"][1] != mb_m["spr_meta"][1]
            if aux_pal_diff or aux_gfx_diffs >= 2 or agfx_diff or spr_diff:
                pops = []
                if aux_pal_diff:
                    pops.append(f"aux_pal ({ma_m['aux1']:02X},{ma_m['aux2']:02X})->({mb_m['aux1']:02X},{mb_m['aux2']:02X})")
                if aux_gfx_diffs >= 2:
                    pops.append(f"custom8_aux({aux_gfx_diffs} sheets)")
                if agfx_diff:
                    pops.append(f"area_gfx 0x{ma_m['area_gfx']:02X}->0x{mb_m['area_gfx']:02X}")
                if spr_diff:
                    pops.append(
                        f"spr_p1 0x{ma_m['spr_meta'][1][0]:02X}/0x{ma_m['spr_meta'][1][1]:02X}"
                        f"->0x{mb_m['spr_meta'][1][0]:02X}/0x{mb_m['spr_meta'][1][1]:02X}"
                    )
                findings.append(_make_finding(
                    rule_id="SEAM-004",
                    category="seams",
                    severity="WARN",
                    map_id=ma,
                    parent_id=par_a,
                    related_map_id=mb,
                    key_suffix=f"vram_pop_{mb:02X}_{axis}",
                    location=f"seam 0x{ma:02X}<->0x{mb:02X} ({axis}) {open_subtiles} subtiles",
                    message=f"Wide open seam ({open_subtiles} subtiles) swaps {', '.join(pops)} mid-scroll.",
                    fix_hint="Align matching biome neighbors onto shared aux_pal, custom8 sheets, area_gfx, and p1 spr_gfx/pal.",
                    details={"open_subtiles": open_subtiles, "pops": pops},
                ))

            # Rain/ambience or song shift across wide open seam
            mus_a, mus_b = ma_m["music"][1], mb_m["music"][1]
            rain_a, rain_b = (mus_a >> 4), (mus_b >> 4)
            if rain_a != rain_b and not mos:
                findings.append(_make_finding(
                    rule_id="SEAM-004",
                    category="seams",
                    severity="WARN",
                    map_id=ma,
                    parent_id=par_a,
                    related_map_id=mb,
                    key_suffix=f"ambience_{mb:02X}_{axis}",
                    location=f"seam 0x{ma:02X}<->0x{mb:02X} ({axis})",
                    message=f"Ambience/SFX nibble jumps 0x{rain_a:X}->0x{rain_b:X} across wide open seam without mosaic.",
                    fix_hint="Match high ambience nibble across continuous biome borders or enable mosaic at biome gates.",
                    details={"music_a": f"0x{mus_a:02X}", "music_b": f"0x{mus_b:02X}"},
                ))
    return findings


def _check_edges_and_landmarks(
    ctx: GrammarContext,
    selected: set[int],
    exits_by_map: dict[int, list[dict]],
    ents_by_map: dict[int, list[dict]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    # 1. OOB / Blocked Exits, Entrances & Cached Landings (EDGE-001)
    ex_f, en_f = cos.audit_exits_and_entrances(ctx, selected)
    ca_f = cos.audit_asm_cached_landings(ctx, selected, root=ctx.root)
    for item in ex_f:
        mp = int(item["map_id"], 16)
        par = int(item["parent_id"], 16)
        findings.append(_make_finding(
            rule_id="EDGE-001",
            category="edges",
            severity="ERROR",
            map_id=mp,
            parent_id=par,
            key_suffix=f"exit_{item['exit_id']}_{item['kind']}",
            location=f"exit {item['exit_id']} @{tuple(item['foot_tile'])}",
            message=f"Exit {item['exit_id']} (room {item['room_id']}) on map 0x{mp:02X}: {item['kind']}.",
            fix_hint="Relocate exit landing coordinates onto in-bounds walkable/shallow ground or clear landing doormat.",
            details=item,
        ))
    for item in en_f:
        mp = int(item["map_id"], 16)
        par = int(item["parent_id"], 16)
        findings.append(_make_finding(
            rule_id="EDGE-001",
            category="edges",
            severity="ERROR",
            map_id=mp,
            parent_id=par,
            key_suffix=f"ent_{item['entrance_id']}_{item['kind']}",
            location=f"ent #{item['ow_ent_index']} ({item['entrance_id']}) @{tuple(item['tile'])}",
            message=f"Entrance #{item['ow_ent_index']} (id {item['entrance_id']}, room {item['room_id']}): {item['kind']}.",
            fix_hint="Ensure entrance trigger tile is inside parent area bounds and has an accessible walkable approach.",
            details=item,
        ))
    for item in ca_f:
        mp = int(item["map_id"], 16)
        par, _ = ctx.parent_and_size(mp)
        findings.append(_make_finding(
            rule_id="EDGE-001",
            category="edges",
            severity="ERROR",
            map_id=mp,
            parent_id=par,
            key_suffix=f"cache_{item['label']}_{item['kind']}",
            location=f"{item['label']} @{tuple(item['foot_tile'])}",
            message=f"Cached warp/boat landing {item['label']} on map 0x{mp:02X}: {item['kind']}.",
            fix_hint="Update Boat_Caches or SpecialSoaring_Caches landing coordinates onto walkable terrain.",
            details=item,
        ))

    # 2. Raw Sprite OOB + Embedded Ground Sprites (EDGE-002 / EDGE-003)
    seen_parents: set[int] = set()
    for m in sorted(selected):
        par, sz = ctx.parent_and_size(m)
        if par in seen_parents:
            continue
        seen_parents.add(par)
        _, _, agrid = ctx.area_grid(par)
        dim_h, dim_w = len(agrid), len(agrid[0])
        for ph in range(3):
            for idx, sp in enumerate(ctx.read_raw_sprites(par, ph)):
                sx, sy, sid = sp["x"], sp["y"], sp["sid"]
                rx, ry = sp["raw_x"], sp["raw_y"]
                if sx >= dim_w or sy >= dim_h or rx >= 64 or ry >= 64:
                    findings.append(_make_finding(
                        rule_id="EDGE-002",
                        category="edges",
                        severity="ERROR",
                        map_id=par,
                        parent_id=par,
                        key_suffix=f"sprite_oob_p{ph}_{idx}_0x{sid:02X}",
                        location=f"p{ph} ({sx},{sy}) raw=({rx},{ry}) sid=0x{sid:02X}",
                        message=f"Sprite 0x{sid:02X} ({ctx.sprite_name(sid)}) in phase {ph} is OOB for {dim_w}x{dim_h} area 0x{par:02X}.",
                        fix_hint=f"Move sprite inside 0..{dim_w - 1} x 0..{dim_h - 1} or remove stale vanilla leftover.",
                        details={"phase": ph, **sp, "dims": [dim_w, dim_h]},
                    ))
                    continue

                if sid in NON_GROUND_SPRITES:
                    continue
                phys = par + (8 if sy >= 32 else 0) + (1 if sx >= 32 else 0)
                if phys not in selected and par not in selected:
                    continue
                tid = agrid[sy][sx]
                tts = ctx.tile16_quadrant_types(phys, tid)
                qs = ctx.tile16_quadrant_classes(phys, tid)
                if all(q == "solid" for q in qs) and 0x27 not in tts:
                    findings.append(_make_finding(
                        rule_id="EDGE-003",
                        category="edges",
                        severity="WARN",
                        map_id=phys,
                        parent_id=par,
                        key_suffix=f"sprite_solid_p{ph}_{sx}_{sy}_0x{sid:02X}",
                        location=f"p{ph} ({sx},{sy}) sid=0x{sid:02X}",
                        message=f"Ground sprite 0x{sid:02X} ({ctx.sprite_name(sid)}) embedded inside solid Tile16 0x{tid:03X}.",
                        fix_hint="Relocate sprite onto walkable/water ground after terrain sculpting (see $0A/$11/$1C/$90 sprite cleanup).",
                        details={"phase": ph, "pos": [sx, sy], "sid": f"0x{sid:02X}", "tile16": f"0x{tid:03X}"},
                    ))

    # 3. Cut-off Door Pairs & Flush External-Seam Exits/Entrances (EDGE-004) + Entrance Framing (LAND-001)
    for m in sorted(selected):
        if m in NON_PLAYABLE_SW_PAGES:
            continue
        par, sz = ctx.parent_and_size(m)
        g = ctx.screen_grid(m)
        world_base = m & 0xC0
        local = m - world_base
        col, row = local % 8, local // 8
        ext_right = (col == 7) or (ctx.parent_and_size(m + 1)[0] != par)
        ext_left = (col == 0) or (ctx.parent_and_size(m - 1)[0] != par)
        ext_down = (row == 7) or (ctx.parent_and_size(m + 8)[0] != par)
        ext_up = (row == 0) or (ctx.parent_and_size(m - 8)[0] != par)

        for y in range(32):
            if ext_right and g[y][31] in DOOR_HALF_TILES:
                findings.append(_make_finding(
                    rule_id="EDGE-004",
                    category="edges",
                    severity="WARN",
                    map_id=m,
                    parent_id=par,
                    key_suffix=f"door_cut_E_{y}",
                    location=f"(31,{y}) tid=0x{g[y][31]:03X}",
                    message=f"Closed-door Tile16 0x{g[y][31]:03X} sits flush on East external seam of 0x{m:02X}.",
                    fix_hint="Shift building doorway >= 1 tile inward from external area boundary.",
                ))
            if ext_left and g[y][0] in DOOR_HALF_TILES:
                findings.append(_make_finding(
                    rule_id="EDGE-004",
                    category="edges",
                    severity="WARN",
                    map_id=m,
                    parent_id=par,
                    key_suffix=f"door_cut_W_{y}",
                    location=f"(0,{y}) tid=0x{g[y][0]:03X}",
                    message=f"Closed-door Tile16 0x{g[y][0]:03X} sits flush on West external seam of 0x{m:02X}.",
                    fix_hint="Shift building doorway >= 1 tile inward from external area boundary.",
                ))

        for ex in exits_by_map[m]:
            lx, ly = ex["lx"], ex["ly"]
            on_ext = (lx == 0 and ext_left) or (lx == 31 and ext_right) or (ly == 0 and ext_up) or (ly == 31 and ext_down)
            if on_ext:
                findings.append(_make_finding(
                    rule_id="EDGE-004",
                    category="edges",
                    severity="WARN",
                    map_id=m,
                    parent_id=par,
                    key_suffix=f"exit_seam_{ex['exit_id']:02X}",
                    location=f"exit 0x{ex['exit_id']:02X} ({lx},{ly})",
                    message=f"Exit 0x{ex['exit_id']:02X} lands directly on external seam tile ({lx},{ly}).",
                    fix_hint="Keep exit arrival tiles >= 1 tile inside external screen transition borders.",
                ))

        for ent in ents_by_map[m]:
            lx, ly = ent["lx"], ent["ly"]
            on_ext = (lx == 0 and ext_left) or (lx == 31 and ext_right) or (ly == 0 and ext_up) or (ly == 31 and ext_down)
            if on_ext:
                findings.append(_make_finding(
                    rule_id="EDGE-004",
                    category="edges",
                    severity="WARN",
                    map_id=m,
                    parent_id=par,
                    key_suffix=f"ent_seam_{ent['entrance_id']:02X}",
                    location=f"ent 0x{ent['entrance_id']:02X} ({lx},{ly})",
                    message=f"Entrance 0x{ent['entrance_id']:02X} sits flush on external seam tile ({lx},{ly}).",
                    fix_hint="Offset entrance trigger >= 1 tile inward from external screen transition edge.",
                ))

            # LAND-001: Check entrance doormat & framing
            if m in ctx.overlay_maps or par in ctx.overlay_maps:
                continue
            _, _, agrid = ctx.area_grid(par)
            cx, cy = ent["local_tile_x"], ent["local_tile_y"]
            h, w = len(agrid), len(agrid[0])
            if 0 <= cy < h and 0 <= cx < w:
                doormat = 0
                for dy in (1, 2):
                    for dx in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= ny < h and 0 <= nx < w:
                            p_sub = par + (8 if ny >= 32 else 0) + (1 if nx >= 32 else 0)
                            if ctx.tile16_summary_class(p_sub, agrid[ny][nx]) in ("walkable", "shallow_water"):
                                doormat += 1
                frame_solid = 0
                for dy in (-1, 0):
                    for dx in (-1, 0, 1):
                        nx, ny = cx + dx, cy + dy
                        if 0 <= ny < h and 0 <= nx < w:
                            p_sub = par + (8 if ny >= 32 else 0) + (1 if nx >= 32 else 0)
                            if ctx.tile16_summary_class(p_sub, agrid[ny][nx]) in ("solid", "deep_water", "ledge"):
                                frame_solid += 1
                if doormat == 0 or frame_solid == 0:
                    findings.append(_make_finding(
                        rule_id="LAND-001",
                        category="landmarks",
                        severity="WARN",
                        map_id=m,
                        parent_id=par,
                        key_suffix=f"ent_frame_{ent['entrance_id']:02X}",
                        location=f"ent 0x{ent['entrance_id']:02X} ({cx},{cy})",
                        message=f"Entrance 0x{ent['entrance_id']:02X} has weak framing (doormat={doormat}, backdrop={frame_solid}).",
                        fix_hint="Anchor entrance in a cliff face/building facade with >= 2 walkable doormat tiles south.",
                        details={"doormat": doormat, "frame_solid": frame_solid},
                    ))

    return findings


def _check_sprites_and_palettes(ctx: GrammarContext, selected: set[int]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    rep = cssc.scan_rom_sprite_compat(ctx.rom, root=ctx.root)

    for r in rep["ow_palette_oob"]:
        m = int(r["map_id"], 16)
        if m not in selected:
            continue
        findings.append(_make_finding(
            rule_id="SPR-001",
            category="sprites",
            severity="ERROR",
            map_id=m,
            parent_id=int(r["parent_id"], 16),
            key_suffix=f"pal_oob_p{r['phase']}",
            location=f"phase {r['phase']} spr_pal={r['spr_pal']}",
            message=f"Sprite palette {r['spr_pal']} in phase {r['phase']} is OOB (>= $14).",
            fix_hint="Assign valid sprite palette index $00-$13.",
            details=r,
        ))
    for r in rep["ow_invalid_sheet_fmt"]:
        m = int(r["map_id"], 16)
        if m not in selected:
            continue
        findings.append(_make_finding(
            rule_id="SPR-001",
            category="sprites",
            severity="ERROR",
            map_id=m,
            parent_id=int(r["parent_id"], 16),
            key_suffix=f"sheet_fmt_p{r['phase']}_s{r['slot']}",
            location=f"phase {r['phase']} slot {r['slot']} ({r['sheet']})",
            message=f"Spriteset {r['spr_gfx']} loads invalid sheet {r['sheet']} in OAM slot {r['slot']} ({r['reason']}).",
            fix_hint="Replace 2bpp/3bpp BG sheet in SpriteBlockset with a valid 3bpp sprite sheet.",
            details=r,
        ))
    for r in rep["ow_sheet_mismatches"]:
        m = int(r["map_id"], 16)
        if m not in selected:
            continue
        findings.append(_make_finding(
            rule_id="SPR-001",
            category="sprites",
            severity="ERROR",
            map_id=m,
            parent_id=int(r["parent_id"], 16),
            key_suffix=f"sheet_mm_p{r['phase']}_{r['sprite_id']}_{r['pos'][0]}_{r['pos'][1]}",
            location=f"phase {r['phase']} {tuple(r['pos'])} {r['sprite_id']}",
            message=f"Sprite {r['sprite_id']} ({r['sprite_name']}) needs slot {r['required_slot']} in {r['expected_sheets']}, got {r['loaded_sheet']}.",
            fix_hint=f"Switch phase {r['phase']} spr_gfx (currently {r['spr_gfx']}) to load {r['expected_sheets']} in slot {r['required_slot']}.",
            details=r,
        ))
    for r in rep["ow_water_terrain"]:
        m = int(r["map_id"], 16)
        if m not in selected:
            continue
        sev = "ERROR" if r["severity"] == "error" else "WARN"
        findings.append(_make_finding(
            rule_id="SPR-002",
            category="sprites",
            severity=sev,
            map_id=m,
            parent_id=int(r["parent_id"], 16),
            key_suffix=f"water_dry_p{r['phase']}_{r['sprite_id']}_{r['pos'][0]}_{r['pos'][1]}",
            location=f"phase {r['phase']} {tuple(r['pos'])} {r['sprite_id']}",
            message=f"Aquatic sprite {r['sprite_id']} ({r['sprite_name']}) placed on dry/non-water tile {r['tile16']} ({r['reason']}).",
            fix_hint="Move aquatic enemy onto deep/shallow water or swap to a land-compatible enemy.",
            details=r,
        ))
    for r in rep["ow_phase_palette_parity"]:
        m = int(r["map_id"], 16)
        if m not in selected:
            continue
        pp = r["phase_palettes"]
        findings.append(_make_finding(
            rule_id="SPR-003",
            category="sprites",
            severity="WARN",
            map_id=m,
            parent_id=int(r["parent_id"], 16),
            key_suffix=f"pal_drift_{r['kind']}",
            location=f"p0={pp['p0']} p1={pp['p1']} p2={pp['p2']}",
            message=f"{r['kind']} on map 0x{m:02X}: phase sprite palettes diverge ({pp['p0']}/{pp['p1']}/{pp['p2']}).",
            fix_hint="Align p0/p1/p2 spr_pal on shared NPCs/enemies so phase transitions do not corrupt CGRAM.",
            details=r,
        ))

    # SPR-004: Persistent NPC phase parity (p1 vs p2) & cross-world MainPal collision
    seen_parents: set[int] = set()
    main_pal_regions: dict[int, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for m in range(ctx.capacity):
        meta = ctx.area_metadata(m)
        region = "abyss" if m < 0x80 and m >= 0x40 else ("kalyxo" if m < 0x40 else "special")
        if m not in NON_PLAYABLE_SW_PAGES:
            main_pal_regions[meta["main_pal"]][region].append(m)

    for m in sorted(selected):
        par, _ = ctx.parent_and_size(m)
        if par not in seen_parents:
            seen_parents.add(par)
            p1 = Counter(s[2] for s in ctx.read_sprites(par, 1))
            p2 = Counter(s[2] for s in ctx.read_sprites(par, 2))
            for sid, name in sorted(PERSISTENT_NPC_SPRITES.items()):
                if p1.get(sid, 0) != p2.get(sid, 0):
                    findings.append(_make_finding(
                        rule_id="SPR-004",
                        category="sprites",
                        severity="WARN",
                        map_id=par,
                        parent_id=par,
                        key_suffix=f"npc_phase_parity_0x{sid:02X}",
                        location=f"p1={p1.get(sid, 0)} p2={p2.get(sid, 0)} sid=0x{sid:02X}",
                        message=f"Persistent NPC/vendor 0x{sid:02X} ({name}) differs between Day (p1={p1.get(sid, 0)}) and Night (p2={p2.get(sid, 0)}).",
                        fix_hint=f"Mirror 0x{sid:02X} ({name}) across both p1 Day and p2 Night sprite lists unless intentional.",
                        details={"sprite_id": f"0x{sid:02X}", "name": name, "p1": p1.get(sid, 0), "p2": p2.get(sid, 0)},
                    ))

        # Check cross-region/cross-biome MainPal collision (e.g. Sky using MainPal 1 shared with Abyss, or MainPal 5 shared with Courage)
        meta = ctx.area_metadata(m)
        mp = meta["main_pal"]
        reg_map = main_pal_regions[mp]
        if m >= 0x80 and m in SKY_ROUTE_MAPS and m not in NON_PLAYABLE_SW_PAGES:
            other_maps = [x for ms in reg_map.values() for x in ms if x not in SKY_ROUTE_MAPS]
            if other_maps:
                findings.append(_make_finding(
                    rule_id="SPR-004",
                    category="sprites",
                    severity="WARN",
                    map_id=m,
                    parent_id=par,
                    key_suffix=f"main_pal_collision_{mp:02X}",
                    location=f"main_pal=0x{mp:02X}",
                    message=f"MainPal 0x{mp:02X} on Sky map 0x{m:02X} collides with {len(other_maps)} non-Sky map(s) (e.g. 0x{other_maps[0]:02X}).",
                    fix_hint="Point Sky/Garrison maps to isolated Ext MainPal ($06/$07+) instead of overwriting shared MainPal 1/5.",
                    details={"main_pal": f"0x{mp:02X}", "colliding_sample": [f"0x{x:02X}" for x in other_maps[:8]]},
                ))
    return findings


def _check_affordances(ctx: GrammarContext, selected: set[int]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []

    # 1. INT-001: Magic Bean 2x2 Soil Pad & Vendor Parity
    for spot in _load_bean_spots(ctx.root):
        m = spot["map_id"]
        if m >= ctx.capacity:
            continue
        par, sz, agrid = ctx.area_grid(m)
        local_m = par & 0x3F
        hx = (spot["home_x"] - (local_m % 8) * 512) // 16
        hy = (spot["home_y"] - (local_m // 8) * 512) // 16
        phys = par + (8 if hy >= 32 else 0) + (1 if hx >= 32 else 0)
        if m not in selected and par not in selected and phys not in selected:
            continue

        # Phase parity for BeanVendor (0x07)
        p1_hits = [(sx, sy) for sx, sy, sid in ctx.read_sprites(par, 1) if sid == 0x07 and abs(sx - hx) <= 3 and abs(sy - hy) <= 3]
        p2_hits = [(sx, sy) for sx, sy, sid in ctx.read_sprites(par, 2) if sid == 0x07 and abs(sx - hx) <= 3 and abs(sy - hy) <= 3]
        if not p1_hits or not p2_hits:
            missing_ph = []
            if not p1_hits:
                missing_ph.append("p1 (Day)")
            if not p2_hits:
                missing_ph.append("p2 (Night)")
            findings.append(_make_finding(
                rule_id="INT-001",
                category="affordances",
                severity="ERROR",
                map_id=phys,
                parent_id=par,
                key_suffix=f"bean_spot{spot['index']}_vendor_missing",
                location=f"spot #{spot['index']} ({hx},{hy})",
                message=f"Magic Bean spot #{spot['index']} on 0x{phys:02X} ({hx},{hy}) is missing Sprite 0x07 (BeanVendor) in {' & '.join(missing_ph)}.",
                fix_hint="Place Sprite 0x07 in both p1 Day and p2 Night at the spot's home tile (or update MagicBeanSpot_* in bean_vendor.asm).",
                details={"spot": spot["index"], "home_tile": [hx, hy], "missing_phases": missing_ph},
            ))

        # Check 2x2 walkable soil pad containing (hx, hy) and bush/rock clutter around home tile
        h, w = len(agrid), len(agrid[0])
        has_clean_2x2 = False
        center_solid = True
        adjacent_clutter = 0
        if 0 <= hy < h and 0 <= hx < w:
            center_cls = ctx.tile16_summary_class(phys, agrid[hy][hx])
            center_solid = center_cls in ("solid", "deep_water")
            for dy in (-1, 0, 1):
                for dx in (-1, 0, 1):
                    nx, ny = hx + dx, hy + dy
                    if 0 <= ny < h and 0 <= nx < w:
                        p_sub = par + (8 if ny >= 32 else 0) + (1 if nx >= 32 else 0)
                        if ctx.tile16_summary_class(p_sub, agrid[ny][nx]) == "interactive":
                            adjacent_clutter += 1
            for ox, oy in ((-1, -1), (0, -1), (-1, 0), (0, 0)):
                ok = True
                for dy in (0, 1):
                    for dx in (0, 1):
                        nx, ny = hx + ox + dx, hy + oy + dy
                        if not (0 <= ny < h and 0 <= nx < w):
                            ok = False
                            break
                        p_sub = par + (8 if ny >= 32 else 0) + (1 if nx >= 32 else 0)
                        if ctx.tile16_summary_class(p_sub, agrid[ny][nx]) != "walkable":
                            ok = False
                            break
                    if not ok:
                        break
                if ok:
                    has_clean_2x2 = True
                    break
        if center_solid or not has_clean_2x2 or adjacent_clutter >= 2:
            findings.append(_make_finding(
                rule_id="INT-001",
                category="affordances",
                severity="ERROR" if center_solid else "WARN",
                map_id=phys,
                parent_id=par,
                key_suffix=f"bean_spot{spot['index']}_soil_pad",
                location=f"spot #{spot['index']} ({hx},{hy}) [parent 0x{par:02X}]",
                message=(
                    f"Magic Bean spot #{spot['index']} ({hx},{hy}) "
                    + (
                        "sits on blocked solid/water terrain."
                        if center_solid
                        else (
                            f"has {adjacent_clutter} adjacent bush/rock tile(s) cluttering its soil pad."
                            if adjacent_clutter >= 2
                            else "lacks an unobstructed 2x2 walkable soil/dirt pad."
                        )
                    )
                ),
                fix_hint="Sculpt a clean 2x2 walkable soil pad (0x3CD or 0x0C6) free of bushes/rocks at the bean spot (see Spot 0 on $00/$01).",
                details={"spot": spot["index"], "home_tile": [hx, hy], "center_solid": center_solid, "clutter": adjacent_clutter},
            ))

        # Check flight landing coordinate
        lx = (spot["home_x"] + spot["dx"] - (local_m % 8) * 512) // 16
        ly = (spot["home_y"] + spot["dy"] - (local_m // 8) * 512) // 16
        if not (0 <= ly < h and 0 <= lx < w):
            findings.append(_make_finding(
                rule_id="INT-001",
                category="affordances",
                severity="ERROR",
                map_id=phys,
                parent_id=par,
                key_suffix=f"bean_spot{spot['index']}_landing_oob",
                location=f"spot #{spot['index']} land=({lx},{ly})",
                message=f"Magic Bean spot #{spot['index']} flight lands OOB at ({lx},{ly}) outside {w}x{h} area.",
                fix_hint="Adjust MagicBean_LegXSpeed/YSpeed/Timers in bean_vendor.asm so flight lands on walkable terrace.",
            ))
        else:
            p_land = par + (8 if ly >= 32 else 0) + (1 if lx >= 32 else 0)
            l_cls = ctx.tile16_summary_class(p_land, agrid[ly][lx])
            if l_cls not in ("walkable", "shallow_water"):
                findings.append(_make_finding(
                    rule_id="INT-001",
                    category="affordances",
                    severity="WARN",
                    map_id=phys,
                    parent_id=par,
                    key_suffix=f"bean_spot{spot['index']}_landing_blocked",
                    location=f"spot #{spot['index']} land=({lx},{ly})",
                    message=f"Magic Bean spot #{spot['index']} flight landing ({lx},{ly}) hits {l_cls} tile 0x{agrid[ly][lx]:03X}.",
                    fix_hint="Verify flight velocity tables or clear landing spot to walkable ground.",
                ))

    # 2. INT-002: Directional Ledge Jump Landing Blocked
    ledge_dirs = {0x28: (0, -1), 0x29: (0, 1), 0x2A: (1, 0), 0x2B: (-1, 0)}
    for m in sorted(selected):
        if m in NON_PLAYABLE_SW_PAGES:
            continue
        par, _ = ctx.parent_and_size(m)
        g = ctx.screen_grid(m)
        cls = ctx.class_grid(m)
        bad_ledges: list[tuple[int, int, int]] = []
        for y in range(2, 29):
            for x in range(2, 29):
                tid = g[y][x]
                if tid in WATERFALL_TILE16_IDS:
                    continue
                tts = ctx.tile16_quadrant_types(m, tid)
                for tt, (dx, dy) in ledge_dirs.items():
                    if tt not in tts:
                        continue
                    entry_x, entry_y = x - dx, y - dy
                    if cls[entry_y][entry_x] not in ("walkable", "shallow_water"):
                        continue
                    # Tall ALTTP cliff walls can drop 2..8 tiles before hitting lower ground
                    dests = [
                        cls[y + dy * k][x + dx * k]
                        for k in range(1, 9)
                        if 0 <= x + dx * k < 32 and 0 <= y + dy * k < 32
                    ]
                    if len(dests) >= 4 and all(d == "solid" for d in dests):
                        bad_ledges.append((x, y, tid))
                        break
        if bad_ledges:
            bx, by, btid = bad_ledges[0]
            findings.append(_make_finding(
                rule_id="INT-002",
                category="affordances",
                severity="WARN",
                map_id=m,
                parent_id=par,
                key_suffix=f"ledge_blocked_{bx}_{by}",
                location=f"({bx},{by}) tid=0x{btid:03X} ({len(bad_ledges)} tiles)",
                message=f"{len(bad_ledges)} jumpable ledge tile(s) (first at ({bx},{by})) jump into >= 8 tiles of unbroken solid wall.",
                fix_hint="Clear a walkable/shallow landing zone past the cliff ledge face.",
                details={"count": len(bad_ledges), "sample": [[x, y, f"0x{t:03X}"] for x, y, t in bad_ledges[:6]]},
            ))

    return findings


def _step_same_world_tile(
    m: int, x: int, y: int, dx: int, dy: int, capacity: int
) -> tuple[int, int, int] | None:
    """Step 1 Tile16 cell across 8x8 world seams without leaving Kalyxo or playable Special OW."""
    nx, ny = x + dx, y + dy
    nm = m
    world_base = 0x00 if m < 0x40 else 0x80
    if nx < 0:
        if (m % 8) == 0:
            return None
        nm, nx = m - 1, 31
    elif nx >= 32:
        if (m % 8) == 7:
            return None
        nm, nx = m + 1, 0
    if ny < 0:
        if (m - world_base) < 8:
            return None
        nm, ny = m - 8, 31
    elif ny >= 32:
        if (m - world_base) >= 56:
            return None
        nm, ny = m + 8, 0
    if nm < 0 or nm >= capacity:
        return None
    if world_base == 0x00 and nm >= 0x40:
        return None
    if world_base == 0x80 and (nm < 0x80 or nm >= 0xC0 or nm in NON_PLAYABLE_SW_PAGES):
        return None
    return (nm, nx, ny)


def _check_stair_affordances(ctx: GrammarContext, selected: set[int]) -> list[dict[str, Any]]:
    """STAIR-001: Flag short cliff ladders (<= 2 Tile16s tall) that belong as biome stairs."""
    findings: list[dict[str, Any]] = []
    playable = sorted(
        m for m in selected
        if m < 0x40 or (0x80 <= m < 0xC0 and m not in NON_PLAYABLE_SW_PAGES)
    )
    if not playable:
        return findings

    visited: set[tuple[int, int, int]] = set()
    ladder_cache: dict[int, list[list[bool]]] = {}

    def is_ladder(cm: int, cx: int, cy: int) -> bool:
        grid_mask = ladder_cache.get(cm)
        if grid_mask is None:
            g = ctx.screen_grid(cm)
            grid_mask = [
                [
                    (tid in LADDER_TILE16_IDS and 0x22 in ctx.tile16_quadrant_types(cm, tid))
                    for tid in row
                ]
                for row in g
            ]
            ladder_cache[cm] = grid_mask
        return grid_mask[cy][cx]

    for m in playable:
        for y in range(32):
            for x in range(32):
                if (m, x, y) in visited or not is_ladder(m, x, y):
                    continue
                q: deque[tuple[int, int, int]] = deque([(m, x, y)])
                visited.add((m, x, y))
                comp: list[tuple[int, int, int]] = []
                while q:
                    cm, cx, cy = q.popleft()
                    comp.append((cm, cx, cy))
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        nxt = _step_same_world_tile(cm, cx, cy, dx, dy, ctx.capacity)
                        if nxt is not None and nxt not in visited and is_ladder(*nxt):
                            visited.add(nxt)
                            q.append(nxt)

                # Group by global world (wx, wy) across horizontal/vertical seams
                gpts = {
                    ((cm % 8) * 32 + cx, ((cm % 64) // 8) * 32 + cy): (cm, cx, cy)
                    for cm, cx, cy in comp
                }
                by_wx: dict[int, list[int]] = defaultdict(list)
                for wx, wy in gpts:
                    by_wx[wx].append(wy)

                max_run_height = 0
                has_passable_access = False
                for wx, wys in by_wx.items():
                    wys.sort()
                    run = 1
                    best_col = 1
                    for a, b in zip(wys, wys[1:]):
                        run = run + 1 if b == a + 1 else 1
                        if run > best_col:
                            best_col = run
                    if best_col > max_run_height:
                        max_run_height = best_col

                    tm, tx, ty = gpts[(wx, wys[0])]
                    bm, bx, by = gpts[(wx, wys[-1])]
                    for adj in (
                        _step_same_world_tile(tm, tx, ty, 0, -1, ctx.capacity),
                        _step_same_world_tile(bm, bx, by, 0, 1, ctx.capacity),
                    ):
                        if adj is not None:
                            am, ax, ay = adj
                            if ctx.class_grid(am)[ay][ax] in ("walkable", "shallow_water", "deep_water"):
                                has_passable_access = True

                if max_run_height > 2 or not has_passable_access:
                    continue

                min_wy = min(wy for _, wy in gpts)
                min_wx = min(wx for wx, wy in gpts if wy == min_wy)
                owner_m, x0, y0 = gpts[(min_wx, min_wy)]
                owner_par, _ = ctx.parent_and_size(owner_m)
                width = max(wx for wx, _ in gpts) - min(wx for wx, _ in gpts) + 1
                sample_tids = sorted({f"0x{ctx.screen_grid(cm)[cy][cx]:03X}" for cm, cx, cy in comp})
                findings.append(_make_finding(
                    rule_id="STAIR-001",
                    category="affordances",
                    severity="WARN",
                    map_id=owner_m,
                    parent_id=owner_par,
                    key_suffix=f"short_ladder_{x0}_{y0}",
                    location=f"({x0},{y0}) {width}x{max_run_height} ({len(comp)} tiles)",
                    message=(
                        f"Short cliff ladder ({width}w x {max_run_height}h, <= 2 tiles tall) "
                        f"should use biome-native stair steps instead of rung ladders."
                    ),
                    fix_hint=(
                        "Replace short <= 2-tile ladder runs with verified biome stair Tile16s "
                        "(keeping >= 3-tile tall cliff climbs)."
                    ),
                    details={
                        "width": width,
                        "height": max_run_height,
                        "tile_count": len(comp),
                        "tile16_ids": sample_tids,
                        "maps": sorted({f"0x{cm:02X}" for cm, _, _ in comp}),
                    },
                ))

    return findings


def classify_findings(findings: list[dict[str, Any]], baseline: dict[str, Any] | None) -> dict[str, Any]:
    ordered = sorted(findings, key=lambda item: (item["finding_key"], item["severity"]))
    if baseline is None:
        return {
            "findings": ordered,
            "new_findings": list(ordered),
            "baselined_findings": [],
            "resolved_findings": [],
        }
    prev = baseline.get("findings", [])
    known = {item["finding_key"] for item in prev if "finding_key" in item}
    have = {item["finding_key"] for item in ordered}
    return {
        "findings": ordered,
        "new_findings": [item for item in ordered if item["finding_key"] not in known],
        "baselined_findings": [item for item in ordered if item["finding_key"] in known],
        "resolved_findings": [item for item in prev if item.get("finding_key") not in have],
    }


def audit_overworld_grammar(
    rom: bytes,
    *,
    maps_spec: str = "all",
    min_severity: str = "INFO",
    rule_prefixes: set[str] | None = None,
    baseline: dict[str, Any] | None = None,
    rom_path: str | None = None,
    root: Path = ROOT,
) -> dict[str, Any]:
    """Run deterministic Scawful Overworld Design Grammar checks on ROM bytes."""
    ctx = GrammarContext(rom, root=root)
    selected = parse_map_spec(maps_spec, ctx.capacity)
    exits_by_map, ents_by_map = _collect_entities_by_map(ctx)

    raw_findings: list[dict[str, Any]] = []
    raw_findings.extend(_check_lanes_and_curves_and_props(ctx, selected, exits_by_map, ents_by_map))
    raw_findings.extend(_check_seams_and_attributes(ctx, selected))
    raw_findings.extend(_check_edges_and_landmarks(ctx, selected, exits_by_map, ents_by_map))
    raw_findings.extend(_check_sprites_and_palettes(ctx, selected))
    raw_findings.extend(_check_affordances(ctx, selected))
    raw_findings.extend(_check_stair_affordances(ctx, selected))

    min_rank = SEV_RANK[min_severity]
    filtered = []
    for f in raw_findings:
        if SEV_RANK[f["severity"]] < min_rank:
            continue
        if rule_prefixes:
            rid = f["rule_id"]
            if not any(rid == p or rid.startswith(p + "-") for p in rule_prefixes):
                continue
        filtered.append(f)

    classified = classify_findings(filtered, baseline)
    findings = classified["findings"]
    by_sev = Counter(f["severity"] for f in findings)
    by_rule = Counter(f["rule_id"] for f in findings)
    by_map = Counter(f["map_id"] for f in findings)

    return {
        "tool": TOOL_NAME,
        "schema_version": SCHEMA_VERSION,
        "rom_path": rom_path,
        "rom_sha256": sha256_bytes(rom),
        "maps_capacity": ctx.capacity,
        "maps_spec": maps_spec,
        "maps_checked": len(selected),
        "total_findings": len(findings),
        "error_count": by_sev["ERROR"],
        "warn_count": by_sev["WARN"],
        "info_count": by_sev["INFO"],
        "baselined_count": len(classified["baselined_findings"]),
        "new_count": len(classified["new_findings"]),
        "resolved_count": len(classified["resolved_findings"]),
        "counts_by_rule": dict(sorted(by_rule.items())),
        "top_hotspot_maps": [
            {"map_id": m, "label": ctx.map_label(int(m, 16)), "count": cnt}
            for m, cnt in by_map.most_common(15)
        ],
        "findings": findings,
        "new_findings": classified["new_findings"],
        "baselined_findings": classified["baselined_findings"],
        "resolved_findings": classified["resolved_findings"],
    }


def exit_code(report: dict[str, Any], *, baseline_set: bool, strict: bool) -> int:
    if baseline_set:
        failing = [
            f for f in report["new_findings"]
            if f["severity"] == "ERROR" or (strict and f["severity"] == "WARN")
        ]
        return 1 if failing else 0
    if strict:
        return 1 if (report["error_count"] or report["warn_count"]) else 0
    return 1 if report["error_count"] else 0


def format_text(report: dict[str, Any]) -> str:
    lines = [
        f"[*] {report['tool']} (maps={report['maps_spec']}, checked={report['maps_checked']}/{report['maps_capacity']}, sha256={report['rom_sha256'][:12]})",
        (
            f"    findings={report['total_findings']} "
            f"(ERROR={report['error_count']}, WARN={report['warn_count']}, INFO={report['info_count']}) | "
            f"new={report['new_count']} baselined={report['baselined_count']} resolved={report['resolved_count']}"
        ),
    ]
    if report["counts_by_rule"]:
        rules_str = ", ".join(f"{k}={v}" for k, v in sorted(report["counts_by_rule"].items()))
        lines.append(f"    by_rule: {rules_str}")
    if report["top_hotspot_maps"]:
        hot_str = ", ".join(f"{h['map_id']}({h['count']})" for h in report["top_hotspot_maps"][:8])
        lines.append(f"    top_hotspots: {hot_str}")
    to_show = report["new_findings"] if report["baselined_count"] > 0 else report["findings"]
    for item in to_show[:40]:
        lines.append(
            f"  [{item['severity']:5s}] {item['rule_id']} {item['map_id']} {item['location']}: "
            f"{item['message']} | Fix: {item['fix_hint']}"
        )
    if len(to_show) > 40:
        lines.append(f"  ... {len(to_show) - 40} additional findings (use --json / --out-json for full list)")
    return "\n".join(lines) + "\n"


def format_markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Scawful Overworld Design Grammar Report (`{report['maps_spec']}`)",
        "",
        f"- **ROM SHA-256:** `{report['rom_sha256'][:16]}...` ({report['maps_checked']}/{report['maps_capacity']} maps)",
        f"- **Findings:** {report['total_findings']} (`ERROR={report['error_count']}`, `WARN={report['warn_count']}`, `INFO={report['info_count']}`)",
        f"- **Ratchet:** new={report['new_count']}, baselined={report['baselined_count']}, resolved={report['resolved_count']}",
        "",
        "## Counts by Rule",
        "",
        "| Rule ID | Count |",
        "|---|---:|",
    ]
    for k, v in sorted(report["counts_by_rule"].items()):
        lines.append(f"| `{k}` | {v} |")
    lines += ["", "## Top Hotspot Maps", "", "| Map | Label | Findings |", "|---|---|---:|"]
    for h in report["top_hotspot_maps"]:
        lines.append(f"| `{h['map_id']}` | {h['label']} | {h['count']} |")
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path, help="Read-only path to SFC/SMC ROM")
    ap.add_argument("--maps", default="all", help="all, kalyxo, abyss, special, region preset, or hex IDs/ranges")
    ap.add_argument("--min-severity", choices=SEVERITIES, default="INFO", help="Minimum severity to emit")
    ap.add_argument("--rules", default="", help="Comma-separated rule IDs or prefixes (e.g. LANE,CURV,SEAM-001)")
    ap.add_argument("--baseline", type=Path, help="Prior baseline JSON report for ratchet comparison")
    ap.add_argument("--write-baseline", type=Path, help="Write JSON report snapshot as baseline")
    ap.add_argument("--json", action="store_true", help="Print JSON report to stdout")
    ap.add_argument("--out-json", type=Path, help="Write JSON report to file")
    ap.add_argument("--out-md", type=Path, help="Write Markdown report to file")
    ap.add_argument("--strict", action="store_true", help="Treat WARN findings as failures")
    args = ap.parse_args(argv)

    if not args.rom.is_file():
        print(f"{TOOL_NAME}: ROM not found: {args.rom}", file=sys.stderr)
        return 2

    try:
        rom = sic.load_rom_bytes(args.rom)
        baseline = json.loads(args.baseline.read_text(encoding="utf-8")) if args.baseline else None
        if baseline is not None and not isinstance(baseline, dict):
            raise ValueError("baseline JSON must be an object")
        rule_prefixes = {p.strip().upper() for p in args.rules.split(",") if p.strip()} or None
        report = audit_overworld_grammar(
            rom,
            maps_spec=args.maps,
            min_severity=args.min_severity,
            rule_prefixes=rule_prefixes,
            baseline=baseline,
            rom_path=str(args.rom),
            root=ROOT,
        )
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"{TOOL_NAME}: {exc}", file=sys.stderr)
        return 2

    payload = json.dumps(report, indent=2) + "\n"
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(payload, encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(format_markdown(report), encoding="utf-8")
    if args.write_baseline:
        args.write_baseline.parent.mkdir(parents=True, exist_ok=True)
        args.write_baseline.write_text(payload, encoding="utf-8")

    sys.stdout.write(payload if args.json else format_text(report))
    return exit_code(report, baseline_set=baseline is not None, strict=args.strict)


if __name__ == "__main__":
    raise SystemExit(main())
