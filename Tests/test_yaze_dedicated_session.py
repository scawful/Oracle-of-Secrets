"""Offline fixtures only: no Mesen process, shared settings, saves or ROMs."""
from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path
import signal
import stat
import subprocess
import tempfile
import sys
import time
import unittest
from unittest import mock
import yaze_dedicated_session as session

from yaze_dedicated_session import (prepare_session, launch_dedicated_mesen,
                                    _run_synthetic_lifecycle)


_PRIVATE_APP_FIXTURE = r'''
import hashlib, json, os, signal, socket, sys, time
from pathlib import Path
assert sys.argv[1] == '--yaze-diagnostic' and len(sys.argv) == 3
assert 'MESEN2_SOCKET_PATH' not in os.environ
assert os.getppid() == int(os.environ['MESEN2_YAZE_OWNER_PID'])
assert Path(os.environ['MESEN2_HOME'], 'instance_guid.txt').read_text() == os.environ['MESEN2_INSTANCE_GUID']
connection = socket.socket(fileno=3)
def stop(_signal, _frame):
    connection.setblocking(False)
    try:
        if connection.recv(1, socket.MSG_PEEK) == b'':
            print('EARLY_EOF', flush=True); os._exit(72)
    except BlockingIOError:
        pass
    print('SIGTERM_WITH_CHANNEL_OPEN', flush=True)
    sys.exit(0)
signal.signal(signal.SIGTERM, stop)
connection.sendall((json.dumps({'event':'YAZE_DIAGNOSTIC_CHANNEL_READY','version':1,'pid':os.getpid()})+'\n').encode())
rom = Path(sys.argv[2]).read_bytes()
identity = {'kind':'snes_prg_rom','size':len(rom),'sha1':hashlib.sha1(rom).hexdigest().upper(),
            'session':os.environ['MESEN2_YAZE_RUN_TOKEN'],'frameCount':0}
attempt = 0
with connection.makefile('rb') as stream:
    for line in stream:
        command = json.loads(line)
        if command == {'type':'PING'}:
            reply = {'success':True,'data':'PONG'}
        elif command == {'type':'LOADED_ROM_IDENTITY'}:
            attempt += 1
            print('IDENTITY_ATTEMPT '+str(attempt),flush=True)
            if mode == 'not-ready' or (mode == 'delayed' and attempt <= 2):
                reply = {'success':False,'error':'No SNES cartridge loaded'}
            elif mode == 'changed':
                reply = {'success':False,'error':'SNES cartridge changed during identity check'}
            elif mode == 'malformed-not-ready':
                reply = {'success':False,'error':'No SNES cartridge loaded','extra':1}
            else:
                if mode == 'wrong-token': identity['session'] = 'f'*32
                if mode == 'wrong-digest': identity['sha1'] = 'F'*40
                if mode == 'float-size': identity['size'] = float(identity['size'])
                if mode == 'advanced-frame': identity['frameCount'] = 1
                reply = {'success':True,'data':identity}
        else:
            sys.exit(73)
        connection.sendall((json.dumps(reply)+'\n').encode())
sys.exit(74)
'''


class _FixtureNativeLease:
    """No /tmp native slot: observe the real gated fixture PID only."""
    def __init__(self):
        self.pid = None
        self.released = False
    def process_start(self, pid):
        value = subprocess.run(['/bin/ps', '-p', str(pid), '-o', 'lstart='],
                               capture_output=True, text=True, check=False)
        return ' '.join(value.stdout.split()) or None
    def acquire(self, owner, purpose, pid):
        assert self.process_start(pid) is not None
        self.pid = pid
        return 'fixture-native-lease'
    def release(self, token):
        assert token == 'fixture-native-lease' and self.process_start(self.pid) is None
        self.released = True
        return True


