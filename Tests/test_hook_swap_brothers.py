#!/usr/bin/env python3
"""Compiled Asar + Lakesnes 65816 execution tests for Abyss $56 Twin Brothers
Hookshot/Goldstar <-> Switch Hook Trade-Back & Swap-Diamond Trial.

Assembles Sprites/NPCs/hook_swap_brothers.asm directly with Asar against exact
vanilla Sprite_32_ArguingBros ($05:E026-$05:E051) preimage bytes and executes
the compiled 65816 code through the hooked $05:E026 gateway on Lakesnes' CPU.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ASAR_BIN = os.environ.get("ASAR_BIN") or shutil.which("asar")
LAKESNES_DIR = Path(os.environ.get("LAKESNES_DIR", "/Users/scawful/src/hobby/lakesnes"))
if not (LAKESNES_DIR / "snes" / "cpu.c").is_file():
    LAKESNES_DIR = Path("/Users/scawful/src/hobby/LakeSnes")

# Vanilla Sprite_32_ArguingBros ($05:E026-$05:E051) exact ROM bytes
VANILLA_E026_BYTES = bytes.fromhex(
    "A5A0"        # $05E026: LDA.b $A0
    "2901"        # $05E028: AND.b #$01
    "D00A"        # $05E02A: BNE $05E036
    "A931"        # $05E02C: LDA.b #$31
    "A001"        # $05E02E: LDY.b #$01
    "22A7E105"    # $05E030: JSL $05E1A7 (Sprite_ShowSolicitedMessage)
    "8017"        # $05E034: BRA $05E04D
    "AD0104"      # $05E036: LDA.w $0401
    "D00A"        # $05E039: BNE $05E045
    "A92F"        # $05E03B: LDA.b #$2F
    "A001"        # $05E03D: LDY.b #$01
    "22A7E105"    # $05E03F: JSL $05E1A7
    "8008"        # $05E043: BRA $05E04D
    "A930"        # $05E045: LDA.b #$30
    "A001"        # $05E047: LDY.b #$01
    "22A7E105"    # $05E049: JSL $05E1A7
    "22F3F41E"    # $05E04D: JSL $1EF4F3 (Sprite_BehaveAsBarrier)
    "60"          # $05E051: RTS
)

# WRAM & SRAM addresses
ADDR_NMIHUD = 0x7E0016
ADDR_INDOORS = 0x7E001B
ADDR_ROOM = 0x7E00A0
ADDR_SFX2 = 0x7E012E
ADDR_SFX3 = 0x7E012F
ADDR_WALL_OPEN = 0x7E0401

ADDR_TRIAL_ACTIVE = 0x7EC13A
ADDR_TRIAL_TIMER = 0x7EC13B
ADDR_TRIAL_STEP = 0x7EC13D

ADDR_HOOKSHOT = 0x7EF342
ADDR_MAGIC = 0x7EF36E
ADDR_GOLDSTAR_OWNED = 0x7EF3A9
ADDR_GOLDSTAR_VER = 0x7EF3AA
ADDR_SAVED_WORLD = 0x7EF3CA
ADDR_SIDEQUEST = 0x7EF3D7
ADDR_SIDEQUEST2 = 0x7EF3D8

BIT_SWAP_DIAMOND = 0x40

STUB_SHOW_SOLICITED = 0x05E1A7
STUB_BARRIER = 0x1EF4F3
STUB_HUD_REFRESH = 0x2E8100


def snes_to_pc(addr: int) -> int:
    return (((addr >> 16) & 0x7F) << 15) | (addr & 0x7FFF)


class Cpu(C.Structure):
    _fields_ = (
        [(n, C.c_void_p) for n in ("mem", "read", "write", "idle")]
        + [(n, C.c_uint16) for n in ("a", "x", "y", "sp", "pc", "dp")]
        + [(n, C.c_uint8) for n in ("k", "db")]
        + [
            (n, C.c_bool)
            for n in (
                "c",
                "z",
                "v",
                "n",
                "i",
                "d",
                "xf",
                "mf",
                "e",
                "waiting",
                "stopped",
                "irqWanted",
                "nmiWanted",
                "intWanted",
                "resetWanted",
            )
        ]
    )


class SwapBrosRunner:
    """Minimal Lakesnes 65816 execution harness for HookSwapBrothers."""

    def __init__(self, lib: C.CDLL, rom: bytes, labels: dict[str, int]) -> None:
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.traps: dict[int, object] = {}
        self.bad_writes: list[tuple[int, int]] = []
        self.messages: list[int] = []
        self.barrier_calls: int = 0
        self.hud_refresh_calls: int = 0
        self.solicited_accept: bool = False

        self.read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self._read(a))
        self.write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self._write(a, v))
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self.read_cb, self.write_cb, self.idle_cb)
        self.cpu = self.p.contents
        self.reset_state()

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def reset_state(self) -> None:
        self.ram[:] = bytes(len(self.ram))
        self.bad_writes.clear()
        self.messages.clear()
        self.barrier_calls = 0
        self.hud_refresh_calls = 0
        self.solicited_accept = False
        self._reset_cpu()
        self.traps = {
            STUB_SHOW_SOLICITED: self._on_solicited,
            STUB_BARRIER: self._on_barrier,
            STUB_HUD_REFRESH: self._on_hud_refresh,
        }

    def _reset_cpu(self) -> None:
        for flag in (
            "c", "z", "v", "n", "i", "d", "e",
            "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted",
        ):
            setattr(self.cpu, flag, False)
        self.cpu.mf = True
        self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x01FF
        self.cpu.a = 0
        self.cpu.x = 0
        self.cpu.y = 0
        self.cpu.db = 0x05

    def _on_solicited(self) -> None:
        # Sprite_ShowSolicitedMessage: A=msg_lo, Y=msg_hi, X=slot preserved, DBR mirrors low WRAM.
        assert self.cpu.mf and self.cpu.xf, "Sprite_ShowSolicitedMessage requires M=8, X=8"
        assert (self.cpu.db & 0x7F) < 0x40, f"DBR ${self.cpu.db:02X} does not mirror low WRAM"
        msg_id = (self.cpu.a & 0xFF) | ((self.cpu.y & 0xFF) << 8)
        self.messages.append(msg_id)
        self.cpu.c = self.solicited_accept

    def _on_barrier(self) -> None:
        assert self.cpu.mf and self.cpu.xf, "Sprite_BehaveAsBarrier requires M=8, X=8"
        assert self.cpu.db == 0x05, f"Expected DBR=$05 at Sprite_BehaveAsBarrier, got ${self.cpu.db:02X}"
        self.barrier_calls += 1

    def _on_hud_refresh(self) -> None:
        self.hud_refresh_calls += 1
        self.put(ADDR_NMIHUD, 0x01)

    @staticmethod
    def _ram_off(addr: int) -> int | None:
        bank = addr >> 16
        lo = addr & 0xFFFF
        if bank in (0x7E, 0x7F):
            return addr - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def _read(self, addr: int) -> int:
        if addr in self.traps:
            return 0x6B  # RTL
        off = self._ram_off(addr)
        if off is not None:
            return self.ram[off]
        if addr & 0x8000:
            pc = snes_to_pc(addr)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, addr: int, val: int) -> None:
        off = self._ram_off(addr)
        if off is None:
            self.bad_writes.append((addr, val))
            return
        self.ram[off] = val & 0xFF

    def get(self, addr: int) -> int:
        off = self._ram_off(addr)
        assert off is not None, hex(addr)
        return self.ram[off]

    def put(self, addr: int, val: int) -> None:
        off = self._ram_off(addr)
        assert off is not None, hex(addr)
        self.ram[off] = val & 0xFF

    def get16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def put16(self, addr: int, val: int) -> None:
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def tick_brother(self, *, slot: int = 4, talk: bool = False, clear_sfx: bool = True) -> None:
        """Execute real hooked $05:E026 -> HookSwapBrothers_Interact -> $05:E04D -> RTS."""
        if clear_sfx:
            self.put(ADDR_SFX2, 0)
            self.put(ADDR_SFX3, 0)
            self.put(ADDR_NMIHUD, 0)
        self.messages.clear()
        self.barrier_calls = 0
        self.hud_refresh_calls = 0
        self.solicited_accept = talk

        c = self.cpu
        self._reset_cpu()
        c.x = slot
        c.db = 0x05
        c.k = 0x05
        c.pc = 0xE026
        sp0 = c.sp
        sentinel_pc = 0x7000
        self.put(sp0, ((sentinel_pc - 1) >> 8) & 0xFF)
        self.put(sp0 - 1, (sentinel_pc - 1) & 0xFF)
        c.sp = sp0 - 2

        for _ in range(4000):
            if c.k == 0x05 and c.pc == sentinel_pc:
                assert not self.bad_writes, f"Unexpected non-WRAM writes: {self.bad_writes}"
                assert c.sp == sp0, f"Stack imbalance: got ${c.sp:04X}, expected ${sp0:04X}"
                assert c.mf and c.xf, f"M/X exit width corrupted: mf={c.mf}, xf={c.xf}"
                assert c.db == 0x05, f"DBR corrupted: ${c.db:02X}"
                assert (c.x & 0xFF) == slot, f"Sprite slot X clobbered: {c.x} != {slot}"
                assert self.barrier_calls == 1, f"Expected 1 Sprite_BehaveAsBarrier call, got {self.barrier_calls}"
                return
            pc24 = (c.k << 16) | c.pc
            if pc24 in self.traps:
                self.traps[pc24]()
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"Step budget exceeded at ${c.k:02X}:{c.pc:04X}")


def assemble_harness(tmpdir: Path) -> tuple[bytes, dict[str, int]]:
    assert ASAR_BIN, "asar binary not found in PATH"
    rom_path = tmpdir / "harness.sfc"
    asm_path = tmpdir / "harness.asm"
    sym_path = tmpdir / "harness.sym"

    buf = bytearray(0x200000)  # 2 MiB LoROM (banks $00-$3F)
    pc = snes_to_pc(0x05E026)
    buf[pc : pc + len(VANILLA_E026_BYTES)] = VANILLA_E026_BYTES
    rom_path.write_bytes(buf)

    asm_src = f"""
