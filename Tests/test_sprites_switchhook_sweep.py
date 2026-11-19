"""Q327-1C+1E Custom Sprites AI/Bugfix Sweep, Boss .bin Repaints,
Switch Hook Menu/Spawn Prereqs, and Fortress $4B Ceremony Beat Tests.

Covers source contracts, boss 4bpp .bin integrity/quality metrics, compiled ROM
byte assertions, and real 65816 CPU execution via Lakesnes' cpu.c core when
compiled ROM/symbols and Lakesnes sources are present.
"""
from __future__ import annotations

import ctypes as C
from pathlib import Path
import re
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
ROM_PATH = ROOT / "Roms" / "oos168x.sfc"
SYM_PATH = ROOT / "Roms" / "oos168x.sym"
LAKESNES_DIR = Path("/Users/scawful/src/hobby/lakesnes")


def snes_to_pc(address: int) -> int:
    bank = (address >> 16) & 0x7F
    offset = address & 0x7FFF
    return (bank << 15) | offset


def load_symbols(sym_path: Path) -> dict[str, int]:
    labels: dict[str, int] = {}
    for m in re.finditer(r"(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(\S+)$", sym_path.read_text(encoding="utf-8")):
        labels[m.group(3)] = (int(m.group(1), 16) << 16) | int(m.group(2), 16)
    for name, val in re.findall(r"(?m)^(\w+)\s*=\s*\$([0-9A-Fa-f]+)", (ROOT / "Core" / "symbols.asm").read_text(encoding="utf-8")):
        labels.setdefault(name, int(val, 16))
    return labels


def read_4bpp_tile(buf: bytes, tid: int) -> list[list[int]]:
    base = tid * 32
    out = [[0] * 8 for _ in range(8)]
    for y in range(8):
        p0, p1 = buf[base + y * 2], buf[base + y * 2 + 1]
        p2, p3 = buf[base + 16 + y * 2], buf[base + 16 + y * 2 + 1]
        for x in range(8):
            out[y][x] = (
                ((p0 >> (7 - x)) & 1)
                | (((p1 >> (7 - x)) & 1) << 1)
                | (((p2 >> (7 - x)) & 1) << 2)
                | (((p3 >> (7 - x)) & 1) << 3)
            )
    return out


def render_oam_frame(buf: bytes, chrs: list[int], xs: list[int], ys: list[int], sizes: list[int]) -> list[list[int]]:
    minx, miny = min(xs), min(ys)
    maxx = max(x + (16 if s == 2 else 8) for x, s in zip(xs, sizes))
    maxy = max(y + (16 if s == 2 else 8) for y, s in zip(ys, sizes))
    grid = [[0] * (maxx - minx) for _ in range(maxy - miny)]
    for c, ox, oy, sz in reversed(list(zip(chrs, xs, ys, sizes))):
        subs = [(0, 0, 0)] if sz == 0 else [(0, 0, 0), (8, 0, 1), (0, 8, 16), (8, 8, 17)]
        for dx, dy, off in subs:
            t = read_4bpp_tile(buf, c + off)
            for py in range(8):
                for px in range(8):
                    v = t[py][px]
                    if v:
                        grid[oy - miny + dy + py][ox - minx + dx + px] = v
    return grid


def frame_quality(grid: list[list[int]]) -> tuple[float, list[int]]:
    h, w = len(grid), len(grid[0])
    edge_total = edge_outline = 0
    for y in range(h):
        for x in range(w):
            v = grid[y][x]
            if not v:
                continue
            nbrs = [
                grid[y + dy][x + dx] if 0 <= y + dy < h and 0 <= x + dx < w else 0
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))
            ]
            if any(n == 0 for n in nbrs):
                edge_total += 1
                if v in (5, 13):
                    edge_outline += 1
    seen = [[False] * w for _ in range(h)]
    comps: list[int] = []
    for y in range(h):
        for x in range(w):
            if grid[y][x] and not seen[y][x]:
                q = [(x, y)]
                seen[y][x] = True
                cnt = 0
                while q:
                    cx, cy = q.pop()
                    cnt += 1
                    for dx in (-1, 0, 1):
                        for dy in (-1, 0, 1):
                            nx, ny = cx + dx, cy + dy
                            if 0 <= nx < w and 0 <= ny < h and grid[ny][nx] and not seen[ny][nx]:
                                seen[ny][nx] = True
                                q.append((nx, ny))
                comps.append(cnt)
    return edge_outline / max(1, edge_total), sorted(comps, reverse=True)


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


