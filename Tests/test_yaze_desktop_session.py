"""Fixed offline desktop-process fixtures; no Mesen, game or user session."""
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Mesen2'))
import yaze_dedicated_session as session


_CHILD = r'''
import hashlib,json,os,signal,socket,sys,time
from pathlib import Path
assert len(sys.argv)==2 and 'MESEN2_YAZE_DIAGNOSTIC_FD' not in os.environ
rom=Path(sys.argv[1]); profile=Path(os.environ['MESEN2_HOME'])
assert rom.parent.parent==profile and rom.stat().st_mode&0o222==0
assert Path(os.environ['HOME'])==profile
assert os.environ['MESEN2_YAZE_PRIVATE_DESKTOP']=='1'
assert profile.joinpath('instance_guid.txt').read_text()==os.environ['MESEN2_INSTANCE_GUID']
assert 'OOS_TEST_SOCKET' not in os.environ and 'DOTNET_STARTUP_HOOKS' not in os.environ
stop=False
def cancel(*_):
 global stop
 stop=True
signal.signal(signal.SIGTERM,cancel)
if mode=='early-exit':sys.exit(7)
server=socket.socket(socket.AF_UNIX,socket.SOCK_STREAM)
server.bind(os.environ['MESEN2_SOCKET_PATH']);server.listen(1);server.settimeout(.05)
while not stop:
 try:connection,_=server.accept();break
 except socket.timeout:pass
else:sys.exit(0)
connection.settimeout(.05);data=bytearray();attempt=0;ready=False
while not stop:
 try:part=connection.recv(4096)
 except socket.timeout:continue
 if not part:break
 data.extend(part)
 while b'\n' in data:
  line,_,data=data.partition(b'\n');command=json.loads(line)
  print(command['type'],flush=True)
  if command=={'type':'PING'}:reply={'success':True,'data':'PONG'}
  elif command=={'type':'LOADED_ROM_IDENTITY'}:
   attempt+=1
   if mode=='timeout' or (mode=='delayed' and attempt<=2):
    reply={'success':False,'error':'No SNES cartridge loaded'}
   elif mode=='changed':reply={'success':False,'error':'SNES cartridge changed during identity check'}
   elif mode=='numeric-not-ready':reply={'success':0,'error':'No SNES cartridge loaded'}
   else:
    b=rom.read_bytes()
    if mode=='ordinary':b+=bytes((-len(b))%4096)
    identity={'kind':'snes_prg_rom','size':len(b),
      'sha1':hashlib.sha1(b).hexdigest().upper(),'session':os.environ['MESEN2_YAZE_RUN_TOKEN']}
    if mode=='wrong-token':identity['session']='f'*32
    if mode=='wrong-digest':identity['sha1']='F'*40
    if mode=='bool-size':identity['size']=True
    reply={'success':True,'data':identity};ready=True
  else:sys.exit(9)
  connection.sendall((json.dumps(reply)+'\n').encode())
# Closing the readiness connection must not close the GUI session.
if ready and mode not in ('wrong-token','wrong-digest','bool-size'):
 profile.joinpath('Saves','fixture.srm').write_bytes(b'persistent fixture save')
 deadline=time.monotonic()+(.15 if mode!='wait' else 5)
 while not stop and time.monotonic()<deadline:time.sleep(.01)
connection.close();server.close()
print('EXIT '+str(stop),flush=True)
'''


