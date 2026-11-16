"""Private host policy fixtures; no repository grant, selected ROM or CPU run."""
import copy
import json
from pathlib import Path
import unittest
from unittest import mock

from test_lyra_current_composer_binding import ComposerFixture
from test_lyra_current_actor_storage import bind_origin
import lyra_current_transfer as X
import lyra_native_loaders as L
import lyra_native_state as S


class SelectedPaletteDependencyTests(unittest.TestCase):
    def test_unselected_palette_cannot_block_a_bound_private_pair(self):
        from test_lyra_project_admission import document
        from lyra_project_terrain import parse_terrain_document
        raw=document();raw['schema_version']=4
        raw['maps'][6]['authoring']['properties']['background_palette']=[0]*128
        raw['maps'][6]['authoring']['asset_bindings']=['1'*64]*3
        parsed=parse_terrain_document(X.P.encoded(raw),raw['profile'],allow_authoring_drafts=True,
            expected_asset_bindings={r['map_id']:r['authoring']['asset_bindings'] for r in raw['maps']})
        pilot=X.native_checkpoint_boundaries(parsed)
        self.assertEqual(X.current_bg128(b'',parsed,None,{},None,private_pilot=pilot),(None,None))
        self.assertIn('background_palette',parsed.properties[6])
        with self.assertRaisesRegex(ValueError,'BG128_UNADMITTED'):
            X.current_bg128(b'',parsed,None,{},None)
        raw['maps'][0]['authoring']['properties']['background_palette']=[0]*128
        raw['maps'][0]['authoring']['asset_bindings']=['1'*64]*3
        selected=parse_terrain_document(X.P.encoded(raw),raw['profile'],allow_authoring_drafts=True,
            expected_asset_bindings={r['map_id']:r['authoring']['asset_bindings'] for r in raw['maps']})
        with self.assertRaisesRegex(ValueError,'BG128_UNADMITTED'):
            X.current_bg128(b'',selected,None,{},None,private_pilot=X.native_checkpoint_boundaries(selected))
        malformed=copy.deepcopy(pilot);malformed['allowed_tail_maps']=[]
        with self.assertRaises(ValueError):
            X.current_bg128(b'',parsed,None,{},None,private_pilot=malformed)


class EventStorageOwnerTests(unittest.TestCase):
    def proposed_ledger(self):
        ledger = json.loads((X.P.ROOT/'Config/allocation_ownership.json').read_text())
        value = dict(flags=0x7EF4C0,version=0x7EF4E0,marker=0xA1)
        for claim in ledger['claims']:
            if claim['id'] in ('LyraCurrentTailFlags','LyraCurrentTailVersion'):
                claim.update(status='shared',base=value[
                    'flags' if claim['id']=='LyraCurrentTailFlags' else 'version'])
        return value,ledger

    def test_real_ledger_unbounded_later_text_buffer_cannot_overlap(self):
        value,ledger = self.proposed_ledger()
        text = next(c for c in ledger['claims'] if c['id']=='text_decomp_reference')
        self.assertEqual((text['base'],text['size']),(0x7F5B00,None))
        self.assertEqual(X.current_event_state(value,ledger),value)

    def test_unknown_earlier_extent_and_known_overlap_still_refuse(self):
        value,ledger = self.proposed_ledger()
        for base,size,message in ((0x7EF4BF,None,'ambiguous owner extent'),
                                  (0x7EF4DF,2,'text_decomp_reference')):
            with self.subTest(base=base,size=size):
                bad = copy.deepcopy(ledger)
                text = next(c for c in bad['claims'] if c['id']=='text_decomp_reference')
                text.update(base=base,size=size)
                with self.assertRaisesRegex(ValueError,message):
                    X.current_event_state(value,bad)


