#!/usr/bin/env python3
"""Compiled 65816 VBlank budget, DMA correctness, and Menu/Overlay safety tests for Epona.

Assembles the real Bank $53 Horse ASM (Masks/horse_form.asm,
Masks/horse_sparse_runtime.asm, Masks/horse_mounted_helpers.asm,
Masks/horse_ground_clearance.asm) plus a real DekuWings_NmiUpload sentinel into
a synthetic LoROM image and executes compiled 65816 machine code on LakeSnes
with hardware-accurate SNES DMA channel $43x2 auto-increment.

Runnable both via `pytest Tests/test_horse_vblank_budget.py` and directly via
`python3 Tests/test_horse_vblank_budget.py`.
"""
from __future__ import annotations

import ctypes as C
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "Tests") not in sys.path:
    sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

STUB_GET_TILE_ATTR = 0x00882E
STUB_DMA_CONT_8ADB = 0x008ADB
STUB_DMA_CONT_8B25 = 0x008B25
STUB_DMA_NATIVE_8A12 = 0x008A12
STUB_PAL_ARMOR = 0x058000
STUB_LOAD_DAYNIGHT = 0x058004
STUB_RESET_LINK_GFX = 0x058008
STUB_KID_START = 0x05800C
STUB_HORSE_GAME_TICK = 0x058010
STUB_SAVE_ANCHOR = 0x058014
STUB_MAINTAIN_NPC = 0x058018
STUB_OFF_RESTORE = 0x05801C
STUB_OFF_RANCH_NPC = 0x058020
STUB_FRAME_END_SCAN = 0x058024
STUB_DEKU_WINGS_NMI = 0x058030
STUB_SFX_PAN = 0x0DBB67
STUB_SPRITE_SPAWN = 0x1DF65D
STUB_DASH_TREMOR = 0x0993F3

# Exact WRAM addresses matching Core/symbols.asm
HORSE_MARKER = 0x1EDE
HORSE_STATE = 0x1EE0
HORSE_FRAME = 0x1EE6
HORSE_UPLOADED_FRAME = 0x1EE7
HORSE_NPC_ACTIVE = 0x1EE8
HORSE_NPC_FRAME = 0x1EE9
HORSE_NPC_UPLOADED = 0x1EEA
HORSE_PAL_LOADED = 0x1EEB
HORSE_DISMOUNT_CD = 0x1EEC

PROTECTED_VRAM_RANGES = [
    ("Rupee top ($0B)", 0x40B0, 0x40C0),
    ("Rupee bot ($1B)", 0x41B0, 0x41C0),
    ("Receipt/Bird top ($0E-$0F)", 0x40E0, 0x4100),
    ("Receipt/Bird bot ($1E-$1F)", 0x41E0, 0x4200),
    ("Follower/Arrows top ($20-$23)", 0x4200, 0x4240),
    ("Follower/Arrows bot ($30-$33)", 0x4300, 0x4340),
    ("HeartContainer/P2 top ($24-$25)", 0x4240, 0x4260),
    ("HeartContainer/P2 bot ($34-$35)", 0x4340, 0x4360),
    ("SmallShadow top ($28)", 0x4280, 0x4290),
    ("SmallShadow bot ($38)", 0x4380, 0x4390),
    ("Heart drop top ($29)", 0x4290, 0x42A0),
    ("Heart drop bot ($39)", 0x4390, 0x43A0),
    ("Bombchu top ($2E-$2F)", 0x42E0, 0x4300),
    ("Bombchu bot ($3E-$3F)", 0x43E0, 0x4400),
]


def find_lakesnes() -> Path:
    env = os.environ.get("LAKESNES_DIR", "").strip()
    candidates = [Path(env)] if env else []
    candidates += [
        ROOT.parent / "lakesnes",
        ROOT.parent / "lakesnes" / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ]
    for path in candidates:
        if path and (path / "snes" / "cpu.c").is_file():
            return path
    raise RuntimeError("Could not locate lakesnes/snes/cpu.c")


def _extract_horse_table_header() -> str:
    lines = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text().splitlines()
    return "\n".join(line for line in lines if not line.lstrip().startswith("assert "))


