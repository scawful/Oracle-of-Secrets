#!/usr/bin/env python3
"""Collaborative Overworld Region Visual Review & Yaze Diff Board Generator.

Generates high-contrast side-by-side diagnostic PNG boards for Oracle of Secrets
rev5 OOSOW192 overworld regions:
  - Left Panel:  True-color stitched region render (via z3ed overworld-render
                 deduplicated per parent area, or pure-Python fallback) with
                 map ID badges, parent/cross-world dividers, and tile rulers.
  - Right Panel: Dimmed map + OverworldTileTypes collision overlay (walkable
                 green, shallow cyan, deep blue, solid/cliff amber, ledge gold,
                 interactive olive) + bright red seam mismatch ticks + purple
                 edge-guard markers + yellow entrance/exit pins + magenta
                 placed sprite markers with hex IDs.
  - Optional 3rd Panel (--diff-rom <prev_rom>): Highlights every changed Tile16
                 cell after edits in Yaze and reports changed clusters per map.

Named presets:
  zora-coast   : 4x3 ($17/$1F/$27 + $90-$92/$98-$9A/$A0-$A2)
  goron-coast  : 4x3 ($2F/$37/$3F + $A8-$AA/$B0-$B2/$B8-$BA)
  courage-lyra : 5x4 ($A3-$A7/$AB-$AF/$B3-$B7/$BB-$BF)
  deku-swamp   : 5x2 ($2D-$2F/$A8-$A9 + $35-$37/$B0-$B1)

Usage:
  python3 Scripts/Tools/overworld_region_board.py --rom <rom> --region zora-coast --out board.png
  python3 Scripts/Tools/overworld_region_board.py --rom <rom> --all-regions --out-dir /tmp/boards
  python3 Scripts/Tools/overworld_region_board.py --rom <new> --diff-rom <prev> --region goron-coast --out diff.png
"""
from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageEnhance, ImageFont

ROOT = Path(__file__).resolve().parents[2]
for _rel in ("Scripts/Build", "Scripts/Tools"):
    _p = str(ROOT / _rel)
    if _p not in sys.path:
        sys.path.insert(0, _p)

import check_overworld_seams as cos  # noqa: E402
import scene_intent_common as sic  # noqa: E402

# Concise Special Overworld & East Kalyxo labels (grounded in lyra_edge_guard.asm + project.yaze)
DEFAULT_MAP_NAMES: dict[int, str] = {
    0x17: "S.Graveyard",
    0x1F: "Zora Falls",
    0x27: "E.Kalyxo",
    0x2D: "Tail Pond",
    0x2E: "Tail Cave",
    0x2F: "Tail Palace",
    0x35: "Loom S.",
    0x36: "Goron Mtn",
    0x37: "SE Coast",
    0x3F: "SE Cape",
    0x80: "Tail Woods",
    0x81: "Korok NW",
    0x82: "Korok NE",
    0x83: "Garrison N",
    0x87: "Sky Tower",
    0x8C: "Sky Land",
    0x8D: "Sky Brg W",
    0x8E: "Sky Brg E",
    0x8F: "Sky East",
    0x90: "Sea Zora N",
    0x91: "Wisdom Shr",
    0x92: "North Reef",
    0x98: "Sea Zora S",
    0x99: "Zora Quay",
    0x9A: "C-Island",
    0xA0: "Zora Cst W",
    0xA1: "Zora Cst E",
    0xA2: "Lyra Sea",
    0xA3: "Twin-Tree",
    0xA4: "Twin Sand",
    0xA5: "Tiny Atoll",
    0xA6: "Courage NW",
    0xA7: "Courage NE",
    0xA8: "Deku Grv W",
    0xA9: "Deku Grv E",
    0xAA: "Square Isl",
    0xAB: "Hut Island",
    0xAC: "Green Isl W",
    0xAD: "Green Isl E",
    0xAE: "Courage SW",
    0xAF: "Courage SE",
    0xB0: "Goron NW",
    0xB1: "Goron NE",
    0xB2: "Sea/Cliff",
    0xB3: "Crescent NW",
    0xB4: "Crescent NE",
    0xB5: "Tower Isl N",
    0xB6: "Sandbar",
    0xB7: "Cresc Sand",
    0xB8: "Goron SW",
    0xB9: "Goron SE",
    0xBA: "Harbor/Sea",
    0xBB: "Crescent SW",
    0xBC: "Crescent SE",
    0xBD: "Tower Isl S",
    0xBE: "Snow Isl W",
    0xBF: "Snow Isl E",
}

TERRAIN_RGBA: dict[str, tuple[int, int, int, int]] = {
    "walkable": (46, 204, 113, 118),
    "shallow_water": (0, 215, 240, 145),
    "deep_water": (28, 88, 225, 155),
    "solid": (235, 138, 30, 135),
    "ledge": (245, 220, 80, 130),
    "interactive": (162, 212, 55, 128),
}


