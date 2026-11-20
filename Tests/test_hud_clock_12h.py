#!/usr/bin/env python3
"""Compiled 65816 and contract tests for the 12-hour Sun/Moon bottom-center HUD
clock and Game Over BG3 sheet $69 preservation fix.

Assembles the real production routines from Overworld/time_system.asm,
Core/symbols.asm, Menu/menu_hud.asm, and Menu/menu_hud_codex.asm with asar into
isolated synthetic LoROM images and executes them on LakeSnes's C 65816 core.
"""
from __future__ import annotations

from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_bosses_sfx_polish import (  # noqa: E402
    CpuHarness,
    find_asar,
    get_lakesnes_lib,
    lorom_pc,
    parse_sym,
)

ROOT = Path(__file__).resolve().parents[1]

SUN_TILE_HEX = "2838287cc6ba01ffc6ba2a7e28381010"
MOON_TILE_HEX = "1c1c243c4c7498e89aea9ae6625e3c3c"
STRIP_TILE_HEX = "0000000000000000ffff00ffff0000ff"


def extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start)
    return text[start:end]


class DmaCapturingHarness(CpuHarness):
    """CpuHarness subclass that records PPU VRAM/DMA0 transfers triggered by $420B."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int], default_db: int = 0x00):
        self.vram_addr = 0
        self.dma0_addr = 0
        self.dma0_bank = 0
        self.dma0_size = 0
        self.dmas: list[dict[str, object]] = []
        super().__init__(lib, rom, labels, default_db=default_db)

    def write(self, a: int, v: int):
        lo = a & 0xFFFF
        bank = (a >> 16) & 0xFF
        if (bank & 0x7F) < 0x40 and 0x2000 <= lo < 0x6000:
            v &= 0xFF
            if lo == 0x2116:
                self.vram_addr = (self.vram_addr & 0xFF00) | v
            elif lo == 0x2117:
                self.vram_addr = (self.vram_addr & 0x00FF) | (v << 8)
            elif lo == 0x4302:
                self.dma0_addr = (self.dma0_addr & 0xFF00) | v
            elif lo == 0x4303:
                self.dma0_addr = (self.dma0_addr & 0x00FF) | (v << 8)
            elif lo == 0x4304:
                self.dma0_bank = v
            elif lo == 0x4305:
                self.dma0_size = (self.dma0_size & 0xFF00) | v
            elif lo == 0x4306:
                self.dma0_size = (self.dma0_size & 0x00FF) | (v << 8)
            elif lo == 0x420B and (v & 0x01):
                size = self.dma0_size if self.dma0_size else 0x10000
                src = (self.dma0_bank << 16) | self.dma0_addr
                payload = bytes(self.read((self.dma0_bank << 16) | ((self.dma0_addr + i) & 0xFFFF)) for i in range(size))
                self.dmas.append({
                    "vram_word": self.vram_addr,
                    "src": src,
                    "size": size,
                    "data": payload,
                })
                # Hardware DMA0 increments $4302-$4303 by transfer size and zeroes $4305-$4306.
                self.dma0_addr = (self.dma0_addr + size) & 0xFFFF
                self.dma0_size = 0
            return
        super().write(a, v)


def assemble_clock_harness() -> tuple[bytes, dict[str, int]]:
    ts_src = (ROOT / "Overworld" / "time_system.asm").read_text(encoding="utf-8")
    clock_and_nmi = extract_block(
        ts_src,
        "DrawClockToHudLong:",
        "; =========================================================\n\nOverworld_SetFixedColAndScroll",
    )
    gameover_patch = extract_block(
        ts_src,
        "org $009038",
        "assert pc() == $00903C",
    ) + "assert pc() == $00903C\n"

    harness = f"""
lorom
!ENABLE_HORSE_FORM = 1
Horse_HudState      = $7F5674
HudCornerBuffer    = $7EC84A
HudCornerBufferEnd = HudCornerBuffer+14
HudClockBuffer      = HudCornerBufferEnd
HudClockLastHours   = HudClockBuffer+12
HudClockLastMinutes = HudClockBuffer+13
HudClockBufferEnd   = HudClockBuffer+14
HudCarrotTopBuffer  = HudClockBufferEnd
HudCarrotBotBuffer  = HudCarrotTopBuffer+10
HudCarrotBufferEnd  = HudCarrotBotBuffer+10

struct TimeState $7EE000
  .Hours:   skip 1
  .Minutes: skip 1
  .Speed:   skip 1
endstruct

org $348000
{clock_and_nmi}

