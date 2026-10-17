from pathlib import Path
import sys
import tempfile
import unittest
sys.path[:0] = [str(Path(__file__).resolve().parents[1])]
import pixels_to_4bpp as gen

ROOT = Path(__file__).resolve().parents[3]


def do3to4low(src):
    """Do3To4Low16Bit ($00:DFB8) for one 24-byte 3bpp tile: plane 3 = 0."""
    out = bytearray(32)
    for r in range(8):
        out[2 * r], out[2 * r + 1], out[16 + 2 * r] = src[2 * r], src[2 * r + 1], src[16 + r]
    return bytes(out)


def to3bpp(px):
    out = bytearray(24)
    for r in range(8):
        for c in range(8):
            v = px[r][c]
            if v & 1: out[2 * r] |= 0x80 >> c
            if v & 2: out[2 * r + 1] |= 0x80 >> c
            if v & 4: out[16 + r] |= 0x80 >> c
    return bytes(out)


class Pixels4bppTests(unittest.TestCase):
    def test_matches_vanilla_low_conversion(self):
        px = [[(r * 3 + c * 5) % 8 for c in range(8)] for r in range(8)]
        self.assertEqual(gen.tile_4bpp(px, 0, 0), do3to4low(to3bpp(px)))

    def test_16x16_runs(self):
        with tempfile.NamedTemporaryFile('w', suffix='.txt', delete=False) as f:
            f.write('cell CE 16x16\n' + ('7' * 16 + '\n') * 16 + 'cell F1 8x8\n' + ('1' * 8 + '\n') * 8)
        try:
            data, runs = gen.build(gen.parse(f.name))
        finally:
            Path(f.name).unlink()
        self.assertEqual(runs, [(0x00, 0xCE, 64), (0x40, 0xDE, 64), (0x80, 0xF1, 32)])
        self.assertEqual(len(data), 0xA0)

    def test_farore_reach_bin_is_current(self):
        txt = ROOT / 'Sprites/NPCs/gfx/farore_reach.txt'
        data, runs = gen.build(gen.parse(str(txt)))
        self.assertEqual(data, (ROOT / 'Sprites/NPCs/gfx/farore_reach.bin').read_bytes())
        # DreamWisdom_LoadReachGfx copies exactly these runs
        self.assertEqual(runs, [(0x00, 0xCE, 64), (0x40, 0xDE, 64), (0x80, 0xF1, 32)])


if __name__ == '__main__':
    unittest.main()
