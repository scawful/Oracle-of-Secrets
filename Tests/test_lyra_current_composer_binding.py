"""Real current-profile composition with isolated host saved-source fixtures.

The inherited external native verifier is a fixture. Reservation review, live
generation checks, source-profile reconstruction, table/BG planning and composer
validation run through their maintained implementations. No output is written.
"""
import copy
import json
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_project_bg_palette as B
import lyra_project_publisher as P
import test_lyra_current_native_loaders as reader_fixtures
import test_lyra_current_source_contract as contract_fixtures


class ComposerFixture:
    def __init__(self, owner):
        self.contract_fixture = contract_fixtures.CurrentSourceContractTest()
        self.contract_fixture.bind_composer_sources = True
        self.contract_fixture.setUp()
        owner.addCleanup(self.contract_fixture.doCleanups)
        self.root = self.contract_fixture.fixture.root
        patch = mock.patch.object(P, 'ROOT', self.root)
        patch.start()
        owner.addCleanup(patch.stop)
        self.contract = self.contract_fixture.value
        self.profile = self.contract_fixture.profile()
        self.source, self.document = self.contract_fixture.inputs()
        reader_fixtures.CurrentNativeLoaderTests.setUpClass()
        self.rows = copy.deepcopy(reader_fixtures.CurrentNativeLoaderTests.rows)
        self.table_plan = self.tables()

    def tables(self, *, source=None, origins=None, profile=None):
        source = self.source if source is None else source
        profile = self.profile if profile is None else profile
        selected = profile['origins']
        origins = origins or dict(table_base=selected['tables']['snes'][0],
            code_base=selected['code']['snes'][0], code_end=selected['code']['snes'][1],
            descriptor_base=selected['descriptor']['snes'][0])
        return L.plan_current_tables(source, self.rows, origins=origins,
            policy=dict(source_rom_sha256=P.R.sha(source), source_profile_sha256=X.T.digest(profile),
                        allocation_granted=False, publication_authorized=False))

    def bg(self, *, data_snes=None, capacity=None, maps=None):
        origin = self.profile['origins']['bg_palette']
        lo, hi = origin['pc']
        return B.plan_bg128(maps if maps is not None else
            [SimpleNamespace(map_id=0xA0+i, properties=properties)
             for i, properties in enumerate(self.document.properties)],
            data_snes=origin['snes'][0] if data_snes is None else data_snes,
            capacity=hi-lo if capacity is None else capacity,
            preimage=X.A.expanded_rom(self.source)[lo:lo+(hi-lo if capacity is None else capacity)])

    def compose(self, *, table_plan=None, profile=None, contract=None, bg128_plan=None):
        contract = self.contract if contract is None else contract
        profile = self.profile if profile is None else profile
        graphics = '; Explicit host graphics source; no real catalog resources qualified.\n'
        report = dict(current_mode=True, parent_count=192,
            source_contract_sha256=P.R.sha(P.encoded(contract)),
            generated_sha256=P.R.sha(graphics.encode()),
            graphics_origin_snes=contract['origins']['graphics']['snes'])
        return P.render_current_source_outputs(self.table_plan if table_plan is None else table_plan,
            contract=contract, graphics_source=graphics, graphics_report=report,
            current_source_profile=profile, bg128_plan=bg128_plan)


