"""Exact shared pointer helpers and private armory source metadata controls."""
import importlib.util
import json
from pathlib import Path
import sys
import unittest
import test_special_overworld_semantic_kernel as T

ROOT=T.R.ROOT
sys.path.insert(0,str(ROOT/'Scripts/Generate'))
import gen_wall_profiles as G


class ArmoryMetadataTest(unittest.TestCase):
    def test_private_stream_does_not_replace_global_source_rows(self):
        asm=G.render_kits()
        kit=next(k for k in G.load_kits() if k['kit']=='prison_armory')
        self.assertTrue(kit['sheets'][0]['private_pointer'])
        self.assertEqual(kit['sheets'][0]['sheet'],'0x08')
        self.assertIn('WallSel_Private_prison_armory_slot3:',asm)
        for address in ('23FD08','23FE08','23FF08','23FDA9','23FEA9','23FFA9','23FDF6','23FEF6','23FFF6'):
            self.assertNotIn('org $'+address,asm)
        metadata=G.render()
        self.assertIn('if !ENABLE_D3_PRISON_ARMORY == 1',metadata)
        self.assertIn('!WallSel_ProfileEnabled4 = $00',metadata)
        self.assertIn('dw $0054 : db $00, $08, $03, $01',metadata)
        self.assertIn('dw $0054 : db $01, $36, $03, $00',metadata)
        self.assertIn('dw $0600 : db $04',metadata)


