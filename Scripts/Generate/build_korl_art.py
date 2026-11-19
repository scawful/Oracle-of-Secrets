#!/usr/bin/env python3
"""Deterministic King of Red Lions sparse 4BPP art & palette packer.

Reads Dervilacus's Minish Cap-scale King of Red Lions sprite sheet:
  /Users/scawful/Documents/Zelda/Graphics/red lion.png

Compacts the 4-way hull + seated Link rider + billowing Wind Waker sail at
integer pixel fidelity into a VBlank-safe sparse 4BPP asset bundle:
  Data/graphics/mounts/korl_sparse.4bpp
  Data/graphics/mounts/korl_sparse_tables.asm
  Data/graphics/mounts/korl_palette.bin

Hardware / VBlank Design (inherits Epona's zero-overrun sparse NMI architecture):
  - SP-3[9..15] (7 BGR555 colors in korl_palette.bin) draws the red hull,
    white/gold dragon-lion head, emerald-teal mast & Wind Waker sail swirl.
    Colors 1..8 of SP-3 remain untouched; Day/Night tinting applies cleanly.
  - SP-7 (Link's own worn Green/Blue/Red Mail palette) draws seated Link
    inside the cockpit (16x16 CHR $08, deduplicated across same-dir frames).
  - Dropable-safe Page 0 VRAM slots ($4000-$43FF):
      $4000/$4100 (CHR $00,$02,$04,$06): 4 x 16x16 Boat Hull + Lion Head (512 B)
      $4080/$4180 (CHR $08):             1 x 16x16 Seated Link Rider     (128 B)
      $42A0/$43A0 (CHR $2A):             1 x 16x16 Wind Waker Sail A     (128 B)
      $42C0/$43C0 (CHR $2C):             1 x 16x16 Wind Waker Sail B     (128 B)
      $40A0/$41A0 (CHR $0A/$1A):         1 x 8x16  Wind Waker Sail Tip   ( 64 B)
    Protected dropables ($0B/$1B Rupee, $0E/$0F Receipt/Bird, $20-$25 Follower/P2,
    $26 Boomerang, $28-$29 Shadow/Heart, $2E-$2F Bombchu) are NEVER touched!
  - Absolute worst-case NMI DMA = 512 + 128 + 320 = 960 bytes (<= 960 B budget).
    Steady cruise wave-bob = 512 B; steady sail boost billow = 832 B; idle = 0 B.

Usage:
  python3 Scripts/Generate/build_korl_art.py [--source PNG] [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys
from typing import Sequence

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SOURCE = Path("/Users/scawful/Documents/Zelda/Graphics/red lion.png")
OUT_DIR = ROOT / "Data/graphics/mounts"
OUT_4BPP = OUT_DIR / "korl_sparse.4bpp"
OUT_TABLES = OUT_DIR / "korl_sparse_tables.asm"
OUT_PAL = OUT_DIR / "korl_palette.bin"

# ---------------------------------------------------------------------------
# Palette definitions
# ---------------------------------------------------------------------------
# SP-3[9..15]: 7 bespoke King of Red Lions + Wind Waker Sail colors.
# Index 15 ($3A67 emerald-teal) is distinct from LW uniform $14A5, Epona $239F,
# and SW/DW palettes (e.g. Goron Coast $B0 $0240) for reliable cross-world refresh.
KORL_SP3_RGB: dict[int, tuple[int, int, int]] = {
    9:  (72,  24,  24),   # #481818 deep warm-crimson outline (crisp on ocean blue)
    10: (152, 40,  32),   # #982820 crimson hull shade
    11: (216, 64,  32),   # #D84020 vivid King of Red Lions crimson-red
    12: (240, 200, 48),   # #F0C830 golden lion horns / mane / tailfin / boom
    13: (248, 248, 248),  # #F8F8F8 crisp white lion head / trim / billowing sail
    14: (160, 168, 176),  # #A0A8B0 cool silver-gray sail & lion face shading
    15: (56,  152, 112),  # #389870 Wind Waker emerald-teal mast & sail swirl
}

# Link's exact Green Mail SP-7 palette (from ROM $1BD308) used to quantize
# Dervilacus's seated Minish Cap Link sprites into real tunic-swappable SP-7!
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


def rgb_to_bgr555(r: int, g: int, b: int) -> int:
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def build_palette_bytes() -> bytes:
    words = [rgb_to_bgr555(*KORL_SP3_RGB[i]) for i in range(9, 16)]
    return b"".join(struct.pack("<H", w) for w in words)


# ---------------------------------------------------------------------------
# Color quantization (source RGBA -> SNES 4BPP palette indices)
# ---------------------------------------------------------------------------
def quantize_boat_pixel(rgb: tuple[int, int, int]) -> int:
    """Map a Dervilacus boat/sail pixel cleanly to SP-3[9..15]."""
    r, g, b = rgb
    # Emerald-teal mast & Wind Waker swirl (g dominant over r, moderate/high b)
    if g >= r + 18 and g >= 60:
        if g < 92 and r < 50:
            return 9   # dark teal-charcoal mast border -> crisp outline
        return 15      # Wind Waker emerald-teal
    # Near-black / very dark outlines
    if max(r, g, b) < 70:
        return 9
    # Whites & cool silver-grays (lion head, gunwale trim, sail cloth)
    sat = max(r, g, b) - min(r, g, b)
    if sat <= 24:
        if r >= 205:
            return 13  # crisp white (includes enclosed 218,218,218 white fills!)
        if r >= 135:
            return 14  # cool silver-gray outline/shade
        return 9       # dark gray outline
    # Bright golden yellow horns, mane, tailfin, sail boom
    if r >= 195 and g >= 150 and b <= 95:
        return 12      # bright gold
    # Olive-gold horn/tailfin outline (Dervilacus RGB 155,140,55) -> crisp outline!
    if r >= 120 and g >= 110 and b <= 75:
        return 9
    # Blues (lion eye glint on Dervilacus side head) -> teal highlight
    if b > r + 20 and b > 100:
        return 15
    # Reds & dark crimson hull
    if r >= 185 and g <= 90:
        return 11      # bright King of Red Lions red
    if r >= 135 and g <= 75:
        return 10      # medium/dark crimson hull shade
    # Dark brown/crimson outlines (109,36,24 / 120,39,24 / 94,74,9)
    return 9


def quantize_link_pixel(rgb: tuple[int, int, int]) -> int:
    """Map a Dervilacus seated Minish Cap Link pixel to ALTTP Link SP-7 (1..14)."""
    r, g, b = rgb
    # Crisp dark outline (including Minish Cap's darkest brown outer outline 102,51,0)
    if max(r, g, b) < 55 or (r <= 110 and g <= 60 and b <= 20):
        return 5
    # Blue eyes
    if b >= 140 and b > r + 40 and b > g + 30:
        return 8
    # White eye highlight
    if r >= 220 and g >= 220 and b >= 220:
        return 1
    # Green tunic & cap -> map strictly to tunic indices 9,10,11,12 so Blue/Red Mail swaps cleanly!
    if g >= r + 15 and g >= b + 10:
        if g < 90:
            return 9   # dark tunic/cap outline
        if g < 135:
            return 11  # mid-dark tunic/cap
        if r >= 90 or g >= 175:
            return 10  # bright highlight green
        return 12      # primary tunic green
    # Minish Cap peach skin tones -> ALTTP Link SP-7 light/shade skin (4 / 3)!
    if r >= 220 and 135 <= g <= 185 and 75 <= b <= 125:
        return 4 if r >= 236 else 3
    # Bright golden-yellow hair & cap band (matches OoS Link SP-7[2] yellow + SP-7[6] gold!)
    if r >= 195 and g >= 145 and b <= 80:
        return 2
    if r >= 145 and g >= 140 and b <= 25:
        return 6
    # Hair midtone / shading: warm gold (6) & hair brown (13/14)
    non_tunic = (2, 3, 4, 5, 6, 7, 13, 14)
    best_i = 6
    best_d = 10**9
    for idx in non_tunic:
        pr, pg, pb = LINK_SP7_GREEN_RGB[idx]
        d = (r - pr) ** 2 * 2 + (g - pg) ** 2 * 3 + (b - pb) ** 2
        if d < best_d:
            best_d = d
            best_i = idx
    return best_i


# ---------------------------------------------------------------------------
# Integer pixel-grid helpers
# ---------------------------------------------------------------------------
Grid = list[list[int]]


def new_grid(w: int, h: int, fill: int = 0) -> Grid:
    return [[fill] * w for _ in range(h)]


def crop_quantize(
    im: Image.Image,
    box: tuple[int, int, int, int],
    bg: tuple[int, int, int, int],
    quantizer,
    *,
    hflip: bool = False,
    flood_bg: bool = True,
) -> Grid:
    """Crop, optionally flood-fill exterior bg so enclosed white/gray fills stay opaque, and quantize."""
    sub = im.crop(box)
    if hflip:
        sub = sub.transpose(Image.FLIP_LEFT_RIGHT)
    w, h = sub.size
    px = sub.load()
    exterior = [[False] * w for _ in range(h)]
    if flood_bg:
        # Pad conceptually with a 1px virtual bg border so all 4 edges seed the exterior flood-fill.
        stack: list[tuple[int, int]] = []
        for x in range(w):
            for y in (0, h - 1):
                if px[x, y] == bg and not exterior[y][x]:
                    exterior[y][x] = True
                    stack.append((x, y))
        for y in range(h):
            for x in (0, w - 1):
                if px[x, y] == bg and not exterior[y][x]:
                    exterior[y][x] = True
                    stack.append((x, y))
        while stack:
            cx, cy = stack.pop()
            for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                nx, ny = cx + dx, cy + dy
                if 0 <= nx < w and 0 <= ny < h and not exterior[ny][nx] and px[nx, ny] == bg:
                    exterior[ny][nx] = True
                    stack.append((nx, ny))
    else:
        for y in range(h):
            for x in range(w):
                if px[x, y] == bg:
                    exterior[y][x] = True

    g = new_grid(w, h)
    for y in range(h):
        for x in range(w):
            c = px[x, y]
            if not exterior[y][x] and c[3] >= 128:
                g[y][x] = quantizer((c[0], c[1], c[2]))
    return g


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


def slice_cols(g: Grid, col_ranges: Sequence[tuple[int, int]]) -> Grid:
    out: Grid = []
    for row in g:
        new_row: list[int] = []
        for a, b in col_ranges:
            new_row.extend(row[a:b])
        out.append(new_row)
    return out


def slice_rows(g: Grid, row_ranges: Sequence[tuple[int, int]]) -> Grid:
    out: Grid = []
    for a, b in row_ranges:
        for y in range(a, b):
            out.append(list(g[y]))
    return out


def add_keel_foam(hull: Grid, y_row: int, segments: Sequence[tuple[int, int, int]]) -> Grid:
    """Clone hull and paint crisp white/silver/teal wave-crest water foam along keel."""
    g = [list(r) for r in hull]
    h, w = len(g), len(g[0])
    for x0, x1, col in segments:
        if 0 <= y_row < h:
            for x in range(max(0, x0), min(w, x1)):
                g[y_row][x] = col
    return g


def shift_grid(g: Grid, dx: int, dy: int) -> Grid:
    h, w = len(g), len(g[0])
    out = new_grid(w, h)
    blit(out, g, dx, dy)
    return out


def trim_to_box(g: Grid, w: int, h: int, ox: int = 0, oy: int = 0) -> Grid:
    out = new_grid(w, h)
    blit(out, g, ox, oy)
    return out


# ---------------------------------------------------------------------------
# Boat Hull + Seated Link + Wind Waker Sail compaction from red lion.png
# ---------------------------------------------------------------------------
def build_side_hull_pair(im: Image.Image, bg: tuple[int, int, int, int]) -> tuple[Grid, Grid]:
    """Compact Dervilacus's empty_ext_L_68 (73x42 -> H-flipped Right) into 46x32.

    Preserves 100% pixel-exact dragon-lion head, golden antlers, full curved red
    hull body with clean horizontal cockpit for seated Link, white gunwale trim,
    and stern + golden tailfin, fitting cleanly into 4 x 16x16 tiles (512 B total).
    """
    raw = crop_quantize(im, (86, 293, 159, 335), bg, quantize_boat_pixel, hflip=True, flood_bg=True)
    # Horizontal (73 -> 46 px):
    #   0..17  (17px): full golden tailfin, curved stern, white rear gunwale
    #   23..29 ( 6px): straight horizontal white gunwale + crimson midship cockpit!
    #   47..54 ( 7px): curved red bow prow + neck base
    #   57..73 (16px): full 16px dragon-lion head, eye, snout & golden antler-horn
    comp_x = slice_cols(raw, [(0, 17), (23, 29), (47, 54), (57, 73)])
    assert len(comp_x[0]) == 46
    # Vertical (42 -> 32 px):
    #   y=0..3   ( 4px): golden antler-horn tip
    #   y=10..28 (19px): 100% UNMODIFIED Lion Face, Eye, Snout, Neck & Stern Curl!
    #   y=30..33 ( 4px): white gunwale & prow curve
    #   y=35..40 ( 5px): full curved crimson hull, golden tailfin & dark keel!
    comp = slice_rows(comp_x, [(0, 4), (10, 29), (30, 34), (35, 40)])
    assert len(comp) == 32, len(comp)
    hull_a = trim_to_box(comp, 46, 32, ox=0, oy=0)
    # Ensure Piece 0 (30, 0) covers 100% of upper head pixels (x=30..45, y=0..15) cleanly
    # and connect the lion's chin/neck seamlessly into the red bow at x=28..32, y=16..20!
    for y in range(16):
        for x in range(30):
            hull_a[y][x] = 0
    # Paint crisp 2px crimson-and-white diagonal neck bridge at (28..31, 16..18) joining head to bow
    for nx, ny, col in (
        (29, 16, 9), (30, 16, 13), (31, 16, 11), (32, 16, 9),
        (28, 17, 9), (29, 17, 11), (30, 17, 10), (31, 17, 9),
        (28, 18, 9), (29, 18, 11), (30, 18, 10), (31, 18, 9),
    ):
        hull_a[ny][nx] = col

    # Frame B: gentle -1px wave bob with crisp animated ocean foam along waterline (rows 30..31)
    hull_b = shift_grid(hull_a, 0, -1)
    hull_a = add_keel_foam(hull_a, 31, [(8, 15, 13), (18, 25, 14), (28, 36, 13)])
    hull_b = add_keel_foam(hull_b, 30, [(6, 13, 13), (16, 23, 14), (26, 35, 13), (36, 41, 15)])
    hull_b = add_keel_foam(hull_b, 31, [(3, 9, 14), (11, 20, 13), (27, 37, 13)])
    return hull_a, hull_b


def build_down_hull_pair(im: Image.Image, bg: tuple[int, int, int, int]) -> tuple[Grid, Grid]:
    """Compact Dervilacus's down_empty (21x51) into 22x38 (exact 1+2+1 boat tiling!)."""
    raw = crop_quantize(im, (284, 293, 305, 344), bg, quantize_boat_pixel)
    # raw is 21x51:
    #   y=0..12:  stern rim & backrest (13 px)
    #   y=13..25: straight empty deck interior (13 px -> slice out!)
    #   y=26..50: full front-facing horned lion head & prow (25 px)
    comp = slice_rows(raw, [(0, 12), (25, 51)])  # 12 + 26 = 38 px tall!
    hull_a = trim_to_box(comp, 22, 38, ox=1, oy=0)
    hull_b = shift_grid(hull_a, 0, -1)
    # Animated ocean wake foam flanking the bow & sides on Frame B, subtle on Frame A
    hull_a = add_keel_foam(hull_a, 36, [(4, 8, 13), (14, 18, 13)])
    hull_a = add_keel_foam(hull_a, 37, [(6, 16, 14)])
    hull_b = add_keel_foam(hull_b, 35, [(2, 6, 13), (16, 20, 13)])
    hull_b = add_keel_foam(hull_b, 36, [(4, 9, 14), (13, 18, 14)])
    hull_b = add_keel_foam(hull_b, 37, [(6, 16, 13)])
    return hull_a, hull_b


