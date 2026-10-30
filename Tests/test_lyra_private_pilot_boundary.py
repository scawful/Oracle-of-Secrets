"""Private pair source/consumer and bounded Asar/offline return controls."""
import copy
from dataclasses import replace
import json
import hashlib
import functools
import os
import shutil
import subprocess
import tempfile
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
from lyra_source_snapshots import read_snapshot_text


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
        base['LYRA_PRIVATE_PILOT_INGRESS_ENABLED']=0  # Explicit unrelated HOST feature selection.
        host=text[text.index('OverworldHandleTransitions:\n'):text.index('org $02A62C ;',text.index('OverworldHandleTransitions:\n'))]
        off=statements(host,dict(base,LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=0))
        absent=statements(host,base)
        self.assertEqual(absent,off)
        frozen=read_snapshot_text('6e7e5f15d555dffb9f4b3d8807595c9e3f13305f',
                                  'Overworld/ZSCustomOverworld.asm')
        begin=frozen.index('OverworldHandleTransitions:\n')
        frozen_host=frozen[begin:frozen.index('org $02A62C ;',begin)]
        # Retain both frozen62b digests on the bundled6e host. Successor859f10a
        # corrected only two current-mode coordinate operands. Not an Asar run.
        digests={0:'c0451aba9645e9e0394eb16809f5c6f95b16813654dbdbfd795411dced8250a2',
                 1:'67baca06839de41268d3873fdbfe4d79f38451d41a76e39e8c5a176ec27382fc'}
        for mode,digest in digests.items():
            defines=dict(base,LYRA_CURRENT_MODE=mode,LYRA_PROJECT_DATA_PRESENT=mode,
                         LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=0)
            expected=statements(frozen_host,defines)
            self.assertEqual(hashlib.sha256('\n'.join(expected).encode()).hexdigest(),digest)
            if mode:
                for axis in ('Y','X'):
                    old='SBC.l Pool_OverworldTransitionPosition'+axis+'_New, X'
                    self.assertEqual(expected.count(old),1)
                    expected[expected.index(old)]='SBC.l !LYRA_CURRENT_TABLE_transition_'+axis.lower()+', X'
            self.assertEqual(statements(host,defines),expected)
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
        coordinates={labels['LyraCall_TransitionDelta'+axis]:
                     rom[L.A.pc(labels['LyraCall_TransitionDelta'+axis]):
                         L.A.pc(labels['LyraCall_TransitionDelta'+axis])+4]
                     for axis in ('Y','X')}
        rom=bytearray(rom);rom[L.A.pc(helper):L.A.pc(helper)+len(L.PRIVATE_PILOT_ENTRY_BYTES)]=L.PRIVATE_PILOT_ENTRY_BYTES
        extra=[('Lyra_PrivatePilotCanEnter',helper),('Lyra_PrivatePilotCanEnter_End',helper+len(L.PRIVATE_PILOT_ENTRY_BYTES))]
        for i,role in enumerate(L.PRIVATE_PILOT_INGRESS_ROLES):
            call=host+0x90+i*8;blocked=host+0x60
            self.assertTrue(-128 <= blocked-call-6 <= 127)
            self.assertTrue(all(call+6 <= at or at+4 <= call for at in coordinates))
            rom[L.A.pc(call):L.A.pc(call)+6]=b'\x22'+helper.to_bytes(3,'little')+bytes([0xB0,(blocked-call-6)&255])
            extra.extend([('LyraCall_PrivatePilot'+role,call),('LyraPilot_'+role+'Blocked',blocked)])
        for at,before in coordinates.items():
            self.assertEqual(bytes(rom[L.A.pc(at):L.A.pc(at)+4]),before)
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
        self.assertIn('JSL Checkpoint_EnterHome\n  JML $02EDC4',entry)
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
        self.assertIn('JSL Checkpoint_EnterHome\n  JML $02EDC4',near)
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


