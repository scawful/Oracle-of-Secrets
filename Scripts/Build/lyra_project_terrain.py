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
from pathlib import Path, PurePosixPath, PureWindowsPath
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
RUNTIME_PROPERTY_DEFAULTS = {
    "mosaic": 0, "subscreen_overlay": 255, "area_specific_bg_color": None,
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


def gameplay_area_footprint(parent_map_id: int, size: str) -> tuple[int, ...]:
    """Return the authored row-major footprint; no alignment or clamping."""
    _require(_integer(parent_map_id, FIRST_MAP, FIRST_MAP + MAP_COUNT - 1),
             "Gameplay area parent must be A0-BF")
    dimensions = {"small": (1, 1), "wide": (2, 1), "tall": (1, 2), "large": (2, 2)}
    _require(type(size) is str and size in dimensions, "Unknown gameplay area size")
    width, height = dimensions[size]
    row, column = divmod(parent_map_id - FIRST_MAP, 8)
    _require(column + width <= 8 and row + height <= 4,
             "Gameplay area footprint leaves A0-BF grid")
    return tuple(parent_map_id + y * 8 + x for y in range(height) for x in range(width))


def validated_gameplay_areas(value) -> tuple[dict, ...]:
    """Validate a JSON array or parsed tuple without sorting or inferring areas."""
    _require(type(value) in (list, tuple) and 1 <= len(value) <= MAP_COUNT,
             "gameplay_areas requires 1..32 explicit areas")
    owned = set()
    for area in value:
        _keys(area, {"parent_map_id", "size", "maps"}, "gameplay area")
        expected = gameplay_area_footprint(area["parent_map_id"], area["size"])
        maps = area["maps"]
        _require(type(maps) is list and 1 <= len(maps) <= 4
                 and all(_integer(map_id, FIRST_MAP, FIRST_MAP + MAP_COUNT - 1) for map_id in maps),
                 "Gameplay area maps must be an A0-BF integer array")
        _require(tuple(maps) == expected,
                 "Gameplay area maps must match its exact ordered footprint")
        _require(not owned.intersection(maps), "Gameplay areas cannot share ownership of a map")
        owned.update(maps)
    return tuple(copy.deepcopy(area) for area in value)


def gameplay_render_directory(areas) -> dict[int, Quad]:
    """Map each authored member to the parent's four native load quadrants.

    Wide/tall/small loads repeat their absent quadrants, as the native loader
    always decompresses four pages. Unassigned pages acquire no layout here.
    """
    result = {}
    for area in validated_gameplay_areas(areas):
        members, size = tuple(area['maps']), area['size']
        quadrants = (members * 4 if size == 'small' else members * 2 if size == 'wide'
                     else (members[0], members[0], members[1], members[1])
                     if size == 'tall' else members)
        result.update((member, quadrants) for member in members)
    return result


@dataclass(frozen=True)
class TerrainDocument:
    profile: dict
    # Maps and properties are ordered A0..BF; each map is row-major Tile16.
    maps: tuple[tuple[int, ...], ...]
    properties: tuple[dict, ...]
    edge_connections: tuple[dict, ...] = ()
    # Complete schema-3/4/5 drafts survive read-only subset planning. They are not
    # a promise that a runtime adapter consumes their metadata.
    authoring: tuple[dict, ...] = ()
    flight_points: tuple[dict, ...] = ()
    # Empty means UNASSIGNED for older schemas; never infer areas from map IDs.
    gameplay_areas: tuple[dict, ...] = ()
    # Schema-7 values retain authoring and provenance without granting runtime
    # lowering or write access to the named source tree.
    boat_transport: dict | None = None
    next_flight_point_id: int = 1
    # Schema-8 source metadata is retained without authenticating a writer.
    whirlpool_transport: dict | None = None


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


def validated_boat_transport(value) -> dict | None:
    """Retain schema-7 authoring; filesystem/source admission is independent."""
    if value is None:
        return None
    _keys(value, {"source_root", "source_path", "source_template", "endpoints"},
          "boat transport")
    root = value["source_root"]
    _require(type(root) is str and root and "\0" not in root
             and (PurePosixPath(root).is_absolute() or PureWindowsPath(root).is_absolute()),
             "Boat source_root must be absolute")
    _require(value["source_path"] == "Data/overworld/kalyxo_boat_placements.asm",
             "Unsupported boat source_path")
    template = value["source_template"]
    _require(type(template) is str and template and "\0" not in template
             and len(template.encode("utf-8")) <= 65536,
             "Invalid boat source_template")
    endpoints = value["endpoints"]
    _require(type(endpoints) is list and len(endpoints) == 2,
             "Boat transport requires two endpoints")
    keys = set()
    for endpoint in endpoints:
        _keys(endpoint, {"exit_id", "parent_map", "world_x", "world_y",
                         "area_size", "facing", "name"}, "boat endpoint")
        key = endpoint["exit_id"]
        _require(_integer(key, 0x186, 0x187) and key not in keys,
                 "Boat endpoints require unique keys0186/0187")
        keys.add(key)
        parent, x, y, size = (endpoint[k] for k in
                              ("parent_map", "world_x", "world_y", "area_size"))
        _require(_integer(parent, 0, 0xBF) and _integer(x, 0, 4095)
                 and _integer(y, 0, 4095) and _integer(size, 0, 3),
                 "Invalid boat endpoint geometry")
        col, row = parent % 8, parent % 0x40 // 8
        width, height = (2 if size in (1, 2) else 1), (2 if size in (1, 3) else 1)
        _require(col + width <= 8 and row + height <= 8
                 and col * 512 <= x < (col + width) * 512
                 and row * 512 <= y < (row + height) * 512,
                 "Boat endpoint leaves its explicit gameplay area")
        _require(_integer(endpoint["facing"], 0, 6) and endpoint["facing"] % 2 == 0,
                 "Invalid boat arrival facing")
        name = endpoint["name"]
        _require(type(name) is str and 0 < len(name.encode("utf-8")) <= 80
                 and all(ord(c) >= 32 and ord(c) != 127 for c in name),
                 "Invalid boat endpoint name")
    return copy.deepcopy(value)


WHIRLPOOL_FIELDS = ("source_map", "destination_map", "world_y", "world_x",
                    "vram", "scroll_y", "scroll_x", "camera_y", "camera_x",
                    "scroll_mod_y", "scroll_mod_x")


def _validated_whirlpool_routes(routes) -> None:
    _require(type(routes) is list and len(routes) == 8,
             "Whirlpool transport requires eight ordered routes")
    sources = set()
    for route in routes:
        _keys(route, set(WHIRLPOOL_FIELDS), "whirlpool route")
        for key in WHIRLPOOL_FIELDS:
            maximum = (0xBF if key.endswith("_map") else
                       4088 if key.startswith("world_") else 0xFFFF)
            _require(_integer(route[key], 0, maximum),
                     f"Invalid whirlpool route {key}")
        source = route["source_map"]
        _require(source != 0x1B and source not in sources,
                 "Whirlpool source parents must be unique and exclude castle map1B")
        sources.add(source)


def validated_whirlpool_transport(value, gameplay_areas) -> dict | None:
    """Read schema-8 authoring without opening or granting its source tree."""
    if value is None:
        return None
    _keys(value, {"source_root", "source_path", "source_template", "routes"},
          "whirlpool transport")
    root = value["source_root"]
    _require(type(root) is str and 0 < len(root.encode("utf-8")) <= 4096
             and "\0" not in root
             and (PurePosixPath(root).is_absolute() or PureWindowsPath(root).is_absolute()),
             "Whirlpool source_root must be absolute")
    _require(value["source_path"] == "Data/overworld/whirlpool_placements.asm",
             "Unsupported whirlpool source_path")
    template = value["source_template"]
    _require(type(template) is str and template and "\0" not in template
             and len(template.encode("utf-8")) <= 65536,
             "Invalid whirlpool source_template")
    # Match the Yaze numeric source dialect. The immutable baseline may differ
    # from edited JSON routes, but must contain all eight valid stable slots.
    baseline = {}
    for line in template.split("\n"):
        line = line.split(";", 1)[0]
        if "%whirlpool_route" not in line:
            continue
        call = re.fullmatch(r"[ \t]*%whirlpool_route\(([^()]*)\)[ \t\r]*", line)
        _require(call is not None, "Whirlpool template requires a complete numeric macro call")
        tokens = [token.strip(" \t") for token in call[1].split(",")]
        _require(len(tokens) == 12 and all(
            re.fullmatch(r"(?:[0-9]+|\$[0-9a-fA-F]+)", token) for token in tokens),
            "Whirlpool template requires twelve unsigned word literals")
        numbers = [int(token[1:], 16) if token.startswith("$") else int(token, 10)
                   for token in tokens]
        _require(all(number <= 0xFFFF for number in numbers),
                 "Whirlpool template requires unsigned word literals")
        slot = numbers[0]
        _require(0 <= slot < 8 and slot not in baseline,
                 "Whirlpool template slot is foreign or duplicated")
        baseline[slot] = dict(zip(WHIRLPOOL_FIELDS, numbers[1:]))
    _require(set(baseline) == set(range(8)), "Whirlpool template requires all eight stable slots")
    _validated_whirlpool_routes([baseline[slot] for slot in range(8)])
    _validated_whirlpool_routes(value["routes"])
    parents = {area["parent_map_id"]: area for area in gameplay_areas}
    for route in value["routes"]:
        for parent in (route["source_map"], route["destination_map"]):
            if parent < FIRST_MAP:
                continue
            _require(parent in parents, "Whirlpool tail parent requires an explicit gameplay area")
            if parent == route["destination_map"]:
                size = parents[parent]["size"]
                width = 1024 if size in ("wide", "large") else 512
                height = 1024 if size in ("tall", "large") else 512
                x, y = parent % 8 * 512, (parent % 0x40 // 8) * 512
                _require(x <= route["world_x"] < x + width
                         and y <= route["world_y"] < y + height,
                         "Whirlpool arrival leaves its explicit gameplay area")
    return copy.deepcopy(value)


def parse_terrain_document(text: str | bytes, expected_profile: Mapping, *,
                           expected_asset_bindings: Mapping[int, tuple[str, str, str]] | None = None,
                           allow_authoring_drafts: bool = False,
                           ) -> TerrainDocument:
    """Parse schema 3/4/5/6/7/8 against independently verified native assets.

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
    _require(type(data) is dict and data.get("schema") == "yaze.lyra-terrain"
             and _integer(data.get("schema_version"), 3, 8),
             "Expected Yaze Lyra schema 3, 4, 5, 6, 7 or 8")
    version = data["schema_version"]
    _keys(data, {"schema", "schema_version", "columns", "rows", "map_width",
                 "map_height", "tile_pixels", "profile", "maps",
                 "flight_points", "edge_connections"}
                | ({"gameplay_areas"} if version >= 5 else set())
                | ({"boat_transport", "next_flight_point_id"} if version >= 7 else set())
                | ({"whirlpool_transport"} if version >= 8 else set()),
             "Lyra schema 3/4/5/6/7/8 header")
    for key, value in (("columns", 8), ("rows", 4), ("map_width", 32),
                       ("map_height", 32), ("tile_pixels", 16)):
        _require(_integer(data[key], value, value), f"Invalid Lyra {key}")
    _profile(data["profile"])
    _require(data["profile"] == expected,
             "Lyra profile differs from independently verified source assets")
    gameplay_areas = ()
    if version >= 5:
        _require(type(data["gameplay_areas"]) is list,
                 "gameplay_areas requires a JSON array")
        gameplay_areas = (() if version >= 6 and not data["gameplay_areas"]
                          else validated_gameplay_areas(data["gameplay_areas"]))
        _require(allow_authoring_drafts,
                 "Unsupported runtime metadata: gameplay_areas")
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
    next_flight_point_id = max(flight_ids, default=0) + 1
    boat_transport = None
    if version >= 7:
        next_flight_point_id = data["next_flight_point_id"]
        _require(_integer(next_flight_point_id, 1, 0x100000000)
                 and next_flight_point_id > max(flight_ids, default=0),
                 "Invalid next_flight_point_id")
        boat_transport = validated_boat_transport(data["boat_transport"])
    whirlpool_transport = (validated_whirlpool_transport(data["whirlpool_transport"], gameplay_areas)
                           if version >= 8 else None)
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
    has_background_palette = False
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
        _require(type(props) is dict, "Malformed Lyra map properties keys")
        has_override = "background_palette" in props
        _keys(props, PROPERTY_KEYS | (set(RUNTIME_PROPERTY_DEFAULTS) if version >= 6 else set())
              | ({"background_palette"} if version >= 4 and has_override else set()), "Lyra map properties")
        if version >= 6:
            _require(_integer(props["mosaic"], 0, 15), "Lyra mosaic requires direction bits0..15")
            _require(_integer(props["subscreen_overlay"], 0, 191) or props["subscreen_overlay"] == 255
                     and type(props["subscreen_overlay"]) is int,
                     "Lyra subscreen overlay requires map00..BF or255 for none")
            _require(props["area_specific_bg_color"] is None
                     or _integer(props["area_specific_bg_color"], 0, 0x7FFF),
                     "Lyra area BG color requires BGR555 or null inheritance")
        if has_override:
            _require(_array(props["background_palette"], 128, 0, 0x7FFF),
                     "Lyra background palette requires 128 BGR555 integers")
            _require(allow_authoring_drafts,
                     f"Unsupported runtime metadata: {area:02X}.background_palette")
            has_background_palette = True
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
            defaults = {**DEFAULT_PROPERTIES, **(RUNTIME_PROPERTY_DEFAULTS if version >= 6 else {})}
            _require(props == defaults,
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
    _require(version != 4 or has_background_palette,
             "Lyra schema 4 requires a background palette override")
    ids = range(FIRST_MAP, FIRST_MAP + MAP_COUNT)
    return TerrainDocument(expected, tuple(maps[i] for i in ids),
                           tuple(properties[i] for i in ids), tuple(copy.deepcopy(edges)),
                           tuple(authoring[i] for i in ids), tuple(copy.deepcopy(flights)), gameplay_areas,
                           boat_transport, next_flight_point_id, whirlpool_transport)


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
    selected_ids = {FIRST_MAP + index for index in selected}
    authored_directory = gameplay_render_directory(document.gameplay_areas) if document.gameplay_areas else {}
    if authored_directory:
        _require(selected_ids <= set(authored_directory),
                 "CURRENT_GAMEPLAY_AREAS_UNASSIGNED: selected pages need explicit gameplay areas")
    directory = {area: row for area, row in authored_directory.items() if area in selected_ids}
    if render_directory is not None:
        directory.update(render_directory)
    for area, row in directory.items():
        _require(type(area) is int and area in selected_ids
                 and isinstance(row, (tuple, list)) and len(row) == 4
                 and all(type(source) is int and source in selected_ids for source in row)
                 and (tuple(row) == authored_directory[area] if area in authored_directory
                      else tuple(row) in (quadrant_map_plan(area), (area,) * 4)),
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
