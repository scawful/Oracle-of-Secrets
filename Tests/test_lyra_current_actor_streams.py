"""Bound authored OW sprite streams; no placement, ROM writer or native run.

Native byte vectors follow Overworld::PrepareSpriteSave and
ReadOverworldSpriteList: Y,X,ID triples plus FF, with no dungeon header. The
existing external native verifier is a host fixture; current profile, saved
generation, reservation review and document verification are real maintained code.
"""
import copy
from dataclasses import replace
import json
from pathlib import Path
import sys
import unittest
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'Scripts/Build'))
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_project_terrain as terrain
import test_lyra_current_source_contract as contract_fixtures
import test_lyra_current_transfer as transfer_fixtures
from test_lyra_project_admission import observation


PLACEMENTS = {
    0xA0: [dict(id=90, x=31, y=0, sprite_id=255, state=2),
           dict(id=5, x=1, y=2, sprite_id=0x0A, state=0),
           dict(id=72, x=0, y=31, sprite_id=0x20, state=2),
           dict(id=3, x=31, y=31, sprite_id=1, state=0)],
    0xA1: [dict(id=10, x=16, y=8, sprite_id=0x42, state=1)],
    0xBF: [dict(id=11, x=0, y=0, sprite_id=0x3F, state=0),
           dict(id=12, x=31, y=31, sprite_id=0, state=2)],
}


