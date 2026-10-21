#!/usr/bin/env python3
"""Read-only Lyra admission and native render-dependency planning.

Reuse the source-built project adapter's allocation and table contract. The
planner never publishes data, patches a ROM, or enables production endpoints.
Native source tables are copied in memory to show exact proposed intervals.
The table/allocation/decoder contract derives from reviewed source49735f4c;
the old diagnostic builder and its runtime enablement are not imported.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

from lyra_project_terrain import (
    Allocation, FIRST_MAP, MAP_COUNT, compile_terrain, parse_terrain_document,
    quadrant_map_plan, resolve_project_terrain,
)

TABLE_START, TABLE_END = 0x144000, 0x1469C0
CODE_START, CODE_END = 0x3C4000, 0x3C6000
EMPTY_ACTORS = 0x09C881
EMPTY_HIDDEN_ITEMS = 0x9BC5C2
# name, legacySNES, legacy rows, firstID, expanded rows, stride, owned offset
SPECS = (
    ("bg_color", 0x288000, 160, 0, 192, 2, 0x0000),
    ("main_palette", 0x288160, 160, 0, 192, 1, 0x0180),
    ("mosaic", 0x288200, 160, 0, 192, 1, 0x0240),
    ("animated", 0x2882A0, 160, 0, 192, 1, 0x0300),
    ("overlay", 0x288340, 160, 0, 192, 2, 0x03C0),
    ("gfx", 0x288480, 160, 0, 192, 8, 0x0540),
    ("parent", 0x288998, 160, 0, 192, 1, 0x0B40),
    ("ByScreen1", 0x288A38, 160, 0, 192, 2, 0x0C00),
    ("ByScreen2", 0x288B78, 160, 0, 192, 2, 0x0D80),
    ("ByScreen3", 0x288CB8, 160, 0, 192, 2, 0x0F00),
    ("ByScreen4", 0x288DF8, 160, 0, 192, 2, 0x1080),
    ("transition_y", 0x288F38, 160, 0, 192, 2, 0x1200),
    ("transition_x", 0x289078, 160, 0, 192, 2, 0x1380),
    ("scroll_north", 0x2891B8, 160, 0, 192, 2, 0x1500),
    ("scroll_west", 0x2892F8, 160, 0, 192, 2, 0x1680),
    ("sprite_phase0", 0x289438, 160, 0, 192, 2, 0x1800),
    ("sprite_phase1", 0x289578, 160, 0, 192, 2, 0x1980),
    ("sprite_phase2", 0x2896B8, 160, 0, 192, 2, 0x1B00),
    ("sign_text", 0x2897F8, 160, 0, 192, 2, 0x1C80),
    ("map32_high", 0x02F94D, 160, 0, 192, 3, 0x1E00),
    ("map32_low", 0x02FB2D, 160, 0, 192, 3, 0x2040),
    ("bomb_doors", 0x02A644, 160, 0, 192, 2, 0x2280),
    ("hidden_items", 0x02A784, 160, 0, 192, 2, 0x2400),
    ("special_sprite_gfx", 0x02E6E1, 32, 128, 64, 1, 0x2580),
    ("special_sprite_palettes", 0x02E701, 32, 128, 64, 1, 0x25C0),
    ("area_gfx", 0x00FC9C, 160, 0, 192, 1, 0x2600),
    ("special_entry_gfx", 0x02E821, 32, 128, 64, 1, 0x26C0),
    ("music_dark_special", 0x02C403, 96, 64, 128, 1, 0x2700),
    ("area_size", 0x02F88D, 160, 0, 192, 1, 0x2840),
    ("palette_set", 0x09C635, 160, 0, 192, 1, 0x2900),
)
TILE32_BASES = (0x18000, 0x20000, 0x1F0000, 0x1F8000)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def pc(address):
    require(type(address) is int and 0 <= address <= 0xFFFFFF
            and address & 0x8000 and address >> 16 not in (0x7E, 0x7F),
            "Invalid LoROM ROM pointer")
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def snes(offset):
    require(type(offset) is int and 0 <= offset < 0x400000, "Invalid PC offset")
    return 0x808000 | ((offset // 0x8000) << 16) | (offset & 0x7FFF)


def read_tile32(source, tile):
    group, slot = tile // 4 * 6, tile % 4
    values = []
    for base in TILE32_BASES:
        data = source[base + group:base + group + 6]
        require(len(data) == 6, "Truncated native Tile32 definition")
        high = data[4 + slot // 2]
        high = high >> 4 if slot % 2 == 0 else high & 15
        values.append(data[slot] | high << 8)
    return tuple(values)


def expanded_rom(source):
    require(type(source) in (bytes, bytearray) and len(source) in (0x200000, 0x400000),
            "Expected an unheadered2MiB or4MiB native ROM")
    return bytes(source).ljust(0x400000, b"\xFF")


def parse_allocation(value, source):
    require(type(value) is dict, "Malformed Lyra allocation")
    require(set(value) == {
        "kind", "source_rom_sha256", "table_range", "code_range",
        "stream_ranges", "owned_tile32_ids", "expanded_size"}
            | ({"admission"} if "admission" in value else set()), "Malformed Lyra allocation")
    require(value["kind"] == "lyra.project_runtime_allocation.v1"
            and value["source_rom_sha256"] == sha(source),
            "Allocation is not bound to the input ROM")
    require(value["expanded_size"] == 0x400000,
            "Allocation must explicitly authorize a4MiB private build input")
    require(value["table_range"] == [TABLE_START, TABLE_END]
            and value["code_range"] == [CODE_START, CODE_END],
            "Allocation must explicitly own the source contract's table/code ranges")
    ranges = value["stream_ranges"]
    require(type(ranges) is list and ranges, "No explicitly owned map stream ranges")
    occupied = [(TABLE_START, TABLE_END), (CODE_START, CODE_END)]
    for region in ranges:
        require(type(region) is list and len(region) == 2
                and all(type(v) is int for v in region), "Invalid stream allocation")
        start, end = region
        require(0x300000 <= start < end <= 0x400000,
                "Stream allocation must use the expanded ROM")
        require(all(end <= a or start >= b for a, b in occupied),
                "Overlapping Lyra allocation")
        occupied.append((start, end))
    ids = value["owned_tile32_ids"]
    require(type(ids) is list and all(type(v) is int and 0 <= v < 0x4540 for v in ids)
            and len(ids) == len(set(ids)), "Invalid owned Tile32 IDs")
    return Allocation(tuple(tuple(v) for v in ranges), tuple(ids))


def verify_allocation(source, allocation):
    source = expanded_rom(source)
    require(source[TABLE_START:TABLE_END] == bytes(TABLE_END - TABLE_START),
            "Expanded bank28 table allocation is occupied")
    for start, end in ((CODE_START, CODE_END), *allocation.stream_ranges):
        require(source[start:end] == b"\xFF" * (end - start),
                f"Owned expanded allocation is occupied: {start:06X}..{end:06X}")
    require(source[pc(EMPTY_ACTORS)] == 255
            and source[pc(EMPTY_HIDDEN_ITEMS):pc(EMPTY_HIDDEN_ITEMS) + 2] == b"\xFF\xFF",
            "Native empty actor/hidden-item lists differ")


def native_verify(z3ed, project, rom):
    terrain = resolve_project_terrain(project)
    paths = (project, rom, terrain)
    require(all(not os.path.samefile(a, b) for index, a in enumerate(paths)
                for b in paths[index + 1:]), "Project, terrain and source ROM alias each other")
    before = {path: sha(path.read_bytes()) for path in paths}
    command = [str(z3ed), "lyra-verify-project", f"--project-context={project}",
               f"--rom={rom}", "--format=json"]
    try:
        result = subprocess.run(command, check=True, text=True, capture_output=True, timeout=120)
    finally:
        require(all(sha(path.read_bytes()) == digest for path, digest in before.items()),
                "Read-only native verifier changed an input file")
    value = json.loads(result.stdout)
    # The CLI can wrap machine-readable command output in its normal envelope.
    if type(value) is dict and "data" in value:
        value = value["data"]
    require(type(value) is dict and value.get("source_rom_sha256") == before[rom]
            and value.get("terrain_sha256") == before[terrain]
            and value.get("map_count") == 32, "Native verifier binding differs")
    require(value.get("donor_map") == 0x3A, "Unsupported native Lyra profile donor")
    require(value.get("native_tile32_capacity") == 0x4540,
            "Unsupported native Tile32 capacity")
    definitions = value.get("native_definitions")
    require(type(definitions) is list and len(definitions) == 0x4540,
            "Native verifier did not export the complete Tile32 dictionary")
    source = rom.read_bytes()
    require(all(type(q) is list and len(q) == 4
                and all(type(v) is int and 0 <= v < 4096 for v in q)
                and tuple(q) == read_tile32(source, index)
                for index, q in enumerate(definitions)),
            "Native Tile32 export differs from the source ROM")
    return value


def _decode_plane(source, pointer):
    at, output = pc(pointer), bytearray()
    end = (at // 0x8000 + 1) * 0x8000

    def take():
        nonlocal at
        require(at < end, "Unterminated native terrain stream")
        value = source[at]
        at += 1
        return value

    while at < end:
        command = take()
        if command == 255:
            require(len(output) == 256, "Native map extent differs")
            return output
        kind, count = command >> 5, (command & 31) + 1
        if command >= 224:
            kind, count = (command >> 2) & 7, ((command & 3) << 8) + take() + 1
        require(len(output) + count <= 256, "Native terrain decompression overflow")
        if kind == 0:
            output.extend(take() for _ in range(count))
        elif kind == 1:
            output.extend(bytes([take()]) * count)
        elif kind == 2:
            a, b = take(), take()
            output.extend(a if n % 2 == 0 else b for n in range(count))
        elif kind == 3:
            a = take()
            output.extend((a + n) & 255 for n in range(count))
        elif kind == 4:
            offset = take() * 256 + take()
            for n in range(count):
                require(offset + n < len(output), "Invalid native terrain backreference")
                output.append(output[offset + n])
        else:
            raise ValueError("Unsupported native terrain compression command")
    raise ValueError("Native terrain stream lacks a terminator")


def require_legacy_definition_preservation(source, compiled):
    changed = {tile for tile, _ in compiled.new_definitions}
    if not changed:
        return
    for area in range(160):
        planes = [_decode_plane(source, int.from_bytes(
            source[pc(table) + area * 3:pc(table) + area * 3 + 3], "little"))
            for table in (0x02F94D, 0x02FB2D)]
        used = {hi << 8 | lo for hi, lo in zip(*planes)}
        require(not changed.intersection(used),
                f"Owned Tile32 allocation is still referenced by native map{area:02X}")


def _map_ids(values, label):
    require(type(values) in (list, tuple) and all(type(v) is int and 0xA0 <= v <= 0xBF for v in values)
            and len(values) == len(set(values)), f"Invalid {label}")
    return tuple(sorted(values))


def parse_admission(allocation):
    """Extend the existing allocation JSON; absent admission means empty."""
    value = (allocation or {}).get("admission", dict(
        candidate_maps=[], candidate_edge_ids=[], production_maps=[], production_edge_ids=[]))
    require(type(value) is dict and set(value) == {
        "candidate_maps", "candidate_edge_ids", "production_maps", "production_edge_ids"},
        "Malformed Lyra admission")
    maps = _map_ids(value["candidate_maps"], "candidate map IDs")
    _map_ids(value["production_maps"], "production map IDs")
    for key in ("candidate_edge_ids", "production_edge_ids"):
        ids = value[key]
        require(type(ids) is list and all(type(v) is int and 1 <= v <= 0xFFFFFFFF for v in ids)
                and len(ids) == len(set(ids)), f"Invalid {key}")
    require(not value["production_maps"] and not value["production_edge_ids"],
            "Production admission must remain empty until runtime/save/return acceptance")
    return maps, tuple(sorted(value["candidate_edge_ids"]))


def render_dependency_plan(map_ids):
    maps = _map_ids(map_ids, "candidate map IDs")
    directory = {area: quadrant_map_plan(area) for area in maps}
    # Only traversal maps initiate a full load. Render-only dependencies do not
    # recursively acquire traversal admission or their own full-load footprint.
    closure = tuple(sorted({source for row in directory.values() for source in row}))
    require(all(source in closure for row in directory.values() for source in row),
            "Unclosed native render dependencies")
    return directory, closure


def consumer_blockers(document, traversal, closure):
    blockers = []
    for area in closure:
        props = document.properties[area - FIRST_MAP]
        for key in ("graphics_sheets", "main_palette", "palette_set", "animated_sheet"):
            if props[key] != document.profile[key]:
                blockers.append(dict(code="UNSUPPORTED_RENDER_PROFILE", map_id=area, field=key))
    for area in traversal:
        auth = document.authoring[area - FIRST_MAP]
        for key in ("sprites", "doors", "exits"):
            if auth[key]:
                blockers.append(dict(code="UNSUPPORTED_ACTIVE_METADATA", map_id=area, field=key))
        for key in ("sprite_graphics", "sprite_palettes", "music"):
            if len(set(auth["properties"][key])) != 1:
                blockers.append(dict(code="UNSUPPORTED_PHASE_SELECTOR", map_id=area, field=key))
    for flight in document.flight_points:
        if flight["map_id"] in traversal:
            blockers.append(dict(code="UNSUPPORTED_ACTIVE_METADATA", map_id=flight["map_id"], field="flight_points"))
    return blockers


def relocated_table_plan(source, document, compiled, traversal):
    """Propose existing adapter rows, with exact native legacy-copy hashes."""
    rows = []
    donor_bg = int.from_bytes(source[pc(0x288000) + 0x3A * 2:pc(0x288000) + 0x3A * 2 + 2], "little")
    profile = document.profile
    for name, old, legacy, first, count, stride, offset in SPECS:
        original = source[pc(old):pc(old) + legacy * stride]
        require(len(original) == legacy * stride, f"Truncated native table: {name}")
        proposed = bytearray(count * stride)
        proposed[:len(original)] = original
        for plan in compiled.maps:
            if plan.map_id not in traversal and name not in ("map32_high", "map32_low"):
                continue
            area, prop = plan.map_id, plan.properties
            x, y = (area & 7) * 512, ((area & 63) // 8) * 512
            phase = lambda key: 0 if prop[key][0] == -1 else prop[key][0]
            values = dict(
                bg_color=donor_bg, main_palette=profile["main_palette"], mosaic=0,
                animated=profile["animated_sheet"], overlay=255,
                gfx=bytes(profile["graphics_sheets"]), parent=area,
                ByScreen1=0x60, ByScreen2=0x40, ByScreen3=0x1800, ByScreen4=0x1000,
                transition_y=y, transition_x=x, scroll_north=(y - 0xE0) & 0xFFFF,
                scroll_west=(x - 0x100) & 0xFFFF,
                sprite_phase0=EMPTY_ACTORS & 0xFFFF, sprite_phase1=EMPTY_ACTORS & 0xFFFF,
                sprite_phase2=EMPTY_ACTORS & 0xFFFF, sign_text=prop["message_id"],
                map32_high=plan.high.snes, map32_low=plan.low.snes, bomb_doors=0,
                hidden_items=EMPTY_HIDDEN_ITEMS & 0xFFFF,
                special_sprite_gfx=phase("sprite_graphics"), special_sprite_palettes=phase("sprite_palettes"),
                area_gfx=0x30, special_entry_gfx=0x30, music_dark_special=phase("music"),
                area_size=0, palette_set=profile["palette_set"])
            value = values[name]
            raw = value if isinstance(value, bytes) else value.to_bytes(stride, "little")
            at = (area - first) * stride
            proposed[at:at + stride] = raw
        require(proposed[:len(original)] == original, f"Legacy copy differs: {name}")
        rows.append(dict(name=name, legacy_snes=old, legacy_rows=legacy,
                         legacy_sha256=sha(original), first_map=first, rows=count, stride=stride,
                         proposed_pc=[TABLE_START + offset, TABLE_START + offset + len(proposed)],
                         proposed_sha256=sha(proposed)))
    return rows


def plan_admission(source, terrain_text, proof, allocation_value=None, *, candidate_maps=None):
    """Return a deterministic report only. No data or runtime publisher exists here."""
    expanded = expanded_rom(source)
    text_bytes = terrain_text.encode("utf-8") if isinstance(terrain_text, str) else terrain_text
    require(type(proof) is dict and proof.get("source_rom_sha256") == sha(source)
            and proof.get("terrain_sha256") == sha(text_bytes)
            and proof.get("map_count") == MAP_COUNT and proof.get("donor_map") == 0x3A
            and proof.get("native_tile32_capacity") == 0x4540, "Native observation is stale or incomplete")
    native = proof.get("native_definitions")
    require(type(native) is list and len(native) == 0x4540
            and all(type(q) is list and len(q) == 4
                    and all(type(v) is int and 0 <= v < 4096 for v in q)
                    and tuple(q) == read_tile32(source, i) for i, q in enumerate(native)),
            "Native Tile32 observation differs from source ROM")
    bindings = proof.get("verified_asset_bindings")
    require(type(bindings) is list and len(bindings) == MAP_COUNT
            and all(type(v) is list and len(v) == 3 for v in bindings), "Missing map/state bindings")
    document = parse_terrain_document(text_bytes, proof["profile"],
        expected_asset_bindings={FIRST_MAP + i: tuple(v) for i, v in enumerate(bindings)},
        allow_authoring_drafts=True)
    admitted, edge_ids = parse_admission(allocation_value)
    if candidate_maps is not None:
        candidate_maps = _map_ids(candidate_maps, "candidate map IDs")
        require(not admitted or admitted == candidate_maps, "CLI selection differs from allocated admission")
        admitted = candidate_maps
    directory, closure = render_dependency_plan(admitted)
    edges_by_id = {edge["id"]: edge for edge in document.edge_connections}
    require(set(edge_ids) <= set(edges_by_id), "Admission refers to a missing edge ID")
    selected_edges, directed = [], []
    for edge_id in edge_ids:
        edge = edges_by_id[edge_id]
        a, b, passage = edge["map_a"], edge["map_b"], edge["passage"]
        require(passage is not None, "Selected edge needs explicit passage bounds")
        require(all(area < FIRST_MAP or area in admitted for area in (a, b)),
                "Selected edge reaches an unadmitted traversal map")
        require(1 <= passage["first_tile"] <= passage["last_tile"] <= 30,
                "Selected passage leaves the existing swimming probe envelope")
        selected_edges.append(edge)
        forward, reverse = ("south", "north") if b - a == 8 else ("east", "west")
        for src, dst, direction in ((a, b, forward), (b, a, reverse)):
            directed.append(dict(edge_id=edge_id, source=src, destination=dst, direction=direction,
                                 first_pixel=passage["first_tile"] * 16,
                                 end_pixel=(passage["last_tile"] + 1) * 16))
    blockers = consumer_blockers(document, admitted, closure)
    # The reused adapter currently qualifies only a diagnostic99/A1 edge.
    for edge in selected_edges:
        if (edge["map_a"], edge["map_b"]) != (0x99, 0xA1):
            blockers.append(dict(code="UNSUPPORTED_EDGE_CONSUMER", edge_id=edge["id"]))
    compiled, tables = None, []
    allocation = None
    if allocation_value is not None:
        allocation = parse_allocation(allocation_value, source)
        verify_allocation(expanded, allocation)
        if not blockers:
            compiled = compile_terrain(document, {i: tuple(q) for i, q in enumerate(native)},
                                       allocation, map_ids=closure)
            require_legacy_definition_preservation(source, compiled)
            tables = relocated_table_plan(source, document, compiled, admitted) if admitted else []
    elif admitted:
        blockers.append(dict(code="ALLOCATION_REQUIRED"))
    stream_rows = []
    if compiled:
        for plan in compiled.maps:
            for plane, stream in (("high", plan.high), ("low", plan.low)):
                stream_rows.append(dict(map_id=plan.map_id, plane=plane,
                    pc=[stream.pc, stream.pc + len(stream.payload)], snes=stream.snes,
                    bytes=len(stream.payload), sha256=sha(stream.payload)))
    new_ids = {i for i, _ in compiled.new_definitions} if compiled else set()
    reused = sorted({tile for plan in compiled.maps for tile in plan.tiles32} - new_ids) if compiled else []
    qualification = []
    if admitted:
        qualification = ["NORMAL_BUILD_RUNTIME_INTEGRATION_REQUIRED", "ENDPOINT_APPEARANCE_DECISION_REQUIRED",
                         "NATIVE_COLLISION_TRANSITION_MUSIC_CONTROL_REQUIRED", "SAVE_DEATH_CONTINUE_RETURN_UNQUALIFIED"]
    events = sorted(set(admitted) | {a for e in selected_edges for a in (e["map_a"], e["map_b"])})
    return dict(kind="lyra.project_admission_plan.v1", status="candidate_unqualified" if admitted else "no_admission",
        source_rom_sha256=sha(source), terrain_sha256=sha(text_bytes), source_map_count=MAP_COUNT,
        candidate_maps=list(admitted), production_maps=[], production_edge_ids=[],
        render_directory=[dict(map_id=a, quadrant_maps=list(row)) for a, row in directory.items()],
        render_maps=list(closure), render_only_maps=sorted(set(closure) - set(admitted)),
        preserved_draft_maps=sorted(set(range(FIRST_MAP, FIRST_MAP + MAP_COUNT)) - set(admitted)),
        selected_edges=selected_edges, directed_edges=directed,
        unselected_edge_ids=sorted(set(edges_by_id) - set(edge_ids)),
        allocation_verified=allocation is not None, candidate_data_plan_ready=bool(admitted) and compiled is not None and not blockers,
        streams=stream_rows, reused_tile32_ids=reused,
        new_tile32_definitions=[dict(tile32_id=i, quadrants=list(q)) for i, q in compiled.new_definitions] if compiled else [],
        relocated_tables=tables, unpopulated_table_rows="zero; runtime admission gate required",
        native_parent_count=160, legacy_table_writes=[], profile_overrides=[],
        native_99=proof.get("native_99"),
        event_aliases=[dict(map_id=a, legacy_address=0x7EF280 + a,
                           overlaps="item extension $7EF310..$7EF33F") for a in events],
        event_policy="unallocated; old adapter suppression is containment, not persistence",
        consumption_blockers=blockers, qualification_blockers=qualification,
        runtime_build_ready=False, native_gameplay_verified=False, save_reopen_verified=False,
        production_endpoints_enabled=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--z3ed", type=Path, required=True)
    parser.add_argument("--allocation", type=Path)
    parser.add_argument("--candidate-map", action="append", type=lambda v: int(v, 0))
    args = parser.parse_args(argv)
    # Match Yaze's descriptor-relative resolution even when the descriptor is
    # reached through a symlink in a different authoring directory.
    paths = [Path(os.path.abspath(args.project)), args.rom.resolve(strict=True), args.z3ed.resolve(strict=True)]
    paths.append(resolve_project_terrain(paths[0]))
    if args.allocation:
        paths.append(args.allocation.resolve(strict=True))
    before = {path: sha(path.read_bytes()) for path in paths}
    try:
        allocation = json.loads(args.allocation.read_text()) if args.allocation else None
        proof = native_verify(paths[2], paths[0], paths[1])
        report = plan_admission(paths[1].read_bytes(), paths[3].read_bytes(), proof, allocation,
                                candidate_maps=args.candidate_map)
        report["inputs"] = [dict(path=str(path), sha256=digest) for path, digest in before.items()]
    finally:
        require(all(sha(path.read_bytes()) == digest for path, digest in before.items()),
                "Read-only admission planner changed an input")
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError, subprocess.SubprocessError) as error:
        print(f"Lyra admission refused: {error}", file=sys.stderr)
        sys.exit(1)
