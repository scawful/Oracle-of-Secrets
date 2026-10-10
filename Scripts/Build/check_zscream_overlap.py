#!/usr/bin/env python3
"""Check Asar WLA emission addresses against the ZScream PC reservation map.

WLA labels also include constants and inactive data declarations. The
address-to-line section identifies emitted code/data, including unlabeled
instructions. It records starts, not byte lengths: this is not a proof that
every emitted byte is outside a reservation.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


# Explicit allocations inside the editor's coarse reserved banks. Require the
# emitting source as well as the PC range; never exempt an entire bank for all
# Oracle code. Bounds are inclusive, in unheadered PC offsets.
OWNED_REGIONS = (
    ("Overworld/ZSCustomOverworld.asm", 0x140000, 0x147FFF),
    ("Overworld/lost_woods.asm", 0x107000, 0x107FFF),
    ("Masks/bunny_hood.asm", 0x102F20, 0x102F6F),
    ("Masks/bunny_hood.asm", 0x102F70, 0x102F8D),
    # generate_water_fill_table.py reserves this tail of custom collision data
    # and rejects tables that exceed it. The collision source contract excludes
    # this area from the editor's per-room collision streams.
    ("Dungeons/generated/water_fill_table.asm", 0x12E000, 0x12FFFF),
)


REPO_ROOT = Path(__file__).resolve().parents[2]


def normalize_source_path(source: str) -> str:
    """Normalize WLA absolute source paths to repository-relative paths."""
    path = Path(source.replace("\\", "/"))
    if path.is_absolute():
        try:
            return path.resolve().relative_to(REPO_ROOT).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix().removeprefix("./")


def snes_to_pc(address: int) -> int | None:
    """Map LoROM/FastROM ROM addresses; omit WRAM and unmapped low halves."""
    bank, offset = address >> 16, address & 0xFFFF
    if bank in (0x7E, 0x7F):
        return None
    # $40-$6F/$C0-$EF low halves mirror their ROM high halves. Low halves
    # in other banks are RAM, hardware registers, SRAM, or unmapped.
    if offset < 0x8000 and not 0x40 <= (bank & 0x7F) <= 0x6F:
        return None
    return ((bank & 0x7F) << 15) | (offset & 0x7FFF)


def parse_zs_map(map_path: Path) -> list[dict]:
    content = map_path.read_text()
    pattern = (
        r'(0x[0-9A-Fa-f]+)\s*-\s*(0x[0-9A-Fa-f]+):'
        r'\s*\d+\s*Banks?\s*\n[ \t]+([^\n]+)'
    )
    ranges = []
    for match in re.finditer(pattern, content):
        start, end = int(match[1], 16), int(match[2], 16)
        if end < start:
            raise ValueError(f"Reversed ZScream range: {match[0]}")
        ranges.append({"start": start, "end": end, "name": match[3].strip()})
    if not ranges:
        raise ValueError(f"No reserved ranges parsed from {map_path}")
    return ranges


def parse_symbols(symbols_path: Path) -> tuple[dict, list[dict]]:
    """Read full Asar WLA symbols, failing on missing/truncated input."""
    sources, labels, mappings = {}, {}, []
    section = None
    sections = set()
    for number, raw in enumerate(symbols_path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith(";"):
            continue
        if line.startswith("["):
            section = line
            sections.add(section)
            continue
        if section == "[source files]":
            match = re.fullmatch(r'([0-9A-Fa-f]+) [0-9A-Fa-f]+ (.+)', line)
            if match:
                sources[int(match[1], 16)] = normalize_source_path(match[2])
        elif section in ("[labels]", "[addr-to-line mapping]"):
            match = re.fullmatch(r'([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)', line)
            if match:
                address = (int(match[1], 16) << 16) | int(match[2], 16)
                pc = snes_to_pc(address)
                if section == "[labels]":
                    if pc is not None:
                        labels.setdefault(pc, []).append(match[3])
                else:
                    origin = re.fullmatch(r'([0-9A-Fa-f]+):([0-9A-Fa-f]+)', match[3])
                    if origin:
                        mappings.append({"snes": address, "pc": pc,
                                         "source_id": int(origin[1], 16),
                                         "line": int(origin[2], 16)})
                    else:
                        match = None
        else:
            continue
        if not match:
            raise ValueError(f"Malformed {section} entry at {symbols_path}:{number}")

    required = {"[labels]", "[source files]", "[addr-to-line mapping]"}
    if not required <= sections or not sources or not mappings:
        raise ValueError(f"Incomplete Asar WLA symbols: {symbols_path}")
    for item in mappings:
        try:
            item["source"] = sources[item.pop("source_id")]
        except KeyError as exc:
            raise ValueError(f"Unknown source id in {symbols_path}") from exc
    return labels, mappings


def check_overlaps(symbols_path: Path, zs_ranges: list[dict]) -> list[dict]:
    labels, mappings = parse_symbols(symbols_path)
    overlaps = []
    seen = set()
    for item in mappings:
        pc = item["pc"]
        if pc is None:
            continue
        for reserved in zs_ranges:
            if not reserved["start"] <= pc <= reserved["end"]:
                continue
            if any(source == item["source"] and start <= pc <= end
                   for source, start, end in OWNED_REGIONS):
                continue
            key = (pc, item["source"], item["line"])
            if key in seen:
                continue
            seen.add(key)
            overlaps.append({
                "label": ", ".join(labels.get(pc, ["<unlabeled emission>"])),
                "pc": f"0x{pc:06X}",
                "snes": f"0x{item['snes']:06X}",
                "source": f"{item['source']}:{item['line']}",
                "range": f"0x{reserved['start']:06X}-0x{reserved['end']:06X}",
                "system": reserved["name"],
            })
    return overlaps


def main() -> int:
    root = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--symbols", type=Path, default=root / "Roms/oos168x.sym",
                        help="Fresh Asar WLA .sym from the build (default: Roms/oos168x.sym)")
    parser.add_argument("--map", type=Path, default=root / "Core/ZS ROM MAP.txt",
                        help="ZScream reserved PC address map")
    args = parser.parse_args()
    print(f"[*] Checking mapped emission starts in {args.symbols}...")
    try:
        overlaps = check_overlaps(args.symbols, parse_zs_map(args.map))
    except (OSError, ValueError) as exc:
        print(f"[-] Error: {exc}")
        return 1
    if overlaps:
        print(f"[!] {len(overlaps)} unowned emission addresses overlap ZScream reservations:")
        for item in overlaps[:30]:
            print(f"  {item['pc']} (SNES {item['snes']}) {item['label']} "
                  f"[{item['source']}] — {item['system']}")
        if len(overlaps) > 30:
            print(f"  ... {len(overlaps) - 30} additional addresses")
        return 1
    print("[+] No unowned mapped emission starts in ZScream reserved regions.")
    print("    Declared source allocations allowed; byte-span overlap is not checked.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
