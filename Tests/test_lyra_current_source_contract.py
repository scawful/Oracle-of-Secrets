"""Explicit current source profiles have no historical allocation defaults."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

import test_lyra_reservation_review as fixtures
import lyra_current_transfer as X
from lyra_project_terrain import Allocation


class CurrentSourceContractTest(unittest.TestCase):
    def setUp(self):
        self.fixture = fixtures.ReservationReviewTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.case = self.fixture.case
        # Every current profile binds inactive consumers and its compiler too.
        # These tiny files are committed but never reached by Oracle_main.asm.
        self.inactive = self.fixture.root / 'Overworld/inactive-resident.asm'
        self.compiler = self.fixture.root / 'Scripts/Build/fixture-compiler.py'
        self.inactive.write_text('; Disabled resident host fixture; no ROM allocation.\n')
        self.compiler.write_text('# Bound host compiler fixture; never executed.\n')
        # The generic host profile is deliberately not the full resident set.
        # ResidentConstructorTest adds and authenticates that set separately.
        name = 'lyra_ferry_visual_boundary_53'
        ledger_path = self.fixture.root / 'Config/allocation_ownership.json'
        ledger = json.loads(ledger_path.read_bytes())
        ledger.update(source_sets={name: 'Owned current-source host fixture'}, sources={
            name+':'+str(path.relative_to(self.fixture.root)): dict(
                source_set=name, path=str(path.relative_to(self.fixture.root)),
                sha256=X.R.sha(path.read_bytes()))
            for path in (self.fixture.root / 'Overworld/world.asm', self.inactive, self.compiler)})
        ledger_path.write_bytes(X.P.encoded(ledger))
        self.fixture.commit()
        self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
        self.fixture.refresh_proposal_source()
        self.review = self.fixture.review()
        self.path = self.fixture.root / 'Config/lyra_current_source_contract.json'
        self.value = json.loads(Path(X.CURRENT_SOURCE_CONTRACT).read_bytes())
        self.value.update(engine_head=self.fixture.head, base_head=self.fixture.head)
        self.value['ledger'].update(source_set=name,
            sha256=self.review['selected_source']['ledger']['sha256'],
            engine_ledger_sha256=self.review['selected_source']['ledger']['sha256'])
        self.value['native_readers'] = dict(decoder_spans=[[0x17691, 0x177CB]],
            pointer_reader_spans=[[0x1759D, 0x175D2], [0x177E3, 0x17818]])
        binding = X.Q.bound(self.fixture.root / 'Overworld/world.asm')
        self.value['origins'] = {name: dict(pc=list(span),
            snes=[X.A.snes(span[0]), X.A.snes(span[1]-1)+1], source_binding=binding)
            for name, span in dict(tables=(0x300000, 0x304000), code=(0x304000, 0x305000),
                descriptor=(0x305000, 0x305100), bg_palette=(0x306000, 0x307000),
                graphics=(0x308000, 0x30A000)).items()}
        self.write()
        for owner, key, value in ((X, 'CURRENT_SOURCE_CONTRACT', self.path),
                (X.R, 'LEDGER', self.fixture.root / 'Config/allocation_ownership.json'),
                (X.P, 'ROOT', self.fixture.root)):
            patch = mock.patch.object(owner, key, value)
            patch.start()
            self.addCleanup(patch.stop)

    def write(self):
        self.path.write_bytes(X.P.encoded(self.value))

    def profile(self):
        return X.current_native_source_profile(self.review, self.case.project, self.case.rom)

    def inputs(self):
        _, source, document = X.verify_transfer(self.fixture.request, self.case.project, self.case.rom)
        return source, document

    def allocation(self):
        return Allocation((X.V.STREAM,), (13992,), tile32_assignments=((13992, (1, 0, 0, 0)),))

    def test_explicit_profile_runs_native_plan_without_historical_ledger_or_origin_defaults(self):
        profile = self.profile()
        source, document = self.inputs()
        with mock.patch.object(X.R, 'reservation_claim', side_effect=AssertionError('Historical authority used')):
            plan, payload = X.V.compile_native_plan(source, document, self.allocation(),
                X.A.render_dependency_plan(X.V.FULL_MAPS)[0], spare_tile32_ids=(13993, 13994, 13995),
                current_source_profile=profile)
        self.assertEqual(len(payload), 32*518)
        self.assertEqual(plan['native_maps_preserved'], 160)
        self.assertEqual(plan['emitted_definitions'], [dict(tile32_id=13992, quadrants=[1, 0, 0, 0])])
        for row in plan['appearance']['selector_rows']:
            self.assertTrue(all(0x300000 <= table['pc'] < 0x304000 for table in row['native_table_rows']))
        for key in ('producer_enforcement_verified', 'ordinary_build_ready', 'runtime_admission', 'rom_written'):
            self.assertIs(plan[key], False)
        self.assertFalse(self.case.candidate.exists())

    def test_inactive_source_origins_are_bound_to_the_selected_commit(self):
        self.value['origins']['code']['source_binding'] = X.Q.bound(self.inactive)
        self.write()
        profile = self.profile()
        self.assertNotIn(str(self.inactive),
                         {row['path'] for row in profile['selected_source']['bindings']})
        self.assertIn(X.Q.bound(self.inactive), profile['current_source_bindings'])
        self.assertIn(X.Q.bound(self.compiler), profile['current_source_bindings'])
        self.assertEqual(profile['origins']['code']['source_binding'], X.Q.bound(self.inactive))
        for key in ('allocation_granted', 'publication_authorized',
                    'producer_enforcement_verified', 'ordinary_build_ready', 'runtime_admission'):
            self.assertIs(profile[key], False)

    def test_inactive_source_or_compiler_mutation_and_missing_file_refuse(self):
        for path in (self.inactive, self.compiler):
            original = path.read_bytes()
            try:
                path.write_bytes(original + b'; uncommitted change\n')
                with self.subTest(path=path.name, control='mutated'):
                    with self.assertRaisesRegex(ValueError, 'source-set consumer changed'):
                        self.profile()
                path.unlink()
                with self.subTest(path=path.name, control='missing'):
                    with self.assertRaisesRegex(ValueError, 'source-set consumer escaped|not available|not found'):
                        self.profile()
            finally:
                path.write_bytes(original)

    def test_newly_rehashed_source_set_cannot_relabel_an_older_engine_commit(self):
        # The ledger may truthfully hash the new bytes while the selected engine
        # still names the earlier committed compiler. That is not the same source.
        previous = self.fixture.head
        self.compiler.write_text('# Different compiler bytes.\n')
        ledger_path = self.fixture.root / 'Config/allocation_ownership.json'
        ledger = json.loads(ledger_path.read_bytes())
        for row in ledger['sources'].values():
            if row['path'] == str(self.compiler.relative_to(self.fixture.root)):
                row['sha256'] = X.R.sha(self.compiler.read_bytes())
        ledger_path.write_bytes(X.P.encoded(ledger))
        self.fixture.git('add', 'Config/allocation_ownership.json')
        self.fixture.git('commit', '-qm', 'Rehashed ledger without selected compiler commit')
        self.fixture.head = self.fixture.git('rev-parse', 'HEAD').strip()
        self.fixture.refresh_proposal_source()
        self.review = self.fixture.review()
        self.value.update(engine_head=previous, base_head=previous)
        self.value['ledger']['sha256'] = X.Q.bound(ledger_path)['sha256']
        self.write()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_SET_ENGINE_MISMATCH'):
            self.profile()

    def test_proposed_null_ledger_readers_and_origins_have_explicit_refusals(self):
        original = copy.deepcopy(self.value)
        self.value['ledger']['sha256'] = None
        self.write()
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_LEDGER_UNBOUND'):
            self.profile()
        for name in ('decoder_spans', 'pointer_reader_spans'):
            self.value = copy.deepcopy(original)
            self.value['native_readers'][name] = None
            self.write()
            with self.subTest(reader=name), self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_READERS_UNBOUND'):
                self.profile()
        for name in original['origins']:
            self.value = copy.deepcopy(original)
            self.value['origins'][name] = None
            self.write()
            with self.subTest(origin=name), self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_ORIGIN_UNBOUND'):
                self.profile()

    def test_domain_and_every_table_family_require_complete192_rows(self):
        original = copy.deepcopy(self.value)
        for count in (64, 160, True):
            self.value = copy.deepcopy(original)
            self.value['tables']['rows'] = count
            self.write()
            with self.subTest(rows=count), self.assertRaisesRegex(ValueError, 'TABLES_INCOMPLETE'):
                self.profile()
        self.value = copy.deepcopy(original)
        self.value['tables']['families'].remove('music_phase3')
        self.write()
        with self.assertRaisesRegex(ValueError, 'TABLES_INCOMPLETE'):
            self.profile()
        self.value = copy.deepcopy(original)
        self.value['source_domain']['parent_count'] = 160
        self.write()
        with self.assertRaisesRegex(ValueError, 'DOMAIN_INCOMPLETE'):
            self.profile()

    def test_caller_contract_ledger_and_forged_authority_are_not_accepted(self):
        other = self.case.root / 'caller-contract.json'
        other.write_bytes(self.path.read_bytes())
        with self.assertRaisesRegex(ValueError, 'CONTRACT_AUTHORITY_MISMATCH'):
            X.validate_current_source_contract(self.review, self.case.project, self.case.rom, contract_path=other)
        ledger = self.case.root / 'caller-ledger.json'
        ledger.write_bytes(Path(X.R.LEDGER).read_bytes())
        with mock.patch.object(X.R, 'LEDGER', ledger), self.assertRaisesRegex(ValueError, 'LEDGER_MISMATCH'):
            self.profile()
        self.value['publication_authorized'] = True
        self.write()
        with self.assertRaisesRegex(ValueError, 'CONTRACT_UNGRANTED'):
            self.profile()

    def test_contract_source_generation_and_document_drift_expire_profile(self):
        profile = self.profile()
        source, document = self.inputs()
        self.value['origins']['code']['pc'][1] -= 1
        self.value['origins']['code']['snes'][1] -= 1
        self.write()
        with self.assertRaisesRegex(ValueError, 'PROFILE_STALE'):
            X.verify_current_native_source_profile(profile, source, document)
        self.value['origins']['code']['pc'][1] += 1
        self.value['origins']['code']['snes'][1] += 1
        self.write()
        changed = bytearray(source)
        changed[0x1000] ^= 1
        with self.assertRaisesRegex(ValueError, 'PROFILE_STALE'):
            X.verify_current_native_source_profile(profile, bytes(changed), document)
        self.case.next_save()
        with self.assertRaisesRegex(ValueError, 'retired'):
            X.verify_current_native_source_profile(profile, source, document)

    def test_origin_geometry_binding_and_engine_ledger_drift_refuse(self):
        original = copy.deepcopy(self.value)
        self.value['origins']['graphics']['snes'][0] += 1
        self.write()
        with self.assertRaisesRegex(ValueError, 'PC/SNES origin differs'):
            self.profile()
        self.value = copy.deepcopy(original)
        self.value['origins']['code']['source_binding'] = X.Q.bound(self.case.verifier)
        self.write()
        with self.assertRaisesRegex(ValueError, 'lacks a selected source binding'):
            self.profile()
        self.value = copy.deepcopy(original)
        self.value['ledger']['engine_ledger_sha256'] = 'f'*64
        self.write()
        with self.assertRaisesRegex(ValueError, 'ENGINE_LEDGER_MISMATCH'):
            self.profile()

    def test_late_contract_change_and_selected_checkout_change_refuse(self):
        verify = X.verify_reservation_review
        changed = []
        def mutate(*args, **kwargs):
            result = verify(*args, **kwargs)
            if not changed:
                changed.append(True)
                self.value['origins']['descriptor'] = None
                self.write()
            return result
        with mock.patch.object(X, 'verify_reservation_review', side_effect=mutate):
            with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                self.profile()
        self.fixture.git('commit', '--allow-empty', '-qm', 'Later selected checkout')
        with self.assertRaisesRegex(ValueError, 'checkout changed'):
            self.profile()

    def test_missing_profile_cannot_consult_historical_reader_authority(self):
        source, document = self.inputs()
        with mock.patch.object(X.R, 'reservation_claim', side_effect=AssertionError('Historical authority used')):
            with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_PROFILE_REQUIRED'):
                X.V.compile_native_plan(source, document, self.allocation(),
                    X.A.render_dependency_plan(X.V.FULL_MAPS)[0])

    def test_allocation_and_spares_cannot_drift_from_the_profile_review(self):
        profile = self.profile()
        source, document = self.inputs()
        for allocation, spare, copies in (
                (Allocation(((0x320000, 0x328000),), (13992,),
                    tile32_assignments=((13992, (1, 0, 0, 0)),)), (13993, 13994, 13995), ()),
                (Allocation((X.V.STREAM,), (13996,),
                    tile32_assignments=((13996, (1, 0, 0, 0)),)), (13993, 13994, 13995), ()),
                (self.allocation(), (13994, 13995), ()),
                (self.allocation(), (13993, 13994, 13995), (0x37,))):
            with self.subTest(allocation=allocation, spares=spare, copies=copies):
                with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_RESERVATION_MISMATCH'):
                    X.V.compile_native_plan(source, document, allocation,
                        X.A.render_dependency_plan(X.V.FULL_MAPS)[0], current_source_profile=profile,
                        spare_tile32_ids=spare, native_copy_maps=copies)


if __name__ == '__main__':
    unittest.main()
