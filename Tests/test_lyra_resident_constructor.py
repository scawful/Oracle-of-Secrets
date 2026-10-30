"""Resident construction/readback using private host inputs, never real grants.

The resource-inspection seam returns an explicit independent graphics fixture.
The source profile, file bindings, ABI emitter, SharedGraphics renderer and
placement verifier remain real. The graphics contract's historical engine/base
pin check is adapted only for the tiny fixture Git repository; its domain,
origins, source hashes and all authority checks still use the real validator.
No test represents native inspection, CPU behavior or ordinary runtime admission.
"""
import copy
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from test_lyra_current_composer_binding import ComposerFixture
import test_lyra_resident_graphics as resources
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_resident_graphics as R

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Graphics'))
import compile_runtime_graphics as graphics


def resource_plan():
    fixture = resources.Fixture(definitions=((
        (2 << 10) | 64, (2 << 10) | 448,
        (2 << 10) | 64, (2 << 10) | 448),))
    fixture.sheet_tiles[9][0] = resources.STRIPES
    source, document, inspection, terrain_hash = fixture.inputs()
    return R.plan_resident_graphics(source, document, inspection,
        terrain_sha256=terrain_hash, provenance=dict(
            inspection_origin='explicit_independent_host_fixture',
            compiler_bindings=[X.Q.bound(ROOT / 'Scripts/Build/lyra_resident_graphics.py')]))


def sparse_payload(emission):
    image = bytearray(0x400000)
    payload = bytes.fromhex(emission['payload_hex'])
    labels = []
    for row in emission['placements']:
        a, b = row['pc']; offset = row['binary_offset']
        image[a:b] = payload[offset:offset + row['byte_count']]
        for name, address in ((row['label'], row['snes']),
                              (row['label'] + '_End', row['snes'] + row['byte_count'])):
            labels.append(f'{address >> 16:02X}:{address & 65535:04X} {name}')
    return bytes(image), ('[labels]\n' + '\n'.join(labels) + '\n').encode()