def consumer_fixture(source, code, *, bg_code=None, legacy_empty=False):
    rom=bytearray(X.A.expanded_rom(source)); labels={}; serial=0
    def put(at,raw):rom[X.A.pc(at):X.A.pc(at)+len(raw)]=raw
    targets={t for _,t in L.SOURCE_CALLS}|{'Lyra_LoadCurrentSprites','Lyra_FullHigh','Lyra_FullLow',
        'Lyra_SubHigh','Lyra_SubLow','Lyra_TailEvent_Load','Lyra_TailEvent_Store','Lyra_TailEvent_MigrateSave'}
    for i,name in enumerate(sorted(targets)):labels[name]=code+i*16
    labels.update(Lyra_CurrentNativeCodeStart=code,Lyra_CurrentNativeCodeEnd=code+0x800)
    put(code,b'\xea'*0x800)
    for i,host in enumerate(L.SOURCE_HOSTS):
        at=0xE68000+i*0x100;name='LyraHost_'+host
        labels[name]=at;labels[name+'_End']=at+0xF0;put(at,b'\xea'*0xF0)
    for i,(name,target) in enumerate([r for r in L.SOURCE_CALLS if r[0]!='LyraCall_SpritePointer']+
                                    [('LyraCall_CurrentActors','Lyra_LoadCurrentSprites')]):
        at=0xE6D000+i*8;labels[name]=at
        put(at,bytes([0x5C if name=='LyraCall_CurrentActors' else 0x22])+labels[target].to_bytes(3,'little'))
    for row in L.current_table_layout(0xE08000):
        labels['Lyra_CurrentTable_'+row['name']] = row['snes']
    for i, axis in enumerate(('Y', 'X')):
        at = labels['LyraHost_OverworldHandleTransitions']+0x80+i*4
        labels['LyraCall_TransitionDelta'+axis] = at
        target = labels['Lyra_CurrentTable_transition_'+axis.lower()]
        put(at,b'\xFF'+target.to_bytes(3,'little'))
    host='LyraHost_Hookshot_IsCollisionCheckFutile_Interupt'
    labels[host]=0x08FA49;labels[host+'_End']=0x08FA81
    put(0x08FA49,b'\xea'*(0x08FA81-0x08FA49))
    for i,(axis,site) in enumerate((('Y',0x08FA57),('X',0x08FA6D))):
        target='Lyra_HookshotSubtract'+axis;start=code+0x700+i*0x40
        labels[target]=start;labels[target+'_End']=start+49
        labels['LyraCall_HookshotDelta'+axis]=site
        put(site,b'\x22'+start.to_bytes(3,'little'))
    for i,(name,size,_,_) in enumerate(S.TAIL_SOURCE_CALLERS):
        at=0xE6F000+i*0x100;labels[name]=at;put(at,b'\xea'*size)
    labels.update(SharedGraphicsRuntimeStart=0xE18000,SharedGraphicsRuntimeEnd=0xE18100)
    put(0xE18000,b'\xea'*256)
    labels['ShakeScreen']=0xE7B000;put(0xE7B000,bytes.fromhex(S.TAIL_M8_DEPENDENCY[2]))
    labels['LoadCheckpointOrWorld']=0xE7A000;labels['LyraHost_LoadCheckpointOrWorld_End']=0xE7A040
    put(0xE7A000,b'\xea'*64)
    def hook(at,target,opcode=0x22,pad=0):put(at,bytes([opcode])+labels[target].to_bytes(3,'little')+b'\xea'*pad)
    for a,t in ((0x02F59D,'Lyra_FullHigh'),(0x02F5C8,'Lyra_FullLow'),(0x02F7E3,'Lyra_SubHigh'),(0x02F80E,'Lyra_SubLow')):hook(a,t,pad=8)
    for a in S.TAIL_LOAD_SITES:hook(a,'Lyra_TailEvent_Load')
    for a,_ in S.TAIL_STORE_SITES:hook(a,'Lyra_TailEvent_Store')
    if legacy_empty:
        name='Lyra_TailEvent_LoadLegacyEmptyBomb';at=code+0x780
        body=bytes.fromhex('08c210e0a000900de0c000b00828bf20f47e29fd6b28bf80f27e6b')
        labels[name]=at;labels[name+'_End']=at+len(body);put(at,body)
        put(0x02EF40,bytes.fromhex('e230'));put(0x02EF54,bytes.fromhex('a68a'))
        hook(0x02EF56,name)
        put(0x02EF5A,bytes.fromhex('2902f01bc230a58a0aaa')+b'\x22'
            +labels['Lyra_ReadBombDoor'].to_bytes(3,'little')
            +bytes.fromhex('aaa9b40d9f00207ea9b50d9f02207ee23060'))
        put(0x1BC8BE,bytes.fromhex('a99b008502'))
        put(X.A.EMPTY_HIDDEN_ITEMS,b'\xff\xff')
        put(labels['Lyra_CurrentTable_hidden_items']+0xA0*2,b'\xc2\xc5'*32)
        put(labels['Lyra_CurrentTable_bomb_doors']+0xA0*2,bytes(64))
    hook(0x028192,'LoadCheckpointOrWorld',0x5C)
    if bg_code is not None:
        bg_names=('Startup','IntroReset','IndoorDeparture','NativeAllBegin','WhirlpoolBegin','WhirlpoolComplete',
                  'NativeMainBegin','NativeAuxBegin','NativeHudComplete','RestoreAndInvalidate','ResolveColor')
        labels.update({f'ProjectBGPalette_{name}':bg_code+i*16 for i,name in enumerate(bg_names)})
        labels.update(ProjectBGPalette_CodeStart=bg_code,ProjectBGPalette_CodeEnd=bg_code+0x400,
                      LyraHost_LoadDayNightPaletteEffect=0xE7B100,LyraHost_LoadDayNightPaletteEffect_End=0xE7B140)
        put(bg_code,b'\xea'*0x400);put(0xE7B100,b'\xea'*64)
        for a,t,op,pad in ((0x008827,'Startup',0x22,0),(0x0CC1A0,'IntroReset',0x5C,0),
                (0x02C55E,'IndoorDeparture',0x5C,0),(0x02C5B2,'NativeAllBegin',0x5C,0),
                (0x02B4AE,'WhirlpoolBegin',0x5C,3),(0x02B4D9,'WhirlpoolComplete',0x22,0),
                (0x1BEEC7,'NativeMainBegin',0x5C,2),(0x0ED5A8,'NativeAuxBegin',0x5C,2),
                (0x02C617,'NativeHudComplete',0x22,0)):
            hook(a,'ProjectBGPalette_'+t,op,pad)
        hook(labels['LoadCheckpointOrWorld'],'ProjectBGPalette_RestoreAndInvalidate')
        hook(labels['LoadCheckpointOrWorld']+4,'Lyra_TailEvent_MigrateSave')
        hook(labels['LyraHost_LoadDayNightPaletteEffect'],'ProjectBGPalette_ResolveColor')
    else:
        hook(labels['LoadCheckpointOrWorld'],'Lyra_TailEvent_MigrateSave')
    put(0x1BC906,bytes.fromhex('290200'))
    symbols=('[labels]\n'+'\n'.join(f'{a>>16:02X}:{a&65535:04X} {n}' for n,a in labels.items())+'\n').encode()
    return bytes(rom),symbols


