#!/usr/bin/env python3
"""Extract overworld area registry from Oracle of Secrets data sources.

Consolidates data from:
  - Docs/Planning/world_map_diagram.md (area names, grid coords, features)
  - Docs/Technical/Sheets/...Overworld GFX.csv (GFX ID per area)
  - Docs/Technical/Sheets/...Overworld Spr.csv (sprite set per area)
  - Docs/Planning/overworld_item_inventory.json (items per area)
  - Docs/Dev/Planning/dungeons.json (dungeon→overworld screen links)

Output: Docs/Dev/Planning/overworld.json
"""

import argparse
import csv
import json
import os
import re
import sys
from collections import defaultdict
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent


def parse_named_locations_table(lines, start_line, world):
    """Parse a markdown table of named locations into area dicts.

    Handles both LW format (with Size column) and DW format (without Size).
    """
    areas = {}
    header_found = False
    for line in lines[start_line:]:
        line = line.strip()
        if not line.startswith("|"):
            if header_found:
                break
            continue
        # Skip header separator
        if re.match(r"^\|[-\s|]+\|$", line):
            header_found = True
            continue
        if not header_found:
            continue

        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 3:
            continue

        screen_str = cols[0].strip()
        hex_str = cols[1].strip().strip("`")
        name = cols[2].strip()
        features = cols[-1].strip() if len(cols) >= 4 else ""

        if not name:
            continue

        # Use hex_str if available, otherwise fall back to screen_str
        parse_str = hex_str if hex_str else screen_str
        if not parse_str:
            continue

        # Handle range entries like "0x40-41" or "0x43-47, 4D-4F, 55-57"
        area_ids = _parse_screen_ranges(parse_str)
        if not area_ids:
            continue

        for area_id in area_ids:
            row = area_id // 8
            col = area_id % 8
            if world == "DW":
                row = (area_id - 0x40) // 8
                col = (area_id - 0x40) % 8
            elif world == "SW":
                row = (area_id - 0x80) // 8
                col = (area_id - 0x80) % 8

            notable = []
            if features:
                # Extract **D5 Entrance** style markers
                for m in re.finditer(r"\*\*([^*]+)\*\*", features):
                    notable.append(m.group(1))
                if not notable and features:
                    notable.append(features)

            areas[area_id] = {
                "area_id": f"0x{area_id:02X}",
                "name": name,
                "world": world,
                "grid_row": row,
                "grid_col": col,
                "notable_features": notable,
            }

    return areas


def _parse_screen_ranges(screen_str):
    """Parse screen identifiers like '0x40-41' or '0x43-47, 4D-4F, 55-57'."""
    area_ids = []
    # Match single hex IDs like "0x10" or "0x0B"
    single_match = re.match(r"^0x([0-9A-Fa-f]{2})$", screen_str.strip())
    if single_match:
        return [int(single_match.group(1), 16)]

    # Match ranges like "0x40-41" or compound "0x43-47, 4D-4F, 55-57"
    parts = re.split(r",\s*", screen_str)
    for part in parts:
        part = part.strip()
        range_match = re.match(
            r"(?:0x)?([0-9A-Fa-f]{2})-([0-9A-Fa-f]{2})", part
        )
        if range_match:
            start = int(range_match.group(1), 16)
            end = int(range_match.group(2), 16)
            # Handle cases like "40-41" where end < start prefix
            if end < start:
                # "40-41" means 0x40 to 0x41
                # "43-47" means 0x43 to 0x47
                end = (start & 0xF0) | end
            for i in range(start, end + 1):
                area_ids.append(i)
        else:
            hex_match = re.match(r"(?:0x)?([0-9A-Fa-f]{2})", part)
            if hex_match:
                area_ids.append(int(hex_match.group(1), 16))

    return area_ids


