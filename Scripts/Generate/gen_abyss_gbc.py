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
     ($100-$10F) and the rooms' floor fills receive the donor metatile chars for
     the same role (B0-B3 walls, B4-BB corners, A0 floor), flips undone.
     A style may name its own floor metatile, a carpet object drawn in a second
     donor palette that shares one SNES row ("accent"), and inlay objects whose
     chars are rebuilt as carpet under the kept SNES pixels (finale style).
  2. Objects the GBC sets have no direct match for get the closest donor art:
     deep walls $007/$008/$067/$068 -> second wall set 38-3B, deep corners
     $118-$11B -> concave corners B8-BB, layered stairs $130/$131/$F9C/$F9D ->
     stair stripes 50, diagonal ceilings $0A0-$0A3 -> black A9, diagonal walls
     $009-$014 -> stepped wall slices (--diagonal wall) or a flat stepped fill
     (--diagonal fill).
  3. Every other char is posterized to the donor's four shades (no donor match;
     listed in coverage.json as fallback).
Layer-2 masks $0C2/$0C6/$FF3 draw chars $1E9/$1EC (sheet $0F, all transparent)
and need no art.
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

# "more_rooms" share a style's sheets and palette but cast no palette votes, so
# rooms reviewed earlier keep their colours when a style grows.
# Style id = position + 1. Room lists follow the 2026-11-05 look plan (scawful picks):
# Onox $44 main Fortress, Fire $42 for $2D/$3D, Rites $46 for $0D/$1D.
# The pendant shrines (Wisdom, Courage, Power) are not in this set: they move to the
# Lyra Sea (scawful, 2026-11-16) and keep SNES art.
STYLES = [
    {"name": "onox", "png": "donor_raw_fortress/seasons_gfx_tileset44.png",
     "map": "donor_raw_fortress/seasons_tilesetMappings44.bin", "pal": "donor_pal/seasons_44.txt",
     "rooms": [0x0C, 0x1C, 0x4C, 0x5C, 0x6B, 0x6D, 0x4D, 0x5D, 0x6C],
     # Fortress island block, same header blockset 14 (no new art).
     "more_rooms": [0x7B, 0x7C, 0x7D, 0x8B, 0x8D, 0x9B, 0x9D]},
    {"name": "fire", "png": "donor_raw_fortress/seasons_gfx_tileset42.png",
     "map": "donor_raw_fortress/seasons_tilesetMappings42.bin", "pal": "donor_pal/seasons_42.txt",
     "rooms": [0x2D, 0x3D]},
    {"name": "rites", "png": "donor_raw_fortress/ages_gfx_tileset46.png",
     "map": "donor_raw_fortress/ages_tilesetMappings46.bin", "pal": "donor_pal/ages_46.txt",
     "rooms": [0x0D, 0x1D]},
    # Finale rooms: onox donor with a throne-room floor, a carpet and the Triforce inlay.
    {"name": "finale", "png": "donor_raw_fortress/seasons_gfx_tileset44.png",
     "map": "donor_raw_fortress/seasons_tilesetMappings44.bin", "pal": "donor_pal/seasons_44.txt",
     "rooms": [0x00, 0x10],
     "floor_meta": 0xA1,
     # Same wall colours and posterize ranking as the onox rooms.
     "row_pal": {2: 3, 3: 4, 4: 4, 5: 4, 6: 4, 7: 3}, "posterize_like": 0x0C,
     # SNES row 2 also carries donor palette 7 (blue) in its three spare indices.
     "accent": {2: 7},
     # Carpet $0E1 -> donor carpet A2 in the accent palette (donor shade -> glyph value):
     # light-blue field, dark-blue lattice, pale dots, so the gold inlay stands out.
     "accent_floors": {0x0E1: (0xA2, {0: 4, 1: 5, 2: 6, 3: 3})},
     # Triforce inlay $FF8: two 4x4 blocks. SNES indices 5/4 (triangle body and the
     # carpet line showing through it) -> brightest gold, everything else -> the
     # carpet under it.
     "inlays": [{"object": 0xFF8, "blocks": 2, "under": 0x0E1, "keep": {5: 0, 4: 0}}]},
    # Shrine of Origins (scawful pick "1 palace", 2026-11-16): Ages palace set,
    # teal walls and green checker floor.
    {"name": "palace", "png": "donor_raw_fortress/ages_gfx_tileset5a.png",
     "map": "donor_raw_fortress/ages_tilesetMappings5a.bin", "pal": "donor_pal/ages_5a.txt",
     "rooms": [0x05],
     # SNES row 6 also carries donor palette 6 (blue) in its three spare indices.
     "accent": {6: 6},
     # Teal panel $0C5 around the chest (walkable floor) -> donor blue tile A2.
     "accent_floors": {0x0C5: (0xA2, {0: 4, 1: 5, 2: 6, 3: 3})}},
]

