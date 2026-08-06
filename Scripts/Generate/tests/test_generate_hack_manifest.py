from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

from generate_hack_manifest import (  # noqa: E402
    CUSTOM_COLLISION_DATA_END_PC,
    CUSTOM_COLLISION_DATA_START_PC,
    CUSTOM_COLLISION_POINTER_TABLE_PC,
    DUNGEON_MESSAGE_IDS_PC,
    DUNGEON_ROOM_COUNT,
    OBJECT_DATA_REGIONS_PC,
    OBJECT_TABLE_POINTER_OPERAND_PC,
    POT_DATA_START_PC,
    POT_DATA_END_PC,
    POT_POINTER_TABLE_PC,
    ROOM_HEADER_BANK_PC,
    ROOM_HEADER_POINTER_PC,
    SPRITE_DATA_END_PC,
    SPRITE_TABLE_POINTER_OPERAND_PC,
    ManifestGenerationError,
    _pc_to_snes,
    _snes_to_pc,
    _strict_lorom_to_pc,
    collect_reachable_asm_sources,
    compute_protected_regions,
    derive_dungeon_stream_regions,
    derive_editor_managed_regions,
    generate_manifest,
)
from generate_hooks_json import HookEntry, scan_hooks  # noqa: E402


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
        data = bytearray(0x200000)

        object_table_pc = 0xF8000
        data[OBJECT_TABLE_POINTER_OPERAND_PC : OBJECT_TABLE_POINTER_OPERAND_PC + 3] = (
            _pc_to_snes(object_table_pc).to_bytes(3, "little")
        )
        for room_id in range(DUNGEON_ROOM_COUNT):
            pointer_pc = object_table_pc + room_id * 3
            data[pointer_pc : pointer_pc + 3] = _pc_to_snes(0x50000).to_bytes(
                3, "little"
            )
        data[0x50000 : 0x50008] = b"\x00\x00\xFF\xFF\xFF\xFF\xFF\xFF"

        sprite_table_pc = 0x4D2B2
        data[SPRITE_TABLE_POINTER_OPERAND_PC : SPRITE_TABLE_POINTER_OPERAND_PC + 2] = (
            _pc_to_snes(sprite_table_pc) & 0xFFFF
        ).to_bytes(2, "little")
        for room_id in range(DUNGEON_ROOM_COUNT):
            pointer_pc = sprite_table_pc + room_id * 2
            data[pointer_pc : pointer_pc + 2] = (0xD502).to_bytes(2, "little")
        data[0x4D502 : 0x4D504] = b"\x00\xFF"

        for room_id in range(DUNGEON_ROOM_COUNT):
            pointer_pc = POT_POINTER_TABLE_PC + room_id * 2
            data[pointer_pc : pointer_pc + 2] = (0xDDE7).to_bytes(2, "little")
        data[POT_DATA_START_PC : POT_DATA_START_PC + 2] = b"\xFF\xFF"

        header_table_pc = 0x110000
        header_table_snes = _pc_to_snes(header_table_pc)
        data[ROOM_HEADER_POINTER_PC : ROOM_HEADER_POINTER_PC + 3] = (
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
            data[pointer_pc : pointer_pc + 2] = header_offset.to_bytes(2, "little")

        message_end = DUNGEON_MESSAGE_IDS_PC + DUNGEON_ROOM_COUNT * 2
        self.assert_span_fits(data, DUNGEON_MESSAGE_IDS_PC, message_end)

        data[
            CUSTOM_COLLISION_POINTER_TABLE_PC : CUSTOM_COLLISION_POINTER_TABLE_PC + 3
        ] = _pc_to_snes(CUSTOM_COLLISION_DATA_START_PC).to_bytes(3, "little")
        data[CUSTOM_COLLISION_DATA_START_PC : CUSTOM_COLLISION_DATA_START_PC + 4] = (
            b"\xf0\xf0\xff\xff"
        )

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


class LoRomConversionTest(unittest.TestCase):
    def test_wram_fastrom_mirrors_are_rejected(self) -> None:
        for address in (0xFE8000, 0xFF8000):
            with self.subTest(address=f"0x{address:06X}"):
                with self.assertRaisesRegex(
                    ManifestGenerationError, "WRAM or its FastROM mirror"
                ):
                    _strict_lorom_to_pc(address, "fixture pointer")
                with self.assertRaisesRegex(
                    ManifestGenerationError, "WRAM or its FastROM mirror"
                ):
                    _snes_to_pc(address)

    def test_pc_offsets_stop_before_wram_backed_window(self) -> None:
        self.assertEqual(_pc_to_snes(0x3EFFFF), 0x7DFFFF)
        self.assertEqual(
            _strict_lorom_to_pc(0x7DFFFF, "fixture pointer"),
            0x3EFFFF,
        )
        for address in (0x3F0000, 0x3FFFFF):
            with self.subTest(address=f"0x{address:X}"):
                with self.assertRaisesRegex(
                    ManifestGenerationError, "outside canonical ROM-backed LoROM"
                ):
                    _pc_to_snes(address)


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

    def test_unknown_cross_file_include_condition_unions_both_branches(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Core/defs.asm"\nincsrc "Core/select.asm"\n',
        )
        self.fixture.write_text("Core/defs.asm", "!FLAG = 0\n")
        self.fixture.write_text(
            "Core/select.asm",
            "if !FLAG == 1\n"
            '  incsrc "safe.asm"\n'
            "else\n"
            '  incsrc "unsafe.asm"\n'
            "endif\n",
        )
        self.fixture.write_text("Core/safe.asm", "org $0E9000\ndb $00\n")
        self.fixture.write_text(
            "Core/unsafe.asm", "org $258500\ndb $00\n"
        )
        rom_path = self.fixture.write_dev_rom()

        sources = {
            path.relative_to(self.fixture.root.resolve()).as_posix()
            for path in collect_reachable_asm_sources(self.fixture.root)
        }
        self.assertIn("Core/unsafe.asm", sources)
        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"expanded hook Core/unsafe\.asm:1 at 0x258500 starts before",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unknown_hook_payload_uses_conservative_data_size(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $0E9000\n"
            "if !UNKNOWN_PAYLOAD\n"
            "  JSL MaybeShortHook\n"
            "else\n"
            "  db $00,$00,$00,$00,$00,$00,$00,$00\n"
            "endif\n",
        )

        hooks = scan_hooks(
            self.fixture.root,
            collect_reachable_asm_sources(self.fixture.root),
        )
        regions = compute_protected_regions(hooks)

        self.assertEqual(hooks[0].kind, "data")
        self.assertEqual(regions[0]["size"], 8)

    def test_reachable_global_flag_override_fails_closed(self) -> None:
        self.fixture.write_text("Config/module_flags.asm", "!FLAG = 0\n")
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Config/module_flags.asm"\n'
            'incsrc "Core/override.asm"\n'
            "if !FLAG == 1\n"
            '  incsrc "Core/danger.asm"\n'
            "endif\n",
        )
        self.fixture.write_text("Core/override.asm", "!FLAG = 1\n")
        self.fixture.write_text("Core/danger.asm", "org $258448\ndb $00\n")

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/override\.asm:1: reachable source reassigns preloaded "
            r"global define !FLAG outside the canonical define files",
        ):
            collect_reachable_asm_sources(self.fixture.root)

    def test_reachable_global_target_override_fails_closed(self) -> None:
        self.fixture.write_text(
            "Config/feature_flags.asm", "!TARGET = $0E9000\n"
        )
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Config/feature_flags.asm"\n'
            'incsrc "Core/override.asm"\n'
            'incsrc "Core/patch.asm"\n',
        )
        self.fixture.write_text("Core/override.asm", "!TARGET = $258448\n")
        self.fixture.write_text("Core/patch.asm", "org !TARGET\ndb $00\n")

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/override\.asm:1: reachable source reassigns preloaded "
            r"global define !TARGET outside the canonical define files",
        ):
            generate_manifest(self.fixture.root)

    def test_literal_include_under_disabled_module_root_remains_reachable(
        self,
    ) -> None:
        self.fixture.write_text(
            "Config/module_flags.asm", "!DISABLE_SPRITES = 1\n"
        )
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Sprites/explicit.asm"\n'
        )
        self.fixture.write_text("Sprites/explicit.asm", "org $0E9000\ndb $00\n")

        sources = collect_reachable_asm_sources(self.fixture.root)
        hooks = scan_hooks(self.fixture.root, sources)

        self.assertIn(
            "Sprites/explicit.asm",
            {
                path.relative_to(self.fixture.root.resolve()).as_posix()
                for path in sources
            },
        )
        self.assertEqual([hook.address for hook in hooks], [0x0E9000])

    def test_duplicate_possible_hooks_preserve_maximum_protected_size(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            'if defined("USE_JSL")\n'
            "  org $0D9000\n"
            "  JSL Foo\n"
            "else\n"
            "  org $0D9000\n"
            "  db $00,$01,$02,$03,$04,$05,$06,$07\n"
            "endif\n",
        )

        hooks = scan_hooks(
            self.fixture.root,
            collect_reachable_asm_sources(self.fixture.root),
        )
        regions = compute_protected_regions(hooks)

        self.assertEqual(hooks[0].kind, "jsl")
        self.assertEqual(hooks[0].protected_size, 8)
        self.assertEqual(regions[0]["size"], 8)

    def test_hook_payload_scanner_applies_local_define_mutations(self) -> None:
        self.fixture.write_text("Config/feature_flags.asm", "!MODE = 1\n")
        active_path = self.fixture.write_text(
            "Core/active.asm",
            "org $0D9000\n"
            "!MODE = 0\n"
            "if !MODE\n"
            "  JSL Foo\n"
            "else\n"
            "  db $00,$01,$02,$03,$04,$05,$06,$07\n"
            "endif\n",
        )

        hooks = scan_hooks(self.fixture.root, [active_path])
        regions = compute_protected_regions(hooks)

        self.assertEqual(hooks[0].kind, "data")
        self.assertEqual(regions[0]["size"], 8)

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

    def test_expanded_hook_cannot_overlap_editor_managed_range(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $258500\n"
            "JSL ExpandedCollisionHook\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"expanded hook Core/active\.asm:1 at 0x258500 starts before "
            r"editor-managed range 0x258450-0x25E000 ends in the same "
            r"physical LoROM bank",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_expanded_hook_just_before_editor_range_fails_closed(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $258448\n"
            "JSL BoundaryStraddlingHook\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"expanded hook Core/active\.asm:1 at 0x258448 starts before "
            r"editor-managed range 0x258450-0x25E000 ends in the same "
            r"physical LoROM bank",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_expanded_hook_at_editor_range_end_is_allowed(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $25E000\n"
            "JSL WaterFillHook\n",
        )
        rom_path = self.fixture.write_dev_rom()

        manifest = generate_manifest(
            self.fixture.root, dev_rom_path=rom_path
        )

        self.assertEqual(manifest["summary"]["total_hooks"], 1)

    def test_computed_local_define_orgs_cannot_bypass_editor_guard(self) -> None:
        expressions = {
            "direct_define": "!addr = $258448\norg !addr\n",
            "define_arithmetic": "!base = $258440\norg !base+$08\n",
        }
        for name, source in expressions.items():
            with self.subTest(name=name):
                self.fixture.write_text(
                    "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
                )
                self.fixture.write_text(
                    "Core/active.asm", source + "JSL ComputedHook\n"
                )
                rom_path = self.fixture.write_dev_rom()

                hooks = scan_hooks(
                    self.fixture.root,
                    collect_reachable_asm_sources(self.fixture.root),
                )
                self.assertEqual([hook.address for hook in hooks], [0x258448])
                with self.assertRaisesRegex(
                    ManifestGenerationError,
                    r"expanded hook Core/active\.asm:2 at 0x258448 starts "
                    r"before editor-managed range 0x258450-0x25E000",
                ):
                    generate_manifest(
                        self.fixture.root, dev_rom_path=rom_path
                    )

    def test_full_define_rhs_is_evaluated_before_org_guard(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "!addr = $248450+$010000\n"
            "org !addr\n"
            "JSL ComputedHook\n",
        )
        rom_path = self.fixture.write_dev_rom()

        hooks = scan_hooks(
            self.fixture.root,
            collect_reachable_asm_sources(self.fixture.root),
        )
        self.assertEqual([hook.address for hook in hooks], [0x258450])
        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"expanded hook Core/active\.asm:2 at 0x258450 starts before",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unresolved_active_org_requires_source_bank_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org UnknownDestination\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/active\.asm:1: unresolved active org expression "
            r"'UnknownDestination' has no @manifest-org-bank proof",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unresolved_org_proof_must_avoid_editor_banks(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org UnknownDestination ; @manifest-org-bank=$25\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"unresolved active org expression 'UnknownDestination' may "
            r"affect editor-managed physical LoROM bank 0x25",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unresolved_org_proof_must_match_literal_bank_anchor(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org $258448+!unknown ; @manifest-org-bank=$0D\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"address-literal bank anchor\(s\) 0x25, contradicting "
            r"@manifest-org-bank proof 0x0D",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unresolved_org_proof_must_match_known_define_bank_anchor(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "!base = $258448\n"
            "org !base+!unknown ; @manifest-org-bank=$0D\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"address-literal bank anchor\(s\) 0x25, contradicting "
            r"@manifest-org-bank proof 0x0D",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unrecognized_unresolved_org_is_rejected_despite_disjoint_proof(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org DynamicVanillaAddress ; @manifest-org-bank=$0E\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"unresolved active org expression 'DynamicVanillaAddress' is "
            r"not an audited source/expression/bank contract",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_invoked_unresolved_macro_org_requires_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "macro WriteAt(addr)\n"
            "  org <addr>\n"
            "  db $00\n"
            "endmacro\n"
            "%WriteAt($258448)\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/active\.asm:2: unresolved active org expression '<addr>' "
            r"has no @manifest-org-bank proof",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_invoked_macro_placeholder_rejects_single_bank_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "!unknown = $08\n"
            "macro WriteAt(offset)\n"
            "  org <offset>+!unknown ; @manifest-org-bank=$0D\n"
            "  db $00\n"
            "endmacro\n"
            "%WriteAt($258448)\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/active\.asm:3: unresolved active org expression "
            r"'<offset>\+!unknown' contains a macro placeholder; a single "
            r"@manifest-org-bank proof cannot cover every invocation",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_variadic_macro_placeholder_rejects_single_bank_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "macro WriteAt(...)\n"
            "  org <...[0]> ; @manifest-org-bank=$0D\n"
            "  db $00\n"
            "endmacro\n"
            "%WriteAt($258448)\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"unresolved active org expression '<\.\.\.\[0\]>' contains "
            r"a macro placeholder",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unsupported_asar_read_cannot_claim_literal_bank_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "org read3($0D8000) ; @manifest-org-bank=$0D\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"unresolved active org expression 'read3\(\$0D8000\)' is not "
            r"an audited source/expression/bank contract",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_cross_file_define_cannot_claim_unverified_bank_proof(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm",
            'incsrc "Core/defs.asm"\nincsrc "Core/active.asm"\n',
        )
        self.fixture.write_text("Core/defs.asm", "!base = $258448\n")
        self.fixture.write_text(
            "Core/active.asm",
            "org !base+$08 ; @manifest-org-bank=$0D\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/active\.asm:1: unresolved active org expression "
            r"'!base\+\$08' is not an audited source/expression/bank contract",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unknown_macro_condition_scans_every_possible_org_branch(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "macro WriteAt(addr)\n"
            "  if <addr> == $258448\n"
            "    org $0E9000\n"
            "    db $00\n"
            "  else\n"
            "    org $258448\n"
            "    db $00\n"
            "  endif\n"
            "endmacro\n"
            "%WriteAt($000000)\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"expanded hook Core/active\.asm:6 at 0x258448 starts before",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_unknown_macro_branches_merge_only_identical_define_states(
        self,
    ) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "macro WriteAt(addr)\n"
            "  if <addr>\n"
            "    !target = $258448\n"
            "  else\n"
            "    !target = $0E9000\n"
            "  endif\n"
            "  org !target\n"
            "  db $00\n"
            "endmacro\n"
            "%WriteAt($000001)\n",
        )
        rom_path = self.fixture.write_dev_rom()

        with self.assertRaisesRegex(
            ManifestGenerationError,
            r"Core/active\.asm:7: unresolved active org expression "
            r"'!target' has no @manifest-org-bank proof",
        ):
            generate_manifest(self.fixture.root, dev_rom_path=rom_path)

    def test_uninvoked_literal_macro_does_not_create_hook(self) -> None:
        self.fixture.write_text(
            "Oracle_main.asm", 'incsrc "Core/active.asm"\n'
        )
        self.fixture.write_text(
            "Core/active.asm",
            "macro NeverCalled()\n"
            "  org $258448\n"
            "  db $00\n"
            "endmacro\n"
            "org $0E9000\n"
            "db $00\n",
        )
        rom_path = self.fixture.write_dev_rom()

        manifest = generate_manifest(
            self.fixture.root, dev_rom_path=rom_path
        )

        self.assertEqual(manifest["summary"]["total_hooks"], 1)

    def test_literal_overworld_incsrc_remains_reachable_despite_flag(
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

        self.assertEqual(manifest["summary"]["total_hooks"], 4)
        self.assertEqual(owned_banks, {"0x2E", "0x40"})
        self.assertEqual(len(manifest["room_tags"]["tags"]), 1)


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


class RepositoryProjectSafetyTest(unittest.TestCase):
    def test_water_fill_save_scope_is_disabled_exactly_once(self) -> None:
        project_lines = (REPO_ROOT / "Oracle-of-Secrets.yaze").read_text(
            encoding="utf-8"
        ).splitlines()

        self.assertEqual(
            [
                line
                for line in project_lines
                if line.startswith("save_dungeon_water_fill_zones=")
            ],
            ["save_dungeon_water_fill_zones=false"],
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
        self.assertIn('if [[ "$base_rom" != /* ]]', build)
        self.assertIn(
            'base_rom="$(cd "$(dirname "$base_rom")" && pwd -P)/'
            '$(basename "$base_rom")"',
            build,
        )
        self.assertEqual(build.count('--dev-rom "$base_rom"'), 1)
        self.assertIn('--rom "$patched_rom"', build)
        self.assertLess(
            build.index('echo "Built patched ROM: $patched_rom"'),
            build.index(generator_call),
        )


class RepositoryMinecartTrackSourceTest(unittest.TestCase):
    def test_manifest_exposes_durable_minecart_track_source(self) -> None:
        manifest = generate_manifest(REPO_ROOT)

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(
            manifest["minecart_tracks"]["source"],
            {
                "format": "yaze-minecart-track-table",
                "version": 1,
                "path": "Sprites/Objects/data/minecart_tracks.asm",
            },
        )


class DevRomProvenanceTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ManifestFixture()
        self.fixture.write_text("Oracle_main.asm", "")
        self.canonical = self.fixture.write_dev_rom()

    def tearDown(self) -> None:
        self.fixture.close()

    def write_distinct_rom(self, path: Path) -> Path:
        data = bytearray(self.canonical.read_bytes())
        data[-1] ^= 0xA5
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        return path

    def test_selected_legacy_rom_drives_pipeline_hash_and_ranges(self) -> None:
        legacy = self.write_distinct_rom(
            self.fixture.root / "Roms" / "oos168_test2.sfc"
        )
        self.fixture.write_rom_value(
            legacy, ROOM_HEADER_BANK_PC, 0x23, 1
        )

        manifest = generate_manifest(
            self.fixture.root,
            dev_rom_path=Path("Roms/oos168_test2.sfc"),
        )

        self.assertEqual(
            manifest["build_pipeline"]["dev_rom"],
            "Roms/oos168_test2.sfc",
        )
        self.assertEqual(
            manifest["rom"]["dev_rom_sha1"],
            hashlib.sha1(legacy.read_bytes()).hexdigest(),
        )
        self.assertNotEqual(
            manifest["rom"]["dev_rom_sha1"],
            hashlib.sha1(self.canonical.read_bytes()).hexdigest(),
        )
        self.assertEqual(
            manifest["rom"]["dev_rom_size"], legacy.stat().st_size
        )
        self.assertEqual(
            manifest["editor_managed_regions"]["regions"],
            [
                {"start": "0x07F61D", "end": "0x07F86D"},
                {"start": "0x238280", "end": "0x2392B0"},
                {"start": "0x258090", "end": "0x258408"},
                {"start": "0x258450", "end": "0x25E000"},
            ],
        )

    def test_external_dev_rom_uses_absolute_manifest_path(self) -> None:
        with tempfile.TemporaryDirectory() as external_dir:
            external = self.write_distinct_rom(
                Path(external_dir) / "override.sfc"
            ).resolve()

            manifest = generate_manifest(
                self.fixture.root,
                dev_rom_path=external,
            )

            self.assertEqual(
                manifest["build_pipeline"]["dev_rom"], str(external)
            )
            self.assertEqual(
                manifest["rom"]["dev_rom_sha1"],
                hashlib.sha1(external.read_bytes()).hexdigest(),
            )

    def test_explicit_missing_dev_rom_fails_closed(self) -> None:
        missing = Path("Roms/missing.sfc")

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Editable dev ROM not found:.*Roms/missing.sfc",
        ):
            generate_manifest(
                self.fixture.root,
                dev_rom_path=missing,
            )

    def test_explicit_missing_patched_rom_fails_closed(self) -> None:
        missing = Path("Roms/missing-patched.sfc")

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Patched ROM not found:.*Roms/missing-patched.sfc",
        ):
            generate_manifest(
                self.fixture.root,
                rom_path=missing,
            )

    def test_cli_records_selected_dev_and_patched_rom_paths(self) -> None:
        legacy = self.write_distinct_rom(
            self.fixture.root / "Roms" / "oos168_test2.sfc"
        )
        patched = self.fixture.root / "Roms" / "oos169x.sfc"
        patched.write_bytes(b"patched-rom")
        output = self.fixture.root / "Roms" / "hack_manifest.json"

        result = subprocess.run(
            [
                sys.executable,
                str(GENERATE_DIR / "generate_hack_manifest.py"),
                "--root",
                str(self.fixture.root),
                "--output",
                str(output),
                "--dev-rom",
                str(legacy),
                "--rom",
                str(patched),
            ],
            check=False,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(
            manifest["build_pipeline"]["dev_rom"],
            "Roms/oos168_test2.sfc",
        )
        self.assertEqual(
            manifest["build_pipeline"]["patched_rom"],
            "Roms/oos169x.sfc",
        )
        self.assertEqual(manifest["rom"]["path"], "Roms/oos169x.sfc")


class DungeonStreamRegionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ManifestFixture()
        self.fixture.write_text("Oracle_main.asm", "")

    def tearDown(self) -> None:
        self.fixture.close()

    def test_manifest_emits_exact_live_dungeon_layout(self) -> None:
        rom_path = self.fixture.write_dev_rom()

        manifest = generate_manifest(
            self.fixture.root,
            dev_rom_path=rom_path,
        )

        self.assertEqual(
            manifest["dungeon_stream_regions"],
            {
                "objects": {
                    "pointer_table": "0x1F8000",
                    "pointer_count": DUNGEON_ROOM_COUNT,
                    "pointer_encoding": "long24",
                    "strategy": "copy_on_write",
                    "data_regions": [
                        {"start": "0x0A8000", "end": "0x0AB730"},
                        {"start": "0x1F878A", "end": "0x208000"},
                        {"start": "0x03EB90", "end": "0x048000"},
                        {"start": "0x278000", "end": "0x288000"},
                        {"start": "0x298000", "end": "0x2A8000"},
                    ],
                    "allocation_regions": [{"start": "0x298000", "end": "0x2A8000"}],
                },
                "sprites": {
                    "pointer_table": "0x09D2B2",
                    "pointer_count": DUNGEON_ROOM_COUNT,
                    "pointer_encoding": "bank16",
                    "pointer_bank": "0x09",
                    "strategy": "copy_on_write",
                    "data_regions": [{"start": "0x09D502", "end": "0x09EC9F"}],
                    "allocation_regions": [{"start": "0x09D502", "end": "0x09EC9F"}],
                },
                "pot_items": {
                    "pointer_table": "0x01DB69",
                    "pointer_count": DUNGEON_ROOM_COUNT,
                    "pointer_encoding": "bank16",
                    "pointer_bank": "0x01",
                    "strategy": "repack_all",
                    "data_regions": [{"start": "0x01DDE7", "end": "0x01E6B2"}],
                    "allocation_regions": [{"start": "0x01DDE7", "end": "0x01E6B2"}],
                },
            },
        )

    def test_invalid_live_stream_pointers_fail_closed(self) -> None:
        mutations = {
            "object": (
                0xF8000,
                _pc_to_snes(0x60000),
                3,
                "object pointer for room 0x000",
            ),
            "sprite": (
                0x4D2B2,
                0xD501,
                2,
                "minimum sprite pointer",
            ),
            "pot": (
                POT_POINTER_TABLE_PC,
                0x7000,
                2,
                "pot-item pointer for room 0x000 is unmapped",
            ),
            "pot_below_fixed_floor": (
                POT_POINTER_TABLE_PC,
                0xDDBD,
                2,
                "pot-item pointer for room 0x000.*outside pot-item data region",
            ),
        }
        for name, (target_pc, replacement, size, expected) in mutations.items():
            with self.subTest(name=name):
                rom_path = self.fixture.write_dev_rom()
                self.fixture.write_rom_value(
                    rom_path,
                    target_pc,
                    replacement,
                    size,
                )
                with self.assertRaisesRegex(ManifestGenerationError, expected):
                    derive_dungeon_stream_regions(rom_path)

    def test_streams_must_terminate_before_region_or_bank_end(self) -> None:
        mutations = {
            "object": (
                0xF8000,
                _pc_to_snes(OBJECT_DATA_REGIONS_PC[0][1] - 1),
                3,
                "objects stream for room 0x000 is missing its two-byte header",
            ),
            "sprite": (
                0x4D2B2,
                _pc_to_snes(SPRITE_DATA_END_PC - 1) & 0xFFFF,
                2,
                "sprites stream for room 0x000 has no 0xFF terminator",
            ),
            "pot": (
                POT_POINTER_TABLE_PC,
                _pc_to_snes(POT_DATA_END_PC - 1) & 0xFFFF,
                2,
                "pot_items stream for room 0x000 has no 0xFFFF terminator",
            ),
        }
        for name, (target_pc, replacement, size, expected) in mutations.items():
            with self.subTest(name=name):
                rom_path = self.fixture.write_dev_rom()
                self.fixture.write_rom_value(
                    rom_path,
                    target_pc,
                    replacement,
                    size,
                )
                with self.assertRaisesRegex(ManifestGenerationError, expected):
                    derive_dungeon_stream_regions(rom_path)


class EditorManagedRegionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = ManifestFixture()
        self.fixture.write_text("Oracle_main.asm", "")

    def tearDown(self) -> None:
        self.fixture.close()

    def test_derives_exact_editor_managed_ranges(self) -> None:
        rom_path = self.fixture.write_dev_rom()

        regions = derive_editor_managed_regions(rom_path)

        self.assertEqual(
            regions,
            [
                {"start": "0x07F61D", "end": "0x07F86D"},
                {"start": "0x228280", "end": "0x2292B0"},
                {"start": "0x258090", "end": "0x258408"},
                {"start": "0x258450", "end": "0x25E000"},
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
                {"start": "0x07F61D", "end": "0x07F86D"},
                {"start": "0x228280", "end": "0x2292B0"},
                {"start": "0x258090", "end": "0x258408"},
                {"start": "0x258450", "end": "0x25E000"},
            ],
        )

    def test_duplicate_room_header_pointer_fails_closed(self) -> None:
        rom_path = self.fixture.write_dev_rom(duplicate_room=1)

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "Room-header pointers are not unique",
        ):
            derive_editor_managed_regions(rom_path)

    def test_custom_collision_pointer_into_water_fill_tail_fails_closed(
        self,
    ) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(
            rom_path,
            CUSTOM_COLLISION_POINTER_TABLE_PC,
            _pc_to_snes(CUSTOM_COLLISION_DATA_END_PC),
            3,
        )

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "custom-collision pointer for room 0x000.*outside the "
            "editor-owned region",
        ):
            derive_editor_managed_regions(rom_path)

    def test_custom_collision_stream_cannot_cross_water_fill_tail(self) -> None:
        rom_path = self.fixture.write_dev_rom()
        self.fixture.write_rom_value(
            rom_path,
            CUSTOM_COLLISION_POINTER_TABLE_PC,
            _pc_to_snes(CUSTOM_COLLISION_DATA_END_PC - 1),
            3,
        )
        data = bytearray(rom_path.read_bytes())
        data[CUSTOM_COLLISION_DATA_END_PC - 1] = 0xFF
        rom_path.write_bytes(data)

        with self.assertRaisesRegex(
            ManifestGenerationError,
            "crosses reserved WaterFill data",
        ):
            derive_editor_managed_regions(rom_path)

    def test_custom_collision_geometry_must_fit_64x64_map(self) -> None:
        malformed_streams = {
            "zero_dimension": (
                b"\x00\x00\x00\x01\xFF\xFF",
                "zero dimension 0x1",
            ),
            "single_offset_0x1000": (
                b"\xF0\xF0\x00\x10\x07\xFF\xFF",
                "single-tile offset 0x1000.*outside the 64x64 map",
            ),
            "rectangle_crosses_right_edge": (
                b"\xFF\x0F\x02\x01\x01\x02\xFF\xFF",
                "offset 0x0FFF with size 2x1 exceeds the 64x64 map",
            ),
        }
        for name, (stream, expected) in malformed_streams.items():
            with self.subTest(name=name):
                rom_path = self.fixture.write_dev_rom()
                data = bytearray(rom_path.read_bytes())
                end = CUSTOM_COLLISION_DATA_START_PC + len(stream)
                data[CUSTOM_COLLISION_DATA_START_PC:end] = stream
                rom_path.write_bytes(data)

                with self.assertRaisesRegex(
                    ManifestGenerationError, expected
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
