#!/usr/bin/env python3
"""Delegate a saved authoring project's bound ROM to its current Oracle build.

Yaze owns expected-hash, producer/transfer and committed-Save admission. This
adapter does not create evidence, change references or publish a project. The
normal build_rom.sh remains the format/compiler owner for its saved ROM input.
"""
from __future__ import annotations

import argparse
import configparser
import hashlib
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


def _admits_page_tile16(config: configparser.ConfigParser) -> bool:
    # Same spellings as Yaze's project ParseBool, so Build follows the editor's
    # saved revision5 admission exactly; absent or any other value stays off.
    value = config.get("feature_flags", "experimental_page_tile16", fallback="")
    return value.strip() in ("true", "1", "yes")


def prepare_source_graphics(project: Path, base_rom: Path, *,
                            compiler_root: Path | None = None) -> int:
    """Refresh derived sheets for the saved source binding, never the ROM.

    Called after build_rom.sh selects flags. Its mandatory --check still runs
    afterwards; ordinary builds without a project remain check-only.
    """
    project = project.resolve(strict=True)
    config = configparser.ConfigParser(interpolation=None)
    config.read(project, encoding="utf-8")
    spec_name = config.get("graphics_sheets", "source_spec", fallback="").strip()
    if not spec_name:
        return 0
    environment = dict(os.environ)
    _bound(project.parent, str(project), "YAZE_PROJECT_FILE", environment)
    code = _bound(project.parent, config.get("files", "code_folder", fallback=""),
                  "YAZE_PROJECT_CODE_FOLDER", environment)
    actual_root = (compiler_root or Path(__file__).resolve().parents[2]).resolve(strict=True)
    if code != actual_root:
        raise ValueError("Source graphics code_folder differs from the actual compiler root")
    rom = _bound(project.parent, config.get("files", "rom_filename", fallback=""),
                 "YAZE_PROJECT_ROM", environment)
    if not rom.is_file() or not base_rom.resolve(strict=True).samefile(rom):
        raise ValueError("Source graphics base ROM differs from the saved project ROM")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Generate"))
    try:
        import sheet_overrides as sheets
        from asm_source import _load_global_defines
        if spec_name not in (sheets.SPEC.as_posix(), sheets.D4_SPEC.as_posix()):
            raise ValueError("Source graphics requires a canonical ordinary or D4 spec")
        spec_path = code / spec_name
        if spec_path.resolve(strict=True) != spec_path:
            raise ValueError("Source graphics spec must not redirect through a symlink")
        saved_sha1 = config.get("graphics_sheets", "source_spec_sha1", fallback="")
        if saved_sha1 != hashlib.sha1(spec_path.read_bytes()).hexdigest():
            raise ValueError("Source graphics saved spec SHA1 differs from the current spec")
        defines = _load_global_defines(code)
        enabled = defines.get(sheets.FLAG)
        if enabled not in (0, 1):
            raise ValueError("Source sheet feature flag is missing or invalid")
        if not enabled:
            return 0
        if defines.get("ENABLE_D4_ZORA_REDESIGN"):
            ordinary = code / sheets.SPEC
            if ordinary.resolve(strict=True) != ordinary:
                raise ValueError("Source graphics ordinary spec must not redirect through a symlink")
        selected, output = sheets.selected_sources(code)
        if selected.as_posix() != spec_name:
            raise ValueError("Source graphics spec differs from the current build flags")
        out = code / output
        if out.resolve() != out:
            raise ValueError("Source graphics output must stay in the actual compiler root")
        spec, items = sheets.build(spec_path, rom, code, rom_role="editable_base")
        frame_source = code / "Data/graphics/d4_zora/frames.asm"
        frames = frame_source.read_bytes() if selected == sheets.D4_SPEC else None
        files = sheets.generated_files(items, frames)
        # Validate every destination before reading stale bytes or publishing any
        # stream. A canonical output root alone does not protect nested parents.
        for name in files:
            target = out / name
            if not target.is_relative_to(out) or target.resolve() != target or target.is_symlink():
                raise ValueError("Source graphics destination redirects outside its canonical output path")
            for parent in target.parents:
                if parent == out:
                    break
                if parent.is_symlink() or (parent.exists() and not parent.is_dir()):
                    raise ValueError("Source graphics destination parent must be an unredirected directory")
            if target.exists() and not target.is_file():
                raise ValueError("Source graphics destination must be a regular file")
        if any(not (out / name).is_file() or (out / name).read_bytes() != data
               for name, data in files.items()):
            inputs = [project, rom, spec_path]
            if frames is not None:
                inputs.append(frame_source)
            inputs.extend(spec_path.parent / entry["source"] for entry in spec["sheets"])
            sheets.write_outputs(out, files, inputs)
        return 0
    finally:
        sys.path.pop(0)


def build_project(project: Path, *, enable: str = "", disable: str = "") -> int:
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
    command = ["bash", str(script), match[1]]
    # Forward explicit CSV selections; build_rom.sh owns feature validation,
    # normalization and precedence. Empty selections keep the default command.
    if enable:
        command.extend(["--enable", enable])
    if disable:
        command.extend(["--disable", disable])
    if _admits_page_tile16(config):
        command.append("--experimental-page-tile16")
    return subprocess.run(command, cwd=root,
                          env=environment, check=False).returncode


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--enable", default="", help="Comma-separated features for build_rom.sh to enable")
    parser.add_argument("--disable", default="", help="Comma-separated features for build_rom.sh to disable")
    parser.add_argument("--prepare-source-graphics", action="store_true",
                        help="Refresh saved source sheets after compiler flag selection")
    parser.add_argument("--base-rom", type=Path,
                        help="Actual compiler base; required by source graphics preparation")
    args = parser.parse_args(argv)
    try:
        if args.prepare_source_graphics:
            if args.base_rom is None:
                raise ValueError("Source graphics preparation requires --base-rom")
            return prepare_source_graphics(args.project, args.base_rom)
        return build_project(args.project, enable=args.enable, disable=args.disable)
    except (OSError, ValueError, configparser.Error) as error:
        print(error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
