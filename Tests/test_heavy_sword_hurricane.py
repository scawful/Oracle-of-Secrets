#!/usr/bin/env python3
"""Unit & real-65816 compiled execution tests for Reforged Heavy Sword Hurricane Spin.

Verifies scawful's approved Option 1 mechanics in Items/heavy_sword.asm and Core/symbols.asm:
1. Volatile WRAM allocation ($7FF3D0-$7FF3D2 < $7FF400), zero new SRAM bytes.
2. Exact vanilla hook preimages at $07:A879, $07:A882, $07:A8CA, $07:8102, and $07:8020 RTL.
3. Real compiled 65816 execution (via asar + lakesnes snes/cpu.c):
   - Eligibility gating: Story Blade & Broken Heavy Blade skip Hurricane Spin;
     Reforged Heavy Sword activates it.
   - 4-revolution cap (max 4 extra revs = 5 total spins) and flat 16 MP (normal)
     / 8 MP floor (half & quarter magic) cost.
   - Out-of-magic error SFX ($3C -> $012E) without triggering dizzy on single spin,
     and with dizzy (without clobbering $3C) if >= 1 extra rev completed.
   - Half-speed alternating-frame steering ($1A bit 0) through Bank $07 $B64F/$D077
     (Y=0) via the $07:8020 RTL trampoline, preserving DBR=$07, M/X=8, and stack.
   - Mid-spin state transition safety (pit/swim/ledge/victory spin).
   - 45-frame Wind Waker dizzy recovery lock: input stripping ($F0/$F2/$F4/$F6),
     facing wobble (0 -> 4 -> 2 -> 6 every 6 frames), and safety clears on
     damage/recoil/transition/doorway/pit/module change.
"""

from __future__ import annotations

import ctypes as C
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
HEAVY_SWORD_ASM = ROOT / "Items" / "heavy_sword.asm"
SWORD_SLOTS_ASM = ROOT / "Menu" / "menu_sword_slots.asm"
SYMBOLS_ASM = ROOT / "Core" / "symbols.asm"
SRAM_ASM = ROOT / "Core" / "sram.asm"

LAKESNES_CANDIDATES = (
    ROOT.parent / "lakesnes",
    Path.home() / "src" / "hobby" / "lakesnes",
)

# WRAM addresses from Core/symbols.asm
ADDR_HURRICANE_ACTIVE = 0x7FF3D0
ADDR_HURRICANE_REVS = 0x7FF3D1
ADDR_DIZZY_TIMER = 0x7FF3D2

# SRAM addresses from Core/sram.asm
ADDR_SWORD = 0x7EF359
ADDR_MAGIC_POWER = 0x7EF36E
ADDR_MAGIC_USAGE = 0x7EF37B
ADDR_SWORD_STORY = 0x7EF3BC
ADDR_SWORD_FLAGS = 0x7EF3BD

FLAG_HEAVY_OWNED = 0x01
FLAG_HEAVY_EQUIPPED = 0x02
FLAG_HEAVY_REFORGED = 0x04
FLAG_INITIALIZED = 0x80

# Vanilla hook preimages (unheadered LoROM)
PREIMAGES = {
    0x079C7D: bytes([0xAF, 0x59, 0xF3, 0x7E]),                # LDA.l $7EF359
    0x079D21: bytes([0xBD, 0xBF, 0x9C, 0x85, 0x3D]),          # LDA.w $9CBF,X : STA.b $3D
    0x06F18B: bytes([0xAF, 0x5A, 0xF3, 0x7E]),                # LDA.l $7EF35A
    0x0596CB: bytes([0xAF, 0x5A, 0xF3, 0x7E]),                # LDA.l $7EF35A
    0x078020: bytes([0x6B]),                                  # Link_Main RTL trampoline
    0x078102: bytes([0xA5, 0x5D, 0x0A, 0xAA]),                # LDA $5D : ASL A : TAX
    0x07A879: bytes([0x64, 0x67, 0x22, 0x45, 0xE2, 0x07]),    # STZ $67 : JSL $07E245
    0x07A882: bytes([0xA9, 0x03, 0x85, 0x5D]),                # LDA #$03 : STA $5D
    0x07A8CA: bytes([0xA9, 0x00, 0x85, 0x5D]),                # LDA #$00 : STA $5D
}


def snes_to_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + ((addr & 0xFFFF) - 0x8000)


