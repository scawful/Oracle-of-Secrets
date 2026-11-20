#!/usr/bin/env python3
"""Generate, verify, and preview Eon Abyss GBC interior sheets, palettes, and ASM tables.

Declarative style definitions live in Dungeons/Data/abyss_gbc/styles.json.
Build reads room headers, object words, and BG sheets from a ROM plus GBC donor
tilesets (prebuilt gbc_interiors directory and/or local oracles-disasm clone),
and writes Dungeons/Data/abyss_gbc/:
  styles.json           declarative style definitions (source of truth)
  <style>.<sheet>.txt   GBC version of a modified BG sheet (sheet_codec text grid)
  <style>.<sheet>.lz2   the same sheet, LC-LZ2 compressed
  abyss_gbc.asm         room style table, sheet map, stream pointers, palettes
  coverage.json         styles digest, palettes, donor vs posterized char coverage

Usage:
  python3 Scripts/Generate/gen_abyss_gbc.py build --rom <rom.sfc> [--donor <dir>] [--oracles-disasm <dir>]
  python3 Scripts/Generate/gen_abyss_gbc.py --check [--rom <rom.sfc>] [--donor <dir>] [--oracles-disasm <dir>]
  python3 Scripts/Generate/gen_abyss_gbc.py --preview-room 0x002[,0x00F,...] --rom <rom.sfc> --out <sheet.png>
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import difflib
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import subprocess
import sys
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parent))
import gen_wall_profiles as gw  # noqa: E402
import lz2  # noqa: E402
import sheet_codec as sc  # noqa: E402
import sheet_table as st  # noqa: E402

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "Dungeons/Data/abyss_gbc"
DEFAULT_STYLES = OUT / "styles.json"
DEFAULT_DISASM = Path("/Users/scawful/src/third_party/oracles-disasm")
DEFAULT_SODACOMA = Path("/Users/scawful/Zelda/Graphics/New Tileset (v2)")
BANK_CAPACITY = 0x8000
CODE_RESERVE = 0x0200  # headroom reserved for Dungeons/abyss_gbc_interiors.asm code in Bank $5A

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
    # concave: NW SW NE SE (top), then bottom $108-$10B
    0x100: (0xB8, COLMAJ_4x4), 0x101: (0xBA, COLMAJ_4x4),
    0x102: (0xB9, COLMAJ_4x4), 0x103: (0xBB, COLMAJ_4x4),
    0x108: (0xB8, COLMAJ_4x4), 0x109: (0xBA, COLMAJ_4x4),
    0x10A: (0xB9, COLMAJ_4x4), 0x10B: (0xBB, COLMAJ_4x4),
    # convex (inner) corners, top $104-$107
    0x104: (0xB7, COLMAJ_4x4), 0x105: (0xB5, COLMAJ_4x4),
    0x106: (0xB6, COLMAJ_4x4), 0x107: (0xB4, COLMAJ_4x4),
}

EXTRA_ROLE_OBJECTS = {
    0x10C: (0xB7, COLMAJ_4x4), 0x10D: (0xB5, COLMAJ_4x4),
    0x10E: (0xB6, COLMAJ_4x4), 0x10F: (0xB4, COLMAJ_4x4),
    # deep walls N S W E -> second GBC wall set (38 top, 39 right, 3A bottom, 3B left)
    0x007: (0x38, COLMAJ_2x2), 0x008: (0x3A, COLMAJ_2x2),
    0x067: (0x3B, COLMAJ_2x2), 0x068: (0x39, COLMAJ_2x2),
    # deep corners NW SW NE SE
    0x118: (0xB8, COLMAJ_2x2), 0x119: (0xBA, COLMAJ_2x2),
    0x11A: (0xB9, COLMAJ_2x2), 0x11B: (0xBB, COLMAJ_2x2),
    # layered stairs -> GBC stair stripes
    0x130: (0x50, COLMAJ_4x4), 0x131: (0x50, COLMAJ_4x4),
    0xF9C: (0x50, COLMAJ_4x4), 0xF9D: (0x50, COLMAJ_4x4),
}

FILL_OBJECTS = {0x0A0: 0xA9, 0x0A1: 0xA9, 0x0A2: 0xA9, 0x0A3: 0xA9}
DIAGONAL_OBJECTS = range(0x009, 0x015)
DIAGONAL_STYLES = {
    "slope45": None,  # synthesized 45-degree GBC stone aligned to Q-OOS-21 single-course walls ($080/$081/$09A/$09B)
    "wall": [(0xA9, 0, 0), (0xB0, 0, 0), (0xB0, 0, 1), (0xB0, 0, 0), (0xB0, 0, 1)],
    "fill": [(0xA9, 0, 0), (0xA8, 0, 0), (0xA8, 0, 0), (0xA8, 0, 0), (0xB0, 0, 1)],
}
DEEP_STYLES = {
    "second": {},
    "main": {
        0x007: (0xB0, COLMAJ_2x2), 0x008: (0xB2, COLMAJ_2x2),
        0x067: (0xB3, COLMAJ_2x2), 0x068: (0xB1, COLMAJ_2x2),
    },
}
STAIR_STYLES = {
    "stripes": {},
    "icons": {
        0x130: (0x44, COLMAJ_4x4), 0x131: (0x44, COLMAJ_4x4),
        0xF9C: (0x45, COLMAJ_4x4), 0xF9D: (0x45, COLMAJ_4x4),
    },
}
FLOOR_META = 0xA0
FLOOR_SHAPE = ROWMAJ_4x2
DEFAULT_SKIP_FLOORS = (0xB, 0xC, 0xE, 0xF)


def parse_int(value: int | str) -> int:
    if isinstance(value, int):
        return value
    text = str(value).strip()
    if text.startswith("$"):
        return int(text[1:], 16)
    return int(text, 0)


def parse_room_id(value: str) -> int:
    text = value.strip()
    if text.startswith("$"):
        return int(text[1:], 16)
    if text.lower().startswith("0x"):
        return int(text, 16)
    return int(text, 16)


def canonical_styles_sha256(raw_config: dict) -> str:
    payload = json.dumps(raw_config, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def load_styles_config(path: Path = DEFAULT_STYLES) -> tuple[dict, dict, list[dict], str]:
    """Load and validate styles.json. Returns (raw_config, defaults, normalized_styles, sha256)."""
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("schema_version") != 1:
        raise ValueError(f"{path}: unsupported schema_version {raw.get('schema_version')!r}")
    defaults_raw = raw.get("defaults", {})
    defaults = {
        "diagonal": defaults_raw.get("diagonal", "wall"),
        "deep": defaults_raw.get("deep", "second"),
        "stairs": defaults_raw.get("stairs", "stripes"),
        "floor_meta": parse_int(defaults_raw.get("floor_meta", FLOOR_META)),
        "skip_floors": [parse_int(v) for v in defaults_raw.get("skip_floors", DEFAULT_SKIP_FLOORS)],
        "skip_unchanged_sheets": bool(defaults_raw.get("skip_unchanged_sheets", True)),
    }
    if defaults["diagonal"] not in DIAGONAL_STYLES:
        raise ValueError(f"{path}: invalid default diagonal style {defaults['diagonal']!r}")
    if defaults["deep"] not in DEEP_STYLES:
        raise ValueError(f"{path}: invalid default deep style {defaults['deep']!r}")
    if defaults["stairs"] not in STAIR_STYLES:
        raise ValueError(f"{path}: invalid default stairs style {defaults['stairs']!r}")

    styles_raw = raw.get("styles")
    if not isinstance(styles_raw, list) or not styles_raw:
        raise ValueError(f"{path}: 'styles' must be a non-empty list")

    seen_names: set[str] = set()
    seen_rooms: dict[int, str] = {}
    styles: list[dict] = []
    for entry in styles_raw:
        name = entry.get("name")
        if not isinstance(name, str) or not name or not name.replace("_", "").isalnum():
            raise ValueError(f"{path}: invalid style name {name!r}")
        if name in seen_names:
            raise ValueError(f"{path}: duplicate style name {name!r}")
        seen_names.add(name)

        rooms = [parse_int(r) for r in entry.get("rooms", [])]
        more_rooms = [parse_int(r) for r in entry.get("more_rooms", [])]
        if not rooms:
            raise ValueError(f"{path}: style {name!r} must have at least one room in 'rooms'")
        for r in rooms + more_rooms:
            if not (0 <= r < gw.ROOM_COUNT):
                raise ValueError(f"{path}: style {name!r} room 0x{r:03X} out of range 0..0x{gw.ROOM_COUNT-1:03X}")
            if r in seen_rooms:
                raise ValueError(
                    f"{path}: duplicate room 0x{r:03X} in style {name!r} (already in {seen_rooms[r]!r})"
                )
            seen_rooms[r] = name

        donor = entry.get("donor", {})
        has_prebuilt = all(k in donor for k in ("png", "map", "pal"))
        has_disasm = bool(donor.get("disasm"))
        has_png_grid = bool(donor.get("png_grid"))
        if not isinstance(donor, dict) or not (has_prebuilt or has_disasm or has_png_grid):
            raise ValueError(
                f"{path}: style {name!r} donor must specify png/map/pal, disasm, and/or png_grid"
            )
        if has_png_grid:
            pg = donor["png_grid"]
            if not isinstance(pg, dict) or "png" not in pg or "kit_origin" not in pg or "wall_rgb4" not in pg:
                raise ValueError(f"{path}: style {name!r} png_grid requires png, kit_origin, and wall_rgb4")
            if len(pg["kit_origin"]) != 2 or len(pg["wall_rgb4"]) != 4:
                raise ValueError(f"{path}: style {name!r} png_grid invalid kit_origin or wall_rgb4")

        row_pal = {}
        for k, v in entry.get("row_pal", {}).items():
            rk, rv = parse_int(k), parse_int(v)
            if not (2 <= rk <= 7):
                raise ValueError(f"{path}: style {name!r} row_pal key {rk} must be in 2..7")
            row_pal[rk] = rv

        extra_pal = {}
        for k, cols in entry.get("extra_pal", {}).items():
            ek = parse_int(k)
            if ek < 8 or len(cols) != 4:
                raise ValueError(f"{path}: style {name!r} extra_pal {k} must have id>=8 and 4 RGB tuples")
            parsed_cols = []
            for c in cols:
                if len(c) != 3 or any(not (0 <= int(ch) <= 31) for ch in c):
                    raise ValueError(f"{path}: style {name!r} extra_pal {k} invalid 5-bit RGB {c!r}")
                parsed_cols.append((int(c[0]), int(c[1]), int(c[2])))
            extra_pal[ek] = parsed_cols

        accent = {}
        for k, v in entry.get("accent", {}).items():
            ak, av = parse_int(k), parse_int(v)
            if not (2 <= ak <= 7):
                raise ValueError(f"{path}: style {name!r} accent row {ak} must be in 2..7")
            accent[ak] = av

        accent_floors = {}
        for obj_k, spec in entry.get("accent_floors", {}).items():
            obj_id = parse_int(obj_k)
            meta = parse_int(spec["meta"])
            shades = {parse_int(sk): parse_int(sv) for sk, sv in spec["shades"].items()}
            accent_floors[obj_id] = (meta, shades)

        inlays = []
        for inl in entry.get("inlays", []):
            inlays.append({
                "object": parse_int(inl["object"]),
                "blocks": parse_int(inl["blocks"]),
                "under": parse_int(inl["under"]),
                "keep": {parse_int(sk): parse_int(sv) for sk, sv in inl["keep"].items()},
            })

        triforce_gold_rgb = None
        if "triforce_gold_rgb" in entry:
            tg = entry["triforce_gold_rgb"]
            if len(tg) != 3 or any(not (0 <= int(ch) <= 255) for ch in tg):
                raise ValueError(f"{path}: style {name!r} invalid triforce_gold_rgb {tg!r}")
            triforce_gold_rgb = (int(tg[0]), int(tg[1]), int(tg[2]))

        norm = {
            "name": name,
            "notes": entry.get("notes", ""),
            "donor": donor,
            "rooms": rooms,
            "more_rooms": more_rooms,
            "floor_meta": parse_int(entry["floor_meta"]) if "floor_meta" in entry else defaults["floor_meta"],
            "skip_floors": [parse_int(v) for v in entry.get("skip_floors", defaults["skip_floors"])],
            "row_pal": row_pal,
            "extra_pal": extra_pal,
            "accent": accent,
            "accent_floors": accent_floors,
            "inlays": inlays,
            "posterize_like": parse_int(entry["posterize_like"]) if "posterize_like" in entry else None,
            "triforce_gold_rgb": triforce_gold_rgb,
        }
        styles.append(norm)

    return raw, defaults, styles, canonical_styles_sha256(raw)


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


def _parse_disasm_palette(pal_file: Path, label: str) -> dict[int, list[tuple[int, int, int]]]:
    txt = pal_file.read_text(encoding="utf-8")
    anchor = label + ":"
    if anchor not in txt:
        raise ValueError(f"Palette label {label!r} not found in {pal_file}")
    cols: list[tuple[int, int, int]] = []
    for ln in txt[txt.index(anchor):].splitlines()[1:]:
        stripped = ln.strip()
        if stripped.startswith("m_RGB16"):
            parts = stripped.split()
            cols.append(tuple(int(p.lstrip("$"), 16) for p in parts[1:4]))
            if len(cols) == 24:
                break
    if len(cols) != 24:
        raise ValueError(f"Palette label {label!r} yielded {len(cols)} colors (expected 24)")
    return {2 + i: cols[i * 4:i * 4 + 4] for i in range(6)}


def _rgb8_to_5(rgb: tuple[int, int, int]) -> tuple[int, int, int]:
    return (round(rgb[0] * 31 / 255), round(rgb[1] * 31 / 255), round(rgb[2] * 31 / 255))


def _nearest_shade(rgb: tuple[int, int, int], palette_rgb: list[tuple[int, int, int]]) -> int:
    best_i, best_d = 0, 10**9
    for i, p in enumerate(palette_rgb):
        d = (rgb[0] - p[0]) ** 2 * 3 + (rgb[1] - p[1]) ** 2 * 6 + (rgb[2] - p[2]) ** 2 * 2
        if d < best_d:
            best_d = d
            best_i = i
    return best_i


def _quantize_tile_by_luma(img, tx: int, ty: int) -> list[list[int]]:
    crop = img.crop((tx * 16, ty * 16, (tx + 1) * 16, (ty + 1) * 16)).convert("RGB")
    px = crop.load()
    uniq = sorted({px[x, y] for y in range(16) for x in range(16)}, key=lambda c: -lum(c))
    if len(uniq) <= 4:
        if len(uniq) == 1:
            lut = {uniq[0]: 1}
        elif len(uniq) == 2:
            lut = {uniq[0]: 0, uniq[1]: 3}
        elif len(uniq) == 3:
            lut = {uniq[0]: 0, uniq[1]: 1, uniq[2]: 2}
        else:
            lut = {c: i for i, c in enumerate(uniq)}
        return [[lut[px[x, y]] for x in range(16)] for y in range(16)]
    mn, mx = lum(uniq[-1]), lum(uniq[0])
    span = max(1.0, mx - mn)
    out = []
    for y in range(16):
        row = []
        for x in range(16):
            norm = (mx - lum(px[x, y])) / span
            row.append(min(3, int(norm * 3.999)))
        out.append(row)
    return out


class Donor:
    def __init__(
        self,
        donor_root: Path | None,
        disasm_root: Path | None,
        style: dict,
        sodacoma_root: Path | None = None,
    ):
        from PIL import Image

        spec = style["donor"]
        self._png_grid_tiles: dict[int, tuple[list[list[int]], int]] | None = None
        use_prebuilt = (
            donor_root is not None
            and all(k in spec for k in ("png", "map", "pal"))
            and (donor_root / spec["png"]).is_file()
            and (donor_root / spec["map"]).is_file()
            and (donor_root / spec["pal"]).is_file()
        )
        if "png_grid" in spec:
            pg = spec["png_grid"]
            png_rel = Path(pg["png"])
            png_path = png_rel if png_rel.is_absolute() else (
                (sodacoma_root / png_rel) if sodacoma_root is not None else (DEFAULT_SODACOMA / png_rel)
            )
            if not png_path.is_file():
                raise FileNotFoundError(
                    f"Style {style['name']!r} requires --sodacoma PNG asset (not found: {png_path})"
                )
            im = Image.open(png_path).convert("RGBA")
            ox, oy = int(pg["kit_origin"][0]), int(pg["kit_origin"][1])
            wall_rgb4 = [tuple(int(ch) for ch in c) for c in pg["wall_rgb4"]]
            floor_rgb4 = [tuple(int(ch) for ch in c) for c in pg.get("floor_pal_rgb4", wall_rgb4)]
            w5 = [_rgb8_to_5(c) for c in wall_rgb4]
            f5 = [_rgb8_to_5(c) for c in floor_rgb4]
            self.pal = {2: w5, 3: w5, 4: f5, 5: f5, 6: w5, 7: w5}
            if "accent_pal_rgb4" in pg:
                self.pal[7] = [_rgb8_to_5(tuple(int(ch) for ch in c)) for c in pg["accent_pal_rgb4"]]

            def tile_from_kit(dx: int, dy: int, pal_id: int = 3):
                crop = im.crop(((ox + dx) * 16, (oy + dy) * 16,
                                (ox + dx + 1) * 16, (oy + dy + 1) * 16)).convert("RGB")
                px = crop.load()
                return [[_nearest_shade(px[x, y], wall_rgb4) for x in range(16)] for y in range(16)], pal_id

            def tile_abs(tx: int, ty: int, pal_id: int = 4, by_luma: bool = False, remap=None):
                if by_luma:
                    grid = _quantize_tile_by_luma(im, tx, ty)
                else:
                    crop = im.crop((tx * 16, ty * 16, (tx + 1) * 16, (ty + 1) * 16)).convert("RGB")
                    px = crop.load()
                    grid = [[_nearest_shade(px[x, y], wall_rgb4) for x in range(16)] for y in range(16)]
                if remap:
                    grid = [[remap.get(v, v) for v in r] for r in grid]
                return grid, pal_id

            floor_by_luma = bool(pg.get("floor_by_luma", False))
            floor_remap = {int(k): int(v) for k, v in pg.get("floor_shade_remap", {}).items()} or None
            stairs_tx, stairs_ty = pg.get("stairs_tile", [6, 5])

            tiles: dict[int, tuple[list[list[int]], int]] = {
                0xB0: tile_from_kit(1, 0, 3),
                0xB1: tile_from_kit(2, 1, 3),
                0xB2: tile_from_kit(1, 2, 3),
                0xB3: tile_from_kit(0, 1, 3),
                0xB8: tile_from_kit(0, 0, 3),
                0xB9: tile_from_kit(2, 0, 3),
                0xBA: tile_from_kit(0, 2, 3),
                0xBB: tile_from_kit(2, 2, 3),
                # Verified convex inner corner orientation vs Bank $01 $104-$107
                0xB7: tile_from_kit(4, 1, 3),
                0xB5: tile_from_kit(4, 0, 3),
                0xB6: tile_from_kit(3, 1, 3),
                0xB4: tile_from_kit(3, 0, 3),
                0x38: tile_from_kit(1, 0, 3),
                0x39: tile_from_kit(2, 1, 3),
                0x3A: tile_from_kit(1, 2, 3),
                0x3B: tile_from_kit(0, 1, 3),
                0xA8: ([[2] * 16 for _ in range(16)], 3),
                0xA9: ([[3] * 16 for _ in range(16)], 3),
                0x50: tile_abs(int(stairs_tx), int(stairs_ty), 3, by_luma=True),
            }
            if "floor_tile" in pg:
                fx, fy = int(pg["floor_tile"][0]), int(pg["floor_tile"][1])
                tiles[0xA0] = tile_abs(fx, fy, 4, by_luma=floor_by_luma, remap=floor_remap)
            else:
                tiles[0xA0] = tile_from_kit(1, 1, 4)
            if "throne_tile" in pg:
                tx, ty = int(pg["throne_tile"][0]), int(pg["throne_tile"][1])
                tiles[0xA1] = tile_abs(tx, ty, 4, by_luma=floor_by_luma, remap=floor_remap)
            else:
                tiles[0xA1] = tiles[0xA0]
            if "accent_tile" in pg:
                ax, ay = int(pg["accent_tile"][0]), int(pg["accent_tile"][1])
                tiles[0xA2] = tile_abs(ax, ay, 4, by_luma=False)
            else:
                tiles[0xA2] = tiles[0xA1]
            self._png_grid_tiles = tiles
            self.vram = []
            self.maps = b""
        elif use_prebuilt:
            im = Image.open(donor_root / spec["png"])
            px = im.load()
            self.vram = [
                [[px[(i % 16) * 8 + x, (i // 16) * 8 + y] & 3 for x in range(8)] for y in range(8)]
                for i in range(256)
            ]
            self.maps = (donor_root / spec["map"]).read_bytes()
            vals = [
                tuple(int(v, 16) for v in ln.split())
                for ln in (donor_root / spec["pal"]).read_text(encoding="utf-8").splitlines()
                if ln.strip()
            ]
            self.pal = {2 + i: vals[i * 4:i * 4 + 4] for i in range(6)}
        elif "disasm" in spec:
            if disasm_root is None or not disasm_root.is_dir():
                raise FileNotFoundError(
                    f"Style {style['name']!r} requires --oracles-disasm directory (not found: {disasm_root})"
                )
            dspec = spec["disasm"]
            game = dspec["game"]
            gfx_dir = disasm_root / f"gfx_compressible/{game}"
            self.vram = [[[0] * 8 for _ in range(8)] for _ in range(256)]
            for item in dspec["gfx"]:
                im = Image.open(gfx_dir / f"{item['file']}.png")
                px = im.load()
                w, h = im.size
                chars = [
                    [[px[cx * 8 + x, cy * 8 + y] & 3 for x in range(8)] for y in range(8)]
                    for cy in range(h // 8)
                    for cx in range(w // 8)
                ]
                count = parse_int(item["count"]) if "count" in item else len(chars)
                base = (parse_int(item["addr"]) - 0x8800) // 16
                for idx in range(min(count, len(chars))):
                    if 0 <= base + idx < 256:
                        self.vram[base + idx] = chars[idx]
            layout_path = disasm_root / f"tileset_layouts/{game}/tilesetMappings{dspec['layout']}.bin"
            self.maps = layout_path.read_bytes()
            pal_path = disasm_root / f"data/{game}/paletteData.s"
            self.pal = _parse_disasm_palette(pal_path, dspec["palette_label"])
        else:
            raise FileNotFoundError(
                f"Style {style['name']!r} donor assets missing under {donor_root} and no 'disasm'/'png_grid' recipe"
            )
        self.pal.update(style.get("extra_pal", {}))

    def char(self, i: int):
        return self.vram[i]

    def quadrant(self, meta: int, qx: int, qy: int):
        """8x8 shade grid (GBC colour 0-3) and GBC palette of a metatile quadrant."""
        if self._png_grid_tiles is not None:
            g16, pal_id = self._png_grid_tiles[meta]
            x0, y0 = qx * 8, qy * 8
            return [row[x0:x0 + 8] for row in g16[y0:y0 + 8]], pal_id
        e = self.maps[meta * 8:meta * 8 + 8]
        k = qy * 2 + qx
        t, a = e[k], e[4 + k]
        g = self.char(t ^ 0x80)
        if a & 0x20:
            g = [r[::-1] for r in g]
        if a & 0x40:
            g = g[::-1]
        return g, (a & 7) if (a & 7) >= 2 else 2


def synthesize_slope45_diagonals(donor: Donor) -> list[list[list[int]]]:
    """Build 4 crisp 8x8 diagonal wall tiles ($080, $081, $09A, $09B) aligned pixel-for-pixel
    to Q-OOS-21 single-course 16px straight walls ($001/$002/$061/$062).

    For a NW 45-degree slope ($009/$00D/$011, stepped dx=+8, dy=-8), pixel (x, y) in tile
    row in {0..3} has exact perpendicular distance d = 8*row + x + y from outer void:
      d <= 14: pure void (meets row 0 / col 0 $3C15 void with zero jagged outer teeth)
      d == 15..30: 16-unit 45-degree beveled GBC stone matching donor's 0xB0 vertical tones
      d >= 31: soft inner shadow trim meeting row 3 / col 3 walkable floor
    Tangent u = (x - y - 8*row) & 15 is 100% continuous across adjacent diagonal columns.
    """
    q00, wall_pal = donor.quadrant(0xB0, 0, 0)
    q10, _ = donor.quadrant(0xB0, 1, 0)
    q01, _ = donor.quadrant(0xB0, 0, 1)
    q11, _ = donor.quadrant(0xB0, 1, 1)
    wall16 = [q00[y] + q10[y] for y in range(8)] + [q01[y] + q11[y] for y in range(8)]

    # Rank donor wall palette indices brightest (0) -> darkest (3)
    cols = donor.pal[wall_pal]
    rank_to_idx = sorted(range(4), key=lambda k: -lum(c5(cols[k])))
    idx_to_rank = {idx: r for r, idx in enumerate(rank_to_idx)}

    row_prof = [
        Counter(idx_to_rank[v] for v in wall16[v_row]).most_common(1)[0][0]
        for v_row in range(16)
    ]

    tiles: list[list[list[int]]] = []
    for row in range(4):
        g = [[rank_to_idx[3]] * 8 for _ in range(8)]
        for y in range(8):
            for x in range(8):
                d = 8 * row + x + y
                u = (x - y - 8 * row) & 15
                if d <= 14:
                    r_sh = 3
                elif d == 15 or d == 30:
                    r_sh = 3
                elif d <= 17:
                    r_sh = 1 if u == 0 else 0
                elif d == 18:
                    r_sh = 2 if u == 0 else (0 if row_prof[3] == 0 else 1)
                elif d <= 26:
                    base = row_prof[d - 15]
                    seam_u = 0 if d < 22 else 8
                    if u == seam_u:
                        r_sh = min(3, max(2, base + 1))
                    elif u == ((seam_u + 1) & 15) and base >= 1:
                        r_sh = max(0, base - 1)
                    else:
                        r_sh = base
                elif d <= 29:
                    r_sh = 3 if (u == 8 and d == 29) else 2
                else:
                    r_sh = 2
                g[y][x] = rank_to_idx[r_sh]
        tiles.append(g)
    return tiles


def unflip(g, word):
    """Glyph to store so that drawing it with `word`'s flips shows g."""
    if word & 0x4000:
        g = [r[::-1] for r in g]
    if word & 0x8000:
        g = g[::-1]
    return g


