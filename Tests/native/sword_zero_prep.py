#!/usr/bin/env python3
"""Attach-only SF10 native Prep matrix. Explicit diagnostic fixtures, no route claim.

The caller owns the cold House session, reservation and positive process cleanup.
Only Sword and sprite fixture tables are written. The game executes state08,
its native property loader and dispatch, then the actual custom Prep. Break at
the immediate return boundaries before Main/combat; HP0/state09 alone never pass.
Uses the existing Portal regression's reviewed owner/pause/breakpoint methods.
"""
from __future__ import annotations
import argparse, hashlib, importlib.util, json, re, sys, time
from pathlib import Path
sys.dont_write_bytecode = True

SUPPORT_SHA = "bac027161d84ff12cc56a3a987f52545800da173c37044b22a5cae35ded6ce0f"
SPRITES, SIZE, SLOT = 0x7E0B00, 0x500, 15
SHIM, SHIM_RETURN = 0x068EB9, 0x068EBD
TYPES = (
    ("ThunderGhost", 0xCD, (6,10,12,16)),
    ("HelmetChuchu", 0x05, (8,12,15,16)),
    ("Booki", 0xCC, (4,8,16,24)),
    ("AntiKirby", 0xA8, (6,10,20,20)),
)
TASK_FILES = tuple("Sprites/Enemies/"+n+".asm" for n in
                   ("thunder_ghost","helmet_chuchu","booki","anti_kirby"))

def require(ok, message):
    if not ok: raise RuntimeError(message)
def sha(data): return hashlib.sha256(data).hexdigest()
def number(value): return int(value,0) if isinstance(value,str) else int(value)
def pc(address):
    require(address & 0x8000, "Expected LoROM address")
    return ((address>>16)&0x7F)*0x8000+(address&0x7FFF)
def raw(image,address,length): return image[pc(address):pc(address)+length]
def symbol(text,name):
    matches = re.findall(r"^([0-9A-Fa-f]{2}):([0-9A-Fa-f]{4})\s+(?:Oracle_)?"+
                         re.escape(name)+r"\s*$",text,re.MULTILINE)
    values = {int(a+b,16) for a,b in matches}
    require(len(values)==1,"Missing or ambiguous symbol: "+name)
    return values.pop()
def data(reply):
    require(reply.get("success"),"Native command rejected: "+str(reply))
    value=reply.get("data",{})
    return json.loads(value) if isinstance(value,str) else value
def load_support(path):
    require(sha(path.read_bytes())==SUPPORT_SHA,"Portal support source hash differs")
    spec=importlib.util.spec_from_file_location("sf10_portal_support",path)
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

