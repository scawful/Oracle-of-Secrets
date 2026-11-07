"""Bundle adapter bindings; the real compiler is never launched by these tests."""
import importlib.util
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location('authoring_bundle_build',
    Path(__file__).resolve().parents[1] / 'authoring_bundle_build.py')
B = importlib.util.module_from_spec(spec)
spec.loader.exec_module(B)


class AuthoringBundleBuildTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / 'authoring bundle with spaces'
        self.root.mkdir()
        self.root = self.root.resolve()
        self.code = self.root / 'current engine'
        script = self.code / 'Scripts/Build/build_rom.sh'
        script.parent.mkdir(parents=True)
        script.write_text('# fixture compiler; never executed\n')
        self.rom = self.root / 'saved editing rom'
        self.rom.write_bytes(b'actual saved ROM fixture')
        self.target = self.code / 'Roms/oos178x.sfc'
        self.project = self.root / 'project.yaze'
        self.text = ('[files]\ncode_folder=current engine\n'
            'rom_filename=saved editing rom\nrom_backup_folder=backups\n'
            'output_folder=current engine/Roms\nlyra_terrain_file=\n'
            'hack_manifest_file=current engine/Roms/hack_manifest.json\n'
            'lyra_build_request_file=\nnative_save_producer_file=transfer/producer.json\n'
            'native_save_transfer_proof_file=transfer/proof.json\n'
            '[rom]\nexpected_hash=unchanged-identity\nwrite_policy=block\n'
            '[build]\nbuild_target=current engine/Roms/oos178x.sfc\n'
            'output_folder=current engine/Roms\n')
        self.project.write_text(self.text)
        self.env = dict(YAZE_PROJECT_FILE=str(self.project),
            YAZE_PROJECT_CODE_FOLDER=str(self.code), YAZE_PROJECT_ROM=str(self.rom),
            YAZE_PROJECT_OUTPUT=str(self.target),
            YAZE_NATIVE_SAVE_RECEIPT='current committed receipt',
            YAZE_NATIVE_SAVE_CONTEXT='current save context',
            OOS_Z3ED_BIN='matching producer CLI')

    def invoke(self, exit_code=0):
        with mock.patch.dict(os.environ, self.env, clear=True), mock.patch.object(
                B.subprocess, 'run', return_value=SimpleNamespace(returncode=exit_code)) as run:
            result = B.build_project(self.project)
        return result, run

    def test_current_bindings_delegate_exact_rom_and_version_preserving_controls(self):
        result, run = self.invoke(7)
        self.assertEqual(result, 7)
        args, kwargs = run.call_args
        self.assertEqual(args[0], ['bash', str(self.code / 'Scripts/Build/build_rom.sh'), '178'])
        self.assertEqual(kwargs['cwd'], self.root)
        self.assertFalse(kwargs['check'])
        env = kwargs['env']
        for key, value in self.env.items():
            self.assertEqual(env[key], value)
        self.assertNotIn('OOS_BASE_ROM', env)
        self.assertEqual(env['OOS_MANIFEST_ROOT'], str(self.root))
        self.assertEqual(env['OOS_MANIFEST_OUTPUT'],
                         str(self.target.with_suffix('.manifest.json')))
        self.assertEqual(env['OOS_BACKUP_ROOT'], str(self.root / 'backups'))
        self.assertEqual(self.project.read_text(), self.text)
        self.assertEqual(self.rom.read_bytes(), b'actual saved ROM fixture')

    def test_direct_project_invocation_derives_same_paths_without_environment(self):
        self.env.clear()
        _, run = self.invoke()
        self.assertEqual(run.call_args.kwargs['env']['YAZE_PROJECT_ROM'], str(self.rom))
        self.assertEqual(run.call_args.args[0][-1], '178')

    def test_legacy_sidecar_and_request_refuse_before_child(self):
        for key in ('lyra_terrain_file', 'lyra_build_request_file'):
            self.project.write_text(self.text.replace(key + '=\n', key + '=legacy.json\n'))
            with self.subTest(key=key), mock.patch.dict(os.environ, self.env, clear=True), \
                    mock.patch.object(B.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, 'legacy ' + key):
                    B.build_project(self.project)
                run.assert_not_called()

    def test_stale_project_environment_cannot_select_different_inputs(self):
        for key in ('YAZE_PROJECT_FILE', 'YAZE_PROJECT_CODE_FOLDER',
                    'YAZE_PROJECT_ROM', 'YAZE_PROJECT_OUTPUT'):
            env = dict(self.env, **{key: str(self.root / 'different')})
            with self.subTest(key=key), mock.patch.dict(os.environ, env, clear=True), \
                    mock.patch.object(B.subprocess, 'run') as run:
                with self.assertRaisesRegex(ValueError, key + ' differs'):
                    B.build_project(self.project)
                run.assert_not_called()

    def test_legacy_environment_refuses_without_rewriting_project(self):
        for key in ('YAZE_LYRA_TERRAIN_FILE', 'OOS_LYRA_PROJECT', 'OOS_LYRA_REQUEST'):
            with self.subTest(key=key), mock.patch.dict(os.environ,
                    dict(self.env, **{key: 'legacy'}), clear=True):
                with self.assertRaisesRegex(ValueError, 'legacy ' + key):
                    B.build_project(self.project)
        self.assertEqual(self.project.read_text(), self.text)

    def test_target_placement_cannot_claim_unrelated_or_alias_output(self):
        for target in ('output/other.sfc', 'current engine/Roms/other.sfc'):
            self.project.write_text(self.text.replace(
                'current engine/Roms/oos178x.sfc', target))
            self.env.pop('YAZE_PROJECT_OUTPUT', None)
            with self.subTest(target=target), self.assertRaisesRegex(ValueError, 'Build target must'):
                self.invoke()
        self.project.write_text(self.text)
        self.target.parent.mkdir()
        self.target.hardlink_to(self.rom)
        with self.assertRaisesRegex(ValueError, 'aliases'):
            self.invoke()

    def test_explicit_base_must_still_match_saved_rom(self):
        other = self.root / 'foreign source'
        other.write_bytes(b'foreign')
        self.env['OOS_BASE_ROM'] = str(other)
        with self.assertRaisesRegex(ValueError, 'OOS_BASE_ROM differs'):
            self.invoke()
        self.env['OOS_BASE_ROM'] = str(self.rom)
        _, run = self.invoke()
        self.assertEqual(run.call_args.kwargs['env']['OOS_BASE_ROM'], str(self.rom))

    def test_missing_script_and_mismatched_output_folder_refuse(self):
        script = self.code / 'Scripts/Build/build_rom.sh'
        script.unlink()
        with self.assertRaisesRegex(ValueError, 'build script is missing'):
            self.invoke()
        script.write_text('# restored fixture\n')
        self.project.write_text(self.text.replace('output_folder=current engine/Roms',
                                                  'output_folder=foreign'))
        with self.assertRaisesRegex(ValueError, 'output_folder differs'):
            self.invoke()

    def test_foreign_compiled_manifest_override_refuses_before_child(self):
        self.env['OOS_MANIFEST_OUTPUT'] = str(self.code / 'Roms/hack_manifest.json')
        with mock.patch.dict(os.environ, self.env, clear=True), \
                mock.patch.object(B.subprocess, 'run') as run:
            with self.assertRaisesRegex(ValueError, 'OOS_MANIFEST_OUTPUT differs'):
                B.build_project(self.project)
            run.assert_not_called()

    def test_compiled_manifest_aliases_cannot_overwrite_policy_or_receipts(self):
        policy = self.code / 'Roms/hack_manifest.json'
        policy.parent.mkdir()
        policy.write_text('saved editor policy')
        manifest = self.target.with_suffix('.manifest.json')
        for kind in ('symlink', 'hardlink'):
            if kind == 'symlink':
                manifest.symlink_to(policy)
            else:
                manifest.hardlink_to(policy)
            with self.subTest(kind=kind), self.assertRaisesRegex(ValueError,
                    'Compiled manifest must'):
                self.invoke()
            self.assertEqual(policy.read_text(), 'saved editor policy')
            manifest.unlink()
        self.env['OOS_BUILD_RECEIPT'] = str(manifest)
        with self.assertRaisesRegex(ValueError, 'aliases project policy or saved inputs'):
            self.invoke()
        self.env.pop('OOS_BUILD_RECEIPT')
        self.project.write_text(self.text.replace(
            'hack_manifest_file=current engine/Roms/hack_manifest.json',
            'hack_manifest_file=current engine/Roms/oos178x.manifest.json'))
        with self.assertRaisesRegex(ValueError, 'aliases project policy or saved inputs'):
            self.invoke()


if __name__ == '__main__':
    unittest.main()
