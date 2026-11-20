#!/usr/bin/env python3
"""Compiled 65816 unit tests for QUEUE324:
1. Message $021B rename ("Start From Eon Abyss" / "Start From Kalyxo") + contract.
2. Startup spawn-location green-background fix in Oracle_CgramAuxToMain_Impl.
3. Abyss Windmill ($00C9) spawn routing in AbyssSpawnMenu_Select.
4. GBC Link live ($7EC6E0) + aux ($7EC4E0) palette persistence on Dark World /
   Eon Abyss spawn, dungeon entry, transitions, and mirror warps.
"""

from __future__ import annotations

import ctypes as C
import json
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
sys.path.insert(0, str(ROOT / "Scripts" / "Generate"))

from d4_compiled_fight_check import Cpu, Fixture  # noqa: E402
import validate_expanded_message_source as msg_contract  # noqa: E402

LAKESNES_CANDIDATES = [
    Path(os.environ["LAKESNES_DIR"]) if "LAKESNES_DIR" in os.environ else None,
    ROOT.parent / "lakesnes",
    Path("/Users/scawful/src/hobby/lakesnes"),
]

GBC_GREEN_WORDS = (
    0x0000, 0x7FFF, 0x237E, 0xB711, 0x369E, 0x14A5, 0x01FF, 0x1078,
    0x46FF, 0x22A2, 0x3B68, 0x0A4A, 0x12EF, 0x2A5C, 0x1571, 0x7A18,
)
GBC_BLUE_WORDS = (
    0x0000, 0x7FFF, 0x237E, 0xB711, 0x369E, 0x14A5, 0x01FF, 0x1078,
    0x46FF, 0x4D25, 0x3B68, 0x0A4A, 0x12EF, 0x2A5C, 0x1571, 0x7A18,
)
GBC_RED_WORDS = (
    0x0000, 0x7FFF, 0x237E, 0xB711, 0x369E, 0x14A5, 0x01FF, 0x1078,
    0x46FF, 0x081D, 0x3B68, 0x0A4A, 0x12EF, 0x2A5C, 0x1571, 0x7A18,
)


def _words_to_bytes(words: tuple[int, ...]) -> bytes:
    return b"".join(struct.pack("<H", w) for w in words)


def _extract_block(text: str, label: str) -> str:
    start = text.index(label + ":")
    opened = text.index("{", start)
    depth = 1
    idx = opened + 1
    while depth:
        depth += (text[idx] == "{") - (text[idx] == "}")
        idx += 1
    return text[start:idx] + "\n"


def _extract_data_table(text: str, label: str) -> str:
    m = re.search(
        rf"^{re.escape(label)}:\n(?:[ \t]+dw[^\n]+\n)+",
        text,
        re.MULTILINE,
    )
    assert m is not None, f"Data table {label} not found"
    return m.group(0)


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


