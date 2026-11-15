"""Private kit palettes must remain unreferenced by compiled room headers."""
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_wall_profiles as profiles


class WallKitPaletteOwnershipTest(unittest.TestCase):
    def rom(self):
        data = bytearray(0x200000)
        for pid, offset in profiles.PRIVATE_PALETTES.items():
            struct.pack_into('<H', data, profiles.snes_pc(profiles.PAL_INDEX) + pid, offset)
        for room in range(profiles.ROOM_COUNT):
            struct.pack_into('<H', data, profiles.snes_pc(profiles.ROOM_HEADERS) + room * 2,
                             0x9000 + room * 4)
        return data

    def test_ordinary_and_sky_palettes_remain_legal(self):
        data = self.rom()
        # Sky's source override consumes $1C; it is not a spare private palette.
        data[profiles.snes_pc(profiles.PAL_SETS)] = 0x1C
        self.assertEqual(profiles.verify_palette_ownership(data)['rooms_checked'], 296)

    def test_compiled_palette_set_override_is_rejected(self):
        data = self.rom()
        data[profiles.room_header(data, 0x0C) + 1] = 3
        profiles.verify_palette_ownership(data)  # Editable input was unreferenced.
        data[profiles.snes_pc(profiles.PAL_SETS) + 3 * 4] = 0x1A
        with self.assertRaisesRegex(ValueError, r'room \$00C uses private kit palette \$1A'):
            profiles.verify_palette_ownership(data)

    def test_offset_alias_or_truncated_rom_is_rejected(self):
        data = self.rom()
        struct.pack_into('<H', data, profiles.snes_pc(profiles.PAL_INDEX) + 0x1A, 0)
        with self.assertRaisesRegex(ValueError, 'offset moved'):
            profiles.verify_palette_ownership(data)
        with self.assertRaisesRegex(ValueError, 'too short'):
            profiles.verify_palette_ownership(b'')

    def test_unmapped_header_is_rejected(self):
        data = self.rom()
        struct.pack_into('<H', data, profiles.snes_pc(profiles.ROOM_HEADERS), 0)
        with self.assertRaisesRegex(ValueError, 'header is not mapped ROM'):
            profiles.verify_palette_ownership(data)

    def test_new_palette_is_admitted_but_sky_and_table_alias_are_not(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'fortress.kit.json'
            kit = {'kit': 'fortress', 'verdict': 'partial', 'profile': 'fortress',
                   'palette': {'id': '0x1A', 'copy_of': '0x0E',
                               'copy_offset': '0x04EC', 'splices': []}}
            with mock.patch.object(profiles, 'KITS_DIR', Path(directory)):
                path.write_text(json.dumps(kit))
                self.assertEqual(len(profiles.load_kits()), 1)
                for forbidden in ('0x1C', '0x28'):
                    kit['palette']['id'] = forbidden
                    path.write_text(json.dumps(kit))
                    with self.assertRaisesRegex(SystemExit, 'not a free private palette'):
                        profiles.load_kits()


if __name__ == '__main__':
    unittest.main()
