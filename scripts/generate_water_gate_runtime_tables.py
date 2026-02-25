#!/usr/bin/env python3
"""Generate water gate runtime tables from Yaze-authored room data.

Outputs ASM tables for:
- room -> flood/swim overlay object stream (object ids 0xC9/0xD9 by default)
- room -> Zora Baby post-switch cutscene target

This lets designers move objects in Yaze and keep runtime behavior/data in sync
without hand-editing ASM byte tables.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Tuple


ROOM_COUNT = 296  # 0x00..0x127

# PC addresses (from Yaze's dungeon_rom_addresses.h)
ROOM_OBJECT_POINTER_PC = 0x874C
ROOMS_SPRITE_POINTER_PC = 0x4C298

# Sprite IDs used by Zora Baby switch interactions.
SWITCH_SPRITE_IDS = {0x21, 0x04}


@dataclass(frozen=True)
class RoomObject:
    obj_id: int
    x: int
    y: int
    size: int
    layer: int
    b1: int
    b2: int
    b3: int


@dataclass(frozen=True)
class RoomSprite:
    spr_id: int
    x: int
    y: int
    subtype: int
    layer: int


def read24(data: bytes, offset: int) -> int:
    return data[offset] | (data[offset + 1] << 8) | (data[offset + 2] << 16)


def snes_to_pc(addr: int) -> int:
    # LoROM mapping
    return ((addr & 0x7F0000) >> 1) | (addr & 0x7FFF)


def parse_hex_list(raw: str) -> List[int]:
    out: List[int] = []
    for part in raw.split(","):
        token = part.strip()
        if not token:
            continue
        out.append(int(token, 0))
    return out


def decode_room_object(b1: int, b2: int, b3: int, layer: int) -> RoomObject:
    # Matches Yaze room_object.cc DecodeObjectFromBytes.
    if b1 >= 0xFC:
        obj_id = (b3 & 0x3F) | 0x100
        x = ((b2 & 0xF0) >> 4) | ((b1 & 0x03) << 4)
        y = ((b2 & 0x0F) << 2) | ((b3 & 0xC0) >> 6)
        size = 0
    elif b3 >= 0xF8:
        obj_id = (b3 << 4) | 0x80 | (((b2 & 0x03) << 2) + (b1 & 0x03))
        x = (b1 & 0xFC) >> 2
        y = (b2 & 0xFC) >> 2
        size = ((b1 & 0x03) << 2) | (b2 & 0x03)
    else:
        obj_id = b3
        x = (b1 & 0xFC) >> 2
        y = (b2 & 0xFC) >> 2
        size = ((b1 & 0x03) << 2) | (b2 & 0x03)

    return RoomObject(
        obj_id=obj_id,
        x=x,
        y=y,
        size=size,
        layer=layer,
        b1=b1,
        b2=b2,
        b3=b3,
    )


def parse_room_objects(data: bytes, room_id: int) -> List[RoomObject]:
    object_table_pc = snes_to_pc(read24(data, ROOM_OBJECT_POINTER_PC))
    room_ptr_pc = object_table_pc + (room_id * 3)
    room_stream_pc = snes_to_pc(read24(data, room_ptr_pc))

    pos = room_stream_pc + 2  # skip floor/layout bytes
    layer = 0
    in_door_list = False
    out: List[RoomObject] = []

    guard = 0
    while pos + 1 < len(data) and guard < 0x8000:
        guard += 1
        b1 = data[pos]
        b2 = data[pos + 1]

        if b1 == 0xFF and b2 == 0xFF:
            pos += 2
            layer += 1
            in_door_list = False
            if layer == 3:
                break
            continue

        if b1 == 0xF0 and b2 == 0xFF:
            pos += 2
            in_door_list = True
            continue

        if in_door_list:
            # Doors are 2-byte entries until 0xFFFF.
            pos += 2
            continue

        if pos + 2 >= len(data):
            break
        b3 = data[pos + 2]
        pos += 3
        out.append(decode_room_object(b1, b2, b3, layer))

    return out


def parse_room_sprites(data: bytes, room_id: int) -> List[RoomSprite]:
    # Matches Yaze Room::LoadSprites.
    sprite_ptr_table_snes = (0x09 << 16) | (data[ROOMS_SPRITE_POINTER_PC + 1] << 8) | data[ROOMS_SPRITE_POINTER_PC]
    sprite_ptr_table_pc = snes_to_pc(sprite_ptr_table_snes)
    ptr_off = sprite_ptr_table_pc + (room_id * 2)
    sprite_stream_snes = (0x09 << 16) | (data[ptr_off + 1] << 8) | data[ptr_off]
    sprite_stream_pc = snes_to_pc(sprite_stream_snes)

    pos = sprite_stream_pc + 1  # first byte is SortSprites mode
    out: List[RoomSprite] = []
    guard = 0
    while pos + 2 < len(data) and guard < 512:
        guard += 1
        b1 = data[pos]
        if b1 == 0xFF:
            break
        b2 = data[pos + 1]
        b3 = data[pos + 2]

        out.append(
            RoomSprite(
                spr_id=b3,
                x=b2 & 0x1F,
                y=b1 & 0x1F,
                subtype=((b2 & 0xE0) >> 5) + ((b1 & 0x60) >> 2),
                layer=(b1 & 0x80) >> 7,
            )
        )
        pos += 3

    return out


def choose_switch_targets(
    objects: Sequence[RoomObject],
    sprites: Sequence[RoomSprite],
    target_marker_ids: Sequence[int],
) -> List[Tuple[int, int, int, int, int]]:
    switches = [s for s in sprites if s.spr_id in SWITCH_SPRITE_IDS]
    if not switches:
        return []

    candidates = [o for o in objects if o.obj_id in target_marker_ids]
    if not candidates:
        return []

    # Convert sprite coords (0..31, ~8px grid) into object-space (~4px grid).
    sx_obj = switches[0].x * 2
    sy_obj = switches[0].y * 2

    marker_pri = {obj_id: idx for idx, obj_id in enumerate(target_marker_ids)}

    def rank(obj: RoomObject) -> Tuple[int, int, int, int]:
        pri = marker_pri.get(obj.obj_id, 999)
        dist = abs(obj.x - sx_obj) + abs(obj.y - sy_obj)
        return (pri, dist, obj.y, obj.x)

    ordered = sorted(candidates, key=rank)
    out: List[Tuple[int, int, int, int, int]] = []
    for obj in ordered:
        target_x_px = (obj.x << 2) & 0xFF
        target_y_px = (obj.y << 2) & 0xFF
        out.append((obj.obj_id, obj.x, obj.y, target_x_px, target_y_px))
    return out


def fmt_hex(v: int, width: int = 2) -> str:
    return f"${v:0{width}X}"


def generate_tables(
    data: bytes,
    room_max: int,
    overlay_object_ids: Sequence[int],
    target_marker_ids: Sequence[int],
) -> Tuple[Dict[int, List[RoomObject]], Dict[int, List[Tuple[int, int, int, int, int]]]]:
    overlays: Dict[int, List[RoomObject]] = {}
    targets: Dict[int, List[Tuple[int, int, int, int, int]]] = {}

    for room_id in range(min(ROOM_COUNT, room_max + 1)):
        objects = parse_room_objects(data, room_id)
        sprites = parse_room_sprites(data, room_id)

        room_overlay = [o for o in objects if o.obj_id in overlay_object_ids]
        if room_overlay:
            overlays[room_id] = room_overlay

        room_targets = choose_switch_targets(objects, sprites, target_marker_ids)
        if room_targets:
            targets[room_id] = room_targets

    return overlays, targets


def write_asm(
    out_path: Path,
    rom_path: Path,
    overlays: Dict[int, List[RoomObject]],
    targets: Dict[int, List[Tuple[int, int, int, int, int]]],
    overlay_object_ids: Sequence[int],
    target_marker_ids: Sequence[int],
) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)

    lines: List[str] = []
    lines.append("; Auto-generated. Do not edit manually.")
    lines.append("; Generated by scripts/generate_water_gate_runtime_tables.py")
    lines.append(f"; Source ROM: {rom_path}")
    lines.append(f"; Overlay object IDs: {', '.join(fmt_hex(x) for x in overlay_object_ids)}")
    lines.append(f"; Target marker IDs (priority): {', '.join(fmt_hex(x, 4) for x in target_marker_ids)}")
    lines.append("")

    lines.append("WaterOverlayData_Empty:")
    lines.append("{")
    lines.append("  db $FF, $FF")
    lines.append("}")
    lines.append("")

    lines.append("WaterOverlayRoomTable:")
    lines.append("{")
    lines.append("  ; db room_id, dw pointer")
    for room_id in sorted(overlays):
        lines.append(f"  db {fmt_hex(room_id)} : dw WaterOverlayData_Room{room_id:02X}")
    lines.append("  db $FF")
    lines.append("}")
    lines.append("")

    for room_id in sorted(overlays):
        entries = overlays[room_id]
        lines.append(f"WaterOverlayData_Room{room_id:02X}:")
        lines.append("{")
        for obj in entries:
            lines.append(
                "  db "
                f"{fmt_hex(obj.b1)}, {fmt_hex(obj.b2)}, {fmt_hex(obj.b3)}"
                f" ; id={fmt_hex(obj.obj_id, 4)} x={obj.x} y={obj.y} size={obj.size} layer={obj.layer}"
            )
        lines.append("  db $FF, $FF")
        lines.append("}")
        lines.append("")

    lines.append("ZoraBabySwitchTargetTable:")
    lines.append("{")
    lines.append("  ; db room_id, target_x_px, target_y_px")
    for room_id in sorted(targets):
        for marker_id, obj_x, obj_y, tx, ty in targets[room_id]:
            lines.append(
                "  db "
                f"{fmt_hex(room_id)}, {fmt_hex(tx)}, {fmt_hex(ty)}"
                f" ; marker={fmt_hex(marker_id, 4)} obj=({obj_x},{obj_y})"
            )
    lines.append("  db $FF")
    lines.append("}")
    lines.append("")

    out_path.write_text("\n".join(lines))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate room-authored runtime tables for water gate overlays and Zora Baby switch paths."
    )
    parser.add_argument("--rom", type=Path, required=True, help="Source ROM path (typically base ROM edited by Yaze).")
    parser.add_argument(
        "--out-asm",
        type=Path,
        default=Path("Dungeons/generated/water_gate_runtime_tables.asm"),
        help="Output ASM include path.",
    )
    parser.add_argument(
        "--room-max",
        type=lambda s: int(s, 0),
        default=0xFF,
        help="Max room id to include (default: 0xFF).",
    )
    parser.add_argument(
        "--overlay-object-ids",
        default="0xC9,0xD9",
        help="Comma-separated type-1 object IDs to export as overlay streams.",
    )
    parser.add_argument(
        "--target-marker-ids",
        default="0x124,0x137,0x135",
        help="Comma-separated marker object IDs for Zora Baby switch target lookup (priority order).",
    )
    args = parser.parse_args()

    rom_path = args.rom
    if not rom_path.exists():
        raise SystemExit(f"ROM not found: {rom_path}")
    if args.room_max > 0xFF:
        raise SystemExit("--room-max must be <= 0xFF (runtime room id in $A0 is 8-bit).")

    overlay_ids = parse_hex_list(args.overlay_object_ids)
    marker_ids = parse_hex_list(args.target_marker_ids)

    rom_data = rom_path.read_bytes()
    overlays, targets = generate_tables(
        rom_data,
        room_max=args.room_max,
        overlay_object_ids=overlay_ids,
        target_marker_ids=marker_ids,
    )

    write_asm(
        out_path=args.out_asm,
        rom_path=rom_path,
        overlays=overlays,
        targets=targets,
        overlay_object_ids=overlay_ids,
        target_marker_ids=marker_ids,
    )

    target_entries = sum(len(v) for v in targets.values())
    print(f"Wrote {args.out_asm}")
    print(f"  overlay rooms: {len(overlays)}")
    print(f"  switch target rooms: {len(targets)}")
    print(f"  switch target entries: {target_entries}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
