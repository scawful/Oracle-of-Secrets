#!/usr/bin/env python3
"""Generate Eon Abyss GBC interior sheets, palettes and tables.

Reads the room headers, object words and BG sheets of a built ROM plus GBC donor
tilesets (oracles-disasm PNG + tilesetMappings + 24-line palette text), and writes
Dungeons/Data/abyss_gbc/:
  <style>.<sheet>.txt   GBC version of a BG sheet (sheet_codec text grid, reviewable)
  <style>.<sheet>.lz2   the same sheet, LC-LZ2
  abyss_gbc.asm         room style table, sheet map, stream pointers, palettes
  coverage.json         chars written from donor art vs posterized fallback

Per style, every BG sheet in slots 0-6 of the style's rooms gets a GBC copy:
  1. Chars drawn by wall objects ($001-$004, $061-$064), concave/convex corners
     ($100-$10B) and the rooms' floor fills receive the donor metatile chars for
     the same role (B0-B3 walls, B4-BB corners, A0 floor), flips undone.
  2. Every other char is posterized to the donor's four shades (no donor match;
     listed in coverage.json as fallback).
The palette table holds 6 BG rows x 15 colours per style (rows 2-7). Each SNES row
gets the donor palette that most of its donor-mapped chars use.

Usage:
  python3 Scripts/Generate/gen_abyss_gbc.py build --rom Roms/oos168x.sfc --donor <gbc_interiors dir>
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_wall_profiles as gw  # noqa: E402
import lz2  # noqa: E402
import sheet_codec as sc  # noqa: E402
import sheet_table as st  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "Dungeons/Data/abyss_gbc"

# Style id = position + 1. Room lists follow the 2026-11-05 look plan (scawful picks):
# Onox $44 main Fortress, Fire $42 for $2D/$3D, Rites $46 for $0D/$1D, Mermaid $3B shrines.
STYLES = [
    {"name": "onox", "png": "donor_raw_fortress/seasons_gfx_tileset44.png",
     "map": "donor_raw_fortress/seasons_tilesetMappings44.bin", "pal": "donor_pal/seasons_44.txt",
     "rooms": [0x0C, 0x1C, 0x4C, 0x5C, 0x6B, 0x6D, 0x4D, 0x5D, 0x6C]},
    {"name": "fire", "png": "donor_raw_fortress/seasons_gfx_tileset42.png",
     "map": "donor_raw_fortress/seasons_tilesetMappings42.bin", "pal": "donor_pal/seasons_42.txt",
     "rooms": [0x2D, 0x3D]},
    {"name": "rites", "png": "donor_raw_fortress/ages_gfx_tileset46.png",
     "map": "donor_raw_fortress/ages_tilesetMappings46.bin", "pal": "donor_pal/ages_46.txt",
     "rooms": [0x0D, 0x1D]},
    {"name": "mermaid", "png": "donor_raw_3b/gfx_tileset3b.png",
     "map": "donor_raw_3b/tilesetMappings3b.bin", "pal": "donor_pal/ages_3b.txt",
     "rooms": [0xC9, 0x53]},
]

# Object -> (donor metatile, shape). Shapes give word k's (col, row) in the object.
COLMAJ_2x4 = [(k // 4, k % 4) for k in range(8)]
ROWMAJ_4x2 = [(k % 4, k // 4) for k in range(8)]
COLMAJ_4x4 = [(k // 4, k % 4) for k in range(16)]
ROLE_OBJECTS = {
    0x001: (0xB0, COLMAJ_2x4), 0x003: (0xB0, COLMAJ_2x4),
    0x002: (0xB2, COLMAJ_2x4), 0x004: (0xB2, COLMAJ_2x4),
    0x061: (0xB3, ROWMAJ_4x2), 0x063: (0xB3, ROWMAJ_4x2),
    0x062: (0xB1, ROWMAJ_4x2), 0x064: (0xB1, ROWMAJ_4x2),
    # concave: NW SW NE SE (top), then the same for bottom $108-$10B
    0x100: (0xB8, COLMAJ_4x4), 0x101: (0xBA, COLMAJ_4x4), 0x102: (0xB9, COLMAJ_4x4), 0x103: (0xBB, COLMAJ_4x4),
    0x108: (0xB8, COLMAJ_4x4), 0x109: (0xBA, COLMAJ_4x4), 0x10A: (0xB9, COLMAJ_4x4), 0x10B: (0xBB, COLMAJ_4x4),
    # convex (inner) corners: SE NE SW NW
    0x104: (0xB7, COLMAJ_4x4), 0x105: (0xB5, COLMAJ_4x4), 0x106: (0xB6, COLMAJ_4x4), 0x107: (0xB4, COLMAJ_4x4),
}
FLOOR_META = 0xA0
STREAM_BUDGET = 0x7000  # bank $5A bytes for streams after code + tables
FLOOR_SHAPE = ROWMAJ_4x2


def c5(c):
    return (c[0] * 255 // 31, c[1] * 255 // 31, c[2] * 255 // 31)


def lum(rgb):
    return 0.299 * rgb[0] + 0.587 * rgb[1] + 0.114 * rgb[2]


class Donor:
    def __init__(self, root: Path, style: dict):
        from PIL import Image
        im = Image.open(root / style["png"])
        self.px = im.load()
        self.maps = (root / style["map"]).read_bytes()
        vals = [tuple(int(v, 16) for v in ln.split()) for ln in (root / style["pal"]).read_text().splitlines() if ln.strip()]
        self.pal = {2 + i: vals[i * 4:i * 4 + 4] for i in range(6)}  # 5-bit RGB, GBC palettes 2-7

    def char(self, i):
        x0, y0 = (i % 16) * 8, (i // 16) * 8
        return [[self.px[x0 + x, y0 + y] & 3 for x in range(8)] for y in range(8)]

    def quadrant(self, meta, qx, qy):
        """8x8 shade grid (GBC colour 0-3) and GBC palette of a metatile quadrant."""
        e = self.maps[meta * 8:meta * 8 + 8]
        k = qy * 2 + qx
        t, a = e[k], e[4 + k]
        g = self.char(t ^ 0x80)
        if a & 0x20:
            g = [r[::-1] for r in g]
        if a & 0x40:
            g = g[::-1]
        return g, (a & 7) if (a & 7) >= 2 else 2


def unflip(g, word):
    """Glyph to store so that drawing it with `word`'s flips shows g."""
    if word & 0x4000:
        g = [r[::-1] for r in g]
    if word & 0x8000:
        g = g[::-1]
    return g


