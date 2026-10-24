"""Check committed intro assets without requiring the Pillow compiler dependency."""

import hashlib
import json
from pathlib import Path
import struct
import unittest


ROOT = Path(__file__).resolve().parents[3]
ASSETS = ROOT / 'Core/Cutscene/Assets/link_hyrule_intro'
NAME = 'link_hyrule_intro'


def digest(data):
    return hashlib.sha256(data).hexdigest()


def decode_visible(tiles, tilemap):
    """Read the actual SNES plane pairs into the visible 256x224 index frame."""
    frame = bytearray(256 * 224)
    for tile_y in range(28):
        for tile_x in range(32):
            tile_start = tilemap[tile_y * 32 + tile_x] * 32
            tile = tiles[tile_start:tile_start + 32]
            for y in range(8):
                low, high = tile[2 * y:2 * y + 2], tile[16 + 2 * y:18 + 2 * y]
                for x in range(8):
                    mask = 0x80 >> x
                    value = (bool(low[0] & mask) + 2 * bool(low[1] & mask)
                             + 4 * bool(high[0] & mask) + 8 * bool(high[1] & mask))
                    frame[(tile_y * 8 + y) * 256 + tile_x * 8 + x] = value
    return bytes(frame)


class IntroArtAssetsTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.manifest = json.loads((ASSETS / 'manifest.json').read_text())
        cls.tiles = (ASSETS / (NAME + '.bin')).read_bytes()
        cls.map_data = (ASSETS / (NAME + '.map')).read_bytes()
        cls.palette_data = (ASSETS / (NAME + '.pal')).read_bytes()

    def test_source_compiler_and_native_file_hashes_match_manifest(self):
        manifest = self.manifest
        self.assertEqual(manifest['schema_version'], 1)
        self.assertEqual(manifest['compiler'], 'Scripts/Generate/compile_intro_art.py')
        self.assertEqual(digest((ROOT / manifest['compiler']).read_bytes()),
                         manifest['compiler_sha256'])
        self.assertEqual(set(manifest['files']),
                         {'approved_source.png', NAME + '.bin', NAME + '.pal', NAME + '.map'})
        for name, receipt in manifest['files'].items():
            with self.subTest(file=name):
                data = (ASSETS / name).read_bytes()
                self.assertEqual(len(data), receipt['bytes'])
                self.assertEqual(digest(data), receipt['sha256'])
        source = (ASSETS / 'approved_source.png').read_bytes()
        self.assertEqual(source[:16], b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR')
        self.assertEqual(struct.unpack('>II', source[16:24]),
                         (manifest['source']['width'], manifest['source']['height']))
        self.assertEqual(manifest['source']['file'], 'approved_source.png')
        self.assertEqual(digest(source), manifest['source']['sha256'])

    def test_blank_tile_and_graphics_fit_reserved_vram(self):
        self.assertGreater(len(self.tiles), 32)
        self.assertEqual(len(self.tiles) % 32, 0)
        self.assertLessEqual(len(self.tiles), 0x4000)
        self.assertEqual(self.tiles[:32], bytes(32))
        self.assertEqual(len(self.tiles) // 32,
                         self.manifest['counts']['tiles_including_blank'])
        self.assertEqual(self.manifest['layout']['tile_vram_word_address'], 0)
        self.assertEqual(self.manifest['layout']['max_tiles'], 512)
        self.assertEqual(self.manifest['layout']['blank_tile_index'], 0)

    def test_map_uses_local_indices_and_blank_panel_borders(self):
        self.assertEqual(len(self.map_data), 32 * 32 * 2)
        tilemap = struct.unpack('<1024H', self.map_data)
        self.assertLess(max(tilemap), len(self.tiles) // 32)
        self.assertTrue(all(word & 0xFC00 == 0 for word in tilemap),
                        'palette, priority and flip bits must be clear')
        layout = self.manifest['layout']
        self.assertEqual(layout['tilemap_tiles'], [32, 32])
        self.assertEqual(layout['panel_pixels'], [240, 136])
        self.assertEqual(layout['panel_tile_origin'], [1, 5])
        self.assertEqual(layout['screen_pixels'], [256, 224])
        self.assertEqual(layout['bg1_map_vram_word_address'], 0x6000)
        self.assertEqual(layout['palette_number'], 0)
        self.assertEqual(self.manifest['counts']['panel_tile_cells'], 30 * 17)
        for y in range(32):
            for x in range(32):
                with self.subTest(cell=(x, y)):
                    word = tilemap[y * 32 + x]
                    if 1 <= x < 31 and 5 <= y < 22:
                        self.assertNotEqual(word, 0)
                    else:
                        self.assertEqual(word, 0)

    def test_palette_has_fifteen_opaque_rgb555_colors(self):
        self.assertEqual(len(self.palette_data), 32)
        palette = struct.unpack('<16H', self.palette_data)
        self.assertEqual(palette[0], 0)
        self.assertTrue(all(word < 0x8000 for word in palette))
        self.assertEqual(len(set(palette[1:])), 15)
        self.assertEqual(self.manifest['counts']['palette_entries'], 16)
        self.assertEqual(self.manifest['counts']['opaque_colors'], 15)
        self.assertEqual(self.manifest['conversion']['transparent_index'], 0)
        self.assertEqual(self.manifest['conversion']['opaque_indices'], [1, 15])

    def test_actual_native_pixels_match_manifest_without_transparency_holes(self):
        self.assertEqual(len(self.map_data), 2048)
        self.assertEqual(len(self.tiles) % 32, 0)
        tilemap = struct.unpack('<1024H', self.map_data)
        self.assertLess(max(tilemap), len(self.tiles) // 32)
        frame = decode_visible(self.tiles, tilemap)
        self.assertEqual(digest(frame),
                         self.manifest['selfcheck']['decoded_visible_indices_sha256'])
        for y in range(224):
            row = frame[y * 256:(y + 1) * 256]
            if 40 <= y < 176:
                self.assertTrue(all(1 <= pixel <= 15 for pixel in row[8:248]))
                self.assertEqual(row[:8] + row[248:], bytes(16))
            else:
                self.assertEqual(row, bytes(256))
        self.assertEqual(len(self.palette_data), 32)
        palette = struct.unpack('<16H', self.palette_data)
        rgb = bytearray()
        for pixel in frame:
            word = palette[pixel]
            for shift in (0, 5, 10):
                channel = (word >> shift) & 31
                rgb.append((channel << 3) | (channel >> 2))
        self.assertEqual(digest(rgb), self.manifest['selfcheck']['preview_rgb_sha256'])


if __name__ == '__main__':
    unittest.main()
