#!/usr/bin/env python3
"""Unit & real-65816 compiled execution tests for Zora Link Fast Swim,
Separate Overworld/Dungeon Diving, and Overworld Strong Sea Currents.

Verifies scawful's locked Option 1 design in Masks/zora_mask.asm:
1. Static source & allocation contracts:
   - Exact vanilla hook preimages ($0796D9, $079825, $0798A8, $079903,
     $07E459, $07E478, $07E53A, $07DAFA).
   - Bank $36 helper upper bound (<= $36F200 before DungeonWeb) and in-place
     Bank $07 routine bounds (<= $079903, <= $07996C).
   - Weak-default !KORL_Mounted = $7FF3D4 (King of Red Lions WRAM flag, read via
     LDA.l $7FF3D4) and !SeaCurrentDir = $0AB9 (low WRAM mirror; zero SRAM changes).
   - zora_palette format compatibility with Scripts/Graphics/zora_link_face_preview.py.
2. Real compiled 65816 execution (via asar + lakesnes snes/cpu.c):
   - Human Flippers ($00F0 = 0.9375 px/f) vs Zora Surface Swim ($01B0 = 1.6875 px/f,
     ~1.80x faster, leaving KORL headroom at ~2.75-3.0 px/f) vs Zora Overworld Dive
     ($0120 = 1.125 px/f) across full 60-frame multi-frame physics loops.
   - Clean separation of Y dive toggle vs B/A swim stroke in Zora form while
     preserving exact vanilla A/B/Y stroke for Human Link, plus Zora $0230 stroke peak.
   - Smooth dive deceleration ($01B0 -> $0120) and immediate resurface recovery
     ($0120 -> $01B0) even while continuously holding D-pad (never stuck at dive speed).
   - Ice movement ($034A != 0) strictly untouched for both Human and Zora.
   - Overworld Strong Sea Current TileTypes $68/$69/$6A/$6B (N/S/W/E) flag both
     Deep Water ($0341) and directional current bits ($03F1/$03F2).
   - Strong Sea Current pushback beats Human Link, Zora Surface (+ B stroke),
     and Zora Diving upstream in all 4 directions, with splash feedback.
   - King of Red Lions mount bypass (!KORL_Mounted != 0) cleanly disables both
     current latching and pushback/clamping so KORL sails straight upstream.
   - Clean speed/flag cleanup ($55/$5E/$037B/$0351/!ZoraDiving/!SeaCurrentDir)
     when unmasking, hopping onto shore, or walking on Overworld land (without
     breaking Stone Mask / Cape $55 when !ZoraDiving == 0).
   - Dungeon Zora Dive, DiveGate_CanSurface gate, resurface, and pit stall guard
     100% preserved, with Strong Sea Currents strictly inert indoors.
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
ZORA_ASM = ROOT / "Masks" / "zora_mask.asm"
SRAM_ASM = ROOT / "Core" / "sram.asm"

LAKESNES_CANDIDATES = (
    ROOT.parent / "lakesnes",
    Path.home() / "src" / "hobby" / "lakesnes",
)

# WRAM addresses used by Masks/zora_mask.asm
ADDR_ZORA_DIVING = 0x0AAB
ADDR_KORL_MOUNTED = 0x7FF3D4
ADDR_SEA_CURRENT_DIR = 0x0AB9

# Exact vanilla Bank $07 ROM bytes (unheadered LoROM) for self-contained CPU execution
VANILLA_SLICES = (
    (0x079639, bytes.fromhex("f000")),
    (0x0796D3, bytes.fromhex("a5f629808500a5f4050029c0")),
    (
        0x0797C7,
        bytes.fromhex(
            "e220a5f0290f85006401c230a903008502a202008604a00000a5002502f04525"
            "04d003a00100a920009d2603ad4a0329ff00f00b5a3a0aa8b9c3979d26037aad"
            "400305672502c502d008a902009d2b038007989d38039e2b03bd3403d006ad39"
            "969d34030602060206040604caca10a6e23060"
        ),
    ),
    (
        0x079896,
        bytes.fromhex(
            "8000a000c000e00000012001400160018001c230a20200a903008502a5f02502"
            "f040bd3c03f01cbd3403c980019014a00000b99698dd3c03b025c8c8c01200d0"
            "f1801cbd3403f00e1869a000c98001900ea980018009a901009d3c03ad39969d"
            "340306020602caca10b2e23060c230ad4a0329ff00d05cad4f0329ff00d054a2"
            "0200a903008502a5f02502f035bd2b03c90200f02dbd2f03d0129e2f03bd3c03"
            "cd39969026dd3403f002901f9e2b03bd3c03cd3996900ba901009d2b039d2f03"
            "8009ad39969d34039e2f0306020602caca10b4e23060"
        ),
    ),
    (0x07DAFA, bytes.fromhex("29de2dde35de3ade")),
    (0x07DE29, bytes.fromhex("a50a8014a50a0a0a0a0a800ca50aeb8007a50aeb0a0a0a0a0cf10360")),
    (
        0x07E3E0,
        bytes.fromhex(
            "c220a520186d7e0b8520a522186d7c0b8522e220a52038e5008530a52238e501"
            "8531e220ab6b0800f4fff8fff0ff0400fafff4fffaff0a00f0fff4fffafff3ff"
            "fcff080004000200010064276428c220a2027408de26031009a901009d2b039e"
            "2603bd2b030aa8ad4a0329ff00f00a0a0a0a850098186500a8b906e4187d3c03"
            "f002102abd1ee4256785678526bd2b03c90200d00e9e2b03ad39969d3403a902"
            "008023a900009d34039d2b038018488a187d38030aa8b922e40567856768dd34"
            "039003bd34039d3c039508a56af00db5084a4a8500b50838e5009508bd380329"
            "ff00d008b50849ffff1a9508caca3003825fffe220a5208500853ea522850185"
            "3fa52185028540a52385038541a001a202b50818792a00992a005a08b509c908"
            "a000900409f0a0ff287520952098752195217ab5084a4a4a4a9508b509100349"
            "ff1a0a0a0a0a150899270088caca10c1ad6c04c904d00320cde564686469829f"
            "fe"
        ),
    ),
)

# External stub addresses referenced by Masks/zora_mask.asm
STUB_SPLASH = 0x0998FC
STUB_INDOOR_CAM = 0x07E8F0
STUB_CHECK_NEW_Y = 0x07B073
STUB_DIVEGATE = 0x2C9000
STUB_TRANSFORM = 0x3A9000
STUB_COLOR_SUB = 0x349000
STUB_FALL_PIT = 0x079427


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
        self.stubs: dict[int, tuple[str, int, object | None]] = {}
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

    def get16(self, addr: int) -> int:
        return self.get(addr) | (self.get(addr + 1) << 8)

    def put(self, addr: int, val: int) -> None:
        self._write(addr, val & 0xFF)

    def put16(self, addr: int, val: int) -> None:
        self.put(addr, val & 0xFF)
        self.put(addr + 1, (val >> 8) & 0xFF)

    def add_stub(self, addr: int, name: str, opcode: int, hook=None) -> None:
        self.stubs[addr] = (name, opcode, hook)

    def _run_until(self, sentinel: int, sp0: int, max_steps: int) -> None:
        for _ in range(max_steps):
            pc24 = (self.cpu.k << 16) | self.cpu.pc
            if pc24 == sentinel:
                if self.cpu.sp != sp0:
                    raise AssertionError(f"SP drift: expected {sp0:#06x}, got {self.cpu.sp:#06x}")
                if self.bad_writes:
                    raise AssertionError(f"Unexpected non-WRAM writes: {self.bad_writes}")
                return
            if pc24 in self.stubs:
                name, _, hook = self.stubs[pc24]
                self.calls.append((name, {"a": self.cpu.a, "x": self.cpu.x, "y": self.cpu.y, "db": self.cpu.db}))
                if hook is not None:
                    hook(self)
            self.lib.cpu_runOpcode(self._ptr)
        raise AssertionError(f"Instruction ceiling reached at ${self.cpu.k:02X}:{self.cpu.pc:04X}")

    def call_jsl(self, target: int, max_steps: int = 8000) -> None:
        sp0 = self.cpu.sp
        sentinel_bank, sentinel_pc = 0x07, 0x7000
        self.put(sp0, sentinel_bank)
        self.put(sp0 - 1, (sentinel_pc - 1) >> 8)
        self.put(sp0 - 2, (sentinel_pc - 1) & 0xFF)
        self.cpu.sp = sp0 - 3
        self.cpu.k = target >> 16
        self.cpu.pc = target & 0xFFFF
        self._run_until((sentinel_bank << 16) | sentinel_pc, sp0, max_steps)

    def call_jsr(self, target: int, max_steps: int = 8000) -> None:
        sp0 = self.cpu.sp
        bank = target >> 16
        sentinel_pc = 0x7000
        self.put(sp0, (sentinel_pc - 1) >> 8)
        self.put(sp0 - 1, (sentinel_pc - 1) & 0xFF)
        self.cpu.sp = sp0 - 2
        self.cpu.k = bank
        self.cpu.pc = target & 0xFFFF
        self._run_until((bank << 16) | sentinel_pc, sp0, max_steps)


def _find_lakesnes() -> Path | None:
    for candidate in LAKESNES_CANDIDATES:
        if (candidate / "snes" / "cpu.c").is_file() and (candidate / "snes" / "statehandler.c").is_file():
            return candidate
    return None


class ZoraSwimContractTest(unittest.TestCase):
    """Static source & allocation contract checks (always run)."""

    def test_hook_preimages_and_bounds_present(self):
        text = ZORA_ASM.read_text(encoding="utf-8")
        for expected in (
            "assert pc() <= $36F200",
            "org $0796D9",
            "assert read4($0796D9) == $0005F4A5 && read2($0796DD) == $C029",
            "org $079825",
            "assert read4($079825) == $9D9639AD && read2($079829) == $0334",
            "org $0798A8",
            "assert pc() <= $079903",
            "org $079903",
            "assert pc() <= $07996C",
            "org $07E459",
            "assert read4($07E459) == $18E406B9",
            "org $07E478",
            "org $07E53A",
            "assert read4($07E53A) == $69646864",
            "org $07DAFA",
            "assert read4($07DAFA) == $DE2DDE29 && read4($07DAFE) == $DE3ADE35",
            'if not(defined("KORL_Mounted"))',
            "!KORL_Mounted = $7FF3D4",
            "LDA.l !KORL_Mounted",
            "!SeaCurrentDir = $0AB9",
        ):
            self.assertIn(expected, text)

    def test_zero_sram_delta_and_palette_preview_compat(self):
        sram_text = SRAM_ASM.read_text(encoding="utf-8")
        self.assertNotIn("KORL_Mounted", sram_text)
        self.assertNotIn("SeaCurrentDir", sram_text)

        # Preserve zora_palette parse contract used by Scripts/Graphics/zora_link_face_preview.py
        text = ZORA_ASM.read_text(encoding="utf-8")
        section = text.split("zora_palette:", 1)[1].split("; dw", 1)[0]
        words = re.findall(r"\$([0-9A-Fa-f]{4})", section)
        self.assertEqual(len(words), 16, "zora_palette must expose 16 BGR555 words before '; dw'")


class ZoraSwimCompiledCpuTest(unittest.TestCase):
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

        cls.tmpdir = tempfile.TemporaryDirectory(prefix="oos-zora-swim-")
        work = Path(cls.tmpdir.name)

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

        # 2 MiB LoROM seeded with exact vanilla Bank $07 swimming & conveyor slices
        raw = bytearray(0x200000)
        for addr, payload in VANILLA_SLICES:
            pc = snes_to_pc(addr)
            raw[pc : pc + len(payload)] = payload
        image = work / "fixture.sfc"
        image.write_bytes(raw)

        asm_path = work / "harness.asm"
        asm_path.write_text(
            f"""lorom