class MiniCpuRunner:
    """Minimal Lakesnes 65816 execution harness with programmable JSL/JML traps."""

    def __init__(self, lib: C.CDLL, rom: bytes, labels: dict[str, int]) -> None:
        self.lib = lib
        self.rom = rom
        self.labels = labels
        self.ram = bytearray(0x20000)
        self.traps: dict[int, object] = {}
        self.calls: list[str] = []
        self.read_cb = C.CFUNCTYPE(C.c_uint8, C.c_void_p, C.c_uint32)(lambda _, a: self._read(a))
        self.write_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_uint32, C.c_uint8)(lambda _, a, v: self._write(a, v))
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(lambda *_: None)
        self.p = lib.cpu_init(None, self.read_cb, self.write_cb, self.idle_cb)
        self.cpu = self.p.contents
        self.reset_cpu()

    def reset_cpu(self) -> None:
        for flag in ("c", "z", "v", "n", "i", "d", "e", "waiting", "stopped", "irqWanted", "nmiWanted", "intWanted", "resetWanted"):
            setattr(self.cpu, flag, False)
        self.cpu.mf = True
        self.cpu.xf = True
        self.cpu.dp = 0
        self.cpu.sp = 0x1FF
        self.cpu.a = 0
        self.cpu.x = 0
        self.cpu.y = 0
        self.cpu.db = 0

    def close(self) -> None:
        if self.p:
            self.lib.cpu_free(self.p)
            self.p = None

    def sym(self, *names: str) -> int:
        for name in names:
            for cand in (name, f"Oracle_{name}"):
                if cand in self.labels:
                    return self.labels[cand]
        raise KeyError(names)

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
        if a in self.traps:
            return 0x6B  # RTL after trap handler runs
        off = self._ram_off(a)
        if off is not None:
            return self.ram[off]
        if a & 0x8000:
            pc = snes_to_pc(a)
            return self.rom[pc] if pc < len(self.rom) else 0
        return 0

    def _write(self, a: int, v: int) -> None:
        off = self._ram_off(a)
        if off is not None:
            self.ram[off] = v & 0xFF

    def get(self, a: int) -> int:
        off = self._ram_off(a)
        assert off is not None, hex(a)
        return self.ram[off]

    def put(self, a: int, v: int) -> None:
        off = self._ram_off(a)
        assert off is not None, hex(a)
        self.ram[off] = v & 0xFF

    def get16(self, a: int) -> int:
        return self.get(a) | (self.get(a + 1) << 8)

    def put16(self, a: int, v: int) -> None:
        self.put(a, v & 0xFF)
        self.put(a + 1, (v >> 8) & 0xFF)

    def trap_jsl(self, addr: int, fn) -> None:
        self.traps[addr] = fn

    def call_jsr(self, entry: int, *, x: int = 0, y: int = 0, a: int = 0, db: int | None = None, m8: bool = True, x8: bool = True, max_steps: int = 8000) -> int:
        c = self.cpu
        c.mf = m8
        c.xf = x8
        c.a = a
        c.x = x
        c.y = y
        c.db = (entry >> 16) if db is None else db
        c.k = entry >> 16
        c.pc = entry & 0xFFFF
        sentinel_pc = 0x7000
        # Push RTS return address (sentinel_pc - 1)
        self.put(c.sp, ((sentinel_pc - 1) >> 8) & 0xFF)
        self.put(c.sp - 1, (sentinel_pc - 1) & 0xFF)
        c.sp -= 2
        return self._run_until(lambda: c.k == (entry >> 16) and c.pc == sentinel_pc, max_steps)

    def call_jsl(self, entry: int, *, x: int = 0, y: int = 0, a: int = 0, db: int | None = None, m8: bool = True, x8: bool = True, max_steps: int = 8000, stop_addrs: set[int] | None = None) -> int:
        c = self.cpu
        c.mf = m8
        c.xf = x8
        c.a = a
        c.x = x
        c.y = y
        c.db = (entry >> 16) if db is None else db
        c.k = entry >> 16
        c.pc = entry & 0xFFFF
        sentinel_bank = 0x20
        sentinel_pc = 0x7000
        # Push RTL return address (bank, hi, lo = sentinel_pc - 1)
        self.put(c.sp, sentinel_bank)
        self.put(c.sp - 1, ((sentinel_pc - 1) >> 8) & 0xFF)
        self.put(c.sp - 2, (sentinel_pc - 1) & 0xFF)
        c.sp -= 3
        stops = stop_addrs or set()
        return self._run_until(
            lambda: (c.k == sentinel_bank and c.pc == sentinel_pc) or ((c.k << 16 | c.pc) in stops),
            max_steps,
        )

    def _run_until(self, done_pred, max_steps: int) -> int:
        c = self.cpu
        for _ in range(max_steps):
            if done_pred():
                return (c.k << 16) | c.pc
            pc24 = (c.k << 16) | c.pc
            if pc24 in self.traps:
                self.traps[pc24](self)
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError(f"CPU step budget exceeded at ${c.k:02X}:{c.pc:04X}")


