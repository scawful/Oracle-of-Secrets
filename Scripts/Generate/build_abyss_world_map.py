#!/usr/bin/env python3
"""Build the Eon Abyss Mode 7 world map in authentic GBC Oracle of Ages/Seasons style.

Generates the three SNES Mode 7 world-map binaries consumed by Overworld/world_map.asm:

  Overworld/world_map/DwMapTileset.bin   4096 B (64x64 tilemap in 4x 32x32 quadrants)
  Overworld/world_map/DwMapGfx.bin       16384 B (256 8x8 8bpp Mode 7 tiles, idx 1..127)
  Overworld/world_map/dw_palette.bin     256 B (128 BGR555 colors)

Hardware contract (matching LwMap and SwMap in Overworld/world_map.asm):
  * Central 32x32 tiles (tx=16..47, ty=16..47; 256x256 px) hold the full 8x8-screen
    Eon Abyss ($40-$7F) at exact 1:16 world scale (world_coord // 16), matching
    WorldMap_CalculateOAMCoordinates ($0AC38A) and all 457d8fcb marker pins.
  * Outer 16-tile frame (tx/ty outside 16..47) uses the exact 9 vanilla ALTTP
    folded-parchment border tiles ($0C,$0D,$0E,$1C,$1D,$1E,$1F,$2C,$2D) and
    parchment palette slots (7, 56, 68), plus tile $EF set to matching parchment
    fill for WorldMap_FillTilemapWithEF ($0ABDA5).
  * Central 1,024 tiles are authored from an organic curved GBC autotile & miniature
    landmark atlas fitting natively inside the 246-tile SNES Mode 7 content budget
    with zero (or near-zero) quantization loss.

Usage:
  python3 Scripts/Generate/build_abyss_world_map.py
  python3 Scripts/Generate/build_abyss_world_map.py --check
  python3 Scripts/Generate/build_abyss_world_map.py --preview /tmp/abyss-map.png
"""

from __future__ import annotations

import argparse
import heapq
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "Overworld" / "world_map"
TILESET_PATH = OUT_DIR / "DwMapTileset.bin"
GFX_PATH = OUT_DIR / "DwMapGfx.bin"
PAL_PATH = OUT_DIR / "dw_palette.bin"

MAP_TILES = 64
CENTER_START = 16
CENTER_TILES = 32
CENTER_PX = CENTER_TILES * 8  # 256x256 central map at 1:16 world scale

TILESET_SIZE = 4096
GFX_SIZE = 16384
PAL_SIZE = 256

# Reserved hardware border tiles matching LwMap/SwMap + WorldMap_FillTilemapWithEF ($0ABDA5)
BORDER_FILL_EF = 0xEF
VANILLA_FRAME_TILES = (0x0C, 0x0D, 0x0E, 0x1C, 0x1D, 0x1E, 0x1F, 0x2C, 0x2D)
RESERVED_TILES = frozenset(VANILLA_FRAME_TILES) | {BORDER_FILL_EF}
CONTENT_TILE_SLOTS = tuple(i for i in range(256) if i not in RESERVED_TILES)
MAX_CONTENT_TILES = len(CONTENT_TILE_SLOTS)  # 246

# Live Overworld/world_map.asm (457d8fcb) Eon Abyss marker coordinates.
# World (0..4095) -> central 256x256 pixel = (wx // 16, wy // 16).
MARKERS_WORLD: dict[str, tuple[int, int]] = {
    "sword": (0x02C0, 0x00A0),     # $41 Master Sword clearing -> (44, 10)
    "shield": (0x0100, 0x0500),    # $50 Forest of Dreams clearing -> (16, 80)
    "fortress": (0x08A0, 0x0240),  # $4C Fortress of Secrets north gate -> (138, 36)
    "pyramid": (0x0F70, 0x04F0),   # $57 Final Boss volcanic pit rim -> (247, 79)
    "escape": (0x04F4, 0x0B0E),    # $6A Eon Escape meadow glade -> (79, 176)
}
MARKERS_PX: dict[str, tuple[int, int]] = {
    name: (wx >> 4, wy >> 4) for name, (wx, wy) in MARKERS_WORLD.items()
}

# ---------------------------------------------------------------------------
# Palette (128 BGR555 slots; 0 = Mode 7 backdrop; 7/56/68 = ALTTP parchment)
# ---------------------------------------------------------------------------
PARCH_BASE = 7
PARCH_MID = 56
PARCH_LINE = 68

INK_DARK = 1
INK_BROWN = 2
INK_FOREST = 3
INK_SLATE = 4

SEA_ABYSS = 5
SEA_DEEP = 6
SEA_MID = 8
SEA_SHALLOW = 9
SEA_FOAM = 10
CORAL_DARK = 11
CORAL_MID = 12
CORAL_HI = 13
RUIN_SEA = 14
RUIN_SEA_HI = 15

GRASS_HI = 16
GRASS_MID = 17
GRASS_SH = 18
LEAF_HI = 19
LEAF_MID = 20
LEAF_DEEP = 21
MYSTIC_HI = 22
MYSTIC_MID = 23
MYSTIC_DARK = 24

SWAMP_WATER = 25
SWAMP_SHALLOW = 26
SWAMP_MOSS = 27
SWAMP_DARK = 28

PATH_HI = 29
PATH_MID = 30
PATH_SH = 31
WOOD_HI = 32
WOOD_DARK = 33

CLIFF_TOP = 34
CLIFF_FACE = 35
CLIFF_DARK = 36
SLATE_HI = 37
SLATE_MID = 38
SLATE_DARK = 39
OBS_MID = 40
OBS_DARK = 41

VOLC_TOP = 42
VOLC_FACE = 43
VOLC_DARK = 44
LAVA_CORE = 45
LAVA_BRIGHT = 46
LAVA_MID = 47
LAVA_CRUST = 48

SAND_HI = 49
SAND_MID = 50
SAND_SH = 51
SAND_DARK = 52

GOLD_HI = 53
GOLD_MID = 54
GOLD_SH = 55
FORT_GREEN_HI = 57
FORT_GREEN = 58
FORT_WALL = 59
ROOF_RED = 60
ROOF_RED_SH = 61
ROOF_BLUE = 62
CREAM = 63
PALM_GREEN = 64
VOLC_CRAG = 65

PALETTE_ENTRIES: dict[int, tuple[int, int, int]] = {
    0: (0, 0, 0),
    INK_DARK: (24, 16, 32),
    INK_BROWN: (64, 40, 24),
    INK_FOREST: (16, 56, 32),
    INK_SLATE: (40, 40, 64),
    SEA_ABYSS: (16, 40, 104),
    SEA_DEEP: (24, 64, 152),
    PARCH_BASE: (189, 139, 90),   # 0x2E37 exact vanilla parchment
    SEA_MID: (40, 112, 192),
    SEA_SHALLOW: (88, 184, 232),
    SEA_FOAM: (216, 248, 248),
    CORAL_DARK: (88, 48, 112),
    CORAL_MID: (168, 72, 136),
    CORAL_HI: (224, 136, 184),
    RUIN_SEA: (40, 88, 168),
    RUIN_SEA_HI: (72, 136, 208),
    GRASS_HI: (128, 200, 72),
    GRASS_MID: (80, 160, 56),
    GRASS_SH: (48, 120, 48),
    LEAF_HI: (96, 184, 64),
    LEAF_MID: (40, 136, 56),
    LEAF_DEEP: (24, 88, 48),
    MYSTIC_HI: (136, 112, 200),
    MYSTIC_MID: (80, 64, 144),
    MYSTIC_DARK: (40, 32, 88),
    SWAMP_WATER: (32, 96, 136),
    SWAMP_SHALLOW: (64, 144, 160),
    SWAMP_MOSS: (72, 144, 56),
    SWAMP_DARK: (24, 64, 96),
    PATH_HI: (232, 200, 136),
    PATH_MID: (192, 152, 96),
    PATH_SH: (144, 104, 64),
    WOOD_HI: (176, 120, 64),
    WOOD_DARK: (104, 56, 32),
    CLIFF_TOP: (192, 152, 96),
    CLIFF_FACE: (136, 88, 56),
    CLIFF_DARK: (88, 48, 32),
    SLATE_HI: (192, 192, 224),
    SLATE_MID: (136, 136, 176),
    SLATE_DARK: (88, 88, 128),
    OBS_MID: (64, 56, 96),
    OBS_DARK: (40, 32, 64),
    VOLC_TOP: (136, 56, 48),
    VOLC_FACE: (88, 32, 32),
    VOLC_DARK: (48, 16, 24),
    LAVA_CORE: (248, 232, 104),
    LAVA_BRIGHT: (248, 128, 32),
    LAVA_MID: (216, 64, 24),
    LAVA_CRUST: (160, 40, 24),
    SAND_HI: (248, 224, 152),
    SAND_MID: (224, 184, 104),
    SAND_SH: (184, 136, 72),
    SAND_DARK: (136, 96, 48),
    GOLD_HI: (248, 224, 96),
    GOLD_MID: (224, 168, 48),
    GOLD_SH: (168, 112, 32),
    PARCH_MID: (172, 123, 74),    # 0x25F5 exact vanilla parchment shadow
    FORT_GREEN_HI: (128, 208, 88),
    FORT_GREEN: (56, 152, 64),
    FORT_WALL: (200, 176, 104),
    ROOF_RED: (216, 64, 56),
    ROOF_RED_SH: (144, 32, 32),
    ROOF_BLUE: (64, 120, 216),
    CREAM: (248, 240, 216),
    PALM_GREEN: (72, 184, 64),
    VOLC_CRAG: (112, 40, 40),
    PARCH_LINE: (131, 90, 57),    # 0x1D70 exact vanilla parchment crease
}

EXACT_BGR555: dict[int, int] = {
    PARCH_BASE: 0x2E37,
    PARCH_MID: 0x25F5,
    PARCH_LINE: 0x1D70,
}


def rgb_to_bgr555(rgb: tuple[int, int, int]) -> int:
    r, g, b = rgb
    return ((b >> 3) << 10) | ((g >> 3) << 5) | (r >> 3)


def bgr555_to_rgb(word: int) -> tuple[int, int, int]:
    r = ((word & 0x1F) * 255) // 31
    g = (((word >> 5) & 0x1F) * 255) // 31
    b = (((word >> 10) & 0x1F) * 255) // 31
    return (r, g, b)


def build_palette_bytes() -> bytes:
    out = bytearray(PAL_SIZE)
    for idx, rgb in PALETTE_ENTRIES.items():
        word = EXACT_BGR555.get(idx, rgb_to_bgr555(rgb))
        out[idx * 2] = word & 0xFF
        out[idx * 2 + 1] = (word >> 8) & 0xFF
    return bytes(out)


def _palette_rgb_table(pal: bytes) -> list[tuple[int, int, int]]:
    return [bgr555_to_rgb(pal[i * 2] | (pal[i * 2 + 1] << 8)) for i in range(128)]


# ---------------------------------------------------------------------------
# 32x32 Organic GBC Tile Map Layout (Grounded on Real $40-$7F Geography!)
# ---------------------------------------------------------------------------
# Live 457d8fcb marker alignment:
#   sword    = (44, 10)  -> tile (5, 1)    [$41 Master Sword sacred clearing]
#   shield   = (16, 80)  -> tile (2, 10)   [$50 Forest of Dreams sanctuary]
#   fortress = (138, 36) -> tile (17, 4)   [$4C Fortress of Secrets North Gate]
#   pyramid  = (247, 79) -> tile (30, 9)   [$57 Final Boss volcanic pit rim]
#   escape   = (79, 176) -> tile (9, 22)   [$6A Eon Escape meadow glade]

