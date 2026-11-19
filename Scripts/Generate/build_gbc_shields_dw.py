#!/usr/bin/env python3
"""Generate compact, face-clearing Dark World GBC Shield Trilogy 4BPP tiles.

Output:
  Data/graphics/items/gbc_shields_dw.4bpp (1,152 bytes = 3 levels x 12 tiles x 32 B)

Layout per 384-byte shield level (copied directly to GFX_SHIELD $7E9300..$7E947F
by ShieldWorld_SyncTiles in Items/mirror_shield_palette.asm when SavedWorld == $40):
  Top row    (+$000..$0BF, 6 tiles): Front TL, Front TR, Back TL, Back TR, Side TL, Side TR
  Bottom row (+$0C0..$17F, 6 tiles): Front BL, Front BR, Back BL, Back BR, Side BL, Side BR

Proportion & Face-Clearance Invariants for GBC Link (Masks/gfx/gbc_link.4bpp):
  - GBC Link's sprite is compact (~16px tall, sitting lower in ALTTP's 16x24 OAM box:
    head y=[5..15], eyes y=[8..11], chin y=[12..14], body/boots y=[13..20]).
  - ALTTP's LinkOAM_DrawShield draws the 16x16 shield OAM at:
      Down (Front): dx=-4, dy=+8 standing (+6..+9 walk)
      Up   (Back):  dx=+5, dy=+4 standing (+2..+4 walk)
      Left (Side):  dx=-8, dy=+4 standing (+2..+4 walk, unflipped)
      Right(Side):  dx=+8, dy=+4 standing (+2..+4 walk, H-flipped)
  - Therefore ALL THREE DW GBC shields keep top rows y=0..5 transparent on Front/Back
    (and y=0..5/6 transparent on Side), anchoring compact 9x9..9x10 silhouettes low
    in the 16x16 cell so GBC Link's full face, eyes, and chin stay 100% unobstructed!

Palette Invariants (SP-5 C12..C15 + Option D C8; ZERO Sword C9..C11 bleed):
  - L1 GBC Wooden Shield: {0, 12, 13, 14, 15}
      C12=$379F (#F8E068 brass), C13=$0865 (#281810 outline),
      C14=$15F9 (#C87828 oak),   C15=$08EF (#783810 walnut)
  - L2 GBC Iron Shield:   {0, 12, 13, 14, 15}
      C12=$7BDE (#F0F0F8 silver), C13=$1CA4 (#202838 navy-steel outline),
      C14=$6ECE (#70B0DC steel),  C15=$4947 (#385090 iron-slate)
  - L3 GBC Mirror Shield: {0, 8, 12, 13, 14, 15} (original $1BD658 + SP-5 C8!)
      C8 =$67F8 (#C6FFCE pale turquoise-silver), C12=$3B3B (#DECE73 gold rim),
      C13=$18C6 (#313131 dark outline),          C14=$62F8 (#C6BDC6 silver-lavender),
      C15=$518B (#5A63A5 indigo mirror face)

Usage:
  python3 Scripts/Generate/build_gbc_shields_dw.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_4BPP = ROOT / "Data/graphics/items/gbc_shields_dw.4bpp"

# L1 Wooden Shield pixel legend -> 4BPP indices (SP-5 C12..C15)
L1_LEGEND = {
    ".": 0,   # transparent
    "Y": 12,  # $379F #F8E068 bright golden-brass rim & cross
    "K": 13,  # $0865 #281810 deep warm umber outline
    "O": 14,  # $15F9 #C87828 warm Oracle oak wood
    "W": 15,  # $08EF #783810 deep walnut wood grain / shadow
}

# L2 Iron Shield pixel legend -> 4BPP indices (SP-5 C12..C15)
L2_LEGEND = {
    ".": 0,   # transparent
    "S": 12,  # $7BDE #F0F0F8 gleaming silver bevel & center crest
    "K": 13,  # $1CA4 #202838 deep cool navy-steel outline
    "B": 14,  # $6ECE #70B0DC cool steely-blue face
    "D": 15,  # $4947 #385090 deep iron-slate shadow
}

# L3 Mirror Shield pixel legend -> 4BPP indices (original $1BD658 + SP-5 C8)
L3_LEGEND = {
    ".": 0,   # transparent
    "I": 8,   # $67F8 #C6FFCE pale turquoise-silver mirror sheen (SP-5 C8)
    "G": 12,  # $3B3B #DECE73 antique gold bezel / trim
    "K": 13,  # $18C6 #313131 crisp dark outline
    "W": 14,  # $62F8 #C6BDC6 cool silver-lavender rim
    "D": 15,  # $518B #5A63A5 cool indigo-blue mirror face
}

# Exact BGR555 -> RGBA palettes for preview sheets
def _bgr555(w: int) -> tuple[int, int, int, int]:
    return (((w & 31) << 3) | ((w & 31) >> 2),
            (((w >> 5) & 31) << 3) | (((w >> 5) & 31) >> 2),
            (((w >> 10) & 31) << 3) | (((w >> 10) & 31) >> 2),
            255)


L1_RGB = {0: (0, 0, 0, 0), 12: _bgr555(0x379F), 13: _bgr555(0x0865), 14: _bgr555(0x15F9), 15: _bgr555(0x08EF)}
L2_RGB = {0: (0, 0, 0, 0), 12: _bgr555(0x7BDE), 13: _bgr555(0x1CA4), 14: _bgr555(0x6ECE), 15: _bgr555(0x4947)}
L3_RGB = {0: (0, 0, 0, 0), 8: _bgr555(0x67F8), 12: _bgr555(0x3B3B), 13: _bgr555(0x18C6), 14: _bgr555(0x62F8), 15: _bgr555(0x518B)}

# =============================================================================
# LEVEL 1: Compact GBC Oracle Wooden Buckler (9x9 Front/Back, 4x9 Side)
#   Front: x=3..11, y=6..14 (6 transparent top rows -> 100% face-clearing!)
#   Back:  x=4..12, y=6..14
#   Side:  x=6..9,  y=7..15 (unflipped faces Left; H-flipped faces Right)
# =============================================================================

L1_WOODEN_FRONT = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "....KKKKKKK.....",
    "...KYYYYYYYK....",
    "...KYOWYWOYK....",
    "...KYOYYYOYK....",
    "...KYOWYWOYK....",
    "...KYOOYOOYK....",
    "...KYWOOOWYK....",
    "....KYYYYYK.....",
    ".....KKKKK......",
    "................",
]

L1_WOODEN_BACK = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".....KKKKKKK....",
    "....KYYYYYYYK...",
    "....KYOOOOOYK...",
    "....KYWWKWWYK...",
    "....KYWKOKWYK...",
    "....KYWWKWWYK...",
    "....KYWWWWWYK...",
    ".....KYYYYYK....",
    "......KKKKK.....",
    "................",
]

L1_WOODEN_SIDE = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......KK.......",
    "......KYYK......",
    "......KYOK......",
    "......KYYK......",
    "......KYOK......",
    "......KYWK......",
    "......KYWK......",
    "......KYYK......",
    ".......KK.......",
]

# =============================================================================
# LEVEL 2: Compact GBC Oracle Iron / Steel Heater Shield (9x9 Front/Back, 4x9 Side)
#   Front: x=3..11, y=6..14 (6 transparent top rows -> 100% face-clearing!)
#   Back:  x=4..12, y=6..14
#   Side:  x=6..9,  y=7..15
# =============================================================================

L2_IRON_FRONT = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "...KKKKKKKKK....",
    "...KSSSSSSSK....",
    "...KSBBSBBDK....",
    "...KSBSSSBDK....",
    "...KSBBSBBDK....",
    "...KSBBDBDDK....",
    "....KSBBDDK.....",
    ".....KSSDK......",
    "......KKK.......",
    "................",
]

L2_IRON_BACK = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "....KKKKKKKKK...",
    "....KSSSSSSSK...",
    "....KSBBBBBSK...",
    "....KSBDKDBSK...",
    "....KSBKSKBSK...",
    "....KSDDKDDSK...",
    ".....KSDDDSK....",
    "......KSSDK.....",
    ".......KKK......",
    "................",
]

L2_IRON_SIDE = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......KK.......",
    "......KSSK......",
    "......KSBK......",
    "......KSSK......",
    "......KSBK......",
    "......KSDK......",
    "......KSDK......",
    "......KSSK......",
    ".......KK.......",
]

# =============================================================================
# LEVEL 3: Compact & Simple GBC Oracle Mirror Shield (9x9 Front/Back, 4x9 Side)
#   NO bulky top horn-ears, NO cluttered concentric rings!
#   Sleek rounded gold-trimmed kite/heater silhouette with gleaming diagonal
#   silver-white / ice-blue reflective mirror face (Option D C8 pre-baked).
#   Front: x=3..11, y=6..14 (6 transparent top rows -> 100% face-clearing!)
#   Back:  x=4..12, y=6..14
#   Side:  x=6..9,  y=7..15
# =============================================================================

L3_MIRROR_FRONT = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "....KKKKKKK.....",
    "...KGGGWGGGK....",
    "...KGWWWIIGK....",
    "...KGWWIIDGK....",
    "...KGWIIIDGK....",
    "....KGIIDGK.....",
    "....KGGDGGK.....",
    ".....KGGGK......",
    "......KKK.......",
    "................",
]

L3_MIRROR_BACK = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".....KKKKKKK....",
    "....KGGGGGGGK...",
    "....KGDDDDDGK...",
    "....KGDWKWDGK...",
    "....KGDDDDDGK...",
    ".....KGDDDGK....",
    ".....KGGGGGK....",
    "......KGGGK.....",
    ".......KKK......",
    "................",
]

L3_MIRROR_SIDE = [
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    "................",
    ".......KK.......",
    "......KGGK......",
    "......KWGK......",
    "......KWGK......",
    "......KIGK......",
    "......KIGK......",
    "......KDGK......",
    "......KGGK......",
    ".......KK.......",
]

LEVELS: list[tuple[str, list[str], list[str], list[str], dict[str, int], dict[int, tuple[int, int, int, int]]]] = [
    ("L1_GBC_Wooden", L1_WOODEN_FRONT, L1_WOODEN_BACK, L1_WOODEN_SIDE, L1_LEGEND, L1_RGB),
    ("L2_GBC_Iron",   L2_IRON_FRONT,   L2_IRON_BACK,   L2_IRON_SIDE,   L2_LEGEND, L2_RGB),
    ("L3_GBC_Mirror", L3_MIRROR_FRONT, L3_MIRROR_BACK, L3_MIRROR_SIDE, L3_LEGEND, L3_RGB),
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


def encode_shield_level(front: list[list[int]], back: list[list[int]], side: list[list[int]]) -> bytes:
    """Encode 1 shield level (384 B = 12 tiles in GFX_SHIELD $7E9300 row-major order)."""
    # Top row:    Front TL, Front TR, Back TL, Back TR, Side TL, Side TR
    # Bottom row: Front BL, Front BR, Back BL, Back BR, Side BL, Side BR
    top = (
        encode_tile_4bpp(front, 0, 0) + encode_tile_4bpp(front, 8, 0)
        + encode_tile_4bpp(back, 0, 0) + encode_tile_4bpp(back, 8, 0)
        + encode_tile_4bpp(side, 0, 0) + encode_tile_4bpp(side, 8, 0)
    )
    bot = (
        encode_tile_4bpp(front, 0, 8) + encode_tile_4bpp(front, 8, 8)
        + encode_tile_4bpp(back, 0, 8) + encode_tile_4bpp(back, 8, 8)
        + encode_tile_4bpp(side, 0, 8) + encode_tile_4bpp(side, 8, 8)
    )
    blob = top + bot
    assert len(blob) == 384
    return blob


def build_4bpp() -> bytes:
    out = bytearray()
    for name, front_rows, back_rows, side_rows, legend, _pal in LEVELS:
        f_grid = parse_grid(f"{name}_front", front_rows, legend)
        b_grid = parse_grid(f"{name}_back", back_rows, legend)
        s_grid = parse_grid(f"{name}_side", side_rows, legend)
        # Enforce strict face-clearing top margin & zero Sword C9..C11 bleed
        for pose_name, g in (("front", f_grid), ("back", b_grid), ("side", s_grid)):
            used = {v for row in g for v in row}
            bad = used - {0, 8, 12, 13, 14, 15}
            assert not bad, f"{name} {pose_name} leaked forbidden indices: {bad}"
            for r in range(5):
                assert all(v == 0 for v in g[r]), f"{name} {pose_name} row {r} must stay transparent"
        out += encode_shield_level(f_grid, b_grid, s_grid)
    assert len(out) == 3 * 384 == 1152
    return bytes(out)


def render_preview(out_png: Path, scale: int = 8) -> None:
    from PIL import Image, ImageDraw

    cell = 16 * scale
    pad = 16
    label_h = 20
    cols = 4  # Front, Back, Side L, Side R
    rows_n = len(LEVELS)
    w = pad + cols * (cell + pad)
    h = 30 + pad + rows_n * (cell + label_h + pad)
    img = Image.new("RGBA", (w, h), (28, 32, 40, 255))
    draw = ImageDraw.Draw(img)
    draw.text((pad, 8), "Compact Face-Clearing DW GBC Shield Trilogy (8x)", fill=(245, 245, 245, 255))

    def blit(grid: list[list[int]], pal: dict[int, tuple[int, int, int, int]],
             x0: int, y0: int, hflip: bool = False) -> None:
        spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = spr.load()
        for y in range(16):
            for x in range(16):
                sx = 15 - x if hflip else x
                px[x, y] = pal[grid[y][sx]]
        img.alpha_composite(spr.resize((cell, cell), Image.Resampling.NEAREST), (x0, y0))

    for r_idx, (name, f_rows, b_rows, s_rows, legend, pal) in enumerate(LEVELS):
        ry = 30 + pad + r_idx * (cell + label_h + pad)
        f_g = parse_grid(f"{name}_front", f_rows, legend)
        b_g = parse_grid(f"{name}_back", b_rows, legend)
        s_g = parse_grid(f"{name}_side", s_rows, legend)
        views = [
            (f"{name} Front", f_g, False),
            (f"{name} Back",  b_g, False),
            (f"{name} Left",  s_g, False),
            (f"{name} Right", s_g, True),
        ]
        for c_idx, (cap, grid, hf) in enumerate(views):
            cx = pad + c_idx * (cell + pad)
            draw.rectangle((cx, ry, cx + cell - 1, ry + cell - 1), fill=(58, 66, 54, 255), outline=(100, 110, 125, 255))
            blit(grid, pal, cx, ry, hflip=hf)
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
    print(f"Wrote {args.out} ({len(data)} bytes = ${len(data):04X}, 3 levels x 12 tiles)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
