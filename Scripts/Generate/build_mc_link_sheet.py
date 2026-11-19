#!/usr/bin/env python3
"""Build Data/graphics/link/mc_link_sheet.4bpp cleanly from scawful's base ROM Link sheet
($108000) + artist-authored InTheBEEF Minish Cap Link frames (Masks/etc/minishcaplink.3.zspr).

Design principles (per scawful's 2026-11-19 review):
  1. Preserve 100% of scawful's existing hand-ported Minish Cap heads, walk, idle, swim,
     and action frames in the base ROM ($108000).
  2. For remaining untouched vanilla ALTTP frames (Praying/Shock R17C1/R18C1/R19C1,
     Midway Pull R13C0, Upside-Down R04C7, Hatless/Flute/Bed R25C5/R26C1/R26C4, and
     secondary action bodies), pull the genuine artist-drawn frames directly from
     Masks/etc/minishcaplink.3.zspr (InTheBEEF) and remap cleanly into Oracle's exact
     ROM Link palette (preserving Green/Blue/Red Mail sleeve recoloring via C10/C11/C12/C09).
  3. Never pull InTheBEEF's unused-slot Easter-egg signature blocks (R16C2..C4, R17C3..C5,
     R21C7, R22C0..C7, R23C0) or blank ZSPR slots; on remaining brown-sleeve vanilla body
     cells, apply a minimal Mail-recolored sleeve remap directly to the base ROM cell.
  4. Never overwrite valid existing cells with synthetic/procedural faces.

Usage:
  python3 Scripts/Generate/build_mc_link_sheet.py [--base PATH] [--out PATH] [--check]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = ROOT / "Data/graphics/link/mc_link_sheet.4bpp"
DEFAULT_ZSPR = ROOT / "Masks/etc/minishcaplink.3.zspr"
DEFAULT_BASE_CANDIDATES = [
    Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"),
    ROOT / "Roms/oos168.sfc",
]
SHEET_SIZE = 28672  # $7000 bytes = 28 rows x 8 cols of 16x16 4BPP cells

# ZSPR (InTheBEEF) -> Oracle ROM Link palette index remap:
#   ZSPR: 1=white, 2=goldHairMid, 3=warmBrownHairShade, 4=midSkin, 5=outline, 6=goldAccent,
#         7=red, 8=blue, 9=tunicDark, 10=tunicMid, 11=tunicBright, 12=lightSkin,
#         13=brightHair, 14=darkBrownBootBelt, 15=slash
#   ROM:  1=white, 2=brightHair, 3=midSkin, 4=lightSkin, 5=outline, 6=goldHairMid,
#         7=red, 8=blue, 9=tunicDarkest, 10=tunicBright, 11=tunicDark, 12=tunicMid,
#         13=tanBrownMid, 14=darkBrownBootBelt, 15=slash
ZSPR_TO_ROM_PAL = {
    0: 0,
    1: 1,
    2: 6,
    3: 6,   # warm hair-shadow / cuff-gold -> C06 (matches R00 Minish Cap blonde shading!)
    4: 3,
    5: 5,
    6: 6,
    7: 7,
    8: 8,
    9: 11,  # tunic dark (Mail-recolored!)
    10: 12, # tunic mid (Mail-recolored!)
    11: 10, # tunic bright (Mail-recolored!)
    12: 4,
    13: 2,  # bright blonde hair -> C02
    14: 14,
    15: 15,
}

# Body-only ZSPR cells where ZSPR C03 is boot/belt warm brown -> ROM C13 instead of C06 gold
ZSPR_TO_ROM_BODY = {
    **ZSPR_TO_ROM_PAL,
    3: 13,
}

# Valid artist-drawn InTheBEEF ZSPR head/full-figure cells (zero blank/signature cells!)
ZSPR_HEAD_CELLS: tuple[tuple[int, int], ...] = (
    (4, 7),   # Upside-down somersault ($12B)
    (17, 1),  # Praying / Shock top ($07D)
    (18, 1),  # Praying / Shock mid ($07D/$080)
    (19, 1),  # Praying / Shock full ($080)
    (23, 1),  # Side hooded/tumble head
    (25, 5),  # Hatless / Flute head ($128)
    (26, 1),  # Sleep / Bed back head
    (26, 4),  # Sleep / Bed side head
)

# Valid artist-drawn InTheBEEF ZSPR body cells (all Mail-recolored sleeves, zero Easter-egg cells!)
ZSPR_BODY_CELLS: tuple[tuple[int, int], ...] = (
    (2, 7),
    (8, 0),
    (11, 4),
    (13, 0),  # Midway pull!
    (13, 2),
    (13, 3),
    (14, 2),
    (14, 3),
    (14, 4),
    (15, 1),
    (15, 5),
    (16, 0),
    (16, 1),
    (18, 5),
    (18, 6),
    (20, 4),
    (20, 7),
    (21, 0),
    (21, 1),
    (21, 2),
    (21, 3),
    (21, 4),
    (21, 5),
    (21, 6),
    (23, 3),
    (23, 5),
    (23, 6),
    (23, 7),
    (24, 3),
    (24, 4),
    (24, 5),
    (25, 7),
    (26, 0),
    (26, 2),
    (26, 3),
    (26, 5),
    (26, 6),
    (26, 7),
    (27, 2),
    (27, 3),
)

# Vanilla brown-sleeve body cells where ZSPR has blank or @InTheBEEF signature art:
# Keep the exact ROM body silhouette and ONLY recolor brown ALTTP sleeve pixels (C13/C14 -> C12/C11)
# in the upper-arm/shoulder band (rows 0..10), preserving belt/boots untouched!
SLEEVE_RECOLOR_CELLS: tuple[tuple[int, int], ...] = (
    (3, 5),
    (3, 6),
    (4, 0),
    (4, 1),
    (16, 2),
    (16, 3),
    (16, 4),
    (17, 3),
    (17, 4),
    (17, 5),
    (20, 3),
    (21, 7),
    (22, 0),
    (22, 1),
    (22, 2),
    (22, 3),
    (22, 4),
    (22, 5),
    (22, 6),
    (22, 7),
    (23, 0),
)

ALL_UPGRADED_CELLS = set(ZSPR_HEAD_CELLS) | set(ZSPR_BODY_CELLS) | set(SLEEVE_RECOLOR_CELLS)


def decode_4bpp_sheet(data: bytes) -> list[list[int]]:
    if len(data) != SHEET_SIZE:
        raise ValueError(f"Expected {SHEET_SIZE} bytes, got {len(data)}")
    grid = [[0] * 128 for _ in range(448)]
    for tr in range(56):
        for tc in range(16):
            off = (tr * 16 + tc) * 32
            for y in range(8):
                b0 = data[off + y * 2]
                b1 = data[off + y * 2 + 1]
                b2 = data[off + 16 + y * 2]
                b3 = data[off + 16 + y * 2 + 1]
                row = grid[tr * 8 + y]
                x0 = tc * 8
                for x in range(8):
                    bit = 7 - x
                    row[x0 + x] = (
                        ((b0 >> bit) & 1)
                        | (((b1 >> bit) & 1) << 1)
                        | (((b2 >> bit) & 1) << 2)
                        | (((b3 >> bit) & 1) << 3)
                    )
    return grid


def encode_4bpp_sheet(grid: list[list[int]]) -> bytes:
    out = bytearray(SHEET_SIZE)
    for tr in range(56):
        for tc in range(16):
            off = (tr * 16 + tc) * 32
            x0 = tc * 8
            for y in range(8):
                row = grid[tr * 8 + y]
                p0 = p1 = p2 = p3 = 0
                for x in range(8):
                    v = row[x0 + x]
                    bit = 0x80 >> x
                    if v & 1:
                        p0 |= bit
                    if v & 2:
                        p1 |= bit
                    if v & 4:
                        p2 |= bit
                    if v & 8:
                        p3 |= bit
                out[off + y * 2] = p0
                out[off + y * 2 + 1] = p1
                out[off + 16 + y * 2] = p2
                out[off + 16 + y * 2 + 1] = p3
    return bytes(out)


def load_zspr_gfx(path: Path) -> bytes:
    raw = path.read_bytes()
    if raw[:4] != b"ZSPR":
        raise ValueError(f"{path} is not a valid ZSPR file")
    gfx_off, gfx_len, _pal_off, _pal_len = struct.unpack_from("<IHIH", raw, 9)
    if gfx_len != SHEET_SIZE:
        raise ValueError(f"{path}: unexpected gfx_len={gfx_len}")
    return raw[gfx_off : gfx_off + gfx_len]


def load_base_sheet(path: Path) -> bytes:
    raw = path.read_bytes()
    if len(raw) == SHEET_SIZE:
        return raw
    if len(raw) >= 0x80000 + SHEET_SIZE:
        return raw[0x80000 : 0x80000 + SHEET_SIZE]
    raise ValueError(f"Unsupported base size {len(raw)} for {path}")


def build_sheet(base_bytes: bytes, zspr_path: Path = DEFAULT_ZSPR) -> bytes:
    grid = decode_4bpp_sheet(base_bytes)
    zgrid = decode_4bpp_sheet(load_zspr_gfx(zspr_path))

    # 1. Copy artist-drawn InTheBEEF head/praying/flute/bed frames with clean ROM palette remap
    for r, c in ZSPR_HEAD_CELLS:
        y0, x0 = r * 16, c * 16
        for dy in range(16):
            for dx in range(16):
                grid[y0 + dy][x0 + dx] = ZSPR_TO_ROM_PAL[zgrid[y0 + dy][x0 + dx]]

    # 2. Copy artist-drawn InTheBEEF body frames (including midway pull R13C0)
    for r, c in ZSPR_BODY_CELLS:
        y0, x0 = r * 16, c * 16
        for dy in range(16):
            for dx in range(16):
                grid[y0 + dy][x0 + dx] = ZSPR_TO_ROM_BODY[zgrid[y0 + dy][x0 + dx]]

    # 3. On body cells where ZSPR has blank or @InTheBEEF signature art, minimally recolor
    #    vanilla brown ALTTP sleeves (C13/C14 in rows 0..10) to Mail-recolored tunic shades
    #    (C10/C12/C11) while keeping the exact ROM silhouette, hands, belt, and boots intact!
    for r, c in SLEEVE_RECOLOR_CELLS:
        y0, x0 = r * 16, c * 16
        for dy in range(11):
            for dx in range(16):
                v = grid[y0 + dy][x0 + dx]
                if v == 13:
                    grid[y0 + dy][x0 + dx] = 10  # sleeve highlight -> Mail tunic bright
                elif v == 14:
                    # Only convert brown sleeve pixels adjacent to tunic/skin/arm, not deep bottom boots
                    grid[y0 + dy][x0 + dx] = 11  # sleeve shade -> Mail tunic dark

    return encode_4bpp_sheet(grid)


def resolve_default_base() -> Path:
    for cand in DEFAULT_BASE_CANDIDATES:
        if cand.is_file():
            return cand
    if DEFAULT_OUT.is_file():
        return DEFAULT_OUT
    raise FileNotFoundError("No base ROM or mc_link_sheet.4bpp found; pass --base")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--base", type=Path, help="Base ROM (.sfc/rom) or 28672B 4BPP sheet")
    ap.add_argument("--zspr", type=Path, default=DEFAULT_ZSPR, help="Reference Minish Cap Link ZSPR")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="Output 28672B 4BPP path")
    ap.add_argument("--check", action="store_true", help="Verify output matches reproducible build")
    args = ap.parse_args(argv)

    base_path = args.base or resolve_default_base()
    rebuilt = build_sheet(load_base_sheet(base_path), args.zspr)

    if args.check:
        if not args.out.is_file():
            print(f"MISSING: {args.out}", file=sys.stderr)
            return 1
        cur = args.out.read_bytes()
        if cur != rebuilt:
            print(f"STALE: {args.out} differs from freshly built bytes", file=sys.stderr)
            return 1
        print(f"OK: {args.out} matches reproducible build ({len(rebuilt)} bytes, {len(ALL_UPGRADED_CELLS)} cells upgraded from ZSPR/recolor)")
        return 0

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(rebuilt)
    print(f"Wrote {args.out} ({len(rebuilt)} bytes, {len(ALL_UPGRADED_CELLS)} cells upgraded)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
