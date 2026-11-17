#!/usr/bin/env python3
"""Compile actual P2 ASM and execute it with the existing Lakesnes CPU fixture.

Synthetic FF image; no game ROM, SNES PPU, DMA timing or controller proof.
External collision/spawn/overlap services are explicit stubs. Changed P2
routines, including held-object stash/restore and NMI guards, execute real bytes.
"""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu, Fixture

ROOT = Path(__file__).resolve().parents[1]


def assemble(folder, player_source):
    folder.mkdir()
    defs = '\n'.join(re.findall(r'(?m)^[A-Za-z_][\w]*\s*=\s*\$[\da-fA-F]+',
        (ROOT/'Core/symbols.asm').read_text() + (ROOT/'Core/sram.asm').read_text()))
    (folder/'player2.asm').write_text(player_source)
    (folder/'player2_hooks.asm').write_bytes((ROOT/'Sprites/Players/player2_hooks.asm').read_bytes())
    asm = folder/'fixture.asm'
    asm.write_text('lorom\n!ENABLE_NATIVE_2P_POC = 1\nInCutScene = $7EF303\n' + defs +
                   '\nincsrc "player2.asm"\n')
    image = folder/'fixture.sfc'
    image.write_bytes(b'\xff' * 0x200000)
    result = subprocess.run(['asar', '--no-title-check', '--fix-checksum=off',
                             '--symbols=wla', str(asm), str(image)], capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr
    labels = {m[3]:int(m[1]+m[2],16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$', image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels


class P2Fixture(Fixture):
    def __init__(self, lib, rom, labels):
        self.bus = self.idles = 0
        self.io = []; self.near = {}; self.handlers = {}
        super().__init__(lib, rom, labels)
        self.stubs = {}
        self.idle_cb = C.CFUNCTYPE(None, C.c_void_p, C.c_bool)(self.idle)
        self.cpu.idle = C.cast(self.idle_cb, C.c_void_p).value
        self.cpu.db = 0x3A
        self.word(0x7FF400, 0x2B7C)
        self.put(0x10, 9); self.word(0x8A, 1); self.word(0x7FF412, 0x8001)
        self.word(0x7FF406, 100); self.word(0x7FF408, 100)
        self.word(0x22, 120); self.word(0x20, 100)
        self.put(0x7FF402, 1)  # P2 right
        self.stub_near('P2_ProbeSolid', lambda f:setattr(f.cpu,'c',False))
        self.stub_long(0x0683EA, lambda f:None)
        self.stub_long(0x0683E6, lambda f:setattr(f.cpu,'c',True))
        self.stub_long(0x068156, self.spawn)

    def idle(self, *_): self.idles += 1

    def read(self, address):
        self.bus += 1
        if address in self.near: return 0x60
        return super().read(address)

    def write(self, address, value):
        self.bus += 1
        if (address >> 16) in (0,0x80) and (0x2100 <= (address & 65535) <= 0x437F):
            self.io.append((address & 65535,value)); return
        super().write(address,value)

    def stub_near(self, name, fn):
        address=self.addr(name); self.near[address]=name; self.handlers[address]=fn

    def stub_long(self, address, fn):
        self.stubs[address]=hex(address); self.handlers[address]=fn

    @staticmethod
    def spawn(f):
        for slot in range(15,-1,-1):
            if f.get(0xDD0+slot)==0:
                f.cpu.x=slot; f.put(0xE20+slot,0xEC); f.put(0xDB0+slot,f.cpu.a)
                return
        f.cpu.x=0xFF

    def run(self, name, *, long_return=False, x=6, y=7, x16=False, db=None):
        c=self.cpu; c.xf=not x16; c.mf=True; c.x=x; c.y=y
        if db is not None:c.db=db
        entry=self.addr(name); c.k=entry>>16; c.pc=entry&65535
        sp=c.sp; olddb=c.db
        if long_return:self.put(c.sp,c.k); c.sp-=1
        self.put(c.sp,0x6F); self.put(c.sp-1,0xFF); c.sp-=2
        start=self.bus+self.idles; minsp=c.sp
        for count in range(15000):
            address=c.k<<16|c.pc
            if address==((entry&0xFF0000)|0x7000):
                cycles=self.bus+self.idles-start
                assert c.sp==sp and not self.bad_writes,(name,c.sp,self.bad_writes)
                assert c.db==olddb and c.mf and c.xf==(not x16),(name,'ABI',c.db,c.mf,c.xf)
                return {'instructions':count,'cpu_bus_cycles':cycles,'stack_bytes_including_return':sp-minsp}
            if address in self.handlers:
                self.calls.append(self.near.get(address,self.stubs.get(address)))
                self.handlers[address](self)
            self.lib.cpu_runOpcode(self.p); minsp=min(minsp,c.sp)
        raise AssertionError((name,'instruction bound',hex(c.k<<16|c.pc)))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lakesnes',type=Path,required=True)
    ap.add_argument('--control-source',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    a=ap.parse_args(); cases=[]; control_failures=[]; control_details={}; timings={}
    candidate=(ROOT/'Sprites/Players/player2.asm').read_text()
    with tempfile.TemporaryDirectory(prefix='p2-suspension-cpu-') as tmp:
        d=Path(tmp); library=d/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),
                        str(a.lakesnes/'snes/statehandler.c'),'-o',str(library)],check=True)
        lib=C.CDLL(str(library)); lib.cpu_init.restype=C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        for variant,source in [('control',a.control_source.read_text()),('candidate',candidate)]:
            rom,labels=assemble(d/variant,source)
            def fresh():return P2Fixture(lib,rom,labels)
            def check(name,fn,regression=False):
                f=fresh()
                try:
                    fn(f)
                    if variant=='candidate':cases.append(name)
                except AssertionError as error:
                    if variant=='control' and regression:
                        control_failures.append(name);control_details[name]=str(error) or 'Expected behavioral assertion failed'
                    else:raise
                finally:f.close()
            def busy(f,kind):
                if kind=='bird':f.put(0xC4A+4,0x27)
                elif kind in ('hook','receipt'):f.put(0xC4A+4,0x1F if kind=='hook' else 0x22)
                else:f.put(0xDD0+12,9);f.put(0xE20+12,0xEA if kind=='heart' else 0xE7)
            for owner in ('bird','hook','receipt','heart','mushroom'):
                def gate(f,owner=owner):
                    busy(f,owner);f.run('P2_CanAct');assert not f.cpu.c
                    assert f.cpu.x==6 and f.cpu.y==7
                check('action-refusal-'+owner,gate,True)
                def update(f,owner=owner):
                    busy(f,owner);f.put(0x7FF435,7);f.put(0x7FF44F,1);f.put(0x7FF40F,5)
                    f.put(0x7FF458,3);f.put(0x7FF461,2);f.put(0xDD2,9);f.put(0xE22,0xEC)
                    f.put(0xDD3,9);f.put(0xE23,0xD8)
                    f.run('P2_Update')
                    assert f.get(0x7FF406)==100 and f.get(0x7FF408)==100
                    assert f.get(0x7FF435)==0 and f.get(0x7FF40F)==2
                    assert f.get(0xDD2)==0 and f.get(0x7FF458)==0 and f.get(0x7FF461)==2
                    assert f.get(0xDD3)==9 and '0x6d125' not in f.calls
                # Old Update can reach pickup: an explicit absorption stub records that call.
                def bounded_update(f,owner=owner):
                    f.stub_long(0x06D125,lambda x:None);update(f,owner)
                check('freeze-stash-no-pickup-'+owner,bounded_update,True)
                def attack(f,owner=owner):
                    busy(f,owner);f.put(0x7FF435,7);f.run('P2_PunchHitsSprite')
                    assert not f.cpu.c and f.cpu.x==6
                    assert f.get(0x7FF436)==0 and f.get(0x7FF437)==0
                check('attack-refusal-'+owner,attack,True)
                def contact(f,owner=owner):
                    busy(f,owner);f.run('P2_ContactGate',long_return=True,db=6)
                    assert f.get(0x7FF44C)==0 and f.get(0x373)==0
                    assert f.cpu.x==6
                check('contact-refusal-'+owner,contact,True)
                def nmi(f,owner=owner):
                    busy(f,owner);f.put(0x7FF40F,5);f.word(0xADC,0xABCD)
                    t=f.run('P2_NmiUpload',long_return=True,x=0xBEAD,y=0xCAFE,x16=True,db=0)
                    assert f.io==[(0x4302,0xCD),(0x4303,0xAB)],f.io
                    assert f.get(0x7FF40F)==0 and f.cpu.y==0xCAFE and f.cpu.x==0xABCD
                    if variant=='candidate':timings['nmi-refusal-'+owner]=t
                check('late-owner-no-dma-'+owner,nmi,True)
            for module,cutscene in ((8,0),(9,1),(7,1)):
                def suspend(f,module=module,cutscene=cutscene):
                    f.put(0x10,module);f.put(0x7EF303,cutscene);f.put(0x7FF40F,5)
                    f.run('P2_Update');assert f.get(0x7FF40F)==2
                    f.put(0x7FF40F,5);f.run('P2_NmiUpload',long_return=True,x16=True,db=0)
                    assert not any(x==0x420B for x,_ in f.io)
                check(f'cutscene-flight-{module}-{cutscene}',suspend,True)
            def menu(f):
                f.put(0x10,0x0E);f.put(0x7FF435,7)
                f.run('P2_Update');assert f.get(0x7FF435)==7 and f.get(0x7FF40F)==0
            check('menu-freezes-without-regroup',menu)
            def resume(f):
                f.put(0x7FF40F,2);f.put(0x7FF461,2);f.put(0xB9C,0x4A)
                f.put(0x314,0x32);f.put(0xFB2,0x76)
                f.run('P2_Spawn')
                assert f.get(0x7FF40F)==0 and f.get(0x7FF406)==104 and f.get(0x7FF408)==100
                assert f.get(0x7FF458)==16 and f.get(0x7FF461)==2 and f.get(0xDDF)==9
                assert (f.get(0xB9C),f.get(0x314),f.get(0xFB2))==(0x4A,0x32,0x76)
            check('release-safe-placement-restore-one-held',resume)
            def full(f):
                for slot in range(16):f.put(0xDD0+slot,9);f.put(0xE20+slot,1)
                f.put(0x7FF461,2);f.run('P2_Unstash')
                assert f.get(0x7FF461)==2 and f.get(0x7FF40F)&2 and f.get(0x7FF458)==0
                f.put(0xDD7,0);f.run('P2_Spawn')
                assert f.get(0x7FF458)==8 and f.get(0x7FF461)==2 and not(f.get(0x7FF40F)&2)
                assert all(f.get(0xDD0+s)==9 for s in range(16))
            check('full-table-retains-and-restores-later',full,True)
            def free_nmi(f):
                f.put(0x7FF40F,1);f.word(0xADC,0x1234)
                t=f.run('P2_NmiUpload',long_return=True,x16=True,x=0xBEAD,y=0xCAFE,db=0)
                assert sum(reg==0x420B for reg,_ in f.io)==4
                assert f.cpu.y==0xCAFE and f.cpu.x==0x1234 and f.get(0x7FF40F)==0
                timings[variant+'-nmi-free']=t
            check('free-owner-ordinary-dma-abi',free_nmi)
            def follower(f):
                f.put(0x7FF40F,5);f.put(0x7EF3CC,9)
                f.run('P2_NmiUpload',long_return=True,x16=True,db=0)
                assert sum(reg==0x420B for reg,_ in f.io)==4 and f.get(0x7FF40F)==0
            check('late-follower-no-blade-dma',follower,True)
            for wide in (False,True):
                def slots(f,wide=wide):
                    t=f.run('P2_SlotsBusy',x=0xBEAD if wide else 6,y=0xCAFE if wide else 7,x16=wide)
                    assert not f.cpu.c and f.cpu.x==(0xBEAD if wide else 6) and f.cpu.y==(0xCAFE if wide else 7)
                    if variant=='candidate':timings['slot-scan-'+str(wide)]=t
                check('slot-scan-ABI-'+str(wide),slots,True)
            def ordinary(f):
                f.run('P2_CanAct');assert f.cpu.c
                f.put(0x7FF435,7);f.run('P2_PunchHitsSprite')
                assert f.cpu.c and f.get(0x7FF436)==0x40 and f.cpu.x==6
                f.put(0x7FF435,0);f.cpu.c=False
                f.run('P2_ContactGate',long_return=True,db=6)
                assert f.get(0x7FF44C)==0x3A and f.get(0x7FF44D)==8 and f.cpu.x==6
            check('ordinary-attack-contact-still-work',ordinary)
            def movement(f):
                f.stub_near('P2_PvP',lambda x:None)
                f.stub_near('P2_CheckOnScreen',lambda x:None)
                f.run('P2_Update')
                assert f.get(0x7FF406)>100 and f.get(0x7FF408)==100
            check('ordinary-movement-still-works',movement)
            def p1_contact(f):
                f.put(0xAF4,1);f.cpu.c=True
                f.run('P2_ContactGate',long_return=True,db=6)
                assert f.cpu.c and f.get(0x7FF44C)==0 and f.cpu.x==6
            check('p1-contact-carry-preserved',p1_contact)
            def worst_scan(f):
                for slot in range(16):f.put(0xDD0+slot,9);f.put(0xE20+slot,1)
                t=f.run('P2_SlotsBusy',x16=True,x=0xBEAD,y=0xCAFE)
                assert not f.cpu.c
                if variant=='candidate':timings['slot-scan-all-active']=t
            check('slot-scan-nonowners-active',worst_scan,True)
            def stale_bird(f):
                f.put(0xAF4,0x20)
                f.run('P2_SlotsBusy',x16=True,x=0xBEAD,y=0xCAFE)
                assert not f.cpu.c
            check('stale-bird-flag-not-busy',stale_bird,True)
            def cutscene_duck(f):
                f.put(0xC4A+4,0x38)
                f.run('P2_SlotsBusy',x16=True,x=0xBEAD,y=0xCAFE)
                assert f.cpu.c
            check('cutscene-duck-busy',cutscene_duck,True)
            def action_hook_refusal(f):
                f.put(0xC4A+4,0x27);f.put(0x7FF435,7);f.put(0x44,0x80)
                f.run('P2_ActionGate',long_return=True,db=6)
                assert f.cpu.z and f.cpu.c and f.cpu.a&255==0x80 and f.cpu.x==6
                assert f.get(0x7FF436)==0
            if variant=='candidate':check('action-hook-replays-vanilla-compare',action_hook_refusal)
            def no_join(f):
                f.word(0x7FF400,0);f.put(0x7FF40F,5);f.word(0xADC,0xBA98)
                f.run('P2_NmiUpload',long_return=True,x16=True,y=0xCAFE,db=0)
                assert f.io==[(0x4302,0x98),(0x4303,0xBA)] and f.cpu.y==0xCAFE
            check('not-joined-nmi-replay-only',no_join)
            def no_overlap(f):
                f.stub_long(0x0683E6,lambda x:setattr(x.cpu,'c',False))
                f.put(0x7FF435,7);t=f.run('P2_PunchHitsSprite')
                assert not f.cpu.c and f.get(0x7FF436)==0
                if variant=='candidate':timings['attack-no-overlap']=t
            check('nonoverlap-no-hit',no_overlap)
            def stale_draw(f):
                f.put(0x7FF40F,7);f.run('P2_Draw');assert f.get(0x7FF40F)==2
            check('skipped-draw-clears-stale-request',stale_draw,True)
    result={'passed':True,'case_count':len(cases),'cases':cases,'control_failed_cases':control_failures,
            'source_sha256':hashlib.sha256(candidate.encode()).hexdigest(),'timings':timings,'control_failure_details':control_details,
            'scope':'Assembled CPU behavior; collision/spawn/overlap are explicit engine stubs. No native SNES/PPU/DMA timing/save proof.'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
