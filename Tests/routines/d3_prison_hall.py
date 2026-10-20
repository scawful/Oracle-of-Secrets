#!/usr/bin/env python3
"""Bounded compiled D3 hall/gap/exit checks; synthetic WRAM, no engine stubs.

Does not prove guard choreography, collision geometry, or native traversal.
The pending-exit case executes the real room-save/key-save routines.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import subprocess
import tempfile

from d3_prison_state import FLAGS, SWORD, SP, digest, physical, require, symbol

RESUME = "D3Prison_ShouldResumeHall"
SELECT = "D3Prison_SelectGate"
GAP = "D3Prison_IsTinyPrisonGap"
EXIT = "D3Prison_RecordExit"
PLAYER = "D3Prison_PlayerControl"
PENDING = "D3Prison_PendingExitGate"
EXIT_MESSAGE_PENDING = 0x7FF368
EXIT_MESSAGE_MARKER = 0xD355
REGIONS = ((0x7E0000, 0x2000), (0x7EF000, 0x400), (0x7FF360, 0x20))


@dataclass(frozen=True)
class Case:
    name: str
    helper: str
    flags: int = 0x84
    sword: int = 2
    room: int = 0x56
    module: int = 7
    expected: int = 0  # Predicate Carry or native Select result.
    p: int = 0x75
    orphan: bool = False


def cases():
    return (
        Case("pending-hall-resumes", RESUME, expected=1, p=0x65),
        Case("later-sword-not-pending-hall", RESUME, sword=3),
        Case("pending-select-blocked", SELECT),
        Case("captured-select-remains-native", SELECT, flags=0xA1, sword=0, expected=0x20),
        Case("cell-gap-minish-only", GAP, flags=0xA1, sword=0, room=0x65, expected=1),
        Case("corridor-gap-minish-only", GAP, flags=0xA9, room=0x64, expected=1),
        Case("ordinary-gap-unchanged", GAP, flags=0xA1, sword=0, room=0x66),
        Case("escaped-gap-unchanged", GAP, flags=0xAB, room=0x65),
        Case("room55-exit-commits", EXIT, flags=0xA9, room=0x55, module=8),
        Case("other-room-exit-replays-only", EXIT, flags=0xA9, room=0x54, module=8),
        Case("already-escaped-exit-clears-stale-message", EXIT, flags=0xAB,
             room=0x55, module=8),
        Case("ordinary-player-callback-noop", PLAYER, flags=0, room=0x54),
        Case("one-orphan-releases-only-owned-locks", PLAYER, flags=0, orphan=True, p=0x65),
        Case("pending-exit-saves-and-reloads-hall", PENDING, module=8),
    )


def put(regions, address, value, width=1):
    for base, data in regions.items():
        if base <= address and address + width <= base + len(data):
            data[address-base:address-base+width] = value.to_bytes(width, "little")
            return
    raise AssertionError(f"Fixture outside inspected WRAM: ${address:06X}")


def fixture(case, entry):
    before = {base: bytearray((i*37 + 11) & 255 for i in range(size))
              for base, size in REGIONS}
    for address, value, width in (
        (0x7E0010,case.module,1),(0x7E0011,0,1),(0x7E001B,1,1),
        (0x7E00A0,case.room,2),(0x7E040C,0x10,1),(0x7E00F0,0x20,1),
        (FLAGS,case.flags,1),(SWORD,case.sword,1),
        (0x7E00A6,0,2),(0x7E00A9,0,2),
        (0x7E0400,0xA000,2),(0x7E0402,0x00B0,2),(0x7E0408,0x0100,2),
        (0x7EF36F,3,1),
        (EXIT_MESSAGE_PENDING,EXIT_MESSAGE_MARKER,2),
    ):
        put(before,address,value,width)
    # Empty slot arrays avoid accidental ownership from canaries. One ordinary
    # blue guard must survive the orphan-release case with its state intact.
    for base in (0x7E0DD0,0x7E0E20,0x7E0E30):
        for slot in range(16):
            put(before,base+slot,0)
    put(before,0x7E0DD2,9); put(before,0x7E0E22,0x41)
    for address in (0x7E02E4,0x7E0FFC,0x7E0FC1):
        put(before,address,1)
    if case.orphan:
        put(before,0x7E0DD5,9); put(before,0x7E0E25,0x41); put(before,0x7E0E35,0xE1)
    x,y = (0x47,0x5A) if case.p & 0x10 else (0xA547,0xB65A)
    registers = dict(a=0xBE11,x=x,y=y,p=case.p,db=0x35,d=0,sp=SP)
    request = dict(entry=entry,reset_ram=True,registers=registers,
                   writes=[dict(address=b,bytes=list(v)) for b,v in before.items()],
                   reads=[dict(address=b,length=len(v)) for b,v in before.items()],
                   trace_writes=True,max_steps=1800)
    return before,request


def verify(case,before,request,result):
    label=case.name
    require(result.get("returned"),f"{label}: CPU failure: {result.get('error')}")
    require(not result.get("stub_calls") and not result.get("mmio_writes"),
            f"{label}: unexpected stub/device access")
    regs=result["registers"]
    for key in ("x","y","db","d","sp"):
        require(regs[key]==request["registers"][key],f"{label}: ABI changed {key}")
    require(regs["e"]==0,f"{label}: left native CPU mode")
    expected={b:bytearray(v) for b,v in before.items()}
    allowed=set(range(0x7E0000+SP-0x40,0x7E0000+SP+1))
    allowed.update(range(0x7F8000,0x7F8004))  # Existing runner JSL trampoline.
    def change(address,value,width=1):
        put(expected,address,value,width)
        allowed.update(range(address,address+width))
    expected_p=case.p
    if case.helper in (RESUME,GAP):
        expected_p=(case.p&0xFE)|case.expected
    elif case.helper==SELECT:
        expected_p=(case.p&~0x82)|(0x02 if not case.expected else 0)
        require(regs["a"]==0xBE00|case.expected,f"{label}: original A result not replayed")
    elif case.helper==EXIT:
        require(regs["a"]==request["registers"]["a"],f"{label}: exit lost A")
        change(0x7E001B,0); change(0x7E0458,0)
        change(EXIT_MESSAGE_PENDING,0,2)
        if case.room==0x55 and case.flags==0xA9:
            change(FLAGS,0xAB)
            change(EXIT_MESSAGE_PENDING,EXIT_MESSAGE_MARKER,2)
    elif case.helper==PLAYER:
        change(EXIT_MESSAGE_PENDING,0,2)
        if case.orphan:
            change(0x7E0DD5,0); change(0x7E0E35,0)
            for address in (0x7E02E4,0x7E0FFC,0x7E0FC1): change(address,0)
    elif case.helper==PENDING:
        expected_p=case.p|1
        # Real Underworld_FlagRoomData_Quadrants: layout index0 -> visited08;
        # packed room word A000 | 0108 | (00B0>>4) = A10B. Keys use dungeon/2.
        for address,value,width in (
            (0x7E0000,0,1),(0x7E0006,0x000B,2),(0x7E0408,0x08,1),
            (0x7EF0AC,0xA10B,2),(0x7EF384,3,1),
            (0x7E010A,1,1),(0x7E010E,0x0028,2),(0x7E04AA,0,2),
            (0x7E0010,5,1),(0x7E0011,0,1),(0x7E0014,0,1),(0x7E00B0,0,1),
        ): change(address,value,width)
    require(regs["p"]==expected_p,f"{label}: status {regs['p']:02X} != {expected_p:02X}")
    require(len(result["reads"])==len(REGIONS),f"{label}: missing canary region")
    for (base,size),read in zip(REGIONS,result["reads"]):
        actual=bytes(read["bytes"])
        require(len(actual)==size,f"{label}: truncated canary region")
        for offset,(value,want) in enumerate(zip(actual,expected[base])):
            address=base+offset
            if not 0x7E0000+SP-0x40<=address<=0x7E0000+SP:
                require(value==want,f"{label}: ${address:06X}={value:02X}, expected {want:02X}")
    writes={physical(w["address"]) for w in result.get("writes",[])}
    require(writes<=allowed,f"{label}: undeclared writes {sorted(writes-allowed)}")
    if case.helper==EXIT:
        for address in (EXIT_MESSAGE_PENDING,EXIT_MESSAGE_PENDING+1):
            stores=[w["value"] for w in result.get("writes",[])
                    if physical(w["address"])==address]
            require(stores and stores[0]==0,
                    f"{label}: stale exit message was not cleared before the transaction")
    for base,data in expected.items():
        for offset,value in enumerate(data):
            if value!=before[base][offset]:
                require(base+offset in writes,f"{label}: missing traced expected store")
    return dict(name=label,helper=case.helper,passed=True,steps=result["steps"],registers=regs)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    for name in ("rom","symbols","cpu-runner"):
        parser.add_argument("--"+name,type=Path,required=True)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    inputs={p:p.read_bytes() for p in (args.rom,args.symbols,args.cpu_runner)}
    rom,symbols=inputs[args.rom],inputs[args.symbols].decode()
    require(0<len(rom)<=0x400000 and len(rom)%0x8000!=0x200,"Expected headerless LoROM <=4MiB")
    entries={name:symbol(symbols,name) for name in (RESUME,SELECT,GAP,EXIT,PLAYER,PENDING)}
    for address,name in ((0x02891B,SELECT),(0x02E4A6,EXIT),(0x0283CE,PENDING)):
        pc=(address>>16)*0x8000+(address&0x7FFF)
        require(rom[pc:pc+4]==b"\x22"+entries[name].to_bytes(3,"little"),
                f"Native hook ${address:06X} does not call tested {name}")
    if args.output:
        require(args.output.resolve() not in {p.resolve() for p in inputs},"Output overwrites input")
    plans=[(case,*fixture(case,entries[case.helper])) for case in cases()]
    padding=(-len(rom))%0x8000
    with tempfile.TemporaryDirectory(prefix="d3-prison-hall-") as folder:
        copy=Path(folder)/"candidate.sfc"; copy.write_bytes(rom+b"\xFF"*padding)
        run=subprocess.run([str(args.cpu_runner),str(copy)],
                           input="".join(json.dumps(p[2])+"\n" for p in plans),
                           capture_output=True,text=True,timeout=30,check=True)
    lines=run.stdout.splitlines()
    require(len(lines)==len(plans),"Wrong number of runner results")
    results=[verify(case,before,request,json.loads(line))
             for (case,before,request),line in zip(plans,lines)]
    require(all(p.read_bytes()==v for p,v in inputs.items()),"Input changed during test")
    report=dict(passed=True,case_count=len(results),cases=results,
                entries={n:f"{a:06X}" for n,a in entries.items()},
                input_sha256={str(p):digest(v) for p,v in inputs.items()},
                script_sha256=digest(Path(__file__).read_bytes()),
                imported_helpers_sha256=digest(Path(__file__).with_name("d3_prison_state.py").read_bytes()),
                runner_copy_padding_bytes=padding,source_inputs_unchanged=True,stubs=[],
                claim="Compiled hall/gap/exit CPU and ABI proof with synthetic WRAM; "
                      "not guard staging, native collision, controller traversal, or gameplay acceptance.")
    text=json.dumps(report,indent=2)+"\n"
    if args.output: args.output.write_text(text)
    print(text,end="")


if __name__=="__main__": main()