def build_up_hull_pair(im: Image.Image, bg: tuple[int, int, int, int]) -> tuple[Grid, Grid]:
    """Compact Dervilacus's up_empty (23x63) into 23x38 (exact 1+2+1 boat tiling!)."""
    raw = crop_quantize(im, (298, 175, 321, 238), bg, quantize_boat_pixel)
    # raw is 23x63:
    #   y=0..17:  full golden-horned lion head pointing north (18 px)
    #   y=18..42: long thin neck & empty deck (25 px -> slice out!)
    #   y=43..62: full curved stern + white trim + golden tailfin (20 px)
    comp = slice_rows(raw, [(0, 17), (42, 63)])  # 17 + 21 = 38 px tall!
    hull_a = trim_to_box(comp, 23, 38, ox=0, oy=0)
    hull_b = shift_grid(hull_a, 0, -1)
    # Trailing stern wake foam behind golden tailfin
    hull_a = add_keel_foam(hull_a, 36, [(4, 8, 13), (15, 19, 13)])
    hull_a = add_keel_foam(hull_a, 37, [(6, 10, 14), (13, 17, 14)])
    hull_b = add_keel_foam(hull_b, 35, [(2, 6, 13), (17, 21, 13)])
    hull_b = add_keel_foam(hull_b, 36, [(5, 10, 13), (13, 18, 13)])
    hull_b = add_keel_foam(hull_b, 37, [(7, 16, 14)])
    return hull_a, hull_b