class CurrentActorStreamsTest(unittest.TestCase):
    def setUp(self):
        prepare = transfer_fixtures.CurrentSaveTransferTest.prepare

        def prepare_authored(case, **kwargs):
            # Seed owned saved inputs before the existing immutable transfer is
            # created. The live Save receipt and observation bind these bytes.
            data = json.loads(case.terrain.read_bytes())
            for entry in data['maps']:
                entry['authoring']['sprites'] = copy.deepcopy(PLACEMENTS.get(entry['map_id'], []))
            data['maps'][0]['authoring']['doors'] = [dict(id=100, x=5, y=6, entrance_id=None)]
            data['maps'][0]['authoring']['exits'] = [dict(id=101, x=7, y=8, room_id=0x83, exit_row=None)]
            data['flight_points'] = [dict(id=102, map_id=0xA0, x=8, y=9,
                                          name='Host fixture', runtime_slot=None)]
            case.terrain.write_bytes(X.P.encoded(data))
            case.inputs['terrain'] = X.Q.bound(case.terrain)
            case.save['artifacts'] = case.artifacts(case.inputs)
            case.receipt.write_bytes(X.P.encoded(case.save))
            case.proof.clear()
            case.proof.update(observation(case.rom.read_bytes(), data)[1])
            case.proof['terrain_sha256'] = X.R.sha(case.terrain.read_bytes())
            return prepare(case, **kwargs)

        with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest, 'prepare', prepare_authored):
            self.fixture = contract_fixtures.CurrentSourceContractTest()
            self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.source, self.document = self.fixture.inputs()
        self.profile = self.fixture.profile()

    def plan(self, *, source=None, document=None, profile=None):
        return L.plan_current_actor_streams(self.source if source is None else source,
            self.document if document is None else document,
            current_source_profile=self.profile if profile is None else profile)

    def test_exact_a0_a1_bf_bytes_preserve_phases_and_authored_order_without_header(self):
        plan = self.plan()
        streams = {(row['map_id'], row['state']): row for row in plan['streams']}
        vectors = {(0xA0, 0): ('02010a1f1f01ff', [5, 3], [1, 3]),
                   (0xA0, 2): ('001fff1f0020ff', [90, 72], [0, 2]),
                   (0xA1, 1): ('081042ff', [10], [0]),
                   (0xBF, 0): ('00003fff', [11], [0]),
                   (0xBF, 2): ('1f1f00ff', [12], [1])}
        self.assertEqual([(row['map_id'], row['state']) for row in plan['streams']],
                         [(area, phase) for area in range(0xA0, 0xC0) for phase in range(3)])
        for key, (hex_bytes, placement_ids, ordinals) in vectors.items():
            row = streams[key]
            self.assertEqual((row['payload_hex'], row['placement_ids'], row['placement_ordinals']),
                             (hex_bytes, placement_ids, ordinals), key)
        self.assertEqual(len(plan['streams']), 96)
        self.assertEqual(sum(row['payload_hex'] == 'ff' for row in plan['streams']), 91)
        self.assertEqual(plan['demand'], dict(maps=32, phases=3, lists=96, placements=7,
            payload_bytes=117, pointer_rows=96, pointer_bytes=192))
        for row in plan['streams']:
            payload = bytes.fromhex(row['payload_hex'])
            self.assertEqual(row['sha256'], X.R.sha(payload))
            self.assertEqual(row['bytes'], len(payload))
            self.assertEqual(len(payload), len(row['placement_ids'])*3+1)
            self.assertEqual(payload[-1], 255)

    def test_source_profile_generation_and_blockers_remain_bound_without_storage(self):
        plan = self.plan()
        self.assertEqual(plan['source_rom_sha256'], X.R.sha(self.source))
        self.assertEqual(plan['source_size'], 0x200000)
        self.assertEqual(plan['source_profile_sha256'], X.T.digest(self.profile))
        self.assertEqual(plan['source_contract_binding'], self.profile['contract'])
        self.assertEqual(plan['document_sha256'], self.profile['document_sha256'])
        self.assertEqual(plan['generation'], self.profile['review']['generation'])
        self.assertEqual(plan['operation_id'], self.profile['review']['operation_id'])
        self.assertIsNone(plan['storage'])
        self.assertIsNone(plan['pointers'])
        self.assertEqual(plan['consumer_blockers'], X.A.consumer_blockers(
            self.document, tuple(range(0xA0, 0xC0)), ()))
        self.assertEqual({row.get('field') for row in plan['consumer_blockers']},
                         {'sprites', 'doors', 'exits', 'flight_points'})
        for flag in ('allocation_granted', 'producer_enforcement_verified', 'publication_authorized',
                     'ordinary_build_ready', 'runtime_admission', 'actors_compiled', 'rom_written'):
            self.assertIs(plan[flag], False, flag)
        json.dumps(plan)

    def test_invalid_model_fields_phase_count_and_order_shape_refuse_without_masking(self):
        for field, value in (('x', True), ('x', 32), ('y', -1), ('sprite_id', 256),
                             ('sprite_id', -1), ('state', 3), ('state', False), ('id', 0)):
            document = copy.deepcopy(self.document)
            document.authoring[0]['sprites'][0][field] = value
            with self.subTest(field=field, value=value), self.assertRaisesRegex(ValueError, 'CURRENT_ACTOR_MODEL_INVALID'):
                self.plan(document=document)
        for sprites in (tuple(PLACEMENTS[0xA0]),
                        [dict(id=i+1, x=0, y=0, sprite_id=0, state=0) for i in range(129)],
                        [dict(id=90, x=0, y=0, sprite_id=0, state=0)]*2):
            document = copy.deepcopy(self.document)
            document.authoring[0]['sprites'] = sprites
            with self.assertRaisesRegex(ValueError, 'CURRENT_ACTOR_MODEL_INVALID'):
                self.plan(document=document)

    def test_changed_source_document_order_and_profile_refuse(self):
        source = bytearray(self.source)
        source[0x11111] ^= 1
        document = copy.deepcopy(self.document)
        document.authoring[0]['sprites'].reverse()
        profile = copy.deepcopy(self.profile)
        profile['document_sha256'] = 'f'*64
        for args in (dict(source=bytes(source)), dict(document=document), dict(profile=profile),
                     dict(source=X.A.expanded_rom(self.source))):
            with self.subTest(fields=list(args)), self.assertRaisesRegex(ValueError, 'PROFILE_STALE'):
                self.plan(**args)

    def test_same_byte_new_save_and_changed_contract_retire_old_profile(self):
        self.fixture.value['origins']['code']['pc'][1] -= 1
        self.fixture.value['origins']['code']['snes'][1] -= 1
        self.fixture.write()
        with self.assertRaisesRegex(ValueError, 'PROFILE_STALE'):
            self.plan()
        self.fixture.value['origins']['code']['pc'][1] += 1
        self.fixture.value['origins']['code']['snes'][1] += 1
        self.fixture.write()
        before = self.fixture.case.rom.read_bytes()
        self.fixture.case.next_save()
        self.assertEqual(self.fixture.case.rom.read_bytes(), before)
        with self.assertRaisesRegex(ValueError, 'retired'):
            self.plan()

    def test_final_profile_recheck_refuses_generation_drift_before_return(self):
        blockers = L.A.consumer_blockers
        def later_save(*args, **kwargs):
            result = blockers(*args, **kwargs)
            self.fixture.case.next_save()
            return result
        with mock.patch.object(L.A, 'consumer_blockers', side_effect=later_save):
            with self.assertRaisesRegex(ValueError, 'retired'):
                self.plan()

    def test_no_file_writer_or_historical_authority_is_used(self):
        before = X.R.sha(self.fixture.case.rom.read_bytes())
        with (mock.patch.object(Path, 'write_bytes', side_effect=AssertionError('file writer')),
              mock.patch.object(Path, 'write_text', side_effect=AssertionError('file writer')),
              mock.patch.object(X.P, 'write_outputs', side_effect=AssertionError('output writer')),
              mock.patch.object(L.R, 'reservation_claim', side_effect=AssertionError('historical authority'))):
            plan = self.plan()
        self.assertEqual(plan['source_rom_sha256'], before)
        self.assertEqual(X.R.sha(self.fixture.case.rom.read_bytes()), before)
        self.assertFalse(self.fixture.case.candidate.exists())

    def test_profile_validation_still_surrounds_codec_and_rejects_census(self):
        codec = L._current_actor_codec
        verify = X.verify_current_native_source_profile
        with mock.patch.object(X, 'verify_current_native_source_profile', wraps=verify) as checked:
            def encode(*args, **kwargs):
                self.assertEqual(checked.call_count, 1)
                return codec(*args, **kwargs)
            with mock.patch.object(L, '_current_actor_codec', side_effect=encode):
                self.plan()
            self.assertEqual(checked.call_count, 2)
        with mock.patch.object(L, '_current_actor_codec', side_effect=AssertionError('codec before profile')):
            with self.assertRaisesRegex(ValueError, 'CURRENT_SOURCE_PROFILE_REQUIRED'):
                self.plan(profile={'kind': 'lyra.schema5_actor_codec_census.v1'})


