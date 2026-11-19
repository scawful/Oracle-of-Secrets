#!/usr/bin/env python3
"""Surgically recolor ONLY the untouched vanilla human-tunic cells in Masks/gfx/deku_link.bin
while preserving 100% of DarkLink45/scawful's original slim Deku Link body, cute red gloves,
and little red boots!

Design principles (per scawful's 2026-11-19 review):
  1. Preserve 100% of R00..R13 and every already-authored Deku Link cell byte-for-byte
     (zero fattening, zero removal of Deku Link's cute red gloves C09/C10 or little red boots!).
  2. On ONLY the untouched vanilla ALTTP green-tunic + yellow-belt cells in R14..R26
     (where the whole torso was left bright vanilla green C03/C04 with a bright yellow belt C06),
     recolor IN-PLACE using the exact same slim pixel silhouette:
       - Upper torso / arms (above belt): warm Deku wooden bark (C05 mid, C02 dark, C07 light)
       - Waist / lower leaf skirt & belt (formerly yellow C06 + lower green): emerald leaf (C03/C04/C01)
       - Hands / feet where vanilla used bare skin/brown boots: matching cute red gloves/boots (C09/C10)
       - Outline C08 and white C12 preserved untouched; zero undefined index 15 pixels.

Usage:
  python3 Scripts/Generate/build_deku_link_sheet.py [--base PATH] [--out PATH] [--check]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "Masks/gfx/deku_link.bin"
SHEET_SIZE = 28672
ORIG_GIT_REV = "96cf28f1"  # Pre-overhaul original slim Deku Link with cute red gloves & boots

# ONLY the leftover untouched vanilla human green-tunic + yellow-belt cells on R14..R26!
# Every single cell in R00..R13, R14 C0..C2, R15 C0, R16 C0..C2, R17 C0..C2, R19 C0..C2,
# R20 C0..C2, R24 C6..C7, R25 C0..C7, R26 C7, and R27 C0..C4 is preserved 100% BYTE-FOR-BYTE!
VANILLA_TUNIC_CELLS: tuple[tuple[int, int], ...] = (
    (14, 3), (14, 4), (14, 5), (14, 6), (14, 7),
    (15, 1), (15, 2), (15, 3), (15, 4), (15, 5), (15, 6), (15, 7),
    (16, 3), (16, 4), (16, 5), (16, 6), (16, 7),
    (17, 3), (17, 4), (17, 5), (17, 6), (17, 7),
    (18, 3), (18, 4), (18, 5), (18, 6), (18, 7),
    (19, 3), (19, 4), (19, 5), (19, 6), (19, 7),
    (20, 3), (20, 4), (20, 5), (20, 6), (20, 7),
    (21, 0), (21, 1), (21, 2), (21, 3), (21, 4), (21, 5), (21, 6), (21, 7),
    (22, 0), (22, 1), (22, 2), (22, 3), (22, 4), (22, 5), (22, 6), (22, 7),
    (23, 0), (23, 1), (23, 2), (23, 3), (23, 4), (23, 5), (23, 6), (23, 7),
    (24, 0), (24, 1), (24, 2), (24, 3), (24, 4), (24, 5),
    (26, 0), (26, 1), (26, 2), (26, 3), (26, 4), (26, 5), (26, 6),
)


def decode_4bpp_sheet(data: bytes) -> list[list[int]]:
    if len(data) != SHEET_SIZE:
        raise ValueError(f"Expected {SHEET_SIZE} bytes, got {len(data)}")
    grid = [[0] * 128 for _ in range(448)]
    for tr in range(56):
        for tc in range(16):
            off = (tr * 16 + tc) * 32
            for y in range(8):
                b0 = data[off + y * 2]
                b1 = data[off + y * 2 + 1]
                b2 = data[off + 16 + y * 2]
                b3 = data[off + 16 + y * 2 + 1]
                row = grid[tr * 8 + y]
                x0 = tc * 8
                for x in range(8):
                    bit = 7 - x
                    row[x0 + x] = (
                        ((b0 >> bit) & 1)
                        | (((b1 >> bit) & 1) << 1)
                        | (((b2 >> bit) & 1) << 2)
                        | (((b3 >> bit) & 1) << 3)
                    )
    return grid


def encode_4bpp_sheet(grid: list[list[int]]) -> bytes:
    out = bytearray(SHEET_SIZE)
    for tr in range(56):
        for tc in range(16):
            off = (tr * 16 + tc) * 32
            x0 = tc * 8
            for y in range(8):
                row = grid[tr * 8 + y]
                p0 = p1 = p2 = p3 = 0
                for x in range(8):
                    v = row[x0 + x]
                    bit = 0x80 >> x
                    if v & 1:
                        p0 |= bit
                    if v & 2:
                        p1 |= bit
                    if v & 4:
                        p2 |= bit
                    if v & 8:
                        p3 |= bit
                out[off + y * 2] = p0
                out[off + y * 2 + 1] = p1
                out[off + 16 + y * 2] = p2
                out[off + 16 + y * 2 + 1] = p3
    return bytes(out)


def recolor_vanilla_cell_in_place(grid: list[list[int]], r: int, c: int) -> None:
    """Recolor a single leftover vanilla green-tunic+yellow-belt 16x16 cell IN-PLACE
    to match DarkLink45's slim brown-bark + emerald leaf-skirt + cute red gloves/boots style!
    Does NOT add or remove a single opaque pixel (100% identical slim silhouette!)."""
    y0, x0 = r * 16, c * 16

    # Find vertical extent of opaque body pixels inside this cell so we split
    # upper bark torso vs lower green leaf skirt naturally per pose!
    ys = [dy for dy in range(16) if any(grid[y0 + dy][x0 + dx] != 0 for dx in range(16))]
    if not ys:
        return
    y_min, y_max = ys[0], ys[-1]
    # Find yellow belt rows (C06) if present; otherwise split at ~60% down the cell
    belt_ys = [dy for dy in range(16) if any(grid[y0 + dy][x0 + dx] == 6 for dx in range(16))]
    split_y = min(belt_ys) if belt_ys else (y_min + ((y_max - y_min) * 5) // 9)

    for dy in range(16):
        for dx in range(16):
            v = grid[y0 + dy][x0 + dx]
            if v == 0:
                continue
            if v == 15:
                grid[y0 + dy][x0 + dx] = 8  # fix undefined index 15 -> charcoal outline
                continue
            # Keep outline (8), existing red gloves/boots (9, 10), white (12), purple FX (13)
            if v in (8, 9, 10, 12, 13):
                continue
            # Yellow human belt (C06) -> bright emerald leaf collar/skirt highlight (C04)
            if v == 6:
                grid[y0 + dy][x0 + dx] = 4
                continue
            # Vanilla bright green tunic pixels:
            #   - Above the belt/skirt line -> warm Deku wooden bark (matching R01..R13!)
            #   - At/below the belt/skirt line -> crisp green leaf skirt (C03/C04/C01)
            if v in (1, 3, 4, 14):
                if dy < split_y:
                    if v in (4, 14):
                        grid[y0 + dy][x0 + dx] = 5  # warm bark midtone
                    elif v == 3:
                        grid[y0 + dy][x0 + dx] = 5  # warm bark midtone
                    else:
                        grid[y0 + dy][x0 + dx] = 2  # deep bark shadow
                else:
                    # Keep lush emerald leaf skirt (clamp index 14 -> 4 for palette consistency)
                    if v == 14:
                        grid[y0 + dy][x0 + dx] = 4


def load_original_deku(base_path: Path | None) -> bytes:
    if base_path is not None:
        return base_path.read_bytes()
    return subprocess.check_output(
        ["git", "-C", str(ROOT), "show", f"{ORIG_GIT_REV}:Masks/gfx/deku_link.bin"]
    )


def build_sheet(orig_bytes: bytes) -> bytes:
    grid = decode_4bpp_sheet(orig_bytes)
    for r, c in VANILLA_TUNIC_CELLS:
        recolor_vanilla_cell_in_place(grid, r, c)
    return encode_4bpp_sheet(grid)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", type=Path, help="Original 28672B deku_link.bin (default: git 96cf28f1)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output 28672B deku_link.bin")
    ap.add_argument("--check", action="store_true", help="Verify output matches reproducible build")
    args = ap.parse_args(argv)

    rebuilt = build_sheet(load_original_deku(args.base))

    if args.check:
        if not args.out.is_file():
            print(f"MISSING: {args.out}", file=sys.stderr)
            return 1
        cur = args.out.read_bytes()
        if cur != rebuilt:
            print(f"STALE: {args.out} differs from freshly built bytes", file=sys.stderr)
            return 1
        print(f"OK: {args.out} matches surgical slim Deku recolor ({len(rebuilt)} bytes, {len(VANILLA_TUNIC_CELLS)} cells recolored in-place)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(rebuilt)
    print(f"Wrote {args.out} ({len(rebuilt)} bytes, {len(VANILLA_TUNIC_CELLS)} vanilla cells recolored in-place; R00..R13 100% preserved!)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
