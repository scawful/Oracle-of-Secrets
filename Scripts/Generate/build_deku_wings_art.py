#!/usr/bin/env python3
"""Generate custom 4BPP Majora's Mask-style hand-held Deku Flower hover wings.

Output:
  Data/graphics/items/deku_flower_wings.4bpp (768 bytes = $0300 = 6 x 16x16 frames)

Each 128-byte frame is stored in SNES 16x16 OBJ row-major DMA order:
  +$00..$3F (64 B): Top row    (TL tile 32B + TR tile 32B) -> VRAM $4070
  +$40..$7F (64 B): Bottom row (BL tile 32B + BR tile 32B) -> VRAM $4170

Geometry & Fist-Grip Invariant (Left wing normal, Right wing H-flipped via ORA #$40):
  Each Left-wing frame curves its green Deku stem diagonally down-right into the
  bottom-inner corner (cols 12..15, rows 11..15) so the gripped stem connects
  directly into Deku Link's hands across all 4 facings with zero detached gap,
  while keeping inner cols 12..15 clear on rows 0..8 so the blossoms never
  obscure Deku Link's face, eyes, or snout.

Frame map (streamed during NMI by DekuWings_NmiUpload in Bank $35):
  Phase 1 — Steady Levitating Glide (FallTimer >= #$50):
    0 (+$000): Full lush wide-open 3-petal helicopter blossom
    1 (+$080): Tilted 45 deg CW diagonal spin sweep
    2 (+$100): Edge-on foreshortened fast spin flash with motion wisps
    3 (+$180): Tilted 45 deg CCW diagonal spin sweep
  Phase 2 — End-of-Hover Frantic Flapping (FallTimer < #$50):
    4 (+$200): Flap-Up high upstroke (blossom pitched sharply upward; paired with -2px OAM lift)
    5 (+$280): Flap-Down low downstroke (blossom swept downward/outward + wind streaks; paired with +2px Y, +-1px X)

Palette invariant:
  Uses ONLY Deku Link's SP-7 palette indices (Masks/deku_mask.asm `deku_palette`,
  indices 0..14, attr $0E/$4E). 100% identical across Light World, Underworld,
  Dark World, and Special Overworld, and automatically Day/Night tinted with
  Deku Link via UpdateDekuPalette -> ColorSubEffect!

Usage:
  python3 Scripts/Generate/build_deku_wings_art.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
OUT_4BPP = ROOT / "Data/graphics/items/deku_flower_wings.4bpp"

# Deku Link SP-7 (`deku_palette`, Masks/deku_mask.asm) 4BPP color indices (0..14)
WINGS_LEGEND = {
    ".": 0,   # transparent
    "f": 1,   # $15C5 #297329 deep forest green (stem / calyx shade)
    "b": 2,   # $150E #734129 warm bark brown (gripped stem butt)
    "g": 3,   # $26C9 #4AB44A emerald green (calyx & stem body)
    "l": 4,   # $17AA #52EE29 bright lime leaf highlight
    "o": 5,   # $21F4 #A47B41 warm golden-ochre (petal under-shade)
    "y": 6,   # $17DF #FFF629 bright sunny yellow-gold (blossom core)
    "c": 7,   # $42DB #DEB483 warm cream-gold transition
    "k": 8,   # $14A5 #292929 crisp ALTTP charcoal outline
    "r": 9,   # $14BC #E62929 vibrant rose-crimson (petal mid-tip accent)
    "d": 10,  # $14B2 #942929 deep rose-magenta shade
    "w": 12,  # $7FFF #FFFFFF pure white specular highlight / spin glint
    "m": 13,  # $7A18 #C583F6 radiant Majora's Mask orchid-pink/magenta tips!
}

# Exact RGB colors from Masks/deku_mask.asm `deku_palette` for accurate preview rendering
DEKU_SP7_RGB = {
    0:  (0, 0, 0, 0),
    1:  (41, 115, 41, 255),
    2:  (115, 65, 41, 255),
    3:  (74, 180, 74, 255),
    4:  (82, 238, 41, 255),
    5:  (164, 123, 65, 255),
    6:  (255, 246, 41, 255),
    7:  (222, 180, 131, 255),
    8:  (41, 41, 41, 255),
    9:  (230, 41, 41, 255),
    10: (148, 41, 41, 255),
    11: (41, 41, 41, 255),
    12: (255, 255, 255, 255),
    13: (197, 131, 246, 255),
    14: (98, 230, 41, 255),
}

# Frame 0: Phase 1 Levitate — Full Lush Wide-Open 3-Petal Majora's Mask Flower Blossom
WING_0_WIDE = [
    "................",
    "...kkk..kkk.....",
    ".kkmmwkkwmmkk...",
    "kmwwrryyyrwwmk..",
    "kmrryywwyyrrmk..",
    "kdrryyyyyyyrdk..",
    ".kdryyccyyyrdk..",
    "..kkooyyyoook...",
    "....kklggglk....",
    "......kfggglk...",
    ".......kfgglk...",
    "........kfgflk..",
    ".........kfgfk..",
    "..........kfgbk.",
    "...........kbgk.",
    "............kkk.",
]

# Frame 1: Phase 1 Levitate — Tilted 45 deg CW Lush Spinning Blossom
WING_1_CW = [
    "......kkkk......",
    ".....kmwwmk.....",
    "....kmwwrmmk....",
    "....kmryyrmk....",
    "..kkryywwyrk....",
    ".kmmryyyyyok....",
    "kmwryycyook.....",
    "kmrryooklggk....",
    "kddookkfgglk....",
    ".kkk...kfgglk...",
    "........kfgflk..",
    ".........kfgfk..",
    "..........kfgfk.",
    "..........kfgbk.",
    "...........kbgk.",
    "............kkk.",
]

# Frame 2: Phase 1 Levitate — Edge-On Fast Propeller Flash + Horizontal Spin Wisps
WING_2_EDGE = [
    "....kkkk........",
    "...kmmwmk.......",
    "..kmwwrmmk......",
    "wm.kmwyyrmk.mw..",
    "..kmrywwyrk.....",
    "mw.kdyyyydk.wm..",
    "...kdoyyodk.....",
    "....kkoook......",
    ".....klgglk.....",
    "......kfgglk....",
    ".......kfgglk...",
    "........kfgflk..",
    ".........kfgfk..",
    "..........kfgbk.",
    "...........kbgk.",
    "............kkk.",
]

# Frame 3: Phase 1 Levitate — Tilted 45 deg CCW Lush Spinning Blossom
WING_3_CCW = [
    ".kkkk...........",
    "kmwwmk..........",
    "kmmrwmk.........",
    "kmryyykkk.......",
    "kmryywwyykk.....",
    ".kdryyyyyrmk....",
    "..kooyyyyrmmk...",
    "....kggloyrdk...",
    ".....kfggkook...",
    "......kfgglk....",
    ".......kfgglk...",
    "........kfgflk..",
    ".........kfgfk..",
    "..........kfgbk.",
    "...........kbgk.",
    "............kkk.",
]

# Frame 4: Phase 2 End-of-Hover FLAP-UP (High Upstroke — scalloped blossom pitched sharply UP)
# Paired with -2px OAM Y lift; stem extends cleanly to cols 13..15, row 15 to keep grip in hand.
WING_4_FLAP_UP = [
    "..kkk..kkk......",
    ".kmwwkkwmmk.....",
    "kmwwrryyrwmk....",
    "kmrryywwyrmk....",
    ".kmrryyyyrdk....",
    "..kdryyyyydk....",
    "...kdryyyodk....",
    "....kkooyook....",
    "......kklgglk...",
    "........kfgglk..",
    ".........kfgfk..",
    "..........kfgfk.",
    "..........kfgfk.",
    "...........kfgbk",
    "...........kfgbk",
    "............kbgk",
]

# Frame 5: Phase 2 End-of-Hover FLAP-DOWN (Low Downstroke — drooping blossom + air-rush streaks)
# Paired with +2px OAM Y & +-1px X spread; flexed stem anchors at cols 12..15, rows 10..13.
WING_5_FLAP_DOWN = [
    "................",
    "...w.....m......",
    ".m...w..........",
    "................",
    "......kkkk......",
    "....kkggggkk....",
    "..kkoolllgggk...",
    ".koorryyygglgk..",
    "kmrryywwyykgggk.",
    "kmwwrryyyyk.kfgk",
    "kmwwrmkyyk..kfgk",
    "kmmrmk.kk...kbgk",
    ".kddk.......kbgk",
    "..kk.........kkk",
    "................",
    "................",
]

FRAMES: list[tuple[str, list[str]]] = [
    ("frame0_wide",      WING_0_WIDE),
    ("frame1_cw",        WING_1_CW),
    ("frame2_edge",      WING_2_EDGE),
    ("frame3_ccw",       WING_3_CCW),
    ("frame4_flap_up",   WING_4_FLAP_UP),
    ("frame5_flap_down", WING_5_FLAP_DOWN),
]


def parse_grid(name: str, rows: list[str]) -> list[list[int]]:
    if len(rows) != 16:
        raise ValueError(f"{name}: expected 16 rows, got {len(rows)}")
    out: list[list[int]] = []
    for r, line in enumerate(rows):
        if len(line) != 16:
            raise ValueError(f"{name} row {r}: expected 16 cols, got {len(line)}")
        vals = []
        for c, ch in enumerate(line):
            if ch not in WINGS_LEGEND:
                raise ValueError(f"{name} ({r},{c}): unexpected char {ch!r}")
            idx = WINGS_LEGEND[ch]
            assert 0 <= idx <= 14, f"{name}: index {idx} exceeds deku_palette bounds (0..14)"
            vals.append(idx)
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
    for name, rows in FRAMES:
        grid = parse_grid(name, rows)
        out += encode_block_16x16(grid)
    assert len(out) == 6 * 128 == 0x300, f"Unexpected 4BPP size {len(out)}"
    return bytes(out)


def render_preview(out_png: Path, scale: int = 6) -> None:
    from PIL import Image, ImageDraw

    grids = [(name, parse_grid(name, rows)) for name, rows in FRAMES]

    def blit(canvas: Image.Image, grid: list[list[int]], x0: int, y0: int, hflip: bool = False) -> None:
        spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = spr.load()
        for y in range(16):
            for x in range(16):
                sx = 15 - x if hflip else x
                px[x, y] = DEKU_SP7_RGB[grid[y][sx]]
        spr = spr.resize((16 * scale, 16 * scale), Image.Resampling.NEAREST)
        canvas.alpha_composite(spr, (x0, y0))

    cell = 16 * scale
    pad = 16
    w = pad + len(grids) * (cell + pad)
    h = 30 + cell + 34 + cell + 34
    img = Image.new("RGBA", (w, h), (30, 36, 44, 255))
    draw = ImageDraw.Draw(img)
    draw.text((pad, 6), "Deku Flower Hover Wings - 6-Frame 4BPP SP-7 Preview (F0..F3 Levitate Spin, F4..F5 Flap)", fill=(245, 245, 245, 255))

    ry1 = 30
    for i, (name, grid) in enumerate(grids):
        cx = pad + i * (cell + pad)
        bg = (68, 122, 58, 255) if i < 4 else (92, 86, 54, 255)
        draw.rectangle((cx, ry1, cx + cell - 1, ry1 + cell - 1), fill=bg, outline=(105, 118, 130, 255))
        blit(img, grid, cx, ry1, hflip=False)
        draw.text((cx + 2, ry1 + cell + 4), f"F{i}: {name}", fill=(235, 235, 235, 255))

    ry2 = ry1 + cell + 34
    pair_sc = max(2, scale // 2)
    for i, (name, grid) in enumerate(grids):
        cx = pad + i * (cell + pad)
        draw.rectangle((cx, ry2, cx + cell - 1, ry2 + cell - 1), fill=(42, 52, 68, 255), outline=(105, 118, 130, 255))
        for hf, ox in ((False, cx + 2), (True, cx + cell - 16 * pair_sc - 2)):
            spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
            px = spr.load()
            for y in range(16):
                for x in range(16):
                    sx = 15 - x if hf else x
                    px[x, y] = DEKU_SP7_RGB[grid[y][sx]]
            spr = spr.resize((16 * pair_sc, 16 * pair_sc), Image.Resampling.NEAREST)
            img.alpha_composite(spr, (ox, ry2 + (cell - 16 * pair_sc) // 2))
        draw.text((cx + 2, ry2 + cell + 4), f"Paired F{i} (L+R)", fill=(215, 228, 240, 255))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    print(f"Wrote preview: {out_png} ({w}x{h})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_4BPP, help="Output 4BPP path")
    ap.add_argument("--check", action="store_true", help="Verify output matches freshly built bytes")
    ap.add_argument("--preview", type=Path, help="Write zoomed RGBA preview sheet PNG")
    ap.add_argument("--scale", type=int, default=6, help="Preview integer pixel scale (default 6)")
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
    print(f"Wrote {args.out} ({len(data)} bytes = ${len(data):04X}, 6 x 16x16 frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
