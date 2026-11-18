#!/usr/bin/env python3
"""Compiled 65816 & contract unit tests for Items/mirror_shield_palette.asm."""
from __future__ import annotations

import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASM_PATH = ROOT / "Items" / "mirror_shield_palette.asm"


def pc(address: int) -> int:
    bank = (address >> 16) & 0x7F
    assert address & 0x8000, f"Expected LoROM address, got ${address:06X}"
    return bank * 0x8000 + (address & 0x7FFF)


def encode_tile_from_pixels(pixels: list[int]) -> bytes:
    """Encode 64 4bpp pixel values (0..15) into 32 SNES 4bpp tile bytes."""
    assert len(pixels) == 64
    out = bytearray(32)
    for y in range(8):
        bp0 = bp1 = bp2 = bp3 = 0
        for x in range(8):
            c = pixels[y * 8 + x]
            bit = 1 << (7 - x)
            if c & 1:
                bp0 |= bit
            if c & 2:
                bp1 |= bit
            if c & 4:
                bp2 |= bit
            if c & 8:
                bp3 |= bit
        out[y * 2] = bp0
        out[y * 2 + 1] = bp1
        out[16 + y * 2] = bp2
        out[16 + y * 2 + 1] = bp3
    return bytes(out)


def decode_tile_pixels(raw: bytes) -> list[int]:
    """Decode 32 SNES 4bpp bytes into 64 4bpp pixel values (0..15)."""
    assert len(raw) == 32
    pixels: list[int] = []
    for y in range(8):
        bp0, bp1 = raw[y * 2], raw[y * 2 + 1]
        bp2, bp3 = raw[16 + y * 2], raw[16 + y * 2 + 1]
        for x in range(8):
            sh = 7 - x
            pixels.append(
                ((bp0 >> sh) & 1)
                | (((bp1 >> sh) & 1) << 1)
                | (((bp2 >> sh) & 1) << 2)
                | (((bp3 >> sh) & 1) << 3)
            )
    return pixels