@functools.lru_cache(maxsize=1)
def assembled_preview_guard_fixture():
    """Reassemble current guards over preserved sparse f45 diagnostic windows.

    The old raw fixture stays immutable. Only the current source's guard code,
    hooks and relocated overlay dispatch are new; Home/host bytes stay pinned.
    This synthetic combination is not a game build or native qualification.
    """
    data=json.loads((ROOT/'Tests/fixtures/lyra_actual_preview_guard_windows.json').read_bytes())
    source=bytearray(0x200000)
    for row in data['source_windows']:
        raw=bytes.fromhex(row['payload_hex']);pc=L.A.pc(row['snes']);source[pc:pc+len(raw)]=raw
    # Existing native Module08 RTS, independently read from preserved625 ROM.
    source[L.A.pc(0x02EDC4)]=0x60
    compiled=source+bytearray(0x200000)
    for row in data['compiled_windows']:
        raw=bytes.fromhex(row['payload_hex']);pc=L.A.pc(row['snes']);compiled[pc:pc+len(raw)]=raw
    # Asar must check actual unpatched hook preimages, not prior JML bytes.
    for at in (0x0283C7,0x02B217,0x02EDB9,0x02A475):
        pc=L.A.pc(at);compiled[pc:pc+4]=source[pc:pc+4]
    asar=os.environ.get('ASAR_BIN') or shutil.which('asar')
    if not asar:raise unittest.SkipTest('Asar required for current guard regression')
    labels=data['labels'].copy()
    with tempfile.TemporaryDirectory() as temp:
        folder=Path(temp);rom=folder/'sparse.sfc';rom.write_bytes(compiled)
        driver=folder/'driver.asm'
        driver.write_text('lorom\n'+
            '!LYRA_CURRENT_MODE = 1\n!LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED = 1\n'+
            '!LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND = 1\n!Func02A9C4 = 1\n'+
            '!LYRA_PRIVATE_PILOT_INGRESS_ENABLED = 1\n'+
            '!REGIONAL_CHECKPOINTS_ENABLED = 1\n!REGIONAL_CHECKPOINTS_BOUND = 1\n'+
            'OverworldScreenIDChange = $02A634\nCheckpoint_EnterHome = $34FC54\n'+
            ''.join(f'{name} = ${labels[name]:06X}\n' for name in
                    ('LyraPilot_SubNativeAllowed','LyraPilot_SubNativeNoOverlay'))+
            f'org ${labels["Lyra_PrivatePilotCanScroll"]:06X}\n'+
            f'incsrc "{ROOT / "Overworld/lyra_private_pilot.asm"}"\n')
        run=subprocess.run([asar,'--no-title-check','--fix-checksum=off','--symbols=wla',
                            str(driver),str(rom)],capture_output=True,text=True,timeout=20)
        if run.returncode:raise AssertionError(run.stdout+run.stderr)
        compiled=bytearray(rom.read_bytes())
        emitted=L._labels(rom.with_suffix('.sym').read_bytes())
    labels.update({name:emitted[name] for name in labels if name in emitted})
    site=L.A.pc(labels['LyraPilot_SubDispatchSite'])
    compiled[site:site+4]=b'\x5C'+labels['Lyra_PrivatePilotSubGate'].to_bytes(3,'little')
    reviewed=copy.deepcopy(data['reviewed'])
    reviewed['source_rom_sha256']=L.R.sha(source)
    reviewed['guard_source_sha256']=L.R.sha((ROOT/'Overworld/lyra_private_pilot.asm').read_bytes())
    reviewed['code_snes']=[labels['Lyra_PrivatePilotCanScroll'],labels['Lyra_PrivatePilotSubGate_End']]
    lo,hi=reviewed['code_snes'];reviewed['code_sha256']=L.R.sha(compiled[L.A.pc(lo):L.A.pc(lo)+hi-lo])
    lo,hi=reviewed['overlay_host_snes'];reviewed['overlay_host_sha256']=L.R.sha(compiled[L.A.pc(lo):L.A.pc(lo)+hi-lo])
    return bytes(source),bytes(compiled),labels,reviewed


