#!/usr/bin/env python3
"""Generate runtime WaterFillTable from Yaze custom collision marker tiles.

This script reads room custom-collision streams from ROM (table at $25:8090),
collects offsets with a marker tile value (default: 0xF5), and emits an ASM
include that writes WaterFillTable data into bank $25 at $E000.

Runtime consumer:
  Dungeons/Collision/water_collision.asm (WaterFill_FindRoomInTable)
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Dict, List, Sequence


ROOM_COUNT = 296  # 0x00..0x127
ROOM_POINTER_SNES = 0x258090
WATER_FILL_TABLE_SNES = 0x25E000
CUSTOM_COLLISION_DATA_PC_START = 0x128450
CUSTOM_COLLISION_DATA_PC_END = 0x12E000  # reserved WaterFill table starts here


def snes_to_pc(addr: int) -> int:
    # LoROM mapping
    return ((addr & 0x7F0000) >> 1) | (addr & 0x7FFF)


def read16(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8)


def fmt_hex(v: int, width: int = 2) -> str:
    return f"${v:0{width}X}"


def parse_room_masks(raw: str) -> Dict[int, int]:
    out: Dict[int, int] = {}
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        if "=" not in token:
            raise ValueError(f"Invalid room mask mapping '{token}' (expected room=mask)")
        room_raw, mask_raw = token.split("=", 1)
        room_id = int(room_raw.strip(), 0)
        mask = int(mask_raw.strip(), 0)
        out[room_id] = mask
    return out


def parse_room_custom_collision(data: bytes, room_id: int) -> Dict[int, int]:
    """Decode per-room custom collision tiles by emulating custom_collision.asm format."""
    pointer_table_pc = snes_to_pc(ROOM_POINTER_SNES)
    entry_pc = pointer_table_pc + (room_id * 3)
    if entry_pc + 2 >= len(data):
        return {}

    lo = data[entry_pc]
    hi = data[entry_pc + 1]
    bank = data[entry_pc + 2]
    if lo == 0 and hi == 0:
        return {}

    stream_snes = (bank << 16) | (hi << 8) | lo
    stream_pc = snes_to_pc(stream_snes)
    if stream_pc < 0 or stream_pc >= len(data):
        raise ValueError(f"Room {room_id:02X}: stream pointer out of range ({stream_snes:06X})")

    # Guard against stale/invalid pointers outside the custom-collision data bank.
    # These should be treated as "no custom collision data" for generation.
    if stream_pc < CUSTOM_COLLISION_DATA_PC_START or stream_pc >= CUSTOM_COLLISION_DATA_PC_END:
        return {}

    tiles: Dict[int, int] = {}
    pos = stream_pc
    guard = 0

    while True:
        guard += 1
        if guard > 0x20000:
            raise ValueError(f"Room {room_id:02X}: collision parse guard exceeded")
        if pos + 1 >= len(data):
            raise ValueError(f"Room {room_id:02X}: unexpected EOF reading stream word")

        word = read16(data, pos)
        pos += 2

        # Rectangle block
        if word < 0xF0F0:
            if pos + 1 >= len(data):
                raise ValueError(f"Room {room_id:02X}: unexpected EOF reading rectangle size")
            cols = data[pos]
            rows = data[pos + 1]
            pos += 2

            byte_count = cols * rows
            if pos + byte_count > len(data):
                raise ValueError(f"Room {room_id:02X}: unexpected EOF reading rectangle payload")

            for row in range(rows):
                base = word + (row * 64)
                row_pos = pos + (row * cols)
                for col in range(cols):
                    tiles[base + col] = data[row_pos + col]

            pos += byte_count
            continue

        # Single-tile block (or terminator)
        while True:
            if word == 0xF0F0:
                if pos + 1 >= len(data):
                    raise ValueError(f"Room {room_id:02X}: unexpected EOF after F0F0 sentinel")
                word = read16(data, pos)
                pos += 2
                continue

            if word == 0xFFFF:
                return tiles

            if pos >= len(data):
                raise ValueError(f"Room {room_id:02X}: unexpected EOF reading single tile")
            tiles[word] = data[pos]
            pos += 1

            if pos + 1 >= len(data):
                raise ValueError(f"Room {room_id:02X}: unexpected EOF reading next single offset")
            word = read16(data, pos)
            pos += 2


def collect_marker_offsets(
    data: bytes,
    room_max: int,
    marker_tile: int,
) -> Dict[int, List[int]]:
    out: Dict[int, List[int]] = {}
    upper = min(room_max, ROOM_COUNT - 1)
    for room_id in range(upper + 1):
        tiles = parse_room_custom_collision(data, room_id)
        if not tiles:
            continue
        offsets = sorted(off for off, value in tiles.items() if value == marker_tile)
        if offsets:
            out[room_id] = offsets
    return out


def validate_mask(mask: int) -> bool:
    return mask in {0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80}


def assign_room_masks(
    marker_rooms: Sequence[int],
    explicit_masks: Dict[int, int],
) -> Dict[int, int]:
    assigned: Dict[int, int] = {}
    used_masks = set()

    for room_id in marker_rooms:
        if room_id not in explicit_masks:
            continue
        mask = explicit_masks[room_id]
        if not validate_mask(mask):
            raise ValueError(f"Room {room_id:02X}: invalid mask {mask:#04x} (must be single bit 0x01..0x80)")
        if mask in used_masks:
            raise ValueError(f"Room {room_id:02X}: duplicate mask {mask:#04x}")
        assigned[room_id] = mask
        used_masks.add(mask)

    mask_candidates = [0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80]
    for room_id in marker_rooms:
        if room_id in assigned:
            continue
        next_mask = None
        for mask in mask_candidates:
            if mask not in used_masks:
                next_mask = mask
                break
        if next_mask is None:
            raise ValueError("No free WaterGateStates mask bits remain (max 8 rooms)")
        assigned[room_id] = next_mask
        used_masks.add(next_mask)

    return assigned


def build_layout(marker_offsets: Dict[int, List[int]], room_masks: Dict[int, int]) -> Dict[int, int]:
    rooms = sorted(marker_offsets)
    if len(rooms) > 8:
        raise ValueError(f"Found {len(rooms)} water fill rooms, runtime max is 8")

    # [zone_count] + N*[room_id,mask,off_lo,off_hi]
    running = 1 + (len(rooms) * 4)
    data_offsets: Dict[int, int] = {}

    for room_id in rooms:
        offsets = marker_offsets[room_id]
        if len(offsets) > 0xFF:
            raise ValueError(
                f"Room {room_id:02X}: {len(offsets)} marker tiles, runtime max per room is 255 (db tile_count)"
            )
        for off in offsets:
            if off < 0 or off > 0x0FFF:
                raise ValueError(
                    f"Room {room_id:02X}: marker offset {off:#06x} out of 64x64 collision bounds (0x0000..0x0FFF)"
                )
        data_offsets[room_id] = running
        running += 1 + (len(offsets) * 2)

    table_span = running
    if table_span > 0x2000:
        raise ValueError(f"WaterFillTable span {table_span:#06x} exceeds reserved bank region 0x2000")

    # Keep this check tied to runtime assumptions in WaterFill_FindRoomInTable.
    max_off = max(data_offsets.values(), default=0)
    if max_off > 0x1FFF:
        raise ValueError(f"Data offset {max_off:#06x} exceeds 0x1FFF")

    # Sanity: ensure all rooms have masks.
    for room_id in rooms:
        if room_id not in room_masks:
            raise ValueError(f"Room {room_id:02X}: no assigned mask")

    return data_offsets


def write_asm(
    out_path: Path,
    rom_path: Path,
    marker_tile: int,
    marker_offsets: Dict[int, List[int]],
    room_masks: Dict[int, int],
    data_offsets: Dict[int, int],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    rooms = sorted(marker_offsets)
    lines: List[str] = []
    lines.append("; Auto-generated. Do not edit manually.")
    lines.append("; Generated by scripts/generate_water_fill_table.py")
    lines.append(f"; Source ROM: {rom_path}")
    lines.append(f"; Marker tile: {fmt_hex(marker_tile)}")
    lines.append("; Format at $25E000:")
    lines.append(";   db zone_count")
    lines.append(";   repeat zone_count: db room_id, mask, dw data_offset")
    lines.append(";   data: db tile_count, dw offsets...")
    lines.append("")
    lines.append("pushpc")
    lines.append(f"org {fmt_hex(WATER_FILL_TABLE_SNES, 6)}")
    lines.append("WaterFillTable_Generated:")
    lines.append("{")
    lines.append(f"  db {fmt_hex(len(rooms))}")
    for room_id in rooms:
        mask = room_masks[room_id]
        data_off = data_offsets[room_id]
        lines.append(
            "  db "
            f"{fmt_hex(room_id)}, {fmt_hex(mask)} : dw {fmt_hex(data_off, 4)}"
            f" ; tiles={len(marker_offsets[room_id])}"
        )
    lines.append("}")
    lines.append("")

    for room_id in rooms:
        offsets = marker_offsets[room_id]
        lines.append(f"WaterFillData_Room{room_id:02X}:")
        lines.append("{")
        lines.append(f"  db {fmt_hex(len(offsets))} ; mask={fmt_hex(room_masks[room_id])}")
        for i in range(0, len(offsets), 10):
            chunk = offsets[i : i + 10]
            lines.append("  dw " + ", ".join(fmt_hex(off, 4) for off in chunk))
        lines.append("}")
        lines.append("")

    lines.append("pullpc")
    lines.append("")
    out_path.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate WaterFillTable from custom collision marker tiles."
    )
    parser.add_argument("--rom", type=Path, required=True, help="Source ROM path (typically Yaze-edited ROM).")
    parser.add_argument(
        "--out-asm",
        type=Path,
        default=Path("Dungeons/generated/water_fill_table.asm"),
        help="Output ASM include path.",
    )
    parser.add_argument(
        "--room-max",
        type=lambda s: int(s, 0),
        default=0xFF,
        help="Max room id to scan (default: 0xFF). Runtime room id ($A0) is 8-bit.",
    )
    parser.add_argument(
        "--marker-tile",
        type=lambda s: int(s, 0),
        default=0xF5,
        help="Custom collision tile value used to mark water fill zones.",
    )
    parser.add_argument(
        "--room-masks",
        default="0x27=0x01,0x25=0x02",
        help="Comma-separated room=mask pairs (single-bit masks in WaterGateStates).",
    )
    args = parser.parse_args()

    if args.room_max > 0xFF:
        raise SystemExit("--room-max must be <= 0xFF (runtime room id in $A0 is 8-bit)")
    if args.marker_tile < 0 or args.marker_tile > 0xFF:
        raise SystemExit("--marker-tile must be 0x00..0xFF")

    rom_path = args.rom
    if not rom_path.exists():
        raise SystemExit(f"ROM not found: {rom_path}")

    explicit_masks = parse_room_masks(args.room_masks)
    for room_id, mask in explicit_masks.items():
        if room_id < 0 or room_id > 0xFF:
            raise SystemExit(f"Invalid room in --room-masks: {room_id:#x} (must be 0x00..0xFF)")
        if not validate_mask(mask):
            raise SystemExit(f"Invalid mask for room {room_id:#x}: {mask:#x} (must be single bit 0x01..0x80)")

    rom_data = rom_path.read_bytes()
    marker_offsets = collect_marker_offsets(
        rom_data,
        room_max=args.room_max,
        marker_tile=args.marker_tile,
    )
    rooms = sorted(marker_offsets)
    room_masks = assign_room_masks(rooms, explicit_masks)
    data_offsets = build_layout(marker_offsets, room_masks)

    write_asm(
        out_path=args.out_asm,
        rom_path=rom_path,
        marker_tile=args.marker_tile,
        marker_offsets=marker_offsets,
        room_masks=room_masks,
        data_offsets=data_offsets,
    )

    print(f"Wrote {args.out_asm}")
    print(f"  rooms: {len(rooms)}")
    if rooms:
        print("  room masks:")
        for room_id in rooms:
            print(
                f"    {fmt_hex(room_id)} -> {fmt_hex(room_masks[room_id])}"
                f" ({len(marker_offsets[room_id])} tiles)"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
