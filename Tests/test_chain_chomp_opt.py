#!/usr/bin/env python3
"""Compiled 65816 unit tests (Lakesnes) for:
1. Sprites/Enemies/chain_chomp_opt.asm:
   - 16-slot disjoint chain buffer allocation ($7FFC00/$7FFD00, slots 0..15).
   - Exact vanilla-equivalent leash clamping, pipelined hardware-multiply chain
     lerp (asserting >= 8 CPU cycles between WRMPYB write and RDMPYH read), and
     bit-identical 6-link OAM emission (including X-high bit, Y-offscreen $F0
     clipping, and lunge jitter).
2. Masks/gbc_form.asm (LinkState_GameboyInDungeonEntrance):
   - Zero per-frame ShieldWorld_SyncBoth / UpdateGbcPalette / $15 CGRAM reload
     in Light World dungeons and in Dark World steady-state frames, while still
     applying GBC form + shield sync on the initial DW transition.
"""

from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]


def _find_lakesnes() -> Path:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    raise RuntimeError("Could not locate lakesnes checkout; set LAKESNES_DIR")


def _extract_block(src: str, label: str) -> str:
    start = src.index(label + ":")
    opened = src.index("{", start)
    depth = 1
    i = opened + 1
    while depth:
        if src[i] == "{":
            depth += 1
        elif src[i] == "}":
            depth -= 1
        i += 1
    return src[start:i] + "\n"


def _extract_data_table(src: str, label: str) -> str:
    m = re.search(rf"(?m)^{re.escape(label)}:\n(?:[ \t]+d[bwl][^\n]*\n)+", src)
    assert m is not None, f"table {label} not found"
    return m.group(0)


