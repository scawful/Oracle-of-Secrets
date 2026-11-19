#!/usr/bin/env python3
"""Compiled 65816 CPU proof for Special Overworld Mode 7 Lyra Sea Map numbered-pin
Soaring (1-6) and Light World Bird Travel non-regression via Lakesnes.

Covers:
  - SpecialSoaring_Open ($80..$BF admission -> Module $0E / Sub $0A, Ocarina timer/Y-lock clear;
    LW/DW/out-of-range rejection)
  - TravelPicker_LoadMap ($0AB74B: SW starts on Pin 1 even with TravelSpotsVisited=0;
    LW starts on first visited bit)
  - TravelPicker_Move ($0AB7AC: Up/Down/Left/Right wrap for Sky locked [0..4],
    Sky unlocked [0..5], and LW visited mask)
  - TravelPicker_Numeral ($0AB813: exact Lyra Sea pin coordinates 1..5 / 1..6,
    hiding pins 6-8 when Sky locked and 7-8 when unlocked, LW vanilla dispatch)
  - TravelPicker_CheckAction ($0AB78F: SW B/X cancel -> Sub $07 + $0200++,
    SW A/START confirm -> Sub $0A + $0200++, cancel priority, LW vanilla $F0/$F2 confirm)
  - TravelPicker_LoadSelectedScreen ($0AB8C5) & SpecialSoaring_ExecuteTransport:
    all 6 verified $32-byte $7EC140 exit cache copies, Sky lock enforcement + WorldMap_ExitMap
    fallback, SpecialOverworld_MapSavedPos restore, Boat/swim/$4B/$031F cleanup, LW handoff
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
    # (index, label, area_id, cam_y, cam_x, link_y, link_x, origin, pin_x, pin_y)
    (0, "GARRISON",     0x0083, 0x00F0, 0x0688, 0x0140, 0x0700, 0x0790, 0x0700, 0x0140),
    (1, "ZORA_COAST",   0x00A0, 0x08C0, 0x0208, 0x0910, 0x0280, 0x0640, 0x0280, 0x0910),
    (2, "DEKU_GROVE",   0x00A8, 0x0AB0, 0x00B8, 0x0B00, 0x0130, 0x0596, 0x0130, 0x0B00),
    (3, "GORON_COAST",  0x00B0, 0x0C30, 0x0178, 0x0C80, 0x01F0, 0x01AE, 0x01F0, 0x0C80),
    (4, "COURAGE_ISLE", 0x00A6, 0x09D0, 0x0DA8, 0x0A20, 0x0E20, 0x0EB4, 0x0E20, 0x0A20),
    (5, "SKY",          0x008C, 0x0260, 0x0868, 0x02B0, 0x08E0, 0x030C, 0x08E0, 0x02B0),
]


def run_until(f, entry, *, db=0x0A, long_return=True, stop_addrs=(), limit=40000):
    """Execute from SNES address `entry` until either RTL/RTS sentinel or one of `stop_addrs`."""
    p = f.cpu
    p.k = entry >> 16
    p.pc = entry & 0xFFFF
    p.db = db
    p.mf = True
    p.xf = True
    p.dp = 0
    initial_sp = p.sp
    sentinel = (entry & 0xFF0000) | 0x7000
    frame = ([entry >> 16, 0x6F, 0xFF] if long_return else [0x6F, 0xFF])
    for v in frame:
        f.put(p.sp, v)
        p.sp -= 1
    stops = set(stop_addrs)
    for _ in range(limit):
        cur = (p.k << 16) | p.pc
        if cur == sentinel:
            assert p.sp == initial_sp, (hex(entry), "stack", hex(p.sp), hex(initial_sp))
            assert p.db == db, (hex(entry), "DBR", hex(p.db), hex(db))
            assert not f.bad_writes, (hex(entry), f.bad_writes)
            return "RETURN"
        if cur in stops:
            assert p.db == db, (hex(entry), "DBR at stop", hex(cur), hex(p.db))
            assert not f.bad_writes, (hex(entry), f.bad_writes)
            return cur
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError((hex(entry), "instruction limit", hex(p.k), hex(p.pc)))


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

    def sym_addr(name):
        return labels.get("Oracle_" + name) or labels.get(name)

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

        def fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05):
            f = Fixture(lib, rom, labels)
            f.word(0x8A, area)
            f.put(0x10, module)
            f.put(0x11, sub)
            f.put(0x0200, step)
            f.word(0x010C, 0x09)
            return f

        def read_word(f, at):
            return f.get(at) | (f.get(at + 1) << 8)

        # ------------------------------------------------------------------
        # 1. SpecialSoaring_Open area admission & Mode 7 Flute Map entry
        # ------------------------------------------------------------------
        open_addr = sym_addr("SpecialSoaring_Open")
        assert open_addr is not None, "SpecialSoaring_Open missing"
        for source, opens in (
            (0x00, False), (0x2C, False), (0x7F, False),
            (0x80, True), (0x83, True), (0x8C, True),
            (0xA0, True), (0xA6, True), (0xA8, True), (0xB0, True),
            (0xBF, True), (0xC0, False),
        ):
            f = fresh(area=source, module=0x09, sub=0x00, step=0x03)
            f.put(0x03F0, 0x80)
            f.put(0x3A, 0x40)
            res = run_until(f, open_addr, db=0x07, long_return=True)
            assert res == "RETURN"
            if opens:
                assert f.get(0x10) == 0x0E and f.get(0x11) == 0x0A
                assert f.get(0x010C) == 0x09 and f.get(0x0200) == 0x00
                assert f.get(0x03F0) == 0x00 and (f.get(0x3A) & 0x40) == 0
            else:
                assert f.get(0x10) == 0x09 and f.get(0x11) == 0x00
                assert f.get(0x03F0) == 0x80 and (f.get(0x3A) & 0x40) == 0x40
            cases.append(f"open-area-{source:02x}")
            f.close()

        # ------------------------------------------------------------------
        # 2. TravelPicker_LoadMap ($0AB74B): SW pin 1 init + LW regression
        # ------------------------------------------------------------------
        for area, visited, sky, exp_cursor in (
            (0x83, 0x00, 0x00, 0),
            (0xA6, 0x00, 0xA5, 0),
            (0x2C, 0x00, 0xA5, 0),
            (0x2C, 0x01, 0x00, 0),
            (0x2C, 0x08, 0x00, 3),
            (0x2C, 0x20, 0x00, 5),
            (0x2C, 0x80, 0x00, 7),
        ):
            f = fresh(area=area, step=0x01)
            f.put(0x7EF412, visited)
            f.put(0x7EF3B2, sky)
            f.put(0x1AF0, 0x77)
            res = run_until(f, 0x0AB74B, stop_addrs=(0x0ABA30,))
            assert res == 0x0ABA30
            assert f.get(0x1AF0) == exp_cursor, (hex(area), hex(visited), f.get(0x1AF0))
            cases.append(f"loadmap-{area:02x}-v{visited:02x}-s{sky:02x}")
            f.close()

        # ------------------------------------------------------------------
        # 3. TravelPicker_Move ($0AB7AC): SW wrap 1..5 / 1..6 + LW regression
        # ------------------------------------------------------------------
        for learned, max_idx in ((0x00, 4), (0xA4, 4), (0xA5, 5)):
            # Down & Right forward wrap
            for btn, tag in ((0x04, "down"), (0x01, "right")):
                cur = 0
                for _ in range(max_idx + 1):
                    f = fresh(area=0x83)
                    f.put(0x7EF3B2, learned)
                    f.put(0x7EF412, 0x00)  # must ignore LW visited mask on SW
                    f.cpu.x = cur
                    f.put(0xF4, btn)
                    res = run_until(f, sym_addr("TravelPicker_Move"), long_return=True)
                    assert res == "RETURN"
                    exp = (cur + 1) % (max_idx + 1)
                    assert f.get(0x1AF0) == exp, (learned, tag, cur, f.get(0x1AF0))
                    assert f.get(0x012F) == 0x20
                    assert f.cpu.x == cur  # preserves X
                    cur = exp
                    f.close()
                cases.append(f"sw-move-{tag}-sky{learned:02x}")

            # Up & Left backward wrap
            for btn, tag in ((0x08, "up"), (0x02, "left")):
                cur = 0
                for _ in range(max_idx + 1):
                    f = fresh(area=0x83)
                    f.put(0x7EF3B2, learned)
                    f.put(0x7EF412, 0x00)
                    f.cpu.x = cur
                    f.put(0xF4, btn)
                    res = run_until(f, sym_addr("TravelPicker_Move"), long_return=True)
                    assert res == "RETURN"
                    exp = (cur - 1) % (max_idx + 1)
                    assert f.get(0x1AF0) == exp, (learned, tag, cur, f.get(0x1AF0))
                    assert f.get(0x012F) == 0x20
                    assert f.cpu.x == cur
                    cur = exp
                    f.close()
                cases.append(f"sw-move-{tag}-sky{learned:02x}")

        # LW visited mask regression: bits 0, 2, 5 ($25)
        lw_ring = [0, 2, 5]
        for idx, cur in enumerate(lw_ring):
            f = fresh(area=0x2C)
            f.put(0x7EF412, 0x25)
            f.put(0x7EF3B2, 0xA5)
            f.cpu.x = cur
            f.put(0xF4, 0x04)  # Down
            assert run_until(f, sym_addr("TravelPicker_Move"), long_return=True) == "RETURN"
            assert f.get(0x1AF0) == lw_ring[(idx + 1) % len(lw_ring)]
            f.close()
        cases.append("lw-move-visited-mask-regression")

        # ------------------------------------------------------------------
        # 4. TravelPicker_Numeral ($0AB813): pin coords, lock gating, LW intact
        # ------------------------------------------------------------------
        for learned, unlocked_count in ((0x00, 5), (0xA5, 6)):
            for cursor in (0, 2, unlocked_count - 1):
                for pin in range(8):
                    f = fresh(area=0x83)
                    f.put(0x7EF3B2, learned)
                    f.put(0x7EF412, 0x00)
                    f.put(0x1AF0, cursor)
                    f.cpu.x = pin
                    res = run_until(
                        f,
                        0x0AB813,
                        stop_addrs=(0x0AB818, 0x0AB844, 0x0AB864, 0x0AB890, 0x0AB8AA),
                    )
                    if pin >= unlocked_count:
                        assert res == 0x0AB8AA, (learned, cursor, pin, hex(res))
                    else:
                        exp_stop = 0x0AB844 if pin == cursor else 0x0AB890
                        assert res == exp_stop, (learned, cursor, pin, hex(res), hex(exp_stop))
                        exp_px, exp_py = STOPS[pin][8], STOPS[pin][9]
                        assert read_word(f, 0x7EC10A) == exp_px, (pin, hex(read_word(f, 0x7EC10A)), hex(exp_px))
                        assert read_word(f, 0x7EC108) == exp_py, (pin, hex(read_word(f, 0x7EC108)), hex(exp_py))
                        assert f.get(0x1AB0 + pin) == (exp_px & 0xFF)
                        assert f.get(0x1AC0 + pin) == (exp_px >> 8)
                        assert f.get(0x1AD0 + pin) == (exp_py & 0xFF)
                        assert f.get(0x1AE0 + pin) == (exp_py >> 8)
                    f.close()
            cases.append(f"sw-numerals-sky{learned:02x}")

        # LW numeral regression
        for pin, cursor, visited, exp_stop in (
            (0, 0, 0x01, 0x0AB818),
            (3, 0, 0x09, 0x0AB864),
            (4, 0, 0x09, 0x0AB8AA),
            (7, 7, 0x80, 0x0AB818),
        ):
            f = fresh(area=0x2C)
            f.put(0x7EF412, visited)
            f.put(0x1AF0, cursor)
            f.cpu.x = pin
            res = run_until(
                f, 0x0AB813, stop_addrs=(0x0AB818, 0x0AB844, 0x0AB864, 0x0AB890, 0x0AB8AA)
            )
            assert res == exp_stop, (pin, cursor, hex(visited), hex(res))
            f.close()
        cases.append("lw-numerals-regression")

        # ------------------------------------------------------------------
        # 5. TravelPicker_CheckAction ($0AB78F): SW confirm/cancel + LW intact
        # ------------------------------------------------------------------
        # SW cancel: B ($F4=$80), X ($F6=$40), and B+A priority
        for f4, f6, tag in ((0x80, 0x00, "B"), (0x00, 0x40, "X"), (0x80, 0x80, "B+A")):
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
            f.put(0x1AF0, 0x03)
            f.put(0xF4, f4)
            f.put(0xF6, f6)
            res = run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,))
            assert res == "RETURN", (tag, res)
            assert f.get(0x11) == 0x07 and f.get(0x0200) == 0x06 and f.get(0x1AF0) == 0x00
            cases.append(f"sw-cancel-{tag}")
            f.close()

        # SW confirm: A ($F6=$80) and START ($F4=$10)
        for f4, f6, tag in ((0x00, 0x80, "A"), (0x10, 0x00, "START")):
            f = fresh(area=0xA6, module=0x0E, sub=0x0A, step=0x05)
            f.put(0x1AF0, 0x04)
            f.put(0xF4, f4)
            f.put(0xF6, f6)
            res = run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,))
            assert res == "RETURN", (tag, res)
            assert f.get(0x11) == 0x0A and f.get(0x0200) == 0x06 and f.get(0x1AF0) == 0x04
            cases.append(f"sw-confirm-{tag}")
            f.close()

        # SW no-op (even if held $F0/$F2 has $C0 without new press!)
        f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x05)
        f.put(0xF0, 0xC0)
        f.put(0xF2, 0xC0)
        f.put(0xF4, 0x04)  # D-pad Down only
        res = run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,))
        assert res == 0x0AB79D and f.get(0x0200) == 0x05 and f.get(0x11) == 0x0A
        cases.append("sw-no-action-held-ignored")
        f.close()

        # LW vanilla confirm ($F2/$F0 & $C0) and idle
        f = fresh(area=0x2C, module=0x0E, sub=0x0A, step=0x05)
        f.put(0xF2, 0x80)
        assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == "RETURN"
        assert f.get(0x0200) == 0x06 and f.get(0x11) == 0x0A
        f.close()

        f = fresh(area=0x2C, module=0x0E, sub=0x0A, step=0x05)
        assert run_until(f, 0x0AB78F, stop_addrs=(0x0AB79D,)) == 0x0AB79D
        assert f.get(0x0200) == 0x05
        f.close()
        cases.append("lw-action-regression")

        # ------------------------------------------------------------------
        # 6. TravelPicker_LoadSelectedScreen ($0AB8C5) & ExecuteTransport
        # ------------------------------------------------------------------
        exec_addr = sym_addr("SpecialSoaring_ExecuteTransport")
        assert exec_addr is not None, "SpecialSoaring_ExecuteTransport missing"

        # Invalid / Sky-locked rejections -> ExecuteTransport C=0 & hook falls back to WorldMap_ExitMap
        for cursor, learned in ((5, 0x00), (5, 0xA4), (6, 0xA5), (7, 0xA5), (0xFF, 0xA5)):
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x07)
            f.put(0x1AF0, cursor)
            f.put(0x7EF3B2, learned)
            assert run_until(f, exec_addr, long_return=True) == "RETURN"
            assert f.cpu.c == 0 and f.get(0x10) == 0x0E and f.get(0x7EF3B2) == learned
            f.close()

            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x07)
            f.put(0x1AF0, cursor)
            f.put(0x7EF3B2, learned)
            res = run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9))
            assert res == 0x0ABC54, (cursor, learned, hex(res))
            f.close()
            cases.append(f"reject-{cursor:02x}-{learned:02x}")

        # LW LoadSelectedScreen regression -> reads $7EF2BB and resumes at $0AB8C9
        f = fresh(area=0x2C, module=0x0E, sub=0x0A, step=0x07)
        f.put(0x7EF2BB, 0x5A)
        res = run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9))
        assert res == 0x0AB8C9 and (f.cpu.a & 0xFF) == 0x5A
        cases.append("lw-load-selected-regression")
        f.close()

        # All 6 valid Special Overworld landings via $0AB8C5 hook!
        boat_marker = sym_addr("Boat_Marker")
        for idx, label, area_id, cam_y, cam_x, link_y, link_x, origin, _px, _py in STOPS:
            f = fresh(area=0x83, module=0x0E, sub=0x0A, step=0x07)
            f.put(0x1AF0, idx)
            f.put(0x7EF3B2, 0xA5 if idx == 5 else 0x00)
            # Arm SpecialOverworld_MapSavedPos backup to verify restore!
            f.word(0x7EC133, 0x0412)
            f.word(0x7EC135, 0x0734)
            f.put(0x7EC137, 0x01)
            f.word(0x7EC108, 0x9999)
            f.word(0x7EC10A, 0x8888)
            # Dirty boat, swimming, invincibility blink ($031F), link-hide ($4B), Korok sheet ($0AA5)
            if boat_marker is not None:
                f.word(boat_marker, 0x4254)
            f.put(0x0345, 0x01)
            f.put(0x0351, 0x01)
            f.put(0x02CB, 0x01)
            f.put(0x034F, 0x01)
            f.put(0x032A, 0x01)
            f.put(0x5D, 0x04)
            f.put(0x4B, 0x0C)
            f.put(0x031F, 0x90)
            f.put(0x0AA5, 0x01)

            res = run_until(f, 0x0AB8C5, stop_addrs=(0x0ABC54, 0x0AB8C9))
            assert res == "RETURN", (label, res)
            assert f.get(0x10) == 0x08 and f.get(0x11) == 0x00
            assert f.get(0x0200) == 0x00 and f.get(0x1AF0) == 0x00
            assert f.get(0x012F) == 0x10 and f.get(0x012C) == 0xF3
            assert f.get(0x7EF3CA) == 0x00  # SavedWorld = 0
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
            for off in (0x6A, 0x6C, 0x6E, 0x70):
                assert read_word(f, 0x7EC100 + off) == 0
            # Map return backup restored & cleared
            assert f.get(0x7EC137) == 0x00
            assert read_word(f, 0x7EC108) == 0x0412 and read_word(f, 0x7EC10A) == 0x0734
            # Boat, swim, blink, hide, Korok flag all cleared
            if boat_marker is not None:
                assert read_word(f, boat_marker) == 0, "Boat_Marker not cleared"
            assert f.get(0x0345) == 0 and f.get(0x0351) == 0
            assert f.get(0x02CB) == 0 and f.get(0x034F) == 0 and f.get(0x032A) == 0
            assert f.get(0x5D) == 0 and f.get(0x4B) == 0 and f.get(0x031F) == 0
            assert f.get(0x0AA5) == 0
            cases.append(f"transport-stop-{idx}-{label.lower()}")
            f.close()

    result = {
        "passed": True,
        "case_count": len(cases),
        "cases": cases,
        "rom_sha256": hashlib.sha256(rom).hexdigest(),
        "scope": "Compiled 65816 proof for Lyra Sea Mode 7 World Map numbered-pin Soaring (1-6), cancel/confirm, cache/cleanup, and LW Bird Travel non-regression.",
    }
    a.output.write_text(json.dumps(result, indent=2) + "\n")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
