#!/usr/bin/env python3
"""Guarded dry run / apply for the Sky D8 rooms $90-$92 prototype byte recipe.

Bound to one reviewed recipe (schema sky-d8-room-authoring-proposal/v1, pinned
sha256 and pinned field values) and one base ROM (oos168.sfc, pinned sha256).
The recipe is a custom proposed-byte payload, not a z3ed import schema.

Default: dry run. Builds the patched ROM in memory, audits every room's header,
object/door, sprite and pot stream plus the chest table, and prints a JSON
report. Nothing is written.

  python3 Scripts/Rooms/sky_d8_room_writer.py --rom BASE.sfc \
      --recipe AUTHORING_RECIPE.json --manifest hack_manifest.json

--write also needs --output and --rollback: two new files (never existing),
outside the shared checkout. The input ROM is only ever opened read-only.
There is no override flag. The SNES header checksum is not recomputed; the
normal build owns assembly and checksum.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Iterable, Sequence

TOOL = "sky_d8_room_writer"
TOOL_VERSION = 1

ROM_SIZE = 0x200000
ROOM_COUNT = 296
TARGET_ROOMS = (0x90, 0x91, 0x92)

SHARED_CHECKOUT = Path("/Users/scawful/src/hobby/oracle-of-secrets")
DEFAULT_PROTECTED_DIRS = (SHARED_CHECKOUT / "Roms", SHARED_CHECKOUT)


@dataclass(frozen=True)
class Pins:
    base_sha256: str
    base_sha1: str
    recipe_sha256: str
    chest_table_sha256: str


DEFAULT_PINS = Pins(
    base_sha256="5689b1d383331b383670bdbb2d8470443d9431e22678e90d184ca5f8fad85b62",
    base_sha1="86f51331e2efdece28e6424ac294ed47e8a644f0",
    recipe_sha256="2d9ad8f5bc1ced7d295e39d0ac9e6d07cc7048a655ea1558269ecb768f87250b",
    chest_table_sha256="c9e388a969b6ce5059dfc89692555b63408096d691ce51f0d7b77c38bc9e6406",
)

# --- ROM layout (PC offsets, unheadered LoROM) -----------------------------

HEADER_ROOT_PC, HEADER_ROOT = 0x00B5DD, "008022"
HEADER_BANK_PC, HEADER_BANK = 0x00B5E7, 0x22
HEADER_SIZE = 14
OBJECT_ROOT_PC, OBJECT_ROOT = 0x00874C, "00801f"
OBJECT_TABLE_PC = 0x0F8000
DOOR_TABLE_PC = 0x0F83C0
DOOR_ROOT_OPERANDS = ((0x00B6CC, "c0831f"), (0x00B7FE, "c0831f"))
SPRITE_ROOT_PC, SPRITE_ROOT = 0x04C298, "b2d2"
SPRITE_TABLE_PC, SPRITE_BANK = 0x04D2B2, 0x09
POT_TABLE_PC, POT_BANK = 0x00DB69, 0x01

OBJECT_DATA_REGIONS = ((0x050000, 0x053730), (0x0F878A, 0x100000), (0x01EB90, 0x020000),
                       (0x138000, 0x140000), (0x148000, 0x150000))
OBJECT_ALLOC_REGION = (0x148000, 0x150000)
SPRITE_REGION = (0x04D502, 0x04EC9F)
POT_REGION = (0x00DDE7, 0x00E6B2)

CHEST_TABLE_PC, CHEST_CAPACITY = 0x00E96E, 0x1F8
CHEST_SIZE_OPERAND_PC = 0x00EBF6
CHEST_CODE_GUARDS = ((0x00EBF5, "e0"), (0x00EBF8, "f0"), (0x00EBFA, "bf6ee901"),
                     (0x00EC09, "bf70e901"), (0x00EC0F, "bf6ee901"))

ENTRANCE_ID = 0x29
# Base loader at $02:D99F JSLs $0F:F008, then reads $8000/$8C00/$8E00,X and $8200,Y
# ($02:D9A3/$D9AB/$D9CB/$DA1A). $8C00 feeds $E8 (vertical scroll).
ENTRANCE_CODE_GUARDS = ((0x01599F, "2208f00f"), (0x0159A3, "bd0080"), (0x0159AB, "bd008c"),
                        (0x0159CB, "bd008e"), (0x015A1A, "b90082"))
ENTRANCE_ROOM_TABLE = 0x078000
ENTRANCE_FIELDS = (  # name, table PC, width, before, after
    ("ypos", 0x078E00, 2, "d80d", "d813"),
    ("yscroll", 0x078C00, 2, "100d", "1013"),
    ("edges", 0x078200, 8, "0d0c0d0d01000101", "1312131301000101"),
)

OBJECT_STREAMS = {  # room: (pc, object pointer, door pointer, full old stream)
    0x90: (0x050091, "91808a", "b4808a",
           "010cc40c05b40c05fee139fe6a24ff6a24b48c05c48c05b46c06c46c06fffffffff0ff810a8000ffff"),
    0x91: (0x0504F6, "f6848a", "34858a",
           "0100440c05340c05c40c05b40c05fee138348c05448c05c48c05b48c05346c06446c06c46c06b46c06"
           "84b86584c8656cb8666cc866fce139fffffffff0ff800082006000ffff"),
    0x92: (0x0509BD, "bd898a", "168a8a",
           "0100440c05340c05fce138348c05448c05c48c05b48c05346c06446c06c46c06b46c0684b86584c865"
           "6cb8666cc866aa2834a82e33aa5c34a62a71da2a71a83e33a84e33bd42f9a8243dd0243da84c3dd04c3d"
           "fffffffff0ff600082008000ffff"),
}
EXPECTED_ALLOC_PC = 0x148338
EXPECTED_POINTERS_AFTER = {  # room: (object pointer, door pointer)
    0x90: ("91808a", "b1808a"),
    0x91: ("388329", "798329"),
    0x92: ("bd898a", "108a8a"),
}

# --- Pinned recipe fields (exact JSON values the tool reads) -----------------

_TAG24 = "0x24"
PINNED_RECIPE_FIELDS: tuple[tuple[tuple[str, ...], Any], ...] = (
    (("schema",), "sky-d8-room-authoring-proposal/v1"),
    (("kind",), "custom proposed byte recipe; not an accepted z3ed schema"),
    (("base_rom", "sha256_before"), DEFAULT_PINS.base_sha256),
    (("rooms", "0x90", "header"), {
        "pc": "0x110A60", "before": "0005011600250000000c91000000",
        "after": "0005011600000000000c00000000",
        "changes": ["tag1 0x25->0x00 (inherited boss role removed)", "stair1 0x91->0x00"],
        "kept": ["holewarp 0x0C inert header-only"]}),
    (("rooms", "0x90", "object_stream"), {
        "pc": "0x050091", "pointer_slot_pc": "0x0F81B0", "pointer_bytes": "91808a",
        "len_before": 41, "len_after": 40, "placement": "in place",
        "erase": [{"list": 0, "index": 2, "id": "0x139", "x": 46, "y": 4, "bytes": "fee139"}],
        "doors_add": [{"bytes": "8300", "dir": "E", "pos": 8, "tile": [58, 47], "type": "0x00"}],
        "after_hex": "010c c40c05 b40c05 fe6a24 ff6a24 b48c05 c48c05 b46c06 c46c06 ffff ffff f0ff "
                     "810a 8000 8300 ffff"}),
    (("rooms", "0x90", "sprites"), "unchanged (081b18, 071426)"),
    (("rooms", "0x90", "pots"), "none"),
    (("rooms", "0x90", "chests"), "none"),
    (("rooms", "0x91", "header"), {
        "pc": "0x110A6E", "before": "0005010a00000000000090920000",
        "after": "0005010a00240000000000000000"}),
    (("rooms", "0x91", "object_stream", "pc"), "0x0504F6"),
    (("rooms", "0x91", "object_stream", "pointer_slot_pc"), "0x0F81B3"),
    (("rooms", "0x91", "object_stream", "pointer_bytes_before"), "f6848a"),
    (("rooms", "0x91", "object_stream", "len_before"), 70),
    (("rooms", "0x91", "object_stream", "len_after"), 77),
    (("rooms", "0x91", "object_stream", "erase"), [
        {"list": 0, "index": 17, "id": "0x139", "x": 14, "y": 4, "bytes": "fce139",
         "reason": "bypass stair to $92"},
        {"list": 0, "index": 4, "id": "0x138", "x": 46, "y": 4, "bytes": "fee138"}]),
    (("rooms", "0x91", "object_stream", "objects_add"), [
        {"id": "0xFD0", "name": "pressure plate", "x": 52, "y": 53, "layer": 0,
         "bytes": "d0d4fd", "px": [416, 424, 16, 16]},
        {"id": "0xFAF", "name": "pot", "x": 12, "y": 54, "layer": 0, "bytes": "33dbfa"},
        {"id": "0xFAF", "name": "pot", "x": 18, "y": 54, "layer": 0, "bytes": "4bdbfa"}]),
    (("rooms", "0x91", "object_stream", "doors_add"), [
        {"bytes": "2200", "dir": "W", "pos": 2, "tile": [2, 47], "type": "0x00",
         "role": "free return to $90"},
        {"bytes": "8318", "dir": "E", "pos": 8, "tile": [58, 47],
         "type": "0x18 DoubleSidedShutter", "role": "only shutter"}]),
    (("rooms", "0x91", "object_stream", "after_hex"),
     "0100 440c05 340c05 c40c05 b40c05 348c05 448c05 c48c05 b48c05 346c06 446c06 c46c06 "
     "b46c06 84b865 84c865 6cb866 6cc866 d0d4fd 33dbfa 4bdbfa ffff ffff f0ff 8000 8200 6000 "
     "2200 8318 ffff"),
    (("rooms", "0x91", "sprites", "stream_pc"), "0x04DFCA"),
    (("rooms", "0x91", "sprites", "before"), "00 051584 0808d1 170793 141361 ff"),
    (("rooms", "0x91", "sprites", "after"), "00 ff"),
    (("rooms", "0x91", "pots", "slot_pc"), "0x00DC8B"),
    (("rooms", "0x91", "pots", "slot_before"), "e7dd"),
    (("rooms", "0x91", "pots", "slot_after"), "a9e6"),
    (("rooms", "0x91", "pots", "stream_pc"), "0x00E6A9"),
    (("rooms", "0x91", "pots", "stream_hex"), "181b0c 241b0c ffff"),
    (("rooms", "0x91", "pots", "bytes"), 8),
    (("rooms", "0x91", "pots", "allocatable"), 9),
    (("rooms", "0x91", "pots", "current_unreferenced"), "0bffff0b641c0bffff"),
    (("rooms", "0x91", "chests"), "none"),
    (("rooms", "0x92", "header"), {
        "pc": "0x110A7C", "before": "0005010a00000000000091000000",
        "after": "0005010a00000000000000000000"}),
    (("rooms", "0x92", "object_stream", "pc"), "0x0509BD"),
    (("rooms", "0x92", "object_stream", "pointer_slot_pc"), "0x0F81B6"),
    (("rooms", "0x92", "object_stream", "pointer_bytes"), "bd898a"),
    (("rooms", "0x92", "object_stream", "len_before"), 97),
    (("rooms", "0x92", "object_stream", "len_after"), 93),
    (("rooms", "0x92", "object_stream", "placement"), "in place"),
    (("rooms", "0x92", "object_stream", "erase"), [
        {"list": 0, "index": 22, "id": "0xF99", "name": "chest", "x": 47, "y": 16,
         "bytes": "bd42f9", "note": "prototype cleanup, not an item decision"},
        {"list": 0, "index": 2, "id": "0x138", "x": 14, "y": 4, "bytes": "fce138"}]),
    (("rooms", "0x92", "object_stream", "doors_add"), [
        {"bytes": "2200", "dir": "W", "pos": 2, "tile": [2, 47], "type": "0x00",
         "pairs_with": "$91 E8:18"}]),
    (("rooms", "0x92", "object_stream", "after_hex"),
     "0100 440c05 340c05 348c05 448c05 c48c05 b48c05 346c06 446c06 c46c06 b46c06 84b865 "
     "84c865 6cb866 6cc866 aa2834 a82e33 aa5c34 a62a71 da2a71 a83e33 a84e33 a8243d d0243d "
     "a84c3d d04c3d ffff ffff f0ff 6000 8200 8000 2200 ffff"),
    (("rooms", "0x92", "chest_record_removal", "table_pointer_operand_pc"), "0x00EBFB"),
    (("rooms", "0x92", "chest_record_removal", "table_pointer_bytes"), "6ee901 (unchanged)"),
    (("rooms", "0x92", "chest_record_removal", "record_index"), 57),
    (("rooms", "0x92", "chest_record_removal", "record_pc"), "0x00EA19"),
    (("rooms", "0x92", "chest_record_removal", "record_bytes"), "92001c"),
    (("rooms", "0x92", "chest_record_removal", "size_operand", "operand_pc"), "0x00EBF6"),
    (("rooms", "0x92", "chest_record_removal", "size_operand", "before"), "f801"),
    (("rooms", "0x92", "chest_record_removal", "size_operand", "after"), "f501"),
    (("rooms", "0x92", "chest_record_removal", "record_count"), {"before": 168, "after": 167}),
    (("rooms", "0x92", "sprites"), "unchanged (1a05a4, 160aa4)"),
    (("rooms", "0x92", "pots"), "none"),
    (("inbound", "entrance_0x29", "room"), "0x90"),
    (("inbound", "entrance_0x29", "fields_row6"), {
        "ypos@0x78E52": "0x0DD8", "yscroll@0x78C52": "0x0D10",
        "edges@0x78348": "0d0c0d0d01000101"}),
    (("inbound", "entrance_0x29", "proposed_if_retained"), {
        "ypos": "0x13D8", "yscroll": "0x1310", "edges": "13121313 01000101"}),
)

DIRS = {"N": 0, "S": 1, "W": 2, "E": 3}

LIMITATIONS = [
    "Custom recipe payload bound to one base ROM and one reviewed recipe; not a z3ed schema.",
    "Static byte/structure proof only; no build, emulator, native or gameplay check was run.",
    "Door-pointer slots ($1F:83C0 + room*3) for $90-$92 are updated because the door lists move;"
    " the recipe does not list them.",
    "The SNES header checksum is not recomputed; the normal build owns it.",
    "Entrance 0x29 coordinates are prototype values; CrystalBossRooms $90->$96 stays a separate"
    " future ASM dependency; no boss or prize is activated.",
    "Vacated tails (old $90/$92 stream ends, old $91 stream, $91 sprite bytes after FF, chest"
    " table bytes $EB63-$EB65) keep their old bytes and are unreferenced.",
    "Tag $24 on $91 is safe only in a build containing the PR231 gateway at $01CC89.",
]


class PlanError(Exception):
    """A guard failed; nothing may be written."""


# --- small helpers -------------------------------------------------------------

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def hx(text: str) -> bytes:
    return bytes.fromhex(text.replace(" ", ""))


def snes_to_pc(addr: int) -> int:
    bank, offset = (addr >> 16) & 0x7F, addr & 0xFFFF
    if offset < 0x8000 or bank >= 0x7E:
        raise PlanError(f"SNES address ${addr:06X} is not LoROM ROM space")
    return bank * 0x8000 + (offset - 0x8000)


def pc_to_snes(pc: int) -> int:
    if not 0 <= pc < ROM_SIZE:
        raise PlanError(f"PC 0x{pc:06X} is outside the ROM")
    return ((pc // 0x8000) << 16) | 0x8000 | (pc % 0x8000)


def long_ptr(raw: bytes) -> int:
    return snes_to_pc(raw[0] | raw[1] << 8 | raw[2] << 16)


def bank16_ptr(raw: bytes, bank: int) -> int:
    return snes_to_pc(bank << 16 | raw[0] | raw[1] << 8)


def encode_long(pc: int, mirror_from: bytes | None = None) -> bytes:
    snes = pc_to_snes(pc)
    if mirror_from is not None:
        snes |= mirror_from[2] << 16 & 0x800000
    return bytes((snes & 0xFF, snes >> 8 & 0xFF, snes >> 16 & 0xFF))


def overlaps(a: tuple[int, int], b: tuple[int, int]) -> bool:
    return a[0] < b[1] and b[0] < a[1]


def region_end(pc: int, regions: Iterable[tuple[int, int]], what: str) -> int:
    for start, end in regions:
        if start <= pc < end:
            return end
    raise PlanError(f"{what} pointer 0x{pc:06X} is outside its data regions")


def expect(cond: bool, message: str) -> None:
    if not cond:
        raise PlanError(message)


def expect_bytes(rom: bytes, pc: int, want: bytes, what: str) -> None:
    got = bytes(rom[pc:pc + len(want)])
    expect(got == want, f"{what} preimage at PC 0x{pc:06X}: got {got.hex()}, want {want.hex()}")


# --- object streams ------------------------------------------------------------

@dataclass
class ObjectStream:
    pc: int
    end: int
    header: bytes
    lists: list[list[bytes]]
    has_marker: bool
    doors: list[bytes]
    door_pc: int

    @property
    def raw_len(self) -> int:
        return self.end - self.pc


def parse_object_stream(rom: bytes, start: int, limit: int) -> ObjectStream:
    """Mirror of yaze ParseObjectStream: hdr2, two FFFF lists, list 2 with F0FF doors."""
    def need(cursor: int, n: int, what: str) -> None:
        if cursor + n > limit:
            raise PlanError(f"object stream 0x{start:06X}: {what}")

    need(start, 2, "missing two-byte header")
    cursor = start + 2
    lists: list[list[bytes]] = [[], [], []]
    for index in (0, 1):
        while True:
            need(cursor, 2, f"list {index} has no FFFF terminator")
            if rom[cursor] == 0xFF and rom[cursor + 1] == 0xFF:
                cursor += 2
                break
            need(cursor, 3, f"list {index} truncated record")
            lists[index].append(bytes(rom[cursor:cursor + 3]))
            cursor += 3
    doors: list[bytes] = []
    while True:
        need(cursor, 2, "list 2 has no door marker or terminator")
        if rom[cursor] == 0xF0 and rom[cursor + 1] == 0xFF:
            cursor += 2
            door_pc = cursor
            while True:
                need(cursor, 2, "door list has no terminator")
                if rom[cursor] == 0xFF and rom[cursor + 1] == 0xFF:
                    return ObjectStream(start, cursor + 2, bytes(rom[start:start + 2]), lists,
                                        True, doors, door_pc)
                doors.append(bytes(rom[cursor:cursor + 2]))
                cursor += 2
        if rom[cursor] == 0xFF and rom[cursor + 1] == 0xFF:
            return ObjectStream(start, cursor + 2, bytes(rom[start:start + 2]), lists,
                                False, doors, cursor)
        need(cursor, 3, "list 2 truncated record")
        lists[2].append(bytes(rom[cursor:cursor + 3]))
        cursor += 3


def encode_object_stream(header: bytes, lists: Sequence[Sequence[bytes]],
                         doors: Sequence[bytes]) -> tuple[bytes, int]:
    out = bytearray(header)
    for records in lists[:2]:
        for rec in records:
            out += rec
        out += b"\xff\xff"
    for rec in lists[2]:
        out += rec
    out += b"\xf0\xff"
    door_offset = len(out)
    for door in doors:
        out += door
    out += b"\xff\xff"
    return bytes(out), door_offset


def decode_object(rec: bytes) -> tuple[int, int, int]:
    """(id, x, y) for type-2 ($100-$13F) and type-3 ($F80-$FFF) records."""
    b1, b2, b3 = rec
    if b1 >= 0xFC:
        return 0x100 + (b3 & 0x3F), (b1 & 3) << 4 | b2 >> 4, (b2 & 0xF) << 2 | b3 >> 6
    if b3 >= 0xF8:
        return 0xF80 | (b3 & 7) << 4 | (b2 & 3) << 2 | (b1 & 3), b1 >> 2, b2 >> 2
    raise PlanError(f"object {rec.hex()} is not a type-2/type-3 record")


def encode_type3(obj_id: int, x: int, y: int) -> bytes:
    expect(0xF80 <= obj_id <= 0xFFF and 0 <= x < 64 and 0 <= y < 64,
           f"type-3 object 0x{obj_id:X} ({x},{y}) out of range")
    return bytes((x << 2 | obj_id & 3, y << 2 | obj_id >> 2 & 3, 0xF8 | obj_id >> 4 & 7))


def parse_until_ff(rom: bytes, start: int, limit: int, kind: str) -> int:
    if kind == "sprite":
        expect(start < limit, f"sprite stream 0x{start:06X} missing sort byte")
        cursor = start + 1
        while cursor < limit:
            if rom[cursor] == 0xFF:
                return cursor + 1
            expect(cursor + 3 <= limit, f"sprite stream 0x{start:06X} truncated")
            cursor += 3
        raise PlanError(f"sprite stream 0x{start:06X} has no FF terminator")
    cursor = start
    while True:
        expect(cursor + 2 <= limit, f"pot stream 0x{start:06X} has no FFFF terminator")
        if rom[cursor] == 0xFF and rom[cursor + 1] == 0xFF:
            return cursor + 2
        expect(cursor + 3 <= limit, f"pot stream 0x{start:06X} truncated")
        cursor += 3


# --- full inventory -----------------------------------------------------------

@dataclass
class Inventory:
    header_pc: list[int] = field(default_factory=list)
    obj_ptr: list[bytes] = field(default_factory=list)
    door_ptr: list[bytes] = field(default_factory=list)
    objects: list[ObjectStream] = field(default_factory=list)
    door_target: list[int] = field(default_factory=list)
    spr_ptr: list[bytes] = field(default_factory=list)
    spr_span: list[tuple[int, int]] = field(default_factory=list)
    pot_ptr: list[bytes] = field(default_factory=list)
    pot_span: list[tuple[int, int]] = field(default_factory=list)
    chest_size: int = 0
    chests: list[bytes] = field(default_factory=list)


def check_roots(rom: bytes) -> None:
    expect_bytes(rom, HEADER_ROOT_PC, hx(HEADER_ROOT), "header pointer root")
    expect(rom[HEADER_BANK_PC] == HEADER_BANK, "header bank byte moved")
    expect_bytes(rom, OBJECT_ROOT_PC, hx(OBJECT_ROOT), "object pointer root")
    for pc, want in DOOR_ROOT_OPERANDS:
        expect_bytes(rom, pc, hx(want), "door pointer root")
    expect_bytes(rom, SPRITE_ROOT_PC, hx(SPRITE_ROOT), "sprite pointer root")
    for pc, want in CHEST_CODE_GUARDS:
        expect_bytes(rom, pc, hx(want), "chest lookup code")
    for pc, want in ENTRANCE_CODE_GUARDS:
        expect_bytes(rom, pc, hx(want), "entrance loader code")


def build_inventory(rom: bytes) -> Inventory:
    check_roots(rom)
    inv = Inventory()
    header_table = snes_to_pc(HEADER_BANK << 16 | 0x8000)
    for room in range(ROOM_COUNT):
        slot = header_table + room * 2
        pc = snes_to_pc(HEADER_BANK << 16 | rom[slot] | rom[slot + 1] << 8)
        expect(pc + HEADER_SIZE <= ROM_SIZE, f"room 0x{room:03X} header out of range")
        inv.header_pc.append(pc)

        raw = bytes(rom[OBJECT_TABLE_PC + room * 3:OBJECT_TABLE_PC + room * 3 + 3])
        start = long_ptr(raw)
        stream = parse_object_stream(rom, start, region_end(start, OBJECT_DATA_REGIONS, "object"))
        door_raw = bytes(rom[DOOR_TABLE_PC + room * 3:DOOR_TABLE_PC + room * 3 + 3])
        inv.obj_ptr.append(raw)
        inv.objects.append(stream)
        inv.door_ptr.append(door_raw)
        inv.door_target.append(long_ptr(door_raw))

        raw = bytes(rom[SPRITE_TABLE_PC + room * 2:SPRITE_TABLE_PC + room * 2 + 2])
        start = bank16_ptr(raw, SPRITE_BANK)
        end = parse_until_ff(rom, start, region_end(start, (SPRITE_REGION,), "sprite"), "sprite")
        inv.spr_ptr.append(raw)
        inv.spr_span.append((start, end))

        raw = bytes(rom[POT_TABLE_PC + room * 2:POT_TABLE_PC + room * 2 + 2])
        start = bank16_ptr(raw, POT_BANK)
        end = parse_until_ff(rom, start, region_end(start, (POT_REGION,), "pot"), "pot")
        inv.pot_ptr.append(raw)
        inv.pot_span.append((start, end))

    size = rom[CHEST_SIZE_OPERAND_PC] | rom[CHEST_SIZE_OPERAND_PC + 1] << 8
    expect(size % 3 == 0 and size <= CHEST_CAPACITY, f"chest table size 0x{size:X} invalid")
    inv.chest_size = size
    inv.chests = [bytes(rom[CHEST_TABLE_PC + i:CHEST_TABLE_PC + i + 3]) for i in range(0, size, 3)]
    return inv


def chest_lists(chests: Sequence[bytes]) -> dict[int, list[tuple[bool, int]]]:
    rooms: dict[int, list[tuple[bool, int]]] = {}
    for rec in chests:
        word = rec[0] | rec[1] << 8
        rooms.setdefault(word & 0x7FFF, []).append((bool(word & 0x8000), rec[2]))
    return rooms


def logical_room(rom: bytes, inv: Inventory, room: int) -> dict[str, Any]:
    """Everything the game reads for one room, as comparable values."""
    obj = inv.objects[room]
    spr, pot = inv.spr_span[room], inv.pot_span[room]
    hpc = inv.header_pc[room]
    return {
        "header": (hpc, bytes(rom[hpc:hpc + HEADER_SIZE])),
        "objects": (inv.obj_ptr[room], bytes(rom[obj.pc:obj.end])),
        "doors": (inv.door_ptr[room], tuple(obj.doors) if inv.door_target[room] == obj.door_pc
                  else bytes(rom[inv.door_target[room]:inv.door_target[room] + 2])),
        "sprites": (inv.spr_ptr[room], bytes(rom[spr[0]:spr[1]])),
        "pots": (inv.pot_ptr[room], bytes(rom[pot[0]:pot[1]])),
    }


# --- manifest -----------------------------------------------------------------

def _pc_ranges(entries: Iterable[dict], what: str) -> list[tuple[int, int]]:
    out = []
    for entry in entries:
        start = snes_to_pc(int(entry["start"], 16))
        end = snes_to_pc(int(entry["end"], 16))
        expect(start < end, f"{what} range {entry} is empty")
        out.append((start, end))
    return out


def check_manifest(manifest: dict, pins: Pins) -> dict[str, list[tuple[int, int]]]:
    try:
        rom = manifest["rom"]
        expect(rom["dev_rom_sha1"] == pins.base_sha1 and rom["dev_rom_size"] == ROM_SIZE,
               "manifest describes a different base ROM")
        streams = manifest["dungeon_stream_regions"]
        obj, spr, pot = streams["objects"], streams["sprites"], streams["pot_items"]
        expect(snes_to_pc(int(obj["pointer_table"], 16)) == OBJECT_TABLE_PC
               and obj["pointer_count"] == ROOM_COUNT and obj["pointer_encoding"] == "long24",
               "manifest object pointer table differs")
        expect(sorted(_pc_ranges(obj["data_regions"], "object")) == sorted(OBJECT_DATA_REGIONS),
               "manifest object data regions differ")
        expect(_pc_ranges(obj["allocation_regions"], "object alloc") == [OBJECT_ALLOC_REGION],
               "manifest object allocation region differs")
        expect(snes_to_pc(int(spr["pointer_table"], 16)) == SPRITE_TABLE_PC
               and int(spr["pointer_bank"], 16) == SPRITE_BANK
               and _pc_ranges(spr["data_regions"], "sprite") == [SPRITE_REGION],
               "manifest sprite layout differs")
        expect(snes_to_pc(int(pot["pointer_table"], 16)) == POT_TABLE_PC
               and int(pot["pointer_bank"], 16) == POT_BANK
               and _pc_ranges(pot["data_regions"], "pot") == [POT_REGION],
               "manifest pot layout differs")

        forbidden = _pc_ranges(manifest["protected_regions"]["regions"], "protected")
        for bank in manifest["owned_banks"]["banks"]:
            if bank["ownership"] != "ram":
                start = snes_to_pc(int(bank["bank"], 16) << 16 | 0x8000)
                forbidden.append((start, start + 0x8000))
        ledger = manifest["allocation_contracts"]["ledger"]
        for table in ledger.get("tables", []):
            if table.get("space") == "snes_rom":
                start = snes_to_pc(table["address"])
                forbidden.append((start, start + table["boundary"] - table["address"]))
        for claim in ledger.get("claims", []):
            if claim.get("space") == "snes_rom":
                start = snes_to_pc(claim["base"])
                forbidden.append((start, start + claim["size"]))
        forbidden += _pc_ranges(manifest["graphics_sheet_regions"]["allocation_regions"], "gfx")
        editor = _pc_ranges(manifest["editor_managed_regions"]["regions"], "editor")
    except (KeyError, TypeError, ValueError) as exc:
        raise PlanError(f"manifest is missing or malformed: {exc!r}") from exc
    return {"forbidden": forbidden, "editor": editor}


# --- recipe -------------------------------------------------------------------

def get_path(doc: Any, path: Sequence[str]) -> Any:
    for key in path:
        if not isinstance(doc, dict) or key not in doc:
            raise PlanError(f"recipe is missing {'.'.join(path)}")
        doc = doc[key]
    return doc


def check_recipe(recipe_bytes: bytes, pins: Pins) -> dict:
    expect(sha256(recipe_bytes) == pins.recipe_sha256,
           f"recipe sha256 {sha256(recipe_bytes)} is not the reviewed recipe")
    try:
        recipe = json.loads(recipe_bytes)
    except ValueError as exc:
        raise PlanError(f"recipe is not JSON: {exc}") from exc
    for path, want in PINNED_RECIPE_FIELDS:
        got = get_path(recipe, path)
        expect(got == want, f"recipe field {'.'.join(path)} differs from the reviewed payload")
    return recipe


# --- plan ---------------------------------------------------------------------

@dataclass
class Write:
    name: str
    pc: int
    before: bytes
    after: bytes

    @property
    def span(self) -> tuple[int, int]:
        return self.pc, self.pc + len(self.before)


def _check_door_entry(entry: dict) -> bytes:
    raw = hx(entry["bytes"])
    expect(len(raw) == 2, f"door {entry['bytes']} is not 2 bytes")
    expect(raw[0] & 0x0C == 0 and raw[0] & 3 == DIRS[entry["dir"]] and raw[0] >> 4 == entry["pos"]
           and raw[1] == int(entry["type"].split()[0], 16),
           f"door {entry['bytes']} does not encode {entry['dir']}{entry['pos']}:{entry['type']}")
    return raw


def derive_object_stream(rom: bytes, inv: Inventory, room: int, spec: dict) -> tuple[bytes, int]:
    pc, ptr, door_ptr, old_hex = OBJECT_STREAMS[room]
    stream = inv.objects[room]
    expect(inv.obj_ptr[room].hex() == ptr and stream.pc == pc,
           f"room 0x{room:02X} object pointer preimage differs")
    expect(inv.door_ptr[room].hex() == door_ptr and inv.door_target[room] == stream.door_pc,
           f"room 0x{room:02X} door pointer preimage differs")
    expect_bytes(rom, pc, hx(old_hex), f"room 0x{room:02X} object stream")
    expect(stream.raw_len == len(hx(old_hex)) == spec["len_before"],
           f"room 0x{room:02X} object stream length differs")
    expect(stream.has_marker and not stream.lists[2], f"room 0x{room:02X} list 2 layout differs")

    lists = [list(records) for records in stream.lists]
    erase = sorted(spec["erase"], key=lambda e: e["index"], reverse=True)
    for entry in erase:
        expect(entry["list"] == 0, "only list 0 erasures are supported")
        rec = stream.lists[0][entry["index"]] if entry["index"] < len(stream.lists[0]) else b""
        expect(rec.hex() == entry["bytes"]
               and decode_object(rec) == (int(entry["id"], 16), entry["x"], entry["y"]),
               f"room 0x{room:02X} erase index {entry['index']} preimage differs")
        del lists[0][entry["index"]]
    for entry in spec.get("objects_add", []):
        expect(entry["layer"] == 0, "objects are only added to layer 0")
        rec = encode_type3(int(entry["id"], 16), entry["x"], entry["y"])
        expect(rec.hex() == entry["bytes"], f"object {entry['bytes']} encoding differs")
        lists[0].append(rec)
    doors = list(stream.doors) + [_check_door_entry(e) for e in spec["doors_add"]]
    encoded, door_offset = encode_object_stream(stream.header, lists, doors)
    expect(encoded == hx(spec["after_hex"]) and len(encoded) == spec["len_after"],
           f"room 0x{room:02X} derived stream differs from recipe after_hex")
    return encoded, door_offset


def audit_unique(spans: Sequence[tuple[int, int]], pointers: Sequence[int], room: int,
                 what: str, extra_pointers: Sequence[int] = ()) -> None:
    """No other room's stream may overlap or point into this room's span."""
    target = spans[room]
    for other in range(ROOM_COUNT):
        if other == room:
            continue
        expect(not overlaps(spans[other], target) and not target[0] <= pointers[other] < target[1],
               f"{what} of room 0x{room:02X} is shared with room 0x{other:03X}")
    for ptr in extra_pointers:
        expect(not target[0] <= ptr < target[1], f"{what} of room 0x{room:02X} has a foreign pointer")


def allocate_object_stream(inv: Inventory, size: int, reserved: Sequence[tuple[int, int]]
                           ) -> tuple[int, dict]:
    region = OBJECT_ALLOC_REGION
    live = [(s.pc, s.end) for s in inv.objects]
    targets = [s.pc for s in inv.objects] + list(inv.door_target)
    tail = region[0]
    for start, end in live:
        if overlaps((start, end), region):
            tail = max(tail, end)
    for ptr in targets:
        if region[0] <= ptr < region[1]:
            expect(any(s <= ptr < e for s, e in live),
                   f"pointer 0x{ptr:06X} targets unparsed bytes in the allocation region")
            tail = max(tail, ptr + 1)
    candidate = (tail, tail + size)
    expect(candidate[1] <= region[1], "object allocation region is full")
    expect(candidate[0] // 0x8000 == (candidate[1] - 1) // 0x8000, "allocation crosses a bank")
    for span in live:
        expect(not overlaps(span, candidate), f"allocation overlaps live stream {span}")
    for ptr in targets:
        expect(not candidate[0] <= ptr < region[1], f"pointer 0x{ptr:06X} targets the free tail")
    for span in reserved:
        expect(not overlaps(span, candidate), f"allocation overlaps reserved range {span}")
    expect(candidate[0] == EXPECTED_ALLOC_PC,
           f"allocator chose 0x{candidate[0]:06X}, reviewed plan expects 0x{EXPECTED_ALLOC_PC:06X}")
    return candidate[0], {"region": [hex(region[0]), hex(region[1])],
                          "highest_live_end": hex(tail), "chosen": hex(candidate[0]),
                          "size": size, "live_object_streams_audited": len(live),
                          "pointer_targets_audited": len(targets)}


def build_plan(rom: bytes, recipe_bytes: bytes, manifest: dict,
               pins: Pins = DEFAULT_PINS) -> tuple[bytes, dict]:
    expect(len(rom) == ROM_SIZE,
           f"ROM size {len(rom)} != {ROM_SIZE} (truncated, headered or wrong ROM)")
    source_sha = sha256(rom)
    expect(source_sha == pins.base_sha256, f"ROM sha256 {source_sha} is not the pinned base")
    recipe = check_recipe(recipe_bytes, pins)
    regions = check_manifest(manifest, pins)
    rooms = recipe["rooms"]

    inv = build_inventory(rom)
    before_logical = {room: logical_room(rom, inv, room) for room in range(ROOM_COUNT)}
    obj_spans = [(s.pc, s.end) for s in inv.objects]
    obj_ptrs = [s.pc for s in inv.objects]
    writes: list[Write] = []

    for room in TARGET_ROOMS:
        spec = rooms[f"0x{room:02X}"]["header"]
        pc = int(spec["pc"], 16)
        expect(inv.header_pc[room] == pc, f"room 0x{room:02X} header pointer differs")
        audit_unique([(p, p + HEADER_SIZE) for p in inv.header_pc], inv.header_pc, room, "header")
        expect(any(s <= pc and pc + HEADER_SIZE <= e for s, e in regions["editor"]),
               f"room 0x{room:02X} header is outside the editor-managed headers")
        writes.append(Write(f"header_{room:02x}", pc, hx(spec["before"]), hx(spec["after"])))

    door_targets = list(inv.door_target)
    new_streams = {}
    for room in TARGET_ROOMS:
        spec = rooms[f"0x{room:02X}"]["object_stream"]
        expect(int(spec["pointer_slot_pc"], 16) == OBJECT_TABLE_PC + room * 3,
               f"room 0x{room:02X} pointer slot differs")
        new_streams[room] = derive_object_stream(rom, inv, room, spec)
    for room in (0x90, 0x92):
        others = [t for r, t in enumerate(door_targets) if r != room]
        audit_unique(obj_spans, obj_ptrs, room, "object stream", others)

    reserved = list(regions["forbidden"]) + list(regions["editor"])
    alloc_pc, allocation = allocate_object_stream(inv, len(new_streams[0x91][0]), reserved)
    expect_bytes(rom, alloc_pc, bytes(len(new_streams[0x91][0])), "object allocation")

    for room in TARGET_ROOMS:
        stream, door_offset = new_streams[room]
        old = inv.objects[room]
        old_bytes = bytes(rom[old.pc:old.end])
        slot = DOOR_TABLE_PC + room * 3
        if room == 0x91:
            obj_ptr = encode_long(alloc_pc)
            door_ptr = encode_long(alloc_pc + door_offset)
            writes.append(Write("object_stream_91_new", alloc_pc, bytes(len(stream)), stream))
            writes.append(Write("object_pointer_91", OBJECT_TABLE_PC + room * 3,
                                inv.obj_ptr[room], obj_ptr))
        else:
            expect(len(stream) <= len(old_bytes), f"room 0x{room:02X} grows in place")
            obj_ptr = inv.obj_ptr[room]
            door_ptr = encode_long(old.pc + door_offset, mirror_from=inv.door_ptr[room])
            writes.append(Write(f"object_stream_{room:02x}_in_place", old.pc, old_bytes,
                                stream + old_bytes[len(stream):]))
        expect((obj_ptr.hex(), door_ptr.hex()) == EXPECTED_POINTERS_AFTER[room],
               f"room 0x{room:02X} derived pointers differ from the reviewed plan")
        writes.append(Write(f"door_pointer_{room:02x}", slot, inv.door_ptr[room], door_ptr))

    spr = rooms["0x91"]["sprites"]
    spr_pc = int(spr["stream_pc"], 16)
    spr_old, spr_new = hx(spr["before"]), hx(spr["after"])
    expect(inv.spr_span[0x91] == (spr_pc, spr_pc + len(spr_old)), "room 0x91 sprite span differs")
    audit_unique(inv.spr_span, [s for s, _ in inv.spr_span], 0x91, "sprite stream")
    expect([spr_old[i + 2] for i in range(1, len(spr_old) - 1, 3)] == [0x84, 0xD1, 0x93, 0x61],
           "room 0x91 sprite ids differ")
    writes.append(Write("sprites_91", spr_pc, spr_old, spr_new + spr_old[len(spr_new):]))

    pots = rooms["0x91"]["pots"]
    slot_pc, pot_pc = int(pots["slot_pc"], 16), int(pots["stream_pc"], 16)
    expect(slot_pc == POT_TABLE_PC + 0x91 * 2, "room 0x91 pot slot differs")
    pot_old, pot_new = hx(pots["current_unreferenced"]), hx(pots["stream_hex"])
    expect(len(pot_old) == pots["allocatable"] and len(pot_new) == pots["bytes"] <= len(pot_old),
           "pot payload lengths differ")
    pot_span = (pot_pc, pot_pc + len(pot_old))
    expect(pot_span[1] == POT_REGION[1], "pot allocation is not the region tail")
    for room in range(ROOM_COUNT):
        expect(not overlaps(inv.pot_span[room], pot_span), f"pot stream of 0x{room:03X} overlaps")
        expect(not pot_span[0] <= inv.pot_span[room][0] < pot_span[1],
               f"pot pointer of 0x{room:03X} targets the new pot space")
    items = [(pot_new[i] | pot_new[i + 1] << 8, pot_new[i + 2]) for i in range(0, 6, 3)]
    expect(items == [(54 * 0x80 + 12 * 2, 0x0C), (54 * 0x80 + 18 * 2, 0x0C)]
           and pot_new[6:] == b"\xff\xff", "pot records do not match the pot objects")
    expect(parse_until_ff(pot_new, 0, len(pot_new), "pot") == len(pot_new), "pot stream malformed")
    expect(bank16_ptr(hx(pots["slot_after"]), POT_BANK) == pot_pc, "pot slot does not point at stream")
    writes.append(Write("pot_slot_91", slot_pc, hx(pots["slot_before"]), hx(pots["slot_after"])))
    writes.append(Write("pot_stream_91", pot_pc, pot_old, pot_new + pot_old[len(pot_new):]))

    chest = rooms["0x92"]["chest_record_removal"]
    size_spec = chest["size_operand"]
    table = bytes(rom[CHEST_TABLE_PC:CHEST_TABLE_PC + CHEST_CAPACITY])
    expect(sha256(table) == pins.chest_table_sha256, "chest table preimage differs")
    expect(int(chest["table_pointer_operand_pc"], 16) == 0x00EBFB
           and int(size_spec["operand_pc"], 16) == CHEST_SIZE_OPERAND_PC, "chest operands moved")
    expect(inv.chest_size == 3 * chest["record_count"]["before"] == CHEST_CAPACITY,
           "chest size preimage differs")
    index = chest["record_index"]
    rec_pc = CHEST_TABLE_PC + index * 3
    expect(rec_pc == int(chest["record_pc"], 16) and inv.chests[index].hex() == chest["record_bytes"],
           "chest record preimage differs")
    expect(chest_lists(inv.chests).get(0x92) == [(False, 0x1C)],
           "room 0x92 must have exactly the one Mitts chest record")
    end = CHEST_TABLE_PC + inv.chest_size
    moved = table[(index + 1) * 3:inv.chest_size]
    expect(len(moved) == 330, "chest shift length differs")
    writes.append(Write("chest_table_shift", rec_pc, bytes(rom[rec_pc:end]),
                        moved + bytes(rom[end - 3:end])))
    new_size = 3 * chest["record_count"]["after"]
    expect(hx(size_spec["after"]) == bytes((new_size & 0xFF, new_size >> 8)), "chest size differs")
    writes.append(Write("chest_size_operand", CHEST_SIZE_OPERAND_PC, hx(size_spec["before"]),
                        hx(size_spec["after"])))

    entrance = recipe["inbound"]["entrance_0x29"]
    expect(int(entrance["room"], 16) == 0x90, "entrance room differs")
    room_pc = ENTRANCE_ROOM_TABLE + ENTRANCE_ID * 2
    expect_bytes(rom, room_pc, b"\x90\x00", "entrance 0x29 room id")
    proposed = entrance["proposed_if_retained"]
    entrance_report = {"room_id_pc": hex(room_pc), "room_id": "0x0090"}
    for name, table_pc, width, before, after in ENTRANCE_FIELDS:
        pc = table_pc + ENTRANCE_ID * width
        old_key = f"{name}@0x{pc:05X}"
        old_val, new_val = entrance["fields_row6"][old_key], proposed[name]
        if width == 2:
            expect(hx(before) == int(old_val, 16).to_bytes(2, "little")
                   and hx(after) == int(new_val, 16).to_bytes(2, "little"),
                   f"entrance {name} values differ from the recipe")
        else:
            expect(hx(before) == hx(old_val) and hx(after) == hx(new_val),
                   f"entrance {name} values differ from the recipe")
        writes.append(Write(f"entrance_29_{name}", pc, hx(before), hx(after)))
        entrance_report[name] = {"pc": hex(pc), "before": before, "after": after}

    out = apply_writes(rom, writes, regions["forbidden"])
    after_inv = build_inventory(out)
    isolation = verify_after(rom, out, inv, after_inv, before_logical, new_streams, alloc_pc,
                             pot_pc, pot_new, spr_new)
    report = {
        "tool": TOOL, "tool_version": TOOL_VERSION,
        "source": {"sha256": source_sha, "size": len(rom)},
        "recipe_sha256": sha256(recipe_bytes),
        "output_sha256": sha256(out),
        "writes": [{"name": w.name, "pc": hex(w.pc), "snes": f"${pc_to_snes(w.pc):06X}",
                    "length": len(w.before), "changed_bytes": sum(a != b for a, b in
                                                                  zip(w.before, w.after)),
                    "before_sha256": sha256(w.before), "after_sha256": sha256(w.after),
                    **({"before": w.before.hex(), "after": w.after.hex()}
                       if len(w.before) <= 16 else {})} for w in writes],
        "allowed_ranges": [[hex(a), hex(b)] for a, b in merged_spans(writes)],
        "allocations": {"object_stream_91": allocation,
                        "pot_stream_91": {"region": [hex(POT_REGION[0]), hex(POT_REGION[1])],
                                          "chosen": hex(pot_pc), "size": len(pot_new),
                                          "pot_streams_audited": ROOM_COUNT}},
        "pointers_after": {f"0x{r:02X}": {"object": EXPECTED_POINTERS_AFTER[r][0],
                                          "door": EXPECTED_POINTERS_AFTER[r][1]}
                           for r in TARGET_ROOMS},
        "entrance_0x29": entrance_report,
        "isolation": isolation,
        "limitations": LIMITATIONS,
    }
    return out, report


def merged_spans(writes: Sequence[Write]) -> list[tuple[int, int]]:
    spans = sorted(w.span for w in writes)
    merged: list[tuple[int, int]] = []
    for start, end in spans:
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def apply_writes(rom: bytes, writes: Sequence[Write],
                 forbidden: Sequence[tuple[int, int]]) -> bytes:
    ordered = sorted(writes, key=lambda w: w.pc)
    for prev, cur in zip(ordered, ordered[1:]):
        expect(prev.span[1] <= cur.span[0], f"writes {prev.name} and {cur.name} overlap")
    out = bytearray(rom)
    for w in ordered:
        expect(len(w.before) == len(w.after) > 0, f"write {w.name} length mismatch")
        expect(w.span[1] <= ROM_SIZE, f"write {w.name} is outside the ROM")
        expect_bytes(rom, w.pc, w.before, f"write {w.name}")
        for span in forbidden:
            expect(not overlaps(w.span, span), f"write {w.name} hits protected range "
                   f"0x{span[0]:06X}-0x{span[1]:06X}")
        out[w.pc:w.pc + len(w.after)] = w.after
    verify_diff_within(rom, bytes(out), merged_spans(writes))
    return bytes(out)


def verify_diff_within(src: bytes, out: bytes, allowed: Sequence[tuple[int, int]]) -> int:
    expect(len(src) == len(out), "output size differs from source")
    changed = 0
    for pc, (a, b) in enumerate(zip(src, out)):
        if a != b:
            changed += 1
            expect(any(s <= pc < e for s, e in allowed), f"byte 0x{pc:06X} changed outside writes")
    return changed


ALLOWED_ROOM_CHANGES = {"header": set(TARGET_ROOMS), "objects": set(TARGET_ROOMS),
                        "doors": set(TARGET_ROOMS), "sprites": {0x91}, "pots": {0x91}}


def room_changes(before_logical: dict, out: bytes, after: Inventory) -> dict[str, list[int]]:
    """Rooms whose logical header/object/door/sprite/pot data differ; refuses unplanned ones."""
    changed: dict[str, list[int]] = {k: [] for k in ALLOWED_ROOM_CHANGES}
    for room in range(ROOM_COUNT):
        for key, value in logical_room(out, after, room).items():
            if value != before_logical[room][key]:
                changed[key].append(room)
                expect(room in ALLOWED_ROOM_CHANGES[key], f"room 0x{room:03X} {key} changed")
    return changed


def verify_after(src: bytes, out: bytes, inv: Inventory, after: Inventory,
                 before_logical: dict, new_streams: dict, alloc_pc: int,
                 pot_pc: int, pot_new: bytes, spr_new: bytes) -> dict:
    changed = room_changes(before_logical, out, after)
    for room in TARGET_ROOMS:
        stream = after.objects[room]
        expect(bytes(out[stream.pc:stream.end]) == new_streams[room][0]
               and after.door_target[room] == stream.door_pc,
               f"room 0x{room:02X} objects/doors after differ")
        expect(after.spr_ptr[room] == inv.spr_ptr[room], f"room 0x{room:02X} sprite pointer moved")
    expect(after.objects[0x91].pc == alloc_pc, "room 0x91 does not point at the new stream")
    expect(all(after.objects[r].pc != inv.objects[0x91].pc for r in range(ROOM_COUNT)),
           "old room 0x91 stream is still referenced")
    spr = after.spr_span[0x91]
    expect(bytes(out[spr[0]:spr[1]]) == spr_new, "room 0x91 still has sprites")
    expect(after.pot_span[0x91] == (pot_pc, pot_pc + len(pot_new)), "room 0x91 pots differ")

    before_chests, after_chests = chest_lists(inv.chests), chest_lists(after.chests)
    expect(after.chest_size == inv.chest_size - 3, "chest count did not drop by one")
    expect(after_chests.get(0x92) is None, "room 0x92 still has a chest record")
    for room, entries in before_chests.items():
        if room != 0x92:
            expect(after_chests.get(room) == entries, f"room 0x{room:03X} chest order changed")
    expect(set(after_chests) == set(before_chests) - {0x92}, "chest rooms changed")
    return {
        "rooms_checked": ROOM_COUNT,
        "changed_rooms": {k: [f"0x{r:02X}" for r in v] for k, v in changed.items()},
        "unchanged_room_count": {k: ROOM_COUNT - len(v) for k, v in changed.items()},
        "chest_records": {"before": len(inv.chests), "after": len(after.chests),
                          "rooms_with_identical_order": len(before_chests) - 1,
                          "removed": "room 0x092 record 57 (92001c)"},
        "bytes_changed": verify_diff_within(src, out, [(0, len(src))]),
        "old_room_91_stream": {"pc": hex(inv.objects[0x91].pc), "referenced_after": False},
    }


# --- file guards ----------------------------------------------------------------

def _under(path: Path, roots: Sequence[Path]) -> bool:
    existing = [r for r in roots if r.exists()]
    for ancestor in (path, *path.parents):
        if ancestor.exists() and any(os.path.samefile(ancestor, r) for r in existing):
            return True
        resolved = ancestor.resolve()
        if any(resolved == r.resolve() for r in roots):
            return True
    return False


def check_new_target(path: Path, label: str, protected: Sequence[Path],
                     taken: Sequence[Path]) -> Path:
    expect(not os.path.lexists(path), f"{label} {path} already exists; nothing is overwritten")
    parent = path.parent.resolve()
    expect(parent.is_dir(), f"{label} parent {parent} is not a directory")
    target = parent / path.name
    expect(not _under(target, protected), f"{label} {path} is under a protected directory")
    for other in taken:
        expect(target != other and not (other.exists() and target.exists()
                                        and os.path.samefile(target, other)),
               f"{label} {path} aliases {other}")
    return target


def create_exclusive(path: Path, data: bytes, mode: int) -> None:
    flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags, mode)
    try:
        view = memoryview(data)
        while view:
            view = view[os.write(fd, view):]
        os.fsync(fd)
    finally:
        os.close(fd)


def readback(path: Path, want_sha: str, label: str, input_path: Path) -> None:
    info = os.lstat(path)
    expect(stat.S_ISREG(info.st_mode) and info.st_nlink == 1, f"{label} is not a single-link file")
    expect(not os.path.samefile(path, input_path), f"{label} aliases the input ROM")
    expect(sha256(path.read_bytes()) == want_sha, f"{label} readback hash differs")


def read_input(path: Path) -> bytes:
    info = os.stat(path)
    expect(stat.S_ISREG(info.st_mode), f"input {path} is not a regular file")
    with open(path, "rb") as handle:
        return handle.read()


def main(argv: Sequence[str] | None = None, pins: Pins = DEFAULT_PINS,
         protected_dirs: Sequence[Path] = DEFAULT_PROTECTED_DIRS) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, required=True, help="pinned base ROM (read-only)")
    ap.add_argument("--recipe", type=Path, required=True)
    ap.add_argument("--manifest", type=Path, required=True)
    ap.add_argument("--write", action="store_true", help="materialize --output (default: dry run)")
    ap.add_argument("--output", type=Path, help="new patched ROM path (with --write)")
    ap.add_argument("--rollback", type=Path, help="new copy of the input ROM (with --write)")
    ap.add_argument("--report", type=Path, help="new JSON report path (default: stdout)")
    args = ap.parse_args(argv)

    report: dict[str, Any] = {"tool": TOOL, "mode": "write" if args.write else "dry-run"}
    report_path = None
    try:
        input_path = args.rom.resolve()
        rom = read_input(input_path)
        input_sha = sha256(rom)
        taken = [input_path, args.recipe.resolve(), args.manifest.resolve()]
        if args.report is not None:
            expect(args.report.suffix == ".json", "--report must end in .json")
            report_path = check_new_target(args.report, "report", protected_dirs, taken)
            taken.append(report_path)
        if args.write:
            expect(args.output is not None and args.rollback is not None,
                   "--write needs --output and --rollback")
            output = check_new_target(args.output, "output", protected_dirs, taken)
            taken.append(output)
            rollback = check_new_target(args.rollback, "rollback", protected_dirs, taken)
        else:
            expect(args.output is None and args.rollback is None,
                   "--output/--rollback are only accepted with --write")

        manifest = json.loads(read_input(args.manifest.resolve()))
        out, plan = build_plan(rom, read_input(args.recipe.resolve()), manifest, pins)
        report.update(plan)
        report["source"]["path"] = str(input_path)

        if args.write:
            create_exclusive(rollback, rom, 0o444)
            readback(rollback, input_sha, "rollback", input_path)
            create_exclusive(output, out, 0o644)
            readback(output, plan["output_sha256"], "output", input_path)
            report["written"] = {"output": str(output), "rollback": str(rollback),
                                 "output_readback_sha256": plan["output_sha256"],
                                 "rollback_readback_sha256": input_sha}
        after_sha = sha256(read_input(input_path))
        expect(after_sha == input_sha, "input ROM changed during the run")
        report["source"]["sha256_after_run"] = after_sha
        report["status"] = "ok"
        code = 0
    except (PlanError, OSError, ValueError) as exc:
        report["status"] = "refused"
        report["error"] = str(exc)
        code = 1

    text = json.dumps(report, indent=2) + "\n"
    if report_path is not None and code == 0:
        create_exclusive(report_path, text.encode(), 0o644)
    else:
        sys.stdout.write(text)
    return code


if __name__ == "__main__":
    sys.exit(main())
