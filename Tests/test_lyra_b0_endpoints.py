"""Existing-row B0 lowering; disposable fixtures, never a saved/game ROM."""
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Scripts/Build'))
import lyra_native_state as S
import lyra_project_composition as C
import test_lyra_native_state as state_fixtures
import test_lyra_project_admission as admission_fixtures


AREA = dict(parent_map_id=0xB0, size='large', maps=[0xB0, 0xB1, 0xB8, 0xB9])


def source_fixture():
    source = bytearray(admission_fixtures.source_rom())
    # Preserve the common terrain fixture while adding actual native consumers.
    native = state_fixtures.fixture(inline=True)
    for name, label, at, raw in S.BINDINGS:
        state_fixtures.put(source, at, bytes.fromhex(raw))
    state_fixtures.put(source, 0x1BBBF4, state_fixtures.INLINE_ENTRANCE_BODY)
    for at, count in ((0x02D998, 19), (0x0FF008, len(S.ENTRANCE_ROOM_TRAMPOLINE)),
                      (0x0F8016, 2), (S.ENTRANCE_SCREENS, 258),
                      (S.ENTRANCE_TILES, 258), (S.ENTRANCE_IDS, 129), (S.EXIT_ROOMS, 158)):
        state_fixtures.put(source, at, S._read(native, at, count))
    state_fixtures.put(source, 0x02E4D4, S.EXIT_GEOMETRY_BYTES)
    state_fixtures.put(source, 0x288998+0x4B, b'\x4b')
    state_fixtures.put(source, 0x02F88D+0x4B, b'\x01')
    # Literal independent current-record readback, not the implementation constant.
    records = {
        40: [0x84, 0x4B, 3736, 984, 1728, 1064, 1848, 1095, 1855, 7, 250, 0, 0],
        41: [0x83, 0x4B, 5920, 1256, 1792, 1336, 1912, 1367, 1919, 10, 14, 0, 0],
        43: [0x76, 0x4B, 1680, 720, 1672, 800, 1792, 831, 1799, 10, 254, 0, 0],
        44: [0x86, 0x4B, 5592, 1200, 2248, 1280, 2368, 1311, 2375, 10, 250, 0, 0],
    }
    for row, values in records.items():
        for (_, at, stride), value in zip(S.EXIT_FIELDS, values):
            state_fixtures.put(source, at+row*stride, value.to_bytes(stride, 'little'))
    return bytes(source)


def authored_document():
    raw = admission_fixtures.document()
    raw.update(schema_version=5, gameplay_areas=[copy.deepcopy(AREA)])
    raw['maps'][16]['authoring'].update(
        doors=[dict(id=24577, entrance_id=0x0B, x=21, y=9)],
        exits=[dict(id=24578, room_id=0x83, exit_row=None, x=22, y=11)])
    return raw


def simple_document():
    raw = authored_document()
    return SimpleNamespace(authoring=tuple(r['authoring'] for r in raw['maps']),
                           gameplay_areas=raw['gameplay_areas'])


