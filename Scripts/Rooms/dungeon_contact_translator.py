#!/usr/bin/env python3
"""Translate measured wall/stair contacts into ordered dungeon object lists (v0).

v0 copies only the three measured wall-cutting contacts in
`data/dungeon_contact_library.json`. It keeps each member's object ID
(including extended 0xFxx), size, stream list and relative order, and moves the
whole group by one translation. It never rotates, mirrors, stretches or infers a
new family: any such request returns UNSUPPORTED with a reason.

Subcommands:
  translate  design-packet contacts -> ordered object list JSON
  apply      object list -> z3ed dungeon-place-object on a PRIVATE scratch ROM
             (dry run on a temporary copy unless --write)
  contract   object list + candidate trace -> dungeon_layout_preflight contract

The translator does not encode room bytes. Writes go through the maintained
guarded z3ed writer (`dungeon-remove-object`, `dungeon-place-object`).
"""

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

HERE = Path(__file__).resolve().parent
DEFAULT_LIBRARY = HERE / "data" / "dungeon_contact_library.json"
DEFAULT_REFERENCE_ROOT = (Path.home() / ".context/projects/oracle-of-secrets/scratchpad/handoffs/"
                          "dungeon_wall_completion_2026-11-05")
DEFAULT_Z3ED = os.environ.get("Z3ED", "z3ed")
# Canonical yaze project ROM and other shared images are never write targets.
PROTECTED_SHA_PREFIXES = ("e1e6fb5b",)
PROTECTED_PATH_PARTS = ("Roms",)
PROTECTED_PATH_SUFFIXES = (".yazeproj",)


class Unsupported(Exception):
    """A request outside the measured v0 contact families."""


class InputError(ValueError):
    """Malformed or stale input."""


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def parse_int(value, name):
    if isinstance(value, bool):
        raise InputError(f"{name} must be an integer")
    if isinstance(value, int):
        return value
    if isinstance(value, str):
        return int(value, 0)
    raise InputError(f"{name} must be an integer or 0x text")


def load_library(path=DEFAULT_LIBRARY):
    data = json.loads(Path(path).read_text())
    if data.get("schema_version") != 1:
        raise InputError("library schema_version must be 1")
    return {f["name"]: f for f in data["families"]}


def translate_contact(contact, library, room_id):
    name = contact.get("name") or contact.get("family")
    family_name = contact.get("family")
    if family_name not in library:
        raise Unsupported(f"{name}: family {family_name!r} is not a measured v0 contact "
                          f"(supported: {', '.join(sorted(library))})")
    family = library[family_name]
    if contact.get("mirror", False):
        raise Unsupported(f"{name}: mirrored contacts are not measured; v0 copies source orientation only")
    if contact.get("rotation", 0) not in (0, "0", None):
        raise Unsupported(f"{name}: rotated contacts are not measured; v0 copies source orientation only")
    facing = contact.get("facing", family["facing"])
    if facing != family["facing"]:
        raise Unsupported(f"{name}: {family_name} is measured facing {family['facing']}; "
                          f"facing {facing} needs a rotated family that is not measured")
    anchor = contact.get("anchor")
    if not isinstance(anchor, list) or len(anchor) != 2:
        raise InputError(f"{name}: anchor must be [x, y] in tile8 units")
    ax, ay = (parse_int(v, "anchor") for v in anchor)
    objects = []
    for m in family["members"]:
        x, y = ax + m["dx"], ay + m["dy"]
        x0, y0, x1, y1 = m["tile_box"]
        if not (0 <= x <= 63 and 0 <= y <= 63 and ax + x0 >= 0 and ay + y0 >= 0
                and ax + x1 <= 64 and ay + y1 <= 64):
            raise Unsupported(f"{name}: member {m['role']} {m['object_id']} leaves the 64x64 room at anchor {ax},{ay}")
        objects.append({"contact": name, "family": family_name, "role": m["role"],
                        "source_index": m["source_index"], "object_id": m["object_id"],
                        "size": m["size"], "list": m["list"], "x": x, "y": y,
                        "tile_box": [ax + x0, ay + y0, ax + x1, ay + y1]})
    sx, sy = family["source"]["anchor"]
    record = {"name": name, "family": family_name, "anchor": [ax, ay],
              "translation_from_source": [ax - sx, ay - sy],
              "source_room_id": family["source"]["room_id"]}
    return record, objects