class Schema5ActorCodecCensusTest(unittest.TestCase):
    def inputs(self):
        from test_lyra_project_terrain import fixture, profile
        data = fixture()
        data['schema_version'] = 5
        data['gameplay_areas'] = [
            dict(parent_map_id=area, size='large' if area == 0xB0 else 'small',
                 maps=[0xB0, 0xB1, 0xB8, 0xB9] if area == 0xB0 else [area])
            for area in range(0xA0, 0xC0) if area not in (0xB1, 0xB8, 0xB9)]
        placements = {0xB0: [(1, 23, 14), (2, 15, 21)], 0xB1: [(3, 8, 12)],
                      0xB8: [(4, 13, 11)], 0xB9: [(5, 5, 13)]}
        for area, entries in placements.items():
            data['maps'][area-0xA0]['authoring']['sprites'] = [
                dict(id=identity, x=x, y=y, sprite_id=0x52, state=1)
                for identity, x, y in entries]
        raw = json.dumps(data).encode()
        document = terrain.parse_terrain_document(raw, profile(), allow_authoring_drafts=True)
        return bytes(0x200000), document, raw

    def test_exact_large_area_codec_without_source_profile_or_runtime_assignment(self):
        source, document, raw = self.inputs()
        before = copy.deepcopy(document)
        with (mock.patch.object(X, 'verify_current_native_source_profile', side_effect=AssertionError('profile')),
              mock.patch.object(Path, 'write_bytes', side_effect=AssertionError('writer')),
              mock.patch.object(Path, 'write_text', side_effect=AssertionError('writer'))):
            result = L.census_schema5_actor_streams(source, document, terrain_raw=raw)
        streams = {(row['map_id'], row['state']): row for row in result['streams']}
        expected = '0e1752150f520c28522b0d522d2552ff'
        for area in (0xB0, 0xB1, 0xB8, 0xB9):
            row = streams[area, 1]
            self.assertEqual(row['payload_hex'], expected)
            self.assertEqual(row['placement_ids'], [1, 2, 3, 4, 5])
            self.assertEqual(row['placement_maps'], [0xB0, 0xB0, 0xB1, 0xB8, 0xB9])
            self.assertEqual(row['parent_map_id'], 0xB0)
            self.assertEqual(streams[area, 0]['payload_hex'], 'ff')
            self.assertEqual(streams[area, 2]['payload_hex'], 'ff')
        self.assertEqual(result['demand'], dict(maps=32, phases=3, lists=96, placements=5,
            payload_bytes=156, pointer_rows=96, pointer_bytes=192))
        self.assertEqual(sum(row['payload_hex'] == 'ff' for row in result['streams']), 92)
        for key in ('source_profile', 'source_epoch', 'storage', 'pointers'):
            self.assertIsNone(result[key])
        for key in ('saved_inputs_authenticated', 'source_epoch_qualified', 'selected',
                    'transfer_created', 'recipe_created', 'allocation_granted',
                    'producer_enforcement_verified', 'publication_authorized',
                    'ordinary_build_ready', 'runtime_admission', 'actors_compiled',
                    'resource_closure_verified', 'rom_written'):
            self.assertIs(result[key], False, key)
        self.assertEqual(document, before)
        self.assertEqual(result['terrain_sha256'], X.R.sha(raw))
        self.assertEqual(result['source_rom_sha256'], X.R.sha(source))
        digest = result.pop('census_sha256')
        self.assertEqual(digest, X.R.sha(json.dumps(result, sort_keys=True, separators=(',', ':')).encode()))

    def test_exact_document_and_schema_required_without_native_resource_upgrade(self):
        source, document, raw = self.inputs()
        changed = copy.deepcopy(document)
        changed.authoring[0]['properties']['music'][0] = 1
        with self.assertRaisesRegex(ValueError, 'DOCUMENT_MISMATCH'):
            L.census_schema5_actor_streams(source, changed, terrain_raw=raw)
        for version in (3, 6, 9, True):
            value = json.loads(raw)
            value['schema_version'] = version
            with self.subTest(version=version), self.assertRaisesRegex(ValueError, 'SCHEMA5_REQUIRED'):
                L.census_schema5_actor_streams(source, document, terrain_raw=json.dumps(value).encode())
        for changed in (replace(document, next_native_resource_id=2),
                        replace(document, boat_transport={}), replace(document, whirlpool_transport={})):
            with self.assertRaisesRegex(ValueError, 'SCHEMA5_REQUIRED'):
                L.census_schema5_actor_streams(source, changed, terrain_raw=raw)
        with self.assertRaisesRegex(ValueError, 'DOCUMENT_INVALID'):
            L.census_schema5_actor_streams(source, document, terrain_raw=b'\xff')

    def test_invalid_actor_and_incomplete_layout_refuse(self):
        source, document, raw = self.inputs()
        for field, value in (('state', True), ('state', 3), ('x', 32), ('id', 0)):
            changed = copy.deepcopy(document)
            changed.authoring[16]['sprites'][0][field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'CURRENT_ACTOR_MODEL_INVALID'):
                L.census_schema5_actor_streams(source, changed, terrain_raw=raw)
        changed = copy.deepcopy(document)
        changed.authoring[16]['sprites'][1]['id'] = 1
        with self.assertRaisesRegex(ValueError, 'CURRENT_ACTOR_MODEL_INVALID'):
            L.census_schema5_actor_streams(source, changed, terrain_raw=raw)
        value = json.loads(raw)
        value['gameplay_areas'] = value['gameplay_areas'][1:]
        changed_raw = json.dumps(value).encode()
        changed = terrain.parse_terrain_document(changed_raw, document.profile, allow_authoring_drafts=True)
        with self.assertRaisesRegex(ValueError, 'AREAS_INCOMPLETE'):
            L.census_schema5_actor_streams(source, changed, terrain_raw=changed_raw)


if __name__ == '__main__':
    unittest.main()
