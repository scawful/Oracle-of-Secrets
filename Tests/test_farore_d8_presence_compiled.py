#!/usr/bin/env python3
"""Execute Farore presence core and production callers. Floor probes are stubbed."""
import argparse,ctypes as C,json,re,subprocess,tempfile
from pathlib import Path
from d4_compiled_fight_check import Cpu
from test_farore_d8_graphics_compiled import GraphicsFixture,call
ROOT=Path(__file__).resolve().parents[1]

class PresenceFixture(GraphicsFixture):
    def __init__(self,*args):
        super().__init__(*args);self.stubs={0x06E87B:'tile', self.addr('Sprite_CheckActive'):'inactive'};self.queries=[];self.tile=lambda x,y:0
    def stub(self,name):
        if name=='inactive':
            self.cpu.c=False
            return
        assert name=='tile'
        x=self.get(2)|self.get(3)<<8;y=self.get(0)|self.get(1)<<8
        self.queries.append((x,y,self.cpu.a&255));self.put(0xFA5,self.tile(x,y))
        for i in range(8):self.put(i,0xDC+i)
        self.cpu.x=7;self.cpu.y=9

def setup(f,room=0x90,crystal=0):
    f.word(0xA0,room);f.word(0x48E,room);f.put(0x1B,1);f.put(0x40C,4);f.put(0x7EF37A,crystal)
    f.word(0x22,0x100);f.word(0x20,0x100);f.put(0x10,7);f.put(0x11,0);f.put(0xEE,0)
    f.put(0x7EF303,0)

