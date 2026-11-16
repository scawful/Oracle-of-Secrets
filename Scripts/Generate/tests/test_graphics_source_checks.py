"""Read-only capability decisions from fixed, disposable ASM include graphs."""
from pathlib import Path
import sys
import tempfile
import unittest

GEN = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(GEN))
import graphics_source_checks as checks
from asm_source import SourceGraphError


class GraphicsSourceChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.write('Oracle_main.asm', '; no graphics consumers\n')

    def write(self, relative, text):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def consumer(self, name, condition=None):
        relative = checks.CONSUMERS[name]
        self.write(relative, '; disposable generated include\n')
        source = f'incsrc "{relative.as_posix()}"\n'
        if condition is not None:
            source = f'if {condition}\n{source}endif\n'
        self.write('Oracle_main.asm', source)

    def test_absence_comes_from_graph_not_artifact_presence(self):
        for name, relative in checks.CONSUMERS.items():
            with self.subTest(name=name):
                self.assertFalse(checks.applicable(self.root, name))
                self.write(relative, '; unused artifact is not a consumer\n')
                self.assertFalse(checks.applicable(self.root, name))

    def test_each_transitive_consumer_remains_required(self):
        for name in checks.CONSUMERS:
            with self.subTest(name=name):
                self.consumer(name)
                source = (self.root/'Oracle_main.asm').read_text()
                self.write('nested/entry.asm', source)
                self.write('Oracle_main.asm', 'incsrc "nested/entry.asm"\n')
                self.assertTrue(checks.applicable(self.root, name))

    def test_false_flag_is_absent_but_unknown_branch_is_required(self):
        for condition in ('!ENABLE_SOURCE_SPRITE_SHEETS == 1', '!UNRESOLVED_GRAPHICS == 1'):
            self.write('Config/feature_flags.asm', '!ENABLE_SOURCE_SPRITE_SHEETS = 0\n')
            self.consumer('source_sprite_sheets', condition)
            self.assertEqual(checks.applicable(self.root, 'source_sprite_sheets'),
                             condition.startswith('!UNRESOLVED'))

    def test_snowpeak_requires_both_assembled_features(self):
        for source, expanded in ((0, 0), (1, 0), (0, 1), (1, 1)):
            with self.subTest(source=source, expanded=expanded):
                self.write('Config/feature_flags.asm',
                           f'!ENABLE_SOURCE_SPRITE_SHEETS = {source}\n'
                           f'!ENABLE_EXPANDED_GRAPHICS_TABLE = {expanded}\n')
                self.consumer('snowpeak_sheet',
                              '!ENABLE_SOURCE_SPRITE_SHEETS == 1 && !ENABLE_EXPANDED_GRAPHICS_TABLE == 1')
                self.assertEqual(checks.applicable(self.root, 'snowpeak_sheet'), bool(source and expanded))

    def test_joint_palette_directory_or_reader_stays_required(self):
        for relative in (checks.CONSUMERS['joint_palette_source'], checks.JOINT_PALETTE_READER):
            for condition in (None, '!JOINT_PALETTE_DIRECTORY_ENABLED == 1', '!UNKNOWN_PALETTE == 1'):
                with self.subTest(consumer=relative, condition=condition):
                    self.write('Config/feature_flags.asm', '!JOINT_PALETTE_DIRECTORY_ENABLED = 0\n')
                    self.write(relative, '; disposable palette consumer\n')
                    source = f'incsrc "{relative.as_posix()}"\n'
                    if condition is not None:
                        source = f'if {condition}\n{source}endif\n'
                    self.write('Oracle_main.asm', source)
                    self.assertEqual(checks.applicable(self.root, 'joint_palette_source'),
                                     condition != '!JOINT_PALETTE_DIRECTORY_ENABLED == 1')

    def test_joint_palette_missing_reader_cannot_become_absent(self):
        self.write('Oracle_main.asm',
                   'if !UNKNOWN_PALETTE == 1\nincsrc "Overworld/joint_palette_readers.asm"\nendif\n')
        with self.assertRaisesRegex(SourceGraphError, 'unresolved incsrc'):
            checks.applicable(self.root, 'joint_palette_source')

    def test_enabled_canonical_joint_palette_survives_unselected_graph_default(self):
        for canonical in ('Util/macros.asm', 'Config/module_flags.asm', 'Config/feature_flags.asm'):
            for relative in (checks.CONSUMERS['joint_palette_source'], checks.JOINT_PALETTE_READER):
                with self.subTest(canonical=canonical, consumer=relative):
                    self.write(canonical, '!JOINT_PALETTE_DIRECTORY_ENABLED = 1\n')
                    self.write(relative, '; disposable palette consumer\n')
                    self.write('Oracle_main.asm', f'incsrc "{canonical}"\n'
                               'if not(defined("JOINT_PALETTE_DIRECTORY_ENABLED"))\n'
                               '  !JOINT_PALETTE_DIRECTORY_ENABLED = 0\nendif\n'
                               f'if !JOINT_PALETTE_DIRECTORY_ENABLED == 1\nincsrc "{relative.as_posix()}"\nendif\n')
                    self.assertTrue(checks.applicable(self.root, 'joint_palette_source'))
                    (self.root / relative).unlink()
                    with self.assertRaisesRegex(SourceGraphError, 'unresolved incsrc'):
                        checks.applicable(self.root, 'joint_palette_source')
            self.write(canonical, '; no override\n')

    def test_invalid_joint_palette_flag_refuses_in_config_or_entry(self):
        for relative in ('Config/feature_flags.asm', 'Oracle_main.asm'):
            for value in ('2', '!UNKNOWN', 'nonsense()', '"0"'):
                with self.subTest(path=relative, value=value):
                    self.write('Config/feature_flags.asm', '!JOINT_PALETTE_DIRECTORY_ENABLED = 0\n')
                    self.write('Oracle_main.asm', '; no palette consumer\n')
                    self.write(relative, f'!JOINT_PALETTE_DIRECTORY_ENABLED = {value}\n')
                    with self.assertRaisesRegex(ValueError, 'Invalid graphics feature flag'):
                        checks.applicable(self.root, 'joint_palette_source')

    def test_missing_feasible_include_cannot_become_absent(self):
        for condition in (None, '!UNKNOWN_GRAPHICS == 1'):
            self.consumer('menu_icon_sheets', condition)
            (self.root/checks.CONSUMERS['menu_icon_sheets']).unlink()
            with self.assertRaisesRegex(SourceGraphError, 'unresolved incsrc'):
                checks.applicable(self.root, 'menu_icon_sheets')

    def test_dynamic_and_escaping_includes_refuse(self):
        self.write('Oracle_main.asm', 'incsrc "!UNBOUND_GRAPHICS/include.asm"\n')
        with self.assertRaisesRegex(SourceGraphError, 'unresolved incsrc'):
            checks.applicable(self.root, 'menu_icon_sheets')
        with tempfile.TemporaryDirectory() as outside:
            path = Path(outside)/'outside.asm'
            path.write_text('; outside fixture\n')
            self.write('Oracle_main.asm', f'incsrc "{path}"\n')
            with self.assertRaisesRegex(SourceGraphError, 'escapes repo root'):
                checks.applicable(self.root, 'menu_icon_sheets')

    def test_invalid_flag_cannot_reuse_earlier_value(self):
        self.write('Util/macros.asm', '!ENABLE_SOURCE_SPRITE_SHEETS = 1\n')
        for value in ('2', '!UNKNOWN', 'nonsense()', '"0"'):
            with self.subTest(value=value):
                self.write('Config/feature_flags.asm', f'!ENABLE_SOURCE_SPRITE_SHEETS = {value}\n')
                with self.assertRaisesRegex(ValueError, 'Invalid graphics feature flag'):
                    checks.applicable(self.root, 'source_sprite_sheets')


if __name__ == '__main__':
    unittest.main()
