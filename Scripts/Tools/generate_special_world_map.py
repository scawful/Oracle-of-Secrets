#!/usr/bin/env python3
"""Deterministic SNES Mode 7 Special Overworld ($80-$BF) World Map generator.

Reads the 64 Special Overworld maps ($80-$BF) directly from an Oracle of Secrets
base ROM (read-only), using OOSOW192 native tail tables for $A0-$BF and legacy
ZSCustomOverworld v3 tables for $80-$9F, renders each playable area with its
actual Tile16/8-sheet graphics and main/aux/BG palettes, masks non-world slots
(overlays $93-$97/$9C-$9F, curtain $88, unlinked Sky drafts $84-$86, isolated
Maku Tree $80, reserved Fortress $9B) with ALTTP Mode 7 ocean/cloud veil, and
quantizes the resulting 512x512 map into authentic SNES Mode 7 binaries:

  - Overworld/world_map/SwMapTileset.bin (4,096 B, 4 quadrants of 32x32 tiles)
  - Overworld/world_map/SwMapGfx.bin     (16,384 B, 256 8bpp 8x8 tiles, indices 0..127)
  - Overworld/world_map/sw_palette.bin   (256 B, 128 BGR555 colors)

Tile index $EF (239) is reserved as the outer ocean/cloud border tile to match
vanilla WorldMap_FillTilemapWithEF ($0ABDA5).
"""
from __future__ import annotations

import argparse
import hashlib
import math
from pathlib import Path
import struct
import sys

from PIL import Image, ImageDraw, ImageFilter

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "Scripts" / "Tools"))
sys.path.insert(0, str(REPO_ROOT / "Scripts" / "Build"))

import lyra_native_loaders as lnl  # noqa: E402
import scene_intent_common as sic  # noqa: E402

# Non-world slots masked with tasteful ocean/cloud mist so overlays, indoor
# rooms, and unlinked draft areas do not render as raw tiles on the World Map.
MASKED_SLOTS = frozenset({
    0x80,  # Tail Woods / Maku Tree (indoor/warp pocket)
    0x84, 0x85, 0x86,  # Unlinked Sky drafts
    0x88,  # Dark curtain indoor room
    0x93, 0x94, 0x95, 0x96, 0x97,  # Overlays
    0x9B,  # Reserved Fortress slot
    0x9C, 0x9D, 0x9E, 0x9F,  # Overlays
})

# Sky cloud-band slots (tinted with airy mist around their borders).
SKY_CLOUD_SLOTS = frozenset({0x84, 0x85, 0x86})
BORDER_TILE_IDX = 0xEF


def _load_oosow192_families(rom: bytes) -> dict[str, object] | None:
    desc_pc = sic.snes_to_pc(0x28F000)
    if desc_pc + 12 <= len(rom) and rom[desc_pc:desc_pc + 8] == b"OOSOW192":
        return {f.name: f for f in lnl.current_table_layout(lnl.TABLE_BASE)}
    return None


def _rd_u8(rom: bytes, families: dict[str, object] | None, name: str, idx: int, legacy_snes: int) -> int:
    if idx >= 0xA0 and families and name in families:
        return rom[sic.snes_to_pc(families[name].snes) + idx]
    return rom[sic.snes_to_pc(legacy_snes) + idx]


def _rd_u16(rom: bytes, families: dict[str, object] | None, name: str, idx: int, legacy_snes: int) -> int:
    if idx >= 0xA0 and families and name in families:
        pc = sic.snes_to_pc(families[name].snes) + idx * 2
    else:
        pc = sic.snes_to_pc(legacy_snes) + idx * 2
    return struct.unpack_from("<H", rom, pc)[0]


