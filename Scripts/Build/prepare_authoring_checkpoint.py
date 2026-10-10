#!/usr/bin/env python3
"""Snapshot a Yaze editing project onto an identified RC source, without building.

Only saved file changes relative to the original authoring checkpoint are
carried forward. The output is a new, independent build directory. Existing
build_rom.sh performs assembly; this tool never stages or reloads an emulator.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


AUTHORING_DIRS = {"Core", "Data", "Dungeons", "Menu", "Sprites"}
SKIP_DIRS = {".git", ".context", "__pycache__", "Backups", ".pytest_cache"}
TEXT_SUFFIXES = {".asm", ".json", ".org", ".md", ".txt"}


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_local(root: Path, relative: str) -> bytes:
    path = root / relative
    if Path(relative).is_absolute() or ".." in Path(relative).parts:
        raise ValueError(f"Path must be relative to its project: {relative}")
    for part in (path, *path.parents):
        if part == root:
            break
        if part.is_symlink():
            raise ValueError(f"Symlinks are not checkpoint inputs: {path}")
    return path.read_bytes()


def inventory(root: Path, authoring_only: bool = False) -> dict[str, bytes]:
    result = {}
    for directory, dirs, files in os.walk(root, followlinks=False):
        parent = Path(directory)
        for name in list(dirs):
            if name in SKIP_DIRS or (parent == root and
                                    (name == "Roms" or
                                     (authoring_only and name not in AUTHORING_DIRS))):
                dirs.remove(name)
            elif (parent / name).is_symlink():
                raise ValueError(f"Symlink directory is not a checkpoint input: {parent / name}")
        for name in files:
            if name.endswith((".pyc", ".pyo", ".lock")):
                continue
            if authoring_only and parent == root:
                continue
            relative = (parent / name).relative_to(root).as_posix()
            result[relative] = read_local(root, relative)
    return result


def project_rom(project_bytes: bytes) -> str:
    config = configparser.ConfigParser(interpolation=None, strict=False)
    config.read_string(project_bytes.decode("utf-8-sig"))
    name = config.get("files", "rom_filename")
    if not name or Path(name).is_absolute() or ".." in Path(name).parts:
        raise ValueError("Project ROM must be a relative file inside the editing folder")
    return name


def check_source_bindings(baseline: bytes, edited: bytes) -> None:
    configs = []
    for data in (baseline, edited):
        config = configparser.ConfigParser(interpolation=None, strict=False)
        config.read_string(data.decode("utf-8-sig"))
        configs.append(config)
    for name in ("code_folder", "assets_folder", "custom_objects_folder",
                 "custom_collision_json", "dungeon_tile_patterns"):
        old, new = [c.get("files", name, fallback="") for c in configs]
        if old != new:
            raise ValueError(f"Changed project source binding requires explicit review: {name}")


def merge_file(name: str, baseline: bytes | None, edited: bytes | None,
               current: bytes | None) -> bytes | None:
    if edited == baseline or edited == current:
        return current
    if current == baseline:
        return edited
    if baseline is None or edited is None or current is None:
        raise ValueError(f"Conflicting addition/deletion: {name}")
    if name.endswith(".sfc") and len(baseline) == len(edited) == len(current):
        merged = bytearray(current)
        conflicts = []
        for offset, (old, edit, rc) in enumerate(zip(baseline, edited, current)):
            if edit != old:
                if rc not in (old, edit):
                    conflicts.append(f"0x{offset:06X}")
                else:
                    merged[offset] = edit
        if conflicts:
            raise ValueError(f"ROM byte conflicts at {', '.join(conflicts[:12])}")
        return bytes(merged)
    if Path(name).suffix not in TEXT_SUFFIXES:
        raise ValueError(f"Both RC and author changed binary data or ROM size: {name}")
    # Let Git reject overlapping edits. No checkout, index or input file changes.
    for data in (current, baseline, edited):
        data.decode("utf-8")
        if b"\0" in data:
            raise ValueError(f"Binary data in text input: {name}")
    with tempfile.TemporaryDirectory(prefix="oos-author-merge-") as tmp:
        paths = [Path(tmp) / x for x in ("rc", "baseline", "author")]
        for path, data in zip(paths, (current, baseline, edited)):
            path.write_bytes(data)
        proc = subprocess.run(["git", "merge-file", "-p", *map(str, paths)],
                              capture_output=True, check=False)
        if proc.returncode:
            raise ValueError(f"Overlapping source edits require review: {name}")
        return proc.stdout


def fingerprints(files: dict[str, bytes]) -> dict:
    return {name: {"sha256": sha(data), "size": len(data)}
            for name, data in sorted(files.items())}


def prepare(project: Path, baseline_manifest: Path, rc_source: Path,
            rc_receipt: Path, output: Path, version: str = "168") -> dict:
    if not version.isdigit():
        raise ValueError("Version must contain only digits")
    project, baseline_manifest, rc_source, rc_receipt, output = (
        p.resolve() for p in (project, baseline_manifest, rc_source, rc_receipt, output))
    manifest_bytes = baseline_manifest.read_bytes()
    receipt_bytes = rc_receipt.read_bytes()
    manifest = json.loads(manifest_bytes)
    receipt = json.loads(receipt_bytes)
    baseline_root = Path(manifest["checkpoint"]).resolve()
    author_root = project.parent
    for root in (author_root, baseline_root, rc_source):
        if output == root or root in output.parents or output in root.parents:
            raise ValueError("Output must be separate from all input directories")
    if output.exists():
        raise ValueError(f"Output already exists: {output}")

    baseline_project = Path(manifest["project"]).name
    baseline_project_bytes = read_local(baseline_root, baseline_project)
    if sha(baseline_project_bytes) != manifest["project_sha256"]:
        raise ValueError("Original project checkpoint hash changed")
    for name, expected in manifest["copied_files"].items():
        if sha(read_local(baseline_root, name)) != expected:
            raise ValueError(f"Original checkpoint hash changed: {name}")

    rc_base_name = f"Roms/oos{version}.sfc"
    rc_files = inventory(rc_source)
    rc_files[rc_base_name] = read_local(rc_source, rc_base_name)
    if receipt.get("state") not in ("passed", "completed", "completed_with_gaps"):
        raise ValueError(f"RC receipt is not a completed build: {receipt.get('state')}")
    if sha(rc_files[rc_base_name]) != receipt["base_rom"]["sha256"]:
        raise ValueError("RC base ROM no longer matches its receipt")
    for name, entry in receipt["snapshots"]["pre_assembly"]["files"].items():
        # Lock files are coordination artifacts, not source inputs.
        if name.endswith(".lock"):
            continue
        if name not in rc_files or sha(rc_files[name]) != entry["sha256"]:
            raise ValueError(f"RC source no longer matches its receipt: {name}")

    author_project = read_local(author_root, project.name)
    check_source_bindings(baseline_project_bytes, author_project)
    base_rom_name = project_rom(baseline_project_bytes)
    author_rom_name = project_rom(author_project)
    baseline = inventory(baseline_root, authoring_only=True)
    edited = inventory(author_root, authoring_only=True)
    baseline[rc_base_name] = read_local(baseline_root, base_rom_name)
    edited[rc_base_name] = read_local(author_root, author_rom_name)
    merged = dict(rc_files)
    changes = []
    for name in sorted(baseline.keys() | edited.keys()):
        old, edit, rc = baseline.get(name), edited.get(name), rc_files.get(name)
        if old == edit:
            continue
        result = merge_file(name, old, edit, rc)
        changes.append({"path": name, "baseline": sha(old) if old is not None else None,
                        "author": sha(edit) if edit is not None else None,
                        "rc": sha(rc) if rc is not None else None,
                        "result": sha(result) if result is not None else None})
        if result is None:
            merged.pop(name, None)
        else:
            merged[name] = result

    # Detect changes during capture instead of silently combining two saves.
    recaptured = inventory(author_root, authoring_only=True)
    recaptured[rc_base_name] = read_local(author_root, author_rom_name)
    if recaptured != edited or read_local(author_root, project.name) != author_project:
        raise ValueError("Editing files changed during capture; save and retry")
    rc_recaptured = inventory(rc_source)
    rc_recaptured[rc_base_name] = read_local(rc_source, rc_base_name)
    if rc_recaptured != rc_files:
        raise ValueError("RC source changed during capture; retry with a frozen source")

    report = {"schema": "oos-authoring-checkpoint-v1", "state": "prepared",
              "project": str(project), "author_rom": author_rom_name,
              "baseline_manifest": str(baseline_manifest),
              "baseline_manifest_sha256": sha(manifest_bytes),
              "rc_source": str(rc_source), "rc_receipt": str(rc_receipt),
              "rc_receipt_sha256": sha(receipt_bytes), "version": version,
              "project_sha256": sha(author_project), "changes": changes,
              "saved_authoring_inputs": fingerprints(edited),
              "rc_inputs": fingerprints(rc_files), "build_inputs": fingerprints(merged),
              "limitations": ["Saved files only; no unsaved editor model capture",
                               "No assembly, runtime or release acceptance",
                               "ROM merge detects byte conflicts, not semantic conflicts"]}
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}-", dir=output.parent))
    try:
        saved_authoring = dict(edited)
        saved_authoring.pop(rc_base_name)
        saved_authoring[author_rom_name] = edited[rc_base_name]
        for directory, files in (("src", merged), ("authoring", saved_authoring)):
            for name, data in files.items():
                path = temp / directory / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
                if directory == "src" and (rc_source / name).is_file():
                    path.chmod((rc_source / name).stat().st_mode & 0o777)
        (temp / "authoring" / project.name).write_bytes(author_project)
        (temp / "checkpoint.json").write_text(json.dumps(report, indent=2) + "\n")
        # Reserve the name after all validation, then move our completed files.
        # An existing checkpoint is never replaced by a repeated command.
        output.mkdir()
        for name in ("src", "authoring", "checkpoint.json"):
            (temp / name).rename(output / name)
    finally:
        shutil.rmtree(temp)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("project", "baseline-manifest", "rc-source", "rc-receipt", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--version", default="168")
    args = parser.parse_args()
    try:
        report = prepare(args.project, args.baseline_manifest, args.rc_source,
                         args.rc_receipt, args.out, args.version)
    except (ValueError, OSError, KeyError, configparser.Error) as exc:
        parser.exit(1, f"checkpoint: {exc}\n")
    print(json.dumps({"state": report["state"], "out": str(args.out.resolve()),
                      "changed_files": [c["path"] for c in report["changes"]]}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
