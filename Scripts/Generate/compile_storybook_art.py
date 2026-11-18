#!/usr/bin/env python3
"""Compile the 4 QUEUE298 Intro Scene 0 storybook panels into SNES 4bpp LC-LZ2 assets.

Inputs:
  Data/graphics/storybook/panel_{0..3}.png  (168x48, <= 15 BGR555 colors; opaque)

Generated outputs under Core/Cutscene/storybook/:
  panel_{0..3}_chr.lz2   LC-LZ2 compressed 4bpp tiles (Tile 0 reserved blank)
  panel_{0..3}_map.lz2   LC-LZ2 compressed 32x32 BG1 tilemap (pal row 6, $1800)
  panel_{0..3}_pal.bin   32-byte BGR555 palette (index 0 = $0000, colors 1..15)
  storybook_data.asm     Asar incbin + size/pointer tables

Usage:
  python3 Scripts/Generate/compile_storybook_art.py [--check]
"""
from __future__ import annotations

import argparse
from pathlib import Path
import struct
import sys

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SRC_DIR = ROOT / 'Data/graphics/storybook'
OUT_DIR = ROOT / 'Core/Cutscene/storybook'

GEN_DIR = Path(__file__).resolve().parent
if str(GEN_DIR) not in sys.path:
    sys.path.insert(0, str(GEN_DIR))
import lz2  # noqa: E402

PANEL_COUNT = 4
PANEL_W = 168
PANEL_H = 48
TILES_X = PANEL_W // 8       # 21
TILES_Y = PANEL_H // 8       # 6
MAP_ORIGIN_X = 5             # X=40..207 centered inside X=24..224 parchment box (aligns w/ text & .table_b shadow)
MAP_ORIGIN_Y = 8             # row 8 (bgY=64) -> screen Y=67..114 with BG1VOFS=-4 ($FFFC), over .table_b Y=72..119
MAX_TILES = 127              # Tile 0 reserved blank + <= 126 panel tiles (<= 4,064 B raw CHR)
PALETTE_ATTR = 6 << 10       # $1800 -> CGRAM row 6 ($60..$6F / $7EC3C0..$7EC3DE)
TILEMAP_BYTES = 32 * 32 * 2  # 2048 bytes


def rgb_to_bgr555(rgb: tuple[int, int, int]) -> int:
    r5, g5, b5 = (c >> 3 for c in rgb)
    return r5 | (g5 << 5) | (b5 << 10)


def encode_tile_4bpp(pixels: tuple[int, ...] | list[int]) -> bytes:
    """Encode 64 palette indices (0..15) in row-major order into 32 SNES 4bpp bytes."""
    if len(pixels) != 64:
        raise ValueError(f'expected 64 pixels per tile, got {len(pixels)}')
    out = bytearray(32)
    for y in range(8):
        for x in range(8):
            c = pixels[y * 8 + x]
            if not 0 <= c <= 15:
                raise ValueError(f'pixel index out of 4bpp range: {c}')
            bit = 7 - x
            if c & 1:
                out[y * 2] |= 1 << bit
            if c & 2:
                out[y * 2 + 1] |= 1 << bit
            if c & 4:
                out[16 + y * 2] |= 1 << bit
            if c & 8:
                out[17 + y * 2] |= 1 << bit
    return bytes(out)


def decode_tile_4bpp(data: bytes) -> list[int]:
    """Decode one 32-byte SNES 4bpp tile back to 64 palette indices."""
    if len(data) != 32:
        raise ValueError(f'expected 32 bytes per 4bpp tile, got {len(data)}')
    pixels = [0] * 64
    for y in range(8):
        p0, p1 = data[y * 2], data[y * 2 + 1]
        p2, p3 = data[16 + y * 2], data[17 + y * 2]
        for x in range(8):
            bit = 7 - x
            pixels[y * 8 + x] = (
                ((p0 >> bit) & 1)
                | (((p1 >> bit) & 1) << 1)
                | (((p2 >> bit) & 1) << 2)
                | (((p3 >> bit) & 1) << 3)
            )
    return pixels


def tile_flips(tile: tuple[int, ...]) -> list[tuple[int, ...]]:
    """Return [none, H-flip, V-flip, HV-flip] 8x8 pixel tuples."""
    rows = [tile[y * 8:(y + 1) * 8] for y in range(8)]
    h = tuple(v for row in rows for v in row[::-1])
    v = tuple(v for row in rows[::-1] for v in row)
    hv = tuple(v for row in rows[::-1] for v in row[::-1])
    return [tile, h, v, hv]


