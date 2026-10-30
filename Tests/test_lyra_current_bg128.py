"""Saved BG128 current bindings and restoration controls; no native execution."""
import copy
from dataclasses import replace
import json
from pathlib import Path
import struct
import unittest
from unittest import mock

from test_lyra_current_build import CurrentBuildTest
from test_lyra_current_composer_binding import ComposerFixture
import test_lyra_current_transfer as transfer_fixtures
from test_lyra_project_admission import observation
from test_lyra_current_actor_storage import bind_origin, storage
from test_project_bg_palette_restore import Protocol
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_project_bg_palette as B

SNAPSHOT=Path(__file__).parent/'fixtures/lyra_saved_authoring_20261027.json'


def saved_authoring():
    return json.loads(SNAPSHOT.read_bytes())


def assemble_data(prepared, base):
    rom=bytearray(base)
    for row in [*prepared['terrain_plan']['writes'],*prepared['tables']['tables']]:
        rom[slice(*row['pc'])]=bytes.fromhex(row['payload_hex'])
    rom[slice(*prepared['tables']['descriptor_pc'])]=bytes.fromhex(prepared['tables']['descriptor_hex'])
    actor=prepared['actor_storage_plan'];at=X.A.pc(actor['data_snes'])
    rom[at:at+actor['payload_bytes']]=bytes.fromhex(actor['payload_hex'])
    if bg:=prepared.get('bg128_plan'):
        at=X.A.pc(bg['data_snes']);raw=bytes.fromhex(bg['payload_hex']);rom[at:at+len(raw)]=raw
    return bytes(rom)


class CurrentBG128BuildTest(unittest.TestCase):
    # Reuse one real maintained host Save/profile/composer fixture, not its test
    # methods. Registry/producer are explicitly synthetic and private.
    BG128=True
    setUpClass=classmethod(CurrentBuildTest.setUpClass.__func__)

    def test_all_eight_actual_saved_palettes_lower_without_native_or_obj_rows(self):
        bg=self.prepared['bg128_plan'];raw=bytes.fromhex(bg['payload_hex'])
        expected={r['map_id']:r['authoring']['properties']['background_palette'] for r in saved_authoring()['maps']
                  if 'background_palette' in r['authoring']['properties']}
        self.assertEqual([r['map_id'] for r in bg['records']],list(expected))
        directory=struct.unpack('<192H',raw[:384]);self.assertEqual(directory[:160],(0,)*160)
        for area,words in expected.items():
            self.assertEqual(list(struct.unpack_from('<128H',raw,directory[area])),words)
        constants=self.files['runtime_constants.asm']
        for line in (b'!PROJECT_BG128_ENABLED = 1',b'!PROJECT_BG128_RESTORE_BOUND = 1',
                     b'!PROJECT_BG128_CODE_BASE = $E0D000',b'!LYRA_CURRENT_CODE_END = $E0D000'):
            self.assertIn(line,constants)
        self.assertIn(b'Oracle_ProjectBGPalette_Data:',self.files['runtime_data.asm'])
        self.assertFalse(bg['publication_authorized'])

    def test_missing_restore_binding_wrong_code_and_underlay_owner_refuse(self):
        p=self.prepared;profile=p['current_source_profile'];ledger=json.loads(self.ledger.read_bytes())
        for binding in (None,dict(restore_bound=False,code_snes=[0xE0D000,0xE0D800]),
                        dict(restore_bound=True,code_snes=[0xE0BFFF,0xE0C000]),
                        dict(restore_bound=True,code_snes=[0xE0D000,0xE0E000])):
            with self.subTest(binding=binding),self.assertRaises(ValueError):
                X.current_bg128(self.f.source,self.f.document,profile,ledger,binding)
        for change in ('missing','predicate','overlap'):
            bad=copy.deepcopy(ledger)
            if change=='missing':bad['claims']=[r for r in bad['claims'] if r['id']!='ProjectBGPaletteNativeUnderlay']
            elif change=='predicate':next(r for r in bad['claims'] if r['id']=='ProjectBGPaletteNativeUnderlay')['condition']={}
            else:bad['claims'].append(dict(id='foreign',space='wram',base=0x7ECB00,size=1))
            with self.subTest(change=change),self.assertRaisesRegex(ValueError,'BG128_WRAM'):
                X.current_bg128(self.f.source,self.f.document,profile,bad,p['bg128_binding'])

    def test_derived_palette_data_restore_code_tint_and_native_hooks_are_verified(self):
        rom=assemble_data(self.prepared,self.compiled)
        result=X.verify_current_output(self.prepared,rom,self.symbols)
        self.assertTrue(result['bg128_data_verified']);self.assertEqual(result['bg128_code_bytes'],1024)
        for at in (X.A.pc(0xE0D000),X.A.pc(0xE7B100),X.A.pc(0x02C55E),X.A.pc(0x008827)):
            bad=bytearray(rom);bad[at]^=1
            with self.subTest(at=at),self.assertRaises(ValueError):
                X.verify_current_output(self.prepared,bytes(bad),self.symbols)
        at=X.A.pc(self.prepared['bg128_plan']['data_snes'])+384
        bad=bytearray(rom);bad[at]^=1
        with self.assertRaisesRegex(ValueError,'PAYLOAD_MISMATCH'):
            X.verify_current_output(self.prepared,bytes(bad),self.symbols)

    def test_enter_leave_native_warm_continue_and_minish_use_distinct_native_backing(self):
        palettes=[r['authoring']['properties']['background_palette'] for r in saved_authoring()['maps']
                  if 'background_palette' in r['authoring']['properties']]
        p=Protocol();native=(p.reference[:],p.effective[:]);obj=p.obj[:]
        # Non-idempotent +1 tint catches repeated application, while separate
        # reference/effective data catches accidentally aliased underlay buffers.
        for area,words in zip((0xA6,0xA7,0xAE,0xAF,0xB0,0xB8,0xBE,0xBF),palettes):
            p.begin(area);p.complete(area,words,both=True)
            self.assertEqual(p.reference,[v+1 for v in words])
            p.begin(0x3A);p.complete(0x3A,None,both=True)
            self.assertEqual((p.reference,p.effective),native)
        # Warm save-load restores before native partial writers, including holes.
        p.begin(0xA6);p.complete(0xA6,palettes[0],both=True);p.depart()
        p.reference[49]=777;p.begin(0xA6);p.complete(0xA6,palettes[0],both=False)
        self.assertEqual(p.backing[0][48],native[0][48]);self.assertEqual(p.backing[0][49],777)
        # Minish/native cache restoration is a native producer transaction, not
        # a recapture of tinted project colors; source order is checked below.
        p.depart();cache=(p.reference[:],p.effective[:]);p.begin(0xA6)
        p.reference[:],p.effective[:]=map(list,cache)
        p.complete(0xA6,palettes[0],both=True);self.assertEqual(p.backing,cache)
        self.assertEqual(p.obj,obj)


