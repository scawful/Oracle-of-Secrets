#!/usr/bin/env python3
"""Deterministic, idempotent installer for the Wind Tribe Clouds Sky Kit.

Installs the Yaze-paintable Wind Tribe Sky Kit non-destructively into an
editable revision-5 OOSOW192 base ROM with ZERO existing Sky map Tile16 layout
edits, ZERO dict 413 (page_tile16) mutations, and ZERO writes into Bank $47
(which remains owned by sheet_overrides.py):

  1. Palettes (100% native in both SNES hardware and current Yaze Nightly/z3ed):
       - Main $07 (exclusive to $87/$94): patches Row 6 LO idx 2-3 @ $22F480
       - Aux1 $1C ($22FA50, Bank $45): clones Aux1 $19; fixes $87 corner clouds
       - Aux2 $1D ($22FA7A, Bank $45): clones Aux $06; Ramp B in 0-use Row 5 HI ($84-$86)
       - Aux2 $1E ($22FAA4, Bank $45): clones Aux2 $18; Ramp B in 0-use Row 6 HI ($8C-$8F)
       - Aux2 $1F ($22FACE, Bank $45): clones Aux2 $1A; unused Row 7 HI idx 6 -> gold ($87)
       - Anim $09 ($0DE682, unused vanilla slot): $8C-$8F Row 7 LO (preserves idx 1-2)
       - Anim $0A ($0DE690, unused vanilla slot): $84-$87,$94 Row 7 LO (preserves idx 1-2)
  2. PC_PAL_GROUP ($075504) entries for pset $0D, $0E, $0F, $15
     (leaves shared pset $07 untouched).
  3. Sky map headers ONLY ($84-$87, $8C-$8F, $94) in both rev5 native tables
     and legacy ZSCustomOverworld mirrors (map_id < 160). Zero layout edits.
  4. 104 modular Wind Tribe Tile16 definitions (65 base tiles + 39 pre-bound
     $8C-$8F [Row 6 HI] and $87 [Slot 5 $EF Row 7 HI] variants) packed into
     existing Sky Overworld sheets ($EB/$ED/$EF/$F0/$F1 — zero Glacia $FD/$FE
     conflicts!) and verified free global Tile16 slots ($CE6-$CEB, $D28-$D3C,
     $D3F, $DA7-$DBD, $EA8-$EB0, $EBD-$ED9, $EDD-$EEB; never touches Q326
     graves $EB1-$EB8 or Goron lava $EB9-$EBC).
  5. Re-encodes OOSOW192 directory CRCs at $147000 and verifies Bank $47 == 0.

Usage:
  python3 Scripts/Generate/install_wind_tribe_kit.py --rom <target_base_rom>
  python3 Scripts/Generate/install_wind_tribe_kit.py --rom <target_base_rom> --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import struct
import sys
import tempfile
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CATALOG = ROOT / "Data" / "graphics" / "sky_overworld" / "wind_tribe_tile16_catalog.json"

sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
import check_tile16_pins as ctp  # noqa: E402
import lyra_native_loaders as lnl  # noqa: E402

PC_PAL_GROUP = 0x075504
PC_LEGACY_MAIN_PAL = 0x140160
PC_LEGACY_PAL_SET = 0x04C635
PC_LEGACY_GFX = 0x140480
BANK47_PC_START = 0x238000
BANK47_PC_END = 0x240000
FORBIDDEN_TILE16_IDS = set(range(0x0EB1, 0x0EBD))  # Q326 graves ($EB1-$EB8) + Goron lava ($EB9-$EBC)


def _hex(val: str | int) -> int:
    return int(val, 0) if isinstance(val, str) else int(val)


def _compute_expected_palettes(rom: bytes, catalog: dict[str, Any]) -> list[tuple[str, int, bytes]]:
    writes: list[tuple[str, int, bytes]] = []
    pal_dict = catalog.get("palettes") or catalog.get("bank45_palettes", {})
    for name, spec in pal_dict.items():
        pc = _hex(spec["pc"])
        nwords = int(spec["words"])
        if "values" in spec:
            words = [_hex(v) for v in spec["values"]]
            if len(words) != nwords:
                raise ValueError(f"Palette {name}: expected {nwords} words, got {len(words)}")
        else:
            src_pc = _hex(spec["clone_from_pc"])
            words = list(struct.unpack_from(f"<{nwords}H", rom, src_pc))
            if "patch_slice" in spec:
                sl = spec["patch_slice"]
                start = int(sl["start"])
                vals = [_hex(v) for v in sl["values"]]
                words[start : start + len(vals)] = vals
            for k, v in spec.get("patch_words", {}).items():
                words[int(k)] = _hex(v)
        for w in words:
            if not (0 <= w <= 0x7FFF):
                raise ValueError(f"Palette {name}: invalid BGR555 word 0x{w:04X}")
        writes.append((f"palette:{name}", pc, struct.pack(f"<{nwords}H", *words)))
    return writes


def _compute_expected_pal_groups(catalog: dict[str, Any]) -> list[tuple[str, int, bytes]]:
    writes: list[tuple[str, int, bytes]] = []
    for pset_s, spec in catalog["palette_sets"].items():
        pset = _hex(pset_s)
        if pset == 0x07:
            raise ValueError("Refusing to modify shared palette_set $07")
        data = bytes([_hex(spec["aux1"]), _hex(spec["aux2"]), _hex(spec["anim"]), 0xFF])
        writes.append((f"pal_group:0x{pset:02X}", PC_PAL_GROUP + pset * 4, data))
    return writes


def _check_unreferenced_free_slots(rom: bytes, tile_ids_to_write: set[int]) -> None:
    if not tile_ids_to_write:
        return
    overlap = tile_ids_to_write & FORBIDDEN_TILE16_IDS
    if overlap:
        raise ValueError(f"Refusing to write forbidden Tile16 IDs: {[hex(x) for x in sorted(overlap)]}")
    capacity, native_tables = ctp._native_table_addresses(rom)
    map32 = ctp.decode_map32_table(rom)
    static_used: set[int] = set()
    for m in range(capacity):
        for row in ctp.decode_map16_grid(rom, m, map32, native_tables):
            static_used.update(row)
    used_conflicts = tile_ids_to_write & static_used
    if used_conflicts:
        raise ValueError(
            "Target Tile16 IDs are already referenced by live map grids: "
            + ", ".join(f"0x{t:03X}" for t in sorted(used_conflicts))
        )
    pins_path = ROOT / "Data" / "tile16_pins.json"
    if pins_path.is_file():
        pins_data = json.loads(pins_path.read_text(encoding="utf-8"))
        pinned = {_hex(k) for k in pins_data.get("pins", {})}
        pin_conflicts = tile_ids_to_write & pinned
        if pin_conflicts:
            raise ValueError(
                "Target Tile16 IDs conflict with Data/tile16_pins.json: "
                + ", ".join(f"0x{t:03X}" for t in sorted(pin_conflicts))
            )


def _apply_or_check(rom_bytes: bytes, catalog: dict[str, Any], *, check_only: bool) -> tuple[bytes, list[str]]:
    if len(rom_bytes) < 0x200000 or len(rom_bytes) % 0x8000 != 0:
        raise ValueError(f"Expected unheadered LoROM image >= 2 MiB; got {len(rom_bytes)} bytes")
    if any(rom_bytes[BANK47_PC_START:BANK47_PC_END]):
        raise ValueError(
            "Bank $47 (PC 0x238000..0x240000) is non-zero in target base ROM; "
            "refusing to run on a compiled/patched image instead of an editable base ROM"
        )

    # Validate existing rev5 OOSOW192 directory first
    raw_dir = rom_bytes[lnl.DIRECTORY_PC : lnl.DIRECTORY_PC + lnl.DIRECTORY_SIZE]
    if not raw_dir.startswith(lnl.MAGIC):
        raise ValueError("Target ROM does not have an OOSOW192 native directory at PC 0x147000")
    revision = struct.unpack_from("<H", raw_dir, 8)[0]
    if revision != 5:
        raise ValueError(f"Expected OOSOW192 revision 5 base ROM, found revision {revision}")

    capacity, tail_actor_bank, entries_map = lnl.read_native_directory(
        rom_bytes, experimental_page_tile16=True
    )
    for req_id in (2, 6, 31, 400, 413):
        if req_id not in entries_map:
            raise ValueError(f"Missing required native directory entry {req_id}")

    pc_main_pal = lnl.pc(entries_map[2][0])
    pc_gfx = lnl.pc(entries_map[6][0])
    pc_pal_set = lnl.pc(entries_map[31][0])
    pc_dict400 = lnl.pc(entries_map[400][0])
    dict400_count = entries_map[400][1]
    pc_dict413 = lnl.pc(entries_map[413][0])
    dict413_cap = entries_map[413][1]

    if dict400_count != 4096:
        raise ValueError(f"Unexpected dict 400 Tile16 count: {dict400_count}")

    mismatches: list[str] = []
    out = bytearray(rom_bytes)

    def apply_patch(label: str, offset: int, expected: bytes) -> None:
        actual = bytes(out[offset : offset + len(expected)])
        if actual != expected:
            if check_only:
                mismatches.append(f"{label} @ PC 0x{offset:06X}: got {actual.hex()} expected {expected.hex()}")
            else:
                out[offset : offset + len(expected)] = expected

    # 1. Palettes (Bank $45 Aux/Main + vanilla unused Anim $09/$0A)
    for label, pc, data in _compute_expected_palettes(rom_bytes, catalog):
        apply_patch(label, pc, data)

    # 2. Palette group table ($075504)
    for label, pc, data in _compute_expected_pal_groups(catalog):
        apply_patch(label, pc, data)

    # 3. Sky map headers (native + legacy mirrors for map_id < 160; ZERO map layout edits)
    for map_s, spec in catalog["map_bindings"].items():
        m = _hex(map_s)
        if not (0 <= m < capacity):
            raise ValueError(f"Map ID 0x{m:02X} out of capacity {capacity}")
        if "main_palette" in spec:
            mp = bytes([_hex(spec["main_palette"])])
            apply_patch(f"native:main_pal[0x{m:02X}]", pc_main_pal + m, mp)
            if m < 160:
                apply_patch(f"legacy:main_pal[0x{m:02X}]", PC_LEGACY_MAIN_PAL + m, mp)
        if "palette_set" in spec:
            ps = bytes([_hex(spec["palette_set"])])
            apply_patch(f"native:pal_set[0x{m:02X}]", pc_pal_set + m, ps)
            if m < 160:
                apply_patch(f"legacy:pal_set[0x{m:02X}]", PC_LEGACY_PAL_SET + m, ps)
        for slot_s, sheet_s in spec.get("gfx_slots", {}).items():
            slot = int(slot_s)
            if not (0 <= slot < 8):
                raise ValueError(f"Invalid GFX slot {slot}")
            sb = bytes([_hex(sheet_s)])
            apply_patch(f"native:gfx[0x{m:02X}][{slot}]", pc_gfx + m * 8 + slot, sb)
            if m < 160:
                apply_patch(f"legacy:gfx[0x{m:02X}][{slot}]", PC_LEGACY_GFX + m * 8 + slot, sb)

    # 4. 65 Modular Wind Tribe Tile16s in dict 400
    changed_tile16_ids: set[int] = set()
    tile16_patches: list[tuple[int, str, bytes]] = []
    for tile in catalog["tiles"]:
        tid = _hex(tile["id"])
        if tid in FORBIDDEN_TILE16_IDS or not (0 <= tid < 4096):
            raise ValueError(f"Forbidden or out-of-range Tile16 ID 0x{tid:03X}")
        words = [_hex(w) for w in tile["global_words"]]
        if len(words) != 4:
            raise ValueError(f"Tile16 0x{tid:03X} ({tile['name']}): expected 4 words")
        packed = struct.pack("<4H", *words)
        tile16_patches.append((tid, tile["name"], packed))
        if bytes(out[pc_dict400 + tid * 8 : pc_dict400 + tid * 8 + 8]) != packed:
            changed_tile16_ids.add(tid)

    if not check_only and changed_tile16_ids:
        _check_unreferenced_free_slots(rom_bytes, changed_tile16_ids)

    for tid, name, packed in tile16_patches:
        apply_patch(f"tile16:0x{tid:03X}({name})", pc_dict400 + tid * 8, packed)

    # 5. Optional sorted rev5 page_tile16 (dict 413) overrides (if any in catalog)
    raw_413 = bytes(out[pc_dict413 : pc_dict413 + dict413_cap * 12])
    existing_413 = lnl.decode_page_tile16(raw_413, capacity)
    merged_413 = dict(existing_413)
    has_kit_overrides = False
    for tile in catalog["tiles"]:
        tid = _hex(tile["id"])
        for map_s, words_s in tile.get("page_overrides", {}).items():
            has_kit_overrides = True
            m = _hex(map_s)
            words = tuple(_hex(w) for w in words_s)
            if len(words) != 4:
                raise ValueError(f"page_tile16 (0x{m:02X}, 0x{tid:03X}): expected 4 words")
            key = (m, tid)
            if check_only:
                if existing_413.get(key) != words:
                    mismatches.append(
                        f"page_tile16(0x{m:02X},0x{tid:03X}): got {existing_413.get(key)} expected {words}"
                    )
            else:
                merged_413[key] = words

    if not check_only:
        if has_kit_overrides:
            if len(merged_413) > dict413_cap:
                raise ValueError(f"dict 413 capacity exceeded: {len(merged_413)} > {dict413_cap}")
            buf413 = bytearray()
            for (m, tid), words in sorted(merged_413.items()):
                buf413.extend(struct.pack("<6H", m, tid, *words))
            buf413.extend(b"\xFF" * ((dict413_cap - len(merged_413)) * 12))
            out[pc_dict413 : pc_dict413 + dict413_cap * 12] = buf413

        # 6. Re-encode OOSOW192 directory CRCs
        dir_entries = [(eid, addr, rows) for eid, (addr, rows) in entries_map.items()]
        new_dir = lnl._encode_native_directory(
            bytes(out),
            dir_entries,
            tail_actor_bank=tail_actor_bank,
            capacity=capacity,
            revision=revision,
        )
        out[lnl.DIRECTORY_PC : lnl.DIRECTORY_PC + lnl.DIRECTORY_SIZE] = new_dir

        # Self-verify Bank $47 untouched and directory CRC valid
        if any(out[BANK47_PC_START:BANK47_PC_END]):
            raise RuntimeError("Internal error: Bank $47 was unexpectedly modified")
        lnl.read_native_directory(bytes(out), experimental_page_tile16=True)

    return bytes(out), mismatches


def _atomic_write(path: Path, data: bytes) -> None:
    path = path.resolve()
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix=f".{path.name}.", delete=False) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(data)
        tmp.flush()
        os.fsync(tmp.fileno())
    try:
        os.replace(tmp_path, path)
    except BaseException:
        tmp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument(
        "--rom",
        required=True,
        type=Path,
        help="Path to target editable rev5 OOSOW192 base ROM (required; no default).",
    )
    ap.add_argument(
        "--catalog",
        type=Path,
        default=DEFAULT_CATALOG,
        help=f"Path to Wind Tribe Tile16 catalog JSON (default: {DEFAULT_CATALOG.relative_to(ROOT)}).",
    )
    ap.add_argument(
        "--check",
        action="store_true",
        help="Verify whether the Wind Tribe Sky Kit is cleanly installed without modifying the ROM.",
    )
    args = ap.parse_args(argv)

    if not args.rom.is_file():
        print(f"ERROR: Target ROM not found: {args.rom}", file=sys.stderr)
        return 1
    if not args.catalog.is_file():
        print(f"ERROR: Catalog JSON not found: {args.catalog}", file=sys.stderr)
        return 1

    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    before = args.rom.read_bytes()
    before_sha = hashlib.sha256(before).hexdigest()

    try:
        after, mismatches = _apply_or_check(before, catalog, check_only=args.check)
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 1

    if args.check:
        if mismatches:
            print(f"[!] Wind Tribe Sky Kit NOT cleanly installed ({len(mismatches)} mismatches):", file=sys.stderr)
            for msg in mismatches[:25]:
                print(f"    - {msg}", file=sys.stderr)
            if len(mismatches) > 25:
                print(f"    ... and {len(mismatches) - 25} more", file=sys.stderr)
            return 1
        print(
            f"[+] Wind Tribe Sky Kit verified cleanly on {args.rom} "
            f"(sha256={before_sha[:16]}..., {catalog['tile16_count']} Tile16s, "
            f"{len(catalog['map_bindings'])} Sky maps, Bank $47 untouched)."
        )
        return 0

    after_sha = hashlib.sha256(after).hexdigest()
    if after == before:
        print(
            f"[=] Wind Tribe Sky Kit already installed (idempotent no-op, sha256={after_sha[:16]}...)."
        )
        return 0

    _atomic_write(args.rom, after)
    # Re-read and verify --check post-write
    _, post_mismatches = _apply_or_check(args.rom.read_bytes(), catalog, check_only=True)
    if post_mismatches:
        print(f"ERROR: Post-write verification failed ({len(post_mismatches)} mismatches)", file=sys.stderr)
        return 1
    print(
        f"[+] Installed Wind Tribe Sky Kit onto {args.rom}\n"
        f"    before sha256 : {before_sha}\n"
        f"    after  sha256 : {after_sha}\n"
        f"    Tile16 ranges : {', '.join(catalog['tile16_ranges'])} ({catalog['tile16_count']} tiles)\n"
        f"    Sky maps bound: {', '.join(catalog['map_bindings'].keys())} (ZERO layout edits)\n"
        f"    Bank $47      : verified all-zero (owned by sheet_overrides.py)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