def build_riders(im: Image.Image, bg: tuple[int, int, int, int]) -> dict[str, Grid]:
    """Extract Dervilacus's Minish Cap seated Link sprites into 16x16 SP-7 tiles."""
    # Down seated Link: x=436..452, y=68..86 (16x18 -> take top 16 rows = full cap+face+tunic+hands!)
    down_raw = crop_quantize(im, (436, 68, 452, 84), bg, quantize_link_pixel)
    # Up seated Link: x=494..510, y=68..86 (16x18 -> top 16 rows = full cap+shoulders+hands!)
    up_raw = crop_quantize(im, (494, 68, 510, 84), bg, quantize_link_pixel)
    # Right seated Link: x=474..492, y=68..86 (18x18 -> trim 1px left, 1px right, top 16 rows!)
    side_raw = crop_quantize(im, (475, 68, 491, 84), bg, quantize_link_pixel)
    return {
        "down": trim_to_box(down_raw, 16, 16),
        "up": trim_to_box(up_raw, 16, 16),
        "side": trim_to_box(side_raw, 16, 16),
    }


def parse_sail_art(rows: Sequence[str]) -> Grid:
    """Parse crisp hand-compacted 24x32 Wind Waker sail art (SP-3[9..15])."""
    legend = {
        ".": 0,   # transparent
        "k": 9,   # deep outline
        "d": 10,  # crimson tie / grommet shade
        "r": 11,  # crimson Wind Waker corner pennant / ring
        "g": 12,  # golden horizontal boom & spar tips
        "w": 13,  # crisp billowing white canvas
        "s": 14,  # silver-gray sail fold shadow
        "t": 15,  # iconic Wind Waker emerald-teal mast & spiral swirl!
    }
    assert len(rows) == 32, f"Expected 32 sail rows, got {len(rows)}"
    grid: Grid = []
    for r_idx, r in enumerate(rows):
        assert len(r) == 24, f"Row {r_idx}: expected 24 cols, got {len(r)}"
        grid.append([legend[ch] for ch in r])
    return grid


