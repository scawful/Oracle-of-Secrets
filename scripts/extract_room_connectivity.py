#!/usr/bin/env python3
"""Extract room connectivity data (stairs, holewarps, doors) from ALTTP ROM.

Reads room headers to extract stair destinations and holewarp targets,
then cross-references with dungeon room lists to build connectivity graph.

Usage:
    python3 scripts/extract_room_connectivity.py --rom Roms/oos168.sfc
    python3 scripts/extract_room_connectivity.py --rom Roms/oos168.sfc --format json
"""

import argparse
import json
import struct
import sys
from pathlib import Path


def snes_to_pc(addr):
    """Convert SNES LoROM address to PC file offset."""
    bank = (addr >> 16) & 0xFF
    offset = addr & 0xFFFF
    if bank < 0x80:
        return (bank * 0x8000) + (offset - 0x8000)
    else:
        return ((bank - 0x80) * 0x8000) + (offset - 0x8000)


def get_room_header_location(rom, room_id):
    """Get the PC offset of a room's 14-byte header."""
    # Read the 3-byte pointer at 0xB5DD (PC address)
    ptr_pc = snes_to_pc(0x04F1E0)  # Known header pointer table in bank $04

    # The header pointer table is a list of 2-byte offsets, one per room
    # Bank byte for all headers
    bank_addr = snes_to_pc(0x04F1E0)

    # Actually, based on yaze code:
    # kRoomHeaderPointer = 0xB5DD (this is a PC address in the ROM)
    # kRoomHeaderPointerBank = 0xB5E7
    # Let's read the base pointer
    base_ptr = rom[0xB5DD] | (rom[0xB5DE] << 8) | (rom[0xB5DF] << 16)
    base_pc = snes_to_pc(base_ptr)

    bank = rom[0xB5E7]

    # Each room has a 2-byte entry in the pointer table
    table_offset = base_pc + (room_id * 2)
    room_ptr = (bank << 16) | (rom[table_offset + 1] << 8) | rom[table_offset]

    return snes_to_pc(room_ptr)


def extract_room_header(rom, room_id):
    """Extract the 14-byte room header for a given room ID."""
    try:
        loc = get_room_header_location(rom, room_id)
    except (IndexError, ValueError):
        return None

    if loc < 0 or loc + 14 > len(rom):
        return None

    return {
        "room_id": room_id,
        "bg2_collision": rom[loc],
        "palette": rom[loc + 1] & 0x3F,
        "blockset": rom[loc + 2],
        "spriteset": rom[loc + 3],
        "effect": rom[loc + 4],
        "tag1": rom[loc + 5],
        "tag2": rom[loc + 6],
        "stair_planes_0_2": rom[loc + 7],
        "stair_plane_3": rom[loc + 8],
        "holewarp": rom[loc + 9],
        "staircase_rooms": [
            rom[loc + 10],
            rom[loc + 11],
            rom[loc + 12],
            rom[loc + 13],
        ],
    }


def load_dungeon_registry(path):
    """Load dungeons.json."""
    with open(path) as f:
        return json.load(f)


def get_all_dungeon_rooms(registry):
    """Get a set of all room IDs that belong to any dungeon."""
    rooms = {}
    for dungeon in registry["dungeons"]:
        for room in dungeon["rooms"]:
            rid = int(room["id"], 16)
            rooms[rid] = {
                "dungeon_id": dungeon["id"],
                "dungeon_name": dungeon["name"],
                "name": room["name"],
            }
    return rooms


def classify_room_type(room_name, room_id, entrance_rooms, dungeon_id):
    """Classify a room as entrance/boss/mini_boss/connector/normal."""
    name_lower = room_name.lower()

    # Check if it's an entrance from overworld
    if room_id in entrance_rooms:
        return "entrance"

    # Boss rooms
    if "[boss]" in name_lower or "(boss)" in name_lower or "boss" in name_lower:
        return "boss"

    # Mini-boss rooms
    mini_boss_keywords = [
        "lanmolas mini",
        "mini-boss",
        "miniboss",
        "armos knights",
    ]
    if any(kw in name_lower for kw in mini_boss_keywords):
        return "mini_boss"

    # Connector rooms (small transition rooms)
    if name_lower in ("connector",) or room_name == "Connector":
        return "connector"

    return "normal"


def find_entrance_rooms(csv_path, dungeon_rooms):
    """Parse the Rooms and Entrances CSV to find which rooms have overworld entrances."""
    entrance_rooms = {}  # room_id -> [entrance_info, ...]

    if not csv_path.exists():
        return entrance_rooms

    with open(csv_path) as f:
        lines = f.readlines()

    for line in lines[1:]:  # Skip header
        parts = line.strip().split(",")
        if len(parts) < 4:
            continue

        entrance_id_str = parts[0].strip()
        room_name = parts[1].strip()
        world = parts[2].strip()
        ow_area = parts[3].strip()

        if not entrance_id_str or not room_name:
            continue

        try:
            entrance_id = int(entrance_id_str, 16)
        except ValueError:
            continue

        # Match entrance room names to dungeon room IDs
        for rid, info in dungeon_rooms.items():
            if info["name"].lower() in room_name.lower() or room_name.lower() in info["name"].lower():
                if rid not in entrance_rooms:
                    entrance_rooms[rid] = []
                entrance_rooms[rid].append({
                    "entrance_id": entrance_id,
                    "name": room_name,
                    "world": world,
                    "overworld_area": ow_area,
                })

    return entrance_rooms


