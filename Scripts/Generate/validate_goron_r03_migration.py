#!/usr/bin/env python3
"""Validate the pinned Goron R03 base/source pair without writing a ROM."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

from validate_custom_collision_source import (
    NUMBER_OF_ROOMS,
    POINTER_TABLE_START,
    SOURCE_PATH,
    _decode_room,
    _load_source,
)


SPEC_PATH = Path("Data/dungeons/migrations/goron_r03.json")
SHA256 = re.compile(r"[0-9a-f]{64}")
HEX_BYTES = re.compile(r"(?:[0-9A-F]{2})+")
PC_OFFSET = re.compile(r"0x[0-9A-F]{6}")


class MigrationError(ValueError):
    """The specification or supplied preimage does not match the pinned pair."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise MigrationError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_edits(patch: dict, size: int) -> None:
    require(type(patch.get("changed_bytes")) is int, "Invalid changed-byte count")
    edits = patch.get("edits")
    require(isinstance(edits, list) and bool(edits), "Missing migration edits")
    require(type(patch.get("runs")) is int and patch["runs"] == len(edits),
            "Edit-run count differs")
    previous_end, changed = 0, 0
    for edit in edits:
        require(isinstance(edit, dict) and set(edit) == {"pc", "before", "after"},
                "Invalid edit fields")
        require(isinstance(edit["pc"], str) and PC_OFFSET.fullmatch(edit["pc"]),
                "Invalid PC offset")
        before, after = edit["before"], edit["after"]
        require(isinstance(before, str) and HEX_BYTES.fullmatch(before)
                and isinstance(after, str) and HEX_BYTES.fullmatch(after),
                "Invalid edit hex bytes")
        require(len(before) == len(after), "Edit changes ROM size")
        start, length = int(edit["pc"], 16), len(before) // 2
        require(start >= previous_end and start + length <= size,
                "Edits overlap, are unsorted, or exceed ROM size")
        require(all(a != b for a, b in zip(bytes.fromhex(before), bytes.fromhex(after))),
                "Edit includes unchanged bytes")
        previous_end, changed = start + length, changed + length
    require(changed == patch["changed_bytes"], "Changed-byte count differs")


def replay(data: bytes, patch: dict, target: dict) -> bytes:
    """Return a reconstructed byte string; this function has no write path."""
    require(len(data) == target["size"], "Preimage ROM size differs")
    require(digest(data) == patch["input_sha256"], "Preimage SHA256 differs")
    validate_edits(patch, target["size"])
    reconstructed = bytearray(data)
    for edit in patch["edits"]:
        start = int(edit["pc"], 16)
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        require(reconstructed[start:start + len(before)] == before,
                f"Edit preimage differs at {edit['pc']}")
        reconstructed[start:start + len(after)] = after
    result = bytes(reconstructed)
    require(digest(result) == target["sha256"], "Reconstructed SHA256 differs")
    return result


