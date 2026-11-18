#!/usr/bin/env python3
"""Generate the graphics sheet ledger and check bank ownership.

One row per sheet ($00-$DE): type, address, free 16x16 cells, who loads it in
which slot (overworld areas, main blocksets, room blocksets, spritesets), owner,
and an off-limits status. The inventory comes from `z3ed gfx-sheet-inventory`
run on a COPY of the ROM; the source ROM is hashed before and after and never
written. The ledger goes to AFS (not Docs/).

A free cell is only free if nobody loads the sheet in that slot. The users
column counts loaders per slot so a "free" cell shared by 42 areas is visible.

Tail maps ($A0-$BF, special overworld) are not in the z3ed inventory, which
stops at area $9F. Their sheets come from the saved ROM's native directory
(PC $147000, `lyra_native_loaders.read_native_directory`): family `gfx` holds
8 static sheets per map, and the `special_sprite_gfx` phase families hold one
spriteset id per map. They are counted as `area` / `area_spriteset` users.

Bank check: BANK_CLAIMS lists which writer owns which ROM banks. The check
fails when two different owners claim overlapping banks, or when an `org` in
the repo (working tree or --ref) emits into a guarded bank from a source file
that is not listed for that claim. Add PR claims with --claims FILE.json.

Usage:
  gfx_ledger.py --rom Roms/oos168.sfc            # ledger + bank check
  gfx_ledger.py --rom R --sheet 0x33             # print one sheet's loaders
  gfx_ledger.py --check-banks-only [--ref REF] [--claims FILE.json]
Exit 1 when the bank check fails.
"""
from __future__ import annotations

import argparse
import fnmatch
import hashlib
import json
import re
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lyra_native_loaders as native  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_OUT = (Path.home() / ".context/projects/oracle-of-secrets/scratchpad/"
               "handoffs/gfx_ledger_2026-10-20")

# --- Off-limits rules (PLAN.md, handoffs/gfx_expansion_2026-10-20) ----------
RESERVED = {
    0x7B: "compression rule (2026-09-25)",
    0x7C: "compression rule (2026-09-25)",
    0xD4: "filler stub",
    0xD6: "filler stub",
    0x28: "filler stub (bg)",
}
RAW_RANGE = (0x71, 0x7E)   # raw sheets
BPP2_FROM = 0xDA           # 2bpp sheets $DA and up

# Unreferenced sheets after the static code search (PLAN.md section 2).
CLEARED = {  # nothing in code, tables or overrides names them
    0x5E: "cleared", 0x5F: "cleared", 0x60: "cleared", 0x96: "cleared",
}
NOT_CLEARED = {  # code loads them directly although no table does
    0x58: "animated OW tiles $00D8D5",
    0x5A: "animated OW tiles $00D8E7",
    0x5C: "Decompress_background_low $00D34C",
    0xC7: "item sheet $00D279",
    0xCB: "follower sheet $00D440/$00D3DA/$00D8D5",
    0xCE: "item sheet $00D505; experiment.asm:903",
    0xD1: "LoadItemGFX $00D250/$00D266; file select $00E4FE",
    0xD2: "LoadItemGFX $00D250/$00D266; file select $00E4FE",
    0xD3: "LoadItemGFX $00D250/$00D266; file select $00E4FE",
    0xD7: "LoadFollowerGraphics $00D426; sheet_overrides spr64",
    0xD9: "LoadFollowerGraphics $00D430",
}
# Empty stub IDs: usable once the area tables do not reference them.
EMPTY_STUBS = {0x63, 0x69, 0x6C, 0x6D, 0x6E, 0x6F, 0x70}

# Sheet claims by branch/PR. Extend with --owners FILE.json ({"0x63": "text"}).
OWNERS = {
    0x63: "PR #228 claude/volcano-57-import-442b78 (clone of $33 for the 9 volcano areas, slot 5)",
    0x6F: "D3 B/V20 sheet clone at $23C000 (source policy; application pending)",
    0x70: "D3 B/V20 trim clone at $23C800 (source policy; application pending)",
}

