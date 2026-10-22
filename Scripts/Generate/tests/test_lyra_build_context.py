"""Both source scanners use the current invocation, never stale file presence."""
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import asm_source as S
import generate_hooks_json as H
import generate_hack_manifest as M


class LyraBuildContextTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.write('Util/macros.asm', '!ENABLE_TEST = 1\n')
        self.write('Config/module_flags.asm', '!DISABLE_OVERWORLD = 0\n')
        self.write('Config/feature_flags.asm', '; fixture\n')
        self.write('Oracle_main.asm', '''incsrc "Util/macros.asm"
incsrc "Config/module_flags.asm"
incsrc "Config/feature_flags.asm"
if not(defined("LYRA_BUILD_CONTEXT"))
 !LYRA_BUILD_CONTEXT = 0
endif
if !LYRA_BUILD_CONTEXT == 1
 incsrc "Data/Generated/lyra_project/runtime_constants.asm"
else
 !LYRA_PROJECT_DATA_PRESENT = 0
 !LYRA_NATIVE_A1_ENABLED = 0
endif
incsrc "Overworld/reader.asm"
if !LYRA_PROJECT_DATA_PRESENT == 1
 incsrc "Data/Generated/lyra_project/runtime_data.asm"
 incsrc "Overworld/lyra_native_loaders.asm"
endif
''')
        self.write('Overworld/reader.asm', '''org $028010
if !LYRA_PROJECT_DATA_PRESENT == 1
 JSL Lyra_Helper
else
 JSL Legacy_Helper
endif
''')
        self.write('Overworld/lyra_native_loaders.asm', 'org $F8C000\nLyra_Helper:\n RTL\n')
        self.write('Data/Generated/lyra_project/runtime_data.asm', 'org $28C000\n db $01\n')
        self.constants = self.write(S.LYRA_CONSTANTS,
            '!LYRA_PROJECT_DATA_PRESENT = 1\n!LYRA_NATIVE_A1_ENABLED = 1\n'
            '!LYRA_RUNTIME_CODE_BASE = $F8C000\n!LYRA_RUNTIME_TABLE_BASE = $28C000\n')
        self.write('Data/Generated/lyra_project/prepare.json', json.dumps(dict(
            kind='lyra.ordinary_build_prepare.v1', selected=True,
            generated_files={'runtime_constants.asm': hashlib.sha256(self.constants.read_bytes()).hexdigest()})))

    def write(self, name, text):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        return path

    def collectors(self):
        return (S.collect_reachable_asm_sources, M.collect_reachable_asm_sources)

    def test_defined_and_not_are_exact_for_current_context(self):
        self.assertIs(S._eval_condition('not(defined("LYRA_BUILD_CONTEXT"))', {}), True)
        self.assertIs(S._eval_condition('not(defined("LYRA_BUILD_CONTEXT"))', {'LYRA_BUILD_CONTEXT': 0}), False)
        self.assertIsNone(S._eval_condition('defined("USE_JSL")', {}))
        self.assertIs(S._eval_condition('defined("USE_JSL")', {'USE_JSL': 0}), True)

    def test_unselected_ignores_stale_enabled_files_and_scans_only_legacy_branch(self):
        # The assembler's direct/default build cannot enable these stale files.
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '0'}):
            for collect in self.collectors():
                paths = collect(self.root)
                self.assertNotIn(self.root / S.LYRA_CONSTANTS, paths)
                self.assertNotIn(self.root / 'Overworld/lyra_native_loaders.asm', paths)
                self.assertNotIn(self.root / 'Data/Generated/lyra_project/runtime_data.asm', paths)
                hook = next(h for h in H.scan_hooks(self.root, asm_paths=paths) if h.address == 0x028010)
                self.assertEqual(hook.target, 'Legacy_Helper')
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual(S._load_global_defines(self.root)['LYRA_PROJECT_DATA_PRESENT'], 0)

    def test_selected_includes_data_native_and_current_reader_for_both_collectors(self):
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '1'}):
            for collect in self.collectors():
                paths = collect(self.root)
                for name in (S.LYRA_CONSTANTS, 'Overworld/lyra_native_loaders.asm',
                             'Data/Generated/lyra_project/runtime_data.asm'):
                    self.assertIn(self.root / name, paths)
                hook = next(h for h in H.scan_hooks(self.root, asm_paths=paths) if h.address == 0x028010)
                self.assertEqual(hook.target, 'Lyra_Helper')
            self.assertEqual(S._load_global_defines(self.root)['LYRA_RUNTIME_CODE_BASE'], 0xF8C000)

    def test_selected_requires_current_hash_bound_constants(self):
        self.constants.write_text(self.constants.read_text() + '; changed after prepare\n')
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '1'}):
            for collect in self.collectors():
                with self.assertRaisesRegex(ValueError, 'not bound to current prepared constants'):
                    collect(self.root)

    def test_selected_missing_inputs_and_invalid_context_refuse(self):
        self.constants.unlink()
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '1'}):
            for collect in self.collectors():
                with self.assertRaises(FileNotFoundError):
                    collect(self.root)
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: 'yes'}):
            with self.assertRaisesRegex(ValueError, 'must be0 or1'):
                S._load_global_defines(self.root)

    def test_unrelated_missing_include_still_refuses(self):
        self.write('Overworld/reader.asm', 'incsrc "missing-native.asm"\n')
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '0'}):
            for collect in self.collectors():
                with self.assertRaisesRegex((S.SourceGraphError, M.ManifestGenerationError), 'unresolved incsrc'):
                    collect(self.root)

    def test_foreign_preloaded_global_reassignment_still_refuses(self):
        self.write('Overworld/reader.asm', '!ENABLE_TEST = 0\n')
        with mock.patch.dict(os.environ, {S.LYRA_CONTEXT_ENV: '0'}):
            for collect in self.collectors():
                with self.assertRaisesRegex((S.SourceGraphError, M.ManifestGenerationError), 'reassigns preloaded global define'):
                    collect(self.root)

    def test_only_identical_context_declarations_are_allowed(self):
        self.assertTrue(S._is_identical_build_context_assignment('Oracle_main.asm',
            '!LYRA_PROJECT_DATA_PRESENT = 0', {'LYRA_PROJECT_DATA_PRESENT': 0}))
        for relative, line in (('Oracle_main.asm', '!LYRA_PROJECT_DATA_PRESENT = 1'),
                               ('Overworld/reader.asm', '!LYRA_PROJECT_DATA_PRESENT = 0')):
            self.assertFalse(S._is_identical_build_context_assignment(relative, line,
                {'LYRA_PROJECT_DATA_PRESENT': 0}))


if __name__ == '__main__':
    unittest.main()
