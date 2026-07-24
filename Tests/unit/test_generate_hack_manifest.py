from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "Scripts" / "Generate"))

from generate_hack_manifest import (
    ManifestGenerationError,
    generate_manifest,
)


ROM_SIZE = 0x200000
ROOM_COUNT = 296


def pc_to_snes(pc_address: int) -> int:
    return (
        ((pc_address << 1) & 0x7F0000)
        | (pc_address & 0x7FFF)
        | 0x8000
    )


def write_u16(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 2] = value.to_bytes(2, "little")


def write_u24(data: bytearray, offset: int, value: int) -> None:
    data[offset : offset + 3] = value.to_bytes(3, "little")


def make_layout_rom(path: Path) -> bytearray:
    data = bytearray(ROM_SIZE)

    object_table_pc = 0xF8000
    write_u24(data, 0x874C, pc_to_snes(object_table_pc))
    for room_id in range(ROOM_COUNT):
        write_u24(
            data,
            object_table_pc + room_id * 3,
            pc_to_snes(0x50000),
        )

    sprite_table_pc = 0x4D2B2
    write_u16(data, 0x4C298, pc_to_snes(sprite_table_pc) & 0xFFFF)
    for room_id in range(ROOM_COUNT):
        write_u16(data, sprite_table_pc + room_id * 2, 0xD502)

    for room_id in range(ROOM_COUNT):
        write_u16(data, 0xDB69 + room_id * 2, 0xDDE7)

    header_table_pc = 0x110000
    write_u24(data, 0xB5DD, pc_to_snes(header_table_pc))
    data[0xB5E7] = 0x22
    for room_id in range(ROOM_COUNT):
        write_u16(
            data,
            header_table_pc + room_id * 2,
            0x8280 + room_id * 14,
        )

    write_u24(data, 0x128090, pc_to_snes(0x128450))
    data[0x128450 : 0x128454] = b"\xF0\xF0\xFF\xFF"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return data


class HackManifestMessagePolicyTest(unittest.TestCase):
    def test_expanded_messages_require_asm_rebuild_workflow(self) -> None:
        generated = generate_manifest(REPO_ROOT)
        generated_messages = generated["messages"]
        tracked_messages = json.loads(
            (REPO_ROOT / "Roms" / "hack_manifest.json").read_text(encoding="utf-8")
        )["messages"]

        self.assertEqual(generated_messages, tracked_messages)

        guidance = generated_messages["editing_guidance"]["expanded_asm_owned"]
        self.assertIn("ASM-owned bank $2F", guidance)
        self.assertIn("Core/message.asm", guidance)
        self.assertIn("Scripts/Build/build_rom.sh 168", guidance)
        self.assertIn("reopen or reload", guidance)

        policy_text = json.dumps(generated_messages)
        self.assertNotIn("message-write", policy_text)
        self.assertNotIn("z3ed", policy_text)

        self.assertEqual(generated["manifest_version"], 3)
        for region in generated["protected_regions"]["regions"]:
            for endpoint in ("start", "end"):
                address = int(region[endpoint], 16)
                self.assertGreaterEqual(address & 0xFFFF, 0x8000)
        self.assertTrue(
            any(
                region["start"] == "0x1EFF21"
                and region["end"] == "0x1EFF25"
                for region in generated["protected_regions"]["regions"]
            )
        )


