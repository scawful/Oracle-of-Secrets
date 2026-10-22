"""Read-only event/save/return consumer contract for the 192-map proposal.

Byte bindings describe existing consumers, not a grant of SRAM or entrance
rows. In particular, a valid terrain plan never supplies a Lyra save policy.
All intervals in the report are half-open.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

# Use the ledger's canonical physical-space model: save_buffer is WRAM.
sys.path.append(str(Path(__file__).resolve().parents[1] / "Generate"))
from allocation_contracts import physical as allocation_physical


EVENT_BASE = 0x7EF280
SAVE_BUFFER = (0x7EF000, 0x7EF500)
ENTRANCE_COUNT = 129  # FindEntrance: LDX #$0102, then DEX twice before reading.
EXIT_COUNT = 79       # LoadOverworldFromUnderworld: LDX #$9E, predecrement twice.
ENTRANCE_SCREENS, ENTRANCE_TILES, ENTRANCE_IDS = 0x1BB96F, 0x1BBA71, 0x1BBB73
EXIT_ROOMS, EXIT_MAPS = 0x02DD8A, 0x02DE28
ENTRANCE_ROOM_VARIANTS = (
    ("vanilla", "ad0e0129ff000aaa0a0aa8bd13c885a08d8e04", 0x02C813, 133),
    ("zs_expanded", "ad0e0129ff000a2208f00fbd008085a08d8e04", 0x0F8000, 256),
)
ENTRANCE_ROOM_TRAMPOLINE = bytes.fromhex("aa0a0aa8e220a90f48abc2206b")
ENTRANCE_SCAN = bytes.fromhex("988500a20201a500caca3067df71ba1bd0f6ad0a04df6fb91bd0eb")
# Full entry-through-final-RTL identities, read from the reviewed saved editor
# inputs and R16 source build. This binds every branch before the scanner and
# the later LDA.l $1BBB73,X, not merely nearby recognizable instructions.
# A recompiled/relocated body needs a fresh source review before qualification.
ENTRANCE_BODY_BYTES = 0x186
ENTRANCE_BODY_SHA256 = {
    "inline_source": "060f6fd5457a26c4880337101a20c414370dfab08e9fd6cfed3c6d6499472e4b",
    "source_hook": "2e2a7dc111bdb925f273689ca97816437de9e74a809144b3f14069d1597401ce",
}

# Exact native instructions, independently read against usdasm labels and the
# retained R16 normal build. Changes refuse consumer verification, even if the
# changed operand still points inside a saved or apparently unused interval.
# id, native label, SNES address, expected bytes
BINDINGS = (
    ("save_copy", "SaveGameFile.write_save", 0x00895D,
     "bf00f07e99000099000fbf00f17e990001990010bf00f27e990002990011"
     "bf00f37e990003990012bf00f47e990004990013c8c8e8e8e00001d0c5"),
    ("save_checksum", "SaveGameFile.calc_checksum", 0x00899C,
     "187f00f07ee8e8e0fe04d0f485007aa95a5a38e5008ffef47ebb9ffe04709ffe1370"),
    ("load_copy", "CopySaveToWRAM.copy_next", 0x0CCFE1,
     "bf0000709900f0bf0001709900f1bf0002709900f2bf0003709900f3"
     "bf0004709900f4e8e8c8c8c00001d0d4"),
    ("new_file_clear", "FadeMusicAndResetSRAMMirror.next_sram", 0x0CC315,
     "9f00f07e9f00f17e9f00f27e9f00f37e9f00f47ee8e8e00001d0e5"),
    ("exit_dispatch", "LoadOverworldFromUnderworld", 0x02E4BD,
     "a5a0c90401f010c98001b00bc90001900620d4e54c8ae5a29ecacadd8addd0f9"),
    ("exit_map", "LoadOverworldFromUnderworld.custom_exit", 0x02E549,
     "bd28de858a8d0a04648b9c0b04"),
    ("entrance_cache_write", "Underworld_LoadEntrance.recache", 0x02D8C5,
     "c220ad0a048f40c17ea51c8f42c17e"),
    ("entrance_cache_read", "LoadCachedEntranceProperties", 0x02E5D6,
     "af40c17e8d0a04af42c17e"),
    ("entrance_cache_map", "LoadCachedEntranceProperties.face_down", 0x02E631,
     "af4cc17e858aaf4ec17e8584"),
    ("special_cache_write", "LoadSpecialOverworld", 0x02E859, "8f00c17e"),
    ("special_cache_read", "LoadOverworldFromSpecialOverworld", 0x02E9C1, "af00c17e"),
    ("event_bomb_read", "Overworld_HandleOverlaysAndBombDoors.no_overlay", 0x02EF56,
     "bf80f27e2902f01b"),
    ("event_overlay_write", "Overworld event overlay writer", 0x1BC0C6,
     "bf80f27e09209f80f27e"),
)

# The reviewed callers use byte-sized event writes. The helpers' ability to
# replay an M16 STA is not permission for a two-byte tail event (BF would reach
# the version marker). These are the complete fixed sites in tail_events.asm.
TAIL_LOAD_SITES = (
    0x02EF48, 0x02EF56, 0x0588DF, 0x0589A5, 0x05EF1E, 0x05EFFA,
    0x068D4C, 0x06BE6A, 0x06EFA8, 0x099A87, 0x09A6BC, 0x0DCCAD,
    0x1BC0C6, 0x1BC20F, 0x1BC902, 0x1BCBD8, 0x1BCD59, 0x1BCE4A,
    0x1BCFE2, 0x1EE4A6,
)
TAIL_STORE_SITES = (
    (0x0589AB, "0940"), (0x05F000, "0940"), (0x06BE70, "0920"),
    (0x06EFAE, "0940"), (0x099A8D, "0920"), (0x1BC0CC, "0920"),
    (0x1BC215, "0902"), (0x1BCBDE, "0920"), (0x1BCD5F, "0920"),
    (0x1BCE50, "0920"), (0x1BCFE8, "0920"),
)
TAIL_HELPERS = {
    "TailEvent_Load": "08c210e0a000900be0c000b00628bf20f47e6b28bf80f27e6b",
    "TailEvent_Store": "08c210e0a000900be0c000b006289f20f47e6b289f80f27e6b",
    "TailEvent_MigrateSave": "afe0f47ec9a1f013daa21fa9009fc0f47eca10f9faa9a18fe0f47e6b",
}
# Entry-through-last-event-call body identities from the reviewed 01c4ba1d
# build. Only the checked JSL operands are normalized; every intervening byte
# remains pinned. Labels come from this image's build symbols, never a scan
# for a convenient dead copy. Recompiling another caller body requires review.
TAIL_SOURCE_CALLERS = (
    ("Frame8", 49, "3e87c620baf2c4e626c188f818e7690e92c62ffd1ba646fe40d97255726a47fb", ((39, "load"), (45, "store"))),
    ("Castle_EndAnimation", 47, "1eaef0217aa6da85f65df18487971204d1ef495d9b220651e7ef98a1b802986f", ((37, "load"), (43, "store"))),
    ("TailPalace_Frame2", 86, "fcf70d1a8b75f98b1e466d6576ea73687a2b66b35337dcc2cc1286a250af7155", ((76, "load"), (82, "store"))),
    ("Goron_Frame4", 81, "9169f9278f9af6a3e8de81d0b053e58bcb62e26c4c3c00d08cb344baf844d199", ((71, "load"), (77, "store"))),
    ("Fortress_Frame4", 83, "42dd297de36bf7c2bf89040c0bdb5604250b5c5f3d05e521f80a45ae4f299008", ((73, "load"), (79, "store"))),
    ("Sprite_Octoboss_Long", 23, "8650e6f3451bc214c761cbd12be8fe3c7ca8fa839fe0b9352e5b25c293b377f0", ((19, "load"),)),
    ("EmergeWaitGiveItem", 58, "cc7d90a7bbf63ccac2b7967824cd5357c03e19081cda8a5669897218f6ea7061", ((48, "load"), (54, "store"))),
    ("Sprite_Goron_Prep", 51, "bf218ebe9c4efd065ee4571a762b19111da3c49dab2132665da297b9f7a08332", ((47, "load"),)),
)
TAIL_SOURCE_ENTRIES = {
    "Frame8": 0x348A58, "Castle_EndAnimation": 0x348ABC,
    "TailPalace_Frame2": 0x348D99, "Goron_Frame4": 0x348EB9,
    "Fortress_Frame4": 0x3490EA, "Sprite_Octoboss_Long": 0x3096AA,
    "EmergeWaitGiveItem": 0x309AED, "Sprite_Goron_Prep": 0x2CDE8D,
}
# Frame8 and the other checked overlay prefixes call this actual M8 restorer.
# Pin its entry/body as well as the callers; a relabeled matching dead copy is
# not the dependency reached by the checked JSR operands.
TAIL_M8_DEPENDENCY = ("ShakeScreen", 0x3484CB,
    "c220a51a2901000aaabf61c9018d1a01bf65c9018d1c01e22060")
TAIL_FLAGS, TAIL_VERSION, TAIL_MARKER = 0x7EF4C0, 0x7EF4E0, 0xA1


def _labels(text):
    _require(type(text) is str, "Build symbols are required for tail dispatch")
    result = {}
    required = set(TAIL_HELPERS) | {row[0] for row in TAIL_SOURCE_CALLERS} | {
        "LoadCheckpointOrWorld", "TailEventFlags", "TailEventVersion", TAIL_M8_DEPENDENCY[0]}
    # WLA also contains non-label address-to-line sections. Read labels only.
    section = None
    for line in text.splitlines():
        if line.startswith("["):
            section = line
        if section != "[labels]":
            continue
        match = re.fullmatch(r"([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?([A-Za-z][A-Za-z0-9_]*)", line)
        if match:
            name = match[3]
            if name not in required:
                continue
            _require(name not in result, f"Duplicate build symbol: {name}")
            result[name] = int(match[1] + match[2], 16)
    return result


def _rom_label(labels, name):
    address = labels.get(name)
    _require(type(address) is int and address & 0x8000
             and address >> 16 not in (0x7E, 0x7F), f"Missing/invalid ROM symbol: {name}")
    return address


def _bound(source, name, address, expected):
    observed = _read(source, address, len(expected))
    return dict(id=name, snes=address, bytes=len(expected), expected_hex=expected.hex(),
                observed_sha256=_sha(observed), verified=observed == expected)


def _tail_ownership(value, labels):
    _require(type(value) is dict and type(value.get("claims")) is list,
             "Named tail-state ownership ledger is required")
    claims = value["claims"]
    _require(all(type(row) is dict for row in claims), "Malformed ownership claim")
    chosen = []
    for name, base, size in (("TailEventFlags", TAIL_FLAGS, 32), ("TailEventVersion", TAIL_VERSION, 1)):
        matches = [row for row in claims if row.get("id") == name]
        _require(len(matches) == 1, f"Missing/duplicate ownership claim: {name}")
        row = matches[0]
        _require(row.get("base") == base and type(row.get("base")) is int
                 and row.get("size") == size and type(row.get("size")) is int
                 and row.get("space") == "save_buffer" and row.get("status") == "shared"
                 and row.get("condition") == {} and row.get("aliases") == []
                 and row.get("binding") == dict(source="shared:Core/sram.asm", symbol=name, bank00_mirror=False)
                 and labels.get(name) == base, f"Divergent ownership claim: {name}")
        if name == "TailEventFlags":
            _require(row.get("count") == 32 and row.get("stride") == 1, "Tail event claim layout differs")
        for other in claims:
            if other is row:
                continue
            lo, count = other.get("base"), other.get("size")
            if lo is None:
                # An explicitly unallocated proposal is not a physical owner.
                _require(other.get("status") in ("pending", "proposed"), "Ambiguous ownership address")
                continue
            _require(type(lo) is int and lo >= 0, "Malformed ownership address")
            if count is None:
                _require(lo >= base + size, f"Ambiguous ownership extent: {name}")
                continue
            _require(type(count) is int and count >= 0, "Malformed ownership extent")
            _require(type(other.get("space")) is str, "Ambiguous physical ownership space")
            space, start, end = allocation_physical(other)
            if start < base + size and base < end:
                _require(False, f"{'Overlapping' if space == 'wram' else 'Ambiguous physical'} ownership claim: {name}")
        chosen.append(dict(id=name, base=base, size=size, status="shared"))
    return dict(verified=True, claims=chosen,
                ledger_sha256=_sha(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()),
                grants_other_storage=False)


def _event_contract(source, symbols, ownership):
    fixed = [(address, "load") for address in TAIL_LOAD_SITES]
    fixed += [(address, "store") for address, _ in TAIL_STORE_SITES]
    legacy = all(_read(source, address, 4) == bytes([0xBF if kind == "load" else 0x9F, 0x80, 0xF2, 0x7E])
                 for address, kind in fixed)
    result = dict(variant="legacy_direct" if legacy else "tail_dispatch_v1", verified=False,
                  bindings=[], failures=[], ownership=None, migration=None, targets={},
                  writer_width_bits=8, multi_byte_tail_store_supported=False)
    try:
        if legacy:
            if symbols is not None:
                labels = _labels(symbols)
                _require(not any(name in labels for name in TAIL_HELPERS), "Mixed/dead tail implementation")
            result["verified"] = True
            return result
        labels = _labels(symbols)
        result["symbols_sha256"] = _sha(symbols.encode())
        targets = {kind: _rom_label(labels, name) for kind, name in
                   (("load", "TailEvent_Load"), ("store", "TailEvent_Store"), ("migrate", "TailEvent_MigrateSave"))}
        result["targets"] = targets
        rows = result["bindings"]
        for kind, name in (("load", "TailEvent_Load"), ("store", "TailEvent_Store"), ("migrate", "TailEvent_MigrateSave")):
            rows.append(_bound(source, name, targets[kind], bytes.fromhex(TAIL_HELPERS[name])))
        for address, kind in fixed:
            rows.append(_bound(source, f"tail_{kind}_{address:06X}", address,
                               b"\x22" + targets[kind].to_bytes(3, "little")))
        for address, prefix in TAIL_STORE_SITES:
            rows.append(_bound(source, f"tail_store_m8_{address:06X}", address - 2, bytes.fromhex(prefix)))
        dependency_name, dependency_entry, dependency_hex = TAIL_M8_DEPENDENCY
        _require(_rom_label(labels, dependency_name) == dependency_entry,
                 "Unreviewed M8 dependency entry")
        rows.append(_bound(source, "tail_m8_ShakeScreen", dependency_entry, bytes.fromhex(dependency_hex)))
        for name, size, expected_hash, calls in TAIL_SOURCE_CALLERS:
            address = _rom_label(labels, name)
            _require(address == TAIL_SOURCE_ENTRIES[name], f"Unreviewed source caller entry: {name}")
            body = bytearray(_read(source, address, size))
            calls_verified = True
            for offset, kind in calls:
                calls_verified &= body[offset:offset + 4] == b"\x22" + targets[kind].to_bytes(3, "little")
                body[offset + 1:offset + 4] = bytes(3)
            rows.append(dict(id=f"tail_source_{name}", snes=address, bytes=size,
                             body_sha256=_sha(body), expected_body_sha256=expected_hash,
                             verified=bool(calls_verified) and _sha(body) == expected_hash,
                             calls=[dict(snes=address + offset, kind=kind) for offset, kind in calls]))
        entry = _rom_label(labels, "LoadCheckpointOrWorld")
        rows.append(_bound(source, "tail_migration_active_hook", 0x028192, b"\x5c" + entry.to_bytes(3, "little")))
        rows.append(_bound(source, "tail_migration_first_call", entry, b"\x22" + targets["migrate"].to_bytes(3, "little")))
        result["ownership"] = _tail_ownership(ownership, labels)
        result["failures"] = [row["id"] for row in rows if not row["verified"]]
        result["verified"] = not result["failures"]
        if result["verified"]:
            result["migration"] = dict(version_address=TAIL_VERSION, current_version=TAIL_MARKER,
                flags=[TAIL_FLAGS, TAIL_FLAGS + 32], clear_if_version_differs=True,
                stamped_save_preserved=True, active_load_entry=entry)
    except (ValueError, TypeError, KeyError) as error:
        result["failures"] = [row["id"] for row in result["bindings"] if not row["verified"]]
        result["failures"].append(str(error))
    return result


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _pc(address):
    return ((address & 0x7F0000) >> 1) | (address & 0x7FFF)


def _read(source, address, count):
    at = _pc(address)
    result = source[at:at + count]
    _require(len(result) == count, "Truncated native state consumer")
    return result


def _entrance_scanner(source):
    """Follow the active source hook; old builds can leave identical dead code."""
    hook = _read(source, 0x1BBBF4, 5)
    result = dict(id="entrance_scan", label="Oracle_FindEntrance", hook_snes=0x1BBBF4,
                  hook_hex=hook.hex(), verified=False)
    if hook == b"\xc2\x31\xa5\x20\x18":
        # Saved editor inputs retain the inline consumer; normal source builds
        # replace it with the source hook below. Bind both forms explicitly.
        entry_address = 0x1BBBF4
        result.update(variant="inline_source")
    else:
        if hook[0] != 0x22 or hook[4] != 0x6B:
            return result
        wrapper_address = int.from_bytes(hook[1:4], "little")
        if not wrapper_address & 0x8000 or wrapper_address >> 16 in (0x7E, 0x7F):
            return result
        wrapper = _read(source, wrapper_address, 9)
        if wrapper[:4] != b"\x8b\x4b\xab\x22" or wrapper[7:] != b"\xab\x6b":
            return result
        entry_address = int.from_bytes(wrapper[4:7], "little")
        if entry_address >> 16 != wrapper_address >> 16 or not entry_address & 0x8000:
            return result
        result.update(variant="source_hook", wrapper_snes=wrapper_address)
    entry_pc = _pc(entry_address)
    body = _read(source, entry_address, ENTRANCE_BODY_BYTES)
    observed = _sha(body)
    expected = ENTRANCE_BODY_SHA256[result["variant"]]
    result.update(entry_snes=entry_address,
                  scanner_pc=entry_pc + 0x110, id_reader_pc=entry_pc + 0x16B,
                  body_bytes=ENTRANCE_BODY_BYTES, body_sha256=observed,
                  expected_body_sha256=expected, verified=observed == expected)
    return result


def legacy_event_row(area):
    """Preserve the legacy address even where it aliases another owner."""
    _require(type(area) is int and 0 <= area < 192, "Invalid native state map ID")
    owner = ("overworld_events" if area < 0x80 else
             "story_extension" if area < 0x90 else "item_extension")
    return dict(map_id=area, legacy_address=EVENT_BASE + area, owner=owner,
                aliases_other_owner=area >= 0x80,
                compatibility="legacy_unchanged" if area < 0xA0 else "unsupported_tail_state")


def room_return(source, room, map_id, exit_row):
    """Describe the actual dispatch; never allocate an unmatched/blank row."""
    _require(type(room) is int and 0 <= room <= 0xFFFF, "Invalid return room ID")
    legacy_event_row(map_id)
    _require(exit_row is None or type(exit_row) is int and 0 <= exit_row < EXIT_COUNT,
             "Invalid return exit row")
    cached = 0x100 <= room < 0x180 and room != 0x104
    matches = []
    for row in range(EXIT_COUNT):
        value = int.from_bytes(_read(source, EXIT_ROOMS + row * 2, 2), "little")
        if value == room:
            matches.append(dict(row=row, map_id=_read(source, EXIT_MAPS + row, 1)[0]))
    # The native scan descends. Multiple room matches do not grant a choice:
    # the highest row always wins, regardless of a proposed exit_row value.
    consumed = matches[-1] if matches and not cached else None
    return dict(room_id=room, requested_map_id=map_id, requested_exit_row=exit_row,
                path="cached_entrance" if cached else "custom_exit_table",
                matching_rows=matches, consumed_row=consumed,
                requested_row_consumed=(not cached and exit_row is not None
                    and consumed == dict(row=exit_row, map_id=map_id)),
                allocation_granted=False, save_reopen_supported=False)


def _plan_native_state(source, map_ids, *, authoring=(), symbols=None, ownership=None):
    """Bind existing consumers and expose the unchosen tail-state interfaces.

    `map_ids` includes selected traversal endpoints, never render-only maps.
    `authoring` contains only those traversal maps' parsed metadata. Missing
    byte identities fail closed in the returned runtime blockers; they do not
    prevent a separate terrain-only plan from being inspected.
    """
    _require(type(map_ids) in (list, tuple)
             and all(type(area) is int and 0 <= area < 192 for area in map_ids)
             and len(map_ids) == len(set(map_ids)),
             "Invalid native state map selection")
    events = [legacy_event_row(area) for area in sorted(map_ids)]
    dispatch = _event_contract(source, symbols, ownership)
    tail_implemented = dispatch["verified"] and dispatch["variant"] == "tail_dispatch_v1"
    for row in events:
        is_tail = row["map_id"] >= 0xA0
        row["effective_event_address"] = (TAIL_FLAGS + row["map_id"] - 0xA0
            if is_tail and tail_implemented else None if is_tail else row["legacy_address"])
        row["effective_owner"] = "TailEventFlags" if is_tail and tail_implemented else row["owner"]
        if is_tail and tail_implemented:
            row["compatibility"] = "tail_dispatch_v1"
    bindings = []
    for name, label, address, expected_hex in BINDINGS:
        expected = bytes.fromhex(expected_hex)
        if dispatch["variant"] == "tail_dispatch_v1" and dispatch["targets"]:
            load = b"\x22" + dispatch["targets"]["load"].to_bytes(3, "little")
            store = b"\x22" + dispatch["targets"]["store"].to_bytes(3, "little")
            if name == "event_bomb_read":
                expected = load + bytes.fromhex("2902f01b")
            elif name == "event_overlay_write":
                expected = load + bytes.fromhex("0920") + store
        observed = _read(source, address, len(expected))
        bindings.append(dict(id=name, label=label, snes=address, bytes=len(expected),
                             expected_hex=expected_hex, observed_sha256=_sha(observed),
                             verified=observed == expected))
    bindings.append(_entrance_scanner(source))
    decoder = _read(source, 0x02D998, 19)
    room_decoder = None
    for name, expected, address, count in ENTRANCE_ROOM_VARIANTS:
        if decoder.hex() == expected and (name != "zs_expanded" or
                _read(source, 0x0FF008, len(ENTRANCE_ROOM_TRAMPOLINE)) == ENTRANCE_ROOM_TRAMPOLINE):
            room_decoder = dict(variant=name, table_snes=address, index_capacity=count,
                                allocation_granted=False)
    bindings.append(dict(id="entrance_room_decoder", label="Underworld_LoadEntrance.not_a_respawn",
        snes=0x02D998, observed_sha256=_sha(decoder), verified=room_decoder is not None))
    failures = [entry["id"] for entry in bindings if not entry["verified"]]
    if not dispatch["verified"]:
        failures.append("tail_event_dispatch")
    tables = [dict(id=name, snes=address, rows=count, stride=stride,
                   sha256=_sha(_read(source, address, count * stride)))
              for name, address, count, stride in (
                  ("entrance_screens", ENTRANCE_SCREENS, ENTRANCE_COUNT, 2),
                  ("entrance_tiles", ENTRANCE_TILES, ENTRANCE_COUNT, 2),
                  ("entrance_ids", ENTRANCE_IDS, ENTRANCE_COUNT, 1),
                  ("exit_rooms", EXIT_ROOMS, EXIT_COUNT, 2),
                  ("exit_maps", EXIT_MAPS, EXIT_COUNT, 1))]
    if room_decoder:
        tables.append(dict(id="entrance_rooms", snes=room_decoder["table_snes"],
            rows=room_decoder["index_capacity"], stride=2,
            sha256=_sha(_read(source, room_decoder["table_snes"], room_decoder["index_capacity"] * 2))))
    returns, doors = [], []
    seen = set()
    for area, metadata in authoring:
        _require(type(area) is int and area in map_ids and area not in seen,
                 "Authoring must name selected traversal maps once")
        seen.add(area)
        for entry in metadata["exits"]:
            result = room_return(source, entry["room_id"], area, entry["exit_row"])
            returns.append(dict(map_id=area, placement_id=entry["id"], **result))
        for entry in metadata["doors"]:
            matches, other_maps = [], []
            for row in range(ENTRANCE_COUNT):
                screen = int.from_bytes(_read(source, ENTRANCE_SCREENS + row * 2, 2), "little")
                entrance = _read(source, ENTRANCE_IDS + row, 1)[0]
                if entrance == entry["entrance_id"]:
                    record = dict(row=row, map_id=screen, tile_index=int.from_bytes(
                        _read(source, ENTRANCE_TILES + row * 2, 2), "little"))
                    (matches if screen == area else other_maps).append(record)
            entrance = entry["entrance_id"]
            room = (int.from_bytes(_read(source, room_decoder["table_snes"] + entrance * 2, 2), "little")
                    if room_decoder and entrance is not None
                    and 0 <= entrance < room_decoder["index_capacity"] else None)
            doors.append(dict(map_id=area, placement_id=entry["id"],
                entrance_id=entrance, resolved_room_id=room, matching_rows=matches,
                same_entrance_other_maps=other_maps,
                tile_match_verified=False, allocation_granted=False))
    tail = [row["map_id"] for row in events if row["map_id"] >= 0xA0]
    blockers = ([dict(code="NATIVE_STATE_CONSUMER_MISMATCH", consumers=failures)] if failures else [])
    if tail:
        if not tail_implemented:
            blockers += [dict(code=code, map_ids=tail) for code in (
                "PERSISTENT_EVENT_STORAGE_UNALLOCATED", "EVENT_INITIALIZATION_MIGRATION_UNCHOSEN",
                "NATIVE_EVENT_DISPATCH_UNINTEGRATED")]
        blockers += [dict(code=code, map_ids=tail) for code in (
            "SAVE_DEATH_CONTINUE_POLICY_UNCHOSEN", "ENTRY_RETURN_BINDING_UNQUALIFIED")]
    return dict(kind="lyra.native_state_consumers.v1", source_rom_sha256=_sha(source),
        source_rom_bytes=len(source), image_scope="native_state_contract",
        consumers_verified=not failures, consumers=bindings, tables=tables,
        entrance_room_decoder=room_decoder,
        event_rows=events, event_implementation=dispatch,
        persistent_event_storage=(dict(base=TAIL_FLAGS, bytes=32, first_map=0xA0, end_map=0xC0,
            ownership=dispatch["ownership"], writer_width_bits=8) if tail_implemented else None),
        event_initialization_migration=dispatch["migration"] if tail_implemented else None,
        event_dispatch=("legacy 00..9F unchanged; A0..BF use byte-sized TailEventFlags with versioned initialization"
                        if tail_implemented else "legacy indexing; tail persistence is unqualified"),
        save=dict(buffer=list(SAVE_BUFFER), primary_bank=0x70, copy_bytes=0x500,
                  backup_delta=0xF00, checksum_words=0x27F, checksum_target=0x5A5A,
                  checksum_address=0x7EF4FE, saved_world_address=0x7EF3CA,
                  saved_world_mask=0x40, lyra_resume_policy=None),
        caches=[dict(kind="entrance", interval=[0x7EC140, 0x7EC172], persisted=False),
                dict(kind="special_return", interval=[0x7EC100, 0x7EC130], persisted=False)],
        requested_doors=doors, requested_returns=returns,
        runtime_blockers=blockers, allocation_granted=False, runtime_ready=False,
        native_acceptance_scenario="LYRA_STATE_SAVE_RETURN_01")


def plan_native_state(source, map_ids, *, authoring=(), symbols=None, ownership=None):
    """Plan only a supported full input shape; never expand or pad a ROM."""
    _require(type(source) in (bytes, bytearray) and len(source) in (0x200000, 0x400000),
             "Expected an unheadered2MiB or4MiB native ROM")
    return _plan_native_state(source, map_ids, authoring=authoring, symbols=symbols, ownership=ownership)


def inspect_compiled_dispatch(source, map_ids, *, symbols, ownership, authoring=()):
    """Read a normal ASM output independently of terrain/composition admission.

    The exact original bytes/hash remain in the receipt. This diagnostic does
    not turn a short ASM output into a qualified 4MiB composed image.
    """
    _require(type(source) in (bytes, bytearray) and 0 < len(source) <= 0x400000,
             "Expected a headerless compiled ROM no larger than4MiB")
    result = _plan_native_state(source, map_ids, authoring=authoring, symbols=symbols, ownership=ownership)
    result["image_scope"] = "compiled_dispatch_inspection_only"
    result["runtime_blockers"].append(dict(code="COMPOSED_IMAGE_IDENTITY_UNQUALIFIED"))
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", type=Path, required=True)
    parser.add_argument("--map", dest="maps", action="append", type=lambda value: int(value, 0), default=[])
    parser.add_argument("--symbols", type=Path)
    parser.add_argument("--ownership", type=Path)
    parser.add_argument("--inspect-compiled-dispatch", action="store_true")
    args = parser.parse_args(argv)
    paths = [p.resolve(strict=True) for p in (args.rom, args.symbols, args.ownership) if p is not None]
    before = {path: _sha(path.read_bytes()) for path in paths}
    try:
        source = args.rom.read_bytes()
        kwargs = dict(symbols=args.symbols.read_text() if args.symbols else None,
                      ownership=json.loads(args.ownership.read_text()) if args.ownership else None)
        fn = inspect_compiled_dispatch if args.inspect_compiled_dispatch else plan_native_state
        result = fn(source, args.maps, **kwargs)
        result["inputs"] = [dict(path=str(path), sha256=digest) for path, digest in before.items()]
    finally:
        _require(all(_sha(path.read_bytes()) == digest for path, digest in before.items()),
                 "Read-only state inspection changed an input")
    print(json.dumps(result, sort_keys=True, indent=2))
    return 0 if result["consumers_verified"] else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (ValueError, OSError) as error:
        print(f"Native state inspection refused: {error}", file=sys.stderr)
        sys.exit(1)