# ---------------------------------------------------------------------------
# Hand-compacted Wind Waker Sail frames (24x32 -> 2x16x16 + 1x8x16 = 320 B!)
# Faithfully modeled after Dervilacus's sail_alone_R/D/U with the iconic
# emerald-teal spiral swirl, vertical teal mast, crimson grommets & gold boom!
# ---------------------------------------------------------------------------

# SIDE SAIL (Right facing: mast on right/prow side x=15..18, canvas billowing aft/forward!)
# Wait: in Dervilacus's sail_right_boat (377..450, 510..579), look at korl_crops.png:
# The emerald mast rises vertically in front of Link, with the billowing white Wind Waker
# sail puffing OUT FORWARD to the right (wind catching the back of the sail!) and tapering
# back toward Link behind the mast! Let's capture that exact Wind Waker silhouette!
SAIL_SIDE_A = [
    ".........kkk............",
    "........ktttk...........",
    "........krttkk..........",
    "........krtkwwk.........",
    "........kkttwswk........",
    "........kttwwwswk.......",
    "........kttwwwwswk......",
    "........kttwwttwswk.....",
    "........kttwtttwswk.....",
    "........kttwttwwwswk....",
    "........kttwtttwwwswk...",
    "......kswwttwwttwwwwswk.",
    ".....kswwwttwwwttwwwswk.",
    "....kswwwwttwwtttwwwswk.",
    "...kswwwwwttwtttwwwwswk.",
    "..kswwwwwwttwttwwwwwswk.",
    "..kswwwwwwttwwttwwwwswk.",
    "..kswwwwwwttwwwttwwwswk.",
    ".kswwwwwwwttwwtttwwwswk.",
    ".kswwwwwwwttwtttwwwwswk.",
    ".kswwwwwwwttwwtwwwwwswk.",
    ".kswwwwwwwttwwwwwwwwswk.",
    "kswwwwwwwwttwwwwwwwwswk.",
    "ksswwwwwwwttwwwwwwwsswk.",
    "kkrsssssssrtsssssssrkk..",
    "kkggggggggrkgggggggkk...",
    "kgggggggggttggggggkk....",
    "........kkttkkkkkk......",
    "........kttk............",
    "........kttk............",
    "........kttk............",
    "........kkkk............",
]