def assemble(p, enabled=1):
    source=(ROOT/'Core/symbols.asm').read_text()
    defs='\n'.join(m[0] for m in re.finditer(r'(?m)^Spr\w+\s*=\s*\$[0-9a-fA-F]+',source))
    graphics=(ROOT/'Sprites/NPCs/farore_d8_graphics.asm').read_text()
    membership=graphics[graphics.index('D8Farore_IsMember:'):graphics.index('; Header ABI')]
    asm=p/'fixture.asm';rom=p/'fixture.sfc';rom.write_bytes(b'\xff'*0x200000)
    asm.write_text('lorom\n'+defs+'\nSprite_Farore = $73\nInCutScene = $7EF303\norg $2C8000\n'+membership+'\nincsrc "'+str(ROOT/'Sprites/NPCs/farore_d8_companion.asm')+'"\n')
    callers=(ROOT/'Sprites/NPCs/farore.asm').read_text()
    callers=callers[callers.index('Sprite_Farore_Long:'):callers.index('; Movement key bitwise')]
    stage=(ROOT/'Core/part00.asm').read_text()
    stage=stage[stage.index('Part00_RoomSprites:'):stage.index('if !ENABLE_PART00_CHECKPOINT == 1\n; Room')]
    flags='\n'.join('!'+n+' = 0' for n in ('ENABLE_DREAM_RETURN','DISABLE_SPRITES','ENABLE_DREAM_ENTRY_FX','ENABLE_DREAM_WISDOM_SCENE','ENABLE_DREAM_ROOM_SHEETS','ENABLE_PART00_CHECKPOINT','ENABLE_PART00_ARRIVAL_LINES'))
    with asm.open('a') as out:
        out.write(f'\n!ENABLE_D8_FARORE_GRAPHICS = {enabled}\n'+flags+'\nSprite_CheckActive = $008000\nINDOORS = $1B\nGameState = $7EF3C5\norg $2D8000\n'+callers+stage+'\norg $2DF000\nincsrc "'+str(ROOT/'Sprites/NPCs/farore_d8_follow.asm')+'"\n'+"""
Sprite_HyruleDream_Draw: INC.w $1FF0 : RTS
Sprite_HyruleDream_Prep: INC.w $1FF1 : RTS
Sprite_HyruleDream_Main: INC.w $1FF2 : RTS
Sprite_Farore_Draw: INC.w $1FF3 : RTS
Sprite_Farore_Main: INC.w $1FF4 : RTS
org $06DC5C
  INC.w $1FF6
  RTL
org $09C2D4
  RTS
org $09F000
StageCaller:
  JSR .load
  RTL
.load
  LDA.b #$FF
  JSL Part00_RoomSprites
  INC.w $1FF5 ; native end-of-list must skip this record continuation
  RTS
""")
    proc=subprocess.run(['asar','--no-title-check','--fix-checksum=off','--symbols=wla',str(asm),str(rom)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stdout+proc.stderr
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$',rom.with_suffix('.sym').read_text())}
    return rom.read_bytes(),labels

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--rom',type=Path);a=ap.parse_args();checks=[];admission=None
    if a.rom:
        import hashlib
        data=a.rom.read_bytes();pc=lambda address:(address>>16)*0x8000+(address&0x7FFF)
        assert data[pc(0x02D99F):pc(0x02D99F)+4]==bytes.fromhex('2208f00f')
        assert data[pc(0x0FF008):pc(0x0FF008)+13]==bytes.fromhex('aa0a0aa8e220a90f48abc2206b')
        assert data[pc(0x02DA96):pc(0x02DA96)+6]==bytes.fromhex('bd00988d0c04')
        assert data[pc(0x0F8000)+0x29*2:pc(0x0F8000)+0x29*2+2]==bytes.fromhex('9000')
        assert data[pc(0x0F9800)+0x29]==4, 'actual entrance29 runtime dungeon ID differs'
        admission={'rom_sha256':hashlib.sha256(data).hexdigest(),'entrance':0x29,'room':0x90,'selected_dbr':0x0F,'dungeon_table':0x0F9800,'runtime_040c':4}

    with tempfile.TemporaryDirectory(prefix='oos-farore-presence-') as t:
        p=Path(t);dll=p/'cpu.dylib';subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(dll)],check=True)
        lib=C.CDLL(str(dll));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        rom,labels=assemble(p)
        for room,crystal in [(r,c) for r in (0x90,0x91,0x92,0x93,0x94,0x95,0xA0,0xA6,0xA7,0xB0,0x96,0x190,0x1A6) for c in (0,0x80)]:
            f=PresenceFixture(lib,rom,labels)
            try:
                setup(f,room,crystal);f.put(2,3)
                call(f,'D8Farore_Stage',db=0x09)
                yes=(room in set(range(0x90,0x96))|{0xA0,0xA6}) and not crystal
                assert f.get(0xDD3)==(8 if yes else 0),(hex(room),crystal)
                if yes:
                    assert (f.get(0xE23),f.get(0xE33),f.get(0xE93),f.get(0xEB3),f.get(2))==(0x73,0xD8,room&255,room>>8,4)
                    call(f,'D8Farore_Stage',db=0x09)
                    assert sum(f.get(0xDD0+i)!=0 for i in range(16))==1,'duplicate'
                checks.append(f'stage-{room:03X}-{crystal:02X}')
            finally:f.close()
        for invalid in ('outdoor','wrong-dungeon','full-slots'):
            f=PresenceFixture(lib,rom,labels)
            try:
                setup(f)
                if invalid=='outdoor':f.put(0x1B,0)
                elif invalid=='wrong-dungeon':f.put(0x40C,8)
                else:
                    for i in range(16):f.put(0xDD0+i,9);f.put(0xE20+i,0xA7)
                before=bytes(f.ram);call(f,'D8Farore_Stage',db=0x09)
                assert all(x==y or 0x100<=i<0x200 for i,(x,y) in enumerate(zip(before,f.ram)))
                checks.append(invalid)
            finally:f.close()
        for scenario in ('join','blocked-straight','all-blocked','A6-wait','pause','completion','stale-room','B0','96','transition-room-change'):
            f=PresenceFixture(lib,rom,labels)
            try:
                room=0xA6 if scenario=='A6-wait' else 0x90;setup(f,room);f.put(2,6)
                call(f,'D8Farore_Stage',db=0x09)
                # Native $0DB874/$0DB89E clear these before custom Prep.
                f.put(0xE96,0);f.put(0xEB6,0);f.put(0xDB6,0)
                f.call('D8Farore_Prep',long_return=True)
                assert (f.get(0xE96),f.get(0xEB6))==(room&255,room>>8)
                if scenario=='blocked-straight':f.tile=lambda x,y:1 if 0x100<=x<0x110 and y>=0x120 else 0
                if scenario=='all-blocked':f.tile=lambda x,y:0x20
                if scenario=='pause':f.put(0x11,1)
                if scenario=='transition-room-change':f.put(0x11,1);f.word(0xA0,0x96)
                if scenario=='completion':f.put(0x7EF37A,0x80)
                if scenario=='stale-room':f.word(0xA0,0x91)
                if scenario in ('B0','96'):f.word(0xA0,int(scenario,16))
                before=bytes(f.ram[:12]);f.cpu.db=0x30
                f.call('D8Farore_Frame',long_return=True)
                assert f.cpu.db==0x30 and f.ram[:12]==before
                placed=scenario in ('join','blocked-straight','A6-wait')
                assert bool(f.get(0xDB6))==placed
                assert f.cpu.c==placed
                if placed:
                    x=f.get(0xD16)|f.get(0xD36)<<8;y=f.get(0xD06)|f.get(0xD26)<<8
                    assert (x,y)==({'join':(0x100,0x120),'blocked-straight':(0xE0,0x120),'A6-wait':(0xC38,0x1440)}[scenario])
                    # Moving Link engages ordinary following but never drags the A6 anchor.
                    f.word(0x22,0x190);f.call('D8Farore_Frame',long_return=True)
                    assert (f.get(0xD16)|f.get(0xD36)<<8)==(x if scenario=='A6-wait' else x+1)
                if scenario in ('completion','stale-room','B0','96'):assert f.get(0xDD6)==0
                if scenario=='transition-room-change':
                    assert f.get(0xDD6)==8, 'transition must not discard pending new-room actor'
                    f.put(0x11,0);f.call('D8Farore_Frame',long_return=True)
                    assert f.get(0xDD6)==0, 'settled excluded room must release actor'
                checks.append(scenario)
            finally:f.close()
        # Actual production dispatch and room-list caller, including flag-off legacy routing.
        for enabled in (0,1):
            q=p/f'callers{enabled}';q.mkdir();caller_rom,caller_labels=assemble(q,enabled)
            for own in (False,True):
                f=PresenceFixture(lib,caller_rom,caller_labels)
                try:
                    setup(f);f.put(0x7EF3C5,3);f.put(2,6)
                    f.call('StageCaller',long_return=True)
                    assert f.get(0xDD6)==(8 if enabled else 0)
                    assert f.get(0x1FF5)==0
                    f.put(0xDD6,9);f.put(0xE36,0xD8 if own else 0)
                    f.put(0xE96,0);f.put(0xEB6,0)
                    f.call('Sprite_Farore_Prep',long_return=True)
                    assert f.get(0x1FF1)==int(not(enabled and own))
                    if enabled and own:
                        assert (f.get(0xE96),f.get(0xEB6))==(0x90,0)
                        assert f.get(0xE46)==0x82 and f.get(0xDA6)==0, 'two body OAM pieces, reset follow latch'
                    f.call('Sprite_Farore_Long',long_return=True)
                    assert f.get(0x1FF0)==int(not(enabled and own))
                    assert f.get(0x1FF3)==int(bool(enabled and own))
                    assert f.get(0x1FF6)==int(bool(enabled and own)), 'native shadow must be D8 placed-only'
                    assert f.get(0x1FF2)==0 and f.get(0x1FF4)==0
                    checks.append(f'actual-callers-flag{enabled}-owned{own}')
                finally:f.close()
        size=labels['D8Farore_CompanionEnd']-labels['D8Farore_CompanionStart']
    result={'status':'PASS','actual_rom_admission':admission,'size':size,'checks':checks,'scope':'CPU-only presence/placement and actual production callers; authored A6 anchor with stubbed terrain; no P2/solo control, plate weight, real placement or ROM proof'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','size':size,'checks':len(checks)}))
if __name__=='__main__':main()
