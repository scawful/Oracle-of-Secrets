#!/usr/bin/env python3
"""Generate custom 4BPP Majora's Mask-style overhead Deku Flower-Leaf hover art.

Output:
  Data/graphics/items/deku_flower_wings.4bpp (1,536 bytes = $0600 = 12 x 16x16 frames)

Each 128-byte frame is stored in SNES 16x16 OBJ row-major DMA order:
  +$00..$3F (64 B): Top row    (TL tile 32B + TR tile 32B) -> VRAM $4070
  +$40..$7F (64 B): Bottom row (BL tile 32B + BR tile 32B) -> VRAM $4170

Directional Geometry & Overhead Invariants:
  Frames 0..5 — FRONT / BACK (Up/Down) Overhead Twin Flower-Leaf Propellers:
    Left flower drawn normal, Right flower H-flipped (ORA #$40), held high
    overhead above Deku Link's cap/shoulders (dx = +-12, dy = -11/-10). Each
    Left-side frame curves its slender green stem down-inward into the
    bottom-inner corner (cols 12..15, rows 10..15) while keeping face-clearance
    cols 14..15 empty on rows 0..7 so blossoms never obscure Deku Link's cap
    or face.
  Frames 6..11 — SIDE PROFILE (Left/Right) Single Centered Overhead Flower:
    Because Deku Link holds one flower in each outstretched hand (left & right
    of his body), viewing him from the side aligns both hands/flowers along the
    viewer's sightline into ONE single centered overhead flower right down the
    middle (1 OAM slot at dx = 0, dy = -12; normal on Left, H-flipped on Right).
    All 6 side frames feature a lively, fluttering petal-wave animation with a
    clean centered vertical stem (cols 6..9) tucked down onto his cap crown,
    staying high and clear of his forehead and eyes even on Flap-Down.

Frame map (streamed during NMI by DekuWings_NmiUpload from Bank $38 tail):
  Front/Back (LinkFaceDir = $00 Up / $02 Down, 2 OAM slots):
    0 (+$000): Phase 1 Levitate — Wide horizontal 3-leaf helicopter canopy
    1 (+$080): Phase 1 Levitate — Tilted 45 deg CW rotor spin sweep
    2 (+$100): Phase 1 Levitate — Edge-on high-speed horizontal spin flash
    3 (+$180): Phase 1 Levitate — Tilted 45 deg CCW rotor spin sweep
    4 (+$200): Phase 2 Fall Flap-Up — Scalloped leaves pitched skyward (-2px Y)
    5 (+$280): Phase 2 Fall Flap-Down — Drooping bent leaves + wind streaks (+2px Y, +-1px X)
  Side Profile (LinkFaceDir = $04 Left / $06 Right, 1 centered OAM slot):
    6 (+$300): Phase 1 Side Flutter — Front petal crest lifted, rear tips dipping
    7 (+$380): Phase 1 Side Flutter — Crisp horizontal breeze snap + dancing glint motes
    8 (+$400): Phase 1 Side Flutter — Rear petal crest lifted, front tips dipping
    9 (+$480): Phase 1 Side Flutter — Buoyant triple-scallop open bloom (1px flutter lift)
   10 (+$500): Phase 2 Side Flap-Up — Skyward-folded V-cupped profile (-2px Y)
   11 (+$580): Phase 2 Side Flap-Down — Gull-wing drooping flutter + wind motes (+2px Y, high clearance)

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
    "y": 6,   # $17DF #FFF629 bright sunny yellow-gold (flower-leaf core)
    "c": 7,   # $42DB #DEB483 warm cream-gold transition
    "k": 8,   # $14A5 #292929 crisp ALTTP charcoal outline
    "r": 9,   # $14BC #E62929 vibrant rose-crimson (petal mid-tip accent)
    "d": 10,  # $14B2 #942929 deep rose-magenta shade
    "w": 12,  # $7FFF #FFFFFF pure white specular highlight / spin glint
    "m": 13,  # $7A18 #C583F6 radiant Majora's Mask orchid-pink/magenta tips!
    "e": 14,  # $178C #62E629 sunlit yellow-lime sepal accent
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

# =========================================================================
# FRONT / BACK FRAMES (0..5): Overhead Twin Flower-Leaf Propellers (Up/Down)
# Broad open scalloped flower-leaves + slim flared calyx + slender stem.
# =========================================================================

# Frame 0 (F0): Phase 1 Levitate — Wide Open 3-Leaf Scalloped Majora's Mask Canopy
FRONT_0_WIDE = [
    "..kkk...kkk.....",
    ".kmwwk.kwmmk....",
    "kmwrykkkyrwmkk..",
    "kmryyywwyyyrmk..",
    "kdryycyycyyrdk..",
    ".kkooyyyyookk...",
    "..kllggggllk....",
    "...kkffggfk.....",
    "......kfggk.....",
    ".......kfgk.....",
    "........kfgk....",
    ".........kfgk...",
    "..........kfgk..",
    "..........kfgbk.",
    "...........kfgbk",
    "............kbgk",
]

# Frame 1 (F1): Phase 1 Levitate — Tilted 45 deg CW Helicopter Leaf Spin Sweep
FRONT_1_CW = [
    "......kkkk......",
    ".....kmwwmk.....",
    "....kmwrymmk....",
    "...kmryyyrmk....",
    ".kkwryywwyrk....",
    "kmwryyycyyok....",
    "kmrryyyoookk....",
    "kddoooklgglk....",
    ".kkkk..kfggk....",
    "........kfgk....",
    "........kfgk....",
    ".........kfgk...",
    "..........kfgk..",
    "..........kfgbk.",
    "...........kfgbk",
    "............kbgk",
]

# Frame 2 (F2): Phase 1 Levitate — Edge-On Fast Horizontal Propeller Spin Flash
FRONT_2_EDGE = [
    "................",
    "................",
    "..kkkkkkkkk.....",
    "wkmwyywwywmkmw..",
    ".kmrrywwyrrdk...",
    "m.kdooyyoodk.w..",
    "...kllggllk.....",
    ".....kfggfk.....",
    "......kfggk.....",
    ".......kfgk.....",
    "........kfgk....",
    ".........kfgk...",
    "..........kfgk..",
    "..........kfgbk.",
    "...........kfgbk",
    "............kbgk",
]

# Frame 3 (F3): Phase 1 Levitate — Tilted 45 deg CCW Helicopter Leaf Spin Sweep
FRONT_3_CCW = [
    ".kkkk...........",
    "kmwwmk..........",
    "kmwrymk.........",
    "kmryyykkkk......",
    "kmryywwyymwk....",
    ".kdryyycyrmmk...",
    "..kkooyyyrdk....",
    "....klggoook....",
    ".....kfggkk.....",
    ".......kfgk.....",
    "........kfgk....",
    ".........kfgk...",
    "..........kfgk..",
    "..........kfgbk.",
    "...........kfgbk",
    "............kbgk",
]

# Frame 4 (F4): Phase 2 Fall FLAP-UP (Scalloped leaves folded sharply skyward)
# Paired with -2px OAM Y lift; slender taut stem anchors to cols 12..15, row 15.
FRONT_4_FLAP_UP = [
    ".kkk...kkk......",
    "kmwwk.kwmmk.....",
    "kmwrykkywmk.....",
    "kmryyywwymk.....",
    ".kmryyyyyrmk....",
    "..kdryyyydk.....",
    "...kooyyook.....",
    "....klggglk.....",
    "......kfggk.....",
    ".......kfgk.....",
    "........kfgk....",
    ".........kfgk...",
    "..........kfgk..",
    "..........kfgbk.",
    "...........kfgbk",
    "............kbgk",
]

# Frame 5 (F5): Phase 2 Fall FLAP-DOWN (Drooping bent flower-leaf + wind streaks)
# Paired with +2px OAM Y & +-1px outward spread; calyx sits high so drooping tips stay clear.
FRONT_5_FLAP_DOWN = [
    "..w.....m.......",
    "....w...........",
    ".m..............",
    "......kkkkk.....",
    "....kklggggk....",
    "..kkoyyggfggk...",
    ".koyyyyykffgk...",
    "kmryywwyykkfgk..",
    "kmwryyycyykfgk..",
    "kmwrmryyyk.kfgk.",
    "kmwrmkkyk..kfgbk",
    ".kddk..k....kbgk",
    "..kk........kbgk",
    ".............kkk",
    "................",
    "................",
]

# =========================================================================
# SIDE PROFILE FRAMES (6..11): Single Centered Overhead Fluttering Flower
# Drawn normal on Left facing ($04), H-flipped via ORA #$40 on Right ($06).
# Strictly 1 OAM slot centered right down the middle above Deku Link's head!
# =========================================================================

# Frame 6 (S0): Phase 1 Side Flutter — Front Petal Crest Lifted, Rear Dipping
SIDE_0_FLUTTER_FWD = [
    "................",
    "..kkk...........",
    ".kmwwkk...w.....",
    "kmwryykkkkkk....",
    "kmryyywwyyrmkk..",
    ".kdryycyyyyrrmk.",
    "..kkoollloyydk..",
    "....kelgggllk...",
    ".....kkfggfk....",
    "......kfgfk.....",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kbgk......",
    ".......kk.......",
]

# Frame 7 (S1): Phase 1 Side Flutter — Crisp Horizontal Breeze Snap + Glint Motes
SIDE_1_FLUTTER_FLAT = [
    "................",
    "....w......m....",
    "..m...........w.",
    "..kkkkkkkkkkkk..",
    "wkmwwyywwyywmmkw",
    "mkdrryyccyyrddkm",
    "..kkoelggleokk..",
    ".....klgglk.....",
    ".....kffggk.....",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kbgk......",
    ".......kk.......",
]

# Frame 8 (S2): Phase 1 Side Flutter — Rear Petal Crest Lifted, Front Dipping
SIDE_2_FLUTTER_BACK = [
    "................",
    "...........kkk..",
    ".....w...kkwwmk.",
    "....kkkkkkyyrwmk",
    "..kkmryywwyyyrmk",
    ".kmrryyyycryydk.",
    "..kdyyolllookk..",
    "...kllgggek.....",
    "....kfgffkk.....",
    ".....kfgfk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kbgk......",
    ".......kk.......",
]

# Frame 9 (S3): Phase 1 Side Flutter — Buoyant Triple-Scallop Open Crown (+1px Lift)
SIDE_3_FLUTTER_CROWN = [
    "......kkkk......",
    ".kkk.kmwwmk.kkk.",
    "kmwwkkwrywkkmwwk",
    "kmwryyyyyyyyrwmk",
    ".kdryycyycyyrdk.",
    "..kkooyyyyookk..",
    "...kelgggglek...",
    ".....kffggk.....",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kbgk......",
    ".......kk.......",
]

# Frame 10 (S4): Phase 2 Side FLAP-UP — Skyward V-Cupped Fluttering Profile (-2px Y)
SIDE_4_FLAP_UP = [
    "...kkk....kkk...",
    "..kmwwk..kwwmk..",
    "..kmwrykkrymmk..",
    "..kmryywwyyrmk..",
    "...kmryyyyrmk...",
    "...kdryyyyrdk...",
    "....kkooyokk....",
    ".....klgglk.....",
    ".....kffggk.....",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kfgk......",
    "......kbgk......",
]

# Frame 11 (S5): Phase 2 Side FLAP-DOWN — Gull-Wing Drooping Flutter + Wind Motes (+2px Y)
# Rows 13..15 stay completely transparent so drooping petals & stem never touch cap/eyes!
SIDE_5_FLAP_DOWN = [
    "...w........m...",
    ".m......w.......",
    "..........w.....",
    ".....kkkkkk.....",
    "...kkllggllkk...",
    "..koyyggggyyok..",
    ".koyyykfgkyyyok.",
    "kmrywykfgkywyrmk",
    "kmwrykkfgkkyrwmk",
    "kmwmk.kfgk.kmwmk",
    ".kddk.kfgk.kddk.",
    "..kk..kbgk..kk..",
    ".......kk.......",
    "................",
    "................",
    "................",
]

FRONT_FRAMES: list[tuple[str, list[str]]] = [
    ("front0_wide",      FRONT_0_WIDE),
    ("front1_cw",        FRONT_1_CW),
    ("front2_edge",      FRONT_2_EDGE),
    ("front3_ccw",       FRONT_3_CCW),
    ("front4_flap_up",   FRONT_4_FLAP_UP),
    ("front5_flap_down", FRONT_5_FLAP_DOWN),
]

SIDE_FRAMES: list[tuple[str, list[str]]] = [
    ("side0_flutter_fwd",   SIDE_0_FLUTTER_FWD),
    ("side1_flutter_flat",  SIDE_1_FLUTTER_FLAT),
    ("side2_flutter_back",  SIDE_2_FLUTTER_BACK),
    ("side3_flutter_crown", SIDE_3_FLUTTER_CROWN),
    ("side4_flap_up",       SIDE_4_FLAP_UP),
    ("side5_flap_down",     SIDE_5_FLAP_DOWN),
]

FRAMES: list[tuple[str, list[str]]] = FRONT_FRAMES + SIDE_FRAMES


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
    assert len(out) == 12 * 128 == 0x600, f"Unexpected 4BPP size {len(out)}"
    return bytes(out)


def render_preview(out_png: Path, scale: int = 6) -> None:
    from PIL import Image, ImageDraw

    front_grids = [(name, parse_grid(name, rows)) for name, rows in FRONT_FRAMES]
    side_grids = [(name, parse_grid(name, rows)) for name, rows in SIDE_FRAMES]

    def blit(canvas: Image.Image, grid: list[list[int]], x0: int, y0: int,
             sc: int = scale, hflip: bool = False) -> None:
        spr = Image.new("RGBA", (16, 16), (0, 0, 0, 0))
        px = spr.load()
        for y in range(16):
            for x in range(16):
                sx = 15 - x if hflip else x
                px[x, y] = DEKU_SP7_RGB[grid[y][sx]]
        spr = spr.resize((16 * sc, 16 * sc), Image.Resampling.NEAREST)
        canvas.alpha_composite(spr, (x0, y0))

    cell = 16 * scale
    pad = 16
    w = pad + 6 * (cell + pad)
    h = 34 + 3 * (cell + 34)
    img = Image.new("RGBA", (w, h), (26, 32, 40, 255))
    draw = ImageDraw.Draw(img)
    draw.text(
        (pad, 8),
        "Deku Overhead Flower-Leaves - 12-Frame 4BPP SP-7 Preview (Row 1: Front/Back F0..F5 | Row 2: Side Left S0..S5 | Row 3: Side Right H-Flip S0..S5)",
        fill=(245, 245, 245, 255),
    )

    # Row 1: Front/Back frames 0..5
    ry1 = 34
    for i, (name, grid) in enumerate(front_grids):
        cx = pad + i * (cell + pad)
        bg = (64, 118, 56, 255) if i < 4 else (92, 84, 52, 255)
        draw.rectangle((cx, ry1, cx + cell - 1, ry1 + cell - 1), fill=bg, outline=(105, 118, 130, 255))
        blit(img, grid, cx, ry1, sc=scale, hflip=False)
        draw.text((cx + 2, ry1 + cell + 4), f"F{i}: {name}", fill=(235, 235, 235, 255))

    # Row 2: Side Profile frames 6..11 (S0..S5, single centered Left facing)
    ry2 = ry1 + cell + 34
    for i, (name, grid) in enumerate(side_grids):
        cx = pad + i * (cell + pad)
        bg = (54, 96, 116, 255) if i < 4 else (96, 74, 88, 255)
        draw.rectangle((cx, ry2, cx + cell - 1, ry2 + cell - 1), fill=bg, outline=(105, 118, 130, 255))
        blit(img, grid, cx, ry2, sc=scale, hflip=False)
        draw.text((cx + 2, ry2 + cell + 4), f"S{i}: {name.split('_', 1)[1]}", fill=(235, 235, 235, 255))

    # Row 3: Side Profile Right facing (H-flipped single centered mirror check)
    ry3 = ry2 + cell + 34
    for i, (name, grid) in enumerate(side_grids):
        cx = pad + i * (cell + pad)
        bg = (42, 56, 74, 255) if i < 4 else (74, 52, 68, 255)
        draw.rectangle((cx, ry3, cx + cell - 1, ry3 + cell - 1), fill=bg, outline=(105, 118, 130, 255))
        blit(img, grid, cx, ry3, sc=scale, hflip=True)
        draw.text((cx + 2, ry3 + cell + 4), f"Right Mirror S{i}", fill=(215, 228, 240, 255))

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
    print(f"Wrote {args.out} ({len(data)} bytes = ${len(data):04X}, 12 x 16x16 frames)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
