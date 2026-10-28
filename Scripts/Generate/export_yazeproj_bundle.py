#!/usr/bin/env python3
"""
Export a portable `.yazeproj` bundle for yaze (macOS + iOS).

This is the "seamless Mac <-> iPad" file format:
  - A `.yazeproj` is a directory package that can live in iCloud Drive.
  - It contains a ROM plus a filtered snapshot of the Oracle-of-Secrets repo.
  - yaze can open the bundle root directly.

Bundle layout (compatible with yaze core + iOS document browser):
  <Name>.yazeproj/
    project.yaze        # yaze project config (paths relative to bundle root)
    manifest.json       # iOS-friendly metadata (optional for core)
    rom                # ROM binary (no extension)
    project/           # Oracle-of-Secrets snapshot (hack_manifest + Docs/Dev/Planning)
    backups/           # per-bundle backups (optional)
    output/            # per-bundle build output (optional)
"""

from __future__ import annotations

import argparse
import ctypes
import datetime as _dt
import errno
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path, PureWindowsPath

from generate_hack_manifest import (
    MINECART_TRACK_SOURCE_CONTRACT,
    generate_manifest,
)
from palette_catalog_contract import validate_palette_catalog


PORTABLE_BUILD_SCRIPT = "project/Scripts/Build/build_rom.sh"
PORTABLE_HACK_MANIFEST = "project/Roms/hack_manifest.json"
PORTABLE_BUILD_COMMAND = (
    "OOS_BASE_ROM=rom OOS_BACKUP_ROOT=backups OOS_MANIFEST_ROOT=. "
    f"{PORTABLE_BUILD_SCRIPT} 168"
)
PORTABLE_BUILD_TARGET = "project/Roms/oos168x.sfc"
AUTHORING_BUILD_SCRIPT = "project/Scripts/Build/authoring_bundle_build.py"
AUTHORING_BUILD_COMMAND = f"python3 {AUTHORING_BUILD_SCRIPT} --project project.yaze"
# Fail-closed save settings shared by every Oracle project descriptor.
ORACLE_BASE_SAVE_CONTRACT = (
    ("feature_flags", "save_dungeon_maps", "false"),
    ("feature_flags", "save_dungeon_water_fill_zones", "false"),
    ("workspace", "autosave_enabled", "false"),
    ("workspace", "backup_on_save", "true"),
)
# Portable (iOS/bundle) projects: graphics sheet saving stays off (not qualified there).
ORACLE_SAVE_CONTRACT = ORACLE_BASE_SAVE_CONTRACT + (
    ("feature_flags", "save_graphics_sheet", "false"),
)
# Desktop (repo Oracle-of-Secrets.yaze): graphics sheet saving is the approved Mac editing
# workflow (2026-09-27), allowed only while the compression-reserved sheets stay protected.
ORACLE_DESKTOP_SAVE_CONTRACT = ORACLE_BASE_SAVE_CONTRACT + (
    ("feature_flags", "save_graphics_sheet", "true"),
)
DESKTOP_RESERVED_GRAPHICS_SHEETS = {"0x7B", "0x7C"}
PORTABLE_PROJECT_CONTRACT = (
    ("files", "rom_filename", "rom"),
    ("files", "rom_backup_folder", "backups"),
    ("files", "code_folder", "project"),
    ("files", "assets_folder", "project"),
    ("files", "patches_folder", "project"),
    ("files", "output_folder", "project/Roms"),
    (
        "files",
        "custom_objects_folder",
        "project/Dungeons/Objects/Data",
    ),
    ("files", "hack_manifest_file", PORTABLE_HACK_MANIFEST),
    ("rom", "role", "dev"),
    ("rom", "write_policy", "block"),
    ("build", "build_script", PORTABLE_BUILD_COMMAND),
    ("build", "output_folder", "project/Roms"),
    ("build", "git_repository", "project"),
    ("build", "build_target", PORTABLE_BUILD_TARGET),
    ("build", "asm_entry_point", "project/Oracle_main.asm"),
)


def find_repo_root() -> Path:
    p = Path(__file__).resolve().parent.parent
    if (p / "CLAUDE.md").exists():
        return p
    return Path.cwd().resolve()


def sha1_file(path: Path) -> str:
    h = hashlib.sha1()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def iso8601_now_utc() -> str:
    return _dt.datetime.now(tz=_dt.timezone.utc).isoformat(timespec="seconds")


def default_icloud_drive_root() -> Path | None:
    """
    Return the local filesystem path to iCloud Drive on macOS, if available.

    This is the canonical location for "iCloud Drive" contents:
      ~/Library/Mobile Documents/com~apple~CloudDocs
    """
    p = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    return p if p.exists() else None


def slugify_project_id(name: str) -> str:
    """
    Create a stable, filesystem-agnostic project_id from a human-readable name.
    """
    out = []
    prev_underscore = False
    for ch in name.lower():
        if ch.isalnum():
            out.append(ch)
            prev_underscore = False
            continue
        if not prev_underscore:
            out.append("_")
            prev_underscore = True
    s = "".join(out).strip("_")
    return s or "yaze_project"


def _parse_project_contract(
    content: str,
) -> tuple[list[str], list[tuple[str, str, str]]]:
    """Parse only the section/key/value behavior relevant to Yaze safety."""
    if "\r" in content:
        raise ValueError("project.yaze must use LF-only line endings")

    current_section = ""
    sections: list[str] = []
    assignments: list[tuple[str, str, str]] = []
    for line in content.split("\n"):
        if not line or line[0] == "#":
            continue
        if line[0] == "[" and line[-1] == "]":
            current_section = line[1:-1]
            sections.append(current_section)
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip(" \t")
        value = value.strip(" \t")
        if key:
            assignments.append((current_section, key, value))
    return sections, assignments


def _require_project_assignment(
    assignments: list[tuple[str, str, str]],
    expected_section: str,
    key: str,
    expected_value: str,
) -> None:
    matches = [
        entry
        for entry in assignments
        if entry[0] == expected_section and entry[1] == key
    ]
    if len(matches) != 1:
        raise ValueError(
            f"project.yaze must contain exactly one {key} assignment"
        )
    _, _, value = matches[0]
    if value != expected_value:
        raise ValueError(
            f"project.yaze {key} must equal {expected_value}"
        )


def validate_oracle_project_contract(
    content: str, contract: tuple = ORACLE_SAVE_CONTRACT
) -> None:
    """Require Oracle's fail-closed save and workspace settings exactly once.

    The default is the portable/bundle contract. The desktop repo descriptor uses
    validate_desktop_project_contract().
    """
    sections, assignments = _parse_project_contract(content)
    for section in ("feature_flags", "workspace"):
        if sections.count(section) != 1:
            raise ValueError(
                f"project.yaze must contain exactly one [{section}] section"
            )
    for section, key, value in contract:
        _require_project_assignment(assignments, section, key, value)


def validate_desktop_project_contract(content: str) -> None:
    """Desktop repo descriptor: shared fail-closed settings, graphics saving on, reserved sheets kept."""
    validate_oracle_project_contract(content, ORACLE_DESKTOP_SAVE_CONTRACT)
    _, assignments = _parse_project_contract(content)
    reserved = [
        value
        for section, key, value in assignments
        if section == "graphics_sheets" and key == "reserved_sheets"
    ]
    if len(reserved) != 1:
        raise ValueError(
            "desktop project.yaze must declare [graphics_sheets] reserved_sheets exactly once"
        )
    listed = {item.strip().upper().replace("0X", "0x") for item in reserved[0].split(",") if item.strip()}
    missing = DESKTOP_RESERVED_GRAPHICS_SHEETS - listed
    if missing:
        raise ValueError(
            "desktop project.yaze reserved_sheets must include " + ",".join(sorted(missing))
        )


