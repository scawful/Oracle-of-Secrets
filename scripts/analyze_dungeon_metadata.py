#!/usr/bin/env python3
"""
Analyze all Oracle dungeons using z3ed - uses correct Debug binary.
"""

import subprocess
import json
import re
from pathlib import Path

Z3ED = "/Users/scawful/src/hobby/yaze/build/bin/Debug/z3ed"
ROM = "/Users/scawful/src/hobby/oracle-of-secrets/Roms/oos168x.sfc"

DUNGEONS = {
    "D1_mushroom_grotto": {
        "name": "Mushroom Grotto",
        "rooms": [0x07, 0x09, 0x0A, 0x0B, 0x17, 0x19, 0x1A, 0x1B,
                  0x2A, 0x2B, 0x32, 0x33, 0x3A, 0x3B, 0x43, 0x4A,
                  0x4B, 0x53, 0x5B, 0x63, 0x6A],
        "entrance_room": 0x4A,
        "blockset": 7,
        "palette": 15,
    },
    "D2_tail_palace": {
        "name": "Tail Palace",
        "rooms": [0x0E, 0x1D, 0x1E, 0x1F, 0x2D, 0x2E, 0x2F, 0x3E, 0x3F,
                  0x4E, 0x4F, 0x5E, 0x5F, 0x6E, 0x6F, 0x7E, 0xDE],
        "entrance_room": 0x5F,
        "blockset": 5,
        "palette": 6,
    },
    "D3_kalyxo_castle": {
        "name": "Kalyxo Castle",
        "rooms": [0x29, 0x30, 0x39, 0x47, 0x48, 0x49, 0x51, 0x56,
                  0x57, 0x58, 0x59, 0x66, 0x67, 0x68],
        "entrance_room": 0x56,
        "blockset": 2,
        "palette": 12,
    },
    "D4_zora_temple": {
        "name": "Zora Temple",
        "rooms": [0x06, 0x16, 0x18, 0x25, 0x26, 0x27, 0x28, 0x34,
                  0x35, 0x36, 0x37, 0x38, 0x44, 0x45, 0x46],
        "entrance_room": 0x28,
        "blockset": 1,
        "palette": 9,
    },
    "D5_glacia_estate": {
        "name": "Glacia Estate",
        "rooms": [0x9E, 0x9F, 0xAC, 0xAD, 0xAE, 0xAF, 0xBB, 0xBC,
                  0xBD, 0xBE, 0xBF, 0xCB, 0xCC, 0xCD, 0xCE, 0xCF,
                  0xDB, 0xDC, 0xDD],
        "entrance_room": 0xDB,
        "blockset": 11,
        "palette": 19,
    },
    "D7_dragon_ship": {
        "name": "Dragon Ship",
        "rooms": [0xB7, 0xC6, 0xC7, 0xD5, 0xD6],
        "entrance_room": 0xD6,
        "blockset": 9,
        "palette": 5,
    },
}


def parse_z3ed_output(output: str) -> dict:
    """Parse z3ed JSON output with regex (handles malformed JSON)."""
    data = {}

    patterns = {
        'blockset': r'"blockset":\s*(\d+)',
        'spriteset': r'"spriteset":\s*(\d+)',
        'palette': r'"palette":\s*(\d+)',
        'layout': r'"layout":\s*(\d+)',
        'floor1': r'"floor1":\s*(\d+)',
        'floor2': r'"floor2":\s*(\d+)',
        'effect': r'"effect":\s*(\d+)',
        'object_count': r'"object_count":\s*(\d+)',
    }

    for key, pattern in patterns.items():
        match = re.search(pattern, output)
        if match:
            data[key] = int(match.group(1))

    return data