# --- Bank ownership (PLAN.md piece 0) ---------------------------------------
# lo/hi are inclusive ROM bank numbers. sources are repo-relative globs of the
# files allowed to `org` into those banks; empty = nobody writes by asm.
BANK_CLAIMS = [
    {"owner": "shared bank $23: Yaze graphics and Oracle sheet helpers/tables", "lo": 0x23, "hi": 0x23,
     "sources": ["Data/rom_patches/*", "Core/gfx_sheet_table.asm",
                 "Core/Generated/source_sprite_sheets/sheet_overrides.asm"],
     "note": "source policy: D3 [23C000,23D000); exclusive helpers/tables PC[11FC00,120000); no bank $24 grant"},
    {"owner": "custom collision / water fill table", "lo": 0x25, "hi": 0x25,
     "sources": ["Oracle_main.asm", "Dungeons/generated/*", "Dungeons/*"]},
    {"owner": "ZSCustomOverworld", "lo": 0x28, "hi": 0x28,
     "sources": ["Overworld/ZSCustomOverworld.asm"]},
    {"owner": "PR #225 claude/serene-solomon-4b9937 (Ganondorf)", "lo": 0x2A, "hi": 0x2A,
     "sources": ["Sprites/Bosses/ganondorf.asm"]},
    {"owner": "master world map + source sprite sheets", "lo": 0x40, "hi": 0x41,
     "sources": ["Overworld/world_map.asm",
                 "Core/Generated/source_sprite_sheets/sheet_overrides.asm"]},
    {"owner": "unclaimed", "lo": 0x42, "hi": 0x43, "sources": []},
    {"owner": "PR #226 codex/kalyxo-docks-native-20261020 (docks art)", "lo": 0x44, "hi": 0x44,
     "sources": ["Overworld/custom_gfx.asm", "Overworld/kalyxo_docks*.asm"]},
]
GUARDED = (0x23, 0x25, 0x28, 0x2A, 0x40, 0x41, 0x42, 0x43, 0x44)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def snes_addr(pc: int) -> str:
    return f"${pc >> 15:02X}:{0x8000 | (pc & 0x7FFF):04X}"


def run_inventory(rom: Path) -> dict:
    """Run z3ed on a temp copy; the source ROM must be unchanged afterwards."""
    before = sha256(rom)
    with tempfile.TemporaryDirectory(prefix="gfx_ledger_") as tmp:
        copy = Path(tmp) / "rom.sfc"
        shutil.copyfile(rom, copy)
        out = Path(tmp) / "inv.json"
        proc = subprocess.run(
            ["z3ed", "gfx-sheet-inventory", f"--rom={copy}", "--out", str(out),
             "--format", "json"], capture_output=True, text=True)
        if not out.exists():
            sys.exit(f"z3ed gfx-sheet-inventory failed:\n{proc.stdout}\n{proc.stderr}")
        inv = json.loads(out.read_text())
    if sha256(rom) != before:
        sys.exit(f"source ROM changed during the run: {rom}")
    inv["rom"] = str(rom)
    inv["rom_sha256"] = before
    add_tail_areas(inv, rom)
    return inv


# --- Tail maps ($A0-$BF) -----------------------------------------------------
TAIL_SPRITE_FAMILIES = ("special_sprite_gfx", "special_sprite_gfx_phase1",
                        "special_sprite_gfx_phase2")


def read_tail_areas(image: bytes) -> dict[int, dict]:
    """Tail map id -> {static_graphics: 8 sheets, sprite_graphics: 3 spriteset ids}.

    Read from the native special-overworld directory in the saved ROM, the same
    tables Lyra_ReadGfx0-7 and Lyra_ReadSpriteGfxByArea index at run time
    (Overworld/lyra_native_loaders.asm). Returns {} for a ROM with no directory
    (ordinary 160-map layout). Read-only.
    """
    installed = native.read_native_directory(image, experimental_page_tile16=True)
    if installed is None:
        return {}
    capacity, _bank, entries = installed
    ids = {f.name: f.id for f in native.current_table_layout(native.TABLE_BASE)}

    def row(name: str, area: int, stride: int) -> bytes:
        base = native.pc(entries[ids[name]][0]) + area * stride
        return image[base:base + stride]

    return {
        area: {"static_graphics": list(row("gfx", area, 8)),
               "sprite_graphics": [row(n, area, 1)[0] for n in TAIL_SPRITE_FAMILIES]}
        for area in range(native.FIRST_TAIL_MAP, capacity)
    }


def add_tail_areas(inv: dict, rom: Path) -> None:
    try:
        tail = read_tail_areas(rom.read_bytes())
    except ValueError as error:
        sys.exit(f"cannot read tail-map graphics from {rom}: {error}")
    inv["tail_areas"] = {str(a): v for a, v in tail.items()}