class CoordinateOperandTests(unittest.TestCase):
    def test_actual_subtractions_require_current_tables_and_indexed_opcode(self):
        image, symbols = consumer_fixture(bytes(0x400000), 0xE0C000)
        observed = L.inspect_current_consumers(image, symbols)
        calls = {r['label']: r for r in observed['source_calls']}
        for axis, legacy, current in (('Y', 0x288F38, 0xE09200),
                                      ('X', 0x289078, 0xE09380)):
            row = calls['LyraCall_TransitionDelta'+axis]
            self.assertEqual(row['payload_hex'], (b'\xFF'+current.to_bytes(3, 'little')).hex())
            for payload in (b'\xFF'+legacy.to_bytes(3, 'little'),
                            b'\xEF'+current.to_bytes(3, 'little')):
                with self.subTest(axis=axis, payload=payload.hex()):
                    control = bytearray(image)
                    at = X.A.pc(row['snes'])
                    control[at:at+4] = payload
                    with self.assertRaisesRegex(ValueError, 'transition subtraction target differs'):
                        L.inspect_current_consumers(bytes(control), symbols)

    def test_missing_or_rebound_coordinate_symbol_refuses(self):
        image, symbols = consumer_fixture(bytes(0x400000), 0xE0C000)
        rows = symbols.decode().splitlines()
        missing = ('\n'.join(r for r in rows if not r.endswith('LyraCall_TransitionDeltaX'))+'\n').encode()
        with self.assertRaisesRegex(ValueError, 'Missing current consumer symbol'):
            L.inspect_current_consumers(image, missing)
        rebound = ('\n'.join('28:9078 Lyra_CurrentTable_transition_x'
                             if r.endswith('Lyra_CurrentTable_transition_x') else r for r in rows)+'\n').encode()
        with self.assertRaisesRegex(ValueError, 'coordinate table layout differs'):
            L.inspect_current_consumers(image, rebound)


class HookshotOperandTests(unittest.TestCase):
    def test_calls_require_helpers_instead_of_native_or_current_table_operands(self):
        image,symbols=consumer_fixture(bytes(0x400000),0xE0C000)
        observed=L.inspect_current_consumers(image,symbols)
        calls={r['label']:r for r in observed['source_calls']}
        regions={r['label']:r for r in observed['regions']}
        for axis,site,legacy,current in (('Y',0x08FA57,0x288F38,0xE09200),
                                         ('X',0x08FA6D,0x289078,0xE09380)):
            row=calls['LyraCall_HookshotDelta'+axis]
            self.assertEqual(row['snes'],site)
            self.assertEqual(len(bytes.fromhex(regions[row['target']]['payload_hex'])),49)
            for payload in (b'\xFF'+legacy.to_bytes(3,'little'),
                            b'\xFF'+current.to_bytes(3,'little'),
                            b'\x22'+current.to_bytes(3,'little')):
                with self.subTest(axis=axis,payload=payload.hex()):
                    control=bytearray(image);at=X.A.pc(site);control[at:at+4]=payload
                    with self.assertRaisesRegex(ValueError,'hookshot subtraction target differs'):
                        L.inspect_current_consumers(bytes(control),symbols)

    def test_missing_shifted_and_unowned_helper_symbols_refuse(self):
        image,symbols=consumer_fixture(bytes(0x400000),0xE0C000)
        rows=symbols.decode().splitlines()
        controls=(('LyraCall_HookshotDeltaX',None,'Missing current consumer symbol'),
                  ('LyraCall_HookshotDeltaX',0x08FA6E,'hookshot subtraction target differs'),
                  ('LyraHost_Hookshot_IsCollisionCheckFutile_Interupt_End',0x08FA80,
                   'hookshot host extent differs'),
                  ('Lyra_HookshotSubtractY',0xE0BFFF,'hookshot helper span differs'),
                  ('Lyra_HookshotSubtractX_End',0xE0C801,'hookshot helper span differs'),
                  ('Lyra_HookshotSubtractY_End',0xE0C741,'hookshot helper span differs'))
        for name,value,error in controls:
            with self.subTest(symbol=name,value=value):
                changed=[(f'{value>>16:02X}:{value&65535:04X} {name}' if value is not None else '')
                         if r.endswith(' '+name) else r for r in rows]
                with self.assertRaisesRegex(ValueError,error):
                    L.inspect_current_consumers(image,('\n'.join(changed)+'\n').encode())


