#!/usr/bin/env python3
"""Derive the approved one-shot outside-Mines start from canonical preview SRAM.

Only file2's spawn selector/checksum and its native backup change. Inventory,
progression and the closed gate are inherited, not granted by this tool.
"""
import argparse
import hashlib
import json
from pathlib import Path

CANONICAL_SHA256 = "47e7002072330556402324c1b3a7f6dbd2f4490b548f1b9a325072bf2008b150"
PRIMARY = 0x500
BACKUP = 0x1400
BLOCK_SIZE = 0x500
SPAWN = 0x3C8
CHECKSUM = 0x4FE


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def word_sum(block):
    return sum(int.from_bytes(block[i:i + 2], "little")
               for i in range(0, len(block), 2)) & 0xFFFF


def prepare(data):
    if len(data) != 8192 or sha256(data) != CANONICAL_SHA256:
        raise ValueError("Expected the exact canonical 8192-byte preview SRAM")
    block = bytearray(data[PRIMARY:PRIMARY + BLOCK_SIZE])
    if block != data[BACKUP:BACKUP + BLOCK_SIZE] or word_sum(block) != 0x5A5A:
        raise ValueError("Native file2 backup/checksum differs")
    if block[SPAWN] != 0 or block[0x3C5] != 2 or block[0x3CA] or block[0x3CC]:
        raise ValueError("Expected the canonical House/light-world/no-follower context")
    block[SPAWN] = 7
    block[CHECKSUM:CHECKSUM + 2] = b"\0\0"
    block[CHECKSUM:CHECKSUM + 2] = ((0x5A5A - word_sum(block)) & 0xFFFF).to_bytes(2, "little")
    result = bytearray(data)
    for start in (PRIMARY, BACKUP):
        result[start:start + BLOCK_SIZE] = block
    allowed = {start + offset for start in (PRIMARY, BACKUP)
               for offset in (SPAWN, CHECKSUM, CHECKSUM + 1)}
    if any(a != b and i not in allowed for i, (a, b) in enumerate(zip(data, result))):
        raise AssertionError("Unexpected SRAM mutation")
    if word_sum(block) != 0x5A5A:
        raise AssertionError("Prepared native checksum differs")
    return bytes(result)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--report", required=True, type=Path)
    args = parser.parse_args()
    if args.input.resolve() in (args.output.resolve(), args.report.resolve()) or args.output.resolve() == args.report.resolve():
        parser.error("Input, output and report must be separate paths")
    if args.output.exists() or args.report.exists():
        parser.error("Output/report already exists; preserve previous artifacts")
    data = args.input.read_bytes()
    result = prepare(data)
    with args.output.open("xb") as out:
        out.write(result)
    report = dict(input=str(args.input), input_sha256=sha256(data),
                  output=str(args.output), output_sha256=sha256(result),
                  changed_offsets=[f"{i:04X}" for i, (a, b) in enumerate(zip(data, result)) if a != b],
                  semantics="Outside on prepared start; House after native Save & Quit")
    with args.report.open("x") as out:
        json.dump(report, out, indent=2)
        out.write("\n")
    print(json.dumps(report))


if __name__ == "__main__":
    main()
