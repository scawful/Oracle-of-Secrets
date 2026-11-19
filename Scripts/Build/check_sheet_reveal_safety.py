#!/usr/bin/env python3
"""Transitive reveal-char corruption & slot-6 interactive TileType bleed detector (Q328 Track A2).

Scans all 192 overworld maps ($00-$BF) in a ROM:
  Check A — Transitive Reveal-Char Corruption:
    Expands static Tile16 placements on each map to runtime-revealed Tile16s
    (bushes $0036 -> $0DC7, signs $0101/$017D -> $0DC6, rocks $020F-$021B/$0239/$0251
    -> $0DC5/$0DC9, tall grass $037E -> $0DC5, plus ROM overlay streams), resolves
    every quadrant's (slot, local_char) on custom sheets ($DF-$FE), and flags
    reveal chars that are blanked or repurposed by unrelated static scenery on
    that custom sheet (respecting explicit ASM overrides such as DW $63 -> $0172).

  Check B — Slot-6 Interactive OverworldTileTypes Bleed:
    Flags non-interactive static Tile16s whose quadrants land on VRAM $180-$1BF
    (slot 6) chars with interactive OverworldTileTypes ($40, $50-$57) on custom
    sheets ($DF-$FE), which would otherwise allow Link to lift/cut cliffs or walls.

Usage:
  python3 Scripts/Build/check_sheet_reveal_safety.py --rom <rom.sfc> [--json] [--strict]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402

CUSTOM_SHEET_RANGE = range(0xDF, 0xFF)
INTERACTIVE_TILE_TYPES = {0x40, 0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57}

# Static interactive Tile16 -> list of runtime revealed Tile16s (Bank $1B)
INTERACTIVE_REVEALS: dict[int, tuple[int, ...]] = {
    0x0036: (0x0DC7,),
    0x0101: (0x0DC6,),
    0x017D: (0x0DC6,),
    0x020F: (0x0DC5, 0x0DC9),
    0x0210: (0x0DC9,),
    0x0211: (0x0DC9,),
    0x0212: (0x0DC9,),
    0x0213: (0x0DC9,),
    0x0214: (0x0DC9,),
    0x0215: (0x0DC9,),
    0x0216: (0x0DC9,),
    0x0217: (0x0DC9,),
    0x0218: (0x0DC9,),
    0x0219: (0x0DC9,),
    0x021A: (0x0DC9,),
    0x021B: (0x0DC9,),
    0x0239: (0x0DC9,),
    0x0251: (0x0DC9,),
    0x037E: (0x0DC5,),
}

# Known genuine interactive/reveal Tile16s that legitimately occupy interactive TileTypes
LEGITIMATE_INTERACTIVE_TILES = set(INTERACTIVE_REVEALS.keys()) | {
    0x0DC5, 0x0DC6, 0x0DC7, 0x0DC8, 0x0DC9, 0x0DCA, 0x0DCB,
    0x0DCC, 0x0DCD, 0x0DCE, 0x0DCF, 0x0DD0,
    # Standard grass/bush/peg/stump/flower/warp/sign tiles across LW/DW
    0x0034, 0x0035, 0x0037, 0x0038, 0x0039, 0x003A, 0x003B,
    0x0100, 0x0102, 0x0172, 0x020E, 0x0238, 0x0250, 0x037D,
}

# Explicit ASM reveal overrides from Overworld/liftables_palette_fix.asm:
# (parent_area, source_tile16) -> replacement reveal tuple
ASM_REVEAL_OVERRIDES: dict[tuple[int, int], tuple[int, ...]] = {
    (0x63, 0x0036): (0x0172,),
    (0x63, 0x017D): (0x0172,),
}


def _read_area_parent_and_sheets(
    rom: bytes,
    area_id: int,
    native_tables: dict[str, int],
) -> tuple[int, list[int]]:
    """Resolve (parent_id, 8 static BG sheet IDs) for any map $00-$BF,
    substituting vanilla AreaGFX defaults for any $FF ZSCustomOverworld sentinel slot."""
    if area_id >= 0xA0 and "parent" in native_tables and "gfx" in native_tables:
        parent = rom[native_tables["parent"] + area_id]
        off = native_tables["gfx"] + parent * 8
        raw = list(rom[off:off + 8])
        defaults = [0x3A, 0x3B, 0x3C, 0x3D, 0x47, 0x48, 0x3E, 0x5B]
        return parent, [defaults[i] if raw[i] == 0xFF else raw[i] for i in range(8)]

    parent = sic.area_parent_id(rom, area_id)
    base_sheets = sic.load_area_static_graphics(rom, parent)
    # ZSCustomOverworld v3: non-zero (0x01 or 0xFF) enables OverworldCustomTileGFXGroupArray;
    # per-slot $FF retains the AreaGFX default sheet for that slot.
    if sic.zs_version(rom) >= 3 and parent < 0xA0 and rom[sic.PC_ZS_TILE_GFX_EN] != 0:
        off = sic.PC_ZS_TILE_GFX_ARR + parent * 8
        raw = list(rom[off:off + 8])
        if any(b not in (0x00, 0xFF) for b in raw):
            return parent, [base_sheets[i] if raw[i] == 0xFF else raw[i] for i in range(8)]
    return parent, base_sheets


def _read_record413_semantic_tiles(rom: bytes) -> dict[int, set[int]]:
    """Return {physical_page: set(local_tile16_ids)} covered by Record 413 semantic overrides."""
    covered: dict[int, set[int]] = {}
    try:
        import lyra_native_loaders as lnl  # type: ignore

        info = lnl.read_native_directory(rom, experimental_page_tile16=True)
        if info is None:
            return covered
        _cap, _bank, entries = info
        if 413 not in entries:
            return covered
        addr, count = entries[413]
        pc = ctp.snes_to_pc(addr)
        for i in range(count):
            page = ctp.read_u16(rom, pc + i * 12)
            tid = ctp.read_u16(rom, pc + i * 12 + 2)
            if page == 0xFFFF:
                break
            covered.setdefault(page, set()).add(tid)
    except Exception:
        pass
    return covered


def scan_sheet_reveal_safety(rom: bytes) -> dict[str, Any]:
    """Run Check A (transitive reveal-char corruption) and Check B (slot-6 TileType bleed)
    across all maps ($00-$BF when rev5, else $00-$9F)."""
    capacity, native_tables = ctp._native_table_addresses(rom)
    map32_table = ctp.decode_map32_table(rom)
    tile16_table = sic.decode_tile16_table(rom)
    ow_tile_types = list(rom[sic.PC_TILETYPE:sic.PC_TILETYPE + 0x200])
    sem_covered = _read_record413_semantic_tiles(rom)

    # Decode standard baseline slot-6 sheets ($3E LW, $45 DW) and any custom sheets ($DF-$FE)
    # actually referenced by maps.
    map_sheets: dict[int, tuple[int, list[int]]] = {}
    referenced_custom: set[int] = set()
    for m in range(capacity):
        parent, sheets = _read_area_parent_and_sheets(rom, m, native_tables)
        map_sheets[m] = (parent, sheets)
        for s in sheets:
            if s in CUSTOM_SHEET_RANGE:
                referenced_custom.add(s)

    decode_set = set(referenced_custom) | {0x3E, 0x45}
    sheet_chars = sic.decode_sheet_chars(rom, decode_set)

    # Pre-group overlay Tile16s per map
    overlay_by_map: dict[int, set[int]] = {}
    for tid, users in ctp.extract_overlay_stream_refs(rom).items():
        for u in users:
            if u.startswith("ov"):
                overlay_by_map.setdefault(int(u[2:], 16), set()).add(tid)

    reveal_findings: list[dict[str, Any]] = []
    slot6_bleed_findings: list[dict[str, Any]] = []
    seen_reveal_keys: set[tuple[int, int, int, int]] = set()
    seen_bleed_keys: set[tuple[int, int, int, int]] = set()

    # Pass 1: decode grids for maps using custom sheets and aggregate static scenery
    # per (parent, slot, local) so LargeArea sibling quadrants (e.g. DW $63/$64/$6B/$6C)
    # share their custom-sheet scenery char occupancy!
    map_counts: dict[int, dict[int, int]] = {}
    parent_scenery_chars: dict[tuple[int, int, int], set[int]] = {}
    for m in range(capacity):
        parent, sheets = map_sheets[m]
        if not any(s in CUSTOM_SHEET_RANGE for s in sheets):
            continue
        grid = ctp.decode_map16_grid(rom, m, map32_table, native_tables)
        counts: dict[int, int] = {}
        for row in grid:
            for tid in row:
                counts[tid] = counts.get(tid, 0) + 1
        map_counts[m] = counts

        for tid, cnt in counts.items():
            if tid >= len(tile16_table):
                continue
            words = tile16_table[tid]
            is_legit_inter = tid in LEGITIMATE_INTERACTIVE_TILES
            is_sem_overridden = tid in sem_covered.get(m, set())
            for w in words:
                ch = w & 0x3FF
                if ch >= 0x200:
                    continue
                slot, local = ch >> 6, ch & 0x3F
                sh = sheets[slot]
                if not is_legit_inter:
                    parent_scenery_chars.setdefault((parent, slot, local), set()).add(tid)

                # Check B: Slot-6 interactive OverworldTileTypes bleed on custom sheets
                if (
                    slot == 6
                    and sh in CUSTOM_SHEET_RANGE
                    and not is_legit_inter
                    and not is_sem_overridden
                    and ow_tile_types[ch] in INTERACTIVE_TILE_TYPES
                ):
                    key = (parent, sh, tid, ch)
                    if key not in seen_bleed_keys:
                        seen_bleed_keys.add(key)
                        slot6_bleed_findings.append({
                            "check": "B_slot6_interactive_tiletype_bleed",
                            "map_id": f"0x{m:02X}",
                            "parent_id": f"0x{parent:02X}",
                            "sheet": f"0x{sh:02X}",
                            "tile16": f"0x{tid:03X}",
                            "placements": cnt,
                            "vram_char": f"0x{ch:03X}",
                            "local_char": f"0x{local:02X}",
                            "tile_type": f"0x{ow_tile_types[ch]:02X}",
                        })

    # Pass 2: Check A — Transitive reveal-char corruption on custom sheets
    for m, counts in map_counts.items():
        parent, sheets = map_sheets[m]
        baseline_slot6 = 0x45 if (0x40 <= m < 0x80) else 0x3E
        for src_tid, default_reveals in INTERACTIVE_REVEALS.items():
            src_cnt = counts.get(src_tid, 0)
            if src_cnt == 0:
                continue
            reveals = ASM_REVEAL_OVERRIDES.get((parent, src_tid), default_reveals)
            for rev_tid in reveals:
                if rev_tid >= len(tile16_table):
                    continue
                for w in tile16_table[rev_tid]:
                    ch = w & 0x3FF
                    if ch >= 0x200:
                        continue
                    slot, local = ch >> 6, ch & 0x3F
                    sh = sheets[slot]
                    if sh not in CUSTOM_SHEET_RANGE:
                        continue
                    px = sheet_chars.get(sh, [None] * 64)[local]
                    is_blank = px is not None and not any(px)
                    base_px = (
                        sheet_chars.get(baseline_slot6, [None] * 64)[local]
                        if slot == 6 else None
                    )
                    base_nonblank = base_px is not None and any(base_px)
                    colliding_scenery = sorted(
                        parent_scenery_chars.get((parent, slot, local), set()) - {src_tid, rev_tid}
                    )
                    differs_from_base = (
                        slot == 6 and px is not None and base_px is not None and px != base_px
                    )

                    reasons: list[str] = []
                    if is_blank and base_nonblank:
                        reasons.append("blanked_reveal_char")
                    if colliding_scenery:
                        reasons.append("shared_with_static_scenery")
                    if differs_from_base and not is_blank and not colliding_scenery:
                        reasons.append("modified_vs_baseline_slot6")

                    if reasons:
                        rkey = (parent, sh, rev_tid, ch)
                        if rkey not in seen_reveal_keys:
                            seen_reveal_keys.add(rkey)
                            reveal_findings.append({
                                "check": "A_transitive_reveal_char_corruption",
                                "map_id": f"0x{m:02X}",
                                "parent_id": f"0x{parent:02X}",
                                "sheet": f"0x{sh:02X}",
                                "slot": slot,
                                "source_tile16": f"0x{src_tid:03X}",
                                "source_placements": src_cnt,
                                "reveal_tile16": f"0x{rev_tid:03X}",
                                "vram_char": f"0x{ch:03X}",
                                "local_char": f"0x{local:02X}",
                                "reasons": reasons,
                                "colliding_scenery_tile16s": [f"0x{t:03X}" for t in colliding_scenery[:8]],
                                "severity": "error" if ("blanked_reveal_char" in reasons or "shared_with_static_scenery" in reasons) else "warn",
                            })

    return {
        "maps_scanned": capacity,
        "custom_sheets_found": [f"0x{s:02X}" for s in sorted(referenced_custom)],
        "asm_reveal_overrides_applied": [
            {"parent_id": f"0x{p:02X}", "source_tile16": f"0x{s:03X}", "reveals": [f"0x{r:03X}" for r in rs]}
            for (p, s), rs in sorted(ASM_REVEAL_OVERRIDES.items())
        ],
        "check_a_reveal_corruption_count": len(reveal_findings),
        "check_b_slot6_bleed_count": len(slot6_bleed_findings),
        "check_a_findings": reveal_findings,
        "check_b_findings": slot6_bleed_findings,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--json", action="store_true", help="emit structured JSON")
    ap.add_argument("--strict", action="store_true", help="exit 1 if any Check A error or Check B finding exists")
    args = ap.parse_args(argv)

    rom = args.rom.read_bytes()
    report = scan_sheet_reveal_safety(rom)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(
            f"[*] Scanned {report['maps_scanned']} maps across {len(report['custom_sheets_found'])} custom sheets "
            f"({', '.join(report['custom_sheets_found'])}):"
        )
        print(f"    Check A (Transitive reveal-char corruption): {report['check_a_reveal_corruption_count']} findings")
        for f in report["check_a_findings"][:25]:
            print(
                f"      [{f['severity'].upper():5s}] map {f['map_id']}(p={f['parent_id']}) sheet {f['sheet']} "
                f"src {f['source_tile16']}(x{f['source_placements']}) -> rev {f['reveal_tile16']} "
                f"char {f['vram_char']}({f['local_char']}): {','.join(f['reasons'])} "
                f"{('collides=' + ','.join(f['colliding_scenery_tile16s'])) if f['colliding_scenery_tile16s'] else ''}"
            )
        print(f"    Check B (Slot-6 interactive TileType bleed): {report['check_b_slot6_bleed_count']} findings")
        for f in report["check_b_findings"][:25]:
            print(
                f"      [BLEED] map {f['map_id']}(p={f['parent_id']}) sheet {f['sheet']} "
                f"tile16 {f['tile16']}(x{f['placements']}) char {f['vram_char']}({f['local_char']}) "
                f"inherits interactive type {f['tile_type']}"
            )

    if args.strict:
        has_err = any(f["severity"] == "error" for f in report["check_a_findings"]) or bool(report["check_b_findings"])
        return 1 if has_err else 0
    return 0


if __name__ == "__main__":
    sys.exit(main())
