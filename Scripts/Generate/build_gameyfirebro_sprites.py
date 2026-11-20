#!/usr/bin/env python3
"""Pack locked GameyFireBro yaze bundles into validated SNES 4bpp sprite assets.

Reads only the pre-cut bundles under oos-discord/art/gameyfirebro/yaze/.
Does not open raw/ (third-party rips live there) and does not write a ROM.

Usage:
  python3 Scripts/Generate/build_gameyfirebro_sprites.py
  python3 Scripts/Generate/build_gameyfirebro_sprites.py --check
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
OUT_ROOT = ROOT / "Data/graphics/sprites/gameyfirebro"
DEFAULT_YAZE = Path("/Users/scawful/src/hobby/oos-discord/art/gameyfirebro/yaze")

# Whole pre-cut bundles. Pig Moblins are one indexed sheet: the COL row is the
# green poster palette; the same indices sit on the blue soldier OBJ row.
WHOLE_PACKS: tuple[dict, ...] = (
    {"id": "eow_poe_lantern", "folder": "2026-04-02_003_poe_lantern", "frames": None},
    {"id": "pig_moblins", "folder": "2025-06-16_010_moblins", "frames": None},
    {"id": "chain_chomp", "folder": "2024-06-28_091_chomp_anim", "frames": None},
    {"id": "gibdo", "folder": "2024-10-04_015_gibdo", "frames": None},
    {"id": "gibdo_front", "folder": "2024-10-04_016_gibdo_front", "frames": None},
    {"id": "cheep_blooper", "folder": "2024-07-13_060_cheep_blooper", "frames": None},
    {"id": "cheep_anim", "folder": "2024-07-13_059_cheep_anim", "frames": None},
    {"id": "blooper_anim", "folder": "2024-07-13_056_blooper_anim", "frames": None},
)

# 16-bit red octorok frames inside the mixed master sheet, plus the modular
# cut that was saved under the beetles_shaved folder name.
OCTOROK_PACKS: tuple[dict, ...] = (
    {
        "id": "red_octorok",
        "folder": "2026-04-05_000_master_enemies",
        "frames": (14, 15, 17, 18, 59, 71, 72, 73),
    },
    {
        "id": "red_octorok_modular",
        "folder": "2024-06-29_086_beetles_shaved",
        "frames": None,
    },
)


def read_str(blob: bytes, i: int) -> tuple[str, int]:
    n = shift = 0
    while True:
        v = blob[i]
        i += 1
        n |= (v & 0x7F) << shift
        shift += 7
        if not v & 0x80:
            return blob[i : i + n].decode(), i + n


def read_zsm(path: Path) -> list[list[tuple[int, int, int, int, int]]]:
    blob = path.read_bytes()
    i = 0
    (na,) = struct.unpack_from("<i", blob, i)
    i += 4
    for _ in range(na):
        _, i = read_str(blob, i)
        i += 3
    (nf,) = struct.unpack_from("<i", blob, i)
    i += 4
    frames = []
    for _ in range(nf):
        (nt,) = struct.unpack_from("<i", blob, i)
        i += 4
        tiles = []
        for _ in range(nt):
            tid, pal, _mx, _my, _pr, size, x, y, _z = struct.unpack_from("<HB??B?BBB", blob, i)
            i += 10
            tiles.append((tid, pal, size, x, y))
        frames.append(tiles)
    return frames


def tile8(binb: bytes, idx: int) -> list[list[int]]:
    if idx < 0 or (idx + 1) * 32 > len(binb):
        raise ValueError(f"tile {idx} outside {len(binb)}-byte sheet")
    t = binb[idx * 32 : (idx + 1) * 32]
    return [
        [
            ((t[y * 2] >> (7 - x)) & 1)
            | (((t[y * 2 + 1] >> (7 - x)) & 1) << 1)
            | (((t[16 + y * 2] >> (7 - x)) & 1) << 2)
            | (((t[16 + y * 2 + 1] >> (7 - x)) & 1) << 3)
            for x in range(8)
        ]
        for y in range(8)
    ]


def encode_tile8(px: list[list[int]]) -> bytes:
    out = bytearray(32)
    for y in range(8):
        planes = [0, 0, 0, 0]
        for x in range(8):
            v = px[y][x]
            if not 0 <= v <= 15:
                raise ValueError(f"4bpp index {v}")
            bit = 0x80 >> x
            for plane in range(4):
                if v & (1 << plane):
                    planes[plane] |= bit
        out[y * 2] = planes[0]
        out[y * 2 + 1] = planes[1]
        out[16 + y * 2] = planes[2]
        out[16 + y * 2 + 1] = planes[3]
    return bytes(out)


def snes_rgb(color: int) -> tuple[int, int, int]:
    return ((color & 31) << 3, ((color >> 5) & 31) << 3, ((color >> 10) & 31) << 3)


def load_col(path: Path) -> list[tuple[int, int, int]]:
    blob = path.read_bytes()
    if len(blob) < 32 or len(blob) % 2:
        raise ValueError(f"{path} is not a COL palette")
    return [snes_rgb(struct.unpack_from("<H", blob, i)[0]) for i in range(0, len(blob), 2)]


def frame_origin(width: int, height: int, x: int, y: int) -> tuple[int, int]:
    return x - 128 + (width - 16) // 2, y - 112 + (height - 16)


def render_indices(binb: bytes, tiles, width: int, height: int) -> tuple[list[list[int]], list[list[int]]]:
    idx = [[0] * width for _ in range(height)]
    pal = [[0] * width for _ in range(height)]
    for tid, row, _size, x, y in tiles:
        fx, fy = frame_origin(width, height, x, y)
        for dx, dy, delta in ((0, 0, 0), (8, 0, 1), (0, 8, 16), (8, 8, 17)):
            tile = tile8(binb, tid + delta)
            for yy in range(8):
                for xx in range(8):
                    px, py = fx + dx + xx, fy + dy + yy
                    if not (0 <= px < width and 0 <= py < height):
                        continue
                    v = tile[yy][xx]
                    if v:
                        idx[py][px] = v
                        pal[py][px] = row
    return idx, pal


def png_matches(path: Path, idx, pal_rows, rgb: list[tuple[int, int, int]]) -> bool:
    ref = Image.open(path).convert("RGBA")
    height, width = len(idx), len(idx[0])
    if ref.size != (width, height):
        return False
    pixels = list(ref.getdata())
    for y in range(height):
        for x in range(width):
            v = idx[y][x]
            got = pixels[y * width + x]
            if v == 0:
                if got[3] != 0:
                    return False
            else:
                if got[:3] != rgb[pal_rows[y][x] * 16 + v] or got[3] == 0:
                    return False
    return True


def validate_bundle(folder: Path, meta: dict) -> list[dict]:
    by_bundle: dict[str, list[dict]] = {}
    for frame in meta["frames"]:
        by_bundle.setdefault(frame["bundle"], []).append(frame)
    checked = []
    for bundle, frames in by_bundle.items():
        bin_path = folder / f"{bundle}.bin"
        col_path = folder / f"{bundle}.col"
        zsm_path = folder / f"{bundle}.zsm"
        binb = bin_path.read_bytes()
        if len(binb) % 32 or len(binb) == 0 or len(binb) > 8192:
            raise ValueError(f"{bin_path} is not a 4bpp sheet ({len(binb)} bytes)")
        rgb = load_col(col_path)
        if len(rgb) < 16:
            raise ValueError(f"{col_path} has {len(rgb)} colors")
        zframes = read_zsm(zsm_path)
        if len(zframes) != len(frames):
            raise ValueError(f"{zsm_path} has {len(zframes)} frames, json has {len(frames)}")
        for frame, tiles in zip(frames, zframes):
            width, height = frame["size"]
            idx, pal = render_indices(binb, tiles, width, height)
            if not png_matches(folder / frame["png"], idx, pal, rgb):
                raise ValueError(f"{folder.name} {frame['png']} does not rebuild from 4bpp")
            used = {v for row in idx for v in row if v}
            if any(v > 15 for v in used):
                raise ValueError(f"{folder.name} {frame['png']} uses a non-4bpp index")
            if frame["colors"] > 15:
                raise ValueError(f"{folder.name} {frame['png']} needs {frame['colors']} colors")
        checked.append({"bundle": bundle, "bin": binb, "col": col_path.read_bytes(), "zsm": zsm_path.read_bytes(),
                        "frames": frames, "zframes": zframes, "rgb": rgb})
    return checked


def pack_selected(checked: list[dict], wanted: tuple[int, ...] | None) -> dict:
    chosen = []
    for part in checked:
        for frame, tiles in zip(part["frames"], part["zframes"]):
            if wanted is not None and frame["frame"] not in wanted:
                continue
            chosen.append((part, frame, tiles))
    if wanted is not None and len(chosen) != len(wanted):
        found = [frame["frame"] for _part, frame, _tiles in chosen]
        raise ValueError(f"missing octorok frames, found {found}")
    tiles_out = bytearray()
    placed = []
    cursor = 0
    for part, frame, tiles in chosen:
        width, height = frame["size"]
        idx, pal = render_indices(part["bin"], tiles, width, height)
        cols = (width + 7) // 8
        rows = (height + 7) // 8
        start = cursor // 32
        for ty in range(rows):
            for tx in range(cols):
                tile = [[0] * 8 for _ in range(8)]
                for y in range(8):
                    for x in range(8):
                        sy, sx = ty * 8 + y, tx * 8 + x
                        if sy < height and sx < width:
                            tile[y][x] = idx[sy][sx]
                tiles_out += encode_tile8(tile)
                cursor += 32
        placed.append({
            "source_frame": frame["frame"],
            "bundle": frame["bundle"],
            "size": frame["size"],
            "colors": frame["colors"],
            "palette_row": frame["palette_row"],
            "tile_index": start,
            "tile_columns": cols,
            "tile_rows": rows,
            "png": frame["png"],
        })
    if cursor > 8192:
        raise ValueError(f"packed sheet is {cursor} bytes")
    col = checked[0]["col"]
    return {"bin": bytes(tiles_out), "col": col, "frames": placed, "parts": checked}


def contact_image(folder: Path, placed: list[dict], rgb: list[tuple[int, int, int]]) -> Image.Image:
    thumbs = []
    for frame in placed:
        src = Image.open(folder / frame["png"]).convert("RGBA")
        scale = max(1, min(4, 96 // max(src.size)))
        thumb = src.resize((src.width * scale, src.height * scale), Image.NEAREST)
        thumbs.append((f"{frame['source_frame']:03d}", thumb))
    if not thumbs:
        raise ValueError("empty contact")
    cell_w = max(t.width for _n, t in thumbs) + 8
    cell_h = max(t.height for _n, t in thumbs) + 16
    cols = min(8, len(thumbs))
    rows = (len(thumbs) + cols - 1) // cols
    sheet = Image.new("RGBA", (cols * cell_w, rows * cell_h), (16, 16, 20, 255))
    draw = ImageDraw.Draw(sheet)
    for i, (name, thumb) in enumerate(thumbs):
        r, c = divmod(i, cols)
        x, y = c * cell_w + 4, r * cell_h + 14
        sheet.paste(thumb, (x, y), thumb)
        draw.text((c * cell_w + 4, r * cell_h + 1), name, fill=(255, 220, 80, 255))
    return sheet


def build_pack(yaze: Path, spec: dict) -> dict:
    folder = yaze / spec["folder"]
    if not folder.is_dir():
        raise ValueError(f"missing bundle {folder}")
    meta = json.loads((folder / "frames.json").read_text())
    checked = validate_bundle(folder, meta)
    wanted = spec["frames"]
    if wanted is None:
        placed = []
        blob = bytearray()
        for part in checked:
            start = len(blob)
            blob += part["bin"]
            for frame in part["frames"]:
                placed.append({**{k: frame[k] for k in ("size", "colors", "palette_row", "png")},
                               "source_frame": frame["frame"], "bundle": frame["bundle"],
                               "tile_index": None, "sheet_offset": start})
        packed = {"bin": bytes(blob), "col": b"".join(part["col"] for part in checked),
                  "frames": placed, "parts": checked}
    else:
        packed = pack_selected(checked, wanted)
    rgb = checked[0]["rgb"]
    image = contact_image(folder, [
        {"source_frame": fr["source_frame"], "png": fr["png"]} for fr in packed["frames"]
    ], rgb)
    digest = hashlib.sha256(packed["bin"]).hexdigest()
    return {
        "id": spec["id"],
        "folder": spec["folder"],
        "bin": packed["bin"],
        "col": packed["col"],
        "frames": packed["frames"],
        "sha256": digest,
        "contact": image,
        "frame_count": len(packed["frames"]),
        "bytes": len(packed["bin"]),
    }


def write_pack(pack: dict) -> None:
    dest = OUT_ROOT / pack["id"]
    dest.mkdir(parents=True, exist_ok=True)
    (dest / "sheet.4bpp").write_bytes(pack["bin"])
    (dest / "sheet.col").write_bytes(pack["col"])
    pack["contact"].save(dest / "contact.png")
    manifest = {
        "id": pack["id"],
        "source_folder": pack["folder"],
        "frame_count": pack["frame_count"],
        "sheet_bytes": pack["bytes"],
        "sheet_sha256": pack["sha256"],
        "frames": pack["frames"],
    }
    (dest / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")


def combined_contact(packs: list[dict]) -> Image.Image:
    strips = []
    for pack in packs:
        im = pack["contact"]
        label_h = 18
        strip = Image.new("RGBA", (max(im.width, 240), im.height + label_h), (12, 12, 16, 255))
        draw = ImageDraw.Draw(strip)
        draw.text((4, 2), pack["id"], fill=(255, 255, 255, 255))
        strip.paste(im, (0, label_h))
        strips.append(strip)
    width = max(s.width for s in strips)
    height = sum(s.height for s in strips) + 8 * (len(strips) - 1)
    sheet = Image.new("RGBA", (width, height), (8, 8, 12, 255))
    y = 0
    for strip in strips:
        sheet.paste(strip, (0, y))
        y += strip.height + 8
    return sheet


def check_pack(pack: dict) -> None:
    dest = OUT_ROOT / pack["id"]
    got = (dest / "sheet.4bpp").read_bytes()
    if got != pack["bin"]:
        raise ValueError(f"{pack['id']} sheet.4bpp does not match the bundles")
    if (dest / "sheet.col").read_bytes() != pack["col"]:
        raise ValueError(f"{pack['id']} sheet.col does not match the bundles")
    manifest = json.loads((dest / "manifest.json").read_text())
    if manifest["sheet_sha256"] != pack["sha256"] or manifest["frame_count"] != pack["frame_count"]:
        raise ValueError(f"{pack['id']} manifest does not match")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--yaze", type=Path, default=DEFAULT_YAZE)
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args(argv)
    yaze = args.yaze
    if not yaze.is_dir():
        print(f"MISSING: {yaze}", file=sys.stderr)
        return 1
    packs = []
    for spec in (*WHOLE_PACKS, *OCTOROK_PACKS):
        packs.append(build_pack(yaze, spec))
    if args.check:
        for pack in packs:
            check_pack(pack)
        print(f"OK: {len(packs)} GameyFireBro packs match Data/graphics/sprites/gameyfirebro")
        return 0
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    for pack in packs:
        write_pack(pack)
        print(f"Wrote {pack['id']}: {pack['frame_count']} frames, {pack['bytes']} bytes, {pack['sha256'][:12]}")
    combined_contact(packs).save(OUT_ROOT / "contact_sheet.png")
    index = {
        "packs": [{"id": p["id"], "source_folder": p["folder"], "frames": p["frame_count"],
                   "bytes": p["bytes"], "sha256": p["sha256"]} for p in packs]
    }
    (OUT_ROOT / "index.json").write_text(json.dumps(index, indent=2) + "\n")
    print(f"Wrote {OUT_ROOT / 'contact_sheet.png'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
