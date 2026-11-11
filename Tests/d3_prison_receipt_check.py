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


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for n in ('rom','symbols','lakesnes','output'):ap.add_argument('--'+n,type=Path,required=True)
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
    report={'status':'COMPILED_CPU_FIXTURE_PASS','rom_sha256':hashlib.sha256(rom).hexdigest(),
            'results':results,'scope':'Actual receipt dispatcher and capture/cleanup bytes; drawing replaced by RTS. Not native gameplay.'}
    a.output.parent.mkdir(parents=True,exist_ok=True);a.output.write_text(json.dumps(report,indent=2)+'\n');print(json.dumps(report,indent=2))


if __name__=='__main__':main()