class ResidentConstructorTest(unittest.TestCase):
    def setUp(self):
        self.f = ComposerFixture(self)
        c = self.f.contract_fixture
        # The reviewed resident source set is distinct from historical source
        # sets. Commit actual support-file copies in the tiny fixture engine.
        self.resident_sources = (
            'Overworld/lyra_resident_atlas.asm', 'Overworld/lyra_resident_resources.asm',
            'Scripts/Build/lyra_native_streams.py', 'Scripts/Build/lyra_project_allocation.py',
            'Scripts/Build/lyra_project_composition.py', 'Scripts/Build/lyra_project_prepare.py',
            'Scripts/Build/lyra_project_tile32.py', 'Scripts/Build/lyra_resident_graphics.py',
            'Scripts/Generate/lz2.py', 'Scripts/Generate/sheet_codec.py', 'Scripts/Generate/sheet_table.py',
            'Items/all_items.asm', 'Items/ice_rod.asm', 'Overworld/entrances.asm')
        for relative in self.resident_sources:
            path = self.f.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        self.bind_source_set(X.RESIDENT_SOURCE_SET)
        for name, lo, hi in (('resident_data', 0x340000, 0x360000),
                             ('resident_code', 0x3C0000, 0x3C0600),
                             ('resident_resource_code', 0x3C0600, 0x3C0700)):
            c.value['origins'][name] = dict(pc=[lo, hi],
                snes=[X.A.snes(lo), X.A.snes(hi - 1) + 1],
                source_binding=c.value['origins']['code']['source_binding'])
        c.write()
        self.f.profile = c.profile()
        self.plan = resource_plan()
        self.inspection = self.f.root / 'retained-inspection.json'
        self.inspection.write_bytes(X.P.encoded(dict(inspection_only=True,
            fixture='independent resource inspection seam, not native evidence')))
        self.review = dict(kind='lyra.current_resident_graphics_review.v1',
            appearance=dict(resident_graphics=self.plan))
        self.real_review = X.resident_graphics_plan
        patch = mock.patch.object(X, 'resident_graphics_plan', return_value=self.review)
        patch.start(); self.addCleanup(patch.stop)
        original_contract = graphics.current_graphics_contract
        canonical = json.loads((ROOT / 'Config/lyra_current_source_contract.json').read_bytes())

        def host_contract(contract, **kwargs):
            adapted = copy.deepcopy(contract)
            adapted.update(engine_head=canonical['engine_head'], base_head=canonical['base_head'])
            return original_contract(adapted, **kwargs)

        patch = mock.patch.object(graphics, 'current_graphics_contract', side_effect=host_contract)
        patch.start(); self.addCleanup(patch.stop)
        self.asset = self.f.root / 'fixture.4bpp.bin'
        self.asset.write_bytes(bytes(range(32)))
        catalog = dict(schema_version=2, resources=dict(fixture=dict(
            path=self.asset.name, format='snes4bpp', byte_count=32,
            sha256=X.R.sha(self.asset.read_bytes()))), profiles=dict(fixture=dict(
                bg_character_base_word=0x2000, transfers=[dict(resource_id='fixture',
                    source_offset=0, vram_word_address=0x2C00, byte_count=32)])),
            bindings=[dict(parent_maps=[0x9F], profile_id='fixture')])
        policy = dict(schema_version=1, profiles=dict(fixture=dict(runtime_enabled=True,
            normal='all_declared_transfers', cache_slots=[3],
            transition=dict(mode='native_staging'), staging=dict(mode='native_after_conversion',
                vram_start_word=0x2C00, vram_end_word=0x3C00, wram_base=0x7F0000), late=None)))
        self.catalog = self.f.root / 'graphics-catalog.json'
        self.policy = self.f.root / 'graphics-policy.json'
        self.catalog.write_bytes(X.P.encoded(catalog))
        self.policy.write_bytes(X.P.encoded(policy))
        self.selection = dict(inspection=X.Q.bound(self.inspection),
            graphics_catalog=X.Q.bound(self.catalog), graphics_policy=X.Q.bound(self.policy))

    def bind_source_set(self, name):
        c = self.f.contract_fixture
        ledger_path = self.f.root / 'Config/allocation_ownership.json'
        ledger = json.loads(ledger_path.read_bytes())
        relatives = {row['path'] for row in ledger['sources'].values()} | set(self.resident_sources)
        ledger['source_sets'][name] = 'Independent committed resident host fixture'
        ledger['sources'].update({name + ':' + relative: dict(source_set=name,
            path=relative, sha256=X.R.sha((self.f.root / relative).read_bytes()))
            for relative in sorted(relatives)})
        ledger_path.write_bytes(X.P.encoded(ledger))
        c.fixture.commit()
        c.fixture.head = c.fixture.git('rev-parse', 'HEAD').strip()
        c.fixture.refresh_proposal_source()
        c.review = c.fixture.review()
        c.value['ledger'].update(source_set=name, sha256=X.Q.bound(ledger_path)['sha256'])
        c.write()
        self.f.profile = c.profile()

    def construct(self, selection=None):
        return X.current_resident_inputs(self.f.profile, self.f.source, self.f.document,
            self.selection if selection is None else selection)

    def test_constructor_rebuilds_all32_payload_and_shared_graphics_without_activation(self):
        properties = copy.deepcopy(self.f.document.properties)
        before = {p: p.read_bytes() for p in (self.inspection, self.catalog, self.policy, self.asset)}
        result = self.construct()
        self.assertEqual([row['map_id'] for row in result['native']['pages']], list(range(0xA0, 0xC0)))
        self.assertEqual(result['graphics_report']['resident_bridge'], result['bridge'])
        self.assertIn('!GfxRT_ParentCount = $00C0', result['graphics_source'])
        self.assertEqual(result['emission']['data_pc'], [0x340000, 0x360000])
        palette = result['bg128_plan']
        palette_payload = bytes.fromhex(palette['payload_hex'])
        self.assertFalse(palette['publication_authorized'])
        self.assertEqual([row['map_id'] for row in palette['records']], list(range(0xA0, 0xC0)))
        self.assertEqual(struct.unpack('<160H', palette_payload[:320]), (0,) * 160)
        native_blobs = {row['label']: bytes.fromhex(row['payload_hex'])
                        for row in result['native']['blobs']}
        for page, row in zip(result['native']['pages'], palette['records']):
            area = result['native']['areas'][page['area_index']]
            self.assertEqual(palette_payload[row['offset']:row['offset'] + 256],
                             native_blobs[area['palette_label']])
        self.assertEqual(json.loads(X.P.encoded(result)), result)
        self.assertIn(X.Q.bound(self.asset), result['inputs'])
        self.assertEqual(self.f.document.properties, properties)
        self.assertEqual({p: p.read_bytes() for p in before}, before)
        self.assertFalse(self.f.contract_fixture.case.candidate.exists())
        for key in ('selected', 'allocation_granted', 'publication_authorized',
                    'ordinary_build_ready', 'runtime_admission'):
            self.assertIs(result[key], False)

    def test_historical_source_set_cannot_authenticate_resident_constructor(self):
        c = self.f.contract_fixture
        c.value['ledger']['source_set'] = 'lyra_ferry_visual_boundary_53'
        c.write(); self.f.profile = c.profile()
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SOURCE_SET_REQUIRED'):
            self.construct()

    def test_nonuniform_ice_rod_row_refuses_before_native_emission(self):
        # Supply a plausible four-quadrant B7 row at the authenticated-review
        # seam. One lookup cannot feed both DMA rows when its words differ.
        area = self.plan['areas'][0]
        page = area['maps'][0]
        area['remaps'].extend(dict(map_id=page, tile16_id=0xB7, quadrant=q,
            source_word=0x1D83, target_word=0x2100 + (q == 3)) for q in range(4))
        with mock.patch.object(R, 'plan_native_resident_abi') as lower:
            with self.assertRaisesRegex(ValueError,
                    'CURRENT_RESIDENT_ICE_ROD_PACKED_SHAPE_UNSUPPORTED'):
                self.construct()
        lower.assert_not_called()

    def test_omitted_resident_source_record_refuses_even_when_file_exists(self):
        c = self.f.contract_fixture
        ledger_path = self.f.root / 'Config/allocation_ownership.json'
        ledger = json.loads(ledger_path.read_bytes())
        relative = 'Overworld/lyra_resident_resources.asm'
        omitted = ledger['sources'].pop(X.RESIDENT_SOURCE_SET + ':' + relative)
        self.assertEqual(omitted['sha256'], X.R.sha((self.f.root / relative).read_bytes()))
        for row in ledger['sources'].values():
            self.assertEqual(row['sha256'], X.R.sha((self.f.root / row['path']).read_bytes()))
        ledger_path.write_bytes(X.P.encoded(ledger))
        c.fixture.commit()
        c.fixture.head = c.fixture.git('rev-parse', 'HEAD').strip()
        c.fixture.refresh_proposal_source()
        c.review = c.fixture.review()
        c.value['ledger']['sha256'] = X.Q.bound(ledger_path)['sha256']
        c.write()
        self.assertTrue((self.f.root / relative).is_file())
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SOURCE_SET_INCOMPLETE'):
            c.profile()

    def test_changed_or_missing_selected_binding_refuses(self):
        for name in self.selection:
            selection = copy.deepcopy(self.selection)
            selection[name]['sha256'] = '0' * 64
            with self.subTest(binding=name, control='changed'):
                with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                    self.construct(selection)
            del selection[name]
            with self.subTest(binding=name, control='missing'):
                with self.assertRaisesRegex(ValueError, 'Malformed current resident source selection'):
                    self.construct(selection)

    def test_origin_and_real_selected_inspection_binding_are_required(self):
        c = self.f.contract_fixture
        del c.value['origins']['resident_resource_code']
        c.write(); self.f.profile = c.profile()
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_ORIGIN_UNBOUND'):
            self.construct()
        # Invoke the real review function rather than its disclosed resource
        # seam. A retained file outside producer bindings must still refuse.
        with self.assertRaisesRegex(ValueError, 'RESIDENT_INSPECTION_UNBOUND'):
            self.real_review(c.fixture.request, c.case.project, c.case.rom, self.inspection)

    def test_late_graphics_policy_change_is_caught_before_returning_inputs(self):
        render = graphics.render

        def change_after_render(*args, **kwargs):
            result = render(*args, **kwargs)
            self.policy.write_bytes(b'{}')
            return result

        with mock.patch.object(graphics, 'render', side_effect=change_after_render):
            with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                self.construct()

    def test_postassembly_rejects_rehashed_emission_before_accepting_compiled_mutant(self):
        built = self.construct()
        mutated = copy.deepcopy(built)
        emission = mutated['emission']
        payload = bytearray.fromhex(emission['payload_hex']); payload[-1] ^= 1
        emission['payload_hex'] = payload.hex(); emission['payload_sha256'] = X.R.sha(payload)
        row = emission['placements'][-1]
        emission['placements'][-1]['sha256'] = X.R.sha(payload[row['binary_offset']:])
        compiled, symbols = sparse_payload(emission)
        # The placement helper alone checks bytes. The maintained output
        # verifier must first compare this rehashed proposal with its rederivation.
        X.verify_resident_payload(emission, compiled, symbols)
        prepared, observed = self.output_fixture(mutated)
        with mock.patch.object(L, 'inspect_current_consumers', return_value=observed) as inspect:
            with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_SOURCE_STALE'):
                X.verify_current_output(prepared, compiled, symbols)
        self.assertTrue(inspect.call_args.kwargs['require_resident'])

    def output_fixture(self, resident_source, *, palette=None):
        observed = dict(regions=[dict(label='fixture_' + name,
            snes=[self.f.profile['origins'][name]['snes'][0],
                  self.f.profile['origins'][name]['snes'][0] + 1]) for name in ('code', 'graphics')])
        if palette is not None:
            code_lo, code_hi = self.f.profile['origins']['code']['snes']
            observed['regions'].append(dict(label='ProjectBGPalette_Code', snes=[code_lo + 0x800, code_hi]))
        consumers = self.f.root / 'compiled-consumers.json'
        consumers.write_bytes(X.P.encoded(observed))
        prepared = dict(base_rom=self.f.profile['base_rom'], saved_rom_sha256=X.R.sha(self.f.source),
            compiled_consumers=X.Q.bound(consumers), current_source_profile=self.f.profile,
            terrain_plan=dict(writes=[]), tables=dict(tables=[], descriptor_pc=[0x305000, 0x305040],
                descriptor_hex=bytes(64).hex()), actor_storage_plan=dict(
                    data_snes=X.A.snes(0x305100), payload_bytes=1, payload_hex='00'),
            resident_source=resident_source, resident_selection=self.selection,
            request=self.f.profile['review']['transfer']['path'], project=self.f.profile['project'])
        if palette is not None:
            prepared.update(bg128_plan=palette, bg128_binding=dict(code_snes=[code_lo + 0x800, code_hi]))
        return prepared, observed

    def test_postassembly_rejects_separately_rehashed_packed_palette(self):
        built = self.construct()
        palette = copy.deepcopy(built['bg128_plan'])
        payload = bytearray.fromhex(palette['payload_hex']); payload[-1] ^= 1
        palette.update(payload_hex=payload.hex(), payload_sha256=X.R.sha(payload))
        prepared, observed = self.output_fixture(built, palette=palette)
        image, symbols = sparse_payload(built['emission'])
        image = bytearray(image)
        at = X.A.pc(palette['data_snes']); image[at:at + len(payload)] = payload
        with mock.patch.object(L, 'inspect_current_consumers', return_value=observed):
            with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_BG128_MISMATCH'):
                X.verify_current_output(prepared, bytes(image), symbols)


class ResidentPlacementReadbackTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        native = R.plan_native_resident_abi(resource_plan(), tile16_count=4096)
        # Deliberately cross the first LoROM-bank boundary through emitter
        # padding. These addresses remain private sparse readback fixtures.
        cls.emission = R.emit_native_resident_abi(native, data_pc=0x347F80,
            capacity=0x20000, preimage=bytes(0x20000))
        cls.compiled, cls.symbols = sparse_payload(cls.emission)

    def test_all_payload_roles_and_bank_padding_read_back(self):
        proof = X.verify_resident_payload(self.emission, self.compiled, self.symbols)
        self.assertEqual(proof['placements_verified'], len(self.emission['placements']))
        self.assertEqual(proof['payload_bytes_verified'], len(bytes.fromhex(self.emission['payload_hex'])))
        self.assertGreater(self.emission['bank_padding_bytes'], 0)
        roles = {row['role'] for row in self.emission['placements']}
        self.assertTrue({'page_directory', 'animation_directory'} <= roles)

    def test_each_compiled_placement_and_missing_label_refuse(self):
        for row in self.emission['placements']:
            wrong = bytearray(self.compiled); wrong[row['pc'][0]] ^= 1
            with self.subTest(role=row['role'], label=row['label']):
                with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_COMPILED_PAYLOAD_MISMATCH'):
                    X.verify_resident_payload(self.emission, bytes(wrong), self.symbols)
        missing = b'\n'.join(line for line in self.symbols.splitlines()
            if not line.endswith(b' ' + self.emission['placements'][1]['label'].encode())) + b'\n'
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_PLACEMENT_MISMATCH'):
            X.verify_resident_payload(self.emission, self.compiled, missing)

    def test_payload_hash_and_directory_coverage_tamper_refuse(self):
        changed = copy.deepcopy(self.emission); changed['payload_sha256'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_PAYLOAD_STALE'):
            X.verify_resident_payload(changed, self.compiled, self.symbols)
        changed = copy.deepcopy(self.emission); changed['placements'][1]['role'] = 'unqualified'
        with self.assertRaisesRegex(ValueError, 'CURRENT_RESIDENT_PLACEMENT_COVERAGE_MISMATCH'):
            X.verify_resident_payload(changed, self.compiled, self.symbols)


class ConditionalDemandBindingTest(unittest.TestCase):
    """Real binder/Git/files around a disclosed synthetic Save-transfer seam.

    Receipt/context files and the minimal request are host fixtures. The real
    binder authenticates their hashes, source epoch, feature files, exact recipe
    bytes and independently derived artifact. No verifier or native Save runs.
    """
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(prefix='lyra-conditional-binding-')
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        for relative in R.CONDITIONAL_SOURCE_FILES:
            path = self.root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes((ROOT / relative).read_bytes())
        self.git('init', '-q')
        self.git('config', 'user.name', 'Conditional binding fixture')
        self.git('config', 'user.email', 'fixture@example.invalid')
        self.commit()
        self.epoch = self.git('rev-parse', 'HEAD').strip()
        patch = mock.patch.object(X.P, 'ROOT', self.root)
        patch.start(); self.addCleanup(patch.stop)
        pure = resources.ConditionalDemandTest()
        fixture = pure.fixture()
        fixture.map_tiles[0][0] = 0x34
        fixture.map_tiles[1][7] = 0x36
        self.source, self.document, self.inspection, terrain_hash, _ = pure.inputs(fixture)
        self.source_path = self.root / 'saved-source.bin'
        self.source_path.write_bytes(self.source)
        self.terrain = self.root / 'saved-terrain.json'
        self.terrain.write_bytes(json.dumps(dict(maps=fixture.map_tiles,
            authoring=self.document.authoring, areas=fixture.areas), sort_keys=True).encode())
        self.assertEqual(X.Q.bound(self.terrain)['sha256'], terrain_hash)
        self.project = self.root / 'saved-project.yaze'
        self.project.write_text('[rom]\nrole=dev\n')
        self.receipt = self.root / 'native-save.json'
        self.context = self.root / 'native-context.json'
        self.producer = self.root / 'selected-producer.json'
        for path, kind in ((self.receipt, 'synthetic_receipt'), (self.context, 'synthetic_context'),
                           (self.producer, 'synthetic_producer')):
            path.write_bytes(X.P.encoded(dict(kind=kind, generation=1)))
        self.inspection.update(project_descriptor_identity_status='identified',
            project_descriptor_path=str(self.project),
            project_descriptor_sha256=X.Q.bound(self.project)['sha256'], terrain_path=str(self.terrain))
        self.inspection_path = self.root / 'retained-inspection.json'
        self.inspection_path.write_bytes(X.P.encoded(self.inspection))
        inputs = dict(project=X.Q.bound(self.project), rom=X.Q.bound(self.source_path),
                      terrain=X.Q.bound(self.terrain))
        self.request = dict(kind=X.KIND, inputs=inputs, live=dict(generation=1,
            operation_id='synthetic-native-save-1', save_receipt=X.Q.bound(self.receipt),
            save_context=X.Q.bound(self.context), project=str(self.project), inputs=copy.deepcopy(inputs),
            producer=X.Q.bound(self.producer), producer_identity=dict(
                source_bindings=[X.Q.bound(self.inspection_path)])))
        self.request['transfer_id'] = X._identity(self.request)
        self.request_path = self.root / 'immutable-transfer.json'
        self.request_path.write_bytes(X.P.encoded(self.request))
        self.recipe = self.root / 'selected-tail-recipe.json'
        self.recipe.write_bytes(X.P.encoded({f'{page:02X}': {} for page in range(0xA0, 0xC0)}))
        self.artifact = self.root / 'selected-conditional-demands.json'

    def git(self, *args):
        return subprocess.check_output(['git', '-C', str(self.root), *args], stderr=subprocess.PIPE).decode()

    def commit(self):
        self.git('add', '-A')
        self.git('commit', '-qm', 'Independent conditional source binding fixture')

    def bind(self, *, artifact=None, request=None, source=None, inspection=None, source_epoch=None):
        return X.conditional_demands_inputs(self.request if request is None else request,
            self.source if source is None else source, self.document,
            self.inspection if inspection is None else inspection, tail_recipe=self.recipe,
            artifact=artifact, source_epoch=self.epoch if source_epoch is None else source_epoch)

    def write_artifact(self, witness):
        self.artifact.write_bytes(X.P.encoded(witness))
        return self.artifact

    def public_review(self, *, artifact=None, **kwargs):
        with mock.patch.object(X, 'verify_transfer', return_value=(self.request, self.source, self.document)):
            return X.resident_graphics_plan(self.request_path, self.project, self.source_path,
                self.inspection_path, tail_recipe=self.recipe, conditional_demands=artifact,
                conditional_source_epoch=self.epoch, **kwargs)

    def test_post_save_artifact_rederives_with_bound_recipe_epoch_and_save_inputs(self):
        before = {path: path.read_bytes() for path in (self.source_path, self.terrain, self.recipe)}
        generated = self.bind()
        witness = generated['witness']
        selected = self.bind(artifact=self.write_artifact(witness))
        self.assertEqual(selected['witness'], witness)
        self.assertEqual(selected['selection'], dict(tail_recipe=X.Q.bound(self.recipe),
            artifact=X.Q.bound(self.artifact), source_epoch=self.epoch))
        for path in (self.recipe, self.artifact, self.receipt, self.context,
                     *(self.root / name for name in R.CONDITIONAL_SOURCE_FILES)):
            self.assertIn(X.Q.bound(path), selected['bindings'])
        self.assertNotIn(X.Q.bound(self.artifact), self.request['live']['producer_identity']['source_bindings'])
        self.assertEqual(witness['source_policy']['save_identity']['transfer_id'], self.request['transfer_id'])
        self.assertEqual(witness['source_policy']['save_identity']['generation'], 1)
        self.assertEqual(witness['additional_rows'], [dict(map_id=0xA0, tile16_id=0xDC9),
                                                     dict(map_id=0xA1, tile16_id=0xDC7)])
        self.assertTrue(witness['known_conditional_demands_ready'])
        for key in ('selected', 'allocation_granted', 'ordinary_build_ready', 'runtime_admission',
                    'resource_closure_verified', 'compiled_consumers_verified'):
            self.assertIs(witness[key], False)
        self.assertEqual({path: path.read_bytes() for path in before}, before)

    def test_rehashed_missing_extra_and_changed_trigger_rows_refuse(self):
        original = self.bind()['witness']
        for change in ('missing', 'extra', 'trigger'):
            witness = copy.deepcopy(original)
            if change == 'missing':
                witness['rows'].pop()
            elif change == 'extra':
                row = copy.deepcopy(witness['rows'][0]); row['map_id'] = 0xA2
                witness['rows'].append(row)
            else:
                witness['rows'][0]['triggers'][0]['cell_index'] += 1
            resources.ConditionalDemandTest.rehash(witness)
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_ARTIFACT_MISMATCH'):
                self.bind(artifact=self.write_artifact(witness))

    def test_rebound_recipe_source_and_definition_cannot_reuse_the_artifact(self):
        artifact = self.write_artifact(self.bind()['witness'])
        before = self.recipe.read_bytes()
        recipe = json.loads(before); recipe['A0']['hidden_items'] = 1
        self.recipe.write_bytes(X.P.encoded(recipe))
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_ARTIFACT_MISMATCH'):
            self.bind(artifact=artifact)
        self.recipe.write_bytes(before)
        changed = bytearray(self.source); changed[0x1234] ^= 1
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_SAVE_MISMATCH'):
            self.bind(artifact=artifact, source=bytes(changed))
        changed = bytearray(self.source)
        at = X.A.pc(int.from_bytes(changed[0x865:0x868], 'little')) + 0xDC9 * 8
        changed[at] ^= 1
        source_path = self.root / 'changed-definitions.bin'; source_path.write_bytes(changed)
        request = copy.deepcopy(self.request); request['inputs']['rom'] = X.Q.bound(source_path)
        request['transfer_id'] = X._identity(request)
        inspection = copy.deepcopy(self.inspection); inspection['source_rom_sha256'] = X.R.sha(changed)
        with self.assertRaisesRegex(ValueError, 'CONDITIONAL_DEFINITION_HASH_MISMATCH'):
            self.bind(artifact=artifact, source=bytes(changed), request=request, inspection=inspection)

    def test_changed_source_epoch_and_uncommitted_semantic_file_refuse(self):
        artifact = self.write_artifact(self.bind()['witness'])
        path = self.root / 'Items/ice_rod.asm'
        path.write_bytes(path.read_bytes() + b'\n; Fixture epoch changes without gameplay edits.\n')
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_SOURCE_CHANGED'):
            self.bind(artifact=artifact)
        self.commit()
        newer = self.git('rev-parse', 'HEAD').strip()
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_SOURCE_EPOCH_MISMATCH'):
            self.bind(artifact=artifact, source_epoch=newer)
        fresh = self.bind(source_epoch=newer)
        self.assertEqual(fresh['witness']['source_policy']['source_epoch'], newer)
        self.assertNotEqual(fresh['witness']['witness_sha256'], json.loads(artifact.read_bytes())['witness_sha256'])

    def test_changed_save_generation_operation_inspection_and_transfer_refuse(self):
        artifact = self.write_artifact(self.bind()['witness'])
        for key, value in (('generation', 2), ('operation_id', 'synthetic-native-save-2')):
            request = copy.deepcopy(self.request); request['live'][key] = value
            request['transfer_id'] = X._identity(request)
            with self.subTest(field=key), self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_ARTIFACT_MISMATCH'):
                self.bind(artifact=artifact, request=request)
        inspection = copy.deepcopy(self.inspection); inspection['retained_fixture_revision'] = 2
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_ARTIFACT_MISMATCH'):
            self.bind(artifact=artifact, inspection=inspection)
        request = copy.deepcopy(self.request); request['transfer_id'] = '0' * 64
        with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_TRANSFER_MISMATCH'):
            self.bind(artifact=artifact, request=request)

    def test_late_recipe_and_save_context_writes_invalidate_bound_inputs(self):
        derive = R.derive_conditional_demands
        for path in (self.recipe, self.context):
            original = path.read_bytes()

            def change_after_derivation(*args, **kwargs):
                result = derive(*args, **kwargs)
                path.write_bytes(b'{}')
                return result

            try:
                with mock.patch.object(R, 'derive_conditional_demands', side_effect=change_after_derivation):
                    with self.subTest(path=path.name), self.assertRaisesRegex(ValueError, 'Current saved input changed'):
                        self.bind()
            finally:
                path.write_bytes(original)

    def test_public_review_preserves_conditional_selection_and_rejects_recipe_drift(self):
        artifact = self.write_artifact(self.bind()['witness'])
        review = self.public_review(artifact=artifact)
        self.assertEqual(review['conditional_demands'], json.loads(artifact.read_bytes()))
        self.assertEqual(review['appearance']['resident_graphics']['conditional_demands'], review['conditional_demands'])
        self.assertEqual(X.conditional_review_kwargs(review), dict(tail_recipe=str(self.recipe),
            conditional_demands=str(artifact), conditional_source_epoch=self.epoch))
        self.recipe.write_bytes(b'{}')
        with self.assertRaisesRegex(ValueError, 'Current saved input changed'):
            X.conditional_review_kwargs(review)

    def test_public_review_rejects_artifact_without_recipe_and_a_later_save(self):
        artifact = self.write_artifact(self.bind()['witness'])
        with mock.patch.object(X, 'verify_transfer', return_value=(self.request, self.source, self.document)):
            with self.assertRaisesRegex(ValueError, 'CURRENT_CONDITIONAL_RECIPE_REQUIRED'):
                X.resident_graphics_plan(self.request_path, self.project, self.source_path,
                    self.inspection_path, conditional_demands=artifact)
        later = copy.deepcopy(self.request); later['live']['generation'] = 2
        later['transfer_id'] = X._identity(later)
        with mock.patch.object(X, 'verify_transfer', side_effect=[(self.request, self.source, self.document),
                                                                (later, self.source, self.document)]):
            with self.assertRaisesRegex(ValueError, 'RESIDENT_TRANSFER_STALE'):
                X.resident_graphics_plan(self.request_path, self.project, self.source_path,
                    self.inspection_path, tail_recipe=self.recipe, conditional_demands=artifact,
                    conditional_source_epoch=self.epoch)


if __name__ == '__main__':
    unittest.main()