def compute_door_connections(dungeon_rooms_list):
    """Compute valid door connections between grid-adjacent rooms in same dungeon.

    Two rooms are door-connected if they differ by exactly 1 in grid position
    (horizontally or vertically, not diagonally).
    """
    doors = []
    room_set = {int(r["id"], 16): r for r in dungeon_rooms_list}
    room_ids = sorted(room_set.keys())

    for i, rid_a in enumerate(room_ids):
        for rid_b in room_ids[i + 1 :]:
            ra = room_set[rid_a]
            rb = room_set[rid_b]
            row_a, col_a = ra["grid_row"], ra["grid_col"]
            row_b, col_b = rb["grid_row"], rb["grid_col"]

            dr = abs(row_a - row_b)
            dc = abs(col_a - col_b)

            if dr + dc == 1:  # Exactly one step apart
                if dr == 1:
                    direction = "south" if row_b > row_a else "north"
                else:
                    direction = "east" if col_b > col_a else "west"

                doors.append({
                    "from": ra["id"],
                    "to": rb["id"],
                    "direction": direction,
                })

    return doors


def build_stair_connections(rom, dungeon_rooms_list, all_dungeon_rooms):
    """Build stair connections for rooms in a dungeon by reading ROM headers."""
    stairs = []
    seen = set()

    for room in dungeon_rooms_list:
        rid = int(room["id"], 16)
        header = extract_room_header(rom, rid)
        if not header:
            continue

        for slot, dest in enumerate(header["staircase_rooms"]):
            if dest == 0 or dest == rid:
                continue

            # Create a canonical pair to avoid duplicates
            pair = tuple(sorted([rid, dest]))
            if pair in seen:
                continue
            seen.add(pair)

            # Determine if destination is in same dungeon or outside
            dest_hex = f"0x{dest:02X}"
            from_hex = room["id"]

            dest_info = all_dungeon_rooms.get(dest)
            from_info = all_dungeon_rooms.get(rid)

            if dest_info and from_info and dest_info["dungeon_id"] == from_info["dungeon_id"]:
                dest_name = dest_info["name"]
                from_name = from_info["name"]
                stairs.append({
                    "from": from_hex,
                    "to": dest_hex,
                    "label": f"{from_name} ↔ {dest_name}",
                })

    return stairs


def build_holewarp_connections(rom, dungeon_rooms_list, all_dungeon_rooms):
    """Build holewarp connections for rooms in a dungeon."""
    holewarps = []

    for room in dungeon_rooms_list:
        rid = int(room["id"], 16)
        header = extract_room_header(rom, rid)
        if not header:
            continue

        dest = header["holewarp"]
        if dest == 0 or dest == rid:
            continue

        dest_hex = f"0x{dest:02X}"
        from_hex = room["id"]

        dest_info = all_dungeon_rooms.get(dest)
        from_info = all_dungeon_rooms.get(rid)

        if dest_info and from_info and dest_info["dungeon_id"] == from_info["dungeon_id"]:
            holewarps.append({
                "from": from_hex,
                "to": dest_hex,
                "label": f"{from_info['name']} → {dest_info['name']}",
            })

    return holewarps


# Known entrance room IDs per dungeon (from data sheet analysis)
ENTRANCE_ROOMS = {
    "D1": [0x4A],       # Mushroom Grotto Entrance
    "D2": [0x0E],       # Tail Palace Entrance
    "D3": [0x59, 0x56], # Kalyxo Castle entrances
    "D4": [0x28],       # Zora Temple Entrance
    "D5": [0xDB, 0xCB, 0xCC, 0xDC],  # Glacia Estate (4 entrances)
    "D6": [0x98, 0xC9], # Goron Mines (Main + Lower)
    "D7": [0xD6],       # Dragon Ship Entrance
    "FOS": [0x0C],      # Fortress of Secrets Entrance
    "SOP": [0x84, 0x83, 0x85, 0x86],  # Shrine of Power (4 entrances)
    "SOW": [0x9A],      # Shrine of Wisdom
}

# Known boss room IDs per dungeon
BOSS_ROOMS = {
    "D1": [0x5A],  # Helmasaur King
    "D2": [0xDE],  # Kholdstare
    "D3": [0x29],  # Mothula
    "D4": [0x06],  # Arrghus
    "D5": [0xAC],  # Blind the Thief
    "D6": [0x90, 0xC8],  # Vitreous + Armos Knights
    "D7": [0xA4],  # Trinexx
    "FOS": [0x0D], # Agahnim2
    "SOP": [0x33], # Lanmolas
    "SOW": [],     # No boss
}

