#!/usr/bin/env python3
"""Create a declared prerequisite save in new files; never edit the input save.

The portal-acquisition-prerequisites profile supplies Power Glove for the
proposed coastal route. Rod acquisition and alternate routes remain untested.
Existing Power Glove or Titan's Mitt levels are retained. This tool does not
repair damaged saves, relocate Link, launch an emulator, or grant either rod.
"""
from __future__ import annotations

import argparse
from contextlib import ExitStack
import json
import os
from pathlib import Path

from prepare_goron_checkpoint import BLOCK_SIZE, CHECKSUM, sha256, word_sum

PROFILE = "portal-acquisition-prerequisites"
GLOVES = 0x354
CUSTOM_RODS = 0x351
PORTAL_ROD_OWNED = 0x3A6


def prepare(data: bytes, slot: int, profile: str = PROFILE) -> tuple[bytes, dict]:
    """Return a copied save and its fixture declaration without performing I/O."""
    if profile != PROFILE:
        raise ValueError(f"Unknown prerequisite profile: {profile}")
    if type(slot) is not int or slot not in (1, 2, 3):
        raise ValueError("Slot must be 1, 2 or 3")
    if len(data) != 8192:
        raise ValueError("Expected an 8192-byte SRAM file")
    primary = (slot - 1) * BLOCK_SIZE
    backup = primary + 0xF00
    block = bytearray(data[primary:primary + BLOCK_SIZE])
    if block[0x3E5:0x3E7] != b"\xAA\x55":
        raise ValueError("Selected slot is not an initialized native save")
    if block != data[backup:backup + BLOCK_SIZE] or word_sum(block) != 0x5A5A:
        raise ValueError("Selected slot backup/checksum differs; use a valid save")
    if block[CUSTOM_RODS] or block[PORTAL_ROD_OWNED]:
        raise ValueError("Acquisition fixture requires CustomRods=0 and PortalRodOwned=0")
    before = block[GLOVES]
    if before not in (0, 1, 2):
        raise ValueError("Gloves must be 0, 1 or 2")
    block[GLOVES] = max(before, 1)
    block[CHECKSUM:CHECKSUM + 2] = b"\0\0"
    block[CHECKSUM:CHECKSUM + 2] = (
        (0x5A5A - word_sum(block)) & 0xFFFF).to_bytes(2, "little")
    result = bytearray(data)
    for start in (primary, backup):
        result[start:start + BLOCK_SIZE] = block
    report = {
        "schema": "oos-progression-fixture-v1", "state": "prepared",
        "profile": profile, "slot": slot,
        "input_sha256": sha256(data), "output_sha256": sha256(result),
        "prerequisites": [{"name": "Gloves", "address": "0x7EF354",
                           "before": before, "after": block[GLOVES],
                           "supplied": before == 0}],
        "ungranted": {"CustomRods": 0, "PortalRodOwned": 0},
        "changed_offsets": [f"0x{i:04X}" for i, (old, new)
                            in enumerate(zip(data, result)) if old != new],
        "acquisition_tested": False,
        "limitations": ["Prerequisite fixture; no route or acquisition proof",
                        "Existing story, spawn, health and chest flags are inherited",
                        "Power Glove is a prerequisite for the proposed coastal route, "
                        "not a claim about every possible route"],
    }
    return bytes(result), report


def write_fixture(source: Path, output: Path, report_path: Path,
                  slot: int, profile: str = PROFILE) -> dict:
    paths = tuple(path.resolve() for path in (source, output, report_path))
    if len(set(paths)) != 3:
        raise ValueError("Input, output and report must be separate paths")
    if output.exists() or report_path.exists():
        raise ValueError("Output/report already exists; preserve previous artifacts")
    result, report = prepare(source.read_bytes(), slot, profile)
    report.update(input=str(paths[0]), output=str(paths[1]))
    payload = (json.dumps(report, indent=2) + "\n").encode()
    created = []
    try:
        with ExitStack() as stack:
            # Reserve both names before publishing bytes. Exclusive creation also
            # refuses dangling symlinks or targets created after the preflight.
            handles = []
            for path in (output, report_path):
                handle = stack.enter_context(path.open("xb"))
                info = os.fstat(handle.fileno())
                created.append((path, (info.st_dev, info.st_ino)))
                handles.append(handle)
            for handle, content in zip(handles, (result, payload)):
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
    except BaseException:
        # Remove only files created by this attempt, never a replacement target.
        for path, identity in created:
            try:
                info = path.lstat()
                if (info.st_dev, info.st_ino) == identity:
                    path.unlink()
            except FileNotFoundError:
                pass
        raise
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    parser.add_argument("--slot", required=True, type=int, choices=(1, 2, 3))
    parser.add_argument("--profile", required=True, choices=(PROFILE,))
    args = parser.parse_args()
    try:
        report = write_fixture(args.input, args.output, args.report,
                               args.slot, args.profile)
    except (ValueError, OSError) as exc:
        parser.exit(1, f"progression fixture: {exc}\n")
    print(json.dumps(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
