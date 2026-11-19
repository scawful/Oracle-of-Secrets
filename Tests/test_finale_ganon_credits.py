"""Q332 Finale Bosses (Ganon Beast & Ganondorf) + Ending Credits Scenes 0-7 tests.

Covers:
1. Ganon Beast 16-bit 13-frame animated tilesheet art pipeline (`build_ganon_beast_art.py --check`,
   cell budget <= 43 + 5 reserved Ganondorf cells, 15/15 palette utilization, cloak cleanliness).
2. Compiled 65816 execution (via Lakesnes CPU core) of Ganon Beast animated stomp march
   (never slides), phase scaling, micro-quake, cloak-warp ambush, wall-slam sparks, and 8-way
   spinning trident draw.
3. Compiled 65816 execution of Ganondorf Phase 1/2/3 escalations (Phase 1 parity preserved,
   Phase 2/3 bounce speed-up, 4-way & 8-way stomp shockwaves, twin-flank return barrage,
   and angled bat sweeps).
4. Compiled 65816 execution & ROM table contracts for Credits Scenes 0-7 (all 8 BG3 captions,
   Scene 5 D4 River Zora spriteset/palette, Scene 7 volcanic emerald-moss grass palette fix,
   Scene 3 Kalyxo Castle framing, and active OAM actors on every scene 0-7).
"""
from __future__ import annotations

import ctypes as C
import json
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))
from d4_compiled_fight_check import Cpu  # noqa: E402

ROM_PATH = ROOT / "Roms" / "oos168x.sfc"
SYM_PATH = ROOT / "Roms" / "oos168x.sym"
ART_DIR = ROOT / "Data" / "graphics" / "ganon_beast"
ART_SCRIPT = ROOT / "Scripts" / "Generate" / "build_ganon_beast_art.py"
BEAST_BIN = ROOT / "Sprites" / "Bosses" / "ganon_beast.bin"
BEAST_FRAMES = ROOT / "Sprites" / "Bosses" / "ganon_beast_frames.asm"

EXPECTED_FRAMES = [
    "idle",
    "walk_l",
    "walk_r",
    "roar",
    "charge_lean",
    "core_open",
    "core_pulse",
    "cloak",
    "trident_up",
    "trident_throw",
    "trident_v",
    "trident_h",
    "trident_d",
]
RESERVED_GANONDORF_CELLS = {0x6A, 0x6C, 0x6E, 0x80, 0x82}


def snes_to_pc(address: int) -> int:
    return (((address >> 16) & 0x7F) << 15) | (address & 0x7FFF)