def validate_portable_project_contract(
    content: str,
    expected_rom_sha1: str,
    save_contract: tuple = ORACLE_SAVE_CONTRACT,
    build_command: str = PORTABLE_BUILD_COMMAND,
    build_target: str = PORTABLE_BUILD_TARGET,
) -> None:
    """Require the portable descriptor's paths and build contract."""
    validate_oracle_project_contract(content, save_contract)
    sections, assignments = _parse_project_contract(content)
    for section in ("project", "files", "rom", "build"):
        if sections.count(section) != 1:
            raise ValueError(
                f"project.yaze must contain exactly one [{section}] section"
            )
    for section, key, value in PORTABLE_PROJECT_CONTRACT:
        if (section, key) == ("build", "build_script"):
            value = build_command
        elif (section, key) == ("build", "build_target"):
            value = build_target
        _require_project_assignment(assignments, section, key, value)
    _require_project_assignment(
        assignments,
        "rom",
        "expected_hash",
        expected_rom_sha1,
    )


def _resolve_bundle_member(
    bundle_root: Path,
    raw_path: str,
    description: str,
    *,
    must_exist: bool,
) -> Path:
    """Resolve a path inside the bundle on POSIX or Windows hosts."""
    if (
        not raw_path
        or Path(raw_path).is_absolute()
        or PureWindowsPath(raw_path).is_absolute()
        or raw_path.startswith("\\\\")
    ):
        raise ValueError(
            f"{description} must be a relative bundle-root path: {raw_path}"
        )
    resolved_root = bundle_root.resolve()
    resolved = (resolved_root / raw_path).resolve()
    if resolved == resolved_root or not resolved.is_relative_to(resolved_root):
        raise ValueError(
            f"{description} escapes the portable bundle: {raw_path}"
        )
    if must_exist and not resolved.is_file():
        raise FileNotFoundError(f"Bundle is missing {description}: {resolved}")
    return resolved


def _iter_manifest_source_locations(manifest: dict):
    """Yield ASM path:line provenance from the manifest's typed sections.

    Other `source` fields have different schemas. In particular, allocation
    ledger claim bindings contain source-set IDs such as
    `shared:Sprites/Objects/minecart.asm`, which are not bundle paths.
    """
    def records(section: str, key: str):
        metadata = manifest.get(section)
        items = metadata.get(key) if isinstance(metadata, dict) else None
        if not isinstance(items, list):
            raise ValueError(f"hack_manifest.json {section}.{key} must be a list")
        return items

    def source(record: object, description: str) -> str:
        value = record.get("source") if isinstance(record, dict) else None
        if not isinstance(value, str):
            raise ValueError(
                f"hack_manifest.json {description}.source must be a path:line string"
            )
        return value

    for bank in records("owned_banks", "banks"):
        regions = bank.get("regions") if isinstance(bank, dict) else None
        if not isinstance(regions, list):
            raise ValueError(
                "hack_manifest.json owned_banks.banks[].regions must be a list"
            )
        for region in regions:
            yield source(region, "owned_banks.banks[].regions[]")
    for tag in records("room_tags", "tags"):
        yield source(tag, "room_tags.tags[]")
    for flag in records("feature_flags", "flags"):
        yield source(flag, "feature_flags.flags[]")


def validate_portable_manifest_contract(
    bundle_root: Path,
    manifest: dict,
) -> None:
    """Validate path-bearing manifest fields against one bundle-root namespace."""
    pipeline = manifest.get("build_pipeline")
    if not isinstance(pipeline, dict):
        raise ValueError("hack_manifest.json must contain build_pipeline")
    expected_pipeline = {
        "dev_rom": "rom",
        "patched_rom": "project/Roms/oos168x.sfc",
        "entry_point": "project/Oracle_main.asm",
        "build_script": PORTABLE_BUILD_SCRIPT,
    }
    for key, expected in expected_pipeline.items():
        if pipeline.get(key) != expected:
            raise ValueError(
                f"hack_manifest.json build_pipeline.{key} must equal "
                f"{expected}"
            )
        _resolve_bundle_member(
            bundle_root,
            expected,
            f"build_pipeline.{key}",
            must_exist=key != "patched_rom",
        )

    rom = manifest.get("rom")
    if not isinstance(rom, dict):
        raise ValueError("hack_manifest.json must contain object field rom")
    if "path" in rom and rom["path"] != expected_pipeline["patched_rom"]:
        raise ValueError(
            "hack_manifest.json rom.path must match build_pipeline.patched_rom"
        )

    messages = manifest.get("messages")
    message_source = (
        messages.get("source") if isinstance(messages, dict) else None
    )
    expected_messages = {
        "canonical_bundle_path": (
            "project/Data/dialogue/expanded_messages.json"
        ),
        "generated_asm_include_path": (
            "project/Core/Generated/expanded_messages.asm"
        ),
    }
    if not isinstance(message_source, dict):
        raise ValueError("hack_manifest.json must contain messages.source")
    for key, expected in expected_messages.items():
        if message_source.get(key) != expected:
            raise ValueError(
                f"hack_manifest.json messages.source.{key} must equal "
                f"{expected}"
            )
        _resolve_bundle_member(
            bundle_root,
            expected,
            f"messages.source.{key}",
            must_exist=True,
        )

    expected_source_files = (
        ("feature_flags", "config_file", "project/Config/feature_flags.asm"),
        ("sram", "source_file", "project/Core/sram.asm"),
    )
    for section, key, expected in expected_source_files:
        metadata = manifest.get(section)
        if not isinstance(metadata, dict) or metadata.get(key) != expected:
            raise ValueError(
                f"hack_manifest.json {section}.{key} must equal {expected}"
            )
        _resolve_bundle_member(
            bundle_root,
            expected,
            f"{section}.{key}",
            must_exist=True,
        )

    minecart_tracks = manifest.get("minecart_tracks")
    minecart_source = (
        minecart_tracks.get("source")
        if isinstance(minecart_tracks, dict)
        else None
    )
    expected_minecart = {
        **MINECART_TRACK_SOURCE_CONTRACT,
        "path": "project/Sprites/Objects/data/minecart_tracks.asm",
    }
    if minecart_source != expected_minecart:
        raise ValueError(
            "hack_manifest.json minecart_tracks.source does not match the "
            "portable source contract"
        )
    _resolve_bundle_member(
        bundle_root,
        expected_minecart["path"],
        "minecart_tracks.source.path",
        must_exist=True,
    )

    for source_location in _iter_manifest_source_locations(manifest):
        source_path, separator, line = source_location.rpartition(":")
        if not separator or not line.isdigit():
            raise ValueError(
                f"Invalid manifest source location: {source_location}"
            )
        if not source_path.startswith("project/"):
            raise ValueError(
                "Manifest source locations must resolve from the bundle root: "
                f"{source_location}"
            )
        _resolve_bundle_member(
            bundle_root,
            source_path,
            "manifest source location",
            must_exist=True,
        )


def should_skip(rel: Path) -> bool:
    """
    Decide whether to exclude a path from the bundled project snapshot.
    `rel` is a path relative to the Oracle-of-Secrets repo root.
    """
    parts = set(rel.parts)

    # Repo-internal state and caches (not useful on iOS; often huge/noisy).
    if parts & {
        ".git",
        ".agent",
        ".cache",
        ".claude",
        ".context",
        ".cursor",
        ".genkit",
        ".gemini",
        ".pytest_cache",
        ".vscode",
        "build",
        "evaluations",
        "scratchpad",
    }:
        return True

    # ROM binaries and archives: bundle has its own `rom` file.
    if rel.parts and rel.parts[0] == "Roms":
        return True

    # Visual diffs/screenshots are large and not needed for editing.
    if rel.parts and rel.parts[0] == "tests":
        if len(rel.parts) >= 2 and rel.parts[1] in {
            "screenshots",
            "baselines",
            "baseline",
            "current",
            "diffs",
        }:
            return True

    # OS noise
    if rel.name in {".DS_Store", "Thumbs.db"}:
        return True

    return False