def _load_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for cand in (
        "/System/Library/Fonts/Menlo.ttc",
        "/System/Library/Fonts/SFNSMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
    ):
        p = Path(cand)
        if p.is_file():
            try:
                return ImageFont.truetype(str(p), size=size)
            except OSError:
                pass
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


def _parse_custom_grid(spec: str) -> list[list[int]]:
    """Parse --grid '90,91,92;98,99,9A' into a 2D list of map IDs."""
    rows: list[list[int]] = []
    for row_str in spec.strip().split(";"):
        row_str = row_str.strip()
        if not row_str:
            continue
        row = [sic.parse_hex_int(tok if tok.strip().startswith(("0x", "$")) else "0x" + tok.strip())
               for tok in row_str.split(",") if tok.strip()]
        rows.append(row)
    if not rows or any(len(r) != len(rows[0]) for r in rows):
        raise ValueError("Custom --grid must be a non-empty rectangular matrix of hex map IDs")
    return rows


def _render_screen_python(
    ctx: cos.OverworldContext,
    map_id: int,
    all_sheets: dict[int, list[tuple[int, ...]]],
    cell_px: int,
) -> Image.Image:
    """Pure-Python fallback true-color screen renderer (for synthetic ROMs or --no-z3ed)."""
    slot_chars = sic.load_overworld_slot_chars(ctx.rom, map_id, all_sheets)
    pal128 = sic.decode_overworld_palette_128(ctx.rom, map_id)
    grid = ctx.screen_grid(map_id)
    canvas = Image.new("RGBA", (512, 512), (*pal128[0], 255))
    tile_cache: dict[int, Image.Image] = {}
    for ty in range(32):
        for tx in range(32):
            tid = grid[ty][tx]
            im = tile_cache.get(tid)
            if im is None:
                words = ctx.tile16_words(map_id, tid)
                im = sic.render_tile16_rgba(words, slot_chars, pal128, transparent_zero=False)
                tile_cache[tid] = im
            canvas.paste(im, (tx * 16, ty * 16))
    if cell_px != 512:
        canvas = canvas.resize((cell_px, cell_px), Image.Resampling.NEAREST)
    return canvas


def render_grid_screens(
    rom_path: Path,
    ctx: cos.OverworldContext,
    grid_ids: list[list[int]],
    *,
    cell_px: int = 256,
    use_z3ed: bool = True,
    z3ed_bin: Path | None = None,
) -> dict[int, Image.Image]:
    """Render every physical map in grid_ids to a cell_px x cell_px RGBA image."""
    unique_maps = sorted({m for row in grid_ids for m in row})
    renders: dict[int, Image.Image] = {}

    resolved_z3ed = (z3ed_bin or sic.find_z3ed_bin()) if use_z3ed else None
    if resolved_z3ed is not None:
        # Deduplicate z3ed overworld-render calls by parent area ID
        parents_needed: dict[int, list[int]] = {}
        for m in unique_maps:
            par, _sz = ctx.parent_and_size(m)
            parents_needed.setdefault(par, []).append(m)

        with sic.staged_ro_rom(rom_path) as (ro_copy, _sha):
            with tempfile.TemporaryDirectory(prefix="oos_ow_board_") as tmp:
                tmp_dir = Path(tmp)
                for par, members in sorted(parents_needed.items()):
                    out_png = tmp_dir / f"area_{par:02X}.png"
                    proc = subprocess.run(
                        [
                            str(resolved_z3ed),
                            "overworld-render",
                            f"--rom={ro_copy}",
                            f"--screen=0x{par:02X}",
                            f"--out={out_png}",
                        ],
                        capture_output=True,
                        text=True,
                    )
                    if proc.returncode == 0 and out_png.is_file():
                        full_im = Image.open(out_png).convert("RGBA")
                        fw, fh = full_im.size
                        for m in members:
                            dx = (m - par) % 8
                            dy = (m - par) // 8
                            x0, y0 = dx * 512, dy * 512
                            if x0 + 512 <= fw and y0 + 512 <= fh:
                                crop = full_im.crop((x0, y0, x0 + 512, y0 + 512))
                            else:
                                crop = full_im.crop((0, 0, min(512, fw), min(512, fh)))
                            if crop.size != (cell_px, cell_px):
                                crop = crop.resize((cell_px, cell_px), Image.Resampling.NEAREST)
                            renders[m] = crop

    missing = [m for m in unique_maps if m not in renders]
    if missing:
        needed_sheets: set[int] = set()
        for m in missing:
            needed_sheets.update(sic.load_area_static_graphics(ctx.rom, m))
            needed_sheets.add(sic.load_area_animated_sheet(ctx.rom, m))
        all_sheets = sic.decode_sheet_chars(ctx.rom, needed_sheets)
        for m in missing:
            renders[m] = _render_screen_python(ctx, m, all_sheets, cell_px)

    return renders


