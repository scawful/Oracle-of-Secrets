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
import test_lyra_current_transfer as transfer_fixtures
from test_lyra_project_admission import observation


class ComposerFixture:
    def __init__(self, owner, *, gameplay_areas=None):
        self.contract_fixture = contract_fixtures.CurrentSourceContractTest()
        self.contract_fixture.bind_composer_sources = True
        if gameplay_areas is None:
            self.contract_fixture.setUp()
        else:
            prepare = transfer_fixtures.CurrentSaveTransferTest.prepare
            def prepare_authored(case, **kwargs):
                data = json.loads(case.terrain.read_bytes())
                data.update(schema_version=5, gameplay_areas=copy.deepcopy(gameplay_areas))
                case.terrain.write_bytes(X.P.encoded(data))
                case.inputs['terrain'] = X.Q.bound(case.terrain)
                case.save['artifacts'] = case.artifacts(case.inputs)
                case.receipt.write_bytes(X.P.encoded(case.save))
                case.proof.clear()
                case.proof.update(observation(case.rom.read_bytes(), data)[1])
                case.proof['terrain_sha256'] = X.R.sha(case.terrain.read_bytes())
                return prepare(case, **kwargs)
            with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest, 'prepare', prepare_authored):
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
        for area, values in L.current_property_rows(self.document, source=self.source).items():
            self.rows[area].update(values)
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

    def compose(self, *, table_plan=None, profile=None, contract=None, bg128_plan=None, actor_storage_plan=None,
                resident_graphics_plan=None, resource_inspection=None, resident_native_emission=None,
                resident_bridge=None):
        contract = self.contract if contract is None else contract
        profile = self.profile if profile is None else profile
        graphics = '; Explicit host graphics source; no real catalog resources qualified.\n'
        report = dict(current_mode=True, parent_count=192,
            source_contract_sha256=P.R.sha(P.encoded(contract)),
            generated_sha256=P.R.sha(graphics.encode()),
            graphics_origin_snes=contract['origins']['graphics']['snes'])
        if resident_bridge is not None:
            report['resident_bridge'] = resident_bridge
        return P.render_current_source_outputs(self.table_plan if table_plan is None else table_plan,
            contract=contract, graphics_source=graphics, graphics_report=report,
            current_source_profile=profile, bg128_plan=bg128_plan, actor_storage_plan=actor_storage_plan,
            resident_graphics_plan=resident_graphics_plan, resource_inspection=resource_inspection,
            resident_native_emission=resident_native_emission)