class B0EndpointTest(unittest.TestCase):
    def setUp(self):
        self.source = source_fixture()
        self.document = simple_document()

    def test_exact_geometry_and_all_other_rows_preserved_without_source_mutation(self):
        before = copy.deepcopy(self.document)
        plan = S.plan_b0_endpoints(self.source, self.document)
        result, authoring = S.project_b0_endpoints(self.source, self.document, plan)
        self.assertEqual(plan['after_return'], dict(room=0x83, map=0xB0, vram=0x031C,
            scroll_y=3168, scroll_x=232, player_y=3248, player_x=352,
            camera_y=3279, camera_x=359, scroll_mod_y=10, scroll_mod_x=14, door1=0, door2=0))
        self.assertEqual(S._read(result, S.ENTRANCE_TILES+53*2, 2), b'\xaa\x04')
        self.assertEqual(S._read(result, S.ENTRANCE_IDS+53, 1), b'\x0b')
        self.assertEqual(sum(b-a for a,b in (r['pc'] for r in plan['writes'])), 19)
        allowed = {i for row in plan['writes'] for i in range(*row['pc'])}
        self.assertTrue(all(a == b or i in allowed for i,(a,b) in enumerate(zip(self.source,result))))
        for row in (40, 43, 44):
            for _, at, stride in S.EXIT_FIELDS:
                self.assertEqual(S._read(result, at+row*stride, stride), S._read(self.source, at+row*stride, stride))
        self.assertEqual(self.document, before)
        self.assertIsNone(self.document.authoring[16]['exits'][0]['exit_row'])
        self.assertEqual(authoring[16]['exits'][0]['exit_row'], 41)
        proof = S.verify_b0_endpoints(self.source, result, self.document, plan)
        self.assertTrue(proof['other_rows_preserved'])
        self.assertFalse(plan['allocation_granted'])
        self.assertFalse(proof['native_gameplay_verified'])

    def test_each_return_preimage_field_and_dispatch_consumer_refuse_drift(self):
        addresses = [at+41*stride for _,at,stride in S.EXIT_FIELDS]
        addresses += [S.ENTRANCE_SCREENS+53*2, S.ENTRANCE_TILES+53*2,
                      S.ENTRANCE_IDS+53, 0x02E4BD, 0x02E4C4, 0x02E4DD, 0x02E51D, 0x02E565, 0x02D998,
                      0x0F8016, 0x0FF008, 0x1BBBF4, 0x288998+0x4B, 0x02F88D+0x4B]
        for at in addresses:
            changed = bytearray(self.source); changed[S._pc(at)] ^= 1
            with self.subTest(snes=hex(at)), self.assertRaises(ValueError):
                S.plan_b0_endpoints(changed, self.document)

    def test_duplicate_existing_keys_and_destination_conflicts_refuse(self):
        for at, raw in ((S.ENTRANCE_IDS+128, b'\x0b'), (S.EXIT_ROOMS+78*2, b'\x83\x00')):
            changed = bytearray(self.source); state_fixtures.put(changed, at, raw)
            with self.subTest(snes=hex(at)), self.assertRaises(ValueError):
                S.plan_b0_endpoints(changed, self.document)
        for row in (1, 128):
            changed = bytearray(self.source)
            state_fixtures.put(changed, S.ENTRANCE_SCREENS+row*2, b'\xb0\x00')
            state_fixtures.put(changed, S.ENTRANCE_TILES+row*2, b'\xaa\x04')
            with self.subTest(row=row), self.assertRaisesRegex(ValueError, 'DESTINATION_CONFLICT'):
                S.plan_b0_endpoints(changed, self.document)

    def test_missing_layout_changed_placement_or_wrong_explicit_row_refuse(self):
        mutations = [lambda d: d.gameplay_areas.clear(),
            lambda d: d.authoring[16]['doors'][0].update(x=22),
            lambda d: d.authoring[16]['exits'][0].update(exit_row=40),
            lambda d: d.authoring[16]['exits'][0].update(y=12)]
        for mutate in mutations:
            changed = copy.deepcopy(self.document); mutate(changed)
            with self.assertRaises(ValueError): S.plan_b0_endpoints(self.source, changed)
        self.document.authoring[16].update(doors=[], exits=[])
        self.assertIsNone(S.plan_b0_endpoints(self.source, self.document))

    def test_forged_plan_and_stale_apply_preimage_refuse(self):
        plan = S.plan_b0_endpoints(self.source, self.document)
        forged = copy.deepcopy(plan); forged['writes'][0]['payload_hex'] = 'b100'
        with self.assertRaisesRegex(ValueError, 'PLAN_MISMATCH'):
            S.emit_b0_endpoints(self.source, self.document, forged)
        stale = bytearray(self.source); stale[plan['writes'][0]['pc'][0]] ^= 1
        with self.assertRaisesRegex(ValueError, 'preimage differs'):
            C.apply_writes(stale, plan['writes'])

    def test_compiled_tamper_in_target_or_any_other_shrine_record_refuses(self):
        plan = S.plan_b0_endpoints(self.source, self.document)
        result, _ = S.project_b0_endpoints(self.source, self.document, plan)
        for row in (40, 41, 43, 44):
            for _, at, stride in S.EXIT_FIELDS:
                changed = bytearray(result); changed[S._pc(at+row*stride)] ^= 1
                with self.subTest(row=row, field=hex(at)), self.assertRaisesRegex(ValueError, 'COMPILED_TABLE_MISMATCH'):
                    S.verify_b0_endpoints(self.source, changed, self.document, plan)
        changed = bytearray(result); changed[S._pc(S.ENTRANCE_IDS+128)] ^= 1
        with self.assertRaisesRegex(ValueError, 'COMPILED_TABLE_MISMATCH'):
            S.verify_b0_endpoints(self.source, changed, self.document, plan)

    def test_actual_asar_emission_and_preimage_assertion(self):
        asar = os.environ.get('ASAR_BIN') or shutil.which('asar')
        if not asar: self.skipTest('Asar unavailable')
        plan = S.plan_b0_endpoints(self.source, self.document)
        text = 'lorom\n'+S.emit_b0_endpoints(self.source, self.document, plan)
        with tempfile.TemporaryDirectory(prefix='oos-b0-asar-') as folder:
            root = Path(folder); asm = root/'endpoints.asm'; rom = root/'fixture.sfc'
            asm.write_text(text); rom.write_bytes(self.source)
            argv = [asar, '--no-title-check', '--fix-checksum=off', str(asm), str(rom)]
            run = subprocess.run(argv, capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout+run.stderr)
            expected, _ = S.project_b0_endpoints(self.source, self.document, plan)
            self.assertEqual(rom.read_bytes(), expected)
            tampered = bytearray(self.source); tampered[plan['writes'][0]['pc'][0]] ^= 1
            rom.write_bytes(tampered)
            refused = subprocess.run(argv, capture_output=True, text=True)
            self.assertNotEqual(refused.returncode, 0)
            self.assertIn('B0 endpoint preimage differs', refused.stdout+refused.stderr)
            self.assertEqual(rom.read_bytes(), tampered)
            print(json.dumps(dict(asar=str(Path(asar).resolve()),
                asar_sha256=hashlib.sha256(Path(asar).read_bytes()).hexdigest(),
                positive_exit=run.returncode, negative_exit=refused.returncode,
                output_sha256=hashlib.sha256(expected).hexdigest(),
                negative_log=refused.stdout+refused.stderr), sort_keys=True))


