#!/usr/bin/env python3
"""Per-dungeon wall-profile tables for Dungeons/wall_profile_selector.asm.

Authoring is per dungeon: Dungeons/Data/wall_profiles/wall_profiles.json lists
profiles (id + word file + optional kit) and groups (a dungeon, or a named room
group such as the Glacia estate interiors) that bind a room list to one
profile. The output is the same per-room ($A0) lookup table the selector reads.

A kit (Dungeons/Data/kits/<kit>.kit.json) registers the graphics that belong to
one accepted wall set: its private blockset row (slot sheets copied into new
global sheets), its private BG palette (a copy of the rooms' palette with the
kit's words spliced in), the char remap applied to the profile words, and the
tile types of the relocated chars. A kit without a private row or palette is a
registry entry only (words-only, or already in the base ROM).

Steps:
  extract      read one profile's class words from a candidate ROM into
               Dungeons/Data/wall_profiles/<profile>.words.json (needs the ROM).
  extract-kit  read one kit (class words, glyphs, tile types, palette) from a
               candidate ROM and fit it into a private row (needs the ROM).
  build        wall_profiles.json + *.words.json + *.kit.json ->
               wall_profiles.asm + kits.asm + kit sheet streams (no ROM).
               --check fails if any committed output is stale.

A class is one wall object whose drawer reads a fixed 8/12/16-word span from
RoomDrawObjectData ($00:9B52 + offset). The selector supports exactly CLASSES.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import struct
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DATA_DIR = REPO / "Dungeons/Data/wall_profiles"
CONFIG = DATA_DIR / "wall_profiles.json"
OUT_ASM = DATA_DIR / "wall_profiles.asm"
KITS_DIR = REPO / "Dungeons/Data/kits"
KITS_ASM = KITS_DIR / "kits.asm"

SUB1 = [0x061, 0x062, 0x001, 0x002, 0x063, 0x064, 0x003, 0x004,
        0x03A, 0x03B, 0x076, 0x077, 0x081, 0x082]
SUB2 = list(range(0x100, 0x110))
CLASSES = SUB1 + SUB2  # class index = position (0..29)
ROOM_COUNT = 0x128
OBJ_TABLE_PC = 0x1B52  # PC of $00:9B52 (RoomDrawObjectData) in a headerless LoROM

MAIN_GROUPS = 0x00E073     # 8 sheets per main blockset ($0AA1)
AA2_ROWS = 0x00DD97        # 4 sheets (slots 3-6) per secondary blockset row ($0AA2)
TILE_TYPES = 0x0E9659      # UnderworldTileTypes (chars 0-$13F, then $1C0-$1FF)
PAL_DATA, PAL_INDEX = 0x1BD734, 0x1BEC4B
PAL_SETS = 0x0ED460        # 4 bytes per palette set; byte 0 = BG palette id*2
PAL_WORDS = 90
ROOM_HEADERS = 0x228000    # dw per room; header = $220000|word
DOOR_OFFSETS = (0x00CD9E, 0x00CF44)  # DoorGFXDataOffset_* + DoorAnimGFXDataOffset_*
FANCY_EXIT_BLOCK = (0x00C1A8, 80)  # obj2656: south fancy dungeon exit, 10 words x 8 rows
OBJ_PTR_LOAD = 0x01874B  # LDA.l RoomData_ObjectDataPointers+0,X (operand = the table)

# Private ids. Rows $17-$1A and palette ids $1A/$22/$24/$26 are unused by
# ordinary room headers. Verify both the editable input (kits.asm assertions)
# and the compiled ROM (verify-rom), since source can replace palette sets.
# $1C belongs to Sky; $28 is outside the UW offset table, not another palette.
KIT_ROW0 = 0x17
PRIVATE_ROWS = {0x17: (0x09, 0x00, 0x24, 0x1B), 0x18: (0x08, 0x00, 0x22, 0x1B),
                0x19: (0x09, 0x00, 0x25, 0x1B), 0x1A: (0x09, 0x00, 0x26, 0x1B)}
PRIVATE_PALETTES = {0x1A: 0x0924, 0x22: 0x0BF4, 0x24: 0x0CA8, 0x26: 0x0D5C}
KIT_SHEETS = range(0xF3, 0xFF)          # spare global sheet rows (empty streams); $EA = Sky room sky, $EB-$F2 = Sky port
KIT_SHEET_ORG, KIT_SHEET_END = 0x458000, 0x45F000
VERDICTS = ("routed", "partial", "words_only", "in_base")


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


def snes_pc(a: int) -> int:
    return ((a >> 16) & 0x7F) * 0x8000 + (a & 0x7FFF)


def hx(v) -> int | None:
    """'0x0B' / '$0B' / '0B' / int -> int; None stays None."""
    if v is None or isinstance(v, int):
        return v
    s = str(v).strip().lstrip("$")
    return int(s[2:] if s.lower().startswith("0x") else s, 16)


def class_words(d: bytes, base: bytes, obj: int) -> list[int]:
    pc = OBJ_TABLE_PC + obj_offset(base, obj)
    return [rom_word(d, pc + 2 * k) for k in range(span_words(obj))]


def room_header(d: bytes, room: int) -> int:
    return snes_pc(0x220000 | rom_word(d, snes_pc(ROOM_HEADERS) + room * 2))


def room_blockset_palette(d: bytes, room: int) -> tuple[int, int]:
    h = room_header(d, room)
    return d[h + 2], d[snes_pc(PAL_SETS) + d[h + 1] * 4]


def effective_slots(d: bytes, blockset: int) -> list[int]:
    """Global sheet per slot 0-7 with main group = header blockset (editor view)."""
    m = list(d[snes_pc(MAIN_GROUPS) + blockset * 8:][:8])
    row = d[snes_pc(AA2_ROWS) + blockset * 4:][:4]
    for i, s in enumerate(row):
        if s:
            m[3 + i] = s
    return m


def tile_type(d: bytes, c: int) -> int | None:
    if c < 0x140:
        return d[snes_pc(TILE_TYPES) + c]
    if c >= 0x1C0:
        return d[snes_pc(TILE_TYPES) + c - 0x80]
    return None  # $140-$1BF: per-blockset custom attributes


def palette(d: bytes, pid: int) -> list[int]:
    off = rom_word(d, snes_pc(PAL_INDEX) + pid)
    return [rom_word(d, snes_pc(PAL_DATA) + off + 2 * i) for i in range(PAL_WORDS)]


def door_chars(base: bytes) -> set[int]:
    out = set()
    for p in range(snes_pc(DOOR_OFFSETS[0]), snes_pc(DOOR_OFFSETS[1]), 2):
        for k in range(12):
            out.add(rom_word(base, OBJ_TABLE_PC + rom_word(base, p) + 2 * k) & 0x3FF)
    # The south "fancy dungeon exit" (door types $0A/$0C, $01:A9DB/$01:AA01) draws a
    # fixed 10x8 block obj2656 through RoomDraw_SomeBigDecors, not the offset tables.
    first, count = FANCY_EXIT_BLOCK
    for k in range(count):
        out.add(rom_word(base, snes_pc(first) + 2 * k) & 0x3FF)
    return out


def room_object_table(data: bytes, rooms: list[int]) -> int:
    """Read the vanilla table or the qualified D4 fallback, never its NOP operand.

    Same two exact compiled dispatch shapes as Yaze room.cc's
    GetObjectPointerTablePc. D4 state rooms need state-specific inspection;
    a kit claiming one is refused instead of silently using its fallback.
    """
    op = snes_pc(OBJ_PTR_LOAD)
    if data[op] == 0xBF:
        table = int.from_bytes(data[op + 1:op + 4], "little")
    else:
        hook, dispatcher = snes_pc(0x018745), snes_pc(0x508000)
        if data[hook:hook + 12] != bytes.fromhex("22 00 80 50 EA EA EA EA EA EA EA EA"):
            raise ValueError("unsupported compiled room-object loader")
        layouts = (("AF A0 00 7E C9 25 00 F0 12 C9 37 00 F0 35", {0x25, 0x37}),
                   ("AF A0 00 7E C9 25 00 F0 17 C9 26 00 F0 3A C9 37 00 F0 59", {0x25, 0x26, 0x37}))
        for prefix, state_rooms in layouts:
            signature = bytes.fromhex(prefix)
            if data[dispatcher:dispatcher + len(signature)] != signature:
                continue
            if set(rooms) & state_rooms:
                raise ValueError("kit floor ownership requires D4 state-specific room inspection")
            p = dispatcher + len(signature)
            fallback = data[p:p + 13]
            if len(fallback) != 13 or fallback[0] != 0xBF or fallback[4:7] != bytes.fromhex("85 B8 BF") or fallback[10:] != bytes.fromhex("85 B7 6B"):
                raise ValueError("unsupported compiled D4 fallback")
            table = int.from_bytes(fallback[7:10], "little")
            if int.from_bytes(fallback[1:4], "little") != table + 1:
                raise ValueError("compiled D4 fallback pointer operands disagree")
            break
        else:
            raise ValueError("unsupported compiled D4 dispatch")
    if table & 0xFFFF < 0x8000 or table >> 16 & 0x7F >= 0x7E or snes_pc(table) + ROOM_COUNT * 3 > len(data):
        raise ValueError("room-object pointer table is outside ROM")
    return table


def floor_chars(base: bytes, rooms: list[int]) -> set[int]:
    """Chars of the two floor fills (RoomDraw_DrawFloors) of each room.

    Byte 0 of a room's object data holds floor 1 (high nibble, BG2) and floor 2
    (low nibble, BG1); each draws the 8 words at RoomDrawObjectData + nibble*16.
    z3ed object traces do not include these fills.
    """
    table = room_object_table(base, rooms)
    out = set()
    for r in rooms:
        p = snes_pc(table + 3 * r)
        b = base[snes_pc(int.from_bytes(base[p:p + 3], "little"))]
        for f in (b >> 4, b & 0xF):
            for k in range(8):
                out.add(rom_word(base, OBJ_TABLE_PC + f * 16 + 2 * k) & 0x3FF)
    return out


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
        got = class_words(src, base, o)
        if ref is not None and got == class_words(ref, base, o):
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


# ------------------------------------------------------------- extract-kit
# Fit one candidate's wall set into a private blockset row. Changed glyph
# chars of shared slots 0-2 move into free chars of a private copy of the
# slot-3 sheet (VRAM half rule: slots 0-3 share the high palette half), and
# the profile words are remapped to them. Shared sheets are never edited.
# A class is included only if all of its chars fit; the rest are recorded as
# blocked. Free = slot-3 chars no other object in the kit rooms draws (z3ed
# traces), no door or fancy exit draws, and the kit's own words do not keep
# in place. Room floor fills are not traced: --protect-floors keeps them too;
# without it a kit that replaces a floor char is reported as a warning.
def cmd_extract_kit(a: argparse.Namespace) -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import sheet_codec
    from sheet_table import decomp, ptr
    C, T = Path(a.rom).read_bytes(), Path(a.base).read_bytes()
    O = Path(a.origin).read_bytes() if a.origin else None
    rooms = [int(x, 16) for x in a.rooms.split(",")]
    for o in CLASSES:
        if obj_offset(C, o) != obj_offset(T, o):
            sys.exit(f"offset table differs from base for object {o:03X}; refusing")
    bps = {room_blockset_palette(T, r) for r in rooms}
    if len(bps) != 1:
        sys.exit(f"kit rooms use more than one blockset/palette in base: {sorted(bps)}")
    bs, pid = bps.pop()
    slots = effective_slots(T, bs)
    if effective_slots(C, bs) != slots:
        sys.exit("candidate and base load different sheets for the kit blockset; refusing")
    if T[snes_pc(AA2_ROWS) + bs * 4] != slots[3] or not slots[3]:
        # A $00 row byte shows the entrance's main-group sheet ($0AA1), which a
        # private row cannot copy reliably; build asserts the same rule.
        sys.exit("slot-3 row byte is $00 or disagrees with the effective sheet")

    cache: dict = {}

    def sheet(d: bytes, g: int) -> bytes:
        if (id(d), g) not in cache:
            cache[(id(d), g)] = decomp(d, ptr(d, g))[0]
        return cache[(id(d), g)]

    def glyph(d: bytes, c: int) -> bytes:
        return sheet(d, slots[c >> 6])[(c & 0x3F) * 24:][:24]

    def status(c_val, t_val, o_val) -> str:
        if O is None or t_val == o_val:
            return "edit"
        return "drift" if c_val == o_val else "conflict"

    # traced usage in the kit rooms
    usage: collections.Counter = collections.Counter()
    drawn_by: dict[int, set[int]] = collections.defaultdict(set)
    for r in rooms:
        doc = json.loads((Path(a.traces) / f"{r:03X}-traces.json").read_text())
        for case in doc["cases"]:
            o = int(case["object_id"], 16)
            usage[o] += 1
            for t in case["tiles"]:
                drawn_by[o].add(int(t["tile_id"], 16) & 0x3FF)

    blocked: list[dict] = []
    edit: dict[int, list[int]] = {}
    for o in CLASSES:
        cw, tw = class_words(C, T, o), class_words(T, T, o)
        if cw == tw:
            continue
        st = status(cw, tw, class_words(O, T, o) if O else None)
        if st != "edit":
            blocked.append({"item": f"class {o:03X}",
                            "reason": f"{st}: the base changed these words after the candidate"})
            continue
        edit[o] = cw

    doors = door_chars(T)
    floors = floor_chars(T, rooms)
    drawn = set(doors) | (floors if a.protect_floors else set())
    traced = set()
    for o, chars in drawn_by.items():
        if o not in edit:
            traced |= chars
    drawn |= traced
    for o in edit:  # base words of edited classes: keep them drawable (conservative)
        drawn |= {w & 0x3FF for w in class_words(T, T, o)}
    keep3 = {w & 0x3FF for ws in edit.values() for w in ws if 0xC0 <= (w & 0x3FF) < 0x100}

    def needed(o: int) -> tuple[list[int], list[int], str | None]:
        """(relocate, in_place, blocked reason) for one class."""
        rel, inplace = [], []
        for c in sorted({w & 0x3FF for w in edit[o]}):
            g_diff = glyph(C, c) != glyph(T, c)
            tc, tt = tile_type(C, c), tile_type(T, c)
            t_diff = tc != tt
            if not (g_diff or t_diff):
                continue
            if O is not None:
                if g_diff and status(glyph(C, c), glyph(T, c), glyph(O, c)) != "edit":
                    return [], [], f"char {c:03X} glyph changed in base after the candidate"
                if t_diff and status(tc, tt, tile_type(O, c)) != "edit":
                    return [], [], f"char {c:03X} tile type changed in base after the candidate"
            slot = c >> 6
            if slot <= 2:
                rel.append(c)
            elif slot == 3:
                (inplace if c not in drawn else rel).append(c)
            else:
                return [], [], f"char {c:03X} is in slot {slot}; slot 4-7 kit sheets are not implemented"
        return rel, inplace, None

    free = [c for c in range(0xC0, 0x100) if c not in drawn and c not in keep3]
    s3 = lambda cs: len({c for c in cs if 0xC0 <= c < 0x100})
    need_all = set()
    for o in edit:
        rel, _, why = needed(o)
        if not why:
            need_all |= set(rel)
    print(f"slot 3: {len(free)}/64 chars free; all {len(edit)} edited classes need {len(need_all)}. "
          f"Kept out: door+fancy exit {s3(doors)}, floor fill {s3(floors)}"
          f"{'' if a.protect_floors else ' (not protected)'}, other traced objects {s3(traced)}, "
          f"edited-class base words and kept chars {s3(drawn - set(doors) - floors - traced) + len(keep3 - drawn)}")
    order = sorted(edit, key=lambda o: (-usage[o], CLASSES.index(o)))
    char_map: dict[int, int] = {}
    in_place: set[int] = set()
    included: list[int] = []
    for o in order:
        rel, inplace, why = needed(o)
        if why:
            blocked.append({"item": f"class {o:03X}", "reason": why})
            continue
        new = [c for c in rel if c not in char_map]
        if len(new) > len(free):
            blocked.append({"item": f"class {o:03X}",
                            "reason": f"budget: needs {len(new)} more slot-3 chars, {len(free)} free"})
            continue
        for c in new:
            char_map[c] = free.pop(0)
        in_place |= set(inplace)
        included.append(o)

    grid = sheet_codec.sheet_to_grid(sheet(T, slots[3]))
    for c, n in list(char_map.items()) + [(c, c) for c in sorted(in_place)]:
        g = sheet_codec.sheet_to_grid(sheet(C, slots[c >> 6]))
        tx, ty = (c & 0xF) * 8, ((c & 0x3F) >> 4) * 8
        nx, ny = (n & 0xF) * 8, ((n & 0x3F) >> 4) * 8
        for y in range(8):
            grid[ny + y][nx:nx + 8] = g[ty + y][tx:tx + 8]
    raw = sheet_codec.grid_to_sheet(grid)
    types = {}
    for c, n in list(char_map.items()) + [(c, c) for c in sorted(in_place)]:
        if tile_type(C, c) != tile_type(T, n):
            types[n] = tile_type(C, c)

    # What the selector cannot carry: other objects whose words or glyphs differ.
    if a.candidate_traces:
        carried = set(included)
        words_diff: dict[int, set[str]] = collections.defaultdict(set)
        glyph_diff: dict[int, set[int]] = collections.defaultdict(set)
        for r in rooms:
            tb = json.loads((Path(a.traces) / f"{r:03X}-traces.json").read_text())["cases"]
            tc = json.loads((Path(a.candidate_traces) / f"{r:03X}-traces.json").read_text())["cases"]
            if [c["object_id"] for c in tb] != [c["object_id"] for c in tc]:
                sys.exit(f"room {r:03X}: candidate and base object lists differ; trace the same rooms")
            for cb, cc in zip(tb, tc):
                o = int(cc["object_id"], 16)
                if o in carried:
                    continue
                wb = [t["tile_id"] for t in cb["tiles"]]
                wc = [t["tile_id"] for t in cc["tiles"]]
                if wb != wc:
                    words_diff[o].add(f"{r:03X}")
                # The kit sheet keeps base glyphs at every char other objects draw.
                for t in cc["tiles"]:
                    c = int(t["tile_id"], 16) & 0x3FF
                    if c < 0x200 and glyph(C, c) != glyph(T, c):
                        glyph_diff[o].add(c)
        for o in sorted(words_diff):
            blocked.append({"item": f"object {o:03X}",
                            "reason": "not a selector class: the candidate draws other words in rooms "
                                      + " ".join(sorted(words_diff[o]))})
        for o in sorted(set(glyph_diff) - set(words_diff)):
            blocked.append({"item": f"object {o:03X} glyphs",
                            "reason": "candidate changed chars " + " ".join(f"{c:03X}" for c in sorted(glyph_diff[o]))
                                      + " that this object draws; the kit only replaces carried class chars"})

    pal_c, pal_t = palette(C, pid), palette(T, pid)
    pal_o = palette(O, pid) if O else pal_t
    idx = []
    for i in range(PAL_WORDS):
        if pal_c[i] == pal_t[i]:
            continue
        st = status(pal_c[i], pal_t[i], pal_o[i])
        if st == "edit":
            idx.append(i)
        else:
            blocked.append({"item": f"palette word {i}", "reason": f"{st}: base changed it after the candidate"})
    splices = []
    for i in idx:
        if splices and splices[-1]["first"] + len(splices[-1]["words"]) == i:
            splices[-1]["words"].append(f"${pal_c[i]:04X}")
        else:
            splices.append({"first": i, "words": [f"${pal_c[i]:04X}"]})

    txt = KITS_DIR / f"{a.kit}.slot3.txt"
    KITS_DIR.mkdir(exist_ok=True)
    txt.write_text(sheet_codec.grid_to_text(grid))
    words_path = DATA_DIR / f"{a.profile}.words.json"
    kit_note = f"kit {a.kit}: classes the candidate edited that fit the private row"
    carried = {f"{o:03X}": [f"${v:04X}" for v in edit[o]] for o in CLASSES if o in included}
    old = json.loads(words_path.read_text()) if words_path.exists() else None
    if old is not None and old.get("note") != kit_note:
        # A profile authored elsewhere (extract): keep its header and every class the
        # kit does not carry; only the carried classes take the candidate's words.
        changed = sorted(c for c, v in carried.items() if old["classes"].get(c) not in (None, v))
        merged = dict(old["classes"], **carried)
        old["classes"] = {f"{o:03X}": merged[f"{o:03X}"] for o in CLASSES if f"{o:03X}" in merged}
        words_doc = old
        print(f"{words_path.relative_to(REPO)}: kept {len(merged) - len(carried)} uncarried classes; "
              f"{len(changed)} carried classes changed words" + (": " + " ".join(changed) if changed else ""))
    else:
        words_doc = {
            "profile": a.profile,
            "source_rom_sha256": hashlib.sha256(C).hexdigest(),
            "base_rom_sha256": hashlib.sha256(T).hexdigest(),
            "reference_rom_sha256": None,
            "note": kit_note,
            "classes": carried,
        }
    words_path.write_text(json.dumps(words_doc, indent=1) + "\n")
    kit = {
        "kit": a.kit,
        "inventory_id": a.inventory_id,
        "verdict": "partial" if blocked else "routed",
        "profile": a.profile,
        "source_rom_sha256": hashlib.sha256(C).hexdigest(),
        "origin_rom_sha256": hashlib.sha256(O).hexdigest() if O else None,
        "base_rom_sha256": hashlib.sha256(T).hexdigest(),
        "rooms": [f"{r:03X}" for r in rooms],
        "base_blockset": f"0x{bs:02X}",
        "base_palette": f"0x{pid:02X}",
        "private_row": f"0x{a.row:02X}",
        "sheets": [{"slot": 3, "sheet": f"0x{a.sheet:02X}", "copy_of": f"0x{slots[3]:02X}",
                    "source": txt.name, "decoded_sha256": hashlib.sha256(raw).hexdigest()}],
        "char_map": {f"{c:03X}": f"{n:03X}" for c, n in sorted(char_map.items())},
        "in_place": [f"{c:03X}" for c in sorted(in_place)],
        "tile_types": {f"{n:03X}": f"0x{t:02X}" for n, t in sorted(types.items())},
        "palette": ({"id": f"0x{a.palette:02X}", "copy_of": f"0x{pid:02X}",
                     "copy_offset": f"0x{rom_word(T, snes_pc(PAL_INDEX) + pid):04X}",
                     "splices": splices} if splices else None),
        "classes": [f"{o:03X}" for o in CLASSES if o in included],
        "blocked": blocked,
        "free_slot3_left": len(free),
        "note": a.note or "",
    }
    out = KITS_DIR / f"{a.kit}.kit.json"
    out.write_text(json.dumps(kit, indent=1) + "\n")
    print(f"{out.relative_to(REPO)}: {len(included)}/{len(edit)} edited classes, "
          f"{len(char_map)} relocated + {len(in_place)} in place, {len(free)} free left, "
          f"{len(types)} tile types, {sum(len(s['words']) for s in splices)} palette words, "
          f"{len(blocked)} blocked")
    for b in blocked:
        print(f"  blocked {b['item']}: {b['reason']}")
    hit = sorted((set(char_map.values()) | in_place) & floors)
    if hit:
        print(f"  warning: kit art replaces floor-fill chars {' '.join(f'{c:03X}' for c in hit)}; "
              f"rooms whose floor uses them draw kit art (--protect-floors keeps them)")
    return 0


# ------------------------------------------------------------------- build
def load_kits() -> list[dict]:
    """Every registered kit, validated; routed kits sorted by private row."""
    kits = []
    sheets_seen: dict[int, str] = {}
    pal_seen: dict[int, str] = {}
    for f in sorted(KITS_DIR.glob("*.kit.json")):
        k = json.loads(f.read_text())
        name = f.name[: -len(".kit.json")]
        if k.get("kit") != name:
            raise SystemExit(f"{f.name}: kit name must match the file name")
        if k.get("verdict") not in VERDICTS:
            raise SystemExit(f"{f.name}: verdict must be one of {VERDICTS}")
        row = hx(k.get("private_row"))
        pal = k.get("palette")
        sheets = k.get("sheets") or []
        cmap = {int(c, 16): int(n, 16) for c, n in (k.get("char_map") or {}).items()}
        types = {int(c, 16): hx(t) for c, t in (k.get("tile_types") or {}).items()}
        if (sheets or cmap or types) and row is None:
            raise SystemExit(f"{f.name}: sheets, char_map and tile_types need a private_row")
        if row is not None and row not in PRIVATE_ROWS:
            raise SystemExit(f"{f.name}: private_row must be one of "
                             + ", ".join(f"${r:02X}" for r in PRIVATE_ROWS))
        if (row is not None or pal) and not k.get("profile"):
            raise SystemExit(f"{f.name}: a kit with a private row or palette needs a profile")
        if (row is not None or pal) and k["verdict"] not in ("routed", "partial"):
            raise SystemExit(f"{f.name}: only routed/partial kits may claim a row or palette")
        slots_seen = set()
        for s in sheets:
            sid, slot = hx(s["sheet"]), int(s["slot"])
            if sid not in KIT_SHEETS:
                raise SystemExit(f"{f.name}: sheet ${sid:02X} is not a spare row $F3-$FE")
            if sid in sheets_seen:
                raise SystemExit(f"{f.name}: sheet ${sid:02X} is also used by {sheets_seen[sid]}")
            if not 3 <= slot <= 6 or slot in slots_seen:
                raise SystemExit(f"{f.name}: sheet slot must be a unique 3-6")
            sheets_seen[sid] = name
            slots_seen.add(slot)
            high = [hx(c) for c in s.get("high_palette_chars", [])]
            if high and (slot != 6 or any(c < 0x180 or c >= 0x1B0 for c in high)):
                raise SystemExit(f"{f.name}: high_palette_chars only supports static slot-6 chars $180-$1AF")
            if len(set(high)) != len(high) or any(c not in cmap.values() or c not in types for c in high):
                raise SystemExit(f"{f.name}: high_palette_chars needs unique mapped chars with tile types")
        for c, n in cmap.items():
            if c >= 0x200 or (n >> 6) not in slots_seen:
                raise SystemExit(f"{f.name}: char {c:03X} -> {n:03X} needs a kit sheet in slot {n >> 6}")
        if len(set(cmap.values())) != len(cmap):
            raise SystemExit(f"{f.name}: two chars map to one target")
        for n, t in types.items():
            if not 0 <= n < 0x200 or not 0 <= t <= 0xFF:
                raise SystemExit(f"{f.name}: bad tile type {n:03X}={t}")
        if pal:
            pid = hx(pal["id"])
            if pid not in PRIVATE_PALETTES or pid in pal_seen:
                raise SystemExit(f"{f.name}: palette ${pid:02X} is not a free private palette id")
            pal_seen[pid] = name
            used = set()
            for sp in pal["splices"]:
                rng = set(range(sp["first"], sp["first"] + len(sp["words"])))
                if used & rng or max(rng) >= PAL_WORDS:
                    raise SystemExit(f"{f.name}: palette splices overlap or exceed {PAL_WORDS} words")
                used |= rng
        k["_row"], k["_cmap"], k["_types"] = row, cmap, types
        kits.append(k)
    routed = sorted((k for k in kits if k["_row"] is not None), key=lambda k: k["_row"])
    rows = [k["_row"] for k in routed]
    if rows != list(range(KIT_ROW0, KIT_ROW0 + len(rows))):
        raise SystemExit(f"kit rows must be contiguous from ${KIT_ROW0:02X}, got {rows}")
    for i, k in enumerate(routed):
        k["_index"] = i
    return kits


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


def bind_kits(profiles: list[dict], kits: list[dict]) -> dict[str, dict]:
    """profile name -> kit; every kit with a route must be bound to its profile."""
    by_kit = {k["kit"]: k for k in kits}
    bound: dict[str, dict] = {}
    for p in profiles:
        if not p.get("kit"):
            continue
        k = by_kit.get(p["kit"])
        if k is None:
            raise SystemExit(f"profile {p['name']}: unknown kit {p['kit']}")
        if k.get("profile") != p["name"]:
            raise SystemExit(f"kit {k['kit']} names profile {k.get('profile')}, not {p['name']}")
        if any(b is k for b in bound.values()):
            raise SystemExit(f"kit {k['kit']} is bound to two profiles")
        bound[p["name"]] = k
    for k in kits:
        if (k["_row"] is not None or k.get("palette")) and k.get("profile") not in bound:
            raise SystemExit(f"kit {k['kit']} has a route but no profile binds it")
    return bound


def render() -> str:
    profiles, groups, room_profile, _ = load_config()
    kits = load_kits()
    bound = bind_kits(profiles, kits)
    routed = sorted((k for k in kits if k["_row"] is not None), key=lambda k: k["_row"])
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
        kit = bound.get(p["name"])
        if kit and kit["_cmap"]:
            cmap = kit["_cmap"]
            cls = {o: [(w & ~0x3FF) | cmap.get(w & 0x3FF, w & 0x3FF) for w in vals]
                   for o, vals in cls.items()}
        words_by_profile.append((p, doc, cls, kit))

    out: list[str] = []
    E = out.append
    E("; GENERATED by Scripts/Generate/gen_wall_profiles.py build - do not edit by hand.")
    E("; Input: Dungeons/Data/wall_profiles/wall_profiles.json + *.words.json,")
    E(";        Dungeons/Data/kits/*.kit.json")
    for p, doc, cls, kit in words_by_profile:
        E(f"; profile {p['id']} {p['name']}: {len(cls)} classes, "
          f"source ROM {doc['source_rom_sha256'][:8]}, base {doc['base_rom_sha256'][:8]}"
          + (f", kit {kit['kit']}" if kit else ""))
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
    for _p, _doc, cls, _k in words_by_profile:
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
    E("; ---- kit graphics routes (Dungeons/Data/kits/kits.asm writes the rows,")
    E("; palettes and sheets; Dungeons/wall_profile_selector.asm swaps them in)")
    for k in kits:
        route = []
        if k["_row"] is not None:
            route.append(f"row ${k['_row']:02X} (kit {k['_index']})")
        if k.get("palette"):
            route.append(f"palette ${hx(k['palette']['id']):02X}")
        E(f"; kit {k['kit']} [{k['verdict']}] profile {k.get('profile') or '-'}: "
          + (", ".join(route) if route else "no route"))
    has_route = any(k["_row"] is not None or k.get("palette") for k in kits)
    E(f"!WALLSEL_GFX = {1 if has_route else 0}")
    E(f"!WALLSEL_KIT_ROW0 = ${KIT_ROW0:02X}")
    E(f"!WALLSEL_KIT_COUNT = {len(routed)}")
    bs = [0xFF] * len(profiles)
    pl = [0xFF] * len(profiles)
    for p, _doc, _cls, k in words_by_profile:
        if k and k["_row"] is not None:
            bs[p["id"] - 1] = k["_row"]
        if k and k.get("palette"):
            pl[p["id"] - 1] = hx(k["palette"]["id"])
    E("WallSel_ProfileBlockset:  ; private row per profile-1, $FF = keep the header blockset")
    E("  db " + ", ".join(f"${v:02X}" for v in bs))
    E("WallSel_ProfilePalette:  ; BG palette id*2 for $0AB6 per profile-1, $FF = keep")
    E("  db " + ", ".join(f"${v:02X}" for v in pl))
    if not routed:
        return "\n".join(out) + "\n"
    E("WallSel_KitBase:  ; base blockset per kit (row-!WALLSEL_KIT_ROW0)")
    E("  db " + ", ".join(f"${hx(k['base_blockset']):02X}" for k in routed))
    E("WallSel_KitHighPalette:  ; 64 bytes per kit; slot-6 tile index, 0=low/1=high")
    for k in routed:
        high = {hx(c) & 0x3F for s in k.get("sheets", [])
                for c in s.get("high_palette_chars", [])}
        for start in range(0, 64, 16):
            E("  db " + ", ".join("$01" if i in high else "$00"
                                  for i in range(start, start + 16)))
    E("WallSel_RenderMetadata:  ; compiled read-only view of the SAME selector tables")
    E('  db "WSR1"')
    E(f"  dw ${ROOM_COUNT:04X}")
    E(f"  db {len(CLASSES)}, {len(profiles)}, ${KIT_ROW0:02X}, {len(routed)}")
    for label in ("RoomProfile", "Sub1Class", "Sub2Class", "ProfileBase", "SlotSrc",
                  "SlotLen", "Data", "ProfileBlockset", "ProfilePalette", "KitHighPalette"):
        E(f"  dl WallSel_{label}")
    E("")
    E("; Tile types. Called from WallSel_LoadTileAttr with M=8 X=8 (X/Y untouched).")
    E("; Chars $C0-$FF are restored from the ROM table on every room by the")
    E("; selector; $140-$1BF reload per room from the custom attributes. Any other")
    E("; char a kit patches is restored here from the ROM table on every room.")
    extra = sorted({n for k in routed for n in k["_types"]
                    if not (0xC0 <= n < 0x100 or 0x140 <= n < 0x1C0)})
    E("WallSel_RestoreExtra:")
    for n in extra:
        rom_i = n if n < 0x140 else n - 0x80
        E(f"  LDA.l read3($0E97F6)-$C0+${rom_i:03X} : STA.l $7EFE00+${n:03X}")
    E("  RTS")
    for k in routed:
        E(f"WallSel_KitPatch{k['_index']}:  ; {k['kit']}: {len(k['_types'])} chars")
        by_type: dict[int, list[int]] = collections.defaultdict(list)
        for n, t in sorted(k["_types"].items()):
            by_type[t].append(n)
        for t in sorted(by_type):
            E(f"  LDA.b #${t:02X}")
            for n in by_type[t]:
                E(f"  STA.l $7EFE00+${n:03X}")
        E("  RTS")
    E("WallSel_KitPatchPtr:")
    E("  dw " + ", ".join(f"WallSel_KitPatch{k['_index']}" for k in routed))
    return "\n".join(out) + "\n"


def render_kits() -> str:
    """kits.asm: private rows, palettes, sheet streams and their guards."""
    profiles, groups, room_profile, _ = load_config()
    kits = load_kits()
    bound = bind_kits(profiles, kits)
    pid_of = {p["name"]: p["id"] for p in profiles}
    out: list[str] = []
    E = out.append
    E("; GENERATED by Scripts/Generate/gen_wall_profiles.py build - do not edit by hand.")
    E("; Input: Dungeons/Data/kits/*.kit.json. Global scope; included from")
    E("; Dungeons/wall_profile_gfx.asm after Core/gfx_sheet_table.asm.")
    E("; asar evaluates left to right without precedence: keep the parentheses.")
    E("")
    for k in kits:
        E(f"; {k['kit']} ({k.get('inventory_id') or '-'}) [{k['verdict']}]: {k.get('note', '')}")
        for b in k.get("blocked") or []:
            E(f";   blocked {b['item']}: {b['reason']}")
    E("")
    E("; ---- private ids: vanilla spare rows, palette offsets, no room uses them ----")
    for r, vb in PRIVATE_ROWS.items():
        a = AA2_ROWS + r * 4
        E(f"assert " + " && ".join(f"read1(${a + i:06X}) == ${v:02X}" for i, v in enumerate(vb))
          + f", \"blockset row ${r:02X} is not the vanilla spare row\"")
    for pid, off in PRIVATE_PALETTES.items():
        E(f"assert read2(${PAL_INDEX + pid:06X}) == ${off:04X}, \"palette ${pid:02X} offset moved\"")
    hdr = "($220000|read2($228000+(!wsk_r*2)))"
    E("!wsk_r = 0")
    E("while !wsk_r < $128")
    E(f"  assert read1({hdr}+2) < ${KIT_ROW0:02X} || read1({hdr}+2) > ${max(PRIVATE_ROWS):02X}, "
      f"\"a room header uses a private kit row\"")
    pal_expr = f"read1($0ED460+(read1({hdr}+1)*4))"
    E(f"  assert " + " && ".join(f"{pal_expr} != ${pid:02X}" for pid in PRIVATE_PALETTES)
      + ", \"a room palette set uses a private kit palette\"")
    E("  !wsk_r #= !wsk_r+1")
    E("endwhile")
    E("")
    routed = [k for k in kits if k["_row"] is not None or k.get("palette")]
    for k in routed:
        base_bs = hx(k.get("base_blockset"))
        base_pal = hx(k["palette"]["copy_of"]) if k.get("palette") else None
        pid = pid_of[k["profile"]]
        E(f"; ---- kit {k['kit']} -> profile {pid} {k['profile']} ----")
        for r in (r for r in range(ROOM_COUNT) if room_profile[r] == pid):
            h = f"($220000|read2($228000+${r * 2:03X}))"
            conds = []
            if k["_row"] is not None:
                conds.append(f"read1({h}+2) == ${base_bs:02X}")
            if base_pal is not None:
                conds.append(f"read1($0ED460+(read1({h}+1)*4)) == ${base_pal:02X}")
            E(f"assert {' && '.join(conds)}, \"room ${r:03X} header no longer matches kit {k['kit']}\"")
        if k["_row"] is not None:
            row_a = AA2_ROWS + k["_row"] * 4
            src_a = AA2_ROWS + base_bs * 4
            sheets = {int(s["slot"]): s for s in k.get("sheets") or []}
            for slot, s in sorted(sheets.items()):
                cp = hx(s["copy_of"])
                # Strict: a $00 row byte would show the room's main-group sheet,
                # which depends on the entrance ($0AA1), so it is not accepted.
                E(f"assert read1(${src_a + slot - 3:06X}) == ${cp:02X}, "
                  f"\"kit {k['kit']} slot {slot} source is not sheet ${cp:02X}\"")
            E("pushpc")
            E(f"org ${row_a:06X} ; @hook module=Dungeons kind=data protected_size=4")
            vals = []
            for i in range(4):
                s = sheets.get(3 + i)
                vals.append(f"${hx(s['sheet']):02X}" if s else f"read1(${src_a + i:06X})")
            E("  db " + ", ".join(vals))
            E("pullpc")
        if k.get("palette"):
            p = k["palette"]
            ppid, cp, cp_off = hx(p["id"]), hx(p["copy_of"]), hx(p["copy_offset"])
            E(f"assert read2(${PAL_INDEX + cp:06X}) == ${cp_off:04X}, "
              f"\"kit {k['kit']} palette source ${cp:02X} offset moved\"")
            words: list[str | None] = [None] * PAL_WORDS
            for sp in p["splices"]:
                for i, w in enumerate(sp["words"]):
                    words[sp["first"] + i] = w
            dst = PAL_DATA + PRIVATE_PALETTES[ppid]
            E("pushpc")
            E(f"org ${dst:06X} ; @hook module=Dungeons kind=data protected_size={PAL_WORDS * 2}")
            for i in range(0, PAL_WORDS, 6):
                E("  dw " + ", ".join(
                    w if w else f"read2(${PAL_DATA + cp_off + 2 * j:06X})"
                    for j, w in ((j, words[j]) for j in range(i, min(i + 6, PAL_WORDS)))))
            E(f"assert pc() == ${dst + PAL_WORDS * 2:06X}, \"kit palette must be exactly {PAL_WORDS} words\"")
            E("pullpc")
        E("")
    all_sheets = [(k, s) for k in kits for s in sorted(k.get("sheets") or [], key=lambda s: int(s["slot"]))]
    if all_sheets:
        E("; ---- kit sheet streams (3bpp LC-LZ2) and their pointer rows ----")
        E("assert GfxSheet_Bank == $23FD00 && GfxSheet_High == $23FE00 && GfxSheet_Low == $23FF00, "
          "\"gfx sheet arrays moved\"")
        E("pushpc")
        E(f"org ${KIT_SHEET_ORG:06X}")
        for k, s in all_sheets:
            E(f"WallSel_KitSheet_{hx(s['sheet']):02X}:  ; {k['kit']} slot {s['slot']}")
            E(f"  incbin \"Dungeons/Data/kits/{stream_name(k, s)}\"")
        E(f"assert pc() <= ${KIT_SHEET_END:06X}, \"kit sheet streams exceeded ${KIT_SHEET_ORG:06X}-${KIT_SHEET_END - 1:06X}\"")
        for k, s in all_sheets:
            sid = hx(s["sheet"])
            E(f"assert ${sid:02X} < !GfxSheet_Rows, \"kit sheet ${sid:02X} is past the sheet table\"")
            for arr, shift in ((0x23FD00, 16), (0x23FE00, 8), (0x23FF00, 0)):
                E(f"org ${arr + sid:06X} ; @hook module=Dungeons kind=data protected_size=1")
                E(f"  db WallSel_KitSheet_{sid:02X}>>{shift}" if shift else f"  db WallSel_KitSheet_{sid:02X}")
        E("pullpc")
    return "\n".join(out) + "\n"


def stream_name(k: dict, s: dict) -> str:
    return f"{k['kit']}.slot{int(s['slot'])}.lz2"


def kit_streams() -> dict[Path, bytes]:
    """lz2 stream per kit sheet, rebuilt from the tracked text grid."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import lz2
    import sheet_codec
    out: dict[Path, bytes] = {}
    for k in load_kits():
        for s in k.get("sheets") or []:
            raw = bytes(sheet_codec.grid_to_sheet(
                sheet_codec.text_to_grid((KITS_DIR / s["source"]).read_text())))
            if hashlib.sha256(raw).hexdigest() != s["decoded_sha256"]:
                raise SystemExit(f"{s['source']}: decoded sheet does not match decoded_sha256")
            comp = bytes(lz2.compress(raw))
            dec, used = lz2.decompress(comp)
            if dec != raw or used != len(comp):
                raise SystemExit(f"{s['source']}: lz2 round trip failed")
            out[KITS_DIR / stream_name(k, s)] = comp
    return out


