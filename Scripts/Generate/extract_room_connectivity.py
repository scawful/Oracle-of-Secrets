#!/usr/bin/env python3
"""Extract room connectivity evidence from ALTTP ROM headers and dungeon registry.

Distinguishes registry grid adjacency candidates from raw ROM-header destinations.
Neither observation establishes a usable door, staircase, pit transition, or return route.

Evidence-report schema_version = 2.

Usage:
    python3 Scripts/Generate/extract_room_connectivity.py --rom Roms/oos168.sfc
    python3 Scripts/Generate/extract_room_connectivity.py --rom Roms/oos168.sfc --format json
    python3 Scripts/Generate/extract_room_connectivity.py --rom Roms/oos168.sfc --output report.txt
"""

import argparse
import hashlib
import json
import signal
import sys
import tempfile
from pathlib import Path

try:
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)
except (AttributeError, ValueError):
    pass

ROOM_HEADER_POINTER_OFFSET = 0xB5DD
ROOM_HEADER_BANK_OFFSET = 0xB5E7


def snes_to_pc(addr: int) -> int:
    """Convert SNES LoROM address to PC file offset."""
    bank = (addr >> 16) & 0xFF
    offset = addr & 0xFFFF
    if bank < 0x80:
        return (bank * 0x8000) + (offset - 0x8000)
    else:
        return ((bank - 0x80) * 0x8000) + (offset - 0x8000)


def get_room_header_location(rom: bytes, room_id: int) -> int:
    """Get the PC offset of a room's 14-byte header."""
    if len(rom) < ROOM_HEADER_BANK_OFFSET + 1:
        raise ValueError(
            f"ROM truncated: length {len(rom)} bytes is smaller than required header pointer area"
        )
    base_ptr = (
        rom[ROOM_HEADER_POINTER_OFFSET]
        | (rom[ROOM_HEADER_POINTER_OFFSET + 1] << 8)
        | (rom[ROOM_HEADER_POINTER_OFFSET + 2] << 16)
    )
    base_pc = snes_to_pc(base_ptr)
    if base_pc < 0 or base_pc >= len(rom):
        raise ValueError(
            f"ROM malformed: base pointer 0x{base_ptr:06X} resolves to invalid PC offset {base_pc}"
        )
    bank = rom[ROOM_HEADER_BANK_OFFSET]
    table_offset = base_pc + (room_id * 2)
    if table_offset < 0 or table_offset + 2 > len(rom):
        raise ValueError(
            f"ROM malformed or truncated: table offset {table_offset} for room 0x{room_id:02X} exceeds ROM size {len(rom)}"
        )
    room_ptr = (bank << 16) | (rom[table_offset + 1] << 8) | rom[table_offset]
    loc = snes_to_pc(room_ptr)
    if loc < 0 or loc + 14 > len(rom):
        raise ValueError(
            f"ROM malformed or truncated: room 0x{room_id:02X} header offset {loc} exceeds ROM size {len(rom)}"
        )
    return loc


def validate_rom_spans(rom: bytes, room_ids: set[int]) -> dict[int, int]:
    """Validate room-header pointer table and header spans for all requested rooms.

    Returns a map of room_id -> PC offset.
    Raises ValueError on any truncated, malformed, or out-of-bounds structure.
    """
    if len(rom) < ROOM_HEADER_BANK_OFFSET + 1:
        raise ValueError(
            f"ROM truncated: size {len(rom)} bytes is smaller than required pointer table area ({ROOM_HEADER_BANK_OFFSET + 1} bytes)"
        )
    base_ptr = (
        rom[ROOM_HEADER_POINTER_OFFSET]
        | (rom[ROOM_HEADER_POINTER_OFFSET + 1] << 8)
        | (rom[ROOM_HEADER_POINTER_OFFSET + 2] << 16)
    )
    base_pc = snes_to_pc(base_ptr)
    if base_pc < 0 or base_pc >= len(rom):
        raise ValueError(
            f"ROM malformed: base pointer 0x{base_ptr:06X} resolves to invalid PC offset {base_pc}"
        )
    bank = rom[ROOM_HEADER_BANK_OFFSET]

    room_locs = {}
    for rid in sorted(room_ids):
        table_offset = base_pc + (rid * 2)
        if table_offset < 0 or table_offset + 2 > len(rom):
            raise ValueError(
                f"ROM malformed or truncated: table offset {table_offset} for room 0x{rid:02X} exceeds ROM size {len(rom)}"
            )
        room_ptr = (bank << 16) | (rom[table_offset + 1] << 8) | rom[table_offset]
        loc = snes_to_pc(room_ptr)
        if loc < 0 or loc + 14 > len(rom):
            raise ValueError(
                f"ROM malformed or truncated: room 0x{rid:02X} header offset {loc} (pointer 0x{room_ptr:06X}) exceeds ROM size {len(rom)}"
            )
        room_locs[rid] = loc

    return room_locs


