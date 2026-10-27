"""Synthetic source tests for BG128 emission; no ROM or allocation grant."""
import hashlib
from pathlib import Path
import struct
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
from lyra_project_bg_palette import emit_bg128_data, plan_bg128


class BG128Test(unittest.TestCase):
    def plan(self, rows, **kw):
        args = dict(data_snes=0x5C8000, capacity=0x1000, preimage=bytes(0x1000))
        args.update(kw)
        return plan_bg128(rows, **args)

    def row(self, area, words=None):
        return SimpleNamespace(map_id=area, properties={} if words is None else
                               dict(background_palette=words))

    def test_exact_all_words_dedup_and_no_native_binding(self):
        words = list(range(128))
        p = self.plan([self.row(0xBF, words), self.row(0xA0, words), self.row(1)])
        self.assertEqual(len(p['payload']), 384 + 256)
        offsets = struct.unpack('<192H', p['payload'][:384])
        self.assertEqual((offsets[0xBF], offsets[0xA0], offsets[1]), (384, 384, 0))
        self.assertEqual(p['payload'][384:], struct.pack('<128H', *words))
        self.assertFalse(p['publication_authorized'])
        self.assertEqual(p['records'][0]['sha256'],
                         hashlib.sha256(struct.pack('<128H', *words)).hexdigest())
        self.assertIn('Oracle_ProjectBGPalette_Data:', emit_bg128_data(p))

    def test_current_full32_domain_and_original160_directory_fallback(self):
        rows = [self.row(area, [area] * 128) for area in (0xA0, 0xA1, 0xBF)]
        p = self.plan(rows)
        directory = struct.unpack('<192H', p['payload'][:384])
        self.assertEqual(directory[:160], (0,) * 160)
        for area in (0xA0, 0xA1, 0xBF):
            offset = directory[area]
            self.assertGreaterEqual(offset, 384)
            self.assertEqual(struct.unpack('<128H', p['payload'][offset:offset + 256]),
                             (area,) * 128)
        for area in (-1, 0xC0, True):
            with self.subTest(area=area):
                with self.assertRaises(ValueError):
                    self.plan([self.row(area, [0] * 128)])

    def test_current_runtime_uses_explicit_origins_and_defaults_stay_off(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'Overworld/project_bg_palette.asm').read_text()
        self.assertIn('org !PROJECT_BG128_CODE_BASE', source)
        self.assertNotIn('$F8C000', source)
        self.assertNotIn('$28C000', source)
        self.assertNotIn('$5B8000', source)
        main = (root / 'Oracle_main.asm').read_text()
        self.assertIn('!PROJECT_BG128_ENABLED = 0', main)
        self.assertIn('!PROJECT_BG128_RESTORE_BOUND = 0', main)
        self.assertLess(main.index('!PROJECT_BG128_ENABLED = 0'), main.index('namespace Oracle'))

    def test_invalid_shape_bool_range_and_duplicate(self):
        for words in ([0] * 127, [True] * 128, [-1] * 128, [0x8000] * 128):
            with self.subTest(words=words[:1]):
                with self.assertRaises(ValueError):
                    self.plan([self.row(0xBF, words)])
        with self.assertRaises(ValueError):
            self.plan([self.row(0xBF), self.row(0xBF)])

    def test_bank_bounds_capacity_and_preimage(self):
        for kw in (dict(data_snes=0x5C7000), dict(data_snes=0x7E8000),
                   dict(data_snes=0x5CFF00), dict(preimage=b''),
                   dict(capacity=384, preimage=bytes(384))):
            with self.subTest(kw=kw):
                with self.assertRaises(ValueError):
                    self.plan([self.row(0xBF, [0] * 128)], **kw)

    def test_runtime_bg_only_and_existing_tint_abi_source(self):
        root = Path(__file__).resolve().parents[1]
        source = (root / 'Overworld/project_bg_palette.asm').read_text()
        self.assertIn('CMP.w #$0100', source)
        self.assertIn('JSL LoadDayNightPaletteEffect', source)
        self.assertNotIn('$7EC400', source)
        self.assertNotIn('$2122', source)
        self.assertIn('!PROJECT_BG128_CODE_END', source)


if __name__ == '__main__':
    unittest.main()