class Cpu(C.Structure):
    _fields_ = (
        [(n, C.c_void_p) for n in ("mem", "read", "write", "idle")]
        + [(n, C.c_uint16) for n in ("a", "x", "y", "sp", "pc", "dp")]
        + [(n, C.c_uint8) for n in ("k", "db")]
        + [
            (n, C.c_bool)
            for n in (
                "c", "z", "v", "n", "i", "d", "xf", "mf", "e",
                "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted",
            )
        ]
    )


class CpuHarness:
    """Minimal 65816 execution harness around lakesnes snes/cpu.c."""

    def __init__(self, lib: C.CDLL, rom: bytes, labels: dict[str, int]):
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.stubs: dict[int, tuple[str, int]] = {}
        self.calls: list[tuple[str, dict[str, int]]] = []
        self.bad_writes: list[tuple[int, int]] = []

        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(
            lambda _, a: self._read(a)
        )
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(
            lambda _, a, v: self._write(a, v)
        )
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self._ptr = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self._ptr.contents
        self.reset_cpu()

    def close(self) -> None:
        if self._ptr:
            self.lib.cpu_free(self._ptr)
            self._ptr = None

    def reset_cpu(self, db: int = 0x07, m8: bool = True, x8: bool = True) -> None:
        for flag in (
            "c", "z", "v", "n", "i", "d", "e",
            "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted",
        ):
            setattr(self.cpu, flag, False)
        self.cpu.mf = m8
        self.cpu.xf = x8
        self.cpu.dp = 0
        self.cpu.sp = 0x01FF
        self.cpu.a = 0
        self.cpu.x = 0
        self.cpu.y = 0
        self.cpu.db = db

    @staticmethod
    def _ram_offset(addr: int) -> int | None:
        bank = addr >> 16
        lo = addr & 0xFFFF
        if bank in (0x7E, 0x7F):
            return addr - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def _read(self, addr: int) -> int:
        if addr in self.stubs:
            return self.stubs[addr][1]
        off = self._ram_offset(addr)
        if off is not None:
            return self.ram[off]
        if addr & 0x8000:
            pc = snes_to_pc(addr)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, addr: int, val: int) -> None:
        off = self._ram_offset(addr)
        if off is None:
            self.bad_writes.append((addr, val))
            return
        self.ram[off] = val & 0xFF

    def get(self, addr: int) -> int:
        return self._read(addr)

    def put(self, addr: int, val: int) -> None:
        self._write(addr, val & 0xFF)

    def add_stub(self, addr: int, name: str, opcode: int) -> None:
        """Register an RTS ($60) or RTL ($6B) stub at a SNES address."""
        self.stubs[addr] = (name, opcode)

    def call_jsl(self, target: int, max_steps: int = 5000) -> None:
        """Invoke a JSL/RTL routine at `target` and verify exact stack return."""
        sp0 = self.cpu.sp
        sentinel_bank = 0x07
        sentinel_pc = 0x7000
        # Push return address (sentinel - 1) in exact 65816 JSL order: PBR, PCH, PCL
        self.put(sp0, sentinel_bank)
        self.put(sp0 - 1, (sentinel_pc - 1) >> 8)
        self.put(sp0 - 2, (sentinel_pc - 1) & 0xFF)
        self.cpu.sp = sp0 - 3
        self.cpu.k = target >> 16
        self.cpu.pc = target & 0xFFFF

        for _ in range(max_steps):
            pc24 = (self.cpu.k << 16) | self.cpu.pc
            if pc24 == ((sentinel_bank << 16) | sentinel_pc):
                if self.cpu.sp != sp0:
                    raise AssertionError(f"SP drift: expected {sp0:#06x}, got {self.cpu.sp:#06x}")
                if self.bad_writes:
                    raise AssertionError(f"Unexpected non-WRAM writes: {self.bad_writes}")
                return
            if pc24 in self.stubs:
                name, _ = self.stubs[pc24]
                self.calls.append(
                    (
                        name,
                        {
                            "a": self.cpu.a & 0xFF,
                            "x": self.cpu.x & 0xFF,
                            "y": self.cpu.y & 0xFF,
                            "db": self.cpu.db,
                            "mf": int(self.cpu.mf),
                            "xf": int(self.cpu.xf),
                            "67": self.get(0x67),
                            "3c": self.get(0x3C),
                        },
                    )
                )
            self.lib.cpu_runOpcode(self._ptr)
        raise AssertionError(f"Instruction ceiling reached at ${self.cpu.k:02X}:{self.cpu.pc:04X}")


