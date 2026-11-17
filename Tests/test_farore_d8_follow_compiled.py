#!/usr/bin/env python3
"""Floor-aware following; no real room path or animation proof."""
import argparse,ctypes as C,json,re,subprocess,tempfile
from pathlib import Path
from d4_compiled_fight_check import Cpu
from test_farore_d8_presence_compiled import assemble,PresenceFixture,setup,ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);ap.add_argument('--compiled-shadow-rom',type=Path);ap.add_argument('--symbols',type=Path);ap.add_argument('--runner',type=Path);ap.add_argument('--control-source',type=Path);a=ap.parse_args();checks=[]
    assert all(v is not None for v in (a.compiled_shadow_rom,a.symbols,a.runner)) or all(v is None for v in (a.compiled_shadow_rom,a.symbols,a.runner)), 'compiled shadow inputs are atomic'
    with tempfile.TemporaryDirectory(prefix='oos-farore-follow-') as t:
        p=Path(t);rom,labels=assemble(p)
        image=p/'follow.sfc';image.write_bytes(rom)
        dll=p/'cpu.dylib';subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(dll)],check=True)
        lib=C.CDLL(str(dll));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        scenarios={'right':(0x140,0x100,0x101,0x100),'left':(0xC0,0x100,0xFF,0x100),'north':(0x100,0xC0,0x100,0xFF),'south':(0x100,0x140,0x100,0x101),'near':(0x118,0x118,0x100,0x100),'pit':(0x140,0x100,0x100,0x100),'wall':(0x140,0x100,0x100,0x100),'other-layer':(0x140,0x100,0x100,0x100),'link-state':(0x140,0x100,0x100,0x100),'blocked-x-y-open':(0x140,0x140,0x100,0x101)}
        for name,(lx,ly,ex,ey) in scenarios.items():
            f=PresenceFixture(lib,image.read_bytes(),labels)
            try:
                setup(f);f.word(0x22,lx);f.word(0x20,ly);f.put(0xD16,0);f.put(0xD36,1);f.put(0xD06,0);f.put(0xD26,1)
                if name=='pit':f.tile=lambda x,y:0x20
                if name=='wall':f.tile=lambda x,y:1
                if name=='blocked-x-y-open':f.tile=lambda x,y:1 if x>=0x110 else 0
                if name=='other-layer':f.put(0xEE,1)
                if name=='link-state':f.put(0x5D,0x13)
                f.cpu.db=0x30;f.call('D8Farore_Follow',long_return=True)
                assert f.cpu.db==0x30
                assert (f.get(0xD16)|f.get(0xD36)<<8,f.get(0xD06)|f.get(0xD26)<<8)==(ex,ey),name
                assert (f.get(0x22)|f.get(0x23)<<8,f.get(0x20)|f.get(0x21)<<8)==(lx,ly),'Link moved'
                checks.append(name)
            finally:f.close()
        def actor(f,x=0x100,y=0x1300):
            setup(f);f.word(0x22,x);f.word(0x20,y)
            f.put(0xD16,x&255);f.put(0xD36,x>>8);f.put(0xD06,y&255);f.put(0xD26,y>>8)
            f.put(0xDB6,1);f.put(0xE96,0x90);f.put(0xEB6,0);f.put(0xDD6,9)
        def pos(f):return f.get(0xD16)|f.get(0xD36)<<8,f.get(0xD06)|f.get(0xD26)<<8
        def follow(f):
            before=(f.cpu.sp,f.cpu.db);f.call('D8Farore_Follow',long_return=True);assert f.cpu.sp==before[0] and f.cpu.db==before[1]
        f=PresenceFixture(lib,image.read_bytes(),labels)
        try:
            actor(f);f.word(0x22,0x129);follow(f)
            assert pos(f)==(0x101,0x1300) and f.get(0xDA6)==1
            for _ in range(9):follow(f)
            assert pos(f)==(0x109,0x1300) and f.get(0xDA6)==0 and f.get(0xDC6)==0
            held=pos(f)
            for delta in [33,40,34,39,35,38,36,37]*3:
                f.word(0x22,held[0]+delta);follow(f)
                assert pos(f)==held and f.get(0xDA6)==0 and f.get(0xDC6)==0
            checks.append('32-stop40-start-hysteresis-no-jitter')
            actor(f);f.word(0x20,0x12C0);f.put(0x1A,0);follow(f);assert f.get(0xDC6)==3
            f.put(0x1A,8);follow(f);assert f.get(0xDC6)==4
            f.word(0x20,pos(f)[1]-32);follow(f);assert f.get(0xDC6)==0
            f.word(0x22,pos(f)[0]+64);follow(f);assert f.get(0xDC6)==0
            checks.append('north-walk-frames-movement-only-stop-turn')
            f.put(0xDA6,1);f.put(0xDC6,4);f.put(0xEE,1);held=pos(f);follow(f)
            assert pos(f)==held and f.get(0xDA6)==0 and f.get(0xDC6)==0
            checks.append('layer-hold-clears-animation-latch')
        finally:f.close()
        for facing,delta in [(0,(0,32)),(2,(0,-32)),(4,(32,0)),(6,(-32,0))]:
            f=PresenceFixture(lib,image.read_bytes(),labels)
            try:
                actor(f);f.put(0xDB6,0);f.put(0x2F,facing);f.call('D8Farore_Frame',long_return=True)
                assert pos(f)==(0x100+delta[0],0x1300+delta[1]) and f.get(0xDB6)==1
                checks.append('behind-join-facing-'+str(facing))
            finally:f.close()
        for scenario in ['blocked-to-clear','door-room-wrap-to-clear','side-fallback','no-centred-overlap']:
            f=PresenceFixture(lib,image.read_bytes(),labels)
            try:
                actor(f);f.put(0xDB6,0);f.put(0x2F,0)
                if scenario in ('blocked-to-clear','no-centred-overlap'):f.tile=lambda x,y:1
                if scenario=='door-room-wrap-to-clear':f.word(0x20,0x13D8)
                if scenario=='side-fallback':f.tile=lambda x,y:1 if 0x100<=x<0x110 and y>=0x1320 else 0
                f.call('D8Farore_Frame',long_return=True)
                if scenario=='side-fallback':assert pos(f)==(0xE0,0x1320) and f.get(0xDB6)==1
                else:
                    assert f.get(0xDB6)==0
                    if scenario=='door-room-wrap-to-clear':assert not f.queries
                    f.tile=lambda x,y:0
                    if scenario=='door-room-wrap-to-clear':f.word(0x20,0x13A0)
                    f.call('D8Farore_Frame',long_return=True)
                    assert f.get(0xDB6)==1 and pos(f)==(0x100,(0x13C0 if scenario=='door-room-wrap-to-clear' else 0x1320))
                checks.append(scenario)
            finally:f.close()
        # Native STOP8159830a accepted a disconnected point behind the south
        # wall, then could not follow. Preserve that exact source as the negative
        # control; the terrain strips here are explicit synthetic regressions,
        # since the old native caller captured OAM/VRAM, not a collision plane.
        versions=[('connected',image.read_bytes(),labels)]
        if a.control_source:
            import test_farore_d8_presence_compiled as presence
            saved_root=presence.ROOT;presence.ROOT=a.control_source
            try:
                control=p/'point_only_control';control.mkdir();cr,cl=presence.assemble(control)
            finally:presence.ROOT=saved_root
            versions.append(('old-native-STOP-source',cr,cl))
        for version,version_rom,version_labels in versions:
            for scenario in ['thin-wall-disconnected','door-boundary','footbox-middle-cell','footbox-room-wrap']:
                f=PresenceFixture(lib,version_rom,version_labels)
                try:
                    actor(f,y=0x1380);f.put(0xDB6,0);f.put(0x2F,0)
                    if scenario=='thin-wall-disconnected':f.tile=lambda x,y:1 if 0x1398<=y<0x13A0 else 0
                    if scenario=='door-boundary':f.tile=lambda x,y:0x8E if 0x1380<=y<0x1398 else 0
                    if scenario.startswith('footbox-'):
                        f.word(8,0x101 if scenario=='footbox-middle-cell' else 0x100);f.word(10,0x1300 if scenario=='footbox-middle-cell' else 0x13ED)
                        if scenario=='footbox-middle-cell':f.tile=lambda x,y:1 if 0x108<=x<0x110 else 0
                        f.call('D8Farore_CheckFootprintLong',long_return=True);assert f.cpu.c==(version=='connected'),(version,scenario)
                    else:
                        f.call('D8Farore_Frame',long_return=True);assert bool(f.get(0xDB6))==(version!='connected'),(version,scenario)
                        if version=='connected':
                            f.tile=lambda x,y:0;f.call('D8Farore_Frame',long_return=True)
                            assert f.get(0xDB6)==1 and pos(f)==(0x100,0x13A0),'pending connection never recovered'
                    checks.append(version+'-'+scenario)
                finally:f.close()
        size=labels['D8Farore_FollowEnd']-labels['D8Farore_FollowStart']
    actual=[]
    if a.compiled_shadow_rom:
        labels={m[2].removeprefix('Oracle_'):int(m[1].replace(':',''),16) for line in a.symbols.read_text().splitlines() if (m:=re.match(r'([0-9A-Fa-f]{2}:[0-9A-Fa-f]{4}) (\S+)',line))}
        for name,x,change,visible in [('visible',64,{},True),('negative-partial',-8,{},True),('negative-carry-to-zero',-4,{},True),('last-right-pixel',251,{},True),('right-clipped',252,{},False),('positive-no9bitwrap',510,{},False),('negative-clipped',-12,{},False),('first-left-pixel',-11,{},True),('wrong-dungeon',64,{0x40C:8},False),('outdoor',64,{0x1B:0},False),('full-room-alias',64,{0xA1:1},False),('completed',64,{0xF37A:0x80},False),('native-offscreen',64,{0xF06:1},False)]:
            b=bytearray(65536);b[0x800:0x810]=bytes(range(16));b[0xA00:0xA04]=bytes([2,2,0xFF,0xFF])
            for at,value in {0x1B:1,0xA0:0x90,0x40C:4,0xDD6:9,0xE46:0x82,0xE66:0x30,0xD06:0x40,0xD26:0x13,0x05:0x30,**change}.items():b[at]=value
            for at,value in [(0x00,x&65535),(0x90,0x800),(0x92,0xA00),(0xE8,0x1300)]:b[at:at+2]=value.to_bytes(2,'little')
            q=dict(entry=labels['D8Farore_DrawGroundShadow'],reset_ram=True,registers=dict(a=0x5A,x=6,y=0x77,p=0x30,db=0x30,d=0,sp=0x1FFF),writes=[dict(address=0x7E0000,bytes=list(b))],reads=[dict(address=0x7E0800,length=16),dict(address=0x7E0A00,length=4)],max_steps=10000)
            proc=subprocess.run([str(a.runner),str(a.compiled_shadow_rom)],input=json.dumps(q)+'\n',capture_output=True,text=True,check=True);j=json.loads(proc.stdout);assert j['returned'],name;oam=bytes(j['reads'][0]['bytes']);ext=bytes(j['reads'][1]['bytes']);assert oam[:8]==bytes(range(8)) and ext[:2]==bytes([2,2]),(name,'body OAM overwritten')
            if visible:assert oam[8:12]==bytes([(x+4)&255,83,0x38,0x38]) and ext[2]==(1 if x+4<0 else 0),(name,oam.hex(),ext.hex())
            else:assert oam==bytes(range(16)) and ext==bytes([2,2,0xFF,0xFF]),(name,'clipped/foreign OAM written')
            assert all(j['registers'][k]==v for k,v in [('x',6),('db',0x30),('d',0),('sp',0x1FFF),('p',0x30)]),(name,j['registers'])
            actual.append(name)
    result={'status':'PASS','helper_bytes_including_join':size,'wrapper_bytes':8,'caller_bytes':10,'checks':checks,'actual_compiled_shadow_controls':actual,'scope':'synthetic-location CPU test with actual presence footprint helper and stubbed terrain; no native/pathfinding/control proof'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