def extract_room_header(rom: bytes, loc: int, room_id: int) -> dict:
    """Extract raw 14-byte room header data from validated PC offset."""
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


def parse_room_id(raw_id: str | int) -> int:
    """Parse and validate room ID integer value.

    Raises ValueError on invalid formats (e.g. 'not-a-room') or negative values.
    """
    if isinstance(raw_id, int):
        rid = raw_id
    elif isinstance(raw_id, str):
        raw_str = raw_id.strip()
        if not raw_str:
            raise ValueError("Room ID cannot be empty")
        rid = int(raw_str, 0)
    else:
        raise ValueError(f"Invalid room ID type: {type(raw_id).__name__}")
    if rid < 0:
        raise ValueError(f"Room ID cannot be negative: {raw_id}")
    return rid


def validate_dungeon_registry(data: dict) -> None:
    """Validate structure and room IDs of dungeon registry dict."""
    if not isinstance(data, dict) or "dungeons" not in data or not isinstance(data["dungeons"], list):
        raise ValueError("Registry JSON missing top-level 'dungeons' list")
    for d in data["dungeons"]:
        if "id" not in d or "name" not in d or "rooms" not in d or not isinstance(d["rooms"], list):
            raise ValueError(f"Dungeon entry missing required id/name/rooms: {d}")
        for r in d["rooms"]:
            if not all(k in r for k in ("id", "name", "grid_row", "grid_col")):
                raise ValueError(f"Room entry missing required fields in dungeon {d['id']}: {r}")
            try:
                parse_room_id(r["id"])
            except (ValueError, TypeError) as err:
                raise ValueError(f"Invalid room id in dungeon {d['id']}: {r.get('id')!r}: {err}")


def load_dungeon_registry(path: Path | str, raw: bytes | None = None) -> dict:
    """Load and validate one captured UTF-8 registry snapshot."""
    p = Path(path)
    if not p.is_file():
        raise FileNotFoundError(f"Registry file not found: {p}")
    data = json.loads((p.read_bytes() if raw is None else raw).decode("utf-8"))
    validate_dungeon_registry(data)
    return data


def get_all_dungeon_rooms(registry: dict) -> dict[int, dict]:
    """Get a map of all room IDs in registry to their dungeon identity."""
    rooms = {}
    for dungeon in registry["dungeons"]:
        did = dungeon["id"]
        dname = dungeon["name"]
        for room in dungeon["rooms"]:
            rid = parse_room_id(room["id"])
            rooms[rid] = {
                "dungeon_id": did,
                "dungeon_name": dname,
                "name": room.get("name", f"Room 0x{rid:02X}"),
            }
    return rooms


def compute_adjacency_candidates(dungeon_rooms_list: list[dict]) -> list[dict]:
    """Compute grid-adjacent room candidates within the same dungeon.

    Two rooms are grid adjacency candidates if their grid_row/grid_col differ
    by exactly 1 Manhattan distance step (dr + dc == 1).
    These are structural layout neighbors from the registry grid;
    neither establishes a usable door or traversal route.
    """
    candidates = []
    room_map = {}
    for r in dungeon_rooms_list:
        rid = parse_room_id(r["id"])
        room_map[rid] = r

    room_ids = sorted(room_map.keys())
    for i, rid_a in enumerate(room_ids):
        for rid_b in room_ids[i + 1:]:
            ra = room_map[rid_a]
            rb = room_map[rid_b]
            row_a, col_a = ra["grid_row"], ra["grid_col"]
            row_b, col_b = rb["grid_row"], rb["grid_col"]

            dr = abs(row_a - row_b)
            dc = abs(col_a - col_b)
            if dr + dc == 1:
                if dr == 1:
                    direction = "south" if row_b > row_a else "north"
                else:
                    direction = "east" if col_b > col_a else "west"

                candidates.append({
                    "from_room": ra["id"],
                    "to_room": rb["id"],
                    "rooms": [ra["id"], rb["id"]],
                    "direction": direction,
                    "source": "registry_grid",
                    "verification_status": "unverified",
                })
    return candidates