def _assemble(folder: Path, source: str) -> tuple[bytes, dict[str, int]]:
    folder.mkdir(parents=True, exist_ok=True)
    asm = folder / "fixture.asm"
    image = folder / "fixture.sfc"
    asm.write_text(source, encoding="utf-8")
    image.write_bytes(b"\xFF" * 0x200000)
    proc = subprocess.run(
        ["asar", "--no-title-check", "--fix-checksum=off", "--symbols=wla", str(asm), str(image)],
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    labels = {
        m[3]: int(m[1] + m[2], 16)
        for m in re.finditer(
            r"(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$",
            image.with_suffix(".sym").read_text(encoding="utf-8"),
        )
    }
    return image.read_bytes(), labels


def _run_until_stop(f: Fixture, entry: str, stops: set[int] | None = None, long_return: bool = True) -> int:
    c = f.cpu
    addr = f.addr(entry)
    sp = c.sp
    c.k = addr >> 16
    c.pc = addr & 0xFFFF
    ret_addr = (addr & 0xFF0000) | 0x7000
    if long_return:
        f.put(sp, addr >> 16)
        f.put(sp - 1, 0x6F)
        f.put(sp - 2, 0xFF)
        c.sp -= 3
    else:
        f.put(sp, 0x6F)
        f.put(sp - 1, 0xFF)
        c.sp -= 2
    stop_set = set(stops or ()) | {ret_addr}
    for _ in range(20000):
        pc = (c.k << 16) | c.pc
        if pc in stop_set:
            if pc == ret_addr:
                assert c.sp == sp, f"Unbalanced stack in {entry}: {c.sp:#x} != {sp:#x}"
            return pc
        if pc in f.stubs:
            f.stub(f.stubs[pc])
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(f"Instruction ceiling reached in {entry}")


class SramFixture(Fixture):
    """Fixture with $70:0000-$70:1FFF battery SRAM mapped for File Select tests."""

    def __init__(self, lib, rom, labels):
        super().__init__(lib, rom, labels)
        self.sram = bytearray(0x2000)

    def read(self, a):
        if (a >> 16) == 0x70 and (a & 0xFFFF) < len(self.sram):
            return self.sram[a & 0xFFFF]
        return super().read(a)

    def write(self, a, v):
        if (a >> 16) == 0x70 and (a & 0xFFFF) < len(self.sram):
            self.sram[a & 0xFFFF] = v & 0xFF
            self.writes.append((a, v & 0xFF))
            return
        super().write(a, v)

    def seed_slot(
        self,
        slot: int,
        *,
        valid: bool = True,
        saved_world: int = 0x00,
        game_state: int = 0x00,
        armor: int = 0x00,
        sword_flags: int = 0x00,
    ) -> int:
        off = slot * 0x500
        self.word(0x7003E5 + off, 0x55AA if valid else 0x0000)
        self.put(0x7003CA + off, saved_world)
        self.put(0x7003C5 + off, game_state)
        self.put(0x70035B + off, armor)
        self.put(0x7003BD + off, sword_flags)
        return off


class StartupGbcSpawnTests(unittest.TestCase):
    _tmpdir: tempfile.TemporaryDirectory[str]
    _lib: C.CDLL
    _cgram_rom: bytes
    _cgram_labels: dict[str, int]
    _spawn_rom: bytes
    _spawn_labels: dict[str, int]
    _gbc_rom: bytes
    _gbc_labels: dict[str, int]
    _savequit_rom: bytes
    _savequit_labels: dict[str, int]

    @classmethod
    def setUpClass(cls) -> None:
        cls._tmpdir = tempfile.TemporaryDirectory(prefix="oos-q324-unit-")
        base = Path(cls._tmpdir.name)
        cls._lib = _build_cpu_lib(base)

        mask_src = (ROOT / "Masks" / "mask_routines.asm").read_text(encoding="utf-8")
        cgram_body = _extract_block(mask_src, "Oracle_CgramAuxToMain_Impl")
        cls._cgram_rom, cls._cgram_labels = _assemble(
            base / "cgram",
            "lorom\n"
            "!ENABLE_HORSE_FORM = 0\n"
            "!CurrentMask = $02B2\n"
            "RefreshOverworldBackdrop = $018000\n"
            "org $2C8000\n"
            + cgram_body,
        )

        time_src = (ROOT / "Overworld" / "time_system.asm").read_text(encoding="utf-8")
        structs_src = (ROOT / "Core" / "structs.asm").read_text(encoding="utf-8")
        ts_start = structs_src.index("struct TimeState")
        ts_end = structs_src.index("endstruct", ts_start) + len("endstruct")
        ts_struct = structs_src[ts_start:ts_end] + "\n"
        savequit_body = "\n".join([
            _extract_block(mask_src, "ForceResetMask_SaveAndQuit"),
            _extract_block(time_src, "FixSaveAndQuit"),
        ])
        cls._savequit_rom, cls._savequit_labels = _assemble(
            base / "savequit",
            "lorom\n"
            "!ENABLE_HORSE_FORM = 1\n"
            "!KORL_MOUNT_DEFINED = 1\n"
            "!CurrentMask = $02B2\n"
            "!LinkGraphics = $BC\n"
            "!ZoraDiving = $0AAB\n"
            "DekuFloating = $70\n"
            "SpecialOverworld_VortexWorld = $7EC138\n"
            "GameState = $7EF3C5\n"
            "DekuStick_Drop = $018200\n"
            "GaroMask_Clear = $018210\n"
            "HorseForm_ClearState = $018220\n"
            "KORL_ClearState = $018230\n"
            "Palette_ArmorAndGloves = $018240\n"
            + ts_struct
            + "org $2C8000\n"
            + savequit_body,
        )

        spawn_src = (ROOT / "Overworld" / "abyss_spawn_menu.asm").read_text(encoding="utf-8")
        spawn_body = (
            _extract_block(spawn_src, "AbyssSpawnMenu_Check")
            + "\n"
            + _extract_block(spawn_src, "AbyssSpawnMenu_Select")
        )
        cls._spawn_rom, cls._spawn_labels = _assemble(
            base / "spawn",
            "lorom\n"
            "SavedWorld = $7EF3CA\n"
            "SpawnPoint = $7EF3C8\n"
            "GameState = $7EF3C5\n"
            "GoldstarOwned = $7EF3A9\n"
            "!GameState_FaroreRescued = $03\n"
            "org $2C8000\n"
            + spawn_body,
        )

        gbc_src = (ROOT / "Masks" / "gbc_form.asm").read_text(encoding="utf-8")
        tunic_src = (ROOT / "Menu" / "menu_tunic.asm").read_text(encoding="utf-8")
        tunic_macro_start = tunic_src.index("macro Tunic_Resolve")
        tunic_macro_end = tunic_src.index("endmacro", tunic_macro_start) + len("endmacro")
        tunic_macro = tunic_src[tunic_macro_start:tunic_macro_end] + "\n"
        tunic_fn = _extract_block(tunic_src, "Tunic_GetWorn")
        fs_tunic_start = tunic_src.index("Tunic_FileSelectSlot1:")
        fs_tunic_end = tunic_src.index("RTL", tunic_src.index("Tunic_FileSelectReturn:")) + len("RTL")
        fs_tunic_fns = tunic_src[fs_tunic_start:fs_tunic_end] + "\n"

        gbc_body = "\n".join([
            _extract_block(gbc_src, "UpdateGbcPalette"),
            _extract_data_table(gbc_src, "GameboyLinkPalette"),
            _extract_data_table(gbc_src, "GameboyLinkBlueMail"),
            _extract_data_table(gbc_src, "GameboyLinkRedMail"),
            _extract_block(gbc_src, "LinkState_GameboyInDungeonEntrance"),
            _extract_block(gbc_src, "LoadOverworld_CheckForGbcLink"),
            _extract_block(gbc_src, "OverworldTransition_CheckForGbcLink"),
            _extract_block(gbc_src, "MirrorWarp_PearllessArrival"),
            _extract_block(gbc_src, "MirrorWarp_PearlArrival"),
            _extract_block(gbc_src, "FileSelect_IsSlotGbcEligible"),
            _extract_block(gbc_src, "FileSelect_LoadPalettes"),
            _extract_block(gbc_src, "FileSelect_GetSlotTunic"),
            _extract_data_table(gbc_src, "FileSelect_SlotSramOffsets"),
            _extract_data_table(gbc_src, "FileSelect_SlotCgramOffsets"),
            _extract_block(gbc_src, "FileSelect_SelectSlotLinkSprite"),
        ])
        cls._gbc_rom, cls._gbc_labels = _assemble(
            base / "gbc",
            "lorom\n"
            "!CurrentMask = $02B2\n"
            "!SwordSlot_TunicMask = $38\n"
            "!GameState_FaroreRescued = $03\n"
            "SwordSlotFlags = $7EF3BD\n"
            "Armor = $7EF35B\n"
            "SavedWorld = $7EF3CA\n"
            "Palette_ArmorAndGloves = $018100\n"
            "LinkGraphics_ApplyD8Base = $018110\n"
            "Link_HandleMovingAnimation_FullLongEntry = $018120\n"
            "ShieldWorld_SyncBoth = $018130\n"
            "org $018130 : RTL\n"
            "org $2C8000\n"
            + tunic_macro
            + tunic_fn
            + "\n"
            + fs_tunic_fns
            + "\n"
            + gbc_body,
        )

    @classmethod
    def tearDownClass(cls) -> None:
        cls._tmpdir.cleanup()

    # ------------------------------------------------------------------
    # Deliverable 2a: Message $021B ("Start From Eon Abyss" / "Kalyxo")
    # ------------------------------------------------------------------
    def test_message_21b_uses_eon_abyss_not_pyramid_and_passes_contract(self) -> None:
        bundle = json.loads((ROOT / "Data" / "dialogue" / "expanded_messages.json").read_text(encoding="utf-8"))
        entry = next(m for m in bundle["messages"] if m["id"] == 142)
        self.assertEqual(
            entry["text"],
            "[P:00][S:00]>Start From Eon Abyss[2]  Start From Kalyxo[CH2]",
        )
        self.assertIn("Eon Abyss", entry["text"])
        self.assertNotIn("Pyramid", entry["text"])
        self.assertNotIn("PYRAMID", entry["text"])

        contract = msg_contract.validate_contract(ROOT)
        self.assertEqual(contract.message_count, 157)

        registry = json.loads((ROOT / "Data" / "dialogue" / "message_registry.json").read_text(encoding="utf-8"))
        reg_21b = next(r for r in registry["ranges"] if r["start"] == "0x21B")
        self.assertIn("Start From Eon Abyss", reg_21b["purpose"])
        self.assertIn("$00C9", reg_21b["purpose"])

    # ------------------------------------------------------------------
    # Deliverable 1: Green-background fix on Module05 / Module1B
    # ------------------------------------------------------------------
    def test_cgram_copy_skips_overworld_backdrop_for_spawn_select_modules(self) -> None:
        cases = [
            # (module $10, saved_module $010C, indoor $1B, expect_backdrop_call)
            (0x05, 0x00, 0, False),  # Module05_LoadFile direct
            (0x1B, 0x00, 0, False),  # Module1B_SpawnSelect direct
            (0x0E, 0x05, 0, False),  # Module05 -> Interface_PrepAndDisplayMessage -> Underworld_LoadPalettes
            (0x0E, 0x1B, 0, False),  # Module1B -> Kalyxo step-2 -> Interface_PrepAndDisplayMessage -> Underworld_LoadPalettes
            (0x07, 0x00, 1, False),  # Indoors ($1B=1)
            (0x08, 0x00, 0, True),   # Module08_OverworldLoad
            (0x09, 0x00, 0, True),   # Module09_Overworld
            (0x0B, 0x00, 0, True),   # Module0B_SpecialOverworld
            (0x0E, 0x09, 0, True),   # Interface over Overworld
            (0x0E, 0x0B, 0, True),   # Interface over Special Overworld
        ]
        for module, saved_mod, indoor, expect_call in cases:
            with self.subTest(module=hex(module), saved_mod=hex(saved_mod), indoor=indoor):
                f = Fixture(self._lib, self._cgram_rom, self._cgram_labels)
                f.stubs = {0x018000: "RefreshOverworldBackdrop"}
                try:
                    # Seed aux $7EC300 = black ($0000) and live $7EC500 = sentinel green ($2669)
                    f.put(0x7EC300, 0x00)
                    f.put(0x7EC301, 0x00)
                    f.put(0x7EC500, 0x69)
                    f.put(0x7EC501, 0x26)
                    f.put(0x0010, module)
                    f.put(0x010C, saved_mod)
                    f.put(0x001B, indoor)
                    f.put(0x02B2, 0x00)
                    f.put(0x0015, 0x00)
                    f.cpu.db = 0x3A
                    f.call("Oracle_CgramAuxToMain_Impl", long_return=True, x=0x40)
                    self.assertEqual(
                        f.calls,
                        ["RefreshOverworldBackdrop"] if expect_call else [],
                    )
                    self.assertEqual(f.get(0x7EC500), 0x00)
                    self.assertEqual(f.get(0x7EC501), 0x00)
                    self.assertEqual(f.get(0x0015), 0x01)
                    self.assertTrue(f.cpu.mf and f.cpu.xf)
                finally:
                    f.close()

    # ------------------------------------------------------------------
    # Deliverable 2b: AbyssSpawnMenu_Select spawns at Abyss Windmill $00C9
    # ------------------------------------------------------------------
    def test_abyss_spawn_menu_option0_spawns_outside_windmill_room_00c9(self) -> None:
        f = Fixture(self._lib, self._spawn_rom, self._spawn_labels)
        f.stubs = {
            0x0DE395: "SearchForEquippedItem_long",
            0x0DFA6C: "RebuildHUD_long2",
            0x0DDD32: "UpdateEquippedItem_long",
        }
        try:
            f.put(0x7EF3CA, 0x40)  # SavedWorld = Abyss
            f.put(0x1CE8, 0x00)    # Choice 0 = Start From Eon Abyss
            f.put(0x009B, 0xC0)    # Stale HDMA bits
            f.put(0x010A, 0x01)
            f.put(0x04AA, 0x01)
            f.put(0x0011, 0x02)
            f.put(0x00B0, 0x05)
            f.put(0x00A1, 0xFF)
            _run_until_stop(f, "AbyssSpawnMenu_Select")
            self.assertEqual(f.get(0x00A0) | (f.get(0x00A1) << 8), 0x00C9)
            self.assertEqual(f.get(0x0010), 0x08)
            self.assertEqual(f.get(0x0011), 0x00)
            self.assertEqual(f.get(0x00B0), 0x00)
            self.assertEqual(f.get(0x009B), 0x00)
            self.assertEqual(f.get(0x010A), 0x00)
            self.assertEqual(f.get(0x04AA), 0x00)
            self.assertEqual(
                f.calls,
                ["SearchForEquippedItem_long", "RebuildHUD_long2", "UpdateEquippedItem_long"],
            )
        finally:
            f.close()

    def test_abyss_spawn_menu_option1_kalyxo_routes_to_light_world_menu(self) -> None:
        for goldstar_owned, hookshot_slot, expected_msg in [
            (0x00, 0x02, 0x0184),  # Switch Hook alone ($7EF342=2) must NOT unlock Mountain Cave
            (0x01, 0x01, 0x0185),  # GoldstarOwned ($7EF3A9=1) unlocks Mountain Cave
        ]:
            with self.subTest(goldstar_owned=goldstar_owned, hookshot_slot=hookshot_slot):
                f = Fixture(self._lib, self._spawn_rom, self._spawn_labels)
                try:
                    f.put(0x7EF3CA, 0x40)
                    f.put(0x1CE8, 0x01)    # Choice 1 = Start From Kalyxo
                    f.put(0x7EF3D6, 0x04)  # Hall of Secrets unlocked
                    f.put(0x7EF3A9, goldstar_owned)
                    f.put(0x7EF342, hookshot_slot)
                    f.put(0x00BC, 0x3B)
                    f.put(0x02B2, 0x06)
                    stop = _run_until_stop(f, "AbyssSpawnMenu_Select", stops={0x0281ED})
                    self.assertEqual(stop, 0x0281ED)
                    self.assertEqual(f.get(0x7EF3CA), 0x00)
                    self.assertEqual(f.get(0x00BC), 0x10)
                    self.assertEqual(f.get(0x02B2), 0x00)
                    self.assertEqual(f.cpu.x, expected_msg)
                finally:
                    f.close()

    # ------------------------------------------------------------------
    # Deliverable 3: GBC Link palette on Dark World / Eon Abyss spawn
    # ------------------------------------------------------------------
    def test_load_overworld_gbc_sets_both_live_and_aux_palettes_without_clobber(self) -> None:
        tunic_cases = [
            # (armor, sword_slot_flags, expected_palette)
            (0, 0x00, _words_to_bytes(GBC_GREEN_WORDS)),
            (1, 0x00, _words_to_bytes(GBC_BLUE_WORDS)),
            (2, 0x00, _words_to_bytes(GBC_RED_WORDS)),
            # Owned Red Mail (2), explicitly wearing Green (1<<3 | $80 = $88)
            (2, 0x88, _words_to_bytes(GBC_GREEN_WORDS)),
            # Owned Red Mail (2), explicitly wearing Blue (2<<3 | $80 = $90)
            (2, 0x90, _words_to_bytes(GBC_BLUE_WORDS)),
        ]
        for armor, flags, expected in tunic_cases:
            with self.subTest(armor=armor, flags=hex(flags)):
                f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
                f.stubs = {0x018100: "Palette_ArmorAndGloves"}
                try:
                    # Fill both buffers with sentinel garbage before spawning
                    for i in range(32):
                        f.put(0x7EC4E0 + i, 0xAA)
                        f.put(0x7EC6E0 + i, 0x55)
                    f.put(0x7EF3CA, 0x40)  # SavedWorld = Abyss
                    f.put(0x7EF35B, armor)
                    f.put(0x7EF3BD, flags)
                    f.put(0x02B2, 0x00)
                    f.put(0x00BC, 0x10)
                    f.put(0x00B0, 0x03)
                    f.put(0x0011, 0x02)
                    f.put(0x0015, 0x00)
                    _run_until_stop(f, "LoadOverworld_CheckForGbcLink")

                    live = bytes(f.get(0x7EC6E0 + i) for i in range(32))
                    aux = bytes(f.get(0x7EC4E0 + i) for i in range(32))
                    self.assertEqual(live, expected, "Live CGRAM $7EC6E0 mismatch")
                    self.assertEqual(aux, expected, "Aux/fade buffer $7EC4E0 mismatch")
                    self.assertEqual(f.get(0x02B2), 0x06)
                    self.assertEqual(f.get(0x00BC), 0x3B)
                    self.assertEqual(f.get(0x00B0), 0x00)
                    self.assertEqual(f.get(0x0011), 0x00)
                    self.assertEqual(f.get(0x0015), 0x01)
                    self.assertEqual(f.calls, [], "Palette_ArmorAndGloves must not run after UpdateGbcPalette")
                    self.assertTrue(f.cpu.mf and f.cpu.xf)
                finally:
                    f.close()

    def test_load_overworld_preserves_light_world_and_active_masks(self) -> None:
        # Light World clears mask 0/6 and invokes Palette_ArmorAndGloves
        f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {0x018100: "Palette_ArmorAndGloves"}
        try:
            f.put(0x7EF3CA, 0x00)
            f.put(0x02B2, 0x06)
            f.put(0x00BC, 0x3B)
            _run_until_stop(f, "LoadOverworld_CheckForGbcLink")
            self.assertEqual(f.get(0x02B2), 0x00)
            self.assertEqual(f.calls, ["Palette_ArmorAndGloves"])
        finally:
            f.close()

        # Active masks (Deku=1, Zora=2, Wolf=3, Bunny=4, Minish=5 in DW, Garo=8) stay preserved
        for mask, bank in [(1, 0x35), (2, 0x36), (3, 0x38), (4, 0x37), (5, 0x39), (8, 0x42)]:
            with self.subTest(mask=mask, bank=hex(bank)):
                f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
                f.stubs = {0x018100: "Palette_ArmorAndGloves"}
                try:
                    f.put(0x7EF3CA, 0x40)
                    f.put(0x02B2, mask)
                    f.put(0x00BC, bank)
                    _run_until_stop(f, "LoadOverworld_CheckForGbcLink")
                    self.assertEqual(f.get(0x02B2), mask)
                    self.assertEqual(f.get(0x00BC), bank)
                    self.assertEqual(f.calls, ["Palette_ArmorAndGloves"])
                finally:
                    f.close()

    def test_dungeon_entrance_and_transition_and_mirror_warps_sync_both_buffers(self) -> None:
        expected = _words_to_bytes(GBC_BLUE_WORDS)

        # LinkState_GameboyInDungeonEntrance (non-D8: stub returns C=0)
        f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {
            0x018110: "LinkGraphics_ApplyD8Base",
            0x0AFE80: "Underworld_HandleLayerEffect",
        }
        try:
            f.put(0x7EF3CA, 0x40)
            f.put(0x7EF35B, 0x01)  # Blue Mail
            f.put(0x02B2, 0x00)
            f.put(0x00BC, 0x10)
            f.cpu.c = 0
            _run_until_stop(f, "LinkState_GameboyInDungeonEntrance")
            self.assertEqual(f.get(0x02B2), 0x06)
            self.assertEqual(f.get(0x00BC), 0x3B)
            self.assertEqual(bytes(f.get(0x7EC6E0 + i) for i in range(32)), expected)
            self.assertEqual(bytes(f.get(0x7EC4E0 + i) for i in range(32)), expected)
        finally:
            f.close()

        # OverworldTransition_CheckForGbcLink
        f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {0x018120: "Link_HandleMovingAnimation_FullLongEntry"}
        try:
            f.put(0x7EF3CA, 0x40)
            f.put(0x7EF35B, 0x01)
            f.put(0x02B2, 0x00)
            f.put(0x00BC, 0x10)
            _run_until_stop(f, "OverworldTransition_CheckForGbcLink")
            self.assertEqual(f.get(0x02B2), 0x06)
            self.assertEqual(f.get(0x00BC), 0x3B)
            self.assertEqual(bytes(f.get(0x7EC6E0 + i) for i in range(32)), expected)
            self.assertEqual(bytes(f.get(0x7EC4E0 + i) for i in range(32)), expected)
        finally:
            f.close()

        # MirrorWarp_PearlArrival and MirrorWarp_PearllessArrival
        for routine, pearl in [("MirrorWarp_PearllessArrival", 0), ("MirrorWarp_PearlArrival", 1)]:
            with self.subTest(routine=routine):
                f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
                try:
                    f.put(0x0010, 0x15)
                    f.put(0x7EF3CA, 0x40)
                    f.put(0x7EF357, pearl)
                    f.put(0x7EF35B, 0x01)
                    f.put(0x02B2, 0x00)
                    f.put(0x00BC, 0x10)
                    _run_until_stop(f, routine)
                    self.assertEqual(f.get(0x02B2), 0x06)
                    self.assertEqual(f.get(0x00BC), 0x3B)
                    self.assertEqual(bytes(f.get(0x7EC6E0 + i) for i in range(32)), expected)
                    self.assertEqual(bytes(f.get(0x7EC4E0 + i) for i in range(32)), expected)
                finally:
                    f.close()

    # ------------------------------------------------------------------
    # Save & Quit / File Select GBC Reset & Per-Slot Isolation Tests
    # ------------------------------------------------------------------
    def test_save_and_quit_unconditionally_resets_gbc_and_mask_form_even_in_dark_world(self) -> None:
        for world in (0x00, 0x40):
            for mask, bank in [(0x06, 0x3B), (0x01, 0x35), (0x05, 0x39), (0x08, 0x42), (0x00, 0x3B)]:
                with self.subTest(world=hex(world), mask=hex(mask), bank=hex(bank)):
                    f = Fixture(self._lib, self._savequit_rom, self._savequit_labels)
                    f.stubs = {
                        0x018200: "DekuStick_Drop",
                        0x018210: "GaroMask_Clear",
                        0x018220: "HorseForm_ClearState",
                        0x018230: "KORL_ClearState",
                        0x018240: "Palette_ArmorAndGloves",
                    }
                    try:
                        f.cpu.db = 0x09  # Module17_SaveAndQuit runs in bank $09
                        f.put(0x0FFF, world)
                        f.put(0x02B2, mask)
                        f.put(0x00BC, bank)
                        f.put(0x0070, 0x01)   # DekuFloating
                        f.put(0x0AAB, 0x01)   # ZoraDiving
                        f.put(0x0095, 0x00)
                        _run_until_stop(f, "ForceResetMask_SaveAndQuit")
                        self.assertEqual(f.get(0x02B2), 0x00)
                        self.assertEqual(f.get(0x00BC), 0x10)
                        self.assertEqual(f.get(0x0070), 0x00)
                        self.assertEqual(f.get(0x0AAB), 0x00)
                        self.assertEqual(f.get(0x0095), 0x0F)
                        self.assertIn("Palette_ArmorAndGloves", f.calls)
                        self.assertTrue(f.cpu.mf and f.cpu.xf)
                    finally:
                        f.close()

    def test_gameover_save_and_quit_hook_resets_gbc_and_preserves_gamestate_flags(self) -> None:
        for game_state in (0x00, 0x02, 0x03):
            with self.subTest(game_state=game_state):
                f = Fixture(self._lib, self._savequit_rom, self._savequit_labels)
                try:
                    f.cpu.db = 0x09
                    f.put(0x7EC138, 0x40)
                    f.put(0x7EE000, 0x15)
                    f.put(0x7EE007, 0x00)
                    f.put(0x02B2, 0x06)
                    f.put(0x00BC, 0x3B)
                    f.put(0x7EF3C5, game_state)
                    _run_until_stop(f, "FixSaveAndQuit")
                    self.assertEqual(f.get(0x02B2), 0x00)
                    self.assertEqual(f.get(0x00BC), 0x10)
                    self.assertEqual(f.get(0x7EC138), 0x00)
                    self.assertEqual(f.get(0x7EE000), 0x08)
                    self.assertEqual(f.get(0x7EE007), 0x01)
                    self.assertEqual(f.cpu.a & 0xFF, game_state)
                    self.assertEqual(f.cpu.z, game_state == 0)
                finally:
                    f.close()

    def test_abyss_spawn_menu_check_gates_post_intro_vs_intro_abyss_lock(self) -> None:
        # GameState < 3 in Dark World -> vanilla Abyss load ($028196), Kalyxo not selectable
        # GameState >= 3 outdoors in Dark World -> AbyssSpawnMenu ($0281ED), Kalyxo selectable
        for game_state, expected_stop, expected_x in [
            (0x02, 0x028196, 0x0000),
            (0x03, 0x0281ED, 0x021B),
        ]:
            with self.subTest(game_state=game_state):
                f = Fixture(self._lib, self._spawn_rom, self._spawn_labels)
                try:
                    f.put(0x7EF3CA, 0x40)
                    f.put(0x7EF3C5, game_state)
                    f.put(0x001B, 0x00)
                    f.put(0x7EC011, 0x00)
                    f.put(0x010A, 0x00)
                    f.cpu.z = False  # SavedWorld != 0
                    stop = _run_until_stop(f, "AbyssSpawnMenu_Check", stops={0x028196, 0x0281ED})
                    self.assertEqual(stop, expected_stop)
                    if expected_x:
                        self.assertEqual(f.cpu.x, expected_x)
                finally:
                    f.close()

    def test_file_select_slot_eligibility_oam_and_real_gbc_palettes_isolated(self) -> None:
        # Slot 0: Light World Green Mail -> normal Link ($00/$02, N=0, $30/$70)
        # Slot 1: Intro Abyss-locked (SavedWorld=$40, GameState=2, Blue Mail) -> GBC Link ($80/$82, N=1, $35/$75) + GameboyLinkBlueMail
        # Slot 2: Post-intro Abyss (SavedWorld=$40, GameState=3, Green worn over Red Mail) -> normal Link ($00/$02, N=0, $38/$78)
        f = SramFixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {0x1BEF96: "Palettes_LoadForFileSelect"}
        try:
            off0 = f.seed_slot(0, valid=True, saved_world=0x00, game_state=0x03, armor=0x00, sword_flags=0x80)
            off1 = f.seed_slot(1, valid=True, saved_world=0x40, game_state=0x02, armor=0x01, sword_flags=0x80)
            off2 = f.seed_slot(2, valid=True, saved_world=0x40, game_state=0x03, armor=0x02, sword_flags=0x88)

            # Seed sentinel normal-Link / sword-shield / fairy palettes in CGRAM buffers
            for slot in range(3):
                base_off = slot * 0x40
                for c_idx in range(1, 16):
                    sentinel = 0x1100 + slot * 0x20 + c_idx
                    for buf in (0x7EC400, 0x7EC600):
                        f.word(buf + base_off + c_idx * 2, sentinel)
                for extra in range(0x20, 0x40, 2):
                    val = 0x2200 + slot * 0x20 + extra
                    for buf in (0x7EC400, 0x7EC600):
                        f.word(buf + base_off + extra, val)

            f.cpu.db = 0x0C
            _run_until_stop(f, "FileSelect_LoadPalettes")
            self.assertEqual(f.calls, ["Palettes_LoadForFileSelect"])
            self.assertTrue(f.cpu.mf and f.cpu.xf)

            # Slot 0 (LW): untouched normal sentinel palette
            for c_idx in range(1, 16):
                want = 0x1100 + c_idx
                self.assertEqual(f.get(0x7EC600 + c_idx * 2) | (f.get(0x7EC601 + c_idx * 2) << 8), want)
                self.assertEqual(f.get(0x7EC400 + c_idx * 2) | (f.get(0x7EC401 + c_idx * 2) << 8), want)

            # Slot 1 (Intro Abyss-locked, Blue Mail): real GameboyLinkBlueMail (colors 1..15)
            blue_bytes = _words_to_bytes(GBC_BLUE_WORDS)[2:]
            self.assertEqual(bytes(f.get(0x7EC642 + i) for i in range(30)), blue_bytes)
            self.assertEqual(bytes(f.get(0x7EC442 + i) for i in range(30)), blue_bytes)
            # Slot 1 sword/shield palette ($7EC660..7F) untouched
            for extra in range(0x20, 0x40, 2):
                want = 0x2200 + 0x20 + extra
                self.assertEqual(f.get(0x7EC640 + extra) | (f.get(0x7EC641 + extra) << 8), want)

            # Slot 2 (Post-intro Abyss with Kalyxo spawn option): untouched normal sentinel palette
            for c_idx in range(1, 16):
                want = 0x1140 + c_idx
                self.assertEqual(f.get(0x7EC680 + c_idx * 2) | (f.get(0x7EC681 + c_idx * 2) << 8), want)
                self.assertEqual(f.get(0x7EC480 + c_idx * 2) | (f.get(0x7EC481 + c_idx * 2) << 8), want)

            # Verify OAM tile & attribute selection for all 3 slots
            expected_oam = [
                (0, off0, 0x28, 0x00, 0x02, 0x30, 0x70),
                (1, off1, 0x3C, 0x80, 0x82, 0x35, 0x75),
                (2, off2, 0x50, 0x00, 0x02, 0x38, 0x78),
            ]
            for slot, sram_off, oam_off, t_head, t_body, attr_head, attr_body in expected_oam:
                f.word(0x0E, sram_off)
                f.cpu.db = 0x0C
                f.cpu.mf = True
                f.cpu.xf = True
                f.cpu.x = oam_off
                f.cpu.y = slot
                _run_until_stop(f, "FileSelect_SelectSlotLinkSprite")
                self.assertEqual(f.get(0x0802 + oam_off), t_head)
                self.assertEqual(f.get(0x0806 + oam_off), t_body)
                self.assertEqual(f.get(0x0803 + oam_off), attr_head)
                self.assertEqual(f.get(0x0807 + oam_off), attr_body)
                self.assertEqual(f.cpu.x, oam_off)
                self.assertEqual(f.cpu.y, slot)
                self.assertTrue(f.cpu.mf and f.cpu.xf)
        finally:
            f.close()

    def test_file_select_gbc_worn_tunic_override_and_invalid_slot_guard(self) -> None:
        # Invalid slot ($55AA missing) never receives GBC palette even with SavedWorld=$40, GameState=2
        # Valid Abyss-locked slot with Red Mail owned (2) + worn Green ($88) uses GBC_GREEN_WORDS
        # Valid Abyss-locked slot with Red Mail owned (2) + follow Armor ($80) uses GBC_RED_WORDS
        f = SramFixture(self._lib, self._gbc_rom, self._gbc_labels)
        f.stubs = {0x1BEF96: "Palettes_LoadForFileSelect"}
        try:
            f.seed_slot(0, valid=False, saved_world=0x40, game_state=0x02, armor=0x01, sword_flags=0x80)
            f.seed_slot(1, valid=True, saved_world=0x40, game_state=0x02, armor=0x02, sword_flags=0x88)
            f.seed_slot(2, valid=True, saved_world=0x40, game_state=0x02, armor=0x02, sword_flags=0x80)
            f.word(0x7EC602, 0x4321)
            f.word(0x7EC402, 0x4321)
            f.cpu.db = 0x0C
            _run_until_stop(f, "FileSelect_LoadPalettes")

            # Slot 0 invalid -> untouched
            self.assertEqual(f.get(0x7EC602) | (f.get(0x7EC603) << 8), 0x4321)
            self.assertEqual(f.get(0x7EC402) | (f.get(0x7EC403) << 8), 0x4321)
            # Slot 1 -> green GBC palette
            self.assertEqual(bytes(f.get(0x7EC642 + i) for i in range(30)), _words_to_bytes(GBC_GREEN_WORDS)[2:])
            # Slot 2 -> red GBC palette
            self.assertEqual(bytes(f.get(0x7EC682 + i) for i in range(30)), _words_to_bytes(GBC_RED_WORDS)[2:])
        finally:
            f.close()

    def test_dungeon_entrance_restores_normal_link_if_stale_gbc_in_light_world(self) -> None:
        for mask, bank in [(0x06, 0x3B), (0x00, 0x3B), (0x06, 0x10)]:
            with self.subTest(mask=hex(mask), bank=hex(bank)):
                f = Fixture(self._lib, self._gbc_rom, self._gbc_labels)
                f.stubs = {
                    0x018110: "LinkGraphics_ApplyD8Base",
                    0x1BEDF9: "Palette_ArmorAndGloves",
                    0x018130: "ShieldWorld_SyncBoth",
                    0x0AFE80: "Underworld_HandleLayerEffect",
                }
                try:
                    f.put(0x7EF3CA, 0x00)  # Light World / Kalyxo
                    f.put(0x02B2, mask)
                    f.put(0x00BC, bank)
                    f.cpu.c = 0
                    _run_until_stop(f, "LinkState_GameboyInDungeonEntrance")
                    self.assertEqual(f.get(0x02B2), 0x00)
                    self.assertEqual(f.get(0x00BC), 0x10)
                    self.assertEqual(
                        f.calls,
                        [
                            "LinkGraphics_ApplyD8Base",
                            "Palette_ArmorAndGloves",
                            "ShieldWorld_SyncBoth",
                            "Underworld_HandleLayerEffect",
                        ],
                    )
                finally:
                    f.close()


if __name__ == "__main__":
    unittest.main()
