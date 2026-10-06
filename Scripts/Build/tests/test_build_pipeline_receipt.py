"""Run the real shell orchestration on disposable source and assembler fixtures.

Source-contract/generator internals have their own suites. These tests exercise
exit propagation, provenance dispatch and cleanup without real ROMs or emulators.
"""
from pathlib import Path
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[3]


class BuildPipelineReceiptTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name) / '.context' / 'source with spaces'
        self.root.mkdir(parents=True)
        self.env = {k: v for k, v in os.environ.items()
                    if not k.startswith(('OOS_', 'SKIP_', 'ASAR_', 'MESEN2_'))}
        self.env.update(PYTHONDONTWRITEBYTECODE='1',
                        OOS_SKIP_WATER_TABLE_GEN='1', OOS_SKIP_WATER_FILL_TABLE_GEN='1',
                        OOS_SKIP_MENU_VALIDATE='1', OOS_SKIP_VERSION_STAMP='1',
                        OOS_BACKUP_ROOT=str(self.root / 'Roms/backups'))
        for name in ('build_rom.sh', 'build_checks.sh', 'build_receipt.py',
                     'verify_feature_flags.py', 'set_feature_flags.py'):
            self.copy(f'Scripts/Build/{name}')
        for name in ('generate_hooks_json.py', 'asm_source.py'):
            self.copy(f'Scripts/Generate/{name}')
        self.copy('Scripts/Validate/verify_hooks_json.py')
        self.write('Util/macros.asm', '!ENABLE_FIXTURE = 1\n')
        self.write('Config/feature_flags.asm', '!ENABLE_FIXTURE = 1\n')
        self.write('Config/module_flags.asm', '!DISABLE_OVERWORLD = 0\n')
        self.write('Oracle_main.asm', 'incsrc "Util/macros.asm"\n'
                   'incsrc "Config/feature_flags.asm"\norg $028000 ; @hook module=Core\nRTL\n')
        self.write('Roms/oos999.sfc', 'disposable fixture bytes')
        for name in ('validate_custom_collision_source.py', 'validate_expanded_message_source.py'):
            self.write(f'Scripts/Generate/{name}', 'import os,sys\nsys.exit(int(os.getenv("FIXTURE_SOURCE_EXIT", "0")))\n')
        self.write('Scripts/Generate/generate_hack_manifest.py',
                   'import json,sys,pathlib\n'
                   'pathlib.Path(sys.argv[sys.argv.index("--output")+1]).write_text(json.dumps({"fixture":True,"argv":sys.argv[1:]}))\n')
        self.write('Scripts/Generate/export_symbols.py',
                   'import pathlib,sys\npathlib.Path(sys.argv[sys.argv.index("-o")+1]).write_text("fixture label")\n')
        self.write('Scripts/Build/check_zscream_overlap.py', 'import sys\nsys.exit(0)\n')
        self.assembler = self.write('tools/fake-asar', f'#!{sys.executable}\n' + '''import json,hashlib,os,pathlib,sys
sys.exit(int(os.environ['FIXTURE_ASM_EXIT'])) if os.getenv('FIXTURE_ASM_EXIT') else None
rom=pathlib.Path(sys.argv[-1]); rom.write_bytes(rom.read_bytes()+b' assembled')
for arg in sys.argv:
 if arg.startswith('--symbols-path=') and not os.getenv('FIXTURE_OMIT_SYMBOLS'):
  pathlib.Path(arg.split('=',1)[1]).write_text('[labels]\\n2C:8000 Oracle_Fixture\\n')
 if arg.startswith('--emit=hooks:'):
  mode=os.getenv('FIXTURE_HOOKS_MODE','good')
  data=rom.read_bytes()
  record={'rom':{'sha256':hashlib.sha256(data).hexdigest(),'size':len(data)},'hooks':[{'address':'0x028000','kind':'patch'}]}
  if mode=='stale': record['rom']['sha256']='0'*64
  if mode=='empty': record['hooks']=[]
  pathlib.Path(arg.split(':',1)[1]).write_text(json.dumps(record))
''')
        self.assembler.chmod(0o755)
        self.analyzer = self.write('tools/oracle_analyzer.py', '''import json,os,pathlib,sys
pathlib.Path('Roms/analyzer-args.json').write_text(json.dumps(sys.argv[1:]))
sys.exit(int(os.getenv('FIXTURE_ANALYSIS_EXIT','0')))
''')
        self.env['OOS_ANALYZER'] = str(self.analyzer)

    def write(self, name, content):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content)
        return p

    def copy(self, name):
        p = self.root / name
        p.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / name, p)

    def build(self, *args):
        self.result = subprocess.run(['bash', str(self.root / 'Scripts/Build/build_rom.sh'),
                                      '999', str(self.assembler), *args],
                                     cwd=self.temp.name, env=self.env, capture_output=True, text=True)
        self.receipt = json.loads((self.root / 'Roms/oos999x.build.json').read_text())
        return self.result

    def check(self, name):
        return next(c for c in self.receipt['checks'] if c['name'] == name)

    def test_compile_records_fresh_identity_and_local_symbols(self):
        self.write('Roms/hooks.json', '{"stale":true}')
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.receipt['state'], 'completed_with_gaps')
        self.assertEqual(self.check('smoke')['status'], 'unavailable')
        hooks = json.loads((self.root / 'Roms/hooks.json').read_text())
        self.assertEqual(hooks['rom']['sha256'], self.receipt['artifacts']['output_rom']['sha256'])
        argv = json.loads((self.root / 'Roms/analyzer-args.json').read_text())
        self.assertEqual(argv[argv.index('--sym')+1], str(self.root / 'Roms/oos999x.sym'))
        self.assertIn('pre_assembly', self.receipt['snapshots'])

    def test_external_cwd_preserves_relative_tool_base_and_manifest_paths(self):
        caller = Path(self.temp.name)
        self.assembler = self.assembler.relative_to(caller)
        self.env.update(
            OOS_BASE_ROM=str((self.root / 'Roms/oos999.sfc').relative_to(caller)),
            OOS_MANIFEST_ROOT='.context',
            OOS_ANALYZER=str(self.analyzer.relative_to(caller)),
        )
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = json.loads((self.root / 'Roms/hack_manifest.json').read_text())
        argv = manifest['argv']
        self.assertEqual(argv[argv.index('--manifest-root') + 1],
                         str((caller / '.context').resolve()))
        self.assertEqual(Path(self.receipt['base_rom']['path']),
                         (self.root / 'Roms/oos999.sfc').resolve())
        self.assertTrue((self.root / 'Roms/oos999x.mlb').is_file())
        self.assertFalse((caller / 'Roms').exists())

    def test_external_cwd_writes_explicit_water_outputs_in_repository(self):
        self.env.update(OOS_SKIP_WATER_TABLE_GEN='0', OOS_SKIP_WATER_FILL_TABLE_GEN='0')
        for generator in ('generate_water_gate_runtime_tables.py', 'generate_water_fill_table.py'):
            self.write('Scripts/Generate/' + generator,
                       'import json,pathlib,sys\n'
                       'assert pathlib.Path(sys.argv[sys.argv.index("--rom")+1]).is_file()\n'
                       'out=pathlib.Path(sys.argv[sys.argv.index("--out-asm")+1])\n'
                       'out.parent.mkdir(parents=True,exist_ok=True)\n'
                       'out.write_text("; disposable water output\\n")\n')
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        for output in ('water_gate_runtime_tables.asm', 'water_fill_table.asm'):
            self.assertTrue((self.root / 'Dungeons/generated' / output).is_file())
        self.assertEqual(self.check('water_tables')['status'], 'passed')
        self.assertEqual(self.check('water_fill')['status'], 'passed')
        self.assertFalse((Path(self.temp.name) / 'Dungeons').exists())

    def test_missing_required_analyzer_fails(self):
        self.env.update(OOS_ANALYZER=str(self.root / 'absent.py'), OOS_ANALYSIS_FATAL='1')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('analysis')['status'], 'unavailable')
        self.assertEqual(self.receipt['state'], 'failed')

    def test_required_menu_skip_does_not_pass(self):
        self.env['OOS_REQUIRE_CHECKS'] = 'menu'
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('menu')['status'], 'skipped')

    def test_missing_required_menu_tool_fails(self):
        self.env.update(OOS_SKIP_MENU_VALIDATE='0', OOS_Z3ED_BIN='/missing-z3ed-fixture')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('menu')['status'], 'unavailable')

    def test_reload_without_endpoint_never_calls_client(self):
        self.write('Scripts/Mesen2/mesen2_client.py',
                   'from pathlib import Path\nPath("Roms/client-called").touch()\n')
        self.assertNotEqual(self.build('--reload', '--skip-tests').returncode, 0)
        self.assertEqual(self.check('reload')['status'], 'unavailable')
        self.assertFalse((self.root / 'Roms/client-called').exists())

    def test_reload_failed_identity_never_calls_client(self):
        self.write('Scripts/Mesen2/mesen2_client.py',
                   'from pathlib import Path\nPath("Roms/client-called").touch()\n')
        self.write('Scripts/Build/run_build_smoke.py', 'import sys\nprint("{}")\nsys.exit(1)\n')
        self.env['OOS_TEST_SOCKET'] = '/unused-fixture.sock'
        self.assertNotEqual(self.build('--reload', '--skip-tests').returncode, 0)
        self.assertEqual(self.check('reload_identity')['status'], 'failed')
        self.assertFalse((self.root / 'Roms/client-called').exists())

    def test_required_analysis_cannot_be_skipped(self):
        self.env.update(OOS_REQUIRE_CHECKS='analysis', SKIP_ANALYSIS='1')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertTrue(self.check('analysis')['required'])

    def test_optional_analysis_failure_is_explicit_gap(self):
        self.env['FIXTURE_ANALYSIS_EXIT'] = '7'
        self.assertEqual(self.build().returncode, 0)
        self.assertEqual(self.check('analysis')['status'], 'failed')
        self.assertEqual(self.receipt['state'], 'completed_with_gaps')

    def test_required_smoke_without_endpoint_fails_without_discovery(self):
        self.env['OOS_REQUIRE_CHECKS'] = 'smoke'
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('smoke')['status'], 'unavailable')

    def test_required_smoke_skip_does_not_pass(self):
        self.env['OOS_TEST_REQUIRE_EMULATOR'] = '1'
        self.assertNotEqual(self.build('--skip-tests').returncode, 0)
        self.assertEqual(self.check('smoke')['status'], 'skipped')

    def test_actual_smoke_failure_fails_build(self):
        self.write('Scripts/Build/run_build_smoke.py', 'import sys\nsys.exit(7)\n')
        self.env['OOS_TEST_SOCKET'] = '/unused-fixture.sock'
        self.assertEqual(self.build().returncode, 7)
        self.assertEqual(self.check('smoke')['status'], 'failed')
        self.assertEqual(self.receipt['state'], 'failed')

    def test_flags_restore_after_assembly_failure(self):
        before = (self.root / 'Config/feature_flags.asm').read_bytes()
        self.env['FIXTURE_ASM_EXIT'] = '9'
        self.assertEqual(self.build('--disable', 'fixture').returncode, 9)
        self.assertEqual((self.root / 'Config/feature_flags.asm').read_bytes(), before)
        flags = self.receipt['snapshots']['pre_assembly']['profile']['effective_flags']
        self.assertEqual(flags['ENABLE_FIXTURE'], 0)

    def test_flags_restore_after_success(self):
        before = (self.root / 'Config/feature_flags.asm').read_bytes()
        self.assertEqual(self.build('--disable', 'fixture').returncode, 0, self.result.stderr)
        self.assertEqual((self.root / 'Config/feature_flags.asm').read_bytes(), before)

    def test_unknown_flag_assignment_under_context_is_detected(self):
        self.write('Core/incorrect.asm', '!ENABLE_FIXTURE = 0\n')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('flags')['status'], 'failed')
        self.assertNotIn('output_rom', self.receipt['artifacts'])

    def test_missing_base_produces_failed_receipt(self):
        (self.root / 'Roms/oos999.sfc').unlink()
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('base_rom')['status'], 'unavailable')

    def test_base_alias_to_output_is_rejected_before_write(self):
        base = self.root / 'Roms/oos999.sfc'
        before = base.read_bytes()
        (self.root / 'Roms/oos999x.sfc').symlink_to(base)
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(base.read_bytes(), before)

    def test_missing_assembler_preserves_previous_output(self):
        output = self.write('Roms/oos999x.sfc', 'previous candidate')
        self.assembler.unlink()
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(output.read_text(), 'previous candidate')

    def test_no_symbols_cannot_use_stale_shared_analysis(self):
        self.write('Roms/oos999x.sym', 'stale symbols')
        self.env['OOS_REQUIRE_CHECKS'] = 'analysis'
        self.assertNotEqual(self.build('--no-symbols').returncode, 0)
        self.assertEqual(self.check('analysis')['status'], 'unavailable')
        self.assertFalse((self.root / 'Roms/oos999x.sym').exists())

    def test_assembler_success_without_symbols_fails(self):
        self.write('Roms/oos999x.sym', 'stale symbols')
        self.env['FIXTURE_OMIT_SYMBOLS'] = '1'
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.receipt['state'], 'failed')

    def test_bad_exact_hooks_fail_before_manifest(self):
        self.assembler = self.assembler.rename(self.assembler.with_name('fake-z3asm'))
        for mode in ('stale', 'empty'):
            with self.subTest(mode=mode):
                self.env['FIXTURE_HOOKS_MODE'] = mode
                self.assertNotEqual(self.build().returncode, 0)
                self.assertEqual(self.check('hooks')['status'], 'failed')
                self.assertNotIn('manifest', self.receipt['artifacts'])


if __name__ == '__main__':
    unittest.main()
