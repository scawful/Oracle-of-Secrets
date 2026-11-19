#!/usr/bin/env python3
"""Compiled 65816 unit tests for Overworld/liftables_palette_fix.asm (QUEUE325).

Assembles the real Overworld/liftables_palette_fix.asm verbatim with Asar into a
synthetic LoROM image seeded with the vanilla hook pre-images, then executes the
real compiled 65816 machine code on Lakesnes across:
  - Light World ($00-$3F: standard MainPal=0, Snow MainPal=3, Heavy Rock $0239)
  - Dark World / Eon Abyss ($40-$7F: MainPal=1, MainPal=2, Small Light Rock
    SP0 separation from DW Bush SP6, Small Heavy Rock, DW Sign, Gigantic Rocks)
  - Special Overworld ($80-$BF: Record-411 / Snow $84 / Slate $8C / Tail $B1)
  - Indoors ($1B != 0: 100% vanilla OAM palette, zero CGRAM writes)
  - Translucency guard ($0ABD != 0)
  - Lazy $15 NMI upload dirty flag & zero direct-page scratch clobber
  - Bank $1B revealed-Tile16 dispatch ($017D DW Sign, DW $63 Sheet $F8 -> $0172
    across lift/sword/dash/bomb, and LW $22 overwritten $072A brick-wall guard)
"""
import ctypes as C
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
ASM_PATH = ROOT / "Overworld" / "liftables_palette_fix.asm"
LAKESNES_CANDIDATES = [
    ROOT.parent / "lakesnes",
    ROOT.parent / "lakesnes" / "lakesnes",
    ROOT.parent.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]

sys.path.insert(0, str(ROOT / "Tests"))
from d4_compiled_fight_check import Cpu


def snes_to_pc(addr: int) -> int:
    return ((addr & 0x7F0000) >> 1) | (addr & 0x7FFF)


def find_lakesnes() -> Path:
    for cand in LAKESNES_CANDIDATES:
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    raise RuntimeError("Could not locate lakesnes/snes/cpu.c")


def find_asar() -> str:
    found = shutil.which("asar")
    if found:
        return found
    fallback = Path("/Users/scawful/src/third_party/asar-repo/build/asar/bin/asar")
    if fallback.is_file():
        return str(fallback)
    raise RuntimeError("Could not locate asar binary")


