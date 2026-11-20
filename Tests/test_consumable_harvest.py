#!/usr/bin/env python3
"""Schema, safety, and compiled 65816 CPU tests for Q-OOS-06 consumable harvesting.

Verifies:
1. Overworld/consumable_harvest.asm pin tables match Scripts/Proposals/plan_consumable_islands.py
   1:1 across all 12 non-sprite harvest pins (Banana, Seashell, Honeycomb, Deku Stick).
2. Core/symbols.asm WRAM layout ($7F57F8-$7F57FB), Sprites/all_sprites.asm Bank $32 include,
   and Masks/mask_routines.asm LinkMain_FrameHook chain contracts.
3. Compiled 65816 execution (Asar + LakeSnes CPU) of Overworld/consumable_harvest.asm:
   - All 12 pins (including wide-area $A8/$A9 parent $A8 at area_x=46, area_y=8) harvest
     into the right SRAM byte, latch once per visit, emit SFX3.$0B, set 12f cooldown,
     and preserve DP $00-$0F.
   - +/- 1 tile radius matches; +/- 2 tiles rejected.
   - Gesture rules: kind 0 (sword, dash, bonk, fresh A) vs kind 1 (shovel, Gust Jar, swim,
     shallow water $0351=$01, sword, fresh A; rejects grass $0351=$02 and dry idle).
   - Per-visit latch persists across pause menu ($10=$0E) and resets on OW area change ($8A)
     or interior entry ($1B=1 / $10=$07).
   - Cap 10 ($0A): active gestures emit SFX2.$3C + 24f cooldown without latching; passive
     seashell wading/swimming stays silent when full.
   - Fast area filter skips unrelated overworld maps with zero side effects.
4. Scripts/Proposals/apply_consumable_islands.py refuses protected live/shared ROM paths
   by default and produces idempotent plans.
"""

from __future__ import annotations

import ctypes as C
import importlib.util
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "Tests"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402

HARVEST_ASM = ROOT / "Overworld" / "consumable_harvest.asm"
SYMBOLS_ASM = ROOT / "Core" / "symbols.asm"
ALL_SPRITES_ASM = ROOT / "Sprites" / "all_sprites.asm"
MASK_ROUTINES_ASM = ROOT / "Masks" / "mask_routines.asm"
PLAN_PATH = ROOT / "Scripts" / "Proposals" / "plan_consumable_islands.py"
APPLY_PATH = ROOT / "Scripts" / "Proposals" / "apply_consumable_islands.py"

LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]

# SRAM addresses
SRAM_BANANAS = 0x7EF38B
SRAM_SEASHELLS = 0x7EF391
SRAM_HONEYCOMB = 0x7EF393
SRAM_DEKUSTICKS = 0x7EF395

# Transient WRAM addresses
WRAM_LAST_AREA = 0x7F57F8
WRAM_LATCH_LO = 0x7F57F9
WRAM_LATCH_HI = 0x7F57FA
WRAM_COOLDOWN = 0x7F57FB

# Game WRAM mirrors (bank $7E)
RAM_GAMEMODE = 0x7E0010
RAM_SUBMODULE = 0x7E0011
RAM_INDOORS = 0x7E001B
RAM_LINK_Y = 0x7E0020
RAM_LINK_X = 0x7E0022
RAM_SWORD = 0x7E003C
RAM_LINK_STATE = 0x7E005D
RAM_OW_AREA = 0x7E008A
RAM_JOY1B_NEW = 0x7E00F6
RAM_SFX2 = 0x7E012E
RAM_SFX3 = 0x7E012F
RAM_GUSTJAR_STATE = 0x7E0273
RAM_FREEZE_LINK = 0x7E02E4
RAM_FEETS = 0x7E0351
RAM_DASHING = 0x7E0372
RAM_USEY2 = 0x7E037A
RAM_ORIGIN_Y = 0x7E0708
RAM_MASK_Y = 0x7E070A
RAM_ORIGIN_X8 = 0x7E070C
RAM_MASK_X2 = 0x7E070E
RAM_MENU_FREEZE = 0x7E0FFC


def _load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


