"""Failed disposable builds restore derived files, never authored inputs."""
import hashlib
from pathlib import Path
import unittest

import test_build_pipeline_receipt as fixtures


class BuildOutputRollbackTest(unittest.TestCase):
    # Reuse the real-shell, fake-assembler fixture without inheriting its tests.
    write = fixtures.BuildPipelineReceiptTest.write
    copy = fixtures.BuildPipelineReceiptTest.copy
    build = fixtures.BuildPipelineReceiptTest.build
    check = fixtures.BuildPipelineReceiptTest.check

    OUTPUTS = (
        'Roms/oos999x.sfc', 'Roms/oos999x.sym', 'Roms/oos999x.mlb',
        'Roms/hooks.json', 'Roms/hack_manifest.json', 'Roms/sourcemap.json',
        '.cache/annotations.json',
        'Dungeons/generated/water_gate_runtime_tables.asm',
        'Dungeons/generated/water_fill_table.asm',
    )

    def setUp(self):
        fixtures.BuildPipelineReceiptTest.setUp(self)
        self.env.update(OOS_SKIP_WATER_TABLE_GEN='0',
                        OOS_SKIP_WATER_FILL_TABLE_GEN='0',
                        OOS_GENERATE_ANNOTATIONS='1', OOS_ANALYSIS_FATAL='1')
        for name in ('generate_water_gate_runtime_tables.py', 'generate_water_fill_table.py'):
            self.write('Scripts/Generate/' + name,
                       'import os,pathlib,sys\n'
                       'out=pathlib.Path(sys.argv[sys.argv.index("--out-asm")+1])\n'
                       'out.parent.mkdir(parents=True,exist_ok=True)\n'
                       'out.write_text("; newly generated water\\n")\n'
                       'if "water_fill" in sys.argv[0]:\n'
                       ' sys.exit(int(os.getenv("FIXTURE_WATER_EXIT", "0")))\n')
        self.write('Scripts/Generate/generate_annotations.py',
                   'import pathlib,sys\n'
                   'out=pathlib.Path(sys.argv[sys.argv.index("--out")+1])\n'
                   'out.parent.mkdir(parents=True,exist_ok=True)\n'
                   'out.write_text("new annotations")\n')
        with self.assembler.open('a') as handle:
            handle.write('\npathlib.Path("Roms/sourcemap.json").write_text("new source map")\n')
        self.base_before = (self.root / 'Roms/oos999.sfc').read_bytes()
        self.flags_before = (self.root / 'Config/feature_flags.asm').read_bytes()

    def seed_outputs(self):
        return {name: self.write(name, 'previous ' + name).read_bytes()
                for name in self.OUTPUTS}

    def assert_inputs_preserved(self):
        self.assertEqual((self.root / 'Roms/oos999.sfc').read_bytes(), self.base_before)
        self.assertEqual((self.root / 'Config/feature_flags.asm').read_bytes(), self.flags_before)
        self.assertFalse(list((self.root / 'Roms').glob('.build-outputs.*')))

    def test_late_required_failure_restores_existing_set_and_keeps_attempt_receipt(self):
        before = self.seed_outputs()
        self.env['FIXTURE_ANALYSIS_EXIT'] = '7'
        result = self.build('--disable', 'fixture')
        self.assertEqual(result.returncode, 7, result.stderr)
        self.assertEqual({name: (self.root / name).read_bytes() for name in self.OUTPUTS}, before)
        self.assert_inputs_preserved()
        self.assertEqual(self.receipt['state'], 'failed')
        self.assertEqual(self.receipt['finish']['stage'], 'analysis')
        self.assertEqual(self.check('output_rollback')['status'], 'passed')
        self.assertIn('failed attempt', self.check('output_rollback')['detail'])
        attempted_digest = hashlib.sha256(self.base_before + b' assembled').hexdigest()
        self.assertEqual(self.receipt['artifacts']['output_rom']['sha256'], attempted_digest)
        self.assertNotEqual(hashlib.sha256(before['Roms/oos999x.sfc']).hexdigest(), attempted_digest)
        self.assertFalse(any(c['name'].startswith('identity:') for c in self.receipt['checks']))

    def test_failure_removes_outputs_that_were_absent_before(self):
        self.env['FIXTURE_ANALYSIS_EXIT'] = '7'
        self.assertEqual(self.build().returncode, 7)
        self.assertTrue(all(not (self.root / name).exists() for name in self.OUTPUTS))
        self.assert_inputs_preserved()
        self.assertEqual(self.receipt['state'], 'failed')
        self.assertEqual(self.check('output_rollback')['status'], 'passed')

    def test_partial_generator_failure_restores_water_before_assembly(self):
        before = self.seed_outputs()
        self.env['FIXTURE_WATER_EXIT'] = '8'
        self.assertEqual(self.build().returncode, 8)
        self.assertEqual({name: (self.root / name).read_bytes() for name in self.OUTPUTS}, before)
        self.assertEqual(self.receipt['finish']['stage'], 'water_fill')
        self.assertNotIn('pre_assembly', self.receipt['snapshots'])
        self.assertNotIn('output_rom', self.receipt['artifacts'])
        self.assert_inputs_preserved()

    def test_success_publishes_complete_new_set_with_current_receipt(self):
        before = self.seed_outputs()
        result = self.build('--disable', 'fixture')
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in self.OUTPUTS:
            self.assertNotEqual((self.root / name).read_bytes(), before[name], name)
        self.assert_inputs_preserved()
        self.assertEqual(self.receipt['state'], 'completed_with_gaps')
        self.assertFalse(any(c['name'] == 'output_rollback' for c in self.receipt['checks']))
        for name in ('output_rom', 'symbols', 'mlb', 'hooks', 'manifest', 'annotations'):
            artifact = self.receipt['artifacts'][name]
            actual = hashlib.sha256(Path(artifact['path']).read_bytes()).hexdigest()
            self.assertEqual(artifact['sha256'], actual, name)

    def test_final_receipt_failure_rolls_back_outputs_but_preserves_new_source(self):
        before = self.seed_outputs()
        # Simulate a concurrent authored edit, discovered by receipt finalization
        # only after every build stage has completed.
        self.analyzer.write_text(
            'import pathlib\n'
            'p=pathlib.Path("Core/user_edit.asm")\n'
            'p.parent.mkdir(exist_ok=True)\n'
            'p.write_text("; retain this authored edit\\n")\n')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.receipt['state'], 'failed')
        self.assertEqual(self.receipt['finish']['stage'], 'complete')
        self.assertEqual(self.check('source_snapshot_identity')['status'], 'failed')
        self.assertEqual({name: (self.root / name).read_bytes() for name in self.OUTPUTS}, before)
        self.assertEqual((self.root / 'Core/user_edit.asm').read_text(), '; retain this authored edit\n')
        self.assert_inputs_preserved()

    def test_output_alias_is_rejected_before_generating_or_patching(self):
        authored = self.write('Core/user_owned.asm', '; user-owned content\n')
        (self.root / 'Roms/hooks.json').symlink_to(authored)
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(authored.read_text(), '; user-owned content\n')
        self.assertEqual(self.receipt['finish']['stage'], 'output_snapshot')
        self.assertFalse((self.root / 'Dungeons/generated/water_fill_table.asm').exists())
        self.assert_inputs_preserved()

    def test_restore_failure_is_explicit_and_retains_prior_files_for_recovery(self):
        before = self.seed_outputs()
        self.analyzer.write_text(
            'import pathlib,sys\n'
            'p=pathlib.Path("Roms/oos999x.sfc")\n'
            'p.unlink()\n'
            'p.mkdir()\n'
            'sys.exit(7)\n')
        self.assertEqual(self.build().returncode, 7)
        self.assertEqual(self.receipt['state'], 'failed')
        self.assertEqual(self.check('output_rollback')['status'], 'failed')
        backups = list((self.root / 'Roms').glob('.build-outputs.*'))
        self.assertEqual(len(backups), 1)
        self.assertEqual((backups[0] / '0').read_bytes(), before['Roms/oos999x.sfc'])
        self.assertTrue((self.root / 'Roms/oos999x.sfc').is_dir())
        for name in self.OUTPUTS[1:]:
            self.assertEqual((self.root / name).read_bytes(), before[name], name)
        self.assertEqual((self.root / 'Roms/oos999.sfc').read_bytes(), self.base_before)
        self.assertIn(str(backups[0]), self.result.stderr)


if __name__ == '__main__':
    unittest.main()
