#!/usr/bin/env python3
"""Save-state library manager for Oracle of Secrets.

Stores .mss files in a local library and tracks metadata in a manifest.
The ROM assets remain local (Roms/ is gitignored); the manifest is tracked.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = REPO_ROOT / "Docs" / "Testing" / "save_state_library.json"
DEFAULT_LIBRARY_ROOT = "Roms/SaveStates/library"

def _default_mesen_root() -> Path:
    env_home = os.getenv("MESEN2_HOME")
    if env_home:
        return Path(env_home).expanduser()

    candidates = [
        Path.home() / "Documents" / "Mesen2",
        Path.home() / "Library" / "Application Support" / "Mesen2",
        Path.home() / ".config" / "mesen2",
        Path.home() / ".config" / "Mesen2",
    ]

    for candidate in candidates:
        if (candidate / "SaveStates").exists():
            return candidate

    for candidate in candidates:
        if candidate.exists():
            return candidate

    return Path.home() / "Documents" / "Mesen2"


DEFAULT_MESEN_ROOT = _default_mesen_root()
DEFAULT_MESEN_STATES = DEFAULT_MESEN_ROOT / "SaveStates"
DEFAULT_MESEN_SAVES = DEFAULT_MESEN_ROOT / "Saves"
DEFAULT_MESEN_CLI = REPO_ROOT / "scripts" / "mesen_cli.sh"


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
        data = json.loads(path.read_text())
    else:
        data = {
            "version": 1,
            "library_root": DEFAULT_LIBRARY_ROOT,
            "entries": [],
        }
    data.setdefault("sets", [])
    return data


def _save_manifest(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n")


def _resolve_state_path(entry: dict, manifest: dict) -> Path | None:
    path_str = entry.get("state_path") or entry.get("path") or ""
    if not path_str:
        return None
    path = Path(path_str)
    if path.is_absolute():
        return path
    if entry.get("state_path"):
        return (REPO_ROOT / path).resolve()
    library_root = Path(manifest.get("library_root", DEFAULT_LIBRARY_ROOT))
    return (REPO_ROOT / library_root / path).resolve()


def _find_entry(entries: list[dict], state_id: str) -> dict | None:
    for entry in entries:
        if entry.get("id") == state_id:
            return entry
    return None


def _find_set(sets: list[dict], name: str) -> dict | None:
    for entry in sets:
        if entry.get("name") == name:
            return entry
    return None


def _parse_slot_spec(raw: str) -> tuple[int, str]:
    if ":" not in raw:
        raise SystemExit(f"Invalid slot spec '{raw}' (expected slot:id)")
    slot_str, state_id = raw.split(":", 1)
    try:
        slot = int(slot_str)
    except ValueError as exc:
        raise SystemExit(f"Invalid slot '{slot_str}' in '{raw}'") from exc
    if slot < 1 or slot > 10:
        raise SystemExit(f"Slot {slot} out of range (1-10)")
    state_id = state_id.strip()
    if not state_id:
        raise SystemExit(f"Missing state id in '{raw}'")
    return slot, state_id


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [tag.strip() for tag in raw.split(",") if tag.strip()]

def _normalize_tags(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(tag).strip() for tag in value if str(tag).strip()]
    if isinstance(value, str):
        return _parse_tags(value)
    return [str(value).strip()]


def _ensure_path(path_str: str, label: str) -> Path:
    path = Path(path_str).expanduser()
    if not path.exists():
        raise SystemExit(f"{label} not found: {path}")
    return path


def _load_slot_meta(path_str: str | None) -> dict:
    if not path_str:
        return {}
    path = _ensure_path(path_str, "Slot metadata file")
    suffix = path.suffix.lower()
    if suffix in (".yaml", ".yml"):
        try:
            import yaml  # type: ignore
        except Exception as exc:
            raise SystemExit(f"PyYAML not available for {path}: {exc}") from exc
        data = yaml.safe_load(path.read_text()) or {}
    else:
        try:
            data = json.loads(path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise SystemExit("Slot metadata file must contain a JSON/YAML object.")
    return data


def _parse_int(value) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value)
    s = str(value).strip()
    if not s:
        return None
    if s.startswith("$"):
        s = "0x" + s[1:]
    try:
        if s.lower().startswith("0x"):
            return int(s, 16)
        return int(s)
    except ValueError:
        return None


def _build_location(meta: dict) -> str | None:
    indoors = meta.get("indoors")
    indoors_val = None
    if isinstance(indoors, bool):
        indoors_val = indoors
    elif isinstance(indoors, str):
        indoors_val = indoors.lower() in ("1", "true", "yes")

    room = _parse_int(meta.get("room"))
    area = _parse_int(meta.get("area"))
    module = meta.get("module")

    if indoors_val is True and room is not None:
        return f"Room 0x{room:02X} (indoors)"
    if indoors_val is False and area is not None:
        return f"Overworld 0x{area:02X}"
    if room is not None:
        return f"Room 0x{room:02X}"
    if area is not None:
        return f"Overworld 0x{area:02X}"
    if module:
        return f"Mode {module}"
    return None


def _build_summary(meta: dict) -> str | None:
    location = meta.get("location") or _build_location(meta)
    link_x = _parse_int(meta.get("link_x"))
    link_y = _parse_int(meta.get("link_y"))
    link_state = _parse_int(meta.get("link_state"))
    parts = []
    if location:
        parts.append(location)
    if link_x is not None and link_y is not None:
        parts.append(f"Link ({link_x},{link_y})")
    if link_state is not None:
        parts.append(f"State 0x{link_state:02X}")
    if parts:
        return " | ".join(parts)
    return None


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
        meta = entry.get("meta", {}) or {}
        label = meta.get("label", "")
        location = meta.get("location", "")
        suffix = " ".join([v for v in [label, location] if v]).strip()
        if suffix:
            desc = f"{desc} ({suffix})" if desc else suffix
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
    if args.label:
        meta["label"] = args.label
    if args.location:
        meta["location"] = args.location
    if args.summary:
        meta["summary"] = args.summary

    if args.state_json:
        state_path = _ensure_path(args.state_json, "State JSON")
        try:
            state_data = json.loads(state_path.read_text())
        except json.JSONDecodeError as exc:
            raise SystemExit(f"Invalid state JSON: {exc}") from exc

        def _set_meta(key: str, value) -> None:
            if value is None:
                return
            if key not in meta or meta[key] in ("", None):
                meta[key] = value

        mode = state_data.get("mode")
        room_id = state_data.get("roomId")
        area = state_data.get("overworldArea")
        link_state = state_data.get("linkState")
        link_x = state_data.get("linkX")
        link_y = state_data.get("linkY")
        indoors = state_data.get("indoors")
        dungeon_scrolls = state_data.get("dungeonScrolls")
        side_quest_prog = state_data.get("sideQuestProg")
        side_quest_prog2 = state_data.get("sideQuestProg2")
        reinit = state_data.get("reinit") if isinstance(state_data.get("reinit"), dict) else None
        reinit_flags = state_data.get("reinitFlags")
        reinit_status = state_data.get("reinitStatus")
        reinit_error = state_data.get("reinitError")
        reinit_seq = state_data.get("reinitSeq")
        reinit_last = state_data.get("reinitLast")

        if isinstance(mode, int):
            _set_meta("module", f"0x{mode:02X}")
        if isinstance(room_id, int):
            _set_meta("room", f"0x{room_id:02X}")
        if isinstance(area, int):
            _set_meta("area", f"0x{area:02X}")
        if isinstance(link_state, int):
            _set_meta("link_state", f"0x{link_state:02X}")
        if isinstance(link_x, int):
            _set_meta("link_x", str(link_x))
        if isinstance(link_y, int):
            _set_meta("link_y", str(link_y))
        if isinstance(indoors, bool):
            _set_meta("indoors", "true" if indoors else "false")
        if isinstance(dungeon_scrolls, int):
            _set_meta("dungeon_scrolls", f"0x{dungeon_scrolls:02X}")
        if isinstance(side_quest_prog, int):
            _set_meta("side_quest_prog", f"0x{side_quest_prog:02X}")
        if isinstance(side_quest_prog2, int):
            _set_meta("side_quest_prog2", f"0x{side_quest_prog2:02X}")

        if "reinit" not in meta:
            reinit_meta = {}
            def _hex_byte(value):
                if isinstance(value, int):
                    return f"0x{value:02X}"
                return None
            if isinstance(reinit, dict):
                for key in ("flags", "status", "error", "seq", "last"):
                    val = reinit.get(key)
                    hexed = _hex_byte(val)
                    if hexed is not None:
                        reinit_meta[key] = hexed
            else:
                hexed = _hex_byte(reinit_flags)
                if hexed is not None:
                    reinit_meta["flags"] = hexed
                hexed = _hex_byte(reinit_status)
                if hexed is not None:
                    reinit_meta["status"] = hexed
                hexed = _hex_byte(reinit_error)
                if hexed is not None:
                    reinit_meta["error"] = hexed
                hexed = _hex_byte(reinit_seq)
                if hexed is not None:
                    reinit_meta["seq"] = hexed
                hexed = _hex_byte(reinit_last)
                if hexed is not None:
                    reinit_meta["last"] = hexed
            if reinit_meta:
                meta["reinit"] = reinit_meta

        # Human-readable auto-summary
        if "location" not in meta:
            loc = _build_location(meta)
            if loc:
                meta["location"] = loc
        if "summary" not in meta:
            summary = _build_summary(meta)
            if summary:
                meta["summary"] = summary

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
    if args.screenshot:
        shot_src = _ensure_path(args.screenshot, "Screenshot")
        shot_dest = dest_dir / f"{state_id}{shot_src.suffix or '.png'}"
        shutil.copy2(shot_src, shot_dest)
        entry["screenshot_path"] = _relpath(shot_dest)
    if args.save_state_json:
        json_src = _ensure_path(args.save_state_json, "State JSON")
        json_dest = dest_dir / f"{state_id}.state.json"
        shutil.copy2(json_src, json_dest)
        entry["state_json_path"] = _relpath(json_dest)
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

    state_path = _resolve_state_path(entry, manifest)
    if not state_path:
        raise SystemExit(f"State entry missing path: {args.id}")
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


def cmd_set_list(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    sets = manifest.get("sets", [])
    if not sets:
        print("No save-state sets in manifest.")
        return
    for entry in sets:
        slots = entry.get("slots", {})
        count = sum(1 for _, value in slots.items() if value)
        desc = entry.get("description", "")
        rom_base = entry.get("rom_base", "")
        print(f"{entry.get('name')}\t{count}/10\t{rom_base}\t{desc}")


def cmd_set_show(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    entry = _find_set(manifest.get("sets", []), args.set)
    if not entry:
        raise SystemExit(f"Set '{args.set}' not found.")
    print(f"Set: {entry.get('name')}")
    desc = entry.get("description", "")
    if desc:
        print(f"Description: {desc}")
    rom_base = entry.get("rom_base", "")
    if rom_base:
        print(f"ROM base: {rom_base}")
    srm_id = entry.get("srm_id")
    if srm_id:
        print(f"SRM source: {srm_id}")
    slots = entry.get("slots", {})
    for slot in range(1, 11):
        state_id = slots.get(str(slot), "")
        print(f"{slot}\t{state_id}")


def cmd_set_create(args) -> None:
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    entries = manifest.get("entries", [])
    sets = manifest.setdefault("sets", [])

    if not args.slot:
        raise SystemExit("Provide at least one --slot spec (e.g. --slot 1:state_id).")

    slots: dict[str, str] = {}
    for raw in args.slot:
        slot, state_id = _parse_slot_spec(raw)
        if str(slot) in slots and not args.force:
            raise SystemExit(f"Duplicate slot {slot} (use --force to overwrite)")
        slots[str(slot)] = state_id

    if not args.allow_partial and len(slots) != 10:
        raise SystemExit("Set must define exactly 10 slots (use --allow-partial to override).")

    missing_ids = []
    bases = set()
    md5s = set()
    for state_id in slots.values():
        entry = _find_entry(entries, state_id)
        if entry:
            base = entry.get("rom_base")
            if base:
                bases.add(base)
            md5 = entry.get("rom_md5")
            if md5:
                md5s.add(md5)
        else:
            missing_ids.append(state_id)

    rom_base = args.rom_base
    rom_md5 = ""
    if args.rom:
        rom_path = _ensure_path(args.rom, "ROM")
        rom_base = rom_base or rom_path.stem
        rom_md5 = _md5(rom_path)
    if not rom_base:
        if len(bases) == 1:
            rom_base = bases.pop()
        else:
            if missing_ids and args.force:
                raise SystemExit("Missing entries require --rom or --rom-base to set rom_base.")
            raise SystemExit("Set spans multiple rom_base values; provide --rom or --rom-base.")

    if not rom_md5:
        if len(md5s) == 1:
            rom_md5 = md5s.pop()

    if args.srm_id:
        srm_entry = _find_entry(entries, args.srm_id)
        if not srm_entry:
            raise SystemExit(f"SRM source id not found: {args.srm_id}")
        if "srm_path" not in srm_entry:
            raise SystemExit(f"SRM source '{args.srm_id}' has no srm_path")

    if missing_ids:
        if not args.force:
            raise SystemExit(f"Unknown state id in set: {missing_ids[0]}")
        for state_id in missing_ids:
            placeholder = {
                "id": state_id,
                "rom_base": rom_base or "",
                "rom_md5": rom_md5 or "",
                "rom_path": _relpath(args.rom) if args.rom else "",
                "slot": "",
                "description": "placeholder",
                "tags": [],
                "state_path": "",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "pending": True,
            }
            entries.append(placeholder)

    new_set = {
        "name": args.set,
        "description": args.description or "",
        "rom_base": rom_base or "",
        "rom_md5": rom_md5 or "",
        "slots": slots,
    }
    if args.srm_id:
        new_set["srm_id"] = args.srm_id

    existing = _find_set(sets, args.set)
    if existing:
        if not args.force:
            raise SystemExit(f"Set '{args.set}' already exists (use --force).")
        sets.remove(existing)
    sets.append(new_set)

    _save_manifest(manifest_path, manifest)
    print(f"Saved set '{args.set}' with {len(slots)} slot(s).")


def cmd_set_apply(args) -> None:
    manifest = _load_manifest(Path(args.manifest))
    entries = manifest.get("entries", [])
    set_entry = _find_set(manifest.get("sets", []), args.set)
    if not set_entry:
        raise SystemExit(f"Set '{args.set}' not found.")

    slots = set_entry.get("slots", {})
    if not slots:
        raise SystemExit(f"Set '{args.set}' has no slots defined.")
    if not args.allow_partial and len(slots) != 10:
        raise SystemExit("Set must define exactly 10 slots (use --allow-partial to override).")

    rom_base = set_entry.get("rom_base")
    rom_md5 = set_entry.get("rom_md5") or ""
    if args.rom:
        rom_path = _ensure_path(args.rom, "ROM")
        rom_base = rom_path.stem
        rom_md5 = _md5(rom_path)

    if not rom_base:
        bases = {(_find_entry(entries, state_id) or {}).get("rom_base") for state_id in slots.values()}
        bases.discard(None)
        if len(bases) == 1:
            rom_base = bases.pop()
        else:
            raise SystemExit("Unable to determine rom_base; provide --rom.")

    mesen_dir = Path(args.mesen_dir).expanduser()
    mesen_dir.mkdir(parents=True, exist_ok=True)

    for slot_str, state_id in slots.items():
        entry = _find_entry(entries, state_id)
        if not entry:
            raise SystemExit(f"Set references unknown state id: {state_id}")
        state_path = _resolve_state_path(entry, manifest)
        if not state_path:
            raise SystemExit(f"State entry missing path: {state_id}")
        if not state_path.exists():
            raise SystemExit(f"State file missing: {state_path}")

        if args.rom and not args.allow_stale:
            stored_md5 = entry.get("rom_md5")
            if stored_md5 and stored_md5 != rom_md5:
                raise SystemExit(f"ROM MD5 mismatch for {state_id} (use --allow-stale).")

        try:
            slot = int(slot_str)
        except ValueError as exc:
            raise SystemExit(f"Invalid slot '{slot_str}' in set '{args.set}'") from exc

        dest = mesen_dir / f"{rom_base}_{slot}.mss"
        if dest.exists() and not args.force:
            raise SystemExit(f"Destination exists: {dest} (use --force)")
        shutil.copy2(state_path, dest)

    srm_id = args.srm_id or set_entry.get("srm_id")
    if srm_id:
        srm_entry = _find_entry(entries, srm_id)
        if not srm_entry:
            raise SystemExit(f"SRM source id not found: {srm_id}")
        srm_path = Path(srm_entry.get("srm_path", ""))
        if not srm_path.is_absolute():
            srm_path = (REPO_ROOT / srm_path).resolve()
        if not srm_path.exists():
            raise SystemExit(f"SRM file missing: {srm_path}")
        mesen_saves = Path(args.mesen_saves_dir).expanduser()
        mesen_saves.mkdir(parents=True, exist_ok=True)
        dest_srm = mesen_saves / f"{rom_base}.srm"
        if dest_srm.exists() and not args.force:
            raise SystemExit(f"Destination exists: {dest_srm} (use --force)")
        shutil.copy2(srm_path, dest_srm)

    print(f"Applied set '{args.set}' to {mesen_dir}")


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
        if entry.get("pending"):
            continue
        state_path = _resolve_state_path(entry, manifest)
        if not state_path:
            print(f"MISSING: {entry.get('id')} -> <no path>")
            error = True
            continue
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


def _mesen_cli(cli_path: Path, *args, timeout: float = 10.0) -> tuple[bool, str]:
    try:
        result = subprocess.run(
            [str(cli_path), *[str(a) for a in args]],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=REPO_ROOT
        )
        output = (result.stdout or "").strip()
        if result.returncode == 0:
            return True, output
        return False, (result.stderr or output or "mesen_cli failed").strip()
    except subprocess.TimeoutExpired:
        return False, "mesen_cli timed out"
    except Exception as exc:
        return False, str(exc)


def cmd_capture(args) -> None:
    rom_path = _ensure_path(args.rom, "ROM")
    rom_base = args.rom_base or rom_path.stem

    cli_path = Path(args.mesen_cli).expanduser()
    if not cli_path.exists():
        raise SystemExit(f"mesen_cli not found: {cli_path}")

    if not args.state and not args.slot:
        raise SystemExit("capture requires --slot (unless --state is provided)")

    if not args.no_save:
        if not args.slot:
            raise SystemExit("capture requires --slot when saving from the bridge")
        ok, out = _mesen_cli(cli_path, "savestate", str(args.slot), timeout=args.wait_save + 2)
        if not ok:
            raise SystemExit(f"Failed to trigger savestate: {out}")
        ok, out = _mesen_cli(cli_path, "wait-save", str(args.wait_save), timeout=args.wait_save + 2)
        if not ok:
            raise SystemExit(f"Save did not complete: {out}")

    state_json_path = args.state_json
    screenshot_path = None
    temp_dir = None
    if args.snapshot or args.screenshot:
        temp_dir = tempfile.TemporaryDirectory()
        snap_dir = Path(temp_dir.name)
        ok, out = _mesen_cli(cli_path, "snapshot", str(snap_dir), timeout=4.0)
        if ok:
            # Parse output for paths
            for line in out.splitlines():
                if line.startswith("State:"):
                    state_json_path = line.split("State:", 1)[1].strip()
                elif line.startswith("Screenshot:"):
                    screenshot_path = line.split("Screenshot:", 1)[1].strip()
        if args.snapshot and not state_json_path:
            state_json_path = str(next(snap_dir.glob("state_*.json"), "")) or ""
        if args.screenshot and not screenshot_path:
            screenshot_path = str(next(snap_dir.glob("shot_*.png"), "")) or ""

    if not state_json_path and not args.no_state_json:
        temp_dir = tempfile.TemporaryDirectory()
        state_json_path = str(Path(temp_dir.name) / f"{args.id}_state.json")
        ok, out = _mesen_cli(cli_path, "state-json", state_json_path, timeout=3.0)
        if not ok:
            state_json_path = ""

    import_args = argparse.Namespace(
        manifest=args.manifest,
        id=args.id,
        rom=str(rom_path),
        rom_base=args.rom_base,
        state=args.state,
        slot=str(args.slot) if args.slot else None,
        mesen_dir=str(Path(args.mesen_dir).expanduser()),
        include_srm=args.include_srm,
        srm=args.srm,
        mesen_saves_dir=str(Path(args.mesen_saves_dir).expanduser()),
        description=args.description or "",
        tags=args.tags,
        module=args.module,
        room=args.room,
        area=args.area,
        link_state=args.link_state,
        progress=args.progress,
        notes=args.notes,
        state_json=state_json_path or "",
        label=args.label,
        location=args.location,
        summary=args.summary,
        screenshot=screenshot_path if args.screenshot or args.snapshot else None,
        save_state_json=state_json_path if args.save_state_json or args.snapshot else None,
        force=args.force,
    )
    try:
        cmd_import(import_args)
    finally:
        if temp_dir is not None:
            temp_dir.cleanup()


def cmd_capture_set(args) -> None:
    manifest_path = Path(args.manifest)
    manifest = _load_manifest(manifest_path)
    sets = manifest.get("sets", [])
    entries = manifest.get("entries", [])

    slots: dict[str, str] = {}
    if args.slot:
        for raw in args.slot:
            slot, state_id = _parse_slot_spec(raw)
            if str(slot) in slots and not args.force:
                raise SystemExit(f"Duplicate slot {slot} (use --force to overwrite)")
            slots[str(slot)] = state_id
    else:
        source_set = args.from_set or args.set
        entry = _find_set(sets, source_set)
        if not entry:
            raise SystemExit(f"Set '{source_set}' not found and no --slot specs provided.")
        slots = entry.get("slots", {})

    if not slots:
        raise SystemExit("capture-set requires slot mappings.")

    if not args.allow_partial and len(slots) != 10:
        raise SystemExit("Set must define exactly 10 slots (use --allow-partial to override).")

    meta = _load_slot_meta(args.slot_meta)
    slot_meta = meta.get("slots", {}) if isinstance(meta.get("slots", {}), dict) else {}
    id_meta = meta.get("ids", {}) if isinstance(meta.get("ids", {}), dict) else {}
    if id_meta:
        missing_meta_ids = [state_id for state_id in id_meta.keys() if state_id not in slots.values() and not _find_entry(entries, state_id)]
        if missing_meta_ids and not args.force:
            raise SystemExit(f"Slot metadata references unknown ids: {missing_meta_ids[0]}")

    # Capture each slot
    for slot_str, state_id in slots.items():
        slot_info = {}
        if slot_str in slot_meta and isinstance(slot_meta[slot_str], dict):
            slot_info = slot_meta[slot_str]
        elif state_id in id_meta and isinstance(id_meta[state_id], dict):
            slot_info = id_meta[state_id]

        if slot_info.get("skip"):
            continue

        if slot_info.get("id"):
            state_id = str(slot_info.get("id"))

        desc = args.description
        if args.description_template:
            try:
                desc = args.description_template.format(slot=slot_str, id=state_id)
            except Exception:
                desc = args.description_template
        if slot_info.get("description"):
            desc = slot_info.get("description")

        tags = args.tags
        if "tags" in slot_info:
            tags = ",".join(_normalize_tags(slot_info.get("tags")))
        elif "tags_extra" in slot_info:
            base = _normalize_tags(tags)
            extra = _normalize_tags(slot_info.get("tags_extra"))
            tags = ",".join(base + extra)

        module = slot_info.get("module", args.module)
        room = slot_info.get("room", args.room)
        area = slot_info.get("area", args.area)
        link_state = slot_info.get("link_state", slot_info.get("linkState", args.link_state))
        progress = slot_info.get("progress", args.progress)
        notes = slot_info.get("notes", args.notes)

        capture_args = argparse.Namespace(
            manifest=args.manifest,
            id=state_id,
            rom=args.rom,
            rom_base=args.rom_base,
            slot=slot_str,
            state=None,
            no_save=args.no_save,
            wait_save=args.wait_save,
            mesen_cli=args.mesen_cli,
            state_json=args.state_json,
            no_state_json=args.no_state_json,
            mesen_dir=args.mesen_dir,
            include_srm=args.include_srm,
            srm=args.srm,
            mesen_saves_dir=args.mesen_saves_dir,
            description=desc or "",
            tags=tags,
            module=module,
            room=room,
            area=area,
            link_state=link_state,
            progress=progress,
            notes=notes,
            label=slot_info.get("label", args.label),
            location=slot_info.get("location", args.location),
            summary=slot_info.get("summary", args.summary),
            screenshot=args.screenshot,
            save_state_json=args.save_state_json,
            snapshot=args.snapshot,
            force=args.force,
        )
        cmd_capture(capture_args)

    if not args.no_set_update:
        set_meta = meta.get("set", {}) if isinstance(meta.get("set", {}), dict) else {}
        set_description = args.set_description or set_meta.get("description", "")
        srm_id = args.srm_id or set_meta.get("srm_id")
        slot_specs = [f"{slot}:{state_id}" for slot, state_id in slots.items()]
        set_args = argparse.Namespace(
            manifest=args.manifest,
            set=args.set,
            slot=slot_specs,
            description=set_description or "",
            rom=args.rom,
            rom_base=args.rom_base,
            srm_id=srm_id,
            allow_partial=args.allow_partial,
            force=True if args.force else False,
        )
        cmd_set_create(set_args)


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
    import_cmd.add_argument("--label", help="Short human-friendly label")
    import_cmd.add_argument("--location", help="Human-readable location string")
    import_cmd.add_argument("--summary", help="Human-readable summary")
    import_cmd.add_argument("--state-json", help="Path to bridge state JSON for auto-metadata")
    import_cmd.add_argument("--screenshot", help="Path to screenshot to store in library")
    import_cmd.add_argument("--save-state-json", help="Path to state JSON to store in library")
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

    capture_cmd = sub.add_parser("capture", help="Capture a live bridge state into the library")
    capture_cmd.add_argument("--id", required=True, help="State identifier (used as filename)")
    capture_cmd.add_argument("--rom", required=True, help="ROM path used to generate the state")
    capture_cmd.add_argument("--rom-base", help="Override ROM base name used for slots")
    capture_cmd.add_argument("--slot", help="Mesen2 slot number (1-10) to save into")
    capture_cmd.add_argument("--state", help="Path to existing .mss file (skip saving)")
    capture_cmd.add_argument("--no-save", action="store_true", help="Do not trigger savestate")
    capture_cmd.add_argument("--wait-save", type=int, default=10, help="Seconds to wait for save")
    capture_cmd.add_argument("--mesen-cli", default=str(DEFAULT_MESEN_CLI))
    capture_cmd.add_argument("--state-json", help="Path to state JSON (skip bridge read)")
    capture_cmd.add_argument("--no-state-json", action="store_true", help="Skip bridge state JSON")
    capture_cmd.add_argument("--mesen-dir", default=str(DEFAULT_MESEN_STATES))
    capture_cmd.add_argument("--include-srm", action="store_true", help="Copy matching .srm")
    capture_cmd.add_argument("--srm", help="Path to .srm file")
    capture_cmd.add_argument("--mesen-saves-dir", default=str(DEFAULT_MESEN_SAVES))
    capture_cmd.add_argument("--description", default="")
    capture_cmd.add_argument("--tags", help="Comma-separated tags")
    capture_cmd.add_argument("--module", help="Module value (hex) at capture")
    capture_cmd.add_argument("--room", help="Room ID (hex) at capture")
    capture_cmd.add_argument("--area", help="Overworld area ID (hex) at capture")
    capture_cmd.add_argument("--link-state", help="Link state (hex) at capture")
    capture_cmd.add_argument("--progress", help="Progress milestone label")
    capture_cmd.add_argument("--notes", help="Extra notes")
    capture_cmd.add_argument("--label", help="Short human-friendly label")
    capture_cmd.add_argument("--location", help="Human-readable location string")
    capture_cmd.add_argument("--summary", help="Human-readable summary")
    capture_cmd.add_argument("--snapshot", action="store_true", help="Capture state JSON + screenshot")
    capture_cmd.add_argument("--screenshot", action="store_true", help="Capture screenshot")
    capture_cmd.add_argument("--save-state-json", action="store_true", help="Store state JSON in library")
    capture_cmd.add_argument("--force", action="store_true")
    capture_cmd.set_defaults(func=cmd_capture)

    capture_set_cmd = sub.add_parser("capture-set", help="Capture a full 10-slot set from a live session")
    capture_set_cmd.add_argument("--set", required=True, help="Set name to create/update")
    capture_set_cmd.add_argument("--slot", action="append", help="Slot spec (e.g. 1:state_id). If omitted, uses existing set mapping.")
    capture_set_cmd.add_argument("--from-set", help="Reuse slot mapping from an existing set")
    capture_set_cmd.add_argument("--rom", required=True, help="ROM path used to generate the state")
    capture_set_cmd.add_argument("--rom-base", help="Override ROM base name used for slots")
    capture_set_cmd.add_argument("--no-save", action="store_true", help="Do not trigger savestate")
    capture_set_cmd.add_argument("--wait-save", type=int, default=10, help="Seconds to wait for save")
    capture_set_cmd.add_argument("--mesen-cli", default=str(DEFAULT_MESEN_CLI))
    capture_set_cmd.add_argument("--state-json", help="Path to state JSON (skip bridge read)")
    capture_set_cmd.add_argument("--no-state-json", action="store_true", help="Skip bridge state JSON")
    capture_set_cmd.add_argument("--mesen-dir", default=str(DEFAULT_MESEN_STATES))
    capture_set_cmd.add_argument("--include-srm", action="store_true", help="Copy matching .srm")
    capture_set_cmd.add_argument("--srm", help="Path to .srm file")
    capture_set_cmd.add_argument("--mesen-saves-dir", default=str(DEFAULT_MESEN_SAVES))
    capture_set_cmd.add_argument("--description", default="", help="Description applied to each state")
    capture_set_cmd.add_argument("--description-template", help="Template for per-state description (supports {slot} {id})")
    capture_set_cmd.add_argument("--tags", help="Comma-separated tags applied to each state")
    capture_set_cmd.add_argument("--slot-meta", help="Per-slot metadata JSON/YAML file")
    capture_set_cmd.add_argument("--module", help="Module value (hex) at capture")
    capture_set_cmd.add_argument("--room", help="Room ID (hex) at capture")
    capture_set_cmd.add_argument("--area", help="Overworld area ID (hex) at capture")
    capture_set_cmd.add_argument("--link-state", help="Link state (hex) at capture")
    capture_set_cmd.add_argument("--progress", help="Progress milestone label")
    capture_set_cmd.add_argument("--notes", help="Extra notes")
    capture_set_cmd.add_argument("--label", help="Short human-friendly label")
    capture_set_cmd.add_argument("--location", help="Human-readable location string")
    capture_set_cmd.add_argument("--summary", help="Human-readable summary")
    capture_set_cmd.add_argument("--snapshot", action="store_true", help="Capture state JSON + screenshot per slot")
    capture_set_cmd.add_argument("--screenshot", action="store_true", help="Capture screenshot per slot")
    capture_set_cmd.add_argument("--save-state-json", action="store_true", help="Store state JSON per slot")
    capture_set_cmd.add_argument("--srm-id", help="State id to source .srm from when creating set")
    capture_set_cmd.add_argument("--set-description", default="", help="Description for the set entry")
    capture_set_cmd.add_argument("--no-set-update", action="store_true", help="Skip updating the set entry")
    capture_set_cmd.add_argument("--allow-partial", action="store_true")
    capture_set_cmd.add_argument("--force", action="store_true")
    capture_set_cmd.set_defaults(func=cmd_capture_set)

    set_list_cmd = sub.add_parser("set-list", help="List save-state sets")
    set_list_cmd.set_defaults(func=cmd_set_list)

    set_show_cmd = sub.add_parser("set-show", help="Show slots for a set")
    set_show_cmd.add_argument("--set", required=True)
    set_show_cmd.set_defaults(func=cmd_set_show)

    set_create_cmd = sub.add_parser("set-create", help="Create or update a set of 10 slots")
    set_create_cmd.add_argument("--set", required=True)
    set_create_cmd.add_argument("--slot", action="append", help="Slot spec (e.g. 1:state_id)")
    set_create_cmd.add_argument("--description", default="")
    set_create_cmd.add_argument("--rom", help="ROM path to lock rom_base/md5")
    set_create_cmd.add_argument("--rom-base", help="Override rom_base")
    set_create_cmd.add_argument("--srm-id", help="State id to source .srm from")
    set_create_cmd.add_argument("--allow-partial", action="store_true")
    set_create_cmd.add_argument("--force", action="store_true")
    set_create_cmd.set_defaults(func=cmd_set_create)

    set_apply_cmd = sub.add_parser("set-apply", help="Apply a set to Mesen2 slots")
    set_apply_cmd.add_argument("--set", required=True)
    set_apply_cmd.add_argument("--rom", help="ROM path to validate MD5")
    set_apply_cmd.add_argument("--mesen-dir", default=str(DEFAULT_MESEN_STATES))
    set_apply_cmd.add_argument("--mesen-saves-dir", default=str(DEFAULT_MESEN_SAVES))
    set_apply_cmd.add_argument("--srm-id", help="Override SRM source id")
    set_apply_cmd.add_argument("--allow-partial", action="store_true")
    set_apply_cmd.add_argument("--allow-stale", action="store_true")
    set_apply_cmd.add_argument("--force", action="store_true")
    set_apply_cmd.set_defaults(func=cmd_set_apply)

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
