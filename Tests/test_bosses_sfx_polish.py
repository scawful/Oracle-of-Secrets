#!/usr/bin/env python3
"""Q333 compiled 65816 & contract tests for Bosses Polish (Manhandla, Twinrova,
Kydreeok), remaining Q330 Audit SFX Fixes, and Switch Hook HUD Icon.

Assembles the real ASM source files with asar into isolated synthetic LoROM
images and executes the compiled 65816 code on LakeSnes's C CPU core
(no shared Roms/, no .yazeproj/rom writes, no emulator process).
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

sys.path.insert(0, str(Path(__file__).resolve().parent))
from d4_compiled_fight_check import Cpu  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]


def find_lakesnes() -> Path | None:
    env = os.environ.get("OOS_LAKESNES")
    cands = [Path(env)] if env else []
    cands.extend([
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ])
    for cand in cands:
        if (cand / "snes" / "cpu.c").is_file():
            return cand
    return None


def find_asar() -> str | None:
    return shutil.which("asar") or shutil.which("z3asm")


_LAKESNES_LIB = None
_LAKESNES_TMP = None


def get_lakesnes_lib():
    global _LAKESNES_LIB, _LAKESNES_TMP
    if _LAKESNES_LIB is not None:
        return _LAKESNES_LIB
    src_root = find_lakesnes()
    if src_root is None:
        return None
    _LAKESNES_TMP = tempfile.TemporaryDirectory(prefix="oos-q333-lakesnes-")
    so_path = Path(_LAKESNES_TMP.name) / "libcpu.dylib"
    cmd = [
        "cc", "-shared", "-fPIC", "-O2",
        str(src_root / "snes" / "cpu.c"),
        str(src_root / "snes" / "statehandler.c"),
        "-o", str(so_path),
    ]
    subprocess.run(cmd, check=True)
    lib = C.CDLL(str(so_path))
    lib.cpu_init.argtypes = [C.c_void_p, C.c_void_p, C.c_void_p, C.c_void_p]
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_runOpcode.restype = C.c_int
    _LAKESNES_LIB = lib
    return lib


def parse_sym(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for line in sym_path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", line.strip())
        if m and ":" not in m.group(3):
            labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    return labels


def lorom_pc(addr: int) -> int:
    return ((addr >> 16) & 0x7F) * 0x8000 + (addr & 0x7FFF)


class CpuHarness:
    """Minimal LakeSnes 65816 execution harness for real compiled ASM routines."""

    def __init__(self, lib, rom: bytes, labels: dict[str, int], default_db: int = 0x30):
        self.lib = lib
        self.rom = bytearray(rom)
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.stubs: dict[int, str] = {}
        self.stub_handlers: dict[str, callable] = {}
        self.calls: list[tuple[str, int, int, int]] = []
        self.sfx1: list[int] = []
        self.sfx2: list[int] = []
        self.sfx3: list[int] = []

        self._read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self._write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self._idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self._read_cb, self._write_cb, self._idle_cb)
        self.cpu = self.p.contents
        self.reset_regs(db=default_db)

    def reset_regs(self, db: int = 0x30, mf: bool = True, xf: bool = True):
        for n in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped",
                  "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, n, False)
        self.cpu.mf = mf
        self.cpu.xf = xf
        self.cpu.dp = 0
        self.cpu.sp = 0x1FF
        self.cpu.a = 0
        self.cpu.x = 0
        self.cpu.y = 0
        self.cpu.db = db

    def addr(self, name: str) -> int:
        if name in self.labels:
            return self.labels[name]
        if f"Oracle_{name}" in self.labels:
            return self.labels[f"Oracle_{name}"]
        raise KeyError(f"Missing label: {name}")

    def add_stub(self, addr: int, name: str, handler=None):
        self.stubs[addr] = name
        if handler is not None:
            self.stub_handlers[name] = handler

    @staticmethod
    def ram_offset(a: int) -> int | None:
        bank = (a >> 16) & 0xFF
        lo = a & 0xFFFF
        if bank in (0x7E, 0x7F):
            return a - 0x7E0000
        if (bank & 0x7F) < 0x40 and lo < 0x2000:
            return lo
        return None

    def read(self, a: int) -> int:
        if a in self.stubs:
            return 0x6B  # RTL
        off = self.ram_offset(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = lorom_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def write(self, a: int, v: int):
        off = self.ram_offset(a)
        if off is not None:
            self.ram[off] = v & 0xFF
            if off == 0x012D:
                self.sfx1.append(v & 0xFF)
            elif off == 0x012E:
                self.sfx2.append(v & 0xFF)
            elif off == 0x012F:
                self.sfx3.append(v & 0xFF)

    def get(self, a: int) -> int:
        return self.read(a)

    def get16(self, a: int) -> int:
        return self.get(a) | (self.get(a + 1) << 8)

    def put(self, a: int, v: int):
        off = self.ram_offset(a)
        assert off is not None
        self.ram[off] = v & 0xFF

    def put16(self, a: int, v: int):
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def call_jsr(self, target: int, *, x: int = 0, y: int = 0, a: int = 0,
                 db: int | None = None, mf: bool = True, xf: bool = True,
                 max_steps: int = 5000):
        """Execute a same-bank JSR routine until it RTS's back to a sentinel."""
        sentinel_pc = 0x1FFE
        bank = (target >> 16) & 0xFF
        self.cpu.db = bank if db is None else db
        self.cpu.mf = mf
        self.cpu.xf = xf
        self.cpu.a = a & (0xFF if mf else 0xFFFF)
        self.cpu.x = x & (0xFF if xf else 0xFFFF)
        self.cpu.y = y & (0xFF if xf else 0xFFFF)
        # Push return address (sentinel_pc - 1) onto stack
        ret = sentinel_pc - 1
        self.cpu.sp = 0x01FF
        self.ram[0x01FF] = (ret >> 8) & 0xFF
        self.ram[0x01FE] = ret & 0xFF
        self.cpu.sp = 0x01FD
        self.cpu.k = bank
        self.cpu.pc = target & 0xFFFF
        return self._run_until(bank, sentinel_pc, max_steps)

    def call_jsl(self, target: int, *, x: int = 0, y: int = 0, a: int = 0,
                 db: int | None = None, mf: bool = True, xf: bool = True,
                 max_steps: int = 5000):
        """Execute a long JSL routine until it RTL's back to a sentinel."""
        sentinel_bank = 0x00
        sentinel_pc = 0x1FFE
        bank = (target >> 16) & 0xFF
        self.cpu.db = bank if db is None else db
        self.cpu.mf = mf
        self.cpu.xf = xf
        self.cpu.a = a & (0xFF if mf else 0xFFFF)
        self.cpu.x = x & (0xFF if xf else 0xFFFF)
        self.cpu.y = y & (0xFF if xf else 0xFFFF)
        ret = sentinel_pc - 1
        self.cpu.sp = 0x01FF
        self.ram[0x01FF] = sentinel_bank
        self.ram[0x01FE] = (ret >> 8) & 0xFF
        self.ram[0x01FD] = ret & 0xFF
        self.cpu.sp = 0x01FC
        self.cpu.k = bank
        self.cpu.pc = target & 0xFFFF
        return self._run_until(sentinel_bank, sentinel_pc, max_steps)

    def _run_until(self, stop_bank: int, stop_pc: int, max_steps: int) -> int:
        steps = 0
        while steps < max_steps:
            cur = (self.cpu.k << 16) | self.cpu.pc
            if self.cpu.k == stop_bank and self.cpu.pc == stop_pc:
                return steps
            if cur in self.stubs:
                name = self.stubs[cur]
                self.calls.append((name, self.cpu.a, self.cpu.x, self.cpu.y))
                if name in self.stub_handlers:
                    self.stub_handlers[name](self)
            self.lib.cpu_runOpcode(self.p)
            steps += 1
        raise AssertionError(f"Routine did not return within {max_steps} steps (stuck at {self.cpu.k:02X}:{self.cpu.pc:04X})")


