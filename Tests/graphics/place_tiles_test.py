import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from PIL import Image

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'Scripts/Graphics/place_tiles.py'
EXAMPLE = ROOT / 'Scripts/Graphics/examples/tile-placement'
TYPES = EXAMPLE / 'slot_types.fixture.json'
CLASSES = EXAMPLE / 'tile_type_classes.fixture.json'


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


p = load('place_tiles', SCRIPT)
codec = load('sheet_codec', ROOT / 'Scripts/Generate/sheet_codec.py')
PALETTE = [(0, 0, 0), (40, 90, 200), (200, 220, 255), (120, 170, 240), (60, 40, 20), (150, 110, 60), (110, 80, 40), (60, 150, 60)]
# Fixture overworld slot 7: 0-15 deep water, 16-23 shallow, 24-31 floor, 32-39 ledge, 40-43 bush, 44 pit, rest solid.
# Fixture overworld slot 6: 0-7 deep water, 8-31 floor, rest solid. Dungeon slot 5: blockset 4 pit 0-7, blockset 7 pit 0-3.


def tile(seed):
    """Asymmetric 8x8 pattern (no flip of it equals another seed's tile)."""
    rows = [[(x * 3 + y * 5 + seed) % 7 + 1 if x <= y else 0 for x in range(8)] for y in range(7)]
    return rows + [[(seed >> x & 1) + 1 for x in range(8)]]


def hflip(rows):
    return [r[::-1] for r in rows]


