#!/usr/bin/env python3
"""
Dungeon Map Generator - Builds accurate room connectivity graphs from ROM data.

Uses:
  1. Door directions from z3ed dungeon-describe-room
  2. Staircase destinations from z3ed dungeon-room-header (bytes 10-13)
  3. ALTTP room grid system (16x16) for door target inference

Output:
  - Connection graph (JSON)
  - ASCII map visualization
"""

import subprocess
import json
import re
import argparse
from pathlib import Path
from typing import Optional
from collections import defaultdict
from dataclasses import dataclass, field

Z3ED = "/Users/scawful/src/hobby/yaze/build/bin/Debug/z3ed"
ROM = "/Users/scawful/src/hobby/oracle-of-secrets/Roms/oos168x.sfc"

# Dungeon definitions from analyze_dungeon_metadata.py
DUNGEONS = {
    "mushroom_grotto": {
        "name": "Mushroom Grotto",
        "rooms": [0x07, 0x09, 0x0A, 0x0B, 0x17, 0x19, 0x1A, 0x1B,
                  0x2A, 0x2B, 0x32, 0x33, 0x3A, 0x3B, 0x43, 0x4A,
                  0x4B, 0x53, 0x5B, 0x63, 0x6A],
        "entrance_room": 0x4A,
        "boss_room": 0x07,
    },
    "tail_palace": {
        "name": "Tail Palace",
        "rooms": [0x0E, 0x1D, 0x1E, 0x1F, 0x2D, 0x2E, 0x2F, 0x3E, 0x3F,
                  0x4E, 0x4F, 0x5E, 0x5F, 0x6E, 0x6F, 0x7E, 0xDE],
        "entrance_room": 0x5F,
        "boss_room": 0x0E,
    },
    "kalyxo_castle": {
        "name": "Kalyxo Castle",
        "rooms": [0x29, 0x30, 0x39, 0x47, 0x48, 0x49, 0x51, 0x56,
                  0x57, 0x58, 0x59, 0x66, 0x67, 0x68],
        "entrance_room": 0x56,
        "boss_room": 0x29,
    },
    "zora_temple": {
        "name": "Zora Temple",
        "rooms": [0x06, 0x16, 0x18, 0x25, 0x26, 0x27, 0x28, 0x34,
                  0x35, 0x36, 0x37, 0x38, 0x44, 0x45, 0x46],
        "entrance_room": 0x28,
        "boss_room": 0x06,
    },
    "glacia_estate": {
        "name": "Glacia Estate",
        "rooms": [0x9E, 0x9F, 0xAC, 0xAD, 0xAE, 0xAF, 0xBB, 0xBC,
                  0xBD, 0xBE, 0xBF, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
                  0xDB, 0xDC, 0xDD],
        "entrance_room": 0xDB,
        "boss_room": 0x9E,
    },
    "dragon_ship": {
        "name": "Dragon Ship",
        "rooms": [0xB7, 0xC6, 0xC7, 0xD5, 0xD6],
        "entrance_room": 0xD6,
        "boss_room": 0xB7,
    },
    "goron_mines": {
        "name": "Goron Mines",
        "rooms": [0x69, 0x77, 0x78, 0x79, 0x87, 0x88, 0x89,
                  0x97, 0x98, 0x99, 0xA8, 0xA9, 0xB8, 0xB9,
                  0xC8, 0xD7, 0xD8, 0xD9, 0xDA],
        "entrance_room": 0x98,
        "boss_room": 0xC8,
    },
}


@dataclass
class Door:
    """Represents a door in a room."""
    position: int
    direction: str
    door_type: str
    tile_x: int = 0
    tile_y: int = 0


@dataclass
class RoomData:
    """All data for a single room."""
    room_id: int
    doors: list[Door] = field(default_factory=list)
    stairs: list[int] = field(default_factory=list)  # Destination room IDs
    holewarp: Optional[int] = None
    object_count: int = 0
    blockset: int = 0
    palette: int = 0


@dataclass
class Connection:
    """A connection between two rooms."""
    from_room: int
    to_room: int
    conn_type: str  # 'door', 'stair', 'holewarp'
    direction: Optional[str] = None  # For doors only
    door_type: Optional[str] = None  # For doors only
    stair_index: Optional[int] = None  # For stairs only
    bidirectional: bool = True


