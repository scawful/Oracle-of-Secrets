#!/usr/bin/env python3
"""Apply a reviewed byte patch (JSON) to the base ROM, with before-byte guards.

Usage:
  python3 Scripts/Build/apply_rom_byte_patch.py PATCH.json --rom Roms/oos168.sfc          # dry run
  python3 Scripts/Build/apply_rom_byte_patch.py PATCH.json --rom Roms/oos168.sfc --apply  # write

PATCH.json:
  {"base_sha1": "<sha1 of the ROM the patch was made against, optional>",
   "edits": [{"id": "...", "pc": "0x7163B", "snes": "$0E963B",
              "before": "4B", "after": "02", "why": "..."}]}

Every edit must read its "before" bytes (or already read "after": re-running is a
no-op). Any other value aborts without writing. Offsets are unheadered PC.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path


def snes_to_pc(snes: int) -> int:
    return ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("patch", type=Path)
    ap.add_argument("--rom", type=Path, required=True)
    ap.add_argument("--apply", action="store_true", help="write the ROM (default: dry run)")
    args = ap.parse_args()

    spec = json.loads(args.patch.read_text())
    rom = bytearray(args.rom.read_bytes())
    sha_before = hashlib.sha1(rom).hexdigest()
    print(f"ROM {args.rom} SHA-1 {sha_before}")
    if spec.get("base_sha1") and not sha_before.startswith(spec["base_sha1"]):
        print(f"note: patch was made against base SHA-1 {spec['base_sha1']}")

    pending, failed = [], False
    for edit in spec["edits"]:
        pc = int(edit["pc"], 16)
        if "snes" in edit:
            snes = int(edit["snes"].lstrip("$"), 16)
            if snes_to_pc(snes) != pc:
                print(f"FAIL {edit['id']}: {edit['snes']} maps to PC 0x{snes_to_pc(snes):X}, not 0x{pc:X}")
                failed = True
                continue
        before, after = bytes.fromhex(edit["before"]), bytes.fromhex(edit["after"])
        if len(before) != len(after):
            print(f"FAIL {edit['id']}: before/after length differ")
            failed = True
            continue
        now = bytes(rom[pc:pc + len(before)])
        if now == after:
            print(f"ok   {edit['id']}: PC 0x{pc:06X} already {after.hex(' ').upper()}")
        elif now == before:
            print(f"edit {edit['id']}: PC 0x{pc:06X} {before.hex(' ').upper()} -> {after.hex(' ').upper()}")
            pending.append((pc, after))
        else:
            print(f"FAIL {edit['id']}: PC 0x{pc:06X} reads {now.hex(' ').upper()}, "
                  f"expected {before.hex(' ').upper()} (or {after.hex(' ').upper()})")
            failed = True
    if failed:
        print("aborted: nothing written")
        return 1
    for pc, after in pending:
        rom[pc:pc + len(after)] = after
    sha_after = hashlib.sha1(rom).hexdigest()
    if not args.apply:
        print(f"dry run: {len(pending)} edit(s) pending; result SHA-1 would be {sha_after}")
        return 0
    if pending:
        args.rom.write_bytes(rom)
    print(f"wrote {len(pending)} edit(s); SHA-1 {sha_after}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