def cmd_build(a: argparse.Namespace) -> int:
    texts = {OUT_ASM: render(), KITS_ASM: render_kits()}
    bins = kit_streams()
    if a.check:
        stale = [f for f, t in texts.items() if not f.exists() or f.read_text() != t]
        stale += [f for f, b in bins.items() if not f.exists() or f.read_bytes() != b]
        known = set(bins) | {KITS_ASM}
        stale += [f for f in KITS_DIR.glob("*.lz2") if f not in known]
        for f in stale:
            print(f"{f.relative_to(REPO)} is stale; run gen_wall_profiles.py build")
        if stale:
            return 1
        print(f"{OUT_ASM.relative_to(REPO)} + {KITS_ASM.relative_to(REPO)} + "
              f"{len(bins)} kit sheet stream(s) up to date")
        return 0
    KITS_DIR.mkdir(exist_ok=True)
    for f, t in texts.items():
        f.write_text(t)
        print(f"wrote {f.relative_to(REPO)}")
    for f in KITS_DIR.glob("*.lz2"):
        if f not in bins:
            f.unlink()
            print(f"removed stale {f.relative_to(REPO)}")
    for f, b in bins.items():
        f.write_bytes(b)
        print(f"wrote {f.relative_to(REPO)} ({len(b)} bytes)")
    return 0


