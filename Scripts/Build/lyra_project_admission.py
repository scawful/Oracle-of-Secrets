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
import struct
import subprocess
import sys

from lyra_project_terrain import (
    Allocation, FIRST_MAP, MAP_COUNT, TerrainDocument, compile_terrain,
    gameplay_area_footprint, gameplay_render_directory, parse_terrain_document, quadrant_map_plan,
    resolve_project_terrain, validated_gameplay_areas,
)
from lyra_native_state import plan_native_state

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
            | ({"admission"} if "admission" in value else set())
            | ({"tile32_assignment"} if "tile32_assignment" in value else set())
            | ({"private_reservation"} if "private_reservation" in value else set())
            | ({"reservation"} if "reservation" in value else set()), "Malformed Lyra allocation")
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
    private_grant = "private_reservation" in value
    if private_grant:
        from lyra_private_reservation import verify_private_allocation
        verify_private_allocation(value, source)
    occupied = [(TABLE_START, TABLE_END), (CODE_START, CODE_END)]
    for region in ranges:
        require(type(region) is list and len(region) == 2
                and all(type(v) is int for v in region), "Invalid stream allocation")
        start, end = region
        require((private_grant and region == [0x133D3A, 0x138000])
                or 0x300000 <= start < end <= 0x400000,
                "Stream allocation must use the expanded ROM")
        require(all(end <= a or start >= b for a, b in occupied),
                "Overlapping Lyra allocation")
        occupied.append((start, end))
    ids = value["owned_tile32_ids"]
    require(type(ids) is list and all(type(v) is int and 0 <= v < 0x4540 for v in ids)
            and len(ids) == len(set(ids)), "Invalid owned Tile32 IDs")
    assignments = None
    if "tile32_assignment" in value:
        require("reservation" in value, "Source reservation required for Tile32 assignments")
        contract = value["tile32_assignment"]
        require(type(contract) is dict and type(contract.get("assignments")) is list
                and all(type(r) is dict and set(r) == {"tile32_id", "quadrants"}
                        and type(r["tile32_id"]) is int and type(r["quadrants"]) is list
                        for r in contract["assignments"]), "Malformed Tile32 assignments")
        assignments = tuple((r["tile32_id"], tuple(r["quadrants"])) for r in contract["assignments"])
    return Allocation(tuple(tuple(v) for v in ranges), tuple(ids), tile32_assignments=assignments)


def verify_allocation(source, allocation, reservation=None, tile32_assignment=None):
    if reservation is not None:
        from lyra_project_allocation import verify_reservation
        verify_reservation(source, allocation, reservation, tile32_assignment=tile32_assignment)
    source = expanded_rom(source)
    if reservation is None:
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
        "candidate_maps", "candidate_edge_ids", "production_maps", "production_edge_ids"}
            | ({"render_footprints"} if "render_footprints" in value else set()),
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


def gameplay_area_plan(document):
    """Describe explicit authored areas without assigning storage or admission."""
    require(isinstance(document, TerrainDocument),
            "Gameplay area plan requires a parsed TerrainDocument")
    raw = document.gameplay_areas
    # Only the parsed legacy default is unassigned. Malformed falsey values
    # still pass through the shared validator rather than disappearing.
    areas = () if type(raw) is tuple and not raw else validated_gameplay_areas(raw)
    size_codes = {"small": 0, "large": 1, "wide": 2, "tall": 3}
    assignments, footprints = [], []
    for area in areas:
        parent, size = area["parent_map_id"], area["size"]
        members = gameplay_area_footprint(parent, size)
        if size == "small":
            quadrants = members * 4
        elif size == "wide":
            quadrants = members * 2
        elif size == "tall":
            quadrants = (members[0], members[0], members[1], members[1])
        else:
            quadrants = members
        for map_id in members:
            assignments.append(dict(map_id=map_id, parent_map_id=parent,
                                    size=size, area_size_code=size_codes[size]))
            footprints.append(dict(map_id=map_id, quadrant_maps=list(quadrants)))
    assigned = {row["map_id"] for row in assignments}
    unassigned = [map_id for map_id in range(FIRST_MAP, FIRST_MAP + MAP_COUNT)
                  if map_id not in assigned]
    complete = not unassigned
    return dict(kind="lyra.gameplay_area_source_plan.v1",
                status="ASSIGNED" if complete else "PARTIAL" if areas else "UNASSIGNED",
                complete=complete, areas=list(areas), assignments=assignments,
                render_footprints=footprints, unassigned_maps=unassigned,
                allocation_granted=False, publication_authorized=False,
                runtime_admission=False)


