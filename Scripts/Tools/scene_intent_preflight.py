#!/usr/bin/env python3
"""Area & Room Scene-Intent Preflight Tool.

Generates a single upfront Area Intent Packet (JSON + Markdown + visual PNGs)
covering:
  1. Design rulings (decisions.org DECIDED), design-proposals/, Overworld ASM
     overlays ($7EF280+area, $04C6, area comparisons), dialogue refs, and labels.
  2. Graphics sheet ledger integration (Scripts/Build/gfx_ledger.py) + z3ed
     overworld-tile-catalog / overworld-tile16-reuse-audit (or pure-Python fallback)
     with exact Tile8 headroom per slot and visual <=2x rare Tile16 eviction sheets.
  3. Dungeon room collision-map flood-fill partitioning (COLMAPA $7F2000), entrance &
     door component mapping, Overworld exterior building footprint extraction,
     off-limits / disconnected wing detection, and shared blockset/palette/spriteset
     blast radius across all 0x000..0x127 rooms.

Strictly read-only on source ROMs (copies to scratch tempfiles for z3ed runs and
verifies unchanged SHA-256).
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
import json
import math
import os
from pathlib import Path
import re
import sys
from typing import Any

from PIL import Image, ImageDraw, ImageFont

TOOLS_DIR = Path(__file__).resolve().parent
if str(TOOLS_DIR) not in sys.path:
    sys.path.insert(0, str(TOOLS_DIR))

import scene_intent_common as C  # noqa: E402

# COLMAPA walkable tile attribute types (grounded in z3ed dungeon-tile-types).
DEFAULT_WALKABLE_TYPES = frozenset({
    0x00, 0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0E, 0x0F,
    0x22, 0x26, 0x40, 0x44, 0x48, 0x4C, 0x62, 0x66,
    0x81, 0x8E,
})
CONDITIONAL_DOOR_TYPES = frozenset(range(0xF0, 0xFB))
POT_BLOCK_TYPES = frozenset(range(0x70, 0x80))

# Common overworld building wall/door/roof collision TileType bytes.
EXTERIOR_BUILDING_TILETYPES = frozenset({
    0x01, 0x02, 0x04, 0x05, 0x08, 0x09, 0x0A, 0x0B,
    0x10, 0x11, 0x12, 0x13, 0x20, 0x21, 0x22, 0x23,
    0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87,
    0x88, 0x89, 0x8A, 0x8B, 0x8C, 0x8D, 0x8E, 0x8F,
})

# Palette colors matching design audit visual styling.
UI_BG = (16, 19, 27)
UI_CARD = (25, 29, 41)
UI_BORDER = (58, 67, 90)
UI_TEXT = (240, 244, 250)
UI_MUTED = (162, 174, 196)
UI_GREEN = (74, 222, 128)
UI_CYAN = (56, 189, 248)
UI_AMBER = (251, 191, 36)
UI_RED = (248, 113, 113)
COMP_COLORS = [
    (56, 189, 248, 95),
    (248, 113, 113, 115),
    (251, 191, 36, 105),
    (192, 132, 252, 105),
    (74, 222, 128, 95),
    (251, 146, 60, 105),
]


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


# ---------------------------------------------------------------------------
# A. Upfront Area Intent Collectors
# ---------------------------------------------------------------------------
def _area_search_tokens(ow_ids: list[int], room_ids: list[int],
                        labels: dict[str, dict[str, str]],
                        entrance_ids: list[int]) -> tuple[list[re.Pattern[str]], list[str]]:
    """Build exact regex patterns for matching areas, rooms, entrances, and named regions."""
    patterns: list[str] = []
    human_terms: list[str] = []
    for ow in ow_ids:
        patterns.extend([rf"\${ow:02X}\b", rf"\b0x{ow:02x}\b"])
        if ow < 0x10:
            patterns.append(rf"\$0?{ow:X}\b")
        sram = 0x7EF280 + ow
        patterns.append(rf"\${sram:06X}\b")
        lbl = labels.get("overworld_map", {}).get(f"0x{ow:02x}") or labels.get("overworld_map", {}).get(f"0x{ow:x}")
        if lbl:
            human_terms.append(lbl)
            base = lbl.split("(")[0].split("—")[0].strip()
            if len(base) >= 4:
                patterns.append(re.escape(base))
                first_word = base.split()[0]
                if first_word.lower() not in {"room", "area", "cave", "house", "shop", "east", "west", "north", "south"} and len(first_word) >= 5:
                    patterns.append(rf"\b{re.escape(first_word)}\b")
    for rid in room_ids:
        patterns.extend([
            rf"\$0?{rid:03X}\b", rf"\${rid:02X}\b",
            rf"\b0x0?{rid:03x}\b", rf"\b0x{rid:x}\b",
        ])
        lbl = labels.get("room", {}).get(f"0x{rid:02x}") or labels.get("room", {}).get(f"0x{rid:03x}")
        if lbl:
            human_terms.append(lbl)
            name_part = lbl.split("—")[0].strip()
            if len(name_part) >= 4 and not name_part.lower().startswith("room "):
                patterns.append(re.escape(name_part))
    for eid in entrance_ids:
        patterns.extend([rf"\bE{eid:02X}\b", rf"\b0x{eid:02x}\b", rf"\${eid:02X}\b"])
        elbl = labels.get("entrance", {}).get(f"0x{eid:02x}")
        if elbl and len(elbl) >= 4:
            human_terms.append(elbl)
    compiled = [re.compile(p, re.IGNORECASE) for p in dict.fromkeys(patterns)]
    return compiled, list(dict.fromkeys(human_terms))


def collect_decisions(afs_root: Path, patterns: list[re.Pattern[str]]) -> list[dict[str, Any]]:
    """Extract matching DECIDED/OPEN rulings from decisions.org."""
    dec_path = afs_root / "knowledge" / "planning" / "decisions.org"
    if not dec_path.is_file() or not patterns:
        return []
    lines = dec_path.read_text(encoding="utf-8", errors="replace").splitlines()
    sections: list[tuple[int, str, list[str]]] = []
    cur_start, cur_head, cur_body = 0, "", []
    for idx, line in enumerate(lines, 1):
        if line.startswith("* "):
            if cur_head:
                sections.append((cur_start, cur_head, cur_body))
            cur_start, cur_head, cur_body = idx, line, []
        elif cur_head:
            cur_body.append(line)
    if cur_head:
        sections.append((cur_start, cur_head, cur_body))

    matches: list[dict[str, Any]] = []
    for ln, head, body in sections:
        text = head + "\n" + "\n".join(body)
        hits = sum(1 for p in patterns if p.search(text))
        if hits == 0:
            continue
        status = "DECIDED" if head.startswith("* DECIDED") else ("OPEN" if head.startswith("* OPEN") else "OTHER")
        doc_ref = ""
        for b in body[:8]:
            m = re.match(r"^\s*:DOC:\s*(.+)$", b)
            if m:
                doc_ref = m.group(1).strip()
                break
        summary_lines = [
            b.strip() for b in body
            if b.strip() and not b.strip().startswith(":")
        ][:4]
        matches.append({
            "line": ln,
            "status": status,
            "heading": head[2:].strip(),
            "doc": doc_ref,
            "match_score": hits,
            "excerpt": " ".join(summary_lines)[:260],
        })
    matches.sort(key=lambda m: (m["status"] != "DECIDED", -m["match_score"], m["line"]))
    return matches[:25]


def collect_design_proposals(proposals_dirs: list[Path],
                             patterns: list[re.Pattern[str]],
                             ow_ids: list[int]) -> list[dict[str, Any]]:
    """Locate matching PROPOSAL.md / design docs in scratchpad or repo design-proposals."""
    seen: set[Path] = set()
    found: list[dict[str, Any]] = []
    for root in proposals_dirs:
        if not root or not root.is_dir():
            continue
        for md in sorted(root.glob("*/*.md")) + sorted(root.glob("*.md")):
            rp = md.resolve()
            if rp in seen:
                continue
            seen.add(rp)
            if md.name.upper() not in ("PROPOSAL.MD", "README.MD", "AUDIT.MD", "DESIGN.MD") and "PROPOSAL" not in md.name.upper():
                continue
            txt = md.read_text(encoding="utf-8", errors="replace")
            head_snippet = "\n".join(txt.splitlines()[:40])
            hits = sum(1 for p in patterns if p.search(md.parent.name + "\n" + txt))
            # Prefer docs explicitly targeting the area ID in filename or top section.
            area_in_top = any(
                re.search(rf"(?:\$|0x){ow:02x}\b", head_snippet, re.IGNORECASE)
                for ow in ow_ids
            )
            if hits > 0 or area_in_top:
                title = next((l.lstrip("# ").strip() for l in txt.splitlines() if l.startswith("#")), md.stem)
                found.append({
                    "path": str(md),
                    "title": title,
                    "hits": hits + (3 if area_in_top else 0),
                })
    found.sort(key=lambda x: (-x["hits"], x["path"]))
    return found[:12]


def collect_asm_overlays_and_hooks(repo_root: Path, ow_ids: list[int],
                                   room_ids: list[int]) -> dict[str, Any]:
    """Find SRAM overlay flags ($7EF280 + ow), overlays.asm hooks, and area/room ASM checks."""
    sram_refs: list[dict[str, Any]] = []
    area_hooks: list[dict[str, Any]] = []
    pinned_tile16s: set[int] = set()

    # Scan Overworld/*.asm for overlay hooks, area comparisons, and ASM-pinned Tile16 literals.
    sram_targets = {0x7EF280 + ow: ow for ow in ow_ids}
    sram_pat = re.compile(r"\$(7EF2[89A-F][0-9A-F])\b", re.IGNORECASE)
    ow_cmp_pats = {
        ow: re.compile(rf"(?:CMP(?:\.[bw])?\s+#\$(?:00)?{ow:02X}\b|\b#$02{ow:02X}\b)", re.IGNORECASE)
        for ow in ow_ids
    }
    room_cmp_pats = {
        rid: re.compile(rf"\$0?{rid:03X}\b|\b0x0?{rid:03x}\b", re.IGNORECASE)
        for rid in room_ids
    }
    pin_word_pat = re.compile(r"\$([0-9A-Fa-f]{4})\b")

    scan_dirs = [repo_root / d for d in ("Overworld", "Core", "Items", "Sprites", "Dungeons", "Docs/Technical") if (repo_root / d).exists()]
    for sdir in scan_dirs:
        for p in sorted(sdir.rglob("*")):
            if p.suffix.lower() not in (".asm", ".md"):
                continue
            rel = p.relative_to(repo_root).as_posix()
            text = p.read_text(encoding="utf-8", errors="replace")
            for idx, line in enumerate(text.splitlines(), 1):
                for m in sram_pat.finditer(line):
                    addr = int(m.group(1), 16)
                    if addr in sram_targets:
                        sram_refs.append({
                            "area": f"0x{sram_targets[addr]:02X}",
                            "sram": f"${addr:06X}",
                            "location": f"{rel}:{idx}",
                            "line": line.strip()[:140],
                        })
                if p.suffix.lower() == ".asm":
                    for ow, pat in ow_cmp_pats.items():
                        if pat.search(line):
                            area_hooks.append({
                                "kind": "ow_area_check",
                                "target": f"0x{ow:02X}",
                                "location": f"{rel}:{idx}",
                                "line": line.strip()[:140],
                            })
                    for rid, pat in room_cmp_pats.items():
                        if pat.search(line):
                            area_hooks.append({
                                "kind": "room_ref",
                                "target": f"0x{rid:03X}",
                                "location": f"{rel}:{idx}",
                                "line": line.strip()[:140],
                            })
                    if p.parent.name == "Overworld" and ("Tile16" in line or "tile16" in line or "CPY.w" in line or "dw $" in line or "Overlay" in rel):
                        for wm in pin_word_pat.finditer(line.split(";", 1)[0]):
                            val = int(wm.group(1), 16)
                            if val < C.EXPANDED_TILE16_COUNT:
                                pinned_tile16s.add(val)

    return {
        "sram_overlay_flags": {
            f"0x{ow:02X}": f"${0x7EF280 + ow:06X}" for ow in ow_ids
        },
        "sram_flag_refs": sram_refs[:25],
        "asm_hooks": area_hooks[:30],
        "asm_pinned_tile16s": sorted(pinned_tile16s),
    }


def collect_message_refs(repo_root: Path, patterns: list[re.Pattern[str]],
                         area_msg_ids: dict[int, int]) -> dict[str, Any]:
    """Scan Core/messages.org headers and Data/dialogue/expanded_messages.json metadata."""
    org_hits: list[dict[str, str]] = []
    msg_org = repo_root / "Core" / "messages.org"
    if msg_org.is_file():
        lines = msg_org.read_text(encoding="utf-8", errors="replace").splitlines()
        cur_id, cur_title, cur_buf = "", "", []
        for line in lines:
            m = re.match(r"^\*\*\s+([0-9A-Fa-f]+)\s+-\s+(.+)$", line)
            if m:
                if cur_id and any(p.search(cur_title + "\n" + "\n".join(cur_buf)) for p in patterns):
                    org_hits.append({"id": cur_id, "title": cur_title.strip()})
                cur_id, cur_title, cur_buf = m.group(1), m.group(2), []
            elif cur_id:
                cur_buf.append(line)
        if cur_id and any(p.search(cur_title + "\n" + "\n".join(cur_buf)) for p in patterns):
            org_hits.append({"id": cur_id, "title": cur_title.strip()})

    exp_json = repo_root / "Data" / "dialogue" / "expanded_messages.json"
    expanded_count = 0
    area_expanded_matches: list[dict[str, Any]] = []
    if exp_json.is_file():
        data = json.loads(exp_json.read_text(encoding="utf-8", errors="replace"))
        msgs = data.get("messages", [])
        expanded_count = len(msgs)
        target_ids = set(area_msg_ids.values())
        for msg in msgs:
            mid = msg.get("id")
            if mid in target_ids:
                area_expanded_matches.append({
                    "id": f"0x{mid:04X}",
                    "bank": msg.get("bank", ""),
                    "preview": str(msg.get("text", ""))[:80],
                })

    return {
        "area_message_ids": {f"0x{k:02X}": f"0x{v:04X}" for k, v in area_msg_ids.items()},
        "messages_org_matches": org_hits[:20],
        "expanded_message_count": expanded_count,
        "area_expanded_matches": area_expanded_matches,
    }


# ---------------------------------------------------------------------------
# B. Graphics Budget & Cut-to-Fit Rare Tile16 Analysis
# ---------------------------------------------------------------------------
def _scan_asm_protected_tile16s(repo_root: Path) -> set[int]:
    """Extract Tile16 literals specifically protected in Overworld ASM tables."""
    protected: set[int] = set()
    ov_dir = repo_root / "Overworld"
    if not ov_dir.is_dir():
        return protected
    for p in ov_dir.glob("*.asm"):
        txt = p.read_text(encoding="utf-8", errors="replace")
        for line in txt.splitlines():
            code = line.split(";", 1)[0]
            if any(k in line for k in ("HorseFence", "Tile16", "ValidDoor", "StoneArch", "02CD", "01AD")):
                for m in re.finditer(r"\$([0-9A-Fa-f]{4})\b", code):
                    v = int(m.group(1), 16)
                    if v < C.EXPANDED_TILE16_COUNT:
                        protected.add(v)
    return protected


def _find_global_tile8_usage(tile16s: list[tuple[int, int, int, int]]) -> dict[int, set[int]]:
    """Map Tile16 ID -> set of Tile8 global indices (0..511), and vice versa."""
    t8_to_t16: dict[int, set[int]] = defaultdict(set)
    for t16_id, words in enumerate(tile16s):
        for w in words:
            ch = w & 0x3FF
            if ch < 512:
                t8_to_t16[ch].add(t16_id)
    return t8_to_t16


def _render_cut_to_fit_sheet(
    area_id: int,
    rare_items: list[dict[str, Any]],
    tile16s: list[tuple[int, int, int, int]],
    slot_chars: dict[int, list[tuple[int, ...]]],
    pal128: list[tuple[int, int, int]],
    out_path: Path,
) -> Path:
    """Render a crisp 4x thumbnail contact sheet of rare <=2x Tile16 eviction candidates."""
    f_title = _load_font(20)
    f_head = _load_font(13)
    f_mono = _load_font(12, mono=True)
    items = rare_items[:18]
    cols = 2
    rows = max(1, (len(items) + cols - 1) // cols)
    card_w, card_h = 700, 96
    pad = 16
    w = pad * 2 + cols * card_w + (cols - 1) * 14
    h = 74 + rows * (card_h + 10) + pad

    img = Image.new("RGB", (w, h), UI_BG)
    dr = ImageDraw.Draw(img)
    dr.text((pad, 16), f"OW 0x{area_id:02X} Cut-to-Fit Rare Tile16 Eviction Candidates (<=2x)", font=f_title, fill=UI_TEXT)
    dr.text((pad, 44), f"Showing {len(items)} of {len(rare_items)} rare Tile16s with freed Tile8 slots & lowest-delta common replacements", font=f_head, fill=UI_MUTED)

    scale = 4
    tsize = 16 * scale
    for idx, item in enumerate(items):
        col = idx % cols
        row = idx // cols
        cx = pad + col * (card_w + 14)
        cy = 74 + row * (card_h + 10)
        accent = UI_AMBER if item["freed_tile8s"] else UI_BORDER
        dr.rounded_rectangle([cx, cy, cx + card_w, cy + card_h], radius=6, fill=UI_CARD, outline=accent, width=2)

        tid = int(item["tile16"], 16)
        t_img = C.render_tile16_rgba(tile16s[tid], slot_chars, pal128).resize((tsize, tsize), Image.Resampling.NEAREST).convert("RGB")
        img.paste(t_img, (cx + 12, cy + 16))

        freed_str = ", ".join(f"S{x['slot']}:0x{x['chr']:02X}" for x in item["freed_tile8s"][:4]) or "0 unique t8"
        dr.text((cx + 88, cy + 12), f"{item['tile16']} ({item['count']}x)", font=f_head, fill=UI_TEXT)
        dr.text((cx + 88, cy + 32), f"Frees {len(item['freed_tile8s'])} Tile8: {freed_str}", font=f_mono, fill=UI_GREEN if item["freed_tile8s"] else UI_MUTED)
        pin_note = " [ASM-PINNED]" if item["asm_pinned"] else ""
        if pin_note:
            dr.text((cx + 215, cy + 12), pin_note, font=f_mono, fill=UI_RED)

        sugs = item["suggested_replacements"]
        if sugs:
            rep = sugs[0]
            rid = int(rep["tile16"], 16)
            r_img = C.render_tile16_rgba(tile16s[rid], slot_chars, pal128).resize((tsize, tsize), Image.Resampling.NEAREST).convert("RGB")
            rx = cx + card_w - tsize - 14
            dr.text((rx - 36, cy + 28), "->", font=f_title, fill=UI_CYAN)
            img.paste(r_img, (rx, cy + 16))
            src_tt = ",".join(t[2:] for t in item["tiletypes"])
            dst_tt = ",".join(t[2:] for t in rep["tiletypes"])
            dr.text((cx + 88, cy + 54), f"Replace -> {rep['tile16']} ({rep['count']}x) dE={rep['lab_delta']:.1f}", font=f_mono, fill=UI_CYAN)
            dr.text((cx + 88, cy + 72), f"TileType [{src_tt}] -> [{dst_tt}]", font=f_mono, fill=UI_MUTED)

    img.save(out_path)
    return out_path


def _ledger_summary_for_sheets(rom: bytes, staged_rom: Path | None,
                               z3ed_bin: Path | None, repo_root: Path) -> dict[int, dict[str, Any]]:
    """Query gfx_ledger.py for active sheet loaders and off-limits/follower pins."""
    build_dir = repo_root / "Scripts" / "Build"
    if str(build_dir) not in sys.path:
        sys.path.insert(0, str(build_dir))
    import gfx_ledger

    inv: dict[str, Any] | None = None
    if staged_rom and z3ed_bin:
        out = staged_rom.parent / "gfx_inv.json"
        res, _ = C.run_z3ed_json(z3ed_bin, [
            "gfx-sheet-inventory", f"--rom={staged_rom}", "--out", str(out), "--format", "json"
        ])
        if out.is_file():
            inv = json.loads(out.read_text(encoding="utf-8"))
            gfx_ledger.add_tail_areas(inv, staged_rom)
        elif isinstance(res, dict) and "sheets" in res:
            inv = res
            gfx_ledger.add_tail_areas(inv, staged_rom)

    out_map: dict[int, dict[str, Any]] = {}
    if inv is not None:
        loaders = gfx_ledger.build_loaders(inv, repo_root=repo_root, include_code_refs=True)
        for s in inv.get("sheets", []):
            sid = int(s["hex"], 16)
            ld = loaders.get(sid, {})
            n_users = sum(len(v) for kinds in ld.values() for v in kinds.values())
            status, reason = gfx_ledger.classify(sid, s, gfx_ledger.OWNERS.get(sid), n_users)
            out_map[sid] = {
                "sheet": f"0x{sid:02X}",
                "status": status,
                "reason": reason,
                "free_16x16_blocks": len(s.get("free_16x16_blocks", [])),
                "ow_areas_static": s.get("usage", {}).get("ow_areas_static", []),
                "room_blocksets": sorted({int(x) for x in ld.get("room_blockset", {}).values() for x in x}) if ld.get("room_blockset") else [],
                "main_blocksets": sorted({int(x) for x in ld.get("main_blockset", {}).values() for x in x}) if ld.get("main_blockset") else [],
                "user_count": n_users,
            }
    else:
        for sid in range(255):
            if sid in gfx_ledger.RESERVED:
                out_map[sid] = {"sheet": f"0x{sid:02X}", "status": "OFF-LIMITS", "reason": gfx_ledger.RESERVED[sid], "user_count": 0}
            elif sid in gfx_ledger.NOT_CLEARED:
                out_map[sid] = {"sheet": f"0x{sid:02X}", "status": "OFF-LIMITS", "reason": "unreferenced but not cleared: " + gfx_ledger.NOT_CLEARED[sid], "user_count": 0}
    return out_map


def analyze_overworld_area(
    rom: bytes,
    area_id: int,
    *,
    repo_root: Path,
    staged_rom: Path | None,
    z3ed_bin: Path | None,
    z3ed_cmds: set[str],
    ledger_map: dict[int, dict[str, Any]],
    max_rare: int = 2,
    out_dir: Path | None = None,
) -> dict[str, Any]:
    """Analyze OW area Tile8 slot budget, rare <=2x Tile16 cuts, and entrances."""
    static_sheets = C.load_area_static_graphics(rom, area_id)
    anim_sheet = C.load_area_animated_sheet(rom, area_id)
    grid, size_label = C.decode_large_overworld_grid(rom, area_id)
    tile16s = C.decode_tile16_table(rom)
    pal128 = C.decode_overworld_palette_128(rom, area_id)
    slot_chars = C.load_overworld_slot_chars(rom, area_id)

    # Query z3ed overworld-describe-map & Wave 1B catalog/reuse commands if present.
    z3ed_desc = None
    z3ed_catalog = None
    z3ed_reuse = None
    if staged_rom and z3ed_bin:
        if "overworld-describe-map" in z3ed_cmds:
            z3ed_desc, _ = C.run_z3ed_json(z3ed_bin, [
                "overworld-describe-map", f"--rom={staged_rom}", f"--screen=0x{area_id:02X}", "--format=json"
            ])
        if "overworld-tile-catalog" in z3ed_cmds:
            z3ed_catalog, _ = C.run_z3ed_json(z3ed_bin, [
                "overworld-tile-catalog", f"--rom={staged_rom}", f"--map=0x{area_id:02X}", "--unused-only", "--top=0", "--format=json"
            ])
        if "overworld-tile16-reuse-audit" in z3ed_cmds:
            z3ed_reuse, _ = C.run_z3ed_json(z3ed_bin, [
                "overworld-tile16-reuse-audit", f"--rom={staged_rom}", f"--map=0x{area_id:02X}", "--json"
            ])

    # Count Tile16 placements on this area grid (plus coordinates).
    t16_positions: dict[int, list[tuple[int, int]]] = defaultdict(list)
    for y, row in enumerate(grid):
        for x, tid in enumerate(row):
            if tid < len(tile16s):
                t16_positions[tid].append((x, y))

    # Track per-slot Tile8 references both on this area map AND globally across Map16.
    area_chr_to_t16: dict[int, Counter[int]] = defaultdict(Counter)
    for tid, pts in t16_positions.items():
        for w in tile16s[tid]:
            ch = w & 0x3FF
            if ch < 512:
                area_chr_to_t16[ch][tid] += len(pts)

    global_chr_to_t16 = _find_global_tile8_usage(tile16s)

    # Also build rendered RGB/Lab fingerprints of common tiles on this area for replacement ranking.
    tile_types = rom[C.PC_TILETYPE:C.PC_TILETYPE + 512] if len(rom) >= C.PC_TILETYPE + 512 else bytes([0] * 512)

    def t16_types(tid: int) -> tuple[int, ...]:
        return tuple(tile_types[w & 0x1FF] if (w & 0x1FF) < len(tile_types) else 0 for w in tile16s[tid])

    slot_budget = []
    for slot_idx, sid in enumerate(static_sheets):
        base = slot_idx * 64
        area_used = sorted(ch - base for ch in range(base, base + 64) if area_chr_to_t16.get(ch))
        global_used = sorted(ch - base for ch in range(base, base + 64) if global_chr_to_t16.get(ch))
        area_free = sorted(set(range(64)) - set(area_used))
        global_free = sorted(set(range(64)) - set(global_used))
        ldg = ledger_map.get(sid, {})
        slot_budget.append({
            "slot": slot_idx,
            "sheet": f"0x{sid:02X}",
            "ledger_status": ldg.get("status", "IN-USE"),
            "ow_shared_areas": len(ldg.get("ow_areas_static", [])),
            "area_used_tile8_count": len(area_used),
            "area_unused_tile8_count": len(area_free),
            "global_map16_unused_tile8_count": len(global_free),
            "area_unused_chrs": [f"0x{c:02X}" for c in area_free[:16]],
        })

    # Merge Wave 1B catalog slot unused CHRs if z3ed supplied them.
    if isinstance(z3ed_catalog, dict):
        by_sheet = {s.get("sheet", "").upper(): s for s in z3ed_catalog.get("loaded_sheets", []) if isinstance(s, dict)}
        for sb in slot_budget:
            m = by_sheet.get(sb["sheet"].upper())
            if m and "unused_chr_count" in m:
                sb["z3ed_unused_chr_count"] = m["unused_chr_count"]

    asm_pins = _scan_asm_protected_tile16s(repo_root)
    common_tids = [tid for tid, pts in t16_positions.items() if len(pts) >= 3]
    def _rgb_pixels(im_rgb: Image.Image) -> list[tuple[int, int, int]]:
        raw = im_rgb.tobytes()
        return [(raw[i], raw[i + 1], raw[i + 2]) for i in range(0, len(raw), 3)]

    common_imgs: dict[int, list[tuple[int, int, int]]] = {}
    for tid in common_tids:
        im = C.render_tile16_rgba(tile16s[tid], slot_chars, pal128).convert("RGB")
        common_imgs[tid] = _rgb_pixels(im)

    def avg_lab_delta(px_a: list[tuple[int, int, int]], px_b: list[tuple[int, int, int]]) -> float:
        # Fast RGB weighted perceptual metric over 16x16 rendered pixels.
        total = 0.0
        for (r1, g1, b1), (r2, g2, b2) in zip(px_a, px_b):
            rm = 0.5 * (r1 + r2)
            dr, dg, db = r1 - r2, g1 - g2, b1 - b2
            total += math.sqrt(((2 + rm / 256.0) * dr * dr) + 4 * dg * dg + ((2 + (255 - rm) / 256.0) * db * db))
        return total / max(1, len(px_a))

    rare_candidates: list[dict[str, Any]] = []
    for tid, pts in sorted(t16_positions.items(), key=lambda kv: (len(kv[1]), kv[0])):
        cnt = len(pts)
        if cnt > max_rare:
            continue
        freed = []
        seen_ch = set()
        for w in tile16s[tid]:
            ch = w & 0x3FF
            if ch < 512 and ch not in seen_ch:
                seen_ch.add(ch)
                if len(area_chr_to_t16[ch]) == 1:
                    freed.append({"slot": ch // 64, "chr": ch % 64, "global_tile8": ch})
        tt = t16_types(tid)
        t_px = _rgb_pixels(C.render_tile16_rgba(tile16s[tid], slot_chars, pal128).convert("RGB"))
        ranked = []
        for rep_id in common_tids:
            if rep_id == tid:
                continue
            rtt = t16_types(rep_id)
            tt_penalty = 0.0 if rtt == tt else 35.0
            delta = avg_lab_delta(t_px, common_imgs[rep_id]) + tt_penalty
            ranked.append((delta, rep_id, len(t16_positions[rep_id]), rtt))
        ranked.sort()
        rare_candidates.append({
            "tile16": f"0x{tid:04X}",
            "count": cnt,
            "coords": pts,
            "asm_pinned": tid in asm_pins,
            "freed_tile8s": freed,
            "tiletypes": [f"0x{x:02X}" for x in tt],
            "suggested_replacements": [
                {
                    "tile16": f"0x{rid:04X}",
                    "count": rcnt,
                    "lab_delta": round(d, 2),
                    "tiletypes": [f"0x{x:02X}" for x in rtt],
                }
                for d, rid, rcnt, rtt in ranked[:3]
            ],
        })

    # Prioritize eviction candidates that free the most unique Tile8 slots without ASM pins.
    rare_candidates.sort(key=lambda r: (r["asm_pinned"], -len(r["freed_tile8s"]), r["count"], int(r["tile16"], 16)))

    eviction_sheet = None
    if out_dir is not None and rare_candidates:
        out_dir.mkdir(parents=True, exist_ok=True)
        eviction_sheet = str(_render_cut_to_fit_sheet(
            area_id, rare_candidates, tile16s, slot_chars, pal128,
            out_dir / f"cut_to_fit_ow_{area_id:02X}.png",
        ))

    entrances = []
    if isinstance(z3ed_desc, dict):
        entrances = z3ed_desc.get("entrances", [])

    return {
        "area_id": f"0x{area_id:02X}",
        "parent_id": f"0x{C.area_parent_id(rom, area_id):02X}",
        "size": size_label,
        "grid_dims": [len(grid[0]), len(grid)],
        "static_graphics": [f"0x{s:02X}" for s in static_sheets],
        "animated_sheet": f"0x{anim_sheet:02X}",
        "message_id": (z3ed_desc or {}).get("message_id"),
        "overlay": (z3ed_desc or {}).get("overlay"),
        "entrances": entrances,
        "slot_budget": slot_budget,
        "unique_tile16_used": len(t16_positions),
        "rare_tile16_count": len(rare_candidates),
        "rare_tile16_eviction_candidates": rare_candidates[:30],
        "cut_to_fit_sheet_png": eviction_sheet,
        "z3ed_tile_catalog_used": z3ed_catalog is not None,
        "z3ed_reuse_audit": z3ed_reuse,
        "grid_tile16": grid,
        "tile_types": tile_types,
        "tile16_table": tile16s,
    }


def detect_exterior_building_footprint(area_report: dict[str, Any], ow_x: int, ow_y: int) -> dict[str, Any]:
    """Infer OW exterior building bounding box in Tile16 units around entrance world (ow_x, ow_y)."""
    grid: list[list[int]] = area_report["grid_tile16"]
    tile16s = area_report["tile16_table"]
    tile_types = area_report["tile_types"]
    area_id = int(area_report["area_id"], 16)
    col_off = (area_id % 8) * 512
    row_off = ((area_id % 64) // 8) * 512
    lx = (ow_x - col_off) // 16
    ly = (ow_y - row_off) // 16
    h, w = len(grid), len(grid[0]) if grid else 0
    if not (0 <= lx < w and 0 <= ly < h):
        return {"in_area": False, "local_tile": [lx, ly]}

    def is_building_cell(cx: int, cy: int) -> bool:
        tid = grid[cy][cx]
        if tid >= len(tile16s):
            return False
        tts = {tile_types[word & 0x1FF] for word in tile16s[tid] if (word & 0x1FF) < len(tile_types)}
        return bool(tts & EXTERIOR_BUILDING_TILETYPES)

    # Seed just above the entrance mat (doors sit on the bottom facade edge).
    seed = None
    for sy in (ly, ly - 1, ly - 2):
        for sx in (lx, lx - 1, lx + 1):
            if 0 <= sx < w and 0 <= sy < h and is_building_cell(sx, sy):
                seed = (sx, sy)
                break
        if seed:
            break
    if seed is None:
        return {"in_area": True, "local_tile": [lx, ly], "building_found": False}

    vis = {seed}
    q = deque([seed])
    # Constrain flood fill to bounded house size so long cliff faces don't swallow whole village.
    while q and len(vis) < 96:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            nx, ny = cx + dx, cy + dy
            if 0 <= nx < w and 0 <= ny < h and (nx, ny) not in vis and abs(nx - lx) <= 10 and -10 <= ny - ly <= 2:
                if is_building_cell(nx, ny):
                    vis.add((nx, ny))
                    q.append((nx, ny))
    xs = [p[0] for p in vis]
    ys = [p[1] for p in vis]
    return {
        "in_area": True,
        "local_tile": [lx, ly],
        "building_found": True,
        "tile_bbox": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
        "width_tiles": max(xs) - min(xs) + 1,
        "height_tiles": max(ys) - min(ys) + 1,
        "width_px": (max(xs) - min(xs) + 1) * 16,
        "height_px": (max(ys) - min(ys) + 1) * 16,
    }


# ---------------------------------------------------------------------------
# C. Dungeon Room Flood-Fill Partition & Blockset Blast Radius
# ---------------------------------------------------------------------------
def partition_room_grid(grid: list[list[int]],
                        walkable_types: frozenset[int] = DEFAULT_WALKABLE_TYPES,
                        *, min_tiles: int = 16) -> list[dict[str, Any]]:
    """Run BFS connected-components over 64x64 COLMAPA grid, returning sorted regions."""
    h = len(grid)
    w = len(grid[0]) if h else 0
    vis = [[False] * w for _ in range(h)]
    comps: list[dict[str, Any]] = []
    tiny_pockets = 0

    for y in range(h):
        for x in range(w):
            if vis[y][x] or grid[y][x] not in walkable_types:
                continue
            q = deque([(x, y)])
            vis[y][x] = True
            pts: list[tuple[int, int]] = []
            adj_cond_doors: set[tuple[int, int]] = set()
            while q:
                cx, cy = q.popleft()
                pts.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nx, ny = cx + dx, cy + dy
                    if 0 <= nx < w and 0 <= ny < h:
                        val = grid[ny][nx]
                        if not vis[ny][nx] and val in walkable_types:
                            vis[ny][nx] = True
                            q.append((nx, ny))
                        elif val in CONDITIONAL_DOOR_TYPES:
                            adj_cond_doors.add((nx, ny))
            if len(pts) < min_tiles:
                tiny_pockets += 1
                continue
            xs = [p[0] for p in pts]
            ys = [p[1] for p in pts]
            cx_px = sum(p[0] * 8 + 4 for p in pts) / len(pts)
            cy_px = sum(p[1] * 8 + 4 for p in pts) / len(pts)
            x0, y0, x1, y1 = min(xs) * 8, min(ys) * 8, (max(xs) + 1) * 8, (max(ys) + 1) * 8
            quad_ns = "N" if cy_px < 256 else "S"
            quad_ew = "W" if cx_px < 256 else "E"
            span_x = "W+E" if (x0 < 200 and x1 > 312) else quad_ew
            span_y = "N+S" if (y0 < 200 and y1 > 312) else quad_ns
            label = f"{span_y}{span_x}" if ("+" not in span_y or "+" not in span_x) else "FullRoom"
            comps.append({
                "tile_count": len(pts),
                "tile_bbox": [min(xs), min(ys), max(xs) + 1, max(ys) + 1],
                "px_bbox": [x0, y0, x1, y1],
                "centroid_px": [round(cx_px, 1), round(cy_px, 1)],
                "quadrant": label,
                "adjacent_conditional_door_tiles": sorted(adj_cond_doors),
                "_points": set(pts),
            })

    comps.sort(key=lambda c: (-c["tile_count"], c["px_bbox"][1], c["px_bbox"][0]))
    for idx, c in enumerate(comps):
        c["component_id"] = idx
    return comps


def map_point_to_component(comps: list[dict[str, Any]], px: int, py: int,
                           *, max_snap_tiles: int = 3) -> int | None:
    """Find component_id containing (px, py) or within max_snap_tiles of doorway/mat."""
    tx, ty = px // 8, py // 8
    best_id = None
    best_dist = (max_snap_tiles * 8) ** 2 + 1
    for c in comps:
        if (tx, ty) in c["_points"]:
            return c["component_id"]
        x0, y0, x1, y1 = c["px_bbox"]
        if x0 - max_snap_tiles * 8 <= px <= x1 + max_snap_tiles * 8 and y0 - max_snap_tiles * 8 <= py <= y1 + max_snap_tiles * 8:
            for cx, cy in c["_points"]:
                d2 = (cx * 8 + 4 - px) ** 2 + (cy * 8 + 4 - py) ** 2
                if d2 < best_dist:
                    best_dist = d2
                    best_id = c["component_id"]
    return best_id


def compute_room_blast_radius(rom: bytes, room_id: int,
                              labels: dict[str, dict[str, str]],
                              ledger_map: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Find every room sharing blockset, spriteset, or palette, plus follower DMA conflicts."""
    hdr = C.read_room_header(rom, room_id)
    if hdr is None:
        return {"error": f"room 0x{room_id:03X} header unreadable"}
    bs, pal, ss = hdr["blockset"], hdr["palette"], hdr["spriteset"]
    same_bs, same_pal, same_ss = [], [], []
    room_lbls = labels.get("room", {})
    for r in range(C.ROOM_COUNT):
        rh = C.read_room_header(rom, r)
        if rh is None:
            continue
        rname = room_lbls.get(f"0x{r:02x}") or room_lbls.get(f"0x{r:03x}") or f"Room ${r:03X}"
        rec = f"0x{r:03X} ({rname})"
        if rh["blockset"] == bs:
            same_bs.append({"room": f"0x{r:03X}", "name": rname, "is_dungeon": not any(w in rname.lower() for w in ("tavern", "bar", "library", "house", "shop", "hotel", "hall", "school", "inn", "cave"))})
        if rh["palette"] == pal:
            same_pal.append(rec)
        if rh["spriteset"] == ss:
            same_ss.append(rec)

    # Extract sheets loaded by main_blocksets[bs] and room_blocksets[bs] + spritesets[ss].
    gfx_main_pc = C.read_u16(rom, 0x6237)
    main_base = C.snes_to_pc(gfx_main_pc) if gfx_main_pc >= 0x8000 else C.PC_GFX_GROUPS2
    bs_sheets = list(rom[main_base + bs * 8:main_base + bs * 8 + 8]) if main_base + bs * 8 + 8 <= len(rom) else []
    rb_sheets = list(rom[C.PC_GFX_GROUPS1 + bs * 4:C.PC_GFX_GROUPS1 + bs * 4 + 4]) if C.PC_GFX_GROUPS1 + bs * 4 + 4 <= len(rom) else []
    ss_raw = list(rom[0x5B57 + ss * 4:0x5B57 + ss * 4 + 4]) if 0x5B57 + ss * 4 + 4 <= len(rom) else []
    ss_sheets = [v + 0x73 for v in ss_raw]

    follower_warnings = []
    for label, sids in (("main_blockset", bs_sheets), ("room_blockset", rb_sheets), ("spriteset", ss_sheets)):
        for sid in sids:
            if sid in C.FOLLOWER_DMA_SHEETS or (sid in ledger_map and ledger_map[sid].get("status") == "OFF-LIMITS"):
                follower_warnings.append(f"{label} references off-limits/DMA sheet 0x{sid:02X}: {ledger_map.get(sid, {}).get('reason', 'DMA pin')}")

    named_dungeons = ("Dragon Ship", "Fortress", "Castle", "Shrine", "Temple", "Mines", "Grotto", "Palace", "Sanctum")
    dungeons_sharing_bs = sorted(
        {x["name"].split("—")[0].strip() for x in same_bs if x["is_dungeon"]},
        key=lambda n: (not any(d.lower() in n.lower() for d in named_dungeons), n),
    )
    return {
        "room_id": f"0x{room_id:03X}",
        "blockset": f"0x{bs:02X}",
        "palette": f"0x{pal:02X}",
        "spriteset": f"0x{ss:02X}",
        "main_blockset_sheets": [f"0x{s:02X}" for s in bs_sheets],
        "room_blockset_sheets": [f"0x{s:02X}" for s in rb_sheets],
        "spriteset_sheets": [f"0x{s:02X}" for s in ss_sheets],
        "rooms_sharing_blockset_count": len(same_bs),
        "dungeons_or_non_house_sharing_blockset": dungeons_sharing_bs[:20],
        "rooms_sharing_blockset_sample": [x["room"] + " " + x["name"] for x in same_bs[:16]],
        "rooms_sharing_palette_count": len(same_pal),
        "rooms_sharing_spriteset_count": len(same_ss),
        "off_limits_sheet_warnings": follower_warnings,
    }