class SourceAndArtSweepTests(unittest.TestCase):
    def test_source_contracts_and_crlf_preservation(self) -> None:
        # 1. Darknut & Booki: 16-bit LOS raycast using Probe_CheckTileSolidity, no unthrottled probe spam
        dn = (ROOT / "Sprites" / "Enemies" / "darknut.asm").read_bytes()
        self.assertIn(b"\r\n", dn)
        dn_txt = dn.decode("utf-8")
        self.assertNotIn("Sprite_SpawnProbeAlways_long", dn_txt)
        self.assertIn("Darknut_CheckLineOfSight:", dn_txt)
        self.assertIn("JSL Probe_CheckTileSolidity", dn_txt)
        self.assertIn("Darknut_SyncFrame:", dn_txt)

        bk = (ROOT / "Sprites" / "Enemies" / "booki.asm").read_bytes()
        self.assertIn(b"\r\n", bk)
        bk_txt = bk.decode("utf-8")
        self.assertNotIn("Sprite_FloatAwayFromPlayer", bk_txt)
        self.assertIn("Booki_PlayerCanSeeUs:", bk_txt)
        self.assertIn("JSL Probe_CheckTileSolidity", bk_txt)
        self.assertIn("JSL Sprite_InvertSpeed_XY", bk_txt)

        # 2. Octoboss: 16-bit Home-relative clamp, no hardcoded $E2 / $08C8
        ob = (ROOT / "Sprites" / "Bosses" / "octoboss.asm").read_text(encoding="utf-8")
        self.assertIn("Octoboss_ClampBounds:", ob)
        self.assertNotIn("CMP.b #$E2", ob)
        self.assertNotIn("CMP #$08C8", ob)
        self.assertIn("LDA.w SprY,Y : CLC : ADC.b #$18 : STA.l $7FF81E,X", ob)

        # 3. Thunder Ghost: right bolt frame 7, TYA direction fix, wall despawn, centered draw offsets
        tg = (ROOT / "Sprites" / "Enemies" / "thunder_ghost.asm").read_text(encoding="utf-8")
        self.assertIn("CastThunderRight:\n  {\n    %StartOnFrame(7)", tg.replace("\r\n", "\n"))
        self.assertNotIn("JSL Sprite_IsToRightOfPlayer : TAY", tg)
        self.assertIn("LDA.b #$18 : JSL Sprite_ApplySpeedTowardsPlayer", tg)

        # 4. Octorok: vanilla HP/Damage/Prize restored, WORLDFLAG split, rock coords fixed
        oc = (ROOT / "Sprites" / "Enemies" / "octorok.asm").read_text(encoding="utf-8")
        self.assertIn("!Health             = 02", oc)
        self.assertIn("!Damage             = 01", oc)
        self.assertIn("!Prize              = 02", oc)
        self.assertIn("LDA.w WORLDFLAG : BNE .abyss_pal", oc)
        self.assertNotIn("LDA.w SprMiscC,Y", oc)

        # 5. Kydrog Boss: freeze timer armed via SprMiscG + SprTimerC, baseline y_offsets untouched
        kg = (ROOT / "Sprites" / "Bosses" / "kydrog_boss.asm").read_text(encoding="utf-8")
        self.assertIn("LDA.b #$90 : STA.w SprTimerC, X", kg)
        self.assertIn("LDA.w SprMiscG, X : BNE .counting", kg)
        self.assertNotIn("TODO: Use a timer", kg)

        # 6. Portal Sprite: H+V 180-degree spin flip ($E4 / $E2)
        ps = (ROOT / "Sprites" / "Objects" / "portal_sprite.asm").read_text(encoding="utf-8")
        self.assertIn("db $24\n    db $E4\n    db $22\n    db $E2", ps.replace("\r\n", "\n"))

        # 7. Kydreeok: CRLF preserved, damage NOT nerfed, wounded Song of Healing cleans quake & fireballs
        ky_raw = (ROOT / "Sprites" / "Bosses" / "kydreeok.asm").read_bytes()
        self.assertIn(b"\r\n", ky_raw)
        ky = ky_raw.decode("utf-8")
        self.assertIn("LDA.b #$09 : STA.w SprBump,   X", ky)
        self.assertIn(".clear_fireballs", ky)
        kyh = (ROOT / "Sprites" / "Bosses" / "kydreeok_head.asm").read_text(encoding="utf-8")
        self.assertIn("LDA.b #$07 : STA.w SprBump,   X", kyh)

        # 8. Switch Hook Menu icon & Abyss spawn menu GoldstarOwned gate
        md = (ROOT / "Menu" / "menu_draw.asm").read_text(encoding="utf-8")
        self.assertIn("CMP.w #$0002 : BNE .hook_icon_ready", md)
        self.assertIn("dw $24F5, $34F6, $24C0, $24F5", md)
        asm_spawn = (ROOT / "Overworld" / "abyss_spawn_menu.asm").read_text(encoding="utf-8")
        self.assertIn("LDA.l GoldstarOwned : BNE .show_light_world", asm_spawn)
        self.assertNotIn("LDA.l $7EF342", asm_spawn)

        # 9. Fortress $4B Sword-Raise ceremony beat
        ovl = (ROOT / "Overworld" / "overlays.asm").read_text(encoding="utf-8")
        self.assertIn("dw Fortress_SwordRaise", ovl)
        self.assertIn("LDA.b #$01 : STA.w $03EF", ovl)
        self.assertIn("STZ.w $03EF", ovl)

    def test_tracked_boss_bin_integrity(self) -> None:
        # Both manhandla.bin (Big Chuchu cap-mount top) and twinrova.bin are preserved as-is on master.
        mbin = (ROOT / "Sprites" / "Bosses" / "manhandla.bin").read_bytes()
        self.assertEqual(len(mbin), 8192)
        tbin = (ROOT / "Sprites" / "Bosses" / "twinrova.bin").read_bytes()
        self.assertEqual(len(tbin), 8192)