def compile_panel(png_path: Path) -> dict:
    """Compile one 168x48 PNG into compressed CHR, compressed 32x32 map, and 32B palette."""
    with Image.open(png_path) as raw_im:
        if raw_im.size != (PANEL_W, PANEL_H):
            raise ValueError(
                f'{png_path.name}: expected {PANEL_W}x{PANEL_H}, got {raw_im.size}'
            )
        if 'A' in raw_im.getbands():
            alpha = raw_im.getchannel('A')
            lo, hi = alpha.getextrema()
            if lo != 255 or hi != 255:
                raise ValueError(f'{png_path.name}: alpha must be fully opaque, got extrema {(lo, hi)}')
        rgb_im = raw_im.convert('RGB')

    raw_rgb = rgb_im.tobytes()
    px_rgb = [(raw_rgb[i], raw_rgb[i + 1], raw_rgb[i + 2]) for i in range(0, len(raw_rgb), 3)]
    bgr_values = [rgb_to_bgr555(rgb) for rgb in px_rgb]

    # Sort unique colors deterministically by luminance then BGR555 code; slot 0 stays $0000 transparent.
    unique_bgr = sorted(
        set(bgr_values),
        key=lambda c: (((c & 0x1F) * 299 + ((c >> 5) & 0x1F) * 587 + ((c >> 10) & 0x1F) * 114), c),
    )
    if not 1 <= len(unique_bgr) <= 15:
        raise ValueError(
            f'{png_path.name}: expected 1..15 distinct BGR555 colors, got {len(unique_bgr)}'
        )

    color_to_idx = {bgr: idx + 1 for idx, bgr in enumerate(unique_bgr)}
    pal_words = [0] + unique_bgr + [0] * (15 - len(unique_bgr))
    pal_bytes = struct.pack('<16H', *pal_words)

    grid = [
        [color_to_idx[bgr_values[y * PANEL_W + x]] for x in range(PANEL_W)]
        for y in range(PANEL_H)
    ]

    # Tile 0 is reserved all-zeros so borders outside the 21x6 panel are transparent (index 0).
    blank_tile = (0,) * 64
    tiles: list[tuple[int, ...]] = [blank_tile]
    canon_to_id: dict[tuple[int, ...], int] = {}

    tilemap = [PALETTE_ATTR] * (32 * 32)
    flip_attrs = (0x0000, 0x4000, 0x8000, 0xC000)

    for ty in range(TILES_Y):
        for tx in range(TILES_X):
            tile = tuple(
                grid[ty * 8 + py][tx * 8 + px]
                for py in range(8)
                for px in range(8)
            )
            variants = tile_flips(tile)
            canon = min(variants)
            flip_kind = variants.index(canon)
            if canon not in canon_to_id:
                canon_to_id[canon] = len(tiles)
                tiles.append(canon)
            tile_id = canon_to_id[canon]
            map_idx = (MAP_ORIGIN_Y + ty) * 32 + (MAP_ORIGIN_X + tx)
            tilemap[map_idx] = PALETTE_ATTR | flip_attrs[flip_kind] | tile_id

    if len(tiles) > MAX_TILES:
        raise ValueError(
            f'{png_path.name}: {len(tiles)} unique tiles exceeds MAX_TILES={MAX_TILES}'
        )

    raw_chr_parts = []
    for t in tiles:
        enc = encode_tile_4bpp(t)
        if decode_tile_4bpp(enc) != list(t):
            raise RuntimeError(f'{png_path.name}: 4bpp round-trip mismatch')
        raw_chr_parts.append(enc)
    chr_raw = b''.join(raw_chr_parts)
    map_raw = struct.pack('<1024H', *tilemap)
    assert len(map_raw) == TILEMAP_BYTES

    chr_lz2 = lz2.compress(chr_raw)
    map_lz2 = lz2.compress(map_raw)

    de_chr, _ = lz2.decompress(chr_lz2, max_output=len(chr_raw) + 64)
    de_map, _ = lz2.decompress(map_lz2, max_output=TILEMAP_BYTES + 64)
    if de_chr != chr_raw or de_map != map_raw:
        raise RuntimeError(f'{png_path.name}: LZ2 round-trip verification failed')

    return {
        'colors': len(unique_bgr),
        'tiles': len(tiles),
        'chr_raw_len': len(chr_raw),
        'chr_lz2': chr_lz2,
        'map_lz2': map_lz2,
        'pal_bytes': pal_bytes,
    }