def build(a: argparse.Namespace) -> int:
    rom = Path(a.rom).read_bytes()
    donor_root = Path(a.donor)
    OUT.mkdir(parents=True, exist_ok=True)
    streams = []  # (label, path)
    sheet_map = []  # per style: dict sheet -> stream index (1-based)
    palettes = []
    coverage = {}
    room_style = [0] * gw.ROOM_COUNT

    for sid, style in enumerate(STYLES, 1):
        donor = Donor(donor_root, style)
        rooms = style["rooms"]
        for r in rooms:
            room_style[r] = sid
        # sheets per slot 0-6 (slot 7 is shared animated/door art and stays SNES)
        slot_sheets: dict[int, set[int]] = defaultdict(set)
        pal_ids = []
        for r in rooms:
            bs, pid = gw.room_blockset_palette(rom, r)
            pal_ids.append(pid)
            for slot, s in enumerate(gw.effective_slots(rom, bs)[:7]):
                slot_sheets[slot].add(s)

        # donor glyph per (char, from word) ; first writer wins
        glyph: dict[int, list] = {}
        votes: dict[int, Counter] = defaultdict(Counter)

        def place(word, meta, col, row):
            c = word & 0x3FF
            g, p = donor.quadrant(meta, col % 2, row % 2)
            votes[(word >> 10) & 7][p] += 1
            if c not in glyph:
                glyph[c] = unflip(g, word)

        for obj, (meta, shape) in ROLE_OBJECTS.items():
            for k, w in enumerate(gw.class_words(rom, rom, obj)):
                col, row = shape[k]
                place(w, meta, col, row)
        table = gw.room_object_table(rom, rooms)
        for r in rooms:
            p = gw.snes_pc(table + 3 * r)
            b = rom[gw.snes_pc(int.from_bytes(rom[p:p + 3], "little"))]
            for f in (b >> 4, b & 0xF):
                for k in range(8):
                    w = gw.rom_word(rom, gw.OBJ_TABLE_PC + f * 16 + 2 * k)
                    col, row = FLOOR_SHAPE[k]
                    place(w, FLOOR_META, col, row)

        # palette rows 2-7: donor palette by vote, default = floor palette
        floor_pal = donor.quadrant(FLOOR_META, 0, 0)[1]
        row_pal = {r: (votes[r].most_common(1)[0][0] if votes[r] else floor_pal) for r in range(2, 8)}
        words = []
        for r in range(2, 8):
            cols = donor.pal[row_pal[r]]
            half = list(cols) + [cols[3]] * 3  # indices 1-7
            row = half + [cols[0]] + half  # 1-7, 8, 9-15
            for c in row:
                words.append(c[0] | (c[1] << 5) | (c[2] << 10))
        palettes.append(words)

        # posterize: rank SNES indices 1-7 by mean luminance over the rooms' rows 2-7
        snes = gw.palette(rom, pal_ids[0])
        mean = {}
        for i in range(1, 8):
            vals = []
            for r in range(6):
                w = snes[r * 15 + (i - 1)]
                vals.append(lum(((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8)))
            mean[i] = sum(vals) / len(vals)
        fp = donor.pal[floor_pal]
        donor_rank = sorted(range(4), key=lambda k: -lum(c5(fp[k])))  # brightest first
        ranked = sorted(mean, key=lambda i: -mean[i])
        quant = {0: 0}
        for n, i in enumerate(ranked):
            quant[i] = donor_rank[min(3, n * 4 // 7)] + 1

        smap = {}
        cov = {}
        for slot in sorted(slot_sheets):
            for s in sorted(slot_sheets[slot]):
                if s in smap:
                    continue
                addr = st.ptr(rom, s)
                data, _ = st.decomp(rom, addr)
                if len(data) < 0x600:
                    cov[f"{s:02X}"] = "skipped: not a 0x600-byte 3bpp sheet"
                    continue
                g = sc.sheet_to_grid(bytes(data[:0x600]))
                donor_chars, fallback = [], []
                for t in range(64):
                    tx, ty = (t % 16) * 8, (t // 16) * 8
                    c = slot * 64 + t
                    dg = glyph.get(c)
                    for y in range(8):
                        for x in range(8):
                            v = g[ty + y][tx + x]
                            g[ty + y][tx + x] = (dg[y][x] + 1) if dg else quant[v]
                    if dg:
                        donor_chars.append(c)
                    elif any(g[ty + y][tx + x] for y in range(8) for x in range(8)):
                        fallback.append(c)
                stem = f"{style['name']}.{s:02X}"
                (OUT / f"{stem}.txt").write_text(sc.grid_to_text(g))
                (OUT / f"{stem}.lz2").write_bytes(lz2.compress(sc.grid_to_sheet(g)))
                streams.append(stem)
                smap[s] = len(streams)
                cov[f"{s:02X}"] = {"slot": slot, "donor_chars": [f"{c:03X}" for c in donor_chars],
                                   "posterized_chars": len(fallback)}
        sheet_map.append(smap)
        coverage[style["name"]] = {"rooms": [f"{r:02X}" for r in rooms], "row_palettes": {str(k): v for k, v in row_pal.items()},
                                   "sheets": cov}

    lines = [
        "; Generated by Scripts/Generate/gen_abyss_gbc.py. Do not edit.",
        f"; Styles: {', '.join(f'{i}={s['name']}' for i, s in enumerate(STYLES, 1))}",
        "AbyssGbc_RoomStyle:",
    ]
    for i in range(0, gw.ROOM_COUNT, 16):
        lines.append("  db " + ", ".join(f"${v:02X}" for v in room_style[i:i + 16]))
    lines.append("AbyssGbc_SheetMap:")
    for smap in sheet_map:
        row = [smap.get(s, 0) for s in range(256)]
        for i in range(0, 256, 16):
            lines.append("  db " + ", ".join(f"${v:02X}" for v in row[i:i + 16]))
    lines.append("AbyssGbc_Ptr:")
    for stem in streams:
        lines.append(f"  dl AbyssGbc_{stem.replace('.', '_')} : db $00")
    lines.append("AbyssGbc_PalOffset:")
    lines.append("  dw " + ", ".join(f"${i * 180:04X}" for i in range(len(palettes))))
    lines.append("AbyssGbc_Pal:")
    for words in palettes:
        for i in range(0, len(words), 15):
            lines.append("  dw " + ", ".join(f"${w:04X}" for w in words[i:i + 15]))
    # Streams fill the rest of bank $5A (code + tables stay under STREAM_BUDGET), then $5B.
    used, bank_b = 0, False
    for stem in streams:
        size = (OUT / f"{stem}.lz2").stat().st_size
        if not bank_b and used + size > STREAM_BUDGET:
            lines += ["assert pc() <= $5B0000, \"Abyss GBC bank $5A overrun\"", "org $5B8000"]
            bank_b = True
        used += size
        lines.append(f"AbyssGbc_{stem.replace('.', '_')}: incbin \"Dungeons/Data/abyss_gbc/{stem}.lz2\"")
    lines.append("assert pc() <= $5C0000, \"Abyss GBC bank $5B overrun\"")
    (OUT / "abyss_gbc.asm").write_text("\n".join(lines) + "\n")
    (OUT / "coverage.json").write_text(json.dumps(coverage, indent=1) + "\n")
    total = sum((OUT / f"{s}.lz2").stat().st_size for s in streams)
    print(f"styles={len(STYLES)} streams={len(streams)} lz2_bytes={total}")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--rom", default=str(REPO / "Roms/oos168x.sfc"))
    b.add_argument("--donor", required=True, help="AFS gbc_interiors directory with donor_raw_* and donor_pal")
    b.set_defaults(fn=build)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
