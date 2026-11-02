#!/usr/bin/env python3
"""ROM-free preservation, allocation and refusal checks for 2bpp HUD icons."""
import hashlib
import contextlib
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT/'Scripts/Generate'))
import lz2
import menu_icon_overrides as icons
from sheet_table import TBL_BANK, TBL_HIGH, TBL_LOW, pc


class MenuIconOverrides(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.spec_path = self.root/'spec.json'
        self.spec = json.loads((ROOT/icons.SPEC).read_text())
        self.rom = bytearray(0x220000)
        self.bases = {}
        for entry, position in zip(self.spec['sheets'], (0x028000, 0x038000, 0x048000)):
            sheet = icons.number(entry['sprite_sheet'])
            raw = bytearray(bytes(range(256))*8)
            for tile in icons.TILES | {icons.BLANK}:
                owner, offset = icons.tile_location(tile)
                if owner == sheet:
                    raw[offset:offset+16] = bytes(16)
            self.bases[sheet] = bytes(raw)
            entry['base_sha256'] = hashlib.sha256(raw).hexdigest()
            stream = lz2.stored(raw)
            self.rom[pc(position):pc(position)+len(stream)] = stream
            for table, shift in ((TBL_BANK, 16), (TBL_HIGH, 8), (TBL_LOW, 0)):
                self.rom[pc(table)+sheet+0x73] = (position >> shift) & 255
        for index, entry in enumerate(self.spec['icons']):
            source = self.root/entry['source']
            source.parent.mkdir(exist_ok=True)
            source.write_bytes(bytes(range(1+index, 65+index)))
        self.base = self.root/'base.sfc'
        self.base.write_bytes(self.rom)
        self.write_spec()

    def write_spec(self):
        self.spec_path.write_text(json.dumps(self.spec))

    def build(self):
        return icons.build(self.spec_path, self.base)

    def test_preserves_all_non_icon_bytes_and_blank(self):
        _, items = self.build()
        for item in items:
            expected = bytearray(self.bases[item['s']])
            for entry in self.spec['icons']:
                pixels = (self.root/entry['source']).read_bytes()
                for quadrant, value in enumerate(entry['tiles']):
                    sheet, offset = icons.tile_location(icons.number(value))
                    if sheet == item['s']:
                        expected[offset:offset+16] = pixels[quadrant*16:(quadrant+1)*16]
            decoded, consumed = lz2.decompress(item['stream'], max_output=0x800)
            self.assertEqual(decoded, bytes(expected))
            self.assertEqual(consumed, len(item['stream']))
        blank_sheet = next(item for item in items if item['s'] == 0x6A)
        self.assertEqual(blank_sheet['raw'][0x7F0:0x800], bytes(16))
        self.assertEqual(self.base.read_bytes(), self.rom)

    def test_only_nine_independent_pointer_bytes_owned(self):
        _, items = self.build()
        source = icons.generated_files(items)[Path('menu_icon_overrides.asm')].decode()
        self.assertEqual(source.count('protected_size=1'), 9)
        self.assertEqual(source.count('assert read1('), 9)
        self.assertEqual(source.count('assert pc() =='), 9)
        for sheet in icons.SHEETS:
            for table in (TBL_BANK, TBL_HIGH, TBL_LOW):
                self.assertIn(f'org ${table+sheet+0x73:06X} ', source)
        self.assertIn('assert pc() <= $43A000', source)

    def test_changed_base_sheet_refused(self):
        self.spec['sheets'][0]['base_sha256'] = '0'*64
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'base sheet changed'):
            self.build()

    def test_blank_or_duplicate_tile_refused(self):
        for replacement, message in (('0x07F', 'canonical blank'), ('0x00E', 'already allocated')):
            with self.subTest(replacement=replacement):
                self.spec['icons'][0]['tiles'][0] = replacement
                self.write_spec()
                with self.assertRaisesRegex(ValueError, message):
                    self.build()

    def test_occupied_target_refused_even_with_matching_hash(self):
        raw = bytearray(self.bases[0x6A])
        raw[0x0D0] = 1
        stream = lz2.stored(raw)
        self.rom[pc(0x038000):pc(0x038000)+len(stream)] = stream
        self.base.write_bytes(self.rom)
        self.spec['sheets'][1]['base_sha256'] = hashlib.sha256(raw).hexdigest()
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'is not empty'):
            self.build()

    def test_icon_size_and_empty_icon_refused(self):
        source = self.root/self.spec['icons'][0]['source']
        for data, message in ((bytes(63), '64 bytes'), (bytes(64), 'transparent')):
            with self.subTest(length=len(data)):
                source.write_bytes(data)
                with self.assertRaisesRegex(ValueError, message):
                    self.build()

    def test_icon_path_escape_refused(self):
        self.spec['icons'][0]['source'] = '../outside.2bpp'
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'inside spec directory'):
            self.build()

    def test_capacity_enforced(self):
        old_capacity = icons.CAPACITY
        self.addCleanup(setattr, icons, 'CAPACITY', old_capacity)
        icons.CAPACITY = 1
        self.spec['capacity'] = 1
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'allocation is full'):
            self.build()

    def test_occupied_bank_refused(self):
        self.rom[pc(icons.START)] = 1
        with self.assertRaisesRegex(ValueError, 'allocation is occupied'):
            icons.validate_reservation(self.root, self.rom)

    def test_check_refuses_stale_generated_file_without_rewriting_it(self):
        out = self.root/'generated'
        arguments = ['menu_icon_overrides.py', str(self.spec_path), '--root', str(self.root),
                     '--base-rom', str(self.base), '--out-dir', str(out)]
        with mock.patch.object(icons, 'validate_reservation'), mock.patch.object(sys, 'argv', arguments):
            with contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(icons.main(), 0)
        stale = out/'sheets/spr69.bin'
        stale.write_bytes(b'stale')
        with mock.patch.object(icons, 'validate_reservation'), mock.patch.object(sys, 'argv', arguments+['--check']):
            with contextlib.redirect_stderr(io.StringIO()) as errors:
                self.assertEqual(icons.main(), 1)
        self.assertIn('stale generated', errors.getvalue())
        self.assertEqual(stale.read_bytes(), b'stale')
        self.assertEqual(self.base.read_bytes(), self.rom)

    def test_reachable_competing_bank_writer_refused(self):
        (self.root/'Oracle_main.asm').write_text('org $438100\n')
        with self.assertRaisesRegex(ValueError, 'another reachable source owns bank'):
            icons.validate_reservation(self.root, self.rom)

    def test_allocation_and_sheet_scope_cannot_expand(self):
        self.spec['sheets'][0]['sprite_sheet'] = '0x68'
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'unsupported or duplicate'):
            self.build()
        self.spec['sheets'][0]['sprite_sheet'] = '0x69'
        self.spec['start'] = '0x428000'
        self.write_spec()
        with self.assertRaisesRegex(ValueError, 'audited'):
            self.build()


if __name__ == '__main__':
    unittest.main()
