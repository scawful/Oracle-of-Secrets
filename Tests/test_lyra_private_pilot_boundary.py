"""Private pair source/consumer controls; no assembler or native execution."""
import copy
from dataclasses import replace
import json
import hashlib
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'Scripts/Build'))
sys.path.insert(0,str(ROOT/'Scripts/Generate'))
import lyra_native_loaders as L
import lyra_project_terrain as T
import asm_source as S
from test_lyra_current_build import consumer_fixture
from test_lyra_project_admission import document,source_rom
from test_lyra_current_port_integration import statements


def pilot_compiled_fixture():
    rom,symbols=consumer_fixture(source_rom(),0xE0C000)
    labels=L._labels(symbols);host=labels['LyraHost_OverworldHandleTransitions']
    call=host+0x40;blocked=host+0x20;helper=0xE0C7E0
    raw=b'\x22'+helper.to_bytes(3,'little')+bytes([0xB0,(blocked-call-6)&255])
    rom=bytearray(rom);rom[L.A.pc(call):L.A.pc(call)+6]=raw
    rom[L.A.pc(0x02A634):L.A.pc(0x02A634)+8]=bytes.fromhex('0200feff1000f0ff')
    symbols+=(''.join(f'{at>>16:02X}:{at&65535:04X} {name}\n' for name,at in
        [('LyraCall_PrivatePilotBoundary',call),('LyraPilot_BoundaryBlocked',blocked),
         ('Lyra_PrivatePilotCanScroll',helper)])).encode()
    return bytes(rom),symbols,call