class LegacyEmptyCompiledTests(unittest.TestCase):
    def test_exact_guard_and_native_bank_are_required(self):
        image,symbols=consumer_fixture(bytes(0x400000),0xE0C000,legacy_empty=True)
        result=L.inspect_current_consumers(image,symbols,require_legacy_empty=True)
        self.assertEqual(result['legacy_empty_bomb_guard']['event_base'],0x7EF4C0)
        controls=((0xE0C780+18,'GUARD_BODY'),(0x02EF56,'GUARD_HOOK'),
            (0x02EF40,'RESTORE_CALLER'),(0x02EF54,'RESTORE_CALLER'),
            (0x02EF5A,'RESTORE_CALLER'),(0x1BC8BE+1,'NATIVE_LIST_BANK'),
            (X.A.EMPTY_HIDDEN_ITEMS,'NATIVE_LIST_BANK'))
        labels=L._labels(symbols)
        controls+=tuple((labels['Lyra_CurrentTable_'+family]+0x140,'TABLE_CHANGED')
                        for family in ('hidden_items','bomb_doors'))
        for site,error in controls:
            with self.subTest(site=hex(site)):
                bad=bytearray(image);bad[X.A.pc(site)]^=1
                with self.assertRaisesRegex(ValueError,error):
                    L.inspect_current_consumers(bytes(bad),symbols,require_legacy_empty=True)
        old,oldsymbols=consumer_fixture(bytes(0x400000),0xE0C000)
        self.assertNotIn('legacy_empty_bomb_guard',L.inspect_current_consumers(old,oldsymbols))
        with self.assertRaisesRegex(ValueError,'GUARD_REQUIRED'):
            L.inspect_current_consumers(old,oldsymbols,require_legacy_empty=True)