class Harness:
    """Minimal 65816 execution harness over Lakesnes cpu.c."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.bad_writes: list[tuple[int, int]] = []
        self.writes: list[tuple[int, int]] = []
        self.read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self.write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self.read_cb, self.write_cb, self.idle_cb)
        self.cpu = self.p.contents
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped",
                     "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, flag, False)
        self.cpu.mf = True
        self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x1FF
        self.cpu.a = self.cpu.x = self.cpu.y = 0
        self.cpu.db = 0x06

    def close(self):
        self.lib.cpu_free(self.p)

    @staticmethod
    def ram_offset(a: int):
        bank = a >> 16
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def read(self, a: int) -> int:
        off = self.ram_offset(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = snes_to_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def write(self, a: int, v: int):
        off = self.ram_offset(a)
        if off is None:
            self.bad_writes.append((a, v))
            return
        self.ram[off] = v
        self.writes.append((a, v))

    def put(self, a: int, v: int):
        self.write(a, v & 0xFF)

    def get(self, a: int) -> int:
        return self.read(a)

    def put_word(self, a: int, v: int):
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def get_word(self, a: int) -> int:
        return self.get(a) | (self.get(a + 1) << 8)

    def seed_bg_pal(self, row: int, colors_1_to_7: list[int], live_delta: int = 0):
        """Seed BG row (2..7) colors 1..7 in both aux ($7EC300) and live ($7EC500)."""
        assert len(colors_1_to_7) == 7
        for i, col in enumerate(colors_1_to_7, start=1):
            off = row * 0x20 + i * 2
            self.put_word(0x7EC300 + off, col)
            self.put_word(0x7EC500 + off, (col ^ live_delta) & 0x7FFF)

    def seed_spr_pal(self, sp: int, colors_9_to_15: list[int]):
        """Seed Sprite row (0..7) right half colors 9..15 in both aux and live."""
        assert len(colors_9_to_15) == 7
        for i, col in enumerate(colors_9_to_15, start=9):
            off = 0x100 + sp * 0x20 + i * 2
            self.put_word(0x7EC300 + off, col)
            self.put_word(0x7EC500 + off, col)

    def read_spr_right(self, sp: int, buf_base: int = 0x7EC500) -> list[int]:
        return [self.get_word(buf_base + 0x100 + sp * 0x20 + c * 2) for c in range(9, 16)]

    def call_jsl(self, addr: int, *, a=0, x=0, y=0, db=0x06, m8=True, x8=True, limit=2000):
        cpu = self.cpu
        cpu.mf = m8
        cpu.xf = x8
        cpu.a = a & (0xFF if m8 else 0xFFFF)
        cpu.x = x & (0xFF if x8 else 0xFFFF)
        cpu.y = y & (0xFF if x8 else 0xFFFF)
        cpu.db = db
        cpu.k = addr >> 16
        cpu.pc = addr & 0xFFFF
        sp = cpu.sp
        # Synthetic RTL return sentinel at $00:7000 (RTL adds +1 to pushed PC -> push $6FFF)
        self.put(sp, 0x00)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        cpu.sp = sp - 3
        self.writes.clear()
        self.bad_writes.clear()
        for _ in range(limit):
            if ((cpu.k << 16) | cpu.pc) == 0x007000:
                assert not self.bad_writes, f"Non-WRAM writes: {self.bad_writes}"
                assert cpu.sp == sp, f"Stack imbalance: got {cpu.sp:#x}, expected {sp:#x}"
                return
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"Instruction limit exceeded at ${cpu.k:02X}:{cpu.pc:04X}")

    def run_until(self, start_addr: int, stop_addrs: set[int], *, a=0, x=0, y=0, db=0x1B, m8=False, x8=False, limit=2000) -> int:
        cpu = self.cpu
        cpu.mf = m8
        cpu.xf = x8
        cpu.a = a & (0xFF if m8 else 0xFFFF)
        cpu.x = x & (0xFF if x8 else 0xFFFF)
        cpu.y = y & (0xFF if x8 else 0xFFFF)
        cpu.db = db
        cpu.k = start_addr >> 16
        cpu.pc = start_addr & 0xFFFF
        sp = cpu.sp
        self.writes.clear()
        self.bad_writes.clear()
        for _ in range(limit):
            cur = (cpu.k << 16) | cpu.pc
            if cur in stop_addrs:
                assert not self.bad_writes, f"Non-WRAM writes: {self.bad_writes}"
                assert cpu.sp == sp, f"Stack imbalance at ${cur:06X}: {cpu.sp:#x} vs {sp:#x}"
                return cur
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"Instruction limit exceeded at ${cpu.k:02X}:{cpu.pc:04X}")


class LiftablesPaletteCompiledTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory(prefix="oos-liftables-test-")
        tmp = Path(cls.tmp.name)

        # Compile Lakesnes 65816 CPU shared library
        lakesnes = find_lakesnes()
        libpath = tmp / "cpu.dylib"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2",
             str(lakesnes / "snes" / "cpu.c"),
             str(lakesnes / "snes" / "statehandler.c"),
             "-o", str(libpath)],
            check=True,
        )
        cls.lib = C.CDLL(str(libpath))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        # Build synthetic 2MB LoROM seeded with exact vanilla bytes at all 9 hook sites + $06AACA table
        img = bytearray(0x200000)
        patches = {
            0x06AACA: bytes([0x0C, 0x0C, 0x0C, 0x00, 0x00, 0x00]),
            0x0681A9: bytes.fromhex("B9 CA AA 9D 50 0F"),
            0x06AB38: bytes.fromhex("1D CA AA 91 90"),
            0x06AB79: bytes.fromhex("B9 6E AB 9D 50 0F"),
            0x1BBDC4: bytes.fromhex("C9 2A 07 D0 23"),
            0x1BBE36: bytes.fromhex("C9 2A 07 F0 52"),
            0x1BBEAF: bytes.fromhex("A0 C7 0D C9 2A 07 D0 03 A0 C8 0D"),
            0x1BBFE3: bytes.fromhex(
                "A0 C7 0D C9 36 00 F0 1D A0 C8 0D C9 2A 07 F0 15 "
                "A0 CA 0D C9 0F 02 F0 0D C9 39 02 F0 08 C9 01 01 D0 22 A0 C6 0D"
            ),
            0x1BC055: bytes.fromhex("A0 C7 0D C9 36 00 F0 AB"),
            0x1BC176: bytes.fromhex(
                "A0 C7 0D A2 02 00 C9 36 00 F0 16 A2 04 00 A0 C8 0D C9 2A 07 F0 0B "
                "C9 7E 03 D0 45 A0 C5 0D A2 03 00"
            ),
        }
        for snes_addr, raw in patches.items():
            pc = snes_to_pc(snes_addr)
            img[pc:pc + len(raw)] = raw

        rom_file = tmp / "fixture.sfc"
        rom_file.write_bytes(img)
        wrapper = tmp / "fixture.asm"
        wrapper.write_text(
            f'lorom\norg $348000\nincsrc "{ASM_PATH}"\n',
            encoding="utf-8",
        )
        proc = subprocess.run(
            [find_asar(), "--no-title-check", "--fix-checksum=off",
             "--symbols=wla", f"--symbols-path={tmp / 'fixture.sym'}",
             str(wrapper), str(rom_file)],
            capture_output=True, text=True,
        )
        assert proc.returncode == 0, proc.stdout + proc.stderr
        cls.rom = rom_file.read_bytes()
        cls.labels = {
            m[3]: (int(m[1], 16) << 16) | int(m[2], 16)
            for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$",
                                 (tmp / "fixture.sym").read_text())
        }

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def make_harness(self) -> Harness:
        h = Harness(self.lib, self.rom, self.labels)
        self.addCleanup(h.close)
        # Seed representative DP scratch bytes to prove zero DP clobber
        for i in range(0x10):
            h.put(i, 0xA0 + i)
        return h

    def assert_dp_preserved(self, h: Harness):
        for i in range(0x10):
            self.assertEqual(h.get(i), 0xA0 + i, f"DP ${i:02X} clobbered")

    # ------------------------------------------------------------------
    # 1. Dark World / Eon Abyss ($40-$7F): Core bug fix tests
    # ------------------------------------------------------------------
    def test_dw_small_light_rock_uses_sp0_and_syncs_sage_green_from_bg5(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)       # outdoors
        h.put(0x8A, 0x50)       # DW $50 (Eon Abyss, MainPal=1)
        h.put(0x0ABD, 0x00)     # no translucency
        h.put(0x15, 0x05)

        # DW MainPal=1 BG[5] (Light Rock/Skull) and BG[6] (DW Bush)
        bg5 = [0x0C63, 0x21C9, 0x366E, 0x4F34, 0x1565, 0x2669, 0x3274]
        bg6 = [0x0C63, 0x2B4D, 0x194C, 0x21D1, 0x0965, 0x1E6E, 0x1A53]
        h.seed_bg_pal(5, bg5)
        h.seed_bg_pal(6, bg6)
        # Seed stale muddy-brown Env[8] in SP6 and stale Env[9] in SP0
        env8 = [0x08C4, 0x21C9, 0x194C, 0x21D1, 0x12B7, 0x4F34, 0x366E]
        env9 = [0x0C63, 0x08C4, 0x196E, 0x29F2, 0x29F2, 0x366E, 0x21C9]
        h.seed_spr_pal(6, env8)
        h.seed_spr_pal(0, env9)

        # Lift Small Light Rock ($0DB0 = 1) into sprite slot X = 4
        h.call_jsl(self.labels["Liftables_InitPalette"], x=4, y=1, db=0x06)

        # MUST assign SP0 ($00), NOT SP6 ($0C)!
        self.assertEqual(h.get(0x0F50 + 4), 0x00)
        self.assertEqual(h.cpu.x, 4)
        self.assertEqual(h.cpu.y, 1)
        self.assertEqual(h.cpu.db, 0x06)
        self.assertTrue(h.cpu.mf and h.cpu.xf)
        self.assert_dp_preserved(h)

        # SP0[9,11,12] MUST match BG[5][1,3,4] (#181818, #709868, #A0C898) in BOTH live & aux!
        sp0_live = h.read_spr_right(0, 0x7EC500)
        sp0_aux = h.read_spr_right(0, 0x7EC300)
        self.assertEqual([sp0_live[0], sp0_live[2], sp0_live[3]], [bg5[0], bg5[2], bg5[3]])
        self.assertEqual(sp0_aux, sp0_live)
        # SP6 (DW Bush palette) MUST be completely untouched!
        self.assertEqual(h.read_spr_right(6, 0x7EC500), env8)
        # $15 incremented once because SP0 changed
        self.assertEqual(h.get(0x15), 0x06)

        # Second call (e.g., draw frame) must be lazy: NO extra $15 increment!
        h.put_word(0x90, 0x08B0)
        h.call_jsl(self.labels["Liftables_ApplyDrawPalette"], a=0x30, x=1, y=3, db=0x06)
        self.assertEqual(h.cpu.a & 0xFF, 0x30)         # high nibble $30 | SP0 $00
        self.assertEqual(h.get(0x08B0 + 3), 0x30)
        self.assertEqual(h.get(0x15), 0x06)            # NOT incremented again!

    def test_dw_bush_and_light_rock_coexist_without_collision(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x5E)       # DW $5E (MainPal=2: slate-lavender bush, mint-green rock)
        h.put(0x0ABD, 0x00)
        h.put(0x15, 0x01)

        bg5 = [0x14E6, 0x3A0A, 0x4AEF, 0x5FD6, 0x158D, 0x19CF, 0x7DBF]
        bg6 = [0x14A5, 0x3546, 0x45EE, 0x5A54, 0x39AC, 0x5671, 0x4A2E]
        h.seed_bg_pal(5, bg5)
        h.seed_bg_pal(6, bg6)
        h.seed_spr_pal(0, [0] * 7)
        h.seed_spr_pal(6, [0] * 7)

        # Lift rock (slot 2, Y=1 -> SP0) and cut/lift bush (slot 3, Y=2 -> SP6)
        h.call_jsl(self.labels["Liftables_InitPalette"], x=2, y=1, db=0x06)
        h.call_jsl(self.labels["Liftables_InitPalette"], x=3, y=2, db=0x06)

        self.assertEqual(h.get(0x0F50 + 2), 0x00)      # DW Light Rock -> SP0
        self.assertEqual(h.get(0x0F50 + 3), 0x0C)      # DW Bush -> SP6
        sp0 = h.read_spr_right(0)
        sp6 = h.read_spr_right(6)
        self.assertEqual([sp0[0], sp0[2], sp0[3]], [bg5[0], bg5[2], bg5[3]])
        self.assertEqual([sp6[0], sp6[2], sp6[3]], [bg6[0], bg6[2], bg6[3]])
        self.assertEqual(h.get(0x15), 0x03)

    def test_dw_small_heavy_rock_syncs_from_bg2(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x48)       # DW $48 (Heavy Rock $0239, MainPal=2 BG[2])
        h.put(0x0ABD, 0x00)
        bg2 = [0x0C63, 0x0C87, 0x3546, 0x112D, 0x158D, 0x19CF, 0x1D90]
        h.seed_bg_pal(2, bg2)
        h.seed_spr_pal(0, [0x7FFF] * 7)

        h.call_jsl(self.labels["Liftables_InitPalette"], x=1, y=5, db=0x06)
        self.assertEqual(h.get(0x0F50 + 1), 0x00)
        sp0 = h.read_spr_right(0)
        # DW Heavy Rock uses BG[2][1,2,4] -> SP0[9,11,12]
        self.assertEqual([sp0[0], sp0[2], sp0[3]], [bg2[0], bg2[1], bg2[3]])

    def test_dw_sign_syncs_sp6_wood_from_bg2(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x5B)       # DW $5B (Sign $017D)
        bg2 = [0x0C63, 0x190C, 0x2192, 0x3677, 0x0965, 0x1E6E, 0x190C]
        h.seed_bg_pal(2, bg2)
        h.seed_spr_pal(6, [0] * 7)

        h.call_jsl(self.labels["Liftables_InitPalette"], x=7, y=0, db=0x06)
        self.assertEqual(h.get(0x0F50 + 7), 0x0C)
        sp6 = h.read_spr_right(6)
        self.assertEqual([sp6[0], sp6[4], sp6[5]], [bg2[0], bg2[2], bg2[3]])

    def test_dw_translucency_guard_preserves_sp0_and_falls_back_to_sp6(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x50)
        h.put(0x0ABD, 0x01)     # translucency active
        h.put(0x15, 0x09)
        sentinel = [0x1111, 0x2222, 0x3333, 0x4444, 0x5555, 0x6666, 0x7777]
        h.seed_spr_pal(0, sentinel)
        h.seed_bg_pal(5, [0x0101] * 7)

        h.call_jsl(self.labels["Liftables_InitPalette"], x=2, y=1, db=0x06)
        self.assertEqual(h.get(0x0F50 + 2), 0x0C)
        self.assertEqual(h.read_spr_right(0), sentinel)
        self.assertEqual(h.get(0x15), 0x09)

    # ------------------------------------------------------------------
    # 2. Light World ($00-$3F) & Special Overworld ($80-$BF)
    # ------------------------------------------------------------------
    def test_lw_snow_and_sw_packed_palettes_sync_correctly(self):
        for area in (0x04, 0x84, 0x8C, 0xB1):
            with self.subTest(area=f"${area:02X}"):
                h = self.make_harness()
                h.put(0x1B, 0x00)
                h.put(0x8A, area)
                h.put(0x0ABD, 0x00)
                bg2 = [0x14A5, 0x10E7, 0x192A, 0x218D, 0x19C6, 0x2669, 0x25CF]
                bg4 = [0x0884, 0x0CC7, 0x1509, 0x196C, 0x1509, 0x7BDC, 0x21AF]
                bg5 = [0x1084, 0x562B, 0x6734, 0x6734, 0x77B9, 0x7BDC, 0x258E]
                bg6 = [0x1084, 0x4DB1, 0x72D3, 0x7FE0, 0x77BA, 0x7BDC, 0x77BA]
                h.seed_bg_pal(2, bg2)
                h.seed_bg_pal(4, bg4)
                h.seed_bg_pal(5, bg5)
                h.seed_bg_pal(6, bg6)
                h.seed_spr_pal(0, [0] * 7)
                h.seed_spr_pal(6, [0] * 7)

                # Small Light Rock (Y=1 -> SP6: 9=BG5[1], 10=BG5[2], 14=BG5[4], 15=BG5[3])
                h.call_jsl(self.labels["Liftables_InitPalette"], x=0, y=1, db=0x06)
                self.assertEqual(h.get(0x0F50 + 0), 0x0C)
                sp6 = h.read_spr_right(6)
                self.assertEqual([sp6[0], sp6[1], sp6[5], sp6[6]], [bg5[0], bg5[1], bg5[3], bg5[2]])

                # Light Bush (Y=2 -> SP6: 9=BG6[1], 11=BG6[5], 12=BG6[6], 13=BG6[7])
                h.call_jsl(self.labels["Liftables_InitPalette"], x=1, y=2, db=0x06)
                self.assertEqual(h.get(0x0F50 + 1), 0x0C)
                sp6 = h.read_spr_right(6)
                self.assertEqual([sp6[0], sp6[2], sp6[3], sp6[4]], [bg6[0], bg6[4], bg6[5], bg6[6]])

                # Sign (Y=0 -> SP6: 9=BG4[1], 13=BG4[4])
                h.call_jsl(self.labels["Liftables_InitPalette"], x=2, y=0, db=0x06)
                self.assertEqual(h.get(0x0F50 + 2), 0x0C)
                sp6 = h.read_spr_right(6)
                self.assertEqual([sp6[0], sp6[4]], [bg4[0], bg4[3]])

                # Small Heavy Rock (Y=5 -> SP0: 9=BG2[1], 10=BG2[2], 14=BG2[4], 15=BG2[3])
                h.call_jsl(self.labels["Liftables_InitPalette"], x=3, y=5, db=0x06)
                self.assertEqual(h.get(0x0F50 + 3), 0x00)
                sp0 = h.read_spr_right(0)
                self.assertEqual([sp0[0], sp0[1], sp0[5], sp0[6]], [bg2[0], bg2[1], bg2[3], bg2[2]])

                # Big Light Rock (Y=6 -> SP6) & Big Heavy Rock (Y=7 -> SP0) via Gigantic entry
                h.call_jsl(self.labels["Liftables_ApplyGiganticPalette"], x=5, y=6, db=0x06)
                self.assertEqual(h.get(0x0F50 + 5), 0x0C)
                h.call_jsl(self.labels["Liftables_ApplyGiganticPalette"], x=6, y=7, db=0x06)
                self.assertEqual(h.get(0x0F50 + 6), 0x00)
                self.assert_dp_preserved(h)

    def test_live_and_aux_fade_buffers_copied_independently(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x5B)
        bg5_aux = [0x0C63, 0x21C9, 0x366E, 0x4F34, 0x1565, 0x2669, 0x3274]
        h.seed_bg_pal(5, bg5_aux, live_delta=0x0421)
        h.seed_spr_pal(0, [0] * 7)

        h.call_jsl(self.labels["Liftables_InitPalette"], x=0, y=1, db=0x06)
        sp0_aux = h.read_spr_right(0, 0x7EC300)
        sp0_live = h.read_spr_right(0, 0x7EC500)
        self.assertEqual([sp0_aux[0], sp0_aux[2], sp0_aux[3]], [bg5_aux[0], bg5_aux[2], bg5_aux[3]])
        self.assertEqual([sp0_live[0], sp0_live[2], sp0_live[3]],
                         [(c ^ 0x0421) & 0x7FFF for c in (bg5_aux[0], bg5_aux[2], bg5_aux[3])])

    def test_indoors_preserves_exact_vanilla_palettes_and_touches_zero_cgram(self):
        expected = [0x0C, 0x0C, 0x0C, 0x00, 0x00, 0x00, 0x0C, 0x00]
        h = self.make_harness()
        h.put(0x1B, 0x01)       # indoors!
        h.put(0x8A, 0x50)       # even with DW bit set in $8A
        h.put(0x15, 0x04)
        sp0_orig = [0x1001, 0x1002, 0x1003, 0x1004, 0x1005, 0x1006, 0x1007]
        sp6_orig = [0x2001, 0x2002, 0x2003, 0x2004, 0x2005, 0x2006, 0x2007]
        h.seed_spr_pal(0, sp0_orig)
        h.seed_spr_pal(6, sp6_orig)
        h.seed_bg_pal(5, [0x7777] * 7)
        h.seed_bg_pal(6, [0x7777] * 7)

        for y, exp in enumerate(expected):
            h.call_jsl(self.labels["Liftables_InitPalette"], x=y, y=y, db=0x06)
            self.assertEqual(h.get(0x0F50 + y), exp)
        self.assertEqual(h.read_spr_right(0, 0x7EC500), sp0_orig)
        self.assertEqual(h.read_spr_right(6, 0x7EC500), sp6_orig)
        self.assertEqual(h.get(0x15), 0x04)
        self.assert_dp_preserved(h)

    def test_draw_hook_preserves_oam_high_nibble_and_registers(self):
        h = self.make_harness()
        h.put(0x1B, 0x00)
        h.put(0x8A, 0x50)
        h.put_word(0x90, 0x08B4)
        h.seed_bg_pal(5, [0x0C63, 0x21C9, 0x366E, 0x4F34, 0x1565, 0x2669, 0x3274])

        # OAM high nibble $F0 (V/H flip + priority 3) + DW Small Light Rock (X=1 -> $00)
        h.call_jsl(self.labels["Liftables_ApplyDrawPalette"], a=0xF0, x=1, y=3, db=0x06)
        self.assertEqual(h.cpu.a & 0xFF, 0xF0)
        self.assertEqual(h.get(0x08B4 + 3), 0xF0)
        self.assertEqual(h.cpu.x, 1)
        self.assertEqual(h.cpu.y, 3)
        self.assertEqual(h.cpu.db, 0x06)

        # OAM high nibble $20 + DW Bush (X=2 -> $0C) => $2C
        h.call_jsl(self.labels["Liftables_ApplyDrawPalette"], a=0x20, x=2, y=3, db=0x06)
        self.assertEqual(h.cpu.a & 0xFF, 0x2C)
        self.assertEqual(h.get(0x08B4 + 3), 0x2C)
        self.assert_dp_preserved(h)

    # ------------------------------------------------------------------
    # 3. Bank $1B Revealed-Tile16 Pure-ASM Fixes
    # ------------------------------------------------------------------
    def test_bank1b_small_liftable_dispatch(self):
        stops = {0x1BC008, 0x1BC027}
        cases = [
            # (area, tile16, expected_stop, expected_reveal_y)
            (0x15, 0x0036, 0x1BC008, 0x0DC7),  # LW bush -> $0DC7
            (0x5B, 0x0036, 0x1BC008, 0x0DC7),  # DW bush -> $0DC7
            (0x63, 0x0036, 0x1BC008, 0x0172),  # DW $63 (Sheet $F8) bush -> $0172 DW grass!
            (0x15, 0x020F, 0x1BC008, 0x0DCA),  # LW small light rock -> $0DCA
            (0x50, 0x020F, 0x1BC008, 0x0DCA),  # DW small light rock -> $0DCA
            (0x48, 0x0239, 0x1BC008, 0x0DCA),  # DW small heavy rock -> $0DCA
            (0x15, 0x0101, 0x1BC008, 0x0DC6),  # LW sign -> $0DC6
            (0x5B, 0x017D, 0x1BC008, 0x0DC6),  # DW sign $017D -> $0DC6 (FIXED!)
            (0x63, 0x017D, 0x1BC008, 0x0172),  # DW $6B (parent $63, Sheet $F8) sign -> $0172!
            (0x22, 0x072A, 0x1BC027, None),    # LW $22 brick wall $072A NOT matched!
            (0x15, 0x0034, 0x1BC027, None),    # plain grass NOT matched!
        ]
        for area, tid, exp_stop, exp_y in cases:
            with self.subTest(area=f"${area:02X}", tid=f"${tid:04X}"):
                h = self.make_harness()
                h.put(0x8A, area)
                dest = h.run_until(0x1BBFE3, stops, a=tid, x=0x0420, y=0x9999, m8=False, x8=False)
                self.assertEqual(dest, exp_stop)
                self.assertEqual(h.cpu.a, tid)
                self.assertEqual(h.cpu.x, 0x0420)
                if exp_y is not None:
                    self.assertEqual(h.cpu.y, exp_y)

    def test_bank1b_bush_cut_dash_and_bomb_dw63_and_072a_guard(self):
        # 1) OverworldTileAction_Bush reveal ($1BBEAF -> $1BBEBA)
        for area, exp_y in ((0x15, 0x0DC7), (0x5B, 0x0DC7), (0x63, 0x0172), (0x80, 0x0DC7)):
            h = self.make_harness()
            h.put(0x8A, area)
            dest = h.run_until(0x1BBEAF, {0x1BBEBA}, a=0x0036, x=0x0120, m8=False, x8=False)
            self.assertEqual(dest, 0x1BBEBA)
            self.assertEqual(h.cpu.y, exp_y)
            self.assertEqual(h.cpu.a, 0x0036)
            self.assertEqual(h.cpu.x, 0x0120)

        # 2) Pegasus dash bush check ($1BC055 -> $1BC008 or $1BC05D)
        for area, tid, exp_stop, exp_y in (
            (0x15, 0x0036, 0x1BC008, 0x0DC7),
            (0x63, 0x0036, 0x1BC008, 0x0172),
            (0x22, 0x072A, 0x1BC05D, None),
        ):
            h = self.make_harness()
            h.put(0x8A, area)
            dest = h.run_until(0x1BC055, {0x1BC008, 0x1BC05D}, a=tid, x=0x0240, m8=False, x8=False)
            self.assertEqual(dest, exp_stop)
            if exp_y is not None:
                self.assertEqual(h.cpu.y, exp_y)

        # 3) Bomb tile match ($1BC176 -> $1BC197 greenery or $1BC1D6 check_for_cave)
        for area, tid, exp_stop, exp_y, exp_x in (
            (0x15, 0x0036, 0x1BC197, 0x0DC7, 0x0002),
            (0x63, 0x0036, 0x1BC197, 0x0172, 0x0002),
            (0x15, 0x037E, 0x1BC197, 0x0DC5, 0x0003),
            (0x22, 0x072A, 0x1BC1D6, None, None),
        ):
            h = self.make_harness()
            h.put(0x8A, area)
            dest = h.run_until(0x1BC176, {0x1BC197, 0x1BC1D6}, a=tid, m8=False, x8=False)
            self.assertEqual(dest, exp_stop)
            if exp_y is not None:
                self.assertEqual(h.cpu.y, exp_y)
                self.assertEqual(h.cpu.x, exp_x)

        # 4) Powder ($1BBDC4 -> $1BBDEC) & Sword ($1BBE36 -> $1BBE3B) skip $072A
        h = self.make_harness()
        self.assertEqual(h.run_until(0x1BBDC4, {0x1BBDEC, 0x1BBDC9}, a=0x072A, m8=False, x8=False), 0x1BBDEC)
        self.assertEqual(h.run_until(0x1BBE36, {0x1BBE3B, 0x1BBE8D}, a=0x072A, m8=False, x8=False), 0x1BBE3B)


if __name__ == "__main__":
    unittest.main(verbosity=2)
