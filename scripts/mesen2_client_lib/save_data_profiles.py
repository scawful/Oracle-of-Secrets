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

from .constants import ITEMS, STORY_FLAGS, SAVEFILE_WRAM_SIZE, SAVEFILE_WRAM_START
from .paths import SAVE_DATA_PROFILE_DIR


SAVEFILE_WRAM_END = SAVEFILE_WRAM_START + SAVEFILE_WRAM_SIZE


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


@dataclass(frozen=True)
class ProfileExpectation:
    kind: str
    name: str
    addr: int
    size: int
    value: int | bool
    memtype: str | None = None
    mask: int | None = None
    persistent: bool = False


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


def _is_wram_memtype(memtype: str | None) -> bool:
    if memtype is None:
        return True
    return str(memtype).strip().upper() == "WRAM"


def is_persistent_save_address(addr: int, *, size: int = 1, memtype: str | None = None) -> bool:
    if not _is_wram_memtype(memtype):
        return False
    end_addr = addr + max(1, size) - 1
    return SAVEFILE_WRAM_START <= addr and end_addr < SAVEFILE_WRAM_END


def iter_profile_expectations(profile: SaveDataProfile) -> list[ProfileExpectation]:
    """Parse profile data into normalized operations for apply/verify paths."""
    data = profile.data or {}
    expectations: list[ProfileExpectation] = []

    items = data.get("items") or {}
    if not isinstance(items, dict):
        raise ValueError("Profile 'items' must be a JSON object")
    for key, raw_value in items.items():
        if key not in ITEMS:
            raise ValueError(f"Unknown item in profile: {key}")
        addr, _, _ = ITEMS[key]
        size = 2 if key == "rupees" else 1
        value = _parse_int(raw_value)
        expectations.append(
            ProfileExpectation(
                kind="item",
                name=key,
                addr=addr,
                size=size,
                value=value,
                persistent=is_persistent_save_address(addr, size=size),
            )
        )

    flags = data.get("flags") or {}
    if not isinstance(flags, dict):
        raise ValueError("Profile 'flags' must be a JSON object")
    for key, raw_value in flags.items():
        if key not in STORY_FLAGS:
            raise ValueError(f"Unknown flag in profile: {key}")
        addr, _, mask_or_values = STORY_FLAGS[key]
        if isinstance(mask_or_values, int):
            value = bool(raw_value) if isinstance(raw_value, bool) else bool(_parse_int(raw_value))
            expectations.append(
                ProfileExpectation(
                    kind="flag_bit",
                    name=key,
                    addr=addr,
                    size=1,
                    value=value,
                    mask=mask_or_values,
                    persistent=is_persistent_save_address(addr),
                )
            )
        else:
            value = _parse_int(raw_value) & 0xFF
            expectations.append(
                ProfileExpectation(
                    kind="flag_byte",
                    name=key,
                    addr=addr,
                    size=1,
                    value=value,
                    persistent=is_persistent_save_address(addr),
                )
            )

    writes = data.get("writes") or []
    if writes:
        if not isinstance(writes, list):
            raise ValueError("Profile 'writes' must be a list")
        for write_entry in writes:
            if not isinstance(write_entry, dict):
                raise ValueError("Profile 'writes' entries must be objects")
            addr = _parse_int(write_entry.get("addr"))
            wtype = str(write_entry.get("type") or "u8").lower()
            memtype_raw = write_entry.get("memtype")
            memtype = str(memtype_raw).strip() if memtype_raw is not None else None
            memtype = memtype or None
            if wtype == "u16":
                value = _parse_int(write_entry.get("value")) & 0xFFFF
                size = 2
            else:
                value = _parse_int(write_entry.get("value")) & 0xFF
                size = 1
            expectations.append(
                ProfileExpectation(
                    kind="write",
                    name=f"0x{addr:06X}",
                    addr=addr,
                    size=size,
                    value=value,
                    memtype=memtype,
                    persistent=is_persistent_save_address(addr, size=size, memtype=memtype),
                )
            )

    return expectations


def summarize_expectations(expectations: list[ProfileExpectation]) -> dict[str, int]:
    persistent = sum(1 for entry in expectations if entry.persistent)
    total = len(expectations)
    return {
        "total": total,
        "persistent": persistent,
        "volatile": total - persistent,
    }


def apply_profile(
    client,
    profile: SaveDataProfile,
    *,
    dry_run: bool = False,
    expectations: list[ProfileExpectation] | None = None,
) -> list[str]:
    """Apply a profile using high-level setters + optional raw writes.

    Returns a list of actions taken (for logging/printing).
    """
    actions: list[str] = []
    ops = expectations if expectations is not None else iter_profile_expectations(profile)

    for op in ops:
        if op.kind == "item":
            value = int(op.value)
            actions.append(f"item:{op.name}={value}")
            if not dry_run and not client.set_item(op.name, value):
                raise RuntimeError(f"Failed to set item: {op.name}")
            continue

        if op.kind == "flag_bit":
            value = bool(op.value)
            actions.append(f"flag:{op.name}={'1' if value else '0'}")
            if not dry_run and not client.set_flag(op.name, value):
                raise RuntimeError(f"Failed to set flag bit: {op.name}")
            continue

        if op.kind == "flag_byte":
            value = int(op.value) & 0xFF
            actions.append(f"flag:{op.name}=0x{value:02X}")
            if not dry_run and not client.set_flag(op.name, value):
                raise RuntimeError(f"Failed to set flag byte: {op.name}")
            continue

        if op.kind == "write":
            value = int(op.value)
            memtype = op.memtype
            mem_name = memtype or "default"
            if op.size == 2:
                actions.append(f"write16:{op.addr:06X}={value:04X}({mem_name})")
                if not dry_run and not client.bridge.write_memory16(op.addr, value, memtype=memtype):
                    raise RuntimeError(f"Failed write16 at 0x{op.addr:06X}")
            else:
                actions.append(f"write8:{op.addr:06X}={value:02X}({mem_name})")
                if not dry_run and not client.bridge.write_memory(op.addr, value, memtype=memtype):
                    raise RuntimeError(f"Failed write8 at 0x{op.addr:06X}")
            continue

        raise ValueError(f"Unsupported profile operation kind: {op.kind}")

    return actions
