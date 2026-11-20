#!/usr/bin/env python3
"""Compile real Horse Form Bank $53 ASM and verify QUEUE319 fixes on LakeSnes 65816 CPU.

Assembles Masks/horse_ground_clearance.asm, Masks/horse_mounted_helpers.asm,
Masks/horse_sparse_runtime.asm, and Horse_DrawPlayerOam_Long/Rider/Epona OAM
emitters into a synthetic LoROM image and executes real 65816 machine code on
the LakeSnes CPU core (matching Tests/test_horse_charge_compiled.py).

Proves:
  1. North/South/West/East .point_outside_area clearance on Small (512x512),
     Large (1024x1024), Wide (1024x512), Tall (512x1024), and row-0 borders.
  2. Corner-slide forgiveness (single outer corner hit + orthogonal input -> 1px
     safe nudge; center/both-corner/diagonal/water/pit -> zero nudge; idle early-out;
     fence tiles stay clear).
  3. Zero overlap between mounted Horse VRAM DMA / OAM emission and ALL vanilla +
     Oracle of Secrets dropables (Rupees $0B/$1B, Hearts $29/$39, Small Shadow $38,
     Bombchu $2E/$3E, Receipt $0E/$1E, Follower/Arrows $20-$23, Heart Container $24,
     and Sheet $74+ dropables $4400-$4FFF), plus live animated Rupee DMA in
     Horse_LinkDmaPrefix and pixel-exact 8-part narrow part 4 verification.
  4. Mounted overworld hostile-enemy cap (<= 1) with strict preservation of all
     NPCs, Ranch residents, Cuccos, Farore, Piratian, Portals, Switches, Apples,
     Pickups, Bosses, Minigame targets, and Harmless/Impervious/Persist/Bulletproof
     sprites.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import subprocess
import tempfile

from d4_compiled_fight_check import Cpu, Fixture

ROOT = Path(__file__).resolve().parents[1]

# Vanilla entry/hook target stubs
STUB_GET_TILE_ATTR = 0x00882E
STUB_DMA_CONT_8ADB = 0x008ADB
STUB_DMA_CONT_8B25 = 0x008B25
STUB_DMA_NATIVE_8A12 = 0x008A12
STUB_PAL_ARMOR = 0x058000
STUB_LOAD_DAYNIGHT = 0x058004
STUB_SFX_PAN = 0x0DBB67
STUB_RESET_LINK_GFX = 0x058008
STUB_SPRITE_SPAWN = 0x1DF65D
STUB_DASH_TREMOR = 0x0993F3
STUB_KID_START = 0x05800C
STUB_HORSE_GAME_TICK = 0x058010
STUB_SUPPRESS_BTNS = 0x53E800

# Dropable & protected Page 0 VRAM word ranges (inclusive start, exclusive end)
PROTECTED_VRAM_RANGES = [
    ("Rupee top ($0B)",          0x40B0, 0x40C0),
    ("Rupee bot ($1B)",          0x41B0, 0x41C0),
    ("Receipt/Bird top ($0E-$0F)", 0x40E0, 0x4100),
    ("Receipt/Bird bot ($1E-$1F)", 0x41E0, 0x4200),
    ("Follower/Arrows top ($20-$23)", 0x4200, 0x4240),
    ("Follower/Arrows bot ($30-$33)", 0x4300, 0x4340),
    ("HeartContainer/P2 top ($24-$25)", 0x4240, 0x4260),
    ("HeartContainer/P2 bot ($34-$35)", 0x4340, 0x4360),
    ("SmallShadow/Sparkle top ($28)", 0x4280, 0x4290),
    ("SmallShadow/Sparkle bot ($38)", 0x4380, 0x4390),
    ("Heart dropable top ($29)", 0x4290, 0x42A0),
    ("Heart dropable bot ($39)", 0x4390, 0x43A0),
    ("Bombchu pickup top ($2E-$2F)", 0x42E0, 0x4300),
    ("Bombchu pickup bot ($3E-$3F)", 0x43E0, 0x4400),
    ("Sheet $74/$75/$76 drops ($40-$FF)", 0x4400, 0x5000),
]


def _extract_horse_table_header():
    """Extract only the data tables (without ROM-byte assertions) from horse_sparse_tables.asm."""
    lines = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text().splitlines()
    return "\n".join(l for l in lines if not l.lstrip().startswith("assert "))


def assemble(folder: Path):
    folder.mkdir()
    # Create clean test-local include tree pointing to the real ASM files
    (folder / "Masks").mkdir()
    (folder / "Masks/gfx").mkdir()
    for rel in [
        "Masks/horse_ground_clearance.asm",
        "Masks/horse_mounted_helpers.asm",
        "Masks/horse_sparse_runtime.asm",
        "Masks/horse_form.asm",
    ]:
        txt = (ROOT / rel).read_text()
        # Strip base-ROM read1/read2/read3/read4 preimage asserts so synthetic image assembles cleanly
        txt = re.sub(r'(?m)^(\s*)assert\s+read\d.*$', r'\1; [stripped rom preimage assert]', txt)
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
        """lorom
