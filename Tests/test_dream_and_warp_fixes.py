#!/usr/bin/env python3
"""Compiled 65816 (Asar + LakeSnes CPU) & structural tests for Q-OOS-13:

Covers the 4 tracked Dream / Opening / Post-Kydrog Warp technical bugs:
  1. DREAM-PAL: Maple's-bed dream blanket palette (no PaletteFilter wrap;
     Blanket_UseBedColors writes $739C/$56B5 to PAL_SPR6A + PALB_SPR6A on both
     sleep and DreamWake_TuckIntoBed).
  2. DREAM-LINK: Link hidden ($4B=$0C) in Link_WarpToRoom during Module07_15
     fade-out, restored by Part00_RoomSprites (staying visible for Courage,
     re-hidden by Wisdom/Power stage hooks), and kept hidden through
     DreamReturn_Begin until DreamWisdom_ReleaseLink on Dream Hut reload.
  3. Part 0 storm bit decoupling (Overworld/storm.asm):
     - Active strictly on Kalyxo Light World ($8A < $40), excluding both Eon
       Abyss ($40-$7F) and Special Overworld ($80-$BF) so Sky/Lyra overlays
       and ActivateSubScreen never inherit Part 0 rain.
     - Decoupled from GameState < 2 at Overworld_ScrollTransition ($02AC12),
       AdjustOverworldAmbiance ($02C4B6), and WorldMap_FadeOut ($0ABA04).
     - Clears cleanly once back on Kalyxo after Kydrog (SavedWorld == $00 and
       Story2_KydrogEncounter set), stripping only $10 rain nibbles from LW
       !OverworldMusicCache entries.
  4. Post-Kydrog DW pyramid warp graphics & Glade ambush Abyss landing:
     - Overworld_ReloadSubscreenOverlay_Interupt (.noSubscreenOverlay) sets
       $8C=$FF, $1C=$16, $1D=$00, $9A=$00 (fixing file-select/dungeon leaks).
     - MirrorWarp_NoOverlayUploadTable repoints $7F4000-$7F407F to unused BG1
       tilemap $1000-$1FC0 when $8C==$FF, leaving real overlays untouched.
     - Core/patches.asm ($00EF80) and Masks/gbc_form.asm ($07AB09) contracts.
     - KydrogLanding_Tick (!ENABLE_GLADE_AMBUSH=1): locks $0FFC (NOMENU) during
       states 2-3, guards $95 mosaic decrement against underflow ($00->$F0),
       pans $011C smoothly back to $0000, and restores Link/camera/mosaic/menu
       state on both normal completion and mid-pan abort.
"""
from __future__ import annotations

import ctypes as C
import os
from pathlib import Path
import re
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]


def _find_lakesnes() -> Path:
    for cand in LAKESNES_CANDIDATES:
        if cand is not None and (cand / "snes" / "cpu.c").is_file():
            return cand
    raise RuntimeError("LakeSnes checkout not found (set LAKESNES_DIR)")


def _build_cpu_lib(temp_dir: Path) -> C.CDLL:
    lakesnes = _find_lakesnes()
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


