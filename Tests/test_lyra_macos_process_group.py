"""Owned fixture coverage for unadmitted macOS process-group mechanics."""
import json
import hashlib
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import lyra_macos_process_group as group
from lyra_process_containment import ContainedResult, ContainmentUncertain, ContainmentUnavailable
from test_lyra_contained_lifecycle import selection_module


class MacProcessGroupTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='lyra-mac-group-')
        self.root = Path(self.temp.name).resolve()

    def tearDown(self):
        self.temp.cleanup()

    def run_fixture(self, code, timeout=10):
        return group._run_fixture_group([sys.executable, '-c', code], cwd=self.root, timeout=timeout)

    def test_other_platform_refuses_before_launch(self):
        marker = self.root / 'must-not-exist'
        with mock.patch.object(group.sys, 'platform', 'unsupported'):
            with self.assertRaises(ContainmentUnavailable):
                self.run_fixture(f'from pathlib import Path; Path({str(marker)!r}).touch()')
        self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_prelaunch_rejection_allows_release(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        session = selection_module().begin_project_build(project, engine)
        command = [str(self.root / 'missing-executable')]
        with mock.patch.object(group, 'prepare_oracle_build',
                               return_value=(command, self.root, 5)):
            with self.assertRaises(ContainmentUnavailable):
                session.run_macos_audited_child(command, cwd=self.root, timeout=5)
        session.release()
        self.assertFalse((engine / '.lyra-build-engine.lock').exists())
        self.assertFalse(Path(str(project) + '.lyra-build-project.lock').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_interruption_kills_group_and_retains_locks(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        session = selection_module().begin_project_build(project, engine)
        ready, late = self.root / 'ready-interrupt', self.root / 'late-interrupt'
        code = (f'import time; from pathlib import Path; Path({str(ready)!r}).touch(); '
                f'time.sleep(1); Path({str(late)!r}).touch()')
        command = [sys.executable, '-c', code]
        def interrupt_after_start(_group):
            deadline = time.monotonic() + 5
            while not ready.exists() and time.monotonic() < deadline:
                time.sleep(.01)
            if not ready.exists():
                raise RuntimeError('owned child did not start')
            raise KeyboardInterrupt()
        with mock.patch.object(group, 'prepare_oracle_build',
                               return_value=(command, self.root, 5)), \
             mock.patch.object(group, '_run_fixture_group', side_effect=group._run_owned_group), \
             mock.patch.object(group, '_live_group_members', side_effect=interrupt_after_start):
            with self.assertRaises(ContainmentUncertain):
                session.run_macos_audited_child(command, cwd=self.root, timeout=5)
        time.sleep(1.1)
        self.assertFalse(late.exists())
        self.assertTrue((engine / '.lyra-build-engine.lock').exists())
        self.assertTrue(Path(str(project) + '.lyra-build-project.lock').exists())
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_fixture_does_not_inherit_shell_startup_hook(self):
        marker = self.root / 'inherited-hook-ran'
        hook = self.root / 'startup.sh'
        hook.write_text(f'touch "{marker}"\n')
        with mock.patch.dict(os.environ, {'BASH_ENV': str(hook)}):
            result = group._run_fixture_group(['/bin/bash', '-c', 'true'], cwd=self.root, timeout=5)
        self.assertEqual(result, ContainedResult(0, False))
        self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_fixture_does_not_inherit_python_startup_module(self):
        marker = self.root / 'inherited-python-hook-ran'
        (self.root / 'sitecustomize.py').write_text(
            f'from pathlib import Path\nPath({str(marker)!r}).touch()\n')
        with mock.patch.dict(os.environ, {'PYTHONPATH': str(self.root)}):
            # Control: this interpreter executes the module with inherited PYTHONPATH.
            subprocess.run([sys.executable, '-c', 'pass'], cwd=self.root, check=True)
            self.assertTrue(marker.exists())
            marker.unlink()
            result = self.run_fixture('pass')
        self.assertEqual(result, ContainedResult(0, False))
        self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_preserves_failure_exit(self):
        self.assertEqual(self.run_fixture('raise SystemExit(7)'), ContainedResult(7, False))

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_waits_for_group_member_after_leader_exits(self):
        marker = self.root / 'finished'
        child = f'import time; from pathlib import Path; time.sleep(.5); Path({str(marker)!r}).write_text("done")'
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        self.assertEqual(self.run_fixture(parent), ContainedResult(0, False))
        self.assertEqual(marker.read_text(), 'done')

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_group_absence_check_catches_omitted_snapshot_member(self):
        marker = self.root / 'finished-after-omitted-snapshot'
        child = f'import time; from pathlib import Path; time.sleep(.5); Path({str(marker)!r}).touch()'
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        # Simulate a process-table snapshot omitting a still-running member.
        with mock.patch.object(group, '_live_group_members', return_value=[]):
            self.assertEqual(group._run_owned_group([sys.executable, '-c', parent],
                             cwd=self.root, timeout=10), ContainedResult(0, False))
        self.assertTrue(marker.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_omitted_member_timeout_retains_locks_without_late_signal(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        session = selection_module().begin_project_build(project, engine)
        done = self.root / 'child-finished'
        child = f'import time; from pathlib import Path; time.sleep(1); Path({str(done)!r}).touch()'
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        command = [sys.executable, '-c', parent]
        with mock.patch.object(group, 'prepare_oracle_build', return_value=(command, self.root, .3)), \
             mock.patch.object(group, '_run_fixture_group', side_effect=group._run_owned_group):
            with mock.patch.object(group, '_live_group_members', return_value=[]):
                with self.assertRaisesRegex(ContainmentUncertain, 'still exists'):
                    session.run_macos_audited_child(command, cwd=self.root, timeout=.3)
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()
        self.assertTrue((engine / '.lyra-build-engine.lock').exists())
        deadline = time.monotonic() + 5
        while not done.exists() and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(done.exists(), 'owned child did not finish without a late signal')

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_timeout_stops_descendant_before_delayed_write(self):
        ready, late = self.root / 'ready', self.root / 'late'
        child = (f'import time; from pathlib import Path; Path({str(ready)!r}).touch(); '
                 f'time.sleep(2); Path({str(late)!r}).touch()')
        parent = f'import subprocess,sys; subprocess.Popen([sys.executable,"-c",{child!r}])'
        self.assertEqual(self.run_fixture(parent, timeout=.7), ContainedResult(None, True))
        self.assertTrue(ready.exists(), 'child did not run before timeout')
        time.sleep(1.6)
        self.assertFalse(late.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def _supervisor_fixture(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        ready, done = self.root / 'ready', self.root / 'done'
        leader = self.root / 'leader'
        result_path = self.root / 'result.json'
        leaf = (f'import os,time; from pathlib import Path; '
                f'Path({str(ready)!r}).write_text(str(os.getpgrp())); '
                f'time.sleep(1.5); Path({str(done)!r}).touch()')
        child = (f'import os,subprocess,sys; from pathlib import Path; '
                 f'Path({str(leader)!r}).write_text(str(os.getpid())); '
                 f'subprocess.Popen([sys.executable,"-c",{leaf!r}])')
        supervisor = (
            'import json,sys; from pathlib import Path; from types import SimpleNamespace; '
            'sys.modules["lyra_current_transfer"]=SimpleNamespace(_json=json.loads); '
            'import lyra_build_selection as s; import lyra_macos_process_group as g; '
            f'owner=s.begin_project_build({str(project)!r},{str(engine)!r}); '
            f'command=[sys.executable,"-c",{child!r}]; '
            f'g.prepare_oracle_build=lambda *a,**k:(command,Path({str(self.root)!r}),10); '
            f'result=owner.run_macos_audited_child(command,cwd={str(self.root)!r},timeout=10); '
            f'Path({str(result_path)!r}).write_text(json.dumps([result.exit_code,result.timed_out])); '
            'owner.release()'
        )
        env = dict(os.environ, PYTHONPATH=str(Path(group.__file__).resolve().parent),
                   PYTHONDONTWRITEBYTECODE='1')
        proc = subprocess.Popen([sys.executable, '-c', supervisor], cwd=self.root, env=env,
                                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                start_new_session=True)
        return proc, engine, project, ready, done, leader, result_path

    def _wait_for_unreaped_fixture_leader(self, proc, ready, leader):
        deadline = time.monotonic() + 10
        while not ready.exists() and proc.poll() is None and time.monotonic() < deadline:
            time.sleep(.02)
        self.assertTrue(ready.exists(), 'fixture descendant did not start')
        pid = int(leader.read_text())
        self.assertEqual(int(ready.read_text()), pid)
        while time.monotonic() < deadline:
            status = subprocess.run(['/bin/ps', '-o', 'stat=', '-p', str(pid)],
                                    capture_output=True, text=True, check=False).stdout.strip()
            if status.startswith('Z'):
                return pid
            time.sleep(.02)
        self.fail('fixture leader was not retained unreaped')

    def _assert_fixture_group_gone(self, group_id):
        deadline = time.monotonic() + 5
        while time.monotonic() < deadline:
            try:
                os.killpg(group_id, 0)
            except ProcessLookupError:
                return
            except PermissionError:
                # EPERM proves nothing about absence. Keep observing within the
                # bound, and pass only if a later probe explicitly returns ESRCH.
                pass
            time.sleep(.02)
        self.fail('owned fixture group did not disappear')

    def test_group_absence_permission_error_is_uncertain(self):
        with mock.patch.object(group.os, 'killpg', side_effect=PermissionError()):
            with self.assertRaisesRegex(ContainmentUncertain, 'Cannot establish'):
                group._wait_group_gone(123, time.monotonic() + 5)

    def test_fixture_observer_requires_esrch_after_permission_error(self):
        with mock.patch.object(os, 'killpg',
                               side_effect=[PermissionError(), ProcessLookupError()]) as probe:
            self._assert_fixture_group_gone(123)
        self.assertEqual(probe.call_count, 2)

    def test_fixture_observer_never_accepts_persistent_permission_error(self):
        with mock.patch.object(os, 'killpg', side_effect=PermissionError()), \
             mock.patch.object(time, 'monotonic', side_effect=[0, 0, 6]), \
             mock.patch.object(time, 'sleep'):
            with self.assertRaisesRegex(AssertionError, 'did not disappear'):
                self._assert_fixture_group_gone(123)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_supervisor_death_stops_descendant_without_leaked_pipe_writer(self):
        proc, engine, project, ready, done, leader, result_path = self._supervisor_fixture()
        try:
            group_id = self._wait_for_unreaped_fixture_leader(proc, ready, leader)
            proc.kill()
            proc.wait(timeout=5)
            self.assertTrue((engine / '.lyra-build-engine.lock').exists())
            self.assertTrue(Path(str(project) + '.lyra-build-project.lock').exists())
            # The still-live exec child/descendant must not inherit any liveness
            # writer. Otherwise EOF never reaches the guardian and this fails.
            self._assert_fixture_group_gone(group_id)
            time.sleep(1.6)
            self.assertFalse(done.exists(), 'descendant wrote after supervisor death')
            self.assertFalse(result_path.exists())
            self.assertTrue((engine / '.lyra-build-engine.lock').exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process table required')
    def test_supervisor_sigterm_settles_group_before_releasing_sentinels(self):
        proc, engine, project, ready, done, leader, result_path = self._supervisor_fixture()
        try:
            group_id = self._wait_for_unreaped_fixture_leader(proc, ready, leader)
            os.killpg(proc.pid, signal.SIGTERM)
            self.assertEqual(proc.wait(timeout=10), 0)
            self._assert_fixture_group_gone(group_id)
            self.assertEqual(json.loads(result_path.read_text()), [128 + signal.SIGTERM, False])
            self.assertFalse((engine / '.lyra-build-engine.lock').exists())
            self.assertFalse(Path(str(project) + '.lyra-build-project.lock').exists())
            time.sleep(1.6)
            self.assertFalse(done.exists())
        finally:
            if proc.poll() is None:
                proc.kill()
                proc.wait(timeout=5)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_cancellation_before_start_does_not_launch_guardian(self):
        cancellation = threading.Event()
        cancellation.set()
        with mock.patch.object(group.subprocess, 'Popen') as spawn:
            result = group._run_fixture_group([sys.executable, '-c', 'pass'],
                     cwd=self.root, timeout=5, cancel_event=cancellation)
        self.assertEqual(result, ContainedResult(128 + signal.SIGTERM, False))
        spawn.assert_not_called()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_cancellation_before_spawn_publication_never_executes_target(self):
        cancellation = threading.Event()
        marker = self.root / 'target-must-not-run'
        original = group.subprocess.Popen
        def cancel_after_guardian_launch(*args, **kwargs):
            process = original(*args, **kwargs)
            # The parent has not yet received the guardian's spawned event or
            # acknowledged exec. A raced launch must remain behind its gate.
            cancellation.set()
            return process
        with mock.patch.object(group.subprocess, 'Popen', side_effect=cancel_after_guardian_launch):
            result = group._run_fixture_group([sys.executable, '-c',
                     f'from pathlib import Path; Path({str(marker)!r}).touch()'],
                     cwd=self.root, timeout=5, cancel_event=cancellation)
        self.assertEqual(result, ContainedResult(128 + signal.SIGTERM, False))
        self.assertFalse(marker.exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_missing_or_malformed_guardian_status_retains_sentinels(self):
        # These controlled stand-ins launch no child; they only exercise the
        # parent's refusal to treat guardian loss/status corruption as settled.
        for index, raw in enumerate((b'', b'not-json\n', b'{"kind":"result"}\n',
                                    b'{"kind":"uncertain","message":"fixture uncertainty"}\n')):
            with self.subTest(raw=raw):
                engine = self.root / ('engine-' + str(index))
                engine.mkdir()
                project = self.root / ('project-' + str(index) + '.yaze')
                project.write_text('[project]\nname=fixture\n')
                session = selection_module().begin_project_build(project, engine)
                command = [sys.executable, '-c', 'pass']
                def broken_guardian(mode, reader, writer):
                    return [sys.executable, '-I', '-S', '-B', '-c',
                            f'import os; os.write({writer},{raw!r})']
                with mock.patch.object(group, 'prepare_oracle_build',
                                       return_value=(command, self.root, 5)), \
                     mock.patch.object(group, '_fixture_helper_command', side_effect=broken_guardian):
                    with self.assertRaises(ContainmentUncertain):
                        session.run_macos_audited_child(command, cwd=self.root, timeout=5)
                with self.assertRaisesRegex(ValueError, 'uncertain child'):
                    session.release()
                self.assertTrue((engine / '.lyra-build-engine.lock').exists())
                self.assertTrue(Path(str(project) + '.lyra-build-project.lock').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_result_with_failed_guardian_exit_retains_sentinels(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        session = selection_module().begin_project_build(project, engine)
        command = [sys.executable, '-c', 'pass']
        def failed_guardian(mode, reader, writer):
            code = '''import json,os,sys
stream=os.fdopen(int(sys.argv[1]))
writer=int(sys.argv[2])
json.loads(stream.readline())
os.write(writer,(json.dumps({'kind':'spawned','pid':os.getpid()})+'\\n').encode())
json.loads(stream.readline())
os.write(writer,b'{"kind":"result","exit_code":0,"timed_out":false}\\n')
raise SystemExit(7)
'''
            return [sys.executable, '-I', '-S', '-B', '-c', code, reader, writer]
        with mock.patch.object(group, 'prepare_oracle_build', return_value=(command, self.root, 5)), \
             mock.patch.object(group, '_fixture_helper_command', side_effect=failed_guardian):
            with self.assertRaisesRegex(ContainmentUncertain, 'without confirmed completion'):
                session.run_macos_audited_child(command, cwd=self.root, timeout=5)
        with self.assertRaisesRegex(ValueError, 'uncertain child'):
            session.release()
        self.assertTrue((engine / '.lyra-build-engine.lock').exists())
        self.assertTrue(Path(str(project) + '.lyra-build-project.lock').exists())

    def test_invalid_process_snapshot_is_uncertain(self):
        with mock.patch.object(group.subprocess, 'run', return_value=mock.Mock(stdout='bad row\n')):
            with self.assertRaises(ContainmentUncertain):
                group._live_group_members(123)

    def test_snapshot_without_unreaped_leader_is_uncertain(self):
        with mock.patch.object(group.subprocess, 'run', return_value=mock.Mock(stdout='456 123 S\n')):
            with self.assertRaises(ContainmentUncertain):
                group._live_group_members(123)

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_running_fixture_holds_session_locks_until_group_exit(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        selection = selection_module()
        session = selection.begin_project_build(project, engine)
        ready = self.root / 'ready'
        code = f'import time; from pathlib import Path; Path({str(ready)!r}).touch(); time.sleep(.8)'
        command = [sys.executable, '-c', code]
        results = []
        def run():
            try:
                results.append(session.run_macos_audited_child(command, cwd=self.root, timeout=5))
            except Exception as error:
                results.append(error)
        with mock.patch.object(group, 'prepare_oracle_build', return_value=(command, self.root, 5)):
            thread = threading.Thread(target=run)
            thread.start()
            try:
                deadline = time.monotonic() + 5
                while not ready.exists() and thread.is_alive() and time.monotonic() < deadline:
                    time.sleep(.01)
                self.assertTrue(ready.exists(), 'fixture child did not start')
                with self.assertRaisesRegex(ValueError, 'held or stale'):
                    selection.begin_engine_build(engine)
                with self.assertRaisesRegex(ValueError, 'uncertain child'):
                    session.release()
            finally:
                thread.join(timeout=10)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, [ContainedResult(0, False)])
        session.release()
        self.assertFalse((engine / '.lyra-build-engine.lock').exists())

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_selected_fixture_receives_owned_generation_without_startup_hooks(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        request = self.root / 'request.json'
        request.write_text('{}')
        candidate = (Path(str(project) + '.lyra-build-output')
                     / ('lyra-' + '1' * 32) / 'oos168x.sfc')
        candidate.parent.mkdir(parents=True)
        captured = self.root / 'child-env.json'
        marker = self.root / 'hook-ran'
        hook = self.root / 'startup.sh'
        hook.write_text(f'touch "{marker}"\n')
        code = (f'import json,os; from pathlib import Path; '
                f'Path({str(captured)!r}).write_text(json.dumps(dict(os.environ)))')
        command = [sys.executable, '-c', code]
        selection = selection_module()
        session = selection.begin_attempt(project, engine)
        with mock.patch.object(group, 'prepare_oracle_build', return_value=(command, self.root, 5)):
            result = session.run_macos_audited_child(
                command, cwd=self.root, timeout=5,
                environment={'BASH_ENV': str(hook), 'PYTHONPATH': str(self.root),
                             'OOS_LYRA_BUILD_ID': 'stale', 'OOS_BASE_ROM': 'fixture'},
                request=request, candidate=candidate)
        self.assertEqual(result, ContainedResult(0, False))
        actual = json.loads(captured.read_text())
        self.assertEqual(actual['OOS_LYRA_PROJECT'], str(project))
        self.assertEqual(actual['OOS_LYRA_REQUEST'], str(request))
        self.assertEqual(actual['OOS_LYRA_CANDIDATE'], str(candidate))
        self.assertEqual(actual['OOS_LYRA_BUILD_ID'], session.build_id)
        self.assertEqual(actual['OOS_BASE_ROM'], 'fixture')
        self.assertNotIn('BASH_ENV', actual)
        self.assertNotIn('PYTHONPATH', actual)
        self.assertFalse(marker.exists())
        self.assertEqual(session._child_selection, (request, candidate))
        session.release()

    @unittest.skipUnless(sys.platform == 'darwin', 'macOS process groups required')
    def test_timed_out_macos_child_cannot_publish(self):
        engine = self.root / 'engine'
        engine.mkdir()
        project = self.root / 'project.yaze'
        project.write_text('[project]\nname=fixture\n')
        session = selection_module().begin_attempt(project, engine)
        request = self.root / 'request.json'
        request.write_text('{}')
        candidate = (Path(str(project) + '.lyra-build-output')
                     / ('lyra-' + '1' * 32) / 'oos168x.sfc')
        candidate.parent.mkdir(parents=True)
        command = [sys.executable, '-c', 'import time; time.sleep(5)']
        with mock.patch.object(group, 'prepare_oracle_build', return_value=(command, self.root, .3)):
            result = session.run_macos_audited_child(command, cwd=self.root, timeout=.3,
                                                    request=request, candidate=candidate)
        self.assertEqual(result, ContainedResult(None, True))
        with self.assertRaisesRegex(ValueError, 'Failed or timed-out child'):
            session.publish(self.root / 'request', self.root / 'candidate', self.root / 'receipt')
        session.release()


class MacSavedBuildPreflightTest(unittest.TestCase):
    """Reuse full owned Save bindings; no native verifier or Build is run."""

    def setUp(self):
        import test_lyra_ordinary_transfer_handoff as fixtures
        self.artifacts = fixtures.OrdinaryTransferSelectionTest.artifacts.__get__(self)
        self.write_policies = fixtures.OrdinaryTransferSelectionTest.write_policies.__get__(self)
        fixtures.OrdinaryTransferSelectionTest.setUp(self)

    def files(self):
        return {path: path.read_bytes() for path in self.root.rglob('*') if path.is_file()}

    def command(self, producer=None):
        command = [sys.executable, '-B',
                   str(Path(group.__file__).resolve().with_name('lyra_project_prepare.py')),
                   '--current-save-transfer', '--auto-ordinary', '--project', str(self.project),
                   '--output', str(self.output), '--candidate', str(self.candidate),
                   '--validate-build-engine', str(self.root / 'engine')]
        if producer is not None:
            command += ['--producer-identity', str(producer)]
        return command

    def test_missing_receipt_reports_existing_action_without_writes_or_launch(self):
        self.receipt.unlink()
        before = self.files()
        with mock.patch.object(group.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ValueError,
                    'CURRENT_NATIVE_SAVE_RECEIPT_REQUIRED: complete an actual native Save'):
                group.prepare_oracle_build(self.command(), cwd=self.root, timeout=5)
            launch.assert_not_called()
        self.assertEqual(self.files(), before)
        import lyra_current_transfer as current
        current.A.native_verify.assert_not_called()

    def test_bound_external_producer_returns_only_save_environment_without_execution(self):
        external = self.root / 'actual-producer.json'
        external.write_bytes(self.producer_path.read_bytes())
        before = self.files()
        with mock.patch.dict(os.environ, {'OOS_Z3ED_BIN': '/unbound', 'PATH': '/unbound'}), \
             mock.patch.object(group.subprocess, 'Popen') as launch:
            result = group.prepare_current_save_environment(self.project, producer_identity=external)
            launch.assert_not_called()
        self.assertEqual(result['environment'], {
            'YAZE_NATIVE_SAVE_CONTEXT': str(self.context_path),
            'OOS_Z3ED_BIN': str(self.verifier)})
        self.assertEqual(result['selection']['producer']['path'], str(external))
        self.assertEqual(result['selection']['policy_id'], 'ordinary-fixture')
        self.assertEqual(self.files(), before)
        import lyra_current_transfer as current
        current.A.native_verify.assert_not_called()

    def test_bound_save_keeps_production_command_graph_closed(self):
        external = self.root / 'actual-producer.json'
        external.write_bytes(self.producer_path.read_bytes())
        before = self.files()
        with mock.patch.object(group.subprocess, 'Popen') as launch:
            with self.assertRaisesRegex(ContainmentUnavailable, 'No audited macOS Oracle Build'):
                group.prepare_oracle_build(self.command(external), cwd=self.root, timeout=5)
            launch.assert_not_called()
        self.assertEqual(self.files(), before)
        import lyra_current_transfer as current
        current.A.native_verify.assert_not_called()

    def test_missing_ordinary_policy_preserves_existing_actionable_refusal(self):
        self.write_policies([])
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'):
            group.prepare_oracle_build(self.command(), cwd=self.root, timeout=5)
        self.assertEqual(self.files(), before)

    def test_changed_bound_verifier_is_not_replaced_from_path(self):
        self.verifier.write_bytes(b'changed verifier')
        before = self.files()
        with self.assertRaisesRegex(ValueError, 'changed|differs'):
            group.prepare_oracle_build(self.command(), cwd=self.root, timeout=5)
        self.assertEqual(self.files(), before)


@unittest.skipUnless(sys.platform == 'darwin', 'macOS production profile mechanics required')
class MacOracleProfileTest(unittest.TestCase):
    """Actual guardian runs only owned fake preparation/build scripts."""

    def setUp(self):
        MacSavedBuildPreflightTest.setUp(self)
        self.engine = self.project.parent / 'project'
        self.engine.mkdir()
        (self.engine / '.git').mkdir()
        (self.engine / '.git/HEAD').write_text('a'*40 + '\n')
        self.verifier.chmod(0o700)  # It is bound but never executed by these fixtures.
        for name in group._COMMAND_SOURCES:
            path = self.engine / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.name in ('lyra_macos_process_group.py', 'lyra_process_containment.py', 'lyra_output_paths.py'):
                shutil.copy2(Path(group.__file__).with_name(path.name), path)
            else:
                path.write_text('# owned fixture input\n')
        runtime = Path(str(self.project) + '.lyra-build-runtime'); runtime.mkdir(mode=0o700)
        self.home = runtime / 'home'; self.home.mkdir(mode=0o700)
        self.tmpdir = runtime / 'tmp'; self.tmpdir.mkdir(mode=0o700)
        self.asar = self.root / 'fake-asar'
        self.asar.write_text('#!/bin/sh\nexit 91\n'); self.asar.chmod(0o700)
        self.preparer = self.engine / 'Scripts/Build/lyra_project_prepare.py'
        self.preparer.write_text('''import json,os,pathlib,sys
p=pathlib.Path(os.environ['OOS_LYRA_REQUEST']);p.parent.mkdir(parents=True)
p.write_text('{}')
pathlib.Path(os.environ['HOME'],'prepare.json').write_text(json.dumps(dict(environment=dict(os.environ),argv=sys.argv,pid=os.getpid(),pgid=os.getpgrp())))
''')
        self.script = self.engine / 'Scripts/Build/build_rom.sh'
        self.script.write_text('''#!/bin/bash
set -eu
python3 - "$@" <<'PY'
import json,os,pathlib,sys
p=pathlib.Path(os.environ['OOS_LYRA_CANDIDATE']);p.write_bytes(b'owned fake artifact; not a ROM')
(p.parent/'oos168x.build.json').write_text(json.dumps(dict(root=FIXTURE_ENGINE,lyra_attempt=dict(build_id=os.environ['OOS_LYRA_BUILD_ID']))))
pathlib.Path(os.environ['HOME'],'build.json').write_text(json.dumps(dict(environment=dict(os.environ),argv=sys.argv,pid=os.getpid(),pgid=os.getpgrp())))
PY
'''.replace('FIXTURE_ENGINE', repr(str(self.engine))))
        self.source_inventory = self.root / 'command-source.json'
        self.profile_path = self.root / 'profile.json'
        self.profile = dict(kind=group.PROFILE_KIND, project=str(self.project), engine=str(self.engine),
            source_inventory={}, tools={
                'python': self.binding(Path(sys.executable).resolve()), 'bash': self.binding(Path('/bin/bash')),
                'asar': self.binding(self.asar), 'git': self.binding(Path('/usr/bin/git')), 'analyzer': None},
            path=[str(Path(sys.executable).resolve().parent), '/usr/bin', '/bin', '/usr/sbin', '/sbin'],
            home=str(self.home), tmpdir=str(self.tmpdir), required_checks=sorted(group._REQUIRED_CHECKS))
        self.refresh_profile()
        self.build_id = 'b' * 32
        self.candidate = Path(str(self.project) + '.lyra-build-output') / ('lyra-' + self.build_id) / 'oos168x.sfc'
        self.request = self.candidate.parent / 'transfer/request.json'
        self.environment = dict(os.environ, OOS_BASE_ROM=str(self.rom), OOS_LYRA_PROJECT=str(self.project),
            OOS_LYRA_BUILD_ID=self.build_id, OOS_LYRA_REQUEST=str(self.request), OOS_LYRA_CANDIDATE=str(self.candidate))

    @staticmethod
    def binding(path):
        return {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}

    def refresh_profile(self):
        rows = []
        for path in sorted(self.engine.rglob('*')):
            if path.is_file() and not path.is_relative_to(self.engine / '.git'):
                rows.append(dict(path=path.relative_to(self.engine).as_posix(),
                    sha256=hashlib.sha256(path.read_bytes()).hexdigest(), size=path.stat().st_size,
                    mode='100755' if path.stat().st_mode & 0o111 else '100644'))
        self.source_inventory.write_text(json.dumps(dict(engine_head='a'*40, files=rows)))
        self.profile['source_inventory'] = self.binding(self.source_inventory)
        self.profile_path.write_text(json.dumps(self.profile))
        self.profile_binding = self.binding(self.profile_path)

    def command(self):
        return [str(Path(sys.executable).resolve()), '-B', str(self.preparer), '--current-save-transfer',
                '--auto-ordinary', '--project', str(self.project), '--output', str(self.request.parent),
                '--candidate', str(self.candidate), '--validate-build-engine', str(self.engine)]

    def prepare(self, command=None):
        return group.prepare_oracle_build(command or self.command(), cwd=self.project.parent, timeout=8,
            environment=self.environment, profile=self.profile_binding)

    def test_same_guardian_runs_two_fixed_stages_with_bound_environment(self):
        hook = self.root / 'unselected-bash-env'; marker = self.root / 'hook-ran'
        hook.write_text('touch ' + str(marker) + '\n')
        self.environment.update(BASH_ENV=str(hook), PYTHONPATH='/unbound', OOS_TEST_SOCKET='/foreign',
                                ASAR_BIN='/wrong', OOS_SKIP_MENU_VALIDATE='1')
        self.assertEqual(group.run_oracle_build(self.prepare()), ContainedResult(0, False))
        second = self.prepare(['/bin/bash', str(self.script), '168'])
        self.assertEqual(group.run_oracle_build(second), ContainedResult(0, False))
        first, second = [json.loads((self.home / name).read_text()) for name in ('prepare.json', 'build.json')]
        for captured in (first, second):
            env = captured['environment']
            self.assertEqual(env['HOME'], str(self.home)); self.assertEqual(env['TMPDIR'], str(self.tmpdir))
            self.assertEqual(env['YAZE_NATIVE_SAVE_CONTEXT'], str(self.context_path))
            self.assertEqual(env['OOS_Z3ED_BIN'], str(self.verifier))
            self.assertEqual(env['OOS_REQUIRE_CHECKS'], ','.join(sorted(group._REQUIRED_CHECKS)))
            self.assertEqual(env['ASAR_BIN'], str(self.asar))
            self.assertEqual(env['SKIP_ANALYSIS'], '1')
            for name in ('BASH_ENV', 'PYTHONPATH', 'OOS_TEST_SOCKET', 'OOS_SKIP_MENU_VALIDATE'):
                self.assertNotIn(name, env)
            with self.assertRaises(ProcessLookupError):
                os.killpg(captured['pgid'], 0)
        self.assertEqual(first['environment']['OOS_LYRA_BUILD_ID'], second['environment']['OOS_LYRA_BUILD_ID'])
        self.assertEqual(second['argv'][1:], ['168', '--asar=' + str(self.asar)])
        self.assertFalse((self.engine / 'Roms').exists())
        self.assertFalse(marker.exists())

    def test_missing_or_changed_profile_source_tool_and_required_check_refuse_before_exec(self):
        for change in ('profile', 'source', 'tool', 'checks', 'head'):
            with self.subTest(change=change):
                path = {'profile': self.profile_path, 'source': self.preparer,
                        'tool': self.asar, 'checks': self.profile_path,
                        'head': self.engine / '.git/HEAD'}[change]
                before = path.read_bytes()
                if change == 'checks':
                    value = json.loads(before); value['required_checks'] = ['hooks']
                    path.write_text(json.dumps(value)); binding = self.binding(path)
                elif change == 'head':
                    path.write_text('b'*40 + '\n'); binding = self.profile_binding
                else:
                    path.write_bytes(before + b'\n'); binding = self.profile_binding
                try:
                    with mock.patch.object(group.subprocess, 'Popen') as start:
                        with self.assertRaises(ContainmentUnavailable):
                            group.prepare_oracle_build(self.command(), cwd=self.project.parent, timeout=8,
                                environment=self.environment, profile=binding)
                        start.assert_not_called()
                finally:
                    path.write_bytes(before)
        self.assertFalse(self.request.exists() or self.candidate.exists())

    def test_extra_command_foreign_generation_context_and_missing_policy_refuse(self):
        with self.assertRaisesRegex(ContainmentUnavailable, 'outside the fixed'):
            self.prepare(self.command() + ['--allocation-policy-id', 'invented'])
        for key, value in (('OOS_LYRA_BUILD_ID', 'a'*32), ('YAZE_NATIVE_SAVE_CONTEXT', '/foreign')):
            previous = self.environment[key]; self.environment[key] = value
            try:
                with self.assertRaises(ContainmentUnavailable): self.prepare()
            finally: self.environment[key] = previous
        self.write_policies([])
        with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'): self.prepare()
        self.assertFalse(self.request.exists())

    def test_prepared_save_change_or_redirected_environment_refuses_before_guardian(self):
        prepared = self.prepare()
        before = self.context_path.read_bytes(); self.context_path.write_bytes(before + b'\n')
        with mock.patch.object(group.subprocess, 'Popen') as start:
            with self.assertRaisesRegex(ContainmentUnavailable, 'bound file changed'):
                group.run_oracle_build(prepared)
            start.assert_not_called()
        self.context_path.write_bytes(before)
        prepared['environment']['OOS_Z3ED_BIN'] = str(self.asar)
        with self.assertRaisesRegex(ContainmentUnavailable, 'Save or ROM identity changed'):
            group.run_oracle_build(prepared)

    def test_python_tool_directory_cannot_shadow_system_file_helpers(self):
        directory = self.root / 'shadow-tools'; directory.mkdir()
        (directory / 'python3').symlink_to(Path(sys.executable).resolve())
        helper = directory / 'cp'; helper.write_text('#!/bin/sh\nexit 73\n'); helper.chmod(0o700)
        self.profile['path'].insert(0, str(directory)); self.refresh_profile()
        with self.assertRaisesRegex(ContainmentUnavailable, 'PATH shadows the system helper cp'):
            self.prepare()
        self.assertFalse(self.request.exists())


@unittest.skipUnless(sys.platform == 'darwin', 'macOS ordinary guardian')
class OrdinaryGuardianTests(unittest.TestCase):
    def setUp(self):
        from test_oracle_ordinary_build import OrdinaryFixture
        self.temp = tempfile.TemporaryDirectory(prefix='ordinary-guardian-fixture-')
        self.addCleanup(self.temp.cleanup)
        self.fixture = OrdinaryFixture(self.temp.name, mode='timeout')

    def test_exact_prepared_environment_is_rechecked_before_guardian(self):
        import oracle_ordinary_build as ordinary
        original = group.run_ordinary_build
        def substituted(prepared):
            prepared['environment']['OOS_TEST_SOCKET'] = '/foreign/must-not-connect'
            with mock.patch.object(group.subprocess, 'Popen') as launch:
                with self.assertRaisesRegex(ContainmentUnavailable, 'command/environment differs'):
                    original(prepared)
                launch.assert_not_called()
            return ContainedResult(17, False)
        with mock.patch.object(group, 'run_ordinary_build', side_effect=substituted):
            with self.assertRaisesRegex(ValueError, 'Build failed'):
                self.fixture.run()
        self.assertFalse((self.fixture.engine / '.lyra-build-engine.lock').exists())

    def run_parent_control(self, signum):
        import oracle_ordinary_build as ordinary
        fixture = self.fixture
        bootstrap = ('import runpy,sys;sys.path.insert(0,sys.argv.pop(1));'
                     'runpy.run_module("oracle_ordinary_build",run_name="__main__")')
        command = [str(Path(sys.executable).resolve()), '-I', '-S', '-B', '-c', bootstrap,
                   str(Path(ordinary.__file__).parent), '--project', str(fixture.project),
                   '--engine', str(fixture.engine), '--macos-profile', str(fixture.profile),
                   '--macos-profile-sha256', ordinary.binding(fixture.profile)['sha256']]
        with (fixture.root/'supervisor.log').open('wb') as log:
            process = subprocess.Popen(command, env={**fixture.environment,
                'PATH': '/usr/bin:/bin', 'PYTHONDONTWRITEBYTECODE': '1'},
                stdin=subprocess.DEVNULL, stdout=log, stderr=log, close_fds=True)
            try:
                deadline = time.monotonic() + 8
                while time.monotonic() < deadline:
                    files = list(Path(str(fixture.project)+'.oracle-build-output').glob('oracle-*/child.pid'))
                    if files: break
                    if process.poll() is not None:
                        self.fail('Supervisor exited before fixed child: ' + (fixture.root/'supervisor.log').read_text())
                    time.sleep(.02)
                self.assertTrue(files)
                child = int(files[0].read_text())
                process.send_signal(signum)  # Only the retained owned supervisor.
                process.wait(timeout=12)
                # Observe only. Never signal a child/group after guardian reap.
                deadline = time.monotonic() + 12
                gone = False
                while time.monotonic() < deadline:
                    try: os.kill(child, 0)
                    except ProcessLookupError: gone = True; break
                    except PermissionError: pass  # Unknown/alive, never absence.
                    time.sleep(.02)
                self.assertTrue(gone, 'Guardian child absence is unproven')
                self.assertEqual(json.loads(fixture.selector.read_text())['kind'], 'oracle.latest_pending.v1')
                self.assertFalse((files[0].parent/'oos168x.build.json').exists())
                held = (fixture.engine/'.lyra-build-engine.lock').exists()
                self.assertEqual(held, signum == signal.SIGKILL)
                self.assertEqual(Path(str(fixture.project)+'.lyra-build-project.lock').exists(), held)
            finally:
                if process.poll() is None:
                    process.kill(); process.wait(timeout=12)

    def test_explicit_cancel_stops_owned_child_before_release(self):
        self.run_parent_control(signal.SIGTERM)

    def test_parent_death_cleans_owned_child_and_retains_markers(self):
        self.run_parent_control(signal.SIGKILL)


if __name__ == '__main__':
    unittest.main()
