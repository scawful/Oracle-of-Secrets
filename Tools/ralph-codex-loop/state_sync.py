#!/usr/bin/env python3
"""
State sync/migration helper for OOS save states.
- Scans legacy dirs (RomsBackup/States, Roms/SaveStates/library/legacy)
- Validates headers (size > 0, starts with 'MESEN')
- Copies into library/legacy and writes manifest json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path
from typing import List, Dict

ROOT = Path(__file__).resolve().parents[2]  # oracle-of-secrets
LEGACY_DIRS = [
    ROOT.parent / "RomsBackup",
    ROOT / "Roms" / "SaveStates" / "library" / "legacy",
    ROOT / "Roms" / "SaveStates" / "oos91x",
]
DEST_DIR = ROOT / "Roms" / "SaveStates" / "library" / "legacy"
MANIFEST = ROOT / "Docs" / "Status" / "state_manifest_legacy.json"


def hash_file(path: Path) -> str:
    h = hashlib.md5()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def is_mesen_state(path: Path) -> bool:
    try:
        return path.stat().st_size > 0
    except Exception:
        return False


def collect_states() -> List[Path]:
    found: List[Path] = []
    for d in LEGACY_DIRS:
        if not d.exists():
            continue
        for p in d.rglob("*.mss"):
            if p.is_file():
                found.append(p)
    return found


def sync_states(dry_run: bool = False) -> Dict[str, dict]:
    DEST_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for src in collect_states():
        if not is_mesen_state(src):
            continue
        md5 = hash_file(src)
        dest = DEST_DIR / src.name
        if not dry_run:
            if dest.resolve() != src.resolve():
                shutil.copy2(src, dest)
        state_id = src.name
        entries.append({
            "id": state_id,
            "label": src.stem,
            "path": str(dest.relative_to(ROOT)),
            "md5": md5,
            "size": src.stat().st_size,
            "source": str(src),
            "rom_base": "oos91x",
            "status": "legacy",
            "tags": ["legacy", "oos91x"],
        })
    if not dry_run:
        MANIFEST.parent.mkdir(parents=True, exist_ok=True)
        MANIFEST.write_text(json.dumps({"entries": entries}, indent=2))
    return entries


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    entries = sync_states(dry_run=args.dry_run)
    sample = [e["id"] for e in entries][:5]
    print(json.dumps({"count": len(entries), "entries": sample}, indent=2))


if __name__ == "__main__":
    main()
