"""The attract data allocation must not exempt neighboring or foreign writes."""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_zscream_overlap as checker


class AttractCastAllocationTest(unittest.TestCase):
    def test_only_exact_owner_and_bounds_are_allowed(self):
        owner = 'Dungeons/attract_royal_graphics.asm'
        entries = [(0x1E4000, owner), (0x1E5FFF, owner),
                   (0x1E3FFF, owner), (0x1E6000, owner),
                   (0x1E4000, 'Dungeons/foreign.asm')]
        mappings = [dict(pc=pc, snes=0x3C8000+(pc-0x1E0000), source=source, line=i+1)
                    for i, (pc, source) in enumerate(entries)]
        reserved = [dict(start=0x1E0000, end=0x1E7FFF, name='Custom ASM Patches')]
        with patch.object(checker, 'parse_symbols', return_value=({}, mappings)):
            failures = checker.check_overlaps(Path('unused.sym'), reserved)
        self.assertEqual([f['pc'] for f in failures],
                         ['0x1E3FFF', '0x1E6000', '0x1E4000'])


if __name__ == '__main__':
    unittest.main()
