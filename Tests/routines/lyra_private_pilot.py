#!/usr/bin/env python3
"""Execute the compiled private scroll helper in an explicit offline CPU runner.

No emulator socket, MMIO stub, gameplay or runtime admission is used here.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys

sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Scripts/Build'))
import lyra_native_loaders as L


def require(condition,message):
    if not condition:raise AssertionError(message)


def physical(address):
    return 0x7E0000|(address&65535) if address>>16&127<64 and address&65535<8192 else address


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--symbols',type=Path,required=True)
    parser.add_argument('--cpu-runner',type=Path,required=True)
    parser.add_argument('--raw-output-dir',type=Path)
    args=parser.parse_args();image=args.rom.read_bytes();labels=L._labels(args.symbols.read_bytes())
    entry=labels['Lyra_PrivatePilotCanScroll'];plans=[]
    directions=(0,2,4,6);delta={0:1,2:-1,4:8,6:-8}
    for area in (0xA0,0xA1,0xA2,0xB0,0xBF,0xC0,0xE0,0x4B,0x98,0,0x9F):
        cell=(area&63)*2
        for direction in directions:
            target=area+delta[direction]
            expected=((area,direction) in ((0xA0,0),(0xA1,2)) if area>=0xA0
                      else 0<=target<0xA0)
            plans.append((f'area{area:02X}-direction{direction}',area,cell,direction,expected))
    for area,cell,direction in ((0xA0,0x42,0),(0xA0,0,0),(0xA1,0x40,2),(0xA1,0xFFFF,2)):
        plans.append((f'mismatched-cell{cell:04X}-area{area:02X}',area,cell,direction,False))
    for area,direction in itertools.product((0xA0,0xA1,0x4B),(1,3,8,0xFF)):
        plans.append((f'bad-direction{direction}-area{area:02X}',area,(area&63)*2,direction,False))
    requests=[]
    for plan,(p,db,d) in itertools.product(plans,itertools.product((0x30,0x31,0xFE,0xFF),(2,0x7E),(0,0x120))):
        name,area,cell,direction,expected=plan;sp=0x1FFF
        regs=dict(a=0xABCD,x=0x67,y=direction,p=p,db=db,d=d,sp=sp)
        request=dict(entry=entry,reset_ram=True,registers=regs,
            writes=[dict(address=0x7E0000+d+0x8A,bytes=[area,0]),
                    dict(address=0x7E0700,bytes=list(cell.to_bytes(2,'little')))],
            reads=[dict(address=0x7E0000+d+0x8A,length=2),dict(address=0x7E0700,length=2)],
            trace_writes=True,max_steps=1000)
        requests.append((name,regs,area,cell,expected,request))
    payload=''.join(json.dumps(row[-1])+'\n' for row in requests)
    if args.raw_output_dir:args.raw_output_dir.mkdir(parents=True,exist_ok=False)
    result=subprocess.run([str(args.cpu_runner.resolve()),str(args.rom.resolve())],
        input=payload,text=True,capture_output=True,check=False,timeout=60)
    if args.raw_output_dir:
        (args.raw_output_dir/'requests.jsonl').write_text(payload)
        (args.raw_output_dir/'results.jsonl').write_text(result.stdout)
        (args.raw_output_dir/'runner.stderr').write_text(result.stderr)
    require(result.returncode==0,'Offline CPU runner failed: '+result.stderr)
    lines=result.stdout.splitlines();require(len(lines)==len(requests),'Missing offline CPU results')
    cases=[]
    for (name,regs,area,cell,expected,_),line in zip(requests,lines):
        row=json.loads(line);cpu=row['registers']
        require(row.get('returned'),name+': no RTL return')
        require(not row.get('stub_calls') and not row.get('mmio_writes'),name+': unexpected stub/MMIO')
        for key in ('a','x','y','d','db','sp'):require(cpu[key]==regs[key],name+': changed '+key)
        require(cpu['p']&~1==regs['p']&~1,name+': changed P beyond Carry')
        require(bool(cpu['p']&1)==(not expected),name+': wrong Carry admission')
        require(row['reads'][0]['bytes']==[area,0] and row['reads'][1]['bytes']==list(cell.to_bytes(2,'little')),
                name+': changed input state')
        allowed=set(range(0x7E0000+regs['sp']-32,0x7E0000+regs['sp']+1))|set(range(0x7F8000,0x7F8004))
        require(all(physical(write['address']) in allowed for write in row.get('writes',[])),name+': non-stack RAM write')
        cases.append(dict(name=name,p=regs['p'],db=regs['db'],d=regs['d'],allowed=expected,steps=row['steps'],passed=True))
    require(args.rom.read_bytes()==image,'Fixture ROM changed')
    print(json.dumps(dict(passed=True,cases=cases,case_count=len(cases),rom_sha256=hashlib.sha256(image).hexdigest(),
        runner_sha256=hashlib.sha256(args.cpu_runner.read_bytes()).hexdigest(),
        claim='emitted helper offline CPU/ABI fixture; no Link collision, native movement, save/reopen or admission'),indent=2))


if __name__=='__main__':main()