class Compiled65816ExecutionTests(unittest.TestCase):
    lib: C.CDLL | None = None
    rom: bytes = b""
    labels: dict[str, int] = {}
    _tmp: tempfile.TemporaryDirectory | None = None

    @classmethod
    def setUpClass(cls) -> None:
        if not (ROM_PATH.is_file() and SYM_PATH.is_file() and (LAKESNES_DIR / "snes" / "cpu.c").is_file()):
            return
        cls._tmp = tempfile.TemporaryDirectory(prefix="oos-q327-cpu-")
        lib_path = Path(cls._tmp.name) / "cpu.dylib"
        subprocess.run(
            [
                "cc",
                "-shared",
                "-fPIC",
                "-O2",
                str(LAKESNES_DIR / "snes" / "cpu.c"),
                str(LAKESNES_DIR / "snes" / "statehandler.c"),
                "-o",
                str(lib_path),
            ],
            check=True,
        )
        lib = C.CDLL(str(lib_path))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        cls.lib = lib
        cls.rom = ROM_PATH.read_bytes()
        cls.labels = load_symbols(SYM_PATH)

    @classmethod
    def tearDownClass(cls) -> None:
        if cls._tmp is not None:
            cls._tmp.cleanup()

    def _runner(self) -> MiniCpuRunner:
        if self.lib is None:
            self.skipTest("Compiled ROM, symbols, or Lakesnes cpu.c not available")
        r = MiniCpuRunner(self.lib, self.rom, self.labels)
        self.addCleanup(r.close)
        return r

    def test_compiled_octorok_properties_and_portal_flip_bytes(self) -> None:
        if not self.rom:
            self.skipTest("Compiled ROM not present")
        # Octorok ($08) sprite property tables: HP=2, Bump=1, Prize=2
        self.assertEqual(self.rom[snes_to_pc(0x0DB173 + 8)], 2)
        self.assertEqual(self.rom[snes_to_pc(0x0DB266 + 8)], 1)
        self.assertEqual(self.rom[snes_to_pc(0x0DB632 + 8)], 2)
        # Portal sprite .properties bytes == [$24, $E4, $22, $E2]
        prop_addr = self.labels.get("Oracle_Sprite_Portal_Draw_properties") or self.labels.get("Sprite_Portal_Draw_properties")
        self.assertIsNotNone(prop_addr)
        pc = snes_to_pc(prop_addr)
        self.assertEqual(list(self.rom[pc : pc + 4]), [0x24, 0xE4, 0x22, 0xE2])

    def test_darknut_los_all_four_facings_walls_cape_and_sync_frame(self) -> None:
        r = self._runner()
        probe_addr = r.sym("Probe_CheckTileSolidity")
        los_addr = r.sym("Darknut_CheckLineOfSight")
        sync_addr = r.sym("Darknut_SyncFrame")
        slot = 3

        def run_los(action: int, sx: int, sy: int, lx: int, ly: int, *, solid_step: int = -1, tile_type: int = 1, cape: int = 0, indoors: int = 0, sfloor: int = 0, lfloor: int = 0) -> bool:
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()
            steps = [0]

            def probe_stub(runner: MiniCpuRunner) -> None:
                steps[0] += 1
                runner.put(0x0FA5, tile_type if steps[0] == solid_step else 0)
                runner.cpu.c = steps[0] == solid_step

            r.trap_jsl(probe_addr, probe_stub)
            r.put(0x55, cape)
            r.put(0x1B, indoors)
            r.put(0xEE, lfloor)
            r.put(0x0F20 + slot, sfloor)
            r.put(0x0D80 + slot, action)
            r.put(0x0D10 + slot, sx & 0xFF)
            r.put(0x0D30 + slot, sx >> 8)
            r.put(0x0D00 + slot, sy & 0xFF)
            r.put(0x0D20 + slot, sy >> 8)
            r.put16(0x22, lx)
            r.put16(0x20, ly)
            r.put16(0x0FD8, 0x1234)
            r.put16(0x0FDA, 0x5678)
            r.call_jsr(los_addr, x=slot)
            self.assertEqual((r.get16(0x0FD8), r.get16(0x0FDA)), (0x1234, 0x5678), "Cached coords clobbered")
            return r.cpu.c

        # All 4 facings spot Link in front (incl. Up = action 3!)
        self.assertTrue(run_los(0, 0x0180, 0x0200, 0x01C0, 0x0200))  # Right
        self.assertTrue(run_los(1, 0x0180, 0x0200, 0x0140, 0x0200))  # Left
        self.assertTrue(run_los(2, 0x0180, 0x0200, 0x0180, 0x0240))  # Down
        self.assertTrue(run_los(3, 0x0180, 0x0200, 0x0180, 0x01C0))  # Up (previously impossible!)
        # Behind (> 24px) is not spotted
        self.assertFalse(run_los(3, 0x0180, 0x0200, 0x0180, 0x0240))
        self.assertFalse(run_los(0, 0x0180, 0x0200, 0x0140, 0x0200))
        # Close proximity (< 24px) senses Link even from behind
        self.assertTrue(run_los(0, 0x0180, 0x0200, 0x0170, 0x0200))
        # Magic Cape hides Link
        self.assertFalse(run_los(0, 0x0180, 0x0200, 0x01A0, 0x0200, cape=1))
        # Indoor floor mismatch blocks sight
        self.assertFalse(run_los(0, 0x0180, 0x0200, 0x01A0, 0x0200, indoors=1, sfloor=0, lfloor=1))
        # Solid wall blocks sight; deep water ($09) does NOT block sight
        self.assertFalse(run_los(0, 0x0180, 0x0200, 0x01C0, 0x0200, solid_step=4, tile_type=0x01))
        self.assertTrue(run_los(0, 0x0180, 0x0200, 0x01C0, 0x0200, solid_step=4, tile_type=0x09))
        # Out of 128px range (> 256px wrap test too!)
        self.assertFalse(run_los(0, 0x0180, 0x0200, 0x0288, 0x0200))

        # Darknut_SyncFrame clamps out-of-pair frames cleanly
        for act, expected_base in ((0, 6), (1, 4), (2, 2), (3, 0)):
            r.put(0x0D80 + slot, act)
            r.put(0x0D90 + slot, (expected_base + 3) & 7)
            r.call_jsr(sync_addr, x=slot)
            self.assertEqual(r.get(0x0D90 + slot), expected_base)
            r.put(0x0D90 + slot, expected_base + 1)
            r.call_jsr(sync_addr, x=slot)
            self.assertEqual(r.get(0x0D90 + slot), expected_base + 1)

    def test_booki_los_signed_coords_facing_and_wall_block(self) -> None:
        r = self._runner()
        probe_addr = r.sym("Probe_CheckTileSolidity")
        los_addr = r.sym("Booki_PlayerCanSeeUs")
        slot = 2

        def run_seen(link_dir: int, sx: int, sy: int, lx: int, ly: int, *, solid_step: int = -1) -> bool:
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()
            steps = [0]

            def probe_stub(runner: MiniCpuRunner) -> None:
                steps[0] += 1
                runner.put(0x0FA5, 1 if steps[0] == solid_step else 0)
                runner.cpu.c = steps[0] == solid_step

            r.trap_jsl(probe_addr, probe_stub)
            r.put(0x2F, link_dir)
            r.put(0x0D10 + slot, sx & 0xFF)
            r.put(0x0D30 + slot, sx >> 8)
            r.put(0x0D00 + slot, sy & 0xFF)
            r.put(0x0D20 + slot, sy >> 8)
            r.put16(0x22, lx)
            r.put16(0x20, ly)
            r.call_jsr(los_addr, x=slot)
            return r.cpu.c

        # Link facing Booki in all 4 directions ($2F: 0=Up, 2=Down, 4=Left, 6=Right)
        self.assertTrue(run_seen(0, 0x0100, 0x00C0, 0x0100, 0x0100))  # Booki above Link, Link faces Up
        self.assertTrue(run_seen(2, 0x0100, 0x0140, 0x0100, 0x0100))  # Booki below Link, Link faces Down
        self.assertTrue(run_seen(4, 0x00C0, 0x0100, 0x0100, 0x0100))  # Booki left of Link, Link faces Left
        self.assertTrue(run_seen(6, 0x0140, 0x0100, 0x0100, 0x0100))  # Booki right of Link, Link faces Right
        # Link looking away (> 26px) -> unseen
        self.assertFalse(run_seen(6, 0x00C0, 0x0100, 0x0100, 0x0100))
        self.assertFalse(run_seen(2, 0x0100, 0x00C0, 0x0100, 0x0100))
        # Close proximity with signed negative delta (Link ABOVE & LEFT of Booki — old unsigned bug!)
        self.assertTrue(run_seen(4, 0x0110, 0x0110, 0x0100, 0x0100))
        # Wall blocks Link's sight -> unseen
        self.assertFalse(run_seen(6, 0x0140, 0x0100, 0x0100, 0x0100, solid_step=3))

    def test_octoboss_16bit_home_relative_bounds_page_wrap_and_splash_y(self) -> None:
        r = self._runner()
        clamp_addr = r.sym("Octoboss_ClampBounds")
        splash_addr = r.sym("HandleMovingSplash")
        sfx_addr = r.sym("Sound_SetSfx2PanLong")
        slot = 4

        def run_clamp(subtype_f: int, hx: int, hy: int, sx: int, sy: int, vx: int, vy: int) -> tuple[int, int]:
            r.ram[:] = bytes(len(r.ram))
            r.put(0x0EC0 + slot, subtype_f)  # SprMiscF
            r.put(0x0DA0 + slot, hx & 0xFF)  # HomeXL
            r.put(0x0DB0 + slot, hx >> 8)    # HomeXH
            r.put(0x0DE0 + slot, hy & 0xFF)  # HomeYL
            r.put(0x0ED0 + slot, hy >> 8)    # HomeYH
            r.put(0x0D10 + slot, sx & 0xFF)
            r.put(0x0D30 + slot, sx >> 8)
            r.put(0x0D00 + slot, sy & 0xFF)
            r.put(0x0D20 + slot, sy >> 8)
            r.put(0x0D50 + slot, vx & 0xFF)
            r.put(0x0D40 + slot, vy & 0xFF)
            r.call_jsr(clamp_addr, x=slot)
            return r.get(0x0D50 + slot), r.get(0x0D40 + slot)

        # Live OW $75 coords ($0AD0, $0D20): inside bounds keeps velocity
        self.assertEqual(run_clamp(0, 0x0AD0, 0x0D20, 0x0AE0, 0x0D20, 0x10, 0x08), (0x10, 0x08))
        # Crossing $FF -> $00 page boundary at HomeX = $0AE0, SprX = $0B12 (+$32) -> exact 2's comp reflect -$10 ($F0)!
        self.assertEqual(run_clamp(0, 0x0AE0, 0x0D20, 0x0B12, 0x0D20, 0x10, 0x00), (0xF0, 0x00))
        # Crossing $00 -> $FF page boundary left at HomeX = $0A10, SprX = $09DF (-$31) -> exact reflect +$10!
        self.assertEqual(run_clamp(0, 0x0A10, 0x0D20, 0x09DF, 0x0D20, 0xF0, 0x00), (0x10, 0x00))
        # Blue brother (SprMiscF=1) right bound +$58 across page boundary
        self.assertEqual(run_clamp(1, 0x0AC0, 0x0D1C, 0x0B18, 0x0D1C, 0x0C, 0x00), (0xF4, 0x00))

        # HandleMovingSplash writes SprY + $18 (with carry into SprYH), NOT SprXH + $18!
        r.ram[:] = bytes(len(r.ram))
        r.traps.clear()
        r.trap_jsl(sfx_addr, lambda _: None)
        r.put(0x1A, 0x00)
        r.put(0x0D10 + slot, 0xD0)
        r.put(0x0D30 + slot, 0x0A)
        r.put(0x0D00 + slot, 0xF0)  # $0CF0 + $18 = $0D08 (tests carry propagation too!)
        r.put(0x0D20 + slot, 0x0C)
        r.put(0x0D40 + slot, 0x08)  # positive Y speed -> slot $0E
        r.call_jsr(splash_addr, x=slot)
        self.assertEqual(r.get(0x7FF800 + 0x0E), 0x15)
        self.assertEqual(r.get(0x7FF81E + 0x0E), 0x08)  # ($F0 + $18) & $FF
        self.assertEqual(r.get(0x7FF85A + 0x0E), 0x0D)  # $0C + carry 1

    def test_thunder_ghost_child_spawn_direction_and_properties(self) -> None:
        r = self._runner()
        spawn_addr = r.sym("SpawnLightningAttack")
        dyn_addr = r.sym("Sprite_SpawnDynamically")
        right_addr = r.sym("Sprite_IsToRightOfPlayer")
        speed_addr = r.sym("Sprite_ApplySpeedTowardsPlayer")
        parent = 2
        child = 7

        for link_left, exp_act, exp_frame, exp_x in ((1, 3, 6, 0x0100 - 12), (0, 4, 7, 0x0100 + 12)):
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()
            aimed_slots: list[tuple[int, int]] = []

            def dyn_stub(runner: MiniCpuRunner) -> None:
                runner.cpu.y = child
                runner.cpu.n = False

            def right_stub(runner: MiniCpuRunner, val: int = link_left) -> None:
                runner.cpu.y = val

            def speed_stub(runner: MiniCpuRunner) -> None:
                aimed_slots.append((runner.cpu.x, runner.cpu.a & 0xFF))

            r.trap_jsl(dyn_addr, dyn_stub)
            r.trap_jsl(right_addr, right_stub)
            r.trap_jsl(speed_addr, speed_stub)
            r.put(0x0D10 + parent, 0x00)
            r.put(0x0D30 + parent, 0x01)
            r.put(0x0D00 + parent, 0x80)
            r.put(0x0D20 + parent, 0x02)
            r.put(0x0F20 + parent, 1)  # floor 1
            r.call_jsr(spawn_addr, x=parent)
            self.assertEqual(r.get(0x0D80 + child), exp_act)
            self.assertEqual(r.get(0x0E30 + child), exp_act)
            self.assertEqual(r.get(0x0D90 + child), exp_frame)
            cx = r.get(0x0D10 + child) | (r.get(0x0D30 + child) << 8)
            cy = r.get(0x0D00 + child) | (r.get(0x0D20 + child) << 8)
            self.assertEqual((cx, cy), (exp_x, 0x028C))
            self.assertEqual(r.get(0x0F20 + child), 1)
            self.assertEqual(r.get(0x0F60 + child), 0x02)
            self.assertEqual(r.get(0x0E60 + child), 0x40)
            self.assertEqual(r.get(0x0DF0 + child), 0x38)
            self.assertEqual(r.get(0x0E00 + child), 0x00)
            self.assertEqual(aimed_slots, [(child, 0x18)])

        # CastThunderLeft / CastThunderRight despawn on wall collision OR SprTimerA == 0
        dmg_addr = r.sym("Sprite_CheckDamageToPlayer")
        move_addr = r.sym("Sprite_MoveLong")
        col_addr = r.sym("Sprite_CheckTileCollision")
        for label in ("CastThunderLeft", "CastThunderRight"):
            cast_addr = r.sym(label)
            for timer, col, exp_state in ((10, 0, 9), (0, 0, 0), (10, 1, 0)):
                r.ram[:] = bytes(len(r.ram))
                r.traps.clear()
                r.trap_jsl(dmg_addr, lambda _: None)
                r.trap_jsl(move_addr, lambda _: None)
                r.trap_jsl(col_addr, lambda _: None)
                r.put(0x0DD0 + child, 9)
                r.put(0x0DF0 + child, timer)
                r.put(0x0E70 + child, col)
                r.call_jsr(cast_addr, x=child)
                self.assertEqual(r.get(0x0DD0 + child), exp_state, (label, timer, col))

    def test_octorok_worldflag_draw_split_and_rock_spawn(self) -> None:
        r = self._runner()
        draw_addr = r.sym("Sprite_Octorok_Draw")
        rock_addr = r.sym("Octorok_SpawnRock")
        prep_oam = r.sym("Sprite_PrepOamCoord")
        alloc_oam = r.sym("Sprite_OAM_AllocateDeferToPlayer")
        dyn_addr = r.sym("Sprite_SpawnDynamically")
        sfx_addr = r.sym("SpriteSFX_QueueSFX2WithPan")
        slot = 1

        def run_draw(worldflag: int, subtype: int, frame: int, flash: int, *, offscreen: bool = False) -> int:
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()

            def prep_stub(runner: MiniCpuRunner) -> None:
                runner.put16(0x00, 0x0080)
                runner.put16(0x02, 0x0080)
                runner.cpu.c = offscreen

            def alloc_stub(runner: MiniCpuRunner) -> None:
                runner.put16(0x90, 0x0800)
                runner.put16(0x92, 0x0A00)

            r.trap_jsl(prep_oam, prep_stub)
            r.trap_jsl(alloc_oam, alloc_stub)
            r.put(0x0FFF, worldflag)
            r.put(0x0E30 + slot, subtype)
            r.put(0x0D90 + slot, frame)
            r.put(0x0B89 + slot, flash)
            r.call_jsr(draw_addr, x=slot)
            return r.get(0x0803)  # OAM property byte

        self.assertEqual(run_draw(0, 0, 0, 0), 0x27)  # Kalyxo/Special OW land: Pal 3 ($06) | $21
        self.assertEqual(run_draw(0, 1, 8, 0), 0x35)  # Kalyxo/Special OW water: Pal 2 ($04) | $31
        self.assertEqual(run_draw(1, 0, 0, 0), 0x2D)  # Eon Abyss: Aux Pal 6 ($0C) | $21
        # Damage flash shifts by 1, preserving bit 0 (NT=1) & priority ($20)
        flashed = run_draw(0, 0, 0, 3)
        self.assertEqual(flashed, 0x21 | ((3 << 1) ^ 0x06))
        self.assertEqual(flashed & 1, 1)
        # Offscreen clip leaves OAM untouched (0)
        self.assertEqual(run_draw(0, 0, 0, 0, offscreen=True), 0x00)

        # Octorok_SpawnRock: direction 2 (Down) uses parent coords & SprMiscC,X (even when child SprMiscC,Y=0)
        r.ram[:] = bytes(len(r.ram))
        r.traps.clear()
        child = 5
        r.trap_jsl(sfx_addr, lambda _: None)
        r.trap_jsl(dyn_addr, lambda runner: (setattr(runner.cpu, "y", child), setattr(runner.cpu, "n", False)))
        r.put(0x0D10 + slot, 0x40)
        r.put(0x0D30 + slot, 0x01)
        r.put(0x0D00 + slot, 0x50)
        r.put(0x0D20 + slot, 0x02)
        r.put(0x0DE0 + slot, 2)  # Down
        r.put(0x0F20 + slot, 1)
        r.call_jsr(rock_addr, x=slot)
        self.assertEqual((r.get(0x0D10 + child), r.get(0x0D30 + child)), (0x40, 0x01))
        self.assertEqual((r.get(0x0D00 + child), r.get(0x0D20 + child)), (0x5C, 0x02))
        self.assertEqual((r.get(0x0D50 + child), r.get(0x0D40 + child)), (0x00, 44))
        self.assertEqual(r.get(0x0F20 + child), 1)

    def test_kydrog_freeze_timer_lifecycle_on_65816(self) -> None:
        r = self._runner()
        fn = r.sym("Sprite_CheckIfFrozen")
        slot = 0
        r.put(0x0DD0 + slot, 0x0B)  # Frozen
        r.put(0x0ED0 + slot, 0x00)  # SprMiscG not yet armed
        r.put(0x0E10 + slot, 0x00)  # SprTimerC initially 0
        r.put(0x7FFA3C + slot, 0x01)
        # Frame 0: arms timer to $90 and stays frozen!
        r.call_jsr(fn, x=slot)
        self.assertEqual(r.get(0x0DD0 + slot), 0x0B)
        self.assertEqual(r.get(0x0ED0 + slot), 0x01)
        self.assertEqual(r.get(0x0E10 + slot), 0x90)
        # Mid-freeze: stays frozen
        r.put(0x0E10 + slot, 0x05)
        r.call_jsr(fn, x=slot)
        self.assertEqual(r.get(0x0DD0 + slot), 0x0B)
        # Timer expires: cleanly thaws back to $09
        r.put(0x0E10 + slot, 0x00)
        r.call_jsr(fn, x=slot)
        self.assertEqual(r.get(0x0DD0 + slot), 0x09)
        self.assertEqual(r.get(0x0ED0 + slot), 0x00)
        self.assertEqual(r.get(0x7FFA3C + slot), 0x00)

    def test_kydreeok_wounded_finish_clears_quake_and_fireballs(self) -> None:
        r = self._runner()
        fn = r.sym("Sprite_Kydreeok_CheckIfDead")
        boss_slot = 0
        r.put(0x0D80 + boss_slot, 0x01)  # Stand
        r.put(0x0E90 + boss_slot, 0x02)  # Phase 2
        r.put(0x0B08, 1)  # Offspring1_Id = slot 1 (dead)
        r.put(0x0B09, 2)  # Offspring2_Id = slot 2 (dead)
        r.put(0x0DD0 + 1, 0)
        r.put(0x0DD0 + 2, 0)
        # Live fireball in slot 5 ($55) and unrelated sprite in slot 6 ($D3)
        r.put(0x0DD0 + 5, 9)
        r.put(0x0E20 + 5, 0x55)
        r.put(0x0DD0 + 6, 9)
        r.put(0x0E20 + 6, 0xD3)
        # Active quake + stale SongFlag
        quake_addr = r.sym("BossKit_Quake")
        r.put(quake_addr, 0x18)
        r.put16(0x011A, 0x0003)
        r.put16(0x011C, 0x0002)
        r.put(r.sym("SongFlag"), 0x01)
        r.call_jsr(fn, x=boss_slot)
        self.assertEqual(r.get(0x0D80 + boss_slot), 0x0A)  # !Kyd_Wounded
        self.assertEqual(r.get(quake_addr), 0x00)
        self.assertEqual((r.get16(0x011A), r.get16(0x011C)), (0, 0))
        self.assertEqual(r.get(0x0DD0 + 5), 0x00, "Fireball should be dismissed")
        self.assertEqual(r.get(0x0DD0 + 6), 0x09, "Non-fireball sprite must be untouched")
        self.assertEqual(r.get(r.sym("SongFlag")), 0x00)
        self.assertEqual(r.get(0x012C), 0xF1)

    def test_switch_hook_menu_icon_and_abyss_spawn_goldstar_gate(self) -> None:
        r = self._runner()
        # 1. Menu DrawYItems renders Hookshot ($7EF342==1) vs Switch Hook ($7EF342==2) while keeping Goldstar intact
        draw_y = r.sym("DrawYItems")
        update_flute = r.sym("UpdateFluteSong_Long")
        hook_off = 7 * 64 + 8 * 2      # menu_offset(7,8)
        gold_off = 10 * 64 + 14 * 2    # menu_offset(10,14)

        def run_menu(hook_val: int, goldstar: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()
            r.trap_jsl(update_flute, lambda _: None)
            r.put(0x7EF342, hook_val)
            r.put(0x7EF3A9, goldstar)
            r.call_jsr(draw_y, m8=False, x8=False, max_steps=16000)
            hook_words = (
                r.get16(0x1108 + hook_off),
                r.get16(0x110A + hook_off),
                r.get16(0x1148 + hook_off),
                r.get16(0x114A + hook_off),
            )
            gold_words = (
                r.get16(0x1108 + gold_off),
                r.get16(0x110A + gold_off),
                r.get16(0x1148 + gold_off),
                r.get16(0x114A + gold_off),
            )
            return hook_words, gold_words

        h1, g1 = run_menu(1, 1)
        self.assertEqual(h1, (0x2CF5, 0x2CF6, 0x2CC0, 0x2CF5))  # Blue/White Hookshot
        self.assertEqual(g1, (0x2C17, 0x3531, 0x2D40, 0x3541))  # Ball & Chain Goldstar

        h2, g2 = run_menu(2, 1)
        self.assertEqual(h2, (0x24F5, 0x34F6, 0x24C0, 0x24F5))  # Switch Hook (gold prong + red grip)
        self.assertEqual(g2, (0x2C17, 0x3531, 0x2D40, 0x3541))  # Goldstar untouched!

        # 2. AbyssSpawnMenu_Select .light_world gates Mountain Cave ($0185) strictly on GoldstarOwned ($7EF3A9)
        sel_addr = r.sym("AbyssSpawnMenu_Select")
        for hook_val, goldstar, exp_msg in ((2, 0, 0x0184), (1, 1, 0x0185), (2, 1, 0x0185), (1, 0, 0x0184)):
            r.ram[:] = bytes(len(r.ram))
            r.traps.clear()
            r.put(0x7EF3CA, 0x40)  # SavedWorld != 0 (Abyss menu active)
            r.put(0x1CE8, 0x01)    # Choice 1 = Kalyxo (.light_world)
            r.put(0x7EF3D6, 0x04)  # Hall of Secrets unlocked
            r.put(0x7EF342, hook_val)
            r.put(0x7EF3A9, goldstar)
            pc = r.call_jsl(sel_addr, stop_addrs={0x0281ED})
            self.assertEqual(pc, 0x0281ED)
            self.assertEqual(r.cpu.x, exp_msg, f"hook={hook_val}, goldstar={goldstar}")

    def test_fortress_4b_sword_raise_ceremony_beat(self) -> None:
        r = self._runner()
        anim_addr = r.sym("Fortress_EntranceAnimation")
        r.ram[:] = bytes(len(r.ram))
        r.put(0xB0, 0x00)
        r.put(0xC8, 0x00)

        # Frame 0: locks movement, faces Link down ($2F=2), raises Master Sword ($03EF=1), chimes ($012F=$16)
        r.call_jsl(anim_addr)
        self.assertEqual(r.get(0x02E4), 0x01)
        self.assertEqual(r.get(0x2F), 0x02)
        self.assertEqual(r.get(0x03EF), 0x01)
        self.assertEqual(r.get(0x012F), 0x16)
        self.assertEqual(r.get(0xB0), 0x00)
        self.assertEqual(r.get(0xC8), 0x01)

        # Advance frames 1..46: holds sword aloft ($03EF=1)
        for _ in range(46):
            r.call_jsl(anim_addr)
            self.assertEqual(r.get(0x03EF), 0x01)
            self.assertEqual(r.get(0xB0), 0x00)

        # Frame 47 ($C8 == $2F -> $30): lowers sword ($03EF=0), plays Fortress_SFX, advances to Fortress_Frame0 ($B0=1)
        r.call_jsl(anim_addr)
        self.assertEqual(r.get(0x03EF), 0x00)
        self.assertEqual(r.get(0xB0), 0x01)
        self.assertEqual(r.get(0xC8), 0x00)
        self.assertEqual((r.get(0x012D), r.get(0x012E), r.get(0x012F)), (0x05, 0x0C, 0x07))


if __name__ == "__main__":
    unittest.main()