def _is_geographic_pair(map_a: int, map_b: int, axis: str) -> tuple[bool, bool]:
    """Return (is_real_adjacent_seam, is_cross_world)."""
    if axis == "H":
        if (map_a, map_b) in cos.CROSS_WORLD_SEAMS:
            return True, True
        if (map_a >> 6) == (map_b >> 6) and (map_a & 7) < 7 and map_b == map_a + 1:
            return True, False
    else:
        if (map_a >> 6) == (map_b >> 6) and ((map_a & 0x3F) // 8) < 7 and map_b == map_a + 8:
            return True, False
    return False, False


def _draw_dashed_line(
    draw: ImageDraw.ImageDraw,
    p0: tuple[int, int],
    p1: tuple[int, int],
    color: tuple[int, int, int, int],
    width: int = 2,
    dash: int = 6,
    gap: int = 4,
) -> None:
    x0, y0 = p0
    x1, y1 = p1
    if x0 == x1:
        y = y0
        while y < y1:
            draw.line([(x0, y), (x0, min(y + dash, y1))], fill=color, width=width)
            y += dash + gap
    else:
        x = x0
        while x < x1:
            draw.line([(x, y0), (min(x + dash, x1), y0)], fill=color, width=width)
            x += dash + gap


def _draw_badge(
    draw: ImageDraw.ImageDraw,
    x: int,
    y: int,
    text: str,
    font: Any,
    bg: tuple[int, int, int, int] = (12, 16, 24, 210),
    fg: tuple[int, int, int, int] = (245, 248, 255, 255),
    border: tuple[int, int, int, int] | None = (110, 140, 185, 210),
    pad_x: int = 4,
    pad_y: int = 2,
) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    rect = [x, y, x + tw + pad_x * 2, y + th + pad_y * 2]
    draw.rectangle(rect, fill=bg, outline=border, width=1 if border else 0)
    draw.text((x + pad_x - bbox[0], y + pad_y - bbox[1]), text, fill=fg, font=font)
    return rect[2] - rect[0], rect[3] - rect[1]


def compute_tile16_diff(
    ctx_new: cos.OverworldContext,
    ctx_prev: cos.OverworldContext,
    grid_ids: list[list[int]],
) -> dict[int, list[tuple[int, int, int, int]]]:
    """Return {map_id: [(tx, ty, prev_tid, new_tid)]} for every changed Tile16 cell."""
    diffs: dict[int, list[tuple[int, int, int, int]]] = {}
    for row in grid_ids:
        for m in row:
            if m in diffs:
                continue
            g_new = ctx_new.screen_grid(m)
            g_prev = ctx_prev.screen_grid(m)
            changed: list[tuple[int, int, int, int]] = []
            for ty in range(32):
                for tx in range(32):
                    if g_new[ty][tx] != g_prev[ty][tx]:
                        changed.append((tx, ty, g_prev[ty][tx], g_new[ty][tx]))
            diffs[m] = changed
    return diffs


def build_region_board(
    rom_path: Path,
    grid_ids: list[list[int]],
    *,
    title: str,
    region_key: str = "custom",
    cell_px: int = 256,
    phase: int = 1,
    use_z3ed: bool = True,
    z3ed_bin: Path | None = None,
    diff_rom_path: Path | None = None,
    root: Path = ROOT,
) -> tuple[Image.Image, dict[str, Any]]:
    """Render side-by-side collaborative region board image + structured metadata."""
    rom = sic.load_rom_bytes(rom_path)
    ctx = cos.OverworldContext(rom, root=root)
    rom_sha = hashlib.sha256(rom).hexdigest()[:12]

    rows_n = len(grid_ids)
    cols_n = len(grid_ids[0])
    panel_w = cols_n * cell_px
    panel_h = rows_n * cell_px
    tile_px = cell_px / 32.0
    sub_px = tile_px / 2.0

    screens = render_grid_screens(
        rom_path, ctx, grid_ids, cell_px=cell_px, use_z3ed=use_z3ed, z3ed_bin=z3ed_bin
    )

    # Load readable map names
    labels = sic.load_resource_labels(root).get("overworld_map", {})

    def map_label(m: int) -> str:
        if m in DEFAULT_MAP_NAMES:
            return DEFAULT_MAP_NAMES[m]
        for k in (f"0x{m:02x}", f"{m}", f"${m:02x}"):
            if k in labels:
                return labels[k][:14]
        return ""

    # ------------------------------------------------------------------
    # Panel 1: True-Color Stitched Region
    # ------------------------------------------------------------------
    left_panel = Image.new("RGBA", (panel_w, panel_h), (16, 20, 28, 255))
    for r, row in enumerate(grid_ids):
        for c, m in enumerate(row):
            left_panel.paste(screens[m], (c * cell_px, r * cell_px))

    # ------------------------------------------------------------------
    # Panel 2: Diagnostic Collision, Seam & Entity Overlay
    # ------------------------------------------------------------------
    dimmed = ImageEnhance.Brightness(left_panel.convert("RGB")).enhance(0.36).convert("RGBA")
    overlay_layer = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay_layer)

    for r, row in enumerate(grid_ids):
        for c, m in enumerate(row):
            g = ctx.screen_grid(m)
            ox = c * cell_px
            oy = r * cell_px
            for ty in range(32):
                for tx in range(32):
                    tid = g[ty][tx]
                    q_classes = ctx.tile16_quadrant_classes(m, tid)
                    if len(set(q_classes)) == 1:
                        col = TERRAIN_RGBA[q_classes[0]]
                        x0 = int(round(ox + tx * tile_px))
                        y0 = int(round(oy + ty * tile_px))
                        x1 = int(round(ox + (tx + 1) * tile_px)) - 1
                        y1 = int(round(oy + (ty + 1) * tile_px)) - 1
                        ov_draw.rectangle([x0, y0, x1, y1], fill=col)
                    else:
                        for qi, (qx, qy) in enumerate(((0, 0), (1, 0), (0, 1), (1, 1))):
                            col = TERRAIN_RGBA[q_classes[qi]]
                            x0 = int(round(ox + tx * tile_px + qx * sub_px))
                            y0 = int(round(oy + ty * tile_px + qy * sub_px))
                            x1 = int(round(ox + tx * tile_px + (qx + 1) * sub_px)) - 1
                            y1 = int(round(oy + ty * tile_px + (qy + 1) * sub_px)) - 1
                            ov_draw.rectangle([x0, y0, max(x0, x1), max(y0, y1)], fill=col)

    right_panel = Image.alpha_composite(dimmed, overlay_layer)

    # ------------------------------------------------------------------
    # Seam grid dividers & Seam Mismatch Ticks
    # ------------------------------------------------------------------
    left_draw = ImageDraw.Draw(left_panel, "RGBA")
    right_draw = ImageDraw.Draw(right_panel, "RGBA")
    seam_records: list[dict[str, Any]] = []
    error_seam_count = 0
    warn_seam_count = 0
    total_error_tiles = 0
    blocked_seam_count = 0

    # Evaluate every internal border in the displayed grid
    for r in range(rows_n):
        for c in range(cols_n):
            m = grid_ids[r][c]
            par_m, _ = ctx.parent_and_size(m)

            # East border with (r, c+1)
            if c + 1 < cols_n:
                nb = grid_ids[r][c + 1]
                par_nb, _ = ctx.parent_and_size(nb)
                x = (c + 1) * cell_px
                y0, y1 = r * cell_px, (r + 1) * cell_px
                is_adj, is_cw = _is_geographic_pair(m, nb, "H")
                if par_m == par_nb:
                    _draw_dashed_line(left_draw, (x, y0), (x, y1), (130, 215, 255, 110), width=1, dash=4, gap=4)
                    _draw_dashed_line(right_draw, (x, y0), (x, y1), (130, 215, 255, 110), width=1, dash=4, gap=4)
                elif is_cw:
                    _draw_dashed_line(left_draw, (x, y0), (x, y1), (255, 210, 60, 235), width=2, dash=8, gap=4)
                    _draw_dashed_line(right_draw, (x, y0), (x, y1), (255, 210, 60, 235), width=2, dash=8, gap=4)
                else:
                    left_draw.line([(x, y0), (x, y1)], fill=(235, 240, 250, 165), width=1)
                    right_draw.line([(x, y0), (x, y1)], fill=(235, 240, 250, 165), width=1)

                if is_adj and par_m != par_nb:
                    permitted = is_cw or ctx.special_seam_permitted(m, nb, "H")
                    if not permitted:
                        blocked_seam_count += 1
                        _draw_dashed_line(right_draw, (x, y0), (x, y1), (190, 95, 255, 230), width=3, dash=5, gap=5)
                    else:
                        res = cos.audit_seam_pair(ctx, m, nb, "H", is_cw)
                        seam_records.append(res)
                        if res["error_tile_count"] > 0:
                            error_seam_count += 1
                            total_error_tiles += res["error_tile_count"]
                        elif res["warn_tile_count"] > 0:
                            warn_seam_count += 1
                        for ti in res["warn_tiles"]:
                            ty0 = int(round(y0 + ti * tile_px))
                            ty1 = int(round(y0 + (ti + 1) * tile_px)) - 1
                            right_draw.rectangle([x - 3, ty0, x + 3, ty1], fill=(255, 195, 20, 230))
                        for ti in res["error_tiles"]:
                            ty0 = int(round(y0 + ti * tile_px))
                            ty1 = int(round(y0 + (ti + 1) * tile_px)) - 1
                            right_draw.rectangle([x - 4, ty0, x + 4, ty1], fill=(255, 30, 48, 255), outline=(255, 240, 240, 230), width=1)

            # South border with (r+1, c)
            if r + 1 < rows_n:
                nb = grid_ids[r + 1][c]
                par_nb, _ = ctx.parent_and_size(nb)
                y = (r + 1) * cell_px
                x0, x1 = c * cell_px, (c + 1) * cell_px
                is_adj, is_cw = _is_geographic_pair(m, nb, "V")
                if par_m == par_nb:
                    _draw_dashed_line(left_draw, (x0, y), (x1, y), (130, 215, 255, 110), width=1, dash=4, gap=4)
                    _draw_dashed_line(right_draw, (x0, y), (x1, y), (130, 215, 255, 110), width=1, dash=4, gap=4)
                else:
                    left_draw.line([(x0, y), (x1, y)], fill=(235, 240, 250, 165), width=1)
                    right_draw.line([(x0, y), (x1, y)], fill=(235, 240, 250, 165), width=1)

                if is_adj and par_m != par_nb:
                    permitted = ctx.special_seam_permitted(m, nb, "V")
                    if not permitted:
                        blocked_seam_count += 1
                        _draw_dashed_line(right_draw, (x0, y), (x1, y), (190, 95, 255, 230), width=3, dash=5, gap=5)
                    else:
                        res = cos.audit_seam_pair(ctx, m, nb, "V", is_cw)
                        seam_records.append(res)
                        if res["error_tile_count"] > 0:
                            error_seam_count += 1
                            total_error_tiles += res["error_tile_count"]
                        elif res["warn_tile_count"] > 0:
                            warn_seam_count += 1
                        for ti in res["warn_tiles"]:
                            tx0 = int(round(x0 + ti * tile_px))
                            tx1 = int(round(x0 + (ti + 1) * tile_px)) - 1
                            right_draw.rectangle([tx0, y - 3, tx1, y + 3], fill=(255, 195, 20, 230))
                        for ti in res["error_tiles"]:
                            tx0 = int(round(x0 + ti * tile_px))
                            tx1 = int(round(x0 + (ti + 1) * tile_px)) - 1
                            right_draw.rectangle([tx0, y - 4, tx1, y + 4], fill=(255, 30, 48, 255), outline=(255, 240, 240, 230), width=1)

    # Map coordinates lookup for entity overlays
    grid_pos: dict[int, tuple[int, int]] = {
        grid_ids[r][c]: (c, r) for r in range(rows_n) for c in range(cols_n)
    }

    # Fonts
    font_title = _load_font(17)
    font_sub = _load_font(12)
    font_badge = _load_font(max(10, cell_px // 23))
    font_tiny = _load_font(max(9, cell_px // 28))

    # ------------------------------------------------------------------
    # Entrances & Exits markers (Right panel — yellow squares)
    # ------------------------------------------------------------------
    shown_entrances = 0
    shown_exits = 0
    for ent in ctx.read_entrances():
        par = ent["parent_id"]
        cx, cy = ent["local_tile_x"], ent["local_tile_y"]
        if not (0 <= cx < 64 and 0 <= cy < 64):
            continue
        phys = par + (8 if cy >= 32 else 0) + (1 if cx >= 32 else 0)
        if phys not in grid_pos:
            continue
        col_i, row_i = grid_pos[phys]
        lx, ly = cx % 32, cy % 32
        px = int(round(col_i * cell_px + (lx + 0.5) * tile_px))
        py = int(round(row_i * cell_px + (ly + 0.5) * tile_px))
        rad = max(4, int(round(tile_px * 0.65)))
        right_draw.rectangle(
            [px - rad, py - rad, px + rad, py + rad],
            fill=(255, 235, 40, 95),
            outline=(255, 240, 50, 255),
            width=2,
        )
        _draw_badge(
            right_draw, px + rad + 2, max(0, py - 8), f"E{ent['entrance_id']:02X}",
            font_tiny, bg=(45, 38, 0, 215), fg=(255, 242, 90, 255), border=(255, 230, 50, 220),
            pad_x=2, pad_y=1,
        )
        shown_entrances += 1

    for ex in ctx.read_exits():
        par = ex["parent_id"]
        fx, fy = ex["foot_tile_x"], ex["foot_tile_y"]
        if not (0 <= fx < 64 and 0 <= fy < 64):
            continue
        phys = par + (8 if fy >= 32 else 0) + (1 if fx >= 32 else 0)
        if phys not in grid_pos:
            continue
        col_i, row_i = grid_pos[phys]
        lx, ly = fx % 32, fy % 32
        px = int(round(col_i * cell_px + (lx + 0.5) * tile_px))
        py = int(round(row_i * cell_px + (ly + 0.5) * tile_px))
        rad = max(3, int(round(tile_px * 0.5)))
        right_draw.rectangle(
            [px - rad, py - rad, px + rad, py + rad],
            outline=(255, 200, 30, 255),
            width=2,
        )
        shown_exits += 1

    # ------------------------------------------------------------------
    # Placed Sprites (Right panel — magenta dots + hex IDs)
    # ------------------------------------------------------------------
    # Sprites live on the parent area list (in parent 0..63 coords)
    shown_sprites = 0
    seen_parents_spr: set[int] = set()
    for r, row in enumerate(grid_ids):
        for c, m in enumerate(row):
            par, _ = ctx.parent_and_size(m)
            if par in seen_parents_spr:
                continue
            seen_parents_spr.add(par)
            for sx, sy, sid in ctx.read_sprites(par, phase=phase):
                phys = par + (8 if sy >= 32 else 0) + (1 if sx >= 32 else 0)
                if phys not in grid_pos:
                    continue
                col_i, row_i = grid_pos[phys]
                lx, ly = sx % 32, sy % 32
                px = int(round(col_i * cell_px + (lx + 0.5) * tile_px))
                py = int(round(row_i * cell_px + (ly + 0.5) * tile_px))
                rad = max(3, int(round(tile_px * 0.48)))
                right_draw.ellipse(
                    [px - rad, py - rad, px + rad, py + rad],
                    fill=(255, 45, 220, 245),
                    outline=(255, 255, 255, 240),
                    width=1,
                )
                _draw_badge(
                    right_draw,
                    min(panel_w - 28, px + rad + 2),
                    max(0, py - 7),
                    f"{sid:02X}",
                    font_tiny,
                    bg=(58, 8, 52, 215),
                    fg=(255, 175, 245, 255),
                    border=(255, 70, 225, 210),
                    pad_x=2,
                    pad_y=1,
                )
                shown_sprites += 1

    # ------------------------------------------------------------------
    # Map ID Badges on both Left & Right panels
    # ------------------------------------------------------------------
    for r, row in enumerate(grid_ids):
        for c, m in enumerate(row):
            ox, oy = c * cell_px, r * cell_px
            par, sz = ctx.parent_and_size(m)
            sz_tag = {0: "", 1: "L", 2: "W", 3: "T"}.get(sz, "")
            name = map_label(m)
            label_left = f"${m:02X}" + (f" {name}" if name else "")
            if par != m:
                label_right = f"${m:02X} (p${par:02X}{sz_tag})"
            else:
                label_right = f"${m:02X}" + (f" [{sz_tag}]" if sz_tag else "")
            _draw_badge(left_draw, ox + 4, oy + 4, label_left, font_badge)
            _draw_badge(
                right_draw, ox + 4, oy + 4, label_right, font_badge,
                bg=(10, 14, 22, 225), fg=(225, 236, 255, 255), border=(95, 125, 170, 210),
            )

    # ------------------------------------------------------------------
    # Optional 3rd Panel: Yaze Diff Highlight (--diff-rom <prev_rom>)
    # ------------------------------------------------------------------
    diff_panel: Image.Image | None = None
    diff_summary: dict[str, Any] | None = None
    if diff_rom_path is not None:
        prev_rom = sic.load_rom_bytes(diff_rom_path)
        ctx_prev = cos.OverworldContext(prev_rom, root=root)
        diffs = compute_tile16_diff(ctx, ctx_prev, grid_ids)
        diff_base = ImageEnhance.Brightness(left_panel.convert("RGB")).enhance(0.42).convert("RGBA")
        diff_ov = Image.new("RGBA", (panel_w, panel_h), (0, 0, 0, 0))
        d_draw = ImageDraw.Draw(diff_ov)
        total_changed = 0
        per_map_changed: dict[str, int] = {}
        for r, row in enumerate(grid_ids):
            for c, m in enumerate(row):
                ox, oy = c * cell_px, r * cell_px
                cells = diffs.get(m, [])
                if cells:
                    per_map_changed[f"0x{m:02X}"] = len(cells)
                    total_changed += len(cells)
                for tx, ty, _old_tid, _new_tid in cells:
                    x0 = int(round(ox + tx * tile_px))
                    y0 = int(round(oy + ty * tile_px))
                    x1 = int(round(ox + (tx + 1) * tile_px)) - 1
                    y1 = int(round(oy + (ty + 1) * tile_px)) - 1
                    d_draw.rectangle([x0, y0, x1, y1], fill=(0, 245, 255, 165), outline=(255, 255, 255, 235), width=1)
        diff_panel = Image.alpha_composite(diff_base, diff_ov)
        dp_draw = ImageDraw.Draw(diff_panel, "RGBA")
        for r, row in enumerate(grid_ids):
            for c, m in enumerate(row):
                cnt = len(diffs.get(m, []))
                tag = f"${m:02X} (+{cnt})" if cnt else f"${m:02X} (0)"
                _draw_badge(
                    dp_draw, c * cell_px + 4, r * cell_px + 4, tag, font_badge,
                    bg=(0, 45, 60, 225) if cnt else (16, 20, 28, 185),
                    fg=(140, 255, 255, 255) if cnt else (170, 180, 195, 220),
                )
        diff_summary = {
            "prev_rom": str(diff_rom_path),
            "total_changed_tile16": total_changed,
            "per_map_changed": per_map_changed,
        }

    # ------------------------------------------------------------------
    # Assemble Composite Board with Header, Rulers & Footer Legend
    # ------------------------------------------------------------------
    panels: list[tuple[str, Image.Image]] = [
        ("TRUE-COLOR STITCHED MAP", left_panel),
        (f"COLLISION, SEAMS & ENTITIES (phase={phase})", right_panel),
    ]
    if diff_panel is not None and diff_summary is not None:
        panels.append((
            f"YAZE TILE16 DIFF ({diff_summary['total_changed_tile16']} changed cells)",
            diff_panel,
        ))

    pad = 16
    ruler_top = 18
    ruler_left = 24
    panel_title_h = 24
    header_h = 58
    footer_h = 42
    gap = 20

    block_w = ruler_left + panel_w
    block_h = panel_title_h + ruler_top + panel_h
    total_w = pad * 2 + len(panels) * block_w + (len(panels) - 1) * gap
    total_h = header_h + pad + block_h + pad + footer_h

    board = Image.new("RGBA", (total_w, total_h), (18, 22, 31, 255))
    b_draw = ImageDraw.Draw(board, "RGBA")

    # Header bar
    b_draw.rectangle([0, 0, total_w, header_h], fill=(12, 16, 24, 255))
    b_draw.line([(0, header_h - 1), (total_w, header_h - 1)], fill=(55, 72, 102, 255), width=2)
    b_draw.text((pad, 9), f"Oracle of Secrets — {title}", fill=(240, 246, 255, 255), font=font_title)
    stats_line = (
        f"ROM: {rom_path.name} ({rom_sha})  |  Grid: {cols_n}x{rows_n} ({cols_n * rows_n} maps)  |  "
        f"Seam Errors: {error_seam_count} seams ({total_error_tiles} tiles)  |  "
        f"Warn Seams: {warn_seam_count}  |  Edge-Guard Blocked: {blocked_seam_count}  |  "
        f"Entrances: {shown_entrances}  Exits: {shown_exits}  Sprites(p{phase}): {shown_sprites}"
    )
    b_draw.text((pad, 33), stats_line, fill=(165, 185, 215, 255), font=font_sub)

    # Paste panels + tile coordinate rulers (0, 8, 16, 24 per screen)
    for idx, (ptitle, pim) in enumerate(panels):
        bx = pad + idx * (block_w + gap)
        by = header_h + pad
        b_draw.text((bx + ruler_left, by + 3), ptitle, fill=(210, 224, 245, 255), font=font_sub)
        px0 = bx + ruler_left
        py0 = by + panel_title_h + ruler_top
        board.paste(pim, (px0, py0))
        b_draw.rectangle([px0 - 1, py0 - 1, px0 + panel_w, py0 + panel_h], outline=(75, 95, 130, 255), width=1)

        # Horizontal tile-grid ticks (0, 8, 16, 24)
        for c in range(cols_n):
            for t in (0, 8, 16, 24):
                tx = int(round(px0 + c * cell_px + t * tile_px))
                b_draw.line([(tx, py0 - 4), (tx, py0 - 1)], fill=(120, 140, 175, 255), width=1)
                b_draw.text((tx + 1, py0 - 16), str(t), fill=(135, 155, 185, 255), font=font_tiny)
        # Vertical tile-grid ticks (0, 8, 16, 24)
        for r in range(rows_n):
            for t in (0, 8, 16, 24):
                ty = int(round(py0 + r * cell_px + t * tile_px))
                b_draw.line([(px0 - 4, ty), (px0 - 1, ty)], fill=(120, 140, 175, 255), width=1)
                b_draw.text((bx + 2, ty - 4), f"{t:2d}", fill=(135, 155, 185, 255), font=font_tiny)

    # Footer legend bar
    fy0 = total_h - footer_h
    b_draw.rectangle([0, fy0, total_w, total_h], fill=(12, 16, 24, 255))
    b_draw.line([(0, fy0), (total_w, fy0)], fill=(55, 72, 102, 255), width=1)
    legend_items: list[tuple[tuple[int, int, int, int], str]] = [
        ((46, 204, 113, 255), "Walkable Land"),
        ((0, 215, 240, 255), "Shallow Water"),
        ((28, 88, 225, 255), "Deep Water"),
        ((235, 138, 30, 255), "Solid / Cliff"),
        ((245, 220, 80, 255), "Ledge"),
        ((255, 30, 48, 255), "Seam Error Tick"),
        ((255, 195, 20, 255), "Seam Warn"),
        ((190, 95, 255, 255), "Edge-Guard Blocked"),
        ((255, 240, 50, 255), "Entrance/Exit (E##)"),
        ((255, 45, 220, 255), "Sprite (##)"),
        ((255, 210, 60, 255), "Cross-World LW<->SW"),
    ]
    lx = pad
    ly = fy0 + 13
    for swatch, label in legend_items:
        b_draw.rectangle([lx, ly, lx + 12, ly + 12], fill=swatch, outline=(230, 236, 245, 200), width=1)
        b_draw.text((lx + 17, ly - 1), label, fill=(210, 220, 235, 255), font=font_sub)
        bbox = b_draw.textbbox((0, 0), label, font=font_sub)
        lx += 17 + (bbox[2] - bbox[0]) + 18
        if lx > total_w - 140:
            break

    meta: dict[str, Any] = {
        "region": region_key,
        "title": title,
        "rom": str(rom_path),
        "rom_sha256_prefix": rom_sha,
        "grid": [[f"0x{m:02X}" for m in row] for row in grid_ids],
        "image_size": list(board.size),
        "seam_error_count": error_seam_count,
        "seam_error_tiles": total_error_tiles,
        "seam_warn_count": warn_seam_count,
        "edge_guard_blocked_seams": blocked_seam_count,
        "entrances_shown": shown_entrances,
        "exits_shown": shown_exits,
        "sprites_shown": shown_sprites,
        "seams": seam_records,
    }
    if diff_summary is not None:
        meta["diff"] = diff_summary
    return board.convert("RGB"), meta


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--rom", required=True, type=Path, help="Path to rev5 OOSOW192 or ZSOW ROM")
    ap.add_argument(
        "--region",
        choices=tuple(cos.REGION_GRIDS.keys()),
        help="Named region preset to render",
    )
    ap.add_argument("--grid", help="Custom rectangular hex map grid, e.g. '90,91,92;98,99,9A'")
    ap.add_argument("--all-regions", action="store_true", help="Generate all 4 standard region boards")
    ap.add_argument("--out", type=Path, help="Output PNG path (single region / custom grid)")
    ap.add_argument("--out-dir", type=Path, help="Output directory for --all-regions")
    ap.add_argument("--diff-rom", type=Path, help="Optional previous ROM to render a 3rd Yaze diff panel")
    ap.add_argument("--cell-px", type=int, default=256, help="Rendered pixel size per 32x32 map screen (default: 256)")
    ap.add_argument("--phase", type=int, choices=(0, 1, 2), default=1, help="Sprite phase to overlay (default: 1)")
    ap.add_argument("--no-z3ed", action="store_true", help="Force pure-Python renderer instead of z3ed")
    ap.add_argument("--z3ed", type=Path, help="Explicit path to z3ed binary")
    ap.add_argument("--out-json", type=Path, help="Optional JSON metadata summary path")
    args = ap.parse_args(argv)

    if args.all_regions:
        if args.out_dir is None:
            ap.error("--all-regions requires --out-dir")
        args.out_dir.mkdir(parents=True, exist_ok=True)
        summaries: dict[str, Any] = {}
        for key, grid in cos.REGION_GRIDS.items():
            out_path = args.out_dir / f"ow_board_{key.replace('-', '_')}.png"
            img, meta = build_region_board(
                args.rom,
                grid,
                title=cos.REGION_TITLES[key],
                region_key=key,
                cell_px=args.cell_px,
                phase=args.phase,
                use_z3ed=not args.no_z3ed,
                z3ed_bin=args.z3ed,
                diff_rom_path=args.diff_rom,
            )
            img.save(out_path)
            meta["output_png"] = str(out_path)
            summaries[key] = meta
            print(
                f"[+] Wrote {out_path} ({img.size[0]}x{img.size[1]}) | "
                f"err_seams={meta['seam_error_count']} ({meta['seam_error_tiles']} tiles) "
                f"warn={meta['seam_warn_count']} ent={meta['entrances_shown']} spr={meta['sprites_shown']}"
            )
        if args.out_json:
            args.out_json.parent.mkdir(parents=True, exist_ok=True)
            args.out_json.write_text(json.dumps(summaries, indent=2) + "\n", encoding="utf-8")
        return 0

    if not args.region and not args.grid:
        ap.error("Specify --region <name>, --grid <spec>, or --all-regions")
    if args.out is None:
        ap.error("Specify --out <path.png>")

    if args.grid:
        grid = _parse_custom_grid(args.grid)
        region_key = "custom"
        title = f"Custom Region Grid ({args.grid})"
    else:
        grid = cos.REGION_GRIDS[args.region]
        region_key = args.region
        title = cos.REGION_TITLES[args.region]

    img, meta = build_region_board(
        args.rom,
        grid,
        title=title,
        region_key=region_key,
        cell_px=args.cell_px,
        phase=args.phase,
        use_z3ed=not args.no_z3ed,
        z3ed_bin=args.z3ed,
        diff_rom_path=args.diff_rom,
    )
    args.out.parent.mkdir(parents=True, exist_ok=True)
    img.save(args.out)
    meta["output_png"] = str(args.out)
    if args.out_json:
        args.out_json.parent.mkdir(parents=True, exist_ok=True)
        args.out_json.write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    print(
        f"[+] Wrote {args.out} ({img.size[0]}x{img.size[1]}) | "
        f"err_seams={meta['seam_error_count']} ({meta['seam_error_tiles']} tiles) "
        f"warn={meta['seam_warn_count']} ent={meta['entrances_shown']} spr={meta['sprites_shown']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