def parse_json_output(output: str) -> dict:
    """Parse z3ed JSON output, handling malformed JSON."""
    try:
        # Try direct parse first
        return json.loads(output)
    except json.JSONDecodeError:
        # Fallback: try to extract the JSON object
        match = re.search(r'\{[\s\S]*\}', output)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return {}


def query_room_header(room_id: int, rom_path: str = ROM) -> dict:
    """Query z3ed for room header (staircase destinations)."""
    room_hex = f"0x{room_id:02X}"
    try:
        result = subprocess.run(
            [Z3ED, "dungeon-room-header", f"--rom={rom_path}", f"--room={room_hex}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            data = parse_json_output(result.stdout)
            if "Room Header Debug" in data:
                return data["Room Header Debug"].get("decoded", {})
            elif "decoded" in data:
                return data["decoded"]
        return {}
    except Exception as e:
        print(f"  Warning: Failed to query header for room {room_hex}: {e}")
        return {}


def query_room_description(room_id: int, rom_path: str = ROM) -> dict:
    """Query z3ed for room description (doors, properties)."""
    room_hex = f"0x{room_id:02X}"
    try:
        result = subprocess.run(
            [Z3ED, "dungeon-describe-room", f"--rom={rom_path}", f"--room={room_hex}"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            return parse_json_output(result.stdout)
        return {}
    except Exception as e:
        print(f"  Warning: Failed to query description for room {room_hex}: {e}")
        return {}


def collect_room_data(room_id: int, rom_path: str = ROM) -> RoomData:
    """Collect all data for a room from z3ed."""
    header = query_room_header(room_id, rom_path)
    desc = query_room_description(room_id, rom_path)

    room = RoomData(room_id=room_id)

    # Parse doors
    for door_data in desc.get("doors", []):
        room.doors.append(Door(
            position=door_data.get("position", 0),
            direction=door_data.get("direction", ""),
            door_type=door_data.get("type", "Unknown"),
            tile_x=door_data.get("tile_x", 0),
            tile_y=door_data.get("tile_y", 0),
        ))

    # Parse staircase destinations
    for i in range(1, 5):
        stair_dest = header.get(f"stair{i}_room")
        if stair_dest is not None:
            room.stairs.append(stair_dest)

    # Parse holewarp
    room.holewarp = header.get("holewarp")

    # Parse properties
    props = desc.get("properties", {})
    room.object_count = props.get("object_count", 0)
    room.blockset = props.get("blockset", header.get("blockset", 0))
    room.palette = props.get("palette", header.get("palette", 0))

    return room


def get_adjacent_room(room_id: int, direction: str) -> Optional[int]:
    """Calculate adjacent room ID using ALTTP 16x16 grid system.

    Room layout:
        Row 0: 0x00-0x0F
        Row 1: 0x10-0x1F
        ...
        Row F: 0xF0-0xFF

    Adjacent calculation:
        North: room_id - 0x10 (previous row)
        South: room_id + 0x10 (next row)
        West:  room_id - 0x01 (previous column)
        East:  room_id + 0x01 (next column)
    """
    if direction == "North":
        return room_id - 0x10 if room_id >= 0x10 else None
    elif direction == "South":
        return room_id + 0x10 if room_id < 0xF0 else None
    elif direction == "West":
        return room_id - 0x01 if room_id % 16 != 0 else None
    elif direction == "East":
        return room_id + 0x01 if room_id % 16 != 15 else None
    return None


def get_opposite_direction(direction: str) -> str:
    """Get opposite cardinal direction."""
    opposites = {
        "North": "South",
        "South": "North",
        "East": "West",
        "West": "East",
    }
    return opposites.get(direction, "")


def room_has_door_facing(room_data: RoomData, direction: str) -> bool:
    """Check if a room has a door facing the given direction."""
    for door in room_data.doors:
        if door.direction == direction:
            return True
    return False


def build_connectivity_graph(
    dungeon_rooms: dict[int, RoomData],
    dungeon_room_set: set[int]
) -> list[Connection]:
    """Build the connectivity graph for a dungeon.

    Algorithm:
    1. For each door, infer target room using grid adjacency
    2. Validate connection (target in dungeon, has reciprocal door)
    3. Add staircase connections (explicit destinations)
    4. Optionally add holewarp connections
    """
    connections = []
    seen_pairs = set()  # Avoid duplicate entries

    for room_id, room_data in dungeon_rooms.items():
        # Process doors - group by direction to collect all door types
        doors_by_target = defaultdict(list)
        for door in room_data.doors:
            target = get_adjacent_room(room_id, door.direction)
            if target is None or target not in dungeon_room_set:
                continue
            if "Exit" in door.door_type:
                continue
            doors_by_target[(target, door.direction)].append(door)

        for (target, direction), doors in doors_by_target.items():
            pair = tuple(sorted([room_id, target]))
            if pair in seen_pairs:
                continue

            # Pick most descriptive door type (prefer non-Normal)
            door_types = [d.door_type for d in doors]
            best_type = next(
                (t for t in door_types if t != "Normal Door"), door_types[0]
            )

            # Validate: check if target has reciprocal door
            target_data = dungeon_rooms.get(target)
            opposite = get_opposite_direction(direction)

            if target_data and room_has_door_facing(target_data, opposite):
                connections.append(Connection(
                    from_room=room_id,
                    to_room=target,
                    conn_type="door",
                    direction=direction,
                    door_type=best_type,
                    bidirectional=True,
                ))
                seen_pairs.add(pair)
            else:
                connections.append(Connection(
                    from_room=room_id,
                    to_room=target,
                    conn_type="door",
                    direction=direction,
                    door_type=best_type,
                    bidirectional=False,
                ))
                seen_pairs.add(pair)

        # Process staircases (explicit destinations)
        for i, stair_dest in enumerate(room_data.stairs):
            if stair_dest and stair_dest != room_id and stair_dest in dungeon_room_set:
                # Check if already connected (stair pairs)
                pair = tuple(sorted([room_id, stair_dest]))
                if pair not in seen_pairs:
                    connections.append(Connection(
                        from_room=room_id,
                        to_room=stair_dest,
                        conn_type="stair",
                        stair_index=i + 1,
                        bidirectional=True,  # Usually bidirectional
                    ))
                    seen_pairs.add(pair)

        # Process holewarp (one-way)
        if room_data.holewarp and room_data.holewarp in dungeon_room_set:
            connections.append(Connection(
                from_room=room_id,
                to_room=room_data.holewarp,
                conn_type="holewarp",
                bidirectional=False,
            ))

    return connections


def direction_to_offset(direction: str) -> tuple[int, int]:
    """Convert direction to grid offset (dx, dy)."""
    offsets = {
        "North": (0, -1),
        "South": (0, 1),
        "East": (1, 0),
        "West": (-1, 0),
    }
    return offsets.get(direction, (0, 0))


def generate_ascii_map(
    entrance_room: int,
    connections: list[Connection],
    dungeon_rooms: dict[int, RoomData],
    boss_room: Optional[int] = None
) -> str:
    """Generate ASCII map using the ALTTP 16x16 room grid.

    Uses the room IDs themselves to determine spatial layout since ALTTP
    rooms are arranged in a 16x16 grid where room_id = row*16 + col.

    Door connections between adjacent rooms are drawn with connectors.
    Staircase connections are listed below the map.
    """
    if not dungeon_rooms:
        return "No rooms to display"

    # Derive grid positions from room IDs
    room_positions = {}  # room_id -> (col, row)
    for room_id in dungeon_rooms:
        col = room_id % 16
        row = room_id // 16
        room_positions[room_id] = (col, row)

    # Build lookup for door connections between adjacent rooms
    door_links = {}  # (room_a, room_b) -> door_type
    for conn in connections:
        if conn.conn_type == "door":
            pair = tuple(sorted([conn.from_room, conn.to_room]))
            door_links[pair] = conn.door_type or "Normal"

    # Find grid bounds
    min_col = min(c for c, r in room_positions.values())
    max_col = max(c for c, r in room_positions.values())
    min_row = min(r for c, r in room_positions.values())
    max_row = max(r for c, r in room_positions.values())

    # Build position lookup
    pos_to_room = {(c, r): rid for rid, (c, r) in room_positions.items()}

    # Find rows that actually contain rooms (skip empty rows)
    occupied_rows = sorted(set(r for c, r in room_positions.values()))

    # Render ASCII map
    cell_width = 8
    lines = []

    # Header
    total_width = (max_col - min_col + 1) * cell_width + 2
    lines.append(f"╔{'═' * total_width}╗")
    title = f" Grid Map (Entrance: 0x{entrance_room:02X}) "
    lines.append(f"║{title:^{total_width}}║")
    lines.append(f"╠{'═' * total_width}╣")

    for row_idx, row in enumerate(occupied_rows):
        # Room row (with horizontal connectors between adjacent rooms)
        room_line = "║ "
        for col in range(min_col, max_col + 1):
            if (col, row) in pos_to_room:
                room_id = pos_to_room[(col, row)]
                marker = ""
                if room_id == entrance_room:
                    marker = "*"
                elif room_id == boss_room:
                    marker = "B"
                cell = f"[{room_id:02X}{marker}]"
            else:
                cell = ""

            # Check for horizontal connection to next column
            next_room = pos_to_room.get((col + 1, row))
            curr_room = pos_to_room.get((col, row))
            if curr_room is not None and next_room is not None and col < max_col:
                pair = tuple(sorted([curr_room, next_room]))
                if pair in door_links:
                    room_line += f"{cell:>5}--"
                else:
                    room_line += f"{cell:^{cell_width}}"
                continue

            room_line += f"{cell:^{cell_width}}"
        room_line += " ║"
        lines.append(room_line)

        # Connector row (vertical connections to the next occupied row)
        if row_idx < len(occupied_rows) - 1:
            next_row = occupied_rows[row_idx + 1]
            # Only draw connectors if next row is adjacent (row+1)
            if next_row == row + 1:
                conn_line = "║ "
                for col in range(min_col, max_col + 1):
                    upper = pos_to_room.get((col, row))
                    lower = pos_to_room.get((col, next_row))
                    if upper is not None and lower is not None:
                        pair = tuple(sorted([upper, lower]))
                        if pair in door_links:
                            connector = "  |   "
                        else:
                            connector = "      "
                    else:
                        connector = "      "
                    conn_line += f"{connector:^{cell_width}}"
                conn_line += " ║"
                lines.append(conn_line)
            else:
                # Non-adjacent rows: show a gap indicator
                gap_line = f"║{'  ···':^{total_width}}║"
                lines.append(gap_line)

    lines.append(f"╚{'═' * total_width}╝")

    # Horizontal connectors note
    horiz_pairs = []
    for conn in connections:
        if conn.conn_type == "door":
            a, b = conn.from_room, conn.to_room
            ac, ar = room_positions[a]
            bc, br = room_positions[b]
            if ar == br and abs(ac - bc) == 1:
                horiz_pairs.append(conn)

    # Stair connections
    stair_conns = [c for c in connections if c.conn_type == "stair"]
    hole_conns = [c for c in connections if c.conn_type == "holewarp"]

    lines.append("")
    lines.append("Legend: * = Entrance, B = Boss, | = Door connection (vertical)")

    if stair_conns:
        lines.append("")
        lines.append("Staircase connections:")
        for sc in stair_conns:
            lines.append(f"  0x{sc.from_room:02X} <-> 0x{sc.to_room:02X}  (Stair {sc.stair_index})")

    if hole_conns:
        lines.append("")
        lines.append("Holewarp connections:")
        for hc in hole_conns:
            lines.append(f"  0x{hc.from_room:02X}  -> 0x{hc.to_room:02X}  (Fall)")

    return "\n".join(lines)


def format_connections_table(connections: list[Connection]) -> str:
    """Format connections as a readable table."""
    lines = []
    lines.append("=" * 70)
    lines.append("CONNECTIONS")
    lines.append("=" * 70)
    lines.append(f"{'From':>6} -> {'To':>6}  {'Type':<10}  {'Details':<30}")
    lines.append("-" * 70)

    # Sort by connection type, then from_room
    sorted_conns = sorted(connections, key=lambda c: (c.conn_type, c.from_room))

    for conn in sorted_conns:
        from_hex = f"0x{conn.from_room:02X}"
        to_hex = f"0x{conn.to_room:02X}"

        if conn.conn_type == "door":
            details = f"{conn.direction} ({conn.door_type})"
            bidir = " <->" if conn.bidirectional else " ->"
        elif conn.conn_type == "stair":
            details = f"Stair {conn.stair_index}"
            bidir = " <->" if conn.bidirectional else " ->"
        else:  # holewarp
            details = "Fall through"
            bidir = " ->"

        lines.append(f"{from_hex:>6}{bidir}{to_hex:>6}  {conn.conn_type:<10}  {details:<30}")

    return "\n".join(lines)


def analyze_dungeon(dungeon_key: str, rom_path: str = ROM) -> dict:
    """Analyze a dungeon and generate connectivity map."""
    if dungeon_key not in DUNGEONS:
        print(f"Unknown dungeon: {dungeon_key}")
        print(f"Available: {', '.join(DUNGEONS.keys())}")
        return {}

    dungeon_info = DUNGEONS[dungeon_key]
    room_ids = dungeon_info["rooms"]
    room_set = set(room_ids)

    print(f"\n{'=' * 70}")
    print(f"  {dungeon_info['name']}")
    print(f"  Rooms: {len(room_ids)}")
    print(f"  Entrance: 0x{dungeon_info['entrance_room']:02X}")
    print(f"{'=' * 70}")

    # Collect room data
    print("\nCollecting room data...")
    dungeon_rooms = {}
    for room_id in room_ids:
        room_data = collect_room_data(room_id, rom_path)
        dungeon_rooms[room_id] = room_data
        print(f"  0x{room_id:02X}: {len(room_data.doors)} doors, "
              f"{len([s for s in room_data.stairs if s])} stairs")

    # Build connectivity
    print("\nBuilding connectivity graph...")
    connections = build_connectivity_graph(dungeon_rooms, room_set)
    print(f"  Found {len(connections)} connections")

    # Format output
    print("\n" + format_connections_table(connections))

    # Generate ASCII map
    ascii_map = generate_ascii_map(
        dungeon_info["entrance_room"],
        connections,
        dungeon_rooms,
        dungeon_info.get("boss_room")
    )
    print(f"\n{ascii_map}")

    # Build result structure
    result = {
        "dungeon": dungeon_key,
        "name": dungeon_info["name"],
        "entrance_room": dungeon_info["entrance_room"],
        "boss_room": dungeon_info.get("boss_room"),
        "rooms": {
            f"0x{rid:02X}": {
                "doors": [
                    {"position": d.position, "direction": d.direction, "type": d.door_type}
                    for d in rdata.doors
                ],
                "stairs": [s for s in rdata.stairs if s],
                "holewarp": rdata.holewarp,
            }
            for rid, rdata in dungeon_rooms.items()
        },
        "connections": [
            {
                "from": f"0x{c.from_room:02X}",
                "to": f"0x{c.to_room:02X}",
                "type": c.conn_type,
                "direction": c.direction,
                "door_type": c.door_type,
                "stair_index": c.stair_index,
                "bidirectional": c.bidirectional,
            }
            for c in connections
        ],
        "ascii_map": ascii_map,
    }

    return result


def main():
    parser = argparse.ArgumentParser(
        description="Generate dungeon connectivity maps from ROM data"
    )
    parser.add_argument(
        "dungeon",
        nargs="?",
        default="mushroom_grotto",
        help=f"Dungeon to analyze ({', '.join(DUNGEONS.keys())})"
    )
    parser.add_argument(
        "--rom",
        default=ROM,
        help="Path to ROM file"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Analyze all dungeons"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output as JSON"
    )
    parser.add_argument(
        "--output",
        "-o",
        help="Output file (default: stdout)"
    )

    args = parser.parse_args()

    if args.all:
        results = {}
        for dungeon_key in DUNGEONS:
            results[dungeon_key] = analyze_dungeon(dungeon_key, args.rom)
    else:
        results = analyze_dungeon(args.dungeon, args.rom)

    if args.json:
        output = json.dumps(results, indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"\nJSON saved to: {args.output}")
        else:
            print("\n" + output)
    elif args.output:
        # Save ASCII map
        if isinstance(results, dict) and "ascii_map" in results:
            Path(args.output).write_text(results["ascii_map"])
            print(f"\nASCII map saved to: {args.output}")


if __name__ == "__main__":
    main()