def verify_palette_ownership(data: bytes) -> dict:
    """Private palettes are selected by WallSel, never an ordinary header.

    Read the final palette-set bytes, not just the input ROM: Sky's source
    override is an example of why an unused input id need not remain unused.
    """
    index = snes_pc(PAL_INDEX)
    headers = snes_pc(ROOM_HEADERS)
    if len(data) < max(index + max(PRIVATE_PALETTES) + 2,
                       headers + ROOM_COUNT * 2):
        raise ValueError("ROM is too short for wall-kit palette ownership")
    for pid, expected in PRIVATE_PALETTES.items():
        if rom_word(data, index + pid) != expected:
            raise ValueError(f"private palette ${pid:02X} offset moved")
    for room in range(ROOM_COUNT):
        pointer = rom_word(data, headers + room * 2)
        if pointer < 0x8000:
            raise ValueError(f"room ${room:03X} header is not mapped ROM")
        header = snes_pc(0x220000 | pointer)
        if header + 3 > len(data):
            raise ValueError(f"room ${room:03X} header is outside ROM")
        palette_set = data[header + 1]
        address = snes_pc(PAL_SETS) + palette_set * 4
        if address >= len(data):
            raise ValueError(f"room ${room:03X} palette set is outside ROM")
        pid = data[address]
        if pid in PRIVATE_PALETTES:
            raise ValueError(f"room ${room:03X} uses private kit palette "
                             f"${pid:02X} through palette set ${palette_set:02X}")
    return {"rooms_checked": ROOM_COUNT,
            "private_palettes": [f"0x{p:02X}" for p in PRIVATE_PALETTES]}


