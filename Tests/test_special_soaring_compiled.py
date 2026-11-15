#!/usr/bin/env python3
"""Check compiled Soaring list/state/cache bytes with the existing Lakesnes fixture.

No SNES system, PPU, emulator session, controller play or saved-file proof.
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


def execute(f, name, long_return=False):
    entry=f.addr(name); assert entry is not None,name
    p=f.cpu;p.k=entry>>16;p.pc=entry&65535;p.db=0x2D
    initial_sp=p.sp
    frame=([entry>>16,0x6F,0xFF] if long_return else [0x6F,0xFF])
    for v in frame:f.put(p.sp,v);p.sp-=1
    for _ in range(30000):
        if (p.k<<16|p.pc)==((entry&0xFF0000)|0x7000):
            assert p.sp==initial_sp,(name,'stack',p.sp)
            assert p.db==0x2D,(name,'DBR',p.db)
            assert not f.bad_writes,(name,f.bad_writes)
            return
        f.lib.cpu_runOpcode(f.p)
    raise AssertionError((name,'instruction limit',p.k,p.pc))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('rom','symbols','lakesnes','output'):ap.add_argument('--'+n,type=Path,required=True)
    a=ap.parse_args();rom=a.rom.read_bytes();sym=a.symbols.read_text()
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([\dA-Fa-f]{2}):([\dA-Fa-f]{4}) (\S+)$',sym)}
    cases=[]
    with tempfile.TemporaryDirectory(prefix='soaring-cpu-') as tmp:
        libpath=Path(tmp)/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath));lib.cpu_init.restype=C.POINTER(Cpu)
        lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        def fresh():
            f=Fixture(lib,rom,labels);f.word(0x010C,0x0B);f.put(0x10,0x0B);f.word(0x8A,0x83);return f
        for value in (0,1,0xA4,0xA5,0xFF):
            f=fresh();f.put(0x7EF3B2,value);f.put(0x1AF0,0x81)
            execute(f,'Menu_DrawSoaring')
            word=lambda at:f.get(at)|(f.get(at+1)<<8)
            sky=0x1000+15*64+10*2
            assert (word(sky)&0x3FF==0x162)==(value==0xA5),('Sky visibility',value,hex(word(sky)))
            assert [word(0x1000+11*64+10*2+2*i)&0x3FF for i in range(8)]==[0x150+ord(c)-ord('A') for c in 'GARRISON']
            assert f.get(0x1AF0)==(0x81 if value==0xA5 else 0x80)
            assert f.get(0x7EF3B2)==value,'drawing changed saved state'
            cases.append('list-token-'+hex(value));f.close()
        for source,opens in ((0x7F,False),(0x80,True),(0x83,True),(0x8C,True),(0xBF,True),(0xC0,False)):
            f=fresh();f.word(0x8A,source);execute(f,'SpecialSoaring_Open',True)
            assert f.get(0x10)==(0x0E if opens else 0x0B)
            if opens:assert f.get(0x11)==1 and f.get(0x1AF0)==0x80
            cases.append('source-'+hex(source));f.close()
        for pending,learned,map_id in ((0,0,None),(0x80,0,None),(0xC0,0,0x83),(0xC1,0,None),(0xC1,0xA4,None),(0xC1,0xA5,0x8C)):
            f=fresh();f.put(0x1AF0,pending);f.put(0x7EF3B2,learned);execute(f,'SpecialSoaring_Complete',True)
            assert f.get(0x7EF3B2)==learned,'transport changed saved state'
            if map_id is None:assert f.get(0x10)==0x0B
            else:
                assert f.get(0x10)==8 and f.get(0x11)==0 and f.get(0x1AF0)==0
                assert f.get(0x7EC140)==map_id and f.get(0x7EC14C)==map_id
                assert f.get(0xA0)==0x51 and f.get(0xA1)==1
            cases.append(f'transport-{pending:02x}-{learned:02x}');f.close()
        for learned,next_row in ((0,0x80),(0xA5,0x81)):
            f=fresh();f.put(0x1AF0,0x80);f.put(0x7EF3B2,learned);f.put(0xF4,8);execute(f,'Menu_SpecialSoaring')
            assert f.get(0x1AF0)==next_row and f.get(0x17)==1
            cases.append('navigation-'+hex(learned));f.close()
        for module,requested in ((0x09,False),(0x0B,True)):
            f=fresh();f.word(0x010C,module);f.put(0x1AF0,0x80);execute(f,'Menu_SoaringRequested')
            assert f.cpu.c==requested
            cases.append('menu-admission-'+hex(module));f.close()
        for pad,expected in ((0x80,0),(0x10,0)):
            f=fresh();f.put(0x1AF0,0x80);f.put(0xF4,pad);execute(f,'Menu_SpecialSoaring')
            assert f.get(0x1AF0)==expected and f.get(0x200)==8
            cases.append('cancel-'+hex(pad));f.close()
        f=fresh();f.put(0x1AF0,0x81);f.put(0x7EF3B2,0xA5);f.put(0xF6,0x80);execute(f,'Menu_SpecialSoaring')
        assert f.get(0x1AF0)==0xC1 and f.get(0x200)==8
        cases.append('select-sky');f.close()
    result={'passed':True,'case_count':len(cases),'cases':cases,'rom_sha256':hashlib.sha256(rom).hexdigest(),'scope':'Compiled CPU/menu-buffer/state/cache fixture only; native UI/travel/save proof remains open.'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))

if __name__=='__main__':main()
