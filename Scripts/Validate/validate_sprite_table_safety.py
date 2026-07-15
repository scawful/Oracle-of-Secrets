#!/usr/bin/env python3
"""Validate Oracle sprite-table boundaries against a canonical base ROM.

The bytes after sprite ID $F2 are not empty, so treating non-zero data as an
overflow produces false positives.  Oracle instead requires those bytes to
match the canonical edit ROM, apart from the documented Twinrova prep hook.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path


MAX_SPRITE_ID = 0xF2
INVALID_SPRITE_COUNT = 0x100 - (MAX_SPRITE_ID + 1)
POINTER_SIZE = 2

SPRITE_MAIN_POINTER_TABLE = 0x069283
SPRITE_PREP_POINTER_TABLE = 0x06865B
MAIN_OVERFLOW_START = SPRITE_MAIN_POINTER_TABLE + (MAX_SPRITE_ID + 1) * POINTER_SIZE
PREP_OVERFLOW_START = SPRITE_PREP_POINTER_TABLE + (MAX_SPRITE_ID + 1) * POINTER_SIZE
OVERFLOW_SIZE = INVALID_SPRITE_COUNT * POINTER_SIZE

LOAD_PROPERTIES_SENTINEL = 0x0DB818
CANONICAL_SENTINEL = bytes.fromhex("22 71 B8 0D 5A 8B 4B AB")

TWINROVA_HOOK = 0x068841
TWINROVA_HOOK_SIZE = 5


def snes_to_pc(address: int) -> int:
    """Convert a 24-bit LoROM address to an unheadered file offset."""
    bank = (address >> 16) & 0xFF
    offset = address & 0xFFFF
    if offset < 0x8000 or (bank & 0x7E) == 0x7E:
        raise ValueError(f"SNES address ${address:06X} is not in LoROM space")
    return (bank & 0x7F) * 0x8000 + (offset - 0x8000)


def _read(rom: bytes, address: int, size: int, rom_name: str) -> bytes:
    start = snes_to_pc(address)
    end = start + size
    if end > len(rom):
        raise ValueError(
            f"{rom_name} is too small for ${address:06X}-${address + size - 1:06X} "
            f"(need at least {end} bytes, found {len(rom)})"
        )
    return rom[start:end]


def _mismatch_addresses(base: bytes, patched: bytes, start: int) -> str:
    addresses = [f"${start + index:06X}" for index, pair in enumerate(zip(base, patched)) if pair[0] != pair[1]]
    return ", ".join(addresses)


def validate_sprite_table_safety(base: bytes, patched: bytes) -> list[str]:
    """Return safety violations; an empty list means validation passed."""
    errors: list[str] = []

    try:
        base_sentinel = _read(base, LOAD_PROPERTIES_SENTINEL, len(CANONICAL_SENTINEL), "base ROM")
        patched_sentinel = _read(
            patched, LOAD_PROPERTIES_SENTINEL, len(CANONICAL_SENTINEL), "patched ROM"
        )
        base_main = _read(base, MAIN_OVERFLOW_START, OVERFLOW_SIZE, "base ROM")
        patched_main = _read(patched, MAIN_OVERFLOW_START, OVERFLOW_SIZE, "patched ROM")
        base_prep = _read(base, PREP_OVERFLOW_START, OVERFLOW_SIZE, "base ROM")
        patched_prep = _read(patched, PREP_OVERFLOW_START, OVERFLOW_SIZE, "patched ROM")
    except ValueError as exc:
        return [str(exc)]

    if base_sentinel != CANONICAL_SENTINEL:
        errors.append(
            f"base ROM sentinel at ${LOAD_PROPERTIES_SENTINEL:06X} is not the canonical "
            f"JSL $0DB871 hook ({base_sentinel.hex(' ')} != {CANONICAL_SENTINEL.hex(' ')})"
        )
    if patched_sentinel != CANONICAL_SENTINEL:
        errors.append(
            f"patched ROM sentinel at ${LOAD_PROPERTIES_SENTINEL:06X} changed "
            f"({patched_sentinel.hex(' ')} != {CANONICAL_SENTINEL.hex(' ')})"
        )

    if base_main != patched_main:
        errors.append(
            "patched ROM changed the sprite main pointer overflow region at "
            + _mismatch_addresses(base_main, patched_main, MAIN_OVERFLOW_START)
        )

    hook = patched_prep[:TWINROVA_HOOK_SIZE]
    hook_target = int.from_bytes(hook[1:4], "little")
    target_bank = hook_target >> 16
    if (
        hook[0] != 0x22
        or hook[-1] != 0x60
        or (hook_target & 0xFFFF) < 0x8000
        or (target_bank & 0x7E) == 0x7E
    ):
        errors.append(
            f"patched ROM bytes at ${TWINROVA_HOOK:06X} are not a LoROM JSL target followed by RTS "
            f"({hook.hex(' ')})"
        )

    base_prep_tail = base_prep[TWINROVA_HOOK_SIZE:]
    patched_prep_tail = patched_prep[TWINROVA_HOOK_SIZE:]
    if base_prep_tail != patched_prep_tail:
        errors.append(
            "patched ROM changed the sprite prep pointer overflow region outside the allowed "
            f"${TWINROVA_HOOK:06X}-${TWINROVA_HOOK + TWINROVA_HOOK_SIZE - 1:06X} hook at "
            + _mismatch_addresses(
                base_prep_tail,
                patched_prep_tail,
                PREP_OVERFLOW_START + TWINROVA_HOOK_SIZE,
            )
        )

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Validate Oracle sprite-table boundaries against a canonical base ROM"
    )
    parser.add_argument("--base", type=Path, required=True, help="Canonical unpatched edit ROM")
    parser.add_argument("--patched", type=Path, required=True, help="Asar-patched test ROM")
    args = parser.parse_args(argv)

    try:
        base = args.base.read_bytes()
        patched = args.patched.read_bytes()
    except OSError as exc:
        print(f"Sprite table safety check failed: {exc}", file=sys.stderr)
        return 1

    errors = validate_sprite_table_safety(base, patched)
    if errors:
        print("Sprite table safety check failed:", file=sys.stderr)
        for error in errors:
            print(f"  - {error}", file=sys.stderr)
        return 1

    hook = _read(patched, TWINROVA_HOOK, TWINROVA_HOOK_SIZE, "patched ROM")
    hook_target = int.from_bytes(hook[1:4], "little")
    print(
        "Sprite table safety check passed: canonical sentinel preserved; "
        f"main IDs $F3-$FF unchanged; prep IDs $F3-$FF unchanged outside "
        f"JSL ${hook_target:06X} : RTS at ${TWINROVA_HOOK:06X}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
