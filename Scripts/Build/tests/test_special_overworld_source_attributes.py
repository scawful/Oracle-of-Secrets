"""Source-sheet authentication and actual Asar/CPU page90 attribute controls."""
from pathlib import Path
import copy
import hashlib
import json
import unittest

import test_special_overworld_resources as F
import test_special_overworld_semantic_kernel as K
import test_special_overworld_native_build as S
import special_overworld_native_build as B

R = F.R


def payload(raw):
    return dict(collision_attributes_hex=raw.hex(),
                collision_attributes_sha256=hashlib.sha256(raw).hexdigest())


class SourceAttributeAuthenticationTest(unittest.TestCase):
    def setUp(self):
        self.fixture = F.SavedNativeTerrainResourcesTest()
        self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        self.root, self.value, _ = self.fixture.bound_global()
        self.spec = self.root / 'Data/graphics/source_sprite_sheets.json'

    def bind(self, raw):
        spec = json.loads(self.spec.read_text())
        spec['sheets'][-1].update(payload(raw))
        self.spec.write_text(json.dumps(spec))
        self.value['graphics_source']['spec_sha1'] = hashlib.sha1(self.spec.read_bytes()).hexdigest()
        self.value['graphics_source']['sheets'][0].update(payload(raw))

    def test_selected_flagged_entry_authenticates_exact_raw64_bytes(self):
        raw = bytes(range(64))
        self.bind(raw)
        authenticated = R._graphics_sources(self.value, self.root)
        self.assertEqual(R.sheet_overrides.collision_attributes(authenticated[0xEB][2]), raw)
        # The unflagged fallback must never supply the selected variant's attrs.
        spec = json.loads(self.spec.read_text())
        spec['sheets'][0].update(payload(bytes([0x65]) * 64))
        self.spec.write_text(json.dumps(spec))
        self.value['graphics_source']['spec_sha1'] = hashlib.sha1(self.spec.read_bytes()).hexdigest()
        selected = R._graphics_sources(self.value, self.root)
        self.assertEqual(R.sheet_overrides.collision_attributes(selected[0xEB][2]), raw)

    def test_malformed_optional_pair_is_never_silently_ignored(self):
        raw = bytes(range(64))
        valid = payload(raw)
        variants = [{}, {k:v for k,v in valid.items() if k.endswith('_hex')},
                    {k:v for k,v in valid.items() if k.endswith('_sha256')}]
        # Empty pair is the exact legacy behavior; every malformed present pair refuses.
        self.assertIsNone(R.sheet_overrides.collision_attributes(variants.pop(0)))
        for field, value in [('collision_attributes_hex', raw.hex().upper()),
                             ('collision_attributes_hex', raw.hex()[:-2]),
                             ('collision_attributes_hex', 'gg'*64),
                             ('collision_attributes_hex', 64),
                             ('collision_attributes_sha256', valid['collision_attributes_sha256'].upper()),
                             ('collision_attributes_sha256', '0'*64),
                             ('collision_attributes_sha256', None)]:
            bad = dict(valid);bad[field] = value;variants.append(bad)
        for fields in variants:
            with self.subTest(fields=fields):
                spec = json.loads(self.spec.read_text())
                for key in R.sheet_overrides.COLLISION_FIELDS:
                    spec['sheets'][-1].pop(key, None)
                spec['sheets'][-1].update(fields)
                self.spec.write_text(json.dumps(spec))
                with self.assertRaises(ValueError):
                    R.sheet_overrides.read_spec(self.spec)

    def test_export_row_and_spec_must_match_including_attribute_hash(self):
        self.bind(bytes(range(64)))
        for mutate in ('omit', 'replace'):
            bad = copy.deepcopy(self.value)
            row = bad['graphics_source']['sheets'][0]
            if mutate == 'omit':
                for key in R.sheet_overrides.COLLISION_FIELDS:row.pop(key)
            else:
                row.update(payload(bytes([2])*64))
            with self.assertRaisesRegex(ValueError, 'GRAPHICS_SOURCE_ROWS_MISMATCH'):
                R._graphics_sources(bad, self.root)

    def compose(self, supplied, *, page=0x90, parent=0x90, size='small', revision=5,
                static=None, animation=0xFE, marker=3, resident=True):
        source = bytearray(0x140146)
        source[0x140145] = marker
        source[0x71459:0x7165A] = bytes([0x27])*512 + b'\x5A'
        static = static or list(range(0xF6,0xFE))
        assets = {(page,0):dict(slots=[dict(sheet_id=s) for s in static],
                               animation=dict(sheet_id=animation))}
        areas = [dict(parent_map_id=parent,size=size,maps=[page],resident_required=resident)]
        value = dict(directory_revision=revision,pages=[dict(map_id=page,parent_map_id=parent,
            source_profile=dict(graphics_sheets=static,animated_sheet=animation))])
        auth = {sid:(None,None,payload(raw)) for sid,raw in supplied.items()}
        return R._page_source_attributes(bytes(source),value,assets,areas,auth)

    def test_animation_uses_active_sheet_not_static7_or_predecessor(self):
        result = self.compose({0xF6:bytes([1])*64,0xFD:bytes([2])*64,0xFE:bytes(range(64))})
        raw = bytes.fromhex(result['payload_hex'])
        self.assertEqual(raw[:64],bytes([1])*64)
        self.assertEqual(raw[64:448],bytes([0x27])*384)
        self.assertEqual(raw[448:480],bytes(range(32)))
        self.assertEqual(raw[480:512],bytes([2])*32)
        self.assertEqual(raw[512],0x5A)
        no_active = self.compose({0xFD:bytes([2])*64})
        self.assertEqual(bytes.fromhex(no_active['payload_hex'])[448:480],bytes([0x27])*32)

    def test_other_pages_revision_and_non_small_geometry_refuse(self):
        attrs = {0xF6:bytes([1])*64}
        for kw in (dict(page=0x91,parent=0x91),dict(parent=0x88),dict(size='tall'),
                   dict(size='large'),dict(size='wide'),dict(revision=4),dict(marker=5),dict(marker=0),dict(resident=False)):
            with self.subTest(kw=kw), self.assertRaises(ValueError):self.compose(attrs,**kw)
        self.assertIsNone(self.compose({}))
        self.assertIsNone(self.compose({0xDF:bytes([1])*64}))

    def test_constants_preserve_absence_and_require_full_M16_sentinel(self):
        self.assertEqual(B.source_attribute_constants({'resource_plan':{}}),'')
        row = self.compose({0xF6:bytes([1])*64})
        text = B.source_attribute_constants({'resource_plan':{'source_attributes':row}})
        self.assertIn('macro SpecialOverworldSourceAttributeBytes()',text)
        self.assertIn('!SPECIAL_OVERWORLD_SOURCE_ATTRIBUTES_ENABLED = 1',text)
        for field,value in [('payload_hex','00'),('sha256','0'*64),('area_size',4)]:
            bad = dict(row);bad[field]=value
            with self.assertRaises(ValueError):
                B.source_attribute_constants({'resource_plan':{'source_attributes':bad}})


