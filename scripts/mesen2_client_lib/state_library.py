"""Save state library helpers."""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Optional, List, Dict, Any

from .paths import LIBRARY_ROOT, MANIFEST_PATH

DISALLOWED_STATE_MARKERS = ("spooky", "allhallows", "halloween")
ALLOW_LEGACY_ENV = "OOS_ALLOW_LEGACY_STATES"

# State status constants
STATUS_DRAFT = "draft"
STATUS_CANON = "canon"
STATUS_DEPRECATED = "deprecated"

# Captured by constants
CAPTURED_BY_HUMAN = "human"
CAPTURED_BY_AGENT = "agent"


def compute_file_hash(path: Path) -> str:
    """Compute MD5 hash of a file."""
    md5 = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            md5.update(chunk)
    return md5.hexdigest()


def _legacy_states_allowed() -> bool:
    raw = os.getenv(ALLOW_LEGACY_ENV)
    if raw is None:
        return False
    return raw.strip().lower() in ("1", "true", "yes", "on")


def is_disallowed_state_path(path: Path) -> bool:
    """Return True if the path matches legacy/blocked save state markers."""
    if _legacy_states_allowed():
        return False
    lower = str(path).lower()
    return any(marker in lower for marker in DISALLOWED_STATE_MARKERS)


def disallowed_state_reason(path: Path) -> str:
    return (
        f"Blocked legacy save state: {path} "
        f"(set {ALLOW_LEGACY_ENV}=1 to override)"
    )


