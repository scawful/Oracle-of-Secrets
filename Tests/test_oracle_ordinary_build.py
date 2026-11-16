"""Owned synthetic ordinary Save/Build trees; never run Asar, z3ed or a game."""
from pathlib import Path
import hashlib
import json
import os
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BUILD = Path(__file__).resolve().parents[1] / 'Scripts/Build'
sys.path.insert(0, str(BUILD))
import oracle_ordinary_build as ordinary
import lyra_macos_process_group as guardian
import lyra_process_containment as containment


def compact_rom(size=0x2190fe):
    raw = bytearray(size)
    raw[0] = 0x78
    raw[0x7fd5:0x7fd9] = bytes((0x20, 2, 12, 3))
    raw[0x7fdc:0x7fe0] = bytes((0x34, 0x12, 0xcb, 0xed))
    raw[0x7ffc:0x7ffe] = bytes((0, 0x80))
    return bytes(raw)


_FAKE_BUILD = r'''import hashlib,json,os,pathlib,sys,time
root=pathlib.Path.cwd();sys.path.insert(0,str(root/'Scripts/Build'))
import build_receipt as receipts
import oracle_ordinary_build as ordinary
state=json.loads((root.parent/'attempt.json').read_text())
profile=json.loads(pathlib.Path(state['profile']['path']).read_text())
mode=(root/'Config/fixture-mode.txt').read_text()
(root.parent/'child-environment.json').write_text(json.dumps(dict(os.environ),sort_keys=True))
(root.parent/'child.pid').write_text(str(os.getpid()))
if mode=='timeout':time.sleep(20)
if mode=='failure':sys.exit(17)
rom=root/'Roms';rom.mkdir()
source=pathlib.Path(os.environ['OOS_BASE_ROM'])
(rom/'oos168x.sfc').write_bytes(source.read_bytes())
for name in ('oos168x.sym','hooks.json','hack_manifest.json','oos168x.mlb'):
 (rom/name).write_bytes(b'fixed fixture artifact\n')
receipt_path=pathlib.Path(os.environ['OOS_BUILD_RECEIPT'])
initial=receipts.profile(root)
if mode=='generated':
 (root/'Config/feature_flags.asm').write_text('!ENABLE_FIXTURE = 1\n')
 target=root/'Dungeons/generated/water_fill_table.asm';target.parent.mkdir(parents=True)
 target.write_text('; generated fixture\n')
pre=receipts.source_snapshot(root,receipt_path)
if mode=='generated':(root/'Config/feature_flags.asm').write_text('!ENABLE_FIXTURE = 0\n')
if mode=='source-mutation':(root/'Oracle_main.asm').write_text('; changed after assembly\n')
checks=[dict(name=n,status='passed',required=True,exit_code=0) for n in sorted(ordinary.ESSENTIAL|set(profile['required_checks']))]
checks.append(dict(name='smoke',status='skipped',required=False,exit_code=0))
if mode=='failed-check':checks[0]['status']='failed'
fixed={'output_rom':rom/'oos168x.sfc','symbols':rom/'oos168x.sym','hooks':rom/'hooks.json',
 'manifest':rom/'hack_manifest.json','mlb':rom/'oos168x.mlb','water_source_rom':source}
receipt=dict(schema_version=1,state='completed_with_gaps',version='168',root=str(root),
 source_snapshot_status='captured',initial_profile=initial,snapshots={'pre_assembly':pre},
 base_rom=ordinary.binding(source),artifacts={k:ordinary.binding(p) for k,p in fixed.items()},
 tools={n:profile['tools'][key] for n,key in [('assembler','asar'),('python','python'),('z3ed','z3ed')]},
 checks=checks,finish=dict(exit_code=0,supplied_exit_code=0,stage='complete',required_gaps=[],optional_gaps=['smoke']))
receipt_path.write_text(json.dumps(receipt,sort_keys=True))
'''