def assemble_snippet(asm_source: str, extra_files: dict[str, bytes] | None = None) -> tuple[bytes, dict[str, int]]:
    asar = find_asar()
    assert asar, "asar binary required"
    with tempfile.TemporaryDirectory(prefix="oos-q333-asm-") as td:
        tmp = Path(td)
        if extra_files:
            for rel, content in extra_files.items():
                dest = tmp / rel
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_bytes(content)
        rom_path = tmp / "test.sfc"
        rom_path.write_bytes(b"\x00" * 0x300000)  # 3 MiB LoROM (covers up to bank $5F)
        src_path = tmp / "main.asm"
        src_path.write_text(asm_source, encoding="utf-8")
        sym_path = tmp / "test.sym"
        res = subprocess.run(
            [asar, "--no-title-check", "-I" + str(ROOT), "--symbols=wla",
             f"--symbols-path={sym_path}", str(src_path), str(rom_path)],
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            errors="replace",
        )
        if res.returncode != 0:
            raise AssertionError(f"asar failed:\nSTDOUT:\n{res.stdout}\nSTDERR:\n{res.stderr}")
        return rom_path.read_bytes(), parse_sym(sym_path)


# Real JumpTableLocal implementation (8-bit A index -> 16-bit RTS dispatch in caller bank)
JUMP_TABLE_LOCAL_ASM = """
org JumpTableLocal
  ; Exact 65816 JSL JumpTableLocal: reads 16-bit target at (caller_pc+1 + 2*A) in caller bank K
  REP #$30
  AND.w #$00FF : ASL A : TAY
  PLA : INC A : STA.b $00 ; caller PC + 1
  SEP #$20
  PLA : STA.b $02 : PHA   ; caller bank K (keep on stack for RTL)
  REP #$20
  LDA.b [$00], Y : DEC A : PHA ; RTL increments PC by 1!
  SEP #$30
  RTL
"""


# =====================================================================
# 1. Remaining Audit SFX Fixes + Binary Immutability Contract Tests
# =====================================================================
class Q333AuditSfxAndImmutabilityTest(unittest.TestCase):
    def test_gust_jar_sfx_fixed(self):
        txt = (ROOT / "Items/gust_jar.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$13 : STA.w $012E", txt, "Must not play Song of Healing on capture")
        self.assertNotIn("LDA.b #$2B : STA.w $012E", txt, "Must not play Low-Heart beep on portal warp")
        self.assertGreaterEqual(txt.count("LDA.b #$13 : STA.w $012F"), 2)
        self.assertGreaterEqual(txt.count("LDA.b #$30 : STA.w $012F"), 3)

    def test_goriya_boomerang_sfx_channel_fixed(self):
        txt = (ROOT / "Sprites/Enemies/goriya.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$09 : STA.w $012F", txt, "Must not play Enemy Death on boomerang throw")
        self.assertIn("LDA.b #$09 : STA.w $012E", txt)

    def test_d4_water_control_uses_water_rush_not_storms(self):
        txt = (ROOT / "Dungeons/d4_water_control.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$2F : STA.w $012E", txt, "SFX2.$2F is Song of Storms")
        self.assertIn("LDA.b #$38 : STA.w $012E", txt)

    def test_honeycomb_uses_bees_not_key_jingle(self):
        txt = (ROOT / "Items/all_items.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$2F : STA.w $012F", txt)
        self.assertIn("LDA.b #$2C : STA.w $012F", txt)

    def test_deku_stick_and_dungeon_web_sfx_fixed(self):
        stick = (ROOT / "Items/deku_stick.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$2D : STA.w $012F", stick, "Must not play Milestone fanfare on ignite")
        self.assertNotIn("LDA.b #$0A : STA.w $012E", stick, "Must not play Hookshot clink on wood swipe")
        self.assertNotIn("LDA.b #$3C : STA.w $012E", stick, "Must not play Error beep on extinguish")
        self.assertNotIn("LDA.b #$20 : STA.w $012E", stick, "Must not play Pit fall on stun")
        self.assertNotIn("LDA.b #$09 : STA.w $012E", stick, "Must not play Boomerang on wall tink")
        self.assertGreaterEqual(stick.count("LDA.b #$01 : STA.w $012E"), 2)  # swipe
        self.assertIn("LDA.b #$07 : STA.w $012E", stick)                    # extinguish
        self.assertGreaterEqual(stick.count("LDA.b #$2A : STA.w $012E"), 2)  # ignition
        self.assertIn("LDA.b #$08 : STA.w $012F", stick)                    # stun impact
        self.assertIn("LDA.b #$05 : STA.w $012E", stick)                    # wall clink

        web = (ROOT / "Sprites/Objects/dungeon_web.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$2D : STA.w $012F", web, "Must not play Milestone fanfare burning web")
        self.assertIn("LDA.b #$2A : STA.w $012E", web)

    def test_kydrog_no_looping_flute_boy(self):
        txt = (ROOT / "Sprites/Bosses/kydrog.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$0C : STA $012D", txt, "Must not trigger looping Flute Boy accomp")
        self.assertIn("LDA.b #$28 : STA.w $012F", txt)

    def test_song_teachers_play_correct_songs(self):
        wmg = (ROOT / "Sprites/NPCs/windmill_guy.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$13 : STA.w $0CF8", wmg)
        self.assertIn("LDA.b #$2F : STA.w $0CF8", wmg)  # Song of Storms (SFX2.$2F)

        rg = (ROOT / "Sprites/NPCs/ranch_girl.asm").read_text(encoding="utf-8")
        self.assertNotIn("LDA.b #$13 : STA.w $0CF8", rg)
        self.assertIn("LDA.b #$1B : STA.w $012D", rg)   # Epona's Song (SFX1.$1B, no pan bits!)

    def test_boss_binary_assets_untouched_and_kydreeok_crlf(self):
        # Verify git diff against master shows zero changes to manhandla.bin / twinrova.bin
        res = subprocess.run(
            ["git", "-C", str(ROOT), "diff", "--name-only", "master", "--",
             "Sprites/Bosses/manhandla.bin", "Sprites/Bosses/twinrova.bin"],
            capture_output=True, text=True, check=True,
        )
        self.assertEqual(res.stdout.strip(), "", "manhandla.bin and twinrova.bin must remain untouched")
        self.assertIn(b"\r\n", (ROOT / "Sprites/Bosses/kydreeok.asm").read_bytes())
        self.assertIn(b"\r\n", (ROOT / "Sprites/Bosses/kydreeok_head.asm").read_bytes())


