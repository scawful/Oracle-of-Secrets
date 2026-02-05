#!/usr/bin/env python3
"""
Analyze dungeon progression and difficulty from the location registry.

This script reads the canonical location_registry.json and generates
a progression analysis report showing:
- Dungeon order and difficulty
- Item gates (what items are required to access each dungeon)
- Room statistics per dungeon
- Progression flow graph

Usage:
    python3 scripts/analyze_progression.py [--format=text|md|json]
"""

import json
import sys
from pathlib import Path
from typing import Optional

SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
REGISTRY_PATH = PROJECT_ROOT / "Data" / "location_registry.json"


def load_registry() -> dict:
    """Load the location registry JSON."""
    with open(REGISTRY_PATH) as f:
        return json.load(f)


def analyze_dungeons(registry: dict) -> list:
    """Analyze dungeon statistics and return sorted by order."""
    dungeons = []

    for key, dungeon in registry.get("dungeons", {}).items():
        difficulty = dungeon.get("difficulty", {})
        rooms = dungeon.get("rooms", {})

        # Count special rooms
        boss_rooms = sum(1 for r in rooms.values() if r.get("is_boss"))
        miniboss_rooms = sum(1 for r in rooms.values() if r.get("is_miniboss"))
        chest_rooms = sum(1 for r in rooms.values() if r.get("is_big_chest"))

        # Count tracks (minecart rails, etc.)
        total_tracks = sum(r.get("tracks", 0) for r in rooms.values())
        track_heavy_rooms = sum(1 for r in rooms.values() if r.get("tracks", 0) > 30)

        # Count floors
        floors = dungeon.get("floors", ["F1"])

        dungeons.append({
            "key": key,
            "name": dungeon["name"],
            "dungeon_id": dungeon.get("dungeon_id"),
            "order": difficulty.get("order", 99),
            "enemy_level": difficulty.get("enemy_level", "unknown"),
            "puzzle_complexity": difficulty.get("puzzle_complexity", "unknown"),
            "required_items": difficulty.get("required_items", []),
            "room_count": len(rooms),
            "floor_count": len(floors),
            "floors": floors,
            "boss": dungeon.get("boss", {}).get("name", "TBD"),
            "boss_room": dungeon.get("boss", {}).get("room"),
            "miniboss": dungeon.get("miniboss", {}).get("name") if dungeon.get("miniboss") else None,
            "dungeon_item": dungeon.get("dungeon_item", "TBD"),
            "theme": dungeon.get("theme", "unknown"),
            "total_tracks": total_tracks,
            "track_heavy_rooms": track_heavy_rooms,
            "has_connections": any(r.get("connections") for r in rooms.values()),
        })

    return sorted(dungeons, key=lambda d: d["order"])


def analyze_shrines(registry: dict) -> list:
    """Analyze shrine statistics."""
    shrines = []
    for key, shrine in registry.get("shrines", {}).items():
        shrines.append({
            "key": key,
            "name": shrine["name"],
            "room_count": len(shrine.get("rooms", [])),
            "theme": shrine.get("theme", "unknown"),
        })
    return shrines


def analyze_caves(registry: dict) -> list:
    """Analyze cave statistics."""
    caves = []
    for key, cave in registry.get("caves", {}).items():
        caves.append({
            "key": key,
            "name": cave["name"],
            "room_count": len(cave.get("rooms", [])),
        })
    return caves


