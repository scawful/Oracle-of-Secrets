#!/usr/bin/env python3
"""Floor-aware following; no real room path or animation proof."""
import argparse,ctypes as C,json,re,subprocess,tempfile
from pathlib import Path
from d4_compiled_fight_check import Cpu
from test_farore_d8_presence_compiled import assemble,PresenceFixture,setup,ROOT

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args();checks=[]
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
        size=labels['D8Farore_FollowEnd']-labels['D8Farore_FollowStart']
    result={'status':'PASS','core_bytes':size,'wrapper_bytes':8,'caller_bytes':10,'checks':checks,'scope':'synthetic-location CPU test with actual presence footprint helper and stubbed terrain; no native/pathfinding/control proof'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result))
if __name__=='__main__':main()
