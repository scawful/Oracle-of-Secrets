"""Synthetic lifecycle and receipt checks; no ROM build or subprocess launch."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import unittest
from unittest import mock

import lyra_build_selection as selection
import lyra_current_transfer as X
from test_lyra_current_build import CurrentBuildTest
import test_lyra_current_transfer as transfer_fixtures


class BuildSelectionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = transfer_fixtures.CurrentSaveTransferTest.prepare

        def capture(case, **kwargs):
            case.candidate = (Path(str(case.project) + '.lyra-build-output')
                              / ('lyra-' + '1' * 32) / 'oos168x.sfc')
            return original(case, **kwargs)

        with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest, 'prepare', capture):
            CurrentBuildTest.setUpClass.__func__(cls)
        cls.target = cls.case.candidate
        cls.target.parent.mkdir(parents=True)
        cls.target.write_bytes(bytes(0x400000))
        cls.symbols = cls.target.parent / 'oos168x.sym'
        cls.symbols.write_bytes(b'synthetic symbols')
        cls.prepare = cls.target.parent / 'oos168x.lyra-prepare.json'
        cls.prepare.write_bytes(cls.files['prepare.json'])
        cls.verification = cls.target.parent / 'oos168x.lyra-verification.json'
        cls.verification.write_bytes(X.P.encoded(dict(
            kind='lyra.current_build_verification.v1', compiled_consumers_verified=True,
            prepared_sha256=X.Q.bound(cls.prepare)['sha256'],
            compiled_rom_sha256=X.Q.bound(cls.target)['sha256'],
            symbols_sha256=X.Q.bound(cls.symbols)['sha256'],
            saved_rom_sha256=X.Q.bound(cls.case.rom)['sha256'],
            current_ledger_sha256=cls.prepared['current_ledger_sha256'])))
        cls.receipt = cls.target.parent / 'oos168x.build.json'

        def artifact(path):
            return dict(**X.Q.bound(path), size=path.stat().st_size)

        cls.build = dict(schema_version=1, state='completed', root=str(cls.f.root),
            finish=dict(exit_code=0, required_gaps=[]),
            checks=[dict(name='lyra_verify', required=True, status='passed', exit_code=0)],
            base_rom=artifact(cls.case.rom), artifacts=dict(
                output_rom=artifact(cls.target), symbols=artifact(cls.symbols),
                lyra_prepare=artifact(cls.prepare), lyra_verification=artifact(cls.verification)))
        cls.selector = Path(str(cls.case.project) + '.lyra-build-latest.json')
        cls.project_lock = Path(str(cls.case.project) + '.lyra-build-project.lock')
        cls.engine_lock = cls.f.root / '.lyra-build-engine.lock'

    def receipt_for(self, build_id, **changes):
        value = copy.deepcopy(self.build)
        value['lyra_attempt'] = {'build_id': build_id}
        value.update(changes)
        self.receipt.write_bytes(X.P.encoded(value))

    def publish(self, session):
        # These cases test receipt validation with synthetic evidence; actual
        # contained execution is covered separately on Windows.
        with mock.patch.object(session, '_child_completed', True), \
             mock.patch.object(session, '_child_selection', (self.request, self.target)):
            return session.publish(self.request, self.target, self.receipt)

    def test_unstarted_lifecycle_cannot_publish_a_receipt(self):
        session = selection.begin_attempt(self.case.project, self.f.root)
        try:
            self.receipt_for(session.build_id)
            before = self.selector.read_bytes()
            with self.assertRaisesRegex(ValueError, 'No contained Build child'):
                session.publish(self.request, self.target, self.receipt)
            self.assertEqual(self.selector.read_bytes(), before)
        finally:
            session.release()
            self.selector.unlink(missing_ok=True)

    def test_partial_sentinel_write_keeps_original_error_and_marker(self):
        def partial_fsync(fd):
            os.ftruncate(fd, 0)
            raise OSError('injected sentinel sync failure')

        try:
            with mock.patch.object(selection.os, 'fsync', side_effect=partial_fsync):
                with self.assertRaisesRegex(OSError, 'injected sentinel sync failure') as caught:
                    selection.begin_project_build(self.case.project, self.f.root)
            self.assertIsInstance(caught.exception.__cause__, RuntimeError)
            self.assertIn('ownership changed', str(caught.exception.__cause__))
            self.assertEqual(self.project_lock.read_bytes(), b'')
            self.assertFalse(self.engine_lock.exists())
        finally:
            # Only the empty marker created by this test is removed here.
            if self.project_lock.exists() and self.project_lock.read_bytes() == b'':
                self.project_lock.unlink()

    def test_partial_engine_sentinel_retains_both_owned_markers(self):
        original_fsync = os.fsync
        calls = 0

        def fail_engine_fsync(fd):
            nonlocal calls
            calls += 1
            # Directory sync is stubbed below; the second file is the engine.
            if calls == 2:
                os.ftruncate(fd, 0)
                raise OSError('injected engine sync failure')
            return original_fsync(fd)

        try:
            with mock.patch.object(selection, '_sync_dir'), \
                 mock.patch.object(selection.os, 'fsync', side_effect=fail_engine_fsync):
                with self.assertRaisesRegex(OSError, 'injected engine sync failure') as caught:
                    selection.begin_project_build(self.case.project, self.f.root)
            self.assertIsInstance(caught.exception.__cause__, RuntimeError)
            self.assertIn('ownership changed', str(caught.exception.__cause__))
            self.assertEqual(json.loads(self.project_lock.read_text())['kind'],
                             'lyra.build_lock.v1')
            self.assertEqual(self.engine_lock.read_bytes(), b'')
        finally:
            # These two sentinel paths are owned by this isolated fixture.
            self.engine_lock.unlink(missing_ok=True)
            self.project_lock.unlink(missing_ok=True)

    def test_project_hard_links_refuse_build_and_keep_existing_lock(self):
        alias = self.case.project.with_name('project-hard-link.yaze')
        try:
            os.link(self.case.project, alias)
        except OSError as error:
            self.skipTest(f'hard links unavailable: {error}')
        try:
            with self.assertRaisesRegex(ValueError, 'exactly one hard link'):
                selection.begin_project_build(self.case.project, self.f.root)
            with self.assertRaisesRegex(ValueError, 'exactly one hard link'):
                selection.begin_project_build(alias, self.f.root)
            self.assertFalse(self.project_lock.exists())
            self.assertFalse(self.engine_lock.exists())
        finally:
            alias.unlink(missing_ok=True)

        session = selection.begin_project_build(self.case.project, self.f.root)
        try:
            os.link(self.case.project, alias)
            with self.assertRaisesRegex(ValueError, 'exactly one hard link'):
                session._check_owned()
            self.assertTrue(self.project_lock.exists())
            self.assertTrue(self.engine_lock.exists())
        finally:
            alias.unlink(missing_ok=True)
            session.release()

    def test_run_markers_block_build_without_being_reclaimed(self):
        for marker in (b'{"kind":"lyra.run_lock.v1"}\n',
                       b'{"kind":"lyra.save_lock.v1"}\n'):
            with self.subTest(marker=marker):
                self.project_lock.write_bytes(marker)
                try:
                    with self.assertRaisesRegex(ValueError, 'held or stale'):
                        selection.begin_project_build(self.case.project, self.f.root)
                    with self.assertRaisesRegex(ValueError, 'held or stale'):
                        selection.begin_attempt(self.case.project, self.f.root)
                    self.assertEqual(self.project_lock.read_bytes(), marker)
                    self.assertFalse(self.engine_lock.exists())
                finally:
                    self.project_lock.unlink(missing_ok=True)

        marker = b'{"kind":"lyra.run_lock.v1"}\n'
        self.engine_lock.write_bytes(marker)
        try:
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_engine_build(self.f.root)
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_project_build(self.case.project, self.f.root)
            self.assertEqual(self.engine_lock.read_bytes(), marker)
            self.assertFalse(self.project_lock.exists())
        finally:
            self.engine_lock.unlink(missing_ok=True)

    def test_run_owner_process_excludes_build_and_crash_retains_locks(self):
        ready = self.case.root / 'run-owner-ready'
        worker = r'''
import os, pathlib, sys
paths = [pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2])]
fds = [os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR, 0o600) for path in paths]
for fd in fds:
    os.write(fd, b'{"kind":"lyra.run_lock.v1"}\n')
    os.fsync(fd)
pathlib.Path(sys.argv[3]).write_text('ready')
sys.stdin.readline()
for fd, path in reversed(list(zip(fds, paths))):
    os.close(fd)
    path.unlink()
'''

        def start():
            process = subprocess.Popen(
                [sys.executable, '-c', worker, str(self.project_lock),
                 str(self.engine_lock), str(ready)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True)
            deadline = time.monotonic() + 15
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not ready.exists():
                process.kill()
                _, stderr = process.communicate(timeout=5)
                self.fail('Run owner did not acquire locks: ' + stderr)
            return process

        process = None
        try:
            process = start()
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_attempt(self.case.project, self.f.root)
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_engine_build(self.f.root)
            _, stderr = process.communicate(input='release\n', timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            process = None
            self.assertFalse(self.project_lock.exists())
            self.assertFalse(self.engine_lock.exists())
            ready.unlink()

            process = start()
            process.kill()
            process.communicate(timeout=5)
            process = None
            for path in (self.project_lock, self.engine_lock):
                self.assertEqual(path.read_bytes(), b'{"kind":"lyra.run_lock.v1"}\n')
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_attempt(self.case.project, self.f.root)
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_engine_build(self.f.root)
        finally:
            if process is not None:
                process.kill()
                process.communicate(timeout=5)
            # Only synthetic fixture files are removed here.
            self.project_lock.unlink(missing_ok=True)
            self.engine_lock.unlink(missing_ok=True)
            ready.unlink(missing_ok=True)

    def test_engine_only_build_serializes_with_selected_build(self):
        self.assertFalse(self.selector.exists())
        ordinary = selection.begin_engine_build(self.f.root)
        self.assertTrue(self.engine_lock.exists())
        self.assertFalse(self.project_lock.exists())
        self.assertFalse(self.selector.exists())
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_engine_build(self.f.root)
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(self.case.project, self.f.root)
        self.assertFalse(self.project_lock.exists())
        with self.assertRaisesRegex(ValueError, 'engine-only'):
            self.publish(ordinary)
        ordinary.release()
        self.assertFalse(self.engine_lock.exists())

        project_build = selection.begin_project_build(self.case.project, self.f.root)
        self.assertTrue(self.project_lock.exists())
        self.assertTrue(self.engine_lock.exists())
        self.assertFalse(self.selector.exists())
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(self.case.project, self.f.root)
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_engine_build(self.f.root)
        with self.assertRaisesRegex(ValueError, 'ordinary'):
            self.publish(project_build)
        project_build.release()
        self.assertFalse(self.project_lock.exists())
        self.assertFalse(self.engine_lock.exists())

        selected = selection.begin_attempt(self.case.project, self.f.root)
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_engine_build(self.f.root)
        selected.release()
        self.selector.unlink()  # This fixture created its pending marker.
        self.assertFalse(self.engine_lock.exists())
        self.assertFalse(self.project_lock.exists())

    def test_cross_process_refusal_and_crash_retains_sentinels(self):
        ready = self.case.root / 'child-ready'
        other_project = self.case.root / 'other-process.yaze'
        worker = '''
import pathlib, sys
import lyra_build_selection as selection
session = selection.begin_attempt(pathlib.Path(sys.argv[1]), pathlib.Path(sys.argv[2]))
pathlib.Path(sys.argv[3]).write_text(session.build_id)
sys.stdin.readline()
session.release()
'''

        def start():
            process = subprocess.Popen(
                [sys.executable, '-c', worker, str(self.case.project),
                 str(self.f.root), str(ready)],
                stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                stderr=subprocess.PIPE, text=True, env=os.environ.copy())
            deadline = time.monotonic() + 15
            while not ready.exists() and process.poll() is None and time.monotonic() < deadline:
                time.sleep(0.02)
            if not ready.exists():
                process.kill()
                _, stderr = process.communicate(timeout=5)
                self.fail('child did not acquire its locks: ' + stderr)
            return process

        self.assertFalse(self.selector.exists())
        other_project.write_text('[project]\nname=other\n')
        process = None
        try:
            process = start()
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_attempt(self.case.project, self.f.root)
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_attempt(other_project, self.f.root)
            self.assertFalse(Path(str(other_project) + '.lyra-build-project.lock').exists())
            _, stderr = process.communicate(input='release\n', timeout=15)
            self.assertEqual(process.returncode, 0, stderr)
            process = None
            self.assertFalse(self.project_lock.exists())
            self.assertFalse(self.engine_lock.exists())
            ready.unlink()

            process = start()
            project_lock = self.project_lock.read_bytes()
            engine_lock = self.engine_lock.read_bytes()
            process.kill()
            process.communicate(timeout=5)
            process = None
            with self.assertRaisesRegex(ValueError, 'held or stale'):
                selection.begin_attempt(self.case.project, self.f.root)
            self.assertEqual(self.project_lock.read_bytes(), project_lock)
            self.assertEqual(self.engine_lock.read_bytes(), engine_lock)
        finally:
            if process is not None:
                process.kill()
                process.communicate(timeout=5)
            # All files here belong to this synthetic test fixture.
            self.project_lock.unlink(missing_ok=True)
            self.engine_lock.unlink(missing_ok=True)
            self.selector.unlink(missing_ok=True)
            ready.unlink(missing_ok=True)
            other_project.unlink(missing_ok=True)

    def test_serialized_lifecycle_receipts_failures_and_save_race(self):
        case = self.case
        inputs = (case.project, case.rom, case.terrain, case.receipt,
                  case.context_path, self.request)
        before = {path: path.read_bytes() for path in inputs}

        # An initial marker failure releases both unstarted locks; no selection.
        with mock.patch.object(selection.os, 'link', side_effect=OSError('link failed')):
            with self.assertRaisesRegex(OSError, 'link failed'):
                selection.begin_attempt(case.project, self.f.root)
        self.assertFalse(self.selector.exists())
        self.assertFalse(self.project_lock.exists())
        self.assertFalse(self.engine_lock.exists())

        session = selection.begin_attempt(case.project, self.f.root)
        with self.assertRaises(AttributeError):
            session.build_id = '0' * 32
        with self.assertRaises(AttributeError):
            session.engine = case.root
        with self.assertRaises(AttributeError):
            session.project = case.root / 'other.yaze'
        self.assertTrue(self.project_lock.exists())
        self.assertTrue(self.engine_lock.exists())
        pending = {'kind': selection.PENDING_KIND, 'project': str(case.project)}
        self.assertEqual(json.loads(self.selector.read_bytes()), pending)
        pending_bytes = self.selector.read_bytes()
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(case.project, self.f.root)
        other_engine = case.root / 'other-engine'
        other_engine.mkdir()
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(case.project, other_engine)

        other_project = case.root / 'other.yaze'
        other_project.write_text('[project]\nname=other\n')
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(other_project, self.f.root)
        self.assertFalse(Path(str(other_project) + '.lyra-build-project.lock').exists())
        self.assertTrue(self.engine_lock.exists())

        self.receipt_for(session.build_id, state='failed')
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            self.publish(session)
        self.assertEqual(self.selector.read_bytes(), pending_bytes)
        self.receipt_for(session.build_id)
        bad_attempt = copy.deepcopy(self.build)
        bad_attempt['lyra_attempt'] = {}
        self.receipt.write_bytes(X.P.encoded(bad_attempt))
        with self.assertRaisesRegex(ValueError, 'attempt identity'):
            self.publish(session)
        self.assertEqual(self.selector.read_bytes(), pending_bytes)
        self.receipt_for(session.build_id)
        for checks in ([dict(name='lyra_verify', required=True, status='passed')],
                       [dict(name='lyra_verify', required=1, status='passed', exit_code=0)],
                       [dict(name='lyra_verify', required=True, status='passed', exit_code=1)],
                       [dict(name='lyra_verify', required=True, status='passed', exit_code=False)],
                       [dict(name='lyra_verify', required=True, status='passed', exit_code=0),
                        dict(name='lyra_verify', required=False, status='failed')]):
            self.receipt_for(session.build_id, checks=checks)
            with self.subTest(checks=checks), self.assertRaises(ValueError):
                self.publish(session)
            self.assertEqual(self.selector.read_bytes(), pending_bytes)
        self.receipt_for(session.build_id)

        self.selector.write_bytes(X.P.encoded(dict(kind=selection.PENDING_KIND,
                                                   project='/foreign/project.yaze')))
        foreign = self.selector.read_bytes()
        with self.assertRaisesRegex(ValueError, 'malformed or foreign'):
            self.publish(session)
        self.assertEqual(self.selector.read_bytes(), foreign)
        self.selector.write_bytes(pending_bytes)

        result = self.publish(session)
        self.assertEqual(result['build_id'], session.build_id)
        self.assertEqual(result['generation'], case.save['generation'])
        self.assertEqual(result['operation_id'], case.save['operation_id'])
        self.assertEqual(result['candidate'], str(self.target))
        prior = self.selector.read_bytes()
        self.target.write_bytes(b'changed')
        with self.assertRaises(ValueError):
            self.publish(session)
        self.assertEqual(self.selector.read_bytes(), prior)
        self.target.write_bytes(bytes(0x400000))
        old_id = session.build_id
        session.release()
        self.assertFalse(self.project_lock.exists())
        self.assertFalse(self.engine_lock.exists())
        with self.assertRaisesRegex(ValueError, 'not active'):
            self.publish(session)

        retry = selection.begin_attempt(case.project, self.f.root)
        self.assertNotEqual(retry.build_id, old_id)
        self.assertEqual(self.selector.read_bytes(), prior)
        # A later lifecycle cannot publish the old, otherwise valid receipt.
        with self.assertRaisesRegex(ValueError, 'another lifecycle'):
            self.publish(retry)
        self.assertEqual(self.selector.read_bytes(), prior)
        self.receipt_for(retry.build_id, state='in_progress')
        with self.assertRaisesRegex(ValueError, 'did not complete'):
            self.publish(retry)
        self.assertEqual(self.selector.read_bytes(), prior)
        self.receipt_for(retry.build_id)
        newer = self.publish(retry)
        self.assertEqual(newer['generation'], result['generation'])
        self.assertEqual(newer['build_id'], retry.build_id)
        newer_bytes = self.selector.read_bytes()

        # Atomic replacement failure leaves the previous successful selector.
        with mock.patch.object(selection.os, 'replace', side_effect=OSError('injected')):
            with self.assertRaisesRegex(OSError, 'injected'):
                self.publish(retry)
        self.assertEqual(self.selector.read_bytes(), newer_bytes)

        # A Save after the final producer recheck can stale the selector; the
        # real consumer must revalidate rather than trust the published pointer.
        old_save, old_context = copy.deepcopy(case.save), copy.deepcopy(case.context)
        replace = selection.os.replace
        def save_then_replace(source, destination):
            case.next_save()
            replace(source, destination)
        try:
            with mock.patch.object(selection.os, 'replace', side_effect=save_then_replace):
                self.publish(retry)
            with self.assertRaisesRegex(ValueError, 'Current-save transfer retired'):
                selection.validate(case.project, self.request, self.target, self.receipt)
        finally:
            case.save, case.context = old_save, old_context
            case.receipt.write_bytes(before[case.receipt])
            case.context_path.write_bytes(before[case.context_path])
        self.assertEqual({path: path.read_bytes() for path in inputs}, before)
        retry.release()

        self.project_lock.write_bytes(b'uncertain stale owner')
        with self.assertRaisesRegex(ValueError, 'held or stale'):
            selection.begin_attempt(case.project, self.f.root)
        self.assertEqual(self.project_lock.read_bytes(), b'uncertain stale owner')
        self.project_lock.unlink()  # The test created this synthetic sentinel.

        # Unknown child lifetime deliberately prevents publication and release.
        uncertain = selection.begin_attempt(case.project, self.f.root)
        uncertain.mark_child_started()
        with self.assertRaisesRegex(ValueError, 'Child lifetime is not verified'):
            self.publish(uncertain)
        with self.assertRaisesRegex(ValueError, 'uncertain child lifecycle'):
            uncertain.release()
        self.assertTrue(self.project_lock.exists())
        self.assertTrue(self.engine_lock.exists())
        with mock.patch.object(selection.os, 'getpid', return_value=uncertain._pid + 1):
            with self.assertRaisesRegex(ValueError, 'another process'):
                uncertain.release()
        self.engine_lock.write_bytes(b'foreign sentinel')
        with self.assertRaisesRegex(RuntimeError, 'ownership changed'):
            uncertain.release()
        self.assertTrue(self.project_lock.exists())
        self.assertEqual(self.engine_lock.read_bytes(), b'foreign sentinel')
        # No child was launched in this case; these are fixture-owned files.
        self.project_lock.unlink()
        self.engine_lock.unlink()
        self.selector.unlink(missing_ok=True)


if __name__ == '__main__':
    unittest.main()
