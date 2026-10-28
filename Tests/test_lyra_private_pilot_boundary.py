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
        instructions=statements(helper,dict(base,LYRA_PRIVATE_PILOT_BOUNDARIES_ENABLED=1,LYRA_PRIVATE_PILOT_BOUNDARIES_BOUND=1))
        self.assertFalse(any(line.split()[0].upper() in ('STA','STA.B','STA.W','STA.L','STZ','STZ.W','STZ.B') for line in instructions))
        self.assertIn('ADC.l OverworldScreenIDChange, X',instructions)
        # Exact private pair source checks and stack-only ABI; execution remains unrun.
        for line in ('CPY.w #$0000','CPY.w #$0002','CMP.w #$0040','CMP.w #$0042','CMP.w #$0140'):
            self.assertIn(line,instructions)

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


if __name__=='__main__':unittest.main()