class OrdinaryFixture:
    """Complete shared wire constructor for Python and C++ contract fixtures."""
    def __init__(self, root, mode='success'):
        self.root = Path(root).resolve()
        self.engine = self.root/'selected-engine'; self.engine.mkdir()
        (self.engine/'Oracle_main.asm').write_text('; fixed fixture assembly; never assembled\n')
        (self.engine/'Config').mkdir()
        (self.engine/'Config/feature_flags.asm').write_text('!ENABLE_FIXTURE = 0\n')
        (self.engine/'Config/fixture-mode.txt').write_text(mode)
        for path in BUILD.glob('*.py'):
            destination = self.engine/'Scripts/Build'/path.name
            destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(path,destination)
        for name in ('yaze_dedicated_session.py','yaze_dedicated_profile.py','mesen2_launch_instance.sh'):
            destination=self.engine/'Scripts/Mesen2'/name;destination.parent.mkdir(parents=True,exist_ok=True)
            shutil.copy2(BUILD.parent/'Mesen2'/name,destination)
        (self.engine/'Scripts/Build/build_checks.sh').write_text('# fixed benign fixture\n')
        (self.engine/'Scripts/Build/build_rom.sh').write_text('''#!/bin/bash
set -eu
exec python3 -I -S -B "$PWD/Scripts/Build/fixture_complete.py"
''')
        (self.engine/'Scripts/Build/fixture_complete.py').write_text(_FAKE_BUILD)
        self.project=self.root/'ordinary.yaze'
        self.rom=self.root/'saved.sfc';self.rom.write_bytes(compact_rom())
        self.project.write_text('[project]\nproject_id=ordinary-fixture\n[files]\nrom_filename=saved.sfc\ncode_folder=selected-engine\n')
        self.producer=self.root/'recorded-producer';self.producer.write_bytes(b'fixed recorded producer')
        self.receipt=Path(str(self.project)+'.native-save.json')
        self.context=self.root/'native-save-context.json'
        def artifact(role,path):
            row=ordinary.binding(path)
            return {'role':role,'path':row['path'],'sha256':row['sha256'],'bytes':row['size']}
        producer=artifact('producer',self.producer)
        self.receipt.write_text(json.dumps(dict(kind='yaze.native_save.v1',generation=1,
            operation_id='fixed-save-operation',operation='save',receipt_path=str(self.receipt),
            bindings_complete=True,binding_errors=[],artifacts=[artifact('project',self.project),
                artifact('rom',self.rom),producer])))
        self.context.write_text(json.dumps(dict(kind='yaze.native_save_context.v1',state='committed',
            editing_source_path=str(self.rom),project_path=str(self.project),rom_path=str(self.rom),
            producer=producer,native_commit=dict(receipt_path=str(self.receipt),generation=1,
                                               operation_id='fixed-save-operation'))))
        self.bin=self.root/'tools';self.bin.mkdir()
        (self.bin/'python3').symlink_to(Path(sys.executable).resolve())
        for name in ('asar','z3ed'):
            path=self.bin/name;path.write_text('#!/bin/sh\nexit 97\n');path.chmod(0o700)
        self.inventory=self.root/'command-sources.json'
        self.profile=Path(str(self.project)+'.oracle-build-profile.json')
        self.repin()
        self.selector=Path(str(self.project)+'.oracle-build-latest.json')
        self.environment={'YAZE_PROJECT_FILE':str(self.project),'YAZE_PROJECT_CODE_FOLDER':str(self.engine),
            'YAZE_PROJECT_ROM':str(self.rom),'YAZE_NATIVE_SAVE_RECEIPT':str(self.receipt),
            'YAZE_NATIVE_SAVE_CONTEXT':str(self.context)}

    def repin(self, timeout=5):
        files=ordinary.source_map(self.engine)
        self.inventory.write_text(json.dumps(dict(kind='oracle.command_source_inventory.v1',engine=str(self.engine),
            files={p:r for p,r in files.items() if Path(p).suffix in ('.py','.sh')}),sort_keys=True))
        tools={name:ordinary.binding(path) for name,path in {'python':Path(sys.executable).resolve(),
            'bash':Path('/bin/bash'),'git':Path('/usr/bin/git'),'asar':self.bin/'asar','z3ed':self.bin/'z3ed'}.items()}
        tools['analyzer']=None
        self.profile.write_text(json.dumps(dict(kind='oracle.macos_build_profile.v1',project=str(self.project),
            engine=str(self.engine),source_inventory=ordinary.binding(self.inventory),tools=tools,
            path=[str(self.bin),'/usr/bin','/bin','/usr/sbin','/sbin'],
            required_checks=sorted(ordinary.REQUIRED),timeout=timeout),sort_keys=True))

    def run(self):
        return ordinary.supervise(self.project,self.engine,ordinary.binding(self.profile),environment=self.environment)

    def validate(self):
        return ordinary.validate_selector(ordinary.binding(self.selector),project=self.project,
                                          engine=self.engine,context_path=self.context)

    def generations(self):
        return list(Path(str(self.project)+'.oracle-build-output').glob('oracle-*'))


class OrdinaryPureTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ordinary-binding-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.fixture=OrdinaryFixture(self.temp.name)

    def test_loaded_identity_keeps_exact_file_and_rounds_only_loaded_bytes(self):
        for length in (0x200000,0x2190fe,0x21a000,0x400000):
            with self.subTest(length=length):
                raw=compact_rom(length);before=hashlib.sha256(raw).hexdigest()
                result=ordinary.loaded_identity(raw);rounded=(length+4095)//4096*4096
                self.assertEqual(result,{'size':rounded,'sha1':hashlib.sha1(raw+bytes(rounded-length)).hexdigest()})
                self.assertEqual(len(raw),length);self.assertEqual(hashlib.sha256(raw).hexdigest(),before)

    def test_rejects_headered_ambiguous_hirom_and_coprocessor(self):
        normal=compact_rom()
        alternatives=[b'\0'*512+normal,bytes(len(normal)),normal[:0x7fd5]+b'\x21'+normal[0x7fd6:],
                      normal[:0x7fd6]+b'\x03'+normal[0x7fd7:]]
        tied=bytearray(normal);tied[0x8000:0x10000]=normal[:0x8000];tied[0xffd5]=0x21;alternatives.append(bytes(tied))
        for raw in alternatives:
            with self.subTest(digest=hashlib.sha256(raw).hexdigest()):
                with self.assertRaisesRegex(ValueError,'format'):ordinary.loaded_identity(raw)

    def test_mesen_spc_dispatch_precedes_valid_lorom_header(self):
        raw=bytearray(compact_rom());raw[0x7ffc:0x7ffe]=b'\x40\x80';raw[0x40]=0x78
        signature=b'SNES-SPC700 Sound File Data'
        self.assertEqual(len(signature),27)
        raw[:27]=signature
        with self.assertRaisesRegex(ValueError,'SPC'):ordinary.loaded_identity(bytes(raw))
        # Change exactly one signature byte without moving the header/reset
        # vector. The normal-LoROM positive stays valid.
        raw[26]=0x20
        self.assertEqual(ordinary.loaded_identity(bytes(raw))['size'],0x21a000)

    def test_genuine_recorded_producer_and_missing_receipt_are_read_only(self):
        f=self.fixture
        selected=ordinary.validate_save(f.project,f.engine,f.receipt,f.context)
        self.assertEqual(selected['project_id'],'ordinary-fixture')
        f.receipt.unlink()
        with self.assertRaisesRegex(ValueError,'Save Project first'):ordinary.validate_save(f.project,f.engine,f.receipt,f.context)
        self.assertFalse(f.selector.exists());self.assertEqual(f.generations(),[])

    def test_stale_save_and_expanded_downgrade_refuse(self):
        f=self.fixture;original=f.rom.read_bytes();f.rom.write_bytes(original+b'changed')
        with self.assertRaisesRegex(ValueError,'bound file changed'):ordinary.validate_save(f.project,f.engine,f.receipt,f.context)
        f.rom.write_bytes(original)
        for kind in ('terrain','request','selector'):
            with self.subTest(kind=kind):
                before=f.project.read_bytes()
                if kind=='selector':Path(str(f.project)+'.lyra-build-latest.json').symlink_to('/missing')
                else:f.project.write_bytes(before+('lyra_'+('terrain_file' if kind=='terrain' else 'build_request_file')+'=x\n').encode())
                with self.assertRaisesRegex(ValueError,'expanded project'):ordinary.validate_save(f.project,f.engine,f.receipt,f.context)
                f.project.write_bytes(before)

    def test_inventory_complete_set_and_strict_types(self):
        f=self.fixture
        ordinary.load_profile(ordinary.binding(f.profile),project=f.project,engine=f.engine,executing=True)
        (f.engine/'Scripts/Build/unlisted.py').write_text('raise RuntimeError("must never run")')
        with self.assertRaisesRegex(ValueError,'inventory'):ordinary.load_profile(ordinary.binding(f.profile),project=f.project,engine=f.engine)
        (f.engine/'Scripts/Build/unlisted.py').unlink()
        value=json.loads(f.profile.read_text());value['tools']['asar']['size']=True;f.profile.write_text(json.dumps(value))
        with self.assertRaisesRegex(ValueError,'binding'):ordinary.load_profile(ordinary.binding(f.profile),project=f.project,engine=f.engine)

    def test_source_symlink_and_duplicate_json_refuse(self):
        f=self.fixture
        (f.engine/'Items').symlink_to(f.root,target_is_directory=True)
        with self.assertRaisesRegex(ValueError,'canonical'):ordinary.source_map(f.engine)
        with self.assertRaisesRegex(ValueError,'duplicate'):ordinary.json_bytes(b'{"kind":1,"kind":2}')

    def test_save_as_retains_distinct_canonical_editing_origin(self):
        f=self.fixture
        value=json.loads(f.context.read_text());value['editing_source_path']=str(f.root/'previous-edit-origin.sfc')
        f.context.write_text(json.dumps(value))
        receipt=json.loads(f.receipt.read_text());receipt['operation']='save_as';f.receipt.write_text(json.dumps(receipt))
        self.assertEqual(ordinary.validate_save(f.project,f.engine,f.receipt,f.context)['base_rom'],ordinary.binding(f.rom))


