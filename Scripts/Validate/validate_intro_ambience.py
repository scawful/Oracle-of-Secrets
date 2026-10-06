#!/usr/bin/env python3
"""Read-only check of intro rain removal in a built, unheadered LoROM.

Compare against the exact base ROM used for the build. Only phase-00 rain
commands may become silence. All music nibbles, other phase-00 ambience, later
light-world phases, and dark/special-world ambience must remain unchanged.
This checks compiled data, not audible output or the device's loaded ROM.
Exit codes: 0 = pass, 1 = findings, 2 = invalid input.
"""
from __future__ import annotations

import argparse
import hashlib
from pathlib import Path


TABLE_SNES = 0x02C303
TABLE_PC = 0x014303
INTRO_SIZE = 0x40
TABLE_SIZE = 0x160  # Four light-world phases, then dark/special-world entries.


def check_ambience(base: bytes, rom: bytes) -> list[str]:
    end = TABLE_PC + TABLE_SIZE
    if min(len(base), len(rom)) < end:
        raise ValueError(f"Both ROMs must contain the full ambiance table through ${end - 1:06X}")
    issues = []
    for index in range(TABLE_SIZE):
        before, actual = base[TABLE_PC + index], rom[TABLE_PC + index]
        remove_rain = index < INTRO_SIZE and before >> 4 == 1
        expected = (0x50 | (before & 0x0F)) if remove_rain else before
        if actual != expected:
            issues.append(
                f"${TABLE_SNES + index:06X}: base ${before:02X}, "
                f"expected ${expected:02X}, got ${actual:02X}"
            )
    return issues


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    args = parser.parse_args()
    try:
        base, rom = args.base.read_bytes(), args.rom.read_bytes()
        issues = check_ambience(base, rom)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"Error: {exc}\n")
    print(f"base_sha256={hashlib.sha256(base).hexdigest()}")
    print(f"rom_sha256={hashlib.sha256(rom).hexdigest()}")
    for issue in issues:
        print(f"FAIL {issue}")
    if not issues:
        print("PASS: phase-00 rain silenced; music and other ambiance entries preserved")
    return int(bool(issues))


if __name__ == "__main__":
    raise SystemExit(main())
