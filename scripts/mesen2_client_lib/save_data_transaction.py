"""Transactional save-data profile application with verification.

This module implements a deterministic pipeline for live profile application:
1. Apply profile writes to WRAM/memtypes.
2. Verify those writes in live memory.
3. Optionally persist WRAMSAVE into cart SRAM.
4. Optionally verify persisted values in SRAM slot data.
"""

from __future__ import annotations

from typing import Any

from .cart_sram import read_slot_saveblock
from .constants import SAVEFILE_WRAM_START
from .save_data_profiles import (
    ProfileExpectation,
    SaveDataProfile,
    apply_profile,
    iter_profile_expectations,
    summarize_expectations,
)


def _expectation_label(op: ProfileExpectation) -> str:
    if op.kind in ("item", "flag_bit", "flag_byte"):
        return f"{op.kind}:{op.name}"
    mem = op.memtype or "WRAM"
    return f"write:0x{op.addr:06X}({mem})"


def _read_value(bridge, addr: int, size: int, memtype: str | None = None) -> int:
    if size == 2:
        return bridge.read_memory16(addr, memtype=memtype)
    return bridge.read_memory(addr, memtype=memtype)


def _read_persistent_value(save_blob: bytes, addr: int, size: int) -> int:
    offset = addr - SAVEFILE_WRAM_START
    if offset < 0 or (offset + size) > len(save_blob):
        raise ValueError(f"Address 0x{addr:06X} is outside WRAMSAVE range")
    if size == 2:
        return save_blob[offset] | (save_blob[offset + 1] << 8)
    return save_blob[offset]


def _verify_wram(client, ops: list[ProfileExpectation]) -> list[str]:
    issues: list[str] = []
    for op in ops:
        if op.kind == "flag_bit":
            raw = _read_value(client.bridge, op.addr, 1)
            got = bool(raw & int(op.mask or 0))
            expected = bool(op.value)
            if got != expected:
                issues.append(
                    f"{_expectation_label(op)} expected bit={int(expected)} got {int(got)} (raw=0x{raw:02X})"
                )
            continue

        memtype = op.memtype if op.kind == "write" else None
        got = _read_value(client.bridge, op.addr, op.size, memtype=memtype)
        expected = int(op.value)
        if got != expected:
            fmt = "04X" if op.size == 2 else "02X"
            issues.append(
                f"{_expectation_label(op)} expected 0x{expected:{fmt}} got 0x{got:{fmt}}"
            )
    return issues


def _verify_sram_slot(client, slot: int, ops: list[ProfileExpectation]) -> list[str]:
    issues: list[str] = []
    save_blob = read_slot_saveblock(client.bridge, slot, prefer_mirror=False)

    for op in ops:
        if not op.persistent:
            continue

        if op.kind == "flag_bit":
            raw = _read_persistent_value(save_blob, op.addr, 1)
            got = bool(raw & int(op.mask or 0))
            expected = bool(op.value)
            if got != expected:
                issues.append(
                    f"SRAM slot {slot} {_expectation_label(op)} expected bit={int(expected)} "
                    f"got {int(got)} (raw=0x{raw:02X})"
                )
            continue

        got = _read_persistent_value(save_blob, op.addr, op.size)
        expected = int(op.value)
        if got != expected:
            fmt = "04X" if op.size == 2 else "02X"
            issues.append(
                f"SRAM slot {slot} {_expectation_label(op)} expected 0x{expected:{fmt}} got 0x{got:{fmt}}"
            )

    return issues


def apply_profile_transaction(
    client,
    profile: SaveDataProfile,
    *,
    slot: int | None = None,
    persist: bool = True,
    verify: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Apply a save-data profile with optional persistence and verification."""
    ops = iter_profile_expectations(profile)
    summary = summarize_expectations(ops)
    warnings: list[str] = []

    if persist and summary["volatile"] > 0:
        warnings.append(
            "Profile includes volatile targets outside WRAMSAVE; these validate in live WRAM but do not persist to SRAM."
        )

    actions = apply_profile(client, profile, dry_run=dry_run, expectations=ops)

    result: dict[str, Any] = {
        "profile": profile.profile_id,
        "label": profile.label,
        "dry_run": bool(dry_run),
        "persisted": False,
        "verified": False,
        "slot": int(slot or 0) or None,
        "actions": actions,
        "targets": summary,
        "warnings": warnings,
        "errors": [],
        "wram_issues": [],
        "sram_issues": [],
    }

    if dry_run:
        result["ok"] = True
        return result

    if verify:
        wram_issues = _verify_wram(client, ops)
        result["wram_issues"] = wram_issues

    slot_used: int | None = None
    if persist:
        sync_result = client.sync_wram_save_to_sram(slot=slot)
        slot_used = int(sync_result.get("slot", 0) or 0) or None
        result["slot"] = slot_used
        result["persisted"] = True

        if verify and slot_used is not None:
            sram_issues = _verify_sram_slot(client, slot_used, ops)
            result["sram_issues"] = sram_issues

    if verify:
        result["verified"] = True

    errors: list[str] = []
    errors.extend(result.get("wram_issues") or [])
    errors.extend(result.get("sram_issues") or [])
    result["errors"] = errors
    result["ok"] = len(errors) == 0
    return result