def render_dependency_plan(map_ids, footprints=(), *, document=None):
    maps = _map_ids(map_ids, "candidate map IDs")
    authored = gameplay_render_directory(document.gameplay_areas) if document is not None and document.gameplay_areas else {}
    require(not authored or set(maps) <= set(authored),
            "CURRENT_GAMEPLAY_AREAS_UNASSIGNED: selected pages need explicit gameplay areas")
    directory = {area: authored.get(area, quadrant_map_plan(area)) for area in maps}
    require(type(footprints) in (list, tuple), "Malformed render footprints")
    seen = set()
    for entry in footprints:
        require(type(entry) is dict and set(entry) == {"map_id", "quadrant_maps"},
                "Malformed render footprint")
        area, row = entry["map_id"], entry["quadrant_maps"]
        require(type(area) is int and area in directory and area not in seen,
                "Render footprint must name one selected traversal map")
        require(type(row) in (list, tuple) and len(row) == 4
                and all(type(v) is int for v in row)
                and (tuple(row) == authored[area] if area in authored
                     else tuple(row) in (quadrant_map_plan(area), (area,) * 4)),
                "Render footprint must be natural or explicitly isolated")
        directory[area] = tuple(row)
        seen.add(area)
    # Only traversal maps initiate a full load. Render-only dependencies do not
    # recursively acquire traversal admission or their own full-load footprint.
    closure = tuple(sorted({source for row in directory.values() for source in row}))
    require(all(source in closure for row in directory.values() for source in row),
            "Unclosed native render dependencies")
    return directory, closure


def _background_palette_payload(colors):
    payload = struct.pack("<128H", *colors)
    return dict(word_count=128, payload_hex=payload.hex(), sha256=sha(payload),
                runtime_consumer="unbound")


