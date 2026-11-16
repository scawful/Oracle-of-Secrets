"""Read-only selection for an automatic ordinary Build transfer."""
import contextlib
import copy
import io
import json
import sys
import unittest
from unittest import mock

import lyra_current_transfer as current
import lyra_project_prepare as prepare
import lyra_project_publisher as publisher
import test_lyra_current_transfer as transfer_fixtures


class OrdinaryTransferSelectionTest(unittest.TestCase):
    artifacts = transfer_fixtures.CurrentSaveTransferTest.artifacts

    def setUp(self):
        transfer_fixtures.CurrentSaveTransferTest.setUp(self)
        self.ledger = self.root / 'source-ledger.json'
        self.policy = {
            'id': 'ordinary-fixture',
            'kind': current.NATIVE_POLICY_KIND,
            'scope': 'disposable_build_only',
            'producer_identity_sha256': current.Q.bound(self.producer_path)['sha256'],
            'current_runtime': {'kind': 'lyra.current_runtime_policy.v1',
                                'scope': 'disposable_build_only',
                                'runtime_admission': True},
        }
        self.write_policies([self.policy])
        self.ledger_patch = mock.patch.object(current.R, 'LEDGER', self.ledger)
        self.ledger_patch.start()
        self.addCleanup(self.ledger_patch.stop)
        # This module tests the ordinary caller/CLI seam. The selected
        # executable and inspection content have real-process controls in
        # FreshInspectionCaptureTest and full resident reconstruction controls.
        self.inspection = dict(inspection_only=True,
            native_resolution_schema='yaze.lyra-native-resolution.v1',
            project_descriptor_identity_status='identified',
            project_descriptor_path=str(self.project),
            project_descriptor_sha256=current.Q.bound(self.project)['sha256'],
            terrain_path=str(self.terrain), terrain_sha256=current.Q.bound(self.terrain)['sha256'],
            source_rom_sha256=current.Q.bound(self.rom)['sha256'], map_count=32, donor_map=0x3A,
            asset_binding_mismatches=0,
            map_assets=[dict(map_id=page, state=state)
                        for page in range(0xA0, 0xC0) for state in range(3)])
        patch = mock.patch.object(current.A, 'native_inspect', return_value=self.inspection)
        self.inspect = patch.start()
        self.addCleanup(patch.stop)

    def write_policies(self, policies):
        self.ledger.write_text(json.dumps({'current_save_transfer_policies': policies}))

    def test_matching_current_save_selects_bound_verifier_and_policy(self):
        before = {p: p.read_bytes() for p in (self.project, self.rom, self.receipt,
                                                self.context_path, self.producer_path)}
        result = current.select_ordinary_transfer_inputs(self.project)
        self.assertEqual(result['policy_id'], 'ordinary-fixture')
        self.assertEqual(result['verifier'], self.producer['verifier'])
        self.assertEqual(result['producer'], current.Q.bound(self.producer_path))
        self.assertEqual(result['save_receipt'], current.Q.bound(self.receipt))
        self.assertEqual(before, {p: p.read_bytes() for p in before})
        self.assertFalse(self.output.exists())
        current.A.native_verify.assert_not_called()
        self.inspect.assert_not_called()

    def test_auto_transfer_records_selected_policy_without_changing_save(self):
        before = self.project.read_bytes()
        report = current.prepare_ordinary_transfer(self.project, self.output, self.candidate)
        request = json.loads((self.output / 'request.json').read_bytes())
        self.assertTrue(report['snapshot_ready'])
        self.assertFalse(report['ordinary_build_ready'])
        self.assertEqual(request['allocation_policy_id'], 'ordinary-fixture')
        self.assertEqual(request['native_verification']['path'],
                         str(self.output / 'native-verification.json'))
        self.assertEqual(request['live']['producer'], current.Q.bound(self.producer_path))
        self.assertEqual(self.project.read_bytes(), before)
        self.assertFalse(self.candidate.exists())
        current.A.native_verify.assert_called_once()
        self.inspect.assert_called_once_with(self.verifier, self.project, self.rom)
        execution = current.inspection_execution(request)
        self.assertEqual(execution['binary'], self.producer['verifier'])
        self.assertEqual(execution['command'], [str(self.verifier), 'lyra-inspect-project',
            f'--project-context={self.project}', f'--rom={self.rom}', '--format=json'])
        self.assertEqual(json.loads(current.Q.read_bound(request['resource_inspection'])), self.inspection)
        self.assertNotIn(request['resource_inspection'], self.producer['source_bindings'])

    def test_auto_inspection_failure_cannot_publish_snapshot_or_candidate(self):
        self.inspect.side_effect = ValueError('owned inspector refused')
        with self.assertRaisesRegex(ValueError, 'owned inspector refused'):
            current.prepare_ordinary_transfer(self.project, self.output, self.candidate)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.candidate.exists())
        current.A.native_verify.assert_called_once()
        self.inspect.assert_called_once_with(self.verifier, self.project, self.rom)

    def test_direct_historical_transfer_keeps_inspection_disabled(self):
        report = current.prepare_transfer(self.project, self.verifier, self.output, self.candidate,
                                          policy_id='historical-fixture')
        request = json.loads((self.output / 'request.json').read_bytes())
        self.assertTrue(report['snapshot_ready'])
        self.assertNotIn('resource_inspection', request)
        self.assertNotIn('native_inspection', request)
        self.inspect.assert_not_called()

    def test_policy_change_during_verifier_does_not_publish_request(self):
        def change_policy(*args):
            self.write_policies([])
            return self.proof
        current.A.native_verify.side_effect = change_policy
        with self.assertRaisesRegex(ValueError, 'changed'):
            current.prepare_ordinary_transfer(self.project, self.output, self.candidate)
        self.assertFalse((self.output / 'request.json').exists())
        self.assertFalse(self.candidate.exists())

    def test_policy_change_during_marker_write_removes_marker(self):
        write_outputs = current.P.write_outputs
        def write_and_change(folder, files, **kwargs):
            result = write_outputs(folder, files, **kwargs)
            if 'request.json' in files:
                self.write_policies([])
            return result
        with mock.patch.object(current.P, 'write_outputs', side_effect=write_and_change):
            with self.assertRaisesRegex(ValueError, 'changed'):
                current.prepare_ordinary_transfer(self.project, self.output, self.candidate)
        self.assertFalse((self.output / 'request.json').exists())
        self.assertFalse(self.candidate.exists())

    def test_auto_transfer_command_uses_bound_identity(self):
        args = ['lyra_project_prepare.py', '--current-save-transfer', '--auto-ordinary',
                '--project', str(self.project), '--output', str(self.output),
                '--candidate', str(self.candidate)]
        captured = io.StringIO()
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(captured):
            self.assertEqual(prepare.main(), 0)
        report = json.loads(captured.getvalue())
        self.assertTrue(report['snapshot_ready'])
        self.assertFalse(report['ordinary_build_ready'])
        request = json.loads((self.output / 'request.json').read_bytes())
        self.assertEqual(request['allocation_policy_id'], 'ordinary-fixture')
        self.assertFalse(self.candidate.exists())
        self.inspect.assert_called_once_with(self.verifier, self.project, self.rom)
        self.assertEqual(current.inspection_execution(request)['observation'], request['resource_inspection'])

    def test_auto_transfer_command_checks_engine_before_success(self):
        engine = self.root / 'engine'
        engine.mkdir()
        args = ['lyra_project_prepare.py', '--current-save-transfer', '--auto-ordinary',
                '--project', str(self.project), '--output', str(self.output),
                '--candidate', str(self.candidate), '--validate-build-engine', str(engine)]
        captured = io.StringIO()
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stdout(captured), \
             mock.patch.object(publisher, 'resolve_current_target',
                               return_value={'engine': str(engine)}) as validate:
            self.assertEqual(prepare.main(), 0)
        validate.assert_called_once_with(self.project, request=self.output / 'request.json',
                                         candidate=self.candidate)
        self.assertTrue(json.loads(captured.getvalue())['snapshot_ready'])

    def test_auto_transfer_command_refuses_another_engine(self):
        engine = self.root / 'engine'
        foreign = self.root / 'foreign-engine'
        engine.mkdir()
        foreign.mkdir()
        args = ['lyra_project_prepare.py', '--current-save-transfer', '--auto-ordinary',
                '--project', str(self.project), '--output', str(self.output),
                '--candidate', str(self.candidate), '--validate-build-engine', str(engine)]
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stderr(io.StringIO()), \
             mock.patch.object(publisher, 'resolve_current_target', return_value={'engine': str(foreign)}):
            with self.assertRaises(SystemExit) as error:
                prepare.main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(self.candidate.exists())

    def test_auto_transfer_command_rejects_external_verifier_override(self):
        args = ['lyra_project_prepare.py', '--current-save-transfer', '--auto-ordinary',
                '--project', str(self.project), '--output', str(self.output),
                '--candidate', str(self.candidate), '--z3ed', str(self.verifier)]
        with mock.patch.object(sys, 'argv', args), contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit) as error:
                prepare.main()
        self.assertEqual(error.exception.code, 1)
        self.assertFalse(self.output.exists())
        current.A.native_verify.assert_not_called()
        self.inspect.assert_not_called()

    def test_auto_transfer_does_not_snapshot_preview_policy(self):
        policy = copy.deepcopy(self.policy)
        policy['current_runtime'].update(kind=current.PREVIEW_POLICY_KIND,
                                         scope=current.PREVIEW_SCOPE)
        self.write_policies([policy])
        with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'):
            current.prepare_ordinary_transfer(self.project, self.output, self.candidate)
        self.assertFalse(self.output.exists())
        self.assertFalse(self.candidate.exists())
        current.A.native_verify.assert_not_called()
        self.inspect.assert_not_called()

    def test_preview_or_private_pilot_is_not_selected_for_ordinary_build(self):
        for change in ('preview', 'pilot'):
            with self.subTest(change=change):
                policy = copy.deepcopy(self.policy)
                if change == 'preview':
                    policy['current_runtime'].update(kind=current.PREVIEW_POLICY_KIND,
                                                     scope=current.PREVIEW_SCOPE)
                else:
                    policy['current_runtime']['private_pilot'] = {}
                self.write_policies([policy])
                with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'):
                    current.select_ordinary_transfer_inputs(self.project)
        self.assertFalse(self.output.exists())
        current.A.native_verify.assert_not_called()

    def test_foreign_or_ambiguous_producers_do_not_select_a_policy(self):
        foreign = copy.deepcopy(self.policy)
        foreign['producer_identity_sha256'] = 'f' * 64
        self.write_policies([foreign])
        with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'):
            current.select_ordinary_transfer_inputs(self.project)
        other = copy.deepcopy(self.policy)
        other['id'] = 'another-ordinary'
        self.write_policies([self.policy, other])
        with self.assertRaisesRegex(ValueError, 'CURRENT_ORDINARY_POLICY_REQUIRED'):
            current.select_ordinary_transfer_inputs(self.project)
        self.assertFalse(self.output.exists())

    def test_changed_ledger_during_selection_is_rejected(self):
        recheck = current._recheck
        def change_ledger(live):
            recheck(live)
            self.write_policies([])
        with mock.patch.object(current, '_recheck', side_effect=change_ledger):
            with self.assertRaisesRegex(ValueError, 'changed|hash|SHA|binding'):
                current.select_ordinary_transfer_inputs(self.project)
        self.assertFalse(self.output.exists())
