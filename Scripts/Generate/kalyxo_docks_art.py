#!/usr/bin/env python3
"""Compile the hand-authored Kalyxo docks index matrices. No ROM access.

The source is Data/graphics/kalyxo_docks/source.json. Each stable logical cell
is 16x16 pixels. Indices 0..7 fit both SNES 3bpp and 4bpp (plane 3 is clear).
The atlas uses eight cells per row; sheet_N.3bpp is a native 128x32 sheet.
Neither logical cell IDs nor library subtile indices allocate game slots.
"""
import argparse
import hashlib
import io
import json
from pathlib import Path
import struct

from sheet_codec import grid_to_sheet, sheet_to_grid


ROOT = Path(__file__).resolve().parents[2] / "Data/graphics/kalyxo_docks"


def load_source(path):
    source = json.loads(path.read_text())
    if source.get("schema_version") != 1 or source.get("cell_size") != 16 or source.get("atlas_columns") != 8:
        raise ValueError("source must use schema 1, 16x16 cells and eight atlas columns")
    palette = source["palette"]
    if len(palette) != 8:
        raise ValueError("need exactly eight palette entries")
    for entry in palette:
        rgb = entry["rgb"]
        if len(rgb) != 3 or any(type(v) is not int or v < 0 or v > 248 or v % 8 for v in rgb):
            raise ValueError("palette must use exact RGB5 channels, 0..248 in steps of 8")
    tiles = source["tiles"]
    names = set()
    for index, tile in enumerate(tiles):
        if type(tile["id"]) is not int or tile["id"] != index or tile["name"] in names:
            raise ValueError("cell IDs must be contiguous and names unique")
        names.add(tile["name"])
        rows = tile["pixels"]
        if len(rows) != 16 or any(len(row) != 16 or set(row) - set(".01234567") for row in rows):
            raise ValueError(f"{tile['name']}: need 16 rows of 16 index characters")
        intents = {"walk", "solid", "water", "unbound"}
        if tile["collision_intent"] not in intents:
            raise ValueError("unknown collision intent")
        overrides = tile.get("collision_quadrants", {})
        if set(overrides) - {"tl", "tr", "bl", "br"} or set(overrides.values()) - intents:
            raise ValueError("invalid collision quadrant override")
    if not tiles or len(tiles) % 16:
        raise ValueError("cell count must fill complete 16-cell native sheets")
    return source


def matrix(tile):
    return [[0 if c == "." else int(c) for c in row] for row in tile["pixels"]]


def flip(tile, h, v):
    result = tile[::-1] if v else tile
    return [row[::-1] if h else row[:] for row in result]


