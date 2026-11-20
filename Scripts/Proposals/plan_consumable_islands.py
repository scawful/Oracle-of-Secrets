#!/usr/bin/env python3
"""Read-only planner for dedicated consumable homes (track Q-OOS-06).

The script never writes a ROM. It checks a proposal catalog against one ROM
copy using z3ed for tile facts and Scripts/Build/check_sprite_sheet_compat.py
for sprite-sheet rules.

Engine fact this catalog is built around: overworld sprites have no subtype
byte. Sprite $52 (Sprites/Objects/collectible.asm) becomes Rock Meat only on
$5E/$B0/$B1/$B8/$B9, the intro sword on $58, and a Pineapple everywhere else.
Seashell is action 1 and is never selected at spawn. Banana, Honeycomb, and
Deku Stick have SRAM counts and menu handlers, not world sprites.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

import check_sprite_sheet_compat as cssc  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402

TRACK = "Q-OOS-06"
FORTRESS_MAPS = (0x4B, 0x4C, 0x53, 0x54)
# Maps where Collectible_IsRockMeatArea returns carry. $5E is Lupo Mountain.
# The selected route hides Meat on the Lyra Goron Coast and does not require Lupo.
ROCK_MEAT_CODE_MAPS = (0x5E, 0xB0, 0xB1, 0xB8, 0xB9)
ROCK_MEAT_HOME_MAPS = (0xB0, 0xB1, 0xB8, 0xB9)
LIVE_ROM_MARKERS = (
    Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"),
    ROOT / "Roms" / "oos168.sfc",
    ROOT / "Roms" / "oos168x.sfc",
)

SUPPLIES: dict[str, dict[str, Any]] = {
    "banana": {
        "label": "Banana",
        "sram": "0x7EF38B",
        "menu_use": "heal_two_hearts",
        "sprite_id": None,
    },
    "pineapple": {
        "label": "Pineapple",
        "sram": "0x7EF38D",
        "menu_use": "fill_magic",
        "sprite_id": "0x52",
    },
    "rock_meat": {
        "label": "Rock Meat",
        "sram": "0x7EF38F",
        "menu_use": "goron_trade_count",
        "sprite_id": "0x52",
    },
    "seashell": {
        "label": "Seashell",
        "sram": "0x7EF391",
        "menu_use": "collectible",
        "sprite_id": None,
    },
    "honeycomb": {
        "label": "Honeycomb",
        "sram": "0x7EF393",
        "menu_use": "bee_swarm",
        "sprite_id": None,
    },
    "deku_stick": {
        "label": "Deku Stick",
        "sram": "0x7EF395",
        "menu_use": "draw_torch",
        "sprite_id": None,
    },
    "bombchu": {
        "label": "Bombchu",
        "sram": "0x7EF3AD",
        "menu_use": "ammo",
        "sprite_id": None,
        "receipt_item": "0x4C",
    },
}

# Screen-local x/y are 0..31. area_x/area_y are parent-area tiles (0..63 on
# large areas). query_* is the z3ed overworld-tile-reference-inspect coordinate,
# which matches screen-local tiles on the screens checked for this catalog.
PLACEMENTS: list[dict[str, Any]] = [
    {
        "id": "banana_atoll_palm",
        "supply": "banana",
        "home": "Tiny Atoll banana palm",
        "map_id": 0xA5,
        "x": 16,
        "y": 16,
        "parent": 0xA5,
        "area_x": 16,
        "area_y": 16,
        "surface": "walk",
        "sprite_id": None,
        "method": "palm_harvest",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "King of Red Lions or swim. No Glove, Hammer, or Mitt.",
        "note": "Map $A4 stays the fairy/bug net minigame. Sprite $52 here would be a Pineapple.",
    },
    {
        "id": "banana_atoll_west",
        "supply": "banana",
        "home": "Tiny Atoll banana palm",
        "map_id": 0xA5,
        "x": 6,
        "y": 8,
        "parent": 0xA5,
        "area_x": 6,
        "area_y": 8,
        "surface": "walk",
        "sprite_id": None,
        "method": "palm_harvest",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "Same islet as the east palm. Two trees, one home.",
        "note": "Feeds Kiki on Tail Swamp $2F and the menu heal (+2 hearts).",
    },
    {
        "id": "pineapple_sandbar",
        "supply": "pineapple",
        "home": "Sunlit sandbar",
        "map_id": 0xB6,
        "x": 19,
        "y": 15,
        "parent": 0xB6,
        "area_x": 19,
        "area_y": 15,
        "surface": "walk",
        "sprite_id": 0x52,
        "method": "sprite_pickup",
        "requires": [],
        "forbids": ["enemy_drop", "hammer"],
        "access": "Open sandbar. Neighbor $B7 stays the digging minigame.",
        "note": "$B6 is not a Rock Meat map, so sprite $52 collects a Pineapple.",
    },
    {
        "id": "rock_meat_b0_interior",
        "supply": "rock_meat",
        "home": "Goron Coast boulders",
        "map_id": 0xB0,
        "x": 16,
        "y": 12,
        "parent": 0xB0,
        "area_x": 16,
        "area_y": 12,
        "surface": "walk",
        "sprite_id": 0x52,
        "method": "glove_lift",
        "requires": ["power_glove"],
        "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
        "access": "Basic Power Glove ($7EF354 != 0). Tan path beside the red channel.",
        "note": "The live phase-1 sprite sits at (21,11), on the red channel. This pin is the tan yard at (16,12). Nudge that sprite here when the map is edited.",
    },
    {
        "id": "rock_meat_b0_seam",
        "supply": "rock_meat",
        "home": "Goron Coast boulders",
        "map_id": 0xB0,
        "x": 5,
        "y": 19,
        "parent": 0xB0,
        "area_x": 5,
        "area_y": 19,
        "surface": "walk",
        "sprite_id": 0x52,
        "adopts_sprite": 0x52,
        "method": "glove_lift",
        "requires": ["power_glove"],
        "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
        "access": "West edge of $B0, beside the cross-world seam to Kalyxo $37.",
        "note": "Desert-seam Meat. Not on Lupo $5E and not on $B2.",
    },
    {
        "id": "rock_meat_b1",
        "supply": "rock_meat",
        "home": "Goron Coast boulders",
        "map_id": 0xB1,
        "x": 8,
        "y": 12,
        "parent": 0xB0,
        "area_x": 40,
        "area_y": 12,
        "surface": "walk",
        "sprite_id": 0x52,
        "adopts_sprite": 0x52,
        "method": "glove_lift",
        "requires": ["power_glove"],
        "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
        "access": "Northeast quadrant of the Goron Coast large area.",
        "note": "Existing $52. z3ed lists it on parent $B0 at area (40,12).",
    },
    {
        "id": "rock_meat_b8_seam",
        "supply": "rock_meat",
        "home": "Goron Coast boulders",
        "map_id": 0xB8,
        "x": 13,
        "y": 11,
        "parent": 0xB0,
        "area_x": 13,
        "area_y": 43,
        "surface": "walk",
        "sprite_id": 0x52,
        "adopts_sprite": 0x52,
        "method": "glove_lift",
        "requires": ["power_glove"],
        "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
        "access": "Southwest quadrant, beside the cross-world seam to Kalyxo $3F.",
        "note": "Existing $52.",
    },
    {
        "id": "rock_meat_b9",
        "supply": "rock_meat",
        "home": "Goron Coast boulders",
        "map_id": 0xB9,
        "x": 5,
        "y": 13,
        "parent": 0xB0,
        "area_x": 37,
        "area_y": 45,
        "surface": "walk",
        "sprite_id": 0x52,
        "adopts_sprite": 0x52,
        "method": "glove_lift",
        "requires": ["power_glove"],
        "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
        "access": "Southeast quadrant of the Goron Coast.",
        "note": "Existing $52. Fifth of the five-Meat Goron trade.",
    },
    {
        "id": "seashell_a2",
        "supply": "seashell",
        "home": "Tide-pool shallows",
        "map_id": 0xA2,
        "x": 25,
        "y": 15,
        "parent": 0xA2,
        "area_x": 25,
        "area_y": 15,
        "surface": "shore",
        "sprite_id": None,
        "method": "wade_or_shovel",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "Shallow edge. Flippers, Zora swim, Gust Jar, or shovel.",
        "note": "$A2 stays the open Sea Zora / Wisdom approach. This pin is the beach, not a new island quest.",
    },
    {
        "id": "seashell_9a",
        "supply": "seashell",
        "home": "Tide-pool shallows",
        "map_id": 0x9A,
        "x": 25,
        "y": 11,
        "parent": 0x9A,
        "area_x": 25,
        "area_y": 11,
        "surface": "shore",
        "sprite_id": None,
        "method": "wade_or_shovel",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "Zora reef shallows north of the $A2 channel.",
        "note": "Sprite $52 fails the sheet rule on this spriteset, so the shell is a place harvest.",
    },
    {
        "id": "seashell_92",
        "supply": "seashell",
        "home": "Tide-pool shallows",
        "map_id": 0x92,
        "x": 21,
        "y": 13,
        "parent": 0x92,
        "area_x": 21,
        "area_y": 13,
        "surface": "shallow",
        "sprite_id": None,
        "method": "wade_or_shovel",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "North reef shallow water.",
        "note": "Pure shallow tile. No new enemy.",
    },
    {
        "id": "seashell_ab",
        "supply": "seashell",
        "home": "Tide-pool shallows",
        "map_id": 0xAB,
        "x": 9,
        "y": 18,
        "parent": 0xAB,
        "area_x": 9,
        "area_y": 18,
        "surface": "shore",
        "sprite_id": None,
        "method": "wade_or_shovel",
        "requires": [],
        "forbids": ["sprite_52", "enemy_drop"],
        "access": "Hut Island beach. The chest-game house stays the minigame.",
        "note": "Sea spriteset $1B could draw $52, but $52 would be a Pineapple until a shell map-gate exists.",
    },
    {
        "id": "honey_glade_west",
        "supply": "honeycomb",
        "home": "Forest glade apiary",
        "map_id": 0x80,
        "x": 8,
        "y": 15,
        "parent": 0x80,
        "area_x": 8,
        "area_y": 15,
        "surface": "walk",
        "sprite_id": None,
        "method": "dash_shake_tree",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "Forest Glade meadow edge. Stand on open ground and shake the tree.",
        "note": "Korok Cove itself is dense. The wide meadow is $80, next to the cove.",
    },
    {
        "id": "honey_korok_lane",
        "supply": "honeycomb",
        "home": "Korok Cove apiary",
        "map_id": 0x81,
        "x": 2,
        "y": 26,
        "parent": 0x81,
        "area_x": 2,
        "area_y": 26,
        "surface": "walk",
        "sprite_id": None,
        "method": "dash_shake_tree",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "Existing west walk lane of Korok Cove. Shake the tree beside the lane.",
        "note": "Interior of $81/$89 has no open 0x00 meadow. Do not plant a blocking sprite in the lane.",
    },
    {
        "id": "stick_grove_a8",
        "supply": "deku_stick",
        "home": "Deku Grove thicket",
        "map_id": 0xA8,
        "x": 23,
        "y": 17,
        "parent": 0xA8,
        "area_x": 23,
        "area_y": 17,
        "surface": "walk",
        "sprite_id": None,
        "method": "thicket_harvest",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "Deku Grove west screen, off the scrub NPC tiles.",
        "note": "$A8/$A9 are scawful's Deku maps. This pin is a proposal, not a tile edit.",
    },
    {
        "id": "stick_grove_a9",
        "supply": "deku_stick",
        "home": "Deku Grove thicket",
        "map_id": 0xA9,
        "x": 14,
        "y": 8,
        "parent": 0xA8,
        "area_x": 46,
        "area_y": 8,
        "surface": "walk",
        "sprite_id": None,
        "method": "thicket_harvest",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "Deku Grove east screen of the wide $A8/$A9 area.",
        "note": "Walkable scrub edge. No sprite $52.",
    },
    {
        "id": "stick_swamp_2e",
        "supply": "deku_stick",
        "home": "Tail Swamp thicket",
        "map_id": 0x2E,
        "x": 24,
        "y": 24,
        "parent": 0x2E,
        "area_x": 24,
        "area_y": 24,
        "surface": "walk",
        "sprite_id": None,
        "method": "thicket_harvest",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "Tail Swamp refuge village screen. Off the Deku NPC at (25,22).",
        "note": "Matches the Tail Swamp refuge-village ruling. Sticks are a thicket, not a drop.",
    },
    {
        "id": "stick_swamp_2f",
        "supply": "deku_stick",
        "home": "Tail Swamp thicket",
        "map_id": 0x2F,
        "x": 22,
        "y": 14,
        "parent": 0x2F,
        "area_x": 22,
        "area_y": 14,
        "surface": "walk",
        "sprite_id": None,
        "method": "thicket_harvest",
        "requires": [],
        "forbids": ["enemy_drop"],
        "access": "South of Kiki (8,4)/(8,5). Kiki stays the banana consumer, not a stick drop.",
        "note": "Open walk tile beside scrub, not on the Kiki tile.",
    },
    {
        "id": "bombchu_sanctuary",
        "supply": "bombchu",
        "home": "Bombchu chest",
        "kind": "dungeon_chest",
        "room": 0x097,
        "item_id": 0x4C,
        "map_id": None,
        "x": None,
        "y": None,
        "surface": None,
        "sprite_id": None,
        "method": "chest",
        "requires": [],
        "forbids": ["enemy_drop", "fortress"],
        "access": "The only chest receipt $4C on this ROM. z3ed still titles the room with the vanilla Misery Mire name.",
        "note": "Decisions also mention room $D7 camera issues. This audit records the chest that is actually $4C.",
    },
    {
        "id": "bombchu_goron_outpost",
        "supply": "bombchu",
        "home": "Goron outpost vendor",
        "map_id": 0x3E,
        "x": 16,
        "y": 2,
        "parent": 0x36,
        "area_x": 16,
        "area_y": 34,
        "query_map": 0x36,
        "query_x": 16,
        "query_y": 34,
        "surface": "walk",
        "sprite_id": None,
        "adopts_sprite": 0xF2,
        "method": "vendor_refill",
        "requires": [],
        "forbids": ["enemy_drop", "hammer"],
        "access": "Existing Goron sprite $F2 on the Goron Mines large area. Refill vendor, not a new enemy.",
        "note": "Crescent Island keeps the Feather cup game. A camp vendor is option 2, not this pin.",
    },
]

OPTIONS: list[dict[str, str]] = [
    {
        "id": "A",
        "title": "Keep today's Meat sprites and harvest the other supplies in place",
        "pick": "recommended",
        "body": (
            "Leave the five Rock Meat sprites on Goron Coast $B0/$B1/$B8/$B9. "
            "They already ask for the basic Power Glove and do not ask for the Hammer, "
            "the Titan's Mitt, or a trip to Lupo. Put the one new Pineapple sprite on "
            "sandbar $B6. Banana palms, tide-pool shells, apiary trees, and Deku thickets "
            "are places the player harvests. They are not enemy drops and they do not reuse "
            "sprite $52. Bombchus stay the chest in room $097, with refills at the Goron "
            "who already stands on the mines area. Crescent Island keeps the Feather game."
        ),
    },
    {
        "id": "B",
        "title": "Teach sprite $52 a seashell map list",
        "pick": "later_asm",
        "body": (
            "Add a third result to Collectible_IsRockMeatArea's idea: on a short list of "
            "tide-pool maps, sprite $52 becomes a Seashell. Hut Island $AB already loads a "
            "sea spriteset that passes the $52 sheet rule. Reef maps $A2, $9A, and $92 do "
            "not, so they stay place-harvests until their sheets change. This is a small "
            "ASM follow-up. This commit does not include it."
        ),
    },
    {
        "id": "C",
        "title": "Give Banana, Seashell, Honeycomb, and Deku Stick their own sprites",
        "pick": "later_art",
        "body": (
            "New sprite IDs and silhouettes, one per supply, so a palm reads as a Banana "
            "and a thicket reads as a stick at island scale. This is the clearest map and "
            "the most new art. It is the right follow-up if option A feels too quiet in play. "
            "This commit does not add sprite IDs or graphics."
        ),
    },
]


def catalog_problems(placements: list[dict[str, Any]] | None = None) -> list[str]:
    """Static checks that do not need a ROM."""
    rows = PLACEMENTS if placements is None else placements
    problems: list[str] = []
    seen: set[str] = set()
    homes: dict[str, set[str]] = {}
    meat = 0
    for row in rows:
        ident = str(row.get("id", ""))
        if not ident or ident in seen:
            problems.append(f"bad id {ident!r}")
        seen.add(ident)
        supply = row.get("supply")
        if supply not in SUPPLIES:
            problems.append(f"{ident}: unknown supply {supply!r}")
            continue
        homes.setdefault(supply, set()).add(str(row.get("home")))
        kind = row.get("kind", "overworld")
        if kind == "dungeon_chest":
            room = row.get("room")
            if not isinstance(room, int) or not 0 <= room <= 0x127:
                problems.append(f"{ident}: room out of range")
            continue
        map_id = row.get("map_id")
        x, y = row.get("x"), row.get("y")
        if not isinstance(map_id, int) or not 0 <= map_id <= 0xBF:
            problems.append(f"{ident}: map out of range")
        if map_id in FORTRESS_MAPS or row.get("parent") in FORTRESS_MAPS:
            problems.append(f"{ident}: fortress map")
        if not isinstance(x, int) or not isinstance(y, int) or not (0 <= x <= 31 and 0 <= y <= 31):
            problems.append(f"{ident}: screen coordinate out of range")
        ax, ay = row.get("area_x"), row.get("area_y")
        if not isinstance(ax, int) or not isinstance(ay, int) or not (0 <= ax <= 63 and 0 <= ay <= 63):
            problems.append(f"{ident}: area coordinate out of range")
        if supply == "rock_meat":
            meat += 1
            if map_id not in ROCK_MEAT_HOME_MAPS:
                problems.append(f"{ident}: Rock Meat map {map_id:#x} is outside the Goron Coast home")
            if map_id == 0x5E or row.get("parent") == 0x5E:
                problems.append(f"{ident}: Lupo gate")
            if row.get("requires") != ["power_glove"]:
                problems.append(f"{ident}: Rock Meat must require only the basic Power Glove")
            for forbidden in ("hammer", "titans_mitt", "lupo"):
                if forbidden not in row.get("forbids", []):
                    problems.append(f"{ident}: missing forbid {forbidden}")
            if "hammer" in row.get("requires", []):
                problems.append(f"{ident}: Hammer gate")
            if row.get("sprite_id") != 0x52:
                problems.append(f"{ident}: Rock Meat pickup is sprite $52")
        if supply == "pineapple" and row.get("sprite_id") != 0x52:
            problems.append(f"{ident}: Pineapple home uses sprite $52")
        if supply == "pineapple" and map_id in ROCK_MEAT_CODE_MAPS:
            problems.append(f"{ident}: Pineapple placed on a Rock Meat map")
        if supply not in ("rock_meat", "pineapple") and row.get("sprite_id") == 0x52:
            problems.append(f"{ident}: sprite $52 would not be this supply")
        if "enemy_drop" not in row.get("forbids", []) and supply != "bombchu":
            problems.append(f"{ident}: missing enemy_drop forbid")
    for supply in SUPPLIES:
        if supply not in homes:
            problems.append(f"missing home for {supply}")
    if meat != 5:
        problems.append(f"Rock Meat spots: {meat}, expected 5")
    return problems


def assert_safe_rom(path: Path) -> None:
    resolved = path.resolve()
    for banned in LIVE_ROM_MARKERS:
        try:
            if resolved == banned.resolve():
                raise SystemExit(f"refusing live ROM {resolved}")
        except FileNotFoundError:
            continue
    if not resolved.is_file():
        raise SystemExit(f"ROM not found: {resolved}")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def z3ed_bin() -> str:
    local = Path.home() / ".local" / "bin" / "z3ed"
    if local.is_file():
        return str(local)
    return "z3ed"


def z3ed_json(args: list[str], rom: Path) -> dict[str, Any]:
    cmd = [z3ed_bin(), *args, f"--rom={rom}", "--format=json"]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    text = proc.stdout
    start = text.find("{")
    if proc.returncode != 0 or start < 0:
        tail = (proc.stderr or proc.stdout)[-500:]
        raise RuntimeError(f"z3ed failed ({proc.returncode}): {' '.join(args)}\n{tail}")
    payload = json.loads(text[start:])
    if not isinstance(payload, dict):
        raise RuntimeError(f"z3ed JSON was {type(payload).__name__}")
    return payload


def sprite_blockset(rom: bytes, map_id: int, phase: int = 1) -> tuple[int, int, list[int]]:
    """Same spriteset tables check_sprite_sheet_compat scans."""
    _capacity, native = ctp._native_table_addresses(rom)
    if map_id < 0xA0:
        parent = sic.area_parent_id(rom, map_id)
    else:
        parent = rom[native["parent"] + map_id]
    if parent < 0x40:
        blockset = rom[cssc.OW_SPR_GFX_PC + parent + phase * 0x40]
    elif parent < 0x80:
        blockset = rom[cssc.OW_SPR_GFX_PC + parent + 0x80]
    elif parent < 0xA0:
        blockset = rom[cssc.SW_SPR_GFX_PC + (parent - 0x80)]
    else:
        key = ("special_sprite_gfx", "special_sprite_gfx_phase1", "special_sprite_gfx_phase2")[phase]
        blockset = rom[native[key] + parent]
    return parent, blockset, cssc.decode_sprite_blockset(rom, blockset)


def surface_ok(types: list[int], kind: str) -> bool:
    if not types:
        return False
    if kind == "walk":
        return all(item == 0x00 for item in types)
    if kind == "shallow":
        return all(item in (0x08, 0x09) for item in types)
    if kind == "shore":
        return 0x00 in types and 0x09 in types and all(item in (0x00, 0x09) for item in types)
    return False


def _parse_tile(text: str) -> tuple[int, int]:
    body = text.strip().lstrip("(").rstrip(")")
    sx, sy = body.split(",")
    return int(sx), int(sy)


def _sprite_hits(sprites: list[dict[str, Any]], row: dict[str, Any]) -> list[dict[str, Any]]:
    hits = []
    for sprite in sprites:
        sx, sy = _parse_tile(sprite["tile"])
        smap = int(sprite["map_id"], 16)
        local = smap == row["map_id"] and (sx, sy) == (row["x"], row["y"])
        area = smap == row["parent"] and (sx, sy) == (row["area_x"], row["area_y"])
        if local or area:
            hits.append(sprite)
    return hits


def _hex_list(values: list[int]) -> list[str]:
    return [f"0x{item:02X}" for item in values]


def evaluate_placement(
    row: dict[str, Any],
    rom_bytes: bytes,
    rom_path: Path,
    sprites: list[dict[str, Any]],
    chests: list[dict[str, Any]],
) -> dict[str, Any]:
    out = {
        "id": row["id"],
        "supply": row["supply"],
        "home": row["home"],
        "method": row["method"],
        "requires": list(row.get("requires", [])),
        "forbids": list(row.get("forbids", [])),
        "access": row["access"],
        "note": row["note"],
        "sprite_id": None if row.get("sprite_id") is None else f"0x{row['sprite_id']:02X}",
        "problems": [],
    }
    if row.get("kind") == "dungeon_chest":
        out["room"] = f"0x{row['room']:03X}"
        out["item_id"] = f"0x{row['item_id']:02X}"
        found = [
            chest for chest in chests
            if int(chest["room"], 16) == row["room"] and int(chest["raw"], 16) == row["item_id"]
        ]
        out["chest_hits"] = len(found)
        if not found:
            out["problems"].append("receipt chest not in this ROM")
        out["status"] = "pass" if not out["problems"] else "fail"
        return out

    out["map_id"] = f"0x{row['map_id']:02X}"
    out["x"] = row["x"]
    out["y"] = row["y"]
    out["parent"] = f"0x{row['parent']:02X}"
    out["area_x"] = row["area_x"]
    out["area_y"] = row["area_y"]
    out["surface"] = row["surface"]
    qmap = row.get("query_map", row["map_id"])
    qx = row.get("query_x", row["x"])
    qy = row.get("query_y", row["y"])
    tile = z3ed_json(
        [
            "overworld-tile-reference-inspect",
            "--map", f"0x{qmap:02X}",
            "--x", str(qx),
            "--y", str(qy),
        ],
        rom_path,
    )["Overworld Tile Reference"]
    types = [int(quad["tile_type"], 16) for quad in tile["quadrants"]]
    out["tile16"] = tile.get("tile16")
    out["tile_types"] = _hex_list(types)
    if not surface_ok(types, row["surface"]):
        out["problems"].append(f"surface {row['surface']} does not match {_hex_list(types)}")

    parent, blockset, sheets = sprite_blockset(rom_bytes, row["map_id"], 1)
    if parent != row["parent"]:
        out["problems"].append(f"parent is 0x{parent:02X}, catalog says 0x{row['parent']:02X}")
    rule = None
    if row.get("sprite_id") is not None:
        rule = cssc._check_sprite_rule(row["sprite_id"], sheets, "ow", row["map_id"])
        if rule is not None:
            out["problems"].append(
                f"sprite ${row['sprite_id']:02X} sheet rule failed on slot {rule.get('required_slot')}"
            )
    out["spriteset"] = {
        "phase": 1,
        "blockset": f"0x{blockset:02X}",
        "sheets": _hex_list(sheets),
        "sheet_rule": "no_sprite" if row.get("sprite_id") is None else ("pass" if rule is None else "fail"),
    }
    hits = _sprite_hits(sprites, row)
    out["sprites_on_tile"] = [
        {"id": sprite["sprite_id"], "phase": sprite["phase"], "name": sprite["name"]}
        for sprite in hits
    ]
    adopted = row.get("adopts_sprite")
    if adopted is None and hits:
        out["problems"].append("tile already has a sprite")
    if adopted is not None:
        own = [sprite for sprite in hits if int(sprite["sprite_id"], 16) == adopted]
        other = [sprite for sprite in hits if int(sprite["sprite_id"], 16) != adopted]
        if not own:
            out["problems"].append(f"expected existing sprite ${adopted:02X} on this tile")
        if other:
            out["problems"].append("extra sprite shares this tile")
    out["status"] = "pass" if not out["problems"] else "fail"
    return out


def audit_sprites(sprites: list[dict[str, Any]]) -> dict[str, Any]:
    regions = {"kalyxo": 0, "abyss": 0, "lyra": 0}
    sprite_52 = []
    watch = {0x52: [], 0xA0: [], 0xB6: [], 0xF1: [], 0xF2: []}
    for sprite in sprites:
        mid = int(sprite["map_id"], 16)
        if mid < 0x40:
            regions["kalyxo"] += 1
        elif mid < 0x80:
            regions["abyss"] += 1
        else:
            regions["lyra"] += 1
        sid = int(sprite["sprite_id"], 16)
        if sid in watch:
            watch[sid].append(
                {
                    "map_id": sprite["map_id"],
                    "phase": sprite["phase"],
                    "tile": sprite["tile"],
                    "name": sprite["name"],
                }
            )
        if sid == 0x52:
            sprite_52.append(sprite)
    return {
        "overworld_sprite_count": len(sprites),
        "by_region": regions,
        "sprite_52": watch[0x52],
        "deku_scrub_a0": watch[0xA0],
        "kiki_b6": watch[0xB6],
        "korok_f1": watch[0xF1],
        "goron_f2": watch[0xF2],
        "note": (
            "z3ed still prints vanilla names. Sprite $52 is the collectible, "
            "sprite $F2 is the Goron, sprite $A0 is the Deku scrub NPC, "
            "and sprite $F1 is the Korok."
        ),
    }


def _world_origin(map_id: int) -> tuple[int, int]:
    if map_id >= 0x80:
        index = map_id - 0x80
    else:
        index = map_id
    return index & 7, (index >> 3) & 7


def _area_tile_size(rom: bytes, parent: int) -> tuple[int, int]:
    if parent < 0xA0 and sic.zs_version(rom) >= 3:
        code = rom[0x1788D + parent]
    elif parent >= 0xA0:
        _capacity, native = ctp._native_table_addresses(rom)
        code = rom[native["area_size"] + parent]
    else:
        code = 0
    if code == 1:
        return 64, 64
    if code == 2:
        return 64, 32
    if code == 3:
        return 32, 64
    return 32, 32


def render_map(
    rom_path: Path,
    rom_bytes: bytes,
    placements: list[dict[str, Any]],
    out_png: Path,
    scale: float = 0.5,
) -> None:
    from PIL import Image, ImageDraw, ImageFont

    screen_px = int(32 * 16 * scale)
    world = 8 * screen_px
    legend_w = 460
    header = 72
    canvas = Image.new("RGB", (world * 2 + 36 + legend_w, world + header + 28), (14, 18, 24))
    draw = ImageDraw.Draw(canvas)
    try:
        font = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 18)
        small = ImageFont.truetype("/System/Library/Fonts/Supplemental/Arial.ttf", 14)
    except OSError:
        font = ImageFont.load_default()
        small = font
    draw.text((24, 18), "Consumable homes  ·  Kalyxo $00-$3F", fill=(236, 232, 214), font=font)
    draw.text((24 + world + 36, 18), "Lyra Sea $80-$BF", fill=(236, 232, 214), font=font)

    def paint_world(first: int, origin_x: int) -> None:
        seen: set[int] = set()
        for map_id in range(first, first + 0x40):
            if map_id < 0xA0:
                parent = sic.area_parent_id(rom_bytes, map_id)
            else:
                _capacity, native = ctp._native_table_addresses(rom_bytes)
                parent = rom_bytes[native["parent"] + map_id]
            if parent != map_id or parent in seen:
                continue
            seen.add(parent)
            col, row = _world_origin(parent)
            tiles_w, tiles_h = _area_tile_size(rom_bytes, parent)
            box = (
                origin_x + col * screen_px,
                header + row * screen_px,
                origin_x + col * screen_px + int(tiles_w * 16 * scale),
                header + row * screen_px + int(tiles_h * 16 * scale),
            )
            tmp = out_png.parent / f".render_{parent:02X}.png"
            try:
                z3ed_json(
                    [
                        "overworld-render",
                        f"--screen=0x{parent:02X}",
                        f"--out={tmp}",
                        f"--scale={scale}",
                        "--area-overlay=off",
                    ],
                    rom_path,
                )
                shot = Image.open(tmp).convert("RGB")
                canvas.paste(shot, (box[0], box[1]))
            except Exception:
                draw.rectangle(box, fill=(48, 36, 56))
            finally:
                if tmp.exists():
                    tmp.unlink()
        for col in range(9):
            x = origin_x + col * screen_px
            draw.line((x, header, x, header + world), fill=(255, 255, 255), width=1)
        for row in range(9):
            y = header + row * screen_px
            draw.line((origin_x, y, origin_x + world, y), fill=(255, 255, 255), width=1)

    paint_world(0x00, 16)
    paint_world(0x80, 16 + world + 36)

    colors = {
        "banana": (196, 40, 196),
        "pineapple": (96, 48, 210),
        "rock_meat": (255, 255, 255),
        "seashell": (255, 220, 40),
        "honeycomb": (255, 90, 0),
        "deku_stick": (255, 40, 150),
        "bombchu": (255, 32, 32),
    }
    codes = {
        "banana": "BA",
        "pineapple": "PI",
        "rock_meat": "RM",
        "seashell": "SH",
        "honeycomb": "HO",
        "deku_stick": "DK",
        "bombchu": "CH",
    }
    legend_x = 16 + world * 2 + 52
    draw.text((legend_x, header), "Pins", fill=(236, 232, 214), font=font)
    legend_y = header + 36
    drawn: set[str] = set()
    for row in placements:
        if row.get("kind") == "dungeon_chest":
            continue
        supply = row["supply"]
        color = colors[supply]
        origin_x = 16 if row["map_id"] < 0x40 else 16 + world + 36
        col, grid_row = _world_origin(row["map_id"])
        px = origin_x + col * screen_px + int((row["x"] + 0.5) * 16 * scale)
        py = header + grid_row * screen_px + int((row["y"] + 0.5) * 16 * scale)
        radius = 7
        draw.ellipse((px - radius - 2, py - radius - 2, px + radius + 2, py + radius + 2), fill=(255, 255, 255))
        draw.ellipse((px - radius, py - radius, px + radius, py + radius), fill=color, outline=(12, 12, 16))
        draw.text((px + 10, py - 8), codes[supply], fill=(255, 255, 255), font=small)
        if supply not in drawn:
            drawn.add(supply)
            draw.ellipse((legend_x, legend_y, legend_x + 16, legend_y + 16), fill=color)
            draw.text((legend_x + 24, legend_y - 1), f"{codes[supply]}  {SUPPLIES[supply]['label']}", fill=(236, 232, 214), font=small)
            legend_y += 26
    draw.text((legend_x, legend_y + 12), "RM is the five existing", fill=(180, 176, 160), font=small)
    draw.text((legend_x, legend_y + 32), "Goron Coast boulders.", fill=(180, 176, 160), font=small)
    draw.text((legend_x, legend_y + 60), "Chest $4C is room $097,", fill=(180, 176, 160), font=small)
    draw.text((legend_x, legend_y + 80), "not an overworld pin.", fill=(180, 176, 160), font=small)
    canvas.save(out_png)


def design_markdown(manifest: dict[str, Any]) -> str:
    audit = manifest["audit"]
    lines = [
        "# Consumable islands design",
        "",
        f"Track {TRACK}. Read-only proposal against ROM `{manifest['rom_sha256']}`.",
        "No ASM, no tile edits, and no live ROM writes come from this document.",
        "",
        "## What the ROM does today",
        "",
        "The six SUPPLIES are Banana, Pineapple, Rock Meat, Seashell, Honeycomb, and Deku Stick.",
        "Menu A currently heals with Banana, fills magic with Pineapple, sends the bee swarm from a Honeycomb, and draws a Deku Stick. Rock Meat and Seashell are counts, not A-use items.",
        "",
        "Sprite `$52` is the only overworld collectible. On `$B0/$B1/$B8/$B9` and on Lupo `$5E` it is Rock Meat and it checks the basic Glove at `$7EF354`. On `$58` it is the intro sword. Everywhere else it is a Pineapple. There is no subtype byte, so a Banana sprite cannot share `$52`.",
        "",
        f"Overworld sprites on this copy: {audit['overworld_sprite_count']} "
        f"(Kalyxo {audit['by_region']['kalyxo']}, Abyss {audit['by_region']['abyss']}, "
        f"Lyra {audit['by_region']['lyra']}).",
        "",
        "Sprite `$52` placements z3ed reported:",
        "",
    ]
    for row in audit["sprite_52"]:
        lines.append(f"- map {row['map_id']} phase {row['phase']} tile {row['tile']} (vanilla name {row['name']})")
    lines += [
        "",
        "The five phase-1 sprites on parent `$B0` are the Meat this plan keeps. `$58` stays the sword. `$4D`, `$5B`, and `$65` currently behave as Pineapples because they are outside the Meat map list. This plan does not move them.",
        "",
        f"Bombchu receipt `$4C` chest hits in the dungeon find: {manifest['bombchu_chest_hits']}.",
        "Kiki (`$B6`) stands on Tail Swamp `$2F`. Koroks (`$F1`) stand on Korok Cove. Deku scrubs (`$A0`) stand on the grove and the swamp. The Goron (`$F2`) stands on the mines large area. None of those NPCs are turned into drop tables.",
        "",
        "Fortress screens `$4B/$4C/$53/$54` are not used. `$B2` is not a Meat map: sprite `$52` there would be a Pineapple, and the islet has little open ground. The landscape track owns tiles; these pins do not move them.",
        "",
        "## Recommended homes",
        "",
        "| Pin | Supply | Map | Tile | Sprite | Surface | Gate |",
        "|---|---|---|---|---|---|---|",
    ]
    for row in manifest["placements"]:
        if row.get("room"):
            where = row["room"]
            tile = "chest"
            surface = ""
        else:
            where = row["map_id"]
            tile = f"({row['x']},{row['y']})"
            surface = row["surface"]
        gate = ", ".join(row["requires"]) if row["requires"] else "none"
        lines.append(
            f"| {row['id']} | {row['supply']} | {where} | {tile} | {row['sprite_id'] or 'none'} | {surface} | {gate} |"
        )
    lines += [
        "",
        "## Checks on this ROM",
        "",
    ]
    for row in manifest["placements"]:
        sheet = row.get("spriteset", {})
        sheets = " ".join(sheet.get("sheets", []))
        problems = "; ".join(row["problems"]) if row["problems"] else "none"
        lines.append(
            f"- `{row['id']}` {row['status']}: tile {row.get('tile_types', [])} "
            f"sheets [{sheets}] rule {sheet.get('sheet_rule', 'n/a')}; problems: {problems}"
        )
    lines += [
        "",
        "## Decisions for scawful",
        "",
    ]
    for option in OPTIONS:
        mark = "Recommended. " if option["pick"] == "recommended" else ""
        lines.append(f"### {option['id']}. {option['title']}")
        lines.append("")
        lines.append(mark + option["body"])
        lines.append("")
    lines += [
        "Stray `$52` sprites on `$4D`, `$5B`, and `$65` should stay until you say whether sandbar `$B6` is the only Pineapple.",
        "",
        "Wide lanes stay as they are. The Korok honey pin stands on the existing west walk tile and shakes a tree beside it. It does not add a rock, a cactus, or a second sprite in that lane.",
        "",
    ]
    return "\n".join(lines)


def build(rom_path: Path, out_dir: Path, render: bool) -> dict[str, Any]:
    problems = catalog_problems()
    if problems:
        raise SystemExit("catalog rejected:\n" + "\n".join(problems))
    rom_bytes = rom_path.read_bytes()
    sprites = z3ed_json(["overworld-list-sprites"], rom_path)["Overworld Sprites"]["sprites"]
    chests = z3ed_json(["dungeon-find", "--item", "0x4C"], rom_path)["Dungeon Find"]["rows"]
    placements = [evaluate_placement(row, rom_bytes, rom_path, sprites, chests) for row in PLACEMENTS]
    failed = [row["id"] for row in placements if row["status"] != "pass"]
    manifest = {
        "track": TRACK,
        "rom_sha256": sha256_file(rom_path),
        "ok": not failed,
        "failed": failed,
        "supplies": list(SUPPLIES),
        "fortress_maps": [f"0x{item:02X}" for item in FORTRESS_MAPS],
        "rock_meat_rule": {
            "requires": ["power_glove"],
            "forbids": ["hammer", "titans_mitt", "lupo", "enemy_drop"],
            "home_maps": [f"0x{item:02X}" for item in ROCK_MEAT_HOME_MAPS],
            "code_also_accepts_lupo": "0x5E",
            "count": 5,
        },
        "audit": audit_sprites(sprites),
        "bombchu_chest_hits": sum(1 for row in chests if int(row["raw"], 16) == 0x4C),
        "placements": placements,
        "options": OPTIONS,
    }
    out_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = out_dir / "consumable_islands_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    design_path = out_dir / "CONSUMABLE_ISLANDS_DESIGN.md"
    design_path.write_text(design_markdown(manifest), encoding="utf-8")
    png_path = out_dir / "consumable_islands_map.png"
    if render:
        render_map(rom_path, rom_bytes, PLACEMENTS, png_path)
    manifest["manifest_path"] = str(manifest_path)
    manifest["design_path"] = str(design_path)
    if render:
        manifest["png_path"] = str(png_path)
    return manifest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Plan dedicated consumable islands against a ROM copy.")
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--no-render", action="store_true")
    args = parser.parse_args(argv)
    assert_safe_rom(args.rom)
    manifest = build(args.rom, args.out_dir, render=not args.no_render)
    print(
        f"{'PASS' if manifest['ok'] else 'FAIL'} "
        f"{len(manifest['placements'])} placements "
        f"sha {manifest['rom_sha256'][:12]} "
        f"manifest {manifest['manifest_path']}"
    )
    if manifest.get("png_path"):
        print(f"png {manifest['png_path']}")
    print(f"design {manifest['design_path']}")
    return 0 if manifest["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