# Frame B: Wind gust catches the sail — canvas puffs +1..2px further forward & swirl shifts!
SAIL_SIDE_B = [
    ".........kkk............",
    "........ktttk...........",
    "........krttkk..........",
    "........krtkwwkk........",
    "........kkttwwswk.......",
    "........kttwwwwswk......",
    "........kttwwwwwswk.....",
    "........kttwwwttwswk....",
    "........kttwwtttwswk....",
    "........kttwwttwwwswk...",
    "........kttwwtttwwwswk..",
    ".....kswwwttwwwttwwwwswk",
    "....kswwwwttwwwwttwwwswk",
    "...kswwwwwttwwwtttwwwswk",
    "..kswwwwwwttwwtttwwwwswk",
    "..kswwwwwwttwwttwwwwwswk",
    ".kswwwwwwwttwwwttwwwwswk",
    ".kswwwwwwwttwwwwttwwwswk",
    ".kswwwwwwwttwwwtttwwwswk",
    ".kswwwwwwwttwwtttwwwwswk",
    "kswwwwwwwwttwwwtwwwwwswk",
    "kswwwwwwwwttwwwwwwwwwswk",
    "kswwwwwwwwttwwwwwwwwsswk",
    "ksswwwwwwwttwwwwwwwsswk.",
    "kkrsssssssrtsssssssrkk..",
    "kkggggggggrkgggggggkk...",
    "kgggggggggttggggggkk....",
    "........kkttkkkkkk......",
    "........kttk............",
    "........kttk............",
    "........kttk............",
    "........kkkk............",
]

# DOWN SAIL (Facing South: mast on left side of sail x=1..4, canvas billowing starboard!)
SAIL_DOWN_A = [
    "..kkk...................",
    ".ktttk..................",
    ".kttrkk.................",
    ".kttwwkk................",
    ".kttwwwsk...............",
    ".kttwwwwsk..............",
    ".kttwwwwwsk.............",
    ".kttwwttwwsk............",
    ".kttwttttwwsk...........",
    ".kttwttwwwswk...........",
    ".kttwwtttwwswk..........",
    ".kttwwwttwwwswk.........",
    ".kttwwwwttwwswk.........",
    ".kttwwwtttwwwswk........",
    ".kttwwttttwwwswk........",
    ".kttwwttwwwwwswk........",
    ".kttwwwttwwwwswk........",
    ".kttwwwwttwwwswk........",
    ".kttwwwtttwwwswk........",
    ".kttwwtttwwwwswk........",
    ".kttwwwtwwwwwwswk.......",
    ".kttwwwwwwwwwwwswk......",
    ".kttwwwwwwwwwwwsswk.....",
    ".kttsssssssssssssrkk....",
    ".krgggggggggggggggrk....",
    ".ktgggggggggggggggkk....",
    ".kttkkkkkkkkkkkkkkk.....",
    ".kttk...................",
    ".kttk...................",
    ".kttk...................",
    ".kttk...................",
    ".kkkk...................",
]

SAIL_DOWN_B = [
    "..kkk...................",
    ".ktttk..................",
    ".kttrkk.................",
    ".kttwwwkk...............",
    ".kttwwwwsk..............",
    ".kttwwwwwsk.............",
    ".kttwwwwwwsk............",
    ".kttwwwttwwsk...........",
    ".kttwwttttwwsk..........",
    ".kttwwttwwwswk..........",
    ".kttwwwtttwwswk.........",
    ".kttwwwwttwwwswk........",
    ".kttwwwwwttwwswk........",
    ".kttwwwwtttwwwswk.......",
    ".kttwwwttttwwwswk.......",
    ".kttwwwttwwwwwswk.......",
    ".kttwwwwttwwwwswk.......",
    ".kttwwwwwttwwwswk.......",
    ".kttwwwwtttwwwswk.......",
    ".kttwwwtttwwwwswk.......",
    ".kttwwwwtwwwwwwswk......",
    ".kttwwwwwwwwwwwwswk.....",
    ".kttwwwwwwwwwwwwsswk....",
    ".kttssssssssssssssrkk...",
    ".krggggggggggggggggrk...",
    ".ktggggggggggggggggkk...",
    ".kttkkkkkkkkkkkkkkkk....",
    ".kttk...................",
    ".kttk...................",
    ".kttk...................",
    ".kttk...................",
    ".kkkk...................",
]