def bank_5a_stream_budget(num_styles: int, num_streams: int) -> int:
    table_bytes = (
        gw.ROOM_COUNT
        + 256 * num_styles
        + 4 * num_streams
        + 2 * num_styles
        + 180 * num_styles
    )
    budget = BANK_CAPACITY - CODE_RESERVE - table_bytes
    if budget <= 0:
        raise ValueError(f"Bank $5A tables ({table_bytes} B) exceed bank capacity")
    return budget


def render_abyss_asm(
    styles: list[dict],
    sheet_map: list[dict[int, int]],
    streams: list[str],
    palettes: list[list[int]],
    stream_sizes: dict[str, int],
) -> tuple[str, dict[str, int]]:
    """Deterministically generate abyss_gbc.asm and bank usage metrics."""
    room_style = [0] * gw.ROOM_COUNT
    for sid, style in enumerate(styles, 1):
        for r in style["rooms"] + style["more_rooms"]:
            room_style[r] = sid

    lines = [
        "; Generated by Scripts/Generate/gen_abyss_gbc.py. Do not edit.",
        f"; Styles: {', '.join(f'{i}={s['name']}' for i, s in enumerate(styles, 1))}",
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

    budget_a = bank_5a_stream_budget(len(styles), len(streams))
    used_a, used_b, bank_b = 0, 0, False
    for stem in streams:
        size = stream_sizes[stem]
        if not bank_b and used_a + size > budget_a:
            lines += ['assert pc() <= $5B0000, "Abyss GBC bank $5A overrun"', "org $5B8000"]
            bank_b = True
        if bank_b:
            used_b += size
        else:
            used_a += size
        lines.append(f'AbyssGbc_{stem.replace(".", "_")}: incbin "Dungeons/Data/abyss_gbc/{stem}.lz2"')
    if not bank_b:
        lines.append('assert pc() <= $5B0000, "Abyss GBC bank $5A overrun"')
    else:
        lines.append('assert pc() <= $5C0000, "Abyss GBC bank $5B overrun"')
    if used_b > BANK_CAPACITY:
        raise ValueError(f"Abyss GBC Bank $5B stream overflow: {used_b} > {BANK_CAPACITY}")

    metrics = {
        "bank5a_stream_budget": budget_a,
        "bank5a_stream_bytes": used_a,
        "bank5b_stream_bytes": used_b,
        "bank5b_free_bytes": BANK_CAPACITY - used_b,
        "total_lz2_bytes": used_a + used_b,
    }
    return "\n".join(lines) + "\n", metrics


def generate_artifacts(
    rom: bytes,
    styles_path: Path,
    donor_root: Path | None,
    disasm_root: Path | None,
    *,
    sodacoma_root: Path | None = None,
    diagonal: str | None = None,
    deep: str | None = None,
    stairs: str | None = None,
) -> tuple[dict[str, bytes | str], dict[str, int]]:
    """Build all Abyss GBC artifacts in memory. Returns ({filename: content}, metrics)."""
    _, defaults, styles, styles_sha = load_styles_config(styles_path)
    diag_mode = diagonal or defaults["diagonal"]
    deep_mode = deep or defaults["deep"]
    stairs_mode = stairs or defaults["stairs"]
    skip_unchanged = defaults["skip_unchanged_sheets"]

    streams: list[str] = []
    sheet_map: list[dict[int, int]] = []
    palettes: list[list[int]] = []
    stream_sizes: dict[str, int] = {}
    artifacts: dict[str, bytes | str] = {}
    coverage_styles: dict[str, dict] = {}

    for style in styles:
        donor = Donor(donor_root, disasm_root, style, sodacoma_root=sodacoma_root)
        voters = set(style["rooms"])
        rooms = style["rooms"] + style["more_rooms"]

        slot_sheets: dict[int, set[int]] = defaultdict(set)
        pal_ids = []
        for r in rooms:
            bs, pid = gw.room_blockset_palette(rom, r)
            pal_ids.append(pid)
            for slot, s in enumerate(gw.effective_slots(rom, bs)[:7]):
                slot_sheets[slot].add(s)

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

        floor_meta = style["floor_meta"]
        for obj, (meta, shades) in style["accent_floors"].items():
            for (col, row), w in zip(FLOOR_SHAPE, object_words(rom, obj, 8)):
                place(w, meta, col, row, None, shades)
        for inlay in style["inlays"]:
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
                src = unflip(src, w)
                ug, _ = donor.quadrant(meta, (col + 1) % 2, row % 2)
                out = [
                    [inlay["keep"][src[y][x]] if src[y][x] in inlay["keep"] else shades[ug[y][x]]
                     for x in range(8)]
                    for y in range(8)
                ]
                glyph[c] = unflip(out, w)

        extra = {**EXTRA_ROLE_OBJECTS, **DEEP_STYLES[deep_mode], **STAIR_STYLES[stairs_mode]}
        for roles, tally in ((ROLE_OBJECTS, votes), (extra, extra_votes)):
            for obj, (meta, shape) in roles.items():
                for (col, row), w in zip(shape, object_words(rom, obj, len(shape))):
                    place(w, meta, col, row, tally)
        for obj, meta in FILL_OBJECTS.items():
            place(object_words(rom, obj, 1)[0], meta, 0, 0, None)
        if diag_mode == "slope45":
            slope_tiles = synthesize_slope45_diagonals(donor)
            diag_words = object_words(rom, DIAGONAL_OBJECTS[0], 5)
            for w, dg in zip(diag_words[:4], slope_tiles):
                c = w & 0x3FF
                if c not in glyph:
                    glyph[c] = unflip(dg, w)
            # Keep 5th vanilla diagonal floor-edge tile ($0AB) remapped cleanly if ever referenced
            place(diag_words[4], 0xB0, 0, 1, None)
        else:
            diag = {
                w & 0x3FF: spec
                for w, spec in zip(object_words(rom, DIAGONAL_OBJECTS[0], 5), DIAGONAL_STYLES[diag_mode])
            }
            for obj in DIAGONAL_OBJECTS:
                for w in object_words(rom, obj, 5):
                    if (w & 0x3FF) in diag:
                        meta, col, row = diag[w & 0x3FF]
                        place(w, meta, col, row, None)

        table = gw.room_object_table(rom, rooms)
        skip_floors = set(style["skip_floors"])
        for r in rooms:
            p = gw.snes_pc(table + 3 * r)
            b = rom[gw.snes_pc(int.from_bytes(rom[p:p + 3], "little"))]
            for f in (b >> 4, b & 0xF):
                if f in skip_floors:
                    continue
                for k in range(8):
                    w = gw.rom_word(rom, gw.OBJ_TABLE_PC + f * 16 + 2 * k)
                    col, row = FLOOR_SHAPE[k]
                    place(w, floor_meta, col, row, votes if r in voters else None)

        floor_pal = donor.quadrant(floor_meta, 0, 0)[1]
        row_pal = {}
        for r in range(2, 8):
            tally = votes[r] or extra_votes[r]
            row_pal[r] = tally.most_common(1)[0][0] if tally else floor_pal
        row_pal.update(style["row_pal"])

        like = style["posterize_like"]
        snes = gw.palette(rom, gw.room_blockset_palette(rom, like)[1] if like is not None else pal_ids[0])
        mean = {}
        for i in range(1, 8):
            vals = []
            for r in range(6):
                w = snes[r * 15 + (i - 1)]
                vals.append(lum(((w & 31) * 8, ((w >> 5) & 31) * 8, ((w >> 10) & 31) * 8)))
            mean[i] = sum(vals) / len(vals)
        fp = donor.pal[floor_pal]
        donor_rank = sorted(range(4), key=lambda k: -lum(c5(fp[k])))
        ranked = sorted(mean, key=lambda i: -mean[i])
        quant = {0: 0}
        for n, i in enumerate(ranked):
            quant[i] = donor_rank[min(3, n * 4 // 7)] + 1

        inv = {}
        for i in range(1, 8):
            inv.setdefault(quant[i] - 1, i)
        accent = style["accent"]
        spare = sorted(
            (i for i in range(1, 8) if i not in inv.values()),
            key=lambda i: donor_rank.index(quant[i] - 1),
        )
        pix = {**inv, **{4 + k: i for k, i in enumerate(spare)}}
        words = []
        triforce_gold = style.get("triforce_gold_rgb")
        for r in range(2, 8):
            cols = donor.pal[row_pal[r]]
            half = [cols[quant[i] - 1] for i in range(1, 8)]
            if r in accent:
                acc = sorted(donor.pal[accent[r]][:3], key=lambda c: -lum(c5(c)))
                for k, i in enumerate(spare):
                    half[i - 1] = acc[k]
                if triforce_gold is not None:
                    half[inv[0] - 1] = _rgb8_to_5(triforce_gold)
            row = half + [cols[0]] + half
            for c in row:
                words.append(c[0] | (c[1] << 5) | (c[2] << 10))
        palettes.append(words)

        smap: dict[int, int] = {}
        cov: dict[str, dict | str] = {}
        for slot in sorted(slot_sheets):
            for s in sorted(slot_sheets[slot]):
                if s in smap or f"{s:02X}" in cov:
                    continue
                addr = st.ptr(rom, s)
                data, _ = st.decomp(rom, addr)
                if len(data) < 0x600:
                    cov[f"{s:02X}"] = "skipped: not a 0x600-byte 3bpp sheet"
                    continue
                orig = sc.sheet_to_grid(bytes(data[:0x600]))
                g = [row[:] for row in orig]
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
                                g[ty + y][tx + x] = inv[quant[v] - 1]
                    if dg:
                        donor_chars.append(c)
                    elif any(g[ty + y][tx + x] for y in range(8) for x in range(8)):
                        fallback.append(c)

                identical = (g == orig)
                remapped = not (skip_unchanged and identical)
                if remapped:
                    stem = f"{style['name']}.{s:02X}"
                    txt_data = sc.grid_to_text(g)
                    lz2_data = lz2.compress(sc.grid_to_sheet(g))
                    artifacts[f"{stem}.txt"] = txt_data
                    artifacts[f"{stem}.lz2"] = lz2_data
                    streams.append(stem)
                    stream_sizes[stem] = len(lz2_data)
                    smap[s] = len(streams)
                cov[f"{s:02X}"] = {
                    "slot": slot,
                    "remapped": remapped,
                    "donor_chars": [f"{c:03X}" for c in donor_chars],
                    "posterized_chars": len(fallback),
                }
        sheet_map.append(smap)
        coverage_styles[style["name"]] = {
            "rooms": [f"{r:02X}" for r in rooms],
            "row_palettes": {str(k): v for k, v in row_pal.items()},
            "row_votes": {str(r): dict(sorted(votes[r].items())) for r in range(2, 8)},
            "extra_row_votes": {str(r): dict(sorted(extra_votes[r].items())) for r in range(2, 8)},
            "palette_words": [f"{w:04X}" for w in words],
            "sheets": cov,
        }

    asm_text, metrics = render_abyss_asm(styles, sheet_map, streams, palettes, stream_sizes)
    artifacts["abyss_gbc.asm"] = asm_text
    coverage_doc = {
        "schema_version": 2,
        "styles_sha256": styles_sha,
        "streams": streams,
        "bank_metrics": metrics,
        "styles": coverage_styles,
    }
    artifacts["coverage.json"] = json.dumps(coverage_doc, indent=1) + "\n"
    metrics["styles"] = len(styles)
    metrics["rooms"] = sum(len(s["rooms"]) + len(s["more_rooms"]) for s in styles)
    metrics["streams"] = len(streams)
    return artifacts, metrics


def cmd_build(a: argparse.Namespace) -> int:
    out_dir = Path(a.out_dir)
    styles_path = Path(a.styles) if a.styles else (out_dir / "styles.json")
    rom = Path(a.rom).read_bytes()
    if not st.relocated(rom):
        print(
            "[WARN] --rom appears unpatched (sheet table not relocated); pass a built oos168x.sfc "
            "so Bank $01 wall_profile_selector object words match runtime.",
            file=sys.stderr,
        )
    donor_root = Path(a.donor) if a.donor else None
    disasm_root = Path(a.oracles_disasm) if a.oracles_disasm else (DEFAULT_DISASM if DEFAULT_DISASM.is_dir() else None)
    sodacoma_root = Path(a.sodacoma) if a.sodacoma else (DEFAULT_SODACOMA if DEFAULT_SODACOMA.is_dir() else None)

    artifacts, metrics = generate_artifacts(
        rom, styles_path, donor_root, disasm_root,
        sodacoma_root=sodacoma_root,
        diagonal=a.diagonal, deep=a.deep, stairs=a.stairs,
    )
    out_dir.mkdir(parents=True, exist_ok=True)
    expected_names = set(artifacts.keys())
    # Remove stale .txt/.lz2 files from earlier style configurations
    for stale in sorted(out_dir.iterdir()):
        if stale.suffix in (".txt", ".lz2") and stale.name not in expected_names:
            stale.unlink()
    for name, content in sorted(artifacts.items()):
        target = out_dir / name
        if isinstance(content, bytes):
            target.write_bytes(content)
        else:
            target.write_text(content, encoding="utf-8")

    print(
        f"styles={metrics['styles']} rooms={metrics['rooms']} streams={metrics['streams']} "
        f"lz2_bytes={metrics['total_lz2_bytes']} "
        f"bank5A_streams={metrics['bank5a_stream_bytes']}/{metrics['bank5a_stream_budget']} "
        f"bank5B_streams={metrics['bank5b_stream_bytes']}/{BANK_CAPACITY}"
    )
    return 0


def cmd_check(a: argparse.Namespace) -> int:
    out_dir = Path(a.out_dir)
    styles_path = Path(a.styles) if a.styles else (out_dir / "styles.json")
    errors: list[str] = []

    try:
        _, _, styles, styles_sha = load_styles_config(styles_path)
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(f"[FAIL] styles.json validation failed: {exc}", file=sys.stderr)
        return 1

    cov_path = out_dir / "coverage.json"
    asm_path = out_dir / "abyss_gbc.asm"
    if not cov_path.is_file():
        errors.append(f"Missing {cov_path}")
    if not asm_path.is_file():
        errors.append(f"Missing {asm_path}")
    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    cov_doc = json.loads(cov_path.read_text(encoding="utf-8"))
    if cov_doc.get("styles_sha256") != styles_sha:
        errors.append(
            f"styles.json digest drift: coverage.json has {cov_doc.get('styles_sha256')!r}, "
            f"styles.json has {styles_sha!r} (re-run build)"
        )

    cov_styles = cov_doc.get("styles", {})
    expected_style_names = [s["name"] for s in styles]
    if list(cov_styles.keys()) != expected_style_names:
        errors.append(
            f"Style order/set mismatch: styles.json={expected_style_names} vs coverage.json={list(cov_styles.keys())}"
        )

    streams = cov_doc.get("streams", [])
    stream_index = {stem: idx for idx, stem in enumerate(streams, 1)}
    sheet_map: list[dict[int, int]] = []
    palettes: list[list[int]] = []
    stream_sizes: dict[str, int] = {}
    expected_stems: set[str] = set()

    for style in styles:
        name = style["name"]
        centry = cov_styles.get(name)
        if not isinstance(centry, dict):
            errors.append(f"Missing coverage entry for style {name!r}")
            continue
        expected_rooms = [f"{r:02X}" for r in style["rooms"] + style["more_rooms"]]
        if centry.get("rooms") != expected_rooms:
            errors.append(f"Style {name!r} rooms mismatch: styles.json={expected_rooms} vs coverage.json={centry.get('rooms')}")
        for rk, rv in style["row_pal"].items():
            if centry.get("row_palettes", {}).get(str(rk)) != rv:
                errors.append(
                    f"Style {name!r} row_pal[{rk}] mismatch: styles.json={rv} vs coverage.json={centry.get('row_palettes', {}).get(str(rk))}"
                )
        pwords_hex = centry.get("palette_words", [])
        if len(pwords_hex) != 90:
            errors.append(f"Style {name!r} palette_words has {len(pwords_hex)} words (expected 90)")
            palettes.append([0] * 90)
        else:
            palettes.append([int(w, 16) for w in pwords_hex])

        smap: dict[int, int] = {}
        for shex, sinfo in centry.get("sheets", {}).items():
            if not isinstance(sinfo, dict) or not sinfo.get("remapped", True):
                continue
            stem = f"{name}.{shex}"
            expected_stems.add(stem)
            if stem not in stream_index:
                errors.append(f"Remapped sheet {stem} missing from coverage.json streams list")
            else:
                smap[int(shex, 16)] = stream_index[stem]
        sheet_map.append(smap)

    if set(streams) != expected_stems or len(streams) != len(expected_stems):
        errors.append(
            f"Stream list mismatch: streams={len(streams)} expected_remapped={len(expected_stems)}"
        )

    # Verify every .txt -> .lz2 matches deterministically and no orphan files exist
    for stem in streams:
        txt_p = out_dir / f"{stem}.txt"
        lz2_p = out_dir / f"{stem}.lz2"
        if not txt_p.is_file():
            errors.append(f"Missing {txt_p.name}")
            continue
        if not lz2_p.is_file():
            errors.append(f"Missing {lz2_p.name}")
            continue
        expected_lz2 = lz2.compress(sc.grid_to_sheet(sc.text_to_grid(txt_p.read_text(encoding="utf-8"))))
        actual_lz2 = lz2_p.read_bytes()
        if expected_lz2 != actual_lz2:
            errors.append(
                f"Drift in {lz2_p.name}: checked-in ({len(actual_lz2)} B) != recompressed {txt_p.name} ({len(expected_lz2)} B)"
            )
        stream_sizes[stem] = len(actual_lz2)

    disk_sheet_files = {p.name for p in out_dir.iterdir() if p.suffix in (".txt", ".lz2")}
    expected_sheet_files = {f"{stem}.{ext}" for stem in expected_stems for ext in ("txt", "lz2")}
    orphans = sorted(disk_sheet_files - expected_sheet_files)
    if orphans:
        errors.append(f"Orphan sheet files in {out_dir}: {', '.join(orphans[:10])}")

    if not errors:
        try:
            expected_asm, metrics = render_abyss_asm(styles, sheet_map, streams, palettes, stream_sizes)
        except ValueError as exc:
            errors.append(str(exc))
            expected_asm, metrics = "", {}
        else:
            actual_asm = asm_path.read_text(encoding="utf-8")
            if expected_asm != actual_asm:
                diff = "".join(
                    difflib.unified_diff(
                        actual_asm.splitlines(keepends=True),
                        expected_asm.splitlines(keepends=True),
                        fromfile="abyss_gbc.asm (checked-in)",
                        tofile="abyss_gbc.asm (expected)",
                        n=2,
                    )
                )
                errors.append(f"abyss_gbc.asm drift detected:\n{diff[:1200]}")

    # Optional full ROM + donor deterministic rebuild verification
    if not errors and a.rom:
        rom_bytes = Path(a.rom).read_bytes()
        donor_root = Path(a.donor) if a.donor else None
        disasm_root = Path(a.oracles_disasm) if a.oracles_disasm else (DEFAULT_DISASM if DEFAULT_DISASM.is_dir() else None)
        sodacoma_root = Path(a.sodacoma) if a.sodacoma else (DEFAULT_SODACOMA if DEFAULT_SODACOMA.is_dir() else None)
        rebuilt, _ = generate_artifacts(
            rom_bytes, styles_path, donor_root, disasm_root,
            sodacoma_root=sodacoma_root,
            diagonal=a.diagonal, deep=a.deep, stairs=a.stairs,
        )
        for name, expected in sorted(rebuilt.items()):
            p = out_dir / name
            if not p.is_file():
                errors.append(f"Full rebuild check: missing {name}")
                continue
            actual = p.read_bytes() if isinstance(expected, bytes) else p.read_text(encoding="utf-8")
            if actual != expected:
                errors.append(f"Full rebuild check: drift in {name}")

    if errors:
        for e in errors:
            print(f"[FAIL] {e}", file=sys.stderr)
        return 1

    print(
        f"[OK] abyss_gbc check passed: styles={len(styles)} "
        f"rooms={sum(len(s['rooms']) + len(s['more_rooms']) for s in styles)} "
        f"streams={len(streams)} lz2_bytes={metrics['total_lz2_bytes']} "
        f"bank5A_streams={metrics['bank5a_stream_bytes']}/{metrics['bank5a_stream_budget']} "
        f"bank5B_streams={metrics['bank5b_stream_bytes']}/{BANK_CAPACITY}"
    )
    return 0


def _find_z3ed(explicit: str | None) -> Path | None:
    if explicit:
        p = Path(explicit)
        return p if p.is_file() else None
    env = os.environ.get("YAZE_Z3ED")
    if env and Path(env).is_file():
        return Path(env)
    which = shutil.which("z3ed")
    if which:
        return Path(which)
    cand = Path.home() / ".local/bin/z3ed"
    return cand if cand.is_file() else None


def _load_font(size: int):
    from PIL import ImageFont
    for candidate in (
        "/System/Library/Fonts/Menlo.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        if os.path.exists(candidate):
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _bgr555_to_rgb(w: int) -> tuple[int, int, int]:
    return (((w & 31) * 255) // 31, (((w >> 5) & 31) * 255) // 31, (((w >> 10) & 31) * 255) // 31)


def _render_sheet_strip_fallback(rom: bytes, slots: list[int], pal_words: list[int], overrides: dict[int, bytes]):
    """Pure-Python 3bpp sheet strip preview fallback when z3ed is unavailable."""
    from PIL import Image
    # 7 sheets side by side (each 128x32 -> scaled 1x or stacked 2x4 -> 384x160)
    tile_w, tile_h = 128, 32
    cols_n = 2
    rows_n = (len(slots) + 1) // 2
    img = Image.new("RGB", (cols_n * tile_w + 8, rows_n * (tile_h + 14) + 8), (18, 18, 22))
    px = img.load()
    # Use row 2 palette (first 15 colors, index 0 = black)
    pal_rgb = [(0, 0, 0)] + [_bgr555_to_rgb(pal_words[i]) for i in range(7)]
    for idx, s in enumerate(slots):
        if s in overrides:
            raw, _ = lz2.decompress(overrides[s], 0)
        else:
            raw, _ = st.decomp(rom, st.ptr(rom, s))
        grid = sc.sheet_to_grid(bytes(raw[:0x600])) if len(raw) >= 0x600 else [[0] * 128 for _ in range(32)]
        ox = (idx % cols_n) * tile_w + 4
        oy = (idx // cols_n) * (tile_h + 14) + 14
        for y in range(min(32, len(grid))):
            for x in range(min(128, len(grid[y]))):
                px[ox + x, oy + y] = pal_rgb[grid[y][x] & 7]
    return img.resize((384, 384), Image.NEAREST)


def _render_room_z3ed(z3ed: Path, rom_path: Path, room: int, out_png: Path) -> None:
    proc = subprocess.run(
        [str(z3ed), "dungeon-render", f"--rom={rom_path}", f"--room=0x{room:03X}", f"--output={out_png}", "--format=json"],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"z3ed dungeon-render failed for 0x{room:03X}: {(proc.stderr or proc.stdout).strip()[:300]}")


def _patch_scratch_rom(rom: bytes, room: int, pal_words: list[int], sheet_lz2: dict[int, bytes]) -> bytes:
    """Create an in-memory scratch ROM copy with GBC sheets + palette patched for preview rendering."""
    buf = bytearray(rom)
    pc = 0x2D0000  # Bank $5A in unheadered 4MB LoROM
    for s, blob in sheet_lz2.items():
        bank = pc >> 15
        addr = 0x8000 | (pc & 0x7FFF)
        if addr + len(blob) > 0x10000:
            bank += 1
            pc = bank << 15
            addr = 0x8000
        buf[pc:pc + len(blob)] = blob
        if s < st.N:
            buf[st.pc(st.TBL_BANK) + s] = bank
            buf[st.pc(st.TBL_HIGH) + s] = (addr >> 8) & 0xFF
            buf[st.pc(st.TBL_LOW) + s] = addr & 0xFF
        if st.relocated(rom) or s >= st.N:
            buf[st.pc(st.NEW_BANK) + s] = bank
            buf[st.pc(st.NEW_HIGH) + s] = (addr >> 8) & 0xFF
            buf[st.pc(st.NEW_LOW) + s] = addr & 0xFF
        pc += len(blob)

    _, pid = gw.room_blockset_palette(rom, room)
    off = gw.rom_word(rom, gw.snes_pc(gw.PAL_INDEX) + pid)
    pal_pc = gw.snes_pc(gw.PAL_DATA) + off
    for i, w in enumerate(pal_words):
        struct.pack_into("<H", buf, pal_pc + 2 * i, w)
    return bytes(buf)


def cmd_preview_room(a: argparse.Namespace) -> int:
    from PIL import Image, ImageDraw

    out_dir = Path(a.out_dir)
    styles_path = Path(a.styles) if a.styles else (out_dir / "styles.json")
    _, _, styles, _ = load_styles_config(styles_path)
    cov_doc = json.loads((out_dir / "coverage.json").read_text(encoding="utf-8"))
    cov_styles = cov_doc.get("styles", {})

    rom_path = Path(a.rom)
    if not rom_path.is_file():
        print(f"[FAIL] ROM not found: {rom_path}", file=sys.stderr)
        return 1
    rom = rom_path.read_bytes()

    room_ids: list[int] = []
    for raw_arg in a.preview_room:
        for tok in raw_arg.split(","):
            tok = tok.strip()
            if tok:
                rid = parse_room_id(tok)
                if not (0 <= rid < gw.ROOM_COUNT):
                    print(f"[FAIL] Room ID 0x{rid:03X} out of range", file=sys.stderr)
                    return 1
                room_ids.append(rid)
    if not room_ids:
        print("[FAIL] No room IDs supplied to --preview-room", file=sys.stderr)
        return 1

    room_to_style: dict[int, tuple[int, dict]] = {}
    for sid, style in enumerate(styles, 1):
        for r in style["rooms"] + style["more_rooms"]:
            room_to_style[r] = (sid, style)

    z3ed = None if a.no_z3ed else _find_z3ed(a.z3ed)
    panel_size = a.panel_size
    sidebar_w = 340
    gap = 12
    f_hdr = _load_font(15)
    f_sub = _load_font(12)
    f_mono = _load_font(11)

    rows_imgs = []
    summary = []

    with tempfile.TemporaryDirectory(prefix="oos-abyss-preview-") as td:
        tdir = Path(td)
        for rid in room_ids:
            bs, pid = gw.room_blockset_palette(rom, rid)
            slots = gw.effective_slots(rom, bs)[:7]
            st_pair = room_to_style.get(rid)
            if st_pair is not None:
                sid, style = st_pair
                sname = style["name"]
                centry = cov_styles[sname]
                pal_words = [int(w, 16) for w in centry["palette_words"]]
                sheet_lz2: dict[int, bytes] = {}
                slot_stats = []
                total_donor = 0
                total_fallback = 0
                for slot_idx, s in enumerate(slots):
                    shex = f"{s:02X}"
                    sinfo = centry["sheets"].get(shex, {})
                    if isinstance(sinfo, dict):
                        remapped = bool(sinfo.get("remapped", True))
                        d_cnt = len(sinfo.get("donor_chars", []))
                        f_cnt = int(sinfo.get("posterized_chars", 0))
                    else:
                        remapped, d_cnt, f_cnt = False, 0, 0
                    total_donor += d_cnt
                    total_fallback += f_cnt
                    if remapped:
                        sheet_lz2[s] = (out_dir / f"{sname}.{shex}.lz2").read_bytes()
                    slot_stats.append({
                        "slot": slot_idx,
                        "sheet": shex,
                        "remapped": remapped,
                        "donor_chars": d_cnt,
                        "fallback_chars": f_cnt,
                    })
            else:
                sid, sname = 0, "vanilla"
                pal_words = gw.palette(rom, pid)
                sheet_lz2 = {}
                slot_stats = [
                    {"slot": i, "sheet": f"{s:02X}", "remapped": False, "donor_chars": 0, "fallback_chars": 64}
                    for i, s in enumerate(slots)
                ]
                total_donor, total_fallback = 0, len(slots) * 64

            if z3ed is not None:
                v_png = tdir / f"v_{rid:03X}.png"
                g_png = tdir / f"g_{rid:03X}.png"
                _render_room_z3ed(z3ed, rom_path, rid, v_png)
                if sid > 0:
                    patched = _patch_scratch_rom(rom, rid, pal_words, sheet_lz2)
                    patched_rom = tdir / f"gbc_{rid:03X}.sfc"
                    patched_rom.write_bytes(patched)
                    _render_room_z3ed(z3ed, patched_rom, rid, g_png)
                else:
                    shutil.copy(v_png, g_png)
                im_vanilla = Image.open(v_png).convert("RGB").resize((panel_size, panel_size), Image.NEAREST)
                im_gbc = Image.open(g_png).convert("RGB").resize((panel_size, panel_size), Image.NEAREST)
                render_mode = "z3ed"
            else:
                v_pal = gw.palette(rom, pid)
                im_vanilla = _render_sheet_strip_fallback(rom, slots, v_pal, {}).resize((panel_size, panel_size), Image.NEAREST)
                im_gbc = _render_sheet_strip_fallback(rom, slots, pal_words, sheet_lz2).resize((panel_size, panel_size), Image.NEAREST)
                render_mode = "sheet-fallback"

            row_h = panel_size + 28
            row_w = panel_size * 2 + sidebar_w + gap * 2
            row_canvas = Image.new("RGB", (row_w, row_h), (24, 24, 30))
            draw = ImageDraw.Draw(row_canvas)
            draw.text((4, 6), f"Room ${rid:03X}  BEFORE: Vanilla SNES (b{bs}/p{pid})", fill=(215, 220, 235), font=f_sub)
            draw.text(
                (panel_size + gap + 4, 6),
                f"AFTER: GBC '{sname}' (style #{sid}, $7EF3CA==$40)",
                fill=(130, 235, 165) if sid else (235, 180, 110),
                font=f_sub,
            )
            row_canvas.paste(im_vanilla, (0, 26))
            row_canvas.paste(im_gbc, (panel_size + gap, 26))

            sx = panel_size * 2 + gap * 2
            draw.rectangle((sx, 26, row_w - 2, row_h - 2), fill=(18, 19, 25), outline=(60, 64, 78))
            y = 34
            draw.text((sx + 10, y), f"Room 0x{rid:03X}  ->  {sname} (#{sid})", fill=(255, 255, 255), font=f_sub)
            y += 20
            draw.text((sx + 10, y), f"Header: b{bs} / p{pid}  |  Renderer: {render_mode}", fill=(180, 190, 210), font=f_mono)
            y += 16
            draw.text((sx + 10, y), "Gate: $7EF3CA == $40 (LW $00 / SW $80 = SNES)", fill=(160, 210, 255), font=f_mono)
            y += 20
            tot = max(1, total_donor + total_fallback)
            donor_pct = (100.0 * total_donor) / tot
            draw.text(
                (sx + 10, y),
                f"Coverage: {total_donor} donor / {total_fallback} fallback ({donor_pct:.1f}%)",
                fill=(255, 235, 140),
                font=f_mono,
            )
            y += 18
            # Coverage bar
            bar_w = sidebar_w - 22
            donor_w = int(bar_w * total_donor / tot)
            draw.rectangle((sx + 10, y, sx + 10 + bar_w, y + 10), fill=(70, 75, 95))
            if donor_w > 0:
                draw.rectangle((sx + 10, y, sx + 10 + donor_w, y + 10), fill=(75, 200, 120))
            y += 18
            draw.text((sx + 10, y), "Slot Sheet Mode    Donor  Fallback", fill=(160, 170, 190), font=f_mono)
            y += 15
            for ss in slot_stats:
                mode_lbl = "REMAP " if ss["remapped"] else "PASS  "
                col_fill = (130, 230, 155) if ss["donor_chars"] else ((180, 200, 240) if ss["remapped"] else (150, 155, 170))
                draw.text(
                    (sx + 10, y),
                    f"  {ss['slot']}   ${ss['sheet']}  {mode_lbl}  {ss['donor_chars']:3d}     {ss['fallback_chars']:3d}",
                    fill=col_fill,
                    font=f_mono,
                )
                y += 15

            if sid > 0:
                y += 8
                draw.text((sx + 10, y), "GBC Palette Rows 2-7 (shades 1-7):", fill=(180, 190, 210), font=f_mono)
                y += 16
                for pr in range(3):
                    for col_idx, row_off in enumerate((pr, pr + 3)):
                        base_x = sx + 10 + col_idx * 160
                        draw.text((base_x, y + 1), f"r{row_off+2}:", fill=(170, 175, 195), font=f_mono)
                        for ci in range(7):
                            rgb = _bgr555_to_rgb(pal_words[row_off * 15 + ci])
                            bx = base_x + 24 + ci * 18
                            draw.rectangle((bx, y, bx + 15, y + 12), fill=rgb, outline=(45, 45, 55))
                    y += 16

            rows_imgs.append(row_canvas)
            summary.append({
                "room": f"0x{rid:03X}",
                "style_id": sid,
                "style": sname,
                "blockset": bs,
                "palette": pid,
                "renderer": render_mode,
                "donor_chars": total_donor,
                "fallback_chars": total_fallback,
                "donor_pct": round(donor_pct, 1),
                "slots": slot_stats,
            })

    title_h = 34
    sheet_w = max(r.width for r in rows_imgs) + 2 * gap
    sheet_h = title_h + sum(r.height for r in rows_imgs) + gap * (len(rows_imgs) + 1)
    sheet = Image.new("RGB", (sheet_w, sheet_h), (14, 15, 20))
    draw = ImageDraw.Draw(sheet)
    draw.text(
        (gap, 10),
        f"Eon Abyss GBC Interiors Preview ({len(room_ids)} room{'s' if len(room_ids) != 1 else ''}) — Vanilla SNES vs GBC ($7EF3CA == $40)",
        fill=(255, 255, 255),
        font=f_hdr,
    )
    y = title_h + gap
    for rimg in rows_imgs:
        sheet.paste(rimg, (gap, y))
        y += rimg.height + gap

    out_png = Path(a.out) if a.out else Path(f"/tmp/abyss_gbc_preview_{'_'.join(f'{r:03X}' for r in room_ids)}.png")
    out_png.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(out_png)
    print(json.dumps({"out": str(out_png), "rooms": summary}, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--check", action="store_true", help="Verify checked-in .txt/.lz2/abyss_gbc.asm match styles.json")
    ap.add_argument("--preview-room", action="append", default=[], metavar="ROOM_ID[,ROOM_ID...]",
                    help="Render vanilla SNES vs GBC contact sheet for one or more hex room IDs")
    ap.add_argument("--rom", default=str(REPO / "Roms/oos168x.sfc"), help="Read-only ROM path")
    ap.add_argument("--donor", help="Prebuilt gbc_interiors donor directory")
    ap.add_argument("--oracles-disasm", help="Local oracles-disasm checkout for disasm-backed donor recipes")
    ap.add_argument("--sodacoma", help="Local SodaComa New Tileset (v2) directory for png_grid donor recipes")
    ap.add_argument("--styles", help="Override path to styles.json (default: <out-dir>/styles.json)")
    ap.add_argument("--out-dir", default=str(OUT), help="Output/checked-in abyss_gbc directory")
    ap.add_argument("--out", help="Output PNG path for --preview-room")
    ap.add_argument("--z3ed", help="Explicit z3ed binary path for --preview-room")
    ap.add_argument("--no-z3ed", action="store_true", help="Force pure-Python sheet-strip preview fallback")
    ap.add_argument("--panel-size", type=int, default=320, help="Square pixel size of each room render panel")
    ap.add_argument("--diagonal", choices=sorted(DIAGONAL_STYLES), default=None)
    ap.add_argument("--deep", choices=sorted(DEEP_STYLES), default=None)
    ap.add_argument("--stairs", choices=sorted(STAIR_STYLES), default=None)
    return ap


def main(argv: list[str] | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)
    mode = None
    if raw_argv and raw_argv[0] in ("build", "check", "preview-room"):
        mode = raw_argv.pop(0)
    ap = build_parser()
    a = ap.parse_args(raw_argv)

    if mode == "check" or a.check:
        # Only run full ROM rebuild check if --rom was explicitly supplied
        if "--rom" not in raw_argv and not any(tok.startswith("--rom=") for tok in raw_argv):
            a.rom = None
        return cmd_check(a)
    if mode == "preview-room" or a.preview_room:
        return cmd_preview_room(a)
    if mode == "build":
        return cmd_build(a)
    ap.print_help()
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