def extract_header_destinations(
    rom: bytes,
    loc: int,
    room_id: int,
    room_name: str,
    all_dungeon_rooms: dict[int, dict],
    current_dungeon_id: str,
) -> list[dict]:
    """Extract raw pit and stair header destination records for a room.

    Preserves exact slot, byte offset, raw target byte, raw destination-plane bits,
    and lookup status. Does not filter 0x00 or self targets.
    Does not infer active routes or reciprocity.
    """
    destinations = []
    from_hex = f"0x{room_id:02X}"

    # Pit / holewarp destination (byte +9, plane in byte +7 bits 0..1)
    raw_pit_target = rom[loc + 9]
    pit_plane = rom[loc + 7] & 0x03
    target_hex = f"0x{raw_pit_target:02X}"

    pit_lookup = all_dungeon_rooms.get(raw_pit_target)
    if pit_lookup:
        if pit_lookup["dungeon_id"] == current_dungeon_id:
            lookup_status = "same_dungeon"
        else:
            lookup_status = "cross_dungeon"
        target_dungeon_id = pit_lookup["dungeon_id"]
        target_dungeon_name = pit_lookup["dungeon_name"]
        target_room_name = pit_lookup["name"]
    else:
        lookup_status = "unregistered"
        target_dungeon_id = None
        target_dungeon_name = None
        target_room_name = None

    destinations.append({
        "source_room": from_hex,
        "source_room_name": room_name,
        "transition_kind": "pit",
        "slot": 0,
        "header_byte_offset": 9,
        "raw_target_byte": raw_pit_target,
        "target_room": target_hex,
        "destination_plane": pit_plane,
        "plane_bits": pit_plane,
        "lookup_status": lookup_status,
        "target_dungeon_id": target_dungeon_id,
        "target_dungeon_name": target_dungeon_name,
        "target_room_name": target_room_name,
        "is_self_target": (raw_pit_target == room_id),
        "verification_status": "unverified",
    })

    # Staircase destinations (slots 0..3 at byte offsets 10..13)
    planes = [
        (rom[loc + 7] >> 2) & 0x03,
        (rom[loc + 7] >> 4) & 0x03,
        (rom[loc + 7] >> 6) & 0x03,
        rom[loc + 8] & 0x03,
    ]

    for slot_idx in range(4):
        byte_offset = 10 + slot_idx
        raw_target = rom[loc + byte_offset]
        plane = planes[slot_idx]
        target_hex = f"0x{raw_target:02X}"

        lookup = all_dungeon_rooms.get(raw_target)
        if lookup:
            if lookup["dungeon_id"] == current_dungeon_id:
                lookup_status = "same_dungeon"
            else:
                lookup_status = "cross_dungeon"
            target_dungeon_id = lookup["dungeon_id"]
            target_dungeon_name = lookup["dungeon_name"]
            target_room_name = lookup["name"]
        else:
            lookup_status = "unregistered"
            target_dungeon_id = None
            target_dungeon_name = None
            target_room_name = None

        destinations.append({
            "source_room": from_hex,
            "source_room_name": room_name,
            "transition_kind": "stair",
            "slot": slot_idx,
            "header_byte_offset": byte_offset,
            "raw_target_byte": raw_target,
            "target_room": target_hex,
            "destination_plane": plane,
            "plane_bits": plane,
            "lookup_status": lookup_status,
            "target_dungeon_id": target_dungeon_id,
            "target_dungeon_name": target_dungeon_name,
            "target_room_name": target_room_name,
            "is_self_target": (raw_target == room_id),
            "verification_status": "unverified",
        })

    return destinations