class CurrentComposerBindingTest(unittest.TestCase):
    def setUp(self):
        self.f = ComposerFixture(self)

    def test_same_verified_profile_composes_saved_identity_and_bg_without_selection(self):
        files = self.f.compose(bg128_plan=self.f.bg())
        prepared = json.loads(files['prepare.json'])
        tables = self.f.table_plan['tables']
        self.assertEqual(len(tables), 38)
        self.assertEqual(self.f.table_plan['tables_snes'][1] -
                         self.f.table_plan['tables_snes'][0], 0x30C0)
        self.assertEqual([row['name'] for row in tables[-4:]],
                         ['special_sprite_gfx_phase1', 'special_sprite_palettes_phase1',
                          'special_sprite_palettes_phase2', 'special_sprite_gfx_phase2'])
        self.assertEqual(prepared['source_rom_sha256'], P.R.sha(self.f.source))
        self.assertEqual(prepared['source_size'], 0x200000)
        self.assertEqual(prepared['source_profile_sha256'], X.T.digest(self.f.profile))
        self.assertEqual(prepared['document_sha256'], self.f.profile['document_sha256'])
        self.assertEqual(prepared['generation'], self.f.profile['review']['generation'])
        self.assertEqual(prepared['operation_id'], self.f.profile['review']['operation_id'])
        self.assertEqual(prepared['source_contract_sha256'], P.R.sha(P.encoded(self.f.contract)))
        state = prepared['native_state_contract']
        self.assertEqual(state['source_rom_sha256'], prepared['source_rom_sha256'])
        self.assertEqual(state['requested_doors'], [])
        self.assertEqual(state['requested_returns'], [])
        self.assertFalse(state['runtime_ready'])
        self.assertIn(b'Oracle_ProjectBGPalette_Data:', files['runtime_data.asm'])
        for key in ('selected', 'allocation_granted', 'producer_enforcement_verified',
                    'publication_authorized', 'ordinary_build_ready', 'runtime_admission', 'rom_written'):
            self.assertIs(prepared[key], False, key)
        self.assertFalse(self.f.contract_fixture.case.candidate.exists())

    def test_valid_foreign_property_table_bytes_cannot_relabel_saved_document(self):
        for field, value in (('gfx', [1]*8), ('sign_text', 0x1234), ('music_phase3', 0x42),
                             ('special_sprite_gfx_phase1', 27), ('special_sprite_gfx_phase2', 4),
                             ('special_sprite_palettes_phase1', 1),
                             ('special_sprite_palettes_phase2', 2)):
            before = copy.deepcopy(self.f.rows)
            self.f.rows[0xBF][field] = value
            # Each table plan remains internally consistent and has the same
            # genuine source/profile identity. Only the saved selectors differ.
            foreign = self.f.tables()
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'COMPOSER_PROPERTIES_MISMATCH'):
                self.f.compose(table_plan=foreign)
            self.f.rows = before

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

    def test_legacy_area_identity_and_unassigned_plan_do_not_invent_parent_rows(self):
        document = self.f.document
        legacy = X.T.digest({key: getattr(document, key) for key in
            ('profile', 'maps', 'properties', 'authoring', 'edge_connections', 'flight_points')})
        self.assertEqual(X._document_identity(document), legacy)
        plan = json.loads(self.f.compose()['prepare.json'])['gameplay_area_plan']
        self.assertEqual(plan['status'], 'UNASSIGNED')
        self.assertEqual(plan['assignments'], [])
        self.assertEqual(plan['render_footprints'], [])
        self.assertEqual(plan['unassigned_maps'], list(range(0xA0, 0xC0)))

    def test_authored_area_tables_must_match_and_layout_changes_retire_profile(self):
        from dataclasses import replace
        areas = [dict(parent_map_id=0xA1, size='large', maps=[0xA1, 0xA2, 0xA9, 0xAA])]
        f = ComposerFixture(self, gameplay_areas=areas)
        for area in areas[0]['maps']:
            f.rows[area].update(parent=0xA1, area_size=1)
        f.table_plan = f.tables()
        prepared = json.loads(f.compose()['prepare.json'])
        self.assertEqual(prepared['gameplay_area_plan']['areas'], areas)
        self.assertEqual(prepared['gameplay_area_plan']['status'], 'PARTIAL')
        self.assertIs(prepared['gameplay_area_plan']['runtime_admission'], False)
        self.assertIs(prepared['selected'], False)
        self.assertIn('authored gameplay-area native render/actor aggregation', prepared['remaining_consumers'])
        for field, value in (('parent', 0xA2), ('area_size', 0)):
            rows = copy.deepcopy(f.rows)
            f.rows[0xA2][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'GAMEPLAY_AREAS_MISMATCH'):
                f.compose(table_plan=f.tables())
            f.rows = rows
        changed = replace(f.document, gameplay_areas=(dict(parent_map_id=0xA1, size='small', maps=[0xA1]),))
        with self.assertRaisesRegex(ValueError, 'PROFILE_STALE'):
            X.verify_current_native_source_profile(f.profile, f.source, changed)
        with self.assertRaisesRegex(ValueError, 'GAMEPLAY_AREAS_NATIVE_UNBOUND'):
            X.V.compile_native_plan(f.source, f.document, None, {})

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