# --- Loaders per sheet and slot ----------------------------------------------
FIXED_ASM_LOADERS = {
    0x58: "fixed:$00D8D5 animated OW tiles",
    0x5A: "fixed:$00D8E7 animated OW tiles",
    0x5C: "fixed:$00D34C Decompress_background_low",
    0xC7: "fixed:$00D279 LoadItemGFX",
    0xCB: "fixed:$00D440/$00D3DA/$00D8D5 LoadFollowerGraphics",
    0xCE: "fixed:$00D505 item sheet",
    0xD1: "fixed:$00D250/$00E4FE LoadItemGFX/file-select",
    0xD2: "fixed:$00D250/$00E4FE LoadItemGFX/file-select",
    0xD3: "fixed:$00D250/$00E4FE LoadItemGFX/file-select",
    0xD7: "fixed:$00D426 LoadFollowerGraphics",
    0xD9: "fixed:$00D430 LoadFollowerGraphics",
}

LASTSPRSET_SLOT = {
    "LASTSPRSET0": 0, "$7EC2FC": 0,
    "LASTSPRSET1": 1, "$7EC2FD": 1,
    "LASTSPRSET2": 2, "$7EC2FE": 2,
    "LASTSPRSET3": 3, "$7EC2FF": 3,
}

DEFINE_RE = re.compile(r"^\s*(!\w+)\s*=\s*(\$[0-9A-Fa-f]{1,4}|[0-9]+)\b")
TOKEN_VAL = r"(\$[0-9A-Fa-f]{1,4}|!\w+|[0-9]+)"
LASTSPRSET_STA_RE = re.compile(
    r"\bSTA(?:\.[lw])?\s+(LASTSPRSET[0-3]|\$7EC2F[CDEF])\b",
    re.IGNORECASE,
)
LDA_IMM_RE = re.compile(rf"\bLDA(?:\.b)?\s+#{TOKEN_VAL}\b", re.IGNORECASE)
SPRSET_AA3_RE = re.compile(
    rf"\b(?:LDA|CMP)(?:\.b)?\s+#{TOKEN_VAL}\b[^;\n]*(?:\$0AA3|SprGfx)\b|\$0AA3\b[^;\n]*\bCMP(?:\.b)?\s+#{TOKEN_VAL}\b",
    re.IGNORECASE,
)
E772_CALL_RE = re.compile(r"\bJ[MS]L\s+\$00E772\b", re.IGNORECASE)
LDY_IMM_RE = re.compile(rf"\bLDY(?:\.b)?\s+#{TOKEN_VAL}\b", re.IGNORECASE)
KIT_ORG_RE = re.compile(r"^\s*org\s+\$00DD([0-9A-Fa-f]{2})\b", re.IGNORECASE)


def _parse_int(tok: str, defs: dict[str, int]) -> int | None:
    tok = tok.strip()
    if tok in defs:
        return defs[tok]
    if tok.startswith("$"):
        try:
            return int(tok[1:], 16)
        except ValueError:
            return None
    if tok.isdigit():
        return int(tok, 10)
    return None


def _iter_asm_files(repo_root: Path, ref: str | None = None):
    if ref:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "-z", "*.asm"],
            capture_output=True, text=True)
        if proc.returncode == 0:
            for rel in proc.stdout.split("\0"):
                if not rel:
                    continue
                show = subprocess.run(
                    ["git", "-C", str(repo_root), "show", f"{ref}:{rel}"],
                    capture_output=True, text=True, errors="replace")
                if show.returncode == 0:
                    yield rel, show.stdout
            return
    for p in sorted(repo_root.rglob("*.asm")):
        if not p.is_file():
            continue
        rel = p.relative_to(repo_root).as_posix()
        if any(part.startswith(".") for part in p.relative_to(repo_root).parts):
            continue
        if rel.startswith(("Roms/", "Backups/", "usdasm/")):
            continue
        yield rel, p.read_text(encoding="utf-8", errors="replace")