def _decode_map_grid(rom: bytes, area_id: int, map32_table: list[tuple[int, int, int, int]],
                     families: dict[str, object] | None) -> list[list[int]]:
    if area_id >= 0xA0 and families:
        hi_base = sic.snes_to_pc(families["map32_high"].snes)
        lo_base = sic.snes_to_pc(families["map32_low"].snes)
    else:
        hi_base = sic.PC_MAP32_PTR_HI
        lo_base = sic.PC_MAP32_PTR_LO
    p1 = sic.snes_to_pc(int.from_bytes(rom[hi_base + 3 * area_id:hi_base + 3 * area_id + 3], "little"))
    p2 = sic.snes_to_pc(int.from_bytes(rom[lo_base + 3 * area_id:lo_base + 3 * area_id + 3], "little"))
    lo, _ = sic.lz2_decompress(rom, p2, big_endian=True, max_output=512)
    hi, _ = sic.lz2_decompress(rom, p1, big_endian=True, max_output=512)
    grid = [[0] * 32 for _ in range(32)]
    for idx in range(min(256, len(lo), len(hi))):
        tid = (hi[idx] << 8) | lo[idx]
        if tid < len(map32_table):
            tl, tr, bl, br = map32_table[tid]
            x, y = idx % 16, idx // 16
            grid[y * 2][x * 2] = tl
            grid[y * 2][x * 2 + 1] = tr
            grid[y * 2 + 1][x * 2] = bl
            grid[y * 2 + 1][x * 2 + 1] = br
    return grid


def _decode_palette_128_special(rom: bytes, area_id: int, families: dict[str, object] | None) -> list[tuple[int, int, int]]:
    # Use authoritative resident 128-color CGRAM palette at $4D8100 when bound (flag bit 1)
    flags_pc = sic.snes_to_pc(0x4D8000)
    pals_pc = sic.snes_to_pc(0x4D8100)
    if (
        0x80 <= area_id < 0xC0
        and flags_pc + 0xC0 <= len(rom)
        and pals_pc + 64 * 256 <= len(rom)
        and (rom[flags_pc + area_id] & 0x02) != 0
    ):
        off = pals_pc + (area_id - 0x80) * 256
        pal128 = [sic.bgr555_to_rgb(struct.unpack_from("<H", rom, off + i * 2)[0]) for i in range(128)]
        bg_rgb = pal128[0]
        for r in range(8):
            pal128[r * 16] = bg_rgb
            pal128[r * 16 + 8] = bg_rgb
        return pal128

    parent = _rd_u8(rom, families, "parent", area_id, 0x288998)
    mp = _rd_u8(rom, families, "main_palette", parent, 0x288160)
    if mp == 0xFF:
        mp = 0
    ps = _rd_u8(rom, families, "palette_set", parent, 0x09C635)
    bg_word = _rd_u16(rom, families, "bg_color", parent, 0x288000)

    p1 = rom[sic.PC_PAL_GROUP + ps * 4 + 0]
    p2 = rom[sic.PC_PAL_GROUP + ps * 4 + 1]
    p3 = rom[sic.PC_PAL_GROUP + ps * 4 + 2]

    pal128: list[tuple[int, int, int]] = [sic.bgr555_to_rgb(bg_word)] * 128

    # Main OW palette (35 colors -> rows 2..6 cols 1..7, matching scene_intent_common)
    main_off = sic.PC_OW_MAIN_PAL + (mp % 6) * 70
    if main_off + 70 <= len(rom):
        for r in range(5):
            for c in range(7):
                w = struct.unpack_from("<H", rom, main_off + (r * 7 + c) * 2)[0]
                pal128[(r + 2) * 16 + 1 + c] = sic.bgr555_to_rgb(w)

    # Aux1 (21 colors -> rows 2..4 cols 9..15)
    aux1_off = sic.PC_OW_AUX_PAL + (p1 % 20) * 42
    if aux1_off + 42 <= len(rom):
        for r in range(3):
            for c in range(7):
                w = struct.unpack_from("<H", rom, aux1_off + (r * 7 + c) * 2)[0]
                pal128[(r + 2) * 16 + 9 + c] = sic.bgr555_to_rgb(w)

    # Aux2 (21 colors -> rows 5..7 cols 9..15)
    aux2_off = sic.PC_OW_AUX_PAL + (p2 % 20) * 42
    if aux2_off + 42 <= len(rom):
        for r in range(3):
            for c in range(7):
                w = struct.unpack_from("<H", rom, aux2_off + (r * 7 + c) * 2)[0]
                pal128[(r + 5) * 16 + 9 + c] = sic.bgr555_to_rgb(w)

    # Animated palette (7 colors -> row 7 cols 1..7)
    anim_off = sic.PC_OW_ANIM_PAL + (p3 % 14) * 14
    if anim_off + 14 <= len(rom):
        for c in range(7):
            w = struct.unpack_from("<H", rom, anim_off + c * 2)[0]
            pal128[7 * 16 + 1 + c] = sic.bgr555_to_rgb(w)

    # Fill transparent/backdrop slot 0 of every subpalette row with custom BG color
    bg_rgb = sic.bgr555_to_rgb(bg_word)
    for r in range(8):
        pal128[r * 16] = bg_rgb
        pal128[r * 16 + 8] = bg_rgb
    return pal128