def build_connectivity_report(
    rom: bytes,
    registry: dict,
    rom_path: str = "",
    registry_path: str = "",
    room_locs: dict[int, int] | None = None,
    registry_sha256: str = "",
) -> dict:
    """Build deterministic connectivity evidence report."""
    validate_dungeon_registry(registry)
    all_dungeon_rooms = get_all_dungeon_rooms(registry)

    if room_locs is None:
        all_room_ids = {parse_room_id(r["id"]) for d in registry["dungeons"] for r in d["rooms"]}
        room_locs = validate_rom_spans(rom, all_room_ids)

    rom_hash = hashlib.sha256(rom).hexdigest()
    if not registry_sha256:
        registry_canonical_bytes = json.dumps(registry, sort_keys=True).encode("utf-8")
        registry_hash = hashlib.sha256(registry_canonical_bytes).hexdigest()
    else:
        registry_hash = registry_sha256

    result = {
        "_meta": {
            "generated_by": "extract_room_connectivity.py",
            "schema_version": 2,
            "description": "Room connectivity evidence report distinguishing registry grid adjacency from raw ROM-header destinations",
            "rom": str(rom_path),
            "rom_sha256": rom_hash,
            "registry": str(registry_path),
            "registry_sha256": registry_hash,
            "verification_status": {
                "door_objects_checked": False,
                "triggers_checked": False,
                "collision_checked": False,
                "state_checked": False,
                "gameplay_checked": False,
                "status": "unverified",
                "notes": (
                    "Grid adjacency candidates and raw header destinations do not establish "
                    "confirmed traversal, usable doors, staircases, pit transitions, or return routes."
                ),
            },
        },
        "dungeons": [],
    }

    for dungeon in registry["dungeons"]:
        did = dungeon["id"]
        rooms_enriched = []
        dungeon_header_destinations = []

        for room in dungeon["rooms"]:
            rid = parse_room_id(room["id"])

            loc = room_locs[rid]
            header = extract_room_header(rom, loc, rid)

            # Preserve all room metadata from input registry exactly
            room_entry = dict(room)
            if "palette" not in room_entry:
                room_entry["palette"] = header["palette"]
            if "blockset" not in room_entry:
                room_entry["blockset"] = header["blockset"]
            if "spriteset" not in room_entry:
                room_entry["spriteset"] = header["spriteset"]
            if "tag1" not in room_entry:
                room_entry["tag1"] = header["tag1"]
            if "tag2" not in room_entry:
                room_entry["tag2"] = header["tag2"]

            rooms_enriched.append(room_entry)

            room_dests = extract_header_destinations(
                rom, loc, rid, room.get("name", ""), all_dungeon_rooms, did
            )
            dungeon_header_destinations.extend(room_dests)

        adjacency_candidates = compute_adjacency_candidates(dungeon["rooms"])

        dungeon_entry = {
            "id": did,
            "name": dungeon["name"],
            "vanilla_name": dungeon.get("vanilla_name", ""),
            "rooms": rooms_enriched,
            "adjacency_candidates": adjacency_candidates,
            "header_destinations": dungeon_header_destinations,
        }
        if "crystal_bit" in dungeon:
            dungeon_entry["crystal_bit"] = dungeon["crystal_bit"]
        if "features" in dungeon:
            dungeon_entry["features"] = dungeon["features"]

        result["dungeons"].append(dungeon_entry)

    return result


def format_text(result: dict) -> str:
    """Format connectivity evidence report as human-readable text."""
    lines = []
    meta = result.get("_meta", {})
    lines.append("=" * 60)
    lines.append("ROOM CONNECTIVITY EVIDENCE REPORT (schema_version=2)")
    lines.append("=" * 60)
    lines.append(f"ROM: {meta.get('rom', '')} (SHA256: {meta.get('rom_sha256', '')})")
    lines.append(f"Registry: {meta.get('registry', '')} (SHA256: {meta.get('registry_sha256', '')})")
    vstatus = meta.get("verification_status", {})
    lines.append(f"Verification status: {vstatus.get('status', 'unverified')}")
    lines.append(f"Notice: {vstatus.get('notes', '')}")

    for dungeon in result.get("dungeons", []):
        lines.append(f"\n{'='*60}")
        lines.append(f"{dungeon['id']} {dungeon['name']} ({len(dungeon['rooms'])} rooms)")
        lines.append(f"{'='*60}")

        lines.append("\nRooms:")
        for room in dungeon["rooms"]:
            rtype = f" [{room.get('type')}]" if room.get("type") and room.get("type") != "normal" else ""
            floor = f" (floor={room.get('floor')})" if room.get("floor") else ""
            lines.append(
                f"  {room['id']} {room['name']}{rtype}{floor}  (row={room['grid_row']}, col={room['grid_col']})"
            )

        candidates = dungeon.get("adjacency_candidates", [])
        lines.append(f"\nGrid adjacency candidates ({len(candidates)}):")
        if candidates:
            for c in candidates:
                lines.append(
                    f"  {c['from_room']} -> {c['to_room']}  ({c['direction']}, source={c['source']}, {c['verification_status']})"
                )
        else:
            lines.append("  (none)")

        destinations = dungeon.get("header_destinations", [])
        lines.append(f"\nHeader destinations ({len(destinations)}):")
        if destinations:
            for d in destinations:
                kind = d["transition_kind"]
                slot = d["slot"]
                byte_off = d["header_byte_offset"]
                src = d["source_room"]
                tgt = d["target_room"]
                plane = d["destination_plane"]
                lstatus = d["lookup_status"]
                tname = f": {d['target_room_name']}" if d.get("target_room_name") else ""
                tdung = f" in {d['target_dungeon_id']}" if d.get("target_dungeon_id") else ""
                self_note = ", self" if d.get("is_self_target") else ""
                lines.append(
                    f"  {src} {kind} slot {slot} (byte +{byte_off}) -> {tgt} "
                    f"(plane {plane}, {lstatus}{tdung}{tname}{self_note}) [{d['verification_status']}]"
                )
        else:
            lines.append("  (none)")

    return "\n".join(lines)


