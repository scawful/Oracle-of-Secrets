#!/usr/bin/env python3
"""Generate or verify the 4bpp GBC Flying Rooster sprite sheet (Items/gfx/gbc_travel_bird.4bpp).

4 frames x 16x16 pixels (2x2 SNES 4bpp tiles per frame = 512 bytes total),
authored directly against the measured Eon Abyss SP1 CGRAM palette:
  0: transparent
  1: #FFFFFF (white primary plumage)
  2: #CD3110 (bright red comb / wattle)
  5: #292929 (charcoal outline & eye)
  6: #FFCD20 (gold beak & talons)
  7: #FF7331 (orange shaded beak & talons)
 11: #B42929 (crimson comb / tail shadow)
 12: #E67373 (coral comb / tail highlight)
 14: #BDBDCD (silver-grey wing / belly feather shading)
 15: #7B7B8B (slate-grey deep feather shadow)

Layout per frame (128 bytes):
  bytes   0.. 63 -> top row    ($0E, $0F -> VRAM $40E0, 64 bytes)
  bytes  64..127 -> bottom row ($1E, $1F -> VRAM $41E0, 64 bytes)
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_PATH = ROOT / "Items/gfx/gbc_travel_bird.4bpp"

PALETTE_LEGEND: dict[str, int] = {
    ".": 0,   # transparent
    "#": 5,   # #292929 charcoal outline / eye
    "W": 1,   # #FFFFFF white plumage
    "S": 14,  # #BDBDCD silver-grey feather highlight shade
    "G": 15,  # #7B7B8B slate-grey deep feather shade
    "C": 11,  # #B42929 crimson comb / tail tip
    "R": 2,   # #CD3110 bright red comb / wattle
    "P": 12,  # #E67373 coral highlight
    "Y": 6,   # #FFCD20 gold yellow beak / talons
    "O": 7,   # #FF7331 orange beak / talon shade
}

# Measured live Eon Abyss SP1 CGRAM RGB (for --preview verification only).
ABYSS_SP1_RGB: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 0),
    1: (255, 255, 255),
    2: (205, 49, 16),
    3: (123, 139, 49),
    4: (172, 189, 98),
    5: (41, 41, 41),
    6: (255, 205, 32),
    7: (255, 115, 49),
    8: (0, 0, 0),
    9: (255, 255, 255),
    10: (205, 90, 49),
    11: (180, 41, 41),
    12: (230, 115, 115),
    13: (41, 41, 41),
    14: (189, 189, 205),
    15: (123, 123, 139),
}

# 4 x 16x16 frames matching Ancilla27_Duck .vram_offset ($00/$01, $20, $40, $E0),
# facing right (.prop = $22, no H-flip).
FRAMES: list[tuple[str, list[str]]] = [
    (
        "Frame 0 ($00/$01): Wing Upstroke",
        [
            "........###.###.",
            "..####..#PR##R#.",
            ".#WWWS###PRR##..",
            ".#WSSSW##WWWW#..",
            "..#GSSSW#WW#W#Y#",
            ".##GGGWW#WWWWYY#",
            "#CR##WWWW###YYO#",
            "#CC#WWWWWS#RR#..",
            ".#W#WWSSSS##....",
            ".###WSSSSG#.....",
            "...##GGGG#......",
            "....#YY##YY#....",
            "....#OO..#O#....",
            ".....##...#.....",
            "................",
            "................",
        ],
    ),
    (
        "Frame 1 ($20): Wing Midstroke",
        [
            "........###.###.",
            "........#PR##R#.",
            "........#PRR##..",
            "....#####WWWW#..",
            "..##WWWW#WW#W#Y#",
            ".##GWWWW#WWWWYY#",
            "#CR#SSSSWW##YYO#",
            "#CC#SSGGGWS#R#..",
            ".#W#WWSSSS##....",
            ".###WSSSSG#.....",
            "...##GGGG#......",
            "....#YY##YY#....",
            "....#OO..#O#....",
            ".....##...#.....",
            "................",
            "................",
        ],
    ),
    (
        "Frame 2 ($40): Wing Downstroke",
        [
            "........###.###.",
            "........#PR##R#.",
            "........#PRR##..",
            "........#WWWW#..",
            "....#####WW#W#Y#",
            ".##WWWWWW#WWWYY#",
            "#CR#WWWWW###YYO#",
            "#CC#WWSSGWW#R#..",
            ".#W#WWSSSGG#....",
            ".###W#SSGG#.....",
            "...#.#GG##......",
            ".....#YY#YY#....",
            ".....#OO.#O#....",
            "......##..#.....",
            "................",
            "................",
        ],
    ),
    (
        "Frame 3 ($E0): Carry / Dropoff Glide",
        [
            "........###.###.",
            "..####..#PR##R#.",
            ".#WWWS###PRR##..",
            ".#WSSSW##WWWW#..",
            "..#GSSSW#WW#W#Y#",
            ".##GGGWW#WWWWYY#",
            "#CR##WWWW###YYO#",
            "#CC#WWWWWS#RR#..",
            ".#W#WWSSSS##....",
            ".###WWSSSG#.....",
            "...###GGG#......",
            "....#YY#YY#.....",
            "....#OO##OO#....",
            ".....##..##.....",
            "................",
            "................",
        ],
    ),
]


def _encode_tile(grid: list[list[int]], tx: int, ty: int) -> bytes:
    """Encode an 8x8 tile at (tx*8, ty*8) in SNES 4bpp planar format (32 bytes)."""
    out = bytearray(32)
    x0, y0 = tx * 8, ty * 8
    for row in range(8):
        p0 = p1 = p2 = p3 = 0
        for col in range(8):
            c = grid[y0 + row][x0 + col]
            bit = 7 - col
            p0 |= ((c >> 0) & 1) << bit
            p1 |= ((c >> 1) & 1) << bit
            p2 |= ((c >> 2) & 1) << bit
            p3 |= ((c >> 3) & 1) << bit
        out[row * 2] = p0
        out[row * 2 + 1] = p1
        out[16 + row * 2] = p2
        out[16 + row * 2 + 1] = p3
    return bytes(out)


def build_bytes() -> bytes:
    buf = bytearray()
    for name, rows in FRAMES:
        if len(rows) != 16:
            raise ValueError(f"{name}: expected 16 rows, got {len(rows)}")
        grid: list[list[int]] = []
        for r_idx, row in enumerate(rows):
            if len(row) != 16:
                raise ValueError(f"{name} row {r_idx}: expected width 16, got {len(row)}")
            grid.append([PALETTE_LEGEND[ch] for ch in row])
        # Row-major 2x2 tiles matching VRAM $40E0 ($0E, $0F) then VRAM $41E0 ($1E, $1F).
        for ty in (0, 1):
            for tx in (0, 1):
                buf.extend(_encode_tile(grid, tx, ty))
    return bytes(buf)


def write_preview(out_png: Path) -> None:
    from PIL import Image, ImageDraw

    scale = 10
    pad = 12
    cell = 16 * scale
    w = len(FRAMES) * (cell + pad) + pad
    h = cell * 2 + pad * 3 + 24
    img = Image.new("RGB", (w, h), (26, 22, 34))
    draw = ImageDraw.Draw(img)
    backdrops = [
        (42, 34, 62),    # Abyss twilight purple backdrop
        (96, 128, 72),   # Abyss moss/ground backdrop
    ]
    for idx, (name, rows) in enumerate(FRAMES):
        x0 = pad + idx * (cell + pad)
        draw.text((x0, 4), f"F{idx}", fill=(230, 230, 240))
        for b_idx, bg in enumerate(backdrops):
            y0 = 22 + b_idx * (cell + pad)
            draw.rectangle([x0, y0, x0 + cell - 1, y0 + cell - 1], fill=bg)
            for r in range(16):
                for c in range(16):
                    ci = PALETTE_LEGEND[rows[r][c]]
                    if ci == 0:
                        continue
                    rgb = ABYSS_SP1_RGB[ci]
                    draw.rectangle(
                        [x0 + c * scale, y0 + r * scale,
                         x0 + (c + 1) * scale - 1, y0 + (r + 1) * scale - 1],
                        fill=rgb,
                    )
    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--check", action="store_true", help="Verify checked-in .4bpp matches generated bytes")
    ap.add_argument("--preview", type=Path, help="Optional PNG path to render scaled preview frames")
    args = ap.parse_args()

    data = build_bytes()
    if args.preview:
        write_preview(args.preview)

    if args.check:
        if not OUT_PATH.exists():
            print(f"MISSING {OUT_PATH}", file=sys.stderr)
            return 1
        cur = OUT_PATH.read_bytes()
        if cur != data:
            print(f"MISMATCH {OUT_PATH} ({len(cur)} vs {len(data)} bytes)", file=sys.stderr)
            return 1
        print(f"OK {OUT_PATH} ({len(data)} bytes)")
        return 0

    OUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUT_PATH.write_bytes(data)
    print(f"Wrote {OUT_PATH} ({len(data)} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
