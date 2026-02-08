#!/usr/bin/env python3
"""
Extract Oracle story events from Story_Event_Graph.md into machine-readable JSON.

Generates story_events.json with node/edge data for yaze's StoryEventGraphPanel.

Sources:
  - Docs/Planning/Story_Event_Graph.md  -> event nodes + relationships

Usage:
  python3 scripts/extract_story_events.py [--validate] [--output PATH]
"""

import argparse
import json
import re
import sys
from pathlib import Path


def find_project_root() -> Path:
    """Walk up from script dir to find the repo root (contains CLAUDE.md)."""
    p = Path(__file__).resolve().parent.parent
    if (p / "CLAUDE.md").exists():
        return p
    return Path.cwd()


def parse_flags(flags_str: str) -> list:
    """Parse flag field into structured list of {name, value} pairs."""
    flags = []
    if not flags_str or flags_str.strip() in ("", "TBD", "-"):
        return flags

    # Split on semicolons
    for part in flags_str.split(";"):
        part = part.strip()
        if not part:
            continue

        # Pattern: FlagName=Value or FlagName (bit N)
        flag = {"name": part}

        # Extract value if present (e.g., "GameState=2")
        eq_match = re.match(r"(\w[\w_]*)\s*=\s*(\S+)", part)
        if eq_match:
            flag["name"] = eq_match.group(1)
            flag["value"] = eq_match.group(2)

        # Extract bit info if present (e.g., "OOSPROG bit 1")
        bit_match = re.search(r"\((\w+)\s+bit\s+(\d+)\)", part)
        if bit_match:
            flag["register"] = bit_match.group(1)
            flag["bit"] = int(bit_match.group(2))
            # Clean name
            flag["name"] = re.sub(r"\s*\(.*\)", "", flag["name"]).strip()

        # Extract increment notation (e.g., "IntroState++ (StoryState)")
        inc_match = re.match(r"(\w+)\+\+", part)
        if inc_match:
            flag["name"] = inc_match.group(1)
            flag["operation"] = "increment"

        flags.append(flag)

    return flags


def parse_locations(locations_str: str) -> list:
    """Parse locations field into structured list."""
    locations = []
    if not locations_str or locations_str.strip() in ("", "TBD", "-"):
        return locations

    def split_outside_parens(s: str) -> list[str]:
        # Locations are comma-separated in the markdown table, but some entries
        # include commas inside parentheses, e.g.:
        #   "Hall of Secrets (Entrance 2, OW 0x0E)"
        # We only split on separators at paren-depth 0.
        parts: list[str] = []
        buf: list[str] = []
        depth = 0
        for ch in s:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth = max(depth - 1, 0)

            if depth == 0 and ch in {",", ";"}:
                part = "".join(buf).strip()
                if part:
                    parts.append(part)
                buf = []
                continue

            buf.append(ch)

        tail = "".join(buf).strip()
        if tail:
            parts.append(tail)
        return parts

    for part in split_outside_parens(locations_str):
        part = part.strip()
        if not part:
            continue

        location = {"name": part}

        # Extract IDs: Entrance 0/1, Entrance ID 2, OW 0x33, Room 0x202, SW 0x80
        entrance_match = re.search(r"Entrance\s+(?:ID\s+)?(\w+(?:/\w+)?)", part)
        if entrance_match:
            location["entrance_id"] = entrance_match.group(1)

        ow_match = re.search(r"OW\s+(0x[0-9A-Fa-f]+)", part)
        if ow_match:
            location["overworld_id"] = ow_match.group(1)

        sw_match = re.search(r"SW\s+(0x[0-9A-Fa-f]+)", part)
        if sw_match:
            location["special_world_id"] = sw_match.group(1)

        room_match = re.search(r"Room\s+(0x[0-9A-Fa-f]+)", part)
        if room_match:
            location["room_id"] = room_match.group(1)

        # Clean name to just the place name
        clean = re.sub(r"\s*\(.*?\)", "", part).strip()
        clean = re.sub(r"\s*Entrance\s+(?:ID\s+)?\S+", "", clean).strip()
        clean = re.sub(r"\s*OW\s+\S+", "", clean).strip()
        clean = re.sub(r"\s*SW\s+\S+", "", clean).strip()
        clean = re.sub(r"\s*Room\s+\S+", "", clean).strip()
        if clean:
            location["name"] = clean

        locations.append(location)

    return locations


