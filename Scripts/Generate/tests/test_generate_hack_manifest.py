from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

from generate_hack_manifest import (  # noqa: E402
    DUNGEON_MESSAGE_IDS_PC,
    DUNGEON_ROOM_COUNT,
    ROOM_HEADER_BANK_PC,
    ROOM_HEADER_POINTER_PC,
    ManifestGenerationError,
    _pc_to_snes,
    collect_reachable_asm_sources,
    compute_protected_regions,
    derive_editor_managed_regions,
    generate_manifest,
)
from generate_hooks_json import HookEntry  # noqa: E402


class ManifestFixture:
    def __init__(self) -> None:
        self._temp = tempfile.TemporaryDirectory()
        self.root = Path(self._temp.name)

    def close(self) -> None:
        self._temp.cleanup()

    def write_text(self, relative: str, text: str) -> Path:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def write_dev_rom(self, duplicate_room: int | None = None) -> Path:
        data = bytearray(0x120000)
        header_table_pc = 0x110000
        header_table_snes = _pc_to_snes(header_table_pc)
        data[ROOM_HEADER_POINTER_PC:ROOM_HEADER_POINTER_PC + 3] = (
            header_table_snes.to_bytes(3, "little")
        )
        data[ROOM_HEADER_BANK_PC] = 0x22

        first_header_offset = 0x8280
        for room_id in range(DUNGEON_ROOM_COUNT):
            source_room = (
                duplicate_room - 1
                if duplicate_room is not None and room_id == duplicate_room
                else room_id
            )
            header_offset = first_header_offset + source_room * 14
            pointer_pc = header_table_pc + room_id * 2
            data[pointer_pc:pointer_pc + 2] = header_offset.to_bytes(
                2, "little"
            )

        message_end = DUNGEON_MESSAGE_IDS_PC + DUNGEON_ROOM_COUNT * 2
        self.assert_span_fits(data, DUNGEON_MESSAGE_IDS_PC, message_end)

        rom_path = self.root / "Roms" / "oos168.sfc"
        rom_path.parent.mkdir(parents=True, exist_ok=True)
        rom_path.write_bytes(data)
        return rom_path

    @staticmethod
    def write_rom_value(
        rom_path: Path,
        offset: int,
        value: int,
        size: int,
    ) -> None:
        data = bytearray(rom_path.read_bytes())
        data[offset:offset + size] = value.to_bytes(size, "little")
        rom_path.write_bytes(data)

    @staticmethod
    def assert_span_fits(data: bytes, start: int, end: int) -> None:
        if not 0 <= start < end <= len(data):
            raise AssertionError(
                f"Fixture span [0x{start:X}, 0x{end:X}) does not fit"
            )


class ReachableSourceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ManifestFixture()

    def tearDown(self) -> None:
        self.fixture.close()

    def test_collects_nested_and_root_relative_includes(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Core/active.asm"\n'
            '; incsrc "Core/commented.asm"\n',
        )
        self.fixture.write_text(
            "Core/active.asm",
            "incsrc nested.asm ; relative to this file\n",
        )
        self.fixture.write_text(
            "Core/nested.asm",
            'incsrc "Shared/root.asm"\n',
        )
        self.fixture.write_text("Shared/root.asm", "org $2F8000\n")
        self.fixture.write_text("Core/commented.asm", "org $228080\n")

        sources = {
            path.relative_to(self.fixture.root.resolve()).as_posix()
            for path in collect_reachable_asm_sources(self.fixture.root)
        }

        self.assertEqual(
            sources,
            {
                "Oracle_main.asm",
                "Core/active.asm",
                "Core/nested.asm",
                "Shared/root.asm",
            },
        )

    def test_unresolved_reachable_include_fails_closed(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/missing.asm"\n'
        )

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Oracle_main\.asm:1: unresolved incsrc 'Core/missing\.asm'",
        ):
            collect_reachable_asm_sources(self.fixture.root)

    def test_case_mismatched_include_fails_closed(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/Active.asm"\n'
        )
        self.fixture.write_text("Core/active.asm", "org $2E8000\n")

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Oracle_main\.asm:1: unresolved incsrc 'Core/Active\.asm'",
        ):
            collect_reachable_asm_sources(self.fixture.root)

    def test_disabled_sprite_edge_blocks_cross_root_descendants(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Config/module_flags.asm"\n'
            "if !DISABLE_SPRITES == 0\n"
            '  incsrc "Sprites/disabled.asm"\n'
            "endif\n"
            'incsrc "Core/shared.asm"\n',
        )
        self.fixture.write_text(
            "Config/module_flags.asm",
            "!DISABLE_SPRITES = 1\n",
        )
        self.fixture.write_text(
            "Sprites/disabled.asm",
            'incsrc "../Core/sprite_only.asm"\n'
            'incsrc "../Core/shared.asm"\n',
        )
        self.fixture.write_text(
            "Core/sprite_only.asm",
            "org $2F8000\n"
            "db $00\n",
        )
        self.fixture.write_text(
            "Core/shared.asm",
            "org $2E8000\n"
            "db $00\n",
        )

        sources = {
            path.relative_to(self.fixture.root.resolve()).as_posix()
            for path in collect_reachable_asm_sources(self.fixture.root)
        }
        manifest = generate_manifest(self.fixture.root)

        self.assertEqual(
            sources,
            {
                "Oracle_main.asm",
                "Config/module_flags.asm",
                "Core/shared.asm",
            },
        )
        self.assertEqual(
            {
                entry["bank"]
                for entry in manifest["owned_banks"]["banks"]
            },
            {"0x2E"},
        )

    def test_missing_include_in_inactive_module_condition_is_ignored(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Config/module_flags.asm"\n'
            "if !DISABLE_SPRITES == 0\n"
            '  incsrc "Sprites/missing.asm"\n'
            "endif\n"
            'incsrc "Core/active.asm"\n',
        )
        self.fixture.write_text(
            "Config/module_flags.asm",
            "!DISABLE_SPRITES = 1\n",
        )
        self.fixture.write_text("Core/active.asm", "org $2E8000\n")

        sources = {
            path.relative_to(self.fixture.root.resolve()).as_posix()
            for path in collect_reachable_asm_sources(self.fixture.root)
        }

        self.assertEqual(
            sources,
            {
                "Oracle_main.asm",
                "Config/module_flags.asm",
                "Core/active.asm",
            },
        )

    def test_manifest_excludes_unreachable_bank_claims_and_hooks(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $2F8000\n"
            "db $00\n",
        )
        self.fixture.write_text(
            "Dungeons/Assets/Wagon Cart/WagonCart.asm",
            "org $228080\n"
            "db $00\n",
        )

        manifest = generate_manifest(self.fixture.root)
        owned_banks = {
            entry["bank"] for entry in manifest["owned_banks"]["banks"]
        }

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(manifest["summary"]["total_hooks"], 1)
        self.assertIn("0x2F", owned_banks)
        self.assertNotIn("0x22", owned_banks)

    def test_reachable_tools_source_is_scanned_by_every_manifest_scanner(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Tools/reachable.asm"\n'
        )
        self.fixture.write_text(
            "Tools/reachable.asm",
            "org $008100\n"
            "JSL ReachableToolsHook\n"
            "org $01CC18 : JML ReachableToolsTag ; @hook name=ToolsTag\n"
            "org $2F8000\n"
            "db $00\n",
        )

        manifest = generate_manifest(self.fixture.root)
        owned_banks = {
            entry["bank"] for entry in manifest["owned_banks"]["banks"]
        }

        self.assertEqual(manifest["summary"]["total_hooks"], 3)
        self.assertIn("0x2F", owned_banks)
        self.assertTrue(
            any(
                tag["name"] == "ToolsTag"
                for tag in manifest["room_tags"]["tags"]
            )
        )

    def test_fastrom_orgs_map_to_physical_spans_not_mirror_banks(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $808B6B : LDX.w #$6040\n"
            "org $20AF20\n"
            "db $00\n"
            "org $A0F000\n"
            "db $00\n",
        )

        manifest = generate_manifest(self.fixture.root)
        protected = manifest["protected_regions"]["regions"]
        banks = {
            entry["bank"]: entry for entry in manifest["owned_banks"]["banks"]
        }

        self.assertEqual(protected[0]["start"], "0x008B6B")
        self.assertNotIn("0x80", banks)
        self.assertNotIn("0xA0", banks)
        self.assertEqual(banks["0x20"]["ownership"], "shared")
        self.assertEqual(
            {
                region["start"] for region in banks["0x20"]["regions"]
            },
            {"0x20AF20", "0x20F000"},
        )

    def test_disabled_overworld_incsrc_cannot_leak_manifest_state(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Config/module_flags.asm"\n'
            'incsrc "Core/active.asm"\n'
            'incsrc "Overworld/disabled.asm"\n',
        )
        self.fixture.write_text(
            "Config/module_flags.asm",
            "!DISABLE_OVERWORLD = 1\n",
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $2E8000\n"
            "db $00\n",
        )
        self.fixture.write_text(
            "Overworld/disabled.asm",
            "org $008200\n"
            "JSL DisabledOverworldHook\n"
            "org $01CC18 : JML DisabledTag ; @hook name=DisabledTag\n"
            "org $408000\n"
            "db $00\n",
        )

        manifest = generate_manifest(self.fixture.root)
        owned_banks = {
            entry["bank"] for entry in manifest["owned_banks"]["banks"]
        }

        self.assertEqual(manifest["summary"]["total_hooks"], 1)
        self.assertEqual(owned_banks, {"0x2E"})
        self.assertEqual(manifest["room_tags"]["tags"], [])