def scan_asm_sheet_loaders(
    inv: dict | None = None,
    repo_root: Path = REPO_ROOT,
    ref: str | None = None,
) -> dict[int, dict[int, list[str]]]:
    """Scan repo ASM and vanilla fixed loaders for code-driven sheet references."""
    out: dict[int, dict[int, list[str]]] = defaultdict(lambda: defaultdict(list))
    if (repo_root / "Core").is_dir() or (repo_root / "Sprites").is_dir() or (repo_root / "Dungeons").is_dir():
        for sid, desc in FIXED_ASM_LOADERS.items():
            out[sid][0].append(desc)

    spritesets = (inv or {}).get("spritesets", {})
    for rel, text in _iter_asm_files(repo_root, ref):
        lines = text.splitlines()
        defs: dict[str, int] = {}
        for line in lines:
            dm = DEFINE_RE.match(line.split(";", 1)[0])
            if dm:
                v = _parse_int(dm.group(2), defs)
                if v is not None:
                    defs[dm.group(1)] = v

        in_kit_org = False
        abyss_map_left = 0
        abyss_map_idx = 0
        for idx, raw in enumerate(lines, 1):
            code = raw.split(";", 1)[0].strip()
            if not code:
                continue

            # 1. LASTSPRSET0..3 immediate writes (same line or preceding LDA #) -> sheet (val + 0x73)
            for m in LASTSPRSET_STA_RE.finditer(code):
                slot = LASTSPRSET_SLOT[m.group(1).upper()]
                prefix = code[:m.start()]
                imm = list(LDA_IMM_RE.finditer(prefix))
                if not imm and idx > 1:
                    window = "\n".join(l.split(";", 1)[0] for l in lines[max(0, idx - 10):idx - 1])
                    imm = list(LDA_IMM_RE.finditer(window))
                if imm:
                    val = _parse_int(imm[-1].group(1), defs)
                    if val is not None and 0 <= val + 0x73 < 256:
                        out[val + 0x73][slot].append(f"{rel}:{idx} LASTSPRSET{slot}")

            # 2. $0AA3 spriteset writes/checks + HorseGame_CourseEnemyAA3 table
            for m in SPRSET_AA3_RE.finditer(code):
                tok = m.group(1) or m.group(2)
                ss = _parse_int(tok, defs)
                if ss is not None and str(ss) in spritesets:
                    for slot, val in enumerate(spritesets[str(ss)]):
                        if 0 <= val + 0x73 < 256:
                            out[val + 0x73][slot].append(f"{rel}:{idx} $0AA3=${ss:02X}")

            if code.startswith("HorseGame_CourseEnemyAA3:"):
                for j in range(idx, min(idx + 6, len(lines))):
                    sub = lines[j].split(";", 1)[0].strip()
                    if sub.lower().startswith("db "):
                        for tok in sub[3:].split(","):
                            ss = _parse_int(tok.strip(), defs)
                            if ss is not None and ss != 0xFF and str(ss) in spritesets:
                                for slot, val in enumerate(spritesets[str(ss)]):
                                    if 0 <= val + 0x73 < 256:
                                        out[val + 0x73][slot].append(f"{rel}:{j + 1} horse $0AA3=${ss:02X}")

            # 3. Direct Decompress_sprite_arbitrary ($00E772) calls paired with LDY #val
            if E772_CALL_RE.search(code):
                window = "\n".join(lines[max(0, idx - 6):idx])
                ldy_matches = list(LDY_IMM_RE.finditer(window))
                if ldy_matches:
                    val = _parse_int(ldy_matches[-1].group(1), defs)
                    if val is not None and 0 <= val + 0x73 < 256:
                        out[val + 0x73][0].append(f"{rel}:{idx} $00E772")

            # 4. Generated Kit blockset overrides (`org $00DDxx` -> `db ...`)
            if KIT_ORG_RE.match(code):
                in_kit_org = True
                continue
            if in_kit_org:
                if code.lower().startswith("pullpc"):
                    in_kit_org = False
                elif code.lower().startswith("db "):
                    for slot, tok in enumerate(code[3:].split(",")[:4]):
                        val = _parse_int(tok.strip(), defs)
                        if val is not None and 0 <= val < 255:
                            out[val][slot].append(f"{rel}:{idx} kit blockset")

            # 5. Abyss GBC room style remapped BG sheets (`AbyssGbc_SheetMap`)
            if code.startswith("AbyssGbc_SheetMap:"):
                abyss_map_left = 64
                abyss_map_idx = 0
                continue
            if abyss_map_left > 0 and code.lower().startswith("db "):
                for tok in code[3:].split(","):
                    if abyss_map_left <= 0:
                        break
                    val = _parse_int(tok.strip(), defs)
                    if val is not None and val > 0:
                        out[abyss_map_idx][0].append(f"{rel}:{idx} AbyssGbc_SheetMap")
                    abyss_map_idx += 1
                    abyss_map_left -= 1

    return out


