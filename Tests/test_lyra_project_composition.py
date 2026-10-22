"""Private byteplan proof; no ROM file writer, emulator or production admission."""
import contextlib
import io
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import lyra_project_composition as C
import lyra_project_admission as A
import lyra_project_delta as D
import lyra_native_streams as N
import lyra_project_tile32 as T32

REQUEST = Path('/Users/scawful/.context/projects/oracle-of-secrets/scratchpad/handoffs/'
    'christmas_completion_2026-10-20/credit-phase/composition/REQUEST.json')


class CompositionWriteTest(unittest.TestCase):
    def test_memory_only_writer_refuses_overlap_resize_stale_and_out_of_bounds(self):
        source = bytes(16)
        row = dict(pc=[2, 4], preimage_hex='0000', payload_hex='1234')
        self.assertEqual(C.apply_writes(source, [row]), b'\x00\x00\x12\x34' + bytes(12))
        for writes in ([row, row], [dict(row, payload_hex='12')],
                       [dict(row, preimage_hex='1234')], [dict(row, pc=[15, 17])]):
            with self.subTest(writes=writes), self.assertRaises(ValueError):
                C.apply_writes(source, writes)
        self.assertEqual(source, bytes(16))


@unittest.skipUnless(REQUEST.exists(), 'Exact private saved/fresh inputs are not available in CI')
class ActualCompositionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.request = json.loads(REQUEST.read_bytes())
        if not all(Path(p).exists() for p in cls.request.values()):
            raise unittest.SkipTest('Exact private saved/fresh inputs are unavailable')
        cls.plan = C.plan_composition(cls.request)
        cls.source = Path(cls.request['rom']).read_bytes()
        cls.saved = Path(cls.request['saved_rom']).read_bytes()
        manifest = json.loads(Path(cls.request['power_manifest']).read_bytes())
        cls.fixture = Path(manifest['inputs']['candidate_fixture_rom']['path']).read_bytes()
        # Independent replay, not the coordinator's apply_writes helper.
        proposed = bytearray(cls.source)
        for row in cls.plan['writes']:
            start, end = row['pc']
            assert proposed[start:end].hex() == row['preimage_hex']
            proposed[start:end] = bytes.fromhex(row['payload_hex'])
        cls.proposed = bytes(proposed)

    def test_actual_native37_and_a1_decode_from_proposed_pointer_tables(self):
        p = self.plan
        self.assertEqual(C.R.sha(self.proposed), p['proposed_rom_sha256'])
        self.assertEqual(D.native_map_grid(self.proposed, 0x37), D.native_map_grid(self.fixture, 0x37))
        before, after = D.native_map_grid(self.source, 0x37), D.native_map_grid(self.proposed, 0x37)
        self.assertEqual(sum(a != b for old, new in zip(before, after) for a, b in zip(old, new)), 21)
        self.assertEqual(len(p['native37']['changed_block_indices']), 8)
        old_ids = [a << 8 | b for a, b in zip(*(N._plane(self.source, 0x37, t)[0] for t in N.POINTER_TABLES))]
        self.assertEqual(sum(a == b for a, b in zip(old_ids, p['native37']['tile32_ids'])), 248)
        planes = []
        for at in p['a1']['relocated_pointer_tables_pc']:
            pointer = int.from_bytes(self.proposed[at + 0xA1 * 3:at + 0xA1 * 3 + 3], 'little')
            planes.append(A._decode_plane(self.proposed, pointer))
        ids = [a << 8 | b for a, b in zip(*planes)]
        self.assertEqual(len(ids), 256)
        grid = [0] * 1024
        for cell, tile in enumerate(ids):
            y, x = divmod(cell, 16)
            for q, v in enumerate(A.read_tile32(self.proposed, tile)):
                grid[(y * 2 + q // 2) * 32 + x * 2 + q % 2] = v
        terrain = json.loads(Path(self.request['terrain']).read_bytes())
        self.assertEqual(grid, [value for row in terrain['maps'][1]['tiles16'] for value in row])

    def test_other159_components_pointers_all_dictionary_neighbors_and_profiles(self):
        for area in range(160):
            if area != 0x37:
                for table in N.POINTER_TABLES:
                    at = A.pc(table) + area * 3
                    self.assertEqual(self.source[at:at + 3], self.proposed[at:at + 3])
                    self.assertEqual(N._plane(self.source, area, table)[0], N._plane(self.proposed, area, table)[0])
            self.assertEqual(N.native_profile(self.source, area), N.native_profile(self.proposed, area))
        emitted = {r['tile32_id']: tuple(r['quadrants']) for r in self.plan['a1']['emitted_definitions']}
        self.assertEqual(len(emitted), 55)
        for i in range(0x4540):
            self.assertEqual(A.read_tile32(self.proposed, i), emitted.get(i, A.read_tile32(self.source, i)))
        self.assertEqual(len(self.plan['frozen60_not_emitted']), 60)
        self.assertEqual(self.plan['unassigned13_preserved'], list(range(0x4533, 0x4540)))

    def test_disjoint_children_scope_preimages_banks_and_dormant_tables(self):
        intervals = []
        allowed = set()
        for row in self.plan['writes']:
            lo, hi = row['pc']
            self.assertTrue(all(hi <= a or lo >= b for a, b in intervals))
            intervals.append((lo, hi))
            allowed.update(range(lo, hi))
            self.assertEqual(self.source[lo:hi].hex(), row['preimage_hex'])
            if row['kind'].endswith('_stream'):
                self.assertTrue(0x3D4000 <= lo < hi <= 0x3D440C)
                self.assertEqual(lo // 0x8000, (hi - 1) // 0x8000)
            elif row['kind'].startswith('dormant_'):
                self.assertTrue(A.TABLE_START <= lo < hi <= A.TABLE_END)
            elif row['kind'] == 'native37_pointer':
                self.assertIn(lo, [A.pc(t) + 0x37 * 3 for t in N.POINTER_TABLES])
            else:
                self.assertEqual(row['kind'], 'a1_dictionary_group')
                self.assertTrue(any(base + 0x44C0 // 4 * 6 <= lo < hi <= base + 0x4540 // 4 * 6
                                    for base in A.TILE32_BASES))
        self.assertTrue(all(a == b or i in allowed for i, (a, b) in enumerate(zip(self.source, self.proposed))))
        self.assertEqual(self.plan['stream_children'], [dict(owner='native37', pc=[0x3D4000, 0x3D4206]),
            dict(owner='isolated_a1', pc=[0x3D4206, 0x3D440C])])
        self.assertEqual(self.plan['stream_bytes'], 1036)
        self.assertEqual(self.source[A.CODE_START:A.CODE_END], self.proposed[A.CODE_START:A.CODE_END])
        self.assertFalse(self.plan['ingress_installed'])

    def test_frozen_meaning_and_state_recognition_stay_distinct_from_acceptance(self):
        frozen = json.loads(Path(self.request['frozen_assignment']).read_bytes())
        self.assertEqual(self.plan['lineage_binding']['frozen_assignments'], frozen['assignments'])
        self.assertEqual(set(self.plan['original_contract_fresh_refusals']), {'historical', 'current'})
        state = self.plan['native_state_contract']
        self.assertTrue(state['consumers_verified'])
        self.assertEqual(state['persistent_event_storage']['base'], 0x7EF4C0)
        self.assertFalse(state['runtime_ready'])
        self.assertIn('SAVE_DEATH_CONTINUE_POLICY_UNCHOSEN', [r['code'] for r in state['runtime_blockers']])
        self.assertEqual(self.plan['production_maps'], [])
        self.assertEqual(self.plan['production_edge_ids'], [])
        self.assertFalse(self.plan['runtime_build_ready'])

    def test_collision_extra_partial_operand_reader_and_atlas_drift_refuse(self):
        for at, value in ((0x71840, self.source[0x71840] ^ 1), (0x715DC, 0x51),
                          (0x715DD, 0), (0x864, 0), (0x86E, 0), (0x1E8000, self.source[0x1E8000] ^ 1)):
            with self.subTest(at=at):
                changed = bytearray(self.source)
                changed[at] = value
                with self.assertRaises(ValueError):
                    C.collision_projection(self.saved, changed, [])

    def test_changed_tile8_quarter_is_refused(self):
        with self.assertRaisesRegex(ValueError, 'tile8'):
            C.collision_projection(self.saved, self.source, [[[0xB7]]])

    def test_every_write_category_and_crossing_stream_alias_refuse(self):
        examples = {}
        for row in self.plan['writes']:
            examples.setdefault(row['kind'], row['pc'])
        for kind, (lo, hi) in examples.items():
            for crossing in (0, 8):
                with self.subTest(kind=kind, crossing=crossing):
                    raw = bytearray(self.source)
                    target = lo - crossing
                    raw[target:target + 259] = b'\xe0\xff' + bytes(256) + b'\xff'
                    at = A.pc(N.POINTER_TABLES[0])
                    raw[at:at + 3] = A.snes(target).to_bytes(3, 'little')
                    with self.assertRaisesRegex(ValueError, 'alias native map00'):
                        N.reject_stream_aliases(raw, [(lo, hi)])

    def test_stale_source_ledger_manifest_fixture_promotion_binding_and_anchor_refuse(self):
        original = Path.read_bytes
        anchor = Path(C.__file__).resolve().parents[2] / 'Items/ice_rod.asm'
        for key in ('rom', 'saved_rom', 'ledger', 'historical_ledger', 'power_manifest',
                    'frozen_assignment', 'terrain', 'symbols', 'build_receipt', 'authoring_observation', 'anchor'):
            target = anchor if key == 'anchor' else Path(self.request[key]).resolve()
            def changed(path, target=target):
                raw = original(path)
                return bytes([raw[0] ^ 1]) + raw[1:] if path.resolve() == target else raw
            with self.subTest(key=key), mock.patch.object(Path, 'read_bytes', changed):
                with self.assertRaisesRegex(ValueError, 'pinned input differs'):
                    C.plan_composition(self.request)

    def test_public_tile32_cli_mode_and_exclusion(self):
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            T32.main(['--compose-native37-a1', str(REQUEST)])
        plan = json.loads(output.getvalue())
        self.assertEqual(plan['proposed_rom_sha256'], self.plan['proposed_rom_sha256'])
        self.assertEqual(plan['request_sha256'], C.R.sha(REQUEST.read_bytes()))
        with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            T32.main(['--request', 'unused.json', '--compose-native37-a1', str(REQUEST)])


if __name__ == '__main__':
    unittest.main()
