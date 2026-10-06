#!/usr/bin/env python3
"""Record build inputs and check outcomes; a receipt is not gameplay qualification.

Mutations are atomic and intended for one build process. ``check`` only records
an outcome; ``finish`` enforces required outcomes. Source snapshots describe a
conservative tree, not exact assembled reachability, and survive flag restoration.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from datetime import datetime, timezone

SCHEMA_VERSION = 1
SOURCE_DIRS = ("Config", "Core", "Data", "Dungeons", "Items", "Masks", "Menu",
               "Music", "Overworld", "Sprites", "Util", "Scripts", "Tests")
EXCLUDED_DIRS = {".git", ".context", ".claude", "__pycache__", "node_modules",
                 "build", "dist", "bin", "obj", "output", "outputs"}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".sfc", ".smc", ".sym", ".mlb", ".log",
                     ".o", ".a", ".dylib"}
GENERATED_OUTPUT_DIRS = ("Tests/screenshots",)
PROFILE_FILES = ("Util/macros.asm", "Config/module_flags.asm", "Config/feature_flags.asm")
RESTORABLE_FLAGS = {"Config/module_flags.asm", "Config/feature_flags.asm"}
ROOT_GLOBS = ("*.asm", "*.toml", "*.yaze")
PROTECTED_ROOT_GLOBS = ROOT_GLOBS + ("*.json", "*.yaml", "*.yml", "*.sh", "*.py")
PROTECTED_ROOT_NAMES = ("AGENTS.md", "CLAUDE.md", "README.md", "Makefile", "CMakeLists.txt",
                        ".gitignore", ".gitattributes", ".editorconfig")
FLAG_ASSIGNMENT = re.compile(r"^\s*!(ENABLE_\w+|DISABLE_\w+|DEBUG)\s*=\s*(.*?)\s*$")
LITERAL = re.compile(r"(?:\$[0-9a-fA-F]+|0[xX][0-9a-fA-F]+|[0-9]+)\Z")


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def guard_receipt_destination(path: Path, root: Path, base_rom: Path, version: str) -> None:
    """Reject source/output destinations and existing symlink/hardlink aliases."""
    source_directories = [root / name for name in (*SOURCE_DIRS, ".github")]
    for directory in source_directories:
        if path.is_relative_to(directory.resolve()):
            raise ValueError(f"Receipt path is inside protected source directory: {directory}")
    if path.parent == root and (path.name in PROTECTED_ROOT_NAMES or any(
            path.match(pattern) for pattern in PROTECTED_ROOT_GLOBS)):
        raise ValueError(f"Receipt path is a protected root source/config file: {path}")

    managed = [base_rom, root / ".cache/annotations.json"]
    managed.extend(root / "Roms" / name for name in (
        f"oos{version}.sfc", f"oos{version}_test2.sfc", f"oos{version}x.sfc",
        f"oos{version}x.sym", f"oos{version}x.mlb", f"oos{version}x.smoke.json",
        f"oos{version}x.reload-identity.json", "hooks.json", "hack_manifest.json", "sourcemap.json"))
    if any(path == protected.resolve() for protected in managed):
        raise ValueError("Receipt path aliases a base ROM or managed build artifact")

    if not path.exists():
        return
    destination = path.stat()
    destination_id = (destination.st_dev, destination.st_ino)
    protected_files = managed + [root / name for name in PROTECTED_ROOT_NAMES]
    protected_files.extend(candidate for pattern in PROTECTED_ROOT_GLOBS for candidate in root.glob(pattern))
    for directory in source_directories:
        if directory.exists():
            protected_files.extend(candidate for candidate in directory.rglob("*") if candidate.is_file())
    for protected in protected_files:
        if not protected.is_file():
            continue
        stat = protected.stat()
        if (stat.st_dev, stat.st_ino) == destination_id:
            raise ValueError(f"Receipt path aliases protected input/artifact: {protected}")


def identity(path: Path) -> dict:
    path = path.resolve()
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return {"path": str(path), "sha256": digest.hexdigest(), "size": size}


def write_receipt(path: Path, receipt: dict) -> None:
    """Replace only complete JSON; leave the previous receipt on any failure."""
    path.parent.mkdir(parents=True, exist_ok=True)
    receipt["updated_at"] = now()
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                         prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            json.dump(receipt, handle, indent=2, sort_keys=True)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def add_check(receipt: dict, name: str, status: str, required: bool,
              detail: str, exit_code: int | None = None) -> None:
    entry = {"name": name, "status": status, "required": required,
             "detail": detail, "recorded_at": now()}
    if exit_code is not None:
        entry["exit_code"] = exit_code
    receipt["checks"].append(entry)
    receipt["last_stage"] = name


def profile(root: Path) -> dict:
    effective: dict[str, int | None] = {}
    origins = {}
    files = {}
    unresolved = []
    for relative in PROFILE_FILES:
        path = root / relative
        if not path.is_file():
            files[relative] = {"status": "unavailable"}
            continue
        files[relative] = identity(path)
        for line_number, line in enumerate(path.read_text().splitlines(), 1):
            match = FLAG_ASSIGNMENT.match(line.split(";", 1)[0])
            if not match:
                continue
            name, expression = match.groups()
            value = None
            if LITERAL.fullmatch(expression):
                value = int(expression[1:], 16) if expression.startswith("$") else int(
                    expression, 16 if expression.lower().startswith("0x") else 10)
            else:
                unresolved.append({"name": name, "expression": expression,
                                   "file": relative, "line": line_number})
            effective[name] = value
            origins[name] = {"file": relative, "line": line_number}
    return {"method": "literal_assignments_in_default_then_override_order",
            "files": files, "effective_flags": effective, "origins": origins,
            "unresolved_assignments": unresolved,
            "limitation": "Not an Asar evaluator; nonliteral values are null, not guessed."}


def source_snapshot(root: Path, receipt_path: Path) -> dict:
    files = {}
    candidates = [path for pattern in ROOT_GLOBS for path in root.glob(pattern)]
    for relative in SOURCE_DIRS:
        directory = root / relative
        if directory.exists():
            candidates.extend(directory.rglob("*"))
    for path in sorted(candidates):
        relative = path.relative_to(root)
        # The runtime runner writes tests/screenshots on case-insensitive Macs;
        # omit just this generated directory, not PNG fixture inputs elsewhere.
        if len(relative.parts) >= 2 and tuple(part.casefold() for part in relative.parts[:2]) == ("tests", "screenshots"):
            continue
        if any(part in EXCLUDED_DIRS for part in relative.parts):
            continue
        if path.suffix.lower() in EXCLUDED_SUFFIXES or not path.is_file():
            continue
        if path.resolve() == receipt_path.resolve():
            continue
        item = identity(path)
        # The aggregate has no absolute paths or timestamps, so equivalent
        # isolated roots have the same digest. Incbin assets are included.
        files[relative.as_posix()] = {"sha256": item["sha256"], "size": item["size"]}
    if not files or "Oracle_main.asm" not in files:
        raise ValueError("Source snapshot requires Oracle_main.asm and a nonempty source tree")
    canonical = json.dumps(files, sort_keys=True, separators=(",", ":")).encode()
    return {"method": "conservative_source_tree_v1", "captured_at": now(),
            "included_directories": list(SOURCE_DIRS),
            "included_root_globs": list(ROOT_GLOBS),
            "excluded_directories": sorted(EXCLUDED_DIRS),
            "excluded_suffixes": sorted(EXCLUDED_SUFFIXES),
            "generated_output_directories_case_insensitive": list(GENERATED_OUTPUT_DIRS),
            "scope_note": "Includes inactive source and assets; not exact include reachability. "
                          "Roms, Docs, .context and build outputs are outside this source scope.",
            "files": files, "file_count": len(files),
            "aggregate_sha256": hashlib.sha256(canonical).hexdigest(),
            "profile": profile(root)}


def verify_identity(item: dict) -> str | None:
    if "sha256" not in item:
        return "No recorded file identity"
    try:
        actual = identity(Path(item["path"]))
    except OSError as error:
        return str(error)
    if actual["sha256"] != item["sha256"] or actual["size"] != item["size"]:
        return "File changed after its identity was recorded"
    return None


def verify_source_identity(receipt: dict, receipt_path: Path) -> str | None:
    snapshot = receipt["snapshots"].get("pre_assembly")
    if snapshot is None:
        return None  # The caller records whether this stage was required/reached.
    try:
        current = source_snapshot(Path(receipt["root"]), receipt_path)["files"]
    except (OSError, ValueError) as error:
        return str(error)
    changes = []
    for relative in sorted(set(snapshot["files"]) | set(current)):
        before = snapshot["files"].get(relative)
        after = current.get(relative)
        if before == after:
            continue
        if relative in RESTORABLE_FLAGS:
            initial = receipt["initial_profile"]["files"].get(relative, {})
            if after is None and initial.get("status") == "unavailable":
                continue  # A temporarily created override was removed again.
            if after and all(after.get(key) == initial.get(key) for key in ("sha256", "size")):
                continue
        changes.append(relative)
    if changes:
        return f"Source inputs changed after pre_assembly ({len(changes)}): " + ", ".join(changes[:8])
    return None


def run(args: argparse.Namespace) -> int:
    path = args.receipt.resolve()
    if args.command == "init":
        root = args.root.resolve()
        guard_receipt_destination(path, root, args.base_rom, args.version)
        receipt = {"schema_version": SCHEMA_VERSION, "state": "in_progress",
                   "started_at": now(), "root": str(root), "version": args.version,
                   "requested_profile": args.requested_profile,
                   "assembler_requested": args.assembler, "last_stage": "init",
                   "checks": [], "artifacts": {}, "tools": {}, "snapshots": {},
                   "initial_profile": profile(root),
                   "evidence_scope": "Recorded inputs and check outcomes only; no implicit runtime or release qualification."}
        try:
            receipt["base_rom"] = identity(args.base_rom)
        except OSError as error:
            receipt["base_rom"] = {"path": str(args.base_rom.resolve()), "status": "unavailable"}
            add_check(receipt, "base_rom", "unavailable", True, str(error))
        write_receipt(path, receipt)
        return 0

    receipt = json.loads(path.read_text())
    if receipt.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("Unsupported receipt schema")
    if args.command == "check":
        add_check(receipt, args.name, args.status, bool(args.required), args.detail, args.exit_code)
    elif args.command in ("artifact", "tool"):
        collection = "artifacts" if args.command == "artifact" else "tools"
        try:
            receipt[collection][args.name] = {**identity(args.path), "recorded_at": now()}
        except OSError as error:
            receipt[collection][args.name] = {"path": str(args.path.resolve()), "status": "unavailable"}
            add_check(receipt, f"{args.command}:{args.name}", "unavailable", True, str(error))
            write_receipt(path, receipt)
            return 1
        receipt["last_stage"] = f"{args.command}:{args.name}"
    elif args.command == "snapshot":
        # Do not overwrite a phase after a trap restores flags or source changes.
        if args.phase in receipt["snapshots"]:
            raise ValueError(f"Snapshot phase already recorded: {args.phase}")
        snapshot = source_snapshot(Path(receipt["root"]), path)
        receipt["snapshots"][args.phase] = snapshot
        error = verify_identity(receipt["base_rom"])
        if error:
            add_check(receipt, "base_rom_snapshot_identity", "failed", True, error)
            write_receipt(path, receipt)
            return 1
        receipt["last_stage"] = args.phase
    elif args.command == "finish":
        if args.exit_code == 0 and "pre_assembly" not in receipt["snapshots"]:
            add_check(receipt, "source_snapshot", "unavailable", True,
                      "Successful build requires a pre_assembly source snapshot")
        # Source snapshots stay immutable; exact restoration to initial flag
        # bytes is allowed, but an unrelated source edit invalidates identity.
        source_error = verify_source_identity(receipt, path)
        if source_error:
            add_check(receipt, "source_snapshot_identity", "failed", True, source_error)
        for name, item in [("base_rom", receipt["base_rom"])] + [
                (f"{kind}:{name}", item) for kind in ("artifacts", "tools")
                for name, item in receipt[kind].items()]:
            error = verify_identity(item)
            if error:
                add_check(receipt, f"identity:{name}", "failed", True, error)
        gaps = [check for check in receipt["checks"] if check["status"] != "passed"]
        required_gaps = [check for check in gaps if check["required"]]
        final_exit = args.exit_code or (1 if required_gaps else 0)
        receipt.update({"state": "failed" if final_exit else (
                            "completed_with_gaps" if gaps else "completed"),
                        "finished_at": now(), "last_stage": args.stage,
                        "source_snapshot_status": "captured" if "pre_assembly" in receipt["snapshots"] else "not_reached",
                        "finish": {"stage": args.stage, "supplied_exit_code": args.exit_code,
                                   "exit_code": final_exit,
                                   "required_gaps": [check["name"] for check in required_gaps],
                                   "optional_gaps": [check["name"] for check in gaps if not check["required"]]}})
        write_receipt(path, receipt)
        return final_exit
    write_receipt(path, receipt)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "check", "artifact", "tool", "snapshot", "finish"):
        command = commands.add_parser(name)
        command.add_argument("--receipt", type=Path, required=True)
        if name == "init":
            command.add_argument("--root", type=Path, required=True)
            command.add_argument("--base-rom", type=Path, required=True)
            for option in ("version", "requested-profile", "assembler"):
                command.add_argument(f"--{option}", required=True)
        elif name == "check":
            command.add_argument("--name", required=True)
            command.add_argument("--status", choices=("passed", "failed", "unavailable", "skipped"), required=True)
            command.add_argument("--required", type=int, choices=(0, 1), required=True)
            command.add_argument("--detail", required=True)
            command.add_argument("--exit-code", type=int)
        elif name in ("artifact", "tool"):
            command.add_argument("--name", required=True)
            command.add_argument("--path", type=Path, required=True)
        elif name == "snapshot":
            command.add_argument("--phase", choices=("pre_assembly",), required=True)
        else:
            command.add_argument("--exit-code", type=int, required=True)
            command.add_argument("--stage", required=True)
    args = parser.parse_args(argv)
    try:
        return run(args)
    except (OSError, ValueError, KeyError) as error:
        print(f"build_receipt: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