class CurrentComposerBindingTest(unittest.TestCase):
    def setUp(self):
        self.f = ComposerFixture(self)

    def test_same_verified_profile_composes_saved_identity_and_bg_without_selection(self):
        files = self.f.compose(bg128_plan=self.f.bg())
        prepared = json.loads(files['prepare.json'])
        self.assertEqual(prepared['source_rom_sha256'], P.R.sha(self.f.source))
        self.assertEqual(prepared['source_size'], 0x200000)
        self.assertEqual(prepared['source_profile_sha256'], X.T.digest(self.f.profile))
        self.assertEqual(prepared['document_sha256'], self.f.profile['document_sha256'])
        self.assertEqual(prepared['generation'], self.f.profile['review']['generation'])
        self.assertEqual(prepared['operation_id'], self.f.profile['review']['operation_id'])
        self.assertEqual(prepared['source_contract_sha256'], P.R.sha(P.encoded(self.f.contract)))
        self.assertIn(b'Oracle_ProjectBGPalette_Data:', files['runtime_data.asm'])
        for key in ('selected', 'allocation_granted', 'producer_enforcement_verified',
                    'publication_authorized', 'ordinary_build_ready', 'runtime_admission', 'rom_written'):
            self.assertIs(prepared[key], False, key)
        self.assertFalse(self.f.contract_fixture.case.candidate.exists())

    def test_actor_source_streams_share_saved_identity_without_storage_or_admission(self):
        prepared = json.loads(self.f.compose()['prepare.json'])
        actors = prepared['actor_stream_plan']
        self.assertEqual(actors['kind'], 'lyra.current_actor_streams_source_plan.v1')
        for key in ('source_rom_sha256', 'source_size', 'source_profile_sha256',
                    'document_sha256', 'generation', 'operation_id', 'reservation_review_id'):
            self.assertEqual(actors[key], prepared[key], key)
        self.assertEqual(actors['source_contract_binding'], self.f.profile['contract'])
        self.assertEqual([(row['map_id'], row['state']) for row in actors['streams']],
                         [(area, phase) for area in range(0xA0, 0xC0) for phase in range(3)])
        self.assertEqual(actors['demand']['lists'], 96)
        self.assertEqual(actors['demand']['pointer_bytes'], 192)
        self.assertTrue(all(row['payload_hex'] == 'ff' for row in actors['streams']))
        self.assertIsNone(actors['storage'])
        self.assertIsNone(actors['pointers'])
        for key in ('allocation_granted', 'producer_enforcement_verified', 'publication_authorized',
                    'ordinary_build_ready', 'runtime_admission', 'actors_compiled', 'rom_written'):
            self.assertIs(actors[key], False, key)
        self.assertFalse(self.f.contract_fixture.case.candidate.exists())

    def test_independent_valid_origin_and_profile_plans_cannot_be_mixed(self):
        foreign_origins = dict(self.f.table_plan['origins'])
        foreign_origins['table_base'] += 0x10000
        foreign = self.f.tables(origins=foreign_origins)
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_ORIGIN_MISMATCH'):
            self.f.compose(table_plan=foreign)
        old_plan = self.f.table_plan
        self.f.contract['origins']['graphics']['pc'][1] -= 1
        self.f.contract['origins']['graphics']['snes'][1] -= 1
        self.f.contract_fixture.write()
        new_profile = self.f.contract_fixture.profile()
        # Both pure table plans are independently valid under their own profile
        # digest. The old plan cannot be paired with the fresh new profile.
        self.f.tables(profile=new_profile)
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_SOURCE_MISMATCH'):
            self.f.compose(table_plan=old_plan, profile=new_profile)

    def test_supplied_contract_and_profile_document_identity_cannot_be_relabelled(self):
        contract = copy.deepcopy(self.f.contract)
        contract['origins']['graphics']['pc'][1] -= 1
        contract['origins']['graphics']['snes'][1] -= 1
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_CONTRACT_MISMATCH'):
            self.f.compose(contract=contract)
        profile = copy.deepcopy(self.f.profile)
        profile['document_sha256'] = 'f'*64
        with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_PROFILE_STALE'):
            self.f.compose(profile=profile)

    def test_table_payload_assembler_and_extent_metadata_are_reconstructed(self):
        for key in ('constants_assembler', 'tables_assembler', 'descriptor_assembler',
                    'descriptor_hex', 'tables_pc', 'code_pc', 'descriptor_pc', 'tables'):
            plan = copy.deepcopy(self.f.table_plan)
            if key.endswith('_assembler'):
                plan[key] += '\norg $008000\n'
            elif key == 'descriptor_hex':
                plan[key] = '00' + plan[key][2:]
            elif key == 'tables':
                row = plan[key][0]
                row['payload_hex'] = 'ff' + row['payload_hex'][2:]
            else:
                plan[key][1] += 1
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_TABLES_MISMATCH'):
                self.f.compose(table_plan=plan)

    def test_saved2mib_identity_does_not_accept_expanded_or_candidate4mib_plan(self):
        expanded = X.A.expanded_rom(self.f.source)
        changed = bytearray(expanded)
        changed[0x300100] ^= 1
        for source in (expanded, bytes(changed)):
            plan = self.f.tables(source=source)
            self.assertNotEqual(plan['source_rom_sha256'], P.R.sha(self.f.source))
            with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_SOURCE_MISMATCH'):
                self.f.compose(table_plan=plan)

    def test_valid_bg_plans_for_other_origin_capacity_or_document_are_refused(self):
        origin = self.f.profile['origins']['bg_palette']
        capacity = origin['pc'][1]-origin['pc'][0]
        other_rows = [SimpleNamespace(map_id=0xA0, properties=dict(background_palette=[1]*128))]
        for plan in (self.f.bg(data_snes=origin['snes'][0]+0x100),
                     self.f.bg(capacity=capacity//2), self.f.bg(maps=other_rows)):
            with self.subTest(origin=plan['data_snes'], capacity=plan['capacity']), \
                    self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_BG128_MISMATCH'):
                self.f.compose(bg128_plan=plan)

    def test_bg_payload_and_preimage_cannot_keep_copied_or_rehashed_metadata(self):
        original = self.f.bg()
        for field in ('preimage_sha256', 'payload_sha256', 'payload', 'rehashed_payload', 'records'):
            plan = copy.deepcopy(original)
            if field == 'payload':
                plan['payload'] += b'\x00'
            elif field == 'rehashed_payload':
                plan['payload'] += b'\x00'
                plan['payload_sha256'] = P.R.sha(plan['payload'])
            elif field == 'records':
                plan['records'] = [dict(map_id=0xA0, offset=384, sha256='f'*64)]
            else:
                plan[field] = 'f'*64
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_BG128_MISMATCH'):
                self.f.compose(bg128_plan=plan)

    def test_same_bytes_later_generation_retires_cached_profile(self):
        before = self.f.contract_fixture.case.rom.read_bytes()
        self.f.contract_fixture.case.next_save()
        self.assertEqual(self.f.contract_fixture.case.rom.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.f.compose()

    def test_late_generation_change_is_rechecked_before_source_outputs_return(self):
        emit = B.emit_bg128_data
        def later_save(plan):
            source = emit(plan)
            self.f.contract_fixture.case.next_save()
            return source
        with mock.patch.object(B, 'emit_bg128_data', side_effect=later_save):
            with self.assertRaisesRegex(ValueError, 'retired'):
                self.f.compose(bg128_plan=self.f.bg())


if __name__ == '__main__':
    unittest.main()