def load_symbols(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", sym_path.read_text(encoding="utf-8")):
        labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    for name, val in re.findall(r"(?m)^(\w+)\s*=\s*\$([0-9A-Fa-f]+)", (ROOT / "Core" / "symbols.asm").read_text(encoding="utf-8")):
        labels.setdefault(name, int(val, 16))
    return labels


def find_lakesnes() -> Path | None:
    candidates = [
        ROOT.parent / "lakesnes",
        ROOT.parent.parent / "lakesnes",
        Path("/Users/scawful/src/hobby/lakesnes"),
    ]
    for path in candidates:
        if (path / "snes" / "cpu.c").is_file() and (path / "snes" / "statehandler.c").is_file():
            return path
    return None


class Compiled65816Harness:
    """Minimal Lakesnes 65816 execution harness for compiled ROM routines."""

    _cached_lib = None
    _cached_tmpdir = None

    @classmethod
    def get_lib(cls):
        if cls._cached_lib is not None:
            return cls._cached_lib
        lakesnes = find_lakesnes()
        if lakesnes is None:
            return None
        tmpdir = tempfile.TemporaryDirectory(prefix="q332-lakesnes-")
        lib_path = Path(tmpdir.name) / "cpu.dylib"
        subprocess.run(
            [
                "cc", "-shared", "-fPIC", "-O2",
                str(lakesnes / "snes" / "cpu.c"),
                str(lakesnes / "snes" / "statehandler.c"),
                "-o", str(lib_path),
            ],
            check=True,
        )
        lib = C.CDLL(str(lib_path))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls._cached_tmpdir = tmpdir
        cls._cached_lib = lib
        return lib

    def __init__(self, lib, rom: bytes, labels: dict[str, int], default_db: int = 0x2A):
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.stubs: dict[int, str] = {}
        self.calls: list[tuple[str, int]] = []
        self.bad_writes: list[tuple[int, int]] = []
        self.oam_cursor = 0x0800
        self.oam_hi_cursor = 0x0A00
        self.oam_allocs: list[int] = []
        self.sfx3_calls: list[int] = []
        self.rand_val = 0

        self.read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self.read(a))
        self.write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self.write(a, v))
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self.read_cb, self.write_cb, self.idle_cb)
        self.cpu = self.p.contents
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, flag, False)
        self.cpu.mf = True
        self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x01FF
        self.cpu.a = self.cpu.x = self.cpu.y = 0
        self.cpu.db = default_db

        # Stub common vanilla engine JSL services cleanly with RTL ($6B)
        for name in (
            "OAM_AllocateFromRegionA",
            "Sprite_PrepOamCoord",
            "Sprite_OAM_AllocateDeferToPlayer",
            "Sprite_SpawnDynamically",
            "Sprite_SetSpawnedCoords",
            "Sprite_Move",
            "Sprite_ApplySpeedTowardsPlayer",
            "Sprite_ProjectSpeedTowardsPlayer",
            "Sprite_CheckDamageToPlayerSameLayer",
            "Sprite_CheckDamageFromPlayer",
            "Sprite_DrawShadow",
            "SpriteSFX_QueueSFX2WithPan",
            "SpriteSFX_QueueSFX3WithPan",
            "GetRandomInt",
        ):
            addr = self.addr(name)
            if addr is not None:
                self.stubs[addr] = name

    def addr(self, name: str) -> int | None:
        return self.labels.get(f"Oracle_{name}", self.labels.get(name))

    @staticmethod
    def ram_offset(a: int) -> int | None:
        bank = a >> 16
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
            pc = snes_to_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def write(self, a: int, v: int) -> None:
        off = self.ram_offset(a)
        if off is None:
            self.bad_writes.append((a, v))
            return
        self.ram[off] = v & 0xFF

    def get(self, a: int) -> int:
        return self.read(a)

    def get16(self, a: int) -> int:
        return self.read(a) | (self.read(a + 1) << 8)

    def put(self, a: int, v: int) -> None:
        self.write(a, v & 0xFF)

    def put16(self, a: int, v: int) -> None:
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def spr(self, name: str, val: int | None = None, slot: int = 2) -> int:
        base = self.addr(name)
        assert base is not None, f"Missing symbol {name}"
        if val is None:
            return self.get(base + slot)
        self.put(base + slot, val)
        return val

    def handle_stub(self, name: str) -> None:
        a_lo = self.cpu.a & 0xFF
        self.calls.append((name, a_lo))
        if name == "OAM_AllocateFromRegionA":
            self.oam_allocs.append(a_lo)
            self.put16(0x90, self.oam_cursor)
            self.put16(0x92, self.oam_hi_cursor)
            self.oam_cursor += a_lo
            self.oam_hi_cursor += max(1, a_lo >> 2)
        elif name == "Sprite_SpawnDynamically":
            # Find first free sprite slot in $0DD0[0..15] (state == 0)
            chosen = 0xFF
            for s in range(15, -1, -1):
                if self.ram[0x0DD0 + s] == 0:
                    chosen = s
                    break
            if chosen == 0xFF:
                self.cpu.y = 0xFF
                self.cpu.n = True
                self.cpu.z = False
            else:
                self.ram[0x0DD0 + chosen] = 0x09
                self.ram[0x0E20 + chosen] = a_lo
                self.cpu.y = chosen
                self.cpu.n = False
                self.cpu.z = (chosen == 0)
        elif name == "Sprite_SetSpawnedCoords":
            src = self.cpu.x & 0xFF
            dst = self.cpu.y & 0xFF
            for base in (0x0D00, 0x0D10, 0x0D20, 0x0D30, 0x0F20):
                self.ram[base + dst] = self.ram[base + src]
        elif name in ("Sprite_ApplySpeedTowardsPlayer", "Sprite_ProjectSpeedTowardsPlayer"):
            # Deterministic vector (+speed, 0) for testable deflection
            slot = self.cpu.x & 0xFF
            self.ram[0x0D50 + slot] = a_lo
            self.ram[0x0D40 + slot] = 0
            self.ram[0x00] = 0
            self.ram[0x01] = a_lo
        elif name == "SpriteSFX_QueueSFX3WithPan":
            self.sfx3_calls.append(a_lo)
        elif name == "GetRandomInt":
            self.cpu.a = (self.cpu.a & 0xFF00) | (self.rand_val & 0xFF)
            self.cpu.z = (self.rand_val & 0xFF) == 0
            self.cpu.n = bool(self.rand_val & 0x80)
        elif name == "Sprite_PrepOamCoord":
            self.put16(0x00, 128)
            self.put16(0x02, 128)

    def call(
        self,
        name: str,
        *,
        x: int = 2,
        y: int = 0,
        a: int = 0,
        long_return: bool = False,
        db: int | None = None,
        limit: int = 50000,
    ) -> None:
        addr = self.addr(name)
        assert addr is not None, f"Missing symbol {name}"
        cpu = self.cpu
        cpu.x = x & 0xFF
        cpu.y = y & 0xFF
        cpu.a = (cpu.a & 0xFF00) | (a & 0xFF)
        cpu.mf = True
        cpu.xf = True
        cpu.k = addr >> 16
        cpu.pc = addr & 0xFFFF
        if db is not None:
            cpu.db = db
        sp0 = cpu.sp
        sentinel = (addr & 0xFF0000) | 0x7000
        if long_return:
            self.put(sp0, addr >> 16)
            self.put(sp0 - 1, 0x6F)
            self.put(sp0 - 2, 0xFF)
            cpu.sp -= 3
        else:
            self.put(sp0, 0x6F)
            self.put(sp0 - 1, 0xFF)
            cpu.sp -= 2

        for _ in range(limit):
            cur = (cpu.k << 16) | cpu.pc
            if cur == sentinel:
                assert not self.bad_writes, f"{name} unexpected non-WRAM writes: {self.bad_writes}"
                assert cpu.sp == sp0, f"{name} stack imbalance: {cpu.sp:#x} != {sp0:#x}"
                return
            if cur in self.stubs:
                self.handle_stub(self.stubs[cur])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"{name} exceeded instruction limit at {cpu.k:02X}:{cpu.pc:04X}")

    def close(self) -> None:
        self.lib.cpu_free(self.p)