def _render_room_partition_png(
    room_id: int,
    room_name: str,
    comps: list[dict[str, Any]],
    entrances_mapped: list[dict[str, Any]],
    z3ed_bin: Path | None,
    z3ed_cmds: set[str],
    staged_rom: Path | None,
    out_path: Path,
) -> str | None:
    """Overlay sub-room flood-fill bounds & entrance pins on genuine z3ed dungeon-render."""
    if not (staged_rom and z3ed_bin and "dungeon-render" in z3ed_cmds):
        return None
    raw_png = out_path.parent / f".tmp_ppu_room_{room_id:03X}.png"
    proc = C.run_z3ed_json(z3ed_bin, [
        "dungeon-render", f"--rom={staged_rom}", f"--room=0x{room_id:03X}", f"--output={raw_png}"
    ])
    if not raw_png.is_file():
        return None
    base = Image.open(raw_png).convert("RGBA")
    raw_png.unlink(missing_ok=True)
    overlay = Image.new("RGBA", base.size, (0, 0, 0, 0))
    dr = ImageDraw.Draw(overlay)
    f_lbl = _load_font(12, mono=True)
    for c in comps:
        cid = c["component_id"]
        col = COMP_COLORS[cid % len(COMP_COLORS)]
        pts = c.get("_points", set())
        if pts:
            # Shade only actual walkable 8x8 tiles (preserves L-shapes without covering voids).
            fill_col = (col[0], col[1], col[2], 78)
            edge_col = (col[0], col[1], col[2], 235)
            for tx, ty in pts:
                px0, py0 = tx * 8, ty * 8
                dr.rectangle([px0, py0, px0 + 7, py0 + 7], fill=fill_col)
                if (tx - 1, ty) not in pts:
                    dr.line([(px0, py0), (px0, py0 + 7)], fill=edge_col, width=2)
                if (tx + 1, ty) not in pts:
                    dr.line([(px0 + 7, py0), (px0 + 7, py0 + 7)], fill=edge_col, width=2)
                if (tx, ty - 1) not in pts:
                    dr.line([(px0, py0), (px0 + 7, py0)], fill=edge_col, width=2)
                if (tx, ty + 1) not in pts:
                    dr.line([(px0, py0 + 7), (px0 + 7, py0 + 7)], fill=edge_col, width=2)
        x0, y0, _, _ = c["px_bbox"]
        tag = f"C{cid} {c['quadrant']} ({c['tile_count']}t)"
        if c.get("disconnected_flag"):
            tag += " [DISCONNECTED]"
        tag_w = int(dr.textlength(tag, font=f_lbl)) + 10
        lx = max(2, min(x0 + 2, base.width - tag_w - 2))
        ly = max(2, min(y0 + 2, base.height - 20))
        dr.rectangle([lx, ly, lx + tag_w, ly + 18], fill=(16, 19, 27, 215))
        dr.text((lx + 4, ly + 2), tag, font=f_lbl, fill=(255, 255, 255, 255))
    for em in entrances_mapped:
        lx, ly = em["room_local_px"]
        dr.ellipse([lx - 6, ly - 6, lx + 6, ly + 6], fill=(74, 222, 128, 230), outline=(16, 19, 27, 255), width=2)
        elbl = f"E{em['entrance_id'][2:]} -> C{em['component_id']}"
        dr.text((lx + 8, max(2, ly - 14)), elbl, font=f_lbl, fill=(74, 222, 128, 255))
    composed = Image.alpha_composite(base, overlay).convert("RGB")
    composed.save(out_path)
    return str(out_path)


