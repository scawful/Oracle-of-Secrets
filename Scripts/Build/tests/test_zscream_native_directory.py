"""The generated native directory has one explicit source/range allocation."""
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_zscream_overlap as C


class NativeDirectoryEmissionTest(unittest.TestCase):
    def test_only_generated_directory_emissions_within_its_extent_are_owned(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'candidate.sym'
            for source, address, accepted in (
                    ('.cache/special_overworld_native_data.asm', 0x28F000, True),
                    ('.cache/special_overworld_native_data.asm', 0x28F3FF, True),
                    ('.cache/special_overworld_native_data.asm', 0x28EFFF, False),
                    ('.cache/special_overworld_native_data.asm', 0x28F400, False),
                    ('Overworld/unrelated.asm', 0x28F000, False)):
                with self.subTest(source=source, address=address):
                    location = f'{address >> 16:02X}:{address & 65535:04X}'
                    path.write_text('[labels]\n' + location + ' Directory\n'
                        + '[source files]\n00000000 00000000 ' + source + '\n'
                        + '[addr-to-line mapping]\n' + location + ' 00000000:00000001\n')
                    overlaps = C.check_overlaps(path,
                        [dict(start=0x140000, end=0x147FFF, name='Custom overworld data')])
                    self.assertEqual(not overlaps, accepted)


if __name__ == '__main__':
    unittest.main()
