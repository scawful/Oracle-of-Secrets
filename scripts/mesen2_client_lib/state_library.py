"""Save state library helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from .paths import LIBRARY_ROOT, MANIFEST_PATH


class StateLibrary:
    """Handles manifest lookups and file resolution for the save state library."""

    def __init__(self, manifest_path: Path = MANIFEST_PATH, library_root: Path = LIBRARY_ROOT):
        self.manifest_path = Path(manifest_path)
        self.library_root = Path(library_root)

    def get_manifest(self) -> dict:
        """Load the save state library manifest."""
        if self.manifest_path.exists():
            return json.loads(self.manifest_path.read_text())
        return {"version": 1, "entries": [], "sets": []}

    def find_entry(self, state_id: str) -> Optional[dict]:
        """Find a state entry by ID in the library manifest."""
        manifest = self.get_manifest()
        for entry in manifest.get("entries", []):
            if entry.get("id") == state_id:
                return entry
        return None

    def list_entries(self, tag: Optional[str] = None) -> list[dict]:
        """List all entries in the library, optionally filtered by tag."""
        manifest = self.get_manifest()
        entries = manifest.get("entries", [])
        if tag:
            entries = [e for e in entries if tag in e.get("tags", [])]
        return entries

    def resolve_path(self, entry: dict) -> Path:
        """Resolve the full state file path for a manifest entry."""
        # Support both "path" (legacy) and "state_path" (new format)
        state_path = entry.get("path") or entry.get("state_path")
        if not state_path:
            raise ValueError(f"State '{entry.get('id', '?')}' has no path")

        # Check if state_path is absolute or relative
        path_obj = Path(state_path)
        if path_obj.is_absolute():
            full_path = path_obj
        else:
            full_path = self.library_root.parent.parent.parent / state_path

        if not full_path.exists():
            raise ValueError(f"State file not found: {full_path}")

        return full_path

    def load_state(self, bridge, state_id: str) -> bool:
        """Load a save state from the library by ID."""
        entry = self.find_entry(state_id)
        if not entry:
            raise ValueError(f"State '{state_id}' not found in library")

        full_path = self.resolve_path(entry)
        return bridge.load_state(path=str(full_path))

    def get_sets(self) -> list[dict]:
        """List all state sets in the library."""
        manifest = self.get_manifest()
        return manifest.get("sets", [])
