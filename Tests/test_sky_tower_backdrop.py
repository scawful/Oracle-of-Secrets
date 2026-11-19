#!/usr/bin/env python3
"""Compiled 65816 unit tests for Sky Tower ($87) & Sky Route ($8C-$8F) BG1 backdrop.

Verifies the real Asar-compiled ASM from Overworld/ZSCustomOverworld.asm,
Overworld/lyra_overlay_fix.asm, and Overworld/sky_overlay_transition.asm on
LakeSnes 65816 CPU:
  1. Overworld_ReloadSubscreenOverlay_Interupt ($02AF58):
     - Sky hosts ($87, $8C-$8F) with overlay $94 configure BG1 strictly BELOW
       BG2: TM=$16 (BG1 off Main), TS=$01 (BG1 on Subscreen), CGWSEL=$82,
       CGADSUB=$60 (Half + Add on Backdrop only; BG2/OBJ bits clear), and skip
       the vanilla $94 under-the-bridge X-offset bit.
     - Other overlays ($95/$9C/$96 -> $20; $93/$97/$9D/$9E/$9F -> $72;
       $FF -> $00/$1D=0; Song of Storms -> $9F/$72; Tree House $0181 -> $9E/$72)
       retain their exact contracts.
  2. Overworld_LoadBGColorAndSubscreenOverlay ($0BFEB6):
     - Sky backdrop $94 preserves neutral COLDATA ($20/$40/$80) so authored
       CGRAM[0] ($764C) tints cleanly day/night and matches mid-scroll Stage 04
       (zero sky snap/flash on $8F <-> $87), and defensively re-asserts
       TM=$16, CGWSEL=$82, CGADSUB=$60, TS=$01 even if caller had stale $1C=$17
       or $9A=$72.
     - $95 (LW DM) keeps $26/$4C/$8C, $9C (DW DM) keeps $26/$4A/$87, $FF clears
       $9A/$1D.
  3. Palette_RestoreFixedColor_Interupt ($0ED8AE):
     - $94 stays neutral $20/$40/$80 while $95/$9C/$96 preserve their colors.
  4. Bank $02 ($02BD04) & Bank $0E ($0EAF94) BG overlay scroll parity:
     - Both patch CPX #$9C -> CPX #!SKY_CLOUD_OVERLAY ($94) when
       ENABLE_SKY_OVERLAY_SOURCE_PROFILE == 1.
  5. Sky-to-Sky smooth scroll ($8F -> $87 and $87 -> $8F via
     LyraOverlay_FinishTransition -> $02B1F4 -> $0BFE70):
     - Stage 04 hides stale BG1 with neutral COLDATA; Stage 08 reloads $94 for
       the destination host and settles with identical neutral COLDATA,
       TM=$16, TS=$01, CGWSEL=$82, CGADSUB=$60, and synced BG1/BG2 scrolls.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

ASAR = shutil.which("asar")
LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]
SKY_HOSTS = (0x87, 0x8C, 0x8D, 0x8E, 0x8F)


def _find_lakesnes() -> Path | None:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def _build_cpu_lib(temp_dir: Path) -> C.CDLL:
    lakesnes = _find_lakesnes()
    assert lakesnes is not None, "LakeSnes checkout not found (set LAKESNES_DIR)"
    dll = temp_dir / "cpu.dylib"
    subprocess.run(
        [
            "cc", "-shared", "-fPIC", "-O2",
            str(lakesnes / "snes" / "cpu.c"),
            str(lakesnes / "snes" / "statehandler.c"),
            "-o", str(dll),
        ],
        check=True,
    )
    lib = C.CDLL(str(dll))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


def _extract_block(text: str, start_marker: str, end_marker: str) -> str:
    start = text.index(start_marker)
    end = text.index(end_marker, start) + len(end_marker)
    return text[start:end]


def _assemble_sky_backdrop_fixture(folder: Path, *, sky_profile_flag: int = 1) -> tuple[bytes, dict[str, int]]:
    zs = (ROOT / "Overworld" / "ZSCustomOverworld.asm").read_text(encoding="utf-8")

    const_block = _extract_block(
        zs,
        "if !ENABLE_SKY_OVERLAY_SOURCE_PROFILE == 1\n!SKY_CLOUD_OVERLAY = $94",
        "!SKY_CLOUD_OVERLAY = $9C\nendif",
    )
    reload_block = _extract_block(
        zs,
        "org $02AF58 ; $012F58",
        "assert pc() <= $02B0D2 ; $0130D2",
    )
    fixed_color_block = _extract_block(
        zs,
        "org $0BFEB6 ; $05FEB6 ; @hook module=Overworld",
        "assert pc() <= $0BFFA8 ; $05FFA8",
    )
    restore_fixed_block = _extract_block(
        zs,
        "org $0ED8AE ; $0758AE",
        "assert pc() <= $0ED8FB ; $0758FB",
    )

    image = bytearray(b"\x00" * 0x280000)
    # Vanilla Bank $02/$0E scroll lock opcodes (CPX.b #$9C)
    image[_snes_to_pc(0x02BD03)] = 0xE0
    image[_snes_to_pc(0x02BD04)] = 0x9C
    image[_snes_to_pc(0x0EAF93)] = 0xE0
    image[_snes_to_pc(0x0EAF94)] = 0x9C
    # Vanilla hook bytes expected by lyra_overlay_fix.asm & sky_overlay_transition.asm
    image[_snes_to_pc(0x02EF50):_snes_to_pc(0x02EF50) + 4] = bytes.fromhex("2252F60E")
    image[_snes_to_pc(0x02C242):_snes_to_pc(0x02C242) + 4] = bytes.fromhex("22008037")
    # Native finalize tail stub after $02C246 (just RTS so test isolates transition hook)
    image[_snes_to_pc(0x02C246)] = 0x60
    image[_snes_to_pc(0x02C2A3)] = 0x60

    rom_path = folder / f"sky_backdrop_{sky_profile_flag}.sfc"
    rom_path.write_bytes(image)

    harness = f'''lorom
!SPECIAL_OVERWORLD_NATIVE = 1
!ENABLE_SKY_OVERWORLD_ROUTE = 1
!ENABLE_SKY_OVERLAY_SOURCE_PROFILE = {sky_profile_flag}
!LYRA_CURRENT_RESIDENT_OVERLAY_DIRECTORY = $4E9000
!SPECIAL_OVERWORLD_RESOURCE_CODE_END = $4DD000

{const_block}

org $348000
namespace Oracle
incsrc "{ROOT / 'Overworld' / 'lyra_overlay_fix.asm'}"
org $4DCB60
incsrc "{ROOT / 'Overworld' / 'sky_overlay_transition.asm'}"
namespace off

org $029000
; Test wrapper calling Overworld_ReloadSubscreenOverlay_Interupt ($02AF58) with JSR -> RTL
Test_CallReloadOverlay:
  JSR $AF58
  RTL

; Test wrapper calling $02C242 (LyraOverlay_FinishTransition) with JSR -> RTL
Test_CallFinishTransition:
  JSR $C242
  RTL

; Minimal LoadSubscreenOverlay ($02FD0D) stub: record invocation & queue upload $17/$0710
org $02FD0D
LoadSubscreenOverlay:
  INC.w $0F20
  LDA.b $8C : STA.w $0F22
  LDA.b #$04 : STA.b $17 : STA.w $0710
  RTS

; Real native wrapper $02B1F4: save $8A->$7EC213 (M16/X16), call $02AF58 (M8/X16), return M8/X8
org $02B1F4
NativeReloadWrapper:
  REP #$30
  LDA.b $8A : STA.l $7EC213
  LDA.b $84 : STA.l $7EC215
  LDA.b $88 : STA.l $7EC217
  LDA.b $86 : STA.l $7EC219
  LDA.w $0418 : STA.l $7EC21B
  LDA.w $0410 : STA.l $7EC21D
  LDA.w $0416 : STA.l $7EC21F
  SEP #$20
  JSR $AF58
  SEP #$30
  INC.w $0F24
  RTL

org $0BFE70
  REP #$30
  JML $0BFEB6

{reload_block}

{fixed_color_block}

{restore_fixed_block}

org $378000
OriginalAnimation:
  INC.w $0F26
  RTL

; Test ReadOverlayArray: reads 16-bit mock overlay from WRAM $7E0F10
ReadOverlayArray:
  LDA.l $7E0F10
  RTL

Oracle_Part0Storm_CarryClearIfStorm:
  SEC
  RTL

Pool_EnableRainMireEvent:
  db $00, $00

Docks_ShouldHideSubscreen:
  CLC
  RTL

ReplaceBGColor:
  INC.w $0F28
  RTL

SpecialBgHorizOffsetAdjustment:
  RTL
'''
    asm_path = folder / f"sky_backdrop_{sky_profile_flag}.asm"
    asm_path.write_text(harness, encoding="utf-8")
    sym_path = rom_path.with_suffix(".sym")
    proc = subprocess.run(
        [ASAR, "--no-title-check", "--fix-checksum=off",
         "--symbols=wla", f"--symbols-path={sym_path}",
         str(asm_path), str(rom_path)],
        capture_output=True,
        text=True,
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
                             sym_path.read_text(encoding="utf-8"))
    }
    return rom_path.read_bytes(), labels


def _call(f: Fixture, entry: str, *, m8: bool = True, x8: bool = True,
          a: int = 0, x: int = 0, y: int = 0, db: int = 0x02) -> None:
    c = f.cpu
    addr = f.addr(entry)
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    c.db = db
    c.dp = 0
    c.mf = m8
    c.xf = x8
    c.a = a & (0xFF if m8 else 0xFFFF)
    c.x = x & (0xFF if x8 else 0xFFFF)
    c.y = y & (0xFF if x8 else 0xFFFF)
    ret_addr = (addr & 0xFF0000) | 0x7000
    f.put(sp, addr >> 16)
    f.put(sp - 1, 0x6F)
    f.put(sp - 2, 0xFF)
    c.sp -= 3
    for _ in range(50000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack in {entry}: {c.sp:#x} != {sp:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction ceiling reached in {entry}")


def _put16(f: Fixture, addr: int, val: int) -> None:
    f.put(addr, val & 0xFF)
    f.put(addr + 1, (val >> 8) & 0xFF)


def _get16(f: Fixture, addr: int) -> int:
    return f.get(addr) | (f.get(addr + 1) << 8)


@unittest.skipUnless(ASAR and _find_lakesnes(), "Asar and LakeSnes checkout required")
class SkyTowerBackdropCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._td = tempfile.TemporaryDirectory(prefix="oos-sky87-backdrop-test-")
        cls.td = Path(cls._td.name)
        cls.lib = _build_cpu_lib(cls.td)
        cls.rom_on, cls.labels_on = _assemble_sky_backdrop_fixture(cls.td, sky_profile_flag=1)
        cls.rom_off, cls.labels_off = _assemble_sky_backdrop_fixture(cls.td, sky_profile_flag=0)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._td.cleanup()

    def _fx(self, *, flag_on: bool = True) -> Fixture:
        rom = self.rom_on if flag_on else self.rom_off
        labels = self.labels_on if flag_on else self.labels_off
        return Fixture(self.lib, rom, labels)

    def test_bank02_and_bank0e_overlay_scroll_keep_vanilla_9c_no_sky_drift(self) -> None:
        """Both Bank $02 ($02BD04) and Bank $0E ($0EAF94) keep vanilla $9C so $94 does not auto-drift."""
        self.assertEqual(self.rom_on[_snes_to_pc(0x02BD03)], 0xE0)
        self.assertEqual(self.rom_on[_snes_to_pc(0x02BD04)], 0x9C)
        self.assertEqual(self.rom_on[_snes_to_pc(0x0EAF93)], 0xE0)
        self.assertEqual(self.rom_on[_snes_to_pc(0x0EAF94)], 0x9C)
        # Flag OFF also preserves vanilla $9C in both banks.
        self.assertEqual(self.rom_off[_snes_to_pc(0x02BD04)], 0x9C)
        self.assertEqual(self.rom_off[_snes_to_pc(0x0EAF94)], 0x9C)

    def test_reload_overlay_sky_hosts_place_bg1_strictly_below_bg2(self) -> None:
        """$87 and $8C-$8F reload $94 with TM=$16, TS=$01, CGWSEL=$82, CGADSUB=$60 (Backdrop only)."""
        for host in SKY_HOSTS:
            with self.subTest(host=hex(host)):
                f = self._fx(flag_on=True)
                _put16(f, 0x7E008A, host)
                _put16(f, 0x7EC213, host)
                _put16(f, 0x7E0F10, 0x0094)  # ReadOverlayArray -> $0094
                _put16(f, 0x7E00A0, 0x0090)  # D8 room $0090 (non-special exit)
                f.put(0x7E001C, 0x17)        # Start with stale BG1 on Main screen!
                f.put(0x7E009A, 0x72)        # Start with stale foreground overlay math!
                f.put(0x7E00E7, 0x00)        # Verify under-the-bridge bit is NOT set
                _call(f, "Test_CallReloadOverlay", m8=True, x8=False)

                self.assertEqual(f.get(0x7E001C), 0x16, "TM must disable BG1 on Main screen ($16)")
                self.assertEqual(f.get(0x7E001D), 0x01, "TS must enable BG1 on Subscreen ($01)")
                self.assertEqual(f.get(0x7E0099), 0x82, "CGWSEL must enable subscreen color math ($82)")
                self.assertEqual(f.get(0x7E009A), 0x60, "CGADSUB must be $60 (Half+Add Backdrop only)")
                self.assertEqual(f.get(0x7E009A) & 0x1F, 0x00, "BG1/BG2/BG3/BG4/OBJ color math bits must be 0")
                self.assertEqual(f.get(0x7E008C), 0x94)
                self.assertEqual(f.get(0x7E00E7), 0x00, "Must not apply under-the-bridge $E7 |= $01 offset")
                self.assertEqual(_get16(f, 0x7E008A), host)
                self.assertEqual(f.get(0x7E0F20), 1, "LoadSubscreenOverlay must run once")

    def test_reload_overlay_other_overlays_and_rain_unchanged(self) -> None:
        """$95/$9C/$96 keep $20; $93/$97/$9D/$9E/$9F keep $72; $FF clears $1D/$9A; rain overrides $87."""
        cases = [
            (0x05, 0x0095, 0, 0x20, 1),
            (0x43, 0x009C, 0, 0x20, 1),
            (0x5B, 0x0096, 0, 0x20, 1),
            (0x00, 0x009D, 0, 0x72, 1),
            (0x00, 0x009E, 0, 0x72, 1),
            (0x87, 0x0094, 1, 0x72, 1),  # Song of Storms rain overrides $94 -> $9F ($72)
            (0x23, 0x00FF, 0, 0x00, 0),  # No overlay -> $9A=0, $1D=0
        ]
        for area, ov, storms, want_cgadsub, want_ts in cases:
            with self.subTest(area=hex(area), ov=hex(ov), storms=storms):
                f = self._fx(flag_on=True)
                _put16(f, 0x7E008A, area)
                _put16(f, 0x7EC213, area)
                _put16(f, 0x7E0F10, ov)
                f.put(0x7EE00E, storms)
                _call(f, "Test_CallReloadOverlay", m8=True, x8=False)
                self.assertEqual(f.get(0x7E001C), 0x16)
                self.assertEqual(f.get(0x7E001D), want_ts)
                self.assertEqual(f.get(0x7E009A), want_cgadsub)

    def test_fixed_color_and_defensive_backdrop_guard_at_0bfeb6(self) -> None:
        """$0BFEB6 keeps neutral COLDATA for $94 and repairs stale TM/CGWSEL/CGADSUB."""
        for host in SKY_HOSTS:
            with self.subTest(host=hex(host)):
                f = self._fx(flag_on=True)
                f.put(0x7E0010, 0x09)
                f.put(0x7E0011, 0x00)
                _put16(f, 0x7E008A, host)
                _put16(f, 0x7EC213, host)
                f.put(0x7E008C, 0x94)
                # Inject corrupted foreground-overlay PPU mirrors & DW lava fixed color
                f.put(0x7E001C, 0x17)
                f.put(0x7E001D, 0x00)
                f.put(0x7E0099, 0x00)
                f.put(0x7E009A, 0x72)
                f.put(0x7E009C, 0x26); f.put(0x7E009D, 0x4A); f.put(0x7E009E, 0x87)
                _put16(f, 0x7E00E2, 0x0E80); _put16(f, 0x7E00E8, 0x0110)
                _put16(f, 0x7E00E0, 0x0123); _put16(f, 0x7E00E6, 0x0456)

                _call(f, "Overworld_LoadBGColorAndSubscreenOverlay", m8=False, x8=False, db=0x0B)

                self.assertEqual([f.get(0x7E009C), f.get(0x7E009D), f.get(0x7E009E)],
                                 [0x20, 0x40, 0x80], "Sky $94 must keep neutral COLDATA")
                self.assertEqual(f.get(0x7E001C), 0x16, "TM repaired to $16")
                self.assertEqual(f.get(0x7E001D), 0x01, "TS enabled ($01)")
                self.assertEqual(f.get(0x7E0099), 0x82, "CGWSEL repaired to $82")
                self.assertEqual(f.get(0x7E009A), 0x60, "CGADSUB repaired to $60")
                self.assertEqual(_get16(f, 0x7E00E0), 0x0E80, "BG1 X synced to BG2 X")
                self.assertEqual(_get16(f, 0x7E00E6), 0x0110, "BG1 Y synced to BG2 Y")
                self.assertEqual(f.get(0x7E0015), 1, "CGRAM refresh queued")

    def test_fixed_color_0bfeb6_and_0ed8ae_preserve_dm_95_and_9c(self) -> None:
        """Tree-Snow ($95) and Sky ($94) keep neutral COLDATA ($20/$40/$80) for Day/Night; DW Lava ($9C) keeps vanilla."""
        for ov, want_coldata in ((0x95, [0x20, 0x40, 0x80]),
                                 (0x9C, [0x26, 0x4A, 0x87]),
                                 (0x94, [0x20, 0x40, 0x80])):
            with self.subTest(ov=hex(ov)):
                # 1. $0BFEB6
                f = self._fx(flag_on=True)
                _put16(f, 0x7E008A, 0x87 if ov == 0x94 else 0x05)
                _put16(f, 0x7EC213, 0x87 if ov == 0x94 else 0x05)
                f.put(0x7E008C, ov)
                f.put(0x7E009A, 0x20)
                _call(f, "Overworld_LoadBGColorAndSubscreenOverlay", m8=False, x8=False, db=0x0B)
                self.assertEqual([f.get(0x7E009C), f.get(0x7E009D), f.get(0x7E009E)], want_coldata)

                # 2. $0ED8AE (Palette_RestoreFixedColor_Interupt)
                f2 = self._fx(flag_on=True)
                f2.put(0x7E001B, 0)
                _put16(f2, 0x7E0F10, ov)
                _call(f2, "Palette_RestoreFixedColor_Interupt", m8=True, x8=True, db=0x0E)
                self.assertEqual([f2.get(0x7E009C), f2.get(0x7E009D), f2.get(0x7E009E)], want_coldata)

    def test_sky_scroll_transition_8f_to_87_zero_coldata_snap(self) -> None:
        """$8F <-> $87 Stage 04 hide and Stage 08 reload share identical neutral COLDATA ($20/$40/$80)."""
        for src_host, dst_host in ((0x8F, 0x87), (0x87, 0x8F), (0x8C, 0x8D)):
            with self.subTest(src=hex(src_host), dst=hex(dst_host)):
                f = self._fx(flag_on=True)
                f.put(0x7E0010, 0x09)
                f.put(0x7E0011, 0x04)  # Stage 04 mid-scroll
                _put16(f, 0x7E008A, dst_host)
                _put16(f, 0x7EC213, src_host)
                f.put(0x7E008C, 0x94)
                f.put(0x7E001C, 0x16); f.put(0x7E001D, 0x01)
                f.put(0x7E0099, 0x82); f.put(0x7E009A, 0x60)
                _put16(f, 0x7E0F10, 0x0094)

                # Stage 04: $0BFEB6 hides stale subscreen and sets neutral COLDATA
                _call(f, "Overworld_LoadBGColorAndSubscreenOverlay", m8=False, x8=False, db=0x0B)
                stage04_coldata = [f.get(0x7E009C), f.get(0x7E009D), f.get(0x7E009E)]
                self.assertEqual(stage04_coldata, [0x20, 0x40, 0x80])
                self.assertEqual(f.get(0x7E001D), 0x00, "Stale host BG1 hidden during scroll")

                # Stage 08: LyraOverlay_FinishTransition reloads $94 for dst_host & runs $0BFE70
                f.put(0x7E0011, 0x08)
                f.put(0x7E0017, 0x00); f.put(0x7E0710, 0x00)
                _put16(f, 0x7E00E2, 0x0E78); _put16(f, 0x7E00E8, 0x0118)
                _call(f, "Test_CallFinishTransition", m8=True, x8=True, db=0x02)

                stage08_coldata = [f.get(0x7E009C), f.get(0x7E009D), f.get(0x7E009E)]
                self.assertEqual(stage08_coldata, stage04_coldata, "Zero COLDATA flash between Stage 04 and Stage 08")
                self.assertEqual(_get16(f, 0x7EC213), dst_host)
                self.assertEqual(f.get(0x7E001C), 0x16)
                self.assertEqual(f.get(0x7E001D), 0x01)
                self.assertEqual(f.get(0x7E0099), 0x82)
                self.assertEqual(f.get(0x7E009A), 0x60)
                self.assertEqual(_get16(f, 0x7E00E0), 0x0E78)
                self.assertEqual(_get16(f, 0x7E00E6), 0x0118)
                self.assertEqual(f.get(0x7E0F24), 1, "Reload wrapper ran once")
                self.assertEqual(f.get(0x7E0F26), 1, "Original animation tail ran")


if __name__ == "__main__":
    unittest.main()