@unittest.skipUnless(sys.platform == 'darwin', 'macOS desktop peer PID contract')
class DesktopSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yaze-desktop-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profiles = self.root / 'profiles'
        self.profiles.mkdir(mode=0o700)
        self.project = self.root / 'project.yaze'
        self.project.write_bytes(b'fixed desktop fixture project')
        self.rom = self.root / 'selected.sfc'
        self.rom.write_bytes(bytes(0x400000))
        self.settings = self.root / 'selected-settings.json'
        self.settings.write_text(json.dumps({'Input':{},'Preferences':{
            'OverrideSaveDataFolder':True,'SaveDataFolder':'/foreign/saves'}}))
        self.source_rom = self.rom.read_bytes()
        self.settings_before = self.settings.read_bytes()
        self.app = self.root / 'Fixture.app'
        self.binary = self.app / 'Contents/MacOS'
        self.binary.mkdir(parents=True)
        self.resources = self.app / 'Contents/Resources'
        self.resources.mkdir()
        self.config_path = self.root / 'desktop-config.json'
        self.set_app('delayed')

    def digest(self, path):
        return hashlib.sha256(path.read_bytes()).hexdigest()

    def set_app(self, mode, timeout=2, *, reviewed_source=None, private_loader=True):
        executable = self.binary / 'Mesen'
        executable.write_text('#!' + str(session._socketpair_interpreter()) + ' -I\nmode=' + repr(mode) + '\n' + _CHILD)
        executable.chmod(0o700)
        (self.binary/'MesenCore.dylib').write_bytes(b'fixture core never loaded')
        (self.binary/'Mesen.dll').write_bytes(b'fixture managed never loaded')
        receipt = self.resources/'oos-build.json'
        receipt.write_text(json.dumps({'schema_version':2,
            'reviewed_freeze_sha256':reviewed_source or session._REVIEWED_DESKTOP_MESEN_SOURCE,
            'contains_channel_greeting':True,'contains_frame_count':True,
            'contains_private_desktop_loader':private_loader,
            'core_sha256':self.digest(self.binary/'MesenCore.dylib'),
            'managed_sha256':self.digest(self.binary/'Mesen.dll')}))
        manifest = self.root/'bundle.json'
        manifest.write_text(json.dumps({str(p.relative_to(self.app)):{'kind':'file',
            'bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),
            'sha256':self.digest(p)} for p in self.app.rglob('*') if p.is_file()}))
        config = {'version':1,'profiles_root':str(self.profiles),
            'settings_path':str(self.settings),'settings_sha256':self.digest(self.settings),
            'startup_timeout':timeout,'app_binding':{'app_path':str(self.app),
            'receipt_sha256':self.digest(receipt),'bundle_manifest_path':str(manifest),
            'bundle_manifest_sha256':self.digest(manifest)}}
        self.config_path.write_text(json.dumps(config))

    def args(self):
        return [str(self.config_path),self.digest(self.config_path),str(self.project),
            'fixture-project-id',str(self.root),str(self.rom),self.digest(self.rom),str(len(self.source_rom))]

    def profile(self):
        return self.profiles/('yaze-'+hashlib.sha256(str(self.project).encode()).hexdigest()[:32])

    def logs(self):
        return '\n'.join(p.read_text() for p in self.profile().glob('desktop-*/mesen.log'))

    def test_desktop_requires_new_loader_receipt_but_headless_binding_is_unchanged(self):
        for source, capability in ((session._REVIEWED_MESEN_SOURCE, True),
                                   (session._REVIEWED_DESKTOP_MESEN_SOURCE, False),
                                   (session._REVIEWED_DESKTOP_MESEN_SOURCE, 1)):
            with self.subTest(source=source, capability=capability):
                self.set_app('delayed', reviewed_source=source, private_loader=capability)
                binding = json.loads(self.config_path.read_text())['app_binding']
                if source == session._REVIEWED_MESEN_SOURCE:
                    # Existing diagnostic/headless receipt remains accepted.
                    self.assertEqual(session._verify_private_app(binding)['executable'],
                                     str(self.binary / 'Mesen'))
                with mock.patch.object(session.subprocess, 'Popen') as spawn:
                    with self.assertRaisesRegex(ValueError, 'Private app lacks'):
                        session._desktop_request(self.args(), lambda _: self.fail('Unexpected ready'))
                    spawn.assert_not_called()
                self.assertFalse(self.profile().exists())

    def test_delayed_readiness_private_copy_and_persistent_profile(self):
        ready=[]
        def observe(value):
            self.assertTrue(self.profile().joinpath('.yaze-session').is_dir())
            owner=json.loads(self.profile().joinpath('.yaze-session/owner.json').read_text())
            self.assertNotIn(owner['session_token'],json.dumps(value))
            self.assertEqual(Path(value['rom_path']).read_bytes(),self.source_rom)
            self.assertNotEqual(Path(value['rom_path']),self.rom)
            ready.append(value)
        with mock.patch.dict(os.environ,{'OOS_TEST_SOCKET':'/foreign/socket','DOTNET_STARTUP_HOOKS':'foreign'}):
            self.assertEqual(session._desktop_request(self.args(),observe),0)
        self.assertEqual(len(ready),1)
        self.assertEqual(self.logs().count('LOADED_ROM_IDENTITY'),3)
        self.assertFalse(self.profile().joinpath('.yaze-session').exists())
        self.assertFalse(Path(ready[0]['socket_path']).parent.exists())
        self.assertEqual(self.rom.read_bytes(),self.source_rom)
        self.assertEqual(self.settings.read_bytes(),self.settings_before)
        settings=self.profile().joinpath('settings.json').read_bytes()
        saved=self.profile().joinpath('Saves/fixture.srm').read_bytes()
        # An existing profile does not read/reseed the selected settings source.
        self.settings.write_bytes(b'now unavailable as a settings seed')
        self.assertEqual(session._desktop_request(self.args(),ready.append),0)
        self.assertEqual(self.profile().joinpath('settings.json').read_bytes(),settings)
        self.assertEqual(self.profile().joinpath('Saves/fixture.srm').read_bytes(),saved)
        self.assertNotEqual(ready[0]['session'],ready[1]['session'])
        self.assertNotEqual(ready[0]['socket_path'],ready[1]['socket_path'])

    def test_exact_launcher_ready_line_and_exit(self):
        launcher=Path(session.__file__).with_name('mesen2_launch_instance.sh')
        result=subprocess.run(['/bin/bash',str(launcher),'--yaze-desktop',*self.args()],
            capture_output=True,text=True,timeout=8,env={**os.environ,'PYTHONDONTWRITEBYTECODE':'1'})
        self.assertEqual(result.returncode,0,result.stderr)
        lines=result.stdout.splitlines();self.assertEqual(len(lines),1)
        self.assertTrue(lines[0].startswith('YAZE_DESKTOP_READY '))
        value=json.loads(lines[0].split(' ',1)[1])
        self.assertEqual(set(value),{'version','project_path','project_id','engine_path',
            'output_path','output_sha256','output_size','pid','session','socket_path',
            'profile_path','rom_path','rom_sha1'})
        self.assertEqual(value['output_sha256'],self.digest(self.rom))
        self.assertEqual(value['project_id'],'fixture-project-id')

    def ordinary_fixture(self):
        from test_oracle_ordinary_build import OrdinaryFixture
        root=self.root/'ordinary';root.mkdir()
        fixture=OrdinaryFixture(root)
        result=fixture.run()
        self.project=fixture.project
        self.rom=Path(result['candidate']['path'])
        self.source_rom=self.rom.read_bytes()
        args=[str(self.config_path),self.digest(self.config_path),str(self.project),
              result['project_id'],str(fixture.engine),str(self.rom),self.digest(self.rom),
              str(len(self.source_rom)),str(fixture.selector),self.digest(fixture.selector)]
        return fixture,args

    def test_ordinary_exact_raw_copy_and_loaded_normalized_identity(self):
        self.set_app('ordinary')
        fixture,args=self.ordinary_fixture();ready=[]
        before=self.source_rom
        self.assertEqual(session._ordinary_desktop_request(args,ready.append),0)
        self.assertEqual(len(ready),1);value=ready[0]
        self.assertEqual(value['route'],'ordinary')
        self.assertEqual(value['output_size'],0x2190fe)
        self.assertEqual(value['loaded_rom_size'],0x21a000)
        self.assertEqual(value['rom_sha1'],hashlib.sha1(before+bytes(3842)).hexdigest())
        self.assertEqual(value['selector_sha256'],self.digest(fixture.selector))
        self.assertEqual(Path(value['rom_path']).read_bytes(),before)
        self.assertEqual(self.rom.read_bytes(),before)
        with self.assertRaisesRegex(ValueError,'4 MiB'):
            session._desktop_request(args[:8],lambda _:self.fail('expanded route accepted compact'))

    def test_ordinary_launcher_and_stale_receipt_refusal(self):
        self.set_app('ordinary');fixture,args=self.ordinary_fixture()
        launcher=Path(session.__file__).with_name('mesen2_launch_instance.sh')
        env={**os.environ,'PATH':str(fixture.bin)+':/usr/bin:/bin:/usr/sbin:/sbin',
             'YAZE_ORDINARY_RUN_PYTHON':str(Path(sys.executable).resolve())}
        result=subprocess.run(['/bin/bash',str(launcher),'--yaze-desktop-ordinary',*args],
                              capture_output=True,text=True,timeout=10,env=env)
        self.assertEqual(result.returncode,0,result.stderr)
        self.assertEqual(len(result.stdout.splitlines()),1)
        ready=json.loads(result.stdout.split(' ',1)[1]);self.assertEqual(ready['loaded_rom_size'],0x21a000)
        record=json.loads(fixture.selector.read_text());Path(record['build_receipt']['path']).write_bytes(b'changed')
        with mock.patch.object(session.subprocess,'Popen') as spawn:
            with self.assertRaisesRegex(ValueError,'bound file changed'):
                session._ordinary_desktop_request(args,lambda _:self.fail('stale receipt ready'))
            spawn.assert_not_called()

    def test_ordinary_launcher_never_falls_back_to_ambient_python(self):
        launcher=Path(session.__file__).with_name('mesen2_launch_instance.sh')
        tools=self.root/'ambient';tools.mkdir()
        marker=self.root/'ambient-was-run'
        ambient=tools/'python3'
        ambient.write_text('#!/bin/sh\n: > "$AMBIENT_MARKER"\nexit 42\n');ambient.chmod(0o700)
        nonexecutable=self.root/'not-executable';nonexecutable.write_bytes(b'fixed refusal')
        env={k:v for k,v in os.environ.items() if k!='YAZE_ORDINARY_RUN_PYTHON'}
        env.update(PATH=str(tools)+':/usr/bin:/bin',AMBIENT_MARKER=str(marker))
        for supplied in (None,'python3',str(nonexecutable),str(self.root/'missing')):
            with self.subTest(supplied=supplied):
                selected=dict(env)
                if supplied is not None:selected['YAZE_ORDINARY_RUN_PYTHON']=supplied
                result=subprocess.run(['/bin/bash',str(launcher),'--yaze-desktop-ordinary',*(['fixed']*10)],
                    capture_output=True,text=True,env=selected,timeout=3)
                self.assertEqual(result.returncode,2,result.stderr)
                self.assertIn('YAZE_ORDINARY_RUN_PYTHON',result.stderr)
                self.assertFalse(marker.exists())

    def test_ordinary_launcher_quotes_the_explicit_interpreter_path(self):
        launcher=Path(session.__file__).with_name('mesen2_launch_instance.sh')
        executable=self.root/'pinned interpreter; literal'
        executable.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\n');executable.chmod(0o700)
        result=subprocess.run(['/bin/bash',str(launcher),'--yaze-desktop-ordinary',*(['fixed']*10)],
            capture_output=True,text=True,timeout=3,
            env={**os.environ,'YAZE_ORDINARY_RUN_PYTHON':str(executable)})
        self.assertEqual(result.returncode,0,result.stderr)
        lines=result.stdout.splitlines()
        self.assertEqual(lines[:4],['-I','-S','-B','-c'])
        self.assertEqual(lines[-11:],['--desktop-ordinary',*(['fixed']*10)])

    def test_ordinary_launcher_isolated_real_helper_import_and_safe_refusal(self):
        launcher=Path(session.__file__).with_name('mesen2_launch_instance.sh')
        config=self.root/'invalid-config.json';config.write_text('{}')
        selector=self.root/'invalid-selector.json';selector.write_text('{}')
        tools=self.root/'ambient';tools.mkdir()
        marker=self.root/'ambient-was-run'
        ambient=tools/'python3'
        ambient.write_text('#!/bin/sh\n: > "$AMBIENT_MARKER"\nexit 42\n');ambient.chmod(0o700)
        args=[str(config),self.digest(config),str(self.project),'fixture-project',
              str(self.root),str(self.rom),self.digest(self.rom),str(self.rom.stat().st_size),
              str(selector),self.digest(selector)]
        before={str(p.relative_to(self.root)):p.read_bytes()
                for p in self.root.rglob('*') if p.is_file()}
        env={k:v for k,v in os.environ.items() if not k.startswith('PYTHON')}
        env.update(PATH=str(tools)+':/usr/bin:/bin',AMBIENT_MARKER=str(marker),
                   YAZE_ORDINARY_RUN_PYTHON=str(Path(sys.executable).resolve()))
        result=subprocess.run(['/bin/bash',str(launcher),'--yaze-desktop-ordinary',*args],
            capture_output=True,text=True,timeout=5,env=env)
        self.assertEqual(result.returncode,2,result.stderr)
        self.assertEqual(result.stdout,'')
        self.assertEqual(result.stderr,
            'Private ordinary desktop session refused: Expected an explicit version-1 desktop configuration\n')
        self.assertFalse(marker.exists())
        self.assertEqual(list(self.profiles.iterdir()),[])
        self.assertEqual({str(p.relative_to(self.root)):p.read_bytes()
                          for p in self.root.rglob('*') if p.is_file()},before)

    def test_refuses_changed_output_or_app_before_spawn_or_profile(self):
        for kind in ('output','app','config'):
            with self.subTest(kind=kind):
                args=self.args()
                if kind=='output':args[-2]='f'*64
                elif kind=='config':args[1]='f'*64
                else:(self.binary/'Mesen').write_bytes(b'changed')
                with mock.patch.object(session.subprocess,'Popen') as launch:
                    with self.assertRaisesRegex(ValueError,'hash differs'):
                        session._desktop_request(args,lambda _:self.fail('unexpected readiness'))
                launch.assert_not_called();self.assertEqual(list(self.profiles.iterdir()),[])

    def test_wrong_peer_refuses_before_any_request(self):
        with mock.patch.object(session,'_fixture_peer_pid',return_value=-1):
            with self.assertRaisesRegex(ValueError,'peer is not the owned child'):
                session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
        self.assertNotIn('PING',self.logs())
        self.assertFalse(self.profile().joinpath('.yaze-session').exists())

    def test_identity_mismatch_is_not_retried(self):
        for mode in ('wrong-token','wrong-digest','bool-size','changed','numeric-not-ready'):
            with self.subTest(mode=mode):
                self.project=self.root/(mode+'.yaze');self.project.write_bytes(b'fixture')
                self.set_app(mode)
                with self.assertRaisesRegex(ValueError,'loaded ROM identity differs'):
                    session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
                self.assertEqual(self.logs().count('LOADED_ROM_IDENTITY'),1)
                self.assertFalse(self.profile().joinpath('.yaze-session').exists())

    def test_timeout_and_early_exit_do_not_publish_ready(self):
        for mode in ('timeout','early-exit'):
            with self.subTest(mode=mode):
                self.project=self.root/(mode+'.yaze');self.project.write_bytes(b'fixture')
                self.set_app(mode,timeout=.25)
                with self.assertRaises((TimeoutError,RuntimeError)):
                    session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
                self.assertFalse(self.profile().joinpath('.yaze-session').exists())

    def test_cancellation_and_second_run_only_affect_owned_child(self):
        self.set_app('wait')
        def ready(_value):
            with self.assertRaises(FileExistsError):
                session._desktop_request(self.args(),lambda _:self.fail('second readiness'))
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        self.assertEqual(session._desktop_request(self.args(),ready),143)
        self.assertIn('EXIT True',self.logs())
        self.assertFalse(self.profile().joinpath('.yaze-session').exists())

    def test_uncertain_child_exit_retains_reservation(self):
        child=mock.Mock(pid=123456,returncode=None)
        child.poll.return_value=None
        child.wait.side_effect=subprocess.TimeoutExpired('fixed fixture',1.5)
        def refuse(_child, endpoint, *_):
            # The child is a mock, so removing this empty fixture-only directory
            # after checking retention cannot affect an actual process.
            self.addCleanup(endpoint.parent.rmdir)
            raise ValueError('fixture readiness')
        with mock.patch.object(session.subprocess,'Popen',return_value=child), \
             mock.patch.object(session,'_desktop_ready',side_effect=refuse):
            with self.assertRaisesRegex(RuntimeError,'exit is unproven'):
                session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
        child.terminate.assert_called_once()
        self.assertTrue(self.profile().joinpath('.yaze-session').is_dir())
        # No process was spawned or signaled; mock uncertainty is not reclaimed.

    def test_cancel_before_ready_publication_never_reports_ready(self):
        def cancel_before_publish(*_):
            signal.getsignal(signal.SIGTERM)(signal.SIGTERM,None)
        with mock.patch.object(session,'_desktop_ready',side_effect=cancel_before_publish):
            with self.assertRaisesRegex(InterruptedError,'before readiness publication'):
                session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
        self.assertFalse(self.profile().joinpath('.yaze-session').exists())

    def test_signal_uncertainty_retains_marker_and_restores_handlers(self):
        previous=signal.getsignal(signal.SIGTERM)
        child=mock.Mock(pid=123456,returncode=None)
        child.poll.return_value=None
        child.terminate.side_effect=PermissionError('fixture EPERM')
        def refuse(_child,endpoint,*_):
            self.addCleanup(endpoint.parent.rmdir)
            raise ValueError('fixture readiness')
        with mock.patch.object(session.subprocess,'Popen',return_value=child), \
             mock.patch.object(session,'_desktop_ready',side_effect=refuse):
            with self.assertRaisesRegex(RuntimeError,'exit is unproven'):
                session._desktop_request(self.args(),lambda _:self.fail('unexpected readiness'))
        self.assertIs(signal.getsignal(signal.SIGTERM),previous)
        self.assertTrue(self.profile().joinpath('.yaze-session').is_dir())


if __name__=='__main__':unittest.main()
