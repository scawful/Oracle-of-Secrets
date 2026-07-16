from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from Scripts.Generate import generate_water_fill_table as water_fill


REPO_ROOT = Path(__file__).resolve().parents[2]
GENERATOR = REPO_ROOT / "Scripts/Generate/generate_water_fill_table.py"
TRACKED_TABLE = REPO_ROOT / "Dungeons/generated/water_fill_table.asm"
ROM_SIZE = 0x130000


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
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            rom = root / "authoring.sfc"
            output = root / "water_fill_table.asm"
            make_marker_rom(rom, (0x25,))

            result = self.run_generator(rom, output)

            self.assertNotEqual(result.returncode, 0)
            self.assertIn(
                "Required water-fill rooms have no marker tiles: 0x27",
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
            generated = output.read_text()
            self.assertIn("  db $02", generated)
            self.assertIn("  db $25, $02 : dw $0009 ; tiles=1", generated)
            self.assertIn("  db $27, $01 : dw $000C ; tiles=1", generated)

    def test_tracked_release_table_keeps_both_d4_rooms(self) -> None:
        tracked = TRACKED_TABLE.read_text()
        self.assertIn("  db $25, $02 : dw $0009 ; tiles=168", tracked)
        self.assertIn("  db $27, $01 : dw $015A ; tiles=222", tracked)


if __name__ == "__main__":
    unittest.main()
