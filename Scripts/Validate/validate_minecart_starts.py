#!/usr/bin/env python3
"""Read-only comparison of compiled minecart starts, sprites, and stop tiles.

Supply the patched ROM and the WLA symbols from that exact build. This checks
initial placement prerequisites, not riding, return routes, or persistence.
Exit codes: 0 = checks passed, 1 = findings, 2 = invalid input.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys


GENERATE_DIR = Path(__file__).resolve().parents[1] / "Generate"
sys.path.insert(0, str(GENERATE_DIR))
from generate_water_gate_runtime_tables import (  # noqa: E402
    ROOM_COUNT,
    parse_room_sprites,
    snes_to_pc,
)
from generate_water_fill_table import parse_room_custom_collision  # noqa: E402


TRACK_COUNT = 32
MINECART_ID = 0xA3
STOP_TILES = {0xB7, 0xB8, 0xB9, 0xBA}
TABLE_SYMBOLS = {
    "room": "Oracle_Sprite_Minecart_Prep_TrackStartingRooms",
    "x": "Oracle_Sprite_Minecart_Prep_TrackStartingX",
    "y": "Oracle_Sprite_Minecart_Prep_TrackStartingY",
}


def parse_tracks(raw: str) -> list[int]:
    """Accept comma-separated decimal/0x IDs, inclusive ranges, or all."""
    if raw.strip().lower() == "all":
        return list(range(TRACK_COUNT))
    tracks = set()
    try:
        for token in raw.split(","):
            bounds = token.strip().split("-")
            if len(bounds) == 1:
                tracks.add(int(bounds[0], 0))
            elif len(bounds) == 2:
                start, end = (int(value, 0) for value in bounds)
                if start > end:
                    raise ValueError("reversed range")
                tracks.update(range(start, end + 1))
            else:
                raise ValueError("invalid range")
        if not tracks or min(tracks) < 0 or max(tracks) >= TRACK_COUNT:
            raise ValueError("track IDs must be 0 through 31")
    except ValueError as exc:
        raise argparse.ArgumentTypeError(f"Invalid --tracks {raw!r}: {exc}") from exc
    return sorted(tracks)


def read_start_tables(data: bytes, symbols_text: str) -> tuple[list[dict], dict]:
    """Read all 32 entries from each required WLA label; never use ASM text."""
    labels = {}
    section = None
    for number, raw in enumerate(symbols_text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line
            continue
        if section != "[labels]":
            continue
        match = re.fullmatch(r"([0-9a-fA-F]{2}):([0-9a-fA-F]{4})\s+(\S+)", line)
        if not match:
            raise ValueError(f"Malformed WLA label at line {number}")
        name = match[3]
        if name not in TABLE_SYMBOLS.values():
            continue
        address = int(match[1] + match[2], 16)
        if name in labels:
            raise ValueError(f"Duplicate WLA label: {name}")
        labels[name] = address

    tables, addresses = {}, {}
    for field, name in TABLE_SYMBOLS.items():
        if name not in labels:
            raise ValueError(f"Missing WLA label: {name}")
        address = labels[name]
        bank, offset = address >> 16, address & 0xFFFF
        if bank in (0x7E, 0x7F) or offset < 0x8000 or offset + TRACK_COUNT * 2 > 0x10000:
            raise ValueError(f"Table is not a contiguous LoROM span: {name}")
        pc = snes_to_pc(address)
        if pc + TRACK_COUNT * 2 > len(data):
            raise ValueError(f"Table extends beyond ROM: {name}")
        tables[field] = [int.from_bytes(data[pc + i * 2:pc + i * 2 + 2], "little")
                         for i in range(TRACK_COUNT)]
        addresses[field] = {"symbol": name, "snes_address": f"0x{address:06X}"}
    return ([{field: values[i] for field, values in tables.items()}
             for i in range(TRACK_COUNT)], addresses)


def collect_placements(data: bytes) -> list[dict]:
    placements = []
    for room in range(ROOM_COUNT):
        for index, sprite in enumerate(parse_room_sprites(data, room)):
            if sprite.spr_id == MINECART_ID:
                placements.append({
                    "room": room, "record_index": index, "subtype": sprite.subtype,
                    "layer": sprite.layer,
                    "x": (room % 16) * 512 + sprite.x * 16,
                    "y": (room // 16) * 512 + sprite.y * 16,
                })
    return placements


def check_starts(starts: list[dict], placements: list[dict], collisions: dict,
                 tracks: list[int]) -> dict:
    """Keep initial matches separate from same-subtype return placements."""
    results, issues, tuples = [], [], {}
    for track in tracks:
        start = starts[track]
        room, x, y = (start[field] for field in ("room", "x", "y"))
        candidates = [p for p in placements if p["subtype"] == track]
        matches = [p for p in candidates if all(p[k] == start[k] for k in ("room", "x", "y"))]
        row = {"track": track, "start": start, "placements": candidates,
               "initial_matches": matches, "initial_match_count": len(matches),
               "status": "disabled" if room == 0 else "pass"}
        results.append(row)
        if room == 0:
            continue  # Room zero is the runtime's reserved/disabled sentinel.
        tuples.setdefault((room, x, y), []).append(track)
        local_issues = []
        if room >= ROOM_COUNT:
            local_issues.append(("invalid_start_room", f"Room ${room:04X} is outside the room table"))
        local_x, local_y = x - (room % 16) * 512, y - (room // 16) * 512
        valid_xy = 0 <= local_x < 512 and 0 <= local_y < 512 and x % 8 == 0 and y % 8 == 0
        if not valid_xy:
            local_issues.append(("invalid_start_coordinates", "Start is outside its room or not aligned to an 8px tile"))
        if not matches:
            local_issues.append(("missing_initial_placement", "No A3 sprite of this subtype matches the starting room and coordinates"))
        elif len(matches) > 1:
            local_issues.append(("multiple_initial_placements", "More than one A3 sprite matches this starting tuple"))
        if room < ROOM_COUNT and valid_xy:
            tile_x, tile_y = local_x // 8, local_y // 8
            row["tile"] = [tile_x, tile_y]
            # Custom collision offsets include the layer ($0000 or $1000).
            layers = sorted({p["layer"] for p in matches}) if matches else [0]
            row["stop_samples"] = [
                {"layer": layer, "collision": collisions.get(room, {}).get(layer * 0x1000 + tile_y * 64 + tile_x)}
                for layer in layers
            ]
            if any(sample["collision"] not in STOP_TILES for sample in row["stop_samples"]):
                local_issues.append(("initial_point_not_on_stop", "Initial point lacks an authored B7-BA stop on its placement layer"))
        if local_issues:
            row["status"] = "fail"
            issues.extend({"code": code, "tracks": [track], "message": message}
                          for code, message in local_issues)
    for start_tuple, owners in tuples.items():
        if len(owners) > 1:
            issues.append({"code": "duplicate_start_tuple", "tracks": owners,
                           "start": dict(zip(("room", "x", "y"), start_tuple)),
                           "message": "Selected tracks share the same nonzero initial room and coordinates"})
            for row in results:
                if row["track"] in owners:
                    row["status"] = "fail"
    return {"status": "fail" if issues else "pass", "selected_tracks": tracks,
            "tracks": results, "issues": issues, "issue_count": len(issues)}


def audit_rom(rom_path: Path, symbols_path: Path, tracks: list[int]) -> dict:
    data, symbols = rom_path.read_bytes(), symbols_path.read_bytes()
    # Asar can extend Oracle past its original ROM size by a partial bank.
    # Bounds checks belong to the tables being read, not the whole-file size.
    starts, addresses = read_start_tables(data, symbols.decode("utf-8"))
    placements = collect_placements(data)
    collisions = {room: parse_room_custom_collision(data, room)
                  for room in {starts[t]["room"] for t in tracks} if 0 < room < ROOM_COUNT}
    report = check_starts(starts, placements, collisions, tracks)
    report.update({
        "rom": str(rom_path.resolve()), "rom_sha256": hashlib.sha256(data).hexdigest(),
        "symbols": str(symbols_path.resolve()), "symbols_sha256": hashlib.sha256(symbols).hexdigest(),
        "compiled_track_count": TRACK_COUNT, "rooms_scanned": ROOM_COUNT,
        "minecart_placement_count": len(placements), "table_addresses": addresses,
        "limits": ["Requires WLA symbols from this exact ROM build; freshness is not independently proven.",
                   "Checks custom collision stops and initial placements only; riding and return routes are unverified.",
                   "Only selected tracks participate in duplicate-start checks; room-zero tracks are disabled."],
    })
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True, help="Patched, unheadered ROM to read")
    parser.add_argument("--symbols", type=Path, required=True, help="WLA .sym from this exact build")
    parser.add_argument("--tracks", type=parse_tracks, default=parse_tracks("0-3"), help="IDs/ranges or all (default: 0-3)")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--json", action="store_true", help="Alias for --format json")
    args = parser.parse_args(argv)
    try:
        report = audit_rom(args.rom, args.symbols, args.tracks)
    except (OSError, ValueError, IndexError) as exc:
        report = {"status": "error", "error": str(exc)}
    if args.json or args.format == "json":
        print(json.dumps(report, indent=2))
    elif report["status"] == "error":
        print(f"[error] {report['error']}", file=sys.stderr)
    else:
        for row in report["tracks"]:
            start = row["start"]
            print(f"[{row['status']}] track {row['track']}: room ${start['room']:04X}, "
                  f"X ${start['x']:04X}, Y ${start['y']:04X}; {row['initial_match_count']} initial match(es)")
        for issue in report["issues"]:
            print(f"[error] tracks {issue['tracks']}: {issue['code']}: {issue['message']}")
        print(f"{report['issue_count']} finding(s). Initial placement check only; riding remains unverified.")
    return {"pass": 0, "fail": 1, "error": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