def copy_repo_snapshot(src_root: Path, dst_root: Path, *, reject_symlinks=False) -> None:
    if reject_symlinks and dst_root.resolve().is_relative_to(src_root.resolve()):
        if not should_skip(dst_root.resolve().relative_to(src_root.resolve())):
            raise ValueError("Snapshot output must not be inside captured source")
    dst_root.mkdir(parents=True, exist_ok=True)

    for dirpath, dirnames, filenames in os.walk(src_root):
        abs_dir = Path(dirpath)
        rel_dir = abs_dir.relative_to(src_root)

        # Prune excluded directories early.
        keep_dirnames: list[str] = []
        for d in dirnames:
            rel = rel_dir / d
            if not should_skip(rel):
                if reject_symlinks and (src_root / rel).is_symlink():
                    raise ValueError(f"Snapshot directory is a symlink: {rel}")
                keep_dirnames.append(d)
        dirnames[:] = keep_dirnames

        # Ensure destination directory exists.
        (dst_root / rel_dir).mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            rel = rel_dir / filename
            if should_skip(rel):
                continue
            src_file = abs_dir / filename
            if reject_symlinks and src_file.is_symlink():
                raise ValueError(f"Snapshot file is a symlink: {rel}")
            dst_file = dst_root / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


AUTHORING_RECEIPT = "authoring-dependencies.json"
PROJECT_FILE_DEPENDENCIES = (
    "labels_filename",
    "symbols_filename",
    "dungeon_tile_patterns",
    "custom_collision_json",
    "cutscene_shots",
    "terrain_catalog_file",
    "lyra_terrain_file",
    "palette_catalog_file",
    "sprite_catalog_file",
    # Preserve bytes and supported references, never rewrite internal native
    # Save identities or turn an exported descriptor into the original project.
    "lyra_build_request_file",
    "native_save_receipt_file",
    "native_save_producer_file",
    "native_save_transfer_proof_file",
)


def _source_path(raw: str, parent: Path) -> Path:
    if not raw or "\\" in raw or "\0" in raw or ".." in Path(raw).parts:
        raise ValueError(f"Invalid dependency path: {raw!r}")
    if PureWindowsPath(raw).drive:
        raise ValueError(f"Foreign dependency path: {raw!r}")
    path = Path(raw)
    if not path.is_absolute():
        path = parent / path
    for part in (path, *path.parents):
        if part.is_symlink():
            raise ValueError(f"Dependency is a symlink: {part}")
    if not path.exists():
        raise FileNotFoundError(f"Missing dependency: {path}")
    return path


def _rewrite_project(content: str, updates: dict[tuple[str, str], str]) -> str:
    """Change declared bindings without rewriting labels, comments or settings."""
    remaining = dict(updates)
    output = []
    section = ""

    def finish_section():
        for pair in list(remaining):
            if pair[0] == section:
                output.append(f"{pair[1]}={remaining.pop(pair)}")

    for line in content.splitlines():
        if line.startswith("[") and line.endswith("]"):
            finish_section()
            section = line[1:-1]
        elif "=" in line and not line.startswith("#"):
            key = line.split("=", 1)[0].strip()
            pair = (section, key)
            if pair in remaining:
                line = f"{key}={remaining.pop(pair)}"
        output.append(line)
    finish_section()
    for section in dict.fromkeys(pair[0] for pair in remaining):
        output.extend(["", f"[{section}]"])
        finish_section()
    return "\n".join(output) + "\n"


