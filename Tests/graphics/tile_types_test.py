import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
MODULE = ROOT / 'Scripts/Graphics/tile_types.py'
CLASSES = ROOT / 'Scripts/Graphics/tile_type_classes.json'
spec = importlib.util.spec_from_file_location('tile_types', MODULE)
t = importlib.util.module_from_spec(spec)
spec.loader.exec_module(t)

# Synthetic layout: bank $0E tables at vanilla addresses, groups in bank $10.
OFFSETS = (0x10, 0x8000)
GROUPS = (0x10, 0x8030)
SYM = """; wla symbolic information file
[labels]
10:8000 Oracle_group_offsets
10:8030 Oracle_group00
10:8030 Oracle_offs
10:9000 Oracle_offs_decoy

[source files]
0000 00000000 Dungeons/Collision/CollisionTablesExpanded.asm
10:8000 Oracle_not_a_label
"""


def synthetic_rom():
    rom = bytearray(0x88000)
    ow = t.lorom_pc(0x0E, 0x9459)
    rom[ow:ow + 0x200] = bytes(c & 0xFF for c in range(0x200))
    uw = t.lorom_pc(0x0E, 0x9659)
    rom[uw:uw + 0x180] = bytes((0x80 | c) & 0xFF for c in range(0x180))
    offsets = t.lorom_pc(*OFFSETS)
    groups = t.lorom_pc(*GROUPS)
    for blockset in range(24):
        offset = (blockset % 3) * 0x80  # three distinct groups shared across blocksets, like the asm
        rom[offsets + blockset * 2:offsets + blockset * 2 + 2] = offset.to_bytes(2, 'little')
    for group in range(3):
        rom[groups + group * 0x80:groups + group * 0x80 + 0x80] = bytes([0x10 + group]) * 0x40 + bytes([0x20 + group]) * 0x40
    return bytes(rom)


class TileTypesTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.dir = Path(self.temp.name)
        self.rom = self.dir / 'test.sfc'
        self.rom.write_bytes(synthetic_rom())
        self.sym = self.dir / 'test.sym'
        self.sym.write_text(SYM)

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args):
        return subprocess.run([sys.executable, str(MODULE), '--rom', str(self.rom), *args], capture_output=True, text=True)

    def test_lorom_mapping(self):
        self.assertEqual(t.lorom_pc(0x0E, 0x9459), 0x71459)
        self.assertEqual(t.lorom_pc(0x0E, 0x9659), 0x71659)
        self.assertEqual(t.lorom_pc(0x2C, 0x887F), 0x16087F)
        self.assertEqual(t.lorom_pc(0x80, 0x8000), 0)
        self.assertEqual(t.lorom_pc(0xAC, 0x887F), 0x16087F)
        with self.assertRaises(ValueError):
            t.lorom_pc(0x0E, 0x7FFF)

    def test_sym_label_resolution(self):
        labels = t.parse_sym(SYM)
        self.assertEqual(labels['Oracle_group_offsets'], OFFSETS)
        self.assertEqual(t.find_label(labels, t.GROUP_DATA_LABELS), ('Oracle_offs', GROUPS))
        self.assertNotIn('Oracle_not_a_label', labels)
        with self.assertRaises(ValueError):
            t.find_label({}, t.GROUP_OFFSET_LABELS)

    def test_cli_writes_schema_and_hashes(self):
        out = self.dir / 'slot_types.json'
        result = self.run_cli('--sym', str(self.sym), '--out', str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        data = json.loads(out.read_text())
        self.assertEqual(data['schema'], 1)
        self.assertEqual(len(data['source']['rom_sha256']), 64)
        self.assertEqual(len(data['source']['sym_sha256']), 64)
        self.assertEqual(data['source']['addresses'], {'overworld': '$0E:9459', 'dungeon_shared': '$0E:9659', 'group_offsets': '$10:8000', 'groups': '$10:8030'})
        self.assertEqual(sorted(data['dungeon_blocksets'], key=int), [str(n) for n in range(24)])
        self.assertEqual(data['overworld'][0x183], 0x83)
        self.assertEqual(t.load_types(out)['dungeon_blocksets']['4'], [0x11] * 0x40 + [0x21] * 0x40)

    def test_dungeon_shared_skips_overlay_chars(self):
        shared = t.dungeon_shared(synthetic_rom())
        self.assertEqual(len(shared), 0x200)
        self.assertEqual(shared[0x13F], 0xBF)
        self.assertIsNone(shared[0x140]); self.assertIsNone(shared[0x1BF])
        self.assertEqual(shared[0x1C0], 0xC0)  # table byte $140 -> char $1C0
        self.assertEqual(shared[0x1FF], 0xFF)

    def test_char_type_blockset_overlay(self):
        types, _ = t.extract(synthetic_rom(), t.parse_sym(SYM))
        self.assertEqual(t.char_type(types, 'overworld', 0x150), 0x50)
        self.assertEqual(t.char_type(types, 'dungeon', 0x13F, 5), 0xBF)
        self.assertEqual(t.char_type(types, 'dungeon', 0x140, 5), 0x12)  # slot 5, group 2
        self.assertEqual(t.char_type(types, 'dungeon', 0x1BF, 5), 0x22)  # slot 6, group 2
        self.assertEqual(t.char_type(types, 'dungeon', 0x1BF, 6), 0x20)
        self.assertEqual(t.char_type(types, 'dungeon', 0x1C0, 6), 0xC0)
        with self.assertRaises(ValueError):
            t.char_type(types, 'dungeon', 0x150)
        with self.assertRaises(ValueError):
            t.char_type(types, 'dungeon', 0x200, 1)
        with self.assertRaises(ValueError):
            t.char_type(types, 'sea', 0)

    def test_no_sym_mode(self):
        out = self.dir / 'nosym.json'
        result = self.run_cli('--out', str(out))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn('warning', result.stderr)
        data = t.load_types(out)
        self.assertEqual(data['dungeon_blocksets'], {})
        self.assertIsNone(data['source']['sym']); self.assertIsNone(data['source']['sym_sha256'])
        self.assertIsNone(data['source']['addresses']['group_offsets'])
        self.assertEqual(t.char_type(data, 'dungeon', 0x20), 0xA0)
        with self.assertRaises(ValueError):
            t.char_type(data, 'dungeon', 0x150, 4)

    def test_refuses_existing_out(self):
        out = self.dir / 'exists.json'
        out.write_text('keep')
        result = self.run_cli('--sym', str(self.sym), '--out', str(out))
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(out.read_text(), 'keep')

    def test_classes_load_without_overlap(self):
        data = json.loads(CLASSES.read_text())
        self.assertEqual(data['schema'], 1)
        seen = {}
        for name, ids in data['classes'].items():
            self.assertRegex(name, r'^[a-z_]+$')
            for value in ids:
                self.assertTrue(type(value) is int and 0 <= value <= 0xFF)
                self.assertNotIn(value, seen, '%s and %s both claim type $%02X' % (seen.get(value), name, value))
                seen[value] = name
        self.assertEqual(data['classes']['deep_water'], [8])
        self.assertEqual(data['classes']['spike'], [13, 68])


if __name__ == '__main__':
    unittest.main()