# UP SAIL (Facing North: mast on right side of sail x=19..22, canvas billowing port!)
SAIL_UP_A = [row[::-1] for row in SAIL_DOWN_A]
SAIL_UP_B = [row[::-1] for row in SAIL_DOWN_B]


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
    """Encode 4 x 16x16 pieces into 512 bytes: 256B top row (8 tiles) + 256B bot row (8 tiles).

    Hardware $4302 auto-increment uploads top 256B -> $4000 and bot 256B -> $4100 in 2 bursts!
    """
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


# ---------------------------------------------------------------------------
# Master Sparse Asset Assembly (12 frames: 0..5 Cruise, 6..11 Sail Boost)
# ---------------------------------------------------------------------------
def build_all(source_png: Path) -> tuple[bytes, str, bytes, dict]:
    im = Image.open(source_png).convert("RGBA")
    bg = im.getpixel((0, 0))

    side_a, side_b = build_side_hull_pair(im, bg)
    down_a, down_b = build_down_hull_pair(im, bg)
    up_a, up_b = build_up_hull_pair(im, bg)
    riders = build_riders(im, bg)

    sail_side_a = parse_sail_art(SAIL_SIDE_A)
    sail_side_b = parse_sail_art(SAIL_SIDE_B)
    sail_down_a = parse_sail_art(SAIL_DOWN_A)
    sail_down_b = parse_sail_art(SAIL_DOWN_B)
    sail_up_a = parse_sail_art(SAIL_UP_A)
    sail_up_b = parse_sail_art(SAIL_UP_B)

    # Hull 4x16x16 tiling coordinates (relative to hull top-left):
    #   Down (22x38): 1+2+1 tapered boat layout (0..22 x 0..38)
    #   Up   (23x38): 1+2+1 tapered boat layout (0..23 x 0..38)
    #   Side (46x30): Lion Head top-right + 3 lower hull tiles (0..46 x 0..30)
    HULL_PIECES = {
        "down": [(3, 0), (0, 12), (16, 12), (3, 22)],
        "up":   [(3, 0), (0, 16), (16, 16), (3, 24)],
        "side": [(30, 0), (0, 16), (16, 16), (30, 16)],
    }
    HULL_DIMS = {
        "down": (22, 38),
        "up":   (23, 38),
        "side": (46, 32),
    }
    # Rider 16x16 placement relative to hull top-left (facing Right for side; auto-mirrored for Left!)
    RIDER_POS = {
        "down": (3, 0),    # Seated in stern looking South above lion prow
        "up":   (3, 15),   # Seated in cockpit facing North behind lion prow
        "side": (14, 9),   # Centered cleanly in midship cockpit between rear & front gunwale rims!
    }
    # Sail 24x32 placement relative to hull top-left:
    SAIL_NARROW_Y = {
        "down": 11,  # rows 11..26 cover full right billowing wing + gold boom tip
        "up":   11,  # symmetric! (for Up, mast is on right so x=8..23 main + x=0..7 narrow)
        "side": 11,  # rows 11..26 cover full trailing sail corner & boom!
    }
    # Sail anchor (ox, oy) relative to hull top-left
    SAIL_ANCHOR = {
        "down": (12, -16),  # rises beside Link on starboard, leaving Link & Lion Head 100% clear!
        "up":   (-12, -15), # rises on port side above cockpit, leaving Lion Head & Link clear!
        "side": (17, -19),  # mast planted cleanly ahead of Link, Wind Waker sail towering clear above cap!
    }

    # Verify ZERO pixels lost on narrow 8x16 sail edges (check full sail coverage!)
    # For Down/Side, main 16x16s cover x=0..15, y=0..31; narrow covers x=16..23, y=ny..ny+15.
    # For Up (mirrored), main 16x16s cover x=8..23, y=0..31; narrow covers x=0..7, y=ny..ny+15.
    def sail_piece_coords(dir_key: str) -> tuple[tuple[int, int], tuple[int, int], tuple[int, int]]:
        ny = SAIL_NARROW_Y[dir_key]
        if dir_key in ("up", "side"):
            return (8, 0), (8, 16), (0, ny)
        return (0, 0), (0, 16), (16, ny)

    # Deduplicated 4BPP binary dictionary
    dictionary = bytearray()
    blob_offsets: dict[bytes, int] = {}

    def intern(blob: bytes) -> int:
        if blob not in blob_offsets:
            blob_offsets[blob] = len(dictionary)
            dictionary.extend(blob)
        return blob_offsets[blob]

    # Validate SP-3 palette purity on hulls & sails (only 0 or 9..15 allowed!)
    for name, g in [
        ("side_a", side_a), ("side_b", side_b),
        ("down_a", down_a), ("down_b", down_b),
        ("up_a", up_a), ("up_b", up_b),
        ("sail_side_a", sail_side_a), ("sail_side_b", sail_side_b),
        ("sail_down_a", sail_down_a), ("sail_down_b", sail_down_b),
        ("sail_up_a", sail_up_a), ("sail_up_b", sail_up_b),
    ]:
        for y, row in enumerate(g):
            for x, v in enumerate(row):
                assert v == 0 or 9 <= v <= 15, f"{name} ({x},{y}) invalid SP-3 idx {v}"

    # Verify narrow sail slices don't drop pixels outside [ny..ny+15]
    for dkey, sgrid in [
        ("down", sail_down_a), ("down", sail_down_b),
        ("up", sail_up_a), ("up", sail_up_b),
        ("side", sail_side_a), ("side", sail_side_b),
    ]:
        _, _, (nx, ny) = sail_piece_coords(dkey)
        for y in range(32):
            if ny <= y < ny + 16:
                continue
            for x in range(nx, nx + 8):
                # Trim any stray 1-2px tip outside the 16px narrow band cleanly
                assert sgrid[y][x] == 0, f"Sail {dkey} has pixel at ({x},{y}) outside narrow band y={ny}..{ny+15}"

    # Build the 12 frames (0..5 Cruise, 6..11 Sail Boost)
    frame_specs = [
        # (dir_key, hull_grid, sail_grid_or_None, bob_dy)
        ("down", down_a, None,        0),  # 0: Down Cruise A
        ("down", down_b, None,       -1),  # 1: Down Cruise B
        ("up",   up_a,   None,        0),  # 2: Up Cruise A
        ("up",   up_b,   None,       -1),  # 3: Up Cruise B
        ("side", side_a, None,        0),  # 4: Side Cruise A
        ("side", side_b, None,       -1),  # 5: Side Cruise B
        ("down", down_a, sail_down_a, 0),  # 6: Down Sail Boost A
        ("down", down_b, sail_down_b,-1),  # 7: Down Sail Boost B
        ("up",   up_a,   sail_up_a,   0),  # 8: Up Sail Boost A
        ("up",   up_b,   sail_up_b,  -1),  # 9: Up Sail Boost B
        ("side", side_a, sail_side_a, 0),  # 10: Side Sail Boost A
        ("side", side_b, sail_side_b,-1),  # 11: Side Sail Boost B
    ]

    frame_meta = []
    # Reserve dummy zero offset for "no sail" pointer ($0000 = unused when HasSail == 0)
    for dkey, hgrid, sgrid, bob_dy in frame_specs:
        hp = HULL_PIECES[dkey]
        hull_off = intern(encode_group0_4x16(hgrid, hp))
        rider_off = intern(encode_16x16(riders[dkey], 0, 0))
        if sgrid is not None:
            sc0, sc1, scn = sail_piece_coords(dkey)
            sail0_off = intern(encode_16x16(sgrid, sc0[0], sc0[1]))
            sail1_off = intern(encode_16x16(sgrid, sc1[0], sc1[1]))
            sailn_off = intern(encode_narrow_8x16(sgrid, scn[0], scn[1]))
            has_sail = 1
            sox, soy = SAIL_ANCHOR[dkey]
            sail_screen_coords = [
                (sox + sc0[0], soy + sc0[1] + bob_dy),
                (sox + sc1[0], soy + sc1[1] + bob_dy),
                (sox + scn[0], soy + scn[1] + bob_dy),
            ]
        else:
            sail0_off = sail1_off = sailn_off = 0
            has_sail = 0
            sail_screen_coords = [(0, 0), (0, 0), (0, 0)]

        w, h = HULL_DIMS[dkey]
        rx, ry = RIDER_POS[dkey]
        frame_meta.append({
            "dir": dkey,
            "width": w,
            "height": h,
            "has_sail": has_sail,
            "rider_x": rx,
            "rider_y": ry + bob_dy,
            "pieces": hp,
            "sail_coords": sail_screen_coords,
            "ptrs": (hull_off, rider_off, sail0_off, sail1_off, sailn_off),
            "hull_grid": hgrid,
            "rider_grid": riders[dkey],
            "sail_grid": sgrid,
            "bob_dy": bob_dy,
        })

    # Verify VBlank DMA budget across ALL 12 x 12 frame transitions (<= 960 B!)
    max_dma = 0
    for old_f in [None, *range(len(frame_meta))]:
        for new_f, fm in enumerate(frame_meta):
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

    # Emit ASM tables (10-byte stride per frame in KORL_Frame_GroupPointers)
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


