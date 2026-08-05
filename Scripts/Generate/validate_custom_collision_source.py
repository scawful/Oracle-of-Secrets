#!/usr/bin/env python3
"""Validate the canonical Oracle dungeon custom-collision source contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


SOURCE_PATH = Path("Data/dungeons/custom_collision.json")

NUMBER_OF_ROOMS = 296
COLLISION_MAP_WIDTH = 64
COLLISION_MAP_HEIGHT = 64
COLLISION_MAP_TILES = COLLISION_MAP_WIDTH * COLLISION_MAP_HEIGHT
POINTER_TABLE_START = 0x128090
COLLISION_DATA_START = 0x128450
COLLISION_DATA_END_EXCLUSIVE = 0x12E000
WATER_FILL_TABLE_END_EXCLUSIVE = 0x130000

SINGLE_TILE_MARKER = 0xF0F0
END_MARKER = 0xFFFF
ROOM_ID_RE = re.compile(r"^0x[0-9A-F]+$")


class CustomCollisionSourceContractError(RuntimeError):
    """Raised when tracked custom-collision source or ROM data drifts."""


@dataclass(frozen=True)
class CustomCollisionSourceContract:
    room_count: int
    tile_count: int
    source_sha256: str
    rom_sha256: str | None = None


CollisionRooms = dict[int, dict[int, int]]


def _is_integer(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _load_source(source_path: Path) -> tuple[CollisionRooms, bytes, str]:
    try:
        source_bytes = source_path.read_bytes()
    except OSError as exc:
        raise CustomCollisionSourceContractError(
            f"cannot read canonical source {source_path}: {exc}"
        ) from exc

    try:
        source = json.loads(source_bytes)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise CustomCollisionSourceContractError(
            f"canonical source is not valid JSON: {exc}"
        ) from exc

    if not isinstance(source, dict) or set(source) != {"rooms", "version"}:
        raise CustomCollisionSourceContractError(
            "canonical source top-level keys must be exactly "
            "['rooms', 'version']"
        )
    if not _is_integer(source["version"]) or source["version"] != 1:
        raise CustomCollisionSourceContractError(
            "canonical source version must be integer 1"
        )

    room_entries = source["rooms"]
    if not isinstance(room_entries, list):
        raise CustomCollisionSourceContractError(
            "canonical source rooms must be an array"
        )

    rooms: CollisionRooms = {}
    previous_room_id = -1
    for room_index, room_entry in enumerate(room_entries):
        if not isinstance(room_entry, dict) or set(room_entry) != {
            "room_id",
            "tiles",
        }:
            raise CustomCollisionSourceContractError(
                f"canonical source room {room_index} keys must be exactly "
                "['room_id', 'tiles']"
            )

        room_text = room_entry["room_id"]
        if not isinstance(room_text, str) or not ROOM_ID_RE.fullmatch(
            room_text
        ):
            raise CustomCollisionSourceContractError(
                f"canonical source room {room_index} must use an uppercase "
                "hex room_id"
            )
        room_id = int(room_text, 16)
        if not 0 <= room_id < NUMBER_OF_ROOMS:
            raise CustomCollisionSourceContractError(
                f"canonical source room_id {room_text} is outside "
                f"0x000..0x{NUMBER_OF_ROOMS - 1:03X}"
            )
        if room_text != f"0x{room_id:02X}":
            raise CustomCollisionSourceContractError(
                f"canonical source room_id {room_text} is not normalized as "
                f"0x{room_id:02X}"
            )
        if room_id <= previous_room_id:
            raise CustomCollisionSourceContractError(
                "canonical source rooms must be unique and sorted by room_id"
            )
        previous_room_id = room_id

        tile_entries = room_entry["tiles"]
        if not isinstance(tile_entries, list) or not tile_entries:
            raise CustomCollisionSourceContractError(
                f"canonical source room {room_text} must contain nonzero tiles"
            )

        tiles: dict[int, int] = {}
        previous_offset = -1
        for tile_index, tile_entry in enumerate(tile_entries):
            if not isinstance(tile_entry, list) or len(tile_entry) != 2:
                raise CustomCollisionSourceContractError(
                    f"canonical source room {room_text} tile {tile_index} "
                    "must be [offset, value]"
                )
            offset, value = tile_entry
            if not _is_integer(offset) or not 0 <= offset < COLLISION_MAP_TILES:
                raise CustomCollisionSourceContractError(
                    f"canonical source room {room_text} tile {tile_index} "
                    f"offset must be integer 0..{COLLISION_MAP_TILES - 1}"
                )
            if not _is_integer(value) or not 1 <= value <= 0xFF:
                raise CustomCollisionSourceContractError(
                    f"canonical source room {room_text} tile {tile_index} "
                    "value must be integer 1..255"
                )
            if offset <= previous_offset:
                raise CustomCollisionSourceContractError(
                    f"canonical source room {room_text} tiles must be unique "
                    "and sorted by offset"
                )
            previous_offset = offset
            tiles[offset] = value

        rooms[room_id] = tiles

    try:
        canonical_bytes = json.dumps(
            source,
            ensure_ascii=True,
            indent=2,
            sort_keys=True,
        ).encode("ascii")
    except (TypeError, UnicodeEncodeError) as exc:
        raise CustomCollisionSourceContractError(
            f"canonical source cannot be serialized deterministically: {exc}"
        ) from exc
    if source_bytes != canonical_bytes:
        raise CustomCollisionSourceContractError(
            "canonical source is not in deterministic z3ed export format"
        )

    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    return rooms, source_bytes, source_sha256


def _strict_lorom_to_pc(address: int, room_id: int) -> int:
    """Convert a raw ROM pointer only when it is mapped, ROM-backed LoROM."""
    if not 0 <= address <= 0xFFFFFF:
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision pointer 0x{address:X} is "
            "outside 24-bit address space"
        )
    bank = (address >> 16) & 0xFF
    offset = address & 0xFFFF
    if bank in (0x7E, 0x7F, 0xFE, 0xFF):
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision pointer 0x{address:06X} "
            f"uses WRAM bank or mirror 0x{bank:02X}"
        )
    if offset < 0x8000:
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision pointer 0x{address:06X} "
            "is a raw low-half LoROM address"
        )
    pc_address = ((bank & 0x7F) << 15) | (offset & 0x7FFF)
    if pc_address >= 0x3F0000:
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision pointer 0x{address:06X} "
            "maps into the WRAM-backed LoROM PC window"
        )
    return pc_address


def _read_u16(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def _decode_room(data: bytes, room_id: int, snes_pointer: int) -> dict[int, int]:
    cursor = _strict_lorom_to_pc(snes_pointer, room_id)
    if not COLLISION_DATA_START <= cursor < COLLISION_DATA_END_EXCLUSIVE:
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision pointer "
            f"0x{snes_pointer:06X} maps outside collision data "
            f"(PC 0x{cursor:06X})"
        )

    tiles: dict[int, int] = {}
    single_tiles_mode = False
    found_end_marker = False
    while cursor + 1 < COLLISION_DATA_END_EXCLUSIVE:
        offset = _read_u16(data, cursor)
        cursor += 2

        if offset == END_MARKER:
            found_end_marker = True
            break
        if offset == SINGLE_TILE_MARKER:
            single_tiles_mode = True
            continue

        if single_tiles_mode:
            if cursor >= COLLISION_DATA_END_EXCLUSIVE:
                break
            if offset >= COLLISION_MAP_TILES:
                raise CustomCollisionSourceContractError(
                    f"ROM room 0x{room_id:02X} has out-of-range single-tile "
                    f"offset {offset}"
                )
            tiles[offset] = data[cursor]
            cursor += 1
            continue

        if cursor + 1 >= COLLISION_DATA_END_EXCLUSIVE:
            break
        width = data[cursor]
        height = data[cursor + 1]
        cursor += 2
        if width == 0 or height == 0:
            raise CustomCollisionSourceContractError(
                f"ROM room 0x{room_id:02X} has zero-dimension collision "
                f"rectangle {width}x{height}"
            )

        byte_count = width * height
        if cursor + byte_count > COLLISION_DATA_END_EXCLUSIVE:
            raise CustomCollisionSourceContractError(
                f"ROM room 0x{room_id:02X} rectangle crosses the collision "
                "data boundary"
            )
        start_row, start_column = divmod(offset, COLLISION_MAP_WIDTH)
        if (
            offset >= COLLISION_MAP_TILES
            or start_column + width > COLLISION_MAP_WIDTH
            or start_row + height > COLLISION_MAP_HEIGHT
        ):
            raise CustomCollisionSourceContractError(
                f"ROM room 0x{room_id:02X} has an out-of-range collision "
                f"rectangle at offset {offset} with size {width}x{height}"
            )
        for row in range(height):
            row_offset = offset + (row * COLLISION_MAP_WIDTH)
            for column in range(width):
                tiles[row_offset + column] = data[cursor]
                cursor += 1

    if not found_end_marker:
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} collision data is unterminated before "
            "the reserved water-fill region"
        )
    return {offset: value for offset, value in tiles.items() if value != 0}


def _decode_rom(rom_path: Path) -> tuple[CollisionRooms, str]:
    try:
        data = rom_path.read_bytes()
    except OSError as exc:
        raise CustomCollisionSourceContractError(
            f"cannot read ROM {rom_path}: {exc}"
        ) from exc

    pointer_table_end = POINTER_TABLE_START + (NUMBER_OF_ROOMS * 3)
    if len(data) < WATER_FILL_TABLE_END_EXCLUSIVE or len(data) < pointer_table_end:
        raise CustomCollisionSourceContractError(
            f"ROM {rom_path} is too small for the Oracle custom-collision "
            "and reserved water-fill contract"
        )

    rooms: CollisionRooms = {}
    for room_id in range(NUMBER_OF_ROOMS):
        pointer_offset = POINTER_TABLE_START + (room_id * 3)
        snes_pointer = int.from_bytes(
            data[pointer_offset : pointer_offset + 3], "little"
        )
        if snes_pointer == 0:
            continue
        tiles = _decode_room(data, room_id, snes_pointer)
        # A legacy room may own a valid all-zero map. z3ed deliberately omits
        # it from the compact canonical export, so compare effective nonzero
        # maps rather than pointer presence.
        if tiles:
            rooms[room_id] = tiles

    return rooms, hashlib.sha256(data).hexdigest()


def _format_room_ids(room_ids: set[int]) -> str:
    return ", ".join(f"0x{room_id:02X}" for room_id in sorted(room_ids))


def _validate_rom_matches(
    source_rooms: CollisionRooms,
    rom_rooms: CollisionRooms,
) -> None:
    source_ids = set(source_rooms)
    rom_ids = set(rom_rooms)
    missing = source_ids - rom_ids
    unexpected = rom_ids - source_ids
    if missing:
        raise CustomCollisionSourceContractError(
            "ROM is missing canonical custom-collision rooms: "
            f"{_format_room_ids(missing)}"
        )
    if unexpected:
        raise CustomCollisionSourceContractError(
            "ROM has untracked custom-collision rooms: "
            f"{_format_room_ids(unexpected)}"
        )

    for room_id in sorted(source_ids):
        expected = source_rooms[room_id]
        actual = rom_rooms[room_id]
        if expected == actual:
            continue
        differing_offsets = sorted(
            offset
            for offset in set(expected) | set(actual)
            if expected.get(offset, 0) != actual.get(offset, 0)
        )
        preview = ", ".join(str(offset) for offset in differing_offsets[:8])
        suffix = "..." if len(differing_offsets) > 8 else ""
        raise CustomCollisionSourceContractError(
            f"ROM room 0x{room_id:02X} differs from canonical source at "
            f"{len(differing_offsets)} tile(s): {preview}{suffix}"
        )


def validate_contract(
    root: Path,
    rom_path: Path | None = None,
) -> CustomCollisionSourceContract:
    root = root.resolve()
    source_rooms, _, source_sha256 = _load_source(root / SOURCE_PATH)

    rom_sha256 = None
    if rom_path is not None:
        if not rom_path.is_absolute():
            rom_path = root / rom_path
        rom_rooms, rom_sha256 = _decode_rom(rom_path.resolve())
        _validate_rom_matches(source_rooms, rom_rooms)

    return CustomCollisionSourceContract(
        room_count=len(source_rooms),
        tile_count=sum(len(tiles) for tiles in source_rooms.values()),
        source_sha256=source_sha256,
        rom_sha256=rom_sha256,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Oracle repo root (default: repo root)",
    )
    parser.add_argument(
        "--rom",
        type=Path,
        help="optionally require a ROM's effective collision maps to match",
    )
    args = parser.parse_args()

    try:
        contract = validate_contract(args.root, args.rom)
    except CustomCollisionSourceContractError as exc:
        print(
            f"ERROR: custom collision source contract invalid: {exc}",
            file=sys.stderr,
        )
        return 1

    result = (
        "Custom collision source contract valid: "
        f"{contract.room_count} rooms, "
        f"{contract.tile_count} nonzero tiles, "
        f"source SHA-256 {contract.source_sha256}"
    )
    if contract.rom_sha256 is not None:
        result += f", ROM SHA-256 {contract.rom_sha256}"
    print(result)
    return 0


if __name__ == "__main__":
    sys.exit(main())