def _find_lakesnes() -> Path | None:
    for candidate in LAKESNES_CANDIDATES:
        if (candidate / "snes" / "cpu.c").is_file() and (candidate / "snes" / "statehandler.c").is_file():
            return candidate
    return None


class HeavySwordHurricaneContractTest(unittest.TestCase):
    """Static source & allocation contract checks (always run)."""

    def test_volatile_wram_allocation_and_zero_sram_delta(self):
        symbols_text = SYMBOLS_ASM.read_text(encoding="utf-8")
        self.assertIn("HeavySword_HurricaneActive = $7FF3D0", symbols_text)
        self.assertIn("HeavySword_HurricaneRevs   = $7FF3D1", symbols_text)
        self.assertIn("HeavySword_DizzyTimer      = $7FF3D2", symbols_text)
        self.assertIn("assert HeavySword_DizzyTimer < $7FF400", symbols_text)

        # Ensure zero Hurricane symbols were added to SRAM
        sram_text = SRAM_ASM.read_text(encoding="utf-8")
        self.assertNotIn("Hurricane", sram_text)
        self.assertNotIn("DizzyTimer", sram_text)

    def test_hook_sites_and_preimage_assertions_present(self):
        text = HEAVY_SWORD_ASM.read_text(encoding="utf-8")
        for expected in (
            "org $07A879",
            "assert read4($07A879) == $45226764",
            "assert read2($07A87D) == $07E2",
            "assert read1($078020) == $6B",
            "JSL HeavySword_HurricaneMove",
            "org $07A882",
            "assert read4($07A882) == $5D8503A9",
            "JSL HeavySword_HurricaneKeepState",
            "org $07A8CA",
            "assert read4($07A8CA) == $5D8500A9",
            "JSL HeavySword_HurricaneEndCheck",
            "org $078102",
            "assert read4($078102) == $AA0A5DA5",
            "JSL HeavySword_ControlFrameHook",
        ):
            self.assertIn(expected, text)


