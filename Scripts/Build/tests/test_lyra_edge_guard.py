"""Compiled Asar + 65816 execution tests for Overworld/lyra_edge_guard.asm.

Covers all 64 Special Overworld maps ($80-$BF) across all 4 directions
(256 transitions), overlay hard-blocks ($93-$97, $9C-$9F), outer world edges,
East Kalyxo <-> Garrison / Sea Zora / Deku / Goron Desert links, multi-area
parent invariance ($8A, $8B, $98, $A9, $B9), and register/RAM preservation.
"""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / "Overworld" / "lyra_edge_guard.asm"
ASAR_BIN = os.environ.get("ASAR_BIN") or shutil.which("asar")

DIR_RIGHT = 0x00
DIR_LEFT = 0x02
DIR_DOWN = 0x04
DIR_UP = 0x06
DIRECTIONS = (DIR_RIGHT, DIR_LEFT, DIR_DOWN, DIR_UP)

BIT_RIGHT = 0x01
BIT_LEFT = 0x02
BIT_DOWN = 0x04
BIT_UP = 0x08

EXPECTED_PERMISSIONS: dict[int, int] = {
    # Row 0 ($80-$87)
    0x80: 0x00,
    0x81: BIT_RIGHT | BIT_DOWN,
    0x82: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0x83: BIT_LEFT | BIT_DOWN,
    0x84: 0x00,
    0x85: 0x00,
    0x86: 0x00,
    0x87: BIT_DOWN,
    # Row 1 ($88-$8F)
    0x88: 0x00,
    0x89: BIT_RIGHT | BIT_UP,
    0x8A: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0x8B: BIT_LEFT | BIT_UP,
    0x8C: BIT_RIGHT,
    0x8D: BIT_RIGHT | BIT_LEFT,
    0x8E: BIT_RIGHT | BIT_LEFT,
    0x8F: BIT_LEFT | BIT_UP,
    # Row 2 ($90-$97)
    0x90: BIT_DOWN,
    0x91: BIT_DOWN,
    0x92: BIT_UP,
    0x93: 0x00,
    0x94: 0x00,
    0x95: 0x00,
    0x96: 0x00,
    0x97: 0x00,
    # Row 3 ($98-$9F)
    0x98: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0x99: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0x9A: BIT_LEFT | BIT_DOWN,
    0x9B: 0x00,
    0x9C: 0x00,
    0x9D: 0x00,
    0x9E: 0x00,
    0x9F: 0x00,
    # Row 4 ($A0-$A7)
    0xA0: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xA1: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xA2: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xA3: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0xA4: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0xA5: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0xA6: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0xA7: BIT_LEFT | BIT_DOWN,
    # Row 5 ($A8-$AF)
    0xA8: BIT_RIGHT | BIT_LEFT | BIT_DOWN,
    0xA9: BIT_LEFT | BIT_DOWN,
    0xAA: BIT_RIGHT | BIT_DOWN | BIT_UP,
    0xAB: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xAC: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xAD: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xAE: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xAF: BIT_LEFT | BIT_DOWN | BIT_UP,
    # Row 6 ($B0-$B7)
    0xB0: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB1: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB2: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB3: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB4: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB5: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB6: BIT_RIGHT | BIT_LEFT | BIT_DOWN | BIT_UP,
    0xB7: BIT_LEFT | BIT_DOWN | BIT_UP,
    # Row 7 ($B8-$BF)
    0xB8: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xB9: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBA: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBB: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBC: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBD: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBE: BIT_RIGHT | BIT_LEFT | BIT_UP,
    0xBF: BIT_LEFT | BIT_UP,
}


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def assemble_guard(directory: Path) -> tuple[bytes, dict[str, int]]:
    rom_path = directory / "probe.sfc"
    asm_path = directory / "probe.asm"
    sym_path = directory / "probe.sym"
    rom_path.write_bytes(bytes(0x400000))
    asm_path.write_text(
        "lorom\n"
        "!LYRA_CURRENT_FIRST = $00A0\n"
        "!LYRA_CURRENT_END = $00C0\n"
        "org $07F439\n"
        "Vanilla_PermitStub:\n"
        "  CLC\n"
        "  RTL\n"
        "org $348000\n"
        f'incsrc "{SOURCE}"\n'
        "EdgeGuardEnd:\n",
        encoding="utf-8",
    )
    proc = subprocess.run(
        [
            ASAR_BIN,
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"--symbols-path={sym_path}",
            str(asm_path),
            str(rom_path),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(f"asar failed:\n{proc.stdout}\n{proc.stderr}")
    labels: dict[str, int] = {}
    for bank, offset, name in re.findall(
        r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+([A-Za-z0-9_.:]+)$",
        sym_path.read_text(encoding="utf-8"),
        re.M,
    ):
        labels[name] = (int(bank, 16) << 16) | int(offset, 16)
    return rom_path.read_bytes(), labels


def _run_65816(
    rom: bytearray,
    entry: int,
    wram: bytearray,
    *,
    a: int = 0x37,
    x: int = 0x55,
    y: int = 0x00,
    p: int = 0x31,  # M=1 (bit 5), X=1 (bit 4), C=1
    db: int = 0x7E,
    dp: int = 0x0000,
    max_steps: int = 128,
) -> dict[str, int]:
    """Execute the compiled 65816 instructions at `entry` against `rom` & `wram`."""
    pc = entry
    sp = 0x1FFF
    stack = bytearray(0x2000)

    def rd8(addr: int) -> int:
        bank = (addr >> 16) & 0xFF
        off = addr & 0xFFFF
        if bank in (0x7E, 0x7F):
            return wram[((bank & 1) << 16) | off]
        if off < 0x2000:
            return wram[off]
        return rom[snes_to_pc(addr)]

    def wr8(addr: int, val: int) -> None:
        bank = (addr >> 16) & 0xFF
        off = addr & 0xFFFF
        val &= 0xFF
        if bank in (0x7E, 0x7F):
            wram[((bank & 1) << 16) | off] = val
        elif off < 0x2000:
            wram[off] = val
        else:
            raise AssertionError(f"Unexpected write to ${addr:06X}")

    def rd16(addr: int) -> int:
        return rd8(addr) | (rd8((addr & 0xFF0000) | ((addr + 1) & 0xFFFF)) << 8)

    def wr16(addr: int, val: int) -> None:
        wr8(addr, val & 0xFF)
        wr8((addr & 0xFF0000) | ((addr + 1) & 0xFFFF), (val >> 8) & 0xFF)

    def set_nz8(val: int) -> None:
        nonlocal p
        val &= 0xFF
        p = (p & ~0x82) | (0x80 if (val & 0x80) else 0) | (0x02 if val == 0 else 0)

    def set_nz16(val: int) -> None:
        nonlocal p
        val &= 0xFFFF
        p = (p & ~0x82) | (0x80 if (val & 0x8000) else 0) | (0x02 if val == 0 else 0)

    def fetch8() -> int:
        nonlocal pc
        v = rd8(pc)
        pc = (pc & 0xFF0000) | ((pc + 1) & 0xFFFF)
        return v

    def fetch16() -> int:
        lo = fetch8()
        hi = fetch8()
        return lo | (hi << 8)

    def fetch24() -> int:
        lo = fetch8()
        hi = fetch8()
        bk = fetch8()
        return lo | (hi << 8) | (bk << 16)

    def branch(cond: bool) -> None:
        nonlocal pc
        rel = fetch8()
        if rel & 0x80:
            rel -= 0x100
        if cond:
            pc = (pc & 0xFF0000) | ((pc + rel) & 0xFFFF)

    for _ in range(max_steps):
        op = fetch8()
        m8 = bool(p & 0x20)
        x8 = bool(p & 0x10)
        if op == 0x22:  # JSL
            target = fetch24()
            ret = (pc - 1) & 0xFFFF
            stack[sp] = (pc >> 16) & 0xFF; sp -= 1
            stack[sp] = (ret >> 8) & 0xFF; sp -= 1
            stack[sp] = ret & 0xFF; sp -= 1
            pc = target
        elif op == 0x6B:  # RTL
            if sp == 0x1FFF:
                return {"a": a, "x": x, "y": y, "p": p, "db": db, "dp": dp}
            sp += 1; lo = stack[sp]
            sp += 1; hi = stack[sp]
            sp += 1; bk = stack[sp]
            pc = (bk << 16) | (((lo | (hi << 8)) + 1) & 0xFFFF)
        elif op == 0x18:  # CLC
            p &= ~0x01
        elif op == 0x38:  # SEC
            p |= 0x01
        elif op == 0xC2:  # REP
            p &= (~fetch8()) & 0xFF
        elif op == 0xE2:  # SEP
            p |= fetch8()
        elif op == 0xB0:  # BCS
            branch(bool(p & 0x01))
        elif op == 0x90:  # BCC
            branch(not (p & 0x01))
        elif op == 0xD0:  # BNE
            branch(not (p & 0x02))
        elif op == 0xF0:  # BEQ
            branch(bool(p & 0x02))
        elif op == 0x80:  # BRA
            branch(True)
        elif op == 0xDA:  # PHX
            assert x8
            stack[sp] = x & 0xFF; sp -= 1
        elif op == 0xFA:  # PLX
            assert x8
            sp += 1; x = stack[sp]
            set_nz8(x)
        elif op == 0xBB:  # TYX
            assert x8
            x = y & 0xFF
            set_nz8(x)
        elif op == 0xAA:  # TAX
            assert x8
            x = a & 0xFF
            set_nz8(x)
        elif op == 0x4A:  # LSR A
            assert m8
            p = (p & ~0x01) | (a & 0x01)
            a = (a >> 1) & 0x7F
            set_nz8(a)
        elif op == 0x29:  # AND #imm
            assert m8
            a = (a & fetch8()) & 0xFF
            set_nz8(a)
        elif op == 0xA9:  # LDA #imm
            if m8:
                a = fetch8()
                set_nz8(a)
            else:
                a = fetch16()
                set_nz16(a)
        elif op == 0xC9:  # CMP #imm
            assert m8
            imm = fetch8()
            diff = (a & 0xFF) - imm
            p = (p & ~0x01) | (1 if (a & 0xFF) >= imm else 0)
            set_nz8(diff)
        elif op == 0xA5:  # LDA dp
            off = (dp + fetch8()) & 0xFFFF
            if m8:
                a = rd8(off)
                set_nz8(a)
            else:
                a = rd16(off)
                set_nz16(a)
        elif op == 0x85:  # STA dp
            off = (dp + fetch8()) & 0xFFFF
            if m8:
                wr8(off, a)
            else:
                wr16(off, a)
        elif op == 0x64:  # STZ dp
            off = (dp + fetch8()) & 0xFFFF
            if m8:
                wr8(off, 0)
            else:
                wr16(off, 0)
        elif op == 0xAF:  # LDA long
            addr = fetch24()
            if m8:
                a = rd8(addr)
                set_nz8(a)
            else:
                a = rd16(addr)
                set_nz16(a)
        elif op == 0xBF:  # LDA long, X
            addr = fetch24() + (x & (0xFF if x8 else 0xFFFF))
            if m8:
                a = rd8(addr)
                set_nz8(a)
            else:
                a = rd16(addr)
                set_nz16(a)
        elif op == 0x3F:  # AND long, X
            assert m8
            addr = fetch24() + (x & (0xFF if x8 else 0xFFFF))
            a = (a & rd8(addr)) & 0xFF
            set_nz8(a)
        else:
            raise AssertionError(f"Unhandled opcode ${op:02X} at ${(pc - 1):06X}")
    raise AssertionError("Instruction limit exceeded")


@unittest.skipUnless(ASAR_BIN, "asar required")
class LyraEdgeGuardTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.tmp = tempfile.TemporaryDirectory()
        cls.rom, cls.labels = assemble_guard(Path(cls.tmp.name))

    @classmethod
    def tearDownClass(cls) -> None:
        cls.tmp.cleanup()

    def _call(
        self,
        *,
        area8a: int,
        phys_map: int,
        direction: int,
        vanilla_block: bool = False,
        x_in: int = 0x55,
    ) -> tuple[dict[str, int], bytearray]:
        rom = bytearray(self.rom)
        if vanilla_block:
            # SEC : RTL at $07F439
            pc = snes_to_pc(0x07F439)
            rom[pc:pc + 2] = bytes((0x38, 0x6B))
        wram = bytearray(0x20000)
        wram[0x8A] = area8a & 0xFF
        wram[0x27] = 0x11
        wram[0x28] = 0xEE
        wram[0x22:0x24] = (0x1234).to_bytes(2, "little")
        wram[0x20:0x22] = (0x5678).to_bytes(2, "little")
        wram[0x0FC2:0x0FC4] = (0x1110).to_bytes(2, "little")
        wram[0x0FC4:0x0FC6] = (0x2220).to_bytes(2, "little")
        if 0x80 <= phys_map <= 0xBF:
            cell2 = (phys_map & 0x3F) * 2
            wram[0x0700:0x0702] = cell2.to_bytes(2, "little")
        res = _run_65816(
            rom,
            self.labels["LyraEdgeGuard"],
            wram,
            x=x_in,
            y=direction,
            db=0x02,  # non-program bank to prove long table reads
            dp=0x0000,
        )
        return res, wram

    def test_all_64_special_maps_all_4_directions(self) -> None:
        dir_bits = (BIT_RIGHT, BIT_LEFT, BIT_DOWN, BIT_UP)
        for phys in range(0x80, 0xC0):
            expected_mask = EXPECTED_PERMISSIONS[phys]
            for d, bit in zip(DIRECTIONS, dir_bits):
                should_allow = bool(expected_mask & bit)
                with self.subTest(phys=f"${phys:02X}", direction=d):
                    res, wram = self._call(area8a=phys, phys_map=phys, direction=d, x_in=0x00)
                    self.assertEqual(res["p"] & 0x30, 0x30, "M=8/X=8 corrupted")
                    self.assertEqual(res["x"], 0x00, "X corrupted (tested with 0x00)")
                    self.assertEqual(res["y"], d, "Y corrupted")
                    self.assertEqual(res["db"], 0x02, "DBR corrupted")
                    if should_allow:
                        self.assertEqual(res["p"] & 0x01, 0, f"${phys:02X} dir {d} unexpectedly blocked")
                        self.assertEqual((wram[0x27], wram[0x28]), (0x11, 0xEE))
                        self.assertEqual(int.from_bytes(wram[0x22:0x24], "little"), 0x1234)
                        self.assertEqual(int.from_bytes(wram[0x20:0x22], "little"), 0x5678)
                    else:
                        self.assertEqual(res["p"] & 0x01, 1, f"${phys:02X} dir {d} unexpectedly allowed")
                        self.assertEqual((wram[0x27], wram[0x28]), (0x00, 0x00))
                        self.assertEqual(int.from_bytes(wram[0x22:0x24], "little"), 0x1110)
                        self.assertEqual(int.from_bytes(wram[0x20:0x22], "little"), 0x2220)

    def test_overlay_curtain_and_outer_edges_hard_blocked(self) -> None:
        overlays = (0x93, 0x94, 0x95, 0x96, 0x97, 0x9C, 0x9D, 0x9E, 0x9F)
        hard_zero = overlays + (0x80, 0x84, 0x85, 0x86, 0x88, 0x9B)
        cross_world_col0 = (0x98, 0xA0, 0xA8, 0xB0, 0xB8)
        for m in hard_zero:
            for d in DIRECTIONS:
                self.assertEqual(EXPECTED_PERMISSIONS[m] & (1 << (d // 2)), 0, f"${m:02X} d={d}")
        for m in range(0x80, 0xC0):
            r, c = (m - 0x80) >> 3, (m - 0x80) & 7
            if r == 0:
                self.assertFalse(EXPECTED_PERMISSIONS[m] & BIT_UP, f"North of ${m:02X} open")
            if r == 7:
                self.assertFalse(EXPECTED_PERMISSIONS[m] & BIT_DOWN, f"South of ${m:02X} open")
            if c == 0:
                if m in cross_world_col0:
                    self.assertTrue(EXPECTED_PERMISSIONS[m] & BIT_LEFT, f"Cross-world West of ${m:02X} closed")
                else:
                    self.assertFalse(EXPECTED_PERMISSIONS[m] & BIT_LEFT, f"West of ${m:02X} open")
            if c == 7:
                self.assertFalse(EXPECTED_PERMISSIONS[m] & BIT_RIGHT, f"East of ${m:02X} open")
            # No allowed transition may step onto a hard-zero overlay/indoor/unused map.
            neighbors = (
                (BIT_RIGHT, m + 1 if c < 7 else None),
                (BIT_LEFT, m - 1 if c > 0 else None),
                (BIT_DOWN, m + 8 if r < 7 else None),
                (BIT_UP, m - 8 if r > 0 else None),
            )
            for bit, nb in neighbors:
                if EXPECTED_PERMISSIONS[m] & bit:
                    if bit == BIT_LEFT and m in cross_world_col0:
                        continue
                    self.assertIsNotNone(nb)
                    self.assertNotIn(nb, hard_zero, f"${m:02X} leaks into ${nb:02X}")

    def test_bidirectional_kalyxo_and_garrison_links(self) -> None:
        links = [
            # Korok Cove <-> Garrison Tall & North Reef ($92)
            (0x82, DIR_RIGHT, 0x83, DIR_LEFT),
            (0x8A, DIR_RIGHT, 0x8B, DIR_LEFT),
            (0x8A, DIR_DOWN, 0x92, DIR_UP),
            (0x83, DIR_DOWN, 0x8B, DIR_UP),
            # Sea Zora <-> Zora Quay <-> Zora Coast <-> Lyra Sea
            (0x90, DIR_DOWN, 0x98, DIR_UP),
            (0x91, DIR_DOWN, 0x99, DIR_UP),
            (0x98, DIR_RIGHT, 0x99, DIR_LEFT),
            (0x98, DIR_DOWN, 0xA0, DIR_UP),
            (0x99, DIR_DOWN, 0xA1, DIR_UP),
            (0x99, DIR_RIGHT, 0x9A, DIR_LEFT),
            (0xA0, DIR_RIGHT, 0xA1, DIR_LEFT),
            (0xA1, DIR_RIGHT, 0xA2, DIR_LEFT),
            # Deku Wide <-> Goron Desert Large <-> Lyra Sea Harbor
            (0xA8, DIR_RIGHT, 0xA9, DIR_LEFT),
            (0xA8, DIR_DOWN, 0xB0, DIR_UP),
            (0xA9, DIR_DOWN, 0xB1, DIR_UP),
            (0xB1, DIR_RIGHT, 0xB2, DIR_LEFT),
            (0xB9, DIR_RIGHT, 0xBA, DIR_LEFT),
            # Sky Chain <-> D8 Tower
            (0x8C, DIR_RIGHT, 0x8D, DIR_LEFT),
            (0x8D, DIR_RIGHT, 0x8E, DIR_LEFT),
            (0x8E, DIR_RIGHT, 0x8F, DIR_LEFT),
            (0x8F, DIR_UP, 0x87, DIR_DOWN),
        ]
        for a, da, b, db in links:
            ra, _ = self._call(area8a=a, phys_map=a, direction=da)
            rb, _ = self._call(area8a=b, phys_map=b, direction=db)
            self.assertEqual(ra["p"] & 1, 0, f"${a:02X} d={da} should be open")
            self.assertEqual(rb["p"] & 1, 0, f"${b:02X} d={db} should be open")

    def test_multi_area_parent_uses_0700_physical_map(self) -> None:
        # Standing on $8A (parent=$81): East into $8B allowed, South into $92 allowed
        res_east, _ = self._call(area8a=0x81, phys_map=0x8A, direction=DIR_RIGHT)
        res_south, _ = self._call(area8a=0x81, phys_map=0x8A, direction=DIR_DOWN)
        self.assertEqual(res_east["p"] & 1, 0)
        self.assertEqual(res_south["p"] & 1, 0)
        # Standing on $92 (North Reef): North to $8A allowed, West/South/East blocked
        self.assertEqual(self._call(area8a=0x92, phys_map=0x92, direction=DIR_UP)[0]["p"] & 1, 0)
        for d in (DIR_RIGHT, DIR_LEFT, DIR_DOWN):
            self.assertEqual(self._call(area8a=0x92, phys_map=0x92, direction=d)[0]["p"] & 1, 1)

        # Standing on $8B (parent=$83): East into $8C blocked, South into $93 overlay blocked
        for d in (DIR_RIGHT, DIR_DOWN):
            res, _ = self._call(area8a=0x83, phys_map=0x8B, direction=d)
            self.assertEqual(res["p"] & 1, 1)

        # Standing on $A9 (parent=$A8): North into $A1 blocked, East into $AA blocked, South into $B1 allowed
        self.assertEqual(self._call(area8a=0xA8, phys_map=0xA9, direction=DIR_UP)[0]["p"] & 1, 1)
        self.assertEqual(self._call(area8a=0xA8, phys_map=0xA9, direction=DIR_RIGHT)[0]["p"] & 1, 1)
        self.assertEqual(self._call(area8a=0xA8, phys_map=0xA9, direction=DIR_DOWN)[0]["p"] & 1, 0)

    def test_outside_special_overworld_and_vanilla_passthrough(self) -> None:
        for area in (0x00, 0x3F, 0x40, 0x7F, 0xC0):
            for d in DIRECTIONS:
                res, _ = self._call(area8a=area, phys_map=0x88, direction=d)
                self.assertEqual(res["p"] & 1, 0)
        res, _ = self._call(area8a=0x99, phys_map=0x99, direction=DIR_RIGHT, vanilla_block=True)
        self.assertEqual(res["p"] & 1, 1)


if __name__ == "__main__":
    unittest.main()
