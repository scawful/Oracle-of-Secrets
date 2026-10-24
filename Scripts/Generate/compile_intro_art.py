#!/usr/bin/env python3
"""Compile an approved illustration into a centered SNES 4bpp intro panel.

Requires Pillow. The original PNG is retained with the generated assets.
Example:
  python3 Scripts/Generate/compile_intro_art.py --input approved.png \
      --output-dir Core/Cutscene/Assets/link_hyrule_intro --preview preview.png
Repeat with --check to compare every output without writing any files.
"""

import argparse
import hashlib
import io
import json
from pathlib import Path
import struct
import sys

from PIL import Image, ImageOps, __version__ as PILLOW_VERSION


PANEL_WIDTH, PANEL_HEIGHT = 240, 136
SCREEN_WIDTH, SCREEN_HEIGHT = 256, 224
MAP_WIDTH, MAP_HEIGHT = 32, 32
PANEL_TILE_X, PANEL_TILE_Y = 1, 5
ASSET_NAME = "link_hyrule_intro"
SOURCE_NAME = "approved_source.png"


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def encode_tile(pixels):
    """Encode 64 indices, left pixel in bit 7, in SNES plane-pair order."""
    encoded = bytearray(32)
    for y in range(8):
        for x in range(8):
            value = pixels[y * 8 + x]
            for plane in range(4):
                offset = (plane // 2) * 16 + y * 2 + plane % 2
                encoded[offset] |= ((value >> plane) & 1) << (7 - x)
    return bytes(encoded)


def decode_tile(encoded):
    """Decode one SNES tile independently of the encoder's write loop."""
    pixels = []
    for y in range(8):
        planes = (encoded[y * 2], encoded[y * 2 + 1],
                  encoded[y * 2 + 16], encoded[y * 2 + 17])
        for bit in range(7, -1, -1):
            pixels.append(sum(((row >> bit) & 1) << plane
                              for plane, row in enumerate(planes)))
    return bytes(pixels)


def check_bitplanes():
    # Known plane bytes exercise every index, including the fourth bitplane.
    pixels = bytes(list(range(8)) + list(range(8, 16)) + [0] * 48)
    expected = bytes([0x55, 0x33, 0x55, 0x33] + [0] * 12
                     + [0x0F, 0, 0x0F, 0xFF] + [0] * 12)
    if encode_tile(pixels) != expected or decode_tile(expected) != pixels:
        raise ValueError("SNES 4bpp known-pattern check failed")


def rgb555(rgb):
    r, g, b = ((channel * 31 + 127) // 255 for channel in rgb)
    return r | (g << 5) | (b << 10)


def rgb888(word):
    channels = ((word >> shift) & 31 for shift in (0, 5, 10))
    return tuple((channel << 3) | (channel >> 2) for channel in channels)


def compile_assets(source_data):
    check_bitplanes()
    with Image.open(io.BytesIO(source_data)) as source:
        if source.format != "PNG":
            raise ValueError("input must be a PNG")
        source_size = source.size
        if source.convert("RGBA").getchannel("A").getextrema() != (255, 255):
            raise ValueError("input must be fully opaque")
        # Preserve proportions with a small centered crop to the tile-aligned
        # panel. Its 510 cells plus blank tile 0 fit below the VRAM budget.
        resized = ImageOps.fit(source.convert("RGB"),
                               (PANEL_WIDTH, PANEL_HEIGHT),
                               method=Image.Resampling.LANCZOS,
                               centering=(0.5, 0.5))
    quantized = resized.quantize(colors=15, method=Image.Quantize.MEDIANCUT,
                                 dither=Image.Dither.NONE)
    palette = quantized.getpalette()
    used_indices = sorted(set(quantized.tobytes()))
    old_to_word = {index: rgb555(palette[index * 3:index * 3 + 3])
                   for index in used_indices}
    # Canonicalize after RGB555 rounding, which may merge palette colors.
    opaque_words = sorted(set(old_to_word.values()))
    word_to_index = {word: index + 1 for index, word in enumerate(opaque_words)}
    panel = bytes(word_to_index[old_to_word[index]]
                  for index in quantized.tobytes())
    palette_words = [0] + opaque_words + [0] * (15 - len(opaque_words))
    palette_data = struct.pack("<16H", *palette_words)

    tiles = [bytes(32)]
    tile_indices = {tiles[0]: 0}
    tilemap = [0] * (MAP_WIDTH * MAP_HEIGHT)
    for tile_y in range(PANEL_HEIGHT // 8):
        for tile_x in range(PANEL_WIDTH // 8):
            pixels = bytes(panel[y * PANEL_WIDTH + x]
                           for y in range(tile_y * 8, tile_y * 8 + 8)
                           for x in range(tile_x * 8, tile_x * 8 + 8))
            tile = encode_tile(pixels)
            if tile not in tile_indices:
                tile_indices[tile] = len(tiles)
                tiles.append(tile)
            tilemap[(PANEL_TILE_Y + tile_y) * MAP_WIDTH + PANEL_TILE_X + tile_x] = tile_indices[tile]
    if len(tiles) > 512:
        raise ValueError("tile count exceeds the 512-tile VRAM budget")
    tile_data = b"".join(tiles)
    map_data = struct.pack("<1024H", *tilemap)

    # Read back the encoded bytes, including blank screen rows and map layout.
    decoded = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    decoded_tiles = [decode_tile(tile_data[offset:offset + 32])
                     for offset in range(0, len(tile_data), 32)]
    for cell, (word,) in enumerate(struct.iter_unpack("<H", map_data)):
        if word & ~0x03FF:
            raise ValueError("tilemap unexpectedly sets palette/priority/flip bits")
        tile_x, tile_y = cell % MAP_WIDTH, cell // MAP_WIDTH
        if tile_y >= SCREEN_HEIGHT // 8:
            continue
        tile = decoded_tiles[word]
        for y in range(8):
            start = (tile_y * 8 + y) * SCREEN_WIDTH + tile_x * 8
            decoded[start:start + 8] = tile[y * 8:y * 8 + 8]
    expected = bytearray(SCREEN_WIDTH * SCREEN_HEIGHT)
    for y in range(PANEL_HEIGHT):
        start = (PANEL_TILE_Y * 8 + y) * SCREEN_WIDTH + PANEL_TILE_X * 8
        expected[start:start + PANEL_WIDTH] = panel[y * PANEL_WIDTH:(y + 1) * PANEL_WIDTH]
    if bytes(decoded) != expected:
        raise ValueError("encoded tiles/map do not reproduce the quantized pixels")
    if not all(1 <= index <= 15 for index in panel):
        raise ValueError("opaque panel uses the reserved transparent palette index")

    decoded_palette = [rgb888(word) for (word,) in struct.iter_unpack("<H", palette_data)]
    preview = Image.new("RGB", (SCREEN_WIDTH, SCREEN_HEIGHT))
    preview.putdata([decoded_palette[index] for index in decoded])
    preview_buffer = io.BytesIO()
    preview.save(preview_buffer, format="PNG", optimize=False, compress_level=9)
    preview_data = preview_buffer.getvalue()

    files = {SOURCE_NAME: source_data, ASSET_NAME + ".bin": tile_data,
             ASSET_NAME + ".pal": palette_data, ASSET_NAME + ".map": map_data}
    manifest = {
        "schema_version": 1,
        "compiler": "Scripts/Generate/compile_intro_art.py",
        "compiler_sha256": sha256(Path(__file__).read_bytes()),
        "pillow_version": PILLOW_VERSION,
        "source": {"file": SOURCE_NAME, "width": source_size[0],
                   "height": source_size[1], "sha256": sha256(source_data)},
        "conversion": {"resize": "centered fit, LANCZOS, 240x136 tile-aligned panel",
                       "quantize": "15-color MEDIANCUT, no dithering",
                       "palette": "RGB555 rounded to nearest, canonical numeric order",
                       "transparent_index": 0, "opaque_indices": [1, len(opaque_words)]},
        "layout": {"screen_pixels": [SCREEN_WIDTH, SCREEN_HEIGHT],
                   "panel_pixels": [PANEL_WIDTH, PANEL_HEIGHT],
                   "panel_tile_origin": [PANEL_TILE_X, PANEL_TILE_Y],
                   "tilemap_tiles": [MAP_WIDTH, MAP_HEIGHT],
                   "tile_vram_word_address": 0x0000,
                   "bg1_map_vram_word_address": 0x6000,
                   "palette_number": 0, "blank_tile_index": 0,
                   "max_tiles": 512,
                   "tile_format": "SNES planar 4bpp",
                   "map_format": "little-endian 16-bit local tile indices; no flags"},
        "counts": {"palette_entries": 16, "opaque_colors": len(opaque_words),
                   "tiles_including_blank": len(tiles),
                   "panel_tile_cells": (PANEL_WIDTH // 8) * (PANEL_HEIGHT // 8)},
        "selfcheck": {"known_bitplane_pattern": "PASS",
                      "decoded_indices_equal_quantized": "PASS",
                      "decoded_visible_indices_sha256": sha256(bytes(decoded)),
                      "preview_rgb_sha256": sha256(preview.tobytes())},
        "preview": {"sha256": sha256(preview_data), "bytes": len(preview_data)},
        "files": {name: {"sha256": sha256(data), "bytes": len(data)}
                  for name, data in files.items()},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode()
    return files, preview_data, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--input", required=True, type=Path, help="approved opaque source PNG")
    parser.add_argument("--output-dir", required=True, type=Path, help="native asset directory")
    parser.add_argument("--preview", type=Path, help="optional decoded 256x224 PNG")
    parser.add_argument("--check", action="store_true", help="compare outputs; do not write files")
    args = parser.parse_args()
    try:
        files, preview, manifest = compile_assets(args.input.read_bytes())
        outputs = {args.output_dir / name: data for name, data in files.items()}
        if args.preview:
            preview_path = args.preview.resolve()
            if preview_path == args.input.resolve() or any(
                    preview_path == path.resolve() for path in outputs):
                raise ValueError("preview path must be separate from input and native assets")
            outputs[args.preview] = preview
        if args.check:
            stale = [str(path) for path, data in outputs.items()
                     if not path.is_file() or path.read_bytes() != data]
            if stale:
                raise ValueError("missing or stale output: " + ", ".join(stale))
        else:
            for path, data in outputs.items():
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(data)
    except (OSError, ValueError) as error:
        parser.exit(1, f"{parser.prog}: {error}\n")
    print(json.dumps({"result": "PASS", "mode": "check" if args.check else "write",
                      "counts": manifest["counts"],
                      "selfcheck": manifest["selfcheck"],
                      "output_dir": str(args.output_dir)}, sort_keys=True))


if __name__ == "__main__":
    main()
