#!/usr/bin/env python3
"""Deterministic King of Red Lions V3 sparse 4BPP art & palette packer.

Builds sleek 16-bit Wind Waker King of Red Lions pixel art matched to
Oracle of Secrets' 16x24 Minish Cap Link (`Data/graphics/link/mc_link_sheet.4bpp`):
  - Side hull (56x28): long, graceful crimson wooden skiff with curved sheer,
    crisp ivory gunwale trim, scrolled gold stern rudder/tiller, compact regal
    King of Red Lions dragon figurehead (13x14 px), and seated MC Link aft.
  - Down / Up hulls (24x42): sleek tapered wooden skiff (20px midship beam,
    39px hull length) with sculpted wooden interior thwarts, proportionate
    carved dragon prow, and centered cockpit.
  - Always-hoisted Wind Waker Sail while riding (`HasSail = 1` on all 12 mounted
    frames): trimmer calm-breeze sail for Cruise (frames 0..5) vs full wind-filled
    billowing forward-leaning sail + crisp white bow wave/wake foam for Sail Boost
    (frames 6..11). Empty moored boat (`KORL_Mounted == 0`) renders hull-only
    frames 0..5 with sail stowed.

Hardware / VBlank Design (inherits Epona's zero-overrun sparse NMI architecture):
  - SP-3[9..15] (7 BGR555 colors in korl_palette.bin) draws the crimson hull,
    ivory/gold dragon figurehead, emerald-teal mast & Wind Waker sail spiral.
    Colors 1..8 of SP-3 remain untouched; Day/Night tinting applies cleanly.
  - SP-7 (Link's own worn Green/Blue/Red Mail palette) draws seated MC Link
    inside the cockpit (16x16 CHR $08, deduplicated across same-dir frames).
  - Dropable-safe Page 0 VRAM slots ($4000-$43FF):
      $4000/$4100 (CHR $00,$02,$04,$06): 4 x 16x16 Boat Hull + Figurehead (512 B)
      $4080/$4180 (CHR $08):             1 x 16x16 Seated MC Link Rider   (128 B)
      $42A0/$43A0 (CHR $2A):             1 x 16x16 Wind Waker Sail A      (128 B)
      $42C0/$43C0 (CHR $2C):             1 x 16x16 Wind Waker Sail B      (128 B)
      $40A0/$41A0 (CHR $0A/$1A):         1 x 8x16  Wind Waker Sail Wing   ( 64 B)
    Protected dropables ($0B/$1B Rupee, $0E/$0F Receipt/Bird, $20-$25 Follower/P2,
    $26 Boomerang, $28-$29 Shadow/Heart, $2E-$2F Bombchu) are NEVER touched!
  - Absolute worst-case NMI DMA = 512 + 128 + 320 = 960 bytes (<= 960 B budget).
    Steady same-dir bob/billow or cruise<->boost = 832 B; idle steady = 0 B.
    Docked Page 1 ($5C00/$5D00) backup stays exact 512 B (4 x 16x16 empty hull).

Usage:
  python3 Scripts/Generate/build_korl_art.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys
from typing import Sequence

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MC_SHEET = ROOT / "Data/graphics/link/mc_link_sheet.4bpp"
OUT_DIR = ROOT / "Data/graphics/mounts"
OUT_4BPP = OUT_DIR / "korl_sparse.4bpp"
OUT_TABLES = OUT_DIR / "korl_sparse_tables.asm"
OUT_PAL = OUT_DIR / "korl_palette.bin"

# ---------------------------------------------------------------------------
# Palette definitions (14 bytes = 7 BGR555 colors for SP-3[9..15])
# ---------------------------------------------------------------------------
# Index 15 ($3A86 Wind Waker sea-emerald) is distinct from LW uniform $14A5,
# Epona $239F, and SW/DW palettes (e.g. Goron Coast $B0 $0240) for reliable
# cross-world Day/Night palette refresh.
KORL_SP3_RGB: dict[int, tuple[int, int, int]] = {
    9:  ( 64,  24,  24),  # #401818 deep mahogany-crimson outline (crisp on ocean)
    10: (152,  40,  32),  # #982820 rich crimson wood shade / inner cockpit deck
    11: (224,  56,  32),  # #E03820 vivid King of Red Lions crimson hull
    12: (240, 192,  48),  # #F0C030 warm gold horns / rudder / tiller / sail boom
    13: (248, 248, 240),  # #F8F8F0 warm ivory-white gunwale / figurehead / sail
    14: (176, 184, 192),  # #B0B8C0 luminous silver-gray sail shade / wake mist
    15: ( 48, 160, 112),  # #30A070 Wind Waker emerald-teal mast & spiral crest
}

# Link's exact Green/Blue/Red Mail SP-7 palettes (from ROM $1BD308) for previews.
LINK_SP7_GREEN_RGB: dict[int, tuple[int, int, int]] = {
    1:  (248, 248, 248),  # eye white
    2:  (224, 224,   0),  # belt/trim yellow
    3:  (208, 176, 136),  # skin shade
    4:  (248, 224, 184),  # skin light
    5:  ( 40,  40,  40),  # outline charcoal
    6:  (216, 168,  80),  # hair blond
    7:  (192,  24,  32),  # red accent
    8:  ( 48,  80, 248),  # eye blue
    9:  (  0,  72,  24),  # tunic dark outline
    10: ( 96, 224,  40),  # tunic highlight
    11: ( 48, 128,  24),  # tunic mid-dark
    12: (  0, 192,   0),  # tunic bright
    13: (160, 120,  64),  # hair/belt warm brown
    14: (136,  88,  40),  # sleeve/hair dark brown
}

LINK_SP7_BLUE_RGB = {
    **LINK_SP7_GREEN_RGB,
    9: (0, 0, 128), 10: (0, 128, 192), 11: (0, 64, 128), 12: (0, 128, 248),
}
LINK_SP7_RED_RGB = {
    **LINK_SP7_GREEN_RGB,
    9: (160, 0, 0), 10: (248, 128, 128), 11: (184, 0, 0), 12: (248, 56, 56),
}

SP3_LEGEND: dict[str, int] = {
    ".": 0,   # transparent
    "k": 9,   # deep mahogany-crimson outline
    "d": 10,  # dark crimson wood plank shade / inner deck
    "r": 11,  # vivid King of Red Lions crimson
    "g": 12,  # warm gold horns / rudder / tiller / boom
    "w": 13,  # crisp warm ivory-white gunwale / dragon / sail / foam
    "s": 14,  # cool silver-gray shading / wake mist
    "t": 15,  # Wind Waker emerald-teal mast & spiral crest
}

Grid = list[list[int]]


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def build_palette_bytes() -> bytes:
    words = [rgb_to_bgr555(*KORL_SP3_RGB[i]) for i in range(9, 16)]
    return b"".join(struct.pack("<H", w) for w in words)


def new_grid(w: int, h: int, fill: int = 0) -> Grid:
    return [[fill] * w for _ in range(h)]


def parse_art(rows: Sequence[str], expected_w: int, expected_h: int) -> Grid:
    assert len(rows) == expected_h, f"Expected {expected_h} rows, got {len(rows)}"
    out: Grid = []
    for r_idx, row in enumerate(rows):
        assert len(row) == expected_w, f"Row {r_idx}: expected {expected_w} cols, got {len(row)}"
        out.append([SP3_LEGEND[ch] for ch in row])
    return out


def clone_grid(g: Grid) -> Grid:
    return [list(r) for r in g]


def blit(dst: Grid, src: Grid, dx: int, dy: int, *, transparent: int = 0) -> None:
    dh, dw = len(dst), len(dst[0])
    sh, sw = len(src), len(src[0])
    for y in range(sh):
        ty = dy + y
        if not (0 <= ty < dh):
            continue
        row_s = src[y]
        row_d = dst[ty]
        for x in range(sw):
            v = row_s[x]
            if v != transparent:
                tx = dx + x
                if 0 <= tx < dw:
                    row_d[tx] = v


def shift_grid(g: Grid, dx: int, dy: int) -> Grid:
    h, w = len(g), len(g[0])
    out = new_grid(w, h)
    blit(out, g, dx, dy)
    return out


def paint_pixels(g: Grid, pts: Sequence[tuple[int, int, str]]) -> Grid:
    out = clone_grid(g)
    h, w = len(out), len(out[0])
    for x, y, ch in pts:
        if 0 <= y < h and 0 <= x < w:
            out[y][x] = SP3_LEGEND[ch]
    return out


def paint_spans(g: Grid, y_row: int, segments: Sequence[tuple[int, int, str]]) -> Grid:
    out = clone_grid(g)
    h, w = len(out), len(out[0])
    if 0 <= y_row < h:
        for x0, x1, ch in segments:
            col = SP3_LEGEND[ch]
            for x in range(max(0, x0), min(w, x1)):
                out[y_row][x] = col
    return out


# ---------------------------------------------------------------------------
# Bespoke 16-bit Wind Waker King of Red Lions Hull Art
# ---------------------------------------------------------------------------

# SIDE HULL (56 x 28, Right-facing; hardware H-flipped for Left):
#   Tile windows: (0,12), (16,12), (32,12), (40,0) -> exact 4 x 16x16 = 512 B!
#   - Rows 0..12 in x=0..39 are empty so -1px wave-bob NEVER clips at y=12.
#   - Rows 16..27 in x=48..55 are empty (open water under overhanging dragon jaw).
#   - Curved wooden skiff sheer: rises gently at stern (y=13..15) and bow (y=13..15),
#     dips smoothly midship (y=16..17), with warm crimson planks & curved rocker keel!
#   - Regal King of Red Lions figurehead (x=42..55, y=2..15 = 14w x 14h): curved
#     golden crown horns, crimson mane crest, sculpted squared lion snout & beard.
SIDE_HULL_BASE = [
    # 0         1         2         3         4         5
    # 01234567890123456789012345678901234567890123456789012345
    "........................................................",  # 00 (bob headroom)
    "........................................................",  # 01
    "..........................................kk............",  # 02 swept gold horn tip
    ".........................................kggkk..........",  # 03 curved crown horn
    "..........................................kgggk.........",  # 04
    "...........................................kggwkk.......",  # 05 horn meets proud brow
    "..........................................krrwwwwkk.....",  # 06 crimson crest + ivory brow
    ".........................................krrkwkgwwkk....",  # 07 fierce gold eye + bridge
    ".........................................krrkwwgwwwwk...",  # 08 sculpted squared lion snout
    "..........................................krkwwwwwkgk...",  # 09 golden nose tip + muzzle
    "..........................................krrwwssddwk...",  # 10 warm crimson smile crease
    "..........................................krrwwwswwwk...",  # 11 flowing white lion beard
    ".........................................krrrrwwwssk....",  # 12 crimson neck + mane collar
    "....kkk.................................krrrrrwwsk......",  # 13 curved stern peak + rising bow
    "...kggwk..kkk.........................kkrrdddwwk........",  # 14 stern gold trim + tiller + bow sheer
    "...kwwwkkkdddkkkkkkkkkkkkkkkkkkkkkkkkkddddwwwwk.........",  # 15 curved far rim + sweeping bow rim
    "....kwwwwwwwddddddddddddddddddddddddwwwwwwssrk..........",  # 16 graceful curved ivory gunwale!
    ".....ksssssswwwwwwwwwwwwwwwwwwwwwwwwsssssrrrrk..........",  # 17 midship sheer dip + gunwale bevel
    ".....krrrrrrssssssssssssssssssssssssrrrrrrrrrk..........",  # 18 bright crimson upper strake
    "....kkrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrk...........",  # 19 sculpted wooden hull side
    "..kkggkrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrrk...........",  # 20 curled gold stern scroll
    ".kggggkkrrrddrrrrrrrrrrrrrrrrrrrrrrrrddrrrrk............",  # 21 subtle plank shading
    ".kgggkk.krrrrddddddddddddddddddddddddrrrrrk.............",  # 22 curved lower hull belly
    "..kkkk..kddddddddddddddddddddddddddddddddk..............",  # 23 deep keel shade
    ".........kkddddddddddddddddddddddddddddkk...............",  # 24 gentle curved rocker keel
    "...........kkkkkkkkkkkkkkkkkkkkkkkkkkkk.................",  # 25 sleek waterline keel
    "........................................................",  # 26 waterline foam row
    "........................................................",  # 27 waterline wake row
]


def build_side_hulls() -> dict[str, Grid]:
    base = parse_art(SIDE_HULL_BASE, 56, 28)

    # Calm Cruise A / B (also used for calm moored empty boat!)
    cruise_a = paint_spans(base, 26, [(11, 18, "s"), (22, 31, "w"), (35, 41, "s")])
    cruise_b = shift_grid(base, 0, -1)
    cruise_b = paint_spans(cruise_b, 25, [(10, 17, "w"), (21, 29, "s"), (34, 42, "w")])
    cruise_b = paint_spans(cruise_b, 26, [(13, 21, "s"), (28, 36, "s")])

    # Sail Boost A / B: crisp white curling bow-wave plume + lively ocean wake foam!
    boost_a = clone_grid(base)
    boost_a = paint_spans(boost_a, 25, [(4, 10, "s"), (38, 46, "w")])
    boost_a = paint_spans(boost_a, 26, [(0, 6, "w"), (9, 20, "w"), (24, 35, "s"), (37, 47, "w")])
    boost_a = paint_spans(boost_a, 27, [(5, 14, "s"), (18, 29, "w"), (34, 45, "s")])
    boost_a = paint_pixels(boost_a, [
        # Curling bow-wave plume slicing water at prow (x=41..47, y=21..25)
        (45, 21, "w"), (46, 21, "s"),
        (44, 22, "w"), (45, 22, "w"), (46, 22, "w"), (47, 22, "s"),
        (42, 23, "s"), (43, 23, "w"), (44, 23, "w"), (45, 23, "w"), (46, 23, "w"),
        (41, 24, "w"), (42, 24, "w"), (43, 24, "w"), (44, 24, "w"), (45, 24, "w"), (46, 24, "s"),
        (46, 25, "w"), (47, 25, "s"),
        # Trailing stern wake flick
        (2, 24, "w"), (3, 24, "s"), (4, 25, "w"),
    ])

    boost_b = shift_grid(base, 0, -1)
    boost_b = paint_spans(boost_b, 24, [(4, 10, "w"), (39, 46, "w")])
    boost_b = paint_spans(boost_b, 25, [(1, 12, "s"), (16, 27, "w"), (32, 47, "w")])
    boost_b = paint_spans(boost_b, 26, [(0, 6, "s"), (9, 22, "w"), (26, 38, "s"), (40, 46, "w")])
    boost_b = paint_spans(boost_b, 27, [(7, 17, "s"), (23, 33, "w")])
    boost_b = paint_pixels(boost_b, [
        # Animated surging bow wave (+1px crest!)
        (46, 19, "w"),
        (45, 20, "w"), (46, 20, "w"), (47, 20, "s"),
        (44, 21, "s"), (45, 21, "w"), (46, 21, "w"), (47, 21, "w"),
        (42, 22, "w"), (43, 22, "w"), (44, 22, "w"), (45, 22, "w"), (46, 22, "s"),
        (41, 23, "s"), (42, 23, "w"), (43, 23, "w"), (44, 23, "w"), (45, 23, "w"),
        (1, 23, "w"), (2, 24, "w"), (3, 24, "s"),
    ])

    return {
        "cruise_a": cruise_a,
        "cruise_b": cruise_b,
        "boost_a": boost_a,
        "boost_b": boost_b,
    }


# DOWN HULL (24 x 42, facing South):
#   Tile windows: (4,0), (0,13), (8,13), (4,26) -> exact 4 x 16x16 = 512 B!
#   - Rows 0..13 and 29..41 stay strictly inside x=4..19 (zero clip on -1px bob!).
#   - Sculpted wooden cockpit with cross-thwart benches & mast step socket!
#   - Regal symmetrical King of Red Lions front figurehead (y=26..39): curved twin
#     gold horns, crimson crown crest, sculpted white lion muzzle & bright gold eyes.
DOWN_HULL_BASE = [
    # 0         1         2
    # 012345678901234567890123
    "........................",  # 00 (bob headroom)
    "........................",  # 01
    "..........kkkk..........",  # 02 stern tip
    ".........kggggk.........",  # 03 gold stern scroll/rudder
    "........kkwwwwkk........",  # 04 curved ivory stern rim
    ".......kwwrrrrwwk.......",  # 05 stern bench highlight
    "......kwwddddddwwk......",  # 06 rear cockpit shadow
    ".....kwwddkkkkddwwk.....",  # 07 stern seating thwart edge
    ".....kwddrrrrrrddwk.....",  # 08 wooden stern bench
    "....krwddrrrrrrddwrk....",  # 09
    "....krwddddddddddwrk....",  # 10 cockpit floor
    "....krwdddkkkkdddwrk....",  # 11 subtle floor plank depth
    "....krwddddddddddwrk....",  # 12
    "....krwddddddddddwrk....",  # 13 (stays in x=4..19 for -1 bob)
    "...krrwddddddddddwrrk...",  # 14 smooth flare to 18px
    "..krrswddddddddddwsrrk..",  # 15 graceful 20px midship beam
    "..krrswddrrrrrrddwsrrk..",  # 16 midship seating bench
    "..krrswddrrrrrrddwsrrk..",  # 17
    "..krrswddkkkkkkddwsrrk..",  # 18 bench shadow
    "..krrswddddddddddwsrrk..",  # 19
    "..krrswddddddddddwsrrk..",  # 20
    "..krrswddrrrrrrddwsrrk..",  # 21 forward mast-step thwart!
    "..krrswddrrkkrrddwsrrk..",  # 22 center mast step socket
    "..krrswddkkkkkkddwsrrk..",  # 23 forward deck beam
    "...krrwddddddddddwrrk...",  # 24 smooth taper toward bow
    "...krrwddrrrrrrddwrrk...",  # 25 forward bow deck
    "....kggkrrrrrrrrkggk....",  # 26 curved twin gold horn tips
    "....kggkrkrrrrkrkggk....",  # 27 gold horns + crimson crown crest
    ".....kggkwwrrwwkggk.....",  # 28 horns curving into lion brow
    ".....kkwwwwrrwwwwkk.....",  # 29 sculpted lion brow + crest
    "......kwwkwwwwkwwk......",  # 30 fierce brow ridge
    "......kwkgwwwwgkwk......",  # 31 bright golden lion eyes
    "......kswwkwwkwwsk......",  # 32 carved nose bridge
    "......kwwwwggwwwwk......",  # 33 regal squared lion snout + gold nose
    ".......kwwkddkwwk.......",  # 34 warm crimson smile crease
    ".......ksswwwwssk.......",  # 35 white lion chin beard
    "........kwwsswwk........",  # 36 tapered lion beard tip
    "........krrrrrrk........",  # 37 crimson prow stem
    ".........kddddk.........",  # 38 waterline prow keel
    "..........kkkk..........",  # 39 pointed bow tip
    "........................",  # 40 water ripple row
    "........................",  # 41 water wake row
]


def build_down_hulls() -> dict[str, Grid]:
    base = parse_art(DOWN_HULL_BASE, 24, 42)

    cruise_a = paint_spans(base, 40, [(7, 10, "w"), (14, 17, "w")])
    cruise_a = paint_spans(cruise_a, 41, [(9, 15, "s")])

    cruise_b = shift_grid(base, 0, -1)
    cruise_b = paint_spans(cruise_b, 39, [(6, 9, "s"), (15, 18, "s")])
    cruise_b = paint_spans(cruise_b, 40, [(8, 16, "w")])

    # Boost A / B: dynamic V-shaped bow-wave spray curling around the dragon prow!
    boost_a = clone_grid(base)
    boost_a = paint_pixels(boost_a, [
        (5, 34, "s"), (6, 35, "w"), (5, 36, "w"), (6, 36, "w"), (5, 37, "s"),
        (6, 37, "w"), (7, 37, "w"), (6, 38, "w"), (7, 38, "w"), (8, 38, "w"),
        (7, 39, "w"), (8, 39, "w"), (9, 39, "w"),
        (18, 34, "s"), (17, 35, "w"), (18, 36, "w"), (17, 36, "w"), (18, 37, "s"),
        (17, 37, "w"), (16, 37, "w"), (17, 38, "w"), (16, 38, "w"), (15, 38, "w"),
        (16, 39, "w"), (15, 39, "w"), (14, 39, "w"),
    ])
    boost_a = paint_spans(boost_a, 40, [(6, 18, "w")])
    boost_a = paint_spans(boost_a, 41, [(8, 16, "s")])

    boost_b = shift_grid(base, 0, -1)
    boost_b = paint_pixels(boost_b, [
        (4, 33, "w"), (5, 34, "w"), (6, 34, "w"), (5, 35, "s"), (6, 35, "w"),
        (5, 36, "w"), (6, 36, "w"), (7, 36, "w"), (6, 37, "w"), (7, 37, "w"),
        (8, 37, "w"), (7, 38, "w"), (8, 38, "w"), (9, 38, "s"),
        (19, 33, "w"), (18, 34, "w"), (17, 34, "w"), (18, 35, "s"), (17, 35, "w"),
        (18, 36, "w"), (17, 36, "w"), (16, 36, "w"), (17, 37, "w"), (16, 37, "w"),
        (15, 37, "w"), (16, 38, "w"), (15, 38, "w"), (14, 38, "s"),
    ])
    boost_b = paint_spans(boost_b, 39, [(6, 18, "w")])
    boost_b = paint_spans(boost_b, 40, [(7, 17, "s")])
    boost_b = paint_spans(boost_b, 41, [(9, 15, "w")])

    return {
        "cruise_a": cruise_a,
        "cruise_b": cruise_b,
        "boost_a": boost_a,
        "boost_b": boost_b,
    }


# UP HULL (24 x 42, facing North):
#   Tile windows: (4,0), (0,13), (8,13), (4,26) -> exact 4 x 16x16 = 512 B!
#   - Compact sculpted dragon figurehead pointing North (y=2..14) with curved twin
#     gold horns & crimson dorsal mane crest.
#   - Sleek tapered skiff with wooden interior benches & curved stern gold rudder.
UP_HULL_BASE = [
    # 0         1         2
    # 012345678901234567890123
    "........................",  # 00 (bob headroom)
    "........................",  # 01
    "..........kkkk..........",  # 02 north dragon snout tip
    ".........kwwwwk.........",  # 03 symmetric sculpted ivory snout
    "........kwwwwwwk........",  # 04
    "....kk..kwwrrwwk..kk....",  # 05 outward-curving gold horn tips
    "....kggkwwwrrwwwkggk....",  # 06 twin curved gold horns + crimson crest
    "....kggkwwsrrswwkggk....",  # 07
    ".....kggkwwrrwwkggk.....",  # 08 horns join dragon brow
    "......kkkwwrrwwkkk......",  # 09
    "......krrwwrrwwrrk......",  # 10 crimson neck & mane crest
    ".....krrrwwwwwwrrrk.....",  # 11 ivory bow collar
    ".....krrwddrrddwrrk.....",  # 12 forward bow deck
    "....krrwddddddddwrrk....",  # 13 (stays in x=4..19 for -1 bob)
    "...krrwddrrrrrrddwrrk...",  # 14 forward mast-step thwart
    "..krrswddrrkkrrddwsrrk..",  # 15 center mast socket (20px beam)
    "..krrswddkkkkkkddwsrrk..",  # 16
    "..krrswddddddddddwsrrk..",  # 17 cockpit floor
    "..krrswddddddddddwsrrk..",  # 18
    "..krrswddrrrrrrddwsrrk..",  # 19 midship seating bench
    "..krrswddrrrrrrddwsrrk..",  # 20
    "..krrswddkkkkkkddwsrrk..",  # 21
    "..krrswddddddddddwsrrk..",  # 22
    "..krrswddddddddddwsrrk..",  # 23
    "..krrswddrrrrrrddwsrrk..",  # 24 rear seating bench
    "...krrwddrrrrrrddwrrk...",  # 25 smooth aft taper
    "...krrwddkkkkkkddwrrk...",  # 26
    "....krwddddddddddwrk....",  # 27
    "....krwddddddddddwrk....",  # 28
    "....krwddrrrrrrddwrk....",  # 29 stern shelf
    ".....kwddddddddddwk.....",  # 30
    ".....kwwddddddddwwk.....",  # 31 rear cockpit rail
    "......kwwrrrrrrwwk......",  # 32
    "......krrwwwwwwrrk......",  # 33 curved ivory stern transom
    ".......krrrrrrrrk.......",  # 34 crimson stern hull
    ".......kddddddddk.......",  # 35 waterline stern shade
    "........kkggggkk........",  # 36 scrolled golden rudder base
    ".........kggggk.........",  # 37 golden rudder fin
    "..........kggk..........",  # 38 rudder tip
    "..........kkkk..........",  # 39
    "........................",  # 40 wake row
    "........................",  # 41 wake row
]


def build_up_hulls() -> dict[str, Grid]:
    base = parse_art(UP_HULL_BASE, 24, 42)

    cruise_a = paint_spans(base, 40, [(6, 9, "w"), (15, 18, "w")])
    cruise_a = paint_spans(cruise_a, 41, [(8, 11, "s"), (13, 16, "s")])

    cruise_b = shift_grid(base, 0, -1)
    cruise_b = paint_spans(cruise_b, 39, [(5, 9, "s"), (15, 19, "s")])
    cruise_b = paint_spans(cruise_b, 40, [(7, 10, "w"), (14, 17, "w")])

    # Boost A / B: bow ripples breaking at north prow + foamy twin wake behind stern!
    boost_a = clone_grid(base)
    boost_a = paint_pixels(boost_a, [
        (7, 2, "w"), (8, 2, "s"), (6, 3, "w"), (7, 3, "w"), (5, 4, "s"),
        (16, 2, "w"), (15, 2, "s"), (17, 3, "w"), (16, 3, "w"), (18, 4, "s"),
        (6, 37, "s"), (7, 38, "w"), (6, 39, "w"), (7, 39, "w"), (8, 39, "s"),
        (17, 37, "s"), (16, 38, "w"), (17, 39, "w"), (16, 39, "w"), (15, 39, "s"),
    ])
    boost_a = paint_spans(boost_a, 40, [(5, 10, "w"), (14, 19, "w")])
    boost_a = paint_spans(boost_a, 41, [(6, 11, "s"), (13, 18, "s")])

    boost_b = shift_grid(base, 0, -1)
    boost_b = paint_pixels(boost_b, [
        (7, 1, "w"), (6, 2, "w"), (7, 2, "w"), (5, 3, "w"), (6, 3, "s"),
        (16, 1, "w"), (17, 2, "w"), (16, 2, "w"), (18, 3, "w"), (17, 3, "s"),
        (5, 37, "w"), (6, 38, "w"), (7, 38, "w"),
        (18, 37, "w"), (17, 38, "w"), (16, 38, "w"),
    ])
    boost_b = paint_spans(boost_b, 39, [(5, 10, "w"), (14, 19, "w")])
    boost_b = paint_spans(boost_b, 40, [(6, 11, "w"), (13, 18, "w")])
    boost_b = paint_spans(boost_b, 41, [(7, 17, "s")])

    return {
        "cruise_a": cruise_a,
        "cruise_b": cruise_b,
        "boost_a": boost_a,
        "boost_b": boost_b,
    }


# ---------------------------------------------------------------------------
# Authentic 16x16 Seated Minish Cap Link Riders (native SP-7 from mc_link_sheet.4bpp)
# ---------------------------------------------------------------------------
def decode_mc_tile16(sheet: bytes, tile_row: int, tile_col: int) -> Grid:
    """Decode one 16x16 4BPP sprite block directly from Data/graphics/link/mc_link_sheet.4bpp."""
    grid = new_grid(16, 16, 0)
    for dy in range(2):
        for dx in range(2):
            off = ((tile_row + dy) * 16 + (tile_col + dx)) * 32
            for y in range(8):
                p0 = sheet[off + y * 2]
                p1 = sheet[off + y * 2 + 1]
                p2 = sheet[off + 16 + y * 2]
                p3 = sheet[off + 16 + y * 2 + 1]
                for x in range(8):
                    b = 7 - x
                    grid[dy * 8 + y][dx * 8 + x] = (
                        ((p0 >> b) & 1)
                        | (((p1 >> b) & 1) << 1)
                        | (((p2 >> b) & 1) << 2)
                        | (((p3 >> b) & 1) << 3)
                    )
    return grid


def overlay_grid(dst: Grid, src: Grid, ox: int, oy: int, src_y0: int = 0, src_y1: int | None = None) -> None:
    dh, dw = len(dst), len(dst[0])
    sh, sw = len(src), len(src[0])
    y1 = sh if src_y1 is None else min(sh, src_y1)
    for sy in range(src_y0, y1):
        dy = oy + (sy - src_y0)
        if not (0 <= dy < dh):
            continue
        for sx in range(sw):
            v = src[sy][sx]
            if v == 0:
                continue
            dx = ox + sx
            if 0 <= dx < dw:
                dst[dy][dx] = v


def build_mc_riders(mc_sheet_path: Path) -> dict[str, Grid]:
    """Assemble authentic 16x16 seated Minish Cap Link riders directly from mc_link_sheet.4bpp."""
    sheet = mc_sheet_path.read_bytes()
    assert len(sheet) >= 8 * 16 * 32, f"mc_link_sheet.4bpp unexpectedly short ({len(sheet)} B)"

    side_head = decode_mc_tile16(sheet, 0, 0)
    side_body = decode_mc_tile16(sheet, 2, 0)
    side = new_grid(16, 16, 0)
    overlay_grid(side, side_body, ox=1, oy=10, src_y0=4, src_y1=10)
    overlay_grid(side, side_head, ox=0, oy=0, src_y0=1, src_y1=14)

    down_head = decode_mc_tile16(sheet, 0, 2)
    down_body = decode_mc_tile16(sheet, 2, 6)
    down = new_grid(16, 16, 0)
    overlay_grid(down, down_body, ox=0, oy=11, src_y0=5, src_y1=10)
    overlay_grid(down, down_head, ox=0, oy=0, src_y0=1, src_y1=15)

    up_head = decode_mc_tile16(sheet, 0, 4)
    up_body = decode_mc_tile16(sheet, 4, 2)
    up = new_grid(16, 16, 0)
    overlay_grid(up, up_body, ox=0, oy=11, src_y0=6, src_y1=11)
    overlay_grid(up, up_head, ox=0, oy=0, src_y0=1, src_y1=16)

    return {"down": down, "up": up, "side": side}


# ---------------------------------------------------------------------------
# Always-Hoisted Wind Waker Sail Art (24 x 32 -> 2x16x16 + 1x8x16 = 320 B!)
#
# Narrow 8x16 piece sits at x=16..23, y=8..23 (or mirrored x=0..7, y=8..23 for Up),
# so rows 0..7 and 24..31 MUST be empty in columns 16..23!
#
# Features the iconic Wind Waker emerald-teal ocean-swirl vortex crest (clean
# curled spiral!), luminous white sailcloth with cool silver curvature shading,
# crimson corner lashings, and golden bottom boom on a sturdy emerald-teal mast.
#
# Cruise vs Boost distinction:
#   - Cruise (frames 0..5): Upright mast, sleek trimmer hoisted sail (~14px belly),
#     gentle 2-frame calm-breeze flutter.
#   - Boost  (frames 6..11): Full wind-filled billowing forward-leaning sail
#     (~21px wide taut convex curve + 1px wind-bent upper mast + lively 8f gust!).
# ---------------------------------------------------------------------------

# --- SIDE SAIL: CRUISE (upright mast, sleek calm-breeze sail, curled Wind Waker spiral!) ---
SAIL_SIDE_CRUISE_A = [
    # 0         1         2
    # 012345678901234567890123
    "........................",  # 00
    "...kkk..................",  # 01 masthead finial
    "..ktttk.................",  # 02 emerald-teal mast top
    "..krttkk................",  # 03 crimson top ring
    "..kttwwkk...............",  # 04 trimmer cruise sail profile
    "..kttwwwwkk.............",  # 05
    "..kttwwwwwwk............",  # 06
    "..kttwwwwwwwk...........",  # 07 (x<=15)
    "..kttswwwwwwwk..........",  # 08
    "..kttswwttttwwk.........",  # 09 iconic curled Wind Waker spiral!
    "..kttswttwwttwwk........",  # 10
    "..kttswttwttwwswk.......",  # 11
    "..kttswttwwtwwswk.......",  # 12
    "..kttswwttwwwsswk.......",  # 13
    "..kttswttwwwttswk.......",  # 14 sweeping outer swirl tail!
    "..kttswwtttttwswk.......",  # 15
    "..kttswwwwwwwsswk.......",  # 16
    "..kttsswwwwwsswk........",  # 17
    "..kttssswwwsswk.........",  # 18
    "..kttssssssssk..........",  # 19
    "..krrssssssrrk..........",  # 20 crimson corner ties
    "..kggggggggggk..........",  # 21 crisp golden boom
    "..kgggggggggkk..........",  # 22
    "..kttkkkkkkkk...........",  # 23 mast collar
    "..kttk..................",  # 24 mast stepping cleanly into deck!
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kttk..................",  # 30
    "..kttk..................",  # 31 (tucks cleanly behind near gunwale!)
]

SAIL_SIDE_CRUISE_B = [
    "........................",  # 00
    "...kkk..................",  # 01
    "..ktttk.................",  # 02
    "..krttkk................",  # 03
    "..kttwwwkk..............",  # 04 gentle +1px calm-breeze flutter
    "..kttwwwwwkk............",  # 05
    "..kttwwwwwwwk...........",  # 06
    "..kttwwwwwwwwk..........",  # 07 (x<=15)
    "..kttswwwwwwwwk.........",  # 08
    "..kttswwwttttwwk........",  # 09
    "..kttswtttwwttwwk.......",  # 10
    "..kttswwttwttwwswk......",  # 11
    "..kttswwttwwtwwswk......",  # 12
    "..kttswwwttwwwsswk......",  # 13
    "..kttswwttwwwttswk......",  # 14
    "..kttswwwtttttwswk......",  # 15
    "..kttswwwwwwwwsswk......",  # 16
    "..kttsswwwwwwsswk.......",  # 17
    "..kttssswwwwsswk........",  # 18
    "..kttsssssssssk.........",  # 19
    "..krrsssssssrrk.........",  # 20
    "..kgggggggggggk.........",  # 21
    "..kggggggggggkk.........",  # 22
    "..kttkkkkkkkkk..........",  # 23
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kttk..................",  # 30
    "..kttk..................",  # 31
]

# --- SIDE SAIL: BOOST (full wind-filled billowing forward-leaning Wind Waker sail!) ---
# Narrow 8x16 sits at y=7..22 (x=16..23), giving a butter-smooth diagonal leading arc!
SAIL_SIDE_BOOST_A = [
    # 0         1         2
    # 012345678901234567890123
    "....kkk.................",  # 00 +1px forward wind-bent masthead!
    "...ktttk................",  # 01
    "...krttkk...............",  # 02 crimson ring + sweeping top spar
    "...kttwwwkk.............",  # 03
    "...kttwwwwwwkk..........",  # 04
    "...kttwwwwwwwwkk........",  # 05
    "..kttwwwwwwwwwwk........",  # 06 (x<=15! smooth diagonal transition into row 7!)
    "..kttswwwwwwwwwwwkk.....",  # 07 butter-smooth diagonal leading arc!
    "..kttswwwwwwwwwwwwwk....",  # 08 FULL WIND-FILLED BILLOW (x=16..22!)
    "..kttswwwwtttttwwwwwk...",  # 09 bold Wind Waker ocean spiral!
    "..kttswwwttwwwttwwwwwk..",  # 10
    "..kttswtttwwttwwtwwwwsk.",  # 11 taut sunlit white belly!
    "..kttswwttwwttwwtwwwwsk.",  # 12
    "..kttswwttwwwttwwwwwssk.",  # 13
    "..kttswwwttwwwwtttwwssk.",  # 14 sweeping vortex tail!
    "..kttswwwttwwwttttwssk..",  # 15
    "..kttswwwwtttttttwwssk..",  # 16
    "..kttsswwwwwwwwwwwssk...",  # 17 deep luminous billow curve
    "..kttssswwwwwwwwwssk....",  # 18
    "..kttsssssssssssssk.....",  # 19
    "..krrsssssssssssrrk.....",  # 20 crimson corner lashings
    "..kgggggggggggggggk.....",  # 21 taut extended golden boom
    "..kggggggggggggggkk.....",  # 22 (narrow band ends cleanly here!)
    "..kttkkkkkkkkkkk........",  # 23 (x<=15! mast collar)
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kttk..................",  # 30
    "..kttk..................",  # 31
]

SAIL_SIDE_BOOST_B = [
    "....kkk.................",  # 00
    "...ktttk................",  # 01
    "...krttkkk..............",  # 02 +1..2px dynamic gale gust surge!
    "...kttwwwwkk............",  # 03
    "...kttwwwwwwwkk.........",  # 04
    "...kttwwwwwwwwwk........",  # 05
    "..kttwwwwwwwwwww........",  # 06 -> keep outline inside x<=15 below
    "..kttswwwwwwwwwwwwkk....",  # 07 butter-smooth gale arc!
    "..kttswwwwwwwwwwwwwwk...",  # 08
    "..kttswwwwwtttttwwwwwk..",  # 09
    "..kttswwwwttwwwttwwwwwk.",  # 10
    "..kttswwwttwwttwwtwwwwsk",  # 11 FULL 24px wind-caught belly!
    "..kttswwwttwwttwwtwwwwsk",  # 12
    "..kttswwwttwwwttwwwwwssk",  # 13
    "..kttswwwwttwwwwtttwwssk",  # 14
    "..kttswwwwttwwwttttwssk.",  # 15
    "..kttswwwwwtttttttwwssk.",  # 16
    "..kttsswwwwwwwwwwwwssk..",  # 17
    "..kttssswwwwwwwwwwssk...",  # 18
    "..kttssssssssssssssk....",  # 19
    "..krrssssssssssssrrk....",  # 20
    "..kggggggggggggggggk....",  # 21
    "..kgggggggggggggggkk....",  # 22
    "..kttkkkkkkkkkkk........",  # 23 (x<=15!)
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kttk..................",  # 30
    "..kttk..................",  # 31
]
SAIL_SIDE_BOOST_B[6] = "..kttwwwwwwwwwwk........"

# --- DOWN SAIL (starboard-billowing Wind Waker sail; Up is exact horizontal mirror!) ---
SAIL_DOWN_CRUISE_A = [
    "........................",  # 00
    "...kkk..................",  # 01
    "..ktttk.................",  # 02
    "..kttrkk................",  # 03
    "..kttwwkk...............",  # 04
    "..kttwwwwkk.............",  # 05
    "..kttwwwwwwk............",  # 06
    "..kttwwwwwwwk...........",  # 07 (x<=15)
    "..kttswwwwwwwk..........",  # 08
    "..kttswwttttwwk.........",  # 09 iconic curled Wind Waker spiral!
    "..kttswttwwttwwk........",  # 10
    "..kttswttwttwwswk.......",  # 11
    "..kttswttwwtwwswk.......",  # 12
    "..kttswwttwwwsswk.......",  # 13
    "..kttswttwwwttswk.......",  # 14
    "..kttswwtttttwswk.......",  # 15
    "..kttswwwwwwwsswk.......",  # 16
    "..kttsswwwwwsswk........",  # 17
    "..kttssswwwsswk.........",  # 18
    "..kttssssssssk..........",  # 19
    "..krrssssssrrk..........",  # 20
    "..kggggggggggk..........",  # 21
    "..kgggggggggkk..........",  # 22
    "..kttkkkkkkkk...........",  # 23
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kggk..................",  # 30 gold mast collar on deck thwart!
    "..kkkk..................",  # 31
]

SAIL_DOWN_CRUISE_B = [
    "........................",  # 00
    "...kkk..................",  # 01
    "..ktttk.................",  # 02
    "..kttrkk................",  # 03
    "..kttwwwkk..............",  # 04
    "..kttwwwwwkk............",  # 05
    "..kttwwwwwwwk...........",  # 06
    "..kttwwwwwwwwk..........",  # 07 (x<=15)
    "..kttswwwwwwwwk.........",  # 08
    "..kttswwwttttwwk........",  # 09
    "..kttswtttwwttwwk.......",  # 10
    "..kttswwttwttwwswk......",  # 11
    "..kttswwttwwtwwswk......",  # 12
    "..kttswwwttwwwsswk......",  # 13
    "..kttswwttwwwttswk......",  # 14
    "..kttswwwtttttwswk......",  # 15
    "..kttswwwwwwwwsswk......",  # 16
    "..kttsswwwwwwsswk.......",  # 17
    "..kttssswwwwsswk........",  # 18
    "..kttsssssssssk.........",  # 19
    "..krrsssssssrrk.........",  # 20
    "..kgggggggggggk.........",  # 21
    "..kggggggggggkk.........",  # 22
    "..kttkkkkkkkkk..........",  # 23
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kggk..................",  # 30
    "..kkkk..................",  # 31
]

SAIL_DOWN_BOOST_A = [
    "....kkk.................",  # 00
    "...ktttk................",  # 01
    "...kttrkk...............",  # 02
    "...kttwwwkk.............",  # 03
    "...kttwwwwwwkk..........",  # 04
    "...kttwwwwwwwwkk........",  # 05
    "..kttwwwwwwwwwwk........",  # 06 (x<=15)
    "..kttswwwwwwwwwwwkk.....",  # 07 butter-smooth diagonal arc!
    "..kttswwwwwwwwwwwwwk....",  # 08
    "..kttswwwwtttttwwwwwk...",  # 09
    "..kttswwwttwwwttwwwwwk..",  # 10
    "..kttswtttwwttwwtwwwwsk.",  # 11
    "..kttswwttwwttwwtwwwwsk.",  # 12
    "..kttswwttwwwttwwwwwssk.",  # 13
    "..kttswwwttwwwwtttwwssk.",  # 14
    "..kttswwwttwwwttttwssk..",  # 15
    "..kttswwwwtttttttwwssk..",  # 16
    "..kttsswwwwwwwwwwwssk...",  # 17
    "..kttssswwwwwwwwwssk....",  # 18
    "..kttsssssssssssssk.....",  # 19
    "..krrsssssssssssrrk.....",  # 20
    "..kgggggggggggggggk.....",  # 21
    "..kggggggggggggggkk.....",  # 22
    "..kttkkkkkkkkkkk........",  # 23 (x<=15)
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kggk..................",  # 30
    "..kkkk..................",  # 31
]

SAIL_DOWN_BOOST_B = [
    "....kkk.................",  # 00
    "...ktttk................",  # 01
    "...kttrkkk..............",  # 02
    "...kttwwwwkk............",  # 03
    "...kttwwwwwwwkk.........",  # 04
    "...kttwwwwwwwwwk........",  # 05
    "..kttwwwwwwwwwwk........",  # 06 (x<=15)
    "..kttswwwwwwwwwwwwkk....",  # 07 butter-smooth gale arc!
    "..kttswwwwwwwwwwwwwwk...",  # 08
    "..kttswwwwwtttttwwwwwk..",  # 09
    "..kttswwwwttwwwttwwwwwk.",  # 10
    "..kttswwwttwwttwwtwwwwsk",  # 11
    "..kttswwwttwwttwwtwwwwsk",  # 12
    "..kttswwwttwwwttwwwwwssk",  # 13
    "..kttswwwwttwwwwtttwwssk",  # 14
    "..kttswwwwttwwwttttwssk.",  # 15
    "..kttswwwwwtttttttwwssk.",  # 16
    "..kttsswwwwwwwwwwwwssk..",  # 17
    "..kttssswwwwwwwwwwssk...",  # 18
    "..kttssssssssssssssk....",  # 19
    "..krrssssssssssssrrk....",  # 20
    "..kggggggggggggggggk....",  # 21
    "..kgggggggggggggggkk....",  # 22
    "..kttkkkkkkkkkkk........",  # 23 (x<=15)
    "..kttk..................",  # 24
    "..kttk..................",  # 25
    "..kttk..................",  # 26
    "..kttk..................",  # 27
    "..kttk..................",  # 28
    "..kttk..................",  # 29
    "..kggk..................",  # 30
    "..kkkk..................",  # 31
]

SAIL_UP_CRUISE_A = [row[::-1] for row in SAIL_DOWN_CRUISE_A]
SAIL_UP_CRUISE_B = [row[::-1] for row in SAIL_DOWN_CRUISE_B]
SAIL_UP_BOOST_A = [row[::-1] for row in SAIL_DOWN_BOOST_A]
SAIL_UP_BOOST_B = [row[::-1] for row in SAIL_DOWN_BOOST_B]


# ---------------------------------------------------------------------------
# SNES 4BPP tile encoding (exact same row-major DMA layout as Epona!)
# ---------------------------------------------------------------------------
def encode_tile8(grid: Grid, tx: int, ty: int) -> bytes:
    """Encode an 8x8 tile at (tx, ty) into 32-byte SNES 4BPP planar format."""
    h, w = len(grid), len(grid[0])
    bp01 = bytearray(16)
    bp23 = bytearray(16)
    for row in range(8):
        b0 = b1 = b2 = b3 = 0
        yy = ty + row
        for col in range(8):
            xx = tx + col
            px = grid[yy][xx] if (0 <= yy < h and 0 <= xx < w) else 0
            bit = 7 - col
            if px & 1:
                b0 |= 1 << bit
            if px & 2:
                b1 |= 1 << bit
            if px & 4:
                b2 |= 1 << bit
            if px & 8:
                b3 |= 1 << bit
        bp01[row * 2] = b0
        bp01[row * 2 + 1] = b1
        bp23[row * 2] = b2
        bp23[row * 2 + 1] = b3
    return bytes(bp01 + bp23)


def encode_group0_4x16(grid: Grid, pieces: Sequence[tuple[int, int]]) -> bytes:
    """Encode 4 x 16x16 pieces into 512 bytes: 256B top row (8 tiles) + 256B bot row (8 tiles)."""
    assert len(pieces) == 4
    top = bytearray()
    bot = bytearray()
    for px, py in pieces:
        top += encode_tile8(grid, px, py)
        top += encode_tile8(grid, px + 8, py)
        bot += encode_tile8(grid, px, py + 8)
        bot += encode_tile8(grid, px + 8, py + 8)
    assert len(top) == 256 and len(bot) == 256
    return bytes(top + bot)


def encode_16x16(grid: Grid, px: int, py: int) -> bytes:
    """Encode 1 x 16x16 piece into 128 bytes: 64B top row + 64B bot row."""
    top = encode_tile8(grid, px, py) + encode_tile8(grid, px + 8, py)
    bot = encode_tile8(grid, px, py + 8) + encode_tile8(grid, px + 8, py + 8)
    return top + bot


def encode_narrow_8x16(grid: Grid, px: int, py: int) -> bytes:
    """Encode 1 x 8x16 narrow piece into 64 bytes: 32B top ($40A0) + 32B bot ($41A0)."""
    return encode_tile8(grid, px, py) + encode_tile8(grid, px, py + 8)


def verify_hull_coverage(name: str, grid: Grid, pieces: Sequence[tuple[int, int]]) -> None:
    """Assert 100% of non-zero hull pixels are covered by the 4 x 16x16 VRAM tiles."""
    h, w = len(grid), len(grid[0])
    covered = [[False] * w for _ in range(h)]
    for px, py in pieces:
        for y in range(py, min(h, py + 16)):
            for x in range(px, min(w, px + 16)):
                if 0 <= y < h and 0 <= x < w:
                    covered[y][x] = True
    for y in range(h):
        for x in range(w):
            if grid[y][x] != 0 and not covered[y][x]:
                raise AssertionError(f"Hull {name} has uncovered pixel at ({x},{y}) val={grid[y][x]}")


# ---------------------------------------------------------------------------
# Master Sparse Asset Assembly (12 frames: 0..5 Cruise Sail, 6..11 Boost Sail)
# ---------------------------------------------------------------------------
def build_all(
    source_png: Path | None = None,
    mc_sheet: Path = DEFAULT_MC_SHEET,
) -> tuple[bytes, str, bytes, dict]:
    _ = source_png  # V3 hull & sail art are bespoke self-contained 16-bit grids
    side_hulls = build_side_hulls()
    down_hulls = build_down_hulls()
    up_hulls = build_up_hulls()
    riders = build_mc_riders(mc_sheet)

    sails = {
        "side_cruise_a": parse_art(SAIL_SIDE_CRUISE_A, 24, 32),
        "side_cruise_b": parse_art(SAIL_SIDE_CRUISE_B, 24, 32),
        "side_boost_a":  parse_art(SAIL_SIDE_BOOST_A,  24, 32),
        "side_boost_b":  parse_art(SAIL_SIDE_BOOST_B,  24, 32),
        "down_cruise_a": parse_art(SAIL_DOWN_CRUISE_A, 24, 32),
        "down_cruise_b": parse_art(SAIL_DOWN_CRUISE_B, 24, 32),
        "down_boost_a":  parse_art(SAIL_DOWN_BOOST_A,  24, 32),
        "down_boost_b":  parse_art(SAIL_DOWN_BOOST_B,  24, 32),
        "up_cruise_a":   parse_art(SAIL_UP_CRUISE_A,   24, 32),
        "up_cruise_b":   parse_art(SAIL_UP_CRUISE_B,   24, 32),
        "up_boost_a":    parse_art(SAIL_UP_BOOST_A,    24, 32),
        "up_boost_b":    parse_art(SAIL_UP_BOOST_B,    24, 32),
    }

    # Exact 4 x 16x16 hull tiling (512 B VRAM & 512 B docked WRAM backup):
    #   Down/Up (24x42): 1+2+1 sleek tapered skiff
    #   Side    (56x28): Stern (0,12) + Midship (16,12) + Bow (32,12) + Dragon Figurehead (40,0)
    HULL_PIECES = {
        "down": [(4, 0), (0, 13), (8, 13), (4, 26)],
        "up":   [(4, 0), (0, 13), (8, 13), (4, 26)],
        "side": [(0, 12), (16, 12), (32, 12), (40, 0)],
    }
    HULL_DIMS = {
        "down": (24, 42),
        "up":   (24, 42),
        "side": (56, 28),
    }
    # Authentic Minish Cap Link 16x16 rider placement (Right-facing for side; H-flipped for Left)
    RIDER_POS = {
        "down": (4, 8),    # Centered in cockpit looking South over compact dragon prow
        "up":   (4, 17),   # Centered in aft cockpit facing North behind mast & prow
        "side": (10, 4),   # Seated comfortably in rear cockpit holding stern tiller!
    }
    # Wind Waker Sail 24x32 placement relative to hull top-left:
    #   Side mast local x=3..5 -> world x=28..30 (center-forward deck, clear of Link & figurehead!)
    #   Down mast local x=3..5 -> world x=17..19 (anchored inside starboard thwart, clear of Link's face!)
    #   Up   mast local x=18..20 -> world x=5..7 (anchored inside port thwart behind Link's shoulder!)
    SAIL_NARROW_Y = {
        "down": 7,
        "up":   7,
        "side": 7,
    }
    SAIL_ANCHOR = {
        "down": (15, -6),
        "up":   (-14, -6),
        "side": (25, -14),
    }

    def sail_piece_coords(dir_key: str) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        ny = SAIL_NARROW_Y[dir_key]
        if dir_key == "up":
            return (8, 0), (8, 16), (0, ny)
        return (0, 0), (0, 16), (16, ny)

    # Validate SP-3 palette purity (0 or 9..15) AND 100% tile coverage on all hulls & sails
    for dkey, hdict in (("side", side_hulls), ("down", down_hulls), ("up", up_hulls)):
        for variant, g in hdict.items():
            for y, row in enumerate(g):
                for x, v in enumerate(row):
                    assert v == 0 or 9 <= v <= 15, f"{dkey}_{variant} ({x},{y}) invalid SP-3 idx {v}"
            verify_hull_coverage(f"{dkey}_{variant}", g, HULL_PIECES[dkey])

    for sname, sgrid in sails.items():
        dkey = sname.split("_")[0]
        for y, row in enumerate(sgrid):
            for x, v in enumerate(row):
                assert v == 0 or 9 <= v <= 15, f"sail_{sname} ({x},{y}) invalid SP-3 idx {v}"
        _, _, (nx, ny) = sail_piece_coords(dkey)
        for y in range(32):
            if ny <= y < ny + 16:
                continue
            for x in range(nx, nx + 8):
                assert sgrid[y][x] == 0, (
                    f"Sail {sname} has pixel at ({x},{y}) outside narrow band y={ny}..{ny+15}"
                )

    dictionary = bytearray()
    blob_offsets: dict[bytes, int] = {}

    def intern(blob: bytes) -> int:
        if blob not in blob_offsets:
            blob_offsets[blob] = len(dictionary)
            dictionary.extend(blob)
        return blob_offsets[blob]

    # Build the 12 mounted frames:
    #   0..5:  Cruise (Sail ALWAYS hoisted! Gentle calm-breeze flutter; hulls also used for Docked)
    #   6..11: Sail Boost (Full billowing Wind Waker sail + lively bow-wave/wake foam!)
    frame_specs = [
        ("down", down_hulls["cruise_a"], sails["down_cruise_a"],  0),  # 0: Down Cruise A
        ("down", down_hulls["cruise_b"], sails["down_cruise_b"], -1),  # 1: Down Cruise B
        ("up",   up_hulls["cruise_a"],   sails["up_cruise_a"],    0),  # 2: Up Cruise A
        ("up",   up_hulls["cruise_b"],   sails["up_cruise_b"],   -1),  # 3: Up Cruise B
        ("side", side_hulls["cruise_a"], sails["side_cruise_a"],  0),  # 4: Side Cruise A
        ("side", side_hulls["cruise_b"], sails["side_cruise_b"], -1),  # 5: Side Cruise B
        ("down", down_hulls["boost_a"],  sails["down_boost_a"],   0),  # 6: Down Boost A
        ("down", down_hulls["boost_b"],  sails["down_boost_b"],  -1),  # 7: Down Boost B
        ("up",   up_hulls["boost_a"],    sails["up_boost_a"],     0),  # 8: Up Boost A
        ("up",   up_hulls["boost_b"],    sails["up_boost_b"],    -1),  # 9: Up Boost B
        ("side", side_hulls["boost_a"],  sails["side_boost_a"],   0),  # 10: Side Boost A
        ("side", side_hulls["boost_b"],  sails["side_boost_b"],  -1),  # 11: Side Boost B
    ]

    frame_meta = []
    for dkey, hgrid, sgrid, bob_dy in frame_specs:
        hp = HULL_PIECES[dkey]
        hull_off = intern(encode_group0_4x16(hgrid, hp))
        rider_off = intern(encode_16x16(riders[dkey], 0, 0))
        sc0, sc1, scn = sail_piece_coords(dkey)
        sail0_off = intern(encode_16x16(sgrid, sc0[0], sc0[1]))
        sail1_off = intern(encode_16x16(sgrid, sc1[0], sc1[1]))
        sailn_off = intern(encode_narrow_8x16(sgrid, scn[0], scn[1]))
        sox, soy = SAIL_ANCHOR[dkey]
        sail_screen_coords = [
            (sox + sc0[0], soy + sc0[1] + bob_dy),
            (sox + sc1[0], soy + sc1[1] + bob_dy),
            (sox + scn[0], soy + scn[1] + bob_dy),
        ]
        w, h = HULL_DIMS[dkey]
        rx, ry = RIDER_POS[dkey]
        frame_meta.append({
            "dir": dkey,
            "width": w,
            "height": h,
            "has_sail": 1,
            "rider_x": rx,
            "rider_y": ry + bob_dy,
            "pieces": hp,
            "sail_coords": sail_screen_coords,
            "sail_anchor": (sox, soy + bob_dy),
            "ptrs": (hull_off, rider_off, sail0_off, sail1_off, sailn_off),
            "hull_grid": hgrid,
            "rider_grid": riders[dkey],
            "sail_grid": sgrid,
            "bob_dy": bob_dy,
        })

    # Verify VBlank DMA budget across ALL 12 x 12 transitions (<= 960 B!)
    # AND verify Sail0 pointer uniqueness for fast dedup safety.
    sail_tuples_by_s0: dict[int, tuple[int, int, int]] = {}
    for fm in frame_meta:
        s_tup = fm["ptrs"][2:5]
        prev = sail_tuples_by_s0.get(s_tup[0])
        assert prev is None or prev == s_tup, f"Ambiguous Sail0 dedup ptr {s_tup[0]:04X}"
        sail_tuples_by_s0[s_tup[0]] = s_tup

    max_dma = 0
    for old_f in [None, *range(len(frame_meta))]:
        for fm in frame_meta:
            dma = 0
            old_ptrs = frame_meta[old_f]["ptrs"] if old_f is not None else (-1, -1, -1, -1, -1)
            old_sail = frame_meta[old_f]["has_sail"] if old_f is not None else 0
            if fm["ptrs"][0] != old_ptrs[0]:
                dma += 512
            if fm["ptrs"][1] != old_ptrs[1]:
                dma += 128
            if fm["has_sail"] and (
                not old_sail
                or fm["ptrs"][2] != old_ptrs[2]
                or fm["ptrs"][3] != old_ptrs[3]
                or fm["ptrs"][4] != old_ptrs[4]
            ):
                dma += 320
            if dma > max_dma:
                max_dma = dma
    assert max_dma <= 960, f"Worst-case NMI DMA {max_dma}B exceeded 960B budget!"

    def s8(v: int) -> str:
        return f"${v & 0xFF:02X}"

    lines = [
        "; Generated by Scripts/Generate/build_korl_art.py — DO NOT HAND-EDIT.",
        f"!KORL_FrameCount      = {len(frame_meta)}",
        f"!KORL_DictionaryBytes = {len(dictionary)}",
        f"!KORL_MaxDmaBytes     = {max_dma}",
        "",
        "KORL_Frame_Width:",
        "  db " + ",".join(s8(m["width"]) for m in frame_meta),
        "KORL_Frame_Height:",
        "  db " + ",".join(s8(m["height"]) for m in frame_meta),
        "KORL_Frame_HasSail:",
        "  db " + ",".join(s8(m["has_sail"]) for m in frame_meta),
        "KORL_Rider_X:",
        "  db " + ",".join(s8(m["rider_x"]) for m in frame_meta),
        "KORL_Rider_Y:",
        "  db " + ",".join(s8(m["rider_y"]) for m in frame_meta),
        "; 4 hull pieces per frame (frame * 4 + piece 0..3):",
        "KORL_Piece_X:",
        "  db " + ",".join(s8(px) for m in frame_meta for px, _ in m["pieces"]),
        "KORL_Piece_Y:",
        "  db " + ",".join(s8(py) for m in frame_meta for _, py in m["pieces"]),
        "; 3 sail pieces per frame (frame * 4 + idx 0..2; idx 3 pad for ASL #2 indexing):",
        "KORL_Sail_X:",
        "  db " + ",".join(
            s8(v) for m in frame_meta for v in (
                m["sail_coords"][0][0], m["sail_coords"][1][0], m["sail_coords"][2][0], 0
            )
        ),
        "KORL_Sail_Y:",
        "  db " + ",".join(
            s8(v) for m in frame_meta for v in (
                m["sail_coords"][0][1], m["sail_coords"][1][1], m["sail_coords"][2][1], 0
            )
        ),
        "; 10 bytes per frame: Hull(512B), Rider(128B), Sail0(128B), Sail1(128B), SailNarrow(64B)",
        "KORL_Frame_GroupPointers:",
    ]
    for idx, m in enumerate(frame_meta):
        p0, p1, p2, p3, p4 = m["ptrs"]
        lines.append(
            f"  dw KORL_Graphics+${p0:04X},KORL_Graphics+${p1:04X},"
            f"KORL_Graphics+${p2:04X},KORL_Graphics+${p3:04X},KORL_Graphics+${p4:04X} ; frame {idx}"
        )
    asm_text = "\n".join(lines) + "\n"
    pal_bytes = build_palette_bytes()
    return bytes(dictionary), asm_text, pal_bytes, {"frames": frame_meta, "max_dma": max_dma}


def render_korl_cell(
    m: dict,
    *,
    cw: int = 96,
    ch: int = 84,
    hflip: bool = False,
    link_pal: dict[int, tuple[int, int, int]] = LINK_SP7_GREEN_RGB,
    docked: bool = False,
) -> Image.Image:
    """Render one KORL frame at 1x SNES resolution over Lyra Sea blue + ripple lines."""
    ocean = (32, 96, 176, 255)
    canvas = Image.new("RGBA", (cw, ch), ocean)
    for wy in range(10, ch, 14):
        for wx in range((wy * 5) % 18, cw, 22):
            for dx in range(5):
                if wx + dx < cw:
                    canvas.putpixel((wx + dx, wy), (56, 128, 208, 255))

    bx = (cw - m["width"]) // 2
    by = ch - m["height"] - 14

    def paint_grid(g: Grid, ox: int, oy: int, pal: dict[int, tuple[int, int, int]], flip: bool):
        gh, gw = len(g), len(g[0])
        for y in range(gh):
            for x in range(gw):
                v = g[y][x]
                if v == 0:
                    continue
                px = (gw - 1 - x) if flip else x
                tx, ty = ox + px, oy + y
                if 0 <= tx < cw and 0 <= ty < ch:
                    r, gg, b = pal[v]
                    canvas.putpixel((tx, ty), (r, gg, b, 255))

    def mirror_x(local_x: int, piece_w: int) -> int:
        return (m["width"] - piece_w - local_x) if hflip else local_x

    if docked:
        paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
        return canvas

    rx = bx + mirror_x(m["rider_x"], 16)
    ry = by + m["rider_y"]
    sx = bx + mirror_x(m["sail_anchor"][0], 24)
    sy = by + m["sail_anchor"][1]

    # Exact painter's order (back -> front) matching SNES OAM priority in KORL_DrawPlayerOam_Long:
    #   - Side: Rider (back) -> Sail (mid) -> Hull (front: near gunwale wraps Link & mast base!)
    #   - Down: Hull (back) -> Rider (mid) -> Sail (front)
    #   - Up:   Hull (back) -> Sail (mid) -> Rider (front: aft Link sits in front of forward mast!)
    if m["dir"] == "side":
        paint_grid(m["rider_grid"], rx, ry, link_pal, hflip)
        if m["sail_grid"] is not None:
            paint_grid(m["sail_grid"], sx, sy, KORL_SP3_RGB, hflip)
        paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
    elif m["dir"] == "up":
        paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
        if m["sail_grid"] is not None:
            paint_grid(m["sail_grid"], sx, sy, KORL_SP3_RGB, hflip)
        paint_grid(m["rider_grid"], rx, ry, link_pal, hflip)
    else:
        paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
        paint_grid(m["rider_grid"], rx, ry, link_pal, hflip)
        if m["sail_grid"] is not None:
            paint_grid(m["sail_grid"], sx, sy, KORL_SP3_RGB, hflip)

    return canvas


def render_preview(meta: dict, out_path: Path) -> None:
    """Render all 12 frames + Left H-flip + Docked + Blue/Red Mail over Lyra Sea blue."""
    frames = meta["frames"]
    cw, ch = 96, 84
    scale = 3
    panels = [
        ("0: Down Cruise A (Sail!)", 0, False, LINK_SP7_GREEN_RGB, False),
        ("1: Down Cruise B (Sail!)", 1, False, LINK_SP7_GREEN_RGB, False),
        ("2: Up Cruise A (Sail!)",   2, False, LINK_SP7_GREEN_RGB, False),
        ("3: Up Cruise B (Sail!)",   3, False, LINK_SP7_GREEN_RGB, False),
        ("4: Right Cruise A",        4, False, LINK_SP7_GREEN_RGB, False),
        ("5: Left Cruise A (HFlip)", 4, True,  LINK_SP7_GREEN_RGB, False),
        ("6: Right Cruise B (Blue)", 5, False, LINK_SP7_BLUE_RGB,  False),
        ("7: Docked Empty Side",     4, False, LINK_SP7_GREEN_RGB, True),
        ("8: Down Boost A",          6, False, LINK_SP7_GREEN_RGB, False),
        ("9: Down Boost B",          7, False, LINK_SP7_GREEN_RGB, False),
        ("10: Up Boost A",           8, False, LINK_SP7_GREEN_RGB, False),
        ("11: Up Boost B",           9, False, LINK_SP7_GREEN_RGB, False),
        ("12: Right Boost A",       10, False, LINK_SP7_GREEN_RGB, False),
        ("13: Left Boost A (HFlip)",10, True,  LINK_SP7_GREEN_RGB, False),
        ("14: Right Boost B (Blue)",11, False, LINK_SP7_BLUE_RGB,  False),
        ("15: Left Boost B (Red)",  11, True,  LINK_SP7_RED_RGB,   False),
    ]
    out = Image.new("RGBA", (4 * cw * scale, 4 * ch * scale), (20, 40, 72, 255))
    draw = ImageDraw.Draw(out)

    for idx, (label, fidx, hflip, link_pal, docked) in enumerate(panels):
        canvas = render_korl_cell(frames[fidx], cw=cw, ch=ch, hflip=hflip, link_pal=link_pal, docked=docked)
        r_idx, c_idx = divmod(idx, 4)
        scaled = canvas.resize((cw * scale, ch * scale), Image.NEAREST)
        x0, y0 = c_idx * cw * scale, r_idx * ch * scale
        out.paste(scaled, (x0, y0))
        draw.rectangle([x0, y0, x0 + cw * scale - 1, y0 + 18], fill=(12, 24, 48, 220))
        draw.text((x0 + 6, y0 + 3), label, fill=(248, 248, 248, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, default=None, help="Unused (kept for CLI backwards compatibility)")
    ap.add_argument("--mc-sheet", type=Path, default=DEFAULT_MC_SHEET, help="Source mc_link_sheet.4bpp")
    ap.add_argument("--check", action="store_true", help="Verify generated artifacts match deterministically")
    ap.add_argument("--preview", type=Path, default=None, help="Write zoomed RGBA preview sheet")
    args = ap.parse_args(argv)

    raw_4bpp, asm_text, pal_bytes, meta = build_all(args.source, args.mc_sheet)

    if args.preview:
        render_preview(meta, args.preview)
        print(f"[ok] Wrote preview sheet: {args.preview}")

    if args.check:
        mismatches = []
        if not OUT_4BPP.is_file() or OUT_4BPP.read_bytes() != raw_4bpp:
            mismatches.append(str(OUT_4BPP))
        if not OUT_TABLES.is_file() or OUT_TABLES.read_text() != asm_text:
            mismatches.append(str(OUT_TABLES))
        if not OUT_PAL.is_file() or OUT_PAL.read_bytes() != pal_bytes:
            mismatches.append(str(OUT_PAL))
        if mismatches:
            print(f"ERROR: Stale KORL art artifacts: {', '.join(mismatches)}", file=sys.stderr)
            return 1
        print(
            f"[ok] KORL V3 art verified: {len(raw_4bpp)} B sparse 4BPP, "
            f"{len(pal_bytes)} B SP-3 palette, max NMI DMA = {meta['max_dma']} B (<= 960 B)."
        )
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_4BPP.write_bytes(raw_4bpp)
    OUT_TABLES.write_text(asm_text)
    OUT_PAL.write_bytes(pal_bytes)
    print(
        f"[ok] Generated KORL V3 art: {OUT_4BPP.name} ({len(raw_4bpp)} B), "
        f"{OUT_TABLES.name}, {OUT_PAL.name} ({len(pal_bytes)} B), "
        f"max NMI DMA = {meta['max_dma']} B (<= 960 B)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