def scan_json_sheet_overrides(repo_root: Path = REPO_ROOT) -> dict[int, list[str]]:
    """Scan Data/graphics/*.json specs for active source/override sheet IDs."""
    out: dict[int, list[str]] = defaultdict(list)
    gfx_dir = repo_root / "Data" / "graphics"
    if not gfx_dir.is_dir():
        return out
    for name in ("source_sprite_sheets.json", "d4_zora_sprite_sheets.json",
                 "dungeon_bg_sheets.json", "menu_icons.json"):
        path = gfx_dir / name
        if not path.is_file():
            continue
        data = json.loads(path.read_text(encoding="utf-8"))
        for entry in data.get("sheets", []):
            if not isinstance(entry, dict):
                continue
            sid = None
            if "global_sheet" in entry:
                sid = int(str(entry["global_sheet"]), 0)
            elif "sprite_sheet" in entry:
                sid = int(str(entry["sprite_sheet"]), 0) + 0x73
            if sid is not None and 0 <= sid < 256:
                src = entry.get("source") or f"0x{sid:02X}"
                flag = f" [{entry['flag']}]" if entry.get("flag") else ""
                out[sid].append(f"{name}:{src}{flag}")
    return out


def build_loaders(inv: dict, *, repo_root: Path = REPO_ROOT, ref: str | None = None,
                  include_code_refs: bool = True) -> dict[int, dict]:
    """sheet id -> {kind: {slot: [ids]}} built from raw tables plus ASM/JSON loaders."""
    L: dict[int, dict] = defaultdict(lambda: defaultdict(lambda: defaultdict(list)))
    for area, a in inv["overworld_areas"].items():
        for slot, sheet in enumerate(a["static_graphics"]):
            L[sheet]["area"][slot].append(int(area))
        for sidx, ss in enumerate(a["sprite_graphics"]):
            # sprite_graphics[sidx] is a spriteset id; the sheets come from it.
            for slot, val in enumerate(inv["spritesets"].get(str(ss), [])):
                L[val + 0x73]["area_spriteset"][slot].append(int(area))
    # Tail maps $A0-$BF: z3ed's overworld_areas stops at $9F (see read_tail_areas).
    for area, a in inv.get("tail_areas", {}).items():
        for slot, sheet in enumerate(a["static_graphics"]):
            L[sheet]["area"][slot].append(int(area))
        for ss in a["sprite_graphics"]:
            for slot, val in enumerate(inv["spritesets"].get(str(ss), [])):
                L[val + 0x73]["area_spriteset"][slot].append(int(area))
    for bs, sheets in inv["main_blocksets"].items():
        for slot, sheet in enumerate(sheets):
            L[sheet]["main_blockset"][slot].append(int(bs))
    for bs, sheets in inv["room_blocksets"].items():
        for slot, sheet in enumerate(sheets):
            L[sheet]["room_blockset"][slot].append(int(bs))
    for ss, vals in inv["spritesets"].items():
        for slot, val in enumerate(vals):
            L[val + 0x73]["spriteset"][slot].append(int(ss))
    if include_code_refs:
        for sid, slots in scan_asm_sheet_loaders(inv, repo_root=repo_root, ref=ref).items():
            for slot, refs in slots.items():
                L[sid]["asm_code"][slot].extend(refs)
        for sid, refs in scan_json_sheet_overrides(repo_root=repo_root).items():
            L[sid]["json_spec"][0].extend(refs)
    return L


def check_inventory_usage(inv: dict, L: dict) -> list[str]:
    """Cross-check: our areas-by-static-slot match z3ed's ow_areas_static.

    Tail maps are left out: z3ed does not list them."""
    problems = []
    for s in inv["sheets"]:
        sid = int(s["hex"], 16)
        ours = sorted({a for sl in L[sid]["area"].values() for a in sl
                       if a < native.FIRST_TAIL_MAP})
        theirs = sorted(s["usage"].get("ow_areas_static", []))
        if ours != theirs:
            problems.append(f"${sid:02X}: static-area users differ: table {len(ours)} vs z3ed {len(theirs)}")
    return problems


def slot_summary(slots: dict) -> str:
    return ", ".join(f"s{k}×{len(v)}" for k, v in sorted(slots.items())) or "-"


