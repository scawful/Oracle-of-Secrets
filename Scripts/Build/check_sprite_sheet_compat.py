#!/usr/bin/env python3
"""Overworld (192-map, 3-phase) + Dungeon (296-room) Sprite-Sheet, Sprite-Palette,
and Water-Enemy Terrain Compatibility Auditor (Q329 + Retroid Playtest Guardrails).

Decodes:
  - All 192 overworld maps ($00-$BF, phases 0/1/2) including rev5 OOSOW192 tail maps ($A0-$BF)
  - All 296 dungeon rooms ($000-$127)
  - Loaded 4-sheet SpriteBlockset ($00DB57 -> global sheet = byte + $73) and sprite palette IDs

Checks:
  1. sprite_palette_oob        : OW sprite palette >= $14 (past 20-entry $0ED580 table)
  2. sprite_sheet_invalid_fmt  : SpriteBlockset loads 2bpp ($71-$72, $DA-$DF) or 3bpp BG (>= $E0) sheet
  3. sprite_sheet_mismatch     : Placed sprite's required OAM slot/sheets missing from loaded spriteset
                                 (covers vanilla ALTTP enemies/soldiers/dungeon foes + Oracle custom sprites)
  4. water_enemy_on_dry_land   : Water-only enemy ($55 FireBallZora, $56 WalkingZora, $81 Hover,
                                 $82 4Bubbles; plus warn for coastal $AE SeaUrchin) placed on non-water
                                 OverworldTileTypes across all 192 maps (all 3 phases)

Usage:
  python3 Scripts/Build/check_sprite_sheet_compat.py --rom <rom.sfc> [--out-json <p>] [--out-md <p>] [--strict]
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402

SPRITE_BLOCKSET_PC = 0x005B57  # $00:DB57 (4 bytes per spriteset; global = byte + $73 if nonzero)
OW_SPR_GFX_PC = 0x007A41       # LW ph0 (+0), LW ph1 (+$40), LW ph2 (+$80), DW (+$80 -> $7AC1..$7B00? Wait: +$80 for parent >= $40!)
OW_SPR_PAL_PC = 0x007B41
SW_SPR_GFX_PC = 0x0166E1       # $02:E6E1 ($80-$9F, 32B)
SW_SPR_PAL_PC = 0x016701       # $02:E701 ($80-$9F, 32B)
OW_SPR_PTRS_EXPANDED = (0x141438, 0x141578, 0x1416B8)
ROOMS_SPRITE_PTR_PC = 0x04C298

MAX_VALID_OW_SPR_PAL = 0x14    # $0ED580 table has 20 entries ($00-$13)
MAX_VALID_SPRITE_BLOCKSET = 0x90  # $00DB57 has 144 entries ($00-$8F)
INVALID_2BPP_SHEETS = {0x71, 0x72, 0xDA, 0xDB, 0xDC, 0xDD, 0xDE}
# Known custom 3bpp sprite sheets allocated in Bank $23 extended range ($DF-$FE)
# via Data/graphics/d4_zora_sprite_sheets.json (D4 Warden $DF-$E2, Refuge/Lyra Zora $E7).
# All other $DF-$FE sheets ($E3-$E6, $E8-$FE) are 3bpp BG sheets and invalid in OAM slots.
DEFAULT_CUSTOM_3BPP_SPRITE_SHEETS = {0xDF, 0xE0, 0xE1, 0xE2, 0xE7}
WATER_TILE_TYPES = {0x08, 0x09, 0x0C, 0x0D, 0x0E, 0x0F, 0x4A, 0x80}

# Water-only enemies (error if placed on non-water tile) & coastal enemies (warn)
WATER_ONLY_SPRITES: dict[int, str] = {
    0x55: "FireBallZora",
    0x56: "WalkingZora",
    0x81: "WaterBug_Hover",
    0x82: "FourBubbles",
}
COASTAL_WATER_SPRITES: dict[int, str] = {
    0xAE: "SeaUrchin",
}

# Verified Sprite -> Required (slot_index, allowed_global_sheets, label, scope)
# scope: "both", "ow", or "dungeon"
# Each rule checks ONLY the exact OAM VRAM slot (0..3 -> page 1 $00/$40/$80/$C0) that
# the sprite actually draws from, eliminating co-occurrence false positives.
SPRITE_SHEET_RULES: dict[int, dict[str, Any]] = {
    # --- Soldiers (Slot 1 MUST hold LW soldier sheet $BC or DW/Palace soldier sheet $80) ---
    0x41: {"name": "BlueSoldier",         "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x42: {"name": "GreenSoldier",        "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x43: {"name": "RedSpearSoldier",     "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x44: {"name": "BlueTrooper",         "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x47: {"name": "GreenGrassArcher",    "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x48: {"name": "RedSpearKnight",      "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x49: {"name": "RedGrassSpear",       "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x4A: {"name": "RedBombKnight",       "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    0x4B: {"name": "Knight",              "slot": 1, "sheets": {0x80, 0xBC}, "scope": "both"},
    # --- Overworld enemies with fixed single-slot sheets ---
    0x0E: {"name": "SnapDragon",          "slot": 2, "sheets": {0x8A},       "scope": "ow"},
    0x0F: {"name": "OctoBlimp",           "slot": 2, "sheets": {0x7F},       "scope": "ow"},
    0x4C: {"name": "Geldman",             "slot": 2, "sheets": {0x85},       "scope": "ow"},
    0x55: {"name": "FireBallZora",        "slot": 3, "sheets": {0x84, 0x87, 0x88, 0x8C, 0x8D, 0x8E, 0xC9}, "scope": "ow", "alt_slot": (2, {0x7F, 0x8B})},
    0x56: {"name": "WalkingZora",         "slot": 3, "sheets": {0x84, 0x87, 0x88, 0x8C, 0x8D, 0x8E, 0xC9}, "scope": "ow", "alt_slot": (2, {0x7F, 0x8B})},
    0x58: {"name": "Crab",                "slot": 3, "sheets": {0x84, 0x8C, 0xC9}, "scope": "ow", "alt_slot": (2, {0x7F})},
    0x71: {"name": "Leever",              "slot": 2, "sheets": {0x85, 0x8A, 0x8B, 0xA1}, "scope": "both"},
    # --- Dungeon enemies with verified fixed single-slot sheets ---
    0x09: {"name": "Moldorm",             "slot": 1, "sheets": {0x91},       "scope": "dungeon"},
    0x13: {"name": "MiniHelmasaur",       "slot": 0, "sheets": {0x92},       "scope": "dungeon"},
    0x18: {"name": "MiniMoldorm",         "slot": 0, "sheets": {0x92, 0x81}, "scope": "dungeon"},
    0x20: {"name": "Sluggula",            "slot": 2, "sheets": {0x98},       "scope": "dungeon"},
    0x24: {"name": "BlueBari",            "slot": 0, "sheets": {0x92},       "scope": "dungeon"},
    0x26: {"name": "HardhatBeetle",       "slot": 0, "sheets": {0x92},       "scope": "dungeon"},
    0x31: {"name": "FortuneTeller",       "slot": 0, "sheets": {0xBE, 0xC3}, "scope": "dungeon"},
    0x83: {"name": "GreenEyegore",        "slot": 1, "sheets": {0x9F, 0x91}, "scope": "dungeon"},
    0x84: {"name": "RedEyegore",          "slot": 1, "sheets": {0x9F, 0x91}, "scope": "dungeon"},
    0x8B: {"name": "Gibdo",               "slot": 2, "sheets": {0x96},       "scope": "dungeon"},
    0x8C: {"name": "Arrghus",             "slot": 2, "sheets": {0xAC},       "scope": "dungeon"},
    0x91: {"name": "StalfosKnight",       "slot": 2, "sheets": {0x99, 0x9A}, "scope": "dungeon"},
    # --- Oracle Custom Sprites (Sprites/registry.csv) ---
    0x14: {"name": "BusinessScrub",       "slot": 2, "sheets": {0xB8},       "scope": "ow"},
    0x25: {"name": "VillageDog",          "slot": 0, "sheets": {0x9E},       "scope": "ow"},
    0xB8: {"name": "SeaZora_ZoraPrincess","slot": 3, "sheets": {0xC9, 0xE7}, "scope": "both"},
    0xF1: {"name": "Korok",               "slot": 3, "sheets": {0xB7},       "scope": "ow"},
    0xA0: {"name": "DekuScrubNPC",        "slot": 0, "sheets": {0xA6, 0xBE, 0xB0}, "scope": "ow"},
    0x52: {"name": "Goron_ZoraKing",      "slot": 3, "sheets": {0xCF, 0x83, 0x8C, 0x8E, 0xB4, 0xB5}, "scope": "ow"},
    0x73: {"name": "Farore",              "slot": 3, "sheets": {0xB5, 0xC3}, "scope": "ow"},
    0x7B: {"name": "KydrogNPC",           "slot": 0, "sheets": {0xC4, 0xB3}, "scope": "ow"},
    0x9E: {"name": "MakuTree",            "slot": 2, "sheets": {0xC8},       "scope": "ow"},
    0xB2: {"name": "WindmillGuy",         "slot": 3, "sheets": {0xAB},       "scope": "dungeon"},
}

# Light World areas that switch to phase-0 peacetime sprite lists once their
# governing dungeon crystal is obtained (LoadPeacetimeSprites in Overworld/time_system.asm).
PEACETIME_OW_MAPS = {0x1E, 0x2E, 0x2F}


def load_custom_3bpp_sprite_sheets(root: Path = ROOT) -> set[int]:
    """Load extended ($DF-$FE) custom 3bpp sprite sheet IDs from Data/graphics/*.json."""
    sheets = set(DEFAULT_CUSTOM_3BPP_SPRITE_SHEETS)
    manifest = root / "Data" / "graphics" / "d4_zora_sprite_sheets.json"
    if manifest.exists():
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
            for entry in data.get("sheets", []):
                g = entry.get("global_sheet")
                src = entry.get("source", "")
                if g and src.startswith("d4_zora/"):
                    sheets.add(int(g, 16))
        except Exception:
            pass
    return sheets


def load_custom_sprite_names(root: Path = ROOT) -> dict[int, str]:
    out: dict[int, str] = {}
    csv_path = root / "Sprites" / "registry.csv"
    if not csv_path.exists():
        return out
    with csv_path.open(encoding="utf-8") as f:
        for row in csv.DictReader(f):
            try:
                sid = int(row["id"].lstrip("$"), 16)
            except Exception:
                continue
            out.setdefault(sid, row["name"])
    return out


def decode_sprite_blockset(rom: bytes, blockset_id: int) -> list[int]:
    off = SPRITE_BLOCKSET_PC + blockset_id * 4
    if off + 4 > len(rom):
        return [0, 0, 0, 0]
    raw = rom[off:off + 4]
    return [(b + 0x73) if b != 0 else 0 for b in raw]


def _check_sheet_format(sheets: list[int], custom_spr_sheets: set[int]) -> list[dict[str, Any]]:
    bad: list[dict[str, Any]] = []
    for slot, sid in enumerate(sheets):
        if sid == 0:
            continue
        if sid in INVALID_2BPP_SHEETS:
            bad.append({"slot": slot, "sheet": f"0x{sid:02X}", "reason": "2bpp_font_hud_sheet_in_sprite_slot"})
        elif sid >= 0xDF and sid not in custom_spr_sheets:
            bad.append({"slot": slot, "sheet": f"0x{sid:02X}", "reason": "3bpp_bg_or_unmapped_sheet_in_sprite_slot"})
    return bad


def _check_sprite_rule(
    sid: int,
    sheets: list[int],
    scope: str,
    context_id: int = -1,
) -> dict[str, Any] | None:
    # Context-aware dispatch for world-variant Oracle sprites:
    #   - 0x14 BusinessScrub (LW/SW: Slot 2 $B8) vs EonScrub (DW $40-$7F: Slot 0 $89)
    #   - 0x25 VillageDog    (LW/SW: Slot 0 $9E) vs EonDog   (DW $40-$7F: Slot 3 $8C)
    #   - 0xB8 SeaZora/Princess (LW/SW/Dungeon: Slot 3 $C9/$E7; DW: Slot 1 $CA; Room $46: Slot 3 $E2)
    if sid == 0x14 and scope == "ow":
        if 0x40 <= context_id < 0x80:
            slot, allowed, label = 0, {0x89}, "EonScrub"
        else:
            slot, allowed, label = 2, {0xB8}, "BusinessScrub"
        loaded = sheets[slot]
        if loaded in allowed:
            return None
        return {
            "sprite_id": f"0x{sid:02X}",
            "sprite_name": label,
            "required_slot": slot,
            "loaded_sheet": f"0x{loaded:02X}",
            "expected_sheets": [f"0x{x:02X}" for x in sorted(allowed)],
            "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
        }

    if sid == 0x25 and scope == "ow":
        if 0x40 <= context_id < 0x80:
            slot, allowed, label = 3, {0x8C}, "EonDog"
        else:
            slot, allowed, label = 0, {0x9E}, "VillageDog"
        loaded = sheets[slot]
        if loaded in allowed:
            return None
        return {
            "sprite_id": f"0x{sid:02X}",
            "sprite_name": label,
            "required_slot": slot,
            "loaded_sheet": f"0x{loaded:02X}",
            "expected_sheets": [f"0x{x:02X}" for x in sorted(allowed)],
            "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
        }

    if sid == 0xB8:
        if scope == "ow" and 0x40 <= context_id < 0x80:
            slot, allowed, label = 1, {0xCA}, "EonZora"
        elif scope == "dungeon" and context_id == 0x0046:
            slot, allowed, label = 3, {0xE2}, "D4Warden_ZoraProtector"
        else:
            slot, allowed, label = 3, {0xC9, 0xE7}, "SeaZora_ZoraPrincess"
        loaded = sheets[slot]
        if loaded in allowed:
            return None
        return {
            "sprite_id": f"0x{sid:02X}",
            "sprite_name": label,
            "required_slot": slot,
            "loaded_sheet": f"0x{loaded:02X}",
            "expected_sheets": [f"0x{x:02X}" for x in sorted(allowed)],
            "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
        }

    rule = SPRITE_SHEET_RULES.get(sid)
    if rule is None:
        return None
    if rule["scope"] != "both" and rule["scope"] != scope:
        return None
    slot = rule["slot"]
    allowed = rule["sheets"]
    loaded = sheets[slot]
    if loaded in allowed:
        return None
    alt = rule.get("alt_slot")
    if alt is not None:
        alt_slot, alt_allowed = alt
        if sheets[alt_slot] in alt_allowed:
            return None
    return {
        "sprite_id": f"0x{sid:02X}",
        "sprite_name": rule["name"],
        "required_slot": slot,
        "loaded_sheet": f"0x{loaded:02X}",
        "expected_sheets": [f"0x{x:02X}" for x in sorted(allowed)],
        "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
    }


def scan_rom_sprite_compat(rom: bytes, root: Path = ROOT) -> dict[str, Any]:
    """Run complete overworld (192 maps x 3 phases) + dungeon (296 rooms) audit."""
    custom_names = load_custom_sprite_names(root)
    custom_spr_sheets = load_custom_3bpp_sprite_sheets(root)
    capacity, native_tables = ctp._native_table_addresses(rom)
    tail_bank = native_tables.get("_tail_actor_bank", 0x4C)
    map32 = ctp.decode_map32_table(rom)
    tile16 = sic.decode_tile16_table(rom)
    ow_tt = list(rom[sic.PC_TILETYPE:sic.PC_TILETYPE + 0x200])

    # Pre-cache parent area grids for terrain checks
    area_grid_cache: dict[int, tuple[list[list[int]], int]] = {}

    def get_parent_and_grid(m: int) -> tuple[int, int, list[list[int]]]:
        if m < 0xA0:
            parent = sic.area_parent_id(rom, m)
            sz = rom[0x1788D + parent] if sic.zs_version(rom) >= 3 else 0
        else:
            parent = rom[native_tables["parent"] + m]
            sz = rom[native_tables["area_size"] + parent]
        if parent in area_grid_cache:
            g, cached_sz = area_grid_cache[parent]
            return parent, cached_sz, g
        nw = ctp.decode_map16_grid(rom, parent, map32, native_tables)
        if sz == 1:
            ne = ctp.decode_map16_grid(rom, parent + 1, map32, native_tables)
            sw = ctp.decode_map16_grid(rom, parent + 8, map32, native_tables)
            se = ctp.decode_map16_grid(rom, parent + 9, map32, native_tables)
            g = [nw[r] + ne[r] for r in range(32)] + [sw[r] + se[r] for r in range(32)]
        elif sz == 2:
            ne = ctp.decode_map16_grid(rom, parent + 1, map32, native_tables)
            g = [nw[r] + ne[r] for r in range(32)]
        elif sz == 3:
            sw = ctp.decode_map16_grid(rom, parent + 8, map32, native_tables)
            g = nw + sw
        else:
            g = nw
        area_grid_cache[parent] = (g, sz)
        return parent, sz, g

    def ow_spr_meta(m: int, parent: int, phase: int) -> tuple[int, int]:
        if parent < 0x40:
            sg = rom[OW_SPR_GFX_PC + parent + phase * 0x40]
            sp = rom[OW_SPR_PAL_PC + parent + phase * 0x40]
        elif parent < 0x80:
            sg = rom[OW_SPR_GFX_PC + parent + 0x80]
            sp = rom[OW_SPR_PAL_PC + parent + 0x80]
        elif parent < 0xA0:
            sg = rom[SW_SPR_GFX_PC + (parent - 0x80)]
            sp = rom[SW_SPR_PAL_PC + (parent - 0x80)]
        else:
            gk = ("special_sprite_gfx", "special_sprite_gfx_phase1", "special_sprite_gfx_phase2")[phase]
            pk = ("special_sprite_palettes", "special_sprite_palettes_phase1", "special_sprite_palettes_phase2")[phase]
            sg = rom[native_tables[gk] + parent]
            sp = rom[native_tables[pk] + parent]
        return sg, sp

    ow_palette_oob: list[dict[str, Any]] = []
    ow_invalid_sheet_fmt: list[dict[str, Any]] = []
    ow_sheet_mismatches: list[dict[str, Any]] = []
    ow_water_terrain: list[dict[str, Any]] = []
    ow_phase_palette_parity: list[dict[str, Any]] = []
    special_ow_table: list[dict[str, Any]] = []

    seen_pal_oob: set[tuple[int, int]] = set()
    seen_fmt: set[tuple[int, int, int]] = set()

    for m in range(capacity):
        parent, sz, grid = get_parent_and_grid(m)
        is_special = m >= 0x80
        sw_phases: dict[str, Any] = {}
        phase_sids: dict[int, set[int]] = {}
        phase_pal: dict[int, int] = {}

        for phase in range(3):
            sg, sp = ow_spr_meta(m, parent, phase)
            sheets = decode_sprite_blockset(rom, sg)
            phase_pal[phase] = sp

            # Check 1: Sprite palette OOB (>= $14)
            if sp >= MAX_VALID_OW_SPR_PAL and (m, phase) not in seen_pal_oob:
                seen_pal_oob.add((m, phase))
                ow_palette_oob.append({
                    "map_id": f"0x{m:02X}",
                    "parent_id": f"0x{parent:02X}",
                    "phase": phase,
                    "spr_pal": f"0x{sp:02X}",
                    "max_valid": f"0x{MAX_VALID_OW_SPR_PAL - 1:02X}",
                })

            # Check 2: Invalid 2bpp/3bpp sheet format or OOB spriteset index
            if sg >= MAX_VALID_SPRITE_BLOCKSET:
                fkey = (m, phase, -1)
                if fkey not in seen_fmt:
                    seen_fmt.add(fkey)
                    ow_invalid_sheet_fmt.append({
                        "map_id": f"0x{m:02X}",
                        "parent_id": f"0x{parent:02X}",
                        "phase": phase,
                        "spr_gfx": f"0x{sg:02X}",
                        "slot": -1,
                        "sheet": "OOB",
                        "reason": "sprite_blockset_index_oob",
                        "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
                    })
            for b in _check_sheet_format(sheets, custom_spr_sheets):
                fkey = (m, phase, b["slot"])
                if fkey not in seen_fmt:
                    seen_fmt.add(fkey)
                    ow_invalid_sheet_fmt.append({
                        "map_id": f"0x{m:02X}",
                        "parent_id": f"0x{parent:02X}",
                        "phase": phase,
                        "spr_gfx": f"0x{sg:02X}",
                        **b,
                        "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
                    })

            # Read sprite list for (m, phase)
            sprs: list[tuple[int, int, int]] = []
            if m < 0xA0:
                ptr = ctp.read_u16(rom, OW_SPR_PTRS_EXPANDED[phase] + m * 2)
                p = ctp.snes_to_pc(0x090000 | ptr)
            else:
                nt_key = ("sprite_phase0", "sprite_phase1", "sprite_phase2")[phase]
                ptr = ctp.read_u16(rom, native_tables[nt_key] + m * 2)
                p = ctp.snes_to_pc((tail_bank << 16) | ptr) if ptr >= 0x8000 else -1

            if p >= 0:
                while p + 2 < len(rom) and rom[p] != 0xFF and len(sprs) < 64:
                    sprs.append((rom[p] & 0x3F, rom[p + 1] & 0x3F, rom[p + 2]))
                    p += 3
            phase_sids[phase] = {s[2] for s in sprs}

            if is_special:
                sw_phases[f"p{phase}"] = {
                    "spr_gfx": f"0x{sg:02X}",
                    "sheets": [f"0x{x:02X}" for x in sheets],
                    "spr_pal": f"0x{sp:02X}",
                    "sprites": [f"0x{s[2]:02X}@({s[1]},{s[0]})" for s in sprs],
                }

            for sy, sx, sid in sprs:
                # Check 3: Sprite-to-sheet compatibility
                mm = _check_sprite_rule(sid, sheets, "ow", m)
                if mm is not None:
                    ow_sheet_mismatches.append({
                        "map_id": f"0x{m:02X}",
                        "parent_id": f"0x{parent:02X}",
                        "phase": phase,
                        "spr_gfx": f"0x{sg:02X}",
                        "pos": [sx, sy],
                        **mm,
                    })

                # Check 4: Water-enemy terrain compatibility
                if sid in WATER_ONLY_SPRITES or sid in COASTAL_WATER_SPRITES:
                    is_strict_water = sid in WATER_ONLY_SPRITES
                    name = WATER_ONLY_SPRITES.get(sid) or COASTAL_WATER_SPRITES[sid]
                    if 0 <= sy < len(grid) and 0 <= sx < len(grid[0]):
                        tid = grid[sy][sx]
                        tts = [ow_tt[w & 0x1FF] for w in tile16[tid]]
                        if not any(t in WATER_TILE_TYPES for t in tts):
                            ow_water_terrain.append({
                                "severity": "error" if is_strict_water else "warn",
                                "map_id": f"0x{m:02X}",
                                "parent_id": f"0x{parent:02X}",
                                "area_size": sz,
                                "phase": phase,
                                "sprite_id": f"0x{sid:02X}",
                                "sprite_name": name,
                                "pos": [sx, sy],
                                "tile16": f"0x{tid:03X}",
                                "tile_types": [f"0x{t:02X}" for t in tts],
                                "reason": "placed_on_dry_land",
                            })
                    else:
                        ow_water_terrain.append({
                            "severity": "error",
                            "map_id": f"0x{m:02X}",
                            "parent_id": f"0x{parent:02X}",
                            "area_size": sz,
                            "phase": phase,
                            "sprite_id": f"0x{sid:02X}",
                            "sprite_name": name,
                            "pos": [sx, sy],
                            "tile16": "OOB",
                            "tile_types": [],
                            "reason": f"coords_oob_for_grid_{len(grid[0])}x{len(grid)}",
                        })

        # Check 5 (advisory): Day/Night/Peacetime sprite-palette parity audit
        all_sids = sorted({sid for s in phase_sids.values() for sid in s})
        shared_diffs: list[dict[str, Any]] = []
        for sid in all_sids:
            ph_pals = {ph: phase_pal[ph] for ph in range(3) if sid in phase_sids.get(ph, ())}
            if len(set(ph_pals.values())) > 1:
                sname = (
                    custom_names.get(sid)
                    or (SPRITE_SHEET_RULES[sid]["name"] if sid in SPRITE_SHEET_RULES else f"Spr_0x{sid:02X}")
                )
                shared_diffs.append({
                    "sprite_id": f"0x{sid:02X}",
                    "sprite_name": sname,
                    "phase_palettes": {f"p{ph}": f"0x{pal:02X}" for ph, pal in sorted(ph_pals.items())},
                })
        if shared_diffs:
            ow_phase_palette_parity.append({
                "severity": "warn",
                "kind": "multi_phase_sprite_pal_drift",
                "map_id": f"0x{m:02X}",
                "parent_id": f"0x{parent:02X}",
                "is_peacetime_map": m in PEACETIME_OW_MAPS,
                "phase_palettes": {f"p{ph}": f"0x{phase_pal[ph]:02X}" for ph in range(3)},
                "sprites": shared_diffs,
            })
        elif m in PEACETIME_OW_MAPS and phase_sids.get(0) and (
            phase_pal[0] != phase_pal[1] or phase_pal[0] != phase_pal[2]
        ):
            p0_list = []
            for sid in sorted(phase_sids[0]):
                sname = (
                    custom_names.get(sid)
                    or (SPRITE_SHEET_RULES[sid]["name"] if sid in SPRITE_SHEET_RULES else f"Spr_0x{sid:02X}")
                )
                p0_list.append({
                    "sprite_id": f"0x{sid:02X}",
                    "sprite_name": sname,
                    "phase_palettes": {"p0": f"0x{phase_pal[0]:02X}"},
                })
            ow_phase_palette_parity.append({
                "severity": "warn",
                "kind": "peacetime_pal_divergence",
                "map_id": f"0x{m:02X}",
                "parent_id": f"0x{parent:02X}",
                "is_peacetime_map": True,
                "phase_palettes": {f"p{ph}": f"0x{phase_pal[ph]:02X}" for ph in range(3)},
                "sprites": p0_list,
            })

        if is_special:
            if m < 0xA0:
                main_pal = rom[sic.PC_ZS_MAIN_PAL_ARR + m]
                pal_set = rom[0x4C635 + m]
                bg_col = ctp.read_u16(rom, sic.PC_ZS_CUSTOM_BG_PAL + m * 2)
                music_b = rom[0x14403 + (m - 0x40)]
            else:
                main_pal = rom[native_tables["main_palette"] + m]
                pal_set = rom[native_tables["palette_set"] + m]
                bg_col = ctp.read_u16(rom, native_tables["bg_color"] + m * 2)
                music_b = rom[native_tables["music_phase1"] + m]
            special_ow_table.append({
                "map_id": f"0x{m:02X}",
                "parent_id": f"0x{parent:02X}",
                "area_size": sz,
                "main_pal": f"0x{main_pal:02X}",
                "pal_set": f"0x{pal_set:02X}",
                "bg_color": f"0x{bg_col:04X}",
                "music_rom": f"0x{music_b:02X}",
                **sw_phases,
            })

    # --- Dungeon Rooms ($000-$127) ---
    dun_invalid_sheet_fmt: list[dict[str, Any]] = []
    dun_sheet_mismatches: list[dict[str, Any]] = []
    spr_tbl_pc = ctp.snes_to_pc(0x090000 | ctp.read_u16(rom, ROOMS_SPRITE_PTR_PC))

    for room_id in range(296):
        rh = sic.read_room_header(rom, room_id)
        if not rh:
            continue
        ss = rh["spriteset"]
        # WindmillGuy_HeaderSpriteset ($01:B647 in Sprites/NPCs/windmill_guy.asm)
        # keeps $0AA3 = $22 for Room $00C9 when header spriteset == $22 so slot 3
        # loads Sheet $38 (global $AB, spr38.txt) instead of UW $62 (Sheet $41).
        effective_ss = ss if (room_id == 0x00C9 and ss == 0x22) else (ss + 0x40)
        sheets = decode_sprite_blockset(rom, effective_ss)
        for b in _check_sheet_format(sheets, custom_spr_sheets):
            dun_invalid_sheet_fmt.append({
                "room_id": f"0x{room_id:04X}",
                "spriteset": f"0x{ss:02X}",
                **b,
                "all_loaded_sheets": [f"0x{x:02X}" for x in sheets],
            })
        ptr = ctp.read_u16(rom, spr_tbl_pc + room_id * 2)
        p = ctp.snes_to_pc(0x090000 | ptr) + 1  # skip sort byte
        seen_in_room = 0
        while p + 2 < len(rom) and rom[p] != 0xFF and seen_in_room < 64:
            b0, b1, sid = rom[p], rom[p + 1], rom[p + 2]
            sy, sx = b0 & 0x1F, b1 & 0x1F
            seen_in_room += 1
            p += 3
            if sid in custom_names and sid not in SPRITE_SHEET_RULES:
                continue
            mm = _check_sprite_rule(sid, sheets, "dungeon", room_id)
            if mm is not None:
                dun_sheet_mismatches.append({
                    "room_id": f"0x{room_id:04X}",
                    "spriteset": f"0x{ss:02X}",
                    "blockset": rh["blockset"],
                    "palette": rh["palette"],
                    "pos": [sx, sy],
                    **mm,
                })

    return {
        "overworld_maps_scanned": capacity,
        "dungeon_rooms_scanned": 296,
        "summary": {
            "ow_palette_oob": len(ow_palette_oob),
            "ow_invalid_sheet_fmt": len(ow_invalid_sheet_fmt),
            "ow_sheet_mismatches": len(ow_sheet_mismatches),
            "ow_water_terrain_errors": sum(1 for x in ow_water_terrain if x["severity"] == "error"),
            "ow_water_terrain_warns": sum(1 for x in ow_water_terrain if x["severity"] == "warn"),
            "ow_phase_palette_parity_warns": len(ow_phase_palette_parity),
            "dungeon_invalid_sheet_fmt": len(dun_invalid_sheet_fmt),
            "dungeon_sheet_mismatches": len(dun_sheet_mismatches),
        },
        "ow_palette_oob": ow_palette_oob,
        "ow_invalid_sheet_fmt": ow_invalid_sheet_fmt,
        "ow_sheet_mismatches": ow_sheet_mismatches,
        "ow_water_terrain": ow_water_terrain,
        "ow_phase_palette_parity": ow_phase_palette_parity,
        "dungeon_invalid_sheet_fmt": dun_invalid_sheet_fmt,
        "dungeon_sheet_mismatches": dun_sheet_mismatches,
        "special_ow_audit": special_ow_table,
    }


def format_markdown(report: dict[str, Any]) -> str:
    s = report["summary"]
    lines = [
        "# Sprite-Sheet, Sprite-Palette & Terrain Compatibility Audit",
        "",
        f"- **Overworld maps scanned:** {report['overworld_maps_scanned']} (all 3 phases)",
        f"- **Dungeon rooms scanned:** {report['dungeon_rooms_scanned']}",
        f"- **OW Sprite Palette OOB (`>= $14`):** {s['ow_palette_oob']}",
        f"- **OW Invalid Sprite Sheet Format (2bpp/3bpp):** {s['ow_invalid_sheet_fmt']}",
        f"- **OW Sprite-Sheet Mismatches:** {s['ow_sheet_mismatches']}",
        f"- **OW Water Enemies on Dry Land:** {s['ow_water_terrain_errors']} errors, {s['ow_water_terrain_warns']} coastal warns",
        f"- **OW Day/Night/Peacetime Palette Parity:** {s['ow_phase_palette_parity_warns']} warns",
        f"- **Dungeon Invalid Sprite Sheet Format:** {s['dungeon_invalid_sheet_fmt']}",
        f"- **Dungeon Sprite-Sheet Mismatches:** {s['dungeon_sheet_mismatches']}",
        "",
    ]

    if report["ow_palette_oob"]:
        lines += ["## Overworld Out-of-Bounds Sprite Palettes (`>= $14`)", "", "| Map | Parent | Phase | SprPal |", "|---|---|---|---|"]
        seen = set()
        for r in report["ow_palette_oob"]:
            key = (r["map_id"], r["spr_pal"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"| `{r['map_id']}` | `{r['parent_id']}` | {r['phase']} | `{r['spr_pal']}` |")
        lines.append("")

    if report["ow_invalid_sheet_fmt"]:
        lines += ["## Overworld Invalid Sprite Sheet Formats (2bpp / 3bpp)", "", "| Map | Phase | SprGfx | Slot | Sheet | Reason |", "|---|---|---|---|---|---|"]
        seen = set()
        for r in report["ow_invalid_sheet_fmt"]:
            key = (r["map_id"], r["spr_gfx"], r["slot"], r["sheet"])
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"| `{r['map_id']}` | {r['phase']} | `{r['spr_gfx']}` | {r['slot']} | `{r['sheet']}` | {r['reason']} |")
        lines.append("")

    if report["ow_sheet_mismatches"]:
        lines += ["## Overworld Sprite-Sheet Mismatches", "", "| Map | Phase | Pos | Sprite | SprGfx | Slot | Loaded | Expected |", "|---|---|---|---|---|---|---|---|"]
        for r in report["ow_sheet_mismatches"]:
            lines.append(
                f"| `{r['map_id']}` | {r['phase']} | ({r['pos'][0]},{r['pos'][1]}) | "
                f"`{r['sprite_id']}` ({r['sprite_name']}) | `{r['spr_gfx']}` | {r['required_slot']} | "
                f"`{r['loaded_sheet']}` | `{'/'.join(r['expected_sheets'])}` |"
            )
        lines.append("")

    if report["ow_water_terrain"]:
        lines += ["## Water Enemies on Dry Land / OOB", "", "| Severity | Map | Phase | Pos | Sprite | Tile16 | TileTypes | Reason |", "|---|---|---|---|---|---|---|---|"]
        for r in report["ow_water_terrain"]:
            lines.append(
                f"| {r['severity'].upper()} | `{r['map_id']}` | {r['phase']} | ({r['pos'][0]},{r['pos'][1]}) | "
                f"`{r['sprite_id']}` ({r['sprite_name']}) | `{r['tile16']}` | `{','.join(r['tile_types'])}` | {r['reason']} |"
            )
        lines.append("")

    if report.get("ow_phase_palette_parity"):
        lines += [
            "## Day/Night/Peacetime Sprite-Palette Parity Warnings",
            "",
            "| Map | Kind | p0 Pal | p1 (Day) Pal | p2 (Night) Pal | Affected Sprites |",
            "|---|---|---|---|---|---|",
        ]
        for r in report["ow_phase_palette_parity"]:
            pp = r["phase_palettes"]
            spr_txt = ", ".join(f"`{x['sprite_id']}` ({x['sprite_name']})" for x in r["sprites"])
            lines.append(
                f"| `{r['map_id']}` | {r['kind']} | `{pp['p0']}` | `{pp['p1']}` | `{pp['p2']}` | {spr_txt} |"
            )
        lines.append("")

    if report["dungeon_sheet_mismatches"]:
        lines += ["## Dungeon Sprite-Sheet Mismatches", "", "| Room | Spriteset | Pos | Sprite | Slot | Loaded | Expected |", "|---|---|---|---|---|---|---|"]
        for r in report["dungeon_sheet_mismatches"]:
            lines.append(
                f"| `{r['room_id']}` | `{r['spriteset']}` | ({r['pos'][0]},{r['pos'][1]}) | "
                f"`{r['sprite_id']}` ({r['sprite_name']}) | {r['required_slot']} | "
                f"`{r['loaded_sheet']}` | `{'/'.join(r['expected_sheets'])}` |"
            )
        lines.append("")

    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--out-json", type=Path, help="write full JSON audit report")
    ap.add_argument("--out-md", type=Path, help="write Markdown audit report")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any error finding exists")
    args = ap.parse_args(argv)

    rom = args.rom.read_bytes()
    report = scan_rom_sprite_compat(rom)

    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    if args.out_md:
        args.out_md.parent.mkdir(parents=True, exist_ok=True)
        args.out_md.write_text(format_markdown(report), encoding="utf-8")

    s = report["summary"]
    print(
        f"[*] Scanned {report['overworld_maps_scanned']} OW maps (3 phases) + "
        f"{report['dungeon_rooms_scanned']} dungeon rooms:"
    )
    print(f"    OW sprite palette OOB (>= $14) : {s['ow_palette_oob']}")
    print(f"    OW invalid sprite sheet format : {s['ow_invalid_sheet_fmt']}")
    print(f"    OW sprite-sheet mismatches     : {s['ow_sheet_mismatches']}")
    print(f"    OW water enemies on dry land   : {s['ow_water_terrain_errors']} errors, {s['ow_water_terrain_warns']} warns")
    print(f"    OW day/night/peace pal parity  : {s['ow_phase_palette_parity_warns']} warns")
    print(f"    Dungeon invalid sheet format   : {s['dungeon_invalid_sheet_fmt']}")
    print(f"    Dungeon sprite-sheet mismatches: {s['dungeon_sheet_mismatches']}")

    if args.strict:
        errs = (
            s["ow_palette_oob"]
            + s["ow_invalid_sheet_fmt"]
            + s["ow_sheet_mismatches"]
            + s["ow_water_terrain_errors"]
            + s["dungeon_invalid_sheet_fmt"]
            + s["dungeon_sheet_mismatches"]
        )
        return 1 if errs else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