def boxes_overlap(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def translate(packet, library, relocate_source=False):
    """Return (result, exit_code). Result status is OK or UNSUPPORTED."""
    if packet.get("schema_version") != 1:
        raise InputError("packet schema_version must be 1")
    room_id = parse_int(packet["room_id"], "room_id")
    contacts = packet.get("contacts")
    if not isinstance(contacts, list) or not contacts:
        raise InputError("packet needs a nonempty contacts list")
    result = {"schema_version": 1, "tool": "dungeon_contact_translator v0",
              "room_id": "0x%03X" % room_id, "status": "OK", "unsupported": [],
              "contacts": [], "removals": [], "objects": []}
    placed = []
    for contact in contacts:
        try:
            record, objects = translate_contact(contact, library, room_id)
        except Unsupported as error:
            result["unsupported"].append({"name": contact.get("name") or contact.get("family"),
                                          "reason": str(error)})
            continue
        for other in placed:
            if other["contact"] != record["name"] and any(
                    boxes_overlap(o["tile_box"], other["tile_box"]) for o in objects):
                result["unsupported"].append({"name": record["name"], "reason":
                    f"overlaps contact {other['contact']}; relative order between contacts is not measured"})
                break
        else:
            placed.extend(objects)
            result["contacts"].append(record)
            if relocate_source:
                family = library[record["family"]]
                if parse_int(family["source"]["room_id"], "room_id") != room_id:
                    raise InputError("--relocate-source needs the packet room to be the family source room")
                sx, sy = family["source"]["anchor"]
                for m in family["members"]:
                    result["removals"].append({"index": m["source_index"], "object_id": m["object_id"],
                                               "x": sx + m["dx"], "y": sy + m["dy"],
                                               "size": m["size"], "list": m["list"]})
    if result["unsupported"]:
        result["status"] = "UNSUPPORTED"
        result["contacts"], result["removals"], placed = [], [], []
    result["removals"].sort(key=lambda r: -r["index"])
    for order, o in enumerate(placed):
        o = dict(o)
        o.pop("tile_box")
        result["objects"].append({"order": order, **o})
    return result, (0 if result["status"] == "OK" else 1)


def guard_scratch_rom(rom):
    path = Path(rom).resolve()
    if any(part in PROTECTED_PATH_PARTS or part.endswith(PROTECTED_PATH_SUFFIXES) for part in path.parts):
        raise InputError(f"refusing to write {path}: shared Roms/ and yaze project ROMs are not write targets")
    digest = sha256(path)
    if digest.startswith(PROTECTED_SHA_PREFIXES):
        raise InputError(f"refusing to write {path}: sha256 {digest[:8]} is a protected ROM")
    return path, digest


def run_z3ed(z3ed, args):
    proc = subprocess.run([z3ed, *args, "--format=json"], capture_output=True, text=True)
    return {"argv": args, "returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr}


def apply_objects(objects_doc, rom, z3ed, write):
    """Remove listed source objects (highest index first), then place in order."""
    if objects_doc.get("status") != "OK":
        raise InputError("object list status is not OK; nothing to apply")
    target, before = guard_scratch_rom(rom)
    work_dir = None
    if not write:
        work_dir = tempfile.mkdtemp(prefix="contact-translator-dry-")
        target = Path(work_dir) / target.name
        shutil.copyfile(rom, target)
    room = objects_doc["room_id"]
    steps = []
    try:
        for r in objects_doc.get("removals", []):
            steps.append(run_z3ed(z3ed, [
                "dungeon-remove-object", f"--room={room}", f"--index={r['index']}",
                f"--expect-id={r['object_id']}", f"--expect-x={r['x']}", f"--expect-y={r['y']}",
                f"--expect-size={r['size']}", f"--expect-layer={r['list']}", "--write", f"--rom={target}"]))
            if steps[-1]["returncode"]:
                break
        else:
            for o in objects_doc["objects"]:
                steps.append(run_z3ed(z3ed, [
                    "dungeon-place-object", f"--room={room}", f"--id={o['object_id']}",
                    f"--x={o['x']}", f"--y={o['y']}", f"--size={o['size']}", f"--layer={o['list']}",
                    "--write", f"--rom={target}"]))
                if steps[-1]["returncode"]:
                    break
        ok = all(s["returncode"] == 0 for s in steps)
        after = sha256(target)
    finally:
        if work_dir:
            shutil.rmtree(work_dir, ignore_errors=True)
    return {"mode": "write" if write else "dry-run (temporary copy)", "rom": str(Path(rom).resolve()),
            "sha256_before": before, "sha256_after": after if write else None,
            "dry_run_sha256_after": None if write else after,
            "status": "OK" if ok else "FAILED", "steps": steps}, (0 if ok else 1)


def trace_cases(path):
    return json.loads(Path(path).read_text())["cases"]


def find_index(cases, o):
    want = (int(o["object_id"], 16), o["size"], o["list"], o["x"], o["y"])
    hits = [c["object_index"] for c in cases
            if (c["object_id_dec"], c["size"], c["object_layer"], c["object_x"], c["object_y"]) == want]
    return hits


def build_contract(objects_doc, candidate_trace, out_path, library, reference_root, require):
    if objects_doc.get("status") != "OK":
        raise InputError("object list status is not OK; no contract")
    cases = trace_cases(candidate_trace)
    out_dir = Path(out_path).resolve().parent
    room_id = parse_int(objects_doc["room_id"], "room_id")
    assemblies, required = [], []
    for record in objects_doc["contacts"]:
        family = library[record["family"]]
        # Family member order, not object-list order: the checker compares the two orders.
        by_source = {o["source_index"]: o for o in objects_doc["objects"] if o["contact"] == record["name"]}
        members = [by_source[m["source_index"]] for m in family["members"]]
        candidate = []
        for o in members:
            hits = find_index(cases, o)
            if len(hits) != 1:
                raise InputError(f"{record['name']}: {o['role']} {o['object_id']} at {o['x']},{o['y']} "
                                 f"matches {len(hits)} candidate trace objects; need exactly one")
            candidate.append(hits[0])
        # Candidate indices keep member order; a reversed stream is left for the checker to block.
        ref_path = (Path(reference_root) / family["source"]["trace"]).resolve()
        ref_sha = sha256(ref_path)
        if ref_sha != family["source"]["trace_sha256"]:
            raise InputError(f"{record['family']}: reference trace sha256 {ref_sha} differs from library")
        ref_cases = {c["object_index"]: c for c in trace_cases(ref_path)}
        sx, sy = family["source"]["anchor"]
        for m in family["members"]:
            c = ref_cases.get(m["source_index"])
            if c is None or (c["object_id_dec"], c["size"], c["object_layer"], c["object_x"], c["object_y"]) != (
                    int(m["object_id"], 16), m["size"], m["list"], sx + m["dx"], sy + m["dy"]):
                raise InputError(f"{record['family']}: reference index {m['source_index']} differs from library")
        assemblies.append({"name": record["name"],
                           "reference": {"trace": os.path.relpath(ref_path, out_dir), "sha256": ref_sha,
                                         "object_indices": [m["source_index"] for m in family["members"]]},
                           "candidate": {"object_indices": candidate},
                           "translation": record["translation_from_source"]})
        if require == "all":
            required.extend(candidate)
        else:
            required.extend(i for i, m in zip(candidate, family["members"]) if m["role"] == "stair")
    profiles = {c["state_profile"] for c in cases}
    if len(profiles) != 1:
        raise InputError("candidate trace mixes state profiles")
    return {"schema_version": 1, "room_id": room_id, "state_profile": profiles.pop(),
            "provenance": {"candidate_trace_sha256": sha256(candidate_trace),
                           "source_note": f"dungeon_contact_translator v0 contract (require={require})"},
            "required_object_indices": required, "assemblies": assemblies,
            "owner_expectations": [], "unsupported": []}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--library", type=Path, default=DEFAULT_LIBRARY)
    sub = parser.add_subparsers(dest="command", required=True)
    t = sub.add_parser("translate")
    t.add_argument("--packet", type=Path, required=True)
    t.add_argument("--out", type=Path)
    t.add_argument("--relocate-source", action="store_true",
                   help="round-trip control: also remove the source members (packet room must be the source room)")
    a = sub.add_parser("apply")
    a.add_argument("--objects", type=Path, required=True)
    a.add_argument("--rom", type=Path, required=True, help="private scratch ROM copy outside Roms/")
    a.add_argument("--z3ed", default=DEFAULT_Z3ED)
    a.add_argument("--write", action="store_true")
    a.add_argument("--out", type=Path)
    c = sub.add_parser("contract")
    c.add_argument("--objects", type=Path, required=True)
    c.add_argument("--candidate-trace", type=Path, required=True)
    c.add_argument("--out", type=Path, required=True)
    c.add_argument("--reference-root", type=Path, default=DEFAULT_REFERENCE_ROOT)
    c.add_argument("--require", choices=["all", "stair"], default="all",
                   help="all: every member is a changed object (walls need boundary proof); "
                        "stair: only stair members are declared changed")
    args = parser.parse_args(argv)
    try:
        library = load_library(args.library)
        if args.command == "translate":
            result, code = translate(json.loads(args.packet.read_text()), library, args.relocate_source)
        elif args.command == "apply":
            result, code = apply_objects(json.loads(args.objects.read_text()), args.rom, args.z3ed, args.write)
        else:
            result = build_contract(json.loads(args.objects.read_text()), args.candidate_trace, args.out,
                                    library, args.reference_root, args.require)
            code = 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(error)}, indent=2))
        return 2
    text = json.dumps(result, indent=2) + "\n"
    if getattr(args, "out", None):
        args.out.write_text(text)
    print(text, end="")
    return code


if __name__ == "__main__":
    sys.exit(main())
