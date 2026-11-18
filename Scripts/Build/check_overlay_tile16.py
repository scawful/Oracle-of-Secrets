#!/usr/bin/env python3
"""Fail when a Tile16 ID drawn by an overworld overlay changes its definition.

Overlays (ROM overlay streams for maps $00-$9F and the LDA.w immediates in
Overworld/overlays.asm) draw Tile16 IDs by number. Rewriting one of those IDs for
new map art silently breaks the overlay (castle bridge, 2026-11-17). This check
compares each overlay-referenced ID's 8-byte definition with
Data/overlay_tile16_pins.json.

  check_overlay_tile16.py --rom <base.sfc>            check (exit 1 on a changed ID)
  check_overlay_tile16.py --rom <base.sfc> --update   re-pin after an intended change
  check_overlay_tile16.py --rom <base.sfc> --free     list Tile16 IDs no overlay uses

Before giving a Tile16 ID new art, pick one that no map and no overlay uses.
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PINS = ROOT / "Data" / "overlay_tile16_pins.json"
OVERLAYS_ASM = ROOT / "Overworld" / "overlays.asm"
TILE16 = 0x1E8000  # expanded Tile16 table (ZSCustomOverworld), 8 bytes per ID
TILE16_COUNT = 0x1000
OVERLAY_PTRS = 0x77677  # 24-bit pointers, valid for maps $00-$9F
OVERLAY_MAPS = 0xA0


def pc(snes):
    return ((snes & 0x7F0000) >> 1) | (snes & 0x7FFF)


def stream_refs(rom):
    """Tile16 IDs stored by each overlay stream: LDA #imm, STA/STA,X addr, INC A, RTL."""
    refs = {}
    for m in range(OVERLAY_MAPS):
        p = OVERLAY_PTRS + m * 3
        addr = pc(rom[p] | rom[p + 1] << 8 | rom[p + 2] << 16)
        value, stores = 0, 0
        while rom[addr] != 0x6B:
            op = rom[addr]
            if op == 0xA9:
                value = rom[addr + 1] | rom[addr + 2] << 8
                addr += 3
            elif op in (0x8D, 0x9D):
                refs.setdefault(value, set()).add("ov%02X" % m)
                addr += 3
                stores += 1
            elif op == 0x1A:
                value += 1
                addr += 1
            else:
                raise SystemExit("overlay stream ov%02X: unexpected opcode $%02X at PC $%06X" % (m, op, addr))
            if stores > 1024:
                raise SystemExit("overlay stream ov%02X: no RTL after 1024 stores" % m)
    return refs


def asm_refs():
    refs, label = {}, None
    for line in OVERLAYS_ASM.read_text().splitlines():
        m = re.match(r"([A-Za-z_][A-Za-z0-9_]*):", line)
        if m:
            label = m.group(1)
        for h in re.findall(r"LDA\.w #\$([0-9A-Fa-f]{4})", line):
            t = int(h, 16)
            if t < TILE16_COUNT:
                refs.setdefault(t, set()).add(label or "overlays.asm")
    return refs


def all_refs(rom):
    refs = stream_refs(rom)
    for t, users in asm_refs().items():
        refs.setdefault(t, set()).update(users)
    return refs


def definition(rom, t):
    return rom[TILE16 + t * 8:TILE16 + t * 8 + 8].hex()


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--pins", type=Path, default=PINS)
    ap.add_argument("--update", action="store_true", help="rewrite the pin file from --rom")
    ap.add_argument("--free", action="store_true", help="print Tile16 IDs no overlay references")
    args = ap.parse_args()
    rom = args.rom.read_bytes()
    refs = all_refs(rom)

    if args.free:
        free = [t for t in range(TILE16_COUNT) if t not in refs]
        print(json.dumps({"overlay_free": ["%03X" % t for t in free]}))
        print("[*] %d of %d Tile16 IDs have no overlay reference; also check map usage "
              "(z3ed overworld-tile-stats) before reuse." % (len(free), TILE16_COUNT), file=sys.stderr)
        return 0

    if args.update:
        data = {
            "about": "8-byte Tile16 definitions drawn by overworld overlays. "
                     "Regenerate: python3 Scripts/Build/check_overlay_tile16.py --rom <base> --update",
            "tile16": {"%03X" % t: {"def": definition(rom, t), "users": sorted(u)}
                       for t, u in sorted(refs.items())},
        }
        args.pins.write_text(json.dumps(data, indent=1) + "\n")
        print("[+] pinned %d overlay Tile16 IDs to %s" % (len(refs), args.pins))
        return 0

    pins = json.loads(args.pins.read_text())["tile16"]
    changed = []
    for t, users in sorted(refs.items()):
        pin = pins.get("%03X" % t)
        if pin and pin["def"] != definition(rom, t):
            changed.append((t, users, pin["def"]))
    unpinned = sorted(t for t in refs if "%03X" % t not in pins)
    if unpinned:
        print("[!] %d overlay Tile16 IDs are not pinned (new overlay data?): %s"
              % (len(unpinned), " ".join("%03X" % t for t in unpinned[:20])))
    if changed:
        print("[-] %d Tile16 IDs drawn by overlays changed definition:" % len(changed))
        for t, users, old in changed[:40]:
            print("    %03X %s -> %s  used by %s" % (t, old, definition(rom, t), " ".join(sorted(users))))
        print("    Fix: give the new art free Tile16 IDs and restore these, or move the overlay "
              "to new IDs. If the change is intended, re-pin with --update.")
        return 1
    print("[+] %d overlay Tile16 IDs match their pins." % len(refs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