class PrivatePilotBoundaryTest(unittest.TestCase):
    def test_source_plan_is_exact_private_selection_and_preserves_all_authored_content(self):
        raw=document();raw['maps'][16]['authoring']['doors']=[dict(id=24577,x=21,y=9,entrance_id=11)]
        raw['maps'][16]['authoring']['exits']=[dict(id=24578,x=22,y=11,room_id=131,exit_row=None)]
        parsed=T.parse_terrain_document(json.dumps(raw),raw['profile'],allow_authoring_drafts=True)
        before=copy.deepcopy(parsed);areas=[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)]
        plan=L.plan_private_pilot_boundaries(parsed,areas)
        self.assertEqual(parsed,before);self.assertEqual(plan['allowed_tail_maps'],[0xA0,0xA1])
        self.assertEqual(len(plan['unselected_tail_maps']),30);self.assertEqual(len(plan['blocked_scroll_edges']),6)
        self.assertEqual(plan['protected_legacy_storage_span'],[0x93,0x9F]);self.assertFalse(plan['overlay_decoding_changed'])
        self.assertEqual(len(plan['named_overlay_templates']),9)
        self.assertNotIn(0x98,plan['named_overlay_templates']);self.assertEqual(plan['approved_native_coast_map'],0x98)
        for key in ('allocation_granted','producer_enforcement_verified','runtime_admission','boundaries_compiled','rom_written'):
            self.assertIs(plan[key],False,key)
        for foreign in (areas[:1],[dict(parent_map_id=0xA0,size='wide',maps=[0xA0,0xA1])],
                        areas+[dict(parent_map_id=0xB0,size='small',maps=[0xB0])]):
            with self.assertRaisesRegex(ValueError,'AREAS_UNBOUND'):L.plan_private_pilot_boundaries(parsed,foreign)
        conflicting=replace(parsed,gameplay_areas=(dict(parent_map_id=0xA0,size='wide',maps=[0xA0,0xA1]),))
        with self.assertRaisesRegex(ValueError,'AREAS_CONFLICT'):L.plan_private_pilot_boundaries(conflicting,areas)

    def test_subset_view_and_terrain_keep_all_saved_metadata_without_assigning_other_areas(self):
        from lyra_project_terrain import Allocation,compile_terrain
        raw=document();raw['maps'][16]['authoring']['doors']=[dict(id=24577,x=21,y=9,entrance_id=11)]
        parsed=T.parse_terrain_document(json.dumps(raw),raw['profile'],allow_authoring_drafts=True)
        before=copy.deepcopy(parsed)
        pilot=L.plan_private_pilot_boundaries(parsed,[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        view=L.private_pilot_document(parsed,pilot)
        self.assertEqual((view.maps,view.properties,view.authoring),(parsed.maps,parsed.properties,parsed.authoring))
        self.assertEqual(len(view.gameplay_areas),2);self.assertEqual(parsed,before)
        directory,closure=L.A.render_dependency_plan([0xA0,0xA1],document=view)
        self.assertEqual(closure,(0xA0,0xA1));self.assertEqual(directory,{0xA0:(0xA0,)*4,0xA1:(0xA1,)*4})
        compiled=compile_terrain(view,{0:(0,0,0,0)},Allocation(((0x300000,0x301000),),(),tile32_capacity=1),
                                 map_ids=[0xA0,0xA1],render_directory=directory)
        self.assertEqual([row.map_id for row in compiled.maps],[0xA0,0xA1])
        transitions=L.A.gameplay_transition_rows(source_rom(),view,private_pilot=True)
        self.assertEqual(set(transitions),{0xA0,0xA1})
        with self.assertRaisesRegex(ValueError,'all32'):
            L.A.gameplay_transition_rows(source_rom(),view)
        stale=copy.deepcopy(pilot);stale['allowed_tail_maps'].append(0xA2)
        with self.assertRaisesRegex(ValueError,'SELECTION_STALE'):L.private_pilot_document(parsed,stale)

    def test_authored_scroll_to_unselected_area_refuses_without_stripping_it(self):
        parsed=T.parse_terrain_document(json.dumps(document()),document()['profile'],allow_authoring_drafts=True)
        pilot=L.plan_private_pilot_boundaries(parsed,[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        for target in (0xA2,0xB0,0x98):
            changed=replace(parsed,edge_connections=({'map_a':0xA1,'map_b':target},))
            plan=L.plan_private_pilot_boundaries(changed,pilot['selected_areas'])
            with self.assertRaisesRegex(ValueError,'UNSELECTED_EDGE'):L.private_pilot_document(changed,plan)
            self.assertEqual(changed.edge_connections[0]['map_b'],target)

    def test_partial_tables_keep_native_prefix_and_leave_other_tail_rows_inert(self):
        from test_lyra_current_native_loaders import CurrentNativeLoaderTests as F
        F.setUpClass()
        parsed=T.parse_terrain_document(json.dumps(document()),document()['profile'],allow_authoring_drafts=True)
        pilot=L.plan_private_pilot_boundaries(parsed,[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        rows={a:F.rows[a] for a in (0xA0,0xA1)}
        result=L.plan_current_tables(F.source,rows,origins=F.origins,policy=F.policy,private_pilot=pilot)
        self.assertEqual(result['admitted_maps'],[0xA0,0xA1]);self.assertEqual(len(result['unadmitted_maps']),30)
        for row,full in zip(result['tables'],F.plan['tables']):
            raw=bytes.fromhex(row['payload_hex']);stride=row['stride']
            self.assertEqual(raw[:0xA0*stride],bytes.fromhex(full['payload_hex'])[:0xA0*stride])
            self.assertEqual(raw[0xA2*stride:],bytes(30*stride))
        with self.assertRaisesRegex(ValueError,'all32'):
            L.plan_current_tables(F.source,rows,origins=F.origins,policy=F.policy)
        rows[0xB0]=F.rows[0xB0]
        with self.assertRaisesRegex(ValueError,'RECIPE_UNSELECTED'):
            L.plan_current_tables(F.source,rows,origins=F.origins,policy=F.policy,private_pilot=pilot)

    def test_subset_cannot_replace_source_or_entry_or_ingress_qualification(self):
        import tempfile
        import lyra_current_transfer as X
        import lyra_private_reservation as V
        parsed=T.parse_terrain_document(json.dumps(document()),document()['profile'],allow_authoring_drafts=True)
        pilot=L.plan_private_pilot_boundaries(parsed,[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        with self.assertRaisesRegex(ValueError,'SOURCE_UNBOUND'):
            V.compile_native_plan(source_rom(),parsed,None,{},private_pilot=pilot)
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'selection.json'
            for area,room,row in ((0xA0,None,None),(0xB0,131,41),(0xA0,131,41)):
                value=dict(kind='lyra.private_pilot_runtime_selection.v1',selected_areas=pilot['selected_areas'],
                           entry_map_id=area,entry_room_id=room,entry_exit_row=row)
                path.write_text(json.dumps(value))
                with self.assertRaisesRegex(ValueError,'ENDPOINT_UNBOUND'):
                    X.private_pilot_runtime({'private_pilot':X.Q.bound(path)},source_rom(),parsed)
        rom,symbols,_=pilot_compiled_fixture()
        scroll_only=L.inspect_current_consumers(rom,symbols)
        with self.assertRaisesRegex(ValueError,'INGRESS_UNBOUND'):L.require_private_pilot_ingress(scroll_only)
        asm=(ROOT/'Overworld/lyra_private_pilot.asm').read_text()
        self.assertIn('CMP.w #$00A2 : BCS .blocked',asm)
        self.assertNotIn('STA',asm[asm.index('Lyra_PrivatePilotCanEnter:'):asm.index('Lyra_PrivatePilotCanEnter_End')])

    def test_disabled_boundary_has_no_new_instructions_and_call_precedes_state_mutation(self):
        text=(ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        base=S._load_global_defines(ROOT)
        host=text[text.index('OverworldHandleTransitions:\n'):text.index('org $02A62C ;',text.index('OverworldHandleTransitions:\n'))]
        off=statements(host,dict(base,LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=0))
        absent=statements(host,base)
        self.assertEqual(absent,off)
        # Frozen62b instruction baselines: absent/zero remains byte-equivalent
        # in both native and current source paths. This is not an Asar run.
        digests={0:'c0451aba9645e9e0394eb16809f5c6f95b16813654dbdbfd795411dced8250a2',
                 1:'67baca06839de41268d3873fdbfe4d79f38451d41a76e39e8c5a176ec27382fc'}
        for mode,digest in digests.items():
            defines=dict(base,LYRA_CURRENT_MODE=mode,LYRA_PROJECT_DATA_PRESENT=mode,
                         LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=0)
            self.assertEqual(hashlib.sha256('\n'.join(statements(host,defines)).encode()).hexdigest(),digest)
        enabled=statements(host,dict(base,LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=1))
        self.assertEqual(len(enabled),len(off)+2)
        index=enabled.index('JSL Lyra_PrivatePilotCanScroll')
        self.assertEqual(enabled[index:index+2],['JSL Lyra_PrivatePilotCanScroll','BCS .noTransition'])
        call=host.index('JSL Lyra_PrivatePilotCanScroll')
        for mutation in ('JSR.w DeleteCertainAncillaeStopDashing','STA.b $84','STA.b $8A','STA.w $040A'):
            self.assertLess(call,host.index(mutation))
        helper=(ROOT/'Overworld/lyra_private_pilot.asm').read_text()
        self.assertIn('assert !LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND == 1',helper)
        instructions=statements(helper[:helper.index('; The earlier scroll prototype')],dict(base,LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=1,LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND=1))
        self.assertFalse(any(line.split()[0].upper() in ('STA','STA.B','STA.W','STA.L','STZ','STZ.W','STZ.B') for line in instructions))
        self.assertIn('ADC.l OverworldScreenIDChange, X',instructions)
        # Exact private pair source checks and stack-only ABI; execution remains unrun.
        for line in ('CPY.w #$0000','CPY.w #$0002','CMP.w #$0040','CMP.w #$0042','CMP.w #$0140'):
            self.assertIn(line,instructions)

    def test_ingress_inspection_requires_every_preaccess_role_and_exact_helper_bytes(self):
        rom,symbols,_=pilot_compiled_fixture();labels=L._labels(symbols)
        helper=0xE0C7C0;host=labels['LyraHost_OverworldHandleTransitions']
        rom=bytearray(rom);rom[L.A.pc(helper):L.A.pc(helper)+len(L.PRIVATE_PILOT_ENTRY_BYTES)]=L.PRIVATE_PILOT_ENTRY_BYTES
        extra=[('Lyra_PrivatePilotCanEnter',helper),('Lyra_PrivatePilotCanEnter_End',helper+len(L.PRIVATE_PILOT_ENTRY_BYTES))]
        for i,role in enumerate(L.PRIVATE_PILOT_INGRESS_ROLES):
            call=host+0x60+i*8;blocked=host+0x20
            rom[L.A.pc(call):L.A.pc(call)+6]=b'\x22'+helper.to_bytes(3,'little')+bytes([0xB0,(blocked-call-6)&255])
            extra.extend([('LyraCall_PrivatePilot'+role,call),('LyraPilot_'+role+'Blocked',blocked)])
        symbols+=(''.join(f'{at>>16:02X}:{at&65535:04X} {name}\n' for name,at in extra)).encode()
        result=L.inspect_current_consumers(bytes(rom),symbols)
        self.assertEqual(len(L.require_private_pilot_ingress(result)['calls']),6)
        # Byte vectors are explicit host fixtures, not assembled or admitted callers.
        rom[L.A.pc(helper)+1]^=1
        with self.assertRaises(ValueError):L.inspect_current_consumers(bytes(rom),symbols)
        missing=b'\n'.join(line for line in symbols.splitlines() if b'LyraCall_PrivatePilotColdResume' not in line)
        with self.assertRaisesRegex(ValueError,'INGRESS_UNBOUND'):L.inspect_current_consumers(bytes(rom),missing)

    def test_actual_module08_and_mirror_gate_sources_keep_remaining_roles_held(self):
        asm=(ROOT/'Overworld/lyra_private_pilot.asm').read_text()
        self.assertIn('!LYRA_PRIVATE_PILOT_INGRESS_ENABLED = 0',asm)
        self.assertIn('assert !REGIONAL_CHECKPOINTS_ENABLED == 1',asm)
        self.assertIn('assert !REGIONAL_CHECKPOINTS_BOUND == 1',asm)
        entry=asm[asm.index('Lyra_PrivatePilotEntryGate:'):asm.index('Lyra_PrivatePilotEntryGate_End')]
        self.assertLess(entry.index('JSL Lyra_PrivatePilotEntryMap'),entry.index('STA.b $99'))
        self.assertLess(entry.index('JSL Lyra_PrivatePilotCanEnter'),entry.index('STA.b $99'))
        self.assertIn('JSL Checkpoint_EnterHome\n  RTS',entry)
        self.assertNotIn('JML Checkpoint_EnterHome',entry)
        self.assertIn('LyraCall_PrivatePilotColdResume = pc()',entry)
        for role in ('Warp',):
            self.assertNotIn('LyraCall_PrivatePilot'+role+' = pc()',asm)
        current=asm[asm.index('Lyra_PrivatePilotCurrentMapAllowed:'):asm.index('Lyra_PrivatePilotCurrentMapAllowed_End')]
        self.assertIn('LDA.b $8A',current);self.assertNotIn('AND',current);self.assertNotIn('$0700',current)
        mirror=asm[asm.index('Lyra_PrivatePilotMirrorGate:'):asm.index('Lyra_PrivatePilotMirrorGate_End')]
        self.assertIn('JML $02B21B',mirror);self.assertIn('JML $02B21D',mirror)
        self.assertNotIn('STA',mirror);self.assertNotIn('AND',mirror)
        scanner=asm[asm.index('Lyra_PrivatePilotEntryMap:'):asm.index('Lyra_PrivatePilotEntryMap_End')]
        self.assertIn('LDX.w #$009C',scanner);self.assertIn('DEX #2 : BPL .next',scanner)
        self.assertIn('LDA.l $7EC140 : CMP.w #$00A2',scanner)
        self.assertIn('LDA.l $7EC14C : CMP.w #$00A2',scanner)
        self.assertIn('CMP.w #$0008 : BNE .allowed',entry)
        self.assertIn('LDA.l $02DE28,X : AND.w #$00FF',scanner)

    def test_full_sub_whole_operation_sources_and_native_static_fail_closed(self):
        asm=(ROOT/'Overworld/lyra_private_pilot.asm').read_text()
        self.assertNotIn('org $02B1F0',asm)
        self.assertIn('PEA.w $B1F8\n  JML $02ED59',asm)
        near=asm[asm.index('Lyra_PrivatePilotFullNearGate:'):asm.index('Lyra_PrivatePilotFullNearGate_End')]
        self.assertLess(near.index('JSL Lyra_PrivatePilotCurrentMapAllowed'),near.index('JSL Lyra_PrivatePilotFullNativeCall'))
        self.assertIn('JSL Checkpoint_EnterHome\n  RTS',near)
        frame=asm[asm.index('Lyra_PrivatePilotFullFrameGate:'):asm.index('Lyra_PrivatePilotFullFrameGate_End')]
        self.assertTrue(frame.index('SEP #$30')<frame.index('JSL Lyra_PrivatePilotCanEnter')<frame.index('JML $02A479'))
        self.assertIn('JSL Checkpoint_EnterHome\n  RTL',frame)
        overlay=(ROOT/'Overworld/ZSCustomOverworld.asm').read_text()
        block=overlay[overlay.index('Lyra_Fixture_PreOverlaySelect = pc()'):overlay.index('STY.b $84',overlay.index('Lyra_Fixture_PreOverlaySelect = pc()'))]
        self.assertIn('JML Lyra_PrivatePilotSubGate\n        NOP #4',block)
        self.assertIn('LyraPilot_SubNativeAllowed = pc()',block)
        sub=asm[asm.index('Lyra_PrivatePilotSubGate:'):asm.index('Lyra_PrivatePilotSubGate_End')]
        self.assertIn('PHP : PHA : TXA',sub)
        self.assertIn('JML LyraPilot_SubNativeNoOverlay',sub);self.assertNotIn('Checkpoint_EnterHome',sub)
        with self.assertRaisesRegex(ValueError,'NATIVE_FULL_CALLER_CHANGED'):
            L.private_pilot_native_full_paths(bytes(0x200000))

    def test_native_full_data_is_full_word_and_credits_mismatch_stays_explicit(self):
        source=bytearray(0x200000)
        def put(at,raw):source[L.A.pc(at):L.A.pc(at)+len(raw)]=raw
        for at,raw in ((0x0286A5,'2059ed'),(0x02B1F0,'2059ed6b201eafc6116b'),(0x0AB953,'22f0b102'),
                (0x02ABCC,'20e8ef'),(0x02EEC7,'204af5'),(0x02EFEA,'204af5'),(0x02B31A,'20c5ee'),
                (0x02ED8D,'20c5ee'),(0x02FD0F,'20cbf7')):put(at,bytes.fromhex(raw))
        descriptors=(0x1000,2,0x1002,0x1012,0x1004,0x1006,0x1010,0x1014,0x100A,0x1016,0x5D,0x64,0x100E,0x1008,0x1018,0x180)
        raw=b''.join(v.to_bytes(2,'little') for v in descriptors);put(0x0285C2,raw);put(0x02DD8A,raw)
        put(0x02DE28,bytes(range(16)))
        report=L.private_pilot_native_full_paths(bytes(source))
        self.assertTrue(report['complete']);self.assertEqual(len(report['transport_maps']),17)
        self.assertFalse(report['warp_admission']);self.assertFalse(report['runtime_admission'])
        put(0x02DE28,b'\xa0')
        report=L.private_pilot_native_full_paths(bytes(source))
        self.assertFalse(report['complete']);self.assertEqual(report['held_callers'][0]['room'],0x1000)
        for word in (0xA0,0xA1,0x100,0xFFFF):
            put(0x02EAE5,word.to_bytes(2,'little'))
            with self.assertRaisesRegex(ValueError,'NATIVE_TRANSPORT_CHANGED'):
                L.private_pilot_native_full_paths(bytes(source))

    def test_optional_compiled_consumer_requires_exact_carry_branch_target_and_direction_table(self):
        rom,symbols,call=pilot_compiled_fixture()
        result=L.inspect_current_consumers(rom,symbols);proof=result['private_pilot_boundary']
        self.assertEqual(proof['scope'],'private_A0_A1_scroll_only');self.assertFalse(proof['entry_warp_loader_admission'])
        for at in (L.A.pc(call)+1,L.A.pc(call)+4,L.A.pc(call)+5,L.A.pc(0x02A634)):
            altered=bytearray(rom);altered[at]^=1
            with self.assertRaises(ValueError):L.inspect_current_consumers(bytes(altered),symbols)
        partial=b'\n'.join(line for line in symbols.splitlines() if b'LyraPilot_BoundaryBlocked' not in line)
        with self.assertRaisesRegex(ValueError,'Incomplete private pilot'):L.inspect_current_consumers(rom,partial)
        oldrom,oldsymbols=consumer_fixture(source_rom(),0xE0C000)
        self.assertNotIn('private_pilot_boundary',L.inspect_current_consumers(oldrom,oldsymbols))


class PrivatePilotComposerTest(unittest.TestCase):
    def test_real_source_bound_subset_compiles_and_composes_without_runtime_admission(self):
        # Reuse copied-project source/generation fixtures. Only the external
        # editor observation is a fixture; source binding/review/compiler and
        # composer are maintained implementations, with all authority OFF.
        from test_lyra_current_composer_binding import ComposerFixture
        from test_lyra_current_actor_storage import bind_origin,storage
        import lyra_current_transfer as X
        import lyra_private_reservation as V
        from lyra_project_terrain import Allocation
        f=ComposerFixture(self);f.profile=bind_origin(f.contract_fixture)
        pilot=L.plan_private_pilot_boundaries(f.document,[dict(parent_map_id=a,size='small',maps=[a]) for a in (0xA0,0xA1)])
        view=L.private_pilot_document(f.document,pilot)
        directory,_=L.A.render_dependency_plan([0xA0,0xA1],document=view)
        review=f.profile['review'];lo,hi=review['tile32_id_range'];spares=review['spare_tile32_ids']
        ids=tuple(i for i in range(lo,hi) if i not in spares)
        missing=X.C._missing(X.A.expanded_rom(f.source),f.document,[0xA0,0xA1])
        allocation=Allocation((tuple(review['preimages'][-1]['pc']),),ids,tile32_assignments=tuple(zip(ids,missing)))
        plan,payload=V.compile_native_plan(f.source,f.document,allocation,directory,
            spare_tile32_ids=spares,current_source_profile=f.profile,private_pilot=pilot)
        self.assertEqual(plan['selected_maps'],[0xA0,0xA1]);self.assertEqual(len(plan['streams']),4)
        self.assertTrue(payload);self.assertEqual(plan['native_maps_preserved'],160)
        actors=storage(f.source,f.document,f.profile,private_pilot=pilot)
        self.assertEqual(set(actors['phase_rows']),{0xA0,0xA1})
        self.assertEqual(actors['actor_stream_plan']['demand']['pointer_rows'],6)
        rows={a:copy.deepcopy(f.rows[a]) for a in (0xA0,0xA1)}
        for a,v in L.A.gameplay_transition_rows(f.source,view,private_pilot=True).items():rows[a].update(v)
        for a,v in actors['phase_rows'].items():rows[a].update(v)
        origins=f.profile['origins']
        tables=L.plan_current_tables(f.source,rows,
            origins=dict(table_base=origins['tables']['snes'][0],code_base=origins['code']['snes'][0],
                code_end=origins['code']['snes'][1],descriptor_base=origins['descriptor']['snes'][0]),
            policy=dict(source_rom_sha256=X.R.sha(f.source),source_profile_sha256=X.T.digest(f.profile),
                        allocation_granted=False,publication_authorized=False),private_pilot=pilot)
        graphics='; Host source only, no asset grant.\n'
        files=X.P.render_current_source_outputs(tables,contract=f.contract,graphics_source=graphics,
            graphics_report=dict(current_mode=True,parent_count=192,
                source_contract_sha256=X.R.sha(X.P.encoded(f.contract)),generated_sha256=X.R.sha(graphics.encode()),
                graphics_origin_snes=f.contract['origins']['graphics']['snes']),
            current_source_profile=f.profile,actor_storage_plan=actors,private_pilot=pilot)
        prepared=json.loads(files['prepare.json'])
        self.assertEqual(prepared['document_sha256'],X._document_identity(f.document))
        self.assertEqual([r['map_id'] for r in prepared['native_state_contract']['event_rows']],[0xA0,0xA1])
        self.assertEqual(len(f.document.maps),32);self.assertFalse(f.document.gameplay_areas)
        self.assertFalse(prepared['selected']);self.assertFalse(prepared['runtime_admission'])
        f.contract_fixture.case.next_save()
        with self.assertRaisesRegex(ValueError,'retired'):
            L.plan_current_actor_streams(f.source,f.document,current_source_profile=f.profile,private_pilot=pilot)


if __name__=='__main__':unittest.main()