# =====================================================================
# 2. Switch Hook HUD Icon Compiled 65816 Test (Menu/menu_hud.asm)
# =====================================================================
class Q333SwitchHookHudCompiledTest(unittest.TestCase):
    def setUp(self):
        self.lib = get_lakesnes_lib()
        if self.lib is None or find_asar() is None:
            self.skipTest("LakeSnes or asar unavailable")

    def test_hud_draw_item_switch_hook_vs_hookshot_vs_goldstar(self):
        hud_src = (ROOT / "Menu/menu_hud.asm").read_text(encoding="utf-8")
        # Strip base-ROM preimage assert and incbin tilemap so synthetic image assembles cleanly
        cleaned_lines = []
        for line in hud_src.splitlines():
            if "assert read1($008B82)" in line or "incbin tilemaps/hud.tilemap" in line:
                cleaned_lines.append("; stripped for isolated unit harness")
            else:
                cleaned_lines.append(line)
        harness = f"""
lorom
!DISABLE_ITEMS = 0
!ENABLE_GOLDSTAR_CELL = 1
!BOMBCHU_AMMO_MAX = 50
!CurrentMask = $02B2
GoldstarOrHookshot = $7EF342
CurrentSong = $030F
BombchuAmmo = $7EF375
HudCornerBuffer = $7EC84A
HUD_Update_Impl = $2B8000
HUD_Update_Impl_ignore_item = $2B8004
HUD_Update_Impl_ignore_health = $2B8008
HUD_CodexCells = $2B800C
HUD_NMIUpload = $2B8010
Ocarina_ValidSong_Long = $2B8014
DreamWisdom_HUDHidden = $2B8018
Menu_AddressIndex = $0DF000
{chr(10).join(cleaned_lines)}
"""
        rom, labels = assemble_snippet(harness)
        h = CpuHarness(self.lib, rom, labels, default_db=0x0D)
        draw_addr = h.addr("HUD_DrawItem")

        # Case 1: Switch Hook ($7EF342 == 2), slot $03, A == 0 -> $24F5, $34F6, $24C0, $24F5
        h.put(0x7EF342, 2)
        h.call_jsr(draw_addr, x=0x0003, a=0x0000, db=0x0D, mf=False, xf=False)
        self.assertEqual(
            [h.get16(0x7EC776), h.get16(0x7EC778), h.get16(0x7EC7B6), h.get16(0x7EC7B8)],
            [0x24F5, 0x34F6, 0x24C0, 0x24F5],
            "Switch Hook ($7EF342==2) must render gold-prong + red-grip tiles in HUD",
        )

        # Case 2: Regular Hookshot ($7EF342 == 1), slot $03, A == 0 -> $2CF5, $2CF6, $2CC0, $2CF5
        h.put(0x7EF342, 1)
        h.call_jsr(draw_addr, x=0x0003, a=0x0000, db=0x0D, mf=False, xf=False)
        self.assertEqual(
            [h.get16(0x7EC776), h.get16(0x7EC778), h.get16(0x7EC7B6), h.get16(0x7EC7B8)],
            [0x2CF5, 0x2CF6, 0x2CC0, 0x2CF5],
            "Regular Hookshot ($7EF342==1) must keep blue/white Hookshot HUD icon",
        )

        # Case 3: Goldstar cell ($1A routes to X=3, A=1) even when $7EF342 == 2 -> Ball & Chain
        h.put(0x7EF342, 2)
        h.call_jsr(draw_addr, x=0x0003, a=0x0001, db=0x0D, mf=False, xf=False)
        self.assertEqual(
            [h.get16(0x7EC776), h.get16(0x7EC778), h.get16(0x7EC7B6), h.get16(0x7EC7B8)],
            [0x2C17, 0x3531, 0x2D40, 0x3541],
            "Goldstar cell (X=3, A=1) must preserve Ball & Chain HUD icon",
        )