@unittest.skipUnless(K.R.ASSEMBLER and K.RUNNER,'Asar and retained OOS_65816_RUNNER required')
class SourceAttributeKernelTest(unittest.TestCase):
    def artifact(self, *, enabled=True, parent=0x90, size=0):
        attrs = bytes((i*37+11)&255 for i in range(512)) + b'\x5A'
        row = dict(map_id=0x90,parent_map_id=0x90,area_size=0,
                   byte_count=513,payload_hex=attrs.hex(),sha256=hashlib.sha256(attrs).hexdigest())
        preamble = B.source_attribute_constants({'resource_plan':{'source_attributes':row}}) if enabled else ''
        tables = {f.name:f.snes for f in K.R.N.current_table_layout(K.R.N.TABLE_BASE)}
        updates=[(site,bytes.fromhex('BF59940E')) for site in
                 (0x00886E,0x1BBEFD,0x1BBF2A,0x1BC04E)]
        updates += [(0x1BBE3E,bytes.fromhex('AD7A0329FF00C90100D0F2')),
                    (0x0E9459,bytes([0x27])*512+b'\x5A'),
                    (tables['parent']+0x90,bytes([parent])),
                    (tables['area_size']+0x90,bytes([size]))]
        extra=(f'org $348000\nnamespace Oracle\nincsrc "{K.R.ROOT / "Overworld/sky_tile_types.asm"}"\nnamespace off\n'
               + ''.join(f'org ${site+4:06X}\nRTL\n' for site in
                         (0x00886E,0x1BBEFD,0x1BBF2A,0x1BC04E)))
        a = K.Artifact([K.row(0x90,7,(1,2,3,4))],preamble=preamble,
                       overrides={'ENABLE_SKY_OVERWORLD_ROUTE':1,'ENABLE_SKY_OVERWORLD_GRAPHICS':1,
                                  'SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE':0x518000,
                                  'SPECIAL_OVERWORLD_SEMANTIC_CODE_END':0x519000},
                       extra_source=extra,image_updates=updates)
        self.addCleanup(a.close)
        self.assertEqual(a.proc.returncode,0,a.proc.stdout+a.proc.stderr)
        return a,attrs

    @staticmethod
    def ram(page=0x90,area=0x90,indoor=0):
        ram=bytearray((i*37+19)&255 for i in range(65536))
        K.word(ram,0x8A,page);K.word(ram,0x40A,area);ram[0x1B]=indoor
        return ram

    def test_fullword_neighbor_sentinel_and_all_ABI(self):
        a,attrs=self.artifact()
        # Include immediately adjacent reads, final character and all changed
        # positions, rather than checking only a returned low attribute byte.
        for ch in (0,0x1C,0x1D,0x37,0x38,0x80,0x81,0x1FE,0x1FF):
            for p in (0,0xCD):
                ram=self.ram();r,out,b=a.call('Oracle_SkyTileType',x=ch,y=0xABCD,p=p,db=0x42,d=0x120,ram=ram)
                self.assertEqual(r['registers']['a'],int.from_bytes(attrs[ch:ch+2],'little'))
                K.SemanticKernelTest.preserved(self,r,b,ram,out,nz=True)
        self.assertLessEqual(a.labels['Lyra_SemanticCodeEnd'],0x519000)
        self.assertEqual(a.labels['Lyra_SourceTileTypes90_End']-a.labels['Lyra_SourceTileTypes90'],513)

    def test_every_unqualified_context_matches_existing_Sky_and_vanilla(self):
        control,_=self.artifact(enabled=False)
        cases=[(0x87,0x87,0,0x90,0),(0x8F,0x8F,0,0x90,0),
               (0x8C,0x8C,0,0x90,0),(0x91,0x91,0,0x90,0),
               (0x190,0x90,0,0x90,0),(0x90,0x190,0,0x90,0),
               (0x90,0x90,1,0x90,0),(0x90,0x90,0,0x8F,0),
               (0x90,0x90,0,0x90,1),(0x90,0x90,0,0x90,3),
               (0x90,0x90,0,0x90,4)]
        for page,area,indoor,parent,size in cases:
            a,_=self.artifact(parent=parent,size=size)
            for ch in (0x1C,0x1D,0x80,0x81,0x1FF):
                ram=self.ram(page,area,indoor)
                actual,out,b=a.call('Oracle_SkyTileType',x=ch,p=0xCD,ram=ram)
                expected,_,_=control.call('Oracle_SkyTileType',x=ch,p=0xCD,ram=ram)
                self.assertEqual(actual['registers'],expected['registers'],(page,area,indoor,parent,size,ch))
                K.SemanticKernelTest.preserved(self,actual,b,ram,out,nz=True)

    def test_all_four_real_hook_sites_reach_the_same_guarded_table(self):
        a,attrs=self.artifact()
        # Execute each real JSL site; only its continuation is replaced with
        # an RTL observation boundary using the maintained assembly seam.
        for site in (0x00886E,0x1BBEFD,0x1BBF2A,0x1BC04E):
            at=K.R.N.pc(site)
            self.assertEqual(a.image[at:at+4],b'\x22'+a.labels['Oracle_SkyTileType'].to_bytes(3,'little'))
            for ch in (0x1C,0x1D,0x80,0x81,0x1FF):
                ram=self.ram();r,out,b=a.call(site,x=ch,p=0xCD,ram=ram)
                self.assertEqual(r['registers']['a'],int.from_bytes(attrs[ch:ch+2],'little'))
                K.SemanticKernelTest.preserved(self,r,b,ram,out,nz=True)