def _load_slot_chars_special(rom: bytes, area_id: int, families: dict[str, object] | None,
                             sheet_cache: dict[int, list[tuple[int, ...]]]) -> dict[int, list[tuple[int, ...]]]:
    parent = _rd_u8(rom, families, "parent", area_id, 0x288998)
    if parent >= 0xA0 and families:
        gfx_pc = sic.snes_to_pc(families["gfx"].snes) + parent * 8
    else:
        gfx_pc = sic.snes_to_pc(0x288480) + parent * 8
    slots = list(rom[gfx_pc:gfx_pc + 8])
    anim = _rd_u8(rom, families, "animated", parent, 0x2882A0)

    needed = [s for s in set(slots) | {anim} if s != 0xFF and s not in sheet_cache]
    if needed:
        decoded = sic.decode_sheet_chars(rom, needed)
        sheet_cache.update(decoded)

    blank = (0,) * 64
    out: dict[int, list[tuple[int, ...]]] = {}
    for slot_idx, sid in enumerate(slots):
        base = list(sheet_cache.get(sid, [])) if sid != 0xFF else []
        while len(base) < 64:
            base.append(blank)
        if slot_idx == 7 and anim in sheet_cache:
            ac = sheet_cache[anim]
            for c in range(min(32, len(ac))):
                base[c] = ac[c]
        out[slot_idx] = base
    return out


def _render_screen_64x64(rom: bytes, area_id: int, t16: list[tuple[int, int, int, int]],
                         map32_table: list[tuple[int, int, int, int]],
                         families: dict[str, object] | None,
                         sheet_cache: dict[int, list[tuple[int, ...]]]) -> Image.Image:
    grid = _decode_map_grid(rom, area_id, map32_table, families)
    pal128 = _decode_palette_128_special(rom, area_id, families)
    slot_chars = _load_slot_chars_special(rom, area_id, families, sheet_cache)

    # Render directly at 2x2 px per Tile16 (64x64 per 512x512 screen) by
    # averaging each 8x8 Tile8 quadrant of every Tile16! Fast & crisp.
    img = Image.new("RGB", (64, 64))
    px = img.load()
    t16_rgb_cache: dict[int, tuple[tuple[int, int, int], ...]] = {}

    for ty in range(32):
        row = grid[ty]
        for tx in range(32):
            tid = row[tx]
            quads = t16_rgb_cache.get(tid)
            if quads is None:
                words = t16[tid] if tid < len(t16) else (0, 0, 0, 0)
                qcols = []
                for w in words:
                    ch_id = w & 0x3FF
                    pal_row = (w >> 10) & 7
                    slot = ch_id // 64
                    local_chr = ch_id % 64
                    ch = slot_chars.get(slot, [(0,) * 64] * 64)[local_chr]
                    pal8 = sic.palette8_for_subpal(pal128, pal_row, high_half=(slot in sic.HIGH_PALETTE_SLOTS))
                    sr = sg = sb = 0
                    for v in ch:
                        r, g, b = pal8[v & 7]
                        sr += r
                        sg += g
                        sb += b
                    qcols.append((sr >> 6, sg >> 6, sb >> 6))
                quads = tuple(qcols)
                t16_rgb_cache[tid] = quads
            px[tx * 2, ty * 2] = quads[0]
            px[tx * 2 + 1, ty * 2] = quads[1]
            px[tx * 2, ty * 2 + 1] = quads[2]
            px[tx * 2 + 1, ty * 2 + 1] = quads[3]
    return img