def parse_grid_names(lines, start_line, world_offset):
    """Parse the ASCII grid to extract area names as fallback.

    Each cell spans 3 lines of content between box-drawing borders.
    """
    areas = {}
    grid_lines = []
    in_grid = False

    for line in lines[start_line:]:
        if line.strip().startswith("```") and not in_grid:
            in_grid = True
            continue
        if line.strip().startswith("```") and in_grid:
            break
        if in_grid:
            grid_lines.append(line.rstrip())

    if not grid_lines:
        return areas

    # Parse rows: each row has 3 content lines between borders
    current_row = -1
    row_names = {}  # col -> list of text lines

    for line in grid_lines:
        # Skip the column header line
        if re.match(r"^\s+\d", line):
            continue

        # Row border line with row number
        row_num_match = re.match(r"^\s*(\d+)\s*│", line)
        if row_num_match:
            current_row = int(row_num_match.group(1))
            if current_row not in row_names:
                row_names[current_row] = defaultdict(list)

        # Row indicator without leading number (continuation line)
        if "│" in line and current_row >= 0:
            cells = line.split("│")
            # First cell might have the row number, skip it
            for col_idx, cell in enumerate(cells[1:], 0):
                text = cell.strip()
                if text and not re.match(r"^[┌┬┐├┼┤└┴┘─]+$", text):
                    # Skip pure border characters
                    if col_idx < 8:
                        row_names[current_row][col_idx].append(text)

    # Build area entries from parsed names
    for row, cols in row_names.items():
        for col, text_lines in cols.items():
            area_id = world_offset + row * 8 + col
            name = " ".join(
                t for t in text_lines if not re.match(r"^D\d$|^S\d$", t)
            ).strip()
            dungeon_ref = None
            for t in text_lines:
                dm = re.match(r"^(D\d|S\d)$", t.strip())
                if dm:
                    dungeon_ref = dm.group(1)

            if name and area_id not in areas:
                areas[area_id] = {
                    "area_id": f"0x{area_id:02X}",
                    "name": name,
                    "world": (
                        "LW"
                        if world_offset == 0
                        else ("DW" if world_offset == 0x40 else "SW")
                    ),
                    "grid_row": row,
                    "grid_col": col,
                    "notable_features": (
                        [f"{dungeon_ref} Entrance"] if dungeon_ref else []
                    ),
                }

    return areas


def parse_gfx_csv(filepath):
    """Parse Overworld GFX CSV. Lines 3-10 contain the 8x8 grid values."""
    gfx_map = {}
    if not filepath.exists():
        return gfx_map

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # LW grid: rows 2-9 (0-indexed), columns 0-7
    for row_idx in range(2, 10):
        if row_idx >= len(rows):
            break
        row = rows[row_idx]
        for col_idx in range(8):
            if col_idx >= len(row):
                break
            val = row[col_idx].strip()
            if val:
                try:
                    gfx_id = int(val, 16)
                    area_id = (row_idx - 2) * 8 + col_idx
                    gfx_map[area_id] = f"0x{gfx_id:02X}"
                except ValueError:
                    pass

    # DW grid: rows 2-9, columns 9-16
    for row_idx in range(2, 10):
        if row_idx >= len(rows):
            break
        row = rows[row_idx]
        for col_idx in range(9, 17):
            if col_idx >= len(row):
                break
            val = row[col_idx].strip()
            if val:
                try:
                    gfx_id = int(val, 16)
                    area_id = 0x40 + (row_idx - 2) * 8 + (col_idx - 9)
                    gfx_map[area_id] = f"0x{gfx_id:02X}"
                except ValueError:
                    pass

    return gfx_map


def parse_sprite_csv(filepath):
    """Parse Overworld Spr CSV. Same layout as GFX."""
    spr_map = {}
    if not filepath.exists():
        return spr_map

    with open(filepath, "r") as f:
        reader = csv.reader(f)
        rows = list(reader)

    # LW grid: rows 2-9, columns 0-7
    for row_idx in range(2, 10):
        if row_idx >= len(rows):
            break
        row = rows[row_idx]
        for col_idx in range(8):
            if col_idx >= len(row):
                break
            val = row[col_idx].strip()
            if val:
                try:
                    spr_id = int(val, 16)
                    area_id = (row_idx - 2) * 8 + col_idx
                    spr_map[area_id] = f"0x{spr_id:02X}"
                except ValueError:
                    pass

    # DW grid: rows 2-9, columns 9-16
    for row_idx in range(2, 10):
        if row_idx >= len(rows):
            break
        row = rows[row_idx]
        for col_idx in range(9, 17):
            if col_idx >= len(row):
                break
            val = row[col_idx].strip()
            if val:
                try:
                    spr_id = int(val, 16)
                    area_id = 0x40 + (row_idx - 2) * 8 + (col_idx - 9)
                    spr_map[area_id] = f"0x{spr_id:02X}"
                except ValueError:
                    pass

    return spr_map


def parse_item_inventory(filepath):
    """Parse overworld_item_inventory.json, grouping by map_id."""
    items_by_area = defaultdict(list)
    if not filepath.exists():
        return items_by_area

    with open(filepath, "r") as f:
        data = json.load(f)

    for item in data.get("items", []):
        map_id_str = item.get("map_id", "")
        if not map_id_str:
            continue
        try:
            area_id = int(map_id_str, 16)
        except ValueError:
            continue

        entry = {
            "item_id": item.get("item_id", ""),
            "tile_pos": item.get("tile_pos", ""),
        }
        name = item.get("item_name", "")
        if name:
            entry["item_name"] = name
        items_by_area[area_id].append(entry)

    return items_by_area