class ChainChompFixture(Fixture):
    """Lakesnes fixture with cycle-accurate SNES $4202/$4203/$4216/$4217 multiplier."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        self.cpu_cycles = 0
        self.wrmpya = 0
        self.wrmpyb = 0
        self.rdmpy = 0
        self.mult_kick_cycle = -1000
        self.min_mult_wait = 10**9
        self.mult_reads = 0
        super().__init__(lib, rom, labels)
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(self._idle)
        # Re-init CPU with our cycle-counting idle callback
        self.lib.cpu_free(self.p)
        self.p = lib.cpu_init(None, self.read_cb, self.write_cb, self.idle_cb)
        self.cpu = self.p.contents
        for n in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped",
                  "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, n, False)
        self.cpu.mf = self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x1FF
        self.cpu.a = self.cpu.x = self.cpu.y = 0
        self.cpu.db = 0x1D

    def _idle(self, _mem, _waiting):
        self.cpu_cycles += 1

    def read(self, a: int) -> int:
        self.cpu_cycles += 1
        bank = a >> 16
        lo = a & 0xFFFF
        if (bank & 0x7F) < 0x40 and lo in (0x4216, 0x4217):
            wait = self.cpu_cycles - self.mult_kick_cycle
            if wait < self.min_mult_wait:
                self.min_mult_wait = wait
            self.mult_reads += 1
            return (self.rdmpy & 0xFF) if lo == 0x4216 else ((self.rdmpy >> 8) & 0xFF)
        return super().read(a)

    def write(self, a: int, v: int) -> None:
        self.cpu_cycles += 1
        bank = a >> 16
        lo = a & 0xFFFF
        if (bank & 0x7F) < 0x40 and lo == 0x4202:
            self.wrmpya = v & 0xFF
            return
        if (bank & 0x7F) < 0x40 and lo == 0x4203:
            self.wrmpyb = v & 0xFF
            self.rdmpy = (self.wrmpya * self.wrmpyb) & 0xFFFF
            self.mult_kick_cycle = self.cpu_cycles
            return
        super().write(a, v)

    def run_jsl(self, name: str, slot: int, db: int = 0x1D, check_x: bool = True) -> int:
        c = self.cpu
        c.mf = c.xf = True
        c.x = slot & 0xFF
        c.db = db
        entry = self.addr(name)
        assert entry is not None, f"missing symbol {name}"
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        # Push return address $01:FFFF -> RTL lands at $01:0000? Use $02:6FFF -> $02:7000
        self.put(sp, 0x02)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        start_cyc = self.cpu_cycles
        for _ in range(10000):
            pc = (c.k << 16) | c.pc
            if pc == 0x027000:
                assert c.sp == sp, f"{name}: SP drift {c.sp:#x} != {sp:#x}"
                assert c.mf and c.xf, f"{name}: M/X width leak mf={c.mf} xf={c.xf}"
                assert c.db == db, f"{name}: DBR leak {c.db:#x} != {db:#x}"
                if check_x:
                    assert (c.x & 0xFF) == slot, f"{name}: slot X clobbered {c.x:#x} != {slot:#x}"
                assert not self.bad_writes, f"{name}: bad writes {self.bad_writes}"
                return self.cpu_cycles - start_cyc
            if pc in self.stubs:
                self.calls.append(self.stubs[pc])
                self.stub(self.stubs[pc])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name}: instruction ceiling at ${c.k:02X}:{c.pc:04X}")

    def read_links(self, slot: int) -> tuple[list[int], list[int]]:
        off = slot * 16
        xs = [self.ram[0x1FC00 + off + i * 2] | (self.ram[0x1FC00 + off + i * 2 + 1] << 8) for i in range(6)]
        ys = [self.ram[0x1FD00 + off + i * 2] | (self.ram[0x1FD00 + off + i * 2 + 1] << 8) for i in range(6)]
        return xs, ys

    def write_links(self, slot: int, xs: list[int], ys: list[int]) -> None:
        off = slot * 16
        for i in range(6):
            self.ram[0x1FC00 + off + i * 2] = xs[i] & 0xFF
            self.ram[0x1FC00 + off + i * 2 + 1] = (xs[i] >> 8) & 0xFF
            self.ram[0x1FD00 + off + i * 2] = ys[i] & 0xFF
            self.ram[0x1FD00 + off + i * 2 + 1] = (ys[i] >> 8) & 0xFF


def _vanilla_clamp_axis(vals: list[int]) -> list[int]:
    out = list(vals)
    for k in range(5):
        diff = (out[k] - out[k + 1]) & 0xFFFF
        sdiff = diff - 0x10000 if diff & 0x8000 else diff
        if sdiff >= 8:
            out[k + 1] = (out[k] - 8) & 0xFFFF
        elif sdiff < -8:
            out[k + 1] = (out[k] + 8) & 0xFFFF
    return out


def _vanilla_move_axis(vals: list[int], anchor: int) -> list[int]:
    out = list(vals)
    d = (out[0] - anchor) & 0xFF
    neg = bool(d & 0x80)
    mag = ((-d) & 0xFF) if neg else d
    mults = (0xCD, 0x9A, 0x66, 0x33, 0x08)
    for idx, m in enumerate(mults, start=1):
        hi = ((mag * m) >> 8) & 0xFF
        if neg:
            target = (anchor + (hi ^ 0xFF) + 0xFF00) & 0xFFFF
        else:
            target = (anchor + hi) & 0xFFFF
        cur = out[idx]
        if cur != target:
            diff = (cur - target) & 0xFFFF
            if diff & 0x8000:
                out[idx] = (cur + 1) & 0xFFFF
            else:
                out[idx] = (cur - 1) & 0xFFFF
    return out


class TestChainChompOptAndGbcDungeon(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        lakesnes = _find_lakesnes()
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="oos-cc-opt-")
        base = Path(cls._tmpdir.name)
        dll = base / "cpu.dylib"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2",
             str(lakesnes / "snes" / "cpu.c"),
             str(lakesnes / "snes" / "statehandler.c"),
             "-o", str(dll)],
            check=True,
        )
        cls._lib = C.CDLL(str(dll))
        cls._lib.cpu_init.restype = C.POINTER(Cpu)
        cls._lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls._lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        # Assemble Sprites/Enemies/chain_chomp_opt.asm onto a synthetic 2MB ROM with vanilla bank-$1D preimages
        raw = bytearray(b"\xFF" * 0x200000)
        def put_preimage(snes_addr: int, data: bytes) -> None:
            pc = ((snes_addr >> 16) & 0x7F) * 0x8000 + (snes_addr & 0x7FFF)
            raw[pc : pc + len(data)] = data
        put_preimage(0x1DBE44, bytes.fromhex("da a0 05 bf 3c be 1d aa"))
        put_preimage(0x1DC02A, bytes.fromhex("bd 90 0d 85 00 bd a0 0d"))
        put_preimage(0x1DC0F2, bytes.fromhex("da bd 3c be aa c2 20 64"))
        put_preimage(0x1DC1AA, bytes.fromhex("bd 00 0e 29 01 18 69 04"))

        cc_img = base / "cc.sfc"
        cc_img.write_bytes(raw)
        cc_asm = base / "cc.asm"
        cc_asm.write_text(
            f'lorom\norg $328000\nincsrc "{ROOT / "Sprites/Enemies/chain_chomp_opt.asm"}"\n',
            encoding="utf-8",
        )
        res = subprocess.run(
            ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(cc_asm), str(cc_img)],
            capture_output=True, text=True,
        )
        assert res.returncode == 0, res.stdout + res.stderr
        cls._cc_rom = cc_img.read_bytes()
        cls._cc_labels = {
            m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
            for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$", cc_img.with_suffix(".sym").read_text())
        }

        # Assemble Masks/gbc_form.asm LinkState_GameboyInDungeonEntrance
        gbc_src = (ROOT / "Masks" / "gbc_form.asm").read_text(encoding="utf-8")
        tunic_src = (ROOT / "Menu" / "menu_tunic.asm").read_text(encoding="utf-8")
        m0 = tunic_src.index("macro Tunic_Resolve")
        m1 = tunic_src.index("endmacro", m0) + len("endmacro")
        gbc_body = "\n".join([
            tunic_src[m0:m1],
            _extract_block(tunic_src, "Tunic_GetWorn"),
            _extract_block(gbc_src, "UpdateGbcPalette"),
            _extract_data_table(gbc_src, "GameboyLinkPalette"),
            _extract_data_table(gbc_src, "GameboyLinkBlueMail"),
            _extract_data_table(gbc_src, "GameboyLinkRedMail"),
            _extract_block(gbc_src, "LinkState_GameboyInDungeonEntrance"),
        ])
        gbc_img = base / "gbc.sfc"
        gbc_img.write_bytes(b"\xFF" * 0x200000)
        gbc_asm = base / "gbc.asm"
        gbc_asm.write_text(
            "lorom\n"
            "!CurrentMask = $02B2\n"
            "!SwordSlot_TunicMask = $38\n"
            "SwordSlotFlags = $7EF3BD\n"
            "Armor = $7EF35B\n"
            "SavedWorld = $7EF3CA\n"
            "LinkGraphics_ApplyD8Base = $018110\n"
            "ShieldWorld_SyncBoth = $018130\n"
            "org $2C8000\n" + gbc_body + "\n",
            encoding="utf-8",
        )
        res2 = subprocess.run(
            ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(gbc_asm), str(gbc_img)],
            capture_output=True, text=True,
        )
        assert res2.returncode == 0, res2.stdout + res2.stderr
        cls._gbc_rom = gbc_img.read_bytes()
        cls._gbc_labels = {
            m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
            for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$", gbc_img.with_suffix(".sym").read_text())
        }

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    def test_prep_all_16_slots_disjoint(self) -> None:
        f = ChainChompFixture(self._lib, self._cc_rom, self._cc_labels)
        try:
            for slot in range(16):
                x = 0x0900 + slot * 17
                y = 0x1100 + slot * 23
                f.word(0x0FD8, x)
                f.word(0x0FDA, y)
                f.put(0x0D10 + slot, x & 0xFF)
                f.put(0x0D30 + slot, x >> 8)
                f.put(0x0D00 + slot, y & 0xFF)
                f.put(0x0D20 + slot, y >> 8)
                f.run_jsl("ChainChomp_PrepLong", slot, db=0x06)

            for slot in range(16):
                x = 0x0900 + slot * 17
                y = 0x1100 + slot * 23
                xs, ys = f.read_links(slot)
                self.assertEqual(xs, [x] * 6, f"slot {slot} X corrupted")
                self.assertEqual(ys, [y] * 6, f"slot {slot} Y corrupted")
                self.assertEqual(f.get(0x0D90 + slot), x & 0xFF)
                self.assertEqual(f.get(0x0DA0 + slot), x >> 8)
                self.assertEqual(f.get(0x0DB0 + slot), y & 0xFF)
                self.assertEqual(f.get(0x0ED0 + slot), y >> 8)
        finally:
            f.close()

    def test_handle_leash_matches_vanilla_across_slots(self) -> None:
        cases = [
            (0,  0x0940, 0x1130, [0x0940, 0x0920, 0x0900, 0x0905, 0x0906, 0x08E0],
                                 [0x1130, 0x1150, 0x1152, 0x1170, 0x1120, 0x1120]),
            (9,  0x08B0, 0x1180, [0x08B0, 0x08C0, 0x08C8, 0x08D0, 0x08E0, 0x0900],
                                 [0x1180, 0x1178, 0x1170, 0x1168, 0x1160, 0x1158]),
            (15, 0x0010, 0x0010, [0x0010, 0x0008, 0x0000, 0xFFF8, 0xFFF0, 0xFFE8],
                                 [0x0010, 0x0019, 0x0022, 0x002B, 0x0034, 0x003D]),
        ]
        for slot, hx, hy, init_xs, init_ys in cases:
            f = ChainChompFixture(self._lib, self._cc_rom, self._cc_labels)
            try:
                f.write_links(slot, init_xs, init_ys)
                f.word(0x0FD8, hx)
                f.word(0x0FDA, hy)
                f.run_jsl("ChainChomp_HandleLeashLong", slot)
                got_x, got_y = f.read_links(slot)
                exp_x = _vanilla_clamp_axis([hx] + init_xs[1:])
                exp_y = _vanilla_clamp_axis([hy] + init_ys[1:])
                self.assertEqual(got_x, exp_x, f"slot {slot} leash X mismatch")
                self.assertEqual(got_y, exp_y, f"slot {slot} leash Y mismatch")
            finally:
                f.close()

    def test_move_chain_matches_vanilla_and_respects_hardware_mult_latency(self) -> None:
        cases = [
            # Positive dx, positive dy (slot 0)
            (0,  0x0900, 0x1100, 0x0930, 0x1128),
            # Negative dx, negative dy (slot 1)
            (1,  0x0900, 0x1100, 0x08D0, 0x10D4),
            # Positive dx, negative dy (slot 10 — vanilla overflowed into slot 0!)
            (10, 0x0900, 0x1100, 0x0924, 0x10E0),
            # Negative dx, positive dy (slot 15)
            (15, 0x0900, 0x1100, 0x08D8, 0x112E),
            # Zero delta (head == anchor)
            (8,  0x0900, 0x1100, 0x0900, 0x1100),
        ]
        for slot, ax, ay, hx, hy in cases:
            f = ChainChompFixture(self._lib, self._cc_rom, self._cc_labels)
            try:
                f.put(0x0D90 + slot, ax & 0xFF)
                f.put(0x0DA0 + slot, ax >> 8)
                f.put(0x0DB0 + slot, ay & 0xFF)
                f.put(0x0ED0 + slot, ay >> 8)
                init_xs = [hx, ax + 5, ax - 3, ax + 12, ax - 9, ax]
                init_ys = [hy, ay - 7, ay + 4, ay - 15, ay + 6, ay]
                f.write_links(slot, init_xs, init_ys)

                f.run_jsl("ChainChomp_MoveChainLong", slot)
                got_x, got_y = f.read_links(slot)
                exp_x = _vanilla_move_axis(init_xs, ax)
                exp_y = _vanilla_move_axis(init_ys, ay)
                self.assertEqual(got_x, exp_x, f"slot {slot} move X mismatch")
                self.assertEqual(got_y, exp_y, f"slot {slot} move Y mismatch")
                self.assertEqual(f.mult_reads, 10, "expected 10 hardware mult reads (5 X + 5 Y)")
                self.assertGreaterEqual(
                    f.min_mult_wait, 8,
                    f"SNES WRMPYB->RDMPYH wait {f.min_mult_wait} < 8 cycles!",
                )
            finally:
                f.close()

    def test_draw_links_bit_identical_oam_including_clipping_and_jitter(self) -> None:
        for slot, jitter, prio in ((0, 0, 0x20), (11, 1, 0x30)):
            f = ChainChompFixture(self._lib, self._cc_rom, self._cc_labels)
            try:
                cam_x, cam_y = 0x0880, 0x10C0
                # Mix on-screen, negative X (X-hi bit = 1), and off-screen Y (clipped to $F0)
                xs = [cam_x + 40, cam_x - 8, cam_x + 252, cam_x + 100, cam_x + 120, cam_x + 140]
                ys = [cam_y + 40, cam_y + 80, cam_y - 20, cam_y + 245, cam_y + 120, cam_y + 160]
                f.write_links(slot, xs, ys)
                f.word(0xE2, cam_x)
                f.word(0xE8, cam_y)
                f.word(0x90, 0x0800)
                f.word(0x92, 0x0A20)
                f.put(0x0E00 + slot, jitter)
                f.put(0x05, prio | 0x07)

                f.run_jsl("ChainChomp_DrawLinksLong", slot)
                off = 4 + (jitter & 1)
                want_attr = (prio & 0xF0) | 0x0D
                for i in range(6):
                    oam = 0x0800 + (i + 1) * 4
                    sx = (xs[i] + off - cam_x) & 0xFFFF
                    sy = (ys[i] + off - cam_y) & 0xFFFF
                    clipped_y = 0xF0 if ((sy + 0x10) & 0xFFFF) >= 0x0100 else (sy & 0xFF)
                    self.assertEqual(f.get(oam + 0), sx & 0xFF, f"link {i} X")
                    self.assertEqual(f.get(oam + 1), clipped_y, f"link {i} Y")
                    self.assertEqual(f.get(oam + 2), 0x8B, f"link {i} tile")
                    self.assertEqual(f.get(oam + 3), want_attr, f"link {i} attr")
                    self.assertEqual(f.get(0x0A20 + i + 1), (sx >> 8) & 1, f"link {i} X-hi")
            finally:
                f.close()

    def test_dungeon_gbc_hook_zero_per_frame_reloads(self) -> None:
        # 1. Light World dungeon: zero ShieldWorld_SyncBoth, zero UpdateGbcPalette, zero $15 bump
        f = ChainChompFixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {
            0x018110: "LinkGraphics_ApplyD8Base",
            0x018130: "ShieldWorld_SyncBoth",
            0x0AFE80: "Underworld_HandleLayerEffect",
        }
        try:
            f.put(0x7EF3CA, 0x00)
            f.put(0x02B2, 0x00)
            f.put(0x00BC, 0x10)
            f.put(0x0015, 0x00)
            f.cpu.c = False
            f.run_jsl("LinkState_GameboyInDungeonEntrance", 0, db=0x7E)
            self.assertNotIn("ShieldWorld_SyncBoth", f.calls)
            self.assertIn("Underworld_HandleLayerEffect", f.calls)
            self.assertEqual(f.get(0x0015), 0x00)
        finally:
            f.close()

        # 2. Dark World dungeon: frame 1 transitions and syncs ONCE; frame 2 does ZERO reloads!
        f = ChainChompFixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {
            0x018110: "LinkGraphics_ApplyD8Base",
            0x018130: "ShieldWorld_SyncBoth",
            0x0AFE80: "Underworld_HandleLayerEffect",
        }
        try:
            f.put(0x7EF3CA, 0x40)
            f.put(0x02B2, 0x00)
            f.put(0x00BC, 0x10)
            f.put(0x0015, 0x00)
            f.cpu.c = False
            f.run_jsl("LinkState_GameboyInDungeonEntrance", 0, db=0x7E, check_x=False)
            self.assertEqual((f.get(0x02B2), f.get(0x00BC)), (0x06, 0x3B))
            self.assertIn("ShieldWorld_SyncBoth", f.calls)
            self.assertEqual(f.get(0x0015), 0x01)

            # Steady-state frame 2: ZERO ShieldWorld_SyncBoth, ZERO $15 increment!
            f.calls.clear()
            f.cpu.c = False
            f.run_jsl("LinkState_GameboyInDungeonEntrance", 0, db=0x7E, check_x=False)
            self.assertNotIn("ShieldWorld_SyncBoth", f.calls)
            self.assertEqual(f.get(0x0015), 0x01)
            self.assertIn("Underworld_HandleLayerEffect", f.calls)
        finally:
            f.close()


if __name__ == "__main__":
    unittest.main()