# Object -> (donor metatile, shape). Shapes give word k's (col, row) in the object.
# Draw orders checked against vanilla bank $01 (usdasm):
#   COLMAJ_2x4  RoomDraw_Rightwards2x4*          walls $001-$004
#   ROWMAJ_4x2  RoomDraw_Downwards4x2*  $01B220  walls $061-$064
#   COLMAJ_4x4  RoomDraw_4x4 / 4x4Corner_BothBG  $0197ED / $019813, corners $100-$10F
#               RoomDraw_AutoStairs_*MultiLayer  $01A25D / $01A31C, stairs
#   COLMAJ_2x2  RoomDraw_Rightwards2x2 $019895 / Downwards2x2 $01B2AF, deep walls
COLMAJ_2x4 = [(k // 4, k % 4) for k in range(8)]
ROWMAJ_4x2 = [(k % 4, k // 4) for k in range(8)]
COLMAJ_4x4 = [(k // 4, k % 4) for k in range(16)]
COLMAJ_2x2 = [(k // 2, k % 2) for k in range(4)]
ROLE_OBJECTS = {
    0x001: (0xB0, COLMAJ_2x4), 0x003: (0xB0, COLMAJ_2x4),
    0x002: (0xB2, COLMAJ_2x4), 0x004: (0xB2, COLMAJ_2x4),
    0x061: (0xB3, ROWMAJ_4x2), 0x063: (0xB3, ROWMAJ_4x2),
    0x062: (0xB1, ROWMAJ_4x2), 0x064: (0xB1, ROWMAJ_4x2),
    # concave: NW SW NE SE (top), then the same for bottom $108-$10B
    0x100: (0xB8, COLMAJ_4x4), 0x101: (0xBA, COLMAJ_4x4), 0x102: (0xB9, COLMAJ_4x4), 0x103: (0xBB, COLMAJ_4x4),
    0x108: (0xB8, COLMAJ_4x4), 0x109: (0xBA, COLMAJ_4x4), 0x10A: (0xB9, COLMAJ_4x4), 0x10B: (0xBB, COLMAJ_4x4),
    # convex (inner) corners, top $104-$107 then bottom $10C-$10F. Checked: the
    # $104 word grid has its wall block at NW (left column = north-wall profile,
    # top row = west-wall profile), $105 = v-flip (SW), $106 = h-flip (NE),
    # $107 = both (SE). Donor B7/B5/B6/B4 have the wall block at NW/SW/NE/SE
    # (real Ages room 05:24).
    0x104: (0xB7, COLMAJ_4x4), 0x105: (0xB5, COLMAJ_4x4), 0x106: (0xB6, COLMAJ_4x4), 0x107: (0xB4, COLMAJ_4x4),
}
# Roles added after the first styled rooms were reviewed. Their palette votes go
# to a second tally that only decides rows the roles above leave unclaimed, so
# rooms already styled keep their colours.
EXTRA_ROLE_OBJECTS = {
    0x10C: (0xB7, COLMAJ_4x4), 0x10D: (0xB5, COLMAJ_4x4), 0x10E: (0xB6, COLMAJ_4x4), 0x10F: (0xB4, COLMAJ_4x4),
    # deep walls N S W E -> second GBC wall set (38 top, 39 right, 3A bottom, 3B left)
    0x007: (0x38, COLMAJ_2x2), 0x008: (0x3A, COLMAJ_2x2),
    0x067: (0x3B, COLMAJ_2x2), 0x068: (0x39, COLMAJ_2x2),
    # deep corners NW SW NE SE: corner and inner chars from the concave corners
    # (their two wall chars are already set by the deep walls above)
    0x118: (0xB8, COLMAJ_2x2), 0x119: (0xBA, COLMAJ_2x2), 0x11A: (0xB9, COLMAJ_2x2), 0x11B: (0xBB, COLMAJ_2x2),
    # layered stairs (north $130/$131, south $F9C/$F9D) -> GBC stair stripes
    0x130: (0x50, COLMAJ_4x4), 0x131: (0x50, COLMAJ_4x4),
    0xF9C: (0x50, COLMAJ_4x4), 0xF9D: (0x50, COLMAJ_4x4),
}
# Solid fills: one flat glyph, no palette vote (a flat tile reads in any row).
FILL_OBJECTS = {0x0A0: 0xA9, 0x0A1: 0xA9, 0x0A2: 0xA9, 0x0A3: 0xA9}  # diagonal ceilings -> black
# Diagonal walls $009-$014 draw one 5-char column (void edge, 3 body, floor trim)
# stepped one row per column. GBC sets have no diagonals; per char of the $009
# column: (donor metatile, col, row). No palette votes: the trim char uses a
# different palette row per object group.
DIAGONAL_OBJECTS = range(0x009, 0x015)
DIAGONAL_STYLES = {
    # stepped slices of the north wall under a black step
    "wall": [(0xA9, 0, 0), (0xB0, 0, 0), (0xB0, 0, 1), (0xB0, 0, 0), (0xB0, 0, 1)],
    # flat dark steps with the wall's inner edge
    "fill": [(0xA9, 0, 0), (0xA8, 0, 0), (0xA8, 0, 0), (0xA8, 0, 0), (0xB0, 0, 1)],
}
# Alternates for objects with no direct GBC equivalent (review options).
DEEP_STYLES = {
    "second": {},  # default above: second GBC wall set 38-3B
    "main": {0x007: (0xB0, COLMAJ_2x2), 0x008: (0xB2, COLMAJ_2x2),
             0x067: (0xB3, COLMAJ_2x2), 0x068: (0xB1, COLMAJ_2x2)},
}
STAIR_STYLES = {
    "stripes": {},  # default above: stair stripes 50
    "icons": {0x130: (0x44, COLMAJ_4x4), 0x131: (0x44, COLMAJ_4x4),
              0xF9C: (0x45, COLMAJ_4x4), 0xF9D: (0x45, COLMAJ_4x4)},
}
FLOOR_META = 0xA0
STREAM_BUDGET = 0x7000  # bank $5A bytes for streams after code + tables
# Checked: RoomDraw_A_Many32x32Blocks ($018A44) writes the 8 floor words
# row-major 4x2 (tilemap +$000..+$006, then +$080..+$086), twice vertically.
FLOOR_SHAPE = ROWMAJ_4x2


def object_words(rom: bytes, obj: int, n: int) -> list[int]:
    """First n tile words of an object. Subtype 3 ($F80-$FFF) uses the
    offset table at $01:84F0, which gen_wall_profiles does not read."""
    if obj >= 0xF80:
        pc = gw.OBJ_TABLE_PC + gw.rom_word(rom, 0x84F0 + (obj - 0xF80) * 2)
        return [gw.rom_word(rom, pc + 2 * k) for k in range(n)]
    return gw.class_words(rom, rom, obj)[:n]


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
        voters = set(style["rooms"])
        rooms = style["rooms"] + style.get("more_rooms", [])
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
        extra_votes: dict[int, Counter] = defaultdict(Counter)

        def place(word, meta, col, row, tally=votes, shades=None):
            c = word & 0x3FF
            g, p = donor.quadrant(meta, col % 2, row % 2)
            if shades:
                g = [[shades[v] for v in ln] for ln in g]
            if tally is not None:
                tally[(word >> 10) & 7][p] += 1
            if c not in glyph:
                glyph[c] = unflip(g, word)

        floor_meta = style.get("floor_meta", FLOOR_META)
        # Glyph values: 0-3 = shade of the row's donor palette, 4-6 = shade 0-2 of
        # the row's accent palette (style key "accent").
        for obj, (meta, shades) in style.get("accent_floors", {}).items():
            for (col, row), w in zip(FLOOR_SHAPE, object_words(rom, obj, 8)):
                place(w, meta, col, row, None, shades)
        for inlay in style.get("inlays", []):
            meta, shades = style["accent_floors"][inlay["under"]]
            under_c = object_words(rom, inlay["under"], 1)[0] & 0x3FF
            ws = object_words(rom, inlay["object"], 16 * inlay["blocks"])
            for k, w in enumerate(ws):
                c = w & 0x3FF
                if c == under_c or c in glyph:
                    continue
                col, row = COLMAJ_4x4[k % 16]
                slot = c // 64
                sheet = gw.effective_slots(rom, gw.room_blockset_palette(rom, rooms[0])[0])[slot]
                data, _ = st.decomp(rom, st.ptr(rom, sheet))
                sg = sc.sheet_to_grid(bytes(data[:0x600]))
                tx, ty = (c % 16) * 8, ((c % 64) // 16) * 8
                src = [[sg[ty + y][tx + x] for x in range(8)] for y in range(8)]
                src = unflip(src, w)  # as drawn on screen
                # The carpet words alternate h-flip per column starting flipped, so
                # block column c sits on carpet quadrant (c + 1) % 2.
                ug, _ = donor.quadrant(meta, (col + 1) % 2, row % 2)
                out = [[inlay["keep"][src[y][x]] if src[y][x] in inlay["keep"] else shades[ug[y][x]]
                        for x in range(8)] for y in range(8)]
                glyph[c] = unflip(out, w)

        extra = {**EXTRA_ROLE_OBJECTS, **DEEP_STYLES[a.deep], **STAIR_STYLES[a.stairs]}
        for roles, tally in ((ROLE_OBJECTS, votes), (extra, extra_votes)):
            for obj, (meta, shape) in roles.items():
                for (col, row), w in zip(shape, object_words(rom, obj, len(shape))):
                    place(w, meta, col, row, tally)
        for obj, meta in FILL_OBJECTS.items():
            place(object_words(rom, obj, 1)[0], meta, 0, 0, None)
        diag = {w & 0x3FF: spec for w, spec in
                zip(object_words(rom, DIAGONAL_OBJECTS[0], 5), DIAGONAL_STYLES[a.diagonal])}
        for obj in DIAGONAL_OBJECTS:
            for w in object_words(rom, obj, 5):
                if (w & 0x3FF) in diag:
                    meta, col, row = diag[w & 0x3FF]
                    place(w, meta, col, row, None)
        table = gw.room_object_table(rom, rooms)
        for r in rooms:
            p = gw.snes_pc(table + 3 * r)
            b = rom[gw.snes_pc(int.from_bytes(rom[p:p + 3], "little"))]
            for f in (b >> 4, b & 0xF):
                for k in range(8):
                    w = gw.rom_word(rom, gw.OBJ_TABLE_PC + f * 16 + 2 * k)
                    col, row = FLOOR_SHAPE[k]
                    place(w, floor_meta, col, row, votes if r in voters else None)

        # palette rows 2-7: donor palette by vote, default = floor palette
        floor_pal = donor.quadrant(floor_meta, 0, 0)[1]
        row_pal = {}
        for r in range(2, 8):
            tally = votes[r] or extra_votes[r]
            row_pal[r] = tally.most_common(1)[0][0] if tally else floor_pal
        row_pal.update(style.get("row_pal", {}))
        # posterize: rank SNES indices 1-7 by mean luminance over the rooms' rows 2-7
        like = style.get("posterize_like")
        snes = gw.palette(rom, gw.room_blockset_palette(rom, like)[1] if like is not None else pal_ids[0])
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

        # Palette entry i (1-7) holds the donor shade that SNES index i posterizes
        # to, so sheets this style does not remap (slot 7, animated, unlisted)
        # still read by luminance instead of falling to the darkest shade.
        inv = {}
        for i in range(1, 8):
            inv.setdefault(quant[i] - 1, i)
        # Accent: the three indices that duplicate a shade (one each for the three
        # brightest) hold the accent palette's shades 0-2, brightest first. Its
        # shade 3 is the row's own darkest shade.
        accent = style.get("accent", {})
        spare = sorted((i for i in range(1, 8) if i not in inv.values()),
                       key=lambda i: donor_rank.index(quant[i] - 1))
        pix = {**inv, **{4 + k: i for k, i in enumerate(spare)}}
        words = []
        for r in range(2, 8):
            cols = donor.pal[row_pal[r]]
            half = [cols[quant[i] - 1] for i in range(1, 8)]
            if r in accent:
                acc = sorted(donor.pal[accent[r]][:3], key=lambda c: -lum(c5(c)))
                for k, i in enumerate(spare):
                    half[i - 1] = acc[k]
            row = half + [cols[0]] + half  # 1-7, 8, 9-15
            for c in row:
                words.append(c[0] | (c[1] << 5) | (c[2] << 10))
        palettes.append(words)


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
                            if dg:
                                g[ty + y][tx + x] = pix[dg[y][x]]
                            elif accent and v:
                                # free the spare indices for the accent palette
                                g[ty + y][tx + x] = inv[quant[v] - 1]
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
                                   "row_votes": {str(r): dict(sorted(votes[r].items())) for r in range(2, 8)},
                                   "extra_row_votes": {str(r): dict(sorted(extra_votes[r].items())) for r in range(2, 8)},
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
    b.add_argument("--diagonal", choices=sorted(DIAGONAL_STYLES), default="wall",
                   help="art for diagonal walls $009-$014 (default: stepped wall slices)")
    b.add_argument("--deep", choices=sorted(DEEP_STYLES), default="second",
                   help="art for deep walls $007/$008/$067/$068 (default: second GBC wall set)")
    b.add_argument("--stairs", choices=sorted(STAIR_STYLES), default="stripes",
                   help="art for layered stairs $130/$131/$F9C/$F9D (default: stair stripes)")
    b.set_defaults(fn=build)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