BASE_MAP_ROWS: tuple[str, ...] = (
    #01234567890123456789012345678901   row
    "PPPPPPPPPPPKKKVKKKVKKVVKKKVVVVLV",  # 00  $40..$47
    "PPPPPPPPPPPKKKVVKKVVVVVKKVVVVLLV",  # 01
    "PPPPPPPPPPPVLVVVVVVLLLLLLVLLLLLV",  # 02
    "PPPPPPPPPPPVLLLVVVLLVVVVLLLVVLLV",  # 03
    "PPPPPPPPPPPPBBBBBBBBOOOOVVLLVLLV",  # 04  $48..$4F
    "PPPPPPPPPPPPBBBBBBBBOOOOVLLLLLLV",  # 05
    "PPPPPPPPPPPPBBBBBBBBOOOOVLLVVLLV",  # 06
    "PPPPPPPPPPPPBBBBBBBBOOOOVKKVLLVV",  # 07
    "MMMFFFFFGGGGBBBBBBBBOOOOKKKVLVVV",  # 08  $50..$57
    "MMMGFFFFGGFGBBBBBBBBOOOOVVLLVVLV",  # 09
    "MMGGGFFGGFFGBBBBBBBBOOOOVVLLLLLV",  # 10
    "MMGGFFFFFGGGGGGGGGGGOOOVVVVLLLVV",  # 11
    "MFGFFFFFGGFFGGGGGGFFGGEGGAAAGAAA",  # 12  $58..$5F  (organic curved Lupo peaks!)
    "FFGFFFFFGGFGGGGGGGGGGEEEAAAAAAAA",  # 13
    "FFGFFFFFGGGGGGGGGGGGGGEEAAAAAAAA",  # 14
    "FFGFFFFFGGFFGGGGGGGGGGGGGAAAGAAA",  # 15
    "FFFGGFFFGGGGFGGGGGGFGGGGAAAAAAAA",  # 16  $60..$67
    "FFFGFFFFGGGGGGGGGGGGGGEEAAAAAAAA",  # 17
    "FFFGFFFFGFGGGGGGGGGGGGEEAAAAAAAG",  # 18
    "FFFGFFFGGGGGGGGGGGGGGGEGGAAAAAGG",  # 19
    "FFFGFFFGGGGGGGWWWWWWGGEEEGHHHGGH",  # 20  $68..$6F  (curved Marsh + curved foothills!)
    "FFFGFFGGGGGWWIIWWWWWWGEEGGHHHHHH",  # 21
    "FFFFGGGGGGWWWWWWIWWWWGEEDDDHHHHH",  # 22
    "FFFFGGGGGGWWWIWWWWIWWGDDDDDDDDDD",  # 23
    "SSSSSSSGGGGWWWWWWWWSSSDDDDDDRRRD",  # 24  $70..$77  (curved coast + $76 turquoise bay!)
    "SSSSSSSSSSSSSSSSSSSSSSSSSSSDDRRD",  # 25             (Boardwalk crosses OPEN bay tx=25, ty=25..27!)
    "SSSSSSSSSSSSSSSSSSSSSSSSSSSDDRRD",  # 26
    "SSSSSSSSSSSSSSSSSSSSSSSSSSDRRRRD",  # 27
    "SSSSSSSSSSSSSSSSSSSSSSSSSDDRRRDD",  # 28  $78..$7F  (Smith's Beach palms tx=25..27, ty=28..30)
    "SSSSSSSSSSSSSSSSSSSSSSSSSDDRRRDD",  # 29
    "SSSSSSSSSSSSSSSSSSSSSSSSSDDDDDDD",  # 30
    "SSSSSSSSSSSSSSSSSSSSSSSSSSSSSDDD",  # 31
)

# Subtle organic dirt footpath segments (smooth 8-way curves!)
ROAD_PATHS: list[list[tuple[int, int]]] = [
    # NW Pyramids -> Sword clearing -> $42 -> $4A causeway -> Yesterwind North -> Windmill
    [(4, 6), (4, 3), (5, 2), (8, 2), (9, 3), (9, 4)],
    [(9, 7), (9, 10), (11, 12), (15, 12), (17, 14), (18, 15)],
    # Forest Shield ($50) -> $51 woodland pond bridge -> $52
    [(2, 10), (6, 10), (9, 10)],
    # Forest of Dreams sunlit trail -> $6A Escape glade -> Yesterwind -> East Canyon -> $76 Boardwalk!
    [(2, 11), (2, 15), (3, 16), (3, 21), (4, 22), (9, 22), (11, 20), (13, 18), (18, 18), (20, 18), (21, 19), (21, 22), (22, 23), (25, 23), (25, 28)],
    # Yesterwind -> Lupo Mountain South Pass
    [(18, 15), (22, 15), (24, 15)],
    # Yesterwind North -> Fortress South Approach
    [(15, 12), (15, 11)],
]


# ---------------------------------------------------------------------------
# Pure 8x8 Tile Art Generators (Compact, Lossless Autotiles <= 246!)
# ---------------------------------------------------------------------------
Tile = list[list[int]]


def _blank(color: int) -> Tile:
    return [[color] * 8 for _ in range(8)]


def _copy_tile(t: Tile) -> Tile:
    return [row[:] for row in t]


def _tile_ocean(parity: int = 0) -> Tile:
    t = _blank(SEA_DEEP)
    if parity & 1:
        t[2][2] = t[2][3] = SEA_MID
        t[3][3] = t[3][4] = SEA_ABYSS
    else:
        t[5][4] = t[5][5] = SEA_MID
        t[6][5] = t[6][6] = SEA_ABYSS
    return t


def _tile_grass(parity: int = 0) -> Tile:
    t = _blank(GRASS_MID)
    if parity & 1:
        t[2][2] = t[2][3] = GRASS_HI
        t[6][5] = GRASS_SH
    else:
        t[5][2] = t[5][3] = GRASS_HI
        t[1][6] = GRASS_SH
    return t


def _tile_slate(parity: int = 0, dark: bool = False) -> Tile:
    base = OBS_MID if dark else SLATE_MID
    hi = SLATE_MID if dark else SLATE_HI
    sh = OBS_DARK if dark else SLATE_DARK
    t = _blank(base)
    if parity & 1:
        t[1][2] = hi
        t[5][6] = sh
    else:
        t[5][1] = hi
        t[2][5] = sh
    return t


def _tile_volc(parity: int = 0) -> Tile:
    t = _blank(VOLC_FACE)
    if parity & 1:
        t[1][1] = t[2][2] = VOLC_TOP
        t[5][5] = VOLC_DARK
    else:
        t[5][2] = VOLC_TOP
        t[2][6] = VOLC_DARK
    return t


def _tile_sand(parity: int = 0) -> Tile:
    t = _blank(SAND_MID)
    if parity & 1:
        t[2][1] = t[2][2] = t[2][3] = SAND_HI
        t[3][2] = t[3][3] = SAND_SH
    else:
        t[5][4] = t[5][5] = t[5][6] = SAND_HI
        t[6][5] = t[6][6] = SAND_SH
    return t


def _tile_marsh_water(parity: int = 0) -> Tile:
    t = _blank(SWAMP_WATER)
    if parity & 1:
        t[2][2] = t[2][3] = SWAMP_DARK
        t[5][5] = SWAMP_SHALLOW
    else:
        t[5][1] = t[5][2] = SWAMP_DARK
        t[2][5] = SWAMP_SHALLOW
    return t


# Seamless 16x8 billowing GBC Oracle forest canopy (only 2 interior tiles!)
_CANOPY_16X8 = (
    "dmmhhmmdmmhhhmmd",
    "mmhhhhmmmhhhhmmd",
    "mhhhhmmmdmhhmmdd",
    "mmhhmmddmmmmmddd",
    "mmmmddmmhhmmdmmd",
    "mddddmhhhhmmmhhm",
    "ddmmmdhhhhmmdhhm",
    "dmmhhmmhhmmddmmd",
)


def _canopy_px(x: int, y: int, mystic: bool) -> int:
    ch = _CANOPY_16X8[y & 7][x & 15]
    if mystic:
        return {"h": MYSTIC_HI, "m": MYSTIC_MID, "d": MYSTIC_DARK}[ch]
    return {"h": LEAF_HI, "m": LEAF_MID, "d": LEAF_DEEP}[ch]


def _tile_forest_autotile(tx: int, ty: int, mask4: int, mystic: bool = False) -> Tile:
    """Organic billowing GBC forest canopy autotile with scalloped domes & soft shadows."""
    hi = MYSTIC_HI if mystic else LEAF_HI
    deep = MYSTIC_DARK if mystic else LEAF_DEEP
    out = INK_DARK if mystic else INK_FOREST
    has_n, has_e, has_s, has_w = bool(mask4 & 1), bool(mask4 & 2), bool(mask4 & 4), bool(mask4 & 8)

    if mask4 == 15:
        t = _blank(LEAF_MID)
        x0 = ((tx + ty) & 1) * 8
        for y in range(8):
            for x in range(8):
                t[y][x] = _canopy_px(x0 + x, y, mystic)
        return t

    t = _tile_grass(0)
    inside = [[True] * 8 for _ in range(8)]
    for y in range(8):
        for x in range(8):
            if not has_n and y == 0 and x in (0, 3, 4, 7):
                inside[y][x] = False
            if not has_s and y == 7:
                inside[y][x] = False
            if not has_s and y == 6 and x in (0, 7):
                inside[y][x] = False
            if not has_w and x == 0 and y in (0, 3, 4, 6, 7):
                inside[y][x] = False
            if not has_e and x == 7 and y in (0, 3, 4, 6, 7):
                inside[y][x] = False
            if not has_n and not has_w and (x + y) <= 2:
                inside[y][x] = False
            if not has_n and not has_e and ((7 - x) + y) <= 2:
                inside[y][x] = False
            if not has_s and not has_w and (x + (6 - y)) <= 2:
                inside[y][x] = False
            if not has_s and not has_e and ((7 - x) + (6 - y)) <= 2:
                inside[y][x] = False

    for y in range(8):
        for x in range(8):
            if not inside[y][x]:
                if y > 0 and inside[y - 1][x]:
                    t[y][x] = GRASS_SH
                continue
            n_in = (y == 0 and has_n) or (y > 0 and inside[y - 1][x])
            s_in = (y == 7 and has_s) or (y < 7 and inside[y + 1][x])
            w_in = (x == 0 and has_w) or (x > 0 and inside[y][x - 1])
            e_in = (x == 7 and has_e) or (x < 7 and inside[y][x + 1])
            if not s_in:
                t[y][x] = out
            elif not n_in or not w_in:
                t[y][x] = hi
            elif not e_in:
                t[y][x] = deep
            else:
                t[y][x] = _canopy_px(x, y, mystic)
    return t


def _tile_coast_ocean(land_mask4: int, land_diag4: int) -> Tile:
    """Organic curved turquoise surf + foam edging where ocean meets dry land."""
    t = _tile_ocean(0)
    ln, le, ls, lw = bool(land_mask4 & 1), bool(land_mask4 & 2), bool(land_mask4 & 4), bool(land_mask4 & 8)
    # Only use diagonal bits when neither adjacent cardinal is already land (cuts redundant variants!)
    d_ne = bool(land_diag4 & 1) and not ln and not le
    d_se = bool(land_diag4 & 2) and not ls and not le
    d_sw = bool(land_diag4 & 4) and not ls and not lw
    d_nw = bool(land_diag4 & 8) and not ln and not lw

    for y in range(8):
        for x in range(8):
            d = 12.0
            if ln:
                d = min(d, y + 0.5 + 0.5 * math.sin(x * 0.9))
            if ls:
                d = min(d, (7 - y) + 0.5 + 0.5 * math.sin(x * 0.9))
            if lw:
                d = min(d, x + 0.5 + 0.5 * math.sin(y * 0.9))
            if le:
                d = min(d, (7 - x) + 0.5 + 0.5 * math.sin(y * 0.9))
            if d_nw:
                d = min(d, math.hypot(x + 0.5, y + 0.5))
            if d_ne:
                d = min(d, math.hypot((7 - x) + 0.5, y + 0.5))
            if d_sw:
                d = min(d, math.hypot(x + 0.5, (7 - y) + 0.5))
            if d_se:
                d = min(d, math.hypot((7 - x) + 0.5, (7 - y) + 0.5))
            if ln and lw:
                d = min(d, max(0.0, math.hypot(x + 0.5, y + 0.5) - 3.0))
            if ln and le:
                d = min(d, max(0.0, math.hypot((7 - x) + 0.5, y + 0.5) - 3.0))
            if ls and lw:
                d = min(d, max(0.0, math.hypot(x + 0.5, (7 - y) + 0.5) - 3.0))
            if ls and le:
                d = min(d, max(0.0, math.hypot((7 - x) + 0.5, (7 - y) + 0.5) - 3.0))

            if d < 1.3:
                t[y][x] = SEA_FOAM if ((x + y) & 1) else SEA_SHALLOW
            elif d < 3.6:
                t[y][x] = SEA_SHALLOW
            elif d < 5.8:
                t[y][x] = SEA_MID
    return t


