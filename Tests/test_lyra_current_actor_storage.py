"""Real bound host actor storage/composition, without grants or CPU execution."""
import copy
import json
import unittest

import test_lyra_current_actor_streams as actor_fixtures
from test_lyra_current_composer_binding import ComposerFixture
import lyra_current_transfer as X
import lyra_native_loaders as L


def bind_origin(fixture, capacity=0x1000, pc=0x30B000):
    fixture.value['origins']['actors'] = dict(pc=[pc,pc+capacity],
        snes=[X.A.snes(pc),X.A.snes(pc+capacity-1)+1],
        source_binding=fixture.value['origins']['code']['source_binding'])
    fixture.write()
    return fixture.profile()


def storage(source, document, profile, **kwargs):
    origin = profile['origins']['actors']
    lo,hi = origin['pc']
    arguments = dict(current_source_profile=profile, data_snes=origin['snes'][0],
                     capacity=hi-lo, preimage=X.A.expanded_rom(source)[lo:hi])
    arguments.update(kwargs)
    return L.plan_current_actor_storage(source,document,**arguments)


class CurrentActorStorageTest(unittest.TestCase):
    def setUp(self):
        self.f = actor_fixtures.CurrentActorStreamsTest()
        self.f.setUp()
        self.addCleanup(self.f.doCleanups)
        self.profile = bind_origin(self.f.fixture)

    def plan(self, **kwargs):
        return storage(self.f.source,self.f.document,self.profile,**kwargs)

    def test_actual_phase_bytes_deduplicate_in_one_explicit_bank_and_pointer_rows_read_back(self):
        plan = self.plan()
        payload = bytes.fromhex(plan['payload_hex'])
        self.assertEqual((plan['unique_lists'],len(payload)),(6,27))
        streams = {(r['map_id'],r['state']):r for r in plan['actor_stream_plan']['streams']}
        self.assertEqual(len(plan['pointers']),96)
        for row in plan['pointers']:
            stream = streams[row['map_id'],row['state']]
            raw = payload[row['offset']:row['offset']+stream['bytes']]
            self.assertEqual(raw.hex(),stream['payload_hex'])
            self.assertEqual(row['snes'] >> 16,plan['bank'])
            self.assertEqual(row['pointer_word'],row['snes'] & 65535)
            self.assertEqual(plan['phase_rows'][row['map_id']][f"sprite_phase{row['state']}"],row['pointer_word'])
        self.assertEqual([r['offset'] for r in plan['pointers'][:3]],[0,7,8])
        self.assertIn('Lyra_CurrentActorData:',L.emit_current_actor_data(plan))
        for flag in ('allocation_granted','producer_enforcement_verified','publication_authorized',
                     'runtime_admission','ordinary_build_ready','actors_compiled','rom_written'):
            self.assertIs(plan[flag],False)

    def test_unbound_shifted_or_incomplete_preimages_refuse_without_storage_fallback(self):
        self.assertNotIn('actors',self.f.profile['origins'])
        with self.assertRaisesRegex(ValueError,'PROFILE_STALE'):
            L.plan_current_actor_storage(self.f.source,self.f.document,current_source_profile=self.f.profile,
                                         data_snes=0,capacity=1,preimage=b'')
        actor_origin = self.f.fixture.value['origins'].pop('actors')
        self.f.fixture.write()
        unbound_profile = self.f.fixture.profile()
        with self.assertRaisesRegex(ValueError,'ACTOR_STORAGE_UNBOUND'):
            L.plan_current_actor_storage(self.f.source,self.f.document,current_source_profile=unbound_profile,
                                         data_snes=0,capacity=1,preimage=b'')
        self.f.fixture.value['origins']['actors'] = actor_origin
        self.f.fixture.write()
        self.profile = self.f.fixture.profile()
        for kwargs in (dict(data_snes=self.profile['origins']['actors']['snes'][0]+1),
                       dict(capacity=32),dict(preimage=b''),dict(preimage=bytes(0x1000))):
            with self.subTest(kwargs=list(kwargs)),self.assertRaisesRegex(ValueError,'ACTOR_STORAGE_(ORIGIN|PREIMAGE)_MISMATCH'):
                self.plan(**kwargs)

    def test_capacity_and_bank_crossing_refuse_under_fresh_real_source_profiles(self):
        self.profile = bind_origin(self.f.fixture,16)
        with self.assertRaisesRegex(ValueError,'ACTOR_STORAGE_CAPACITY'):
            self.plan()
        self.profile = bind_origin(self.f.fixture,0x200,0x30FF00)
        with self.assertRaisesRegex(ValueError,'ACTOR_STORAGE_ORIGIN_MISMATCH'):
            self.plan()

    def test_generation_drift_and_contract_changes_retire_storage_plan(self):
        original = self.plan()
        self.f.fixture.case.next_save()
        with self.assertRaisesRegex(ValueError,'retired'):
            self.plan()
        self.assertFalse(original['runtime_admission'])


class CurrentActorStorageComposerTest(unittest.TestCase):
    def setUp(self):
        self.f = ComposerFixture(self)
        self.f.profile = bind_origin(self.f.contract_fixture)
        self.plan = storage(self.f.source,self.f.document,self.f.profile)
        for area,values in self.plan['phase_rows'].items():
            self.f.rows[area].update(values)
        self.f.table_plan = self.f.tables()

    def test_matching_storage_emits_data_and_explicit_bank_but_never_enables_runtime(self):
        files = self.f.compose(actor_storage_plan=self.plan)
        self.assertIn(b'Lyra_CurrentActorData:',files['runtime_data.asm'])
        self.assertIn(b'!LYRA_CURRENT_ACTOR_BANK = $E1',files['runtime_constants.asm'])
        self.assertIn(b'!LYRA_CURRENT_ACTORS_ENABLED = 0',files['runtime_constants.asm'])
        prepared = json.loads(files['prepare.json'])
        # JSON object keys are strings after serialization.
        self.assertEqual(prepared['actor_storage_plan']['payload_sha256'],self.plan['payload_sha256'])
        self.assertFalse(prepared['selected'])
        self.assertFalse(prepared['runtime_admission'])

    def test_payload_and_internally_valid_pointer_substitution_are_refused(self):
        wrong = copy.deepcopy(self.plan)
        wrong['payload_hex'] = '00ff'
        wrong['payload_sha256'] = X.R.sha(bytes.fromhex(wrong['payload_hex']))
        with self.assertRaisesRegex(ValueError,'COMPOSER_ACTORS_MISMATCH'):
            self.f.compose(actor_storage_plan=wrong)
        self.f.rows[0xA0]['sprite_phase0'] += 1
        with self.assertRaisesRegex(ValueError,'COMPOSER_ACTOR_POINTERS_MISMATCH'):
            self.f.compose(table_plan=self.f.tables(),actor_storage_plan=self.plan)


if __name__ == '__main__':
    unittest.main()
