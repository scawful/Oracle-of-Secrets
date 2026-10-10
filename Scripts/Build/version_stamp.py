#!/usr/bin/env python3
"""Stamp the build version into the in-game version line (message $C7).

Message $C7 reads "Oracle of Secrets Preview / v0.168 / scawful". Line 2 (the
bytes between the [2] and [3] line commands) is rewritten with
"v<version>-b<build>" from Config/version.json, padded to the same byte
length, so no other message moves. Runs on the patched ROM after asar: a
post-build write does not enter the hack manifest, so yaze can still rewrite
the vanilla text region in the base ROM (and $C7 may move; it is found by
walking the text the way CreateMessagePointers ($0ED3EB) does).

Usage:
  python3 Scripts/Build/version_stamp.py --rom Roms/oos168x.sfc [--check]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
VERSION_FILE = REPO_ROOT / "Config" / "version.json"

MESSAGE_ID = 0xC7
REGION1_PC = 0x0E0000          # Message_Data, $1C:8000
CMD_LENGTHS_PC = 0x07536B      # $0E:D36B RenderText_MoreInitialSettings (lengths by byte)
LINE2, LINE3, END, BANK = 0x75, 0x76, 0x7F, 0x80
SPACE, DICT_4_SPACES, DICT_3_SPACES = 0x59, 0x88, 0x89
TARGET_LEAD_SPACES = 15        # original centering of "v0.168"


def encode_char(ch: str) -> int:
    if "A" <= ch <= "Z":
        return ord(ch) - ord("A")
    if "a" <= ch <= "z":
        return 0x1A + ord(ch) - ord("a")
    if "0" <= ch <= "9":
        return 0x34 + ord(ch) - ord("0")
    table = {"-": 0x40, ".": 0x41, " ": SPACE}
    if ch in table:
        return table[ch]
    raise SystemExit(f"version_stamp: character {ch!r} has no encoding")


def cmd_length(rom: bytes, byte: int) -> int:
    if 0x67 <= byte < 0x80:
        return rom[CMD_LENGTHS_PC + byte]
    return 1


def find_message(rom: bytes, message_id: int) -> tuple[int, int]:
    """Return (start, end) PC of message_id in text region 1 (end = its $7F)."""
    pc, index, start = REGION1_PC, 0, REGION1_PC
    while True:
        byte = rom[pc]
        if byte == BANK:
            raise SystemExit(f"version_stamp: message ${message_id:02X} not in region 1")
        if byte == END:
            if index == message_id:
                return start, pc
            index += 1
            pc += 1
            start = pc
            continue
        pc += cmd_length(rom, byte)


def build_line(text: str, width: int) -> bytes:
    body = bytes(encode_char(c) for c in text)
    budget = width - len(body)
    if budget < 0:
        raise SystemExit(f"version_stamp: {text!r} needs {len(body)} bytes; line 2 has {width}")
    lead, spaces = [], TARGET_LEAD_SPACES
    while budget > 0 and spaces > 0:
        if spaces >= 4:
            lead.append(DICT_4_SPACES); spaces -= 4
        elif spaces == 3:
            lead.append(DICT_3_SPACES); spaces -= 3
        else:
            lead.append(SPACE); spaces -= 1
        budget -= 1
    return bytes(lead) + body + bytes([SPACE] * budget)  # trailing pad


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--version-file", type=Path, default=VERSION_FILE)
    parser.add_argument("--check", action="store_true", help="report only; do not write")
    args = parser.parse_args()

    info = json.loads(args.version_file.read_text())
    text = f"v{info['version']}-b{info['build']}"
    rom = bytearray(args.rom.read_bytes())

    start, end = find_message(rom, MESSAGE_ID)
    body = rom[start:end]
    # Line commands appear at top level; find them by walking, not searching.
    i, l2, l3 = 0, None, None
    while i < len(body):
        b = body[i]
        if b == LINE2 and l2 is None:
            l2 = i
        elif b == LINE3 and l3 is None:
            l3 = i
        i += cmd_length(rom, b)
    if l2 is None or l3 is None or l3 <= l2:
        raise SystemExit(f"version_stamp: message ${MESSAGE_ID:02X} has no [2]..[3] line")
    w0, w1 = start + l2 + 1, start + l3
    new = build_line(text, w1 - w0)
    old = bytes(rom[w0:w1])
    snes = ((w0 << 1) & 0x7F0000) | 0x8000 | (w0 & 0x7FFF)
    print(f"version_stamp: ${MESSAGE_ID:02X} line 2 at PC {w0:#x} (${snes:06X}), "
          f"{w1 - w0} bytes: {old.hex(' ')} -> {new.hex(' ')} ({text})")
    if args.check or old == new:
        return 0

    rom[w0:w1] = new
    # Only these bytes changed, so adjust the header checksum by the delta.
    delta = sum(new) - sum(old)
    checksum = (rom[0x7FDE] | rom[0x7FDF] << 8) + delta
    checksum &= 0xFFFF
    rom[0x7FDE], rom[0x7FDF] = checksum & 0xFF, checksum >> 8
    comp = checksum ^ 0xFFFF
    rom[0x7FDC], rom[0x7FDD] = comp & 0xFF, comp >> 8
    args.rom.write_bytes(bytes(rom))
    return 0


if __name__ == "__main__":
    sys.exit(main())