def actual_preview_fixture(*,combined=False):
    """Actual emitted windows in a sparse diagnostic image, never a ROM grant.

    Combined mode adds the existing artificial core-consumer fixture solely
    to exercise the common inspection path. It is not actual core assembly.
    """
    source,actual,labels,reviewed=assembled_preview_guard_fixture()
    labels=labels.copy()
    if combined:
        compiled,symbols=consumer_fixture(source,0xE0B000)
        end=labels['Lyra_PrivatePilotSubGate_End']
        symbols=symbols.replace(b'E0:B800 Lyra_CurrentNativeCodeEnd',
            f'{end>>16:02X}:{end&65535:04X} Lyra_CurrentNativeCodeEnd'.encode())
        compiled=bytearray(compiled)
        # Preserve the original sparse fixture's host/Home spans and use the
        # real newly assembled guard range and fixed hooks.
        windows=json.loads((ROOT/'Tests/fixtures/lyra_actual_preview_guard_windows.json').read_bytes())['compiled_windows']
        for row in windows:
            lo=row['snes'];size=len(bytes.fromhex(row['payload_hex']))
            if lo==reviewed['code_snes'][0]:size=reviewed['code_snes'][1]-lo
            pc=L.A.pc(lo);compiled[pc:pc+size]=actual[pc:pc+size]
    else:compiled,symbols=bytearray(actual),b'[labels]\n'
    if combined:
        # Replace only this artificial core stub with its actual emitted host.
        replaced={'LyraHost_Overworld_ReloadSubscreenOverlay_Interupt',
                  'LyraHost_Overworld_ReloadSubscreenOverlay_Interupt_End'}
        symbols=b''.join(row for row in symbols.splitlines(keepends=True)
                         if row.decode().strip().split(' ')[-1] not in replaced)
    if combined:
        host=L._labels(symbols)['LyraHost_OverworldHandleTransitions'];call=host+0x40;blocked=host+0x20
        helper=labels['Lyra_PrivatePilotCanScroll']
        raw=b'\x22'+helper.to_bytes(3,'little')+bytes([0xB0,(blocked-call-6)&255])
        compiled[L.A.pc(call):L.A.pc(call)+6]=raw
        labels.update(LyraCall_PrivatePilotBoundary=call,LyraPilot_BoundaryBlocked=blocked)
    symbols+=(''.join(f'{a>>16:02X}:{a&65535:04X} {n}\n' for n,a in labels.items())).encode()
    return bytes(compiled),symbols,dict(source=source,reviewed=copy.deepcopy(reviewed),
                                      mode='seeded_checkpoint_preview')