def render_preview(meta: dict, out_path: Path) -> None:
    """Render all 12 frames + Left H-flip + Blue/Red Mail tunics over Lyra Sea blue."""
    frames = meta["frames"]
    # Render 16 panels: 6 Cruise (D/U/R/L + bob) + 6 Sail Boost (D/U/R/L + bob) + Mail checks
    ocean = (32, 96, 176, 255)
    cw, ch = 104, 92
    scale = 3
    # Grid: 4 rows x 4 cols
    panels = [
        ("0: Down Cruise A", 0, False, LINK_SP7_GREEN_RGB),
        ("1: Down Cruise B", 1, False, LINK_SP7_GREEN_RGB),
        ("2: Up Cruise A",   2, False, LINK_SP7_GREEN_RGB),
        ("3: Up Cruise B",   3, False, LINK_SP7_GREEN_RGB),
        ("4: Right Cruise A", 4, False, LINK_SP7_GREEN_RGB),
        ("5: Left Cruise A (HFlip)", 4, True, LINK_SP7_GREEN_RGB),
        ("6: Right Cruise B", 5, False, LINK_SP7_BLUE_RGB),
        ("7: Left Cruise B (RedMail)", 5, True, LINK_SP7_RED_RGB),
        ("8: Down Sail A",   6, False, LINK_SP7_GREEN_RGB),
        ("9: Down Sail B",   7, False, LINK_SP7_GREEN_RGB),
        ("10: Up Sail A",    8, False, LINK_SP7_GREEN_RGB),
        ("11: Up Sail B",    9, False, LINK_SP7_GREEN_RGB),
        ("12: Right Sail A", 10, False, LINK_SP7_GREEN_RGB),
        ("13: Left Sail A (HFlip)", 10, True, LINK_SP7_GREEN_RGB),
        ("14: Right Sail B (Blue)", 11, False, LINK_SP7_BLUE_RGB),
        ("15: Left Sail B (Red)",   11, True, LINK_SP7_RED_RGB),
    ]
    out = Image.new("RGBA", (4 * cw * scale, 4 * ch * scale), (20, 40, 72, 255))
    draw = ImageDraw.Draw(out)

    for idx, (label, fidx, hflip, link_pal) in enumerate(panels):
        m = frames[fidx]
        canvas = Image.new("RGBA", (cw, ch), ocean)
        # Subtle horizontal ocean wave shimmer lines
        for wy in range(10, ch, 16):
            for wx in range((wy * 3) % 16, cw, 24):
                for dx in range(5):
                    if wx + dx < cw:
                        canvas.putpixel((wx + dx, wy), (48, 120, 200, 255))

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

        # Painter's order (back -> front) matching SNES OAM priority in KORL_DrawPlayerOam_Long:
        #   - Down/Up: Hull behind Rider (Link sits atop open interior deck), Sail in front
        #   - Side:    Rider behind Hull (white gunwale & red hull overlap Link's waist!), Sail in front
        rx = bx + mirror_x(m["rider_x"], 16)
        ry = by + m["rider_y"]
        if m["dir"] == "side":
            paint_grid(m["rider_grid"], rx, ry, link_pal, hflip)
            paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
        else:
            paint_grid(m["hull_grid"], bx, by, KORL_SP3_RGB, hflip)
            paint_grid(m["rider_grid"], rx, ry, link_pal, hflip)
        if m["sail_grid"] is not None:
            sx = bx + mirror_x(m["sail_coords"][0][0] if m["dir"] == "down" else m["sail_coords"][2][0], 24)
            sy = by + m["sail_coords"][0][1]
            paint_grid(m["sail_grid"], sx, sy, KORL_SP3_RGB, hflip)

        r_idx, c_idx = divmod(idx, 4)
        scaled = canvas.resize((cw * scale, ch * scale), Image.NEAREST)
        x0, y0 = c_idx * cw * scale, r_idx * ch * scale
        out.paste(scaled, (x0, y0))
        draw.rectangle([x0, y0, x0 + cw * scale - 1, y0 + 18], fill=(12, 24, 48, 220))
        draw.text((x0 + 6, y0 + 3), label, fill=(248, 248, 248, 255))

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out.save(out_path)


