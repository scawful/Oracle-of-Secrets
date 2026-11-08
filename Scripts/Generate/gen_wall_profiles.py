#!/usr/bin/env python3
"""Per-dungeon wall-profile tables for Dungeons/wall_profile_selector.asm.

Authoring is per dungeon: Dungeons/Data/wall_profiles/wall_profiles.json lists
profiles (id + word file) and groups (a dungeon, or a named room group such as
the Glacia estate interiors) that bind a room list to one profile. The output
is the same per-room ($A0) lookup table the selector reads.

Two steps:
  extract  read one profile's class words from a private candidate ROM into
           Dungeons/Data/wall_profiles/<profile>.words.json (needs the ROM).
  build    wall_profiles.json + *.words.json -> wall_profiles.asm (no ROM).
           --check fails if the committed asm is stale.

A class is one wall object whose drawer reads a fixed 8/12/16-word span from
RoomDrawObjectData ($00:9B52 + offset). The selector supports exactly CLASSES.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = REPO / "Dungeons/Data/wall_profiles"
CONFIG = DATA_DIR / "wall_profiles.json"
OUT_ASM = DATA_DIR / "wall_profiles.asm"

SUB1 = [0x061, 0x062, 0x001, 0x002, 0x063, 0x064, 0x003, 0x004,
        0x03A, 0x03B, 0x076, 0x077, 0x081, 0x082]
SUB2 = list(range(0x100, 0x110))
CLASSES = SUB1 + SUB2  # class index = position (0..29)
ROOM_COUNT = 0x128
OBJ_TABLE_PC = 0x1B52  # PC of $00:9B52 (RoomDrawObjectData) in a headerless LoROM


def span_words(obj: int) -> int:
    if obj in (0x03A, 0x03B, 0x076, 0x077, 0x081, 0x082):
        return 12
    return 16 if obj >= 0x100 else 8


def rom_word(d: bytes, pc: int) -> int:
    return struct.unpack_from("<H", d, pc)[0]


def obj_offset(d: bytes, obj: int) -> int:
    if obj < 0x100:
        return rom_word(d, 0x8000 + obj * 2)          # $01:8000 subtype-1 table
    return rom_word(d, 0x83F0 + (obj - 0x100) * 2)   # $01:83F0 subtype-2 table


def sha8(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:8]


# ----------------------------------------------------------------- extract
def cmd_extract(a: argparse.Namespace) -> int:
    src_path, base_path = Path(a.rom), Path(a.base)
    src, base = src_path.read_bytes(), base_path.read_bytes()
    ref = Path(a.reference).read_bytes() if a.reference else None
    for o in CLASSES:
        if obj_offset(src, o) != obj_offset(base, o):
            sys.exit(f"offset table differs from base for object {o:03X}; refusing")
    if obj_offset(base, 0x057) != obj_offset(base, 0x081):
        sys.exit("expected 057/081 to share an offset (057 stays excluded)")
    only = {int(x, 16) for x in a.classes.split(",")} if a.classes else None
    words: dict[str, list[str]] = {}
    for o in CLASSES:
        if only is not None and o not in only:
            continue
        pc = OBJ_TABLE_PC + obj_offset(base, o)
        got = [rom_word(src, pc + 2 * k) for k in range(span_words(o))]
        if ref is not None and got == [rom_word(ref, pc + 2 * k) for k in range(span_words(o))]:
            continue  # --reference: keep only classes the candidate changed
        words[f"{o:03X}"] = [f"${v:04X}" for v in got]
    doc = {
        "profile": a.name,
        "source_rom_sha256": hashlib.sha256(src).hexdigest(),
        "base_rom_sha256": hashlib.sha256(base).hexdigest(),
        "reference_rom_sha256": hashlib.sha256(ref).hexdigest() if ref is not None else None,
        "note": a.note or "",
        "classes": words,
    }
    out = DATA_DIR / f"{a.name}.words.json"
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{out.relative_to(REPO)}: {len(words)} classes, "
          f"{sum(len(v) for v in words.values())} words from {sha8(src_path)}")
    return 0


# ------------------------------------------------------------- extract-gfx
# Per-room graphics route for one profile. The profile's rooms get their own
# secondary blockset row (slot 3 = a new global sheet) and their own palette
# id. Changed glyph chars that the vanilla words fetch from shared main-group
# sheets are copied into free chars of the new slot-3 sheet, and the profile
# words are remapped to them. Shared sheets are never edited.
MAIN_GROUPS = 0x00E073     # 8 sheets per main blockset
TILE_TYPES = 0x0E9659      # UnderworldTileTypes (global classes, chars 0-$13F)
PAL_DATA, PAL_INDEX = 0x1BD734, 0x1BEC4B
DOOR_OFFSETS = (0x00CD9E, 0x00CF44)  # DoorGFXDataOffset_* + DoorAnimGFXDataOffset_*


def snes_pc(a: int) -> int:
    return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)


def cmd_extract_gfx(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sheet_codec
    from sheet_table import decomp, ptr
    src, base = Path(a.rom).read_bytes(), Path(a.base).read_bytes()
    words = json.loads((DATA_DIR / f"{a.name}.words.json").read_text())
    census = json.loads(Path(a.census).read_text())
    main_b = base[snes_pc(MAIN_GROUPS) + a.main * 8:][:8]
    if main_b != src[snes_pc(MAIN_GROUPS) + a.main * 8:][:8]:
        sys.exit("main group differs between candidate and base; refusing")
    sheet = lambda rom, g: decomp(rom, ptr(rom, g))[0]
    tile = lambda d, t: d[t * 24:(t + 1) * 24]
    chars = sorted({int(v.lstrip("$"), 16) & 0x3FF
                    for vals in words["classes"].values() for v in vals})
    glyphs = []
    for c in chars:
        if c >= 0x100:
            sys.exit(f"char {c:03X} is outside main slots 0-3; not supported")
        g = main_b[c >> 6]
        if tile(sheet(src, g), c & 0x3F) != tile(sheet(base, g), c & 0x3F):
            glyphs.append(c)
    # Free slot-3 chars: not drawn by the rooms' other objects (z3ed traces)
    # and not drawn by any door or door animation.
    w = lambda rom, p: struct.unpack_from("<H", rom, p)[0]
    door_chars = set()
    for p in range(snes_pc(DOOR_OFFSETS[0]), snes_pc(DOOR_OFFSETS[1]), 2):
        for k in range(12):
            door_chars.add(w(base, OBJ_TABLE_PC + w(base, p) + 2 * k) & 0x3FF)
    drawn = set(census["slot3_drawn"])
    free = [c for c in range(0xC0, 0x100) if c not in drawn and c not in door_chars]
    if len(free) < len(glyphs):
        sys.exit(f"{len(glyphs)} glyphs but only {len(free)} free slot-3 chars")
    slot3_src = main_b[3]
    grid = sheet_codec.sheet_to_grid(sheet(base, slot3_src))
    char_map = {}
    for c, n in zip(glyphs, free):
        g = sheet_codec.sheet_to_grid(sheet(src, main_b[c >> 6]))
        tx, ty = (c & 0xF) * 8, ((c & 0x3F) >> 4) * 8
        nx, ny = (n & 0xF) * 8, ((n & 0x3F) >> 4) * 8
        for y in range(8):
            grid[ny + y][nx:nx + 8] = g[ty + y][tx:tx + 8]
        char_map[f"{c:03X}"] = f"{n:03X}"
    raw = sheet_codec.grid_to_sheet(grid)
    txt = DATA_DIR / f"{a.name}.slot3.txt"
    txt.write_text(sheet_codec.grid_to_text(grid))
    types = bytearray(base[snes_pc(TILE_TYPES) + 0xC0:][:0x40])
    for c, n in zip(glyphs, free):
        types[n - 0xC0] = src[snes_pc(TILE_TYPES) + c]
    pal_src = w(base, snes_pc(PAL_INDEX) + a.palette_src)
    first, count = a.palette_words.split(":")
    first, count = int(first), int(count)
    pal = [w(src, snes_pc(PAL_DATA) + pal_src + 2 * (first + i)) for i in range(count)]
    doc = {
        "profile": a.name,
        "source_rom_sha256": hashlib.sha256(src).hexdigest(),
        "base_rom_sha256": hashlib.sha256(base).hexdigest(),
        "main_group": f"0x{a.main:02X}",
        "blockset_row": f"0x{a.blockset:02X}",
        "blockset_row_copy_of": f"0x{a.main:02X}",
        "slot3_global_sheet": f"0x{a.sheet:02X}",
        "slot3_copy_of": f"0x{slot3_src:02X}",
        "slot3_source": txt.name,
        "slot3_decoded_sha256": hashlib.sha256(raw).hexdigest(),
        "palette_id": f"0x{a.palette:02X}",
        "palette_copy_of": f"0x{a.palette_src:02X}",
        "palette_first_word": first,
        "palette_words": [f"${v:04X}" for v in pal],
        "char_map": char_map,
        "slot3_tile_types": base64_hex(types),
        "note": a.note or "",
    }
    out = DATA_DIR / f"{a.name}.gfx.json"
    out.write_text(json.dumps(doc, indent=1) + "\n")
    print(f"{out.relative_to(REPO)}: {len(glyphs)} glyphs -> slot-3 chars "
          f"{' '.join(char_map.values())}; {len(free) - len(glyphs)} free left")
    return 0


def base64_hex(b: bytes) -> list[str]:
    return [b[i:i + 16].hex().upper() for i in range(0, len(b), 16)]


# ------------------------------------------------------------------- build
def load_config() -> tuple[list[dict], list[dict], list[int], dict[int, str]]:
    cfg = json.loads(CONFIG.read_text())
    profiles = sorted(cfg["profiles"], key=lambda p: p["id"])
    ids = [p["id"] for p in profiles]
    if ids != list(range(1, len(ids) + 1)):
        raise SystemExit(f"profile ids must be 1..N with no gaps, got {ids}")
    by_name = {p["name"]: p for p in profiles}
    room_profile = [0] * ROOM_COUNT
    owner: dict[int, str] = {}
    for g in cfg["groups"]:
        if g["profile"] not in by_name:
            raise SystemExit(f"group {g['name']}: unknown profile {g['profile']}")
        pid = by_name[g["profile"]]["id"]
        for r in (int(x, 16) for x in g["rooms"]):
            if not 0 <= r < ROOM_COUNT:
                raise SystemExit(f"group {g['name']}: room {r:03X} out of range")
            if r in owner:
                raise SystemExit(f"room {r:03X} is in both {owner[r]} and {g['name']}")
            owner[r] = g["name"]
            room_profile[r] = pid
    return profiles, cfg["groups"], room_profile, owner


def render() -> str:
    profiles, groups, room_profile, _ = load_config()
    words_by_profile = []
    for p in profiles:
        doc = json.loads((DATA_DIR / p["words"]).read_text())
        cls = {int(k, 16): [int(v.lstrip("$"), 16) for v in vals]
               for k, vals in doc["classes"].items()}
        for o, vals in cls.items():
            if o not in CLASSES:
                raise SystemExit(f"{p['words']}: object {o:03X} is not a selector class")
            if len(vals) != span_words(o):
                raise SystemExit(f"{p['words']}: object {o:03X} needs {span_words(o)} words")
        gfx = None
        if p.get("gfx"):
            gfx = json.loads((DATA_DIR / p["gfx"]).read_text())
            cmap = {int(k, 16): int(v, 16) for k, v in gfx["char_map"].items()}
            cls = {o: [(w & ~0x3FF) | cmap.get(w & 0x3FF, w & 0x3FF) for w in vals]
                   for o, vals in cls.items()}
        words_by_profile.append((p, doc, cls, gfx))
    gfx_profiles = [(p, g) for p, _d, _c, g in words_by_profile if g]
    if len(gfx_profiles) > 1:
        raise SystemExit("only one profile may route gfx (one AA2 row / sheet / palette)")

    out: list[str] = []
    E = out.append
    E("; GENERATED by Scripts/Generate/gen_wall_profiles.py build - do not edit by hand.")
    E("; Input: Dungeons/Data/wall_profiles/wall_profiles.json + *.words.json")
    for p, doc, cls, _g in words_by_profile:
        E(f"; profile {p['id']} {p['name']}: {len(cls)} classes, "
          f"source ROM {doc['source_rom_sha256'][:8]}, base {doc['base_rom_sha256'][:8]}")
    for g in groups:
        E(f"; group {g['name']} -> {g['profile']}: {' '.join(g['rooms'])}")
    E(f"!WALLSEL_CLASS_COUNT = {len(CLASSES)}")
    E(f"!WALLSEL_PROFILE_COUNT = {len(profiles)}")
    E("")
    E("; class index per subtype-1 object ($FF = vanilla). Indexed by obj.")
    s1 = [0xFF] * 0xF8
    s2 = [0xFF] * 0x40
    for ci, o in enumerate(CLASSES):
        if o < 0x100:
            s1[o] = ci
        else:
            s2[o - 0x100] = ci
    E("WallSel_Sub1Class:")
    for i in range(0, len(s1), 16):
        E("  db " + ", ".join(f"${v:02X}" for v in s1[i:i + 16]))
    E("WallSel_Sub2Class:  ; indexed by obj-$100")
    for i in range(0, len(s2), 16):
        E("  db " + ", ".join(f"${v:02X}" for v in s2[i:i + 16]))
    E("; profile per room ID ($A0), 0 = none")
    E("WallSel_RoomProfile:")
    for i in range(0, ROOM_COUNT, 16):
        E("  db " + ", ".join(f"${v:02X}" for v in room_profile[i:i + 16]))
    E("WallSel_ProfileBase:  ; (profile-1)*CLASS_COUNT*2")
    E("  dw " + ", ".join(f"${i * len(CLASSES) * 2:04X}" for i in range(len(profiles))))
    data: list[int] = []
    src: list[int] = []
    ln: list[int] = []
    for _p, _doc, cls, _g in words_by_profile:
        for o in CLASSES:
            if o in cls:
                start = len(data) * 2
                data += cls[o]
                src.append(start + 2 * (len(cls[o]) - 1))
                ln.append(2 * (len(cls[o]) - 1))
            else:
                src.append(0xFFFF)
                ln.append(0xFFFF)
    if len(data) * 2 > 0x8000:
        raise SystemExit("WallSel data exceeds $8000 bytes")
    E("WallSel_SlotSrc:  ; byte offset of LAST word in WallSel_Data, $FFFF = vanilla")
    for i in range(0, len(src), 10):
        E("  dw " + ", ".join(f"${v:04X}" for v in src[i:i + 10]))
    E("WallSel_SlotLen:  ; span bytes - 2")
    for i in range(0, len(ln), 10):
        E("  dw " + ", ".join(f"${v:04X}" for v in ln[i:i + 10]))
    E(f"WallSel_Data:  ; {len(data)} words")
    for i in range(0, len(data), 8):
        E("  dw " + ", ".join(f"${v:04X}" for v in data[i:i + 8]))
    E("WallSel_Data_End:")
    E("")
    E("; per-profile graphics route ($FF = keep the room header's blockset/palette)")
    if gfx_profiles:
        gp, g = gfx_profiles[0]
        E(f"; gfx profile {gp['id']} {gp['name']}: {len(g['char_map'])} glyph chars -> "
          f"slot-3 sheet {g['slot3_global_sheet']} (decoded {g['slot3_decoded_sha256'][:8]})")
        E("!WALLSEL_GFX = 1")
        E(f"!WALLSEL_GFX_MAIN = ${int(g['main_group'], 16):02X}")
        E(f"!WALLSEL_GFX_BLOCKSET = ${int(g['blockset_row'], 16):02X}")
        E(f"!WALLSEL_GFX_SHEET = ${int(g['slot3_global_sheet'], 16):02X}")
        E(f"!WALLSEL_GFX_SLOT3_COPY = ${int(g['slot3_copy_of'], 16):02X}")
        E(f"!WALLSEL_GFX_PALETTE = ${int(g['palette_id'], 16):02X}")
        E(f"!WALLSEL_GFX_PALETTE_SRC = ${int(g['palette_copy_of'], 16):02X}")
        E(f"!WALLSEL_GFX_PAL_FIRST = {g['palette_first_word']}")
        E(f"!WALLSEL_GFX_SLOT3_BIN = \"Dungeons/Data/wall_profiles/{gp['name']}.slot3.lz2\"")
        E(f"!WALLSEL_GFX_PAL_COUNT = {len(g['palette_words'])}")
        E("!WALLSEL_GFX_PAL_WORDS = " + ", ".join(g["palette_words"]))
        E("; every room bound to the gfx profile must load the copied main blockset and palette")
        E("; (asar evaluates left to right without precedence: keep the parentheses)")
        for r in (r for r in range(ROOM_COUNT) if room_profile[r] == gp["id"]):
            hdr = f"($220000|read2($228000+${r * 2:03X}))"
            E(f"assert read1({hdr}+2) == !WALLSEL_GFX_MAIN && "
              f"read1($0ED460+(read1({hdr}+1)*4)) == !WALLSEL_GFX_PALETTE_SRC, "
              f"\"room ${r:03X} header no longer matches the gfx profile copy source\"")
    else:
        E("!WALLSEL_GFX = 0")
    bs = [0xFF] * len(profiles)
    pl = [0xFF] * len(profiles)
    for gp, g in gfx_profiles:
        bs[gp["id"] - 1] = int(g["blockset_row"], 16)
        pl[gp["id"] - 1] = int(g["palette_id"], 16)
    E("WallSel_ProfileBlockset:  ; indexed by profile-1")
    E("  db " + ", ".join(f"${v:02X}" for v in bs))
    E("WallSel_ProfilePalette:  ; BG palette id*2 for $0AB6, indexed by profile-1")
    E("  db " + ", ".join(f"${v:02X}" for v in pl))
    if gfx_profiles:
        g = gfx_profiles[0][1]
        E("WallSel_Slot3TileTypes:  ; 64 class bytes for chars $C0-$FF of the gfx blockset")
        for row in g["slot3_tile_types"]:
            E("  db " + ", ".join(f"${row[i:i + 2]}" for i in range(0, 32, 2)))
    return "\n".join(out) + "\n"


def slot3_streams() -> dict[Path, bytes]:
    """lz2 stream per gfx profile, rebuilt from the tracked text grid."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import lz2
    import sheet_codec
    out: dict[Path, bytes] = {}
    for p in json.loads(CONFIG.read_text())["profiles"]:
        if not p.get("gfx"):
            continue
        g = json.loads((DATA_DIR / p["gfx"]).read_text())
        raw = bytes(sheet_codec.grid_to_sheet(
            sheet_codec.text_to_grid((DATA_DIR / g["slot3_source"]).read_text())))
        if hashlib.sha256(raw).hexdigest() != g["slot3_decoded_sha256"]:
            raise SystemExit(f"{g['slot3_source']}: decoded sheet does not match slot3_decoded_sha256")
        comp = bytes(lz2.compress(raw))
        dec, used = lz2.decompress(comp)
        if dec != raw or used != len(comp):
            raise SystemExit(f"{g['slot3_source']}: lz2 round trip failed")
        out[DATA_DIR / f"{p['name']}.slot3.lz2"] = comp
    return out


