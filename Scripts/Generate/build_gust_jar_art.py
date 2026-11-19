#!/usr/bin/env python3
"""Generate custom 4BPP Minish Cap-style Gust Jar & Wind Effect world tiles.

Output:
  Data/graphics/items/gust_jar_world.4bpp (1,152 bytes = $0480 = 9 x 16x16 blocks)

Each 128-byte block is stored in SNES 16x16 OBJ row-major DMA order:
  +$00..$3F (64 B): Top row    (TL tile 32B + TR tile 32B) -> VRAM $4070 / $4090
  +$40..$7F (64 B): Bottom row (BL tile 32B + BR tile 32B) -> VRAM $4170 / $4190

Block map (streamed during NMI by GustJar_NmiUpload in Bank $34):
  0 (+$000): Jar 0 — Side Normal (Right; H-flip for Left)        [Pal 4 $08 / Pal 2 $04]
  1 (+$080): Jar 1 — Side Swollen/Bulging (Tier 2/3 or Corked)   [Pal 4 $08 / Pal 2 $04]
  2 (+$100): Jar 2 — Front / Down View (Open Circular Nozzle)    [Pal 4 $08 / Pal 2 $04]
  3 (+$180): Jar 3 — Back / Up View (Flared Top Nozzle)          [Pal 4 $08 / Pal 2 $04]
  4 (+$200): Inhale Wind Set (4 x 8x8 tiles: $09,$0A,$19,$1A)    [Pal 2 $04]
  5 (+$280): Blast H0 — Horizontal Crescent Air-Gust Wave A (R)  [Pal 2 $04]
  6 (+$300): Blast H1 — Horizontal Billowing Gust Wave B (R)     [Pal 2 $04]
  7 (+$380): Blast V0 — Vertical Crescent Air-Gust Wave A (D)    [Pal 2 $04]
  8 (+$400): Blast V1 — Vertical Billowing Gust Wave B (D)       [Pal 2 $04]

Palette invariants verified against live ROM global sprite tables ($1BD218 / $1BD290):
  - Held Jar uses ONLY indices {0, 8, 9, 11, 12, 13, 14, 15}:
      100% byte-identical across Light World, Dungeons, and Dark World!
      Pal 4 ($08): #000000 hollow mouth, #FFFFFF shine, #4A9431/#9CD673 emerald,
                   #292929 outline, #FFD639/#BD8C21 Minish gold collar & rim.
      Pal 2 ($04): cleanly shifts emerald -> glowing wind-sapphire (#526BAD/#94ADEF)
                   and gold -> warm amber-gold (#FFB552/#BD6329) on Tier 3 / Blast Peak!
  - Wind Effects use ONLY indices {0, 1, 3, 4, 6, 11} under OAM Pal 2 ($04):
      LW/Dungeon: #FFFFFF white, #A5FFDE pale mint, #8CD6FF ice-sky, #63BDC6 aqua, #526BAD accent.
      Dark World: #FFFFFF white, #ADF7FF ice-white, #84D6BD mint, #7BB5CE sky, #526BAD accent.

Usage:
  python3 Scripts/Generate/build_gust_jar_art.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_4BPP = ROOT / "Data/graphics/items/gust_jar_world.4bpp"

# Held Gust Jar pixel legend -> SNES 4BPP color indices (OAM Pal 4 normal / Pal 2 glow)
JAR_LEGEND = {
    ".": 0,   # transparent
    "0": 8,   # #000000 deep hollow nozzle interior
    "w": 9,   # #FFFFFF pure white ceramic specular glaze / rim highlight
    "d": 11,  # #4A9431 deep emerald shade (Pal 2: #526BAD)
    "g": 12,  # #9CD673 bright Minish emerald (Pal 2: #94ADEF)
    "k": 13,  # #292929 crisp ALTTP charcoal outline
    "y": 14,  # #FFD639 bright Minish gold collar & bell rim (Pal 2: #FFB552)
    "o": 15,  # #BD8C21 warm shaded gold-bronze (Pal 2: #BD6329)
}

# Wind & Blast Wave pixel legend -> SNES 4BPP color indices (OAM Pal 2)
WIND_LEGEND = {
    ".": 0,   # transparent
    "W": 1,   # #FFFFFF pure white leading crest / core
    "T": 3,   # #63BDC6 (LW) / #7BB5CE (DW) crisp aqua-cyan airflow contour
    "M": 4,   # #A5FFDE (LW) / #ADF7FF (DW) luminous pale mint / ice-white glow
    "C": 6,   # #8CD6FF (LW) / #84D6BD (DW) soft sky-cyan / mint-aqua body
    "B": 11,  # #526BAD (LW & DW identical) subtle crisp slate-blue rim accent
}

# Exact ROM palette colors (from $1BD218 LW/UW & $1BD290 DW) for accurate PNG previews
PAL4_RGB = {
    0: (0, 0, 0, 0),
    8: (0, 0, 0, 255),
    9: (255, 255, 255, 255),
    11: (74, 148, 49, 255),
    12: (156, 214, 115, 255),
    13: (41, 41, 41, 255),
    14: (255, 214, 57, 255),
    15: (189, 140, 33, 255),
}

PAL2_LW_RGB = {
    0: (0, 0, 0, 0),
    1: (255, 255, 255, 255),
    3: (99, 189, 198, 255),
    4: (165, 255, 222, 255),
    6: (140, 214, 255, 255),
    8: (0, 0, 0, 255),
    9: (255, 255, 255, 255),
    11: (82, 107, 173, 255),
    12: (148, 173, 239, 255),
    13: (41, 41, 41, 255),
    14: (255, 181, 82, 255),
    15: (189, 99, 41, 255),
}

PAL2_DW_RGB = {
    **PAL2_LW_RGB,
    3: (123, 181, 206, 255),
    4: (173, 247, 255, 255),
    6: (132, 214, 189, 255),
}

# =============================================================================
# 1. HELD GUST JAR (4 x 16x16 frames, $000..$1FF)
# =============================================================================

# Block 0: Side Normal (Facing Right; H-flip for Left)
# Authentic Minish Cap squat ribbed emerald pot tapering smoothly into a pinched
# golden neck collar and flaring into a gleaming gold trumpet suction bell!
JAR_0_SIDE_NORMAL = [
    "................",
    "................",
    "...........kkk..",
    "...kkkkk..kwwyk.",
    "..kgggggkkwy0yok",
    ".kgwwggggyyw00yk",
    "kogwgggggyyo000k",
    "kygggdgggyyo000k",
    "kygggdgggyyo000k",
    "kogggdgggyyo000k",
    ".kddgddddyyo00yk",
    "..kdddddkkoo0yok",
    "...kkkkk..koook.",
    "...........kkk..",
    "................",
    "................",
]

# Block 1: Side Swollen / Bulging (Tier 2/3 pulse or Corked, Facing Right)
# Iconic Minish Cap inflated belly puffing noticeably rounder (+2px top & bottom)
# with bright stretched ceramic sheen & strained wide-open trumpet mouth!
JAR_1_SIDE_SWOLLEN = [
    "................",
    "...kkkkk...kkk..",
    "..kgggggk.kwwyk.",
    ".kgwwwgggkwy0yok",
    "kggwwwgggyyw00yk",
    "koggdggggyyo000k",
    "kyggdggggyyo000k",
    "kyggdggggyyo000k",
    "kyggddgggyyo000k",
    "koggddgggyyo000k",
    "koddddgggyyo000k",
    ".kddddddgyyo00yk",
    "..kddddddkoo0yok",
    "...kkkkk..koook.",
    "...........kkk..",
    "................",
]

# Block 2: Front / Down View (ALTTP 3/4 overhead angle, open circular nozzle!)
# Plump rounded emerald ceramic dome + pinched gold collar band + gleaming oval
# golden trumpet rim framing a clean rounded dark suction opening facing down.
JAR_2_FRONT_DOWN = [
    "................",
    "....kkkkkkkk....",
    "..kkggggggggkk..",
    ".kggwwggggdggdk.",
    ".kggwgggggdggdk.",
    "kgggggggggdggddk",
    "kggdggggggdddddk",
    ".kkyywwwwyyyykk.",
    ".kyyyyooyyyyyyk.",
    "kkyw00000000wykk",
    "kyy0000000000ook",
    "koy0000000000ook",
    ".koyy000000yook.",
    "..kkoooooooook..",
    "....kkkkkkkk....",
    "................",
]

# Block 3: Back / Up View (Facing Up, drawn behind Link in Region B)
# Wide flared gleaming golden trumpet bell pointing UP (peeking cleanly above
# Link's raised hands & cap) + pinched gold neck + glossy emerald pot body.
JAR_3_BACK_UP = [
    "...kkkkkkkkkk...",
    "..kwwyyyyyyook..",
    ".kwyy000000yyok.",
    ".kkyyyyyyyyyokk.",
    "...kkyyyyooyk...",
    "..kkggggggggkk..",
    ".kggwwggggdggdk.",
    "kggwwgggggdggddk",
    "kgggggggggdggddk",
    "kggggdggggdggddk",
    "kggggdggggdddddk",
    "kddddddddddddddk",
    ".kddddddddddddk.",
    "..kkoooooooook..",
    "....kkkkkkkk....",
    "................",
]

# =============================================================================
# 2. MINISH CAP INHALE WIND SET (Block 4, $200..$27F: 4 distinct 8x8 tiles)
#    TL = $09 (Horizontal Tapered Speed-Streak, pointing Right; H-flip for Left)
#    TR = $0A (Vertical Swooping Airflow Ribbon, pointing Down; V-flip for Up)
#    BL = $19 (Curled Minish Wind Wisp / Air-Loop Puff — hollow breezy curl!)
#    BR = $1A (Curved Flared Suction-Ring Sheen at nozzle mouth, Right; H-flip L)
# =============================================================================

TILE_09_H_STREAK = [
    "........",
    "....TT..",
    "..TCMWW.",
    "TCMWWWW.",
    ".BCMMWT.",
    "...BT...",
    "........",
    "........",
]

TILE_0A_V_RIBBON = [
    "..T.....",
    "..CT....",
    "..MCB...",
    ".TMMT...",
    ".CMWC...",
    ".TWWC...",
    "..WWB...",
    "..TT....",
]

TILE_19_AIR_CURL = [
    "..TTMM..",
    ".TMWWWM.",
    "TWWC.TWW",
    "MWB...MW",
    "MC.MW.CT",
    ".CTWT.B.",
    "..BBT...",
    "........",
]

TILE_1A_NOZZLE_SHEEN = [
    "....TC..",
    "...CMW..",
    "..TWM...",
    "..MWB.M.",
    "..MWB.W.",
    "..TWM...",
    "...CMW..",
    "....TC..",
]


def _compose_4_tiles(tl: list[str], tr: list[str], bl: list[str], br: list[str]) -> list[str]:
    top = [a + b for a, b in zip(tl, tr)]
    bot = [a + b for a, b in zip(bl, br)]
    return top + bot


INHALE_WIND_SET = _compose_4_tiles(
    TILE_09_H_STREAK,
    TILE_0A_V_RIBBON,
    TILE_19_AIR_CURL,
    TILE_1A_NOZZLE_SHEEN,
)

# =============================================================================
# 3. MINISH CAP BLAST WAVE PROJECTILE SET (Blocks 5..8, $280..$47F)
#    Stylized curved C-shaped Minish Cap rushing wind crescent clouds with
#    bright white leading rim, luminous mint-aqua body & twin curling tips!
# =============================================================================

# Block 5: Blast H0 — Horizontal Crescent Air-Gust Wave A (Facing Right; H-flip Left)
BLAST_H0_CRESCENT = [
    "....TTT.........",
    "..TCMMMTT.......",
    ".TMWWMWWMMT.....",
    ".TWCTB.CMWWM....",
    "..B.....TMWWMT..",
    ".........CMWWWT.",
    "....TTM..TMWWWM.",
    "..TCMWWT..CMWWWM",
    "..BCMMT...CMWWWM",
    ".........TMWWWM.",
    ".........CMWWWT.",
    "..B.....TMWWMT..",
    ".TWCTB.CMWWM....",
    ".TMWWMWWMMT.....",
    "..TCMMMTT.......",
    "....TTT.........",
]

# Block 6: Blast H1 — Horizontal Billowing Gust Wave B (animated frame 2, Right)
BLAST_H1_BILLOW = [
    "..TTMMTT........",
    ".TMWWWWMMT......",
    "TWWC.TTMWWMT....",
    ".BB....CMWWWM...",
    "....T...TMWWWM..",
    "..TMWT..CMWWWWM.",
    "..BCBT..TMWWWWM.",
    "TCMWWT...CMWWWWM",
    ".BCMMT...CMWWWWM",
    "..TTB...TMWWWWM.",
    "..CMWT..CMWWWWM.",
    "....B...TMWWWM..",
    ".TT....CMWWWM...",
    "TWWC.TTMWWMT....",
    ".TMWWWWMMT......",
    "..TTMMTT........",
]

# Block 7: Blast V0 — Vertical Crescent Air-Gust Wave A (Facing Down; V-flip Up)
# Exact 90-degree rounded crescent counterpart of Blast H0 (graceful curved
# Minish Cap air-gust arc with twin curling scroll tips & center breeze streak).
BLAST_V0_CRESCENT = [
    "................",
    "..TT........TT..",
    ".TMMT......TMMT.",
    "TMWWMT....TMWWMT",
    "TWC.BT.TT.TB.CWT",
    "TMB...TMMT...BMT",
    ".CT...CMWT...TC.",
    "..TM..BCMT..MT..",
    "..TMM......MMT..",
    "...CMMT..TMMC...",
    "...TMWWTTWWMT...",
    "....CMWWWWMC....",
    "...TMWWWWWWMT...",
    "....TCMWWWCT....",
    ".....TCMMCT.....",
    "......BBBB......",
]

# Block 8: Blast V1 — Vertical Billowing Gust Wave B (animated frame 2, Down)
# Puffier scalloped vertical billowing crescent mirroring Blast H1!
BLAST_V1_BILLOW = [
    ".......TT.......",
    ".TT...TMMT...TT.",
    "TMMT..CMWT..TMMT",
    "MWWT..CMWT..TWWM",
    "WWCB..BTTB..BCWW",
    "TMB...TMMT...BMT",
    ".CT...B..B...TC.",
    "..TM........MT..",
    ".TMMT......TMMT.",
    ".MWWMMTTTTMMWWM.",
    "..CMWWWWWWWWMC..",
    "..TMWWWWWWWWMT..",
    "...CMWWWWWWMC...",
    "....TMWWWWMT....",
    ".....TCMMCT.....",
    "......BBBB......",
]

BLOCKS: list[tuple[str, list[str], dict[str, int], str]] = [
    ("jar_0_side_normal",  JAR_0_SIDE_NORMAL,  JAR_LEGEND,  "jar"),
    ("jar_1_side_swollen", JAR_1_SIDE_SWOLLEN, JAR_LEGEND,  "jar"),
    ("jar_2_front_down",   JAR_2_FRONT_DOWN,   JAR_LEGEND,  "jar"),
    ("jar_3_back_up",      JAR_3_BACK_UP,      JAR_LEGEND,  "jar"),
    ("inhale_wind_set",    INHALE_WIND_SET,    WIND_LEGEND, "wind"),
    ("blast_h0_crescent",  BLAST_H0_CRESCENT,  WIND_LEGEND, "wind"),
    ("blast_h1_billow",    BLAST_H1_BILLOW,    WIND_LEGEND, "wind"),
    ("blast_v0_crescent",  BLAST_V0_CRESCENT,  WIND_LEGEND, "wind"),
    ("blast_v1_billow",    BLAST_V1_BILLOW,    WIND_LEGEND, "wind"),
]


def parse_grid(name: str, rows: list[str], legend: dict[str, int]) -> list[list[int]]:
    if len(rows) != 16:
        raise ValueError(f"{name}: expected 16 rows, got {len(rows)}")
    out: list[list[int]] = []
    for r, line in enumerate(rows):
        if len(line) != 16:
            raise ValueError(f"{name} row {r}: expected 16 cols, got {len(line)}")
        vals = []
        for c, ch in enumerate(line):
            if ch not in legend:
                raise ValueError(f"{name} ({r},{c}): unexpected char {ch!r}")
            vals.append(legend[ch])
        out.append(vals)
    return out


def encode_tile_4bpp(grid: list[list[int]], ox: int, oy: int) -> bytes:
    """Encode an 8x8 tile from 16x16 pixel indices (0..15) into 32-byte SNES 4BPP."""
    tile = bytearray(32)
    for y in range(8):
        p0 = p1 = p2 = p3 = 0
        for x in range(8):
            v = grid[oy + y][ox + x]
            bit = 0x80 >> x
            if v & 1:
                p0 |= bit
            if v & 2:
                p1 |= bit
            if v & 4:
                p2 |= bit
            if v & 8:
                p3 |= bit
        tile[y * 2] = p0
        tile[y * 2 + 1] = p1
        tile[16 + y * 2] = p2
        tile[16 + y * 2 + 1] = p3
    return bytes(tile)


def encode_block_16x16(grid: list[list[int]]) -> bytes:
    """Encode a 16x16 OBJ block in SNES DMA row-major order: TL, TR (64B), BL, BR (64B)."""
    return (
        encode_tile_4bpp(grid, 0, 0)
        + encode_tile_4bpp(grid, 8, 0)
        + encode_tile_4bpp(grid, 0, 8)
        + encode_tile_4bpp(grid, 8, 8)
    )


def build_4bpp() -> bytes:
    out = bytearray()
    for name, rows, legend, _kind in BLOCKS:
        grid = parse_grid(name, rows, legend)
        out += encode_block_16x16(grid)
    assert len(out) == 9 * 128 == 0x480, f"Unexpected 4BPP size {len(out)}"
    return bytes(out)


def render_preview(out_png: Path, scale: int = 8) -> None:
    from PIL import Image, ImageDraw

    grids = [(name, parse_grid(name, rows, legend), kind) for name, rows, legend, kind in BLOCKS]

    def blit_sprite(canvas: Image.Image, grid: list[list[int]], pal: dict[int, tuple[int, int, int, int]],
                    x0: int, y0: int, hflip: bool = False, vflip: bool = False) -> None:
        spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = spr.load()
        for y in range(16):
            sy = 15 - y if vflip else y
            for x in range(16):
                sx = 15 - x if hflip else x
                px[x, y] = pal[grid[sy][sx]]
        spr = spr.resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        canvas.alpha_composite(spr, (x0, y0))

    cell = 16 * scale
    pad = 16
    label_h = 22
    cols = 6
    rows_n = 4
    w = pad + cols * (cell + pad)
    h = pad + rows_n * (cell + label_h + pad) + 28
    img = Image.new("RGBA", (w, h), (30, 34, 42, 255))
    draw = ImageDraw.Draw(img)
    draw.text((pad, 6), "Minish Cap Gust Jar & Wind Effects - 4BPP SNES Palette Preview (8x)", fill=(245, 245, 245, 255))

    jar_grids = {n: g for n, g, k in grids if k == "jar"}
    wind_grids = {n: g for n, g, k in grids if k == "wind"}

    row_specs = [
        ("Row 1: Held Jar - OAM Pal 4 ($08) Normal (Grass & Dungeon BG)", (72, 128, 64, 255), [
            ("Jar0 Side R",    jar_grids["jar_0_side_normal"],  PAL4_RGB, False, False),
            ("Jar0 Side L",    jar_grids["jar_0_side_normal"],  PAL4_RGB, True,  False),
            ("Jar1 Swollen R", jar_grids["jar_1_side_swollen"], PAL4_RGB, False, False),
            ("Jar2 Front D",   jar_grids["jar_2_front_down"],   PAL4_RGB, False, False),
            ("Jar3 Back U",    jar_grids["jar_3_back_up"],      PAL4_RGB, False, False),
            ("Jar0 (Dungeon)", jar_grids["jar_0_side_normal"],  PAL4_RGB, False, False),
        ]),
        ("Row 2: Held Jar - OAM Pal 2 ($04) Tier 3 / Blast Peak Glow", (48, 52, 68, 255), [
            ("Glow Side R",    jar_grids["jar_0_side_normal"],  PAL2_LW_RGB, False, False),
            ("Glow Swollen",   jar_grids["jar_1_side_swollen"], PAL2_LW_RGB, False, False),
            ("Glow Front D",   jar_grids["jar_2_front_down"],   PAL2_LW_RGB, False, False),
            ("Glow Back U",    jar_grids["jar_3_back_up"],      PAL2_LW_RGB, False, False),
            ("Inhale $09-$1A", wind_grids["inhale_wind_set"],   PAL2_LW_RGB, False, False),
            ("Inhale (Grass)", wind_grids["inhale_wind_set"],   PAL2_LW_RGB, False, False),
        ]),
        ("Row 3: Minish Cap Blast Waves - Light World / Dungeon OAM Pal 2 ($04)", (54, 70, 82, 255), [
            ("Blast H0 (R)",   wind_grids["blast_h0_crescent"], PAL2_LW_RGB, False, False),
            ("Blast H1 (R)",   wind_grids["blast_h1_billow"],   PAL2_LW_RGB, False, False),
            ("Blast H0 (L)",   wind_grids["blast_h0_crescent"], PAL2_LW_RGB, True,  False),
            ("Blast V0 (D)",   wind_grids["blast_v0_crescent"], PAL2_LW_RGB, False, False),
            ("Blast V1 (D)",   wind_grids["blast_v1_billow"],   PAL2_LW_RGB, False, False),
            ("Blast V0 (U)",   wind_grids["blast_v0_crescent"], PAL2_LW_RGB, False, True),
        ]),
        ("Row 4: Wind & Blast Waves - Dark World OAM Pal 2 ($04) Parity", (62, 54, 68, 255), [
            ("DW Inhale",      wind_grids["inhale_wind_set"],   PAL2_DW_RGB, False, False),
            ("DW Blast H0",    wind_grids["blast_h0_crescent"], PAL2_DW_RGB, False, False),
            ("DW Blast H1",    wind_grids["blast_h1_billow"],   PAL2_DW_RGB, False, False),
            ("DW Blast V0",    wind_grids["blast_v0_crescent"], PAL2_DW_RGB, False, False),
            ("DW Blast V1",    wind_grids["blast_v1_billow"],   PAL2_DW_RGB, False, False),
            ("DW Blast V0(U)", wind_grids["blast_v0_crescent"], PAL2_DW_RGB, False, True),
        ]),
    ]

    for r_idx, (title, bg, items) in enumerate(row_specs):
        ry = 28 + pad + r_idx * (cell + label_h + pad)
        draw.text((pad, ry - 16), title, fill=(215, 225, 235, 255))
        for c_idx, (cap, grid, pal, hf, vf) in enumerate(items):
            cx = pad + c_idx * (cell + pad)
            box_bg = (52, 54, 64, 255) if "Dungeon" in cap else ((88, 148, 72, 255) if "Grass" in cap else bg)
            draw.rectangle((cx, ry, cx + cell - 1, ry + cell - 1), fill=box_bg, outline=(95, 105, 120, 255))
            blit_sprite(img, grid, pal, cx, ry, hflip=hf, vflip=vf)
            draw.text((cx + 2, ry + cell + 3), cap, fill=(235, 235, 235, 255))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    print(f"Wrote preview: {out_png} ({w}x{h})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_4BPP, help="Output 4BPP path")
    ap.add_argument("--check", action="store_true", help="Verify output matches freshly built bytes")
    ap.add_argument("--preview", type=Path, help="Write zoomed RGBA preview sheet PNG")
    ap.add_argument("--scale", type=int, default=8, help="Preview integer pixel scale (default 8)")
    args = ap.parse_args(argv)

    data = build_4bpp()
    if args.preview:
        render_preview(args.preview, scale=args.scale)

    if args.check:
        if not args.out.is_file():
            print(f"MISSING: {args.out}", file=sys.stderr)
            return 1
        cur = args.out.read_bytes()
        if cur != data:
            print(f"STALE: {args.out} differs from freshly built bytes ({len(cur)} vs {len(data)})", file=sys.stderr)
            return 1
        print(f"OK: {args.out} up to date ({len(data)} bytes)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(f"Wrote {args.out} ({len(data)} bytes = ${len(data):04X}, 9 x 16x16 blocks)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
