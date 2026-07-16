from __future__ import annotations

import re
import subprocess
import sys
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from Scripts.Generate import generate_water_fill_table as water_fill


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "Scripts/Generate/generate_water_fill_table.py"
TRACKED_TABLE = REPO_ROOT / "Dungeons/generated/water_fill_table.asm"
ROM_SIZE = 0x130000


@dataclass(frozen=True)
class ParsedZone:
    room_id: int
    mask: int
    data_offset: int
    tile_count: int
    payload: tuple[int, ...]


@dataclass(frozen=True)
class ParsedTable:
    zone_count: int
    zones: tuple[ParsedZone, ...]


def parse_emitted_table(asm: str) -> ParsedTable:
    """Parse runtime directives, deliberately ignoring all `; tiles=` comments."""
    header = re.search(
        r"WaterFillTable_Generated:\s*\{\s*db\s+\$([0-9A-Fa-f]+)(.*?)\}",
        asm,
        re.DOTALL,
    )
    if not header:
        raise ValueError("WaterFillTable_Generated block not found")

    zone_count = int(header.group(1), 16)
    entry_matches = re.findall(
        r"^\s*db\s+\$([0-9A-Fa-f]+),\s*\$([0-9A-Fa-f]+)\s*"
        r":\s*dw\s+\$([0-9A-Fa-f]+)",
        header.group(2),
        re.MULTILINE,
    )

    zones: list[ParsedZone] = []
    for room_raw, mask_raw, offset_raw in entry_matches:
        room_id = int(room_raw, 16)
        data_block = re.search(
            rf"WaterFillData_Room{room_id:02X}:\s*\{{(.*?)\}}",
            asm,
            re.DOTALL,
        )
        if not data_block:
            raise ValueError(f"WaterFillData_Room{room_id:02X} block not found")

        count_match = re.search(
            r"^\s*db\s+\$([0-9A-Fa-f]+)",
            data_block.group(1),
            re.MULTILINE,
        )
        if not count_match:
            raise ValueError(f"Room {room_id:02X} count directive not found")

        payload: list[int] = []
        for values in re.findall(
            r"^\s*dw\s+([^;\n]+)", data_block.group(1), re.MULTILINE
        ):
            payload.extend(
                int(raw, 16)
                for raw in re.findall(r"\$([0-9A-Fa-f]+)", values)
            )

        zones.append(
            ParsedZone(
                room_id=room_id,
                mask=int(mask_raw, 16),
                data_offset=int(offset_raw, 16),
                tile_count=int(count_match.group(1), 16),
                payload=tuple(payload),
            )
        )

    return ParsedTable(zone_count=zone_count, zones=tuple(zones))


def pc_to_lorom(pc: int) -> int:
    bank = (pc >> 15) & 0x7F
    address = (pc & 0x7FFF) | 0x8000
    return (bank << 16) | address


def make_marker_rom(path: Path, rooms: tuple[int, ...]) -> None:
    data = bytearray(ROM_SIZE)
    pointer_table = water_fill.snes_to_pc(water_fill.ROOM_POINTER_SNES)

    for index, room_id in enumerate(rooms):
        stream_pc = water_fill.CUSTOM_COLLISION_DATA_PC_START + (index * 0x10)
        stream_snes = pc_to_lorom(stream_pc)
        pointer_pc = pointer_table + (room_id * 3)
        data[pointer_pc : pointer_pc + 3] = stream_snes.to_bytes(3, "little")

        # Single-tile stream: marker, one offset/tile pair, terminator.
        data[stream_pc : stream_pc + 7] = bytes(
            (0xF0, 0xF0, room_id, 0x01, 0xF5, 0xFF, 0xFF)
        )

    path.write_bytes(data)


class WaterFillGenerationTest(unittest.TestCase):
    def run_generator(self, rom: Path, output: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(GENERATOR),
                "--rom",
                str(rom),
                "--out-asm",
                str(output),
                "--require-rooms",
                "0x25,0x27",
            ],
            cwd=REPO_ROOT,
            check=False,
            capture_output=True,
            text=True,
        )

    def test_required_rooms_reject_incomplete_authoring_rom(self) -> None:
        cases = (
            ((0x25,), "0x27"),
            ((0x27,), "0x25"),
            ((), "0x25, 0x27"),
        )
        for rooms, missing in cases:
            with self.subTest(rooms=rooms), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                rom = root / "authoring.sfc"
                output = root / "water_fill_table.asm"
                make_marker_rom(rom, rooms)

                result = self.run_generator(rom, output)

                self.assertNotEqual(result.returncode, 0)
                self.assertIn(
                    f"Required water-fill rooms have no marker tiles: {missing}",
                    result.stderr,
                )
                self.assertFalse(output.exists())

    def test_required_rooms_generate_complete_d4_table(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rom = root / "authoring.sfc"
            output = root / "water_fill_table.asm"
            make_marker_rom(rom, (0x25, 0x27))

            result = self.run_generator(rom, output)

            self.assertEqual(result.returncode, 0, result.stderr)
            table = parse_emitted_table(output.read_text())
            self.assertEqual(table.zone_count, 2)
            self.assertEqual(
                table.zones,
                (
                    ParsedZone(0x25, 0x02, 0x0009, 1, (0x0125,)),
                    ParsedZone(0x27, 0x01, 0x000C, 1, (0x0127,)),
                ),
            )

    def test_tracked_release_table_keeps_both_d4_rooms(self) -> None:
        table = parse_emitted_table(TRACKED_TABLE.read_text())
        self.assertEqual(table.zone_count, 2)
        self.assertEqual(len(table.zones), table.zone_count)

        expected = (
            (0x25, 0x02, 0x0009, 0xA8),
            (0x27, 0x01, 0x015A, 0xDE),
        )
        running_offset = 1 + (table.zone_count * 4)
        for zone, (room_id, mask, data_offset, tile_count) in zip(
            table.zones, expected, strict=True
        ):
            self.assertEqual(zone.room_id, room_id)
            self.assertEqual(zone.mask, mask)
            self.assertEqual(zone.data_offset, data_offset)
            self.assertEqual(zone.data_offset, running_offset)
            self.assertEqual(zone.tile_count, tile_count)
            self.assertEqual(len(zone.payload), tile_count)
            running_offset += 1 + (len(zone.payload) * 2)


if __name__ == "__main__":
    unittest.main()
