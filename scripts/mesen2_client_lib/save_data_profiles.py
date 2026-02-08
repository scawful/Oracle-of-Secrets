"""Human-editable save-data profiles (item/flag loadouts).

Profiles are JSON files stored under `Docs/Debugging/Testing/save_data_profiles/`.

Format (version 1):
{
  "version": 1,
  "id": "zora_temple_debug",
  "label": "Zora Temple Debug",
  "description": "...",
  "items": { "flute": 4, "ocarina_song": 3 },
  "flags": { "Story_IntroComplete": true },
  "writes": [
    {"addr": "0x7E030F", "type": "u8", "value": 3, "memtype": "WRAM"}
  ]
}
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .paths import SAVE_DATA_PROFILE_DIR


@dataclass(frozen=True)
class SaveDataProfile:
    path: Path
    data: dict[str, Any]

    @property
    def profile_id(self) -> str:
        return str(self.data.get("id") or self.path.stem)

    @property
    def label(self) -> str:
        return str(self.data.get("label") or self.profile_id)

    @property
    def description(self) -> str:
        return str(self.data.get("description") or "")


def profile_dir() -> Path:
    return Path(SAVE_DATA_PROFILE_DIR)


def list_profiles() -> list[SaveDataProfile]:
    root = profile_dir()
    if not root.exists():
        return []
    profiles: list[SaveDataProfile] = []
    for p in sorted(root.glob("*.json")):
        try:
            data = json.loads(p.read_text())
            profiles.append(SaveDataProfile(path=p, data=data))
        except Exception:
            continue
    return profiles


def load_profile(name_or_path: str) -> SaveDataProfile:
    p = Path(name_or_path)
    if not p.suffix and "/" not in name_or_path and "\\" not in name_or_path:
        p = profile_dir() / f"{name_or_path}.json"
    p = p.expanduser()
    if not p.exists():
        raise FileNotFoundError(f"Profile not found: {p}")
    data = json.loads(p.read_text())
    return SaveDataProfile(path=p, data=data)


def _parse_int(value: Any) -> int:
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        s = value.strip().lower()
        if s.startswith("0x"):
            return int(s, 16)
        if s.startswith("$"):
            return int(s[1:], 16)
        return int(s)
    raise ValueError(f"Invalid int value: {value!r}")


def apply_profile(client, profile: SaveDataProfile, *, dry_run: bool = False) -> list[str]:
    """Apply a profile using high-level setters + optional raw writes.

    Returns a list of actions taken (for logging/printing).
    """
    actions: list[str] = []
    data = profile.data or {}

    items = data.get("items") or {}
    if not isinstance(items, dict):
        raise ValueError("Profile 'items' must be a JSON object")
    for k, v in items.items():
        value = _parse_int(v)
        actions.append(f"item:{k}={value}")
        if not dry_run:
            client.set_item(k, value)

    flags = data.get("flags") or {}
    if not isinstance(flags, dict):
        raise ValueError("Profile 'flags' must be a JSON object")
    for k, v in flags.items():
        # Allow bool or 0/1.
        val_bool = bool(v) if isinstance(v, bool) else bool(_parse_int(v))
        actions.append(f"flag:{k}={'1' if val_bool else '0'}")
        if not dry_run:
            client.set_flag(k, val_bool)

    writes = data.get("writes") or []
    if writes:
        if not isinstance(writes, list):
            raise ValueError("Profile 'writes' must be a list")
        for w in writes:
            if not isinstance(w, dict):
                raise ValueError("Profile 'writes' entries must be objects")
            addr = _parse_int(w.get("addr"))
            wtype = (w.get("type") or "u8").lower()
            memtype = w.get("memtype") or None
            if wtype == "u16":
                value = _parse_int(w.get("value"))
                actions.append(f"write16:{addr:06X}={value:04X}({memtype or 'default'})")
                if not dry_run:
                    client.bridge.write_memory16(addr, value, memtype=memtype)
            else:
                value = _parse_int(w.get("value"))
                actions.append(f"write8:{addr:06X}={value:02X}({memtype or 'default'})")
                if not dry_run:
                    client.bridge.write_memory(addr, value, memtype=memtype)

    return actions