@unittest.skipUnless(T.R.ASSEMBLER and T.RUNNER,'Asar and retained65816 runner required')
class ArmoryPointerTest(unittest.TestCase):
    def artifact(self,enabled):
        helper=(ROOT/'Core/gfx_sheet_table.asm').read_text().split('macro GfxSheetCopy',1)[1].split('; Empty LC-LZ2',1)[0]
        helper='macro GfxSheetCopy'+helper
        blade=(ROOT/'Dungeons/d3_prison_blade.asm').read_text()
        private=blade.split('if !ENABLE_D3_PRISON_ARMORY == 1\n; Context-only',1)[1].split('\npushpc\nassert read4($098610)',1)[0]
        source=f'''
!ENABLE_D3_PRISON_ARMORY = {enabled}
!ENABLE_EON_OWL_ONE_SHOT = 0
!DISABLE_SPRITES = 0
!GfxSheet_SprOffset = $73
GfxSheet_Low = $348000
GfxSheet_High = $348100
GfxSheet_Bank = $348200
WallSel_Private_prison_armory_slot3 = $459172
org $23FC00
{helper}
org $528000
if !ENABLE_D3_PRISON_ARMORY == 1
; Context-only{private}
org $348000
fillbyte $11 : fill 256
fillbyte $22 : fill 256
fillbyte $33 : fill 256
'''
        a=T.Artifact([],overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0},extra_source=source)
        self.addCleanup(a.close)
        self.assertEqual(a.proc.returncode,0,a.proc.stdout+a.proc.stderr)
        return a

    def test_actual_native_draw_tail_reads_size_and_xor_palette(self):
        source=(ROOT/'Dungeons/d3_prison_blade.asm').read_text()
        draw='D3Prison_BladeDraw:'+source.split('D3Prison_BladeDraw:',1)[1].split('; Room header sprite group',1)[0]
        # Native05DF78..05DFE4, with only OAM allocation/coordinate preparation
        # represented by the fixture. Table index7 and attribute XOR are real.
        tail="""
org $05DF75
  JSR $FE00
  BCS .exit
  PHX : REP #$30 : LDY.w #0 : LDX.w $0090
.next
  LDA.b ($08),Y : CLC : ADC.b $00 : STA.w $0000,X
  AND.w #$0100 : STA.b $0C : INY : INY
  LDA.b ($08),Y : CLC : ADC.b $02 : STA.w $0001,X
  CLC : ADC.w #$0010 : CMP.w #$0100 : BCC .on_screen
  LDA.w #$00F0 : STA.w $0001,X
.on_screen
  INY : INY : LDA.w $0CFE : CMP.w #$0001
  LDA.b ($08),Y : EOR.b $04 : BCC .normal_palette
  AND.w #$F1FF : ORA.w #$0400
.normal_palette
  STA.w $0002,X : PHX : TXA : SEC : SBC.w #$0800
  LSR : LSR : TAX : SEP #$20 : INY : INY : INY
  LDA.b ($08),Y : ORA.b $0D : STA.w $0A20,X
  PLX : REP #$20 : INY : INX : INX : INX : INX
  DEC.b $06 : BNE .next
  SEP #$30 : PLX
.exit
  RTL
assert pc() == $05DFE5
org $05FE00
  REP #$20
  LDA.w #$0080 : STA.b $00 : STA.b $02
  LDA.w #$2900 : STA.b $04 ; actual native04 priority20 + palette09
  LDA.w #$0800 : STA.b $90
  SEP #$20 : CLC : RTS
"""
        extra='!ENABLE_D3_PRISON_ARMORY = 1\norg $348000\nDrawFixture: JSR D3Prison_BladeDraw : RTL\n'+draw+tail
        a=T.Artifact([],overrides={'SPECIAL_OVERWORLD_SEMANTIC_ENABLED':0},extra_source=extra)
        self.addCleanup(a.close);self.assertEqual(a.proc.returncode,0,a.proc.stdout+a.proc.stderr)
        result,out,_=a.call('DrawFixture',x=15,p=0x30,db=0,d=0,ram=bytearray(65536))
        self.assertEqual(out[0x800:0x804],bytes.fromhex('7874c629'))
        self.assertEqual(out[0xA20],2,'16x16 OAM size, not discarded table byte6')

    def test_selected_blade_draw_and_inventory_contract(self):
        import test_prison_cell65 as P
        a=P.PrisonCell65Test.inventory_artifact(self,armory=1)
        data=(a.dir/'probe.sfc').read_bytes()
        at=T.R.N.pc(0x38F100)
        self.assertEqual(data[at:at+48],bytes.fromhex('f8fff4ffc6000002')+bytes(40))
        ram=bytearray(65536);ram[0x10]=7;ram[0x1B]=1;ram[0x40C]=0x10
        ram[0xA0]=0x54;ram[0x48E]=0x54;ram[0xF306]=0x21
        _,ram,_=a.call('D3Prison_BladeStage',ram=ram,p=0x30,db=0x52,d=0)
        ram[0xF6]=0x80;T.word(ram,0x22,0x878);T.word(ram,0x20,0xA95)
        _,out,_=a.call('D3Prison_BladeMain',x=15,ram=ram,p=0x30,db=0x52,d=0)
        self.assertEqual(out[0xF359],2)
        self.assertEqual(out[0xF306],0x29)
        self.assertEqual(out[0x5D],0x15)
        self.assertEqual(out[0xF70:0xF72],b'\x01\x01')

    def test_actual_shared_helpers_context_controls_and_abi(self):
        for enabled in (0,1):
            a=self.artifact(enabled)
            cases=[({},True),({0xA0:0x55},False),({0xA1:1},False),({0x1B:0},False),({0x40C:9},False),({0xAA2:1},False)]
            for entry,request,dest in [('GfxSheet_GetPtr_Spr',0x36,0),('GfxSheet_GetPtr_SprCA',0x36,0xC8),('GfxSheet_GetPtr_BgCA',8,0xC8)]:
                for changes,admitted in cases:
                    for d in (0,0x120):
                        ram=bytearray(65536);ram[0xA0]=0x54;ram[0x1B]=1;ram[0x40C]=0x10;ram[0xAA2]=0x19
                        for at,val in changes.items():ram[at]=val
                        result,out,before=a.call(entry,a=0x6C,x=0x5A,y=request,p=0x31,db=0x52,d=d,ram=ram)
                        self.assertEqual(out[d+dest:d+dest+3],bytes.fromhex('729145')if enabled and admitted else bytes.fromhex('112233'))
                        for key in ('x','y','p','db','d','sp'):self.assertEqual(result['registers'][key],before[key],key)
                        allowed=set(range(d+dest,d+dest+3))|set(range(0x1F80,0x2000))
                        self.assertTrue(all(out[i]==ram[i] for i in range(65536)if i not in allowed))
                ram=bytearray(65536);ram[0xA0]=0x54;ram[0x1B]=1;ram[0x40C]=0x10;ram[0xAA2]=0x19
                _,out,_=a.call(entry,y=request+1,p=0x30,db=0,d=0,ram=ram)
                self.assertEqual(out[dest:dest+3],bytes.fromhex('112233'))


if __name__=='__main__':unittest.main()