PLAN = _load_module("plan_consumable_islands", PLAN_PATH)
APPLIER = _load_module("apply_consumable_islands", APPLY_PATH)


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
            "cc",
            "-shared",
            "-fPIC",
            "-O2",
            str(lakesnes / "snes" / "cpu.c"),
            str(lakesnes / "snes" / "statehandler.c"),
            "-o",
            str(dll),
        ],
        check=True,
    )
    lib = C.CDLL(str(dll))
    lib.cpu_init.restype = C.POINTER(Cpu)
    lib.cpu_runOpcode.argtypes = [C.POINTER(Cpu)]
    lib.cpu_free.argtypes = [C.POINTER(Cpu)]
    return lib


def _assemble_harvest(folder: Path) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    image = bytearray(b"\xFF" * 0x200000)  # 2 MB LoROM covers Bank $32 ($328000 -> PC $190000)
    rom_path = folder / "harvest_fixture.sfc"
    rom_path.write_bytes(image)

    asm_path = folder / "harness.asm"
    asm_path.write_text(
        "lorom\n"
        f"Bananas                    = ${SRAM_BANANAS:06X}\n"
        f"Seashells                  = ${SRAM_SEASHELLS:06X}\n"
        f"Honeycomb                  = ${SRAM_HONEYCOMB:06X}\n"
        f"DekuSticks                 = ${SRAM_DEKUSTICKS:06X}\n"
        f"ConsumableHarvest_LastArea = ${WRAM_LAST_AREA:06X}\n"
        f"ConsumableHarvest_LatchLo  = ${WRAM_LATCH_LO:06X}\n"
        f"ConsumableHarvest_LatchHi  = ${WRAM_LATCH_HI:06X}\n"
        f"ConsumableHarvest_Cooldown = ${WRAM_COOLDOWN:06X}\n"
        "org $328000\n"
        f'incsrc "{HARVEST_ASM.as_posix()}"\n',
        encoding="utf-8",
    )
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
        cwd=ROOT,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    labels = {
        mm[3]: int(mm[1] + mm[2], 16)
        for mm in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            rom_path.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return rom_path.read_bytes(), labels


def _run_tick(f: Fixture, *, m8: bool = True, x8: bool = True) -> None:
    c = f.cpu
    addr = f.addr("ConsumableHarvest_FrameTick")
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    c.mf = m8
    c.xf = x8
    c.db = 0x3A
    c.dp = 0x0000
    ret_addr = (addr & 0xFF0000) | 0x7000
    f.put(sp, addr >> 16)
    f.put(sp - 1, 0x6F)
    f.put(sp - 2, 0xFF)
    c.sp -= 3
    for _ in range(10000):
        pc = (c.k << 16) | c.pc
        if pc == ret_addr:
            assert c.sp == sp, f"Unbalanced stack: {c.sp:#x} != {sp:#x}"
            assert c.mf == m8 and c.xf == x8, "Processor width flags clobbered"
            assert c.db == 0x3A, f"DBR clobbered: {c.db:#x}"
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError("Instruction ceiling reached in ConsumableHarvest_FrameTick")


def _parse_db_table(asm_text: str, label: str) -> list[int]:
    m = re.search(rf"(?m)^{re.escape(label)}:\s*\n\s*db\s+([^\n;]+)", asm_text)
    if not m:
        raise AssertionError(f"Table {label} not found in {HARVEST_ASM}")
    vals = []
    for tok in m.group(1).split(","):
        tok = tok.strip()
        if tok.startswith("$"):
            vals.append(int(tok[1:], 16))
        else:
            vals.append(int(tok, 10))
    return vals


class ConsumableHarvestContractTests(unittest.TestCase):
    def test_asm_pin_table_matches_planner_1_to_1(self) -> None:
        text = HARVEST_ASM.read_text(encoding="utf-8")
        parents = _parse_db_table(text, "ConsumableHarvest_PinParent")
        xs = _parse_db_table(text, "ConsumableHarvest_PinX")
        ys = _parse_db_table(text, "ConsumableHarvest_PinY")
        offs = _parse_db_table(text, "ConsumableHarvest_PinSramOff")
        kinds = _parse_db_table(text, "ConsumableHarvest_PinKind")
        masks = _parse_db_table(text, "ConsumableHarvest_BitMask")

        expected_rows = [
            row
            for row in PLAN.PLACEMENTS
            if row["supply"] in {"banana", "seashell", "honeycomb", "deku_stick"}
        ]
        self.assertEqual(len(expected_rows), 12)
        self.assertEqual(len(parents), 12)
        self.assertEqual(masks, [1 << (i % 8) for i in range(12)])

        sram_off_map = {
            "banana": 0x00,
            "seashell": 0x06,
            "honeycomb": 0x08,
            "deku_stick": 0x0A,
        }
        kind_map = {
            "banana": 0,
            "seashell": 1,
            "honeycomb": 0,
            "deku_stick": 0,
        }
        for idx, row in enumerate(expected_rows):
            self.assertEqual(parents[idx], row["parent"], row["id"])
            self.assertEqual(xs[idx], row["area_x"], row["id"])
            self.assertEqual(ys[idx], row["area_y"], row["id"])
            self.assertEqual(offs[idx], sram_off_map[row["supply"]], row["id"])
            self.assertEqual(kinds[idx], kind_map[row["supply"]], row["id"])

    def test_wram_and_hook_wiring(self) -> None:
        sym_text = SYMBOLS_ASM.read_text(encoding="utf-8")
        self.assertIn("assert Horse_CgiCache_End < $7F57F8", sym_text)
        self.assertIn("ConsumableHarvest_LastArea = $7F57F8", sym_text)
        self.assertIn("ConsumableHarvest_LatchLo  = $7F57F9", sym_text)
        self.assertIn("ConsumableHarvest_LatchHi  = $7F57FA", sym_text)
        self.assertIn("ConsumableHarvest_Cooldown = $7F57FB", sym_text)

        sprites_text = ALL_SPRITES_ASM.read_text(encoding="utf-8")
        self.assertIn('incsrc "Overworld/consumable_harvest.asm"', sprites_text)

        masks_text = MASK_ROUTINES_ASM.read_text(encoding="utf-8")
        self.assertIn('if defined("CONSUMABLE_HARVEST_DEFINED")', masks_text)
        self.assertIn("JSL ConsumableHarvest_FrameTick", masks_text)


class ConsumableHarvestCpuTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls._tmp = tempfile.TemporaryDirectory(prefix="oos-harvest-cpu-")
        tmp_path = Path(cls._tmp.name)
        cls.lib = _build_cpu_lib(tmp_path)
        cls.rom, cls.labels = _assemble_harvest(tmp_path)

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmp.cleanup()

    def _new_fixture(self) -> Fixture:
        f = Fixture(self.lib, self.rom, self.labels)
        f.put(WRAM_LAST_AREA, 0xFF)
        f.put(RAM_GAMEMODE, 0x09)
        f.put(RAM_SUBMODULE, 0x00)
        f.put(RAM_INDOORS, 0x00)
        return f

    @staticmethod
    def _put16(f: Fixture, addr: int, val: int) -> None:
        f.put(addr, val & 0xFF)
        f.put(addr + 1, (val >> 8) & 0xFF)

    @classmethod
    def _set_area_and_pos(
        cls,
        f: Fixture,
        parent: int,
        area_x: int,
        area_y: int,
        *,
        wide: bool = False,
        tall: bool = False,
    ) -> None:
        origin_x = (parent & 0x07) * 512
        origin_y = ((parent & 0x3F) >> 3) * 512
        f.put(RAM_OW_AREA, parent)
        cls._put16(f, RAM_ORIGIN_Y, origin_y)
        cls._put16(f, RAM_MASK_Y, 0x03F0 if tall else 0x01F0)
        cls._put16(f, RAM_ORIGIN_X8, origin_x >> 3)
        cls._put16(f, RAM_MASK_X2, 0x007E if wide else 0x003E)
        cls._put16(f, RAM_LINK_X, origin_x + area_x * 16)
        cls._put16(f, RAM_LINK_Y, origin_y + area_y * 16)

    def test_all_12_pins_harvest_and_preserve_dp(self) -> None:
        sram_by_supply = {
            "banana": SRAM_BANANAS,
            "seashell": SRAM_SEASHELLS,
            "honeycomb": SRAM_HONEYCOMB,
            "deku_stick": SRAM_DEKUSTICKS,
        }
        expected_rows = [
            row
            for row in PLAN.PLACEMENTS
            if row["supply"] in sram_by_supply
        ]
        for idx, row in enumerate(expected_rows):
            f = self._new_fixture()
            try:
                # Seed recognizable DP bytes $00-$0F to guarantee zero DP clobber
                dp_before = [0xA0 + i for i in range(16)]
                for i, val in enumerate(dp_before):
                    f.put(0x7E0000 + i, val)

                wide = row["parent"] == 0xA8
                self._set_area_and_pos(f, row["parent"], row["area_x"], row["area_y"], wide=wide)
                f.put(RAM_JOY1B_NEW, 0x80)  # fresh A press works on both kinds

                _run_tick(f)

                sram_addr = sram_by_supply[row["supply"]]
                self.assertEqual(f.get(sram_addr), 1, f"Pin {idx} ({row['id']}) did not increment SRAM")
                self.assertEqual(f.get(RAM_SFX3), 0x0B, f"Pin {idx} missing SFX3.$0B")
                self.assertEqual(f.get(WRAM_COOLDOWN), 12)
                if idx < 8:
                    self.assertEqual(f.get(WRAM_LATCH_LO), 1 << idx)
                    self.assertEqual(f.get(WRAM_LATCH_HI), 0)
                else:
                    self.assertEqual(f.get(WRAM_LATCH_LO), 0)
                    self.assertEqual(f.get(WRAM_LATCH_HI), 1 << (idx - 8))

                dp_after = [f.get(0x7E0000 + i) for i in range(16)]
                self.assertEqual(dp_after, dp_before, f"Pin {idx} clobbered DP $00-$0F")
            finally:
                f.close()

    def test_radius_and_latch_pause_reset_behavior(self) -> None:
        f = self._new_fixture()
        try:
            # 2 tiles away from banana_atoll_palm (16,16) -> rejected
            self._set_area_and_pos(f, 0xA5, 18, 16)
            f.put(RAM_SWORD, 0x01)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 0)

            # 1 tile diagonal (15,17) -> accepted!
            self._set_area_and_pos(f, 0xA5, 15, 17)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 1)
            self.assertEqual(f.get(WRAM_LATCH_LO), 0x01)

            # Drain cooldown (12 ticks)
            for _ in range(12):
                _run_tick(f)
            self.assertEqual(f.get(WRAM_COOLDOWN), 0)

            # Same pin cannot be harvested twice on the same visit
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 1)

            # Second palm on same map ($A5, 6,8) still harvests!
            self._set_area_and_pos(f, 0xA5, 6, 8)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 2)
            self.assertEqual(f.get(WRAM_LATCH_LO), 0x03)

            # Drain cooldown and open pause menu ($10=$0E): latches MUST persist
            for _ in range(12):
                _run_tick(f)
            f.put(RAM_GAMEMODE, 0x0E)
            _run_tick(f)
            f.put(RAM_GAMEMODE, 0x09)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 2)
            self.assertEqual(f.get(WRAM_LATCH_LO), 0x03)

            # Entering an interior ($1B=1) resets LastArea -> re-entering $A5 respawns palms
            f.put(RAM_INDOORS, 0x01)
            _run_tick(f)
            self.assertEqual(f.get(WRAM_LAST_AREA), 0xFF)
            f.put(RAM_INDOORS, 0x00)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 3)

            # Leaving to another OW screen ($A4) and returning also resets latches
            self._set_area_and_pos(f, 0xA4, 10, 10)
            _run_tick(f)
            self.assertEqual(f.get(WRAM_LAST_AREA), 0xA4)
            self._set_area_and_pos(f, 0xA5, 16, 16)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_BANANAS), 4)
        finally:
            f.close()

    def test_gesture_classes_and_full_cap_rules(self) -> None:
        # Kind 0 idle walking does NOT trigger; dash/bonk DOES trigger
        f = self._new_fixture()
        try:
            self._set_area_and_pos(f, 0x80, 8, 15)  # honey_glade_west
            _run_tick(f)
            self.assertEqual(f.get(SRAM_HONEYCOMB), 0)

            f.put(RAM_DASHING, 0x01)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_HONEYCOMB), 1)
        finally:
            f.close()

        # Kind 1 (seashell): tall grass ($0351=$02) does NOT trigger; shallow wade ($0351=$01),
        # shovel ($037A&$01), Gust Jar ($0273), and swim ($5D=$04) ALL trigger.
        for label, setup in (
            ("wade", lambda fx: fx.put(RAM_FEETS, 0x01)),
            ("shovel", lambda fx: fx.put(RAM_USEY2, 0x01)),
            ("gust_jar", lambda fx: fx.put(RAM_GUSTJAR_STATE, 0x01)),
            ("swim", lambda fx: fx.put(RAM_LINK_STATE, 0x04)),
        ):
            f = self._new_fixture()
            try:
                self._set_area_and_pos(f, 0xA2, 25, 15)
                f.put(RAM_FEETS, 0x02)  # tall grass must not trigger
                _run_tick(f)
                self.assertEqual(f.get(SRAM_SEASHELLS), 0, f"{label} false-triggered on grass")

                f.put(RAM_FEETS, 0x00)
                setup(f)
                _run_tick(f)
                self.assertEqual(f.get(SRAM_SEASHELLS), 1, f"{label} failed to trigger seashell")
            finally:
                f.close()

        # Cap 10 ($0A): active gesture buzzes without latching; passive wading stays silent
        f = self._new_fixture()
        try:
            f.put(SRAM_SEASHELLS, 10)
            self._set_area_and_pos(f, 0x92, 21, 13)
            f.put(RAM_FEETS, 0x01)  # passive wade while full -> silent!
            _run_tick(f)
            self.assertEqual(f.get(SRAM_SEASHELLS), 10)
            self.assertEqual(f.get(RAM_SFX2), 0x00)
            self.assertEqual(f.get(WRAM_COOLDOWN), 0)

            # Active shovel press while full -> SFX2.$3C buzz + 24f cooldown, latch stays 0
            f.put(RAM_USEY2, 0x01)
            _run_tick(f)
            self.assertEqual(f.get(SRAM_SEASHELLS), 10)
            self.assertEqual(f.get(RAM_SFX2), 0x3C)
            self.assertEqual(f.get(WRAM_COOLDOWN), 24)
            self.assertEqual(f.get(WRAM_LATCH_LO), 0)
        finally:
            f.close()