# =====================================================================
# 3. D1 Manhandla / Big Chuchu Compiled 65816 Tests
# =====================================================================
class Q333ManhandlaCompiledTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = get_lakesnes_lib()
        if cls.lib is None or find_asar() is None:
            return
        src = (ROOT / "Sprites/Bosses/manhandla.asm").read_text(encoding="utf-8")
        # Keep the real code; replace incbin manhandla.bin with 8KB dummy data for fast isolated assemble
        src = src.replace("incbin manhandla.bin", "fillbyte $00 : fill $2000")
        harness = f"""
lorom
incsrc "Util/macros.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"
{JUMP_TABLE_LOCAL_ASM}
org $06FFF8
  RTL
; Custom sprite helpers not in symbols.asm
Sprite_CheckActive = $318000
Sprite_Move = $318004
Sprite_DamageFlash_Long = $318008
Sprite_ApplySpeedTowardsPlayerXOrY = $31800C
MoveBody = $328004
BossDefeated_Remnant = $318010
NewMainSprFunction = $06FFF8
NewSprPrepFunction = $068EB9
org $308000
NewSprRoutinesLong:
  fill $300
NewSprPrepRoutinesLong:
  fill $300
org $309000
{src}
"""
        cls.rom, cls.labels = assemble_snippet(harness)

    def _make_harness(self) -> CpuHarness:
        if self.lib is None or find_asar() is None:
            self.skipTest("LakeSnes or asar unavailable")
        h = CpuHarness(self.lib, self.rom, self.labels, default_db=0x30)
        self.spawned_slots: list[int] = []
        self.next_slot = 15

        def stub_active(fx):
            fx.cpu.c = True

        def stub_sfx2(fx):
            fx.sfx2.append(fx.cpu.a & 0xFF)

        def stub_sfx3(fx):
            fx.sfx3.append(fx.cpu.a & 0xFF)

        def stub_spawn(fx):
            slot = self.next_slot
            self.next_slot -= 1
            fx.put(0x0DD0 + slot, 9)
            fx.put(0x0E20 + slot, fx.cpu.a & 0xFF)
            fx.cpu.y = slot
            fx.cpu.n = False
            self.spawned_slots.append(slot)

        def stub_project(fx):
            # Aim straight right-down (+20, +16)
            fx.put(0x00, 16)  # vy
            fx.put(0x01, 20)  # vx

        def stub_apply(fx):
            spd = fx.cpu.a & 0xFF
            fx.put(0x0D50 + fx.cpu.x, spd)
            fx.put(0x0D40 + fx.cpu.x, spd)

        def stub_tile_col(fx):
            fx.cpu.a = 0
            fx.cpu.z = True

        for name, fn in (
            ("Sprite_CheckActive", stub_active),
            ("Sprite_Move", None),
            ("Sprite_DamageFlash_Long", None),
            ("Sprite_CheckDamageFromPlayer", None),
            ("Sprite_CheckDamageToPlayerSameLayer", None),
            ("Sprite_SpawnDynamically", stub_spawn),
            ("Sprite_PrepOamCoord", None),
            ("Sprite_OAM_AllocateDeferToPlayer", None),
            ("Sprite_KillFriends", None),
            ("Sprite_CheckTileCollision", stub_tile_col),
            ("Sprite_ApplySpeedTowardsPlayer", stub_apply),
            ("Sprite_ApplySpeedTowardsPlayerXOrY", stub_apply),
            ("Sprite_ProjectSpeedTowardsPlayer", stub_project),
            ("Sprite_IsBelowPlayer", None),
            ("Sprite_SetSpawnedCoordinates", None),
            ("GetRandomInt", None),
            ("Sound_SetSfx2PanLong", stub_sfx2),
            ("Sound_SetSfx3PanLong", stub_sfx3),
            ("MoveBody", None),
            ("BossDefeated_Remnant", None),
        ):
            h.add_stub(h.addr(name), name, fn)
        h.add_stub(0x0DBB8A, "SpriteSFX_QueueSFX3WithPan", stub_sfx3)
        return h

    def test_transformation_emerge_flicker_smooth_bloom_no_oob(self):
        h = self._make_harness()
        # Body in slot 0, Phase 0 with all 3 heads dead -> CheckForNextPhaseOrDeath triggers Action 7
        h.put(0x0DD0, 9)      # SprState = active
        h.put(0x0E30, 0)      # SprSubtype = 0 (body)
        h.put(0x0E90, 0)      # SprMiscD = 0
        h.put(0x0E50, 0x80)   # HP
        h.put(0x0D80, 6)      # Manhandla_Body
        h.put(h.addr("Offspring1_Id"), 13)  # Dead head slots (SprState == 0)
        h.put(h.addr("Offspring2_Id"), 14)
        h.put(h.addr("Offspring3_Id"), 15)
        h.put16(0x0FD8, 0x1580)  # SprCachedX
        h.put16(0x0FDA, 0x0B70)  # SprCachedY
        h.put(0x1C, 0x01)     # BG2 enabled

        # Trigger Phase 0 -> Phase 1 (BigChuchu_Emerge)
        h.call_jsr(h.addr("Sprite_Manhandla_CheckForNextPhaseOrDeath"), x=0)
        self.assertEqual(h.get(0x0E90), 1, "SprMiscD must become 1 on Emerge")
        self.assertEqual(h.get(0x0D80), 7, "SprAction must become 7 (BigChuchu_Emerge)")
        self.assertEqual(h.get(0x0DF0), 0x40, "SprTimerA must be $40")

        # Run all 64 frames of BigChuchu_Emerge -> must transition to Flower_Flicker keeping SprMiscD==1!
        seen_emerge_frames = []
        for frame in range(0x40):
            h.put(0x1A, frame)
            h.put(0x0DF0, 0x3F - frame)  # Engine decrements SprTimerA before Main
            h.call_jsr(h.addr("Sprite_Manhandla_Main"), x=0)
            if h.get(0x0D80) == 7:
                seen_emerge_frames.append(h.get(0x0D90))
                self.assertEqual(h.get(0x0E60) & 0x40, 0x40, "Must be invulnerable during Emerge")
        self.assertIn(9, seen_emerge_frames)
        self.assertIn(10, seen_emerge_frames)
        self.assertIn(11, seen_emerge_frames)
        self.assertEqual(h.get(0x0D80), 5, "Must transition to Action 5 (Flower_Flicker)")
        self.assertEqual(h.get(0x0E90), 1, "SprMiscD must STAY 1 during Flower_Flicker (no BigChuchu OOB!)")
        self.assertIn(0x35, h.sfx2)  # Shaking start
        self.assertIn(0x2A, h.sfx3)  # Swell cue
        self.assertIn(0x30, h.sfx3)  # Petal crack
        self.assertIn(0x0C, h.sfx2)  # Pod burst

        # Run all 36 frames of Flower_Flicker -> must transition cleanly into BigChuchu_Main!
        for frame in range(0x24):
            h.put(0x1A, frame)
            h.put(0x0DF0, 0x23 - frame)
            if h.get(0x0E00) > 0:
                h.put(0x0E00, h.get(0x0E00) - 1)
            h.call_jsr(h.addr("Sprite_Manhandla_Main"), x=0)
            if h.get(0x0D80) == 5:
                self.assertEqual(h.get(0x0E90), 1, "SprMiscD stays 1 throughout Flower_Flicker")
                self.assertIn(h.get(0x0D90), (11, 12), "Flower_Flicker frame must stay 11..12")

        self.assertEqual(h.get(0x0D80), 4, "Must reach Action 4 (BigChuchu_Main)")
        self.assertEqual(h.get(0x0E90), 2, "SprMiscD becomes 2 ONLY on BigChuchu reveal")
        self.assertEqual(h.get(0x0D90), 0, "SprFrame snapped cleanly to 0 for BigChuchu")
        self.assertEqual(h.get(0x0E60) & 0x40, 0, "Invulnerability cleared on reveal")
        self.assertEqual(h.get16(0x011A), 0, "Quake X cleared")
        self.assertEqual(h.get16(0x011C), 0, "Quake Y cleared")
        self.assertIn(0x32, h.sfx3, "Elastic BOING reveal SFX must play")
        # Crown flower spawned at CachedY + $10 (NOT +$20) with TimerC = $10 for seamless 16px rise
        flower_slot = h.get(h.addr("Offspring3_Id"))
        self.assertEqual(h.get(0x0E30 + flower_slot), 8)
        self.assertEqual(h.get(0x0D00 + flower_slot), (0x70 + 0x10) & 0xFF)
        self.assertEqual(h.get(0x0E10 + flower_slot), 0x10)

    def test_bounds_left_right_bounce_signs_fixed(self):
        h = self._make_harness()
        # Left OOB moving left (-12) -> must bounce RIGHT (+8)!
        h.put16(0x0FD8, 0x1520)  # < $153A
        h.put16(0x0FDA, 0x0B70)
        h.put(0x0D50, 0xF4)      # -12
        h.call_jsr(h.addr("Manhandla_StopIfOutOfBounds"), x=0)
        self.assertEqual(h.get(0x0D50), 0x08, "Left OOB must bounce RIGHT (+8)")

        # Right OOB moving right (+12) -> must bounce LEFT (-8 = $F8)!
        h.put16(0x0FD8, 0x15E0)  # >= $15C8
        h.put(0x0D50, 0x0C)      # +12
        h.call_jsr(h.addr("Manhandla_StopIfOutOfBounds"), x=0)
        self.assertEqual(h.get(0x0D50), 0xF8, "Right OOB must bounce LEFT (-8)")

    def test_big_chuchu_alternating_beats_and_enrage(self):
        h = self._make_harness()
        h.put(0x0DD0, 9)
        h.put(0x0E90, 2)      # Phase 2
        h.put(0x0D80, 4)      # BigChuchu_Main
        h.put(0x0E50, 0x30)   # Normal HP (> $20)
        h.put(0x0E10, 0)      # TimerC = 0 (active)
        h.put(0x0EB0, 0)      # Beat 0 Stalk
        h.put(0x0EE0, 0)      # TimerD = 0 -> enters Swell Telegraph!
        h.call_jsr(h.addr("BigChuchu_RunBeat"), x=0)
        self.assertEqual(h.get(0x0EB0), 1, "Must enter Beat 1 (Swell Telegraph)")
        self.assertEqual(h.get(0x0EE0), 0x1E, "Normal swell telegraph = 30 frames")
        self.assertIn(0x32, h.sfx3)

        # Expire Swell -> Pattern A (Aimed Pair) -> Punish Window
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("BigChuchu_RunBeat"), x=0)
        self.assertEqual(h.get(0x0EB0), 3, "Pattern A must enter Beat 3 (Punish Window)")
        self.assertEqual(len(self.spawned_slots), 2, "Aimed Pair must spawn 2 ChuchuBlast orbs")
        for s in self.spawned_slots:
            self.assertEqual(h.get(0x0F10 + s), 0x78, "Each orb must have 2s lifetime TimerE=$78")

        # Next Swell (enraged HP <= $20!) -> Pattern B (Elastic Lunge, faster!)
        h.put(0x0E50, 0x18)
        h.put(0x0EB0, 0)
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("BigChuchu_RunBeat"), x=0)
        self.assertEqual(h.get(0x0EE0), 0x16, "Enraged swell telegraph = 22 frames")
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("BigChuchu_RunBeat"), x=0)
        self.assertEqual(h.get(0x0EB0), 2, "Pattern B must enter Beat 2 (Elastic Lunge)")
        self.assertEqual(h.get(0x0D50), 0x22, "Enraged lunge speed = $22")

    def test_manhandla_phase1_telegraphed_volley_and_blast_despawn(self):
        h = self._make_harness()
        # Phase 1 body with 1 living head (slot 13 alive, 14 & 15 dead)
        h.put(0x0DD0 + 0, 9)
        h.put(0x0D80 + 0, 6)  # Manhandla_Body
        h.put(h.addr("Offspring1_Id"), 13); h.put(0x0DD0 + 13, 9); h.put(0x0E20 + 13, 0x88); h.put(0x0E30 + 13, 1)
        h.put(h.addr("Offspring2_Id"), 14); h.put(0x0DD0 + 14, 0)
        h.put(h.addr("Offspring3_Id"), 15); h.put(0x0DD0 + 15, 0)
        h.put(0x0EB0 + 0, 0)  # Stalking
        h.put(0x0EE0 + 0, 0)  # TimerD expired -> enter telegraphed volley!
        h.call_jsr(h.addr("Sprite_Manhandla_Main"), x=0)
        self.assertEqual(h.get(0x0EB0 + 0), 1, "Must enter Phase 1 telegraph state (SprMiscE=1)")
        self.assertEqual(h.get(0x0EE0 + 0), 0x22, "Phase 1 volley telegraph = 34 frames")
        self.assertIn(0x2A, h.sfx3, "Bud charge SFX3.$2A cue")

        # Expire telegraph -> spawns 3 Mothula beams, scales next cooldown to $44 (1 head left!)
        h.put(0x0EE0 + 0, 0)
        self.spawned_slots.clear()
        h.call_jsr(h.addr("Sprite_Manhandla_Main"), x=0)
        self.assertEqual(h.get(0x0EB0 + 0), 0)
        self.assertEqual(h.get(0x0EE0 + 0), 0x44, "1 head remaining must scale volley CD to $44")
        self.assertEqual(len(self.spawned_slots), 3, "Must spawn 3 Mothula beams")

        # ChuchuBlast despawns cleanly when TimerE hits 0
        h.put(0x0DD0 + 5, 9)
        h.put(0x0D80 + 5, 0x0A)  # ChuchuBlast
        h.put(0x0F10 + 5, 0)     # TimerE == 0
        h.call_jsr(h.addr("Sprite_Manhandla_Main"), x=5)
        self.assertEqual(h.get(0x0DD0 + 5), 0, "Expired ChuchuBlast must despawn")