class Mini65816:
    """Minimal deterministic 65816 executor for compiled ASM hook routines."""

    def __init__(self, rom: bytes, a: int = 0, x: int = 0, y: int = 0, p: int = 0x30, db: int = 0, d: int = 0):
        self.rom = rom
        self.a = a
        self.x = x
        self.y = y
        self.p = p
        self.db = db
        self.d = d
        self.mem: dict[int, int] = {}
        self.stack: list[int] = []
        self.pc = 0
        self.calls: list[int] = []
        self.stubs: dict[int, callable] = {}

    def put(self, addr: int, val: int, size: int = 1) -> None:
        for i in range(size):
            self.mem[addr + i] = (val >> (8 * i)) & 0xFF

    def put_bytes(self, addr: int, data: bytes) -> None:
        for i, b in enumerate(data):
            self.mem[addr + i] = b

    def read(self, addr: int, size: int = 1) -> int:
        val = 0
        for i in range(size):
            cur = addr + i
            if cur in self.mem:
                b = self.mem[cur]
            else:
                bank, off = cur >> 16, cur & 0xFFFF
                if (bank & 0x7F) < 0x40 and off >= 0x8000:
                    b = self.rom[((bank & 0x7F) * 0x8000) + (off & 0x7FFF)]
                else:
                    b = 0
            val |= b << (8 * i)
        return val

    def read_bytes(self, addr: int, length: int) -> bytes:
        return bytes(self.read(addr + i, 1) for i in range(length))

    def push(self, val: int, size: int) -> None:
        for i in range(size - 1, -1, -1):
            self.stack.append((val >> (8 * i)) & 0xFF)

    def pop(self, size: int) -> int:
        val = 0
        for i in range(size):
            val |= self.stack.pop() << (8 * i)
        return val

    def take(self, size: int = 1) -> int:
        val = self.read(self.pc, size)
        self.pc += size
        return val

    def nz(self, val: int, size: int) -> None:
        mask = (1 << (8 * size)) - 1
        top = 1 << (8 * size - 1)
        masked = val & mask
        self.p = (self.p & ~0x82) | (0x80 if (masked & top) else 0) | (0x02 if masked == 0 else 0)

    def load_a(self, val: int) -> None:
        if self.p & 0x20:
            self.a = (self.a & 0xFF00) | (val & 0xFF)
            self.nz(val, 1)
        else:
            self.a = val & 0xFFFF
            self.nz(val, 2)

    def run(self, start: int, stops: set[int], limit: int = 20000) -> None:
        self.pc = start
        for _ in range(limit):
            if self.pc in stops:
                return
            if self.pc in self.stubs:
                self.calls.append(self.pc)
                self.stubs[self.pc](self)
                continue
            op = self.take()
            m = 1 if (self.p & 0x20) else 2
            ix = 1 if (self.p & 0x10) else 2
            xmask = (1 << (8 * ix)) - 1
            mmask = (1 << (8 * m)) - 1
            if op == 0xC2:  # REP
                self.p &= ~self.take()
            elif op == 0xE2:  # SEP
                self.p |= self.take()
                if self.p & 0x10:
                    self.x &= 0xFF
                    self.y &= 0xFF
            elif op == 0xA9:  # LDA #imm
                self.load_a(self.take(m))
            elif op == 0xA2:  # LDX #imm
                self.x = self.take(ix)
                self.nz(self.x, ix)
            elif op == 0xA0:  # LDY #imm
                self.y = self.take(ix)
                self.nz(self.y, ix)
            elif op == 0xA5:  # LDA dp
                self.load_a(self.read(self.d + self.take(), m))
            elif op == 0x85:  # STA dp
                addr = self.d + self.take()
                self.put(addr, self.a, m)
            elif op == 0xAF:  # LDA long
                self.load_a(self.read(self.take(3), m))
            elif op == 0xBF:  # LDA long,X
                self.load_a(self.read(self.take(3) + (self.x & xmask), m))
            elif op == 0x8F:  # STA long
                self.put(self.take(3), self.a, m)
            elif op == 0x9F:  # STA long,X
                self.put(self.take(3) + (self.x & xmask), self.a, m)
            elif op == 0x29:  # AND #imm
                self.load_a((self.a & mmask) & self.take(m))
            elif op == 0x09:  # ORA #imm
                self.load_a((self.a & mmask) | self.take(m))
            elif op == 0x3F:  # AND long,X
                self.load_a((self.a & mmask) & self.read(self.take(3) + (self.x & xmask), m))
            elif op == 0xC9:  # CMP #imm
                v = self.take(m)
                lhs = self.a & mmask
                self.p = (self.p & ~1) | int(lhs >= v)
                self.nz(lhs - v, m)
            elif op == 0x18:  # CLC
                self.p &= ~1
            elif op == 0x69:  # ADC #imm
                v = self.take(m)
                lhs = self.a & mmask
                tot = lhs + v + (self.p & 1)
                self.p = (self.p & ~0x41) | int(tot > mmask) | (0x40 if ~(lhs ^ v) & (lhs ^ tot) & (mmask + 1 >> 1) else 0)
                self.load_a(tot & mmask)
            elif op == 0xD0:  # BNE
                off = self.take()
                off -= 256 if off >= 128 else 0
                if not (self.p & 2):
                    self.pc += off
            elif op == 0xE6:  # INC dp
                addr = self.d + self.take()
                v = (self.read(addr, m) + 1) & mmask
                self.put(addr, v, m)
                self.nz(v, m)
            elif op == 0xE8:  # INX
                self.x = (self.x + 1) & xmask
                self.nz(self.x, ix)
            elif op == 0x88:  # DEY
                self.y = (self.y - 1) & xmask
                self.nz(self.y, ix)
            elif op == 0x8A:  # TXA
                self.load_a(self.x & xmask)
            elif op == 0xAA:  # TAX
                self.x = self.a & xmask
                self.nz(self.x, ix)
            elif op == 0xEB:  # XBA
                lo, hi = self.a & 0xFF, (self.a >> 8) & 0xFF
                self.a = (lo << 8) | hi
                self.nz(hi, 1)
            elif op == 0x5A:  # PHY
                self.push(self.y & xmask, ix)
            elif op == 0x7A:  # PLY
                self.y = self.pop(ix)
                self.nz(self.y, ix)
            elif op == 0xAB:  # PLB
                self.db = self.pop(1)
                self.nz(self.db, 1)
            elif op == 0x20:  # JSR abs
                target = self.take(2)
                self.push((self.pc - 1) & 0xFFFF, 2)
                self.pc = (self.pc & 0xFF0000) | target
            elif op == 0x60:  # RTS
                self.pc = (self.pc & 0xFF0000) | ((self.pop(2) + 1) & 0xFFFF)
            elif op == 0x22:  # JSL
                target = self.take(3)
                self.push(self.pc - 1, 3)
                self.pc = target
            elif op == 0x5C:  # JML
                self.pc = self.take(3)
            elif op == 0x6B:  # RTL
                self.pc = self.pop(3) + 1
            elif op == 0xEA:  # NOP
                pass
            else:
                raise AssertionError(f"Unsupported opcode ${op:02X} at ${self.pc - 1:06X}")
        raise AssertionError("CPU step limit reached")


class MirrorShieldPaletteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asm_bin = os.environ.get("ASAR_BIN") or shutil.which("z3asm") or shutil.which("asar")
        if not cls.asm_bin:
            raise unittest.SkipTest("z3asm or asar is required")
        cls.temp = tempfile.TemporaryDirectory(prefix="oos-mirror-shield-unit-")
        cls.addClassCleanup(cls.temp.cleanup)
        tmp = Path(cls.temp.name)
        src = tmp / "harness.asm"
        rom_path = tmp / "harness.sfc"
        sym_path = tmp / "harness.sym"
        rom_path.write_bytes(b"\x00" * 0x200000)
        src.write_text(
            "lorom\n"
            "!DISABLE_OVERWORLD = 0\n"
            "Shield = $7EF35A\n"
            "PALB_SPR5B = $7EC4B0\n"
            "PAL_SPR5B = $7EC6B0\n"
            "LoadDayNightPaletteEffect = $348000\n"
            "org $2BD000\n"
            f'incsrc "{ASM_PATH}"\n',
            encoding="utf-8",
        )
        args = [cls.asm_bin]
        if "z3asm" not in Path(cls.asm_bin).name:
            args += ["--no-title-check", "--fix-checksum=off"]
        args += ["--symbols=wla", f"--symbols-path={sym_path}", str(src), str(rom_path)]
        res = subprocess.run(args, capture_output=True, text=True)
        if res.returncode != 0:
            raise AssertionError(res.stdout + res.stderr)
        cls.rom = rom_path.read_bytes()
        cls.labels = {
            m[3]: int(m[1] + m[2], 16)
            for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)\s*$", sym_path.read_text())
        }

    def test_hook_annotations_and_rom_bytes(self) -> None:
        text = ASM_PATH.read_text(encoding="utf-8")
        for line_tag in (
            "org $1BD658 ; @hook module=Items name=PaletteData_ShieldMirror kind=data protected_size=8",
            "org $1BED4A ; @hook module=Items name=MirrorShield_LoadColor8 kind=jml target=MirrorShield_LoadColor8 expected_m=16 expected_x=16 protected_size=5",
            "org $0ED73C ; @hook module=Items name=MirrorShield_RefreshColor8 kind=jml target=MirrorShield_RefreshColor8 expected_m=16 expected_x=16 protected_size=5",
            "org $00D333 ; @hook module=Items name=MirrorShield_RemapEquippedWRAM kind=jml target=MirrorShield_RemapEquippedWRAM expected_m=16 expected_x=16 protected_size=4",
            "org $00D510 ; @hook module=Items name=MirrorShield_CaptureItemId kind=jsl target=MirrorShield_CaptureItemId expected_m=8 expected_x=8 expected_exit_m=16 expected_exit_x=8 protected_size=5",
            "org $00D533 ; @hook module=Items name=MirrorShield_RemapPickupWRAM kind=jml target=MirrorShield_RemapPickupWRAM expected_m=16 expected_x=16 protected_size=4",
        ):
            self.assertIn(line_tag, text)
        pal_words = [
            int.from_bytes(self.rom[pc(0x1BD658) + i * 2 : pc(0x1BD658) + i * 2 + 2], "little")
            for i in range(4)
        ]
        self.assertEqual(pal_words, [0x373C, 0x18A5, 0x7FFE, 0x5589])
        self.assertEqual(self.rom[pc(0x1BED4A) + 4], 0xEA)
        self.assertEqual(self.rom[pc(0x0ED73C) + 4], 0xEA)
        self.assertEqual(self.rom[pc(0x00D510) + 4], 0xEA)

    def test_color8_load_and_refresh_hooks(self) -> None:
        def stub_day_night(cpu: Mini65816) -> None:
            self.assertEqual(cpu.p & 0x30, 0x00)
            self.assertEqual(cpu.a, 0x7B13)
            self.assertEqual(cpu.x, 0x01B0)
            tinted = 0x6A0B  # simulated midnight tint
            cpu.put(0x7EC300 + cpu.x, tinted, 2)
            cpu.a = tinted
            cpu.pc = cpu.pop(3) + 1

        for shield in (0, 1, 2, 3):
            cpu = Mini65816(self.rom, p=0x00)
            cpu.stubs[0x348000] = stub_day_night
            cpu.put(0x7EF35A, shield, 1)
            cpu.put(0x7EC4B0, 0x1234, 2)
            cpu.put(0x7EC6B0, 0x5678, 2)
            cpu.put(0x15, 4, 1)
            cpu.push(0x02FFEF, 3)
            cpu.run(self.labels["MirrorShield_LoadColor8"], {0x02FFF0})
            self.assertEqual(cpu.p & 0x30, 0x30)
            self.assertEqual(cpu.read(0x15, 1), 5)
            expected = 0x6A0B if shield == 3 else None
            if shield == 3:
                self.assertEqual(cpu.read(0x7EC4B0, 2), expected)
                self.assertEqual(cpu.read(0x7EC6B0, 2), expected)
                self.assertEqual(cpu.calls, [0x348000])
            else:
                self.assertEqual(cpu.read(0x7EC4B0, 2), 0x1234)
                self.assertEqual(cpu.read(0x7EC6B0, 2), 0x5678)
                self.assertEqual(cpu.calls, [])

        # Refresh hook inspects DP $0D so zap state ($0D=2) does not override with C8
        for dp_0d in (0, 1, 2, 3, 4):
            cpu = Mini65816(self.rom, p=0x00)
            cpu.stubs[0x348000] = stub_day_night
            cpu.put(0x0D, dp_0d, 1)
            cpu.put(0x7EF35A, 3, 1)
            cpu.put(0x7EC4B0, 0x1111, 2)
            cpu.put(0x7EC6B0, 0x2222, 2)
            cpu.put(0x15, 9, 1)
            cpu.push(0x07FFEF, 3)
            cpu.run(self.labels["MirrorShield_RefreshColor8"], {0x07FFF0})
            self.assertEqual(cpu.p & 0x30, 0x30)
            self.assertEqual(cpu.read(0x15, 1), 10)
            self.assertEqual(cpu.read(0x7EC6B0, 2), 0x6A0B if dp_0d == 3 else 0x2222)

    def test_capture_item_id_abi(self) -> None:
        for item_id in (0x00, 0x06, 0x20, 0x2D, 0x2E, 0x39, 0xFF):
            for entry_p in (0x30, 0x31, 0xB1):
                cpu = Mini65816(self.rom, a=0xAB00 | item_id, x=0x44, y=0x55, p=entry_p)
                cpu.push(0x00D513, 3)
                cpu.run(self.labels["MirrorShield_CaptureItemId"], {0x00D514})
                self.assertEqual(cpu.p & 0x31, 0x10)  # M=16 (bit 0x20 clear), X=8 (bit 0x10 set), C=0
                self.assertEqual(cpu.a, item_id)
                self.assertEqual(cpu.read(0x0A, 2), item_id)
                self.assertEqual((cpu.x, cpu.y), (0x44, 0x55))

    def test_equipped_and_pickup_wram_remap_exact(self) -> None:
        # Construct 64 pixels containing every valid 4bpp value produced by RightPal ({0, 10, 12, 13, 14, 15})
        pattern = ([0, 10, 12, 13, 14, 15, 8, 10] * 8)[:64]
        tile = encode_tile_from_pixels(pattern)
        expected_pixels = [8 if c == 10 else c for c in pattern]

        for shield in (1, 2, 3):
            cpu = Mini65816(self.rom, p=0x00, db=0x00)
            cpu.put(0x7EF35A, shield, 1)
            cpu.put_bytes(0x7E9300, tile * 2)
            cpu.put_bytes(0x7E9340, tile * 4)  # untouched non-front block
            cpu.put_bytes(0x7E93C0, tile * 2)
            cpu.put(0x7E92FF, 0xA5, 1)
            cpu.put(0x7E9400, 0x5A, 1)
            cpu.push(0x09FFEF, 3)  # caller JSL return address
            cpu.push(0x1B, 1)      # saved caller DBR popped by PLB
            cpu.run(self.labels["MirrorShield_RemapEquippedWRAM"], {0x09FFF0})
            self.assertEqual((cpu.p & 0x30, cpu.db, cpu.stack), (0x30, 0x1B, []))
            self.assertEqual((cpu.read(0x7E92FF, 1), cpu.read(0x7E9400, 1)), (0xA5, 0x5A))
            self.assertEqual(decode_tile_pixels(cpu.read_bytes(0x7E9340, 32)), pattern)
            want = expected_pixels if shield == 3 else pattern
            for base in (0x7E9300, 0x7E9320, 0x7E93C0, 0x7E93E0):
                self.assertEqual(decode_tile_pixels(cpu.read_bytes(base, 32)), want)

        for item_id in (0x00, 0x20, 0x2D, 0x2E, 0x39):
            cpu = Mini65816(self.rom, p=0x00, db=0x00)
            cpu.put(0x0A, item_id, 2)
            cpu.put_bytes(0x7EBD40, tile * 4)
            cpu.put(0x7EBD3F, 0xCC, 1)
            cpu.put(0x7EBDC0, 0xDD, 1)
            cpu.push(0x08FFEF, 3)  # caller JSL return address
            cpu.push(0x09, 1)      # saved caller DBR popped by PLB
            cpu.run(self.labels["MirrorShield_RemapPickupWRAM"], {0x08FFF0})
            self.assertEqual((cpu.p & 0x30, cpu.db, cpu.stack), (0x30, 0x09, []))
            self.assertEqual((cpu.read(0x7EBD3F, 1), cpu.read(0x7EBDC0, 1)), (0xCC, 0xDD))
            want = expected_pixels if item_id == 0x2E else pattern
            for idx in range(4):
                self.assertEqual(decode_tile_pixels(cpu.read_bytes(0x7EBD40 + idx * 32, 32)), want)


if __name__ == "__main__":
    unittest.main()
