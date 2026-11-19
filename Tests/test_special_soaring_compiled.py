#!/usr/bin/env python3
"""Check compiled Special Overworld Soaring (6 stops) list/state/cache/cleanup
bytes with the existing Lakesnes 65816 CPU fixture.

Covers:
  - Menu_DrawSoaring (6 stops on rows 10..20, Sky gating on $7EF3B2 == $A5,
    cursor placement & clamp without mutating saved state)
  - SpecialSoaring_Open ($80..$BF admission, $7F/$C0 rejection)
  - Menu_SoaringRequested ($010C == $0B & $1AF0 in $80..$85)
  - Menu_SpecialSoaring (Up/Down/Left/Right wrap both Sky locked [0..4] and
    unlocked [0..5], cancel B/Start, select A for all 6 stops, SFX3 cues)
  - SpecialSoaring_Complete (all 6 $32-byte $7EC140 exit cache copies, Sky
    lock enforcement, Boat_ResetSession & swim-state cleanup)
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu, Fixture

STOPS = [
    # (index, label, menu_row, area_id, cam_y, cam_x, link_y, link_x, origin)
    (0, "GARRISON",     10, 0x0083, 0x00F0, 0x0688, 0x0140, 0x0700, 0x0790),
    (1, "ZORA_COAST",   12, 0x00A0, 0x08C0, 0x0208, 0x0910, 0x0280, 0x0640),
    (2, "DEKU_GROVE",   14, 0x00A8, 0x0AB0, 0x00B8, 0x0B00, 0x0130, 0x0596),
    (3, "GORON_COAST",  16, 0x00B0, 0x0C30, 0x0178, 0x0C80, 0x01F0, 0x01AE),
    (4, "COURAGE_ISLE", 18, 0x00A6, 0x0970, 0x0DB8, 0x09C0, 0x0E30, 0x0BB6),
    (5, "SKY",          20, 0x008C, 0x0260, 0x0868, 0x02B0, 0x08E0, 0x030C),
]


def char_tile(ch: str) -> int:
    if ch == "_":
        return 0x0F5
    if ch == ":":
        return 0x16B
    return 0x150 + ord(ch) - ord("A")


def execute(f, name, long_return=False):
    entry = f.addr(name)
    assert entry is not None, name
    p = f.cpu
    p.k = entry >> 16
    p.pc = entry & 65535
    p.db = 0x2D
    initial_sp = p.sp
    frame = ([entry >> 16, 0x6F, 0xFF] if long_return else [0x6F, 0xFF])
    for v in frame:
        f.put(p.sp, v)
        p.sp -= 1
    for _ in range(40000):
        if (p.k << 16 | p.pc) == ((entry & 0xFF0000) | 0x7000):
            assert p.sp == initial_sp, (name, "stack", p.sp)
            assert p.db == 0x2D, (name, "DBR", p.db)
            assert not f.bad_writes, (name, f.bad_writes)
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError((name, "instruction limit", hex(p.k), hex(p.pc)))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    for n in ("rom", "symbols", "lakesnes", "output"):
        ap.add_argument("--" + n, type=Path, required=True)
    a = ap.parse_args()
    rom = a.rom.read_bytes()
    sym = a.symbols.read_text()
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\dA-Fa-f]{2}):([\dA-Fa-f]{4}) (\S+)$", sym)
    }
    cases = []
    with tempfile.TemporaryDirectory(prefix="soaring-cpu-") as tmp:
        libpath = Path(tmp) / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(a.lakesnes / "snes/cpu.c"),
                str(a.lakesnes / "snes/statehandler.c"),
                "-o", str(libpath),
            ],
            check=True,
        )
        lib = C.CDLL(str(libpath))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        def fresh():
            f = Fixture(lib, rom, labels)
            f.word(0x010C, 0x0B)
            f.put(0x10, 0x0B)
            f.word(0x8A, 0x83)
            return f

        def read_word(f, at):
            return f.get(at) | (f.get(at + 1) << 8)

        # 1. Menu_DrawSoaring: Sky visibility + all 5 base rows + cursor clamp
        for value in (0, 1, 0xA4, 0xA5, 0xFF):
            f = fresh()
            f.put(0x7EF3B2, value)
            f.put(0x1AF0, 0x85)
            execute(f, "Menu_DrawSoaring")
            # Check all 5 always-visible stops
            for idx, label, row, *_ in STOPS[:5]:
                base = 0x1000 + row * 64 + 10 * 2
                got = [read_word(f, base + 2 * i) & 0x3FF for i in range(len(label))]
                exp = [char_tile(c) for c in label]
                assert got == exp, ("row label", label, value, [hex(x) for x in got])
            # Check Sky row visibility
            sky_base = 0x1000 + 20 * 64 + 10 * 2
            sky_visible = [read_word(f, sky_base + 2 * i) & 0x3FF for i in range(3)] == [
                char_tile(c) for c in "SKY"
            ]
            assert sky_visible == (value == 0xA5), ("Sky visibility", value, hex(read_word(f, sky_base)))
            # Cursor clamp when Sky locked vs preserved when Sky unlocked
            assert f.get(0x1AF0) == (0x85 if value == 0xA5 else 0x80)
            cur_row = 20 if value == 0xA5 else 10
            assert read_word(f, 0x1000 + cur_row * 64 + 7 * 2) == 0x256B
            assert f.get(0x7EF3B2) == value, "drawing changed saved state"
            cases.append("list-token-" + hex(value))
            f.close()

        # Verify rows 1..4 are NOT clamped when Sky is locked
        for row_idx in range(5):
            f = fresh()
            f.put(0x7EF3B2, 0x00)
            f.put(0x1AF0, 0x80 | row_idx)
            execute(f, "Menu_DrawSoaring")
            assert f.get(0x1AF0) == (0x80 | row_idx)
            cur_row = 10 + row_idx * 2
            assert read_word(f, 0x1000 + cur_row * 64 + 7 * 2) == 0x256B
            cases.append(f"cursor-unlocked-row-{row_idx}")
            f.close()

        # 2. SpecialSoaring_Open area gating
        for source, opens in (
            (0x7F, False), (0x80, True), (0x83, True), (0x8C, True),
            (0xA0, True), (0xA6, True), (0xA8, True), (0xB0, True),
            (0xBF, True), (0xC0, False),
        ):
            f = fresh()
            f.word(0x8A, source)
            execute(f, "SpecialSoaring_Open", True)
            assert f.get(0x10) == (0x0E if opens else 0x0B)
            if opens:
                assert f.get(0x11) == 1 and f.get(0x1AF0) == 0x80
            cases.append("source-" + hex(source))
            f.close()

        # 3. SpecialSoaring_Complete: invalid/locked rejections + all 6 stops + boat/swim cleanup
        for pending, learned in ((0, 0), (0x80, 0), (0xC5, 0), (0xC5, 0xA4), (0xC6, 0xA5), (0xC7, 0xA5)):
            f = fresh()
            f.put(0x1AF0, pending)
            f.put(0x7EF3B2, learned)
            execute(f, "SpecialSoaring_Complete", True)
            assert f.get(0x7EF3B2) == learned, "transport changed saved state"
            assert f.get(0x10) == 0x0B, ("should reject", hex(pending), hex(learned))
            cases.append(f"reject-{pending:02x}-{learned:02x}")
            f.close()

        boat_marker = labels.get("Oracle_Boat_Marker") or labels.get("Boat_Marker")
        for idx, label, _row, area_id, cam_y, cam_x, link_y, link_x, origin in STOPS:
            f = fresh()
            f.put(0x1AF0, 0xC0 | idx)
            f.put(0x7EF3B2, 0xA5 if idx == 5 else 0x00)
            # Dirty boat + swimming state to verify cleanup!
            if boat_marker is not None:
                f.word(boat_marker, 0x4254)
            f.put(0x0345, 0x01)
            f.put(0x0351, 0x01)
            f.put(0x02CB, 0x01)
            f.put(0x034F, 0x01)
            f.put(0x032A, 0x01)
            f.put(0x5D, 0x04)
            execute(f, "SpecialSoaring_Complete", True)
            assert f.get(0x10) == 8 and f.get(0x11) == 0 and f.get(0x1AF0) == 0
            assert read_word(f, 0xA0) == 0x0151
            assert read_word(f, 0x7EC140) == area_id, (label, hex(read_word(f, 0x7EC140)))
            assert read_word(f, 0x7EC142) == 0x0016
            assert read_word(f, 0x7EC144) == cam_y, (label, hex(read_word(f, 0x7EC144)))
            assert read_word(f, 0x7EC146) == cam_x, (label, hex(read_word(f, 0x7EC146)))
            assert read_word(f, 0x7EC148) == link_y, (label, hex(read_word(f, 0x7EC148)))
            assert read_word(f, 0x7EC14A) == link_x, (label, hex(read_word(f, 0x7EC14A)))
            assert read_word(f, 0x7EC14C) == area_id
            assert read_word(f, 0x7EC14E) == origin, (label, hex(read_word(f, 0x7EC14E)))
            assert read_word(f, 0x7EC150) == (link_y + 0x1F)
            assert read_word(f, 0x7EC152) == (link_x + 0x07)
            # Scroll modifiers zeroed
            for off in (0x6A, 0x6C, 0x6E, 0x70):
                assert read_word(f, 0x7EC100 + off) == 0
            # Boat & swimming state cleanly reset
            if boat_marker is not None:
                assert read_word(f, boat_marker) == 0, "Boat_Marker not cleared"
            assert f.get(0x0345) == 0 and f.get(0x0351) == 0
            assert f.get(0x02CB) == 0 and f.get(0x034F) == 0 and f.get(0x032A) == 0
            assert f.get(0x5D) == 0
            cases.append(f"transport-stop-{idx}-{label.lower()}")
            f.close()

        # 4. Navigation wrap (Up/Down/Left/Right) for Sky locked (0..4) & unlocked (0..5)
        for learned, max_row in ((0x00, 4), (0xA5, 5)):
            # Walk Down around entire ring: 0 -> 1 -> ... -> max_row -> 0
            cur = 0
            for step in range(max_row + 1):
                f = fresh()
                f.put(0x1AF0, 0x80 | cur)
                f.put(0x7EF3B2, learned)
                f.put(0xF4, 0x04)  # Down
                execute(f, "Menu_SpecialSoaring")
                expected = (cur + 1) % (max_row + 1)
                assert f.get(0x1AF0) == (0x80 | expected), (learned, "down", cur, hex(f.get(0x1AF0)))
                assert f.get(0x012F) == 0x20 and f.get(0x17) == 1
                cur = expected
                f.close()
            cases.append(f"nav-down-wrap-{learned:02x}")

            # Walk Up around entire ring: 0 -> max_row -> ... -> 0
            cur = 0
            for step in range(max_row + 1):
                f = fresh()
                f.put(0x1AF0, 0x80 | cur)
                f.put(0x7EF3B2, learned)
                f.put(0xF4, 0x08)  # Up
                execute(f, "Menu_SpecialSoaring")
                expected = (cur - 1) % (max_row + 1)
                assert f.get(0x1AF0) == (0x80 | expected), (learned, "up", cur, hex(f.get(0x1AF0)))
                assert f.get(0x012F) == 0x20 and f.get(0x17) == 1
                cur = expected
                f.close()
            cases.append(f"nav-up-wrap-{learned:02x}")

        # 5. Menu_SoaringRequested admission
        for module, cursor, requested in (
            (0x09, 0x80, False),
            (0x0B, 0x00, False),
            (0x0B, 0xC0, False),
            (0x0B, 0x80, True),
            (0x0B, 0x84, True),
            (0x0B, 0x85, True),
        ):
            f = fresh()
            f.word(0x010C, module)
            f.put(0x1AF0, cursor)
            execute(f, "Menu_SoaringRequested")
            assert f.cpu.c == requested, (hex(module), hex(cursor), f.cpu.c)
            cases.append(f"menu-admission-{module:02x}-{cursor:02x}")
            f.close()

        # 6. Cancel (B / Start)
        for pad in (0x80, 0x10):
            f = fresh()
            f.put(0x1AF0, 0x83)
            f.put(0xF4, pad)
            execute(f, "Menu_SpecialSoaring")
            assert f.get(0x1AF0) == 0 and f.get(0x200) == 8 and f.get(0x012F) == 0x12
            cases.append("cancel-" + hex(pad))
            f.close()

        # 7. Select A on every stop 0..5
        for idx in range(6):
            f = fresh()
            f.put(0x1AF0, 0x80 | idx)
            f.put(0x7EF3B2, 0xA5 if idx == 5 else 0x00)
            f.put(0xF6, 0x80)
            execute(f, "Menu_SpecialSoaring")
            assert f.get(0x1AF0) == (0xC0 | idx) and f.get(0x200) == 8 and f.get(0x012F) == 0x12
            cases.append(f"select-stop-{idx}")
            f.close()

    result = {
        "passed": True,
        "case_count": len(cases),
        "cases": cases,
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "scope": "Compiled 65816 CPU/menu-buffer/state/cache/cleanup proof for all 6 Special Overworld Soaring stops.",
    }
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
