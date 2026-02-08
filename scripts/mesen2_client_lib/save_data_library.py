"""Save-data library helpers (WRAM savefile mirror snapshots).

This is intentionally analogous to the save-state library, but stores the
active savefile block from WRAM ($7EF000-$7EF4FF) as a binary blob.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from .paths import SAVE_DATA_LIBRARY_ROOT, SAVE_DATA_MANIFEST_PATH
from .save_data_io import read_savefile_bytes, write_savefile_bytes
from .state_library import compute_file_hash


STATUS_DRAFT = "draft"
STATUS_CANON = "canon"
STATUS_DEPRECATED = "deprecated"

CAPTURED_BY_HUMAN = "human"
CAPTURED_BY_AGENT = "agent"


class SaveDataLibrary:
    """Manages a library of save-data snapshots and a JSON manifest."""

    def __init__(
        self,
        manifest_path: Path = SAVE_DATA_MANIFEST_PATH,
        library_root: Path = SAVE_DATA_LIBRARY_ROOT,
    ):
        self.manifest_path = Path(manifest_path)
        self.library_root = Path(library_root)
        self.library_root.mkdir(parents=True, exist_ok=True)

    def get_manifest(self) -> dict:
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except json.JSONDecodeError:
                pass
        return {
            "version": 1,
            "library_root": str(self.library_root.relative_to(self.manifest_path.parents[2])),
            "entries": [],
            "sets": [],
        }

    def save_manifest(self, manifest: dict) -> None:
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def find_entry(self, entry_id: str) -> Optional[dict]:
        manifest = self.get_manifest()
        for entry in manifest.get("entries", []):
            if entry.get("id") == entry_id:
                return entry
        return None

    def list_entries(self, tag: Optional[str] = None, status: Optional[str] = None) -> list[dict]:
        manifest = self.get_manifest()
        entries = manifest.get("entries", [])
        if tag:
            entries = [e for e in entries if tag in e.get("tags", [])]
        if status:
            entries = [e for e in entries if e.get("status", STATUS_DRAFT) == status]
        return entries

    def resolve_path(self, entry: dict) -> Path:
        rel = entry.get("path") or entry.get("save_path")
        if not rel:
            raise ValueError(f"Save-data entry '{entry.get('id', '?')}' has no path")
        p = Path(rel)
        if p.is_absolute():
            full = p
        else:
            full = self.library_root / p
        if not full.exists():
            raise ValueError(f"Save-data file not found: {full}")
        return full

    def save_current(
        self,
        bridge,
        *,
        label: str,
        metadata: Dict[str, Any] | None = None,
        tags: List[str] | None = None,
        captured_by: str = CAPTURED_BY_AGENT,
        check_duplicates: bool = True,
    ) -> tuple[str, list[str]]:
        warnings: list[str] = []
        timestamp = int(time.time())
        clean_label = "".join(c if c.isalnum() else "_" for c in label).strip("_") or "save"
        entry_id = f"{timestamp}_{clean_label}"
        filename = f"oos_save_{entry_id}.bin"
        full_path = self.library_root / filename

        blob = read_savefile_bytes(bridge)
        full_path.write_bytes(blob)
        md5 = compute_file_hash(full_path)

        if check_duplicates:
            dups = self.find_entries_by_hash(md5)
            if dups:
                warnings.append("DUPLICATE: save-data matches: " + ", ".join(d["id"] for d in dups))

        manifest = self.get_manifest()
        entry: dict[str, Any] = {
            "id": entry_id,
            "label": label,
            "created_at": timestamp,
            "captured_by": captured_by,
            "status": STATUS_DRAFT,
            "md5": md5,
            "path": filename,
            "metadata": metadata or {},
            "tags": tags or [],
        }
        manifest.setdefault("entries", []).insert(0, entry)
        self.save_manifest(manifest)
        return entry_id, warnings

    def find_entries_by_hash(self, md5: str) -> list[dict]:
        manifest = self.get_manifest()
        return [e for e in manifest.get("entries", []) if e.get("md5") == md5]

    def load_into_wram(self, bridge, entry_id: str) -> bool:
        entry = self.find_entry(entry_id)
        if not entry:
            raise ValueError(f"Save-data entry '{entry_id}' not found in manifest")
        full_path = self.resolve_path(entry)
        blob = full_path.read_bytes()
        write_savefile_bytes(bridge, blob)
        return True

    def load_from_path(self, bridge, path: Path) -> bool:
        blob = Path(path).read_bytes()
        write_savefile_bytes(bridge, blob)
        return True

