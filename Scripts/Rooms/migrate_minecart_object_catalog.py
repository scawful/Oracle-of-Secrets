#!/usr/bin/env python3
"""Plan the 37-record legacy minecart object migration without changing input.

Default is a read-only JSON dry run. --output and --receipt opt into publishing
two new private files; neither existing path can be overwritten. The result is
an intermediate room-data image, NOT an editor-ready or runtime-ready ROM. It
must be composed with the MCR2 object handlers by the normal build owner.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

from sky_d8_room_writer import (
    DEFAULT_PROTECTED_DIRS,
    PlanError,
    check_new_target,
    parse_object_stream,
    publish_exclusive,
    read_input,
    readback,
)

ROOM_COUNT = 296
POINTER_OPERAND = 0x874C
MARKER_PC = 0x160017
MCR2_MARKER = b"MCR2\x10\x0D\x02\x00"
EXPECTED_RECORDS = 37
EXPECTED_CHANGED_BYTES = 111
MIGRATION = {12: 5, 13: 6, 14: 7, 15: 8}
PROTECTED_DIRS = (*DEFAULT_PROTECTED_DIRS, Path.home() / "Zelda" / "Projects")


def require(condition: bool, message: str) -> None:
    if not condition:
        raise PlanError(message)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def snes_to_pc(address: int) -> int:
    require(address & 0x8000 != 0, f"Not a LoROM pointer: {address:06X}")
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def census(data: bytes) -> tuple[dict, list[dict]]:
    """Parse every room through the maintained parser, with stream boundaries."""
    require(0x200000 <= len(data) <= 0x1000000, "Expected an unheadered 2-16 MiB ROM")
    table = snes_to_pc(int.from_bytes(data[POINTER_OPERAND:POINTER_OPERAND + 3], "little"))
    require(table + ROOM_COUNT * 3 <= len(data), "Room pointer table exceeds ROM")
    aliases: dict[int, list[int]] = defaultdict(list)
    for room in range(ROOM_COUNT):
        slot = table + room * 3
        start = snes_to_pc(int.from_bytes(data[slot:slot + 3], "little"))
        require(start + 2 < len(data), f"Room {room:03X} pointer exceeds ROM")
        require(not (table <= start < table + ROOM_COUNT * 3), "Room points into pointer table")
        aliases[start].append(room)

    starts = sorted(aliases)
    streams = {}
    records = []
    for index, start in enumerate(starts):
        limit = starts[index + 1] if index + 1 < len(starts) else len(data)
        stream = parse_object_stream(data, start, limit)
        require(stream.end <= limit, "Overlapping object streams")
        streams[start] = (stream.end, stream.header.hex(), stream.has_marker,
                          tuple(door.hex() for door in stream.doors))
        for room in aliases[start]:
            pos = start + 2
            for layer, objects in enumerate(stream.lists):
                for record_index, raw in enumerate(objects):
                    require(data[pos:pos + 3] == raw, "Object cursor/preimage mismatch")
                    records.append({"room": room, "layer": layer, "index": record_index,
                                    "pc": pos, "raw": raw.hex(),
                                    "aliased_rooms": aliases[start]})
                    pos += 3
                if layer < 2:
                    pos += 2
    return {"table": table, "streams": streams}, records


def plan_migration(data: bytes, expected_sha256: str) -> tuple[bytes, dict]:
    require(re.fullmatch(r"[0-9a-fA-F]{64}", expected_sha256) is not None,
            "Expected SHA-256 must contain 64 hexadecimal characters")
    require(digest(data) == expected_sha256.lower(), "Input SHA-256 differs from expected input")
    require(data[MARKER_PC:MARKER_PC + 4] != b"MCR2",
            "MCR2 catalog already present; room migration must precede the new runtime build")
    structure, records = census(data)
    changes = []
    for record in records:
        raw = bytes.fromhex(record["raw"])
        b1, b2, object_id = raw
        if b1 >= 0xFC or object_id >= 0xF8:
            continue  # Other encoding families do not use the size-subtype ABI.
        subtype = ((b1 & 3) << 2) | (b2 & 3)
        require(not (object_id == 0x32 and subtype >= 3),
                "Already migrated or ambiguous custom-object 32 catalog")
        if object_id != 0x31 or subtype not in MIGRATION:
            continue
        require(len(record["aliased_rooms"]) == 1,
                "Migration target has aliased room consumers; explicit alias review required")
        target = MIGRATION[subtype]
        new = bytes(((b1 & 0xFC) | (target >> 2), (b2 & 0xFC) | (target & 3), 0x32))
        changes.append({**record, "old": raw.hex(), "new": new.hex(),
                        "x": b1 >> 2, "y": b2 >> 2,
                        "old_object": 0x31, "old_subtype": subtype,
                        "new_object": 0x32, "new_subtype": target})
    require(len(changes) == EXPECTED_RECORDS,
            f"Expected {EXPECTED_RECORDS} reviewed placements, found {len(changes)}")
    require(len({r["pc"] for r in changes}) == len(changes), "Duplicate migration record")

    candidate = bytearray(data)
    allowed = set()
    for change in changes:
        pos = change["pc"]
        require(candidate[pos:pos + 3].hex() == change["old"], "Record CAS preimage differs")
        candidate[pos:pos + 3] = bytes.fromhex(change["new"])
        allowed.update(range(pos, pos + 3))
    result = bytes(candidate)
    changed = {i for i, (old, new) in enumerate(zip(data, result)) if old != new}
    require(changed == allowed and len(changed) == EXPECTED_CHANGED_BYTES,
            "Migration changed bytes outside the exact 37 records / 111 bytes")
    after_structure, after_records = census(result)
    require(structure == after_structure, "Room headers, pointers or door data changed")
    replacements = {r["pc"]: r["new"] for r in changes}
    expected_records = [{**r, "raw": replacements.get(r["pc"], r["raw"])} for r in records]
    require(after_records == expected_records,
            "Object order, coordinates, layers or unrelated room records changed")
    return result, {
        "schema": "oracle-minecart-object-migration/v1",
        "state": "intermediate-old-runtime", "editor_ready": False, "runtime_ready": False,
        "next": "Compose these room records with the MCR2 handlers through the normal build owner",
        "input_sha256": digest(data), "output_sha256": digest(result), "bytes": len(data),
        "rooms_parsed": ROOM_COUNT, "record_count": len(changes), "changed_bytes": len(changed),
        "mapping": {f"31:{old:X}": f"32:{new:X}" for old, new in MIGRATION.items()},
        "records": changes,
        "warnings": ["Header checksum remains unchanged; the normal build owns it",
                     "Unlanded castle/D3 object32:5-8 plans conflict with this catalog; preserve their source packet"],
    }


def verify_build_input(data: bytes, receipt: dict | None = None) -> dict:
    """Bind MCR2 source to migrated room data before the assembler can run."""
    marker = data[MARKER_PC:MARKER_PC + 8]
    if marker[:4] == b"MCR2":
        require(marker == MCR2_MARKER, "Unsupported MCR2 catalog counts/version")
        census(data)
        return {"mode": "verify-build-input", "catalog": "MCR2",
                "input_sha256": digest(data), "receipt_required": False}
    require(isinstance(receipt, dict),
            "MCR2 source requires an MCR2 base or OOS_MINECART_MIGRATION_RECEIPT")
    require(receipt.get("schema") == "oracle-minecart-object-migration/v1" and
            receipt.get("mode") == "published" and
            receipt.get("state") == "intermediate-old-runtime",
            "Unsupported or unpublished migration receipt")
    require(receipt.get("output_sha256") == digest(data),
            "Migration receipt output SHA-256 differs from selected base")
    require(receipt.get("record_count") == EXPECTED_RECORDS and
            receipt.get("changed_bytes") == EXPECTED_CHANGED_BYTES and
            receipt.get("rooms_parsed") == ROOM_COUNT,
            "Migration receipt does not bind 37 records / 111 bytes / 296 rooms")
    records = receipt.get("records")
    require(isinstance(records, list) and len(records) == EXPECTED_RECORDS,
            "Migration receipt record list is incomplete")
    restored = bytearray(data)
    seen = set()
    for record in records:
        require(isinstance(record, dict), "Invalid migration receipt record")
        pos = record.get("pc")
        require(type(pos) is int and 0 <= pos <= len(data) - 3 and pos not in seen,
                "Invalid or duplicate migration receipt offset")
        seen.add(pos)
        old_hex, new_hex = record.get("old"), record.get("new")
        require(isinstance(old_hex, str) and isinstance(new_hex, str) and
                re.fullmatch(r"[0-9a-f]{6}", old_hex) is not None and
                re.fullmatch(r"[0-9a-f]{6}", new_hex) is not None,
                "Invalid migration receipt record bytes")
        require(data[pos:pos + 3].hex() == new_hex, "Migrated record CAS differs from receipt")
        restored[pos:pos + 3] = bytes.fromhex(old_hex)
    # Reconstruct the original complete image, then rerun the exhaustive planner.
    # This verifies old/new bytes, aliases, coordinates, layers and unrelated data
    # rather than trusting receipt counters or an output hash alone.
    original_sha = receipt.get("input_sha256")
    require(isinstance(original_sha, str), "Migration receipt original SHA-256 is invalid")
    planned, verified = plan_migration(bytes(restored), original_sha)
    require(planned == data and verified["records"] == records,
            "Migration receipt structural record proof differs")
    return {"mode": "verify-build-input", "catalog": "migrated-for-MCR2",
            "input_sha256": digest(data), "receipt_required": True,
            "record_count": EXPECTED_RECORDS, "changed_bytes": EXPECTED_CHANGED_BYTES}


def main(argv: Sequence[str] | None = None, protected_dirs: Sequence[Path] = PROTECTED_DIRS) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", required=True, type=Path)
    parser.add_argument("--expected-sha256")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--receipt", type=Path)
    parser.add_argument("--verify-build-input", action="store_true")
    parser.add_argument("--verify-receipt", type=Path)
    args = parser.parse_args(argv)
    output = None
    report = None
    try:
        if args.verify_build_input or args.verify_receipt:
            require(not args.output and not args.receipt,
                    "Build-input verification cannot publish files")
            data = read_input(args.rom)
            if args.expected_sha256:
                require(digest(data) == args.expected_sha256.lower(),
                        "Input SHA-256 differs from expected input")
            receipt = json.loads(args.verify_receipt.read_text()) if args.verify_receipt else None
            print(json.dumps(verify_build_input(data, receipt), indent=2))
            return 0
        require(bool(args.output) == bool(args.receipt), "--output and --receipt must be supplied together")
        require(args.expected_sha256 is not None, "Migration planning requires --expected-sha256")
        original = read_input(args.rom)
        result, report = plan_migration(original, args.expected_sha256)
        report["mode"] = "dry-run"
        if args.output:
            output = check_new_target(args.output, "output", protected_dirs, [args.rom.resolve()])
            receipt = check_new_target(args.receipt, "receipt", protected_dirs,
                                       [args.rom.resolve(), output])
            # Recheck the live input before publication; a changed source is not
            # permission to migrate a later human Save.
            require(digest(read_input(args.rom)) == report["input_sha256"], "Input changed during planning")
            publish_exclusive(output, result, 0o600)
            readback(output, report["output_sha256"], "migration output", args.rom)
            report.update(mode="published", output=str(output), receipt=str(receipt))
            encoded = (json.dumps(report, indent=2) + "\n").encode()
            publish_exclusive(receipt, encoded, 0o600)
            require(receipt.read_bytes() == encoded, "Receipt readback differs")
        print(json.dumps(report, indent=2))
        return 0
    except (PlanError, OSError, ValueError) as error:
        # A published unique ROM is retained if later receipt publication fails.
        # Never delete a possible recovery artifact or an externally raced path.
        print(json.dumps({"status": "refused", "error": str(error),
                          "output": str(output) if output else None,
                          "output_exists": output.exists() if output else False}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
