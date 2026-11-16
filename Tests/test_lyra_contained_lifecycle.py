"""Exercise real process containment against synthetic Build sentinels."""
import importlib.util
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import threading
import time
from types import SimpleNamespace
import unittest
from unittest import mock

import lyra_process_containment as containment

if sys.platform == 'darwin':
    import lyra_macos_process_group as macos


def selection_module():
    # Ordinary lock lifecycles need only the transfer module's strict JSON
    # parser; no transfer, ROM or project publication is used in these tests.
    path = Path(containment.__file__).with_name('lyra_build_selection.py')
    spec = importlib.util.spec_from_file_location('lyra_selection_containment_fixture', path)
    module = importlib.util.module_from_spec(spec)
    with mock.patch.dict(sys.modules, {'lyra_current_transfer': SimpleNamespace(_json=json.loads)}):
        spec.loader.exec_module(module)
    return module


class ContainedLifecycleTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lyra-contained-lifecycle-')
        self.root = Path(self.temp.name).resolve()
        self.engine = self.root / 'engine'
        self.engine.mkdir()
        self.project = self.root / 'project.yaze'
        self.project.write_text('[project]\nname=fixture\n')
        self.request = self.root / 'request.json'
        self.request.write_text('{}')
        self.candidate = (Path(str(self.project) + '.lyra-build-output')
                          / ('lyra-' + '1' * 32) / 'oos168x.sfc')
        self.candidate.parent.mkdir(parents=True, exist_ok=True)
        self.selection = selection_module()
        # Existing staged mocks exercise the Windows job-object contract even
        # when these portable controls run on a Mac. Darwin controls opt in below.
        self.staged_platform = mock.patch.object(self.selection, 'platform', 'win32')
        self.staged_platform.start()
        self.addCleanup(self.staged_platform.stop)

    def tearDown(self):
        self.temp.cleanup()

    def test_generated_output_is_project_bound_and_outside_engine_roms(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        try:
            request, candidate = session.generated_paths()
            self.assertEqual(candidate, Path(str(self.project) + '.lyra-build-output')
                             / ('lyra-' + session.build_id) / 'oos168x.sfc')
            self.assertFalse(candidate.is_relative_to(self.engine / 'Roms'))
            self.assertEqual(request.name, 'request.json')
            legacy = self.engine / 'Roms' / 'generation-1' / 'oos168x.sfc'
            with self.assertRaisesRegex(ValueError, 'fresh canonical generation'):
                session._child_environment({}, request=self.request, candidate=legacy)
            foreign = (Path(str(self.root / 'other.yaze') + '.lyra-build-output')
                       / ('lyra-' + '1' * 32) / 'oos168x.sfc')
            with self.assertRaisesRegex(ValueError, 'fresh canonical generation'):
                session._child_environment({}, request=self.request, candidate=foreign)
        finally:
            session.release()

    def test_generated_output_refuses_symlinked_private_root(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        output_root = Path(str(self.project) + '.lyra-build-output')
        # The fixture's regular root was created in setUp for explicit tests.
        import shutil
        shutil.rmtree(output_root)
        try:
            try:
                output_root.symlink_to(self.root, target_is_directory=True)
            except OSError as error:
                self.skipTest(f'symlink unavailable: {error}')
            with self.assertRaisesRegex(ValueError, 'Private Build output'):
                session.generated_paths()
        finally:
            session.release()

    def test_project_inside_engine_roms_cannot_make_private_output_there(self):
        project = self.engine / 'Roms' / 'nested' / 'project.yaze'
        project.parent.mkdir(parents=True)
        project.write_text('[project]\nname=fixture\n')
        session = self.selection.begin_attempt(project, self.engine)
        try:
            with self.assertRaisesRegex(ValueError, 'Private Build output'):
                session.generated_paths()
        finally:
            session.release()

    def test_selected_child_environment_is_bound_without_inherited_selection(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        supplied = {'PATH': 'fixture-path', 'OOS_LYRA_PROJECT': '/foreign',
                    'OOS_LYRA_BUILD_ID': 'foreign-id',
                    'OOS_LYRA_REQUEST': '/explicit/request',
                    'OOS_LYRA_CANDIDATE': '/explicit/candidate',
                    'OOS_LYRA_BUILD_CONTEXT': 'foreign',
                    'oos_lyra_build_id': 'lowercase-foreign',
                    'PythonPycachePrefix': '/foreign/cache',
                    'pythonDontWriteBytecode': '',
                    'oos_Test_socket': '127.0.0.1:12345'}
        original = dict(supplied)
        try:
            with self.assertRaisesRegex(ValueError, 'explicit request and candidate'):
                session._child_environment(supplied)
            child = session._child_environment(supplied, request=self.request,
                                               candidate=self.candidate)
            self.assertEqual(supplied, original)
            self.assertEqual(child['OOS_LYRA_PROJECT'], str(self.project))
            self.assertEqual(child['OOS_LYRA_BUILD_ID'], session.build_id)
            self.assertEqual(child['OOS_LYRA_REQUEST'], str(self.request))
            self.assertEqual(child['OOS_LYRA_CANDIDATE'], str(self.candidate))
            self.assertNotIn('OOS_LYRA_BUILD_CONTEXT', child)
            self.assertNotIn('oos_lyra_build_id', child)
            self.assertEqual(child['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertFalse(any(key.upper() in ('PYTHONPYCACHEPREFIX', 'OOS_TEST_SOCKET') for key in child))
            self.assertNotIn('pythonDontWriteBytecode', child)
            with mock.patch.dict(os.environ, supplied):
                inherited = session._child_environment(None, request=self.request,
                                                       candidate=self.candidate)
            self.assertEqual(inherited['OOS_LYRA_REQUEST'], str(self.request))
            self.assertEqual(inherited['OOS_LYRA_CANDIDATE'], str(self.candidate))
            self.assertNotIn('oos_lyra_build_id', inherited)
            self.candidate.touch()
            with self.assertRaisesRegex(ValueError, 'fresh canonical generation'):
                session._child_environment(supplied, request=self.request,
                                           candidate=self.candidate)
            self.candidate.unlink()
        finally:
            session.release()
            Path(str(self.project) + '.lyra-build-latest.json').unlink(missing_ok=True)

        ordinary = self.selection.begin_project_build(self.project, self.engine)
        try:
            child = ordinary._child_environment(supplied)
            self.assertFalse(any(key.upper().startswith('OOS_LYRA_') for key in child))
            self.assertEqual(child['PATH'], 'fixture-path')
            for selection in ({'request': self.request}, {'candidate': self.candidate}):
                with self.subTest(selection=selection), \
                     self.assertRaisesRegex(ValueError, 'Ordinary Build cannot select'):
                    ordinary._child_environment(supplied, **selection)
        finally:
            ordinary.release()

        engine_only = self.selection.begin_engine_build(self.engine)
        try:
            child = engine_only._child_environment(supplied)
            self.assertFalse(any(key.upper().startswith('OOS_LYRA_') for key in child))
            for selection in ({'request': self.request}, {'candidate': self.candidate}):
                with self.subTest(selection=selection), \
                     self.assertRaisesRegex(ValueError, 'Ordinary Build cannot select'):
                    engine_only._child_environment(supplied, **selection)
        finally:
            engine_only.release()

    def test_publication_must_match_the_contained_child_selection(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        receipt = self.root / 'receipt.json'
        try:
            with mock.patch.object(containment, 'prepare_contained', return_value=()), \
                 mock.patch.object(containment, '_run_windows',
                                   return_value=containment.ContainedResult(0, False)):
                session.run_child(['fixture'], cwd=self.root, timeout=5,
                                  request=self.request, candidate=self.candidate)
            for request, candidate in ((self.root / 'other-request', self.candidate),
                                       (self.request, self.root / 'other-candidate')):
                with self.subTest(request=request, candidate=candidate), \
                     self.assertRaisesRegex(ValueError, 'must match the contained Build'):
                    session.publish(request, candidate, receipt)
        finally:
            session.release()
            Path(str(self.project) + '.lyra-build-latest.json').unlink(missing_ok=True)

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_selected_contained_child_receives_its_build_identity(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        output = self.root / 'child-identity.json'
        environment = dict(os.environ)
        environment.update(OOS_LYRA_PROJECT='/foreign', OOS_LYRA_BUILD_ID='stale',
                           OOS_LYRA_REQUEST='/explicit/request',
                           OOS_LYRA_CANDIDATE='/explicit/candidate',
                           OOS_LYRA_BUILD_CONTEXT='foreign')
        code = ('import json,os,pathlib; keys=' +
                repr(['OOS_LYRA_PROJECT', 'OOS_LYRA_BUILD_ID',
                      'OOS_LYRA_REQUEST', 'OOS_LYRA_CANDIDATE',
                      'OOS_LYRA_BUILD_CONTEXT']) +
                '; pathlib.Path(' + repr(str(output)) +
                ').write_text(json.dumps({k:os.environ.get(k) for k in keys}))')
        try:
            result = session.run_child([sys.executable, '-c', code], cwd=self.root,
                                       timeout=10, environment=environment,
                                       request=self.request, candidate=self.candidate)
            self.assertEqual(result, containment.ContainedResult(0, False))
            self.assertEqual(json.loads(output.read_text()), {
                'OOS_LYRA_PROJECT': str(self.project),
                'OOS_LYRA_BUILD_ID': session.build_id,
                'OOS_LYRA_REQUEST': str(self.request),
                'OOS_LYRA_CANDIDATE': str(self.candidate),
                'OOS_LYRA_BUILD_CONTEXT': None})
        finally:
            session.release()
            Path(str(self.project) + '.lyra-build-latest.json').unlink(missing_ok=True)

    def test_generated_preparation_and_build_share_locks_and_identity(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        self.assertEqual(request, candidate.parent / 'transfer' / 'request.json')
        self.assertFalse((self.engine / '.lyra-build-inputs').exists())
        calls = []
        def prepare(argv, *, cwd, timeout, environment):
            self.assertTrue((self.engine / '.lyra-build-engine.lock').exists())
            self.assertTrue(Path(str(self.project) + '.lyra-build-project.lock').exists())
            self.assertEqual(environment['OOS_LYRA_BUILD_ID'], session.build_id)
            self.assertEqual(environment['OOS_LYRA_REQUEST'], str(request))
            self.assertEqual(environment['OOS_LYRA_CANDIDATE'], str(candidate))
            self.assertNotIn('oos_lyra_build_id', environment)
            self.assertEqual(environment['PYTHONDONTWRITEBYTECODE'], '1')
            self.assertFalse(any(key.upper() in ('PYTHONPYCACHEPREFIX', 'OOS_TEST_SOCKET') for key in environment))
            return (argv, environment)
        def run(argv, environment):
            calls.append(argv[0])
            if argv[0] == 'prepare':
                request.parent.mkdir(parents=True)
                request.write_text('{}')
            else:
                candidate.parent.mkdir(parents=True, exist_ok=True)
                candidate.write_bytes(b'fixture')
            return containment.ContainedResult(0, False)
        def validate(actual_request, actual_candidate):
            self.assertEqual((actual_request, actual_candidate), (request, candidate))
            self.assertTrue(request.exists())
            self.assertFalse(candidate.exists())
            self.assertTrue((self.engine / '.lyra-build-engine.lock').exists())
            return {'PATH': 'fixture'}
        with mock.patch.object(containment, 'prepare_contained', side_effect=prepare), \
             mock.patch.object(containment, '_run_windows', side_effect=run):
            result = session.run_generated_build(['prepare'], ['build'], cwd=self.root, timeout=5,
                                                 environment={'oos_lyra_build_id': 'foreign',
                                                              'pythonpycacheprefix': '/foreign/cache',
                                                              'PyThOnDoNtWrItEbYtEcOdE': '',
                                                              'oos_test_socket': '127.0.0.1:12345'},
                                                 validate_prepared=validate)
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual(calls, ['prepare', 'build'])
        self.assertEqual(session._child_selection, (request, candidate))
        with self.assertRaisesRegex(ValueError, 'must match the contained Build'):
            session.publish(self.request, candidate, self.root / 'receipt.json')
        session.release()

    def test_generated_preparation_failure_never_starts_build(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        with mock.patch.object(containment, 'prepare_contained', return_value=()) as prepare, \
             mock.patch.object(containment, '_run_windows',
                               return_value=containment.ContainedResult(7, False)) as run:
            result = session.run_generated_build(['prepare'], ['build'], cwd=self.root, timeout=5,
                                                 environment={}, validate_prepared=mock.Mock())
        self.assertEqual(result, containment.ContainedResult(7, False))
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(run.call_count, 1)
        with self.assertRaisesRegex(ValueError, 'Failed or timed-out child'):
            session.publish(self.request, self.candidate, self.root / 'receipt.json')
        session.release()

    def test_selected_preparation_and_build_children_cannot_use_ambient_socket_or_cache(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        probe = self.root / 'child_probe.py'
        probe.write_text('''import os,socket,sys
import probe_dependency
for key,value in os.environ.items():
 if key.upper() == 'OOS_TEST_SOCKET' and value:
  host,port=value.split(':'); socket.create_connection((host,int(port))).close()
assert sys.dont_write_bytecode
assert not any(k.upper() in ('OOS_TEST_SOCKET','PYTHONPYCACHEPREFIX') for k in os.environ)
''')
        (self.root / 'probe_dependency.py').write_text('value = 1\n')
        with socket.socket() as listener:
            listener.bind(('127.0.0.1', 0))
            listener.listen()
            listener.settimeout(0.05)
            address = '%s:%d' % listener.getsockname()
            hostile = {key: value for key, value in os.environ.items()
                       if key.upper() not in ('PYTHONDONTWRITEBYTECODE', 'PYTHONPYCACHEPREFIX', 'OOS_TEST_SOCKET')}
            hostile.update(PythonPycachePrefix=str(self.root / 'forbidden-cache'),
                           pythonDontWriteBytecode='', OoS_TeSt_SoCkEt=address,
                           OOS_TEST_SOCKET=address)
            observed = []

            def run(argv, environment):
                result = subprocess.run([sys.executable, str(probe)], cwd=self.root,
                                        env=environment, capture_output=True, text=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                observed.append(argv[0])
                if argv[0] == 'prepare':
                    request.parent.mkdir(parents=True)
                    request.write_text('{}')
                else:
                    candidate.write_bytes(b'fixture')
                return containment.ContainedResult(0, False)

            try:
                with mock.patch.object(containment, 'prepare_contained',
                                       side_effect=lambda argv, **kw: (argv, kw['environment'])), \
                     mock.patch.object(containment, '_run_windows', side_effect=run):
                    result = session.run_generated_build(['prepare'], ['build'], cwd=self.root,
                        timeout=10, environment=hostile, validate_prepared=lambda r, c: hostile)
                self.assertEqual(result.exit_code, 0)
                self.assertEqual(observed, ['prepare', 'build'])
                self.assertFalse(list(self.root.rglob('__pycache__')))
                self.assertFalse((self.root / 'forbidden-cache').exists())
                with self.assertRaises(TimeoutError):
                    listener.accept()
            finally:
                session.release()

    def test_generated_validation_that_exhausts_timeout_never_starts_build(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        def first_job():
            request.parent.mkdir(parents=True)
            request.write_text('{}')
            return containment.ContainedResult(0, False)
        with mock.patch.object(containment, 'prepare_contained', return_value=()) as prepare, \
             mock.patch.object(containment, '_run_windows', side_effect=first_job) as run, \
             mock.patch('time.monotonic', side_effect=[0, .5, 6]):
            result = session.run_generated_build(['prepare'], ['build'], cwd=self.root, timeout=5,
                                                 environment={}, validate_prepared=lambda r, c: {})
        self.assertEqual(result, containment.ContainedResult(None, True))
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(run.call_count, 1)
        session.release()

    def test_generated_validation_failure_never_starts_build(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        with mock.patch.object(containment, 'prepare_contained', return_value=()) as prepare, \
             mock.patch.object(containment, '_run_windows',
                               return_value=containment.ContainedResult(0, False)) as run:
            result = session.run_generated_build(['prepare'], ['build'], cwd=self.root, timeout=5,
                                                 environment={},
                                                 validate_prepared=mock.Mock(side_effect=ValueError('stale Save')))
        self.assertEqual(result, containment.ContainedResult(2, False))
        self.assertEqual(prepare.call_count, 1)
        self.assertEqual(run.call_count, 1)
        session.release()

    def test_generated_selection_refuses_existing_or_symlinked_directory(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        request.parent.mkdir(parents=True)
        with self.assertRaisesRegex(ValueError, 'new and canonical'):
            session.generated_paths()
        request.parent.rmdir()
        request.parent.parent.rmdir()
        try:
            request.parent.parent.symlink_to(self.root, target_is_directory=True)
        except OSError as error:
            session.release()
            self.skipTest(f'directory symlinks unavailable: {error}')
        with self.assertRaisesRegex(ValueError, 'new and canonical|Private Build output'):
            session.generated_paths()
        session.release()

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_generated_jobs_execute_owned_children_in_sequence(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        prepare_code = ('import os,pathlib; p=pathlib.Path(os.environ["OOS_LYRA_REQUEST"]); '
                        'p.parent.mkdir(parents=True); p.write_text("prepared")')
        build_code = ('import os,pathlib; p=pathlib.Path(os.environ["OOS_LYRA_CANDIDATE"]); '
                      'p.parent.mkdir(parents=True, exist_ok=True); p.write_text(os.environ["OOS_LYRA_BUILD_ID"])')
        result = session.run_generated_build([sys.executable, '-c', prepare_code],
                                             [sys.executable, '-c', build_code],
                                             cwd=self.root, timeout=10, environment=dict(os.environ),
                                             validate_prepared=lambda r, c: dict(os.environ))
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual(request.read_text(), 'prepared')
        self.assertEqual(candidate.read_text(), session.build_id)
        session.release()

    def macos_stage_commands(self):
        """Fixed disposable programs; neither imports Build code or game data."""
        prefix = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-c']
        locks = [str(self.engine / '.lyra-build-engine.lock'),
                 str(self.project) + '.lyra-build-project.lock']
        common = ('import json,os,pathlib; '
                  f'assert all(pathlib.Path(p).is_file() for p in {locks!r}); '
                  'assert "OOS_TEST_SOCKET" not in os.environ; '
                  'assert "BASH_ENV" not in os.environ; '
                  'assert "PYTHONPYCACHEPREFIX" not in os.environ; '
                  'request=pathlib.Path(os.environ["OOS_LYRA_REQUEST"]); '
                  'candidate=pathlib.Path(os.environ["OOS_LYRA_CANDIDATE"]); '
                  'identity={key:os.environ[key] for key in '
                  '["OOS_LYRA_PROJECT","OOS_LYRA_REQUEST",'
                  '"OOS_LYRA_CANDIDATE","OOS_LYRA_BUILD_ID"]}; ')
        prepare = prefix + [common + 'request.parent.mkdir(parents=True,exist_ok=True); '
                            'request.write_text(json.dumps(identity))']
        build = prefix + [common + 'assert json.loads(request.read_text())==identity; '
                          'assert not candidate.exists(); '
                          'candidate.write_text(json.dumps(identity))']
        return prepare, build

    def admit_macos_fixture(self, commands):
        def admit(argv, *, cwd, timeout):
            self.assertIn(argv, commands)
            self.assertEqual(cwd, self.root)
            self.assertGreater(timeout, 0)
            self.assertTrue((self.engine / '.lyra-build-engine.lock').is_file())
            self.assertTrue(Path(str(self.project) + '.lyra-build-project.lock').is_file())
            return argv, cwd, timeout
        return mock.patch.object(macos, 'prepare_oracle_build', side_effect=admit)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_generated_stages_refuse_before_any_child(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        prepare, build = self.macos_stage_commands()
        request, candidate = session.generated_paths()
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             mock.patch.object(macos, '_run_fixture_group') as run:
            with self.assertRaisesRegex(containment.ContainmentUnavailable, 'No audited'):
                session.run_generated_build(prepare, build, cwd=self.root, timeout=5,
                                            environment={}, validate_prepared=mock.Mock())
            run.assert_not_called()
        self.assertFalse(request.exists() or candidate.exists())
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_disposable_stages_share_attempt_and_wait_for_exit(self):
        for automatic in (True, False):
            with self.subTest(automatic=automatic):
                session = self.selection.begin_attempt(self.project, self.engine)
                prepare, build = self.macos_stage_commands()
                request, candidate = (session.generated_paths() if automatic else
                                      (self.request, self.candidate))
                def validate(actual_request, actual_candidate):
                    self.assertEqual((actual_request, actual_candidate), (request, candidate))
                    self.assertEqual(json.loads(request.read_text())['OOS_LYRA_BUILD_ID'],
                                     session.build_id)
                    self.assertFalse(candidate.exists())
                    return {'BASH_ENV': '/unowned', 'OOS_TEST_SOCKET': '/unowned',
                            'PYTHONPYCACHEPREFIX': '/unowned'}
                args = (prepare, build) if automatic else (request, candidate, prepare, build)
                runner = session.run_generated_build if automatic else session.run_selected_build
                with mock.patch.object(self.selection, 'platform', 'darwin'), \
                     self.admit_macos_fixture([prepare, build]):
                    result = runner(*args, cwd=self.root, timeout=8, environment={},
                                    validate_prepared=validate)
                self.assertEqual(result, containment.ContainedResult(0, False))
                self.assertEqual(candidate.read_text(), request.read_text())
                self.assertFalse(session._child_started)
                self.assertTrue(session._child_completed)
                self.assertFalse(session._child_failed)
                self.assertEqual(session._child_selection, (request, candidate))
                # Successful child exit does not publish a selector by itself.
                selector = json.loads(Path(str(self.project) + '.lyra-build-latest.json').read_text())
                self.assertEqual(selector['kind'], self.selection.PENDING_KIND)
                session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_preparation_failure_and_timeout_do_not_start_build(self):
        for body, timeout, expected in (
                ('raise SystemExit(6)', 5, containment.ContainedResult(6, False)),
                ('import time; time.sleep(2)', .15, containment.ContainedResult(None, True))):
            with self.subTest(body=body):
                session = self.selection.begin_attempt(self.project, self.engine)
                request, candidate = session.generated_paths()
                _, build = self.macos_stage_commands()
                prepare = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-c', body]
                validate = mock.Mock()
                with mock.patch.object(self.selection, 'platform', 'darwin'), \
                     self.admit_macos_fixture([prepare]) as gate:
                    result = session.run_generated_build(prepare, build, cwd=self.root,
                        timeout=timeout, environment={}, validate_prepared=validate)
                self.assertEqual(result, expected)
                self.assertEqual(gate.call_count, 1)
                validate.assert_not_called()
                self.assertFalse(request.exists() or candidate.exists())
                session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_changed_save_between_stages_prevents_build(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        prepare, build = self.macos_stage_commands()
        def stale_save(*_):
            self.project.write_text('[project]\nname=changed\n')
            raise ValueError('Saved project changed during Build preparation')
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             self.admit_macos_fixture([prepare]) as gate:
            result = session.run_generated_build(prepare, build, cwd=self.root, timeout=5,
                environment={}, validate_prepared=stale_save)
        self.assertEqual(result, containment.ContainedResult(2, False))
        self.assertEqual(gate.call_count, 1)
        self.assertTrue(request.exists())
        self.assertFalse(candidate.exists())
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_second_stage_admission_refusal_releases_settled_locks(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        prepare, build = self.macos_stage_commands()
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             mock.patch.object(macos, 'prepare_oracle_build', side_effect=[
                 (prepare, self.root, 5), containment.ContainmentUnavailable('Build graph unadmitted')]):
            with self.assertRaisesRegex(containment.ContainmentUnavailable, 'unadmitted'):
                session.run_generated_build(prepare, build, cwd=self.root, timeout=5,
                    environment={}, validate_prepared=lambda *_: {})
        self.assertTrue(request.exists())
        self.assertFalse(candidate.exists())
        session.release()
        self.assertFalse((self.engine / '.lyra-build-engine.lock').exists())
        self.assertFalse(Path(str(self.project) + '.lyra-build-project.lock').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_stages_share_timeout_including_parent_validation(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        # Use explicit selection because its request already exists. No child
        # runs under the fake clock; only deadline propagation is exercised.
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             self.admit_macos_fixture([['prepare'], ['build']]) as gate, \
             mock.patch.object(macos, '_run_fixture_group',
                               return_value=containment.ContainedResult(0, False)), \
             mock.patch('time.monotonic', side_effect=[100, 101, 103]):
            result = session.run_selected_build(self.request, self.candidate,
                ['prepare'], ['build'], cwd=self.root, timeout=5, environment={},
                validate_prepared=lambda *_: {})
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertEqual([call.kwargs['timeout'] for call in gate.call_args_list], [5, 2])
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_uncertain_second_stage_retains_both_sentinels(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             self.admit_macos_fixture([['prepare'], ['build']]), \
             mock.patch.object(macos, '_run_fixture_group', side_effect=[
                 containment.ContainedResult(0, False),
                 containment.ContainmentUncertain('guardian status unavailable')]):
            with self.assertRaisesRegex(containment.ContainmentUncertain, 'status unavailable'):
                session.run_selected_build(self.request, self.candidate,
                    ['prepare'], ['build'], cwd=self.root, timeout=5, environment={},
                    validate_prepared=lambda *_: {})
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()
        self.assertTrue((self.engine / '.lyra-build-engine.lock').is_file())
        self.assertTrue(Path(str(self.project) + '.lyra-build-project.lock').is_file())
        self.assertFalse(self.candidate.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_macos_late_sigterm_during_guardian_cleanup_prevents_second_stage(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        request, candidate = session.generated_paths()
        prepare, build = self.macos_stage_commands()
        real_popen = subprocess.Popen
        injected = []
        class GuardianProxy:
            def __init__(self, *args, **kwargs):
                self.child = real_popen(*args, **kwargs)
                self.waits = 0
            def __getattr__(self, name):
                return getattr(self.child, name)
            def wait(self, *args, **kwargs):
                self.waits += 1
                if self.waits == 2 and not injected:
                    # The first wait observes a completed guardian. Its second
                    # wait is finally cleanup, previously after choosing success.
                    # Invoke this thread's installed handler, never an OS signal.
                    handler = signal.getsignal(signal.SIGTERM)
                    if not callable(handler):
                        raise AssertionError('Guardian cancellation handler is not installed')
                    injected.append('finally')
                    handler(signal.SIGTERM, None)
                return self.child.wait(*args, **kwargs)
        with mock.patch.object(self.selection, 'platform', 'darwin'), \
             self.admit_macos_fixture([prepare, build]) as gate, \
             mock.patch.object(macos.subprocess, 'Popen', GuardianProxy):
            result = session.run_generated_build(prepare, build, cwd=self.root, timeout=8,
                environment={}, validate_prepared=lambda *_: {})
        self.assertEqual(injected, ['finally'])
        self.assertEqual(result, containment.ContainedResult(128 + signal.SIGTERM, False),
                         f'second_stage_output_exists={candidate.exists()}')
        self.assertEqual(gate.call_count, 1)
        self.assertTrue(request.exists())
        self.assertFalse(candidate.exists())
        session.release()

    def test_two_threads_cannot_start_the_same_lifecycle(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        start = threading.Barrier(3)
        outcomes = []

        def mark():
            start.wait()
            try:
                session.mark_child_started()
                outcomes.append('started')
            except ValueError:
                outcomes.append('refused')

        # Force the ownership check to yield, exposing the old check/set race.
        with mock.patch.object(session, '_check_owned', side_effect=lambda: time.sleep(.1)):
            threads = [threading.Thread(target=mark) for _ in range(2)]
            for thread in threads:
                thread.start()
            start.wait()
            for thread in threads:
                thread.join(timeout=5)
        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertCountEqual(outcomes, ['started', 'refused'])
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()

    @unittest.skipIf(os.name == 'nt', 'Windows supports contained children')
    def test_unsupported_platform_refuses_without_retaining_an_unstarted_lock(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        marker = self.root / 'not-launched'
        code = f'from pathlib import Path; Path({str(marker)!r}).write_text("bad")'
        with self.assertRaises(containment.ContainmentUnavailable):
            session.run_child([sys.executable, '-c', code], cwd=self.root, timeout=3)
        self.assertFalse(marker.exists())
        session.release()
        self.assertFalse((self.engine / '.lyra-build-engine.lock').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_unadmitted_macos_build_refuses_before_launch(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        marker = self.root / 'not-launched'
        code = f'from pathlib import Path; Path({str(marker)!r}).touch()'
        with self.assertRaisesRegex(containment.ContainmentUnavailable, 'No audited'):
            session.run_macos_audited_child([sys.executable, '-c', code], cwd=self.root, timeout=3)
        self.assertFalse(marker.exists())
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_fixture_admission_runs_macos_child_under_locks(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        marker = self.root / 'fixture-finished'
        code = f'from pathlib import Path; Path({str(marker)!r}).touch()'
        command = [sys.executable, '-c', code]
        with mock.patch.object(macos, 'prepare_oracle_build', return_value=(command, self.root, 5)):
            result = session.run_macos_audited_child(command, cwd=self.root, timeout=5)
        self.assertEqual(result, containment.ContainedResult(0, False))
        self.assertTrue(marker.exists())
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_uncertain_macos_group_retains_locks(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        command = [sys.executable, '-c', 'pass']
        with mock.patch.object(macos, 'prepare_oracle_build', return_value=(command, self.root, 5)):
            with mock.patch.object(macos, '_run_fixture_group',
                                   side_effect=containment.ContainmentUncertain('injected')):
                with self.assertRaises(containment.ContainmentUncertain):
                    session.run_macos_audited_child(command, cwd=self.root, timeout=5)
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()
        self.assertTrue((self.engine / '.lyra-build-engine.lock').exists())
        self.assertTrue(Path(str(self.project) + '.lyra-build-project.lock').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_real_child_keeps_locks_until_job_is_empty(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        ready = self.root / 'child-ready'
        code = f'import time; from pathlib import Path; Path({str(ready)!r}).write_text("ready"); time.sleep(.7)'
        outcome = []

        def run():
            try:
                outcome.append(session.run_child([sys.executable, '-c', code], cwd=self.root, timeout=10))
            except Exception as error:
                outcome.append(error)

        thread = threading.Thread(target=run)
        thread.start()
        try:
            deadline = time.monotonic() + 10
            while not ready.exists() and thread.is_alive() and time.monotonic() < deadline:
                time.sleep(.01)
            self.assertTrue(ready.exists(), 'contained child did not start')
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                self.selection.begin_engine_build(self.engine)
            with self.assertRaisesRegex(ValueError, 'uncertain child'):
                session.release()
        finally:
            thread.join(timeout=15)
        self.assertFalse(thread.is_alive())
        self.assertEqual(outcome, [containment.ContainedResult(0, False)])
        session.release()
        self.assertFalse((self.engine / '.lyra-build-engine.lock').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_failed_child_cannot_publish_but_can_release_after_cleanup(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        result = session.run_child([sys.executable, '-c', 'raise SystemExit(7)'],
                                   cwd=self.root, timeout=10,
                                   request=self.request, candidate=self.candidate)
        self.assertEqual(result, containment.ContainedResult(7, False))
        with self.assertRaisesRegex(ValueError, 'Failed or timed-out child'):
            session.publish(self.root / 'request', self.root / 'candidate', self.root / 'receipt')
        session.release()

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_timed_out_child_cannot_publish_after_confirmed_cleanup(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        result = session.run_child([sys.executable, '-c', 'import time; time.sleep(5)'],
                                   cwd=self.root, timeout=.3,
                                   request=self.request, candidate=self.candidate)
        self.assertEqual(result, containment.ContainedResult(None, True))
        with self.assertRaisesRegex(ValueError, 'Failed or timed-out child'):
            session.publish(self.root / 'request', self.root / 'candidate', self.root / 'receipt')
        session.release()

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_successful_child_can_publish_synthetic_selector(self):
        session = self.selection.begin_attempt(self.project, self.engine)
        result = session.run_child([sys.executable, '-c', 'pass'], cwd=self.root,
                                   timeout=10, request=self.request, candidate=self.candidate)
        self.assertEqual(result, containment.ContainedResult(0, False))
        request, candidate, receipt = self.request, self.candidate, self.root / 'receipt'
        candidate.write_text('synthetic candidate')
        receipt.write_text(json.dumps({'root': str(self.engine)}))
        selector = dict(kind=self.selection.KIND, project=str(self.project), generation=1,
                        operation_id='fixture', request=str(request), candidate=str(candidate),
                        build_receipt={'path': str(receipt), 'sha256': '0' * 64},
                        build_id=session.build_id)
        with mock.patch.object(self.selection, 'validate', return_value=selector):
            self.assertEqual(session.publish(request, candidate, receipt), selector)
        self.assertEqual(json.loads(Path(str(self.project) + '.lyra-build-latest.json').read_text()), selector)
        session.release()

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_rejected_executable_releases_unstarted_locks(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        invalid = self.root / 'not-an-executable.txt'
        invalid.write_text('not an executable')
        with self.assertRaises(containment.ContainmentUnavailable):
            session.run_child([str(invalid)], cwd=self.root, timeout=10)
        session.release()
        self.assertFalse((self.engine / '.lyra-build-engine.lock').exists())

    @unittest.skipUnless(os.name == 'nt', 'Windows job objects are required')
    def test_uncertain_containment_retains_locks(self):
        session = self.selection.begin_project_build(self.project, self.engine)
        with mock.patch.object(containment, '_run_windows', side_effect=containment.ContainmentUncertain('injected')):
            with self.assertRaises(containment.ContainmentUncertain):
                session.run_child([sys.executable, '-c', 'pass'], cwd=self.root, timeout=10)
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()
        self.assertTrue((self.engine / '.lyra-build-engine.lock').exists())
        self.assertTrue(Path(str(self.project) + '.lyra-build-project.lock').exists())


if __name__ == '__main__':
    unittest.main()