def _tile_coast_land_trim(base: Tile, sea_mask4: int, is_sand: bool = False) -> Tile:
    """Round peninsula corners smoothly into turquoise surf where land meets ocean."""
    t = _copy_tile(base)
    sn, se, ss, sw = bool(sea_mask4 & 1), bool(sea_mask4 & 2), bool(sea_mask4 & 4), bool(sea_mask4 & 8)
    rim = SAND_DARK if is_sand else INK_BROWN
    shore = SAND_HI if is_sand else PATH_HI

    for y in range(8):
        for x in range(8):
            corner_sea = (
                (sn and sw and (x + y) <= 2)
                or (sn and se and ((7 - x) + y) <= 2)
                or (ss and sw and (x + (7 - y)) <= 2)
                or (ss and se and ((7 - x) + (7 - y)) <= 2)
            )
            if corner_sea:
                t[y][x] = SEA_FOAM if ((x + y) & 1) else SEA_SHALLOW
                continue
            on_edge = (
                (sn and y == 0) or (ss and y == 7) or (sw and x == 0) or (se and x == 7)
                or (sn and sw and (x + y) == 3) or (sn and se and ((7 - x) + y) == 3)
                or (ss and sw and (x + (7 - y)) == 3) or (ss and se and ((7 - x) + (7 - y)) == 3)
            )
            near_edge = (sn and y == 1) or (ss and y == 6) or (sw and x == 1) or (se and x == 6)
            if on_edge:
                t[y][x] = rim
            elif near_edge and is_sand:
                t[y][x] = shore
    return t


def _tile_cliff_autotile(
    base_bg: Tile,
    mask4: int,
    top_col: int,
    top_hi: int,
    rim_col: int,
    face_col: int,
    dark_col: int,
    outline_col: int,
) -> Tile:
    """Rounded sculpted GBC stepped cliff & mountain massif autotile."""
    has_n, has_e, has_s, has_w = bool(mask4 & 1), bool(mask4 & 2), bool(mask4 & 4), bool(mask4 & 8)
    if mask4 == 15:
        t = _blank(top_col)
        t[2][2] = top_hi
        t[5][6] = top_hi
        return t

    t = _copy_tile(base_bg)
    top_bottom = 7 if has_s else 4
    inside = [[False] * 8 for _ in range(8)]
    for y in range(0, top_bottom + 1):
        for x in range(8):
            ok = True
            if not has_n and y == 0:
                ok = False
            if not has_w and x == 0:
                ok = False
            if not has_e and x == 7:
                ok = False
            if not has_n and not has_w and (x + y) <= 2:
                ok = False
            if not has_n and not has_e and ((7 - x) + y) <= 2:
                ok = False
            if not has_s and not has_w and (x + (top_bottom - y)) <= 1:
                ok = False
            if not has_s and not has_e and ((7 - x) + (top_bottom - y)) <= 1:
                ok = False
            inside[y][x] = ok

    for y in range(0, top_bottom + 1):
        for x in range(8):
            if not inside[y][x]:
                continue
            n_in = (y == 0 and has_n) or (y > 0 and inside[y - 1][x])
            w_in = (x == 0 and has_w) or (x > 0 and inside[y][x - 1])
            e_in = (x == 7 and has_e) or (x < 7 and inside[y][x + 1])
            s_in = (y == top_bottom and has_s) or (y < top_bottom and inside[y + 1][x])
            if not n_in:
                if y > 0:
                    t[y - 1][x] = outline_col
                t[y][x] = rim_col
            elif not w_in or not s_in:
                t[y][x] = rim_col
            elif not e_in:
                t[y][x] = dark_col
            else:
                t[y][x] = top_hi if (x, y) in ((2, 2), (5, 3)) else top_col

    if not has_s:
        for x in range(8):
            low_y = -1
            for y in range(top_bottom, -1, -1):
                if inside[y][x]:
                    low_y = y
                    break
            if low_y < 0:
                continue
            for step in range(1, 4):
                py = low_y + step
                if py >= 8:
                    break
                if step == 3:
                    t[py][x] = outline_col
                elif step == 2:
                    t[py][x] = dark_col if (x & 1) else face_col
                else:
                    t[py][x] = dark_col if (x % 3 == 0) else face_col
    return t


def _tile_lava_autotile(lava_mask4: int, parity: int = 0) -> Tile:
    """Organic glowing molten lava river & caldera autotile."""
    has_n, has_e, has_s, has_w = bool(lava_mask4 & 1), bool(lava_mask4 & 2), bool(lava_mask4 & 4), bool(lava_mask4 & 8)
    if lava_mask4 == 15:
        t = _blank(LAVA_BRIGHT)
        if parity & 1:
            t[2][2] = t[2][3] = LAVA_CORE
            t[5][5] = t[5][6] = LAVA_MID
        else:
            t[5][2] = t[5][3] = LAVA_CORE
            t[2][5] = LAVA_MID
        return t

    t = _tile_volc(0)
    for y in range(8):
        for x in range(8):
            d = math.hypot(x - 3.5, y - 3.5)
            if has_n and y < 4:
                d = min(d, abs(x - 3.5))
            if has_s and y > 3:
                d = min(d, abs(x - 3.5))
            if has_w and x < 4:
                d = min(d, abs(y - 3.5))
            if has_e and x > 3:
                d = min(d, abs(y - 3.5))
            if has_n and has_w and x < 4 and y < 4:
                d = 0.0
            if has_n and has_e and x > 3 and y < 4:
                d = 0.0
            if has_s and has_w and x < 4 and y > 3:
                d = 0.0
            if has_s and has_e and x > 3 and y > 3:
                d = 0.0

            if d <= 1.2:
                t[y][x] = LAVA_CORE if ((x + y) % 3 == 0) else LAVA_BRIGHT
            elif d <= 2.3:
                t[y][x] = LAVA_BRIGHT
            elif d <= 3.1:
                t[y][x] = LAVA_MID
            elif d <= 3.9:
                t[y][x] = LAVA_CRUST
    return t


def _tile_marsh_islet(islet_mask4: int) -> Tile:
    """Rounded mossy Wisdom Marsh islet rising out of murky teal swamp water."""
    t = _tile_marsh_water(0)
    has_n, has_e, has_s, has_w = bool(islet_mask4 & 1), bool(islet_mask4 & 2), bool(islet_mask4 & 4), bool(islet_mask4 & 8)
    for y in range(8):
        for x in range(8):
            d = math.hypot(x - 3.5, y - 3.5)
            if has_n and y < 4:
                d = min(d, abs(x - 3.5))
            if has_s and y > 3:
                d = min(d, abs(x - 3.5))
            if has_w and x < 4:
                d = min(d, abs(y - 3.5))
            if has_e and x > 3:
                d = min(d, abs(y - 3.5))
            if d <= 2.4:
                t[y][x] = GRASS_HI if ((x + y) % 5 == 0) else SWAMP_MOSS
            elif d <= 3.2:
                t[y][x] = GRASS_SH
            elif d <= 3.9:
                t[y][x] = SWAMP_SHALLOW
    return t


def _overlay_road(t: Tile, road_mask8: int, is_bridge: bool = False, on_sand: bool = False) -> Tile:
    """Subtle, organic 2px curved dirt footpath (8-way N/E/S/W + diagonals) or wooden boardwalk!"""
    out = _copy_tile(t)
    if is_bridge:
        if road_mask8 & (1 | 4):
            for y in range(8):
                out[y][2] = out[y][5] = INK_BROWN
                out[y][3] = WOOD_HI if (y & 1) else WOOD_DARK
                out[y][4] = WOOD_DARK if (y & 1) else WOOD_HI
        else:
            for x in range(8):
                out[2][x] = out[5][x] = INK_BROWN
                out[3][x] = WOOD_HI if (x & 1) else WOOD_DARK
                out[4][x] = WOOD_DARK if (x & 1) else WOOD_HI
        return out

    arms: list[tuple[float, float]] = []
    if road_mask8 & 1:
        arms.append((3.5, 0.0))
    if road_mask8 & 2:
        arms.append((7.0, 3.5))
    if road_mask8 & 4:
        arms.append((3.5, 7.0))
    if road_mask8 & 8:
        arms.append((0.0, 3.5))
    if road_mask8 & 16:
        arms.append((7.0, 0.0))
    if road_mask8 & 32:
        arms.append((7.0, 7.0))
    if road_mask8 & 64:
        arms.append((0.0, 7.0))
    if road_mask8 & 128:
        arms.append((0.0, 0.0))

    def _dseg(px: float, py: float, x0: float, y0: float, x1: float, y1: float) -> float:
        dx, dy = x1 - x0, y1 - y0
        l2 = dx * dx + dy * dy
        if l2 <= 1e-6:
            return math.hypot(px - x0, py - y0)
        u = max(0.0, min(1.0, ((px - x0) * dx + (py - y0) * dy) / l2))
        return math.hypot(px - (x0 + u * dx), py - (y0 + u * dy))

    c_hi = PATH_SH if on_sand else PATH_HI
    c_mid = SAND_DARK if on_sand else PATH_MID
    for y in range(8):
        for x in range(8):
            d = 9.0
            if len(arms) == 2:
                a0, a1 = arms[0], arms[1]
                mx = 0.5 * (a0[0] + a1[0]) * 0.45 + 3.5 * 0.55
                my = 0.5 * (a0[1] + a1[1]) * 0.45 + 3.5 * 0.55
                d = min(_dseg(x, y, a0[0], a0[1], mx, my), _dseg(x, y, mx, my, a1[0], a1[1]))
            else:
                for ax, ay in arms:
                    d = min(d, _dseg(x, y, 3.5, 3.5, ax, ay))
            if d <= 0.85:
                out[y][x] = c_hi if ((x + y) & 1) else c_mid
            elif d <= 1.35:
                out[y][x] = c_mid
    return out