@unittest.skipUnless(sys.platform=='darwin','macOS owned guardian')
class OrdinarySupervisorTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='ordinary-supervisor-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.fixture=OrdinaryFixture(self.temp.name)

    def test_completed_private_copy_publishes_exact_current_save(self):
        f=self.fixture;source=ordinary.source_map(f.engine);rom=f.rom.read_bytes();saved=f.receipt.read_bytes()
        with mock.patch.dict(os.environ,{'OOS_TEST_SOCKET':'/foreign/socket','PYTHONPYCACHEPREFIX':'/foreign/cache',
                                         'OOS_LYRA_PROJECT':'/foreign/project','BASH_ENV':'/foreign/startup'}):
            result=f.run()
        self.assertEqual(f.validate()[0],result)
        self.assertEqual(f.rom.read_bytes(),rom);self.assertEqual(f.receipt.read_bytes(),saved)
        self.assertEqual(ordinary.source_map(f.engine),source)
        root=Path(result['build_root']);env=json.loads((root.parent/'child-environment.json').read_text())
        for key in ('OOS_TEST_SOCKET','PYTHONPYCACHEPREFIX','OOS_LYRA_PROJECT','BASH_ENV'):self.assertNotIn(key,env)
        self.assertEqual(env['HOME'],str(root.parent/'home'));self.assertEqual(env['PYTHONDONTWRITEBYTECODE'],'1')
        self.assertFalse((f.engine/'Roms').exists())
        self.assertFalse(Path(str(f.project)+'.lyra-build-project.lock').exists())
        self.assertFalse((f.engine/'.lyra-build-engine.lock').exists())
        self.assertFalse(list(f.engine.rglob('__pycache__')))

    def test_generated_changes_and_exact_restored_flags(self):
        f=self.fixture;(f.engine/'Config/fixture-mode.txt').write_text('generated');f.repin()
        result=f.run();self.assertEqual(f.validate()[0],result)
        snapshot=json.loads(Path(result['source_snapshot']['path']).read_text())
        self.assertEqual(snapshot['generated_changes'],['Config/feature_flags.asm','Dungeons/generated/water_fill_table.asm'])
        self.assertEqual(snapshot['selected']['Config/feature_flags.asm'],snapshot['final']['Config/feature_flags.asm'])

    def test_failure_timeout_bad_check_and_source_mutation_stay_pending(self):
        f=self.fixture
        for mode in ('failure','timeout','failed-check','source-mutation'):
            with self.subTest(mode=mode):
                (f.engine/'Config/fixture-mode.txt').write_text(mode);f.repin(timeout=.15 if mode=='timeout' else 5)
                with self.assertRaises(ValueError):f.run()
                self.assertEqual(json.loads(f.selector.read_text())['kind'],'oracle.latest_pending.v1')
                self.assertFalse((f.engine/'.lyra-build-engine.lock').exists())

    def test_stale_artifact_source_snapshot_and_receipt_refuse_run(self):
        f=self.fixture;result=f.run()
        changes=[Path(result['candidate']['path']),f.engine/'Oracle_main.asm',
                 Path(result['build_receipt']['path']),Path(result['source_snapshot']['path']),f.producer]
        for path in changes:
            with self.subTest(path=str(path)):
                before=path.read_bytes();path.write_bytes(before+b'changed')
                with self.assertRaises(ValueError):f.validate()
                path.write_bytes(before)
        self.assertEqual(f.validate()[0],result)

    def test_required_exit_boolean_and_missing_check_refuse(self):
        f=self.fixture;result=f.run();path=Path(result['build_receipt']['path']);before=path.read_bytes()
        for mode in ('boolean','missing','duplicate','lyra'):
            with self.subTest(mode=mode):
                receipt=json.loads(before)
                if mode=='boolean':receipt['checks'][0]['exit_code']=False
                elif mode=='missing':receipt['checks'].pop(0)
                elif mode=='duplicate':receipt['checks'].append(receipt['checks'][0])
                else:receipt['lyra_attempt']={'build_id':'0'*32}
                path.write_text(json.dumps(receipt));selector=dict(result);selector['build_receipt']=ordinary.binding(path)
                f.selector.write_text(json.dumps(selector))
                with self.assertRaises(ValueError):f.validate()
        path.write_bytes(before)

    def test_guardian_uncertainty_retains_both_sentinels_and_pending(self):
        f=self.fixture
        with mock.patch.object(guardian,'run_ordinary_build',side_effect=containment.ContainmentUncertain('fixed lost guardian')):
            with self.assertRaisesRegex((ValueError,RuntimeError),'uncertain child'):f.run()
        self.assertTrue((f.engine/'.lyra-build-engine.lock').exists())
        self.assertTrue(Path(str(f.project)+'.lyra-build-project.lock').exists())
        self.assertEqual(json.loads(f.selector.read_text())['kind'],'oracle.latest_pending.v1')

    def test_cancel_during_publication_restores_pending(self):
        f=self.fixture;replace=ordinary._replace
        def cancelled(path,value,expected):
            replace(path,value,expected)
            if value['kind']=='oracle.latest_success.v1':
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        with mock.patch.object(ordinary,'_replace',side_effect=cancelled):
            with self.assertRaisesRegex(ValueError,'cancelled during publication'):f.run()
        self.assertEqual(json.loads(f.selector.read_text())['kind'],'oracle.latest_pending.v1')
        self.assertFalse((f.engine/'.lyra-build-engine.lock').exists())

    def test_selector_binding_numeric_types_cannot_compare_equal(self):
        f=self.fixture;result=f.run()
        for mutate in (lambda d:d.update(generation=True),
                       lambda d:d['project'].update(size=float(d['project']['size']))):
            value=json.loads(json.dumps(result));mutate(value);f.selector.write_text(json.dumps(value))
            with self.assertRaises(ValueError):f.validate()

    def test_committed_completion_ignores_late_release_signal_and_preserves_new_owner(self):
        import lyra_build_selection as lifecycle
        f=self.fixture;release=lifecycle.BuildSession.release;new=[]
        def completed(session):
            release(session)
            successor=lifecycle.BuildSession(f.project,f.engine,selected=False).begin()
            try:
                next_selector={'kind':'oracle.latest_pending.v1','project':str(f.project),
                    'build_id':successor.build_id,'generation':1,'operation_id':'next-owned-attempt'}
                f.selector.write_text(json.dumps(next_selector))
                new.append(f.selector.read_bytes())
                signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
            finally:release(successor)
        with mock.patch.object(lifecycle.BuildSession,'release',completed):
            result=f.run()
        self.assertEqual(result['kind'],'oracle.latest_success.v1')
        self.assertEqual(f.selector.read_bytes(),new[0])

    def test_pending_sigterm_before_terminal_commit_rolls_back_under_locks(self):
        f=self.fixture;replace=ordinary._replace;observed=[]
        def pending(path,value,expected):
            replace(path,value,expected)
            if value['kind']=='oracle.latest_success.v1':
                os.kill(os.getpid(),signal.SIGTERM)
                observed.append(signal.SIGTERM in signal.sigpending())
            elif observed:
                self.assertTrue((f.engine/'.lyra-build-engine.lock').exists())
                self.assertTrue(Path(str(f.project)+'.lyra-build-project.lock').exists())
        with mock.patch.object(ordinary,'_replace',side_effect=pending):
            with self.assertRaisesRegex(ValueError,'cancelled during publication'):f.run()
        self.assertEqual(observed,[True])
        self.assertEqual(json.loads(f.selector.read_text())['kind'],'oracle.latest_pending.v1')

    def test_sigterm_after_terminal_observation_cannot_reclassify_completion(self):
        f=self.fixture;pending=signal.sigpending;calls=[]
        def immediately_after_observation():
            observed=pending();calls.append(observed)
            if len(calls)==2:
                self.assertNotIn(signal.SIGTERM,observed)
                os.kill(os.getpid(),signal.SIGTERM)
                self.assertIn(signal.SIGTERM,pending())
                self.assertTrue((f.engine/'.lyra-build-engine.lock').exists())
            return observed
        with mock.patch.object(signal,'sigpending',side_effect=immediately_after_observation):
            result=f.run()
        self.assertEqual(len(calls),2)
        self.assertEqual(f.validate()[0],result)


if __name__=='__main__':unittest.main()
