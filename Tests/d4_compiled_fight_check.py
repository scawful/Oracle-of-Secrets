#!/usr/bin/env python3
"""Execute compiled private D4 routines with Lakesnes' existing 65816 core.

Most engine calls are explicit stubs; dedicated allocation controls execute real
vanilla region/defer routines. JumpTableLocal also executes its real ROM bytes.
This proves bounded CPU behavior, not SNES rendering, collision or controller play.
No emulator process, socket, save, shared ROM or ROM file write is used.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parents[1]


class Cpu(C.Structure):
    _fields_=([(n,C.c_void_p) for n in ('mem','read','write','idle')]+
              [(n,C.c_uint16) for n in ('a','x','y','sp','pc','dp')]+
              [(n,C.c_uint8) for n in ('k','db')]+
              [(n,C.c_bool) for n in ('c','z','v','n','i','d','xf','mf','e',
                  'waiting','stopped','irqWanted','nmiWanted','intWanted','resetWanted')])


class Fixture:
    def __init__(self,lib,rom,labels):
        self.lib,self.rom,self.labels=lib,rom,labels
        self.ram=bytearray(0x20000);self.stubs={};self.calls=[];self.writes=[];self.bad_writes=[]
        self.screen=(128,128);self.direction=0;self.distance=32;self.blocked=False
        self.step_delta=(1,0);self.contact=[];self.speed_calls=[]
        self.read_cb=C.CFUNCTYPE(C.c_uint8,C.c_void_p,C.c_uint32)(lambda _,a:self.read(a))
        self.write_cb=C.CFUNCTYPE(None,C.c_void_p,C.c_uint32,C.c_uint8)(lambda _,a,v:self.write(a,v))
        self.idle_cb=C.CFUNCTYPE(None,C.c_void_p,C.c_bool)(lambda *_:None)
        self.p=lib.cpu_init(None,self.read_cb,self.write_cb,self.idle_cb);self.cpu=self.p.contents
        for n in ('c','z','v','n','i','d','e','waiting','stopped','irqWanted','nmiWanted','intWanted','resetWanted'):setattr(self.cpu,n,False)
        self.cpu.mf=self.cpu.xf=True;self.cpu.dp=0;self.cpu.sp=0x1FF
        self.cpu.a=self.cpu.x=self.cpu.y=0;self.cpu.db=0x2C
        for name in ('Sprite_PrepOamCoord','Sprite_OAM_AllocateDeferToPlayer','OAM_AllocateFromRegionA',
                     'Sprite_CheckDamageFromPlayer','Sprite_PlayerCantPassThrough',
                     'Sprite_DirectionToFacePlayer','Sprite_ApplySpeedTowardsPlayer',
                     'Sprite_CheckTileCollision','Sprite_Move','GetDistance8bit_Long',
                     'Sprite_CheckDamageToPlayerSameLayer','SpriteSFX_QueueSFX2WithPan','Link_ReceiveItem'):
            self.stubs[self.addr(name)]=name

    def addr(self,n):return self.labels.get('Oracle_'+n,self.labels.get(n))

    @staticmethod
    def ram_offset(a):
        bank=a>>16;lo=a&65535
        if bank in (0x7E,0x7F):return a-0x7E0000
        if bank&0x7F<0x40 and lo<0x2000:return lo
        return None

    def read(self,a):
        if a in self.stubs:return 0x6B # explicit engine ABI stubs return RTL
        offset=self.ram_offset(a)
        if offset is not None:return self.ram[offset]
        if a&0x8000:
            pc=((a>>16)&0x7F)*0x8000+(a&0x7FFF)
            return self.rom[pc] if pc<len(self.rom) else 0
        return 0

    def write(self,a,v):
        offset=self.ram_offset(a)
        if offset is None:
            self.bad_writes.append((a,v));return
        self.ram[offset]=v;self.writes.append((a,v))

    def get(self,a):return self.read(a)
    def put(self,a,v):self.write(a,v&255)
    def word(self,a,v):self.put(a,v);self.put(a+1,v>>8)
    def spr(self,n,v=None,slot=6):
        a=self.addr(n)+slot
        if v is None:return self.get(a)
        self.put(a,v)

    def acc(self,v):
        self.cpu.a=(self.cpu.a&0xFF00)|(v&255);self.cpu.z=(v&255)==0;self.cpu.n=bool(v&128)

    def stub(self,name):
        self.calls.append(name);x=self.cpu.x
        if name=='Sprite_PrepOamCoord':
            self.word(0,self.screen[0]&65535);self.word(2,self.screen[1]&65535)
        elif name in ('Sprite_OAM_AllocateDeferToPlayer','OAM_AllocateFromRegionA'):self.word(0x90,0x800);self.word(0x92,0xA00)
        elif name=='Sprite_DirectionToFacePlayer':self.cpu.y=self.direction
        elif name=='Sprite_ApplySpeedTowardsPlayer':
            speed=self.cpu.a&255;self.speed_calls.append(speed)
            dx,dy=((1,0),(-1,0),(0,1),(0,-1))[self.direction]
            self.spr('SprXSpeed',dx*speed,x);self.spr('SprYSpeed',dy*speed,x)
        elif name=='Sprite_CheckTileCollision':self.acc(int(self.blocked))
        elif name=='Sprite_Move':
            self.spr('SprX',self.spr('SprX',slot=x)+self.step_delta[0],x)
            self.spr('SprY',self.spr('SprY',slot=x)+self.step_delta[1],x)
        elif name=='GetDistance8bit_Long':self.acc(self.distance)
        elif name=='Sprite_CheckDamageToPlayerSameLayer':
            self.contact.append(tuple(self.spr(n,slot=x) for n in ('SprX','SprY','SprHitbox')))

    def call(self,name,x=6,a=0,limit=20000,long_return=False,m8=True):
        cpu=self.cpu;cpu.x=x;cpu.a=(cpu.a&0xFF00)|(a&255)
        address=self.addr(name);assert address is not None,name
        cpu.k=address>>16;cpu.pc=address&65535
        sp=cpu.sp
        if long_return:
            self.put(sp,address>>16);self.put(sp-1,0x6F);self.put(sp-2,0xFF);cpu.sp-=3
        else:
            self.put(sp,0x6F);self.put(sp-1,0xFF);cpu.sp-=2
        for _ in range(limit):
            address=cpu.k<<16|cpu.pc
            if address==(self.addr(name)&0xFF0000)|0x7000:
                assert not self.bad_writes,('unexpected non-WRAM writes',self.bad_writes)
                assert cpu.sp==sp,(name,'stack',cpu.sp,sp)
                assert cpu.mf==m8 and cpu.xf,(name,'M/X exit')
                assert cpu.x==x,(name,'actor X lost',cpu.x,x)
                return
            if address in self.stubs:self.stub(self.stubs[address])
            self.lib.cpu_runOpcode(self.p)
        raise AssertionError((name,'instruction limit',f'{cpu.k:02X}:{cpu.pc:04X}',cpu.sp))

    def close(self):self.lib.cpu_free(self.p)


def check_camera_cache(lib,rom,labels):
    """Run actual cache helper bytes, including its RTL and displaced ABI."""
    cases=(
        (0x26,0x14,0,0,3095,2253,3095,2253),
        (0x46,0x1C,0,0,3095,2253,3095,2253),
        (0x46,0x14,2,2,3095,2253,3095,2253),
        (0x46,0x14,2,0,3095,2253,3095,2304),
        (0x46,0x14,0,0,3095,2323,3072,2320),
        (0x46,0x14,0,0,3060,2296,3072,2304),
        (0x46,0x14,0,0,3072,2312,3072,2312),
    )
    for room,layout,wide,tall,x,y,ex,ey in cases:
        f=Fixture(lib,rom,labels)
        f.word(0xA0,room);f.word(0x40E,layout)
        f.put(0xA6,wide);f.put(0xA7,tall)
        f.word(0x600,2304);f.word(0x604,2320)
        f.word(0x608,3072);f.word(0x60C,3072)
        f.word(0xE2,x);f.word(0xE0,x-8)
        f.word(0xE8,y);f.word(0xE6,y-4)
        for address in (0x11E,0x120):f.word(address,x)
        for address in (0x122,0x124):f.word(address,y)
        f.word(0x61C,150);f.word(0x61E,152)
        f.word(0x618,324);f.word(0x61A,326)
        f.word(0x20,2359);f.word(0x22,3425);f.word(0,0xBEEF)
        before=bytes(f.ram);f.cpu.y=0x37;f.cpu.c=True;f.cpu.db=0x7E
        f.call('D4Zora_CacheRoomCamera',long_return=True,m8=False)
        word=lambda a:f.get(a)|(f.get(a+1)<<8)
        assert (word(0xE2),word(0xE8))==(ex,ey),(room,layout,wide,tall,x,y)
        assert word(0xE0)==ex-8 and word(0xE6)==ey-4,'BG scroll offset lost'
        assert all(word(a)==ex for a in (0x11E,0x120,0x7EC180))
        assert all(word(a)==ey for a in (0x122,0x124))
        assert (word(0x61C),word(0x61E))==((150+ex-x)&65535,(152+ex-x)&65535)
        assert (word(0x618),word(0x61A))==((324+ey-y)&65535,(326+ey-y)&65535)
        assert word(0)==0xBEEF and f.cpu.y==0x37 and f.cpu.c and f.cpu.db==0x7E
        assert f.cpu.a==ex and f.cpu.dp==0,'Displaced LDA/STA ABI changed'
        allowed=set(range(0x100,0x200))|{0xC180,0xC181}
        for a in (0xE0,0xE2,0xE6,0xE8,0x11E,0x120,0x122,0x124,0x618,0x61A,0x61C,0x61E):allowed.update((a,a+1))
        assert all(a in allowed or old==new for a,(old,new) in enumerate(zip(before,f.ram))),'Unexpected Link/actor/progression write'
        f.close()
    return len(cases)


def check_palette_handoff(lib,rom,labels):
    """Fade setup owns display colours; ordinary-play prep updates both."""
    phases=((6,0),(7,14),(7,1),(7,0))
    rows=(('protector_head',0x62),('protector_body',0x82),('warden_armor',0xA2),('warden_iron',0xC2))
    for module,submodule in phases:
        f=Fixture(lib,rom,labels)
        f.ram[0xC400:0xC700]=bytes([0x55])*0x300
        f.put(0x10,module);f.put(0x11,submodule)
        before=bytes(f.ram);f.cpu.y=0x37
        f.call('D4Zora_LoadPalettes')
        immediate=(module,submodule)==(7,0)
        allowed=set(range(0x100,0x200))|{0x15}
        for name,offset in rows:
            address=f.addr('D4Zora_Palette_'+name)
            expected=bytes(f.read(address+i) for i in range(14))
            assert f.ram[0xC400+offset:0xC400+offset+14]==expected
            allowed.update(range(0xC400+offset,0xC400+offset+14))
            if immediate:
                assert f.ram[0xC600+offset:0xC600+offset+14]==expected
                allowed.update(range(0xC600+offset,0xC600+offset+14))
        if not immediate:assert f.ram[0xC600:0xC700]==before[0xC600:0xC700],'Display buffer filled before fade'
        assert f.cpu.y==0x37 and all(a in allowed or old==new for a,(old,new) in enumerate(zip(before,f.ram)))
        f.close()
    return len(phases)



def check_real_allocator(lib,rom,labels,candidate):
    """Exercise actual region/defer code with normal and every fallback slot."""
    cases=0
    for index,(name,frame) in enumerate(candidate['frames'].items()):
        for fallback in range(-1,8):
            for near in (False,True):
                f=Fixture(lib,rom,labels)
                for routine in ('Sprite_OAM_AllocateDeferToPlayer','OAM_AllocateFromRegionA'):
                    del f.stubs[f.addr(routine)]
                f.spr('SprFrame',index)
                f.spr('SprNbrOAM',1 if name.startswith('protector_') else 14)
                f.spr('SprX',128);f.spr('SprY',128)
                f.word(0x22,128 if near else 192);f.word(0x20,128)
                # Sprite dispatch supplies a normal OAM cursor before drawing.
                f.word(0x90,0x830);f.word(0x92,0xA2C)
                f.word(0xFE0,0x30 if fallback<0 else 0x170)
                f.word(0xFE2,0x1D0 if fallback<0 else 0x1F0)
                f.word(0xFEC,max(0,fallback));f.word(0xFEE,max(0,fallback))
                sentinel=bytes(range(0x20))
                f.ram[0xAA0:0xAC0]=sentinel
                f.writes.clear()
                f.call('D4Zora_Draw')
                overflow=[(a,v) for a,v in f.writes if 0xAA0<=(a&0xFFFF)<0xB00]
                assert not overflow,(name,fallback,near,'OAM overflow into graphics/mask state',overflow)
                assert f.ram[0xAA0:0xAC0]==sentinel,(name,'resource/dive canary')
                low=f.get(0x90)|(f.get(0x91)<<8)
                high=f.get(0x92)|(f.get(0x93)<<8)
                n=len(frame['oam'])
                assert 0x800<=low and low+n*4<=0xA00,(name,'OAM low bounds',low,n)
                assert 0xA20<=high and high+n<=0xAA0,(name,'OAM auxiliary bounds',high,n)
                assert not f.bad_writes
                cases+=1;f.close()
    return cases


def check(lib,rom,labels,candidate):
    results={};f=Fixture(lib,rom,labels)
    # All signed offsets, X flip properties, OAM size/X9, clipping and cursors
    # execute the compiled draw loop, including 16-bit accumulator stores.
    screens=((128,128),(-16,128),(0,128),(255,128),(256,128),(128,-16),(128,0),(128,239),(128,256))
    for index,(name,frame) in enumerate(candidate['frames'].items()):
        for sx,sy in screens:
            f.screen=(sx,sy);f.ram[0x800:0xA40]=b'\xA5'*0x240;f.spr('SprFrame',index)
            f.call('D4Zora_Draw')
            ox,oy=frame['runtime_origin']
            for i,e in enumerate(frame['oam']):
                x=(sx+e['x']+ox)&65535;y=(sy+e['y']+oy)&65535
                prop=0x31|(dict(protector_head=3,protector_body=4,warden_armor=5,warden_iron=6)[e['palette']]<<1)|(0x40 if e.get('flip_x') else 0)
                expected=bytes((x&255,(y&255) if ((y+16)&65535)<256 else 0xF0,e['char'],prop))
                assert f.ram[0x800+i*4:0x804+i*4]==expected,(name,sx,sy,i,'OAM')
                assert f.ram[0xA00+i]==2|((x>>8)&1),(name,'X9/size')
            n=len(frame['oam']);assert f.ram[0x800+n*4]==0xA5 and f.ram[0xA00+n]==0xA5
    results['real_allocator_cases']=check_real_allocator(lib,rom,labels,candidate)
    results['compiled_draw_cases']=len(candidate['frames'])*len(screens)
    for direction in range(4):
        f.spr('SprMiscC',direction)
        for phase in range(4):
            f.call('D4Warden_SelectCharge',a=phase)
            assert f.spr('SprFrame')==candidate['lookups']['Charge'][direction*4+phase]
            f.spr('SprMiscA',phase*8);f.call('D4Warden_SelectWalk')
            assert f.spr('SprFrame')==candidate['lookups']['Walk'][direction*4+phase]
        for phase in range(5):
            f.call('D4Warden_SelectSlam',a=phase)
            assert f.spr('SprFrame')==candidate['lookups']['Slam'][direction*5+phase]
        f.call('D4Warden_SelectVent');assert f.spr('SprFrame')==candidate['lookups']['Vent'][direction]
    results['direction_phase_lookups']=56
    f.close()
    def fresh():
        m=Fixture(lib,rom,labels)
        for n,v in (('SprState',9),('SprType',0x11),('SprSubtype',3),('SprHealth',24),('SprX',128),('SprY',128),('SprHitbox',7)):m.spr(n,v)
        m.word(0x22,128);m.word(0x20,128)
        return m
    f=fresh();f.call('D4Warden_Main');assert (f.spr('SprAction'),f.spr('SprTimerA'))==(1,48)
    f.spr('SprTimerA',0);f.call('D4Warden_Main');assert (f.spr('SprAction'),f.spr('SprTimerA'))==(2,40)
    speed_calls=len(f.speed_calls);f.direction=3
    f.call('D4Warden_Main');assert f.spr('SprMiscC')==0 and len(f.speed_calls)==speed_calls
    f.spr('SprTimerA',0);f.call('D4Warden_Main');assert (f.spr('SprAction'),f.spr('SprTimerA'))==(3,24)
    f.blocked=True;f.call('D4Warden_Main');assert (f.spr('SprAction'),f.spr('SprTimerA'))==(9,56)
    f.spr('SprTimerA',0);f.call('D4Warden_Main');assert (f.spr('SprAction'),f.spr('SprMiscB'))==(1,1)
    f.blocked=False;f.spr('SprTimerA',0);f.call('D4Warden_Main');assert f.spr('SprAction')==4
    for expected,timer in ((5,28),(6,4),(7,40),(8,16),(1,48)):
        f.spr('SprTimerA',0);f.call('D4Warden_Main')
        assert (f.spr('SprAction'),f.spr('SprTimerA'))==(expected,timer)
    assert len(f.contact)==2 # charge contact + one strike call
    results['charge_slam_cycle']=True;f.close()
    # Gate controls: do not start from the gallery, rescue side or wrong floor.
    for x,y,floor in ((256+128,128,0),(128,256+128,0),(128,128,1),(16,128,0),(128,32,0)):
        f=fresh();f.word(0x22,x);f.word(0x20,y);f.put(0xEE,floor)
        f.call('D4Warden_Main');assert f.spr('SprAction')==0;f.close()
    for action in range(10):
        f=fresh();f.spr('SprAction',action);f.spr('SprTimerA',10)
        f.call('D4Warden_Main')
        assert bool(f.get(0xE66)&0x40)==(action<7),(action,'armor window')
        f.close()
    results['arena_and_armor_controls']=15
    # Body and temporary anchor collision, with full position restoration.
    f=fresh()
    for d,dx in enumerate((9,-9,-14,14)):
        f.spr('SprMiscC',d);f.call('D4Warden_AnchorDamage')
        assert f.contact[-1]==(128+dx,139,9)
        assert tuple(f.spr(n) for n in ('SprX','SprY','SprHitbox'))==(128,128,7)
    for x,y,delta,blocked in ((48,128,(-1,0),True),(208,128,(1,0),True),(128,80,(0,-1),True),(128,208,(0,1),True),(128,128,(1,1),False)):
        f.spr('SprX',x);f.spr('SprY',y);f.step_delta=delta;f.call('D4Warden_MoveBounded')
        assert f.cpu.c==blocked
        assert (f.spr('SprX'),f.spr('SprY'))==((x,y) if blocked else (x+delta[0],y+delta[1]))
    results['anchor_and_boundary_cases']=9;f.close()
    for health,present,latch,expected in ((13,True,0,False),(12,False,0,False),(12,True,1,False),(12,True,0,True)):
        f=fresh();f.spr('SprHealth',health);f.spr('SprMiscD',latch);f.spr('SprTimerA',17)
        if present:
            for n,v in (('SprState',9),('SprType',0xB8),('SprSubtype',2)):f.spr(n,v,12)
        f.call('D4Warden_TryValveAssist')
        assert f.spr('SprTimerA')==(112 if expected else 17)
        if expected:
            assert f.spr('SprMiscD')==1 and f.spr('SprMiscA',slot=12)==1 and f.spr('SprTimerB',slot=12)==48
            assert f.spr('SprAction',slot=12)==0 and f.get(0x7EF302)==0
            f.spr('SprTimerA',16);f.call('D4Warden_TryValveAssist');assert f.spr('SprTimerA')==16
        f.close()
    results['valve_controls']=5
    for state in (9,6,0):
        f=fresh();f.spr('SprState',state);f.put(0xFE,1)
        for n,v in (('SprState',9),('SprType',0xB8),('SprSubtype',2)):f.spr(n,v,12)
        f.spr('SprMiscA',1,12);f.call('D4Zora_ProtectorMain',x=12)
        assert f.get(0x7EF302)==0
        if state:assert f.get(0xFE)==1 and f.spr('SprAction',slot=12)==0
        else:
            assert f.get(0xFE)==0 and f.spr('SprAction',slot=12)==1 and f.spr('SprTimerD',slot=12)==96
            f.spr('SprTimerD',0,12);f.call('D4Zora_ProtectorMain',x=12)
            assert f.get(0x7EF302)==1 and f.spr('SprState',slot=12)==0 and 'Link_ReceiveItem' in f.calls
        f.close()
    results['healing_controls']=3
    return results


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('rom','symbols','candidate','lakesnes','output'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--handoff-only','--camera-only',dest='handoff_only',action='store_true')
    a=ap.parse_args();assert not a.output.exists()
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$',a.symbols.read_text())}
    labels.update({n:int(v,16) for n,v in re.findall(r'(?m)^(\w+)\s*=\s*\$([0-9A-Fa-f]+)',(ROOT/'Core/symbols.asm').read_text())})
    sources=[a.lakesnes/'snes'/n for n in ('cpu.c','cpu.h','statehandler.c','statehandler.h')]
    with tempfile.TemporaryDirectory(prefix='d4-cpu-') as temp:
        library=Path(temp)/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(sources[0]),str(sources[2]),'-o',str(library)],check=True)
        lib=C.CDLL(str(library));lib.cpu_init.restype=C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        results={'camera_cache_cases':check_camera_cache(lib,a.rom.read_bytes(),labels)}
        results['palette_handoff_cases']=check_palette_handoff(lib,a.rom.read_bytes(),labels)
        if not a.handoff_only:
            results.update(check(lib,a.rom.read_bytes(),labels,json.loads((a.candidate/'RECEIPT.json').read_text())))
    report=dict(status='COMPILED_CPU_FIXTURE_PASS',rom_sha256=hashlib.sha256(a.rom.read_bytes()).hexdigest(),
        core_sources={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in sources},results=results,
        scope='Compiled 65816 routines; real allocator bounds controls and JumpTableLocal; other engine services stubbed. Not native gameplay.',native_runtime_qualified=False)
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