class HeavySwordHurricaneCompiledCpuTest(unittest.TestCase):
    """Real Asar compilation + lakesnes 65816 CPU execution tests."""

    tmpdir: tempfile.TemporaryDirectory[str]
    lib: C.CDLL
    rom: bytes
    labels: dict[str, int]

    @classmethod
    def setUpClass(cls) -> None:
        asar_bin = shutil.which("asar")
        lakesnes = _find_lakesnes()
        cc_bin = shutil.which("cc")
        if not asar_bin or not lakesnes or not cc_bin:
            raise unittest.SkipTest(
                f"Compiled CPU test requires asar ({asar_bin}), cc ({cc_bin}), and lakesnes ({lakesnes})"
            )

        cls.tmpdir = tempfile.TemporaryDirectory(prefix="oos-heavy-hurricane-")
        work = Path(cls.tmpdir.name)

        # Compile lakesnes 65816 core
        dll_path = work / "cpu.dylib"
        subprocess.run(
            [
                cc_bin, "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes" / "cpu.c"),
                str(lakesnes / "snes" / "statehandler.c"),
                "-o", str(dll_path),
            ],
            check=True,
            capture_output=True,
        )
        cls.lib = C.CDLL(str(dll_path))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]

        # Create minimal 2 MiB LoROM seeded with exact vanilla preimages
        raw = bytearray(0x200000)
        for addr, payload in PREIMAGES.items():
            pc = snes_to_pc(addr)
            raw[pc : pc + len(payload)] = payload
        image = work / "fixture.sfc"
        image.write_bytes(raw)

        # Assemble real Menu/menu_sword_slots.asm + Items/heavy_sword.asm in Bank $2B
        asm_path = work / "harness.asm"
        asm_path.write_text(
            f"""lorom
Sword                      = $7EF359
Armor                      = $7EF35B
SwordStoryBlade            = $7EF3BC
SwordSlotFlags             = $7EF3BD
!SwordSlot_HeavyOwned      = $01
!SwordSlot_HeavyEquipped   = $02
!SwordSlot_HeavyReforged   = $04
!SwordSlot_Initialized     = $80
HeavySword_HurricaneActive = $7FF3D0
HeavySword_HurricaneRevs   = $7FF3D1
HeavySword_DizzyTimer      = $7FF3D2
Tunic_SetWorn              = $2B8000

org $2BC000
incsrc "{SWORD_SLOTS_ASM}"
incsrc "{HEAVY_SWORD_ASM}"
""",
            encoding="utf-8",
        )
        proc = subprocess.run(
            [asar_bin, "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm_path), str(image)],
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise AssertionError(f"Asar assembly failed:\n{proc.stdout}\n{proc.stderr}")

        cls.rom = image.read_bytes()
        sym_text = image.with_suffix(".sym").read_text(encoding="utf-8")
        cls.labels = {
            m.group(3): (int(m.group(1), 16) << 16) | int(m.group(2), 16)
            for m in re.finditer(r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4})\s+(\S+)$", sym_text)
        }

    @classmethod
    def tearDownClass(cls) -> None:
        if hasattr(cls, "tmpdir"):
            cls.tmpdir.cleanup()

    def make_harness(self) -> CpuHarness:
        h = CpuHarness(self.lib, self.rom, self.labels)
        self.addCleanup(h.close)
        # Stub Bank $07 routines called by HeavySword_HurricaneMove
        h.add_stub(0x07B64F, "Link_HandleDiagonalCollision", 0x60)  # RTS
        h.add_stub(0x07D077, "TileDetect_MainHandler", 0x60)        # RTS
        h.add_stub(0x07E245, "Link_HandleVelocity", 0x6B)           # RTL
        return h

    def _equip_reforged_heavy(self, h: CpuHarness) -> None:
        h.put(ADDR_SWORD_FLAGS, FLAG_INITIALIZED | FLAG_HEAVY_OWNED | FLAG_HEAVY_EQUIPPED | FLAG_HEAVY_REFORGED)
        h.put(ADDR_SWORD, 3)

    def _equip_broken_heavy(self, h: CpuHarness) -> None:
        h.put(ADDR_SWORD_FLAGS, FLAG_INITIALIZED | FLAG_HEAVY_OWNED | FLAG_HEAVY_EQUIPPED)
        h.put(ADDR_SWORD, 1)

    def _equip_story_blade(self, h: CpuHarness, level: int = 2, reforged_owned: bool = False) -> None:
        flags = FLAG_INITIALIZED | (FLAG_HEAVY_OWNED | FLAG_HEAVY_REFORGED if reforged_owned else 0)
        h.put(ADDR_SWORD_FLAGS, flags)
        h.put(ADDR_SWORD_STORY, level)
        h.put(ADDR_SWORD, level)

    def _setup_spin_end_state(self, h: CpuHarness, *, magic: int = 0x80, usage: int = 0, pad_l: int = 0x80) -> None:
        h.put(0x5D, 0x03)       # LinkState_SpinAttack
        h.put(0xF0, pad_l)      # Held B (and optional D-pad)
        h.put(0x0341, 0x00)     # Not deep water
        h.put(0x037B, 0x00)     # Not invincible
        h.put(0x0375, 0x13)     # Not ledge-hopping
        h.put(0x4D, 0x00)       # Not recoiling
        h.put(0x50, 0x00)       # Cleared right before $07:A8CA
        h.put(0x3C, 0x00)       # Cleared right before $07:A8CA
        h.put(0x3A, 0x00)       # Cleared right before $07:A8CA
        h.put(0x012E, 0x00)     # SFX2 queue
        h.put(ADDR_MAGIC_POWER, magic)
        h.put(ADDR_MAGIC_USAGE, usage)

    def test_compiled_hook_sites_match_jsl_targets(self):
        for site, label, trailing in (
            (0x07A879, "HeavySword_HurricaneMove", bytes([0xEA, 0xEA])),
            (0x07A882, "HeavySword_HurricaneKeepState", b""),
            (0x07A8CA, "HeavySword_HurricaneEndCheck", b""),
            (0x078102, "HeavySword_ControlFrameHook", b""),
        ):
            target = self.labels[label]
            expected = bytes([0x22, target & 0xFF, (target >> 8) & 0xFF, target >> 16]) + trailing
            pc = snes_to_pc(site)
            self.assertEqual(self.rom[pc : pc + len(expected)], expected, f"Hook mismatch at ${site:06X}")

    def test_reforged_active_gating_and_register_preservation(self):
        h = self.make_harness()
        target = self.labels["HeavySword_ReforgedActive"]

        # Test in both M=8/X=8 and M=16/X=8 modes (verifying full 16-bit A preservation)
        for m8, x8 in ((True, True), (False, True)):
            # 1. Story blade -> CLC
            h.reset_cpu(db=0x07, m8=m8, x8=x8)
            h.cpu.a, h.cpu.x, h.cpu.y = 0x1234, 0x0078, 0x00BC
            self._equip_story_blade(h, level=3, reforged_owned=True)
            h.call_jsl(target)
            self.assertFalse(h.cpu.c)
            self.assertEqual((h.cpu.a, h.cpu.x, h.cpu.y, h.cpu.mf, h.cpu.xf), (0x1234, 0x0078, 0x00BC, m8, x8))

            # 2. Broken heavy blade -> CLC
            h.reset_cpu(db=0x07, m8=m8, x8=x8)
            h.cpu.a, h.cpu.x, h.cpu.y = 0xABCD, 0x0042, 0x0077
            self._equip_broken_heavy(h)
            h.call_jsl(target)
            self.assertFalse(h.cpu.c)
            self.assertEqual((h.cpu.a, h.cpu.x, h.cpu.y, h.cpu.mf, h.cpu.xf), (0xABCD, 0x0042, 0x0077, m8, x8))

            # 3. Reforged heavy sword equipped -> SEC
            h.reset_cpu(db=0x07, m8=m8, x8=x8)
            h.cpu.a, h.cpu.x, h.cpu.y = 0xDEAD, 0x00EF, 0x00FE
            self._equip_reforged_heavy(h)
            h.call_jsl(target)
            self.assertTrue(h.cpu.c)
            self.assertEqual((h.cpu.a, h.cpu.x, h.cpu.y, h.cpu.mf, h.cpu.xf), (0xDEAD, 0x00EF, 0x00FE, m8, x8))

    def test_story_and_broken_heavy_keep_vanilla_single_spin(self):
        for name, equip_fn in (
            ("story_meadow", lambda h: self._equip_story_blade(h, level=1)),
            ("story_master", lambda h: self._equip_story_blade(h, level=2)),
            ("story_tempered_with_reforged_owned", lambda h: self._equip_story_blade(h, level=3, reforged_owned=True)),
            ("broken_heavy", self._equip_broken_heavy),
        ):
            with self.subTest(sword=name):
                h = self.make_harness()
                equip_fn(h)
                self._setup_spin_end_state(h, magic=0x80, usage=0, pad_l=0x80)
                h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
                self.assertEqual(h.get(0x5D), 0x00)
                self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x80)
                self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0x00)
                self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0x00)
                self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0x00)
                self.assertEqual(h.get(0x012E), 0x00)

    def test_normal_magic_4_rev_cap_and_dizzy_trigger(self):
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, usage=0, pad_l=0x85)  # Holding B + D-pad

        # 4 extra revolutions succeed at 16 MP ($10) each
        for rev in range(1, 5):
            h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
            self.assertEqual(h.get(0x5D), 0x03)
            self.assertEqual(h.get(0x3C), 0x90)
            self.assertEqual(h.get(0x50) & 0x01, 0x01)
            self.assertEqual(h.get(0x3A), 0x80)
            self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0x01)
            self.assertEqual(h.get(ADDR_HURRICANE_REVS), rev)
            self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x80 - rev * 0x10)
            self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0x00)

        # 5th attempt hits 4-rev cap -> ends spin, sets 45-frame dizzy + stumble SFX $21
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0x00)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 45)
        self.assertEqual(h.get(0x012E), 0x21)
        self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x40)  # no 5th deduction

    def test_half_and_quarter_magic_both_floor_at_8mp(self):
        for usage_level in (1, 2):  # 1 = half magic, 2 = quarter magic
            with self.subTest(magic_usage=usage_level):
                h = self.make_harness()
                self._equip_reforged_heavy(h)
                self._setup_spin_end_state(h, magic=0x20, usage=usage_level, pad_l=0x80)

                for rev in range(1, 5):
                    h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
                    self.assertEqual(h.get(0x5D), 0x03)
                    self.assertEqual(h.get(ADDR_HURRICANE_REVS), rev)
                    self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x20 - rev * 0x08)

                # 0 MP left + rev cap reached -> clean end + dizzy
                h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
                self.assertEqual(h.get(0x5D), 0x00)
                self.assertEqual(h.get(ADDR_DIZZY_TIMER), 45)

    def test_out_of_magic_single_spin_vs_hurricane(self):
        # Case 1: Out of magic trying to start rev 1 (Revs == 0) -> error SFX, NO dizzy!
        for usage, magic in ((0, 0x0F), (1, 0x07), (2, 0x07)):
            with self.subTest(case="first_extra_rev", usage=usage, magic=magic):
                h = self.make_harness()
                self._equip_reforged_heavy(h)
                self._setup_spin_end_state(h, magic=magic, usage=usage, pad_l=0x80)
                h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
                self.assertEqual(h.get(0x5D), 0x00)
                self.assertEqual(h.get(ADDR_MAGIC_POWER), magic)
                self.assertEqual(h.get(0x012E), 0x3C)
                self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0x00)

        # Case 2: Out of magic after 1 extra rev completed -> error SFX preserved, dizzy SET!
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x10, usage=0, pad_l=0x80)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 1)
        self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x00)

        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0x00)
        self.assertEqual(h.get(0x012E), 0x3C)          # error beep NOT overwritten by $21
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 45)  # dizzy triggered after >= 2 total spins

    def test_release_b_after_single_spin_is_penalty_free_but_after_hurricane_is_dizzy(self):
        # Single normal spin (B released before rev 1): zero dizzy, zero SFX
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, usage=0, pad_l=0x00)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x00)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0x00)
        self.assertEqual(h.get(0x012E), 0x00)

        # Release B after 1 extra rev (2 total spins): triggers 45-frame dizzy + SFX $21
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, usage=0, pad_l=0x80)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 1)
        h.put(0xF0, 0x00)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0x00)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0x00)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 45)
        self.assertEqual(h.get(0x012E), 0x21)

    def test_end_check_guards_swim_victory_recoil_invincible_and_collision_state(self):
        # Deep water ($0341 == 1) -> transitions to swim ($5D = 4), no dizzy
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, pad_l=0x80)
        h.put(ADDR_HURRICANE_ACTIVE, 1)
        h.put(ADDR_HURRICANE_REVS, 2)
        h.put(0x0341, 1)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x04)
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0)

        # Victory spin ($5D == $1E) -> returns to $00 without magic drain or dizzy
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, pad_l=0x80)
        h.put(0x5D, 0x1E)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x00)
        self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x80)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0)

        # Mid-spin pit state ($5D == $01) -> preserved (not overwritten back to $00!)
        h = self.make_harness()
        self._equip_reforged_heavy(h)
        self._setup_spin_end_state(h, magic=0x80, pad_l=0x80)
        h.put(0x5D, 0x01)
        h.put(ADDR_HURRICANE_ACTIVE, 1)
        h.put(ADDR_HURRICANE_REVS, 1)
        h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
        self.assertEqual(h.get(0x5D), 0x01)
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0)

        # Other guards: Y held ($C0), Start held ($90), invincible ($037B), ledge ($0375 != $13), recoil ($4D)
        for label, addr, val in (
            ("holding_Y", 0xF0, 0xC0),
            ("holding_Start", 0xF0, 0x90),
            ("invincible", 0x037B, 0x01),
            ("ledge_hop", 0x0375, 0x10),
            ("recoil", 0x4D, 0x01),
        ):
            with self.subTest(guard=label):
                h = self.make_harness()
                self._equip_reforged_heavy(h)
                self._setup_spin_end_state(h, magic=0x80, pad_l=0x80)
                h.put(addr, val)
                h.call_jsl(self.labels["HeavySword_HurricaneEndCheck"])
                self.assertEqual(h.get(0x5D), 0x00)
                self.assertEqual(h.get(ADDR_MAGIC_POWER), 0x80)

    def test_half_speed_steerable_movement_and_bank07_trampoline(self):
        # 1. Normal spin (HurricaneActive == 0): stationary, calls ONLY Link_HandleVelocity
        h = self.make_harness()
        h.put(ADDR_HURRICANE_ACTIVE, 0)
        h.put(0x1A, 0x01)       # odd frame
        h.put(0xF0, 0x89)       # B + Up + Right
        h.put(0x67, 0xFF)
        h.call_jsl(self.labels["HeavySword_HurricaneMove"])
        self.assertEqual([c[0] for c in h.calls], ["Link_HandleVelocity"])
        self.assertEqual(h.get(0x67), 0x00)
        self.assertEqual(h.cpu.db, 0x07)

        # 2. HurricaneActive == 1, even frame ($1A bit 0 clear): half-speed skip frame
        h = self.make_harness()
        h.put(ADDR_HURRICANE_ACTIVE, 1)
        h.put(0x1A, 0x10)       # even frame
        h.put(0xF0, 0x89)       # B + Up + Right
        h.put(0x3C, 0x00)
        h.put(0x67, 0x09)
        h.call_jsl(self.labels["HeavySword_HurricaneMove"])
        self.assertEqual([c[0] for c in h.calls], ["Link_HandleVelocity"])
        self.assertEqual(h.get(0x3C), 0x90)
        self.assertEqual(h.get(0x67), 0x00)
        self.assertEqual(h.cpu.db, 0x07)

        # 3. HurricaneActive == 1, odd frame ($1A bit 0 set): steers via $B64F -> $D077 (Y=0) -> $07E245
        h = self.make_harness()
        h.put(ADDR_HURRICANE_ACTIVE, 1)
        h.put(0x1A, 0x11)       # odd frame
        h.put(0xF0, 0x89)       # B + Up($08) + Right($01)
        h.put(0x3C, 0x00)
        h.cpu.y = 0x55          # verify Y is explicitly zeroed before TileDetect_MainHandler
        h.call_jsl(self.labels["HeavySword_HurricaneMove"])
        self.assertEqual(
            [c[0] for c in h.calls],
            ["Link_HandleDiagonalCollision", "TileDetect_MainHandler", "Link_HandleVelocity"],
        )
        self.assertEqual(h.calls[0][1]["67"], 0x09)
        self.assertEqual(h.calls[0][1]["db"], 0x07)
        self.assertEqual(h.calls[1][1]["y"], 0x00)
        self.assertEqual(h.calls[1][1]["db"], 0x07)
        self.assertEqual(h.calls[2][1]["67"], 0x09)
        self.assertEqual(h.get(0x3C), 0x90)
        self.assertEqual(h.cpu.db, 0x07)
        self.assertTrue(h.cpu.mf and h.cpu.xf)

    def test_keep_state_preserves_collision_transitions(self):
        # Default/spin states remain $03; victory spin remains $1E
        for initial, expected in ((0x00, 0x03), (0x03, 0x03), (0x1E, 0x1E)):
            h = self.make_harness()
            h.put(0x5D, initial)
            h.put(ADDR_HURRICANE_ACTIVE, 1)
            h.put(ADDR_HURRICANE_REVS, 2)
            h.call_jsl(self.labels["HeavySword_HurricaneKeepState"])
            self.assertEqual(h.get(0x5D), expected)
            self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 1)
            self.assertEqual(h.get(ADDR_HURRICANE_REVS), 2)

        # Pit ($01), swim ($04), ledge hop ($0B) are preserved & clear Hurricane flags
        for state in (0x01, 0x04, 0x0B):
            with self.subTest(state=hex(state)):
                h = self.make_harness()
                h.put(0x5D, state)
                h.put(0x50, 0x01)
                h.put(ADDR_HURRICANE_ACTIVE, 1)
                h.put(ADDR_HURRICANE_REVS, 3)
                h.call_jsl(self.labels["HeavySword_HurricaneKeepState"])
                self.assertEqual(h.get(0x5D), state)
                self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0)
                self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0)
                self.assertEqual(h.get(0x50) & 0x01, 0)
                self.assertEqual(h.get(0x3A), 0x80)

    def test_dizzy_45_frame_lock_input_strip_and_facing_wobble(self):
        h = self.make_harness()
        h.put(0x10, 0x09)  # Overworld gameplay
        h.put(0x11, 0x00)
        h.put(0x5D, 0x00)
        h.put(0x2F, 0x00)  # Facing Up
        h.put(ADDR_DIZZY_TIMER, 45)

        observed_facings: list[tuple[int, int]] = []
        for frame in range(1, 46):
            # Simulate player mashing D-pad + B/Y/A/X/L/R + Start every frame
            h.put(0xF0, 0xDF)  # B + Y + Start + all D-pad
            h.put(0xF4, 0xDF)
            h.put(0xF2, 0xF0)  # A + X + L + R
            h.put(0xF6, 0xF0)
            h.call_jsl(self.labels["HeavySword_ControlFrameHook"])

            # D-pad ($0F) and B/Y ($C0) stripped; Start/Select ($30) preserved; A/X/L/R ($F0) stripped
            self.assertEqual(h.get(0xF0), 0x10, f"frame {frame}")
            self.assertEqual(h.get(0xF4), 0x10, f"frame {frame}")
            self.assertEqual(h.get(0xF2), 0x00, f"frame {frame}")
            self.assertEqual(h.get(0xF6), 0x00, f"frame {frame}")
            self.assertEqual(h.cpu.x & 0xFF, 0x00)  # replayed LDA $5D : ASL : TAX
            observed_facings.append((h.get(ADDR_DIZZY_TIMER), h.get(0x2F)))

        # Timer reached 0 on frame 45
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0)

        # Facing cycled 0 -> 4 -> 2 -> 6 -> 0 -> 4 -> 2 -> 6 at exact 6-frame intervals
        turns = [
            (timer, face)
            for i, (timer, face) in enumerate(observed_facings)
            if (i == 0 and face != 0) or (i > 0 and face != observed_facings[i - 1][1])
        ]
        self.assertEqual(
            turns,
            [(42, 4), (36, 2), (30, 6), (24, 0), (18, 4), (12, 2), (6, 6)],
        )

        # Frame 46: normal control restored (inputs completely untouched!)
        h.put(0xF0, 0x8F)
        h.put(0xF4, 0x8F)
        h.put(0xF2, 0xF0)
        h.put(0xF6, 0xF0)
        h.call_jsl(self.labels["HeavySword_ControlFrameHook"])
        self.assertEqual(h.get(0xF0), 0x8F)
        self.assertEqual(h.get(0xF4), 0x8F)
        self.assertEqual(h.get(0xF2), 0xF0)
        self.assertEqual(h.get(0xF6), 0xF0)

    def test_dizzy_safety_clears_and_stale_hurricane_cleanup(self):
        # Every safety condition must clear DizzyTimer immediately WITHOUT stripping inputs
        safety_cases = (
            ("module_menu", 0x10, 0x0E),
            ("submodule_transition", 0x11, 0x01),
            ("damage_recoil", 0x4D, 0x01),
            ("fresh_damage_iframe", 0x031F, 0x3A),
            ("doorway", 0x6C, 0x01),
            ("pit_fall", 0x5B, 0x02),
            ("non_default_link_state", 0x5D, 0x02),
        )
        for name, addr, val in safety_cases:
            with self.subTest(safety=name):
                h = self.make_harness()
                h.put(0x10, 0x07)  # Indoor gameplay
                h.put(0x11, 0x00)
                h.put(0x5D, 0x00)
                h.put(ADDR_DIZZY_TIMER, 30)
                h.put(0xF0, 0x8F)
                h.put(0xF2, 0xF0)
                h.put(addr, val)
                h.call_jsl(self.labels["HeavySword_ControlFrameHook"])
                self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0)
                self.assertEqual(h.get(0xF0), 0x8F)
                self.assertEqual(h.get(0xF2), 0xF0)
                self.assertEqual(h.cpu.x & 0xFF, (h.get(0x5D) << 1) & 0xFF)

        # Stale HurricaneActive/Revs are cleared whenever $5D != $03, preserved when $5D == $03
        h = self.make_harness()
        h.put(0x5D, 0x03)
        h.put(ADDR_HURRICANE_ACTIVE, 1)
        h.put(ADDR_HURRICANE_REVS, 2)
        h.put(ADDR_DIZZY_TIMER, 10)
        h.call_jsl(self.labels["HeavySword_ControlFrameHook"])
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 1)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 2)
        self.assertEqual(h.get(ADDR_DIZZY_TIMER), 0)
        self.assertEqual(h.cpu.x & 0xFF, 0x06)

        h.put(0x5D, 0x02)  # Recoil interrupted spin
        h.call_jsl(self.labels["HeavySword_ControlFrameHook"])
        self.assertEqual(h.get(ADDR_HURRICANE_ACTIVE), 0)
        self.assertEqual(h.get(ADDR_HURRICANE_REVS), 0)
        self.assertEqual(h.cpu.x & 0xFF, 0x04)


if __name__ == "__main__":
    unittest.main()
