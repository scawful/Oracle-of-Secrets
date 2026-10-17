"""Validate the schema consumed by Yaze's PaletteCatalog::Parse.

Consumer contract: yaze dec9ba7d, src/core/palette_catalog.cc and
src/zelda3/palette_constants.h. Keep this version-1 producer check aligned when
that consumer changes; exporting a bundle must not require a Yaze checkout.
"""

from __future__ import annotations

import json
from pathlib import Path

MAX_BYTES = 1024 * 1024
GROUP_COUNTS = {
    "ow_main": 6, "ow_aux": 20, "ow_animated": 14, "hud": 2,
    "global_sprites": 2, "armors": 5, "swords": 4, "shields": 3,
    "sprites_aux1": 12, "sprites_aux2": 11, "sprites_aux3": 24,
    "dungeon_main": 20, "grass": 3, "3d_object": 2, "ow_mini_map": 2,
}
USES = {"link_items", "npcs", "enemies", "bosses", "environment", "hud",
        "effects", "mixed"}
WORLDS = {"light_world", "dark_world", "underworld", "special", "shared"}


def _fields(value, fields):
    if not isinstance(value, dict) or set(value) != set(fields.split()):
        raise ValueError("Missing or unsupported catalog fields")


def _text(value):
    if (not isinstance(value, str) or not value or "\0" in value
            or len(value.encode("utf-8")) > 4096):
        raise ValueError("Catalog text must contain 1..4096 UTF-8 bytes without NUL")
    return value


def _integer(value, maximum):
    # bool is an int subclass in Python, but is not a JSON integer in Yaze.
    if type(value) is not int or not 0 <= value <= maximum:
        raise ValueError("Catalog integer outside supported range")
    return value


def _array(value, maximum):
    if not isinstance(value, list) or len(value) > maximum:
        raise ValueError("Catalog array exceeds supported size or has wrong type")
    return value


def _invalid_constant(value):
    raise ValueError(f"Non-JSON number: {value}")


def validate_palette_catalog(path: Path) -> None:
    """Reject catalogs Yaze cannot load before publishing their descriptor."""
    with path.open("rb") as stream:
        raw = stream.read(MAX_BYTES + 1)
    if len(raw) > MAX_BYTES:
        raise ValueError("Palette catalog exceeds 1 MiB")
    try:
        document = json.loads(raw.decode("utf-8-sig"),
                              parse_constant=_invalid_constant)
        _fields(document, "schema_version game_id entries")
        if _integer(document["schema_version"], 1) != 1:
            raise ValueError("Palette catalog requires schema_version 1")
        _text(document["game_id"])
        keys, identities = set(), set()
        for entry in _array(document["entries"], 4096):
            _fields(entry, "key name group index world use description provenance "
                           "ownership usages")
            for field in ("key", "name", "group", "world", "use", "description",
                          "provenance", "ownership"):
                _text(entry[field])
            index = _integer(entry["index"], 255)
            if index >= GROUP_COUNTS.get(entry["group"], 0):
                raise ValueError("Unknown palette group or index")
            if (entry["world"] not in WORLDS or entry["use"] not in USES
                    or entry["ownership"] not in {"rom", "asm"}):
                raise ValueError("Unsupported world, use or ownership")
            identity = (entry["group"], index)
            if entry["key"] in keys or identity in identities:
                raise ValueError("Duplicate palette key or group/index")
            keys.add(entry["key"])
            identities.add(identity)
            for usage in _array(entry["usages"], 256):
                _fields(usage, "name context use obj_row sprite_sheets source")
                for field in ("name", "context", "use", "source"):
                    _text(usage[field])
                if usage["use"] not in USES:
                    raise ValueError("Unsupported usage category")
                _integer(usage["obj_row"], 7)
                for sheet in _array(usage["sprite_sheets"], 8):
                    _integer(sheet, 0x6B)
    except (ValueError, RecursionError) as error:
        raise ValueError(f"Invalid palette catalog: {error}") from error
