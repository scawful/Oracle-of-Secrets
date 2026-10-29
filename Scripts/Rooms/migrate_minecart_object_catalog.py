#!/usr/bin/env python3
"""Plan the 37-record legacy minecart object migration without changing input.

Default is a read-only JSON dry run. --output and --receipt publish two NEW
private files. Their intermediate image needs the MCR2 source in a normal build.
--project-output instead publishes a NEW private version 2 editing project with
the data-only ROM, immutable migration evidence and owned source bindings. It
does not apply runtime ASM, launch an editor or replace an existing project.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import io
import json
import os
import re
import shlex
import stat
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from sky_d8_room_writer import (
    DEFAULT_PROTECTED_DIRS,
    PlanError,
    check_new_target,
    parse_object_stream,
    publish_exclusive,
    read_input,
    readback,
)

ROOM_COUNT = 296
POINTER_OPERAND = 0x874C
MARKER_PC = 0x160017
MCR2_MARKER = b"MCR2\x10\x0D\x02\x00"
EXPECTED_RECORDS = 37
EXPECTED_CHANGED_BYTES = 111
MIGRATION = {12: 5, 13: 6, 14: 7, 15: 8}
PROTECTED_DIRS = (*DEFAULT_PROTECTED_DIRS, Path.home() / "Zelda" / "Projects")
OBJECT_FILES = {
    "0x31": ["track_LR.bin", "track_UD.bin", "track_corner_TL.bin", "track_corner_TR.bin",
             "track_corner_BL.bin", "track_corner_BR.bin", "track_floor_UD.bin",
             "track_floor_LR.bin", "track_floor_corner_TL.bin", "track_floor_corner_TR.bin",
             "track_floor_corner_BL.bin", "track_floor_corner_BR.bin",
             *[f"track_tjunction_{side}.bin" for side in "NSEW"]],
    "0x32": ["furnace.bin", "firewood.bin", "ice_chair.bin", "", "",
             "track_floor_any.bin", "wall_sword_house.bin", "track_any.bin", "small_statue.bin",
             *[f"track_floor_tjunction_{side}.bin" for side in "NSEW"]],
    "0x54": ["kydreeok_body.bin", "manhandla_body_1a.bin"],
}
LEGACY_OBJECT_FILES = {
    "0x31": OBJECT_FILES["0x31"][:12] +
    ["track_floor_any.bin", "wall_sword_house.bin", "track_any.bin", "small_statue.bin"],
    "0x32": OBJECT_FILES["0x32"][:3],
    "0x54": OBJECT_FILES["0x54"],
}


def unique_json(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON key")
        result[key] = value
    return result


def json_document(data: bytes):
    return json.loads(data, object_pairs_hook=unique_json)


def project_fields(data: bytes) -> tuple[dict, dict, dict, object]:
    """Read the existing INI/JSON Yaze fields without changing their schema."""
    text = data.decode("utf-8-sig")
    if text.lstrip().startswith("{"):
        document = json_document(data)
        require(type(document) is dict and type(document.get("yaze_project")) is dict,
                "Expected a yaze_project JSON descriptor")
        project = document["yaze_project"]
        overlay = project.get("dungeon_overlay", {})
        objects = project.get("custom_objects", {})
        require(type(overlay) is dict and type(objects) is dict, "Invalid project catalog fields")
        return project, overlay, objects, document
    config = configparser.ConfigParser(interpolation=None, strict=True)
    config.optionxform = str
    config.read_string(text)
    require(not config.defaults() and config.has_section("files"), "Invalid project files section")
    overlay = dict(config["dungeon_overlay"]) if config.has_section("dungeon_overlay") else {}
    objects = dict(config["custom_objects"]) if config.has_section("custom_objects") else {}
    return dict(config["files"]), overlay, objects, config


def project_reference(project: Path, value: str) -> Path:
    require(type(value) is str and value and "\0" not in value, "Missing project input reference")
    path = Path(value)
    return (path if path.is_absolute() else project.parent / path).resolve(strict=True)


def exact_keys(value, keys, label):
    require(type(value) is dict and set(value) == set(keys), f"Malformed {label}")


def bound_file(path: Path) -> tuple[Path, bytes]:
    require(path.is_absolute() and "\0" not in str(path), "Bound input path must be absolute")
    require(stat.S_ISREG(path.lstat().st_mode), "Bound input must be a regular non-symlink file")
    canonical = path.resolve(strict=True)
    require(path == canonical, "Bound input path is not canonical")
    data = path.read_bytes()
    require(path.resolve(strict=True) == canonical and path.stat().st_size == len(data),
            "Bound input changed while reading")
    return canonical, data


def verify_native_save(data: bytes, project: Path, project_rom: Path,
                       migration_path: Path, save_path: Path, context_path: Path,
                       project_snapshot: bytes, migration_snapshot: bytes) -> dict:
    """Reuse the native Save contract, not a minecart-specific receipt format.

    Invariants follow Scripts/Build/lyra_current_transfer.py::_live and Yaze
    core/native_save_receipt.cc. No foreign worktree or Lyra graph is imported.
    """
    project, project_bytes = bound_file(project)
    require(project_bytes == project_snapshot, "Project descriptor changed during admission")
    project_rom, current_rom = bound_file(project_rom)
    require(data == current_rom, "Copied assembly input differs from the current project ROM")
    require(save_path == Path(str(project) + ".native-save.json"),
            "Native Save receipt is not adjacent to this project")
    snapshots = {project: project_bytes, project_rom: current_rom}
    for path in (save_path, context_path, migration_path):
        canonical, content = bound_file(path)
        snapshots[canonical] = content
    require(snapshots[migration_path] == migration_snapshot,
            "Migration evidence changed during admission")
    require(len(snapshots[save_path]) <= 1024 * 1024 and
            len(snapshots[context_path]) <= 1024 * 1024, "Native Save metadata exceeds size limit")
    receipt = json_document(snapshots[save_path])
    exact_keys(receipt, {"kind", "generation", "operation_id", "operation", "receipt_path",
                         "bindings_complete", "binding_errors", "artifacts"}, "native Save receipt")
    generation, operation = receipt["generation"], receipt["operation_id"]
    require(receipt["kind"] == "yaze.native_save.v1" and type(generation) is int and
            0 < generation <= 0xFFFFFFFFFFFFFFFF and type(operation) is str and
            0 < len(operation) <= 128 and all(0x20 <= ord(c) <= 0x7E for c in operation) and
            receipt["operation"] in ("save", "save_as") and receipt["receipt_path"] == str(save_path) and
            receipt["bindings_complete"] is True and receipt["binding_errors"] == [],
            "A current fully bound native Save is required")
    require(type(receipt["artifacts"]) is list and len(receipt["artifacts"]) <= 256,
            "Invalid native Save artifacts")
    artifacts, paths = {}, {}
    for row in receipt["artifacts"]:
        exact_keys(row, {"role", "path", "sha256", "bytes"}, "native Save artifact")
        role = row["role"]
        require(type(role) is str and len(role) <= 128 and
                re.fullmatch(r"[a-z][a-z0-9._:-]*", role) is not None and role not in artifacts,
                "Unknown or duplicate native Save artifact role")
        require(type(row["path"]) is str and type(row["sha256"]) is str and
                re.fullmatch(r"[0-9a-f]{64}", row["sha256"]) is not None and
                type(row["bytes"]) is int and 0 <= row["bytes"] <= 0xFFFFFFFFFFFFFFFF,
                "Invalid native Save artifact binding")
        path, content = bound_file(Path(row["path"]))
        require(digest(content) == row["sha256"] and len(content) == row["bytes"],
                "Native Save artifact changed after Save")
        prior = paths.get(str(path).lower())
        require(prior is None or prior == (str(path), row["sha256"], row["bytes"]),
                "Conflicting native Save artifact aliases")
        paths[str(path).lower()] = (str(path), row["sha256"], row["bytes"])
        require(path not in snapshots or snapshots[path] == content,
                "Native Save input changed during admission")
        snapshots[path] = content
        artifacts[role] = row
    required = {"rom": project_rom, "project": project,
                "dependency.minecart_catalog_migration": migration_path}
    require(set(required) | {"producer"} <= set(artifacts), "Native Save required roles are missing")
    for role, path in required.items():
        require(artifacts[role]["path"] == str(path), "Native Save binds another project/input")
    context = json_document(snapshots[context_path])
    exact_keys(context, {"kind", "editing_source_path", "project_path", "rom_path",
                        "producer", "state", "native_commit"}, "native Save context")
    origin = context["editing_source_path"]
    require(type(origin) is str and Path(origin).is_absolute() and
            str(Path(origin).resolve()) == origin and
            context_path.parent.name == "native-saves" and
            not context_path.is_relative_to(project.parent) and
            context_path.name == digest(origin.encode("utf-8")) + ".json",
            "Native Save context does not use the stable editing-source identity")
    require(context["kind"] == "yaze.native_save_context.v1" and context["state"] == "committed" and
            context["project_path"] == str(project) and context["rom_path"] == str(project_rom) and
            context["producer"] == artifacts["producer"], "Native Save context moved or was retired")
    exact_keys(context["native_commit"], {"receipt_path", "generation", "operation_id"}, "native commit")
    require(type(context["native_commit"]["generation"]) is int and
            context["native_commit"] == {"receipt_path": str(save_path), "generation": generation,
                                         "operation_id": operation}, "Native Save generation is stale")
    # Rehash every declared artifact and metadata input, not only required roles.
    for path, expected in snapshots.items():
        require(bound_file(path)[1] == expected, "Native Save input changed during verification")
    return {"catalog": "project-v2-native-save", "generation": generation,
            "operation_id": operation, "receipt_path": str(save_path),
            "native_receipt_sha256": digest(snapshots[save_path]),
            "native_context_sha256": digest(snapshots[context_path]),
            "project_sha256": digest(project_bytes), "producer_sha256": artifacts["producer"]["sha256"],
            "migration_sha256": digest(snapshots[migration_path])}


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snes_to_pc(address: int) -> int:
    require(address & 0x8000 != 0, f"Not a LoROM pointer: {address:06X}")
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def census(data: bytes) -> tuple[dict, list[dict]]:
    """Parse every room through the maintained parser, with stream boundaries."""
    require(0x200000 <= len(data) <= 0x1000000, "Expected an unheadered 2-16 MiB ROM")
    table = snes_to_pc(int.from_bytes(data[POINTER_OPERAND:POINTER_OPERAND + 3], "little"))
    require(table + ROOM_COUNT * 3 <= len(data), "Room pointer table exceeds ROM")
    aliases: dict[int, list[int]] = defaultdict(list)
    for room in range(ROOM_COUNT):
        slot = table + room * 3
        start = snes_to_pc(int.from_bytes(data[slot:slot + 3], "little"))
        require(start + 2 < len(data), f"Room {room:03X} pointer exceeds ROM")
        require(not (table <= start < table + ROOM_COUNT * 3), "Room points into pointer table")
        aliases[start].append(room)

    starts = sorted(aliases)
    streams = {}
    records = []
    for index, start in enumerate(starts):
        limit = starts[index + 1] if index + 1 < len(starts) else len(data)
        stream = parse_object_stream(data, start, limit)
        require(stream.end <= limit, "Overlapping object streams")
        streams[start] = (stream.end, stream.header.hex(), stream.has_marker,
                          tuple(door.hex() for door in stream.doors))
        for room in aliases[start]:
            pos = start + 2
            for layer, objects in enumerate(stream.lists):
                for record_index, raw in enumerate(objects):
                    require(data[pos:pos + 3] == raw, "Object cursor/preimage mismatch")
                    records.append({"room": room, "layer": layer, "index": record_index,
                                    "pc": pos, "raw": raw.hex(),
                                    "aliased_rooms": aliases[start]})
                    pos += 3
                if layer < 2:
                    pos += 2
    return {"table": table, "streams": streams}, records


def plan_migration(data: bytes, expected_sha256: str) -> tuple[bytes, dict]:
    require(re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) is not None,
            "Expected SHA-256 must contain 64 hexadecimal characters")
    require(digest(data) == expected_sha256.lower(), "Input SHA-256 differs from expected input")
    require(data[MARKER_PC:MARKER_PC + 4] != b"MCR2",
            "MCR2 catalog already present; room migration must precede the new runtime build")
    structure, records = census(data)
    changes = []
    for record in records:
        raw = bytes.fromhex(record["raw"])
        b1, b2, object_id = raw
        if b1 >= 0xFC or object_id >= 0xF8:
            continue  # Other encoding families do not use the size-subtype ABI.
        subtype = ((b1 & 3) << 2) | (b2 & 3)
        require(not (object_id == 0x32 and subtype >= 3),
                "Already migrated or ambiguous custom-object 32 catalog")
        if object_id != 0x31 or subtype not in MIGRATION:
            continue
        require(len(record["aliased_rooms"]) == 1,
                "Migration target has aliased room consumers; explicit alias review required")
        target = MIGRATION[subtype]
        new = bytes(((b1 & 0xFC) | (target >> 2), (b2 & 0xFC) | (target & 3), 0x32))
        changes.append({**record, "old": raw.hex(), "new": new.hex(),
                        "x": b1 >> 2, "y": b2 >> 2,
                        "old_object": 0x31, "old_subtype": subtype,
                        "new_object": 0x32, "new_subtype": target})
    require(len(changes) == EXPECTED_RECORDS,
            f"Expected {EXPECTED_RECORDS} reviewed placements, found {len(changes)}")
    require(len({r["pc"] for r in changes}) == len(changes), "Duplicate migration record")

    candidate = bytearray(data)
    allowed = set()
    for change in changes:
        pos = change["pc"]
        require(candidate[pos:pos + 3].hex() == change["old"], "Record CAS preimage differs")
        candidate[pos:pos + 3] = bytes.fromhex(change["new"])
        allowed.update(range(pos, pos + 3))
    result = bytes(candidate)
    changed = {i for i, (old, new) in enumerate(zip(data, result)) if old != new}
    require(changed == allowed and len(changed) == EXPECTED_CHANGED_BYTES,
            "Migration changed bytes outside the exact 37 records / 111 bytes")
    after_structure, after_records = census(result)
    require(structure == after_structure, "Room headers, pointers or door data changed")
    replacements = {r["pc"]: r["new"] for r in changes}
    expected_records = [{**r, "raw": replacements.get(r["pc"], r["raw"])} for r in records]
    require(after_records == expected_records,
            "Object order, coordinates, layers or unrelated room records changed")
    return result, {
        "schema": "oracle-minecart-object-migration/v1",
        "state": "intermediate-old-runtime", "editor_ready": False, "runtime_ready": False,
        "next": "Compose these room records with the MCR2 handlers through the normal build owner",
        "input_sha256": digest(data), "output_sha256": digest(result), "bytes": len(data),
        "rooms_parsed": ROOM_COUNT, "record_count": len(changes), "changed_bytes": len(changed),
        "mapping": {f"31:{old:X}": f"32:{new:X}" for old, new in MIGRATION.items()},
        "records": changes,
        "warnings": ["Header checksum remains unchanged; the normal build owns it",
                     "Unlanded castle/D3 object32:5-8 plans conflict with this catalog; preserve their source packet"],
    }


def migration_receipt_header(receipt: dict | None) -> None:
    require(isinstance(receipt, dict),
            "MCR2 source requires an MCR2 base or OOS_MINECART_MIGRATION_RECEIPT")
    require(receipt.get("schema") == "oracle-minecart-object-migration/v1" and
            receipt.get("mode") == "published" and
            receipt.get("state") == "intermediate-old-runtime",
            "Unsupported or unpublished migration receipt")
    require(receipt.get("record_count") == EXPECTED_RECORDS and
            receipt.get("changed_bytes") == EXPECTED_CHANGED_BYTES and
            receipt.get("rooms_parsed") == ROOM_COUNT,
            "Migration receipt does not bind 37 records / 111 bytes / 296 rooms")
    records = receipt.get("records")
    require(isinstance(records, list) and len(records) == EXPECTED_RECORDS,
            "Migration receipt record list is incomplete")
    require(all(type(receipt.get(key)) is str and re.fullmatch(r"[0-9a-f]{64}", receipt[key])
                for key in ("input_sha256", "output_sha256")), "Migration receipt original SHA-256 is invalid")


def verify_initial_migration(data: bytes, receipt: dict | None) -> dict:
    migration_receipt_header(receipt)
    require(receipt.get("output_sha256") == digest(data),
            "Migration receipt output SHA-256 differs from selected base")
    records = receipt["records"]
    restored = bytearray(data)
    seen = set()
    for record in records:
        require(isinstance(record, dict), "Invalid migration receipt record")
        pos = record.get("pc")
        require(type(pos) is int and 0 <= pos <= len(data) - 3 and pos not in seen,
                "Invalid or duplicate migration receipt offset")
        seen.add(pos)
        old_hex, new_hex = record.get("old"), record.get("new")
        require(isinstance(old_hex, str) and isinstance(new_hex, str) and
                re.fullmatch(r"[0-9a-f]{6}", old_hex) is not None and
                re.fullmatch(r"[0-9a-f]{6}", new_hex) is not None,
                "Invalid migration receipt record bytes")
        require(data[pos:pos + 3].hex() == new_hex, "Migrated record CAS differs from receipt")
        restored[pos:pos + 3] = bytes.fromhex(old_hex)
    # Reconstruct the original complete image, then rerun the exhaustive planner.
    # This verifies old/new bytes, aliases, coordinates, layers and unrelated data
    # rather than trusting receipt counters or an output hash alone.
    original_sha = receipt.get("input_sha256")
    require(isinstance(original_sha, str), "Migration receipt original SHA-256 is invalid")
    planned, verified = plan_migration(bytes(restored), original_sha)
    require(planned == data and verified["records"] == records,
            "Migration receipt structural record proof differs")
    return {"mode": "verify-build-input", "catalog": "migrated-for-MCR2",
            "input_sha256": digest(data), "receipt_required": True,
            "record_count": EXPECTED_RECORDS, "changed_bytes": EXPECTED_CHANGED_BYTES}


def verify_build_input(data: bytes, receipt: dict | None = None, *, project: Path | None = None,
                       project_rom: Path | None = None, migration_path: Path | None = None,
                       native_receipt: Path | None = None, native_context: Path | None = None) -> dict:
    """Admit a ROM marker, the initial migration, or a current qualified Save."""
    marker = data[MARKER_PC:MARKER_PC + 8]
    if marker[:4] == b"MCR2":
        require(marker == MCR2_MARKER, "Unsupported MCR2 catalog counts/version")
        census(data)
        return {"mode": "verify-build-input", "catalog": "MCR2",
                "input_sha256": digest(data), "receipt_required": False}
    if project is not None:
        project = project.resolve(strict=True)
        project_snapshot = read_input(project)
        fields, overlay, _, document = project_fields(project_snapshot)
        version = overlay.get("minecart_catalog_version", 1)
        require(version == ("2" if isinstance(document, configparser.ConfigParser) else 2) and
                type(version) in (str, int), "Unmarked catalog requires explicit project version 2")
        selected_rom = project_reference(project, fields.get("rom_filename"))
        require(project_rom is not None and project_rom.resolve(strict=True) == selected_rom,
                "YAZE_PROJECT_ROM differs from the descriptor ROM")
        require(data == read_input(selected_rom),
                "Copied assembly input differs from the current project ROM")
        configured_migration = project_reference(project, fields.get("minecart_catalog_migration_receipt"))
        require(migration_path is None or migration_path.resolve(strict=True) == configured_migration,
                "Migration receipt differs from the descriptor dependency")
        migration_path = configured_migration
        migration_snapshot = read_input(migration_path)
        receipt = json_document(migration_snapshot)
    migration_receipt_header(receipt)
    if project is None or receipt["output_sha256"] == digest(data):
        proof = verify_initial_migration(data, receipt)
        if project is not None:
            require(read_input(project) == project_snapshot and read_input(selected_rom) == data and
                    read_input(migration_path) == migration_snapshot,
                    "Project admission inputs changed during verification")
        return proof
    require(project is not None and native_receipt is not None and native_context is not None,
            "Edited project version 2 requires a current native Save receipt and context")
    census(data)
    proof = verify_native_save(data, project, selected_rom, migration_path,
                               native_receipt.resolve(strict=True), native_context.resolve(strict=True),
                               project_snapshot, migration_snapshot)
    return {"mode": "verify-build-input", "input_sha256": digest(data),
            "receipt_required": True, **proof}


def update_ini(text: str, updates: dict[str, dict[str, str]]) -> bytes:
    """Change named assignments while preserving unrelated lines/comments."""
    pending = {section: dict(values) for section, values in updates.items()}
    lines, section = [], ""
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("[") and stripped.endswith("]"):
            lines.extend(f"{key}={value}" for key, value in pending.pop(section, {}).items())
            section = stripped[1:-1]
        if not stripped.startswith(("#", ";")) and "=" in line:
            key = line.split("=", 1)[0].strip()
            if key in pending.get(section, {}):
                line = f"{key}={pending[section].pop(key)}"
        lines.append(line)
    lines.extend(f"{key}={value}" for key, value in pending.pop(section, {}).items())
    for section, values in pending.items():
        if values:
            lines.extend(["", f"[{section}]", *[f"{key}={value}" for key, value in values.items()]])
    return ("\n".join(lines) + "\n").encode()


def project_bundle_descriptor(project: Path, original: bytes, migrated: bytes,
                               bundle: Path, private_fields: dict[str, str], assets: Path) -> bytes:
    fields, overlay, objects, document = project_fields(original)
    is_ini = isinstance(document, configparser.ConfigParser)
    version = overlay.get("minecart_catalog_version")
    require(version is None or (type(version) is (str if is_ini else int) and
                                version == ("1" if is_ini else 1)),
            "Project migration requires the legacy version 1 catalog")
    # A relocated descriptor keeps noncatalog input references pointing at their
    # original inputs. Outputs and build commands cannot point at that project.
    directories = {"code_folder", "assets_folder", "patches_folder", "sprite_source_root"}
    file_keys = {"labels_filename", "symbols_filename", "cutscene_shots", "dungeon_tile_patterns",
                 "overworld_graphics_preview", "custom_collision_json", "hack_manifest_file",
                 "sprite_catalog_file", "terrain_catalog_file", "palette_catalog_file",
                 "lyra_terrain_file", "native_save_producer_file", "native_save_transfer_proof_file"}
    rebased = {}
    for key in directories | file_keys:
        value = fields.get(key, "")
        if value:
            require(type(value) is str, "Invalid project path value")
            path = Path(value)
            rebased[key] = str((path if path.is_absolute() else project.parent / path).resolve())
    additions = fields.get("additional_roms", "" if is_ini else [])
    if is_ini and isinstance(additions, str):
        rebased["additional_roms"] = ",".join(
            str((Path(value) if Path(value).is_absolute() else project.parent / value).resolve())
            for value in (s.strip() for s in additions.split(",")) if value)
    elif not is_ini and isinstance(additions, list):
        require(all(type(value) is str for value in additions), "Invalid additional ROM references")
        rebased["additional_roms"] = [str((Path(value) if Path(value).is_absolute()
                                          else project.parent / value).resolve()) for value in additions]
    else:
        raise PlanError("Invalid additional ROM references")
    rebased.update(rom_filename="rom", rom_backup_folder="backups", output_folder="output",
                   custom_objects_folder=str(assets.resolve()), minecart_catalog_migration_receipt="migration-receipt.json",
                   native_save_receipt_file="", lyra_build_request_file="",
                   native_save_transfer_proof_file="transfer/transfer-proof.json",
                   assets_folder="assets", patches_folder="patches", sprite_source_root="sprite-source")
    source_root = Path(__file__).resolve().parents[2]
    rebased.update(private_fields, code_folder=str(source_root))
    # Yaze runs this command from descriptor.parent, not code_folder. Use the
    # reviewed owned script explicitly and preserve its normal checks/output.
    command = ('env OOS_BASE_ROM="$YAZE_PROJECT_ROM" OOS_BACKUP_ROOT=' +
               shlex.quote(str(bundle / "backups")) + " " +
               shlex.quote(str(source_root / "Scripts/Build/build_rom.sh")) + " 99904")
    build = {"build_script": command, "output_folder": str(source_root / "Roms"),
             "git_repository": str(source_root), "build_target": str(source_root / "Roms/oos99904x.sfc"),
             "asm_entry_point": str(source_root / "Oracle_main.asm"), "asm_sources": ""}
    maps = {}
    for key, values in objects.items():
        key = key.removeprefix("object_")
        require(re.fullmatch(r"0[xX][0-9a-fA-F]+", key) is not None, "Invalid custom-object family")
        key = f"0x{int(key, 16):X}"
        require(key in OBJECT_FILES and key not in maps,
                "Unreviewed or aliased custom-object family requires allocation review")
        entries = values.split(",") if isinstance(values, str) else values
        require(type(entries) is list and all(type(v) is str for v in entries), "Invalid object asset map")
        maps[key] = [v.strip() for v in entries]
        require(maps[key] == LEGACY_OBJECT_FILES[key],
                "Custom-object filename overrides require explicit source-copy review")
    maps.update(OBJECT_FILES)
    agent = (dict(document["agent_settings"]) if is_ini and document.has_section("agent_settings")
             else document.get("yaze_project", {}).get("agent_settings", {}) if not is_ini else {})
    agent_paths = {}
    for key in ("custom_system_prompt", "builder_blueprint_path"):
        value = agent.get(key, "")
        if value:
            require(type(value) is str, "Invalid agent input reference")
            path = Path(value)
            agent_paths[key] = str((path if path.is_absolute() else project.parent / path).resolve())
    if is_ini:
        return update_ini(original.decode("utf-8-sig"), {
            "files": rebased,
            "dungeon_overlay": {"minecart_catalog_version": "2", "track_object_ids": "0x31,0x32"},
            "custom_objects": {"object_" + key: ",".join(value) for key, value in maps.items()},
            "rom": {"role": "dev", "expected_hash": hashlib.sha1(migrated).hexdigest()},
            "build": build,
            "workspace": {"recent_files": ""},
            "agent_settings": agent_paths,
        })
    root = document["yaze_project"]
    root.update(rebased)
    root.setdefault("dungeon_overlay", {}).update(minecart_catalog_version=2, track_object_ids=[0x31, 0x32])
    root["custom_objects"] = maps
    root.setdefault("rom", {}).update(role="dev", expected_hash=hashlib.sha1(migrated).hexdigest())
    root.update(build)
    root.setdefault("agent_settings", {}).update(agent_paths)
    root.setdefault("workspace_settings", {})["recent_files"] = []
    return (json.dumps(document, indent=2) + "\n").encode()


def publish_project_bundle(project: Path, source_rom: Path, result: bytes, report: dict,
                           output: Path, expected_project_sha256: str, protected_dirs,
                           assets: Path | None = None) -> dict:
    project = project.resolve(strict=True)
    original = read_input(project)
    require(digest(original) == expected_project_sha256, "Project SHA-256 differs from expected input")
    fields, _, _, _ = project_fields(original)
    require(project_reference(project, fields.get("rom_filename")) == source_rom.resolve(strict=True),
            "Source project does not bind the selected input ROM")
    bundle = check_new_target(output, "project output", protected_dirs, [project, source_rom.resolve()])
    source_root = Path(__file__).resolve().parents[2]
    assets = assets or source_root / "Dungeons/Objects/Data"
    # These sources can be written by normal editor Save or authoring actions.
    # Preview/symbol/manifest inputs are read-only references and remain rebased.
    private_fields, private_bytes, private_sources = {}, {}, {}
    for key in ("lyra_terrain_file", "terrain_catalog_file", "labels_filename", "sprite_catalog_file"):
        if fields.get(key):
            path = project_reference(project, fields[key])
            name = "dependencies/" + key + "/" + path.name
            private_fields[key] = name
            private_bytes[name] = read_input(path)
            private_sources[path] = private_bytes[name]
    # Normal Save and the normal build must consume the same OWNED source.
    # Preparation only records these bindings; it never writes source files.
    external_writable = {}
    owned_sources = {"custom_collision_json": source_root / "Data/dungeons/custom_collision.json",
                     "dungeon_tile_patterns": source_root / "Dungeons/house_walls.asm",
                     "palette_catalog_file": source_root / "Data/graphics/palette_catalog.json"}
    for key, path in owned_sources.items():
        if key == "custom_collision_json" or fields.get(key):
            content = read_input(path)
            private_fields[key] = str(path)
            private_sources[path] = content
            external_writable[key] = {"path": str(path), "sha256": digest(content), "bytes": len(content)}
    _, _, _, project_document = project_fields(original)
    sprite_assets = (project_document.get("yaze_project", {}).get("sprite_assets", [])
                     if isinstance(project_document, dict)
                     else dict(project_document["sprite_assets"]) if project_document.has_section("sprite_assets") else {})
    require(not sprite_assets, "Private bundle with sprite source assets requires explicit source-copy review")
    descriptor = project_bundle_descriptor(project, original, result, bundle, private_fields, assets)
    asset_bytes = {name: read_input(assets / name) for name in sorted({v for values in OBJECT_FILES.values()
                                                                    for v in values if v})}
    require(len(asset_bytes) == 29, "Expected 29 catalog assets")
    legacy_folder = project_reference(project, fields.get("custom_objects_folder"))
    for name in {v for values in LEGACY_OBJECT_FILES.values() for v in values}:
        path = legacy_folder / name
        original_asset = read_input(path)
        require(original_asset == asset_bytes[name],
                "Legacy custom-object artwork differs from owned source; source-copy review required")
        private_sources[path] = original_asset
    receipt = {**report, "mode": "published", "output": str(bundle / "rom"),
               "receipt": str(bundle / "migration-receipt.json")}
    encoded_receipt = (json.dumps(receipt, indent=2) + "\n").encode()
    files = {"rom": result, "migration-receipt.json": encoded_receipt, **private_bytes,
             **{"custom_objects/" + name: content for name, content in asset_bytes.items()}}
    proof = {"schema": "oracle-minecart-project-bundle/v1", "state": "private-project-candidate",
             "catalog_version": 2, "runtime_ready": False, "project": str(bundle / "project.yaze"),
             "source_project": str(project), "source_project_sha256": digest(original),
             "files": {name: {"sha256": digest(content), "bytes": len(content)}
                       for name, content in {**files, "project.yaze": descriptor}.items()},
             "external_writable_owned_sources": {**external_writable,
                 **{"custom_object." + name: {"path": str((assets / name).resolve()),
                      "sha256": digest(content), "bytes": len(content)} for name, content in asset_bytes.items()}},
             "build_target": str(Path(__file__).resolve().parents[2] / "Roms/oos99904x.sfc")}
    def recheck_inputs():
        require(read_input(project) == original and digest(read_input(source_rom)) == report["input_sha256"],
                "Project or ROM changed during bundle publication")
        for name, expected in asset_bytes.items():
            require(read_input(assets / name) == expected, "Catalog asset changed during bundle publication")
        for path, expected in private_sources.items():
            require(read_input(path) == expected, "Writable sidecar changed during bundle publication")
    recheck_inputs()
    bundle.mkdir(mode=0o700)  # Exclusive reservation. Retain partial owned output on failure.
    (bundle / "custom_objects").mkdir(mode=0o700)
    (bundle / "backups").mkdir(mode=0o700)
    (bundle / "output").mkdir(mode=0o700)
    for name in ("assets", "patches", "sprite-source", "transfer"):
        (bundle / name).mkdir(mode=0o700)
    for name in private_bytes:
        (bundle / name).parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    files["bundle-receipt.json"] = (json.dumps(proof, indent=2) + "\n").encode()
    files["project.yaze"] = descriptor  # Descriptor publishes last; partial bundles are not admitted.
    for name, content in files.items():
        if name == "project.yaze":
            recheck_inputs()
        target = bundle / name
        publish_exclusive(target, content, 0o444 if name == "migration-receipt.json" else 0o600)
        readback(target, digest(content), "project bundle member", source_rom)
    recheck_inputs()
    return proof


def main(argv: Sequence[str] | None = None, protected_dirs: Sequence[Path] = PROTECTED_DIRS) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--verify-build-input", action="store_true")
    parser.add_argument("--verify-receipt", type=Path)
    parser.add_argument("--project", type=Path,
                        default=Path(os.environ["YAZE_PROJECT_FILE"]) if os.environ.get("YAZE_PROJECT_FILE") else None)
    parser.add_argument("--project-rom", type=Path,
                        default=Path(os.environ["YAZE_PROJECT_ROM"]) if os.environ.get("YAZE_PROJECT_ROM") else None)
    parser.add_argument("--native-save-receipt", type=Path,
                        default=Path(os.environ["YAZE_NATIVE_SAVE_RECEIPT"]) if os.environ.get("YAZE_NATIVE_SAVE_RECEIPT") else None)
    parser.add_argument("--native-save-context", type=Path,
                        default=Path(os.environ["YAZE_NATIVE_SAVE_CONTEXT"]) if os.environ.get("YAZE_NATIVE_SAVE_CONTEXT") else None)
    parser.add_argument("--project-output", type=Path,
                        help="Publish a NEW private .yazeproj bundle with migrated ROM and immutable receipt")
    parser.add_argument("--expected-project-sha256")
    args = parser.parse_args(argv)
    output = None
    report = None
    try:
        if args.verify_build_input or args.verify_receipt:
            require(not args.output and not args.receipt and not args.project_output,
                    "Build-input verification cannot publish files")
            data = read_input(args.rom)
            if args.expected_sha256:
                require(digest(data) == args.expected_sha256.lower(),
                        "Input SHA-256 differs from expected input")
            receipt = json_document(args.verify_receipt.read_bytes()) if args.verify_receipt else None
            print(json.dumps(verify_build_input(data, receipt, project=args.project, project_rom=args.project_rom,
                             migration_path=args.verify_receipt, native_receipt=args.native_save_receipt,
                             native_context=args.native_save_context), indent=2))
            return 0
        require(not args.project_output or not (args.output or args.receipt),
                "--project-output cannot be combined with --output or --receipt")
        require(bool(args.output) == bool(args.receipt), "--output and --receipt must be supplied together")
        require(args.expected_sha256 is not None, "Migration planning requires --expected-sha256")
        original = read_input(args.rom)
        result, report = plan_migration(original, args.expected_sha256)
        report["mode"] = "dry-run"
        if args.project_output:
            require(args.project is not None and args.expected_project_sha256 is not None,
                    "Project publication requires --project and --expected-project-sha256")
            require(args.project_output.suffix == ".yazeproj", "Project output must end in .yazeproj")
            output = args.project_output.resolve()
            proof = publish_project_bundle(args.project, args.rom, result, report, args.project_output,
                                           args.expected_project_sha256, protected_dirs)
            print(json.dumps(proof, indent=2))
            return 0
        if args.output:
            output = check_new_target(args.output, "output", protected_dirs, [args.rom.resolve()])
            receipt = check_new_target(args.receipt, "receipt", protected_dirs,
                                       [args.rom.resolve(), output])
            # Recheck the live input before publication; a changed source is not
            # permission to migrate a later human Save.
            require(digest(read_input(args.rom)) == report["input_sha256"], "Input changed during planning")
            publish_exclusive(output, result, 0o600)
            readback(output, report["output_sha256"], "migration output", args.rom)
            report.update(mode="published", output=str(output), receipt=str(receipt))
            encoded = (json.dumps(report, indent=2) + "\n").encode()
            publish_exclusive(receipt, encoded, 0o600)
            require(receipt.read_bytes() == encoded, "Receipt readback differs")
        print(json.dumps(report, indent=2))
        return 0
    except (PlanError, OSError, ValueError, configparser.Error) as error:
        # A published unique ROM is retained if later receipt publication fails.
        # Never delete a possible recovery artifact or an externally raced path.
        print(json.dumps({"status": "refused", "error": str(error),
                          "output": str(output) if output else None,
                          "output_exists": output.exists() if output else False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
