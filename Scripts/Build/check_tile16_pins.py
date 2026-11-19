#!/usr/bin/env python3
"""Unified engine-referenced Tile16 pin checker, 192-map free-range allocator,
and overworld exit-door overlay auditor (Q328 Track A1 + Q329).

Pins ALL engine-referenced Tile16 IDs across five categories:
  1. overlay_stream        : ROM overlay streams at $077677 (ov00-ov9F)
  2. asm_draw_persist      : all active ASM callers of Overworld_DrawMap16_Persist /
                             Overworld_DrawMap16_Anywhere and OverworldDoorStyles
  3. bank1b_interactive    : Bank $1B lift/cut/dash/bomb/powder/hammer match & reveal IDs
  4. bank02_map32_update   : Bank $02 $02AD0A-$02AD41 Map32UpdateTiles grave reveals
                             (including Q326 Option A relocated slots $0EB1-$0EB8, $0F83-$0F86)
  5. custom_reveal_override: per-map overrides from Overworld/liftables_palette_fix.asm

Modes:
  check_tile16_pins.py --rom <rom.sfc>                  verify pins against Data/tile16_pins.json
  check_tile16_pins.py --rom <rom.sfc> --update         regenerate Data/tile16_pins.json
  check_tile16_pins.py --rom <rom.sfc> --free-range N   list contiguous runs of >= N Tile16 IDs
                                                        unused by all 192 maps AND all engine pins
  check_tile16_pins.py --rom <rom.sfc> --check-exits    audit all 79 exits + 129 OW entrances
                                                        for missing/invalid exit door overlays
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_PINS = ROOT / "Data" / "tile16_pins.json"
ORACLE_MAIN = ROOT / "Oracle_main.asm"

TILE16_EXPANDED_PC = 0x1E8000
TILE16_VANILLA_PC = 0x78000
TILE16_EXP_FLAG_PC = 0x02FD28
MAP32_EXP_FLAG_PC = 0x01772E
MAP32_VANILLA_PCS = (0x18000, 0x1B400, 0x20000, 0x23400)
MAP32_EXPANDED_PCS = (0x18000, 0x020000, 0x1F0000, 0x1F8000)
MAP32_PTR_HI_PC = 0x1794D
MAP32_PTR_LO_PC = 0x17B2D
TILE16_COUNT = 0x1000

OVERLAY_PTRS_PC = 0x77677
OVERLAY_MAPS = 0xA0
MAP32_UPDATE_TILES_PC = 0x12D0A  # SNES $02:AD0A (28 words = 56 bytes)

# Bank $1B lift/cut/dash/bomb/powder/hammer match & reveal IDs (usdasm bank_1B.asm
# + Overworld/liftables_palette_fix.asm).
BANK1B_INTERACTIVE_PINS: dict[int, dict[str, Any]] = {
    0x0036: {"users": ["bank1b:bush_match"], "policy": "block"},
    0x0101: {"users": ["bank1b:lw_sign_match"], "policy": "block"},
    0x0172: {"users": ["bank1b:dw_grass_reveal_override"], "policy": "block"},
    0x017D: {"users": ["bank1b:dw_sign_match"], "policy": "block"},
    0x020F: {"users": ["bank1b:small_light_rock_match"], "policy": "block"},
    0x0210: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0211: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0212: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0213: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0214: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0215: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0216: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0217: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0218: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0219: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x021A: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x021B: {"users": ["bank1b:rock_match"], "policy": "block"},
    0x0239: {"users": ["bank1b:heavy_rock_match"], "policy": "block"},
    0x0251: {"users": ["bank1b:pegasus_rock_pile_match"], "policy": "block"},
    0x037E: {"users": ["bank1b:tall_grass_match"], "policy": "block"},
    0x072A: {
        "users": ["bank1b:repurposed_brick_wall_skipped"],
        "policy": "warn",
        "intentionally_skipped": True,
    },
    0x091A: {"users": ["bank1b:grave_stairs_reveal"], "policy": "block"},
    0x091B: {"users": ["bank1b:grave_stairs_reveal"], "policy": "block"},
    0x0DC5: {"users": ["bank1b:tall_grass_rock_reveal"], "policy": "block"},
    0x0DC6: {"users": ["bank1b:sign_reveal"], "policy": "block"},
    0x0DC7: {"users": ["bank1b:bush_reveal"], "policy": "block"},
    0x0DC8: {"users": ["bank1b:dark_bush_reveal"], "policy": "block"},
    0x0DC9: {"users": ["bank1b:rock_dirt_reveal"], "policy": "block"},
    0x0DCA: {"users": ["bank1b:hammer_stake_reveal"], "policy": "block"},
    0x0DCB: {"users": ["bank1b:hammer_stake_reveal"], "policy": "block"},
    0x0DCC: {"users": ["bank1b:stump_reveal"], "policy": "block"},
    0x0DCD: {"users": ["bank1b:stump_reveal"], "policy": "block"},
    0x0DCE: {"users": ["bank1b:stump_reveal"], "policy": "block"},
    0x0DCF: {"users": ["bank1b:stump_reveal"], "policy": "block"},
    0x0DD0: {"users": ["bank1b:stump_reveal"], "policy": "block"},
}

# Q326 Option A grave reveal IDs patched into $02AD0A-$02AD41 by Overworld/liftables_palette_fix.asm.
Q326_GRAVE_REVEALS = (
    0x0EB1, 0x0EB2, 0x0EB3, 0x0EB4,
    0x0EB5, 0x0EB6, 0x0EB7, 0x0EB8,
    0x0F83, 0x0F84, 0x0F85, 0x0F86,
    0x0DD1, 0x0DD2,
    0x0918, 0x0919, 0x091A, 0x091B,
)

# Custom per-map reveal overrides from Overworld/liftables_palette_fix.asm
CUSTOM_REVEAL_OVERRIDES: dict[int, list[str]] = {
    0x0172: ["liftables_palette_fix.asm:dw63_bush_sign_reveal"],
    0x017D: ["liftables_palette_fix.asm:dw_sign_match"],
}

# Known closed overworld door Tile16 pairs (Overworld/entrances.asm OverworldDoorStyles)
CLOSED_DOOR_PAIRS = {
    (0x00FB, 0x00FC): "house_door",
    (0x075D, 0x075E): "house_door_pal6",
    (0x05D8, 0x05D9): "house_door_pal7",
    (0x0B82, 0x0B83): "kalyxo_boat_cabin",
}


def snes_to_pc(snes: int) -> int:
    return ((snes & 0x7F0000) >> 1) | (snes & 0x7FFF)


def read_u16(rom: bytes, pc: int) -> int:
    return rom[pc] | (rom[pc + 1] << 8)


def read_u24(rom: bytes, pc: int) -> int:
    return rom[pc] | (rom[pc + 1] << 8) | (rom[pc + 2] << 16)


def lz2_decompress_ow(rom: bytes, start: int, max_output: int = 512) -> bytes:
    """Overworld Map32 LZ2 decompressor ($00:E878 — big-endian cmd 4 offset)."""
    out = bytearray()
    p = start
    n = len(rom)
    while p < n and len(out) < max_output:
        hdr = rom[p]
        if hdr == 0xFF:
            break
        p += 1
        cmd = hdr >> 5
        length = (hdr & 0x1F) + 1
        if cmd == 7:
            if p >= n:
                break
            cmd = (hdr >> 2) & 7
            length = (((hdr & 3) << 8) | rom[p]) + 1
            p += 1
        if cmd == 0:
            out.extend(rom[p:p + length])
            p += length
        elif cmd == 1:
            if p >= n:
                break
            b = rom[p]
            p += 1
            out.extend([b] * length)
        elif cmd == 2:
            if p + 1 >= n:
                break
            b1, b2 = rom[p], rom[p + 1]
            p += 2
            for i in range(length):
                out.append(b1 if (i & 1) == 0 else b2)
        elif cmd == 3:
            if p >= n:
                break
            b = rom[p]
            p += 1
            for i in range(length):
                out.append((b + i) & 0xFF)
        elif cmd == 4:
            if p + 1 >= n:
                break
            off = (rom[p] << 8) | rom[p + 1]
            p += 2
            for i in range(length):
                out.append(out[off + i] if off + i < len(out) else 0)
        else:
            break
    return bytes(out[:max_output])


def tile16_table_pc(rom: bytes) -> int:
    if len(rom) > TILE16_EXPANDED_PC + TILE16_COUNT * 8 and (
        rom[TILE16_EXP_FLAG_PC] != 0x0F or len(rom) >= 0x400000
    ):
        return TILE16_EXPANDED_PC
    return TILE16_VANILLA_PC


def tile16_definition(rom: bytes, tid: int) -> str:
    base = tile16_table_pc(rom)
    return rom[base + tid * 8:base + tid * 8 + 8].hex()


def decode_map32_table(rom: bytes) -> list[tuple[int, int, int, int]]:
    exp32 = len(rom) >= 0x200000 and rom[MAP32_EXP_FLAG_PC] != 0x04
    addrs = MAP32_EXPANDED_PCS if exp32 else MAP32_VANILLA_PCS
    n_bytes = 0x67E0 if exp32 else 0x33F0
    groups = n_bytes // 6
    table: list[tuple[int, int, int, int]] = []
    for g in range(groups):
        quads = [[0, 0, 0, 0] for _ in range(4)]
        for qi, base in enumerate(addrs):
            p = base + g * 6
            hi0 = rom[p + 4]
            hi1 = rom[p + 5]
            his = (hi0 >> 4, hi0 & 0x0F, hi1 >> 4, hi1 & 0x0F)
            for s in range(4):
                quads[s][qi] = rom[p + s] | (his[s] << 8)
        for s in range(4):
            table.append((quads[s][0], quads[s][1], quads[s][2], quads[s][3]))
    return table


def _native_table_addresses(rom: bytes) -> tuple[int, dict[str, int]]:
    """Return (map_capacity, {table_name: pc_addr}) supporting rev3/4/5 OOSOW192 ROMs."""
    try:
        sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
        import lyra_native_loaders as lnl  # type: ignore

        info = lnl.read_native_directory(rom, experimental_page_tile16=True)
        if info is not None:
            capacity, bank, _entries = info
            txt = lnl.native_reader_constants(rom, experimental_page_tile16=True)
            tables: dict[str, int] = {"_tail_actor_bank": bank}
            for m in re.finditer(r"!LYRA_CURRENT_TABLE_(\w+)\s*=\s*\$([0-9A-Fa-f]+)", txt):
                tables[m.group(1)] = snes_to_pc(int(m.group(2), 16))
            return capacity, tables
    except Exception:
        pass
    return 160, {}


def decode_map16_grid(
    rom: bytes,
    area_id: int,
    map32_table: list[tuple[int, int, int, int]],
    native_tables: dict[str, int],
) -> list[list[int]]:
    """Decode one 32x32 Tile16 grid for any map $00-$BF (including rev5 tail maps)."""
    if area_id >= 0xA0 and "map32_high" in native_tables and "map32_low" in native_tables:
        hi_base = native_tables["map32_high"]
        lo_base = native_tables["map32_low"]
    elif len(rom) > 0x142640 + area_id * 3 + 2 and rom[0x1423FF] == 0xEA:
        hi_base, lo_base = 0x142400, 0x142640
    else:
        if area_id >= 0xA0:
            return [[0] * 32 for _ in range(32)]
        hi_base, lo_base = MAP32_PTR_HI_PC, MAP32_PTR_LO_PC

    p_hi_snes = read_u24(rom, hi_base + area_id * 3)
    p_lo_snes = read_u24(rom, lo_base + area_id * 3)
    if p_hi_snes == 0 or p_lo_snes == 0:
        return [[0] * 32 for _ in range(32)]
    hi = lz2_decompress_ow(rom, snes_to_pc(p_hi_snes), max_output=256)
    lo = lz2_decompress_ow(rom, snes_to_pc(p_lo_snes), max_output=256)
    grid = [[0] * 32 for _ in range(32)]
    for idx in range(min(256, len(hi), len(lo))):
        t32 = (hi[idx] << 8) | lo[idx]
        if t32 < len(map32_table):
            tl, tr, bl, br = map32_table[t32]
            x, y = (idx & 15) * 2, (idx >> 4) * 2
            grid[y][x] = tl
            grid[y][x + 1] = tr
            grid[y + 1][x] = bl
            grid[y + 1][x + 1] = br
    return grid


def decode_all_maps_usage(rom: bytes) -> tuple[int, dict[int, dict[str, Any]]]:
    """Count Tile16 static placements across all maps ($00-$BF when rev5, else $00-$9F)."""
    capacity, native_tables = _native_table_addresses(rom)
    map32_table = decode_map32_table(rom)
    usage: dict[int, dict[str, Any]] = {}
    for m in range(capacity):
        grid = decode_map16_grid(rom, m, map32_table, native_tables)
        bucket = (
            "lw" if m < 0x40 else
            "dw" if m < 0x80 else
            "sw_base" if m < 0xA0 else
            "sw_tail"
        )
        for row in grid:
            for tid in row:
                rec = usage.get(tid)
                if rec is None:
                    rec = {"total": 0, "lw": 0, "dw": 0, "sw_base": 0, "sw_tail": 0, "maps": set()}
                    usage[tid] = rec
                rec["total"] += 1
                rec[bucket] += 1
                rec["maps"].add(m)
    return capacity, usage


def extract_overlay_stream_refs(rom: bytes) -> dict[int, set[str]]:
    """Tile16 IDs stored by ROM overlay streams ($077677, ov00-ov9F)."""
    refs: dict[int, set[str]] = {}
    for m in range(OVERLAY_MAPS):
        p = OVERLAY_PTRS_PC + m * 3
        snes = read_u24(rom, p)
        if snes == 0:
            continue
        addr = snes_to_pc(snes)
        value, stores = 0, 0
        while addr < len(rom) and rom[addr] != 0x6B:
            op = rom[addr]
            if op == 0xA9:
                value = read_u16(rom, addr + 1)
                addr += 3
            elif op in (0x8D, 0x9D):
                if value < TILE16_COUNT:
                    refs.setdefault(value, set()).add(f"ov{m:02X}")
                addr += 3
                stores += 1
            elif op == 0x1A:
                value = (value + 1) & 0xFFFF
                addr += 1
            else:
                break
            if stores > 1024:
                break
    return refs


def collect_active_asm_files(root: Path = ROOT) -> list[Path]:
    """Walk all active incsrc files reachable from Oracle_main.asm (plus known optional modules)."""
    visited: set[Path] = set()
    ordered: list[Path] = []
    queue: list[Path] = []
    main_asm = root / "Oracle_main.asm"
    if main_asm.exists():
        queue.append(main_asm)
    for extra in (
        root / "Overworld" / "kalyxo_boat.asm",
        root / "Data" / "overworld" / "kalyxo_boat_placements.asm",
    ):
        if extra.exists():
            queue.append(extra)

    inc_re = re.compile(r'^\s*incsrc\s+"([^"]+)"', re.IGNORECASE)
    while queue:
        cur = queue.pop(0).resolve()
        if cur in visited or not cur.exists():
            continue
        visited.add(cur)
        ordered.append(cur)
        try:
            text = cur.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            code = line.split(";", 1)[0]
            m = inc_re.match(code)
            if not m:
                continue
            rel = m.group(1)
            for base in (root, cur.parent):
                cand = (base / rel).resolve()
                if cand.exists():
                    queue.append(cand)
                    break
    return ordered


def extract_asm_draw_persist_refs(root: Path = ROOT) -> dict[int, set[str]]:
    """Scan all active ASM files calling Overworld_DrawMap16_Persist / Anywhere
    plus OverworldDoorStyles and Boat_*Tiles tables."""
    refs: dict[int, set[str]] = {}
    label_re = re.compile(r"^\s*#?([A-Za-z_][A-Za-z0-9_]*):")
    lda_re = re.compile(r"LDA\.w\s+#\$([0-9A-Fa-f]{4})")
    dw_hex_re = re.compile(r"\$([0-9A-Fa-f]{4})")

    for path in collect_active_asm_files(root):
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        has_draw = ("Overworld_DrawMap16_Persist" in text or
                    "Overworld_DrawMap16_Anywhere" in text or
                    "OverworldDoorStyles:" in text or
                    "Boat_OpenTiles:" in text)
        if not has_draw:
            continue
        rel = str(path.relative_to(root))
        lines = text.splitlines()
        label = rel
        in_door_styles = False
        in_boat_tiles = False
        recent_lda: list[tuple[int, int]] = []  # (line_no, tile16)

        for lineno, raw in enumerate(lines, 1):
            code = raw.split(";", 1)[0]
            lm = label_re.match(code)
            if lm:
                label = lm.group(1)
                in_door_styles = (label == "OverworldDoorStyles")
                in_boat_tiles = label in ("Boat_OpenTiles", "Boat_ClosedTiles")

            if in_door_styles:
                if "OverworldDoorStyles_end" in code:
                    in_door_styles = False
                elif re.search(r"\bdw\b", code, re.IGNORECASE):
                    for h in dw_hex_re.findall(code):
                        t = int(h, 16)
                        if t < TILE16_COUNT:
                            refs.setdefault(t, set()).add(f"{rel}:OverworldDoorStyles")
                continue

            if in_boat_tiles:
                if re.search(r"\bdw\b", code, re.IGNORECASE):
                    for h in dw_hex_re.findall(code):
                        t = int(h, 16)
                        if t < TILE16_COUNT and t != 0xFFFF:
                            refs.setdefault(t, set()).add(f"{rel}:{label}")
                elif code.strip():
                    in_boat_tiles = False
                continue

            # For overlays.asm, every LDA.w #$xxxx < $1000 is an overlay Tile16 constant
            if rel == "Overworld/overlays.asm":
                for h in lda_re.findall(code):
                    t = int(h, 16)
                    if t < TILE16_COUNT:
                        refs.setdefault(t, set()).add(f"{rel}:{label}")
                continue

            # For other ASM files, capture LDA.w #$xxxx within 6 lines before DrawMap16 call
            for h in lda_re.findall(code):
                t = int(h, 16)
                if t < TILE16_COUNT:
                    recent_lda.append((lineno, t))
            if "Overworld_DrawMap16_Persist" in code or "Overworld_DrawMap16_Anywhere" in code:
                for prev_line, t in recent_lda:
                    if lineno - prev_line <= 6:
                        refs.setdefault(t, set()).add(f"{rel}:{label}")
                recent_lda = [x for x in recent_lda if lineno - x[0] <= 2]
            else:
                recent_lda = [x for x in recent_lda if lineno - x[0] <= 6]

    return refs


def extract_bank02_map32_update_refs(rom: bytes) -> dict[int, set[str]]:
    """Extract Tile16 IDs from Bank $02 $02AD0A-$02AD41 Map32UpdateTiles plus Q326 ASM IDs."""
    refs: dict[int, set[str]] = {}
    if len(rom) >= MAP32_UPDATE_TILES_PC + 56:
        for i in range(28):
            tid = read_u16(rom, MAP32_UPDATE_TILES_PC + i * 2)
            if tid < TILE16_COUNT:
                # Base ROM still has overwritten $0DD3-$0DDE; Q326 ASM replaces them at patch time
                tag = "bank02:Map32UpdateTiles_base_legacy" if 0x0DD3 <= tid <= 0x0DDE else "bank02:Map32UpdateTiles"
                refs.setdefault(tid, set()).add(tag)
    for tid in Q326_GRAVE_REVEALS:
        refs.setdefault(tid, set()).add("bank02:Map32UpdateTiles_q326")
    return refs


def collect_all_pins(rom: bytes, root: Path = ROOT) -> dict[int, dict[str, Any]]:
    """Aggregate all 5 categories of engine-referenced Tile16 pins."""
    merged: dict[int, dict[str, Any]] = {}

    def add(tid: int, category: str, user: str, *, policy: str = "block", extra: dict[str, Any] | None = None) -> None:
        entry = merged.setdefault(
            tid,
            {"categories": set(), "users": set(), "policy": policy},
        )
        entry["categories"].add(category)
        entry["users"].add(user)
        if policy == "block":
            entry["policy"] = "block"
        if extra:
            entry.update(extra)

    for tid, users in extract_overlay_stream_refs(rom).items():
        for u in users:
            add(tid, "overlay_stream", u)

    for tid, users in extract_asm_draw_persist_refs(root).items():
        for u in users:
            add(tid, "asm_draw_persist", u)

    for tid, meta in BANK1B_INTERACTIVE_PINS.items():
        extra = {"intentionally_skipped": True} if meta.get("intentionally_skipped") else None
        for u in meta["users"]:
            add(tid, "bank1b_interactive", u, policy=meta["policy"], extra=extra)

    for tid, users in extract_bank02_map32_update_refs(rom).items():
        for u in users:
            # Base legacy $0DD3-$0DDE were overwritten before Q326; mark warn if ONLY base legacy
            pol = "warn" if (0x0DD3 <= tid <= 0x0DDE) else "block"
            add(tid, "bank02_map32_update", u, policy=pol)

    for tid, users in CUSTOM_REVEAL_OVERRIDES.items():
        for u in users:
            add(tid, "custom_reveal_override", u)

    return merged


def find_free_ranges(rom: bytes, min_run: int, root: Path = ROOT) -> dict[str, Any]:
    """Find all contiguous runs of >= min_run Tile16 IDs unused by 192 maps AND engine pins."""
    capacity, usage = decode_all_maps_usage(rom)
    pins = collect_all_pins(rom, root)
    occupied = set(usage.keys()) | set(pins.keys())
    free_ids = [t for t in range(TILE16_COUNT) if t not in occupied]

    runs: list[dict[str, Any]] = []
    i = 0
    while i < len(free_ids):
        start = free_ids[i]
        j = i
        while j + 1 < len(free_ids) and free_ids[j + 1] == free_ids[j] + 1:
            j += 1
        length = j - i + 1
        if length >= min_run:
            runs.append({
                "start": f"0x{start:03X}",
                "end": f"0x{free_ids[j]:03X}",
                "length": length,
            })
        i = j + 1

    return {
        "maps_scanned": capacity,
        "tile16_total": TILE16_COUNT,
        "static_used": len(usage),
        "engine_pinned": len(pins),
        "total_occupied": len(occupied),
        "total_free": len(free_ids),
        "min_run": min_run,
        "runs": runs,
    }


def audit_overworld_exit_doors(rom: bytes) -> dict[str, Any]:
    """Audit all 79 Overworld Exits ($00-$4E) and 129 OW Entrances ($1BB96F / $02D724)
    for missing, out-of-bounds, or non-door exit overlay positions."""
    capacity, native_tables = _native_table_addresses(rom)
    map32_table = decode_map32_table(rom)
    area_cache: dict[int, tuple[list[list[int]], str]] = {}

    def get_area_grid(area_id: int) -> tuple[list[list[int]], str, int]:
        if area_id >= capacity:
            return [[0] * 32 for _ in range(32)], "OOB", area_id
        if area_id < 0xA0 and len(rom) > 0x140998 + area_id and rom[0x140145] >= 3:
            parent = rom[0x140998 + area_id]
        elif "parent" in native_tables:
            parent = rom[native_tables["parent"] + area_id]
        else:
            parent = area_id
        if parent in area_cache:
            g, sz = area_cache[parent]
            return g, sz, parent
        if parent < 0xA0 and rom[0x140145] >= 3:
            sz_code = rom[0x1788D + parent]
        elif "area_size" in native_tables:
            sz_code = rom[native_tables["area_size"] + parent]
        else:
            sz_code = 0
        nw = decode_map16_grid(rom, parent, map32_table, native_tables)
        if sz_code == 1:
            ne = decode_map16_grid(rom, parent + 1, map32_table, native_tables)
            sw = decode_map16_grid(rom, parent + 8, map32_table, native_tables)
            se = decode_map16_grid(rom, parent + 9, map32_table, native_tables)
            grid = [nw[r] + ne[r] for r in range(32)] + [sw[r] + se[r] for r in range(32)]
            sz_name = "Large"
        elif sz_code == 2:
            ne = decode_map16_grid(rom, parent + 1, map32_table, native_tables)
            grid = [nw[r] + ne[r] for r in range(32)]
            sz_name = "Wide"
        elif sz_code == 3:
            sw = decode_map16_grid(rom, parent + 8, map32_table, native_tables)
            grid = nw + sw
            sz_name = "Tall"
        else:
            grid = nw
            sz_name = "Small"
        area_cache[parent] = (grid, sz_name)
        return grid, sz_name, parent

    def pair_at_cell(grid: list[list[int]], cell: int) -> tuple[int, int] | None:
        idx = (cell & 0x7FFF) // 2
        cx, cy = idx % 64, idx // 64
        if 0 <= cy < len(grid) and 0 <= cx + 1 < len(grid[0]):
            return (grid[cy][cx], grid[cy][cx + 1])
        return None

    exit_findings: list[dict[str, Any]] = []
    # 1. Audit 79 Overworld Exit records ($02DD8A..)
    for i in range(0x4F):
        room = read_u16(rom, 0x15D8A + i * 2)
        mp = rom[0x15E28 + i]
        yp = read_u16(rom, 0x16051 + i * 2)
        xp = read_u16(rom, 0x160EF + i * 2)
        if xp == 0xFFFF and yp == 0xFFFF:
            continue
        dt1 = read_u16(rom, 0x16367 + i * 2)
        dt2 = read_u16(rom, 0x16405 + i * 2)
        grid, sz, parent = get_area_grid(mp)
        if dt1:
            pair = pair_at_cell(grid, dt1)
            if pair is None:
                exit_findings.append({
                    "kind": "exit_dt1_oob",
                    "exit_id": f"0x{i:02X}",
                    "room_id": f"0x{room:04X}",
                    "map_id": f"0x{mp:02X}",
                    "door_type_1": f"0x{dt1:04X}",
                })
            elif pair not in CLOSED_DOOR_PAIRS:
                exit_findings.append({
                    "kind": "exit_dt1_not_closed_door",
                    "exit_id": f"0x{i:02X}",
                    "room_id": f"0x{room:04X}",
                    "map_id": f"0x{mp:02X}",
                    "door_type_1": f"0x{dt1:04X}",
                    "target_tiles": [f"0x{pair[0]:03X}", f"0x{pair[1]:03X}"],
                })
        if dt2:
            pair = pair_at_cell(grid, dt2)
            if pair is None:
                exit_findings.append({
                    "kind": "exit_dt2_oob",
                    "exit_id": f"0x{i:02X}",
                    "room_id": f"0x{room:04X}",
                    "map_id": f"0x{mp:02X}",
                    "area_size": sz,
                    "door_type_2": f"0x{dt2:04X}",
                })

    # 2. Audit 129 Overworld Entrance triggers ($1BB96F) + kEntranceExit ($02D724)
    entrance_findings: list[dict[str, Any]] = []
    # Map rooms that have an explicit Exit record with non-zero dt1/dt2
    explicit_exit_rooms = {
        read_u16(rom, 0x15D8A + i * 2): (read_u16(rom, 0x16367 + i * 2), read_u16(rom, 0x16405 + i * 2))
        for i in range(0x4F)
        if not (read_u16(rom, 0x160EF + i * 2) == 0xFFFF and read_u16(rom, 0x16051 + i * 2) == 0xFFFF)
    }

    for i in range(129):
        scr = read_u16(rom, 0x0DB96F + i * 2)
        tile = read_u16(rom, 0x0DBA71 + i * 2)
        eid = rom[0x0DBB73 + i]
        if scr == 0xFFFF or tile == 0xFFFF or eid >= 133:
            continue
        room = read_u16(rom, 0x14813 + eid * 2)
        ex_field = read_u16(rom, 0x15724 + eid * 2)
        grid, sz, parent = get_area_grid(scr)
        below_cell = tile + 0x0080
        below_pair = pair_at_cell(grid, below_cell)
        has_explicit_dt1 = explicit_exit_rooms.get(room, (0, 0))[0] != 0

        if below_pair in CLOSED_DOOR_PAIRS and ex_field != below_cell and not has_explicit_dt1:
            entrance_findings.append({
                "kind": "missing_or_wrong_entrance_exit_door",
                "ow_ent_index": i,
                "entrance_id": f"0x{eid:02X}",
                "room_id": f"0x{room:04X}",
                "map_id": f"0x{scr:02X}",
                "tile_cell": f"0x{tile:04X}",
                "expected_exit_field": f"0x{below_cell:04X}",
                "actual_exit_field": f"0x{ex_field:04X}",
                "closed_door_tiles": [f"0x{below_pair[0]:03X}", f"0x{below_pair[1]:03X}"],
                "door_style": CLOSED_DOOR_PAIRS[below_pair],
            })
        elif ex_field not in (0x0000, 0x7FFE, 0xFFFF):
            ex_pair = pair_at_cell(grid, ex_field)
            if ex_pair is None or ex_pair not in CLOSED_DOOR_PAIRS:
                entrance_findings.append({
                    "kind": "stale_entrance_exit_door_non_door_target",
                    "ow_ent_index": i,
                    "entrance_id": f"0x{eid:02X}",
                    "room_id": f"0x{room:04X}",
                    "map_id": f"0x{scr:02X}",
                    "actual_exit_field": f"0x{ex_field:04X}",
                    "target_tiles": (
                        [f"0x{ex_pair[0]:03X}", f"0x{ex_pair[1]:03X}"] if ex_pair else "OOB"
                    ),
                    "guarded_by_asm": True,
                })

    return {
        "exits_checked": 0x4F,
        "ow_entrances_checked": 129,
        "exit_findings": exit_findings,
        "entrance_findings": entrance_findings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--pins", type=Path, default=DEFAULT_PINS)
    ap.add_argument("--update", action="store_true", help="regenerate Data/tile16_pins.json from --rom")
    ap.add_argument("--free-range", type=int, metavar="N", help="find contiguous runs of >= N globally free Tile16 IDs across all 192 maps")
    ap.add_argument("--check-exits", action="store_true", help="audit all overworld exits & entrance exit-door overlays")
    ap.add_argument("--json", action="store_true", help="emit structured JSON")
    args = ap.parse_args(argv)

    rom = args.rom.read_bytes()

    if args.free_range is not None:
        report = find_free_ranges(rom, max(1, args.free_range))
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"[*] Scanned {report['maps_scanned']} maps: "
                f"{report['static_used']} static used, {report['engine_pinned']} engine pinned, "
                f"{report['total_free']} globally free Tile16 IDs."
            )
            print(f"[*] Contiguous free runs >= {report['min_run']} ({len(report['runs'])} runs):")
            for r in report["runs"][:30]:
                print(f"    {r['start']}..{r['end']}  (len={r['length']})")
        return 0

    if args.check_exits:
        report = audit_overworld_exit_doors(rom)
        if args.json:
            print(json.dumps(report, indent=2))
        else:
            print(
                f"[*] Audited {report['exits_checked']} exits + {report['ow_entrances_checked']} OW entrances: "
                f"{len(report['exit_findings'])} exit issues, {len(report['entrance_findings'])} entrance exit-door issues."
            )
            for item in report["exit_findings"]:
                print(f"  [EXIT] {item}")
            for item in report["entrance_findings"]:
                print(f"  [ENT ] {item}")
        return 0

    pins_map = collect_all_pins(rom)

    if args.update:
        categories_summary: dict[str, int] = {}
        tile16_out: dict[str, Any] = {}
        for tid, info in sorted(pins_map.items()):
            cats = sorted(info["categories"])
            for c in cats:
                categories_summary[c] = categories_summary.get(c, 0) + 1
            entry: dict[str, Any] = {
                "def": tile16_definition(rom, tid),
                "categories": cats,
                "policy": info["policy"],
                "users": sorted(info["users"]),
            }
            if info.get("intentionally_skipped"):
                entry["intentionally_skipped"] = True
            tile16_out[f"{tid:03X}"] = entry
        payload = {
            "schema_version": 2,
            "about": (
                "Unified engine-referenced Tile16 pins (overlay streams, active ASM DrawMap16 callers, "
                "Bank $1B interactive tiles, Bank $02 Map32UpdateTiles grave reveals, and custom reveal overrides). "
                "Regenerate: python3 Scripts/Build/check_tile16_pins.py --rom <base.sfc> --update"
            ),
            "category_counts": categories_summary,
            "tile16": tile16_out,
        }
        args.pins.write_text(json.dumps(payload, indent=1) + "\n", encoding="utf-8")
        print(f"[+] pinned {len(tile16_out)} engine-referenced Tile16 IDs to {args.pins} ({categories_summary})")
        return 0

    if not args.pins.exists():
        print(f"[-] pin file not found: {args.pins}", file=sys.stderr)
        return 1

    saved = json.loads(args.pins.read_text(encoding="utf-8"))["tile16"]
    changed_block: list[dict[str, Any]] = []
    changed_warn: list[dict[str, Any]] = []
    unpinned: list[str] = []

    for tid, info in sorted(pins_map.items()):
        key = f"{tid:03X}"
        cur_def = tile16_definition(rom, tid)
        pin = saved.get(key)
        if pin is None:
            unpinned.append(key)
            continue
        if pin["def"] != cur_def:
            rec = {
                "tile16": f"0x{key}",
                "expected": pin["def"],
                "actual": cur_def,
                "policy": pin.get("policy", info["policy"]),
                "categories": sorted(info["categories"]),
                "users": sorted(info["users"]),
            }
            if rec["policy"] == "warn":
                changed_warn.append(rec)
            else:
                changed_block.append(rec)

    result = {
        "checked": len(pins_map),
        "changed_block": changed_block,
        "changed_warn": changed_warn,
        "unpinned": unpinned,
    }
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if unpinned:
            print(f"[!] {len(unpinned)} engine-referenced Tile16 IDs are not pinned: {' '.join(unpinned[:20])}")
        if changed_warn:
            print(f"[!] {len(changed_warn)} warn-policy Tile16 IDs changed definition:")
            for r in changed_warn[:20]:
                print(f"    {r['tile16']} {r['expected']} -> {r['actual']} ({', '.join(r['users'])})")
        if changed_block:
            print(f"[-] {len(changed_block)} protected Tile16 IDs changed definition:")
            for r in changed_block[:40]:
                print(f"    {r['tile16']} {r['expected']} -> {r['actual']} ({', '.join(r['users'])})")
        elif not unpinned:
            print(f"[+] {len(pins_map)} engine-referenced Tile16 IDs match {args.pins.name}.")
    return 1 if changed_block else 0


if __name__ == "__main__":
    sys.exit(main())