def appearance_plan(source, document, directory):
    """Preserve saved selectors and prove conservative render-slot coherence.

    Different used sheet/palette selectors remain unqualified even if their
    art might happen to match. No draft is rewritten to fit a loaded profile.
    """
    at = pc(int.from_bytes(source[0x865:0x868], "little"))
    definitions = source[at:at + document.profile["tile_count"] * 8]
    require(len(definitions) == document.profile["tile_count"] * 8
            and sha(definitions) == document.profile["tile16_definition_fingerprint"],
            "Native Tile16 observation differs from source ROM")
    rows, contexts, blockers = [], [], []
    for area, dependencies in directory.items():
        prop = document.properties[area - FIRST_MAP]
        native_rows = []
        for field, table in (("graphics_sheets", "gfx"), ("main_palette", "main_palette"),
                             ("palette_set", "palette_set"), ("animated_sheet", "animated")):
            spec = next(row for row in SPECS if row[0] == table)
            value = prop[field]
            payload = bytes(value) if isinstance(value, list) else bytes([value])
            native_rows.append(dict(table=table, pc=TABLE_START + spec[6] + area * spec[5],
                                    payload_hex=payload.hex()))
        row = dict(map_id=area, graphics_sheets=prop["graphics_sheets"],
                         main_palette=prop["main_palette"], palette_set=prop["palette_set"],
                         animated_sheet=prop["animated_sheet"],
                         native_table_rows=native_rows,
                         asset_bindings=document.authoring[area - FIRST_MAP]["asset_bindings"])
        if "background_palette" in prop:
            row["background_palette"] = _background_palette_payload(prop["background_palette"])
            blockers.append(dict(code="UNSUPPORTED_BACKGROUND_PALETTE", map_id=area))
        rows.append(row)
        if 255 in prop["graphics_sheets"] or prop["animated_sheet"] in (0, 255):
            blockers.append(dict(code="UNSUPPORTED_NATIVE_SELECTOR", map_id=area))
        for dependency in sorted(set(dependencies)):
            other = document.properties[dependency - FIRST_MAP]
            tiles = set(document.maps[dependency - FIRST_MAP])
            chars = {word & 1023 for tile in tiles
                     for word in struct.unpack_from("<4H", definitions, tile * 8)}
            slots = sorted({char // 64 for char in chars})
            differences = []
            for slot in slots:
                if slot < 8 and prop["graphics_sheets"][slot] != other["graphics_sheets"][slot]:
                    differences.append(f"graphics_sheets[{slot}]")
            for key in ("main_palette", "palette_set", "sprite_palettes"):
                if prop[key] != other[key]:
                    differences.append(key)
            if prop.get("background_palette") != other.get("background_palette"):
                differences.append("background_palette")
            if any(448 <= char < 480 for char in chars) and prop["animated_sheet"] != other["animated_sheet"]:
                differences.append("animated_sheet")
            if any(slot >= 8 for slot in slots) and prop["sprite_graphics"] != other["sprite_graphics"]:
                differences.append("sprite_graphics")
            context = dict(map_id=area, source_map=dependency, tile16_count=len(tiles),
                           used_graphics_slots=slots, differing_selectors=differences,
                           coherent=not differences)
            if "background_palette" in other:
                context["background_palette"] = _background_palette_payload(other["background_palette"])
            contexts.append(context)
            if differences:
                blockers.append(dict(code="RENDER_APPEARANCE_UNPROVEN", map_id=area,
                                     source_map=dependency, fields=differences))
    return dict(selector_rows=rows, render_contexts=contexts,
                coherent=not blockers, blockers=blockers)


def consumer_blockers(document, traversal, closure):
    blockers = []
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


def relocated_table_payloads(source, document, compiled, traversal):
    """Produce adapter bytes once for both the planner and ordinary publisher."""
    require(not getattr(document, "gameplay_areas", ()),
            "Historical table publisher has no authored gameplay area consumer")
    # These tables have palette selectors, but no loader for project BG words.
    # Direct publisher callers must not bypass the admission planner's refusal.
    require(all("background_palette" not in plan.properties for plan in compiled.maps),
            "Native table publisher has no background palette consumer")
    rows = []
    donor_bg = int.from_bytes(source[pc(0x288000) + 0x3A * 2:pc(0x288000) + 0x3A * 2 + 2], "little")
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
                bg_color=donor_bg, main_palette=prop["main_palette"], mosaic=0,
                animated=prop["animated_sheet"], overlay=255,
                gfx=bytes(prop["graphics_sheets"]), parent=area,
                ByScreen1=0x60, ByScreen2=0x40, ByScreen3=0x1800, ByScreen4=0x1000,
                transition_y=y, transition_x=x, scroll_north=(y - 0xE0) & 0xFFFF,
                scroll_west=(x - 0x100) & 0xFFFF,
                sprite_phase0=EMPTY_ACTORS & 0xFFFF, sprite_phase1=EMPTY_ACTORS & 0xFFFF,
                sprite_phase2=EMPTY_ACTORS & 0xFFFF, sign_text=prop["message_id"],
                map32_high=plan.high.snes, map32_low=plan.low.snes, bomb_doors=0,
                hidden_items=EMPTY_HIDDEN_ITEMS & 0xFFFF,
                special_sprite_gfx=phase("sprite_graphics"), special_sprite_palettes=phase("sprite_palettes"),
                area_gfx=0x30, special_entry_gfx=0x30, music_dark_special=phase("music"),
                area_size=0, palette_set=prop["palette_set"])
            value = values[name]
            raw = value if isinstance(value, bytes) else value.to_bytes(stride, "little")
            at = (area - first) * stride
            proposed[at:at + stride] = raw
        require(proposed[:len(original)] == original, f"Legacy copy differs: {name}")
        rows.append(dict(name=name, legacy_snes=old, legacy_rows=legacy,
                         legacy_sha256=sha(original), first_map=first, rows=count, stride=stride,
                         proposed_pc=[TABLE_START + offset, TABLE_START + offset + len(proposed)],
                         proposed_sha256=sha(proposed), payload_hex=proposed.hex()))
    return rows


def relocated_table_plan(source, document, compiled, traversal):
    """Propose existing adapter rows, preserving the public report format."""
    return [{key: value for key, value in row.items() if key != "payload_hex"}
            for row in relocated_table_payloads(source, document, compiled, traversal)]


def plan_admission(source, terrain_text, proof, allocation_value=None, *, candidate_maps=None,
                   state_symbols=None, state_ownership=None):
    """Return a deterministic report only. No data or runtime publisher exists here."""
    expanded_rom(source)
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
    footprints = ((allocation_value or {}).get("admission") or {}).get("render_footprints", ())
    directory, closure = render_dependency_plan(admitted, footprints)
    appearance = appearance_plan(source, document, directory) if admitted else dict(
        selector_rows=[], render_contexts=[], coherent=True, blockers=[])
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
    blockers = appearance["blockers"] + consumer_blockers(document, admitted, closure)
    needed_quartets = set()
    for area in closure:
        cells = document.maps[area - FIRST_MAP]
        needed_quartets.update((cells[y * 32 + x], cells[y * 32 + x + 1],
                               cells[(y + 1) * 32 + x], cells[(y + 1) * 32 + x + 1])
                              for y in range(0, 32, 2) for x in range(0, 32, 2))
    missing_quartets = sorted(needed_quartets - {tuple(q) for q in native})
    # The reused adapter currently qualifies only a diagnostic99/A1 edge.
    for edge in selected_edges:
        if (edge["map_a"], edge["map_b"]) != (0x99, 0xA1):
            blockers.append(dict(code="UNSUPPORTED_EDGE_CONSUMER", edge_id=edge["id"]))
    compiled, tables = None, []
    allocation = None
    if allocation_value is not None:
        allocation = parse_allocation(allocation_value, source)
        assignment = allocation_value.get("tile32_assignment")
        verify_allocation(source, allocation, allocation_value.get("reservation"), assignment)
        if assignment is not None:
            from lyra_project_tile32 import verify_input
            verify_input(source, text_bytes, admitted, directory, missing_quartets, assignment)
        if missing_quartets and not allocation.owned_tile32_ids:
            blockers.append(dict(code="TILE32_ALLOCATION_REQUIRED", missing_definitions=len(missing_quartets)))
        if len(closure) * 518 > sum(end - start for start, end in allocation.stream_ranges):
            blockers.append(dict(code="STREAM_ALLOCATION_REQUIRED", minimum_bytes=len(closure) * 518))
        if not blockers:
            compiled = compile_terrain(document, {i: tuple(q) for i, q in enumerate(native)},
                                       allocation, map_ids=closure, render_directory=directory)
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
    tile32_writes = None
    if compiled is not None and allocation.tile32_assignments is not None:
        from lyra_project_tile32 import packed_write_plan
        tile32_writes = packed_write_plan(source, document, compiled, allocation)
    reused = sorted({tile for plan in compiled.maps for tile in plan.tiles32} - new_ids) if compiled else []
    qualification = []
    if admitted:
        qualification = ["NORMAL_BUILD_RUNTIME_INTEGRATION_REQUIRED", "ENDPOINT_APPEARANCE_DECISION_REQUIRED",
                         "NATIVE_COLLISION_TRANSITION_MUSIC_CONTROL_REQUIRED", "SAVE_DEATH_CONTINUE_RETURN_UNQUALIFIED"]
        if any(row != quadrant_map_plan(area) for area, row in directory.items()):
            qualification.append("ISOLATED_FOOTPRINT_NATIVE_QUALIFICATION_REQUIRED")
    events = sorted(set(admitted) | {a for e in selected_edges for a in (e["map_a"], e["map_b"])})
    state = plan_native_state(source, events, authoring=[
        (area, document.authoring[area - FIRST_MAP]) for area in admitted],
        symbols=state_symbols, ownership=state_ownership)
    return dict(kind="lyra.project_admission_plan.v1", status="candidate_unqualified" if admitted else "no_admission",
        source_rom_sha256=sha(source), terrain_sha256=sha(text_bytes), source_map_count=MAP_COUNT,
        candidate_maps=list(admitted), production_maps=[], production_edge_ids=[],
        render_directory=[dict(map_id=a, quadrant_maps=list(row)) for a, row in directory.items()],
        render_maps=list(closure), render_only_maps=sorted(set(closure) - set(admitted)),
        appearance=appearance,
        tile32_requirements=dict(unique_quartets=len(needed_quartets),
                                 missing_definitions=[list(q) for q in missing_quartets]),
        stream_requirements=dict(minimum_bytes=len(closure) * 518,
                                 reserved_bytes=sum(end - start for start, end in allocation.stream_ranges) if allocation else 0),
        preserved_draft_maps=sorted(set(range(FIRST_MAP, FIRST_MAP + MAP_COUNT)) - set(admitted)),
        selected_edges=selected_edges, directed_edges=directed,
        unselected_edge_ids=sorted(set(edges_by_id) - set(edge_ids)),
        allocation_verified=allocation is not None, candidate_data_plan_ready=bool(admitted) and compiled is not None and not blockers,
        streams=stream_rows, reused_tile32_ids=reused,
        new_tile32_definitions=[dict(tile32_id=i, quadrants=list(q)) for i, q in compiled.new_definitions] if compiled else [],
        tile32_assignment_verified=allocation is not None and allocation.tile32_assignments is not None,
        tile32_write_plan=tile32_writes,
        relocated_tables=tables, unpopulated_table_rows="zero; runtime admission gate required",
        native_parent_count=160, legacy_table_writes=[], profile_overrides=[],
        native_99=proof.get("native_99"),
        event_aliases=[dict(map_id=row["map_id"], legacy_address=row["legacy_address"],
                           overlaps=row["owner"]) for row in state["event_rows"]
                       if row["aliases_other_owner"]],
        event_policy=state["event_dispatch"],
        native_state_contract=state,
        consumption_blockers=blockers, qualification_blockers=qualification,
        runtime_build_ready=False, native_gameplay_verified=False, save_reopen_verified=False,
        production_endpoints_enabled=False)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project", type=Path, required=True)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--z3ed", type=Path, required=True)
    parser.add_argument("--allocation", type=Path)
    parser.add_argument("--state-symbols", type=Path)
    parser.add_argument("--state-ownership", type=Path)
    parser.add_argument("--candidate-map", action="append", type=lambda v: int(v, 0))
    args = parser.parse_args(argv)
    # Match Yaze's descriptor-relative resolution even when the descriptor is
    # reached through a symlink in a different authoring directory.
    paths = [Path(os.path.abspath(args.project)), args.rom.resolve(strict=True), args.z3ed.resolve(strict=True)]
    paths.append(resolve_project_terrain(paths[0]))
    if args.allocation:
        paths.append(args.allocation.resolve(strict=True))
    for extra in (args.state_symbols, args.state_ownership):
        if extra:
            paths.append(extra.resolve(strict=True))
    before = {path: sha(path.read_bytes()) for path in paths}
    try:
        allocation = json.loads(args.allocation.read_text()) if args.allocation else None
        proof = native_verify(paths[2], paths[0], paths[1])
        report = plan_admission(paths[1].read_bytes(), paths[3].read_bytes(), proof, allocation,
                                candidate_maps=args.candidate_map,
                                state_symbols=args.state_symbols.read_text() if args.state_symbols else None,
                                state_ownership=json.loads(args.state_ownership.read_text()) if args.state_ownership else None)
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