def parse_text_ids(text_str: str) -> list:
    """Parse text IDs field into list of hex strings."""
    ids = []
    if not text_str or text_str.strip() in ("", "TBD", "-"):
        return ids

    for part in text_str.split(","):
        part = part.strip()
        # Match hex IDs like 0x1F, $1F, or bare hex
        hex_match = re.search(r"(?:0x|\$)?([0-9A-Fa-f]+)", part)
        if hex_match:
            val = int(hex_match.group(1), 16)
            ids.append(f"0x{val:02X}")

    return ids


def parse_scripts(scripts_str: str) -> list:
    """Parse scripts/routines field into list of routine names."""
    scripts = []
    if not scripts_str or scripts_str.strip() in ("", "TBD", "-"):
        return scripts

    for part in scripts_str.split(";"):
        part = part.strip()
        if not part:
            continue
        # Extract routine name, stripping parenthetical class info
        name = re.sub(r"\s*\(.*?\)", "", part).strip()
        if name:
            scripts.append(name)

    return scripts


def extract_events(root: Path) -> list:
    """Parse Story_Event_Graph.md into structured event list."""
    path = root / "Docs" / "Planning" / "Story_Event_Graph.md"
    if not path.exists():
        print(f"  ERROR: {path} not found", file=sys.stderr)
        return []

    with open(path, encoding="utf-8") as f:
        content = f.read()

    events = []

    # Match markdown table rows: | EV-XXX | Name | Flags | Locations | Scripts | Text IDs | Evidence | Date | Notes |
    # The table has 9 columns
    row_pattern = re.compile(
        r"^\|\s*(EV-\d+)\s*\|"     # Event ID
        r"\s*(.*?)\s*\|"            # Event Name
        r"\s*(.*?)\s*\|"            # Flags Set/Cleared
        r"\s*(.*?)\s*\|"            # Locations/Rooms
        r"\s*(.*?)\s*\|"            # Scripts/Routines
        r"\s*(.*?)\s*\|"            # Text IDs
        r"\s*(.*?)\s*\|"            # Evidence
        r"\s*(.*?)\s*\|"            # Last Verified
        r"\s*(.*?)\s*\|",           # Notes
        re.MULTILINE
    )

    for match in row_pattern.finditer(content):
        event_id = match.group(1).strip()
        name = match.group(2).strip()
        flags_raw = match.group(3).strip()
        locations_raw = match.group(4).strip()
        scripts_raw = match.group(5).strip()
        text_ids_raw = match.group(6).strip()
        evidence = match.group(7).strip()
        last_verified = match.group(8).strip()
        notes = match.group(9).strip()

        event = {
            "id": event_id,
            "name": name,
            "flags": parse_flags(flags_raw),
            "locations": parse_locations(locations_raw),
            "scripts": parse_scripts(scripts_raw),
            "text_ids": parse_text_ids(text_ids_raw),
            "evidence": evidence,
            "last_verified": last_verified,
            "notes": notes,
        }

        events.append(event)

    return events


def infer_dependencies(events: list) -> list:
    """Infer dependency edges from event ordering and flag relationships."""
    edges = []

    # Known dependency chains from game design
    # These are hardcoded based on Oracle narrative progression
    dependency_map = {
        "EV-002": ["EV-001"],       # Meet Maku Tree after intro
        "EV-003": ["EV-002"],       # Hall of Secrets unlocked after meeting Maku
        "EV-004": ["EV-003"],       # Pendant quest after Hall unlocked
        "EV-005": ["EV-004"],       # Kydrog encounter after pendant quest
        "EV-006": ["EV-005"],       # Book of Secrets after Kydrog
        "EV-007": ["EV-006"],       # Fortress complete after Book obtained
        "EV-008": ["EV-007"],       # Endgame after Fortress
        "EV-009": ["EV-005"],       # Mask Salesman available after Kydrog (GameState >= 2)
        "EV-010": ["EV-009"],       # Song of Healing after meeting Mask Salesman
        "EV-011": ["EV-010"],       # Ranch Girl needs Song of Healing
        "EV-012": ["EV-004"],       # Deku Scrub found after pendant quest (between D1-D2)
        "EV-013": ["EV-012", "EV-010"],  # Deku soul freed needs both: found + Song of Healing
        "EV-014": ["EV-004"],       # Village Elder met during pendant quest
        "EV-015": ["EV-001"],       # Impa intro (duplicate of EV-004 per notes)
        "EV-016": ["EV-003"],       # Mirror of Time from Impa in Hall
        "EV-017": ["EV-014"],       # Tail Pond marker set by Elder after D1
    }

    for target_id, source_ids in dependency_map.items():
        for source_id in source_ids:
            edges.append({
                "from": source_id,
                "to": target_id,
                "type": "dependency",
            })

    return edges


