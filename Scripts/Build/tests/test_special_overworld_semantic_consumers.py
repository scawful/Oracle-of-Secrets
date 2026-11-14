"""Bounded assembled entrance/action consumer proofs using the retained runner."""
from pathlib import Path
import json,os,struct,unittest
import test_special_overworld_semantic_kernel as T
R=T.R
word=T.word
@unittest.skipUnless(R.ASSEMBLER and T.RUNNER, 'Asar and existing OOS_65816_RUNNER required')
class SemanticConsumersTest(unittest.TestCase):
 def build(self,rows,*,entrances=False,old_entrances=False,updates=(),caller_source="",**kw):
  extra=''
  if entrances:
   path=R.ROOT/'Overworld/entrances.asm'
   # Old-reader control assembles the maintained OFF branch of this source.
   if old_entrances:extra+='!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 0\n'
   extra+='!ENABLE_D7_FARORE_RESCUE_SEQUENCE = 1\nOverworld_DrawMap16_Persist = $1BC97C\norg $358000\n'+f'incsrc "{path}"\n'
   if old_entrances:extra+='!SPECIAL_OVERWORLD_SEMANTIC_ENABLED = 1\n'
   extra+='org $368000\npushpc\n'+f'incsrc "{R.ROOT / "Overworld/special_areas.asm"}"\n'
   updates=tuple(updates)+((0x02EEF7,bytes.fromhex('a9a40d9f00207e')),(0x02EF1A,bytes.fromhex('9f02207e')),(0x02EF26,bytes.fromhex('9c9606')))
  # Actual displaced native prefixes with an explicit RTL probe boundary.
  for i,(at,name,prefix) in enumerate(R.ACTION_PREFIXES):
   extra+=f'org ${at+len(prefix)+4:06X}\nRTL\norg ${0x378000+i*0x100:06X}\nNativePrefix{i}:\n'
   extra+='db '+','.join(f'${b:02X}' for b in prefix)+'\nLDA.l $3D8000,X\nRTL\n'
  a=T.Artifact(rows,sky=True,extra_source=extra+caller_source,image_updates=updates,**kw);self.addCleanup(a.close);self.assertEqual(a.proc.returncode,0,a.proc.stdout+a.proc.stderr);return a
 def ram(self,raw=0,mapid=0x84):
  r=bytearray(65536);word(r,0x8A,mapid);word(r,0x700,0xB5);word(r,0x70A,0x1F0);word(r,0x70E,0x3E);return r
 def compare_prefix(self,a,which,raw,ram,tile=7):
  at,_,_=R.ACTION_PREFIXES[which]
  regs=dict(a=tile,x=raw,y=0x1234,p=0x45,db=0,d=0,ram=ram)
  control,c_out,b=a.call('NativePrefix'+str(which),**regs)
  actual,out,_=a.call(at,**regs)
  for k in ('x','y','db','d','sp'):self.assertEqual(actual['registers'][k],control['registers'][k],k)
  self.assertEqual(actual['registers']['p']&~0x82,control['registers']['p']&~0x82)
  self.assertEqual(out[:0x1F80],c_out[:0x1F80]);self.assertEqual(out[0x2000:],c_out[0x2000:])
  return actual,out,control
 def test_action_prefix_keeps_raw_target_after_draw_scratch(self):
  a=self.build([T.row(0x84,7,(1,2,3,4)),T.row(0x85,7,(0x8001,0xC002,0x4403,0x0804))])
  for which in range(3):
   for raw in (0x3E,0x40):
    for scratch in ((0x1238,0xCC01),(0x1040,0xCC08)):
     ram=self.ram();word(ram,0,scratch[0]);word(ram,2,scratch[1])
     actual,_,control=self.compare_prefix(a,which,raw,ram)
     q=(control['registers']['x']&6)//2
     expected=((1,2,3,4) if raw==0x3E else (0x8001,0xC002,0x4403,0x0804))[q]
     self.assertEqual(actual['registers']['a'],expected)
 def test_action_after_actual_draw_preserves_target_context(self):
  # Native 1BC980..1BC9DD + 1BCA69..1BCA9E, with the existing resident
  # visual-word JSL hooks installed at their real sites. No helper stub.
  caller="""
org $1BC980
  LDY.w #$0000 : PHX
  ASL : ASL : ASL : STA.b $0C : STY.b $00
  TXA : CLC : ADC.b $00 : STA.b $00
  JSR.w $CA69
  LDY.w $1000
  LDA.b $02 : XBA : STA.w $1002,Y
  LDA.b $02 : CLC : ADC.w #$0020 : XBA : STA.w $100A,Y
  LDA.w #$0300 : STA.w $1004,Y : STA.w $100C,Y
  LDX.b $0C
assert pc() == $1BC9B2
  JSL Lyra_ResidentMutable0 : STA.w $1006,Y
  JSL Lyra_ResidentMutable1 : STA.w $1008,Y
  JSL Lyra_ResidentMutable2 : STA.w $100E,Y
  JSL Lyra_ResidentMutable3 : STA.w $1010,Y
  LDA.w #$FFFF : STA.w $1012,Y
  TYA : CLC : ADC.w #$0010 : STA.w $1000
  PLX : RTL
assert pc() == $1BC9DE
org $1BCA69
  STZ.b $02
  LDA.b $00 : AND.w #$003F : CMP.w #$0020 : BCC .no_adjust
  LDA.w #$0400 : STA.b $02
.no_adjust:
  LDA.b $00 : AND.w #$0FFF : CMP.w #$0800 : BCC .no_overflow
  LDA.b $02 : ADC.w #$07FF : STA.b $02
.no_overflow:
  LDA.b $00 : AND.w #$001F : ADC.b $02 : STA.b $02
  LDA.b $00 : AND.w #$0780 : LSR : ADC.b $02 : STA.b $02
  RTS
assert pc() == $1BCA9F
org $378300
AfterDraw:
  PHA : JSL $1BC980 : PLA
  JSL $1BBEDF : RTL
"""
  a=self.build([T.row(0x84,7,(1,2,3,4)),T.row(0x85,7,(0xC044,0x4045,0x8046,0x0047))],caller_source=caller)
  ram=self.ram();word(ram,0,0x1238);word(ram,2,0xCC01)
  r,out,b=a.call('AfterDraw',a=7,x=0x40,p=0,d=0,db=0,ram=ram)
  self.assertEqual(r['registers']['a'],0xC044)
  self.assertEqual(r['registers']['sp'],b['sp'])
  self.assertEqual(int.from_bytes(out[0:2],'little'),0x40)
  self.assertEqual(int.from_bytes(out[2:4],'little'),0)
  # Resident upload still used global visual words (no resident atlas row).
  self.assertEqual(int.from_bytes(out[0x1006:0x1008],'little'),a.global_words[0])
 def test_action_ordinary_map_matches_native_exactly(self):
  a=self.build([T.row(0x84,7,(1,2,3,4))])
  for which in range(3):
   ram=self.ram(mapid=2);word(ram,0,8);word(ram,2,1)
   actual,_,control=self.compare_prefix(a,which,0x40,ram)
   self.assertEqual(actual['registers'],control['registers'])
 def test_fixed_ids_stay_ids_in_memory_and_source_queries(self):
  ids=(0x034,0xDC9,0xDA4,0xDA6,0xE54)
  a=self.build([T.row(0x85,t,(0xC044,0x0844,0x8896,0xCC96)) for t in sorted(ids)])
  for tile in ids:
   ram=self.ram();word(ram,0x2040,tile)
   r,out,b=a.call('Lyra_SemanticTerrainSourceWord',a=0x40,x=tile*8,ram=ram)
   self.assertEqual(r['registers']['a'],0xC044);self.assertEqual(out[0x2040:0x2042],ram[0x2040:0x2042])
   for k in ('x','y','db','d','sp'):self.assertEqual(r['registers'][k],b[k])
 def test_raw_query_cross_bank_bridge_and_missing_context(self):
  a=self.build([T.row(0x85,7,(0xFEDC,2,3,4))],overrides=dict(SPECIAL_OVERWORLD_SEMANTIC_CODE_BASE=0x518000,SPECIAL_OVERWORLD_SEMANTIC_CODE_END=0x519000))
  ram=self.ram();r,_,_=a.call('Lyra_SemanticTerrainSourceWord',a=0x40,x=56,ram=ram);self.assertEqual(r['registers']['a'],0xFEDC)
  for raw in (0x41,0x2000):
   r,_,_=a.call('Lyra_SemanticTerrainSourceWord',a=raw,x=56,ram=ram);self.assertEqual(r['registers']['a'],a.global_words[0])
  self.assertLess(a.labels['Lyra_SemanticCodeEnd']-a.labels['Lyra_SemanticCodeStart'],0x1000)
 def entrance_fixture(self,seam=False,old=False):
  raw=0x3E if seam else 0x71E;area=0x84 if seam else 0x87
  rows=[T.row(0x84,7,(1,2,3,4)),T.row(0x85,7,(1,2,0xFE,0x14A))] if seam else [T.row(0x87,7,(1,2,3,4)),T.row(0x87,8,(1,2,0x1AD,0x1AE))]
  updates=[(0x1BBA71,struct.pack('<H',raw)),(0x1BB96F,struct.pack('<H',area)),(0x1BBB73,b'\x53')]
  a=self.build(rows,entrances=True,old_entrances=old,updates=updates)
  ram=self.ram(mapid=area);word(ram,0x40A,area);word(ram,0x20,0xFFF9 if seam else 0xD9);word(ram,0x22,0x1F0 if seam else 0xF0)
  word(ram,0x2000+raw,7);word(ram,0x2002+raw,7 if seam else 8)
  return a,ram
 def test_actual_entrance_arch_recognition(self):
  a,ram=self.entrance_fixture();r,out,b=a.call('Overworld_UseEntranceEntry',p=0,db=0,d=0,ram=ram)
  self.assertEqual((out[0x10],out[0x10E]),(0xF,0x53));self.assertEqual(r['registers']['sp'],b['sp'])
 def test_actual_entrance_neighbor_seam_same_local_id(self):
  a,ram=self.entrance_fixture(seam=True);_,out,_=a.call('Overworld_UseEntranceEntry',p=0,db=0,d=0,ram=ram)
  self.assertEqual((out[0x10],out[0x10E]),(0xF,0x53))
 def test_rejected_right_castle_keeps_neighbor_source_and_legacy_y(self):
  # Original Y=$003E, neighbor raw=$0040 (page85), then right-side DEY*2
  # leaves legacy registration Y=$003C. GameState4 rejects D7 castle opening.
  rows=[T.row(0x84,7,(0x4169,2,3,4)),T.row(0x85,7,(0x4169,2,0xFE,0x14A))]
  updates=[(0x3D8000+7*8,struct.pack('<4H',0x4169,2,0xFE,0x14A)),
           (0x1BBA71,struct.pack('<H',0x3C)),(0x1BB96F,struct.pack('<H',0x84)),(0x1BBB73,b'\x53')]
  results=[]
  for old in (True,False):
   a=self.build(rows,entrances=True,old_entrances=old,updates=updates)
   ram=self.ram();word(ram,0x40A,0x84);word(ram,0x20,0xFFF9);word(ram,0x22,0x1F0)
   word(ram,0x203E,7);word(ram,0x2040,7);word(ram,0xF3C5,4);word(ram,0x692,0xA55A)
   r,out,b=a.call('Overworld_UseEntranceEntry',p=0,db=0,d=0,ram=ram)
   self.assertEqual((out[0x10],out[0x10E]),(0xF,0x53),'global control' if old else 'semantic neighbor context')
   self.assertEqual(int.from_bytes(out[0:2],'little'),0x3C)
   self.assertEqual(int.from_bytes(out[0x692:0x694],'little'),0)
   self.assertEqual(r['registers']['sp'],b['sp'])
   results.append((r,out))
  self.assertEqual(results[0][0]['registers'],results[1][0]['registers'])
  self.assertEqual(results[0][1][:0x1F80],results[1][1][:0x1F80])
  self.assertEqual(results[0][1][0x2000:],results[1][1][0x2000:])
 def test_original_entrance_global_control_does_not_recognize_override(self):
  a,ram=self.entrance_fixture(old=True);_,out,_=a.call('Overworld_UseEntranceEntry',p=0,db=0,d=0,ram=ram)
  self.assertEqual(out[0x10],0)
 def test_actual_open_style_preserves_fixed_pairs(self):
  a=self.build([T.row(0x84,7,(1,2,3,4))],entrances=True)
  for pair,expected in [((0xFB,0xFC),(0xDA4,0xDA6)),((0xB82,0xB83),(0xFFC,0xFFD))]:
   ram=self.ram();word(ram,0x203E,pair[0]);word(ram,0x2040,pair[1]);r,out,b=a.call('OverworldDoor_FindOpenStyle',x=0x3E,p=0,d=0,db=0,ram=ram)
   self.assertEqual((r['registers']['a'],r['registers']['y']),expected);self.assertTrue(r['registers']['p']&1);self.assertEqual(out[0x203E:0x2042],ram[0x203E:0x2042])
 def test_actual_special_trigger_uses_source_top_left(self):
  a=self.build([T.row(0x81,7,(0x00B9,1,2,3))],entrances=True)
  ram=self.ram(mapid=0x81);word(ram,0x20,0xFFF4);word(ram,0x22,0xFFF8);word(ram,0x2000,7)
  _,out,_=a.call('Overworld_CheckForSpecialOverworldTrigger',p=0,db=0,d=0,ram=ram)
  self.assertEqual((out[0x10],out[0x11]),(0xB,0x17));self.assertEqual(int.from_bytes(out[0xA0:0xA2],'little'),0x189)
if __name__=='__main__':
 try:unittest.main()
 finally:
  if os.environ.get('OOS_SEMANTIC_RECEIPT'):Path(os.environ['OOS_SEMANTIC_RECEIPT']).write_text(json.dumps(T.CASES,indent=2)+'\n')
