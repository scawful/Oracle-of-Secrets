#!/usr/bin/env python3
"""Execute the real mask CGRAM copy with Lakesnes. No native/PPU proof.
Extract only the named routine verbatim; backdrop helper is an explicit RTL stub.
"""
import argparse,ctypes as C,hashlib,json,re,subprocess,sys,tempfile
from pathlib import Path
sys.dont_write_bytecode=True
support_parser=argparse.ArgumentParser(add_help=False)
support_parser.add_argument('--support-tests',type=Path,default=Path(__file__).resolve().parent)
support_args,_=support_parser.parse_known_args()
sys.path.insert(0,str(support_args.support_tests))
from d4_compiled_fight_check import Cpu,Fixture

def routine(text):
    start=text.index('Oracle_CgramAuxToMain_Impl:');end=text.index('\npushpc',start)
    return text[start:end]

def assemble(folder,text):
    folder.mkdir();asm=folder/'fixture.asm';image=folder/'fixture.sfc'
    asm.write_text('lorom\n!CurrentMask = $02B2\nRefreshOverworldBackdrop = $018000\norg $2C8000\n'+routine(text))
    image.write_bytes(b'\xff'*0x200000)
    proc=subprocess.run(['asar','--no-title-check','--fix-checksum=off','--symbols=wla',str(asm),str(image)],capture_output=True,text=True)
    assert proc.returncode==0,proc.stdout+proc.stderr
    labels={m[3]:int(m[1]+m[2],16) for m in re.finditer(r'(?m)^([\da-fA-F]{2}):([\da-fA-F]{4}) (\S+)$',image.with_suffix('.sym').read_text())}
    return image.read_bytes(),labels

def main():
    ap=argparse.ArgumentParser(parents=[support_parser]);ap.add_argument('--source',type=Path,required=True);ap.add_argument('--control',type=Path,required=True);ap.add_argument('--lakesnes',type=Path,required=True);ap.add_argument('--output',type=Path,required=True);a=ap.parse_args()
    cases=[];controls=[]
    with tempfile.TemporaryDirectory(prefix='oos-mask-env-cpu-') as temp:
        p=Path(temp);libpath=p/'cpu.dylib'
        subprocess.run(['cc','-shared','-fPIC','-O2',str(a.lakesnes/'snes/cpu.c'),str(a.lakesnes/'snes/statehandler.c'),'-o',str(libpath)],check=True)
        lib=C.CDLL(str(libpath));lib.cpu_init.restype=C.POINTER(Cpu);lib.cpu_runOpcode.argtypes=[C.POINTER(Cpu)];lib.cpu_free.argtypes=[C.POINTER(Cpu)]
        for variant,path in [('control',a.control),('candidate',a.source)]:
            rom,labels=assemble(p/variant,path.read_text())
            for mask,neighbor,indoor in [(0,0,0),(0,0,1),(0,0xA7,0),(1,0,0),(2,0,0),(3,0,0),(4,0,0),(5,0,0),(6,0,0),(6,0x91,1),(7,0,0),(8,0,0)]:
                f=Fixture(lib,rom,labels);f.stubs={0x018000:'RefreshOverworldBackdrop'}
                try:
                    source=bytes((i*37+19)&255 for i in range(512));previous=bytes((i*11+7)&255 for i in range(512))
                    for i,v in enumerate(source):f.put(0x7EC300+i,v)
                    for i,v in enumerate(previous):f.put(0x7EC500+i,v)
                    f.put(0x02B2,mask);f.put(0x02B3,neighbor);f.put(0x1B,indoor);f.put(0x15,9)
                    f.cpu.db=0x3A;f.cpu.y=0x27;f.writes=[]
                    f.call('Oracle_CgramAuxToMain_Impl',long_return=True,x=0x40)
                    actual=bytes(f.get(0x7EC500+i) for i in range(512))
                    expected=source[:480]+(previous[480:] if mask else source[480:])
                    name=f'mask{mask:02X}-neighbor{neighbor:02X}-indoor{indoor}'
                    good=actual==expected
                    assert f.cpu.db==0x3A and f.cpu.mf and f.cpu.xf and f.cpu.y==0x27,'ABI'
                    assert f.get(0x15)==10,'upload not requested'
                    assert f.calls==([] if indoor else ['RefreshOverworldBackdrop']),'backdrop routing'
                    assert f.get(0x02B2)==mask and f.get(0x02B3)==neighbor,'form mutated'
                    assert all(0x7EC500<=addr<=0x7EC6FF or addr in (0x15,0x1FD,0x1FE,0x1FF,0x1FA,0x1FB,0x1FC) for addr,_ in f.writes),f.writes[-10:]
                    if variant=='candidate':assert good,name;cases.append(name)
                    elif not good:controls.append({'case':name,'row6_stale':actual[448:480]==previous[448:480],'row7_differs':actual[480:]!=expected[480:]})
                    else:assert mask==0 and neighbor==0,name
                finally:f.close()
        assert len(cases)==12 and len(controls)==10
    result={'status':'PASS','candidate_cases':cases,'control_failures':controls,'source_sha256':hashlib.sha256(a.source.read_bytes()).hexdigest(),'control_sha256':hashlib.sha256(a.control.read_bytes()).hexdigest(),'scope':'real compiled copy routine; synthetic buffers; backdrop helper stub; no native/PPU/full-ROM build'}
    a.output.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({'status':'PASS','candidate':len(cases),'control_failures':len(controls)}))
if __name__=='__main__':main()