def parse_dungeon_entrances(filepath):
    """Extract overworld_entrances from dungeons.json."""
    entrance_map = defaultdict(list)  # area_id -> list of entrance info
    if not filepath.exists():
        return entrance_map

    with open(filepath, "r") as f:
        data = json.load(f)

    for dungeon in data.get("dungeons", []):
        dungeon_id = dungeon.get("id", "")
        dungeon_name = dungeon.get("name", "")
        for ent in dungeon.get("overworld_entrances", []):
            # Field is "overworld_area": "0x10 Toadstool Woods"
            ow_area = ent.get("overworld_area", "")
            hex_match = re.match(r"0x([0-9A-Fa-f]+)", ow_area)
            if not hex_match:
                continue
            try:
                area_id = int(hex_match.group(1), 16)
            except ValueError:
                continue

            entrance_map[area_id].append(
                {
                    "entrance_id": ent.get("entrance_id", ""),
                    "room_name": ent.get("room_id", dungeon_name),
                    "dungeon_id": dungeon_id,
                }
            )

    return entrance_map


def parse_npc_locations(lines):
    """Parse NPC placement tables from world_map_diagram.md."""
    npc_map = defaultdict(list)  # area_id -> list of NPC names

    in_npc_section = False
    for line in lines:
        if "### Light World NPCs" in line or "### Eon Abyss NPCs" in line:
            in_npc_section = True
            continue
        if in_npc_section and line.startswith("##"):
            in_npc_section = False
            continue
        if not in_npc_section or not line.startswith("|"):
            continue
        if re.match(r"^\|[-\s|]+\|$", line):
            continue

        cols = [c.strip() for c in line.split("|")[1:-1]]
        if len(cols) < 2:
            continue

        screen_str = cols[0].strip()
        npcs_str = cols[1].strip()

        # Extract hex from "0x00 Ranch" or "0x1E Zora Sanctuary"
        hex_match = re.match(r"0x([0-9A-Fa-f]{2})", screen_str)
        if not hex_match:
            continue

        area_id = int(hex_match.group(1), 16)
        if npcs_str:
            # Split NPC names by comma
            for npc in npcs_str.split(","):
                npc = npc.strip()
                if npc:
                    npc_map[area_id].append(npc)

    return npc_map


