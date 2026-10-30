"""Focused private producer-grant tests; all candidate application is in memory."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_project_admission as A
import lyra_project_allocation as R
import lyra_project_prepare as Q
import lyra_project_tile32 as T
import lyra_private_reservation as V
from lyra_project_terrain import Allocation, parse_terrain_document

AFS = Path('/Users/scawful/.context/projects/oracle-of-secrets/scratchpad/handoffs/lyra_current_project_2026-10-22')
REQUEST = AFS / 'repair/preparation/request.json'


class DeclarationTest(unittest.TestCase):
    def test_source_transfer_is_whole_groups_and_half_open_stream_end(self):
        policy = V.declaration()
        self.assertEqual(policy['producer_transfer'], V.TRANSFER)
        self.assertEqual(V.IDS[1] - V.IDS[0], 444)
        self.assertEqual(V.IDS[0] % 4, 0)
        self.assertEqual(V.IDS[1] % 4, 0)
        self.assertEqual(V.STREAM[1] - V.STREAM[0], 66 * 259)
        self.assertEqual((V.STREAM[0] // 0x8000), (V.STREAM[1] - 1) // 0x8000)

    def test_general_low_ranges_still_refuse(self):
        source = bytes(0x400000)
        value = dict(kind='lyra.project_runtime_allocation.v1', source_rom_sha256=R.sha(source),
            expanded_size=0x400000, table_range=[A.TABLE_START, A.TABLE_END],
            code_range=[A.CODE_START, A.CODE_END], stream_ranges=[list(V.STREAM)], owned_tile32_ids=[])
        with self.assertRaisesRegex(ValueError, 'expanded ROM'):
            A.parse_allocation(value, source)
        value['private_reservation'] = {}
        with self.assertRaisesRegex(ValueError, 'Malformed private producer allocation'):
            A.parse_allocation(value, source)

    def test_original_expanded_allocation_remains_supported(self):
        source = bytes(0x400000)
        value = dict(kind='lyra.project_runtime_allocation.v1', source_rom_sha256=R.sha(source),
            expanded_size=0x400000, table_range=[A.TABLE_START, A.TABLE_END],
            code_range=[A.CODE_START, A.CODE_END], stream_ranges=[[0x3D4000, 0x3D4818]], owned_tile32_ids=[])
        self.assertEqual(A.parse_allocation(value, source).stream_ranges, ((0x3D4000, 0x3D4818),))

    def test_named_pc_and_numeric_owners_conflict_even_when_unemitted(self):
        for claim in [dict(id='future_id', space='tile32_id', base=V.IDS[0], size=1),
                      dict(id='future_stream', space='pc_rom', base=V.STREAM[0], size=1),
                      dict(id='future_packed', space='pc_rom', base=119292, size=1)]:
            with self.subTest(claim=claim), self.assertRaisesRegex(ValueError, 'named owner'):
                V.require_no_named_conflicts(dict(claims=[claim]))
        V.require_no_named_conflicts(dict(claims=[dict(id='boundary', space='pc_rom', base=V.STREAM[1], size=1)]))

    def test_unreviewed_source_cannot_create_receipt(self):
        with self.assertRaisesRegex(ValueError, 'exact saved source'):
            V.source_receipt(bytes(0x400000))

    def test_caller_boolean_does_not_prove_yaze_enforcement(self):
        attachment = {'example': True}
        for proof in ({}, dict(kind='lyra.private_producer_enforcement_receipt.v1',
                source_rom_sha256=V.SOURCE, attachment_sha256=T.digest(attachment), enforced=True)):
            with self.subTest(proof=proof), self.assertRaises(ValueError):
                V.verify_producer_evidence(attachment, proof)


class CurrentNativePlanTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from test_lyra_project_admission import source_rom
        cls.source = source_rom()
        cls.directory = A.render_dependency_plan(V.FULL_MAPS)[0]

    def document(self, *, edited=False, palette=False):
        from test_lyra_project_admission import document
        data = document()
        if edited:
            data['maps'][0]['tiles16'][0][0] = 1
        bindings = {}
        if palette:
            data['schema_version'] = 4
            auth = data['maps'][31]['authoring']
            auth['properties']['background_palette'] = list(range(128))
            auth['asset_bindings'] = ['a' * 64] * 3
            bindings[0xBF] = tuple(auth['asset_bindings'])
        return parse_terrain_document(json.dumps(data), data['profile'],
            allow_authoring_drafts=True, expected_asset_bindings=bindings)

    def allocation(self, assignments=(), ranges=((0x300000, 0x308000),)):
        return Allocation(ranges, tuple(i for i, _ in assignments),
                          tile32_assignments=tuple(assignments))

    def compile(self, source, document, allocation, directory, **kwargs):
        # This class tests native packing. The independent current-contract
        # tests exercise source/generation authority without this host stub.
        import lyra_current_transfer as X
        spans = ((0x1759D, 0x175D2), (0x17691, 0x177CB), (0x177E3, 0x17818))
        layout, _ = X._current_table_layout([row[0] for row in A.SPECS]
            + [f'music_phase{i}' for i in range(4)]
            + [f'{family}_phase{phase}'
               for family in ('special_sprite_gfx', 'special_sprite_palettes')
               for phase in (1, 2)])
        profile = dict(kind=X.CURRENT_PROFILE_KIND,
            native_reader_preimages=[dict(pc=list(span), sha256=R.sha(source[slice(*span)])) for span in spans],
            origins=dict(tables=dict(pc=[0x320000, 0x328000])), table_layout=layout)
        with mock.patch.object(X, 'verify_current_native_source_profile'):
            return V.compile_native_plan(source, document, allocation, directory,
                current_source_profile=profile, **kwargs)

    def test_two_mib_current_source_compiles_all32_without_historical_copies(self):
        source = self.source
        plan, payload = self.compile(source, self.document(), self.allocation(), self.directory)
        self.assertEqual(plan['source_rom_sha256'], R.sha(source))
        self.assertEqual(plan['source_size'], 0x200000)
        self.assertEqual(plan['expanded_size'], 0x400000)
        self.assertEqual(plan['selected_maps'], V.FULL_MAPS)
        self.assertEqual(len(plan['streams']), 64)
        self.assertEqual(len(payload), 32 * 518)
        self.assertEqual(plan['native_copies'], [])
        self.assertEqual(plan['emitted_definitions'], [])
        self.assertEqual(plan['native_maps_preserved'], 160)
        self.assertFalse(plan['producer_enforcement_verified'])
        self.assertFalse(plan['ordinary_build_ready'])
        self.assertFalse(plan['runtime_admission'])
        self.assertFalse(plan['rom_written'])
        self.assertEqual(self.source, source)
        self.assertTrue(all(row['preimage_hex'] == 'ff' * 259 for row in plan['writes']))

    def test_current_edit_generates_readback_checked_plan_and_preserves_palette_draft(self):
        parsed = self.document(edited=True, palette=True)
        allocation = self.allocation(((13992, (1, 0, 0, 0)),))
        plan, payload = self.compile(self.source, parsed, allocation, self.directory,
            protected_spans=(V.OLD_A0,), spare_tile32_ids=(13993, 13994, 13995))
        self.assertEqual(plan['emitted_definitions'], [dict(tile32_id=13992, quadrants=[1, 0, 0, 0])])
        candidate = V.C.apply_writes(A.expanded_rom(self.source), plan['writes'])
        self.assertEqual(A.read_tile32(candidate, 13992), (1, 0, 0, 0))
        self.assertEqual(A.read_tile32(candidate, 13993), (0, 0, 0, 0))
        self.assertEqual(candidate[slice(*V.OLD_A0)], self.source[slice(*V.OLD_A0)])
        self.assertEqual(V.N.reject_stream_aliases(candidate, []), V.N.reject_stream_aliases(self.source, []))
        row = next(row for row in plan['appearance']['selector_rows'] if row['map_id'] == 0xBF)
        self.assertEqual(row['background_palette']['word_count'], 128)
        self.assertIn(dict(code='UNSUPPORTED_BACKGROUND_PALETTE', map_id=0xBF), plan['appearance_blockers'])
        self.assertFalse(plan['ordinary_build_ready'])

    def test_current_capacity_is_content_derived_instead_of_frozen566(self):
        from test_lyra_project_admission import document
        data = document()
        for cell in range(600):
            area, offset = divmod(cell, 256)
            y, x = divmod(offset, 16)
            data['maps'][area]['tiles16'][y * 2][x * 2] = cell + 1
        parsed = parse_terrain_document(json.dumps(data), data['profile'])
        pairs = tuple((13992 + i, (i + 1, 0, 0, 0)) for i in range(444))
        with self.assertRaisesRegex(ValueError, '600 required, 444 explicitly allocated'):
            self.compile(self.source, parsed, self.allocation(pairs), self.directory)

    def test_current_native_stream_alias_and_referenced_dictionary_id_refuse(self):
        with self.assertRaisesRegex(ValueError, 'alias native map'):
            self.compile(self.source, self.document(),
                self.allocation(ranges=((0x100000, 0x108000),)), self.directory)
        with self.assertRaisesRegex(ValueError, 'referenced by native map'):
            self.compile(self.source, self.document(edited=True),
                self.allocation(((0, (1, 0, 0, 0)),)), self.directory)

    def test_current_native_definitions_tables_and_readers_are_always_protected(self):
        for span in ((0x1E8000, 0x1F0000), (0x17691, 0x1E000),
                     (0x140000, 0x148000), (0x18000, 0x20000)):
            with self.subTest(span=span), self.assertRaisesRegex(ValueError, 'overlaps native definitions'):
                self.compile(self.source, self.document(),
                    self.allocation(ranges=(span,)), self.directory)
        relocated = bytearray(self.source)
        relocated[0x865:0x868] = A.snes(0x300000).to_bytes(3, 'little')
        with self.assertRaisesRegex(ValueError, 'overlaps native definitions'):
            self.compile(bytes(relocated), self.document(), self.allocation(), self.directory)

    def test_current_native_capacity_is_not_silently_widened(self):
        for capacity in (128, 0x4541, True):
            allocation = Allocation(((0x300000, 0x308000),), tile32_capacity=capacity,
                                    tile32_assignments=())
            with self.subTest(capacity=capacity), self.assertRaisesRegex(ValueError, 'capacity0x4540'):
                self.compile(self.source, self.document(), allocation, self.directory)

    def test_current_copy_and_protected_span_options_preserve_historical_guard(self):
        plan, payload = self.compile(self.source, self.document(), self.allocation(),
            self.directory, native_copy_maps=(0x37,))
        self.assertEqual(len(plan['native_copies']), 2)
        self.assertEqual(len(payload), 33 * 518)
        self.assertEqual(plan['streams'][0]['pc'][0], 0x300000 + 518)
        with self.assertRaisesRegex(ValueError, 'protected source span'):
            self.compile(self.source, self.document(), self.allocation(), self.directory,
                protected_spans=((0x300000, 0x300001),))
        with self.assertRaisesRegex(ValueError, 'Native copies exceed'):
            self.compile(self.source, self.document(),
                self.allocation(ranges=((0x307F00, 0x310000),)), self.directory,
                native_copy_maps=(0x37,))

    def test_current_planning_requires_explicit_assignments_and_supported_physical_size(self):
        with self.assertRaisesRegex(ValueError, 'explicit reviewed Tile32 assignments'):
            self.compile(self.source, self.document(), Allocation(((0x300000, 0x308000),)),
                self.directory)
        for source in (bytes(100), bytes(0x200200), bytearray(self.source)):
            with self.subTest(size=len(source)), self.assertRaisesRegex(ValueError, 'unheadered2MiB or4MiB'):
                self.compile(source, self.document(), self.allocation(), self.directory)


@unittest.skipUnless(REQUEST.exists(), 'Exact saved private source inputs are local qualification evidence')
class SavedPrivateGrantTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(REQUEST.read_bytes())
        cls.source = Q.read_bound(cls.request['inputs']['saved_rom'])
        if R.sha(cls.source) != V.SOURCE:
            raise unittest.SkipTest('Saved project changed')
        cls.attachment = V.create_attachment(REQUEST)

    def test_exact_source_all_native_aliases_external_rows_and_assignments(self):
        native = self.attachment['native_receipt']
        self.assertEqual(native['native_maps'], 160)
        self.assertEqual(native['native_planes'], 320)
        self.assertEqual(len(native['exact_alias_groups']), 3)
        self.assertEqual(len(native['external_saved_reference_rows']), 18)
        self.assertEqual(native['retained_native_ids'], [0x453D, 0x453E, 0x453F])
        self.assertEqual(native['preserved_old_a0']['pc'], [0x132000, 0x132400])
        rows = self.attachment['assignments']
        self.assertEqual(len(rows), 566)
        self.assertEqual([r['tile32_id'] for r in rows[:115]], list(range(0x44C0, 0x4533)))
        self.assertEqual([r['tile32_id'] for r in rows[115:125]], list(range(0x4533, 0x453D)))
        self.assertEqual([r['tile32_id'] for r in rows[125:]], list(range(V.IDS[0], V.IDS[1] - 3)))

    def test_one_changed_byte_expires_attachment_before_evidence(self):
        changed = bytearray(self.source)
        changed[0x11111] ^= 1
        with self.assertRaisesRegex(ValueError, 'source differs'):
            V.verify_attachment(bytes(changed), self.attachment)

    def test_mutated_preimage_range_assignment_or_native_receipt_refuses(self):
        mutations = [('tile32_id_range', [V.IDS[0] - 4, V.IDS[1]]),
                     ('stream_pc_range', [V.STREAM[0] - 1, V.STREAM[1]]),
                     ('packed_preimages', []), ('native_receipt', {}),
                     ('assignments', self.attachment['assignments'][:-1])]
        for field, value in mutations:
            attachment = copy.deepcopy(self.attachment)
            attachment[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'source-owner declaration'):
                V.verify_attachment(self.source, attachment)

    def test_exact_low_range_needs_complete_evidence_and_cannot_expand(self):
        value = V.allocation_value(self.attachment, {})
        with self.assertRaisesRegex(ValueError, 'producer enforcement receipt'):
            A.parse_allocation(value, self.source)
        # Isolate allocation-boundary validation from the independently tested
        # external producer-evidence gate; no test claims a Yaze implementation.
        with mock.patch.object(V, 'verify_producer_evidence'):
            parsed = A.parse_allocation(value, self.source)
            self.assertEqual(parsed.stream_ranges, (V.STREAM,))
            for field, replacement in [('stream_ranges', [[V.STREAM[0] - 1, V.STREAM[1]]]),
                    ('owned_tile32_ids', value['owned_tile32_ids'] + [V.IDS[1] - 1]),
                    ('tile32_assignment', {'assignments': []})]:
                bad = copy.deepcopy(value)
                bad[field] = replacement
                with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'exceeds the exact producer grant'):
                    A.parse_allocation(bad, self.source)

    def test_all32_compiler_and_packed_shared_neighbor_readback_in_memory(self):
        # Pure compiler integration fixture. Concrete Yaze enforcement remains a
        # separate actual-source receipt gate exercised by the qualification CLI.
        with mock.patch.object(V, 'verify_producer_evidence'):
            plan, payload = V.compile_private(REQUEST, self.attachment, {})
        self.assertEqual(plan['selected_maps'], list(range(0xA0, 0xC0)))
        self.assertEqual(len(plan['emitted_definitions']), 566)
        self.assertEqual(len(payload), 17094)
        self.assertEqual(plan['streams'][-1]['pc'][1], 0x138000)
        self.assertEqual(plan['native_maps_preserved'], 160)
        self.assertEqual(plan['spare_tile32_ids_preserved'], [14433, 14434, 14435])
        self.assertFalse(plan['runtime_admission'])
        self.assertFalse(plan['ordinary_build_ready'])
        self.assertFalse(plan['rom_written'])
        self.assertEqual(len(plan['appearance_blockers']), 19)
        self.assertEqual(len(plan['actor_blockers']), 6)

    def test_exact_packed_native_alias_and_neighbor_guard_is_additional_to_hash(self):
        source = bytearray(self.source)
        # Even when deliberately isolating the census from its whole-ROM hash,
        # native aliasing the granted stream rejects before any compilation.
        at = A.pc(0x02F94D)
        source[at:at + 3] = A.snes(V.STREAM[0]).to_bytes(3, 'little')
        with self.assertRaises(ValueError):
            V.N.reject_stream_aliases(bytes(source), [V.STREAM])

    def test_failed_cli_has_no_partial_output_or_source_change(self):
        with tempfile.TemporaryDirectory() as folder:
            folder = Path(folder)
            attachment, evidence = folder / 'attachment.json', folder / 'producer.json'
            attachment.write_text(json.dumps(self.attachment))
            evidence.write_text('{}')
            output = folder / 'refused'
            with self.assertRaisesRegex(ValueError, 'producer enforcement receipt'):
                V.main(['--request', str(REQUEST), '--attachment', str(attachment),
                        '--producer-evidence', str(evidence), '--output', str(output)])
            self.assertFalse(output.exists())
            self.assertEqual(Q.read_bound(self.request['inputs']['saved_rom']), self.source)

    def test_write_preimage_failure_does_not_mutate_source(self):
        row = dict(pc=[V.STREAM[0], V.STREAM[0] + 1], preimage_hex='ff', payload_hex='e0')
        with self.assertRaisesRegex(ValueError, 'preimage differs'):
            V.C.apply_writes(self.source, [row])
        self.assertEqual(Q.read_bound(self.request['inputs']['saved_rom']), self.source)


if __name__ == '__main__':
    unittest.main()