def analyze_room(
    rom: bytes,
    room_id: int,
    *,
    labels: dict[str, dict[str, str]],
    ledger_map: dict[int, dict[str, Any]],
    ow_reports_by_id: dict[int, dict[str, Any]],
    staged_rom: Path | None,
    z3ed_bin: Path | None,
    z3ed_cmds: set[str],
    out_dir: Path | None = None,
    injected_grid: list[list[int]] | None = None,
    injected_entrances: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Run partition flood-fill, entrance mapping, footprint check, and blast-radius audit."""
    room_lbl = labels.get("room", {}).get(f"0x{room_id:02x}") or labels.get("room", {}).get(f"0x{room_id:03x}") or f"Room ${room_id:03X}"
    blast = compute_room_blast_radius(rom, room_id, labels, ledger_map)

    room_desc: dict[str, Any] = {}
    grid = injected_grid
    if staged_rom and z3ed_bin:
        if "dungeon-describe-room" in z3ed_cmds:
            d, _ = C.run_z3ed_json(z3ed_bin, [
                "dungeon-describe-room", f"--rom={staged_rom}", f"--room=0x{room_id:03X}", "--format=json"
            ])
            if isinstance(d, dict):
                room_desc = d
        if grid is None and "dungeon-tile-types" in z3ed_cmds:
            tt, _ = C.run_z3ed_json(z3ed_bin, [
                "dungeon-tile-types", f"--rom={staged_rom}", f"--room=0x{room_id:03X}", "--format=json"
            ])
            if isinstance(tt, dict) and tt.get("layers"):
                rows = tt["layers"][0].get("rows", [])
                if len(rows) == 64:
                    grid = [[int(tok, 16) for tok in r.split()] for r in rows]

    comps = partition_room_grid(grid) if grid is not None else []
    raw_entrances: list[dict[str, Any]] = list(injected_entrances or [])
    if not raw_entrances and staged_rom and z3ed_bin and "dungeon-list-entrances" in z3ed_cmds:
        ed, _ = C.run_z3ed_json(z3ed_bin, [
            "dungeon-list-entrances", f"--rom={staged_rom}", f"--room=0x{room_id:03X}", "--format=json"
        ])
        if isinstance(ed, dict):
            raw_entrances = ed.get("Dungeon Entrances", {}).get("entrances", [])

    # Cross-reference OW entrances on any analyzed OW areas.
    ow_ent_lookup: dict[int, tuple[int, dict[str, Any]]] = {}
    for ow_id, ow_rep in ow_reports_by_id.items():
        for oe in ow_rep.get("entrances", []):
            eid = oe.get("entrance_id")
            if isinstance(eid, int) and eid not in ow_ent_lookup:
                ow_ent_lookup[eid] = (ow_id, oe)

    entrances_mapped = []
    for ent in raw_entrances:
        eid = C.parse_hex_int(ent["entrance"])
        ex = int(ent["x"]) & 0x1FF
        ey = int(ent["y"]) & 0x1FF
        cid = map_point_to_component(comps, ex, ey) if comps else None
        ow_footprint = None
        if eid in ow_ent_lookup:
            ow_id, oe = ow_ent_lookup[eid]
            ow_footprint = {
                "ow_area": f"0x{ow_id:02X}",
                "ow_px": [oe["x"], oe["y"]],
                **detect_exterior_building_footprint(ow_reports_by_id[ow_id], oe["x"], oe["y"]),
            }
        entrances_mapped.append({
            "entrance_id": f"0x{eid:02X}",
            "room_local_px": [ex, ey],
            "component_id": cid,
            "component_quadrant": comps[cid]["quadrant"] if cid is not None and cid < len(comps) else None,
            "ow_exterior_footprint": ow_footprint,
        })

    # Detect disconnected components & partitioned entrances.
    primary_cid = entrances_mapped[0]["component_id"] if entrances_mapped else (0 if comps else None)
    flags: list[str] = []
    seen_cids = {em["component_id"] for em in entrances_mapped if em["component_id"] is not None}
    for c in comps:
        cid = c["component_id"]
        c["entrances"] = [em["entrance_id"] for em in entrances_mapped if em["component_id"] == cid]
        if cid not in seen_cids:
            c["disconnected_flag"] = True
            flags.append(
                f"DISCONNECTED_SUBROOM: Room 0x{room_id:03X} C{cid} ({c['quadrant']}, "
                f"px {c['px_bbox']}, {c['tile_count']} tiles) has no entrance in this partition"
            )
        elif primary_cid is not None and cid != primary_cid:
            c["disconnected_flag"] = True
            e_list = ", ".join(c["entrances"])
            e_prim = ", ".join(comps[primary_cid].get("entrances", [])) if primary_cid < len(comps) else "?"
            flags.append(
                f"PARTITIONED_INTERIORS: Room 0x{room_id:03X} C{cid} ({c['quadrant']} [{e_list}], "
                f"px {c['px_bbox']}) is walkable-disconnected from primary C{primary_cid} ([{e_prim}])"
            )
        else:
            c["disconnected_flag"] = False

    if len(seen_cids) > 1 and any(em["ow_exterior_footprint"] for em in entrances_mapped):
        # Flag separate entrances inside one superdungeon room vs primary wing.
        pass

    partition_png = None
    if out_dir is not None and comps:
        out_dir.mkdir(parents=True, exist_ok=True)
        partition_png = _render_room_partition_png(
            room_id, room_lbl, comps, entrances_mapped, z3ed_bin, z3ed_cmds,
            staged_rom, out_dir / f"room_{room_id:03X}_partition.png",
        )

    clean_comps = [{k: v for k, v in c.items() if k != "_points"} for c in comps]
    return {
        "room_id": f"0x{room_id:03X}",
        "name": room_lbl,
        "doors": room_desc.get("doors", []),
        "sprites": room_desc.get("sprites", []),
        "chests": room_desc.get("chests", []),
        "blast_radius": blast,
        "subroom_components": clean_comps,
        "entrances_mapped": entrances_mapped,
        "partition_flags": flags,
        "partition_png": partition_png,
    }


# ---------------------------------------------------------------------------
# Packet Formatting & Orchestration
# ---------------------------------------------------------------------------
def build_preflight_packet(
    *,
    rom_path: Path,
    ow_ids: list[int],
    room_ids: list[int],
    afs_root: Path,
    proposals_dirs: list[Path],
    repo_root: Path,
    z3ed_bin: Path | None,
    offline: bool,
    max_rare: int,
    out_dir: Path | None,
) -> dict[str, Any]:
    rom = C.load_rom_bytes(rom_path)
    labels = C.load_resource_labels(repo_root)
    z3ed = None if offline else z3ed_bin
    z3ed_cmds = C.z3ed_supported_commands(z3ed)

    with C.staged_ro_rom(rom_path) as (staged_rom, rom_sha):
        active_staged = staged_rom if z3ed else None
        ledger_map = _ledger_summary_for_sheets(rom, active_staged, z3ed, repo_root)

        ow_reports: dict[int, dict[str, Any]] = {}
        for ow in ow_ids:
            ow_reports[ow] = analyze_overworld_area(
                rom, ow, repo_root=repo_root, staged_rom=active_staged, z3ed_bin=z3ed,
                z3ed_cmds=z3ed_cmds, ledger_map=ledger_map, max_rare=max_rare, out_dir=out_dir,
            )

        room_reports: dict[int, dict[str, Any]] = {}
        for rid in room_ids:
            room_reports[rid] = analyze_room(
                rom, rid, labels=labels, ledger_map=ledger_map, ow_reports_by_id=ow_reports,
                staged_rom=active_staged, z3ed_bin=z3ed, z3ed_cmds=z3ed_cmds, out_dir=out_dir,
            )

    all_ent_ids: list[int] = []
    area_msg_ids: dict[int, int] = {}
    for ow, rep in ow_reports.items():
        for e in rep.get("entrances", []):
            if isinstance(e.get("entrance_id"), int):
                all_ent_ids.append(e["entrance_id"])
        if rep.get("message_id"):
            area_msg_ids[ow] = int(rep["message_id"], 16)
    for rrep in room_reports.values():
        for em in rrep.get("entrances_mapped", []):
            all_ent_ids.append(C.parse_hex_int(em["entrance_id"]))
    all_ent_ids = sorted(set(all_ent_ids))

    patterns, human_terms = _area_search_tokens(ow_ids, room_ids, labels, all_ent_ids)
    decisions = collect_decisions(afs_root, patterns)
    proposals = collect_design_proposals(proposals_dirs, patterns, ow_ids)
    asm_hooks = collect_asm_overlays_and_hooks(repo_root, ow_ids, room_ids)
    messages = collect_message_refs(repo_root, patterns, area_msg_ids)

    # Strip large in-memory arrays before serializing JSON output.
    serializable_ow = []
    for rep in ow_reports.values():
        copy_rep = {k: v for k, v in rep.items() if k not in ("grid_tile16", "tile_types", "tile16_table")}
        serializable_ow.append(copy_rep)

    return {
        "rom": {"path": str(rom_path), "sha256": rom_sha},
        "z3ed": {"bin": str(z3ed) if z3ed else None, "wave1b_catalog": "overworld-tile-catalog" in z3ed_cmds},
        "targets": {
            "overworld_areas": [f"0x{x:02X}" for x in ow_ids],
            "rooms": [f"0x{x:03X}" for x in room_ids],
            "matched_terms": human_terms,
        },
        "intent": {
            "decisions": decisions,
            "design_proposals": proposals,
            "asm_overlays_and_hooks": asm_hooks,
            "dialogue": messages,
        },
        "overworld": serializable_ow,
        "rooms": list(room_reports.values()),
    }


def render_markdown_packet(pkt: dict[str, Any]) -> str:
    lines = [
        "# Scene-Intent Preflight Packet",
        "",
        f"- ROM: `{pkt['rom']['path']}` (`sha256:{pkt['rom']['sha256'][:12]}`)",
        f"- Targets: OW {', '.join(pkt['targets']['overworld_areas']) or '-'} | Rooms {', '.join(pkt['targets']['rooms']) or '-'}",
        f"- z3ed: `{pkt['z3ed']['bin'] or 'offline-python'}` (Wave 1B catalog: `{pkt['z3ed']['wave1b_catalog']}`)",
        "",
        "## 1. Area Intent & Governance",
        "",
        f"- SRAM overlay bytes: `{pkt['intent']['asm_overlays_and_hooks']['sram_overlay_flags']}`",
    ]
    for r in pkt["intent"]["asm_overlays_and_hooks"]["sram_flag_refs"][:6]:
        lines.append(f"  - `{r['sram']}` (`{r['area']}`) @ `{r['location']}`: `{r['line']}`")
    if pkt["intent"]["design_proposals"]:
        lines.append("- Design proposals:")
        for dp in pkt["intent"]["design_proposals"][:6]:
            lines.append(f"  - `{dp['path']}` — {dp['title']}")
    if pkt["intent"]["decisions"]:
        lines.append(f"- Matched decisions.org entries ({len(pkt['intent']['decisions'])}):")
        for d in pkt["intent"]["decisions"][:10]:
            lines.append(f"  - [{d['status']}] {d['heading']} (L{d['line']})")
    if pkt["intent"]["asm_overlays_and_hooks"]["asm_hooks"]:
        lines.append("- ASM area/room hooks:")
        for h in pkt["intent"]["asm_overlays_and_hooks"]["asm_hooks"][:8]:
            lines.append(f"  - `{h['location']}` ({h['target']}): `{h['line']}`")

    for ow in pkt["overworld"]:
        lines += [
            "",
            f"## 2. Overworld {ow['area_id']} ({ow['size']}, Parent {ow['parent_id']})",
            "",
            f"- Static sheets (`S0..S7`): `{' '.join(ow['static_graphics'])}` (animated `S7` top: `{ow['animated_sheet']}`)",
            f"- Unique Tile16 placed: `{ow['unique_tile16_used']}` | Rare `<=2x`: `{ow['rare_tile16_count']}`",
        ]
        if ow.get("cut_to_fit_sheet_png"):
            lines.append(f"- Cut-to-fit PNG: `{ow['cut_to_fit_sheet_png']}`")
        lines += ["", "| Slot | Sheet | Status | Shared OW | Unused on Area | Unused Globally |", "|---|---|---|---|---|---|"]
        for s in ow["slot_budget"]:
            lines.append(f"| S{s['slot']} | `{s['sheet']}` | {s['ledger_status']} | {s['ow_shared_areas']} | {s['area_unused_tile8_count']} | {s['global_map16_unused_tile8_count']} |")
        if ow["rare_tile16_eviction_candidates"]:
            lines += ["", "Top cut-to-fit `<=2x` Tile16 eviction candidates:"]
            for rc in ow["rare_tile16_eviction_candidates"][:8]:
                rep = rc["suggested_replacements"][0]["tile16"] if rc["suggested_replacements"] else "-"
                pin = " [PINNED]" if rc["asm_pinned"] else ""
                lines.append(f"- `{rc['tile16']}` ({rc['count']}x){pin}: frees `{len(rc['freed_tile8s'])}` Tile8 -> replace `{rep}`")

    for rm in pkt["rooms"]:
        br = rm["blast_radius"]
        lines += [
            "",
            f"## 3. Room {rm['room_id']} — {rm['name']}",
            "",
            f"- Header: `blockset={br['blockset']}`, `palette={br['palette']}`, `spriteset={br['spriteset']}`",
            f"- Blast radius: **{br['rooms_sharing_blockset_count']}** rooms share `{br['blockset']}` ({', '.join(br['dungeons_or_non_house_sharing_blockset'][:8]) or 'none'})",
            f"- Off-limits/DMA warnings: `{br['off_limits_sheet_warnings'] or 'none'}`",
        ]
        if rm["partition_png"]:
            lines.append(f"- Partition PPU overlay PNG: `{rm['partition_png']}`")
        if rm["partition_flags"]:
            lines.append("- **PARTITION GATE FLAGS:**")
            for f in rm["partition_flags"]:
                lines.append(f"  - **FLAG:** {f}")
        lines += ["", "| Comp | Quadrant | Tiles | Px BBox | Entrances | Flag |", "|---|---|---|---|---|---|"]
        for c in rm["subroom_components"]:
            ents = ", ".join(c.get("entrances", [])) or "-"
            lines.append(f"| C{c['component_id']} | {c['quadrant']} | {c['tile_count']} | `{c['px_bbox']}` | `{ents}` | {'FLAG' if c.get('disconnected_flag') else 'ok'} |")
        for em in rm["entrances_mapped"]:
            fp = em.get("ow_exterior_footprint")
            if fp and fp.get("building_found"):
                lines.append(f"- Entrance `{em['entrance_id']}` -> `C{em['component_id']}` | OW `{fp['ow_area']}` exterior footprint: `{fp['width_tiles']}x{fp['height_tiles']}` Tile16 (`{fp['width_px']}x{fp['height_px']}px`)")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--ow", action="append", default=[], help="Overworld area ID in hex (repeatable, e.g. 0x23)")
    ap.add_argument("--room", action="append", default=[], help="Dungeon/interior room ID in hex (repeatable, e.g. 0x0107)")
    ap.add_argument("--rom", type=Path, default=C.DEFAULT_PROJ_ROM, help="Source ROM path (never modified)")
    ap.add_argument("--z3ed", type=Path, help="Optional z3ed binary override")
    ap.add_argument("--offline", action="store_true", help="Disable z3ed subprocesses and run pure-Python mode")
    ap.add_argument("--afs-root", type=Path, default=C.DEFAULT_AFS_ROOT, help="Oracle AFS root")
    ap.add_argument("--proposals-dir", action="append", type=Path, default=[], help="Extra design-proposals roots")
    ap.add_argument("--max-rare", type=int, default=2, help="Max placements for cut-to-fit rare Tile16 detection")
    ap.add_argument("--out-dir", type=Path, help="Write JSON, Markdown, and visual PNG sheets to directory")
    ap.add_argument("--format", choices=("json", "markdown", "both"), default="markdown")
    args = ap.parse_args(argv)

    if not args.ow and not args.room:
        ap.error("Specify at least one --ow <hex> or --room <hex>")
    if not args.rom.is_file():
        ap.error(f"ROM not found: {args.rom}")

    ow_ids = [C.parse_hex_int(x) for x in args.ow]
    room_ids = [C.parse_hex_int(x) for x in args.room]
    prop_dirs = list(args.proposals_dir) + [
        C.REPO_ROOT / "Docs" / "Planning",
        C.REPO_ROOT.parent / "design-proposals",
        Path.home() / "src/hobby/oracle-of-secrets-scratch/design-proposals",
        args.afs_root / "scratchpad" / "handoffs",
    ]
    z3ed_bin = C.find_z3ed_bin(args.z3ed, C.REPO_ROOT)

    pkt = build_preflight_packet(
        rom_path=args.rom,
        ow_ids=ow_ids,
        room_ids=room_ids,
        afs_root=args.afs_root,
        proposals_dirs=prop_dirs,
        repo_root=C.REPO_ROOT,
        z3ed_bin=z3ed_bin,
        offline=args.offline,
        max_rare=args.max_rare,
        out_dir=args.out_dir,
    )
    md = render_markdown_packet(pkt)

    if args.out_dir is not None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        tag = "_".join([f"ow{x:02X}" for x in ow_ids] + [f"r{x:03X}" for x in room_ids])
        (args.out_dir / f"intent_packet_{tag}.json").write_text(json.dumps(pkt, indent=2), encoding="utf-8")
        (args.out_dir / f"intent_packet_{tag}.md").write_text(md, encoding="utf-8")

    if args.format in ("markdown", "both"):
        print(md)
    if args.format in ("json", "both"):
        print(json.dumps(pkt, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