class ApplyConsumableIslandsSafetyTests(unittest.TestCase):
    def test_refuses_protected_live_and_shared_roms(self) -> None:
        for marker in APPLIER.LIVE_ROM_MARKERS:
            self.assertTrue(APPLIER.is_protected_rom(marker), f"Missed guard for {marker}")
        self.assertFalse(APPLIER.is_protected_rom(Path("/tmp/oos-track2/dryrun.sfc")))

    def test_idempotent_plan_generation(self) -> None:
        b0_before = [
            {"list_index": 0, "sprite_id": "0x52", "tile": "(21,11)"},
            {"list_index": 1, "sprite_id": "0x52", "tile": "(5,19)"},
        ]
        b6_before: list[dict[str, object]] = []
        ops = APPLIER.plan_edits(b0_before, b6_before)
        self.assertEqual([o["action"] for o in ops], ["move_sprite", "add_sprite"])
        self.assertEqual(ops[0]["list_index"], 0)
        self.assertEqual(ops[0]["to_tile"], [16, 12])
        self.assertEqual(ops[1]["phase"], 1)
        self.assertEqual(ops[1]["tile"], [19, 15])

        b0_after = [
            {"list_index": 0, "sprite_id": "0x52", "tile": "(16,12)"},
            {"list_index": 1, "sprite_id": "0x52", "tile": "(5,19)"},
        ]
        b6_after = [{"list_index": 0, "sprite_id": "0x52", "tile": "(19,15)"}]
        ops_after = APPLIER.plan_edits(b0_after, b6_after)
        self.assertEqual([o["action"] for o in ops_after], ["already_applied", "already_applied"])


if __name__ == "__main__":
    unittest.main()
