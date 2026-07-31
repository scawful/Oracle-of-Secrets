from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


GENERATE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = GENERATE_DIR.parents[1]
sys.path.insert(0, str(GENERATE_DIR))

from validate_custom_collision_source import (  # noqa: E402
    COLLISION_DATA_START,
    POINTER_TABLE_START,
    SOURCE_PATH,
    WATER_FILL_TABLE_END_EXCLUSIVE,
    CustomCollisionSourceContractError,
    validate_contract,
)


class CustomCollisionSourceContractTest(unittest.TestCase):
    def write_source(
        self,
        root: Path,
        rooms: list[dict[str, object]],
    ) -> Path:
        path = root / SOURCE_PATH
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {"rooms": rooms, "version": 1},
                ensure_ascii=True,
                indent=2,
                sort_keys=True,
            ),
            encoding="ascii",
        )
        return path

    def write_rom(
        self,
        root: Path,
        room_tiles: dict[int, list[tuple[int, int]]],
    ) -> Path:
        streams: dict[int, bytes] = {}
        for room_id, tiles in room_tiles.items():
            encoded = bytearray(b"\xF0\xF0")
            for offset, value in sorted(tiles):
                encoded.extend(offset.to_bytes(2, "little"))
                encoded.append(value)
            encoded.extend(b"\xFF\xFF")
            streams[room_id] = bytes(encoded)
        return self.write_raw_rom(root, streams)

    def write_raw_rom(
        self,
        root: Path,
        room_streams: dict[int, bytes],
    ) -> Path:
        data = bytearray(WATER_FILL_TABLE_END_EXCLUSIVE)
        cursor = COLLISION_DATA_START
        for room_id, stream in sorted(room_streams.items()):
            snes_pointer = ((cursor >> 15) << 16) | (cursor & 0x7FFF) | 0x8000
            pointer_offset = POINTER_TABLE_START + (room_id * 3)
            data[pointer_offset : pointer_offset + 3] = (
                snes_pointer.to_bytes(3, "little")
            )
            data[cursor : cursor + len(stream)] = stream
            cursor += len(stream)

        rom_path = root / "fixture.sfc"
        rom_path.write_bytes(data)
        return rom_path

    def test_repository_source_is_complete(self) -> None:
        contract = validate_contract(REPO_ROOT)

        self.assertEqual(contract.room_count, 18)
        self.assertEqual(contract.tile_count, 2491)
        self.assertEqual(
            contract.source_sha256,
            "af221afd9226b4d321155135899a5208cc86badac58f7f1af195a725495e49bc",
        )

    def test_repository_source_forces_exact_export_bytes(self) -> None:
        attributes = (REPO_ROOT / ".gitattributes").read_text(
            encoding="utf-8"
        )

        self.assertIn(
            "Data/dungeons/custom_collision.json text eol=lf",
            attributes.splitlines(),
        )
        self.assertNotIn(b"\r\n", (REPO_ROOT / SOURCE_PATH).read_bytes())

    def test_readme_provenance_matches_locked_source(self) -> None:
        readme = (REPO_ROOT / "Data/dungeons/README.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("source: 18 rooms, 2,491 nonzero tiles", readme)
        self.assertIn(
            "af221afd9226b4d321155135899a5208cc86badac58f7f1af195a725495e49bc",
            readme,
        )

    def test_duplicate_room_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            room = {"room_id": "0x25", "tiles": [[1, 7]]}
            self.write_source(root, [room, room])

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "rooms must be unique and sorted",
            ):
                validate_contract(root)

    def test_duplicate_tile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[1, 7], [1, 8]]}],
            )

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "tiles must be unique and sorted",
            ):
                validate_contract(root)

    def test_out_of_range_tile_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[4096, 7]]}],
            )

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "offset must be integer 0..4095",
            ):
                validate_contract(root)

    def test_rom_exact_match_passes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[5, 7], [70, 8]]}],
            )
            rom_path = self.write_rom(root, {0x25: [(5, 7), (70, 8)]})

            contract = validate_contract(root, rom_path)

            self.assertEqual(contract.room_count, 1)
            self.assertEqual(contract.tile_count, 2)
            self.assertIsNotNone(contract.rom_sha256)

    def test_rom_rectangle_then_single_tile_overwrite_and_clear(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [
                    {
                        "room_id": "0x25",
                        "tiles": [[65, 1], [66, 9], [130, 4]],
                    }
                ],
            )
            stream = bytearray()
            stream.extend((65).to_bytes(2, "little"))
            stream.extend((2, 2, 1, 2, 3, 4))
            stream.extend(b"\xF0\xF0")
            stream.extend((66).to_bytes(2, "little"))
            stream.append(9)
            stream.extend((129).to_bytes(2, "little"))
            stream.append(0)
            stream.extend(b"\xFF\xFF")
            rom_path = self.write_raw_rom(root, {0x25: bytes(stream)})

            contract = validate_contract(root, rom_path)

            self.assertEqual(contract.tile_count, 3)

    def test_rom_tile_drift_fails_with_room_and_count(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[5, 7]]}],
            )
            rom_path = self.write_rom(root, {0x25: [(5, 9)]})

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                r"room 0x25 differs.*1 tile",
            ):
                validate_contract(root, rom_path)

    def test_rom_untracked_room_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[5, 7]]}],
            )
            rom_path = self.write_rom(
                root,
                {0x25: [(5, 7)], 0x27: [(6, 8)]},
            )

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "untracked custom-collision rooms: 0x27",
            ):
                validate_contract(root, rom_path)

    def test_rom_missing_canonical_room_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [
                    {"room_id": "0x25", "tiles": [[5, 7]]},
                    {"room_id": "0x27", "tiles": [[6, 8]]},
                ],
            )
            rom_path = self.write_rom(root, {0x25: [(5, 7)]})

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "missing canonical custom-collision rooms: 0x27",
            ):
                validate_contract(root, rom_path)

    def test_rom_unterminated_stream_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[5, 7]]}],
            )
            stream = b"\xF0\xF0\x05\x00\x07"
            rom_path = self.write_raw_rom(root, {0x25: stream})

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "unterminated before the reserved water-fill region",
            ):
                validate_contract(root, rom_path)

    def test_rom_pointer_into_reserved_tail_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(
                root,
                [{"room_id": "0x25", "tiles": [[5, 7]]}],
            )
            rom_path = self.write_raw_rom(root, {})
            data = bytearray(rom_path.read_bytes())
            reserved_pointer = (
                ((0x12E000 >> 15) << 16) | (0x12E000 & 0x7FFF) | 0x8000
            )
            pointer_offset = POINTER_TABLE_START + (0x25 * 3)
            data[pointer_offset : pointer_offset + 3] = (
                reserved_pointer.to_bytes(3, "little")
            )
            rom_path.write_bytes(data)

            with self.assertRaisesRegex(
                CustomCollisionSourceContractError,
                "maps outside collision data",
            ):
                validate_contract(root, rom_path)

    def test_rom_all_zero_pointer_is_omitted_like_z3ed_export(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.write_source(root, [])
            rom_path = self.write_rom(root, {0x74: [(5, 0)]})

            contract = validate_contract(root, rom_path)

            self.assertEqual(contract.room_count, 0)
            self.assertEqual(contract.tile_count, 0)

    def test_build_validates_selected_base_before_generators(self) -> None:
        build = (REPO_ROOT / "Scripts/Build/build_rom.sh").read_text(
            encoding="utf-8"
        )
        validator_call = (
            'python3 "$repo_root/Scripts/Generate/'
            'validate_custom_collision_source.py"'
        )

        self.assertEqual(build.count(validator_call), 1)
        self.assertEqual(build.count('--rom "$base_rom"'), 1)
        self.assertIn(
            'water_table_rom="${OOS_WATER_TABLE_ROM:-$base_rom}"',
            build,
        )
        self.assertNotIn('water_table_rom="$patched_rom"', build)
        self.assertNotIn('yaze_rom_rel=', build)
        self.assertLess(
            build.index(validator_call),
            build.index("generate_water_gate_runtime_tables.py"),
        )
        self.assertLess(
            build.index(validator_call),
            build.index("generate_water_fill_table.py"),
        )


if __name__ == "__main__":
    unittest.main()