def validate_spec(root: Path, rom: Path | None = None) -> dict:
    root = root.resolve()
    spec = json.loads((root / SPEC_PATH).read_text(encoding="utf-8"))
    require(isinstance(spec, dict), "Specification must be an object")
    require(spec.get("schema") == "goron-r03-base-source-v1", "Unknown migration schema")
    require(spec.get("source_dependency") == {
        "pull_request": 240,
        "head": "ca19cca6b1c3d99cdd158a90dc5449e7cd9d972c",
    }, "PR240 source dependency differs")
    require(spec.get("feature_profile") == {
        "flag": "ENABLE_MINECART_CART_SHUTTERS",
        "tested_value": 1,
        "tracked_default": 0,
    }, "Explicit feature profile differs")
    require(type(spec["feature_profile"]["tested_value"]) is int
            and type(spec["feature_profile"]["tracked_default"]) is int,
            "Feature values must be integers")
    require(spec.get("tested_patched_sha256") ==
            "03d8e06a3efbd2a86fc2e6076263218112996e5509eda09475349d8a8653da5e",
            "Qualified patched candidate differs")
    require(spec.get("application_policy") == {
        "verifier_is_read_only": True,
        "shared_base_application_requires_scawful_approval": True,
        "never_apply_to_patched_rom": True,
        "unknown_input_hash": "refuse; no partial or semantic rebase",
    }, "Application policy differs")
    for relative in ("Util/macros.asm", "Config/feature_flags.asm"):
        defaults = re.findall(
            r"^!ENABLE_MINECART_CART_SHUTTERS\s*=\s*([01])\s*$",
            (root / relative).read_text(encoding="utf-8"), re.MULTILINE,
        )
        require(defaults == ["0"], f"Prototype default differs in {relative}")
    target = spec.get("target", {})
    require(isinstance(target, dict), "Invalid target record")
    require(type(target.get("size")) is int and target["size"] == 2097152,
            "Target must be a headerless 2 MiB edit ROM")
    require(target.get("sha256") ==
            "28b21601f0bf5d068349be8f745b74a19dbb675c3d4b1145dc04f40139aa2781",
            "Pinned R03 target differs")
    source = spec.get("collision_source", {})
    require(isinstance(source, dict), "Invalid collision source record")
    require(source.get("path") == SOURCE_PATH.as_posix(), "Collision source path differs")
    rooms, source_bytes, source_sha = _load_source(root / SOURCE_PATH)
    require(source.get("sha256") == source_sha, "Collision source SHA256 differs")
    require(source.get("room_count") == len(rooms) == 20
            and source.get("tile_count") == sum(map(len, rooms.values())) == 3395,
            "Collision source counts differ")
    require(source.get("explicit_zero_count") ==
            sum(value == 0 for tiles in rooms.values() for value in tiles.values()) == 123,
            "Explicit zero count differs")
    require(source.get("room_contracts") == {
        f"0x{room:02X}": {"tile_count": len(rooms[room]),
                          "explicit_zero_offsets": sorted(k for k, v in rooms[room].items() if v == 0)}
        for room in (0x88, 0x97, 0x98)
    }, "Three-room collision contract differs")
    require(source_sha ==
            "216f201247c7cf46210483c669d3838732b0c0ea8203dab974138f9336872b83",
            "Pinned collision source differs")
    migrations = spec.get("migrations", {})
    require(isinstance(migrations, dict), "Invalid migration records")
    require(set(migrations) == {"seal-only", "full-base"}, "Migration choices differ")
    expected = {
        "seal-only": ("19277e47b02e6d4018b7be6526365058ab816e077f9e7e6b9843c3fdd1b69887", 4, 2),
        "full-base": ("e75690add9200a8db00a44772b5aaf05c04284616ec8aaf9aa02919096ed14ac", 2062, 135),
    }
    for name, patch in migrations.items():
        require(isinstance(patch, dict), "Invalid migration record")
        require((patch.get("input_sha256"), patch.get("changed_bytes"), patch.get("runs"))
                == expected[name], f"Pinned {name} identity/counts differ")
        require(isinstance(patch["input_sha256"], str)
                and SHA256.fullmatch(patch["input_sha256"]), "Invalid preimage hash")
        validate_edits(patch, target["size"])
    require(migrations["seal-only"]["edits"] == [
        {"pc": "0x0FD2A2", "before": "4002", "after": "FFFF"},
        {"pc": "0x138617", "before": "A102", "after": "FFFF"},
    ], "Four-byte seal provenance differs")
    result = {"passed": True, "collision_sha256": digest(source_bytes),
              "explicit_zero_count": 123, "target_sha256": target["sha256"],
              "rom_replayed": False}
    if rom is not None:
        original = rom.read_bytes()
        matches = [name for name, patch in migrations.items()
                   if patch["input_sha256"] == digest(original)]
        require(len(matches) == 1, "ROM is not one of the two exact preimages")
        reconstructed = replay(original, migrations[matches[0]], target)
        actual = {}
        for room in range(NUMBER_OF_ROOMS):
            slot = POINTER_TABLE_START + room * 3
            pointer = int.from_bytes(reconstructed[slot:slot + 3], "little")
            if pointer:
                tiles = _decode_room(reconstructed, room, pointer)
                if tiles:
                    actual[room] = tiles
        require(actual == rooms, "Reconstructed collision maps differ from tracked source")
        result.update(rom_replayed=True, migration=matches[0], input_sha256=digest(original))
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--rom", type=Path, help="read an exact preimage and replay in memory only")
    args = parser.parse_args()
    try:
        print(json.dumps(validate_spec(args.root, args.rom), sort_keys=True))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"ERROR: Goron R03 migration invalid: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