pushpc
{gameover_patch}
pullpc
"""
    asar = find_asar()
    assert asar is not None
    with tempfile.TemporaryDirectory(prefix="oos-hud-clock-12h-") as td:
        tmp = Path(td)
        asm_path = tmp / "clock_harness.asm"
        rom_path = tmp / "clock_harness.sfc"
        sym_path = tmp / "clock_harness.sym"
        # Synthetic 4 MB LoROM with vanilla NMI_UploadGameOverText preimage at $009038
        rom = bytearray(0x40 * 0x8000)
        pre = bytes([0xC2, 0x20, 0xA9, 0x00, 0x78])
        pc_9038 = lorom_pc(0x009038)
        rom[pc_9038:pc_9038 + len(pre)] = pre
        rom_path.write_bytes(rom)
        asm_path.write_text(harness, encoding="utf-8")

        res = subprocess.run(
            [asar, "--no-title-check", "--fix-checksum=off", "--symbols=wla",
             f"--symbols-path={sym_path}", str(asm_path), str(rom_path)],
            capture_output=True, text=True,
        )
        assert res.returncode == 0, f"asar failed:\n{res.stdout}\n{res.stderr}"
        return rom_path.read_bytes(), parse_sym(sym_path)


class HudClock12hCompiledTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = get_lakesnes_lib()
        cls.asar = find_asar()
        if cls.lib is None or cls.asar is None:
            raise unittest.SkipTest("LakeSnes or asar unavailable")
        cls.rom, cls.labels = assemble_clock_harness()

    def _new_harness(self, default_db: int = 0x00) -> DmaCapturingHarness:
        return DmaCapturingHarness(self.lib, self.rom, self.labels, default_db=default_db)

    def _read_clock_words(self, h: DmaCapturingHarness) -> list[int]:
        return [h.get16(0x7EC858 + i * 2) for i in range(6)]

    def test_all_24_hours_12h_conversion_leading_zero_suppression_and_sun_moon(self):
        h = self._new_harness(default_db=0x0D)
        # Seed old top-left clock cells ($7EC7C4..$7EC7CC) with sentinel to prove untouched
        for off in range(0, 10, 2):
            h.put16(0x7EC7C4 + off, 0x207F)
        h.put(0x7E0010, 0x09)  # Overworld gameplay

        draw_long = h.addr("DrawClockToHudLong")

        for hour24 in range(24):
            for minute in (0, 5, 15, 34, 59):
                h.put(0x7EE000, hour24)
                h.put(0x7EE001, minute)
                h.put(0x7E0016, 0)
                h.call_jsl(draw_long, db=0x0D, mf=True, xf=True)

                is_day = 6 <= hour24 < 18
                exp_icon = 0x3415 if is_day else 0x2C15
                hour12 = 12 if hour24 % 12 == 0 else (hour24 % 12)
                m10, m1 = divmod(minute, 10)
                if hour12 >= 10:
                    expected = [
                        exp_icon,
                        0x2491,
                        0x2490 + (hour12 - 10),
                        0x24AB,
                        0x2490 + m10,
                        0x2490 + m1,
                    ]
                else:
                    expected = [
                        0x207F,
                        exp_icon,
                        0x2490 + hour12,
                        0x24AB,
                        0x2490 + m10,
                        0x2490 + m1,
                    ]

                got = self._read_clock_words(h)
                self.assertEqual(
                    got, expected,
                    f"Mismatch for {hour24:02d}:{minute:02d} (expected 12h={hour12}, day={is_day}): "
                    f"got {[hex(w) for w in got]} != {[hex(w) for w in expected]}",
                )
                self.assertEqual(h.get(0x7E0016), 1, f"Expected $16=1 on time change {hour24:02d}:{minute:02d}")

        # Verify old top-left clock cells ($7EC7C4..$7EC7CC) were never overwritten
        self.assertEqual(
            [h.get16(0x7EC7C4 + off) for off in range(0, 10, 2)],
            [0x207F] * 5,
            "DrawClockToHud must never write to legacy top-left cells $7EC7C4..$7EC7CC",
        )

    def test_sun_moon_boundary_transitions_and_nmi_dirty_cache(self):
        h = self._new_harness(default_db=0x00)
        draw_long = h.addr("DrawClockToHudLong")
        h.put(0x7E0010, 0x09)

        boundary_cases = [
            (5, 59, [0x207F, 0x2C15, 0x2495, 0x24AB, 0x2495, 0x2499]),  # 5:59 Moon
            (6, 0,  [0x207F, 0x3415, 0x2496, 0x24AB, 0x2490, 0x2490]),  # 6:00 Sun
            (12, 0, [0x3415, 0x2491, 0x2492, 0x24AB, 0x2490, 0x2490]),  # 12:00 Sun
            (17, 59,[0x207F, 0x3415, 0x2495, 0x24AB, 0x2495, 0x2499]),  # 5:59 Sun
            (18, 0, [0x207F, 0x2C15, 0x2496, 0x24AB, 0x2490, 0x2490]),  # 6:00 Moon
            (0, 0,  [0x2C15, 0x2491, 0x2492, 0x24AB, 0x2490, 0x2490]),  # 12:00 Moon
        ]
        for hr, mn, expected in boundary_cases:
            h.put(0x7EE000, hr)
            h.put(0x7EE001, mn)
            h.put(0x7E0016, 0)
            h.call_jsl(draw_long, db=0x00, mf=True, xf=True)
            self.assertEqual(self._read_clock_words(h), expected)
            self.assertEqual(h.get(0x7E0016), 1)

            # Calling again with identical (Hours, Minutes) must NOT spam $16
            h.put(0x7E0016, 0)
            h.call_jsl(draw_long, db=0x00, mf=True, xf=True)
            self.assertEqual(h.get(0x7E0016), 0, "Unchanged time must not re-trigger NMI DMA ($16)")

    def test_dialogue_and_menu_mode_defers_upload_and_preserves_caller_regs(self):
        h = self._new_harness(default_db=0x0D)
        draw_long = h.addr("DrawClockToHudLong")

        # Mode $0E (Menu/Dialogue/Map): formats buffer cleanly, does NOT set $16,
        # and leaves HudClockLastMinutes=$FF so returning to gameplay syncs VRAM.
        h.put(0x7E0010, 0x0E)
        h.put(0x7EE000, 12)
        h.put(0x7EE001, 34)
        h.put(0x7E0016, 0)
        h.call_jsl(draw_long, x=0x1234, y=0x5678, db=0x0D, mf=False, xf=False)
        self.assertEqual(self._read_clock_words(h), [0x3415, 0x2491, 0x2492, 0x24AB, 0x2493, 0x2494])
        self.assertEqual(h.get(0x7E0016), 0, "Mode $0E must not set $16")
        self.assertEqual(h.get(0x7EC865), 0xFF, "Mode $0E must invalidate HudClockLastMinutes")
        self.assertFalse(h.cpu.mf)
        self.assertFalse(h.cpu.xf)
        self.assertEqual(h.cpu.x, 0x1234)
        self.assertEqual(h.cpu.y, 0x5678)

        # Returning to gameplay ($10=$09) with same 12:34 must now trigger $16=1 once
        h.put(0x7E0010, 0x09)
        h.call_jsl(draw_long, db=0x0D, mf=True, xf=True)
        self.assertEqual(h.get(0x7E0016), 1)

    def test_out_of_range_time_clamps_safely(self):
        h = self._new_harness()
        draw_long = h.addr("DrawClockToHudLong")
        h.put(0x7E0010, 0x09)
        h.put(0x7EE000, 0xFE)
        h.put(0x7EE001, 0x99)
        h.call_jsl(draw_long, db=0x00, mf=True, xf=True)
        # Clamps to 00:00 -> Moon 12:00
        self.assertEqual(self._read_clock_words(h), [0x2C15, 0x2491, 0x2492, 0x24AB, 0x2490, 0x2490])

    def test_hud_nmi_upload_day_night_and_hidden_blanking(self):
        nmi_upload = self.labels["HUD_NMIUpload"]
        draw_long = self.labels["DrawClockToHudLong"]

        for label, hour, minute, hidden, expected_icon_hex in (
            ("day_sun", 12, 34, False, SUN_TILE_HEX),
            ("night_moon_evening", 18, 15, False, MOON_TILE_HEX),
            ("night_moon_midnight", 0, 5, False, MOON_TILE_HEX),
            ("hidden_hud", 12, 34, True, None),
        ):
            with self.subTest(case=label):
                h = self._new_harness(default_db=0x00)
                h.put(0x7E0010, 0x09)
                # Populate HudCornerBuffer (rupees + keys)
                rupee_words = [0x3CA8, 0xFCA8, 0x2499, 0x2499, 0x2499]
                for i, w in enumerate(rupee_words):
                    h.put16(0x7EC84A + i * 2, w)
                h.put16(0x7EC854, 0x2071)
                h.put16(0x7EC856, 0x2493)

                # Populate HudClockBuffer via compiled DrawClockToHudLong
                h.put(0x7EE000, hour)
                h.put(0x7EE001, minute)
                h.call_jsl(draw_long, db=0x00, mf=True, xf=True)

                if hidden:
                    for off in range(0, 0x40, 2):
                        h.put16(0x7EC700 + off, 0x207F)
                else:
                    h.put(0x7EC73A, 0x6F)

                # Prime DMA0 as $008B6B-$008B81 does before JSL HUD_NMIUpload
                h.vram_addr = 0x6040
                h.dma0_addr = 0xC700
                h.dma0_bank = 0x7E
                h.dma0_size = 0x014A
                h.dmas.clear()

                h.call_jsl(nmi_upload, a=0x00, db=0x00, mf=True, xf=False)
                self.assertEqual(h.cpu.a & 0xFF, 0x01, "HUD_NMIUpload must exit with A=$01")

                if hidden:
                    # 4 DMAs: top HUD + rupees blank + keys blank + clock blank; NO CHR DMA
                    self.assertEqual(len(h.dmas), 4)
                    self.assertEqual(h.dmas[1]["vram_word"], 0x6342)
                    self.assertEqual(h.dmas[1]["data"], b"\x7f\x20" * 5)
                    self.assertEqual(h.dmas[2]["vram_word"], 0x635C)
                    self.assertEqual(h.dmas[2]["data"], b"\x7f\x20" * 2)
                    self.assertEqual(h.dmas[3]["vram_word"], 0x634D)
                    self.assertEqual(h.dmas[3]["data"], b"\x7f\x20" * 6)
                else:
                    # 5 DMAs: top HUD + rupees + keys + clock + 32B CHR ($014+$015)
                    self.assertEqual(len(h.dmas), 5)
                    self.assertEqual(h.dmas[1]["vram_word"], 0x6342)
                    self.assertEqual(h.dmas[1]["src"], 0x7EC84A)
                    self.assertEqual(h.dmas[1]["size"], 10)
                    self.assertEqual(h.dmas[2]["vram_word"], 0x635C)
                    self.assertEqual(h.dmas[2]["src"], 0x7EC854)
                    self.assertEqual(h.dmas[2]["size"], 4)
                    self.assertEqual(h.dmas[3]["vram_word"], 0x634D)
                    self.assertEqual(h.dmas[3]["src"], 0x7EC858)
                    self.assertEqual(h.dmas[3]["size"], 12)
                    self.assertEqual(h.dmas[4]["vram_word"], 0x70A0)
                    self.assertEqual(h.dmas[4]["size"], 32)
                    self.assertEqual(h.dmas[4]["data"].hex(), STRIP_TILE_HEX + expected_icon_hex)

    def test_hud_nmi_upload_epona_carrots_lifecycle(self):
        nmi_upload = self.labels["HUD_NMIUpload"]
        draw_long = self.labels["DrawClockToHudLong"]
        h = self._new_harness(default_db=0x00)
        h.put(0x7E0010, 0x09)
        h.put(0x7E02B2, 0x09)
        h.put(0x7EC73A, 0x6F)
        h.put(0x7EE000, 12); h.put(0x7EE001, 34)
        h.call_jsl(draw_long, db=0x00, mf=True, xf=True)

        # Populate HudCarrotTopBuffer ($7EC866) + HudCarrotBotBuffer ($7EC870)
        for i in range(5):
            h.put16(0x7EC866 + i * 2, 0x3D49 if i < 3 else 0x3142)
            h.put16(0x7EC870 + i * 2, 0x294A if i < 3 else 0x3143)
        h.put(0x7F5674, 0x83)

        def prime():
            h.vram_addr = 0x6040
            h.dma0_addr = 0xC700
            h.dma0_bank = 0x7E
            h.dma0_size = 0x014A
            h.dmas.clear()

        # 1. Mounted outdoors: streams $630E (10B), $632E (10B), $7A48 (32B), $7A10 (32B)
        prime()
        h.call_jsl(nmi_upload, a=0x00, db=0x00, mf=True, xf=False)
        self.assertEqual(h.cpu.a & 0xFF, 0x01)
        self.assertEqual(len(h.dmas), 9)
        self.assertEqual(h.dmas[5]["vram_word"], 0x630E)
        self.assertEqual(h.dmas[5]["size"], 10)
        self.assertEqual(h.dmas[6]["vram_word"], 0x632E)
        self.assertEqual(h.dmas[6]["size"], 10)
        self.assertEqual(h.dmas[7]["vram_word"], 0x7A48)
        self.assertEqual(h.dmas[7]["size"], 32)
        self.assertEqual(h.dmas[8]["vram_word"], 0x7A10)
        self.assertEqual(h.dmas[8]["size"], 32)

        # 2. Menu/Dialogue ($10=$0E): skips carrot DMA and invalidates Horse_HudState -> $8F
        h.put(0x7E0010, 0x0E)
        prime()
        h.call_jsl(nmi_upload, a=0x00, db=0x00, mf=True, xf=False)
        self.assertEqual(h.cpu.a & 0xFF, 0x01)
        self.assertEqual(len(h.dmas), 5)
        self.assertEqual(h.get(0x7F5674), 0x8F)

        # 3. Pending clear on dismount (Horse_HudState=$01): streams $207F blanks once and clears to $00
        h.put(0x7E0010, 0x09)
        h.put(0x7E02B2, 0x00)
        h.put(0x7F5674, 0x01)
        for off in range(0, 12, 2):
            h.put16(0x7EC700 + off, 0x207F)
        prime()
        h.call_jsl(nmi_upload, a=0x00, db=0x00, mf=True, xf=False)
        self.assertEqual(h.cpu.a & 0xFF, 0x01)
        self.assertEqual(len(h.dmas), 7)
        self.assertEqual(h.dmas[5]["vram_word"], 0x630E)
        self.assertEqual(h.dmas[5]["data"], b"\x7f\x20" * 5)
        self.assertEqual(h.dmas[6]["vram_word"], 0x632E)
        self.assertEqual(h.dmas[6]["data"], b"\x7f\x20" * 5)
        self.assertEqual(h.get(0x7F5674), 0x00)

        # 4. Subsequent frame unmounted ($00): zero carrot DMA
        prime()
        h.call_jsl(nmi_upload, a=0x00, db=0x00, mf=True, xf=False)
        self.assertEqual(h.cpu.a & 0xFF, 0x01)
        self.assertEqual(len(h.dmas), 5)

    def test_gameover_nmi_preserves_sheet69_and_clears_0710(self):
        h = self._new_harness(default_db=0x00)
        h.put(0x7E0710, 0x16)
        h.dmas.clear()
        h.call_jsr(0x009038, db=0x00, mf=True, xf=True)
        self.assertEqual(h.get(0x7E0710), 0x00, "$009038 must clear $0710")
        self.assertEqual(h.dmas, [], "$009038 must NOT DMA TILEMAPA over BG3 sheet $69 ($7800-$7BFF)")
        self.assertTrue(h.cpu.mf)
        self.assertTrue(h.cpu.xf)


class HudClock12hContractTest(unittest.TestCase):
    def test_source_contracts_and_legacy_top_left_removed(self):
        symbols = (ROOT / "Core" / "symbols.asm").read_text(encoding="utf-8")
        time_asm = (ROOT / "Overworld" / "time_system.asm").read_text(encoding="utf-8")
        menu_hud = (ROOT / "Menu" / "menu_hud.asm").read_text(encoding="utf-8")
        menu_asm = (ROOT / "Menu" / "menu.asm").read_text(encoding="utf-8")
        menu_cache = (ROOT / "Menu" / "menu_hud_cache.asm").read_text(encoding="utf-8")

        # HudClockBuffer contiguous at $7EC858..$7EC865
        self.assertIn("HudClockBuffer      = HudCornerBufferEnd", symbols)
        self.assertIn("assert HudClockBuffer == $7EC858 && HudClockBufferEnd == $7EC866", symbols)

        # Legacy top-left clock addresses and org $0DFF07 completely gone
        for legacy in ("!hud_hours_high", "!hud_hours_low", "!hud_min_high", "!hud_min_low", "$7EC7C4", "$7EC7CC", "org $0DFF07"):
            self.assertNotIn(legacy, time_asm, f"Legacy top-left clock reference {legacy} must be removed")

        # HUD_Tilemap explicitly blanks row 3 cols 2-6 ($0DFF3B..$0DFF44) including colon $0DFF3F
        self.assertIn("org $0DFF3B", menu_hud)
        self.assertIn("dw $207F, $207F, $207F, $207F, $207F", menu_hud)

        # Menu close scroll copies HudClockBuffer (12 bytes) to $169A (BG3 row 26 cols 13-18)
        self.assertIn("LDA.l HudClockBuffer, X : STA $169A, X", menu_asm)

        # Cached HUD rebuild populates HudClockBuffer before first NMI
        self.assertIn("JSL DrawClockToHudLong", menu_cache)

        # Game Over Sheet $69 preservation hook present
        self.assertIn("org $009038 ; @hook module=Overworld name=HUD_GameOverPreserveSheet69", time_asm)


if __name__ == "__main__":
    unittest.main()
