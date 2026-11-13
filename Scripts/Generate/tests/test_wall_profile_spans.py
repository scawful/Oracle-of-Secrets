"""Extraction must respect native object-data boundaries, including diagonals."""
import argparse
import contextlib
import io
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import gen_wall_profiles as profiles


class WallProfileSpanTest(unittest.TestCase):
    DIAGONALS = tuple(range(0x009, 0x015))

    def fixture(self):
        data = bytearray(0x9000)
        expected = {}
        for i, obj in enumerate(profiles.CLASSES):
            count = (16 if obj >= 0x100 else
                     12 if obj in (0x03A, 0x03B, 0x076, 0x077, 0x081, 0x082) else 8)
            offset = 0x1000 + i * 0x40
            table = 0x8000 + obj * 2 if obj < 0x100 else 0x83F0 + (obj - 0x100) * 2
            struct.pack_into('<H', data, table, offset)
            values = [0x2000 + i * 0x10 + k for k in range(count)]
            struct.pack_into(f'<{count}H', data, profiles.OBJ_TABLE_PC + offset, *values)
            expected[f'{obj:03X}'] = [f'${v:04X}' for v in values]
        # Native $01:8000 offsets: each 009..014 owns exactly ten bytes.
        # Include 015 as the final adjacent sentinel, without admitting a class.
        for obj in range(0x009, 0x016):
            offset = 0x0420 + (obj - 0x009) * 10
            struct.pack_into('<H', data, 0x8000 + obj * 2, offset)
            struct.pack_into('<5H', data, profiles.OBJ_TABLE_PC + offset,
                             *(0x6000 + obj * 8 + k for k in range(5)))
        struct.pack_into('<H', data, 0x8000 + 0x057 * 2,
                         profiles.obj_offset(data, 0x081))
        return data, expected

    def extract(self, base, candidate, obj=None, reference=False):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            base_path, src_path = root / 'base.sfc', root / 'candidate.sfc'
            base_path.write_bytes(base)
            src_path.write_bytes(candidate)
            args = argparse.Namespace(name='fixture', rom=str(src_path), base=str(base_path),
                                      reference=str(base_path) if reference else None,
                                      classes=f'{obj:03X}' if obj is not None else None, note='fixture')
            # Exercise diagonal extraction without activating selector classes.
            classes = self.DIAGONALS if obj is not None else profiles.CLASSES
            with mock.patch.object(profiles, 'CLASSES', classes), \
                    mock.patch.object(profiles, 'REPO', root), \
                    mock.patch.object(profiles, 'DATA_DIR', root), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(profiles.cmd_extract(args), 0)
            return json.loads((root / 'fixture.words.json').read_text())['classes']

    def test_diagonal_extraction_stops_before_next_object(self):
        base, _ = self.fixture()
        for obj in self.DIAGONALS:
            with self.subTest(object=f'{obj:03X}'):
                pc = profiles.OBJ_TABLE_PC + profiles.obj_offset(base, obj)
                expected = [f'${v:04X}' for v in struct.unpack_from('<5H', base, pc)]
                self.assertEqual(self.extract(base, base, obj), {f'{obj:03X}': expected})

    def test_reference_filter_does_not_attribute_adjacent_object_edit(self):
        base, _ = self.fixture()
        for obj in self.DIAGONALS:
            with self.subTest(object=f'{obj:03X}'):
                candidate = bytearray(base)
                next_pc = profiles.OBJ_TABLE_PC + profiles.obj_offset(base, obj + 1)
                struct.pack_into('<3H', candidate, next_pc, 0x7A01, 0x7A02, 0x7A03)
                self.assertEqual(self.extract(base, candidate, obj, reference=True), {})

    def test_existing_selector_classes_keep_their_complete_spans(self):
        base, expected = self.fixture()
        self.assertEqual(self.extract(base, base), expected)


if __name__ == '__main__':
    unittest.main()