class StateLibrary:
    """Handles manifest lookups and file resolution for the save state library."""

    def __init__(self, manifest_path: Path = MANIFEST_PATH, library_root: Path = LIBRARY_ROOT):
        self.manifest_path = Path(manifest_path)
        self.library_root = Path(library_root)
        self.library_root.mkdir(parents=True, exist_ok=True)

    def get_manifest(self) -> dict:
        """Load the save state library manifest."""
        if self.manifest_path.exists():
            try:
                return json.loads(self.manifest_path.read_text())
            except json.JSONDecodeError:
                pass
        return {"version": 1, "entries": [], "sets": []}

    def save_manifest(self, manifest: dict) -> None:
        """Save the manifest to disk."""
        self.manifest_path.write_text(json.dumps(manifest, indent=2))

    def find_entry(self, state_id: str) -> Optional[dict]:
        """Find a state entry by ID in the library manifest."""
        manifest = self.get_manifest()
        for entry in manifest.get("entries", []):
            if entry.get("id") == state_id:
                return entry
        return None

    def list_entries(
        self,
        tag: Optional[str] = None,
        status: Optional[str] = None,
        canon_only: bool = False
    ) -> list[dict]:
        """List all entries in the library, optionally filtered by tag or status.

        Args:
            tag: Filter by tag (e.g., "transition", "baseline")
            status: Filter by status (draft, canon, deprecated)
            canon_only: Shorthand for status="canon"
        """
        manifest = self.get_manifest()
        entries = manifest.get("entries", [])

        if tag:
            entries = [e for e in entries if tag in e.get("tags", [])]

        if canon_only:
            status = STATUS_CANON

        if status:
            entries = [e for e in entries if e.get("status", STATUS_DRAFT) == status]

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
            # If the entry has the modern 'state_path' field, it's relative to REPO_ROOT
            # If it only has the legacy 'path' field, it's relative to library_root
            if entry.get("state_path"):
                # Ideally, resolve relative to repo root, but for now library_root parent logic
                # assumes a specific structure. Fallback to library_root if it looks local.
                if (self.library_root / state_path).exists():
                    full_path = self.library_root / state_path
                else:
                    # Fallback for repo-relative paths (adjust based on project structure)
                    full_path = self.library_root.parent.parent.parent / state_path
            else:
                full_path = self.library_root / state_path

        if not full_path.exists():
            raise ValueError(f"State file not found: {full_path}")

        if is_disallowed_state_path(full_path):
            raise ValueError(disallowed_state_reason(full_path))

        return full_path

    def load_state(
        self,
        bridge,
        state_id: str,
        validate: bool = False,
        strict: bool = False
    ) -> bool:
        """Load a save state from the library by ID.

        Args:
            bridge: MesenBridge instance
            state_id: State ID from manifest
            validate: If True, validate state after loading
            strict: If True, treat validation warnings as errors

        Returns:
            True if load succeeded (and validation passed if enabled)
        """
        entry = self.find_entry(state_id)
        if not entry:
            raise ValueError(f"State '{state_id}' not found in library")

        full_path = self.resolve_path(entry)
        success = bridge.load_state(path=str(full_path))

        if not success:
            return False

        if validate:
            result = self.validate_loaded_state(bridge, entry, state_id)
            if not result.valid:
                return False
            if strict and result.warnings:
                return False

        return True

    def validate_loaded_state(
        self,
        bridge,
        entry: dict,
        state_id: str = ""
    ):
        """Validate a loaded state against its manifest entry.

        Args:
            bridge: MesenBridge instance
            entry: Manifest entry for the state
            state_id: State ID for error messages

        Returns:
            ValidationResult from StateValidator
        """
        from .state_validator import StateValidator

        validator = StateValidator()
        return validator.validate(bridge, entry, state_id)

    def save_labeled_state(
        self,
        bridge,
        label: str,
        metadata: Dict[str, Any] = None,
        tags: List[str] = None,
        captured_by: str = CAPTURED_BY_AGENT,
        check_duplicates: bool = True
    ) -> tuple[str, list[str]]:
        """Save a new state to the library with metadata.

        Args:
            bridge: MesenBridge instance
            label: Human-readable label for the state
            metadata: Optional dictionary of game state metadata
            tags: Optional list of tags for organization
            captured_by: Who captured this state (human or agent)
            check_duplicates: If True, check for duplicate hashes

        Returns:
            Tuple of (state_id, warnings_list)
        """
        warnings = []
        timestamp = int(time.time())
        # Clean label for filename
        clean_label = "".join(c if c.isalnum() else "_" for c in label)
        filename = f"oos_{timestamp}_{clean_label}.mss"
        full_path = self.library_root / filename

        # Save the state via bridge
        if not bridge.save_state(path=str(full_path)):
            raise RuntimeError(f"Failed to save state to {full_path}")

        # Compute hash of the new state
        file_hash = compute_file_hash(full_path)

        # Check for duplicates
        if check_duplicates:
            duplicates = self.find_states_by_hash(file_hash)
            if duplicates:
                dup_ids = [d["id"] for d in duplicates]
                warnings.append(
                    f"DUPLICATE: State matches existing state(s): {', '.join(dup_ids)}"
                )

        # Update manifest
        manifest = self.get_manifest()
        state_id = f"{timestamp}_{clean_label}"

        new_entry = {
            "id": state_id,
            "path": filename,  # Relative to library root
            "label": label,
            "created_at": timestamp,
            "tags": tags or [],
            "metadata": metadata or {},
            # New quality fields
            "status": STATUS_DRAFT,
            "captured_by": captured_by,
            "verified_by": None,
            "verified_at": None,
            "md5": file_hash,
        }

        # Add to entries (prepend for newest first)
        manifest.setdefault("entries", []).insert(0, new_entry)
        self.save_manifest(manifest)

        return state_id, warnings

    def find_states_by_hash(self, file_hash: str) -> list[dict]:
        """Find all states with the given MD5 hash."""
        manifest = self.get_manifest()
        return [
            e for e in manifest.get("entries", [])
            if e.get("md5") == file_hash
        ]

    def verify_state(
        self,
        state_id: str,
        verified_by: str = "scawful"
    ) -> bool:
        """Promote a draft state to canon status.

        Args:
            state_id: ID of the state to verify
            verified_by: Username of the verifier

        Returns:
            True if state was verified, False if not found or already canon
        """
        manifest = self.get_manifest()
        for entry in manifest.get("entries", []):
            if entry.get("id") == state_id:
                current_status = entry.get("status", STATUS_DRAFT)
                if current_status == STATUS_CANON:
                    return False  # Already canon

                entry["status"] = STATUS_CANON
                entry["verified_by"] = verified_by
                entry["verified_at"] = int(time.time())
                self.save_manifest(manifest)
                return True
        return False

    def deprecate_state(self, state_id: str, reason: str = "") -> bool:
        """Mark a state as deprecated.

        Args:
            state_id: ID of the state to deprecate
            reason: Optional reason for deprecation

        Returns:
            True if state was deprecated, False if not found
        """
        manifest = self.get_manifest()
        for entry in manifest.get("entries", []):
            if entry.get("id") == state_id:
                entry["status"] = STATUS_DEPRECATED
                if reason:
                    entry["deprecation_reason"] = reason
                self.save_manifest(manifest)
                return True
        return False

    def backfill_hashes(self) -> int:
        """Compute and store hashes for entries missing md5 field.

        Returns:
            Number of entries updated
        """
        manifest = self.get_manifest()
        updated = 0

        for entry in manifest.get("entries", []):
            if entry.get("md5"):
                continue  # Already has hash

            try:
                full_path = self.resolve_path(entry)
                entry["md5"] = compute_file_hash(full_path)
                updated += 1
            except (ValueError, FileNotFoundError):
                continue  # Skip missing files

        if updated > 0:
            self.save_manifest(manifest)

        return updated

    def scan_library(self) -> int:
        """Scan library directory for unmanaged states and add them."""
        manifest = self.get_manifest()
        existing_paths = {e.get("path") for e in manifest.get("entries", [])}
        added_count = 0
        
        for item in self.library_root.glob("*.mss"):
            if item.name not in existing_paths and not is_disallowed_state_path(item):
                # Generate a basic entry
                timestamp = int(item.stat().st_mtime)
                state_id = f"auto_{timestamp}_{item.stem}"
                entry = {
                    "id": state_id,
                    "path": item.name,
                    "label": item.stem.replace("_", " "),
                    "created_at": timestamp,
                    "tags": ["auto-discovered"],
                    "metadata": {}
                }
                manifest.setdefault("entries", []).append(entry)
                added_count += 1
        
        if added_count > 0:
            # Sort by creation time desc
            manifest["entries"].sort(key=lambda x: x.get("created_at", 0), reverse=True)
            self.save_manifest(manifest)
            
        return added_count

    def get_sets(self) -> list[dict]:
        """List all state sets in the library."""
        manifest = self.get_manifest()
        return manifest.get("sets", [])

    def load_state_aliased(
        self,
        bridge,
        state_id: str,
        target_rom: str,
        mesen_states_dir: Optional[Path] = None,
    ) -> bool:
        """Load a state from the library, aliasing it to a different ROM name.

        This enables cross-version state loading. For example, loading an `oos168x`
        state into `oos168p` by copying the state file with the target ROM's name.

        Args:
            bridge: MesenBridge instance
            state_id: State ID from the manifest
            target_rom: Target ROM base name (e.g., "oos168p")
            mesen_states_dir: Mesen2 SaveStates directory (auto-detected if None)

        Returns:
            True if state loaded successfully
        """
        import shutil

        entry = self.find_entry(state_id)
        if not entry:
            raise ValueError(f"State '{state_id}' not found in library")

        source_path = self.resolve_path(entry)
        if is_disallowed_state_path(source_path):
            raise ValueError(disallowed_state_reason(source_path))
        source_rom = entry.get("rom_base", "")

        # If source and target ROM match, load directly
        if source_rom == target_rom or not target_rom:
            return bridge.load_state(path=str(source_path))

        # Determine Mesen2 SaveStates directory
        if mesen_states_dir is None:
            home = Path.home()
            candidates = [
                home / "Library" / "Application Support" / "Mesen2" / "SaveStates",
                home / "Documents" / "Mesen2" / "SaveStates",
                home / ".config" / "Mesen2" / "SaveStates",
            ]
            for candidate in candidates:
                if candidate.exists():
                    mesen_states_dir = candidate
                    break
            if mesen_states_dir is None:
                mesen_states_dir = candidates[0]
                mesen_states_dir.mkdir(parents=True, exist_ok=True)

        # Extract slot number from source path (e.g., "oos168x_1.mss" -> "1")
        source_name = source_path.name
        slot = "1"
        if "_" in source_name:
            parts = source_name.replace(".mss", "").split("_")
            if parts[-1].isdigit():
                slot = parts[-1]

        # Create aliased state path
        aliased_name = f"{target_rom}_{slot}.mss"
        aliased_path = mesen_states_dir / aliased_name

        # Copy state file with new name
        shutil.copy2(source_path, aliased_path)

        # Load via slot number (more reliable than path in Mesen2)
        return bridge.load_state(slot=int(slot))