class HackManifestDungeonLayoutTest(unittest.TestCase):
    def generate_synthetic(
        self,
        mutate=None,
    ) -> dict:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rom = root / "Roms" / "oos168.sfc"
            data = make_layout_rom(rom)
            if mutate is not None:
                mutate(data)
                rom.write_bytes(data)
            return generate_manifest(
                root,
                rom,
                root / "Roms" / "oos168x.sfc",
            )

    def test_emits_exact_live_dungeon_layout_and_editor_ranges(self) -> None:
        manifest = self.generate_synthetic()

        self.assertEqual(manifest["manifest_version"], 3)
        self.assertEqual(
            manifest["rom"]["path"],
            "Roms/oos168.sfc",
        )
        self.assertEqual(
            set(manifest["dungeon_stream_regions"]),
            {"objects", "sprites", "pot_items"},
        )
        self.assertEqual(
            manifest["dungeon_stream_regions"],
            {
                "objects": {
                    "pointer_table": "0x1F8000",
                    "pointer_count": ROOM_COUNT,
                    "pointer_encoding": "long24",
                    "strategy": "copy_on_write",
                    "data_regions": [
                        {"start": "0x0A8000", "end": "0x0AB730"},
                        {"start": "0x1F878A", "end": "0x208000"},
                        {"start": "0x03EB90", "end": "0x048000"},
                        {"start": "0x278000", "end": "0x288000"},
                        {"start": "0x298000", "end": "0x2A8000"},
                    ],
                    "allocation_regions": [
                        {"start": "0x298000", "end": "0x2A8000"}
                    ],
                },
                "sprites": {
                    "pointer_table": "0x09D2B2",
                    "pointer_count": ROOM_COUNT,
                    "pointer_encoding": "bank16",
                    "pointer_bank": "0x09",
                    "strategy": "copy_on_write",
                    "data_regions": [
                        {"start": "0x09D502", "end": "0x09EC9F"}
                    ],
                    "allocation_regions": [
                        {"start": "0x09D502", "end": "0x09EC9F"}
                    ],
                },
                "pot_items": {
                    "pointer_table": "0x01DB69",
                    "pointer_count": ROOM_COUNT,
                    "pointer_encoding": "bank16",
                    "pointer_bank": "0x01",
                    "strategy": "repack_all",
                    "data_regions": [
                        {"start": "0x01DDE7", "end": "0x01E6B2"}
                    ],
                    "allocation_regions": [
                        {"start": "0x01DDE7", "end": "0x01E6B2"}
                    ],
                },
            },
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
        self.assertNotIn(
            {"start": "0x25E000", "end": "0x268000"},
            manifest["editor_managed_regions"]["regions"],
        )

    def test_invalid_live_pointers_fail_closed(self) -> None:
        def make_collision_terminator_straddle(data: bytearray) -> None:
            write_u24(data, 0x128090, pc_to_snes(0x12DFFF))
            data[0x12DFFF : 0x12E001] = b"\xFF\xFF"

        mutations = {
            "object": (
                lambda data: write_u24(data, 0xF8000, pc_to_snes(0x60000)),
                "object pointer for room 0x000",
            ),
            "sprite": (
                lambda data: write_u16(data, 0x4D2B2, 0xD501),
                "minimum sprite pointer",
            ),
            "pot": (
                lambda data: write_u16(data, 0xDB69, 0x7000),
                "pot-item pointer for room 0x000 is unmapped",
            ),
            "collision": (
                lambda data: write_u24(data, 0x128090, pc_to_snes(0x12E000)),
                "custom-collision pointer for room 0x000",
            ),
            "collision_tail_straddle": (
                make_collision_terminator_straddle,
                "crosses reserved WaterFill data",
            ),
        }
        for name, (mutate, expected) in mutations.items():
            with self.subTest(name=name):
                with self.assertRaisesRegex(ManifestGenerationError, expected):
                    self.generate_synthetic(mutate)

    def test_missing_explicit_editable_rom_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            missing = root / "Roms" / "missing.sfc"
            with self.assertRaisesRegex(
                ManifestGenerationError,
                "editable ROM does not exist",
            ):
                generate_manifest(root, missing)

    def test_generation_is_deterministic_for_same_editable_rom(self) -> None:
        first = self.generate_synthetic()
        second = self.generate_synthetic()
        self.assertEqual(first, second)

    def test_tracked_manifest_has_v3_daily_driver_contract(self) -> None:
        tracked = json.loads(
            (REPO_ROOT / "Roms" / "hack_manifest.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(tracked["manifest_version"], 3)
        self.assertEqual(
            set(tracked["dungeon_stream_regions"]),
            {"objects", "sprites", "pot_items"},
        )
        self.assertEqual(
            tracked["editor_managed_regions"]["regions"],
            [
                {"start": "0x07F61D", "end": "0x07F86D"},
                {"start": "0x228280", "end": "0x2292B0"},
                {"start": "0x258090", "end": "0x258408"},
                {"start": "0x258450", "end": "0x25E000"},
            ],
        )


if __name__ == "__main__":
    unittest.main()