def check_output_alias(output_path: Path, rom_path: Path, registry_path: Path) -> None:
    """Refuse to run if output path aliases ROM or registry."""
    targets = [("ROM", rom_path), ("registry", registry_path)]
    for target_name, target_path in targets:
        try:
            if output_path.resolve() == target_path.resolve():
                raise ValueError(
                    f"Refusing to overwrite input {target_name}: output path '{output_path}' aliases '{target_path}'"
                )
        except (FileNotFoundError, OSError):
            pass

        try:
            if output_path.exists() and target_path.exists() and output_path.samefile(target_path):
                raise ValueError(
                    f"Refusing to overwrite input {target_name}: output path '{output_path}' points to same file as '{target_path}'"
                )
        except (FileNotFoundError, OSError):
            pass


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Extract room connectivity evidence from ALTTP ROM headers and dungeon registry (schema_version=2)"
    )
    parser.add_argument("--rom", required=True, help="Path to ROM file")
    parser.add_argument(
        "--registry",
        default="Docs/Dev/Planning/dungeons.json",
        help="Path to dungeons.json (default: Docs/Dev/Planning/dungeons.json)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="text",
        help="Output format: text (default) or json",
    )
    parser.add_argument("--output", help="Output file path (default: stdout)")
    args = parser.parse_args(argv)

    rom_path = Path(args.rom)
    registry_path = Path(args.registry)

    if not rom_path.is_file():
        sys.stderr.write(f"ROM file not found: {rom_path}\n")
        return 1

    if not registry_path.is_file():
        sys.stderr.write(f"Registry file not found: {registry_path}\n")
        return 1

    if args.output:
        output_path = Path(args.output)
        try:
            check_output_alias(output_path, rom_path, registry_path)
        except ValueError as err:
            sys.stderr.write(f"Alias error: {err}\n")
            return 1

    try:
        registry_raw = registry_path.read_bytes()
        registry = load_dungeon_registry(registry_path, raw=registry_raw)
    except Exception as err:
        sys.stderr.write(f"Registry error: {err}\n")
        return 1

    try:
        rom_bytes = rom_path.read_bytes()
    except Exception as err:
        sys.stderr.write(f"Error reading ROM: {err}\n")
        return 1

    all_room_ids = {parse_room_id(r["id"]) for d in registry["dungeons"] for r in d["rooms"]}

    try:
        room_locs = validate_rom_spans(rom_bytes, all_room_ids)
    except ValueError as err:
        sys.stderr.write(f"ROM validation error: {err}\n")
        return 1

    try:
        report = build_connectivity_report(
            rom_bytes,
            registry,
            rom_path=str(rom_path),
            registry_path=str(registry_path),
            room_locs=room_locs,
            registry_sha256=hashlib.sha256(registry_raw).hexdigest(),
        )
    except Exception as err:
        sys.stderr.write(f"Report generation error: {err}\n")
        return 1

    if args.format == "json":
        rendered = json.dumps(report, indent=2) + "\n"
    else:
        rendered = format_text(report) + "\n"

    if args.output:
        try:
            out_p = Path(args.output)
            out_p.parent.mkdir(parents=True, exist_ok=True)
            tmp_p = None
            try:
                # Keep the exclusively created descriptor: never reopen a
                # predictable temporary path that may alias an input file.
                with tempfile.NamedTemporaryFile(
                    mode="w", encoding="utf-8", dir=out_p.parent,
                    prefix=f".{out_p.name}.tmp.", delete=False,
                ) as stream:
                    tmp_p = Path(stream.name)
                    stream.write(rendered)
                tmp_p.replace(out_p)
                tmp_p = None
            finally:
                if tmp_p is not None:
                    tmp_p.unlink(missing_ok=True)
            print(f"Written to {args.output}")
        except Exception as err:
            sys.stderr.write(f"Error writing output: {err}\n")
            return 1
    else:
        sys.stdout.write(rendered)

    return 0


if __name__ == "__main__":
    sys.exit(main())
