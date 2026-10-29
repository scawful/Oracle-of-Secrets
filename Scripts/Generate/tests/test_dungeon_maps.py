from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import dungeon_maps as maps


def map_rom() -> bytearray:
    """Four basement grids per slot, with one placed boss on B4."""
    data = bytearray(0x110000)
    for slot in range(14):
        rooms = maps.DATA_START + slot * 100
        templates = 0x57700 + slot
        data[maps.FLOOR_COUNTS + slot * 2] = 4
        for table, pc in ((maps.ROOM_PTRS, rooms), (maps.TMPL_PTRS, templates)):
            data[table + slot * 2:table + slot * 2 + 2] = (0x8000 | (pc & 0x7FFF)).to_bytes(2, "little")
        data[rooms:rooms + 100] = bytes([maps.EMPTY]) * 100
        data[rooms] = 0x20 + slot
        data[maps.BOSS_ROOMS + slot * 2:maps.BOSS_ROOMS + slot * 2 + 2] = (0x20 + slot).to_bytes(2, "little")
        data[maps.BOSS_FLOORS + slot * 2] = 0xFC
        data[maps.BOSS_FLOORS + slot * 2 + 1] = (0x00, 0x80, 0xFF, 0x12)[slot % 4]
    return data


class DungeonMapFloorTest(unittest.TestCase):
    def test_native_floor_byte_is_signed_independently_of_icon_flags(self):
        data = map_rom()
        for raw, expected, flags in ((0xFC, -4, 0), (0xFC, -4, 0xFF),
                                     (1, 1, 0x80), (0x80, -128, 0x7F)):
            with self.subTest(raw=raw, flags=flags):
                data[maps.BOSS_FLOORS:maps.BOSS_FLOORS + 2] = bytes((raw, flags))
                dungeon = maps.MapRom(data).dungeon(0)
                self.assertEqual(dungeon["boss_floor"], expected)
                self.assertEqual(dungeon["boss_icon_flags"], flags)

    def test_repack_unchanged_maps_preserves_every_byte(self):
        data = map_rom()
        decoded = [maps.MapRom(data).dungeon(slot) for slot in range(14)]
        self.assertEqual(maps.repack(data, decoded), data)

    def test_floor_change_preserves_all_icon_flags(self):
        data = map_rom()
        data[maps.BOSS_FLOORS + 10] = 0
        decoded = [maps.MapRom(data).dungeon(slot) for slot in range(14)]
        decoded[5]["boss_floor"] = -4
        after = maps.repack(data, decoded)
        changed = [pc for pc, (old, new) in enumerate(zip(data, after)) if old != new]
        self.assertEqual(changed, [maps.BOSS_FLOORS + 10])
        self.assertEqual(after[maps.BOSS_FLOORS + 10:maps.BOSS_FLOORS + 12], bytes((0xFC, 0x80)))

    def test_preview_honors_native_icon_disable_bit(self):
        data = map_rom()
        with patch.object(maps, "map_chars", return_value=[]), patch.object(
                maps, "template_pixels", return_value=[[0] * 16 for _ in range(16)]):
            for flags, border in ((0x00, (255, 70, 70)), (0x7F, (255, 70, 70)),
                                  (0x80, (52, 52, 64)), (0xFF, (52, 52, 64))):
                with self.subTest(flags=flags):
                    data[maps.BOSS_FLOORS + 1] = flags
                    image = maps.render_maps(data, 0, "boss icon")
                    self.assertEqual(image.getpixel((12, 30)), border)


if __name__ == "__main__":
    unittest.main()
