#!/usr/bin/env python3
"""Real compiled D8/base-form callers; actual retained ROM palette routines.
Only Underworld_HandleLayerEffect is an explicit RTL stub. No native PPU proof.
"""
import argparse,ctypes as C,hashlib,json,re,subprocess,tempfile
from pathlib import Path
from d4_compiled_fight_check import Cpu,Fixture
ROOT=Path(__file__).resolve().parents[1]

def block(text,name):
    start=text.index(name+':');opened=text.index('{',start);depth=1;i=opened+1
    while depth:
        depth += (text[i]=='{')-(text[i]=='}');i+=1
    return text[start:i]+'\n'

def sources(ref=None):
    paths=['Masks/mask_routines.asm','Masks/gbc_form.asm','Overworld/time_system.asm']
    return [subprocess.check_output(['git','-C',str(ROOT),'show',ref+':'+p],text=True) if ref else (ROOT/p).read_text() for p in paths]

def assemble(folder,raw,texts):
    folder.mkdir();image=folder/'fixture.sfc';image.write_bytes(raw)
    mask,gbc,clock=texts
    names=['ResetToLinkGraphics','ForceResetMask_GameOver','ForceResetMask_SaveAndQuit']
    names += [n for n in ['LinkGraphics_IsD8','LinkGraphics_ApplyD8Base'] if n+':' in mask]
    body='\n'.join(block(mask,n) for n in names)
    body+='\n'+block(gbc,'LinkState_GameboyInDungeonEntrance')+'\n'+block(gbc,'LoadOverworld_CheckForGbcLink')+'\n'+block(clock,'TimeSystem_UpdateGBCLink')
    asm=folder/'fixture.asm'
    asm.write_text('''lorom
!ENABLE_MASK_R_BINDING = 1
!ENABLE_DIVE_GATE = 0
!ENABLE_HORSE_FORM = 0
!CurrentMask = $02B2
!LinkGraphics = $BC
GaroMask_Clear = $42F073
DekuStick_Drop = $2BB8F5
Palette_ArmorAndGloves = $3A808F
UpdateGbcPalette = $3BF000
org $2C8000
'''+body+'\nFixtureEnd:\n')
    subprocess.run(['asar','--no-title-check','--fix-checksum=off','--symbols=wla',str(asm),str(image)],check=True,capture_output=True)
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$',image.with_suffix('.sym').read_text())}
    return image.read_bytes(),labels

def run(f,name):
    c=f.cpu;address=f.addr(name);sp=c.sp;c.k=address>>16;c.pc=address&65535
    long_return=name!='TimeSystem_UpdateGBCLink'
    if long_return:f.put(sp,address>>16);f.put(sp-1,0x6F);f.put(sp-2,0xFF);c.sp-=3
    else:f.put(sp,0x6F);f.put(sp-1,0xFF);c.sp-=2
    for _ in range(10000):
        pc=c.k<<16|c.pc
        if pc==(address&0xFF0000)|0x7000:
            assert c.sp==sp and c.mf and c.xf and c.db==0x7E and c.dp==0
            assert not f.bad_writes,f.bad_writes
            return
        if pc in f.stubs:f.stub(f.stubs[pc])
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError('instruction ceiling '+name)

