"""Publisher proofs use memory only; no assembler, emulator or ROM-file writes."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_publisher as P
import lyra_project_admission as A
import lyra_project_composition as C
import lyra_project_allocation as R

REQUEST = Path('/Users/scawful/.context/projects/oracle-of-secrets/scratchpad/handoffs/'
    'christmas_completion_2026-10-20/credit-phase/composition/REQUEST.json')


class PublisherContextTest(unittest.TestCase):
    def test_only_verified_current_native_receipts_allow_publication(self):
        digest = 'a' * 64
        valid = dict(kind=P.PUBLICATION['compiled_reader_variant'],
                     compiled_consumers_verified=True, compiled_rom_sha256=digest,
                     production_admission=False, save_exit_policy='held', runtime_verified=False)
        self.assertIs(P.require_verified_native_receipt(valid, digest), valid)
        for update in ({'kind': 'lyra.unverified_inspection.v1'},
                       {'compiled_consumers_verified': False},
                       {'compiled_rom_sha256': 'b' * 64},
                       {'production_admission': True}, {'save_exit_policy': 'new_destination'}):
            with self.subTest(update=update), self.assertRaisesRegex(ValueError, 'Native loader receipt'):
                P.require_verified_native_receipt(dict(valid, **update), digest)
        for incomplete in (None, {}, {'kind': valid['kind']}):
            with self.subTest(incomplete=incomplete), self.assertRaisesRegex(ValueError, 'Native loader receipt'):
                P.require_verified_native_receipt(incomplete, digest)

    def test_unselected_prepare_overwrites_stale_context_without_reading_private_inputs(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            (folder / 'runtime_constants.asm').write_text('!LYRA_PROJECT_DATA_PRESENT=1')
            with mock.patch.object(P, 'make_plan', side_effect=AssertionError('Must not inspect a project')):
                plan = P.prepare(folder)
            self.assertFalse(plan['selected'])
            self.assertIn('!LYRA_PROJECT_DATA_PRESENT = 0', (folder / 'runtime_constants.asm').read_text())
            self.assertNotIn('incbin', (folder / 'runtime_data.asm').read_text())
            self.assertEqual((folder / 'binaries/payload.bin').read_bytes(), b'')
            with self.assertRaisesRegex(ValueError, 'requires a selected'):
                P.prepare(folder, request='unselected-request.json')

    def test_project_references_follow_opened_descriptor_and_ignore_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            for name in ('base.sfc', 'terrain.json', 'request.json'):
                (folder / name).write_text('fixture')
            project = folder / 'fixture.yaze'
            project.write_text('[files]\nrom_filename=base.sfc\nlyra_terrain_file=terrain.json\n'
                               'lyra_build_request_file=request.json\n[rom]\nrole=dev\n')
            context = P.project_context(project)
            self.assertEqual(context, (project, folder / 'base.sfc', folder / 'terrain.json', folder / 'request.json'))
            project.write_text('[DEFAULT]\nrom_filename=base.sfc\n[files]\nlyra_terrain_file=terrain.json\n'
                               'lyra_build_request_file=request.json\n[rom]\nrole=dev\n')
            with self.assertRaisesRegex(ValueError, 'no rom_filename'):
                P.project_context(project)

    def test_current_authorization_is_specific_and_does_not_grant_general_allocation(self):
        ledger = json.loads(R.LEDGER.read_bytes())
        claim = next(c for c in ledger['rom_candidate_reservations'] if c['id'] == R.CLAIM)
        claim['ordinary_build_publication'] = copy.deepcopy(P.PUBLICATION)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'ledger.json'
            path.write_bytes(P.encoded(ledger))
            self.assertEqual(P.publication_authorization(path)[0], claim)
            for update in ({'selected_maps': [37, 161]}, {'production_admission': True}, {'enabled': False}):
                bad = copy.deepcopy(ledger)
                next(c for c in bad['rom_candidate_reservations'] if c['id'] == R.CLAIM)[
                    'ordinary_build_publication'].update(update)
                path.write_bytes(P.encoded(bad))
                with self.assertRaisesRegex(ValueError, 'does not authorize'):
                    P.publication_authorization(path)
            ledger['allocation_available'] = True
            path.write_bytes(P.encoded(ledger))
            with self.assertRaisesRegex(ValueError, 'general free-space'):
                P.publication_authorization(path)

    def test_descriptor_keeps_raw_minus_one_and_uses_effective_zero(self):
        props = dict(graphics_sheets=list(range(8)), main_palette=2, palette_set=3, animated_sheet=4,
                     sprite_graphics=[-1] * 3, sprite_palettes=[-1] * 3, music=[0] * 4)
        raw, report = P.descriptor_payload(props)
        self.assertEqual(len(raw), 64)
        self.assertEqual(raw[:12], b'LYR1\x01\xa1\x00\xa1' + bytes([0xA1]) * 4)
        self.assertEqual(raw[12:20], bytes(range(8)))
        self.assertEqual(raw[20:32], bytes([2, 3, 4, 0x30, 0x30, 0, 0, 0, 0x10, 7, 0, 0]))
        self.assertEqual(raw[32:], bytes(32))
        self.assertEqual(report['raw_source_phase']['sprite_graphics'], [-1] * 3)
        props['sprite_graphics'] = [255] * 3
        with self.assertRaisesRegex(ValueError, 'phase selectors'):
            P.descriptor_payload(props)

    def test_shared_payload_refactor_preserves_public_report_shape(self):
        from types import SimpleNamespace
        source = bytes(0x400000)
        rows = A.relocated_table_payloads(source, None, SimpleNamespace(maps=[]), [])
        self.assertEqual(A.relocated_table_plan(source, None, SimpleNamespace(maps=[]), []),
                         [{k: v for k, v in row.items() if k != 'payload_hex'} for row in rows])
        self.assertEqual(len(rows), 30)
        for row in rows:
            self.assertEqual(A.sha(bytes.fromhex(row['payload_hex'])), row['proposed_sha256'])

    def test_generated_output_refuses_symlinks_and_input_aliases(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory).resolve()
            source = folder / 'input.json'
            source.write_text('saved input')
            (folder / 'link.json').symlink_to(source)
            for name in ('input.json', 'link.json'):
                with self.assertRaises(ValueError):
                    P.write_outputs(folder, {name: b'changed'}, protected=[source])
            self.assertEqual(source.read_text(), 'saved input')

    def test_build_stages_verify_before_output_hash_and_snapshot_all_generated_inputs(self):
        script = (ROOT / 'Scripts/Build/build_rom.sh').read_text()
        checks = (ROOT / 'Scripts/Build/build_checks.sh').read_text()
        self.assertLess(script.index('snapshot_build_outputs'), script.index('run_check lyra_prepare'))
        self.assertLess(script.index('run_check lyra_prepare'), script.index('receipt snapshot --phase pre_assembly'))
        self.assertLess(script.index('run_check lyra_verify'), script.index('receipt artifact --name output_rom'))
        for name in P.GENERATED_FILES:
            self.assertIn('Data/Generated/lyra_project/' + name, checks)
        self.assertIn('oos${version}x.lyra-verification.json', checks)
        self.assertIn('-DLYRA_BUILD_CONTEXT=1', script)


@unittest.skipUnless(REQUEST.exists(), 'Exact private saved inputs are unavailable in CI')
class ActualPublisherDataTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        original = json.loads(REQUEST.read_bytes())
        if not all(Path(original[key]).exists() for key in P.ROLES):
            raise unittest.SkipTest('Exact historical inputs unavailable')
        cls.directory = tempfile.TemporaryDirectory()
        cls.folder = Path(cls.directory.name).resolve()
        cls.request = cls.folder / 'request.json'
        cls.request.write_bytes(P.encoded({key: original[key] for key in P.ROLES}))
        cls.base = Path(original['saved_rom'])
        cls.project = cls.folder / 'private.yaze'
        cls.project.write_text('[files]\nrom_filename=' + str(cls.base) + '\nlyra_terrain_file='
            + original['terrain'] + '\nlyra_build_request_file=request.json\n[rom]\nrole=dev\n')
        # Private preparation test only: does not authorize native code or change
        # the source ledger. Native-owner tests verify the real runtime variant.
        ledger = json.loads(R.LEDGER.read_bytes())
        next(c for c in ledger['rom_candidate_reservations'] if c['id'] == R.CLAIM)[
            'ordinary_build_publication'] = copy.deepcopy(P.PUBLICATION)
        cls.ledger = cls.folder / 'ledger.json'
        cls.ledger.write_bytes(P.encoded(ledger))
        cls.plan = P.make_plan(cls.project, cls.base, ledger_path=cls.ledger)
        cls.saved = cls.base.read_bytes()
        cls.proposed = C.apply_writes(cls.saved, cls.plan['writes'])

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def test_actual_data_readback_full_tables_and_isolated_descriptor(self):
        plan = self.plan
        result = P.verify_data(self.saved, self.proposed, plan['writes'],
            dict(enumerate(A.read_tile32(self.saved, i) for i in range(0x4540))),
            {row['tile32_id']: tuple(row['quadrants']) for row in plan['emitted_definitions']},
            plan['targets']['native37'], plan['targets']['a1'])
        self.assertEqual(result['legacy_tables_verified'], 30)
        self.assertEqual(plan['stream_bytes'], 1036)
        self.assertEqual(plan['stream_capacity'], 2072)
        self.assertEqual(plan['production_maps'], [])
        self.assertEqual(plan['production_edge_ids'], [])
        self.assertEqual(self.proposed[P.DESCRIPTOR_PC:P.DESCRIPTOR_PC + 64].hex(), plan['descriptor']['payload_hex'])

    def test_actual_readback_refuses_one_legacy_row_drift_even_with_valid_generated_data(self):
        changed = bytearray(self.proposed)
        changed[A.pc(0x288160)] ^= 1
        with self.assertRaisesRegex(ValueError, 'Final legacy table prefix differs: main_palette'):
            P.verify_data(self.saved, bytes(changed), self.plan['writes'],
                dict(enumerate(A.read_tile32(self.saved, i) for i in range(0x4540))),
                {row['tile32_id']: tuple(row['quadrants']) for row in self.plan['emitted_definitions']},
                self.plan['targets']['native37'], self.plan['targets']['a1'])

    def test_new_plan_does_not_bind_any_output_rom_symbols_or_receipt(self):
        self.assertEqual(set(json.loads(self.request.read_bytes())), set(P.ROLES))
        self.assertNotIn('rom', P.ROLES)
        files = P.render_outputs(self.plan)
        self.assertIn('!LYRA_TABLE_bg_color = $28C000', files['runtime_constants.asm'].decode())
        self.assertIn('org $28C000\nLyraRuntime_bg_color:', files['runtime_data.asm'].decode())
        self.assertIn('LyraRuntime_map32_high:', files['runtime_data.asm'].decode())
        self.assertIn('Lyra_A1Descriptor:', files['runtime_data.asm'].decode())
        payload = files['binaries/payload.bin']
        self.assertEqual(payload, b''.join(bytes.fromhex(row['payload_hex']) for row in self.plan['writes']))
        self.assertEqual(len(self.plan['emitted_definitions']), 55)
        self.assertTrue(all(not (A.CODE_START <= row['pc'][0] < P.DESCRIPTOR_PC) for row in self.plan['writes']))

    def test_changed_historical_source_role_refuses_and_does_not_write_a_plan(self):
        request = json.loads(self.request.read_bytes())
        request['frozen_assignment'] = request['historical_ledger']
        path = self.folder / 'wrong-request.json'
        path.write_bytes(P.encoded(request))
        with self.assertRaisesRegex(ValueError, 'Historical publisher input differs'):
            P.make_plan(self.project, self.base, path, ledger_path=self.ledger)

    def test_verify_passes_actual_descriptor_slice_to_strict_native_verifier_and_preserves_inputs(self):
        from types import SimpleNamespace
        output = self.folder / 'strict-refusal'
        files = P.render_outputs(self.plan)
        P.write_outputs(output, files)
        compiled = bytearray(self.proposed)
        compiled[P.DESCRIPTOR_PC] ^= 1
        compiled_path, symbols_path = self.folder / 'memory-only-compiled', self.folder / 'memory-only-symbols'
        native = SimpleNamespace(verify_native_loaders=mock.Mock(side_effect=ValueError('native descriptor refusal')))
        original_read = Path.read_bytes

        def read(path):
            if path == compiled_path:
                return bytes(compiled)
            if path == symbols_path:
                return b'memory symbols fixture'
            return original_read(path)

        receipt = self.folder / 'must-not-exist.json'
        with mock.patch.object(Path, 'read_bytes', read), mock.patch.object(P.importlib, 'import_module', return_value=native):
            with self.assertRaisesRegex(ValueError, 'native descriptor refusal'):
                P.verify(output, compiled_path, symbols_path, receipt=receipt)
        actual = native.verify_native_loaders.call_args.args[3]
        self.assertEqual(actual, bytes(compiled[P.DESCRIPTOR_PC:P.DESCRIPTOR_PC + 64]))
        self.assertNotEqual(actual.hex(), self.plan['descriptor']['payload_hex'])
        self.assertFalse(receipt.exists())
        self.assertTrue(all((output / name).read_bytes() == raw for name, raw in files.items()))

    def test_missing_native_verifier_is_a_hard_refusal(self):
        output = self.folder / 'missing-native'
        P.write_outputs(output, P.render_outputs(self.plan))
        original_read = Path.read_bytes
        compiled_path, symbols_path = self.folder / 'memory-only-compiled2', self.folder / 'memory-only-symbols2'

        def read(path):
            return self.proposed if path == compiled_path else b'fixture symbols' if path == symbols_path else original_read(path)

        with mock.patch.object(Path, 'read_bytes', read), mock.patch.object(P.importlib, 'import_module',
                side_effect=ModuleNotFoundError('lyra_native_loaders')):
            with self.assertRaises(ModuleNotFoundError):
                P.verify(output, compiled_path, symbols_path, receipt=self.folder / 'missing-native-receipt.json')
        self.assertFalse((self.folder / 'missing-native-receipt.json').exists())


if __name__ == '__main__':
    unittest.main()
