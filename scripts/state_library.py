#!/usr/bin/env python3
"""Save-state library manager for Oracle of Secrets.

Stores .mss files in a local library and tracks metadata in a manifest.
The ROM assets remain local (Roms/ is gitignored); the manifest is tracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "Docs" / "Testing" / "save_state_library.json"
DEFAULT_LIBRARY_ROOT = "Roms/SaveStates/library"
DEFAULT_MESEN_STATES = Path.home() / "Documents" / "Mesen2" / "SaveStates"
DEFAULT_MESEN_SAVES = Path.home() / "Documents" / "Mesen2" / "Saves"


def _md5(path: Path) -> str:
    hasher = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


def _relpath(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _load_manifest(path: Path) -> dict:
    if path.exists():
        return json.loads(path.read_text())
    return {
        "version": 1,
        "library_root": DEFAULT_LIBRARY_ROOT,
        "entries": [],
    }


def _save_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _find_entry(entries: list[dict], state_id: str) -> dict | None:
    for entry in entries:
        if entry.get("id") == state_id:
            return entry
    return None


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]


def _ensure_path(path_str: str, label: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    return path


def _resolve_state_source(args, rom_base: str) -> Path:
    if args.state:
        return _ensure_path(args.state, "State file")
    if not args.slot:
        raise SystemExit("Provide --state or --slot to locate a Mesen2 state.")
    mesen_dir = Path(args.mesen_dir).expanduser()
    return _ensure_path(mesen_dir / f"{rom_base}_{args.slot}.mss", "Mesen2 state")


def _resolve_srm_source(args, rom_base: str) -> Path:
    if args.srm:
        return _ensure_path(args.srm, "SRM file")
    mesen_saves_dir = Path(args.mesen_saves_dir).expanduser()
    return _ensure_path(mesen_saves_dir / f"{rom_base}.srm", "Mesen2 SRM")


def cmd_list(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    entries = manifest.get("entries", [])
    if not entries:
        print("No save states in manifest.")
        return
    for entry in entries:
        tags = ",".join(entry.get("tags", []))
        desc = entry.get("description", "")
        print(f"{entry.get('id')}\t{entry.get('rom_base')}\t{entry.get('slot','-')}\t{tags}\t{desc}")


def cmd_import(args) -> None:
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    entries = manifest.setdefault("entries", [])

    rom_path = _ensure_path(args.rom, "ROM")
    rom_base = args.rom_base or rom_path.stem
    rom_md5 = _md5(rom_path)

    state_src = _resolve_state_source(args, rom_base)

    library_root = Path(manifest.get("library_root", DEFAULT_LIBRARY_ROOT))
    dest_dir = (REPO_ROOT / library_root / rom_base).resolve()
    dest_dir.mkdir(parents=True, exist_ok=True)

    state_id = args.id
    if _find_entry(entries, state_id) and not args.force:
        raise SystemExit(f"State '{state_id}' already exists. Use --force to overwrite.")

    dest_state = dest_dir / f"{state_id}.mss"
    shutil.copy2(state_src, dest_state)

    srm_dest = None
    if args.include_srm:
        srm_src = _resolve_srm_source(args, rom_base)
        srm_dest = dest_dir / f"{state_id}.srm"
        shutil.copy2(srm_src, srm_dest)

    meta = {}
    if args.module:
        meta["module"] = args.module
    if args.room:
        meta["room"] = args.room
    if args.area:
        meta["area"] = args.area
    if args.link_state:
        meta["link_state"] = args.link_state
    if args.progress:
        meta["progress"] = args.progress
    if args.notes:
        meta["notes"] = args.notes

    entry = {
        "id": state_id,
        "rom_base": rom_base,
        "rom_md5": rom_md5,
        "rom_path": _relpath(rom_path),
        "slot": args.slot or "",
        "description": args.description or "",
        "tags": _parse_tags(args.tags),
        "state_path": _relpath(dest_state),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "source_state": _relpath(state_src),
    }
    if srm_dest:
        entry["srm_path"] = _relpath(srm_dest)
    if meta:
        entry["meta"] = meta

    existing = _find_entry(entries, state_id)
    if existing:
        entries.remove(existing)
    entries.append(entry)

    _save_manifest(manifest_path, manifest)
    print(f"Imported {state_id} -> {dest_state}")


def cmd_export(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    entry = _find_entry(manifest.get("entries", []), args.id)
    if not entry:
        raise SystemExit(f"State '{args.id}' not found in manifest.")

    rom_base = entry.get("rom_base")
    if not rom_base:
        raise SystemExit("Manifest entry missing rom_base.")

    if args.rom:
        rom_path = _ensure_path(args.rom, "ROM")
        rom_md5 = _md5(rom_path)
        stored_md5 = entry.get("rom_md5")
        if stored_md5 and stored_md5 != rom_md5 and not args.allow_stale:
            raise SystemExit("ROM MD5 mismatch. Use --allow-stale to override.")

    state_path = Path(entry.get("state_path", ""))
    if not state_path.is_absolute():
        state_path = (REPO_ROOT / state_path).resolve()
    if not state_path.exists():
        raise SystemExit(f"State file missing: {state_path}")

    mesen_dir = Path(args.mesen_dir).expanduser()
    mesen_dir.mkdir(parents=True, exist_ok=True)

    slot = args.slot or entry.get("slot")
    if not slot:
        raise SystemExit("No slot specified. Use --slot or set slot in manifest.")

    dest = mesen_dir / f"{rom_base}_{slot}.mss"
    if dest.exists() and not args.force:
        raise SystemExit(f"Destination exists: {dest} (use --force)")
    shutil.copy2(state_path, dest)
    print(f"Exported {entry.get('id')} -> {dest}")


def cmd_verify(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    entries = manifest.get("entries", [])
    if not entries:
        print("No save states in manifest.")
        return

    error = False
    rom_md5 = None
    rom_base = None
    if args.rom:
        rom_path = _ensure_path(args.rom, "ROM")
        rom_md5 = _md5(rom_path)
        rom_base = rom_path.stem

    for entry in entries:
        state_path = Path(entry.get("state_path", ""))
        if not state_path.is_absolute():
            state_path = (REPO_ROOT / state_path).resolve()
        if not state_path.exists():
            print(f"MISSING: {entry.get('id')} -> {state_path}")
            error = True
            continue

        if rom_md5 and entry.get("rom_base") == rom_base:
            stored_md5 = entry.get("rom_md5")
            if stored_md5 and stored_md5 != rom_md5:
                print(f"MD5 MISMATCH: {entry.get('id')} expected {stored_md5}, got {rom_md5}")
                error = True

    if error:
        raise SystemExit(1)
    print("OK: save-state library verified")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Manage Oracle of Secrets save-state library")
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))

    sub = parser.add_subparsers(dest="command", required=True)

    list_cmd = sub.add_parser("list", help="List states in the manifest")
    list_cmd.set_defaults(func=cmd_list)

    import_cmd = sub.add_parser("import", help="Import a Mesen2 state into the library")
    import_cmd.add_argument("--id", required=True, help="State identifier (used as filename)")
    import_cmd.add_argument("--rom", required=True, help="ROM path used to generate the state")
    import_cmd.add_argument("--rom-base", help="Override ROM base name used for slots")
    import_cmd.add_argument("--state", help="Path to .mss file")
    import_cmd.add_argument("--slot", help="Mesen2 slot number (e.g. 1)")
    import_cmd.add_argument("--mesen-dir", default=str(DEFAULT_MESEN_STATES))
    import_cmd.add_argument("--include-srm", action="store_true", help="Copy matching .srm")
    import_cmd.add_argument("--srm", help="Path to .srm file")
    import_cmd.add_argument("--mesen-saves-dir", default=str(DEFAULT_MESEN_SAVES))
    import_cmd.add_argument("--description", default="")
    import_cmd.add_argument("--tags", help="Comma-separated tags")
    import_cmd.add_argument("--module", help="Module value (hex) at capture")
    import_cmd.add_argument("--room", help="Room ID (hex) at capture")
    import_cmd.add_argument("--area", help="Overworld area ID (hex) at capture")
    import_cmd.add_argument("--link-state", help="Link state (hex) at capture")
    import_cmd.add_argument("--progress", help="Progress milestone label")
    import_cmd.add_argument("--notes", help="Extra notes")
    import_cmd.add_argument("--force", action="store_true")
    import_cmd.set_defaults(func=cmd_import)

    export_cmd = sub.add_parser("export", help="Export a library state to Mesen2")
    export_cmd.add_argument("--id", required=True)
    export_cmd.add_argument("--rom", help="ROM path to verify MD5")
    export_cmd.add_argument("--mesen-dir", default=str(DEFAULT_MESEN_STATES))
    export_cmd.add_argument("--slot", help="Override slot number")
    export_cmd.add_argument("--allow-stale", action="store_true")
    export_cmd.add_argument("--force", action="store_true")
    export_cmd.set_defaults(func=cmd_export)

    verify_cmd = sub.add_parser("verify", help="Verify library files and ROM MD5")
    verify_cmd.add_argument("--rom", help="ROM path to validate MD5")
    verify_cmd.set_defaults(func=cmd_verify)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