@unittest.skipUnless(os.name == 'posix', 'POSIX preparation contract')
class DedicatedSessionTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='yaze-session-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.profiles = self.root / 'profiles'
        self.profiles.mkdir(mode=0o700)
        self.project = self.root / 'oracle.yaze'
        self.project.write_bytes(b'fixture project')
        self.rom = self.root / 'oos168x.sfc'
        self.rom_bytes = bytes(0x400000)
        self.rom.write_bytes(self.rom_bytes)
        self.settings = json.dumps({
            'Input': {'Player1': 'selected controller'},
            'Preferences': {'OverrideSaveDataFolder': True,
                            'SaveDataFolder': '/shared/saves',
                            'OverrideSaveStateFolder': True,
                            'SaveStateFolder': '/shared/states',
                            'GameSelectionScreenMode': 'ResumeState',
                            'EnableAutoSaveState': True},
        }).encode()

    def prepare(self, *, fresh=True, **overrides):
        args = dict(project_path=self.project, rom_path=self.rom,
                    verified_rom_bytes=self.rom_bytes, profiles_root=self.profiles,
                    settings_bytes=self.settings if fresh else None)
        args.update(overrides)
        return prepare_session(**args)

    def private_app(self, mode='delayed'):
        app = self.root / 'Fixture.app'
        binary_dir = app / 'Contents/MacOS'
        binary_dir.mkdir(parents=True)
        resources = app / 'Contents/Resources'
        resources.mkdir()
        executable = binary_dir / 'Mesen'
        executable.write_text('#!' + str(session._socketpair_interpreter()) + ' -I\nmode=' + repr(mode) + '\n' + _PRIVATE_APP_FIXTURE)
        executable.chmod(0o700)
        core = b'fixed fixture core, never loaded'
        managed = b'fixed fixture assembly, never loaded'
        (binary_dir / 'MesenCore.dylib').write_bytes(core)
        (binary_dir / 'Mesen.dll').write_bytes(managed)
        receipt = resources / 'oos-build.json'
        receipt.write_text(json.dumps({'schema_version':2,
            'reviewed_freeze_sha256':session._REVIEWED_MESEN_SOURCE,
            'contains_channel_greeting':True,'contains_frame_count':True,
            'core_sha256':hashlib.sha256(core).hexdigest(),
            'managed_sha256':hashlib.sha256(managed).hexdigest()}))
        manifest = self.root / 'bundle.json'
        manifest.write_text(json.dumps({str(p.relative_to(app)):{'kind':'file',
            'bytes':p.stat().st_size,'mode':stat.S_IMODE(p.stat().st_mode),
            'sha256':hashlib.sha256(p.read_bytes()).hexdigest()}
            for p in app.rglob('*') if p.is_file()}))
        return {'app_path':str(app),'receipt_sha256':hashlib.sha256(receipt.read_bytes()).hexdigest(),
            'bundle_manifest_path':str(manifest),'bundle_manifest_sha256':hashlib.sha256(manifest.read_bytes()).hexdigest()}

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_delayed_identity_and_sigterm_channel_lifetime(self):
        prepared = self.prepare(diagnostic=True)
        self.rom.chmod(0o444)
        binding = self.private_app()
        lease = _FixtureNativeLease()
        with mock.patch.object(session, '_native_lock_module', return_value=lease):
            result = launch_dedicated_mesen(prepared, app_binding=binding,
                private_root=self.root, timeout=5)
        self.assertEqual(result['identity_attempts'], 3)
        self.assertEqual(result['identity']['data']['sha1'], hashlib.sha1(self.rom_bytes).hexdigest())
        self.assertEqual(result['child_exit'], 0)
        self.assertEqual(result['shutdown_signal'], 'SIGTERM')
        self.assertTrue(result['native_lease']['released'] and lease.released)
        self.assertEqual(result['native_lease']['pid'], result['child_pid'])
        log = Path(prepared.plan.profile_path) / ('socketpair-' + prepared.plan.session_token + '-child.log')
        self.assertIn('SIGTERM_WITH_CHANNEL_OPEN', log.read_text())
        self.assertFalse((Path(prepared.plan.profile_path) / '.yaze-session').exists())
        print('PRIVATE_ADAPTER_OBSERVATION ' + json.dumps(result, sort_keys=True))

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_binding_mismatch_refuses_before_spawn(self):
        prepared = self.prepare(diagnostic=True)
        self.rom.chmod(0o444)
        binding = self.private_app()
        (Path(binding['app_path']) / 'Contents/MacOS/Mesen').write_text('changed')
        with mock.patch('subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'hash differs'):
                launch_dedicated_mesen(prepared, app_binding=binding, private_root=self.root)
        popen.assert_not_called()
        prepared.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_foreign_identity_and_other_errors_are_not_retried(self):
        for mode in ('wrong-token', 'wrong-digest', 'float-size', 'changed', 'malformed-not-ready', 'advanced-frame'):
            with self.subTest(mode=mode), tempfile.TemporaryDirectory(dir=self.root) as unused:
                # Each candidate uses a fresh project/profile binding.
                self.project = self.root / (mode + '.yaze')
                self.project.write_bytes(b'fixture')
                if (self.root / 'Fixture.app').exists():
                    import shutil
                    shutil.rmtree(self.root / 'Fixture.app')
                prepared = self.prepare(diagnostic=True)
                self.rom.chmod(0o444)
                binding = self.private_app(mode)
                lease = _FixtureNativeLease()
                with mock.patch.object(session, '_native_lock_module', return_value=lease):
                    with self.assertRaises(session.SyntheticGuardianError) as error:
                        launch_dedicated_mesen(prepared, app_binding=binding,
                            private_root=self.root, timeout=3)
                self.assertTrue(error.exception.observation['quiescent'])
                self.assertTrue(lease.released)
                log = Path(prepared.plan.profile_path) / ('socketpair-' + prepared.plan.session_token + '-child.log')
                self.assertEqual(log.read_text().count('IDENTITY_ATTEMPT '), 1)
                self.assertIn('SIGTERM_WITH_CHANNEL_OPEN', log.read_text())
                guardian_log = log.with_name(log.name.replace('-child.log', '-guardian.log')).read_text()
                evidence = [json.loads(line) for line in guardian_log.splitlines()
                            if json.loads(line).get('event') == 'identity_mismatch']
                self.assertEqual(len(evidence), 1)
                field = {'wrong-token': 'session', 'wrong-digest': 'sha1', 'float-size': 'size',
                         'changed': 'error', 'malformed-not-ready': 'envelope.keys',
                         'advanced-frame': 'frameCount'}[mode]
                self.assertIn(field, [row['field'] for row in evidence[0]['fields']])
                self.assertNotIn(prepared.plan.session_token, guardian_log)
                if mode == 'wrong-token':
                    self.assertNotIn('f' * 32, guardian_log)
                self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_readiness_timeout_retains_reservation(self):
        prepared = self.prepare(diagnostic=True)
        self.rom.chmod(0o444)
        binding = self.private_app('not-ready')
        lease = _FixtureNativeLease()
        with mock.patch.object(session, '_native_lock_module', return_value=lease):
            with self.assertRaises(session.SyntheticGuardianError) as error:
                launch_dedicated_mesen(prepared, app_binding=binding,
                    private_root=self.root, timeout=1)
        self.assertTrue(error.exception.observation['quiescent'])
        self.assertTrue(lease.released)
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_native_lease_refusal_keeps_child_gated(self):
        prepared = self.prepare(diagnostic=True)
        self.rom.chmod(0o444)
        binding = self.private_app()
        lease = _FixtureNativeLease()
        lease.acquire = lambda *args, **kwargs: None
        with mock.patch.object(session, '_native_lock_module', return_value=lease):
            with self.assertRaisesRegex(RuntimeError, 'Native lease unavailable'):
                launch_dedicated_mesen(prepared, app_binding=binding,
                    private_root=self.root, timeout=3)
        log = Path(prepared.plan.profile_path) / ('socketpair-' + prepared.plan.session_token + '-child.log')
        self.assertEqual(log.read_bytes(), b'')
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'fixed private-app guardian fixture')
    def test_private_adapter_uncertain_cleanup_retains_native_lease(self):
        prepared = self.prepare(diagnostic=True)
        self.rom.chmod(0o444)
        binding = self.private_app()
        app = session._verify_private_app(binding)
        lease = _FixtureNativeLease()
        with mock.patch.object(session, '_native_lock_module', return_value=lease):
            with self.assertRaises(session.SyntheticGuardianError):
                session._run_guardian(prepared, timeout=3, scenario='uncertain-quiescence',
                    mesen={**app, 'binding':binding, 'private_root':str(self.root),
                           'instance_guid':prepared.plan.instance_guid, 'owner':'offline-fixture'})
        self.assertFalse(lease.released)
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    def test_diagnostic_launcher_refuses_bad_request_before_ordinary_defaults(self):
        launcher = Path(session.__file__).with_name('mesen2_launch_instance.sh')
        request = self.root / 'request.json'
        request.write_text('{}')
        result = subprocess.run(['/bin/bash', str(launcher), '--yaze-headless-diagnostic',
                                 str(request), '0' * 64], capture_output=True, text=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('input hash differs', result.stderr)
        self.assertNotIn('ROM not found', result.stderr)
        self.assertEqual(list(self.profiles.iterdir()), [])

    def test_prepare_has_no_launch_endpoint_and_preserves_selected_settings(self):
        prepared = self.prepare()
        plan = prepared.plan
        settings = json.loads((Path(plan.profile_path) / 'settings.json').read_bytes())
        self.assertEqual(settings['Input']['Player1'], 'selected controller')
        self.assertFalse(settings['Preferences']['OverrideSaveDataFolder'])
        self.assertFalse(settings['Preferences']['OverrideSaveStateFolder'])
        self.assertEqual(settings['Preferences']['GameSelectionScreenMode'], 'ResumeState')
        self.assertTrue(settings['Preferences']['EnableAutoSaveState'])
        self.assertEqual(plan.rom_sha256, hashlib.sha256(self.rom_bytes).hexdigest())
        self.assertEqual(plan.socket_path, '')
        with self.assertRaisesRegex(ValueError, 'launch is unavailable'):
            plan.child_environment(dict(os.environ))
        prepared.cancel_before_launch()

    def test_diagnostic_settings_disable_snapshots_only_for_new_diagnostic_profile(self):
        source = self.settings
        prepared = self.prepare(diagnostic=True)
        profile = Path(prepared.plan.profile_path)
        raw = (profile / 'settings.json').read_bytes()
        session._verify_diagnostic_settings(raw)
        preferences = json.loads(raw)['Preferences']
        self.assertEqual(preferences['GameSelectionScreenMode'], 'Disabled')
        self.assertIs(preferences['EnableAutoSaveState'], False)
        self.assertEqual(self.settings, source)
        self.assertEqual(json.loads(raw)['Input'], json.loads(source)['Input'])
        prepared.cancel_before_launch()
        reopened = self.prepare(fresh=False, diagnostic=True)
        self.assertEqual((profile / 'settings.json').read_bytes(), raw)
        reopened.cancel_before_launch()

    def test_diagnostic_refuses_existing_snapshot_settings_without_rewriting(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        raw = (profile / 'settings.json').read_bytes()
        prepared.cancel_before_launch()
        reopened = self.prepare(fresh=False, diagnostic=True)
        self.rom.chmod(0o444)
        with mock.patch('subprocess.Popen') as popen:
            with self.assertRaisesRegex(ValueError, 'GameSelectionScreenMode'):
                launch_dedicated_mesen(reopened, app_binding={}, private_root=self.root)
        popen.assert_not_called()
        self.assertEqual((profile / 'settings.json').read_bytes(), raw)
        reopened.cancel_before_launch()

    def test_sha1_wire_hex_case_only_is_canonicalized(self):
        # Known all-zero 4 MiB cartridge digest; Mesen Utilities/sha1.cpp uses
        # uppercase A-F. The private-app fixture above emits that exact casing.
        digest = '2BCCBD2F38F15C13EB7D5A89FD9D85F595E23BC3'
        self.assertEqual(hashlib.sha1(self.rom_bytes).hexdigest(), digest.lower())
        identity = {'kind': 'snes_prg_rom', 'size': len(self.rom_bytes),
                    'sha1': digest.lower(), 'session': 'a' * 32, 'frameCount': 0}
        expected = {'success': True, 'data': identity}
        for wire in (digest, digest.lower(), digest[:20] + digest[20:].lower()):
            reply = {'success': True, 'data': {**identity, 'sha1': wire}}
            self.assertEqual(session._canonical_identity_reply(reply), expected)
            self.assertEqual(reply['data']['sha1'], wire)
        for wire in ('F' * 40, digest[:-1], digest + '0', digest[:-1] + 'G',
                     ' ' + digest, digest + '\n', 'Ｆ' * 40, None, 123, [digest]):
            reply = {'success': True, 'data': {**identity, 'sha1': wire}}
            canonical = session._canonical_identity_reply(reply)
            self.assertNotEqual(canonical, expected)
            self.assertIn('sha1', [row['field'] for row in
                                  session._identity_mismatch_evidence(canonical, identity)])
        for field, changed in (('session', 'A' * 32), ('kind', 'SNES_PRG_ROM'),
                               ('size', len(self.rom_bytes) + 1), ('frameCount', True)):
            reply = {'success': True, 'data': {**identity, 'sha1': digest, field: changed}}
            self.assertIn(field, [row['field'] for row in session._identity_mismatch_evidence(
                session._canonical_identity_reply(reply), identity)])
        wrong = {'success': False, 'error': 'unexpected ' + identity['session'],
                 'data': {**identity, 'session': 'b' * 32, 'sha1': 'b' * 32}}
        evidence = json.dumps(session._identity_mismatch_evidence(wrong, identity))
        self.assertNotIn('a' * 32, evidence)
        self.assertNotIn('b' * 32, evidence)
        self.assertIn('<redacted>', evidence)

    def test_existing_profile_preserves_settings_guid_saves_and_states(self):
        first = self.prepare()
        profile = Path(first.plan.profile_path)
        (profile / 'Saves' / 'oos168x.srm').write_bytes(b'owned saved progress')
        (profile / 'SaveStates' / 'oos168x_1.mss').write_bytes(b'owned state')
        before = {p.relative_to(profile): p.read_bytes()
                  for p in profile.rglob('*') if p.is_file()
                  and '.yaze-session' not in p.parts}
        first.cancel_before_launch()
        second = self.prepare(fresh=False)
        self.assertEqual(second.plan.profile_path, first.plan.profile_path)
        self.assertEqual(second.plan.instance_guid, first.plan.instance_guid)
        self.assertNotEqual(second.plan.session_token, first.plan.session_token)
        self.assertEqual(before, {p: (profile / p).read_bytes() for p in before})
        second.cancel_before_launch()

    def test_reservation_blocks_concurrent_and_uncertain_launch(self):
        prepared = self.prepare()
        with self.assertRaises(FileExistsError):
            self.prepare(fresh=False)
        prepared.mark_launch_started()
        with self.assertRaisesRegex(ValueError, 'Child exit is unproven'):
            prepared.cancel_before_launch()
        with self.assertRaises(FileExistsError):
            self.prepare(fresh=False)
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').is_dir())

    def test_changed_owner_cannot_release_reservation(self):
        prepared = self.prepare()
        owner = Path(prepared.plan.profile_path) / '.yaze-session' / 'owner.json'
        owner.write_text('{}')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            prepared.cancel_before_launch()
        self.assertTrue(owner.exists())

    def test_existing_profile_rejects_redirect_and_retains_marker(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        (profile / 'settings.json').write_bytes(self.settings)
        with self.assertRaisesRegex(ValueError, 'redirects saves'):
            self.prepare(fresh=False)
        self.assertEqual((profile / 'settings.json').read_bytes(), self.settings)
        self.assertTrue((profile / '.yaze-session' / 'owner.json').is_file())

    def test_changed_rom_filename_cannot_silently_switch_save_identity(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        other = self.root / 'different.sfc'
        other.write_bytes(self.rom_bytes)
        with self.assertRaisesRegex(ValueError, 'project/save identity differs'):
            self.prepare(fresh=False, rom_path=other)
        self.assertTrue((profile / '.yaze-session').is_dir())

    def test_changed_rom_and_symlink_are_refused_before_profile_mutation(self):
        self.rom.write_bytes(bytes([1]) + self.rom_bytes[1:])
        with self.assertRaisesRegex(ValueError, 'does not match'):
            self.prepare()
        self.assertEqual(list(self.profiles.iterdir()), [])
        alias = self.root / 'alias.sfc'
        alias.symlink_to(self.rom)
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.prepare(rom_path=alias)
        self.assertEqual(list(self.profiles.iterdir()), [])

    def test_profile_save_symlink_is_refused(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        (profile / 'Saves').rmdir()
        outside = self.root / 'outside-saves'
        outside.mkdir(mode=0o700)
        (profile / 'Saves').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'canonical'):
            self.prepare(fresh=False)
        self.assertEqual(list(outside.iterdir()), [])

    def test_profile_save_file_alias_is_refused(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        outside = self.root / 'shared.srm'
        outside.write_bytes(b'untouched')
        (profile / 'Saves' / 'oos168x.srm').symlink_to(outside)
        with self.assertRaisesRegex(ValueError, 'file aliases'):
            self.prepare(fresh=False)
        self.assertEqual(outside.read_bytes(), b'untouched')

    def test_unavailable_directory_apis_refuse_before_writes(self):
        with mock.patch.object(session.os, 'supports_dir_fd', set()):
            with self.assertRaisesRegex(ValueError, 'Anchored directory operations'):
                self.prepare()
        self.assertEqual(list(self.profiles.iterdir()), [])

    def test_profile_swap_cannot_redirect_reservation_or_settings_writes(self):
        outside = self.root / 'shared-profile'
        outside.mkdir(mode=0o700)
        (outside / 'settings.json').write_bytes(b'shared settings untouched')
        moved = self.root / 'moved-private-profile'
        original_open = session._open_directory_at
        def swap_after_profile_open(parent_fd, name, **kwargs):
            fd = original_open(parent_fd, name, **kwargs)
            if name.startswith('yaze-') and kwargs.get('private'):
                profile = self.profiles / name
                profile.rename(moved)
                profile.symlink_to(outside)
            return fd
        with mock.patch.object(session, '_open_directory_at', side_effect=swap_after_profile_open):
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                self.prepare()
        self.assertEqual({p.name for p in outside.iterdir()}, {'settings.json'})
        self.assertEqual((outside / 'settings.json').read_bytes(), b'shared settings untouched')
        self.assertTrue((moved / '.yaze-session' / 'owner.json').exists())
        self.assertTrue((moved / 'settings.json').exists())

    def test_root_swap_cannot_redirect_profile_creation(self):
        outside = self.root / 'shared-root'
        outside.mkdir(mode=0o700)
        (outside / 'untouched').write_bytes(b'shared root untouched')
        moved = self.root / 'moved-private-root'
        original_open = session._open_private_root
        def swap_after_root_open(path):
            fd = original_open(path)
            self.profiles.rename(moved)
            self.profiles.symlink_to(outside)
            return fd
        with mock.patch.object(session, '_open_private_root', side_effect=swap_after_root_open):
            with self.assertRaisesRegex(ValueError, 'canonical'):
                self.prepare()
        self.assertEqual({p.name for p in outside.iterdir()}, {'untouched'})
        self.assertEqual((outside / 'untouched').read_bytes(), b'shared root untouched')
        self.assertEqual(len(list(moved.iterdir())), 1)

    def test_lease_swap_cannot_redirect_owner_write(self):
        outside = self.root / 'shared-lease'
        outside.mkdir(mode=0o700)
        (outside / 'owner.json').write_bytes(b'shared owner untouched')
        moved = self.root / 'moved-private-lease'
        original_write = session._write_new_at
        def swap_before_owner_write(directory_fd, name, data):
            if name == 'owner.json':
                profile = next(self.profiles.iterdir())
                lease = profile / '.yaze-session'
                lease.rename(moved)
                lease.symlink_to(outside)
            original_write(directory_fd, name, data)
        with mock.patch.object(session, '_write_new_at', side_effect=swap_before_owner_write):
            with self.assertRaisesRegex(ValueError, 'file aliases'):
                self.prepare()
        self.assertEqual((outside / 'owner.json').read_bytes(), b'shared owner untouched')
        self.assertTrue((moved / 'owner.json').exists())

    def test_profile_swap_during_cancel_cannot_remove_shared_marker(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        outside = self.root / 'shared-profile'
        outside.mkdir(mode=0o700)
        (outside / '.yaze-session').mkdir(mode=0o700)
        shared_owner = outside / '.yaze-session' / 'owner.json'
        shared_owner.write_bytes(b'shared owner untouched')
        moved = self.root / 'moved-private-profile'
        original_unlink = os.unlink
        def swap_before_unlink(name, *, dir_fd=None):
            self.assertEqual(name, 'owner.json')
            self.assertEqual(dir_fd, prepared._lease_fd)
            profile.rename(moved)
            profile.symlink_to(outside)
            return original_unlink(name, dir_fd=dir_fd)
        with mock.patch.object(session.os, 'unlink', side_effect=swap_before_unlink):
            with self.assertRaisesRegex(ValueError, 'identity changed'):
                prepared.cancel_before_launch()
        self.assertEqual(shared_owner.read_bytes(), b'shared owner untouched')
        self.assertTrue((moved / '.yaze-session').is_dir())

    def test_unreadable_subtree_fails_closed_instead_of_skipping(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        unreadable = profile / 'Saves' / 'unreadable'
        unreadable.mkdir(mode=0o700)
        (unreadable / 'hidden-alias').symlink_to(self.root / 'outside-save')
        unreadable.chmod(0)
        try:
            try:
                os.listdir(unreadable)
            except PermissionError:
                pass
            else:
                self.skipTest('Host privileges can read mode-000 directory')
            with self.assertRaises((ValueError, PermissionError)):
                self.prepare(fresh=False)
            self.assertTrue((profile / '.yaze-session' / 'owner.json').is_file())
        finally:
            unreadable.chmod(0o700)

    def test_subtree_swap_during_traversal_fails_without_following_alias(self):
        prepared = self.prepare()
        profile = Path(prepared.plan.profile_path)
        prepared.cancel_before_launch()
        subtree = profile / 'Saves' / 'nested'
        subtree.mkdir(mode=0o700)
        outside = self.root / 'outside-subtree'
        outside.mkdir(mode=0o700)
        (outside / 'untouched').write_bytes(b'outside')
        moved = self.root / 'moved-subtree'
        original_open = session._open_directory_at
        def swap_after_open(parent_fd, name, **kwargs):
            fd = original_open(parent_fd, name, **kwargs)
            if name == 'nested':
                subtree.rename(moved)
                subtree.symlink_to(outside)
            return fd
        with mock.patch.object(session, '_open_directory_at', side_effect=swap_after_open):
            with self.assertRaisesRegex(ValueError, 'changed during traversal'):
                self.prepare(fresh=False)
        self.assertEqual((outside / 'untouched').read_bytes(), b'outside')

    def test_production_gate_refuses_without_spawning(self):
        prepared = self.prepare()
        with mock.patch('subprocess.Popen') as popen:
            with self.assertRaisesRegex(RuntimeError, 'No reviewed Mesen'):
                launch_dedicated_mesen(prepared)
        popen.assert_not_called()
        prepared.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS synthetic process lifecycle')
    def test_synthetic_owned_child_handshake_and_confirmed_cleanup(self):
        prepared = self.prepare()
        result = _run_synthetic_lifecycle(prepared)
        self.assertEqual(result['peer_pid'], result['pid'])
        self.assertEqual(result['exit_code'], 0)
        with self.assertRaises(ProcessLookupError):
            os.kill(result['pid'], 0)
        self.assertFalse(Path(prepared.plan.socket_path).parent.exists())
        self.assertFalse((Path(prepared.plan.profile_path) / '.yaze-session').exists())
        next_session = self.prepare(fresh=False)
        self.assertEqual(next_session.plan.profile_path, prepared.plan.profile_path)
        next_session.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS synthetic process lifecycle')
    def test_synthetic_error_retains_marker_after_owned_child_cleanup(self):
        prepared = self.prepare()
        observed = []
        def fail_after_peer(_plan, pid):
            observed.append(pid)
            raise RuntimeError('fixture interruption')
        with self.assertRaisesRegex(RuntimeError, 'fixture interruption'):
            _run_synthetic_lifecycle(prepared, after_peer_check=fail_after_peer)
        self.assertEqual(len(observed), 1)
        with self.assertRaises(ProcessLookupError):
            os.kill(observed[0], 0)
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())
        with self.assertRaisesRegex(ValueError, 'Child exit is unproven'):
            prepared.cancel_before_launch()
        socket_path = Path(prepared.plan.socket_path)
        socket_path.unlink()
        socket_path.parent.rmdir()

    def test_environment_is_explicit_and_does_not_mutate_parent(self):
        prepared = self.prepare()
        # Pure envelope fixture only. Production preparation has no endpoint.
        plan = replace(prepared.plan, socket_path=str(self.root / 'fixture.sock'))
        inherited = {'HOME': str(self.root), 'MESEN2_HOME': '/shared/profile',
                     'MESEN2_YAZE_RUN_TOKEN': 'old', 'DYLD_INSERT_LIBRARIES': 'bad',
                     'MESEN2_YAZE_PRIVATE_DESKTOP': '1',
                     'DOTNET_STARTUP_HOOKS': 'bad', 'PATH': '/usr/bin:/bin'}
        before = inherited.copy()
        environment = plan.child_environment(inherited)
        self.assertEqual(inherited, before)
        self.assertEqual(environment['MESEN2_HOME'], plan.profile_path)
        self.assertEqual(environment['MESEN2_YAZE_RUN_TOKEN'], plan.session_token)
        self.assertNotIn('DYLD_INSERT_LIBRARIES', environment)
        self.assertNotIn('DOTNET_STARTUP_HOOKS', environment)
        self.assertNotIn('MESEN2_YAZE_PRIVATE_DESKTOP', environment)
        prepared.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_guardian_peer_credentials_and_descriptor_custody(self):
        prepared = self.prepare()
        sentinel = self.root / 'outside-writable-sentinel'
        sentinel.write_bytes(b'outside untouched')
        # Deliberately inheritable, and explicitly loaned to the guardian. Its
        # child must still receive exactly 0/1/2/3, with no report/control pipe.
        fd = os.open(sentinel, os.O_WRONLY)
        os.set_inheritable(fd, True)
        try:
            result = session._run_synthetic_guardian(prepared, sentinel_fd=fd)
        finally:
            os.close(fd)
        self.assertEqual(sentinel.read_bytes(), b'outside untouched')
        self.assertTrue(result['quiescent'])
        self.assertTrue(result['success'])
        self.assertEqual(result['child_exit'], 0)
        child_log = next(Path(prepared.plan.profile_path).glob('socketpair-*-child.log'))
        records = [json.loads(line) for line in child_log.read_text().splitlines()]
        child = records[0]['checked']
        self.assertEqual(child['pid'], result['child_pid'])
        self.assertEqual(child['ppid'], result['guardian_pid'])
        self.assertEqual(child['peer_pid'], result['guardian_pid'])
        # Initial peer credentials reflect the creator; writes can refresh them.
        # Neither sample authenticates an arbitrary peer.
        self.assertEqual(result['guardian_peer_pid'], result['guardian_pid'])
        self.assertNotEqual(result['guardian_peer_pid'], result['child_pid'])
        self.assertEqual(result['guardian_peer_pid_after_child_reply'], result['child_pid'])
        self.assertEqual(child['sid'], child['pid'])
        self.assertEqual(child['pgid'], child['pid'])
        self.assertEqual(result['ready'], {'event': 'YAZE_DIAGNOSTIC_CHANNEL_READY',
                                          'version': 1, 'pid': child['pid']})
        self.assertEqual(result['ping'], {'success': True, 'data': 'PONG'})
        self.assertEqual(result['identity'], {'success': True, 'data': {
            'kind': 'snes_prg_rom', 'size': len(self.rom_bytes),
            'sha1': hashlib.sha1(self.rom_bytes).hexdigest(),
            'session': prepared.plan.session_token, 'frameCount': 0}})
        self.assertNotIn('child', result)
        self.assertEqual([row['command'] for row in records if 'command' in row],
                         ['PING', 'LOADED_ROM_IDENTITY'])
        descriptors = child['descriptors']
        self.assertEqual([entry['fd'] for entry in descriptors], [0, 1, 2, 3])
        self.assertTrue(stat.S_ISCHR(descriptors[0]['mode']))
        self.assertEqual(descriptors[0]['access'], os.O_RDONLY)
        for descriptor in descriptors[1:3]:
            self.assertTrue(stat.S_ISREG(descriptor['mode']))
            self.assertEqual(descriptor['access'], os.O_WRONLY)
            self.assertEqual(descriptor['inode'], child_log.stat().st_ino)
        self.assertTrue(stat.S_ISSOCK(descriptors[3]['mode']))
        self.assertFalse((Path(prepared.plan.profile_path) / '.yaze-session').exists())
        print('SOCKETPAIR_OBSERVATION ' + json.dumps(result, sort_keys=True))
        print('CHILD_LOG_DIAGNOSTICS ' + json.dumps(child, sort_keys=True))

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_ready_mismatch_refuses_before_ping(self):
        for scenario in ('ready-pid', 'ready-version', 'ready-extra'):
            with self.subTest(scenario=scenario):
                self.project = self.root / (scenario + '.yaze')
                self.project.write_bytes(b'fixture')
                prepared = self.prepare()
                with self.assertRaisesRegex(session.SyntheticGuardianError, 'channel readiness mismatch') as caught:
                    session._run_synthetic_guardian(prepared, scenario=scenario)
                self.assertTrue(caught.exception.observation['quiescent'])
                child_log = next(Path(prepared.plan.profile_path).glob('socketpair-*-child.log'))
                records = [json.loads(line) for line in child_log.read_text().splitlines()]
                self.assertIn('checked', records[0])
                self.assertFalse(any('command' in row for row in records))
                self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_legacy_ping_and_invalid_restricted_frame_count_refuse(self):
        for scenario in ('legacy-ping', 'frame-count-missing', 'frame-count-bool', 'frame-count-range'):
            with self.subTest(scenario=scenario):
                self.project = self.root / (scenario + '.yaze')
                self.project.write_bytes(b'fixture')
                prepared = self.prepare()
                with self.assertRaises(session.SyntheticGuardianError) as caught:
                    session._run_synthetic_guardian(prepared, scenario=scenario)
                result = caught.exception.observation
                self.assertTrue(result['quiescent'], result)
                self.assertFalse(result['success'])
                if scenario != 'legacy-ping':
                    self.assertIn('frameCount is invalid', result['error'])
                child_log = next(Path(prepared.plan.profile_path).glob('socketpair-*-child.log'))
                records = [json.loads(line) for line in child_log.read_text().splitlines()]
                expected = ['PING'] if scenario == 'legacy-ping' else ['PING', 'LOADED_ROM_IDENTITY']
                self.assertEqual([row['command'] for row in records if 'command' in row], expected)
                self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_frame_count_is_recorded_not_a_zero_work_assertion(self):
        prepared = self.prepare()
        result = session._run_synthetic_guardian(prepared, scenario='frame-count-advanced')
        self.assertTrue(result['success'])
        self.assertEqual(result['identity']['data']['frameCount'], 7)
        # Synthetic protocol value only; no emulator/PPU/CPU actually ran.
        self.assertFalse((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_invalid_peer_and_fd_refuse_before_read(self):
        for scenario in ('forwarded-peer', 'missing-fd', 'wrong-fd'):
            with self.subTest(scenario=scenario):
                # Each retained failure needs its own private project/profile.
                self.project = self.root / (scenario + '.yaze')
                self.project.write_bytes(b'fixture')
                prepared = self.prepare()
                with self.assertRaises(session.SyntheticGuardianError) as caught:
                    session._run_synthetic_guardian(prepared, scenario=scenario)
                result = caught.exception.observation
                self.assertTrue(result['quiescent'], result)
                self.assertFalse(result['success'])
                child_log = next(Path(prepared.plan.profile_path).glob('socketpair-*-child.log'))
                refusal = json.loads(child_log.read_text())
                self.assertIn('refused', refusal)
                self.assertEqual(refusal['commands_read'], 0)
                if scenario == 'forwarded-peer':
                    self.assertIn('Control peer differs', refusal['refused'])
                    self.assertEqual(result['guardian_peer_pid'], os.getpid())
                    self.assertEqual(refusal['peer_pid'], os.getpid())
                    print('FORWARDED_PEER_REFUSAL ' + json.dumps(
                        {'supervisor_pid': os.getpid(), 'result': result, 'refusal': refusal},
                        sort_keys=True))
                self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())
                with self.assertRaisesRegex(ValueError, 'Child exit is unproven'):
                    prepared.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_identity_timeout_and_cancel_keep_marker(self):
        for scenario in ('identity-mismatch', 'timeout', 'cancel-before-run'):
            with self.subTest(scenario=scenario):
                self.project = self.root / (scenario + '.yaze')
                self.project.write_bytes(b'fixture')
                prepared = self.prepare()
                with self.assertRaises(session.SyntheticGuardianError) as caught:
                    session._run_synthetic_guardian(prepared, scenario=scenario, timeout=1)
                result = caught.exception.observation
                self.assertTrue(result['quiescent'], result)
                self.assertFalse(result['success'])
                if scenario == 'identity-mismatch':
                    self.assertIn('loaded identity mismatch', result['error'])
                elif scenario == 'timeout':
                    self.assertIn('deadline exceeded', result['error'])
                else:
                    self.assertIn('cancelled', result['error'])
                    child_log = next(Path(prepared.plan.profile_path).glob('socketpair-*-child.log'))
                    self.assertEqual(child_log.read_bytes(), b'')
                self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_unproven_guardian_report_keeps_marker(self):
        prepared = self.prepare()
        with self.assertRaisesRegex(session.SyntheticGuardianError, 'closed before reply'):
            session._run_synthetic_guardian(prepared, scenario='uncertain-report')
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())
        with self.assertRaisesRegex(ValueError, 'Child exit is unproven'):
            prepared.cancel_before_launch()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_uncertain_quiescence_keeps_marker(self):
        prepared = self.prepare()
        with self.assertRaises(session.SyntheticGuardianError) as caught:
            session._run_synthetic_guardian(prepared, scenario='uncertain-quiescence')
        result = caught.exception.observation
        self.assertFalse(result['success'])
        self.assertFalse(result['quiescent'])
        self.assertIn('uncertain quiescence', result['error'])
        self.assertTrue((Path(prepared.plan.profile_path) / '.yaze-session').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_supervisor_death_and_term_do_not_leak_liveness_writer(self):
        for termination in (signal.SIGKILL, signal.SIGTERM):
            with self.subTest(signal=termination):
                self.project = self.root / (str(int(termination)) + '.yaze')
                self.project.write_bytes(b'fixture')
                publication = self.root / (str(int(termination)) + '-spawn.json')
                supervisor_log = self.root / (str(int(termination)) + '-supervisor.log')
                module_dir = str(Path(session.__file__).resolve().parent)
                build_dir = str(Path(module_dir).parent / 'Build')
                program = ('import sys; sys.path[:0]=' + repr([module_dir, build_dir]) + '\n'
                           'import yaze_dedicated_session as s\n'
                           'from pathlib import Path\n'
                           'import json\n'
                           'p=s.prepare_session(project_path=Path(' + repr(str(self.project)) + '),'
                           'rom_path=Path(' + repr(str(self.rom)) + '),'
                           'verified_rom_bytes=bytes(0x400000),'
                           'profiles_root=Path(' + repr(str(self.profiles)) + '),'
                           'settings_bytes=' + repr(self.settings) + ')\n'
                           'def published(value):\n'
                           '    value["profile"]=p.plan.profile_path\n'
                           '    Path(' + repr(str(publication)) + ').write_text(json.dumps(value))\n'
                           's._run_synthetic_guardian(p,scenario="timeout",timeout=6,after_spawn=published)\n')
                with supervisor_log.open('wb') as stream:
                    process = subprocess.Popen([str(session._socketpair_interpreter()), '-I', '-S', '-B',
                                                '-c', program], stdin=subprocess.DEVNULL,
                                               stdout=stream, stderr=stream, close_fds=True,
                                               start_new_session=True,
                                               env={'PATH': '/usr/bin:/bin', 'LANG': 'C'})
                    deadline = time.monotonic() + 5
                    observation = None
                    checked = False
                    try:
                        while time.monotonic() < deadline:
                            if publication.exists():
                                try:
                                    observation = json.loads(publication.read_text())
                                except json.JSONDecodeError:
                                    continue
                                logs = list(Path(observation['profile']).glob('socketpair-*-child.log'))
                                if logs and 'checked' in logs[0].read_text():
                                    checked = True
                                    break
                            time.sleep(.01)
                        # Only this unreaped direct fixture PID may be signaled.
                        os.kill(process.pid, termination)
                        code = process.wait(timeout=10)
                        self.assertTrue(checked, supervisor_log.read_text())
                    finally:
                        if process.returncode is None:
                            os.kill(process.pid, signal.SIGKILL)
                            process.wait(timeout=10)
                self.assertEqual(code, -signal.SIGKILL if termination == signal.SIGKILL else 1)
                profile = Path(observation['profile'])
                guardian_log = next(profile.glob('socketpair-*-guardian.log'))
                result = None
                deadline = time.monotonic() + 7
                while time.monotonic() < deadline:
                    for line in guardian_log.read_text().splitlines():
                        try:
                            candidate = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if candidate.get('event') == 'result':
                            result = candidate
                    if result is not None:
                        break
                    time.sleep(.01)
                self.assertIsNotNone(result, guardian_log.read_text())
                self.assertTrue(result['quiescent'], result)
                self.assertFalse(result['success'])
                self.assertIn('liveness pipe reached EOF', result['error'])
                self.assertTrue((profile / '.yaze-session' / 'owner.json').exists())
                # Observation only after reap: never signal a reusable identity.
                with self.assertRaises(ProcessLookupError):
                    os.kill(result['child_pid'], 0)
                print('SUPERVISOR_LOSS_OBSERVATION ' + json.dumps(result, sort_keys=True))

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS socketpair guardian fixture')
    def test_socketpair_success_cannot_release_changed_marker(self):
        prepared = self.prepare()
        owner = Path(prepared.plan.profile_path) / '.yaze-session' / 'owner.json'
        def change_owner(_observation):
            owner.write_bytes(b'changed private fixture owner')
        with self.assertRaisesRegex(ValueError, 'identity changed'):
            session._run_synthetic_guardian(prepared, after_spawn=change_owner)
        self.assertEqual(owner.read_bytes(), b'changed private fixture owner')
        self.assertTrue(prepared._launch_started)


if __name__ == '__main__':
    unittest.main()