class GanonBeastArtTests(unittest.TestCase):
    def test_build_ganon_beast_art_check_passes(self) -> None:
        proc = subprocess.run(
            [sys.executable, str(ART_SCRIPT), "--check"],
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("cells 43+5 reserved", proc.stdout)

    def test_tilesheet_frames_budget_and_palette_richness(self) -> None:
        proj = json.loads((ART_DIR / "project.json").read_text(encoding="utf-8"))
        frame_names = [f["id"] for f in proj["frames"]]
        self.assertEqual(set(frame_names), set(EXPECTED_FRAMES))
        self.assertEqual(len(frame_names), len(EXPECTED_FRAMES))
        self.assertEqual(BEAST_BIN.stat().st_size, 48 * 128, "ganon_beast.bin must be 48 16x16 4bpp cells")

        # Verify canonical.png uses all 15 non-transparent palette indices and cloak has a single clean silhouette (no floating stray pixels)
        img = Image.open(ART_DIR / "canonical.png")
        self.assertEqual(img.mode, "P")
        used = set(img.tobytes()) - {0}
        self.assertEqual(len(used), 15, f"Expected all 15 non-zero palette indices used, got {sorted(used)}")

        cloak_spec = next(f for f in proj["frames"] if f["id"] == "cloak")
        cx, cy, cw, ch = cloak_spec["rect"]
        px = img.load()
        opaque = {
            (x, y)
            for y in range(cy, cy + ch)
            for x in range(cx, cx + cw)
            if px[x, y] != 0
        }
        self.assertGreater(len(opaque), 200, "Cloak frame unexpectedly sparse")
        # Flood-fill (8-connected) to prove zero disconnected floating stray pixels!
        seen: set[tuple[int, int]] = set()
        components = 0
        for pt in opaque:
            if pt in seen:
                continue
            components += 1
            stack = [pt]
            seen.add(pt)
            while stack:
                ux, uy = stack.pop()
                for dx in (-1, 0, 1):
                    for dy in (-1, 0, 1):
                        nb = (ux + dx, uy + dy)
                        if nb in opaque and nb not in seen:
                            seen.add(nb)
                            stack.append(nb)
        self.assertEqual(components, 1, f"Cloak frame should be 1 cohesive silhouette with zero stray artifacts, got {components} components")

        # Verify generated ASM defines all 13 frame constants and never collides with Ganondorf ball/bat cells
        asm_text = BEAST_FRAMES.read_text(encoding="utf-8")
        for idx, name in enumerate(EXPECTED_FRAMES):
            self.assertIn(f"!BeastFrame_{name} = {idx}", asm_text)
        chr_block = re.search(r"^\.chr\s*\n(.*?)^\.properties", asm_text, re.M | re.S)
        self.assertIsNotNone(chr_block, ".chr block missing from ganon_beast_frames.asm")
        used_chrs = {int(m, 16) for m in re.findall(r"\$([0-9A-Fa-f]{2})", chr_block.group(1))}
        self.assertGreaterEqual(len(used_chrs), 40, "Expected rich deduplicated 4bpp cell set")
        self.assertTrue(
            used_chrs.isdisjoint(RESERVED_GANONDORF_CELLS),
            f"Ganon Beast frame cells collided with reserved Ganondorf cells: {used_chrs & RESERVED_GANONDORF_CELLS}",
        )


class CompiledFinaleAndCreditsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        if not (ROM_PATH.is_file() and SYM_PATH.is_file()):
            raise unittest.SkipTest("Compiled ROM/symbols not present")
        cls.lib = Compiled65816Harness.get_lib()
        if cls.lib is None:
            raise unittest.SkipTest("Lakesnes 65816 core not available")
        cls.rom = ROM_PATH.read_bytes()
        cls.labels = load_symbols(SYM_PATH)

    def make_harness(self, default_db: int = 0x2A) -> Compiled65816Harness:
        return Compiled65816Harness(self.lib, self.rom, self.labels, default_db=default_db)

    # ---- Ganon Beast 65816 behavior ----
    def test_beast_get_phase_thresholds(self) -> None:
        h = self.make_harness(0x2A)
        try:
            expected = {6: 0, 5: 0, 4: 1, 3: 1, 2: 2, 1: 2}
            for hp, want_phase in expected.items():
                h.spr("SprMiscF", hp, slot=2)
                h.call("Beast_GetPhase", x=2)
                self.assertEqual(h.cpu.y & 0xFF, want_phase, f"HP={hp} expected phase {want_phase}")
        finally:
            h.close()

    def test_beast_stomp_march_animates_and_never_slides(self) -> None:
        """Beast_StepWalkAnim must cycle walk_l -> idle(THUD!) -> walk_r -> idle(THUD!)."""
        h = self.make_harness(0x2A)
        try:
            h.spr("SprMiscF", 6, slot=2)   # Phase 1: 12 frames per step
            h.spr("SprGfx", 0x00, slot=2)  # step 0, countdown 0 -> advances to step 1 on first call
            h.spr("SprTimerE", 0, slot=2)

            seen_frames: list[int] = []
            thud_steps: list[int] = []
            thud_sfx: list[int] = []
            for step in range(4):
                # Clear low nibble (tick countdown) so each call advances to the next march step
                h.spr("SprGfx", h.spr("SprGfx", slot=2) & 0xF0, slot=2)
                h.spr("SprTimerE", 0, slot=2)
                h.put(0x012D, 0)
                h.call("Beast_StepWalkAnim", x=2)
                seen_frames.append(h.spr("SprFrame", slot=2))
                if h.spr("SprTimerE", slot=2) == 3:
                    thud_steps.append(step)
                if h.get(0x012D) == 0x07:
                    thud_sfx.append(step)

            # Steps 1, 2, 3, 0 -> frames idle (0) [THUD!], walk_r (2), idle (0) [THUD!], walk_l (1)
            self.assertEqual(seen_frames, [0, 2, 0, 1])
            self.assertEqual(thud_steps, [0, 2], "Both foot-plant steps must trigger SprTimerE=3 micro-quake")
            self.assertEqual(thud_sfx, [0, 2], "Both foot-plant steps must queue heavy thud SFX $07 to $012D")

            # Verify Phase 3 cadence is faster (8 ticks vs 12 ticks in Phase 1)
            h.spr("SprMiscF", 2, slot=2)
            h.spr("SprGfx", 0x00, slot=2)
            h.call("Beast_StepWalkAnim", x=2)
            self.assertEqual(h.spr("SprGfx", slot=2) & 0x0F, 8)
        finally:
            h.close()

    def test_beast_micro_quake_toggles_and_resets_bg_offset(self) -> None:
        h = self.make_harness(0x2A)
        try:
            h.spr("SprSubtype", 0, slot=2)
            h.spr("SprAction", 9, slot=2)  # Beast_ActStalk
            h.spr("SprTimerE", 3, slot=2)
            h.call("Beast_RunMicroQuake", x=2)
            self.assertEqual(h.get16(0x011C), 0x0001)  # +1 px shudder on odd tick

            h.spr("SprTimerE", 2, slot=2)
            h.call("Beast_RunMicroQuake", x=2)
            self.assertEqual(h.get16(0x011C), 0x0000)  # 0 px on even tick

            h.spr("SprTimerE", 1, slot=2)
            h.put16(0x011C, 0x0001)
            h.call("Beast_RunMicroQuake", x=2)
            self.assertEqual(h.get16(0x011C), 0x0000)  # cleanly cleared on final tick
        finally:
            h.close()

    def test_beast_phase3_cloak_warp_and_slam_sparks(self) -> None:
        h = self.make_harness(0x2A)
        try:
            # Phase 1: Beast_GotoStalk enters normal march (no cloak warp)
            h.spr("SprMiscF", 6, slot=2)
            h.spr("SprMiscA", 0, slot=2)
            h.call("Beast_GotoStalk", x=2)
            self.assertEqual(h.spr("SprMiscA", slot=2) & 0x40, 0)
            self.assertEqual(h.spr("SprFrame", slot=2), 1)  # walk_l

            # Phase 3: Beast_GotoStalk toggles bit 5 ($20) -> enters Cloak-Warp Ambush ($40)
            h.spr("SprMiscF", 2, slot=2)
            h.spr("SprSubtype", 0, slot=2)
            h.spr("SprMiscA", 0, slot=2)
            h.call("Beast_GotoStalk", x=2)
            self.assertEqual(h.spr("SprMiscA", slot=2) & 0x40, 0x40)
            self.assertEqual(h.spr("SprFrame", slot=2), 7)  # cloak pose
            self.assertEqual(h.spr("SprTimerD", slot=2), 0x48)

            # Wall-slam sparks spawn 4 diagonal dark shards (Sprite_GanonBall=$46, SprAction=1)
            h.ram[0x0DD0:0x0DE0] = b"\x00" * 16
            h.ram[0x0DD0 + 2] = 0x09  # boss occupies slot 2
            h.call("Beast_SpawnSlamSparks", x=2)
            shards = [
                s for s in range(16)
                if s != 2 and h.ram[0x0DD0 + s] == 0x09 and h.ram[0x0E20 + s] == 0x46 and h.ram[0x0D80 + s] == 1
            ]
            self.assertEqual(len(shards), 4, f"Expected 4 wall-slam sparks, got {len(shards)}")
        finally:
            h.close()

    def test_beast_trident_cycles_all_8_spin_angles(self) -> None:
        h = self.make_harness(0x2A)
        try:
            # Spin table uses ($1A >> 1) & 7 -> writes OAM entry 12 (byte offset $30 -> $0830)
            h.spr("SprX", 128, slot=2)
            h.spr("SprY", 128, slot=2)
            h.spr("SprMiscC", 128, slot=2)
            h.spr("SprMiscD", 128, slot=2)
            h.put16(0x00, 128)  # beast screen X
            h.put16(0x02, 128)  # beast screen Y
            h.put(0x0F, 0)      # flash bits
            distinct_outputs: set[tuple[int, int]] = set()
            for angle in range(8):
                h.put(0x1A, angle << 1)
                h.put16(0x90, 0x0800)
                h.put16(0x92, 0x0A00)
                h.call("Beast_DrawTrident", x=2)
                distinct_outputs.add((h.ram[0x0832], h.ram[0x0833]))
            self.assertEqual(len(distinct_outputs), 8, f"Expected all 8 distinct spin OAM states, got {distinct_outputs}")
        finally:
            h.close()

    # ---- Ganondorf 65816 multi-phase behavior ----
    def test_ganondorf_phase_escalation_and_phase1_parity(self) -> None:
        h = self.make_harness(0x2A)
        try:
            # 1. GanonBall_SpeedUp: owner in SprMiscD, speed in SprMiscE.
            #    Phase 1 (MiscF=9) adds +4; Phase 2 (MiscF=5) adds +5.
            h.spr("SprMiscF", 9, slot=1)   # boss in slot 1
            h.spr("SprMiscD", 1, slot=5)   # ball owner = slot 1
            h.spr("SprMiscE", 0x10, slot=5)
            h.call("GanonBall_SpeedUp", x=5)
            self.assertEqual(h.spr("SprMiscE", slot=5), 0x14, "Phase 1 SpeedUp must remain +$04")

            h.spr("SprMiscF", 5, slot=1)
            h.spr("SprMiscE", 0x10, slot=5)
            h.call("GanonBall_SpeedUp", x=5)
            self.assertEqual(h.spr("SprMiscE", slot=5), 0x15, "Phase 2/3 SpeedUp must accelerate by +$05")

            # 2. Ganondorf_SpawnStompWave: 4 diagonal shards (Phase 2) and 8 radial shards (Phase 3)
            for count in (4, 8):
                h.ram[0x0DD0:0x0DE0] = b"\x00" * 16
                h.ram[0x0DD0 + 1] = 0x09
                h.call("Ganondorf_SpawnStompWave", x=1, a=count)
                shards = [
                    s for s in range(16)
                    if s != 1 and h.ram[0x0DD0 + s] == 0x09 and h.ram[0x0E20 + s] == 0x46 and h.ram[0x0D80 + s] == 1
                ]
                self.assertEqual(len(shards), count, f"Expected {count} stomp wave shards, got {len(shards)}")

            # 3. GanonBall_SpawnReturnFlanks: spawns 2 flanking dark-magic shards (SprAction=1)
            h.ram[0x0DD0:0x0DE0] = b"\x00" * 16
            h.ram[0x0DD0 + 1] = 0x09
            h.ram[0x0DD0 + 5] = 0x09
            h.spr("SprXSpeed", 0x18, slot=5)
            h.spr("SprYSpeed", 0x00, slot=5)
            h.call("GanonBall_SpawnReturnFlanks", x=5)
            bolts = [
                s for s in range(16)
                if s not in (1, 5) and h.ram[0x0DD0 + s] == 0x09 and h.ram[0x0E20 + s] == 0x46 and h.ram[0x0D80 + s] == 1
            ]
            self.assertEqual(len(bolts), 2, f"Expected 2 twin-flank bolts, got {len(bolts)}")

            # 4. Ganondorf_SpawnAngledBat: spawns bat (Sprite_GanonBall=$46, SprAction=3),
            #    returns Carry set + bat slot in Y, and rotates velocity away from 0 Y-speed!
            h.ram[0x0DD0:0x0DE0] = b"\x00" * 16
            h.ram[0x0DD0 + 1] = 0x09
            h.call("Ganondorf_SpawnAngledBat", x=1, a=0x01)
            self.assertTrue(h.cpu.c, "Ganondorf_SpawnAngledBat must return Carry set when spawned")
            bat_slot = h.cpu.y & 0xFF
            self.assertEqual(h.ram[0x0E20 + bat_slot], 0x46)
            self.assertEqual(h.ram[0x0D80 + bat_slot], 3)
            self.assertNotEqual(h.ram[0x0D40 + bat_slot], 0, "Angled bat must have non-zero deflected Y velocity")
        finally:
            h.close()

    # ---- Ending Credits Scenes 0-7 ----
    def test_credits_rom_tables_and_scene3_castle_framing(self) -> None:
        areas_pc = snes_to_pc(self.labels["Oracle_OracleCredits_Area"])
        self.assertEqual(list(self.rom[areas_pc:areas_pc + 8]), [0x00, 0x23, 0x0E, 0x0B, 0x33, 0x1E, 0x36, 0x46])

        scroll_y_pc = snes_to_pc(self.labels["Oracle_OracleCredits_ScrollY"])
        scene3_scroll_y = int.from_bytes(self.rom[scroll_y_pc + 6:scroll_y_pc + 8], "little")
        self.assertEqual(scene3_scroll_y, 0x0300, "Scene 3 Castle scroll Y must start at $0300 to clear southern white blocks")

        gfx_pc = snes_to_pc(0x0285E2)
        self.assertEqual(list(self.rom[gfx_pc:gfx_pc + 8]), [0x06, 0x0A, 0x09, 0x28, 0x06, 0x8E, 0x08, 0x06])

    def test_credits_upload_caption_builds_valid_vram_packets_for_all_8_scenes(self) -> None:
        h = self.make_harness(0x34)
        try:
            for scene in range(8):
                h.ram[0x1000:0x1400] = b"\x00" * 0x400
                h.put(0x11, scene * 2)
                h.put(0x14, 0)
                h.call("OracleCredits_UploadCaption", db=0x34)
                self.assertEqual(h.get(0x14), 1, f"Scene {scene} must set NMI VRAM update flag $14=1")
                qsize = h.get16(0x7E1000)
                self.assertGreater(qsize, 40, f"Scene {scene} caption packet unexpectedly tiny ({qsize} bytes)")
                self.assertEqual(h.get16(0x7E1002), 0x0060, "Must clear BG3 tilemap at $6000 first")
                self.assertEqual(h.get16(0x7E1004), 0xFE47, "Must RLE-clear 1024 words")
                self.assertEqual(h.get(0x7E1002 + qsize), 0xFF, f"Scene {scene} VRAM queue missing $FF terminator")
        finally:
            h.close()

    def test_credits_patch_scene_palette_scene5_zora_and_scene7_abyss_grass(self) -> None:
        h = self.make_harness(0x34)
        try:
            # Scene 0: no custom palette override
            h.put(0x11, 0x00)
            h.put(0x15, 0)
            h.call("OracleCredits_PatchScenePalette", db=0x34)
            self.assertEqual(h.get(0x15), 0)

            # Scene 5 ($0A): loads D4 River Zora head & body palettes into OBJ rows 3 & 4
            h.put(0x11, 0x0A)
            h.put(0x15, 0)
            h.call("OracleCredits_PatchScenePalette", db=0x34)
            self.assertEqual(h.get(0x15), 1)
            expected_head = [0x0C63, 0x2525, 0x39E5, 0x46F0, 0x2F7D, 0x5B7D, 0x1ADF]
            expected_body = [0x0C63, 0x2525, 0x39E5, 0x46F0, 0x1970, 0x5B7D, 0x1ADF]
            for i, word in enumerate(expected_head):
                self.assertEqual(h.get16(0x7EC662 + i * 2), word)
            for i, word in enumerate(expected_body):
                self.assertEqual(h.get16(0x7EC682 + i * 2), word)

            # Scene 7 ($0E): patches harsh chartreuse Abyss grass to volcanic emerald-moss
            h.put(0x11, 0x0E)
            h.put(0x15, 0)
            h.call("OracleCredits_PatchScenePalette", db=0x34)
            self.assertEqual(h.get(0x15), 1)
            self.assertEqual(h.get16(0x7EC54A), 0x1143)
            self.assertEqual(h.get16(0x7EC54C), 0x1DA6)
            self.assertEqual(h.get16(0x7EC5CA), 0x1143)
            self.assertEqual(h.get16(0x7EC5CC), 0x1DA6)
            self.assertEqual(h.get16(0x7EC5CE), 0x2649)
            self.assertEqual(h.get16(0x7EC5C4), 0x2A8B)
        finally:
            h.close()

    def test_credits_draw_scene_actors_renders_on_all_8_scenes(self) -> None:
        scroll_x_pc = snes_to_pc(self.labels["Oracle_OracleCredits_ScrollX"])
        scroll_y_pc = snes_to_pc(self.labels["Oracle_OracleCredits_ScrollY"])
        pan_dir_pc = snes_to_pc(0x0E98FC)
        for scene in range(8):
            h = self.make_harness(0x0E)
            try:
                sx = int.from_bytes(self.rom[scroll_x_pc + scene * 2:scroll_x_pc + scene * 2 + 2], "little")
                sy = int.from_bytes(self.rom[scroll_y_pc + scene * 2:scroll_y_pc + scene * 2 + 2], "little")
                # Approximate mid-pan camera (32 px along pan direction)
                pdir = self.rom[pan_dir_pc + scene]
                if pdir == 0:
                    sx += 0x20
                elif pdir == 2:
                    sx -= 0x20
                elif pdir == 4:
                    sy += 0x20
                elif pdir == 6:
                    sy -= 0x20
                h.put16(0xE2, sx)
                h.put16(0xE8, sy)
                h.put(0x11, scene * 2 + 1)
                h.put(0x1A, 0x00)
                h.put16(0xC8, 0x0180)  # Scene 7 past sapling sprout threshold
                h.ram[0x0800:0x0A00] = b"\xF0" * 0x200
                h.call("OracleCredits_DrawSceneActors", long_return=True, db=0x0E)
                self.assertGreater(len(h.oam_allocs), 0, f"Scene {scene} allocated zero OAM actors")
                visible = sum(
                    1 for addr in range(0x0800, h.oam_cursor, 4)
                    if h.ram[addr + 1] != 0xF0
                )
                self.assertGreater(visible, 0, f"Scene {scene} produced zero visible OAM tiles")
            finally:
                h.close()


if __name__ == "__main__":
    unittest.main()
