"""Managed compiler adapter controls; production byte formats are reused."""
import copy
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import special_overworld_native_build_cli as C

SPEC = importlib.util.spec_from_file_location('native_build_cli_fixture',
    Path(__file__).with_name('test_special_overworld_native_build.py'))
F = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(F)


class NativeBuildCliTest(unittest.TestCase):
    def setUp(self):
        self.fixture = F.NativeBuildPreparationTest()
        self.fixture.setUp()
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / 'source with spaces'
        self.root.mkdir()
        self.rom = self.root / 'saved source.sfc'
        self.rom.write_bytes(self.fixture.source)
        self.cache = self.root / '.cache'
        self.args = SimpleNamespace(rom=self.rom, build_cache=self.cache,
            constants=self.cache / 'special_overworld_reader_constants.asm',
            compiled=None, seal_compiled=None, symbols=None, z3ed=None)

    def test_real_cli_export_prefix_and_paths_prepare_without_source_write(self):
        project = self.root / 'project with spaces.yaze'
        project.write_text('[files]\ncode_folder=.\n')
        exported = self.root / 'export.json'
        exported.write_text(json.dumps(self.fixture.exported))
        command = self.root / 'fixture z3ed'
        command.write_text(f'#!{sys.executable}\nimport json,sys\n'
            f'assert sys.argv[1:] == ["overworld-export-native-source", "--rom", {str(self.rom.resolve())!r}, '
            f'"--format", "json", "--project-context", {str(project.resolve())!r}]\n'
            f'print("[INFO] source fixture loaded")\nprint(open({str(exported)!r}).read())\n')
        command.chmod(0o755)
        script = Path(C.native.__file__)
        result = subprocess.run([sys.executable, str(script), '--rom', str(self.rom),
            '--constants', str(self.args.constants), '--build-cache', str(self.cache),
            '--project-context', str(project),
            '--z3ed', str(command)], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.rom.read_bytes(), self.fixture.source)
        self.assertIn('!SPECIAL_OVERWORLD_NATIVE_COMPILED = 1', self.args.constants.read_text())
        self.assertIn('!SPECIAL_OVERWORLD_PALETTE_ENABLED = 1', self.args.constants.read_text())
        self.assertTrue((self.cache / C.BINARY_FILE).is_file())
        self.assertTrue((self.cache / C.DATA_FILE).is_file())
        self.assertFalse((self.cache / C.DIRECTORY_FILE).exists())
        self.assertEqual(json.loads((self.cache / C.EXPORT_FILE).read_text()), self.fixture.exported)
        with self.assertRaisesRegex(ValueError, 'cannot publish revision4'):
            C.native.reader_constants(self.fixture.source)

    def test_bound_export_requires_actual_project_selection(self):
        project = self.root / 'project.yaze'
        binding = dict(spec='Data/graphics/source_sprite_sheets.json',
                       spec_sha1='a' * 40, sheets=[])
        exported = copy.deepcopy(self.fixture.exported)
        exported['native_source']['graphics_source'] = binding
        with self.assertRaisesRegex(ValueError, 'selected project context'):
            C._graphics_root(None, exported)
        project.write_text('[files]\ncode_folder=.\n')
        with self.assertRaisesRegex(ValueError, 'unselected graphics source'):
            C._graphics_root(project, exported)
        project.write_text('[files]\ncode_folder=.\n[graphics_sheets]\n'
                           f'source_spec={binding["spec"]}\n'
                           f'source_spec_sha1={binding["spec_sha1"]}\n')
        with mock.patch.object(C, 'BUILD_ROOT', self.root):
            self.assertEqual(C._graphics_root(project, exported), self.root.resolve())
            foreign = self.root / 'different source'
            foreign.mkdir()
            (foreign / 'Util').mkdir()
            (foreign / 'Util/macros.asm').write_text('!ENABLE_SKY_OVERWORLD_GRAPHICS = 0\n')
            selected = project.read_text()
            project.write_text(selected.replace('code_folder=.',
                                                'code_folder=different source'))
            with self.assertRaisesRegex(ValueError, 'source being built'):
                C._graphics_root(project, exported)
            project.write_text(selected)
        with self.assertRaisesRegex(ValueError, 'does not match'):
            C._graphics_root(project, self.fixture.exported)
        binding['spec_sha1'] = 'b' * 40
        with self.assertRaisesRegex(ValueError, 'does not match'):
            C._graphics_root(project, exported)

    def test_stale_export_keeps_previous_generated_constants(self):
        self.cache.mkdir()
        self.args.constants.write_text('previous constants')
        exported = copy.deepcopy(self.fixture.exported)
        exported['native_source']['source_rom_sha256'] = '0' * 64
        exported = self.fixture.fixture.seal(exported['native_source'])
        with mock.patch.object(C, '_export_source', return_value=exported):
            self.assertEqual(C.run_native_build_stage(self.args, self.fixture.source), 1)
        self.assertEqual(self.args.constants.read_text(), 'previous constants')
        self.assertFalse((self.cache / C.BINARY_FILE).exists())
        self.assertEqual(self.rom.read_bytes(), self.fixture.source)

    def test_source_change_during_export_is_not_overwritten(self):
        def changed(*_):
            self.rom.write_bytes(self.fixture.source + b'concurrent authored bytes')
            return self.fixture.exported
        with mock.patch.object(C, '_export_source', side_effect=changed):
            self.assertEqual(C.run_native_build_stage(self.args, self.fixture.source), 1)
        self.assertTrue(self.rom.read_bytes().endswith(b'concurrent authored bytes'))
        self.assertFalse(self.args.constants.exists())

    def test_missing_fresh_symbols_cannot_seal_compiled_output(self):
        with mock.patch.object(C, '_export_source', return_value=self.fixture.exported):
            self.assertEqual(C.run_native_build_stage(self.args, self.fixture.source), 0)
        self.args.constants = None
        self.args.seal_compiled = self.root / 'compiled.sfc'
        self.args.seal_compiled.write_bytes(self.fixture.source)
        self.assertEqual(C.run_native_build_stage(self.args, self.fixture.source), 1)
        self.assertFalse((self.cache / C.DIRECTORY_FILE).exists())
        self.assertEqual(self.args.seal_compiled.read_bytes(), self.fixture.source)

    def test_native_source_at_directory_cleanup_path_is_never_deleted(self):
        source = self.cache / C.DIRECTORY_FILE
        source.parent.mkdir(parents=True)
        source.write_bytes(self.fixture.source)
        self.args.rom = source
        with mock.patch.object(C, '_export_source', return_value=self.fixture.exported) as export:
            self.assertEqual(C.run_native_build_stage(self.args, self.fixture.source), 1)
        self.assertEqual(source.read_bytes(), self.fixture.source)
        export.assert_not_called()
        self.assertFalse(self.args.constants.exists())

    def test_legacy_source_at_marker_cleanup_path_is_preserved(self):
        self.cache.mkdir()
        source = self.cache / C.EXPORT_FILE
        source.write_bytes(b'ordinary160 fixture source')
        self.args.constants.write_text('previous reader constants')
        result = subprocess.run([sys.executable, str(Path(C.native.__file__)),
            '--rom', str(source), '--constants', str(self.args.constants),
            '--build-cache', str(self.cache)], capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(source.read_bytes(), b'ordinary160 fixture source')
        self.assertEqual(self.args.constants.read_text(), 'previous reader constants')


if __name__ == '__main__':
    unittest.main()