# Known mini-boss rooms
MINI_BOSS_ROOMS = {
    "D6": [0x78],  # Lanmolas Mini-boss
}


def main():
    parser = argparse.ArgumentParser(description="Extract room connectivity from ALTTP ROM")
    parser.add_argument("--rom", required=True, help="Path to ROM file")
    parser.add_argument("--registry", default="Docs/Dev/Planning/dungeons.json",
                       help="Path to dungeons.json")
    parser.add_argument("--format", choices=["json", "text"], default="text")
    parser.add_argument("--output", help="Output file (default: stdout)")
    args = parser.parse_args()

    rom_path = Path(args.rom)
    if not rom_path.exists():
        print(f"ROM not found: {rom_path}", file=sys.stderr)
        sys.exit(1)

    rom = rom_path.read_bytes()
    registry = load_dungeon_registry(args.registry)
    all_dungeon_rooms = get_all_dungeon_rooms(registry)

    csv_path = Path("Docs/Technical/Sheets/Oracle of Secrets Data Sheet - Rooms and Entrances.csv")

    result = {
        "_meta": {
            "generated_by": "extract_room_connectivity.py",
            "rom": str(rom_path),
            "description": "Room connectivity data extracted from ROM headers",
        },
        "dungeons": [],
    }

    for dungeon in registry["dungeons"]:
        did = dungeon["id"]
        rooms_enriched = []

        for room in dungeon["rooms"]:
            rid = int(room["id"], 16)
            header = extract_room_header(rom, rid)

            # Determine room type
            if rid in BOSS_ROOMS.get(did, []):
                rtype = "boss"
            elif rid in MINI_BOSS_ROOMS.get(did, []):
                rtype = "mini_boss"
            elif rid in ENTRANCE_ROOMS.get(did, []):
                rtype = "entrance"
            elif room["name"].lower() == "connector":
                rtype = "connector"
            else:
                rtype = "normal"

            room_entry = {
                "id": room["id"],
                "name": room["name"],
                "grid_row": room["grid_row"],
                "grid_col": room["grid_col"],
                "type": rtype,
            }

            if header:
                room_entry["palette"] = header["palette"]
                room_entry["blockset"] = header["blockset"]
                room_entry["spriteset"] = header["spriteset"]
                room_entry["tag1"] = header["tag1"]
                room_entry["tag2"] = header["tag2"]

            rooms_enriched.append(room_entry)

        # Build connections
        stairs = build_stair_connections(rom, dungeon["rooms"], all_dungeon_rooms)
        holewarps = build_holewarp_connections(rom, dungeon["rooms"], all_dungeon_rooms)
        doors = compute_door_connections(dungeon["rooms"])

        dungeon_entry = {
            "id": did,
            "name": dungeon["name"],
            "vanilla_name": dungeon["vanilla_name"],
            "crystal_bit": dungeon.get("crystal_bit"),
            "rooms": rooms_enriched,
            "stairs": stairs,
            "holewarps": holewarps,
            "doors": doors,
            "features": dungeon.get("features", {}),
        }

        result["dungeons"].append(dungeon_entry)

    if args.format == "json":
        output = json.dumps(result, indent=2)
    else:
        output = format_text(result)

    if args.output:
        Path(args.output).write_text(output)
        print(f"Written to {args.output}")
    else:
        print(output)


def format_text(result):
    """Format connectivity data as human-readable text."""
    lines = []
    for dungeon in result["dungeons"]:
        lines.append(f"\n{'='*60}")
        lines.append(f"{dungeon['id']} {dungeon['name']} ({len(dungeon['rooms'])} rooms)")
        lines.append(f"{'='*60}")

        lines.append("\nRooms:")
        for room in dungeon["rooms"]:
            rtype = f" [{room['type']}]" if room["type"] != "normal" else ""
            lines.append(f"  {room['id']} {room['name']}{rtype}  (row={room['grid_row']}, col={room['grid_col']})")

        if dungeon["stairs"]:
            lines.append(f"\nStairs ({len(dungeon['stairs'])}):")
            for s in dungeon["stairs"]:
                lines.append(f"  {s['from']} ↔ {s['to']}  ({s['label']})")

        if dungeon["holewarps"]:
            lines.append(f"\nHolewarps ({len(dungeon['holewarps'])}):")
            for h in dungeon["holewarps"]:
                lines.append(f"  {h['from']} → {h['to']}  ({h['label']})")

        if dungeon["doors"]:
            lines.append(f"\nDoor connections ({len(dungeon['doors'])}):")
            for d in dungeon["doors"]:
                lines.append(f"  {d['from']} → {d['to']}  ({d['direction']})")

    return "\n".join(lines)


if __name__ == "__main__":
    main()
