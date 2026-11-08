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
        words_by_profile.append((p, doc, cls))

    out: list[str] = []
    E = out.append
    E("; GENERATED by Scripts/Generate/gen_wall_profiles.py build - do not edit by hand.")
    E("; Input: Dungeons/Data/wall_profiles/wall_profiles.json + *.words.json")
    for p, doc, cls in words_by_profile:
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
    for _p, _doc, cls in words_by_profile:
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
    return "\n".join(out) + "\n"


def cmd_build(a: argparse.Namespace) -> int:
    text = render()
    if a.check:
        if not OUT_ASM.exists() or OUT_ASM.read_text() != text:
            print(f"{OUT_ASM.relative_to(REPO)} is stale; run gen_wall_profiles.py build")
            return 1
        print(f"{OUT_ASM.relative_to(REPO)} up to date")
        return 0
    OUT_ASM.write_text(text)
    print(f"wrote {OUT_ASM.relative_to(REPO)}")
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
    bd = sub.add_parser("build", help="emit wall_profiles.asm")
    bd.add_argument("--check", action="store_true", help="fail if the asm is stale")
    bd.set_defaults(fn=cmd_build)
    a = ap.parse_args()
    return a.fn(a)


if __name__ == "__main__":
    raise SystemExit(main())