def cmd_build(a: argparse.Namespace) -> int:
    text = render()
    bins = slot3_streams()
    if a.check:
        stale = [] if OUT_ASM.exists() and OUT_ASM.read_text() == text else [OUT_ASM]
        stale += [f for f, b in bins.items() if not f.exists() or f.read_bytes() != b]
        for f in stale:
            print(f"{f.relative_to(REPO)} is stale; run gen_wall_profiles.py build")
        if stale:
            return 1
        print(f"{OUT_ASM.relative_to(REPO)} + {len(bins)} slot-3 stream(s) up to date")
        return 0
    OUT_ASM.write_text(text)
    print(f"wrote {OUT_ASM.relative_to(REPO)}")
    for f, b in bins.items():
        f.write_bytes(b)
        print(f"wrote {f.relative_to(REPO)} ({len(b)} bytes)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("extract", help="read one profile's words from a candidate ROM")
    ex.add_argument("--name", required=True, help="profile name (words file stem)")
    ex.add_argument("--rom", required=True, help="candidate ROM (read only)")
    ex.add_argument("--base", required=True, help="unpatched base ROM for offsets (read only)")
    ex.add_argument("--reference", help="keep only classes whose words differ from this ROM")
    ex.add_argument("--classes", help="comma list of hex objects to keep (default all)")
    ex.add_argument("--note", help="provenance note stored in the words file")
    ex.set_defaults(fn=cmd_extract)
    eg = sub.add_parser("extract-gfx", help="read one profile's glyph chars, classes and palette")
    eg.add_argument("--name", required=True, help="profile name (words file stem)")
    eg.add_argument("--rom", required=True, help="candidate ROM (read only)")
    eg.add_argument("--base", required=True, help="unpatched base ROM (read only)")
    eg.add_argument("--census", required=True, help="estate_census.json (slot3_drawn chars)")
    eg.add_argument("--main", type=lambda s: int(s, 16), required=True, help="main blockset (hex)")
    eg.add_argument("--blockset", type=lambda s: int(s, 16), required=True, help="unused AA2 row (hex)")
    eg.add_argument("--sheet", type=lambda s: int(s, 16), required=True, help="new global sheet (hex)")
    eg.add_argument("--palette", type=lambda s: int(s, 16), required=True, help="unused palette id*2 (hex)")
    eg.add_argument("--palette-src", type=lambda s: int(s, 16), required=True, help="cloned palette id*2 (hex)")
    eg.add_argument("--palette-words", required=True, help="first:count words taken from the candidate")
    eg.add_argument("--note", help="provenance note")
    eg.set_defaults(fn=cmd_extract_gfx)
    bd = sub.add_parser("build", help="emit wall_profiles.asm")
    bd.add_argument("--check", action="store_true", help="fail if the asm is stale")
    bd.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