def _make_ocean_cloud_backdrop(sea_rgb: tuple[int, int, int]) -> Image.Image:
    """Create a 512x512 stylized ALTTP Mode 7 ocean backdrop matching Lyra Sea."""
    base_sea = sea_rgb
    mid_sea = (
        min(255, sea_rgb[0] + 10),
        min(255, sea_rgb[1] + 14),
        min(255, sea_rgb[2] + 16),
    )
    img = Image.new("RGB", (512, 512), base_sea)
    px = img.load()
    for y in range(512):
        for x in range(512):
            if ((x // 4 + (y // 4) * 3) & 7) == 0 and (y & 3) == 1:
                px[x, y] = mid_sea
    return img


def _draw_cloud_bank(canvas: Image.Image, mask_slots: frozenset[int], sea_rgb: tuple[int, int, int]) -> None:
    """Paint continuous, organic ALTTP-style billowing clouds over masked non-world regions."""
    cloud_layer = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    draw = ImageDraw.Draw(cloud_layer)

    # 1. Fill masked rectangles with matching ocean (or sky mist for Sky drafts $84-$86)
    for slot in sorted(mask_slots):
        r = (slot - 0x80) >> 3
        c = (slot - 0x80) & 7
        x0, y0 = c * 64, r * 64
        if slot in SKY_CLOUD_SLOTS:
            draw.rectangle([x0, y0, x0 + 63, y0 + 63], fill=(168, 208, 236, 255))
        else:
            draw.rectangle([x0, y0, x0 + 63, y0 + 63], fill=(*sea_rgb, 255))

    # 2. Paint cohesive multi-cell cloud banks (shadow -> mid -> bright highlight)
    def paint_bank(box: tuple[int, int, int, int], puffs: list[tuple[int, int, int, int]],
                   sh: tuple[int, int, int, int], mid: tuple[int, int, int, int], hi: tuple[int, int, int, int]) -> None:
        # Clipped softly inside box
        x0, y0, x1, y1 = box
        bank = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
        bd = ImageDraw.Draw(bank)
        for cx, cy, rx, ry in puffs:
            bd.ellipse([cx - rx, cy - ry + 5, cx + rx, cy + ry + 5], fill=sh)
        for cx, cy, rx, ry in puffs:
            bd.ellipse([cx - rx, cy - ry + 2, cx + rx, cy + ry + 2], fill=mid)
        for cx, cy, rx, ry in puffs:
            bd.ellipse([cx - int(rx * 0.88), cy - int(ry * 0.85), cx + int(rx * 0.88), cy + int(ry * 0.82)], fill=hi)
        # Keep bank cleanly inside its masked bounding region
        mask = Image.new("L", (512, 512), 0)
        ImageDraw.Draw(mask).rectangle([x0, y0, x1, y1], fill=255)
        mask = mask.filter(ImageFilter.GaussianBlur(radius=2.0))
        cloud_layer.paste(bank, (0, 0), mask)

    # NW cloud bank ($80 + $88: x=0..63, y=0..127)
    nw_puffs = [
        (22, 24, 24, 16), (42, 34, 22, 16), (18, 56, 24, 18),
        (40, 74, 24, 18), (20, 96, 24, 18), (42, 108, 22, 15),
    ]
    paint_bank((0, 0, 63, 127), nw_puffs,
               (108, 148, 192, 215), (168, 200, 224, 230), (216, 232, 244, 240))

    # Sky cloud ridge ($84-$86: x=256..447, y=0..63)
    sky_puffs = [
        (276, 36, 26, 20), (308, 26, 30, 22), (344, 34, 32, 22),
        (380, 24, 30, 22), (416, 34, 28, 20), (438, 26, 22, 18),
    ]
    paint_bank((256, 0, 447, 63), sky_puffs,
               (128, 176, 216, 235), (192, 224, 244, 245), (240, 248, 255, 255))

    # Central mist bank ($93-$97 + $9B-$9F: x=192..511, y=128..255)
    mid_puffs = [
        (222, 164, 32, 22), (262, 154, 38, 24), (308, 168, 42, 26),
        (356, 156, 40, 24), (404, 166, 42, 26), (452, 156, 38, 24), (486, 168, 28, 22),
        (234, 206, 36, 24), (284, 214, 42, 26), (336, 204, 44, 26),
        (388, 216, 42, 24), (436, 204, 40, 26), (478, 214, 32, 22),
        (264, 184, 46, 26), (342, 186, 52, 28), (426, 184, 48, 26),
    ]
    paint_bank((192, 128, 511, 255), mid_puffs,
               (96, 140, 192, 210), (160, 196, 224, 225), (212, 232, 244, 235))

    cloud_soft = cloud_layer.filter(ImageFilter.GaussianBlur(radius=1.0))
    canvas.paste(cloud_soft, (0, 0), cloud_soft)


def render_special_overworld_rgb(rom: bytes) -> tuple[Image.Image, tuple[int, int, int]]:
    t16 = sic.decode_tile16_table(rom)
    map32_table = sic.decode_map32_table(rom)
    families = _load_oosow192_families(rom)
    sheet_cache: dict[int, list[tuple[int, ...]]] = {}

    screens: dict[int, Image.Image] = {}
    for m in range(0x80, 0xC0):
        if m in MASKED_SLOTS:
            continue
        screens[m] = _render_screen_64x64(rom, m, t16, map32_table, families, sheet_cache)

    # Sample the actual dominant ocean RGB from open Lyra Sea ($A4 corners)
    sea_rgb = screens[0xA4].getpixel((4, 4)) if 0xA4 in screens else (48, 88, 160)

    canvas = _make_ocean_cloud_backdrop(sea_rgb)
    for m, screen in screens.items():
        r = (m - 0x80) >> 3
        c = (m - 0x80) & 7
        canvas.paste(screen, (c * 64, r * 64))

    _draw_cloud_bank(canvas, MASKED_SLOTS, sea_rgb)
    return canvas, sea_rgb


def _rgb_to_bgr555_word(rgb: tuple[int, int, int]) -> int:
    r = (rgb[0] >> 3) & 0x1F
    g = (rgb[1] >> 3) & 0x1F
    b = (rgb[2] >> 3) & 0x1F
    return r | (g << 5) | (b << 10)


def _bgr555_to_rgb888(word: int) -> tuple[int, int, int]:
    r = (word & 0x1F) << 3
    g = ((word >> 5) & 0x1F) << 3
    b = ((word >> 10) & 0x1F) << 3
    return (r | (r >> 5), g | (g >> 5), b | (b >> 5))


def quantize_to_mode7(img_rgb: Image.Image, sea_rgb: tuple[int, int, int]) -> tuple[bytes, bytes, bytes]:
    """Quantize a 512x512 RGB image to SNES Mode 7 (tileset, gfx, palette).

    - 128 BGR555 colors (index 0 = deep ocean backdrop, indices 1..127 = adaptive)
    - 256 8x8 8bpp tiles (slot $EF reserved for outer border fill)
    - 4,096-byte 4-quadrant Mode 7 tilemap matching DMAOwMap
    """
    assert img_rgb.size == (512, 512)

    # Quantize to 127 adaptive colors (reserving index 0 for deep sea backdrop)
    q_img = img_rgb.quantize(colors=127, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    raw_pal = q_img.getpalette()[:127 * 3]

    # Build 128-entry BGR555 palette (index 0 = deep sea backdrop)
    backdrop_word = _rgb_to_bgr555_word(sea_rgb)
    pal_words = [backdrop_word]
    for i in range(127):
        rgb = (raw_pal[i * 3], raw_pal[i * 3 + 1], raw_pal[i * 3 + 2])
        pal_words.append(_rgb_to_bgr555_word(rgb))
    pal_rgb = [_bgr555_to_rgb888(w) for w in pal_words]
    palette_bytes = b"".join(struct.pack("<H", w) for w in pal_words)
    assert len(palette_bytes) == 256

    # Remap pixel indices by +1 so all image pixels use palette indices 1..127
    idx_grid = [v + 1 for v in q_img.tobytes()]

    # Extract 64x64 = 4,096 8x8 tiles
    tiles_idx: list[bytes] = []
    tiles_vec: list[tuple[int, ...]] = []
    for ty in range(64):
        for tx in range(64):
            t_bytes = bytearray(64)
            # Downsampled 2x2 block average RGB vector (12 ints) for fast perceptual clustering
            vec = []
            for py in range(8):
                row_off = (ty * 8 + py) * 512 + tx * 8
                t_bytes[py * 8:py * 8 + 8] = idx_grid[row_off:row_off + 8]
            for by in range(0, 8, 4):
                for bx in range(0, 8, 4):
                    sr = sg = sb = 0
                    for dy in range(4):
                        for dx in range(4):
                            r, g, b = pal_rgb[t_bytes[(by + dy) * 8 + bx + dx]]
                            sr += r
                            sg += g
                            sb += b
                    vec.extend((sr >> 4, sg >> 4, sb >> 4))
            tiles_idx.append(bytes(t_bytes))
            tiles_vec.append(tuple(vec))

    # Build border tile $EF (deep sea with gentle subtle wave matching backdrop)
    # Pick closest palette indices for deep sea & subtle highlight
    def closest_idx(target: tuple[int, int, int]) -> int:
        best_i, best_d = 1, 10**9
        for i in range(1, 128):
            r, g, b = pal_rgb[i]
            d = (r - target[0]) ** 2 + (g - target[1]) ** 2 + (b - target[2]) ** 2
            if d < best_d:
                best_i, best_d = i, d
        return best_i

    sea_i = closest_idx(sea_rgb)
    wave_i = closest_idx((min(255, sea_rgb[0] + 10), min(255, sea_rgb[1] + 14), min(255, sea_rgb[2] + 16)))
    border_tile = bytearray([sea_i] * 64)
    border_tile[1 * 8 + 2] = wave_i
    border_tile[1 * 8 + 3] = wave_i
    border_tile[5 * 8 + 6] = wave_i
    border_tile[5 * 8 + 7] = wave_i
    border_tile_bytes = bytes(border_tile)

    # Deduplicate exact 8x8 tiles first
    unique_map: dict[bytes, int] = {}
    unique_tiles: list[bytes] = []
    unique_vecs: list[tuple[int, ...]] = []
    unique_counts: list[int] = []
    tile_to_uid: list[int] = []

    for tb, tv in zip(tiles_idx, tiles_vec):
        uid = unique_map.get(tb)
        if uid is None:
            uid = len(unique_tiles)
            unique_map[tb] = uid
            unique_tiles.append(tb)
            unique_vecs.append(tv)
            unique_counts.append(1)
        else:
            unique_counts[uid] += 1
        tile_to_uid.append(uid)

    # Cluster unique tiles down to 255 representatives (reserving slot $EF)
    max_reps = 255
    if len(unique_tiles) <= max_reps:
        reps = list(range(len(unique_tiles)))
        uid_to_rep = {u: u for u in range(len(unique_tiles))}
    else:
        # Deterministic farthest-point seeding + 4 Lloyd/medoid iterations on 4-quadrant RGB vectors
        # Start with the most frequent tile (ocean) so ocean is preserved cleanly.
        first_rep = max(range(len(unique_tiles)), key=lambda u: unique_counts[u])
        reps = [first_rep]
        min_dists = [0] * len(unique_tiles)

        def vec_dist(a: tuple[int, ...], b: tuple[int, ...]) -> int:
            return sum((x - y) * (x - y) for x, y in zip(a, b))

        v0 = unique_vecs[first_rep]
        for u in range(len(unique_tiles)):
            min_dists[u] = vec_dist(unique_vecs[u], v0)

        # Also boost weight slightly by log(count) so common structural tiles aren't ignored
        for _ in range(max_reps - 1):
            best_u = max(range(len(unique_tiles)), key=lambda u: min_dists[u])
            reps.append(best_u)
            vb = unique_vecs[best_u]
            for u in range(len(unique_tiles)):
                d = vec_dist(unique_vecs[u], vb)
                if d < min_dists[u]:
                    min_dists[u] = d

        # Assign every unique tile to its closest representative, then refine medoids
        uid_to_rep: dict[int, int] = {}
        rep_vecs = [unique_vecs[r] for r in reps]
        for _it in range(3):
            clusters: list[list[int]] = [[] for _ in range(max_reps)]
            for u, uv in enumerate(unique_vecs):
                best_r = 0
                best_d = vec_dist(uv, rep_vecs[0])
                for ri in range(1, max_reps):
                    d = vec_dist(uv, rep_vecs[ri])
                    if d < best_d:
                        best_d = d
                        best_r = ri
                uid_to_rep[u] = best_r
                clusters[best_r].append(u)

            # Update each cluster center to the weighted-closest real tile (medoid)
            for ri, members in enumerate(clusters):
                if not members:
                    continue
                tot = sum(unique_counts[u] for u in members)
                mean = tuple(
                    sum(unique_vecs[u][k] * unique_counts[u] for u in members) // tot
                    for k in range(12)
                )
                medoid = min(members, key=lambda u: vec_dist(unique_vecs[u], mean))
                reps[ri] = medoid
                rep_vecs[ri] = unique_vecs[medoid]

        # Final assignment using exact 64-pixel RGB MSE against the 255 rep tiles
        rep_px_rgb = [[pal_rgb[b] for b in unique_tiles[r]] for r in reps]
        for u, tb in enumerate(unique_tiles):
            # Narrow candidates to top-12 by coarse vector distance for speed
            uv = unique_vecs[u]
            cands = sorted(range(max_reps), key=lambda ri: vec_dist(uv, rep_vecs[ri]))[:12]
            t_rgb = [pal_rgb[b] for b in tb]
            best_ri = cands[0]
            best_err = 10**12
            for ri in cands:
                rrgb = rep_px_rgb[ri]
                err = 0
                for (r1, g1, b1), (r2, g2, b2) in zip(t_rgb, rrgb):
                    err += (r1 - r2) ** 2 + (g1 - g2) ** 2 + (b1 - b2) ** 2
                    if err >= best_err:
                        break
                if err < best_err:
                    best_err = err
                    best_ri = ri
            uid_to_rep[u] = best_ri

    # Assign hardware Mode 7 tile indices 0..255, reserving BORDER_TILE_IDX ($EF)
    hw_slots = [i for i in range(256) if i != BORDER_TILE_IDX]
    gfx_tiles: list[bytes] = [border_tile_bytes] * 256
    rep_to_hw: dict[int, int] = {}
    for ri, rep_uid in enumerate(reps):
        hw = hw_slots[ri]
        gfx_tiles[hw] = unique_tiles[rep_uid]
        rep_to_hw[ri] = hw
    gfx_tiles[BORDER_TILE_IDX] = border_tile_bytes

    gfx_bytes = b"".join(gfx_tiles)
    assert len(gfx_bytes) == 16384
    assert max(gfx_bytes) < 128

    # Build 64x64 grid of hardware tile indices
    hw_grid = [rep_to_hw[uid_to_rep[uid]] for uid in tile_to_uid]

    # Pack into 4 quadrants of 32x32 tiles matching DMAOwMap (.vram_offset: $0000, $0020, $1000, $1020)
    tileset = bytearray(4096)
    pos = 0
    for qy in (0, 32):
        for qx in (0, 32):
            for row in range(32):
                src_off = (qy + row) * 64 + qx
                tileset[pos:pos + 32] = hw_grid[src_off:src_off + 32]
                pos += 32
    assert pos == 4096
    return bytes(tileset), gfx_bytes, palette_bytes


def render_preview_from_mode7(tileset: bytes, gfx: bytes, palette: bytes) -> Image.Image:
    """Reconstruct exact 512x512 RGB preview straight from the SNES Mode 7 binaries."""
    pal_rgb = [_bgr555_to_rgb888(struct.unpack_from("<H", palette, i * 2)[0]) for i in range(128)]
    img = Image.new("RGB", (512, 512))
    px = img.load()
    q_origins = ((0, 0), (32, 0), (0, 32), (32, 32))
    for q_idx, (qx, qy) in enumerate(q_origins):
        q_off = q_idx * 1024
        for row in range(32):
            for col in range(32):
                tid = tileset[q_off + row * 32 + col]
                t_off = tid * 64
                bx, by = (qx + col) * 8, (qy + row) * 8
                for py in range(8):
                    for px_i in range(8):
                        ci = gfx[t_off + py * 8 + px_i]
                        px[bx + px_i, by + py] = pal_rgb[ci & 0x7F]
    return img


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument(
        "--rom",
        type=Path,
        default=Path("/Users/scawful/Zelda/Projects/Oracle-of-Secrets/Oracle-of-Secrets.yazeproj/rom"),
        help="Read-only base ROM path",
    )
    ap.add_argument(
        "--out-dir",
        type=Path,
        default=REPO_ROOT / "Overworld" / "world_map",
        help="Output directory for SwMapTileset.bin, SwMapGfx.bin, sw_palette.bin",
    )
    ap.add_argument(
        "--preview",
        type=Path,
        default=None,
        help="Optional PNG preview rendered straight from the generated Mode 7 binaries",
    )
    args = ap.parse_args()

    rom = args.rom.read_bytes()
    img_rgb, sea_rgb = render_special_overworld_rgb(rom)
    tileset, gfx, palette = quantize_to_mode7(img_rgb, sea_rgb)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "SwMapTileset.bin").write_bytes(tileset)
    (args.out_dir / "SwMapGfx.bin").write_bytes(gfx)
    (args.out_dir / "sw_palette.bin").write_bytes(palette)

    if args.preview is not None:
        args.preview.parent.mkdir(parents=True, exist_ok=True)
        preview = render_preview_from_mode7(tileset, gfx, palette)
        preview.save(args.preview)

    print(
        f"Generated Mode 7 Special Overworld map from {args.rom}:\n"
        f"  SwMapTileset.bin: {len(tileset)} B (sha256={hashlib.sha256(tileset).hexdigest()[:16]})\n"
        f"  SwMapGfx.bin:     {len(gfx)} B (sha256={hashlib.sha256(gfx).hexdigest()[:16]})\n"
        f"  sw_palette.bin:   {len(palette)} B (sha256={hashlib.sha256(palette).hexdigest()[:16]})"
    )
    if args.preview is not None:
        print(f"  preview PNG:      {args.preview}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
