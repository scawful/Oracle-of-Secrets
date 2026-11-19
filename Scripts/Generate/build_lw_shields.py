#!/usr/bin/env python3
"""Generate clean, sword-independent Light World Shield 4BPP tiles.

Output:
  Data/graphics/items/vanilla_shields_lw.4bpp (1,152 bytes = 3 levels x 12 tiles x 32 B)

Layout per 384-byte shield level (copied directly to GFX_SHIELD $7E9300..$7E947F
by ShieldWorld_SyncTiles in Items/mirror_shield_palette.asm when SavedWorld != $40):
  Top row    (+$000..$0BF, 6 tiles): Front TL, Front TR, Back TL, Back TR, Side TL, Side TR
  Bottom row (+$0C0..$17F, 6 tiles): Front BL, Front BR, Back BL, Back BR, Side BL, Side BR

Zero-Sword-Bleed Palette Invariants (STRICTLY {0, 8, 12, 13, 14, 15}; ZERO C9..C11!):
  Because OAM SP-5 C9..C11 ($7EC6B2..$7EC6B7) are owned by Link's equipped Sword
  ($1BD630..$1BD646), ANY pixel in indices 9/10/11 shifts color when equipping
  Fighter / Master / Tempered / Golden Swords. All 3 Light World shields therefore
  use ONLY sword-independent SP-5 slots:
  - L1 LW Round Blue Fighter Shield: {0, 12, 13, 14, 15} (exact base OoS art)
      $1BD648: C12=$7FFF white, C13=$1CE7 outline, C14=$7A10 sky blue, C15=$64A5 blue
  - L2 LW Custom Hylian Shield:      {0, 8, 12, 13, 14, 15} (5-color Option D C8!)
      SP-5 C8 = $275E (#F7D64A Hylian Triforce Gold, via !HylianShield_Color8)
      $1BD650: C12=$6947 (#3952D6 royal blue), C13=$1CE7 (#393939 outline),
               C14=$047B (#DE1808 Loftwing crimson), C15=$6739 (#CECECE silver)
  - L3 LW Custom Mirror Shield:      {0, 8, 12, 13, 14, 15} (5-color Option D C8!)
      SP-5 C8 = $7B13 (#98C0F0 cool mirror steel, via !MirrorShield_Color8)
      $1BD658: C12=$373C gold rim, C13=$18A5 outline, C14=$7FFE sheen, C15=$5589 steel

Usage:
  python3 Scripts/Generate/build_lw_shields.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_4BPP = ROOT / "Data/graphics/items/vanilla_shields_lw.4bpp"

# L1 Round Blue Fighter Shield pixel legend -> 4BPP indices (SP-5 C12..C15)
L1_LEGEND = {
    ".": 0,   # transparent
    "W": 12,  # $7FFF #FFFFFF bright rim/highlight
    "K": 13,  # $1CE7 #393939 dark outline
    "L": 14,  # $7A10 #8484F7 light blue
    "B": 15,  # $64A5 #2929CE deep royal blue
}

# L2 Custom Hylian Shield pixel legend -> 4BPP indices (SP-5 C8 + C12..C15; ZERO C9..C11!)
L2_LEGEND = {
    ".": 0,   # transparent
    "G": 8,   # $275E #F7D64A Hylian Triforce & crest gold (SP-5 C8)
    "B": 12,  # $6947 #3952D6 rich Hylian royal blue field
    "K": 13,  # $1CE7 #393939 crisp ALTTP charcoal outline
    "R": 14,  # $047B #DE1808 vibrant Crimson Loftwing crest
    "S": 15,  # $6739 #CECECE gleaming metallic silver frame
}

# L3 Custom Mirror Shield pixel legend -> 4BPP indices (Option D C8 + SP-5 C12..C15)
L3_LEGEND = {
    ".": 0,   # transparent
    "I": 8,   # $7B13 #98C0F0 cool mirror steel highlight (Option D C8)
    "G": 12,  # $373C #E0C868 gold bezel/crest
    "K": 13,  # $18A5 #282830 dark outline
    "W": 14,  # $7FFE #F0F8F8 white specular sheen
    "D": 15,  # $5589 #4860A8 deep blue-steel shadow
}


def _bgr555(w: int) -> tuple[int, int, int, int]:
    return (
        ((w & 31) << 3) | ((w & 31) >> 2),
        (((w >> 5) & 31) << 3) | (((w >> 5) & 31) >> 2),
        (((w >> 10) & 31) << 3) | (((w >> 10) & 31) >> 2),
        255,
    )


L1_RGB = {
    0: (0, 0, 0, 0),
    12: _bgr555(0x7FFF),
    13: _bgr555(0x1CE7),
    14: _bgr555(0x7A10),
    15: _bgr555(0x64A5),
}
L2_RGB = {
    0: (0, 0, 0, 0),
    8: _bgr555(0x275E),
    12: _bgr555(0x6947),
    13: _bgr555(0x1CE7),
    14: _bgr555(0x047B),
    15: _bgr555(0x6739),
}
L3_RGB = {
    0: (0, 0, 0, 0),
    8: _bgr555(0x7B13),
    12: _bgr555(0x373C),
    13: _bgr555(0x18A5),
    14: _bgr555(0x7FFE),
    15: _bgr555(0x5589),
}

# =============================================================================
# LEVEL 1: Light World Custom Round Blue Fighter Shield (exact OoS base art)
# =============================================================================

L1_FIGHTER_FRONT = [
    "................",
    "................",
    "................",
    "................",
    ".....KKKKKK.....",
    "....KWWWWWWK....",
    "...KWBBBBBBWK...",
    "...KWBBLLBBWK...",
    "...KWBLBBLBWK...",
    "...KWBWBBWBWK...",
    "...KWLBLLBLWK...",
    "....KWLBBLWK....",
    ".....KWWWWK.....",
    "......KKKK......",
    "................",
    "................",
]

L1_FIGHTER_BACK = [
    "................",
    "................",
    "................",
    "................",
    ".....KKKKKK.....",
    "....KLKLKLKK....",
    "...KLKLKLKLKK...",
    "...KKLKLKLKLK...",
    "...KLKLKLKLKK...",
    "...KKLKLKLKLK...",
    "...KLKLKLKLKK...",
    "....KLKLKLKK....",
    ".....KLKLKK.....",
    "......KKKK......",
    "................",
    "................",
]

L1_FIGHTER_SIDE = [
    "................",
    "................",
    "................",
    "................",
    "......K.........",
    ".....KWK........",
    ".....KWBB.......",
    ".....KWBL.......",
    ".....KWLW.......",
    ".....KWLW.......",
    ".....KWBL.......",
    ".....KWBB.......",
    ".....KWK........",
    "......K.........",
    "................",
    "................",
]

# =============================================================================
# LEVEL 2: Light World Custom Hylian Shield (5-Color Option D C8; ZERO C9..C11!)
#   Exact 12x14 OoS Hylian Shield outer silhouette, rebuilt strictly in
#   {0, 8(Gold), 12(Royal Blue), 13(Outline), 14(Crimson), 15(Silver)} so it
#   renders 100% identically across Fighter, Master, Tempered, and Golden Swords!
# =============================================================================

L2_HYLIAN_FRONT = [
    "................",
    "...KKKKKKKKKK...",
    "..KSSSSSSSSSSK..",
    "..KSSBBBBBBSSK..",
    "..KSBBBGGBBBSK..",
    "..KSBGGBBGGBSK..",
    "..KSBBBBBBBBSK..",
    "..KSSRBRRBRSSK..",
    "..KSBRRRRRRBSK..",
    "..KSBBBRRBBBSK..",
    "..KSSBBBBBBSSK..",
    "..KSGBBGGBBGSK..",
    "...KSSGGGGSSK...",
    "....KKSSSSKK....",
    "......KKKK......",
    "................",
]

L2_HYLIAN_BACK = [
    "................",
    "...KKKKKKKKKK...",
    "..KKSSSSSSSSKK..",
    "..KSSKKKKKKSSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "..KSKKKKKKKKSK..",
    "...KSSKKKKSSK...",
    "....KKSSSSKK....",
    "......KKKK......",
    "................",
]

L2_HYLIAN_SIDE = [
    "................",
    ".......K........",
    "......KSK.......",
    "......KSSK......",
    "......KSBK......",
    "......KSGK......",
    "......KSBK......",
    "......KSRK......",
    "......KSRK......",
    "......KSBK......",
    "......KSBK......",
    "......KSGK......",
    "......KSBK......",
    "......KSK.......",
    ".......K........",
    "................",
]

# =============================================================================
# LEVEL 3: Light World Custom Mirror Shield (exact OoS base art, Option D C8)
# =============================================================================

L3_MIRROR_FRONT = [
    "................",
    ".......KK.......",
    ".KK...KDDK...KK.",
    ".KDKKKDIIDKKKDK.",
    ".KDDDDWIIWDDDDK.",
    "..KDWIDWWDIWDK..",
    "..KDWDIDDIDWDK..",
    "..KDWDIIIIDWDK..",
    "..KDWDIGGIDWDK..",
    "..KDWDGGGGDWDK..",
    "..KDWDIIIIDWDK..",
    "..KDIWDIIDWIDK..",
    "..KDDIWDDWIDDK..",
    "...KDDIWWIDDK...",
    "....KKDDDDKK....",
    "......KKKK......",
]

L3_MIRROR_BACK = [
    "................",
    ".......KK.......",
    ".KK...KWWK...KK.",
    ".KWKKKWKKWKKKWK.",
    ".KWWWWKGGKWWWWK.",
    "..KWKKGGGGKKWK..",
    "..KWKGGGGGGKWK..",
    "..KWKGGGGGGKWK..",
    "..KWKGGGGGGKWK..",
    "..KWKGGGGGGKWK..",
    "..KWKGGGGGGKWK..",
    "..KWKGGGGGGKWK..",
    "..KWWKGGGGKWWK..",
    "...KWWKKKKWWK...",
    "....KKWWWWKK....",
    "......KKKK......",
]

L3_MIRROR_SIDE = [
    "................",
    "................",
    "......KK........",
    "......KWK.......",
    "......KWK.......",
    "......KGDK......",
    "......KGDK......",
    "......KGDK......",
    "......KGWK......",
    "......KGWK......",
    "......KGDK......",
    "......KGDK......",
    "......KGDK......",
    "......KWK.......",
    "......KWK.......",
    "......KK........",
]

LEVELS: list[tuple[str, list[str], list[str], list[str], dict[str, int], dict[int, tuple[int, int, int, int]], set[int]]] = [
    ("L1_LW_Fighter", L1_FIGHTER_FRONT, L1_FIGHTER_BACK, L1_FIGHTER_SIDE, L1_LEGEND, L1_RGB, {0, 12, 13, 14, 15}),
    ("L2_LW_Hylian",  L2_HYLIAN_FRONT,  L2_HYLIAN_BACK,  L2_HYLIAN_SIDE,  L2_LEGEND, L2_RGB, {0, 8, 12, 13, 14, 15}),
    ("L3_LW_Mirror",  L3_MIRROR_FRONT,  L3_MIRROR_BACK,  L3_MIRROR_SIDE,  L3_LEGEND, L3_RGB, {0, 8, 12, 13, 14, 15}),
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
    for name, front_rows, back_rows, side_rows, legend, _pal, allowed in LEVELS:
        f_grid = parse_grid(f"{name}_front", front_rows, legend)
        b_grid = parse_grid(f"{name}_back", back_rows, legend)
        s_grid = parse_grid(f"{name}_side", side_rows, legend)
        level_used: set[int] = set()
        for pose_name, g in (("front", f_grid), ("back", b_grid), ("side", s_grid)):
            used = {v for row in g for v in row}
            sword_leak = used & {9, 10, 11}
            assert not sword_leak, f"{name} {pose_name} leaked Sword C9..C11 indices: {sword_leak}"
            bad = used - allowed
            assert not bad, f"{name} {pose_name} used forbidden indices: {bad} (allowed {allowed})"
            level_used |= used
        assert level_used == allowed, f"{name} expected full palette {allowed}, got {level_used}"
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
    draw.text((pad, 8), "Sword-Independent Light World Shield Trilogy (8x)", fill=(245, 245, 245, 255))

    def blit(grid: list[list[int]], pal: dict[int, tuple[int, int, int, int]],
             x0: int, y0: int, hflip: bool = False) -> None:
        spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = spr.load()
        for y in range(16):
            for x in range(16):
                sx = 15 - x if hflip else x
                px[x, y] = pal[grid[y][sx]]
        img.alpha_composite(spr.resize((cell, cell), Image.Resampling.NEAREST), (x0, y0))

    for r_idx, (name, f_rows, b_rows, s_rows, legend, pal, _allowed) in enumerate(LEVELS):
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
            draw.rectangle((cx, ry, cx + cell - 1, ry + cell - 1), fill=(72, 128, 64, 255), outline=(100, 110, 125, 255))
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