def write_authoring_project(
    bundle_root: Path,
    source_project: Path,
    rom_sha1: str,
    *,
    lyra_terrain: Path | None = None,
    graphics_preview: Path | None = None,
    desktop: bool = False,
    rom_source: Path | None = None,
) -> None:
    """Capture explicit project dependencies; never modify an input resource."""
    source_project = _source_path(str(source_project), Path.cwd())
    project_bytes = source_project.read_bytes()
    content = project_bytes.decode("utf-8")
    _, assignments = _parse_project_contract(content)
    values = {}
    for section, key, value in assignments:
        pair = (section, key)
        if pair in values:
            raise ValueError(f"Duplicate project assignment: {section}.{key}")
        values[pair] = value
    if not values.get(("project", "project_id")):
        raise ValueError("Source project must declare its project_id")
    files = {}
    bindings = {}
    sources = {}

    def copy_file(source: Path, relative: str):
        source = _source_path(str(source), source_project.parent)
        if not source.is_file():
            raise ValueError(f"Dependency is not a regular file: {source}")
        target = _resolve_bundle_member(
            bundle_root, relative, "dependency", must_exist=False
        )
        data = source.read_bytes()
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        if source.read_bytes() != data or target.read_bytes() != data:
            raise ValueError(f"Dependency changed during capture: {source}")
        files[relative] = {
            "size": len(data),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
        sources[source] = files[relative]["sha256"]

    def copy_directory(source: Path, relative: str):
        source = _source_path(str(source), source_project.parent)
        if not source.is_dir():
            raise ValueError(f"Dependency is not a directory: {source}")
        if bundle_root.resolve().is_relative_to(source.resolve()):
            raise ValueError("Bundle output is inside a dependency directory")
        destination = bundle_root / relative
        if destination.exists():
            shutil.rmtree(destination)
        destination.mkdir(parents=True, exist_ok=True)
        for directory, dirs, names in os.walk(source, followlinks=False):
            for name in dirs + names:
                child = Path(directory) / name
                _source_path(str(child), source)
                if child.is_file():
                    copy_file(
                        child, relative + "/" + child.relative_to(source).as_posix()
                    )

    updates = {
        (section, key): value for section, key, value in PORTABLE_PROJECT_CONTRACT
    }
    updates[("build", "build_script")] = AUTHORING_BUILD_COMMAND
    copy_file(Path(__file__).resolve().parents[1] / "Build" / "authoring_bundle_build.py",
              AUTHORING_BUILD_SCRIPT)
    updates[("rom", "expected_hash")] = rom_sha1
    overrides = {"lyra_terrain_file": lyra_terrain}
    for key in PROJECT_FILE_DEPENDENCIES:
        raw = (
            str(overrides[key])
            if overrides.get(key) is not None
            else values.get(("files", key), "")
        )
        if raw:
            source = _source_path(raw, source_project.parent)
            relative = f"assets/project/{key}/{source.name}"
            copy_file(source, relative)
            updates[("files", key)] = relative
            bindings[f"files.{key}"] = relative
    for key, destination in (
        ("custom_objects_folder", "project/Dungeons/Objects/Data"),
        ("sprite_source_root", "assets/sprite-source"),
    ):
        raw = values.get(("files", key), "")
        if raw:
            copy_directory(_source_path(raw, source_project.parent), destination)
            updates[("files", key)] = destination
            bindings[f"files.{key}"] = destination

    raw_preview = (
        str(graphics_preview)
        if graphics_preview is not None
        else values.get(("files", "overworld_graphics_preview"), "")
    )
    if raw_preview:
        source = _source_path(raw_preview, source_project.parent)
        directory = "assets/graphics-preview"
        copy_file(source, directory + "/" + source.name)
        document = json.loads(
            (bundle_root / directory / source.name).read_text(encoding="utf-8")
        )

        def copy_catalog_resources(value):
            if isinstance(value, dict):
                if "path" in value:
                    raw = value["path"]
                    if (
                        not isinstance(raw, str)
                        or Path(raw).is_absolute()
                        or PureWindowsPath(raw).root
                    ):
                        raise ValueError("Graphics catalog resource must be relative")
                    resource = _source_path(raw, source.parent)
                    if not resource.resolve().is_relative_to(source.parent.resolve()):
                        raise ValueError(
                            "Graphics catalog resource escapes its directory"
                        )
                    copy_file(resource, directory + "/" + raw)
                    captured = files[directory + "/" + raw]
                    if "sha256" in value and value["sha256"] != captured["sha256"]:
                        raise ValueError(
                            f"Graphics catalog resource hash mismatch: {raw}"
                        )
                    if "byte_count" in value and (
                        type(value["byte_count"]) is not int
                        or value["byte_count"] != captured["size"]
                    ):
                        raise ValueError(
                            f"Graphics catalog resource size mismatch: {raw}"
                        )
                for child in value.values():
                    copy_catalog_resources(child)
            elif isinstance(value, list):
                for child in value:
                    copy_catalog_resources(child)

        copy_catalog_resources(document)
        relative = directory + "/" + source.name
        updates[("files", "overworld_graphics_preview")] = relative
        bindings["files.overworld_graphics_preview"] = relative

    raw_manifest = values.get(("files", "hack_manifest_file"), "")
    if raw_manifest:
        manifest = json.loads(
            _source_path(raw_manifest, source_project.parent).read_text()
        )
        tracks = manifest.get("minecart_tracks", {}).get("source", {})
        if tracks.get("path"):
            copy_file(
                _source_path(tracks["path"], source_project.parent),
                "project/Sprites/Objects/data/minecart_tracks.asm",
            )
    for section, key in (
        ("agent_settings", "custom_system_prompt"),
        ("agent_settings", "builder_blueprint_path"),
        ("atlas", "symbols"),
        ("zscream_compatibility", "original_project_file"),
    ):
        raw = values.get((section, key), "")
        if raw:
            source = _source_path(raw, source_project.parent)
            relative = f"assets/project/{key}/{source.name}"
            copy_file(source, relative)
            updates[(section, key)] = relative
            bindings[f"{section}.{key}"] = relative
    annotations = []
    for index, raw in enumerate(
        filter(None, values.get(("atlas", "annotations"), "").split(","))
    ):
        source = _source_path(raw.strip(), source_project.parent)
        relative = f"assets/atlas/{index}-{source.name}"
        copy_file(source, relative)
        annotations.append(relative)
    if ("atlas", "annotations") in values:
        updates[("atlas", "annotations")] = ",".join(annotations)
    if any(section == "atlas" for section, key in values):
        updates[("atlas", "export_folder")] = "output/atlas"
    # Sprite asset JSON contains further independently rooted source bindings;
    # refuse rather than preserving an unreviewed external publisher target.
    if any(
        section == "sprite_assets" and value for (section, key), value in values.items()
    ):
        raise ValueError(
            "Sprite asset bindings need an explicit bundle dependency adapter"
        )
    additional = []
    for index, raw in enumerate(
        filter(None, values.get(("files", "additional_roms"), "").split(","))
    ):
        source = _source_path(raw.strip(), source_project.parent)
        relative = f"assets/additional-roms/{index}-{source.name}"
        copy_file(source, relative)
        additional.append(relative)
    updates[("files", "additional_roms")] = ",".join(additional)
    updates[("workspace", "recent_files")] = ""
    updates[("build", "asm_sources")] = ""
    updates[("build", "track_changes")] = "false"
    updates[("music", "storage_key")] = (
        values[("project", "project_id")] + "_bundle_music"
    )
    # Planning is a declared live reference, outside build provenance: keep
    # the plan in place so its own lifecycle never invalidates the export.
    raw_planning = values.get(("planning", "file"), "")
    if raw_planning:
        planning = _source_path(raw_planning, source_project.parent).resolve()
        aliases = {path.resolve() for path in sources}
        aliases.add(source_project.resolve())
        if rom_source is not None:
            aliases.add(rom_source.resolve())
        if planning in aliases or planning.is_relative_to(bundle_root.resolve()):
            raise ValueError(
                f"planning.file {planning} is also a ROM/tool/build input; a live "
                "Planning reference must be a separate file"
            )
        updates[("planning", "file")] = str(planning)
    result = _rewrite_project(content, updates)
    contract = ORACLE_DESKTOP_SAVE_CONTRACT if desktop else ORACLE_SAVE_CONTRACT
    validate_portable_project_contract(result, rom_sha1, contract,
                                       AUTHORING_BUILD_COMMAND)
    if desktop:
        validate_desktop_project_contract(result)
    palette = updates.get(("files", "palette_catalog_file"))
    if palette:
        validate_palette_catalog(bundle_root / palette)
    if source_project.read_bytes() != project_bytes:
        raise ValueError("Source project changed during capture")
    for path, expected in sources.items():
        _source_path(str(path), source_project.parent)
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Dependency changed during capture: {path}")
    (bundle_root / "project.yaze").write_text(result, encoding="utf-8")
    receipt = {
        "schema_version": 1,
        "mode": "desktop" if desktop else "portable",
        "source_project_sha256": hashlib.sha256(project_bytes).hexdigest(),
        "project_sha256": hashlib.sha256(result.encode()).hexdigest(),
        "bindings": bindings,
        "files": files,
    }
    (bundle_root / AUTHORING_RECEIPT).write_text(
        json.dumps(receipt, indent=2, sort_keys=True) + "\n"
    )


# The export receipt is immutable provenance. Only these export bindings may
# change after export, and only as bytes bound by a genuine yaze Save receipt
# (role names from yaze ProjectSaveSources).
NATIVE_SAVE_RECEIPT = "project.yaze.native-save.json"
NATIVE_SAVE_EDITABLE_ROLES = {
    "files.lyra_terrain_file": "sidecar",
    "files.custom_collision_json": "dependency.custom_collision_json",
}
NATIVE_SAVE_MAX_BYTES = 1024 * 1024
NATIVE_SAVE_MAX_ARTIFACTS = 256
CAPTURED_PATH_BINDINGS = (
    *(f"files.{key}" for key in PROJECT_FILE_DEPENDENCIES),
    "files.custom_objects_folder",
    "files.sprite_source_root",
    "files.overworld_graphics_preview",
    "files.hack_manifest_file",
    "agent_settings.custom_system_prompt",
    "agent_settings.builder_blueprint_path",
    "atlas.symbols",
    "zscream_compatibility.original_project_file",
)
CAPTURED_PATH_LIST_BINDINGS = ("files.additional_roms", "atlas.annotations")
NATIVE_SAVE_MANDATORY_ROLES = ("project", "rom", "producer")
# Bundle members the build or the Save contract reads; a live Planning
# reference may not name one of them under another role.
BUILD_OWNED_MEMBERS = ("rom", "project.yaze", "manifest.json",
                       AUTHORING_RECEIPT, NATIVE_SAVE_RECEIPT)
BUILD_OWNED_TREES = ("project", "tools", "assets")
# Hack manifest fields derived from the editable dev ROM (bundle `rom`).
DEV_ROM_MANIFEST_FIELDS = ("dungeon_stream_regions", "editor_managed_regions")


def _is_sha256(value) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(c in "0123456789abcdef" for c in value)
    )


def _is_save_role(value) -> bool:
    allowed = "abcdefghijklmnopqrstuvwxyz0123456789._:-"
    return (
        isinstance(value, str)
        and 0 < len(value) <= 128
        and "a" <= value[0] <= "z"
        and all(c in allowed for c in value)
    )


def _is_count(value) -> bool:
    return type(value) is int and value >= 0