def describe(image,text,expect):
    wrapper=symbol(text,"Sprite_PrepExp_Long")
    table=symbol(text,"NewSprPrepRoutinesLong")
    dispatch=symbol(text,"NewSprPrepTable")
    require(raw(image,SHIM,5)==b"\x22"+wrapper.to_bytes(3,"little")+b"\x60",
            "Native Prep JSL/RTS shim differs")
    require(raw(image,wrapper,9)==b"\x8b\x4b\xab\x22"+dispatch.to_bytes(3,"little")+b"\xab\x6b",
            "Custom Prep wrapper ABI differs")
    require(raw(image,0x06864D,10)==bytes.fromhex("2218B80DFED00DBD200E"),
            "Native state08 property-load/state09/dispatch prefix differs")
    require(raw(image,0x0DBA71,15)==bytes.fromhex("AD3721AD3C21651A6DA10F8DA10F6B"),
            "Native RNG writer changed; Helmet RNG allowance is not justified")
    plan=[]
    for name,sid,health in TYPES:
        start=symbol(text,"Sprite_"+name+"_Prep")
        fields={"health":(symbol(text,"Sprite_"+name+"_Prep_health"),0x0E50,health)}
        if name=="AntiKirby":
            fields["bump_damage"]=(symbol(text,"Sprite_"+name+"_Prep_bump_damage"),0x0CD2,(0x81,0x88,0x88,0x88))
            fields["prize_pack"]=(symbol(text,"Sprite_"+name+"_Prep_prize_pack"),0x0BE0,(6,3,3,3))
        code=raw(image,start,min(v[0] for v in fields.values())-start)
        require(code[:3]==bytes.fromhex("8B4BAB") and code[-2:]==bytes.fromhex("AB6B"),
                "Prep PHB/PHK/PLB ... PLB/RTL contract differs: "+name)
        index_at=12 if name=="AntiKirby" else 3
        expression=bytes.fromhex("AF59F37E")+(
            bytes.fromhex("3AA8") if expect=="baseline" else bytes.fromhex("F0013AA8"))
        require(code[index_at:index_at+len(expression)]==expression,
                "Sword indexing expression differs: "+name)
        require(raw(image,0x06865B+sid*2,2)==(SHIM&0xFFFF).to_bytes(2,"little"),
                "Native state08 table does not select custom shim: "+name)
        require(raw(image,table+sid*3,3)==start.to_bytes(3,"little"),
                "Expanded Prep pointer does not select exact symbol: "+name)
        decoded={}
        for key,(address,target,values) in fields.items():
            require(raw(image,address,4)==bytes(values),"Four-row table differs: "+name+"/"+key)
            pattern=b"\xb9"+(address&0xFFFF).to_bytes(2,"little")+b"\x9d"+target.to_bytes(2,"little")
            require(code.count(pattern)==1,"Missing/ambiguous indexed table store: "+name+"/"+key)
            decoded[key]=dict(table=address,target=target,store=start+code.index(pattern)+3,
                              rows=list(values),
                              sword0_baseline_byte=raw(image,address+0xFF,1)[0])
        plan.append(dict(name=name,sprite_id=sid,prep=start,fields=decoded))
    return dict(wrapper=wrapper,return_pc=wrapper+7,dispatch=dispatch,shim=SHIM,
                shim_return=SHIM_RETURN,expect=expect,plan=plan)

