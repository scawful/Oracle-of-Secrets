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
  steps      room object stream + collision replay -> same-plane dry-step cells
             (library `dry_steps`); optional route through the existing
             scene_director pathfinder admitting only those cells

The translator does not encode room bytes. Writes go through the maintained
guarded z3ed writer (`dungeon-remove-object`, `dungeon-place-object`).
"""

import argparse
import hashlib
import importlib.util
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
    assemblies, required, boundaries = [], [], []
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
        reference = {"trace": os.path.relpath(ref_path, out_dir), "sha256": ref_sha,
                     "object_indices": [m["source_index"] for m in family["members"]]}
        assemblies.append({"name": record["name"], "reference": reference,
                           "candidate": {"object_indices": candidate},
                           "translation": record["translation_from_source"]})
        if require == "all":
            required.extend(candidate)
            # The checker certifies the cut walls only as this measured stair-mouth contact.
            boundaries.append({"name": record["name"], "kind": "stair_mouth", "family": record["family"],
                               "reference": dict(reference), "candidate": {"object_indices": candidate}})
        else:
            required.extend(i for i, m in zip(candidate, family["members"]) if m["role"] == "stair")
    profiles = {c["state_profile"] for c in cases}
    if len(profiles) != 1:
        raise InputError("candidate trace mixes state profiles")
    return {"schema_version": 1, "room_id": room_id, "state_profile": profiles.pop(),
            "provenance": {"candidate_trace_sha256": sha256(candidate_trace),
                           "source_note": f"dungeon_contact_translator v0 contract (require={require})"},
            "required_object_indices": required, "assemblies": assemblies,
            **({"wall_boundaries": boundaries} if boundaries else {}),
            "owner_expectations": [], "unsupported": []}


GRID = 64
PLANE = GRID * GRID


def load_dry_steps(path=DEFAULT_LIBRARY):
    data = json.loads(Path(path).read_text())
    if data.get("schema_version") != 1:
        raise InputError("library schema_version must be 1")
    return {r["name"]: r for r in data.get("dry_steps", [])}


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def stream_objects(raw):
    """Every record of one room object stream, in native draw order (list, then index)."""
    writer = load_module("sky_d8_room_writer", HERE / "sky_d8_room_writer.py")
    try:
        stream = writer.parse_object_stream(raw, 0, len(raw))
        objects = []
        for layer, records in enumerate(stream.lists):
            for index, rec in enumerate(records):
                if rec[0] >= 0xFC or rec[2] >= 0xF8:
                    object_id, x, y = writer.decode_object(rec)
                else:
                    object_id, x, y = rec[2], rec[0] >> 2, rec[1] >> 2
                objects.append({"list": layer, "index": index, "object_id": object_id, "x": x, "y": y})
    except writer.PlanError as error:
        raise InputError(str(error)) from error
    if stream.end != len(raw):
        raise InputError(f"stream has {len(raw) - stream.end} bytes after its door terminator")
    return objects


def read_collision(path):
    path = Path(path)
    if path.suffix == ".json":
        data = bytes(json.loads(path.read_text())["attributes"])
    else:
        data = path.read_bytes()
    if len(data) != 2 * PLANE:
        raise InputError(f"collision replay must hold two 64x64 planes (8192 bytes), got {len(data)}")
    return data


def classify_steps(raw, attrs, rule):
    """Admit 1D cells as same-plane steps only where the rule's source conditions hold.

    Result status: OK (cells admitted), UNSUPPORTED (a refused object, slot overflow or
    a replay that differs from the native stamp) or BLOCKED (a wet follower drawn before
    a dry step, so a native slot is overwritten). Only OK admits cells.
    """
    step_id = parse_int(rule["object_id"], "object_id")
    refuse = {parse_int(k, "refuse"): reason for k, reason in rule["refuse"].items()}
    followers = {parse_int(k, "may_follow") for k in rule["may_follow"]}
    plane = rule["walk_plane"]
    step_attr = parse_int(rule["step_attribute"], "step_attribute")
    landing_attr = parse_int(rule["landing_attribute"], "landing_attribute")
    objects = stream_objects(raw)
    at = lambda p, x, y: attrs[p * PLANE + y * GRID + x]
    where = lambda o: {"list": o["list"], "index": o["index"],
                       "object_id": "0x%03X" % o["object_id"], "origin": [o["x"], o["y"]]}
    result = {"schema_version": 1, "tool": "dungeon_contact_translator steps v0", "rule": rule["name"],
              "stream_sha256": hashlib.sha256(raw).hexdigest(),
              "collision_sha256": hashlib.sha256(attrs).hexdigest(), "status": "OK",
              "walk_plane": plane, "steps": [], "wet_followers": [], "admitted_cells": [],
              "unclassified_step_cells": [], "errors": [], "unsupported": [],
              "not_certified": rule["not_certified"]}
    order = [n for n, o in enumerate(objects) if o["object_id"] == step_id]
    if not order:
        result["unsupported"].append({"reason": f"no {rule['object_id']} record in this stream"})
    for o in objects:
        if o["object_id"] in refuse:
            result["unsupported"].append({**where(o), "reason": refuse[o["object_id"]]})
    wet = [(n, o) for n, o in enumerate(objects) if o["object_id"] in followers]
    for n, o in wet:
        if order and n < order[-1]:
            result["errors"].append({"code": "STEP_SLOT_ORDER", **where(o), "reason":
                f"drawn before a {rule['object_id']}; that step reuses the shared NSTAIR slot and overwrites it"})
        else:
            result["wet_followers"].append(where(o))
    if len(order) + len(wet) > rule["slots"]:
        result["unsupported"].append({"reason": f"{len(order) + len(wet)} NSTAIR records exceed the "
                                                f"{rule['slots']} native slots"})
    stamp = [(int(p), dx, dy, parse_int(a, "stamp")) for p, cells in rule["stamp"].items() for dx, dy, a in cells]
    admitted = set()
    for n in order:
        o = objects[n]
        x, y = o["x"], o["y"]
        if x + 4 > GRID or y + 4 > GRID:
            result["unsupported"].append({**where(o), "reason": "4x4 step stamp leaves the 64x64 room"})
            continue
        differs = [[p, x + dx, y + dy, "%02X" % at(p, x + dx, y + dy), "%02X" % a]
                   for p, dx, dy, a in stamp if at(p, x + dx, y + dy) != a]
        landings = {side: [[x + dx, y + dy] for dx, dy in cells] for side, cells in rule["landings"].items()}
        differs += [[plane, c, r, "%02X" % at(plane, c, r), "%02X" % landing_attr]
                    for cells in landings.values() for c, r in cells if at(plane, c, r) != landing_attr]
        if differs:
            result["unsupported"].append({**where(o), "reason": "collision replay differs from the native step "
                                          "stamp or its floor landings ([plane, x, y, actual, expected])",
                                          "cells": differs})
            continue
        core = [[x + dx, y + dy] for dx, dy in rule["core"]]
        admitted.update(map(tuple, core))
        result["steps"].append({**where(o), "core": core, "landings": landings})
    result["unclassified_step_cells"] = [[c, r, plane] for r in range(GRID) for c in range(GRID)
                                         if at(plane, c, r) == step_attr and (c, r) not in admitted]
    if result["errors"]:
        result["status"] = "BLOCKED"
    elif result["unsupported"]:
        result["status"] = "UNSUPPORTED"
    if result["status"] == "OK":
        result["admitted_cells"] = [[c, r, plane] for c, r in sorted(admitted, key=lambda v: (v[1], v[0]))]
    return result, (0 if result["status"] == "OK" else 1)


def route_steps(steps_doc, attrs, pathfinder_path, start, goal, turn_cost=4):
    """Route on the walk plane through admitted step cells only; every other transition stays solid.

    The default find_path outcome is reported unchanged. A path that enters an admitted
    cell sideways is UNSUPPORTED: the native climb ($07BCA0) is measured for vertical moves.
    """
    if steps_doc.get("status") != "OK":
        raise InputError("steps status is not OK; no route")
    pathfinder = load_module("dry_step_pathfind", pathfinder_path)
    plane = steps_doc["walk_plane"]
    layer = bytes(attrs[plane * PLANE:(plane + 1) * PLANE])
    admitted = {(c, r) for c, r, _ in steps_doc["admitted_cells"]}
    plain = pathfinder.Grid(layer)
    try:
        pathfinder.find_path(plain, start, goal, turn_cost)
        default = "PATH"
    except pathfinder.NeedsRoomChangeError:
        default = "NeedsRoomChangeError"
    except pathfinder.NoPathError:
        default = "NoPathError"
    transitions = {(c, r) for r in range(GRID) for c in range(GRID) if plain.kind(c, r) in ("door", "stairs")}
    grid = pathfinder.Grid(layer, blocked=transitions - admitted)
    s, g = grid.snap(*start), grid.snap(*goal)
    nodes = pathfinder._astar(grid, s, g, transitions=True, turn_cost=turn_cost) if s and g else None
    result = {"pathfinder": str(Path(pathfinder_path).resolve()), "pathfinder_sha256": sha256(pathfinder_path),
              "plane": plane, "start": list(start), "goal": list(goal), "default_find_path": default,
              "status": "NO_PATH", "synthetic_edges": 0}
    if not nodes:
        return result, 1
    body = lambda n: set(pathfinder.link_cells(*pathfinder.node_to_link(*n)))
    touched = lambda n: admitted & body(n)
    sideways = [[list(pathfinder.node_to_link(*a)), list(pathfinder.node_to_link(*b))]
                for a, b in zip(nodes, nodes[1:]) if a[1] == b[1] and (touched(a) or touched(b))]
    rows_first = lambda cells: [list(c) for c in sorted(cells, key=lambda v: (v[1], v[0]))]
    result.update(status="UNSUPPORTED" if sideways else "MODEL_PATH",
                  transition_cells_used=rows_first(transitions & set().union(*map(body, nodes))),
                  sideways_step_moves=sideways,
                  waypoints=[list(pathfinder.node_to_link(*nodes[0]))]
                  + [list(pathfinder.node_to_link(*n)) for n in pathfinder._corners(nodes)])
    return result, (0 if result["status"] == "MODEL_PATH" else 1)


def point(text):
    x, y = (int(v, 0) for v in text.split(","))
    return x, y


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
    s = sub.add_parser("steps")
    s.add_argument("--stream", type=Path, required=True, help="room object stream: header, lists, doors")
    s.add_argument("--collision", type=Path, required=True,
                   help="two-plane collision replay of that stream: 8192-byte .bin or JSON 'attributes'")
    s.add_argument("--rule", default="north_merged_dry_step_132")
    s.add_argument("--route", nargs=2, type=point, metavar="X,Y", help="room-local Link start and goal")
    s.add_argument("--pathfinder", type=Path, help="existing scene_director pathfind.py (required with --route)")
    s.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    try:
        library = load_library(args.library)
        if args.command == "translate":
            result, code = translate(json.loads(args.packet.read_text()), library, args.relocate_source)
        elif args.command == "apply":
            result, code = apply_objects(json.loads(args.objects.read_text()), args.rom, args.z3ed, args.write)
        elif args.command == "steps":
            rules = load_dry_steps(args.library)
            if args.rule not in rules:
                raise InputError(f"unknown dry-step rule {args.rule!r} (have: {', '.join(sorted(rules))})")
            if args.route and not args.pathfinder:
                raise InputError("--route needs --pathfinder")
            attrs = read_collision(args.collision)
            result, code = classify_steps(args.stream.read_bytes(), attrs, rules[args.rule])
            if args.route and code == 0:
                result["route"], code = route_steps(result, attrs, args.pathfinder, *args.route)
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
