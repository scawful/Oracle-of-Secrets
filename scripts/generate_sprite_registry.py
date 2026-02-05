#!/usr/bin/env python3
"""Sprite registry manifest tooling.

- Extract Sprite_* ID definitions from Sprites/all_sprites.asm into Sprites/registry.csv
- Emit Sprites/sprite_registry_ids.asm from Sprites/registry.csv
"""
from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

SPRITE_DEF_RE = re.compile(r"^\s*(Sprite_[A-Za-z0-9_]+)\s*=\s*\$([0-9A-Fa-f]{2})\b\s*(?:;\s*(.*))?$")
LOG_START_RE = re.compile(r"^\s*%log_start\(\"([^\"]+)\"")
LOG_END_RE = re.compile(r"^\s*%log_end\(\"([^\"]+)\"")
INCSRC_RE = re.compile(r"^\s*incsrc\s+\"([^\"]+)\"")

DEFAULT_ASM = Path("Sprites/all_sprites.asm")
DEFAULT_CSV = Path("Sprites/registry.csv")
DEFAULT_IDS = Path("Sprites/sprite_registry_ids.asm")


def _parse_hex(token: str) -> int | None:
    token = token.strip()
    if not token:
        return None
    if token.startswith("$"):
        token = "0x" + token[1:]
    try:
        return int(token, 0)
    except ValueError:
        return None


def extract_registry(asm_path: Path) -> list[dict]:
    entries: list[dict] = []
    current_group: str | None = None
    current_entries: list[dict] = []
    current_paths: list[str] = []

    def flush() -> None:
        nonlocal current_entries, current_paths
        if not current_entries:
            current_entries = []
            current_paths = []
            return
        paths = ";".join(current_paths)
        for entry in current_entries:
            entry["paths"] = paths
            entry["group"] = current_group or ""
            entries.append(entry)
        current_entries = []
        current_paths = []

    for line in asm_path.read_text(errors="ignore").splitlines():
        log_start = LOG_START_RE.match(line)
        if log_start:
            flush()
            current_group = log_start.group(1)
            continue

        log_end = LOG_END_RE.match(line)
        if log_end:
            flush()
            current_group = None
            continue

        incsrc = INCSRC_RE.match(line)
        if incsrc:
            current_paths.append(incsrc.group(1))
            continue

        sprite_def = SPRITE_DEF_RE.match(line)
        if sprite_def:
            name = sprite_def.group(1)
            sprite_id = sprite_def.group(2).upper()
            note = sprite_def.group(3) or ""
            current_entries.append({
                "name": name,
                "id": f"${sprite_id}",
                "paths": "",
                "group": current_group or "",
                "notes": note.strip(),
                "allow_dupe": "",
            })

    flush()
    return entries


def write_registry(entries: list[dict], csv_path: Path) -> None:
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    with csv_path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["name", "id", "paths", "group", "notes", "allow_dupe"])
        writer.writeheader()
        for entry in entries:
            writer.writerow(entry)


def load_registry(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def emit_ids(registry: list[dict], out_path: Path) -> None:
    lines = [
        "; Auto-generated from Sprites/registry.csv",
        "; Do not edit by hand.",
        "",
    ]
    seen_names: dict[str, int] = {}
    for row in registry:
        name = (row.get("name") or "").strip()
        sprite_id = (row.get("id") or "").strip()
        note = (row.get("notes") or "").strip()
        if not name or not sprite_id:
            continue
        value = _parse_hex(sprite_id)
        if value is None:
            raise ValueError(f"Invalid sprite id '{sprite_id}' for {name}")
        if name in seen_names and seen_names[name] != value:
            raise ValueError(f"Sprite name '{name}' has conflicting IDs: {seen_names[name]:02X} vs {value:02X}")
        seen_names[name] = value
        line = f"{name} = ${value:02X}"
        if note:
            line += f" ; {note}"
        lines.append(line)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text("\n".join(lines) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate sprite registry files")
    parser.add_argument("--extract", action="store_true", help="Extract registry.csv from Sprites/all_sprites.asm")
    parser.add_argument("--emit-ids", action="store_true", help="Emit Sprites/sprite_registry_ids.asm from registry.csv")
    parser.add_argument("--asm", type=Path, default=DEFAULT_ASM, help="Path to Sprites/all_sprites.asm")
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV, help="Path to Sprites/registry.csv")
    parser.add_argument("--out", type=Path, default=DEFAULT_IDS, help="Output ASM path for sprite IDs")
    args = parser.parse_args()

    if not args.extract and not args.emit_ids:
        parser.error("At least one of --extract or --emit-ids is required.")

    if args.extract:
        entries = extract_registry(args.asm)
        write_registry(entries, args.csv)
        print(f"Wrote {len(entries)} registry entries to {args.csv}")

    if args.emit_ids:
        registry = load_registry(args.csv)
        emit_ids(registry, args.out)
        print(f"Wrote sprite IDs to {args.out}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