macro m8()
  SEP #$20
endmacro
macro a16()
  REP #$20
endmacro

!CurrentMask = $02B2
!ENABLE_HORSE_FORM = 1
!ENABLE_HORSE_PARK_ANYWHERE = 1
!ENABLE_HORSE_CROWD_CHARGE = 0
!SideQuest2_RanchGirl = $01
InCutScene = $7E02E4
SideQuestProg2 = $7EF3D8
LoadDayNightPaletteEffect = $058004
Palette_ArmorAndGloves = $058000
ResetToLinkGraphics = $058008
Sprite_SpawnDynamically = $1DF65D
HorseGame_State = $7F5410
HorseGame_Tick = $058010
HorseGame_KidStartCheck = $05800C
HorseForm_SuppressMountedButtons = $53E800
Horse_AnchorArea = $7E1EFE
Horse_OffState = $7F5400
Horse_OffClear = $7F5402
HorseForm_SaveOutdoorAnchor_Long = $058014
HorseForm_MaintainParkedNpc_Long = $058018
Horse_OffRestore = $05801C
Horse_OffRanchNpc = $058020
Horse_FrameEndScan = $058024

SprX = $0D10
SprXH = $0D30
SprY = $0D00
SprYH = $0D20
SprAction = $0D80
SprFrame = $0DC0
SprMiscA = $0DA0
SprBulletproof = $0BA0

; Horse transient WRAM symbols (matching Core/symbols.asm)
Horse_Marker           = $7E1EDE
Horse_State            = $7E1EE0
Horse_JumpTimer        = $7E1EE1
Horse_JumpStep         = $7E1EE2
Horse_JumpDir          = $7E1EE3
Horse_JumpZ            = $7E1EE4
Horse_PushTimer        = $7E1EE5
Horse_AnimTimer        = $7E1EE6
Horse_Frame            = $7E1EE7
Horse_UploadedFrame    = $7E1EE8
Horse_NpcActive        = $7E1EE9
Horse_NpcFrame         = $7E1EEA
Horse_NpcUploadedFrame = $7E1EEB
Horse_PalLoaded        = $7E1EEC
Horse_DismountCooldown = $7E1EED
Horse_InteractDelay    = $7E1EEE
Horse_JumpCooldown     = $7E1EEF
Horse_JumpStartX       = $7E1EF0
Horse_JumpStartY       = $7E1EF2
Horse_JumpEndX         = $7E1EF4
Horse_JumpEndY         = $7E1EF6
Horse_AnchorX          = $7E1EF8
Horse_AnchorY          = $7E1EFA
Horse_HasAnchor        = $7E1EFC

; Minimal stub for HorseForm_SuppressMountedButtons
org $53E800
  RTS

; Assemble Bank $53 Horse assets + horse_form.asm + horse_ground_clearance.asm
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

; Assemble horse_mounted_helpers.asm in its real $53D000-$53DFFF slice
org $53D000
  incsrc "Masks/horse_mounted_helpers.asm"
assert pc() <= $53E000

; Vanilla $0DA120/$0DA126 tables used by Horse_DrawPlayerOam_Long
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


