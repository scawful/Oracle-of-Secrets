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
import datetime as _dt
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


PORTABLE_BUILD_SCRIPT = "project/Scripts/Build/build_rom.sh"
PORTABLE_HACK_MANIFEST = "project/Roms/hack_manifest.json"
PORTABLE_BUILD_COMMAND = (
    "OOS_BASE_ROM=rom OOS_BACKUP_ROOT=backups OOS_MANIFEST_ROOT=. "
    f"{PORTABLE_BUILD_SCRIPT} 168"
)
ORACLE_SAVE_CONTRACT = (
    ("feature_flags", "save_dungeon_maps", "false"),
    ("feature_flags", "save_dungeon_water_fill_zones", "false"),
    ("feature_flags", "save_graphics_sheet", "false"),
    ("workspace", "autosave_enabled", "false"),
    ("workspace", "backup_on_save", "true"),
)
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
    ("build", "build_target", "project/Roms/oos168x.sfc"),
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


def validate_oracle_project_contract(content: str) -> None:
    """Require Oracle's fail-closed save and workspace settings exactly once."""
    sections, assignments = _parse_project_contract(content)
    for section in ("feature_flags", "workspace"):
        if sections.count(section) != 1:
            raise ValueError(
                f"project.yaze must contain exactly one [{section}] section"
            )
    for section, key, value in ORACLE_SAVE_CONTRACT:
        _require_project_assignment(assignments, section, key, value)


def validate_portable_project_contract(
    content: str,
    expected_rom_sha1: str,
) -> None:
    """Require the portable descriptor's paths and build contract."""
    validate_oracle_project_contract(content)
    sections, assignments = _parse_project_contract(content)
    for section in ("project", "files", "rom", "build"):
        if sections.count(section) != 1:
            raise ValueError(
                f"project.yaze must contain exactly one [{section}] section"
            )
    for section, key, value in PORTABLE_PROJECT_CONTRACT:
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


def _iter_manifest_source_locations(value: object):
    if isinstance(value, dict):
        for key, child in value.items():
            if key == "source" and isinstance(child, str):
                yield child
            yield from _iter_manifest_source_locations(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_manifest_source_locations(child)


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


def copy_repo_snapshot(src_root: Path, dst_root: Path) -> None:
    dst_root.mkdir(parents=True, exist_ok=True)

    for dirpath, dirnames, filenames in os.walk(src_root):
        abs_dir = Path(dirpath)
        rel_dir = abs_dir.relative_to(src_root)

        # Prune excluded directories early.
        keep_dirnames: list[str] = []
        for d in dirnames:
            rel = rel_dir / d
            if not should_skip(rel):
                keep_dirnames.append(d)
        dirnames[:] = keep_dirnames

        # Ensure destination directory exists.
        (dst_root / rel_dir).mkdir(parents=True, exist_ok=True)

        for filename in filenames:
            rel = rel_dir / filename
            if should_skip(rel):
                continue
            src_file = abs_dir / filename
            dst_file = dst_root / rel
            dst_file.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src_file, dst_file)


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


def write_project_file(bundle_root: Path, name: str, rom_sha1: str) -> None:
    """
    Write `project.yaze` at bundle root with paths relative to bundle root.

    Note: paths in `.yaze` are relative to the directory containing the file.
    For `.yazeproj` bundles, yaze stores `project.yaze` at bundle root.
    """
    now = _dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    project_id = slugify_project_id(name)

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

    # Ensure manifest checksum matches ROM file.
    manifest = json.loads((bundle_root / "manifest.json").read_text(encoding="utf-8"))
    rom_sha1 = sha1_file(bundle_root / "rom")
    if manifest.get("romChecksum") != rom_sha1:
        raise ValueError(
            f"manifest.json romChecksum mismatch: {manifest.get('romChecksum')} != {rom_sha1}"
        )

    project_content = (bundle_root / "project.yaze").read_bytes().decode(
        "utf-8"
    )
    validate_portable_project_contract(project_content, rom_sha1)

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
    if hack_manifest != expected_manifest:
        raise ValueError(
            "hack_manifest.json is stale relative to the bundled ROM or "
            "project source"
        )


def refresh_planning_outputs(repo_root: Path) -> None:
    # Keep these local and deterministic: yaze reads them from
    # Docs/Dev/Planning/ via HackManifest::LoadProjectRegistry().
    scripts = [
        repo_root / "scripts" / "extract_overworld_registry.py",
        repo_root / "scripts" / "extract_resource_labels.py",
        repo_root / "scripts" / "extract_story_events.py",
    ]
    for script in scripts:
        if not script.exists():
            raise FileNotFoundError(str(script))
        subprocess.run([sys.executable, str(script)], cwd=str(repo_root), check=True)


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
    args = parser.parse_args()

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

    rom_path = rom_path.resolve()
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

    if out_bundle.exists() and not args.force:
        print(f"ERROR: output already exists: {out_bundle}", file=sys.stderr)
        print("Pass --force to overwrite.", file=sys.stderr)
        return 2

    if staging_bundle.exists():
        shutil.rmtree(staging_bundle)

    if args.refresh_planning:
        refresh_planning_outputs(repo_root)

    # Create bundle layout.
    staging_bundle.mkdir(parents=True, exist_ok=True)
    (staging_bundle / "backups").mkdir(parents=True, exist_ok=True)
    (staging_bundle / "output").mkdir(parents=True, exist_ok=True)

    # Copy ROM to bundle root as `rom` (no extension).
    rom_dst = staging_bundle / "rom"
    shutil.copy2(rom_path, rom_dst)
    rom_sha1 = sha1_file(rom_dst)

    # Copy repo snapshot to bundle/project/.
    copy_repo_snapshot(repo_root, staging_bundle / "project")
    # Build scripts expect a writable Roms/ folder inside the code snapshot.
    # We intentionally do not copy the repo's real Roms/ directory into the
    # bundle (too large + machine-specific), but an empty directory keeps the
    # build pipeline functional when invoked with OOS_BASE_ROM=rom.
    (staging_bundle / "project" / "Roms").mkdir(parents=True, exist_ok=True)

    # Generate the active manifest from the staged snapshot. The build script
    # regenerates this exact path after assembling the playable ROM.
    write_bundle_hack_manifest(staging_bundle)

    # Write config + metadata.
    write_project_file(staging_bundle, args.name, rom_sha1)
    write_ios_manifest(staging_bundle, args.name, rom_sha1)
    verify_bundle(staging_bundle)

    # Swap bundle into place (reduce the chance of iCloud syncing a partial
    # directory tree). Keep a short-lived `.old` copy when overwriting.
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
