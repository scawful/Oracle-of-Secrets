#!/usr/bin/env python3
"""Author Oracle water-fill marker tiles via z3ed with reusable presets.

This script writes marker tile 0xF5 into room custom collision data so
`scripts/generate_water_fill_table.py` can build runtime water-fill zones.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Set, Tuple


Coord = Tuple[int, int]


@dataclass(frozen=True)
class Rect:
    x1: int
    y1: int
    x2: int
    y2: int

    def coords(self) -> Set[Coord]:
        out: Set[Coord] = set()
        for y in range(self.y1, self.y2 + 1):
            for x in range(self.x1, self.x2 + 1):
                out.add((x, y))
        return out


def _room_hex(room_id: int) -> str:
    return f"0x{room_id:02X}"


def _parse_hex(value: str) -> int:
    return int(value, 0)


def _validate_coord(x: int, y: int) -> None:
    if not (0 <= x <= 63 and 0 <= y <= 63):
        raise ValueError(f"Coordinate out of range: ({x},{y})")


def preset_room25_lower_band() -> Set[Coord]:
    # Lower-half drain band (visual water/grate lane).
    return Rect(5, 45, 60, 47).coords()


def preset_room27_upside_t() -> Set[Coord]:
    # Upside-T with right-side dry lane for stair/chest access.
    # Horizontal bar: lower basin.
    # Stem: dam channel.
    out = set()
    out |= Rect(5, 41, 52, 43).coords()
    out |= Rect(42, 15, 44, 40).coords()
    return out


PRESETS: Dict[str, Dict[int, Set[Coord]]] = {
    "room25_lower_band": {
        0x25: preset_room25_lower_band(),
    },
    "room27_upside_t": {
        0x27: preset_room27_upside_t(),
    },
    "zora_d4": {
        0x25: preset_room25_lower_band(),
        0x27: preset_room27_upside_t(),
    },
}


def sanitize_known_bad_collision_pointer(rom_path: Path) -> bool:
    """Fix known room-0 pointer sentinel that blocks z3ed write preflight.

    Some ROM variants carry room 0 pointer bytes as 80 00 00 at 0x128090.
    z3ed's write preflight rejects this as "points before data region".
    """
    data = bytearray(rom_path.read_bytes())
    ptr0_off = 0x128090  # kCustomCollisionRoomPointers + room0*3
    if ptr0_off + 2 >= len(data):
        return False
    if data[ptr0_off : ptr0_off + 3] == b"\x80\x00\x00":
        data[ptr0_off : ptr0_off + 3] = b"\x00\x00\x00"
        rom_path.write_bytes(data)
        return True
    return False


def run_json(cmd: Sequence[str]) -> dict:
    proc = subprocess.run(cmd, check=False, text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(
            f"Command failed ({proc.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        )
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            f"Failed to parse JSON from command: {' '.join(cmd)}\n"
            f"stdout:\n{proc.stdout}\n"
            f"stderr:\n{proc.stderr}"
        ) from exc


def get_room_markers(z3ed: Path, rom: Path, room_id: int, marker_tile: int) -> Set[Coord]:
    data = run_json(
        [
            str(z3ed),
            "dungeon-list-custom-collision",
            f"--room={_room_hex(room_id)}",
            "--nonzero",
            f"--rom={rom}",
            "--format=json",
        ]
    )
    entries = data.get("Dungeon Custom Collision", {}).get("tiles", [])
    out: Set[Coord] = set()
    for entry in entries:
        tile_raw = entry.get("tile", "0x00")
        tile = int(str(tile_raw), 0)
        if tile == marker_tile:
            x = int(entry["x"])
            y = int(entry["y"])
            _validate_coord(x, y)
            out.add((x, y))
    return out


def _build_tile_ops(coords: Iterable[Coord], tile: int) -> List[str]:
    out: List[str] = []
    for x, y in sorted(coords, key=lambda c: (c[1], c[0])):
        _validate_coord(x, y)
        out.append(f"{x},{y},0x{tile:02X}")
    return out


def apply_ops(
    z3ed: Path,
    rom: Path,
    room_id: int,
    tile_ops: Sequence[str],
    write: bool,
    chunk_size: int = 120,
) -> None:
    if not tile_ops:
        return

    for idx in range(0, len(tile_ops), chunk_size):
        chunk = tile_ops[idx : idx + chunk_size]
        cmd = [
            str(z3ed),
            "dungeon-set-collision-tile",
            f"--room={_room_hex(room_id)}",
            f"--tiles={';'.join(chunk)}",
            f"--rom={rom}",
            "--format=json",
        ]
        if write:
            cmd.insert(3, "--write")
        run_json(cmd)


def merge_presets(preset_names: Sequence[str]) -> Dict[int, Set[Coord]]:
    merged: Dict[int, Set[Coord]] = {}
    for name in preset_names:
        if name not in PRESETS:
            valid = ", ".join(sorted(PRESETS))
            raise ValueError(f"Unknown preset '{name}'. Valid: {valid}")
        for room_id, coords in PRESETS[name].items():
            merged.setdefault(room_id, set()).update(coords)
    return merged


def summarize_room(room_id: int, target: Set[Coord], existing: Set[Coord]) -> str:
    to_add = target - existing
    to_remove = existing - target
    return (
        f"{_room_hex(room_id)} "
        f"target={len(target)} existing={len(existing)} "
        f"add={len(to_add)} remove={len(to_remove)}"
    )


def parse_room_overrides(values: Sequence[str]) -> Dict[int, Set[Coord]]:
    # Format: room:x1,y1-x2,y2
    out: Dict[int, Set[Coord]] = {}
    for raw in values:
        if ":" not in raw:
            raise ValueError(f"Invalid --add-rect '{raw}' (expected room:x1,y1-x2,y2)")
        room_raw, rect_raw = raw.split(":", 1)
        room_id = int(room_raw, 0)

        if "-" not in rect_raw:
            raise ValueError(f"Invalid --add-rect '{raw}' (missing '-')")
        start_raw, end_raw = rect_raw.split("-", 1)
        x1_raw, y1_raw = start_raw.split(",", 1)
        x2_raw, y2_raw = end_raw.split(",", 1)
        rect = Rect(int(x1_raw, 0), int(y1_raw, 0), int(x2_raw, 0), int(y2_raw, 0))
        out.setdefault(room_id, set()).update(rect.coords())
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Apply water-fill marker presets to room custom collision via z3ed."
    )
    parser.add_argument(
        "--rom",
        type=Path,
        required=True,
        help="ROM path to edit (typically Roms/oos168x.sfc).",
    )
    parser.add_argument(
        "--z3ed",
        type=Path,
        default=Path("/Users/scawful/src/hobby/yaze/scripts/z3ed"),
        help="Path to z3ed launcher.",
    )
    parser.add_argument(
        "--preset",
        action="append",
        default=[],
        help="Preset name (repeatable). Available: room25_lower_band, room27_upside_t, zora_d4",
    )
    parser.add_argument(
        "--add-rect",
        action="append",
        default=[],
        help="Extra rectangle to include: room:x1,y1-x2,y2 (repeatable).",
    )
    parser.add_argument(
        "--marker-tile",
        type=_parse_hex,
        default=0xF5,
        help="Marker tile value (default: 0xF5).",
    )
    parser.add_argument(
        "--write",
        action="store_true",
        help="Persist edits to ROM (default: dry-run).",
    )
    parser.add_argument(
        "--sanitize-z3ed-preflight",
        action="store_true",
        help="Before write, patch known room-0 pointer sentinel (80 00 00 -> 00 00 00).",
    )
    parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="Keep existing marker positions even if not in the target set.",
    )
    args = parser.parse_args()

    if not args.rom.exists():
        raise SystemExit(f"ROM not found: {args.rom}")
    if not args.z3ed.exists():
        raise SystemExit(f"z3ed not found: {args.z3ed}")
    if not args.preset and not args.add_rect:
        raise SystemExit("Nothing to do: provide --preset and/or --add-rect")

    targets = merge_presets(args.preset)
    rect_overrides = parse_room_overrides(args.add_rect)
    for room_id, coords in rect_overrides.items():
        targets.setdefault(room_id, set()).update(coords)

    for room_id, coords in targets.items():
        for x, y in coords:
            _validate_coord(x, y)

    print(f"ROM: {args.rom}")
    print(f"z3ed: {args.z3ed}")
    print(f"mode: {'WRITE' if args.write else 'DRY-RUN'}")
    print(f"marker tile: 0x{args.marker_tile:02X}")

    if args.write and args.sanitize_z3ed_preflight:
        changed = sanitize_known_bad_collision_pointer(args.rom)
        if changed:
            print("sanitized: room0 collision pointer 80 00 00 -> 00 00 00")

    for room_id in sorted(targets):
        target = set(targets[room_id])
        existing = get_room_markers(args.z3ed, args.rom, room_id, args.marker_tile)
        print(summarize_room(room_id, target, existing))

        to_add = target - existing
        to_remove: Set[Coord]
        if args.keep_existing:
            to_remove = set()
        else:
            to_remove = existing - target

        ops = _build_tile_ops(to_remove, 0x00) + _build_tile_ops(to_add, args.marker_tile)

        if ops:
            apply_ops(args.z3ed, args.rom, room_id, ops, write=args.write)

        if args.write:
            readback = get_room_markers(args.z3ed, args.rom, room_id, args.marker_tile)
            if args.keep_existing:
                if not target.issubset(readback):
                    missing = sorted(target - readback)[:10]
                    raise RuntimeError(
                        f"Readback failed for {_room_hex(room_id)} (missing target markers): {missing}"
                    )
            else:
                if readback != target:
                    missing = sorted(target - readback)[:10]
                    extra = sorted(readback - target)[:10]
                    raise RuntimeError(
                        f"Readback mismatch for {_room_hex(room_id)} "
                        f"(missing={missing}, extra={extra})"
                    )
            print(f"  readback ok: {_room_hex(room_id)} markers={len(readback)}")

    print("done")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        raise SystemExit(130)
