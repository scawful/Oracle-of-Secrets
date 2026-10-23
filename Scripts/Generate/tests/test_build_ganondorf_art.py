"""Exercise fixed/automatic packing through the real indexed-source exporter."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image


SCRIPT = Path(__file__).resolve().parents[1] / 'build_ganondorf_art.py'
SPEC = importlib.util.spec_from_file_location('ganondorf_art', SCRIPT)
art = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(art)


class PackingLayoutTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.project = self.root / 'project.json'
        palette = [(index * 17,) * 3 for index in range(16)]
        sheet = art.indexed((256, 144), palette)
        frames = []
        for index, name in enumerate(art.SOURCE_IDS):
            effect = name.startswith(('ball_', 'bat_'))
            column, row = index % 8, index // 8
            # Aligning body row3 makes its one pixel share the effect's cell.
            sheet.putpixel((column * 32 + 3, row * 48 + (0 if effect else 3)), 1)
            frames.append(dict(id=name, cell=[column, row],
                               size=[16, 16] if effect else [32, 40]))
        sheet.save(self.root / 'canonical.png', transparency=0)
        self.metadata = dict(schema=1, image='canonical.png', frame_grid=[32, 48],
                             columns=8, palette=['#%02x%02x%02x' % rgb for rgb in palette],
                             frames=frames)
        self.root_patch = patch.object(art, 'ROOT', self.root)
        self.root_patch.start()
        self.addCleanup(self.root_patch.stop)

    def write_project(self):
        self.project.write_text(json.dumps(self.metadata))

    def test_absent_setting_keeps_minimum_layout(self):
        self.write_project()
        result = art.build(self.project)
        self.assertEqual(result['requested_layout'], 'auto')
        self.assertEqual(result['selected_layout'], 'first_opaque_row')
        self.assertEqual(result['layouts'], {'fixed': 2, 'first_opaque_row': 1})

    def test_source_setting_applies_to_generation_and_check(self):
        self.metadata['runtime'] = {'packing_layout': 'fixed'}
        self.write_project()
        result = art.build(self.project)
        self.assertEqual(result['selected_layout'], 'fixed')
        self.assertEqual(result['unique_16x16_cells'], 2)
        self.assertEqual(art.build(self.project, check=True)['selected_layout'], 'fixed')
        binary = self.root / 'Sprites/Bosses/ganondorf.bin'
        previous = binary.read_bytes()
        with self.assertRaisesRegex(ValueError, 'stale/missing generated files'):
            art.build(self.project, check=True, layout='auto')
        self.assertEqual(binary.read_bytes(), previous)

    def test_override_and_invalid_metadata(self):
        self.metadata['runtime'] = {'packing_layout': 'fixed'}
        self.write_project()
        self.assertEqual(art.build(self.project, layout='auto')['selected_layout'],
                         'first_opaque_row')
        self.metadata['runtime']['packing_layout'] = 'unknown'
        self.write_project()
        with self.assertRaisesRegex(ValueError, 'unknown packing layout'):
            art.build(self.project)


if __name__ == '__main__':
    unittest.main()