def verify_kit_glyph_ownership(data: bytes) -> dict:
    """Preserve native floors/animation and protect doors in the new mask slot."""
    from sheet_table import decomp, ptr
    doors = door_chars(data)
    sheets_checked = 0
    for kit in load_kits():
        rooms = [hx(r) for r in kit.get("rooms", [])]
        protected = floor_chars(data, rooms) | set(range(0x1B0, 0x1D0))
        owned = set(kit["_cmap"].values()) | {hx(c) for c in kit.get("in_place", [])}
        for sheet in kit.get("sheets", []):
            sid, source, slot = hx(sheet["sheet"]), hx(sheet["copy_of"]), sheet["slot"]
            actual = bytes(decomp(data, ptr(data, sid))[0])
            original = bytes(decomp(data, ptr(data, source))[0])
            if len(actual) != 1536 or len(original) != 1536:
                raise ValueError(f"kit {kit['kit']} sheet ${sid:02X} is not 3bpp")
            if hashlib.sha256(actual).hexdigest() != sheet["decoded_sha256"]:
                raise ValueError(f"kit {kit['kit']} sheet ${sid:02X} differs from source")
            for tile in range(64):
                char = slot * 64 + tile
                if actual[tile * 24:(tile + 1) * 24] == original[tile * 24:(tile + 1) * 24]:
                    continue
                # Existing slot-3 kit cells predate this admission. Their
                # accepted art is unchanged; the whole global door table also
                # contains unrelated dungeon shapes. Newly allocated slot-6
                # cells conservatively exclude that entire table.
                if char in protected or char not in owned or (slot == 6 and char in doors):
                    raise ValueError(f"kit {kit['kit']} overwrites protected/unowned glyph ${char:03X}")
            sheets_checked += 1
    return {"kit_sheets_checked": sheets_checked}


