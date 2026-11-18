#!/usr/bin/env python3
"""Execute unhooked adapter with granted symbols; no game ROM or save writes."""
import argparse
import ctypes as C
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile

import test_item_bindings_compiled as core

ROOT = Path(__file__).resolve().parents[1]


def granted_addresses():
    text = (ROOT/'Core/sram.asm').read_text()+'\n'+(ROOT/'Core/symbols.asm').read_text()
    result = {}
    for name in core.FIELDS:
        found = re.findall(r'^ItemBinding'+name+r'\s*=\s*\$([0-9A-Fa-f]+)\b', text, re.M)
        assert len(found) == 1, name
        result[name] = int(found[0], 16)
    assert list(result.values()) == [0x7EF3B9, 0x7EF3BA, 0x7EF3BB,
                                     0x7E02B3, 0x7E02B4, 0x7E02B5, 0x7E02B6]
    return result


def assemble(folder, adapter):
    folder.mkdir()
    (folder/'item_bindings.asm').write_bytes((ROOT/'Items/item_bindings.asm').read_bytes())
    (folder/'adapter.asm').write_text(adapter)
    definitions = '\n'.join(f'ItemBinding{k} = ${v:06X}' for k,v in core.ADDR.items())
    assert not re.search(r'^!ENABLE_DUAL_ITEM_BINDING_PROTOTYPE\b',
                         (ROOT/'Util/macros.asm').read_text(),re.M)
    assert not re.search(r'^!ENABLE_DUAL_ITEM_BINDING_PROTOTYPE\b',
                         (ROOT/'Config/feature_flags.asm').read_text(),re.M)
    asm = folder/'fixture.asm'
    asm.write_text('lorom\n'+core.EXTRA_DEFS+definitions+'\norg $208000\nnamespace Oracle\n'
                   'FixtureStart:\nincsrc "adapter.asm"\nnamespace off\n')
    image = folder/'fixture.sfc'; image.write_bytes(b'\xff'*0x110000)
    process = subprocess.run(['asar','--no-title-check','--fix-checksum=off','--symbols=wla',
                              str(asm),str(image)],capture_output=True,text=True)
    assert process.returncode == 0, process.stdout+process.stderr
    labels = {m[3]:int(m[1]+m[2],16) for m in re.finditer(
        r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$',image.with_suffix('.sym').read_text())}
    return image.read_bytes(), labels


class AdapterFixture(core.BindingFixture):
    def __init__(self,*args):
        self.writes=[]
        super().__init__(*args)
    def write(self,address,value):
        self.writes.append((address,value))
        super().write(address,value)


def exercise(lib,rom,labels):
    cases=[]
    for m8,x8 in ((True,True),(False,True),(True,False),(False,False)):
        for carry in (False,True):
            for mode in ('reset','refuse-other-Y','refuse-unowned-Y','load-old','load-current'):
                f=AdapterFixture(lib,rom,labels)
                try:
                    # Both neighbors and all nearby owner bytes must survive.
                    f.ram[0x1E70:0x1EE3]=b'\xA5'*0x73
                    f.ram[0xF3A8:0xF3BD]=b'\xA5'*0x15
                    f.field('SavedVersion',1 if mode=='load-current' else 0xFF)
                    f.field('SavedY',2);f.field('SavedX',1)
                    for field in ('Cursor','Logical','Action','Button'):f.field(field,0xEF)
                    f.put(0x202,0x1D if mode=='refuse-other-Y' else 1)
                    if mode=='refuse-unowned-Y':f.put(0x7EF340,0)
                    f.cpu.n=True;f.cpu.z=False;f.cpu.i=True;f.cpu.d=True
                    saved=bytes(f.ram[0xF3B9:0xF3BC]);f.writes.clear()
                    result=f.run('AdapterReset' if mode=='reset' else 'AdapterLoad',
                                 a=0x37,m8=m8,x8=x8,carry=carry)
                    assert result==0x37 and (f.cpu.n,f.cpu.z,f.cpu.i,f.cpu.d)==(True,False,True,True)
                    writes=[(a,v) for a,v in f.writes if a in core.ADDR.values()]
                    if mode=='reset' or mode.startswith('refuse'):
                        assert bytes(f.ram[0xF3B9:0xF3BC])==saved
                        assert not any(f.field(k) for k in ('Cursor','Logical','Action','Button'))
                        assert not any(a in list(core.ADDR.values())[:3] for a,_ in writes)
                        assert f.cpu.c==(carry if mode=='reset' else False)
                    else:
                        assert f.cpu.c
                        expected=[1,2,1,2,0,0,0] if mode=='load-current' else [1,1,0,1,0,0,0]
                        assert [f.field(k) for k in core.FIELDS]==expected
                        assert writes[-1]==(core.ADDR['SavedVersion'],1),writes
                    cases.append(f'{mode}-m{8 if m8 else 16}-x{8 if x8 else 16}-carry{int(carry)}')
                finally:f.close()
    return cases


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--lakesnes',type=Path,required=True)
    ap.add_argument('--output',type=Path,required=True)
    args=ap.parse_args();core.ADDR=granted_addresses()
    adapter=(ROOT/'Items/item_bindings_adapter.asm').read_text()
    with tempfile.TemporaryDirectory(prefix='item-binding-adapter-') as tmp:
        folder=Path(tmp);library=folder/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(args.lakesnes/'snes/cpu.c'),
                        str(args.lakesnes/'snes/statehandler.c'),'-o',str(library)],check=True)
        lib=C.CDLL(str(library));lib.cpu_init.restype=C.POINTER(core.Cpu)
        lib.cpu_runOpcode.argtypes=[C.POINTER(core.Cpu)];lib.cpu_free.argtypes=[C.POINTER(core.Cpu)]
        rom,labels=assemble(folder/'candidate',adapter)
        cases=exercise(lib,rom,labels)
        core_cases=core.exercise(lib,rom,labels)
        mutations={
            'unsupported-Y-admitted':adapter.replace('JSR ItemBindings_Validate : BCC .refuse','JSR ItemBindings_Validate : NOP : NOP'),
            'reset-clobbers-mask':adapter.replace('STA.l ItemBindingCursor : STA.l ItemBindingLogical','STA.l $7E02B2 : STA.l ItemBindingLogical'),
            'load-clobbers-A':adapter.replace('REP #$20 : PLA : PLP : SEC : RTL','REP #$20 : PLA : PLP : LDA.b #$00 : SEC : RTL'),
        }
        rejected=[]
        for name,bad in mutations.items():
            assert bad!=adapter
            badrom,badlabels=assemble(folder/name,bad)
            try:exercise(lib,badrom,badlabels)
            except AssertionError:rejected.append(name)
            else:raise AssertionError(('mutation escaped',name))
        report={'status':'PASS','adapter_cases':cases,'adapter_passed':len(cases),
                'core_cases_at_granted_addresses':len(core_cases),'flag_removed_default_on':True,
                'mutation_controls_rejected':rejected,'granted_addresses':core.ADDR,
                'source_sha256':hashlib.sha256(adapter.encode()).hexdigest(),
                'limits':'Compiled isolated fixture only. No production include/hook, live map takeover, game ROM, native Save/reopen or actual player migration.'}
        args.output.write_text(json.dumps(report,indent=2)+'\n')
        print(json.dumps({k:report[k] for k in ('status','adapter_passed','core_cases_at_granted_addresses','mutation_controls_rejected')}))

if __name__=='__main__':main()