def classify(sid: int, s: dict, owner: str | None, user_count: int) -> tuple[str, str]:
    """(status, reason). Off-limits wins over owner wins over free-ness."""
    reasons = []
    if sid in RESERVED:
        reasons.append(RESERVED[sid])
    if RAW_RANGE[0] <= sid <= RAW_RANGE[1]:
        reasons.append("raw sheet $71-$7E")
    if sid >= BPP2_FROM and sid <= 0xDE:
        reasons.append("2bpp $DA-$DE")
    elif sid > 0xDE and not user_count:
        reasons.append("extended slot $DF-$FE")
    if sid in NOT_CLEARED:
        reasons.append("unreferenced but not cleared: " + NOT_CLEARED[sid])
    if reasons:
        return "OFF-LIMITS", "; ".join(reasons)
    if owner:
        return "CLAIMED", owner
    if sid in CLEARED or sid in EMPTY_STUBS:
        kind = "cleared unreferenced" if sid in CLEARED else "empty stub"
        if user_count:
            return "CHECK", f"{kind} but {user_count} loaders in this ROM and no owner"
        return "FREE-ID", kind
    if s.get("unreferenced") and not user_count:
        return "CHECK", "inventory marks unreferenced; not in PLAN.md lists"
    return "IN-USE", ""


def _read_extended_sheet_ptrs(rom_bytes: bytes) -> dict[int, int]:
    """Read Bank $23 expanded sheet table ($23:FD00..$23:FFFF) for IDs $DF..$FE."""
    ptrs: dict[int, int] = {}
    base_bk = 0x11FD00
    base_hi = 0x11FE00
    base_lo = 0x11FF00
    if len(rom_bytes) < 0x120000:
        return ptrs
    for sid in range(0xDF, 0xFF):
        snes = (rom_bytes[base_bk + sid] << 16) | (rom_bytes[base_hi + sid] << 8) | rom_bytes[base_lo + sid]
        if (snes & 0xFFFF) >= 0x8000 and snes != 0xFFFFFF:
            pc = ((snes >> 16) & 0x7F) * 0x8000 + (snes & 0x7FFF)
            ptrs[sid] = pc
    return ptrs


def build_rows(inv: dict, owners: dict[int, str], *, repo_root: Path = REPO_ROOT,
               ref: str | None = None, rom_path: Path | None = None) -> list[dict]:
    L = build_loaders(inv, repo_root=repo_root, ref=ref, include_code_refs=True)
    rows = []
    seen_sids: set[int] = set()
    for s in inv["sheets"]:
        sid = int(s["hex"], 16)
        seen_sids.add(sid)
        loaders = L.get(sid, {})
        n_users = sum(len(v) for kinds in loaders.values() for v in kinds.values())
        status, reason = classify(sid, s, owners.get(sid), n_users)
        pc = int(s["pc"], 16)
        rows.append({
            "sheet": sid, "hex": s["hex"], "type": s["kind"],
            "pc": s["pc"], "snes": snes_addr(pc), "bytes": s.get("stored_bytes"),
            "free16": len(s.get("free_16x16_blocks", [])),
            "free_cells": s.get("free_16x16_blocks", []),
            "loaders": {k: {str(sl): ids for sl, ids in v.items()} for k, v in loaders.items()},
            "status": status, "reason": reason, "owner": owners.get(sid, ""),
            "shares_pointer_with": s.get("shares_pointer_with", []),
        })
    ext_ptrs = _read_extended_sheet_ptrs(rom_path.read_bytes()) if rom_path and rom_path.is_file() else {}
    for sid in sorted(set(L) | set(ext_ptrs)):
        if sid in seen_sids:
            continue
        loaders = L.get(sid, {})
        n_users = sum(len(v) for kinds in loaders.values() for v in kinds.values())
        if not n_users and sid not in ext_ptrs:
            continue
        pc = ext_ptrs.get(sid, 0)
        status, reason = classify(sid, {}, owners.get(sid), n_users)
        rows.append({
            "sheet": sid, "hex": f"0x{sid:02X}", "type": "3bpp_ext",
            "pc": f"0x{pc:06X}" if pc else "", "snes": snes_addr(pc) if pc else "", "bytes": None,
            "free16": 0, "free_cells": [],
            "loaders": {k: {str(sl): ids for sl, ids in v.items()} for k, v in loaders.items()},
            "status": status, "reason": reason, "owner": owners.get(sid, ""),
            "shares_pointer_with": [],
        })
    return rows