def cmd_verify_rom(a: argparse.Namespace) -> int:
    from asm_source import _load_global_defines
    if not _load_global_defines(REPO).get("ENABLE_WALL_PROFILE_SELECTOR", 0):
        print("Wall-profile selector is disabled; private palettes are inactive")
        return 0
    try:
        data = Path(a.rom).read_bytes()
        facts = verify_palette_ownership(data)
        facts.update(verify_kit_glyph_ownership(data))
    except (OSError, ValueError) as error:
        print(f"Wall-kit palette ownership: {error}", file=sys.stderr)
        return 1
    print(json.dumps(facts, sort_keys=True))
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
    ek = sub.add_parser("extract-kit", help="fit one candidate wall set into a private row")
    ek.add_argument("--kit", required=True, help="kit name (kit file stem)")
    ek.add_argument("--profile", required=True, help="profile name (words file stem)")
    ek.add_argument("--inventory-id", help="WALL_GFX_INVENTORY id, e.g. N9")
    ek.add_argument("--rom", required=True, help="candidate ROM (read only)")
    ek.add_argument("--base", required=True, help="unpatched base ROM (read only)")
    ek.add_argument("--origin", help="ROM the candidate was cut from: changes the base made "
                                     "after it are blocked, not routed (read only)")
    ek.add_argument("--rooms", required=True, help="comma list of hex room ids")
    ek.add_argument("--traces", required=True, help="dir of <ROOM>-traces.json (z3ed, base ROM)")
    ek.add_argument("--row", type=lambda s: int(s, 16), required=True, help="private row (hex)")
    ek.add_argument("--sheet", type=lambda s: int(s, 16), required=True, help="spare global sheet (hex)")
    ek.add_argument("--palette", type=lambda s: int(s, 16), required=True, help="private palette id*2 (hex)")
    ek.add_argument("--candidate-traces", help="dir of <ROOM>-traces.json traced on the candidate: "
                    "objects outside the carried classes that draw differently are listed as blocked")
    ek.add_argument("--note", help="provenance note")
    ek.add_argument("--protect-floors", action="store_true",
                    help="also keep the kit rooms' floor-fill chars (RoomDraw_DrawFloors) out of the free set")
    ek.set_defaults(fn=cmd_extract_kit)
    bd = sub.add_parser("build", help="emit wall_profiles.asm, kits.asm and kit streams")
    bd.add_argument("--check", action="store_true", help="fail if any output is stale")
    bd.set_defaults(fn=cmd_build)
    vr = sub.add_parser("verify-rom", help="reject compiled room consumers of private palettes")
    vr.add_argument("--rom", required=True, help="compiled ROM (read only)")
    vr.set_defaults(fn=cmd_verify_rom)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