def setup(lib,rom,labels,indoor,did,world,mask,bank,room=0x90):
    f=Fixture(lib,rom,labels);f.stubs={0x0AFE80:'native_layer_effect'}
    f.cpu.db=0x7E;f.cpu.x=5;f.cpu.y=0x37
    for a,v in [(0x1B,indoor),(0xFFF,world),(0x2B2,mask),(0xBC,bank),(0x7EF3CA,world*0x40),(0x7EF36C,160),(0x7EF36D,160),(0x7EF3CC,0),(0x7EF35B,0),(0x7EF354,0)]:f.put(a,v)
    f.word(0x40C,did);f.word(0xA0,room);f.word(0x20,0x13D8);f.word(0x22,0x178)
    # Ownership/return/actor/camera memories must be untouched by form correction.
    f.ram[0xC140:0xC172]=bytes(range(50));f.ram[0xD00:0x1000]=bytes((i*3+7)&255 for i in range(0x300))
    f.put(0xFFF,world)
    return f

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--rom',type=Path,required=True);ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    raw=a.rom.read_bytes();assert hashlib.sha256(raw).hexdigest()=='5730b0d2cde607530671e6c1b6516579d69bf1e7442486af56cfa8348a2b0a64','fixture engine ROM differs'
    checks=[];controls=[]
    with tempfile.TemporaryDirectory(prefix='oos-d8-form-') as t:
        p=Path(t);dll=p/'cpu.dylib';subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(dll)],check=True)
        lib=C.CDLL(str(dll));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        candidate=assemble(p/'candidate',raw,sources());control=assemble(p/'control',raw,sources('6a0bd699fbdbd83565e78412e0e71cd3b85fbbe2'))
        callers=['LinkState_GameboyInDungeonEntrance','TimeSystem_UpdateGBCLink']
        rooms=[0x90,0x91,0x92,0x93,0x94,0x95,0x96,0xA0,0xA6,0xA7,0xB0]
        for room in rooms:
            for name in callers:
                for world in (0,1):
                    f=setup(lib,*candidate,1,4,world,6,0x3B,room);before=bytes(f.ram)
                    try:
                        run(f,name);assert (f.get(0x2B2),f.get(0xBC))==(0,0x10)
                        assert f.cpu.x==5 and f.cpu.y==0x37
                        # Only base form, bank, palette callback scratch, NMI counter,
                        # palette rows, and stack may differ. All actors/return data remain.
                        # Native arbitrary-palette loader owns $00..$02; GlovesFix owns
                        # TimeState.SubColor ($7EE018..19), even for indoor colors.
                        allowed=set(range(0x100,0x200))|{0,1,2,0x15,0xBC,0x2B2,0xE018,0xE019}|set(range(0xC4E0,0xC500))|set(range(0xC6E0,0xC700))
                        assert all(i in allowed or x==y for i,(x,y) in enumerate(zip(before,f.ram))),(name,[(hex(i),x,y) for i,(x,y) in enumerate(zip(before,f.ram)) if i not in allowed and x!=y])
                        count=f.get(0x15);run(f,name);assert f.get(0x15)==count,'per-frame palette reload'
                        checks.append(f'{name}/room{room:02X}/world{world}')
                    finally:f.close()
        for name in callers:
            for mask,bank in [(1,0x35),(2,0x36),(3,0x38),(4,0x37),(5,0x39),(7,0x33),(8,0x42)]:
                f=setup(lib,*candidate,1,4,1,mask,bank)
                try:run(f,name);assert (f.get(0x2B2),f.get(0xBC),f.get(0x15))==(mask,bank,0);checks.append(f'{name}/preserve-mask{mask}')
                finally:f.close()
        for name in callers+['ResetToLinkGraphics','ForceResetMask_GameOver','ForceResetMask_SaveAndQuit','LoadOverworld_CheckForGbcLink']:
            for indoor,did,world in [(0,4,1),(1,0x104,1),(1,0x16,1),(1,4,0)]:
                if indoor and did==4:continue
                pair=[]
                for artifact in (control,candidate):
                    f=setup(lib,*artifact,indoor,did,world,6,0x3B);run(f,name);pair.append(f)
                try:
                    old,new=pair
                    assert all(0x100<=i<0x200 or x==y for i,(x,y) in enumerate(zip(old.ram,new.ram))),name
                    assert (old.cpu.a,old.cpu.x,old.cpu.y,old.cpu.c,old.cpu.z,old.cpu.n)==(new.cpu.a,new.cpu.x,new.cpu.y,new.cpu.c,new.cpu.z,new.cpu.n),name
                    checks.append(f'{name}/legacy-{indoor}-{did:04X}-{world}')
                finally:
                    for f in pair:f.close()
        for name in ['ResetToLinkGraphics','ForceResetMask_GameOver','ForceResetMask_SaveAndQuit']:
            for mask,bank in [(0,0x10),(6,0x3B),(2,0x36),(5,0x39)]:
                f=setup(lib,*candidate,1,4,1,mask,bank)
                try:run(f,name);assert (f.get(0x2B2),f.get(0xBC))==(0,0x10);checks.append(name+'/native-reset-mask'+str(mask))
                finally:f.close()
        for name in callers+['ResetToLinkGraphics']:
            f=setup(lib,*control,1,4,1,6,0x3B)
            try:run(f,name);assert (f.get(0x2B2),f.get(0xBC))==(6,0x3B);controls.append(name+'/old-D8-GBC-reproduced')
            finally:f.close()
        size=candidate[1]['FixtureEnd']-0x2C8000;oldsize=control[1]['FixtureEnd']-0x2C8000
    result={'status':'PASS','checks':checks,'count':len(checks),'controls':controls,'fixture_growth':size-oldsize,'scope':'compiled actual callers; real retained ROM base/GBC palettes, Garo/Deku reset helpers; only native layer effect stubbed; no controller/PPU proof'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