class SeededCheckpointPreviewConsumerTest(unittest.TestCase):
    @staticmethod
    def inspect(rom,symbols,request):
        return L.inspect_seeded_checkpoint_preview(rom,symbols,**request)

    def test_cross_bank_near_returns_execute_native_thunk_and_old_rts_control_fails(self):
        runner=os.environ.get('OOS_CPU_RUNNER')
        if not runner:self.skipTest('Set OOS_CPU_RUNNER for emitted 65816 return regression')
        rom,symbols,_=actual_preview_fixture();labels=L._labels(symbols)
        old=json.loads((ROOT/'Tests/fixtures/lyra_actual_preview_guard_windows.json').read_bytes())
        old_code=next(bytes.fromhex(r['payload_hex']) for r in old['compiled_windows']
                      if r['snes']==old['labels']['Lyra_PrivatePilotCanScroll'])
        cases=(('EntryBlocked',labels['Lyra_PrivatePilotEntryGate_End']-4,
                old['labels']['Lyra_PrivatePilotEntryGate_End']-1),
               ('FullAllowed',labels['Lyra_PrivatePilotFullNearGate']+20,
                old['labels']['Lyra_PrivatePilotFullNearGate']+20),
               ('FullBlocked',labels['Lyra_PrivatePilotFullNearGate_End']-4,
                old['labels']['Lyra_PrivatePilotFullNearGate_End']-1))
        with tempfile.TemporaryDirectory() as folder:
            for name,exit_at,old_at in cases:
                self.assertEqual(old_code[old_at-old['labels']['Lyra_PrivatePilotCanScroll']],0x60)
                self.assertEqual(rom[L.A.pc(exit_at):L.A.pc(exit_at)+4],bytes.fromhex('5cc4ed02'))
                for stage in ('old_rts','native_rts','complete'):
                    control=stage=='old_rts'
                    image=bytearray(rom)
                    # Test-only caller: PEA models the REAL JSR($83B9,X)'s
                    # saved83C5; the runner already supplies its outer JSL.
                    # Native0283C6 RTL is the unchanged actual continuation.
                    image[L.A.pc(0x029000):L.A.pc(0x029000)+7]=(
                        bytes.fromhex('f4c5835c')+exit_at.to_bytes(3,'little'))
                    if control:image[L.A.pc(exit_at)]=0x60 # immutable old emitted opcode
                    path=Path(folder)/'diagnostic.sfc';path.write_bytes(image)
                    regs=dict(a=0xABCD,x=0x67,y=0x45,p=0x31,db=0,d=0,sp=0x1FFF)
                    request=dict(entry=0x029000,reset_ram=True,registers=regs,
                        writes=[],reads=[dict(address=0x7E1FF0,length=16)],
                        trace_writes=True,max_steps={'old_rts':4,'native_rts':5,'complete':20}[stage])
                    run=subprocess.run([runner,str(path)],input=json.dumps(request)+'\n',
                        text=True,capture_output=True,timeout=10)
                    self.assertEqual(run.returncode,0,run.stderr)
                    result=json.loads(run.stdout);cpu=result['registers']
                    with self.subTest(exit=name,stage=stage):
                        self.assertFalse(result.get('stub_calls'));self.assertFalse(result.get('mmio_writes'))
                        self.assertEqual(result['returned'],stage=='complete')
                        for key in ('a','x','y','p','db','d'):self.assertEqual(cpu[key],regs[key],key)
                        if control:
                            # RTS pops ONLY the address; PBR remains E0.
                            self.assertEqual((cpu['pb']<<16)|cpu['pc'],0xE083C6)
                            self.assertEqual(cpu['sp'],regs['sp']-3)
                        elif stage=='native_rts':
                            self.assertEqual((cpu['pb']<<16)|cpu['pc'],0x0283C6)
                            self.assertEqual(cpu['sp'],regs['sp']-3)
                        else:
                            # JML02EDC4; RTS reaches0283C6; its RTL consumes
                            # exactly the caller's long frame, no extra byte.
                            self.assertEqual(cpu['sp'],regs['sp'])
                            self.assertEqual(result['steps'],6) # includes runner's initial JSL
                        self.assertEqual(result['reads'][0]['bytes'][11:13],[0xC5,0x83])
                        for write in result.get('writes',[]):
                            at=write['address']
                            if at>>16&127<64 and at&65535<8192:at=0x7E0000|(at&65535)
                            self.assertTrue(0x7E1FF0<=at<0x7E2000 or 0x7F8000<=at<0x7F8004)

    def test_actual_guard_windows_have_explicit_scope_and_no_readiness_authority(self):
        rom,symbols,request=actual_preview_fixture();proof=self.inspect(rom,symbols,request)
        self.assertTrue(proof['guards_verified']);self.assertEqual(proof['home_bytes'],37)
        self.assertEqual(len(proof['transport_maps']),17);self.assertEqual(len(proof['credits_held']),13)
        self.assertIn('Warp/boat ingress',proof['held_routes'])
        for flag in ('current_core_inspected','allocation_granted','producer_enforcement_verified',
                     'ordinary_build_ready','runtime_admission','production_admission',
                     'native_gameplay_verified','save_reopen_verified'):
            self.assertIs(proof[flag],False,flag)

    def test_each_emitted_helper_byte_refuses_even_with_recomputed_code_hash(self):
        rom,symbols,request=actual_preview_fixture();lo,hi=request['reviewed']['code_snes'];pc=L.A.pc(lo)
        self.assertEqual(hi-lo,407)
        for offset in range(hi-lo):
            with self.subTest(offset=offset):
                changed=bytearray(rom);changed[pc+offset]^=1;pin=copy.deepcopy(request)
                pin['reviewed']['code_sha256']=L.R.sha(changed[pc:pc+hi-lo])
                with self.assertRaisesRegex(ValueError,'PRIVATE_PREVIEW_BYTES_CHANGED'):
                    self.inspect(bytes(changed),symbols,pin)

    def test_home_fixed_hooks_and_sub_dispatch_refuse_mutations(self):
        rom,symbols,request=actual_preview_fixture();labels=L._labels(symbols)
        sites=list(range(0x34FC54,0x34FC54+37))
        sites += [a+i for a in (0x0283C7,0x02B217,0x02EDB9,0x02A475) for i in range(4)]
        for name,length in (('LyraPilot_SubDispatchSite',8),('LyraPilot_SubNativeAllowed',6),
                            ('LyraPilot_SubNativeNoOverlay',17)):
            sites += list(range(labels[name],labels[name]+length))
        for at in sites:
            with self.subTest(snes=hex(at)):
                changed=bytearray(rom);changed[L.A.pc(at)]^=1;pin=copy.deepcopy(request)
                lo,hi=pin['reviewed']['overlay_host_snes']
                pin['reviewed']['overlay_host_sha256']=L.R.sha(changed[L.A.pc(lo):L.A.pc(lo)+hi-lo])
                with self.assertRaises(ValueError):self.inspect(bytes(changed),symbols,pin)

    def test_native_continuation_and_direction_source_cannot_be_rebound_to_changed_bytes(self):
        rom,symbols,request=actual_preview_fixture()
        for at in (0x0283B9,0x0283CB,0x02A479,0x02B21B,0x02A634,0x02B1F9,0x02EDC4):
            with self.subTest(snes=hex(at)):
                changed=bytearray(rom);changed[L.A.pc(at)]^=1
                source=bytearray(request['source']);source[L.A.pc(at)]^=1
                pin=copy.deepcopy(request);pin['source']=bytes(source)
                pin['reviewed']['source_rom_sha256']=L.R.sha(source)
                with self.assertRaises(ValueError):self.inspect(bytes(changed),symbols,pin)

    def test_transport_destinations_refuse_tail_invalid_and_high_word_aliases(self):
        rom,symbols,request=actual_preview_fixture()
        for target in (0xA0,0xA1,0xBF,0xC0,0x100,0xFFFF):
            with self.subTest(target=hex(target)):
                at=L.A.pc(0x02EAE5);changed=bytearray(rom);source=bytearray(request['source'])
                changed[at:at+2]=source[at:at+2]=target.to_bytes(2,'little')
                pin=copy.deepcopy(request);pin['source']=bytes(source)
                pin['reviewed']['source_rom_sha256']=L.R.sha(source)
                with self.assertRaises(ValueError):self.inspect(bytes(changed),symbols,pin)

    def test_missing_redirected_and_conflicting_symbols_refuse(self):
        rom,symbols,request=actual_preview_fixture()
        for name in ('LyraCall_PrivatePilotColdResume','LyraPilot_FullLoadBlocked',
                     'LyraPilot_SubDispatchSite','Checkpoint_EnterHome'):
            line=next(row for row in symbols.splitlines(keepends=True) if row.rstrip().endswith(b' '+name.encode()))
            for altered in (symbols.replace(line,b''),symbols.replace(line,b'E0:C010 '+name.encode()+b'\n'),
                            symbols+b'E0:C010 '+name.encode()+b'\n'):
                with self.subTest(name=name),self.assertRaises(ValueError):self.inspect(rom,altered,request)

    def test_explicit_mode_and_complete_current_review_binding_required(self):
        rom,symbols,request=actual_preview_fixture()
        for change in ({'mode':True},{'mode':'ordinary'},{'reviewed':{}},
                       {'reviewed':dict(request['reviewed'],scope='full32')}):
            with self.assertRaises(ValueError):self.inspect(rom,symbols,dict(request,**change))
        for name in ('source_rom_sha256','guard_source_sha256','code_sha256','overlay_host_sha256','home_sha256'):
            pin=copy.deepcopy(request);pin['reviewed'][name]='0'*64
            with self.subTest(name=name),self.assertRaises(ValueError):self.inspect(rom,symbols,pin)
        for value in (True,{},dict(request,extra=True)):
            with self.assertRaisesRegex(ValueError,'EXPLICIT_REQUEST_REQUIRED'):
                L.inspect_current_consumers(rom,symbols,checkpoint_preview=value)

    def test_combined_opt_in_retains_core_and_default_remains_broad(self):
        rom,symbols,request=actual_preview_fixture(combined=True)
        result=L.inspect_current_consumers(rom,symbols,checkpoint_preview=request)
        self.assertEqual(result['kind'],L.PREVIEW_CONSUMER_KIND)
        self.assertTrue(result['current_core_inspected']);self.assertIn('private_pilot_boundary',result)
        self.assertGreater(len(result['source_calls']),20);self.assertGreater(len(result['fixed_hooks']),20)
        self.assertFalse(result['ordinary_build_ready']);self.assertFalse(result['broad_six_role_qualification'])
        with self.assertRaisesRegex(ValueError,'PRIVATE_PILOT_INGRESS_UNBOUND'):
            L.inspect_current_consumers(rom,symbols)
        changed=bytearray(rom);changed[L.A.pc(0x02F59D)]^=1
        with self.assertRaisesRegex(ValueError,'Current active hook differs'):
            L.inspect_current_consumers(bytes(changed),symbols,checkpoint_preview=request)


if __name__=='__main__':unittest.main()