# =====================================================================
# 4. D5 Twinrova 3-Act Cinematic Compiled 65816 Tests
# =====================================================================
class Q333TwinrovaCompiledTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = get_lakesnes_lib()
        if cls.lib is None or find_asar() is None:
            return
        src = (ROOT / "Sprites/Bosses/twinrova.asm").read_text(encoding="utf-8")
        src = src.replace("incbin twinrova.bin", "fillbyte $00 : fill $2000")
        harness = f"""
lorom
incsrc "Util/macros.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"
{JUMP_TABLE_LOCAL_ASM}
Sprite_CheckActive = $318000
Sprite_DamageFlash_Long = $318004
Sprite_Move = $318008
Sprite_BounceFromTileCollision = $31800C
Sprite_FloatTowardPlayer = $318010
Sprite_SpawnIceKeese = $318014
Sprite_SpawnFireKeese = $318018
Sprite_CountActiveById = $31801C
BossKit_FireTrail = $328004
BossKit_IceTrail = $328008
NewMainSprFunction = $06FFF8
NewSprPrepFunction = $068EB9
org $308000
NewSprRoutinesLong:
  fill $300
NewSprPrepRoutinesLong:
  fill $300
org $329000
{src}
"""
        cls.rom, cls.labels = assemble_snippet(harness)

    def _make_harness(self) -> CpuHarness:
        if self.lib is None or find_asar() is None:
            self.skipTest("LakeSnes or asar unavailable")
        h = CpuHarness(self.lib, self.rom, self.labels, default_db=0x32)
        self.fireball_spawns = 0
        self.rng_val = 0

        def stub_sfx2(fx):
            fx.sfx2.append(fx.cpu.a & 0xFF)

        def stub_sfx3(fx):
            fx.sfx3.append(fx.cpu.a & 0xFF)

        def stub_rng(fx):
            self.rng_val = (self.rng_val + 17) & 0xFF
            fx.cpu.a = self.rng_val
            fx.cpu.z = (self.rng_val == 0)

        def stub_fireball(fx):
            self.fireball_spawns += 1
            fx.cpu.y = 10
            fx.cpu.n = False

        def stub_proj(fx):
            fx.put(0x00, 0x18)
            fx.put(0x01, 0x1E)

        def stub_count(fx):
            fx.put(0x02, 0)

        def stub_below(fx):
            fx.cpu.y = 0

        for name, fn in (
            ("Sprite_CheckActive", lambda fx: setattr(fx.cpu, "c", True)),
            ("Sprite_DamageFlash_Long", None),
            ("Sprite_CheckDamageFromPlayer", None),
            ("Sprite_CheckDamageToPlayerSameLayer", None),
            ("Sprite_DrawShadow", None),
            ("Sprite_PrepOamCoord", None),
            ("Sprite_OAM_AllocateDeferToPlayer", None),
            ("Sprite_KillFriends", None),
            ("Sprite_Move", None),
            ("Sprite_BounceFromTileCollision", None),
            ("Sprite_CheckTileCollision", None),
            ("Sprite_FloatTowardPlayer", None),
            ("Sprite_IsBelowPlayer", stub_below),
            ("Sprite_DirectionToFacePlayer", None),
            ("Sprite_ApplySpeedTowardsPlayer", None),
            ("Sprite_ProjectSpeedTowardsPlayer", stub_proj),
            ("Sprite_SpawnFireball", stub_fireball),
            ("Sprite_SpawnIceKeese", lambda fx: setattr(fx.cpu, "y", 11)),
            ("Sprite_SpawnFireKeese", lambda fx: setattr(fx.cpu, "y", 11)),
            ("Sprite_CountActiveById", stub_count),
            ("Sprite_GetTileAttr", None),
            ("Sprite_ShowMessageUnconditional", None),
            ("GetRandomInt", stub_rng),
            ("Sound_SetSfx2PanLong", stub_sfx2),
            ("Sound_SetSfx3PanLong", stub_sfx3),
            ("BossKit_FireTrail", None),
            ("BossKit_IceTrail", None),
        ):
            h.add_stub(h.addr(name), name, fn)
        return h

    def test_full_3act_progression_deterministic_fusion_and_rod_lifecycle(self):
        h = self._make_harness()
        # Start in Twinrova_Init (Action 0), HP = $5A
        h.put(0x0DD0, 9)
        h.put(0x0E50, 0x5A)
        h.put(0x0D80, 0)
        h.put(0x0EE0, 0)  # TimerD = 0
        h.put(0x0DC0, 7)  # Simulate re-entry non-zero SprGfx; Init must clear to 0!

        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 8, "Act 1 must open with Koume (Action 8)")
        self.assertEqual(h.get(0x0DC0), 0, "SprGfx base offset must be zeroed")
        self.assertEqual(h.get(0x0E90), 0, "SprMiscD must be 0 (Act 1)")

        # Koume at HP = $35 (just above fusion threshold $34): stays Act 1, weak to Ice Rod (0, 1)
        h.put(0x0E50, 0x35)
        h.put(0x0EE0, 0x70)
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 8)
        self.assertEqual(h.get(0x0D90), 8, "Koume Frame 8")
        self.assertEqual((h.get(0x7F6CEB), h.get(0x7F6CEC)), (0, 1), "Koume weak to Ice Rod")

        # Koume timer hits 0 -> deterministic tag-out to Kotake (Action 9, weak to Fire Rod (1, 0))
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 9, "Koume must deterministically tag in Kotake")
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D90), 9, "Kotake Frame 9")
        self.assertEqual((h.get(0x7F6CEB), h.get(0x7F6CEC)), (1, 0), "Kotake weak to Fire Rod")

        # Drop HP to exact fusion threshold $34 -> ZERO RNG immediate Act 2 Fusion Cinematic!
        h.put(0x0E50, 0x34)
        h.put(0x0D10, 0x40)  # Off-center X -> must ease toward $80
        h.put(0x0D00, 0x30)  # Off-center Y -> must ease toward $68
        h.sfx2.clear()
        h.sfx3.clear()
        h.calls.clear()
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 0x0B, "HP <= $34 must deterministically trigger Action $0B Fusion")
        self.assertEqual(h.get(0x0E90), 1, "SprMiscD must be 1 (Act 2 Fusion)")
        self.assertEqual(h.get(0x0EE0), 0x4E, "Fusion cinematic = 78 frames ($4E)")
        self.assertEqual(h.get(0x0E60) & 0x40, 0x40, "Must be invincible during fusion")
        self.assertIn(0x35, h.sfx2, "Fusion rumble start SFX")

        # Run all 78 frames of Act 2 Fusion Cinematic
        fusion_frames_seen = set()
        for step in range(0x4E):
            h.put(0x1A, step)
            h.put(0x0EE0, 0x4D - step)
            h.calls.clear()
            h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
            if h.get(0x0D80) == 0x0B:
                fusion_frames_seen.add(h.get(0x0D90))
                call_names = [c[0] for c in h.calls]
                self.assertNotIn("Sprite_CheckDamageFromPlayer", call_names, "No damage during fusion")
                self.assertNotIn("Sprite_CheckDamageToPlayerSameLayer", call_names, "No bump during fusion")

        self.assertTrue({8, 9, 7}.issubset(fusion_frames_seen),
                        f"Fusion must show Koume (8), Kotake (9) and Combined reveal (7), got {fusion_frames_seen}")
        self.assertEqual(h.get(0x0D80), 1, "Must enter Act 3 Twinrova_MoveState (Action 1)")
        self.assertEqual(h.get(0x0E90), 2, "SprMiscD must be 2 (Act 3)")
        self.assertEqual(h.get(0x0E60) & 0x40, 0, "Invulnerability cleared after fusion")
        self.assertEqual(h.get16(0x011A), 0, "Screen shake X cleared")
        self.assertEqual(h.get16(0x011C), 0, "Screen shake Y cleared")
        for s2 in (0x0E, 0x0F, 0x0C):
            self.assertIn(s2, h.sfx2, f"Expected SFX2.${s2:02X} during fusion")
        for s3 in (0x2A, 0x26):
            self.assertIn(s3, h.sfx3, f"Expected SFX3.${s3:02X} during fusion")

        # Act 3: Deterministic Fire Wave -> Ice Barrage alternation!
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 4, "Must enter Twinrova_PrepareAttack")
        self.assertEqual(h.get(0xAC), 0, "First Act 3 cast must be Fire Wave ($AC=0)")
        self.assertEqual(h.get(0x0EE0), 0x28, "Normal wind-up = 40 frames ($28)")
        self.assertEqual(h.get(0x0D90), 4, "PrepareAttack starts on Twinrova_Ready frame 4")
        # Finish PrepareAttack -> enters FireAttack (Action 5, Frame 7, Ice Rod weak)
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 5, "Must enter Twinrova_FireAttack")
        self.assertEqual(h.get(0x0D90), 7, "FireAttack casts in wide-arm Frame 7")

        # Enraged (<=$1A HP) second cast -> Ice Barrage ($AC=1) with faster $1C wind-up!
        h.put(0x0E50, 0x18)
        h.put(0x0D80, 1)
        h.put(0x0EE0, 0)
        h.call_jsr(h.addr("Sprite_Twinrova_Main"), x=0)
        self.assertEqual(h.get(0x0D80), 4)
        self.assertEqual(h.get(0xAC), 1, "Second Act 3 cast must alternate to Ice Barrage ($AC=1)")
        self.assertEqual(h.get(0x0EE0), 0x1C, "Enraged wind-up drops to 28 frames ($1C)")

        # RestoreRodDamageOnDeath still restores (0, 0) on SprState == 4
        h.put(0x0DD0, 4)
        h.call_jsr(h.addr("Twinrova_RestoreRodDamageOnDeath"), x=0)
        self.assertEqual((h.get(0x7F6CEB), h.get(0x7F6CEC)), (0, 0))