class RepositorySourceRegressionTest(unittest.TestCase):
    def test_real_fastrom_orgs_use_physical_manifest_ranges(self) -> None:
        manifest = generate_manifest(REPO_ROOT)
        protected_starts = {
            region["start"]
            for region in manifest["protected_regions"]["regions"]
        }
        banks = {
            entry["bank"]: entry for entry in manifest["owned_banks"]["banks"]
        }

        self.assertIn("0x008B6B", protected_starts)
        self.assertIn("0x06F725", protected_starts)
        self.assertIn("0x0DDFB2", protected_starts)
        self.assertFalse(
            {"0x80", "0x86", "0x8D", "0xA0"} & banks.keys()
        )
        self.assertTrue(
            any(
                region["start"] == "0x20F000"
                and region["source"] == "Overworld/lost_woods.asm:27"
                for region in banks["0x20"]["regions"]
            )
        )


class RepositoryMessageSourceTest(unittest.TestCase):
    def test_manifest_exposes_durable_expanded_message_source(self) -> None:
        messages = generate_manifest(REPO_ROOT)["messages"]

        self.assertEqual(messages["data_start"], "0x2F8026")
        self.assertEqual(messages["data_end"], "0x2FFDFF")
        self.assertEqual(
            messages["expanded_range"],
            {"first": "0x18D", "last": "0x1F9", "count": 109},
        )
        self.assertEqual(
            messages["source"],
            {
                "format": "yaze-message-bundle",
                "version": 1,
                "canonical_bundle_path": (
                    "Data/dialogue/expanded_messages.json"
                ),
                "generated_asm_include_path": (
                    "Core/Generated/expanded_messages.asm"
                ),
            },
        )
        policy_text = str(messages)
        self.assertIn("ASM-owned bank $2F", policy_text)
        self.assertIn("Scripts/Build/build_rom.sh 168", policy_text)
        self.assertNotIn("message-write", policy_text)

    def test_build_refreshes_the_configured_manifest_after_assembly(self) -> None:
        project = (REPO_ROOT / "Oracle-of-Secrets.yaze").read_text(
            encoding="utf-8"
        )
        build = (REPO_ROOT / "Scripts/Build/build_rom.sh").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "hack_manifest_file=Roms/hack_manifest.json",
            project.splitlines(),
        )
        generator_call = (
            'python3 "$repo_root/Scripts/Generate/'
            'generate_hack_manifest.py"'
        )
        self.assertEqual(build.count(generator_call), 1)
        self.assertIn(
            '--output "$repo_root/Roms/hack_manifest.json"',
            build,
        )
        self.assertIn('--rom "$patched_rom"', build)
        self.assertLess(
            build.index('echo "Built patched ROM: $patched_rom"'),
            build.index(generator_call),
        )


class EditorManagedRegionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ManifestFixture()
        self.fixture.write_text("Oracle_main.asm", "")

    def tearDown(self) -> None:
        self.fixture.close()

    def test_derives_exact_room_header_and_message_ranges(self) -> None:
        rom_path = self.fixture.write_dev_rom()

        regions = derive_editor_managed_regions(rom_path)

        self.assertEqual(
            regions,
            [
                {"start": "0x228280", "end": "0x2292B0"},
                {"start": "0x07F61D", "end": "0x07F86D"},
            ],
        )

    def test_manifest_v3_includes_derived_editor_ranges(self) -> None:
        self.fixture.write_dev_rom()

        manifest = generate_manifest(self.fixture.root)

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(
            manifest["build_pipeline"]["entry_point"], "Oracle_main.asm"
        )
        self.assertEqual(
            manifest["editor_managed_regions"]["regions"],
            [
                {"start": "0x228280", "end": "0x2292B0"},
                {"start": "0x07F61D", "end": "0x07F86D"},
            ],
        )

    def test_duplicate_room_header_pointer_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom(duplicate_room=1)

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointers are not unique",
        ):
            derive_editor_managed_regions(rom_path)

    def test_low_half_header_table_pointer_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(
            rom_path, ROOM_HEADER_POINTER_PC, 0x220000, 3
        )

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointer-table operand "
            "0x220000 is not a high-half LoROM pointer",
        ):
            derive_editor_managed_regions(rom_path)

    def test_wram_header_table_pointer_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(
            rom_path, ROOM_HEADER_POINTER_PC, 0x7E8000, 3
        )

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointer-table operand 0x7E8000 points to WRAM",
        ):
            derive_editor_managed_regions(rom_path)

    def test_low_half_room_header_pointer_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(rom_path, 0x110000, 0x0280, 2)

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointer for room 0x000 "
            "0x220280 is not a high-half LoROM pointer",
        ):
            derive_editor_managed_regions(rom_path)

    def test_wram_room_header_bank_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(
            rom_path, ROOM_HEADER_BANK_PC, 0x7E, 1
        )

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointer for room 0x000 "
            "0x7E8280 points to WRAM",
        ):
            derive_editor_managed_regions(rom_path)

    def test_manifest_v3_canonicalizes_legacy_low_half_hook(self) -> None:
        hook = HookEntry(
            address=0x1E7F21,
            name="ArrghusHook",
            kind="patch",
            target=None,
            source="Sprites/Bosses/arrghus.asm:3",
            module="Sprites",
        )

        regions = compute_protected_regions([hook])

        self.assertEqual(regions[0]["start"], "0x1EFF21")
        self.assertEqual(regions[0]["end"], "0x1EFF25")


if __name__ == "__main__":
    unittest.main()