!ZoraDiving = $0AAB
struct TimeState $7E1E70
  .SubColor: skip 2
endstruct
ColorSubEffect = ${STUB_COLOR_SUB:06X}
Link_TransformMask = ${STUB_TRANSFORM:06X}
Link_CheckNewY_ButtonPress = ${STUB_CHECK_NEW_Y:06X}
DiveGate_CanSurface = ${STUB_DIVEGATE:06X}

org $07F8E3 : pushpc
org $36F000
incsrc "{ZORA_ASM}"
pullpc
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

    def _new_fx(self) -> CpuHarness:
        fx = CpuHarness(self.lib, self.rom, self.labels)
        fx.add_stub(STUB_SPLASH, "AddTransitionSplash", 0x6B)
        fx.add_stub(STUB_INDOOR_CAM, "HandleIndoorCameraAndDoors", 0x60)
        fx.add_stub(STUB_CHECK_NEW_Y, "Link_CheckNewY_ButtonPress", 0x60)
        fx.add_stub(STUB_DIVEGATE, "DiveGate_CanSurface", 0x6B)
        fx.add_stub(STUB_TRANSFORM, "Link_TransformMask", 0x6B)
        fx.add_stub(STUB_FALL_PIT, "FallIntoPit", 0x60)
        return fx

    def _run_swim_frame(self, fx: CpuHarness, dpad: int, *, stroke_b: bool = False) -> None:
        """Execute one compiled swimming physics frame (momentum, max accel,
        optional stroke, HandleSwimStrokeAndSubpixels + SeaCurrent + SandDrag)."""
        fx.put(0xF0, dpad)
        fx.put(0xF4, 0x80 if stroke_b else 0x00)
        fx.put(0xF6, 0x00)
        fx.put(0x1A, (fx.get(0x1A) + 1) & 0xFF)
        if stroke_b:
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(0x0798A8)  # ZoraSwim_HandleStrokeAccels
            fx.put(0x034F, 0x80)

        if dpad:
            if fx.get(0x0340) != dpad:
                fx.put(0x2A, 0)
                fx.put(0x2B, 0)
            fx.put(0x0340, dpad)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(0x0797C7)  # Link_SetMomentum
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(0x079903)  # ZoraSwim_SetTheMaxAccel

        # HandleSwimStrokeAndSubpixels ($07E42A) ends at Link_HandleVelocityAndSandDrag ($07E3E0)
        # which exits with PLB : RTL, so push DB=$07 before calling via call_jsl.
        fx.reset_cpu(db=0x07, m8=True, x8=True)
        fx.put(fx.cpu.sp, 0x07)  # fake PHB pushed by Link_HandleVelocity
        fx.cpu.sp -= 1
        # Push return address below fake PHB: call_jsl pushes PBR/PCH/PCL then we run from $07E42A.
        # Because PLB executes BEFORE RTL, place sentinel return address FIRST, then PHB byte!
        fx.reset_cpu(db=0x07, m8=True, x8=True)
        sp0 = fx.cpu.sp
        sentinel_bank, sentinel_pc = 0x07, 0x7000
        fx.put(sp0, sentinel_bank)
        fx.put(sp0 - 1, (sentinel_pc - 1) >> 8)
        fx.put(sp0 - 2, (sentinel_pc - 1) & 0xFF)
        fx.put(sp0 - 3, 0x07)  # saved DBR popped by PLB at $07E404
        fx.cpu.sp = sp0 - 4
        fx.cpu.k = 0x07
        fx.cpu.pc = 0xE42A
        fx._run_until((sentinel_bank << 16) | sentinel_pc, sp0, 8000)

    def test_human_vs_zora_surface_vs_zora_dive_cruise_speed(self):
        def measure_60f(mask_id: int, diving: int) -> tuple[int, int, int, int]:
            fx = self._new_fx()
            try:
                fx.put(0x1B, 0)                  # Overworld
                fx.put(0x5D, 0x04)               # LinkState_Swimming
                fx.put(0x02B2, mask_id)
                fx.put(ADDR_ZORA_DIVING, diving)
                fx.put16(0x20, 0x0400)
                fx.put16(0x22, 0x0400)
                for _ in range(60):
                    self._run_swim_frame(fx, 0x01)  # Hold Right
                dist_from_rest = fx.get16(0x22) - 0x0400
                x_mid = fx.get16(0x22)
                sust_thrusts = []
                for _ in range(60):
                    self._run_swim_frame(fx, 0x01)  # Sustained 60 frames at cruise
                    sust_thrusts.append(fx.get16(0x033E))
                dist_sustained = fx.get16(0x22) - x_mid
                return dist_from_rest, dist_sustained, min(sust_thrusts), max(sust_thrusts)
            finally:
                fx.close()

        human_rest, human_sust, human_min, human_max = measure_60f(0x00, 0)
        zora_rest, zora_sust, zora_min, zora_max = measure_60f(0x02, 0)
        dive_rest, dive_sust, dive_min, dive_max = measure_60f(0x02, 1)

        # Exact cruise peak & vanilla bobbing oscillation bands
        self.assertEqual((human_min, human_max), (0x00E4, 0x00F0), "Human Flippers must stay exact vanilla [$00E4..$00F0]")
        self.assertEqual((zora_min, zora_max), (0x01A0, 0x01B0), "Zora Surface must cruise in [$01A0..$01B0]")
        self.assertEqual((dive_min, dive_max), (0x0112, 0x0120), "Zora Dive must cruise in [$0112..$0120]")

        # Clear ordering: Human (55px) < Zora Dive (66px) < Zora Surface (99px) < KORL (~165-180px)
        self.assertLess(human_sust, dive_sust)
        self.assertLess(dive_sust, zora_sust)
        self.assertAlmostEqual(zora_sust / human_sust, 1.80, delta=0.05)
        self.assertLess(zora_sust, 150, "Must leave clear speed headroom for King of Red Lions (~165-180 px/60f)")
        self.assertGreater(zora_rest, int(human_rest * 1.6))

    def test_stroke_input_separation_and_peak_speed(self):
        fx = self._new_fx()
        try:
            check_fn = self.labels["ZoraSwim_CheckStrokeInput"]

            # Human Link: B ($80), Y ($40), and A ($00=$80) all trigger stroke (vanilla $C0)
            fx.put(0x02B2, 0x00)
            fx.put(ADDR_ZORA_DIVING, 0x00)
            for f4, z0, expected in ((0x80, 0x00, 0x80), (0x40, 0x00, 0x40), (0x00, 0x80, 0x80), (0x00, 0x00, 0x00)):
                fx.reset_cpu(db=0x07, m8=True, x8=True)
                fx.put(0xF4, f4)
                fx.put(0x00, z0)
                fx.call_jsl(check_fn)
                self.assertEqual(fx.cpu.a & 0xFF, expected)
                self.assertEqual(fx.cpu.z, expected == 0)

            # Zora Surface: B and A stroke ($80), Y is cleanly suppressed ($00) for diving!
            fx.put(0x02B2, 0x02)
            fx.put(ADDR_ZORA_DIVING, 0x00)
            for f4, z0, expected in ((0x80, 0x00, 0x80), (0x40, 0x00, 0x00), (0x00, 0x80, 0x80)):
                fx.reset_cpu(db=0x07, m8=True, x8=True)
                fx.put(0xF4, f4)
                fx.put(0x00, z0)
                fx.call_jsl(check_fn)
                self.assertEqual(fx.cpu.a & 0xFF, expected)
                self.assertEqual(fx.cpu.z, expected == 0)

            # Zora Diving: B, Y, and A all suppressed (no surface stroke while underwater)
            fx.put(ADDR_ZORA_DIVING, 0x01)
            for f4, z0 in ((0x80, 0x00), (0x40, 0x00), (0x00, 0x80)):
                fx.reset_cpu(db=0x07, m8=True, x8=True)
                fx.put(0xF4, f4)
                fx.put(0x00, z0)
                fx.call_jsl(check_fn)
                self.assertEqual(fx.cpu.a & 0xFF, 0x00)
                self.assertTrue(fx.cpu.z)

            # Stroke peak: Human caps at $0180, Zora Surface boosts to $0230
            for mask_id, base_max, expected_peak in ((0x00, 0x00F0, 0x0180), (0x02, 0x01B0, 0x0230)):
                fx.reset_cpu(db=0x07, m8=True, x8=True)
                fx.put(0x5D, 0x04)
                fx.put(0x02B2, mask_id)
                fx.put(ADDR_ZORA_DIVING, 0)
                fx.put(0xF0, 0x01)
                fx.put16(0x033E, base_max)
                fx.put16(0x0336, base_max)
                fx.call_jsr(0x0798A8)
                self.assertEqual(fx.get16(0x0336), expected_peak)
        finally:
            fx.close()

    def test_overworld_dive_and_resurface_speed_recovery(self):
        fx = self._new_fx()
        try:
            fx.put(0x1B, 0)
            fx.put(0x5D, 0x04)
            fx.put(0x02B2, 0x02)
            fx.put16(0x20, 0x0400)
            fx.put16(0x22, 0x0400)

            # Ramp up to full Zora surface cruise ($01B0)
            for _ in range(35):
                self._run_swim_frame(fx, 0x01)
            self.assertEqual(fx.get16(0x033E), 0x01B0)
            self.assertEqual(fx.get(0x55), 0)
            self.assertEqual(fx.get(0x037B), 0)

            # Simulate an active surface stroke ($034F=$80, $032A=2) then press Y to dive
            fx.put(0x034F, 0x80)
            fx.put(0x032A, 0x02)
            fx.add_stub(STUB_CHECK_NEW_Y, "Y_PRESS", 0x60, hook=lambda h: setattr(h.cpu, "c", True))
            fx.calls.clear()
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask"])

            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 1)
            self.assertEqual(fx.get(0x55), 1)
            self.assertEqual(fx.get(0x037B), 1)
            self.assertEqual(fx.get(0x0351), 1)
            self.assertEqual(fx.get(0x5E), 0, "Overworld dive must NOT set ground slow speed $5E")
            self.assertEqual(fx.get(0x034F), 0, "Dive must clear active surface stroke burst")
            self.assertEqual(fx.get(0x032A), 0)
            self.assertEqual(fx.get(0x5D), 0x04)
            self.assertTrue(any(c[0] == "AddTransitionSplash" for c in fx.calls))

            # Simulate vanilla collision clearing $0351 on a non-Y frame while diving:
            # LinkState_UsingZoraMask must keep $0351=1 continuously while underwater!
            fx.put(0x0351, 0)
            fx.add_stub(STUB_CHECK_NEW_Y, "NO_Y", 0x60, hook=lambda h: setattr(h.cpu, "c", False))
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask"])
            self.assertEqual(fx.get(0x0351), 1, "Underwater ripple $0351 must stay active every dive frame")

            # Continue holding Right underwater: smoothly decelerates from $01B0 into [$0112..$0120]
            dive_tail = []
            for f in range(30):
                self._run_swim_frame(fx, 0x01)
                if f >= 20:
                    dive_tail.append(fx.get16(0x033E))
            self.assertEqual((min(dive_tail), max(dive_tail)), (0x0112, 0x0120))
            self.assertEqual(fx.get16(0x0336), 0x0120)

            # Press Y to resurface while STILL holding Right!
            fx.add_stub(STUB_CHECK_NEW_Y, "Y_PRESS", 0x60, hook=lambda h: setattr(h.cpu, "c", True))
            fx.calls.clear()
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask"])
            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 0)
            self.assertEqual(fx.get(0x55), 0)
            self.assertEqual(fx.get(0x037B), 0)
            self.assertEqual(fx.get(0x0351), 0)
            self.assertEqual(fx.get(0x5E), 0)
            self.assertEqual(fx.get(0x5D), 0x04)
            self.assertTrue(any(c[0] == "AddTransitionSplash" for c in fx.calls))

            # Keep holding Right without releasing D-pad: must recover full [$01A0..$01B0] surface speed!
            surf_tail = []
            for f in range(25):
                self._run_swim_frame(fx, 0x01)
                if f >= 15:
                    surf_tail.append(fx.get16(0x033E))
            self.assertEqual(fx.get16(0x0336), 0x01B0, "Target max must immediately rise back to $01B0")
            self.assertEqual((min(surf_tail), max(surf_tail)), (0x01A0, 0x01B0), "Thrust must recover to [$01A0..$01B0] after resurface")
        finally:
            fx.close()

    def test_ice_movement_untouched(self):
        fx = self._new_fx()
        try:
            fx.put(0x5D, 0x00)   # Ground/Ice state (not swimming)
            fx.put(0x034A, 0x01) # On Ice
            fx.put(0x02B2, 0x02) # Zora Mask equipped
            fx.reset_cpu(db=0x07, m8=False, x8=False)
            fx.call_jsl(self.labels["ZoraSwim_GetCruiseMax"])
            self.assertEqual(fx.cpu.a, 0x00F0)

            # StepThrust with Y=8 (ice table row 1: +4) must use vanilla table
            fx.reset_cpu(db=0x07, m8=False, x8=True)
            fx.put16(0x033C, 0x0020)
            fx.cpu.x = 0x00
            fx.cpu.y = 0x08
            fx.call_jsl(self.labels["ZoraSwim_StepThrust"])
            self.assertEqual(fx.cpu.a, 0x0024)
        finally:
            fx.close()

    def test_sea_current_tile_vectors_flag_deep_water_and_direction(self):
        cases = (
            ("TileBehavior_SeaCurrent_Up", 0x03F1, 0x01),
            ("TileBehavior_SeaCurrent_Down", 0x03F1, 0x10),
            ("TileBehavior_SeaCurrent_Left", 0x03F2, 0x01),
            ("TileBehavior_SeaCurrent_Right", 0x03F2, 0x10),
        )
        for label, expected_addr, expected_bit in cases:
            for probe_mask in (0x0001, 0x0002, 0x0004, 0x0008):
                fx = self._new_fx()
                try:
                    fx.reset_cpu(db=0x07, m8=False, x8=False)
                    fx.put16(0x0A, probe_mask)  # TileDetect_MainHandler Y=0,2,4,6 probes
                    fx.call_jsr(self.labels[label])
                    self.assertEqual(fx.get(0x0341), probe_mask, f"{label} must set Deep Water ($0341)")
                    self.assertEqual(fx.get(expected_addr), expected_bit, f"{label} direction bit mismatch")
                    # Mask $22 must stay 0 so vanilla TileDetect_Vertical/Horizontal never set $03F3
                    # (Link_ApplyConveyor), guaranteeing !KORL_Mounted != 0 feels zero conveyor drag.
                    self.assertEqual(fx.get(0x03F1) & 0x22, 0, f"{label} leaked vanilla conveyor bit in $03F1")
                    self.assertEqual(fx.get(0x03F2) & 0x22, 0, f"{label} leaked vanilla conveyor bit in $03F2")
                finally:
                    fx.close()

    def test_strong_sea_current_pushes_human_and_zora_all_directions(self):
        # (tile_label, expected_dir, upstream_dpad, coord_addr, expected_sign)
        directions = (
            ("TileBehavior_SeaCurrent_Up", 1, 0x04, 0x20, -1),     # Current N(-Y), swim S
            ("TileBehavior_SeaCurrent_Down", 2, 0x08, 0x20, +1),   # Current S(+Y), swim N
            ("TileBehavior_SeaCurrent_Left", 3, 0x01, 0x22, -1),   # Current W(-X), swim E
            ("TileBehavior_SeaCurrent_Right", 4, 0x02, 0x22, +1),  # Current E(+X), swim W
        )
        swimmers = (
            ("Human", 0x00, 0, False),
            ("ZoraSurface", 0x02, 0, False),
            ("ZoraStroke", 0x02, 0, True),
            ("ZoraDive", 0x02, 1, False),
        )
        for tile_label, exp_dir, upstream_dpad, coord_addr, sign in directions:
            for sw_name, mask_id, diving, use_stroke in swimmers:
                fx = self._new_fx()
                try:
                    fx.put(0x1B, 0)
                    fx.put(0x5D, 0x04)
                    fx.put(0x02B2, mask_id)
                    fx.put(ADDR_ZORA_DIVING, diving)
                    fx.put(ADDR_KORL_MOUNTED, 0)
                    fx.put16(0x20, 0x0400)
                    fx.put16(0x22, 0x0400)

                    # Execute the Overworld TileBehavior handler to populate $03F1/$03F2
                    fx.reset_cpu(db=0x07, m8=False, x8=False)
                    fx.put16(0x0A, 0x0001)
                    fx.call_jsr(self.labels[tile_label])

                    # Latch current via ZoraSwim_LatchSeaCurrent
                    fx.calls.clear()
                    fx.reset_cpu(db=0x07, m8=True, x8=True)
                    fx.call_jsl(self.labels["ZoraSwim_LatchSeaCurrent"])
                    self.assertEqual(fx.get(ADDR_SEA_CURRENT_DIR), exp_dir)
                    self.assertTrue(
                        any(c[0] == "AddTransitionSplash" for c in fx.calls),
                        f"Expected entry splash for {sw_name} in {tile_label}",
                    )

                    # Fight directly upstream for 30 frames (even with B strokes!)
                    for f in range(30):
                        self._run_swim_frame(fx, upstream_dpad, stroke_b=(use_stroke and f % 10 == 0))
                    delta = fx.get16(coord_addr) - 0x0400
                    pushed = delta * sign
                    self.assertGreaterEqual(
                        pushed,
                        35,
                        f"{sw_name} must be pushed firmly downstream by {tile_label} (delta={delta})",
                    )
                finally:
                    fx.close()

    def test_korl_mounted_bypasses_strong_sea_current(self):
        fx = self._new_fx()
        try:
            fx.put(0x1B, 0)
            fx.put(0x5D, 0x04)
            fx.put(0x02B2, 0x02)
            fx.put(ADDR_KORL_MOUNTED, 1)  # King of Red Lions mounted!
            fx.put16(0x20, 0x0400)
            fx.put16(0x22, 0x0400)

            # Set West Current ($6A) tile flags
            fx.reset_cpu(db=0x07, m8=False, x8=False)
            fx.put16(0x0A, 0x0001)
            fx.call_jsr(self.labels["TileBehavior_SeaCurrent_Left"])

            # Latch must clear !SeaCurrentDir and skip pushback splash
            fx.calls.clear()
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsl(self.labels["ZoraSwim_LatchSeaCurrent"])
            self.assertEqual(fx.get(ADDR_SEA_CURRENT_DIR), 0)
            self.assertFalse(any(c[0] == "AddTransitionSplash" for c in fx.calls))

            # Even if !SeaCurrentDir were nonzero, ApplySeaCurrent must completely bypass it
            fx.put(ADDR_SEA_CURRENT_DIR, 3)
            for _ in range(30):
                self._run_swim_frame(fx, 0x01)  # Sail East directly through West Current!
            delta_x = fx.get16(0x22) - 0x0400
            self.assertGreater(delta_x, 20, "KORL mount must sail freely upstream against strong currents")
        finally:
            fx.close()

    def test_land_exit_shore_hop_and_unmask_clean_speed_and_flags(self):
        fx = self._new_fx()
        try:
            # 1. Unmasking while swimming clears diving flags & speed
            fx.put(0x1B, 0)
            fx.put(0x5D, 0x04)
            fx.put(0x02B2, 0x00)  # Unmasked to Human
            fx.put(ADDR_ZORA_DIVING, 1)
            fx.put(0x55, 1)
            fx.put(0x5E, 0x08)
            fx.put(0x037B, 1)
            fx.put(0x0351, 1)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask"])
            for addr in (ADDR_ZORA_DIVING, 0x55, 0x5E, 0x037B, 0x0351):
                self.assertEqual(fx.get(addr), 0, f"Unmask must clear ${addr:04X}")

            # 2. Exiting Overworld water onto land while diving clears all dive flags & current
            fx.put(0x1B, 0)
            fx.put(0x5D, 0x00)
            fx.put(ADDR_ZORA_DIVING, 1)
            fx.put(ADDR_SEA_CURRENT_DIR, 3)
            fx.put(0x55, 1)
            fx.put(0x5E, 0x08)
            fx.put(0x037B, 1)
            fx.put(0x0351, 1)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask_dungeon_resurface"])
            for addr in (ADDR_ZORA_DIVING, ADDR_SEA_CURRENT_DIR, 0x55, 0x5E, 0x037B, 0x0351):
                self.assertEqual(fx.get(addr), 0, f"Land exit must clear ${addr:04X}")

            # 3. Stone Mask / Cape on Overworld land (!ZoraDiving == 0) must keep $55 intact!
            fx.put(0x1B, 0)
            fx.put(ADDR_ZORA_DIVING, 0)
            fx.put(0x55, 1)
            fx.put(0x037B, 1)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask_dungeon_resurface"])
            self.assertEqual(fx.get(0x55), 1, "Stone Mask / Cape $55 must not be cleared on land")
            self.assertEqual(fx.get(0x037B), 1)

            # 4. Vertical water hop (.dungeon_stairs) outdoors clears dive/current without stomping $9A
            fx.put(0x1B, 0)
            fx.put(0x02B2, 0x02)
            fx.put(ADDR_ZORA_DIVING, 1)
            fx.put(ADDR_SEA_CURRENT_DIR, 2)
            fx.put(0x55, 1)
            fx.put(0x5E, 0x08)
            fx.put(0x0351, 1)
            fx.put(0x9A, 0x42)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask_dungeon_stairs"])
            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 0)
            self.assertEqual(fx.get(ADDR_SEA_CURRENT_DIR), 0)
            self.assertEqual(fx.get(0x55), 0)
            self.assertEqual(fx.get(0x5E), 0)
            self.assertEqual(fx.get(0x0351), 0)
            self.assertEqual(fx.get(0x9A), 0x42, "Outdoor water hop must not overwrite Overworld $9A")
            self.assertEqual(fx.get(0x5D), 0x06)
        finally:
            fx.close()

    def test_dungeon_dive_resurface_and_indoor_current_inert(self):
        fx = self._new_fx()
        try:
            # Indoors ($1B=1): Strong Sea Current must clear & stay completely inert
            fx.put(0x1B, 1)
            fx.put(0x5D, 0x04)
            fx.put(0x02B2, 0x02)
            fx.put(0x03F1, 0x01)
            fx.put(ADDR_SEA_CURRENT_DIR, 1)
            fx.put16(0x20, 0x0200)
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsl(self.labels["ZoraSwim_ApplySeaCurrent"])
            self.assertEqual(fx.get16(0x20), 0x0200, "Sea currents must NEVER push indoors")

            # Dungeon dive via Y press
            fx.add_stub(STUB_CHECK_NEW_Y, "Y_PRESS", 0x60, hook=lambda h: setattr(h.cpu, "c", True))
            fx.calls.clear()
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask"])
            self.assertEqual(fx.get(ADDR_SEA_CURRENT_DIR), 0)
            self.assertEqual(fx.get(0x5D), 0x00)
            self.assertEqual(fx.get(0xEE), 0x00)
            self.assertEqual(fx.get(0x9A), 0x72)
            self.assertEqual(fx.get(0x5E), 0x08)
            self.assertEqual(fx.get(0x0345), 0x00)
            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 0x01)

            # DiveGate_CanSurface returns C=0 -> blocked under deck, stays diving
            fx.put(0x0114, 0x00)
            fx.add_stub(STUB_DIVEGATE, "DiveGate_Deny", 0x6B, hook=lambda h: setattr(h.cpu, "c", False))
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask_dungeon_resurface"])
            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 0x01)
            self.assertEqual(fx.get(0x5D), 0x00)

            # DiveGate_CanSurface returns C=1 + Y pressed -> resurfaces cleanly to swimming
            fx.add_stub(STUB_DIVEGATE, "DiveGate_Allow", 0x6B, hook=lambda h: setattr(h.cpu, "c", True))
            fx.reset_cpu(db=0x07, m8=True, x8=True)
            fx.call_jsr(self.labels["LinkState_UsingZoraMask_dungeon_resurface"])
            self.assertEqual(fx.get(ADDR_ZORA_DIVING), 0x00)
            self.assertEqual(fx.get(0x5D), 0x04)
            self.assertEqual(fx.get(0xEE), 0x01)
            self.assertEqual(fx.get(0x0345), 0x01)
            self.assertEqual(fx.get(0x5E), 0x00)
            self.assertEqual(fx.get(0x9A), 0x62)
        finally:
            fx.close()


if __name__ == "__main__":
    unittest.main()
