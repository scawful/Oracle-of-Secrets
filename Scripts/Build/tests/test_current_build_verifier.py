"""Selected current builds pin the verifier their authenticated transfer ran.

Transfer authentication is the maintained lyra_current_transfer contract; these
fast stubs only fix its result so tool selection and refusal stay observable.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

BUILD = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BUILD))
import lyra_current_transfer as X
import lyra_project_prepare as Q
import lyra_project_publisher as P


class CurrentBuildVerifierTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name).resolve()
        self.selected = self.tool('selected', 0)
        self.nightly = self.tool('nightly', 134)
        self.row = Q.bound(self.selected)
        self.transfer = dict(native_verification=dict(path='native.json', sha256='0' * 64),
                             live=dict(producer_identity=dict(verifier=self.row)))
        context = (self.root / 'opened.yaze', self.root / 'oos168.sfc', None, self.root / 'request.json')
        for patch in (mock.patch.object(P, 'project_context', return_value=context),
                      mock.patch.object(X, 'verify_transfer', side_effect=lambda *_: (self.transfer, b'', None)),
                      mock.patch.object(X, 'native_execution', side_effect=lambda _: dict(binary=self.row))):
            patch.start()
            self.addCleanup(patch.stop)

    def tool(self, name, status):
        path = self.root / name / 'z3ed'
        path.parent.mkdir()
        path.write_text(f'#!/bin/sh\necho "$@" >> "{self.root / name}.log"\nexit {status}\n')
        path.chmod(0o755)
        return path

    def calls(self, name):
        log = self.root / f'{name}.log'
        return log.read_text().splitlines() if log.exists() else []

    def select(self, explicit=None):
        return P.current_verifier(self.root / 'opened.yaze', explicit=explicit)

    def test_recorded_native_execution_binary_is_pinned_and_load_probed(self):
        self.assertEqual(self.select()['verifier'], self.row)
        self.assertEqual(self.calls('selected'), ['--version'])
        self.assertEqual(self.calls('nightly'), [])

    def test_request_without_native_record_uses_authenticated_producer_verifier(self):
        del self.transfer['native_verification']
        X.native_execution.side_effect = AssertionError('absent native record is not consulted')
        self.assertEqual(self.select()['verifier'], self.row)

    def test_explicit_tool_must_be_the_selected_verifier(self):
        self.assertEqual(self.select(explicit=self.selected)['verifier'], self.row)
        for declared in (self.nightly, self.root / 'missing-z3ed'):
            with self.subTest(declared=declared.name):
                with self.assertRaisesRegex(ValueError, 'CURRENT_VERIFIER_MISMATCH'):
                    self.select(explicit=declared)
        self.assertEqual(self.calls('selected'), ['--version'])
        self.assertEqual(self.calls('nightly'), [])

    def test_missing_changed_or_unloadable_pin_refuses(self):
        self.row = Q.bound(self.nightly)
        with self.assertRaisesRegex(ValueError, 'CURRENT_VERIFIER_UNAVAILABLE: .* exited 134'):
            self.select()
        self.row = dict(path=str(self.root / 'missing-z3ed'), sha256='0' * 64)
        with self.assertRaisesRegex(ValueError, 'CURRENT_VERIFIER_UNAVAILABLE'):
            self.select()
        self.row = Q.bound(self.selected)
        self.selected.write_text(self.selected.read_text() + '# rebuilt\n')
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            self.select()
        self.assertEqual(self.calls('selected'), [])

    def test_transfer_refusal_stops_before_any_tool_runs(self):
        X.verify_transfer.side_effect = ValueError('CURRENT_NATIVE_VERIFIER_EXECUTION_MISMATCH')
        with self.assertRaisesRegex(ValueError, 'CURRENT_NATIVE_VERIFIER_EXECUTION_MISMATCH'):
            self.select()
        self.assertEqual(self.calls('selected') + self.calls('nightly'), [])


class CurrentBuildToolShellTest(unittest.TestCase):
    """build_checks.sh pins before menu lookup; the publisher is a python3 stub."""
    SCRIPT = r'''
python3() { echo "${*:2}" >> "$CALLS"; [[ -z "${REFUSE:-}" ]] || return 3; echo "$PINNED"; }
repo_root="$1"; version=168; base_rom="$2"; rom_dir="$repo_root/Roms"
source "$repo_root/Scripts/Build/build_checks.sh"
configure_current_tools || exit $?
select_z3ed_cli
'''

    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.temp = Path(temp.name).resolve()
        self.repo = self.temp / 'oracle'
        (self.repo / 'Scripts/Build').mkdir(parents=True)
        shutil.copy2(BUILD / 'build_checks.sh', self.repo / 'Scripts/Build/build_checks.sh')
        self.nightly = self.tool(self.temp / 'yaze/scripts/z3ed')
        self.on_path = self.tool(self.temp / 'bin/z3ed')
        self.pinned = self.tool(self.temp / 'selected/z3ed')
        self.calls = self.temp / 'publisher-calls.log'
        self.env = {k: v for k, v in os.environ.items() if not k.startswith('OOS_')}
        self.env.update(PATH=f"{self.on_path.parent}:{os.environ['PATH']}", CALLS=str(self.calls),
                        PINNED=str(self.pinned))

    def tool(self, path):
        path.parent.mkdir(parents=True)
        path.write_text('#!/bin/sh\nexit 134\n')
        path.chmod(0o755)
        return path

    def run_checks(self, **env):
        return subprocess.run(['bash', '-c', self.SCRIPT, '_', str(self.repo), '/base/oos168.sfc'],
                              env={**self.env, **env}, text=True, capture_output=True)

    def current(self, **env):
        return self.run_checks(OOS_LYRA_PROJECT='/saved/opened.yaze', OOS_LYRA_REQUEST='/saved/request.json',
                               OOS_LYRA_CANDIDATE='/out/oos168x.sfc', **env)

    def test_selected_tool_wins_over_stale_nightly_and_path(self):
        result = self.current()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(result.stdout.strip(), str(self.pinned))
        self.assertEqual(self.calls.read_text().split(), [
            'current-verifier', '--project', '/saved/opened.yaze', '--base-rom', '/base/oos168.sfc',
            '--request', '/saved/request.json'])

    def test_explicit_tool_is_declared_to_the_selected_verifier_check(self):
        result = self.current(OOS_Z3ED_BIN=str(self.nightly))
        self.assertEqual(result.stdout.strip(), str(self.pinned))
        self.assertEqual(self.calls.read_text().split()[-2:], ['--explicit', str(self.nightly)])

    def test_refused_pin_never_falls_back_to_a_default_tool(self):
        result = self.current(REFUSE='1', OOS_Z3ED_BIN=str(self.nightly))
        self.assertEqual(result.returncode, 3)
        self.assertEqual(result.stdout, '')

    def test_non_current_builds_keep_default_selection_without_publisher(self):
        self.assertEqual(self.run_checks().stdout.strip(), str(self.repo / '../yaze/scripts/z3ed'))
        self.nightly.unlink()
        self.assertEqual(self.run_checks().stdout.strip(), str(self.on_path))
        self.assertEqual(self.run_checks(OOS_Z3ED_BIN='/declared/z3ed').stdout.strip(), '/declared/z3ed')
        self.assertFalse(self.calls.exists())


if __name__ == '__main__':
    unittest.main()
