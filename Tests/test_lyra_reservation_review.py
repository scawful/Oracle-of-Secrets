"""An ungranted reservation review expires with its selected source or Save."""
import copy
import json
from pathlib import Path
import subprocess
import unittest
from unittest import mock

import test_lyra_current_transfer as fixtures
import lyra_current_transfer as X


class ReservationReviewTest(unittest.TestCase):
    def setUp(self):
        self.case = fixtures.CurrentSaveTransferTest()
        self.case.setUp()
        self.addCleanup(self.case.doCleanups)
        self.root = self.case.root / 'engine'
        self.root.mkdir()
        files = {'Oracle_main.asm': 'incsrc "Config/feature_flags.asm"\n'
                    'incsrc "Overworld/world.asm"\n',
                 'Config/feature_flags.asm': '!FEATURE = 0\n',
                 'Overworld/world.asm': 'org $008000\nAsset: incbin "asset.bin"\n',
                 'Overworld/asset.bin': 'binary fixture',
                 'Core/ZS ROM MAP.txt': 'Fixture ownership documentation only\n',
                 'Scripts/Build/build_rom.sh': '# Fixture; never executed\n',
                 'Config/allocation_ownership.json': json.dumps(dict(schema_version=1,
                     allocation_available=False, claims=[], tables=[]))}
        for name, text in files.items():
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text)
        self.git('init', '-q')
        self.git('config', 'user.name', 'Reservation host fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.proposal_path = self.case.root / 'proposal.json'
        lo, hi = 13992, 13996
        expanded = X.A.expanded_rom(self.case.rom.read_bytes())
        spans = [[base+lo//4*6, base+hi//4*6] for base in X.A.TILE32_BASES]
        self.proposal = dict(kind='lyra.current_saved_allocation_proposal.v1',
            allocation_granted=False, runtime_admission=False, producer_enforcement_verified=False,
            source_rom_sha256=X.R.sha(self.case.rom.read_bytes()), source_size=self.case.rom.stat().st_size,
            proposed_tile32_id_range=[lo, hi], proposed_id_capacity=4,
            required_new_tile32_definitions=1, proposed_spare_ids=3, native_copy_maps=[],
            packed_preimages=[dict(pc=span, sha256=X.R.sha(expanded[slice(*span)])) for span in spans],
            proposed_stream_pc_range=list(X.V.STREAM), required_stream_bytes=32*518,
            stream_preimage_sha256=X.R.sha(expanded[slice(*X.V.STREAM)]),
            source_engine_head=self.head, named_ledger_path=str(self.root / 'Config/allocation_ownership.json'),
            named_ledger_sha256=X.Q.bound(self.root / 'Config/allocation_ownership.json')['sha256'],
            named_ledger_conflicts=[], native_reference_conflicts=[], native_tile32_ids_used=1,
            background_palette_runtime_data_range=None, required_consumers=['uncomposed runtime'],
            status='SOURCE_RECIPE_NOT_AN_ALLOCATION_GRANT',
            proposed_lifetime='fresh_native_save_to_disposable_build_only; expires_on_any_saved_ROM_or_sidecar_change')
        self.proposal_path.write_bytes(X.P.encoded(self.proposal))
        self.request = self.case.prepare()[1]

    def test_batch_reads_preserve_spaces_binary_data_and_exact_revision(self):
        binary=self.root/'Overworld/binary data.bin'
        raw=b'first\nline\x00\xff\n0123456789\n';binary.write_bytes(raw);self.commit()
        head=self.git('rev-parse','HEAD').strip()
        paths=['Overworld/binary data.bin','Core/ZS ROM MAP.txt','Oracle_main.asm']
        with mock.patch.object(X.subprocess,'run',wraps=subprocess.run) as runs:
            blobs=X._git_source_blobs(self.root,head,paths)
        self.assertEqual(runs.call_count,1)
        self.assertEqual(runs.call_args.args[0][-2:],['cat-file','--batch'])
        self.assertEqual(blobs['Overworld/binary data.bin'],raw)
        binary.write_bytes(b'changed live bytes')
        self.assertEqual(X._git_source_blobs(self.root,head,paths),blobs)
        with self.assertRaisesRegex(ValueError,'exact revision'):
            X._git_source_blobs(self.root,self.head,paths)
        for names in (['missing.asm'],['Oracle_main.asm','Oracle_main.asm'],
                      ['../escape'],['Oracle_main.asm\nHEAD:Oracle_main.asm']):
            with self.subTest(names=names),self.assertRaises(ValueError):
                X._git_source_blobs(self.root,head,names)

    def test_batch_refuses_non_blob_truncation_and_trailing_output(self):
        from types import SimpleNamespace
        oid=b'0'*40
        for raw in (oid+b' tree 3\nabc\n',oid+b' blob 4\nabc',
                    oid+b' blob 3\nabc\ntrailing',b'HEAD:missing missing\n'):
            with self.subTest(raw=raw),mock.patch.object(X.subprocess,'run',
                    return_value=SimpleNamespace(stdout=raw)):
                with self.assertRaises(ValueError):
                    X._git_source_blobs(self.root,self.head,['Oracle_main.asm'])

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE).decode()

    def commit(self):
        self.git('add', '.')
        self.git('commit', '-qm', 'Owned host fixture')

    def review(self):
        return X.reservation_review(self.request, self.case.project, self.case.rom,
                                    self.proposal_path, self.root, self.head)

    def refresh_proposal_source(self):
        self.proposal['source_engine_head'] = self.head
        self.proposal['named_ledger_sha256'] = X.Q.bound(self.root / 'Config/allocation_ownership.json')['sha256']
        self.proposal_path.write_bytes(X.P.encoded(self.proposal))

    def verify(self, review):
        return X.verify_reservation_review(review, self.case.project, self.case.rom)

    def test_exact_source_inline_binary_and_all_preimages_bind_without_compiler_or_grant(self):
        with mock.patch.object(X.V, 'compile_native_plan') as compiler:
            review = self.review()
            self.assertEqual(self.verify(review), review)
        compiler.assert_not_called()
        self.assertEqual(review['selected_source']['engine_head'], self.head)
        self.assertEqual(review['selected_source']['incbin_paths'], ['Overworld/asset.bin'])
        self.assertEqual(review['selected_source']['ledger'],
                         X.Q.bound(self.root / 'Config/allocation_ownership.json'))
        self.assertEqual(review['preimages'], [*self.proposal['packed_preimages'],
            dict(pc=list(X.V.STREAM), sha256=self.proposal['stream_preimage_sha256'])])
        self.assertEqual(review['spare_tile32_ids'], [13993, 13994, 13995])
        self.assertEqual(review['native_consumer_bounds']['maps'], [0, 160])
        self.assertEqual(review['native_consumer_bounds']['planes'], 320)
        self.assertEqual(review['native_consumer_bounds']['pointer_tables'][0]['pc'], [0x1794D, 0x17B2D])
        for key in ('allocation_granted', 'producer_enforcement_verified', 'assembled_write_extents_verified',
                    'runtime_admission', 'ordinary_build_ready', 'rom_written'):
            self.assertIs(review[key], False)
        self.assertFalse(self.case.candidate.exists())

    def test_asm_asset_ledger_proposal_or_adapter_drift_retires_review(self):
        review = self.review()
        paths = [self.root / name for name in ('Overworld/world.asm', 'Overworld/asset.bin',
                 'Config/allocation_ownership.json')]+[self.proposal_path]
        for path in paths:
            with self.subTest(path=path):
                original = path.read_bytes()
                path.write_bytes(original+b'\nchanged')
                with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                    self.verify(review)
                path.write_bytes(original)
        forged = copy.deepcopy(review)
        forged['adapter_bindings'][0]['sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            self.verify(forged)
        self.assertEqual(self.verify(review), review)

    def test_checkout_head_and_dirty_selected_engine_refuse(self):
        review = self.review()
        self.git('commit', '--allow-empty', '-qm', 'Later source selection')
        with self.assertRaisesRegex(ValueError, 'checkout changed'):
            self.verify(review)
        path = self.root / 'Overworld/world.asm'
        path.write_text(path.read_text()+'nop\n')
        with self.assertRaisesRegex(ValueError, 'differs from engine commit'):
            self.review()

    def test_same_bytes_later_save_and_rebound_context_retire_review(self):
        review = self.review()
        self.case.next_save()
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.verify(review)
        self.case.output = self.case.root / 'generation2'
        self.request = self.case.prepare()[1]
        current = self.review()
        self.assertNotEqual(current['transfer_id'], review['transfer_id'])
        self.case.context['state'] = 'rebound'
        self.case.context['native_commit'] = None
        self.case.context_path.write_bytes(X.P.encoded(self.case.context))
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.verify(current)

    def test_preimage_demand_spares_and_native_consumers_refuse(self):
        for field, value, error in [('packed_preimages', self.proposal['packed_preimages'][:3], 'all four'),
                ('proposed_spare_ids', 2, 'demand/spare'),
                ('required_new_tile32_definitions', 2, 'demand/spare'),
                ('stream_preimage_sha256', 'f'*64, 'preimage differs')]:
            with self.subTest(field=field):
                changed = dict(self.proposal, **{field:value})
                self.proposal_path.write_bytes(X.P.encoded(changed))
                with self.assertRaisesRegex(ValueError, error):
                    self.review()
        self.proposal_path.write_bytes(X.P.encoded(self.proposal))
        original = X.N._plane
        def native_reference(*args):
            decoded, pointer, span = original(*args)
            value = 13995
            part = value >> 8 if args[2] == X.N.POINTER_TABLES[0] else value & 255
            return bytes([part])+decoded[1:], pointer, span
        # Refuse a native consumer in the spare range even when all preimages match.
        with mock.patch.object(X.N, '_plane', side_effect=native_reference):
            with self.assertRaisesRegex(ValueError, 'reader census differs'):
                self.review()

    def test_actual_native_spare_reference_and_actual_stream_overlap_refuse(self):
        changed = copy.deepcopy(self.proposal)
        changed['proposed_stream_pc_range'] = [0x100000, 0x100000+17094]
        changed['stream_preimage_sha256'] = X.R.sha(self.case.rom.read_bytes()[0x100000:0x100000+17094])
        self.proposal_path.write_bytes(X.P.encoded(changed))
        with self.assertRaisesRegex(ValueError, 'alias native map'):
            self.review()
        source = bytearray(self.case.rom.read_bytes())
        for table, at, part in [(X.N.POINTER_TABLES[0], 0x100200, 13995 >> 8),
                                (X.N.POINTER_TABLES[1], 0x100400, 13995 & 255)]:
            source[at:at+259] = b'\xe0\xff'+bytes([part])+bytes(255)+b'\xff'
            source[X.A.pc(table):X.A.pc(table)+3] = X.A.snes(at).to_bytes(3, 'little')
        self.case.rom.write_bytes(source)
        self.case.proof['source_rom_sha256'] = X.R.sha(source)
        self.case.inputs['rom'] = X.Q.bound(self.case.rom)
        self.case.save['artifacts'] = self.case.artifacts(self.case.inputs)
        self.case.next_save()
        self.case.output = self.case.root / 'native-reference-generation'
        self.request = self.case.prepare()[1]
        self.proposal['source_rom_sha256'] = X.R.sha(source)
        self.proposal['native_tile32_ids_used'] = 2
        self.proposal_path.write_bytes(X.P.encoded(self.proposal))
        with self.assertRaisesRegex(ValueError, 'overlaps native Tile32 consumers'):
            self.review()

    def test_named_owner_dynamic_asset_and_late_source_drift_refuse(self):
        ledger = self.root / 'Config/allocation_ownership.json'
        ledger.write_bytes(X.P.encoded(dict(schema_version=1, allocation_available=False,
            claims=[dict(id='future_owner', space='tile32_id', base=13992, size=1)], tables=[])))
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.refresh_proposal_source()
        with self.assertRaisesRegex(ValueError, 'future_owner'):
            self.review()
        ledger.write_bytes(X.P.encoded(dict(schema_version=1, allocation_available=False, claims=[], tables=[])))
        source = self.root / 'Overworld/world.asm'
        source.write_text('org $008000\nAsset: incbin !dynamic\n')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.refresh_proposal_source()
        with self.assertRaisesRegex(ValueError, 'unsupported computed'):
            self.review()
        source.write_text('org $008000\nAsset: incbin "asset.bin"\n')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.refresh_proposal_source()
        original = X._engine_source_context
        def changed(*args):
            result = original(*args)
            source.write_text(source.read_text()+'nop\n')
            return result
        with mock.patch.object(X, '_engine_source_context', side_effect=changed):
            with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                self.review()

    def test_stale_proposal_source_ledger_and_unknown_fields_refuse(self):
        for field, value, error in [('named_ledger_sha256', 'f'*64, 'source/ledger binding is stale'),
                ('named_ledger_path', str(X.R.LEDGER), 'source/ledger binding is stale'),
                ('source_engine_head', 'a'*40, 'source/ledger binding is stale'),
                ('unknown_future_grant', True, 'Malformed current-source reservation proposal')]:
            with self.subTest(field=field):
                self.proposal_path.write_bytes(X.P.encoded(dict(self.proposal, **{field:value})))
                with self.assertRaisesRegex(ValueError, error):
                    self.review()

    def test_valid_new_generation_request_cannot_replace_old_review_binding(self):
        review = self.review()
        self.case.next_save()
        self.case.output = self.case.root / 'new-generation-request'
        self.request = self.case.prepare()[1]
        X.verify_transfer(self.request, self.case.project, self.case.rom)
        review['transfer'] = X.Q.bound(self.request)
        with self.assertRaisesRegex(ValueError, 'source/generation/bindings differ'):
            self.verify(review)

    def test_transient_omitted_include_and_unsupported_inline_include_refuse(self):
        import generate_hack_manifest as manifest
        original = manifest.collect_reachable_asm_sources
        calls = []
        def omitted(*args, **kwargs):
            result = original(*args, **kwargs)
            calls.append(True)
            return [p for p in result if p.name != 'world.asm'] if len(calls) == 1 else result
        with mock.patch.object(manifest, 'collect_reachable_asm_sources', side_effect=omitted):
            with self.assertRaisesRegex(ValueError, 'closure/profile changed'):
                self.review()
        main = self.root / 'Oracle_main.asm'
        main.write_text(main.read_text()+'Hidden: incsrc "extra.asm"\n')
        (self.root / 'extra.asm').write_text('nop\n')
        self.commit()
        self.head = self.git('rev-parse', 'HEAD').strip()
        self.refresh_proposal_source()
        with self.assertRaisesRegex(ValueError, 'unsupported inline incsrc'):
            self.review()

    def test_review_report_cannot_be_used_as_build_request_or_forged_grant(self):
        review = self.review()
        report = self.case.root / 'review.json'
        report.write_bytes(X.P.encoded(review))
        generated = self.case.root / 'generated'
        with (mock.patch.object(X.P, 'render_outputs') as render,
              mock.patch.object(X.P, 'compile_saved_plan') as historical,
              mock.patch.object(X.V, 'compile_native_plan') as compiler):
            with self.assertRaisesRegex(ValueError, 'RESERVATION_REVIEW_UNGRANTED'):
                X.P.prepare(generated, project=self.case.project, base_rom=self.case.rom, request=report)
        render.assert_not_called()
        historical.assert_not_called()
        compiler.assert_not_called()
        self.assertFalse(generated.exists())
        self.assertFalse(self.case.candidate.exists())
        review['allocation_granted'] = True
        with self.assertRaisesRegex(ValueError, 'source/generation/bindings differ'):
            self.verify(review)


if __name__ == '__main__':
    unittest.main()