def write_png(path, cells, width=None):
    width = width or len(cells)
    height = -(-len(cells) // width)
    image = Image.new('P', (width * 8, height * 8), 0)
    image.putpalette([c for rgb in PALETTE for c in rgb])
    for n, rows in enumerate(cells):
        for y, row in enumerate(rows):
            for x, value in enumerate(row):
                image.putpixel(((n % width) * 8 + x, (n // width) * 8 + y), value)
    image.save(path, transparency=0)


class PlaceTilesTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)
        self.types = p.load_types(TYPES)
        self.classes = p.load_classes(CLASSES)
        self.spec = {'schema': 1, 'world': 'overworld', 'slots': [7], 'source': 'tiles.png', 'tiles': []}

    def tearDown(self):
        self.tmp.cleanup()

    def run_cli(self, spec, cells=None, out='out', base=None):
        if cells is not None:
            write_png(self.dir / 'tiles.png', cells)
        if base is not None:
            base.save(self.dir / 'base.png', transparency=0)
        (self.dir / 'spec.json').write_text(json.dumps(spec))
        result = subprocess.run([sys.executable, str(SCRIPT), '--spec', str(self.dir / 'spec.json'), '--types', str(TYPES),
                                 '--classes', str(CLASSES), '--out', str(self.dir / out)], capture_output=True, text=True)
        return result, self.dir / out

    def placed(self, spec, cells):
        source = cells_grid(cells)
        return {t['id']: t for t in p.place(spec, self.types, self.classes, source)['tiles']}

    def test_simple_placement(self):
        self.spec['tiles'] = [{'id': 'deep', 'cell': [0, 0], 'class': 'deep_water'},
                              {'id': 'shallow', 'cell': [1, 0], 'class': 'shallow_water'},
                              {'id': 'bush', 'cell': [2, 0], 'class': 'grass_bush_rock'}]
        result, out = self.run_cli(self.spec, [tile(1), tile(2), tile(3)])
        self.assertEqual(result.returncode, 0, result.stderr)
        tiles = {t['id']: t for t in json.loads((out / 'placement.json').read_text())['tiles']}
        self.assertEqual((tiles['deep']['index'], tiles['shallow']['index'], tiles['bush']['index']), (0, 16, 40))
        self.assertEqual(tiles['deep']['chars'], [0x1C0])
        self.assertEqual(tiles['shallow']['types'], [{'slot': 7, 'blockset': None, 'type': 0x09}])
        with Image.open(out / 'sheet.png') as sheet:
            self.assertEqual((sheet.mode, sheet.size, sheet.info.get('transparency')), ('P', (128, 32), 0))
            self.assertEqual(sheet.getpalette()[:24], [c for rgb in PALETTE for c in rgb])
            self.assertEqual(sheet.getpixel((16 * 8 % 128 + 0, 8 + 7)), tile(2)[7][0])
        with Image.open(out / 'preview.png') as image:
            self.assertEqual(image.size, (512, 128))
        report = json.loads((out / 'report.json').read_text())
        self.assertEqual(report['status'], 'placed')
        self.assertEqual(set(report['inputs']), {'spec', 'types', 'classes', 'source'})
        self.assertTrue(all(len(v['sha256']) == 64 for v in report['inputs'].values()))

    def test_multi_slot_intersection(self):
        self.spec['slots'] = [6, 7]
        self.spec['tiles'] = [{'id': 'w%d' % n, 'cell': [n, 0], 'class': 'deep_water'} for n in range(8)]
        tiles = self.placed(self.spec, [tile(n) for n in range(8)])
        self.assertEqual(sorted(t['index'] for t in tiles.values()), list(range(8)))
        self.assertEqual(tiles['w3']['chars'], [0x183, 0x1C3])
        self.spec['tiles'].append({'id': 'w8', 'cell': [8, 0], 'class': 'deep_water'})
        result = p.place(self.spec, self.types, self.classes, cells_grid([tile(n) for n in range(9)]))
        self.assertEqual(result['status'], 'unplaced')

    def test_dungeon_blockset_overlay(self):
        spec = {'schema': 1, 'world': 'dungeon', 'slots': [5], 'blocksets': [4], 'source': 'tiles.png',
                'tiles': [{'id': 'pit%d' % n, 'cell': [n, 0], 'class': 'pit'} for n in range(5)]}
        cells = [tile(n) for n in range(5)]
        tiles = self.placed(spec, cells)
        self.assertEqual(sorted(t['index'] for t in tiles.values()), [0, 1, 2, 3, 4])
        self.assertEqual(tiles['pit0']['types'], [{'slot': 5, 'blockset': 4, 'type': 0x20}])
        spec['blocksets'] = [4, 7]
        result = p.place(spec, self.types, self.classes, cells_grid(cells))
        self.assertEqual(result['status'], 'unplaced')
        pit = next(c for c in result['capacity'] if c['class'] == 'pit')
        self.assertEqual(pit['candidates'], [0, 1, 2, 3])
        self.assertEqual([(s['blockset'], len(s['free'])) for s in pit['slots']], [(4, 8), (7, 4)])
        spec['slots'] = [0]
        spec['tiles'] = [{'id': 'wall', 'cell': [0, 0], 'class': 'solid'}]
        with self.assertRaises(ValueError):
            p.place(spec, self.types, self.classes, cells_grid(cells))
        spec['blocksets'] = []
        self.assertEqual(self.placed(spec, cells)['wall']['index'], 0)
        spec['slots'] = [6]
        with self.assertRaisesRegex(ValueError, 'requires blocksets'):
            p.place(spec, self.types, self.classes, cells_grid(cells))
        spec['blocksets'] = [9]
        with self.assertRaisesRegex(ValueError, 'missing'):
            p.place(spec, self.types, self.classes, cells_grid(cells))

    def test_pin_honored(self):
        self.spec['tiles'] = [{'id': 'free', 'cell': [0, 0], 'class': 'deep_water'},
                              {'id': 'pinned', 'cell': [1, 0], 'class': 'deep_water', 'index': 0}]
        tiles = self.placed(self.spec, [tile(1), tile(2)])
        self.assertEqual((tiles['pinned']['index'], tiles['free']['index']), (0, 1))

    def test_matching_displaces_for_maximum(self):
        self.spec['free'] = [0, 16]
        self.spec['tiles'] = [{'id': 'wide', 'cell': [0, 0], 'types': [8, 9]}, {'id': 'deep', 'cell': [1, 0], 'class': 'deep_water'}]
        tiles = self.placed(self.spec, [tile(1), tile(2)])
        self.assertEqual((tiles['wide']['index'], tiles['deep']['index']), (16, 0))

    def test_pin_rejected(self):
        cells = [tile(1), tile(2)]
        for pin in (16, 63):
            self.spec['tiles'] = [{'id': 'pinned', 'cell': [0, 0], 'class': 'deep_water', 'index': pin}]
            with self.subTest(pin=pin), self.assertRaisesRegex(ValueError, 'not a candidate'):
                p.place(self.spec, self.types, self.classes, cells_grid(cells))
        self.spec['free'] = [1, 2]
        self.spec['tiles'][0]['index'] = 0
        with self.assertRaisesRegex(ValueError, 'not a candidate'):
            p.place(self.spec, self.types, self.classes, cells_grid(cells))
        self.spec['free'] = None
        self.spec['tiles'] = [{'id': 'a', 'cell': [0, 0], 'class': 'deep_water', 'index': 3},
                              {'id': 'b', 'cell': [1, 0], 'class': 'deep_water', 'index': 3}]
        with self.assertRaisesRegex(ValueError, 'pin index 3'):
            p.place(self.spec, self.types, self.classes, cells_grid(cells))
        result, out = self.run_cli({**self.spec, 'tiles': [{'id': 'a', 'cell': [0, 0], 'class': 'deep_water', 'index': 20}]}, cells)
        self.assertEqual(result.returncode, 1)
        self.assertIn('not a candidate', result.stderr)
        self.assertFalse(out.exists())

    def test_flip_dedupe_and_flip_bits(self):
        art = tile(4)
        vflip = art[::-1]
        self.spec['tiles'] = [{'id': 'a', 'cell': [0, 0], 'class': 'deep_water'},
                              {'id': 'h', 'cell': [1, 0], 'class': 'deep_water'},
                              {'id': 'v', 'cell': [2, 0], 'class': 'deep_water'},
                              {'id': 'hv', 'cell': [3, 0], 'types': [8, 9]},
                              {'id': 'same', 'cell': [4, 0], 'class': 'deep_water'},
                              {'id': 'other_type', 'cell': [5, 0], 'class': 'shallow_water'}]
        cells = [art, hflip(art), vflip, hflip(vflip), art, art]
        result = p.place(self.spec, self.types, self.classes, cells_grid(cells))
        tiles = {t['id']: t for t in result['tiles']}
        self.assertEqual(result['unique_tiles'], 2)
        self.assertEqual({tiles[k]['index'] for k in ('a', 'h', 'v', 'hv', 'same')}, {0})
        self.assertEqual(tiles['other_type']['index'], 16)
        self.assertEqual([(tiles[k]['h_flip'], tiles[k]['v_flip']) for k in ('a', 'h', 'v', 'hv', 'same')],
                         [(False, False), (True, False), (False, True), (True, True), (False, False)])
        self.spec['dedupe_flips'] = False
        result = p.place(self.spec, self.types, self.classes, cells_grid(cells))
        self.assertEqual(result['unique_tiles'], 5)
        self.assertFalse(any(t['h_flip'] or t['v_flip'] for t in result['tiles']))

    def test_capacity_failure_exit_2(self):
        self.spec['tiles'] = [{'id': 'pit%d' % n, 'cell': [n, 0], 'class': 'pit'} for n in range(2)]
        result, out = self.run_cli(self.spec, [tile(1), tile(2)])
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertEqual(sorted(x.name for x in out.iterdir()), ['report.json'])
        report = json.loads((out / 'report.json').read_text())
        self.assertEqual(report['status'], 'unplaced')
        self.assertEqual(report['unplaced'], [{'ids': ['pit1'], 'classes': ['pit'], 'candidates': [44]}])
        pit = report['capacity'][0]
        self.assertEqual((pit['class'], pit['demand'], pit['slots'][0]['indices'], pit['slots'][0]['free']), ('pit', 2, [44], [44]))

    def test_base_sheet_free_list_preserves_pixels(self):
        base = Image.new('P', (128, 32), 0)
        base.putpalette([c for rgb in PALETTE for c in rgb])
        base.putdata([(x // 8 + y) % 8 for y in range(32) for x in range(128)])
        for x in range(8):
            for y in range(8):
                base.putpixel((8 * 3 + x, y), 0)
        before = list(base.tobytes())
        self.spec['base_sheet'] = 'base.png'
        self.spec['tiles'] = [{'id': 'deep', 'cell': [0, 0], 'class': 'deep_water'}]
        tiles = None
        result, out = self.run_cli(self.spec, [tile(5)], base=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        tiles = json.loads((out / 'placement.json').read_text())['tiles']
        self.assertEqual(tiles[0]['index'], 3)
        self.spec['free'] = [5, 9]
        result, out = self.run_cli(self.spec, None, out='out2', base=base)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads((out / 'placement.json').read_text())['tiles'][0]['index'], 5)
        with Image.open(out / 'sheet.png') as sheet:
            after = list(sheet.tobytes())
        changed = {(i % 128 // 8) + (i // 128 // 8) * 16 for i in range(len(after)) if after[i] != before[i]}
        self.assertEqual(changed, {5})
        self.assertEqual([after[y * 128 + 40:y * 128 + 48] for y in range(8)], tile(5))

    def test_sheet_bin_round_trip(self):
        self.spec['tiles'] = [{'id': 'deep', 'cell': [0, 0], 'class': 'deep_water'}, {'id': 'ledge', 'cell': [1, 0], 'class': 'ledge'}]
        result, out = self.run_cli(self.spec, [tile(6), tile(7)])
        self.assertEqual(result.returncode, 0, result.stderr)
        raw = (out / 'sheet.bin').read_bytes()
        self.assertEqual(len(raw), 0x600)
        with Image.open(out / 'sheet.png') as sheet:
            pixels = list(sheet.tobytes())
        grid = codec.sheet_to_grid(raw)
        self.assertEqual([v for row in grid for v in row], pixels)
        self.assertEqual(codec.grid_to_sheet(grid), raw)
        (self.dir / 'base.bin').write_bytes(raw)
        spec = {**self.spec, 'base_sheet': 'base.bin', 'tiles': []}
        result, audit = self.run_cli(spec, None, out='audit')
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(sorted(x.name for x in audit.iterdir()), ['preview.png', 'report.json'])
        self.assertEqual(json.loads((audit / 'report.json').read_text())['status'], 'audit')

    def test_deterministic_outputs(self):
        self.spec['tiles'] = [{'id': 'w%d' % n, 'cell': [n, 0], 'class': 'deep_water'} for n in range(3)] + \
                             [{'id': 'h', 'cell': [3, 0], 'class': 'deep_water'}, {'id': 'b', 'cell': [4, 0], 'class': 'grass_bush_rock', 'index': 42}]
        cells = [tile(1), tile(2), tile(3), hflip(tile(2)), tile(8)]
        first, a = self.run_cli(self.spec, cells, out='a')
        second, b = self.run_cli(self.spec, None, out='b')
        self.assertEqual((first.returncode, second.returncode), (0, 0))
        names = sorted(x.name for x in a.iterdir())
        self.assertEqual(names, ['placement.json', 'preview.png', 'report.json', 'sheet.bin', 'sheet.png'])
        for name in names:
            self.assertEqual((a / name).read_bytes(), (b / name).read_bytes(), name)

    def test_refuse_existing_out_dir(self):
        self.spec['tiles'] = [{'id': 'deep', 'cell': [0, 0], 'class': 'deep_water'}]
        (self.dir / 'out').mkdir()
        (self.dir / 'out' / 'keep.txt').write_text('keep')
        result, out = self.run_cli(self.spec, [tile(1)])
        self.assertEqual(result.returncode, 1)
        self.assertIn('already exists', result.stderr)
        self.assertEqual(sorted(x.name for x in out.iterdir()), ['keep.txt'])

    def test_validation_errors(self):
        cells = [tile(1)]
        good = {'id': 'deep', 'cell': [0, 0], 'class': 'deep_water'}
        bad_specs = [{'tiles': [{**good, 'cell': [1, 0]}]}, {'tiles': [{**good, 'class': 'lava'}]},
                     {'tiles': [good, dict(good)]}, {'tiles': [{**good, 'types': [8]}]}, {'tiles': [{**good, 'pin': 0}]},
                     {'world': 'sky'}, {'slots': [8]}, {'slots': [7, 7]}, {'blocksets': [4]}, {'free': [64]},
                     {'dedupe_flips': 1}, {'schema': 2}, {'extra': True}]
        for change in bad_specs:
            with self.subTest(change=change), self.assertRaises(ValueError):
                p.place({**self.spec, 'tiles': [good], **change}, self.types, self.classes, cells_grid(cells))
        write_png(self.dir / 'eight.png', [[[8] * 8] * 8])
        with self.assertRaisesRegex(ValueError, '0-7'):
            p.read_source(self.dir / 'eight.png')
        Image.new('P', (12, 8)).save(self.dir / 'odd.png')
        with self.assertRaisesRegex(ValueError, 'multiples of 8'):
            p.read_source(self.dir / 'odd.png')
        Image.new('P', (128, 16)).save(self.dir / 'short.png')
        (self.dir / 'short.bin').write_bytes(bytes(0x5FF))
        for name in ('short.png', 'short.bin'):
            with self.subTest(base=name), self.assertRaises(ValueError):
                p.read_base(self.dir / name, codec)
        broken = copy.deepcopy(self.types)
        broken['overworld'] = broken['overworld'][:511]
        (self.dir / 'broken.json').write_text(json.dumps(broken))
        with self.assertRaisesRegex(ValueError, 'overworld'):
            p.load_types(self.dir / 'broken.json')
        broken = copy.deepcopy(self.types)
        broken['dungeon_shared'][0x150] = 0
        (self.dir / 'broken.json').write_text(json.dumps(broken))
        with self.assertRaisesRegex(ValueError, 'null'):
            p.load_types(self.dir / 'broken.json')

    @unittest.skipUnless((ROOT / 'Scripts/Graphics/tile_types.py').exists(), 'tile_types.py not present')
    def test_lookup_matches_tile_types_char_type(self):
        t = load('tile_types', ROOT / 'Scripts/Graphics/tile_types.py')
        for world, slots, blocksets in (('overworld', list(range(8)), []), ('dungeon', list(range(8)), [4, 7])):
            for slot, blockset, types in p.contexts(self.types, world, slots, blocksets):
                self.assertEqual(types, [t.char_type(self.types, world, slot * 0x40 + i, blockset) for i in range(64)])

    def test_example_runs(self):
        out = self.dir / 'example'
        result = subprocess.run([sys.executable, str(SCRIPT), '--spec', str(EXAMPLE / 'spec.json'), '--types', str(TYPES),
                                 '--classes', str(CLASSES), '--out', str(out)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['unique_tiles'], 5)


def cells_grid(cells):
    grid = [[0] * (len(cells) * 8) for _ in range(8)]
    for n, rows in enumerate(cells):
        for y, row in enumerate(rows):
            grid[y][n * 8:n * 8 + 8] = row
    return grid


if __name__ == '__main__':
    unittest.main()
