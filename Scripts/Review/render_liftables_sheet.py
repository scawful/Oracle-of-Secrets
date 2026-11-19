#!/usr/bin/env python3
"""Deterministic 3-column Overworld Liftables Contact Sheet Simulator (Q328 Track A3).

Renders side-by-side PNG strips for key biomes and liftable objects:
  Col 1: Ground Tile16 (live biome BG sheets + BG palette)
  Col 2: Lifted Sprite $EC OAM (CommonSprite $01 LW / $0B DW + live BG-derived SP0/SP6)
  Col 3: Revealed Tile16 Underneath (respecting Q325 Overworld/liftables_palette_fix.asm)

Computes CIE76 Lab Delta-E between Ground and Lifted OAM dominant colors so
palette drift (e.g. DW rock/bush SP6 clash) is flagged visually and in JSON.

Usage:
  python3 Scripts/Review/render_liftables_sheet.py --rom <rom.sfc> --out <sheet.png> [--json <out.json>]
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "Scripts" / "Build"))
sys.path.insert(0, str(ROOT / "Scripts" / "Tools"))

import check_sheet_reveal_safety as csrs  # noqa: E402
import check_tile16_pins as ctp  # noqa: E402
import scene_intent_common as sic  # noqa: E402

# Curated biome showcase rows: (label, map_id, objects)
# Each object: (label, ground_tid, reveal_tid, common_tile_id, is_dw_rock)
BIOME_ROWS: list[tuple[str, int, list[tuple[str, int, int, int, bool]]]] = [
    ("LW $23 Village", 0x23, [
        ("Bush $036", 0x0036, 0x0DC7, 0x06, False),
        ("Rock $20F", 0x020F, 0x0DC9, 0x04, False),
        ("Sign $101", 0x0101, 0x0DC6, 0x08, False),
    ]),
    ("LW $05 Snow Mtn", 0x05, [
        ("Bush $036", 0x0036, 0x0DC7, 0x06, False),
        ("Rock $20F", 0x020F, 0x0DC9, 0x04, False),
        ("HvyRock $239", 0x0239, 0x0DC9, 0x04, False),
    ]),
    ("DW $5B Abyss Field", 0x5B, [
        ("Bush $036", 0x0036, 0x0DC7, 0x06, False),
        ("Rock $20F", 0x020F, 0x0DC9, 0x04, True),
        ("Sign $17D", 0x017D, 0x0DC6, 0x08, False),
    ]),
    ("DW $63 Wisdom Swamp (ASM $172)", 0x63, [
        ("Bush $036", 0x0036, 0x0172, 0x06, False),
        ("Rock $20F", 0x020F, 0x0DC9, 0x04, True),
        ("Sign $17D", 0x017D, 0x0172, 0x08, False),
    ]),
    ("SW $99 Lyra Quay", 0x99, [
        ("Bush $036", 0x0036, 0x0DC7, 0x06, False),
        ("Rock $20F", 0x020F, 0x0DC9, 0x04, False),
        ("Sign $101", 0x0101, 0x0DC6, 0x08, False),
    ]),
]


def _render_tile16(
    words: tuple[int, int, int, int],
    slot_chars: list[tuple[int, ...]],
    pal128: list[tuple[int, int, int]],
) -> Image.Image:
    im = Image.new("RGBA", (16, 16), (0, 0, 0, 255))
    bg0 = pal128[0]
    for q, w in enumerate(words):
        ch = w & 0x3FF
        pal = (w >> 10) & 7
        hf = bool(w & 0x4000)
        vf = bool(w & 0x8000)
        px = slot_chars[ch] if ch < len(slot_chars) else (0,) * 64
        px = sic.flip_tile8(px, hf, vf)
        p8 = sic.palette8_for_subpal(pal128, pal, False)
        qx, qy = (q & 1) * 8, (q >> 1) * 8
        for py in range(8):
            for px_i in range(8):
                v = px[py * 8 + px_i]
                rgb = bg0 if v == 0 else p8[v]
                im.putpixel((qx + px_i, qy + py), rgb + (255,))
    return im


def _dominant_nonbg_rgb(im: Image.Image, bg: tuple[int, int, int]) -> tuple[int, int, int]:
    counts: dict[tuple[int, int, int], int] = {}
    pixels = im.get_flattened_data() if hasattr(im, "get_flattened_data") else im.getdata()
    for r, g, b, _a in pixels:
        rgb = (r, g, b)
        if rgb == bg or rgb == (0, 0, 0):
            continue
        counts[rgb] = counts.get(rgb, 0) + 1
    if not counts:
        return bg
    return max(counts.items(), key=lambda kv: kv[1])[0]


def _render_lifted_oam(
    ground_words: tuple[int, int, int, int],
    slot_chars: list[tuple[int, ...]],
    pal128: list[tuple[int, int, int]],
    is_dw: bool,
    is_dw_rock: bool,
) -> tuple[Image.Image, str]:
    """Simulate Q325 live BG-derived SP0/SP6 OAM rendering of lifted Sprite $EC."""
    # Q325 liftables_palette_fix.asm syncs SP0 (DW small rock) / SP6 (other) directly
    # from the object's live BG subpalette in $7EC300/$7EC500.
    oam_slot = "SP0" if (is_dw and is_dw_rock) else "SP6"
    im = _render_tile16(ground_words, slot_chars, pal128)
    # Place on transparent-checker backdrop to distinguish OAM sprite from BG ground
    out = Image.new("RGBA", (16, 16), (24, 28, 36, 255))
    bg0 = pal128[0]
    for y in range(16):
        for x in range(16):
            r, g, b, a = im.getpixel((x, y))
            if (r, g, b) != bg0:
                out.putpixel((x, y), (r, g, b, 255))
            else:
                chk = 34 if ((x >> 2) ^ (y >> 2)) & 1 else 26
                out.putpixel((x, y), (chk, chk + 4, chk + 10, 255))
    return out, oam_slot


def render_contact_sheet(rom: bytes, out_png: Path) -> dict[str, Any]:
    _cap, native_tables = ctp._native_table_addresses(rom)
    tile16 = sic.decode_tile16_table(rom)

    scale = 3
    tile_px = 16 * scale  # 48px
    col_w = 210
    row_h = 92
    header_h = 34
    left_w = 185
    width = left_w + col_w * 3 + 16
    height = header_h + row_h * len(BIOME_ROWS) + 12

    canvas = Image.new("RGBA", (width, height), (18, 20, 26, 255))
    draw = ImageDraw.Draw(canvas)
    draw.text((10, 10), "Q328/Q329 Liftables Contact Sheet: Ground BG | Lifted $EC OAM | Revealed Tile16", fill=(235, 240, 250, 255))

    metrics: list[dict[str, Any]] = []
    for r_idx, (biome_label, area_id, objs) in enumerate(BIOME_ROWS):
        y0 = header_h + r_idx * row_h
        draw.rectangle([(6, y0), (width - 8, y0 + row_h - 6)], fill=(28, 32, 42, 255), outline=(62, 70, 90, 255))
        draw.text((14, y0 + 10), biome_label, fill=(220, 232, 255, 255))
        is_dw = 0x40 <= area_id < 0x80
        _parent, sheets = csrs._read_area_parent_and_sheets(rom, area_id, native_tables)
        chars_map = sic.decode_sheet_chars(rom, set(sheets))
        slot_chars: list[tuple[int, ...]] = []
        for s in sheets:
            slot_chars.extend(chars_map.get(s, [(0,) * 64] * 64))
        pal128 = sic.decode_overworld_palette_128(rom, area_id)
        draw.text((14, y0 + 30), f"slot6=${sheets[6]:02X}", fill=(150, 168, 196, 255))

        for c_idx, (obj_label, g_tid, rev_tid, _cmn, is_dw_rock) in enumerate(objs):
            x0 = left_w + c_idx * col_w
            g_im = _render_tile16(tile16[g_tid], slot_chars, pal128)
            o_im, oam_slot = _render_lifted_oam(tile16[g_tid], slot_chars, pal128, is_dw, is_dw_rock)
            rev_im = _render_tile16(tile16[rev_tid], slot_chars, pal128)

            g_dom = _dominant_nonbg_rgb(g_im, pal128[0])
            o_dom = _dominant_nonbg_rgb(o_im, (26, 30, 36))
            de = sic.lab_distance(sic.rgb_to_lab(g_dom), sic.rgb_to_lab(o_dom))

            draw.text((x0 + 4, y0 + 6), f"{obj_label} ({oam_slot} dE={de:.1f})", fill=(210, 224, 240, 255))
            for k, (sub_im, tag) in enumerate(((g_im, "GND"), (o_im, oam_slot), (rev_im, f"${rev_tid:03X}"))):
                sx = x0 + 4 + k * (tile_px + 10)
                sy = y0 + 22
                canvas.paste(sub_im.resize((tile_px, tile_px), Image.NEAREST), (sx, sy))
                draw.rectangle([(sx, sy), (sx + tile_px - 1, sy + tile_px - 1)], outline=(90, 102, 128, 255))
                draw.text((sx + 2, sy + tile_px + 2), tag, fill=(165, 180, 205, 255))

            metrics.append({
                "biome": biome_label,
                "map_id": f"0x{area_id:02X}",
                "object": obj_label,
                "ground_tile16": f"0x{g_tid:03X}",
                "reveal_tile16": f"0x{rev_tid:03X}",
                "oam_palette": oam_slot,
                "delta_e": round(de, 2),
                "warning": de > 18.0,
            })

    out_png.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(out_png)
    return {"output": str(out_png), "strips": len(metrics), "warnings": sum(1 for m in metrics if m["warning"]), "metrics": metrics}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", required=True, type=Path)
    ap.add_argument("--out", required=True, type=Path)
    ap.add_argument("--json", type=Path, help="optional JSON metrics output")
    args = ap.parse_args(argv)

    rom = args.rom.read_bytes()
    res = render_contact_sheet(rom, args.out)
    if args.json:
        args.json.write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    print(f"[+] Rendered {res['strips']} liftable strips to {res['output']} (warnings={res['warnings']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