def _load_native_save_receipt(bundle_root: Path) -> dict | None:
    """Read yaze's adjacent yaze.native_save.v1 receipt without trusting it."""
    path = bundle_root / NATIVE_SAVE_RECEIPT
    if not path.exists() and not path.is_symlink():
        return None

    def invalid(reason: str) -> ValueError:
        return ValueError(f"Invalid native-save receipt {NATIVE_SAVE_RECEIPT}: {reason}")

    if path.is_symlink() or not path.is_file():
        raise invalid("not a regular file")
    data = path.read_bytes()
    if len(data) > NATIVE_SAVE_MAX_BYTES:
        raise invalid("exceeds size limit")
    try:
        receipt = json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise invalid("not JSON") from exc
    fields = {
        "kind", "generation", "operation_id", "operation", "receipt_path",
        "bindings_complete", "binding_errors", "artifacts",
    }
    if not isinstance(receipt, dict) or set(receipt) != fields:
        raise invalid("unexpected fields")
    if receipt["kind"] != "yaze.native_save.v1":
        raise invalid("kind is not yaze.native_save.v1")
    if not _is_count(receipt["generation"]) or receipt["generation"] == 0:
        raise invalid("generation must be a positive integer")
    operation_id = receipt["operation_id"]
    if (
        not isinstance(operation_id, str)
        or not 0 < len(operation_id) <= 128
        or any(not 0x20 <= ord(c) <= 0x7E for c in operation_id)
    ):
        raise invalid("operation_id")
    if receipt["operation"] not in ("save", "save_as"):
        raise invalid("operation is not a native Save")
    if receipt["receipt_path"] != str(path.resolve()):
        raise invalid("receipt_path names another location; Save again here")
    errors = receipt["binding_errors"]
    if (
        not isinstance(errors, list)
        or len(errors) > NATIVE_SAVE_MAX_ARTIFACTS
        or any(not isinstance(e, str) or not e or len(e) > 1024 for e in errors)
    ):
        raise invalid("binding_errors")
    if receipt["bindings_complete"] is not (not errors):
        raise invalid("bindings_complete disagrees with binding_errors")
    artifacts = receipt["artifacts"]
    if not isinstance(artifacts, list) or len(artifacts) > NATIVE_SAVE_MAX_ARTIFACTS:
        raise invalid("artifacts")
    roles = {}
    for artifact in artifacts:
        if (
            not isinstance(artifact, dict)
            or set(artifact) != {"role", "path", "sha256", "bytes"}
            or not _is_save_role(artifact["role"])
            or artifact["role"] in roles
            or not isinstance(artifact["path"], str)
            or not Path(artifact["path"]).is_absolute()
            or not _is_sha256(artifact["sha256"])
            or not _is_count(artifact["bytes"])
        ):
            raise invalid("artifact binding")
        roles[artifact["role"]] = artifact
    if "rom" not in roles or "producer" not in roles:
        raise invalid("rom and producer roles are required")
    if "dependency.planning" in roles:
        raise invalid(
            "it binds dependency.planning, but Planning is a live reference "
            "outside Save provenance; complete a new native Save with the "
            "bundle's pinned yaze producer"
        )
    receipt["roles"] = roles
    return receipt


def _input_alias(
    bundle_root: Path, receipt: dict, native: dict | None, path: Path
) -> str | None:
    """Name the ROM, tool, build or Save input that `path` resolves to."""
    root = bundle_root.resolve()
    inputs = {(root / member).resolve(): member for member in BUILD_OWNED_MEMBERS}
    inputs.update({(root / rel).resolve(): rel for rel in receipt["files"]})
    inputs.update({(root / rel).resolve(): key
                   for key, rel in receipt["bindings"].items()})
    if native is not None:
        inputs.update({Path(artifact["path"]).resolve(): f"native Save role {role}"
                       for role, artifact in native["roles"].items()})
    resolved = path.resolve()
    alias = inputs.get(resolved) or next(
        (tree for tree in BUILD_OWNED_TREES
         if resolved.is_relative_to((root / tree).resolve())), None)
    if alias is None and resolved.exists():
        alias = next((name for existing, name in inputs.items()
                      if existing.exists() and os.path.samefile(existing, resolved)),
                     None)
    return alias


def _require_live_planning(
    bundle_root: Path, receipt: dict, values: dict, native: dict | None
) -> None:
    """Refuse a live Planning reference that is also a build or Save input."""
    raw = values.get("planning.file", "")
    if not raw:
        return
    path = Path(raw)
    alias = _input_alias(bundle_root, receipt, native,
                         path if path.is_absolute() else bundle_root / path)
    if alias is not None:
        raise ValueError(
            f"planning.file {raw} is also a ROM/tool/build input ({alias}); a "
            "live Planning reference must stay outside build provenance"
        )


def _require_saved_state(
    bundle_root: Path,
    receipt: dict,
    values: dict,
    changed_files: list[str],
    rom_identity: tuple[str, str] | None = None,
) -> None:
    """Accept post-export differences only when a genuine Save binds them.

    rom_identity is (export romChecksum, current sha1) when the editable
    bundle `rom` differs from its export identity.
    """
    editable = {receipt["bindings"].get(key): role
                for key, role in NATIVE_SAVE_EDITABLE_ROLES.items()}
    editable.pop(None, None)
    for relative in changed_files:
        if relative not in editable:
            raise ValueError(
                f"Authoring dependency hash mismatch: {relative} is immutable "
                "export provenance; restore it or re-export the bundle"
            )
    native = _load_native_save_receipt(bundle_root)
    if native is None:
        if rom_identity is not None:
            raise ValueError(
                f"manifest.json romChecksum mismatch: {rom_identity[0]} != "
                f"{rom_identity[1]}; no {NATIVE_SAVE_RECEIPT} from a yaze Save "
                "binds the edited rom; refusing an external or unsaved edit"
            )
        changed = changed_files[0] if changed_files else "project.yaze"
        raise ValueError(
            f"Authoring dependency hash mismatch: {changed} changed "
            f"and no {NATIVE_SAVE_RECEIPT} from a yaze Save binds it; refusing "
            "an external or unsaved edit"
        )
    roles = native["roles"]

    def require_bound(relative: str, role: str) -> None:
        artifact = roles.get(role)
        path = bundle_root / relative
        data = path.read_bytes()
        if (
            artifact is None
            or artifact["path"] != str(path.resolve())
            or artifact["bytes"] != len(data)
            or artifact["sha256"] != hashlib.sha256(data).hexdigest()
        ):
            raise ValueError(
                f"{NATIVE_SAVE_RECEIPT} does not bind current {relative} "
                f"(role {role}); it changed outside a genuine yaze Save"
            )

    require_bound("project.yaze", "project")
    # The editable input `rom`, never the derived build ROM under project/Roms.
    require_bound("rom", "rom")
    checked_roles = {*NATIVE_SAVE_MANDATORY_ROLES,
                     *(editable[r] for r in changed_files)}
    for relative in changed_files:
        require_bound(relative, editable[relative])
    for error in native["binding_errors"]:
        prefix = error.split(": ", 1)[0] if ": " in error else ""
        if not _is_save_role(prefix) or prefix in checked_roles:
            raise ValueError(
                f"{NATIVE_SAVE_RECEIPT} reports an incomplete Save binding "
                f"affecting {', '.join(sorted(checked_roles))}: {error}"
            )

    pin = "tools/producer.json"
    if pin not in receipt["files"]:
        raise ValueError(
            f"Bundle export provenance pins no tools producer ({pin}); "
            "a native Save cannot be qualified"
        )
    pinned = json.loads((bundle_root / pin).read_text(encoding="utf-8"))
    expected = pinned.get("app_executable_sha256")
    if not _is_sha256(expected) or roles["producer"]["sha256"] != expected:
        raise ValueError(
            f"{NATIVE_SAVE_RECEIPT} producer {roles['producer']['sha256']} is "
            f"not the bundle's pinned tools app {expected}"
        )

    for key in CAPTURED_PATH_BINDINGS + CAPTURED_PATH_LIST_BINDINGS:
        raw = values.get(key, "")
        entries = raw.split(",") if key in CAPTURED_PATH_LIST_BINDINGS else [raw]
        for entry in filter(None, (item.strip() for item in entries)):
            try:
                _resolve_bundle_member(
                    bundle_root, entry, f"saved binding {key}", must_exist=False
                )
            except ValueError as exc:
                raise ValueError(
                    f"Saved project.yaze binds {key} outside the bundle "
                    f"({entry}); re-export to capture it"
                ) from exc
    _require_live_planning(bundle_root, receipt, values, native)