# =====================================================================
# 5. Finale Kydreeok 3-Phase + Unique Maneuvers Compiled 65816 Tests
# =====================================================================
class Q333KydreeokCompiledTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.lib = get_lakesnes_lib()
        if cls.lib is None or find_asar() is None:
            return
        body = (ROOT / "Sprites/Bosses/kydreeok.asm").read_text(encoding="utf-8")
        body = body.replace("incbin kydreeok.bin", "fillbyte $00 : fill $2000")
        body = body.replace("incbin kydreeok_phase2.bin", "fillbyte $00 : fill $2000")
        head = (ROOT / "Sprites/Bosses/kydreeok_head.asm").read_text(encoding="utf-8")
        harness = f"""
lorom
incsrc "Util/macros.asm"
incsrc "Core/symbols.asm"
incsrc "Core/sprite_macros.asm"
incsrc "Sprites/sprite_registry_ids.asm"
{JUMP_TABLE_LOCAL_ASM}
Sprite_CheckActive = $318000
Sprite_DamageFlash_Long = $318004
Sprite_Move = $318008
Sprite_BounceFromTileCollision = $31800C
Sprite_FloatTowardPlayer = $318010
DreamReturn_IsDreaming = $318014
BossDefeated_Remnant = $318018
Kydreeok_FinalePal = $31801C
NewMainSprFunction = $06FFF8
NewSprPrepFunction = $068EB9
org $308000
NewSprRoutinesLong:
  fill $300
NewSprPrepRoutinesLong:
  fill $300
org $328000
incsrc "Sprites/Bosses/boss_kit.asm"
incsrc "Sprites/Bosses/boss_director.asm"
{body}
{head}
"""
        cls.rom, cls.labels = assemble_snippet(harness)

    def _make_harness(self) -> CpuHarness:
        if self.lib is None or find_asar() is None:
            self.skipTest("LakeSnes or asar unavailable")
        h = CpuHarness(self.lib, self.rom, self.labels, default_db=0x32)
        self.fireballs: list[tuple[int, int, int]] = []
        self.next_fb = 12

        def stub_sfx2(fx):
            fx.sfx2.append(fx.cpu.a & 0xFF)

        def stub_sfx3(fx):
            fx.sfx3.append(fx.cpu.a & 0xFF)

        def stub_fb(fx):
            slot = self.next_fb
            self.next_fb = 12 if self.next_fb >= 15 else self.next_fb + 1
            fx.put(0x0DD0 + slot, 9)
            fx.put(0x0E20 + slot, 0x55)
            fx.cpu.y = slot
            fx.cpu.n = False
            self.fireballs.append((slot, fx.get(0x00), fx.get(0x02)))

        def stub_proj(fx):
            fx.put(0x00, 0x18)
            fx.put(0x01, 0x20)

        def stub_apply(fx):
            spd = fx.cpu.a & 0xFF
            fx.put(0x0D50 + fx.cpu.x, spd)
            fx.put(0x0D40 + fx.cpu.x, spd)

        for name, fn in (
            ("Sprite_CheckActive", lambda fx: setattr(fx.cpu, "c", True)),
            ("Sprite_DamageFlash_Long", None),
            ("Sprite_CheckDamageFromPlayer", None),
            ("Sprite_CheckDamageToPlayer", None),
            ("Sprite_PlayerCantPassThrough", None),
            ("Sprite_PrepOamCoord", None),
            ("Sprite_OAM_AllocateDeferToPlayer", None),
            ("OAM_AllocateFromRegionE", None),
            ("Sprite_Move", None),
            ("Sprite_SpawnDynamically", None),
            ("Sprite_SpawnFireball", stub_fb),
            ("Sprite_ApplySpeedTowardsPlayer", stub_apply),
            ("Sprite_ProjectSpeedTowardsPlayer", stub_proj),
            ("Sprite_DirectionToFacePlayer", lambda fx: setattr(fx.cpu, "y", 2)),
            ("Sprite_IsToRightOfPlayer", lambda fx: (setattr(fx.cpu, "y", 0), fx.put(0x0F, 10))),
            ("Sprite_ShowMessageUnconditional", None),
            ("GetRandomInt", None),
            ("Sound_SetSfx2PanLong", stub_sfx2),
            ("Sound_SetSfx3PanLong", stub_sfx3),
            ("DreamReturn_IsDreaming", lambda fx: setattr(fx.cpu, "c", False)),
            ("BossDefeated_Remnant", None),
            ("Kydreeok_FinalePal", None),
        ):
            h.add_stub(h.addr(name), name, fn)
        return h

    def _setup_body_and_heads(self, h: CpuHarness, *, stage: int, both_heads: bool = True):
        h.call_jsl(h.addr("BossKit_Reset"), x=0, db=0x32)
        h.call_jsl(h.addr("BossDirector_Reset"), x=0, db=0x32)
        h.put(h.addr("Kydreeok_Id"), 0)
        h.put(h.addr("Offspring1_Id"), 1)
        h.put(h.addr("Offspring2_Id"), 2)
        # Body slot 0
        h.put(0x0DD0 + 0, 9)
        h.put(0x0E20 + 0, 0x7A)
        h.put(0x0D10 + 0, 0x80); h.put(0x0D30 + 0, 0x01)
        h.put(0x0D00 + 0, 0x80); h.put(0x0D20 + 0, 0x00)
        h.put(0x0E90 + 0, 2 if stage == 3 else 1)  # SprMiscD
        h.put(0x0D80 + 0, 1)  # Stand
        h.put(0x36, 10)
        h.put(h.addr("BossDir_Stage"), stage)
        # Left head slot 1
        h.put(0x0DD0 + 1, 9)
        h.put(0x0E20 + 1, 0xCF)
        h.put(0x0E30 + 1, 0)
        h.put(0x0D80 + 1, 1)  # Idle
        h.put(0x0D10 + 1, 0x60); h.put(0x0D30 + 1, 0x01)
        h.put(0x0D00 + 1, 0x50); h.put(0x0D20 + 1, 0x00)
        # Right head slot 2
        if both_heads:
            h.put(0x0DD0 + 2, 9)
            h.put(0x0E20 + 2, 0xCF)
            h.put(0x0E30 + 2, 1)
            h.put(0x0D80 + 2, 1)  # Idle
            h.put(0x0D10 + 2, 0xA0); h.put(0x0D30 + 2, 0x01)
            h.put(0x0D00 + 2, 0x50); h.put(0x0D20 + 2, 0x00)

    def test_distinct_per_attack_telegraph_cues(self):
        h = self._make_harness()
        # Bite ($02) -> SFX3.$26; Breath ($04) -> SFX3.$2A; Sweep ($0B) -> SFX3.$2A; Spit ($0A) -> SFX2.$0E
        for action, channel, expected_sfx in (
            (0x02, "sfx3", 0x26),
            (0x04, "sfx3", 0x2A),
            (0x0B, "sfx3", 0x2A),
            (0x0A, "sfx2", 0x0E),
        ):
            h.sfx2.clear(); h.sfx3.clear()
            h.put(0x0D80 + 1, action)
            h.put(0x0ED0 + 1, 0)  # SprMiscG = 0 (first telegraph frame)
            h.call_jsr(h.addr("KydreeokHead_Cue"), x=1, db=0x32)
            self.assertTrue(h.cpu.c, f"Cue must set carry on first frame for action ${action:02X}")
            got = h.sfx2 if channel == "sfx2" else h.sfx3
            self.assertEqual(got, [expected_sfx], f"Action ${action:02X} must play {channel}.${expected_sfx:02X}")

    def test_stage2_sweeping_arc_breath_lays_7_flames_then_pants(self):
        h = self._make_harness()
        self._setup_body_and_heads(h, stage=2, both_heads=False)
        h.put(h.addr("BossDir_Turn"), 0)  # Stage 2 turn 0 = !KydTurn_Sweep!
        h.call_jsl(h.addr("Kydreeok_TakeTurn"), x=0, db=0x32)
        self.assertEqual(h.get(0x0D80 + 1), 0x0B, "Stage 2 turn 0 must start !KydHead_Sweep ($0B)")
        self.assertEqual(h.get(0x0DF0 + 1), 32, "Stage 2 sweep telegraph = 32 frames")

        # Complete telegraph -> enters !KydHead_SweepFire ($0C)
        h.put(0x0DF0 + 1, 0)
        h.call_jsr(h.addr("Sprite_KydreeokHead_Main"), x=1, db=0x32)
        self.assertEqual(h.get(0x0D80 + 1), 0x0C, "Must transition to !KydHead_SweepFire ($0C)")

        # Step through all 7 flame spawns -> must enter !KydHead_Pant ($08)
        for _ in range(7):
            h.put(0x0EE0 + 1, 0)  # SprTimerD = 0
            h.call_jsr(h.addr("Sprite_KydreeokHead_Main"), x=1, db=0x32)
        self.assertEqual(h.get(0x0D80 + 1), 0x08, "After 7 crescent flames, must transition to Pant ($08)")
        # Verify garnish pool ($7FF800..$7FF81D) received active fire garnishes ($10)
        flames = sum(1 for i in range(0x1E) if h.get(0x7FF800 + i) == 0x10)
        self.assertEqual(flames, 6, "BossKit garnish cap = 6 live flames per head")

    def test_stage3_dual_crossing_breath_and_swoop_and_dive_ring_and_regrow(self):
        h = self._make_harness()
        self._setup_body_and_heads(h, stage=3, both_heads=True)

        # Stage 3 turn 0 = !KydTurn_DualBreath -> launches BOTH heads simultaneously!
        h.put(h.addr("BossDir_Turn"), 0)
        h.call_jsl(h.addr("Kydreeok_TakeTurn"), x=0, db=0x32)
        self.assertEqual(h.get(0x0D80 + 1), 0x0B, "Left head enters Sweep ($0B)")
        self.assertEqual(h.get(0x0D80 + 2), 0x0B, "Right head ALSO enters Sweep ($0B) simultaneously!")
        self.assertEqual(h.get(h.addr("BossDir_Token")), 1, "Left head holds BossDir_Token")

        # Stage 3 turn 2 = !KydTurn_Swoop -> sets bit 2, plays SFX1.$13, returns !KydOrder_Fly (2)
        h.put(h.addr("BossDir_Token"), 0xFF)
        h.put(h.addr("BossDir_Turn"), 2)
        h.sfx1.clear()
        h.call_jsl(h.addr("Kydreeok_TakeTurn"), x=0, db=0x32)
        self.assertEqual(h.cpu.a & 0xFF, 2, "Swoop must return !KydOrder_Fly (2)")
        self.assertEqual(h.get(h.addr("Kydreeok_Flags")) & 0x04, 0x04, "Must set swoop bit 2")
        self.assertIn(0x13, h.sfx1, "Must play SFX1.$13 Large boss swoosh")

        # TakeOff climbs to altitude 16 and enters !Kyd_Swoop ($04), then fires 3 staggered fireballs
        h.put(0x0F70 + 0, 14)  # SprHeight = 14 -> +2 hits 16
        h.put(0x0D80 + 0, 7)   # TakeOff
        h.call_jsr(h.addr("Sprite_Kydreeok_Main"), x=0, db=0x32)
        self.assertEqual(h.get(0x0D80 + 0), 0x04, "Low-altitude swoop must enter !Kyd_Swoop ($04)")
        self.fireballs.clear()
        for t in (0x34, 0x20, 0x0C):
            h.put(0x0DF0 + 0, t)
            h.call_jsr(h.addr("Sprite_Kydreeok_Main"), x=0, db=0x32)
        self.assertEqual(len(self.fireballs), 3, "Swoop must fire 3 staggered aimed fireballs")

        # High Dive landing (bit 2 clear) spawns 4-way diagonal shockwave fireball ring!
        h.put(h.addr("Kydreeok_Flags"), 0)
        h.put(0x0F70 + 0, 4)   # SprHeight = 4 -> -4 lands at 0
        h.put(0x0D80 + 0, 9)   # Dive
        self.fireballs.clear()
        h.call_jsr(h.addr("Sprite_Kydreeok_Main"), x=0, db=0x32)
        self.assertEqual(len(self.fireballs), 4, "Stage 3 high Dive must unleash 4-way fireball ring")

        # Stage 3 RegrowTick starts at 90 steps (12s, down from 20s) when 1 head is dead
        h.put(0x0DD0 + 2, 0)   # Kill right head
        h.put(h.addr("Kydreeok_Regrow"), 0)
        h.call_jsl(h.addr("Kydreeok_RegrowTick"), x=0, db=0x32)
        self.assertEqual(h.get(h.addr("Kydreeok_Regrow")), 90, "Stage 3 regrow timer must start at 90 (12s)")

    def test_stage3_dual_breath_single_head_fallback_and_healing_beat_intact(self):
        h = self._make_harness()
        self._setup_body_and_heads(h, stage=3, both_heads=False)
        # Turn 0 is DualBreath, but only 1 head is alive -> desperation opener (Spit $0A)!
        h.put(h.addr("BossDir_Turn"), 0)
        h.call_jsl(h.addr("Kydreeok_TakeTurn"), x=0, db=0x32)
        self.assertEqual(h.get(0x0D80 + 1), 0x0A, "Desperation single-head fallback opens with Spit ($0A)")

        # Song of Healing finish preserved: !Kyd_Wounded ($0A) + SongFlag==1 -> !Kyd_Healing ($0B)
        h.put(0x0D80 + 0, 0x0A)  # !Kyd_Wounded
        h.put(0x0F70 + 0, 0)     # Grounded
        h.put(h.addr("SongFlag"), 1)
        h.call_jsr(h.addr("Sprite_Kydreeok_Main"), x=0, db=0x32)
        self.assertEqual(h.get(0x0D80 + 0), 0x0B, "Song of Healing must still transition Wounded -> Healing")
        self.assertEqual(h.get(h.addr("SongFlag")), 0, "SongFlag consumed")


if __name__ == "__main__":
    unittest.main()
