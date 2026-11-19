#!/usr/bin/env python3
"""Generate cleaned Sheet 0x33 (global 0xA6, Deku Scrub NPCs) -> Data/graphics/spr33.txt.

Builds on the authentic base ROM Sheet 0x33 pixel art:
  - Cleans outline consistency across F0/F1 (Cursed Deku Scrub), F2 (Withered Deku),
    F3 (Deku Butler), and F4 (Deku Princess) using the exact Deku SP-5 palette
    (AuxPal 3: 1=#FFF white, 2=#F6DE41 gold, 3=#AC5A20 bark, 4=#F6A46A tan,
     5=#292929 charcoal outline, 6=#8BDE31 lime leaf, 7=#009C39 emerald leaf).
  - Populates blank tiles $09/$0A/$19/$1A (16x16 $09) with Deku Butler Frame 1
    head (dignified eye blink + relaxed leafy hat-ears, H-mirrored at dx=-4/+4, dy=-11).
  - Populates blank tiles $29/$2A/$39/$3A (16x16 $29) with Deku Princess Frame 1
    face & dress (warm royal eye blink + gentle dress ruffle, H-mirrored at dx=-4/+4, dy=+4).
  - Preserves blank column $B ($0B/$1B/$2B/$3B) completely free.

Usage:
  python3 Scripts/Generate/build_deku_npcs_sheet.py [--check] [--preview OUT.png]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts/Generate"))
import sheet_codec  # noqa: E402

OUT_TXT = ROOT / "Data/graphics/spr33.txt"

# Palette AuxPal 3 (SP-5 in Tail Pond $2D, Tail Swamp $2E, Tail Palace $2F & Rooms $E6/$E7)
DEKU_SP5_RGB = {
    0: (0, 0, 0, 0),
    1: (255, 255, 255, 255),  # white (eyes, highlight, lace)
    2: (246, 222, 65, 255),   # royal gold-yellow
    3: (172, 90, 32, 255),    # rich wood-bark brown
    4: (246, 164, 106, 255),  # warm light bark / face tan
    5: (41, 41, 41, 255),     # crisp ALTTP charcoal outline
    6: (139, 222, 49, 255),   # bright lime leaf green
    7: (0, 156, 57, 255),     # deep emerald leaf green
}

# =============================================================================
# Region 1: F2 Withered Deku Scrub (cols 0..3 -> 32x32)
# Cleaned dark #292929 outlines on bare brown/green bark edges; iconic silhouette preserved.
# =============================================================================
F2_WITHERED = [
    "................55..............",
    "...............5775.............",
    "...............57675............",
    "...............57675............",
    ".............557557555..........",
    "............57775576675.........",
    "............55555355555.........",
    ".....5555.......545.............",
    "....5765...55555445.............",
    ".555555...534332435.............",
    ".557745..53444222345............",
    "..55545..534242224245...........",
    "...554355344242222245...........",
    "....534333444422242445......55..",
    ".....534434444224444445....5775.",
    "......53334443444444445....5775.",
    ".......5354455444354345...55755.",
    "........554555444455545..53445..",
    ".........54444444445545.53455...",
    ".........534333443443455345.....",
    "..........5333224344335445......",
    "..........5352552434335555......",
    "...........554555253335.5775....",
    "...........53545545335..5555....",
    "............535445335...........",
    "............533553335...........",
    "............5533333535..........",
    "...........5333555533455........",
    "..........54435....553445.......",
    "..........5555.......5555.......",
    "................................",
    "................................",
]

# =============================================================================
# Region 2: F3 Deku Butler Frame 0 (cols 4..6 -> 24x32)
# Cleaned top-hat silhouette with subtle trim band, crisp dark outlines on
# right torso/leaf edges, clean symmetrical head & grounded feet.
# =============================================================================
F3_BUTLER = [
    "........................",
    "........................",
    ".........555555.........",
    "...5555.55333355.5555...",
    "..57667555555555576675..",
    ".5776666755555576666775.",
    ".5776767555555557676775.",
    ".5777775555225555777775.",
    ".5777775555555555777775.",
    "..57775533333333557775..",
    "...555532223322235555...",
    "....5663314444133665....",
    "...567663331133366765...",
    "..56675555155155557665..",
    "..56657775455457775665..",
    "...566775354453577665...",
    "...55775443553445775....",
    "...53554444444444555....",
    "..5334444661166433445...",
    "..5353446651555334445...",
    "..5335344335444444435...",
    "...55533344544444435....",
    "......5333335573335.....",
    "......5333333774635.....",
    ".......533333744635.....",
    ".......53335534335......",
    "........53355335........",
    "........53355335........",
    "........53355335........",
    "........54355345........",
    ".......5445..5445.......",
    "........55....55........",
]

# =============================================================================
# Region 3: F4 Deku Princess Frame 0 (cols 7..8 -> 16x32, H-mirrored at dx=-4/+4)
# Symmetry axis is between x_local=11 and x_local=12 (cols 8..15 mirrored).
# Cleaned outer dark outlines on crown flanks (rows 8-11) & dress hem (rows 28-31).
# =============================================================================
F4_PRINCESS = [
    "................",
    "................",
    "................",
    "..........5555..",
    ".........557755.",
    "........55577555",
    ".......567666676",
    ".......575666657",
    ".......535766753",
    "......5312577521",
    "......5323311332",
    ".......531322313",
    ".......566122166",
    "......5667566576",
    ".......555566555",
    ".......533355333",
    "......5333333333",
    "......5341133114",
    ".....53441144114",
    ".....53433444433",
    ".....53322244222",
    ".....53312344321",
    "....515443411434",
    "....522535155153",
    ".....55555544555",
    "......5577555577",
    "....557573377337",
    "...5757737377373",
    "..53175737711117",
    "..53111557141141",
    "...5555.51511515",
    ".........5555555",
]

# =============================================================================
# Region 4: NEW IDLE FRAME 1 TILES in FREE cols 9..A (16x32) + blank col B (8x32)
#
# Top half ($09, $0A, $19, $1A -> 16x16 tile $09):
#   Deku Butler Frame 1 Head (symmetrical 24x16 H-mirrored at dx=-4 ($3B) & dx=+4 ($7B)):
#   x_local=0..11 is left half (screen x=-4..+7); x_local=12..15 is transparent (0)
#   for zero-overdraw H-mirror symmetry!
#   Visual animation vs F3:
#     - Dignified blinked/half-lidded eyes (row 11 white eye -> closed charcoal lid + warm brow)
#     - Gently relaxed/drooped twin leafy hat-ears (+1px soft sway)
#     - Drawn at dy=-11 (1px breathing dip) over grounded F3 body ($24/$25 at dy=+4)!
#
# Bottom half ($29, $2A, $39, $3A -> 16x16 tile $29):
#   Deku Princess Frame 1 Face & Dress (symmetrical 24x16 H-mirrored at dx=-4/+4):
#   Matches F4's exact x_local=0..11 left half (x_local=12..15 transparent = zero overdraw!).
#   Visual animation vs F4:
#     - Warm happy closed-arc royal eye blink (rows 17-18 white eyes -> graceful curved lashes
#       & warm cheek glow!)
#     - Subtle 1px royal dress ruffle lift on inner white apron/skirt while feet stay planted
#     - Paired with existing crown ($07) dipped +1px (dy=-11) for a charming royal nod+blink!
# =============================================================================
F5_BUTLER_IDLE1_HEAD = [
    "................",
    "................",
    ".........555....",
    "........5533....",
    "...5555.5555....",
    "..5766755555....",
    ".57766667555....",
    ".57767675552....",
    ".57777755555....",
    "..5777553333....",
    "...555532223....",
    "....56635544....",
    "...567663331....",
    "..5667555515....",
    "..5665777545....",
    "...566775354....",
]

F6_PRINCESS_IDLE1_BODY = [
    "......533333....",
    "......534443....",
    ".....5344554....",
    ".....5343344....",
    ".....5332224....",
    ".....5331234....",
    "....51544341....",
    "....52253515....",
    ".....5555554....",
    "......557755....",
    "....55757337....",
    "...575773737....",
    "..5317573771....",
    "..5311155711....",
    "...5555.5151....",
    ".........555....",
]

FREE_COL_B = ["........"] * 32

# =============================================================================
# Region 5: F1 Cursed Scrub Frame 1 (cols C..D -> 16x32)
# Crisp continuous outlines (closes stray 1px gaps at row 9/17 while keeping authentic art).
# =============================================================================
F1_CURSED1 = [
    "...........55...",
    "....55....5665..",
    "...56655.576665.",
    "..56776655776755",
    "..57577665755756",
    "..55557767555556",
    "..56675575555557",
    ".566667552555525",
    "5657777752255222",
    ".555775524522542",
    "....555245422254",
    ".....53555442255",
    "....534333544533",
    "..55534445455454",
    ".566534411544511",
    "5667753411155111",
    "5225522277777565",
    "245225425577555.",
    "454222542555....",
    "55442255535.....",
    "335445333435....",
    "45455454443555..",
    "115445114435665.",
    "1115511143577665",
    "4114411435555765",
    "3355553356665575",
    "557777557766655.",
    "57766775577765..",
    ".576675..577765.",
    ".566665...55575.",
    "..5665.......5..",
    "...55...........",
]

# =============================================================================
# Region 6: F0 Cursed Scrub Frame 0 (cols E..F -> 16x32)
# Crisp continuous upper leaf outline (row 3) while keeping authentic art intact.
# =============================================================================
F0_CURSED0 = [
    "................",
    "................",
    "................",
    ".......555555555",
    "......5775777757",
    ".....57766577566",
    ".....57555566555",
    ".....55775555557",
    "....557776655667",
    "....577765577556",
    "....577654555545",
    ".....57524522542",
    ".....55245422254",
    "..55533555442255",
    ".565334333544533",
    "5675334444455444",
    "766556677755....",
    "655775567775....",
    "545555456775....",
    "24522542575.....",
    "45422254255.....",
    "55442255533555..",
    "335445333433565.",
    "4445544444335765",
    "5544445544335765",
    "1155551143335775",
    "4114411433356575",
    "335555333356665.",
    "556666555577765.",
    "57766775..57775.",
    ".557755....575..",
    "...55.......5...",
]


def build_grid() -> list[list[int]]:
    idle_cols = F5_BUTLER_IDLE1_HEAD + F6_PRINCESS_IDLE1_BODY
    rows_str: list[str] = []
    for y in range(32):
        line = (
            F2_WITHERED[y]
            + F3_BUTLER[y]
            + F4_PRINCESS[y]
            + idle_cols[y]
            + FREE_COL_B[y]
            + F1_CURSED1[y]
            + F0_CURSED0[y]
        )
        assert len(line) == 128, f"Row {y} width {len(line)} != 128"
        rows_str.append(line)
    grid = [[0 if ch == "." else int(ch) for ch in line] for line in rows_str]
    # Verify col $B ($0B/$1B/$2B/$3B, x=88..95) remains 100% blank
    for y in range(32):
        for x in range(88, 96):
            assert grid[y][x] == 0, f"Col B pixel ({x},{y}) not blank!"
    # Verify exact 1536-byte 3BPP round-trip
    raw = sheet_codec.grid_to_sheet(grid)
    assert len(raw) == 0x600
    assert sheet_codec.sheet_to_grid(raw) == grid
    return grid


def render_preview(grid: list[list[int]], out_png: Path, scale: int = 6) -> None:
    from PIL import Image, ImageDraw

    def draw_16x16(canvas: Image.Image, sx: int, sy: int, ch: int, hflip: bool, sc: int) -> None:
        tr, tc = (ch >> 4) & 3, ch & 15
        d = ImageDraw.Draw(canvas)
        for dy in range(16):
            for dx in range(16):
                gx = tc * 8 + (15 - dx if hflip else dx)
                gy = tr * 8 + dy
                if 0 <= gx < 128 and 0 <= gy < 32:
                    v = grid[gy][gx]
                    if v:
                        px, py = sx + dx * sc, sy + dy * sc
                        d.rectangle((px, py, px + sc - 1, py + sc - 1), fill=DEKU_SP5_RGB[v])

    w = 128 * scale + 24
    h = 32 * scale + 290
    img = Image.new("RGBA", (w, h), (28, 32, 40, 255))
    d = ImageDraw.Draw(img)
    d.text((10, 4), "Cleaned Sheet 0x33 (gid 0xA6) + Butler/Princess 2-Frame Idle Animations (SP-5 AuxPal 3)", fill=(240, 240, 240, 255))

    ox, oy = 12, 24
    for y in range(32):
        for x in range(128):
            v = grid[y][x]
            if v:
                d.rectangle((ox + x * scale, oy + y * scale, ox + (x + 1) * scale - 1, oy + (y + 1) * scale - 1), fill=DEKU_SP5_RGB[v])
    for tc in range(17):
        d.line((ox + tc * 8 * scale, oy, ox + tc * 8 * scale, oy + 32 * scale), fill=(76, 86, 102, 180))
    for tr in range(5):
        d.line((ox, oy + tr * 8 * scale, ox + 128 * scale, oy + tr * 8 * scale), fill=(76, 86, 102, 180))
    for tc in range(16):
        d.text((ox + tc * 8 * scale + 3, oy + 32 * scale + 3), f"{tc:02X}", fill=(200, 212, 228, 255))

    # Assembled frames exactly as Sprites/NPCs/deku_scrub.asm draws them (idx 0 back -> idx 3 front)
    frames = [
        ("F0 Cursed0",   [(4, 4, 0x2E, 0x3B), (4, -4, 0x0E, 0x3B), (-4, -4, 0x0E, 0x7B), (-4, 4, 0x2E, 0x7B)]),
        ("F1 Cursed1",   [(4, 4, 0x2C, 0x3B), (-4, 4, 0x2C, 0x7B), (-4, -4, 0x0C, 0x3B), (4, -4, 0x0C, 0x7B)]),
        ("F2 Withered",  [(-8, 4, 0x20, 0x3B), (-8, -12, 0x00, 0x3B), (8, -12, 0x02, 0x3B), (8, 4, 0x22, 0x3B)]),
        ("F3 Butler 0",  [(-4, -12, 0x04, 0x3B), (4, -12, 0x05, 0x3B), (-4, 4, 0x24, 0x3B), (4, 4, 0x25, 0x3B)]),
        ("F5 Butler 1",  [(-4, -11, 0x09, 0x3B), (4, -11, 0x09, 0x7B), (-4, 4, 0x24, 0x3B), (4, 4, 0x25, 0x3B)]),
        ("F4 Princ. 0",  [(-4, 4, 0x27, 0x3B), (-4, -12, 0x07, 0x3B), (4, 4, 0x27, 0x7B), (4, -12, 0x07, 0x7B)]),
        ("F6 Princ. 1",  [(-4, 4, 0x29, 0x3B), (-4, -11, 0x07, 0x3B), (4, 4, 0x29, 0x7B), (4, -11, 0x07, 0x7B)]),
    ]
    fy = oy + 32 * scale + 34
    card_w = 104
    for fi, (name, parts) in enumerate(frames):
        fx = 12 + fi * (card_w + 6)
        d.rectangle((fx, fy, fx + card_w, fy + 186), fill=(52, 82, 54, 255), outline=(115, 128, 145, 255))
        cx, cy = fx + card_w // 2 - 16, fy + 92
        for dx, dy, ch, prop in parts:
            draw_16x16(img, cx + dx * 3, cy + dy * 3, ch, bool(prop & 0x40), 3)
        d.text((fx + 4, fy + 190), name, fill=(240, 240, 240, 255))

    out_png.parent.mkdir(parents=True, exist_ok=True)
    img.save(out_png)
    print(f"Wrote preview: {out_png} ({w}x{h})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--out", type=Path, default=OUT_TXT, help="Output spr33.txt path")
    ap.add_argument("--check", action="store_true", help="Verify output matches freshly built text")
    ap.add_argument("--preview", type=Path, help="Write zoomed RGBA preview PNG")
    args = ap.parse_args(argv)

    grid = build_grid()
    text = sheet_codec.grid_to_text(grid)
    if args.preview:
        render_preview(grid, args.preview)

    if args.check:
        if not args.out.is_file():
            print(f"MISSING: {args.out}", file=sys.stderr)
            return 1
        if args.out.read_text() != text:
            print(f"STALE: {args.out}", file=sys.stderr)
            return 1
        print(f"OK: {args.out} up to date")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(text)
    print(f"Wrote {args.out} (128x32 3BPP sheet 0x33)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