def generate_text_report(registry: dict) -> str:
    """Generate a text format progression report."""
    lines = []

    lines.append("=" * 70)
    lines.append("  ORACLE OF SECRETS - PROGRESSION ANALYSIS")
    lines.append("=" * 70)
    lines.append("")

    # Dungeon Progression
    dungeons = analyze_dungeons(registry)

    lines.append("DUNGEON PROGRESSION ORDER")
    lines.append("-" * 70)
    lines.append("")

    for d in dungeons:
        lines.append(f"  {d['order']}. {d['name']} ({d['dungeon_id']})")
        lines.append(f"     Theme: {d['theme']}")
        lines.append(f"     Rooms: {d['room_count']} | Floors: {d['floor_count']} ({', '.join(d['floors'])})")
        lines.append(f"     Enemy Level: {d['enemy_level']} | Puzzles: {d['puzzle_complexity']}")
        if d['required_items']:
            lines.append(f"     REQUIRED ITEMS: {', '.join(d['required_items'])}")
        lines.append(f"     Boss: {d['boss']}" + (f" in Room {d['boss_room']}" if d['boss_room'] else ""))
        if d['miniboss']:
            lines.append(f"     Miniboss: {d['miniboss']}")
        lines.append(f"     Dungeon Item: {d['dungeon_item']}")
        if d['total_tracks'] > 0:
            lines.append(f"     Minecart Tracks: {d['total_tracks']} ({d['track_heavy_rooms']} track-heavy rooms)")
        lines.append("")

    # Item Gates Summary
    lines.append("")
    lines.append("ITEM GATES (Required items for dungeon access)")
    lines.append("-" * 70)
    item_gates = registry.get("progression", {}).get("item_gates", {})
    if item_gates:
        for dungeon_key, items in item_gates.items():
            dungeon_name = next((d["name"] for d in dungeons if d["key"] == dungeon_key), dungeon_key)
            lines.append(f"  {dungeon_name}: {', '.join(items)}")
    else:
        lines.append("  No item gates defined")
    lines.append("")

    # Shrines
    shrines = analyze_shrines(registry)
    lines.append("")
    lines.append("SHRINES")
    lines.append("-" * 70)
    for s in shrines:
        lines.append(f"  {s['name']}: {s['room_count']} rooms ({s['theme']} theme)")
    lines.append("")

    # Caves
    caves = analyze_caves(registry)
    lines.append("")
    lines.append("CAVES")
    lines.append("-" * 70)
    for c in caves:
        lines.append(f"  {c['name']}: {c['room_count']} rooms")
    lines.append("")

    # Summary Statistics
    lines.append("")
    lines.append("SUMMARY STATISTICS")
    lines.append("-" * 70)
    total_dungeon_rooms = sum(d["room_count"] for d in dungeons)
    total_shrine_rooms = sum(s["room_count"] for s in shrines)
    total_cave_rooms = sum(c["room_count"] for c in caves)
    total_houses = len(registry.get("houses", {}))
    total_special = sum(len(s.get("rooms", [])) for s in registry.get("special", {}).values())

    lines.append(f"  Dungeons: {len(dungeons)} ({total_dungeon_rooms} rooms)")
    lines.append(f"  Shrines: {len(shrines)} ({total_shrine_rooms} rooms)")
    lines.append(f"  Caves: {len(caves)} ({total_cave_rooms} rooms)")
    lines.append(f"  Houses: {total_houses}")
    lines.append(f"  Special Areas: {len(registry.get('special', {}))} ({total_special} rooms)")
    lines.append(f"  Total Interior Rooms: {total_dungeon_rooms + total_shrine_rooms + total_cave_rooms + total_special}")
    lines.append("")

    return "\n".join(lines)


def generate_markdown_report(registry: dict) -> str:
    """Generate a Markdown format progression report."""
    lines = []

    lines.append("# Oracle of Secrets - Progression Analysis")
    lines.append("")

    # Dungeon Progression Table
    dungeons = analyze_dungeons(registry)

    lines.append("## Dungeon Progression")
    lines.append("")
    lines.append("| # | Dungeon | Theme | Rooms | Floors | Enemy | Puzzles | Required Items |")
    lines.append("|---|---------|-------|-------|--------|-------|---------|----------------|")

    for d in dungeons:
        required = ", ".join(d["required_items"]) if d["required_items"] else "-"
        lines.append(f"| {d['order']} | {d['name']} | {d['theme']} | {d['room_count']} | {d['floor_count']} | {d['enemy_level']} | {d['puzzle_complexity']} | {required} |")

    lines.append("")

    # Boss and Items Table
    lines.append("## Bosses and Dungeon Items")
    lines.append("")
    lines.append("| Dungeon | Boss | Miniboss | Dungeon Item |")
    lines.append("|---------|------|----------|--------------|")

    for d in dungeons:
        miniboss = d["miniboss"] if d["miniboss"] else "-"
        lines.append(f"| {d['name']} | {d['boss']} | {miniboss} | {d['dungeon_item']} |")

    lines.append("")

    # Shrines
    shrines = analyze_shrines(registry)
    lines.append("## Shrines")
    lines.append("")
    lines.append("| Shrine | Rooms | Theme |")
    lines.append("|--------|-------|-------|")
    for s in shrines:
        lines.append(f"| {s['name']} | {s['room_count']} | {s['theme']} |")
    lines.append("")

    # Summary
    total_dungeon_rooms = sum(d["room_count"] for d in dungeons)
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total Dungeons:** {len(dungeons)}")
    lines.append(f"- **Total Dungeon Rooms:** {total_dungeon_rooms}")
    lines.append(f"- **Total Shrines:** {len(shrines)}")
    lines.append(f"- **Total Caves:** {len(analyze_caves(registry))}")
    lines.append("")

    return "\n".join(lines)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Analyze dungeon progression")
    parser.add_argument("--format", choices=["text", "md", "json"], default="text",
                        help="Output format (default: text)")
    parser.add_argument("--output", "-o", type=str, help="Output file (default: stdout)")
    args = parser.parse_args()

    if not REGISTRY_PATH.exists():
        print(f"Error: Registry not found at {REGISTRY_PATH}", file=sys.stderr)
        sys.exit(1)

    registry = load_registry()

    if args.format == "text":
        output = generate_text_report(registry)
    elif args.format == "md":
        output = generate_markdown_report(registry)
    elif args.format == "json":
        output = json.dumps({
            "dungeons": analyze_dungeons(registry),
            "shrines": analyze_shrines(registry),
            "caves": analyze_caves(registry),
            "progression": registry.get("progression", {}),
        }, indent=2)

    if args.output:
        with open(args.output, "w") as f:
            f.write(output)
        print(f"Report written to: {args.output}")
    else:
        print(output)


if __name__ == "__main__":
    main()
