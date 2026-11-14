"""Actual Asar + existing Yaze 65816 runner proof; synthetic bindings only.

Set OOS_65816_RUNNER to the existing runner. No game ROM fixture, new CPU
implementation, runtime allocation, or ordinary Build admission is supplied.
"""
from pathlib import Path
import json,math,os,struct,subprocess,tempfile,unittest
import test_special_overworld_resident_kernel as R
RUNNER=os.environ.get('OOS_65816_RUNNER')
ROWS=0x4F8000
CODE=0x4DC800 # synthetic test extent only; NOT a production allocation
CASES=[]
def row(page,tile,words):return struct.pack('<6H',page,tile,*words)
def word(ram,at,value):ram[at:at+2]=value.to_bytes(2,'little')
def values(count,capacity=192):
 v=R.constants(capacity);v.update(SPECIAL_OVERWORLD_SEMANTIC_ENABLED=1,SPECIAL_OVERWORLD_SEMANTIC_REVISION=5,SPECIAL_OVERWORLD_SEMANTIC_CAPACITY=capacity,SPECIAL_OVERWORLD_SEMANTIC_ROWS=ROWS,SPECIAL_OVERWORLD_SEMANTIC_COUNT=count,SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE=CODE,SPECIAL_OVERWORLD_SEMANTIC_CODE_END=CODE+0x400)
 return v
# Exact native $00882E..$008887 instructions, with only $008864 redirected
# in this synthetic probe. Sky source installs its real $00886E continuation.
CALLER='''
org $00882E
  REP #$30
  LDA.b $00 : SEC : SBC.w $0708 : AND.w $070A
  ASL : ASL : ASL : STA.b $06
  LDA.b $02 : SEC : SBC.w $070C : AND.w $070E : ORA.b $06 : TAX
  LDA.l $7E2000,X : ASL : ASL : STA.b $06
  LDA.b $00 : AND.w #$0008 : LSR : LSR : TSB.b $06
  LDA.b $02 : AND.w #$0001 : ORA.b $06 : ASL : TAX
assert pc() == $008864
  JSL Lyra_SemanticCollisionWord
  STA.b $06 : AND.w #$01FF : TAX
assert pc() == $00886E
  JSL SkyTileType
  SEP #$30
  CMP.b #$10 : BCC .exit
  CMP.b #$1C : BCS .exit
  STA.b $06 : LDA.b $07 : AND.b #$40
  ASL : ROL : ROL : ORA.b $06
.exit:
  RTL
assert pc() == $008888
'''
class Artifact:
 def __init__(self,rows,capacity=192,sky=False,overrides=None,area_size=1,parent=0x84):
  self.tmp=tempfile.TemporaryDirectory();self.dir=Path(self.tmp.name);self.v=values(len(rows),capacity);self.v.update(overrides or {})
  image=bytearray(R.source_fixture());raw=b''.join(rows);image[R.N.pc(ROWS):R.N.pc(ROWS)+len(raw)]=raw
  self.global_words=(0x1011,0x5022,0x9033,0xD044)
  for tile in [0,7,0xFFF]:image[R.N.pc(0x3D8000)+tile*8:R.N.pc(0x3D8000)+tile*8+8]=struct.pack('<4H',*self.global_words)
  tables={f.name:f.snes for f in R.N.current_table_layout(R.N.TABLE_BASE)}
  for page in range(128,capacity):
   image[R.N.pc(tables['parent'])+page]=page
   image[R.N.pc(tables['area_size'])+page]=0
  self.tables=tables
  # area84 large ->84/85/8C/8D, independent from Link0700
  for page in [0x84,0x85,0x8C,0x8D]:
   image[R.N.pc(tables['parent'])+page]=parent
   image[R.N.pc(tables['area_size'])+page]=area_size
  extra=''
  if sky:
   self.v.update(ENABLE_SKY_OVERWORLD_ROUTE=1,ENABLE_SKY_OVERWORLD_GRAPHICS=1)
   for at in (0x00886E,0x1BBEFD,0x1BBF2A,0x1BC04E):image[R.N.pc(at):R.N.pc(at)+4]=bytes.fromhex('BF59940E')
   image[R.N.pc(0x1BBE3E):R.N.pc(0x1BBE3E)+11]=bytes.fromhex('AD7A0329FF00C90100D0F2')
   image[R.N.pc(0x0E9659)]=0x5A
   image[R.N.pc(0x0E9459):R.N.pc(0x0E9459)+512]=bytes([0x27])*512
   extra=f'org $348000\nincsrc "{R.ROOT / "Overworld/sky_tile_types.asm"}"\n'+CALLER
  self.before=bytes(image);self.proc,self.image,self.labels=R.assemble(self.dir,self.before,self.v,extra)
 def close(self):self.tmp.cleanup()
 def call(self,label,*,a=0xA55A,x=0x84,y=56,p=0xCD,db=0x42,d=0x120,ram=None):
  if ram is None:ram=bytearray((i*37+19)&255 for i in range(65536))
  before=dict(a=a,x=x,y=y,p=p,db=db,d=d,sp=0x1FFF)
  request=dict(entry=self.labels[label] if isinstance(label,str) else label,reset_ram=True,registers=before,writes=[dict(address=0x7E0000,bytes=list(ram))],reads=[dict(address=0x7E0000,length=65536)],trace_writes=True,max_steps=2500)
  result=subprocess.run([RUNNER,str(self.dir/'probe.sfc')],input=json.dumps(request)+'\n',capture_output=True,text=True,timeout=10,check=True)
  result=json.loads(result.stdout);assert result.get('returned'),result
  CASES.append(dict(entry=label,steps=result['steps'],inputs=before,output=result['registers']))
  return result,bytearray(result['reads'][0]['bytes']),before