class ResidentComposerResourceTest(unittest.TestCase):
    """Exercise composition with an explicit stub at the inspection-review seam.

    Save/source-profile checks are real host fixtures. The stub is not native
    inspection evidence; these controls cover joining already reviewed bytes.
    """
    def setUp(self):
        import lyra_resident_graphics as resident
        import test_lyra_resident_graphics as resources
        self.resident = resident
        self.f = ComposerFixture(self)
        self.bind_origins()
        self.plan = resources.plan(resources.Fixture().inputs())
        self.native = resident.plan_native_resident_abi(self.plan, tile16_count=4096)
        self.inspection = 'explicit-host-inspection-seam'
        self.review = dict(kind='lyra.current_resident_graphics_review.v1',
            project=self.f.profile['project'], base_rom=self.f.profile['base_rom'],
            request=dict(path=self.f.profile['review']['transfer']['path']),
            inspection=dict(path=self.inspection),
            appearance=dict(resident_graphics=self.plan))
        patch = mock.patch.object(X, 'resident_graphics_plan', return_value=self.review)
        patch.start()
        self.addCleanup(patch.stop)

    def bind_origins(self):
        # These are private proposed host-fixture intervals, not repository
        # claims. The real profile validator binds their source and geometry.
        origins = self.f.contract_fixture.value['origins']
        for name, lo, hi in (('resident_data', 0x310000, 0x330000),
                             ('resident_code', 0x3C0000, 0x3C0600),
                             ('resident_resource_code', 0x3C0600, 0x3C0700)):
            origins[name] = dict(pc=[lo, hi], snes=[X.A.snes(lo), X.A.snes(hi-1)+1],
                                 source_binding=origins['code']['source_binding'])
        self.refresh_profile()

    def refresh_profile(self):
        self.f.contract_fixture.write()
        self.f.profile = self.f.contract_fixture.profile()
        self.f.table_plan = self.f.tables()

    def emission(self, start=0x310000):
        preimage = X.A.expanded_rom(self.f.source)[start:start+0x20000]
        emitted = self.resident.emit_native_resident_abi(self.native, data_pc=start,
            capacity=len(preimage), preimage=preimage)
        bridge = self.resident.resident_runtime_inputs(self.native, emitted, preimage=preimage)
        return emitted, bridge

    def compose(self, emission, bridge, *, bg128_plan=None):
        return self.f.compose(resident_graphics_plan=self.plan, resource_inspection=self.inspection,
            resident_native_emission=emission, resident_bridge=bridge, bg128_plan=bg128_plan)

    def test_emitted_resources_and_packed_palette_join_without_mutating_saved_properties(self):
        before = copy.deepcopy(self.f.document.properties)
        emission, bridge = self.emission()
        rows = [SimpleNamespace(**row) for row in self.resident.resident_bg128_rows(self.native)]
        palette = self.f.bg(maps=rows)
        files = self.compose(emission, bridge, bg128_plan=palette)
        self.assertEqual(files[emission['binary_path']], bytes.fromhex(emission['payload_hex']))
        self.assertIn(emission['runtime_data_asm'].encode(), files['runtime_data.asm'])
        self.assertIn(B.emit_bg128_data(palette).encode(), files['runtime_data.asm'])
        constants = files['runtime_constants.asm']
        self.assertIn(b'!LYRA_CURRENT_RESIDENT_ENABLED = 0', constants)
        self.assertIn(b'!LYRA_CURRENT_RESIDENT_RESOURCES_ENABLED = 0', constants)
        for name, prefix in (('resident_code', 'LYRA_CURRENT_RESIDENT_CODE'),
                             ('resident_resource_code', 'LYRA_CURRENT_RESIDENT_RESOURCE_CODE')):
            lo, hi = self.f.profile['origins'][name]['snes']
            self.assertIn(f'!{prefix}_BASE = ${lo:06X}'.encode(), constants)
            self.assertIn(f'!{prefix}_END = ${hi:06X}'.encode(), constants)
        self.assertNotIn(b'MAIN_CACHE_BASE', constants)
        prepared = json.loads(files['prepare.json'])
        self.assertFalse(prepared['selected'])
        self.assertFalse(prepared['ordinary_build_ready'])
        self.assertIn('resident page-word remap and full resource closure', prepared['remaining_consumers'])
        self.assertEqual(self.f.document.properties, before)
        self.assertFalse(self.f.contract_fixture.case.candidate.exists())

    def test_each_existing_generated_origin_refuses_resident_overlap(self):
        for name, origin in self.f.profile['origins'].items():
            if origin is None or name == 'resident_data':
                continue
            emission, bridge = self.emission(origin['pc'][0])
            with self.subTest(origin=name), self.assertRaisesRegex(ValueError,
                    'CURRENT_COMPOSER_RESIDENT_ORIGIN_CONFLICT'):
                self.compose(emission, bridge)
        for reserved in self.f.profile['review']['preimages']:
            emission, bridge = self.emission(reserved['pc'][0])
            with self.subTest(terrain=reserved['pc']), self.assertRaisesRegex(ValueError,
                    'CURRENT_COMPOSER_RESIDENT_ORIGIN_CONFLICT'):
                self.compose(emission, bridge)

    def test_missing_or_rebound_resident_origins_cannot_join(self):
        original = copy.deepcopy(self.f.contract_fixture.value['origins'])
        emission, bridge = self.emission()
        for name in ('resident_data', 'resident_code', 'resident_resource_code'):
            self.f.contract_fixture.value['origins'] = copy.deepcopy(original)
            del self.f.contract_fixture.value['origins'][name]
            self.refresh_profile()
            with self.subTest(origin=name), self.assertRaisesRegex(ValueError,
                    'CURRENT_COMPOSER_RESIDENT_ORIGIN_UNBOUND'):
                self.compose(emission, bridge)
        self.f.contract_fixture.value['origins'] = copy.deepcopy(original)
        data = self.f.contract_fixture.value['origins']['resident_data']
        data['pc'][0] += 1
        data['snes'][0] += 1
        self.refresh_profile()
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_RESIDENT_ORIGIN_MISMATCH'):
            self.compose(emission, bridge)

    def test_code_capacity_and_bank_crossing_refuse_without_activation(self):
        original = copy.deepcopy(self.f.contract_fixture.value['origins'])
        emission, bridge = self.emission()
        for name, lo, hi in (('resident_code', 0x3B0000, 0x3B0601),
                             ('resident_code', 0x3C7F00, 0x3C8100),
                             ('resident_resource_code', 0x3C7F00, 0x3C8100)):
            self.f.contract_fixture.value['origins'] = copy.deepcopy(original)
            self.f.contract_fixture.value['origins'][name].update(
                pc=[lo, hi], snes=[X.A.snes(lo), X.A.snes(hi-1)+1])
            self.refresh_profile()
            with self.subTest(origin=name, pc=[lo, hi]), self.assertRaisesRegex(ValueError,
                    'CURRENT_COMPOSER_RESIDENT_CODE_ORIGIN_INVALID'):
                self.compose(emission, bridge)

    def test_proposed_origins_do_not_emit_code_constants_without_resident_emission(self):
        files = self.f.compose()
        constants = files['runtime_constants.asm']
        self.assertNotIn(b'!LYRA_CURRENT_RESIDENT_CODE_BASE', constants)
        self.assertNotIn(b'!LYRA_CURRENT_RESIDENT_RESOURCE_CODE_BASE', constants)
        self.assertIn(b'!LYRA_CURRENT_RESIDENT_ENABLED = 0', constants)

    def test_stale_preimage_or_missing_graphics_bridge_cannot_join(self):
        emission, bridge = self.emission()
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_RESIDENT_GRAPHICS_UNBOUND'):
            self.compose(emission, None)
        changed = copy.deepcopy(emission)
        changed['preimage_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'NATIVE_EMISSION_MISMATCH'):
            self.compose(changed, bridge)
        with self.assertRaisesRegex(ValueError, 'CURRENT_COMPOSER_BG128_MISMATCH'):
            self.compose(emission, bridge, bg128_plan=self.f.bg())

    def test_resident_palette_requires_existing_owned_restoration_binding(self):
        with self.assertRaisesRegex(ValueError, 'CURRENT_RUNTIME_BG128_UNADMITTED'):
            X.current_bg128(self.f.source, self.f.document, self.f.profile, {}, None,
                           resident_native_plan=self.native)
        origin = self.f.profile['origins']['code']['snes']
        binding = dict(restore_bound=True, code_snes=[origin[0]+0x800, origin[1]])
        ledger = dict(claims=[dict(id='ProjectBGPaletteNativeUnderlay', space='wram',
            base=0x7ECA00, size=514, status='shared', aliases=[],
            condition=dict(PROJECT_BG128_ENABLED=1))])
        palette, actual_binding = X.current_bg128(self.f.source, self.f.document,
            self.f.profile, ledger, binding, resident_native_plan=self.native)
        rows = [SimpleNamespace(**row) for row in self.resident.resident_bg128_rows(self.native)]
        self.assertEqual(palette, self.f.bg(maps=rows))
        self.assertEqual(actual_binding, binding)
        ledger['claims'].append(dict(id='foreign', space='wram', base=0x7ECA01, size=1))
        with self.assertRaisesRegex(ValueError, 'CURRENT_BG128_WRAM_CONFLICT'):
            X.current_bg128(self.f.source, self.f.document, self.f.profile, ledger, binding,
                           resident_native_plan=self.native)


if __name__ == '__main__':
    unittest.main()