def build_overworld_registry(project_root):
    """Build the complete overworld registry from all sources."""
    docs = project_root / "Docs"
    planning = docs / "Planning"
    sheets = docs / "Technical" / "Sheets"
    dev_planning = docs / "Dev" / "Planning"

    # 1. Parse world_map_diagram.md
    diagram_path = planning / "world_map_diagram.md"
    with open(diagram_path, "r") as f:
        diagram_lines = f.readlines()

    # Find section starts
    lw_named_start = None
    dw_named_start = None
    lw_grid_start = None
    dw_grid_start = None
    sw_grid_start = None
    sw_special_start = None

    for i, line in enumerate(diagram_lines):
        if "### Named Locations (Light World)" in line:
            lw_named_start = i + 1
        elif "### Named Locations (Eon Abyss)" in line:
            dw_named_start = i + 1
        elif "### Grid Layout (8x8 = 64 screens)" in line:
            if "Kalyxo" in diagram_lines[max(0, i - 5) : i][-1] if i > 0 else "":
                lw_grid_start = i + 1
            elif lw_grid_start is None:
                lw_grid_start = i + 1
            else:
                dw_grid_start = i + 1
        elif "### Grid Layout (8x4 = 32 screens)" in line:
            sw_grid_start = i + 1
        elif "### Special Area Registry" in line:
            sw_special_start = i + 1

    # Parse named locations (primary source for names)
    areas = {}
    if lw_named_start:
        areas.update(parse_named_locations_table(diagram_lines, lw_named_start, "LW"))
    if dw_named_start:
        areas.update(parse_named_locations_table(diagram_lines, dw_named_start, "DW"))

    # Parse grids as fallback for unnamed areas
    if lw_grid_start:
        grid_areas = parse_grid_names(diagram_lines, lw_grid_start, 0x00)
        for aid, info in grid_areas.items():
            if aid not in areas:
                areas[aid] = info

    if dw_grid_start:
        grid_areas = parse_grid_names(diagram_lines, dw_grid_start, 0x40)
        for aid, info in grid_areas.items():
            if aid not in areas:
                areas[aid] = info

    if sw_grid_start:
        grid_areas = parse_grid_names(diagram_lines, sw_grid_start, 0x80)
        for aid, info in grid_areas.items():
            if aid not in areas:
                areas[aid] = info

    # Parse special area registry table
    if sw_special_start:
        for line in diagram_lines[sw_special_start:]:
            if not line.startswith("|"):
                if "###" in line:
                    break
                continue
            if re.match(r"^\|[-\s|]+\|$", line):
                continue
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) < 4:
                continue
            hex_str = cols[1].strip().strip("`")
            name = cols[2].strip()
            if not hex_str or not name:
                continue
            try:
                aid = int(hex_str, 16)
            except ValueError:
                continue
            # SW entries with IDs >= 0x100 are entrance IDs, skip
            if aid > 0xFF:
                continue
            if aid not in areas:
                areas[aid] = {
                    "area_id": f"0x{aid:02X}",
                    "name": name,
                    "world": "SW",
                    "grid_row": (aid - 0x80) // 8,
                    "grid_col": (aid - 0x80) % 8,
                    "notable_features": [],
                }

    # 2. Parse GFX and sprite CSVs
    gfx_csv = next(sheets.glob("*Overworld GFX*"), None)
    spr_csv = next(sheets.glob("*Overworld Spr*"), None)
    gfx_map = parse_gfx_csv(gfx_csv) if gfx_csv else {}
    spr_map = parse_sprite_csv(spr_csv) if spr_csv else {}

    # 3. Parse item inventory
    items_by_area = parse_item_inventory(
        planning / "overworld_item_inventory.json"
    )

    # 4. Parse dungeon entrances
    entrance_map = parse_dungeon_entrances(dev_planning / "dungeons.json")

    # 5. Parse NPC locations
    npc_map = parse_npc_locations(diagram_lines)

    # 6. Merge all data
    for aid, area in areas.items():
        if aid in gfx_map:
            area["gfx_id"] = gfx_map[aid]
        if aid in spr_map:
            area["sprite_set"] = spr_map[aid]
        if aid in items_by_area:
            area["items"] = items_by_area[aid]
        if aid in entrance_map:
            area["entrances"] = entrance_map[aid]
        if aid in npc_map:
            area["npcs"] = npc_map[aid]

    # Build output
    registry = {
        "_meta": {
            "generated_by": "scripts/extract_overworld_registry.py",
            "description": "Oracle of Secrets overworld area registry",
            "notes": [
                "Primary source: Docs/Planning/world_map_diagram.md",
                "GFX/Sprite data from CSV sheets",
                "Items from overworld_item_inventory.json",
                "Dungeon entrances from dungeons.json",
                "area_id formula: LW=row*8+col, DW=0x40+row*8+col, SW=0x80+row*8+col",
            ],
        },
        "worlds": [
            {"id": "LW", "name": "Kalyxo Island", "range": "0x00-0x3F"},
            {"id": "DW", "name": "Eon Abyss", "range": "0x40-0x7F"},
            {"id": "SW", "name": "Special World", "range": "0x80-0x9F"},
        ],
        "areas": sorted(areas.values(), key=lambda a: int(a["area_id"], 16)),
    }

    return registry


def main():
    parser = argparse.ArgumentParser(
        description="Extract Oracle of Secrets overworld area registry"
    )
    parser.add_argument(
        "--format",
        choices=["json"],
        default="json",
        help="Output format",
    )
    parser.add_argument(
        "--output",
        default=str(PROJECT_ROOT / "Docs" / "Dev" / "Planning" / "overworld.json"),
        help="Output file path",
    )
    parser.add_argument(
        "--project-root",
        default=str(PROJECT_ROOT),
        help="Project root directory",
    )
    args = parser.parse_args()

    root = Path(args.project_root)
    registry = build_overworld_registry(root)

    # Stats
    lw_count = sum(1 for a in registry["areas"] if a["world"] == "LW")
    dw_count = sum(1 for a in registry["areas"] if a["world"] == "DW")
    sw_count = sum(1 for a in registry["areas"] if a["world"] == "SW")
    with_entrances = sum(1 for a in registry["areas"] if "entrances" in a)

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)
        f.write("\n")

    print(f"Wrote {output_path}")
    print(
        f"  Areas: {len(registry['areas'])} "
        f"(LW={lw_count}, DW={dw_count}, SW={sw_count})"
    )
    print(f"  With dungeon entrances: {with_entrances}")
    print(f"  With items: {sum(1 for a in registry['areas'] if 'items' in a)}")
    print(f"  With NPCs: {sum(1 for a in registry['areas'] if 'npcs' in a)}")


if __name__ == "__main__":
    main()