def build_story_events(root: Path) -> dict:
    """Build the complete story events JSON structure."""
    print("Extracting story events...")

    events = extract_events(root)
    edges = infer_dependencies(events)

    # Add dependency/unlock fields to each event based on edges
    deps_by_target = {}
    unlocks_by_source = {}
    for edge in edges:
        deps_by_target.setdefault(edge["to"], []).append(edge["from"])
        unlocks_by_source.setdefault(edge["from"], []).append(edge["to"])

    for event in events:
        event["dependencies"] = sorted(set(deps_by_target.get(event["id"], [])))
        event["unlocks"] = sorted(set(unlocks_by_source.get(event["id"], [])))

    result = {
        "_meta": {
            "generated_by": "scripts/extract_story_events.py",
            "description": "Oracle of Secrets story event graph for yaze integration",
            "source": "Docs/Planning/Story_Event_Graph.md",
            "event_count": len(events),
            "edge_count": len(edges),
        },
        "events": events,
        "edges": edges,
    }

    print(f"  events: {len(events)}")
    print(f"  edges: {len(edges)}")

    return result


def validate_story_events(data: dict) -> bool:
    """Validate story events JSON structure."""
    ok = True

    if "events" not in data:
        print("  ERROR: Missing 'events' key", file=sys.stderr)
        return False

    if "edges" not in data:
        print("  ERROR: Missing 'edges' key", file=sys.stderr)
        return False

    events = data["events"]
    if len(events) < 10:
        print(
            f"  WARN: Only {len(events)} events (expected >= 10)",
            file=sys.stderr,
        )

    event_ids = set()
    for event in events:
        eid = event.get("id", "")
        if not re.match(r"^EV-\d{3}$", eid):
            print(f"  ERROR: Invalid event ID format: '{eid}'", file=sys.stderr)
            ok = False
        if eid in event_ids:
            print(f"  ERROR: Duplicate event ID: '{eid}'", file=sys.stderr)
            ok = False
        event_ids.add(eid)

        if not event.get("name"):
            print(f"  ERROR: Event {eid} has no name", file=sys.stderr)
            ok = False

    # Validate edge references
    for edge in data["edges"]:
        if edge["from"] not in event_ids:
            print(
                f"  WARN: Edge references unknown source: {edge['from']}",
                file=sys.stderr,
            )
        if edge["to"] not in event_ids:
            print(
                f"  WARN: Edge references unknown target: {edge['to']}",
                file=sys.stderr,
            )

    # Check for cycles (simple DFS)
    adj = {}
    for edge in data["edges"]:
        adj.setdefault(edge["from"], []).append(edge["to"])

    visited = set()
    rec_stack = set()

    def has_cycle(node):
        visited.add(node)
        rec_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor not in visited:
                if has_cycle(neighbor):
                    return True
            elif neighbor in rec_stack:
                print(
                    f"  ERROR: Cycle detected involving {node} -> {neighbor}",
                    file=sys.stderr,
                )
                return True
        rec_stack.discard(node)
        return False

    for eid in event_ids:
        if eid not in visited:
            if has_cycle(eid):
                ok = False

    return ok


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        default=None,
        help="Output path (default: Docs/Dev/Planning/story_events.json)",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate existing output without regenerating",
    )
    args = parser.parse_args()

    root = find_project_root()
    default_output = root / "Docs" / "Dev" / "Planning" / "story_events.json"
    output_path = Path(args.output) if args.output else default_output

    if args.validate:
        if not output_path.exists():
            print(f"ERROR: {output_path} does not exist", file=sys.stderr)
            sys.exit(1)
        with open(output_path) as f:
            data = json.load(f)
        ok = validate_story_events(data)
        if ok:
            print("Validation passed.")
        else:
            print("Validation FAILED.", file=sys.stderr)
            sys.exit(1)
        return

    data = build_story_events(root)
    ok = validate_story_events(data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write("\n")

    print(f"\nWrote {output_path}")
    if not ok:
        print("WARNING: Validation issues detected (see above)", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