def check_existing_artifacts() -> None:
    """Structural verification usable even when external source PNG is absent."""
    raw = OUT_4BPP.read_bytes()
    pal = OUT_PAL.read_bytes()
    tbl = OUT_TABLES.read_text()
    assert len(pal) == 14, f"Expected 14-byte SP-3[9..15] palette, got {len(pal)}"
    assert len(raw) > 0 and len(raw) % 64 == 0, f"Unexpected sparse 4bpp length {len(raw)}"
    assert "!KORL_FrameCount      = 12" in tbl
    assert f"!KORL_DictionaryBytes = {len(raw)}" in tbl
    assert "KORL_Frame_GroupPointers:" in tbl


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Source red lion.png")
    ap.add_argument("--check", action="store_true", help="Verify generated artifacts match source deterministically")
    ap.add_argument("--preview", type=Path, default=None, help="Write zoomed RGBA preview sheet")
    args = ap.parse_args(argv)

    if not args.source.is_file():
        if args.check:
            check_existing_artifacts()
            print(f"[ok] Source PNG not present ({args.source}); verified committed KORL artifacts structurally.")
            return 0
        print(f"ERROR: Source PNG not found: {args.source}", file=sys.stderr)
        return 1

    raw_4bpp, asm_text, pal_bytes, meta = build_all(args.source)

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
            f"[ok] KORL art verified: {len(raw_4bpp)} B sparse 4BPP, "
            f"{len(pal_bytes)} B SP-3 palette, max NMI DMA = {meta['max_dma']} B (<= 960 B)."
        )
        return 0

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    OUT_4BPP.write_bytes(raw_4bpp)
    OUT_TABLES.write_text(asm_text)
    OUT_PAL.write_bytes(pal_bytes)
    print(
        f"[ok] Generated KORL art: {OUT_4BPP.name} ({len(raw_4bpp)} B), "
        f"{OUT_TABLES.name}, {OUT_PAL.name} ({len(pal_bytes)} B), "
        f"max NMI DMA = {meta['max_dma']} B (<= 960 B)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
