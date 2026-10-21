"""Compile saved Yaze Lyra terrain into native data plans without ROM writes.

The caller independently verifies the source profile, complete native Tile32
definitions and allocation ownership. This module never infers free storage
from unused IDs or blank ROM bytes and never enables runtime map admission.
"""

from __future__ import annotations

import configparser
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
from typing import Mapping


FIRST_MAP = 0xA0
MAP_COUNT = 32
MAP_SIZE = 32
TILE32_CAPACITY = 0x4540
MAX_DOCUMENT_BYTES = 4 * 1024 * 1024
PROFILE_KEYS = {
    "graphics_sheets", "main_palette", "palette_set", "animated_sheet",
    "tile_count", "tile16_definition_fingerprint", "graphics_fingerprint",
    "palette_fingerprint", "animation_fingerprint",
}
PROPERTY_KEYS = {
    "graphics_sheets", "main_palette", "palette_set", "animated_sheet",
    "sprite_graphics", "sprite_palettes", "music", "message_id",
}
DEFAULT_PROPERTIES = {
    "graphics_sheets": [0x3A, 0x3B, 0x3C, 0x3D, 0x47, 0x48, 0x3E, 0x5B],
    "main_palette": 0, "palette_set": 1, "animated_sheet": 0x5B,
    "sprite_graphics": [-1, -1, -1], "sprite_palettes": [-1, -1, -1],
    "music": [0, 0, 0, 0], "message_id": 0,
}
Quad = tuple[int, int, int, int]


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _integer(value: object, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _keys(value: object, expected: set[str], label: str) -> None:
    _require(type(value) is dict and set(value) == expected,
             f"Malformed {label} keys")


def _array(value: object, count: int, minimum: int, maximum: int) -> bool:
    return (type(value) is list and len(value) == count
            and all(_integer(v, minimum, maximum) for v in value))


def _fingerprint(value: object) -> bool:
    return type(value) is str and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _profile(value: object) -> None:
    _keys(value, PROFILE_KEYS, "Lyra profile")
    _require(_array(value["graphics_sheets"], 8, 0, 254),
             "Invalid Lyra graphics sheets")
    for key in ("main_palette", "palette_set", "animated_sheet"):
        maximum = 254 if key == "animated_sheet" else 255
        _require(_integer(value[key], 0, maximum), f"Invalid Lyra {key}")
    _require(_integer(value["tile_count"], 1, 4096),
             "Native Tile16 capacity is 1..4096")
    for key in PROFILE_KEYS - {"graphics_sheets", "main_palette", "palette_set",
                               "animated_sheet", "tile_count"}:
        _require(_fingerprint(value[key]), f"Invalid Lyra {key}")


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate JSON keys")
        result[key] = value
    return result


def _invalid_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON numeric constant: {value}")


@dataclass(frozen=True)
class TerrainDocument:
    profile: dict
    # Maps and properties are ordered A0..BF; each map is row-major Tile16.
    maps: tuple[tuple[int, ...], ...]
    properties: tuple[dict, ...]
    edge_connections: tuple[dict, ...] = ()
    # Complete schema-3 drafts survive read-only subset planning. They are not
    # a promise that a runtime adapter consumes their metadata.
    authoring: tuple[dict, ...] = ()
    flight_points: tuple[dict, ...] = ()


@dataclass(frozen=True)
class Allocation:
    # Headerless PC ranges, end-exclusive, independently owned by the caller.
    stream_ranges: tuple[tuple[int, int], ...]
    owned_tile32_ids: tuple[int, ...] = ()
    tile32_capacity: int = TILE32_CAPACITY
    # None retains the historical explicit-owner allocator. A reviewed joint
    # assignment fixes IDs across independently compiled project subsets.
    tile32_assignments: tuple[tuple[int, Quad], ...] | None = None


@dataclass(frozen=True)
class StreamPlan:
    pc: int
    payload: bytes

    @property
    def snes(self) -> int:
        # FastROM mirrors also keep the final two LoROM banks out of WRAM's
        # $7E/$7F CPU bank identities.
        return 0x800000 | ((self.pc // 0x8000) << 16) | 0x8000 | (self.pc & 0x7FFF)


@dataclass(frozen=True)
class MapPlan:
    map_id: int
    tiles32: tuple[int, ...]
    high: StreamPlan
    low: StreamPlan
    quadrant_maps: Quad
    properties: dict


@dataclass(frozen=True)
class CompiledTerrain:
    maps: tuple[MapPlan, ...]
    new_definitions: tuple[tuple[int, Quad], ...]
    edge_connections: tuple[dict, ...] = ()

    @property
    def stream_writes(self) -> tuple[StreamPlan, ...]:
        return tuple(stream for plan in self.maps for stream in (plan.high, plan.low))


def resolve_project_terrain(project_path: str | Path) -> Path:
    """Resolve the existing [files] asset relative to its saved .yaze project.

    Absolute references and symlinks are legal project references. No storage
    is created, and the existing asset must resolve to a regular file.
    """
    # Yaze anchors relative assets to the descriptor path as opened, including
    # a symlink's directory, rather than the symlink target's directory.
    project = Path(os.path.abspath(project_path))
    _require(project.is_file(), "Project path is not a file")
    parser = configparser.ConfigParser(interpolation=None, strict=True)
    parser.optionxform = str
    try:
        parser.read_string(project.read_text(encoding="utf-8-sig"))
        # Yaze's INI reader does not inherit Python ConfigParser defaults.
        parser.defaults().clear()
        _require(parser.has_section("files"), "Project has no [files] section")
        reference = parser.get("files", "lyra_terrain_file", fallback="").strip()
    except configparser.Error as error:
        raise ValueError(f"Malformed Yaze project: {error}") from error
    _require(reference and "\0" not in reference,
             "Project has no Lyra terrain asset")
    asset = Path(reference)
    if not asset.is_absolute():
        asset = project.parent / asset
    asset = asset.resolve(strict=True)
    _require(asset.is_file(), "Lyra terrain asset is not a file")
    return asset


def parse_terrain_document(text: str | bytes, expected_profile: Mapping, *,
                           expected_asset_bindings: Mapping[int, tuple[str, str, str]] | None = None,
                           allow_authoring_drafts: bool = False,
                           ) -> TerrainDocument:
    """Parse schema 3 against independently verified native assets.

    The historical strict runtime policy remains the default. A read-only
    admission planner may preserve valid drafts and apply consumer checks to
    its explicit traversal/render sets instead. No metadata is discarded.
    """
    expected = copy.deepcopy(dict(expected_profile))
    _profile(expected)
    _require(isinstance(text, (str, bytes)), "Lyra document must be text")
    size = len(text.encode("utf-8")) if isinstance(text, str) else len(text)
    _require(size <= MAX_DOCUMENT_BYTES, "Lyra terrain document exceeds 4 MiB")
    data = json.loads(text, object_pairs_hook=_unique_object,
                      parse_constant=_invalid_constant)
    _keys(data, {"schema", "schema_version", "columns", "rows", "map_width",
                 "map_height", "tile_pixels", "profile", "maps",
                 "flight_points", "edge_connections"}, "Lyra schema 3 header")
    _require(data["schema"] == "yaze.lyra-terrain"
             and _integer(data["schema_version"], 3, 3),
             "Expected Yaze Lyra schema 3")
    for key, value in (("columns", 8), ("rows", 4), ("map_width", 32),
                       ("map_height", 32), ("tile_pixels", 16)):
        _require(_integer(data[key], value, value), f"Invalid Lyra {key}")
    _profile(data["profile"])
    _require(data["profile"] == expected,
             "Lyra profile differs from independently verified source assets")
    flights = data["flight_points"]
    _require(type(flights) is list and len(flights) <= 64, "Invalid flight_points")
    _require(allow_authoring_drafts or not flights,
             "Unsupported runtime metadata: flight_points")
    flight_ids = set()
    for flight in flights:
        _keys(flight, {"id", "map_id", "x", "y", "name", "runtime_slot"}, "Lyra flight point")
        _require(_integer(flight["id"], 1, 0xFFFFFFFF) and flight["id"] not in flight_ids
                 and _integer(flight["map_id"], 0, 0xBF)
                 and _integer(flight["x"], 0, 31) and _integer(flight["y"], 0, 31)
                 and type(flight["name"]) is str and 0 < len(flight["name"].encode("utf-8")) <= 80
                 and all(ord(c) >= 32 and ord(c) != 127 for c in flight["name"])
                 and flight["runtime_slot"] is None, "Invalid Lyra flight point")
        flight_ids.add(flight["id"])
    edges = data["edge_connections"]
    _require(type(edges) is list and len(edges) <= 64,
             "Lyra edge connections require an array of at most 64 entries")
    edge_ids, edge_pairs = set(), set()
    for edge in edges:
        _keys(edge, {"id", "map_a", "map_b", "passage"}, "Lyra edge connection")
        _require(_integer(edge["id"], 1, 0xFFFFFFFF) and edge["id"] not in edge_ids,
                 "Invalid or duplicate Lyra edge ID")
        a, b = edge["map_a"], edge["map_b"]
        endpoint = lambda area: _integer(area, 0x98, 0x9B) or _integer(area, 0xA0, 0xBF)
        _require(endpoint(a) and endpoint(b) and a < b and b >= FIRST_MAP
                 and (b - a == 8 or (b - a == 1 and a // 8 == b // 8)),
                 "Lyra edges require canonical adjacent 98..9B/A0..BF pairs")
        _require((a, b) not in edge_pairs, "Duplicate Lyra edge map pair")
        if edge["passage"] is not None:
            _keys(edge["passage"], {"first_tile", "last_tile"}, "Lyra edge passage")
            first, last = edge["passage"]["first_tile"], edge["passage"]["last_tile"]
            _require(_integer(first, 0, 31) and _integer(last, first, 31),
                     "Lyra passage requires 0 <= first_tile <= last_tile <= 31")
        edge_ids.add(edge["id"])
        edge_pairs.add((a, b))
    _require(type(data["maps"]) is list and len(data["maps"]) == MAP_COUNT,
             "Lyra terrain requires all 32 maps")
    maps, properties, authoring = {}, {}, {}
    entity_ids = {key: set() for key in ("sprites", "doors", "exits")}
    for entry in data["maps"]:
        _keys(entry, {"map_id", "tiles16", "authoring"}, "Lyra map")
        area = entry["map_id"]
        _require(_integer(area, FIRST_MAP, FIRST_MAP + MAP_COUNT - 1),
                 "Lyra map ID must be A0..BF")
        _require(area not in maps, "Duplicate Lyra map ID")
        rows = entry["tiles16"]
        _require(type(rows) is list and len(rows) == MAP_SIZE
                 and all(_array(row, MAP_SIZE, 0, expected["tile_count"] - 1)
                         for row in rows),
                 "Lyra map requires 32x32 native Tile16 cells")
        auth = entry["authoring"]
        _keys(auth, {"properties", "sprites", "doors", "exits", "asset_bindings"},
              "Lyra authoring")
        for key in ("sprites", "doors", "exits"):
            entities = auth[key]
            _require(type(entities) is list and len(entities) <= (128 if key == "sprites" else 64),
                     f"Invalid Lyra {key}")
            _require(allow_authoring_drafts or not entities,
                     f"Unsupported runtime metadata: {area:02X}.{key}")
            positions = set()
            for entity in entities:
                extra = {"sprites": {"sprite_id", "state"}, "doors": {"entrance_id"},
                         "exits": {"room_id", "exit_row"}}[key]
                _keys(entity, {"id", "x", "y"} | extra, f"Lyra {key} placement")
                _require(_integer(entity["id"], 1, 0xFFFFFFFF)
                         and entity["id"] not in entity_ids[key]
                         and _integer(entity["x"], 0, 31) and _integer(entity["y"], 0, 31),
                         f"Invalid or duplicate Lyra {key} placement")
                entity_ids[key].add(entity["id"])
                if key == "sprites":
                    _require(_integer(entity["sprite_id"], 0, 255)
                             and _integer(entity["state"], 0, 2), "Invalid Lyra sprite")
                elif key == "doors":
                    position = (entity["x"], entity["y"])
                    _require(position not in positions
                             and (entity["entrance_id"] is None
                                  or _integer(entity["entrance_id"], 0, 254)), "Invalid Lyra door")
                    positions.add(position)
                else:
                    _require(_integer(entity["room_id"], 0, 0x127)
                             and (entity["exit_row"] is None
                                  or _integer(entity["exit_row"], 0, 78)), "Invalid Lyra exit")
        props = auth["properties"]
        _keys(props, PROPERTY_KEYS, "Lyra map properties")
        _require(_array(props["graphics_sheets"], 8, 0, 255)
                 and _array(props["sprite_graphics"], 3, -1, 255)
                 and _array(props["sprite_palettes"], 3, -1, 255)
                 and _array(props["music"], 4, 0, 255)
                 and _integer(props["message_id"], 0, 65535),
                 "Invalid Lyra map properties")
        for key in ("main_palette", "palette_set", "animated_sheet"):
            _require(_integer(props[key], 0, 255), f"Invalid map {key}")
        for key in ("graphics_sheets", "main_palette", "palette_set", "animated_sheet"):
            _require(allow_authoring_drafts or props[key] == expected[key],
                     f"Map {area:02X} {key} needs an independently verified profile")
        bindings = auth["asset_bindings"]
        _require(type(bindings) is list and len(bindings) == 3,
                 "Malformed Lyra map asset bindings")
        if bindings == ["", "", ""]:
            _require(props == DEFAULT_PROPERTIES,
                     "Empty asset bindings require default map properties")
        else:
            # These are three combined hashes (one per story state), not the
            # three global graphics/palette/animation profile fingerprints.
            verified = (expected_asset_bindings or {}).get(area)
            _require(verified is not None and len(verified) == 3
                     and all(_fingerprint(v) for v in verified)
                     and all(_fingerprint(v) for v in bindings)
                     and bindings == list(verified),
                     "Map asset bindings differ from independently verified source assets")
        maps[area] = tuple(cell for row in rows for cell in row)
        properties[area] = copy.deepcopy(props)
        authoring[area] = copy.deepcopy(auth)
    ids = range(FIRST_MAP, FIRST_MAP + MAP_COUNT)
    return TerrainDocument(expected, tuple(maps[i] for i in ids),
                           tuple(properties[i] for i in ids), tuple(copy.deepcopy(edges)),
                           tuple(authoring[i] for i in ids), tuple(copy.deepcopy(flights)))


def quadrant_map_plan(map_id: int) -> Quad:
    """Clamp a native TL/TR/BL/BR footprint without wrapping an 8x4 edge.

    The runtime adapter must use these source IDs rather than unchecked
    map+1/+8/+9 reads. This data plan itself installs no loader hook.
    """
    _require(_integer(map_id, FIRST_MAP, FIRST_MAP + MAP_COUNT - 1),
             "Quadrant map ID must be A0..BF")
    row, column = divmod(map_id - FIRST_MAP, 8)
    right, below = min(column + 1, 7), min(row + 1, 3)
    return (map_id, FIRST_MAP + row * 8 + right,
            FIRST_MAP + below * 8 + column, FIRST_MAP + below * 8 + right)


def decode_literal_stream(payload: bytes) -> bytes:
    """Independent readback of this compiler's one-block native stream."""
    _require(type(payload) is bytes and len(payload) == 259
             and payload[:2] == b"\xe0\xff" and payload[-1] == 0xFF,
             "Invalid terminated 256-byte literal stream")
    return payload[2:-1]


def compile_terrain(document: TerrainDocument, native_definitions: Mapping[int, Quad],
                    allocation: Allocation, *, map_ids=None, render_directory=None) -> CompiledTerrain:
    """Compile all maps or a sorted explicit subset; never mutate inputs."""
    _require(isinstance(document, TerrainDocument), "Expected parsed TerrainDocument")
    _require(isinstance(allocation, Allocation), "Expected explicit Allocation")
    _require(_integer(allocation.tile32_capacity, 1, TILE32_CAPACITY),
             "Invalid native Tile32 capacity")
    capacity = allocation.tile32_capacity
    _require(all(type(i) is int for i in native_definitions)
             and set(native_definitions) == set(range(capacity)),
             "Complete independently verified native Tile32 definitions required")
    definitions = {}
    for index, quad in native_definitions.items():
        _require(isinstance(quad, (tuple, list)) and len(quad) == 4
                 and all(_integer(v, 0, 4095) for v in quad),
                 "Native Tile32 quadrants must be four 12-bit Tile16 IDs")
        definitions[index] = tuple(quad)
    owned = allocation.owned_tile32_ids
    _require(isinstance(owned, (tuple, list))
             and all(_integer(i, 0, capacity - 1) for i in owned)
             and len(set(owned)) == len(owned), "Invalid owned Tile32 allocation")
    ranges = allocation.stream_ranges
    _require(isinstance(ranges, (tuple, list)) and ranges,
             "Explicit stream allocation required")
    checked_ranges = []
    for span in ranges:
        _require(isinstance(span, (tuple, list)) and len(span) == 2
                 and _integer(span[0], 0, 0x3FFFFF)
                 and _integer(span[1], 1, 0x400000) and span[0] < span[1],
                 "Invalid headerless LoROM stream allocation")
        checked_ranges.append(tuple(span))
    checked_ranges.sort()
    _require(all(a[1] <= b[0] for a, b in zip(checked_ranges, checked_ranges[1:])),
             "Overlapping stream allocation ranges")
    _profile(document.profile)
    _require(len(document.maps) == MAP_COUNT and len(document.properties) == MAP_COUNT,
             "Incomplete parsed Lyra maps")
    if map_ids is None:
        selected = tuple(range(MAP_COUNT))
    else:
        message = "map_ids must be an iterable of unique integer A0..BF map IDs"
        _require(not isinstance(map_ids, (str, bytes, bytearray)), message)
        try:
            requested = iter(map_ids)
        except TypeError as error:
            raise ValueError(message) from error
        seen = set()
        for area in requested:
            _require(_integer(area, FIRST_MAP, FIRST_MAP + MAP_COUNT - 1), message)
            _require(area not in seen, "Duplicate selected Lyra map ID")
            seen.add(area)
        selected = tuple(area - FIRST_MAP for area in sorted(seen))
    directory = {} if render_directory is None else dict(render_directory)
    selected_ids = {FIRST_MAP + index for index in selected}
    for area, row in directory.items():
        _require(type(area) is int and area in selected_ids
                 and isinstance(row, (tuple, list)) and len(row) == 4
                 and all(type(source) is int and source in selected_ids for source in row)
                 and tuple(row) in (quadrant_map_plan(area), (area,) * 4),
                 "Unclosed or unsupported explicit render directory")
    map_quads = []
    for cells in document.maps:
        _require(len(cells) == 1024
                 and all(_integer(v, 0, document.profile["tile_count"] - 1)
                         for v in cells), "Invalid parsed Tile16 map")
        map_quads.append(tuple((cells[y * 32 + x], cells[y * 32 + x + 1],
                                cells[(y + 1) * 32 + x], cells[(y + 1) * 32 + x + 1])
                               for y in range(0, 32, 2) for x in range(0, 32, 2)))
    # Reserve every selected reused ID before allocating: a later selected map
    # may need an owned native slot that an earlier selected map did not use.
    lookup = {}
    owned_set = set(owned)
    for index in sorted(definitions, key=lambda value: (value in owned_set, value)):
        lookup.setdefault(definitions[index], index)
    needed = set(quad for index in selected for quad in map_quads[index])
    reused = {lookup[quad] for quad in needed if quad in lookup}
    free = iter(sorted(owned_set - reused))
    assigned = None
    if allocation.tile32_assignments is not None:
        assigned, assigned_ids = {}, set()
        for index, quad in allocation.tile32_assignments:
            _require(type(index) is int and index in owned_set and index not in assigned_ids
                     and isinstance(quad, (tuple, list)) and len(quad) == 4
                     and all(_integer(v, 0, 4095) for v in quad),
                     "Invalid reviewed Tile32 assignment")
            quad = tuple(quad)
            _require(quad not in assigned and quad not in lookup and index not in reused,
                     "Reviewed Tile32 assignment aliases a native or assigned definition")
            assigned[quad] = index
            assigned_ids.add(index)
    added = []
    for quad in sorted(needed - set(lookup)):
        index = assigned.get(quad) if assigned is not None else next(free, None)
        _require(index is not None, "Missing reviewed Tile32 assignment" if assigned is not None
                 else "Insufficient explicitly owned Tile32 capacity")
        lookup[quad] = index
        definitions[index] = quad
        added.append((index, quad))
    range_index, cursor = 0, checked_ranges[0][0]

    def place(payload: bytes) -> StreamPlan:
        nonlocal range_index, cursor
        while range_index < len(checked_ranges):
            begin, end = checked_ranges[range_index]
            cursor = max(cursor, begin)
            bank_end = ((cursor // 0x8000) + 1) * 0x8000
            if cursor + len(payload) <= min(end, bank_end):
                stream = StreamPlan(cursor, payload)
                cursor += len(payload)
                return stream
            if bank_end < end:
                cursor = bank_end
            else:
                range_index += 1
                if range_index < len(checked_ranges):
                    cursor = checked_ranges[range_index][0]
        raise ValueError("Insufficient bank-safe stream allocation")

    plans = []
    for index in selected:
        quads = map_quads[index]
        tiles = tuple(lookup[quad] for quad in quads)
        high = place(b"\xe0\xff" + bytes(tile >> 8 for tile in tiles) + b"\xff")
        low = place(b"\xe0\xff" + bytes(tile & 255 for tile in tiles) + b"\xff")
        decoded = tuple(a << 8 | b for a, b in
                        zip(decode_literal_stream(high.payload), decode_literal_stream(low.payload)))
        _require(decoded == tiles, "Compiled stream Tile32 readback differs")
        rebuilt = [0] * 1024
        for cell, tile in enumerate(decoded):
            y, x = divmod(cell, 16)
            for quadrant, value in enumerate(definitions[tile]):
                rebuilt[(y * 2 + quadrant // 2) * 32 + x * 2 + quadrant % 2] = value
        _require(tuple(rebuilt) == document.maps[index],
                 "Compiled map Tile16 readback differs")
        area = FIRST_MAP + index
        plans.append(MapPlan(area, tiles, high, low, tuple(directory.get(area, quadrant_map_plan(area))),
                             copy.deepcopy(document.properties[index])))
    return CompiledTerrain(tuple(plans), tuple(sorted(added)), copy.deepcopy(document.edge_connections))


# Name accepted by build adapters that identify the project-specific compiler.
compile_project_terrain = compile_terrain