lorom
SavedWorld               = $7EF3CA
GoldstarOwned            = $7EF3A9
GoldstarInventoryVersion = $7EF3AA
SideQuestProgress        = $7EF3D7
!SideQuest_SwapDiamond   = $40
MagicPower               = $7EF36E
Sprite_ShowSolicitedMessage = $05E1A7
HUD_RefreshLong          = $2E8100

org $328000
incsrc "{(ROOT / 'Sprites' / 'NPCs' / 'hook_swap_brothers.asm').as_posix()}"
assert pc() <= $330000
"""
    asm_path.write_text(asm_src, encoding="utf-8")
    proc = subprocess.run(
        [ASAR_BIN, "--no-title-check", "--symbols=wla", f"--symbols-path={sym_path}", str(asm_path), str(rom_path)],
        capture_output=True,
        text=True,
        errors="replace",
    )
    if proc.returncode != 0:
        raise AssertionError(f"Asar assembly failed:\n{proc.stdout}\n{proc.stderr}")

    labels: dict[str, int] = {}
    for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", sym_path.read_text(encoding="utf-8")):
        labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return rom_path.read_bytes(), labels


class HookSwapBrothersSourceTests(unittest.TestCase):
    def test_sram_bit_no_collision_with_ranch_archery(self) -> None:
        sram = (ROOT / "Core" / "sram.asm").read_text(encoding="utf-8")
        self.assertIn("!SideQuest_SwapDiamond     = $40", sram)
        # Bit 7 ($80) of SideQuestProgress2 ($7EF3D8) belongs to Masks/horse_minigame.asm
        self.assertNotIn("!SideQuest2_SwapDiamond", sram)
        horse = (ROOT / "Masks" / "horse_minigame.asm").read_text(encoding="utf-8")
        self.assertIn("!SideQuest2_RanchArchery        = $80", horse)

    def test_all_sprites_includes_hook_swap_brothers_in_bank32(self) -> None:
        all_spr = (ROOT / "Sprites" / "all_sprites.asm").read_text(encoding="utf-8")
        b32_start = all_spr.index("org $328000")
        b32_end = all_spr.index('assert pc() <= $330000', b32_start)
        self.assertIn('incsrc "Sprites/NPCs/hook_swap_brothers.asm"', all_spr[b32_start:b32_end])

    def test_asm_uses_named_msg_constants_and_unused_wram(self) -> None:
        src = (ROOT / "Sprites" / "NPCs" / "hook_swap_brothers.asm").read_text(encoding="utf-8")
        for tok in (
            "!SwapBrosMsg_WestEquip   = $0131",
            "!SwapBrosMsg_TrialStart  = $012F",
            "!SwapBrosMsg_TrialClear  = $0130",
            "!SwapBrosMsg_EastEquip   = $0130",
            "SwapTrial_Active         = $7EC13A",
            "SwapTrial_Timer          = $7EC13B",
            "SwapTrial_Step           = $7EC13D",
            "assert read3($05E026) == $29A0A5",
            "assert read4($05E04D) == $1EF4F322",
        ):
            self.assertIn(tok, src)


class HookSwapBrothers65816Tests(unittest.TestCase):
    lib: C.CDLL | None = None
    rom: bytes = b""
    labels: dict[str, int] = {}
    _tmp: tempfile.TemporaryDirectory | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if not ASAR_BIN or not (LAKESNES_DIR / "snes" / "cpu.c").is_file():
            return
        cls._tmp = tempfile.TemporaryDirectory(prefix="oos-swapbros-")
        tmpdir = Path(cls._tmp.name)
        cls.rom, cls.labels = assemble_harness(tmpdir)
        lib_path = tmpdir / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(LAKESNES_DIR / "snes" / "cpu.c"),
                str(LAKESNES_DIR / "snes" / "statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        lib = C.CDLL(str(lib_path))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.lib = lib

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._tmp is not None:
            cls._tmp.cleanup()

    def _runner(self) -> SwapBrosRunner:
        if self.lib is None:
            self.skipTest("asar or Lakesnes cpu.c not available")
        r = SwapBrosRunner(self.lib, self.rom, self.labels)
        self.addCleanup(r.close)
        return r

    def test_patched_gateway_bytes(self) -> None:
        if not self.rom:
            self.skipTest("Harness ROM not assembled")
        target = self.labels["HookSwapBrothers_Interact"]
        self.assertEqual(target >> 16, 0x32)
        pc = snes_to_pc(0x05E026)
        expected_gateway = bytes([
            0x22, target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0xFF,
            0x4C, 0x4D, 0xE0,  # JMP.w $E04D
        ])
        self.assertEqual(self.rom[pc : pc + 7], expected_gateway)
        # Barrier tail untouched
        tail_pc = snes_to_pc(0x05E04D)
        self.assertEqual(self.rom[tail_pc : tail_pc + 5], bytes.fromhex("22F3F41E60"))

    def test_non_abyss_and_wrong_room_passthrough(self) -> None:
        r = self._runner()
        cases = [
            # (indoors, world, room, wall_open, expected_msg)
            (1, 0x00, 0x00F4, 0, 0x0131),  # Light World West Brother
            (1, 0x00, 0x00F5, 0, 0x012F),  # Light World East Brother (wall closed)
            (1, 0x00, 0x00F5, 1, 0x0130),  # Light World East Brother (wall opened)
            (0, 0x40, 0x00F4, 0, 0x0131),  # Outdoors
            (0, 0x40, 0x00F5, 0, 0x012F),  # Outdoors
            (1, 0x40, 0x00F3, 0, 0x012F),  # Abyss wrong room (odd)
            (1, 0x40, 0x00F6, 0, 0x0131),  # Abyss wrong room (even)
            (1, 0x40, 0x01F4, 0, 0x0131),  # Abyss high-byte room $01F4
            (1, 0x40, 0x01F5, 1, 0x0130),  # Abyss high-byte room $01F5
        ]
        for indoors, world, room, wall, exp_msg in cases:
            r.reset_state()
            r.put(ADDR_INDOORS, indoors)
            r.put(ADDR_SAVED_WORLD, world)
            r.put16(ADDR_ROOM, room)
            r.put(ADDR_WALL_OPEN, wall)
            r.put(ADDR_HOOKSHOT, 1)
            r.put(ADDR_GOLDSTAR_OWNED, 1)
            r.tick_brother(talk=True)
            self.assertEqual(r.messages, [exp_msg], (indoors, hex(world), hex(room), wall))
            self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.get(ADDR_SFX2), 0)
            self.assertEqual(r.get(ADDR_SFX3), 0)
            self.assertEqual(r.hud_refresh_calls, 0)

    def test_pre_goldstar_passthrough(self) -> None:
        r = self._runner()
        for room, wall, exp_msg in ((0x00F4, 0, 0x0131), (0x00F5, 0, 0x012F), (0x00F5, 1, 0x0130)):
            r.reset_state()
            r.put(ADDR_INDOORS, 1)
            r.put(ADDR_SAVED_WORLD, 0x40)
            r.put16(ADDR_ROOM, room)
            r.put(ADDR_WALL_OPEN, wall)
            r.put(ADDR_HOOKSHOT, 0)
            r.put(ADDR_GOLDSTAR_OWNED, 0)
            r.tick_brother(talk=True)
            self.assertEqual(r.messages, [exp_msg])
            self.assertEqual(r.get(ADDR_HOOKSHOT), 0, "Must not grant Hookshot/Switch Hook pre-Goldstar")
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 0, "Must not grant Goldstar pre-Goldstar")
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.get(ADDR_SFX2), 0)
            self.assertEqual(r.get(ADDR_SFX3), 0)
            self.assertEqual(r.hud_refresh_calls, 0)

    def test_no_talk_does_not_mutate_state(self) -> None:
        r = self._runner()
        for room, sq in ((0x00F4, 0x00), (0x00F5, 0x00), (0x00F4, BIT_SWAP_DIAMOND), (0x00F5, BIT_SWAP_DIAMOND)):
            r.reset_state()
            r.put(ADDR_INDOORS, 1)
            r.put(ADDR_SAVED_WORLD, 0x40)
            r.put16(ADDR_ROOM, room)
            r.put(ADDR_SIDEQUEST, sq)
            r.put(ADDR_HOOKSHOT, 1)
            r.put(ADDR_GOLDSTAR_OWNED, 1)
            r.tick_brother(talk=False)
            self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.get(ADDR_SFX2), 0)
            self.assertEqual(r.get(ADDR_SFX3), 0)
            self.assertEqual(r.hud_refresh_calls, 0)

    def test_east_brother_trial_start_and_no_midtrial_reset(self) -> None:
        r = self._runner()
        for init_hook, init_gold in ((1, 1), (1, 0), (0, 1)):
            r.reset_state()
            r.put(ADDR_INDOORS, 1)
            r.put(ADDR_SAVED_WORLD, 0x40)
            r.put16(ADDR_ROOM, 0x00F5)
            r.put(ADDR_HOOKSHOT, init_hook)
            r.put(ADDR_GOLDSTAR_OWNED, init_gold)
            r.tick_brother(talk=True)

            self.assertEqual(r.messages, [0x012F])
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)
            self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1800)
            self.assertEqual(r.get(ADDR_TRIAL_STEP), 1)
            self.assertEqual(r.get(ADDR_HOOKSHOT), 2)
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
            self.assertEqual(r.get(ADDR_SFX3), 0x1B)
            self.assertEqual(r.hud_refresh_calls, 1)
            self.assertEqual(r.get(ADDR_NMIHUD), 1)

        # Talking to East Brother again mid-trial does NOT reset countdown
        r.put16(ADDR_TRIAL_TIMER, 1200)
        r.tick_brother(talk=True)
        self.assertEqual(r.messages, [0x012F])
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1199)
        self.assertEqual(r.get(ADDR_HOOKSHOT), 2)
        self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)

    def test_timer_tick_timeout_reset_and_exit_cancel(self) -> None:
        r = self._runner()
        r.put(ADDR_INDOORS, 1)
        r.put(ADDR_SAVED_WORLD, 0x40)
        r.put16(ADDR_ROOM, 0x00F5)
        r.put(ADDR_HOOKSHOT, 1)
        r.put(ADDR_GOLDSTAR_OWNED, 1)
        r.tick_brother(talk=True)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1800)

        # Tick 10 frames in East room, 5 frames in West room
        for _ in range(10):
            r.tick_brother(talk=False)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1790)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)
        self.assertEqual(r.get(ADDR_SFX2), 0)

        r.put16(ADDR_ROOM, 0x00F4)
        for _ in range(5):
            r.tick_brother(talk=False)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1785)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)

        # Advance to 2 frames left -> 1 frame left (still active) -> 0 (timeout!)
        r.put16(ADDR_TRIAL_TIMER, 2)
        r.tick_brother(talk=False)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)
        self.assertEqual(r.get(ADDR_SFX2), 0)
        self.assertEqual(r.get(ADDR_HOOKSHOT), 2)

        r.tick_brother(talk=False)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 0)
        self.assertEqual(r.get(ADDR_TRIAL_STEP), 0)
        self.assertEqual(r.get(ADDR_SFX2), 0x3C)
        self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
        self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
        self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
        self.assertEqual(r.hud_refresh_calls, 1)
        self.assertEqual(r.get(ADDR_SIDEQUEST) & BIT_SWAP_DIAMOND, 0)

        # Exit cancel (e.g. non-Abyss or outside $00F4/$00F5) clears trial without SFX2.$3C buzz
        r.put16(ADDR_ROOM, 0x00F5)
        r.tick_brother(talk=True)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)
        r.put16(ADDR_ROOM, 0x00F6)
        r.tick_brother(talk=False)
        self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
        self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 0)
        self.assertEqual(r.get(ADDR_TRIAL_STEP), 0)
        self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
        self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
        self.assertEqual(r.get(ADDR_SFX2), 0)
        self.assertEqual(r.hud_refresh_calls, 1)

    def test_west_brother_trial_completion_wall_or_walkaround(self) -> None:
        r = self._runner()
        for wall_open in (0, 1):
            r.reset_state()
            r.put(ADDR_INDOORS, 1)
            r.put(ADDR_SAVED_WORLD, 0x40)
            r.put16(ADDR_ROOM, 0x00F5)
            r.put(ADDR_HOOKSHOT, 1)
            r.put(ADDR_GOLDSTAR_OWNED, 1)
            r.put(ADDR_MAGIC, 0x18)
            r.put(ADDR_SIDEQUEST, 0x05)   # Pre-existing unrelated SideQuestProgress bits
            r.put(ADDR_SIDEQUEST2, 0x80)  # Ranch Archery bit must stay untouched
            r.tick_brother(talk=True)
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 1)

            # Enter West Brother room ($00F4) with time remaining and talk
            r.put16(ADDR_ROOM, 0x00F4)
            r.put(ADDR_WALL_OPEN, wall_open)
            r.tick_brother(talk=False)
            self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 1799)

            r.tick_brother(talk=True)
            self.assertEqual(r.messages, [0x0130])
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.get16(ADDR_TRIAL_TIMER), 0)
            self.assertEqual(r.get(ADDR_TRIAL_STEP), 2)
            self.assertEqual(r.get(ADDR_SIDEQUEST), 0x05 | BIT_SWAP_DIAMOND)
            self.assertEqual(r.get(ADDR_SIDEQUEST2), 0x80)
            self.assertEqual(r.get(ADDR_MAGIC), 0x80)
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
            self.assertEqual(r.get(ADDR_HOOKSHOT), 2)  # Leave Switch Hook equipped
            self.assertEqual(r.get(ADDR_SFX3), 0x1B)
            self.assertEqual(r.hud_refresh_calls, 1)

    def test_post_trial_instant_toggle_and_idle_west_brother(self) -> None:
        r = self._runner()
        # 1. Idle West Brother before trial clear still lets Link switch back to Hookshot ($7EF342=1)
        r.put(ADDR_INDOORS, 1)
        r.put(ADDR_SAVED_WORLD, 0x40)
        r.put16(ADDR_ROOM, 0x00F4)
        r.put(ADDR_HOOKSHOT, 2)
        r.put(ADDR_GOLDSTAR_OWNED, 1)
        r.tick_brother(talk=True)
        self.assertEqual(r.messages, [0x0131])
        self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
        self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
        self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
        self.assertEqual(r.get(ADDR_SFX2), 0x05)
        self.assertEqual(r.hud_refresh_calls, 1)

        # 2. Post-trial permanent instant toggle ($00F4 -> 1, $00F5 -> 2) preserving GoldstarOwned=1
        r.put(ADDR_SIDEQUEST, BIT_SWAP_DIAMOND)
        for _ in range(3):
            # East Brother -> Switch Hook ($7EF342=2)
            r.put16(ADDR_ROOM, 0x00F5)
            r.tick_brother(talk=True)
            self.assertEqual(r.messages, [0x0130])
            self.assertEqual(r.get(ADDR_HOOKSHOT), 2)
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
            self.assertEqual(r.get(ADDR_SFX2), 0x21)
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.hud_refresh_calls, 1)

            # West Brother -> Hookshot/Goldstar ($7EF342=1)
            r.put16(ADDR_ROOM, 0x00F4)
            r.tick_brother(talk=True)
            self.assertEqual(r.messages, [0x0131])
            self.assertEqual(r.get(ADDR_HOOKSHOT), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_OWNED), 1)
            self.assertEqual(r.get(ADDR_GOLDSTAR_VER), 0xA5)
            self.assertEqual(r.get(ADDR_SFX2), 0x05)
            self.assertEqual(r.get(ADDR_TRIAL_ACTIVE), 0)
            self.assertEqual(r.hud_refresh_calls, 1)

    def test_compiled_full_rom_hook_bytes_if_present(self) -> None:
        rom_path = ROOT / "Roms" / "oos168x.sfc"
        sym_path = ROOT / "Roms" / "oos168x.sym"
        if not (rom_path.is_file() and sym_path.is_file()):
            self.skipTest("Full compiled worktree ROM/symbols not present")
        sym_text = sym_path.read_text(encoding="utf-8")
        m = re.search(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?HookSwapBrothers_Interact$", sym_text)
        self.assertIsNotNone(m, "HookSwapBrothers_Interact missing from oos168x.sym")
        target = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
        self.assertEqual(target >> 16, 0x32)
        rom = rom_path.read_bytes()
        pc = snes_to_pc(0x05E026)
        expected = bytes([0x22, target & 0xFF, (target >> 8) & 0xFF, (target >> 16) & 0xFF, 0x4C, 0x4D, 0xE0])
        self.assertEqual(rom[pc : pc + 7], expected)
        self.assertEqual(rom[snes_to_pc(0x05E04D) : snes_to_pc(0x05E04D) + 5], bytes.fromhex("22F3F41E60"))


if __name__ == "__main__":
    unittest.main()