def verify_authoring_dependencies(
    bundle_root: Path, rom_identity: tuple[str, str] | None = None
) -> dict | None:
    receipt_path = bundle_root / AUTHORING_RECEIPT
    if not receipt_path.exists():
        return None
    receipt = json.loads(receipt_path.read_text())
    if receipt.get("schema_version") != 1 or receipt.get("mode") not in (
        "desktop",
        "portable",
    ):
        raise ValueError("Invalid authoring dependency receipt")
    content = (bundle_root / "project.yaze").read_bytes()
    descriptor_changed = (
        hashlib.sha256(content).hexdigest() != receipt["project_sha256"]
    )
    if descriptor_changed and _load_native_save_receipt(bundle_root) is None:
        raise ValueError(
            "Authoring project descriptor differs from captured input and "
            f"no {NATIVE_SAVE_RECEIPT} from a yaze Save binds it; refusing "
            "an external or unsaved edit"
        )
    _, assignments = _parse_project_contract(content.decode("utf-8"))
    values = {f"{section}.{key}": value for section, key, value in assignments}
    for key, expected in receipt["bindings"].items():
        if values.get(key) != expected:
            raise ValueError(f"Authoring dependency binding changed: {key}")
        _resolve_bundle_member(
            bundle_root, expected, "authoring binding", must_exist=False
        )
        _source_path(str(bundle_root / expected), bundle_root)
    changed_files = []
    for relative, expected in receipt["files"].items():
        path = _resolve_bundle_member(
            bundle_root, relative, "authoring dependency", must_exist=True
        )
        _source_path(str(bundle_root / relative), bundle_root)
        data = path.read_bytes()
        if (
            len(data) != expected["size"]
            or hashlib.sha256(data).hexdigest() != expected["sha256"]
        ):
            changed_files.append(relative)
    _require_live_planning(bundle_root, receipt, values, None)
    if descriptor_changed or changed_files or rom_identity is not None:
        _require_saved_state(bundle_root, receipt, values, changed_files,
                             rom_identity)
    return receipt


def _saved_build_target(
    bundle_root: Path, authoring: dict | None, content: bytes
) -> str:
    """Return the build_target the portable contract pins for this descriptor.

    build_target is output metadata: a genuine native Save may name a new
    output, never an input. Every other descriptor pin stays exact; the build
    backend enforces its own stricter fresh-target rules.
    """
    if authoring is None or (
        hashlib.sha256(content).hexdigest() == authoring["project_sha256"]
    ):
        return PORTABLE_BUILD_TARGET
    _, assignments = _parse_project_contract(content.decode("utf-8"))
    targets = [value for section, key, value in assignments
               if (section, key) == ("build", "build_target")]
    planning = [value for section, key, value in assignments
                if (section, key) == ("planning", "file") and value]
    if len(targets) != 1 or targets[0] == PORTABLE_BUILD_TARGET:
        return PORTABLE_BUILD_TARGET
    raw = targets[0]
    native = _load_native_save_receipt(bundle_root)
    project = (native or {}).get("roles", {}).get("project")
    if (
        project is None
        or project["path"] != str((bundle_root / "project.yaze").resolve())
        or project["sha256"] != hashlib.sha256(content).hexdigest()
        or not native["bindings_complete"]
    ):
        raise ValueError(
            f"project.yaze build_target {raw} is not bound by a complete "
            f"{NATIVE_SAVE_RECEIPT} from a yaze Save; refusing an external "
            "or unsaved output change"
        )
    if ("\\" in raw or "\0" in raw or ".." in Path(raw).parts
            or PureWindowsPath(raw).drive):
        raise ValueError(f"Invalid saved build_target: {raw!r}")
    target = Path(raw)
    target = target if target.is_absolute() else bundle_root / target
    alias = _input_alias(bundle_root, authoring, native, target)
    for raw_plan in planning:
        plan = Path(raw_plan)
        plan = plan if plan.is_absolute() else bundle_root / plan
        if alias is None and (plan.resolve() == target.resolve()
                              or (plan.exists() and target.exists() and os.path.samefile(plan, target))):
            alias = "planning.file"
    if alias is None and target.exists() and not target.is_file():
        alias = "a non-file path"
    if alias is not None:
        raise ValueError(
            f"Saved build_target {raw} aliases {alias}; a build output must "
            "not name a ROM, project, tool or dependency input"
        )
    if target.suffix != ".sfc":
        raise ValueError(f"Invalid saved build_target: {raw!r}")
    return raw


def _without_dev_rom_fields(manifest: dict) -> dict:
    """Drop hack manifest fields a native-saved dev ROM edit may change."""
    masked = json.loads(json.dumps(manifest))
    rom = masked.get("rom")
    if isinstance(rom, dict):
        rom.pop("dev_rom_sha1", None)
        rom.pop("dev_rom_size", None)
    for field in DEV_ROM_MANIFEST_FIELDS:
        masked.pop(field, None)
    tags = masked.get("room_tags")
    if isinstance(tags, dict) and tags.get("dispatch_source") == "dev_rom":
        masked.pop("room_tags")
        if isinstance(masked.get("summary"), dict):
            masked["summary"].pop("room_tag_count", None)
    return masked


def _generate_bundle_hack_manifest(bundle_root: Path) -> dict:
    project_root = bundle_root / "project"
    patched_rom = project_root / "Roms" / "oos168x.sfc"
    return generate_manifest(
        project_root,
        rom_path=patched_rom if patched_rom.is_file() else None,
        dev_rom_path=bundle_root / "rom",
        manifest_root=bundle_root,
    )


def write_bundle_hack_manifest(bundle_root: Path) -> Path:
    """Generate the active manifest from staged source and editable ROM."""
    destination = bundle_root / PORTABLE_HACK_MANIFEST
    destination.parent.mkdir(parents=True, exist_ok=True)
    manifest = _generate_bundle_hack_manifest(bundle_root)
    destination.write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )
    return destination


def _portable_palette_catalog(bundle_root: Path) -> str | None:
    """Rebase optional metadata from the staged desktop descriptor."""
    descriptor = bundle_root / "project" / "Oracle-of-Secrets.yaze"
    if not descriptor.is_file():
        return None
    _, assignments = _parse_project_contract(descriptor.read_text(encoding="utf-8"))
    values = [value for section, key, value in assignments
              if section == "files" and key == "palette_catalog_file"]
    if len(values) > 1:
        raise ValueError("Duplicate palette_catalog_file in desktop project")
    if not values or not values[0]:
        return None
    relative = Path(values[0])
    if (relative.is_absolute() or PureWindowsPath(values[0]).root
            or any(part == ".." for part in relative.parts)
            or "\\" in values[0] or ":" in values[0] or "\0" in values[0]):
        raise ValueError("palette_catalog_file must be project-relative")
    rebased = "project/" + relative.as_posix()
    resolved = _resolve_bundle_member(
        bundle_root, rebased, "palette_catalog_file", must_exist=True)
    if not resolved.is_relative_to((bundle_root / "project").resolve()):
        raise ValueError("palette_catalog_file escapes the source snapshot")
    validate_palette_catalog(resolved)
    return rebased


