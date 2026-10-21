"""Post-editor-save assignment, packed nibbles and source/consumer rejection."""
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
import lyra_project_terrain as T
import lyra_project_tile32 as D
from test_lyra_project_admission import document, observation, source_rom


class LyraTile32AssignmentTest(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.ledger = json.loads(R.LEDGER.read_bytes())
        source = bytearray(source_rom().ljust(0x400000, b'\0'))
        for base in A.TILE32_BASES:
            source[base + 0x6720:base + 0x67E0] = bytes.fromhex('a4a4a4a41111') * 32
        self.source = bytes(source)
        self.ledger['rom_candidate_reservations'][0]['tile32_candidate_reservation'][
            'native_decoder']['sha256'] = A.sha(self.source[0x17691:0x177CB])
        for reader in self.ledger['rom_candidate_reservations'][0]['tile32_candidate_reservation']['native_readers']:
            start, end = reader['pc']
            reader['sha256'] = A.sha(self.source[start:end])
        self.path = Path(self.folder.name) / 'ledger.json'
        self.save_ledger()
        patch = mock.patch.object(R, 'LEDGER', self.path)
        patch.start()
        self.addCleanup(patch.stop)

    def save_ledger(self):
        self.path.write_text(json.dumps(self.ledger))

    def request(self, values=(1, 2, 3, 4), area=0xA1):
        data = document()
        cells = data['maps'][area - 0xA0]['tiles16']
        cells[0][:2], cells[1][:2] = list(values[:2]), list(values[2:])
        text, proof = observation(self.source, data)
        return dict(source=self.source, terrain=text.encode(), proof=proof,
            candidate_maps=[area], render_footprints=[dict(map_id=area, quadrant_maps=[area] * 4)])

    def allocation(self, request, contract):
        value = R.derive_allocation(self.source, tile32_assignment=contract)
        value['admission']['candidate_maps'] = request['candidate_maps']
        value['admission']['render_footprints'] = request['render_footprints']
        return value

    def test_joint_requests_share_ids_and_subset_compilation_preserves_packed_neighbors(self):
        first, second = self.request(), self.request((5, 6, 7, 8), 0xB0)
        contract = D.create_contract([second, first])
        self.assertEqual(contract, D.create_contract([first, second]))
        self.assertEqual([r['tile32_id'] for r in contract['assignments']], [0x44C0, 0x44C1])
        self.assertEqual(R.derive_allocation(self.source)['owned_tile32_ids'], [])
        for request in (first, second):
            plan = A.plan_admission(self.source, request['terrain'], request['proof'],
                                   self.allocation(request, contract))
            self.assertTrue(plan['candidate_data_plan_ready'])
            self.assertTrue(plan['tile32_assignment_verified'])
            self.assertEqual(plan['tile32_write_plan']['definition_count'], 1)
            self.assertEqual(plan['tile32_write_plan']['native_maps_preserved'], 160)
            self.assertEqual(len(plan['tile32_write_plan']['writes']), 4)
            for write in plan['tile32_write_plan']['writes']:
                old, new = bytes.fromhex(write['preimage_hex']), bytes.fromhex(write['payload_hex'])
                slot = plan['new_tile32_definitions'][0]['tile32_id'] % 4
                self.assertEqual([new[i] for i in range(4) if i != slot],
                                 [old[i] for i in range(4) if i != slot])
                # The neighboring slot shares a high-nibble byte.
                mask = 15 if slot % 2 == 0 else 240
                self.assertEqual(new[4 + slot // 2] & mask, old[4 + slot // 2] & mask)
            self.assertEqual(plan['production_maps'], [])
            self.assertFalse(plan['runtime_build_ready'])

    def test_terrain_or_footprint_change_cannot_reuse_assignment(self):
        request = self.request()
        contract = D.create_contract([request])
        changed = self.request((7, 8, 9, 10))
        with self.assertRaisesRegex(ValueError, 'terrain/selection/render directory'):
            A.plan_admission(self.source, changed['terrain'], changed['proof'], self.allocation(request, contract))
        value = self.allocation(request, contract)
        value['admission'].pop('render_footprints')
        with self.assertRaisesRegex(ValueError, 'terrain/selection/render directory'):
            A.plan_admission(self.source, request['terrain'], request['proof'], value)

    def test_outer_source_rehash_does_not_refresh_consumer_receipt(self):
        contract = D.create_contract([self.request()])
        changed = bytearray(self.source)
        changed[0x11111] ^= 1
        with self.assertRaisesRegex(ValueError, 'consumer receipt is stale'):
            R.derive_allocation(bytes(changed), tile32_assignment=contract)

    def test_decoder_preimage_and_native_reference_conflicts_refuse(self):
        claim, _ = R.reservation_claim()
        for offset, message in ((0x17691, 'decoder differs'),
                                (0x1E720, 'preimage differs')):
            changed = bytearray(self.source)
            changed[offset] ^= 1
            with self.subTest(offset=offset), self.assertRaisesRegex(ValueError, message):
                D.ownership(bytes(changed), claim)
        changed = bytearray(self.source)
        # The high and low native planes point at this shared fixture stream.
        changed[0x100002] = 0x44
        changed[0x100003] = 0xC0
        # Use separate high/low planes to encode exactly44C0.
        low = 0x110000
        changed[low:low + 259] = b'\xe0\xff' + bytes([0xC0]) * 256 + b'\xff'
        changed[0x100002:0x100102] = bytes([0x44]) * 256
        at = A.pc(0x02FB2D)
        changed[at:at + 3] = A.snes(low).to_bytes(3, 'little')
        with self.assertRaisesRegex(ValueError, 'referenced by native map00'):
            D.ownership(bytes(changed), claim)

    def test_redirected_native_full_or_overlay_pointer_readers_refuse(self):
        claim, _ = R.reservation_claim()
        # Every +0/+1 high/low pointer operand in both native callers is pinned.
        for opcode in (0x1759D, 0x175A3, 0x175C8, 0x175CE,
                       0x177E3, 0x177E9, 0x1780E, 0x17814):
            changed = bytearray(self.source)
            changed[opcode + 1] ^= 1
            with self.subTest(opcode=opcode), self.assertRaisesRegex(ValueError, 'pointer reader differs'):
                D.ownership(bytes(changed), claim)

    def test_packed_bytes_cannot_alias_an_unreferenced_id_native_stream(self):
        # A native plane can use the filler bytes as literal compressed data
        # without ever referencing a reserved dictionary ID. Guard both uses.
        source = bytearray(self.source)
        start, end = 0x1E720 - 66, 0x1E7E0
        tail = bytes(source[0x1E720:end])
        source[start:end + 1] = b'\xe0\xff' + bytes(64) + tail + b'\xff'
        at = A.pc(0x02FB2D)
        source[at:at + 3] = A.snes(start).to_bytes(3, 'little')
        self.source = bytes(source)
        request = self.request()
        contract = D.create_contract([request])
        with self.assertRaisesRegex(ValueError, 'Packed writes change native terrain stream00'):
            A.plan_admission(self.source, request['terrain'], request['proof'], self.allocation(request, contract))

    def test_source_policy_and_foreign_id_or_packed_owner_conflicts_refuse(self):
        contract = D.create_contract([self.request()])
        self.ledger['description'] += ' changed'
        self.save_ledger()
        with self.assertRaisesRegex(ValueError, 'source policy is stale'):
            R.derive_allocation(self.source, tile32_assignment=contract)
        for space, base in (('tile32_id', 0x44C2), ('pc_rom', 0x1E720)):
            self.ledger['claims'].append(dict(id='foreign-private-owner', space=space, base=base, size=1))
            self.save_ledger()
            with self.subTest(space=space), self.assertRaisesRegex(ValueError, 'conflicts with'):
                R.derive_allocation(self.source)
            self.ledger['claims'].pop()

    def test_forged_ids_quartets_and_capacity_refuse(self):
        contract = D.create_contract([self.request()])
        for key, value in (('tile32_id', 0x44BF), ('quadrants', [7, 7, 7, 7])):
            changed = copy.deepcopy(contract)
            changed['assignments'][0][key] = value
            with self.subTest(key=key), self.assertRaisesRegex(ValueError, 'joint assignment differs'):
                R.derive_allocation(self.source, tile32_assignment=changed)
        changed = copy.deepcopy(contract)
        changed['inputs'][0]['missing_definitions'] = [[i, 0, 0, 0] for i in range(129)]
        with self.assertRaisesRegex(ValueError, 'capacity conflict: 129 definitions exceed 128'):
            R.derive_allocation(self.source, tile32_assignment=changed)

    def test_reviewed_compiler_never_falls_back_to_unassigned_capacity(self):
        request = self.request()
        parsed = T.parse_terrain_document(request['terrain'], request['proof']['profile'], allow_authoring_drafts=True)
        native = {i: A.read_tile32(self.source, i) for i in range(0x4540)}
        owned = T.Allocation(((0x3D4000, 0x3D4818),), (0x44C0,), tile32_assignments=())
        with self.assertRaisesRegex(ValueError, 'Missing reviewed Tile32 assignment'):
            T.compile_terrain(parsed, native, owned, map_ids=[0xA1], render_directory={0xA1: (0xA1,) * 4})

    def test_active_metadata_and_natural_stream_budget_stay_blocked(self):
        request = self.request()
        data = json.loads(request['terrain'])
        data['maps'][1]['authoring']['sprites'] = [dict(id=1, sprite_id=0x52, x=1, y=1, state=1)]
        text, proof = observation(self.source, data)
        request.update(terrain=text.encode(), proof=proof)
        contract = D.create_contract([request])
        plan = A.plan_admission(self.source, request['terrain'], proof, self.allocation(request, contract))
        self.assertTrue(plan['tile32_assignment_verified'])
        self.assertFalse(plan['candidate_data_plan_ready'])
        self.assertTrue(any(b['code'] == 'UNSUPPORTED_ACTIVE_METADATA' for b in plan['consumption_blockers']))
        self.assertEqual(plan['streams'], [])
        self.assertIsNone(plan['tile32_write_plan'])
        # Six natural render dependencies still exceed the existing2072bytes.
        allocation = R.derive_allocation(self.source)
        allocation['admission']['candidate_maps'] = [0xB0, 0xB1, 0xB8, 0xB9]
        plan = A.plan_admission(self.source, request['terrain'], proof, allocation)
        self.assertEqual(plan['stream_requirements'], dict(minimum_bytes=3108, reserved_bytes=2072))
        self.assertIn(dict(code='STREAM_ALLOCATION_REQUIRED', minimum_bytes=3108), plan['consumption_blockers'])


if __name__ == '__main__':
    unittest.main()
