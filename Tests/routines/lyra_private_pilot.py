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


def preaccess(args, image, labels):
    """Execute real emitted helpers and bounded actual caller prefixes only."""
    cases=[];raw=[]
    def run(entry,writes,p=0x30,**kwargs):
        regs=dict(a=0xABCD,x=0x67,y=0x45,p=p,db=2,d=0,sp=0x1FFF)
        regs.update(kwargs.pop('registers',{}))
        req=dict(entry=entry,reset_ram=True,registers=regs,writes=writes,
            reads=[dict(address=0x7E0000,length=0x200),dict(address=0x7E1FD0,length=48),
                   dict(address=0x7EF3B4,length=0x17)],trace_writes=True,max_steps=kwargs.pop('max_steps',1000))
        process=subprocess.run([str(args.cpu_runner.resolve()),str(args.rom.resolve())],
            input=json.dumps(req)+'\n',text=True,capture_output=True,timeout=10)
        require(process.returncode==0,'CPU runner failed: '+process.stderr)
        row=json.loads(process.stdout);raw.append(dict(request=req,result=row))
        require(not row.get('stub_calls') and not row.get('mmio_writes'),'Unexpected stub/MMIO')
        return row,regs
    def stack_only(row,extra=()):
        allowed=set(range(0x7E1FC0,0x7E2000))|set(range(0x7F8000,0x7F8004))|set(extra)
        require(all(physical(w['address']) in allowed for w in row.get('writes',[])),'Unexpected RAM write')
    def field(at,value):return dict(address=at,bytes=list(value.to_bytes(2,'little')))
    for word,p in itertools.product((0,0x4B,0x98,0x9F,0xA0,0xA1,0xA2,0xB0,0xBF,0xC0,0xE0,0x100,0x1A0,0xFFFF),(0,1,0xC2,0xCB)):
        row,regs=run(labels['Lyra_PrivatePilotCanEnter'],[],p,registers=dict(a=word,x=0x6789,y=0x4567))
        require(row['returned'],'Admission helper failed RTL');cpu=row['registers']
        for key in ('a','x','y','sp','d','db'):require(cpu[key]==regs[key],'CanEnter changed '+key)
        require(cpu['p']&~1==p&~1 and bool(cpu['p']&1)==(word>=0xA2),'CanEnter flags/classification')
        stack_only(row);cases.append(dict(case='CanEnter',map_word=word,p=p,passed=True))
    # Full physical word from DP8A, not0700 true-cell or a masked low byte.
    for word,p in itertools.product((0x36,0x98,0xA0,0xA1,0xA2,0xC0,0x100,0x1A0,0xFFFF),(0x30,0x31,0xFE,0xFF)):
        row,regs=run(labels['Lyra_PrivatePilotCurrentMapAllowed'],[field(0x7E008A,word),field(0x7E0700,0xFFFF)],p)
        cpu=row['registers'];require(row['returned'],'Current map helper failed RTL')
        for key in ('a','x','y','sp','d','db'):require(cpu[key]==regs[key],'CurrentMap changed '+key)
        require(cpu['p']&~1==p&~1 and bool(cpu['p']&1)==(word>=0xA2),'CurrentMap flags/classification')
        stack_only(row);cases.append(dict(case='CurrentMap',map_word=word,p=p,passed=True))
    # Native highest-row table semantics and cached full words, without edits.
    rooms={int.from_bytes(image[L.A.pc(0x02DD8A)+i*2:L.A.pc(0x02DD8A)+i*2+2],'little'):i for i in range(79)}
    for room,parent,target in [(0x151,p,t) for p,t in ((0x36,0x36),(0x36,0x37),(0x98,0x98),(0xA0,0xA0),(0xA1,0xA1),(0xA0,0xA1),(0x36,0xA0),(0xA0,0x36),(0x100,0),(0,0x100),(0xFFFF,0xFFFF))]+[(0x83,0,None),(0xBEEF,0,None)]:
        row,regs=run(labels['Lyra_PrivatePilotEntryMap'],[field(0x7E00A0,room),field(0x7EC140,parent),field(0x7EC14C,target or 0)],0,
                     registers=dict(x=0x6789,y=0x4567))
        cached=0x100<=room<0x180 and room!=0x104
        expected=(target if parent<0xA2 and target<0xA2 and (max(parent,target)<0xA0 or parent==target) else None) if cached else image[L.A.pc(0x02DE28)+rooms[room]] if room in rooms else None
        cpu=row['registers'];require(row['returned'],'EntryMap bounded scan failed RTL')
        require(bool(cpu['p']&1)==(expected is None),'EntryMap wrong Carry')
        if expected is not None:require(cpu['a']==expected,'EntryMap masked/changed destination')
        for key in ('x','y','sp','d','db'):require(cpu[key]==regs[key],'EntryMap changed '+key)
        require(cpu['p']&~1==regs['p']&~1,'EntryMap changed P');stack_only(row)
        cases.append(dict(case='EntryMap',room=room,parent=parent,target=expected,steps=row['steps'],passed=True))
    def prefix(entry,writes,target):
        # Stop at the first boundary instruction, without executing Home/GFX.
        # Each reset run advances exactly one additional instruction; no code
        # patch, synthetic return, breakpoint or instruction stub is used.
        for limit in range(1,120):
            row,regs=run(entry,writes,max_steps=limit)
            pc=row['registers']['pb']<<16|row['registers']['pc']
            if pc==target:return row,regs,limit
        raise AssertionError('Prefix never reached '+hex(target))
    for target_word in (0x36,0xA0,0xA1,0xA2,0xC0,0x100,0xFFFF):
        admitted=target_word<0xA2;stop=0x0283CB if admitted else 0x34FC54
        writes=[field(0x7E0010,8),field(0x7E00A0,0x151),field(0x7EC140,target_word),field(0x7EC14C,target_word),field(0x7E0098,0x4433)]
        row,regs,steps=prefix(0x0283BF,writes,stop);cpu=row['registers']
        require(not row['returned'],'Prefix must stop before dispatcher return')
        require(cpu['sp']==regs['sp']-(5 if admitted else 8),'Module08/Home call frames wrong')
        low=row['reads'][0]['bytes'];stack=row['reads'][1]['bytes']
        require(low[0x99]==(0x82 if admitted else 0x44),'Preflight99 mutation/refusal differs')
        if not admitted:
            require(stack[0x2B:0x2D]==[0xC5,0x83],'Home lost original Module08 near return')
        stack_only(row,(0x7E0099,) if admitted else ())
        cases.append(dict(case='actual_Module08_entry_prefix',map_word=target_word,admitted=admitted,
                          stop_snes=stop,steps=steps,home_executed=False,passed=True))
    row,regs,steps=prefix(0x0283BF,[field(0x7E0010,0x0A),field(0x7E00A0,0xBEEF),field(0x7E0098,0x4433)],0x0283CB)
    require(row['registers']['sp']==regs['sp']-5,'Module0A original near frame changed')
    require(row['reads'][0]['bytes'][0x99]==0x82,'Module0A replay differs');stack_only(row,(0x7E0099,))
    cases.append(dict(case='Module0A_native_bypass_held',steps=steps,passed=True))
    # Actual mirror hook and native abort: no world XOR or map modulo occurs.
    for word in (0x80,0x98,0x9F,0xA0,0xA1,0xA2,0xC0,0x100,0x1A0,0xFFFF):
        writes=[field(0x7E008A,word),field(0x7E0010,0x1209),field(0x7E00B0,0xAA11),field(0x7E0200,0x7F),
                field(0x7EF3CA,0x40)]
        row,regs=run(0x02B217,writes);require(row['returned'],'Native mirror abort did not return')
        low=row['reads'][0]['bytes'];require(low[0x11]==0 and low[0xB0]==0,'Mirror did not take native abort')
        require(low[0x8A:0x8C]==list(word.to_bytes(2,'little')),'Mirror mapped invalid word into native area')
        require(row['reads'][2]['bytes'][0x16]==0x40,'Mirror changed saved world')
        stack_only(row,(0x7E0011,0x7E00B0,0x7E0200))
        cases.append(dict(case='actual_mirror_native_abort',map_word=word,passed=True))
    for word in (0,0x36,0x4B,0x7F):
        row,regs,steps=prefix(0x02B217,[field(0x7E008A,word)],0x02B21B)
        cpu=row['registers'];require(cpu['a']==0xAB00|word,'Native mirror original LDA changed')
        require(cpu['sp']==regs['sp']-3,'Native mirror stack changed');stack_only(row)
        cases.append(dict(case='native_mirror_original_branch_prefix',map_word=word,steps=steps,passed=True))
    if args.raw_output_dir:
        args.raw_output_dir.mkdir(parents=True,exist_ok=False)
        (args.raw_output_dir/'requests-results.jsonl').write_text(''.join(json.dumps(r)+'\n' for r in raw))
    require(args.rom.read_bytes()==image,'Fixture ROM changed')
    return dict(passed=True,case_count=len(cases),cpu_requests=len(raw),cases=cases,
        rom_sha256=hashlib.sha256(image).hexdigest(),runner_sha256=hashlib.sha256(args.cpu_runner.read_bytes()).hexdigest(),
        scope='emitted helper + actual Module08/mirror hook-prefix and native abort CPU proof; Home body/GFX/native gameplay not executed',
        held_roles=['FullLoad','SubLoad','Warp','Module0A','other native entry callers'])


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rom',type=Path,required=True)
    parser.add_argument('--symbols',type=Path,required=True)
    parser.add_argument('--cpu-runner',type=Path,required=True)
    parser.add_argument('--raw-output-dir',type=Path)
    parser.add_argument('--preaccess',action='store_true')
    args=parser.parse_args();image=args.rom.read_bytes();labels=L._labels(args.symbols.read_bytes())
    if args.preaccess:
        print(json.dumps(preaccess(args,image,labels),indent=2));return
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
