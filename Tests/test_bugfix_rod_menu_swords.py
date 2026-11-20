#!/usr/bin/env python3
"""Compiled 65816 (LakeSnes) + contract tests for Menu_Exit $020B clear & Menu Sword Icons."""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_wolfos_combat import (  # noqa: E402
    find_asar,
    get_lakesnes_lib,
    lorom_pc,
    parse_sym,
)

ROOT = Path(__file__).resolve().parents[1]
MENU_ASM = ROOT / "Menu" / "menu.asm"
MENU_GFX = ROOT / "Menu" / "menu_gfx_table.asm"
SWORD_SLOTS_ASM = ROOT / "Menu" / "menu_sword_slots.asm"


def _extract_menu_exit_body() -> str:
    txt = MENU_ASM.read_text(encoding="utf-8", errors="replace")
    m = re.search(r"^Menu_Exit:\s*\n\{(.*?)^\}", txt, re.M | re.S)
    assert m, "Menu_Exit not found in Menu/menu.asm"
    return m.group(1)


class MenuCpuRunner:
    """Minimal LakeSnes 65816 runner with RTS/RTL stubs for compiled menu code."""

    def __init__(self, rom: bytes, jsl_stubs: set[int], jsr_stubs: set[int]):
        self.lib = get_lakesnes_lib()
        assert self.lib is not None, "LakeSnes CPU library (cpu.c) unavailable"
        self.rom = rom
        self.ram = bytearray(0x20000)
        self.jsl_stubs = jsl_stubs
        self.jsr_stubs = jsr_stubs
        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self._read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self._write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = self.lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self.reset_cpu()

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def reset_cpu(self) -> None:
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, flag, False)
        self.cpu.mf = self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x01FF
        self.cpu.a = self.cpu.x = self.cpu.y = 0
        self.cpu.db = 0

    @staticmethod
    def _ram_off(a: int) -> int | None:
        bank = a >> 16
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def _read(self, a: int) -> int:
        if a in self.jsl_stubs:
            return 0x6B  # RTL
        if a in self.jsr_stubs:
            return 0x60  # RTS
        off = self._ram_off(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = lorom_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, a: int, v: int) -> None:
        off = self._ram_off(a)
        if off is not None:
            self.ram[off] = v & 0xFF

    def put(self, addr: int, val: int) -> None:
        self.ram[addr & 0x1FFFF] = val & 0xFF

    def get(self, addr: int) -> int:
        return self.ram[addr & 0x1FFFF]

    def get16(self, addr: int) -> int:
        o = addr & 0x1FFFF
        return self.ram[o] | (self.ram[o + 1] << 8)

    def _run_until_sp(self, stop_sp: int, max_steps: int = 10000) -> None:
        for _ in range(max_steps):
            self.lib.cpu_runOpcode(self.p)
            if self.cpu.sp == stop_sp:
                return
        raise AssertionError(f"65816 execution did not return within {max_steps} opcodes (sp={self.cpu.sp:#x})")

    def call_jsl(self, addr: int, a: int = 0) -> None:
        self.reset_cpu()
        self.cpu.a = a & 0xFFFF
        self.cpu.k = addr >> 16
        self.cpu.pc = addr & 0xFFFF
        self.ram[0x01FF] = 0x3F
        self.ram[0x01FE] = 0xFF
        self.ram[0x01FD] = 0xFA
        self.cpu.sp = 0x01FC
        self._run_until_sp(0x01FF)

    def call_jsr(self, addr: int, bank: int) -> None:
        self.reset_cpu()
        self.cpu.k = bank
        self.cpu.db = bank
        self.cpu.pc = addr & 0xFFFF
        self.ram[0x01FF] = 0xFF
        self.ram[0x01FE] = 0xFA
        self.cpu.sp = 0x01FD
        self._run_until_sp(0x01FF)


class BugfixRodAndMenuSwordsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        asar = find_asar()
        assert asar, "asar binary required"
        menu_exit_body = _extract_menu_exit_body()
        cls.jsl_stubs = {
            "Menu_Bindings_Close": 0x3E8000,
            "LinkState_ResetMaskAnimated": 0x3E8010,
            "Supply_ProcessPendingExitAction": 0x3E8030,
            "MenuMapTravel_ExitAction": 0x3E8040,
            "Tunic_GetWorn": 0x3E8060,
        }
        asm = f"""lorom
incsrc "Config/feature_flags.asm"
incsrc "Core/sram.asm"
incsrc "Core/symbols.asm"
Menu_Bindings_Close = ${cls.jsl_stubs["Menu_Bindings_Close"]:06X}
LinkState_ResetMaskAnimated = ${cls.jsl_stubs["LinkState_ResetMaskAnimated"]:06X}
Supply_ProcessPendingExitAction = ${cls.jsl_stubs["Supply_ProcessPendingExitAction"]:06X}
MenuMapTravel_ExitAction = ${cls.jsl_stubs["MenuMapTravel_ExitAction"]:06X}
Tunic_GetWorn = ${cls.jsl_stubs["Tunic_GetWorn"]:06X}

org $2D8000
Menu_CheckBottle:
  RTS
Menu_ItemIndex:
  db $00,$03,$02,$0E,$01,$0A,$0B,$04,$09,$05,$06,$14,$0B,$08,$0C,$12,$0D,$07,$0B
  db $11,$0F,$08,$10,$13,$0B,$0D,$0E,$0D,$01,$0E,$00
Menu_Exit:
{{
{menu_exit_body}
}}

org $2B8000
Tunic_SetWorn:
  RTL
incsrc "Menu/menu_sword_slots.asm"
"""
        with tempfile.TemporaryDirectory(prefix="oos-rod-menu-swords-") as td:
            tmp = Path(td)
            rom_path = tmp / "test.sfc"
            rom_path.write_bytes(b"\x00" * 0x200000)
            src_path = tmp / "main.asm"
            src_path.write_text(asm, encoding="utf-8")
            sym_path = tmp / "test.sym"
            res = subprocess.run(
                [asar, "--no-title-check", "-I" + str(ROOT), "--symbols=wla", f"--symbols-path={sym_path}", str(src_path), str(rom_path)],
                cwd=str(ROOT),
                capture_output=True,
                text=True,
                errors="replace",
            )
            assert res.returncode == 0, f"asar failed:\n{res.stdout}\n{res.stderr}"
            cls.rom = rom_path.read_bytes()
            cls.labels = parse_sym(sym_path)

    def test_menu_exit_clears_020B_on_close(self) -> None:
        r = MenuCpuRunner(self.rom, set(self.jsl_stubs.values()), {self.labels["Menu_CheckBottle"]})
        self.addCleanup(r.close)

        # Simulate closing from Equipment page with Garo Master selected (cursor slot $020B = 5)
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(0x0200, 0x0A)   # menu exit state
        r.put(0x020B, 0x05)   # Equipment slot 5 (Garo Master)
        r.put(0x0202, 0x09)   # Fire Rod equipped on Y
        r.put(0x010C, 0x09)   # Overworld return module
        r.put(0x00E4, 0x00)   # $E4 = 0 path
        r.call_jsr(self.labels["Menu_Exit"], bank=0x2D)

        self.assertEqual(r.get(0x020B), 0x00, "Menu_Exit must clear shared cursor $020B so LinkItem_FireAndIceRod is not blocked!")
        self.assertEqual(r.get(0x0303), 0x05, "Fire Rod action $05 must still propagate to $0303")
        self.assertEqual(r.get(0x0010), 0x09)

        # Also test with $E4 = $0100 (closing from Equipment/Quest/Map right-half pages!)
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(0x0200, 0x0A)
        r.put(0x020B, 0x19)   # Heavy Sword slot 25
        r.put(0x010C, 0x09)
        r.put(0x00E4, 0x00)
        r.put(0x00E5, 0x01)   # $E4 = $0100
        r.call_jsr(self.labels["Menu_Exit"], bank=0x2D)
        self.assertEqual(r.get(0x020B), 0x00, "Menu_Exit right-half close must clear $020B!")

    def test_sword_gfx_lv4_blue_and_goronblade_orange_vs_broken_grey(self) -> None:
        gfx = MENU_GFX.read_text(encoding="utf-8", errors="replace")
        m = re.search(r"SwordGFX:\s*\n((?:\s+dw\s+.*\n){4})", gfx)
        self.assertIsNotNone(m, "SwordGFX table not found")
        rows = m.group(1).strip().splitlines()
        self.assertEqual(len(rows), 4)
        # Level 4 Master Sword row must use blue palette 3 ($2Cxx) for its blade ($2C8A, $2C65, $2C74, $EC8A)
        self.assertIn("$2C8A, $2C65, $2C74, $EC8A", rows[3])
        self.assertNotIn("$288A", rows[3])

        # Compiled 65816 execution of SwordSlots_MarkerSlot:
        # 1) Reforged Goronblade ($85) -> orange palette 1 ($248A, $2465)
        # 2) Broken Blade ($81)        -> grey palette 4 ($308A, $30CE)
        r = MenuCpuRunner(self.rom, set(self.jsl_stubs.values()), set())
        self.addCleanup(r.close)

        marker_addr = self.labels["SwordSlots_MarkerSlot"]
        heavy_pos = 0x018E
        tl_addr = 0x7E1108 + heavy_pos
        tr_addr = 0x7E110A + heavy_pos

        # Case 1: Heavy owned + reforged ($85), Sword = 3
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(0x7EF359, 0x03)
        r.put(0x7EF3BD, 0x85)  # Initialized | HeavyReforged | HeavyOwned
        r.call_jsl(marker_addr)
        self.assertEqual(r.get16(tl_addr), 0x248A)
        self.assertEqual(r.get16(tr_addr), 0x2465)
        self.assertEqual(r.cpu.a & 0xFF, 0x18)

        # Case 2: Heavy owned + broken ($81), Sword = 1
        r.ram[:] = b"\x00" * len(r.ram)
        r.put(0x7EF359, 0x01)
        r.put(0x7EF3BD, 0x81)  # Initialized | HeavyOwned (un-reforged)
        r.call_jsl(marker_addr)
        self.assertEqual(r.get16(tl_addr), 0x308A)
        self.assertEqual(r.get16(tr_addr), 0x30CE)
        self.assertEqual(r.cpu.a & 0xFF, 0x18)


if __name__ == "__main__":
    unittest.main()