def query_room(room_id: int) -> dict:
    """Query z3ed for room metadata."""
    room_hex = f"0x{room_id:02X}"
    try:
        result = subprocess.run(
            [Z3ED, "dungeon-describe-room", f"--rom={ROM}", f"--room={room_hex}"],
            capture_output=True, text=True, timeout=5
        )

        data = {"room_id": room_id, "room_hex": room_hex}

        if result.returncode == 0:
            parsed = parse_z3ed_output(result.stdout)
            data.update(parsed)
        else:
            data["error"] = result.stderr

        return data
    except subprocess.TimeoutExpired:
        return {"room_id": room_id, "room_hex": room_hex, "error": "timeout"}
    except Exception as e:
        return {"room_id": room_id, "room_hex": room_hex, "error": str(e)}


def analyze_dungeon(dungeon_key: str, dungeon_info: dict) -> dict:
    """Analyze all rooms in a dungeon."""
    sep = "=" * 70
    print(f"\n{sep}")
    print(f"  {dungeon_info['name']} (Expected: blockset={dungeon_info['blockset']}, palette={dungeon_info['palette']})")
    print(f"{sep}")

    results = {
        "name": dungeon_info["name"],
        "entrance_room": f"0x{dungeon_info['entrance_room']:02X}",
        "expected_blockset": dungeon_info["blockset"],
        "expected_palette": dungeon_info["palette"],
        "rooms": {},
        "anomalies": [],
    }

    for room_id in dungeon_info["rooms"]:
        room_data = query_room(room_id)
        room_hex = f"0x{room_id:02X}"
        results["rooms"][room_hex] = room_data

        # Check for anomalies
        is_entrance = room_id == dungeon_info["entrance_room"]
        anomaly = None

        if "palette" in room_data:
            if room_data["palette"] != dungeon_info["palette"]:
                anomaly = f"DIFFERENT PALETTE ({room_data['palette']} vs {dungeon_info['palette']})"
                results["anomalies"].append({
                    "room": room_hex,
                    "type": "palette_mismatch",
                    "value": room_data["palette"],
                    "expected": dungeon_info["palette"],
                })

        # Format output
        pal = room_data.get('palette', '?')
        blk = room_data.get('blockset', '?')
        obj = room_data.get('object_count', '?')
        spr = room_data.get('spriteset', '?')

        marker = " -> ENTRANCE" if is_entrance else ""
        anomaly_marker = f" !! {anomaly}" if anomaly else ""

        print(f"  {room_hex}: blockset={blk:>2}, palette={pal:>2}, spriteset={spr:>2}, objects={obj:>3}{marker}{anomaly_marker}")

    return results


def main():
    all_results = {}

    for dungeon_key, dungeon_info in DUNGEONS.items():
        results = analyze_dungeon(dungeon_key, dungeon_info)
        all_results[dungeon_key] = results

    # Summary
    sep = "=" * 70
    print(f"\n{sep}")
    print("  ANOMALY SUMMARY (Potential Boss/Special Rooms)")
    print(sep)

    for dungeon_key, results in all_results.items():
        if results["anomalies"]:
            print(f"\n  {results['name']}:")
            for anomaly in results["anomalies"]:
                print(f"    * Room {anomaly['room']}: {anomaly['type']} = {anomaly['value']} (expected {anomaly['expected']})")
        else:
            print(f"\n  {results['name']}: No anomalies detected")

    # Generate registry update suggestions
    print(f"\n{sep}")
    print("  REGISTRY UPDATE SUGGESTIONS")
    print(sep)

    for dungeon_key, results in all_results.items():
        rooms_data = results["rooms"]
        print(f"\n  {results['name']}:")

        # Find rooms with most objects (likely complex/important)
        sorted_by_objects = sorted(
            [(k, v) for k, v in rooms_data.items() if v.get("object_count")],
            key=lambda x: x[1].get("object_count", 0),
            reverse=True
        )

        if sorted_by_objects:
            top3 = sorted_by_objects[:3]
            print(f"    Highest object count rooms (possible key rooms):")
            for room_hex, data in top3:
                print(f"      {room_hex}: {data.get('object_count', '?')} objects")

    # Save results
    output_path = "/tmp/dungeon_metadata.json"
    with open(output_path, "w") as f:
        json.dump(all_results, f, indent=2)
    print(f"\nFull results saved to: {output_path}")


if __name__ == "__main__":
    main()
