#!/usr/bin/env python3
"""Validate Sprites/registry.csv and generated IDs.

Checks:
- Sprite IDs are valid hex and within bounds (<= $F2)
- Duplicate IDs require allow_dupe flag
- Generated sprite_registry_ids.asm matches registry
"""
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import tempfile
from pathlib import Path

DEFAULT_REGISTRY = Path("Sprites/registry.csv")
DEFAULT_IDS = Path("Sprites/sprite_registry_ids.asm")


def _parse_id(value: str) -> int | None:
    token = (value or "").strip()
    if not token:
        return None
    if token.startswith("$"):
        token = "0x" + token[1:]
    try:
        return int(token, 0)
    except ValueError:
        return None


def _truthy(value: str) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "y"}


def _load_registry(path: Path) -> list[dict]:
    with path.open(newline="") as handle:
        reader = csv.DictReader(handle)
        return [row for row in reader]


def _check_ids(registry: list[dict], strict: bool) -> int:
    errors = 0
    warnings = 0

    seen_names: dict[str, int] = {}
    ids_to_rows: dict[int, list[dict]] = {}

    for row in registry:
        name = (row.get("name") or "").strip()
        value = (row.get("id") or "").strip()
        if not name:
            warnings += 1
            print("[warn] missing sprite name")
            continue
        sprite_id = _parse_id(value)
        if sprite_id is None:
            errors += 1
            print(f"[error] {name}: invalid id '{value}'")
            continue
        if sprite_id > 0xF2:
            errors += 1
            print(f"[error] {name}: id ${sprite_id:02X} exceeds $F2")
        if name in seen_names and seen_names[name] != sprite_id:
            errors += 1
            print(f"[error] {name}: conflicting ids ${seen_names[name]:02X} vs ${sprite_id:02X}")
        seen_names[name] = sprite_id
        ids_to_rows.setdefault(sprite_id, []).append(row)

    for sprite_id, rows in sorted(ids_to_rows.items()):
        if len(rows) <= 1:
            continue
        allowed = all(_truthy(row.get("allow_dupe", "")) for row in rows)
        if allowed:
            continue
        msg = f"[warn] duplicate id ${sprite_id:02X}: {', '.join(row.get('name','') for row in rows)}"
        if strict:
            errors += 1
            print(msg.replace("[warn]", "[error]"))
        else:
            warnings += 1
            print(msg)

    if warnings and not strict:
        print(f"[warn] {warnings} warning(s) in sprite registry")
    return errors


def _check_ids_file(registry_csv: Path, ids_path: Path) -> bool:
    script = Path("scripts/generate_sprite_registry.py")
    if not script.exists():
        print(f"[error] {script} not found")
        return False
    with tempfile.NamedTemporaryFile(prefix="sprite_ids_", suffix=".asm", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        cmd = [sys.executable, str(script), "--emit-ids", "--csv", str(registry_csv), "--out", str(temp_path)]
        subprocess.run(cmd, check=True)
        generated = temp_path.read_text()
        existing = ids_path.read_text() if ids_path.exists() else ""
        if generated != existing:
            print("[error] Sprites/sprite_registry_ids.asm is out of date (re-run generate_sprite_registry.py --emit-ids)")
            return False
        return True
    finally:
        temp_path.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate sprite registry")
    parser.add_argument("--registry", type=Path, default=DEFAULT_REGISTRY, help="Path to registry.csv")
    parser.add_argument("--ids", type=Path, default=DEFAULT_IDS, help="Path to sprite_registry_ids.asm")
    parser.add_argument("--strict", action="store_true", help="Treat duplicate IDs as errors unless allow_dupe is set")
    parser.add_argument("--no-ids", action="store_true", help="Skip ids file check")
    args = parser.parse_args()

    if not args.registry.exists():
        print(f"[error] registry not found: {args.registry}")
        return 1

    registry = _load_registry(args.registry)
    errors = _check_ids(registry, args.strict)

    if not args.no_ids:
        if not _check_ids_file(args.registry, args.ids):
            errors += 1

    if errors:
        print(f"[error] {errors} error(s) in sprite registry")
        return 1

    print("sprite registry OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
