#!/usr/bin/env python3
"""ROM-free vectors and real build-wrapper refusal tests for source sheets."""
from pathlib import Path
import hashlib
import importlib.util
import json
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import zlib

ROOT = Path(__file__).resolve().parents[3]
GEN = ROOT/'Scripts/Generate'
sys.path.insert(0, str(GEN))
import lz2
import sheet_codec as codec
import sheet_overrides as sheets
from sheet_table import pc, ptr, TBL_BANK, TBL_HIGH, TBL_LOW


def png(indices, filter_kind=0, mode=3):
    def chunk(kind, data):
        return struct.pack('>I', len(data))+kind+data+struct.pack('>I', zlib.crc32(kind+data))
    def paeth(a,b,c):
        v=a+b-c; d=(abs(v-a),abs(v-b),abs(v-c)); return (a,b,c)[d.index(min(d))]
    rows=[]; prior=bytes(128)
    for row in indices:
        encoded=bytearray()
        for x, value in enumerate(row):
            left=row[x-1] if x else 0; up=prior[x]; corner=prior[x-1] if x else 0
            prediction=(0,left,up,(left+up)//2,paeth(left,up,corner))[filter_kind]
            encoded.append((value-prediction)&255)
        rows.append(bytes([filter_kind])+encoded); prior=row
    return (b'\x89PNG\r\n\x1a\n'+chunk(b'IHDR',struct.pack('>IIBBBBB',128,32,8,mode,0,0,0))+
            chunk(b'PLTE',bytes(24))+chunk(b'IDAT',zlib.compress(b''.join(rows)))+chunk(b'IEND',b''))


class SourceSheets(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup);self.root=Path(self.temp.name)
        self.raw=bytes(range(256))*6
        self.rom=bytearray(0x200000)
        stream=lz2.stored(self.raw);self.rom[0x10000:0x10000+len(stream)]=stream
        for g in range(223):
            for table,value in ((TBL_BANK,0x82),(TBL_HIGH,0x80),(TBL_LOW,0)):
                self.rom[pc(table)+g]=value
        self.base=self.root/'base.sfc';self.base.write_bytes(self.rom)
        self.spec_path=self.root/'spec.json'
        self.spec=dict(schema_version=1,start='0x40D000',capacity=12288,encoding='lz2',sheets=[dict(
            sprite_sheet='0x64',source='sheet.txt',base_sha256=hashlib.sha256(self.raw).hexdigest(),identity=True,why='identity')])
        (self.root/'sheet.txt').write_text(codec.grid_to_text(codec.sheet_to_grid(self.raw)))
        self.write_spec()

    def write_spec(self):
        self.spec_path.write_text(json.dumps(self.spec))

    def test_native_command_vectors_and_overlapping_copy(self):
        vectors=[(b'\x02abc\xff',b'abc'),(b'\x23X\xff',b'XXXX'),
                 (b'\x44ab\xff',b'ababa'),(b'\x63\xfe\xff',bytes([254,255,0,1])),
                 (b'\x01ab\x85\x00\x00\xff',b'abababab'),
                 (b'\xe4\x20Z\xff',b'Z'*33)]
        for encoded,raw in vectors:
            with self.subTest(encoded=encoded.hex()):self.assertEqual(lz2.decompress(encoded),(raw,len(encoded)))

    def test_deterministic_encoder_roundtrips(self):
        for raw in (b'',bytes(1536),self.raw,b'ab'*768,bytes((i*73+19)%256 for i in range(1536))):
            for encoder in (lz2.stored,lz2.compress):
                encoded=encoder(raw);self.assertEqual(encoded,encoder(raw));self.assertEqual(lz2.decompress(encoded),(raw,len(encoded)))

    def test_malformed_lz2_and_output_limit_refused(self):
        for stream in (b'',b'\x05abc',b'\xe0',b'\x40a',b'\x80\x00\x00\xff',b'\xa0\x00\x00\xff'):
            with self.subTest(stream=stream.hex()),self.assertRaises(ValueError):lz2.decompress(stream)
        with self.assertRaisesRegex(ValueError,'limit'):lz2.decompress(b'\x3fX\xff',max_output=31)

    def test_planar_tile_golden_and_all_tile_positions(self):
        grid=[[0]*128 for _ in range(32)]
        grid[0][0]=1;grid[0][1]=2;grid[0][2]=4;grid[31][127]=7
        raw=codec.grid_to_sheet(grid)
        self.assertEqual((raw[0],raw[1],raw[16]),(0x80,0x40,0x20))
        self.assertEqual((raw[-10],raw[-9],raw[-1]),(1,1,1))
        self.assertEqual(codec.sheet_to_grid(raw),grid)

    def test_invalid_dimensions_and_indices_refused(self):
        with self.assertRaises(ValueError):codec.grid_to_sheet([[0]])
        with self.assertRaises(ValueError):codec.sheet_to_grid(bytes(1535))
        with self.assertRaises(ValueError):codec.text_to_grid(('8'*128+'\n')*32)

    def test_indexed_png_all_five_native_filters(self):
        expected=[[(x+3*y)%8 for x in range(128)] for y in range(32)]
        for kind in range(5):
            image=self.root/f'{kind}.png';image.write_bytes(png(expected,kind))
            self.assertEqual(codec.png_to_grid(image),expected)

    def test_png_crc_mode_and_palette_indices_refused(self):
        grid=[[0]*128 for _ in range(32)];path=self.root/'bad.png'
        bad=bytearray(png(grid));bad[30]^=1;path.write_bytes(bad)
        with self.assertRaisesRegex(ValueError,'CRC'):codec.png_to_grid(path)
        path.write_bytes(png(grid,mode=2))
        with self.assertRaisesRegex(ValueError,'indexed'):codec.png_to_grid(path)
        grid[0][0]=8;path.write_bytes(png(grid))
        with self.assertRaisesRegex(ValueError,'indices'):codec.png_to_grid(path)

    def test_identity_pointer_decode_and_exact_simulated_byte_boundary(self):
        _,items=sheets.build(self.spec_path,self.base)
        self.assertEqual(len(items),1);item=items[0];self.assertEqual(item['raw'],self.raw)
        patched=bytearray(self.rom)+bytearray(0xD13A)
        before=bytes(patched);start=pc(item['snes']);patched[start:start+len(item['stream'])]=item['stream']
        address=item['snes']|0x800000
        for table,value in ((TBL_BANK,address>>16),(TBL_HIGH,(address>>8)&255),(TBL_LOW,address&255)):
            patched[pc(table)+0xD7]=value
        self.assertEqual(ptr(patched,0xD7),0xC0D000)
        self.assertEqual(lz2.decompress(patched,pc(ptr(patched,0xD7)),max_output=1536)[0],self.raw)
        allowed=set(range(start,start+len(item['stream'])))|{pc(t)+0xD7 for t in (TBL_BANK,TBL_HIGH,TBL_LOW)}
        self.assertTrue(all(i in allowed for i,(a,b) in enumerate(zip(before,patched)) if a!=b))
        self.assertEqual(len(patched),len(before))

    def test_base_sheet_change_and_short_hash_refused(self):
        self.rom[0x10002]^=1;self.base.write_bytes(self.rom)
        with self.assertRaisesRegex(ValueError,'base sheet changed'):sheets.build(self.spec_path,self.base)
        self.spec['sheets'][0]['base_sha256']=self.spec['sheets'][0]['base_sha256'][:12];self.write_spec()
        with self.assertRaisesRegex(ValueError,'full lowercase'):sheets.build(self.spec_path,self.base)

    def test_identity_pixel_change_refused(self):
        (self.root/'sheet.txt').write_text(('.'*128+'\n')*32)
        with self.assertRaisesRegex(ValueError,'identity override'):sheets.build(self.spec_path,self.base)

    def test_duplicate_unsupported_sheet_and_source_escape_refused(self):
        original=dict(self.spec['sheets'][0])
        self.spec['sheets'].append(dict(original));self.write_spec()
        with self.assertRaisesRegex(ValueError,'duplicate'):sheets.build(self.spec_path,self.base)
        for value in ('0x0B','0x67'):
            self.spec['sheets']=[dict(original,sprite_sheet=value)];self.write_spec()
            with self.assertRaisesRegex(ValueError,'compressed 3bpp'):sheets.build(self.spec_path,self.base)
        self.spec['sheets']=[dict(original,source='../outside.png')];self.write_spec()
        with self.assertRaisesRegex(ValueError,'inside'):sheets.build(self.spec_path,self.base)

    def test_allocation_and_bank_overflow_refused(self):
        self.spec['start']='0x428000';self.write_spec()
        with self.assertRaisesRegex(ValueError,'audited'):sheets.build(self.spec_path,self.base)
        self.spec['start']='0x40D000';self.spec['encoding']='stored'
        self.spec['sheets']=[dict(self.spec['sheets'][0],sprite_sheet=hex(s)) for s in range(0x60,0x68) if s<=0x66]
        # Seven streams fit, an eighth unique compressed-3bpp sheet must refuse.
        self.spec['sheets'].append(dict(self.spec['sheets'][0],sprite_sheet='0x5F'));self.write_spec()
        with self.assertRaisesRegex(ValueError,'allocation is full'):sheets.build(self.spec_path,self.base)

    def reservation_root(self):
        (self.root/'Oracle_main.asm').write_text('incsrc "Overworld/world_map.asm"\n')
        (self.root/'Overworld/world_map').mkdir(parents=True)
        (self.root/'Overworld/world_map.asm').write_text('org $408000\n')
        for name,size in (('LwMapTileset.bin',4096),('LwMapGfx.bin',16384)):
            (self.root/'Overworld/world_map'/name).write_bytes(bytes(size))

    def test_occupied_expanded_tail_and_map_growth_refused(self):
        self.reservation_root();sheets.validate_reservation(self.root,self.rom)
        extended=self.rom+bytearray(0x8000);extended[0x205001]=1
        with self.assertRaisesRegex(ValueError,'occupied'):sheets.validate_reservation(self.root,extended)
        (self.root/'Overworld/world_map/LwMapGfx.bin').write_bytes(bytes(16385))
        with self.assertRaisesRegex(ValueError,'Light World map'):sheets.validate_reservation(self.root,self.rom)

    def test_other_reachable_bank40_owner_refused(self):
        self.reservation_root();(self.root/'Overworld/world_map.asm').write_text('org $408000\norg $C0E000\n')
        with self.assertRaisesRegex(ValueError,'another reachable'):sheets.validate_reservation(self.root,self.rom)

    def test_stream_start_before_allocation_crossing_into_it_refused(self):
        self.reservation_root();extended=self.rom+bytearray(0x10000)
        # One literal command begins before D000 and consumes bytes inside it.
        extended[0x204FFD:0x205001]=b'\x02\x00\x00\x00'
        extended[0x208001]=0xFF
        for table,value in ((TBL_BANK,0xC0),(TBL_HIGH,0xCF),(TBL_LOW,0xFD)):
            extended[pc(table)]=value
        # All bytes in the allocation are zero, but a live stream consumes it.
        self.assertEqual(set(extended[0x205000:0x208000]),{0})
        with self.assertRaisesRegex(ValueError,'overlaps'):sheets.validate_reservation(self.root,extended)

    def test_generation_failure_restores_complete_previous_files(self):
        out=self.root/'generated';files={Path('sheets/spr64.bin'):b'NEW_STREAM',Path('sheet_overrides.asm'):b'NEW_INCLUDE'}
        for name in files:
            (out/name).parent.mkdir(parents=True,exist_ok=True);(out/name).write_bytes(b'OLD_'+name.name.encode())
        before={name:(out/name).read_bytes() for name in files};replace=os.replace;calls=[]
        def fail_second(source,dest):
            calls.append(dest)
            if len(calls)==2:raise OSError('injected publication failure')
            return replace(source,dest)
        with mock.patch.object(sheets.os,'replace',side_effect=fail_second),self.assertRaisesRegex(OSError,'injected'):
            sheets.write_outputs(out,files,[self.base,self.spec_path])
        self.assertEqual({name:(out/name).read_bytes() for name in files},before)
        self.assertEqual(sorted(p.relative_to(out) for p in out.rglob('*') if p.is_file()),sorted(files))

    def test_generation_refuses_input_hardlink_alias(self):
        out=self.root/'generated';(out/'sheets').mkdir(parents=True)
        os.link(self.base,out/'sheets/spr64.bin')
        with self.assertRaisesRegex(ValueError,'aliases an input'):
            sheets.write_outputs(out,{Path('sheets/spr64.bin'):b'BAD'},[self.base])
        self.assertEqual(self.base.read_bytes(),self.rom)

    def test_check_mode_does_not_create_or_modify_outputs(self):
        output=self.root/'absent'
        result=subprocess.run([sys.executable,str(GEN/'sheet_overrides.py'),str(self.spec_path),'--base-rom',str(self.base),'--root',str(ROOT),'--out-dir',str(output),'--check'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0);self.assertIn('stale generated sprite sheets',result.stderr);self.assertFalse(output.exists())

    def test_manifest_reserves_global_not_sprite_id(self):
        metadata=sheets.source_metadata(ROOT)
        self.assertEqual(metadata['sprite_sheet_ids'],['0x64','0x40','0x43','0x47','0x23'])
        self.assertEqual(metadata['global_sheet_ids'],['0xD7','0xB3','0xB6','0xBA','0x96'])
        self.assertEqual(metadata['owned_region']['pc_end'],'0x208000')

    def test_manifest_integration_keeps_strict_yaze_keys_and_portable_paths(self):
        from test_generate_hack_manifest import ManifestFixture
        from generate_hack_manifest import generate_manifest
        fixture=ManifestFixture();self.addCleanup(fixture.close)
        fixture.write_text('Oracle_main.asm','')
        fixture.write_text('Data/graphics/source_sprite_sheets.json',self.spec_path.read_text())
        rom=fixture.write_dev_rom()
        manifest=generate_manifest(fixture.root,dev_rom_path=rom,manifest_root=fixture.root.parent)
        graphics=manifest['graphics_sheet_regions']
        self.assertEqual(set(graphics),{'description','allocation_regions','reserved_sheets'})
        self.assertIn('0xD7',graphics['reserved_sheets']);self.assertNotIn('0x64',graphics['reserved_sheets'])
        self.assertEqual(manifest['source_sprite_sheets']['spec'],fixture.root.name+'/Data/graphics/source_sprite_sheets.json')

    def test_generated_pointer_manifest_leaves_neighbor_sheets_editable(self):
        from test_generate_hack_manifest import ManifestFixture
        from generate_hack_manifest import generate_manifest
        fixture=ManifestFixture();self.addCleanup(fixture.close)
        include='Core/Generated/source_sprite_sheets/sheet_overrides.asm'
        fixture.write_text('Oracle_main.asm',f'incsrc "{include}"\n')
        _,items=sheets.build(self.spec_path,self.base)
        fixture.write_text(include,sheets.asm_text(items))
        manifest=generate_manifest(fixture.root,dev_rom_path=fixture.write_dev_rom())
        self.assertFalse(manifest['protected_regions']['exact'])
        # Pointer rows live in relocated arrays in bank $23, which asm ownership covers.
        bank=next(b for b in manifest['owned_banks']['banks'] if b['bank']=='0x23')
        starts={int(r['start'],16) for r in bank['regions']}
        for table in (sheets.NEW_BANK,sheets.NEW_HIGH,sheets.NEW_LOW):
            self.assertIn(table+0xD7,starts)
            for neighbor in (0xD8,0xD9):
                self.assertNotIn(table+neighbor,starts,f'Follower sheet ${neighbor:02X} pointer is protected')

    def test_actual_build_guard_refuses_wrong_or_truncated_base_before_output(self):
        # Real build wrapper/receipt/guard in a portable disposable repository.
        for directory in ('Scripts/Build','Scripts/Generate','Config','Util','Data/graphics','Roms'):
            (self.root/directory).mkdir(parents=True,exist_ok=True)
        for name in ('build_rom.sh','build_checks.sh','build_receipt.py'):
            shutil.copy2(ROOT/'Scripts/Build'/name,self.root/'Scripts/Build'/name)
        for path in GEN.glob('*.py'):shutil.copy2(path,self.root/'Scripts/Generate'/path.name)
        (self.root/'Oracle_main.asm').write_text('')
        self.reservation_root()
        (self.root/'Util/macros.asm').write_text('!ENABLE_SOURCE_SPRITE_SHEETS = 1\n')
        (self.root/'Config/feature_flags.asm').write_text('!ENABLE_SOURCE_SPRITE_SHEETS = 1\n')
        (self.root/'Data/graphics/source_sprite_sheets.json').write_text(self.spec_path.read_text())
        shutil.copy2(self.root/'sheet.txt',self.root/'Data/graphics/sheet.txt')
        output=self.root/'Roms/oos168x.sfc';output.write_bytes(b'PREVIOUS_OUTPUT')
        for data in (bytes(1), bytes(self.rom[:0x10002])+b'X'+bytes(self.rom[0x10003:])):
            base=self.root/'Roms/oos168.sfc';base.write_bytes(data)
            env=os.environ.copy();env.pop('OOS_BUILD_RECEIPT',None);env.pop('OOS_REQUIRE_CHECKS',None);env.pop('OOS_BASE_ROM',None)
            result=subprocess.run(['bash',str(self.root/'Scripts/Build/build_rom.sh'),'168'],env=env,capture_output=True,text=True)
            self.assertNotEqual(result.returncode,0,result.stdout+result.stderr)
            self.assertEqual(output.read_bytes(),b'PREVIOUS_OUTPUT')
            receipt=json.loads((self.root/'Roms/oos168x.build.json').read_text())
            checks={item['name']:item for item in receipt['checks']}
            self.assertEqual(checks['source_sprite_sheets']['status'],'failed')
            self.assertIn('need an unheadered' if len(data)==1 else 'base sheet changed',result.stderr)
            self.assertEqual(base.read_bytes(),data)


if __name__=='__main__':unittest.main()
