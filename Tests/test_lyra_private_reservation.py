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
