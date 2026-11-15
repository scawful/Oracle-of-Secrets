#!/usr/bin/env python3
"""Real Elegy creation entry; floor probe stub refuses after admission marker.
No native statue or graphics claim. Existing actor RAM must remain untouched.
"""
import argparse
import ctypes as C
import json
from pathlib import Path
import re
import subprocess
import tempfile
from d4_compiled_fight_check import Cpu
from test_farore_d8_graphics_compiled import ROOT, GraphicsFixture, assemble, setup


def compile_gate(folder, image, member, enabled):
    folder.mkdir()
    rom = folder/'gate.sfc'
    rom.write_bytes(image)
    symbols = (ROOT/'Core/symbols.asm').read_text()
    defs = '\n'.join(m[0] for m in re.finditer(r'(?m)^Spr\w+\s*=\s*\$[0-9a-fA-F]+', symbols))
    source = (ROOT/'Items/song_secrets_stone.asm').read_text()
    entry = source[source.index('OcarinaEffect_Stone:'):source.index('; Plain floor retains')]
    asm = folder/'gate.asm'
    asm.write_text('lorom\n'+defs+f'\nSongFlag = $FE\n!Stone_Marker = $E6\n!ENABLE_D8_FARORE_GRAPHICS = {enabled}\nD8Farore_IsMember = ${member:06X}\norg $2C8000\n'+entry+
                   '\nGateEnd:\nStone_SelectSpawnPoint:\n INC.w $1FFF : RTS\nStone_CheckSpawnFloor:\n CLC : RTS\n')
    r = subprocess.run(['asar','--no-title-check','--fix-checksum=off','--symbols=wla',str(asm),str(rom)],capture_output=True,text=True)
    assert r.returncode == 0, r.stdout+r.stderr
    labels = {m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$',rom.with_suffix('.sym').read_text())}
    return rom.read_bytes(), labels


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);args=ap.parse_args()
    checks=[]
    with tempfile.TemporaryDirectory(prefix='oos-farore-stone-') as tmp:
        p=Path(tmp);dll=p/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(args.lakesnes/'snes/cpu.c'),str(args.lakesnes/'snes/statehandler.c'),'-o',str(dll)],check=True)
        lib=C.CDLL(str(dll));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        image,helper,_=assemble(p/'graphics',1)
        for enabled in (0,1):
            rom,labels=compile_gate(p/f'gate{enabled}',image,helper['D8Farore_IsMember'],enabled)
            for room,indoor,crystal in ((0x90,1,0),(0x91,1,0),(0x96,1,0),(0xA7,1,0),(0x190,1,0),(0x90,1,0x80),(0x90,0,0)):
                f=GraphicsFixture(lib,rom,labels)
                try:
                    setup(f,room,indoor,crystal);f.put(0x10,7);f.put(0x11,0);f.put(0x5D,0);f.put(0xFE,0x21)
                    for i in range(0xC00,0x1000):f.put(i,(i*7+3)&255)
                    # A live previous echo must not be replaced or despawned by refusal.
                    f.put(0xDD6,9);f.put(0xE26,0x1C);f.put(0xD96,0xE6)
                    actors=bytes(f.ram[0xC00:0x1000]);scratch=bytes(f.ram[:12]);f.cpu.db=0x30;f.cpu.y=0x28
                    f.call('OcarinaEffect_Stone',long_return=True)
                    blocked=not indoor or (enabled and room==0x90 and not crystal&0x80)
                    assert f.get(0x1FFF)==int(not blocked),(enabled,hex(room),indoor,crystal)
                    assert f.get(0x12E)==0x3C and f.get(0xFE)==0
                    assert bytes(f.ram[0xC00:0x1000])==actors
                    assert bytes(f.ram[:12])==scratch and f.cpu.db==0x30 and f.cpu.y==0x28
                    checks.append(f'flag{enabled}-room{room:03X}-indoor{indoor}-crystal{crystal:02X}')
                finally:f.close()
    result={'status':'PASS','checks':checks,'scope':'actual creation entry and real membership; floor probe stub refuses after admission marker; no actor mutations/native proof'}
    args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','checks':len(checks)}))
if __name__=='__main__':main()