# --- Bank ownership check ----------------------------------------------------
def overlap_conflicts(claims: list[dict]) -> list[str]:
    out = []
    for i, a in enumerate(claims):
        for b in claims[i + 1:]:
            if a["owner"] == b["owner"]:
                continue
            lo, hi = max(a["lo"], b["lo"]), min(a["hi"], b["hi"])
            if lo <= hi:
                out.append(f"banks ${lo:02X}-${hi:02X} claimed by both '{a['owner']}' and '{b['owner']}'")
    return out


ORG_RE = re.compile(r"^\s*(?:pushpc\s*)?org\s+\$([0-9A-Fa-f]{6})\b", re.IGNORECASE)


def scan_orgs(ref: str | None) -> list[tuple[str, int, int]]:
    """(file, line, bank) for every `org $BBxxxx` in a guarded bank."""
    pat = r"org[[:space:]]+\$(" + "|".join(f"{b:02X}" for b in GUARDED) + ")[0-9A-Fa-f]{4}"
    cmd = ["git", "-C", str(REPO_ROOT), "grep", "-n", "-I", "-i", "-E", pat]
    if ref:
        cmd.append(ref)
    cmd += ["--", "*.asm"]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    # git grep returns 1 for a successful search with no matches.
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"git grep failed (exit {proc.returncode}): {proc.stderr.strip()}")
    hits = []
    for line in proc.stdout.splitlines():
        if ref and line.startswith(ref + ":"):
            line = line[len(ref) + 1:]
        path, lineno, text = line.split(":", 2)
        m = ORG_RE.match(text)
        if m:
            hits.append((path, int(lineno), int(m.group(1)[:2], 16)))
    return hits


def source_conflicts(claims: list[dict], hits: list[tuple[str, int, int]]) -> list[str]:
    out = []
    for path, lineno, bank in hits:
        owners = [c for c in claims if c["lo"] <= bank <= c["hi"]]
        if not owners:
            out.append(f"{path}:{lineno} org into ${bank:02X} with no claim")
        elif not any(fnmatch.fnmatch(path, g) for c in owners for g in c["sources"]):
            names = " / ".join(c["owner"] for c in owners)
            out.append(f"{path}:{lineno} org into ${bank:02X} owned by '{names}'; "
                       f"{path} is not one of its sources")
    return out


def load_claims(extra: Path | None) -> list[dict]:
    claims = [dict(c) for c in BANK_CLAIMS]
    if extra:
        for c in json.loads(extra.read_text()):
            claims.append({"owner": c["owner"], "lo": int(str(c["lo"]), 0),
                           "hi": int(str(c["hi"]), 0), "sources": c.get("sources", [])})
    return claims


def check_banks(claims: list[dict], ref: str | None) -> list[str]:
    return overlap_conflicts(claims) + source_conflicts(claims, scan_orgs(ref))


