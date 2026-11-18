#!/usr/bin/env python3
"""Assembled Donor Formation Audition & Perceptual Palette Remapping Tool.

Extracts complete assembled Tile16 / map-box formations from donor ROMs
(preserving Tile8 H/V flips and authentic donor BGR555 subpalettes), remaps
colors perceptually via CIELAB to target Oracle BGR555 subpalettes while strictly
preserving index 0 (BG0 transparency), deduplicates against vanilla + target
Tile8s to report exact marginal Tile8 slot cost, and renders crisp contact sheets.

Strictly read-only on donor and target ROMs. Optional --z3ed-preview-at stages
edits exclusively on a /tmp copy and renders authentic z3ed PPU comparisons.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import scene_intent_common as C  # noqa: E402

UI_BG = (16, 19, 27)
UI_CARD = (25, 29, 41)
UI_BORDER = (58, 67, 90)
UI_TEXT = (240, 244, 250)
UI_MUTED = (162, 174, 196)
UI_GREEN = (74, 222, 128)
UI_CYAN = (56, 189, 248)
UI_AMBER = (251, 191, 36)


def _load_font(size: int, mono: bool = False):
    for p in (
        "/System/Library/Fonts/Menlo.ttc" if mono else "/System/Library/Fonts/SFNS.ttf",
        "/System/Library/Fonts/Supplemental/Arial.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ):
        if Path(p).exists():
            try:
                return ImageFont.truetype(p, size=size)
            except Exception:
                pass
    return ImageFont.load_default()


def parse_box_spec(spec: str) -> tuple[int, int, int, int]:
    parts = [int(x.strip(), 0) for x in spec.split(",")]
    if len(parts) != 4 or parts[2] <= 0 or parts[3] <= 0:
        raise ValueError(f"Expected x,y,w,h with positive dimensions, got {spec!r}")
    return parts[0], parts[1], parts[2], parts[3]


def parse_subpal_spec(spec: str) -> tuple[int, bool | None]:
    """Parse 'row' or 'row:left|right' into (row_0_7, high_half_or_None)."""
    s = spec.strip().lower()
    if ":" in s:
        r_str, half_str = s.split(":", 1)
        row = int(r_str, 0) & 7
        if half_str in ("right", "high", "hi", "1"):
            return row, True
        if half_str in ("left", "low", "lo", "0"):
            return row, False
        raise ValueError(f"Unknown palette half {half_str!r} in {spec!r}")
    return int(s, 0) & 7, None


def candidate_subpalettes_from_128(
    pal128: list[tuple[int, int, int]],
    *,
    specs: list[tuple[int, bool | None]] | None = None,
    allowed_rows: range = range(2, 8),
) -> list[dict[str, Any]]:
    """Enumerate valid 8-entry subpalettes [bg0, c1..c7] from a 128-entry CGRAM palette."""
    wanted: list[tuple[int, bool]] = []
    if specs:
        for row, hh in specs:
            if hh is None:
                wanted.extend([(row, False), (row, True)])
            else:
                wanted.append((row, hh))
    else:
        for row in allowed_rows:
            wanted.extend([(row, False), (row, True)])

    out: list[dict[str, Any]] = []
    seen = set()
    for row, hh in wanted:
        if (row, hh) in seen:
            continue
        seen.add((row, hh))
        pal8 = C.palette8_for_subpal(pal128, row, hh)
        labs = [C.rgb_to_lab(rgb) for rgb in pal8]
        out.append({
            "row": row,
            "high_half": hh,
            "label": f"R{row}:{'R' if hh else 'L'}",
            "pal8": pal8,
            "labs": labs,
        })
    return out


def remap_tile8_perceptual(
    src_px64: tuple[int, ...] | list[int],
    src_pal8: list[tuple[int, int, int]],
    candidates: list[dict[str, Any]],
) -> dict[str, Any]:
    """Remap an 8x8 tile perceptually to the best target subpalette, preserving index 0 (BG0).

    Color index 0 ALWAYS maps to 0 so background transparency never collides with
    opaque colors. Indices 1..7 are matched 1-to-1 onto distinct slots in 1..7 of
    each candidate subpalette via exact bitmask DP minimizing weighted CIELAB
    distance (preserving intra-tile shade & texture contrast).
    """
    src_labs = [C.rgb_to_lab(rgb) for rgb in src_pal8]
    counts = Counter(v & 7 for v in src_px64 if (v & 7) != 0)
    if not counts:
        best_cand = candidates[0]
        return {
            "px": tuple(0 for _ in src_px64),
            "target_subpal": best_cand["label"],
            "target_row": best_cand["row"],
            "target_high_half": best_cand["high_half"],
            "pal8": best_cand["pal8"],
            "avg_delta_e": 0.0,
            "color_map": {0: 0},
        }

    src_order = [idx for idx, _ in counts.most_common()]
    k = len(src_order)
    total_fg = sum(counts.values())
    best: dict[str, Any] | None = None

    for cand in candidates:
        t_labs = cand["labs"]
        t_rgbs = cand["pal8"]
        # Exact bitmask DP: k <= 7 source colors mapped injectively to target slots 1..7 (bit 0..6).
        dp: list[dict[int, tuple[float, list[int]]]] = [{} for _ in range(k + 1)]
        dp[0][0] = (0.0, [])
        for step, s_idx in enumerate(src_order):
            s_lab = src_labs[s_idx]
            w = counts[s_idx]
            for mask, (cur_cost, picks) in dp[step].items():
                for slot_bit in range(7):
                    if mask & (1 << slot_bit):
                        continue
                    t_idx = slot_bit + 1
                    de = C.lab_distance(s_lab, t_labs[t_idx])
                    # Penalize colliding onto an identical target RGB already chosen in this tile.
                    dup_pen = 45.0 if any(t_rgbs[prev] == t_rgbs[t_idx] for prev in picks) else 0.0
                    ncost = cur_cost + w * (de + dup_pen)
                    nmask = mask | (1 << slot_bit)
                    prev_entry = dp[step + 1].get(nmask)
                    if prev_entry is None or ncost < prev_entry[0]:
                        dp[step + 1][nmask] = (ncost, picks + [t_idx])

        _, best_picks = min(dp[k].values(), key=lambda item: item[0])
        cmap: dict[int, int] = {0: 0}
        weighted_de = 0.0
        for s_idx, t_idx in zip(src_order, best_picks):
            cmap[s_idx] = t_idx
            weighted_de += counts[s_idx] * C.lab_distance(src_labs[s_idx], t_labs[t_idx])
        best_score = min(dp[k].values(), key=lambda item: item[0])[0] / total_fg
        if best is None or best_score < best["_score"]:
            remapped = tuple(0 if (v & 7) == 0 else cmap[v & 7] for v in src_px64)
            best = {
                "_score": best_score,
                "px": remapped,
                "target_subpal": cand["label"],
                "target_row": cand["row"],
                "target_high_half": cand["high_half"],
                "pal8": cand["pal8"],
                "avg_delta_e": round(weighted_de / total_fg, 2),
                "color_map": cmap,
            }
    assert best is not None
    best.pop("_score", None)
    return best


def build_known_tile8_corpus(
    target_rom: bytes | None,
    *,
    target_ow: int | None = None,
    vanilla_rom: bytes | None = None,
) -> tuple[set[tuple[int, ...]], set[tuple[int, ...]]]:
    """Build canonical Tile8 sets for (target_area_or_rom, vanilla_rom) with BG0 preserved."""
    target_canons: set[tuple[int, ...]] = set()
    vanilla_canons: set[tuple[int, ...]] = set()

    if vanilla_rom is not None:
        v_sheets = C.decode_sheet_chars(vanilla_rom)
        for chars in v_sheets.values():
            for px in chars:
                k = C.canonical_tile8(px, preserve_zero=True)
                if k is not None:
                    vanilla_canons.add(k)

    if target_rom is not None:
        if target_ow is not None:
            sc = C.load_overworld_slot_chars(target_rom, target_ow)
            for chars in sc.values():
                for px in chars:
                    k = C.canonical_tile8(px, preserve_zero=True)
                    if k is not None:
                        target_canons.add(k)
        else:
            t_sheets = C.decode_sheet_chars(target_rom)
            for chars in t_sheets.values():
                for px in chars:
                    k = C.canonical_tile8(px, preserve_zero=True)
                    if k is not None:
                        target_canons.add(k)

    return target_canons, vanilla_canons


def audition_tile16_grid(
    *,
    name: str,
    tile16_grid: list[list[int]],
    donor_tile16s: list[tuple[int, int, int, int]],
    donor_slot_chars: dict[int, list[tuple[int, ...]]],
    donor_pal128: list[tuple[int, int, int]],
    target_candidates: list[dict[str, Any]],
    target_canons: set[tuple[int, ...]],
    vanilla_canons: set[tuple[int, ...]],
) -> dict[str, Any]:
    """Assemble a Tile16 formation, remap perceptually to target, and tally marginal Tile8 cost."""
    h = len(tile16_grid)
    w = len(tile16_grid[0]) if h else 0
    src_img = Image.new("RGBA", (w * 16, h * 16), (0, 0, 0, 0))
    dst_img = Image.new("RGBA", (w * 16, h * 16), (*target_candidates[0]["pal8"][0], 255))

    seen_new_canons: set[tuple[int, ...]] = set()
    quad_records: list[dict[str, Any]] = []
    counts_by_status: Counter[str] = Counter()
    delta_es: list[float] = []

    positions = ((0, 0), (8, 0), (0, 8), (8, 8))
    for gy in range(h):
        for gx in range(w):
            tid = tile16_grid[gy][gx]
            if not (0 <= tid < len(donor_tile16s)):
                continue
            words = donor_tile16s[tid]
            # Authentic donor Tile16 render (with H/V flips & donor palette)
            d_tile = C.render_tile16_rgba(words, donor_slot_chars, donor_pal128, transparent_zero=False)
            src_img.alpha_composite(d_tile, (gx * 16, gy * 16))

            for q_idx, (word, (qx, qy)) in enumerate(zip(words, positions)):
                ch_id = word & 0x3FF
                pal_row = (word >> 10) & 7
                hflip = bool((word >> 14) & 1)
                vflip = bool((word >> 15) & 1)
                slot = ch_id // 64
                local_chr = ch_id % 64
                raw_px = donor_slot_chars.get(slot, [(0,) * 64] * 64)[local_chr]
                # Preserve H/V flip geometry cleanly.
                tf_px = C.flip_tile8(raw_px, hflip=hflip, vflip=vflip)
                src_pal8 = C.palette8_for_subpal(
                    donor_pal128, pal_row, high_half=(slot in C.HIGH_PALETTE_SLOTS)
                )
                rem = remap_tile8_perceptual(tf_px, src_pal8, target_candidates)
                t_im = C.render_tile8_rgba(rem["px"], rem["pal8"], transparent_zero=True)
                dst_img.alpha_composite(t_im, (gx * 16 + qx, gy * 16 + qy))
                delta_es.append(rem["avg_delta_e"])

                canon = C.canonical_tile8(rem["px"], preserve_zero=True)
                if canon is None:
                    status = "flat"
                elif canon in target_canons:
                    status = "target_reused"
                elif canon in vanilla_canons:
                    status = "vanilla_reusable"
                elif canon in seen_new_canons:
                    status = "intra_deduped"
                else:
                    status = "marginal_new"
                    seen_new_canons.add(canon)
                counts_by_status[status] += 1
                quad_records.append({
                    "cell": [gx, gy],
                    "quadrant": q_idx,
                    "donor_tile16": f"0x{tid:04X}",
                    "donor_word": f"0x{word:04X}",
                    "hflip": hflip,
                    "vflip": vflip,
                    "donor_pal_row": pal_row,
                    "target_subpal": rem["target_subpal"],
                    "avg_delta_e": rem["avg_delta_e"],
                    "status": status,
                })

    mean_de = round(sum(delta_es) / max(1, len(delta_es)), 2)
    return {
        "name": name,
        "grid_dims": [w, h],
        "tile16_ids": [[f"0x{tid:04X}" for tid in row] for row in tile16_grid],
        "quadrant_count": len(quad_records),
        "unique_new_tile8_cost": counts_by_status["marginal_new"],
        "breakdown": dict(counts_by_status),
        "mean_delta_e": mean_de,
        "quadrants": quad_records,
        "_src_img": src_img,
        "_dst_img": dst_img,
    }


def render_audition_contact_sheet(
    formations: list[dict[str, Any]],
    target_candidates: list[dict[str, Any]],
    *,
    donor_label: str,
    target_label: str,
    out_path: Path,
) -> Path:
    """Render a crisp 4x contact sheet: Donor Original | Oracle Remap | Tile8 Cost Overlay."""
    f_title = _load_font(20)
    f_head = _load_font(14)
    f_mono = _load_font(12, mono=True)
    scale = 4
    pad = 18

    row_heights = [max(136, f["_src_img"].height * scale + 56) for f in formations]
    max_fw = max((f["_src_img"].width * scale for f in formations), default=128)
    card_w = max(1060, max_fw * 3 + 340)
    w = pad * 2 + card_w
    h = 92 + sum(rh + 12 for rh in row_heights) + pad

    canvas = Image.new("RGB", (w, h), UI_BG)
    dr = ImageDraw.Draw(canvas)
    dr.text((pad, 16), f"Donor Formation Audition: {donor_label} -> {target_label}", font=f_title, fill=UI_TEXT)
    dr.text(
        (pad, 44),
        "Assembled Tile16 + H/V flips preserved | BG0 index 0 strictly transparent | Perceptual CIELAB BGR555 remap",
        font=f_head,
        fill=UI_MUTED,
    )
    # Render target palette swatches bar
    sx = pad
    for cand in target_candidates[:6]:
        dr.text((sx, 68), cand["label"], font=f_mono, fill=UI_MUTED)
        sx += 44
        for idx, col in enumerate(cand["pal8"]):
            dr.rectangle([sx, 68, sx + 10, 80], fill=col, outline=(255, 255, 255) if idx == 0 else UI_BORDER)
            sx += 11
        sx += 14

    status_col = {
        "flat": (100, 116, 139),
        "target_reused": UI_GREEN,
        "vanilla_reusable": UI_CYAN,
        "intra_deduped": (134, 239, 172),
        "marginal_new": UI_AMBER,
    }

    y = 92
    for fm, rh in zip(formations, row_heights):
        dr.rounded_rectangle([pad, y, pad + card_w, y + rh], radius=8, fill=UI_CARD, outline=UI_BORDER, width=2)
        src_4x = fm["_src_img"].resize((fm["_src_img"].width * scale, fm["_src_img"].height * scale), Image.Resampling.NEAREST).convert("RGB")
        dst_4x = fm["_dst_img"].resize((fm["_dst_img"].width * scale, fm["_dst_img"].height * scale), Image.Resampling.NEAREST).convert("RGB")
        cost_4x = dst_4x.copy()
        cdr = ImageDraw.Draw(cost_4x)
        qpx = 8 * scale
        for q in fm["quadrants"]:
            gx, gy = q["cell"]
            qi = q["quadrant"]
            qx = (gx * 2 + (qi & 1)) * qpx
            qy = (gy * 2 + (qi >> 1)) * qpx
            cdr.rectangle([qx, qy, qx + qpx - 1, qy + qpx - 1], outline=status_col[q["status"]], width=2)

        x0 = pad + 14
        gap = 28
        fw = src_4x.width
        canvas.paste(src_4x, (x0, y + 36))
        canvas.paste(dst_4x, (x0 + fw + gap, y + 36))
        canvas.paste(cost_4x, (x0 + 2 * (fw + gap), y + 36))

        dr.text((x0, y + 12), f"{fm['name']} | Donor Original", font=f_head, fill=UI_TEXT)
        dr.text((x0 + fw + gap, y + 12), f"Target Remapped (mean dE={fm['mean_delta_e']})", font=f_head, fill=UI_CYAN)
        dr.text((x0 + 2 * (fw + gap), y + 12), f"Tile8 Cost (+{fm['unique_new_tile8_cost']} new)", font=f_head, fill=UI_AMBER)

        bd = fm["breakdown"]
        legend_x = x0 + 3 * (fw + gap)
        if legend_x + 220 <= pad + card_w:
            dr.text((legend_x, y + 36), f"Quads: {fm['quadrant_count']}", font=f_mono, fill=UI_TEXT)
            dr.text((legend_x, y + 54), f"New Tile8: {fm['unique_new_tile8_cost']}", font=f_mono, fill=UI_AMBER)
            dr.text((legend_x, y + 72), f"Target reused: {bd.get('target_reused', 0)}", font=f_mono, fill=UI_GREEN)
            dr.text((legend_x, y + 90), f"Vanilla match: {bd.get('vanilla_reusable', 0)}", font=f_mono, fill=UI_CYAN)
            dr.text((legend_x, y + 108), f"Intra-deduped: {bd.get('intra_deduped', 0)}", font=f_mono, fill=UI_MUTED)
        y += rh + 12

    out_path.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_path)
    return out_path


def run_z3ed_scratch_preview(
    *,
    target_rom_path: Path,
    target_ow: int,
    tile16_grid: list[list[int]],
    at_xy: tuple[int, int],
    z3ed_bin: Path,
    out_dir: Path,
) -> dict[str, Any] | None:
    """Copy target_rom to /tmp scratch, apply overworld-set-tile, and render PPU Before vs After."""
    cmds = C.z3ed_supported_commands(z3ed_bin)
    if "overworld-render" not in cmds or "overworld-set-tile" not in cmds:
        return None
    out_dir.mkdir(parents=True, exist_ok=True)
    before_png = out_dir / f"ppu_preview_ow{target_ow:02X}_before.png"
    after_png = out_dir / f"ppu_preview_ow{target_ow:02X}_after.png"
    compare_png = out_dir / f"ppu_preview_ow{target_ow:02X}_compare.png"

    with C.staged_ro_rom(target_rom_path) as (staged_rom, _sha):
        C.run_z3ed_json(z3ed_bin, [
            "overworld-render", f"--rom={staged_rom}", f"--screen=0x{target_ow:02X}", f"--out={before_png}"
        ])
        ax, ay = at_xy
        for dy, row in enumerate(tile16_grid):
            for dx, tid in enumerate(row):
                C.run_z3ed_json(z3ed_bin, [
                    "overworld-set-tile", f"--rom={staged_rom}",
                    f"--map=0x{target_ow:02X}", f"--x={ax + dx}", f"--y={ay + dy}",
                    f"--tile=0x{tid:04X}", "--write", "--allow-lyra-layout-writes",
                ])
        C.run_z3ed_json(z3ed_bin, [
            "overworld-render", f"--rom={staged_rom}", f"--screen=0x{target_ow:02X}", f"--out={after_png}"
        ])

    if before_png.is_file() and after_png.is_file():
        b_im = Image.open(before_png).convert("RGB")
        a_im = Image.open(after_png).convert("RGB")
        cmp_im = Image.new("RGB", (b_im.width + a_im.width + 16, max(b_im.height, a_im.height) + 40), UI_BG)
        cmp_im.paste(b_im, (0, 40))
        cmp_im.paste(a_im, (b_im.width + 16, 40))
        dr = ImageDraw.Draw(cmp_im)
        f_h = _load_font(16)
        dr.text((12, 10), f"Genuine PPU Before (OW 0x{target_ow:02X})", font=f_h, fill=UI_TEXT)
        dr.text((b_im.width + 28, 10), f"Genuine PPU After (/tmp scratch @ {at_xy[0]},{at_xy[1]})", font=f_h, fill=UI_GREEN)
        cmp_im.save(compare_png)
        return {
            "before_png": str(before_png),
            "after_png": str(after_png),
            "compare_png": str(compare_png),
        }
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--donor-rom", type=Path, required=True, help="Donor .sfc/.smc ROM path (read-only)")
    ap.add_argument("--area", help="Donor Overworld area ID in hex (used with --box and donor palette)")
    ap.add_argument("--donor-room", help="Optional donor dungeon room ID in hex (for donor dungeon palette)")
    ap.add_argument("--box", action="append", default=[], help="Map Tile16 formation box x,y,w,h (repeatable)")
    ap.add_argument("--tile16s", help="Explicit comma-separated donor Tile16 IDs (hex or dec)")
    ap.add_argument("--cols", type=int, default=4, help="Grid width when using --tile16s")
    ap.add_argument("--target-rom", type=Path, default=C.DEFAULT_PROJ_ROM, help="Target Oracle ROM (read-only)")
    ap.add_argument("--vanilla-rom", type=Path, default=C.DEFAULT_VANILLA_ROM, help="Vanilla ALTTP ROM for reuse dedupe")
    ap.add_argument("--target-ow", help="Target Overworld area ID in hex for palette & loaded Tile8s")
    ap.add_argument("--target-room", help="Target dungeon room ID in hex for palette")
    ap.add_argument("--target-subpal", action="append", default=[], help="Restrict target subpalette (e.g. 2:right)")
    ap.add_argument("--z3ed-preview-at", help="Optional x,y Tile16 coords for /tmp z3ed Before/After PPU render")
    ap.add_argument("--z3ed", type=Path, help="Optional z3ed binary override")
    ap.add_argument("--out-dir", type=Path, help="Output directory for PNG contact sheet and JSON report")
    args = ap.parse_args(argv)

    if not args.donor_rom.is_file():
        ap.error(f"Donor ROM not found: {args.donor_rom}")
    if not args.box and not args.tile16s:
        ap.error("Specify --box x,y,w,h (with --area) and/or --tile16s id1,id2,...")
    if args.box and not args.area:
        ap.error("--box requires --area <hex>")

    donor_rom = C.load_rom_bytes(args.donor_rom)
    donor_tile16s = C.decode_tile16_table(donor_rom)

    if args.area:
        d_area = C.parse_hex_int(args.area)
        donor_slot_chars = C.load_overworld_slot_chars(donor_rom, d_area)
        donor_pal128 = C.decode_overworld_palette_128(donor_rom, d_area)
        donor_grid, _ = C.decode_large_overworld_grid(donor_rom, d_area)
        donor_tag = f"{args.donor_rom.stem} (OW 0x{d_area:02X})"
    elif args.donor_room:
        d_room = C.parse_hex_int(args.donor_room)
        hdr = C.read_room_header(donor_rom, d_room)
        donor_pal128 = C.decode_dungeon_palette_128(donor_rom, hdr["palette"] if hdr else 0)
        donor_slot_chars = C.load_overworld_slot_chars(donor_rom, 0)
        donor_grid = []
        donor_tag = f"{args.donor_rom.stem} (Room 0x{d_room:03X})"
    else:
        donor_slot_chars = C.load_overworld_slot_chars(donor_rom, 0)
        donor_pal128 = C.decode_overworld_palette_128(donor_rom, 0)
        donor_grid = []
        donor_tag = args.donor_rom.stem

    target_rom_bytes = C.load_rom_bytes(args.target_rom) if args.target_rom.is_file() else donor_rom
    vanilla_rom_bytes = C.load_rom_bytes(args.vanilla_rom) if args.vanilla_rom and args.vanilla_rom.is_file() else None
    t_ow = C.parse_hex_int(args.target_ow) if args.target_ow else None
    t_room = C.parse_hex_int(args.target_room) if args.target_room else None

    if t_room is not None:
        rh = C.read_room_header(target_rom_bytes, t_room)
        t_pal128 = C.decode_dungeon_palette_128(target_rom_bytes, rh["palette"] if rh else 0)
        target_label = f"Target Room 0x{t_room:03X}"
    else:
        area_for_pal = t_ow if t_ow is not None else 0x23
        t_pal128 = C.decode_overworld_palette_128(target_rom_bytes, area_for_pal)
        target_label = f"Target OW 0x{area_for_pal:02X}"

    subpal_specs = [parse_subpal_spec(s) for s in args.target_subpal] if args.target_subpal else None
    candidates = candidate_subpalettes_from_128(t_pal128, specs=subpal_specs)
    target_canons, vanilla_canons = build_known_tile8_corpus(
        target_rom_bytes, target_ow=t_ow, vanilla_rom=vanilla_rom_bytes
    )

    grids: list[tuple[str, list[list[int]]]] = []
    for idx, bspec in enumerate(args.box, 1):
        bx, by, bw, bh = parse_box_spec(bspec)
        sub = [donor_grid[by + dy][bx:bx + bw] for dy in range(bh) if by + dy < len(donor_grid)]
        if sub:
            grids.append((f"Box{idx} ({bx},{by} {bw}x{bh})", sub))
    if args.tile16s:
        ids = [C.parse_hex_int(x) for x in args.tile16s.split(",") if x.strip()]
        c = max(1, min(args.cols, len(ids)))
        tgrid = [ids[i:i + c] for i in range(0, len(ids), c)]
        # Pad last row if uneven
        while tgrid and len(tgrid[-1]) < c:
            tgrid[-1].append(ids[0])
        grids.append((f"Tile16 list ({len(ids)})", tgrid))

    formations = []
    for fname, tgrid in grids:
        formations.append(audition_tile16_grid(
            name=fname,
            tile16_grid=tgrid,
            donor_tile16s=donor_tile16s,
            donor_slot_chars=donor_slot_chars,
            donor_pal128=donor_pal128,
            target_candidates=candidates,
            target_canons=target_canons,
            vanilla_canons=vanilla_canons,
        ))

    contact_png = None
    ppu_preview = None
    if args.out_dir is not None and formations:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        safe_stem = "".join(ch if ch.isalnum() else "_" for ch in args.donor_rom.stem)
        contact_png = str(render_audition_contact_sheet(
            formations,
            candidates,
            donor_label=donor_tag,
            target_label=target_label,
            out_path=args.out_dir / f"donor_audition_{safe_stem}.png",
        ))
        if args.z3ed_preview_at and t_ow is not None and args.target_rom.is_file():
            z3ed_bin = C.find_z3ed_bin(args.z3ed, C.REPO_ROOT)
            if z3ed_bin:
                ax, ay = (int(x.strip(), 0) for x in args.z3ed_preview_at.split(","))
                ppu_preview = run_z3ed_scratch_preview(
                    target_rom_path=args.target_rom,
                    target_ow=t_ow,
                    tile16_grid=grids[0][1],
                    at_xy=(ax, ay),
                    z3ed_bin=z3ed_bin,
                    out_dir=args.out_dir,
                )

    serializable = [
        {k: v for k, v in fm.items() if not k.startswith("_")}
        for fm in formations
    ]
    report = {
        "donor_rom": str(args.donor_rom),
        "target_rom": str(args.target_rom),
        "donor_label": donor_tag,
        "target_label": target_label,
        "candidate_subpalettes": [c["label"] for c in candidates],
        "formations": serializable,
        "contact_sheet_png": contact_png,
        "ppu_preview": ppu_preview,
    }
    if args.out_dir is not None:
        safe_stem = "".join(ch if ch.isalnum() else "_" for ch in args.donor_rom.stem)
        (args.out_dir / f"donor_audition_{safe_stem}.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(json.dumps({k: v for k, v in report.items() if k != "formations"} | {
        "formation_summaries": [
            {
                "name": fm["name"],
                "grid_dims": fm["grid_dims"],
                "quadrant_count": fm["quadrant_count"],
                "unique_new_tile8_cost": fm["unique_new_tile8_cost"],
                "breakdown": fm["breakdown"],
                "mean_delta_e": fm["mean_delta_e"],
            }
            for fm in serializable
        ]
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
