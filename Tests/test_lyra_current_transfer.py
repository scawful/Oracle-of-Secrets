"""Current-save lifetime and normal adapter refusal using owned host fixtures."""
import copy
import configparser
import json
import os
from pathlib import Path
import sys
import subprocess
import tempfile
import unittest
from unittest import mock
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
from test_lyra_project_admission import document, observation, source_rom


class CurrentSaveTransferTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name).resolve()
        self.source_ledger = json.loads(Path(X.R.LEDGER).read_bytes())
        self.project_root = self.root / 'project'
        self.project_root.mkdir()
        self.project = self.project_root / 'project.yaze'
        self.rom = self.project_root / 'native.bin'
        self.terrain = self.project_root / 'terrain.json'
        self.receipt = Path(str(self.project) + '.native-save.json')
        self.context_path = self.root / 'appdata' / 'native-saves' / (X.R.sha(str(self.rom).encode()) + '.json')
        self.context_path.parent.mkdir(parents=True)
        self.producer_path = self.project_root / 'producer.json'
        self.enforcement = self.project_root / 'transfer-proof.json'
        self.output = self.root / 'snapshot'
        self.candidate = self.root / 'compiled.sfc'
        self.verifier = self.root / 'verifier'
        self.project.write_text('[rom]\nrole=dev\n[files]\nrom_filename=native.bin\n'
            'lyra_terrain_file=terrain.json\nsymbols_filename=resource.bin\n'
            'native_save_producer_file=producer.json\n'
            'native_save_transfer_proof_file=transfer-proof.json\n')
        self.rom.write_bytes(source_rom())
        data = document()
        data['maps'][0]['tiles16'][0][0] = 1
        self.terrain.write_bytes(X.P.encoded(data))
        (self.project_root / 'resource.bin').write_bytes(b'resource.bin')
        for name in ('editor', 'verifier', 'producer-source.cc', 'producer-test.log'):
            (self.root / name).write_bytes(name.encode())
        self.producer = dict(kind=X.PRODUCER_KIND, source_head='a' * 40,
            editor=X.Q.bound(self.root / 'editor'), verifier=X.Q.bound(self.verifier),
            source_bindings=[X.Q.bound(self.root / 'producer-source.cc')])
        self.producer_path.write_bytes(X.P.encoded(self.producer))
        self.inputs = {key: X.Q.bound(path) for key, path in sorted(dict(project=self.project,
            rom=self.rom, terrain=self.terrain, **{'dependency.symbols_filename': self.project_root / 'resource.bin'}).items())}
        self.save = dict(kind=X.SAVE_KIND, generation=1, operation_id=str(uuid.uuid4()), operation='save',
            receipt_path=str(self.receipt), artifacts=self.artifacts(self.inputs),
            bindings_complete=True, binding_errors=[])
        self.receipt.write_bytes(X.P.encoded(self.save))
        self.context = dict(kind=X.CONTEXT_KIND, editing_source_path=str(self.rom),
            project_path=str(self.project), rom_path=str(self.rom),
            producer=next(row for row in self.save['artifacts'] if row['role'] == 'producer'),
            state='committed', native_commit=dict(receipt_path=str(self.receipt),
                generation=1, operation_id=self.save['operation_id']))
        self.context_path.write_bytes(X.P.encoded(self.context))
        self.context_environment = mock.patch.dict(os.environ, {'YAZE_NATIVE_SAVE_CONTEXT': str(self.context_path)})
        self.context_environment.start()
        self.addCleanup(self.context_environment.stop)
        self.proof = observation(self.rom.read_bytes(), data)[1]
        self.proof['terrain_sha256'] = X.R.sha(self.terrain.read_bytes())
        self.native = mock.patch.object(X.A, 'native_verify', return_value=self.proof)
        self.native.start()
        self.addCleanup(self.native.stop)

    def prepare(self, **kwargs):
        report = X.prepare_transfer(self.project, self.verifier, self.output, self.candidate,
                                    policy_id='host-fixture-only', **kwargs)
        return report, Path(report['request'])

    def next_save(self):
        self.save['generation'] += 1
        self.save['operation_id'] = str(uuid.uuid4())
        self.receipt.write_bytes(X.P.encoded(self.save))
        self.context['native_commit'] = dict(receipt_path=str(self.receipt), generation=self.save['generation'],
                                             operation_id=self.save['operation_id'])
        self.context_path.write_bytes(X.P.encoded(self.context))

    def test_native_policy_uses_actual_capture_not_a_future_producer_record(self):
        _, request_path = self.prepare()
        request = json.loads(request_path.read_bytes())
        execution = X.native_execution(request)
        self.assertEqual(execution['binary'], self.producer['verifier'])
        self.assertEqual(execution['observation'], request['observation'])
        ledger, policy, _ = self.grant_fixture(request_path)
        policy.update(kind=X.NATIVE_POLICY_KIND,
                      enforcement=dict(owner='oracle.current_builder', required_order=X.COMPILE_ORDER))
        self.write_fixture_ledger(ledger, policy)
        self.enforcement.unlink()  # fixture-only legacy record, never production evidence
        plan, _ = X.plan_transfer(request_path, self.project, self.rom,
                                 current_source_profile=self.current_profile)
        self.assertEqual(plan['enforcement_receipt'], request['native_verification'])
        self.assertEqual(plan['enforcement_owner'], 'oracle.current_builder')
        self.assertEqual(plan['producer_enforcement_scope'], 'native_save_only')
        self.assertFalse(plan['oracle_compile_order_verified'])
        self.assertFalse(self.enforcement.exists())
        self.assertFalse(self.candidate.exists())
        policy['enforcement']['owner'] = 'unverified producer'
        self.write_fixture_ledger(ledger, policy)
        with self.assertRaisesRegex(ValueError, 'COMPILE_ORDER_OWNER_MISMATCH'):
            X.plan_transfer(request_path, self.project, self.rom,
                            current_source_profile=self.current_profile)

    def test_native_execution_semantics_reject_rebound_wrong_or_failed_verifier(self):
        _, request_path = self.prepare()
        original = json.loads(request_path.read_bytes())
        artifact = Path(original['native_verification']['path'])
        before = artifact.read_bytes()
        for change in (dict(exit_code=1), dict(generation=2), dict(source_rom_sha256='0'*64),
                       dict(command=['verifier did not run this command']),
                       dict(binary=self.producer['editor']), dict(source_bindings=[])):
            execution = json.loads(before); execution.update(change)
            artifact.chmod(0o644); artifact.write_bytes(X.P.encoded(execution)); artifact.chmod(0o444)
            request = copy.deepcopy(original)
            request['native_verification'] = X.Q.bound(artifact)
            request['transfer_id'] = X._identity(request)
            request_path.chmod(0o644); request_path.write_bytes(X.P.encoded(request)); request_path.chmod(0o444)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'VERIFIER_EXECUTION_MISMATCH'):
                X.verify_transfer(request_path, self.project, self.rom)

    def test_failed_native_verifier_cannot_emit_an_execution_or_snapshot(self):
        with mock.patch.object(X.A, 'native_verify', side_effect=ValueError('selected verifier failed')):
            with self.assertRaisesRegex(ValueError, 'selected verifier failed'):
                self.prepare()
        self.assertFalse(self.output.exists())

    def artifacts(self, inputs):
        rows = [dict(role='sidecar' if key == 'terrain' else key, **binding,
                     bytes=Path(binding['path']).stat().st_size) for key, binding in sorted(inputs.items())]
        return [*rows, dict(role='producer', **self.producer['editor'],
                           bytes=Path(self.producer['editor']['path']).stat().st_size)]

    def use_serialized_project(self):
        # Actual saved descriptor excerpt; configure supported fields on an
        # owned copy. This is consumer host proof, not a real Save receipt.
        fixture = ROOT / 'Tests/fixtures/lyra_current_transfer/serialized_project.yaze'
        config = configparser.ConfigParser(interpolation=None)
        config.read_string(fixture.read_text())
        files = config['files']
        native, terrain = self.rom.read_bytes(), self.terrain.read_bytes()
        self.rom = self.project_root / files['rom_filename']
        self.terrain = self.project_root / files['lyra_terrain_file']
        self.terrain.parent.mkdir(parents=True, exist_ok=True)
        self.rom.write_bytes(native)
        self.terrain.write_bytes(terrain)
        # This literal list follows7db ProjectSaveSources, independently of X's
        # classification table, so omitted/misnamed roles cannot pass by reuse.
        fields = ('labels_filename', 'symbols_filename', 'cutscene_shots',
                  'overworld_graphics_preview', 'dungeon_tile_patterns', 'custom_collision_json',
                  'hack_manifest_file', 'sprite_catalog_file', 'terrain_catalog_file', 'palette_catalog_file')
        paths = dict(project=self.project, rom=self.rom, terrain=self.terrain)
        for field in fields:
            if not files[field]:
                files[field] = 'assets/typed/' + field + '.txt'
            path = self.project_root / files[field]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(('explicit source ' + field).encode())
            paths['dependency.' + field] = path
        files['rom_backup_folder'] = 'uncreated/backups'
        files['output_folder'] = 'uncreated/output'
        files['sprite_source_root'] = 'assets/sprite-sources'
        self.directory_roots = {}
        for field in ('code_folder', 'assets_folder', 'patches_folder', 'custom_objects_folder', 'sprite_source_root'):
            path = self.project_root / files[field]
            path.mkdir(parents=True, exist_ok=True)
            self.directory_roots[field] = path
        relative = self.project_root / 'extra-roms/relative one.sfc'
        absolute = self.root / 'absolute extra.sfc'
        relative.parent.mkdir()
        relative.write_bytes(native)
        absolute.write_bytes(native)
        files['additional_roms'] = f' ,\textra-roms/relative one.sfc , , {absolute}\t,extra-roms/relative one.sfc, '
        for index, path in enumerate((relative, absolute, relative)):
            paths[f'dependency.additional_roms.{index}'] = path
        files['native_save_producer_file'] = self.producer_path.name
        files['native_save_transfer_proof_file'] = self.enforcement.name
        with self.project.open('w') as handle:
            config.write(handle)
        self.inputs = {role: X.Q.bound(path) for role, path in sorted(paths.items())}
        self.save['artifacts'] = self.artifacts(self.inputs)
        self.context['rom_path'] = str(self.rom)
        self.next_save()
        return config

    def test_normal_serialized_project_binds_files_and_csv_without_directory_reads_or_scans(self):
        config = self.use_serialized_project()
        read = Path.read_bytes
        def file_only(path):
            self.assertFalse(path.is_dir(), f'Directory read attempted: {path}')
            return read(path)
        with (mock.patch.object(Path, 'read_bytes', autospec=True, side_effect=file_only),
              mock.patch.object(Path, 'iterdir', side_effect=AssertionError('Directory scan attempted')),
              mock.patch.object(Path, 'rglob', side_effect=AssertionError('Recursive scan attempted')),
              mock.patch.object(os, 'scandir', side_effect=AssertionError('Directory scan attempted'))):
            report, request = self.prepare()
            data, source, parsed = X.verify_transfer(request, self.project, self.rom)
        self.assertTrue(report['snapshot_ready'])
        self.assertEqual(set(data['inputs']), set(self.inputs))
        self.assertFalse((self.project_root / config['files']['rom_backup_folder']).exists())
        self.assertFalse((self.project_root / config['files']['output_folder']).exists())
        for field in X.DIRECTORY_REFERENCES:
            self.assertTrue(config['files'][field])
            self.assertNotIn('dependency.' + field, data['inputs'])
        self.assertEqual(data['inputs']['dependency.additional_roms.0']['sha256'],
                         data['inputs']['dependency.additional_roms.2']['sha256'])
        self.assertEqual(data['live']['inputs']['dependency.additional_roms.0']['path'],
                         data['live']['inputs']['dependency.additional_roms.2']['path'])
        self.assertEqual(data['live']['inputs']['dependency.additional_roms.1']['path'],
                         str(self.root / 'absolute extra.sfc'))

    def test_unscanned_directory_contents_only_bind_when_producer_declares_a_child_file(self):
        self.use_serialized_project()
        decoys = [self.directory_roots[field] / ('decoy-' + field + '.bin')
                  for field in ('code_folder', 'assets_folder', 'sprite_source_root')]
        for path in decoys:
            path.write_bytes(b'unlisted source')
        report, request = self.prepare()
        for path in decoys:
            path.write_bytes(b'changed unlisted source')
        X.verify_transfer(request, self.project, self.rom)
        child = decoys[-1]
        self.save['artifacts'].append(dict(role='dependency.sprite_0_source', **X.Q.bound(child), bytes=child.stat().st_size))
        self.next_save()
        self.output = self.root / 'snapshot-with-explicit-child'
        report, request = self.prepare()
        data, _, _ = X.verify_transfer(request, self.project, self.rom)
        self.assertIn('dependency.sprite_0_source', data['inputs'])
        child.write_bytes(b'changed declared source')
        with self.assertRaisesRegex(ValueError, 'retired.*Current saved input changed'):
            X.verify_transfer(request, self.project, self.rom)

    def test_receipt_binding_live_planning_refuses_until_a_new_save(self):
        plan = self.root / 'live.plan.json'
        plan.write_bytes(b'{"schema":"yaze.plan/1"}')
        with self.project.open('a') as handle:
            handle.write(f'[planning]\nfile={plan}\n')
        self.inputs['project'] = X.Q.bound(self.project)
        self.save['artifacts'] = [*self.artifacts(self.inputs),
            dict(role='dependency.planning', **X.Q.bound(plan), bytes=plan.stat().st_size)]
        self.next_save()
        with self.assertRaisesRegex(ValueError, 'NATIVE_SAVE_RECEIPT_BINDS_LIVE_PLANNING.*new native Save'):
            self.prepare()
        self.save['artifacts'] = self.artifacts(self.inputs)
        self.next_save()
        report, request = self.prepare()
        self.assertTrue(report['snapshot_ready'])
        plan.write_bytes(b'{"schema":"yaze.plan/1","status":"agent edit"}')
        data, _, _ = X.verify_transfer(request, self.project, self.rom)
        self.assertNotIn('dependency.planning', data['inputs'])

    def test_each_modeled_file_and_additional_rom_mutation_retires_normal_descriptor(self):
        self.use_serialized_project()
        report, request = self.prepare()
        roles = [role for role in self.inputs if role.startswith('dependency.')]
        self.assertEqual(len(roles), 13)
        for role in roles:
            path = Path(self.inputs[role]['path'])
            before = path.read_bytes()
            try:
                path.write_bytes(before + b'changed')
                with self.subTest(role=role), self.assertRaises(ValueError):
                    X.verify_transfer(request, self.project, self.rom)
            finally:
                path.write_bytes(before)
        X.verify_transfer(request, self.project, self.rom)

    def test_missing_or_directory_valued_true_files_and_csv_entries_still_refuse(self):
        self.use_serialized_project()
        for role in ('dependency.symbols_filename', 'dependency.additional_roms.1'):
            path = Path(self.inputs[role]['path'])
            before = path.read_bytes()
            path.unlink()
            try:
                with self.subTest(role=role), self.assertRaises(FileNotFoundError):
                    self.prepare()
                self.assertFalse(self.output.exists())
            finally:
                path.write_bytes(before)
        path = Path(self.inputs['dependency.symbols_filename']['path'])
        path.unlink()
        path.mkdir()
        with self.assertRaisesRegex(ValueError, 'symbols_filename is not a regular file'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_unknown_configured_reference_is_not_silently_omitted(self):
        with self.project.open('a') as handle:
            handle.write('future_source_file=resource.bin\n')
        with self.assertRaisesRegex(ValueError, 'Unsupported typed.*future_source_file'):
            self.prepare()

    def grant_fixture(self, request_path):
        # This temporary fixture policy is not a repository or production grant.
        request = json.loads(request_path.read_bytes())
        lo, hi = 13992, 14004
        spans = [[base + lo // 4 * 6, base + hi // 4 * 6] for base in X.A.TILE32_BASES]
        streams = [list(X.V.STREAM)]
        expanded = X.A.expanded_rom(self.rom.read_bytes())
        policy = dict(id='host-fixture-only', kind=X.POLICY_KIND, scope='disposable_build_only',
            producer_identity_sha256=X.Q.bound(self.producer_path)['sha256'],
            tile32_id_range=[lo, hi], stream_ranges=streams,
            preimages=[dict(pc=span, sha256=X.R.sha(expanded[slice(*span)])) for span in spans + streams],
            spare_tile32_ids=[14002, 14003])
        ledger = self.root / 'fixture-ledger.json'
        self.write_fixture_ledger(ledger, policy)
        # Explicitly inject the trusted registry only in this host fixture.
        # Merely passing --ledger cannot supply production authority.
        self.registry_patch = mock.patch.object(X.R, 'LEDGER', ledger)
        self.registry_patch.start()
        self.addCleanup(self.registry_patch.stop)
        proof = dict(kind=X.PROOF_KIND, transfer_id=request['transfer_id'],
            generation=self.save['generation'], operation_id=self.save['operation_id'],
            save_context=X.Q.bound(self.context_path), source_rom_sha256=X.R.sha(self.rom.read_bytes()),
            policy_sha256=X.T.digest(policy), producer=X.Q.bound(self.producer_path),
            source_bindings=self.producer['source_bindings'],
            writer_order=['native_save', 'immutable_snapshot', 'compile_candidate', 'no_native_serializer'],
            verification=dict(binary=self.producer['verifier'], log=X.Q.bound(self.root / 'producer-test.log'),
                command='host fixture protocol proof', tests=['CurrentTransferFixture'], exit_code=0))
        self.enforcement.write_bytes(X.P.encoded(proof))
        # Existing transfer tests isolate native packing/proof ordering; the
        # real current-source validator has independent complete fixtures.
        spans = ((0x1759D, 0x175D2), (0x17691, 0x177CB), (0x177E3, 0x17818))
        layout, _ = X._current_table_layout([row[0] for row in X.A.SPECS]
            + [f'music_phase{i}' for i in range(4)])
        source = self.rom.read_bytes()
        self.current_profile = dict(kind=X.CURRENT_PROFILE_KIND,
            native_reader_preimages=[dict(pc=list(span), sha256=X.R.sha(source[slice(*span)])) for span in spans],
            origins=dict(tables=dict(pc=[0x320000, 0x328000])), table_layout=layout)
        profile_stub = mock.patch.object(X, 'verify_current_native_source_profile')
        profile_stub.start()
        self.addCleanup(profile_stub.stop)
        return ledger, policy, proof

    def write_fixture_ledger(self, path, policy, extra_claims=()):
        value = copy.deepcopy(self.source_ledger)
        value['current_save_transfer_policies'] = [policy]
        value['claims'] = [*value.get('claims', []), *extra_claims]
        path.write_bytes(X.P.encoded(value))

    def test_fresh_snapshot_reconstructs_readers_and_leaves_editable_source_unchanged(self):
        before = {key: X.Q.read_bound(row) for key, row in self.inputs.items()}
        report, request = self.prepare()
        data, source, parsed = X.verify_transfer(request, self.project, self.rom)
        self.assertTrue(report['snapshot_ready'])
        self.assertFalse(report['ready'])
        self.assertFalse(self.candidate.exists())
        self.assertEqual(data['census']['native_maps'], 160)
        self.assertEqual(data['census']['native_planes'], 320)
        self.assertEqual(data['census']['required_definitions'], 1)
        self.assertEqual(data['census']['source_size'], 0x200000)
        self.assertEqual(parsed.maps[0][0], 1)
        self.assertEqual(source, before['rom'])
        for key, row in self.inputs.items():
            self.assertEqual(X.Q.read_bound(row), before[key])
            self.assertTrue(Path(row['path']).stat().st_mode & 0o200)
        self.assertEqual(request.stat().st_mode & 0o222, 0)

    def test_same_bytes_later_save_retires_transfer_and_fresh_generation_regenerates(self):
        first, request = self.prepare()
        original = {key: X.Q.read_bound(row) for key, row in self.inputs.items()}
        self.next_save()
        self.assertEqual({key: X.Q.read_bound(row) for key, row in self.inputs.items()}, original)
        with self.assertRaisesRegex(ValueError, 'retired'):
            X.verify_transfer(request, self.project, self.rom)
        self.output = self.root / 'snapshot-generation2'
        fresh, request = self.prepare()
        self.assertNotEqual(first['transfer_id'], fresh['transfer_id'])
        X.verify_transfer(request, self.project, self.rom)

    def test_incomplete_missing_or_wrong_project_save_receipt_never_publishes_request(self):
        for mutation in (lambda d: d.update(bindings_complete=False),
                         lambda d: d.update(operation_id='local nonce'),
                         lambda d: d.update(binding_errors=['missing configured sidecar']),
                         lambda d: d['artifacts'][0].update(path=str(self.terrain))):
            value = copy.deepcopy(self.save)
            mutation(value)
            self.receipt.write_bytes(X.P.encoded(value))
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.prepare()
            self.assertFalse((self.output / 'request.json').exists())
        self.receipt.unlink()
        with self.assertRaisesRegex(ValueError, 'CURRENT_NATIVE_SAVE_RECEIPT_REQUIRED'):
            self.prepare()

    def test_generation_change_during_native_observation_publishes_no_completion_marker(self):
        def changed(*args):
            self.next_save()
            return self.proof
        with mock.patch.object(X.A, 'native_verify', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'retired'):
                self.prepare()
        self.assertFalse((self.output / 'request.json').exists())

    def test_generation_change_during_snapshot_write_leaves_refusal_not_request(self):
        write = X.P.write_outputs
        def changed(folder, files, **kwargs):
            write(folder, files, **kwargs)
            if 'observation.json' in files:
                self.next_save()
        with mock.patch.object(X.P, 'write_outputs', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'retired'):
                self.prepare()
        self.assertFalse((self.output / 'request.json').exists())
        self.assertTrue((self.output / 'refusal.json').is_file())

    def test_resource_producer_snapshot_and_target_tampering_refuse(self):
        report, request = self.prepare()
        data = json.loads(request.read_bytes())
        path = Path(data['inputs']['terrain']['path'])
        path.chmod(0o644)
        with self.assertRaisesRegex(ValueError, 'immutable'):
            X.verify_transfer(request, self.project, self.rom)
        path.chmod(0o444)
        self.candidate.write_bytes(b'existing output')
        with self.assertRaisesRegex(ValueError, 'new separate4MiB'):
            X.verify_transfer(request, self.project, self.rom)
        self.candidate.unlink()
        (self.project_root / 'resource.bin').write_bytes(b'later resource')
        with self.assertRaisesRegex(ValueError, 'transfer retired.*Current saved input changed'):
            X.verify_transfer(request, self.project, self.rom)

    def test_generic_operation_id_and_missing_session_context_have_explicit_contract(self):
        self.save['operation_id'] = 'native-operation-17'
        self.context['native_commit']['operation_id'] = self.save['operation_id']
        self.receipt.write_bytes(X.P.encoded(self.save))
        self.context_path.write_bytes(X.P.encoded(self.context))
        with mock.patch.dict(os.environ, {'YAZE_NATIVE_SAVE_CONTEXT': ''}):
            with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_CONTEXT_REQUIRED'):
                self.prepare()
        report, request = self.prepare()
        X.verify_transfer(request, self.project, self.rom)

    def test_rom_only_completion_does_not_qualify_configured_project(self):
        self.save['artifacts'] = [row for row in self.save['artifacts'] if row['role'] in ('rom', 'producer')]
        self.receipt.write_bytes(X.P.encoded(self.save))
        with self.assertRaisesRegex(ValueError, 'omitted a configured'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_successful_saveas_moves_session_and_retires_old_transfer_without_old_file_writes(self):
        report, request = self.prepare()
        original = {row['path']: X.Q.read_bound(row) for row in self.inputs.values()}
        original[str(self.receipt)] = self.receipt.read_bytes()
        destination = self.root / 'save-as'
        destination.mkdir()
        new_project = destination / self.project.name
        new_inputs = {}
        for role, binding in self.inputs.items():
            path = destination / Path(binding['path']).name
            path.write_bytes(X.Q.read_bound(binding))
            new_inputs[role] = X.Q.bound(path)
        (destination / self.producer_path.name).write_bytes(self.producer_path.read_bytes())
        new_receipt = Path(str(new_project) + '.native-save.json')
        new_save = dict(kind=X.SAVE_KIND, generation=1, operation_id=str(uuid.uuid4()), operation='save_as',
            receipt_path=str(new_receipt), artifacts=self.artifacts(new_inputs),
            bindings_complete=True, binding_errors=[])
        new_receipt.write_bytes(X.P.encoded(new_save))
        self.context.update(project_path=str(new_project), rom_path=new_inputs['rom']['path'], state='committed',
            native_commit=dict(receipt_path=str(new_receipt), generation=1,
                               operation_id=new_save['operation_id']))
        self.context_path.write_bytes(X.P.encoded(self.context))
        with self.assertRaisesRegex(ValueError, 'transfer retired.*Editor context moved'):
            X.verify_transfer(request, self.project, self.rom)
        for path, content in original.items():
            self.assertEqual(Path(path).read_bytes(), content)
        new_report = X.prepare_transfer(new_project, self.verifier, self.root / 'save-as-snapshot',
                                        self.root / 'save-as-compiled.sfc')
        X.verify_transfer(new_report['request'], new_project, destination / self.rom.name)

    def test_project_only_saveas_rebind_retires_old_transfer_without_native_completion(self):
        report, request = self.prepare()
        old = self.receipt.read_bytes()
        rebound = self.root / 'project-only-saveas' / self.project.name
        rebound.parent.mkdir()
        rebound.write_bytes(self.project.read_bytes())
        self.context.update(project_path=str(rebound), state='rebound', native_commit=None)
        self.context_path.write_bytes(X.P.encoded(self.context))
        with self.assertRaisesRegex(ValueError, 'transfer retired.*Editor context moved'):
            X.verify_transfer(request, self.project, self.rom)
        self.context['project_path'] = str(self.project)
        self.context_path.write_bytes(X.P.encoded(self.context))
        with self.assertRaisesRegex(ValueError, 'transfer retired.*CURRENT_SAVE_CONTEXT_REBOUND'):
            X.verify_transfer(request, self.project, self.rom)
        self.assertEqual(self.receipt.read_bytes(), old)
        self.assertFalse(Path(str(rebound) + '.native-save.json').exists())
        self.assertFalse(self.candidate.exists())

    def test_in_project_context_and_boolean_context_generation_refuse(self):
        local = self.project_root / 'native-saves' / self.context_path.name
        local.parent.mkdir()
        local.write_bytes(self.context_path.read_bytes())
        with mock.patch.dict(os.environ, {'YAZE_NATIVE_SAVE_CONTEXT': str(local)}):
            with self.assertRaisesRegex(ValueError, 'outside the project'):
                self.prepare()
        self.context['native_commit']['generation'] = True
        self.context_path.write_bytes(X.P.encoded(self.context))
        with self.assertRaisesRegex(ValueError, 'Live native commit/producer'):
            self.prepare()

    def test_partial_receipt_context_publication_refuses_in_both_orders(self):
        report, request = self.prepare()
        old_receipt = self.receipt.read_bytes()
        old_context = self.context_path.read_bytes()
        self.next_save()
        new_receipt = self.receipt.read_bytes()
        new_context = self.context_path.read_bytes()
        for receipt, context in ((new_receipt, old_context), (old_receipt, new_context)):
            self.receipt.write_bytes(receipt)
            self.context_path.write_bytes(context)
            with self.subTest(receipt=receipt), self.assertRaisesRegex(
                    ValueError, 'transfer retired.*Live native commit/producer'):
                X.verify_transfer(request, self.project, self.rom)
        self.assertFalse(self.candidate.exists())

    def test_cancelled_preparation_removes_own_completion_marker_and_preserves_source(self):
        before = self.rom.read_bytes()
        write = X.P.write_outputs
        def cancelled(folder, files, **kwargs):
            write(folder, files, **kwargs)
            if 'request.json' in files:
                raise KeyboardInterrupt('cancelled host transfer preparation')
        with mock.patch.object(X.P, 'write_outputs', side_effect=cancelled):
            with self.assertRaisesRegex(KeyboardInterrupt, 'cancelled host'):
                self.prepare()
        self.assertFalse((self.output / 'request.json').exists())
        self.assertTrue((self.output / 'refusal.json').exists())
        self.assertEqual(self.rom.read_bytes(), before)
        self.assertFalse(self.candidate.exists())

    def test_headered_receipt_uses_exact_saved_file_hash_and_writer_refuses_unsupported_profile(self):
        native = self.rom.read_bytes()
        headered = bytes(512) + native
        self.rom.write_bytes(headered)
        self.inputs['rom'] = X.Q.bound(self.rom)
        self.save['artifacts'] = self.artifacts(self.inputs)
        self.next_save()
        live = X._live(self.project)
        self.assertEqual(live['inputs']['rom']['sha256'], X.R.sha(headered))
        with self.assertRaisesRegex(ValueError, 'Unsupported current native source size'):
            self.prepare()
        artifact = next(row for row in self.save['artifacts'] if row['role'] == 'rom')
        artifact['sha256'] = X.R.sha(native)
        self.receipt.write_bytes(X.P.encoded(self.save))
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            X._live(self.project)
        self.assertFalse(self.output.exists())

    def test_ungranted_current_policy_refuses_before_historical_renderer_or_compiler(self):
        report, request = self.prepare()
        generated = self.root / 'generated'
        with (mock.patch.object(X.P, 'render_outputs') as render,
              mock.patch.object(X.P, 'compile_saved_plan') as historical):
            with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_ALLOCATION_UNGRANTED'):
                X.P.prepare(generated, project=self.project, base_rom=self.rom, request=request)
        render.assert_not_called()
        historical.assert_not_called()
        self.assertFalse(generated.exists())
        self.assertFalse(self.candidate.exists())

    def test_normal_prepare_cli_exits_nonzero_without_asm_or_output_rom(self):
        report, request = self.prepare()
        result = subprocess.run([sys.executable, str(ROOT / 'Scripts/Build/lyra_project_publisher.py'),
            'prepare', '--project', str(self.project), '--base-rom', str(self.rom),
            '--request', str(request), '--output', str(self.root / 'generated')],
            capture_output=True, text=True, timeout=30)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('CURRENT_SAVE_ALLOCATION_UNGRANTED', result.stderr)
        self.assertFalse((self.root / 'generated').exists())
        self.assertFalse(self.candidate.exists())

    def test_capture_cli_uses_selected_readonly_verifier_and_publishes_only_snapshot(self):
        # A host protocol fixture, not a qualified editor or emulator producer.
        self.verifier.write_text('#!/usr/bin/env python3\nimport sys\nsys.stdout.write('
                                 + repr(json.dumps(self.proof)) + ')\n')
        self.verifier.chmod(0o755)
        self.producer['verifier'] = X.Q.bound(self.verifier)
        self.producer_path.write_bytes(X.P.encoded(self.producer))
        self.receipt.write_bytes(X.P.encoded(self.save))
        result = subprocess.run([sys.executable, str(ROOT / 'Scripts/Build/lyra_project_prepare.py'),
            '--current-save-transfer', '--project', str(self.project), '--z3ed', str(self.verifier),
            '--output', str(self.output), '--candidate', str(self.candidate)],
            capture_output=True, text=True, timeout=30)
        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertTrue(report['snapshot_ready'])
        self.assertFalse(report['ordinary_build_ready'])
        X.verify_transfer(report['request'], self.project, self.rom)
        self.assertFalse(self.candidate.exists())

    def test_caller_authored_registry_cannot_grant_current_transfer_authority(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        self.registry_patch.stop()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_POLICY_AUTHORITY_MISMATCH'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)

    def test_candidate_snapshot_ancestor_and_enforcement_alias_refuse_before_creation(self):
        self.output = self.candidate / 'snapshot'
        with self.assertRaisesRegex(ValueError, 'separate from immutable'):
            self.prepare()
        self.assertFalse(self.candidate.exists())
        self.output = self.root / 'snapshot'
        self.candidate = self.enforcement
        with self.assertRaisesRegex(ValueError, 'proof must be separate'):
            self.prepare()
        self.assertFalse(self.output.exists())

    def test_missing_current_proof_and_historical_source_relabel_refuse(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        self.enforcement.unlink()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_PRODUCER_PROOF_REQUIRED'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        proof['source_rom_sha256'] = X.V.SOURCE
        self.enforcement.write_bytes(X.P.encoded(proof))
        with self.assertRaisesRegex(ValueError, 'stale or does not enforce'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)

    def test_forged_reader_census_and_snapshot_bytes_refuse(self):
        report, request = self.prepare()
        data = json.loads(request.read_bytes())
        data['census']['native_streams_sha256'] = 'f' * 64
        data['transfer_id'] = X._identity(data)
        request.chmod(0o644)
        request.write_bytes(X.P.encoded(data))
        request.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'reader census differs'):
            X.verify_transfer(request, self.project, self.rom)
        snapshot = Path(data['inputs']['rom']['path'])
        snapshot.chmod(0o644)
        raw = bytearray(snapshot.read_bytes())
        raw[0x1000] ^= 1
        snapshot.write_bytes(raw)
        snapshot.chmod(0o444)
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            X.verify_transfer(request, self.project, self.rom)

    def test_reviewed_fixture_transfer_runs_actual_current_compiler_and_reconstructs_all32(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        plan, payload = X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        self.assertTrue(plan['current_source_allocation_verified'])
        self.assertTrue(plan['producer_enforcement_verified'])
        self.assertEqual(plan['retirement'], 'next_native_save')
        self.assertEqual(len(plan['streams']), 64)
        self.assertEqual(len(payload), 32 * 518)
        self.assertEqual(plan['emitted_definitions'], [dict(tile32_id=13992, quadrants=[1, 0, 0, 0])])
        self.assertEqual(plan['native_maps_preserved'], 160)
        self.assertFalse(plan['ordinary_build_ready'])
        self.assertFalse(plan['runtime_admission'])
        self.assertFalse(self.candidate.exists())

    def test_wrong_preimage_conflicting_owner_and_stale_enforcement_proof_refuse(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        changed = copy.deepcopy(policy)
        changed['preimages'][0]['sha256'] = 'f' * 64
        self.write_fixture_ledger(ledger, changed)
        with self.assertRaisesRegex(ValueError, 'preimage differs'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        self.write_fixture_ledger(ledger, policy,
            [dict(id='other_named_owner', space='tile32_id', base=13992, size=1)])
        with self.assertRaisesRegex(ValueError, 'other_named_owner'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        self.write_fixture_ledger(ledger, policy)
        proof['operation_id'] = str(uuid.uuid4())
        self.enforcement.write_bytes(X.P.encoded(proof))
        with self.assertRaisesRegex(ValueError, 'stale or does not enforce'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)

    def test_other_current_policy_is_a_named_owner_even_before_emission(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        value = json.loads(ledger.read_bytes())
        other = copy.deepcopy(policy)
        other['id'] = 'future_current_owner'
        value['current_save_transfer_policies'].append(other)
        ledger.write_bytes(X.P.encoded(value))
        with self.assertRaisesRegex(ValueError, 'future_current_owner'):
            X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)

    def test_generation_change_during_compile_retires_result_before_return(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        compile_plan = X.V.compile_native_plan
        def changed(*args, **kwargs):
            result = compile_plan(*args, **kwargs)
            self.next_save()
            return result
        with mock.patch.object(X.V, 'compile_native_plan', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'retired'):
                X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        self.assertFalse(self.candidate.exists())

    def test_valid_generation2_request_replacement_cannot_qualify_generation1_plan(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        compile_plan = X.V.compile_native_plan
        def replaced(*args, **kwargs):
            result = compile_plan(*args, **kwargs)
            self.next_save()
            data = json.loads(request.read_bytes())
            data['live'] = X._live(self.project)
            snapshot = Path(data['save_snapshot']['path'])
            snapshot.chmod(0o644)
            snapshot.write_bytes(self.receipt.read_bytes())
            snapshot.chmod(0o444)
            data['save_snapshot'] = X.Q.bound(snapshot)
            context_snapshot = Path(data['context_snapshot']['path'])
            context_snapshot.chmod(0o644)
            context_snapshot.write_bytes(self.context_path.read_bytes())
            context_snapshot.chmod(0o444)
            data['context_snapshot'] = X.Q.bound(context_snapshot)
            # This is an explicitly manufactured host G2 fixture. Rebind its
            # complete native-verifier capture as well, so G2 is independently
            # valid and the test reaches the G1-versus-G2 replacement guard.
            execution_path = Path(data['native_verification']['path'])
            execution = json.loads(execution_path.read_bytes())
            execution.update(generation=data['live']['generation'], operation_id=data['live']['operation_id'],
                             save_receipt=data['live']['save_receipt'], save_context=data['live']['save_context'])
            execution_path.chmod(0o644)
            execution_path.write_bytes(X.P.encoded(execution))
            execution_path.chmod(0o444)
            data['native_verification'] = X.Q.bound(execution_path)
            data['transfer_id'] = X._identity(data)
            request.chmod(0o644)
            request.write_bytes(X.P.encoded(data))
            request.chmod(0o444)
            # G2 is valid on its own. It must not validate a result compiled for G1.
            X.verify_transfer(request, self.project, self.rom)
            return result
        with mock.patch.object(X.V, 'compile_native_plan', side_effect=replaced):
            with self.assertRaisesRegex(ValueError, 'request replaced during compilation'):
                X.plan_transfer(request, self.project, self.rom, ledger_path=ledger, current_source_profile=self.current_profile)
        self.assertFalse(self.candidate.exists())

    def test_qualified_data_still_refuses_unadmitted_runtime_before_asm_rendering(self):
        report, request = self.prepare()
        ledger, policy, proof = self.grant_fixture(request)
        with mock.patch.object(X.P, 'render_outputs') as render:
            with self.assertRaisesRegex(ValueError, 'CURRENT_SAVE_RUNTIME_EMISSION_UNADMITTED'):
                X.P.prepare(self.root / 'generated', project=self.project, base_rom=self.rom,
                            request=request, ledger_path=ledger)
        render.assert_not_called()
        self.assertFalse((self.root / 'generated').exists())


if __name__ == '__main__':
    unittest.main()