def assemble_vblank_rom(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "Masks").mkdir(exist_ok=True)
    (folder / "Masks/gfx").mkdir(exist_ok=True)
    for rel in [
        "Masks/horse_ground_clearance.asm",
        "Masks/horse_mounted_helpers.asm",
        "Masks/horse_sparse_runtime.asm",
        "Masks/horse_form.asm",
    ]:
        txt = (ROOT / rel).read_text()
        txt = re.sub(r"(?m)^(\s*)assert\s+read\d.*$", r"\1; [stripped]", txt)
        (folder / rel).write_text(txt)
    for bin_rel in [
        "Masks/gfx/horse_sparse.4bpp",
        "Masks/gfx/horse_item_restore.4bpp",
        "Masks/gfx/horse_ranch_restore.4bpp",
        "Masks/gfx/horse_palette.bin",
        "Masks/gfx/horse_npc_rows.4bpp",
    ]:
        (folder / bin_rel).write_bytes((ROOT / bin_rel).read_bytes())
    (folder / "Masks/gfx/horse_sparse_tables.asm").write_text(_extract_horse_table_header() + "\n")

    asm = folder / "fixture.asm"
    asm.write_text(
        f"""lorom
macro m8()
  SEP #$20
endmacro
macro a16()
  REP #$20
endmacro

!CurrentMask = $02B2
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 1
HorseCharge_Tick_Long = ${STUB_FRAME_END_SCAN:06X}
!SideQuest2_RanchGirl = $01
!DEKU_WINGS_NMI_DEFINED = 1
InCutScene = $7EF303
SideQuestProg2 = $7EF3D8
LoadDayNightPaletteEffect = ${STUB_LOAD_DAYNIGHT:06X}
Palette_ArmorAndGloves = ${STUB_PAL_ARMOR:06X}
ResetToLinkGraphics = ${STUB_RESET_LINK_GFX:06X}
Sprite_SpawnDynamically = ${STUB_SPRITE_SPAWN:06X}
HorseGame_State = $7F5410
HorseGame_Tick = ${STUB_HORSE_GAME_TICK:06X}
HorseGame_KidStartCheck = ${STUB_KID_START:06X}
HorseForm_SuppressMountedButtons = $53E800
Horse_AnchorArea = $7E1EFE
Horse_OffState = $7F5400
Horse_OffClear = $7F5402
HorseForm_SaveOutdoorAnchor_Long = ${STUB_SAVE_ANCHOR:06X}
HorseForm_MaintainParkedNpc_Long = ${STUB_MAINTAIN_NPC:06X}
Horse_OffRestore = ${STUB_OFF_RESTORE:06X}
Horse_OffRanchNpc = ${STUB_OFF_RANCH_NPC:06X}
Horse_FrameEndScan = ${STUB_FRAME_END_SCAN:06X}
DekuWings_NmiUpload = ${STUB_DEKU_WINGS_NMI:06X}

SprX = $0D10
SprXH = $0D30
SprY = $0D00
SprYH = $0D20
SprAction = $0D80
SprFrame = $0DC0
SprMiscA = $0DA0
SprBulletproof = $0BA0

; Exact Core/symbols.asm Horse transient block
Horse_Marker           = $7E1EDE
Horse_State            = $7E1EE0
Horse_JumpTimer        = $7E1EE1
Horse_JumpCooldown     = $7E1EE2
Horse_JumpDir          = $7E1EE3
Horse_JumpZ            = $7E1EE4
Horse_AnimTimer        = $7E1EE5
Horse_Frame            = $7E1EE6
Horse_UploadedFrame    = $7E1EE7
Horse_NpcActive        = $7E1EE8
Horse_NpcFrame         = $7E1EE9
Horse_NpcUploadedFrame = $7E1EEA
Horse_PalLoaded        = $7E1EEB
Horse_DismountCooldown = $7E1EEC
Horse_HasAnchor        = $7E1EED
Horse_JumpStep         = $7E1EEE
Horse_PushTimer        = $7E1EEF
Horse_JumpStartX       = $7E1EF0
Horse_JumpStartY       = $7E1EF2
Horse_JumpEndX         = $7E1EF4
Horse_JumpEndY         = $7E1EF6
Horse_AnchorX          = $7E1EF8
Horse_AnchorY          = $7E1EFA
Horse_NpcSlot          = $7E1EFC
Horse_InteractDelay    = $7E1EFD

org $058000
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  RTL : NOP : NOP : NOP
  LDA.b #$00 : RTL : NOP
  LDA.b #$00 : CLC : RTL
  RTL : NOP : NOP : NOP
org ${STUB_DEKU_WINGS_NMI:06X}
  RTL

org $53E800
  RTS

org $538000
HorseGraphics:
  incbin "Masks/gfx/horse_sparse.4bpp"
HorseGraphics_End:
HorseItemRestore:
  incbin "Masks/gfx/horse_item_restore.4bpp"
HorseRanchRestore:
  incbin "Masks/gfx/horse_ranch_restore.4bpp"
  incsrc "Masks/gfx/horse_sparse_tables.asm"
HorsePalette:
  incbin "Masks/gfx/horse_palette.bin"
HorseNpcTail:
  incbin "Masks/gfx/horse_npc_rows.4bpp"
  incsrc "Masks/horse_form.asm"
assert pc() <= $53D000

org $53D000
  incsrc "Masks/horse_mounted_helpers.asm"
assert pc() <= $53E000

org $0DA120
  dw $00C0, $00C0, $00C0
org $0DA126
  dw $2000, $2000, $2000, $2000
"""
    )
    image = folder / "fixture.sfc"
    image.write_bytes(b"\x00" * 0x300000)
    res = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", asm.name, image.name],
        cwd=folder,
        capture_output=True,
        text=True,
    )
    assert res.returncode == 0, res.stdout + res.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            image.with_suffix(".sym").read_text(),
        )
    }
    return image.read_bytes(), labels