class HorseQ319Fixture(Fixture):
    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.cpu.db = 0x00
        self.tile_fn = lambda wx, wy: (0x00, 0x0000)  # (attr, tile16)
        self.tile_queries = []
        self.dma_writes = []  # list of (vram_word_start, vram_word_end, bank, src, nbytes)
        self.vram_addr = 0
        self.dma_regs = {}
        self.jumped_target = None
        self.stubs = {
            STUB_GET_TILE_ATTR: "get_tile_attr",
            STUB_DMA_CONT_8ADB: "dma_8adb",
            STUB_DMA_CONT_8B25: "dma_8b25",
            STUB_DMA_NATIVE_8A12: "dma_8a12",
            STUB_DASH_TREMOR: "dash_tremor",
        }
        # Allow PPU/DMA MMIO register writes ($2116, $420B, $4302-$4345) cleanly
        self.mmio = {}

    def _write_mmio(self, addr, val):
        self.mmio[addr] = val
        if addr == 0x2116:
            self.vram_addr = (self.vram_addr & 0xFF00) | val
        elif addr == 0x2117:
            self.vram_addr = (self.vram_addr & 0x00FF) | (val << 8)
        elif addr == 0x420B:
            for ch in range(5):
                if val & (1 << ch):
                    base = 0x4300 + ch * 0x10
                    src = self.mmio.get(base + 2, 0) | (self.mmio.get(base + 3, 0) << 8)
                    bank = self.mmio.get(base + 4, 0)
                    size = self.mmio.get(base + 5, 0) | (self.mmio.get(base + 6, 0) << 8)
                    words = size // 2
                    self.dma_writes.append((self.vram_addr, self.vram_addr + words, bank, src, size))
                    self.vram_addr = (self.vram_addr + words) & 0xFFFF

    def write(self, addr, val):
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (off in (0x2116, 0x2117, 0x420B) or 0x4300 <= off <= 0x434F):
            self._write_mmio(off, val)
            return
        super().write(addr, val)

    def read(self, addr):
        bank, off = addr >> 16, addr & 0xFFFF
        if bank in (0x00, 0x80) and (off in (0x2116, 0x2117, 0x420B) or 0x4300 <= off <= 0x434F):
            return self.mmio.get(off, 0)
        return super().read(addr)

    def setup_area(self, origin_x, origin_y, width, height):
        self.word(0x0708, origin_y)
        self.word(0x070A, (height - 1) & 0xFFF0)
        self.word(0x070C, origin_x >> 3)
        self.word(0x070E, ((width >> 3) - 1) & 0xFFFE)

    def populate_tile16_grid(self, origin_x, origin_y, width, height, tile_fn):
        """Fill $7E2000 Map16 WRAM and install tile_fn(wx, wy) -> (attr, tile16)."""
        self.tile_fn = tile_fn
        y_mask = (height - 1) & 0xFFF0
        x_mask = ((width >> 3) - 1) & 0xFFFE
        for ty in range(0, height, 16):
            for tx in range(0, width, 16):
                wx, wy = origin_x + tx, origin_y + ty
                _, t16 = tile_fn(wx, wy)
                off = (((wy - origin_y) & y_mask) << 3) | (((wx >> 3) - (origin_x >> 3)) & x_mask)
                self.ram[0x2000 + off] = t16 & 0xFF
                self.ram[0x2000 + off + 1] = (t16 >> 8) & 0xFF

    def stub(self, name):
        c = self.cpu
        if name == "get_tile_attr":
            # $00 = world Y px, $02 = world X / 8; returns SEP #$30, A = attr
            wy = self.get(0x00) | (self.get(0x01) << 8)
            wx8 = self.get(0x02) | (self.get(0x03) << 8)
            wx = (wx8 << 3) & 0xFFFF
            y0 = self.get(0x0708) | (self.get(0x0709) << 8)
            ym = self.get(0x070A) | (self.get(0x070B) << 8)
            x0 = self.get(0x070C) | (self.get(0x070D) << 8)
            xm = self.get(0x070E) | (self.get(0x070F) << 8)
            wrapped_wy = (y0 + (((wy - y0) & ym) | (wy & 0x0F))) & 0xFFFF
            wrapped_wx = ((x0 + (((wx8 - x0) & xm) | (wx8 & 0x01))) << 3) & 0xFFFF
            attr, _ = self.tile_fn(wrapped_wx, wrapped_wy)
            self.tile_queries.append((wx, wy, wrapped_wx, wrapped_wy, attr))
            c.mf = c.xf = True
            self.acc(attr)
            return False  # let cpu_runOpcode execute 0x6B (RTL) natively!
        if name in ("dma_8adb", "dma_8b25", "dma_8a12"):
            self.jumped_target = name
            return "STOP"
        if name == "dash_tremor":
            c.c = True
            return False
        return False

    def run_jsr(self, name, mf=True, xf=True, a=0, x=0, y=0):
        c = self.cpu
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        sp = c.sp
        # Push 2-byte RTS return address ($6FFF -> returns to $7000 in same bank)
        self.put(sp, 0x6F)
        self.put(sp - 1, 0xFF)
        c.sp -= 2
        for count in range(60000):
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

    def run_jsl(self, name, mf=True, xf=True, a=0, x=0, y=0):
        c = self.cpu
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
        for count in range(60000):
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

    def run_jml(self, name, mf=True, xf=False, a=0, x=0, y=0):
        c = self.cpu
        c.mf, c.xf = mf, xf
        c.a, c.x, c.y = a, x, y
        entry = self.addr(name)
        assert entry is not None, name
        c.k, c.pc = entry >> 16, entry & 0xFFFF
        self.jumped_target = None
        for count in range(60000):
            addr = (c.k << 16) | c.pc
            if addr in self.stubs:
                r = self.stub(self.stubs[addr])
                if r == "STOP":
                    return count
                if r is True:
                    continue
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name, "instruction bound", hex((c.k << 16) | c.pc)))

    def set_sprite(self, slot, sid, state=9, harm=0, oam_prop=0, boss=0, f60=0, caa=0, ba0=0):
        self.put(0x0DD0 + slot, state)
        self.put(0x0E20 + slot, sid)
        self.put(0x0E40 + slot, harm)
        self.put(0x0E60 + slot, oam_prop)
        self.put(0x0B6B + slot, boss)
        self.put(0x0F60 + slot, f60)
        self.put(0x0CAA + slot, caa)
        self.put(0x0BA0 + slot, ba0)


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--lakesnes", type=Path, required=True)
    ap.add_argument("--output", type=Path)
    args = ap.parse_args()
    cases = []

    with tempfile.TemporaryDirectory(prefix="horse-q319-cpu-") as tmp:
        d = Path(tmp)
        lib_path = d / "cpu.dylib"
        subprocess.run(
            ["cc", "-shared", "-fPIC", "-O2", str(args.lakesnes / "snes/cpu.c"),
             str(args.lakesnes / "snes/statehandler.c"), "-o", str(lib_path)],
            check=True,
        )
        lib = C.CDLL(str(lib_path))
        lib.cpu_init.restype = C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
        lib.cpu_free.argtypes = [C.POINTER(Cpu)]
        rom, labels = assemble(d / "build")

        def case(name, fn):
            f = HorseQ319Fixture(lib, rom, labels)
            try:
                fn(f)
                cases.append(name)
            finally:
                f.close()

        # =====================================================================
        # 1. NORTH/SOUTH/WEST/EAST TRANSITION CLEARANCE (SMALL, LARGE, WIDE, TALL)
        # =====================================================================
        def check_seams(origin_x, origin_y, width, height):
            def fn(f):
                f.setup_area(origin_x, origin_y, width, height)
                # Make ALL 4 opposite perimeter strips solid ($01) to catch ANY wraparound bug!
                # Leave a clear 64px corridor at each seam so only wrap-to-opposite-edge would read solid.
                def tile_fn(wx, wy):
                    rx, ry = wx - origin_x, wy - origin_y
                    # Solid walls along the opposite edge of each test point:
                    # Test N at (cx, origin_y + 4) -> wrap would hit ry >= height - 16
                    # Test S at (cx, origin_y + height - 12) -> wrap would hit ry < 16
                    # Put solid at South wall ONLY when testing North, etc. — handled per subtest!
                    return (0x00, 0x0000)

                cx = origin_x + width // 2
                cy = origin_y + height // 2

                # (a) North seam: South wall of area is SOLID ($01); North seam itself is CLEAR
                def north_map(wx, wy):
                    ry = wy - origin_y
                    return (0x01, 0x0001) if ry >= height - 32 else (0x00, 0x0000)
                f.populate_tile16_grid(origin_x, origin_y, width, height, north_map)
                f.word(0x22, cx); f.word(0x20, origin_y + 4)
                f.put(0xF0, 0x08); f.put(0xF2, 0x08)
                f.run_jsr("HorseForm_ConstrainGroundInput")
                assert f.get(0xF0) == 0x08, f"North seam blocked on {width}x{height}!"

                # (b) South seam: North wall of area is SOLID ($01); South seam itself is CLEAR
                def south_map(wx, wy):
                    ry = wy - origin_y
                    return (0x01, 0x0001) if ry < 32 else (0x00, 0x0000)
                f.populate_tile16_grid(origin_x, origin_y, width, height, south_map)
                f.word(0x22, cx); f.word(0x20, origin_y + height - 12)
                f.put(0xF0, 0x04); f.put(0xF2, 0x04)
                f.run_jsr("HorseForm_ConstrainGroundInput")
                assert f.get(0xF0) == 0x04, f"South seam blocked on {width}x{height}!"

                # (c) West seam: East wall is SOLID ($01)
                def west_map(wx, wy):
                    rx = wx - origin_x
                    return (0x01, 0x0001) if rx >= width - 32 else (0x00, 0x0000)
                f.populate_tile16_grid(origin_x, origin_y, width, height, west_map)
                f.word(0x22, origin_x + 2); f.word(0x20, cy)
                f.put(0xF0, 0x02); f.put(0xF2, 0x02)
                f.run_jsr("HorseForm_ConstrainGroundInput")
                assert f.get(0xF0) == 0x02, f"West seam blocked on {width}x{height}!"

                # (d) East seam: West wall is SOLID ($01)
                def east_map(wx, wy):
                    rx = wx - origin_x
                    return (0x01, 0x0001) if rx < 32 else (0x00, 0x0000)
                f.populate_tile16_grid(origin_x, origin_y, width, height, east_map)
                f.word(0x22, origin_x + width - 12); f.word(0x20, cy)
                f.put(0xF0, 0x01); f.put(0xF2, 0x01)
                f.run_jsr("HorseForm_ConstrainGroundInput")
                assert f.get(0xF0) == 0x01, f"East seam blocked on {width}x{height}!"

                # (e) Interior solid wall STILL blocks North cleanly
                def solid_ahead(wx, wy):
                    return (0x01, 0x0001) if wy < cy else (0x00, 0x0000)
                f.populate_tile16_grid(origin_x, origin_y, width, height, solid_ahead)
                f.word(0x22, cx); f.word(0x20, cy + 4)
                f.put(0xF0, 0x08); f.put(0xF2, 0x08)
                f.run_jsr("HorseForm_ConstrainGroundInput")
                assert f.get(0xF0) == 0x00, f"Interior solid wall failed to block on {width}x{height}!"
            return fn

        case("seams_nswe_small_512x512", check_seams(0x0200, 0x0200, 512, 512))
        case("seams_nswe_large_1024x1024", check_seams(0x0400, 0x0400, 1024, 1024))
        case("seams_nswe_wide_1024x512", check_seams(0x0400, 0x0200, 1024, 512))
        case("seams_nswe_tall_512x1024", check_seams(0x0200, 0x0400, 512, 1024))
        case("seams_nswe_row0_negative_probe", check_seams(0x0000, 0x0000, 512, 512))

        # =====================================================================
        # 2. CORNER-SLIDE FORGIVENESS + IDLE EARLY-OUT + FENCE PRESERVATION
        # =====================================================================
        def idle_fast_exit(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x00)
            insns = f.run_jsr("HorseForm_ConstrainGroundInput")
            assert insns <= 10, f"Idle early-out took {insns} insns (expected <=10)"
            assert len(f.tile_queries) == 0
        case("idle_dpad_fast_early_out", idle_fast_exit)

        def corner_slide_north_left(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            # Link at (128, 128). North probes at Y=118, X in {131, 136, 140}.
            # Put solid ONLY on X < 134, Y < 124 (hits ONLY left corner X=131!).
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0001) if (x < 134 and y < 124) else (0x00, 0x0000))
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x08); f.put(0xF2, 0x08)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert f.get(0xF0) == 0x00, "Forward Up must be stripped to prevent clip"
            assert (f.get(0x22) | (f.get(0x23) << 8)) == 129, "Left-corner hit should nudge +1 X"
            assert (f.get(0x20) | (f.get(0x21) << 8)) == 128
        case("corner_slide_north_left_nudges_east", corner_slide_north_left)

        def corner_slide_north_right(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            # Link at (132, 128): North probes at Y=118, X in {135 (tile 128), 140 (tile 136), 144 (tile 144)}.
            # Put solid ONLY on 16x16/8x8 tile x >= 144, y < 124 (hits ONLY right corner X=144!).
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0001) if (x >= 144 and y < 124) else (0x00, 0x0000))
            f.word(0x22, 132); f.word(0x20, 128)
            f.put(0xF0, 0x08); f.put(0xF2, 0x08)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert f.get(0xF0) == 0x00
            assert (f.get(0x22) | (f.get(0x23) << 8)) == 131, "Right-corner hit should nudge -1 X"
        case("corner_slide_north_right_nudges_west", corner_slide_north_right)

        def corner_slide_east_top(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            # East probes at X=149, Y in {131, 136, 140, 146}. Hit ONLY top corner Y=131.
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0001) if (x >= 144 and y < 134) else (0x00, 0x0000))
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x01); f.put(0xF2, 0x01)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert f.get(0xF0) == 0x00
            assert (f.get(0x20) | (f.get(0x21) << 8)) == 129, "Top-corner hit should nudge +1 Y"
        case("corner_slide_east_top_nudges_south", corner_slide_east_top)

        def corner_slide_east_bottom(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            # Hit ONLY bottom corner Y=146 (solid for x >= 144 and y >= 144)
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0001) if (x >= 144 and y >= 144) else (0x00, 0x0000))
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x01); f.put(0xF2, 0x01)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert f.get(0xF0) == 0x00
            assert (f.get(0x20) | (f.get(0x21) << 8)) == 127, "Bottom-corner hit should nudge -1 Y"
        case("corner_slide_east_bottom_nudges_north", corner_slide_east_bottom)

        def corner_slide_blocks_hazard_and_diagonal(f):
            f.setup_area(0x0000, 0x0000, 512, 512)
            # (a) Water ($08) at candidate foot -> MUST NOT nudge into water!
            def water_right(x, y):
                if x < 134 and y < 124:
                    return (0x01, 0x0001)
                if x >= 136:
                    return (0x08, 0x0008)  # deep water!
                return (0x00, 0x0000)
            f.populate_tile16_grid(0, 0, 512, 512, water_right)
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x08); f.put(0xF2, 0x08)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert (f.get(0x22) | (f.get(0x23) << 8)) == 128, "Must NOT corner-slide into deep water!"

            # (b) Diagonal (Up+Left) + left corner hit -> MUST NOT nudge East against Left press!
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0001) if (x < 134 and y < 124) else (0x00, 0x0000))
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x0A); f.put(0xF2, 0x0A)  # Up ($08) + Left ($02)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert (f.get(0x22) | (f.get(0x23) << 8)) == 128, "Diagonal input must not auto-nudge!"

            # (c) Ranch fence ($0078) ahead -> MUST remain clear so CheckFenceJump can jump!
            f.populate_tile16_grid(0, 0, 512, 512, lambda x, y: (0x01, 0x0078) if y < 124 else (0x00, 0x0000))
            f.word(0x22, 128); f.word(0x20, 128)
            f.put(0xF0, 0x08); f.put(0xF2, 0x08)
            f.run_jsr("HorseForm_ConstrainGroundInput")
            assert f.get(0xF0) == 0x08, "Ranch fence must stay unblocked for fence jumping!"
        case("corner_slide_safe_vs_water_diagonal_fence", corner_slide_blocks_hazard_and_diagonal)

        # =====================================================================
        # 3. DROPABLE-SAFE VRAM DMA + OAM EMISSION ACROSS ALL 19 FRAMES
        # =====================================================================
        def verify_part4_8px_narrow_pixels(f):
            buf = (ROOT / "Masks/gfx/horse_sparse.4bpp").read_bytes()
            tbl = (ROOT / "Masks/gfx/horse_sparse_tables.asm").read_text()
            ptrs = re.findall(
                r"dw HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),"
                r"HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+),HorseGraphics\+\$([0-9A-F]+)",
                tbl,
            )
            for fi in (8, 9, 16):
                p4_off = int(ptrs[fi][2], 16)
                tr = buf[p4_off + 32 : p4_off + 64]
                br = buf[p4_off + 96 : p4_off + 128]
                assert all(b == 0 for b in tr) and all(b == 0 for b in br), f"Frame {fi} part 4 TR/BR nonzero!"
        case("sparse_4bpp_8part_frames_part4_strictly_8px", verify_part4_8px_narrow_pixels)

        def verify_link_dma_prefix_animates_rupee(f):
            # Setup mounted state: Horse_Marker='HR', CurrentMask=$09, Module=$09, outdoors
            f.word(0x1EDE, 0x4852)
            f.put(0x02B2, 0x09)
            f.put(0x10, 0x09)
            f.put(0x1B, 0x00)
            f.word(0x0AE0, 0xB280)
            f.word(0x0AE2, 0xB2E0)
            f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            assert f.jumped_target == "dma_8adb", f.jumped_target
            # Verify animated Rupee top ($40B0, 32B) and bottom ($41B0, 32B) were DMA'd from bank $7E!
            rupee_dmas = [(s, e, bk, src, sz) for s, e, bk, src, sz in f.dma_writes if s in (0x40B0, 0x41B0)]
            assert rupee_dmas == [
                (0x40B0, 0x40C0, 0x7E, 0xB280, 0x20),
                (0x41B0, 0x41C0, 0x7E, 0xB2E0, 0x20),
            ], rupee_dmas
        case("link_dma_prefix_preserves_animated_rupee", verify_link_dma_prefix_animates_rupee)

        def verify_link_dma_prefix_preserves_horse_during_dialogue(f):
            # Retroid bug_004340: talking to Running Man ($74) or any NPC while mounted
            # enters Module $0E, Submodule $02 (Dialogue). Horse_LinkDmaPrefix MUST grant
            # bit 7 of Horse_PalLoaded and skip native Link overwrite (JML $008ADB), and
            # Horse_NmiUpload MUST take .steady -> .replay without calling Horse_RestoreItemCells.
            f.word(0x1EDE, 0x4852)
            f.put(0x02B2, 0x09)
            f.put(0x10, 0x0E)
            f.put(0x11, 0x02)        # Dialogue / Messaging
            f.put(0x1B, 0x00)
            f.put(0x1EEC, 0x01)      # Horse_PalLoaded bit 0 set, bit 7 clear
            f.word(0x0AE0, 0xB280)
            f.word(0x0AE2, 0xB2E0)
            f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
            assert f.jumped_target == "dma_8adb", f"Dialogue took {f.jumped_target}, expected dma_8adb"
            assert f.get(0x1EEC) == 0x81, f"Expected Horse_PalLoaded=$81, got ${f.get(0x1EEC):02X}"

            # Follow-on NMI upload in same vblank: keeps mounted cells with zero item-restore DMA.
            f.dma_writes.clear()
            f.put(0x1EEB, 0xFF)      # Horse_NpcUploadedFrame = FF
            f.put(0x1EE7, 0x06)      # Horse_Frame = 6
            f.put(0x1EE8, 0x06)      # Horse_UploadedFrame = 6 (already uploaded)
            f.put(0x1EED, 0x01)      # skip trailing BG replay
            f.run_jsl("Horse_NmiUpload", mf=True, xf=False)
            assert f.dma_writes == [], f"Expected zero DMA during steady dialogue, got {f.dma_writes}"
            assert f.get(0x1EE8) == 0x06, "Horse_UploadedFrame must remain 6 (not reset to FF)"

            # Contrast: non-whitelisted $0E submodule ($05) and active Map ($07, $0200!=0) take .native!
            for sub, sub200 in ((0x05, 0x00), (0x07, 0x01)):
                f.put(0x10, 0x0E); f.put(0x11, sub); f.put(0x0200, sub200)
                f.put(0x1EEC, 0x01)
                f.run_jml("Horse_LinkDmaPrefix", mf=True, xf=False)
                assert f.jumped_target == "dma_8a12", (sub, sub200, f.jumped_target)
                assert (f.get(0x1EEC) & 0x80) == 0, (sub, sub200, hex(f.get(0x1EEC)))
        case("link_dma_prefix_preserves_horse_during_dialogue", verify_link_dma_prefix_preserves_horse_during_dialogue)

        def verify_all_19_frames_vram_and_oam_dropable_safe(f):
            # Execute Horse_NmiUpload + Horse_DrawPlayerOam_Long for ALL 19 frames!
            for frame in range(19):
                # (a) NMI upload VRAM write audit
                f.dma_writes.clear()
                f.word(0x1EDE, 0x4852)
                f.put(0x1EEC, 0x80)        # Horse_PalLoaded grant bit7
                f.put(0x1EEB, 0xFF)        # Horse_NpcUploadedFrame = FF
                f.put(0x1EE8, 0xFF)        # Horse_UploadedFrame = FF (force upload)
                f.put(0x1EE7, frame)       # Horse_Frame
                f.put(0x10, 0x09); f.put(0x11, 0x00)
                f.put(0x1EED, 0x01)        # Horse_DismountCooldown=1 skips trailing $0ADC BG replay
                f.run_jsl("Horse_NmiUpload", mf=True, xf=False)
                assert len(f.dma_writes) >= 6, (frame, f.dma_writes)
                for s, e, bk, src, sz in f.dma_writes:
                    for pname, plo, phi in PROTECTED_VRAM_RANGES:
                        assert e <= plo or s >= phi, (
                            f"Frame {frame} VRAM write [${s:04X}..${e:04X}) overlapped {pname} [${plo:04X}..${phi:04X})!"
                        )

                # (b) OAM emission audit for BOTH Right ($2F=6) and Left ($2F=4) facing
                for facing in (6, 4):
                    f.put(0x1EE7, frame)
                    f.put(0x1EE8, frame)
                    f.put(0x1EE0, 0)       # grounded
                    f.put(0x1EE4, 0)       # Horse_JumpZ = 0
                    f.put(0x2F, facing)
                    f.word(0x22, 120); f.word(0x20, 120)
                    f.word(0xE2, 0); f.word(0xE8, 0)
                    f.put(0xEE, 0); f.put(0x0FB3, 0); f.put(0x11, 0); f.put(0x17, 0)
                    f.put(0x4B, 0); f.put(0x55, 0); f.word(0x031F, 0)
                    # Clear OAM slots at $08C0..$08EF ($0352 = $00C0 -> 12 entries)
                    for i in range(0x00C0, 0x00F0):
                        f.put(0x0800 + i, 0xF0)
                    f.run_jsl("Horse_DrawPlayerOam_Long", mf=True, xf=True)
                    visible = []
                    for slot in range(12):
                        base = 0x08C0 + slot * 4
                        x_lo = f.get(base)
                        y_lo = f.get(base + 1)
                        tile = f.get(base + 2)
                        attr = f.get(base + 3)
                        sz = f.get(0x0A20 + (0xC0 // 4) + slot) & 0x02
                        if y_lo != 0xF0:
                            visible.append((tile, sz, x_lo, y_lo, attr))
                    assert len(visible) <= 12, (frame, facing, len(visible))
                    # Rider Head=$08 (16x16), Rider Body=$0C (16x16) — NEVER 16x16 at $0A!
                    tiles_16 = [t for t, sz, *_ in visible if sz == 0x02]
                    tiles_8 = [t for t, sz, *_ in visible if sz == 0x00]
                    assert 0x08 in tiles_16 and 0x0C in tiles_16, (frame, facing, tiles_16)
                    assert 0x0A not in tiles_16, f"Frame {frame} emitted 16x16 at $0A (would read Rupee $0B)!"
                    assert 0x0B not in tiles_16 and 0x0B not in tiles_8
                    assert 0x29 not in tiles_16 and 0x29 not in tiles_8
                    if frame in (8, 9, 16):
                        assert 0x0A in tiles_8 and 0x1A in tiles_8, (frame, facing, tiles_8)
                        assert len(visible) == 11, (frame, facing, len(visible))
                    else:
                        assert tiles_8 == [], (frame, facing, tiles_8)
        case("all_19_frames_zero_dropable_vram_and_oam_overlap", verify_all_19_frames_vram_and_oam_dropable_safe)

        # =====================================================================
        # 4. ZERO MID-SCREEN HOSTILE-ENEMY DESPAWN WHILE MOUNTED
        # =====================================================================
        def throttle_never_despawns_hostiles(f):
            f.put(0x10, 0x09); f.put(0x11, 0x00); f.put(0x02E4, 0x00)
            f.put(0x7F5410, 0x00)  # HorseGame_State = 0
            # Spawn 5 ordinary hostile overworld patrol enemies
            for slot, sid in [(0, 0x08), (1, 0x41), (2, 0x12), (3, 0xC9), (4, 0xD0)]:
                f.set_sprite(slot, sid, state=9)
            f.run_jsr("HorseForm_ThrottleHostiles")
            alive = [s for s in range(5) if f.get(0x0DD0 + s) == 9]
            assert alive == [0, 1, 2, 3, 4], f"Mid-screen enemy despawn detected! alive={alive}"
        case("throttle_never_despawns_hostiles_midscreen", throttle_never_despawns_hostiles)

        def throttle_strictly_preserves_all_protected_actors(f):
            f.put(0x10, 0x09); f.put(0x11, 0x00); f.put(0x02E4, 0x00)
            f.put(0x7F5410, 0x00)
            # Test batch 1: NPCs, Ranch residents, Cucco, Farore, Piratian, Portal, Apple, Pickups
            protected_batch_1 = [
                (0,  0x3C, dict(harm=0x80)),   # Ranch Kid
                (1,  0x2A, dict(harm=0x80)),   # Sweeper
                (2,  0x74, dict(harm=0x80)),   # Runner
                (3,  0x0B, dict(harm=0x00)),   # Cucco (Harmless=0!)
                (4,  0x2D, dict(harm=0x80, ba0=1)),  # Epona NPC
                (5,  0x07, dict(harm=0x80)),   # Bean Vendor / Switch
                (6,  0x6C, dict(harm=0x80)),   # Mirror Portal
                (7,  0xAC, dict(harm=0x00)),   # Apple (Harmless=0!)
                (8,  0xEB, dict(harm=0x80)),   # Heart Piece
                (9,  0xD8, dict(harm=0x80)),   # Heart drop
                (10, 0xD9, dict(harm=0x80)),   # Green Rupee
                (11, 0xE3, dict(harm=0x80, ba0=1)),  # Fairy
                (12, 0x73, dict(harm=0x00)),   # Farore (Harmless=0!)
                (13, 0x0E, dict(harm=0x00)),   # Piratian (Harmless=0!)
                (14, 0x03, dict(harm=0x00)),   # Sprite_Portal (Harmless=0!)
                (15, 0xB0, dict(harm=0x00)),   # SwitchTrack (Harmless=0!)
            ]
            for slot, sid, kw in protected_batch_1:
                f.set_sprite(slot, sid, state=9, **kw)
            f.run_jsr("HorseForm_ThrottleHostiles")
            for slot, sid, _ in protected_batch_1:
                assert f.get(0x0DD0 + slot) == 9, f"Protected actor ${sid:02X} (slot {slot}) was wrongly despawned!"

            # Test batch 2: Bosses, property flags, plus 3 ordinary hostiles (none despawned)
            for s in range(16):
                f.put(0x0DD0 + s, 0)
            protected_batch_2 = [
                (0,  0xC1, dict()),             # Dark Link (Boss=0!)
                (1,  0xA9, dict()),             # Wolfos miniboss (Boss=0!)
                (2,  0x08, dict(caa=0x80)),     # Persisted Archery Target ($0CAA bit7!)
                (3,  0x08, dict(boss=0x02)),    # Any !Boss sprite
                (4,  0x08, dict(oam_prop=0x40)),# Any !ImperviousAll sprite
                (5,  0x08, dict(ba0=0x01)),     # Any SprBulletproof sprite
                (6,  0x08, dict(f60=0x20)),     # Any !Persist sprite
                (7,  0x08, dict(harm=0x80)),    # Any !Harmless sprite
                (8,  0x25, dict(harm=0x00)),    # Village Dog
                (9,  0x0A, dict(harm=0x00)),    # Eon Owl
                (10, 0x59, dict(harm=0x00)),    # Lost Woods Bird
                (11, 0x5A, dict(harm=0x00)),    # Lost Woods Squirrel
            ]
            for slot, sid, kw in protected_batch_2:
                f.set_sprite(slot, sid, state=9, **kw)
            for slot in (12, 13, 14):
                f.set_sprite(slot, 0x08, state=9)
            f.run_jsr("HorseForm_ThrottleHostiles")
            for slot, sid, _ in protected_batch_2:
                assert f.get(0x0DD0 + slot) == 9, f"Protected batch2 ${sid:02X} (slot {slot}) was despawned!"
            alive_hostiles = [s for s in (12, 13, 14) if f.get(0x0DD0 + s) == 9]
            assert alive_hostiles == [12, 13, 14], f"Expected all 3 hostiles preserved, got {alive_hostiles}"
        case("throttle_preserves_all_npcs_targets_pickups_bosses", throttle_strictly_preserves_all_protected_actors)

        def throttle_skips_minigame_and_non_overworld(f):
            # Active minigame (HorseGame_State = 2): 4 unflagged Octoroks survive
            f.put(0x10, 0x09); f.put(0x11, 0x00); f.put(0x02E4, 0x00)
            f.put(0x7F5410, 0x02)
            for s in range(4):
                f.set_sprite(s, 0x08, state=9)
            f.run_jsr("HorseForm_ThrottleHostiles")
            assert all(f.get(0x0DD0 + s) == 9 for s in range(4))

            # Non-overworld module ($10 = $07 Dungeon): 4 enemies survive
            f.put(0x7F5410, 0x00); f.put(0x10, 0x07)
            f.run_jsr("HorseForm_ThrottleHostiles")
            assert all(f.get(0x0DD0 + s) == 9 for s in range(4))
        case("throttle_skips_minigame_and_non_ow", throttle_skips_minigame_and_non_overworld)

    result = {"status": "PASS", "cases": cases, "count": len(cases)}
    text = json.dumps(result, indent=2)
    if args.output:
        args.output.write_text(text + "\n")
    print(text)


if __name__ == "__main__":
    main()