def write_project_file(bundle_root: Path, name: str, rom_sha1: str) -> None:
    """
    Write `project.yaze` at bundle root with paths relative to bundle root.

    Note: paths in `.yaze` are relative to the directory containing the file.
    For `.yazeproj` bundles, yaze stores `project.yaze` at bundle root.
    """
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project_id = slugify_project_id(name)
    palette_catalog = _portable_palette_catalog(bundle_root)

    # Keep this file intentionally minimal and portable. yaze will add more
    # settings as users customize the project.
    content = "\n".join(
        [
            "# yaze Project File",
            "# Format Version: 2.0",
            "# Generated by export_yazeproj_bundle.py",
            f"# Last Modified: {now}",
            "",
            "[project]",
            f"name={name}",
            "description=Oracle of Secrets ROM Hack (Zelda 3)",
            "author=",
            "license=",
            "version=2.0",
            f"created_date={now}",
            f"last_modified={now}",
            "yaze_version=",
            "created_by=export_yazeproj_bundle.py",
            f"project_id={project_id}",
            "tags=",
            "",
            "[files]",
            "rom_filename=rom",
            "rom_backup_folder=backups",
            "code_folder=project",
            "assets_folder=project",
            "patches_folder=project",
            "labels_filename=",
            "symbols_filename=",
            "output_folder=project/Roms",
            "custom_objects_folder=project/Dungeons/Objects/Data",
            f"hack_manifest_file={PORTABLE_HACK_MANIFEST}",
            *([f"palette_catalog_file={palette_catalog}"] if palette_catalog else []),
            "additional_roms=",
            "",
            "[feature_flags]",
            # Oracle-of-Secrets relies on ZSCustomOverworld and custom object
            # support; make the portable bundle open with the right defaults.
            "load_custom_overworld=true",
            "apply_zs_custom_overworld_asm=true",
            "save_dungeon_maps=false",
            "save_dungeon_water_fill_zones=false",
            "save_graphics_sheet=false",
            "enable_custom_objects=true",
            "",
            "[rom]",
            "role=dev",
            f"expected_hash={rom_sha1}",
            "write_policy=block",
            "",
            "[workspace]",
            "autosave_enabled=false",
            "autosave_interval_secs=300",
            "backup_on_save=true",
            "backup_retention_count=20",
            "backup_keep_daily=true",
            "backup_keep_daily_days=14",
            "",
            "[build]",
            # Build is typically run on macOS (or remote build host), not iOS.
            # Keep this deterministic and repo-local.
            f"build_script={PORTABLE_BUILD_COMMAND}",
            "output_folder=project/Roms",
            "git_repository=project",
            "track_changes=false",
            "build_configurations=",
            "build_target=project/Roms/oos168x.sfc",
            "asm_entry_point=project/Oracle_main.asm",
            "asm_sources=",
            "last_build_hash=",
            "build_number=0",
            "",
            "# End of YAZE Project File",
            "",
        ]
    )
    (bundle_root / "project.yaze").write_bytes(content.encode("utf-8"))


def write_ios_manifest(bundle_root: Path, name: str, rom_sha1: str) -> None:
    # Matches `YazeDocumentManifest` fields (yaze iOS).
    now = iso8601_now_utc()
    manifest = {
        "version": 2,
        "name": name,
        "romChecksum": rom_sha1,
        "createdAt": now,
        "lastModifiedAt": now,
        "deviceName": platform.node() or "export",
    }
    (bundle_root / "manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def verify_bundle(bundle_root: Path) -> None:
    required = [
        bundle_root / "project.yaze",
        bundle_root / "manifest.json",
        bundle_root / "rom",
        bundle_root / PORTABLE_HACK_MANIFEST,
        bundle_root
        / "project"
        / "Docs"
        / "Dev"
        / "Planning"
        / "oracle_resource_labels.json",
        bundle_root / "project" / "Docs" / "Dev" / "Planning" / "story_events.json",
        bundle_root / "project" / "Docs" / "Dev" / "Planning" / "overworld.json",
    ]
    missing = [p for p in required if not p.exists()]
    if missing:
        raise FileNotFoundError(
            "Bundle is missing required files:\n"
            + "\n".join(f"  - {p}" for p in missing)
        )

    # Ensure manifest checksum matches ROM file. manifest.json stays the export
    # identity; an authoring bundle accepts a different editable rom only when
    # a genuine native Save binds it.
    manifest = json.loads((bundle_root / "manifest.json").read_text(encoding="utf-8"))
    rom_sha1 = sha1_file(bundle_root / "rom")
    export_sha1 = manifest.get("romChecksum")
    rom_edited = export_sha1 != rom_sha1
    if rom_edited and not (bundle_root / AUTHORING_RECEIPT).exists():
        raise ValueError(
            f"manifest.json romChecksum mismatch: {export_sha1} != {rom_sha1}"
        )

    project_content = (bundle_root / "project.yaze").read_bytes().decode(
        "utf-8"
    )
    authoring = verify_authoring_dependencies(
        bundle_root, (export_sha1, rom_sha1) if rom_edited else None)
    if authoring:
        rom_sha1 = export_sha1
    contract = ORACLE_SAVE_CONTRACT
    if authoring and authoring["mode"] == "desktop":
        contract = ORACLE_DESKTOP_SAVE_CONTRACT
        validate_desktop_project_contract(project_content)
    validate_portable_project_contract(
        project_content, rom_sha1, contract,
        AUTHORING_BUILD_COMMAND if authoring else PORTABLE_BUILD_COMMAND,
        _saved_build_target(bundle_root, authoring,
                            project_content.encode("utf-8")))
    if not authoring:
        palette_catalog = _portable_palette_catalog(bundle_root)
        _, assignments = _parse_project_contract(project_content)
        values = [value for section, key, value in assignments
                  if section == "files" and key == "palette_catalog_file"]
        if values != ([palette_catalog] if palette_catalog else []):
            raise ValueError("Bundle palette_catalog_file differs from source descriptor")

    hack_manifest_path = bundle_root / PORTABLE_HACK_MANIFEST
    try:
        hack_manifest = json.loads(hack_manifest_path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"Invalid hack manifest JSON: {hack_manifest_path}"
        ) from exc
    if not isinstance(hack_manifest, dict):
        raise ValueError("hack_manifest.json root must be an object")
    validate_portable_manifest_contract(bundle_root, hack_manifest)

    expected_manifest = _generate_bundle_hack_manifest(bundle_root)
    if rom_edited:
        if hack_manifest.get("rom", {}).get("dev_rom_sha1") != export_sha1:
            raise ValueError(
                "hack_manifest.json dev_rom_sha1 is not the bundle's export "
                "romChecksum; refusing relabeled ROM provenance"
            )
        hack_manifest = _without_dev_rom_fields(hack_manifest)
        expected_manifest = _without_dev_rom_fields(expected_manifest)
    if hack_manifest != expected_manifest:
        raise ValueError(
            "hack_manifest.json is stale relative to the bundled ROM or "
            "project source"
        )


def refresh_planning_outputs(repo_root: Path) -> None:
    # Keep these local and deterministic: yaze reads them from
    # Docs/Dev/Planning/ via HackManifest::LoadProjectRegistry().
    scripts = [
        repo_root / "Scripts" / "Generate" / "extract_overworld_registry.py",
        repo_root / "Scripts" / "Generate" / "extract_resource_labels.py",
        repo_root / "Scripts" / "Generate" / "extract_story_events.py",
    ]
    for script in scripts:
        if not script.exists():
            raise FileNotFoundError(str(script))
        subprocess.run([sys.executable, str(script)], cwd=str(repo_root), check=True)


def _rename_without_replacement(source: Path, destination: Path) -> None:
    """Publish a directory without POSIX rename's empty-directory replacement."""
    if os.name == "nt":
        os.rename(source, destination)
        return
    libc = ctypes.CDLL(None, use_errno=True)
    if sys.platform == "darwin":
        rename = libc.renamex_np
        rename.argtypes = [ctypes.c_char_p, ctypes.c_char_p, ctypes.c_uint]
        rename.restype = ctypes.c_int
        # Darwin sys/stdio.h: RENAME_EXCL.
        result = rename(os.fsencode(source), os.fsencode(destination), 0x4)
    elif sys.platform.startswith("linux") and hasattr(libc, "renameat2"):
        rename = libc.renameat2
        rename.argtypes = [
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_int,
            ctypes.c_char_p,
            ctypes.c_uint,
        ]
        rename.restype = ctypes.c_int
        # AT_FDCWD and RENAME_NOREPLACE; unsupported kernels/filesystems refuse.
        result = rename(-100, os.fsencode(source), -100, os.fsencode(destination), 1)
    else:
        raise OSError(errno.ENOTSUP, "Exclusive directory publication is unavailable")
    if result != 0:
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(destination))