def encode_4bpp(tile):
    result = bytearray(32)
    for y, row in enumerate(tile):
        for x, value in enumerate(row):
            for plane in range(4):
                result[(plane // 2) * 16 + y * 2 + plane % 2] |= ((value >> plane) & 1) << (7 - x)
    return bytes(result)


def decode_4bpp(raw):
    return [[sum(((raw[(p // 2) * 16 + y * 2 + p % 2] >> (7 - x)) & 1) << p
                 for p in range(4)) for x in range(8)] for y in range(8)]


def encode_3bpp(tile):
    raw = encode_4bpp(tile)
    return raw[:16] + raw[16::2]


def png_bytes(im):
    output = io.BytesIO()
    im.save(output, format="PNG", optimize=False)
    return output.getvalue()


def indexed_image(grid, palette):
    from PIL import Image
    image = Image.new("P", (len(grid[0]), len(grid)))
    image.putpalette([v for color in palette for v in color] + [0] * (768 - 24))
    image.putdata([v for row in grid for v in row])
    image.info["transparency"] = 0
    return image


def preview(source, atlas):
    """Labeled presentation only. atlas.png is the exact native indexed asset."""
    from PIL import Image, ImageDraw, ImageFont
    footer = 86 + (len(source["tiles"]) // 8) * 112 + 15
    width, height = 1024, footer + 45
    image = Image.new("RGB", (width, height), (20, 31, 38))
    draw = ImageDraw.Draw(image)
    small = ImageFont.load_default(size=10)
    normal = ImageFont.load_default(size=14)
    title = ImageFont.load_default(size=25)
    draw.text((22, 16), "KALYXO DOCKS / NATIVE TILE LIBRARY", font=title, fill=(239, 222, 182))
    draw.text((23, 49), "16 x 16 cells  /  8 x 8 subtiles  /  8 indexed colors  /  logical IDs only", font=normal, fill=(151, 178, 185))
    for tile in source["tiles"]:
        cell = tile["id"]
        x, y = (cell % 8) * 128, 86 + (cell // 8) * 112
        draw.rectangle((x + 8, y, x + 120, y + 105), fill=(29, 43, 49), outline=(55, 70, 73))
        crop = atlas.crop(((cell % 8) * 16, (cell // 8) * 16, (cell % 8 + 1) * 16, (cell // 8 + 1) * 16))
        crop = crop.convert("RGBA").resize((64, 64), Image.Resampling.NEAREST)
        image.paste(crop, (x + 32, y + 5), crop)
        draw.text((x + 13, y + 74), f"{cell:02X} {tile['name']}", font=small, fill=(231, 212, 174))
        draw.text((x + 13, y + 89), tile["role"], font=small, fill=(143, 169, 174))
    for index, entry in enumerate(source["palette"]):
        x = 22 + index * 55
        draw.rectangle((x, footer, x + 28, footer + 19), fill=tuple(entry["rgb"]))
        draw.text((x + 34, footer + 3), str(index), font=small, fill=(218, 222, 211))
    draw.text((480, footer), "Existing MAIN row 3: 1-6 wood / 7 water / 0 transparent source", font=small, fill=(151, 178, 185))
    draw.text((480, footer + 18), "Hand-authored pixel matrices. No generated-image sampling.", font=small, fill=(151, 178, 185))
    return image


def compile_library(source, source_bytes):
    palette = [entry["rgb"] for entry in source["palette"]]
    tiles = source["tiles"]
    height = (len(tiles) // 8) * 16
    grid = [[0] * 128 for _ in range(height)]
    for tile in tiles:
        x, y = (tile["id"] % 8) * 16, (tile["id"] // 8) * 16
        for dy, row in enumerate(matrix(tile)):
            grid[y + dy][x:x + 16] = row

    subtile_count = (height // 8) * 16
    subtiles = []
    for index in range(subtile_count):
        x, y = (index % 16) * 8, (index // 16) * 8
        subtiles.append([row[x:x + 8] for row in grid[y:y + 8]])
    unique = []
    lookup = {}
    refs = []
    for tile in subtiles:
        key = tuple(tuple(row) for row in tile)
        if key not in lookup:
            unique_index = len(unique)
            unique.append(tile)
            for h, v in ((False, False), (True, False), (False, True), (True, True)):
                variant = tuple(tuple(row) for row in flip(tile, h, v))
                lookup.setdefault(variant, {"unique_art_index": unique_index, "hflip": h, "vflip": v})
        refs.append(lookup[key])

    atlas = indexed_image(grid, palette)
    files = {"atlas.png": png_bytes(atlas), "preview.png": png_bytes(preview(source, atlas))}
    files["atlas.4bpp"] = b"".join(encode_4bpp(tile) for tile in subtiles)
    files["unique.4bpp"] = b"".join(encode_4bpp(tile) for tile in unique)
    files["unique.3bpp"] = b"".join(encode_3bpp(tile) for tile in unique)
    files["palette.pal"] = b"".join(struct.pack("<H", (r // 8) | ((g // 8) << 5) | ((b // 8) << 10)) for r, g, b in palette)
    for sheet in range(height // 32):
        sheet_grid = grid[sheet * 32:(sheet + 1) * 32]
        packed = grid_to_sheet(sheet_grid)
        if sheet_to_grid(packed) != sheet_grid:
            raise ValueError("3bpp round-trip failed")
        files[f"sheet_{sheet}.3bpp"] = packed
    for index, tile in enumerate(subtiles):
        raw = files["atlas.4bpp"][index * 32:(index + 1) * 32]
        if decode_4bpp(raw) != tile or any(raw[17::2]):
            raise ValueError("4bpp round-trip or empty high plane check failed")
        reference = refs[index]
        if flip(unique[reference["unique_art_index"]], reference["hflip"], reference["vflip"]) != tile:
            raise ValueError("canonical subtile/flip reconstruction failed")

    cells = []
    collision_unions = {}
    for tile in tiles:
        index = tile["id"]
        top_left = (index // 8) * 32 + (index % 8) * 2
        quadrants = []
        for name, offset in (("tl", 0), ("tr", 1), ("bl", 16), ("br", 17)):
            subtile = top_left + offset
            intent = tile.get("collision_quadrants", {}).get(name, tile["collision_intent"])
            collision_unions.setdefault(intent, set()).add(refs[subtile]["unique_art_index"])
            quadrants.append({"quadrant": name, "library_subtile_index": subtile,
                              "collision_intent": intent,
                              "offset_4bpp": subtile * 32,
                              "sheet_3bpp": subtile // 64,
                              "sheet_offset_3bpp": (subtile % 64) * 24,
                              **refs[subtile]})
        cells.append({"id": index, "name": tile["name"], "role": tile["role"],
                      "collision_intent": tile["collision_intent"],
                      "notes": tile["notes"], "subtiles": quadrants})
    manifest = {
        "schema_version": 1,
        "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
        "cell_size": 16, "subtile_size": 8, "cell_count": len(tiles),
        "atlas_size": [128, height], "library_subtile_count": subtile_count,
        "unique_subtile_count_with_flips": len(unique), "transparent_index": 0,
        "unique_collision_requirements": {key: sorted(values) for key, values in sorted(collision_unions.items())},
        "binding": "Unallocated art library. IDs and offsets do not identify ROM, CHR, Map16, palette rows or collision slots.",
        "palette_format": "Eight little-endian SNES BGR555 words, including transparent index 0.",
        "palette_binding": source["palette_binding"],
        "native_binding_index_remap": {"0": 7},
        "native_binding_remap_applied": False,
        "unique_payload": "unique.3bpp / unique.4bpp are sequential 8x8 art tiles; apply each subtile hflip/vflip for reconstruction.",
        "cells": cells,
        "outputs": {name: {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()} for name, data in files.items()},
    }
    files["manifest.json"] = (json.dumps(manifest, indent=2) + "\n").encode()
    return files, manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="validate source and compare every generated file without writing")
    args = parser.parse_args()
    source_path = ROOT / "source.json"
    source_bytes = source_path.read_bytes()
    files, manifest = compile_library(load_source(source_path), source_bytes)
    generated = ROOT / "generated"
    stale = [name for name, data in files.items() if not (generated / name).exists() or (generated / name).read_bytes() != data]
    if args.check:
        if stale:
            parser.exit(1, "stale or missing generated files: " + ", ".join(stale) + "\n")
    else:
        generated.mkdir(parents=True, exist_ok=True)
        for name in stale:
            (generated / name).write_bytes(files[name])
    print(f"{'PASS' if args.check else 'Wrote'}: {manifest['cell_count']} cells, {manifest['library_subtile_count']} subtiles, "
          f"{manifest['unique_subtile_count_with_flips']} unique with flips, {len(files)} generated files; 3bpp/4bpp/flip round-trips pass")


if __name__ == "__main__":
    main()
