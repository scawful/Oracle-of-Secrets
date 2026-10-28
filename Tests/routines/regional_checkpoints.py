#!/usr/bin/env python3
"""Execute compiled checkpoint helpers in the existing offline CPU runner.

No live emulator/native HUD, module loader, Link movement or save proof. The
fixture's external cache-entry alias is not executed by these helper cases.
"""
import argparse
import hashlib
import itertools
import json
from pathlib import Path
import subprocess
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Scripts/Build'))
sys.path.insert(0,str(Path(__file__).resolve().parents[2]/'Scripts/Generate'))
from allocation_contracts import read_symbols


def require(ok,message):
    if not ok:raise AssertionError(message)


def physical(a):
    return 0x7E0000|(a&65535) if a>>16&127<64 and a&65535<8192 else a


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--rom',type=Path,required=True);p.add_argument('--symbols',type=Path,required=True)
    p.add_argument('--runner',type=Path,required=True);p.add_argument('--out',type=Path,required=True)
    args=p.parse_args();args.out.mkdir(exist_ok=False)
    rom=args.rom.read_bytes();labels=read_symbols(args.symbols)
    normal=[1,1,1,0,1];none=[1,1,0,0,0]
    plans=[]
    def case(name,entry,state=normal,expected=None,regs=None,values=None,route=None,carry=None,core=True):
        plans.append(dict(name=name,entry='Oracle_'+entry,state=state,expected=state if expected is None else expected,
                          regs=regs or {},values=values or {},route=route,carry=carry,core=core))
    case('migrate-new','Checkpoint_StateMigrate',[0]*5,none,carry=True)
    case('migrate-current','Checkpoint_StateMigrate',carry=False)
    case('migrate-intent-only','Checkpoint_StateMigrate',[1,1,1,0,9],[1,1,1,0,0],carry=True)
    case('migrate-retired','Checkpoint_StateMigrate',[1,2,1,0,1],none,carry=True)
    case('activate-good','Checkpoint_ActivateKey',none,normal,regs=dict(a=1,x=0,y=0x36),carry=True)
    for name,regs,region in [('key',dict(a=2,x=0,y=0x36),1),('domain',dict(a=1,x=2,y=0x36),1),
                             ('map',dict(a=1,x=0,y=0xA0),1),('region',dict(a=1,x=0,y=0x36),2)]:
        case('activate-refuse-'+name,'Checkpoint_ActivateKey',none,none,regs=regs,
             values={'region_arg':region},carry=False)
    case('cold-stale-current','Checkpoint_ResolveLoad',values={'indoors':1,'map':0xE0},route=2)
    case('cold-Home-keeps-key','Checkpoint_ResolveLoad',[1,1,1,0,0],route=1)
    case('warm-dungeon','Checkpoint_ResolveLoad',values={'indoors':1,'warm':1,'respawn':0},route=0)
    for name,values in [('factory',{'spawn':7}),('old-man',{'spawn':5}),('follower',{'follower':4}),
                        ('Abyss-native',{'world':0x40}),('Part00',{'game':0})]:
        case('legacy-'+name,'Checkpoint_ResolveLoad',values=values,route=0)
    case('invalid-native-index','Checkpoint_ResolveLoad',values={'spawn':0xFF},route=1)
    case('frame-source-control-activation','Checkpoint_OnFrame',[0]*5,normal,core=False)
    case('frame-contact-band','Checkpoint_OnFrame',[0]*5,normal,
         values={'px':0xD21,'py':0xE29},core=False)
    case('frame-wrong-point','Checkpoint_OnFrame',[0]*5,none,values={'px':0xD22},core=False)
    case('frame-before-anchor','Checkpoint_OnFrame',[0]*5,none,values={'px':0xD1F},core=False)
    case('frame-below-contact-band','Checkpoint_OnFrame',[0]*5,none,values={'py':0xE2A},core=False)
    case('frame-wrong-affinity','Checkpoint_OnFrame',none,none,values={'world':0x40},core=False)
    case('frame-entrance-animation','Checkpoint_OnFrame',none,none,values={'entrance_animation':1},core=False)
    case('frame-dungeon-tag-byte-independent','Checkpoint_OnFrame',[0]*5,normal,
         values={'entrance_animation':0x0100},core=False)
    case('prepare-non-anchor-same-region','Checkpoint_PrepareResume',[1,1,1,0,0],normal,values={'map':0x37},core=False)
    case('frame-non-anchor-does-not-activate','Checkpoint_OnFrame',[0]*5,none,values={'map':0x37},core=False)
    case('prepare-other-region','Checkpoint_PrepareResume',normal,[1,1,1,0,0],values={'map':0x4B},core=False)
    case('prepare-same-region','Checkpoint_PrepareResume',[1,1,1,0,0],normal,core=False)
    case('prepare-indoor-retains','Checkpoint_PrepareResume',values={'indoors':1,'map':0xE0},core=False)
    case('cold-context-replay','Checkpoint_ColdContext',core=False)
    requests=[]
    for plan in plans:
        flags=(0,1,0xCE,0xCF) if plan['core'] else (0x30,0x31,0xFE,0xFF)
        for flags,db,d in itertools.product(flags,(2,0x7E),(0,0x120)):
            v=dict(game=2,spawn=0,world=0,follower=0,map=0x36,indoors=0,warm=0,respawn=1,
                   px=0xD20,py=0xE28,entrance_animation=0,region_arg=1);v.update(plan['values'])
            regs=dict(a=0xABCD,x=0x6789 if plan['core'] else 0x67,y=0x1234 if plan['core'] else 0x45,
                      p=flags,db=db,d=d,sp=0x1FEF);regs.update(plan['regs'])
            writes=[]
            def write(a,b):writes.append(dict(address=a,bytes=list(b)))
            def word(a,n):write(a,n.to_bytes(2,'little'))
            write(0x7EF3B4,plan['state'])
            for a,n in [(0x7EF3C5,v['game']),(0x7EF3C8,v['spawn']),(0x7EF3CA,v['world']),(0x7EF3CC,v['follower'])]:write(a,[n])
            for a,n in [(0x8A,v['map']),(0x1B,v['indoors']),(0x20,v['py']),(0x22,v['px'])]:word(0x7E0000+d+a,n)
            for a,n in [(0x010A,v['warm']),(0x04AA,v['respawn']),(0x04C6,v['entrance_animation']),
                        (0x010E,0xCDAB),(0x0710,0x12EF),(0x1FF0,v['region_arg'])]:word(0x7E0000+a,n)
            req=dict(entry=labels[plan['entry']],reset_ram=True,registers=regs,writes=writes,
                     reads=[dict(address=0x7EF3B4,length=5),dict(address=0x7E010A,length=2),
                            dict(address=0x7E010E,length=2),dict(address=0x7E0710,length=2)],trace_writes=True,max_steps=3000)
            requests.append((plan,regs,req))
    raw=''.join(json.dumps(q)+'\n' for _,_,q in requests);(args.out/'requests.jsonl').write_text(raw)
    r=subprocess.run([str(args.runner),str(args.rom)],input=raw,capture_output=True,text=True,timeout=60)
    (args.out/'results.jsonl').write_text(r.stdout);(args.out/'stderr.log').write_text(r.stderr)
    require(r.returncode==0,'Runner failed: '+r.stderr);lines=r.stdout.splitlines();require(len(lines)==len(requests),'Missing results')
    cases=[]
    for (plan,regs,_),line in zip(requests,lines):
        row=json.loads(line);cpu=row['registers'];name=plan['name']+f"-P{regs['p']:02X}-DB{regs['db']:02X}-D{regs['d']:04X}"
        require(row.get('returned'),name+': no return '+str(row))
        require(not row.get('stub_calls') and not row.get('mmio_writes'),name+': external/MMIO call')
        require(row['reads'][0]['bytes']==plan['expected'],name+': wrong state '+str(row['reads'][0]))
        require(all(cpu[k]==regs[k] for k in ('d','db','sp','y')),name+': changed context '+str(cpu))
        if plan['route'] is not None:
            require(cpu['a']==plan['route'],name+': wrong route')
            require(cpu['x']==(0 if plan['route']==2 else regs['x']),name+': wrong index')
            require(cpu['p']&~0x82==regs['p']&~0x82,name+': changed non-result P')
        else:
            require(all(cpu[k]==regs[k] for k in ('a','x')),name+': changed A/X '+str(cpu))
            mask=1 if plan['carry'] is not None else 0
            require(cpu['p']&~mask==regs['p']&~mask,name+': changed P')
            if plan['carry'] is not None:require(bool(cpu['p']&1)==plan['carry'],name+': wrong carry')
        allowed=set(range(0x7E1F70,0x7E1FF2))|set(range(0x7F8000,0x7F8004))|set(range(0x7EF3B4,0x7EF3B9))
        if plan['name']=='cold-context-replay':
            allowed|={0x7E010A,0x7E010E,0x7E0710}
            require(row['reads'][1]['bytes']==[0,0] and row['reads'][2]['bytes']==[0,0xCD] and
                    row['reads'][3]['bytes']==[0,0x12],name+': original cold stores/warm clear')
        require(all(physical(w['address']) in allowed for w in row.get('writes',[])),name+': unowned write')
        cases.append(dict(name=name,steps=row['steps'],passed=True))
    require(args.rom.read_bytes()==rom,'Fixture ROM changed')
    report=dict(passed=True,cases=cases,count=len(cases),rom_sha256=hashlib.sha256(rom).hexdigest(),
                runner_sha256=hashlib.sha256(args.runner.read_bytes()).hexdigest(),
                claim='actual emitted helper/ABI/control-activation proof only; no native loader, gameplay or save/reopen')
    (args.out/'RESULT.json').write_text(json.dumps(report,indent=2)+'\n');print(json.dumps({k:v for k,v in report.items() if k!='cases'}))


if __name__=='__main__':main()
