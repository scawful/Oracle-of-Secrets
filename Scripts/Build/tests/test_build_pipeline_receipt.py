"""Run the real shell orchestration on disposable source and assembler fixtures.

Source-contract/generator internals have their own suites. These tests exercise
exit propagation, provenance dispatch and cleanup without real ROMs or emulators.
"""
from pathlib import Path
import hashlib
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
        # Keep required Lyra preparation real, including its import closure.
        # Unselected preparation consumes no project, ledger or ROM data.
        for name in ('lyra_project_publisher.py', 'lyra_project_admission.py',
                     'lyra_project_allocation.py', 'lyra_project_composition.py',
                     'lyra_project_delta.py', 'lyra_native_streams.py',
                     'lyra_project_tile32.py', 'lyra_project_terrain.py', 'lyra_native_state.py'):
            self.copy(f'Scripts/Build/{name}')
        for name in ('generate_hooks_json.py', 'asm_source.py', 'allocation_contracts.py',
                     'graphics_source_checks.py'):
            self.copy(f'Scripts/Generate/{name}')
        self.copy('Scripts/Validate/verify_hooks_json.py')
        self.write('Util/macros.asm', '!ENABLE_FIXTURE = 1\n')
        self.write('Config/feature_flags.asm', '!ENABLE_FIXTURE = 1\n')
        self.write('Config/module_flags.asm', '!DISABLE_OVERWORLD = 0\n')
        self.write('Oracle_main.asm', 'incsrc "Util/macros.asm"\n'
                   'incsrc "Config/feature_flags.asm"\norg $028000 ; @hook module=Core\nRTL\n')
        self.graphics_consumers = {
            'source_sprite_sheets': 'Core/Generated/source_sprite_sheets/sheet_overrides.asm',
            'snowpeak_sheet': 'Core/Generated/source_sprite_sheets/snowpeak/sheet_overrides.asm',
            'menu_icon_sheets': 'Core/Generated/menu_icons/menu_icon_overrides.asm',
            'joint_palette_source': 'Core/Generated/joint_palette/directory.asm',
        }
        entry = self.root / 'Oracle_main.asm'
        for include in self.graphics_consumers.values():
            self.write(include, '; fixed disposable graphics consumer\n')
            entry.write_text(entry.read_text() + f'incsrc "{include}"\n')
        self.write('Roms/oos999.sfc', 'disposable fixture bytes')
        for name in ('sheet_overrides.py', 'menu_icon_overrides.py',
                     'validate_custom_collision_source.py',
                     'validate_expanded_message_source.py', 'joint_palette_directory.py'):
            self.write(f'Scripts/Generate/{name}', 'import os,sys\nsys.exit(int(os.getenv("FIXTURE_SOURCE_EXIT", "0")))\n')
        # These source guards have independent suites; keep their child-process
        # transport explicit, like the generators above and fixture assembler.
        self.write('Scripts/Build/checkpoint_registry.py', 'import sys\nsys.exit(0)\n')
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
        self.assertEqual(self.check('source_sprite_sheets')['status'], 'passed')
        self.assertTrue(self.check('source_sprite_sheets')['required'])
        self.assertEqual(self.check('menu_icon_sheets')['status'], 'passed')
        self.assertTrue(self.check('menu_icon_sheets')['required'])
        for name in ('joint_palette_source', 'checkpoint_source'):
            self.assertEqual(self.check(name)['status'], 'passed')
            self.assertTrue(self.check(name)['required'])
        self.assertEqual(self.check('lyra_prepare')['status'], 'passed')
        self.assertTrue(self.check('lyra_prepare')['required'])
        generated = self.root / 'Data/Generated/lyra_project'
        prepared = json.loads((generated / 'prepare.json').read_bytes())
        self.assertEqual(prepared['kind'], 'lyra.ordinary_build_prepare.v1')
        self.assertIs(prepared['selected'], False)
        self.assertEqual(set(prepared['generated_files']), {'runtime_constants.asm',
                         'runtime_data.asm', 'descriptor.json', 'binaries/payload.bin'})
        for name, digest in prepared['generated_files'].items():
            self.assertEqual(hashlib.sha256((generated / name).read_bytes()).hexdigest(), digest, name)
        constants = (generated / 'runtime_constants.asm').read_text()
        self.assertIn('!LYRA_PROJECT_DATA_PRESENT = 0', constants)
        self.assertIn('!LYRA_NATIVE_A1_ENABLED = 0', constants)
        self.assertEqual(json.loads((generated / 'descriptor.json').read_bytes()), {'selected': False})
        self.assertEqual((generated / 'binaries/payload.bin').read_bytes(), b'')
        self.assertEqual(self.receipt['artifacts']['lyra_prepare']['sha256'],
                         hashlib.sha256((generated / 'prepare.json').read_bytes()).hexdigest())
        self.assertEqual(self.receipt['state'], 'completed_with_gaps')
        self.assertEqual(self.check('smoke')['status'], 'unavailable')
        hooks = json.loads((self.root / 'Roms/hooks.json').read_text())
        self.assertEqual(hooks['rom']['sha256'], self.receipt['artifacts']['output_rom']['sha256'])
        argv = json.loads((self.root / 'Roms/analyzer-args.json').read_text())
        self.assertEqual(argv[argv.index('--sym')+1], str(self.root / 'Roms/oos999x.sym'))
        self.assertIn('pre_assembly', self.receipt['snapshots'])

    def test_source_sheet_guard_failure_preserves_previous_output(self):
        output = self.write('Roms/oos999x.sfc', 'previous candidate')
        before = (self.root / 'Config/feature_flags.asm').read_bytes()
        self.env['FIXTURE_SOURCE_EXIT'] = '6'
        self.assertEqual(self.build('--disable', 'fixture').returncode, 6)
        self.assertEqual(self.check('source_sprite_sheets')['status'], 'failed')
        self.assertTrue(self.check('source_sprite_sheets')['required'])
        self.assertEqual(self.receipt['finish']['stage'], 'source_sprite_sheets')
        self.assertEqual(output.read_text(), 'previous candidate')
        self.assertEqual((self.root / 'Config/feature_flags.asm').read_bytes(), before)
        self.assertNotIn('output_rom', self.receipt['artifacts'])

    def remove_graphics_consumer(self, name):
        entry = self.root / 'Oracle_main.asm'
        include = self.graphics_consumers[name]
        entry.write_text(entry.read_text().replace(f'incsrc "{include}"\n', ''))
        (self.root / include).unlink()

    def test_absent_graphics_consumers_are_explicit_skips(self):
        for name in ('snowpeak_sheet', 'menu_icon_sheets', 'joint_palette_source'):
            self.remove_graphics_consumer(name)
        (self.root / 'Scripts/Generate/joint_palette_directory.py').unlink()
        result = self.build()
        self.assertEqual(result.returncode, 0, result.stderr)
        for name in ('snowpeak_sheet', 'menu_icon_sheets', 'joint_palette_source'):
            self.assertEqual(self.check(name)['status'], 'skipped')
            self.assertFalse(self.check(name)['required'])
            self.assertIn('Not applicable', self.check(name)['detail'])
        self.assertEqual(self.check('source_sprite_sheets')['status'], 'passed')
        self.assertTrue(self.check('source_sprite_sheets')['required'])

    def test_explicitly_required_absent_graphics_still_fail(self):
        for name, include in self.graphics_consumers.items():
            with self.subTest(name=name):
                entry = self.root / 'Oracle_main.asm'
                original = entry.read_text()
                self.remove_graphics_consumer(name)
                self.env['OOS_REQUIRE_CHECKS'] = name
                output = self.write('Roms/oos999x.sfc', 'previous candidate')
                self.assertNotEqual(self.build().returncode, 0)
                self.assertTrue(self.check(name)['required'])
                self.assertEqual(self.check(name)['status'], 'skipped')
                self.assertIn('Not applicable', self.check(name)['detail'])
                self.assertEqual(output.read_text(), 'previous candidate')
                self.write(include, '; fixed disposable graphics consumer\n')
                entry.write_text(original)

    def test_present_snowpeak_and_menu_validators_remain_required(self):
        for name in ('snowpeak_sheet', 'menu_icon_sheets'):
            with self.subTest(name=name):
                self.write('Scripts/Generate/sheet_overrides.py',
                           'import sys\nsys.exit(6 if '+repr(name == 'snowpeak_sheet')+
                           ' and any(a.endswith("snowpeak_sheet.json") for a in sys.argv) else 0)\n')
                self.write('Scripts/Generate/menu_icon_overrides.py',
                           'import sys\nsys.exit('+('6' if name == 'menu_icon_sheets' else '0')+')\n')
                output = self.write('Roms/oos999x.sfc', 'previous candidate')
                self.assertEqual(self.build().returncode, 6)
                self.assertEqual(self.check(name)['status'], 'failed')
                self.assertTrue(self.check(name)['required'])
                self.assertEqual(output.read_text(), 'previous candidate')

    def test_present_joint_palette_directory_or_reader_requires_validator(self):
        self.write('Scripts/Generate/joint_palette_directory.py', 'import sys\nsys.exit(6)\n')
        self.write('Config/feature_flags.asm', '!JOINT_PALETTE_DIRECTORY_ENABLED = 0\n')
        for reader_only in (False, True):
            with self.subTest(reader_only=reader_only):
                if reader_only:
                    self.remove_graphics_consumer('joint_palette_source')
                    self.write('Overworld/joint_palette_readers.asm', '; disposable reader\n')
                    with (self.root / 'Oracle_main.asm').open('a') as out:
                        out.write('incsrc "Overworld/joint_palette_readers.asm"\n')
                output = self.write('Roms/oos999x.sfc', 'previous candidate')
                self.assertEqual(self.build().returncode, 6)
                self.assertEqual(self.check('joint_palette_source')['status'], 'failed')
                self.assertTrue(self.check('joint_palette_source')['required'])
                self.assertEqual(output.read_text(), 'previous candidate')

    @unittest.skipIf(os.name == 'nt', 'Selected private writer requires POSIX anchored APIs')
    def test_selected_joint_palette_is_checked_after_prepared_enablement(self):
        # Keep the actual shell, graph, private writer and receipt transport.
        # Mock only source admission/preparation and stop before any assembler.
        self.copy('Scripts/Build/lyra_generated_inputs.py')
        self.copy('Scripts/Build/lyra_output_paths.py')
        self.remove_graphics_consumer('joint_palette_source')
        self.write(self.graphics_consumers['joint_palette_source'], '; disposable palette consumer\n')
        with (self.root / 'Oracle_main.asm').open('a') as out:
            out.write('if !LYRA_BUILD_CONTEXT == 1\n'
                      'incsrc "!LYRA_GENERATED_ROOT/runtime_constants.asm"\nendif\n'
                      'if !JOINT_PALETTE_DIRECTORY_ENABLED == 1\n'
                      'incsrc "Core/Generated/joint_palette/directory.asm"\nendif\n')
        private = Path(self.temp.name).resolve()
        project = private / 'selected.yaze'
        project.write_text('disposable selected project')
        candidate = Path(str(project) + '.lyra-build-output') / ('lyra-' + 'a' * 32) / 'oos168x.sfc'
        order = private / 'order.log'
        self.env.update(OOS_LYRA_PROJECT=str(project), OOS_LYRA_CANDIDATE=str(candidate),
                        OOS_BASE_ROM=str((self.root / 'Roms/oos999.sfc').resolve()),
                        OOS_SKIP_WATER_TABLE_GEN='0', FIXTURE_ORDER_LOG=str(order),
                        FIXTURE_VERIFIER=str(self.assembler.resolve()))
        self.write('Scripts/Build/lyra_project_publisher.py', '''import hashlib,json,os,sys
from pathlib import Path
import lyra_generated_inputs as generated
command=sys.argv[1]
def event(value):
 with Path(os.environ['FIXTURE_ORDER_LOG']).open('a') as out: out.write(value+'\\n')
if command=='resolve-target': print(os.environ['OOS_LYRA_CANDIDATE'])
elif command=='current-verifier': print(os.environ['FIXTURE_VERIFIER'])
elif command=='prepare':
 assert os.environ['OOS_LYRA_BUILD_CONTEXT']=='0'
 event('prepare')
 files={'runtime_constants.asm':b'!LYRA_PROJECT_DATA_PRESENT = 1\\n!LYRA_NATIVE_A1_ENABLED = 1\\n!JOINT_PALETTE_DIRECTORY_ENABLED = 1\\n'}
 files['prepare.json']=json.dumps(dict(kind='lyra.ordinary_build_prepare.v1',selected=True,
  generated_files={name:hashlib.sha256(raw).hexdigest() for name,raw in files.items()})).encode()
 generated.write_private_outputs(generated.selected_folder(Path(__file__).resolve().parents[2]),files)
elif command=='check-water':
 event('check-water');sys.exit(7)
else: raise AssertionError(command)
''')
        self.write('Scripts/Generate/joint_palette_directory.py', '''import os
from pathlib import Path
assert os.environ['OOS_LYRA_BUILD_CONTEXT']=='1'
assert (Path(os.environ['OOS_LYRA_CANDIDATE']).parent/'generated-inputs/prepare.json').is_file()
with Path(os.environ['FIXTURE_ORDER_LOG']).open('a') as out: out.write('joint:1\\n')
''')
        result = subprocess.run(['bash', str(self.root / 'Scripts/Build/build_rom.sh'),
                                 '168', str(self.assembler)], cwd=self.temp.name,
                                env=self.env, capture_output=True, text=True)
        self.assertEqual(result.returncode, 7, result.stderr)
        receipt = json.loads((candidate.parent / 'oos168x.build.json').read_text())
        joint = [row for row in receipt['checks'] if row['name'] == 'joint_palette_source']
        self.assertEqual(len(joint), 1)
        self.assertEqual(joint[0]['status'], 'passed')
        self.assertTrue(joint[0]['required'])
        self.assertEqual(order.read_text().splitlines(), ['prepare', 'joint:1', 'check-water'])
        self.assertFalse(candidate.exists())

    def test_missing_reachable_graphics_include_is_a_failure(self):
        (self.root / self.graphics_consumers['menu_icon_sheets']).unlink()
        output = self.write('Roms/oos999x.sfc', 'previous candidate')
        self.assertNotEqual(self.build().returncode, 0)
        self.assertEqual(self.check('source_sprite_sheets')['status'], 'failed')
        self.assertTrue(self.check('source_sprite_sheets')['required'])
        self.assertIn('unresolved incsrc', self.result.stderr)
        self.assertEqual(output.read_text(), 'previous candidate')

    def test_disabled_flag_cannot_bypass_a_reachable_validator(self):
        with (self.root / 'Config/feature_flags.asm').open('a') as out:
            out.write('!ENABLE_SOURCE_SPRITE_SHEETS = 0\n')
        self.write('Scripts/Generate/sheet_overrides.py',
                   'import sys\nassert "--respect-flags" not in sys.argv\nsys.exit(6)\n')
        self.assertEqual(self.build().returncode, 6)
        self.assertTrue(self.check('source_sprite_sheets')['required'])
        self.assertEqual(self.check('source_sprite_sheets')['status'], 'failed')

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
        # It was unavailable to this build; failure restores the previous set.
        self.assertEqual((self.root / 'Roms/oos999x.sym').read_text(), 'stale symbols')

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