@unittest.skipUnless(R.ASSEMBLER and RUNNER,'Asar and existing OOS_65816_RUNNER required')
class SemanticKernelTest(unittest.TestCase):
 def build(self,rows,**kw):
  a=Artifact(rows,**kw);self.addCleanup(a.close);self.assertEqual(a.proc.returncode,0,a.proc.stdout+a.proc.stderr);self.assertIn('Lyra_SemanticSourceWord',a.labels);return a
 def preserved(self,result,before,ram,out,*,nz=False):
  r=result['registers']
  for key in ('x','y','db','d','sp'):self.assertEqual(r[key],before[key],key)
  self.assertEqual(r['p']&(~0x82 if nz else 255),before['p']&(~0x82 if nz else 255))
  # Inactive stack bytes may be written by calls, never live stack or scratch.
  self.assertEqual(out[:0x1F80],ram[:0x1F80]);self.assertEqual(out[0x2000:],ram[0x2000:])
 def test_explicit_page_same_id_all_source_bits_and_flags(self):
  variants={0x84:(0x0044,0x4454,0x8896,0xCDB6),0x85:(0xFFFF,0,0xA123,0x7FFF)}
  a=self.build([row(p,7,w) for p,w in variants.items()])
  for page,words in variants.items():
   for q,w in enumerate(words):
    for p in (0,0xCD):
     ram=bytearray((i*37+19)&255 for i in range(65536));r,out,b=a.call('Lyra_SemanticSourceWord',x=page,y=7*8+2*q,p=p,ram=ram)
     self.assertEqual(r['registers']['a'],w);self.preserved(r,b,ram,out)
 def test_missing_and_invalid_query_preserve_global_word(self):
  a=self.build([row(0x84,7,(1,2,3,4)),b'\xFF'*12])
  for x,y in [(0x83,56),(0x85,56),(0x84,48),(0x84,64),(0x7F,56),(0xC0,56),(0x184,56),(0x84,57),(0x84,0x8000)]:
   r,out,b=a.call('Lyra_SemanticSourceWord',a=0xFCAD,x=x,y=y);self.assertEqual(r['registers']['a'],0xFCAD);self.assertEqual(r['registers']['p'],b['p'])
 def test_160_and_192_last_physical_page(self):
  for capacity in (160,192):
   a=self.build([row(capacity-1,0xFFF,(0xABCD,2,3,4))],capacity=capacity)
   r,_,_=a.call('Lyra_SemanticSourceWord',x=capacity-1,y=0x7FF8);self.assertEqual(r['registers']['a'],0xABCD)
 def test_2730_rows_binary_search_bound(self):
  a=self.build([row(0x84,i,(i,0x4000|i,0x8000|i,0xC000|i)) for i in range(2730)])
  for i in (0,1,2,1364,1365,2728,2729,2730,4095):
   r,_,_=a.call('Lyra_SemanticSourceWord',x=0x84,y=i*8,a=0xFADE)
   self.assertEqual(r['registers']['a'],i if i<2730 else 0xFADE)
   self.assertLessEqual(r['steps'],450)
 def test_malformed_rows_refused_at_assembly(self):
  rows=[[row(0x7F,7,(1,2,3,4))],[row(0xC0,7,(1,2,3,4))],[row(0x84,0x1000,(1,2,3,4))],[row(0x84,7,(1,2,3,4))]*2,[row(0x85,7,(1,2,3,4)),row(0x84,7,(1,2,3,4))],[b'\xFF'*12,row(0x84,7,(1,2,3,4))],[b'\xFF'*10+b'\0\0']]
  for rs in rows:
   a=Artifact(rs);self.addCleanup(a.close);self.assertNotEqual(a.proc.returncode,0)
 def test_revision_extent_origin_refused(self):
  for kv in [('SPECIAL_OVERWORLD_SEMANTIC_REVISION',4),('SPECIAL_OVERWORLD_SEMANTIC_REVISION',6),('SPECIAL_OVERWORLD_SEMANTIC_ROWS',0x4FFFF8),('SPECIAL_OVERWORLD_SEMANTIC_ROWS',0x7E8000),('SPECIAL_OVERWORLD_SEMANTIC_CODE_END',CODE+4),('SPECIAL_OVERWORLD_SEMANTIC_COUNT',0)]:
   a=Artifact([row(0x84,7,(1,2,3,4))],overrides=dict([kv]));self.addCleanup(a.close);self.assertNotEqual(a.proc.returncode,0)
 def test_only_explicit_code_extent_changes_no_hook_installed(self):
  a=self.build([row(0x84,7,(1,2,3,4))]);ranges=[(R.N.pc(CODE),R.N.pc(a.labels['Lyra_SemanticCodeEnd'])) ,(R.N.pc(R.N.RESIDENT_WORD_CODE_BASE),R.N.pc(a.labels['Lyra_ResidentAtlasCodeEnd']))]+[(R.N.pc(at),R.N.pc(at)+n) for at,_,n in R.HOOKS]
  self.assertEqual(a.image[R.N.pc(0x008864):R.N.pc(0x008868)],a.before[R.N.pc(0x008864):R.N.pc(0x008868)])
  for i,(b,c) in enumerate(zip(a.before,a.image)):
   if b!=c:self.assertTrue(any(lo<=i<hi for lo,hi in ranges),hex(i))
 def test_collision_adapter_parent_quadrants_and_full_abi(self):
  pages=[0x84,0x85,0x8C,0x8D];a=self.build([row(p,7,(p,0x4000|p,0x8000|p,0xC000|p)) for p in pages])
  for raw,page in zip([0,0x40,0x1000,0x1040],pages):
   for q in range(4):
    ram=bytearray(65536);word(ram,0x8A,0x8D);word(ram,0x700,0xB5)
    word(ram,0,(raw&0x1000)>>3);word(ram,2,raw&0x40);word(ram,0x70A,0x200);word(ram,0x70E,0x40)
    r,out,b=a.call('Lyra_SemanticCollisionWord',x=56+q*2,y=0xABCD,ram=ram)
    self.assertEqual(r['registers']['a'],page|[0,0x4000,0x8000,0xC000][q]);self.preserved(r,b,ram,out,nz=True)
 def test_collision_small_wide_tall_and_refusal(self):
  for size,expected in [(0,[0x84]*4),(2,[0x84,0x85,0x84,0x85]),(3,[0x84,0x84,0x8C,0x8C]),(4,[None]*4)]:
   a=self.build([row(p,7,(p,2,3,4)) for p in (0x84,0x85,0x8C,0x8D)],area_size=size)
   for raw,page in zip([0,0x40,0x1000,0x1040],expected):
    ram=bytearray(65536);word(ram,0x8A,0x84);word(ram,0,(raw&0x1000)>>3);word(ram,2,raw&0x40);word(ram,0x70A,0x200);word(ram,0x70E,0x40)
    r,out,b=a.call('Lyra_SemanticCollisionWord',x=56,ram=ram)
    self.assertEqual(r['registers']['a'],a.global_words[0] if page is None else page);self.preserved(r,b,ram,out,nz=True)
  for variant in ('indoors','raw_offset_outside','parent_outside','ordinary_page','missing_row'):
   a=self.build([row(0x84,7,(0xAAAA,2,3,4))],parent=0x40 if variant=='parent_outside' else 0x84)
   ram=bytearray(65536);word(ram,0x8A,0x83 if variant=='ordinary_page' else 0x84);word(ram,0x70A,0x400);word(ram,0x70E,0x40)
   if variant=='indoors':ram[0x1B]=1
   if variant=='raw_offset_outside':word(ram,0,0x400)
   if variant=='missing_row':word(ram,2,0x40)
   r,out,b=a.call('Lyra_SemanticCollisionWord',x=56,ram=ram)
   self.assertEqual(r['registers']['a'],a.global_words[0]);self.preserved(r,b,ram,out,nz=True)
 def test_actual_collision_continuation_sky_attributes_hflip(self):
  words=(0x0044,0x4044,0x8896,0xCC96);a=self.build([row(0x84,7,words)],sky=True)
  for q in range(4):
   ram=bytearray(65536);word(ram,0x8A,0x84);word(ram,0x70A,0x200);word(ram,0x70E,0x40);word(ram,0x2000,7)
   word(ram,0,8 if q>=2 else 0);word(ram,2,q&1)
   r,out,b=a.call(0x00882E,p=0,db=0,d=0,ram=ram)
   self.assertEqual(r['registers']['a']&255,[0x1A,0x1B,0x10,0x11][q]);self.assertEqual(r['registers']['sp'],b['sp'])
   self.assertEqual(out[7],words[q]>>8)
 def test_actual_collision_global_fallback_non_sky(self):
  a=self.build([row(0x84,7,(1,2,3,4))],sky=True)
  ram=bytearray(65536);word(ram,0x8A,0x83);word(ram,0x70A,0x200);word(ram,0x70E,0x40);word(ram,0x2000,7)
  r,out,b=a.call(0x00882E,p=0,db=0,d=0,ram=ram);self.assertEqual(r['registers']['a']&255,0x27);self.assertEqual(int.from_bytes(out[6:8],'little'),a.global_words[0])
if __name__=='__main__':
 try:unittest.main()
 finally:
  if os.environ.get('OOS_SEMANTIC_RECEIPT'):Path(os.environ['OOS_SEMANTIC_RECEIPT']).write_text(json.dumps(CASES,indent=2)+'\n')
