"""Tests for Scripts/Generate/compile_storybook_art.py and committed assets."""
import importlib.util
from pathlib import Path
import struct
import tempfile
import unittest

from PIL import Image

ROOT = Path(__file__).resolve().parents[3]
SCRIPT = Path(__file__).resolve().parents[1] / 'compile_storybook_art.py'
SPEC = importlib.util.spec_from_file_location('compile_storybook_art', SCRIPT)
gen = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(gen)


class CompileStorybookArtTests(unittest.TestCase):
    def test_4bpp_tile_roundtrip_and_bit_ordering(self):
        # Row 0 = palette indices 0..7, Row 1 = 8..15; bit 7 = leftmost pixel.
        pixels = [c for c in range(16)] + [((r * 5 + c) & 15) for r in range(6) for c in range(8)]
        encoded = gen.encode_tile_4bpp(pixels)
        self.assertEqual(len(encoded), 32)
        self.assertEqual(gen.decode_tile_4bpp(encoded), pixels)
        # Pixel 1 is index 1 (plane 0 bit 6 = $40), pixel 3 is index 3 (plane 0/1 bit 4 = $10).
        self.assertEqual(encoded[0] & 0x55, 0x55)  # odd indices 1,3,5,7 -> bits 6,4,2,0
        self.assertEqual(encoded[16], 0x0F)         # plane 2 for pixels 4..7
        self.assertEqual(encoded[17], 0x00)         # plane 3 = 0 for row 0
        self.assertEqual(encoded[19], 0xFF)         # row 1 indices 8..15 -> plane 3 = $FF

    def test_synthetic_build_dedup_palette_and_check(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            src = tmp_path / 'src'
            out = tmp_path / 'out'
            src.mkdir()
            # Paint 4 synthetic 168x48 panels using exact flip-symmetric 8x8 tiles and <= 15 colors.
            for idx in range(gen.PANEL_COUNT):
                im = Image.new('RGB', (gen.PANEL_W, gen.PANEL_H), (8, 16, 24))
                px = im.load()
                for ty in range(gen.TILES_Y):
                    for tx in range(gen.TILES_X):
                        # Mirror horizontally on odd tx to verify H-flip deduplication.
                        for y in range(8):
                            for x in range(8):
                                sx = (7 - x) if (tx & 1) else x
                                sy = (7 - y) if (ty & 1) else y
                                c = (sx // 2) + (sy // 2) * 3  # 0..11 (< 15 colors), asymmetric in H and V
                                col = (8 + (c & 3) * 64, 16 + ((c >> 2) & 3) * 64, 40 + idx * 32)
                                px[tx * 8 + x, ty * 8 + y] = col
                im.save(src / f'panel_{idx}.png')

            panels = gen.build(src_dir=src, out_dir=out, check=False)
            self.assertEqual(len(panels), gen.PANEL_COUNT)
            for p in panels:
                # Tile 0 reserved blank + 1 canonical tile = 2 tiles for mirrored tile pattern.
                self.assertEqual(p['tiles'], 2)
                self.assertLessEqual(p['colors'], 15)
                de_map, _ = gen.lz2.decompress(p['map_lz2'], max_output=gen.TILEMAP_BYTES + 16)
                words = struct.unpack('<1024H', de_map)
                # Border (row 0, col 0) uses blank Tile 0 ($1800); active cells use Tile 1 + flip bits.
                self.assertEqual(words[0], gen.PALETTE_ATTR)
                self.assertEqual(words[gen.MAP_ORIGIN_Y * 32 + gen.MAP_ORIGIN_X], gen.PALETTE_ATTR | 1)
                self.assertEqual(words[gen.MAP_ORIGIN_Y * 32 + gen.MAP_ORIGIN_X + 1], gen.PALETTE_ATTR | 0x4000 | 1)

            gen.build(src_dir=src, out_dir=out, check=True)
            (out / 'panel_0_pal.bin').write_bytes(b'\x00' * 32)
            with self.assertRaisesRegex(ValueError, 'stale/missing generated storybook files'):
                gen.build(src_dir=src, out_dir=out, check=True)

    def test_committed_storybook_assets_are_current_and_fit_bank56(self):
        panels = gen.build(check=True)
        total_bytes = sum(
            len(p['chr_lz2']) + len(p['map_lz2']) + len(p['pal_bytes']) for p in panels
        )
        # Compact 168x48 assets leave ample headroom in 32 KB bank $56.
        self.assertLess(total_bytes, 16000)
        self.assertEqual((gen.PANEL_W, gen.PANEL_H), (168, 48))
        self.assertEqual(gen.MAX_TILES, 127)
        for p in panels:
            self.assertLessEqual(p['tiles'], gen.MAX_TILES)
            self.assertLessEqual(p['chr_raw_len'], 127 * 32)
            self.assertEqual(len(p['pal_bytes']), 32)
            self.assertEqual(struct.unpack_from('<H', p['pal_bytes'], 0)[0], 0)


if __name__ == '__main__':
    unittest.main()
