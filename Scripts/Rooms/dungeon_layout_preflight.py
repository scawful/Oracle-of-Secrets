#!/usr/bin/env python3
"""Read-only, scoped wall-assembly checks over z3ed native object traces.

This does not render objects, translate primitives, or approve a room. It checks
exact translated reference assemblies and explicit final tile-owner assertions.
Generate traces with `z3ed dungeon-object-validate --room ... --trace-out ...`.
The shared alttp-dungeon-design skill owns the contract schema and workflow.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import sys


WALL_OBJECT_IDS = {1, 2, 3, 4, 0x61, 0x62, 0x63, 0x64, *range(0x100, 0x118)}


class InputError(ValueError):
    """An invalid, stale, or ambiguous input contract."""


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise InputError(f"{name} must be an integer in [{low}, {high}]")
    return value


def indices(value, name):
    if not isinstance(value, list):
        raise InputError(f"{name} must be an array")
    result = [integer(v, name, 0, 65535) for v in value]
    if len(set(result)) != len(result):
        raise InputError(f"{name} contains duplicate object indices")
    return result


def read_trace(path, expected_sha):
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if not isinstance(expected_sha, str) or actual_sha != expected_sha:
        raise InputError(f"trace SHA-256 differs: {path}; actual={actual_sha}")
    data = json.loads(raw)
    cases = data.get("cases")
    if not isinstance(cases, list) or not cases:
        raise InputError(f"trace must contain nonempty room-context cases: {path}")
    objects = {}
    rooms, profiles = set(), set()
    for c in cases:
        index = integer(c["object_index"], "object_index", 0, 65535)
        if index in objects:
            raise InputError(f"duplicate trace object_index {index}")
        rooms.add(integer(c["room_id"], "room_id", 0, 65535))
        if not isinstance(c["state_profile"], str) or not c["state_profile"]:
            raise InputError("state_profile must be a nonempty string")
        profiles.add(c["state_profile"])
        integer(c["object_layer"], "object_layer (stream list)", 0, 2)
        integer(c["object_id_dec"], "object_id_dec", 0, 4095)
        if int(c["object_id"], 16) != c["object_id_dec"]:
            raise InputError(f"object ID text/decimal differs at index {index}")
        integer(c["size"], "size", 0, 255)
        integer(c["object_x"], "object_x", 0, 63)
        integer(c["object_y"], "object_y", 0, 63)
        if not isinstance(c["tiles"], list):
            raise InputError("tiles must be an array")
        for t in c["tiles"]:
            integer(t["layer"], "physical BG", 0, 1)
            # Keep out-of-bounds writes visible; selected assemblies reject them.
            integer(t["x_tile"], "x_tile", -65536, 65535)
            integer(t["y_tile"], "y_tile", -65536, 65535)
            integer(t["tile_id_dec"], "tile_id_dec", 0, 65535)
            integer(t["flags"], "flags", 0, 65535)
            if int(t["tile_id"], 16) != t["tile_id_dec"]:
                raise InputError(f"tile ID text/decimal differs at index {index}")
        objects[index] = c
    if len(rooms) != 1 or len(profiles) != 1:
        raise InputError("trace mixes rooms or state profiles; select one trace per state")
    return objects, rooms.pop(), profiles.pop(), actual_sha


def ordered(objects):
    # Room::RenderRoomGraphics uses primary, BG2 overlay, BG1 overlay passes.
    return sorted(objects.values(), key=lambda c: (c["object_layer"], c["object_index"]))


def cells(c):
    result = defaultdict(set)
    for t in c["tiles"]:
        result[(t["layer"], t["x_tile"], t["y_tile"])].add(
            (t["tile_id_dec"], t["flags"]))
    return result


def final_writes(objects):
    result = {}
    for c in ordered(objects):
        for key, values in cells(c).items():
            # The CLI sorts intra-object traces. Multiple values at one cell
            # lose chronological order and cannot establish a final tile word.
            result[key] = (c, values)
    return result


def late_table_cells(objects):
    """Conservative contacts for untagged global-table records in CLI traces.

    Frozen reference traces expose torches as 0x120. Current Room loaders use
    0x150 for torches and 0xE00 for blocks. The trace omits ObjectOption flags,
    so these records cannot be placed in ordinary stream-pass order reliably.
    Include the native 2x2 table footprint on both BGs when routing is unknown.
    """
    result = set()
    for c in objects.values():
        if c["object_id_dec"] in {0x120, 0x150, 0xE00}:
            result.update(cells(c))
            result.update((bg, x, y) for bg in (0, 1)
                          for x in range(c["object_x"], c["object_x"] + 2)
                          for y in range(c["object_y"], c["object_y"] + 2))
    return result


def describe(write):
    if write is None:
        return None
    c, values = write
    return {"object_index": c["object_index"], "object_id": c["object_id_dec"],
            "stream_list": c["object_layer"], "origin": [c["object_x"], c["object_y"]],
            "tile_values": [list(v) for v in sorted(values)]}


def compare_visible_cell(name, target, reference_write, actual, mapping, error_code):
    """Shared final ordinary-stream ownership gate for assemblies and walls."""
    rc, rv = reference_write
    if len(rv) != 1 or (actual is not None and len(actual[1]) != 1):
        return [], [{"name": name, "reason": "Trace loses intra-object write order",
                     "cell": list(target)}]
    if rc["object_index"] not in mapping:
        return [], [{"name": name, "reason": "Reference footprint is covered by an unbound reference object",
                     "cell": list(target)}]
    expected = mapping[rc["object_index"]]
    if actual is None or (actual[0]["object_index"], actual[1]) != (expected, rv):
        return [{"code": error_code, "name": name, "cell": list(target),
                 "expected_object_index": expected, "actual": describe(actual)}], []
    return [], []


def selected(objects, wanted, name):
    if not wanted:
        raise InputError(f"{name} must select at least one object")
    missing = set(wanted) - objects.keys()
    if missing:
        raise InputError(f"{name} missing trace indices: {sorted(missing)}")
    return {i: objects[i] for i in wanted}


def object_signature(c, dx=0, dy=0):
    # Preserve intra-object multiplicity and physical BG fan-out. Do not use
    # selection rectangles as a substitute for actual native tile writes.
    tiles = Counter((t["layer"], t["x_tile"] + dx, t["y_tile"] + dy,
                     t["tile_id_dec"], t["flags"]) for t in c["tiles"])
    return (c["object_id_dec"], c["size"], c["object_layer"],
            c["object_x"] + dx, c["object_y"] + dy, tiles)


def wall_rectangle(c):
    """Recognize measured rectangular wall footprints, never selection bounds."""
    if c["object_id_dec"] not in WALL_OBJECT_IDS or not c["tiles"]:
        return None
    by_bg = defaultdict(set)
    for (bg, x, y), values in cells(c).items():
        if len(values) != 1:
            return None
        by_bg[bg].add((x, y))
    boxes = []
    for points in by_bg.values():
        x0, y0 = min(x for x, _ in points), min(y for _, y in points)
        x1, y1 = max(x for x, _ in points) + 1, max(y for _, y in points) + 1
        if points != {(x, y) for x in range(x0, x1) for y in range(y0, y1)}:
            return None
        boxes.append((x0, y0, x1, y1))
    # Mixed BG footprints need explicit ports, not a merged bounding rectangle.
    return boxes[0] if len(set(boxes)) == 1 else None


def contact(a, b):
    """A complete shared face in an observed rectangular reference assembly."""
    ax0, ay0, ax1, ay1 = a
    bx0, by0, bx1, by1 = b
    if (ay0, ay1) == (by0, by1):
        if ax1 == bx0:
            return ("E", "W", ("x", ax1, ay0, ay1))
        if bx1 == ax0:
            return ("W", "E", ("x", ax0, ay0, ay1))
    if (ax0, ax1) == (bx0, bx1):
        if ay1 == by0:
            return ("S", "N", ("y", ay1, ax0, ax1))
        if by1 == ay0:
            return ("N", "S", ("y", ay0, ax0, ax1))
    return None


def overlaps(a, b):
    return max(a[0], b[0]) < min(a[2], b[2]) and max(a[1], b[1]) < min(a[3], b[3])


def connected(graph):
    if not graph:
        return False
    visited, pending = set(), [next(iter(graph))]
    while pending:
        node = pending.pop()
        if node not in visited:
            visited.add(node)
            pending.extend(graph[node] - visited)
    return len(visited) == len(graph)


def translate_port(port, dx, dy):
    axis, line, start, end = port
    return (axis, line + (dx if axis == "x" else dy),
            start + (dy if axis == "x" else dx), end + (dy if axis == "x" else dx))


def check_wall_boundary(boundary, objects, contract_directory, actual_state):
    """Check a single closed cycle using reference-measured connective faces.

    Reference/candidate index arrays map one to one. Each object's displacement
    may differ, but its measured native orientation/size/tile writes may not.
    Open mouths, overlapping and diagonal contacts require later explicit-port
    evidence. They are not certified by this rectangular closed-cycle subset.
    """
    name, ref = boundary["name"], boundary["reference"]
    errors, unsupported = [], []
    issue = lambda reason: [{"name": name, "reason": reason}]
    ref_objects, _, ref_state, _ = read_trace(contract_directory / ref["trace"], ref["sha256"])
    if ref_state != actual_state:
        raise InputError(f"reference state profile differs: {name}")
    ref_ids = indices(ref["object_indices"], name)
    candidate_ids = indices(boundary["candidate"]["object_indices"], name)
    reference = selected(ref_objects, ref_ids, name)
    candidate = selected(objects, candidate_ids, name)
    if len(ref_ids) != len(candidate_ids):
        return ([{"code": "WALL_MEMBER_COUNT", "name": name,
                  "expected": len(ref_ids), "actual": len(candidate_ids)}], [], None)
    boxes = {i: wall_rectangle(c) for i, c in reference.items()}
    if len(boxes) < 4 or any(b is None for b in boxes.values()):
        return [], issue("Reference needs measured rectangular wall objects; unknown/diagonal/mixed footprints need explicit ports"), None
    domains = {frozenset(t["layer"] for t in c["tiles"]) for c in reference.values()}
    if len(domains) != 1:
        return [], issue("Reference wall BG domains differ; explicit per-background ports are required"), None
    ports = defaultdict(list)
    graph = {i: set() for i in ref_ids}
    for n, i in enumerate(ref_ids):
        for j in ref_ids[n + 1:]:
            if overlaps(boxes[i], boxes[j]):
                return [], issue("Overlapping reference wall contacts need explicit measured ports"), None
            join = contact(boxes[i], boxes[j])
            if join:
                side_i, side_j, edge = join
                ports[i].append((side_i, edge))
                ports[j].append((side_j, edge))
                graph[i].add(j)
                graph[j].add(i)
    if any(len(graph[i]) != 2 for i in ref_ids) or not connected(graph):
        return [], issue("Reference is not one closed wall cycle; open mouths and junctions need explicit port evidence"), None
    candidate_ports = defaultdict(list)
    candidate_boxes = {}
    uncertain = late_table_cells(objects)
    reference_uncertain = late_table_cells(ref_objects)
    reference_owners, actual_owners = final_writes(ref_objects), final_writes(objects)
    mapping = dict(zip(ref_ids, candidate_ids))
    for ri, ci in zip(ref_ids, candidate_ids):
        r, c = reference[ri], candidate[ci]
        dx, dy = c["object_x"] - r["object_x"], c["object_y"] - r["object_y"]
        if object_signature(r, dx, dy) != object_signature(c):
            errors.append({"code": "WALL_OBJECT_MISMATCH", "name": name, "object_index": ci,
                           "reason": "Wall/corner native orientation, size, stream list, or tile writes differ from reference"})
            continue
        candidate_boxes[ci] = tuple(v + (dx if k % 2 == 0 else dy) for k, v in enumerate(boxes[ri]))
        if not all(0 <= v <= 64 for v in candidate_boxes[ci]):
            errors.append({"code": "WALL_OUT_OF_BOUNDS", "name": name, "object_index": ci})
        if set(cells(c)) & uncertain or set(cells(r)) & reference_uncertain:
            unsupported.extend(issue("Global-table draw pass/source flags are absent at wall contacts"))
        for bg, x, y in cells(r):
            target = (bg, x + dx, y + dy)
            if (bg, x, y) in reference_uncertain or target in uncertain:
                continue
            cell_errors, cell_unsupported = compare_visible_cell(
                name, target, reference_owners[(bg, x, y)], actual_owners.get(target), mapping, "WALL_OVERWRITTEN")
            errors.extend(cell_errors)
            unsupported.extend(cell_unsupported)
        for side, port in ports[ri]:
            candidate_ports[translate_port(port, dx, dy)].append((ci, side))
    if len(candidate_boxes) != len(candidate_ids):
        return errors, unsupported, None
    candidate_graph = {i: set() for i in candidate_ids}
    opposite = {"N": "S", "S": "N", "E": "W", "W": "E"}
    for port, ends in candidate_ports.items():
        if len(ends) != 2 or ends[0][0] == ends[1][0] or opposite[ends[0][1]] != ends[1][1]:
            errors.append({"code": "WALL_UNCONNECTED_PORT" if len(ends) == 1 else "WALL_INVALID_JOIN",
                           "name": name, "port": list(port),
                           "objects": [{"object_index": i, "face": side} for i, side in ends]})
            continue
        a, b = ends[0][0], ends[1][0]
        candidate_graph[a].add(b)
        candidate_graph[b].add(a)
    for n, i in enumerate(candidate_ids):
        for j in candidate_ids[n + 1:]:
            if overlaps(candidate_boxes[i], candidate_boxes[j]):
                errors.append({"code": "WALL_OVERLAP", "name": name, "object_indices": [i, j]})
    if not errors and (any(len(v) != 2 for v in candidate_graph.values()) or not connected(candidate_graph)):
        errors.append({"code": "WALL_NOT_ONE_CYCLE", "name": name,
                       "reason": "Boundary must be one connected cycle, not disconnected loops or branches"})
    result = None if errors or unsupported else {"name": name, "objects": len(candidate_ids),
                                                "joins": len(candidate_ports), "closed": True}
    return errors, unsupported, result


CONTACT_LIBRARY = Path(__file__).resolve().parent / "data/dungeon_contact_library.json"
CUT_ROLES = {"wall", "corner"}


def load_contact_library():
    """Measured stair-mouth contacts. Fixed repo path: a contract cannot add families."""
    data = json.loads(CONTACT_LIBRARY.read_text())
    return {f["name"]: f for f in data["families"]}


def contact_digest(members, anchor):
    """Native writes of an ordered contact relative to its stair, independent of trace file."""
    ax, ay = anchor["object_x"], anchor["object_y"]
    rows = [[c["object_id_dec"], c["size"], c["object_layer"], c["object_x"] - ax, c["object_y"] - ay,
             sorted([t["layer"], t["x_tile"] - ax, t["y_tile"] - ay, t["tile_id_dec"], t["flags"]]
                    for t in c["tiles"])] for c in members]
    return hashlib.sha256(json.dumps(rows, separators=(",", ":")).encode()).hexdigest()


def check_stair_mouth(boundary, objects, contract_directory, actual_state):
    """Check a rigid copy of one measured wall-cutting stair contact.

    Only families in the repo contact library qualify, and only when the
    reference members reproduce the library's contact digest. The candidate
    must keep every native write at one shared offset, draw the stair after
    the walls it cuts, and keep the stair as final owner of the mouth cells.
    The run's outer ends are not certified joined to the rest of the room.
    """
    name, ref = boundary["name"], boundary["reference"]
    issue = lambda reason: ([], [{"name": name, "reason": reason}], None)
    if not isinstance(boundary.get("family"), str):
        raise InputError(f"stair mouth family must be a string: {name}")
    family = load_contact_library().get(boundary.get("family"))
    if family is None:
        return issue("Stair mouth family is not a measured contact; open mouths need measured evidence")
    ref_objects, _, ref_state, _ = read_trace(contract_directory / ref["trace"], ref["sha256"])
    if ref_state != actual_state:
        raise InputError(f"reference state profile differs: {name}")
    ref_ids = indices(ref["object_indices"], name)
    candidate_ids = indices(boundary["candidate"]["object_indices"], name)
    reference = selected(ref_objects, ref_ids, name)
    candidate = selected(objects, candidate_ids, name)
    roles = [m["role"] for m in family["members"]]
    if len(ref_ids) != len(roles) or roles.count("stair") != 1:
        return issue("Reference members differ from the measured contact")
    if len(candidate_ids) != len(ref_ids):
        return ([{"code": "WALL_MEMBER_COUNT", "name": name,
                  "expected": len(ref_ids), "actual": len(candidate_ids)}], [], None)
    stair = roles.index("stair")
    ref_members = [reference[i] for i in ref_ids]
    cand_members = [candidate[i] for i in candidate_ids]
    if (contact_digest(ref_members, ref_members[stair]) != family.get("contact_sha256")
            or ordered(reference) != ref_members):
        return issue("Reference trace is not the measured contact in its measured draw order")
    dx = cand_members[stair]["object_x"] - ref_members[stair]["object_x"]
    dy = cand_members[stair]["object_y"] - ref_members[stair]["object_y"]
    if any(object_signature(r, dx, dy) != object_signature(c) for r, c in zip(ref_members, cand_members)):
        return issue("Candidate is not a rigid copy of the measured contact; rotated, mirrored, "
                     "resized or re-spaced mouths need measured evidence")
    if ordered(candidate) != cand_members:
        return ([{"code": "STAIR_MOUTH_ORDER", "name": name,
                  "reason": "Stair must be drawn after the walls it cuts, in the measured member order",
                  "draw_order": [c["object_index"] for c in ordered(candidate)]}], [], None)
    local_owners = final_writes(reference)
    stair_index = ref_members[stair]["object_index"]
    cut_cells = {key for r, role in zip(ref_members, roles) if role in CUT_ROLES for key in cells(r)}
    mouth = {key for key in cells(ref_members[stair]) if key in cut_cells}
    if not mouth or any(local_owners[key][0]["object_index"] != stair_index for key in mouth):
        return issue("Measured contact has no stair-owned mouth over a wall")
    errors, unsupported = [], []
    uncertain = late_table_cells(objects)
    actual_owners = final_writes(objects)
    mapping = dict(zip(ref_ids, candidate_ids))
    for bg, x, y in sorted(local_owners):
        target = (bg, x + dx, y + dy)
        if not (0 <= target[1] < 64 and 0 <= target[2] < 64):
            errors.append({"code": "WALL_OUT_OF_BOUNDS", "name": name, "cell": list(target)})
            continue
        if target in uncertain:
            unsupported.append({"name": name, "reason": "Global-table draw pass/source flags are absent at stair mouth",
                                "cell": list(target)})
            continue
        cell_errors, cell_unsupported = compare_visible_cell(
            name, target, local_owners[(bg, x, y)], actual_owners.get(target), mapping,
            "STAIR_MOUTH_OWNER" if (bg, x, y) in mouth else "WALL_OVERWRITTEN")
        errors.extend(cell_errors)
        unsupported.extend(cell_unsupported)
    result = None if errors or unsupported else {
        "name": name, "kind": "stair_mouth", "family": family["name"], "objects": len(candidate_ids),
        "mouth_cells": len(mouth), "translation": [dx, dy], "closed": False, "ends_certified": False}
    return errors, unsupported, result


def check(contract, trace_path, contract_directory):
    if type(contract.get("schema_version")) is not int or contract["schema_version"] != 1:
        raise InputError("schema_version must be 1")
    if contract.get("design", {}).get("stage") == "primitive":
        return {"schema_version": 1, "status": "UNSUPPORTED", "errors": [],
                "unsupported": [{"name": "primitive design", "reason": "Native assembly bindings and traces are required"}],
                "scope": "Primitive geometry is not native assembly proof"}
    if trace_path is None:
        raise InputError("--trace is required for native assembly checks")
    room = integer(contract["room_id"], "room_id", 0, 65535)
    state = contract["state_profile"]
    objects, actual_room, actual_state, sha = read_trace(
        trace_path, contract["provenance"]["candidate_trace_sha256"])
    if (room, state) != (actual_room, actual_state):
        raise InputError("contract room/state does not match candidate trace")
    errors, unsupported, checked = [], list(contract.get("unsupported", [])), []
    for item in unsupported:
        if not isinstance(item, dict) or not item.get("name") or not item.get("reason"):
            raise InputError("unsupported entries require name and reason")
    required = indices(contract.get("required_object_indices", []), "required_object_indices")
    if set(required) - objects.keys():
        raise InputError("required_object_indices includes an absent trace object")
    owners = final_writes(objects)
    late_cells = late_table_cells(objects)
    bound = set()
    for assembly in contract.get("assemblies", []):
        name = assembly["name"]
        ref = assembly["reference"]
        ref_objects, _, ref_state, _ = read_trace(
            contract_directory / ref["trace"], ref["sha256"])
        if ref_state != actual_state:
            raise InputError(f"reference state profile differs: {name}")
        reference = selected(ref_objects, indices(ref["object_indices"], name), name)
        candidate = selected(objects, indices(assembly["candidate"]["object_indices"], name), name)
        translation = assembly["translation"]
        if not isinstance(translation, list) or len(translation) != 2:
            raise InputError(f"translation requires [dx, dy]: {name}")
        dx, dy = [integer(v, "translation", -63, 63) for v in translation]
        if bound & candidate.keys():
            raise InputError(f"candidate objects bound to multiple assemblies: {name}")
        bound.update(candidate)
        reference_order, candidate_order = ordered(reference), ordered(candidate)
        if ([object_signature(c, dx, dy) for c in reference_order]
                != [object_signature(c) for c in candidate_order]):
            errors.append({"code": "ASSEMBLY_MISMATCH", "name": name,
                           "reason": "Native objects, relative positions, draw order, or tile writes differ"})
            continue
        ref_owners = final_writes(ref_objects)
        ref_late_cells = late_table_cells(ref_objects)
        assembly_cells = {key for c in reference.values() for key in cells(c)}
        if not assembly_cells:
            unsupported.append({"name": name, "reason": "Assembly has no native tile writes"})
        mapping = {r["object_index"]: c["object_index"]
                   for r, c in zip(reference_order, candidate_order)}
        for bg, x, y in sorted(assembly_cells):
            target = (bg, x + dx, y + dy)
            if not (0 <= target[1] < 64 and 0 <= target[2] < 64):
                errors.append({"code": "ASSEMBLY_OUT_OF_BOUNDS", "name": name,
                               "cell": list(target)})
                continue
            if target in late_cells or (bg, x, y) in ref_late_cells:
                unsupported.append({"name": name, "reason": "Global-table draw pass/source flags are absent from trace",
                                    "cell": list(target)})
                continue
            cell_errors, cell_unsupported = compare_visible_cell(
                name, target, ref_owners[(bg, x, y)], owners.get(target), mapping, "ASSEMBLY_OVERWRITTEN")
            errors.extend(cell_errors)
            unsupported.extend(cell_unsupported)
        checked.append(name)
    checked_boundaries, boundary_objects, stair_members = [], set(), set()
    for boundary in contract.get("wall_boundaries", []):
        kind = boundary.get("kind", "closed_cycle")
        if kind not in ("closed_cycle", "stair_mouth"):
            raise InputError(f"unknown wall boundary kind: {kind!r}")
        checker = check_stair_mouth if kind == "stair_mouth" else check_wall_boundary
        wall_errors, wall_unsupported, result = checker(boundary, objects, contract_directory, actual_state)
        errors.extend(wall_errors)
        unsupported.extend(wall_unsupported)
        members = indices(boundary["candidate"]["object_indices"], boundary["name"])
        if (kind == "stair_mouth" and boundary_objects & set(members)) or stair_members & set(members):
            raise InputError(f"stair mouth objects shared with another wall boundary: {boundary['name']}")
        if kind == "stair_mouth":
            stair_members.update(members)
        bound.update(members)
        boundary_objects.update(members)
        if result is not None:
            checked_boundaries.append(result)
    for index in sorted(set(required) - bound):
        unsupported.append({"name": f"object[{index}]", "reason": "Changed structural object has no reference assembly binding"})
    for index in sorted(set(required) - boundary_objects):
        if objects[index]["object_id_dec"] in WALL_OBJECT_IDS:
            unsupported.append({"name": f"object[{index}]", "reason": "Changed wall/corner has no verified boundary; an exact object copy does not prove connectivity"})
    expectations = contract.get("owner_expectations", [])
    for expectation in expectations:
        key = (integer(expectation["bg"], "bg", 0, 1),
               integer(expectation["x"], "x", 0, 63), integer(expectation["y"], "y", 0, 63))
        allowed = [integer(v, "allowed_object_ids", 0, 4095)
                   for v in expectation["allowed_object_ids"]]
        if not allowed:
            raise InputError("allowed_object_ids must not be empty")
        actual = owners.get(key)
        if key in late_cells:
            unsupported.append({"name": expectation["name"], "reason": "Global-table draw pass/source flags are absent from trace",
                                "cell": list(key)})
        elif actual is not None and len(actual[1]) != 1:
            unsupported.append({"name": expectation["name"], "reason": "Trace loses intra-object write order",
                                "cell": list(key)})
        elif actual is None or actual[0]["object_id_dec"] not in allowed:
            errors.append({"code": "WRONG_FINAL_OWNER", "name": expectation["name"],
                           "cell": list(key), "allowed_object_ids": allowed, "actual": describe(actual)})
    if not checked and not checked_boundaries and not expectations:
        unsupported.append({"name": "evidence", "reason": "No native assembly or tile-owner assertion was checked"})
    return {"schema_version": 1, "status": "BLOCKED" if errors else "UNSUPPORTED" if unsupported else "PASS",
            "room_id": room, "state_profile": state, "candidate_trace_sha256": sha,
            "scope": "Declared native assemblies, closed wall boundaries, measured stair-mouth contacts, and tile-owner assertions only; not room approval",
            "excluded": ["unlisted geometry", "stair-mouth run ends", "global-table draw passes", "collision/routes", "reveal masks/composite", "doors/layout", "native gameplay"],
            "checked": {"assemblies": checked, "owner_expectations": len(expectations),
                        "wall_boundaries": checked_boundaries, "required_objects": len(required)},
            "errors": errors, "unsupported": unsupported}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--contract", required=True, type=Path)
    parser.add_argument("--trace", type=Path, help="required for native assembly checks")
    args = parser.parse_args(argv)
    try:
        contract = json.loads(args.contract.read_text())
        result = check(contract, args.trace, args.contract.resolve().parent)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as error:
        print(json.dumps({"status": "INPUT_ERROR", "error": str(error)}, indent=2))
        return 2
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
