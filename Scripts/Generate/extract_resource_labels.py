#!/usr/bin/env python3
"""
Extract unified Oracle resource labels from multiple data sources.

Generates oracle_resource_labels.json with sections:
  room, sprite, item, entrance, overworld_map, music

Sources:
  - Docs/Dev/Planning/oracle_room_labels.json  -> room
  - Sprites/sprite_registry_ids.asm            -> sprite
  - Docs/Technical/sprite_catalog.md           -> sprite (names for catalog)
  - Docs/World/Features/Items/Items.md         -> item
  - Docs/Technical/Sheets/...Rooms and Entrances.csv -> entrance
  - Docs/Dev/Planning/overworld.json           -> overworld_map
  - Core/ram.asm (song bank tables)            -> music

Usage:
  python3 Scripts/extract_resource_labels.py [--validate] [--output PATH]
"""

import argparse
import csv
import json
import os
import re
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Walk up from script dir to find the repo root (contains CLAUDE.md)."""
    p = Path(__file__).resolve().parents[2]
    if (p / "CLAUDE.md").exists():
        return p
    # Fallback: cwd
    return Path.cwd()


# ── Room Labels ──────────────────────────────────────────────────────────────

def extract_room_labels(root: Path) -> dict:
    """Load from existing oracle_room_labels.json."""
    path = root / "Docs" / "Dev" / "Planning" / "oracle_room_labels.json"
    if not path.exists():
        print(f"  WARN: {path} not found, skipping room labels", file=sys.stderr)
        return {}
    with open(path) as f:
        data = json.load(f)
    labels = {}
    if "resource_labels" in data and "room" in data["resource_labels"]:
        labels = data["resource_labels"]["room"]
    return labels


# ── Sprite Labels ────────────────────────────────────────────────────────────

def extract_sprite_labels(root: Path) -> dict:
    """
    Name every sprite slot Oracle reuses.

    Oracle reuses vanilla slots, so yaze needs these names to stop calling
    $52 "ZoraKing". Sources, in order:
      1. Sprites/sprite_registry_ids.asm (generated from registry.csv): every
         registry name for an ID ($07 -> Bean Vendor / Village Elder).
      2. Sprites/**/*.asm with `!SPRID = $XX` and no registry constant: the
         `%Set_Sprite_Properties(..., Sprite_<Name>_Long)` routine name comes
         first ($52 -> Collectible, $11 -> Keese / Vampire Bat).
      3. A slot whose `_Long` routine lives in another file is a dispatcher;
         its routine name comes first ($B8 runs Sprite_Zora_Long from
         zora.asm -> Zora / Zora Princess).
    """
    registry_path = root / "Sprites" / "sprite_registry_ids.asm"
    names: dict[int, list[str]] = {}

    def add(sprite_id: int, raw_name: str, first: bool = False) -> None:
        clean = _clean_sprite_name(raw_name)
        slot = names.setdefault(sprite_id, [])
        if clean in slot:
            return
        if first:
            slot.insert(0, clean)
        else:
            slot.append(clean)

    if not registry_path.exists():
        print(f"  WARN: {registry_path} not found", file=sys.stderr)
        return {}

    # Pattern: Sprite_FarName = $XX  (optional comment)
    constant = re.compile(r"^Sprite_(\w+)\s*=\s*\$([0-9A-Fa-f]{2})", re.MULTILINE)
    constants: dict[str, int] = {}
    for match in constant.finditer(registry_path.read_text()):
        sprite_id = int(match.group(2), 16)
        constants[f"Sprite_{match.group(1)}"] = sprite_id
        add(sprite_id, match.group(1))

    sprid = re.compile(r"^!SPRID\s*=\s*(\$[0-9A-Fa-f]{2}|Sprite_\w+)", re.MULTILINE)
    long_ref = re.compile(r"%Set_Sprite_Properties\(\s*\w+\s*,\s*Sprite_(\w+)_Long\s*\)")
    sources = sorted((root / "Sprites").rglob("*.asm"))
    defined_in = {}
    long_label = re.compile(r"^Sprite_(\w+)_Long:", re.MULTILINE)
    for path in sources:
        for match in long_label.finditer(path.read_text(errors="replace")):
            defined_in.setdefault(match.group(1), path)

    for path in sources:
        text = path.read_text(errors="replace")
        id_match = sprid.search(text)
        routine = long_ref.search(text)
        if not id_match or not routine:
            continue
        value = id_match.group(1)
        if value.startswith("$"):
            sprite_id = int(value[1:], 16)
        elif value in constants:
            sprite_id = constants[value]
        else:
            print(f"  WARN: {path.relative_to(root)}: unknown !SPRID {value}",
                  file=sys.stderr)
            continue
        routine_name = routine.group(1)
        dispatcher = defined_in.get(routine_name, path) != path
        if dispatcher or value.startswith("$"):
            add(sprite_id, routine_name, first=True)  # the slot's main routine

    return {f"0x{sprite_id:02X}": " / ".join(slot)
            for sprite_id, slot in sorted(names.items())}


def _clean_sprite_name(raw: str) -> str:
    """Convert CamelCase ASM label to human-readable: KydrogBoss -> Kydrog Boss."""
    # Insert space before transitions: lowercase->uppercase or uppercase->uppercase+lowercase
    spaced = re.sub(r"(?<=[a-z])(?=[A-Z])", " ", raw)
    spaced = re.sub(r"(?<=[A-Z]{2})(?=[A-Z][a-z])", " ", spaced)
    # Common acronym fixes
    spaced = spaced.replace("NP Cs", "NPCs")
    return spaced


# ── Item Labels ──────────────────────────────────────────────────────────────

# Vanilla ALTTP item IDs that Oracle modifies or adds
# Extracted from Items.md documentation + vanilla item table
ITEM_LABELS = {
    "0x00": "Fighter Sword / Shield",
    "0x01": "Master Sword",
    "0x02": "Tempered Sword",
    "0x03": "Golden Sword",
    "0x04": "Fighter Shield",
    "0x05": "Fire Shield",
    "0x06": "Mirror Shield",
    "0x07": "Fire Rod",
    "0x08": "Ice Rod",
    "0x09": "Hammer",
    "0x0A": "Goldstar / Hookshot",
    "0x0B": "Bow",
    "0x0C": "Boomerang",
    "0x0D": "Powder",
    "0x0E": "Bee (Bottle)",
    "0x0F": "Bombos",
    "0x10": "Ether",
    "0x11": "Quake",
    "0x12": "Lamp",
    "0x13": "Shovel",
    "0x14": "Ocarina",
    "0x15": "Roc's Feather",
    "0x16": "Book of Secrets",
    "0x17": "Bottle",
    "0x18": "Cane of Somaria",
    "0x19": "Cane of Byrna",
    "0x1A": "Magic Cape",
    "0x1B": "Magic Mirror / Mirror of Time",
    "0x1C": "Portal Rod / Fishing Rod",
    "0x1D": "Bombs (1)",
    "0x1E": "Mushroom",
    "0x1F": "Red Boomerang",
    "0x20": "Red Potion (Bottle)",
    "0x21": "Green Potion (Bottle)",
    "0x22": "Blue Potion (Bottle)",
    "0x23": "Red Potion",
    "0x24": "Green Potion",
    "0x25": "Blue Potion",
    "0x26": "Bombs (10)",
    "0x27": "Arrows (3)",
    "0x28": "Arrows (10)",
    "0x29": "Ether Magic",
    "0x2A": "Bombs (30)",
    "0x2B": "Arrows (30)",
    "0x2C": "Silver Arrows",
    "0x2D": "Rupees (20)",
    "0x2E": "Pendant of Courage",
    "0x2F": "Pendant of Power",
    "0x30": "Pendant of Wisdom",
    "0x31": "Bow and Silver Arrows",
    "0x32": "Bottle (Medicine)",
    "0x33": "Fairy (Bottle)",
    "0x34": "Heart Container",
    "0x35": "Heart Container (Sanctuary)",
    "0x36": "Rupees (100)",
    "0x37": "Rupees (50)",
    "0x38": "Heart",
    "0x39": "Arrow",
    "0x3A": "Magic (10)",
    "0x3B": "Rupees (300)",
    "0x3C": "Rupees (20)",
    "0x3D": "Bee (Good)",
    "0x3E": "Crystal",
    "0x3F": "Map",
    "0x40": "Compass",
    "0x41": "Big Key",
    "0x42": "Small Key",
    "0x43": "Piece of Heart",
    "0x44": "Zora Mask",
    "0x45": "Deku Mask",
    "0x46": "Bunny Hood",
    "0x47": "Stone Mask",
    "0x48": "Wolf Mask",
    "0x49": "Minish Mask",
}


def extract_item_labels(root: Path) -> dict:
    """Return hardcoded item labels (derived from Items.md analysis)."""
    return dict(ITEM_LABELS)


# ── Entrance Labels ──────────────────────────────────────────────────────────

def extract_entrance_labels(root: Path) -> dict:
    """Parse the Rooms and Entrances CSV for entrance ID -> name mapping."""
    csv_path = (
        root / "Docs" / "Technical" / "Sheets"
        / "Oracle of Secrets Data Sheet - Rooms and Entrances.csv"
    )
    if not csv_path.exists():
        print(f"  WARN: {csv_path} not found", file=sys.stderr)
        return {}

    labels = {}
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if not header:
            return labels

        for row in reader:
            if len(row) < 2:
                continue
            entrance_id_str = row[0].strip()
            entrance_name = row[1].strip()
            if not entrance_id_str or not entrance_name:
                continue

            # Convert hex ID to 0xXX format
            try:
                eid = int(entrance_id_str, 16)
                key = f"0x{eid:02X}"
                labels[key] = entrance_name
            except ValueError:
                continue

    return labels


# ── Overworld Map Labels ─────────────────────────────────────────────────────

def extract_overworld_labels(root: Path) -> dict:
    """Load from existing overworld.json."""
    path = root / "Docs" / "Dev" / "Planning" / "overworld.json"
    if not path.exists():
        print(f"  WARN: {path} not found", file=sys.stderr)
        return {}

    with open(path) as f:
        data = json.load(f)

    labels = {}
    for area in data.get("areas", []):
        area_id = area.get("area_id", "")
        name = area.get("name", "")
        if area_id and name:
            labels[area_id] = name

    return labels


# ── Music Labels ─────────────────────────────────────────────────────────────

# From ram.asm song bank tables + code analysis
MUSIC_LABELS = {
    # Overworld bank
    "0x01": "Triforce Opening",
    "0x02": "Light World Overture",
    "0x03": "Rain / Deku Tree Theme",
    "0x04": "Bunny Link",
    "0x05": "Kalyxo Village",
    "0x06": "Legends Theme (Attract)",
    "0x07": "Kakariko Village",
    "0x08": "Mirror Warp",
    "0x09": "Dark World (Eon Abyss)",
    "0x0A": "Pulling the Master Sword",
    "0x0B": "Fairy Theme",
    "0x0C": "Chase / Fugitive",
    "0x0D": "Skull Woods March",
    "0x0E": "Minigame Theme",
    "0x0F": "Intro Fanfare",
    # Underworld bank
    "0x10": "Hyrule Castle",
    "0x11": "Light World Dungeon",
    "0x12": "Cave Theme",
    "0x13": "Boss Fanfare",
    "0x14": "Sanctuary / Hall of Secrets",
    "0x15": "Boss Battle",
    "0x16": "Dark World Dungeon",
    "0x17": "Fortune Teller",
    "0x18": "Cave Theme (Alt)",
    "0x19": "Zelda Rescue",
    "0x1A": "Crystal Theme",
    "0x1B": "Fairy Theme (Arpeggio)",
    "0x1C": "Pre-Agahnim",
    "0x1D": "Agahnim Escape",
    "0x1E": "Pre-Ganon",
    "0x1F": "Ganondorf the Thief",
    # Special commands
    "0xF1": "Fade Out",
}


def extract_music_labels(root: Path) -> dict:
    """Return music labels (derived from ram.asm analysis)."""
    return dict(MUSIC_LABELS)


# ── Main Pipeline ────────────────────────────────────────────────────────────

def build_resource_labels(root: Path) -> dict:
    """Aggregate all resource label sources into unified structure."""
    print("Extracting resource labels...")

    labels = {
        "_meta": {
            "generated_by": "Scripts/Generate/extract_resource_labels.py",
            "description": "Unified Oracle of Secrets resource labels for yaze integration",
            "sources": [
                "Docs/Dev/Planning/oracle_room_labels.json",
                "Sprites/sprite_registry_ids.asm",
                "Docs/Technical/Sheets/Oracle of Secrets Data Sheet - Rooms and Entrances.csv",
                "Docs/Dev/Planning/overworld.json",
                "Core/ram.asm (song bank tables)",
                "Docs/World/Features/Items/Items.md (manual extraction)",
            ],
        },
    }

    for section_name, extractor in SECTION_EXTRACTORS.items():
        data = extractor(root)
        labels[section_name] = data
        print(f"  {section_name}: {len(data)} entries")

    return labels


SECTION_EXTRACTORS = {
    "room": extract_room_labels,
    "sprite": extract_sprite_labels,
    "item": extract_item_labels,
    "entrance": extract_entrance_labels,
    "overworld_map": extract_overworld_labels,
    "music": extract_music_labels,
}


def validate_labels(labels: dict) -> bool:
    """Check schema validity of generated labels."""
    ok = True
    required_sections = ["room", "sprite", "item", "entrance", "overworld_map", "music"]

    for section in required_sections:
        if section not in labels:
            print(f"  ERROR: Missing section '{section}'", file=sys.stderr)
            ok = False
            continue
        if not isinstance(labels[section], dict):
            print(f"  ERROR: Section '{section}' is not a dict", file=sys.stderr)
            ok = False
            continue
        # Check all keys are 0xXX format
        for key in labels[section]:
            if not re.match(r"^0x[0-9A-Fa-f]+$", key):
                print(
                    f"  ERROR: Invalid key '{key}' in section '{section}'",
                    file=sys.stderr,
                )
                ok = False
        # Check all values are non-empty strings
        for key, val in labels[section].items():
            if not isinstance(val, str) or not val.strip():
                print(
                    f"  ERROR: Empty or non-string value for '{key}' in '{section}'",
                    file=sys.stderr,
                )
                ok = False

    # Minimum counts
    minimums = {"room": 100, "sprite": 20, "item": 30, "entrance": 30, "overworld_map": 30, "music": 15}
    for section, minimum in minimums.items():
        if section in labels and len(labels[section]) < minimum:
            print(
                f"  WARN: Section '{section}' has only {len(labels[section])} entries "
                f"(expected >= {minimum})",
                file=sys.stderr,
            )

    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: Docs/Dev/Planning/oracle_resource_labels.json)",
    )
    parser.add_argument(
        "--only",
        choices=["room", "sprite", "item", "entrance", "overworld_map", "music"],
        help="Regenerate one section and keep the others from the existing output",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing output without regenerating",
    )
    args = parser.parse_args()

    root = find_project_root()
    default_output = root / "Docs" / "Dev" / "Planning" / "oracle_resource_labels.json"
    output_path = Path(args.output) if args.output else default_output

    if args.validate:
        if not output_path.exists():
            print(f"ERROR: {output_path} does not exist", file=sys.stderr)
            sys.exit(1)
        with open(output_path) as f:
            labels = json.load(f)
        ok = validate_labels(labels)
        if ok:
            print("Validation passed.")
        else:
            print("Validation FAILED.", file=sys.stderr)
            sys.exit(1)
        return

    if args.only:
        if not output_path.exists():
            print(f"ERROR: --only needs an existing {output_path}", file=sys.stderr)
            sys.exit(1)
        with open(output_path) as f:
            labels = json.load(f)
        labels[args.only] = SECTION_EXTRACTORS[args.only](root)
        print(f"  {args.only}: {len(labels[args.only])} entries")
    else:
        labels = build_resource_labels(root)
    ok = validate_labels(labels)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(labels, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {output_path}")
    if not ok:
        print("WARNING: Validation issues detected (see above)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
