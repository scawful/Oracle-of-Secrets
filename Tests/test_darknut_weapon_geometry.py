"""Verify every Darknut frame uses its displayed weapon for guard contact."""
from pathlib import Path
import re
import unittest

SOURCE = Path(__file__).resolve().parents[1] / 'Sprites/Enemies/darknut.asm'


def table(source, name):
    body = source.split(name + ':', 1)[1]
    values = []
    for line in body.splitlines():
        if not line.strip():
            if values:
                break
            continue
        match = re.match(r'\s*d[wb]\s+(.+)', line)
        if not match:
            break
        for token in match[1].split(','):
            token = token.strip()
            values.append(int(token[1:], 16) if token.startswith('$') else int(token))
    return values


class DarknutWeaponGeometry(unittest.TestCase):
    def test_all_eight_frames_use_displayed_weapon_offsets(self):
        s = SOURCE.read_text()
        starts = table(s, 'DarknutDrawStartIndex')
        counts = table(s, 'DarknutDrawTileCounts')
        xs, ys = table(s, 'DarknutDrawXOffsets'), table(s, 'DarknutDrawYOffsets')
        self.assertEqual(len(starts), 8)
        self.assertEqual(len(counts), 8)
        self.assertEqual(len(xs), 20)
        self.assertEqual(len(ys), 20)
        positions = [(xs[a + b], ys[a + b]) for a, b in zip(starts, counts)]
        self.assertEqual(positions, [(0, -12)] * 2 + [(0, 20)] * 2
                         + [(-12, 8)] * 2 + [(12, 8)] * 2)
        self.assertTrue(all(-128 < x < 128 and -128 < y < 128 for x, y in positions))


if __name__ == '__main__':
    unittest.main()