# ---------------------------------------------------------------------------
# Canvas & Hand-Crafted Tile-Efficient Miniature Landmarks (256x256)
# ---------------------------------------------------------------------------
class Canvas:
    def __init__(self, width: int = CENTER_PX, height: int = CENTER_PX) -> None:
        self.w = width
        self.h = height
        self.px = [[GRASS_MID] * width for _ in range(height)]
        self.importance = [[1.0] * (width // 8) for _ in range(height // 8)]
        self.tile_tag = [["bg"] * (width // 8) for _ in range(height // 8)]

    def set(self, x: int, y: int, color: int) -> None:
        if 0 <= x < self.w and 0 <= y < self.h:
            self.px[y][x] = color

    def blit_tile(self, tx: int, ty: int, tile: Tile) -> None:
        y0, x0 = ty * 8, tx * 8
        for dy in range(8):
            self.px[y0 + dy][x0:x0 + 8] = tile[dy][:]

    def mark_important_tiles(self, tx0: int, ty0: int, tx1: int, ty1: int, weight: float, tag: str) -> None:
        for ty in range(max(0, ty0), min(CENTER_TILES, ty1 + 1)):
            for tx in range(max(0, tx0), min(CENTER_TILES, tx1 + 1)):
                if weight > self.importance[ty][tx]:
                    self.importance[ty][tx] = weight
                self.tile_tag[ty][tx] = tag

    def fill_rect(self, x0: int, y0: int, x1: int, y1: int, color: int) -> None:
        for y in range(max(0, y0), min(self.h, y1 + 1)):
            row = self.px[y]
            for x in range(max(0, x0), min(self.w, x1 + 1)):
                row[x] = color

    def fill_ellipse(self, cx: float, cy: float, rx: float, ry: float, color: int) -> None:
        for y in range(max(0, int(cy - ry - 1)), min(self.h, int(cy + ry + 2))):
            for x in range(max(0, int(cx - rx - 1)), min(self.w, int(cx + rx + 2))):
                if ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 <= 1.0:
                    self.px[y][x] = color


def _draw_mountain_peak_tile(
    base: Tile, hi: int, mid: int, face: int, dark: int, out: int, crater: bool = False, twin: bool = False
) -> Tile:
    t = _copy_tile(base)
    art = (
        ".oo..oo.",
        "ohmookmo",
        "ohmmkmfo",
        "ommfmffo",
        "omffffdo",
        "ooffdddo",
        ".oooooo.",
        "........",
    ) if twin else (
        "...oo...",
        "..ohmo..",
        ".ohhmdo.",
        ".ohmmfo.",
        "ohmmffdo",
        "ohmfffdo",
        "ooffdddo",
        ".oooooo.",
    )
    cmap = {"h": hi, "k": hi, "m": mid, "f": face, "d": dark, "o": out}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    if crater:
        t[1][3] = LAVA_CORE
        t[1][4] = LAVA_BRIGHT
        t[2][3] = LAVA_BRIGHT
        t[2][4] = LAVA_MID
    return t


def _draw_coral_reef_tile(variant: int = 0) -> Tile:
    t = _tile_ocean(0)
    arts = (
        (
            "..ssss..",
            ".sccccs.",
            "scCHccds",
            "scCccdds",
            "scccHdds",
            ".sddddss",
            "..ssss..",
            "........",
        ),
        (
            ".....ss.",
            ".ssssccs",
            "sccccHds",
            "scHccdds",
            "scccddds",
            ".sdddds.",
            "..ssss..",
            "........",
        ),
        (
            "..sss...",
            ".scccs..",
            "scHccss.",
            ".sddcccs",
            "..ssCHds",
            "...sddds",
            "....sss.",
            "........",
        ),
    )
    cmap = {"s": SEA_SHALLOW, "c": CORAL_MID, "C": CORAL_HI, "H": CORAL_HI, "d": CORAL_DARK}
    for y, row in enumerate(arts[variant % len(arts)]):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    return t


def _draw_pond_tile(base: Tile, bridge: bool = False) -> Tile:
    t = _copy_tile(base)
    art = (
        "..oooo..",
        ".osssso.",
        "osmmmmdo",
        "osmmmdoo",
        "ommmdddo",
        ".oddddo.",
        "..oooo..",
        "........",
    )
    cmap = {"o": INK_BROWN, "s": SEA_SHALLOW, "m": SEA_MID, "d": SEA_DEEP}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    if bridge:
        for x in range(8):
            t[3][x] = WOOD_HI if (x & 1) else WOOD_DARK
            t[4][x] = WOOD_DARK if (x & 1) else WOOD_HI
    return t


def _draw_cottage_tile(base: Tile, roof: int, roof_sh: int) -> Tile:
    t = _copy_tile(base)
    art = (
        "..oooo..",
        ".orrrso.",
        "orrrrsso",
        "owwddswo",
        "owwdwwwo",
        "owwwwwwo",
        ".oooooo.",
        "........",
    )
    cmap = {"o": INK_BROWN, "r": roof, "s": roof_sh, "w": CREAM, "d": WOOD_DARK}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    return t


def _draw_palm_tile(base: Tile) -> Tile:
    t = _copy_tile(base)
    art = (
        "..hlp...",
        ".plhpl..",
        "d.pw..d.",
        "...w....",
        "...W....",
        "...W....",
        "..ss....",
        "........",
    )
    cmap = {"h": LEAF_HI, "l": PALM_GREEN, "p": PALM_GREEN, "d": LEAF_DEEP, "w": WOOD_HI, "W": WOOD_DARK, "s": SAND_SH}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    return t


def _draw_ruin_pillar_tile(base: Tile) -> Tile:
    t = _copy_tile(base)
    art = (
        "..ooo...",
        "..oco...",
        "..oho...",
        "..oso...",
        "..oso...",
        ".oSSSo..",
        "..sss...",
        "........",
    )
    cmap = {"o": INK_BROWN, "c": CREAM, "h": SAND_HI, "s": SAND_SH, "S": SAND_DARK}
    for y, row in enumerate(art):
        for x, ch in enumerate(row):
            if ch != ".":
                t[y][x] = cmap[ch]
    return t


def _draw_stepped_pyramid_aligned(c: Canvas, tx: int, ty: int, tw: int, th: int, has_door: bool = True) -> None:
    """Tile-aligned golden GBC stepped ziggurat pyramid (identical 3x3 stamps share all 9 tiles!)."""
    c.mark_important_tiles(tx, ty, tx + tw - 1, ty + th - 1, 12.0, "pyramid")
    # Paint canonical slate base under the pyramid so multiple 3x3 pyramids share 100% of their tiles!
    for dy in range(th):
        for dx in range(tw):
            c.blit_tile(tx + dx, ty + dy, _tile_slate(0))
    x0, y0 = tx * 8 + 1, ty * 8 + 1
    w, h = tw * 8 - 2, th * 8 - 2
    cx, cy = x0 + w // 2, y0 + h // 2
    c.fill_rect(x0 + 1, y0 + h, x0 + w, y0 + h, SLATE_DARK)
    c.fill_rect(x0 + w, y0 + 1, x0 + w, y0 + h, SLATE_DARK)
    tiers = min(4, min(w, h) // 4)
    for tier in range(tiers):
        inset = tier * 2
        ax0, ay0 = x0 + inset, y0 + inset
        ax1, ay1 = x0 + w - 1 - inset, y0 + h - 1 - inset
        if ax0 >= ax1 or ay0 >= ay1:
            break
        for y in range(ay0, ay1 + 1):
            for x in range(ax0, ax1 + 1):
                if x == ax0 or x == ax1 or y == ay0 or y == ay1:
                    col = INK_BROWN if (x == ax1 or y == ay1) else GOLD_HI
                elif (x - cx) + (y - cy) < -1:
                    col = GOLD_HI if (((x - x0) + (y - y0)) & 1) else GOLD_MID
                elif (x - cx) > 1 or (y - cy) > 1:
                    col = GOLD_SH
                else:
                    col = GOLD_MID
                c.set(x, y, col)
    c.fill_rect(cx - 2, cy - 2, cx + 1, cy + 1, GOLD_HI)
    c.set(cx - 1, cy - 1, CREAM)
    c.set(cx, cy, GOLD_MID)
    for y in range(cy + 2, y0 + h):
        step_p = (y - y0) & 1
        c.set(cx - 1, y, PATH_HI if step_p else PATH_MID)
        c.set(cx, y, PATH_MID if step_p else GOLD_SH)
    if has_door:
        c.fill_rect(cx - 1, y0 + h - 3, cx, y0 + h - 1, INK_DARK)
        c.set(cx - 2, y0 + h - 2, INK_BROWN)
        c.set(cx + 1, y0 + h - 2, INK_BROWN)


def _draw_fortress_aligned(c: Canvas) -> None:
    """8x8-modular Emerald & Gold Fortress of Secrets ($4B/$4C/$53/$54, tx=12..19, ty=4..10).

    Strict 8x8 tile symmetry keeps this grand 56-tile citadel to ~22 unique tiles
    while landing the Grand North Gate cleanly at (138, 36)!
    """
    c.mark_important_tiles(12, 4, 19, 10, 13.0, "fortress")
    x0, y0, x1, y1 = 96, 32, 159, 87
    # Outer modular stone walls
    c.fill_rect(x0, y0, x1, y1, FORT_WALL)
    c.fill_rect(x0, y1 - 3, x1, y1 - 1, CLIFF_FACE)
    c.fill_rect(x0, y1, x1, y1, CLIFF_DARK)
    c.fill_rect(x0, y0, x1, y0, INK_BROWN)
    c.fill_rect(x0, y0, x0, y1, INK_BROWN)
    c.fill_rect(x1, y0, x1, y1, INK_BROWN)

    # Inner emerald citadel lawn (8x8 periodic stipple)
    c.fill_rect(x0 + 4, y0 + 4, x1 - 4, y1 - 6, FORT_GREEN)
    for y in range(y0 + 4, y1 - 6):
        for x in range(x0 + 4, x1 - 3):
            if ((x & 3) == 1 and (y & 3) == 1) or ((x & 3) == 3 and (y & 3) == 3):
                c.set(x, y, FORT_GREEN_HI)

    # Repeating 8px battlements along north wall (all plain north wall tiles identical!)
    for tx in range(13, 19):
        bx = tx * 8
        for off in (1, 5):
            c.set(bx + off, y0 + 1, GOLD_HI)
            c.set(bx + off + 1, y0 + 1, GOLD_MID)
            c.set(bx + off + 2, y0 + 1, INK_BROWN)

    # 4 identical 8x8 corner fortress turrets
    for tx, ty in ((12, 4), (19, 4), (12, 10), (19, 10)):
        ox, oy = tx * 8, ty * 8
        c.fill_rect(ox + 1, oy + 1, ox + 6, oy + 6, INK_BROWN)
        c.fill_rect(ox + 2, oy + 2, ox + 5, oy + 5, FORT_WALL)
        c.fill_rect(ox + 2, oy + 2, ox + 4, oy + 3, GOLD_HI)
        c.set(ox + 4, oy + 4, GOLD_MID)

    # Modular 8x8 inner palace tiles:
    # 1. West emerald garden courtyard (tx=13..14, ty=5..7)
    def _garden_box(x_a: int, y_a: int, x_b: int, y_b: int, wall: int, rim: int) -> None:
        c.fill_rect(x_a, y_a, x_b, y_b, rim)
        c.fill_rect(x_a + 1, y_a + 1, x_b - 1, y_b - 1, wall)
        c.fill_rect(x_a + 3, y_a + 3, x_b - 3, y_b - 3, FORT_GREEN)

    _garden_box(104, 40, 119, 63, FORT_GREEN_HI, INK_FOREST)
    # West golden fountain shrine centered cleanly in (tx=13..14, ty=6)
    c.fill_rect(109, 49, 114, 54, GOLD_MID)
    c.set(110, 50, GOLD_HI)
    c.set(111, 51, CREAM)

    # 2. East royal fortress keep (tx=16..18, ty=5..7 -> symmetric horizontal wall/lawn tiles!)
    _garden_box(128, 40, 151, 63, FORT_WALL, INK_BROWN)
    c.fill_rect(131, 43, 148, 60, FORT_GREEN_HI)
    c.fill_rect(132, 44, 147, 59, FORT_GREEN)
    # Golden inner sanctuary keep centered cleanly in single tile tx=17, ty=6!
    c.fill_rect(136, 48, 143, 55, INK_BROWN)
    c.fill_rect(137, 49, 142, 54, GOLD_MID)
    c.fill_rect(138, 49, 140, 52, GOLD_HI)
    c.set(139, 50, CREAM)
    c.set(139, 54, INK_DARK)

    # 3. South cross-shaped emerald courtyard cleanly aligned to tx=13..18, ty=8..9
    # Use modular 8px tile rhythm so tx=14 and tx=16 are IDENTICAL, and tx=15 & tx=17 cross cleanly!
    c.fill_rect(104, 65, 151, 78, INK_FOREST)
    c.fill_rect(105, 66, 150, 77, FORT_GREEN_HI)
    c.fill_rect(107, 68, 148, 75, FORT_GREEN)
    # Horizontal cross path (y=71..72) + matching vertical avenues in tx=15 (x=123..124) & tx=17 (x=139..140)
    c.fill_rect(106, 71, 149, 72, PATH_HI)
    for px in (123, 139):
        c.fill_rect(px, 66, px + 1, 77, PATH_MID)
        c.fill_rect(px, 71, px + 1, 72, PATH_HI)
    # Central N-S avenue connecting north lawn to south fortress entrance (tx=15)
    c.fill_rect(123, 40, 124, 65, PATH_MID)
    c.fill_rect(123, 40, 123, 65, PATH_HI)
    c.fill_rect(123, 78, 124, 83, PATH_MID)
    # East keep walkway down into south courtyard (tx=17, ty=7)
    c.fill_rect(139, 56, 140, 65, PATH_MID)

    # Grand North Entrance Gate centered right at DrawFortressOfSecretsIcon (138, 36) -> tx=16..17, ty=4!
    gx, gy = MARKERS_PX["fortress"]
    c.fill_rect(gx - 5, gy - 4, gx + 5, gy + 3, INK_BROWN)
    c.fill_rect(gx - 4, gy - 3, gx + 4, gy + 2, FORT_WALL)
    c.fill_rect(gx - 5, gy - 4, gx - 3, gy + 2, GOLD_MID)
    c.fill_rect(gx + 3, gy - 4, gx + 5, gy + 2, GOLD_MID)
    c.set(gx - 4, gy - 3, GOLD_HI)
    c.set(gx + 4, gy - 3, GOLD_HI)
    c.fill_rect(gx - 2, gy - 1, gx + 2, gy + 3, INK_DARK)
    c.fill_rect(gx - 1, gy - 2, gx + 1, gy - 2, GOLD_HI)


def _draw_windmill_2x2(c: Canvas, tx: int, ty: int) -> None:
    """Iconic 16x16 Yesterwind Windmill ($64) with stone tower, red roof & crisp white cross-sails."""
    c.mark_important_tiles(tx, ty, tx + 1, ty + 1, 15.0, "village")
    cx, cy = tx * 8 + 8, ty * 8 + 8
    for dy in range(-2, 6):
        hw = 2 if dy < 1 else 3
        for dx in range(-hw, hw + 1):
            if abs(dx) == hw or dy == 5:
                c.set(cx + dx, cy + dy, INK_BROWN)
            elif dx < 0:
                c.set(cx + dx, cy + dy, CREAM)
            else:
                c.set(cx + dx, cy + dy, PATH_MID)
    for dx in (-2, -1, 0, 1, 2):
        c.set(cx + dx, cy - 3, ROOF_RED if dx <= 0 else ROOF_RED_SH)
    for dx in (-1, 0, 1):
        c.set(cx + dx, cy - 4, ROOF_RED)
    c.set(cx, cy - 5, INK_BROWN)
    c.set(cx, cy + 3, WOOD_DARK)
    c.set(cx, cy + 4, WOOD_DARK)
    for step in range(1, 6):
        for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
            px, py = cx + sx * step, cy - 1 + sy * step
            c.set(px, py, CREAM if step >= 2 else WOOD_HI)
            if step in (3, 4):
                c.set(px, py - sy, PATH_HI)
    c.set(cx, cy - 1, WOOD_DARK)
    c.fill_rect(cx - 5, cy + 6, cx - 2, cy + 7, SEA_MID)
    c.fill_rect(cx + 2, cy + 6, cx + 5, cy + 7, SEA_MID)
    c.set(cx - 4, cy + 6, SEA_SHALLOW)
    c.set(cx + 3, cy + 6, SEA_SHALLOW)


def _draw_lupo_waterfall_aligned(c: Canvas) -> None:
    """Symmetric Twin Sapphire Waterfall Reservoirs + Central Stone Causeway ($4A, tx=8..10, ty=4..6).

    Identical left (tx=8) and right (tx=10) water basins cut tile usage in half (~6 tiles total!).
    """
    c.mark_important_tiles(8, 4, 10, 7, 11.0, "waterfall")
    for btx in (8, 10):
        bx0 = btx * 8
        # Top cascade tile (ty=4)
        t_top = _tile_slate(0)
        for y in range(2, 8):
            for x in range(1, 7):
                if y == 2 or x in (1, 6):
                    t_top[y][x] = SLATE_DARK
                elif y == 3:
                    t_top[y][x] = SEA_FOAM if (x & 1) else SEA_SHALLOW
                elif y == 4:
                    t_top[y][x] = SEA_SHALLOW if (x & 1) else SEA_FOAM
                else:
                    t_top[y][x] = SEA_MID
        c.blit_tile(btx, 4, t_top)
        # Mid reservoir tile (ty=5)
        t_mid = _tile_slate(0)
        for y in range(8):
            for x in range(1, 7):
                if x in (1, 6):
                    t_mid[y][x] = SLATE_DARK
                elif y in (2, 6) and x in (3, 4):
                    t_mid[y][x] = SEA_SHALLOW
                else:
                    t_mid[y][x] = SEA_MID
        c.blit_tile(btx, 5, t_mid)
        # Bottom basin tile (ty=6)
        t_bot = _tile_slate(0)
        for y in range(6):
            for x in range(1, 7):
                if y == 5 or x in (1, 6):
                    t_bot[y][x] = SLATE_DARK
                else:
                    t_bot[y][x] = SEA_DEEP if y == 4 else SEA_MID
        c.blit_tile(btx, 6, t_bot)
    # Central stone causeway cleanly in tx=9, ty=4..7 (reuses 1 vertical stone bridge tile!)
    t_br = _tile_slate(0)
    for y in range(8):
        t_br[y][1] = t_br[y][6] = SLATE_DARK
        for x in range(2, 6):
            t_br[y][x] = SLATE_HI
        if y in (1, 5):
            t_br[y][2] = t_br[y][5] = SLATE_MID
    for ty in (4, 5, 6, 7):
        c.blit_tile(9, ty, t_br)


def _draw_sanctum_aligned(c: Canvas) -> None:
    """Tile-efficient Obsidian Sanctum ($4D/$55, tx=20..23, ty=4..11) — pit, mystic glow & stairs."""
    c.mark_important_tiles(20, 4, 23, 11, 11.0, "sanctum")
    pit = _blank(OBS_MID)
    for y in range(8):
        for x in range(8):
            d = math.hypot(x - 3.5, y - 3.5)
            if d < 2.2:
                pit[y][x] = INK_DARK
            elif d < 3.4:
                pit[y][x] = OBS_DARK
            elif d < 4.1:
                pit[y][x] = INK_SLATE
    pit[1][1] = pit[1][6] = MYSTIC_HI
    pit[6][1] = pit[6][6] = MYSTIC_MID
    c.blit_tile(21, 5, pit)
    # Single reusable dark-obsidian stone stairway connecting $55 -> $4D at tx=21, ty=6..8
    stair = _blank(OBS_MID)
    for y in range(8):
        stair[y][1] = stair[y][6] = INK_DARK
        col = SLATE_HI if (y & 1) == 0 else OBS_DARK
        for x in range(2, 6):
            stair[y][x] = col
    for ty in (6, 7, 8):
        c.blit_tile(21, ty, stair)
    # Stone bridge tile linking Fortress east wall to Sanctum at tx=20, ty=5
    br = _blank(OBS_MID)
    for x in range(8):
        br[2][x] = INK_DARK
        br[3][x] = br[4][x] = SLATE_HI
        br[5][x] = SLATE_DARK
    c.blit_tile(20, 5, br)
    # Twin identical obsidian obelisks on $55 at tx=20, ty=9 and tx=22, ty=9 (1 tile!)
    ob = _blank(OBS_MID)
    for y in range(1, 7):
        ob[y][2] = ob[y][5] = INK_DARK
        ob[y][3] = ob[y][4] = OBS_DARK
    ob[2][3] = ob[2][4] = MYSTIC_HI
    ob[3][3] = SLATE_HI
    c.blit_tile(20, 9, ob)
    c.blit_tile(22, 9, ob)


def _draw_ghost_ship_and_finale_aligned(c: Canvas) -> None:
    """Wrecked Ghost Ship ($57 shore) + glowing Final Boss Pit right at (247, 79)."""
    c.mark_important_tiles(29, 8, 31, 10, 16.0, "finale")
    # Wrecked Ghost Ship perched cleanly in tx=29..30, ty=8
    sx, sy = 239, 69
    for dx in range(-5, 6):
        c.set(sx + dx, sy + 2, INK_DARK)
        if abs(dx) <= 4:
            c.set(sx + dx, sy + 1, WOOD_DARK)
        if abs(dx) <= 3:
            c.set(sx + dx, sy, WOOD_HI if dx <= 0 else WOOD_DARK)
    c.set(sx - 5, sy, WOOD_HI)
    c.set(sx + 4, sy, WOOD_DARK)
    c.set(sx - 1, sy - 1, WOOD_HI)
    c.set(sx - 1, sy - 2, WOOD_HI)
    c.set(sx, sy - 3, WOOD_DARK)
    c.set(sx, sy - 2, CREAM)
    c.set(sx + 1, sy - 2, SLATE_HI)
    c.set(sx + 1, sy - 1, SLATE_MID)

    # Glowing Final Boss Volcanic Pit centered EXACTLY at DrawFinalBossIcon (247, 79)!
    fx, fy = MARKERS_PX["pyramid"]
    c.fill_ellipse(fx, fy, 5.6, 5.0, VOLC_DARK)
    c.fill_ellipse(fx, fy, 4.1, 3.6, LAVA_CRUST)
    c.fill_ellipse(fx, fy, 2.5, 2.2, INK_DARK)
    for dx, dy, col in (
        (-4, -2, LAVA_BRIGHT), (4, -2, LAVA_BRIGHT),
        (-3, 3, LAVA_MID), (3, 3, LAVA_MID),
        (0, -4, LAVA_CORE), (0, 4, LAVA_BRIGHT),
        (-2, -3, GOLD_MID), (2, -3, GOLD_MID),
    ):
        c.set(fx + dx, fy + dy, col)


# ---------------------------------------------------------------------------
# Full Organic 256x256 Map Builder (V5 — Lossless <= 246 Tiles!)
# ---------------------------------------------------------------------------
def build_center_canvas() -> Canvas:
    assert len(BASE_MAP_ROWS) == CENTER_TILES
    assert all(len(r) == CENTER_TILES for r in BASE_MAP_ROWS)

    c = Canvas(CENTER_PX, CENTER_PX)

    def cell(tx: int, ty: int) -> str:
        tx = 0 if tx < 0 else (CENTER_TILES - 1 if tx >= CENTER_TILES else tx)
        ty = 0 if ty < 0 else (CENTER_TILES - 1 if ty >= CENTER_TILES else ty)
        return BASE_MAP_ROWS[ty][tx]

    def mask4(tx: int, ty: int, match: set[str]) -> int:
        m = 0
        if cell(tx, ty - 1) in match:
            m |= 1
        if cell(tx + 1, ty) in match:
            m |= 2
        if cell(tx, ty + 1) in match:
            m |= 4
        if cell(tx - 1, ty) in match:
            m |= 8
        return m

    def diag4(tx: int, ty: int, match: set[str]) -> int:
        m = 0
        if cell(tx + 1, ty - 1) in match:
            m |= 1
        if cell(tx + 1, ty + 1) in match:
            m |= 2
        if cell(tx - 1, ty + 1) in match:
            m |= 4
        if cell(tx - 1, ty - 1) in match:
            m |= 8
        return m

    road_mask = [[0] * CENTER_TILES for _ in range(CENTER_TILES)]
    dir_bit = {
        (0, -1): 1, (1, 0): 2, (0, 1): 4, (-1, 0): 8,
        (1, -1): 16, (1, 1): 32, (-1, 1): 64, (-1, -1): 128,
    }
    for path in ROAD_PATHS:
        for i in range(len(path) - 1):
            x0, y0 = path[i]
            x1, y1 = path[i + 1]
            cx, cy = x0, y0
            while (cx, cy) != (x1, y1):
                dx = 1 if x1 > cx else (-1 if x1 < cx else 0)
                dy = 1 if y1 > cy else (-1 if y1 < cy else 0)
                nx, ny = cx + dx, cy + dy
                road_mask[cy][cx] |= dir_bit[(dx, dy)]
                road_mask[ny][nx] |= dir_bit[(-dx, -dy)]
                cx, cy = nx, ny

    # ------------------------------------------------------------------
    # PASS 1: Render every 8x8 tile cleanly from Organic Autotile Kits
    # ------------------------------------------------------------------
    sea_set = {"S"}
    land_set = set("PVKLGFMHEAOWIDRB")
    forest_set = {"F", "M"}

    for ty in range(CENTER_TILES):
        for tx in range(CENTER_TILES):
            ch = cell(tx, ty)
            sea_m = mask4(tx, ty, sea_set)
            rm = road_mask[ty][tx]
            par = (tx + ty) & 1

            if ch == "S":
                lm = mask4(tx, ty, land_set)
                ld = diag4(tx, ty, land_set)
                tile = _tile_coast_ocean(lm, ld) if (lm or ld) else _tile_ocean(par)
                c.tile_tag[ty][tx] = "coast" if (lm or ld) else "ocean"
                if lm or ld:
                    c.importance[ty][tx] = 7.0
            elif ch == "G":
                tile = _tile_grass(0 if (sea_m or rm) else par)
                c.tile_tag[ty][tx] = "meadow"
            elif ch in ("F", "M"):
                fm = mask4(tx, ty, forest_set)
                tile = _tile_forest_autotile(tx, ty, fm, mystic=(ch == "M"))
                c.tile_tag[ty][tx] = "mystic" if ch == "M" else "forest"
            elif ch == "P":
                if ty == 7 and tx < 8:
                    pm = 1 | 2 | 8
                    tile = _tile_cliff_autotile(
                        _tile_grass(0), pm,
                        SLATE_MID, SLATE_HI, SLATE_HI, CLIFF_FACE, CLIFF_DARK, INK_BROWN,
                    )
                else:
                    tile = _tile_slate(0 if rm else par, dark=False)
                c.tile_tag[ty][tx] = "pyramid"
            elif ch == "V":
                tile = _tile_volc(0 if (sea_m or rm) else par)
                c.tile_tag[ty][tx] = "volcano"
            elif ch == "K":
                km = mask4(tx, ty, {"K"})
                tile = _tile_cliff_autotile(
                    _tile_volc(0), km,
                    VOLC_TOP, LAVA_CRUST, LAVA_CRUST, VOLC_CRAG, VOLC_DARK, INK_DARK,
                )
                c.tile_tag[ty][tx] = "volcano"
                c.importance[ty][tx] = 5.5
            elif ch == "L":
                lm = mask4(tx, ty, {"L"})
                tile = _tile_lava_autotile(lm, parity=par)
                c.tile_tag[ty][tx] = "lava"
                c.importance[ty][tx] = 6.0
            elif ch == "A":
                am = mask4(tx, ty, {"A"})
                if ty == 15:
                    am &= ~4
                if ty == 16:
                    am &= ~1
                tile = _tile_cliff_autotile(
                    _tile_grass(0), am,
                    SLATE_HI, CREAM, CLIFF_TOP, CLIFF_FACE, CLIFF_DARK, INK_BROWN,
                )
                c.tile_tag[ty][tx] = "lupo"
                c.importance[ty][tx] = 5.5
            elif ch == "O":
                om = mask4(tx, ty, {"O"})
                if ty == 7:
                    om &= ~4
                if ty == 8:
                    om &= ~1
                tile = _tile_cliff_autotile(
                    _tile_grass(0), om,
                    OBS_MID, SLATE_MID, SLATE_HI, OBS_DARK, INK_DARK, INK_SLATE,
                )
                c.tile_tag[ty][tx] = "sanctum"
                c.importance[ty][tx] = 6.5
            elif ch == "H":
                hm = mask4(tx, ty, {"H"})
                tile = _tile_cliff_autotile(
                    _tile_grass(0), hm,
                    GRASS_MID, GRASS_HI, CLIFF_TOP, CLIFF_FACE, CLIFF_DARK, INK_BROWN,
                )
                c.tile_tag[ty][tx] = "hills"
                c.importance[ty][tx] = 5.0
            elif ch == "E":
                em = mask4(tx, ty, {"E"})
                tile = _tile_cliff_autotile(
                    _tile_grass(0), em,
                    CLIFF_TOP, PATH_HI, PATH_HI, CLIFF_FACE, CLIFF_DARK, INK_BROWN,
                )
                c.tile_tag[ty][tx] = "canyon"
                c.importance[ty][tx] = 5.5
            elif ch == "W":
                gm = mask4(tx, ty, {"G", "F", "E"})
                tile = _tile_marsh_water(0 if (gm or sea_m) else par)
                if gm & 1:
                    for x in range(8):
                        tile[0][x] = SWAMP_SHALLOW if (x & 1) else GRASS_SH
                if gm & 8:
                    for y in range(8):
                        tile[y][0] = SWAMP_SHALLOW if (y & 1) else GRASS_SH
                if gm & 2:
                    for y in range(8):
                        tile[y][7] = SWAMP_SHALLOW if (y & 1) else GRASS_SH
                c.tile_tag[ty][tx] = "marsh"
                c.importance[ty][tx] = 5.0
            elif ch == "I":
                im = mask4(tx, ty, {"I"})
                tile = _tile_marsh_islet(im)
                c.tile_tag[ty][tx] = "marsh"
                c.importance[ty][tx] = 7.0
            elif ch == "D":
                tile = _tile_sand(0 if (sea_m or rm) else par)
                c.tile_tag[ty][tx] = "desert"
            elif ch == "R":
                rm_c = mask4(tx, ty, {"R"})
                tile = _tile_cliff_autotile(
                    _tile_sand(0), rm_c,
                    SAND_MID, SAND_HI, SAND_HI, SAND_SH, SAND_DARK, INK_BROWN,
                )
                c.tile_tag[ty][tx] = "desert"
                c.importance[ty][tx] = 5.5
            else:  # 'B' Fortress
                tile = _blank(FORT_GREEN)
                c.tile_tag[ty][tx] = "fortress"

            if ch != "S" and sea_m:
                tile = _tile_coast_land_trim(tile, sea_m, is_sand=(ch in ("D", "R")))
                c.tile_tag[ty][tx] = "coast"
                c.importance[ty][tx] = 7.0

            if rm and ch != "B":
                is_bridge = ch == "S" or (tx == 6 and ty == 10)
                tile = _overlay_road(tile, rm, is_bridge=is_bridge, on_sand=(ch == "D"))
                c.importance[ty][tx] = max(c.importance[ty][tx], 8.5)

            c.blit_tile(tx, ty, tile)

    # ------------------------------------------------------------------
    # PASS 2: Curated GBC Feature Tiles (Peaks, Coral, Ruins, Ponds, Palms, Cottages)
    # ------------------------------------------------------------------
    # 2A. Sculpted GBC Volcanic Cones ($43-$47 & $56)
    for ptx, pty, smoke, twin in (
        (12, 0, False, True), (16, 0, True, False), (20, 0, False, True),
        (24, 0, True, False), (25, 8, False, True),
    ):
        c.blit_tile(ptx, pty, _draw_mountain_peak_tile(_blank(VOLC_TOP), LAVA_CRUST, VOLC_TOP, VOLC_FACE, VOLC_DARK, INK_DARK, crater=smoke, twin=twin))
        c.mark_important_tiles(ptx, pty, ptx, pty, 8.5, "volcano")

    # 2B. Sculpted GBC Alpine Peaks & Tarn on Lupo Mountain ($5E/$5F/$66/$67)
    for ptx, pty, twin in (
        (25, 13, True), (26, 14, False), (29, 13, True),
        (25, 17, False), (27, 17, True), (29, 17, False),
    ):
        c.blit_tile(ptx, pty, _draw_mountain_peak_tile(_blank(SLATE_HI), CREAM, SLATE_HI, CLIFF_FACE, CLIFF_DARK, INK_BROWN, twin=twin))
        c.mark_important_tiles(ptx, pty, ptx, pty, 8.5, "lupo")
    c.blit_tile(30, 14, _draw_pond_tile(_blank(SLATE_HI)))
    c.mark_important_tiles(30, 14, 30, 14, 9.0, "lupo")

    # 2C. Underwater Abyss: Clustered Rose Coral Reefs ($70/$71/$78/$79)
    for ctx, cty, var in (
        (1, 26, 0), (2, 26, 1), (2, 27, 2),
        (5, 26, 1), (6, 26, 0), (6, 27, 2),
        (3, 28, 0), (4, 28, 1), (4, 29, 2),
        (1, 30, 1), (6, 30, 0), (7, 29, 2),
    ):
        c.blit_tile(ctx, cty, _draw_coral_reef_tile(var))
        c.mark_important_tiles(ctx, cty, ctx, cty, 7.0, "ocean")

    # Sunken Zora Temple Ruins ($72-$74/$7A-$7C)
    def _ruin_tile(kind: str) -> Tile:
        t = _tile_ocean(0)
        if kind == "h":
            for x in range(8):
                t[3][x] = RUIN_SEA_HI
                t[4][x] = RUIN_SEA
        elif kind == "v":
            for y in range(8):
                t[y][3] = RUIN_SEA_HI
                t[y][4] = RUIN_SEA
        elif kind == "tl":
            for i in range(3, 8):
                t[3][i] = t[i][3] = RUIN_SEA_HI
                t[4][i] = t[i][4] = RUIN_SEA
        elif kind == "tr":
            for i in range(0, 5):
                t[3][i] = RUIN_SEA_HI
                t[4][i] = RUIN_SEA
            for i in range(3, 8):
                t[i][3] = RUIN_SEA_HI
                t[i][4] = RUIN_SEA
        elif kind == "shrine":
            for y in range(2, 6):
                for x in range(2, 6):
                    t[y][x] = RUIN_SEA_HI
            t[3][3] = t[3][4] = GOLD_HI
            t[4][3] = t[4][4] = GOLD_MID
        return t

    for rtx, rty, rk in (
        (10, 26, "tl"), (11, 26, "h"), (12, 26, "tr"), (10, 27, "v"), (12, 27, "v"),
        (11, 28, "shrine"),
        (15, 26, "tl"), (16, 26, "h"), (17, 26, "h"), (18, 26, "tr"),
        (15, 27, "v"), (18, 27, "v"), (15, 28, "v"), (18, 28, "v"),
        (16, 29, "h"), (17, 29, "h"),
    ):
        c.blit_tile(rtx, rty, _ruin_tile(rk))
        c.mark_important_tiles(rtx, rty, rtx, rty, 7.5, "ocean")

    # Octoboss Twin-Basin Reef ($75, tx=21..22, ty=26..27)
    for ox, oy, cxl, cyl in ((21, 26, 6, 6), (22, 26, 1, 6), (21, 27, 6, 1), (22, 27, 1, 1)):
        ot = _tile_ocean(0)
        for y in range(8):
            for x in range(8):
                d = math.hypot(x - cxl, y - cyl)
                if d < 3.2:
                    ot[y][x] = SEA_ABYSS
                elif d < 5.0:
                    ot[y][x] = SEA_SHALLOW if d > 4.1 else SEA_MID
        c.blit_tile(ox, oy, ot)
        c.mark_important_tiles(ox, oy, ox, oy, 7.5, "ocean")

    # 2D. Sparkling Inland Ponds ($51 with bridge, $5A, $5B, $61, $69, $6A)
    for ptx, pty, br in (
        (6, 10, True), (10, 13, False), (13, 14, False),
        (4, 17, False), (6, 21, False), (10, 23, False),
    ):
        c.blit_tile(ptx, pty, _draw_pond_tile(_tile_grass(0), bridge=br))
        c.mark_important_tiles(ptx, pty, ptx, pty, 8.0, "meadow")

    # 2E. Charming Yesterwind Village Cottages ($5B, $5C, $63, $64)
    for htx, hty, r1, r2 in (
        (14, 16, ROOF_RED, ROOF_RED_SH),
        (16, 17, ROOF_BLUE, SEA_DEEP),
        (20, 17, ROOF_RED, ROOF_RED_SH),
        (17, 13, ROOF_RED, ROOF_RED_SH),
        (15, 14, ROOF_BLUE, SEA_DEEP),
    ):
        c.blit_tile(htx, hty, _draw_cottage_tile(_tile_grass(0), r1, r2))
        c.mark_important_tiles(htx, hty, htx, hty, 12.0, "village")

    # 2F. Smith's Beach Palm Trees ($7E) + Desert Ruin Pillars & Shrine ($77/$7F)
    for ptx, pty in ((26, 28), (27, 29), (26, 30)):
        c.blit_tile(ptx, pty, _draw_palm_tile(_tile_sand(0)))
        c.mark_important_tiles(ptx, pty, ptx, pty, 9.5, "desert")
    for ptx, pty in ((28, 25), (30, 25), (29, 28)):
        c.blit_tile(ptx, pty, _draw_ruin_pillar_tile(_blank(SAND_MID)))
        c.mark_important_tiles(ptx, pty, ptx, pty, 9.0, "desert")
    ds = _blank(SAND_MID)
    for y in range(1, 7):
        for x in range(1, 7):
            ds[y][x] = INK_BROWN if y in (1, 6) or x in (1, 6) else GOLD_MID
    ds[2][2] = ds[2][3] = GOLD_HI
    ds[5][3] = ds[5][4] = INK_DARK
    c.blit_tile(29, 26, ds)
    c.mark_important_tiles(29, 26, 29, 26, 10.0, "desert")

    # Foothills Hill Shrine ($6F)
    fs = _blank(GRASS_MID)
    for y in range(1, 7):
        for x in range(1, 7):
            fs[y][x] = INK_BROWN if y in (1, 6) or x in (1, 6) else FORT_WALL
    fs[2][2] = fs[2][3] = fs[2][4] = GOLD_HI
    fs[5][3] = fs[5][4] = INK_DARK
    c.blit_tile(30, 21, fs)
    c.mark_important_tiles(30, 21, 30, 21, 9.0, "hills")

    # Wisdom Marsh Central Shrine ($6C islet)
    ms = _tile_marsh_islet(0)
    for y in range(2, 6):
        for x in range(2, 6):
            ms[y][x] = INK_BROWN if y in (2, 5) or x in (2, 5) else GOLD_HI
    ms[4][3] = INK_DARK
    c.blit_tile(17, 22, ms)
    c.mark_important_tiles(17, 22, 17, 22, 11.0, "marsh")

    # ------------------------------------------------------------------
    # PASS 3: Hand-Crafted Multi-Tile Landmarks & Exact Marker Pins
    # ------------------------------------------------------------------
    # Identical 3x3 stepped golden pyramids at (0,1) and (5,4) share all 9 tiles!
    _draw_stepped_pyramid_aligned(c, 0, 1, 3, 3, has_door=True)
    _draw_stepped_pyramid_aligned(c, 3, 1, 1, 3, has_door=False)
    _draw_stepped_pyramid_aligned(c, 5, 4, 3, 3, has_door=True)

    # Master Sword Sacred Glade centered EXACTLY at (44, 10) = DrawMasterSwordIcon!
    # Cleanly fits inside tx=4..6, ty=0..1 (6 tiles) with bright sunlit stone circle!
    swx, swy = MARKERS_PX["sword"]
    c.mark_important_tiles(4, 0, 6, 1, 15.0, "pyramid")
    for dy in range(2):
        for dx in range(4, 7):
            c.blit_tile(dx, dy, _tile_slate(0))
    c.fill_ellipse(swx, swy, 7.6, 5.6, SAND_SH)
    c.fill_ellipse(swx, swy, 6.2, 4.4, SAND_HI)
    c.fill_ellipse(swx, swy, 3.6, 2.6, CREAM)
    for ang_deg in range(0, 360, 45):
        ang = math.radians(ang_deg)
        rx = int(round(swx + math.cos(ang) * 7.0))
        ry = int(round(swy + math.sin(ang) * 5.2))
        if 1 <= ry <= 14:
            c.set(rx, ry, SLATE_DARK)
            c.set(rx, ry - 1, SLATE_HI)
    c.fill_rect(swx - 1, swy - 1, swx + 1, swy + 1, GOLD_MID)
    c.set(swx, swy, GOLD_HI)

    # $42 Lupo Ridge Temple Altar cleanly centered in tx=9..10, ty=0..1 (2x2 = 4 tiles)
    c.mark_important_tiles(9, 0, 10, 1, 10.0, "pyramid")
    for dy in range(2):
        for dx in (9, 10):
            c.blit_tile(dx, dy, _tile_slate(0))
    c.fill_rect(74, 2, 85, 13, INK_SLATE)
    c.fill_rect(75, 3, 84, 12, SLATE_DARK)
    c.fill_rect(77, 5, 82, 10, SLATE_HI)
    c.fill_rect(78, 6, 81, 9, MYSTIC_HI)
    c.set(79, 7, CREAM)

    _draw_lupo_waterfall_aligned(c)

    # Forest Shield Sanctuary right at (16, 80) = DrawForestShieldIcon!
    shx, shy = MARKERS_PX["shield"]
    c.mark_important_tiles(1, 9, 3, 11, 14.0, "mystic")
    c.fill_ellipse(shx, shy, 6.2, 5.2, GRASS_HI)
    c.fill_ellipse(shx, shy, 3.6, 3.0, PATH_HI)
    c.fill_rect(shx - 1, shy - 1, shx + 1, shy + 1, SLATE_HI)
    c.set(shx, shy, MYSTIC_HI)

    # Fortress of Secrets + Obsidian Sanctum
    _draw_fortress_aligned(c)
    _draw_sanctum_aligned(c)

    # Ghost Ship Wreck & Final Boss Caldera Pit ($57)
    _draw_ghost_ship_and_finale_aligned(c)

    # Iconic Yesterwind Windmill ($64)
    _draw_windmill_2x2(c, 18, 16)

    # Eon Escape Meadow Glade right at (79, 176) = DrawEonEscapeIcon!
    ex, ey = MARKERS_PX["escape"]
    c.mark_important_tiles(9, 21, 10, 22, 13.0, "meadow")
    c.fill_ellipse(ex, ey, 5.5, 4.8, GRASS_HI)
    c.fill_ellipse(ex, ey, 3.0, 2.5, PATH_HI)
    c.set(ex, ey, CREAM)

    return c


# ---------------------------------------------------------------------------
# Vanilla ALTTP Outer Folded-Parchment Frame (Tiles $0C..$2D + $EF)
# ---------------------------------------------------------------------------
def _vanilla_border_tile_gfx() -> dict[int, list[int]]:
    b, m, l = PARCH_BASE, PARCH_MID, PARCH_LINE

    def make(fn) -> list[int]:
        return [fn(x, y) for y in range(8) for x in range(8)]

    return {
        0x0C: make(lambda x, y: l if (y == 0 or x == 7) else (m if (y == 1 or x == 6) else b)),
        0x0D: make(lambda x, y: l if x == 7 else (m if x == 6 else b)),
        0x0E: make(lambda x, y: b),
        0x1C: make(lambda x, y: l if (y == 0 or x == 0) else (m if (y == 1 or x == 1) else b)),
        0x1D: make(lambda x, y: l if (y == 7 or x == 7) else (m if (y == 6 or x == 6) else b)),
        0x1E: make(lambda x, y: l if x == 0 else (m if x == 1 else b)),
        0x1F: make(lambda x, y: l if y == 0 else (m if y == 1 else b)),
        0x2C: make(lambda x, y: l if (y == 7 or x == 0) else (m if (y == 6 or x == 1) else b)),
        0x2D: make(lambda x, y: l if y == 7 else (m if y == 6 else b)),
        BORDER_FILL_EF: make(lambda x, y: b),
    }


def _vanilla_outer_frame_tile(row: int, col: int) -> int:
    if row == 15:
        if col == 15:
            return 0x1D
        if col == 48:
            return 0x2C
        return 0x2D
    if row == 48:
        if col == 15:
            return 0x0C
        if col == 48:
            return 0x1C
        return 0x1F
    if col == 15:
        return 0x0D
    if col == 48:
        return 0x1E
    return 0x0E


# ---------------------------------------------------------------------------
# Region-Aware, Seam-Weighted Deterministic Medoid Tile Compiler (<= 246)
# ---------------------------------------------------------------------------
_PIXEL_WEIGHTS: tuple[int, ...] = tuple(
    2 if (x in (0, 7) or y in (0, 7)) else 1
    for y in range(8)
    for x in range(8)
)

PROTECTED_TAGS = frozenset({"finale", "fortress", "village", "waterfall", "pyramid"})


def _color_dist_table(pal_rgb: list[tuple[int, int, int]]) -> list[list[int]]:
    n = len(pal_rgb)
    table = [[0] * n for _ in range(n)]
    for i in range(n):
        r1, g1, b1 = pal_rgb[i]
        row = table[i]
        for j in range(i + 1, n):
            r2, g2, b2 = pal_rgb[j]
            dr, dg, db = r1 - r2, g1 - g2, b1 - b2
            rmean = (r1 + r2) >> 1
            d = (((512 + rmean) * dr * dr) >> 8) + 4 * dg * dg + (((767 - rmean) * db * db) >> 8)
            row[j] = d
            table[j][i] = d
    return table


def _tile_quad_feature(tile: bytes, pal_rgb: list[tuple[int, int, int]]) -> tuple[int, ...]:
    feats: list[int] = []
    for qy in (0, 4):
        for qx in (0, 4):
            sr = sg = sb = 0
            for y in range(qy, qy + 4):
                base = y * 8 + qx
                for x in range(4):
                    r, g, b = pal_rgb[tile[base + x]]
                    sr += r
                    sg += g
                    sb += b
            feats.extend((sr >> 4, sg >> 4, sb >> 4))
    return tuple(feats)


def _tile_dist(a: bytes, b: bytes, cdist: list[list[int]]) -> int:
    total = 0
    w = _PIXEL_WEIGHTS
    for i in range(64):
        ca = a[i]
        cb = b[i]
        if ca != cb:
            total += w[i] * cdist[ca][cb]
    return total


def compile_center_tiles(
    canvas: Canvas,
    pal_bytes: bytes,
    max_tiles: int = MAX_CONTENT_TILES,
) -> tuple[list[list[int]], dict[int, bytes], dict[str, float]]:
    pal_rgb = _palette_rgb_table(pal_bytes)
    cdist = _color_dist_table(pal_rgb)

    unique_blobs: list[bytes] = []
    blob_to_uid: dict[bytes, int] = {}
    uid_weight: list[float] = []
    uid_tag: list[str] = []
    uid_grid = [[0] * CENTER_TILES for _ in range(CENTER_TILES)]

    for ty in range(CENTER_TILES):
        for tx in range(CENTER_TILES):
            pix = bytearray(64)
            y0, x0 = ty * 8, tx * 8
            for dy in range(8):
                row = canvas.px[y0 + dy]
                base = dy * 8
                for dx in range(8):
                    v = row[x0 + dx]
                    if v <= 0 or v >= 128:
                        raise RuntimeError(f"Illegal palette index {v} at ({x0 + dx},{y0 + dy})")
                    pix[base + dx] = v
            blob = bytes(pix)
            uid = blob_to_uid.get(blob)
            if uid is None:
                uid = len(unique_blobs)
                blob_to_uid[blob] = uid
                unique_blobs.append(blob)
                uid_weight.append(0.0)
                uid_tag.append(canvas.tile_tag[ty][tx])
            elif canvas.importance[ty][tx] > uid_weight[uid]:
                uid_tag[uid] = canvas.tile_tag[ty][tx]
            uid_weight[uid] += canvas.importance[ty][tx]
            uid_grid[ty][tx] = uid

    raw_unique = len(unique_blobs)

    active: dict[int, list[int]] = {i: [i] for i in range(raw_unique)}
    c_weight: dict[int, float] = {i: uid_weight[i] for i in range(raw_unique)}
    c_tag: dict[int, str] = {i: uid_tag[i] for i in range(raw_unique)}
    c_rep: dict[int, int] = {i: i for i in range(raw_unique)}
    version: dict[int, int] = {i: 0 for i in range(raw_unique)}

    if raw_unique > max_tiles:
        feats = [_tile_quad_feature(b, pal_rgb) for b in unique_blobs]
        k_neighbors = 28

        def _push_neighbors(cid: int, heap: list[tuple[float, int, int, int, int]]) -> None:
            rep_a = c_rep[cid]
            fa = feats[rep_a]
            wa = c_weight[cid]
            ta = c_tag[cid]
            va = version[cid]
            scored: list[tuple[int, int]] = []
            for other in active:
                if other == cid:
                    continue
                fb = feats[c_rep[other]]
                fd = sum((fa[k] - fb[k]) * (fa[k] - fb[k]) for k in range(12))
                if c_tag[other] != ta:
                    fd += 150000
                scored.append((fd, other))
            scored.sort()
            blob_a = unique_blobs[rep_a]
            for _, other in scored[:k_neighbors]:
                rep_b = c_rep[other]
                dist = _tile_dist(blob_a, unique_blobs[rep_b], cdist)
                wb = c_weight[other]
                tb = c_tag[other]
                mult = 1.0
                if ta != tb:
                    mult = 18.0 if (ta in PROTECTED_TAGS or tb in PROTECTED_TAGS) else 4.0
                cost = dist * mult * (wa * wb) / (wa + wb)
                lo, hi = (cid, other) if cid < other else (other, cid)
                v_lo, v_hi = (va, version[other]) if cid < other else (version[other], va)
                heapq.heappush(heap, (cost, lo, hi, v_lo, v_hi))

        heap: list[tuple[float, int, int, int, int]] = []
        for cid in range(raw_unique):
            _push_neighbors(cid, heap)

        while len(active) > max_tiles:
            if not heap:
                for cid in sorted(active):
                    _push_neighbors(cid, heap)
            cost, a, b, va, vb = heapq.heappop(heap)
            if a not in active or b not in active:
                continue
            if version[a] != va or version[b] != vb:
                continue
            keep, drop = (a, b) if (c_weight[a], -a) >= (c_weight[b], -b) else (b, a)
            members = active[keep] + active.pop(drop)
            active[keep] = members
            c_weight[keep] += c_weight.pop(drop)
            c_tag.pop(drop)
            c_rep.pop(drop)
            version.pop(drop)
            if len(members) <= 12:
                best_m = c_rep[keep]
                best_err = float("inf")
                for cand in members:
                    bc = unique_blobs[cand]
                    err = sum(uid_weight[m] * _tile_dist(bc, unique_blobs[m], cdist) for m in members if m != cand)
                    if err < best_err or (err == best_err and cand < best_m):
                        best_err = err
                        best_m = cand
                c_rep[keep] = best_m
            version[keep] += 1
            _push_neighbors(keep, heap)

    final_clusters = sorted(active.keys())
    uid_to_tile_idx: dict[int, int] = {}
    tile_gfx: dict[int, bytes] = {}
    for slot_pos, cid in enumerate(final_clusters):
        t_idx = CONTENT_TILE_SLOTS[slot_pos]
        tile_gfx[t_idx] = unique_blobs[c_rep[cid]]
        for m in active[cid]:
            uid_to_tile_idx[m] = t_idx

    sq_err = 0.0
    out_grid = [[0] * CENTER_TILES for _ in range(CENTER_TILES)]
    for ty in range(CENTER_TILES):
        for tx in range(CENTER_TILES):
            uid = uid_grid[ty][tx]
            t_idx = uid_to_tile_idx[uid]
            out_grid[ty][tx] = t_idx
            orig = unique_blobs[uid]
            rep = tile_gfx[t_idx]
            if orig != rep:
                for i in range(64):
                    r1, g1, b1 = pal_rgb[orig[i]]
                    r2, g2, b2 = pal_rgb[rep[i]]
                    sq_err += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
    rmse = math.sqrt(sq_err / (CENTER_PX * CENTER_PX * 3.0))

    stats = {
        "raw_unique_tiles": float(raw_unique),
        "compiled_content_tiles": float(len(final_clusters)),
        "quant_rmse_rgb": rmse,
    }
    return out_grid, tile_gfx, stats


# ---------------------------------------------------------------------------
# Assemble Final SNES Mode 7 Binaries (Tileset, GFX, Palette)
# ---------------------------------------------------------------------------
def build_assets_with_stats() -> tuple[bytes, bytes, bytes, dict[str, float]]:
    palette = build_palette_bytes()
    canvas = build_center_canvas()
    center_grid, content_gfx, stats = compile_center_tiles(canvas, palette)

    grid = [[0] * MAP_TILES for _ in range(MAP_TILES)]
    for row in range(MAP_TILES):
        for col in range(MAP_TILES):
            if CENTER_START <= row < CENTER_START + CENTER_TILES and CENTER_START <= col < CENTER_START + CENTER_TILES:
                grid[row][col] = center_grid[row - CENTER_START][col - CENTER_START]
            else:
                grid[row][col] = _vanilla_outer_frame_tile(row, col)

    tileset = bytearray(TILESET_SIZE)
    quads = ((0, 0), (0, 32), (32, 0), (32, 32))
    for quad, (row0, col0) in enumerate(quads):
        base = quad * 1024
        for row in range(32):
            for col in range(32):
                tileset[base + row * 32 + col] = grid[row0 + row][col0 + col]

    gfx = bytearray(GFX_SIZE)
    for t_idx, pix in _vanilla_border_tile_gfx().items():
        base = t_idx * 64
        gfx[base:base + 64] = bytes(pix)
    for t_idx, blob in content_gfx.items():
        base = t_idx * 64
        gfx[base:base + 64] = blob

    tileset_b, gfx_b = bytes(tileset), bytes(gfx)
    _validate(tileset_b, gfx_b, palette)
    return tileset_b, gfx_b, palette, stats


def build_assets() -> tuple[bytes, bytes, bytes]:
    tileset, gfx, palette, _ = build_assets_with_stats()
    return tileset, gfx, palette


def _validate(tileset: bytes, gfx: bytes, palette: bytes) -> None:
    if (len(tileset), len(gfx), len(palette)) != (TILESET_SIZE, GFX_SIZE, PAL_SIZE):
        raise RuntimeError(f"Asset sizes drifted: {(len(tileset), len(gfx), len(palette))}")
    used = set(tileset)
    for bt in VANILLA_FRAME_TILES:
        if bt not in used:
            raise RuntimeError(f"Vanilla border tile ${bt:02X} missing from tileset")
    content = used - RESERVED_TILES
    if len(content) > MAX_CONTENT_TILES:
        raise RuntimeError(f"{len(content)} content tiles exceeds {MAX_CONTENT_TILES}")
    if gfx[BORDER_FILL_EF * 64:(BORDER_FILL_EF + 1) * 64] != bytes([PARCH_BASE] * 64):
        raise RuntimeError("Tile $EF is not solid parchment fill")
    bad = [idx for idx, val in enumerate(gfx) if val >= 128]
    if bad:
        raise RuntimeError(f"{len(bad)} CHR pixels use palette index >= 128")


def decode_to_image(tileset: bytes, gfx: bytes, palette: bytes, crop_center: bool = False):
    from PIL import Image

    colors = _palette_rgb_table(palette)
    grid = [[0] * MAP_TILES for _ in range(MAP_TILES)]
    quads = ((0, 0), (0, 32), (32, 0), (32, 32))
    for quad, (row0, col0) in enumerate(quads):
        base = quad * 1024
        for row in range(32):
            for col in range(32):
                grid[row0 + row][col0 + col] = tileset[base + row * 32 + col]

    image = Image.new("RGB", (MAP_TILES * 8, MAP_TILES * 8))
    dest = image.load()
    for ty in range(MAP_TILES):
        for tx in range(MAP_TILES):
            base = grid[ty][tx] * 64
            for y in range(8):
                for x in range(8):
                    dest[tx * 8 + x, ty * 8 + y] = colors[gfx[base + y * 8 + x]]
    if crop_center:
        image = image.crop((128, 128, 384, 384))
    return image


def write_preview(path: Path, scale: int = 2, crop_center: bool = False) -> None:
    from PIL import Image

    tileset, gfx, palette = build_assets()
    image = decode_to_image(tileset, gfx, palette, crop_center=crop_center)
    if scale != 1:
        image = image.resize((image.width * scale, image.height * scale), Image.Resampling.NEAREST)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)


def _paths() -> tuple[Path, Path, Path]:
    return TILESET_PATH, GFX_PATH, PAL_PATH


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify checked-in binaries match generator")
    parser.add_argument("--preview", type=Path, help="Write nearest-neighbor PNG decoded from packed Mode 7 binaries")
    parser.add_argument("--preview-center", action="store_true", help="Crop --preview to central 256x256 map")
    parser.add_argument("--scale", type=int, default=2, help="Integer nearest-neighbor preview scale (default: 2)")
    args = parser.parse_args()

    tileset, gfx, palette, stats = build_assets_with_stats()
    if args.preview:
        from PIL import Image

        img = decode_to_image(tileset, gfx, palette, crop_center=args.preview_center)
        if args.scale != 1:
            img = img.resize((img.width * args.scale, img.height * args.scale), Image.Resampling.NEAREST)
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        img.save(args.preview)
        print(f"Wrote {args.preview} ({img.width}x{img.height})")

    if args.check:
        expected = (tileset, gfx, palette)
        names = ("DwMapTileset.bin", "DwMapGfx.bin", "dw_palette.bin")
        failed = False
        for path, want, name in zip(_paths(), expected, names):
            if not path.is_file():
                print(f"MISSING {path}", file=sys.stderr)
                failed = True
                continue
            have = path.read_bytes()
            if have != want:
                print(f"MISMATCH {name}: {len(have)} bytes on disk, {len(want)} generated", file=sys.stderr)
                failed = True
        if failed:
            return 1
        used = set(tileset)
        print(
            f"OK abyss world map: content {len(used - RESERVED_TILES)}/{MAX_CONTENT_TILES} "
            f"+ 9 frame + $EF (raw {int(stats['raw_unique_tiles'])}, RMSE {stats['quant_rmse_rgb']:.2f}), "
            f"colors {len(PALETTE_ENTRIES) - 1}/127, gfx {len(gfx)} B"
        )
        return 0

    for path, blob in zip(_paths(), (tileset, gfx, palette)):
        path.write_bytes(blob)
        print(f"Wrote {path} ({len(blob)} bytes)")
    print(
        f"Stats: raw_unique={int(stats['raw_unique_tiles'])}, "
        f"compiled={int(stats['compiled_content_tiles'])}/{MAX_CONTENT_TILES}, "
        f"quant_rmse={stats['quant_rmse_rgb']:.2f}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