def _publish_authoring_bundle(
    staging: Path, output: Path, old: Path, selected_rom: Path, expected_rom: bytes
) -> None:
    if old.exists() or old.is_symlink():
        raise FileExistsError(f"Authoring .old path became occupied: {old}")
    _source_path(str(selected_rom), Path.cwd())
    if selected_rom.read_bytes() != expected_rom:
        raise ValueError("Selected ROM changed before authoring publication")
    _rename_without_replacement(staging, output)


def main() -> int:
    repo_root = find_repo_root()

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--rom",
        type=Path,
        default=None,
        help="Path to base ROM to embed (default: auto-pick Roms/oos168.sfc)",
    )
    parser.add_argument(
        "--name",
        default="Oracle-of-Secrets",
        help="Bundle name (default: Oracle-of-Secrets)",
    )
    parser.add_argument(
        "--out-icloud",
        action="store_true",
        default=False,
        help="Write bundle into iCloud Drive at 'Yaze/Projects/<Name>.yazeproj' (macOS only)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=repo_root / "build" / "yazeproj" / "Oracle-of-Secrets.yazeproj",
        help="Output bundle path (default: build/yazeproj/Oracle-of-Secrets.yazeproj)",
    )
    parser.add_argument(
        "--refresh-planning",
        action="store_true",
        default=False,
        help="Regenerate Docs/Dev/Planning/oracle_resource_labels.json + story_events.json before bundling",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite output bundle if it already exists",
    )
    parser.add_argument("--project", type=Path,
                        help="Preserve and rebase an existing authoring .yaze descriptor")
    parser.add_argument("--lyra-terrain", type=Path,
                        help="Explicit terrain source override (requires --project)")
    parser.add_argument("--graphics-preview", type=Path,
                        help="Explicit graphics catalog override (requires --project)")
    parser.add_argument("--desktop", action="store_true",
                        help="Retain the desktop graphics-save contract (requires --project)")
    args = parser.parse_args()
    if not args.project and (args.lyra_terrain or args.graphics_preview or args.desktop):
        parser.error("--lyra-terrain, --graphics-preview and --desktop require --project")

    rom_path: Path | None = args.rom
    if rom_path is None:
        cand = repo_root / "Roms" / "oos168.sfc"
        if cand.exists():
            rom_path = cand
        else:
            print(
                "ERROR: --rom not provided and no default ROM found under Roms/",
                file=sys.stderr,
            )
            return 2

    rom_path = (_source_path(str(rom_path), Path.cwd())
                if args.project else rom_path.resolve())
    if not rom_path.exists():
        print(f"ERROR: ROM not found: {rom_path}", file=sys.stderr)
        return 2

    out_bundle = args.out
    if args.out_icloud:
        icloud_root = default_icloud_drive_root()
        if icloud_root is None:
            print(
                "ERROR: iCloud Drive folder not found at "
                "'~/Library/Mobile Documents/com~apple~CloudDocs'",
                file=sys.stderr,
            )
            return 2
        out_bundle = (
            icloud_root / "Yaze" / "Projects" / f"{args.name}.yazeproj"
        )
    if not out_bundle.is_absolute():
        out_bundle = (repo_root / out_bundle).resolve()

    staging_bundle = out_bundle.with_name(out_bundle.name + ".staging")
    old_bundle = out_bundle.with_name(out_bundle.name + ".old")
    if args.project:
        if args.force or any(path.exists() for path in (out_bundle, staging_bundle, old_bundle)):
            raise ValueError("Authoring export requires a fresh output/staging path; --force is portable-only")
        for source in (args.project, args.lyra_terrain, args.graphics_preview, rom_path):
            if source is not None and any(
                source.resolve().is_relative_to(target.resolve())
                for target in (out_bundle, staging_bundle, old_bundle)
            ):
                raise ValueError("Bundle output aliases an authoring input")

    if out_bundle.exists() and not args.force:
        print(f"ERROR: output already exists: {out_bundle}", file=sys.stderr)
        print("Pass --force to overwrite.", file=sys.stderr)
        return 2

    if staging_bundle.exists() and not args.project:
        shutil.rmtree(staging_bundle)

    if args.refresh_planning:
        refresh_planning_outputs(repo_root)

    # Create bundle layout.
    staging_bundle.mkdir(parents=True, exist_ok=not args.project)
    (staging_bundle / "backups").mkdir(parents=True, exist_ok=True)
    (staging_bundle / "output").mkdir(parents=True, exist_ok=True)

    # Copy ROM to bundle root as `rom` (no extension).
    rom_dst = staging_bundle / "rom"
    rom_before = rom_path.read_bytes() if args.project else None
    shutil.copy2(rom_path, rom_dst)
    if args.project and (rom_path.read_bytes() != rom_before or rom_dst.read_bytes() != rom_before):
        raise ValueError("Selected ROM changed during capture")
    rom_sha1 = sha1_file(rom_dst)

    # Copy repo snapshot to bundle/project/.
    copy_repo_snapshot(repo_root, staging_bundle / "project",
                       reject_symlinks=args.project is not None)
    # Build scripts expect a writable Roms/ folder inside the code snapshot.
    # We intentionally do not copy the repo's real Roms/ directory into the
    # bundle (too large + machine-specific), but an empty directory keeps the
    # build pipeline functional when invoked with OOS_BASE_ROM=rom.
    (staging_bundle / "project" / "Roms").mkdir(parents=True, exist_ok=True)

    # Generate the active manifest from the staged snapshot. The build script
    # regenerates this exact path after assembling the playable ROM.
    if args.project:
        write_authoring_project(staging_bundle, args.project, rom_sha1,
                                lyra_terrain=args.lyra_terrain,
                                graphics_preview=args.graphics_preview,
                                desktop=args.desktop,
                                rom_source=rom_path)
    write_bundle_hack_manifest(staging_bundle)

    # Write config + metadata. Existing portable exports keep their contract.
    if not args.project:
        write_project_file(staging_bundle, args.name, rom_sha1)
    write_ios_manifest(staging_bundle, args.name, rom_sha1)
    verify_bundle(staging_bundle)

    if args.project:
        _publish_authoring_bundle(staging_bundle, out_bundle, old_bundle,
                                  rom_path, rom_before)
    else:
        # Keep the existing portable replacement/--force contract.
        if old_bundle.exists():
            shutil.rmtree(old_bundle)
        if out_bundle.exists():
            out_bundle.rename(old_bundle)
        staging_bundle.rename(out_bundle)
        if old_bundle.exists():
            shutil.rmtree(old_bundle)

    print(f"Wrote bundle: {out_bundle}")
    print(f"  ROM: {rom_path} -> {out_bundle / 'rom'} (sha1={rom_sha1})")
    print("  Project snapshot: project/ (filtered)")
    print("  Open in yaze: File -> Open -> select the .yazeproj directory")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