class VBlankBudgetFixture(Fixture):
    """LakeSnes 65816 fixture with hardware-accurate SNES VRAM + $43x2 auto-increment DMA."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int]):
        super().__init__(lib, rom, labels)
        self.cpu.db = 0x00
        self.vram = bytearray(0x10000)  # 64 KB VRAM (word-addressed)
        self.vram_addr = 0
        self.mmio: dict[int, int] = {}
        # Initialize vanilla NMI DMA0..4 mode=$1801, bank=$7E
        for ch in range(5):
            base = 0x4300 + ch * 0x10
            self.mmio[base + 0] = 0x01
            self.mmio[base + 1] = 0x18
            self.mmio[base + 4] = 0x7E
        self.dma_writes: list[tuple[int, int, int, int, int]] = []
        self.jumped_target: str | None = None
        self.deku_wings_calls: list[dict[str, int]] = []
        self.pal_armor_calls: int = 0
        self.off_ranch_return: tuple[bool, int] = (False, 0)  # (carry, A)
        self.stubs = {
            STUB_DMA_CONT_8ADB: "dma_8adb",
            STUB_DMA_CONT_8B25: "dma_8b25",
            STUB_DMA_NATIVE_8A12: "dma_8a12",
            STUB_DEKU_WINGS_NMI: "deku_wings",
            STUB_OFF_RANCH_NPC: "off_ranch",
            STUB_PAL_ARMOR: "pal_armor",
        }

    def _read_bus_byte(self, bank: int, off: int) -> int:
        if bank == 0x7E:
            return self.ram[off]
        if bank == 0x7F:
            return self.ram[0x10000 + off]
        if (bank & 0x7F) < 0x7E and off >= 0x8000:
            pc = ((bank & 0x7F) * 0x8000) + (off - 0x8000)
            return self.rom[pc] if pc < len(self.rom) else 0
        return self.ram[off] if off < 0x2000 else 0

    def _write_mmio(self, off: int, val: int) -> None:
        self.mmio[off] = val & 0xFF
        if off == 0x2116:
            self.vram_addr = (self.vram_addr & 0xFF00) | (val & 0xFF)
        elif off == 0x2117:
            self.vram_addr = (self.vram_addr & 0x00FF) | ((val & 0xFF) << 8)
        elif off == 0x420B:
            for ch in range(5):
                if val & (1 << ch):
                    base = 0x4300 + ch * 0x10
                    src = self.mmio.get(base + 2, 0) | (self.mmio.get(base + 3, 0) << 8)
                    bank = self.mmio.get(base + 4, 0)
                    size = self.mmio.get(base + 5, 0) | (self.mmio.get(base + 6, 0) << 8)
                    if size == 0:
                        size = 0x10000
                    words = size // 2
                    start_vram = self.vram_addr
                    for i in range(size):
                        b = self._read_bus_byte(bank, (src + i) & 0xFFFF)
                        vbyte = ((start_vram * 2) + i) & 0xFFFF
                        self.vram[vbyte] = b
                    # Hardware auto-increment of A-bus address ($43x2/$43x3) and VMADDR
                    new_src = (src + size) & 0xFFFF
                    self.mmio[base + 2] = new_src & 0xFF
                    self.mmio[base + 3] = (new_src >> 8) & 0xFF
                    self.mmio[base + 5] = 0
                    self.mmio[base + 6] = 0
                    self.vram_addr = (start_vram + words) & 0xFFFF
                    self.dma_writes.append((start_vram, start_vram + words, bank, src, size))

    def write(self, addr: int, val: int) -> None:
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (off in (0x2116, 0x2117, 0x420B) or 0x4300 <= off <= 0x434F):
            self._write_mmio(off, val)
            return
        super().write(addr, val)

    def read(self, addr: int) -> int:
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (off in (0x2116, 0x2117, 0x420B) or 0x4300 <= off <= 0x434F):
            return self.mmio.get(off, 0)
        return super().read(addr)

    def stub(self, name: str):
        c = self.cpu
        if name in ("dma_8adb", "dma_8b25", "dma_8a12"):
            self.jumped_target = name
            return "STOP"
        if name == "deku_wings":
            self.deku_wings_calls.append({
                "db": c.db,
                "mf": int(c.mf),
                "xf": int(c.xf),
                "4304": self.mmio.get(0x4304, -1),
                "4314": self.mmio.get(0x4314, -1),
                "4302": self.mmio.get(0x4302, 0) | (self.mmio.get(0x4303, 0) << 8),
            })
            return False  # execute RTL at stub
        if name == "off_ranch":
            carry, aval = self.off_ranch_return
            c.c = carry
            self.acc(aval)
            # Execute RTL right away by advancing to RTL opcode (offset +3 at $058023)
            c.pc = (STUB_OFF_RANCH_NPC & 0xFFFF) + 3
            return True
        if name == "pal_armor":
            self.pal_armor_calls += 1
            return False  # execute RTL at $058000
        return False

    def run_jsl(self, name: str, mf: bool = True, xf: bool = False, a: int = 0, x: int = 0, y: int = 0, db: int = 0) -> int:
        c = self.cpu
        c.db = db
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        self.put(sp, c.k)
        self.put(sp - 1, 0x6F)
        self.put(sp - 2, 0xFF)
        c.sp -= 3
        for count in range(40000):
            addr = (c.k << 16) | c.pc
            if addr == ((entry & 0xFF0000) | 0x7000):
                assert c.sp == sp and not self.bad_writes, (name, hex(c.sp), hex(sp), self.bad_writes)
                return count
            if addr in self.stubs:
                r = self.stub(self.stubs[addr])
                if r == "STOP":
                    return count
                if r is True:
                    continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

    def run_jml(self, name: str, mf: bool = True, xf: bool = False, a: int = 0, x: int = 0, y: int = 0, db: int = 0) -> int:
        c = self.cpu
        c.db = db
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        self.jumped_target = None
        for count in range(40000):
            addr = (c.k << 16) | c.pc
            if addr in self.stubs:
                r = self.stub(self.stubs[addr])
                if r == "STOP":
                    return count
                if r is True:
                    continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

    def setup_ranch_profile(self) -> None:
        self.put(0x1B, 0x00)
        self.put(0x8A, 0x00)
        self.put(0x0AA3, 0x06)
        self.put(0x7EC2FC, 0x4F)
        self.put(0x7EC2FD, 0x49)
        self.put(0x7EC2FE, 0x4A)
        self.put(0x7EC2FF, 0x50)

    def vram_slice(self, word_start: int, nbytes: int) -> bytes:
        b0 = word_start * 2
        return bytes(self.vram[b0 : b0 + nbytes])


class TestHorseVBlankBudget(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="horse-vblank-budget-")
        d = Path(cls._tmp.name)
        lakesnes = find_lakesnes()
        lib_path = d / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes/cpu.c"),
                str(lakesnes / "snes/statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        cls.lib = C.CDLL(str(lib_path))
        cls.lib.cpu_init.restype = C.POINTER(Cpu)
        cls.lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        cls.lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.rom, cls.labels = assemble_vblank_rom(d / "build")
        cls.sparse_bin = (ROOT / "Masks/gfx/horse_sparse.4bpp").read_bytes()
        cls.item_restore_bin = (ROOT / "Masks/gfx/horse_item_restore.4bpp").read_bytes()
        cls.ranch_restore_bin = (ROOT / "Masks/gfx/horse_ranch_restore.4bpp").read_bytes()
        tbl = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text()
        cls.frame_ptrs = [
            [int(x, 16) for x in m]
            for m in re.findall(
                r"dw HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),"
                r"HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+)",
                tbl,
            )
        ]
        cls.frame_counts = [
            int(x, 16)
            for x in re.search(r"HorseFrame_Count:\s*\n\s*db\s+([^\n]+)", tbl).group(1).replace("$", "").split(",")
        ]

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def make_fx(self) -> VBlankBudgetFixture:
        return VBlankBudgetFixture(self.lib, self.rom, self.labels)

    def test_all_19_frames_bit_exact_vram_and_dropable_safety(self):
        """Every mounted frame 0..18 transfers bit-exact pixels via auto-inc + CH0/CH1 and touches zero protected dropables."""
        for frame in range(19):
            fx = self.make_fx()
            try:
                fx.word(HORSE_MARKER, 0x4852)
                fx.put(HORSE_PAL_LOADED, 0x81)
                fx.put(HORSE_NPC_UPLOADED, 0xFF)
                fx.put(HORSE_UPLOADED_FRAME, 0xFF)
                fx.put(HORSE_FRAME, frame)
                fx.put(HORSE_DISMOUNT_CD, 0x00)  # Even with cooldown=0, anim tiles MUST be skipped!
                fx.put(0x10, 0x09)
                fx.put(0x11, 0x00)
                fx.word(0x0ADC, 0x9200)
                fx.word(0x0134, 0x3800)
                fx.word(0x04, 0x1234)
                fx.word(0x06, 0x5678)

                insns = fx.run_jsl("Horse_NmiUpload", mf=True, xf=False, y=0xABCD)
                self.assertEqual(fx.get(HORSE_UPLOADED_FRAME), frame)
                self.assertEqual(fx.get(HORSE_PAL_LOADED), 0x01)
                self.assertEqual(fx.cpu.y, 0xABCD)
                self.assertEqual(fx.get(0x04) | (fx.get(0x05) << 8), 0x1234)
                self.assertEqual(fx.get(0x06) | (fx.get(0x07) << 8), 0x5678)

                # Must NOT upload 1KB animated tiles ($3800) on horse frame upload!
                self.assertFalse(any(s == 0x3800 for s, *_ in fx.dma_writes), (frame, fx.dma_writes))
                # DekuWings_NmiUpload tail chain MUST still run with clean $4304=$7E, $4314=$7E, $4302=$0ADC!
                self.assertEqual(len(fx.deku_wings_calls), 1)
                self.assertEqual(fx.deku_wings_calls[0]["4304"], 0x7E)
                self.assertEqual(fx.deku_wings_calls[0]["4314"], 0x7E)
                self.assertEqual(fx.deku_wings_calls[0]["4302"], 0x9200)

                # Protected dropable VRAM check
                for s, e, bk, src, sz in fx.dma_writes:
                    for pname, plo, phi in PROTECTED_VRAM_RANGES:
                        self.assertTrue(
                            e <= plo or s >= phi,
                            f"Frame {frame} write [${s:04X}..${e:04X}) hit {pname} [${plo:04X}..${phi:04X})",
                        )

                # Bit-exact pixel check for every group!
                ptrs = self.frame_ptrs[frame]
                cnt = self.frame_counts[frame]
                # Group 0 ($4000 / $4100, 256B each)
                p0 = ptrs[0]
                self.assertEqual(fx.vram_slice(0x4000, 256), self.sparse_bin[p0 : p0 + 256])
                self.assertEqual(fx.vram_slice(0x4100, 256), self.sparse_bin[p0 + 256 : p0 + 512])
                # Group 1 Rider ($4080/$40C0/$4180/$41C0, 64B each)
                p1 = ptrs[1]
                self.assertEqual(fx.vram_slice(0x4080, 64), self.sparse_bin[p1 : p1 + 64])
                self.assertEqual(fx.vram_slice(0x40C0, 64), self.sparse_bin[p1 + 64 : p1 + 128])
                self.assertEqual(fx.vram_slice(0x4180, 64), self.sparse_bin[p1 + 128 : p1 + 192])
                self.assertEqual(fx.vram_slice(0x41C0, 64), self.sparse_bin[p1 + 192 : p1 + 256])
                # Remaining parts
                if cnt == 8:
                    p4 = ptrs[2]
                    self.assertEqual(fx.vram_slice(0x40A0, 32), self.sparse_bin[p4 : p4 + 32])
                    self.assertEqual(fx.vram_slice(0x41A0, 32), self.sparse_bin[p4 + 64 : p4 + 96])
                    p5, p6, p7 = ptrs[3], ptrs[4], ptrs[5]
                else:
                    p5, p6, p7 = ptrs[2], ptrs[3], ptrs[4]
                self.assertEqual(fx.vram_slice(0x4260, 64), self.sparse_bin[p5 : p5 + 64])
                self.assertEqual(fx.vram_slice(0x4360, 64), self.sparse_bin[p5 + 64 : p5 + 128])
                self.assertEqual(fx.vram_slice(0x42A0, 64), self.sparse_bin[p6 : p6 + 64])
                self.assertEqual(fx.vram_slice(0x43A0, 64), self.sparse_bin[p6 + 64 : p6 + 128])
                if cnt >= 7:
                    self.assertEqual(fx.vram_slice(0x42C0, 64), self.sparse_bin[p7 : p7 + 64])
                    self.assertEqual(fx.vram_slice(0x43C0, 64), self.sparse_bin[p7 + 64 : p7 + 128])

                total_bytes = sum(sz for *_, sz in fx.dma_writes)
                expected_bytes = {6: 1024, 7: 1152, 8: 1216}[cnt]
                self.assertEqual(total_bytes, expected_bytes, (frame, cnt, total_bytes))
                self.assertLessEqual(insns, 185, f"Frame {frame} took too many insns: {insns}")
            finally:
                fx.close()

    def test_gallop_rider_dedup_and_vblank_budget(self):
        """Galloping 7->8->9->16->17->18->7 skips redundant 256B Rider DMA; turning S->Side uploads Rider."""
        fx = self.make_fx()
        try:
            fx.word(HORSE_MARKER, 0x4852)
            fx.put(HORSE_NPC_UPLOADED, 0xFF)
            fx.put(HORSE_DISMOUNT_CD, 0x00)
            fx.put(0x10, 0x09)
            fx.put(0x11, 0x00)
            fx.word(0x0ADC, 0x9000)
            fx.word(0x0134, 0x3800)

            # Frame 7 -> 8 (8-part gallop, same Side rider +$1680): MUST skip Rider (960B total, NOT 1216B!)
            fx.put(HORSE_UPLOADED_FRAME, 7)
            fx.put(HORSE_FRAME, 8)
            fx.put(HORSE_PAL_LOADED, 0x81)
            insns_gallop = fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            total_bytes = sum(sz for *_, sz in fx.dma_writes)
            self.assertEqual(total_bytes, 960, f"Expected 960B on 8-part gallop dedup, got {total_bytes}")
            self.assertFalse(any(s in (0x4080, 0x40C0, 0x4180, 0x41C0) for s, *_ in fx.dma_writes))
            self.assertLessEqual(insns_gallop, 180, f"8-part gallop insns={insns_gallop}")

            # Direction turn: Frame 8 (Side) -> Frame 0 (South, different Rider +$0200): MUST upload Rider (1024B)!
            fx.dma_writes.clear()
            fx.put(HORSE_FRAME, 0)
            fx.put(HORSE_PAL_LOADED, 0x81)
            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            total_bytes_turn = sum(sz for *_, sz in fx.dma_writes)
            self.assertEqual(total_bytes_turn, 1024)
            rider_dests = {s for s, *_ in fx.dma_writes if s in (0x4080, 0x40C0, 0x4180, 0x41C0)}
            self.assertEqual(rider_dests, {0x4080, 0x40C0, 0x4180, 0x41C0})
            p1 = self.frame_ptrs[0][1]
            self.assertEqual(fx.vram_slice(0x4080, 64), self.sparse_bin[p1 : p1 + 64])
        finally:
            fx.close()

    def test_border_crossing_sub_nonzero_keeps_steady_zero_horse_dma(self):
        """During OW border transition ($10=$09, $11=$06), unchanged resident frame does ZERO horse DMA."""
        fx = self.make_fx()
        try:
            fx.word(HORSE_MARKER, 0x4852)
            fx.put(HORSE_NPC_UPLOADED, 0xFF)
            fx.put(HORSE_UPLOADED_FRAME, 8)
            fx.put(HORSE_FRAME, 8)
            fx.put(HORSE_PAL_LOADED, 0x81)
            fx.put(HORSE_DISMOUNT_CD, 0x00)
            fx.put(0x10, 0x09)
            fx.put(0x11, 0x06)  # Active OW border scroll transition!
            fx.word(0x0ADC, 0x9000)
            fx.word(0x0134, 0x3800)

            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            # Only the 1KB animated tile replay runs (ZERO horse VRAM writes!)
            self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x3800, 0x0400)])
            self.assertEqual(len(fx.deku_wings_calls), 1)

            # Crowded steady frame ($17=3 scroll + $15=1 CGRAM): skips even the 1KB animated tiles!
            fx.dma_writes.clear()
            fx.put(HORSE_PAL_LOADED, 0x81)
            fx.put(0x17, 0x03)
            fx.put(0x15, 0x01)
            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            self.assertEqual(fx.dma_writes, [])
            self.assertEqual(len(fx.deku_wings_calls), 2)
        finally:
            fx.close()

    def test_dismount_restore_item_and_npc_cells_bit_exact_and_skip_anim(self):
        """Dismount item restore (384B) & Ranch NPC restore (1024B) are bit-exact and skip 1KB animated tiles."""
        fx = self.make_fx()
        try:
            fx.word(HORSE_MARKER, 0x4852)
            fx.put(HORSE_UPLOADED_FRAME, 6)
            fx.put(HORSE_NPC_UPLOADED, 14)
            fx.put(HORSE_NPC_ACTIVE, 0)
            fx.put(HORSE_PAL_LOADED, 0x01)  # bit 7 clear -> .not_mounted
            fx.put(HORSE_DISMOUNT_CD, 0x00)
            fx.put(0x10, 0x09)
            fx.setup_ranch_profile()
            fx.word(0x0ADC, 0x9100)
            fx.word(0x0134, 0x3800)

            fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            self.assertEqual(fx.get(HORSE_UPLOADED_FRAME), 0xFF)
            self.assertEqual(fx.get(HORSE_NPC_UPLOADED), 0xFF)
            # Bit-exact item restore (4 bursts: 64+128+64+128 = 384B, skipping $4280/$4380)
            self.assertEqual(fx.vram_slice(0x4260, 64), self.item_restore_bin[0:64])
            self.assertEqual(fx.vram_slice(0x42A0, 128), self.item_restore_bin[64:192])
            self.assertEqual(fx.vram_slice(0x4360, 64), self.item_restore_bin[192:256])
            self.assertEqual(fx.vram_slice(0x43A0, 128), self.item_restore_bin[256:384])
            self.assertEqual(fx.vram_slice(0x4280, 64), bytes(64))
            # Bit-exact Ranch C2 restore (1 contiguous 1024B burst to $5000)
            self.assertEqual(fx.vram_slice(0x5000, 1024), self.ranch_restore_bin[:1024])
            # 1KB animated tiles skipped; DekuWings still chained cleanly!
            self.assertFalse(any(s == 0x3800 for s, *_ in fx.dma_writes))
            self.assertEqual(len(fx.deku_wings_calls), 1)
            self.assertEqual(fx.deku_wings_calls[0]["4302"], 0x9100)
        finally:
            fx.close()

    def test_single_pass_link_dma_prefix_budget_and_arrow_detection(self):
        """Horse_LinkDmaPrefix runs single-pass slot+arrow scan under tight instruction budget."""
        fx = self.make_fx()
        try:
            fx.word(HORSE_MARKER, 0x4852)
            fx.put(0x02B2, 0x09)
            fx.put(0x10, 0x09)
            fx.put(0x1B, 0x00)
            fx.word(0x0AE0, 0xB280)
            fx.word(0x0AE2, 0xB2E0)

            insns_no_arrow = fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            self.assertEqual(fx.jumped_target, "dma_8adb")
            self.assertLessEqual(insns_no_arrow, 200, f"Prefix insns={insns_no_arrow}")

            # With live rider arrow ($09 in ancilla slot 3): routes to .arrow_cells -> $008B25!
            fx.dma_writes.clear()
            fx.put(0x0C4A + 3, 0x09)
            fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            self.assertEqual(fx.jumped_target, "dma_8b25")
            self.assertEqual(fx.mmio[0x4304], 0x7E)
            self.assertEqual(fx.mmio[0x4314], 0x7E)
        finally:
            fx.close()

    def test_menu_and_overlay_safety_all_gates(self):
        """All safe $0E overlays hold Mounted + Ranch NPC VRAM & OAM; unsafe $0E restores/falls back cleanly."""
        safe_cases = [
            (0x01, 0x00),  # Start Pause Menu
            (0x02, 0x00),  # Dialogue / Text
            (0x0B, 0x00),  # Select Save & Quit Menu
            (0x04, 0x00),  # Red Potion
            (0x08, 0x00),  # Green Potion
            (0x09, 0x00),  # Blue Potion
            (0x07, 0x00),  # Overworld Map fade-out
            (0x0A, 0x00),  # Flute Menu fade-out
        ]
        unsafe_cases = [
            (0x05, 0x00),  # Desert Prayer
            (0x07, 0x01),  # Active Overworld Map
            (0x0A, 0x01),  # Active Flute Menu
            (0x03, 0x00),  # Dungeon Map
        ]

        # 1. Mounted Horse_LinkDmaPrefix + Horse_PlayerOamHook alignment
        for sub, s200 in safe_cases:
            fx = self.make_fx()
            try:
                fx.word(HORSE_MARKER, 0x4852)
                fx.put(0x02B2, 0x09)
                fx.put(0x10, 0x0E)
                fx.put(0x11, sub)
                fx.put(0x0200, s200)
                fx.put(0x1B, 0x00)
                fx.put(HORSE_PAL_LOADED, 0x01)
                fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                self.assertEqual(fx.jumped_target, "dma_8adb", f"Safe $0E/${sub:02X} ($200={s200}) rejected!")
                self.assertEqual(fx.get(HORSE_PAL_LOADED), 0x81)
            finally:
                fx.close()

        for sub, s200 in unsafe_cases:
            fx = self.make_fx()
            try:
                fx.word(HORSE_MARKER, 0x4852)
                fx.put(0x02B2, 0x09)
                fx.put(0x10, 0x0E)
                fx.put(0x11, sub)
                fx.put(0x0200, s200)
                fx.put(0x1B, 0x00)
                fx.put(HORSE_PAL_LOADED, 0x01)
                fx.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                self.assertEqual(fx.jumped_target, "dma_8a12", f"Unsafe $0E/${sub:02X} ($200={s200}) wrongly granted!")
                self.assertEqual(fx.get(HORSE_PAL_LOADED) & 0x80, 0)

                # Horse_PlayerOamHook MUST fall through to native PlayerOam_Main (returns via RTL with Y=0, A=$11)!
                fx.run_jsl("Horse_PlayerOamHook", mf=True, xf=True, db=0x0D)
                self.assertEqual(fx.cpu.y & 0xFF, 0x00)
                self.assertEqual(fx.cpu.a & 0xFF, sub)
            finally:
                fx.close()

        # 2. Ranch NPC Horse_NmiUpload .on_ranch holds VRAM on ALL safe overlays (fixes villager-head explosion!)
        for sub, s200 in safe_cases:
            fx = self.make_fx()
            try:
                fx.word(HORSE_MARKER, 0x4852)
                fx.put(0x02B2, 0x00)
                fx.put(0x10, 0x0E)
                fx.put(0x11, sub)
                fx.put(0x0200, s200)
                fx.put(HORSE_UPLOADED_FRAME, 0xFF)
                fx.put(HORSE_NPC_ACTIVE, 1)
                fx.put(HORSE_NPC_FRAME, 14)
                fx.put(HORSE_NPC_UPLOADED, 14)
                fx.put(HORSE_DISMOUNT_CD, 1)
                fx.setup_ranch_profile()
                fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
                self.assertEqual(fx.get(HORSE_NPC_UPLOADED), 14, f"Ranch NPC VRAM wiped on safe $0E/${sub:02X}!")
                self.assertEqual(fx.dma_writes, [], f"Unexpected DMA on safe $0E/${sub:02X}: {fx.dma_writes}")
            finally:
                fx.close()

        # Unsafe $0E cleanly restores Ranch C2 cells (1024B to $5000)
        for sub, s200 in unsafe_cases:
            fx = self.make_fx()
            try:
                fx.word(HORSE_MARKER, 0x4852)
                fx.put(0x02B2, 0x00)
                fx.put(0x10, 0x0E)
                fx.put(0x11, sub)
                fx.put(0x0200, s200)
                fx.put(HORSE_UPLOADED_FRAME, 0xFF)
                fx.put(HORSE_NPC_ACTIVE, 1)
                fx.put(HORSE_NPC_FRAME, 14)
                fx.put(HORSE_NPC_UPLOADED, 14)
                fx.put(HORSE_DISMOUNT_CD, 0)
                fx.setup_ranch_profile()
                fx.run_jsl("Horse_NmiUpload", mf=True, xf=False)
                self.assertEqual(fx.get(HORSE_NPC_UPLOADED), 0xFF, f"Ranch NPC not restored on unsafe $0E/${sub:02X}!")
                self.assertEqual([(s, sz) for s, _, _, _, sz in fx.dma_writes], [(0x5000, 0x0400)])
            finally:
                fx.close()

    def test_cross_world_non_uniform_sp3_palette_refreshes_horse_brown(self):
        """Non-uniform SW/DW SP-3 palette overwrite (e.g. Goron Coast $B0 green) triggers Palette_ArmorAndGloves."""
        fx = self.make_fx()
        try:
            fx.word(HORSE_MARKER, 0x4852)
            fx.put(0x02B2, 0x09)
            fx.put(0x10, 0x09)
            fx.put(0x11, 0x00)
            fx.put(0x13, 0x0F)
            fx.put(0x1B, 0x00)
            # Simulate Goron Coast ($B0) non-uniform green SP-3[14..15] ($7EC67C != $7EC67E, both != $239F)
            fx.put(0x7EC67C, 0xE0)
            fx.put(0x7EC67D, 0x03)
            fx.put(0x7EC67E, 0x40)
            fx.put(0x7EC67F, 0x02)
            fx.run_jsl("HorseForm_FrameTick", mf=True, xf=True)
            self.assertEqual(fx.pal_armor_calls, 1, "Non-uniform green SP-3 must trigger Horse palette reload!")

            # Once $7EC67E holds HorsePalette+12 ($239F), steady frame does NOT spam Palette_ArmorAndGloves
            fx.pal_armor_calls = 0
            fx.put(0x7EC67E, 0x9F)
            fx.put(0x7EC67F, 0x23)
            fx.run_jsl("HorseForm_FrameTick", mf=True, xf=True)
            self.assertEqual(fx.pal_armor_calls, 0, "Matching HorsePalette[6] must not trigger redundant reload!")
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main(verbosity=2)