class B0CurrentBuildIntegrationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        import test_lyra_current_build as build
        import test_lyra_current_transfer as transfer
        from test_lyra_current_composer_binding import ComposerFixture
        areas = [copy.deepcopy(AREA)]+[dict(parent_map_id=a, size='small', maps=[a])
            for a in range(0xA0, 0xC0) if a not in AREA['maps']]
        def composer(owner, **kwargs):
            return ComposerFixture(owner, gameplay_areas=areas)
        with mock.patch.object(transfer, 'source_rom', source_fixture), \
             mock.patch.object(transfer, 'document', authored_document), \
             mock.patch.object(build, 'ComposerFixture', composer):
            build.CurrentBuildTest.setUpClass.__func__(cls)

    def compiled_image(self):
        import lyra_current_transfer as X
        p = self.prepared; rom = bytearray(self.compiled)
        for row in [*p['terrain_plan']['writes'], *p['tables']['tables'], *p['native_endpoint_plan']['writes']]:
            rom[slice(*row['pc'])] = bytes.fromhex(row['payload_hex'])
        rom[slice(*p['tables']['descriptor_pc'])] = bytes.fromhex(p['tables']['descriptor_hex'])
        actor = p['actor_storage_plan']; at = X.A.pc(actor['data_snes'])
        rom[at:at+actor['payload_bytes']] = bytes.fromhex(actor['payload_hex'])
        return bytes(rom)

    def test_ordinary_fixture_rederives_and_verifies_endpoint_tables(self):
        import lyra_current_transfer as X
        plan = self.prepared['native_endpoint_plan']
        self.assertEqual(plan, S.plan_b0_endpoints(self.f.source, self.f.document))
        state = self.prepared['native_state_contract']
        self.assertEqual(state['image_scope'], 'projected_b0_endpoint_tables')
        self.assertEqual(state['saved_rom_sha256'], X.R.sha(self.f.source))
        self.assertTrue(state['requested_doors'][0]['tile_match_verified'])
        self.assertTrue(state['requested_returns'][0]['position_match_verified'])
        result = X.verify_current_output(self.prepared, self.compiled_image(), self.symbols)
        self.assertTrue(result['native_endpoints']['other_rows_preserved'])
        self.assertFalse(result['runtime_verified'])
        self.assertIsNone(self.f.document.authoring[16]['exits'][0]['exit_row'])
        self.assertEqual(self.case.rom.read_bytes(), self.f.source)
        self.assertFalse(self.case.candidate.exists())

    def test_omitted_or_changed_plan_and_other_shrine_compiled_change_refuse(self):
        import lyra_current_transfer as X
        compiled = self.compiled_image()
        missing = copy.deepcopy(self.prepared); missing.pop('native_endpoint_plan')
        with self.assertRaisesRegex(ValueError, 'PREPARED_PLAN_MISMATCH'):
            X.verify_current_output(missing, compiled, self.symbols)
        changed = bytearray(compiled); changed[S._pc(S.EXIT_MAPS+40)] ^= 1
        with self.assertRaisesRegex(ValueError, 'COMPILED_TABLE_MISMATCH'):
            X.verify_current_output(self.prepared, changed, self.symbols)


if __name__ == '__main__':
    unittest.main()
