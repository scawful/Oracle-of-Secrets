import importlib.util
import json
from pathlib import Path
import tempfile
import subprocess
import sys
import unittest
from PIL import Image

MODULE = Path(__file__).resolve().parents[2] / 'Scripts/Graphics/normalize_sprite.py'
spec = importlib.util.spec_from_file_location('normalize_sprite', MODULE)
n = importlib.util.module_from_spec(spec)
spec.loader.exec_module(n)

class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.spec = {'bpp': 3, 'cell_size': [2, 1], 'boxes': [{'id': 'moth', 'source_box': [0, 0, 2, 1], 'allowed_indices': [1, 2]}]}
        self.colors = [(0,0,0), (255,0,0), (0,255,0)]
        self.image = Image.new('RGBA', (2, 1)); self.image.putdata([(250,0,0,255), (0,255,0,191)])

    def test_indexed_transparency_and_counts(self):
        image, report = n.normalize(self.image, self.spec, self.colors)
        self.assertEqual(image.mode, 'P'); self.assertEqual(list(n.data(image)), [1, 0])
        self.assertEqual(image.info['transparency'], 0)
        self.assertEqual(sum(c['count'] for c in report['boxes'][0]['mapping']), 2)
        self.assertEqual(report['boxes'][0]['max_color_error'], 5)

    def test_nearest_resize_and_no_dither(self):
        self.spec['cell_size'] = [4,2]
        image, report = n.normalize(self.image, self.spec, self.colors)
        self.assertEqual(list(n.data(image)), [1,1,0,0]*2)
        self.assertTrue(report['boxes'][0]['size_changed'])

    def test_ordered_tie_and_error_reporting(self):
        self.image.putdata([(128,128,0,255)]*2)
        self.spec['boxes'][0]['allowed_indices'] = [2,1]
        image, report = n.normalize(self.image, self.spec, self.colors)
        self.assertEqual(list(n.data(image)), [2,2])
        self.assertEqual(len(report['boxes'][0]['no_close_match']), 1)

    def test_depth_never_masks(self):
        for bad in [8, -1, 0, True]:
            with self.subTest(index=bad), self.assertRaises(ValueError):
                self.spec['boxes'][0]['allowed_indices'] = [bad]
                n.normalize(self.image, self.spec, self.colors)

    def test_four_bpp_and_multiple_boxes(self):
        self.spec['bpp'] = 4; self.colors += [(0,0,0)]*12 + [(1,2,3)]
        self.spec['boxes'][0]['allowed_indices']=[15]
        self.spec['boxes'].append({'id':'wing','source_box':[0,0,1,1],'allowed_indices':[1]})
        self.spec['columns']=1
        image, report=n.normalize(self.image,self.spec,self.colors)
        self.assertEqual(image.size,(2,2)); self.assertEqual(image.getpixel((0,0)),15)

    def test_invalid_geometry_palette_and_threshold(self):
        for change in [{'cell_size':[0,1]}, {'alpha_threshold':0}, {'bpp':True}, {'close_match_error':float('nan')}, {'columns':99}]:
            with self.subTest(change=change), self.assertRaises(ValueError):n.normalize(self.image,{**self.spec,**change},self.colors)
        self.spec['boxes'][0]['source_box']=[1,0,2,1]
        with self.assertRaises(ValueError):n.normalize(self.image,self.spec,self.colors)

    def test_hex_and_bgr555_roundtrip(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); (root/'pal.json').write_text(json.dumps(['000000','F79C31']))
            (root/'pal.bin').write_bytes(bytes([0,0,0x7e,0x1a]))
            self.assertEqual(n.palette_colors(root/'pal.json',3), n.palette_colors(root/'pal.bin',3))
            (root/'bad.bin').write_bytes(bytes([0,0x80]))
            with self.assertRaises(ValueError):n.palette_colors(root/'bad.bin',3)
            (root/'pal.json').write_text(json.dumps(['000000']*9))
            with self.assertRaises(ValueError):n.palette_colors(root/'pal.json',3)

    def test_cli_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory); self.image.save(root/'in.png')
            (root/'pal.json').write_text(json.dumps(['000000','FF0000','00FF00']))
            (root/'spec.json').write_text(json.dumps({**self.spec,'palette':'pal.json'}))
            args=[sys.executable,str(MODULE),'--source',str(root/'in.png'),'--spec',str(root/'spec.json'),'--out',str(root/'out')]
            run=subprocess.run(args,capture_output=True,text=True); self.assertEqual(run.returncode,0,run.stderr)
            with Image.open(root/'out/indexed.png') as image:
                self.assertEqual(image.mode,'P'); self.assertEqual(list(n.data(image)),[1,0])
            before=(root/'out/indexed.png').read_bytes()
            self.assertNotEqual(subprocess.run(args,capture_output=True).returncode,0)
            self.assertEqual(before,(root/'out/indexed.png').read_bytes())

if __name__=='__main__':unittest.main()