class ActualAuthoringBGSourceTest(unittest.TestCase):
    def test_source_composer_preserves_all_properties_five_sprites_and_b0_unassigned_return(self):
        saved=saved_authoring();prepare=transfer_fixtures.CurrentSaveTransferTest.prepare
        def seed(case,**kwargs):
            data=json.loads(case.terrain.read_bytes())
            for row,original in zip(data['maps'],saved['maps']):row['authoring']=copy.deepcopy(original['authoring'])
            case.terrain.write_bytes(X.P.encoded(data));case.inputs['terrain']=X.Q.bound(case.terrain)
            case.save['artifacts']=case.artifacts(case.inputs);case.receipt.write_bytes(X.P.encoded(case.save))
            case.proof.clear();case.proof.update(observation(case.rom.read_bytes(),data)[1])
            case.proof['terrain_sha256']=X.R.sha(case.terrain.read_bytes())
            return prepare(case,**kwargs)
        # This explicit all-small geometry belongs only to the disposable test;
        # it is not inferred from or written into the real schema4 document.
        areas=[dict(parent_map_id=a,size='small',maps=[a]) for a in range(0xA0,0xC0)]
        with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest,'prepare',seed):
            f=ComposerFixture(self,gameplay_areas=areas)
        f.profile=bind_origin(f.contract_fixture);actor=storage(f.source,f.document,f.profile)
        for area,row in X.A.gameplay_transition_rows(f.source,f.document).items():f.rows[area].update(row)
        for area,row in actor['phase_rows'].items():f.rows[area].update(row)
        f.table_plan=f.tables();origin=f.profile['origins']['bg_palette'];lo,hi=origin['pc']
        from types import SimpleNamespace
        bg=B.plan_bg128([SimpleNamespace(map_id=0xA0+i,properties=p) for i,p in enumerate(f.document.properties)],
            data_snes=origin['snes'][0],capacity=hi-lo,preimage=X.A.expanded_rom(f.source)[lo:hi])
        files=f.compose(bg128_plan=bg,actor_storage_plan=actor);report=json.loads(files['prepare.json'])
        self.assertEqual(list(f.document.authoring),[row['authoring'] for row in saved['maps']])
        self.assertEqual(actor['actor_stream_plan']['demand']['placements'],5)
        self.assertEqual([r['map_id'] for r in bg['records']],[0xA6,0xA7,0xAE,0xAF,0xB0,0xB8,0xBE,0xBF])
        state=report['native_state_contract'];self.assertEqual(state['requested_doors'][0]['entrance_id'],0x0B)
        self.assertEqual(state['requested_returns'][0]['room_id'],0x83)
        self.assertIsNone(state['requested_returns'][0]['requested_exit_row'])
        self.assertFalse(report['selected']);self.assertFalse(report['runtime_admission'])
        self.assertIn(b'Oracle_ProjectBGPalette_Data:',files['runtime_data.asm'])