class SourceAttributeCompiledSealTest(unittest.TestCase):
    def setUp(self):
        self.fixture=S.ManagedSemanticSealTest();self.fixture.setUp()
        self.addCleanup(self.fixture.doCleanups)
        image,symbols=self.fixture.compiled_semantic_fixture()
        self.image=bytearray(image);self.symbols=symbols
        self.raw=bytes((i*37+11)&255 for i in range(512))+b'\x5A'
        self.row=dict(map_id=0x90,parent_map_id=0x90,area_size=0,
                      byte_count=513,payload_hex=self.raw.hex(),sha256=hashlib.sha256(self.raw).hexdigest())
        symbols.update(Lyra_SemanticCodeEnd=0x518400,Lyra_SourceTileType=0x5180F0,
                       Lyra_SourceTileTypes90=0x518100,Lyra_SourceTileTypes90_End=0x518301,
                       Oracle_SkyTileType=0x348000,Oracle_Lyra_SourceTileTypeLegacy=0x348005)
        self.image[K.R.N.pc(0x518100):K.R.N.pc(0x518301)]=self.raw
        self.image[K.R.N.pc(0x348000):K.R.N.pc(0x348005)]=b'\x08\x5C'+(0x5180F0).to_bytes(3,'little')
        for site in (0x00886E,0x1BBEFD,0x1BBF2A,0x1BC04E):
            self.image[K.R.N.pc(site):K.R.N.pc(site)+4]=b'\x22'+(0x348000).to_bytes(3,'little')
        _,_,self.entries=K.R.N.read_native_directory(self.fixture.source,experimental_page_tile16=True)

    def verify(self,image=None,row=None):
        return B._semantic_compiled_readers(self.fixture.source,bytes(image or self.image),
            self.entries,self.symbols,[],self.row if row is None else row)

    def test_table_dispatch_and_existing_hooks_match_authenticated_preparation(self):
        spans,proof=self.verify()
        self.assertEqual(proof['hook_count'],14)
        self.assertEqual(proof['source_attributes']['sha256'],hashlib.sha256(self.raw).hexdigest())
        self.assertTrue(proof['source_attributes']['full_M16_table_verified'])
        self.assertTrue(spans)

    def test_changed_table_sentinel_dispatch_or_caller_refuses(self):
        for at in (0x518100,0x518300,0x348001,0x00886F,0x1BBEFE,0x1BBF2B,0x1BC04F):
            image=bytearray(self.image);image[K.R.N.pc(at)]^=1
            with self.subTest(at=hex(at)),self.assertRaises(ValueError):self.verify(image)
        with self.assertRaisesRegex(ValueError,'UNAUTHENTICATED_SOURCE_ATTRIBUTES'):
            B._semantic_compiled_readers(self.fixture.source,bytes(self.image),
                self.entries,self.symbols,[],None)


if __name__ == '__main__':unittest.main()