def render_data_asm(panels: list[dict]) -> str:
    lines = [
        '; Generated by Scripts/Generate/compile_storybook_art.py; do not edit.',
        '',
        'Storybook_ChrPointers:',
    ]
    for i in range(len(panels)):
        lines.append(f'  dl Storybook_Panel{i}_Chr')
    lines += ['', 'Storybook_MapPointers:']
    for i in range(len(panels)):
        lines.append(f'  dl Storybook_Panel{i}_Map')
    lines += ['', 'Storybook_PalPointers:']
    for i in range(len(panels)):
        lines.append(f'  dl Storybook_Panel{i}_Pal')
    lines += ['', 'Storybook_ChrSizes:']
    for i, p in enumerate(panels):
        lines.append(f'  dw ${p["chr_raw_len"]:04X} ; panel {i}: {p["tiles"]} tiles ({p["colors"]} colors)')
    lines += ['', 'Storybook_Palettes: ; contiguous 4x32B (128B) for zero-DP NMI row-6 copy']
    for i in range(len(panels)):
        lines.append(f'Storybook_Panel{i}_Pal: ; 32 B')
        lines.append(f'  incbin "Core/Cutscene/storybook/panel_{i}_pal.bin"')
    lines.append('')
    for i, p in enumerate(panels):
        lines.append(f'Storybook_Panel{i}_Chr: ; {len(p["chr_lz2"])} B LZ2 -> {p["chr_raw_len"]} B ({p["tiles"]} tiles)')
        lines.append(f'  incbin "Core/Cutscene/storybook/panel_{i}_chr.lz2"')
        lines.append(f'Storybook_Panel{i}_Map: ; {len(p["map_lz2"])} B LZ2 -> 2048 B')
        lines.append(f'  incbin "Core/Cutscene/storybook/panel_{i}_map.lz2"')
    lines.append('')
    return '\n'.join(lines)


def build(src_dir: Path = SRC_DIR, out_dir: Path = OUT_DIR, check: bool = False) -> list[dict]:
    panels = []
    expected: dict[Path, bytes] = {}
    for i in range(PANEL_COUNT):
        src_path = src_dir / f'panel_{i}.png'
        if not src_path.is_file():
            raise FileNotFoundError(f'missing source panel: {src_path}')
        info = compile_panel(src_path)
        panels.append(info)
        expected[out_dir / f'panel_{i}_chr.lz2'] = info['chr_lz2']
        expected[out_dir / f'panel_{i}_map.lz2'] = info['map_lz2']
        expected[out_dir / f'panel_{i}_pal.bin'] = info['pal_bytes']

    expected[out_dir / 'storybook_data.asm'] = render_data_asm(panels).encode('utf-8')

    if check:
        stale = [
            str(path)
            for path, want in expected.items()
            if not path.is_file() or path.read_bytes() != want
        ]
        if stale:
            raise ValueError('stale/missing generated storybook files: ' + ', '.join(stale))
    else:
        out_dir.mkdir(parents=True, exist_ok=True)
        for path, data in expected.items():
            path.write_bytes(data)

    return panels


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument('--check', action='store_true', help='verify generated files match sources')
    args = parser.parse_args(argv)

    try:
        panels = build(check=args.check)
    except (FileNotFoundError, ValueError, RuntimeError) as exc:
        print(f'ERROR: {exc}', file=sys.stderr)
        return 1

    total = 0
    for i, p in enumerate(panels):
        sz = len(p['chr_lz2']) + len(p['map_lz2']) + len(p['pal_bytes'])
        total += sz
        print(
            f'panel_{i}: {p["colors"]} colors, {p["tiles"]}/{MAX_TILES} tiles '
            f'(chr_raw={p["chr_raw_len"]}B), chr_lz2={len(p["chr_lz2"])}B, '
            f'map_lz2={len(p["map_lz2"])}B, pal=32B, total={sz}B'
        )
    print(f'total payload={total}B (+ 44B pointer/size tables = {total + 44}B)')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
