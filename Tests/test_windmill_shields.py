#!/usr/bin/env python3
"""Compiled 65816 & contract tests for Windmill Guy Guru-Guru, Windmill dual-arch doors,
Full GBC Shield Trilogy (Menu/HUD + Sheets $5F/$5C), and expanded Palette Catalog."""
from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))
import palette_catalog_contract as pcc
import sheet_codec as sc

WINDMILL_ASM = ROOT / "Sprites" / "NPCs" / "windmill_guy.asm"
ENTRANCES_ASM = ROOT / "Overworld" / "entrances.asm"
MENU_GFX_ASM = ROOT / "Menu" / "menu_gfx_table.asm"
CATALOG_JSON = ROOT / "Data" / "graphics" / "palette_catalog.json"


def pc(address: int) -> int:
    bank = (address >> 16) & 0x7F
    assert address & 0x8000, f"Expected LoROM address, got ${address:06X}"
    return bank * 0x8000 + (address & 0x7FFF)


class Mini65816:
    """Deterministic 65816 executor for compiled Windmill Guy & door-scan routines."""

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

    def db_addr(self, off: int) -> int:
        if off < 0x8000:
            return 0x7E0000 | off
        return (self.db << 16) | off

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
            elif op == 0x18:  # CLC
                self.p &= ~1
            elif op == 0x38:  # SEC
                self.p |= 1
            elif op == 0xA9:  # LDA #imm
                self.load_a(self.take(m))
            elif op == 0xA2:  # LDX #imm
                self.x = self.take(ix)
                self.nz(self.x, ix)
            elif op == 0xA0:  # LDY #imm
                self.y = self.take(ix)
                self.nz(self.y, ix)
            elif op == 0xA5:  # LDA dp
                self.load_a(self.read(0x7E0000 | ((self.d + self.take()) & 0xFFFF), m))
            elif op == 0x85:  # STA dp
                self.put(0x7E0000 | ((self.d + self.take()) & 0xFFFF), self.a, m)
            elif op == 0xBD:  # LDA abs,X
                self.load_a(self.read(self.db_addr((self.take(2) + (self.x & xmask)) & 0xFFFF), m))
            elif op == 0xB9:  # LDA abs,Y
                self.load_a(self.read(self.db_addr((self.take(2) + (self.y & xmask)) & 0xFFFF), m))
            elif op == 0x9D:  # STA abs,X
                self.put(self.db_addr((self.take(2) + (self.x & xmask)) & 0xFFFF), self.a, m)
            elif op == 0x91:  # STA (dp),Y
                ptr = self.read(0x7E0000 | ((self.d + self.take()) & 0xFFFF), 2)
                self.put(0x7E0000 | ((ptr + (self.y & xmask)) & 0xFFFF), self.a, m)
            elif op == 0x29:  # AND #imm
                self.load_a((self.a & mmask) & self.take(m))
            elif op == 0x05:  # ORA dp
                self.load_a((self.a & mmask) | self.read(0x7E0000 | ((self.d + self.take()) & 0xFFFF), m))
            elif op == 0x65:  # ADC dp
                v = self.read(0x7E0000 | ((self.d + self.take()) & 0xFFFF), m)
                tot = (self.a & mmask) + v + (self.p & 1)
                self.p = (self.p & ~1) | int(tot > mmask)
                self.load_a(tot & mmask)
            elif op == 0x69:  # ADC #imm
                v = self.take(m)
                tot = (self.a & mmask) + v + (self.p & 1)
                self.p = (self.p & ~1) | int(tot > mmask)
                self.load_a(tot & mmask)
            elif op == 0x7D:  # ADC abs,X
                v = self.read(self.db_addr((self.take(2) + (self.x & xmask)) & 0xFFFF), m)
                tot = (self.a & mmask) + v + (self.p & 1)
                self.p = (self.p & ~1) | int(tot > mmask)
                self.load_a(tot & mmask)
            elif op == 0xC9:  # CMP #imm
                v = self.take(m)
                lhs = self.a & mmask
                self.p = (self.p & ~1) | int(lhs >= v)
                self.nz(lhs - v, m)
            elif op == 0xDF:  # CMP long,X
                v = self.read(self.take(3) + (self.x & xmask), m)
                lhs = self.a & mmask
                self.p = (self.p & ~1) | int(lhs >= v)
                self.nz(lhs - v, m)
            elif op == 0x0A:  # ASL A
                lhs = self.a & mmask
                self.p = (self.p & ~1) | ((lhs >> (8 * m - 1)) & 1)
                self.load_a((lhs << 1) & mmask)
            elif op == 0x4A:  # LSR A
                lhs = self.a & mmask
                self.p = (self.p & ~1) | (lhs & 1)
                self.load_a(lhs >> 1)
            elif op == 0xF0:  # BEQ
                off = self.take(); off -= 256 if off >= 128 else 0
                if self.p & 2:
                    self.pc += off
            elif op == 0xD0:  # BNE
                off = self.take(); off -= 256 if off >= 128 else 0
                if not (self.p & 2):
                    self.pc += off
            elif op == 0x90:  # BCC
                off = self.take(); off -= 256 if off >= 128 else 0
                if not (self.p & 1):
                    self.pc += off
            elif op == 0xB0:  # BCS
                off = self.take(); off -= 256 if off >= 128 else 0
                if self.p & 1:
                    self.pc += off
            elif op == 0x10:  # BPL
                off = self.take(); off -= 256 if off >= 128 else 0
                if not (self.p & 0x80):
                    self.pc += off
            elif op == 0xC8:  # INY
                self.y = (self.y + 1) & xmask; self.nz(self.y, ix)
            elif op == 0xCA:  # DEX
                self.x = (self.x - 1) & xmask; self.nz(self.x, ix)
            elif op == 0x8A:  # TXA
                self.load_a(self.x & xmask)
            elif op == 0x98:  # TYA
                self.load_a(self.y & xmask)
            elif op == 0xAA:  # TAX
                self.x = self.a & xmask; self.nz(self.x, ix)
            elif op == 0xA8:  # TAY
                self.y = self.a & xmask; self.nz(self.y, ix)
            elif op == 0x48:  # PHA
                self.push(self.a & mmask, m)
            elif op == 0x68:  # PLA
                self.load_a(self.pop(m))
            elif op == 0xDA:  # PHX
                self.push(self.x & xmask, ix)
            elif op == 0xFA:  # PLX
                self.x = self.pop(ix); self.nz(self.x, ix)
            elif op == 0x5A:  # PHY
                self.push(self.y & xmask, ix)
            elif op == 0x7A:  # PLY
                self.y = self.pop(ix); self.nz(self.y, ix)
            elif op == 0x8B:  # PHB
                self.push(self.db, 1)
            elif op == 0x4B:  # PHK
                self.push((self.pc >> 16) & 0xFF, 1)
            elif op == 0xAB:  # PLB
                self.db = self.pop(1); self.nz(self.db, 1)
            elif op == 0x20:  # JSR
                t = self.take(2); self.push((self.pc - 1) & 0xFFFF, 2); self.pc = (self.pc & 0xFF0000) | t
            elif op == 0x60:  # RTS
                self.pc = (self.pc & 0xFF0000) | ((self.pop(2) + 1) & 0xFFFF)
            elif op == 0x22:  # JSL
                t = self.take(3); self.push(self.pc - 1, 3); self.pc = t
            elif op == 0x5C:  # JML
                self.pc = self.take(3)
            elif op == 0x6B:  # RTL
                self.pc = self.pop(3) + 1
            elif op == 0xEA:  # NOP
                pass
            else:
                raise AssertionError(f"Unsupported opcode ${op:02X} at ${self.pc - 1:06X}")
        raise AssertionError("CPU step limit reached")


class WindmillGuyCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.asm_bin = os.environ.get("ASAR_BIN") or shutil.which("z3asm") or shutil.which("asar")
        if not cls.asm_bin:
            raise unittest.SkipTest("z3asm or asar is required")
        cls.temp = tempfile.TemporaryDirectory(prefix="oos-windmill-unit-")
        cls.addClassCleanup(cls.temp.cleanup)
        tmp = Path(cls.temp.name)
        src = tmp / "harness.asm"
        rom_path = tmp / "harness.sfc"
        sym_path = tmp / "harness.sym"
        rom_path.write_bytes(b"\x00" * 0x200000)

        # Extract Sprite_WindmillGuy_Long + Sprite_WindmillGuy_Draw directly from windmill_guy.asm
        wm_text = WINDMILL_ASM.read_text(encoding="utf-8")
        # Assemble real windmill_guy.asm with stub macros/symbols so we test the actual file!
        src.write_text(
            "lorom\n"
            "Sprite_WindmillGuy = $B2\n"
            "SprMiscC = $0DF0\n"
            "SprFrame = $0DC0\n"
            "SprTimerB = $0DF0\n"
            "Sprite_PrepOamCoord = $348000\n"
            "Sprite_OAM_AllocateDeferToPlayer = $348010\n"
            "Sprite_DrawShadow = $348020\n"
            "Sprite_CheckActive = $348030\n"
            "Sprite_PlayerCantPassThrough = $348040\n"
            "macro Set_Sprite_Properties(prep, main)\n"
            "endmacro\n"
            "macro PlayAnimation(s, e, w)\n"
            "endmacro\n"
            "macro ShowSolicitedMessage(id)\n"
            "  CLC\n"
            "endmacro\n"
            "org $308000\n"
            f'incsrc "{WINDMILL_ASM}"\n',
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

    def test_player_bee_multiplex_guard_bypasses_windmill_guy(self) -> None:
        cpu = Mini65816(self.rom, x=3, p=0x30, db=0x06)
        cpu.put(0x7E0D80 + 3, 1, 1)  # PlayerBee active state
        cpu.put(0x7E0DF0 + 3, 0, 1)
        cpu.push(0x06999E, 3)
        cpu.run(self.labels["Sprite_WindmillGuy_Long"], {0x1E8B11})
        self.assertEqual(cpu.pc, 0x1E8B11)
        self.assertEqual(cpu.read(0x7E0DF0 + 3, 1), 0)  # SprMiscC untouched
        self.assertEqual(cpu.calls, [])

    def test_guru_guru_draws_two_frames_and_preserves_miscc(self) -> None:
        for frame, expected_dy_head, expected_crank_y, expected_crank_prop in (
            (0, -13, 2, 0x2B),
            (1, -12, 4, 0xAB),
            (3, -12, 4, 0xAB),  # stale frame clamped via AND #$01
        ):
            with self.subTest(frame=frame):
                cpu = Mini65816(self.rom, x=2, p=0x30, db=0x06)
                cpu.put(0x7E0D80 + 2, 0, 1)  # Windmill Guy NPC
                cpu.put(0x7E0DC0 + 2, frame, 1)
                cpu.put(0x7E0DF0 + 2, 0, 1)
                cpu.put(0x7E0090, 0x0800, 2)  # OAM low buf
                cpu.put(0x7E0092, 0x0A20, 2)  # OAM hi buf
                cpu.put(0x7E0000, 0x0080, 2)  # screen X = 128
                cpu.put(0x7E0002, 0x0060, 2)  # screen Y = 96

                def stub_prep(c: Mini65816) -> None:
                    c.p &= ~1  # Carry clear = on screen
                    c.pc = c.pop(3) + 1

                def stub_rtl(c: Mini65816) -> None:
                    c.pc = c.pop(3) + 1

                def stub_inactive(c: Mini65816) -> None:
                    c.p &= ~1  # Carry clear = skip Main
                    c.pc = c.pop(3) + 1

                cpu.stubs[0x348000] = stub_prep
                cpu.stubs[0x348010] = stub_rtl
                cpu.stubs[0x348020] = stub_rtl
                cpu.stubs[0x348030] = stub_inactive

                cpu.push(0x06AAAE, 3)
                cpu.run(self.labels["Sprite_WindmillGuy_Long"], {0x06AAAF})
                self.assertEqual(cpu.db, 0x06)
                self.assertEqual(cpu.read(0x7E0DF0 + 2, 1), 1)  # SprMiscC = 1 preserved!
                self.assertEqual(cpu.calls, [0x348000, 0x348010, 0x348020, 0x348030])

                # Inspect all 6 emitted OAM entries (slots 0..5 = Crank, Head, Body, HornBot, HornTop, HornNeck)
                oam = [
                    (
                        cpu.read(0x7E0800 + i * 4 + 0, 1),
                        cpu.read(0x7E0800 + i * 4 + 1, 1),
                        cpu.read(0x7E0800 + i * 4 + 2, 1),
                        cpu.read(0x7E0800 + i * 4 + 3, 1),
                        cpu.read(0x7E0A20 + i, 1),
                    )
                    for i in range(6)
                ]
                dy_h = 0 if (frame & 1) == 0 else 1
                expected = [
                    ((128 - 5) & 0xFF, (96 + expected_crank_y) & 0xFF, 0xFF, expected_crank_prop, 0x00),
                    (128, (96 + expected_dy_head) & 0xFF, 0xE8, 0x2B, 0x02),
                    (128, 96, 0xEA, 0x2B, 0x02),
                    (128 + 12, (96 - 15 + dy_h) & 0xFF, 0xEF, 0x2D, 0x00),
                    (128 + 12, (96 - 23 + dy_h) & 0xFF, 0xDF, 0x2D, 0x00),
                    (128 + 4, (96 - 20 + dy_h) & 0xFF, 0xCF, 0x2D, 0x00),
                ]
                self.assertEqual(oam, expected)

    def test_offscreen_windmill_guy_skips_oam_alloc_and_shadow(self) -> None:
        cpu = Mini65816(self.rom, x=1, p=0x30, db=0x06)
        cpu.put(0x7E0D80 + 1, 0, 1)

        def stub_offscreen(c: Mini65816) -> None:
            c.p |= 1  # Carry set = offscreen
            c.pc = c.pop(3) + 1

        def stub_inactive(c: Mini65816) -> None:
            c.p &= ~1
            c.pc = c.pop(3) + 1

        cpu.stubs[0x348000] = stub_offscreen
        cpu.stubs[0x348030] = stub_inactive
        cpu.push(0x06BBBE, 3)
        cpu.run(self.labels["Sprite_WindmillGuy_Long"], {0x06BBBF})
        # Only PrepOamCoord and CheckActive called; OAM_AllocateDeferToPlayer & DrawShadow skipped!
        self.assertEqual(cpu.calls, [0x348000, 0x348030])


class WindmillDualArchAndShieldContractsTests(unittest.TestCase):
    def test_valid_door_types_expanded_includes_windmill_dual_arch_pairs(self) -> None:
        text = ENTRANCES_ASM.read_text(encoding="utf-8")
        self.assertIn("LDX.w #$0068", text)
        self.assertIn("assert ValidDoorTypesExpanded_high-ValidDoorTypesExpanded_low == $6A", text)
        self.assertIn("assert ValidDoorTypesExpanded_end-ValidDoorTypesExpanded_high == $6A", text)

        lo_blk = text.split("ValidDoorTypesExpanded_low:")[1].split("ValidDoorTypesExpanded_high:")[0]
        hi_blk = text.split("ValidDoorTypesExpanded_high:")[1].split("ValidDoorTypesExpanded_end:")[0]
        lo = [int(x, 16) for x in re.findall(r"\$([0-9A-Fa-f]{4})", re.sub(r";[^\n]*", "", lo_blk))]
        hi = [int(x, 16) for x in re.findall(r"\$([0-9A-Fa-f]{4})", re.sub(r";[^\n]*", "", hi_blk))]
        self.assertEqual(len(lo), 53)
        self.assertEqual(len(hi), 53)
        pairs = set(zip(lo, hi))
        self.assertIn((0x0131, 0x0131), pairs)  # $035E -> neighbor $0FE7
        self.assertIn((0x01A4, 0x01A4), pairs)  # $035C/$0360 -> neighbor $0FE6/$0FE8
        self.assertIn((0x0139, 0x0138), pairs)  # $0362 -> neighbor $0FE9

    def test_source_sheets_have_valid_pixel_budgets_and_zero_sword_bleed(self) -> None:
        # Sheet $38: all 12 Guru-Guru tiles non-empty
        g38 = sc.text_to_grid((ROOT / "Data/graphics/spr38.txt").read_text(encoding="utf-8"))
        for t in (0x0F, 0x1F, 0x2F, 0x3F, 0x28, 0x29, 0x38, 0x39, 0x2A, 0x2B, 0x3A, 0x3B):
            tx, ty = (t % 16) * 8, (t // 16) * 8
            self.assertTrue(any(g38[ty + y][tx + x] for y in range(8) for x in range(8)), f"spr38 tile ${t:02X} empty")

        # Sheet $5F: L1 ($04-$09/$14-$19) and L2 ($0A-$0F/$1A-$1F) MUST NOT use 3bpp 1/2/3 (Sword colors!)
        g5f = sc.text_to_grid((ROOT / "Data/graphics/spr5f.txt").read_text(encoding="utf-8"))
        for label, cols in (("L1 Wooden", range(0x04, 0x0A)), ("L2 Iron/Kite", range(0x0A, 0x10))):
            used = set()
            for row_off in (0x00, 0x10):
                for c in cols:
                    t = c + row_off
                    tx, ty = (t % 16) * 8, (t // 16) * 8
                    used.update(g5f[ty + y][tx + x] for y in range(8) for x in range(8))
            self.assertEqual(used, {0, 4, 5, 6, 7}, f"{label} leaked Sword indices: {used}")

        # L3 Oracle Mirror Front ($20/$21/$30/$31) uses 5-color Option D ({0,2,4,5,6,7} with 2->C8)
        used_l3_front = set()
        for t in (0x20, 0x21, 0x30, 0x31):
            tx, ty = (t % 16) * 8, (t // 16) * 8
            used_l3_front.update(g5f[ty + y][tx + x] for y in range(8) for x in range(8))
        self.assertEqual(used_l3_front, {0, 2, 4, 5, 6, 7})

        # Sheet $5C: L1/L2 pickup ($0F/$1F) uses {0,4,5,6,7} only; L3 pickup ($24/$25/$34/$35) matches L3 front
        g5c = sc.text_to_grid((ROOT / "Data/graphics/spr5c.txt").read_text(encoding="utf-8"))
        used_rcpt = set()
        for t in (0x0F, 0x1F):
            tx, ty = (t % 16) * 8, (t // 16) * 8
            used_rcpt.update(g5c[ty + y][tx + x] for y in range(8) for x in range(8))
        self.assertEqual(used_rcpt, {0, 4, 5, 6, 7})
        for src_t, dst_t in ((0x20, 0x24), (0x21, 0x25), (0x30, 0x34), (0x31, 0x35)):
            sx, sy = (src_t % 16) * 8, (src_t // 16) * 8
            dx, dy = (dst_t % 16) * 8, (dst_t // 16) * 8
            for y in range(8):
                self.assertEqual(g5f[sy + y][sx : sx + 8], g5c[dy + y][dx : dx + 8])

    def test_menu_shield_gfx_and_2bpp_asset(self) -> None:
        gfx = MENU_GFX_ASM.read_text(encoding="utf-8")
        self.assertIn("dw $34FD, $74FD, $34FE, $74FE", gfx)
        self.assertIn("dw $30FF, $70FF, $309F, $709F", gfx)
        self.assertIn("dw $2C80, $2C81, $2C8D, $2C8E", gfx)
        raw_2bpp = (ROOT / "Data/graphics/items/gbc_shields.2bpp").read_bytes()
        self.assertEqual(len(raw_2bpp), 128)
        for i in range(8):
            self.assertTrue(any(raw_2bpp[i * 16 : (i + 1) * 16]))

    def test_expanded_palette_catalog_valid_and_complete(self) -> None:
        pcc.validate_palette_catalog(CATALOG_JSON)
        doc = json.loads(CATALOG_JSON.read_text(encoding="utf-8"))
        entries = {e["key"]: e for e in doc["entries"]}
        self.assertGreaterEqual(len(entries), 20)
        for key in (
            "oracle.shields.wooden",
            "oracle.shields.iron_kite",
            "oracle.shields.mirror_option_d",
            "oracle.actors.aux3.03",
            "oracle.actors.aux3.0a",
            "oracle.actors.aux1.00",
            "oracle.actors.aux2.00",
            "oracle.hud.main",
            "oracle.underworld.main.02_house",
        ):
            self.assertIn(key, entries)


if __name__ == "__main__":
    unittest.main()