def _parse_wla_symbols(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for m in re.finditer(
        r"(?m)^([0-9a-fA-F]{2}):([0-9a-fA-F]{4})\s+(\S+)$",
        sym_path.read_text(encoding="utf-8"),
    ):
        addr = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
        name = m.group(3)
        labels[name] = addr
        if name.startswith("Oracle_"):
            labels.setdefault(name[len("Oracle_"):], addr)
    return labels


def _run_asar(asm_path: Path, rom_path: Path) -> tuple[bytes, dict[str, int]]:
    proc = subprocess.run(
        [
            "asar",
            "--no-title-check",
            "--fix-checksum=off",
            "--symbols=wla",
            f"-I{ROOT.as_posix()}",
            str(asm_path),
            str(rom_path),
        ],
        capture_output=True,
        text=True,
        cwd=str(ROOT),
    )
    if proc.returncode != 0:
        raise AssertionError(f"Asar failed:\n{proc.stdout}\n{proc.stderr}")
    return rom_path.read_bytes(), _parse_wla_symbols(rom_path.with_suffix(".sym"))


class TraceFixture(Fixture):
    """LakeSnes 65816 fixture with clean full-24-bit WRAM/LoROM memory & JSL call hooks."""

    def __init__(self, lib: C.CDLL, rom: bytes, labels: dict[str, int], stubs=None):
        super().__init__(lib, rom, labels)
        self.stubs = dict(stubs or {})
        self.calls: list[tuple[str, int, int, int]] = []

    def read(self, adr: int) -> int:
        offset = self.ram_offset(adr)
        if offset is not None:
            return self.ram[offset]
        if adr & 0x8000:
            pc = ((adr >> 16) & 0x7F) * 0x8000 + (adr & 0x7FFF)
            if pc < len(self.rom):
                return self.rom[pc]
        return 0

    def write(self, adr: int, val: int) -> None:
        offset = self.ram_offset(adr)
        if offset is not None:
            self.ram[offset] = val & 0xFF

    def read_w(self, addr: int) -> int:
        return self.read(addr) | (self.read(addr + 1) << 8)

    def write_w(self, addr: int, val: int) -> None:
        self.write(addr, val & 0xFF)
        self.write(addr + 1, (val >> 8) & 0xFF)

    def call_jsl(
        self,
        target: int,
        *,
        a: int = 0,
        x: int = 0,
        y: int = 0,
        db: int = 0,
        m16: bool = False,
        x16: bool = False,
        c: bool = False,
        max_steps: int = 80_000,
    ) -> int:
        cpu = self.cpu
        cpu.a = a & 0xFFFF
        cpu.x = x & (0xFFFF if x16 else 0xFF)
        cpu.y = y & (0xFFFF if x16 else 0xFF)
        cpu.db = db & 0xFF
        cpu.dp = 0
        cpu.mf = not m16
        cpu.xf = not x16
        cpu.c = c
        cpu.d = False
        # Push sentinel RTL return address ($00:FFFE -> lands at $00:FFFF)
        self.ram[0x1F00] = 0x00
        self.ram[0x1EFF] = 0xFF
        self.ram[0x1EFE] = 0xFE
        cpu.sp = 0x1EFD
        cpu.k = (target >> 16) & 0xFF
        cpu.pc = target & 0xFFFF

        for steps in range(1, max_steps + 1):
            cur = (cpu.k << 16) | cpu.pc
            if cur == 0x00FFFF:
                return steps
            if cur in self.stubs:
                name, handler = self.stubs[cur]
                self.calls.append((name, cpu.a, cpu.x, cpu.y))
                handler(self)
                # Perform RTL from stub
                lo = self.ram[cpu.sp + 1]
                hi = self.ram[cpu.sp + 2]
                bk = self.ram[cpu.sp + 3]
                cpu.sp += 3
                ret = ((hi << 8) | lo) + 1
                cpu.k = bk
                cpu.pc = ret & 0xFFFF
                continue
            self.lib.cpu_runOpcode(self.p)
        raise RuntimeError(
            f"JSL ${target:06X} exceeded {max_steps} steps at ${cpu.k:02X}:{cpu.pc:04X}"
        )


# ---------------------------------------------------------------------------
# Module builders (compiling REAL source files via Asar)
# ---------------------------------------------------------------------------

def _assemble_dream_module(folder: Path) -> tuple[bytes, dict[str, int]]:
    """Compile real maple.asm, dream_wisdom.asm, dream_power.asm, dream_rooms.asm,
    and Part00_RoomSprites from Core/part00.asm."""
    folder.mkdir(parents=True, exist_ok=True)
    rom_path = folder / "dream.sfc"
    rom_path.write_bytes(b"\xFF" * 0x200000)

    part00_src = (ROOT / "Core" / "part00.asm").read_text(encoding="utf-8")
    m = re.search(
        r"(Part00_RoomSprites:\s*\{.*?\n\})",
        part00_src,
        re.S,
    )
    assert m is not None, "Could not locate Part00_RoomSprites in Core/part00.asm"
    part00_room_sprites = m.group(1)

    asm_path = folder / "dream_harness.asm"
    asm_path.write_text(
        "lorom\n"
        'incsrc "Util/macros.asm"\n'
        'incsrc "Core/ram.asm"\n'
        "namespace Oracle\n"
        "{\n"
        'incsrc "Core/link.asm"\n'
        'incsrc "Core/sram.asm"\n'
        'incsrc "Core/symbols.asm"\n'
        "Sprite_Farore = $73\n"
        "macro PlayAnimation(start, end, speed)\n"
        "endmacro\n"
        "macro GotoAction(action)\n"
        "  LDA.b #<action> : STA.w SprAction, X\n"
        "endmacro\n"
        "macro ShowSolicitedMessage(msg)\n"
        "  CLC\n"
        "endmacro\n"
        "macro ShowUnconditionalMessage(msg)\n"
        "  LDA.b #(<msg>&$FF) : LDY.b #(<msg>>>8) : JSL Sprite_ShowMessageUnconditional\n"
        "endmacro\n"
        # Vanilla ROM stubs at their true Core/symbols.asm addresses
        "org $008781 : RTL\n"  # JumpTableLocal
        "org $00D337 : RTL\n"  # DecompressAnimatedUnderworldTiles
        "org $00D4ED : RTL\n"  # WriteTo4BPPBuffer_item_gfx
        "org $00E19B : RTL\n"  # InitializeTilesets
        "org $00EEF1\n"
        "Trap_PaletteFilter_StartBlindingWhite:\n"
        "  RTL\n"
        "org $05E219 : RTL\n"  # Sprite_ShowMessageUnconditional
        "org $078000 : RTL\n"  # Link_Main
        "org $098091 : LDX.b #$00 : RTL\n"  # AncillaAdd_Blanket
        "org $09C2D4 : RTS\n"  # Underworld_LoadSprites .done
        "org $1EF4F3 : RTL\n"  # Sprite_PlayerCantPassThrough
        "org $09F000\n"
        "Call_Part00_RoomSprites:\n"
        "  JSR .inner\n"
        "  RTL\n"
        ".inner:\n"
        "  LDA.b #$FF\n"
        "  JSL Part00_RoomSprites\n"
        "  INC.w $1FF5\n"  # Must be skipped when end-of-list exits via JML $09C2D4
        "  RTS\n"
        # Minimal stubs for non-tested sibling helpers
        "org $08B000\n"
        "Sprite_MoveHoriz: RTL\n"
        "Sprite_MoveVert: RTL\n"
        "D4Water_PlayerControl: RTL\n"
        "Ganondorf_DoorGate: CLC : RTL\n"
        "WallSel_RowToMain: RTL\n"
        "DreamFX_Run: SEC : RTL\n"
        "DreamFX_RoomLoaded: RTL\n"
        # Bank $30 real dream sources
        "org $308000\n"
        'incsrc "Sprites/NPCs/maple.asm"\n'
        'incsrc "Sprites/NPCs/dream_wisdom.asm"\n'
        'incsrc "Sprites/NPCs/dream_power.asm"\n'
        'incsrc "Sprites/NPCs/dream_rooms.asm"\n'
        # Wrappers so JSL can invoke local JSR entrypoints cleanly with DB=$30
        "Call_Sprite_PutLinkToSleep:\n"
        "  PHB : PHK : PLB : JSR Sprite_PutLinkToSleep : PLB : RTL\n"
        "Call_Blanket_UseBedColors:\n"
        "  PHB : PHK : PLB : JSR Blanket_UseBedColors : PLB : RTL\n"
        "Call_Link_WarpToRoom:\n"
        "  PHB : PHK : PLB : JSR Link_WarpToRoom : PLB : RTL\n"
        "Call_DreamReturn_Begin:\n"
        "  PHB : PHK : PLB : JSR DreamReturn_Begin : PLB : RTL\n"
        "Call_DreamWisdom_ReleaseLink:\n"
        "  PHB : PHK : PLB : JSR DreamWisdom_ReleaseLink : PLB : RTL\n"
        # Bank $3A real Part00_RoomSprites + local JSR stubs
        "org $3AB800\n"
        + part00_room_sprites
        + "\n"
        "Part00_CheckpointTrigger: RTS\n"
        "HouseVillager_Stage: RTS\n"
        "}\n"
        "namespace off\n",
        encoding="utf-8",
    )
    return _run_asar(asm_path, rom_path)


def _assemble_storm_module(folder: Path) -> tuple[bytes, dict[str, int]]:
    """Compile real Overworld/storm.asm + Overworld/music_cache.asm hooks."""
    folder.mkdir(parents=True, exist_ok=True)
    image = bytearray(b"\xFF" * 0x200000)

    # Pre-seed exact vanilla hook preimage bytes asserted by music_cache.asm & storm.asm
    for addr in (
        0x00F401, 0x02AE73, 0x02B117, 0x02B126, 0x02B2A1, 0x02B2AA,
        0x02B4FE, 0x02C27D, 0x02C28F, 0x0ABC80,
    ):
        struct.pack_into("<I", image, _snes_to_pc(addr), 0x7F5B00BF)
    for addr in (0x02C49A, 0x02C4AB):
        struct.pack_into("<I", image, _snes_to_pc(addr), 0x7F5B009F)
    image[_snes_to_pc(0x02C4A0):_snes_to_pc(0x02C4A0) + 3] = bytes([0xE0, 0x40, 0x00])
    image[_snes_to_pc(0x02C4B1):_snes_to_pc(0x02C4B1) + 3] = bytes([0xC0, 0x60, 0x00])
    # Vanilla Overworld_ScrollTransition step 4 ($02AC12..$02AC28):
    #   $02AC12: LDA.l $7EF3C5 : CMP.b #$02 : BCS $02AC1D : JMP $AC27
    #   $02AC1D: LDA.b $11 : CMP.b #$12 : BEQ $AC1A : JSL $0BFE70
    #   $02AC27: INC.b $11
    scroll_bytes = bytes.fromhex(
        "AFC5F37EC902B0034C27ACA511C912F0F72270FE0BE611"
    )
    image[_snes_to_pc(0x02AC12):_snes_to_pc(0x02AC12) + len(scroll_bytes)] = scroll_bytes

    rom_path = folder / "storm.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "storm_harness.asm"
    asm_path.write_text(
        "lorom\n"
        'incsrc "Core/ram.asm"\n'
        "namespace Oracle\n"
        "{\n"
        'incsrc "Core/sram.asm"\n'
        'incsrc "Overworld/music_cache.asm"\n'
        "org $0BFE70\n"
        "Stub_SetFixedColorAndScroll:\n"
        "  INC.w $1FF0\n"
        "  RTL\n"
        "org $02AC29\n"
        "  RTL\n"  # Return right after INC.b $11 at $02AC27..$02AC28
        "org $34C000\n"
        'incsrc "Overworld/storm.asm"\n'
        "}\n"
        "namespace off\n",
        encoding="utf-8",
    )
    return _run_asar(asm_path, rom_path)


def _assemble_warp_and_kydrog_module(folder: Path) -> tuple[bytes, dict[str, int]]:
    """Compile real MirrorWarp_NoOverlayUploadTable, .noSubscreenOverlay from
    Overworld/ZSCustomOverworld.asm, and real Sprites/Bosses/kydrog.asm with
    !ENABLE_GLADE_AMBUSH = 1."""
    folder.mkdir(parents=True, exist_ok=True)
    rom_path = folder / "warp_kydrog.sfc"
    rom_path.write_bytes(b"\xFF" * 0x200000)

    zsow = (ROOT / "Overworld" / "ZSCustomOverworld.asm").read_text(encoding="utf-8")
    m_tbl = re.search(
        r"(MirrorWarp_NoOverlayUploadTable:\s*\{.*?\n\})",
        zsow,
        re.S,
    )
    assert m_tbl is not None, "MirrorWarp_NoOverlayUploadTable not found in ZSCustomOverworld.asm"
    m_no_ov = re.search(
        r"(^[ \t]*\.noSubscreenOverlay[ \t]*$.*?INC\.b \$11\s+RTS)",
        zsow,
        re.S | re.M,
    )
    assert m_no_ov is not None, ".noSubscreenOverlay not found in ZSCustomOverworld.asm"
    no_ov_body = m_no_ov.group(1).replace(".noSubscreenOverlay", "NoSubscreenOverlay_Body:", 1)

    asm_path = folder / "warp_kydrog_harness.asm"
    asm_path.write_text(
        "lorom\n"
        'incsrc "Util/macros.asm"\n'
        "!ENABLE_GLADE_AMBUSH = 1\n"
        'incsrc "Core/ram.asm"\n'
        "namespace Oracle\n"
        "{\n"
        'incsrc "Core/link.asm"\n'
        'incsrc "Core/sram.asm"\n'
        'incsrc "Core/symbols.asm"\n'
        "Sprite_KydrogNPC = $7B\n"
        "WALKSPEED = 14\n"
        "macro Set_Sprite_Properties(prep, main)\n"
        "endmacro\n"
        "macro GotoAction(action)\n"
        "  LDA.b #<action> : STA.w SprAction, X\n"
        "endmacro\n"
        "macro ShowUnconditionalMessage(msg)\n"
        "  LDA.b #(<msg>&$FF) : LDY.b #(<msg>>>8) : JSL Sprite_ShowMessageUnconditional\n"
        "endmacro\n"
        "org $008781 : RTL\n"  # JumpTableLocal
        "org $00E33A : RTL\n"  # KydrogAmbush_Bank00_RTL
        "org $00E583 : RTS\n"  # KydrogAmbush_LoadSprGfx
        "org $00FC41 : INC.w $1FF1 : RTL\n"  # Sprite_LoadGfxProperties
        "org $05E219 : RTL\n"  # Sprite_ShowMessageUnconditional
        "org $06E416 : RTL\n"  # Sprite_PrepOamCoord
        "org $06F864 : RTL\n"  # Sprite_OAM_AllocateDeferToPlayer
        "org $1DF65D : LDY.b #$01 : RTL\n"  # Sprite_SpawnDynamically
        "org $08B000\n"
        "Sprite_CheckActive: SEC : RTL\n"
        "org $289000\n"
        + m_tbl.group(1)
        + "\n"
        "Call_NoSubscreenOverlay:\n"
        "  REP #$30\n"
        "  JSR NoSubscreenOverlay_Body\n"
        "  RTL\n"
        + no_ov_body
        + "\n"
        "org $3BF000\n"
        'incsrc "Sprites/Bosses/kydrog.asm"\n'
        "Call_Kydrog_WarpPlayerAway:\n"
        "  PHB : PHK : PLB : JSR Kydrog_WarpPlayerAway : PLB : RTL\n"
        "Call_Kydrog_StartCutscene:\n"
        "  PHB : PHK : PLB : JSR Kydrog_StartCutscene : PLB : RTL\n"
        "Call_Kydrog_ArrivalPan:\n"
        "  PHB : PHK : PLB : JSR Kydrog_ArrivalPan : PLB : RTL\n"
        "}\n"
        "namespace off\n",
        encoding="utf-8",
    )
    return _run_asar(asm_path, rom_path)


class DreamAndWarpFixesTests(unittest.TestCase):
    """Compiled 65816 + structural verification for all 4 Q-OOS-13 technical bugs."""

    _temp_dir: tempfile.TemporaryDirectory[str]
    _lib: C.CDLL
    _dream_rom: bytes
    _dream_labels: dict[str, int]
    _storm_rom: bytes
    _storm_labels: dict[str, int]
    _warp_rom: bytes
    _warp_labels: dict[str, int]

    @classmethod
    def setUpClass(cls) -> None:
        cls._temp_dir = tempfile.TemporaryDirectory(prefix="oos-dream-warp-tests-")
        base = Path(cls._temp_dir.name)
        cls._lib = _build_cpu_lib(base)
        cls._dream_rom, cls._dream_labels = _assemble_dream_module(base / "dream")
        cls._storm_rom, cls._storm_labels = _assemble_storm_module(base / "storm")
        cls._warp_rom, cls._warp_labels = _assemble_warp_and_kydrog_module(base / "warp")

    @classmethod
    def tearDownClass(cls) -> None:
        cls._temp_dir.cleanup()

    # -----------------------------------------------------------------------
    # 1. DREAM-PAL: Green blanket & stale RestoreAdditive palette wrap
    # -----------------------------------------------------------------------

    def test_dream_pal_sleep_sets_bed_greys_and_skips_palette_filter(self) -> None:
        trap_filter = self._dream_labels["Trap_PaletteFilter_StartBlindingWhite"]
        blanket_stub = self._dream_labels["AncillaAdd_Blanket"]
        fx = TraceFixture(
            self._lib,
            self._dream_rom,
            self._dream_labels,
            stubs={
                trap_filter: ("PaletteFilter_StartBlindingWhite", lambda f: None),
                blanket_stub: ("AncillaAdd_Blanket", lambda f: setattr(f.cpu, "x", 0)),
            },
        )
        try:
            # Seed Maple's hut OBJ pal 6: white $7FFF at +$02, green $036F/$026B at +$0C/$0E,
            # and stale $7EC009 = $02 (RestoreAdditive from Module06).
            fx.ram[0x0C009] = 0x02
            fx.write_w(0x7EC6C2, 0x7FFF)
            fx.write_w(0x7EC4C2, 0x7FFF)
            fx.write_w(0x7EC6CC, 0x036F)
            fx.write_w(0x7EC6CE, 0x026B)
            fx.write_w(0x7EC4CC, 0x036F)
            fx.write_w(0x7EC4CE, 0x026B)
            fx.write_w(0x20, 0x0154)
            fx.write_w(0x22, 0x1F60)
            fx.ram[0x15] = 0x00

            fx.call_jsl(self._dream_labels["Call_Sprite_PutLinkToSleep"], x=3, db=0x30)

            call_names = [c[0] for c in fx.calls]
            self.assertNotIn("PaletteFilter_StartBlindingWhite", call_names)
            self.assertIn("AncillaAdd_Blanket", call_names)

            # Bed sheet greys written to BOTH live and backup OBJ palette 6 colors 6-7
            self.assertEqual(fx.read_w(0x7EC6CC), 0x739C)
            self.assertEqual(fx.read_w(0x7EC6CE), 0x56B5)
            self.assertEqual(fx.read_w(0x7EC4CC), 0x739C)
            self.assertEqual(fx.read_w(0x7EC4CE), 0x56B5)
            # White color 1 untouched (no RestoreAdditive $7FFF -> $0420 wrap)
            self.assertEqual(fx.read_w(0x7EC6C2), 0x7FFF)
            self.assertEqual(fx.read_w(0x7EC4C2), 0x7FFF)
            self.assertEqual(fx.ram[0x15], 0x01)
            # Link sleeping in bed with blanket aligned to Link
            self.assertEqual(fx.ram[0x5D], 0x16)
            self.assertEqual(fx.read_w(0x20), 0x0140)
            self.assertEqual(fx.read_w(0x22), 0x1F78)
            self.assertEqual(fx.ram[0x0BFA], 0x44)
            self.assertEqual(fx.ram[0x0C04], 0x70)
        finally:
            fx.close()

    def test_dream_pal_wake_tuck_into_bed_sets_bed_greys(self) -> None:
        blanket_stub = self._dream_labels["AncillaAdd_Blanket"]
        fx = TraceFixture(
            self._lib,
            self._dream_rom,
            self._dream_labels,
            stubs={
                blanket_stub: ("AncillaAdd_Blanket", lambda f: setattr(f.cpu, "x", 0)),
            },
        )
        try:
            # Hut reload after finished Wisdom/Power dream scene
            fx.write_w(0x7EC6CC, 0x036F)
            fx.write_w(0x7EC6CE, 0x026B)
            fx.write_w(0x7EC4CC, 0x036F)
            fx.write_w(0x7EC4CE, 0x026B)
            fx.ram[0x10] = 0x06  # Module06 hut reload
            fx.ram[0x4B] = 0x0C
            fx.ram[0x02E4] = 0x01
            fx.ram[0x0FFC] = 0x01
            fx.ram[0x037B] = 0x01
            fx.ram[0x02F9] = 0x01
            fx.write_w(0x7FF370, 0xD1A5)  # DreamWisdom_Marker = !DW_Live
            fx.write_w(0x7FF37A, 0xD2A6)  # DreamPower_WakeLine = !DreamPower_WakeLive

            fx.call_jsl(self._dream_labels["DreamWisdom_Stage"], db=0x09)

            self.assertEqual(fx.ram[0x4B], 0x00)
            self.assertEqual(fx.ram[0x02E4], 0x00)
            self.assertEqual(fx.ram[0x0FFC], 0x00)
            self.assertEqual(fx.ram[0x037B], 0x00)
            self.assertEqual(fx.ram[0x02F9], 0x00)
            self.assertEqual(fx.read_w(0x7FF370), 0x0000)
            self.assertEqual(fx.ram[0x5D], 0x16)
            self.assertEqual(fx.read_w(0x22), 0x1F78)
            self.assertEqual(fx.read_w(0x20), 0x0140)
            self.assertEqual(fx.read_w(0x0FC2), 0x1F78)
            self.assertEqual(fx.read_w(0x0FC4), 0x0140)
            self.assertEqual(fx.read_w(0x7EC6CC), 0x739C)
            self.assertEqual(fx.read_w(0x7EC6CE), 0x56B5)
            self.assertEqual(fx.read_w(0x7EC4CC), 0x739C)
            self.assertEqual(fx.read_w(0x7EC4CE), 0x56B5)
            self.assertEqual(fx.ram[0x15], 0x01)
        finally:
            fx.close()

    # -----------------------------------------------------------------------
    # 2. DREAM-LINK: Hide during warp fade-out, restore on dream room load
    # -----------------------------------------------------------------------

    def test_dream_link_hidden_during_warp_for_all_three_dreams(self) -> None:
        expected = [
            (0, 0x51, 0x38, 0x70),  # Wisdom
            (1, 0x00, 0x48, 0x44),  # Power
            (2, 0x31, 0x78, 0x70),  # Courage
        ]
        for dream_idx, room, x_lo, y_lo in expected:
            fx = TraceFixture(self._lib, self._dream_rom, self._dream_labels)
            try:
                fx.ram[0x4B] = 0x00
                fx.write_w(0x010E, 0x0068)  # Dream Hut entrance
                fx.ram[0xA0] = 0x0F
                fx.call_jsl(self._dream_labels["Call_Link_WarpToRoom"], x=dream_idx, db=0x30)

                self.assertEqual(fx.ram[0x4B], 0x0C, f"dream {dream_idx} must hide Link during fade")
                self.assertEqual(fx.ram[0x11], 0x15)
                self.assertEqual(fx.ram[0x5D], 0x01)
                self.assertEqual(fx.ram[0x5C], 0x20)
                self.assertEqual(fx.ram[0xA0], room)
                self.assertEqual(fx.ram[0xA1], 0x00)
                self.assertEqual(fx.ram[0x22], x_lo)
                self.assertEqual(fx.ram[0x20], y_lo)
                self.assertEqual(fx.ram[0x0427], 120)

                # DreamReturn_IsDreaming must report Carry set
                fx.call_jsl(self._dream_labels["DreamReturn_IsDreaming"])
                self.assertTrue(fx.cpu.c)
            finally:
                fx.close()

    def test_dream_link_part00_room_sprites_visibility_by_dream(self) -> None:
        # Courage (CurrentDream=2, room $31): Part00_RoomSprites unhides Link ($4B=0)
        fx = TraceFixture(self._lib, self._dream_rom, self._dream_labels)
        try:
            fx.ram[0x10] = 0x07
            fx.ram[0x11] = 0x15
            fx.ram[0x4B] = 0x0C
            fx.ram[0x0426] = 0x02  # Courage
            fx.ram[0x0427] = 120
            fx.write_w(0x010E, 0x0068)
            fx.write_w(0x048E, 0x0031)
            fx.put(0x7EF3C5, 0x02)  # GameState != 0 (skip Part00 villager)
            fx.call_jsl(self._dream_labels["Call_Part00_RoomSprites"], db=0x09)
            self.assertEqual(fx.ram[0x4B], 0x00)
            self.assertEqual(fx.ram[0x1FF5], 0x00)
        finally:
            fx.close()

        # Wisdom (CurrentDream=0, room $51): Part00_RoomSprites unhides, DreamWisdom_Stage re-hides
        fx = TraceFixture(self._lib, self._dream_rom, self._dream_labels)
        try:
            fx.ram[0x10] = 0x07
            fx.ram[0x11] = 0x15
            fx.ram[0x4B] = 0x0C
            fx.ram[0x0426] = 0x00  # Wisdom
            fx.ram[0x0427] = 120
            fx.write_w(0x010E, 0x0068)
            fx.write_w(0x048E, 0x0051)
            fx.ram[0x02] = 0x00  # next free sprite slot
            fx.put(0x7EF3C5, 0x02)
            fx.call_jsl(self._dream_labels["Call_Part00_RoomSprites"], db=0x09)
            self.assertEqual(fx.ram[0x4B], 0x0C)
            self.assertEqual(fx.ram[0x02E4], 0x01)
            self.assertEqual(fx.ram[0x0FFC], 0x01)
            self.assertEqual(fx.read_w(0x7FF370), 0xD1A5)
            self.assertEqual(fx.ram[0x0DD0], 0x08)
            self.assertEqual(fx.ram[0x0DD1], 0x08)
            self.assertEqual(fx.ram[0x0E30], 0xD1)
            self.assertEqual(fx.ram[0x0E31], 0xD2)

            # DreamReturn_Begin releases control locks but keeps $4B=$0C through Module07_19
            fx.call_jsl(self._dream_labels["Call_DreamReturn_Begin"], db=0x30)
            self.assertEqual(fx.ram[0x4B], 0x0C)
            self.assertEqual(fx.ram[0x02E4], 0x00)
            self.assertEqual(fx.ram[0x0FFC], 0x00)
            self.assertEqual(fx.ram[0x11], 0x19)
            self.assertEqual(fx.read_w(0x010E), 0x0068)
            self.assertEqual(fx.get(0x7EF410) & 0x01, 0x01)
        finally:
            fx.close()

        # Power (CurrentDream=1, room $00): DreamRoom_Stage -> DreamPower_Stage re-hides Link
        fx = TraceFixture(self._lib, self._dream_rom, self._dream_labels)
        try:
            fx.ram[0x10] = 0x07
            fx.ram[0x11] = 0x15
            fx.ram[0x4B] = 0x0C
            fx.ram[0x0426] = 0x01  # Power
            fx.ram[0x0427] = 120
            fx.write_w(0x010E, 0x0068)
            fx.write_w(0x048E, 0x0000)
            fx.put(0x7EF3C5, 0x02)
            fx.call_jsl(self._dream_labels["Call_Part00_RoomSprites"], db=0x09)
            self.assertEqual(fx.ram[0x4B], 0x0C)
            self.assertEqual(fx.read_w(0x7FF370), 0xD1A5)
            self.assertEqual(fx.read_w(0xE2), 0x0100)
            self.assertEqual(fx.read_w(0xE8), 0x0010)
            self.assertEqual(fx.ram[0x0E30], 0xD3)
            self.assertEqual(fx.ram[0x0E31], 0xD4)
        finally:
            fx.close()

    # -----------------------------------------------------------------------
    # 3. Part 0 storm bit decoupling (Overworld/storm.asm)
    # -----------------------------------------------------------------------

    def test_part0_storm_strictly_kalyxo_lw_and_decoupled_from_gamestate(self) -> None:
        entry = self._storm_labels["Part0Storm_CarryClearIfStorm"]
        fx = TraceFixture(self._lib, self._storm_rom, self._storm_labels)
        try:
            # Storm active on Kalyxo LW ($00-$3F) regardless of GameState (0..3)
            for gs in (0, 1, 2, 3):
                for area in (0x00, 0x13, 0x23, 0x2A, 0x33, 0x3F):
                    fx.put(0x7EF3C5, gs)
                    fx.put(0x7EF3C6, 0x90)  # LegacyHouseFlag | Part0Storm
                    fx.put(0x7EF3CA, 0x00)
                    fx.ram[0x8A] = area
                    fx.call_jsl(entry, x=0x1234, m16=True, x16=True)
                    self.assertFalse(fx.cpu.c, f"storm must be ON for LW ${area:02X}, GS={gs}")
                    self.assertEqual(fx.cpu.x, 0x1234)
                    self.assertFalse(fx.cpu.mf)
                    self.assertFalse(fx.cpu.xf)

            # Storm OFF in Eon Abyss ($40-$7F) AND Special Overworld ($80-$BF)
            for area in (0x40, 0x5B, 0x7F, 0x80, 0x81, 0x84, 0x87, 0x8C, 0x90, 0xA0, 0xB0, 0xBF):
                fx.put(0x7EF3C5, 0x00)
                fx.put(0x7EF3C6, 0x90)
                fx.put(0x7EF3CA, 0x40 if area < 0x80 else 0x00)
                fx.ram[0x8A] = area
                fx.call_jsl(entry, x=0x00AB, m16=False, x16=False)
                self.assertTrue(fx.cpu.c, f"storm must be OFF for area ${area:02X}")
                self.assertEqual(fx.cpu.x & 0xFF, 0xAB)
                self.assertTrue(fx.cpu.mf)
                self.assertTrue(fx.cpu.xf)

            # Storm bit clear -> storm OFF even on Kalyxo LW with GameState=0
            fx.put(0x7EF3C5, 0x00)
            fx.put(0x7EF3C6, 0x10)  # LegacyHouseFlag only, NO Part0Storm
            fx.put(0x7EF3CA, 0x00)
            fx.ram[0x8A] = 0x23
            fx.call_jsl(entry)
            self.assertTrue(fx.cpu.c)
        finally:
            fx.close()

    def test_part0_storm_scroll_skip_hook_02ac12_decoupled_from_gamestate(self) -> None:
        fx = TraceFixture(self._lib, self._storm_rom, self._storm_labels)
        try:
            # Case A: Post-Farore (GameState=2) with Part0Storm still set on Kalyxo LW -> skips $0BFE70
            fx.ram[0x1FF0] = 0
            fx.ram[0x11] = 0x04
            fx.ram[0x8A] = 0x2A
            fx.put(0x7EF3C5, 0x02)
            fx.put(0x7EF3C6, 0x90)
            fx.put(0x7EF3CA, 0x00)
            fx.call_jsl(0x02AC12)
            self.assertEqual(fx.ram[0x1FF0], 0, "active storm must skip $0BFE70 even at GameState=2")
            self.assertEqual(fx.ram[0x11], 0x05)

            # Case B: GameState=0 without storm bit -> MUST run $0BFE70
            fx.ram[0x1FF0] = 0
            fx.ram[0x11] = 0x04
            fx.ram[0x8A] = 0x2A
            fx.put(0x7EF3C5, 0x00)
            fx.put(0x7EF3C6, 0x10)
            fx.put(0x7EF3CA, 0x00)
            fx.call_jsl(0x02AC12)
            self.assertEqual(fx.ram[0x1FF0], 1, "clear storm bit must run $0BFE70 even at GameState=0")
            self.assertEqual(fx.ram[0x11], 0x05)

            # Case C: Active storm bit in Abyss ($40) or Special OW ($84/$A0) -> MUST run $0BFE70
            for area in (0x40, 0x84, 0xA0):
                fx.ram[0x1FF0] = 0
                fx.ram[0x11] = 0x04
                fx.ram[0x8A] = area
                fx.put(0x7EF3C5, 0x00)
                fx.put(0x7EF3C6, 0x90)
                fx.put(0x7EF3CA, 0x40 if area < 0x80 else 0x00)
                fx.call_jsl(0x02AC12)
                self.assertEqual(fx.ram[0x1FF0], 1, f"non-LW area ${area:02X} must run $0BFE70")
        finally:
            fx.close()

    def test_part0_storm_clears_on_kalyxo_return_and_adjust_ambience(self) -> None:
        carry_fn = self._storm_labels["Part0Storm_CarryClearIfStorm"]
        amb_fn = self._storm_labels["Part0Storm_AdjustAmbience"]
        fx = TraceFixture(self._lib, self._storm_rom, self._storm_labels)
        try:
            # 1. Active storm: AdjustAmbience stamps $1x onto LW $00-$3F only
            for i in range(0xA0):
                fx.put(0x7EC900 + i, 0x50 | (i & 0x0F))
            fx.ram[0x00] = 0x52
            fx.put(0x7EF3C6, 0x90)  # Part0Storm ON, KydrogEncounter OFF
            fx.put(0x7EF3CA, 0x00)
            fx.call_jsl(amb_fn, m16=False, x16=True)
            for i in range(0x40):
                self.assertEqual(fx.get(0x7EC900 + i), 0x10 | (i & 0x0F))
            for i in range(0x40, 0xA0):
                expected = 0x52 if i == 0x80 else (0x50 | (i & 0x0F))
                self.assertEqual(fx.get(0x7EC900 + i), expected)

            # 2. In Abyss after Kydrog ($7EF3CA=$40): storm bit stays set, returns C=1
            fx.put(0x7EF3C6, 0x94)  # LegacyHouse | KydrogEncounter | Part0Storm
            fx.put(0x7EF3CA, 0x40)
            fx.ram[0x8A] = 0x40
            fx.call_jsl(carry_fn)
            self.assertTrue(fx.cpu.c)
            self.assertEqual(fx.get(0x7EF3C6), 0x94)

            # 3. Return to Kalyxo ($7EF3CA=$00): clears ONLY bit 7 and strips $10 from LW cache
            fx.put(0x7EC900 + 0x13, 0x53)  # non-rain $5x must be preserved
            fx.put(0x7EF3CA, 0x00)
            fx.ram[0x8A] = 0x2A
            fx.call_jsl(carry_fn)
            self.assertTrue(fx.cpu.c)
            self.assertEqual(fx.get(0x7EF3C6), 0x14)  # bit 7 cleared; bits 4 & 2 preserved
            self.assertEqual(fx.get(0x7EC900 + 0x2A), 0x0A)  # $1A -> $0A
            self.assertEqual(fx.get(0x7EC900 + 0x13), 0x53)  # $53 preserved
        finally:
            fx.close()

    # -----------------------------------------------------------------------
    # 4. Post-Kydrog DW pyramid warp GFX & Glade ambush Abyss landing
    # -----------------------------------------------------------------------

    def test_mirror_warp_no_overlay_upload_table_guards_bg3(self) -> None:
        fn = self._warp_labels["MirrorWarp_NoOverlayUploadTable"]
        fx = TraceFixture(self._lib, self._warp_rom, self._warp_labels)
        try:
            # Seed $7F4000-$7F407F with dangerous BG3 tilemap ($6000) / CHR ($7000) targets
            for i in range(64):
                fx.write_w(0x7F4000 + i * 2, 0x6000 + i * 0x40)

            # With $8C == $FF (area $40 no overlay): all 64 words repoint to unused BG1 $1000..$1FC0
            fx.ram[0x8C] = 0xFF
            fx.call_jsl(fn, m16=False, x16=False)
            self.assertTrue(fx.cpu.mf)
            self.assertTrue(fx.cpu.xf)
            for i in range(64):
                self.assertEqual(fx.read_w(0x7F4000 + i * 2), 0x1000 + i * 0x40)

            # With a real overlay ($8C == $9F): table must NOT be overwritten
            for i in range(64):
                fx.write_w(0x7F4000 + i * 2, 0x2000 + i * 0x20)
            fx.ram[0x8C] = 0x9F
            fx.call_jsl(fn, m16=True, x16=True)
            self.assertFalse(fx.cpu.mf)
            self.assertFalse(fx.cpu.xf)
            for i in range(64):
                self.assertEqual(fx.read_w(0x7F4000 + i * 2), 0x2000 + i * 0x20)
        finally:
            fx.close()

    def test_no_subscreen_overlay_clears_stale_file_select_and_dungeon_layers(self) -> None:
        fn = self._warp_labels["Call_NoSubscreenOverlay"]
        for stale_1c, stale_1d, stale_9a in ((0x15, 0x01, 0x72), (0x17, 0x01, 0x20)):
            fx = TraceFixture(self._lib, self._warp_rom, self._warp_labels)
            try:
                fx.ram[0x1C] = stale_1c
                fx.ram[0x1D] = stale_1d
                fx.ram[0x9A] = stale_9a
                fx.ram[0x8C] = 0x97
                fx.ram[0x11] = 0x17
                fx.call_jsl(fn)
                self.assertEqual(fx.ram[0x8C], 0xFF)
                self.assertEqual(fx.ram[0x1C], 0x16)  # OBJ + BG2 + BG3 (BG1 off)
                self.assertEqual(fx.ram[0x1D], 0x00)
                self.assertEqual(fx.ram[0x9A], 0x00)
                self.assertEqual(fx.ram[0x11], 0x18)
            finally:
                fx.close()

    def test_kydrog_warp_and_abyss_landing_pan_menu_lock_and_mosaic_guard(self) -> None:
        warp_fn = self._warp_labels["Call_Kydrog_WarpPlayerAway"]
        tick_fn = self._warp_labels["KydrogLanding_Tick"]
        fx = TraceFixture(self._lib, self._warp_rom, self._warp_labels)
        try:
            # 1. Kydrog_WarpPlayerAway arms AbyssLanding=1 and transitions to Module $15 -> DW $20
            fx.put(0x7EF3CA, 0x00)
            fx.put(0x7EF3CC, 0x01)
            fx.put(0x7EF3C6, 0x90)
            fx.call_jsl(warp_fn, db=0x3B)
            self.assertEqual(fx.ram[0x02B8], 0x01)  # AbyssLanding armed
            self.assertEqual(fx.get(0x7EF3CA), 0x40)
            self.assertEqual(fx.ram[0x10], 0x15)
            self.assertEqual(fx.ram[0xA0], 0x20)
            self.assertEqual(fx.get(0x7EF3CC), 0x00)
            self.assertEqual(fx.get(0x7EF300), 0x01)
            self.assertEqual(fx.get(0x7EF3C6), 0x94)  # Story2_KydrogEncounter set, storm bit kept

            # 2. Module $15 ticks do nothing until Module $09 gameplay on area $40
            fx.ram[0x8A] = 0x40
            fx.call_jsl(tick_fn)
            self.assertEqual(fx.ram[0x02B8], 0x01)

            # 3. Enter Module $09 on area $40 -> state 1->2 locks $0FFC, hides Link, sets mosaic & camera
            fx.ram[0x10] = 0x09
            fx.ram[0x11] = 0x00
            fx.call_jsl(tick_fn)
            self.assertEqual(fx.ram[0x02B8], 0x02)
            self.assertEqual(fx.ram[0x02B9], 0xE0)
            self.assertEqual(fx.read_w(0x011C), 0xFF20)
            self.assertEqual(fx.ram[0x02E4], 0x01)
            self.assertEqual(fx.ram[0x0FFC], 0x01, "menu/map must be locked during landing pan")
            self.assertEqual(fx.ram[0x4B], 0x0C)
            self.assertEqual(fx.ram[0x95], 0xF3)

            # 4. Run mosaic clear (state 2 -> 3)
            for frame in range(100):
                fx.ram[0x1A] = frame & 0xFF
                fx.call_jsl(tick_fn)
                if fx.ram[0x02B8] == 0x03:
                    break
            self.assertEqual(fx.ram[0x02B8], 0x03)
            self.assertEqual(fx.ram[0x95], 0x00)
            self.assertEqual(fx.ram[0x0FFC], 0x01)

            # 5. Pan $E0 frames + completion tick restores everything cleanly
            for _ in range(0xE0):
                fx.call_jsl(tick_fn)
            self.assertEqual(fx.read_w(0x011C), 0x0000)
            self.assertEqual(fx.ram[0x02B9], 0x00)
            self.assertEqual(fx.ram[0x02B8], 0x03)

            fx.call_jsl(tick_fn)  # .done
            self.assertEqual(fx.ram[0x02B8], 0x00)
            self.assertEqual(fx.ram[0x4B], 0x00)
            self.assertEqual(fx.ram[0x95], 0x00)
            self.assertEqual(fx.ram[0x02E4], 0x00)
            self.assertEqual(fx.ram[0x0FFC], 0x00)
            self.assertEqual(fx.read_w(0x011C), 0x0000)

            # 6. Mosaic underflow guard: $95 == $00 or $03 in state 2 must NOT wrap to $F0
            for low_mosaic in (0x00, 0x03, 0x0F):
                fx.ram[0x02B8] = 0x02
                fx.ram[0x95] = low_mosaic
                fx.ram[0x1A] = 0x00
                fx.call_jsl(tick_fn)
                self.assertEqual(fx.ram[0x95], 0x00, f"$95={low_mosaic:#x} wrapped instead of clearing")
                self.assertEqual(fx.ram[0x02B8], 0x03)
        finally:
            fx.close()

    def test_kydrog_landing_tick_abort_restores_active_pan_state(self) -> None:
        tick_fn = self._warp_labels["KydrogLanding_Tick"]
        fx = TraceFixture(self._lib, self._warp_rom, self._warp_labels)
        try:
            # State 1 aborted off area $40: disarms without clobbering untouched state
            fx.ram[0x10] = 0x09
            fx.ram[0x8A] = 0x50
            fx.ram[0x02B8] = 0x01
            fx.ram[0x4B] = 0x05
            fx.call_jsl(tick_fn)
            self.assertEqual(fx.ram[0x02B8], 0x00)
            self.assertEqual(fx.ram[0x4B], 0x05)

            # State 2/3 aborted off area $40: MUST clean up $4B/$95/$02E4/$0FFC/$011C
            for state in (0x02, 0x03):
                fx.ram[0x10] = 0x09
                fx.ram[0x8A] = 0x50
                fx.ram[0x02B8] = state
                fx.ram[0x4B] = 0x0C
                fx.ram[0x95] = 0x83
                fx.ram[0x02E4] = 0x01
                fx.ram[0x0FFC] = 0x01
                fx.write_w(0x011C, 0xFF80)
                fx.call_jsl(tick_fn)
                self.assertEqual(fx.ram[0x02B8], 0x00)
                self.assertEqual(fx.ram[0x4B], 0x00)
                self.assertEqual(fx.ram[0x95], 0x00)
                self.assertEqual(fx.ram[0x02E4], 0x00)
                self.assertEqual(fx.ram[0x0FFC], 0x00)
                self.assertEqual(fx.read_w(0x011C), 0x0000)
        finally:
            fx.close()

    def test_kydrog_glade_arrival_pan_locks_and_releases_nomenu(self) -> None:
        start_fn = self._warp_labels["Call_Kydrog_StartCutscene"]
        pan_fn = self._warp_labels["Call_Kydrog_ArrivalPan"]
        fx = TraceFixture(self._lib, self._warp_rom, self._warp_labels)
        try:
            slot = 2
            fx.ram[0x0EB0 + slot] = 0x00  # SprMiscE = 0 (arrival pan not shown yet)
            fx.ram[0x0FFC] = 0x00
            fx.ram[0x02E4] = 0x00
            fx.call_jsl(start_fn, x=slot, db=0x3B)
            self.assertEqual(fx.ram[0x0EB0 + slot], 0x01)
            self.assertEqual(fx.ram[0x02E4], 0x01)
            self.assertEqual(fx.ram[0x0FFC], 0x01, "arrival pan must lock $0FFC")
            self.assertEqual(fx.ram[0x0D80 + slot], 0x08)

            # Finish arrival pan (SprMiscD = 0): must clear $4B, $02E4, $0FFC, $011C/$011D
            fx.ram[0x0E90 + slot] = 0x00  # SprMiscD = 0
            fx.ram[0x4B] = 0x0C
            fx.write_w(0x011C, 0xFF90)
            fx.call_jsl(pan_fn, x=slot, db=0x3B)
            self.assertEqual(fx.ram[0x4B], 0x00)
            self.assertEqual(fx.ram[0x02E4], 0x00)
            self.assertEqual(fx.ram[0x0FFC], 0x00)
            self.assertEqual(fx.read_w(0x011C), 0x0000)
            self.assertEqual(fx.ram[0x0D80 + slot], 0x00)
        finally:
            fx.close()

    def test_structural_contracts_for_patches_gbc_form_and_storm_hooks(self) -> None:
        patches = (ROOT / "Core" / "patches.asm").read_text(encoding="utf-8")
        self.assertIn("org $00EF80 : LDA.b $E2 : NOP", patches)

        gbc = (ROOT / "Masks" / "gbc_form.asm").read_text(encoding="utf-8")
        self.assertIn("MirrorWarp_PearllessArrival:", gbc)
        self.assertIn("org $07AB09 : JSL MirrorWarp_PearllessArrival", gbc)

        zsow = (ROOT / "Overworld" / "ZSCustomOverworld.asm").read_text(encoding="utf-8")
        self.assertIn("LDA.w #$0016 : STA.b $1C", zsow)
        self.assertIn("JSL.l MirrorWarp_NoOverlayUploadTable", zsow)

        storm = (ROOT / "Overworld" / "storm.asm").read_text(encoding="utf-8")
        self.assertIn("LDA.b $8A : CMP.b #$40 : BCS .no_storm", storm)
        self.assertIn("org $02AC12", storm)
        self.assertIn("org $02C4B6", storm)
        self.assertIn("org $0ABA04", storm)

        maple = (ROOT / "Sprites" / "NPCs" / "maple.asm").read_text(encoding="utf-8")
        self.assertNotIn("PaletteFilter_StartBlindingWhite", maple)
        self.assertNotIn("ApplyPaletteFilter", maple)
        self.assertIn("JSR Blanket_UseBedColors", maple)
        self.assertIn("LDA.b #$0C : STA.b $4B", maple)


if __name__ == "__main__":
    unittest.main()
