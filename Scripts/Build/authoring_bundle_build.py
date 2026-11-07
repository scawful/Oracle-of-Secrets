#!/usr/bin/env python3
"""Delegate a saved authoring project's bound ROM to its current Oracle build.

Yaze owns expected-hash, producer/transfer and committed-Save admission. This
adapter does not create evidence, change references or publish a project. The
normal build_rom.sh remains the format/compiler owner for its saved ROM input.
"""
from __future__ import annotations

import argparse
import configparser
import os
from pathlib import Path
import re
import subprocess
import sys


def _path(root: Path, value: str) -> Path:
    path = Path(value)
    return (path if path.is_absolute() else root / path).resolve()


def _bound(root: Path, configured: str, key: str,
           environment: dict[str, str]) -> Path:
    if not configured.strip():
        raise ValueError(f"Authoring Build requires the saved {key} binding")
    result = _path(root, configured.strip())
    supplied = environment.get(key, "").strip()
    if supplied and _path(root, supplied) != result:
        raise ValueError(f"{key} differs from the saved project binding")
    return result


def build_project(project: Path) -> int:
    project = project.resolve(strict=True)
    root = project.parent
    config = configparser.ConfigParser(interpolation=None)
    with project.open(encoding="utf-8") as stream:
        config.read_file(stream)
    environment = dict(os.environ)
    _bound(root, str(project), "YAZE_PROJECT_FILE", environment)
    for key in ("lyra_terrain_file", "lyra_build_request_file"):
        if config.get("files", key, fallback="").strip():
            raise ValueError(
                f"Build Project stopped: legacy {key} is still configured; "
                "complete native import and managed project adoption first")
    for key in ("YAZE_LYRA_TERRAIN_FILE", "OOS_LYRA_PROJECT", "OOS_LYRA_REQUEST"):
        if environment.get(key, "").strip():
            raise ValueError(f"Build Project stopped: legacy {key} is still set")

    code = _bound(root, config.get("files", "code_folder", fallback=""),
                  "YAZE_PROJECT_CODE_FOLDER", environment)
    rom = _bound(root, config.get("files", "rom_filename", fallback=""),
                 "YAZE_PROJECT_ROM", environment)
    output = _bound(root, config.get("build", "build_target", fallback=""),
                    "YAZE_PROJECT_OUTPUT", environment)
    script = code / "Scripts" / "Build" / "build_rom.sh"
    if not code.is_dir() or not script.is_file():
        raise ValueError(f"Configured Oracle build script is missing: {script}")
    if not rom.is_file():
        raise ValueError(f"Configured saved project ROM is missing: {rom}")
    # The existing compiler emits Roms/oos<N>x.sfc. Refuse an unrelated target
    # rather than copying output or claiming a successful build at another path.
    match = re.fullmatch(r"oos([0-9]+)x\.sfc", output.name)
    if not match or output.parent != (code / "Roms").resolve():
        raise ValueError("Build target must be code_folder/Roms/oos<N>x.sfc")
    if output == rom or (output.exists() and output.samefile(rom)):
        raise ValueError("Build target aliases the saved project ROM")
    for section in ("files", "build"):
        folder = config.get(section, "output_folder", fallback="").strip()
        if folder and _path(root, folder) != output.parent:
            raise ValueError(f"[{section}] output_folder differs from build_target")
    override = environment.get("OOS_BASE_ROM", "").strip()
    if override:
        base = _path(root, override)
        if not base.is_file() or not base.samefile(rom):
            raise ValueError("OOS_BASE_ROM differs from the saved project ROM")

    backups = config.get("files", "rom_backup_folder", fallback="backups").strip()
    backup_root = _bound(root, backups, "OOS_BACKUP_ROOT", environment)
    # Save As moves the descriptor, not the bound source/ROM owner. Keep the
    # generated manifest namespace within that owner instead of widening it to
    # an arbitrary common ancestor of unrelated inputs.
    manifest_owner = code if rom.is_relative_to(code) else code.parent
    if (manifest_owner.parent == manifest_owner or
            not rom.is_relative_to(manifest_owner)):
        raise ValueError("ROM must belong to the source namespace (code_folder "
                         "or its immediate parent, never the filesystem root)")
    manifest_root = _bound(root, str(manifest_owner), "OOS_MANIFEST_ROOT", environment)
    compiled_manifest = output.with_suffix(".manifest.json")
    if compiled_manifest.is_symlink():
        raise ValueError("Compiled manifest must not be a symlink")
    manifest_output = _bound(root, str(compiled_manifest),
                             "OOS_MANIFEST_OUTPUT", environment)
    if manifest_output.exists() and (
            not manifest_output.is_file() or manifest_output.stat().st_nlink != 1):
        raise ValueError("Compiled manifest must be an unaliased regular file")
    policy = config.get("files", "hack_manifest_file", fallback="").strip()
    protected = [project, rom, output, code / "Roms/hack_manifest.json"]
    if policy:
        protected.append(_path(root, policy))
    for key in ("YAZE_NATIVE_SAVE_RECEIPT", "YAZE_NATIVE_SAVE_CONTEXT", "OOS_BUILD_RECEIPT"):
        if environment.get(key, "").strip():
            protected.append(_path(root, environment[key]))
    if manifest_output in [path.resolve() for path in protected]:
        raise ValueError("Compiled manifest aliases project policy or saved inputs")
    environment.update(YAZE_PROJECT_FILE=str(project),
        YAZE_PROJECT_CODE_FOLDER=str(code), YAZE_PROJECT_ROM=str(rom),
        YAZE_PROJECT_OUTPUT=str(output), OOS_BACKUP_ROOT=str(backup_root),
        OOS_MANIFEST_ROOT=str(manifest_root),
        OOS_MANIFEST_OUTPUT=str(manifest_output))
    # No OOS_BASE_ROM injection: build_rom.sh consumes YAZE_PROJECT_ROM directly.
    # Save receipt/context, producer controls and tool selection pass unchanged.
    return subprocess.run(["bash", str(script), match[1]], cwd=root,
                          env=environment, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        return build_project(args.project)
    except (OSError, ValueError, configparser.Error) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
