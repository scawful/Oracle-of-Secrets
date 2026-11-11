#!/usr/bin/env python3
"""Execute the compiled D3 receipt hook and native message/completion path.

Reuse the existing D4 Lakesnes CPU fixture. Only item drawing is replaced by
RTS in memory for the draw-only message case; the receipt dispatcher, hook,
capture routine and common cleanup execute their actual compiled ROM bytes.
This is CPU/ABI evidence, not a native chest, message or warp qualification.
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


class ReceiptFixture(Fixture):
    def read(self,address):
        if address==0x08C5F7:  # ItemReceipt_Animate: drawing is outside this check.
            return 0x60
        return super().read(address)


def check(lib,rom,labels):
    labels=dict(labels,Ancilla22_ItemReceipt=0x08C38A)
    slot=4
    def fresh(**values):
        f=ReceiptFixture(lib,rom,labels)
        for a,v in ((0x10,7),(0x11,0),(0x1B,1),(0x40C,0x10),
                    (0x7EF359,2),(0x7EF306,0xA4),(0x7EF3C8,0),
                    (0x02E9,0x5A),(0x0C5E+slot,1),(0x0C54+slot,1),
                    (0x0C4A+slot,0x22),(0x03B1+slot,0xFF)):
            f.put(a,v)
        f.word(0x10E,0xCAFE)
        f.cpu.db=0x08;f.cpu.y=0x42;f.cpu.a=0xAB00;f.cpu.c=True
        for a,v in values.items():f.put(int(a,16),v)
        return f
    cases=(('outdoors',{'1B':0}),('other_dungeon',{'40C':0x0A}),
           ('other_receipt',{'C62':0x24}),('wrong_sword',{'7EF359':1}),
           ('already_captured',{'7EF306':0xA5}),('other_module',{'10':9}),
           ('message_open',{'10':0x0E,'11':2}))
    for name,fields in cases:
        f=fresh(**fields);before=bytes(f.ram)
        f.call('Oracle_PrisonSequence_PostMeadowBlade',x=slot,a=0xFF,long_return=True)
        receipt=f.get(0x0C5E+slot)
        assert f.cpu.a==0xAB00|receipt,(name,'displaced LDA')
        assert f.cpu.c and f.cpu.db==8 and f.cpu.y==0x42 and f.cpu.dp==0,(name,'ABI')
        assert f.get(0x02E9)==0,(name,'displaced STZ')
        allowed=set(range(0x100,0x200))|{0x2E9}
        assert all(a in allowed or v==n for a,(v,n) in enumerate(zip(before,f.ram))),(name,'unexpected state change')
        f.close()
    # The actual receipt dispatcher holds the ancilla while the text runs.
    f=fresh(**{'10':0x0E,'11':2})
    f.call('Ancilla22_ItemReceipt',x=slot,a=0xFF)
    assert f.get(0x10)==0x0E and f.get(0x11)==2
    assert f.get(0x0C4A+slot)==0x22 and f.get(0x03B1+slot)==0xFF
    assert f.get(0x7EF306)==0xA4 and f.get(0x02E9)==0x5A
    assert f.get(0x0C68+slot)==0x10,'Message draw-only path not taken'
    # Closing the message returns normal07/00. Expiry now reaches the common
    # exit, captures once, and still executes the original receipt cleanup.
    f.put(0x10,7);f.put(0x11,0)
    f.call('Ancilla22_ItemReceipt',x=slot,a=0xFF)
    assert f.get(0x10)==5 and f.get(0x10E)==0x32 and f.get(0x10F)==0
    assert f.get(0x7EF306)==0xA5 and f.get(0x7EF3C8)==2
    assert f.get(0x7EF359)==2,'Sword award changed'
    assert f.get(0x0C4A+slot)==0 and f.get(0x02E9)==0 and f.get(0xFC1)==0
    f.close()
    return {'negative_hook_cases':len(cases),'actual_message_draw_only':1,
            'actual_postmessage_capture_cleanup':1}



def loader_fixture(lib,rom,labels,selector=2,captured=1,state=2,world=0,follower=0):
    f=ReceiptFixture(lib,rom,labels)
    for a,v in ((0x7EF3C8,selector),(0x7EF306,captured),(0x7EF3C5,state),
                (0x7EF3CA,world),(0x7EF3CC,follower),(0x7EF359,2),(0x1B,1)):
        f.put(a,v)
    f.word(0x10E,0x9876);f.word(0x04AA,0xBEEF)
    f.cpu.db=2;f.cpu.a=0xAB00;f.cpu.x=5;f.cpu.y=0x42;f.cpu.c=True;f.cpu.v=True
    for address,name in ((0x0DE395,'SearchForEquippedItem_long'),
                         (0x0DFA6C,'RebuildHUD_long2'),(0x0DDD32,'UpdateEquippedItem_long')):
        f.stubs[address]=name
    return f


def run_to(f,stops,start=None,push_return=False):
    """Bounded actual bytes; stop at an existing native continuation."""
    if start is not None:f.cpu.k=start>>16;f.cpu.pc=start&0xFFFF
    if push_return:
        sp=f.cpu.sp;f.put(sp,0x34);f.put(sp-1,0x6F);f.put(sp-2,0xFF);f.cpu.sp-=3
    for _ in range(100000):
        address=f.cpu.k<<16|f.cpu.pc
        if address in stops:
            assert not f.bad_writes,('Unexpected non-WRAM writes',f.bad_writes)
            return address
        if address in f.stubs:f.stub(f.stubs[address])
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError(('Loader instruction cap',hex(f.cpu.k<<16|f.cpu.pc)))


def check_spawn_loader(lib,rom,labels,control_rom,control_labels):
    stops={0x028196,0x028208,0x347000}
    # Same saved-selector contract and entire non-stack RAM/CPU result as the
    # admitted control: every legacy selector, uncaptured prison and valid or
    # malformed Goron factory checkpoint. Escaped files use Sanctuary selector1.
    cases=[(n,1,2,0,0) for n in (0,1,3,4,5,6)]
    cases += [(2,0,2,0,0),(2,2,2,0,0),(1,3,2,0,0),
              (7,0,2,0,0),(7,0,1,0,0),(7,0,2,0x40,0),(7,0,2,0,1)]
    for values in cases:
        fs=[];ends=[]
        for image,syms in ((control_rom,control_labels),(rom,labels)):
            f=loader_fixture(lib,image,syms,*values)
            end=run_to(f,stops,f.addr('LoadCheckpointOrWorld'),True)
            ends.append(end);fs.append(f)
        old,new=fs
        assert ends[0]==ends[1],(values,'Legacy continuation',ends)
        attrs=('a','x','y','sp','dp','db','c','z','v','n','i','d','xf','mf')
        assert all(getattr(old.cpu,a)==getattr(new.cpu,a) for a in attrs),(values,'Legacy CPU ABI')
        assert all(0x100<=a<0x200 or x==y for a,(x,y) in enumerate(zip(old.ram,new.ram))),(values,'Legacy RAM changed')
        assert new.cpu.sp==(0x1FF if ends[1]==0x347000 else 0x1FC),(values,'JML/RTL stack')
        for f in fs:f.close()
    # A captured prison file selects the ordinary entrance32 path, not the
    # separate SpawnPointData record. The existing Module05 return is intact.
    f=loader_fixture(lib,rom,labels);save_before=bytes(f.ram[0xF000:0xF500])
    assert run_to(f,stops,f.addr('LoadCheckpointOrWorld'),True)==0x028208
    word=lambda f,a:f.get(a)|(f.get(a+1)<<8)
    assert word(f,0x10E)==0x32 and f.get(0x10A)==1 and word(f,0x04AA)==0
    assert f.cpu.sp==0x1FC and f.cpu.db==2 and f.cpu.dp==0 and f.cpu.mf and f.cpu.xf
    assert bytes(f.ram[0xF000:0xF500])==save_before,'Prison routing changed saved data'
    # Continue through the actual HUD/Module06/expanded entrance loader until
    # its existing room-dependent load boundary. Only the three HUD calls stub.
    run_to(f,{0x02DAD2})
    g=loader_fixture(lib,control_rom,control_labels)
    g.word(0x10E,0x32);g.put(0x10A,1);g.word(0x04AA,0)
    run_to(g,{0x02DAD2},0x028208,True)
    for start,end in ((0x20,0x24),(0xA0,0xAA),(0xE0,0xEA),(0x11E,0x126),
                      (0x40C,0x40E),(0x476,0x477),(0x48E,0x490),(0x600,0x620)):
        assert bytes(f.ram[start:end])==bytes(g.ram[start:end]),('Complete native entrance contract',hex(start))
    assert word(f,0xA0)==0x55 and f.get(0x40C)==0x10
    assert word(f,0x22)==int.from_bytes(rom[0x79064:0x79066],'little')
    assert word(f,0x20)==int.from_bytes(rom[0x78E64:0x78E66],'little')
    assert bytes(f.ram[0xF000:0xF500])==save_before
    for q in (f,g):q.close()
    return {'legacy_and_goron_equivalence_cases':len(cases),
            'captured_prison_native_entry':1,'complete_native_entrance32_contract':1}


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('rom','symbols','lakesnes','output'):ap.add_argument('--'+n,type=Path,required=True)
    ap.add_argument('--control-rom',type=Path)
    ap.add_argument('--control-symbols',type=Path)
    a=ap.parse_args();assert not a.output.exists()
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$',a.symbols.read_text())}
    root=Path(__file__).resolve().parents[1]
    labels.update({n:int(v,16) for n,v in re.findall(r'(?m)^(\w+)\s*=\s*\$([0-9A-Fa-f]+)',(root/'Core/symbols.asm').read_text())})
    rom=a.rom.read_bytes()
    assert rom[0x4442C:0x44431]==bytes.fromhex('845d9cd802'),'Old receipt path still patched'
    target=labels['Oracle_Oracle_PrisonSequence_PostMeadowBlade']
    assert rom[0x4443B:0x44441]==b'\x22'+target.to_bytes(3,'little')+b'\xEA\xEA'
    with tempfile.TemporaryDirectory(prefix='d3-receipt-cpu-') as temp:
        libpath=Path(temp)/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath));lib.cpu_init.restype=C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        results=check(lib,rom,labels)
        if a.control_rom or a.control_symbols:
            assert a.control_rom and a.control_symbols
            syms={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4}) (\S+)$',a.control_symbols.read_text())}
            results.update(check_spawn_loader(lib,rom,labels,a.control_rom.read_bytes(),syms))
    report={'status':'COMPILED_CPU_FIXTURE_PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),
            'results':results,'scope':'Actual receipt dispatcher and capture/cleanup bytes; drawing replaced by RTS. Not native gameplay.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
