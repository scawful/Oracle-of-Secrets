import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from types import SimpleNamespace
sys.path[:0] = [str(Path(__file__).resolve().parents[1]), str(Path(__file__).resolve().parents[2]/'Build')]
from allocation_contracts import (AllocationError, ownership_conflicts, source_evidence,
    read_ledger, table_checks, emission_crossings, cart_checks, validate_draft,
    valid_area, verify_receipt, digest, read_symbols)
from build_receipt import source_snapshot, profile
from generate_hack_manifest import load_exact_hooks, ManifestGenerationError

ROOT = Path(__file__).resolve().parents[3]


def claim(id, base, size, **kwargs):
    return dict(id=id, owner=id, space='wram', base=base, size=size, status='shared', condition={}, lifetime='fixture phase', reset='fixture reset', save='volatile', provenance=['proof'], **kwargs)


def ledger(*claims):
    return dict(schema_version=1, allocation_available=False, sources={'proof': {'source_set':'shared','path':'proof.txt','sha256':'0'*64}}, claims=list(claims), lifetime_aliases=[])


class OwnershipTests(unittest.TestCase):
    def test_touching_exclusive_ends_pass(self):
        self.assertEqual(ownership_conflicts(ledger(claim('a',0x7E1000,2),claim('b',0x7E1002,2)),{})[0],[])

    def test_unrelated_live_overlap_fails(self):
        self.assertEqual(len(ownership_conflicts(ledger(claim('a',0x7E1000,4),claim('b',0x7E1002,2)),{})[0]),1)

    def test_contained_field_passes(self):
        self.assertEqual(ownership_conflicts(ledger(claim('block',0x7E1000,6,container=True),claim('field',0x7E1005,1,contained_by='block')),{})[0],[])

    def test_false_containment_fails(self):
        with self.assertRaisesRegex(AllocationError,'containment'):
            ownership_conflicts(ledger(claim('block',0x7E1000,6,container=True),claim('field',0x7E1005,2,contained_by='block')), {})

    def test_named_alias_does_not_create_second_owner(self):
        c=claim('canonical',0x7E1000,1);c['aliases']=['old_name','new_name']
        self.assertEqual(ownership_conflicts(ledger(c),{})[0],[])

    def test_declared_disjoint_lifetime_alias_passes(self):
        data=ledger(claim('a',0x7E1000,8),claim('b',0x7E1000,8))
        data['lifetime_aliases']=[dict(owners=['a','b'],phases={'a':['initialization'],'b':['gameplay']},proof_sources=['proof'])]
        self.assertEqual(ownership_conflicts(data,{})[0],[])

    def test_unproven_or_overlapping_lifetime_alias_fails(self):
        for phases,proof in [({'a':['gameplay'],'b':['gameplay']},['proof']),({'a':['a'],'b':['b']},[])]:
            with self.subTest(phases=phases,proof=proof), self.assertRaises(AllocationError):
                data=ledger(claim('a',0x7E1000,8),claim('b',0x7E1000,8));data['lifetime_aliases']=[dict(owners=['a','b'],phases=phases,proof_sources=proof)];ownership_conflicts(data,{})

    def test_cart_minish_conflict_is_conditional(self):
        c=claim('minish',0x7E0766,2);c['condition']={'MINISH':1}
        data=ledger(claim('cart',0x7E0728,64),c)
        self.assertEqual(ownership_conflicts(data,{'MINISH':0})[0],[])
        self.assertEqual(len(ownership_conflicts(data,{'MINISH':1})[0]),1)
        with self.assertRaisesRegex(AllocationError,'unknown feature'):ownership_conflicts(data,{})

    def test_music160_passes_and_192_fails_fishing(self):
        music=claim('music',0x7F5B00,160);fish=claim('fishing',0x7F5BA0,4)
        larger=claim('larger',0x7F5B00,192,replaces='music');larger['status']='proposed'
        data=ledger(music,fish,larger)
        self.assertEqual(ownership_conflicts(data,{},proposed=False)[0],[])
        conflicts=ownership_conflicts(data,{},proposed=True)[0]
        self.assertEqual(conflicts[0]['owners'],['fishing','larger'])
        self.assertEqual(conflicts[0]['classification'],'proposed_conflict')

    def test_pending_claim_is_not_shared_or_free(self):
        a=claim('pending',0x7E1000,1);a['status']='pending'
        self.assertEqual(ownership_conflicts(ledger(a,claim('shared',0x7E1000,1)),{})[0],[])
        self.assertEqual(len(ownership_conflicts(ledger(a,claim('shared',0x7E1000,1)),{},pending=True)[0]),1)

    def test_save_buffer_and_wram_conflict_physically(self):
        a=claim('saved',0x7EF300,1);a['space']='save_buffer'
        self.assertEqual(len(ownership_conflicts(ledger(a,claim('ram',0x7EF300,1)),{})[0]),1)

    def test_schema_rejects_unknown_space_size_and_ownership(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'ledger.json'
            for key,value in [('space','sram_bus_guess'),('size',0),('status','free'),('base',True)]:
                data=ledger(claim('a',0x7E1000,1));data['claims'][0][key]=value;path.write_text(json.dumps(data))
                with self.subTest(key=key),self.assertRaises(AllocationError):read_ledger(path)

    def test_missing_stale_and_wrong_bound_source_fail(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);path=root/'proof.txt';path.write_text('Owner = $7E1000\n')
            data=ledger(claim('a',0x7E1000,1));data['sources']['proof']['sha256']=digest(path)
            data['claims'][0]['binding']={'source':'proof','symbol':'Owner'}
            self.assertTrue(source_evidence(data,{'shared':root}))
            with self.assertRaisesRegex(AllocationError,'Missing required'):source_evidence(data,{})
            data['claims'][0]['base']=0x7E1001
            with self.assertRaisesRegex(AllocationError,'disagrees'):source_evidence(data,{'shared':root})
            path.write_text('Owner = $7E1001\n')
            with self.assertRaisesRegex(AllocationError,'Stale source'):source_evidence(data,{'shared':root})
            path.unlink()
            with self.assertRaisesRegex(AllocationError,'Missing/invalid'):source_evidence(data,{'shared':root})


class TableTests(unittest.TestCase):
    def test_wla_labels_exclude_address_to_line_records(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory)/'labels.sym'
            path.write_text('[labels]\n28:8000 BG\n28:8000 BG\n[addr-to-line mapping]\n28:8000 0000:00000001\n28:8002 0000:00000001\n')
            self.assertEqual(read_symbols(path),{'BG':0x288000})
            path.write_text('[labels]\n28:8000 BG\n28:8002 BG\n')
            with self.assertRaisesRegex(AllocationError,'Conflicting'):read_symbols(path)
            path.write_text('[addr-to-line mapping]\n28:8000 0000:00000001\n')
            with self.assertRaisesRegex(AllocationError,'Missing WLA'):read_symbols(path)

    def table(self,**changes):
        return dict(dict(id='bg',address=0x288000,boundary=0x288140,count=160,stride=2,symbol='BG',source='Overworld/ZSCustomOverworld.asm',payload='data'),**changes)

    def test_160_table_exact_boundary(self):
        self.assertEqual(table_checks([self.table()],{'BG':0x288000},0x200000)[0]['end'],0x140140)

    def test_192_in_place_and_truncated_rom_fail(self):
        for table,size in [(self.table(count=192),0x200000),(self.table(),0x140100),(self.table(boundary=0x28813F),0x200000)]:
            with self.subTest(table=table,size=size),self.assertRaises(AllocationError):table_checks([table],{'BG':0x288000},size)

    def test_missing_or_stale_symbols_fail(self):
        for symbols in ({},{'BG':0x288002}):
            with self.assertRaises(AllocationError):table_checks([self.table()],symbols,0x200000)

    def test_same_source_table_overlap_fails(self):
        with self.assertRaisesRegex(AllocationError,'Tables overlap'):
            table_checks([self.table(),self.table(id='next',address=0x288100,boundary=0x288300,symbol=None)],{'BG':0x288000},0x200000)

    def test_bank_relative_crossing_fails(self):
        with self.assertRaises(AllocationError):table_checks([self.table(address=0x28FF00,boundary=0x298140,symbol=None)],{},0x200000)

    def span(self,start,end,kind='data',source='Overworld/ZSCustomOverworld.asm:12'):
        return SimpleNamespace(start_pc=start,end_pc=end,hook=SimpleNamespace(kind=kind,source=source))

    def test_exact_contained_and_touching_spans_pass(self):
        ranges=table_checks([self.table()],{'BG':0x288000},0x200000)
        emission_crossings([self.span(0x140000,0x140002),self.span(0x14013E,0x140140),self.span(0x140140,0x140142)],ranges)

    def test_exact_start_before_boundary_crossing_fails(self):
        with self.assertRaisesRegex(AllocationError,'crosses'):
            emission_crossings([self.span(0x13FFFE,0x140002)],table_checks([self.table()],{'BG':0x288000},0x200000))

    def test_wrong_payload_and_owner_fail(self):
        ranges=table_checks([self.table()],{'BG':0x288000},0x200000)
        for kind,source in [('code','Overworld/ZSCustomOverworld.asm'),('data','Other.asm')]:
            with self.assertRaisesRegex(AllocationError,'Wrong source/payload'):emission_crossings([self.span(0x140000,0x140002,kind,source)],ranges)

    def test_exact_hook_reader_rejects_stale_or_missing_evidence(self):
        with tempfile.TemporaryDirectory() as directory:
            path=Path(directory);rom=path/'rom.sfc';rom.write_bytes(bytes(0x8000));hooks=path/'hooks.json'
            with self.assertRaises(ManifestGenerationError):load_exact_hooks(hooks,rom)
            hooks.write_text(json.dumps(dict(version=1,rom=dict(sha256='0'*64,size=0x8000),hooks=[])))
            with self.assertRaisesRegex(ManifestGenerationError,'different ROM'):load_exact_hooks(hooks,rom)

    def test_cart_tables_and_reset_failure_are_distinct(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory);(root/'Util').mkdir();(root/'Util/macros.asm').write_text('!ENABLE_MINECART_PLANNED_TRACK_TABLE = 1\n')
            config=dict(count=32,stride=2,source='tracks.asm',symbols_prefix='Cart_',reset_symbol='Reset')
            text='';symbols={'Reset':0x008000}
            for i,name in enumerate(('Rooms','X','Y')):
                text+=f'.TrackStarting{name}\ndw '+','.join(['$0000']*32)+f'\n.TrackStarting{name}End\n'
                symbols['Cart_'+name]=0x018000+i*64;symbols['Cart_'+name+'End']=0x018040+i*64
            (root/'tracks.asm').write_text(text)
            broken=bytes.fromhex('22 68 FA 0D A9 00 8D E8 07 A2 41 CA 9D 28 07 9D 68 07 9D A8 07 E0 00 D0 F2 6B')
            result=cart_checks(root,config,symbols,broken)
            self.assertFalse(result['reset_bounds_passed']);self.assertEqual(result['reset_bytes_per_array'],65)
            corrected=bytearray(broken);corrected[10]=64
            self.assertTrue(cart_checks(root,config,symbols,corrected)['reset_bounds_passed'])
            (root/'tracks.asm').write_text(text.replace('$0000,','',1))
            with self.assertRaisesRegex(AllocationError,'invalid count'):cart_checks(root,config,symbols,broken)

    def test_changed_reset_encoding_needs_new_proof(self):
        # Exact production reset is tested above; an unknown pattern must not pass.
        data=read_ledger(ROOT/'Config/allocation_ownership.json')
        with self.assertRaises(AllocationError):cart_checks(ROOT,data['cart'],{},b'')


class DraftTests(unittest.TestCase):
    def draft(self):return json.loads((ROOT/'Config/overworld_layout_192.draft.json').read_text())

    def test_draft_is_valid_but_cannot_activate(self):
        self.assertEqual(validate_draft(self.draft())['status'],'valid_draft_not_activation_ready')
        with self.assertRaisesRegex(AllocationError,'activation refused'):validate_draft(self.draft(),require_ready=True)

    def test_namespace_boundaries(self):
        for area in (0,0x3F,0x40,0x7F,0x80,0x9F,0xA0,0xBF):self.assertTrue(valid_area(area))
        for area in (-1,0xC0,0xFF,True,'160'):self.assertFalse(valid_area(area))

    def test_invalid_contracts_fail(self):
        mutations=[lambda c:c.update(area_count=160),lambda c:c.update(sea_ids=[128,159]),lambda c:c['roles'].update(overlay_storage_preserve=[160,191]),lambda c:c.update(sprite_phase_stride=320),lambda c:c['tables'][0].update(count=160),lambda c:c['tables'][0].update(address=0x308000),lambda c:c['events'].update(special_base=0x7EF320),lambda c:c['music'].update(cache_base=0x7F5B00),lambda c:c['legacy_detection'].update(never_fallback_on_invalid_expanded=False)]
        for mutate in mutations:
            c=self.draft();mutate(c)
            with self.subTest(contract=c),self.assertRaises(AllocationError):validate_draft(c)

    def test_table_identity_stride_and_addressing_cannot_drift(self):
        for changes in [dict(id='unknown'),dict(stride=1),dict(addressing='anywhere')]:
            c=self.draft();c['tables'][0].update(changes)
            with self.subTest(changes=changes),self.assertRaises(AllocationError):validate_draft(c)
        tables=read_ledger(ROOT/'Config/allocation_ownership.json')['tables']
        validate_draft(self.draft(),current_tables=tables)
        tables[0]['address']+=2
        with self.assertRaisesRegex(AllocationError,'layout disagrees'):validate_draft(self.draft(),current_tables=tables)

    def test_unresolved_allocations_and_legacy_guard_cannot_be_filled_silently(self):
        for field,key,value in [('sprites','bank',0x28),('special_sprite_gfx','address',0x288000),('map_streams','pointer_width',2),('menu_names','count',160),('tile_definitions','tile16_capacity',4096),('legacy_detection','absent_expanded_signature','guess_192'),('four_cell_proof','activation_allowed',True)]:
            c=self.draft();c[field][key]=value
            with self.subTest(field=field,key=key),self.assertRaises(AllocationError):validate_draft(c)


class ReceiptTests(unittest.TestCase):
    def test_success_then_stale_rom_symbols_source_or_missing_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)/'src';root.mkdir();(root/'Oracle_main.asm').write_text('; fixture\n')
            rom=root/'rom.sfc';rom.write_bytes(b'ROM');sym=root/'rom.sym';sym.write_text('[labels]\n00:8000 Start\n')
            path=Path(directory)/'receipt.json'
            data=dict(schema_version=1,state='completed_with_gaps',root=str(root),finish={'exit_code':0},checks=[dict(name='assembly',status='passed',required=True)],snapshots={'pre_assembly':source_snapshot(root,path)},initial_profile=profile(root),artifacts={key:dict(sha256=digest(f),size=f.stat().st_size) for key,f in [('output_rom',rom),('symbols',sym)]})
            path.write_text(json.dumps(data));self.assertEqual(verify_receipt(path,root,rom,sym),{})
            for f in (rom,sym,root/'Oracle_main.asm'):
                saved=f.read_bytes();f.write_bytes(saved+b'changed')
                with self.subTest(path=f),self.assertRaises(AllocationError):verify_receipt(path,root,rom,sym)
                f.write_bytes(saved)
            data['snapshots']={};path.write_text(json.dumps(data))
            with self.assertRaisesRegex(AllocationError,'source evidence'):verify_receipt(path,root,rom,sym)
