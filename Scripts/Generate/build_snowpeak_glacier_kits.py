#!/usr/bin/env python3
"""Convert the locked Snowpeak / Frost Glacier catalog sheets into 3bpp kits.

Locked donors only:
  FSA Tile Sheets 08 and 20 (overworld snow cliffs and pines)
  Minish Cap Temple of Droplets (Snowpeak caves)
  Minish Cap ice dungeon 04 (Glacia lower levels)
  Minish Cap Lake Hylia (Frost Glacier $BE/$BF)

Does not read ZFGC Snow Village, SePH smithy, Geckkko manor, Deadtree,
*__private__* files, or the Holiday Special ROM. Does not write a ROM.

Usage:
  python3 Scripts/Generate/build_snowpeak_glacier_kits.py
  python3 Scripts/Generate/build_snowpeak_glacier_kits.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
GEN = Path(__file__).resolve().parent
sys.path.insert(0, str(GEN))
import sheet_codec  # noqa: E402

OUT_DIR = ROOT / "Data/graphics/snowpeak_glacier"
SHEET37 = ROOT / "Data/graphics/snowpeak_sheet37.txt"
SHEET_JSON = ROOT / "Data/graphics/snowpeak_sheet.json"
SHEET37_SHA = "19279a4cee41b2ee83d52421256b8327dd50338b0a0c0994ee0ec08d35b515a8"

FSA = Path("/Users/scawful/Documents/Zelda/FSA Tilesets")
MCGFX = Path("/Users/scawful/Documents/Zelda/Graphics/MCGFX")
ICE04 = Path(
    "/Users/scawful/Zelda/ReferenceLibrary/sources/documents-zelda/"
    "SePH Folder/Christmas_Present_2/_MC Style/minish_dungeon_04.png"
)

KITS: tuple[dict, ...] = (
    {"id": "fsa_sheet_08", "role": "snowpeak-overworld", "maps": ["0x02", "0x03", "0x04", "0x05", "0x06", "0x07"],
     "paths": [FSA / "Tile Sheet 08.PNG"]},
    {"id": "fsa_sheet_20", "role": "snowpeak-estate", "maps": ["0x06"],
     "paths": [FSA / "Tile Sheet 20.PNG"]},
    {"id": "mc_temple_of_droplets", "role": "snowpeak-caves", "maps": ["0x05", "0x06", "0x07"],
     "paths": [MCGFX / "TempleOfDroplets1.png", MCGFX / "TempleOfDroplets2.png"]},
    {"id": "mc_ice_dungeon_04", "role": "glacia-lower", "maps": ["0x06"],
     "paths": [ICE04]},
    {"id": "mc_lake_hylia", "role": "frost-glacier", "maps": ["0xBE", "0xBF"],
     "paths": [MCGFX / "LakeHylia1.png", MCGFX / "LakeHylia2.png"]},
)

FORBIDDEN = ("deadtree", "__private__", "geckkko", "snowtiles", "smithies-snow", "hs_zs")


def refuse_path(path: Path) -> None:
    text = str(path).lower()
    if any(token in text for token in FORBIDDEN):
        raise ValueError(f"refusing locked-out donor {path}")


def snap_snes(channel: int) -> int:
    return (channel // 8) * 8


def quantize(path: Path) -> tuple[Image.Image, list[tuple[int, int, int]]]:
    refuse_path(path)
    image = Image.open(path).convert("RGB")
    width, height = image.size
    image = image.crop((0, 0, width - width % 8, height - height % 8))
    reduced = image.quantize(colors=8, method=Image.Quantize.MEDIANCUT, dither=Image.Dither.NONE)
    raw = reduced.getpalette()[:24]
    palette = [tuple(snap_snes(raw[i + c]) for c in range(3)) for i in range(0, 24, 3)]
    while len(palette) < 8:
        palette.append((0, 0, 0))
    indexed = reduced.convert("RGB")
    out = Image.new("P", indexed.size)
    out.putpalette([c for rgb in palette for c in rgb] + [0] * (768 - 24))
    src = indexed.load()
    dst = out.load()
    for y in range(indexed.height):
        for x in range(indexed.width):
            pixel = src[x, y]
            snapped = tuple(snap_snes(c) for c in pixel)
            best, dist = 0, 1 << 30
            for i, color in enumerate(palette):
                d = sum((a - b) * (a - b) for a, b in zip(snapped, color))
                if d < dist:
                    best, dist = i, d
            dst[x, y] = best
    return out, palette


def tile_grid(image: Image.Image) -> list[list[list[int]]]:
    width, height = image.size
    tiles = []
    px = image.load()
    for ty in range(0, height, 8):
        for tx in range(0, width, 8):
            tiles.append([[px[tx + x, ty + y] for x in range(8)] for y in range(8)])
    return tiles


def encode_tiles(tiles: list[list[list[int]]]) -> bytes:
    out = bytearray()
    for tile in tiles:
        blob = bytearray(24)
        for y in range(8):
            p0 = p1 = p2 = 0
            for x in range(8):
                v = tile[y][x]
                bit = 0x80 >> x
                if v & 1:
                    p0 |= bit
                if v & 2:
                    p1 |= bit
                if v & 4:
                    p2 |= bit
            blob[y * 2] = p0
            blob[y * 2 + 1] = p1
            blob[16 + y] = p2
        out += blob
    return bytes(out)


def tag_tile(tile: list[list[int]], palette: list[tuple[int, int, int]]) -> str:
    colors = [palette[v] for row in tile for v in row]
    if len({tuple(row) for row in tile}) == 1:
        return "flat"
    avg = tuple(sum(c[i] for c in colors) // len(colors) for i in range(3))
    r, g, b = avg
    lum = (r + g + b) / 3
    spread = max(avg) - min(avg)
    if lum >= 176:
        return "snow"
    if g > r + 18 and g > b + 8:
        return "foliage"
    if b > r + 24 and b >= g and spread >= 28 and lum < 150:
        return "ice"
    if lum < 72:
        return "cliff"
    if spread < 32 and lum > 120:
        return "snow"
    return "ground"


def collision_hint(tag: str) -> str:
    return {
        "flat": "skip",
        "snow": "walk",
        "ground": "walk",
        "foliage": "solid",
        "cliff": "solid",
        "ice": "slip",
    }[tag]


def sheet37_record() -> dict:
    text = SHEET37.read_text()
    grid = sheet_codec.text_to_grid(text)
    raw = sheet_codec.grid_to_sheet(grid)
    digest = hashlib.sha256(raw).hexdigest()
    if digest != SHEET37_SHA:
        raise ValueError(f"snowpeak_sheet37.txt sha {digest} != {SHEET37_SHA}")
    spec = json.loads(SHEET_JSON.read_text())
    if spec["sheets"][0]["decoded_sha256"] != SHEET37_SHA:
        raise ValueError("snowpeak_sheet.json hash drifted")
    if spec["sheets"][0]["global_sheet"] != "0xDF":
        raise ValueError("snowpeak sheet id drifted")
    return {"decoded_sha256": digest, "decoded_bytes": len(raw), "global_sheet": "0xDF",
            "diff_vs_rom_sheet_37": ["0x2B", "0x3B"]}


def build_kit(spec: dict) -> dict:
    pages = []
    for path in spec["paths"]:
        if not path.is_file():
            raise ValueError(f"missing donor {path}")
        image, palette = quantize(path)
        tiles = tile_grid(image)
        pages.append({"path": str(path), "size": list(image.size), "image": image,
                      "palette": palette, "tiles": tiles, "blob": encode_tiles(tiles)})
    tiles = [tile for page in pages for tile in page["tiles"]]
    blob = b"".join(page["blob"] for page in pages)
    unique = len({tuple(tuple(row) for row in tile) for tile in tiles})
    tags: dict[str, int] = {}
    hints: dict[str, int] = {}
    # Tag against the first page palette; later pages carry their own and are counted per page.
    for page in pages:
        for tile in page["tiles"]:
            tag = tag_tile(tile, page["palette"])
            tags[tag] = tags.get(tag, 0) + 1
            hint = collision_hint(tag)
            hints[hint] = hints.get(hint, 0) + 1
    preview = pages[0]["image"]
    if len(pages) > 1:
        width = sum(page["image"].width for page in pages)
        height = max(page["image"].height for page in pages)
        preview = Image.new("P", (width, height))
        preview.putpalette(pages[0]["image"].getpalette())
        x = 0
        for page in pages:
            preview.paste(page["image"], (x, 0))
            x += page["image"].width
    return {
        "id": spec["id"],
        "role": spec["role"],
        "maps": spec["maps"],
        "sources": [str(path) for path in spec["paths"]],
        "blob": blob,
        "sha256": hashlib.sha256(blob).hexdigest(),
        "tile8_count": len(tiles),
        "tile8_unique": unique,
        "duplicate_ratio": round(1 - unique / len(tiles), 4) if tiles else 0,
        "tags": tags,
        "collision_hints": hints,
        "preview": preview,
        "palette": pages[0]["palette"],
    }


def write_kit(kit: dict) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    (OUT_DIR / f"{kit['id']}.3bpp").write_bytes(kit["blob"])
    kit["preview"].save(OUT_DIR / f"{kit['id']}_preview.png")
    record = {k: kit[k] for k in ("id", "role", "maps", "sources", "sha256", "tile8_count",
                                  "tile8_unique", "duplicate_ratio", "tags", "collision_hints", "palette")}
    record["bytes"] = len(kit["blob"])
    (OUT_DIR / f"{kit['id']}.json").write_text(json.dumps(record, indent=2) + "\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    sheet = sheet37_record()
    kits = [build_kit(spec) for spec in KITS]
    if args.check:
        for kit in kits:
            path = OUT_DIR / f"{kit['id']}.3bpp"
            if path.read_bytes() != kit["blob"]:
                print(f"STALE: {path}", file=sys.stderr)
                return 1
        print(f"OK: sheet37 {sheet['decoded_sha256'][:12]} and {len(kits)} kits")
        return 0
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    audit = {"sheet37": sheet, "kits": []}
    for kit in kits:
        write_kit(kit)
        audit["kits"].append({k: kit[k] for k in ("id", "role", "maps", "tile8_count", "tile8_unique",
                                                   "duplicate_ratio", "tags", "collision_hints", "sha256")})
        print(f"Wrote {kit['id']}: {kit['tile8_unique']}/{kit['tile8_count']} unique Tile8, {kit['collision_hints']}")
    (OUT_DIR / "audit.json").write_text(json.dumps(audit, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