# --- Markdown ----------------------------------------------------------------
def render_md(inv: dict, rows: list[dict], claims: list[dict], bank_problems: list[str],
              table_problems: list[str]) -> str:
    sha = inv["rom_sha256"][:8]
    counts = defaultdict(int)
    for r in rows:
        counts[r["status"]] += 1
    lines = [f"# Graphics sheet ledger", "",
             f"ROM: `{Path(inv['rom']).name}` sha256 `{sha}`. Generated by `Scripts/Build/gfx_ledger.py`. "
             "Read-only: z3ed ran on a copy.", "",
             "Status counts: " + ", ".join(f"{k} {v}" for k, v in sorted(counts.items())), "",
             "Loader notation: `sN×K` = K users load the sheet in slot N. "
             "A free cell is only free if the sheet has no loader in that slot "
             "(ow = overworld area static slots 0-15, tail maps $A0-$BF slots 0-7; mb = main blockset, rb = room blockset, "
             "ss = spriteset, as = area spriteset, ac = ASM/follower code, js = graphics JSON spec).", ""]
    lines += ["## Bank ownership", "",
              "| Banks | Owner | Source files |", "|---|---|---|"]
    for c in claims:
        rng = f"${c['lo']:02X}" if c["lo"] == c["hi"] else f"${c['lo']:02X}-${c['hi']:02X}"
        lines.append(f"| {rng} | {c['owner']} | {', '.join(c['sources']) or '-'} |")
    lines += ["", "Bank check: " + ("**PASS**" if not bank_problems else "**FAIL**")]
    lines += [f"- {p}" for p in bank_problems]
    if table_problems:
        lines += ["", "Table cross-check problems:"] + [f"- {p}" for p in table_problems]
    lines += ["", "## Needs attention", ""]
    attn = [r for r in rows if r["status"] in ("CHECK", "CLAIMED")]
    lines += [f"- `{r['hex']}` {r['status']}: {r['reason']}" for r in attn] or ["- none"]
    lines += ["", "## Ledger", "",
              "| Sheet | Type | Addr | Bytes | Free16 | ow | mb | rb | ss | ac | js | Status | Note |",
              "|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ld = r["loaders"]
        cell = lambda k: slot_summary({int(a): b for a, b in ld.get(k, {}).items()})
        note = r["reason"]
        if r["shares_pointer_with"]:
            note += f" shares ptr with {r['shares_pointer_with']}"
        lines.append(
            f"| {r['hex']} | {r['type']} | {r['snes']} | {r['bytes'] or ''} | {r['free16']} | "
            f"{cell('area')} | {cell('main_blockset')} | {cell('room_blockset')} | "
            f"{cell('spriteset')} | {cell('asm_code')} | {cell('json_spec')} | {r['status']} | {note} |")
    return "\n".join(lines) + "\n"


def print_sheet(rows: list[dict], sid: int) -> None:
    matches = [r for r in rows if r["sheet"] == sid]
    if not matches:
        print(f"0x{sid:02X}: not found in ledger rows")
        return
    r = matches[0]
    print(f"{r['hex']} {r['type']} {r['snes']} status={r['status']} {r['reason']}")
    for kind, slots in r["loaders"].items():
        for slot, ids in sorted(slots.items(), key=lambda kv: int(kv[0])):
            print(f"  {kind} slot {slot}: {len(ids)} users {ids}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--rom", type=Path, help="ROM to inventory (copied; never written)")
    ap.add_argument("--inventory", type=Path, help="reuse a z3ed gfx-sheet-inventory JSON instead of --rom")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT, help="output directory (AFS)")
    ap.add_argument("--owners", type=Path, help='JSON {"0x63": "owner text"} added to OWNERS')
    ap.add_argument("--claims", type=Path, help="JSON list of extra bank claims")
    ap.add_argument("--ref", help="git ref to scan for `org` writers (default: working tree)")
    ap.add_argument("--sheet", help="print loaders for one sheet (e.g. 0x33) and exit")
    ap.add_argument("--check-banks-only", action="store_true")
    args = ap.parse_args()

    claims = load_claims(args.claims)
    try:
        bank_problems = check_banks(claims, args.ref)
    except RuntimeError as error:
        print(f"bank check: ERROR: {error}", file=sys.stderr)
        return 2
    if args.check_banks_only:
        print("bank check:", "FAIL" if bank_problems else "PASS")
        for p in bank_problems:
            print("  " + p)
        return 1 if bank_problems else 0

    if args.inventory:
        inv = json.loads(args.inventory.read_text())
        if "tail_areas" not in inv:
            if args.rom:
                add_tail_areas(inv, args.rom)
            else:
                print("warning: inventory has no tail_areas and no --rom given; "
                      "tail maps $A0-$BF are not counted", file=sys.stderr)
    elif args.rom:
        inv = run_inventory(args.rom)
    else:
        ap.error("--rom or --inventory required")

    owners = dict(OWNERS)
    if args.owners:
        owners.update({int(k, 0): v for k, v in json.loads(args.owners.read_text()).items()})
    rows = build_rows(inv, owners, ref=args.ref, rom_path=args.rom)
    if args.sheet:
        print_sheet(rows, int(args.sheet, 0))
        return 0

    out = args.out.resolve()
    if (REPO_ROOT / "Docs") in out.parents or out == REPO_ROOT / "Docs":
        sys.exit("refusing to write the ledger under Docs/; use AFS")
    out.mkdir(parents=True, exist_ok=True)
    table_problems = check_inventory_usage(inv, build_loaders(inv))
    (out / "GFX_LEDGER.md").write_text(render_md(inv, rows, claims, bank_problems, table_problems))
    (out / "gfx_ledger.json").write_text(json.dumps(
        {"rom_sha256": inv["rom_sha256"], "rows": rows, "bank_claims": claims,
         "bank_problems": bank_problems}, indent=1))
    print(f"wrote {out}/GFX_LEDGER.md ({len(rows)} sheets); bank check: "
          f"{'FAIL' if bank_problems else 'PASS'}")
    for p in bank_problems + table_problems:
        print("  " + p)
    return 1 if bank_problems else 0


if __name__ == "__main__":
    sys.exit(main())
