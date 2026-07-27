from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

GENERATE_DIR = Path(__file__).resolve().parents[1]
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