class LegacyEmptyPlanTests(unittest.TestCase):
    def setUp(self):
        import test_lyra_current_transfer as fixtures
        self.case=fixtures.CurrentSaveTransferTest();self.case.setUp()
        self.addCleanup(self.case.doCleanups)

    def prepare(self,version=5,*,bad_bank=False,bad_terminator=False):
        from test_lyra_project_admission import observation
        case=self.case;raw=json.loads(case.terrain.read_bytes())
        raw.update(schema_version=version,gameplay_areas=[dict(parent_map_id=a,size='small',maps=[a])
                                                       for a in range(0xA0,0xC0)])
        auth=raw['maps'][16]['authoring']
        auth['sprites']=[dict(id=20481,sprite_id=0x52,state=1,x=23,y=14)]
        auth['doors']=[dict(id=24577,entrance_id=0x0B,x=21,y=9)]
        auth['exits']=[dict(id=24578,room_id=0x83,exit_row=None,x=22,y=11)]
        auth['properties']['background_palette']=list(range(128))
        auth['asset_bindings']=['a'*64]*3
        if version>=9:
            from lyra_project_terrain import RUNTIME_PROPERTY_DEFAULTS
            raw.update(next_flight_point_id=1,boat_transport=None,whirlpool_transport=None,
                       next_native_resource_id=1)
            for row in raw['maps']:
                row['authoring']['native_resources']=None
                row['authoring']['properties'].update(copy.deepcopy(RUNTIME_PROPERTY_DEFAULTS))
        source=bytearray(case.rom.read_bytes());at=X.A.pc(0x1BC8BE)
        source[at:at+5]=bytes.fromhex('a9e3008502' if bad_bank else 'a99b008502')
        if bad_terminator:source[X.A.pc(X.A.EMPTY_HIDDEN_ITEMS)]=0
        case.rom.write_bytes(source);case.terrain.write_bytes(X.P.encoded(raw))
        case.inputs.update(rom=X.Q.bound(case.rom),terrain=X.Q.bound(case.terrain))
        case.save['artifacts']=case.artifacts(case.inputs);case.receipt.write_bytes(X.P.encoded(case.save))
        case.proof.clear();case.proof.update(observation(bytes(source),raw)[1])
        case.proof['terrain_sha256']=X.R.sha(case.terrain.read_bytes())
        return case.prepare()[1]

    def test_receipt_bound_derivation_preserves_every_authored_byte(self):
        request=self.prepare();case=self.case
        before={p:p.read_bytes() for p in (case.rom,case.terrain,case.receipt,case.context_path)}
        plan=X.legacy_empty_resource_plan(request,case.project,case.rom)
        self.assertEqual((plan['hidden_bank'],plan['hidden_items'],plan['bomb_doors']),(0x9B,0xC5C2,0))
        self.assertEqual(plan['maps'],list(range(0xA0,0xC0)))
        self.assertEqual(plan['generation'],case.save['generation'])
        self.assertFalse(plan['authored_document_modified']);self.assertFalse(plan['runtime_admission'])
        self.assertEqual(before,{p:p.read_bytes() for p in before})
        authored=json.loads(before[case.terrain])['maps'][16]['authoring']
        self.assertEqual(authored['sprites'][0]['sprite_id'],0x52)
        self.assertIsNone(authored['exits'][0]['exit_row'])
        self.assertEqual(authored['properties']['background_palette'],list(range(128)))
        case.terrain.write_bytes(before[case.terrain]+b' ')
        with self.assertRaises(ValueError):X.legacy_empty_resource_plan(request,case.project,case.rom)

    def test_schema9_unselected_is_never_legacy_empty(self):
        request=self.prepare(9)
        with self.assertRaisesRegex(ValueError,'SCHEMA5_REQUIRED'):
            X.legacy_empty_resource_plan(request,self.case.project,self.case.rom)

    def test_wrong_native_bank_refuses_before_deriving_tables(self):
        request=self.prepare(bad_bank=True)
        with self.assertRaisesRegex(ValueError,'NATIVE_PREIMAGE_MISMATCH'):
            X.legacy_empty_resource_plan(request,self.case.project,self.case.rom)

    def test_changed_empty_terminator_refuses_before_deriving_tables(self):
        request=self.prepare(bad_terminator=True)
        with self.assertRaisesRegex(ValueError,'NATIVE_PREIMAGE_MISMATCH'):
            X.legacy_empty_resource_plan(request,self.case.project,self.case.rom)


class CurrentBuildTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.owner=unittest.TestCase();cls.addClassCleanup(cls.owner.doCleanups)
        import test_lyra_current_transfer as transfer_fixtures
        source_rom=transfer_fixtures.source_rom
        def legacy_source():
            raw=bytearray(source_rom());at=X.A.pc(0x1BC8BE)
            raw[at:at+5]=bytes.fromhex('a99b008502')
            return bytes(raw)
        patch=mock.patch.object(transfer_fixtures,'source_rom',legacy_source)
        patch.start();cls.owner.addCleanup(patch.stop)
        areas=[dict(parent_map_id=a,size='small',maps=[a]) for a in range(0xA0,0xC0)]
        bg=getattr(cls,'BG128',False)
        if bg:
            import test_lyra_current_transfer as transfer_fixtures
            from test_lyra_project_admission import observation
            saved=json.loads((Path(__file__).parent/'fixtures/lyra_saved_authoring_20261027.json').read_bytes())
            palettes={row['map_id']:row['authoring']['properties']['background_palette'] for row in saved['maps']
                      if 'background_palette' in row['authoring']['properties']}
            prepare=transfer_fixtures.CurrentSaveTransferTest.prepare
            def seed(case,**kwargs):
                data=json.loads(case.terrain.read_bytes())
                for row in data['maps']:
                    if row['map_id'] in palettes:
                        row['authoring']['properties']['background_palette']=palettes[row['map_id']]
                        row['authoring']['asset_bindings']=['a'*64]*3
                case.terrain.write_bytes(X.P.encoded(data));case.inputs['terrain']=X.Q.bound(case.terrain)
                case.save['artifacts']=case.artifacts(case.inputs);case.receipt.write_bytes(X.P.encoded(case.save))
                case.proof.clear();case.proof.update(observation(case.rom.read_bytes(),data)[1])
                case.proof['terrain_sha256']=X.R.sha(case.terrain.read_bytes())
                return prepare(case,**kwargs)
            with mock.patch.object(transfer_fixtures.CurrentSaveTransferTest,'prepare',seed):
                cls.f=ComposerFixture(cls.owner,gameplay_areas=areas)
        else:
            cls.f=ComposerFixture(cls.owner,gameplay_areas=areas)
        f=cls.f;c=f.contract_fixture;engine=c.fixture;case=c.case
        bind_origin(c)
        if bg:
            c.value['origins']['code'].update(pc=[0x304000,0x305800],snes=[0xE0C000,0xE0D800])
            c.value['origins']['descriptor'].update(pc=[0x305800,0x305840],snes=[0xE0D800,0xE0D840])
            c.write()
        cls.compiled,cls.symbols=consumer_fixture(f.source,c.value['origins']['code']['snes'][0],
                                                 bg_code=0xE0D000 if bg else None,legacy_empty=True)
        cls.expected=L.inspect_current_consumers(cls.compiled,cls.symbols)
        recipe=case.root/'tail-recipe.json';recipe.write_bytes(X.P.encoded({f'{a:02X}':r for a,r in f.rows.items()}))
        graphics=case.root/'current-graphics.asm';graphics.write_text('; Explicit host graphics fixture, not a resource grant.\n')
        consumers=case.root/'consumers.json';consumers.write_bytes(X.P.encoded(cls.expected))
        cls.review_file=case.root/'current-review.json'
        runtime=dict(kind='lyra.current_runtime_policy.v1',scope='disposable_build_only',runtime_admission=True,
            review_file=str(cls.review_file),tail_recipe=X.Q.bound(recipe),graphics_source=X.Q.bound(graphics),graphics_assets=[],
            compiled_consumers=X.Q.bound(consumers),event_state=dict(flags=0x7EF4C0,version=0x7EF4E0,marker=0xA1),
            origin_preimages=[dict(pc=row['pc'],sha256=X.R.sha(X.A.expanded_rom(f.source)[slice(*row['pc'])]))
                              for row in c.value['origins'].values()])
        if bg:runtime['bg128']=dict(restore_bound=True,code_snes=[0xE0D000,0xE0D800])
        lo,hi=engine.proposal['proposed_tile32_id_range'];source=X.A.expanded_rom(f.source)
        spans=[r['pc'] for r in engine.proposal['packed_preimages']]+[list(X.V.STREAM)]
        policy=dict(id='host-fixture-only',kind=X.POLICY_KIND,scope='disposable_build_only',
            producer_identity_sha256=X.Q.bound(case.producer_path)['sha256'],tile32_id_range=[lo,hi],
            stream_ranges=[list(X.V.STREAM)],preimages=[dict(pc=span,sha256=X.R.sha(source[slice(*span)])) for span in spans],
            spare_tile32_ids=[13993,13994,13995],current_runtime=runtime)
        cls.ledger=c.fixture.root/'Config/allocation_ownership.json';value=json.loads(cls.ledger.read_bytes())
        value['current_save_transfer_policies']=[policy]
        value['claims']=[dict(id=n,space='save_buffer',status='shared',base=b,size=z,aliases=[],condition=dict(LYRA_CURRENT_MODE=1,LYRA_CURRENT_EVENTS_ENABLED=1)) for n,b,z in
            (('LyraCurrentTailFlags',0x7EF4C0,32),('LyraCurrentTailVersion',0x7EF4E0,1))]
        if bg:
            value['claims'].append(dict(id='ProjectBGPaletteNativeUnderlay',space='wram',base=0x7ECA00,size=514,
                status='shared',aliases=[],condition=dict(PROJECT_BG128_ENABLED=1)))
        cls.ledger.write_bytes(X.P.encoded(value));engine.commit();engine.head=engine.git('rev-parse','HEAD').strip()
        engine.refresh_proposal_source();c.review=engine.review();cls.review_file.write_bytes(X.P.encoded(c.review))
        c.value.update(engine_head=engine.head,base_head=engine.head)
        c.value['ledger'].update(sha256=X.Q.bound(cls.ledger)['sha256'],engine_ledger_sha256=X.Q.bound(cls.ledger)['sha256']);c.write()
        request=json.loads(engine.request.read_bytes())
        proof=dict(kind=X.PROOF_KIND,transfer_id=request['transfer_id'],generation=case.save['generation'],operation_id=case.save['operation_id'],
            save_context=X.Q.bound(case.context_path),source_rom_sha256=X.R.sha(f.source),policy_sha256=X.T.digest(policy),
            producer=X.Q.bound(case.producer_path),source_bindings=case.producer['source_bindings'],
            writer_order=['native_save','immutable_snapshot','compile_candidate','no_native_serializer'],
            verification=dict(binary=case.producer['verifier'],log=X.Q.bound(case.root/'producer-test.log'),
                              command='host fixture only',tests=['CurrentBuildHostFixture'],exit_code=0))
        case.enforcement.write_bytes(X.P.encoded(proof));cls.case=case;cls.request=engine.request
        cls.files=X.P.render_outputs(X.ordinary_plan(case.project,case.rom,engine.request))
        cls.prepared=json.loads(cls.files['prepare.json'])

    @classmethod
    def tearDownClass(cls):pass

    def test_real_transfer_profile_compiler_and_composer_select_only_the_private_fixture(self):
        p=self.prepared
        self.assertEqual(p['kind'],'lyra.current_build_prepare.v1');self.assertTrue(p['selected'])
        self.assertEqual(p['generation'],self.case.save['generation'])
        self.assertEqual(p['actor_storage_plan']['payload_bytes'],1)
        self.assertEqual(len(p['tables']['tables']),38)
        self.assertTrue({'special_sprite_gfx_phase1', 'special_sprite_gfx_phase2',
                         'special_sprite_palettes_phase1', 'special_sprite_palettes_phase2'}
                        <= {row['name'] for row in p['tables']['tables']})
        self.assertIn(b'!LYRA_CURRENT_EVENTS_ENABLED = 1',self.files['runtime_constants.asm'])
        self.assertIn(b'!LYRA_CURRENT_LEGACY_EMPTY_RESOURCES = 1',self.files['runtime_constants.asm'])
        self.assertEqual(p['legacy_empty_resources']['authored_schema_version'],5)
        self.assertFalse(p['legacy_empty_resources']['saved_state_modified'])
        self.assertIn(b'!LYRA_CURRENT_ACTORS_ENABLED = 1',self.files['runtime_constants.asm'])
        self.assertIn(b'Lyra_CurrentActorData:',self.files['runtime_data.asm'])
        self.assertIn(b'incbin "binaries/payload.bin":',self.files['runtime_data.asm'])
        self.assertFalse(p['native_gameplay_verified']);self.assertFalse(self.case.candidate.exists())

    def test_context_reconstructs_all_generated_files_and_rejects_changed_payload(self):
        root=Path(self.prepared['current_source_profile']['selected_source']['root']);folder=root/X.P.OUTPUT
        X.P.write_outputs(folder,self.files)
        self.assertEqual(X.verify_current_context(root,self.prepared),self.files)
        path=folder/'binaries/payload.bin';original=path.read_bytes()
        try:
            path.write_bytes(b'bad')
            with self.assertRaisesRegex(ValueError,'CONTEXT_STALE'):X.verify_current_context(root,self.prepared)
        finally:path.write_bytes(original)

    def test_actual_compiled_consumer_snapshot_refuses_changed_hook_code_or_symbols(self):
        for at in (X.A.pc(0x02F59D),X.A.pc(0x1BC906),X.A.pc(0xE0C000),X.A.pc(0xE68000)):
            rom=bytearray(self.compiled);rom[at]^=1
            try:observed=L.inspect_current_consumers(bytes(rom),self.symbols)
            except ValueError:continue
            self.assertNotEqual(observed,self.expected)
        with self.assertRaisesRegex(ValueError,'Missing current consumer symbol'):
            L.inspect_current_consumers(self.compiled,b'[labels]\n')

    def test_missing_ungranted_conflicting_event_claims_refuse(self):
        value=self.prepared['event_state'];ledger=json.loads(self.ledger.read_bytes())
        for change in ('missing','proposed','predicate','overlap'):
            bad=copy.deepcopy(ledger)
            if change=='missing':bad['claims']=[]
            elif change=='proposed':bad['claims'][0]['status']='proposed'
            elif change=='predicate':bad['claims'][0]['condition']={'LYRA_CURRENT_EVENTS_ENABLED':0}
            else:bad['claims'].append(dict(id='foreign',space='save_buffer',status='shared',base=0x7EF4C0,size=1))
            with self.assertRaisesRegex(ValueError,'CURRENT_EVENT_STATE_'):X.current_event_state(value,bad)

    def test_changed_review_and_recipe_retire_selection_without_any_rom_write(self):
        for path in (self.review_file,Path(json.loads(self.ledger.read_bytes())['current_save_transfer_policies'][0]['current_runtime']['tail_recipe']['path'])):
            before=path.read_bytes()
            try:
                path.write_bytes(b'{}')
                with self.assertRaises((ValueError,KeyError)):X.ordinary_plan(self.case.project,self.case.rom,self.request)
            finally:path.write_bytes(before)
        self.assertFalse(self.case.candidate.exists())

    def test_complete_derived_data_and_reviewed_code_read_back_and_mutations_refuse(self):
        rom=bytearray(self.compiled);p=self.prepared
        writes=[*p['terrain_plan']['writes'],*p['tables']['tables']]
        for row in writes:rom[slice(*row['pc'])]=bytes.fromhex(row['payload_hex'])
        rom[slice(*p['tables']['descriptor_pc'])]=bytes.fromhex(p['tables']['descriptor_hex'])
        actor=p['actor_storage_plan'];at=X.A.pc(actor['data_snes'])
        rom[at:at+actor['payload_bytes']]=bytes.fromhex(actor['payload_hex'])
        result=X.verify_current_output(p,bytes(rom),self.symbols)
        self.assertTrue(result['compiled_consumers_verified'])
        self.assertEqual(result['native_planes_preserved'],320)
        self.assertFalse(result['native_gameplay_verified'])
        for at in (p['tables']['tables'][0]['pc'][0],X.A.pc(actor['data_snes']),
                   p['terrain_plan']['writes'][-1]['pc'][0]):
            wrong=bytearray(rom);wrong[at]^=1
            with self.assertRaisesRegex(ValueError,'PAYLOAD_MISMATCH'):
                X.verify_current_output(p,bytes(wrong),self.symbols)

    def test_post_assembly_existing_target_uses_exact_read_only_scope(self):
        p=self.prepared;rom=bytearray(self.compiled)
        for row in [*p['terrain_plan']['writes'],*p['tables']['tables']]:
            rom[slice(*row['pc'])]=bytes.fromhex(row['payload_hex'])
        rom[slice(*p['tables']['descriptor_pc'])]=bytes.fromhex(p['tables']['descriptor_hex'])
        actor=p['actor_storage_plan'];at=X.A.pc(actor['data_snes']);rom[at:at+actor['payload_bytes']]=bytes.fromhex(actor['payload_hex'])
        target=Path(p['terrain_plan']['target']['path']);symbol=target.with_suffix('.sym')
        try:
            target.write_bytes(rom);symbol.write_bytes(self.symbols)
            with self.assertRaisesRegex(ValueError,'new separate4MiB'):X.verify_transfer(self.request,self.case.project,self.case.rom)
            with X.candidate_inspection(target):
                X.verify_transfer(self.request,self.case.project,self.case.rom)
                self.assertTrue(X.verify_current_output(p,bytes(rom),self.symbols)['compiled_consumers_verified'])
            with self.assertRaisesRegex(ValueError,'new separate4MiB'):X.verify_transfer(self.request,self.case.project,self.case.rom)
            root=Path(p['current_source_profile']['selected_source']['root']);X.P.write_outputs(root/X.P.OUTPUT,self.files)
            receipt=target.parent/'host-verification.json'
            result=X.P.verify(root/X.P.OUTPUT,target,symbol,receipt=receipt)
            self.assertTrue(result['compiled_consumers_verified'])
            self.assertFalse(result['native_gameplay_verified'])
            import asm_source
            with mock.patch.dict(X.os.environ,{'OOS_LYRA_BUILD_CONTEXT':'1'}):
                defines=asm_source._load_global_defines(root)
            self.assertEqual((defines['LYRA_CURRENT_ACTORS_ENABLED'],defines['LYRA_CURRENT_EVENTS_ENABLED']),(1,1))
        finally:
            target.unlink(missing_ok=True);symbol.unlink(missing_ok=True)

    def test_staging_is_exact_four_mib_and_never_replaces_an_existing_target(self):
        root=Path(self.prepared['current_source_profile']['selected_source']['root']);folder=root/X.P.OUTPUT
        X.P.write_outputs(folder,self.files);target=Path(self.prepared['terrain_plan']['target']['path'])
        try:
            self.assertTrue(X.P.stage_current_candidate(folder,target)['rom_written'])
            self.assertEqual(target.read_bytes(),X.A.expanded_rom(self.f.source))
            with self.assertRaisesRegex(ValueError,'TARGET_MISMATCH'):X.P.stage_current_candidate(folder,target)
            # A source scanner can inspect an admitted source context before
            # assembly, but the separate compiled consumer verifier still fails.
            import asm_source
            with mock.patch.dict(X.os.environ,{'OOS_LYRA_BUILD_CONTEXT':'1'}):
                self.assertEqual(asm_source._load_global_defines(root)['LYRA_CURRENT_MODE'],1)
            with X.candidate_inspection(target),self.assertRaises(ValueError):
                X.verify_current_output(self.prepared,target.read_bytes(),self.symbols)
        finally:target.unlink(missing_ok=True)

    def test_unrelated_namespace_collisions_are_ignored_but_required_roles_are_unique(self):
        symbols=self.symbols+b'01:8000 Unrelated\n02:8000 Oracle_Unrelated\n'
        self.assertEqual(L.inspect_current_consumers(self.compiled,symbols),self.expected)
        with self.assertRaisesRegex(ValueError,'Conflicting current consumer symbol'):
            L.inspect_current_consumers(self.compiled,self.symbols+b'01:8000 Oracle_Frame8\n')