def fixture_class(portal):
    class PrepFixture(portal.Fixture):
        def __init__(self,args,bridge,code,image):
            super().__init__(args,bridge)
            self.deadline=time.monotonic()+240
            self.code,self.image,self.watches=code,image,set()
        def write(self,address,value,reason):
            tables={0x0DD0,0x0E20,0x0D00,0x0D10,0x0D20,0x0D30,
                    0x0F20,0x0E50,0x0CD2,0x0BE0}
            allowed=address==0x7EF359 or any(0x7E0000+t<=address<0x7E0010+t for t in tables)
            require(allowed,"Forbidden fixture write: "+hex(address))
            require(self.paused(),"Fixture write requires paused CPU")
            entry=dict(address=f"{address:06X}",before=self.b.read_memory(address),
                       value=value,reason=reason)
            self.result["writes"].append(entry)
            require(self.b.write_memory(address,value),"Fixture write rejected")
            entry["readback"]=self.b.read_memory(address)
            require(entry["readback"]==value,"Fixture readback differs")
        def watch(self,address):
            ident=number(data(self.b.mem_watch_add(address,1,64))["watch_id"])
            self.watches.add(ident); return ident
        def remove_watch(self,ident):
            data(self.b.mem_watch_remove(ident)); self.watches.remove(ident)
        def case(self,spec,sword):
            self.check_owner()
            require(self.paused(),"CPU must be paused before fixture")
            require((self.b.read_memory(0x7E0010),self.b.read_memory(0x7E0011),
                     self.b.read_memory16(0x7E00A0))==(7,0,0x104),"House context changed")
            for slot in range(16):
                self.write(0x7E0DD0+slot,0,"disable actors before native-init fixture")
                if slot!=SLOT:
                    for table,value in ((0x0E50,0x80+slot),(0x0CD2,0x60+slot),(0x0BE0,0x40+slot)):
                        self.write(0x7E0000+table+slot,value,"inactive-slot preservation canary")
            self.write(0x7EF359,sword,"explicit Sword0..4 diagnostic input")
            x=(self.b.read_memory16(0x7E0022)+0x30)&0xFFFF
            y=self.b.read_memory16(0x7E0020)
            for table,value in ((0x0E20,spec["sprite_id"]),(0x0D10,x&255),(0x0D30,x>>8),
                                (0x0D00,y&255),(0x0D20,y>>8),(0x0F20,0),
                                (0x0E50,0xD7),(0x0CD2,0xEE),(0x0BE0,0xED)):
                self.write(0x7E0000+table+SLOT,value,"state08 diagnostic actor input")
            watches={key:self.watch(0x7E0000+f["target"]+SLOT) for key,f in spec["fields"].items()}
            case=dict(sprite=spec["name"],sprite_id=spec["sprite_id"],sword=sword,slot=SLOT,passed=False)
            self.result["cases"].append(case)
            self.write(0x7E0DD0+SLOT,8,"let native SpriteModule_Initialize execute properties and Prep")
            case["native_dispatch_cpu"]=self.run_to({SHIM})
            caller=case["native_dispatch_cpu"]
            require(number(caller["x"])==SLOT,"Native dispatch used wrong sprite slot")
            case["prep_entry_cpu"]=self.run_to({spec["prep"]})
            entry=case["prep_entry_cpu"]
            require(number(entry["x"])==SLOT and number(entry["d"])==0 and
                    number(entry["dbr"])==0x30 and number(entry["p"])&0x30==0x30,
                    "Native M8/X8/DP0/DBR30 Prep ABI differs")
            require(number(entry["sp"])==number(caller["sp"])-7,"Native nested long-call stack differs")
            expected_stack=((self.code["return_pc"]-1)&0xFFFF).to_bytes(2,"little")+bytes([self.code["return_pc"]>>16])
            stack=self.block(0x7E0000+number(entry["sp"])+1,3)
            case["prep_return_stack"]=stack.hex()
            require(stack==expected_stack,"Native Prep long return bytes differ")
            before=self.block(SPRITES,SIZE)
            name=spec["name"]+"-sword"+str(sword)
            (self.a.output/(name+"-entry-sprites.bin")).write_bytes(before)
            case["expected_index"]=0xFF if sword==0 and self.a.expect=="baseline" else max(sword-1,0)
            case["expected"],case["stores"]={},{}
            for key,f in sorted(spec["fields"].items(),key=lambda kv:kv[1]["store"]):
                expected=raw(self.image,f["table"]+case["expected_index"],1)[0]
                case["expected"][key]=expected
                cpu=self.run_to({f["store"]}); case["stores"][key]=cpu
                require(number(cpu["x"])==SLOT and number(cpu["y"])==case["expected_index"] and
                        number(cpu["a"])&255==expected,"Actual indexed load/store registers differ")
            case["prep_return_cpu"]=self.run_to({self.code["return_pc"]})
            returned=case["prep_return_cpu"]
            require(number(returned["sp"])==number(entry["sp"])+3 and
                    number(returned["x"])==SLOT and number(returned["dbr"])==number(entry["dbr"]) and
                    number(returned["d"])==number(entry["d"]) and
                    number(returned["p"])&0x30==number(entry["p"])&0x30,"Prep return corrupted X/SP/DBR/DP/width ABI")
            after=self.block(SPRITES,SIZE)
            (self.a.output/(name+"-return-sprites.bin")).write_bytes(after)
            case["changed_sprite_addresses"]=[f"{SPRITES+i:06X}" for i,(a,b) in enumerate(zip(before,after)) if a!=b]
            allowed={0x7E0E50+SLOT}
            extra={"ThunderGhost":(0x0DF0,0x0E00),"HelmetChuchu":(0x0D80,0x0DB0,0x0E90,0x0D90),
                   "Booki":(0x0DB0,),"AntiKirby":(0x0CAA,0x0B6B,0x0DB0,0x0CD2,0x0BE0)}
            allowed|={0x7E0000+t+SLOT for t in extra[spec["name"]]}
            if spec["name"]=="HelmetChuchu": allowed.add(0x7E0FA1) # exact guarded GetRandomInt writer
            require(all(SPRITES+i in allowed for i,(a,b) in enumerate(zip(before,after)) if a!=b),
                    "Prep changed another slot or an unexpected sprite/global byte")
            case["observed"],case["write_provenance"]={},{}
            for key,f in spec["fields"].items():
                address=0x7E0000+f["target"]+SLOT
                value=self.b.read_memory(address); case["observed"][key]=value
                require(value==case["expected"][key],"Completed native Prep table result differs")
                blame=data(self.b.mem_blame(watch_id=watches[key])); case["write_provenance"][key]=blame
                writes=[w for w in blame["writes"] if number(w["pc"])==f["store"] and number(w["addr"])==address]
                require(len(writes)==1 and number(writes[0]["value"])==value and number(writes[0]["size"])==1,
                        "Missing unique actual Prep write provenance")
            case["native_return_cpu"]=self.run_to({SHIM_RETURN})
            native=case["native_return_cpu"]
            require(number(native["sp"])==number(caller["sp"]) and number(native["x"])==SLOT and
                    number(native["dbr"])==number(caller["dbr"]) and number(native["d"])==number(caller["d"]) and
                    number(native["p"])&0x30==number(caller["p"])&0x30,"Complete dispatch return ABI differs")
            require(self.b.read_memory(0x7E0DD0+SLOT)==9 and self.b.read_memory(0x7E0E20+SLOT)==spec["sprite_id"],
                    "Actual native Prep did not complete as the selected active sprite")
            require(self.b.read_memory(0x7EF359)==sword,"Sword input changed during initialization")
            case["unaffected_slot_canaries_preserved"]=True
            case["completed_before_main"]=True
            case["matches_intended_sword0_row"]=case["observed"]=={k:f["rows"][0] for k,f in spec["fields"].items()}
            if self.a.expect=="candidate" or sword:
                intended={k:f["rows"][max(sword-1,0)] for k,f in spec["fields"].items()}
                require(case["observed"]==intended,"Candidate or Sword1..4 intended table row differs")
            else:
                require(case["expected_index"]==255,"Baseline did not exercise FF underflow")
            for ident in watches.values(): self.remove_watch(ident)
            case["passed"]=True
    return PrepFixture

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    for name in ("socket","rom-sha256","rom-sha1","symbols-sha256","owner"):
        ap.add_argument("--"+name,required=True)
    for name in ("status-file","owned-rom","symbols","client-root","owner-file","output","support-file"):
        ap.add_argument("--"+name,type=Path,required=True)
    ap.add_argument("--pid",type=int,required=True)
    ap.add_argument("--expect",choices=("baseline","candidate"),required=True)
    ap.add_argument("--execute-fixtures",action="store_true")
    args=ap.parse_args()
    require(args.execute_fixtures and args.pid>0,"Explicit owned diagnostic fixture authorization required")
    image=args.owned_rom.read_bytes(); symbols=args.symbols.read_bytes()
    require(sha(image)==args.rom_sha256.lower(),"Owned ROM hash differs")
    require(hashlib.sha1(image).hexdigest()==args.rom_sha1.lower(),"Owned ROM SHA1 differs")
    require(sha(symbols)==args.symbols_sha256.lower(),"Symbols hash differs")
    code=describe(image,symbols.decode(),args.expect)
    portal=load_support(args.support_file)
    args.output.mkdir(parents=True,exist_ok=False)
    sys.path.insert(0,str(args.client_root.resolve()))
    from mesen2_client_lib.bridge import MesenBridge
    bridge=MesenBridge(args.socket,auto_reconnect=False,max_retries=0)
    fixture=fixture_class(portal)(args,bridge,code,image)
    fixture.result.update(schema="sf10-native-prep-v1",inputs=vars(args),code=code,
                          driver_sha256=sha(Path(__file__).read_bytes()),support_sha256=SUPPORT_SHA,
                          claim="explicit Sword/sprite init fixtures; no natural encounter/combat/route proof")
    owned=False; saved_before=None; sram_before=None; original_sword=None
    try:
        fixture.check_owner(); require(fixture.paused(),"Caller must supply paused owned CPU")
        require(not bridge.list_breakpoints(),"Existing breakpoints; refuse shared debug session")
        require(not data(bridge.mem_watch_list())["watches"],"Existing memory watches; refuse shared debug session")
        owned=True; fixture.input("")
        saved_before=fixture.block(0x7EF000,0x500)
        sram_before=bytes(bridge.read_block(0,8192,"SnesSaveRam"))
        require(len(sram_before)==8192,"Short native SRAM capture")
        original_sword=bridge.read_memory(0x7EF359)
        (args.output/"before-saved-wram.bin").write_bytes(saved_before)
        (args.output/"before-native-sram.bin").write_bytes(sram_before)
        for spec in code["plan"]:
            for sword in range(5): fixture.case(spec,sword)
        require(len(fixture.result["cases"])==20 and all(c["passed"] for c in fixture.result["cases"]),
                "Incomplete four-by-five matrix")
        fixture.result["runtime_checks_passed"]=True
    except BaseException as error:
        fixture.result["error"]=repr(error)
        if owned:
            try:
                bridge.pause(); fixture.result["failure_cpu"]=fixture.cpu()
                (args.output/"failure-sprites.bin").write_bytes(fixture.block(SPRITES,SIZE))
            except BaseException as capture: fixture.result["failure_capture_error"]=repr(capture)
    finally:
        if owned:
            for action in (lambda:fixture.input(""),bridge.pause):
                try: require(action() is not False,"Owned pause/release rejected")
                except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
            for ident in list(fixture.breakpoints):
                try: fixture.remove(ident)
                except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
            for ident in list(fixture.watches):
                try: fixture.remove_watch(ident)
                except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
            try:
                for slot in range(16): fixture.write(0x7E0DD0+slot,0,"fixture cleanup before caller disposes process")
                if original_sword is not None: fixture.write(0x7EF359,original_sword,"restore original Sword; no save")
                after=fixture.block(0x7EF000,0x500)
                live=bytes(bridge.read_block(0,8192,"SnesSaveRam"))
                (args.output/"after-saved-wram.bin").write_bytes(after)
                (args.output/"after-native-sram.bin").write_bytes(live)
                require(after==saved_before,"Nonfixture saved WRAM changed")
                require(live==sram_before,"Diagnostic init changed native SRAM")
                fixture.result["saved_wram_and_sram_preserved"]=True
            except BaseException as error: fixture.result["cleanup_errors"].append(repr(error))
        for path,pin in ((args.owned_rom,args.rom_sha256),(args.symbols,args.symbols_sha256),
                         (args.support_file,SUPPORT_SHA)):
            if sha(path.read_bytes())!=pin.lower(): fixture.result["cleanup_errors"].append("Input changed: "+str(path))
        fixture.result["passed"]=bool(fixture.result.get("runtime_checks_passed") and
                                      fixture.result.get("saved_wram_and_sram_preserved") and not fixture.result["cleanup_errors"])
        (args.output/"RESULT.json").write_text(json.dumps(fixture.result,indent=2,default=str)+"\n")
    print(json.dumps(dict(passed=fixture.result["passed"],result=str(args.output/"RESULT.json"))))
    return 0 if fixture.result["passed"] else 1

if __name__=="__main__": raise SystemExit(main())
